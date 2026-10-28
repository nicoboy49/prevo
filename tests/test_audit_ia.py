# -*- coding: utf-8 -*-
"""Audit M1, M2, M3 et I5 : le fournisseur d'IA est réglé sur le PC serveur, plus dans le navigateur
(lot 7, T158 ; ARCHITECTURE.md §22.12 ; CS134).

Rejoue l'annexe A du rapport d'audit avec le refus attendu, toujours sur de faux services locaux (jamais un vrai
modèle, aucun appel ne quitte le PC) :
    étape 4 (M1)    POST /api/ia avec « url » ou « cle » (ou « delai », ou toute autre clé) → 400 « l'adresse et la
                    clé du fournisseur sont réglées sur le PC serveur » ; le faux service local ne reçoit rien ;
    M3              serveur lancé avec --ia-url vers un faux fournisseur et PREVO_IA_CLE : la requête relayée porte
                    « Authorization: Bearer <clé du serveur> » et pas d'autre (l'en-tête Authorization du client
                    n'est jamais relayé, avec ou sans clé sur le serveur) ; la clé ne figure dans aucune réponse
                    — même recopiée par le fournisseur —, aucun message d'erreur, aucune ligne de la console du
                    serveur, aucun fichier de données ;
    étapes 2 puis 5 (M2)  un PUT /api/csv/parametres avec ia_distant_autorise = 1 n'autorise rien : un fournisseur
                    distant (192.0.2.1, comme l'audit) reste refusé, 403 avant tout appel sortant ; --ia-en-ligne
                    l'autorise (l'appel part) ;
    GET /api/ia/reglages  { fournisseur, url, cle_reglee, en_ligne, portee }, jamais la clé ;
    lancement       ligne de commande > fichier > défauts ; clé : PREVO_IA_CLE > « ia_cle » du fichier, jamais une
                    option de la ligne de commande, jamais recopiée dans le fichier ;
    navigateur (M3, I5)  en mode serveur, aucune clé dans le navigateur : celle d'un ancien réglage de prevo.ia est
                    effacée, Ia.reglages() n'en a pas, chaque POST /api/ia ne porte que chemin, methode et corps, la
                    page ne la montre jamais ; « Ce poste » dit « réglée sur le serveur », sans champ de clé.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_audit_ia.py" -v
"""
import contextlib
import http.client
import http.server
import importlib.util
import io
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from commun import CasNavigateur, RACINE, ServeurPrevo, attendre_pret, preregler_profil  # noqa: E402
from faux_fournisseur_ia import FauxFournisseur  # noqa: E402

CLE_SERVEUR = "sk-cle-du-pc-serveur-7c21e4"
CLE_DU_POSTE = "CLE-SECRETE-DU-POSTE"                # celle de l'annexe A, étape 4
CLE_DU_CLIENT = "cle-glissee-par-un-client-93b0"
REGLE_SUR_LE_SERVEUR = "l'adresse et la clé du fournisseur sont réglées sur le PC serveur"
REFUS_EN_LIGNE = "Les fournisseurs d'IA en ligne ne sont pas autorisés sur le PC serveur."
BOM = b"\xef\xbb\xbf"


def charger_serveur():
    specification = importlib.util.spec_from_file_location("serveur_prevo_audit_ia", RACINE / "serveur.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


serveur = charger_serveur()


class ServiceLocal:
    """Faux service local de l'annexe A : note chaque requête reçue (méthode, chemin, Authorization, corps) et
    répond un JSON qui RECOPIE l'en-tête Authorization reçu (un fournisseur bavard : la clé ne doit pas ressortir
    du relais pour autant)."""

    def __init__(self):
        self.recus = []
        service = self

        class Gestionnaire(http.server.BaseHTTPRequestHandler):
            def _tout(self):
                longueur = int(self.headers.get("Content-Length") or 0)
                corps = self.rfile.read(longueur) if longueur else b""
                service.recus.append({"methode": self.command, "chemin": self.path,
                                      "authorization": self.headers.get("Authorization"),
                                      "corps": corps.decode("utf-8", "replace")})
                reponse = json.dumps({"data": [{"id": "modele-x"}], "recu": self.headers.get("Authorization")})
                octets = reponse.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(octets)))
                self.end_headers()
                self.wfile.write(octets)

            do_GET = _tout
            do_POST = _tout

            def log_message(self, *arguments):
                pass

        self._serveur = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Gestionnaire)
        self._serveur.daemon_threads = True
        self.url = "http://127.0.0.1:%d" % self._serveur.server_address[1]
        threading.Thread(target=self._serveur.serve_forever, daemon=True).start()

    def arreter(self):
        self._serveur.shutdown()
        self._serveur.server_close()


