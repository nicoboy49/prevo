"""Lot 7 — rôles vérifiés par le serveur (ARCHITECTURE.md §22.5 ; D126, D114, D125 ; CS122 ; tâche T152).

Ce qui est vérifié :
    table          ROLES_PAR_ROUTE de serveur.py a une ligne par route de ROUTES_API, comme ATTENDU, la table du
                   contrat recopiée ici ; la table de §22.5 de docs/ARCHITECTURE.md dit la même chose qu'ATTENDU ;
    cases          chaque case route × rôle d'ATTENDU (jamais déduite du code) rend 403 « Accès refusé… » ou 200/201 :
                   trois vraies sessions (demandeur, technicien, responsable) sur un serveur réel, et l'appareil enrôlé
                   (D125, T153) par une identité simulée dans un serveur du processus ; les 24 tables pour csv/<table>,
                   une photo de demande, un document d'équipement et un autre document pour documents/<nom> ;
    technicien     ni taux_horaire (techniciens) ni prix_unitaire (articles, achats) dans les octets reçus, en-tête
                   compris, X-Version voilée (T506 : jamais l'empreinte du fichier) ; à l'écriture, prix remis depuis le fichier (gardés, prix
                   forgé ignoré, ligne nouvelle sans prix) et colonne stock bien écrite ; ajout : colonne vidée ;
                   equipements reçu avec cout_arret_h vidé, nom gardé dans l'en-tête (T473) ;
    demandeur      liste fermée (techniciens.csv jamais reçu), /api/versions réduit à ses tables, wiki_pages sans pages
                   Technicien ni Intervention (D114) ; demandes en ajout seulement (ajout permis ; modification,
                   suppression, décision, numéro pris refusés ; version périmée toujours 409 ; demande récrite par
                   Excel reconnue et gardée telle quelle) ; documents : photos de demandes et documents des
                   équipements lus, seule la photo d'une demande s'envoie ;
    comptes        routes du responsable : liste sans empreinte ni sel, création et réinitialisation avec un mot de
                   passe provisoire rendu une seule fois (jamais dans un fichier, le journal ou la console),
                   modifier, désactiver, activer, dernier responsable gardé, journal des connexions en CSV ;
    sans comptes   rien ne change (colonnes, versions, écritures) et les routes des comptes répondent 400 ;
    navigateur     Signaler une demande avec photo en mode comptes (session posée en cookie, demandeur), écrans du
                   demandeur sans erreur ; sortie d'une pièce par le technicien (stock recopié, prix gardés).

Aucune commande d'administrateur, aucune sortie réseau (faux fournisseur d'IA sur 127.0.0.1).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_acces_roles.py" -v
"""
import csv
import hashlib
import http.client
import importlib.util
import io
import json
import re
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import urlsplit

import commun
from commun import RACINE, CasNavigateur, attendre_pret, preregler_profil
from faux_fournisseur_ia import FauxFournisseur
from test_demandes import MOTIF_PHOTO, fichier_png

SCRIPT = RACINE / "serveur.py"
CONTRAT = RACINE / "docs" / "ARCHITECTURE.md"


def charger_serveur():
    specification = importlib.util.spec_from_file_location("serveur_prevo_roles", SCRIPT)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


serveur = charger_serveur()

# ---------------------------------------------------------------------------
# Table du contrat (ARCHITECTURE.md §22.5), recopiée : l'attendu ne vient jamais de serveur.py
# ---------------------------------------------------------------------------

OUI, NON = "oui", "non"
ROLES = ("demandeur", "appareil", "technicien", "responsable")
TOUTES_LES_TABLES = frozenset(serveur.TABLES)
TABLES_DU_DEMANDEUR = frozenset({"localisations", "equipements", "demandes", "compteurs", "releves",
                                 "codes_defaillance", "parametres", "wiki_pages"})
# habilitations : T445, D195 ; documents réservés : tests/test_droits_format4.py.
# reserves_controle, garanties, contrats_prestataires : T453 (décidé, L4-L6 Q6) ; tests/test_garanties_serveur.py.
ECRITURE_DU_TECHNICIEN = TOUTES_LES_TABLES - {"parametres", "techniciens", "fournisseurs", "reserves_controle",
                                              "garanties", "contrats_prestataires", "habilitations"}
PHOTOS = "photos de demandes"
PHOTOS_ET_EQUIPEMENTS = "photos de demandes, documents des équipements"
TOUS = (OUI, OUI, OUI, OUI)
RESPONSABLE = (NON, NON, NON, OUI)
INTERVENANTS = (NON, NON, OUI, OUI)

ATTENDU = {
    # route                                        demandeur, appareil, technicien, responsable
    ("GET", "ping"): TOUS,
    ("GET", "session"): TOUS,
    ("POST", "connexion"): TOUS,
    ("POST", "deconnexion"): TOUS,
    ("POST", "mot-de-passe"): TOUS,
    ("GET", "info"): TOUS,
    ("GET", "versions"): TOUS,
    ("POST", "acces/deconnecter-partout"): TOUS,
    ("GET", "acces/comptes"): RESPONSABLE,
    ("POST", "acces/comptes"): RESPONSABLE,
    ("POST", "acces/comptes/<identifiant>"): RESPONSABLE,
    ("GET", "acces/journal"): RESPONSABLE,
    ("POST", "enroler"): TOUS,
    ("GET", "acces/invitations"): RESPONSABLE,
    ("POST", "acces/invitations"): RESPONSABLE,
    ("POST", "acces/invitations/<id>/revoquer"): RESPONSABLE,
    ("POST", "acces/appareils/<id>/revoquer"): RESPONSABLE,
    ("POST", "acces/appareils/revoquer-tous"): RESPONSABLE,
    ("GET", "csv/<table>"): (TABLES_DU_DEMANDEUR, TABLES_DU_DEMANDEUR, OUI, OUI),
    ("PUT", "csv/<table>"): (frozenset({"demandes"}), frozenset({"demandes"}), ECRITURE_DU_TECHNICIEN, OUI),
    ("POST", "csv/<table>/ajout"): (frozenset({"demandes", "journal"}), frozenset({"demandes", "journal"}),
                                    ECRITURE_DU_TECHNICIEN, OUI),
    ("GET", "documents/<nom>"): (PHOTOS_ET_EQUIPEMENTS, PHOTOS_ET_EQUIPEMENTS, OUI, OUI),
    ("PUT", "documents/<nom>"): (PHOTOS, PHOTOS, OUI, OUI),
    ("POST", "sauvegarde"): RESPONSABLE,
    ("POST", "sauvegarde/tester"): RESPONSABLE,
    ("GET", "sauvegardes"): RESPONSABLE,
    ("POST", "restauration"): RESPONSABLE,
    ("POST", "ia"): INTERVENANTS,
    ("GET", "ia/reglages"): INTERVENANTS,
    ("GET", "installation/<etape>"): RESPONSABLE,       # T167 (§22.10) : et PC serveur seulement, 404 au réseau
    ("POST", "installation/<etape>"): RESPONSABLE,
}


def permis(regle, genre):
    """Case permise d'après la règle d'ATTENDU ; genre : la table, ou la sorte du document (photo, equipement, autre)."""
    if regle == OUI:
        return True
    if regle == NON:
        return False
    if isinstance(regle, frozenset):
        return genre in regle
    if regle == PHOTOS:
        return genre == "photo"
    if regle == PHOTOS_ET_EQUIPEMENTS:
        return genre in ("photo", "equipement")
    raise AssertionError("règle inconnue : %r" % (regle,))


def regle_du_contrat(cellule, tables_du_demandeur):
    """Une case de la table de §22.5 → règle d'ATTENDU."""
    noms = frozenset(re.findall(r"`([a-z_]+)`", cellule))
    if cellule.startswith("oui"):
        return OUI
    if cellule.startswith("non"):
        return NON
    if cellule.startswith("toutes sauf"):
        return TOUTES_LES_TABLES - noms
    if cellule.startswith("toutes"):
        return OUI
    if cellule.startswith("tables du demandeur"):
        return tables_du_demandeur
    if cellule.startswith(PHOTOS_ET_EQUIPEMENTS):
        return PHOTOS_ET_EQUIPEMENTS
    if cellule.startswith(PHOTOS):
        return PHOTOS
    if noms:
        return noms
    raise AssertionError("case du contrat illisible : %r" % cellule)


