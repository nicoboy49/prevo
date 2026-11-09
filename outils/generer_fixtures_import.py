#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Générateur des fichiers d'essai de l'import (lot 5 ; docs/ARCHITECTURE.md §18.10, tâche T79).

Écrit tests/fixtures/import/ : des fichiers « venus d'ailleurs » (liste Excel d'un atelier, export d'une
autre GMAO, collages tabulés depuis Excel, fichiers piégés) qui servent aux tests de l'assistant d'import,
et le LISEZMOI.md qui dit, fichier par fichier, ce que chacun piège et ce que l'aperçu doit en faire sur la
base de démo (lignes à créer, à mettre à jour, identiques, refusées avec leur raison, doublons sûrs et
supposés, références créées). Ces attentes servent de spécification aux tâches T80 à T86.

Déterministe : relancé, il réécrit les mêmes octets (dates des archives ZIP fixées au 1980-01-01, ordre
fixe des entrées, aucun horodatage du jour). Les fiches « existantes » (repères, codes, techniciens,
fournisseurs, compteurs, contrôles) sont lues dans donnees/demo/ : si le jeu de démo change, le
générateur s'arrête avec un message clair dès qu'une hypothèse des fichiers d'essai ne tient plus.

Formats écrits :
  .xlsx         écrit ici avec zipfile et le XML OOXML minimal (sans SheetJS) : chaînes partagées et une
                chaîne « en ligne », dates en numéros de série Excel (système 1900) avec un style de date ;
  .ods          écrit ici (mimetype non compressé en premier, content.xml, META-INF/manifest.xml), avec
                des cellules vides répétées (table:number-columns-repeated) et des lignes vides répétées
                (table:number-rows-repeated), comme les écrit LibreOffice ;
  .xls          ancien format BIFF8 : Python ne sait pas l'écrire. Le générateur ouvre Chromium
                (Playwright), charge js/lib/xlsx.full.min.js (SheetJS CE 0.20.3) dans une page vide et
                écrit XLSX.write(classeur, { bookType: 'xls', type: 'base64' }) avec les mêmes données que
                le .xlsx (SheetJS 0.20.3 écrit ce format de façon déterministe : mêmes octets à chaque fois) ;
  .csv / .tsv   textes en Windows-1252 ou UTF-8, séparateurs « ; », « , » ou tabulation ;
  chiffre.xlsx  conteneur OLE (CFB, signature D0 CF 11 E0 A1 B1 1A E1) minimal écrit ici, avec les flux
                EncryptionInfo et EncryptedPackage d'un classeur Excel protégé par mot de passe (contenu
                factice : rien n'est vraiment chiffré, mais un lecteur y voit un fichier protégé).

Utilisation (depuis la racine du projet) :
    py outils/generer_fixtures_import.py                    écrit tests/fixtures/import/
    py outils/generer_fixtures_import.py --sortie DOSSIER   écrit dans un autre dossier
    py outils/generer_fixtures_import.py --sans-xls         sans equipements.xls (pas de navigateur)
"""
import argparse
import base64
import codecs
import csv
import hashlib
import io
import math
import struct
import sys
import zipfile
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_DEMO = RACINE / "donnees" / "demo"
SORTIE_DEFAUT = RACINE / "tests" / "fixtures" / "import"
SHEETJS = RACINE / "js" / "lib" / "xlsx.full.min.js"
VERSION_SHEETJS = "0.20.3"
PAGE_VIDE = RACINE / "tests" / "fixtures" / "page-vide.html"

DATE_ZIP = (1980, 1, 1, 0, 0, 0)            # date fixe des entrées des archives (.xlsx, .ods)
ORIGINE_EXCEL_1900 = date(1899, 12, 30)     # numéro de série 0 du système de dates 1900 d'Excel
CRLF = "\r\n"
LF = "\n"
INSECABLE = chr(0xA0)                       # espace insécable (séparateur des milliers d'Excel en français)
APOSTROPHE = chr(0x2019)                    # apostrophe typographique (correction automatique d'Excel)

# Plafonds de la lecture (ARCHITECTURE.md §18.3) : au plus 20 000 lignes de données + 1 ligne d'en-tête.
LIGNES_DONNEES_MAX = 20000
COLONNES_ODS = 1024                         # largeur d'une feuille LibreOffice (cellules répétées en fin de ligne)
LIGNES_ODS = 1048576                        # hauteur d'une feuille LibreOffice (lignes répétées en fin de feuille)
REPETITIONS_BOMBE = 1000000                 # cellules répétées de cellules_repetees.ods

# Actions de l'aperçu (ARCHITECTURE.md §18.5 et §18.6)
CREER = "créer"
MAJ = "mettre à jour"
IDENTIQUE = "identique"
REFUSEE = "refusée"
DOUBLON_SUR = "doublon sûr"
DOUBLON_SUPPOSE = "doublon supposé"
ACTIONS = (CREER, MAJ, IDENTIQUE, REFUSEE, DOUBLON_SUR, DOUBLON_SUPPOSE)


def exiger(condition, message):
    """Arrête le générateur avec un message clair si une hypothèse sur le jeu de démo ne tient plus."""
    if not condition:
        raise SystemExit("generer_fixtures_import : hypothèse non tenue — " + message)


# ---------------------------------------------------------------------------
# Valeurs de cellule
# ---------------------------------------------------------------------------

class Jour:
    """Cellule de date (sans heure) : numéro de série dans .xlsx et .xls, office:date-value dans .ods."""
    __slots__ = ("jour",)

    def __init__(self, iso):
        self.jour = date.fromisoformat(iso)

    @property
    def serie(self):
        return (self.jour - ORIGINE_EXCEL_1900).days

    @property
    def iso(self):
        return self.jour.isoformat()

    @property
    def francais(self):
        return self.jour.strftime("%d/%m/%Y")


class EnLigne(str):
    """Texte écrit en chaîne « en ligne » (t="inlineStr") dans un .xlsx, et non dans sharedStrings.xml."""


def nombre_texte(valeur):
    """Texte d'un nombre de cellule, sans arrondi : 30 → « 30 », 0.75 → « 0.75 »."""
    if isinstance(valeur, int):
        return str(valeur)
    texte = repr(float(valeur))
    return texte[:-2] if texte.endswith(".0") else texte


def vide(valeur):
    return valeur is None or valeur == ""


def texte_lu(valeur):
    """Texte qu'une lecture doit rendre pour une cellule (dates en AAAA-MM-JJ, ARCHITECTURE.md §18.3)."""
    if vide(valeur):
        return ""
    if isinstance(valeur, Jour):
        return valeur.iso
    if isinstance(valeur, (int, float)):
        return nombre_texte(valeur)
    return str(valeur)


def iso_date_heure(texte):
    """« JJ/MM/AAAA HH:MM » → « AAAA-MM-JJ HH:MM » (vide → vide)."""
    if not texte:
        return ""
    jour, heure = texte.split(" ")
    j, m, a = jour.split("/")
    return "%s-%s-%s %s" % (a, m, j, heure)


def iso_date(texte):
    """« JJ/MM/AAAA » → « AAAA-MM-JJ » (vide → vide)."""
    if not texte:
        return ""
    j, m, a = texte.split("/")
    return "%s-%s-%s" % (a, m, j)


def francais_date(iso):
    """« AAAA-MM-JJ » → « JJ/MM/AAAA »."""
    a, m, j = iso.split("-")
    return "%s/%s/%s" % (j, m, a)


def decimal_fr(texte):
    """Décimal de la base (« 4.8 ») écrit à la française (« 4,8 »)."""
    return texte.replace(".", ",")


# ---------------------------------------------------------------------------
# Jeu de démo (base de référence des attentes)
# ---------------------------------------------------------------------------

class Demo:
    """Lecture des CSV de donnees/demo/ (apostrophe de protection retirée, ARCHITECTURE.md §3.2)."""

    def __init__(self, dossier):
        self.dossier = Path(dossier)
        self._tables = {}

    def lignes(self, table):
        if table not in self._tables:
            chemin = self.dossier / (table + ".csv")
            exiger(chemin.is_file(), "fichier de démo absent : %s" % chemin)
            with open(chemin, encoding="utf-8-sig", newline="") as fichier:
                self._tables[table] = [
                    {cle: (valeur[1:] if valeur.startswith("'") else valeur) for cle, valeur in ligne.items()}
                    for ligne in csv.DictReader(fichier, delimiter=";")]
        return self._tables[table]

    def par_id(self, table, identifiant):
        for ligne in self.lignes(table):
            if ligne["id"] == identifiant:
                return ligne
        exiger(False, "%s introuvable dans %s.csv" % (identifiant, table))

    def trouver(self, table, **criteres):
        """Lignes de la table dont les champs valent exactement les critères."""
        return [ligne for ligne in self.lignes(table)
                if all(ligne[cle] == valeur for cle, valeur in criteres.items())]

    def unique(self, table, **criteres):
        trouvees = self.trouver(table, **criteres)
        exiger(len(trouvees) == 1, "une seule ligne de %s attendue pour %r (%d trouvée(s))"
               % (table, criteres, len(trouvees)))
        return trouvees[0]

    def equipement(self, repere):
        return self.unique("equipements", repere=repere)

    def absent(self, table, **criteres):
        exiger(not self.trouver(table, **criteres), "%s ne doit pas contenir %r" % (table, criteres))

    def chemin(self, localisation_id, separateur=" > "):
        """Chemin « Site > Atelier > Ligne » d'une localisation."""
        libelles = []
        courant = localisation_id
        while courant:
            ligne = self.par_id("localisations", courant)
            libelles.append(ligne["libelle"])
            courant = ligne["parent_id"]
        return separateur.join(reversed(libelles))

    def technicien(self, prenom, nom):
        return self.unique("techniciens", prenom=prenom, nom=nom)

    def sans_code(self, code_ou_libelle, famille):
        """Vérifie qu'une valeur n'est ni un code ni un libellé de la famille (code « signalé »)."""
        for ligne in self.trouver("codes_defaillance", famille=famille):
            exiger(code_ou_libelle not in (ligne["code"], ligne["libelle"]) and
                   code_ou_libelle.lower() != ligne["libelle"].lower(),
                   "« %s » ne doit pas être un code de la famille %s" % (code_ou_libelle, famille))


class Identifiants:
    """Identifiants que Donnees.nouvelId donnera sur la démo, dans l'ordre du fichier (plus grand + 1)."""

    FORMATS = {
        "localisations": ("LOC-", 4), "equipements": ("EQ-", 4), "articles": ("ART-", 4),
        "fournisseurs": ("FOU-", 4), "mouvements_stock": ("MVT-", 6), "techniciens": ("TEC-", 4),
        "habilitations": ("HAB-", 4), "codes_defaillance": ("CD-", 4), "compteurs": ("CPT-", 4),
        "controles_reglementaires": ("CTR-", 4), "gammes": ("GAM-", 4), "gamme_operations": ("GOP-", 6),
        "ot_temps": ("OTT-", 6), "garanties": ("GAR-", 4), "contrats_prestataires": ("CTP-", 4),
        "reserves_controle": ("RES-", 5),
    }

    def __init__(self, demo):
        self.demo = demo
        self._suivants = {}

    def _plus_grand(self, table, prefixe):
        numeros = [int(ligne["id"][len(prefixe):]) for ligne in self.demo.lignes(table)
                   if ligne["id"].startswith(prefixe) and ligne["id"][len(prefixe):].isdigit()]
        return max(numeros) if numeros else 0

    def nouveau(self, table, annee=None):
        """Identifiant suivant pour une table (annee : pour les OT, numérotés par année)."""
        if table == "ordres_travail":
            prefixe, chiffres = "OT-%s-" % annee, 4
        else:
            prefixe, chiffres = self.FORMATS[table]
        cle = prefixe
        if cle not in self._suivants:
            self._suivants[cle] = self._plus_grand(table, prefixe) + 1
        numero = self._suivants[cle]
        self._suivants[cle] += 1
        return prefixe + str(numero).zfill(chiffres)


# ---------------------------------------------------------------------------
# Fichiers d'essai : description commune
# ---------------------------------------------------------------------------

class Ligne:
    """Une ligne de données d'un fichier d'essai et ce que l'aperçu doit en faire."""
    __slots__ = ("cellules", "action", "detail", "extra")

    def __init__(self, cellules, action, detail, **extra):
        exiger(action in ACTIONS, "action inconnue : %s" % action)
        self.cellules = list(cellules)
        self.action = action
        self.detail = detail
        self.extra = extra


class Tableau:
    """Données d'un fichier tabulaire : lignes au-dessus de l'en-tête, en-tête, lignes de données."""

    def __init__(self, nom, type_donnees, entetes, lignes, avant_entete=()):
        self.nom = nom
        self.type_donnees = type_donnees
        self.entetes = list(entetes)
        self.lignes = list(lignes)
        self.avant_entete = [list(ligne) for ligne in avant_entete]
        for ligne in self.lignes:
            exiger(len(ligne.cellules) == len(self.entetes),
                   "%s : %d cellules pour %d colonnes" % (nom, len(ligne.cellules), len(self.entetes)))

    @property
    def ligne_entete(self):
        """Numéro (tableur, 1 = première ligne) de la ligne d'en-tête."""
        return len(self.avant_entete) + 1

    def numero(self, index):
        """Numéro (tableur) de la ligne de données d'indice index (0 = première)."""
        return self.ligne_entete + 1 + index

    def grille(self):
        """Toutes les lignes du fichier, titre et en-tête compris (valeurs de cellule)."""
        return self.avant_entete + [list(self.entetes)] + [ligne.cellules for ligne in self.lignes]

    def totaux(self):
        return {action: sum(1 for ligne in self.lignes if ligne.action == action) for action in ACTIONS}


# ---------------------------------------------------------------------------
# Écriture des textes (CSV, collage tabulé)
# ---------------------------------------------------------------------------

def champ_csv(valeur, separateur):
    texte = texte_lu(valeur) if not isinstance(valeur, str) else valeur
    if any(caractere in texte for caractere in (separateur, '"', "\r", "\n")):
        return '"' + texte.replace('"', '""') + '"'
    return texte


def texte_delimite(lignes, separateur, fin=CRLF):
    return "".join(separateur.join(champ_csv(valeur, separateur) for valeur in ligne) + fin for ligne in lignes)


def encoder(texte, encodage, bom=False):
    octets = texte.encode(encodage)   # strict : un caractère hors de l'encodage arrête le générateur
    return (codecs.BOM_UTF8 + octets) if bom else octets


def csv_tableau(tableau, separateur, encodage, bom=False, fin=CRLF):
    return encoder(texte_delimite(tableau.grille(), separateur, fin), encodage, bom)


# ---------------------------------------------------------------------------
# Archives ZIP déterministes (.xlsx, .ods)
# ---------------------------------------------------------------------------

def zip_deterministe(entrees):
    """entrees : [(nom, octets, compresser)] dans l'ordre voulu → octets de l'archive."""
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as archive:
        for nom, donnees, compresser in entrees:
            info = zipfile.ZipInfo(nom, date_time=DATE_ZIP)
            info.create_system = 0          # même valeur sous Windows et ailleurs
            info.external_attr = 0
            info.compress_type = zipfile.ZIP_DEFLATED if compresser else zipfile.ZIP_STORED
            archive.writestr(info, donnees, compresslevel=9 if compresser else None)
    return tampon.getvalue()


# ---------------------------------------------------------------------------
# .xlsx (OOXML minimal, sans SheetJS)
# ---------------------------------------------------------------------------

XML_DECLARATION = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL_DOC = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_REL_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
TYPE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
CT_PREFIXE = "application/vnd.openxmlformats-officedocument.spreadsheetml."
FORMAT_DATE_XLSX = "dd/mm/yyyy"             # numFmtId 164, style de cellule n° 1


def lettres_colonne(index):
    """0 → A, 25 → Z, 26 → AA."""
    texte = ""
    index += 1
    while index:
        index, reste = divmod(index - 1, 26)
        texte = chr(65 + reste) + texte
    return texte


