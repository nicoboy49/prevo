"""Lot 7 — connexion et sessions (ARCHITECTURE.md §22.3, §22.4 ; D124, D126 ; CS121 ; tâche T151).

Ce qui est vérifié :
    porte          avec « comptes », chaque route de ROUTES_API (table lue dans serveur.py, jamais recopiée ici) rend
                   401 sans session ou avec un jeton inconnu, une adresse /api/ inconnue aussi ; les routes publiques
                   (ping, session, connexion) et les fichiers de l'application restent ouverts ; sans session, aucun
                   corps n'est lu (64 Ko au plus jetés, au-delà la connexion est fermée) ; sans « comptes », rien ne
                   change et connexion, déconnexion, mot de passe sont refusés proprement (400) ;
    cookie         id=<jeton>; Path=/; HttpOnly; SameSite=Lax, Max-Age de 30 jours avec « rester », Secure en https ;
                   jeton neuf à chaque connexion ; sessions.json ne garde que l'empreinte SHA-256 du jeton ;
    parcours       connexion, /api/session rempli, déconnexion (cookie effacé), puis 401 ;
    neutralité     identifiant inconnu, compte désactivé et mot de passe faux : même code, même message, mêmes
                   en-têtes, une empreinte calculée à chaque fois, mêmes attentes, même blocage ;
    échecs         attentes de 1, 2, 4, 8, 8 s dès le 5e échec (horloge et attente simulées), blocage de 15 min au 10e
                   (429, temps restant, Retry-After, aucun mot de passe vérifié), réussite qui remet à zéro, tentatives
                   simultanées jamais plus de 10, 1 s de plus par tentative au-delà de 20 échecs dans l'heure pour une
                   adresse, compteurs remis à zéro au redémarrage ;
    durées         12 h glissantes (vu_le réécrit au plus une fois par minute), 30 jours avec « rester », sessions
                   expirées purgées ;
    provisoire     un mot de passe à changer n'ouvre que /api/session, /api/mot-de-passe et /api/deconnexion (403) ;
    mot de passe   changement : session neuve, les autres fermées ; 400 trop court ou identique ; 403 actuel faux ;
                   compte désactivé ou réinitialisé : ses sessions fermées ;
    partout        « déconnecter partout » : ses propres sessions, ou celles d'un autre compte par le responsable seul ;
    journal        connexion, echec, bloque, deconnexion écrits avec l'adresse et l'agent, la colonne Tailscale
                   seulement derrière un mandataire sur ce PC ; jamais un mot de passe ni un jeton (journal, console,
                   réponses, fichiers d'accès).

Deux façons de lancer le serveur : dans ce processus (serveur.py importé, Configuration dont l'horloge et l'attente
sont simulées) pour ce qui dépend du temps ; serveur réel (ServeurPrevo de tests/commun.py, --config à « comptes »,
écoute sur 127.0.0.1, comptes.json préparé dans la copie des données) pour le reste, en http et en https (certificat
de test fabriqué comme dans tests/test_https.py). Aucune sortie réseau, aucune commande d'administrateur.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_acces_sessions.py" -v
"""
import csv
import hashlib
import http.client
import importlib.util
import json
import shutil
import socket
import ssl
import tempfile
import threading
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit

import commun
from commun import RACINE
from test_https import fabriquer_certificat

SCRIPT = RACINE / "serveur.py"


def charger_serveur():
    specification = importlib.util.spec_from_file_location("serveur_prevo_sessions", SCRIPT)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


serveur = charger_serveur()

MOT_DE_PASSE_RESPONSABLE = "phrase du responsable 2026"
MOT_DE_PASSE_TECHNICIEN = "cle a molette et graisse"
MOT_DE_PASSE_PROVISOIRE = "provisoire-a-changer-7"
NOUVEAU_MOT_DE_PASSE = "nouvelle phrase choisie ici"
FAUX_MOT_DE_PASSE = "pas le bon mot de passe"
MOTS_DE_PASSE = (MOT_DE_PASSE_RESPONSABLE, MOT_DE_PASSE_TECHNICIEN, MOT_DE_PASSE_PROVISOIRE, NOUVEAU_MOT_DE_PASSE,
                 FAUX_MOT_DE_PASSE)
AGENT = "Navigateur-de-test/1.0"
MESSAGE_REFUS = "Identifiant ou mot de passe incorrect."
MESSAGE_PROVISOIRE = "Mot de passe provisoire : choisissez votre mot de passe d'abord."
COOKIE_EFFACE = "id=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"
MINUTE, HEURE, JOUR = 60, 3600, 86400
# Les dates de sessions.json sont en heure locale : instants choisis loin de tout changement d'heure.
CREATION_DES_COMPTES = datetime(2026, 1, 5, 9, 0, 0).timestamp()
DEPART = datetime(2026, 6, 15, 10, 0, 0).timestamp()
EXEMPLES_SEGMENTS = {"<table>": "equipements", "<nom>": "photo-essai.jpg"}
FIN_DE_LIGNE = bytes((13, 10))
COMPTES_JSON = b""


def setUpModule():
    """Trois comptes créés une fois (scrypt coûte) puis recopiés dans chaque dossier de données : nicolas.briand
    (responsable), julien.moreau (technicien), lea.martin (demandeur, mot de passe provisoire à changer)."""
    global COMPTES_JSON
    dossier = Path(tempfile.mkdtemp(prefix="prevo-sessions-modele-"))
    try:
        config = serveur.Configuration(str(dossier / "donnees"), [])
        config.horloge = lambda: CREATION_DES_COMPTES
        serveur.creer_dossiers(config)
        serveur.creer_compte(config, "Nicolas", "Briand", "responsable", MOT_DE_PASSE_RESPONSABLE)
        serveur.creer_compte(config, "Julien", "Moreau", "technicien", MOT_DE_PASSE_TECHNICIEN, technicien_id="TEC-0001")
        serveur.creer_compte(config, "Léa", "Martin", "demandeur", MOT_DE_PASSE_PROVISOIRE, a_changer=True)
        COMPTES_JSON = (dossier / "donnees" / "acces" / "comptes.json").read_bytes()
    finally:
        shutil.rmtree(dossier, ignore_errors=True)