def requete(serveur_prevo, methode, chemin, corps=None, entetes=None, delai=30):
    """(statut, en-têtes, octets) d'une requête au serveur Prévo ; `corps` : objet (envoyé en JSON) ou octets."""
    if corps is not None and not isinstance(corps, bytes):
        corps = json.dumps(corps).encode("utf-8")
    connexion = http.client.HTTPConnection("127.0.0.1", serveur_prevo.port, timeout=delai)
    try:
        tout = {"X-Prevo": "1"}
        if corps is not None:
            tout["Content-Type"] = "application/json"
        tout.update(entetes or {})
        connexion.request(methode, chemin, body=corps, headers=tout)
        reponse = connexion.getresponse()
        return reponse.status, dict(reponse.getheaders()), reponse.read()
    finally:
        connexion.close()


def reglages_publics(serveur_prevo):
    statut, _, octets = requete(serveur_prevo, "GET", "/api/ia/reglages")
    if statut != 200:
        raise AssertionError("GET /api/ia/reglages -> %d" % statut)
    return json.loads(octets.decode("utf-8")), octets


# ---------------------------------------------------------------------------
# Fonctions de serveur.py, sans réseau
# ---------------------------------------------------------------------------

class TestDemandeEtLancement(unittest.TestCase):
    """Lecture de la demande de relais, réglages du lancement, réglages publics."""

    def reglages(self, **valeurs):
        reglages = serveur.reglages_par_defaut()
        reglages.update(valeurs)
        return reglages

    def lire(self, demande, **reglages):
        return serveur.lire_demande_ia(json.dumps(demande).encode("utf-8"), self.reglages(**reglages))

    def test_toute_autre_cle_que_chemin_methode_corps_refusee(self):
        base = {"chemin": "models", "methode": "GET"}
        for en_trop in ({"url": "http://127.0.0.1:8766/interne/admin"}, {"cle": CLE_DU_POSTE}, {"delai": 5},
                        {"modele": "faux"}, {"Authorization": "Bearer " + CLE_DU_CLIENT}, {"URL": "http://exemple.invalid"}):
            with self.subTest(cle=list(en_trop)):
                with self.assertRaises(serveur.ErreurHttp) as refus:
                    self.lire(dict(base, **en_trop), _ia_cle=CLE_SERVEUR)
                self.assertEqual(refus.exception.statut, 400)
                self.assertIn(REGLE_SUR_LE_SERVEUR, refus.exception.message)
                for texte in [str(v) for v in en_trop.values()] + [CLE_SERVEUR]:
                    self.assertNotIn(texte, refus.exception.message)

    def test_adresse_cle_et_delai_du_serveur(self):
        demande = self.lire({"chemin": "models", "methode": "GET"}, ia_url="http://127.0.0.1:9/v1/", _ia_cle=CLE_SERVEUR)
        self.assertEqual((demande["cible"], demande["methode"], demande["octets"]), ("http://127.0.0.1:9/v1/models", "GET", None))
        self.assertEqual(demande["entetes"], {"Accept": "application/json", "Authorization": "Bearer " + CLE_SERVEUR})
        self.assertEqual(demande["delai"], serveur.DELAI_IA_S)
        self.assertEqual(serveur.DELAI_IA_S, 120)
        corps = {"model": "faux", "messages": [{"role": "user", "content": "notes"}]}
        demande = self.lire({"chemin": "chat/completions", "methode": "POST", "corps": corps}, ia_url="http://localhost:1234/v1")
        self.assertEqual(demande["cible"], "http://localhost:1234/v1/chat/completions")
        self.assertEqual(json.loads(demande["octets"].decode("utf-8")), corps)
        self.assertNotIn("Authorization", demande["entetes"], "sans clé sur le serveur, aucune")
        # Clé du fichier seulement (pas de variable d'environnement lue) : c'est elle
        self.assertEqual(self.lire({"chemin": "api/tags", "methode": "GET"}, ia_cle="cle-du-fichier")["entetes"]["Authorization"],
                         "Bearer cle-du-fichier")
        # Clé illisible (non ASCII) : 400, sans la citer
        with self.assertRaises(serveur.ErreurHttp) as refus:
            self.lire({"chemin": "models", "methode": "GET"}, _ia_cle="sk-\N{EURO SIGN}-illisible")
        self.assertEqual(refus.exception.statut, 400)
        self.assertNotIn("sk-\N{EURO SIGN}-illisible", refus.exception.message)
        self.assertNotIn("sk-", refus.exception.message)
        # Adresse du serveur invalide : 400 sans la reprendre
        with self.assertRaises(serveur.ErreurHttp) as refus:
            self.lire({"chemin": "models", "methode": "GET"}, ia_url="http://moi:secret@127.0.0.1:1")
        self.assertEqual(refus.exception.statut, 400)
        self.assertNotIn("secret", refus.exception.message)

    def test_lancement_ligne_de_commande_fichier_et_variable_d_environnement(self):
        with tempfile.TemporaryDirectory() as dossier, mock.patch.dict(os.environ):
            os.environ.pop("PREVO_IA_CLE", None)
            chemin = Path(dossier) / "prevo.config.json"
            par_defaut = serveur.reglages_du_lancement(serveur.lire_arguments(["--config", str(chemin)]))
            self.assertEqual((par_defaut["ia_fournisseur"], par_defaut["ia_url"], par_defaut["ia_en_ligne"],
                              serveur.cle_ia(par_defaut)), ("ollama", "http://localhost:11434", False, ""))
            chemin.write_text(json.dumps({"ia_fournisseur": "openai", "ia_url": "http://192.168.1.20:1234/v1",
                                          "ia_cle": "cle-du-fichier", "ia_en_ligne": False}), encoding="utf-8")
            du_fichier = serveur.reglages_du_lancement(serveur.lire_arguments(["--config", str(chemin)]))
            self.assertEqual((du_fichier["ia_fournisseur"], du_fichier["ia_url"], du_fichier["ia_en_ligne"],
                              serveur.cle_ia(du_fichier)), ("openai", "http://192.168.1.20:1234/v1", False, "cle-du-fichier"))
            # La ligne de commande passe avant le fichier
            options = serveur.lire_arguments(["--config", str(chemin), "--ia-url", " http://localhost:11434 ",
                                              "--ia-fournisseur", "ollama", "--ia-en-ligne"])
            lance = serveur.reglages_du_lancement(options)
            self.assertEqual((lance["ia_fournisseur"], lance["ia_url"], lance["ia_en_ligne"], serveur.cle_ia(lance)),
                             ("ollama", "http://localhost:11434", True, "cle-du-fichier"))
            # PREVO_IA_CLE passe avant « ia_cle » du fichier, sans jamais y être recopiée
            os.environ["PREVO_IA_CLE"] = "  " + CLE_SERVEUR + "  "
            avec_variable = serveur.reglages_du_lancement(serveur.lire_arguments(["--config", str(chemin)]))
            self.assertEqual(serveur.cle_ia(avec_variable), CLE_SERVEUR)
            self.assertEqual(avec_variable["ia_cle"], "cle-du-fichier")
            copie = Path(dossier) / "copie.config.json"
            serveur.ecrire_configuration(str(copie), avec_variable)
            self.assertNotIn(CLE_SERVEUR, copie.read_text(encoding="utf-8"))
            # Aucune option de la ligne de commande pour la clé (elle serait visible dans la liste des processus)
            for option in ("--ia-cle", "--ia-key", "--cle-ia"):
                with self.subTest(option=option), contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        serveur.lire_arguments(["--config", str(chemin), option, CLE_SERVEUR])
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                serveur.lire_arguments(["--ia-fournisseur", "mistral"])

    def test_reglages_publics_portee_et_jamais_la_cle(self):
        cas = (
            ("http://localhost:11434", "ollama", False, "http://localhost:11434", "pc-atelier"),
            ("http://[::1]:11434", "ollama", False, "http://[::1]:11434", "pc-atelier"),
            ("http://127.0.0.1:1234/v1/", "openai", False, "http://127.0.0.1:1234/v1", "pc-atelier"),
            ("http://192.168.1.20:11434", "ollama", False, "http://192.168.1.20:11434", "atelier"),
            ("http://pc-atelier.local:1234/v1", "openai", False, "http://pc-atelier.local:1234/v1", "atelier"),
            ("https://api.mistral.ai/v1", "openai", True, "https://api.mistral.ai/v1", "distant"),
            ("http://ia.localhost:11434", "ollama", False, "http://ia.localhost:11434", "distant"),
            ("http://moi:secret@127.0.0.1:1", "ollama", False, "", "distant"),     # adresse invalide : jamais rendue
            ("", "ollama", False, "", "distant"),
        )
        for url, fournisseur, en_ligne, rendue, portee in cas:
            with self.subTest(url=url):
                config = serveur.Configuration(tempfile.gettempdir(), [])
                config.reglages = self.reglages(ia_url=url, ia_fournisseur=fournisseur, ia_en_ligne=en_ligne,
                                                _ia_cle=CLE_SERVEUR)
                publics = serveur.reglages_ia_publics(config)
                self.assertEqual(publics, {"fournisseur": fournisseur, "url": rendue, "cle_reglee": True,
                                           "en_ligne": en_ligne, "portee": portee})
                self.assertNotIn(CLE_SERVEUR, json.dumps(publics))
                self.assertNotIn("secret", json.dumps(publics))
        config.reglages = self.reglages()
        self.assertFalse(serveur.reglages_ia_publics(config)["cle_reglee"])
        self.assertFalse(serveur.distant_autorise(config), "défaut : fournisseurs en ligne refusés")


