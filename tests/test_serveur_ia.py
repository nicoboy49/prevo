"""Relais POST /api/ia de serveur.py (lot 4, ARCHITECTURE.md §17.2 ; CDC D66 ; CS69 ; lot 7, §22.12, audit M1 à M3).

Toujours avec le faux fournisseur (tests/faux_fournisseur_ia.py), jamais un vrai modèle. Depuis T158 (audit M1, M3),
le fournisseur, son adresse et sa clé sont réglés sur le PC serveur (--ia-url, --ia-fournisseur, --ia-en-ligne,
variable PREVO_IA_CLE) : chaque serveur de ces tests est lancé avec son fournisseur, et la requête ne porte que
chemin, methode et corps (le refus d'une adresse, d'une clé ou d'un délai dans la requête, scénario de l'annexe A
de l'audit, est dans tests/test_audit_ia.py) :
    - Ollama (api/tags, api/chat) et API compatible OpenAI (models, chat/completions) relayés ;
    - la clé du PC serveur est transmise au fournisseur en « Authorization: Bearer », et n'apparaît jamais dans une
      réponse du serveur, sa console, ni un fichier de données ;
    - liste fermée des chemins, adresse du PC serveur contrôlée (http ou https, sans identifiant, requête ni
      fragment, ni espace ou caractère de contrôle), en-tête X-Prevo obligatoire, méthode POST seule ;
    - fournisseur injoignable → 502 ; délai dépassé → 504 (vérifié sur appeler_fournisseur avec un délai court : le
      relais a désormais un délai fixe de 120 s) ; réponse de plus de 2 Mo → 502 ; redirection non suivie ;
    - D67 côté serveur (relecture du lot 4 ; audit M2) : une adresse hors de l'atelier (classée sans résolution DNS)
      est refusée (403) tant que le PC serveur ne l'autorise pas (--ia-en-ligne ou « ia_en_ligne »), sans aucun
      appel sortant et quoi que dise parametres.csv ; la boucle locale est toujours relayée ;
    - jamais d'erreur 500 : délai dans la requête, adresse avec espace ou caractère de contrôle, clé illisible
      → 400 ; réponse coupée du fournisseur → 502 ; jamais la clé dans une réponse ni sur la console.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_serveur_ia.py" -v
"""
import importlib.util
import json
import socket
import tempfile
import time
import unittest
import urllib.error
import urllib.request

from commun import RACINE, ServeurPrevo
from faux_fournisseur_ia import FauxFournisseur
from test_ia_regles import taire_coupures

CLE = "sk-test-cle-secrete-123456"
REFUS_DISTANT = {"erreur": "Les fournisseurs d'IA en ligne ne sont pas autorisés sur le PC serveur."}
REGLE_SUR_LE_SERVEUR = "réglées sur le PC serveur"
BOM = b"\xef\xbb\xbf"