def chemin_de(motif):
    """Chemin concret d'un motif de ROUTES_API (« csv/<table> » → « /api/csv/equipements »)."""
    return "/api/" + "/".join(EXEMPLES_SEGMENTS.get(morceau, morceau) for morceau in motif.split("/"))


def empreinte_du_cookie(cookie):
    return hashlib.sha256(cookie.split("=", 1)[1].encode("ascii")).hexdigest()


def iso(instant):
    return datetime.fromtimestamp(instant).strftime("%Y-%m-%dT%H:%M:%S")


def sans_date(entetes):
    return {nom: valeur for nom, valeur in entetes.items() if nom != "date"}


def lignes_du_journal(dossier_donnees):
    chemin = Path(dossier_donnees) / "acces" / "journal-acces.csv"
    if not chemin.is_file():
        return []
    with open(chemin, encoding="utf-8-sig", newline="") as fichier:
        return list(csv.DictReader(fichier, delimiter=";"))


def textes_des_fichiers_d_acces(dossier_donnees):
    """Contenu de chaque fichier de donnees/acces/ (journal, sessions, comptes)."""
    dossier = Path(dossier_donnees) / "acces"
    return {chemin.name: chemin.read_text(encoding="utf-8-sig") for chemin in sorted(dossier.iterdir()) if chemin.is_file()}


class Reponse:
    def __init__(self, statut, entetes, octets):
        self.statut, self.entetes, self.octets = statut, entetes, octets

    def json(self):
        return json.loads(self.octets.decode("utf-8"))

    @property
    def cookie(self):
        """« id=<jeton> » posé par la réponse, ou None."""
        valeur = self.entetes.get("set-cookie")
        return valeur.split(";")[0] if valeur else None


class Client:
    """Requêtes vers un serveur Prévo, une connexion par requête ; un cookie se passe à la main."""

    def __init__(self, url, contexte=None):
        morceaux = urlsplit(url)
        self.https = morceaux.scheme == "https"
        self.hote, self.port = morceaux.hostname, morceaux.port
        self.contexte = contexte

    def requete(self, methode, chemin, corps=None, cookie=None, entetes=None, prevo=True):
        entetes = dict(entetes or {})
        entetes.setdefault("User-Agent", AGENT)
        if cookie:
            entetes["Cookie"] = cookie
        if methode in ("PUT", "POST") and prevo:
            entetes.setdefault("X-Prevo", "1")
        if isinstance(corps, (dict, list)):
            corps = json.dumps(corps).encode("utf-8")
        if self.https:
            connexion = http.client.HTTPSConnection(self.hote, self.port, context=self.contexte, timeout=30)
        else:
            connexion = http.client.HTTPConnection(self.hote, self.port, timeout=30)
        try:
            connexion.request(methode, chemin, body=corps, headers=entetes)
            reponse = connexion.getresponse()
            return Reponse(reponse.status, {nom.lower(): valeur for nom, valeur in reponse.getheaders()}, reponse.read())
        finally:
            connexion.close()

    def connecter(self, identifiant, mot_de_passe, rester=False, cookie=None, entetes=None):
        return self.requete("POST", "/api/connexion", {"identifiant": identifiant, "mot_de_passe": mot_de_passe,
                                                       "rester": rester}, cookie=cookie, entetes=entetes)

    def statut(self, cookie, chemin="/api/versions"):
        return self.requete("GET", chemin, cookie=cookie).statut

    def session(self, cookie):
        return self.requete("GET", "/api/session", cookie=cookie).json()["session"]


# ---------------------------------------------------------------------------
# Serveur dans ce processus : horloge et attente simulées
# ---------------------------------------------------------------------------

class ServeurDansLeProcessus:
    """serveur.py importé et servi dans un fil de ce processus ; config.horloge rend self.instant et config.dormir
    note les attentes demandées (aucune vraie attente)."""

    def __init__(self, dossier_donnees, comptes=True, mandataire=False):
        self.instant = DEPART
        self.attentes = []
        self.config = serveur.Configuration(str(dossier_donnees), [])
        self.config.reglages.update({"comptes": comptes, "mandataire": mandataire})
        self.config.horloge = lambda: self.instant
        self.config.dormir = self.attentes.append
        serveur.creer_dossiers(self.config)
        self.http = serveur.ServeurPrevo(("127.0.0.1", 0), self.config)
        self.config.port = self.http.server_address[1]
        self.client = Client("http://127.0.0.1:%d" % self.config.port)
        self.fil = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.fil.start()

    def avancer(self, secondes):
        self.instant += secondes

    def arreter(self):
        if self.http is not None:
            self.http.shutdown()
            self.http.server_close()
            self.fil.join(timeout=5)
            self.http = None


