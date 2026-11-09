"""Droits du serveur sur les tables et documents du format 4 (T445 ; CS178 ; ARCHITECTURE.md §22.5 et §10 RG8).

RÉPONSES PROVISOIRES aux questions 2 et 3 du L3 (nuit du 08 au 09/11/2026), à confirmer par Nicolas ; seul endroit à
changer pour les annuler : TABLES_DU_RESPONSABLE_PROVISOIRES et DOCUMENTS_DU_RESPONSABLE_PROVISOIRES de serveur.py.

Ce qui est vérifié, en mode serveur avec comptes (vraies sessions sur une copie du jeu f4-v2.2.0) :
    habilitations    écrite par le responsable seul : PUT et ajout du technicien refusés (403, même corps que son refus
                     sur parametres), fichier inchangé ; il la lit toujours (justificatif compris) ; demandeur refusé ;
                     le responsable l'écrit (PUT, ajout) ;
    documents        un document cité par habilitations.justificatif ou contrats_prestataires.document (apostrophe de
                     protection comprise) n'est servi qu'au responsable : 403 « ce document n'est pas ouvert » au
                     technicien (même pour son propre justificatif), au demandeur (même si un équipement le cite
                     aussi) ; casse du nom ignorée ; colonnes relues à chaque requête ; documents de garantie et autres
                     documents inchangés ;
    sans comptes     rien ne change (écriture de habilitations, lecture des documents) ;
    un seul endroit  les deux tuples vidés dans une copie du code : le technicien écrit habilitations et lit les
                     justificatifs, comme avant T445.

Aucune donnée réelle : copie temporaire du jeu f4-v2.2.0 (tests/jeux_formats.py). Sans navigateur.
Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_droits_format4.py" -v
"""
import csv
import http.client
import importlib.util
import io
import json
import re
import shutil
import tempfile
import types
import unittest
from pathlib import Path

import commun
from commun import RACINE
from jeux_formats import copier_jeu

SCRIPT = RACINE / "serveur.py"
JEU = "f4-v2.2.0"
AGENT = "tests-prevo/1.0"
BOM = bytes((0xEF, 0xBB, 0xBF))
PDF = b"%PDF-1.4 essai T445\n"

JUSTIFICATIF = "20250310-090000-titre-habilitation-BR.pdf"     # HAB-0001, du technicien du compte (TEC-0001)
CONTRAT = "20260101-080000-contrat-CTP-0001.pdf"               # contrats_prestataires CTP-0001, avec apostrophe
PARTAGE = "20250101-000000-schema-armoire.pdf"                 # justificatif de HAB-0002 ET document de EQ-0005
GARANTIE = "20250601-100000-garantie-GAR-0001.pdf"             # garanties GAR-0001 : reste lisible du technicien
DOCUMENT_EQUIPEMENT = "20250101-000000-notice-cp01.pdf"        # document de EQ-0001 seulement
AUTRE = "20261020-101500-notice-libre.pdf"                     # cité nulle part
NOUVEAU = "20261109-080000-titre-habilitation-H0V.pdf"         # cité ensuite par le responsable (HAB-0003)
DOCUMENTS = (JUSTIFICATIF, CONTRAT, PARTAGE, GARANTIE, DOCUMENT_EQUIPEMENT, AUTRE, NOUVEAU)

REFUS_TABLE = "Accès refusé : la table « habilitations » ne se modifie que par le responsable."
REFUS_DOCUMENT = "Accès refusé : ce document n'est pas ouvert au {role}."

# Lignes du seul endroit à changer (serveur.py), recopiées : le test d'annulation les remplace par « () ».
LIGNE_TABLES = "TABLES_DU_RESPONSABLE_PROVISOIRES = ('habilitations',)"
LIGNE_DOCUMENTS = ("DOCUMENTS_DU_RESPONSABLE_PROVISOIRES = (('habilitations', 'justificatif'), "
                   "('contrats_prestataires', 'document'))")


# ---------------------------------------------------------------------------
# Données d'essai : CSV au format de Prévo, documents
# ---------------------------------------------------------------------------