# ---------------------------------------------------------------------------
# Relais : étape 4 (M1) et clé du serveur (M3)
# ---------------------------------------------------------------------------

class TestRelaisAudit(unittest.TestCase):
    """Serveur réglé comme un PC d'atelier avec un service compatible OpenAI et sa clé (PREVO_IA_CLE)."""

    @classmethod
    def setUpClass(cls):
        cls.service = ServiceLocal()
        cls.addClassCleanup(cls.service.arreter)
        cls.serveur = ServeurPrevo(arguments=["--ia-url", cls.service.url + "/v1", "--ia-fournisseur", "openai"],
                                   environnement={"PREVO_IA_CLE": CLE_SERVEUR})
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)

    def setUp(self):
        self.service.recus.clear()

    def relayer(self, demande, entetes=None):
        statut, _, octets = requete(self.serveur, "POST", "/api/ia", demande, entetes)
        texte = octets.decode("utf-8")
        return statut, texte, json.loads(texte) if texte else {}

    def test_etape_4_adresse_ou_cle_dans_la_requete_refusee_sans_aucun_appel(self):
        port = self.service.url.rsplit(":", 1)[1]
        annexe = {"url": "http://127.0.0.1:%s/interne/admin" % port, "chemin": "models", "methode": "GET",
                  "cle": CLE_DU_POSTE, "delai": 5}                       # la demande de l'étape 4, telle quelle
        demandes = [annexe] + [{"chemin": "models", "methode": "GET", nom: annexe[nom]} for nom in ("url", "cle", "delai")]
        for demande in demandes:
            with self.subTest(cles=sorted(demande)):
                statut, texte, reponse = self.relayer(demande)
                self.assertEqual(statut, 400)
                self.assertIn(REGLE_SUR_LE_SERVEUR, reponse["erreur"])
                self.assertNotIn(CLE_DU_POSTE, texte)
                self.assertNotIn(CLE_SERVEUR, texte)
        self.assertEqual(self.service.recus, [], "le service local ne reçoit rien")

    def test_seule_la_cle_du_serveur_part_vers_le_fournisseur(self):
        statut, texte, reponse = self.relayer({"chemin": "models", "methode": "GET"},
                                              {"Authorization": "Bearer " + CLE_DU_CLIENT})
        self.assertEqual((statut, reponse["statut"]), (200, 200))
        self.assertEqual(reponse["corps"]["data"], [{"id": "modele-x"}])
        corps = {"model": "modele-x", "messages": [{"role": "user", "content": "notes : garniture changée"}]}
        statut, texte_chat, reponse_chat = self.relayer({"chemin": "chat/completions", "methode": "POST", "corps": corps})
        self.assertEqual((statut, reponse_chat["statut"]), (200, 200))
        self.assertEqual([(r["methode"], r["chemin"], r["authorization"]) for r in self.service.recus],
                         [("GET", "/v1/models", "Bearer " + CLE_SERVEUR),
                          ("POST", "/v1/chat/completions", "Bearer " + CLE_SERVEUR)])
        self.assertEqual(json.loads(self.service.recus[1]["corps"]), corps)
        # Le service recopie l'en-tête reçu : la clé est masquée avant de repartir vers le poste
        for texte_rendu, rendu in ((texte, reponse), (texte_chat, reponse_chat)):
            self.assertNotIn(CLE_SERVEUR, texte_rendu)
            self.assertNotIn(CLE_DU_CLIENT, texte_rendu)
            self.assertEqual(rendu["corps"]["recu"], "Bearer [cle masquee]")

    def test_reglages_publics_sans_la_cle(self):
        publics, octets = reglages_publics(self.serveur)
        self.assertEqual(publics, {"fournisseur": "openai", "url": self.service.url + "/v1", "cle_reglee": True,
                                   "en_ligne": False, "portee": "pc-atelier"})
        self.assertNotIn(CLE_SERVEUR.encode("utf-8"), octets)
        statut, _, _ = requete(self.serveur, "POST", "/api/ia/reglages", {})
        self.assertEqual(statut, 405)
        statut, _, _ = requete(self.serveur, "PUT", "/api/ia/reglages", {"en_ligne": True})
        self.assertEqual(statut, 405)
        self.assertEqual(reglages_publics(self.serveur)[0]["en_ligne"], False)

    def test_cle_jamais_dans_la_console_ni_les_fichiers(self):
        self.relayer({"chemin": "models", "methode": "GET"})
        self.relayer({"chemin": "api/pull", "methode": "GET"})                    # refus 400
        self.relayer({"url": "ftp://exemple.invalid/", "chemin": "models", "cle": CLE_DU_POSTE})
        reglages_publics(self.serveur)
        console = self.serveur.sortie_console()
        self.assertIn("POST '/api/ia'", console)                                # chemin en repr (audit I2, T159)
        self.assertIn("Assistant IA     : API compatible OpenAI, %s/v1 ; clé réglée ; fournisseurs en ligne refusés."
                      % self.service.url, console)
        self.assertNotIn(CLE_SERVEUR, console)
        self.assertNotIn(CLE_DU_POSTE, console)
        self.assertNotIn("Traceback", console)
        for fichier in sorted(self.serveur.dossier.rglob("*")):
            if fichier.is_file():
                with self.subTest(fichier=fichier.name):
                    self.assertNotIn(CLE_SERVEUR.encode("utf-8"), fichier.read_bytes())


