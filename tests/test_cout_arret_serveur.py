"""L5 — coût d'une heure d'arrêt (equipements.cout_arret_h) caché par le serveur au technicien, au demandeur et à
l'appareil (T473 ; CS174 ; D126 prolongé ; QUESTIONS-L2-L6.md, L4-L6 Q6 ; ARCHITECTURE.md §22.5) ; rapports mensuels
figés servis au seul responsable (T478).

Même mécanisme que le taux horaire, les prix et le montant annuel (COLONNES_CACHEES_PAR_ROLE, T152 et T453), à un
écart près : cout_arret_h est une colonne du format 4 dans une table du format 1, son nom reste donc dans l'en-tête
renvoyé et seules ses valeurs sont vidées (retirée, le navigateur lirait equipements au format 3 et, en mode serveur,
ne générerait plus les OT préventifs échus à l'ouverture : Formats.formatDuFichier, passerAuFormatCourant de app.js).

Ce qui est vérifié, en mode serveur avec comptes (vraies sessions sur une copie du jeu f4-v2.2.0, coûts changés) :
    lecture        technicien et demandeur reçoivent equipements avec l'en-tête du fichier (format 4 complet) et
                   cout_arret_h vide sur chaque ligne (0 compris), aucun coût dans les octets, autres cellules
                   intactes, X-Version voilée (T506) ; l'appareil enrôlé aussi (identité simulée,
                   filtrer_csv_pour) ; le responsable reçoit le fichier tel quel ;
    PUT technicien comme le navigateur (ce qu'il a lu, une ligne modifiée, coût forgé, ligne nouvelle avec coût,
                   lignes dans un autre ordre) : écrit, chaque coût du fichier gardé ligne par ligne, coût forgé
                   ignoré, ligne nouvelle sans coût, autre colonne écrite ; réécrire tel quel ce qu'il a lu n'efface
                   rien ; un PUT sans la colonne est refusé (400, en-tête du schéma), fichier inchangé ;
    ajout          coût vidé dans la ligne ajoutée par le technicien ; gardé pour le responsable ;
    demandeur      ne peut écrire equipements (403), fichier inchangé ;
    responsable    écrit un coût ; aucun contrôle pour lui (controle_d_ecriture, controle_d_ajout : None) ;
    sans comptes   rien ne change (coûts lus, coût écrit) ;
    rapports figés (T478, D126 ; écart trouvé par la recette T476) un document cité par parametres.rapports_mensuels
                   (noms séparés par des virgules, apostrophe de protection et espaces de bord tolérés) n'est servi
                   qu'au responsable : 403 « ce document n'est pas ouvert » au technicien (qui en lit pourtant le nom),
                   au demandeur et à l'appareil ; casse du nom ignorée ; liste relue à chaque requête ; à part de
                   DOCUMENTS_RESERVES_AU_RESPONSABLE (D196) : vider celui-ci ne rouvre pas les rapports ; autres documents et envois inchangés ;
                   sans comptes, servis.

Aucune donnée réelle : copie temporaire du jeu f4-v2.2.0 (tests/jeux_formats.py). Sans navigateur.
Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_cout_arret_serveur.py" -v
"""
import csv
import http.client
import importlib.util
import io
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import commun
from commun import RACINE
from jeux_formats import copier_jeu

SCRIPT = RACINE / "serveur.py"
JEU = "f4-v2.2.0"
AGENT = "tests-prevo/1.0"
BOM = bytes((0xEF, 0xBB, 0xBF))
TABLE = "equipements"
COLONNE = "cout_arret_h"
# Coûts posés dans la copie du jeu : chiffres absents du jeu (vérifié), plus un « 0 » (arrêt sans coût, caché aussi).
COUTS = {"EQ-0001": "6043.75", "EQ-0007": "93571", "EQ-0003": "0"}


def charger_serveur():
    specification = importlib.util.spec_from_file_location("serveur_prevo_t473", SCRIPT)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


serveur = charger_serveur()