def lire_tableau(octets):
    """(en-tête, lignes) d'un CSV de Prévo (BOM, « ; »), valeurs telles qu'écrites (apostrophes comprises)."""
    lignes = [ligne for ligne in csv.reader(io.StringIO(octets.decode("utf-8-sig"), newline=""), delimiter=";") if ligne]
    return lignes[0], lignes[1:]


def cellule(texte):
    """Comme celluleCsv de js/donnees.js (§3.1)."""
    return '"' + texte.replace('"', '""') + '"' if re.search(r'[;"\r\n]|\A[ \t]|[ \t]\Z', texte) else texte


def ecrire_tableau(entete, lignes):
    texte = "".join(";".join(cellule(valeur) for valeur in ligne) + "\r\n" for ligne in [entete] + list(lignes))
    return BOM + texte.encode("utf-8")


def avec_cellule(octets, identifiant, colonne, valeur):
    """Octets du CSV où la ligne « identifiant » a « valeur » dans « colonne » (une seule ligne de cet id)."""
    entete, lignes = lire_tableau(octets)
    position = entete.index(colonne)
    trouvees = [ligne for ligne in lignes if ligne[0] == identifiant]
    if len(trouvees) != 1:
        raise AssertionError("%s : %d ligne(s) dans le jeu" % (identifiant, len(trouvees)))
    trouvees[0].extend([""] * (position + 1 - len(trouvees[0])))
    trouvees[0][position] = valeur
    return ecrire_tableau(entete, lignes)


def changer_cellule(chemin, identifiant, colonne, valeur):
    chemin.write_bytes(avec_cellule(chemin.read_bytes(), identifiant, colonne, valeur))


def preparer_source(racine):
    """Copie du jeu f4-v2.2.0 : documents écrits, cités par habilitations, contrats_prestataires, garanties et
    equipements (voir les constantes). Rend le dossier."""
    source = copier_jeu(JEU, racine / "source")
    if JUSTIFICATIF not in (source / "habilitations.csv").read_text(encoding="utf-8-sig"):
        raise AssertionError("le jeu %s ne cite plus %s dans habilitations.csv" % (JEU, JUSTIFICATIF))
    changer_cellule(source / "habilitations.csv", "HAB-0002", "justificatif", PARTAGE)
    changer_cellule(source / "contrats_prestataires.csv", "CTP-0001", "document", "'" + CONTRAT)
    changer_cellule(source / "garanties.csv", "GAR-0001", "document", GARANTIE)
    changer_cellule(source / "equipements.csv", "EQ-0005", "document", PARTAGE)
    changer_cellule(source / "equipements.csv", "EQ-0001", "document", DOCUMENT_EQUIPEMENT)
    documents = source / "documents"
    documents.mkdir(exist_ok=True)
    for nom in DOCUMENTS:
        (documents / nom).write_bytes(PDF + nom.encode("ascii"))
    return source


# ---------------------------------------------------------------------------
# Requêtes
# ---------------------------------------------------------------------------

class Reponse:
    def __init__(self, statut, entetes, octets):
        self.statut, self.entetes, self.octets = statut, entetes, octets

    def json(self):
        return json.loads(self.octets.decode("utf-8"))


def requete(serveur, methode, chemin, corps=None, cookie=None, entetes=None):
    entetes = dict(entetes or {})
    entetes.setdefault("User-Agent", AGENT)
    if cookie:
        entetes["Cookie"] = cookie
    if methode in ("PUT", "POST"):
        entetes.setdefault("X-Prevo", "1")
        corps = b"" if corps is None else corps
    connexion = http.client.HTTPConnection("127.0.0.1", serveur.port, timeout=60)
    try:
        connexion.request(methode, chemin, body=corps, headers=entetes)
        reponse = connexion.getresponse()
        return Reponse(reponse.status, {nom.lower(): valeur for nom, valeur in reponse.getheaders()}, reponse.read())
    finally:
        connexion.close()


