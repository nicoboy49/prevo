"""Fichiers d'essai de l'import (lot 5, tâche T79 ; docs/ARCHITECTURE.md §18.10 ; CS81, CS89).

Ce qui est vérifié :
  - outils/generer_fixtures_import.py, relancé dans un dossier temporaire, réécrit exactement les fichiers de
    tests/fixtures/import/ (mêmes noms, mêmes octets ; le .xls aussi : SheetJS 0.20.3 écrit le BIFF8 de façon
    déterministe, aucune date du jour) ;
  - chaque fichier contient les pièges qu'annonce tests/fixtures/import/LISEZMOI.md, relus en Python SANS
    SheetJS : .xlsx par zipfile + XML (titre au-dessus de l'en-tête, colonnes dans le désordre, colonne inconnue,
    « 007 » en texte, dates en numéros de série 1900 avec un style de date, chaîne « en ligne »), .ods par
    zipfile + XML (mimetype non compressé en premier, cellules et lignes répétées, mêmes données que le .xlsx),
    CSV par le module csv (Windows-1252 et UTF-8 vérifiés par décodage, BOM, séparateurs, fins de ligne),
    collages tabulés, plafonds de lignes (20 001 et 20 000 lignes de données), conteneur OLE et flux
    EncryptionInfo, fichiers vides, bombe de cellules répétées ;
  - les repères, codes, techniciens et fournisseurs « existants » le sont dans donnees/demo/, les nouveaux non ;
  - SheetJS 0.20.3 dans Chromium lit le .xlsx, le .ods et le .xls en une même grille, égale à la lecture
    Python ; gammes.xlsx aussi ; chiffre.xlsx est refusé comme protégé par mot de passe.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_fixtures_import.py" -v
"""
import base64
import csv
import io
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, timedelta
from pathlib import Path

import commun
from commun import RACINE, CasNavigateur, charger_scripts

DOSSIER = RACINE / "tests" / "fixtures" / "import"
GENERATEUR = RACINE / "outils" / "generer_fixtures_import.py"
DEMO = RACINE / "donnees" / "demo"

FICHIERS = (
    "LISEZMOI.md", "equipements.xlsx", "equipements.ods", "equipements.xls", "articles.csv", "fournisseurs.tsv",
    "techniciens.tsv", "habilitations.csv", "codes.csv", "compteurs.csv", "controles.csv", "gammes.xlsx",
    "historique.csv", "trop_de_lignes.csv", "limite_de_lignes.csv", "chiffre.xlsx", "vide.csv",
    "lignes_vides.csv", "sans_entete.csv", "cellules_repetees.ods",
)
TITRE_PARC = "Liste du parc — atelier"
ENTETES_PARC = ["Désignation", "Code machine", "Fabricant", "Mise en service", "Emplacement", "N° de série",
                "Criticité", "Machine mère", "Commentaire"]
NOUVEAUX_REPERES = {"CP-01.PUR", "CP-02", "007", "007.TA", "SC-02", "PE-02", "TR-01", "MT-01"}
ENTETES_HISTORIQUE = ["N° OT", "Machine", "Date demande", "Début", "Fin", "Type", "Libellé", "Compte rendu",
                      "Durée arrêt (h)", "Arrêt", "Symptôme", "Cause", "Remède", "Intervenant", "Temps (h)"]
SIGNATURE_OLE = bytes([0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1])
BOM = b"\xef\xbb\xbf"
INSECABLE = chr(0xA0)
DATE_ZIP = (1980, 1, 1, 0, 0, 0)
TYPE_ODS = b"application/vnd.oasis.opendocument.spreadsheet"

NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
NS_PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"
NS_TABLE = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
NS_OFFICE = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"
NS_TEXT = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"


# ---------------------------------------------------------------------------
# Lectures Python indépendantes de SheetJS
# ---------------------------------------------------------------------------

def nombre_texte(texte):
    """« 30 » → « 30 », « 0.75 » → « 0.75 », « 44333.0 » → « 44333 »."""
    valeur = float(texte)
    return str(int(valeur)) if valeur.is_integer() else repr(valeur)


def colonne_index(lettres):
    index = 0
    for lettre in lettres:
        index = index * 26 + (ord(lettre) - 64)
    return index - 1


def nettoyer(grille):
    """Grille sans cellules vides en fin de ligne ni lignes vides en fin de feuille."""
    lignes = []
    for ligne in grille:
        ligne = list(ligne)
        while ligne and ligne[-1] == "":
            ligne.pop()
        lignes.append(ligne)
    while lignes and not lignes[-1]:
        lignes.pop()
    return lignes