# ---------------------------------------------------------------------------
# Données d'essai : CSV au format de Prévo
# ---------------------------------------------------------------------------

def lire_tableau(octets):
    """(en-tête, lignes) d'un CSV de Prévo (BOM, « ; »), valeurs telles qu'écrites."""
    lignes = [ligne for ligne in csv.reader(io.StringIO(octets.decode("utf-8-sig"), newline=""), delimiter=";") if ligne]
    return lignes[0], lignes[1:]


def cellule(texte):
    """Comme celluleCsv de js/donnees.js (§3.1)."""
    return '"' + texte.replace('"', '""') + '"' if re.search(r'[;"\r\n]|\A[ \t]|[ \t]\Z', texte) else texte


def ecrire_tableau(entete, lignes, bom=True):
    texte = "".join(";".join(cellule(valeur) for valeur in ligne) + "\r\n" for ligne in [entete] + list(lignes))
    return (BOM if bom else b"") + texte.encode("utf-8")


def premiere_ligne(octets):
    """Ligne d'en-tête d'un fichier (sans BOM ni fin de ligne) : début d'un corps d'ajout."""
    return octets[len(BOM):].split(b"\r\n", 1)[0] if octets.startswith(BOM) else octets.split(b"\r\n", 1)[0]


def couts_par_id(octets):
    """{id : cout_arret_h} d'un CSV d'équipements."""
    entete, lignes = lire_tableau(octets)
    position = entete.index(COLONNE)
    return {ligne[0]: ligne[position] for ligne in lignes}


def sans_couts(octets):
    """(en-tête, lignes) du CSV, cout_arret_h vidé sur chaque ligne : ce que le technicien doit recevoir."""
    entete, lignes = lire_tableau(octets)
    position = entete.index(COLONNE)
    return entete, [ligne[:position] + [""] + ligne[position + 1:] for ligne in lignes]


def nouvelle_ligne(entete, identifiant, cout):
    """Ligne d'équipement nouvelle (colonnes de l'en-tête), avec un coût horaire."""
    ligne = [""] * len(entete)
    for nom, valeur in (("id", identifiant), ("repere", "ESSAI-" + identifiant), ("designation", "Essai T473"),
                        ("localisation_id", "LOC-0004"), ("criticite", "B"), ("statut", "en service"),
                        ("actif", "1"), (COLONNE, cout)):
        ligne[entete.index(nom)] = valeur
    return ligne


def preparer_source(racine):
    """Copie du jeu f4-v2.2.0, coûts horaires remplacés par COUTS (les autres équipements sans coût). Rend le dossier."""
    source = copier_jeu(JEU, racine / "source")
    chemin = source / (TABLE + ".csv")
    octets = chemin.read_bytes()
    for cout in COUTS.values():
        if cout != "0" and cout.encode("ascii") in octets:
            raise AssertionError("le coût d'essai %s figure déjà dans le jeu %s" % (cout, JEU))
    entete, lignes = lire_tableau(octets)
    position = entete.index(COLONNE)
    for ligne in lignes:
        ligne[position] = COUTS.get(ligne[0], "")
    if {ligne[0] for ligne in lignes} < set(COUTS):
        raise AssertionError("le jeu %s n'a plus %s" % (JEU, sorted(COUTS)))
    chemin.write_bytes(ecrire_tableau(entete, lignes))
    return source


# ---------------------------------------------------------------------------
# Requêtes sur un serveur réel
# ---------------------------------------------------------------------------

class Reponse:
    def __init__(self, statut, entetes, octets):
        self.statut, self.entetes, self.octets = statut, entetes, octets

    def json(self):
        return json.loads(self.octets.decode("utf-8"))


