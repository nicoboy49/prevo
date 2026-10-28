"""Lot 7 — API de l'assistant d'installation (ARCHITECTURE.md §22.10 ; D131, D132 ; CS130 ; tâche T167).

Ce qui est vérifié, sans navigateur :
    parcours      Solo « ce PC », Solo « hors de l'atelier » avec Tailscale (faux), Atelier « Wi-Fi » avec certificat
                  automatique (faux mkcert), Intranet derrière un mandataire avec des noms : chaque parcours jusqu'à
                  « terminer », puis prevo.config.json relu et comparé CLÉ À CLÉ à la configuration attendue, écrite
                  ici d'après l'étude §6.1 (jamais déduite du code) ; comptes.json avec le responsable (et le technicien
                  « moi » dans techniciens.csv en Solo) ; parametres.csv (mode_solo, cloture_une_etape,
                  solo_technicien_id) ; élévation et relance notées, jamais lancées ; brouillon supprimé ;
    refus         mot de passe trop court 400, deuxième responsable 409, prénom manquant 400 ; dossier de sauvegardes
                  inexistant ou dans les données 400 ; ports hors bornes, portée ou situation inconnue 400 ; X-Prevo
                  manquant 403 ; certificat automatique sans mkcert 503 et brouillon inchangé ; fichiers PEM illisibles
                  400 ; mandataire sans nom 400 ; « terminer » sans responsable, sans https ou sans brouillon 400 ;
                  rien dans le brouillon ni dans les réponses qui ressemble à un mot de passe ou à une empreinte ;
    deplacer      copie d'un dossier de Prévo simulé vers un dossier temporaire (sans .git ni __pycache__), chaque
                  fichier égal, relance notée vers la nouvelle place, ancien dossier intact ; cible non vide, cible
                  dans la source, chemin relatif, hors Windows : 400 ;
    brouillon     relu par une seconde instance du serveur sur le même dossier (rien n'est perdu avant « terminer ») ;
    réseau        serveur du processus sur 0.0.0.0, client par l'adresse réseau du PC : 404 « Adresse inconnue »
                  pour chaque route de l'assistant alors que /api/ping répond ; client mandaté
                  (tests/mandataire_test.py) : 404 même avec la session du responsable ; avec comptes et configuration,
                  en direct : 401 sans session, 403 technicien, 200 responsable ;
    serveur réel  serveur.py lancé sans configuration (premier lancement) : /api/info rend installation_a_faire,
                  l'état dit la configuration absente et les CSV présents, « situation » s'écrit sans session ; avec
                  une configuration : installation_a_faire faux ; adresse ouverte au démarrage (#/installation) ;
    élévation     la ligne de commande de l'élévation (Start-Process -Verb RunAs) est construite, jamais lancée.
Aucune commande d'administrateur (config.lancer_eleve remplacée), aucune relance réelle (config.relancer remplacée),
aucune sortie réseau, jamais le vrai mkcert ni le vrai tailscale (PREVO_MKCERT et PREVO_TAILSCALE posés ici).

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_installation_api.py" -v
"""
import csv
import hashlib
import http.client
import importlib.util
import io
import json
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit

import commun
from commun import RACINE
from mandataire_test import MandataireTest
from test_https import fabriquer_certificat, trouver_openssl

SCRIPT = RACINE / "serveur.py"
FAUX_MKCERT = RACINE / "tests" / "faux_mkcert.py"
FAUX_TAILSCALE = RACINE / "tests" / "faux_tailscale.py"
NOM_TAILSCALE = "prevo.tail1234.ts.net"
NOM_INTRANET = "gmao.entreprise.lan"
MOT_DE_PASSE = "phrase de passe du responsable"
MOT_DE_PASSE_TECHNICIEN = "cle a molette et graisse"
MESSAGE_INCONNUE = "Adresse inconnue dans l'API."
AGENT = "Navigateur-de-test/1.0"
COMPTES_JSON = b""


def charger_serveur():
    specification = importlib.util.spec_from_file_location("serveur_prevo_installation", SCRIPT)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


serveur = charger_serveur()


def setUpModule():
    """Deux comptes créés une fois (scrypt coûte) pour les tests « comptes exigés » : nicolas.briand (responsable) et
    julien.moreau (technicien lié à TEC-0001)."""
    global COMPTES_JSON
    dossier = Path(tempfile.mkdtemp(prefix="prevo-installation-modele-"))
    try:
        config = serveur.Configuration(str(dossier / "donnees"), [])
        serveur.creer_dossiers(config)
        serveur.creer_compte(config, "Nicolas", "Briand", "responsable", MOT_DE_PASSE)
        serveur.creer_compte(config, "Julien", "Moreau", "technicien", MOT_DE_PASSE_TECHNICIEN, technicien_id="TEC-0001")
        COMPTES_JSON = (dossier / "donnees" / "acces" / "comptes.json").read_bytes()
    finally:
        shutil.rmtree(dossier, ignore_errors=True)


# ---------------------------------------------------------------------------
# Configurations attendues, écrites en dur d'après l'étude §6.1 (jamais déduites de serveur.py)
# ---------------------------------------------------------------------------

DEFAUTS_COMMUNS = {
    "port_http": 8080, "port_https": 8443, "certificat": "", "cle": "", "session_heures": 12,
    "session_longue_jours": 30, "invitation_heures": 24, "quota_documents_mo": 2048, "ia_fournisseur": "ollama",
    "ia_url": "http://localhost:11434", "ia_cle": "", "ia_en_ligne": False,
}
ATTENDU_SOLO_CE_PC = dict(DEFAUTS_COMMUNS, portee="ce-pc", ecoute="127.0.0.1", noms=[], certificat_auto=False,
                          mandataire=False, comptes=False, demandeurs_avec_compte=False, demarrage="aucun",
                          veille_desactivee=False, copie_sauvegardes="")
ATTENDU_SOLO_DEHORS = dict(DEFAUTS_COMMUNS, portee="dehors", ecoute="127.0.0.1", noms=[NOM_TAILSCALE],
                           certificat_auto=False, mandataire=True, comptes=True, demandeurs_avec_compte=False,
                           demarrage="systeme", veille_desactivee=True)               # copie_sauvegardes : le dossier du test
ATTENDU_ATELIER = dict(DEFAUTS_COMMUNS, portee="atelier", ecoute="0.0.0.0", noms=[], certificat_auto=True,
                       mandataire=False, comptes=True, demandeurs_avec_compte=False, demarrage="systeme",
                       veille_desactivee=True)                                         # copie_sauvegardes : le dossier du test
ATTENDU_INTRANET = dict(DEFAUTS_COMMUNS, portee="atelier", ecoute="127.0.0.1", noms=[NOM_INTRANET],
                        certificat_auto=False, mandataire=True, comptes=True, demandeurs_avec_compte=True,
                        demarrage="systeme", veille_desactivee=False, copie_sauvegardes="")
CLES_ATTENDUES = sorted(ATTENDU_SOLO_CE_PC)


# ---------------------------------------------------------------------------
# Outils : client HTTP, serveur du processus, enregistreur d'élévation et de relance
# ---------------------------------------------------------------------------