def lire_xlsx(chemin):
    """→ (grilles texte {feuille: [[texte]]}, cellules brutes {feuille: {(ligne, colonne): (t, s, v)}}, formats).

    Texte d'une cellule : chaîne partagée ou en ligne telle quelle ; nombre au style de date → AAAA-MM-JJ
    (système 1900) ; autre nombre → son texte sans arrondi."""
    with zipfile.ZipFile(chemin) as archive:
        classeur = ET.fromstring(archive.read("xl/workbook.xml"))
        relations = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        cibles = {r.get("Id"): r.get("Target") for r in relations.iter(NS_PKG + "Relationship")}
        partagees = []
        if "xl/sharedStrings.xml" in archive.namelist():
            for si in ET.fromstring(archive.read("xl/sharedStrings.xml")).iter(NS_MAIN + "si"):
                partagees.append("".join(t.text or "" for t in si.iter(NS_MAIN + "t")))
        styles = ET.fromstring(archive.read("xl/styles.xml"))
        formats = {int(f.get("numFmtId")): f.get("formatCode") for f in styles.iter(NS_MAIN + "numFmt")}
        xfs = [int(xf.get("numFmtId", "0")) for xf in styles.find(NS_MAIN + "cellXfs").findall(NS_MAIN + "xf")]

        def est_date(style):
            identifiant = xfs[style]
            if 14 <= identifiant <= 22:
                return True
            code = re.sub(r'"[^"]*"', "", formats.get(identifiant, "")).lower()
            return bool(re.search(r"[dmy]", code))

        grilles, brutes = {}, {}
        for feuille in classeur.iter(NS_MAIN + "sheet"):
            nom = feuille.get("name")
            xml = ET.fromstring(archive.read("xl/" + cibles[feuille.get(NS_REL + "id")]))
            cellules = {}
            for c in xml.iter(NS_MAIN + "c"):
                lettres, numero = re.fullmatch(r"([A-Z]+)(\d+)", c.get("r")).groups()
                v = c.find(NS_MAIN + "v")
                texte_is = c.find(NS_MAIN + "is")
                cellules[(int(numero) - 1, colonne_index(lettres))] = (
                    c.get("t"), int(c.get("s", "0")),
                    "".join(t.text or "" for t in texte_is.iter(NS_MAIN + "t")) if texte_is is not None
                    else (v.text if v is not None else None))
            hauteur = max((r for r, _c in cellules), default=-1) + 1
            largeur = max((c for _r, c in cellules), default=-1) + 1
            grille = [[""] * largeur for _ in range(hauteur)]
            for (r, colonne), (t, s, v) in cellules.items():
                if t == "s":
                    texte = partagees[int(v)]
                elif t in ("inlineStr", "str"):
                    texte = v
                elif est_date(s):
                    texte = (date(1899, 12, 30) + timedelta(days=int(float(v)))).isoformat()
                else:
                    texte = nombre_texte(v)
                grille[r][colonne] = texte
            grilles[nom] = nettoyer(grille)
            brutes[nom] = cellules
        return grilles, brutes, (formats, xfs)


def valeur_ods(cellule):
    genre = cellule.get(NS_OFFICE + "value-type")
    if genre is None:
        return ""
    if genre in ("float", "percentage", "currency"):
        return nombre_texte(cellule.get(NS_OFFICE + "value"))
    if genre == "date":
        return cellule.get(NS_OFFICE + "date-value")[:10]
    return "\n".join("".join(p.itertext()) for p in cellule.findall(NS_TEXT + "p"))


def lire_ods(chemin, repetitions_max=10000):
    """→ {feuille: [[texte]]} : cellules et lignes répétées développées ; une cellule NON vide répétée plus de
    repetitions_max fois lève ValueError (bombe) au lieu d'être développée."""
    with zipfile.ZipFile(chemin) as archive:
        racine = ET.fromstring(archive.read("content.xml"))
    feuilles = {}
    for table in racine.iter(NS_TABLE + "table"):
        grille, vides_en_attente = [], 0
        for ligne in table.iter(NS_TABLE + "table-row"):
            repetee = int(ligne.get(NS_TABLE + "number-rows-repeated", "1"))
            cellules = []
            for cellule in ligne:
                if cellule.tag not in (NS_TABLE + "table-cell", NS_TABLE + "covered-table-cell"):
                    continue
                fois = int(cellule.get(NS_TABLE + "number-columns-repeated", "1"))
                valeur = valeur_ods(cellule)
                if valeur and fois > repetitions_max:
                    raise ValueError("cellule non vide répétée %d fois" % fois)
                cellules.extend([valeur] * fois)
            while cellules and cellules[-1] == "":
                cellules.pop()
            if not cellules:
                vides_en_attente += repetee
                continue
            grille.extend([[] for _ in range(vides_en_attente)])
            vides_en_attente = 0
            grille.extend([list(cellules) for _ in range(repetee)])
        feuilles[table.get(NS_TABLE + "name")] = nettoyer(grille)
    return feuilles


def lire_csv(nom, encodage, separateur):
    octets = (DOSSIER / nom).read_bytes()
    texte = octets.decode(encodage)
    if texte.startswith(chr(0xFEFF)):
        texte = texte[1:]
    return list(csv.reader(io.StringIO(texte, newline=""), delimiter=separateur))