def requete(serveur_prevo, methode, chemin, corps=None, cookie=None, entetes=None):
    entetes = dict(entetes or {})
    entetes.setdefault("User-Agent", AGENT)
    if cookie:
        entetes["Cookie"] = cookie
    if methode in ("PUT", "POST"):
        entetes.setdefault("X-Prevo", "1")
        corps = b"" if corps is None else corps
    connexion = http.client.HTTPConnection("127.0.0.1", serveur_prevo.port, timeout=60)
    try:
        connexion.request(methode, chemin, body=corps, headers=entetes)
        reponse = connexion.getresponse()
        return Reponse(reponse.status, {nom.lower(): valeur for nom, valeur in reponse.getheaders()}, reponse.read())
    finally:
        connexion.close()


class CasServeur(unittest.TestCase):
    """Serveur réel (ServeurPrevo) sur une copie préparée du jeu ; sessions des trois rôles si COMPTES."""

    COMPTES = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.racine = Path(tempfile.mkdtemp(prefix="prevo-cout-arret-serveur-"))
        cls.addClassCleanup(shutil.rmtree, cls.racine, True)
        source = preparer_source(cls.racine)
        cls.completer_source(source)
        cls.serveur = commun.ServeurPrevo(source=source, comptes=cls.COMPTES)
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)
        cls.cookies = ({role: cls.serveur.session(role) for role in ("demandeur", "technicien", "responsable")}
                       if cls.COMPTES else {})

    @classmethod
    def completer_source(cls, source):
        """Ajouts d'une classe au jeu préparé, avant le démarrage du serveur (rien par défaut)."""

    def requete(self, role, methode, chemin, corps=None, entetes=None):
        return requete(self.serveur, methode, chemin, corps, self.cookies.get(role), entetes)

    def fichier(self):
        return (self.serveur.dossier / (TABLE + ".csv")).read_bytes()

    def lire(self, role):
        lue = self.requete(role, "GET", "/api/csv/" + TABLE)
        self.assertEqual(lue.statut, 200, lue.octets[:300])
        return lue

    def ecrire(self, role, octets, version):
        return self.requete(role, "PUT", "/api/csv/" + TABLE, octets, {"X-Version-Attendue": version})

    def ajouter(self, role, ligne):
        entete = premiere_ligne(self.fichier())
        return self.requete(role, "POST", "/api/csv/%s/ajout" % TABLE,
                            entete + b"\r\n" + ecrire_tableau([], [ligne], bom=False))

    def assertSansCout(self, octets):
        for cout in COUTS.values():
            if cout != "0":
                self.assertNotIn(cout.encode("ascii"), octets)
        self.assertEqual(set(couts_par_id(octets).values()), {""})


# ---------------------------------------------------------------------------
# Lecture : coût vidé pour le technicien, le demandeur et l'appareil, en-tête du format 4 gardé
# ---------------------------------------------------------------------------