class Reponse:
    def __init__(self, statut, entetes, octets):
        self.statut, self.entetes, self.octets = statut, entetes, octets

    def json(self):
        return json.loads(self.octets.decode("utf-8"))


class Client:
    """Requêtes vers un serveur Prévo, une connexion par requête ; X-Prevo posé sur les écritures sauf demande."""

    def __init__(self, url):
        morceaux = urlsplit(url)
        self.hote, self.port = morceaux.hostname, morceaux.port

    def requete(self, methode, chemin, corps=None, cookie=None, prevo=True, entetes=None):
        entetes = dict(entetes or {})
        entetes.setdefault("User-Agent", AGENT)
        if cookie:
            entetes["Cookie"] = cookie
        if methode in ("PUT", "POST") and prevo:
            entetes.setdefault("X-Prevo", "1")
        if isinstance(corps, (dict, list)):
            corps = json.dumps(corps).encode("utf-8")
        if methode in ("PUT", "POST") and corps is None:
            corps = b""
        connexion = http.client.HTTPConnection(self.hote, self.port, timeout=180)
        try:
            connexion.request(methode, chemin, body=corps, headers=entetes)
            reponse = connexion.getresponse()
            return Reponse(reponse.status, {nom.lower(): valeur for nom, valeur in reponse.getheaders()}, reponse.read())
        finally:
            connexion.close()

    def get(self, etape, cookie=None):
        return self.requete("GET", "/api/installation/" + etape, cookie=cookie)

    def post(self, etape, corps=None, cookie=None, prevo=True):
        return self.requete("POST", "/api/installation/" + etape, corps if corps is not None else {}, cookie, prevo)

    def connecter(self, identifiant, mot_de_passe):
        reponse = self.requete("POST", "/api/connexion", {"identifiant": identifiant, "mot_de_passe": mot_de_passe,
                                                          "rester": False})
        if reponse.statut != 200:
            raise AssertionError("connexion de %s refusée : %r" % (identifiant, reponse.octets))
        return reponse.entetes["set-cookie"].split(";")[0]


class Enregistreur:
    """Remplace config.lancer_eleve et config.relancer : note les appels, ne lance rien."""

    def __init__(self, ok=True):
        self.eleves, self.relances, self.ok = [], [], ok

    def lancer_eleve(self, script, eleve=True):
        self.eleves.append((script, eleve))
        return {"ok": self.ok, "code": 0 if self.ok else 1, "message": "simulé"}

    def relancer(self, dossier=None):
        self.relances.append(dossier)
        return True


class ServeurDuProcessus:
    """serveur.ServeurPrevo du processus (une Configuration injectable) dans un fil, sur un port libre."""

    def __init__(self, config, hote="127.0.0.1"):
        self.config = config
        self.http = serveur.ServeurPrevo((hote, 0), config)
        self.port = self.http.server_address[1]
        self.config.port = self.port
        self.url = "http://127.0.0.1:%d" % self.port
        self.fil = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.fil.start()

    def arreter(self):
        self.http.shutdown()
        self.http.server_close()
        self.fil.join(timeout=5)


def configuration(dossier, reglages=None, systeme="win32"):
    """Configuration comme au premier lancement : dossier des données dans « dossier », fichier de configuration
    absent (ou lu s'il existe), dossier de Prévo = « dossier » (les scripts et la copie y vont), système simulé."""
    lus = serveur.lire_configuration(str(Path(dossier) / "prevo.config.json"))
    lus.update(reglages or {})
    config = serveur.Configuration(str(Path(dossier) / "donnees"), lus["noms"])       # comme main : noms acceptés
    config.reglages = lus
    config.ecoute = config.reglages["ecoute"]
    config.dossier_application = str(dossier)
    config.systeme = systeme
    serveur.creer_dossiers(config)
    return config


def lire_csv(chemin):
    lignes = [l for l in csv.reader(io.StringIO(Path(chemin).read_text(encoding="utf-8-sig"), newline=""), delimiter=";") if l]
    return lignes[0], lignes[1:]


def parametres_de(dossier_donnees):
    entete, lignes = lire_csv(Path(dossier_donnees) / "parametres.csv")
    return {ligne[entete.index("cle")]: ligne[entete.index("valeur")] for ligne in lignes}


def sha256(chemin):
    return hashlib.sha256(Path(chemin).read_bytes()).hexdigest()


class CasAssistant(unittest.TestCase):
    """Un dossier temporaire par test ; faux binaires absents par défaut (PREVO_MKCERT et PREVO_TAILSCALE sur des
    chemins qui n'existent pas : jamais les vrais) ; console silencieuse."""

    def setUp(self):
        self.dossier = Path(tempfile.mkdtemp(prefix="prevo-installation-"))
        self.addCleanup(shutil.rmtree, self.dossier, True)
        self.faux = self.dossier / "faux-tailscale"
        patch = mock.patch.dict(os.environ, {
            "PREVO_MKCERT": str(self.dossier / "nulle-part" / "mkcert.exe"),
            "PREVO_TAILSCALE": str(self.dossier / "nulle-part" / "tailscale.exe"),
            "FAUX_TAILSCALE_DOSSIER": str(self.faux), "FAUX_TAILSCALE_ETAT": "Running",
            "FAUX_TAILSCALE_NOM": NOM_TAILSCALE + ".", "FAUX_TAILSCALE_EXPIRATION": ""})
        patch.start()
        self.addCleanup(patch.stop)
        silence = mock.patch.object(serveur, "afficher")
        silence.start()
        self.addCleanup(silence.stop)
        self.serveurs = []

    def tearDown(self):
        for instance in self.serveurs:
            instance.arreter()
        super().tearDown()

    def lancer(self, dossier=None, reglages=None, hote="127.0.0.1", systeme="win32", source=None):
        """Serveur du processus sur « dossier » (copie de « source » dans donnees/ si donné) ; rend (client, serveur)."""
        dossier = Path(dossier or self.dossier)
        if source is not None and not (dossier / "donnees").exists():
            shutil.copytree(source, dossier / "donnees")
        config = configuration(dossier, reglages, systeme)
        self.enregistreur = Enregistreur()
        config.lancer_eleve = self.enregistreur.lancer_eleve
        config.relancer = self.enregistreur.relancer
        instance = ServeurDuProcessus(config, hote)
        self.serveurs.append(instance)
        return Client(instance.url), instance

    def faux_mkcert(self):
        if not trouver_openssl():
            self.skipTest("openssl introuvable : faux mkcert impossible")
        os.environ["PREVO_MKCERT"] = str(FAUX_MKCERT)

    def faux_tailscale(self):
        os.environ["PREVO_TAILSCALE"] = str(FAUX_TAILSCALE)

    def ok(self, reponse, statut=200):
        self.assertEqual(reponse.statut, statut, reponse.octets[:400])
        return reponse.json()

    def configuration_ecrite(self, instance):
        chemin = Path(instance.config.reglages["_fichier"])
        self.assertTrue(chemin.is_file(), "prevo.config.json n'a pas été écrit à côté de serveur.py")
        return json.loads(chemin.read_text(encoding="utf-8"))

    def comparer_cle_a_cle(self, ecrit, attendu):
        self.assertEqual(sorted(cle for cle in ecrit if not cle.startswith("_")), CLES_ATTENDUES)
        self.assertIn("_aide", ecrit)
        for cle in CLES_ATTENDUES:
            with self.subTest(cle=cle):
                self.assertEqual(ecrit[cle], attendu[cle])
        # Le fichier relu par le serveur tient les règles de portée (démarrage possible, §22.1).
        relu = serveur.lire_configuration(str(self.dossier / "prevo.config.json"))
        relu["_https_auto"] = bool(relu["certificat_auto"]) and not relu["certificat"]
        serveur.verifier_regles_portee(relu, True)
        self.assertEqual(relu["_inconnues"], [])


