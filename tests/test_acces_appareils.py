"""Lot 7 — appareils enrôlés (ARCHITECTURE.md §22.3, §22.4, §22.5 ; D125, D126 ; CS123 ; tâche T153).

Ce qui est vérifié :
    table          POST /api/enroler est une route publique ; chaque route des invitations et des appareils a sa
                   fonction et sa ligne dans ROLES_PAR_ROUTE (responsable seulement) ;
    invitation     créée par le responsable (24 h par défaut, « heures » de 1 à 168, 400 au-delà ou champ inconnu),
                   jeton rendu une seule fois avec le chemin /#/enroler/<jeton>, seule son empreinte dans
                   appareils.json, ligne « invitation » au journal ; refusée au technicien et au demandeur (403) ;
    enrôlement     un navigateur sans session qui ouvre l'invitation donne son nom et devient demandeur : cookie
                   appareil=<jeton>; Path=/; HttpOnly; SameSite=Lax; Max-Age=31536000, /api/session « appareil » vrai,
                   nom mémorisé, libellé d'après le navigateur ; usage multiple ; crée une demande, lit ses tables,
                   403 sur une table ou une route d'un autre rôle ; 401 invitation inconnue, mal formée, expirée ou
                   révoquée (même message), 400 nom manquant ou trop long, X-Prevo exigé ;
    durées         un an glissant depuis la dernière activité (vu_le réécrit au plus une fois par minute),
                   /api/session renvoie le cookie pour un an ; appareil expiré : 401, cookie effacé ;
    révocation     un appareil, ou tous : 401 immédiat avec « appareil_refuse » et le cookie effacé, ligne
                   « revocation » au journal, 404 id inconnu ; une invitation révoquée ne sert plus ;
    désactivé      demandeurs_avec_compte vrai : enrôlement refusé (403) et les appareils déjà enrôlés ne sont
                   plus reconnus ; sans comptes : 400 clair ;
    oubli          invitations finies et appareils révoqués ou expirés oubliés après 30 jours ; appareils.json
                   illisible : aucun appareil reconnu, le fichier est réécrit à l'invitation suivante ;
    secrets        aucun jeton (invitation, appareil) dans les fichiers d'accès ni sur la console.

Serveur dans ce processus (serveur.py importé, Configuration dont l'horloge est simulée), copie de la démo, aucune
sortie réseau, aucune commande d'administrateur.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_acces_appareils.py" -v
"""
import csv
import hashlib
import http.client
import importlib.util
import json
import shutil
import tempfile
import threading
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

import commun
from commun import RACINE

SCRIPT = RACINE / "serveur.py"


def charger_serveur():
    specification = importlib.util.spec_from_file_location("serveur_prevo_appareils", SCRIPT)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


serveur = charger_serveur()

MOT_DE_PASSE_RESPONSABLE = "phrase du responsable 2026"
MOT_DE_PASSE_TECHNICIEN = "cle a molette et graisse"
MOT_DE_PASSE_DEMANDEUR = "une demande de lea 2026"
AGENT_ANDROID = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/130.0 Mobile Safari/537.36"
AGENT_IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"
AGENT_PC = "Navigateur-de-test/1.0 (Windows NT 10.0)"
MINUTE, HEURE, JOUR = 60, 3600, 86400
UN_AN = 365 * JOUR
CREATION_DES_COMPTES = datetime(2026, 1, 5, 9, 0, 0).timestamp()
DEPART = datetime(2026, 6, 15, 10, 0, 0).timestamp()
COOKIE_APPAREIL_EFFACE = "appareil=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"
COMPTES_JSON = b""


def setUpModule():
    global COMPTES_JSON
    dossier = Path(tempfile.mkdtemp(prefix="prevo-appareils-modele-"))
    try:
        config = serveur.Configuration(str(dossier / "donnees"), [])
        config.horloge = lambda: CREATION_DES_COMPTES
        serveur.creer_dossiers(config)
        serveur.creer_compte(config, "Nicolas", "Briand", "responsable", MOT_DE_PASSE_RESPONSABLE)
        serveur.creer_compte(config, "Julien", "Moreau", "technicien", MOT_DE_PASSE_TECHNICIEN, technicien_id="TEC-0001")
        serveur.creer_compte(config, "Léa", "Martin", "demandeur", MOT_DE_PASSE_DEMANDEUR)
        COMPTES_JSON = (dossier / "donnees" / "acces" / "comptes.json").read_bytes()
    finally:
        shutil.rmtree(dossier, ignore_errors=True)