class TestLecture(CasServeur):

    def test_technicien_et_demandeur_recoivent_les_couts_vides_en_tete_gardee(self):
        disque = self.fichier()
        self.assertEqual({identifiant: cout for identifiant, cout in couts_par_id(disque).items() if cout}, COUTS)
        for role in ("technicien", "demandeur"):
            with self.subTest(role=role):
                lue = self.lire(role)
                self.assertTrue(lue.octets.startswith(BOM))
                self.assertSansCout(lue.octets)
                self.assertEqual(lire_tableau(lue.octets), sans_couts(disque))      # le reste intact
                # T506 : version voilée (jamais l'empreinte du fichier, que le responsable reçoit toujours).
                self.assertEqual(self.lire("responsable").entetes["x-version"], serveur.empreinte(disque))
                self.assertNotEqual(lue.entetes["x-version"], serveur.empreinte(disque))

    def test_en_tete_recue_au_format_4_complet(self):
        """Le navigateur reconnaît le format d'un fichier à son en-tête : toutes les colonnes du schéma y restent."""
        entete = lire_tableau(self.lire("technicien").octets)[0]
        self.assertEqual(entete[:len(serveur.COLONNES_PAR_TABLE[TABLE])], list(serveur.COLONNES_PAR_TABLE[TABLE]))
        self.assertIn(COLONNE, entete)

    def test_responsable_recoit_le_fichier_tel_quel(self):
        self.assertEqual(self.lire("responsable").octets, self.fichier())

    def test_appareil_enrole_comme_le_demandeur(self):
        appareil = {"identifiant": "appareil:ap-0001", "role": "demandeur", "appareil": True}
        disque = self.fichier()
        filtres = serveur.filtrer_csv_pour(appareil, TABLE, disque)
        self.assertSansCout(filtres)
        self.assertEqual(lire_tableau(filtres), sans_couts(disque))
        config = serveur.Configuration(tempfile.mkdtemp(prefix="prevo-cout-arret-appareil-"), [])
        self.addCleanup(shutil.rmtree, config.dossier_donnees, True)
        serveur.verifier_role(config, appareil, ("GET", "csv/<table>"), TABLE)    # il lit equipements (sans lever)
        with self.assertRaises(serveur.ErreurHttp) as refus:
            serveur.verifier_role(config, appareil, ("PUT", "csv/<table>"), TABLE)
        self.assertEqual(refus.exception.statut, 403)

    def test_les_autres_colonnes_cachees_restent_retirees(self):
        """L'écart (nom gardé) ne vaut que pour une colonne d'un format suivant : le taux horaire reste retiré."""
        lue = self.requete("technicien", "GET", "/api/csv/techniciens")
        self.assertEqual(lue.statut, 200, lue.octets[:300])
        self.assertNotIn("taux_horaire", lire_tableau(lue.octets)[0])


# ---------------------------------------------------------------------------
# Écritures du technicien : le coût du fichier n'est jamais effacé ni changé
# ---------------------------------------------------------------------------

class TestEcrituresDuTechnicien(CasServeur):

    def test_put_comme_le_navigateur_couts_gardes_forge_ignore_ligne_nouvelle_sans_cout(self):
        avant = couts_par_id(self.fichier())
        lue = self.lire("technicien")
        entete, lignes = lire_tableau(lue.octets)
        p_statut, p_cout = entete.index("statut"), entete.index(COLONNE)
        par_id = {ligne[0]: ligne for ligne in lignes}
        par_id["EQ-0001"][p_statut] = "en service" if par_id["EQ-0001"][p_statut] != "en service" else "arrêt"
        statut_voulu = par_id["EQ-0001"][p_statut]
        par_id["EQ-0007"][p_cout] = "1"                                         # coût forgé sur une ligne existante
        envoyees = list(reversed(lignes)) + [nouvelle_ligne(entete, "EQ-0901", "999")]
        reponse = self.ecrire("technicien", ecrire_tableau(entete, envoyees), lue.entetes["x-version"])
        self.assertEqual(reponse.statut, 200, reponse.octets[:300])
        apres = self.fichier()
        self.assertNotEqual(reponse.json()["version"], serveur.empreinte(apres))         # T506 : version voilée
        self.assertEqual(lire_tableau(apres)[0], entete)
        self.assertEqual(couts_par_id(apres), dict(avant, **{"EQ-0901": ""}))  # gardés, forgé compris ; nouvelle : vide
        ecrites = {ligne[0]: ligne for ligne in lire_tableau(apres)[1]}
        self.assertEqual(ecrites["EQ-0001"][p_statut], statut_voulu)            # l'autre colonne est bien écrite
        relue = self.lire("technicien")
        self.assertEqual(relue.entetes["x-version"], reponse.json()["version"])  # la surveillance reste d'accord
        self.assertSansCout(relue.octets)

    def test_reecrire_tel_quel_ce_qu_il_a_lu_n_efface_rien(self):
        avant = self.fichier()
        lue = self.lire("technicien")
        reponse = self.ecrire("technicien", lue.octets, lue.entetes["x-version"])
        self.assertEqual(reponse.statut, 200, reponse.octets[:300])
        self.assertEqual(couts_par_id(self.fichier()), couts_par_id(avant))
        self.assertEqual(lire_tableau(self.fichier()), lire_tableau(avant))

    def test_put_sans_la_colonne_refuse_fichier_inchange(self):
        avant = self.fichier()
        lue = self.lire("technicien")
        entete, lignes = lire_tableau(lue.octets)
        position = entete.index(COLONNE)
        sans = ecrire_tableau(entete[:position] + entete[position + 1:],
                              [ligne[:position] + ligne[position + 1:] for ligne in lignes])
        reponse = self.ecrire("technicien", sans, lue.entetes["x-version"])
        self.assertEqual(reponse.statut, 400, reponse.octets[:300])
        self.assertEqual(self.fichier(), avant)

    def test_ajout_cout_vide(self):
        entete = lire_tableau(self.fichier())[0]
        reponse = self.ajouter("technicien", nouvelle_ligne(entete, "EQ-0902", "777"))
        self.assertEqual(reponse.statut, 200, reponse.octets[:300])
        couts = couts_par_id(self.fichier())
        self.assertEqual(couts["EQ-0902"], "")
        self.assertEqual({identifiant: cout for identifiant, cout in couts.items() if cout}, COUTS)