# ---------------------------------------------------------------------------
# Les parcours complets (CS130)
# ---------------------------------------------------------------------------

class TestParcours(CasAssistant):

    def test_solo_ce_pc(self):
        client, instance = self.lancer()                     # dossier de données vide : premier lancement
        etat = self.ok(client.get("etat"))
        self.assertFalse(etat["configuration_presente"])
        self.assertFalse(etat["csv_presents"])
        self.assertIsNone(etat["situation"])
        self.assertEqual(set(etat["etapes"].values()), {"a_faire"})
        reponse = self.ok(client.post("situation", {"situation": "seul"}))
        self.assertEqual(reponse["brouillon"]["situation"], "seul")
        self.assertTrue(reponse["brouillon"]["mode_solo"])
        self.assertEqual(reponse["etapes"]["situation"], "fait")
        self.assertEqual(reponse["etapes"]["compte"], "a_faire")            # Solo : le technicien « moi »
        reponse = self.ok(client.post("portee", {"portee": "ce-pc"}))
        self.assertEqual(reponse["etapes"]["certificat"], "sans_objet")
        self.assertEqual(reponse["etapes"]["tailscale"], "sans_objet")
        self.assertEqual(reponse["etapes"]["compte"], "a_faire")
        self.assertFalse(reponse["brouillon"]["comptes"])
        # Sur ce PC en Solo : le nom seul crée le technicien, aucun compte ni mot de passe.
        reponse = self.ok(client.post("compte", {"prenom": "Nicolas", "nom": "Briand"}))
        self.assertIsNone(reponse["compte"])
        self.assertEqual(reponse["technicien_id"], "TEC-0001")
        self.assertFalse(Path(instance.config.dossier_donnees, "acces", "comptes.json").exists())
        reponse = self.ok(client.post("demarrage", {"demarrage": "aucun", "veille_desactivee": False}))
        self.assertIsNone(reponse["lance"])
        self.assertEqual(self.enregistreur.eleves, [])
        self.assertTrue(Path(reponse["scripts"]["Installer_demarrage.ps1"]).is_file())    # écrit, jamais exécuté
        self.ok(client.post("sauvegardes", {"dossier": ""}))
        fin = self.ok(client.post("terminer"))
        self.assertTrue(fin["relance"])
        self.assertEqual(self.enregistreur.relances, [None])
        self.comparer_cle_a_cle(self.configuration_ecrite(instance), ATTENDU_SOLO_CE_PC)
        parametres = parametres_de(instance.config.dossier_donnees)
        self.assertEqual((parametres["mode_solo"], parametres["cloture_une_etape"], parametres["solo_technicien_id"],
                          parametres["version_schema"]), ("1", "1", "TEC-0001", "3"))
        entete, lignes = lire_csv(Path(instance.config.dossier_donnees) / "techniciens.csv")
        self.assertEqual(entete, list(serveur.COLONNES_PAR_TABLE["techniciens"]))
        self.assertEqual(lignes, [["TEC-0001", "Briand", "Nicolas", "", "", "", "1"]])
        self.assertFalse(Path(instance.config.dossier_donnees, "installation.json").exists())
        self.assertIsNone(self.ok(client.get("etat"))["brouillon"])

    def test_solo_hors_de_l_atelier_avec_tailscale(self):
        self.faux_tailscale()
        copie = self.dossier / "copie-externe"
        copie.mkdir()
        client, instance = self.lancer(source=commun.DOSSIER_DEMO)      # migration : la démo tient lieu de base 1.2
        self.assertTrue(self.ok(client.get("etat"))["csv_presents"])
        self.ok(client.post("situation", {"situation": "seul"}))
        reponse = self.ok(client.post("portee", {"portee": "dehors"}))
        self.assertEqual((reponse["etapes"]["compte"], reponse["etapes"]["certificat"], reponse["etapes"]["tailscale"]),
                         ("a_faire", "a_faire", "a_faire"))
        self.assertTrue(reponse["brouillon"]["comptes"])
        reponse = self.ok(client.post("compte", {"prenom": "Nicolas", "nom": "Briand", "mot_de_passe": MOT_DE_PASSE}))
        compte = reponse["compte"]
        self.assertEqual((compte["identifiant"], compte["role"], compte["technicien_id"]),
                         ("nicolas.briand", "responsable", "TEC-0005"))            # la démo a TEC-0001 à TEC-0004
        self.assertFalse({"empreinte", "sel", "algo", "mot_de_passe"} & set(compte))
        comptes = json.loads(Path(instance.config.dossier_donnees, "acces", "comptes.json").read_text(encoding="utf-8"))
        self.assertEqual([(c["identifiant"], c["role"], c["technicien_id"]) for c in comptes["comptes"]],
                         [("nicolas.briand", "responsable", "TEC-0005")])
        self.assertNotIn(MOT_DE_PASSE, Path(instance.config.dossier_donnees, "acces", "comptes.json").read_text("utf-8"))
        entete, lignes = lire_csv(Path(instance.config.dossier_donnees) / "techniciens.csv")
        self.assertEqual(lignes[-1][:3] + lignes[-1][-1:], ["TEC-0005", "Briand", "Nicolas", "1"])
        self.assertEqual(len(lignes), 5)
        self.assertEqual(self.ok(client.get("etat"))["etapes"]["compte"], "fait")
        reponse = self.ok(client.post("certificat", {"mode": "reseau_prive"}))
        self.assertTrue(reponse["brouillon"]["mandataire"])
        self.assertFalse(reponse["brouillon"]["certificat_auto"])
        self.assertEqual(reponse["brouillon"]["ecoute"], "127.0.0.1")       # Tailscale porte seul le https
        detection = self.ok(client.post("tailscale", {"action": "detecter"}))
        self.assertEqual((detection["detection"]["present"], detection["detection"]["nom"]), (True, NOM_TAILSCALE))
        self.assertEqual(detection["proposition"]["noms"], [NOM_TAILSCALE])
        self.assertNotIn("100.64.0.9", json.dumps(detection))                 # jamais un autre appareil du tailnet
        reponse = self.ok(client.post("tailscale", {"action": "appliquer"}))
        self.assertTrue(reponse["ok"])
        self.assertEqual(reponse["brouillon"]["noms"], [NOM_TAILSCALE])
        self.assertEqual(reponse["etapes"]["tailscale"], "fait")
        self.assertEqual(reponse["adresse"], "https://" + NOM_TAILSCALE + "/")
        lancements = (self.faux / "lancements.txt").read_text(encoding="utf-8").splitlines()
        self.assertIn("serve --bg --https=443 http://127.0.0.1:8080", lancements)
        self.assertEqual([l for l in lancements if l.split()[0] in ("up", "down", "login", "install", "set")], [])
        self.assertFalse(Path(instance.config.reglages["_fichier"]).exists())   # rien d'écrit avant « terminer »
        reponse = self.ok(client.post("demarrage", {"demarrage": "systeme", "veille_desactivee": True}))
        self.assertEqual(self.enregistreur.eleves, [(str(self.dossier / "Installer_demarrage.ps1"), True)])
        self.assertEqual((reponse["lance"]["ok"], reponse["etapes"]["demarrage"]), (True, "fait"))
        self.assertIn("powercfg.exe /change standby-timeout-ac 0",
                      Path(reponse["scripts"]["Installer_demarrage.ps1"]).read_text(encoding="utf-8-sig"))
        self.ok(client.post("sauvegardes", {"dossier": str(copie)}))
        brouillon = Path(instance.config.dossier_donnees, "installation.json").read_text(encoding="utf-8")
        self.assertNotIn(MOT_DE_PASSE, brouillon)
        self.assertNotIn("empreinte", brouillon)
        fin = self.ok(client.post("terminer"))
        self.assertEqual(self.enregistreur.relances, [None])
        self.comparer_cle_a_cle(self.configuration_ecrite(instance), dict(ATTENDU_SOLO_DEHORS, copie_sauvegardes=str(copie)))
        self.assertEqual(fin["configuration"]["noms"], [NOM_TAILSCALE])
        parametres = parametres_de(instance.config.dossier_donnees)
        self.assertEqual((parametres["mode_solo"], parametres["cloture_une_etape"], parametres["solo_technicien_id"]),
                         ("1", "1", "TEC-0005"))
        self.assertEqual(parametres["entreprise_nom"], "Atelier des Trois Vallées (démo)")     # le reste gardé
        self.assertTrue(any(p.is_dir() for p in Path(instance.config.dossier_sauvegardes).iterdir()))  # sauvegarde du jour

    def test_atelier_wifi_certificat_automatique(self):
        self.faux_mkcert()
        copie = self.dossier / "nas"
        copie.mkdir()
        client, instance = self.lancer(source=commun.DOSSIER_DEMO)
        reponse = self.ok(client.post("situation", {"situation": "equipe"}))
        self.assertEqual((reponse["brouillon"]["portee"], reponse["brouillon"]["certificat_auto"],
                          reponse["brouillon"]["demarrage"], reponse["brouillon"]["veille_desactivee"]),
                         ("atelier", True, "systeme", True))
        reponse = self.ok(client.post("portee", {"portee": "atelier"}))
        self.assertEqual(reponse["etapes"]["tailscale"], "sans_objet")
        self.ok(client.post("compte", {"prenom": "Nicolas", "nom": "Briand", "mot_de_passe": MOT_DE_PASSE}))
        comptes = json.loads(Path(instance.config.dossier_donnees, "acces", "comptes.json").read_text(encoding="utf-8"))
        self.assertEqual(comptes["comptes"][0]["technicien_id"], "")                   # pas de technicien « moi »
        self.assertEqual(len(lire_csv(Path(instance.config.dossier_donnees) / "techniciens.csv")[1]), 4)
        reponse = self.ok(client.post("certificat", {"mode": "automatique"}))
        self.assertTrue(reponse["autorite_presente"])
        self.assertIn("127.0.0.1", reponse["noms_certificat"])
        self.assertIn("localhost", reponse["noms_certificat"])
        acces = Path(instance.config.dossier_donnees) / "acces"
        self.assertTrue((acces / "certificat.pem").is_file() and (acces / "cle.pem").is_file())
        self.assertTrue((acces / "autorite" / "rootCA.pem").is_file())
        self.assertEqual(reponse["brouillon"]["ecoute"], "0.0.0.0")
        reponse = self.ok(client.post("demarrage", {"demarrage": "systeme", "veille_desactivee": True}))
        self.assertEqual(self.enregistreur.eleves, [(reponse["scripts"]["Installer_demarrage.ps1"], True)])
        script = Path(reponse["scripts"]["Installer_demarrage.ps1"]).read_text(encoding="utf-8-sig")
        self.assertIn("-install", script)                                               # autorité mkcert
        self.assertIn("localport=8080,8443", script)
        self.ok(client.post("sauvegardes", {"dossier": str(copie)}))
        self.ok(client.post("terminer"))
        self.comparer_cle_a_cle(self.configuration_ecrite(instance), dict(ATTENDU_ATELIER, copie_sauvegardes=str(copie)))
        self.assertNotIn("mode_solo", parametres_de(instance.config.dossier_donnees))
        fiche = self.ok(client.get("fiche"))
        self.assertTrue(fiche["autorite_presente"])
        self.assertTrue(fiche["comptes"])
        self.assertEqual(fiche["responsables"], ["nicolas.briand"])
        self.assertEqual(fiche["lanceur"], "Lancer_GMAO.bat")
        self.assertEqual(fiche["reinitialisation"]["script"], "Reinitialiser_mot_de_passe.bat")
        self.assertEqual(fiche["dossier_donnees"], instance.config.dossier_donnees)
        self.assertEqual(fiche["copie_sauvegardes"], str(copie))

    def test_intranet_mandataire_avec_noms(self):
        client, instance = self.lancer(source=commun.DOSSIER_DEMO)
        reponse = self.ok(client.post("situation", {"situation": "informaticien"}))
        self.assertTrue(reponse["brouillon"]["demandeurs_avec_compte"])
        self.assertFalse(reponse["brouillon"]["mode_solo"])
        reponse = self.ok(client.post("portee", {"portee": "atelier", "noms": [NOM_INTRANET.upper()],
                                                  "port_http": 8080, "port_https": 8443}))
        self.assertEqual(reponse["brouillon"]["noms"], [NOM_INTRANET])                 # minuscules, comme le fichier
        self.ok(client.post("compte", {"prenom": "Nicolas", "nom": "Briand", "mot_de_passe": MOT_DE_PASSE}))
        reponse = self.ok(client.post("certificat", {"mode": "mandataire"}))
        self.assertEqual((reponse["brouillon"]["mandataire"], reponse["brouillon"]["ecoute"]), (True, "127.0.0.1"))
        self.assertFalse(reponse["autorite_presente"])
        reponse = self.ok(client.post("demarrage", {"demarrage": "systeme", "veille_desactivee": False}))
        self.assertNotIn("powercfg", Path(reponse["scripts"]["Installer_demarrage.ps1"]).read_text(encoding="utf-8-sig"))
        self.ok(client.post("sauvegardes", {"dossier": ""}))
        self.ok(client.post("terminer"))
        self.comparer_cle_a_cle(self.configuration_ecrite(instance), ATTENDU_INTRANET)
        fiche = self.ok(client.get("fiche"))
        self.assertEqual(fiche["adresses_mandataire"], ["https://" + NOM_INTRANET + "/"])
        self.assertEqual(fiche["adresses"], [])                                          # rien n'écoute sur le réseau
        self.assertIsNone(fiche["adresse_tailscale"])

    def test_configuration_existante_modifiee_sans_perdre_les_cles_inconnues(self):
        """Paramètres › Accès et installation (T170) : l'assistant rejoué sur une configuration présente la modifie
        (modifier_configuration) ; clé inconnue, _aide et ia_cle gardés."""
        fichier = self.dossier / "prevo.config.json"
        fichier.write_text(json.dumps({"_aide": "mon aide", "comptes": False, "ia_cle": "secret", "inconnue": 42}),
                           encoding="utf-8")
        client, instance = self.lancer(source=commun.DOSSIER_DEMO)
        self.assertTrue(self.ok(client.get("etat"))["configuration_presente"])
        self.ok(client.post("situation", {"situation": "seul"}))
        self.ok(client.post("portee", {"portee": "ce-pc"}))
        self.ok(client.post("terminer"))
        ecrit = json.loads(fichier.read_text(encoding="utf-8"))
        self.assertEqual((ecrit["_aide"], ecrit["ia_cle"], ecrit["inconnue"]), ("mon aide", "secret", 42))
        self.assertEqual(ecrit["portee"], "ce-pc")
        self.assertNotIn("ia_cle", self.ok(client.get("etat")).get("brouillon") or {})