class TestRelaisSansCle(unittest.TestCase):
    """Serveur sans clé (Ollama sur ce PC) : l'en-tête Authorization d'un client n'est jamais relayé."""

    def test_authorization_du_client_jamais_relaye(self):
        service = ServiceLocal()
        self.addCleanup(service.arreter)
        with ServeurPrevo(arguments=["--ia-url", service.url]) as sans_cle:
            statut, _, octets = requete(sans_cle, "POST", "/api/ia", {"chemin": "api/tags", "methode": "GET"},
                                        {"Authorization": "Bearer " + CLE_DU_CLIENT})
            self.assertEqual(statut, 200)
            self.assertEqual([(r["chemin"], r["authorization"]) for r in service.recus], [("/api/tags", None)])
            self.assertNotIn(CLE_DU_CLIENT.encode("utf-8"), octets)
            self.assertEqual(reglages_publics(sans_cle)[0], {"fournisseur": "ollama", "url": service.url,
                                                              "cle_reglee": False, "en_ligne": False,
                                                              "portee": "pc-atelier"})
            self.assertIn("Assistant IA     : Ollama, %s ; sans clé ; fournisseurs en ligne refusés." % service.url,
                          sans_cle.sortie_console())


# ---------------------------------------------------------------------------
# Étapes 2 puis 5 (M2) : l'accord pour l'IA en ligne ne s'écrit plus par un PUT
# ---------------------------------------------------------------------------