def iso(instant):
    return datetime.fromtimestamp(instant).strftime("%Y-%m-%dT%H:%M:%S")


def empreinte(jeton):
    return hashlib.sha256(jeton.encode("ascii")).hexdigest()


def lignes_du_journal(dossier_donnees):
    chemin = Path(dossier_donnees) / "acces" / "journal-acces.csv"
    if not chemin.is_file():
        return []
    with open(chemin, encoding="utf-8-sig", newline="") as fichier:
        return list(csv.DictReader(fichier, delimiter=";"))


class Reponse:
    def __init__(self, statut, entetes, octets):
        self.statut, self.entetes, self.octets = statut, entetes, octets

    def json(self):
        return json.loads(self.octets.decode("utf-8"))

    @property
    def set_cookie(self):
        return self.entetes.get("set-cookie")

    @property
    def cookie(self):
        """« nom=<jeton> » posé par la réponse, ou None."""
        return self.set_cookie.split(";")[0] if self.set_cookie else None


class Client:
    def __init__(self, port):
        self.port = port

    def requete(self, methode, chemin, corps=None, cookie=None, entetes=None, prevo=True, agent=AGENT_PC):
        entetes = dict(entetes or {})
        entetes.setdefault("User-Agent", agent)
        if cookie:
            entetes["Cookie"] = cookie
        if methode in ("PUT", "POST") and prevo:
            entetes.setdefault("X-Prevo", "1")
        if isinstance(corps, (dict, list)):
            corps = json.dumps(corps).encode("utf-8")
        connexion = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        try:
            connexion.request(methode, chemin, body=corps, headers=entetes)
            reponse = connexion.getresponse()
            return Reponse(reponse.status, {nom.lower(): valeur for nom, valeur in reponse.getheaders()}, reponse.read())
        finally:
            connexion.close()

    def connecter(self, identifiant, mot_de_passe):
        reponse = self.requete("POST", "/api/connexion", {"identifiant": identifiant, "mot_de_passe": mot_de_passe,
                                                          "rester": False})
        assert reponse.statut == 200, reponse.octets
        return reponse.cookie

    def session(self, cookie):
        return self.requete("GET", "/api/session", cookie=cookie).json()["session"]


class ServeurDansLeProcessus:
    def __init__(self, dossier_donnees, **reglages):
        self.instant = DEPART
        self.config = serveur.Configuration(str(dossier_donnees), [])
        self.config.reglages.update({"comptes": True, "demandeurs_avec_compte": False})
        self.config.reglages.update(reglages)
        self.config.horloge = lambda: self.instant
        serveur.creer_dossiers(self.config)
        self.http = serveur.ServeurPrevo(("127.0.0.1", 0), self.config)
        self.config.port = self.http.server_address[1]
        self.client = Client(self.config.port)
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