# ---------------------------------------------------------------------------
# Refus et bornes
# ---------------------------------------------------------------------------

class TestRefus(CasAssistant):

    def test_sans_brouillon_situation_et_portee(self):
        client, _ = self.lancer()
        self.assertEqual(client.post("portee", {"portee": "ce-pc"}).statut, 400)
        self.assertEqual(client.post("terminer").statut, 400)
        self.assertEqual(client.post("situation", {"situation": "patron"}).statut, 400)
        self.assertEqual(client.post("situation", {"situation": "seul"}, prevo=False).statut, 403)   # X-Prevo
        self.assertEqual(client.requete("POST", "/api/installation/situation", b"pas du json").statut, 400)
        self.ok(client.post("situation", {"situation": "equipe"}))
        self.assertEqual(client.post("portee", {"portee": "partout"}).statut, 400)
        reponse = client.post("portee", {"portee": "atelier", "port_http": 70000})
        self.assertEqual(reponse.statut, 400)
        self.assertIn("port_http", reponse.json()["erreur"])
        self.assertEqual(client.post("portee", {"portee": "atelier", "port_https": "8443"}).statut, 400)
        self.assertEqual(client.post("portee", {"portee": "atelier", "port_http": 9000, "port_https": 9000}).statut, 400)
        self.assertEqual(client.post("portee", {"portee": "atelier", "noms": "pas-une-liste"}).statut, 400)
        self.assertEqual(client.get("inconnue").statut, 404)
        self.assertEqual(client.post("inconnue").statut, 404)
        self.assertEqual(self.ok(client.get("etat"))["brouillon"]["port_http"], 8080)     # rien de refusé n'est gardé

    def test_compte_refuse(self):
        client, instance = self.lancer(source=commun.DOSSIER_DEMO)
        self.ok(client.post("situation", {"situation": "equipe"}))
        self.ok(client.post("portee", {"portee": "atelier"}))
        reponse = client.post("compte", {"prenom": "Nicolas", "nom": "Briand", "mot_de_passe": "court"})
        self.assertEqual(reponse.statut, 400)
        self.assertIn("12 caractères", reponse.json()["erreur"])
        self.assertFalse(Path(instance.config.dossier_donnees, "acces", "comptes.json").exists())
        self.assertEqual(client.post("compte", {"prenom": "", "nom": "Briand", "mot_de_passe": MOT_DE_PASSE}).statut, 400)
        self.assertEqual(client.post("compte", {"prenom": "Nicolas", "mot_de_passe": "x" * 257}).statut, 400)
        self.ok(client.post("compte", {"prenom": "Nicolas", "nom": "Briand", "mot_de_passe": MOT_DE_PASSE}))
        reponse = client.post("compte", {"prenom": "Paul", "nom": "Essai", "mot_de_passe": MOT_DE_PASSE})
        self.assertEqual(reponse.statut, 409)
        self.assertIn("nicolas.briand", reponse.json()["erreur"])
        comptes = json.loads(Path(instance.config.dossier_donnees, "acces", "comptes.json").read_text(encoding="utf-8"))
        self.assertEqual(len(comptes["comptes"]), 1)
        # Sur « ce PC » hors Solo : aucun compte n'a d'objet.
        self.ok(client.post("portee", {"portee": "ce-pc"}))
        self.assertEqual(client.post("compte", {"prenom": "Paul", "nom": "Essai", "mot_de_passe": MOT_DE_PASSE}).statut, 400)

    def test_sauvegardes_refusees(self):
        client, instance = self.lancer()
        self.ok(client.post("situation", {"situation": "seul"}))
        donnees = Path(instance.config.dossier_donnees)
        for dossier, attendu in ((str(self.dossier / "absent"), "introuvable"), (str(donnees), "données"),
                                 (str(donnees / "sauvegardes"), "données"), (42, "chemin")):
            with self.subTest(dossier=dossier):
                reponse = client.post("sauvegardes", {"dossier": dossier})
                self.assertEqual(reponse.statut, 400, reponse.octets)
                self.assertIn(attendu, reponse.json()["erreur"])
        self.assertEqual(self.ok(client.get("etat"))["etapes"]["sauvegardes"], "a_faire")
        bon = self.dossier / "cle-usb"
        bon.mkdir()
        reponse = self.ok(client.post("sauvegardes", {"dossier": str(bon)}))
        self.assertEqual(reponse["brouillon"]["copie_sauvegardes"], str(bon))
        self.assertEqual(sorted(bon.iterdir()), [])                                       # le témoin a été retiré

    def test_certificat_refuse(self):
        client, instance = self.lancer(source=commun.DOSSIER_DEMO)
        self.ok(client.post("situation", {"situation": "equipe"}))
        self.ok(client.post("portee", {"portee": "ce-pc"}))
        self.assertEqual(client.post("certificat", {"mode": "automatique"}).statut, 400)    # sur ce PC : pas de https
        self.ok(client.post("portee", {"portee": "atelier"}))
        avant = Path(instance.config.dossier_donnees, "installation.json").read_bytes()
        reponse = client.post("certificat", {"mode": "automatique"})                        # mkcert absent : 503
        self.assertEqual(reponse.statut, 503, reponse.octets)
        self.assertIn("mkcert", reponse.json()["erreur"])
        self.assertEqual(Path(instance.config.dossier_donnees, "installation.json").read_bytes(), avant)
        self.assertFalse(Path(instance.config.dossier_donnees, "acces", "certificat.pem").exists())
        self.assertEqual(client.post("certificat", {"mode": "magique"}).statut, 400)
        self.assertEqual(client.post("certificat", {"mode": "fichiers"}).statut, 400)
        mauvais = self.dossier / "faux.pem"
        mauvais.write_text("pas un certificat", encoding="ascii")
        reponse = client.post("certificat", {"mode": "fichiers", "certificat": str(mauvais), "cle": str(mauvais)})
        self.assertEqual(reponse.statut, 400)
        self.assertIn("illisible", reponse.json()["erreur"])
        self.assertEqual(client.post("certificat", {"mode": "mandataire"}).statut, 400)      # noms obligatoires
        self.assertEqual(self.ok(client.get("etat"))["etapes"]["certificat"], "a_faire")
        if trouver_openssl():
            certificat, cle = fabriquer_certificat(self.dossier)
            reponse = self.ok(client.post("certificat", {"mode": "fichiers", "certificat": str(certificat), "cle": str(cle)}))
            self.assertEqual((reponse["brouillon"]["certificat"], reponse["brouillon"]["cle"]), (str(certificat), str(cle)))
            self.assertFalse(reponse["brouillon"]["certificat_auto"])
            self.assertEqual(reponse["brouillon"]["ecoute"], "0.0.0.0")

    def test_tailscale_refuse_et_plus_tard(self):
        client, instance = self.lancer()
        self.ok(client.post("situation", {"situation": "seul"}))
        self.ok(client.post("portee", {"portee": "dehors"}))
        self.assertEqual(client.post("tailscale", {"action": "installer"}).statut, 400)
        detection = self.ok(client.post("tailscale", {"action": "detecter"}))           # absent : rien de lancé
        self.assertFalse(detection["detection"]["present"])
        self.assertEqual(detection["proposition"]["telechargement"], "https://tailscale.com/download")
        reponse = client.post("tailscale", {"action": "appliquer"})
        self.assertEqual(reponse.statut, 503)
        self.assertIn("Tailscale", reponse.json()["erreur"])
        self.assertEqual(client.post("tailscale", {"action": "unattended"}).statut, 503)
        reponse = self.ok(client.post("tailscale", {"action": "plus_tard"}))
        self.assertEqual(reponse["etapes"]["tailscale"], "a_faire")
        self.assertFalse(reponse["brouillon"]["mandataire"])
        self.faux_tailscale()
        os.environ["FAUX_TAILSCALE_ETAT"] = "Stopped"
        reponse = client.post("tailscale", {"action": "appliquer"})
        self.assertEqual(reponse.statut, 503)
        self.assertIn("connecté", reponse.json()["erreur"])
        self.assertFalse((self.faux / "serve.json").exists())
        self.assertEqual(self.ok(client.get("etat"))["tailscale"]["present"], True)

    def test_terminer_refuse_quand_les_regles_ne_tiennent_pas(self):
        client, instance = self.lancer(source=commun.DOSSIER_DEMO)
        self.ok(client.post("situation", {"situation": "equipe"}))
        self.ok(client.post("portee", {"portee": "atelier"}))
        reponse = client.post("terminer")                                                 # comptes sans responsable
        self.assertEqual(reponse.statut, 400)
        self.assertIn("responsable", reponse.json()["erreur"])
        self.ok(client.post("compte", {"prenom": "Nicolas", "nom": "Briand", "mot_de_passe": MOT_DE_PASSE}))
        reponse = client.post("terminer")                                                 # réseau sans mkcert
        self.assertEqual(reponse.statut, 400)
        self.assertIn("mkcert", reponse.json()["erreur"])
        self.ok(client.post("situation", {"situation": "seul"}))
        self.ok(client.post("portee", {"portee": "dehors"}))                               # Solo dehors sans https
        reponse = client.post("terminer")
        self.assertEqual(reponse.statut, 400)
        self.assertIn("https", reponse.json()["erreur"])
        self.assertFalse(Path(instance.config.reglages["_fichier"]).exists())
        self.assertEqual(self.enregistreur.relances, [])
        self.assertTrue(Path(instance.config.dossier_donnees, "installation.json").exists())

    def test_demarrage_hors_windows_rend_les_commandes(self):
        client, instance = self.lancer(systeme="linux")
        self.ok(client.post("situation", {"situation": "equipe"}))
        self.assertEqual(self.ok(client.get("etat"))["etapes"]["deplacer"], "sans_objet")
        self.assertEqual(client.post("demarrage", {"demarrage": "systeme", "veille_desactivee": "oui"}).statut, 400)
        reponse = self.ok(client.post("demarrage", {"demarrage": "systeme", "veille_desactivee": False}))
        self.assertIsNone(reponse["lance"])
        self.assertEqual(self.enregistreur.eleves, [])
        self.assertIn("sudo systemctl enable --now prevo", reponse["commandes"])
        self.assertTrue(Path(reponse["scripts"]["prevo.service"]).is_file())
        self.assertEqual(reponse["etapes"]["demarrage"], "fait")
        reponse = client.post("deplacer", {"vers": str(self.dossier / "ailleurs")})
        self.assertEqual(reponse.statut, 400)
        self.assertEqual(self.ok(client.get("etat"))["systeme"], "linux")

    def test_elevation_refusee_laisse_l_etape_a_faire(self):
        client, instance = self.lancer()
        self.enregistreur.ok = False
        self.ok(client.post("situation", {"situation": "equipe"}))
        reponse = self.ok(client.post("demarrage", {"demarrage": "systeme", "veille_desactivee": True}))
        self.assertEqual((reponse["lance"]["ok"], reponse["etapes"]["demarrage"]), (False, "a_faire"))
        reponse = self.ok(client.post("demarrage", {"demarrage": "session", "veille_desactivee": False}))
        self.assertEqual(self.enregistreur.eleves[-1], (str(self.dossier / "Demarrage_session.ps1"), False))