def premiere_ligne(octets):
    """Ligne d'en-tête d'un fichier (sans BOM ni fin de ligne) : début d'un corps d'ajout."""
    return octets[len(BOM):].split(b"\r\n", 1)[0] if octets.startswith(BOM) else octets.split(b"\r\n", 1)[0]


class CasServeur(unittest.TestCase):
    """Serveur réel (ServeurPrevo) sur une copie préparée du jeu ; sessions des trois rôles si COMPTES."""

    COMPTES = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.racine = Path(tempfile.mkdtemp(prefix="prevo-droits-f4-"))
        cls.addClassCleanup(shutil.rmtree, cls.racine, True)
        cls.serveur = commun.ServeurPrevo(source=preparer_source(cls.racine), comptes=cls.COMPTES)
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)
        cls.cookies = ({role: cls.serveur.session(role) for role in ("demandeur", "technicien", "responsable")}
                       if cls.COMPTES else {})

    def requete(self, role, methode, chemin, corps=None, entetes=None):
        return requete(self.serveur, methode, chemin, corps, self.cookies.get(role), entetes)

    def fichier(self, table):
        return (self.serveur.dossier / (table + ".csv")).read_bytes()

    def ecrire(self, role, table, octets):
        """PUT de la table entière, avec la version lue par ce rôle."""
        lue = self.requete(role, "GET", "/api/csv/" + table)
        self.assertEqual(lue.statut, 200, lue.octets[:300])
        return self.requete(role, "PUT", "/api/csv/" + table, octets, {"X-Version-Attendue": lue.entetes["x-version"]})

    def assertRefus(self, reponse, message):
        self.assertEqual(reponse.statut, 403, reponse.octets[:300])
        self.assertEqual(reponse.json()["erreur"], message)

    def assertDocument(self, reponse, nom):
        self.assertEqual(reponse.statut, 200, reponse.octets[:300])
        self.assertEqual(reponse.octets, PDF + nom.encode("ascii"))


# ---------------------------------------------------------------------------
# habilitations : écrite par le responsable seul (réponse provisoire Q2)
# ---------------------------------------------------------------------------

class TestHabilitationsDuResponsable(CasServeur):

    def test_technicien_refuse_a_l_ecriture_fichier_inchange_et_lecture_gardee(self):
        avant = self.fichier("habilitations")
        lue = self.requete("technicien", "GET", "/api/csv/habilitations")
        self.assertEqual(lue.statut, 200, lue.octets[:300])
        self.assertEqual(lue.octets, avant)                         # rien de caché : justificatif compris
        self.assertIn(JUSTIFICATIF.encode("ascii"), lue.octets)
        entete = premiere_ligne(avant)
        envoi = self.requete("technicien", "PUT", "/api/csv/habilitations", BOM + entete + b"\r\n",
                             {"X-Version-Attendue": lue.entetes["x-version"]})
        self.assertRefus(envoi, REFUS_TABLE)
        ajout = self.requete("technicien", "POST", "/api/csv/habilitations/ajout",
                             entete + b"\r\nHAB-0901;TEC-0001;H0V;2026-11-01;2029-11-01;;;;\r\n")
        self.assertRefus(ajout, REFUS_TABLE)
        self.assertEqual(self.fichier("habilitations"), avant)

    def test_meme_refus_que_sur_parametres(self):
        """Mêmes codes et corps que le refus existant (acces.table_du_responsable), au nom de table près."""
        for methode, suffixe in (("PUT", ""), ("POST", "/ajout")):
            with self.subTest(methode=methode):
                corps = {}
                for table in ("parametres", "habilitations"):
                    entete = premiere_ligne(self.fichier(table))
                    reponse = self.requete("technicien", methode, "/api/csv/" + table + suffixe,
                                           (BOM if methode == "PUT" else b"") + entete + b"\r\n",
                                           {"X-Version-Attendue": "0" * 16})
                    self.assertEqual(reponse.statut, 403, reponse.octets[:300])
                    corps[table] = reponse.json()
                attendu = json.loads(json.dumps(corps["parametres"], ensure_ascii=False)
                                     .replace("parametres", "habilitations"))
                self.assertEqual(corps["habilitations"], attendu)

    def test_demandeur_ni_lecture_ni_ecriture(self):
        self.assertEqual(self.requete("demandeur", "GET", "/api/csv/habilitations").statut, 403)
        envoi = self.requete("demandeur", "PUT", "/api/csv/habilitations", BOM + b"id\r\n",
                             {"X-Version-Attendue": "0" * 16})
        self.assertEqual(envoi.statut, 403, envoi.octets[:300])

    def test_le_responsable_l_ecrit(self):
        modifie = avec_cellule(self.fichier("habilitations"), "HAB-0002", "date_echeance", "2028-03-11")
        self.assertEqual(self.ecrire("responsable", "habilitations", modifie).statut, 200)
        self.assertEqual(self.fichier("habilitations"), modifie)
        ligne = b"HAB-0902;TEC-0001;H0V;2026-11-01;2029-11-01;;;;\r\n"
        ajout = self.requete("responsable", "POST", "/api/csv/habilitations/ajout",
                             premiere_ligne(modifie) + b"\r\n" + ligne)
        self.assertEqual(ajout.statut, 200, ajout.octets[:300])
        self.assertTrue(self.fichier("habilitations").endswith(ligne))