class CasAppareils(unittest.TestCase):
    """Copie de la démo avec les trois comptes, serveur dans ce processus, console capturée, responsable connecté."""

    REGLAGES = {}

    def setUp(self):
        dossier = Path(tempfile.mkdtemp(prefix="prevo-appareils-"))
        self.addCleanup(shutil.rmtree, dossier, True)
        self.donnees = dossier / "donnees"
        shutil.copytree(commun.DOSSIER_DEMO, self.donnees)
        (self.donnees / "acces").mkdir()
        (self.donnees / "acces" / "comptes.json").write_bytes(COMPTES_JSON)
        self.console = []
        espion = mock.patch.object(serveur, "afficher", side_effect=self.console.append)
        espion.start()
        self.addCleanup(espion.stop)
        self.serveur = ServeurDansLeProcessus(self.donnees, **self.REGLAGES)
        self.addCleanup(self.serveur.arreter)
        self.client = self.serveur.client
        self.jetons = []
        if self.serveur.config.reglages.get("comptes"):
            self.responsable = self.client.connecter("nicolas.briand", MOT_DE_PASSE_RESPONSABLE)

    # -- aides ---------------------------------------------------------------

    def fichier_appareils(self):
        chemin = self.donnees / "acces" / "appareils.json"
        return json.loads(chemin.read_text(encoding="utf-8")) if chemin.is_file() else None

    def responsable_frais(self):
        """Le cookie du responsable, reconnecté si ses 12 h de session sont passées (sauts d'horloge)."""
        if self.client.session(self.responsable) is None:
            self.responsable = self.client.connecter("nicolas.briand", MOT_DE_PASSE_RESPONSABLE)
        return self.responsable

    def inviter(self, corps=None, cookie=None):
        reponse = self.client.requete("POST", "/api/acces/invitations", corps, cookie=cookie or self.responsable_frais())
        self.assertEqual(reponse.statut, 200, reponse.octets)
        donnees = reponse.json()
        self.jetons.append(donnees["jeton"])
        return donnees

    def enroler(self, jeton, nom="Léa Martin", agent=AGENT_ANDROID, cookie=None):
        reponse = self.client.requete("POST", "/api/enroler", {"invitation": jeton, "nom": nom}, cookie=cookie,
                                      agent=agent)
        if reponse.statut == 200 and reponse.cookie:
            self.jetons.append(reponse.cookie.split("=", 1)[1])
        return reponse

    def appareil(self, jeton=None, **kwargs):
        """Un appareil enrôlé : rend (cookie « appareil=… », identité de /api/session)."""
        jeton = jeton or self.inviter()["jeton"]
        reponse = self.enroler(jeton, **kwargs)
        self.assertEqual(reponse.statut, 200, reponse.octets)
        return reponse.cookie, reponse.json()["session"]

    def ligne_de_demande(self, numero, nom):
        with open(self.donnees / "demandes.csv", encoding="utf-8-sig", newline="") as fichier:
            entete = next(csv.reader(fichier, delimiter=";"))
        valeurs = {"id": "DI-2026-9%03d" % numero, "date_heure": "2026-06-15 10:05", "demandeur": nom,
                   "equipement_id": "EQ-0001", "symptome": "Bruit anormal", "impact": "Faible",
                   "description": "Essai d'enrôlement", "statut": "Nouvelle"}
        return (";".join(entete) + "\r\n" + ";".join(valeurs.get(nom_colonne, "") for nom_colonne in entete)
                + "\r\n").encode("utf-8")

    def verifier_aucun_secret(self):
        """Ni jeton d'invitation ni jeton d'appareil dans les fichiers d'accès ni sur la console."""
        textes = {chemin.name: chemin.read_text(encoding="utf-8-sig")
                  for chemin in (self.donnees / "acces").iterdir() if chemin.is_file()}
        textes["console"] = "\n".join(map(str, self.console))
        self.assertTrue(self.jetons)
        for nom, texte in textes.items():
            for jeton in self.jetons:
                self.assertNotIn(jeton, texte, nom)


class TestTableDesRoutes(unittest.TestCase):

    def test_routes_des_appareils_declarees_publiques_ou_reservees(self):
        self.assertIn(("POST", "enroler"), serveur.ROUTES_PUBLIQUES)
        self.assertEqual(serveur.ROLES_PAR_ROUTE[("POST", "enroler")], serveur.TOUS)
        for route in (("GET", "acces/invitations"), ("POST", "acces/invitations"),
                      ("POST", "acces/invitations/<id>/revoquer"), ("POST", "acces/appareils/<id>/revoquer"),
                      ("POST", "acces/appareils/revoquer-tous")):
            with self.subTest(route=route):
                self.assertIn(route, serveur.ROUTES_API)
                self.assertTrue(callable(getattr(serveur.GestionnaireRequetes, serveur.ROUTES_API[route], None)))
                self.assertEqual(serveur.ROLES_PAR_ROUTE[route], serveur.RESPONSABLE)
        self.assertEqual(serveur.motif_de_route(["acces", "appareils", "revoquer-tous"]), "acces/appareils/revoquer-tous")
        self.assertEqual(serveur.motif_de_route(["acces", "appareils", "AP-1234", "revoquer"]),
                         "acces/appareils/<id>/revoquer")
        self.assertEqual(serveur.segment_de_route("acces/appareils/<id>/revoquer", ["acces", "appareils", "AP-1234",
                                                                                     "revoquer"]), "AP-1234")
        self.assertEqual(serveur.libelle_appareil(AGENT_ANDROID), "Téléphone ou tablette Android")
        self.assertEqual(serveur.libelle_appareil(AGENT_IPHONE), "iPhone")
        self.assertEqual(serveur.libelle_appareil(AGENT_PC), "PC Windows")
        self.assertEqual(serveur.libelle_appareil("Robot " + "x" * 200), ("Robot " + "x" * 200)[:80])
        self.assertEqual(serveur.libelle_appareil(""), "Appareil")