class CasDansLeProcessus(unittest.TestCase):
    """Un dossier de données neuf avec les trois comptes, un serveur dans ce processus, la console capturée."""

    OPTIONS = {}

    def setUp(self):
        dossier = Path(tempfile.mkdtemp(prefix="prevo-sessions-"))
        self.addCleanup(shutil.rmtree, dossier, True)
        self.donnees = dossier / "donnees"
        (self.donnees / "acces").mkdir(parents=True)
        (self.donnees / "acces" / "comptes.json").write_bytes(COMPTES_JSON)
        self.console = []
        espion = mock.patch.object(serveur, "afficher", side_effect=self.console.append)
        espion.start()
        self.addCleanup(espion.stop)
        self.serveur = self.demarrer(**self.OPTIONS)
        self.client = self.serveur.client

    def demarrer(self, **options):
        lance = ServeurDansLeProcessus(self.donnees, **options)
        self.addCleanup(lance.arreter)
        return lance

    def connecter(self, identifiant, mot_de_passe, rester=False, client=None):
        reponse = (client or self.client).connecter(identifiant, mot_de_passe, rester)
        self.assertEqual(reponse.statut, 200, reponse.octets)
        return reponse.cookie

    def sessions(self):
        chemin = self.donnees / "acces" / "sessions.json"
        return json.loads(chemin.read_text(encoding="utf-8")) if chemin.is_file() else {}

    def verifier_aucun_secret(self, cookies=()):
        """Ni mot de passe ni jeton dans les fichiers d'accès ni sur la console."""
        textes = dict(textes_des_fichiers_d_acces(self.donnees), console="\n".join(map(str, self.console)))
        secrets_ = list(MOTS_DE_PASSE) + [cookie.split("=", 1)[1] for cookie in cookies if cookie]
        for nom, texte in textes.items():
            for secret in secrets_:
                self.assertNotIn(secret, texte, nom)


class TestEchecs(CasDansLeProcessus):

    def test_dix_echecs_bloquent_quinze_minutes_sans_verifier_le_mot_de_passe(self):
        for numero in range(1, 10):
            reponse = self.client.connecter("julien.moreau", FAUX_MOT_DE_PASSE)
            self.assertEqual((reponse.statut, reponse.json()), (401, {"erreur": MESSAGE_REFUS}), numero)
        self.assertEqual(self.serveur.attentes, [1, 2, 4, 8, 8])               # du 5e au 9e échec
        dixieme = self.client.connecter("julien.moreau", FAUX_MOT_DE_PASSE)
        self.assertEqual(dixieme.statut, 429)
        self.assertEqual(dixieme.entetes["retry-after"], "900")
        self.assertEqual(dixieme.json()["attente_secondes"], 900)
        self.assertIn("15 min", dixieme.json()["erreur"])
        # Pendant le blocage, même le bon mot de passe est refusé, sans aucun calcul d'empreinte.
        self.serveur.avancer(14 * MINUTE + 59)
        with mock.patch.object(serveur, "hacher_mot_de_passe", wraps=serveur.hacher_mot_de_passe) as hachage:
            bloque = self.client.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN)
        self.assertEqual(bloque.statut, 429)
        self.assertEqual(bloque.entetes["retry-after"], "1")
        self.assertEqual(bloque.json()["attente_secondes"], 1)
        self.assertEqual(hachage.call_count, 0)
        self.assertNotIn("set-cookie", bloque.entetes)
        self.serveur.avancer(1)                                                 # 15 minutes écoulées
        cookie = self.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN)
        # La réussite remet le compteur à zéro : 4 nouveaux échecs, aucune attente de plus.
        for _ in range(4):
            self.assertEqual(self.client.connecter("julien.moreau", FAUX_MOT_DE_PASSE).statut, 401)
        self.assertEqual(self.serveur.attentes, [1, 2, 4, 8, 8])
        resultats = [ligne["resultat"] for ligne in lignes_du_journal(self.donnees)]
        self.assertEqual(resultats, ["echec"] * 10 + ["bloque", "connexion"] + ["echec"] * 4)
        self.assertTrue(all(ligne["qui"] == "julien.moreau" and ligne["adresse"] == "127.0.0.1"
                            and ligne["agent"] == AGENT for ligne in lignes_du_journal(self.donnees)))
        self.verifier_aucun_secret([cookie])

    def test_identifiant_inconnu_et_mot_de_passe_faux_indiscernables(self):
        reponses = {"inconnu": [], "faux": []}
        with mock.patch.object(serveur, "hacher_mot_de_passe", wraps=serveur.hacher_mot_de_passe) as hachage:
            for numero in range(1, 11):
                avant = hachage.call_count
                reponses["inconnu"].append(self.client.connecter("personne.inconnue", FAUX_MOT_DE_PASSE))
                reponses["faux"].append(self.client.connecter("julien.moreau", FAUX_MOT_DE_PASSE))
                self.assertEqual(hachage.call_count - avant, 2, numero)        # une empreinte calculée chaque fois
        for inconnu, faux in zip(reponses["inconnu"], reponses["faux"]):
            self.assertEqual((inconnu.statut, inconnu.octets), (faux.statut, faux.octets))
            self.assertEqual(sans_date(inconnu.entetes), sans_date(faux.entetes))
        self.assertEqual([r.statut for r in reponses["inconnu"]], [401] * 9 + [429])
        self.assertEqual(reponses["inconnu"][0].json(), {"erreur": MESSAGE_REFUS})
        self.assertEqual(self.serveur.attentes, [1, 1, 2, 2, 4, 4, 8, 8, 8, 8])
        # Le journal ne recopie jamais un identifiant sans compte (un mot de passe tapé dans la mauvaise case).
        qui = {ligne["qui"] for ligne in lignes_du_journal(self.donnees)}
        self.assertEqual(qui, {"julien.moreau", "(inconnu)"})

    def test_tentatives_simultanees_jamais_plus_de_dix(self):
        verifications = []

        def hachage_lent(mot_de_passe, sel=None, algo=None):
            verifications.append(mot_de_passe)
            time.sleep(0.2)                 # les tentatives se recouvrent
            return serveur.ALGO_SCRYPT, "AAAA", "BBBB"

        statuts = []

        def tenter():
            statuts.append(self.client.connecter("julien.moreau", FAUX_MOT_DE_PASSE).statut)

        with mock.patch.object(serveur, "hacher_mot_de_passe", side_effect=hachage_lent):
            fils = [threading.Thread(target=tenter) for _ in range(15)]
            for fil in fils:
                fil.start()
            for fil in fils:
                fil.join(timeout=60)
        self.assertEqual(len(statuts), 15)
        self.assertEqual(len(verifications), 10)
        self.assertTrue(set(statuts) <= {401, 429}, statuts)
        self.assertGreaterEqual(statuts.count(429), 5)
        self.assertEqual(self.client.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN).statut, 429)

    def test_adresse_ralentie_au_dela_de_vingt_echecs_dans_l_heure(self):
        for numero in range(20):        # 4 échecs au plus par identifiant : aucune attente par identifiant
            self.assertEqual(self.client.connecter("inconnu.%d" % (numero // 4), FAUX_MOT_DE_PASSE).statut, 401)
        self.assertEqual(self.serveur.attentes, [])
        self.assertEqual(self.client.connecter("inconnu.9", FAUX_MOT_DE_PASSE).statut, 401)
        self.assertEqual(self.serveur.attentes, [1])                            # 21e tentative de cette adresse
        self.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN)
        self.assertEqual(self.serveur.attentes, [1, 1])                         # toute tentative, même juste
        self.serveur.avancer(HEURE)
        self.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN)
        self.assertEqual(self.serveur.attentes, [1, 1])                         # une heure plus tard : plus rien

    def test_redemarrage_remet_les_compteurs_a_zero(self):
        for _ in range(10):
            self.client.connecter("nicolas.briand", FAUX_MOT_DE_PASSE)
        self.assertEqual(self.client.connecter("nicolas.briand", MOT_DE_PASSE_RESPONSABLE).statut, 429)
        self.serveur.arreter()
        relance = self.demarrer()
        self.connecter("nicolas.briand", MOT_DE_PASSE_RESPONSABLE, client=relance.client)


class TestDurees(CasDansLeProcessus):

    def test_douze_heures_glissantes(self):
        cookie = self.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN)
        cle = empreinte_du_cookie(cookie)
        self.assertEqual(self.sessions()[cle]["vu_le"], iso(DEPART))
        self.serveur.avancer(30)
        self.assertEqual(self.client.statut(cookie), 200)
        self.assertEqual(self.sessions()[cle]["vu_le"], iso(DEPART))            # moins d'une minute : pas réécrit
        self.serveur.avancer(31)
        self.assertEqual(self.client.statut(cookie), 200)
        self.assertEqual(self.sessions()[cle]["vu_le"], iso(DEPART + 61))
        for _ in range(3):                                                       # 3 × 11 h 59 avec de l'activité
            self.serveur.avancer(11 * HEURE + 59 * MINUTE)
            self.assertEqual(self.client.statut(cookie), 200)
        self.serveur.avancer(12 * HEURE + 1)                                     # 12 h et 1 s sans activité
        self.assertEqual(self.client.statut(cookie), 401)
        self.assertNotIn(cle, self.sessions())                                   # session expirée supprimée
        self.assertIsNone(self.client.session(cookie))

    def test_trente_jours_avec_rester_et_sessions_expirees_purgees(self):
        longue = self.client.connecter("nicolas.briand", MOT_DE_PASSE_RESPONSABLE, rester=True)
        self.assertTrue(longue.entetes["set-cookie"].endswith("; Max-Age=2592000"), longue.entetes["set-cookie"])
        courte = self.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN)
        self.assertNotIn("max-age", self.client.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN)
                         .entetes["set-cookie"].lower())
        self.assertTrue(self.sessions()[empreinte_du_cookie(longue.cookie)]["longue"])
        self.serveur.avancer(29 * JOUR)                                          # 29 jours sans aucune activité
        self.assertEqual(self.client.statut(longue.cookie), 200)
        self.assertEqual(self.client.statut(courte), 401)
        identifiants = [session["identifiant"] for session in self.sessions().values()]
        self.assertEqual(identifiants, ["nicolas.briand"])                       # sessions courtes expirées purgées
        self.serveur.avancer(JOUR)                                               # 30 jours pile
        self.assertEqual(self.client.statut(longue.cookie), 200)
        self.serveur.avancer(1)
        self.assertEqual(self.client.statut(longue.cookie), 401)
        self.assertEqual(self.sessions(), {})