# ---------------------------------------------------------------------------
# Justificatifs et documents des contrats : au seul responsable (réponse provisoire Q3)
# ---------------------------------------------------------------------------

class TestDocumentsReserves(CasServeur):

    def test_justificatifs_et_contrats_servis_au_seul_responsable(self):
        # JUSTIFICATIF est celui du technicien du compte lui-même : refusé aussi (réponse provisoire : responsable seul).
        for nom in (JUSTIFICATIF, CONTRAT, PARTAGE):
            with self.subTest(nom=nom):
                self.assertDocument(self.requete("responsable", "GET", "/api/documents/" + nom), nom)
                self.assertRefus(self.requete("technicien", "GET", "/api/documents/" + nom),
                                 REFUS_DOCUMENT.format(role="technicien"))
                self.assertRefus(self.requete("demandeur", "GET", "/api/documents/" + nom),
                                 REFUS_DOCUMENT.format(role="demandeur"))

    def test_autres_documents_inchanges(self):
        for nom in (GARANTIE, DOCUMENT_EQUIPEMENT, AUTRE):
            with self.subTest(nom=nom):
                self.assertDocument(self.requete("technicien", "GET", "/api/documents/" + nom), nom)
                self.assertDocument(self.requete("responsable", "GET", "/api/documents/" + nom), nom)
        self.assertDocument(self.requete("demandeur", "GET", "/api/documents/" + DOCUMENT_EQUIPEMENT),
                            DOCUMENT_EQUIPEMENT)
        self.assertEqual(self.requete("demandeur", "GET", "/api/documents/" + GARANTIE).statut, 403)

    def test_casse_du_nom_ignoree(self):
        """Windows et macOS ne distinguent pas la casse : un autre nom ne doit pas ouvrir le même fichier."""
        for nom in (JUSTIFICATIF.upper(), CONTRAT.replace("contrat", "Contrat")):
            with self.subTest(nom=nom):
                self.assertRefus(self.requete("technicien", "GET", "/api/documents/" + nom),
                                 REFUS_DOCUMENT.format(role="technicien"))

    def test_colonnes_relues_a_chaque_requete(self):
        self.assertDocument(self.requete("technicien", "GET", "/api/documents/" + NOUVEAU), NOUVEAU)
        modifie = avec_cellule(self.fichier("habilitations"), "HAB-0003", "justificatif", NOUVEAU)
        self.assertEqual(self.ecrire("responsable", "habilitations", modifie).statut, 200)
        self.assertRefus(self.requete("technicien", "GET", "/api/documents/" + NOUVEAU),
                         REFUS_DOCUMENT.format(role="technicien"))
        self.assertDocument(self.requete("responsable", "GET", "/api/documents/" + NOUVEAU), NOUVEAU)

    def test_envoi_inchange(self):
        """L'envoi d'un document n'est pas touché : le technicien joint toujours un document (201)."""
        envoi = self.requete("technicien", "PUT", "/api/documents/justificatif-essai.pdf", PDF)
        self.assertEqual(envoi.statut, 201, envoi.octets[:300])