def table_du_contrat():
    """({route: (demandeur, appareil, technicien, responsable)}, tables du demandeur) lus dans §22.5 du contrat."""
    texte = CONTRAT.read_text(encoding="utf-8")
    debut = texte.index("### 22.5 ")
    section = texte[debut:texte.index("\n### ", debut + 1)]
    liste = re.search(r"^Tables du demandeur : (.+)$", section, re.MULTILINE)
    tables_du_demandeur = frozenset(re.findall(r"`([a-z_]+)`", liste.group(1)))
    table = {}
    for ligne in section.splitlines():
        if not ligne.startswith("| `"):
            continue
        cellules = [cellule.strip() for cellule in ligne.strip().strip("|").split("|")]
        methode, chemin = cellules[0].strip("`").split(" ", 1)
        table[(methode, chemin[len("/api/"):])] = tuple(regle_du_contrat(cellule, tables_du_demandeur)
                                                         for cellule in cellules[1:])
    return table, tables_du_demandeur


# ---------------------------------------------------------------------------
# Données d'essai : comptes, documents, CSV
# ---------------------------------------------------------------------------

MOTS_DE_PASSE = {
    "nicolas.briand": "phrase du responsable 2026",
    "julien.moreau": "cle a molette et graisse",
    "lea.martin": "une demande de lea 2026",
    "paul.essai": "compte jetable pour les essais",
}
SESSIONS = {"demandeur": "lea.martin", "technicien": "julien.moreau", "responsable": "nicolas.briand"}
AGENT = "Navigateur-de-test/1.0"
BOM = bytes((0xEF, 0xBB, 0xBF))
JPEG = bytes((0xFF, 0xD8, 0xFF, 0xE0, 0, 16)) + b"JFIF" + bytes(64) + bytes((0xFF, 0xD9))
PDF = b"%PDF-1.4 essai\n"
PHOTO = "photo-20261020-101500-ABCD.jpg"
DOCUMENT_EQUIPEMENT = "notice-po02.pdf"
AUTRE_DOCUMENT = "controle-vgp_20260901-100000_x1y2.pdf"
EQUIPEMENT_DU_DOCUMENT = "EQ-0005"
PAGES_RESERVEES = {"WP-9001": "technicien", "WP-9002": "intervention"}
OT_EN_COURS = "OT-2026-0212"
ARTICLE = "ART-0001"
JETON_APPAREIL = "appareil-essai-" + "x" * 30
IDENTITE_APPAREIL = {"identifiant": "appareil:ap-0001", "role": "demandeur", "prenom": "", "nom": "Poste du quai",
                     "technicien_id": "", "a_changer": False, "appareil": True, "cle": "appareil-essai",
                     "longue": True}
COMPTES_JSON = b""


def setUpModule():
    """Quatre comptes créés une fois (scrypt coûte), recopiés dans chaque dossier de données : nicolas.briand
    (responsable), julien.moreau (technicien lié à TEC-0001), lea.martin et paul.essai (demandeurs)."""
    global COMPTES_JSON
    dossier = Path(tempfile.mkdtemp(prefix="prevo-roles-modele-"))
    try:
        config = serveur.Configuration(str(dossier / "donnees"), [])
        serveur.creer_dossiers(config)
        serveur.creer_compte(config, "Nicolas", "Briand", "responsable", MOTS_DE_PASSE["nicolas.briand"])
        serveur.creer_compte(config, "Julien", "Moreau", "technicien", MOTS_DE_PASSE["julien.moreau"],
                             technicien_id="TEC-0001")
        serveur.creer_compte(config, "Léa", "Martin", "demandeur", MOTS_DE_PASSE["lea.martin"])
        serveur.creer_compte(config, "Paul", "Essai", "demandeur", MOTS_DE_PASSE["paul.essai"])
        COMPTES_JSON = (dossier / "donnees" / "acces" / "comptes.json").read_bytes()
    finally:
        shutil.rmtree(dossier, ignore_errors=True)


def version_de(octets):
    return hashlib.sha256(octets).hexdigest()[:16]


def lire_tableau(octets):
    """(en-tête, lignes) d'un CSV de Prévo (BOM, « ; »), valeurs telles qu'écrites (apostrophes comprises)."""
    lignes = [ligne for ligne in csv.reader(io.StringIO(octets.decode("utf-8-sig"), newline=""), delimiter=";") if ligne]
    return lignes[0], lignes[1:]


def cellule(texte):
    """Comme celluleCsv de js/donnees.js (§3.1)."""
    return '"' + texte.replace('"', '""') + '"' if re.search(r'[;"\r\n]|\A[ \t]|[ \t]\Z', texte) else texte


def ecrire_tableau(entete, lignes, bom=True):
    texte = "".join(";".join(cellule(valeur) for valeur in ligne) + "\r\n" for ligne in [entete] + list(lignes))
    return (BOM if bom else b"") + texte.encode("utf-8")


def premiere_ligne(octets):
    """Ligne d'en-tête d'un fichier (sans BOM ni fin de ligne), en octets : début d'un corps d'ajout."""
    return octets[len(BOM):].split(b"\n", 1)[0].rstrip(b"\r") if octets.startswith(BOM) else octets.split(b"\n", 1)[0]


def preparer_source(racine, pages_reservees=False):
    """Copie de la démo avec les comptes, trois documents (une photo de demande, la notice de EQ-0005 citée dans
    equipements.csv, un autre document) et, sur demande, deux pages réservées dans wiki_pages ; configuration à
    « comptes ». Rend (dossier source, fichier de configuration)."""
    source = racine / "source"
    shutil.copytree(commun.DOSSIER_DEMO, source)
    (source / "acces").mkdir()
    (source / "acces" / "comptes.json").write_bytes(COMPTES_JSON)
    documents = source / "documents"
    documents.mkdir(exist_ok=True)
    (documents / PHOTO).write_bytes(JPEG)
    (documents / DOCUMENT_EQUIPEMENT).write_bytes(PDF)
    (documents / AUTRE_DOCUMENT).write_bytes(PDF)
    entete, lignes = lire_tableau((source / "equipements.csv").read_bytes())
    for ligne in lignes:
        if ligne[0] == EQUIPEMENT_DU_DOCUMENT:
            ligne[entete.index("document")] = DOCUMENT_EQUIPEMENT
    (source / "equipements.csv").write_bytes(ecrire_tableau(entete, lignes))
    if pages_reservees:
        entete, lignes = lire_tableau((source / "wiki_pages.csv").read_bytes())
        for identifiant, type_page in PAGES_RESERVEES.items():
            valeurs = {"id": identifiant, "type": type_page, "titre": "Page réservée " + identifiant,
                       "cle": "page reservee " + identifiant.lower(), "texte": "Réservée.", "version": "1",
                       "origine": "manuel", "statut": "active"}
            lignes.append([valeurs.get(nom, "") for nom in entete])
        (source / "wiki_pages.csv").write_bytes(ecrire_tableau(entete, lignes))
    configuration = racine / "prevo.config.json"
    configuration.write_text(json.dumps({"comptes": True, "demandeurs_avec_compte": True}), encoding="utf-8")
    return source, configuration


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

    def refus_de_role(self):
        """Vrai pour le 403 de verifier_role (« Accès refusé… »), pas un autre 403 (X-Prevo, mot de passe…)."""
        if self.statut != 403:
            return False
        try:
            return self.json()["erreur"].startswith("Accès refusé")
        except (ValueError, KeyError):
            return False


class Client:
    """Requêtes vers un serveur Prévo, une connexion par requête ; le cookie se passe à la main."""

    def __init__(self, url):
        morceaux = urlsplit(url)
        self.hote, self.port = morceaux.hostname, morceaux.port

    def requete(self, methode, chemin, corps=None, cookie=None, entetes=None, prevo=True):
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
        connexion = http.client.HTTPConnection(self.hote, self.port, timeout=60)
        try:
            connexion.request(methode, chemin, body=corps, headers=entetes)
            reponse = connexion.getresponse()
            return Reponse(reponse.status, {nom.lower(): valeur for nom, valeur in reponse.getheaders()}, reponse.read())
        finally:
            connexion.close()

    def connecter_brut(self, identifiant, mot_de_passe=None):
        return self.requete("POST", "/api/connexion", {"identifiant": identifiant, "rester": False,
                                                       "mot_de_passe": mot_de_passe or MOTS_DE_PASSE[identifiant]})

    def connecter(self, identifiant, mot_de_passe=None):
        reponse = self.connecter_brut(identifiant, mot_de_passe)
        if reponse.statut != 200:
            raise AssertionError("connexion de %s refusée : %r" % (identifiant, reponse.octets))
        return reponse.cookie