def flux_cfb(octets):
    """Entrées du répertoire d'un fichier OLE/CFB : [(nom, type, secteur de départ, taille)]."""
    taille_secteur = 1 << struct.unpack_from("<H", octets, 0x1E)[0]
    nb_fat, premier_repertoire = struct.unpack_from("<II", octets, 0x2C)
    difat = struct.unpack_from("<109I", octets, 0x4C)
    fat = []
    for secteur in difat[:nb_fat]:
        fat += struct.unpack_from("<%dI" % (taille_secteur // 4), octets, 512 + secteur * taille_secteur)
    entrees, secteur, vus = [], premier_repertoire, set()
    while secteur != 0xFFFFFFFE and secteur not in vus:
        vus.add(secteur)
        debut = 512 + secteur * taille_secteur
        for i in range(taille_secteur // 128):
            entree = octets[debut + i * 128:debut + (i + 1) * 128]
            longueur, genre = struct.unpack_from("<HB", entree, 64)
            if genre:
                nom = entree[:max(0, longueur - 2)].decode("utf-16-le")
                depart, taille = struct.unpack_from("<IQ", entree, 116)
                entrees.append((nom, genre, depart, taille))
        secteur = fat[secteur]
    return entrees


def lire_demo(table):
    with open(DEMO / (table + ".csv"), encoding="utf-8-sig", newline="") as fichier:
        return [{cle: (valeur[1:] if valeur.startswith("'") else valeur) for cle, valeur in ligne.items()}
                for ligne in csv.DictReader(fichier, delimiter=";")]


def lignes_non_vides(nom):
    texte = (DOSSIER / nom).read_bytes().decode("utf-8-sig")
    return [ligne for ligne in texte.split("\r\n") if ligne.strip(";")]


# ---------------------------------------------------------------------------
# Régénération identique à l'octet
# ---------------------------------------------------------------------------

class TestRegeneration(unittest.TestCase):
    """Le générateur relancé dans un dossier temporaire réécrit exactement les fichiers du dépôt."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dossier = Path(tempfile.mkdtemp(prefix="prevo-fixtures-import-"))
        cls.addClassCleanup(shutil.rmtree, cls.dossier, True)
        cls.avec_xls = commun.sync_playwright is not None
        commande = [sys.executable, str(GENERATEUR), "--sortie", str(cls.dossier)]
        if not cls.avec_xls:
            commande.append("--sans-xls")
        resultat = subprocess.run(commande, cwd=str(RACINE), capture_output=True, timeout=600,
                                  env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        if resultat.returncode != 0:
            raise AssertionError("le générateur a échoué (code %d) :\n%s" % (
                resultat.returncode, (resultat.stdout + resultat.stderr).decode("utf-8", "replace")))

    def test_memes_fichiers(self):
        attendus = set(FICHIERS) - (set() if self.avec_xls else {"equipements.xls"})
        produits = {chemin.name for chemin in self.dossier.iterdir()}
        self.assertEqual(produits, attendus)
        livres = {chemin.name for chemin in DOSSIER.iterdir()}
        self.assertEqual(livres, set(FICHIERS), "fichiers en trop ou manquants dans tests/fixtures/import/")

    def test_memes_octets(self):
        for chemin in sorted(self.dossier.iterdir()):
            with self.subTest(fichier=chemin.name):
                self.assertEqual(chemin.read_bytes(), (DOSSIER / chemin.name).read_bytes(),
                                 "%s régénéré diffère du fichier du dépôt : relancer "
                                 "py outils/generer_fixtures_import.py" % chemin.name)


# ---------------------------------------------------------------------------
# Pièges de chaque fichier (lecture Python)
# ---------------------------------------------------------------------------

class TestEquipementsXlsx(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.grilles, cls.brutes, (cls.formats, cls.xfs) = lire_xlsx(DOSSIER / "equipements.xlsx")
        cls.parc = cls.grilles["Parc"]
        cls.par_repere = {ligne[1]: (numero, ligne) for numero, ligne in enumerate(cls.parc[2:], 3)}
        cls.demo = {e["repere"]: e for e in lire_demo("equipements")}

    def test_archive_ooxml_minimale_et_dates_fixes(self):
        with zipfile.ZipFile(DOSSIER / "equipements.xlsx") as archive:
            noms = archive.namelist()
            self.assertEqual(noms[:6], ["[Content_Types].xml", "_rels/.rels", "xl/workbook.xml",
                                        "xl/_rels/workbook.xml.rels", "xl/styles.xml", "xl/sharedStrings.xml"])
            self.assertEqual(noms[6:], ["xl/worksheets/sheet1.xml", "xl/worksheets/sheet2.xml"])
            self.assertTrue(all(info.date_time == DATE_ZIP for info in archive.infolist()))
            self.assertNotIn(b"date1904", archive.read("xl/workbook.xml"), "système de dates 1900 attendu")
        self.assertEqual(list(self.grilles), ["Parc", "Notes"])

    def test_titre_au_dessus_de_l_entete(self):
        self.assertEqual(self.parc[0], [TITRE_PARC])
        self.assertEqual(self.brutes["Parc"][(0, 0)][0], "inlineStr", "titre en chaîne « en ligne »")
        self.assertEqual(self.parc[1], ENTETES_PARC)
        self.assertEqual(self.brutes["Parc"][(1, 0)][0], "s", "en-tête en chaînes partagées")

    def test_colonnes_dans_le_desordre_et_colonne_inconnue(self):
        entetes = self.parc[1]
        self.assertGreater(entetes.index("Code machine"), entetes.index("Désignation"))
        self.assertGreater(entetes.index("Emplacement"), entetes.index("Mise en service"))
        self.assertIn("Commentaire", entetes)
        self.assertTrue(any(ligne[8] for ligne in self.parc[2:] if len(ligne) > 8), "colonne inconnue remplie")

    def test_repere_007_en_texte(self):
        numero, ligne = self.par_repere["007"]
        self.assertEqual(self.brutes["Parc"][(numero - 1, 1)][0], "s", "« 007 » doit être une chaîne")
        self.assertEqual(ligne[1], "007")
        numero_pur, ligne_pur = self.par_repere["CP-01.PUR"]
        self.assertEqual(ligne_pur[5], "1E5")
        self.assertEqual(self.brutes["Parc"][(numero_pur - 1, 5)][0], "s")
        self.assertEqual(self.par_repere["RA-01"][1][5], self.demo["RA-01"]["num_serie"])
        self.assertTrue(self.demo["RA-01"]["num_serie"].startswith("0"))

    def test_dates_en_numero_de_serie_1900_avec_style_de_date(self):
        numero, ligne = self.par_repere["007"]
        t, style, valeur = self.brutes["Parc"][(numero - 1, 3)]
        self.assertIsNone(t)
        self.assertEqual(valeur, "44333")                       # 2021-05-17 dans le système 1900
        self.assertEqual(ligne[3], "2021-05-17")
        self.assertEqual(self.xfs[style], 164)
        self.assertEqual(self.formats[164], "dd/mm/yyyy")
        series = [self.brutes["Parc"][(n - 1, 3)] for n, _l in self.par_repere.values()
                  if (n - 1, 3) in self.brutes["Parc"]]
        self.assertGreaterEqual(sum(1 for t, s, _v in series if t is None and s == 1), 20)
        numero_pur, ligne_pur = self.par_repere["CP-01.PUR"]
        self.assertEqual(self.brutes["Parc"][(numero_pur - 1, 3)][0], "s", "une date écrite en texte")
        self.assertEqual(ligne_pur[3], "15/03/2024")
        self.assertNotIn((self.par_repere["MT-01"][0] - 1, 3), self.brutes["Parc"], "une date vide")

    def test_localisation_nouvelle_parent_plus_bas_et_erreurs(self):
        chemins = {libelle["libelle"] for libelle in lire_demo("localisations")}
        numero_007, ligne_007 = self.par_repere["007"]
        niveaux = ligne_007[4].split(" > ")
        self.assertEqual(len(niveaux), 3)
        self.assertIn(niveaux[0], chemins)
        self.assertIn(niveaux[1], chemins)
        self.assertNotIn(niveaux[2], chemins, "la ligne de la localisation doit être nouvelle")
        numero_ta, ligne_ta = self.par_repere["007.TA"]
        self.assertEqual(ligne_ta[7], "007")
        self.assertGreater(numero_ta, numero_007, "le parent est cité plus bas que sa propre ligne")
        self.assertEqual(self.par_repere["CP-01.PUR"][1][7], "CP-01")
        self.assertIn(" / ", self.par_repere["PO-02"][1][4], "un chemin écrit avec « / »")
        self.assertEqual(self.par_repere["SC-02"][1][6], "Z")
        self.assertEqual(self.par_repere["TR-01"][1][0], "")
        self.assertEqual(self.par_repere["PE-02"][1][7], "XX-99")
        self.assertNotIn("XX-99", self.demo)

    def test_reperes_existants_et_nouveaux(self):
        reperes = set(self.par_repere)
        self.assertEqual(len(reperes), len(self.parc) - 2, "un repère par ligne de données")
        for repere in sorted(reperes - NOUVEAUX_REPERES):
            with self.subTest(repere=repere):
                self.assertIn(repere, self.demo)
                existant = self.demo[repere]
                ligne = self.par_repere[repere][1]
                self.assertEqual((ligne[0], ligne[2], ligne[3], ligne[5]),
                                 (existant["designation"], existant["marque"], existant["date_mes"],
                                  existant["num_serie"]))
        for repere in sorted(NOUVEAUX_REPERES):
            self.assertNotIn(repere, self.demo)
        self.assertEqual(self.demo["PO-02"]["criticite"], "B")
        self.assertEqual(self.par_repere["PO-02"][1][6], "A", "mise à jour de la criticité")

    def test_feuille_notes(self):
        self.assertEqual(len(self.grilles["Notes"]), 2)


class TestEquipementsOdsEtXls(unittest.TestCase):

    def test_ods_archive(self):
        with zipfile.ZipFile(DOSSIER / "equipements.ods") as archive:
            premiere = archive.infolist()[0]
            self.assertEqual(premiere.filename, "mimetype")
            self.assertEqual(premiere.compress_type, zipfile.ZIP_STORED)
            self.assertEqual(archive.read("mimetype"), TYPE_ODS)
            self.assertIn("META-INF/manifest.xml", archive.namelist())
            self.assertIn("content.xml", archive.namelist())
            self.assertTrue(all(info.date_time == DATE_ZIP for info in archive.infolist()))
        brut = (DOSSIER / "equipements.ods").read_bytes()
        self.assertEqual(brut[30:38], b"mimetype", "mimetype en tête de l'archive, sans champ extra")

    def test_ods_cellules_et_lignes_repetees(self):
        with zipfile.ZipFile(DOSSIER / "equipements.ods") as archive:
            contenu = archive.read("content.xml").decode("utf-8")
        self.assertIn("table:number-columns-repeated", contenu)
        self.assertIn("table:number-rows-repeated", contenu)
        self.assertRegex(contenu, r'<table:table-cell table:number-columns-repeated="\d+"/>'
                                  r'<table:table-cell office:value-type="string">',
                         "des cellules vides répétées AU MILIEU d'une ligne (suivies d'une cellule remplie)")
        self.assertIn('office:value-type="date" office:date-value="2021-05-17"', contenu)

    def test_ods_memes_donnees_que_le_xlsx(self):
        xlsx, _b, _f = lire_xlsx(DOSSIER / "equipements.xlsx")
        self.assertEqual(lire_ods(DOSSIER / "equipements.ods"), xlsx)

    def test_xls_ancien_format(self):
        octets = (DOSSIER / "equipements.xls").read_bytes()
        self.assertEqual(octets[:8], SIGNATURE_OLE)
        noms = [nom for nom, genre, _d, _t in flux_cfb(octets) if genre == 2]
        self.assertIn("Workbook", noms, "flux BIFF8 « Workbook »")


class TestTextes(unittest.TestCase):

    def test_articles_windows_1252(self):
        octets = (DOSSIER / "articles.csv").read_bytes()
        with self.assertRaises(UnicodeDecodeError):
            octets.decode("utf-8")
        self.assertFalse(octets.startswith(BOM))
        for caractere, code in (("Œ", 0x8C), ("’", 0x92), ("Ø", 0xD8), (INSECABLE, 0xA0)):
            self.assertIn(bytes([code]), octets, "caractère %r écrit en Windows-1252" % caractere)
        self.assertIn(b"\r\n", octets)
        self.assertNotRegex(octets.replace(b"\r\n", b""), rb"[\r\n]")
        lignes = lire_csv("articles.csv", "cp1252", ";")
        self.assertEqual(lignes[0][0], "Code article")
        self.assertEqual(len(lignes), 13)
        self.assertTrue(all(len(ligne) == 12 for ligne in lignes))
        references = [ligne[0] for ligne in lignes[1:]]
        self.assertEqual(references.count("ROU-101"), 2, "une référence en double dans le fichier")
        existantes = {a["reference"] for a in lire_demo("articles")}
        self.assertIn("ROU-001", existantes)
        self.assertIn("FIL-001", existantes)
        prix = {ligne[0]: ligne[9] for ligne in lignes[1:]}
        self.assertEqual(prix["ROU-001"], "5,15")
        self.assertEqual(prix["VAR-001"], "1" + INSECABLE + "250,00")
        fournisseurs_demo = {f["nom"] for f in lire_demo("fournisseurs")}
        self.assertIn("Boulonnerie des Cimes", {ligne[10] for ligne in lignes[1:]})
        self.assertNotIn("Boulonnerie des Cimes", fournisseurs_demo)
        stocks = {ligne[0]: ligne[7] for ligne in lignes[1:]}
        self.assertEqual(stocks["LUB-010"], "0")
        self.assertEqual(stocks["FIX-011"], "")
        self.assertIn("2 semaines", [ligne[11] for ligne in lignes])

    def test_collages_tabules(self):
        for nom, colonnes in (("fournisseurs.tsv", 4), ("techniciens.tsv", 5)):
            with self.subTest(fichier=nom):
                octets = (DOSSIER / nom).read_bytes()
                texte = octets.decode("utf-8")
                self.assertFalse(octets.startswith(BOM))
                self.assertTrue(texte.endswith("\r\n"), "CRLF jusqu'à la dernière ligne, comme un collage Excel")
                lignes = texte[:-2].split("\r\n")
                self.assertTrue(all(ligne.count("\t") == colonnes - 1 for ligne in lignes))
                self.assertNotIn(";", texte)
        fournisseurs = lire_csv("fournisseurs.tsv", "utf-8", "\t")
        self.assertIn(["Soudure et Métallerie du Guiers", "", "", ""], fournisseurs, "cellules finales vides")
        self.assertIn("04 79 10 20 30", [ligne[2] for ligne in fournisseurs])
        demo = {(t["nom"], t["prenom"]) for t in lire_demo("techniciens")}
        techniciens = {(ligne[0], ligne[1]) for ligne in lire_csv("techniciens.tsv", "utf-8", "\t")[1:]}
        self.assertLessEqual(demo, techniciens, "les techniciens de la démo sont dans le collage")
        self.assertIn(("", "Lucas"), techniciens)

    def test_habilitations(self):
        octets = (DOSSIER / "habilitations.csv").read_bytes()
        self.assertTrue(octets.startswith(BOM))
        lignes = lire_csv("habilitations.csv", "utf-8", ";")
        self.assertEqual(lignes[0], ["Technicien", "Habilitation", "Obtenue le", "Valable jusqu'au"])
        noms = [ligne[0] for ligne in lignes[1:]]
        self.assertIn("Julien Moreau", noms)            # Prénom Nom
        self.assertIn("Garnier Thomas", noms)           # Nom Prénom
        self.assertIn("Paul Dumas", noms)
        self.assertNotIn("Dumas", {t["nom"] for t in lire_demo("techniciens")})
        self.assertIn("31/02/2026", [ligne[2] for ligne in lignes])

    def test_codes(self):
        octets = (DOSSIER / "codes.csv").read_bytes()
        self.assertFalse(octets.startswith(BOM))
        self.assertNotIn(b"\r", octets, "fins de ligne LF")
        lignes = lire_csv("codes.csv", "utf-8", ";")
        self.assertEqual(lignes[0], ["Famille", "Code", "Libellé"])
        familles = {ligne[0] for ligne in lignes[1:]}
        self.assertGreaterEqual(len(familles), 7, "familles écrites librement")
        self.assertIn("Défaut", familles)
        demo = {(c["code"], c["libelle"]) for c in lire_demo("codes_defaillance")}
        presents = {(ligne[1], ligne[2]) for ligne in lignes[1:]}
        self.assertIn(("S01", "Fuite"), presents, "un code existant")
        self.assertLessEqual(demo, presents)
        cles = [(ligne[0].lower(), ligne[1]) for ligne in lignes[1:]]
        self.assertEqual(cles.count(("cause", "C15")), 2, "même famille + code deux fois")

    def test_compteurs_et_controles(self):
        octets = (DOSSIER / "compteurs.csv").read_bytes()
        with self.assertRaises(UnicodeDecodeError):
            octets.decode("utf-8")
        compteurs = lire_csv("compteurs.csv", "cp1252", ";")
        self.assertEqual(compteurs[0], ["Repère", "Libellé", "Unité"])
        reperes_demo = {e["repere"] for e in lire_demo("equipements")}
        reperes = [ligne[0] for ligne in compteurs[1:]]
        self.assertEqual({r for r in reperes if r not in reperes_demo}, {"007", ""})
        self.assertTrue((DOSSIER / "controles.csv").read_bytes().startswith(BOM))
        controles = lire_csv("controles.csv", "utf-8", ";")
        self.assertEqual(controles[0][0], "Équipement")
        self.assertTrue(any(";" in cellule for ligne in controles for cellule in ligne), "« ; » entre guillemets")
        self.assertEqual({ligne[0] for ligne in controles[1:]} - reperes_demo, {"XX-99"})
        self.assertIn("12 mois", [ligne[3] for ligne in controles])

    def test_historique_autre_gmao(self):
        octets = (DOSSIER / "historique.csv").read_bytes()
        texte = octets.decode("utf-8")
        self.assertFalse(octets.startswith(BOM))
        lignes = lire_csv("historique.csv", "utf-8", ",")
        self.assertEqual(lignes[0], ENTETES_HISTORIQUE)
        donnees = [dict(zip(ENTETES_HISTORIQUE, ligne)) for ligne in lignes[1:]]
        self.assertTrue(15 <= len(donnees) <= 20, "une quinzaine de lignes")
        self.assertTrue(all(len(ligne) == 15 for ligne in lignes))
        for ligne in donnees:
            for colonne in ("Date demande", "Début", "Fin"):
                if ligne[colonne]:
                    self.assertRegex(ligne[colonne], r"^\d{2}/\d{2}/\d{4} \d{2}:\d{2}$")
        numeros = [ligne["N° OT"] for ligne in donnees]
        self.assertTrue(any(numeros.count(n) == 2 for n in numeros), "un même N° OT deux fois (doublon sûr)")
        cles = [(l["Machine"], l["Date demande"], l["Libellé"]) for l in donnees if l["Date demande"]]
        doublons = [c for c in set(cles) if cles.count(c) > 1]
        self.assertTrue(any(len({l["N° OT"] for l in donnees if (l["Machine"], l["Date demande"], l["Libellé"]) == c})
                            > 1 for c in doublons), "doublon supposé : même machine, date, libellé, autre numéro")
        self.assertTrue(any(not l["Date demande"] and not l["Début"] for l in donnees), "une ligne sans date")
        self.assertTrue(any(l["Arrêt"] == "oui" and not l["Durée arrêt (h)"] for l in donnees),
                        "un arrêt sans durée d'arrêt")
        self.assertTrue(any(l["Arrêt"] == "non" and not l["Durée arrêt (h)"] for l in donnees))
        self.assertTrue(any(l["Type"] == "" for l in donnees))
        self.assertLessEqual({"Dépannage", "Curatif", "Préventif"}, {l["Type"] for l in donnees})
        self.assertIn("\n", "".join(l["Compte rendu"] for l in donnees), "compte rendu sur deux lignes")
        self.assertIn('"DN10"', texte.replace('""', '"'))
        self.assertIn('"1,75"', texte)
        ot = next(o for o in lire_demo("ordres_travail") if o["id"] == "OT-2025-0002")
        self.assertTrue(any(l["Libellé"] == ot["titre"] for l in donnees), "doublon supposé d'un OT existant")
        libelles = {c["libelle"].lower() for c in lire_demo("codes_defaillance")}
        codes = {c["code"] for c in lire_demo("codes_defaillance")}
        valeurs = {l[col] for l in donnees for col in ("Symptôme", "Cause", "Remède") if l[col]}
        self.assertIn("Usure générale", valeurs)
        self.assertNotIn("usure générale", libelles)
        self.assertTrue(valeurs & codes and {v.lower() for v in valeurs} & libelles,
                        "codes donnés par code et par libellé")
        intervenants = {l["Intervenant"] for l in donnees}
        self.assertIn("Pierre Martel", intervenants)
        self.assertIn("GARNIER Thomas", intervenants)
        self.assertEqual({l["Machine"] for l in donnees} - {e["repere"] for e in lire_demo("equipements")},
                         {"XX-99"})

    def test_plafonds_de_lignes(self):
        trop = lignes_non_vides("trop_de_lignes.csv")
        limite = lignes_non_vides("limite_de_lignes.csv")
        self.assertEqual(trop[0], "Référence;Désignation;Qté stock")
        self.assertEqual(len(trop), 1 + 20001, "1 ligne d'en-tête + 20 001 lignes de données")
        self.assertEqual(limite[0], trop[0])
        self.assertEqual(len(limite), 1 + 20000, "1 ligne d'en-tête + 20 000 lignes de données (accepté)")
        self.assertLess((DOSSIER / "trop_de_lignes.csv").stat().st_size, 10 * 1024 * 1024,
                        "c'est le nombre de lignes qui dépasse, pas la taille")

    def test_vide_et_sans_entete(self):
        self.assertEqual((DOSSIER / "vide.csv").stat().st_size, 0)
        lignes = lire_csv("lignes_vides.csv", "utf-8", ";")
        self.assertTrue(lignes)
        self.assertFalse(any(cellule.strip() for ligne in lignes for cellule in ligne), "aucune cellule remplie")
        sans_entete = lire_csv("sans_entete.csv", "utf-8", ";")
        self.assertGreaterEqual(len(sans_entete), 3)
        for ligne in sans_entete:
            for cellule in ligne:
                self.assertRegex(cellule, r"^\d+(,\d+)?$", "uniquement des nombres")


class TestFichiersPieges(unittest.TestCase):

    def test_chiffre_conteneur_ole_avec_encryption_info(self):
        octets = (DOSSIER / "chiffre.xlsx").read_bytes()
        self.assertEqual(octets[:8], SIGNATURE_OLE)
        self.assertEqual(len(octets) % 512, 0)
        entrees = {nom: (genre, taille) for nom, genre, _d, taille in flux_cfb(octets)}
        self.assertEqual(entrees["Root Entry"][0], 5)
        self.assertEqual(entrees["EncryptionInfo"][0], 2)
        self.assertEqual(entrees["EncryptedPackage"], (2, 6024))
        debut = octets.index(b"<?xml")
        self.assertEqual(struct.unpack_from("<HHI", octets, debut - 8), (4, 4, 0x40), "chiffrement agile 4.4")
        self.assertIn(b'<encryption xmlns="http://schemas.microsoft.com/office/2006/encryption"', octets)
        self.assertFalse(zipfile.is_zipfile(DOSSIER / "chiffre.xlsx"), "pas une archive ZIP malgré son nom")

    def test_bombe_ods_petite_et_repetee(self):
        chemin = DOSSIER / "cellules_repetees.ods"
        self.assertLess(chemin.stat().st_size, 2048, "archive petite")
        with zipfile.ZipFile(chemin) as archive:
            self.assertEqual(archive.infolist()[0].filename, "mimetype")
            contenu = archive.read("content.xml").decode("utf-8")
        self.assertLess(len(contenu), 4096)
        self.assertRegex(contenu, r'<table:table-cell table:number-columns-repeated="1000000" '
                                  r'office:value-type="string"><text:p>x</text:p>',
                         "une cellule NON vide répétée 1 000 000 de fois")
        with self.assertRaises(ValueError):
            lire_ods(chemin)

    def test_lisezmoi_decrit_chaque_fichier(self):
        texte = (DOSSIER / "LISEZMOI.md").read_text(encoding="utf-8")
        for nom in FICHIERS:
            if nom != "LISEZMOI.md":
                self.assertIn(nom, texte)
        for annonce in ("20 001", "20 000", "doublon supposé", "doublon sûr", "number-columns-repeated",
                        "number-rows-repeated", "EncryptionInfo", "Windows-1252", "Ancien n° :"):
            self.assertIn(annonce, texte)


# ---------------------------------------------------------------------------
# Lecture par SheetJS 0.20.3 dans Chromium
# ---------------------------------------------------------------------------

JS_GRILLES = """([b64]) => {
  const classeur = XLSX.read(b64, { type: 'base64', cellNF: true });   // cellNF : format de date de la cellule
  const deux = (n) => String(n).padStart(2, '0');
  const texte = (cellule) => {
    if (!cellule || cellule.v === undefined || cellule.v === null) return '';
    if (cellule.t === 'd') {
      const d = cellule.v;
      return d.getFullYear() + '-' + deux(d.getMonth() + 1) + '-' + deux(d.getDate());
    }
    if (cellule.t === 'n' && cellule.z && XLSX.SSF.is_date(cellule.z)) {
      const d = XLSX.SSF.parse_date_code(cellule.v);
      return d.y + '-' + deux(d.m) + '-' + deux(d.d);
    }
    return String(cellule.v);
  };
  const resultat = {};
  for (const nom of classeur.SheetNames) {
    const ws = classeur.Sheets[nom];
    const plage = XLSX.utils.decode_range(ws['!ref']);
    const grille = [];
    for (let r = plage.s.r; r <= plage.e.r; r++) {
      const ligne = [];
      for (let c = plage.s.c; c <= plage.e.c; c++) ligne.push(texte(ws[XLSX.utils.encode_cell({ r, c })]));
      grille.push(ligne);
    }
    resultat[nom] = grille;
  }
  return { feuilles: classeur.SheetNames, grilles: resultat };
}"""


class TestLectureSheetJS(CasNavigateur):
    """SheetJS 0.20.3 (js/lib/) lit les trois formats de la liste du parc en une même grille."""

    def setUp(self):
        super().setUp()
        charger_scripts(self.page, ["js/lib/xlsx.full.min.js"])
        self.assertEqual(self.page.evaluate("XLSX.version"), "0.20.3")

    def lire(self, nom):
        b64 = base64.b64encode((DOSSIER / nom).read_bytes()).decode("ascii")
        resultat = self.page.evaluate(JS_GRILLES, [b64])
        return resultat["feuilles"], {feuille: nettoyer(grille) for feuille, grille in resultat["grilles"].items()}

    def test_trois_formats_meme_grille_que_python(self):
        attendu, _b, _f = lire_xlsx(DOSSIER / "equipements.xlsx")
        for nom in ("equipements.xlsx", "equipements.ods", "equipements.xls"):
            with self.subTest(fichier=nom):
                feuilles, grilles = self.lire(nom)
                self.assertEqual(feuilles, ["Parc", "Notes"])
                self.assertEqual(grilles, attendu)

    def test_gammes_xlsx(self):
        attendu, _b, _f = lire_xlsx(DOSSIER / "gammes.xlsx")
        feuilles, grilles = self.lire("gammes.xlsx")
        self.assertEqual(feuilles, ["Gammes"])
        self.assertEqual(grilles, attendu)
        gammes = grilles["Gammes"]
        self.assertEqual(gammes[0][0], "Équipement")
        cles = [(ligne[0], ligne[1]) for ligne in gammes[1:]]
        self.assertEqual(max(cles.count(cle) for cle in cles), 3, "une ligne par opération, gamme répétée")
        self.assertIn("0.75", [ligne[3] for ligne in gammes[1:]])
        self.assertIn("2026-10-01", [ligne[4] for ligne in gammes[1:]])

    def test_chiffre_refuse_comme_protege(self):
        b64 = base64.b64encode((DOSSIER / "chiffre.xlsx").read_bytes()).decode("ascii")
        message = self.page.evaluate("""([b64]) => { try { XLSX.read(b64, { type: 'base64' }); return ''; }
                                         catch (e) { return String(e.message); } }""", [b64])
        self.assertRegex(message, r"(?i)password")
        chemins = self.page.evaluate("([b64]) => XLSX.CFB.read(b64, { type: 'base64' }).FullPaths", [b64])
        self.assertIn("Root Entry/EncryptionInfo", chemins)
        self.assertIn("Root Entry/EncryptedPackage", chemins)


if __name__ == "__main__":
    unittest.main()