# ---------------------------------------------------------------------------
# Déplacer Prévo, brouillon durable, élévation
# ---------------------------------------------------------------------------

class TestDeplacerEtBrouillon(CasAssistant):

    def test_deplacer_copie_verifie_et_relance(self):
        source = self.dossier / "Prevo-zip"
        for relatif, contenu in (("serveur.py", b"# serveur\r\n"), ("Lancer_GMAO.bat", b"@echo off\r\n"),
                                 ("js/app.js", b"'use strict';\n"), ("outils-tiers/mkcert.exe", bytes(range(256)) * 10),
                                 (".git/HEAD", b"ref: refs/heads/main\n"), ("js/__pycache__/x.pyc", b"\x00")):
            chemin = source / relatif
            chemin.parent.mkdir(parents=True, exist_ok=True)
            chemin.write_bytes(contenu)
        client, instance = self.lancer(source)
        self.ok(client.post("situation", {"situation": "seul"}))
        self.assertFalse(self.ok(client.get("etat"))["dans_dossier_conseille"])
        self.assertEqual(self.ok(client.get("etat"))["dossier_conseille"], "C:\\Prevo")
        cible = self.dossier / "cible" / "Prevo"
        for vers, attendu in ((str(source), "déjà"), (str(source / "sous"), "ni dans"), (str(self.dossier), "ni dans"),
                              ("Prevo", "complet")):
            with self.subTest(vers=vers):
                reponse = client.post("deplacer", {"vers": vers})
                self.assertEqual(reponse.statut, 400, reponse.octets)
                self.assertIn(attendu, reponse.json()["erreur"])
        occupee = self.dossier / "occupee"
        occupee.mkdir()
        (occupee / "fichier.txt").write_text("x", encoding="ascii")
        self.assertEqual(client.post("deplacer", {"vers": str(occupee)}).statut, 400)
        self.assertEqual(self.enregistreur.relances, [])
        avant = {str(p.relative_to(source)): sha256(p) for p in source.rglob("*") if p.is_file()}
        reponse = self.ok(client.post("deplacer", {"vers": str(cible)}))
        self.assertEqual(reponse["vers"], str(cible))
        self.assertTrue(reponse["relance"])
        self.assertEqual(self.enregistreur.relances, [str(cible)])
        copies = {str(p.relative_to(cible)): sha256(p) for p in cible.rglob("*") if p.is_file()}
        apres = {str(p.relative_to(source)): sha256(p) for p in source.rglob("*") if p.is_file()}
        attendus = {chemin: empreinte for chemin, empreinte in apres.items()
                    if not chemin.startswith(".git") and "__pycache__" not in chemin}
        self.assertEqual(copies, attendus)                                     # données et brouillon compris
        self.assertEqual(reponse["copie"], len(attendus))
        self.assertIn(os.path.join("donnees", "installation.json"), copies)
        self.assertFalse((cible / ".git").exists())
        # L'ancien dossier est intact : seul le brouillon y a été réécrit (étape « deplacer » notée avant la copie).
        brouillon_source = os.path.join("donnees", "installation.json")
        self.assertEqual({c: e for c, e in apres.items() if c != brouillon_source},
                         {c: e for c, e in avant.items() if c != brouillon_source})
        brouillon = json.loads((cible / "donnees" / "installation.json").read_text(encoding="utf-8"))
        self.assertEqual(brouillon["etapes"]["deplacer"], "fait")

    def test_brouillon_relu_apres_un_redemarrage(self):
        client, premier = self.lancer(source=commun.DOSSIER_DEMO)
        self.ok(client.post("situation", {"situation": "equipe"}))
        self.ok(client.post("portee", {"portee": "dehors", "port_http": 8090, "noms": ["pc-atelier.lan"]}))
        self.ok(client.post("compte", {"prenom": "Nicolas", "nom": "Briand", "mot_de_passe": MOT_DE_PASSE}))
        premier.arreter()
        self.serveurs.remove(premier)
        client, second = self.lancer()                                         # même dossier, nouvelle instance
        etat = self.ok(client.get("etat"))
        self.assertEqual((etat["situation"], etat["portee"], etat["brouillon"]["port_http"], etat["brouillon"]["noms"]),
                         ("equipe", "dehors", 8090, ["pc-atelier.lan"]))
        self.assertEqual((etat["etapes"]["situation"], etat["etapes"]["portee"], etat["etapes"]["compte"],
                          etat["etapes"]["tailscale"]), ("fait", "fait", "fait", "a_faire"))
        self.assertTrue(etat["responsable_existe"])
        fiche = self.ok(client.get("fiche"))
        self.assertIn("http://pc-atelier.lan:8090/", fiche["adresses"])
        self.assertTrue(all(a.startswith("http://") and a.endswith(":8090/") for a in fiche["adresses"]))
        # Un brouillon abîmé vaut « aucun » : l'assistant repart de la situation sans erreur 500.
        Path(second.config.dossier_donnees, "installation.json").write_text("{pas du json", encoding="utf-8")
        self.assertIsNone(self.ok(client.get("etat"))["brouillon"])
        self.assertEqual(client.post("portee", {"portee": "ce-pc"}).statut, 400)

    def test_commande_d_elevation_et_adresse_de_demarrage(self):
        script = r"C:\Prevo\Installer_demarrage.ps1"
        commande = serveur.commande_powershell(script, True)
        self.assertEqual(commande[:4], ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass"])
        self.assertIn("Start-Process -FilePath powershell.exe", commande[-1])
        self.assertIn("-Verb RunAs -Wait -PassThru", commande[-1])
        self.assertIn("'-File','%s'" % script, commande[-1])
        self.assertIn("exit $p.ExitCode", commande[-1])
        self.assertEqual(serveur.commande_powershell(script, False)[-2:], ["-File", script])
        config = configuration(self.dossier)
        config.port = 8080
        self.assertEqual(serveur.adresse_de_demarrage(config), "http://localhost:8080/#/installation")
        config.reglages["_present"] = True
        self.assertEqual(serveur.adresse_de_demarrage(config), "http://localhost:8080/")


# ---------------------------------------------------------------------------
# Vu du réseau ou d'un mandataire : l'assistant n'existe pas ; avec comptes : rôles
# ---------------------------------------------------------------------------

ROUTES_DE_L_ASSISTANT = [("GET", "etat"), ("GET", "fiche")] + [("POST", etape) for etape in (
    "situation", "portee", "compte", "certificat", "tailscale", "demarrage", "sauvegardes", "deplacer", "terminer")]


class TestVuDuReseau(CasAssistant):

    def test_client_non_loopback_404_pour_chaque_route(self):
        adresses = [a for a in serveur.adresses_ip_reseau() if not a.startswith("127.")]
        if not adresses:
            self.skipTest("ce PC n'a pas d'adresse réseau")
        client, instance = self.lancer(hote="0.0.0.0")
        reseau = Client("http://%s:%d" % (adresses[0], instance.port))
        self.assertEqual(reseau.requete("GET", "/api/ping").statut, 200)
        for methode, etape in ROUTES_DE_L_ASSISTANT:
            with self.subTest(route="%s %s" % (methode, etape)):
                reponse = reseau.get(etape) if methode == "GET" else reseau.post(etape, {"situation": "seul"})
                self.assertEqual((reponse.statut, reponse.json()), (404, {"erreur": MESSAGE_INCONNUE}))
        self.assertEqual(reseau.requete("GET", "/api/installation").statut, 404)
        self.assertEqual(reseau.requete("POST", "/api/installation/situation", b"{}", prevo=False).statut, 404)
        self.assertEqual(reseau.requete("GET", "/api/inexistante").json(), {"erreur": MESSAGE_INCONNUE})  # identique
        self.assertFalse(Path(instance.config.dossier_donnees, "installation.json").exists())
        self.assertEqual(client.get("etat").statut, 200)                                   # le PC lui-même, oui

    def test_mandate_404_et_roles_en_direct(self):
        (self.dossier / "donnees" / "acces").mkdir(parents=True)
        (self.dossier / "donnees" / "acces" / "comptes.json").write_bytes(COMPTES_JSON)
        (self.dossier / "prevo.config.json").write_text(json.dumps({"comptes": True, "mandataire": True,
                                                                     "noms": ["prevo.exemple"]}), encoding="utf-8")
        client, instance = self.lancer()
        responsable = client.connecter("nicolas.briand", MOT_DE_PASSE)
        technicien = client.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN)
        with MandataireTest(instance.url, hote="prevo.exemple", protocole="https", client="100.64.0.7") as mandataire:
            relais = Client(mandataire.url)
            self.assertEqual(relais.requete("GET", "/api/info", cookie=responsable).statut, 200)   # mandat attesté
            for methode, etape in ROUTES_DE_L_ASSISTANT:
                with self.subTest(route="%s %s" % (methode, etape)):
                    reponse = (relais.get(etape, cookie=responsable) if methode == "GET"
                               else relais.post(etape, {"situation": "seul"}, cookie=responsable))
                    self.assertEqual((reponse.statut, reponse.json()), (404, {"erreur": MESSAGE_INCONNUE}))
        self.assertEqual(client.get("etat").statut, 401)                                  # sans session
        self.assertEqual(client.post("situation", {"situation": "seul"}).statut, 401)
        refus = client.get("etat", cookie=technicien)
        self.assertEqual(refus.statut, 403)
        self.assertTrue(refus.json()["erreur"].startswith("Accès refusé"))
        self.assertEqual(client.post("situation", {"situation": "seul"}, cookie=technicien).statut, 403)
        etat = self.ok(client.get("etat", cookie=responsable))
        self.assertTrue(etat["configuration_presente"])
        self.assertTrue(etat["responsable_existe"])
        self.assertEqual(self.ok(client.post("situation", {"situation": "equipe"}, cookie=responsable))["etapes"]["compte"], "fait")

    def test_table_des_roles_et_des_routes(self):
        for route in (("GET", "installation/<etape>"), ("POST", "installation/<etape>")):
            self.assertIn(route, serveur.ROUTES_API)
            self.assertEqual(serveur.ROLES_PAR_ROUTE[route], serveur.RESPONSABLE)
            self.assertNotIn(route, serveur.ROUTES_PUBLIQUES)