class TestMotDePasseEtComptes(CasDansLeProcessus):

    def changer(self, cookie, actuel, nouveau):
        return self.client.requete("POST", "/api/mot-de-passe", {"actuel": actuel, "nouveau": nouveau}, cookie=cookie)

    def test_changer_son_mot_de_passe_ferme_les_autres_sessions(self):
        premiere = self.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN, rester=True)
        seconde = self.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN)
        trop_court = self.changer(premiere, MOT_DE_PASSE_TECHNICIEN, "x" * 11)
        self.assertEqual(trop_court.statut, 400)
        self.assertIn("12 caractères", trop_court.json()["erreur"])
        self.assertEqual(self.changer(premiere, MOT_DE_PASSE_TECHNICIEN, MOT_DE_PASSE_TECHNICIEN).statut, 400)
        faux = self.changer(premiere, FAUX_MOT_DE_PASSE, NOUVEAU_MOT_DE_PASSE)
        self.assertEqual((faux.statut, faux.json()), (403, {"erreur": "Mot de passe actuel incorrect."}))
        change = self.changer(premiere, MOT_DE_PASSE_TECHNICIEN, NOUVEAU_MOT_DE_PASSE)
        self.assertEqual(change.statut, 200, change.octets)
        self.assertFalse(change.json()["session"]["a_changer"])
        self.assertTrue(change.entetes["set-cookie"].endswith("; Max-Age=2592000"))      # « rester » gardé
        for ancien in (premiere, seconde):
            self.assertEqual(self.client.statut(ancien), 401)
        self.assertEqual(self.client.statut(change.cookie), 200)
        self.assertEqual(self.client.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN).statut, 401)
        nouvelle = self.connecter("julien.moreau", NOUVEAU_MOT_DE_PASSE)
        resultats = [ligne["resultat"] for ligne in lignes_du_journal(self.donnees)]
        self.assertEqual(resultats, ["connexion", "connexion", "echec", "modification", "echec", "connexion"])
        self.verifier_aucun_secret([premiere, seconde, change.cookie, nouvelle])

    def test_compte_desactive_ou_reinitialise_perd_ses_sessions(self):
        cookie = self.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN)
        serveur.modifier_compte(self.serveur.config, "julien.moreau", actif=False)
        self.assertEqual(self.client.statut(cookie), 401)
        self.assertNotIn("julien.moreau", [s["identifiant"] for s in self.sessions().values()])
        # Compte désactivé : la même réponse qu'un mot de passe faux, après le même calcul d'empreinte.
        with mock.patch.object(serveur, "hacher_mot_de_passe", wraps=serveur.hacher_mot_de_passe) as hachage:
            refus = self.client.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN)
        self.assertEqual((refus.statut, refus.json()), (401, {"erreur": MESSAGE_REFUS}))
        self.assertEqual(hachage.call_count, 1)
        serveur.modifier_compte(self.serveur.config, "julien.moreau", actif=True)
        cookie = self.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN)
        provisoire = serveur.reinitialiser_compte(self.serveur.config, "julien.moreau")
        self.assertEqual(self.client.statut(cookie), 401)
        reponse = self.client.connecter("julien.moreau", provisoire)
        self.assertEqual(reponse.statut, 200)
        self.assertTrue(reponse.json()["session"]["a_changer"])
        refus = self.client.requete("GET", "/api/versions", cookie=reponse.cookie)
        self.assertEqual((refus.statut, refus.json()), (403, {"erreur": MESSAGE_PROVISOIRE}))

    def test_compte_change_par_un_autre_processus_refuse_ses_sessions(self):
        """comptes.json réécrit ailleurs sans toucher aux sessions (--reinitialiser lancé pendant que le serveur
        tourne) : chaque requête revérifie le compte, actif et mot de passe inchangé depuis la connexion."""
        technicien = self.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN)
        responsable = self.connecter("nicolas.briand", MOT_DE_PASSE_RESPONSABLE)
        chemin = self.donnees / "acces" / "comptes.json"
        contenu = json.loads(chemin.read_text(encoding="utf-8"))
        for compte in contenu["comptes"]:
            if compte["identifiant"] == "julien.moreau":
                compte["actif"] = False
            elif compte["identifiant"] == "nicolas.briand":
                compte["mot_de_passe_le"] = iso(DEPART + 1)
        chemin.write_text(json.dumps(contenu, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(len(self.sessions()), 2)
        self.assertEqual(self.client.statut(technicien), 401)
        self.assertEqual(self.client.statut(responsable), 401)
        self.assertEqual(self.sessions(), {})

    def test_comptes_illisibles_ping_repond_et_la_connexion_le_dit(self):
        cookie = self.connecter("nicolas.briand", MOT_DE_PASSE_RESPONSABLE)
        (self.donnees / "acces" / "comptes.json").write_text("{ pas du json", encoding="utf-8")
        self.assertEqual(self.client.statut(cookie, "/api/ping"), 200)
        self.assertEqual(self.client.requete("GET", "/api/session", cookie=cookie).json(),
                         {"comptes": True, "session": None})
        self.assertEqual(self.client.statut(cookie), 401)
        refus = self.client.connecter("nicolas.briand", MOT_DE_PASSE_RESPONSABLE)
        self.assertEqual((refus.statut, refus.json()), (500, {"erreur": serveur.MESSAGE_COMPTES_ILLISIBLES}))

    def test_colonne_tailscale_seulement_derriere_un_mandataire_sur_ce_pc(self):
        entetes = {"Tailscale-User-Login": "julien@github"}
        self.assertEqual(self.client.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN, entetes=entetes).statut, 200)
        mandate = self.demarrer(mandataire=True)
        self.assertEqual(mandate.client.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN, entetes=entetes).statut, 200)
        lignes = [ligne for ligne in lignes_du_journal(self.donnees) if ligne["resultat"] == "connexion"]
        self.assertEqual([ligne["tailscale"] for ligne in lignes], ["", "julien@github"])