def lancer_serveur_comptes(cls, pages_reservees=False):
    """Serveur réel (ServeurPrevo de tests/commun.py) sur la copie préparée, --config à « comptes », faux fournisseur
    d'IA local ; une session par rôle dans cls.cookies, une sauvegarde à motif dans cls.sauvegarde."""
    cls.racine = Path(tempfile.mkdtemp(prefix="prevo-roles-"))
    cls.addClassCleanup(shutil.rmtree, cls.racine, True)
    cls.faux = FauxFournisseur()
    cls.faux.demarrer()
    cls.addClassCleanup(cls.faux.arreter)
    source, configuration = preparer_source(cls.racine, pages_reservees)
    cls.serveur = commun.ServeurPrevo(source=source, arguments=["--config", str(configuration),
                                                                "--ia-url", cls.faux.url])
    cls.serveur.demarrer()
    cls.addClassCleanup(cls.serveur.arreter)
    cls.client = Client(cls.serveur.url)
    cls.cookies = {role: cls.client.connecter(identifiant) for role, identifiant in SESSIONS.items()}
    cls.sauvegarde = cls.client.requete("POST", "/api/sauvegarde", {"motif": "avant-import"},
                                        cookie=cls.cookies["responsable"]).json()["sauvegarde"]


# ---------------------------------------------------------------------------
# Table : une ligne par route, contrat et test d'accord
# ---------------------------------------------------------------------------

class TestTableDesRoles(unittest.TestCase):

    def test_chaque_route_a_sa_ligne_dans_le_code_et_dans_le_contrat(self):
        self.assertEqual(set(serveur.ROLES_PAR_ROUTE), set(serveur.ROUTES_API))
        self.assertEqual(set(ATTENDU), set(serveur.ROUTES_API))
        self.assertEqual(tuple(serveur.ORDRE_DES_ROLES), ROLES)
        for route, regles in serveur.ROLES_PAR_ROUTE.items():
            with self.subTest(route=route):
                self.assertEqual(len(regles), len(ROLES))

    def test_la_table_du_contrat_est_celle_du_test(self):
        table, tables_du_demandeur = table_du_contrat()
        self.assertEqual(tables_du_demandeur, TABLES_DU_DEMANDEUR)
        self.assertEqual(set(table), set(ATTENDU))
        for route, regles in ATTENDU.items():
            with self.subTest(route=route):
                self.assertEqual(table[route], regles)
        self.assertNotIn("techniciens", TABLES_DU_DEMANDEUR)            # CS122 : jamais techniciens.csv


# ---------------------------------------------------------------------------
# Chaque case : trois sessions réelles, puis l'appareil enrôlé
# ---------------------------------------------------------------------------

class JoueurDeCases:
    """Joue chaque case d'ATTENDU pour un rôle. Il faut : self.client, self.cookies (rôle → cookie), self.sauvegarde,
    dossier_donnees() ; les routes qui ferment des sessions (mot de passe, déconnecter partout) passent en dernier."""

    FERMENT_LA_SESSION = (("POST", "mot-de-passe"), ("POST", "acces/deconnecter-partout"))
    numero = 0

    def dossier_donnees(self):
        return self.serveur.dossier

    def identifiant_de(self, role):
        return SESSIONS.get(role, "lea.martin")

    @staticmethod
    def segments_de(route):
        """[(segment du chemin, genre)] à essayer : chaque table, chaque sorte de document, ou rien."""
        methode, motif = route
        if "<table>" in motif:
            return [(table, table) for table in serveur.TABLES]
        if motif == "documents/<nom>" and methode == "GET":
            return [(PHOTO, "photo"), (DOCUMENT_EQUIPEMENT, "equipement"), (AUTRE_DOCUMENT, "autre")]
        if motif == "documents/<nom>":
            return [(None, "photo"), (None, "autre")]
        if motif == "acces/comptes/<identifiant>":
            return [("paul.essai", None)]
        if "<id>" in motif:
            return [("INV-0000" if "invitations" in motif else "AP-0000", None)]
        if "<etape>" in motif:
            return [("etat" if methode == "GET" else "situation", None)]
        return [(None, None)]

    @classmethod
    def nouveau_nom(cls, genre):
        JoueurDeCases.numero += 1
        if genre == "photo":
            return "photo-20261026-%06d-ESSA.jpg" % JoueurDeCases.numero
        return "essai-case-%d.pdf" % JoueurDeCases.numero

    def jouer_les_cases(self, role):
        colonne = ROLES.index(role)
        routes = sorted(ATTENDU, key=lambda route: route in self.FERMENT_LA_SESSION)
        jouees = 0
        for route in routes:
            regle = ATTENDU[route][colonne]
            for segment, genre in self.segments_de(route):
                with self.subTest(role=role, route="%s %s" % route, segment=segment or genre):
                    reponse, statuts = self.jouer(role, route, segment, genre, permis(regle, genre))
                    jouees += 1
                    if permis(regle, genre):
                        self.assertIn(reponse.statut, statuts, reponse.octets[:300])
                        self.assertFalse(reponse.refus_de_role(), reponse.octets[:300])
                    else:
                        self.assertEqual(reponse.statut, 403, reponse.octets[:300])
                        self.assertTrue(reponse.refus_de_role(), reponse.octets[:300])
        self.assertGreaterEqual(jouees, 3 * len(serveur.TABLES) + len(ATTENDU))

    def jouer(self, role, route, segment, genre, permise=True):
        """Une requête de la case ; rend (réponse, statuts attendus si la case est permise). Case refusée : un petit
        corps, car un refus prononcé avant la lecture ferme la connexion au-delà de 64 Ko (audit F2, §22.4)."""
        methode, motif = route
        cookie = self.cookies[role]
        if route == ("POST", "connexion"):
            return self.client.connecter_brut(self.identifiant_de(role)), (200,)
        if route == ("POST", "deconnexion"):
            return self.client.requete("POST", "/api/deconnexion", cookie=self.session_jetable(role)), (200,)
        if route == ("POST", "mot-de-passe"):
            return self.changer_et_rechanger(role)
        if route == ("POST", "acces/deconnecter-partout"):
            reponse = self.client.requete("POST", "/api/acces/deconnecter-partout", cookie=cookie)
            self.reconnecter(role)
            return reponse, (200,)
        dossier = self.dossier_donnees()
        chemin = "/api/" + re.sub(r"<[a-z]+>", segment or "", motif)
        corps, entetes, statuts = None, {}, (200,)
        if motif == "csv/<table>" and methode == "PUT":
            octets = (dossier / (segment + ".csv")).read_bytes()
            corps = octets if permise else BOM + premiere_ligne(octets) + b"\r\n"
            # T506 : la version que ce rôle lit (voilée s'il n'a pas toutes les colonnes) ; table non lue : refus.
            listees = self.client.requete("GET", "/api/versions", cookie=cookie).json()["tables"]
            entetes = {"X-Version-Attendue": (listees.get(segment) or {}).get("version") or version_de(octets)}
        elif motif == "csv/<table>/ajout":
            corps = premiere_ligne((dossier / (segment + ".csv")).read_bytes()) + b"\r\n"
        elif motif == "documents/<nom>":
            chemin = "/api/documents/" + (segment or self.nouveau_nom(genre))
            if methode == "PUT":
                corps, statuts = (JPEG if genre == "photo" else PDF), (201,)
        elif route == ("POST", "sauvegarde"):
            corps = {"motif": "avant-import"}
        elif route == ("POST", "sauvegarde/tester"):
            corps = {"nom": self.sauvegarde}
        elif route == ("POST", "restauration"):
            corps = {"sauvegarde": self.sauvegarde, "tables": ["localisations"]}
        elif route == ("POST", "ia"):
            corps = {"chemin": "api/tags", "methode": "GET"}
        elif route == ("POST", "acces/comptes"):
            JoueurDeCases.numero += 1
            corps = {"prenom": "Essai", "nom": "Case %d" % JoueurDeCases.numero, "role": "demandeur"}
        elif route == ("POST", "acces/comptes/<identifiant>"):
            corps = {"action": "modifier", "prenom": "Paul"}
        elif route == ("POST", "installation/<etape>"):
            corps = {"situation": "seul"}               # T167 : brouillon réécrit dans la copie, rien d'autre
        elif route == ("POST", "enroler"):
            # Route publique (T153) : l'invitation décide. Serveur réel, demandeurs_avec_compte vrai : 403 enrôlement
            # désactivé ; serveur du processus (appareil simulé) : 401 invitation inconnue. Ni l'un ni l'autre n'est
            # un refus de rôle (« Accès refusé »).
            corps, statuts = {"invitation": "x" * 43, "nom": "Essai"}, (401, 403)
        elif "<id>" in motif:
            statuts = (404,)                    # la route est passée : l'id d'essai est inconnu
        return self.client.requete(methode, chemin, corps, cookie=cookie, entetes=entetes), statuts

    def session_jetable(self, role):
        return self.client.connecter(self.identifiant_de(role))

    def reconnecter(self, role):
        self.cookies[role] = self.client.connecter(self.identifiant_de(role))

    def changer_et_rechanger(self, role):
        """Mot de passe changé puis remis (chaque changement ferme les autres sessions du compte) ; 200 attendu."""
        identifiant = self.identifiant_de(role)
        actuel, autre = MOTS_DE_PASSE[identifiant], MOTS_DE_PASSE[identifiant] + " bis"
        aller = self.client.requete("POST", "/api/mot-de-passe", {"actuel": actuel, "nouveau": autre},
                                    cookie=self.cookies[role])
        if aller.statut != 200:
            return aller, (200,)
        retour = self.client.requete("POST", "/api/mot-de-passe", {"actuel": autre, "nouveau": actuel},
                                     cookie=aller.cookie)
        self.cookies[role] = retour.cookie or aller.cookie
        return retour, (200,)


