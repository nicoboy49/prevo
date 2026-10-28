"""Lot 7 — Tailscale détecté et guidé (ARCHITECTURE.md §22.8 ; CDC D128 ; CS127 ; tâche T165).

Ce qui est vérifié, avec un faux tailscale (tests/faux_tailscale.py, piloté par des variables d'environnement) :
    détection      detecter_tailscale : présent et connecté (version, nom sans le point final, expiration en heure
                   locale, jours restants, serve status lu), stoppé, absent (exécutable introuvable : rien n'est lancé ;
                   service absent), délai dépassé ; jamais d'exception vers l'appelant ;
    proposition    preparer_tailscale : nom ajouté aux noms acceptés, mandataire, commande serve, « set --unattended »
                   sous Windows seulement, les deux rappels ; sans Tailscale : le lien de téléchargement et rien d'autre ;
    application    appliquer_tailscale : fichier de configuration écrit (noms, mandataire ; clés inconnues et « _aide »
                   gardées), « serve --bg --https=443 http://127.0.0.1:<port> » lancée puis vérifiée par « serve status
                   --json » ; refus sans connexion ; jamais « up », « install » ni « set --unattended » (compte des
                   lancements) ; activer_unattended à part ;
    serveur        /api/info d'un serveur réel (ServeurPrevo, comptes, mandataire, nom en .ts.net, faux tailscale par
                   PREVO_TAILSCALE) : « tailscale » {present, connecte, nom, jours_avant_expiration} seulement (jamais
                   la sortie brute ni l'adresse d'un autre appareil), ligne de console, détection non refaite à chaque
                   requête ; None quand Tailscale n'est pas attendu (aucune commande) ; « non détecté » sans tailscale ;
    accueil        accueil du responsable : bandeau #alerte-tailscale quand Tailscale est déconnecté ou que la clé
                   expire sous 14 jours, rien quand tout va bien ; textes de Accueil.avertissementTailscale.
Aucune commande d'administrateur, aucune sortie réseau, jamais le vrai tailscale (tests/commun.py pose PREVO_TAILSCALE
sur un chemin qui n'existe pas quand le test ne donne pas le faux). Le vrai Tailscale depuis la 4G est à tester en UAT.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_acces_tailscale.py" -v
"""
import datetime
import http.client
import importlib.util
import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from commun import CasNavigateur, RACINE, ServeurPrevo, attendre_pret, url_fichier

FAUX = RACINE / "tests" / "faux_tailscale.py"
NOM = "prevo.tail1234.ts.net"
ADRESSE_AUTRE_APPAREIL = "100.64.0.9"       # un pair du faux tailnet : ne doit jamais sortir par /api/info


def charger_serveur():
    specification = importlib.util.spec_from_file_location("serveur_prevo_tailscale", RACINE / "serveur.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


serveur = charger_serveur()


def dans(jours):
    """KeyExpiry (RFC 3339 UTC) dans « jours » jours et une heure : jours_avant_expiration vaut exactement « jours »."""
    instant = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=jours, hours=1)
    return instant.strftime("%Y-%m-%dT%H:%M:%SZ")


def requete(port, chemin, cookie=None):
    """GET vers un serveur Prévo de 127.0.0.1 : (statut, corps texte)."""
    entetes = {"User-Agent": "tests-prevo/1.0"}
    if cookie:
        entetes["Cookie"] = cookie
    connexion = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    try:
        connexion.request("GET", chemin, headers=entetes)
        reponse = connexion.getresponse()
        return reponse.status, reponse.read().decode("utf-8")
    finally:
        connexion.close()


class CasTailscale(unittest.TestCase):
    """Faux tailscale réglé par l'environnement du processus (les commandes en héritent) ; dossier temporaire."""

    def setUp(self):
        self.dossier = Path(tempfile.mkdtemp(prefix="prevo-tailscale-"))
        self.addCleanup(shutil.rmtree, self.dossier, True)
        self.faux = self.dossier / "faux"
        patch = mock.patch.dict(os.environ, {"FAUX_TAILSCALE_DOSSIER": str(self.faux), "FAUX_TAILSCALE_ETAT": "Running",
                                             "FAUX_TAILSCALE_NOM": NOM + ".", "FAUX_TAILSCALE_EXPIRATION": dans(30)})
        patch.start()
        self.addCleanup(patch.stop)
        for variable in ("PREVO_TAILSCALE", "FAUX_TAILSCALE_ATTENTE"):
            os.environ.pop(variable, None)

    def lancements(self):
        journal = self.faux / "lancements.txt"
        return journal.read_text(encoding="utf-8").splitlines() if journal.is_file() else []

    def configuration(self, reglages=None):
        config = serveur.Configuration(str(self.dossier / "donnees"), [])
        config.reglages["_fichier"] = str(self.dossier / "prevo.config.json")
        config.reglages.update(reglages or {})
        return config