class TestSansComptes(CasDansLeProcessus):

    OPTIONS = {"comptes": False}

    def test_rien_ne_change_et_la_connexion_est_refusee_proprement(self):
        self.assertEqual(self.client.requete("GET", "/api/session").json(), {"comptes": False, "session": None})
        self.assertEqual(self.client.statut(None), 200)
        self.assertEqual(self.client.statut("id=" + "A" * 43), 200)
        demandes = (("/api/connexion", {"identifiant": "nicolas.briand", "mot_de_passe": MOT_DE_PASSE_RESPONSABLE}),
                    ("/api/deconnexion", None),
                    ("/api/mot-de-passe", {"actuel": MOT_DE_PASSE_RESPONSABLE, "nouveau": NOUVEAU_MOT_DE_PASSE}),
                    ("/api/acces/deconnecter-partout", None))
        for chemin, corps in demandes:
            with self.subTest(chemin=chemin):
                reponse = self.client.requete("POST", chemin, corps)
                self.assertEqual((reponse.statut, reponse.json()), (400, {"erreur": serveur.MESSAGE_SANS_COMPTES}))
                self.assertNotIn("set-cookie", reponse.entetes)
        self.assertFalse((self.donnees / "acces" / "sessions.json").exists())
        self.assertEqual(lignes_du_journal(self.donnees), [])


