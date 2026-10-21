"""Relais POST /api/ia de serveur.py (lot 4, ARCHITECTURE.md §17.2 ; CDC D66 ; CS69).

Toujours avec le faux fournisseur (tests/faux_fournisseur_ia.py), jamais un vrai modèle :
    - Ollama (api/tags, api/chat) et API compatible OpenAI (models, chat/completions) relayés ;
    - la clé est transmise au fournisseur en « Authorization: Bearer », et n'apparaît jamais dans une
      réponse du serveur, sa console, ni un fichier de données ;
    - liste fermée des chemins, adresse contrôlée (http ou https, sans identifiant, requête ni
      fragment), en-tête X-Prevo obligatoire, méthode POST seule ;
    - fournisseur injoignable → 502 ; délai dépassé → 504 ; réponse de plus de 2 Mo → 502 ;
      redirection non suivie ;
    - D67 côté serveur (relecture du lot 4) : une adresse hors de l'atelier (classée sans résolution DNS)
      est refusée (403) tant que `ia_distant_autorise` ne vaut pas 1 dans parametres.csv, sans aucun appel
      sortant ; la boucle locale est toujours relayée ;
    - jamais d'erreur 500 : délai non fini, adresse avec espace ou caractère de contrôle, clé illisible
      → 400 ; réponse coupée du fournisseur → 502 ; jamais la clé dans une réponse ni sur la console.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_serveur_ia.py" -v
"""
import importlib.util
import json
import socket
import time
import unittest
import urllib.error
import urllib.request

from commun import RACINE, ServeurPrevo
from faux_fournisseur_ia import FauxFournisseur

CLE = "sk-test-cle-secrete-123456"
REFUS_DISTANT = {"erreur": "Le responsable n'a pas autorisé les fournisseurs en ligne."}
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


class TestPorteeEtAutorisation(unittest.TestCase):
    """Fonctions pures du relais : portée de l'adresse (sans DNS) et lecture de ia_distant_autorise."""

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
        for url in en_ligne:
            with self.subTest(url=url):
                self.assertTrue(self.module.fournisseur_distant(url))

    def test_lecture_de_ia_distant_autorise(self):
        cas = (
            ("\N{ZERO WIDTH NO-BREAK SPACE}cle;valeur\r\nentreprise_nom;Atelier\r\nia_distant_autorise;'1\r\n",
             "utf-8", "1"),                                                      # avec BOM
            ("cle;valeur\r\nia_distant_autorise;1\r\n", "utf-8", "1"),
            ("cle;valeur\r\nia_distant_autorise;'1  \r\n", "utf-8", "1"),           # espaces de fin
            ("valeur;cle\r\n'1;ia_distant_autorise\r\n", "utf-8", "1"),             # colonnes dans le désordre
            ("cle,valeur\r\nia_distant_autorise,'1\r\n", "utf-8", "1"),             # séparateur « , »
            ("cle;valeur\r\n\"ia_distant_autorise\";\"'1\"\r\n", "utf-8", "1"),     # guillemets
            ("cle;valeur\r\nentreprise_nom;Atelier é\r\nia_distant_autorise;'1\r\n", "cp1252", "1"),
            ("cle;valeur\r\nia_distant_autorise;'0\r\n", "utf-8", "0"),
            ("cle;valeur\r\nia_distant_autorise;''1\r\n", "utf-8", "'1"),           # apostrophe doublée : « '1 »
            ("cle;valeur\r\nia_distant_autorise;'0\r\nia_distant_autorise;'1\r\n", "utf-8", "0"),  # 1re ligne
            ("cle;valeur\r\nentreprise_nom;'1\r\n", "utf-8", ""),
            ("cle;valeur\r\nia_distant_autorise\r\n", "utf-8", ""),
            ("n'importe quoi", "utf-8", ""),
            ("", "utf-8", ""),
        )
        for texte, encodage, attendu in cas:
            with self.subTest(texte=texte, encodage=encodage):
                self.assertEqual(self.module.valeur_parametre(texte.encode(encodage), "ia_distant_autorise"), attendu)