# ---------------------------------------------------------------------------
# Demandeur : n'écrit pas equipements ; responsable : écrit le coût, aucun contrôle pour lui
# ---------------------------------------------------------------------------

class TestDemandeurEtResponsable(CasServeur):

    def test_demandeur_n_ecrit_pas_les_equipements(self):
        avant = self.fichier()
        reponse = self.ecrire("demandeur", avant, serveur.empreinte(avant))
        self.assertEqual(reponse.statut, 403, reponse.octets[:300])
        self.assertEqual(self.fichier(), avant)

    def test_responsable_ecrit_un_cout(self):
        lue = self.lire("responsable")
        entete, lignes = lire_tableau(lue.octets)
        position = entete.index(COLONNE)
        for ligne in lignes:
            if ligne[0] == "EQ-0007":
                ligne[position] = "1250.5"
        reponse = self.ecrire("responsable", ecrire_tableau(entete, lignes), lue.entetes["x-version"])
        self.assertEqual(reponse.statut, 200, reponse.octets[:300])
        self.assertEqual(couts_par_id(self.fichier())["EQ-0007"], "1250.5")
        ajout = self.ajouter("responsable", nouvelle_ligne(entete, "EQ-0903", "88"))
        self.assertEqual(ajout.statut, 200, ajout.octets[:300])
        self.assertEqual(couts_par_id(self.fichier())["EQ-0903"], "88")

    def test_aucun_controle_pour_le_responsable(self):
        responsable = {"identifiant": "nicolas.briand", "role": "responsable", "appareil": False}
        self.assertIsNone(serveur.controle_d_ecriture(responsable, TABLE))
        self.assertIsNone(serveur.controle_d_ajout(responsable, TABLE))
        self.assertEqual(serveur.filtrer_csv_pour(responsable, TABLE, self.fichier()), self.fichier())


# ---------------------------------------------------------------------------
# Sans comptes : rien ne change
# ---------------------------------------------------------------------------

class TestSansComptes(CasServeur):

    COMPTES = False

    def test_rien_ne_change(self):
        lue = self.lire(None)
        self.assertEqual(lue.octets, self.fichier())
        entete, lignes = lire_tableau(lue.octets)
        position = entete.index(COLONNE)
        lignes[0][position] = "42"
        reponse = self.ecrire(None, ecrire_tableau(entete, lignes), lue.entetes["x-version"])
        self.assertEqual(reponse.statut, 200, reponse.octets[:300])
        self.assertEqual(couts_par_id(self.fichier())[lignes[0][0]], "42")


# ---------------------------------------------------------------------------
# Rapports mensuels figés : servis au seul responsable (T478 ; D126 ; écart trouvé par la recette T476)
# ---------------------------------------------------------------------------