class TestInvitations(CasAppareils):

    def test_invitation_creee_par_le_responsable_jeton_rendu_une_fois(self):
        donnees = self.inviter()
        jeton, invitation = donnees["jeton"], donnees["invitation"]
        self.assertRegex(jeton, r"^[A-Za-z0-9_-]{43}$")
        self.assertEqual(donnees["chemin"], "/#/enroler/" + jeton)
        self.assertRegex(invitation["id"], r"^INV-[0-9A-F]{4}$")
        self.assertEqual((invitation["cree_le"], invitation["expire_le"]), (iso(DEPART), iso(DEPART + 24 * HEURE)))
        self.assertEqual((invitation["revoquee"], invitation["valide"]), (False, True))
        self.assertNotIn("empreinte", invitation)
        fichier = self.fichier_appareils()
        self.assertEqual([i["empreinte"] for i in fichier["invitations"]], [empreinte(jeton)])
        self.assertEqual(fichier["appareils"], [])
        journal = lignes_du_journal(self.donnees)
        self.assertEqual([(l["qui"], l["resultat"]) for l in journal][-1], ("nicolas.briand", "invitation"))
        self.assertEqual((journal[-1]["adresse"], journal[-1]["agent"]), ("127.0.0.1", AGENT_PC))
        # Durée choisie, de 1 à 168 h ; corps vide ou {} : la durée de la configuration.
        self.assertEqual(self.inviter({"heures": 2})["invitation"]["expire_le"], iso(DEPART + 2 * HEURE))
        self.assertEqual(self.inviter({})["invitation"]["expire_le"], iso(DEPART + 24 * HEURE))
        self.serveur.config.reglages["invitation_heures"] = 168
        self.assertEqual(self.inviter()["invitation"]["expire_le"], iso(DEPART + 7 * JOUR))
        for corps in ({"heures": 0}, {"heures": 169}, {"heures": "2"}, {"heures": True}, {"duree": 2}):
            with self.subTest(corps=corps):
                reponse = self.client.requete("POST", "/api/acces/invitations", corps, cookie=self.responsable)
                self.assertEqual(reponse.statut, 400, reponse.octets)
        # Liste : jamais d'empreinte ; enrôlement actif.
        liste = self.client.requete("GET", "/api/acces/invitations", cookie=self.responsable).json()
        self.assertEqual(len(liste["invitations"]), 4)
        self.assertTrue(all("empreinte" not in i and i["valide"] for i in liste["invitations"]))
        self.assertEqual((liste["appareils"], liste["enrolement_actif"]), ([], True))
        self.verifier_aucun_secret()

    def test_invitations_et_appareils_reserves_au_responsable(self):
        technicien = self.client.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN)
        demandeur = self.client.connecter("lea.martin", MOT_DE_PASSE_DEMANDEUR)
        cookie_appareil, _ = self.appareil()
        for cookie in (technicien, demandeur, cookie_appareil, None):
            for methode, chemin in (("POST", "/api/acces/invitations"), ("GET", "/api/acces/invitations"),
                                    ("POST", "/api/acces/invitations/INV-0000/revoquer"),
                                    ("POST", "/api/acces/appareils/AP-0000/revoquer"),
                                    ("POST", "/api/acces/appareils/revoquer-tous")):
                with self.subTest(cookie=(cookie or "aucun")[:12], chemin=chemin):
                    reponse = self.client.requete(methode, chemin, b"{}" if methode == "POST" else None, cookie=cookie)
                    if cookie is None:
                        self.assertEqual(reponse.statut, 401, reponse.octets)
                    else:
                        self.assertEqual(reponse.statut, 403, reponse.octets)
                        self.assertEqual(reponse.json()["erreur"], serveur.MESSAGE_RESERVE_AU_RESPONSABLE)
        self.assertEqual(len(self.fichier_appareils()["invitations"]), 1)