class TestDetection(CasTailscale):

    def test_present_et_connecte(self):
        detection = serveur.detecter_tailscale(str(FAUX))
        self.assertTrue(detection["present"], detection)
        self.assertEqual(detection["version"], "1.80.0")
        self.assertTrue(detection["connecte"])
        self.assertEqual(detection["nom"], NOM)                   # DNSName sans le point final
        self.assertEqual(detection["jours_avant_expiration"], 30)
        self.assertRegex(detection["expiration_cle"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$")
        self.assertEqual(detection["serve"], {})                  # serve status --json sans configuration
        self.assertIsNone(detection["raison"])
        self.assertEqual(self.lancements(), ["version", "status --json", "serve status --json"])

    def test_stoppe(self):
        os.environ["FAUX_TAILSCALE_ETAT"] = "Stopped"
        detection = serveur.detecter_tailscale(str(FAUX))
        self.assertTrue(detection["present"])
        self.assertFalse(detection["connecte"])
        self.assertEqual(detection["nom"], NOM)

    def test_absent(self):
        # Exécutable introuvable (PREVO_TAILSCALE sur un chemin qui n'existe pas) : rien n'est lancé.
        os.environ["PREVO_TAILSCALE"] = str(self.dossier / "nulle-part" / "tailscale.exe")
        self.assertIsNone(serveur.executable_tailscale())
        detection = serveur.detecter_tailscale()
        self.assertEqual(detection, {"present": False, "raison": "Tailscale introuvable sur ce PC"})
        self.assertEqual(self.lancements(), [])
        # PREVO_TAILSCALE donne le faux : c'est lui que la détection lance.
        os.environ["PREVO_TAILSCALE"] = str(FAUX)
        self.assertEqual(serveur.executable_tailscale(), str(FAUX))
        self.assertTrue(serveur.detecter_tailscale()["present"])
        # Service absent : « tailscale version » échoue, la raison est lisible, aucune exception.
        os.environ["FAUX_TAILSCALE_ETAT"] = "absent"
        detection = serveur.detecter_tailscale(str(FAUX))
        self.assertFalse(detection["present"])
        self.assertIn("tailscaled", detection["raison"])
        # Exécutable qui ne se lance pas (un dossier) : pareil.
        detection = serveur.detecter_tailscale(str(self.dossier))
        self.assertFalse(detection["present"])
        self.assertIn("lancé", detection["raison"])

    def test_delai_depasse(self):
        os.environ["FAUX_TAILSCALE_ATTENTE"] = "4"
        debut = time.monotonic()
        detection = serveur.detecter_tailscale(str(FAUX), delai=0.5)
        self.assertLess(time.monotonic() - debut, 3.5)
        self.assertFalse(detection["present"])
        self.assertIn("délai", detection["raison"])

    def test_expiration_de_cle(self):
        os.environ["FAUX_TAILSCALE_EXPIRATION"] = dans(10)
        self.assertEqual(serveur.detecter_tailscale(str(FAUX))["jours_avant_expiration"], 10)
        os.environ["FAUX_TAILSCALE_EXPIRATION"] = dans(-2)
        self.assertEqual(serveur.detecter_tailscale(str(FAUX))["jours_avant_expiration"], -2)
        os.environ["FAUX_TAILSCALE_EXPIRATION"] = ""             # la clé n'expire pas : champ absent
        detection = serveur.detecter_tailscale(str(FAUX))
        self.assertIsNone(detection["jours_avant_expiration"])
        self.assertIsNone(detection["expiration_cle"])
        os.environ["FAUX_TAILSCALE_EXPIRATION"] = "0001-01-01T00:00:00Z"      # date zéro de Go : désactivée
        self.assertIsNone(serveur.detecter_tailscale(str(FAUX))["jours_avant_expiration"])
        self.assertEqual(serveur.expiration_cle_tailscale("n'importe quoi"), (None, None))
        self.assertEqual(serveur.expiration_cle_tailscale(None), (None, None))
        # Heure locale et nanosecondes de Go : une expiration à midi UTC, 1 jour + 1 h après « maintenant ».
        maintenant = datetime.datetime(2026, 6, 1, 11, 0, tzinfo=datetime.timezone.utc).timestamp()
        local, jours = serveur.expiration_cle_tailscale("2026-06-02T12:00:00.123456789Z", maintenant)
        self.assertEqual(jours, 1)
        attendu = datetime.datetime(2026, 6, 2, 12, 0, tzinfo=datetime.timezone.utc).astimezone()
        self.assertEqual(local, attendu.strftime("%Y-%m-%dT%H:%M:%S"))

    def test_resume_console(self):
        self.assertEqual(serveur.resume_tailscale(serveur.detecter_tailscale(str(FAUX))),
                         NOM + ", connecté, clé valable 30 jours")
        self.assertEqual(serveur.resume_tailscale({"present": False, "raison": "Tailscale introuvable sur ce PC"}),
                         "non détecté (Tailscale introuvable sur ce PC)")
        self.assertEqual(serveur.resume_tailscale({"present": True, "nom": NOM, "connecte": False,
                                                   "jours_avant_expiration": None}), NOM + ", déconnecté, clé sans expiration")
        self.assertEqual(serveur.resume_tailscale({"present": True, "nom": NOM, "connecte": True,
                                                   "jours_avant_expiration": -1}), NOM + ", connecté, clé expirée")

    def test_tailscale_attendu(self):
        self.assertFalse(serveur.tailscale_attendu({"mandataire": False, "noms": ["pc-atelier.local"]}))
        self.assertTrue(serveur.tailscale_attendu({"mandataire": True, "noms": []}))
        self.assertTrue(serveur.tailscale_attendu({"mandataire": False, "noms": [NOM]}))


class TestProposition(CasTailscale):

    def test_preparer(self):
        config = self.configuration({"noms": ["pc-atelier.local"], "port_http": 8085})
        detection = serveur.detecter_tailscale(str(FAUX))
        avant = len(self.lancements())
        proposition = serveur.preparer_tailscale(config, detection, systeme="win32")
        self.assertEqual(len(self.lancements()), avant)           # rien n'est lancé
        self.assertTrue(proposition["present"])
        self.assertEqual(proposition["nom"], NOM)
        self.assertEqual(proposition["adresse"], "https://" + NOM + "/")
        self.assertEqual(proposition["noms"], ["pc-atelier.local", NOM])
        self.assertTrue(proposition["ajouter_nom"])
        self.assertTrue(proposition["mandataire"])
        self.assertEqual(proposition["serve"], "tailscale serve --bg --https=443 http://127.0.0.1:8085")
        self.assertEqual(proposition["arguments_serve"], ["serve", "--bg", "--https=443", "http://127.0.0.1:8085"])
        self.assertEqual(proposition["unattended"], "tailscale set --unattended=true")
        self.assertEqual(len(proposition["rappels"]), 2)
        self.assertIn("expiration de clé", proposition["rappels"][0])
        self.assertIn("veille", proposition["rappels"][1])
        self.assertIsNone(serveur.preparer_tailscale(config, detection, systeme="linux")["unattended"])
        self.assertEqual(config.reglages["noms"], ["pc-atelier.local"])     # la configuration n'a pas bougé
        # Nom déjà accepté : rien à ajouter.
        config = self.configuration({"noms": [NOM]})
        proposition = serveur.preparer_tailscale(config, detection)
        self.assertFalse(proposition["ajouter_nom"])
        self.assertEqual(proposition["noms"], [NOM])

    def test_sans_tailscale_le_lien_et_rien_d_autre(self):
        config = self.configuration()
        proposition = serveur.preparer_tailscale(config, {"present": False, "raison": "Tailscale introuvable sur ce PC"})
        self.assertEqual(proposition, {"present": False, "raison": "Tailscale introuvable sur ce PC",
                                       "telechargement": "https://tailscale.com/download"})
        self.assertEqual(serveur.preparer_tailscale(config, None)["telechargement"], "https://tailscale.com/download")
        self.assertEqual(self.lancements(), [])


class TestApplication(CasTailscale):

    def test_appliquer_ecrit_la_configuration_et_verifie_serve(self):
        fichier = self.dossier / "prevo.config.json"
        fichier.write_text(json.dumps({"_aide": "mon aide", "comptes": True, "noms": ["pc-atelier.local"],
                                       "inconnue": 42}), encoding="utf-8")
        config = self.configuration({"noms": ["pc-atelier.local"], "port_http": 8080})
        resultat = serveur.appliquer_tailscale(config, str(FAUX))
        self.assertTrue(resultat["ok"], resultat["message"])
        self.assertEqual(resultat["nom"], NOM)
        self.assertEqual(resultat["adresse"], "https://" + NOM + "/")
        self.assertIn("https://" + NOM + "/", resultat["message"])
        self.assertEqual(resultat["serve"]["Web"][NOM + ":443"]["Handlers"]["/"]["Proxy"], "http://127.0.0.1:8080")
        # Le fichier : noms et mandataire changés, le reste gardé tel quel.
        contenu = json.loads(fichier.read_text(encoding="utf-8"))
        self.assertEqual(contenu["noms"], ["pc-atelier.local", NOM])
        self.assertTrue(contenu["mandataire"])
        self.assertEqual(contenu["_aide"], "mon aide")
        self.assertEqual(contenu["inconnue"], 42)
        self.assertTrue(contenu["comptes"])
        relu = serveur.lire_configuration(str(fichier))
        self.assertEqual((relu["noms"], relu["mandataire"], relu["_inconnues"]), (["pc-atelier.local", NOM], True, ["inconnue"]))
        # serve écrite puis vérifiée par serve status ; jamais up, install ni set.
        lancements = self.lancements()
        self.assertIn("serve --bg --https=443 http://127.0.0.1:8080", lancements)
        # serve status --json est aussi lancée par la détection : c'est la dernière qui vérifie.
        self.assertGreater(len(lancements) - 1 - lancements[::-1].index("serve status --json"),
                           lancements.index("serve --bg --https=443 http://127.0.0.1:8080"))
        self.assertEqual([l for l in lancements if l.split()[0] in ("up", "down", "login", "logout", "install", "set")], [])
        self.assertEqual(json.loads((self.faux / "serve.json").read_text(encoding="utf-8"))["Web"][NOM + ":443"]
                         ["Handlers"]["/"]["Proxy"], "http://127.0.0.1:8080")
        # En mémoire : les réglages ne bougent pas (le prochain démarrage les lit) ; la détection est gardée.
        self.assertFalse(config.reglages["mandataire"])
        self.assertEqual(config.reglages["noms"], ["pc-atelier.local"])
        self.assertEqual(config.tailscale["serve"], resultat["serve"])
        self.assertEqual(serveur.etat_tailscale_public(config),
                         {"present": True, "connecte": True, "nom": NOM, "jours_avant_expiration": 30})

    def test_fichier_absent_cree_avec_l_aide(self):
        config = self.configuration({"port_http": 8090})
        resultat = serveur.appliquer_tailscale(config, str(FAUX))
        self.assertTrue(resultat["ok"], resultat["message"])
        contenu = json.loads((self.dossier / "prevo.config.json").read_text(encoding="utf-8"))
        self.assertEqual(list(contenu), ["_aide", "noms", "mandataire"])
        self.assertEqual(contenu["_aide"], serveur.AIDE_CONFIGURATION)
        self.assertEqual(contenu["noms"], [NOM])
        self.assertIn("serve --bg --https=443 http://127.0.0.1:8090", self.lancements())

    def test_refus_sans_connexion_ni_tailscale(self):
        config = self.configuration()
        os.environ["FAUX_TAILSCALE_ETAT"] = "Stopped"
        resultat = serveur.appliquer_tailscale(config, str(FAUX))
        self.assertFalse(resultat["ok"])
        self.assertIn("pas connecté", resultat["message"])
        os.environ["FAUX_TAILSCALE_ETAT"] = "absent"
        resultat = serveur.appliquer_tailscale(config, str(FAUX))
        self.assertFalse(resultat["ok"])
        self.assertIn("non détecté", resultat["message"])
        self.assertFalse((self.dossier / "prevo.config.json").exists())      # rien d'écrit
        self.assertEqual([l for l in self.lancements() if l.startswith("serve --bg")], [])

    def test_serve_status_sans_la_cible(self):
        self.assertIsNone(serveur.cible_serve_tailscale({}, 8080))
        self.assertIsNone(serveur.cible_serve_tailscale(None, 8080))
        serve = {"TCP": {"443": {"HTTPS": True}}, "Web": {NOM + ":443": {"Handlers": {"/": {"Proxy": "http://127.0.0.1:8080"}}}}}
        self.assertEqual(serveur.cible_serve_tailscale(serve, 8080), NOM + ":443")
        self.assertIsNone(serveur.cible_serve_tailscale(serve, 8081))
        serve["Web"][NOM + ":443"]["Handlers"]["/"]["Proxy"] = "http://localhost:8080/"
        self.assertEqual(serveur.cible_serve_tailscale(serve, 8080), NOM + ":443")

    def test_unattended_seulement_sur_demande_et_commandes_interdites(self):
        config = self.configuration()
        self.assertTrue(serveur.appliquer_tailscale(config, str(FAUX))["ok"])
        self.assertNotIn("set --unattended=true", self.lancements())
        self.assertEqual(serveur.activer_unattended(str(FAUX))["ok"], True)
        self.assertEqual(self.lancements().count("set --unattended=true"), 1)
        os.environ["PREVO_TAILSCALE"] = str(self.dossier / "nulle-part.exe")
        self.assertFalse(serveur.activer_unattended()["ok"])
        avant = self.lancements()
        for commande in ("up", "install", "login", "down"):
            with self.subTest(commande=commande), self.assertRaises(serveur.ErreurTailscale):
                serveur.lancer_tailscale(str(FAUX), [commande, "--accept-routes"])
        self.assertEqual(self.lancements(), avant)                # refusées avant tout lancement


class TestServeurReel(unittest.TestCase):
    """serveur.py lancé par ServeurPrevo ; le faux tailscale lui est donné par PREVO_TAILSCALE."""

    def setUp(self):
        self.dossier = Path(tempfile.mkdtemp(prefix="prevo-tailscale-reel-"))
        self.addCleanup(shutil.rmtree, self.dossier, True)
        self.faux = self.dossier / "faux"

    def environnement(self, etat="Running", expiration=None):
        return {"PREVO_TAILSCALE": str(FAUX), "FAUX_TAILSCALE_DOSSIER": str(self.faux), "FAUX_TAILSCALE_ETAT": etat,
                "FAUX_TAILSCALE_NOM": NOM + ".", "FAUX_TAILSCALE_EXPIRATION": dans(20) if expiration is None else expiration}

    def lancements(self):
        journal = self.faux / "lancements.txt"
        return journal.read_text(encoding="utf-8").splitlines() if journal.is_file() else []

    def test_api_info_et_console(self):
        with ServeurPrevo(comptes=True, reglages={"mandataire": True, "noms": [NOM]},
                          environnement=self.environnement()) as reel:
            cookie = reel.session("responsable")
            statut, corps = requete(reel.port, "/api/info", cookie)
            self.assertEqual(statut, 200, corps)
            self.assertEqual(json.loads(corps)["tailscale"],
                             {"present": True, "connecte": True, "nom": NOM, "jours_avant_expiration": 20})
            for interdit in (ADRESSE_AUTRE_APPAREIL, "1.80.0", "Peer", "100.64.0.7"):
                self.assertNotIn(interdit, corps)                 # jamais la sortie brute de status
            self.assertIn("Tailscale        : %s, connecté, clé valable 20 jours" % NOM, reel.sortie_console())
            self.assertEqual(self.lancements(), ["version", "status --json", "serve status --json"])
            requete(reel.port, "/api/info", cookie)
            self.assertEqual(len(self.lancements()), 3)           # pas une commande à chaque requête

    def test_api_info_sans_tailscale_attendu(self):
        with ServeurPrevo(comptes=True, environnement=self.environnement()) as reel:
            statut, corps = requete(reel.port, "/api/info", reel.session("responsable"))
            self.assertEqual(statut, 200, corps)
            self.assertIsNone(json.loads(corps)["tailscale"])
            self.assertNotIn("Tailscale", reel.sortie_console())
        self.assertEqual(self.lancements(), [])                   # aucune commande lancée

    def test_api_info_non_detecte(self):
        with ServeurPrevo(comptes=True, reglages={"mandataire": True, "noms": [NOM]}) as reel:   # aucun tailscale
            statut, corps = requete(reel.port, "/api/info", reel.session("responsable"))
            self.assertEqual(statut, 200, corps)
            self.assertEqual(json.loads(corps)["tailscale"],
                             {"present": False, "connecte": False, "nom": None, "jours_avant_expiration": None})
            self.assertIn("Tailscale        : non détecté", reel.sortie_console())


class TestAccueil(CasNavigateur):
    """Accueil du responsable sur un serveur réel en mode comptes, Tailscale simulé par le faux."""

    def setUp(self):
        super().setUp()
        self.dossier = Path(tempfile.mkdtemp(prefix="prevo-tailscale-accueil-"))
        self.addCleanup(shutil.rmtree, self.dossier, True)

    def serveur(self, etat, expiration):
        return ServeurPrevo(comptes=True, reglages={"mandataire": True, "noms": [NOM]}, environnement={
            "PREVO_TAILSCALE": str(FAUX), "FAUX_TAILSCALE_DOSSIER": str(self.dossier / "faux"),
            "FAUX_TAILSCALE_ETAT": etat, "FAUX_TAILSCALE_NOM": NOM + ".", "FAUX_TAILSCALE_EXPIRATION": expiration})

    def ouvrir(self, reel):
        reel.poser_session(self.contexte, "responsable")
        self.page.goto(reel.url + "/#/accueil")
        attendre_pret(self.page)
        self.page.wait_for_selector("#tailscale-zone[data-lu='1']", state="attached")
        return self.page

    def test_bandeau_quand_tailscale_est_deconnecte(self):
        with self.serveur("Stopped", dans(30)) as reel:
            page = self.ouvrir(reel)
            texte = " ".join(page.inner_text("#alerte-tailscale").split())
            self.assertIn("Tailscale est déconnecté : les téléphones hors de l'atelier ne joignent plus Prévo.", texte)
            self.assertIn("attention", page.get_attribute("#alerte-tailscale", "class"))
            self.assertEqual(page.locator("#alerte-copie-externe").count(), 0)
            page.goto("about:blank")

    def test_bandeau_quand_la_cle_expire(self):
        with self.serveur("Running", dans(5)) as reel:
            page = self.ouvrir(reel)
            texte = " ".join(page.inner_text("#alerte-tailscale").split())
            self.assertIn("La clé Tailscale expire dans 5 jours : désactivez l'expiration de clé dans la console "
                          "Tailscale (Machines › " + NOM + " › Disable key expiry)", texte)
            page.goto("about:blank")

    def test_rien_quand_tout_va_bien(self):
        with self.serveur("Running", dans(30)) as reel:
            page = self.ouvrir(reel)
            self.assertEqual(page.locator("#alerte-tailscale").count(), 0)
            self.assertEqual(page.evaluate("App.adaptateur.info().then((info) => info.tailscale)"),
                             {"present": True, "connecte": True, "nom": NOM, "joursAvantExpiration": 30})
            page.goto("about:blank")

    def test_texte_de_l_avertissement(self):
        self.page.goto(url_fichier("index.html"))
        self.page.wait_for_function("typeof Accueil !== 'undefined' && typeof Accueil.avertissementTailscale === 'function'")
        cas = [None,
               {"present": False, "connecte": False, "nom": None, "joursAvantExpiration": None},
               {"present": True, "connecte": False, "nom": NOM, "joursAvantExpiration": 30},
               {"present": True, "connecte": True, "nom": NOM, "joursAvantExpiration": 15},
               {"present": True, "connecte": True, "nom": NOM, "joursAvantExpiration": 14},
               {"present": True, "connecte": True, "nom": NOM, "joursAvantExpiration": 1},
               {"present": True, "connecte": True, "nom": NOM, "joursAvantExpiration": 0},
               {"present": True, "connecte": True, "nom": NOM, "joursAvantExpiration": -3},
               {"present": True, "connecte": True, "nom": None, "joursAvantExpiration": None}]
        textes = self.page.evaluate("""(cas) => cas.map((tailscale) => {
            const fragment = Accueil.avertissementTailscale(tailscale);
            return fragment ? UI.element(UI.html`<div>${fragment}</div>`).textContent.replace(/\\s+/g, ' ').trim() : '';
        })""", cas)
        deconnecte = ("Tailscale est déconnecté : les téléphones hors de l'atelier ne joignent plus Prévo. "
                      "Ouvrez Tailscale sur ce PC et connectez-vous.")
        suite = (" : désactivez l'expiration de clé dans la console Tailscale (Machines › " + NOM
                 + " › Disable key expiry), sinon les téléphones hors de l'atelier ne joignent plus Prévo.")
        self.assertEqual(textes, ["", "", deconnecte, "",
                                  "La clé Tailscale expire dans 14 jours" + suite,
                                  "La clé Tailscale expire dans 1 jour" + suite,
                                  "La clé Tailscale expire aujourd'hui" + suite,
                                  "La clé Tailscale a expiré" + suite,
                                  ""])


if __name__ == "__main__":
    unittest.main()