RAPPORT = "20261001-080000-rapport-mensuel-2026-09.html"           # 1er de rapports_mensuels (apostrophe devant)
REVISION = "20261002-090000-rapport-mensuel-2026-09-r2.html"       # 2e, après « , » (espace gardée par un tableur)
PAS_ENCORE = "20261101-080000-rapport-mensuel-2026-10.html"        # sur le disque, cité ensuite par le responsable
AUTRE = "20261020-101500-notice-libre.pdf"                         # cité nulle part : lisible du technicien
REFUS_DOCUMENT = "Accès refusé : ce document n'est pas ouvert au {role}."
VALEUR = "'%s, %s" % (RAPPORT, REVISION)     # rapports_mensuels au départ (lecture tolérante : apostrophe, espace)


def contenu(nom):
    return ("<!doctype html><title>Rapport mensuel (essai T478)</title><p>Coût de l'arrêt : 6043.75 € ; "
            + nom + "</p>\n").encode("utf-8")


def avec_rapports(octets, valeur):
    """parametres.csv où rapports_mensuels vaut « valeur » (ligne ajoutée ou remplacée)."""
    entete, lignes = lire_tableau(octets)
    return ecrire_tableau(entete, [ligne for ligne in lignes if ligne[0] != "rapports_mensuels"]
                          + [["rapports_mensuels", valeur]])


class CasRapportsFiges(CasServeur):
    """Jeu préparé, plus quatre documents et rapports_mensuels = RAPPORT, REVISION (lecture tolérante : apostrophe de
    protection devant le premier, espace après la virgule)."""

    @classmethod
    def completer_source(cls, source):
        documents = source / "documents"
        documents.mkdir(exist_ok=True)
        for nom in (RAPPORT, REVISION, PAS_ENCORE, AUTRE):
            (documents / nom).write_bytes(contenu(nom))
        parametres = source / "parametres.csv"
        parametres.write_bytes(avec_rapports(parametres.read_bytes(), VALEUR))

    def document(self, role, nom):
        return self.requete(role, "GET", "/api/documents/" + nom)

    def assertServi(self, reponse, nom):
        self.assertEqual((reponse.statut, reponse.octets), (200, contenu(nom)), reponse.octets[:300])

    def assertRefus(self, reponse, role):
        self.assertEqual(reponse.statut, 403, reponse.octets[:300])
        self.assertEqual(reponse.json()["erreur"], REFUS_DOCUMENT.format(role=role))
        self.assertNotIn(b"6043.75", reponse.octets)