# ---------------------------------------------------------------------------
# Sans comptes : rien ne change
# ---------------------------------------------------------------------------

class TestSansComptes(CasServeur):

    COMPTES = False

    def test_rien_ne_change(self):
        modifie = avec_cellule(self.fichier("habilitations"), "HAB-0002", "date_echeance", "2028-03-12")
        self.assertEqual(self.ecrire(None, "habilitations", modifie).statut, 200)
        for nom in (JUSTIFICATIF, CONTRAT, PARTAGE):
            with self.subTest(nom=nom):
                self.assertDocument(self.requete(None, "GET", "/api/documents/" + nom), nom)


# ---------------------------------------------------------------------------
# Un seul endroit pour annuler la réponse provisoire
# ---------------------------------------------------------------------------

def charger_module(nom, texte=None):
    """serveur.py chargé comme module, tel quel ou depuis un texte modifié."""
    if texte is None:
        specification = importlib.util.spec_from_file_location(nom, SCRIPT)
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        return module
    module = types.ModuleType(nom)
    module.__file__ = str(SCRIPT)
    exec(compile(texte, str(SCRIPT), "exec"), module.__dict__)
    return module


class TestUnSeulEndroit(unittest.TestCase):

    TECHNICIEN = {"identifiant": "julien.moreau", "role": "technicien", "technicien_id": "TEC-0001",
                  "appareil": False}

    def setUp(self):
        self.dossier = Path(tempfile.mkdtemp(prefix="prevo-droits-f4-annule-"))
        self.addCleanup(shutil.rmtree, self.dossier, True)

    def permis(self, module, route, segment):
        """Vrai si verifier_role laisse passer le technicien (le 403 levé sinon)."""
        config = module.Configuration(str(self.dossier / module.__name__), [])
        module.creer_dossiers(config)
        source = copier_jeu(JEU, self.dossier / ("jeu-" + module.__name__))
        shutil.copyfile(str(source / "habilitations.csv"), str(Path(config.dossier_donnees) / "habilitations.csv"))
        try:
            module.verifier_role(config, self.TECHNICIEN, route, segment)
        except module.ErreurHttp as erreur:
            self.assertEqual(erreur.statut, 403)
            return False
        return True

    def test_vider_les_deux_tuples_annule_t445(self):
        texte = SCRIPT.read_text(encoding="utf-8")
        for ligne in (LIGNE_TABLES, LIGNE_DOCUMENTS):
            self.assertEqual(texte.count(ligne), 1, ligne)
        annule = texte.replace(LIGNE_TABLES, LIGNE_TABLES.split(" = ")[0] + " = ()")
        annule = annule.replace(LIGNE_DOCUMENTS, LIGNE_DOCUMENTS.split(" = ")[0] + " = ()")
        actuel, avant = charger_module("serveur_t445_actuel"), charger_module("serveur_t445_annule", annule)
        ecriture, document = ("PUT", "csv/<table>"), ("GET", "documents/<nom>")
        self.assertFalse(self.permis(actuel, ecriture, "habilitations"))
        self.assertFalse(self.permis(actuel, document, JUSTIFICATIF))
        # Tables décidées du format 4 (T453) gardées : seul le tuple provisoire de T445 est retiré.
        self.assertEqual(avant.TABLES_DU_RESPONSABLE_EN_ECRITURE, ("parametres", "techniciens", "fournisseurs",
                                                                   "reserves_controle", "garanties",
                                                                   "contrats_prestataires"))
        self.assertTrue(self.permis(avant, ecriture, "habilitations"))
        self.assertTrue(self.permis(avant, ("POST", "csv/<table>/ajout"), "habilitations"))
        self.assertTrue(self.permis(avant, document, JUSTIFICATIF))
        self.assertFalse(self.permis(avant, ecriture, "parametres"))     # le reste des droits ne bouge pas


if __name__ == "__main__":
    unittest.main()