class TestEnLigneAudit(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Adresse « distante » non routable de l'audit : un appel tenté attendrait le délai, un refus est immédiat.
        cls.refuse = ServeurPrevo(arguments=["--ia-url", "http://192.0.2.1", "--ia-fournisseur", "openai"],
                                  environnement={"PREVO_IA_CLE": CLE_SERVEUR})
        cls.refuse.demarrer()
        cls.addClassCleanup(cls.refuse.arreter)

    def test_etapes_2_puis_5_parametres_ecrit_par_un_client_n_autorise_rien(self):
        # Étape 2 : un client du réseau écrit ia_distant_autorise = 1 dans parametres.csv (la table reste écrite par
        # les postes ; c'est le relais qui ne s'y fie plus)
        statut, entetes, octets = requete(self.refuse, "GET", "/api/csv/parametres")
        self.assertEqual(statut, 200)
        lignes = [ligne for ligne in octets.decode("utf-8-sig").split("\r\n")
                  if ligne and not ligne.startswith("ia_distant_autorise;")]
        nouveau = BOM + "\r\n".join(lignes + ["ia_distant_autorise;1", ""]).encode("utf-8")
        statut, _, octets = requete(self.refuse, "PUT", "/api/csv/parametres", nouveau,
                                    {"X-Version-Attendue": entetes["X-Version"], "Content-Type": "text/csv"})
        self.assertEqual(statut, 200, octets)
        self.assertIn(b"\r\nia_distant_autorise;1\r\n", (self.refuse.dossier / "parametres.csv").read_bytes())
        # Étape 5 : le relais refuse aussitôt, sans tenter l'appel sortant
        for demande in ({"chemin": "models", "methode": "GET"},
                        {"chemin": "chat/completions", "methode": "POST", "corps": {"model": "x", "messages": []}}):
            with self.subTest(chemin=demande["chemin"]):
                debut = time.monotonic()
                statut, _, octets = requete(self.refuse, "POST", "/api/ia", demande)
                self.assertEqual((statut, json.loads(octets.decode("utf-8"))), (403, {"erreur": REFUS_EN_LIGNE}))
                self.assertLess(time.monotonic() - debut, 2, "refus immédiat : aucune connexion tentée")
        self.assertEqual(reglages_publics(self.refuse)[0], {"fournisseur": "openai", "url": "http://192.0.2.1",
                                                             "cle_reglee": True, "en_ligne": False, "portee": "distant"})
        console = self.refuse.sortie_console()
        self.assertIn("fournisseurs en ligne refusés", console)
        self.assertNotIn(CLE_SERVEUR, console)

    def test_ia_en_ligne_du_pc_serveur_autorise_l_appel(self):
        # Nom réservé .invalid : jamais résolu, l'appel part et échoue tout de suite (502) au lieu du refus 403.
        with ServeurPrevo(arguments=["--ia-url", "https://exemple.invalid/v1", "--ia-fournisseur", "openai",
                                     "--ia-en-ligne"], environnement={"PREVO_IA_CLE": CLE_SERVEUR}) as autorise:
            self.assertEqual(reglages_publics(autorise)[0], {"fournisseur": "openai", "url": "https://exemple.invalid/v1",
                                                              "cle_reglee": True, "en_ligne": True, "portee": "distant"})
            statut, _, octets = requete(autorise, "POST", "/api/ia", {"chemin": "models", "methode": "GET"}, delai=150)
            self.assertEqual(statut, 502, octets)
            self.assertIn("injoignable", json.loads(octets.decode("utf-8"))["erreur"])
            console = autorise.sortie_console()
            self.assertIn("fournisseurs en ligne autorisés", console)
            self.assertNotIn(CLE_SERVEUR, console + octets.decode("utf-8"))


# ---------------------------------------------------------------------------
# Navigateur en mode serveur (M3, I5) : aucune clé gardée ni envoyée par le poste
# ---------------------------------------------------------------------------

class TestNavigateurAudit(CasNavigateur):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.faux = FauxFournisseur(cle_attendue=CLE_SERVEUR)
        cls.faux.demarrer()
        cls.addClassCleanup(cls.faux.arreter)
        cls.serveur = ServeurPrevo(arguments=["--ia-url", cls.faux.url + "/v1", "--ia-fournisseur", "openai"],
                                   environnement={"PREVO_IA_CLE": CLE_SERVEUR})
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)

    def test_cle_d_un_ancien_reglage_effacee_et_jamais_envoyee_par_le_poste(self):
        # Réglage du poste d'avant T158 : adresse en ligne et clé gardées dans le navigateur
        ancien = {"actif": True, "fournisseur": "openai", "url": "https://api.mistral.ai/v1", "modele": "faux",
                  "cle": CLE_DU_POSTE, "delaiS": 30}
        self.contexte.add_init_script("(() => { try { if (localStorage.getItem('prevo.ia') === null) "
                                      "localStorage.setItem('prevo.ia', %s); } catch (erreur) { /* vide */ } })();"
                                      % json.dumps(json.dumps(ancien)))
        preregler_profil(self.contexte, "responsable", "Responsable")
        envois = []
        page = self.page
        page.on("request", lambda r: envois.append((r.url, r.method, r.post_data or "")))
        page.goto(self.serveur.url + "/")
        attendre_pret(page)
        page.wait_for_function("Ia.etat() !== 'inconnu'")
        self.assertEqual(page.evaluate("Ia.etat()"), "ok")
        memorise = json.loads(page.evaluate("localStorage.getItem('prevo.ia')"))
        self.assertEqual(memorise, {"actif": True, "modele": "faux", "delaiS": 30}, "ni clé, ni adresse, ni fournisseur")
        reglages = page.evaluate("Ia.reglages()")
        self.assertEqual((reglages["fournisseur"], reglages["url"], reglages["cle"]), ("openai", self.faux.url + "/v1", ""))
        self.assertEqual(page.evaluate("Ia.reglagesServeur()"), {"fournisseur": "openai", "url": self.faux.url + "/v1",
                                                               "cleReglee": True, "enLigne": False, "portee": "pc-atelier"})
        texte = page.evaluate("""async () => (await Ia.demander('compteRendu',
            { notes: 'garniture changée', titre: 'Fuite' })).resultat.texte""")
        self.assertIn("Constat", texte)
        relais = [(methode, json.loads(donnees)) for (url, methode, donnees) in envois if url == self.serveur.url + "/api/ia"]
        self.assertGreaterEqual(len(relais), 2, "test d'ouverture et compte rendu, par le relais")
        for methode, corps in relais:
            with self.subTest(chemin=corps.get("chemin")):
                self.assertEqual(methode, "POST")
                self.assertLessEqual(set(corps), {"chemin", "methode", "corps"})
        self.assertFalse([url for (url, _, _) in envois if url.startswith(self.faux.url)], "jamais le fournisseur en direct")
        tout_envoye = json.dumps(envois)
        for cle in (CLE_DU_POSTE, CLE_SERVEUR):
            self.assertNotIn(cle, tout_envoye)
        self.assertEqual({r["entetes"].get("authorization") for r in self.faux.requetes}, {"Bearer " + CLE_SERVEUR})
        # « Ce poste » : l'état de la clé, jamais la clé ni un champ pour la saisir
        page.evaluate("location.hash = '#/poste'")
        page.wait_for_selector("#poste-ia-serveur")
        self.assertIn("réglée sur le serveur", page.inner_text("#poste-ia-serveur"))
        self.assertEqual(page.locator("#carte-ia input[type=password], #poste-ia-url, #poste-ia-cle, "
                                      "#poste-ia-fournisseur").count(), 0)
        stockage = json.dumps(page.evaluate("[Object.entries(localStorage), Object.entries(sessionStorage)]"))
        html = page.content()
        for cle in (CLE_DU_POSTE, CLE_SERVEUR):
            self.assertNotIn(cle, html)
            self.assertNotIn(cle, stockage)


if __name__ == "__main__":
    unittest.main()