class TestRapportsFiges(CasRapportsFiges):

    TECHNICIEN = {"identifiant": "julien.moreau", "role": "technicien", "technicien_id": "TEC-0001", "appareil": False}
    APPAREIL = {"identifiant": "appareil:ap-0001", "role": "demandeur", "appareil": True}
    RESPONSABLE = {"identifiant": "nicolas.briand", "role": "responsable", "appareil": False}

    def test_servis_au_seul_responsable(self):
        for nom in (RAPPORT, REVISION):
            with self.subTest(nom=nom):
                self.assertServi(self.document("responsable", nom), nom)
                self.assertRefus(self.document("technicien", nom), "technicien")
                self.assertRefus(self.document("demandeur", nom), "demandeur")

    def test_le_technicien_en_lit_le_nom_pas_le_document(self):
        """Le nom reste dans parametres (table qu'il lit) : aucun écran du technicien n'ouvre un rapport figé."""
        lue = self.requete("technicien", "GET", "/api/csv/parametres")
        self.assertEqual(lue.statut, 200, lue.octets[:300])
        self.assertIn(REVISION.encode("ascii"), lue.octets)
        self.assertRefus(self.document("technicien", REVISION), "technicien")

    def test_casse_du_nom_ignoree(self):
        """Windows et macOS ne distinguent pas la casse : un autre nom ne doit pas ouvrir le même fichier."""
        for nom in (RAPPORT.upper(), REVISION.replace("rapport", "Rapport")):
            with self.subTest(nom=nom):
                self.assertRefus(self.document("technicien", nom), "technicien")

    def test_liste_relue_a_chaque_requete(self):
        self.assertServi(self.document("technicien", PAS_ENCORE), PAS_ENCORE)        # pas encore un rapport figé
        lue = self.requete("responsable", "GET", "/api/csv/parametres")
        valeur = ",".join((RAPPORT, REVISION, PAS_ENCORE))                           # comme Rapport.figer
        ecrit = self.requete("responsable", "PUT", "/api/csv/parametres", avec_rapports(lue.octets, valeur),
                             {"X-Version-Attendue": lue.entetes["x-version"]})
        self.assertEqual(ecrit.statut, 200, ecrit.octets[:300])
        self.assertRefus(self.document("technicien", PAS_ENCORE), "technicien")
        self.assertServi(self.document("responsable", PAS_ENCORE), PAS_ENCORE)

    def test_autres_documents_inchanges(self):
        self.assertServi(self.document("technicien", AUTRE), AUTRE)
        self.assertServi(self.document("responsable", AUTRE), AUTRE)
        self.assertEqual(self.document("demandeur", AUTRE).statut, 403)      # ni photo ni document d'équipement
        envoi = self.requete("technicien", "PUT", "/api/documents/notice-essai-t478.pdf", b"%PDF-1.4 essai T478\n")
        self.assertEqual(envoi.statut, 201, envoi.octets[:300])              # l'envoi n'est pas touché

    def config(self, avec_parametres=True):
        """Configuration à part (verifier_role appelé ici), parametres.csv du serveur recopié ou absent."""
        dossier = Path(tempfile.mkdtemp(prefix="prevo-rapports-figes-"))
        self.addCleanup(shutil.rmtree, dossier, True)
        config = serveur.Configuration(str(dossier), [])
        serveur.creer_dossiers(config)
        if avec_parametres:                     # la valeur de départ (un autre test complète celle du serveur)
            (Path(config.dossier_donnees) / "parametres.csv").write_bytes(
                avec_rapports((self.serveur.dossier / "parametres.csv").read_bytes(), VALEUR))
        return config

    def permis(self, config, identite, nom):
        """Vrai si verifier_role laisse lire ce document (le 403 levé sinon)."""
        try:
            serveur.verifier_role(config, identite, ("GET", "documents/<nom>"), nom)
        except serveur.ErreurHttp as erreur:
            self.assertEqual(erreur.statut, 403)
            return False
        return True

    def test_regle_lue_dans_parametres_et_appareil_refuse(self):
        config = self.config()
        self.assertEqual(serveur.rapports_figes(config), {RAPPORT, REVISION})
        self.assertEqual(serveur.rapports_figes(self.config(avec_parametres=False)), set())
        self.assertFalse(self.permis(config, self.APPAREIL, RAPPORT))
        self.assertFalse(self.permis(config, self.TECHNICIEN, RAPPORT))
        self.assertTrue(self.permis(config, self.RESPONSABLE, RAPPORT))
        self.assertTrue(self.permis(config, self.TECHNICIEN, AUTRE))

    def test_a_part_des_documents_reserves_d196(self):
        """D126 est décidé : vider DOCUMENTS_RESERVES_AU_RESPONSABLE (D196) ne rouvre pas les rapports."""
        config = self.config()
        with mock.patch.object(serveur, "DOCUMENTS_RESERVES_AU_RESPONSABLE", ()):
            self.assertFalse(self.permis(config, self.TECHNICIEN, RAPPORT))
            self.assertFalse(self.permis(config, self.TECHNICIEN, REVISION))
            self.assertTrue(self.permis(config, self.TECHNICIEN, AUTRE))


class TestRapportsFigesSansComptes(CasRapportsFiges):

    COMPTES = False

    def test_rien_ne_change(self):
        for nom in (RAPPORT, REVISION, AUTRE):
            with self.subTest(nom=nom):
                self.assertServi(self.document(None, nom), nom)


if __name__ == "__main__":
    unittest.main()