class TestTableDesRoutes(unittest.TestCase):

    def test_chaque_route_a_sa_fonction_et_les_routes_ouvertes_sont_listees(self):
        for route, fonction in serveur.ROUTES_API.items():
            with self.subTest(route=route):
                self.assertTrue(callable(getattr(serveur.GestionnaireRequetes, fonction, None)))
        self.assertEqual(set(serveur.ROUTES_PUBLIQUES), {("GET", "ping"), ("GET", "session"), ("POST", "connexion")})
        self.assertEqual(set(serveur.ROUTES_MOT_DE_PASSE_PROVISOIRE),
                         {("GET", "session"), ("POST", "mot-de-passe"), ("POST", "deconnexion")})
        self.assertTrue(set(serveur.ROUTES_PUBLIQUES) | set(serveur.ROUTES_MOT_DE_PASSE_PROVISOIRE)
                        <= set(serveur.ROUTES_API))
        self.assertEqual(serveur.MESSAGE_MOT_DE_PASSE_PROVISOIRE, MESSAGE_PROVISOIRE)
        self.assertEqual(serveur.MESSAGE_CONNEXION_REFUSEE, MESSAGE_REFUS)


# ---------------------------------------------------------------------------
# Serveur réel : tests/commun.py, --config à « comptes », vraie horloge
# ---------------------------------------------------------------------------