def ecrire_xlsx(feuilles):
    """feuilles : [(nom, grille)] ; grille = lignes de valeurs (str, EnLigne, int/float, Jour, None)."""
    partagees, index_partagees = [], {}
    references_partagees = 0
    feuilles_xml = []
    for _nom, grille in feuilles:
        lignes_xml = []
        colonne_max = 0
        for numero, cellules in enumerate(grille, 1):
            morceaux = []
            for colonne, valeur in enumerate(cellules):
                if vide(valeur):
                    continue
                reference = lettres_colonne(colonne) + str(numero)
                colonne_max = max(colonne_max, colonne)
                if isinstance(valeur, EnLigne):
                    morceaux.append('<c r="%s" t="inlineStr"><is><t>%s</t></is></c>' % (reference, escape(valeur)))
                elif isinstance(valeur, str):
                    if valeur not in index_partagees:
                        index_partagees[valeur] = len(partagees)
                        partagees.append(valeur)
                    references_partagees += 1
                    morceaux.append('<c r="%s" t="s"><v>%d</v></c>' % (reference, index_partagees[valeur]))
                elif isinstance(valeur, Jour):
                    morceaux.append('<c r="%s" s="1"><v>%d</v></c>' % (reference, valeur.serie))
                elif isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
                    morceaux.append('<c r="%s"><v>%s</v></c>' % (reference, nombre_texte(valeur)))
                else:
                    exiger(False, "valeur de cellule non prise en charge : %r" % (valeur,))
            if morceaux:
                lignes_xml.append('<row r="%d">%s</row>' % (numero, "".join(morceaux)))
        dimension = "A1:%s%d" % (lettres_colonne(colonne_max), len(grille))
        feuilles_xml.append(
            XML_DECLARATION + '<worksheet xmlns="%s" xmlns:r="%s"><dimension ref="%s"/><sheetData>%s'
            '</sheetData></worksheet>' % (NS_MAIN, NS_REL_DOC, dimension, "".join(lignes_xml)))

    n = len(feuilles)
    types = (XML_DECLARATION + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
             '<Default Extension="xml" ContentType="application/xml"/>'
             '<Override PartName="/xl/workbook.xml" ContentType="%ssheet.main+xml"/>' % CT_PREFIXE
             + "".join('<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="%sworksheet+xml"/>'
                       % (i, CT_PREFIXE) for i in range(1, n + 1))
             + '<Override PartName="/xl/styles.xml" ContentType="%sstyles+xml"/>' % CT_PREFIXE
             + '<Override PartName="/xl/sharedStrings.xml" ContentType="%ssharedStrings+xml"/>' % CT_PREFIXE
             + '</Types>')
    rels = (XML_DECLARATION + '<Relationships xmlns="%s"><Relationship Id="rId1" Type="%sofficeDocument" '
            'Target="xl/workbook.xml"/></Relationships>' % (NS_REL_PKG, TYPE_REL))
    classeur = (XML_DECLARATION + '<workbook xmlns="%s" xmlns:r="%s"><workbookPr/><sheets>%s</sheets></workbook>'
                % (NS_MAIN, NS_REL_DOC, "".join('<sheet name="%s" sheetId="%d" r:id="rId%d"/>'
                                                 % (escape(nom), i, i) for i, (nom, _g) in enumerate(feuilles, 1))))
    rels_classeur = (XML_DECLARATION + '<Relationships xmlns="%s">' % NS_REL_PKG
                     + "".join('<Relationship Id="rId%d" Type="%sworksheet" Target="worksheets/sheet%d.xml"/>'
                               % (i, TYPE_REL, i) for i in range(1, n + 1))
                     + '<Relationship Id="rId%d" Type="%sstyles" Target="styles.xml"/>' % (n + 1, TYPE_REL)
                     + '<Relationship Id="rId%d" Type="%ssharedStrings" Target="sharedStrings.xml"/>'
                     % (n + 2, TYPE_REL)
                     + '</Relationships>')
    styles = (XML_DECLARATION + '<styleSheet xmlns="%s">' % NS_MAIN
              + '<numFmts count="1"><numFmt numFmtId="164" formatCode="%s"/></numFmts>' % FORMAT_DATE_XLSX
              + '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
              '<fills count="2"><fill><patternFill patternType="none"/></fill>'
              '<fill><patternFill patternType="gray125"/></fill></fills>'
              '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
              '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
              '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
              '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs>'
              '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
              '</styleSheet>')
    chaines = (XML_DECLARATION + '<sst xmlns="%s" count="%d" uniqueCount="%d">%s</sst>'
               % (NS_MAIN, references_partagees, len(partagees),
                  "".join("<si><t>%s</t></si>" % escape(texte) for texte in partagees)))

    entrees = [("[Content_Types].xml", types), ("_rels/.rels", rels), ("xl/workbook.xml", classeur),
               ("xl/_rels/workbook.xml.rels", rels_classeur), ("xl/styles.xml", styles),
               ("xl/sharedStrings.xml", chaines)]
    entrees += [("xl/worksheets/sheet%d.xml" % i, xml) for i, xml in enumerate(feuilles_xml, 1)]
    return zip_deterministe([(nom, xml.encode("utf-8"), True) for nom, xml in entrees])


# ---------------------------------------------------------------------------
# .ods (OpenDocument, comme LibreOffice : cellules et lignes vides répétées)
# ---------------------------------------------------------------------------

NS_ODS = ('xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
          'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
          'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"')
TYPE_ODS = "application/vnd.oasis.opendocument.spreadsheet"


def cellules_vides_ods(nombre):
    if nombre == 1:
        return "<table:table-cell/>"
    return '<table:table-cell table:number-columns-repeated="%d"/>' % nombre


def cellule_ods(valeur):
    if isinstance(valeur, Jour):
        return ('<table:table-cell office:value-type="date" office:date-value="%s"><text:p>%s</text:p>'
                '</table:table-cell>' % (valeur.iso, valeur.francais))
    if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
        texte = nombre_texte(valeur)
        return ('<table:table-cell office:value-type="float" office:value="%s"><text:p>%s</text:p>'
                '</table:table-cell>' % (texte, texte.replace(".", ",")))
    exiger("  " not in valeur and valeur == valeur.strip(), "espaces non gérés en .ods : %r" % valeur)
    return '<table:table-cell office:value-type="string"><text:p>%s</text:p></table:table-cell>' % escape(valeur)


def ligne_ods(cellules):
    """Une ligne : cellules vides consécutives regroupées (number-columns-repeated), puis cellules vides
    répétées jusqu'à la 1 024e colonne, comme LibreOffice."""
    morceaux = []
    vides = 0
    for valeur in cellules:
        if vide(valeur):
            vides += 1
            continue
        if vides:
            morceaux.append(cellules_vides_ods(vides))
            vides = 0
        morceaux.append(cellule_ods(valeur))
    utilisees = len(cellules) - vides
    morceaux.append(cellules_vides_ods(COLONNES_ODS - utilisees))
    return "<table:table-row>%s</table:table-row>" % "".join(morceaux)


def contenu_ods(tables_xml):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<office:document-content %s office:version="1.2">'
            '<office:body><office:spreadsheet>%s</office:spreadsheet></office:body></office:document-content>'
            % (NS_ODS, "".join(tables_xml)))


def archive_ods(contenu):
    """Archive .ods : mimetype (non compressé, en premier), content.xml, styles.xml (vide, mais SheetJS
    l'exige), META-INF/manifest.xml."""
    styles = ('<?xml version="1.0" encoding="UTF-8"?>\n<office:document-styles '
              'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" office:version="1.2">'
              '<office:styles/></office:document-styles>')
    manifeste = ('<?xml version="1.0" encoding="UTF-8"?>\n<manifest:manifest '
                 'xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">'
                 '<manifest:file-entry manifest:full-path="/" manifest:version="1.2" manifest:media-type="%s"/>'
                 '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>'
                 '<manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>'
                 '</manifest:manifest>' % TYPE_ODS)
    return zip_deterministe([("mimetype", TYPE_ODS.encode("ascii"), False),
                             ("content.xml", contenu.encode("utf-8"), True),
                             ("styles.xml", styles.encode("utf-8"), True),
                             ("META-INF/manifest.xml", manifeste.encode("utf-8"), True)])


def ecrire_ods(feuilles):
    tables = []
    for nom, grille in feuilles:
        lignes = "".join(ligne_ods(cellules) for cellules in grille)
        fin = ('<table:table-row table:number-rows-repeated="%d">%s</table:table-row>'
               % (LIGNES_ODS - len(grille), cellules_vides_ods(COLONNES_ODS)))
        tables.append('<table:table table:name="%s"><table:table-column table:number-columns-repeated="%d"/>'
                      '%s%s</table:table>' % (escape(nom), COLONNES_ODS, lignes, fin))
    return archive_ods(contenu_ods(tables))


def ecrire_ods_bombe():
    """Une ligne d'en-tête puis une ligne dont UNE cellule non vide est répétée 1 000 000 de fois."""
    entete = ligne_ods(["Repère", "Désignation"])
    bombe = ('<table:table-row><table:table-cell table:number-columns-repeated="%d" office:value-type="string">'
             '<text:p>x</text:p></table:table-cell></table:table-row>' % REPETITIONS_BOMBE)
    table = ('<table:table table:name="Feuille1"><table:table-column table:number-columns-repeated="%d"/>%s%s'
             '</table:table>' % (COLONNES_ODS, entete, bombe))
    return archive_ods(contenu_ods([table]))


# ---------------------------------------------------------------------------
# .xls (BIFF8) écrit par SheetJS dans Chromium
# ---------------------------------------------------------------------------

JS_ECRIRE_XLS = """(feuilles) => {
  const classeur = XLSX.utils.book_new();
  for (const feuille of feuilles) {
    const ws = {};
    let colonneMax = 0;
    feuille.lignes.forEach((ligne, r) => {
      ligne.forEach((valeur, c) => {
        if (valeur === null) return;
        const adresse = XLSX.utils.encode_cell({ r, c });
        if (typeof valeur === 'string') ws[adresse] = { t: 's', v: valeur };
        else if (typeof valeur === 'number') ws[adresse] = { t: 'n', v: valeur };
        else ws[adresse] = { t: 'n', v: valeur.serie, z: valeur.format };
        colonneMax = Math.max(colonneMax, c);
      });
    });
    ws['!ref'] = XLSX.utils.encode_range({ s: { r: 0, c: 0 }, e: { r: feuille.lignes.length - 1, c: colonneMax } });
    XLSX.utils.book_append_sheet(classeur, ws, feuille.nom);
  }
  return XLSX.write(classeur, { bookType: 'xls', type: 'base64' });
}"""


def cellule_json(valeur):
    if vide(valeur):
        return None
    if isinstance(valeur, Jour):
        return {"serie": valeur.serie, "format": FORMAT_DATE_XLSX}
    if isinstance(valeur, (int, float)):
        return valeur
    return str(valeur)


def ecrire_xls(feuilles):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit("generer_fixtures_import : Playwright pour Python est nécessaire pour écrire "
                         "equipements.xls (ou relancer avec --sans-xls).")
    donnees = [{"nom": nom, "lignes": [[cellule_json(valeur) for valeur in ligne] for ligne in grille]}
               for nom, grille in feuilles]
    with sync_playwright() as playwright:
        navigateur = playwright.chromium.launch(headless=True)
        try:
            page = navigateur.new_page()
            page.goto(PAGE_VIDE.as_uri())
            page.add_script_tag(path=str(SHEETJS))
            version = page.evaluate("XLSX.version")
            exiger(version == VERSION_SHEETJS, "SheetJS %s attendu dans js/lib/, %s trouvé" % (VERSION_SHEETJS, version))
            texte = page.evaluate(JS_ECRIRE_XLS, donnees)
        finally:
            navigateur.close()
    return base64.b64decode(texte)


# ---------------------------------------------------------------------------
# Conteneur OLE (CFB) minimal : chiffre.xlsx
# ---------------------------------------------------------------------------

SECTEUR = 512
MINI_SECTEUR = 64
SEUIL_MINI = 4096
FIN_CHAINE = 0xFFFFFFFE
LIBRE = 0xFFFFFFFF
SECTEUR_FAT = 0xFFFFFFFD
SANS_ENTREE = 0xFFFFFFFF
SIGNATURE_CFB = bytes([0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1])


def octets_pseudo_aleatoires(graine, nombre):
    """Octets d'apparence aléatoire mais toujours les mêmes (SHA-256 en chaîne)."""
    morceaux, compteur = [], 0
    while sum(len(m) for m in morceaux) < nombre:
        morceaux.append(hashlib.sha256(("%s-%d" % (graine, compteur)).encode("ascii")).digest())
        compteur += 1
    return b"".join(morceaux)[:nombre]


def entree_repertoire(nom, type_objet, couleur, gauche, droite, enfant, debut, taille):
    nom_utf16 = nom.encode("utf-16-le") + b"\x00\x00" if nom else b""
    exiger(len(nom_utf16) <= 64, "nom de flux trop long : %s" % nom)
    return (nom_utf16.ljust(64, b"\x00")
            + struct.pack("<HBBIII", len(nom_utf16), type_objet, couleur, gauche, droite, enfant)
            + bytes(16) + struct.pack("<I", 0) + bytes(16) + struct.pack("<IQ", debut, taille))