# ---------------------------------------------------------------------------
# Serveur réel : premier lancement sans configuration
# ---------------------------------------------------------------------------

class TestServeurReel(unittest.TestCase):

    def test_premier_lancement_sans_configuration(self):
        with commun.ServeurPrevo() as reel:                      # copie de la démo, aucune configuration, aucun compte
            client = Client(reel.url)
            info = client.requete("GET", "/api/info").json()
            self.assertTrue(info["installation_a_faire"])
            etat = client.get("etat").json()
            self.assertEqual((etat["configuration_presente"], etat["csv_presents"], etat["responsable_existe"],
                              etat["situation"], etat["tailscale"]["present"]), (False, True, False, None, False))
            self.assertEqual(etat["version"], serveur.VERSION_APPLICATION)
            self.assertIn(etat["systeme"], ("windows", "linux", "macos"))
            reponse = client.post("situation", {"situation": "seul"})
            self.assertEqual(reponse.statut, 200, reponse.octets)
            self.assertTrue((reel.dossier / "installation.json").is_file())
            self.assertEqual(client.get("etat").json()["situation"], "seul")
            self.assertIn("#/installation", reel.sortie_console())
        with commun.ServeurPrevo(comptes=True) as reel:
            client = Client(reel.url)
            session = reel.session("responsable")
            self.assertFalse(client.requete("GET", "/api/info", cookie=session).json()["installation_a_faire"])
            self.assertEqual(client.get("etat").statut, 401)
            self.assertEqual(client.get("etat", cookie=session).statut, 200)
            self.assertNotIn("#/installation", reel.sortie_console())

    def test_comptes_exiges_sans_responsable_l_assistant_reste_joignable_sur_ce_pc(self):
        """Configuration écrite à la main avec « comptes », sans aucun compte : personne ne peut se connecter ;
        depuis ce PC, l'assistant reste joignable jusqu'à la création du premier responsable (§22.10)."""
        dossier = Path(tempfile.mkdtemp(prefix="prevo-sans-responsable-"))
        self.addCleanup(shutil.rmtree, dossier, True)
        configuration = dossier / "prevo.config.json"
        configuration.write_text(json.dumps({"comptes": True}), encoding="utf-8")
        with commun.ServeurPrevo(arguments=["--config", str(configuration)]) as reel:
            client = Client(reel.url)
            self.assertEqual(client.requete("GET", "/api/session").json(),
                             {"comptes": True, "session": None, "installation_inachevee": True})
            self.assertEqual(client.requete("GET", "/api/csv/equipements").statut, 401)    # le reste est fermé
            self.assertEqual(client.get("etat").statut, 200)
            console = reel.sortie_console()
            self.assertIn("aucun compte responsable", console)
            self.assertIn("#/installation", console)
            self.assertNotIn("Sur le réseau", console)              # Prévo n'écoute que sur ce PC
            self.assertEqual(client.post("situation", {"situation": "equipe"}).statut, 200)
            self.assertEqual(client.post("portee", {"portee": "atelier"}).statut, 200)
            reponse = client.post("compte", {"prenom": "Nicolas", "nom": "Briand", "mot_de_passe": MOT_DE_PASSE})
            self.assertEqual(reponse.statut, 200, reponse.octets)
            # Le premier responsable existe : l'assistant redevient réservé à sa session.
            self.assertEqual(client.get("etat").statut, 401)
            self.assertEqual(client.requete("GET", "/api/session").json(), {"comptes": True, "session": None})
            cookie = client.connecter("nicolas.briand", MOT_DE_PASSE)
            self.assertEqual(client.get("etat", cookie=cookie).statut, 200)
            # comptes.json abîmé : on ne SAIT pas qu'aucun responsable existe : rien ne s'ouvre sans session (un
            # compte créé par l'assistant écraserait tous les comptes).
            (reel.dossier / "acces" / "comptes.json").write_bytes(b"{ pas du json")
            self.assertEqual(client.requete("GET", "/api/session").json(), {"comptes": True, "session": None})
            self.assertEqual(client.get("etat").statut, 401)
            self.assertEqual(client.post("compte", {"prenom": "Paul", "nom": "Essai",
                                                     "mot_de_passe": MOT_DE_PASSE}).statut, 401)
            self.assertEqual((reel.dossier / "acces" / "comptes.json").read_bytes(), b"{ pas du json")


@unittest.skipUnless(os.name == "nt", "chemins Windows")
class TestDossierConseille(unittest.TestCase):

    def test_c_prevo_et_un_dossier_juste_dessous(self):
        """Le zip dézippé dans C:\\Prevo donne C:\\Prevo\\prevo-<version> : déjà au bon endroit, rien à proposer."""
        from types import SimpleNamespace

        def conseille(dossier, systeme="win32"):
            return serveur.dans_dossier_conseille(SimpleNamespace(systeme=systeme, dossier_application=dossier))

        self.assertTrue(conseille("C:\\Prevo"))
        self.assertTrue(conseille("c:\\prevo\\prevo-2.0.0"))
        self.assertFalse(conseille("C:\\Prevo\\a\\b"))
        self.assertFalse(conseille("C:\\Users\\essai\\Downloads\\prevo-2.0.0"))
        self.assertFalse(conseille("C:\\Prevo2\\prevo-2.0.0"))
        self.assertFalse(conseille("C:\\Prevo", systeme="linux"))


if __name__ == "__main__":
    unittest.main()