class TestCasesDesRoles(JoueurDeCases, unittest.TestCase):
    """Trois vraies sessions (demandeur, technicien, responsable) sur un serveur réel en mode comptes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        lancer_serveur_comptes(cls)

    def test_cases_du_demandeur(self):
        self.jouer_les_cases("demandeur")

    def test_cases_du_responsable(self):
        self.jouer_les_cases("responsable")

    def test_cases_du_technicien(self):
        self.jouer_les_cases("technicien")


class TestCasesDeLAppareil(JoueurDeCases, unittest.TestCase):
    """Appareil enrôlé (D125) : l'enrôlement arrive avec T153 ; d'ici là, son identité (rôle demandeur, appareil vrai)
    est rendue par une verifier_session simulée, dans un serveur du processus. Mêmes cases, mêmes attendus que le
    demandeur. Mot de passe : un appareil n'en a pas ; la route lui est ouverte comme au demandeur, le refus vient alors
    du mot de passe actuel (403 « Mot de passe actuel incorrect. »), jamais du rôle."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.racine = Path(tempfile.mkdtemp(prefix="prevo-roles-appareil-"))
        cls.addClassCleanup(shutil.rmtree, cls.racine, True)
        cls.faux = FauxFournisseur()
        cls.faux.demarrer()
        cls.addClassCleanup(cls.faux.arreter)
        source, _ = preparer_source(cls.racine)
        cls.donnees = cls.racine / "donnees"
        shutil.copytree(source, cls.donnees)
        config = serveur.Configuration(str(cls.donnees), [])
        config.reglages.update({"comptes": True, "ia_url": cls.faux.url})
        serveur.creer_dossiers(config)
        reelle = serveur.verifier_session

        def verifier_session(configuration, entete_cookie):
            if entete_cookie and ("id=" + JETON_APPAREIL) in entete_cookie:
                return dict(IDENTITE_APPAREIL)
            return reelle(configuration, entete_cookie)

        for remplacement in (mock.patch.object(serveur, "verifier_session", side_effect=verifier_session),
                             mock.patch.object(serveur, "afficher")):
            remplacement.start()
            cls.addClassCleanup(remplacement.stop)
        cls.http = serveur.ServeurPrevo(("127.0.0.1", 0), config)
        config.port = cls.http.server_address[1]
        fil = threading.Thread(target=cls.http.serve_forever, daemon=True)
        fil.start()

        def arreter():
            cls.http.shutdown()
            cls.http.server_close()
            fil.join(timeout=5)

        cls.addClassCleanup(arreter)
        cls.client = Client("http://127.0.0.1:%d" % config.port)
        cls.cookies = {"appareil": "id=" + JETON_APPAREIL, "responsable": cls.client.connecter("nicolas.briand")}
        cls.sauvegarde = cls.client.requete("POST", "/api/sauvegarde", {"motif": "avant-import"},
                                            cookie=cls.cookies["responsable"]).json()["sauvegarde"]

    def dossier_donnees(self):
        return self.donnees

    def session_jetable(self, role):
        return self.cookies[role]

    def reconnecter(self, role):
        pass                                    # l'identité simulée de l'appareil n'a pas de session à rouvrir

    def changer_et_rechanger(self, role):
        reponse = self.client.requete("POST", "/api/mot-de-passe", {"actuel": "a" * 12, "nouveau": "b" * 12},
                                      cookie=self.cookies[role])
        self.assertEqual(reponse.json(), {"erreur": serveur.MESSAGE_ACTUEL_FAUX,
                                          "erreur_code": "sessions.mot_de_passe_actuel_faux"})
        return reponse, (403,)

    def test_cases_de_l_appareil(self):
        self.assertEqual(self.client.requete("GET", "/api/session", cookie=self.cookies["appareil"]).json()["session"]
                         ["appareil"], True)
        self.jouer_les_cases("appareil")


# ---------------------------------------------------------------------------
# Technicien : colonnes retirées à la lecture, remises à l'écriture (D126)
# ---------------------------------------------------------------------------