class TestEnrolement(CasAppareils):

    def test_un_navigateur_neuf_devient_demandeur_et_cree_une_demande(self):
        jeton = self.inviter()["jeton"]
        reponse = self.enroler(jeton, nom="  Léa   Martin ", agent=AGENT_ANDROID)
        self.assertEqual(reponse.statut, 200, reponse.octets)
        self.assertEqual(reponse.set_cookie.split("; ")[1:], ["Path=/", "HttpOnly", "SameSite=Lax", "Max-Age=31536000"])
        cookie = reponse.cookie
        self.assertRegex(cookie, r"^appareil=[A-Za-z0-9_-]{43}$")
        session = reponse.json()["session"]
        self.assertEqual(reponse.json()["comptes"], True)
        self.assertRegex(session["identifiant"], r"^appareil:AP-[0-9A-F]{4}$")
        self.assertEqual({champ: session[champ] for champ in ("role", "prenom", "nom", "technicien_id", "a_changer",
                                                             "appareil")},
                         {"role": "demandeur", "prenom": "", "nom": "Léa Martin", "technicien_id": "",
                          "a_changer": False, "appareil": True})
        # Le fichier : empreinte seule, libellé d'après le navigateur, nom, dates, l'invitation qui a servi.
        appareil = self.fichier_appareils()["appareils"][0]
        self.assertEqual(appareil["id"], session["identifiant"].split(":", 1)[1])
        self.assertEqual(appareil["empreinte"], empreinte(cookie.split("=", 1)[1]))
        self.assertEqual((appareil["libelle"], appareil["nom_demandeur"]), ("Téléphone ou tablette Android", "Léa Martin"))
        self.assertEqual((appareil["cree_le"], appareil["vu_le"], appareil["revoque"]), (iso(DEPART), iso(DEPART), False))
        self.assertEqual(appareil["invitation"], self.fichier_appareils()["invitations"][0]["id"])
        self.assertEqual([(l["qui"], l["resultat"]) for l in lignes_du_journal(self.donnees)][-1],
                         (session["identifiant"], "appareil"))
        # /api/session le reconnaît et renvoie le cookie pour un an.
        identite = self.client.requete("GET", "/api/session", cookie=cookie)
        self.assertEqual(identite.json()["session"], session)
        self.assertEqual(identite.set_cookie, cookie + "; Path=/; HttpOnly; SameSite=Lax; Max-Age=31536000")
        # Droits du demandeur (D126) : ses tables, une demande créée ; 403 ailleurs.
        self.assertEqual(self.client.requete("GET", "/api/csv/equipements", cookie=cookie).statut, 200)
        versions = self.client.requete("GET", "/api/versions", cookie=cookie).json()["tables"]
        self.assertEqual(set(versions), set(serveur.TABLES_DU_DEMANDEUR) & set(versions))
        self.assertNotIn("ordres_travail", versions)
        ajout = self.client.requete("POST", "/api/csv/demandes/ajout", self.ligne_de_demande(1, "Léa Martin"),
                                    cookie=cookie)
        self.assertEqual(ajout.statut, 200, ajout.octets)
        self.assertIn(b"DI-2026-9001", (self.donnees / "demandes.csv").read_bytes())
        for methode, chemin in (("GET", "/api/csv/techniciens"), ("GET", "/api/csv/ordres_travail"),
                                ("PUT", "/api/csv/equipements"), ("GET", "/api/acces/comptes"),
                                ("POST", "/api/sauvegarde")):
            with self.subTest(chemin=chemin):
                reponse = self.client.requete(methode, chemin, b"{}" if methode != "GET" else None, cookie=cookie)
                self.assertEqual(reponse.statut, 403, reponse.octets)
                self.assertTrue(reponse.json()["erreur"].startswith("Accès refusé"))
        # Un appareil n'a pas de mot de passe ; la déconnexion ne le révoque pas (seul le responsable révoque).
        change = self.client.requete("POST", "/api/mot-de-passe", {"actuel": "a" * 12, "nouveau": "b" * 12}, cookie=cookie)
        self.assertEqual((change.statut, change.json()["erreur"]), (403, serveur.MESSAGE_ACTUEL_FAUX))
        self.assertEqual(self.client.requete("POST", "/api/deconnexion", cookie=cookie).statut, 200)
        self.assertEqual(self.client.session(cookie)["appareil"], True)
        # Usage multiple : un deuxième appareil avec la même invitation, un autre nom, un autre libellé.
        second, session_2 = self.appareil(jeton, nom="Paul Essai", agent=AGENT_IPHONE)
        self.assertNotEqual(second, cookie)
        self.assertNotEqual(session_2["identifiant"], session["identifiant"])
        liste = self.client.requete("GET", "/api/acces/invitations", cookie=self.responsable).json()["appareils"]
        self.assertEqual([(a["libelle"], a["nom_demandeur"], a["valide"]) for a in liste],
                         [("Téléphone ou tablette Android", "Léa Martin", True), ("iPhone", "Paul Essai", True)])
        self.assertTrue(all("empreinte" not in a for a in liste))
        self.verifier_aucun_secret()

    def test_invitation_inconnue_mal_formee_expiree_ou_revoquee(self):
        jeton = self.inviter()["jeton"]
        for invitation in ("x" * 43, "pas un jeton", "", jeton[:-1] + ("A" if jeton[-1] != "A" else "B")):
            with self.subTest(invitation=invitation[:12]):
                reponse = self.enroler(invitation)
                self.assertEqual((reponse.statut, reponse.json()), (401, {"erreur": serveur.MESSAGE_INVITATION_REFUSEE}))
                self.assertNotIn("set-cookie", reponse.entetes)
        for corps in ({"invitation": jeton}, {"invitation": jeton, "nom": "   "}, {"invitation": jeton, "nom": "x" * 61},
                      {"invitation": jeton, "nom": 12}, {"invitation": 12, "nom": "Léa"}):
            with self.subTest(corps=str(corps)[:40]):
                reponse = self.client.requete("POST", "/api/enroler", corps)
                self.assertEqual(reponse.statut, 400, reponse.octets)
        self.assertEqual(self.client.requete("POST", "/api/enroler", {"invitation": jeton, "nom": "Léa"},
                                             prevo=False).statut, 403)
        self.assertEqual(self.fichier_appareils()["appareils"], [])
        # Expirée : 24 h et une seconde plus tard.
        self.serveur.avancer(24 * HEURE)
        self.assertEqual(self.enroler(jeton).statut, 200)
        self.serveur.avancer(1)
        expiree = self.enroler(jeton)
        self.assertEqual((expiree.statut, expiree.json()), (401, {"erreur": serveur.MESSAGE_INVITATION_REFUSEE}))
        liste = self.client.requete("GET", "/api/acces/invitations", cookie=self.responsable_frais()).json()["invitations"]
        self.assertEqual([(i["revoquee"], i["valide"]) for i in liste], [(False, False)])
        # Révoquée : plus personne ne s'enrôle ; 404 pour un id inconnu ; le journal le dit.
        neuve = self.inviter()
        revocation = self.client.requete("POST", "/api/acces/invitations/%s/revoquer" % neuve["invitation"]["id"],
                                         cookie=self.responsable)
        self.assertEqual((revocation.statut, revocation.json()), (200, {"invitation": neuve["invitation"]["id"],
                                                                        "revoquee": True}))
        revoquee = self.enroler(neuve["jeton"])
        self.assertEqual((revoquee.statut, revoquee.json()), (401, {"erreur": serveur.MESSAGE_INVITATION_REFUSEE}))
        self.assertEqual(self.client.requete("POST", "/api/acces/invitations/INV-ZZZZ/revoquer",
                                             cookie=self.responsable).statut, 404)
        self.assertEqual([(l["qui"], l["resultat"]) for l in lignes_du_journal(self.donnees)][-1],
                         ("invitation:" + neuve["invitation"]["id"], "revocation"))
        self.verifier_aucun_secret()