class CasServeurReel(unittest.TestCase):
    """serveur.py lancé par ServeurPrevo (tests/commun.py) sur une copie de la démo, avec comptes.json préparé et un
    fichier de configuration à « comptes » ; écoute sur 127.0.0.1. Moins de 5 échecs par identifiant et de 20 en tout :
    aucune vraie attente."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.racine = Path(tempfile.mkdtemp(prefix="prevo-sessions-reel-"))
        cls.addClassCleanup(shutil.rmtree, cls.racine, True)
        source = cls.racine / "source"
        if commun.DOSSIER_DEMO.is_dir():
            shutil.copytree(commun.DOSSIER_DEMO, source)
        (source / "acces").mkdir(parents=True)
        (source / "acces" / "comptes.json").write_bytes(COMPTES_JSON)
        configuration = cls.racine / "prevo.config.json"
        configuration.write_text(json.dumps({"comptes": True}), encoding="utf-8")
        arguments = ["--config", str(configuration)] + cls.arguments_en_plus()
        cls.serveur = commun.ServeurPrevo(source=source, arguments=arguments)
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)
        cls.client = Client(cls.serveur.url, cls.contexte())

    @classmethod
    def arguments_en_plus(cls):
        return []

    @classmethod
    def contexte(cls):
        return None

    def connecter(self, identifiant, mot_de_passe, rester=False):
        reponse = self.client.connecter(identifiant, mot_de_passe, rester)
        self.assertEqual(reponse.statut, 200, reponse.octets)
        return reponse.cookie


class TestServeurReel(CasServeurReel):

    def test_chaque_route_de_l_api_rend_401_sans_session(self):
        fermees = sorted(route for route in serveur.ROUTES_API if route not in serveur.ROUTES_PUBLIQUES)
        self.assertGreaterEqual(len(fermees), 15)
        for methode, motif in fermees:
            for cookie in (None, "id=" + "A" * 43):                 # sans cookie, puis avec un jeton inconnu
                with self.subTest(route="%s %s" % (methode, motif), cookie=cookie):
                    corps = b"{}" if methode in ("PUT", "POST") else None
                    reponse = self.client.requete(methode, chemin_de(motif), corps, cookie=cookie)
                    self.assertEqual((reponse.statut, reponse.json()), (401, {"erreur": serveur.MESSAGE_SESSION_ABSENTE}))
        for chemin in ("/api/inexistant", "/api/acces/comptes", "/api/csv/inconnue"):
            with self.subTest(chemin=chemin):
                self.assertEqual(self.client.statut(None, chemin), 401)

    def test_routes_publiques_et_fichiers_de_l_application_ouverts_sans_session(self):
        for methode, motif in serveur.ROUTES_PUBLIQUES:
            with self.subTest(route=motif):
                if methode == "GET":
                    reponse = self.client.requete(methode, chemin_de(motif))
                else:                       # POST /api/connexion : ouverte sans session préalable
                    reponse = self.client.connecter("nicolas.briand", MOT_DE_PASSE_RESPONSABLE)
                self.assertEqual(reponse.statut, 200, reponse.octets)
        self.assertEqual(self.client.requete("GET", "/api/session").json(), {"comptes": True, "session": None})
        # X-Prevo reste exigé sur la connexion comme sur toute écriture (une page d'un autre site ne l'envoie pas).
        sans_prevo = self.client.requete("POST", "/api/connexion", {"identifiant": "nicolas.briand",
                                                                    "mot_de_passe": MOT_DE_PASSE_RESPONSABLE},
                                         prevo=False)
        self.assertEqual(sans_prevo.statut, 403)
        self.assertNotIn("set-cookie", sans_prevo.entetes)
        for chemin in ("/", "/index.html", "/js/app.js", "/css/style.css", "/favicon.svg"):
            with self.subTest(chemin=chemin):
                self.assertEqual(self.client.statut(None, chemin), 200)

    def test_corps_jamais_lu_sans_session(self):
        # 10 Mo annoncés, rien d'envoyé : 401 aussitôt et connexion fermée, le serveur n'attend pas le corps.
        lignes = ["PUT /api/csv/equipements HTTP/1.1", "Host: 127.0.0.1:%d" % self.serveur.port, "X-Prevo: 1",
                  "X-Version-Attendue: aucune", "Content-Length: %d" % (10 * 1024 * 1024)]
        debut = time.monotonic()
        with socket.create_connection(("127.0.0.1", self.serveur.port), timeout=10) as prise:
            prise.sendall(FIN_DE_LIGNE.join(ligne.encode("ascii") for ligne in lignes) + FIN_DE_LIGNE + FIN_DE_LIGNE)
            recu = b""
            while True:
                morceau = prise.recv(65536)
                if not morceau:
                    break
                recu += morceau
        self.assertLess(time.monotonic() - debut, 5)
        self.assertTrue(recu.startswith(b"HTTP/1.1 401"), recu[:80])
        self.assertIn(b"Connection: close", recu)
        # Petit corps (1 Ko) : lu et jeté, la connexion persistante reste utilisable.
        connexion = http.client.HTTPConnection("127.0.0.1", self.serveur.port, timeout=10)
        try:
            connexion.request("POST", "/api/sauvegarde", body=b"x" * 1024, headers={"X-Prevo": "1"})
            reponse = connexion.getresponse()
            reponse.read()
            self.assertEqual(reponse.status, 401)
            self.assertIsNone(reponse.getheader("Connection"))
            prise = connexion.sock
            connexion.request("GET", "/api/ping")
            reponse = connexion.getresponse()
            reponse.read()
            self.assertEqual(reponse.status, 200)
            self.assertIs(connexion.sock, prise)
        finally:
            connexion.close()
        self.assertEqual(list((self.serveur.dossier / "sauvegardes").glob("*")), [])

    def test_cookie_connexion_session_deconnexion(self):
        entree = self.client.connecter("nicolas.briand", MOT_DE_PASSE_RESPONSABLE)
        self.assertEqual(entree.statut, 200, entree.octets)
        self.assertRegex(entree.entetes["set-cookie"], r"^id=[A-Za-z0-9_-]{43}; Path=/; HttpOnly; SameSite=Lax$")
        cookie = entree.cookie
        jeton = cookie.split("=", 1)[1]
        attendu = {"identifiant": "nicolas.briand", "role": "responsable", "prenom": "Nicolas", "nom": "Briand",
                   "technicien_id": "", "a_changer": False, "appareil": False}
        self.assertEqual(entree.json(), {"comptes": True, "session": attendu})
        self.assertNotIn(jeton.encode("ascii"), entree.octets)
        self.assertEqual(self.client.requete("GET", "/api/session", cookie=cookie).json(),
                         {"comptes": True, "session": attendu})
        for chemin in ("/api/versions", "/api/csv/equipements", "/api/info"):
            with self.subTest(chemin=chemin):
                self.assertEqual(self.client.statut(cookie, chemin), 200)
        # sessions.json ne garde que l'empreinte du jeton
        texte = (self.serveur.dossier / "acces" / "sessions.json").read_text(encoding="utf-8")
        self.assertNotIn(jeton, texte)
        self.assertEqual(json.loads(texte)[hashlib.sha256(jeton.encode("ascii")).hexdigest()]["identifiant"],
                         "nicolas.briand")
        # « rester » : Max-Age de 30 jours ; jeton neuf à chaque connexion, l'ancienne session du navigateur fermée
        longue = self.client.connecter("nicolas.briand", MOT_DE_PASSE_RESPONSABLE, rester=True, cookie=cookie)
        self.assertRegex(longue.entetes["set-cookie"],
                         r"^id=[A-Za-z0-9_-]{43}; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000$")
        self.assertNotEqual(longue.cookie, cookie)
        self.assertEqual(self.client.statut(cookie), 401)
        # déconnexion : cookie effacé, session supprimée, puis 401
        sortie = self.client.requete("POST", "/api/deconnexion", cookie=longue.cookie)
        self.assertEqual((sortie.statut, sortie.json()), (200, {"comptes": True, "session": None}))
        self.assertEqual(sortie.entetes["set-cookie"], COOKIE_EFFACE)
        self.assertEqual(self.client.statut(longue.cookie), 401)
        self.assertIsNone(self.client.session(longue.cookie))
        self.assertNotIn(empreinte_du_cookie(longue.cookie),
                         json.loads((self.serveur.dossier / "acces" / "sessions.json").read_text(encoding="utf-8")))

    def test_deconnecter_partout(self):
        premiere = self.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN)
        seconde = self.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN)
        soi = self.client.requete("POST", "/api/acces/deconnecter-partout", cookie=premiere)
        self.assertEqual(soi.statut, 200, soi.octets)
        self.assertEqual(soi.json()["identifiant"], "julien.moreau")
        self.assertGreaterEqual(soi.json()["sessions_fermees"], 2)
        self.assertEqual(soi.entetes["set-cookie"], COOKIE_EFFACE)
        for cookie in (premiere, seconde):
            self.assertEqual(self.client.statut(cookie), 401)
        technicien = self.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN)
        refus = self.client.requete("POST", "/api/acces/deconnecter-partout", {"identifiant": "nicolas.briand"},
                                    cookie=technicien)
        self.assertEqual(refus.statut, 403)
        responsable = self.connecter("nicolas.briand", MOT_DE_PASSE_RESPONSABLE)
        autre = self.client.requete("POST", "/api/acces/deconnecter-partout", {"identifiant": "Julien.Moreau"},
                                    cookie=responsable)
        self.assertEqual(autre.statut, 200, autre.octets)
        self.assertEqual(autre.json()["identifiant"], "julien.moreau")
        self.assertGreaterEqual(autre.json()["sessions_fermees"], 1)
        self.assertNotIn("set-cookie", autre.entetes)
        self.assertEqual(self.client.statut(technicien), 401)
        self.assertEqual(self.client.statut(responsable), 200)
        inconnu = self.client.requete("POST", "/api/acces/deconnecter-partout", {"identifiant": "personne.inconnue"},
                                      cookie=responsable)
        self.assertEqual(inconnu.statut, 404)
        self.assertEqual(self.client.requete("POST", "/api/deconnexion", cookie=responsable).statut, 200)

    def test_journal_sans_mot_de_passe_ni_jeton(self):
        self.assertEqual(self.client.connecter("julien.moreau", FAUX_MOT_DE_PASSE).statut, 401)
        self.assertEqual(self.client.connecter(MOT_DE_PASSE_TECHNICIEN, MOT_DE_PASSE_TECHNICIEN).statut, 401)
        entree = self.client.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN)
        self.assertEqual(self.client.requete("POST", "/api/deconnexion", cookie=entree.cookie).statut, 200)
        lignes = lignes_du_journal(self.serveur.dossier)
        self.assertEqual([(ligne["qui"], ligne["resultat"]) for ligne in lignes[-4:]],
                         [("julien.moreau", "echec"), ("(inconnu)", "echec"), ("julien.moreau", "connexion"),
                          ("julien.moreau", "deconnexion")])
        for ligne in lignes[-4:]:
            self.assertEqual((ligne["adresse"], ligne["agent"], ligne["tailscale"]), ("127.0.0.1", AGENT, ""))
        textes = dict(textes_des_fichiers_d_acces(self.serveur.dossier), console=self.serveur.sortie_console())
        for nom, texte in textes.items():
            for secret in MOTS_DE_PASSE + (entree.cookie.split("=", 1)[1],):
                with self.subTest(fichier=nom, secret=secret[:6]):
                    self.assertNotIn(secret, texte)

    def test_meme_reponse_pour_un_identifiant_inconnu_et_un_mot_de_passe_faux(self):
        inconnu = self.client.connecter("personne.inconnue", "un mot de passe quelconque")
        faux = self.client.connecter("nicolas.briand", "un mot de passe quelconque")
        self.assertEqual((inconnu.statut, inconnu.json()), (401, {"erreur": MESSAGE_REFUS}))
        self.assertEqual((inconnu.statut, inconnu.octets), (faux.statut, faux.octets))
        self.assertEqual(sans_date(inconnu.entetes), sans_date(faux.entetes))
        self.assertNotIn("set-cookie", faux.entetes)

    def test_mot_de_passe_provisoire_n_ouvre_que_trois_routes(self):
        entree = self.client.connecter("lea.martin", MOT_DE_PASSE_PROVISOIRE)
        self.assertEqual(entree.statut, 200, entree.octets)
        cookie = entree.cookie
        self.assertTrue(self.client.session(cookie)["a_changer"])                # GET /api/session : permis
        permises = set(serveur.ROUTES_PUBLIQUES) | set(serveur.ROUTES_MOT_DE_PASSE_PROVISOIRE)
        for methode, motif in sorted(set(serveur.ROUTES_API) - permises):
            with self.subTest(route="%s %s" % (methode, motif)):
                corps = b"{}" if methode in ("PUT", "POST") else None
                reponse = self.client.requete(methode, chemin_de(motif), corps, cookie=cookie)
                self.assertEqual((reponse.statut, reponse.json()), (403, {"erreur": MESSAGE_PROVISOIRE}))
        sortie = self.client.requete("POST", "/api/deconnexion", cookie=cookie)              # permis
        self.assertEqual(sortie.statut, 200)
        cookie = self.connecter("lea.martin", MOT_DE_PASSE_PROVISOIRE)
        change = self.client.requete("POST", "/api/mot-de-passe",                           # permis
                                     {"actuel": MOT_DE_PASSE_PROVISOIRE, "nouveau": NOUVEAU_MOT_DE_PASSE}, cookie=cookie)
        self.assertEqual(change.statut, 200, change.octets)
        self.assertFalse(change.json()["session"]["a_changer"])
        self.assertEqual(self.client.statut(change.cookie), 200)
        self.assertEqual(self.client.statut(cookie), 401)


class TestServeurReelHttps(CasServeurReel):

    @classmethod
    def arguments_en_plus(cls):
        cls.certificat, cls.cle = fabriquer_certificat(cls.racine)          # saute la classe sans openssl
        return ["--certificat", str(cls.certificat), "--cle", str(cls.cle)]

    @classmethod
    def contexte(cls):
        return ssl.create_default_context(cafile=str(cls.certificat))

    def test_cookie_secure_en_https(self):
        self.assertTrue(self.serveur.url.startswith("https://"))
        entree = self.client.connecter("nicolas.briand", MOT_DE_PASSE_RESPONSABLE)
        self.assertEqual(entree.statut, 200, entree.octets)
        self.assertRegex(entree.entetes["set-cookie"], r"^id=[A-Za-z0-9_-]{43}; Path=/; HttpOnly; SameSite=Lax; Secure$")
        longue = self.client.connecter("nicolas.briand", MOT_DE_PASSE_RESPONSABLE, rester=True, cookie=entree.cookie)
        self.assertRegex(longue.entetes["set-cookie"],
                         r"^id=[A-Za-z0-9_-]{43}; Path=/; HttpOnly; SameSite=Lax; Secure; Max-Age=2592000$")
        self.assertEqual(self.client.statut(longue.cookie), 200)
        sortie = self.client.requete("POST", "/api/deconnexion", cookie=longue.cookie)
        self.assertEqual(sortie.entetes["set-cookie"], "id=; Path=/; HttpOnly; SameSite=Lax; Secure; Max-Age=0")
        self.assertEqual(self.client.statut(longue.cookie), 401)


if __name__ == "__main__":
    unittest.main()