class TestTechnicien(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        lancer_serveur_comptes(cls)

    def lire(self, table, role="technicien"):
        reponse = self.client.requete("GET", "/api/csv/" + table, cookie=self.cookies[role])
        self.assertEqual(reponse.statut, 200, reponse.octets[:200])
        return reponse

    def test_ni_taux_horaire_ni_prix_a_la_lecture_et_version_du_fichier_entier(self):
        for table, colonne in (("techniciens", "taux_horaire"), ("articles", "prix_unitaire"),
                               ("achats", "prix_unitaire")):
            with self.subTest(table=table):
                disque = (self.serveur.dossier / (table + ".csv")).read_bytes()
                entete, lignes = lire_tableau(disque)
                position = entete.index(colonne)
                recu = self.lire(table)
                self.assertNotEqual(recu.entetes["x-version"], version_de(disque))      # T506 : version voilée
                self.assertTrue(recu.octets.startswith(BOM))
                entete_recu, lignes_recues = lire_tableau(recu.octets)
                self.assertNotIn(colonne, entete_recu)
                self.assertNotIn(colonne.encode("ascii"), recu.octets)
                self.assertEqual(entete_recu, entete[:position] + entete[position + 1:])
                self.assertEqual(lignes_recues, [ligne[:position] + ligne[position + 1:] for ligne in lignes])
                self.assertEqual(self.lire(table, "responsable").octets, disque)        # le responsable : tout
        for table in ("ordres_travail", "parametres", "mouvements_stock"):
            with self.subTest(table=table):
                self.assertEqual(self.lire(table).octets, (self.serveur.dossier / (table + ".csv")).read_bytes())
        # equipements : cout_arret_h gardé dans l'en-tête, valeurs vidées (T473, tests/test_cout_arret_serveur.py).
        disque = (self.serveur.dossier / "equipements.csv").read_bytes()
        entete, lignes = lire_tableau(disque)
        position = entete.index("cout_arret_h")
        self.assertTrue(any(ligne[position] for ligne in lignes))               # la démo chiffre des équipements
        recu = self.lire("equipements")
        self.assertNotEqual(recu.entetes["x-version"], version_de(disque))              # T506 : version voilée
        self.assertEqual(lire_tableau(recu.octets), (entete, [ligne[:position] + [""] + ligne[position + 1:]
                                                              for ligne in lignes]))

    def test_prix_remis_a_l_ecriture_ligne_nouvelle_sans_prix_et_stock_ecrit(self):
        chemin = self.serveur.dossier / "articles.csv"
        entete, lignes = lire_tableau(chemin.read_bytes())
        p_prix, p_stock = entete.index("prix_unitaire"), entete.index("stock")
        prix_avant = {ligne[0]: ligne[p_prix] for ligne in lignes}
        recu = self.lire("articles")
        _, lignes_recues = lire_tableau(recu.octets)
        # Comme Donnees.modifier dans le navigateur : toutes les colonnes du schéma, le prix vide (jamais reçu).
        envoyees = [ligne[:p_prix] + [""] + ligne[p_prix:] for ligne in lignes_recues]
        cible, forgee = envoyees[0], envoyees[1]
        nouveau_stock = str(int(cible[p_stock]) + 3)
        cible[p_stock] = nouveau_stock
        forgee[p_prix] = "0.01"                                                 # prix forgé sur une ligne existante
        nouvelle = [""] * len(entete)
        for nom, valeur in (("id", "ART-9999"), ("reference", "ESSAI-T152"), ("designation", "Article du technicien"),
                            ("prix_unitaire", "999"), ("stock", "0"), ("actif", "1")):
            nouvelle[entete.index(nom)] = valeur
        reponse = self.client.requete("PUT", "/api/csv/articles", ecrire_tableau(entete, envoyees + [nouvelle]),
                                      cookie=self.cookies["technicien"],
                                      entetes={"X-Version-Attendue": recu.entetes["x-version"]})
        self.assertEqual(reponse.statut, 200, reponse.octets)
        apres = chemin.read_bytes()
        self.assertNotEqual(reponse.json()["version"], version_de(apres))        # T506 : version voilée
        entete_apres, lignes_apres = lire_tableau(apres)
        self.assertEqual(entete_apres, entete)
        par_id = {ligne[0]: ligne for ligne in lignes_apres}
        for identifiant, prix in prix_avant.items():
            self.assertEqual(par_id[identifiant][p_prix], prix, identifiant)     # prix gardés, le forgé compris
        self.assertEqual(par_id[cible[0]][p_stock], nouveau_stock)              # colonne stock bien écrite
        self.assertEqual(par_id["ART-9999"][p_prix], "")                        # ligne nouvelle : prix vide
        relu = self.lire("articles")
        self.assertEqual(relu.entetes["x-version"], reponse.json()["version"])   # la surveillance reste d'accord
        self.assertNotIn("prix_unitaire", lire_tableau(relu.octets)[0])
        # achats : un prix forgé n'est pas écrit non plus
        chemin_achats = self.serveur.dossier / "achats.csv"
        entete_a, lignes_a = lire_tableau(chemin_achats.read_bytes())
        p_prix_a = entete_a.index("prix_unitaire")
        recu_a = self.lire("achats")
        envoyees_a = [ligne[:p_prix_a] + ["1"] + ligne[p_prix_a:] for ligne in lire_tableau(recu_a.octets)[1]]
        reponse = self.client.requete("PUT", "/api/csv/achats", ecrire_tableau(entete_a, envoyees_a),
                                      cookie=self.cookies["technicien"],
                                      entetes={"X-Version-Attendue": recu_a.entetes["x-version"]})
        self.assertEqual(reponse.statut, 200, reponse.octets)
        self.assertEqual(lire_tableau(chemin_achats.read_bytes())[1], lignes_a)

    def test_ajout_du_technicien_sans_prix_et_tables_du_responsable_refusees(self):
        chemin = self.serveur.dossier / "articles.csv"
        entete, _ = lire_tableau(chemin.read_bytes())
        ligne = [""] * len(entete)
        for nom, valeur in (("id", "ART-9998"), ("reference", "AJOUT-T152"), ("prix_unitaire", "777")):
            ligne[entete.index(nom)] = valeur
        reponse = self.client.requete("POST", "/api/csv/articles/ajout", ecrire_tableau(entete, [ligne], bom=False),
                                      cookie=self.cookies["technicien"])
        self.assertEqual(reponse.statut, 200, reponse.octets)
        derniere = lire_tableau(chemin.read_bytes())[1][-1]
        self.assertEqual((derniere[0], derniere[entete.index("prix_unitaire")]), ("ART-9998", ""))
        for table in ("parametres", "techniciens", "fournisseurs"):
            with self.subTest(table=table):
                disque = (self.serveur.dossier / (table + ".csv")).read_bytes()
                ecriture = self.client.requete("PUT", "/api/csv/" + table, disque, cookie=self.cookies["technicien"],
                                               entetes={"X-Version-Attendue": version_de(disque)})
                self.assertTrue(ecriture.refus_de_role(), ecriture.octets)
                ajout = self.client.requete("POST", "/api/csv/%s/ajout" % table, premiere_ligne(disque) + b"\r\n",
                                            cookie=self.cookies["technicien"])
                self.assertTrue(ajout.refus_de_role(), ajout.octets)
                self.assertEqual((self.serveur.dossier / (table + ".csv")).read_bytes(), disque)


# ---------------------------------------------------------------------------
# Demandeur : liste fermée, pages réservées, demandes en ajout seulement, documents
# ---------------------------------------------------------------------------

class TestDemandeur(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        lancer_serveur_comptes(cls, pages_reservees=True)

    def requete(self, methode, chemin, corps=None, entetes=None):
        return self.client.requete(methode, chemin, corps, cookie=self.cookies["demandeur"], entetes=entetes)

    def nouvelle_demande(self, entete, identifiant, **valeurs):
        ligne = [""] * len(entete)
        base = {"id": identifiant, "date_heure": "2026-10-26 10:15", "demandeur": "Léa Martin",
                "equipement_id": "EQ-0005", "symptome": "Fuite", "impact": "dégradé", "statut": "Nouvelle"}
        base.update(valeurs)
        for nom, valeur in base.items():
            ligne[entete.index(nom)] = valeur
        return ligne

    def envoyer_demandes(self, entete, lignes, version=None):
        chemin = self.serveur.dossier / "demandes.csv"
        return self.requete("PUT", "/api/csv/demandes", ecrire_tableau(entete, lignes),
                            entetes={"X-Version-Attendue": version or version_de(chemin.read_bytes())})

    def test_liste_fermee_et_versions_de_ses_tables(self):
        refus = self.requete("GET", "/api/csv/techniciens")                     # CS122
        self.assertTrue(refus.refus_de_role(), refus.octets)
        self.assertNotIn(b"TEC-0001", refus.octets)
        versions = self.requete("GET", "/api/versions").json()["tables"]
        self.assertEqual(set(versions), TABLES_DU_DEMANDEUR)
        for table, valeur in versions.items():           # T506 : equipements (cout_arret_h caché), version voilée
            (self.assertNotEqual if table == "equipements" else self.assertEqual)(
                valeur["version"], version_de((self.serveur.dossier / (table + ".csv")).read_bytes()), table)
        technicien = self.client.requete("GET", "/api/versions", cookie=self.cookies["technicien"]).json()["tables"]
        self.assertEqual(set(technicien), TOUTES_LES_TABLES)

    def test_wiki_sans_pages_technicien_ni_intervention(self):
        disque = (self.serveur.dossier / "wiki_pages.csv").read_bytes()
        entete, lignes = lire_tableau(disque)
        recu = self.requete("GET", "/api/csv/wiki_pages")
        self.assertEqual(recu.statut, 200)
        self.assertEqual(recu.entetes["x-version"], version_de(disque))
        entete_recu, lignes_recues = lire_tableau(recu.octets)
        self.assertEqual(entete_recu, entete)
        self.assertEqual(lignes_recues, [ligne for ligne in lignes if ligne[0] not in PAGES_RESERVEES])
        self.assertEqual(len(lignes) - len(lignes_recues), len(PAGES_RESERVEES))
        self.assertEqual(self.client.requete("GET", "/api/csv/wiki_pages", cookie=self.cookies["technicien"]).octets,
                         disque)

    def test_demandes_en_ajout_seulement(self):
        chemin = self.serveur.dossier / "demandes.csv"
        octets = chemin.read_bytes()
        entete, lignes = lire_tableau(octets)
        modifiee = list(lignes[0])
        modifiee[entete.index("symptome")] = "Autre symptôme"
        nouvelle = lambda identifiant, **valeurs: self.nouvelle_demande(entete, identifiant, **valeurs)   # noqa: E731
        refus = [
            ("modification", [modifiee] + lignes[1:]),
            ("suppression", lignes[1:]),
            ("décision : statut", lignes + [nouvelle("DI-2026-9001", statut="Acceptée")]),
            ("décision : motif", lignes + [nouvelle("DI-2026-9002", motif_decision="Je décide")]),
            ("décision : date", lignes + [nouvelle("DI-2026-9003", date_decision="2026-10-26 10:20")]),
            ("décision : OT", lignes + [nouvelle("DI-2026-9004", ot_id=OT_EN_COURS)]),
            ("numéro pris", lignes + [nouvelle(lignes[0][0], symptome="Bruit")]),
            ("numéro vide", lignes + [nouvelle("")]),
            ("deux fois le même numéro", lignes + [nouvelle("DI-2026-9005"), nouvelle("DI-2026-9005")]),
        ]
        for cas, envoyees in refus:
            with self.subTest(cas=cas):
                reponse = self.envoyer_demandes(entete, envoyees)
                self.assertEqual(reponse.statut, 403, reponse.octets)
                self.assertTrue(reponse.json()["erreur"].startswith("Accès refusé : le demandeur ne peut qu'ajouter"))
                self.assertEqual(chemin.read_bytes(), octets)
        perimee = self.envoyer_demandes(entete, [modifiee] + lignes[1:], version="0123456789abcdef")
        self.assertEqual(perimee.statut, 409, perimee.octets)                  # la version d'abord, comme toujours
        self.assertEqual(chemin.read_bytes(), octets)
        reponse = self.envoyer_demandes(entete, lignes + [nouvelle("DI-2026-9006")])
        self.assertEqual(reponse.statut, 200, reponse.octets)
        apres = chemin.read_bytes()
        self.assertEqual(reponse.json()["version"], version_de(apres))
        self.assertTrue(apres.startswith(octets))                              # lignes actuelles intactes
        self.assertEqual(lire_tableau(apres)[1], lignes + [nouvelle("DI-2026-9006")])

    def test_demande_recrite_par_excel_reconnue_et_gardee_telle_quelle(self):
        chemin = self.serveur.dossier / "demandes.csv"
        entete, lignes = lire_tableau(chemin.read_bytes())
        p_date, p_statut = entete.index("date_heure"), entete.index("statut")
        lue = list(lignes[0])
        self.assertRegex(lue[p_date], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
        abimee = list(lue)
        annee, mois, jour = lue[p_date][:10].split("-")
        abimee[p_date] = "%s/%s/%s %s:00" % (jour, mois, annee, lue[p_date][11:])
        abimee[p_statut] = lue[p_statut].lower() + "  "
        chemin.write_bytes(ecrire_tableau(entete, [abimee] + lignes[1:]))      # enregistré par Excel, à la main
        # Le navigateur envoie ce qu'il a lu (§3.3) : date AAAA-MM-JJ HH:MM, statut canonique, puis sa demande.
        nouvelle = self.nouvelle_demande(entete, "DI-2026-9101")
        reponse = self.envoyer_demandes(entete, [lue] + lignes[1:] + [nouvelle])
        self.assertEqual(reponse.statut, 200, reponse.octets)
        apres = lire_tableau(chemin.read_bytes())[1]
        self.assertEqual(apres[0], abimee)                                     # rien d'une ligne existante n'a changé
        self.assertEqual(apres[-1], nouvelle)

    def test_ajout_par_post_demandes_et_journal(self):
        chemin = self.serveur.dossier / "demandes.csv"
        entete, _ = lire_tableau(chemin.read_bytes())
        identifiant_pris = lire_tableau(chemin.read_bytes())[1][0][0]
        for cas, ligne, statut in (("nouvelle", self.nouvelle_demande(entete, "DI-2026-9201"), 200),
                                   ("décision", self.nouvelle_demande(entete, "DI-2026-9202", statut="Refusée"), 403),
                                   ("numéro pris", self.nouvelle_demande(entete, identifiant_pris), 403)):
            with self.subTest(cas=cas):
                avant = chemin.read_bytes()
                reponse = self.requete("POST", "/api/csv/demandes/ajout", ecrire_tableau(entete, [ligne], bom=False))
                self.assertEqual(reponse.statut, statut, reponse.octets)
                if statut == 200:
                    self.assertEqual(lire_tableau(chemin.read_bytes())[1][-1], ligne)
                else:
                    self.assertTrue(reponse.refus_de_role())
                    self.assertEqual(chemin.read_bytes(), avant)
        journal = self.serveur.dossier / "journal.csv"
        entete_j, _ = lire_tableau(journal.read_bytes())
        ligne_j = [""] * len(entete_j)
        for nom, valeur in (("id", "JR-ESSAI-T152"), ("date_heure", "2026-10-26 10:16"), ("poste", "Poste test"),
                            ("profil", "demandeur"), ("table", "demandes"), ("id_ligne", "DI-2026-9201"),
                            ("action", "création — demande signalée")):
            ligne_j[entete_j.index(nom)] = valeur
        reponse = self.requete("POST", "/api/csv/journal/ajout", ecrire_tableau(entete_j, [ligne_j], bom=False))
        self.assertEqual(reponse.statut, 200, reponse.octets)
        ligne_j[entete_j.index("profil")] = "Demandeur Léa Martin"      # T505 : le profil de la session, imposé
        self.assertEqual(lire_tableau(journal.read_bytes())[1][-1], ligne_j)

    def test_documents_du_demandeur(self):
        nom = "photo-20261026-101530-WXYZ.jpg"
        envoi = self.requete("PUT", "/api/documents/" + nom, JPEG)
        self.assertEqual(envoi.statut, 201, envoi.octets)
        # Nom imposé par le serveur (audit F4, T159) : le demandeur relit sa photo sous ce nom (préfixe accepté par
        # MOTIF_PHOTO_DE_DEMANDE), l'envoi ayant été contrôlé sur le nom demandé.
        enregistre = envoi.json()["nom"]
        self.assertRegex(enregistre, r"^\d{8}-\d{6}-" + re.escape(nom) + "$")
        relu = self.requete("GET", "/api/documents/" + enregistre)
        self.assertEqual((relu.statut, relu.entetes["content-type"], relu.octets), (200, "image/jpeg", JPEG))
        self.assertEqual(self.requete("GET", "/api/documents/" + DOCUMENT_EQUIPEMENT).statut, 200)
        self.assertEqual(self.requete("GET", "/api/documents/photo-20261026-101531-ABSE.jpg").statut, 404)   # permis
        for methode, nom_refuse, corps in (("GET", AUTRE_DOCUMENT, None), ("PUT", "rapport-essai.pdf", PDF),
                                           ("PUT", "photo-2026-essai.jpg", JPEG), ("PUT", "photo-20261026-101532-ABCD.pdf", PDF)):
            with self.subTest(methode=methode, nom=nom_refuse):
                reponse = self.requete(methode, "/api/documents/" + nom_refuse, corps)
                self.assertTrue(reponse.refus_de_role(), reponse.octets)
        self.assertFalse((self.serveur.dossier / "documents" / "rapport-essai.pdf").exists())
        # Les documents des équipements se lisent dans equipements.csv : un document cité ensuite s'ouvre aussi.
        chemin = self.serveur.dossier / "equipements.csv"
        entete, lignes = lire_tableau(chemin.read_bytes())
        lignes[0][entete.index("document")] = AUTRE_DOCUMENT
        chemin.write_bytes(ecrire_tableau(entete, lignes))
        self.assertEqual(self.requete("GET", "/api/documents/" + AUTRE_DOCUMENT).statut, 200)


# ---------------------------------------------------------------------------
# Comptes : routes du responsable (§22.4)
# ---------------------------------------------------------------------------

class TestComptesDuResponsable(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        lancer_serveur_comptes(cls)

    def requete(self, methode, chemin, corps=None, role="responsable", **options):
        return self.client.requete(methode, chemin, corps, cookie=self.cookies[role], **options)

    def journal(self):
        with open(self.serveur.dossier / "acces" / "journal-acces.csv", encoding="utf-8-sig", newline="") as fichier:
            return list(csv.DictReader(fichier, delimiter=";"))

    def verifier_jamais_ecrit(self, secret):
        """Le mot de passe provisoire n'est dans aucun fichier des données (comptes, journal, sauvegardes…) ni sur la
        console du serveur."""
        for fichier in self.serveur.dossier.rglob("*"):
            if fichier.is_file():
                self.assertNotIn(secret.encode("utf-8"), fichier.read_bytes(), fichier.name)
        self.assertNotIn(secret, self.serveur.sortie_console())

    def test_liste_sans_empreinte_et_creation_avec_mot_de_passe_provisoire_rendu_une_fois(self):
        liste = self.requete("GET", "/api/acces/comptes")
        self.assertEqual(liste.statut, 200, liste.octets)
        comptes = liste.json()["comptes"]
        self.assertTrue({"nicolas.briand", "julien.moreau", "lea.martin"} <= {c["identifiant"] for c in comptes})
        for compte in comptes:
            self.assertFalse({"sel", "empreinte", "algo"} & set(compte), compte)
        self.assertNotIn(b"empreinte", liste.octets)
        creation = self.requete("POST", "/api/acces/comptes", {"prenom": "Marie", "nom": "Curie",
                                                               "role": "technicien", "technicien_id": "TEC-0002"})
        self.assertEqual(creation.statut, 200, creation.octets)
        compte, provisoire = creation.json()["compte"], creation.json()["mot_de_passe_provisoire"]
        self.assertEqual((compte["identifiant"], compte["role"], compte["technicien_id"], compte["a_changer"]),
                         ("marie.curie", "technicien", "TEC-0002", True))
        self.assertFalse({"sel", "empreinte", "algo"} & set(compte))
        self.assertEqual(len(provisoire), 16)
        entree = self.client.connecter_brut("marie.curie", provisoire)
        self.assertEqual(entree.statut, 200, entree.octets)
        self.assertTrue(entree.json()["session"]["a_changer"])
        self.assertEqual(self.client.requete("GET", "/api/versions", cookie=entree.cookie).json(),
                         {"erreur": serveur.MESSAGE_MOT_DE_PASSE_PROVISOIRE,
                          "erreur_code": "sessions.mot_de_passe_provisoire"})
        creations = [ligne for ligne in self.journal() if ligne["resultat"] == "creation"
                     and ligne["qui"] == "marie.curie"]
        self.assertEqual([(ligne["adresse"], ligne["agent"]) for ligne in creations], [("127.0.0.1", AGENT)])
        self.verifier_jamais_ecrit(provisoire)

    def test_reinitialiser_modifier_desactiver_activer(self):
        creation = self.requete("POST", "/api/acces/comptes", {"prenom": "Jean", "nom": "Valjean", "role": "demandeur"})
        self.assertEqual(creation.statut, 200, creation.octets)
        premier = creation.json()["mot_de_passe_provisoire"]
        adresse = "/api/acces/comptes/jean.valjean"
        reinit = self.requete("POST", adresse, {"action": "reinitialiser"})
        self.assertEqual(reinit.statut, 200, reinit.octets)
        second = reinit.json()["mot_de_passe_provisoire"]
        self.assertNotEqual(second, premier)
        self.assertTrue(reinit.json()["compte"]["a_changer"])
        self.assertEqual(self.client.connecter_brut("jean.valjean", premier).statut, 401)
        session = self.client.connecter("jean.valjean", second)
        refus = self.requete("POST", adresse, {"action": "modifier", "role": "technicien"})
        self.assertEqual(refus.statut, 400, refus.octets)                       # technicien lié obligatoire
        inconnu = self.requete("POST", adresse, {"action": "modifier", "role": "technicien", "technicien_id": "TEC-9999"})
        self.assertEqual(inconnu.statut, 400, inconnu.octets)
        modifie = self.requete("POST", adresse, {"action": "modifier", "role": "technicien", "technicien_id": "TEC-0003",
                                                 "prenom": "Jean "})
        self.assertEqual(modifie.statut, 200, modifie.octets)
        self.assertEqual((modifie.json()["compte"]["role"], modifie.json()["compte"]["prenom"]), ("technicien", "Jean"))
        desactive = self.requete("POST", adresse, {"action": "desactiver"})
        self.assertEqual((desactive.statut, desactive.json()["compte"]["actif"]), (200, False))
        self.assertIsNone(self.client.requete("GET", "/api/session", cookie=session).json()["session"])
        self.assertEqual(self.client.connecter_brut("jean.valjean", second).statut, 401)
        active = self.requete("POST", adresse, {"action": "activer"})
        self.assertEqual((active.statut, active.json()["compte"]["actif"]), (200, True))
        self.assertEqual(self.client.connecter_brut("jean.valjean", second).statut, 200)
        resultats = [ligne["resultat"] for ligne in self.journal() if ligne["qui"] == "jean.valjean"]
        self.assertIn("reinitialisation", resultats)
        self.assertGreaterEqual(resultats.count("modification"), 3)
        self.verifier_jamais_ecrit(premier)
        self.verifier_jamais_ecrit(second)

    def test_dernier_responsable_garde_et_demandes_refusees(self):
        for corps in ({"action": "desactiver"}, {"action": "modifier", "role": "technicien", "technicien_id": "TEC-0001"}):
            with self.subTest(corps=corps):
                reponse = self.requete("POST", "/api/acces/comptes/nicolas.briand", corps)
                self.assertEqual(reponse.statut, 400, reponse.octets)
                self.assertIn("au moins un compte responsable actif", reponse.json()["erreur"])
        self.assertEqual(self.requete("POST", "/api/acces/comptes/personne.inconnue", {"action": "activer"}).statut, 404)
        for corps in ({"action": "supprimer"}, {"action": "reinitialiser", "prenom": "X"}, {}):
            with self.subTest(corps=corps):
                self.assertEqual(self.requete("POST", "/api/acces/comptes/paul.essai", corps).statut, 400)
        for corps in ({"prenom": "Zoe", "role": "demandeur", "mot_de_passe": "choisi par le responsable"},
                      {"prenom": "Zoe", "role": "chef"}, {"nom": "Sans prénom", "role": "demandeur"},
                      {"prenom": "Zoe", "role": "technicien", "technicien_id": "TEC-9999"}, {"prenom": 3, "role": "demandeur"}):
            with self.subTest(corps=corps):
                self.assertEqual(self.requete("POST", "/api/acces/comptes", corps).statut, 400)
        sans_prevo = self.requete("POST", "/api/acces/comptes", {"prenom": "Zoe", "role": "demandeur"}, prevo=False)
        self.assertEqual(sans_prevo.statut, 403)
        self.assertFalse(sans_prevo.refus_de_role())
        identifiants = {c["identifiant"] for c in self.requete("GET", "/api/acces/comptes").json()["comptes"]}
        self.assertNotIn("zoe", identifiants)
        for role in ("technicien", "demandeur"):
            for methode, chemin, corps in (("GET", "/api/acces/comptes", None), ("GET", "/api/acces/journal", None),
                                           ("POST", "/api/acces/comptes", {"prenom": "Zoe", "role": "responsable"}),
                                           ("POST", "/api/acces/comptes/" + SESSIONS[role], {"action": "modifier",
                                                                                            "role": "responsable"})):
                with self.subTest(role=role, chemin=chemin, methode=methode):
                    reponse = self.requete(methode, chemin, corps, role=role)
                    self.assertEqual(reponse.json(), {"erreur": serveur.MESSAGE_RESERVE_AU_RESPONSABLE,
                                                      "erreur_code": "acces.reserve_au_responsable"})

    def test_journal_des_connexions_en_csv(self):
        reponse = self.requete("GET", "/api/acces/journal")
        self.assertEqual(reponse.statut, 200)
        self.assertEqual(reponse.entetes["content-type"], "text/csv; charset=utf-8")
        self.assertEqual(reponse.entetes["content-disposition"], 'attachment; filename="journal-acces.csv"')
        self.assertTrue(reponse.octets.startswith(BOM + b"date;qui;adresse;agent;resultat;tailscale\r\n"))
        self.assertEqual(reponse.octets, (self.serveur.dossier / "acces" / "journal-acces.csv").read_bytes())


# ---------------------------------------------------------------------------
# Sans comptes (portée « ce PC ») : rien ne change
# ---------------------------------------------------------------------------

class TestSansComptes(unittest.TestCase):

    def test_rien_ne_change_et_les_routes_des_comptes_repondent_400(self):
        racine = Path(tempfile.mkdtemp(prefix="prevo-roles-sans-"))
        self.addCleanup(shutil.rmtree, racine, True)
        source, _ = preparer_source(racine)
        lance = commun.ServeurPrevo(source=source)
        lance.demarrer()
        self.addCleanup(lance.arreter)
        client = Client(lance.url)
        for table in ("techniciens", "articles", "achats", "wiki_pages"):
            with self.subTest(table=table):
                self.assertEqual(client.requete("GET", "/api/csv/" + table).octets,
                                 (lance.dossier / (table + ".csv")).read_bytes())
        self.assertEqual(set(client.requete("GET", "/api/versions").json()["tables"]), TOUTES_LES_TABLES)
        self.assertEqual(client.requete("GET", "/api/documents/" + AUTRE_DOCUMENT).statut, 200)
        chemin = lance.dossier / "demandes.csv"
        entete, lignes = lire_tableau(chemin.read_bytes())
        lignes[0][entete.index("statut")] = "Refusée"
        ecriture = client.requete("PUT", "/api/csv/demandes", ecrire_tableau(entete, lignes),
                                  entetes={"X-Version-Attendue": version_de(chemin.read_bytes())})
        self.assertEqual(ecriture.statut, 200, ecriture.octets)                  # aucune règle de rôle sans comptes
        for methode, adresse, corps in (("GET", "/api/acces/comptes", None), ("GET", "/api/acces/journal", None),
                                        ("POST", "/api/acces/comptes", {"prenom": "Zoe", "role": "demandeur"}),
                                        ("POST", "/api/acces/comptes/paul.essai", {"action": "activer"})):
            with self.subTest(adresse=adresse, methode=methode):
                reponse = client.requete(methode, adresse, corps)
                self.assertEqual((reponse.statut, reponse.json()), (400, {"erreur": serveur.MESSAGE_SANS_COMPTES,
                                                                          "erreur_code": "sessions.sans_comptes"}))


# ---------------------------------------------------------------------------
# Navigateur : le demandeur signale avec photo, le technicien sort une pièce
# ---------------------------------------------------------------------------

class CasNavigateurComptes(CasNavigateur):
    """Navigateur sur un serveur réel en mode comptes. La session (cookie « id ») est posée dans le contexte avant le
    chargement, et le profil de l'écran aussi : l'écran de connexion et App.profil tiré du compte viennent avec T155."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        lancer_serveur_comptes(cls)

    def poser_session(self, role, profil, nom, technicien_id=""):
        cookie = self.client.connecter(SESSIONS[role])
        self.contexte.add_cookies([{"name": "id", "value": cookie.split("=", 1)[1], "url": self.serveur.url,
                                    "httpOnly": True, "sameSite": "Lax"}])
        preregler_profil(self.contexte, profil, nom, technicien_id)
        self.reponses = []
        self.page.on("response", lambda reponse: self.reponses.append(
            (reponse.request.method, reponse.url, reponse.status)) if "/api/" in reponse.url else None)


class TestNavigateurDemandeur(CasNavigateurComptes):

    REFUSEES = sorted(TOUTES_LES_TABLES - TABLES_DU_DEMANDEUR)

    def setUp(self):
        super().setUp()
        self.poser_session("demandeur", "demandeur", "Léa Martin")
        # Donnees.chargerTout lit les 24 tables : celles qui ne sont pas au demandeur répondent 403 (vues comme
        # absentes par stockage-serveur.js) ; Chromium le note en console.error, ces refus-là seulement sont permis.
        self.autoriser_erreur(re.compile(r"status of 403 .*/api/csv/(?:%s):" % "|".join(self.REFUSEES)))

    def verifier_refus_attendus(self):
        for methode, adresse, statut in self.reponses:
            if statut >= 400:
                table = adresse.rsplit("/api/csv/", 1)[-1] if "/api/csv/" in adresse else None
                self.assertTrue(methode == "GET" and statut == 403 and table in self.REFUSEES,
                                (methode, adresse, statut))

    def test_signaler_une_demande_avec_photo_en_mode_comptes(self):
        page = self.page
        chemin = self.serveur.dossier / "demandes.csv"
        avant = len(lire_tableau(chemin.read_bytes())[1])
        page.goto(self.serveur.url + "/#/di/nouvelle?equipement=EQ-0005")
        attendre_pret(page)
        self.assertIn("PO-02", page.inner_text(".selecteur-choisi"))
        page.click(".di-puce[data-symptome='Fuite']")
        page.click("label.tuile:has(input[value='dégradé'])")
        page.fill("textarea[name=description]", "Goutte à goutte sous la garniture (mode comptes).")
        page.locator(".di-fichier-photo").set_input_files(fichier_png(1600, 1200))
        page.wait_for_selector(".di-apercu:not([hidden]) img")
        page.click(".di-envoyer")
        page.wait_for_selector(".di-numero")
        numero = page.inner_text(".di-numero")
        entete, lignes = lire_tableau(chemin.read_bytes())
        self.assertEqual(len(lignes), avant + 1)
        ligne = dict(zip(entete, lignes[-1]))
        self.assertEqual((ligne["id"], ligne["demandeur"], ligne["statut"], ligne["equipement_id"], ligne["symptome"]),
                         (numero, "Léa Martin", "Nouvelle", "EQ-0005", "Fuite"))
        self.assertRegex(ligne["photo"], MOTIF_PHOTO)
        self.assertEqual((self.serveur.dossier / "documents" / ligne["photo"]).read_bytes()[:3], bytes((0xFF, 0xD8, 0xFF)))
        page.click("a:has-text('Voir ma demande')")
        page.wait_for_selector(".di-details")
        page.wait_for_function("document.querySelector('.di-photo-image').naturalWidth > 0")
        ecritures = {(methode, adresse.split("/api/", 1)[1], statut) for methode, adresse, statut in self.reponses
                     if methode in ("PUT", "POST")}
        self.assertIn(("PUT", "csv/demandes", 200), ecritures)
        # L'envoi porte le nom demandé ; la demande garde le nom imposé par le serveur (préfixe, audit F4, T159).
        self.assertIn(("PUT", "documents/" + re.sub(r"^\d{8}-\d{6}-", "", ligne["photo"]), 201), ecritures)
        self.assertIn(("POST", "csv/journal/ajout", 200), ecritures)
        self.verifier_refus_attendus()

    def test_ecrans_du_demandeur_sans_erreur(self):
        page = self.page
        page.goto(self.serveur.url + "/#/accueil")
        attendre_pret(page)
        for route, selecteur in (("#/accueil", ".accueil-signaler"), ("#/di", ".di-zone-tableau"),
                                 ("#/parc", "#parc-arbre"), ("#/equipement/EQ-0001", ".parc-carte-compteurs"),
                                 ("#/wiki", "#wiki-phrase-resume"), ("#/wiki/EQ-0005", '.wiki-entite[data-page="EQ-0005"]'),
                                 ("#/poste", "#poste-nom"), ("#/apropos", ".apropos-liste")):
            with self.subTest(route=route):
                page.evaluate("(route) => { location.hash = route; }", route)
                page.wait_for_selector(selecteur)
        # Compteurs et relevés sont des tables du demandeur : la fiche ouverte par le QR les montre.
        page.evaluate("(route) => { location.hash = route; }", "#/equipement/EQ-0001")
        page.wait_for_selector(".parc-carte-compteurs .parc-dernier-releve")
        self.verifier_refus_attendus()


class TestNavigateurTechnicien(CasNavigateurComptes):

    def test_sortie_d_une_piece_stock_recopie_et_prix_gardes(self):
        self.poser_session("technicien", "technicien", "Julien Moreau", "TEC-0001")
        page = self.page
        chemin = self.serveur.dossier / "articles.csv"
        entete, lignes = lire_tableau(chemin.read_bytes())
        p_prix, p_stock = entete.index("prix_unitaire"), entete.index("stock")
        prix = {ligne[0]: ligne[p_prix] for ligne in lignes}
        page.goto(self.serveur.url + "/#/accueil")
        attendre_pret(page)
        stock = page.evaluate("(article) => Donnees.stockArticle(article)", ARTICLE)    # recalculé des mouvements
        self.assertGreaterEqual(stock, 1)
        # Le navigateur du technicien n'a reçu ni prix ni taux horaire.
        self.assertEqual(page.evaluate("Donnees.lignes('articles').filter((a) => a.prix_unitaire !== '').length"), 0)
        self.assertEqual(page.evaluate("Donnees.lignes('techniciens').filter((t) => t.taux_horaire !== '').length"), 0)
        mouvement = page.evaluate("([ot, article]) => Magasin.sortir(ot, article, 1, 'Essai T152')", [OT_EN_COURS, ARTICLE])
        self.assertTrue(mouvement)
        entete_apres, lignes_apres = lire_tableau(chemin.read_bytes())
        self.assertEqual(entete_apres, entete)
        par_id = {ligne[0]: ligne for ligne in lignes_apres}
        self.assertEqual(float(par_id[ARTICLE][p_stock]), stock - 1)            # copie de la colonne stock écrite
        for identifiant, valeur in prix.items():
            self.assertEqual(par_id[identifiant][p_prix], valeur, identifiant)   # prix gardés
        self.assertIn(("PUT", "csv/articles", 200), {(m, a.split("/api/", 1)[1], s) for m, a, s in self.reponses})
        self.assertEqual([reponse for reponse in self.reponses if reponse[2] >= 400], [])


if __name__ == "__main__":
    unittest.main()