class TestDurees(CasAppareils):

    def test_un_an_glissant_vu_le_une_fois_par_minute(self):
        cookie, session = self.appareil()
        identifiant = session["identifiant"].split(":", 1)[1]

        def vu_le():
            return next(a["vu_le"] for a in self.fichier_appareils()["appareils"] if a["id"] == identifiant)

        self.serveur.avancer(59)
        self.assertEqual(self.client.session(cookie)["appareil"], True)
        self.assertEqual(vu_le(), iso(DEPART))                                   # moins d'une minute : rien réécrit
        self.serveur.avancer(1)
        self.assertEqual(self.client.session(cookie)["appareil"], True)
        self.assertEqual(vu_le(), iso(DEPART + MINUTE))
        # 200 jours plus tard, encore reconnu ; 200 jours après cette activité aussi (glissant) ; un an et un jour
        # après la dernière activité, plus reconnu, cookie effacé.
        self.serveur.avancer(200 * JOUR)
        self.assertEqual(self.client.session(cookie)["appareil"], True)
        self.assertEqual(vu_le(), iso(DEPART + MINUTE + 200 * JOUR))
        self.serveur.avancer(200 * JOUR)
        self.assertEqual(self.client.session(cookie)["appareil"], True)
        self.serveur.avancer(UN_AN + JOUR)
        refuse = self.client.requete("GET", "/api/csv/equipements", cookie=cookie)
        self.assertEqual(refuse.statut, 401)
        self.assertEqual(refuse.json(), {"erreur": serveur.MESSAGE_APPAREIL_REFUSE, "appareil_refuse": True})
        self.assertEqual(refuse.set_cookie, COOKIE_APPAREIL_EFFACE)
        self.assertEqual(self.client.session(cookie), None)
        # Expiré depuis plus de 30 jours : oublié à l'écriture suivante (une invitation neuve).
        self.serveur.avancer(31 * JOUR)
        self.inviter()
        self.assertEqual(self.fichier_appareils()["appareils"], [])
        self.verifier_aucun_secret()

    def test_invitations_finies_oubliees_apres_trente_jours(self):
        premiere = self.inviter({"heures": 1})["invitation"]["id"]
        self.serveur.avancer(HEURE + 29 * JOUR)
        self.inviter()                                                          # écriture : encore gardée
        self.assertIn(premiere, [i["id"] for i in self.fichier_appareils()["invitations"]])
        self.serveur.avancer(JOUR + 1)
        self.inviter()
        self.assertNotIn(premiere, [i["id"] for i in self.fichier_appareils()["invitations"]])
        self.assertEqual(len(self.fichier_appareils()["invitations"]), 2)

    def test_fichier_illisible_aucun_appareil_reconnu_puis_reecrit(self):
        cookie, _ = self.appareil()
        chemin = self.donnees / "acces" / "appareils.json"
        chemin.write_bytes(b"{ pas du json")
        self.assertEqual(self.client.session(cookie), None)
        refuse = self.client.requete("GET", "/api/csv/equipements", cookie=cookie)
        self.assertEqual((refuse.statut, refuse.set_cookie), (401, COOKIE_APPAREIL_EFFACE))
        self.inviter()                                                          # réécrit proprement
        self.assertEqual(self.fichier_appareils()["appareils"], [])
        self.assertEqual(len(self.fichier_appareils()["invitations"]), 1)
        # Éléments de travers : ignorés ; un appareil sans date vaut expiré depuis toujours, oublié à l'écriture.
        chemin.write_text(json.dumps({"invitations": "non", "appareils": [1, "deux", {"id": "AP-0001"}]}), encoding="utf-8")
        self.assertEqual(self.client.session(cookie), None)
        self.inviter()
        self.assertEqual(self.fichier_appareils()["appareils"], [])
        self.assertEqual(len(self.fichier_appareils()["invitations"]), 1)