def ecrire_cfb(flux):
    """flux : [(nom, octets)] (flux à la racine) → octets d'un fichier CFB version 3 (secteurs de 512 octets).
    Les flux de moins de 4 096 octets vont dans le mini-flux (secteurs de 64 octets), les autres dans des
    secteurs ordinaires. Secteurs : 0 = FAT, 1 = répertoire, 2 = mini-FAT, puis mini-flux et grands flux."""
    secteurs, fat = [], []

    def allouer(donnees, marque=None):
        nombre = max(1, math.ceil(len(donnees) / SECTEUR))
        debut = len(secteurs)
        for i in range(nombre):
            secteurs.append(donnees[i * SECTEUR:(i + 1) * SECTEUR].ljust(SECTEUR, b"\x00"))
            fat.append(marque if marque is not None else (debut + i + 1 if i < nombre - 1 else FIN_CHAINE))
        return debut

    allouer(b"", SECTEUR_FAT)                 # secteur 0 : la FAT (remplie à la fin)
    allouer(b"")                              # secteur 1 : le répertoire (rempli à la fin)

    mini_fat, mini_flux, debuts = [], bytearray(), {}
    for nom, donnees in flux:
        if len(donnees) < SEUIL_MINI:
            nombre = math.ceil(len(donnees) / MINI_SECTEUR)
            debut = len(mini_fat)
            debuts[nom] = debut
            mini_fat += [debut + i + 1 if i < nombre - 1 else FIN_CHAINE for i in range(nombre)]
            mini_flux += donnees.ljust(nombre * MINI_SECTEUR, b"\x00")
    mini_fat += [LIBRE] * (-len(mini_fat) % (SECTEUR // 4))
    debut_mini_fat = allouer(struct.pack("<%dI" % len(mini_fat), *mini_fat)) if mini_flux else FIN_CHAINE
    nb_mini_fat = len(mini_fat) * 4 // SECTEUR if mini_flux else 0
    debut_mini_flux = allouer(bytes(mini_flux)) if mini_flux else FIN_CHAINE
    for nom, donnees in flux:
        if len(donnees) >= SEUIL_MINI:
            debuts[nom] = allouer(donnees)

    # Répertoire : arbre rouge-noir des flux, classés comme le veut CFB (longueur du nom, puis majuscules).
    ordre = sorted(range(len(flux)), key=lambda i: (len(flux[i][0]), flux[i][0].upper()))
    gauche, droite, profondeur = {}, {}, {}

    def construire(indices, niveau):
        if not indices:
            return SANS_ENTREE
        milieu = len(indices) // 2
        i = indices[milieu]
        profondeur[i] = niveau
        gauche[i] = construire(indices[:milieu], niveau + 1)
        droite[i] = construire(indices[milieu + 1:], niveau + 1)
        return i + 1                            # entrée 0 = Root Entry

    racine_arbre = construire(ordre, 0)
    niveau_max = max(profondeur.values())
    parfait = len(flux) == 2 ** (niveau_max + 1) - 1
    entrees = [entree_repertoire("Root Entry", 5, 1, SANS_ENTREE, SANS_ENTREE, racine_arbre,
                                 debut_mini_flux, len(mini_flux))]
    for i, (nom, donnees) in enumerate(flux):
        couleur = 0 if (profondeur[i] == niveau_max and not parfait) else 1   # 0 = rouge, 1 = noir
        g = gauche[i]
        d = droite[i]
        entrees.append(entree_repertoire(nom, 2, couleur, g, d, SANS_ENTREE, debuts[nom], len(donnees)))
    exiger(len(entrees) <= SECTEUR // 128, "répertoire CFB sur plus d'un secteur non pris en charge")
    while len(entrees) < SECTEUR // 128:
        entrees.append(entree_repertoire("", 0, 0, SANS_ENTREE, SANS_ENTREE, SANS_ENTREE, 0, 0))
    secteurs[1] = b"".join(entrees)
    fat[1] = FIN_CHAINE

    exiger(len(fat) <= SECTEUR // 4, "FAT CFB sur plus d'un secteur non prise en charge")
    fat += [LIBRE] * (SECTEUR // 4 - len(fat))
    secteurs[0] = struct.pack("<%dI" % len(fat), *fat)

    entete = (SIGNATURE_CFB + bytes(16) + struct.pack("<HHHHH", 0x003E, 0x0003, 0xFFFE, 9, 6) + bytes(6)
              + struct.pack("<IIIIIIIII", 0, 1, 1, 0, SEUIL_MINI, debut_mini_fat, nb_mini_fat, FIN_CHAINE, 0)
              + struct.pack("<109I", 0, *([LIBRE] * 108)))
    exiger(len(entete) == SECTEUR, "en-tête CFB de %d octets" % len(entete))
    return entete + b"".join(secteurs)


def ecrire_chiffre():
    """Classeur « protégé par mot de passe » : flux EncryptionInfo (chiffrement agile 4.4, descripteur XML
    aux valeurs factices) et EncryptedPackage (taille annoncée + octets pseudo-aléatoires)."""
    def b64(graine, nombre):
        return base64.b64encode(octets_pseudo_aleatoires(graine, nombre)).decode("ascii")

    descripteur = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
        '<encryption xmlns="http://schemas.microsoft.com/office/2006/encryption" '
        'xmlns:p="http://schemas.microsoft.com/office/2006/keyEncryptor/password" '
        'xmlns:c="http://schemas.microsoft.com/office/2006/keyEncryptor/certificate">'
        '<keyData saltSize="16" blockSize="16" keyBits="256" hashSize="64" cipherAlgorithm="AES" '
        'cipherChaining="ChainingModeCBC" hashAlgorithm="SHA512" saltValue="%s"/>'
        '<dataIntegrity encryptedHmacKey="%s" encryptedHmacValue="%s"/>'
        '<keyEncryptors><keyEncryptor uri="http://schemas.microsoft.com/office/2006/keyEncryptor/password">'
        '<p:encryptedKey spinCount="100000" saltSize="16" blockSize="16" keyBits="256" hashSize="64" '
        'cipherAlgorithm="AES" cipherChaining="ChainingModeCBC" hashAlgorithm="SHA512" saltValue="%s" '
        'encryptedVerifierHashInput="%s" encryptedVerifierHashValue="%s" encryptedKeyValue="%s"/>'
        '</keyEncryptor></keyEncryptors></encryption>'
        % (b64("sel", 16), b64("hmac-cle", 64), b64("hmac-valeur", 64), b64("sel-cle", 16),
           b64("verif-entree", 16), b64("verif-valeur", 64), b64("cle", 32)))
    info = struct.pack("<HHI", 4, 4, 0x40) + descripteur.encode("utf-8")
    taille_claire = 6000
    paquet = struct.pack("<Q", taille_claire) + octets_pseudo_aleatoires("paquet", 6016)
    return ecrire_cfb([("EncryptionInfo", info), ("EncryptedPackage", paquet)])


# ---------------------------------------------------------------------------
# Données des fichiers d'essai
# ---------------------------------------------------------------------------

TITRE_PARC = "Liste du parc — atelier"
ENTETES_EQUIPEMENTS = ["Désignation", "Code machine", "Fabricant", "Mise en service", "Emplacement",
                       "N° de série", "Criticité", "Machine mère", "Commentaire"]
NOTES_PARC = [["Liste tenue par le service maintenance (export du 14/10/2026)."],
              ["Repères : codes internes de l'atelier ; les zéros en tête comptent (« 007 »)."]]
NOUVELLE_LIGNE = "Ligne de rectification"


def equipements(demo, ids):
    """Liste du parc : les machines de la démo citées par les autres fichiers (identiques, une mise à jour),
    des machines nouvelles, trois lignes en erreur."""
    lignes = []
    usinage = demo.unique("localisations", libelle="Atelier Usinage", type="atelier")
    utilites = demo.unique("localisations", libelle="Atelier Utilités", type="atelier")
    assemblage = demo.unique("localisations", libelle="Atelier Assemblage-conditionnement", type="atelier")
    demo.absent("localisations", libelle=NOUVELLE_LIGNE)
    chemin_nouveau = demo.chemin(usinage["id"]) + " > " + NOUVELLE_LIGNE
    for repere in ("CP-01.PUR", "CP-02", "007", "007.TA", "SC-02", "PE-02", "TR-01", "MT-01", "XX-99"):
        demo.absent("equipements", repere=repere)
    nouveaux = {}

    def existant(repere, commentaire="", separateur=" > ", criticite=None, action=IDENTIQUE, detail=None):
        eq = demo.equipement(repere)
        exiger(eq["date_mes"] and eq["localisation_id"], "%s : date et localisation attendues" % repere)
        parent = demo.par_id("equipements", eq["parent_id"])["repere"] if eq["parent_id"] else ""
        cellules = [eq["designation"], repere, eq["marque"], Jour(eq["date_mes"]),
                    demo.chemin(eq["localisation_id"], separateur), eq["num_serie"],
                    criticite or eq["criticite"], parent, commentaire]
        lignes.append(Ligne(cellules, action, detail or "%s : aucune colonne importée ne change" % eq["id"],
                            cle=repere))

    def nouveau(cellules, detail):
        identifiant = ids.nouveau("equipements")
        nouveaux[cellules[1]] = identifiant
        lignes.append(Ligne(cellules, CREER, detail(identifiant) if callable(detail) else identifiant + " ; " + detail,
                            cle=cellules[1]))

    def refuse(cellules, raison):
        lignes.append(Ligne(cellules, REFUSEE, raison, cle=cellules[1]))

    cp01 = demo.equipement("CP-01")
    exiger(cp01["localisation_id"] == utilites["id"], "CP-01 attendu dans l'atelier Utilités")
    existant("CP-01", "Compresseur principal")
    nouveau(["Purgeur électronique du compresseur CP-01", "CP-01.PUR", "Aerovis", "15/03/2024",
             demo.chemin(utilites["id"]), "1E5", "C", "CP-01", ""],
            "machine mère CP-01 = %s (base) ; mise en service écrite en texte « 15/03/2024 » → 2024-03-15 ; "
            "n° de série « 1E5 » gardé tel quel (champ protégé, jamais un nombre)" % cp01["id"])
    nouveau(["Compresseur à vis 22 kW de secours", "CP-02", "Aerovis", Jour("2023-11-06"),
             demo.chemin(utilites["id"]), "AV22-2023-01188", "b", "", "En secours de CP-01"],
            "criticité « b » → B (correspondance tolérante, D86) ; mise en service 2023-11-06 (n° de série Excel)")
    ra01 = demo.equipement("RA-01")
    exiger(ra01["num_serie"].startswith("0"), "RA-01 : n° de série à zéros en tête attendu")
    existant("RA-01", detail="%s : identique — le n° de série « %s » doit être lu en texte (zéros en tête)"
             % (ra01["id"], ra01["num_serie"]))
    existant("PO-01")
    po02 = demo.equipement("PO-02")
    exiger(po02["criticite"] == "B", "PO-02 : criticité B attendue dans la démo")
    existant("PO-02", "Criticité relevée après la panne de février", separateur=" / ", criticite="A", action=MAJ,
             detail="%s : criticité B → A (seul changement) ; chemin écrit avec « / » au lieu de « > » "
                    "(même localisation %s)" % (po02["id"], po02["localisation_id"]))
    existant("GF-01")
    existant("VE-01")
    loc_nouvelle = ids.nouveau("localisations")
    nouveau(["Rectifieuse plane hydraulique", "007", "Rectimax", Jour("2021-05-17"), chemin_nouveau,
             "0042-117", "A", "", "Reprise du parc de l'ancien site"],
            "repère « 007 » gardé avec ses zéros ; localisation **créée** %s « %s » (type ligne, parent %s "
            "« Atelier Usinage »)" % (loc_nouvelle, NOUVELLE_LIGNE, usinage["id"]))
    nouveau(["Table magnétique de la rectifieuse 007", "007.TA", "Rectimax", Jour("2021-05-17"), chemin_nouveau,
             "TM-0098", "B", "007", ""],
            lambda i: "%s ; machine mère « 007 » = %s, créé plus haut dans le même fichier ; localisation %s "
                      "(déjà créée plus haut : pas de second exemplaire)" % (i, nouveaux["007"], loc_nouvelle))
    for repere in ("CU-01", "PT-01", "SC-01"):
        existant(repere)
    refuse(["Scie circulaire à métaux", "SC-02", "Sciatek", Jour("2022-02-14"), demo.chemin(usinage["id"]),
            "ST-350-22-0077", "Z", "", "Criticité à revoir"],
           "criticité « Z » hors liste (valeurs permises : A, B, C)")
    refuse(["Perceuse radiale", "PE-02", "Foradel", Jour("2020-09-07"), demo.chemin(usinage["id"]),
            "FR-40-20-0311", "C", "XX-99", ""],
           "machine mère « XX-99 » introuvable (ni dans la base ni plus haut dans le fichier ; un équipement "
           "parent n'est jamais créé, D88)")
    for repere in ("PR-01", "CV-02", "CV-03", "EM-01", "ET-01", "CH-01"):
        existant(repere)
    refuse(["", "TR-01", "Manutrel", Jour("2018-03-12"), demo.chemin(assemblage["id"]), "TP-18-0456", "C", "",
            "Transpalette électrique (désignation à saisir)"],
           "désignation vide (champ obligatoire)")
    nouveau(["Touret à meuler d'établi", "MT-01", "", None, "", "", "", "", "Sans plaque constructeur"],
            "sans localisation ni date ; criticité vide → B (défaut du schéma), statut « en service », actif 1")
    tableau = Tableau("equipements", "equipements", ENTETES_EQUIPEMENTS, lignes, avant_entete=[[EnLigne(TITRE_PARC)]])
    tableau.loc_creee = loc_nouvelle
    return tableau


ENTETES_ARTICLES = ["Code article", "Libellé", "Famille", "Marque", "Réf. fabricant", "Casier", "Unité",
                    "Qté stock", "Stock mini", "Prix achat", "Fournisseur", "Délai livraison"]
NOUVEAU_FOURNISSEUR = "Boulonnerie des Cimes"


def articles(demo, ids):
    lignes = []
    nom_fournisseur = {f["id"]: f["nom"] for f in demo.lignes("fournisseurs")}
    for nom in ("Mécaroule Distribution", "Garnitech Pompes", "Électro-Alpes Distribution", "Lubrifix Industrie",
                "Fluidalpes Services"):
        demo.unique("fournisseurs", nom=nom)
    demo.absent("fournisseurs", nom=NOUVEAU_FOURNISSEUR)
    for reference in ("ROU-101", "JNT-201", "FIX-010", "ELE-150", "LUB-010", "FIX-011", "VAR-001", "OUT-020",
                      "PNE-020"):
        demo.absent("articles", reference=reference)

    def existant(reference, famille, prix=None, action=IDENTIQUE, detail=None):
        a = demo.unique("articles", reference=reference)
        cellules = [reference, a["designation"], famille, a["fabricant"], a["ref_fabricant"], a["emplacement"],
                    a["unite"], "", decimal_fr(a["stock_securite"]), prix or decimal_fr(a["prix_unitaire"]),
                    nom_fournisseur[a["fournisseur_id"]], a["delai_jours"]]
        lignes.append(Ligne(cellules, action, detail or "%s : aucune colonne importée ne change ; qté stock vide "
                                                        "→ aucun mouvement" % a["id"], cle=reference))
        return a

    rou001 = demo.unique("articles", reference="ROU-001")
    exiger(rou001["prix_unitaire"] == "4.8", "ROU-001 : prix 4.8 attendu dans la démo")
    existant("ROU-001", "Roulements", prix="5,15", action=MAJ,
             detail="%s : prix unitaire 4.8 → 5.15 (seul changement) ; qté stock vide → aucun mouvement "
                    "(une cellule vide n'efface rien)" % rou001["id"])
    existant("FIL-001", "Filtration")
    premiere = {}
    mouvements = []

    def nouveau(cellules, detail=""):
        identifiant = ids.nouveau("articles")
        premiere.setdefault(cellules[0], len(lignes))
        morceaux = [identifiant]
        if cellules[7] != "":
            mouvement = ids.nouveau("mouvements_stock")
            mouvements.append(mouvement)
            morceaux.append("stock initial « %s » → %s « inventaire » de %s (motif « import »)"
                            % (cellules[7], mouvement, cellules[7].replace(",", ".")))
        else:
            morceaux.append("qté stock vide → aucun mouvement")
        if detail:
            morceaux.append(detail)
        lignes.append(Ligne(cellules, CREER, " ; ".join(morceaux), cle=cellules[0]))

    nouveau(["ROU-101", "Roulement à rouleaux coniques 30205", "Roulements", "Rouloran", "30205-J2", "A3-02", "u",
             "6", "2", "18,40", "Mécaroule Distribution", "5"], "prix 18.40")
    nouveau(["JNT-201", "Joint d" + APOSTROPHE + "étanchéité Ø 40 x 52 x 7", "Étanchéité", "Garnitec", "004512",
             "E2-01", "u", "25", "10", "1,75", "Garnitech Pompes", "7"],
            "réf. fabricant « 004512 » gardée avec ses zéros ; apostrophe typographique et « Ø » (Windows-1252)")
    fournisseur = ids.nouveau("fournisseurs")
    nouveau(["FIX-010", "Œillet de levage M12", "Visserie", "Levamax", "OL-M12", "F1-03", "u", "4", "", "12,90",
             NOUVEAU_FOURNISSEUR, "10"],
            "fournisseur « %s » inconnu → **créé** %s (D88)" % (NOUVEAU_FOURNISSEUR, fournisseur))
    nouveau(["ELE-150", "Câble souple H07RN-F 3G1,5 (au mètre)", "Électricité", "Voltavel", "H07RN-3G15", "C3-01",
             "m", "120,5", "20", "2,35", "Électro-Alpes Distribution", "4"], "virgule dans la désignation")
    doublon = len(lignes)
    lignes.append(Ligne(["ROU-101", "Roulement conique 30205", "Roulements", "Rouloran", "30205", "A3-02", "u",
                         "2", "", "18,40", "Mécaroule Distribution", "5"], REFUSEE, None, cle="ROU-101"))
    nouveau(["LUB-010", "Graisse alimentaire H1 (cartouche 400 g)", "Lubrifiants", "Lubrazur", "GA-H1", "D2-05",
             "cartouche", "0", "6", "9,80", "Lubrifix Industrie", "5"], "« 0 » n'est pas vide : inventaire de 0")
    nouveau(["FIX-011", "Écrou frein M12 (boîte de 50)", "Visserie", "Levamax", "EF-M12-50", "F1-04", "boîte", "",
             "1", "14,60", NOUVEAU_FOURNISSEUR, "10"],
            "fournisseur %s (créé plus haut : une seule création)" % fournisseur)
    nouveau(["VAR-001", "Variateur de fréquence 7,5 kW", "Électricité", "Voltavel", "VF-75", "C2-05", "u", "1",
             "1", "1" + INSECABLE + "250,00", "Électro-Alpes Distribution", "15"],
            "prix « 1 250,00 » avec espace insécable (U+00A0) → 1250.00")
    lignes.append(Ligne(["OUT-020", "", "Outillage", "Outilix", "FC-10", "A2-09", "u", "5", "2", "24,00",
                         "Mécaroule Distribution", "3"], REFUSEE, "désignation vide (champ obligatoire)",
                        cle="OUT-020"))
    lignes.append(Ligne(["PNE-020", "Silencieux pneumatique G1/4", "Pneumatique", "Hydronel", "SP-14", "B1-06",
                         "u", "10", "4", "3,20", "Fluidalpes Services", "2 semaines"], REFUSEE,
                        "délai « 2 semaines » illisible (nombre entier attendu)", cle="PNE-020"))
    tableau = Tableau("articles", "articles", ENTETES_ARTICLES, lignes)
    lignes[doublon].detail = "doublon dans le fichier (même référence que la ligne %d)" % tableau.numero(premiere["ROU-101"])
    tableau.resume = "références créées : fournisseur %s « %s » ; %d mouvements « inventaire » (%s à %s)" % (
        fournisseur, NOUVEAU_FOURNISSEUR, len(mouvements), mouvements[0], mouvements[-1])
    return tableau


ENTETES_FOURNISSEURS = ["Raison sociale", "Interlocuteur", "Tél", "Courriel"]


def fournisseurs(demo, ids):
    lignes = []
    fluid = demo.unique("fournisseurs", nom="Fluidalpes Services")
    exiger(fluid["email"].startswith("ventes@"), "Fluidalpes Services : e-mail ventes@… attendu")
    nouvel_email = fluid["email"].replace("ventes@", "commandes@")
    lignes.append(Ligne([fluid["nom"], fluid["contact"], fluid["telephone"], nouvel_email], MAJ,
                        "%s : e-mail %s → %s" % (fluid["id"], fluid["email"], nouvel_email), cle=fluid["nom"]))
    lub = demo.unique("fournisseurs", nom="Lubrifix Industrie")
    lignes.append(Ligne([lub["nom"], lub["contact"], lub["telephone"], lub["email"]], IDENTIQUE,
                        "%s : aucune colonne ne change (téléphone « %s » lu en texte)" % (lub["id"], lub["telephone"]),
                        cle=lub["nom"]))
    for nom in ("Roulements du Vercors", "Pneumatique Savoie Services", "Soudure et Métallerie du Guiers"):
        demo.absent("fournisseurs", nom=nom)
    lignes.append(Ligne(["Roulements du Vercors", "Lucie Perrin", "0465710023",
                         "achats@roulements-vercors-demo.example"], CREER,
                        ids.nouveau("fournisseurs") + " ; téléphone « 0465710023 » gardé avec son zéro", cle="Roulements du Vercors"))
    lignes.append(Ligne(["Pneumatique Savoie Services", "Marc Collomb", "04 65 71 00 30",
                         "pss@pneumatique-savoie-demo.example"], CREER,
                        ids.nouveau("fournisseurs") + " ; téléphone « 04 65 71 00 30 » gardé tel quel (champ protégé)",
                        cle="Pneumatique Savoie Services"))
    lignes.append(Ligne(["Soudure et Métallerie du Guiers", "", "", ""], CREER,
                        ids.nouveau("fournisseurs") + " ; cellules vides en fin de ligne (tabulations finales)",
                        cle="Soudure et Métallerie du Guiers"))
    lignes.append(Ligne(["", "Paul Girod", "0465710011", ""], REFUSEE,
                        "raison sociale vide (nom = clé naturelle du fournisseur)", cle=""))
    return Tableau("fournisseurs", "fournisseurs", ENTETES_FOURNISSEURS, lignes)


ENTETES_TECHNICIENS = ["Nom", "Prénom", "Fonction", "Coût horaire", "h/semaine"]


def techniciens(demo, ids):
    lignes = []
    moreau = demo.technicien("Julien", "Moreau")
    exiger(moreau["taux_horaire"] == "44", "Julien Moreau : taux horaire 44 attendu")
    lignes.append(Ligne(["Moreau", "Julien", moreau["metier"], "46", moreau["capacite_h_semaine"]], MAJ,
                        "%s : taux horaire 44 → 46" % moreau["id"], cle="Moreau Julien"))
    for prenom, nom in (("Karim", "Benali"), ("Sophie", "Lambert"), ("Thomas", "Garnier")):
        t = demo.technicien(prenom, nom)
        lignes.append(Ligne([nom, prenom, t["metier"], decimal_fr(t["taux_horaire"]), t["capacite_h_semaine"]],
                            IDENTIQUE, "%s : aucune colonne ne change" % t["id"], cle=nom + " " + prenom))
    demo.absent("techniciens", nom="Chabert")
    demo.absent("techniciens", nom="Vidal")
    lignes.append(Ligne(["Chabert", "Inès", "Mécanicienne", "41,50", "35"], CREER,
                        ids.nouveau("techniciens") + " ; taux « 41,50 » → 41.50", cle="Chabert Inès"))
    lignes.append(Ligne(["Vidal", "Mathis", "Électromécanicien", "43", "28"], CREER, ids.nouveau("techniciens"),
                        cle="Vidal Mathis"))
    lignes.append(Ligne(["", "Lucas", "Intérimaire", "35", "35"], REFUSEE, "nom vide (champ obligatoire)",
                        cle="Lucas"))
    return Tableau("techniciens", "techniciens", ENTETES_TECHNICIENS, lignes)


ENTETES_HABILITATIONS = ["Technicien", "Habilitation", "Obtenue le", "Valable jusqu'au"]


def habilitations(demo, ids):
    lignes = []
    moreau = demo.technicien("Julien", "Moreau")
    benali = demo.technicien("Karim", "Benali")
    garnier = demo.technicien("Thomas", "Garnier")
    lambert = demo.technicien("Sophie", "Lambert")
    br = demo.unique("habilitations", technicien_id=moreau["id"], intitule="BR")
    lignes.append(Ligne(["Julien Moreau", "BR", francais_date(br["date_obtention"]), francais_date(br["date_echeance"])],
                        IDENTIQUE, "%s (%s) : aucune date ne change" % (br["id"], moreau["id"]), cle="Julien Moreau / BR"))
    caces = demo.unique("habilitations", technicien_id=benali["id"], intitule="CACES R489")
    lignes.append(Ligne(["Karim Benali", "CACES R489", "15/10/2026", "15/10/2031"], MAJ,
                        "%s (%s) : date d'obtention %s → 2026-10-15 ; échéance %s → 2031-10-15 (renouvellement)"
                        % (caces["id"], benali["id"], caces["date_obtention"], caces["date_echeance"]),
                        cle="Karim Benali / CACES R489"))
    brg = demo.unique("habilitations", technicien_id=garnier["id"], intitule="BR")
    lignes.append(Ligne(["Garnier Thomas", "BR", "01/06/2026", "01/06/2029"], MAJ,
                        "%s (%s, écrit « Nom Prénom ») : obtention %s → 2026-06-01 ; échéance %s → 2029-06-01"
                        % (brg["id"], garnier["id"], brg["date_obtention"], brg["date_echeance"]),
                        cle="Garnier Thomas / BR"))
    demo.absent("habilitations", technicien_id=lambert["id"], intitule="B2V")
    demo.absent("habilitations", technicien_id=garnier["id"], intitule="H1V")
    lignes.append(Ligne(["Sophie Lambert", "B2V", "22/09/2025", "22/09/2028"], CREER,
                        "%s (%s)" % (ids.nouveau("habilitations"), lambert["id"]), cle="Sophie Lambert / B2V"))
    lignes.append(Ligne(["Thomas Garnier", "H1V", "05/01/2026", "05/01/2029"], CREER,
                        "%s (%s)" % (ids.nouveau("habilitations"), garnier["id"]), cle="Thomas Garnier / H1V"))
    lignes.append(Ligne(["Inès Chabert", "H0V", "12/10/2026", "12/10/2029"], REFUSEE,
                        "technicien « Inès Chabert » introuvable (elle n'existe qu'après l'import de techniciens.tsv)",
                        cle="Inès Chabert / H0V"))
    lignes.append(Ligne(["Paul Dumas", "BR", "01/02/2026", "01/02/2029"], REFUSEE,
                        "technicien « Paul Dumas » introuvable (un technicien n'est jamais créé par cet import)",
                        cle="Paul Dumas / BR"))
    lignes.append(Ligne(["Julien Moreau", "ATEX niveau 1", "31/02/2026", "31/02/2029"], REFUSEE,
                        "date « 31/02/2026 » illisible (jour inexistant)", cle="Julien Moreau / ATEX niveau 1"))
    return Tableau("habilitations", "habilitations", ENTETES_HABILITATIONS, lignes)


ECRITURE_FAMILLES = {"symptôme": "Symptome", "cause": "CAUSE", "remède": "Remede"}
NOUVEAUX_CODES = {"symptôme": [("symptôme", "S11", "Fumée")],
                  "cause": [("Cause", "C15", "Usure normale")],
                  "remède": [("remède", "R11", "Remplacement de l'ensemble"),
                             ("REMÈDE", "R12", "Mise à jour du programme automate")]}


def codes(demo, ids):
    lignes = []
    premiere = {}
    for famille in ("symptôme", "cause", "remède"):
        for code in demo.trouver("codes_defaillance", famille=famille):
            lignes.append(Ligne([ECRITURE_FAMILLES[famille], code["code"], code["libelle"]], IDENTIQUE,
                                "%s : famille « %s » = %s" % (code["id"], ECRITURE_FAMILLES[famille], famille),
                                cle=famille + " " + code["code"]))
        for ecrite, code, libelle in NOUVEAUX_CODES[famille]:
            demo.absent("codes_defaillance", famille=famille, code=code)
            premiere[(famille, code)] = len(lignes)
            lignes.append(Ligne([ecrite, code, libelle], CREER, "%s ; famille « %s » → %s"
                                % (ids.nouveau("codes_defaillance"), ecrite, famille), cle=famille + " " + code))
    lignes.append(Ligne(["Défaut", "D01", "Défaut électrique"], REFUSEE,
                        "famille « Défaut » hors liste (valeurs permises : symptôme, cause, remède)", cle="D01"))
    lignes.append(Ligne(["cause", "", "Sans code"], REFUSEE, "code vide (champ obligatoire)", cle=""))
    doublon = len(lignes)
    lignes.append(Ligne(["Cause", "C15", "Usure"], REFUSEE, None, cle="cause C15"))
    tableau = Tableau("codes", "codes", ["Famille", "Code", "Libellé"], lignes)
    lignes[doublon].detail = "doublon dans le fichier (même famille et même code que la ligne %d)" % tableau.numero(
        premiere[("cause", "C15")])
    return tableau


def compteurs(demo, ids):
    lignes = []
    cp01 = demo.equipement("CP-01")
    horaire = demo.unique("compteurs", equipement_id=cp01["id"], libelle="Compteur horaire de marche")
    lignes.append(Ligne(["CP-01", horaire["libelle"], horaire["unite"]], IDENTIQUE,
                        "%s : aucune colonne ne change" % horaire["id"], cle="CP-01"))
    ch01 = demo.equipement("CH-01")
    chariot = demo.unique("compteurs", equipement_id=ch01["id"], libelle="Compteur horaire du chariot")
    exiger(chariot["unite"] == "h", "compteur du chariot : unité h attendue")
    lignes.append(Ligne(["CH-01", chariot["libelle"], "heures"], MAJ, "%s : unité h → heures" % chariot["id"],
                        cle="CH-01"))
    for repere, libelle, unite in (("PO-02", "Compteur horaire de la pompe", "h"),
                                   ("CU-01", "Compteur horaire de broche", "h"),
                                   ("GF-01", "Compteur de démarrages du compresseur frigorifique", "démarrages")):
        eq = demo.equipement(repere)
        demo.absent("compteurs", equipement_id=eq["id"], libelle=libelle)
        lignes.append(Ligne([repere, libelle, unite], CREER, "%s (équipement %s)" % (ids.nouveau("compteurs"), eq["id"]),
                            cle=repere))
    lignes.append(Ligne(["007", "Compteur horaire de la rectifieuse", "h"], REFUSEE,
                        "équipement « 007 » introuvable (il n'existe qu'après l'import de la liste du parc)", cle="007"))
    lignes.append(Ligne(["", "Compteur général électrique", "kWh"], REFUSEE,
                        "équipement vide (repère obligatoire : clé naturelle équipement + libellé)", cle=""))
    return Tableau("compteurs", "compteurs", ["Repère", "Libellé", "Unité"], lignes)


ENTETES_CONTROLES = ["Équipement", "Nature du contrôle", "Texte de référence", "Périodicité (mois)",
                     "Organisme de contrôle", "Date du dernier contrôle", "Date du prochain contrôle", "Observations"]
# Observations du chariot (2.2, T489) : une réserve par ligne non vide (D183).
OBSERVATIONS_CHARIOT = ("Chaîne de levage : maillons usés à remplacer.", "Patin de fourche gauche fissuré.")


def controles(demo, ids):
    lignes = []

    def cellules_existant(ctr, repere, **remplacements):
        valeurs = [repere, ctr["nature"], ctr["texte_reference"], ctr["periodicite_mois"], ctr["organisme"],
                   francais_date(ctr["derniere_date"]), francais_date(ctr["prochaine_date"]), ctr["observations"]]
        for index, valeur in remplacements.items():
            valeurs[int(index[1:])] = valeur
        return valeurs

    pt01 = demo.equipement("PT-01")
    vgp_pont = demo.unique("controles_reglementaires", equipement_id=pt01["id"])
    lignes.append(Ligne(cellules_existant(vgp_pont, "PT-01"), IDENTIQUE, "%s : aucune colonne ne change"
                        % vgp_pont["id"], cle="PT-01"))
    ch01 = demo.equipement("CH-01")
    vgp_chariot = demo.unique("controles_reglementaires", equipement_id=ch01["id"])
    exiger((vgp_chariot["derniere_date"], vgp_chariot["prochaine_date"], vgp_chariot["observations"])
           == ("2026-03-18", "2026-09-18", ""), "VGP du chariot : dates 2026-03-18 / 2026-09-18 attendues")
    demo.absent("reserves_controle", controle_id=vgp_chariot["id"])
    reserves_chariot = [ids.nouveau("reserves_controle") for _ in OBSERVATIONS_CHARIOT]
    lignes.append(Ligne(cellules_existant(vgp_chariot, "CH-01", c5="18/09/2026", c6="18/03/2027",
                                          c7="\n".join(OBSERVATIONS_CHARIOT)), MAJ,
                        "%s : dernier contrôle 2026-03-18 → 2026-09-18 ; prochain 2026-09-18 → 2027-03-18 ; observations "
                        "sur deux lignes (champ entre guillemets) → deux réserves %s créées, datées du 2026-09-18 (D183) ; "
                        "la colonne observations du contrôle n'est pas écrite" % (vgp_chariot["id"], " et ".join(reserves_chariot)),
                        cle="CH-01"))
    pr01 = demo.equipement("PR-01")
    cu01 = demo.equipement("CU-01")
    nature_presse = "Vérification générale périodique de la presse"
    nature_cu = "Contrôle des arrêts d'urgence et des protecteurs"
    demo.absent("controles_reglementaires", equipement_id=pr01["id"], nature=nature_presse)
    demo.absent("controles_reglementaires", equipement_id=cu01["id"], nature=nature_cu)
    lignes.append(Ligne(["PR-01", nature_presse, "Arrêté du 1er mars 2004 (VGP) ; notice du constructeur", "3",
                         "Bureau Alpin de Contrôle (démo)", "05/07/2026", "05/10/2026",
                         "Carter de protection arrière à refixer."], CREER,
                        "%s (équipement %s) ; « ; » dans le texte de référence (champ entre guillemets) ; réserve %s "
                        "« Carter de protection arrière à refixer. » créée, datée du 2026-07-05"
                        % (ids.nouveau("controles_reglementaires"), pr01["id"], ids.nouveau("reserves_controle")), cle="PR-01"))
    lignes.append(Ligne(["CU-01", nature_cu, "Notice du constructeur", "12", "Maintenance interne",
                         "14/01/2026", "14/01/2027", ""], CREER,
                        "%s (équipement %s)" % (ids.nouveau("controles_reglementaires"), cu01["id"]), cle="CU-01"))
    lignes.append(Ligne(["XX-99", "Vérification des installations électriques", "Code du travail", "12",
                         "Certif-Elec Services (démo)", "01/03/2026", "01/03/2027", ""], REFUSEE,
                        "équipement « XX-99 » introuvable", cle="XX-99"))
    gf01 = demo.equipement("GF-01")
    etancheite = demo.unique("controles_reglementaires", equipement_id=gf01["id"])
    lignes.append(Ligne(cellules_existant(etancheite, "GF-01", c3="12 mois"), REFUSEE,
                        "périodicité « 12 mois » illisible (nombre entier attendu) : la fiche %s n'est pas touchée"
                        % etancheite["id"], cle="GF-01"))
    return Tableau("controles", "controles", ENTETES_CONTROLES, lignes)


# Garanties et contrats de prestataires (2.2, T487) : fournisseur ou prestataire par son nom, créé s'il manque (D88 a),
# mais seulement si une ligne gardée le cite ; contrôles du formulaire (Garanties.verifierGarantie, verifierContrat).
NOUVEAU_GARANT = "Froid Industriel du Dauphiné"
GARANT_REFUSE = "Scies et Lames du Grésivaudan"
PRESTATAIRE_REFUSE = "Hydraulique du Guiers"
ENTETES_GARANTIES = ["Repère", "Fournisseur", "Date de début", "Échéance", "Ce qui est couvert"]


def garanties(demo, ids):
    lignes = []
    for nom in (NOUVEAU_GARANT, GARANT_REFUSE, PRESTATAIRE_REFUSE):
        demo.absent("fournisseurs", nom=nom)

    def cellules(garantie, repere, **remplacements):
        valeurs = [repere, demo.par_id("fournisseurs", garantie["fournisseur_id"])["nom"],
                   francais_date(garantie["date_debut"]), francais_date(garantie["date_fin"]), garantie["conditions"]]
        for index, valeur in remplacements.items():
            valeurs[int(index[1:])] = valeur
        return valeurs

    cp01 = demo.equipement("CP-01")
    gar_cp = demo.unique("garanties", equipement_id=cp01["id"])
    exiger(";" in gar_cp["conditions"], "garantie de CP-01 : « ; » attendu dans les conditions")
    lignes.append(Ligne(cellules(gar_cp, "CP-01"), IDENTIQUE, "%s : aucune colonne ne change ; « ; » dans les conditions "
                        "(champ entre guillemets)" % gar_cp["id"], cle="CP-01 / " + gar_cp["date_fin"]))
    po02 = demo.equipement("PO-02")
    gar_po = demo.unique("garanties", equipement_id=po02["id"])
    conditions = "Garniture mécanique, roulements et main-d'œuvre."
    exiger(gar_po["conditions"] != conditions, "garantie de PO-02 : conditions différentes attendues")
    lignes.append(Ligne(cellules(gar_po, "PO-02", c4=conditions), MAJ, "%s : conditions « %s » → « %s »"
                        % (gar_po["id"], gar_po["conditions"], conditions), cle="PO-02 / " + gar_po["date_fin"]))
    gf01 = demo.equipement("GF-01")
    demo.absent("garanties", equipement_id=gf01["id"])
    nouvelle = ids.nouveau("garanties")
    fournisseur = ids.nouveau("fournisseurs")
    lignes.append(Ligne(["GF-01", NOUVEAU_GARANT, "01/09/2026", "31/08/2028", "Compresseur frigorifique : pièces et "
                         "main-d'œuvre, deux ans."], CREER, "%s (équipement %s) ; fournisseur %s « %s » créé"
                        % (nouvelle, gf01["id"], fournisseur, NOUVEAU_GARANT), cle="GF-01 / 2028-08-31"))
    premiere = len(lignes) - 1
    cu01 = demo.equipement("CU-01")
    demo.absent("garanties", equipement_id=cu01["id"])
    lignes.append(Ligne(["CU-01", "", "", "30/06/2027", "Garantie constructeur : pièces seules."], CREER,
                        "%s (équipement %s) ; sans fournisseur ni date de début (facultatifs)"
                        % (ids.nouveau("garanties"), cu01["id"]), cle="CU-01 / 2027-06-30"))
    po01 = demo.equipement("PO-01")
    echue = demo.unique("garanties", equipement_id=po01["id"])
    exiger(echue["date_fin"] < "2028-07-01", "garantie de PO-01 : fin avant 2028-07-01 attendue")
    lignes.append(Ligne(["PO-01", demo.par_id("fournisseurs", echue["fournisseur_id"])["nom"], "02/07/2026", "01/07/2028",
                         "Pompe remplacée : nouvelle garantie de deux ans."], CREER,
                        "%s (équipement %s) : une autre date de fin que %s (fin %s), donc une autre garantie"
                        % (ids.nouveau("garanties"), po01["id"], echue["id"], echue["date_fin"]), cle="PO-01 / 2028-07-01"))
    lignes.append(Ligne(["XX-99", "Fluidalpes Services", "01/01/2026", "31/12/2027", "Pièces seules."], REFUSEE,
                        "équipement « XX-99 » introuvable", cle="XX-99 / 2027-12-31"))
    lignes.append(Ligne(["PR-01", PRESTATAIRE_REFUSE, "01/01/2026", "", "Groupe hydraulique."], REFUSEE,
                        "échéance vide (fin de garantie : obligatoire, clé naturelle avec l'équipement) ; « %s » "
                        "n'est pas créé" % PRESTATAIRE_REFUSE, cle="PR-01 / (vide)"))
    lignes.append(Ligne(["SC-01", GARANT_REFUSE, "01/03/2027", "01/03/2026", "Lame et volants."], REFUSEE,
                        "fin avant le début (contrôle du formulaire, Garanties.verifierGarantie) ; « %s » n'est pas "
                        "créé" % GARANT_REFUSE, cle="SC-01 / 2026-03-01"))
    lignes.append(Ligne(["PT-01", "Fluidalpes Services", "", "31/02/2027", "Palan et chemin de roulement."], REFUSEE,
                        "échéance « 31/02/2027 » illisible (jour inexistant)", cle="PT-01 / 31/02/2027"))
    doublon = len(lignes)
    lignes.append(Ligne(["GF-01", NOUVEAU_GARANT, "01/09/2026", "31/08/2028", "Compresseur seul."], REFUSEE, None,
                        cle="GF-01 / 2028-08-31"))
    tableau = Tableau("garanties", "garanties", ENTETES_GARANTIES, lignes)
    lignes[doublon].detail = "doublon dans le fichier (même équipement et même date de fin que la ligne %d)" % tableau.numero(premiere)
    tableau.resume = "référence créée : fournisseur %s « %s » (les fournisseurs des lignes refusées ne sont pas créés)" % (
        fournisseur, NOUVEAU_GARANT)
    return tableau


ENTETES_CONTRATS = ["Prestataire", "Objet", "Équipements", "Début", "Fin", "Préavis", "Tacite reconduction",
                    "Montant annuel HT", "Périmètre"]


def contrats(demo, ids):
    lignes = []

    def reperes(contrat):
        return ", ".join(demo.par_id("equipements", i)["repere"] for i in contrat["equipement_ids"].split(";") if i)

    def cellules(contrat, **remplacements):
        valeurs = [demo.par_id("fournisseurs", contrat["fournisseur_id"])["nom"], contrat["objet"], reperes(contrat),
                   francais_date(contrat["date_debut"]), francais_date(contrat["date_fin"]), contrat["preavis_mois"],
                   "oui" if contrat["reconduction_tacite"] == "1" else "non", contrat["montant_annuel"], contrat["perimetre"]]
        for index, valeur in remplacements.items():
            valeurs[int(index[1:])] = valeur
        return valeurs

    compresseurs = demo.unique("contrats_prestataires", objet="Maintenance préventive des compresseurs")
    exiger(compresseurs["equipement_ids"].count(";") == 1, "contrat des compresseurs : deux équipements attendus")
    lignes.append(Ligne(cellules(compresseurs), IDENTIQUE, "%s : aucune colonne ne change ; équipements « %s » = %s"
                        % (compresseurs["id"], reperes(compresseurs), compresseurs["equipement_ids"]),
                        cle="Fluidalpes Services / compresseurs"))
    electricite = demo.unique("contrats_prestataires", objet="Vérification annuelle des installations électriques")
    exiger((electricite["date_fin"], electricite["montant_annuel"], electricite["equipement_ids"]) == ("2026-06-30", "1250", ""),
           "contrat d'électricité : fin 2026-06-30, montant 1250, sans équipement attendus")
    lignes.append(Ligne(cellules(electricite, c4="30/06/2027", c7="1300", c8=""), MAJ,
                        "%s : fin 2026-06-30 → 2027-06-30 ; montant 1250 → 1300 (cellules vides : rien d'effacé)"
                        % electricite["id"], cle="Électro-Alpes Distribution / électricité"))
    demo.absent("contrats_prestataires", objet="Maintenance du groupe froid")
    groupe_froid = ids.nouveau("contrats_prestataires")
    prestataire = ids.nouveau("fournisseurs")
    gf01 = demo.equipement("GF-01")
    lignes.append(Ligne([NOUVEAU_GARANT, "Maintenance du groupe froid", "GF-01", "01/01/2026", "31/12/2026", "3", "oui",
                         "2 350,50", "Visite trimestrielle et dépannage sous 24 h."], CREER,
                        "%s (équipement %s) ; prestataire %s « %s » créé ; montant « 2 350,50 » → 2350.5 ; préavis de "
                        "3 mois : date limite de résiliation 2026-09-30 (CS173)" % (groupe_froid, gf01["id"], prestataire,
                                                                               NOUVEAU_GARANT),
                        cle=NOUVEAU_GARANT + " / groupe froid"))
    premiere = len(lignes) - 1
    pompes = [demo.equipement(r)["id"] for r in ("PO-01", "PO-02", "PO-03")]
    lignes.append(Ligne(["Garnitech Pompes", "Dépannage des pompes", "PO-01;PO-02;PO-03", "01/03/2026", "28/02/2027", "1",
                         "non", "", ""], CREER,
                        "%s ; repères séparés par « ; » (champ entre guillemets) → %s ; sans montant (facultatif)"
                        % (ids.nouveau("contrats_prestataires"), ";".join(pompes)), cle="Garnitech Pompes / pompes"))
    demo.equipement("CV-01")
    demo.absent("equipements", repere="CV-09")
    lignes.append(Ligne(["Lubrifix Industrie", "Graissage des convoyeurs", "CV-01, CV-09", "01/01/2026", "31/12/2026", "2",
                         "oui", "600", ""], REFUSEE, "équipement « CV-09 » introuvable (un repère inconnu refuse la ligne,"
                        " les autres s'importent)", cle="Lubrifix Industrie / convoyeurs"))
    lignes.append(Ligne(["", "Nettoyage des filtres de la centrale", "VE-01", "01/01/2026", "31/12/2026", "1", "non", "450",
                         ""], REFUSEE, "prestataire vide (obligatoire, clé naturelle avec l'objet)", cle="(vide) / filtres"))
    lignes.append(Ligne(["Mécaroule Distribution", "Fourniture de roulements", "", "01/01/2026", "31/12/2026", "trois",
                         "oui", "900", ""], REFUSEE, "préavis « trois » illisible (nombre entier attendu)",
                        cle="Mécaroule Distribution / roulements"))
    chaines = demo.unique("contrats_prestataires", objet="Lubrification des chaînes de convoyage")
    exiger(chaines["montant_annuel"] == "", "contrat des chaînes : sans montant attendu")
    lignes.append(Ligne(cellules(chaines, c7="-200"), REFUSEE, "montant « -200 » négatif (contrôle du formulaire, "
                        "Garanties.verifierContrat) : la fiche %s n'est pas touchée" % chaines["id"],
                        cle="Lubrifix Industrie / chaînes"))
    doublon = len(lignes)
    lignes.append(Ligne([NOUVEAU_GARANT.upper(), "Maintenance du groupe froid", "GF-01", "01/01/2026", "31/12/2026", "3",
                         "oui", "2350", ""], REFUSEE, None, cle=NOUVEAU_GARANT + " / groupe froid"))
    lignes.append(Ligne([PRESTATAIRE_REFUSE, "Entretien du groupe hydraulique", "PR-01.GH", "01/01/2026", "31/12/2025",
                         "2", "oui", "1500", ""], REFUSEE, "fin avant le début (contrôle du formulaire) ; prestataire "
                        "« %s » pas créé" % PRESTATAIRE_REFUSE, cle=PRESTATAIRE_REFUSE + " / hydraulique"))
    tableau = Tableau("contrats", "contrats", ENTETES_CONTRATS, lignes)
    lignes[doublon].detail = ("doublon dans le fichier (même prestataire, écrit en majuscules, et même objet que la ligne %d)"
                              % tableau.numero(premiere))
    tableau.resume = "référence créée : fournisseur %s « %s » (prestataire)" % (prestataire, NOUVEAU_GARANT)
    return tableau


# Réserves des contrôles (2.2, T489, CS170) : contrôle désigné par le repère et la nature (déjà dans Prévo) ; clé
# naturelle contrôle + date du contrôle + texte ; règles des réserves du L2 (ajout, levée, correction) ; levée sans
# date : date vide, commentaire de la reprise (D183).
ENTETES_RESERVES = ["Repère", "Nature du contrôle", "Date du contrôle", "Réserve", "Gravité", "Échéance", "Levée",
                    "Levée le", "Commentaire"]
COMMENTAIRE_LEVEE_REPRISE = "levée avant la 2.2, date inconnue"     # = Formats.COMMENTAIRE_LEVEE_REPRISE (D183)


def reserves(demo, ids):
    lignes = []

    def controle(repere):
        return demo.unique("controles_reglementaires", equipement_id=demo.equipement(repere)["id"])

    def reserve(texte):
        return demo.unique("reserves_controle", texte=texte)

    ae01, ra01, gf01, pt01 = controle("AE-01"), controle("RA-01"), controle("GF-01"), controle("PT-01")
    ve02, ae04, ch01 = controle("VE-02"), controle("AE-04"), controle("CH-01")
    schema = reserve("Schéma unifilaire du tableau général à mettre à jour.")
    exiger((schema["controle_id"], schema["levee"], schema["gravite"], schema["echeance_levee"]) == (ae01["id"], "0", "", "2026-12-15"),
           "réserve du schéma unifilaire : ouverte, sans gravité, échéance 2026-12-15 attendues")
    lignes.append(Ligne(["AE-01", ae01["nature"], francais_date(schema["date_controle"]), schema["texte"], "",
                         francais_date(schema["echeance_levee"]), "", "", ""], IDENTIQUE,
                        "%s : aucune colonne ne change" % schema["id"], cle="AE-01 / schéma unifilaire"))
    purgeur = reserve(ra01["observations"])
    exiger((purgeur["controle_id"], purgeur["levee"], purgeur["gravite"]) == (ra01["id"], "0", ""),
           "réserve du purgeur : ouverte, sans gravité attendue")
    lignes.append(Ligne(["RA-01", ra01["nature"], francais_date(purgeur["date_controle"]), purgeur["texte"], "majeure", "",
                         "oui", "", ""], MAJ,
                        "%s : gravité (vide) → majeure ; levée 0 → 1, sans date (date de levée vide) ; commentaire de levée "
                        "(vide) → « %s » (D183)" % (purgeur["id"], COMMENTAIRE_LEVEE_REPRISE), cle="RA-01 / purgeur"))
    demo.absent("reserves_controle", controle_id=gf01["id"])
    demo.absent("reserves_controle", controle_id=pt01["id"])
    exiger((gf01["derniere_date"], pt01["derniere_date"]) == ("2026-03-24", "2026-02-10"),
           "contrôles de GF-01 et PT-01 : derniers contrôles 2026-03-24 et 2026-02-10 attendus")
    raccord = "Raccord du détendeur à resserrer."
    lignes.append(Ligne(["GF-01", gf01["nature"], "24/03/2026", raccord, "mineure", "24/04/2026", "", "", ""], CREER,
                        "%s (contrôle %s), ouverte, échéance 2026-04-24" % (ids.nouveau("reserves_controle"), gf01["id"]),
                        cle="GF-01 / raccord"))
    premiere = len(lignes) - 1
    lignes.append(Ligne(["GF-01", gf01["nature"], "24/03/2026", "Étiquetage du circuit (fluide, charge) à compléter.", "", "",
                         "oui", "10/04/2026", "Étiquette posée par le frigoriste."], CREER,
                        "%s (contrôle %s), levée le 2026-04-10 avec son commentaire" % (ids.nouveau("reserves_controle"),
                                                                                        gf01["id"]),
                        cle="GF-01 / étiquetage"))
    lignes.append(Ligne(["PT-01", pt01["nature"], "10/02/2026", "Fin de course de montée à régler.", "critique", "", "oui",
                         "", ""], CREER,
                        "%s (contrôle %s), levée sans date : date de levée vide, commentaire « %s » (D183)"
                        % (ids.nouveau("reserves_controle"), pt01["id"], COMMENTAIRE_LEVEE_REPRISE), cle="PT-01 / fin de course"))
    demo.absent("controles_reglementaires", equipement_id=demo.equipement("CH-01")["id"], nature="Vérification des freins")
    lignes.append(Ligne(["CH-01", "Vérification des freins", "18/03/2026", "Frein de parc à régler.", "", "", "", "", ""],
                        REFUSEE, "contrôle « Vérification des freins » introuvable pour CH-01 (un contrôle inconnu refuse la ligne)",
                        cle="CH-01 / freins"))
    lignes.append(Ligne(["XX-99", ae01["nature"], "12/11/2025", "Prise de terre à vérifier.", "", "", "", "", ""], REFUSEE,
                        "équipement « XX-99 » introuvable", cle="XX-99"))
    exiger(ve02["derniere_date"] == "2026-06-02", "contrôle de VE-02 : dernier contrôle 2026-06-02 attendu")
    lignes.append(Ligne(["VE-02", ve02["nature"], "02/06/2026", "Débit d'aspiration du poste 3 insuffisant.", "", "", "",
                         "15/06/2026", ""], REFUSEE,
                        "levée datée sans commentaire (règle de la levée : commentaire obligatoire)", cle="VE-02 / débit"))
    lignes.append(Ligne(["GF-01", gf01["nature"], "15/12/2026", "Contrôle d'étanchéité à refaire.", "", "", "", "", ""], REFUSEE,
                        "date du contrôle 2026-12-15 dans le futur (règle de l'ajout ; démo au 2026-10-19)",
                        cle="GF-01 / futur"))
    exiger(ae04["derniere_date"] == "2021-11-05", "contrôle de AE-04 : dernier contrôle 2021-11-05 attendu")
    lignes.append(Ligne(["AE-04", ae04["nature"], "05/11/2021", "Extincteur n° 4 : pression basse.", "mineure", "01/11/2021",
                         "", "", ""], REFUSEE, "échéance de levée avant la date du contrôle (règle de l'ajout)",
                        cle="AE-04 / extincteur"))
    differentiel = reserve("Différentiel 30 mA du tableau de l'atelier à remplacer.")
    exiger((differentiel["levee"], differentiel["gravite"]) == ("1", ""), "réserve du différentiel : levée, sans gravité attendue")
    lignes.append(Ligne(["AE-01", ae01["nature"], francais_date(differentiel["date_controle"]), differentiel["texte"], "majeure",
                         "", "", "", ""], REFUSEE,
                        "%s déjà levée : elle ne se modifie plus (la levée est un fait) ; la fiche n'est pas touchée"
                        % differentiel["id"], cle="AE-01 / différentiel"))
    lignes.append(Ligne(["CH-01", ch01["nature"], "18/03/2026", "Avertisseur de recul inaudible.", "", "", "non", "20/03/2026",
                         "Avertisseur remplacé."], REFUSEE,
                        "« non » dans Levée avec une date de levée : contradiction", cle="CH-01 / avertisseur"))
    doublon = len(lignes)
    lignes.append(Ligne(["GF-01", gf01["nature"], "24/03/2026", raccord.upper(), "", "", "", "", ""], REFUSEE, None,
                        cle="GF-01 / raccord"))
    lignes.append(Ligne(["VE-02", ve02["nature"], "02/06/2026", "Gaine d'extraction percée.", "grave", "", "", "", ""], REFUSEE,
                        "gravité « grave » hors de la liste (mineure, majeure, critique)", cle="VE-02 / gaine"))
    lignes.append(Ligne(["PT-01", pt01["nature"], "", "Câble du palan : un toron cassé.", "", "", "", "", ""], REFUSEE,
                        "date du contrôle vide (règle de l'ajout : date du contrôle obligatoire)", cle="PT-01 / câble"))
    tableau = Tableau("reserves", "reserves", ENTETES_RESERVES, lignes)
    lignes[doublon].detail = ("doublon dans le fichier (même contrôle, même date et même texte, écrit en majuscules, que la "
                              "ligne %d)" % tableau.numero(premiere))
    return tableau


ENTETES_GAMMES =["Équipement", "Libellé", "Périodicité (jours)", "Temps prévu (heures)", "Dernière réalisation",
                  "Opération", "Valeur attendue"]


def gammes(demo, ids):
    lignes = []
    definitions = [
        ("SC-01", "Graissage et contrôle mensuel de la scie SC-01", 30, 1, "2026-10-01",
         [("Nettoyer les copeaux et vider le bac de récupération", ""),
          ("Contrôler la tension du ruban", "Flèche de 3 à 5 mm"),
          ("Graisser les guides du ruban", "")]),
        ("CV-03", "Contrôle trimestriel du convoyeur de sortie CV-03", 90, 0.75, "2026-09-15",
         [("Contrôler l'usure et le centrage de la bande", "Pas de déchirure"),
          ("Contrôler la rotation des rouleaux", "Aucun rouleau bloqué"),
          ("Contrôler le niveau d'huile du réducteur", "Entre mini et maxi")]),
    ]
    for repere, libelle, periodicite, temps, derniere, operations in definitions:
        eq = demo.equipement(repere)
        demo.absent("gammes", equipement_id=eq["id"], libelle=libelle)
        gamme = ids.nouveau("gammes")
        for ordre, (operation, valeur) in enumerate(operations, 1):
            detail = "%s, opération %d (ordre %d)" % (ids.nouveau("gamme_operations"), ordre, ordre)
            if ordre == 1:
                detail = ("**%s créée** (équipement %s, déclencheur « date » par défaut, périodicité %d j, temps "
                          "prévu %s h, dernière réalisation %s) ; " % (gamme, eq["id"], periodicite,
                                                                       nombre_texte(temps), derniere) + detail)
            else:
                detail = "même gamme %s répétée (pas un doublon) ; " % gamme + detail
            lignes.append(Ligne([repere, libelle, periodicite, temps, Jour(derniere), operation, valeur], CREER,
                                detail, cle=repere + " / " + libelle))
    for operation, valeur in (("Contrôler la planéité de la table magnétique", "Écart ≤ 0,01 mm"),
                              ("Vidanger le groupe hydraulique", "")):
        lignes.append(Ligne(["007", "Contrôle annuel de la rectifieuse 007", 365, 4, Jour("2026-01-20"), operation,
                             valeur], REFUSEE, "équipement « 007 » introuvable (toutes les lignes de cette gamme)",
                            cle="007 / Contrôle annuel de la rectifieuse 007"))
    lignes.append(Ligne(["PO-01", "", 180, 2, None, "Contrôler l'étanchéité de la garniture", ""], REFUSEE,
                        "libellé de gamme vide (clé naturelle équipement + libellé)", cle="PO-01 / (vide)"))
    return Tableau("gammes", "gammes", ENTETES_GAMMES, lignes)


ENTETES_HISTORIQUE = ["N° OT", "Machine", "Date demande", "Début", "Fin", "Type", "Libellé", "Compte rendu",
                      "Durée arrêt (h)", "Arrêt", "Symptôme", "Cause", "Remède", "Intervenant", "Temps (h)"]
TYPES_EQUIVALENTS = {"Dépannage": "correctif immédiat", "Curatif": "correctif immédiat",
                     "Correctif différé": "correctif différé", "Préventif": "préventif systématique",
                     "Amélioration": "amélioration", "Réglementaire": "réglementaire", "": "correctif différé"}
TECHNICIENS_HISTORIQUE = {"GARNIER Thomas": ("Thomas", "Garnier"), "Thomas Garnier": ("Thomas", "Garnier"),
                          "Karim Benali": ("Karim", "Benali"), "Julien Moreau": ("Julien", "Moreau"),
                          "Sophie Lambert": ("Sophie", "Lambert")}


def historique(demo, ids):
    """Historique d'une autre GMAO : une quinzaine d'OT clôturés (D92 et ses trois ajustements)."""
    ot_existant = demo.par_id("ordres_travail", "OT-2025-0002")
    cv02 = demo.equipement("CV-02")
    exiger(ot_existant["equipement_id"] == cv02["id"], "OT-2025-0002 attendu sur CV-02")
    exiger(not any("Ancien n°" in ot["compte_rendu"] for ot in demo.lignes("ordres_travail")),
           "aucun compte rendu de la démo ne doit déjà porter « Ancien n° »")

    def fr(date_heure):
        jour, heure = date_heure.split(" ")
        return francais_date(jour) + " " + heure

    brutes = [
        ["3987", "PO-01", "18/11/2024 15:45", "18/11/2024 16:00", "18/11/2024 17:30", "Dépannage",
         "Pompe ne démarre plus", "Contacteur de puissance hors service, remplacé. Essai de démarrage correct.",
         "1.5", "oui", "Ne démarre pas", "Contacteur hors service", "Remplacement de composant électrique",
         "GARNIER Thomas", "1.5"],
        ["3990", "SC-01", "09/12/2024 08:00", "09/12/2024 08:30", "09/12/2024 09:30", "Préventif",
         "Graissage mensuel de la scie", "Guides graissés, tension du ruban contrôlée.", "", "non", "", "", "",
         "Karim Benali", "1"],
        ["4512", "CP-01", "14/01/2025 07:40", "14/01/2025 08:05", "14/01/2025 10:30", "Dépannage",
         "Fuite d'huile au carter", "Joint de carter remplacé, niveau d'huile complété.", "2.5", "oui", "Fuite",
         "Garniture usée", "R01", "Karim Benali", "2.5"],
        ["4513", "PO-02", "03/02/2025 10:15", "03/02/2025 10:40", "03/02/2025 12:10", "Curatif",
         "Bruit anormal de la pompe", "Roulement côté accouplement remplacé, alignement contrôlé.", "1.5", "oui",
         "Bruit anormal", "Roulement hors service", "Remplacement de pièce", "Karim Benali", "1,75"],
        ["4514", "CV-02", "11/02/2025 06:50", "11/02/2025 07:05", "11/02/2025 07:50", "Dépannage",
         "Arrêts intempestifs du convoyeur", "Cellule de détection encrassée, nettoyée et réglée.", "0.75", "oui",
         "Arrêt intempestif", "Capteur encrassé", "Nettoyage", "Julien Moreau", "0.75"],
        ["4515", "PR-01", "24/02/2025 13:20", "24/02/2025 13:30", "24/02/2025 16:00", "Dépannage",
         "Fuite sur flexible hydraulique",
         'Flexible HP percé, remplacé par un flexible "DN10" serti.' + LF + "Essai sous pression : aucune fuite.",
         "", "oui", "S01", "C10", "R01", "Thomas Garnier", "2.5"],
        ["4516", "GF-01", "10/03/2025 09:00", "10/03/2025 09:15", "10/03/2025 12:15", "Préventif",
         "Entretien trimestriel du groupe froid", "Condenseurs nettoyés, pressions relevées et conformes.", "",
         "non", "", "", "", "Julien Moreau", "3"],
        ["4517", "CU-01", "19/03/2025 14:10", "20/03/2025 08:00", "20/03/2025 11:30", "Correctif différé",
         "Changeur d'outils bloqué en position", "Came d'indexage desserrée : resserrée et réglée.", "1.5", "oui",
         "Arrêt intempestif", "Desserrage", "Resserrage", "Sophie Lambert", "3.5"],
        ["4518", "EM-01", "02/04/2025 10:00", "07/04/2025 13:00", "07/04/2025 17:00", "Amélioration",
         "Ajout d'un capteur de présence film", "Capteur ajouté et câblé, programme modifié, essais concluants.",
         "", "non", "", "", "Modification", "Sophie Lambert", "4"],
        ["4519", "PT-01", "15/04/2025 08:00", "16/04/2025 08:00", "16/04/2025 10:00", "Réglementaire",
         "Levée des observations de la VGP", "Fin de course de levée réglé ; crochet remplacé par le constructeur.",
         "", "non", "", "", "", "Pierre Martel", ""],
        ["4520", "CP-01", "14/01/2025 07:40", "14/01/2025 08:10", "14/01/2025 10:20", "Dépannage",
         "Fuite d'huile au carter", "Joint du carter changé.", "2.5", "oui", "Fuite", "Garniture usée", "R01",
         "Karim Benali", "2.5"],
        ["4521", "CV-03", "", "", "05/05/2025 16:00", "Dépannage", "Bande déchirée en sortie de ligne",
         "Bande remplacée.", "1", "oui", "", "", "Remplacement de pièce", "Thomas Garnier", "1"],
        ["4522", "ET-01", "", "12/05/2025 09:30", "12/05/2025 10:15", "Dépannage", "Étiquettes posées de travers",
         "Tête de pose déréglée : réglage puis essai sur 50 étiquettes.", "0.5", "oui", "défaut qualité",
         "Dérive de réglage", "Réglage", "Thomas Garnier", "0.75"],
        ["4523", "XX-99", "19/05/2025 11:00", "19/05/2025 11:20", "19/05/2025 12:00", "Dépannage",
         "Fuite d'air sur le réseau", "Raccord resserré.", "", "non", "Fuite", "Desserrage", "Resserrage",
         "Julien Moreau", "0.5"],
        ["4524", "CH-01", "20/05/2025 14:00", "20/05/2025 14:20", "20/05/2025 16:20", "Dépannage",
         "Le chariot ne lève plus", "Fuite sur le vérin de levée, joint remplacé.", "2", "", "C04",
         "Usure générale", "Réparation", "Karim Benali", "2"],
        ["4525", "VE-01", "03/06/2025 07:30", "03/06/2025 08:00", "03/06/2025 09:10", "", "",
         "Courroie du ventilateur détendue : retendue et alignée, puis vibrations mesurées et correctes après "
         "remise en marche.", "", "non", "Vibration", "Courroie détendue", "Réglage", "Julien Moreau", "1"],
        ["4601", "CV-02", fr(ot_existant["date_creation"]), fr(ot_existant["date_debut"]),
         fr(ot_existant["date_fin"]), "Dépannage", ot_existant["titre"], "Cellule nettoyée, câblage vérifié.",
         "2", "oui", "S05", "C04", "R03", "Julien Moreau", "1"],
        ["4514", "CV-02", "11/02/2025 06:50", "11/02/2025 07:05", "11/02/2025 07:50", "Dépannage",
         "Arrêts intempestifs du convoyeur", "Cellule de détection encrassée, nettoyée et réglée.", "0.75", "oui",
         "Arrêt intempestif", "Capteur encrassé", "Nettoyage", "Julien Moreau", "1"],
    ]
    demo.absent("equipements", repere="XX-99")
    demo.absent("techniciens", nom="Martel")
    demo.sans_code("C04", "symptôme")
    demo.sans_code("Usure générale", "cause")

    lignes = []
    vus_numero = {}          # ancien numéro → index de la ligne
    vus_cle = {}             # (repère, date de création, titre) → index de la ligne
    for index, c in enumerate(brutes):
        (numero, machine, demande, debut, fin, type_libre, libelle, cr, duree, arret, sym, cause, rem,
         intervenant, temps) = c
        date_creation = iso_date_heure(demande or debut)
        extra = {"numero": numero, "machine": machine}
        if numero in vus_numero:
            lignes.append(Ligne(c, DOUBLON_SUR, None, renvoi=vus_numero[numero], **extra))
            continue
        if not demande and not debut:
            lignes.append(Ligne(c, REFUSEE, "ni date de demande ni date de début (la date de fin seule ne suffit "
                                            "pas) : ligne refusée", **extra))
            continue
        if not demo.trouver("equipements", repere=machine):
            lignes.append(Ligne(c, REFUSEE, "équipement « %s » introuvable (obligatoire)" % machine, **extra))
            continue
        eq = demo.equipement(machine)
        cle = (machine, date_creation, libelle.lower())
        if cle in vus_cle:
            lignes.append(Ligne(c, DOUBLON_SUPPOSE, None, renvoi=vus_cle[cle], **extra))
            continue
        existants = [ot for ot in demo.lignes("ordres_travail") if ot["equipement_id"] == eq["id"]
                     and ot["date_creation"] == date_creation and ot["titre"].lower() == libelle.lower()]
        if existants:
            lignes.append(Ligne(c, DOUBLON_SUPPOSE, "même équipement %s (%s), même date de création %s et même "
                                "titre que l'OT existant %s : montrée avec « Importer quand même » (non cochée)"
                                % (machine, eq["id"], date_creation, existants[0]["id"]), **extra))
            continue
        vus_numero[numero] = index
        vus_cle[cle] = index
        annee = date_creation[:4]
        type_ot = TYPES_EQUIVALENTS[type_libre]
        signalements = []
        if type_libre == "":
            signalements.append("type absent → « correctif différé » (signalé)")
        elif type_ot != type_libre.lower():
            signalements.append("type « %s » → « %s » (équivalence affichée)" % (type_libre, type_ot))
        titre = libelle
        if not libelle:
            titre = cr[:80]
            signalements.append("titre absent → 80 premiers caractères du compte rendu : « %s »" % titre)
        if not demande:
            signalements.append("date de demande absente → date de création = date de début")
        codes_ot = []
        for famille, valeur in (("symptôme", sym), ("cause", cause), ("remède", rem)):
            if not valeur:
                codes_ot.append("—")
                continue
            par_code = demo.trouver("codes_defaillance", famille=famille, code=valeur)
            par_libelle = [x for x in demo.trouver("codes_defaillance", famille=famille)
                           if valeur.lower() == x["libelle"].lower()]
            if par_code or par_libelle:
                code = (par_code or par_libelle)[0]
                codes_ot.append(code["code"])
                if not par_code and valeur != code["libelle"]:
                    signalements.append("%s « %s » → %s (libellé « %s », casse ignorée)"
                                        % (famille, valeur, code["code"], code["libelle"]))
            else:
                codes_ot.append("vide")
                signalements.append("%s « %s » introuvable dans la famille %s → vide (signalé, aucun code créé)"
                                    % (famille, valeur, famille))
        if intervenant in TECHNICIENS_HISTORIQUE:
            technicien = demo.technicien(*TECHNICIENS_HISTORIQUE[intervenant])["id"]
            if intervenant.split(" ")[0].isupper():
                signalements.append("intervenant écrit « NOM Prénom »")
        else:
            technicien = ""
            signalements.append("intervenant « %s » introuvable → technicien vide (signalé)" % intervenant)
        arret_production = "1" if (arret == "oui" or (arret == "" and duree and float(duree) > 0)) else "0"
        if arret == "" and arret_production == "1":
            signalements.append("colonne Arrêt vide mais durée > 0 → arrêt de production 1")
        if arret == "oui" and not duree:
            signalements.append("arrêt sans durée : durée d'arrêt **vide** (jamais 0), panne exclue du MTTR et de "
                                "la disponibilité (ajustement 3)")
        # Cas laissé ouvert par le contrat (temps sans technicien) : évité exprès par ce fichier.
        exiger(technicien or not temps, "historique : temps passé sans technicien (cas non spécifié)")
        if temps:
            ligne_temps = "%s : %s h (%s, %s)" % (ids.nouveau("ot_temps"), temps.replace(",", "."), technicien,
                                                   iso_date_heure(fin)[:10])
        else:
            ligne_temps = "aucune (temps vide)"
        if titre != libelle:
            exiger(cr[80:81] in ("", " "), "titre tiré du compte rendu : la coupe à 80 caractères doit finir un mot")
        origine = "préventif" if type_ot.startswith("préventif") else "manuel"
        attendu = {
            "ot": ids.nouveau("ordres_travail", annee), "equipement": eq["id"], "type": type_ot, "origine": origine,
            "titre": titre, "creation": date_creation, "debut": iso_date_heure(debut), "fin": iso_date_heure(fin),
            "arret": arret_production, "duree": duree.replace(",", "."), "codes": " / ".join(codes_ot),
            "technicien": technicien or "vide", "temps": ligne_temps, "signalements": signalements,
        }
        lignes.append(Ligne(c, CREER, None, attendu=attendu, **extra))
    tableau = Tableau("historique", "historique", ENTETES_HISTORIQUE, lignes)
    for ligne in lignes:
        if ligne.action == DOUBLON_SUR:
            ligne.detail = ("même ancien numéro « %s » que la ligne %d, plus haut dans le même fichier : doublon "
                            "sûr, ignorée" % (ligne.extra["numero"], tableau.numero(ligne.extra["renvoi"])))
        elif ligne.action == DOUBLON_SUPPOSE and ligne.detail is None:
            ligne.detail = ("même machine, même date de création à la minute et même titre que la ligne %d "
                            "(n° %s), numéro différent : montrée avec « Importer quand même » (non cochée)"
                            % (tableau.numero(ligne.extra["renvoi"]), lignes[ligne.extra["renvoi"]].extra["numero"]))
    return tableau


def lignes_essai(nombre):
    """Grille d'articles d'essai pour les plafonds de lignes : en-tête + nombre lignes de données."""
    texte = ["Référence;Désignation;Qté stock" + CRLF]
    texte += ["ESS-%05d;Essai %d;1%s" % (i, i, CRLF) for i in range(1, nombre + 1)]
    return encoder("".join(texte), "utf-8", bom=True)


# ---------------------------------------------------------------------------
# LISEZMOI.md
# ---------------------------------------------------------------------------

def cellule_md(texte):
    return str(texte).replace("|", "\\|").replace("\r", "").replace("\n", " ↵ ")


def tableau_md(entetes, lignes):
    sortie = ["| " + " | ".join(entetes) + " |", "|" + "|".join(" --- " for _ in entetes) + "|"]
    sortie += ["| " + " | ".join(cellule_md(valeur) for valeur in ligne) + " |" for ligne in lignes]
    return "\n".join(sortie)


def lignes_attendues_md(tableau, regrouper_identiques=False):
    """Tableau « Ligne | Clé | Action | Détail » ; les identiques consécutives peuvent être regroupées."""
    rangees = []
    groupe = []

    def vider_groupe():
        if not groupe:
            return
        if len(groupe) == 1:
            i = groupe[0]
            rangees.append([tableau.numero(i), tableau.lignes[i].extra.get("cle", ""), IDENTIQUE,
                            tableau.lignes[i].detail])
        else:
            rangees.append(["%d à %d" % (tableau.numero(groupe[0]), tableau.numero(groupe[-1])),
                            "%d fiches de la démo" % len(groupe), IDENTIQUE,
                            "aucune colonne importée ne change (%s à %s)" % (
                                tableau.lignes[groupe[0]].detail.split(" ")[0],
                                tableau.lignes[groupe[-1]].detail.split(" ")[0])])
        groupe.clear()

    for i, ligne in enumerate(tableau.lignes):
        if regrouper_identiques and ligne.action == IDENTIQUE:
            groupe.append(i)
            continue
        vider_groupe()
        rangees.append([tableau.numero(i), ligne.extra.get("cle", ""), ligne.action, ligne.detail])
    vider_groupe()
    return tableau_md(["Ligne", "Clé", "Action attendue", "Détail"], rangees)


def totaux_md(tableau):
    t = tableau.totaux()
    morceaux = ["%d %s" % (t[action], action) for action in ACTIONS if t[action]]
    return "%d lignes de données : %s." % (len(tableau.lignes), ", ".join(morceaux))


def section_equipements(t):
    return """## equipements.xlsx, equipements.ods, equipements.xls — liste du parc d'un atelier

- **Type de données** : `equipements` (tables écrites : `localisations`, `equipements`).
- **Formats** : `.xlsx` écrit en Python (sans SheetJS) ; `.ods` (mêmes données) ; `.xls` ancien format BIFF8
  écrit par SheetJS 0.20.3 dans Chromium (mêmes données). Deux feuilles : **« Parc »** (les données) puis
  « Notes » (deux lignes de texte, à ne pas importer : la feuille « Parc » est la première, proposée par défaut).
- **Ligne 1** : titre « %(titre)s » (une seule cellule, A1 ; dans le .xlsx, chaîne « en ligne » `inlineStr`).
  **Ligne 2** : l'en-tête (`Import.ligneEntete` doit rendre le rang 1, soit la 2ᵉ ligne). Données : lignes 3 à %(fin)d.
- **Colonnes, dans le désordre** (A à I) : %(entetes)s.

| Colonne | Champ attendu | Statut attendu |
| --- | --- | --- |
| Désignation | `designation` | sûre (libellé) |
| Code machine | `repere` (clé naturelle) | sûre (synonyme) |
| Fabricant | `marque` | sûre (synonyme) |
| Mise en service | `date_mes` | sûre (synonyme) |
| Emplacement | `chemin_localisation` (localisation par chemin) | sûre (synonyme de la localisation) |
| N° de série | `num_serie` | sûre (synonyme) |
| Criticité | `criticite` | sûre (libellé) |
| Machine mère | `parent` (équipement parent par repère) | sûre (synonyme) |
| Commentaire | — | **non utilisée** (colonne inconnue) |

**Pièges** :
- repère « 007 » (ligne %(l007)d) : texte à zéros en tête, à garder tel quel ; n° de série « %(ns_ra)s » (RA-01,
  ligne %(lra)d) et « 0042-117 » : texte ; n° de série « 1E5 » (ligne %(lpur)d) : texte, jamais 100000 ;
- dates de mise en service en **numéros de série Excel (système 1900)** avec un style de date `dd/mm/yyyy`
  (.xlsx : `<c s="1"><v>44333</v>` pour le 2021-05-17 ; .xls : même nombre et même format ; .ods :
  `office:date-value`) → la lecture les rend en `AAAA-MM-JJ` ; une date écrite **en texte** « 15/03/2024 »
  (ligne %(lpur)d), convertie par l'aperçu en 2024-03-15 ; une cellule de date vide (ligne %(lmt)d) ;
- localisation **nouvelle** « %(chemin)s » (lignes %(l007)d et %(l007ta)d) : un seul niveau manque (la ligne) → une
  seule localisation créée (D88), réutilisée à la ligne suivante ; chemin écrit avec « / » (ligne %(lpo)d) ;
- équipement parent **cité plus bas** : « 007 » est créé ligne %(l007)d puis cité comme machine mère ligne
  %(l007ta)d ; « CP-01 » (base) cité ligne %(lpur)d ; parent inconnu « XX-99 » (ligne %(lpe)d) ;
- un repère existant mis à jour (PO-02, ligne %(lpo)d) et quatorze repères existants identiques (les machines de la
  démo que citent les autres fichiers d'essai, pour qu'ils s'enchaînent aussi sur une base vide) ;
- lignes en erreur : criticité « Z » (ligne %(lsc)d), désignation vide (ligne %(ltr)d), machine mère introuvable
  (ligne %(lpe)d) ;
- .ods : cellules vides répétées au milieu des lignes (`table:number-columns-repeated`, par exemple les six cellules
  vides de la ligne %(lmt)d avant « Commentaire ») et en fin de ligne jusqu'à la 1 024ᵉ colonne ; lignes vides
  répétées jusqu'à la 1 048 576ᵉ (`table:number-rows-repeated`) : la lecture doit rendre %(nb)d lignes sur 9
  colonnes, sans décaler les colonnes ni lire un million de lignes.

**Attendu** (base de démo, « Compléter et mettre à jour » coché) : %(totaux)s Équipements créés dans l'ordre du
fichier ; références créées : localisation %(loc)s « %(ligne)s » (type `ligne`, parent « Atelier Usinage »).

%(table)s
""" % {
        "titre": TITRE_PARC, "fin": t.numero(len(t.lignes) - 1), "entetes": ", ".join("« %s »" % e for e in t.entetes),
        "l007": numero_cle(t, "007"), "l007ta": numero_cle(t, "007.TA"), "lra": numero_cle(t, "RA-01"),
        "lpur": numero_cle(t, "CP-01.PUR"), "lmt": numero_cle(t, "MT-01"), "lpo": numero_cle(t, "PO-02"),
        "lpe": numero_cle(t, "PE-02"), "lsc": numero_cle(t, "SC-02"), "ltr": numero_cle(t, "TR-01"),
        "ns_ra": t.lignes[numero_cle(t, "RA-01") - t.ligne_entete - 1].cellules[5],
        "chemin": t.lignes[numero_cle(t, "007") - t.ligne_entete - 1].cellules[4], "nb": len(t.grille()),
        "totaux": totaux_md(t), "loc": t.loc_creee, "ligne": NOUVELLE_LIGNE, "table": lignes_attendues_md(t),
    }


def numero_cle(tableau, cle):
    for i, ligne in enumerate(tableau.lignes):
        if ligne.extra.get("cle") == cle:
            return tableau.numero(i)
    exiger(False, "clé %s absente de %s" % (cle, tableau.nom))


def section_simple(nom_fichier, tableau, format_texte, correspondance, pieges, regrouper=False, apres=""):
    lignes_corr = tableau_md(["Colonne", "Champ attendu", "Statut attendu"], correspondance)
    return """## %s

- **Type de données** : `%s`.
- **Format** : %s
- **En-tête** : ligne %d ; colonnes %s.

%s

**Pièges** :
%s

**Attendu** (base de démo) : %s%s

%s
""" % (nom_fichier, tableau.type_donnees, format_texte, tableau.ligne_entete,
       ", ".join("« %s »" % e for e in tableau.entetes), lignes_corr, "\n".join("- " + p for p in pieges),
       totaux_md(tableau), (" " + apres) if apres else "", lignes_attendues_md(tableau, regrouper))


def section_historique(t):
    rangees = []
    for i, ligne in enumerate(t.lignes):
        numero = t.numero(i)
        if ligne.action == CREER:
            a = ligne.extra["attendu"]
            rangees.append([numero, ligne.extra["numero"], ligne.extra["machine"], CREER, a["ot"],
                            "%s (%s)" % (a["type"], a["origine"]),
                            "%s → %s → %s" % (a["creation"], a["debut"][11:] if a["debut"][:10] == a["creation"][:10]
                                              else a["debut"], a["fin"][11:] if a["fin"][:10] == a["debut"][:10]
                                              else a["fin"]),
                            "%s / %s" % (a["arret"], a["duree"] or "vide"), a["codes"], a["technicien"], a["temps"],
                            " ; ".join(a["signalements"]) or "—"])
        else:
            rangees.append([numero, ligne.extra["numero"], ligne.extra["machine"], ligne.action, "—", "—", "—", "—",
                            "—", "—", "—", ligne.detail])
    table = tableau_md(["Ligne", "N° OT", "Machine", "Action", "OT attendu", "Type (origine)",
                        "Création → début → fin", "Arrêt / durée (h)", "Codes S / C / R", "Technicien",
                        "Ligne ot_temps", "Remarques"], rangees)
    crees = [l for l in t.lignes if l.action == CREER]
    return """## historique.csv — historique d'une autre GMAO (D92)

- **Type de données** : `historique` (tables écrites : `ordres_travail`, `ot_temps`).
- **Format** : CSV **UTF-8 sans BOM**, séparateur « , », fins de ligne CRLF, décimales à point (et une à virgule,
  « 1,75 », entre guillemets), champs entre guillemets quand ils contiennent « , », « " » ou un saut de ligne
  (ligne %(l4515)d : compte rendu sur deux lignes avec des guillemets doublés). Dates **JJ/MM/AAAA HH:MM**.
- **En-tête** : ligne 1 ; %(n)d lignes de données (lignes 2 à %(fin)d).

| Colonne | Champ attendu |
| --- | --- |
| N° OT | `ancien_numero` (écrit en tête du compte rendu : `Ancien n° : <numéro>`, ajustement 1) |
| Machine | `equipement` (par repère, obligatoire) |
| Date demande | `date_creation` |
| Début | `date_debut` |
| Fin | `date_fin` |
| Type | `type` (libellés libres, correspondance tolérante) |
| Libellé | `titre` |
| Compte rendu | `compte_rendu` |
| Durée arrêt (h) | `duree_arret_h` |
| Arrêt | `arret_production` (oui / non) |
| Symptôme, Cause, Remède | `symptome_code`, `cause_code`, `remede_code` (par code ou par libellé, dans la bonne famille) |
| Intervenant | `technicien` (par nom) |
| Temps (h) | `temps_passe_h` (→ une ligne `ot_temps`) |

Aucune colonne « Priorité » : chaque OT créé reçoit **P3**, signalée. Chaque OT créé est « Clôturé
administrativement », `date_cloture_tech` = `date_cloture_admin` = date de fin, `remise_service` 1 ; son compte
rendu vaut `Ancien n° : <N° OT>` + saut de ligne + le compte rendu du fichier. Aucun OT existant n'est modifié.

**Pièges** : libellés de type libres (« Dépannage », « Curatif », « Préventif »…) et type absent ; codes par code
(« R01 »), par libellé (« Fuite »), par libellé en minuscules (« défaut qualité ») ; un code d'une autre famille
(« C04 » en symptôme) et un libellé inconnu (« Usure générale ») ; intervenant inconnu (« Pierre Martel ») et
écrit « NOM Prénom » ; durées d'arrêt vides (avec « Arrêt » à non, et une avec « Arrêt » à oui, ligne %(l4515)d) ;
colonne « Arrêt » vide avec une durée (ligne %(l4524)d) ; dates de 2024 et de 2025 (numéros `OT-2024-…` et
`OT-2025-…`) ; **doublon supposé** dans le fichier (ligne %(l4520)d : même machine, même date, même libellé que la
ligne %(l4512)d, numéro différent) et contre un OT existant (ligne %(l4601)d, OT-2025-0002) ; **doublon sûr** : même
N° OT deux fois dans le fichier (lignes %(l4514)d et %(l4514b)d) ; ligne sans date de demande ni de début (refusée,
ligne %(l4521)d) ; date de demande vide mais début renseigné (ligne %(l4522)d) ; machine inconnue (ligne %(l4523)d).

**Attendu** (base de démo, aucune case « Importer quand même » cochée) : %(totaux)s
%(nb_ot)d OT créés (%(premier)s à %(dernier)s, numéros de l'année de création, dans l'ordre du fichier) et
%(nb_temps)d lignes `ot_temps`. Les identifiants supposent les doublons supposés non importés.
**Réimport** du même fichier après cet import : 0 OT créé (les %(nb_ot)d lignes créées et la ligne %(l4514b)d →
doublons sûrs par l'ancien numéro ; ligne %(l4520)d → doublon supposé de l'OT créé pour la ligne %(l4512)d ;
ligne %(l4601)d → doublon supposé d'OT-2025-0002 ; lignes %(l4521)d et %(l4523)d → refusées).

Équivalences de type attendues : « Dépannage », « Curatif » → correctif immédiat ; « Préventif » → préventif
systématique (origine « préventif », sans gamme) ; « Correctif différé », « Amélioration », « Réglementaire » →
même valeur ; absent → correctif différé (signalé). Origine « manuel » pour les autres types.

%(table)s
""" % {
        "n": len(t.lignes), "fin": t.numero(len(t.lignes) - 1), "totaux": totaux_md(t), "nb_ot": len(crees),
        "premier": crees[0].extra["attendu"]["ot"], "dernier": crees[-1].extra["attendu"]["ot"],
        "nb_temps": sum(1 for l in crees if l.extra["attendu"]["temps"].startswith("OTT-")),
        "l4515": numero_historique(t, "4515"), "l4524": numero_historique(t, "4524"),
        "l4520": numero_historique(t, "4520"), "l4512": numero_historique(t, "4512"),
        "l4601": numero_historique(t, "4601"), "l4514": numero_historique(t, "4514"),
        "l4514b": numero_historique(t, "4514", 1), "l4521": numero_historique(t, "4521"),
        "l4522": numero_historique(t, "4522"), "l4523": numero_historique(t, "4523"), "table": table,
    }


def numero_historique(tableau, numero, rang=0):
    trouves = [tableau.numero(i) for i, l in enumerate(tableau.lignes) if l.extra["numero"] == numero]
    return trouves[rang]


def lisezmoi(tableaux, demo):
    eq, art, fou, tec, hab, cod, cpt, ctr, gam, his, gar, con, res = (tableaux[n] for n in (
        "equipements", "articles", "fournisseurs", "techniciens", "habilitations", "codes", "compteurs",
        "controles", "gammes", "historique", "garanties", "contrats", "reserves"))
    vue = []
    for nom, tableau, format_texte in (
            ("equipements.xlsx / .ods / .xls", eq, "classeur (3 formats)"),
            ("articles.csv", art, "CSV Windows-1252 « ; »"),
            ("fournisseurs.tsv", fou, "collage tabulé UTF-8"),
            ("techniciens.tsv", tec, "collage tabulé UTF-8"),
            ("habilitations.csv", hab, "CSV UTF-8 BOM « ; »"),
            ("codes.csv", cod, "CSV UTF-8 « ; », fins LF"),
            ("compteurs.csv", cpt, "CSV Windows-1252 « ; »"),
            ("controles.csv", ctr, "CSV UTF-8 BOM « ; »"),
            ("gammes.xlsx", gam, "classeur .xlsx"),
            ("historique.csv", his, "CSV UTF-8 « , »"),
            ("garanties.csv", gar, "CSV UTF-8 BOM « ; »"),
            ("contrats.csv", con, "CSV UTF-8 BOM « ; »"),
            ("reserves.csv", res, "CSV UTF-8 BOM « ; »")):
        tot = tableau.totaux()
        autres = ", ".join("%d %s" % (tot[a], a) for a in (DOUBLON_SUR, DOUBLON_SUPPOSE) if tot[a]) or "—"
        vue.append([nom, format_texte, "`%s`" % tableau.type_donnees, len(tableau.lignes), tot[CREER], tot[MAJ],
                    tot[IDENTIQUE], tot[REFUSEE], autres])
    vue_md = tableau_md(["Fichier", "Format", "Type", "Données", "Créer", "Mettre à jour", "Identique", "Refusées",
                         "Autres"], vue)

    sections = [
        """# Fichiers d'essai de l'import (lot 5)

Écrits par `py outils/generer_fixtures_import.py` (docs/ARCHITECTURE.md §18.10, tâche T79). **Ne pas les modifier
à la main** : relancer le générateur, qui réécrit les mêmes octets (dates des archives fixées, aucun horodatage) ;
`tests/test_fixtures_import.py` vérifie la régénération à l'octet et la présence de chaque piège annoncé ici.
`.gitattributes` les protège (`tests/fixtures/import/** -text`). Aucune donnée personnelle réelle : noms de
personnes et d'entreprises inventés, adresses en `.example`, comme le jeu de démo.

## Conventions des attentes

- **Base de référence** : le jeu de démo du dépôt (`donnees/demo/`), tel quel. Chaque fichier est importé **seul**
  sur cette base, avec le type de données indiqué, la correspondance de colonnes attendue, la case « Compléter et
  mettre à jour les fiches existantes » **cochée** (défaut, D84 a) et aucune case « Importer quand même » cochée.
- **Ligne** : numéro de ligne du fichier tel que l'affiche un tableur (1 = première ligne du fichier, titre et
  en-tête compris ; une cellule entre guillemets sur plusieurs lignes compte pour une seule ligne).
- **Actions** (§18.5, §18.6) : `créer` ; `mettre à jour` (seules les colonnes importées **non vides** qui changent,
  avant → après) ; `identique` ; `refusée` (avec sa raison ; le texte exact du message est libre, la nature de la
  raison ne l'est pas) ; pour l'historique, `doublon sûr` (ignorée) et `doublon supposé` (montrée avec « Importer
  quand même », non importée par défaut).
- **Identifiants** : ceux que donne `Donnees.nouvelId` sur la démo (plus grand numéro existant + 1), attribués dans
  l'ordre du fichier, table par table.
- Valeurs converties par `Donnees.normaliser` (dates `AAAA-MM-JJ`, décimales à point, booléens `0`/`1`) ; les
  champs protégés (repère, n° de série, référence, réf. fabricant, téléphone) gardent leur texte exact.

## Vue d'ensemble

""" + vue_md + "\n",
        section_equipements(eq),
        section_simple("articles.csv — export d'une autre GMAO", art,
                       "CSV **Windows-1252** (pas UTF-8 : la lecture doit retomber sur Windows-1252), séparateur "
                       "« ; », fins de ligne CRLF, décimales à virgule.",
                       [["Code article", "`reference` (clé naturelle)", "sûre (synonyme)"],
                        ["Libellé", "`designation`", "sûre (synonyme)"],
                        ["Famille", "—", "**non utilisée** (colonne inconnue)"],
                        ["Marque", "`fabricant`", "sûre (synonyme)"],
                        ["Réf. fabricant", "`ref_fabricant`", "sûre (synonyme)"],
                        ["Casier", "`emplacement`", "sûre (synonyme)"],
                        ["Unité", "`unite`", "sûre (libellé)"],
                        ["Qté stock", "`stock_initial` (→ mouvement « inventaire »)", "sûre (synonyme du stock)"],
                        ["Stock mini", "`stock_securite`", "sûre (synonyme)"],
                        ["Prix achat", "`prix_unitaire`", "sûre (synonyme)"],
                        ["Fournisseur", "`fournisseur` (par nom, créé s'il manque)", "sûre (synonyme)"],
                        ["Délai livraison", "`delai_jours`", "sûre (synonyme)"]],
                       ["caractères propres à Windows-1252 : « Œ » (0x8C, ligne %d), apostrophe typographique "
                        "« %s » (0x92) et « Ø » (ligne %d), espace insécable 0xA0 dans « 1 250,00 » (ligne %d) ; "
                        "lus faux en ISO-8859-1 ou en UTF-8 ;" % (numero_cle(art, "FIX-010"), APOSTROPHE,
                                                               numero_cle(art, "JNT-201"), numero_cle(art, "VAR-001")),
                        "prix et stocks à virgule (« 5,15 », « 120,5 ») ; « 0 » en stock (inventaire de 0) et stock "
                        "vide (aucun mouvement) ;",
                        "fournisseur inconnu « %s » cité deux fois : créé une seule fois (D88) ;" % NOUVEAU_FOURNISSEUR,
                        "référence « ROU-101 » en double dans le fichier ; référence existante mise à jour "
                        "(ROU-001) et identique (FIL-001) ;",
                        "désignation vide ; délai « 2 semaines » illisible."],
                       apres=art.resume[0].upper() + art.resume[1:] + "."),
        section_simple("fournisseurs.tsv — collage depuis Excel", fou,
                       "texte tabulé (collage : tabulation entre les cellules, CRLF à chaque fin de ligne, y "
                       "compris la dernière), UTF-8 sans BOM. Peut aussi être collé dans la zone de collage.",
                       [["Raison sociale", "`nom` (clé naturelle)", "sûre (synonyme)"],
                        ["Interlocuteur", "`contact`", "sûre (synonyme)"],
                        ["Tél", "`telephone`", "sûre (synonyme)"],
                        ["Courriel", "`email`", "sûre (synonyme)"]],
                       ["téléphones à zéro en tête et avec espaces (champ protégé, texte exact) ;",
                        "ligne aux cellules finales vides (tabulations en fin de ligne) ;",
                        "raison sociale vide."]),
        section_simple("techniciens.tsv — collage depuis Excel", tec,
                       "texte tabulé (collage), UTF-8 sans BOM, CRLF.",
                       [["Nom", "`nom` (clé naturelle avec le prénom)", "sûre (libellé)"],
                        ["Prénom", "`prenom`", "sûre (libellé)"],
                        ["Fonction", "`metier`", "sûre (synonyme)"],
                        ["Coût horaire", "`taux_horaire`", "sûre (synonyme)"],
                        ["h/semaine", "`capacite_h_semaine`", "sûre (synonyme)"]],
                       ["les quatre techniciens de la démo (un mis à jour, trois identiques) : ils existent ainsi "
                        "aussi sur une base vide ;", "taux à virgule « 41,50 » ;", "nom vide."]),
        section_simple("habilitations.csv", hab, "CSV UTF-8 **avec BOM**, séparateur « ; », CRLF, dates JJ/MM/AAAA.",
                       [["Technicien", "`technicien` (par « Prénom Nom » ou « Nom Prénom », doit exister)",
                         "sûre (libellé)"],
                        ["Habilitation", "`intitule`", "sûre (synonyme)"],
                        ["Obtenue le", "`date_obtention`", "sûre (synonyme)"],
                        ["Valable jusqu'au", "`date_echeance`", "sûre (synonyme)"]],
                       ["technicien écrit « Prénom Nom » et « Nom Prénom » (ligne %d) ;" % numero_cle(hab, "Garnier Thomas / BR"),
                        "technicien inconnu de la base (jamais créé : la ligne est refusée) ;",
                        "date impossible « 31/02/2026 »."]),
        section_simple("codes.csv — codes de défaillance", cod,
                       "CSV UTF-8 **sans BOM**, séparateur « ; », fins de ligne **LF** (pas CRLF).",
                       [["Famille", "`famille` (correspondance tolérante)", "sûre (libellé)"],
                        ["Code", "`code`", "sûre (libellé)"],
                        ["Libellé", "`libelle`", "sûre (libellé)"]],
                       ["familles écrites librement : « Symptome », « CAUSE », « Remede », « symptôme », « Cause », "
                        "« remède », « REMÈDE » → symptôme, cause, remède ; famille hors liste « Défaut » ;",
                        "les %d codes de la démo (identiques ; ils existent ainsi aussi sur une base vide) et quatre "
                        "nouveaux ;" % len(demo.lignes("codes_defaillance")),
                        "code vide ; même famille + code deux fois (C15)."], regrouper=True),
        section_simple("compteurs.csv", cpt, "CSV **Windows-1252**, séparateur « ; », CRLF.",
                       [["Repère", "`equipement` (par repère, doit exister)", "sûre (synonyme attendu de l'équipement)"],
                        ["Libellé", "`libelle`", "sûre (libellé)"],
                        ["Unité", "`unite`", "sûre (libellé)"]],
                       ["équipement par repère ; repère « 007 » inconnu de la démo ; repère vide ;",
                        "compteur existant identique et compteur existant dont l'unité change."]),
        section_simple("controles.csv — contrôles réglementaires", ctr,
                       "CSV UTF-8 **avec BOM**, séparateur « ; », CRLF, dates JJ/MM/AAAA.",
                       [["Équipement", "`equipement` (par repère, doit exister)", "sûre (synonyme attendu)"],
                        ["Nature du contrôle", "`nature` (clé naturelle avec l'équipement)", "sûre (libellé)"],
                        ["Texte de référence", "`texte_reference`", "sûre (libellé)"],
                        ["Périodicité (mois)", "`periodicite_mois`", "sûre (libellé)"],
                        ["Organisme de contrôle", "`organisme`", "sûre (libellé)"],
                        ["Date du dernier contrôle", "`derniere_date`", "sûre (libellé)"],
                        ["Date du prochain contrôle", "`prochaine_date`", "sûre (libellé)"],
                        ["Observations", "`observations` → réserves des contrôles (une par ligne non vide, D183 ; "
                         "colonne `observations` du contrôle jamais écrite)", "sûre (nom du champ)"]],
                       ["« ; » dans un champ entre guillemets (ligne %d) ;" % numero_cle(ctr, "PR-01"),
                        "observations sur deux lignes (ligne %d, champ entre guillemets) : deux réserves (2.2, T489) ;"
                        % numero_cle(ctr, "CH-01"),
                        "périodicité « 12 mois » illisible sur une fiche existante (refusée, la fiche ne change pas) ;",
                        "équipement inconnu « XX-99 »."]),
        section_simple("gammes.xlsx — gammes de préventif, une ligne par opération", gam,
                       ".xlsx écrit en Python (sans SheetJS), une feuille « Gammes » ; périodicités et temps en "
                       "nombres, dernière réalisation en numéro de série Excel avec style de date.",
                       [["Équipement", "`equipement` (par repère, doit exister)", "sûre (synonyme attendu)"],
                        ["Libellé", "`libelle` (clé naturelle avec l'équipement)", "sûre (libellé)"],
                        ["Périodicité (jours)", "`periodicite_jours`", "sûre (libellé)"],
                        ["Temps prévu (heures)", "`temps_prevu_h`", "sûre (libellé)"],
                        ["Dernière réalisation", "`derniere_realisation`", "sûre (libellé)"],
                        ["Opération", "`operations` (une ligne par opération)", "sûre (libellé)"],
                        ["Valeur attendue", "`valeur_attendue` de l'opération", "sûre (libellé)"]],
                       ["une ligne par opération : la même gamme (équipement + libellé) répétée sur trois lignes "
                        "n'est **pas** un doublon ; l'ordre des opérations est celui du fichier (1, 2, 3) ;",
                        "nombre décimal 0.75 ; « ≤ » dans une valeur attendue ;",
                        "gamme d'un équipement inconnu (« 007 ») sur deux lignes ; libellé de gamme vide."]),
        section_historique(his),
        section_simple("garanties.csv — garanties des équipements (2.2)", gar,
                       "CSV UTF-8 **avec BOM**, séparateur « ; », CRLF, dates JJ/MM/AAAA.",
                       [["Repère", "`equipement` (par repère, doit exister ; clé naturelle avec la fin)", "sûre (synonyme)"],
                        ["Fournisseur", "`fournisseur` (par nom, créé s'il manque)", "sûre (libellé)"],
                        ["Date de début", "`date_debut`", "sûre (synonyme)"],
                        ["Échéance", "`date_fin` (clé naturelle avec l'équipement)", "sûre (synonyme)"],
                        ["Ce qui est couvert", "`conditions`", "sûre (synonyme)"]],
                       ["clé naturelle équipement + date de fin : une deuxième garantie du même équipement (PO-01, "
                        "autre fin) est une création, pas une mise à jour ;",
                        "« ; » dans les conditions (ligne %d, champ entre guillemets) ;" % gar.numero(0),
                        "fournisseur inconnu créé une fois (D88 a), mais pas celui d'une ligne refusée (lignes %d et %d) ;"
                        % (numero_cle(gar, "PR-01 / (vide)"), numero_cle(gar, "SC-01 / 2026-03-01")),
                        "fournisseur et date de début vides (facultatifs) ; fin avant le début (formulaire) ; échéance "
                        "vide ; date impossible ; équipement inconnu ; doublon dans le fichier."],
                       apres=gar.resume[0].upper() + gar.resume[1:] + "."),
        section_simple("contrats.csv — contrats de prestataires (2.2)", con,
                       "CSV UTF-8 **avec BOM**, séparateur « ; », CRLF, dates JJ/MM/AAAA, décimales à virgule.",
                       [["Prestataire", "`prestataire` (par nom, créé s'il manque ; clé naturelle avec l'objet)",
                         "sûre (libellé)"],
                        ["Objet", "`objet`", "sûre (libellé)"],
                        ["Équipements", "`equipements_concernes` → `equipement_ids` (repères → identifiants séparés "
                         "par « ; »)", "sûre (synonyme)"],
                        ["Début", "`date_debut`", "sûre (libellé)"],
                        ["Fin", "`date_fin`", "sûre (libellé)"],
                        ["Préavis", "`preavis_mois`", "sûre (synonyme)"],
                        ["Tacite reconduction", "`reconduction_tacite`", "sûre (synonyme)"],
                        ["Montant annuel HT", "`montant_annuel` (devise réglée, hors taxes, D190)", "sûre (libellé)"],
                        ["Périmètre", "`perimetre`", "sûre (libellé)"]],
                       ["équipements concernés en repères séparés par des virgules (« CP-01, CP-01.SEC ») ou par « ; » "
                        "(ligne %d, champ entre guillemets) ; un repère inconnu (« CV-09 », ligne %d) refuse sa ligne, les "
                        "autres s'importent ;" % (numero_cle(con, "Garnitech Pompes / pompes"),
                                                  numero_cle(con, "Lubrifix Industrie / convoyeurs")),
                        "prestataire inconnu créé une fois, écrit aussi en majuscules (doublon ligne %d) ; celui d'une "
                        "ligne refusée n'est pas créé ;" % numero_cle(con, NOUVEAU_GARANT + " / groupe froid"),
                        "montant « 2 350,50 » (espace, virgule) ; montant vide (facultatif) ; montant négatif sur une "
                        "fiche existante (refusée, la fiche ne change pas) ; préavis « trois » ; prestataire vide ;",
                        "contrat existant identique et contrat existant mis à jour (fin et montant ; cellules vides : rien "
                        "d'effacé)."],
                       apres=con.resume[0].upper() + con.resume[1:] + "."),
        section_simple("reserves.csv — réserves des contrôles (2.2)", res,
                       "CSV UTF-8 **avec BOM**, séparateur « ; », CRLF, dates JJ/MM/AAAA.",
                       [["Repère", "`equipement` (par repère, doit exister ; désigne le contrôle avec la nature)", "sûre (synonyme)"],
                        ["Nature du contrôle", "`nature` → `controle_id` (contrôle de cet équipement, doit exister)",
                         "sûre (libellé)"],
                        ["Date du contrôle", "`date_controle` (clé naturelle avec le contrôle et le texte)", "sûre (libellé)"],
                        ["Réserve", "`texte` (clé naturelle)", "sûre (libellé)"],
                        ["Gravité", "`gravite` (mineure, majeure, critique)", "sûre (libellé)"],
                        ["Échéance", "`echeance_levee`", "sûre (synonyme)"],
                        ["Levée", "`levee`", "sûre (libellé)"],
                        ["Levée le", "`date_levee`", "sûre (synonyme)"],
                        ["Commentaire", "`commentaire_levee`", "sûre (synonyme)"]],
                       ["trois réserves créées et rattachées à leur contrôle, désigné par le repère et la nature "
                        "(lignes %d à %d) ; contrôle inconnu (ligne %d) : refusée ;" % (
                            numero_cle(res, "GF-01 / raccord"), numero_cle(res, "PT-01 / fin de course"),
                            numero_cle(res, "CH-01 / freins")),
                        "levée sans date : date de levée vide, commentaire « %s » s'il manque (D183), sur une réserve "
                        "existante (ligne %d) et sur une nouvelle (ligne %d) ;" % (
                            COMMENTAIRE_LEVEE_REPRISE, numero_cle(res, "RA-01 / purgeur"),
                            numero_cle(res, "PT-01 / fin de course")),
                        "règles des réserves (L2) : date du contrôle vide ou future, échéance avant le contrôle, levée "
                        "datée sans commentaire, réserve déjà levée modifiée ; « non » dans Levée avec une date ; "
                        "gravité hors liste ; doublon écrit en majuscules."]),
        """## Fichiers piégés (CS89 : message clair, rien de lu ni d'écrit, l'onglet ne se bloque pas)

| Fichier | Contenu | Attendu |
| --- | --- | --- |
| `trop_de_lignes.csv` | UTF-8 BOM « ; » : 1 ligne d'en-tête + **20 001** lignes de données = 20 002 lignes non vides | `Import.ErreurImport` « fichier trop grand » (plafond : 20 000 lignes de données + 1 ligne d'en-tête, soit 20 001 lignes non vides au plus) ; rien n'est lu |
| `limite_de_lignes.csv` | même forme : 1 ligne d'en-tête + **20 000** lignes de données = 20 001 lignes | **accepté** (pile au plafond) : 20 000 lignes de données lues (type `articles` : référence, désignation, qté stock) |
| `chiffre.xlsx` | conteneur OLE/CFB (signature `D0 CF 11 E0 A1 B1 1A E1`) avec les flux `EncryptionInfo` (chiffrement agile 4.4, descripteur XML aux valeurs factices, dans le mini-flux) et `EncryptedPackage` (6 024 octets pseudo-aléatoires) : la forme d'un classeur Excel protégé par mot de passe. Contenu factice : rien n'est vraiment chiffré ; pas de stockage `\\x06DataSpaces` | `Import.ErreurImport` « fichier protégé par un mot de passe » (SheetJS 0.20.3 lève « File is password-protected ») |
| `vide.csv` | 0 octet | `Import.ErreurImport` « fichier vide » |
| `lignes_vides.csv` | BOM UTF-8 puis seulement des séparateurs et des lignes vides | `Import.ErreurImport` « aucune ligne non vide » |
| `sans_entete.csv` | 5 lignes de nombres seulement (« ; », virgules décimales) | aucune ligne d'en-tête reconnue (`Import.ligneEntete` ne trouve aucune ligne de textes) → message clair, rien d'importé |
| `cellules_repetees.ods` | « bombe » : une ligne d'en-tête, puis une ligne dont **une cellule non vide est répétée 1 000 000 de fois** (`table:number-columns-repeated="1000000"`) ; archive de moins de 2 Ko | `Import.ErreurImport` « fichier trop grand » (plus de 200 colonnes), sans développer le million de cellules |

À ne pas confondre : `equipements.ods` contient aussi des cellules et des lignes répétées, mais **vides** (comme
LibreOffice les écrit) ; il doit se lire normalement (%(nb)d lignes).

## Choix retenus là où le contrat (§18) se tait — à respecter par T80 à T86

1. Une **clé naturelle vide** refuse la ligne, même quand le champ n'est pas obligatoire dans le schéma
   (fournisseur sans nom, compteur sans équipement, gamme sans libellé).
2. **Stock initial** : « 0 » crée un mouvement « inventaire » de 0 ; une cellule vide n'en crée aucun (ni pour un
   article nouveau, ni pour un article existant).
3. **Gammes** : les lignes d'une même gamme (même équipement + même libellé) sont ses opérations, dans l'ordre du
   fichier ; ce n'est pas un doublon. Si l'équipement est introuvable, toutes les lignes de la gamme sont refusées.
4. **Localisation par chemin** : libellés comparés tels quels, niveau par niveau ; séparateurs « > », « / » ou
   « \\ » ; seuls les niveaux manquants sont créés (type déduit du niveau : site, atelier, ligne), une seule fois.
5. **Technicien** (habilitations, historique) : « Prénom Nom » ou « Nom Prénom », casse ignorée
   (« GARNIER Thomas »).
6. **Historique** : équivalences de type ci-dessus ; codes par code ou par libellé, casse et accents ignorés
   (`Import.comparable`), seulement dans la famille de la colonne ; titre absent = les 80 premiers caractères du
   compte rendu du fichier (sans la ligne « Ancien n° » ; ici la coupe tombe en fin de mot, une coupe au dernier
   mot entier donnerait le même titre) ; un doublon supposé se cherche aussi parmi les lignes précédentes du même
   fichier ; la ligne `ot_temps` prend le technicien de l'OT et la date de fin (jour), et n'existe pas sans temps.
7. Les fichiers évitent exprès les cas que le contrat laisse ouverts (décimal « 38,00 » face à « 38 » en base,
   opérations d'une gamme existante, stock d'un article existant, temps passé sans technicien, équipement parent
   défini **plus bas** que son enfant) : ils ne fixent rien à leur sujet.

## Ce que SheetJS 0.20.3 fait de ces fichiers (relevé à la génération, utile à la lecture T81)

- `equipements.xlsx` et `equipements.xls` : dates rendues en nombres (numéros de série, format `dd/mm/yyyy`
  sur la cellule) ; feuilles « Parc » (`!ref` A1:I25) et « Notes » (A1:A2).
- `equipements.ods` : les dates arrivent en objets `Date` **même sans `cellDates`**, à minuit **heure locale**
  (en France : 22 h ou 23 h UTC la veille) ; la lecture doit les rendre en `AAAA-MM-JJ` avec la date locale,
  jamais par `toISOString()`. Les cellules et lignes vides répétées ne gonflent pas `!ref` (A1:I25).
- `cellules_repetees.ods` : SheetJS **développe** la ligne répétée (environ 1 000 000 de cellules créées, environ
  2 s dans Chromium) et rend pourtant `!ref` = A1:B2 : le plafond de 200 colonnes ne se voit ni dans `!ref` ni
  par `sheetRows`. La lecture doit repérer les `table:number-columns-repeated` non vides dans `content.xml`
  **avant** d'appeler SheetJS (ou refuser autrement), pour que l'onglet ne se bloque pas.
- `chiffre.xlsx` : `XLSX.read` lève « File is password-protected » ; `XLSX.CFB.read` y voit `EncryptionInfo`
  et `EncryptedPackage`.

## Enchaînement sur une base vide (recette T86)

Les attentes chiffrées ci-dessus valent pour la **démo**. Pour reprendre un atelier sur une base **vide**, importer
dans cet ordre : `codes.csv`, `techniciens.tsv`, `fournisseurs.tsv`, `equipements.xlsx`, `articles.csv`,
`habilitations.csv`, `compteurs.csv`, `controles.csv`, `gammes.xlsx`, `historique.csv`. La liste du parc contient
toutes les machines de la démo citées par les autres fichiers (avec leurs chemins de localisation complets), les
techniciens et les codes de la démo sont dans leurs fichiers : sur une base vide, les références se résolvent alors
par les fiches créées plus tôt, sauf les pièges voulus (« XX-99 », « Pierre Martel », « Paul Dumas », lignes en
erreur). `garanties.csv`, `contrats.csv` et `reserves.csv` (2.2) ne font pas partie de cette reprise : leurs attentes
valent pour la démo seulement (ils citent des équipements que la liste du parc ne contient pas). Différences attendues avec la démo : tout ce qui était « identique » ou « mis à jour » est **créé** ;
« 007 » existe après la liste du parc (son compteur, sa gamme et l'habilitation d'Inès Chabert après
`techniciens.tsv` deviennent des créations) ; la ligne %(l4601)d de l'historique n'a plus d'OT existant en face
(elle est créée) ; « CP-01.PUR » trouve sa machine mère CP-01 plus haut dans le fichier. Le calcul Python
indépendant de T86 refait les comptes.
""" % {"nb": len(eq.grille()), "l4601": numero_historique(his, "4601")},
    ]
    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Programme principal
# ---------------------------------------------------------------------------

def generer(sortie, avec_xls=True, dossier_demo=DOSSIER_DEMO):
    """Écrit tous les fichiers d'essai dans sortie ; rend {nom: octets}."""
    demo = Demo(dossier_demo)
    tableaux = {}
    # Chaque fichier est importé seul sur la démo : ses identifiants partent du plus grand numéro de la démo.
    for nom, construire in (("equipements", equipements), ("articles", articles), ("fournisseurs", fournisseurs),
                            ("techniciens", techniciens), ("habilitations", habilitations), ("codes", codes),
                            ("compteurs", compteurs), ("controles", controles), ("gammes", gammes),
                            ("historique", historique), ("garanties", garanties), ("contrats", contrats),
                            ("reserves", reserves)):
        tableaux[nom] = construire(demo, Identifiants(demo))

    eq = tableaux["equipements"]
    feuilles_parc = [("Parc", eq.grille()), ("Notes", NOTES_PARC)]
    fichiers = {
        "equipements.xlsx": ecrire_xlsx(feuilles_parc),
        "equipements.ods": ecrire_ods(feuilles_parc),
        "articles.csv": csv_tableau(tableaux["articles"], ";", "cp1252"),
        "fournisseurs.tsv": csv_tableau(tableaux["fournisseurs"], "\t", "utf-8"),
        "techniciens.tsv": csv_tableau(tableaux["techniciens"], "\t", "utf-8"),
        "habilitations.csv": csv_tableau(tableaux["habilitations"], ";", "utf-8", bom=True),
        "codes.csv": csv_tableau(tableaux["codes"], ";", "utf-8", fin=LF),
        "compteurs.csv": csv_tableau(tableaux["compteurs"], ";", "cp1252"),
        "controles.csv": csv_tableau(tableaux["controles"], ";", "utf-8", bom=True),
        "gammes.xlsx": ecrire_xlsx([("Gammes", tableaux["gammes"].grille())]),
        "historique.csv": csv_tableau(tableaux["historique"], ",", "utf-8"),
        "garanties.csv": csv_tableau(tableaux["garanties"], ";", "utf-8", bom=True),
        "contrats.csv": csv_tableau(tableaux["contrats"], ";", "utf-8", bom=True),
        "reserves.csv": csv_tableau(tableaux["reserves"], ";", "utf-8", bom=True),
        "trop_de_lignes.csv": lignes_essai(LIGNES_DONNEES_MAX + 1),
        "limite_de_lignes.csv": lignes_essai(LIGNES_DONNEES_MAX),
        "chiffre.xlsx": ecrire_chiffre(),
        "vide.csv": b"",
        "lignes_vides.csv": encoder(";;;" + CRLF + CRLF + ";;" + CRLF + CRLF, "utf-8", bom=True),
        "sans_entete.csv": encoder("".join(l + CRLF for l in ("12;4,5;2026;0", "7;1,25;2025;1", "3;0,5;2024;0",
                                                               "18;12;2026;1", "5;2,75;2023;0")), "utf-8"),
        "cellules_repetees.ods": ecrire_ods_bombe(),
        "LISEZMOI.md": lisezmoi(tableaux, demo).encode("utf-8"),
    }
    if avec_xls:
        fichiers["equipements.xls"] = ecrire_xls(feuilles_parc)
    sortie = Path(sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    for nom in sorted(fichiers):
        (sortie / nom).write_bytes(fichiers[nom])
    return fichiers


def main(arguments=None):
    analyseur = argparse.ArgumentParser(description="Écrit les fichiers d'essai de l'import (lot 5).")
    analyseur.add_argument("--sortie", default=str(SORTIE_DEFAUT), help="dossier de sortie (défaut : %(default)s)")
    analyseur.add_argument("--sans-xls", action="store_true", help="ne pas écrire equipements.xls (pas de navigateur)")
    options = analyseur.parse_args(arguments)
    fichiers = generer(options.sortie, avec_xls=not options.sans_xls)
    for nom in sorted(fichiers):
        print("%-24s %9d octets" % (nom, len(fichiers[nom])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