class TestRelaisIa(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.serveur = ServeurPrevo()
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)
        cls.faux = FauxFournisseur(lenteur_s=4, cle_attendue=CLE)
        cls.faux.demarrer()
        cls.addClassCleanup(cls.faux.arreter)

    def relayer(self, demande, entete_prevo=True, methode="POST", delai=30):
        """demande : objet envoyé en JSON, ou texte JSON déjà écrit (pour « 1e999 », « NaN »…)."""
        octets = (demande if isinstance(demande, str) else json.dumps(demande)).encode("utf-8")
        requete = urllib.request.Request(self.serveur.url + "/api/ia", data=octets if methode == "POST" else None,
                                         method=methode, headers={"Content-Type": "application/json"})
        if entete_prevo:
            requete.add_header("X-Prevo", "1")
        try:
            with urllib.request.urlopen(requete, timeout=delai) as reponse:
                return reponse.status, json.loads(reponse.read().decode("utf-8"))
        except urllib.error.HTTPError as erreur:
            texte = erreur.read().decode("utf-8")
            return erreur.code, json.loads(texte) if texte else {}

    def chat_ollama(self, modele="faux", **autres):
        demande = {"url": self.faux.url, "chemin": "api/chat", "methode": "POST",
                   "corps": {"model": modele, "stream": False,
                             "messages": [{"role": "system", "content": "Fonction : compteRendu"},
                                          {"role": "user", "content": "notes : garniture changée"}]}}
        demande.update(autres)
        return self.relayer(demande)

    def test_ollama_liste_des_modeles_et_chat_relayes(self):
        statut, reponse = self.relayer({"url": self.faux.url, "chemin": "api/tags", "methode": "GET"})
        self.assertEqual((statut, reponse["statut"]), (200, 200))
        self.assertIn("faux", [m["name"] for m in reponse["corps"]["models"]])
        statut, reponse = self.chat_ollama()
        self.assertEqual((statut, reponse["statut"]), (200, 200))
        self.assertIn("Constat", json.loads(reponse["corps"]["message"]["content"])["texte"])
        self.assertEqual(self.faux.requetes_vers("/api/chat")[-1]["corps"]["messages"][1]["content"], "notes : garniture changée")

    def test_openai_cle_transmise_et_jamais_rendue(self):
        demande = {"url": self.faux.url + "/v1", "chemin": "chat/completions", "methode": "POST", "cle": CLE,
                   "corps": {"model": "faux", "messages": [{"role": "system", "content": "Fonction : resumeHistorique"}]}}
        statut, reponse = self.relayer(demande)
        self.assertEqual((statut, reponse["statut"]), (200, 200))
        self.assertIn("garniture", reponse["corps"]["choices"][0]["message"]["content"])
        self.assertEqual(self.faux.requetes_vers("/v1/chat/completions")[-1]["entetes"]["authorization"], "Bearer " + CLE)
        self.assertNotIn(CLE, json.dumps(reponse))
        # Sans clé : le fournisseur refuse (401), le relais rend ce statut sans rien inventer
        demande.pop("cle")
        statut, reponse = self.relayer(demande)
        self.assertEqual((statut, reponse["statut"]), (200, 401))
        # Liste des modèles
        statut, reponse = self.relayer({"url": self.faux.url + "/v1", "chemin": "models", "methode": "GET", "cle": CLE})
        self.assertIn("faux", [m["id"] for m in reponse["corps"]["data"]])

    def test_cle_absente_de_la_console_et_des_donnees(self):
        self.relayer({"url": self.faux.url + "/v1", "chemin": "chat/completions", "methode": "POST", "cle": CLE,
                      "corps": {"model": "faux", "messages": [{"role": "system", "content": "Fonction : codes"}]}})
        self.relayer({"url": "ftp://exemple/", "chemin": "models", "methode": "GET", "cle": CLE})   # refus : la clé n'est pas citée
        self.assertNotIn(CLE, self.serveur.sortie_console())
        self.assertIn("POST /api/ia", self.serveur.sortie_console())
        for fichier in self.serveur.dossier.rglob("*"):
            if fichier.is_file():
                self.assertNotIn(CLE.encode("utf-8"), fichier.read_bytes(), fichier.name)

    def test_refus_chemin_adresse_entete_methode(self):
        for chemin in ("api/pull", "api/chat/../delete", "../serveur.py", "v1/chat/completions", "", "API/CHAT"):
            with self.subTest(chemin=chemin):
                statut, reponse = self.relayer({"url": self.faux.url, "chemin": chemin, "methode": "GET"})
                self.assertEqual(statut, 400)
                self.assertIn("erreur", reponse)
        for url in ("ftp://127.0.0.1:1/", "file:///C:/Windows", "http://moi:secret@127.0.0.1:1",
                    self.faux.url + "?x=1", self.faux.url + "#a", "pas une adresse", ""):
            with self.subTest(url=url):
                statut, reponse = self.relayer({"url": url, "chemin": "api/tags", "methode": "GET"})
                self.assertEqual(statut, 400)
                self.assertNotIn("secret", json.dumps(reponse))
        statut, _ = self.relayer({"url": self.faux.url, "chemin": "api/tags", "methode": "DELETE"})
        self.assertEqual(statut, 400)
        statut, _ = self.relayer({"url": self.faux.url, "chemin": "api/tags", "methode": "GET"}, entete_prevo=False)
        self.assertEqual(statut, 403)
        statut, _ = self.relayer({}, methode="GET")
        self.assertEqual(statut, 405)
        statut, _ = self.relayer(["pas", "un", "objet"])
        self.assertEqual(statut, 400)

    def test_fournisseur_injoignable_delai_et_reponse_trop_grande(self):
        statut, reponse = self.relayer({"url": "http://127.0.0.1:%d" % port_ferme(), "chemin": "api/tags", "methode": "GET"})
        self.assertEqual(statut, 502)
        self.assertIn("injoignable", reponse["erreur"])
        statut, reponse = self.chat_ollama("faux-lent", delai=1)
        self.assertEqual(statut, 504)
        statut, reponse = self.chat_ollama("faux-enorme")
        self.assertEqual(statut, 502)
        self.assertIn("trop grande", reponse["erreur"])

    def test_redirection_non_suivie(self):
        avant = len(self.faux.requetes_vers("/redirection-cible"))
        statut, reponse = self.chat_ollama("faux-redirige")
        self.assertEqual((statut, reponse["statut"]), (200, 302))
        self.assertEqual(len(self.faux.requetes_vers("/redirection-cible")), avant)

    # -- D67 côté serveur : le relais ne joint un service en ligne qu'avec l'accord du responsable --

    def regler_distant(self, ligne):
        """parametres.csv du dossier de données avec `ligne` (« ia_distant_autorise;'1 », écrite comme
        Prévo : BOM, « ; », CRLF, apostrophe de protection), ou sans la clé (None). Remis à la fin du test."""
        chemin = self.serveur.dossier / "parametres.csv"
        if not hasattr(self, "_parametres_origine"):
            self._parametres_origine = chemin.read_bytes()
            self.addCleanup(chemin.write_bytes, self._parametres_origine)
        lignes = [texte for texte in self._parametres_origine.decode("utf-8-sig").splitlines()
                  if not texte.startswith("ia_distant_autorise;")]
        if ligne is not None:
            lignes.append(ligne)
        chemin.write_bytes(BOM + "\r\n".join(lignes + [""]).encode("utf-8"))

    def test_fournisseur_en_ligne_refuse_sans_l_accord_du_responsable(self):
        """Une page quelconque du réseau, ou un localStorage modifié, ne fait pas sortir de données : 403
        immédiat, avant toute résolution de nom ou connexion (le délai de 3 s n'est jamais attendu)."""
        for ligne in (None, "ia_distant_autorise;'0", "ia_distant_autorise;''1"):
            self.regler_distant(ligne)
            for url in ("https://exemple.invalid/v1", "http://8.8.8.8:1/v1"):
                with self.subTest(parametre=ligne, url=url):
                    debut = time.monotonic()
                    statut, reponse = self.relayer({"url": url, "chemin": "models", "methode": "GET", "cle": CLE,
                                                    "delai": 3})
                    self.assertEqual((statut, reponse), (403, REFUS_DISTANT))
                    self.assertLess(time.monotonic() - debut, 2, "refus immédiat : aucune connexion tentée")
        self.assertNotIn(CLE, self.serveur.sortie_console())

    def test_fournisseur_en_ligne_relaye_avec_l_accord_du_responsable(self):
        for ligne in ("ia_distant_autorise;'1", "ia_distant_autorise;1"):
            self.regler_distant(ligne)
            with self.subTest(parametre=ligne):
                # Plus de refus : l'appel part, et échoue puisque l'hôte n'existe pas (nom réservé .invalid)
                statut, reponse = self.relayer({"url": "https://exemple.invalid/v1", "chemin": "models",
                                                "methode": "GET", "cle": CLE, "delai": 5})
                self.assertEqual(statut, 502)
                self.assertIn("injoignable", reponse["erreur"])
        statut, reponse = self.relayer({"url": "http://8.8.8.8:1/v1", "chemin": "models", "methode": "GET",
                                        "cle": CLE, "delai": 1})
        self.assertIn(statut, (502, 504))       # selon le réseau : refus aussitôt, ou rien dans le délai
        # Nom que le réseau ne sait pas écrire (étiquette vide) : demande invalide, pas une erreur du serveur
        statut, reponse = self.relayer({"url": "http://a..b/v1", "chemin": "models", "methode": "GET", "cle": CLE})
        self.assertEqual(statut, 400)
        self.assertNotIn(CLE, json.dumps(reponse) + self.serveur.sortie_console())

    def test_boucle_locale_relayee_sans_accord_du_responsable(self):
        self.regler_distant("ia_distant_autorise;'0")
        port = self.faux.url.rsplit(":", 1)[1]
        for url in ("http://127.0.0.1:" + port, "http://localhost:" + port):
            with self.subTest(url=url):
                statut, reponse = self.relayer({"url": url, "chemin": "api/tags", "methode": "GET"})
                self.assertEqual((statut, reponse["statut"]), (200, 200))
                self.assertIn("faux", [m["name"] for m in reponse["corps"]["models"]])

    # -- Jamais d'erreur 500 : demande invalide → 400, échec côté fournisseur → 502 --

    def test_demandes_invalides_et_reponses_coupees_jamais_d_erreur_500(self):
        modele = '{"url": %s, "chemin": "models", "methode": "GET", "cle": "%s", "delai": %s}'
        for delai in ("1e999", "-1e999", "Infinity", "NaN"):
            with self.subTest(delai=delai):
                statut, reponse = self.relayer(modele % (json.dumps(self.faux.url + "/v1"), CLE, delai))
                self.assertEqual(statut, 400)
                self.assertIn("Délai", reponse["erreur"])
        for url in (self.faux.url + "/v 1", self.faux.url + "/v\t1", self.faux.url + "/v\x011", self.faux.url + "/v\x7f1",
                    self.faux.url + "/v\N{NO-BREAK SPACE}1", "http://exemple .invalid/v1"):
            with self.subTest(url=url):
                statut, reponse = self.relayer({"url": url, "chemin": "models", "methode": "GET", "cle": CLE})
                self.assertEqual(statut, 400)
                self.assertIn("Adresse", reponse["erreur"])
        for cle in ("sk-\N{EURO SIGN}-illisible", "sk-\x00-illisible"):
            with self.subTest(cle=cle):
                statut, reponse = self.relayer({"url": self.faux.url + "/v1", "chemin": "models", "methode": "GET",
                                                "cle": cle})
                self.assertEqual(statut, 400)
                self.assertNotIn(cle, json.dumps(reponse, ensure_ascii=False))
        for modele_coupe in ("faux-tronque", "faux-tronque-morceaux"):
            with self.subTest(modele=modele_coupe):
                statut, reponse = self.chat_ollama(modele_coupe, cle=CLE)
                self.assertEqual(statut, 502)
                self.assertIn("incomplète", reponse["erreur"])
                self.assertNotIn(CLE, json.dumps(reponse))
        console = self.serveur.sortie_console()
        self.assertNotIn(CLE, console)
        self.assertNotIn("Traceback", console)


if __name__ == "__main__":
    unittest.main()