class TestRevocation(CasAppareils):

    def test_revoquer_un_appareil_le_coupe_aussitot(self):
        cookie, session = self.appareil()
        autre, _ = self.appareil(nom="Paul Essai")
        identifiant = session["identifiant"].split(":", 1)[1]
        self.assertEqual(self.client.requete("GET", "/api/csv/equipements", cookie=cookie).statut, 200)
        revocation = self.client.requete("POST", "/api/acces/appareils/%s/revoquer" % identifiant, cookie=self.responsable)
        self.assertEqual((revocation.statut, revocation.json()), (200, {"appareil": identifiant, "revoque": True}))
        refuse = self.client.requete("GET", "/api/csv/equipements", cookie=cookie)
        self.assertEqual(refuse.statut, 401)
        self.assertEqual(refuse.json(), {"erreur": serveur.MESSAGE_APPAREIL_REFUSE, "appareil_refuse": True})
        self.assertEqual(refuse.set_cookie, COOKIE_APPAREIL_EFFACE)
        self.assertEqual(self.client.session(cookie), None)
        self.assertEqual(self.client.session(autre)["appareil"], True)          # l'autre appareil continue
        liste = self.client.requete("GET", "/api/acces/invitations", cookie=self.responsable).json()["appareils"]
        self.assertEqual([(a["id"] == identifiant, a["revoque"], a["valide"]) for a in liste],
                         [(True, True, False), (False, False, True)])
        journal = [(l["qui"], l["resultat"]) for l in lignes_du_journal(self.donnees)]
        self.assertEqual(journal[-1], ("appareil:" + identifiant, "revocation"))
        self.assertEqual(lignes_du_journal(self.donnees)[-1]["agent"], AGENT_PC)
        # Révoquer deux fois : 200 sans nouvelle ligne ; id inconnu : 404.
        self.assertEqual(self.client.requete("POST", "/api/acces/appareils/%s/revoquer" % identifiant,
                                             cookie=self.responsable).statut, 200)
        self.assertEqual(len(lignes_du_journal(self.donnees)), len(journal))
        self.assertEqual(self.client.requete("POST", "/api/acces/appareils/AP-ZZZZ/revoquer",
                                             cookie=self.responsable).statut, 404)
        # Révoqué depuis plus de 30 jours sans activité : oublié.
        self.serveur.avancer(31 * JOUR)
        self.inviter()
        self.assertEqual([a["id"] == identifiant for a in self.fichier_appareils()["appareils"]], [False])
        self.verifier_aucun_secret()

    def test_revoquer_tous(self):
        cookies = [self.appareil(nom="Appareil %d" % numero)[0] for numero in range(3)]
        ids = [self.client.session(cookie)["identifiant"].split(":", 1)[1] for cookie in cookies]
        reponse = self.client.requete("POST", "/api/acces/appareils/revoquer-tous", cookie=self.responsable)
        self.assertEqual((reponse.statut, sorted(reponse.json()["appareils_revoques"])), (200, sorted(ids)))
        for cookie in cookies:
            self.assertEqual(self.client.requete("GET", "/api/csv/equipements", cookie=cookie).statut, 401)
        self.assertEqual(sorted(l["qui"] for l in lignes_du_journal(self.donnees) if l["resultat"] == "revocation"),
                         sorted("appareil:" + identifiant for identifiant in ids))
        self.assertEqual(self.client.requete("POST", "/api/acces/appareils/revoquer-tous",
                                             cookie=self.responsable).json(), {"appareils_revoques": []})
        self.assertEqual(self.client.session(self.responsable)["role"], "responsable")   # les sessions, elles, restent