def port_ferme():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def charger_serveur():
    """serveur.py chargé comme un module (sans le lancer), pour tester ses fonctions pures."""
    specification = importlib.util.spec_from_file_location("serveur_teste_ia", RACINE / "serveur.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def lancer(*arguments, cle=None):
    """Serveur Prévo lancé avec ses réglages d'IA (et la variable PREVO_IA_CLE si `cle`)."""
    serveur = ServeurPrevo(arguments=list(arguments), environnement={"PREVO_IA_CLE": cle} if cle else None)
    serveur.demarrer()
    return serveur


def relayer(serveur, demande, entete_prevo=True, methode="POST", delai=30):
    """demande : objet envoyé en JSON, ou texte JSON déjà écrit (pour « 1e999 », « NaN »…)."""
    octets = (demande if isinstance(demande, str) else json.dumps(demande)).encode("utf-8")
    requete = urllib.request.Request(serveur.url + "/api/ia", data=octets if methode == "POST" else None,
                                     method=methode, headers={"Content-Type": "application/json"})
    if entete_prevo:
        requete.add_header("X-Prevo", "1")
    try:
        with urllib.request.urlopen(requete, timeout=delai) as reponse:
            return reponse.status, json.loads(reponse.read().decode("utf-8"))
    except urllib.error.HTTPError as erreur:
        texte = erreur.read().decode("utf-8")
        return erreur.code, json.loads(texte) if texte else {}


def regler_distant(serveur, ligne):
    """parametres.csv du dossier de données avec `ligne` (« ia_distant_autorise;'1 », écrite comme Prévo : BOM,
    « ; », CRLF, apostrophe de protection), ou sans la clé (None)."""
    chemin = serveur.dossier / "parametres.csv"
    lignes = [texte for texte in chemin.read_bytes().decode("utf-8-sig").splitlines()
              if not texte.startswith("ia_distant_autorise;")]
    if ligne is not None:
        lignes.append(ligne)
    chemin.write_bytes(BOM + "\r\n".join(lignes + [""]).encode("utf-8"))


class TestPorteeEtAutorisation(unittest.TestCase):
    """Fonctions pures du relais : portée de l'adresse (sans DNS), adresse du PC serveur contrôlée, décision
    « IA en ligne » du PC serveur, délai fixe, réponse lue sans la clé."""

    @classmethod
    def setUpClass(cls):
        cls.module = charger_serveur()

    def test_portee_decidee_sans_resolution_dns(self):
        dans_l_atelier = (
            "http://localhost:11434", "http://LOCALHOST:11434", "http://127.0.0.1:11434", "http://127.8.9.10",
            "http://[::1]:11434", "http://[::ffff:127.0.0.1]:11434", "http://10.1.2.3:11434", "http://172.16.0.1",
            "http://172.31.255.254", "http://192.168.1.20:11434", "http://169.254.1.1", "http://[fd12:3456::1]:11434",
            "http://[fe80::1]:11434", "http://pc-atelier.local:11434", "https://serveur-ia.atelier.local/v1")
        en_ligne = (
            "https://api.mistral.ai/v1", "https://exemple.invalid/v1", "http://8.8.8.8:1/v1", "http://172.32.0.1",
            "http://192.169.0.1", "http://[2001:4860:4860::8888]/v1", "http://[::ffff:8.8.8.8]/v1", "http://[::]:11434",
            "http://0.0.0.0:11434", "http://2130706433:11434", "http://127.1:11434", "http://127.0.0.1.nip.io/v1",
            "http://ia.localhost:11434", "http://localhost.:11434", "http://local:11434", "http://pc-atelier.lan:11434",
            "http://pc-atelier.local.exemple.fr/v1")
        for url in dans_l_atelier:
            with self.subTest(url=url):
                self.assertFalse(self.module.fournisseur_distant(url))
                self.assertIn(self.module.portee_fournisseur(url), ("pc-atelier", "atelier"))
        for url in en_ligne:
            with self.subTest(url=url):
                self.assertTrue(self.module.fournisseur_distant(url))
                self.assertEqual(self.module.portee_fournisseur(url), "distant")

    def test_ia_en_ligne_decidee_par_le_pc_serveur_jamais_par_parametres_csv(self):
        """Audit M2 : l'accord vient de « ia_en_ligne » (ou --ia-en-ligne) ; parametres.csv, que tout appareil du
        réseau peut écrire, n'y est plus pour rien, quelle que soit la façon dont la clé y est écrite."""
        with tempfile.TemporaryDirectory() as dossier:
            config = self.module.Configuration(dossier, [])
            for ligne in ("cle;valeur\r\nia_distant_autorise;'1\r\n", "\N{ZERO WIDTH NO-BREAK SPACE}cle;valeur\r\n"
                          "ia_distant_autorise;1\r\n", "cle,valeur\r\nia_distant_autorise,'1\r\n", ""):
                with open(self.module.chemin_table(config, "parametres"), "w", encoding="utf-8", newline="") as fichier:
                    fichier.write(ligne)
                for en_ligne in (False, True):
                    with self.subTest(parametres=ligne, ia_en_ligne=en_ligne):
                        config.reglages = dict(self.module.reglages_par_defaut(), ia_en_ligne=en_ligne)
                        self.assertIs(self.module.distant_autorise(config), en_ligne)
            config.reglages = self.module.reglages_par_defaut()
            self.assertFalse(self.module.distant_autorise(config), "défaut : refusé")

    def test_adresse_du_pc_serveur_controlee(self):
        """L'adresse lue dans la configuration est contrôlée comme l'était celle de la requête (400, jamais 500),
        sans jamais être reprise dans le message."""
        for url in ("ftp://127.0.0.1:1/", "file:///C:/Windows", "http://moi:secret@127.0.0.1:1", "http://127.0.0.1:1?x=1",
                    "http://127.0.0.1:1#a", "pas une adresse", "", "http://127.0.0.1:1/v 1", "http://127.0.0.1:1/v\t1",
                    "http://127.0.0.1:1/v\x011", "http://127.0.0.1:1/v\x7f1", "http://127.0.0.1:1/v\N{NO-BREAK SPACE}1",
                    "http://exemple .invalid/v1", "http://127.0.0.1:99999"):
            with self.subTest(url=url):
                with self.assertRaises(self.module.ErreurHttp) as refus:
                    self.module.adresse_fournisseur(url)
                self.assertEqual(refus.exception.statut, 400)
                self.assertIn("Adresse", refus.exception.message)
                self.assertNotIn("secret", refus.exception.message)
                self.assertEqual(self.module.adresse_ia_configuree({"ia_url": url}), "")

    def test_cle_illisible_refusee_sans_etre_citee(self):
        reglages = self.module.reglages_par_defaut()
        for cle in ("sk-\N{EURO SIGN}-illisible", "sk-\x00-illisible"):
            with self.subTest(cle=cle):
                with self.assertRaises(self.module.ErreurHttp) as refus:
                    self.module.lire_demande_ia(b'{"chemin": "models", "methode": "GET"}', dict(reglages, _ia_cle=cle))
                self.assertEqual(refus.exception.statut, 400)
                self.assertNotIn(cle, refus.exception.message)

    def test_delai_depasse_504_et_delai_fixe_du_relais(self):
        """Le délai n'est plus choisi par la requête : DELAI_IA_S (120 s) ; le passage du délai en 504 est vérifié sur
        appeler_fournisseur, avec un délai court posé par le test (« faux-lent » répond en 4 s)."""
        self.assertEqual(self.module.DELAI_IA_S, 120)
        with FauxFournisseur(lenteur_s=4) as faux:
            taire_coupures(faux)          # le test abandonne exprès la réponse lente
            corps = json.dumps({"chemin": "api/chat", "methode": "POST", "corps": {"model": "faux-lent", "stream": False,
                                "messages": [{"role": "system", "content": "Fonction : compteRendu"}]}}).encode("utf-8")
            demande = self.module.lire_demande_ia(corps, dict(self.module.reglages_par_defaut(), ia_url=faux.url))
            self.assertEqual(demande["delai"], 120)
            demande["delai"] = 1
            debut = time.monotonic()
            with self.assertRaises(self.module.ErreurHttp) as refus:
                self.module.appeler_fournisseur(demande)
            self.assertEqual(refus.exception.statut, 504)
            self.assertLess(time.monotonic() - debut, 3.5)

    def test_reponse_rendue_sans_la_cle(self):
        self.assertEqual(self.module.sans_la_cle(b'{"recu": "Bearer ' + CLE.encode() + b'"}', CLE),
                         b'{"recu": "Bearer [cle masquee]"}')
        self.assertEqual(self.module.sans_la_cle(b'{"a": 1}', ""), b'{"a": 1}')
        # Clé trop courte pour être masquée sans abîmer la réponse (un mot du texte) : réponse rendue telle quelle
        self.assertEqual(self.module.sans_la_cle(b'{"texte": "test de pompe"}', "test"), b'{"texte": "test de pompe"}')


class TestRelaisIa(unittest.TestCase):
    """Un faux fournisseur pour la classe ; un PC serveur réglé sur Ollama (sans clé), un autre sur l'API compatible
    OpenAI du même faux fournisseur, avec la clé (PREVO_IA_CLE)."""

    @classmethod
    def setUpClass(cls):
        cls.faux = FauxFournisseur(lenteur_s=4, cle_attendue=CLE)
        cls.faux.demarrer()
        cls.addClassCleanup(cls.faux.arreter)
        cls.ollama = lancer("--ia-url", cls.faux.url)
        cls.addClassCleanup(cls.ollama.arreter)
        cls.openai = lancer("--ia-url", cls.faux.url + "/v1", "--ia-fournisseur", "openai", cle=CLE)
        cls.addClassCleanup(cls.openai.arreter)

    def chat_ollama(self, modele="faux"):
        return relayer(self.ollama, {"chemin": "api/chat", "methode": "POST",
                                     "corps": {"model": modele, "stream": False,
                                               "messages": [{"role": "system", "content": "Fonction : compteRendu"},
                                                            {"role": "user", "content": "notes : garniture changée"}]}})

    def test_ollama_liste_des_modeles_et_chat_relayes(self):
        statut, reponse = relayer(self.ollama, {"chemin": "api/tags", "methode": "GET"})
        self.assertEqual((statut, reponse["statut"]), (200, 200))
        self.assertIn("faux", [m["name"] for m in reponse["corps"]["models"]])
        statut, reponse = self.chat_ollama()
        self.assertEqual((statut, reponse["statut"]), (200, 200))
        self.assertIn("Constat", json.loads(reponse["corps"]["message"]["content"])["texte"])
        self.assertEqual(self.faux.requetes_vers("/api/chat")[-1]["corps"]["messages"][1]["content"], "notes : garniture changée")
        self.assertNotIn("authorization", self.faux.requetes_vers("/api/chat")[-1]["entetes"], "sans clé sur le serveur, aucune")

    def test_openai_cle_transmise_et_jamais_rendue(self):
        demande = {"chemin": "chat/completions", "methode": "POST",
                   "corps": {"model": "faux", "messages": [{"role": "system", "content": "Fonction : compteRendu"}]}}
        statut, reponse = relayer(self.openai, demande)
        self.assertEqual((statut, reponse["statut"]), (200, 200))
        self.assertIn("garniture", reponse["corps"]["choices"][0]["message"]["content"])
        self.assertEqual(self.faux.requetes_vers("/v1/chat/completions")[-1]["entetes"]["authorization"], "Bearer " + CLE)
        self.assertNotIn(CLE, json.dumps(reponse))
        # Liste des modèles
        statut, reponse = relayer(self.openai, {"chemin": "models", "methode": "GET"})
        self.assertIn("faux", [m["id"] for m in reponse["corps"]["data"]])
        # Sans clé sur le PC serveur : le fournisseur refuse (401), le relais rend ce statut sans rien inventer
        sans_cle = lancer("--ia-url", self.faux.url + "/v1", "--ia-fournisseur", "openai")
        self.addCleanup(sans_cle.arreter)
        statut, reponse = relayer(sans_cle, demande)
        self.assertEqual((statut, reponse["statut"]), (200, 401))

    def test_cle_absente_de_la_console_et_des_donnees(self):
        relayer(self.openai, {"chemin": "chat/completions", "methode": "POST",
                              "corps": {"model": "faux", "messages": [{"role": "system", "content": "Fonction : codes"}]}})
        relayer(self.openai, {"url": "ftp://exemple/", "chemin": "models", "methode": "GET"})   # refus : la clé n'est pas citée
        relayer(self.openai, {"chemin": "api/pull", "methode": "GET"})
        console = self.openai.sortie_console()
        self.assertNotIn(CLE, console)
        self.assertIn("POST '/api/ia'", console)                                # chemin en repr (audit I2, T159)
        self.assertIn("clé réglée", console)
        for fichier in self.openai.dossier.rglob("*"):
            if fichier.is_file():
                self.assertNotIn(CLE.encode("utf-8"), fichier.read_bytes(), fichier.name)

    def test_refus_chemin_adresse_entete_methode(self):
        for chemin in ("api/pull", "api/chat/../delete", "../serveur.py", "v1/chat/completions", "", "API/CHAT"):
            with self.subTest(chemin=chemin):
                statut, reponse = relayer(self.ollama, {"chemin": chemin, "methode": "GET"})
                self.assertEqual(statut, 400)
                self.assertIn("erreur", reponse)
        # Une adresse dans la requête n'est plus lue : refus (le détail de l'annexe A est dans test_audit_ia)
        statut, reponse = relayer(self.ollama, {"url": self.faux.url, "chemin": "api/tags", "methode": "GET"})
        self.assertEqual(statut, 400)
        self.assertIn(REGLE_SUR_LE_SERVEUR, reponse["erreur"])
        statut, _ = relayer(self.ollama, {"chemin": "api/tags", "methode": "DELETE"})
        self.assertEqual(statut, 400)
        statut, _ = relayer(self.ollama, {"chemin": "api/tags", "methode": "GET"}, entete_prevo=False)
        self.assertEqual(statut, 403)
        statut, _ = relayer(self.ollama, {}, methode="GET")
        self.assertEqual(statut, 405)
        statut, _ = relayer(self.ollama, ["pas", "un", "objet"])
        self.assertEqual(statut, 400)
        # Adresse invalide réglée sur le PC serveur : 400 à chaque demande, jamais reprise ni rendue
        invalide = lancer("--ia-url", "http://moi:secret@127.0.0.1:1")
        self.addCleanup(invalide.arreter)
        statut, reponse = relayer(invalide, {"chemin": "api/tags", "methode": "GET"})
        self.assertEqual(statut, 400)
        self.assertIn("Adresse", reponse["erreur"])
        with urllib.request.urlopen(invalide.url + "/api/ia/reglages", timeout=10) as lu:
            publics = json.loads(lu.read().decode("utf-8"))
        self.assertEqual(publics["url"], "")
        self.assertNotIn("secret", json.dumps(reponse) + json.dumps(publics) + invalide.sortie_console())

    def test_fournisseur_injoignable_delai_et_reponse_trop_grande(self):
        eteint = lancer("--ia-url", "http://127.0.0.1:%d" % port_ferme())
        self.addCleanup(eteint.arreter)
        statut, reponse = relayer(eteint, {"chemin": "api/tags", "methode": "GET"})
        self.assertEqual(statut, 502)
        self.assertIn("injoignable", reponse["erreur"])
        # Délai : fixé par le serveur (120 s) ; « faux-lent » (4 s) passe donc, le 504 est vérifié sur la fonction
        statut, reponse = self.chat_ollama("faux-lent")
        self.assertEqual((statut, reponse["statut"]), (200, 200))
        statut, reponse = self.chat_ollama("faux-enorme")
        self.assertEqual(statut, 502)
        self.assertIn("trop grande", reponse["erreur"])

    def test_redirection_non_suivie(self):
        avant = len(self.faux.requetes_vers("/redirection-cible"))
        statut, reponse = self.chat_ollama("faux-redirige")
        self.assertEqual((statut, reponse["statut"]), (200, 302))
        self.assertEqual(len(self.faux.requetes_vers("/redirection-cible")), avant)

    # -- D67 côté serveur (audit M2) : un service en ligne seulement avec l'accord du PC serveur --

    def test_fournisseur_en_ligne_refuse_sans_l_accord_du_pc_serveur(self):
        """Une page quelconque du réseau, un localStorage ou un parametres.csv modifiés ne font pas sortir de
        données : 403 immédiat, avant toute résolution de nom ou connexion."""
        for url in ("https://exemple.invalid/v1", "http://8.8.8.8:1/v1"):
            serveur = lancer("--ia-url", url, "--ia-fournisseur", "openai", cle=CLE)
            self.addCleanup(serveur.arreter)
            for ligne in (None, "ia_distant_autorise;'0", "ia_distant_autorise;''1", "ia_distant_autorise;'1",
                          "ia_distant_autorise;1"):
                regler_distant(serveur, ligne)
                with self.subTest(parametre=ligne, url=url):
                    debut = time.monotonic()
                    statut, reponse = relayer(serveur, {"chemin": "models", "methode": "GET"})
                    self.assertEqual((statut, reponse), (403, REFUS_DISTANT))
                    self.assertLess(time.monotonic() - debut, 2, "refus immédiat : aucune connexion tentée")
            self.assertNotIn(CLE, serveur.sortie_console())

    def test_fournisseur_en_ligne_relaye_avec_l_accord_du_pc_serveur(self):
        for options in (["--ia-en-ligne"], []):
            with self.subTest(options=options):
                with tempfile.TemporaryDirectory() as dossier:
                    # L'accord par la ligne de commande, ou par « ia_en_ligne » du fichier de configuration
                    configuration = dossier + "/prevo.config.json"
                    with open(configuration, "w", encoding="utf-8") as fichier:
                        json.dump({"ia_en_ligne": not options}, fichier)
                    serveur = lancer("--ia-url", "https://exemple.invalid/v1", "--ia-fournisseur", "openai",
                                     "--config", configuration, *options, cle=CLE)
                    try:
                        # Plus de refus : l'appel part, et échoue puisque l'hôte n'existe pas (nom réservé .invalid)
                        statut, reponse = relayer(serveur, {"chemin": "models", "methode": "GET"}, delai=150)
                        self.assertEqual(statut, 502)
                        self.assertIn("injoignable", reponse["erreur"])
                        self.assertNotIn(CLE, json.dumps(reponse) + serveur.sortie_console())
                    finally:
                        serveur.arreter()
        # Nom que le réseau ne sait pas écrire (étiquette vide) : demande invalide, pas une erreur du serveur
        mauvais_nom = lancer("--ia-url", "http://a..b/v1", "--ia-fournisseur", "openai", "--ia-en-ligne", cle=CLE)
        self.addCleanup(mauvais_nom.arreter)
        statut, reponse = relayer(mauvais_nom, {"chemin": "models", "methode": "GET"})
        self.assertEqual(statut, 400)
        self.assertNotIn(CLE, json.dumps(reponse) + mauvais_nom.sortie_console())

    def test_boucle_locale_relayee_sans_accord_du_pc_serveur(self):
        port = self.faux.url.rsplit(":", 1)[1]
        parametres = self.ollama.dossier / "parametres.csv"
        self.addCleanup(parametres.write_bytes, parametres.read_bytes())
        regler_distant(self.ollama, "ia_distant_autorise;'0")
        localhost = lancer("--ia-url", "http://localhost:" + port)
        self.addCleanup(localhost.arreter)
        for serveur, url in ((self.ollama, "http://127.0.0.1:" + port), (localhost, "http://localhost:" + port)):
            with self.subTest(url=url):
                statut, reponse = relayer(serveur, {"chemin": "api/tags", "methode": "GET"})
                self.assertEqual((statut, reponse["statut"]), (200, 200))
                self.assertIn("faux", [m["name"] for m in reponse["corps"]["models"]])

    # -- Jamais d'erreur 500 : demande invalide → 400, échec côté fournisseur → 502 --

    def test_demandes_invalides_et_reponses_coupees_jamais_d_erreur_500(self):
        modele = '{"chemin": "models", "methode": "GET", "delai": %s}'
        for delai in ("1e999", "-1e999", "Infinity", "NaN", "5"):
            with self.subTest(delai=delai):
                statut, reponse = relayer(self.openai, modele % delai)
                self.assertEqual(statut, 400)
                self.assertIn(REGLE_SUR_LE_SERVEUR, reponse["erreur"])
        for modele_coupe in ("faux-tronque", "faux-tronque-morceaux"):
            with self.subTest(modele=modele_coupe):
                statut, reponse = self.chat_ollama(modele_coupe)
                self.assertEqual(statut, 502)
                self.assertIn("incomplète", reponse["erreur"])
                self.assertNotIn(CLE, json.dumps(reponse))
        for serveur in (self.ollama, self.openai):
            console = serveur.sortie_console()
            self.assertNotIn(CLE, console)
            self.assertNotIn("Traceback", console)


if __name__ == "__main__":
    unittest.main()