class TestDesactive(CasAppareils):

    def test_demandeurs_avec_compte_enrolement_refuse_et_appareils_ignores(self):
        cookie, _ = self.appareil()
        jeton = self.inviter()["jeton"]
        self.serveur.config.reglages["demandeurs_avec_compte"] = True           # Intranet (D124)
        refuse = self.enroler(jeton)
        self.assertEqual((refuse.statut, refuse.json()), (403, {"erreur": serveur.MESSAGE_ENROLEMENT_DESACTIVE}))
        self.assertNotIn("set-cookie", refuse.entetes)
        ignore = self.client.requete("GET", "/api/csv/equipements", cookie=cookie)
        self.assertEqual((ignore.statut, ignore.set_cookie), (401, COOKIE_APPAREIL_EFFACE))
        self.assertEqual(self.client.session(cookie), None)
        liste = self.client.requete("GET", "/api/acces/invitations", cookie=self.responsable).json()
        self.assertEqual((liste["enrolement_actif"], len(liste["appareils"])), (False, 1))
        self.serveur.config.reglages["demandeurs_avec_compte"] = False
        self.assertEqual(self.client.session(cookie)["appareil"], True)         # rien n'a été effacé côté serveur


class TestSansComptes(CasAppareils):

    REGLAGES = {"comptes": False}

    def test_sans_comptes_400_clair(self):
        for methode, chemin in (("POST", "/api/enroler"), ("GET", "/api/acces/invitations"),
                                ("POST", "/api/acces/invitations"), ("POST", "/api/acces/appareils/revoquer-tous")):
            with self.subTest(chemin=chemin):
                reponse = self.client.requete(methode, chemin, {"invitation": "x" * 43, "nom": "Léa"}
                                              if methode == "POST" else None)
                self.assertEqual((reponse.statut, reponse.json()), (400, {"erreur": serveur.MESSAGE_SANS_COMPTES}))
        self.assertFalse((self.donnees / "acces" / "appareils.json").exists())


if __name__ == "__main__":
    unittest.main()
