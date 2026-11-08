"""Tests de js/formats.js (objet Formats) : registre des formats côté navigateur (chantier « socle de données », T183 ;
ARCHITECTURE.md §1, §5.6, §14.1, §20.2 ; format 4 de la 2.2, T382 ; décisions D167, D168 ; CS138, CS139, CS140,
CS169).

Chaque jeu de tests/fixtures/formats (tests/jeux_formats.py) est copié dans un dossier temporaire (règle du chantier :
jamais ailleurs), ses CSV sont lus en Python (BOM, « ; », guillemets, CRLF ; UTF-8, sinon Windows-1252), puis, dans
Chromium (page-vide.html en file://, avec js/lib/papaparse.min.js, js/schema.js, js/formats.js et js/donnees.js), la
base en mémoire est formée comme Prévo la garde (valeurs relues par Donnees.csv.relireValeur : apostrophe de
protection retirée). Couvre :
    - formatDuFichier de chaque table de chaque jeu : format attendu calculé d'après ce que chaque format ajoute
      (recopie de §14.1, §20.2 et du format 4 ci-dessous, indépendante de js/formats.js) ; variantes abîmées : 0
      (en-tête tronqué, colonne du format 1 manquante, fichier vide), 2 (ordres_travail sans astuce), null (table
      inconnue) ;
    - versionDeBase : f1 1, f2 2, f3 3 (f3-v2.1.0 et reserves-a-reprendre compris), plus-recent 5 ; même règle que
      Donnees.nombre (versionSchemaDe) ;
    - migrer(base, versionDeBase, 4) : aucune cellule d'origine perdue ni modifiée (champ à champ, colonnes inconnues
      comprises), colonnes nouvelles en fin avec leur défaut (après les colonnes inconnues, qui restent à leur
      place), tables créées vides, une ligne de journal par étape (f1 3, f2 2, f3 1) ; rejouée (versionDeBase relu) :
      aucun changement, journal vide ; rejouée depuis le format d'origine : même base (étapes idempotentes) ;
      plus-recent : rien ne change ;
    - ETAPES : chaîne sans trou de 1 au format courant, descriptions qui citent ce que l'étape ajoute (celle du
      format 4 au mot près), appliquer pure (l'entrée n'est pas modifiée) et idempotente, cas fabriqués (colonnes
      inconnues, ligne qui a déjà la colonne, parametres absent, noms avec BOM et espaces, table du format 4 déjà
      là) ; texte du journal = marque relue par la suggestion S4 ;
    - colonnes et tables de chaque format, formatDuFichier sur des en-têtes fabriqués (jamais d'exception) ;
    - manifeste : empreintes SHA-256 égales à hashlib.sha256, noms triés, contexte (champs absents omis).
La reprise des observations en réserves (D183) n'est pas encore là (T386) : reserves_controle est créée vide.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_formats_js.py" -v
"""
import csv
import hashlib
import io
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from commun import NB_TABLES, RACINE, CasNavigateur, charger_scripts
from jeux_formats import JEUX, copier_jeu

SCRIPTS = ["js/lib/papaparse.min.js", "js/schema.js", "js/formats.js", "js/donnees.js"]
BOM = b"\xef\xbb\xbf"
CARACTERE_BOM = chr(0xFEFF)
FORMAT_COURANT = 4

# Ce que chaque format ajoute : recopie de ARCHITECTURE.md §14.1 (format 2), §20.2 (format 3) et de la note de
# conception du format 4 (2.2, §2.1 et §2.2), indépendante de js/formats.js et de js/schema.js (le test les compare).
COLONNES_AJOUTEES = {
    2: {"equipements": ["valeur_remplacement"], "demandes": ["symptome_code", "ot_origine_id"],
        "ordres_travail": ["anomalie_constatee"]},
    3: {"ordres_travail": ["astuce"]},
    4: {"equipements": ["cout_arret_h"], "ordres_travail": ["habilitation_requise"],
        "habilitations": ["recyclage_mois", "justificatif", "catalogue_id", "nature_source"],
        "controles_reglementaires": ["source_periodicite", "nature_source", "catalogue_id", "catalogue_relu_le"]},
}
TABLES_AJOUTEES = {2: [], 3: ["wiki_pages", "wiki_journal"], 4: ["reserves_controle", "garanties",
                                                                 "contrats_prestataires"]}
DEFAUTS_AJOUTES = {"valeur_remplacement": "", "symptome_code": "", "ot_origine_id": "", "anomalie_constatee": "0",
                   "astuce": "", "cout_arret_h": "", "habilitation_requise": "", "recyclage_mois": "",
                   "justificatif": "", "catalogue_id": "", "nature_source": "", "source_periodicite": "saisie",
                   "catalogue_relu_le": ""}
# Description de l'étape 3→4, au mot près (note de conception du format 4, §2.4 ; la même dans serveur.py).
DESCRIPTION_FORMAT_4 = (
    "Format 4 (version 2.2) : colonnes equipements.cout_arret_h, ordres_travail.habilitation_requise, "
    "habilitations.recyclage_mois, habilitations.justificatif, habilitations.catalogue_id, habilitations.nature_source, "
    "controles_reglementaires.source_periodicite (défaut saisie), controles_reglementaires.nature_source, "
    "controles_reglementaires.catalogue_id et controles_reglementaires.catalogue_relu_le en fin de table ; tables "
    "reserves_controle (observations reprises, une réserve par ligne, D183), garanties et contrats_prestataires "
    "(vides).")

# Format des fichiers de chaque jeu et format de la base (version_schema) ; les autres jeux : format 3 (2.0 et 2.1).
FORMAT_DES_JEUX = 3
FORMAT_DES_FICHIERS = {"f1": 1, "f2-v1.1.0": 2}
VERSION_DE_BASE = {"f1": 1, "f2-v1.1.0": 2, "plus-recent": 5}
# Fichiers dont le format n'est pas celui du jeu (variantes abîmées : description dans le variante.json du jeu).
FORMATS_PARTICULIERS = {
    ("entete-tronque", "ordres_travail"): 0,     # en-tête coupé dans temps_prevu_h : colonnes du format 1 manquantes
    ("colonnes-manquantes", "equipements"): 0,   # sans modele (format 1) ni valeur_remplacement
    ("vide", "equipements"): 0,                  # 0 octet : aucun en-tête
    ("melange", "ordres_travail"): 2,            # sans astuce, dans une base au format 3
    ("plus-recent", "pieces_v5"): None,          # table inconnue du schéma
}
LIGNES_DE_JOURNAL = {
    1: ["passage au format 2 du fichier", "passage au format 3 du fichier", "passage au format 4 du fichier"],
    2: ["passage au format 3 du fichier", "passage au format 4 du fichier"],
    3: ["passage au format 4 du fichier"],
}


def tables_ajoutees_apres(format):
    """Tables que les formats suivants (jusqu'au format courant) ajoutent."""
    return [table for f in range(format + 1, FORMAT_COURANT + 1) for table in TABLES_AJOUTEES[f]]

# Base en mémoire formée dans la page à partir des cellules lues en Python : { table: { entete, cellules } } →
# { tables: { table: { entete, lignes: [{ colonne: valeur }] } } }, valeurs relues comme Donnees.csv.analyser
# (relireValeur : apostrophe de protection retirée ; colonne inconnue traitée comme un texte). Une cellule au-delà
# de l'en-tête est ignorée, une cellule manquante vaut '' (comme à la lecture par Prévo).
SCRIPT_BASE = """
window.baseDesFichiers = function (fichiers) {
  const base = { tables: {} };
  for (const nomTable of Object.keys(fichiers)) {
    const fichier = fichiers[nomTable];
    const lignes = fichier.cellules.map(function (cellules) {
      const ligne = {};
      fichier.entete.forEach(function (colonne, index) {
        const champ = Schema.champ(nomTable, colonne) || { type: 'texte' };
        ligne[colonne] = Donnees.csv.relireValeur(champ, index < cellules.length ? cellules[index] : '');
      });
      return ligne;
    });
    base.tables[nomTable] = { entete: fichier.entete.slice(), lignes: lignes };
  }
  return base;
};
"""


def decoder(octets):
    """Octets d'un CSV → texte : BOM retiré ; UTF-8, sinon Windows-1252 (comme Donnees.csv.decoder)."""
    if octets.startswith(BOM):
        octets = octets[len(BOM):]
    try:
        return octets.decode("utf-8")
    except UnicodeDecodeError:
        return octets.decode("cp1252")


def lire_csv(octets):
    """{ entete, cellules } d'un CSV « ; » (guillemets RFC 4180, CRLF, sauts de ligne dans les cellules) ; les
    lignes vides ou faites d'espaces sont sautées (comme skipEmptyLines: 'greedy' de Donnees)."""
    texte = decoder(octets)
    if texte.strip() == "":
        return {"entete": [], "cellules": []}
    enregistrements = [ligne for ligne in csv.reader(io.StringIO(texte, newline=""), delimiter=";", quotechar='"')
                       if "".join(ligne).strip() != ""]
    return {"entete": enregistrements[0], "cellules": enregistrements[1:]}


def format_attendu(table, format_des_fichiers):
    """Plus grand format N (jusqu'au format courant) dont l'en-tête est celui d'un fichier écrit au format donné :
    N avance tant que le format suivant n'ajoute rien à la table."""
    attendu = min(format_des_fichiers, FORMAT_COURANT)
    for format in range(attendu + 1, FORMAT_COURANT + 1):
        if table in COLONNES_AJOUTEES.get(format, {}) or table in TABLES_AJOUTEES.get(format, []):
            break
        attendu = format
    return attendu


class TestFormats(CasNavigateur):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        dossier = Path(tempfile.mkdtemp(prefix="prevo-formats-"))
        cls.addClassCleanup(shutil.rmtree, str(dossier), True)
        cls.octets = {}          # jeu -> { chemin relatif : octets }
        cls.fichiers = {}        # jeu -> { table : { entete, cellules } }
        for jeu in JEUX:
            copie = copier_jeu(jeu, dossier / jeu)
            cls.octets[jeu] = {chemin.relative_to(copie).as_posix(): chemin.read_bytes()
                               for chemin in sorted(copie.rglob("*")) if chemin.is_file()}
            cls.fichiers[jeu] = {chemin[:-len(".csv")]: lire_csv(octets)
                                 for chemin, octets in cls.octets[jeu].items()
                                 if chemin.endswith(".csv") and "/" not in chemin}

    def setUp(self):
        super().setUp()
        charger_scripts(self.page, SCRIPTS)
        self.page.add_script_tag(content=SCRIPT_BASE)

    def evaluer(self, script, argument=None):
        return self.page.evaluate(script, argument)

    def schema_courant(self):
        """{ table : { colonnes : [...], defauts : { colonne : défaut } } } du schéma (format courant)."""
        return self.evaluer("""() => {
          const resultat = {};
          for (const nom of Schema.nomsTables()) {
            const champs = Schema.table(nom).champs;
            resultat[nom] = { colonnes: champs.map((c) => c.nom),
              defauts: Object.fromEntries(champs.map((c) => [c.nom, c.defaut === undefined ? '' : c.defaut])) };
          }
          return resultat;
        }""")

    # -----------------------------------------------------------------------------------------------------------
    # Colonnes et tables de chaque format
    # -----------------------------------------------------------------------------------------------------------

    def test_courant_egal_a_schema_version(self):
        self.assertEqual(self.evaluer("() => [Formats.courant, Schema.version]"), [FORMAT_COURANT, FORMAT_COURANT])

    def test_colonnes_et_tables_de_chaque_format(self):
        resultat = self.evaluer("""() => {
          const parFormat = {};
          for (let format = 1; format <= Formats.courant; format += 1) {
            parFormat[format] = { tables: Formats.tables(format), colonnes: {} };
            for (const nom of Schema.nomsTables()) { parFormat[format].colonnes[nom] = Formats.colonnes(nom, format); }
          }
          const omis = {};
          for (const nom of Schema.nomsTables()) { omis[nom] = Formats.colonnes(nom); }
          return { parFormat, omis, tablesOmis: Formats.tables(), nomsTables: Schema.nomsTables(),
            inconnue: Formats.colonnes('pieces_v4', 3), wikiAvant: Formats.colonnes('wiki_pages', 2) };
        }""")
        schema = self.schema_courant()
        noms = resultat["nomsTables"]
        self.assertEqual(sorted(resultat["parFormat"], key=int), [str(f) for f in range(1, FORMAT_COURANT + 1)])
        tables_du_brief = [nom for nom in noms if nom not in tables_ajoutees_apres(1)]
        self.assertEqual(len(tables_du_brief), 22)
        self.assertEqual(len(noms), 22 + len(tables_ajoutees_apres(1)))          # 27 au format 4
        for format in range(1, FORMAT_COURANT + 1):
            # Tables d'un format : celles du schéma, dans son ordre, moins celles des formats suivants
            self.assertEqual(resultat["parFormat"][str(format)]["tables"],
                             [nom for nom in noms if nom not in tables_ajoutees_apres(format)], format)
        self.assertEqual(resultat["parFormat"]["2"]["tables"], tables_du_brief)
        self.assertEqual(resultat["parFormat"]["3"]["tables"], tables_du_brief + TABLES_AJOUTEES[3])
        self.assertEqual(noms[-3:], TABLES_AJOUTEES[4])          # après wiki_journal
        self.assertEqual(resultat["parFormat"][str(FORMAT_COURANT)]["tables"], noms)
        self.assertEqual(resultat["tablesOmis"], noms)
        self.assertEqual(resultat["inconnue"], [])
        self.assertEqual(resultat["wikiAvant"], [])
        for nom in noms:
            with self.subTest(table=nom):
                colonnes = {int(f): resultat["parFormat"][f]["colonnes"][nom] for f in resultat["parFormat"]}
                # Format courant = tous les champs du schéma, dans son ordre ; format omis = format courant
                self.assertEqual(colonnes[FORMAT_COURANT], schema[nom]["colonnes"])
                self.assertEqual(resultat["omis"][nom], schema[nom]["colonnes"])
                for format in range(2, FORMAT_COURANT + 1):
                    if nom in TABLES_AJOUTEES[format]:
                        self.assertEqual(colonnes[format - 1], [])
                        continue
                    # Le format N = le format N-1 suivi exactement des colonnes que N ajoute (en fin de table)
                    self.assertEqual(colonnes[format],
                                     colonnes[format - 1] + COLONNES_AJOUTEES[format].get(nom, []))
        # Valeurs par défaut des colonnes ajoutées (celles des tables nouvelles : voir test_schema.py)
        for format, tables in COLONNES_AJOUTEES.items():
            for table, ajoutees in tables.items():
                for colonne in ajoutees:
                    self.assertEqual(schema[table]["defauts"][colonne], DEFAUTS_AJOUTES[colonne], (table, colonne))

    # -----------------------------------------------------------------------------------------------------------
    # formatDuFichier
    # -----------------------------------------------------------------------------------------------------------

    def test_format_de_chaque_fichier_de_chaque_jeu(self):
        resultats = self.evaluer("""(jeux) => {
          const formats = {};
          for (const jeu of Object.keys(jeux)) {
            formats[jeu] = {};
            for (const table of Object.keys(jeux[jeu])) {
              formats[jeu][table] = Formats.formatDuFichier(table, jeux[jeu][table].entete);
            }
          }
          return formats;
        }""", {jeu: {t: {"entete": f["entete"]} for t, f in fichiers.items()} for jeu, fichiers in self.fichiers.items()})
        vus = set()
        for jeu in JEUX:
            for table in sorted(self.fichiers[jeu]):
                with self.subTest(jeu=jeu, table=table):
                    if (jeu, table) in FORMATS_PARTICULIERS:
                        attendu = FORMATS_PARTICULIERS[(jeu, table)]
                        vus.add((jeu, table))
                    else:
                        attendu = format_attendu(table, FORMAT_DES_FICHIERS.get(jeu, FORMAT_DES_JEUX))
                    self.assertEqual(resultats[jeu][table], attendu)
        self.assertEqual(vus, set(FORMATS_PARTICULIERS), "cas particuliers absents des jeux")
        # Les tables qui distinguent les formats : f1 → 1, f2 → 2, f3 → 3 ; une table que les formats suivants
        # n'ont pas changée est au format courant (wiki_pages, fournisseurs)
        self.assertEqual([resultats["f1"][t] for t in ("equipements", "demandes", "ordres_travail")], [1, 1, 1])
        self.assertEqual(resultats["f2-v1.1.0"]["ordres_travail"], 2)
        self.assertEqual(resultats["f3-v1.2.0"]["ordres_travail"], 3)
        self.assertEqual(resultats["f3-v1.2.0"]["wiki_pages"], 4)
        self.assertEqual(resultats["f3-v2.1.0"]["fournisseurs"], 4)
        self.assertEqual(resultats["plus-recent"]["ordres_travail"], 3)
        # Jeux de la 2.2 (T378) : au format 3 (colonne inconnue en fin de controles_reglementaires comprise)
        for jeu in ("f3-v2.1.0", "reserves-a-reprendre"):
            for table in ("equipements", "ordres_travail", "habilitations", "controles_reglementaires"):
                self.assertEqual(resultats[jeu][table], 3, (jeu, table))
        self.assertEqual(self.fichiers["reserves-a-reprendre"]["controles_reglementaires"]["entete"][-1],
                         "remarque_maison")

    def test_format_du_fichier_en_tetes_fabriques_sans_exception(self):
        resultat = self.evaluer("""(bom) => {
          const ot = (format) => Formats.colonnes('ordres_travail', format);
          const etrange = { toString() { throw new Error('illisible'); } };
          return {
            parFormat: [1, 2, 3, 4].map((format) => Formats.formatDuFichier('ordres_travail', ot(format))),
            desordre: Formats.formatDuFichier('ordres_travail', ot(4).slice().reverse()),
            bomEtEspaces: Formats.formatDuFichier('ordres_travail',
              [bom + 'id'].concat(ot(4).slice(1).map((nom) => '  ' + nom + ' \\t'))),
            enTrop: Formats.formatDuFichier('ordres_travail', ['avant'].concat(ot(2), ['apres', 'astuce'])),
            enTropFormat4: Formats.formatDuFichier('ordres_travail',
              ['avant'].concat(ot(3), ['apres', 'habilitation_requise'])),
            sansUneColonneDuFormat1: Formats.formatDuFichier('ordres_travail', ot(4).filter((n) => n !== 'titre')),
            casseDifferente: Formats.formatDuFichier('parametres', ['Cle', 'Valeur']),
            accentsEtSoulignes: Formats.formatDuFichier('ordres_travail',
              Formats.colonnes('ordres_travail', 4).map((n) => n === 'date_creation' ? 'Date Création' : n)),
            parametres: Formats.formatDuFichier('parametres', ['cle', 'valeur']),
            wikiComplet: Formats.formatDuFichier('wiki_pages', Formats.colonnes('wiki_pages', 3)),
            wikiIncomplet: Formats.formatDuFichier('wiki_pages', Formats.colonnes('wiki_pages', 3).slice(1)),
            wikiVide: Formats.formatDuFichier('wiki_journal', []),
            controlesSansUneColonneDuFormat4: Formats.formatDuFichier('controles_reglementaires',
              Formats.colonnes('controles_reglementaires', 4).filter((n) => n !== 'catalogue_relu_le')),
            reservesCompletes: Formats.formatDuFichier('reserves_controle', Formats.colonnes('reserves_controle')),
            reservesIncompletes: Formats.formatDuFichier('reserves_controle',
              Formats.colonnes('reserves_controle').slice(0, -1)),
            garantiesVides: Formats.formatDuFichier('garanties', []),
            contrats: Formats.formatDuFichier('contrats_prestataires', Formats.colonnes('contrats_prestataires', 4)),
            inconnue: Formats.formatDuFichier('pieces_v4', ['id']),
            tableAbsente: Formats.formatDuFichier(undefined, ['id']),
            etranges: [null, undefined, 'id;origine', 42, {}, [null, undefined, 3, {}], [etrange]]
              .map((entete) => Formats.formatDuFichier('ordres_travail', entete)),
          };
        }""", CARACTERE_BOM)
        self.assertEqual(resultat["parFormat"], [1, 2, 3, 4])
        self.assertEqual(resultat["desordre"], 4)
        self.assertEqual(resultat["bomEtEspaces"], 4)
        self.assertEqual(resultat["enTrop"], 3)
        self.assertEqual(resultat["enTropFormat4"], 4)
        self.assertEqual(resultat["sansUneColonneDuFormat1"], 0)
        # Casse, accents, espaces et soulignés ignorés, comme Donnees.cleEntete (relecture de T183).
        self.assertEqual(resultat["casseDifferente"], FORMAT_COURANT)
        self.assertEqual(resultat["parametres"], FORMAT_COURANT)
        self.assertEqual(resultat["accentsEtSoulignes"], 4)
        # wiki_pages n'a pas changé depuis le format 3 : son en-tête est aussi celui du format 4
        self.assertEqual(resultat["wikiComplet"], FORMAT_COURANT)
        self.assertEqual(resultat["wikiIncomplet"], 0)
        self.assertEqual(resultat["wikiVide"], 0)
        self.assertEqual(resultat["controlesSansUneColonneDuFormat4"], 3)
        self.assertEqual(resultat["reservesCompletes"], 4)
        self.assertEqual(resultat["reservesIncompletes"], 0)
        self.assertEqual(resultat["garantiesVides"], 0)
        self.assertEqual(resultat["contrats"], 4)
        self.assertIsNone(resultat["inconnue"])
        self.assertIsNone(resultat["tableAbsente"])
        self.assertEqual(resultat["etranges"], [0] * 7)

    # -----------------------------------------------------------------------------------------------------------
    # versionDeBase
    # -----------------------------------------------------------------------------------------------------------

    def test_version_de_base_de_chaque_jeu(self):
        resultats = self.evaluer("""(jeux) => {
          const versions = {};
          for (const jeu of Object.keys(jeux)) {
            const base = baseDesFichiers(jeux[jeu]);
            versions[jeu] = Formats.versionDeBase(base.tables.parametres ? base.tables.parametres.lignes : []);
          }
          return versions;
        }""", {jeu: {"parametres": f["parametres"]} for jeu, f in self.fichiers.items() if "parametres" in f})
        self.assertEqual(sorted(resultats), JEUX, "chaque jeu a un parametres.csv")
        for jeu in JEUX:
            with self.subTest(jeu=jeu):
                self.assertEqual(resultats[jeu], VERSION_DE_BASE.get(jeu, FORMAT_DES_JEUX))
        self.assertGreater(resultats["plus-recent"], self.evaluer("() => Formats.courant"))

    def test_version_de_base_meme_regle_que_donnees(self):
        resultat = self.evaluer("""() => {
          const valeurs = ['3', ' 2 ', '2,0', '2.0', '4', '', '   ', 'abc', "'3", '0', '-1', '2,5', '1e3', 'v3', null,
            undefined, 3, 2.5, NaN];
          const regle = (valeur) => { const lu = Donnees.nombre(valeur); return lu === null ? 1 : lu; };
          const avecLaCle = (valeur) => [{ cle: 'delai_p1_h', valeur: '9' }, { cle: 'version_schema', valeur: valeur }];
          return {
            ecarts: valeurs.filter((v) => Formats.versionDeBase(avecLaCle(v)) !== regle(v)).map(String),
            exemples: ['2', ' 2 ', '2,0', "'3", 'abc', ''].map((v) => Formats.versionDeBase(avecLaCle(v))),
            sansLaCle: Formats.versionDeBase([{ cle: 'entreprise_nom', valeur: '3' }]),
            vide: Formats.versionDeBase([]),
            pasUnTableau: [null, undefined, 'version_schema;3', {}].map((v) => Formats.versionDeBase(v)),
            premiereLigne: Formats.versionDeBase([{ cle: 'version_schema', valeur: '2' },
              { cle: 'version_schema', valeur: '3' }]),
            lignesEtranges: Formats.versionDeBase([null, 3, { cle: 'version_schema', valeur: '2' }]),
          };
        }""")
        self.assertEqual(resultat["ecarts"], [])
        self.assertEqual(resultat["exemples"], [2, 2, 2, 1, 1, 1])
        self.assertEqual(resultat["sansLaCle"], 1)
        self.assertEqual(resultat["vide"], 1)
        self.assertEqual(resultat["pasUnTableau"], [1, 1, 1, 1])
        self.assertEqual(resultat["premiereLigne"], 2)   # comme Donnees.parametre : la première ligne de la clé
        self.assertEqual(resultat["lignesEtranges"], 2)

    # -----------------------------------------------------------------------------------------------------------
    # migrer sur chaque jeu : sans perte, une ligne de journal par étape, rejouée sans changement
    # -----------------------------------------------------------------------------------------------------------

    def migrer_jeu(self, jeu):
        return self.evaluer("""(fichiers) => {
          const base = baseDesFichiers(fichiers);
          const avant = JSON.stringify(base);
          const parametres = (b) => (b.tables.parametres ? b.tables.parametres.lignes : []);
          const de = Formats.versionDeBase(parametres(base));
          const premier = Formats.migrer(base, de, Formats.courant);
          const deRejoue = Formats.versionDeBase(parametres(premier.base));
          const rejoue = Formats.migrer(premier.base, deRejoue, Formats.courant);
          const depuisOrigine = Formats.migrer(premier.base, de, Formats.courant);
          const formats = {};
          for (const table of Object.keys(premier.base.tables)) {
            formats[table] = Formats.formatDuFichier(table, premier.base.tables[table].entete);
          }
          return { base, de, premier, deRejoue, rejoue, depuisOrigine, formats,
            entreeIntacte: JSON.stringify(base) === avant, memeObjetSiRien: premier.base === base };
        }""", self.fichiers[jeu])

    def ecarts_de_cellules(self, avant, apres):
        """Cellules d'origine perdues ou modifiées (sauf parametres.version_schema, que la migration pose)."""
        ecarts = []
        for table, contenu in avant["tables"].items():
            if table not in apres["tables"]:
                ecarts.append("%s : table perdue" % table)
                continue
            lignes_apres = apres["tables"][table]["lignes"]
            if len(lignes_apres) != len(contenu["lignes"]):
                ecarts.append("%s : %d lignes au lieu de %d" % (table, len(lignes_apres), len(contenu["lignes"])))
            for numero, (ligne, ligne_apres) in enumerate(zip(contenu["lignes"], lignes_apres), start=1):
                for colonne, valeur in ligne.items():
                    if table == "parametres" and colonne == "valeur" and ligne.get("cle") == "version_schema":
                        continue
                    if ligne_apres.get(colonne) != valeur:
                        ecarts.append("%s ligne %d, %s : %r devenu %r" % (table, numero, colonne, valeur,
                                                                          ligne_apres.get(colonne)))
        return ecarts

    def test_migration_de_chaque_jeu_sans_perte(self):
        schema = self.schema_courant()
        for jeu in JEUX:
            with self.subTest(jeu=jeu):
                r = self.migrer_jeu(jeu)
                avant, apres = r["base"], r["premier"]["base"]
                de = VERSION_DE_BASE.get(jeu, FORMAT_DES_JEUX)
                self.assertEqual(r["de"], de)
                self.assertTrue(r["entreeIntacte"], "migrer a modifié la base reçue")
                self.assertEqual(r["premier"]["journal"], LIGNES_DE_JOURNAL.get(de, []))
                self.assertEqual([(e["de"], e["vers"]) for e in r["premier"]["etapes"]],
                                 [(n - 1, n) for n in range(de + 1, FORMAT_COURANT + 1)])
                self.assertEqual(self.ecarts_de_cellules(avant, apres), [])
                if de >= FORMAT_COURANT:
                    # Déjà au format courant (ou plus récent) : base rendue telle quelle
                    self.assertTrue(r["memeObjetSiRien"])
                    self.assertEqual(apres, avant)
                    continue
                # Colonnes d'origine à leur place (inconnues comprises), colonnes nouvelles en fin, après elles,
                # avec leur défaut
                for table, contenu in apres["tables"].items():
                    with self.subTest(jeu=jeu, table=table):
                        if table not in avant["tables"]:
                            self.assertEqual(contenu, {"entete": schema[table]["colonnes"], "lignes": []})
                            continue
                        entete_avant = avant["tables"][table]["entete"]
                        nouvelles = [c for c in schema[table]["colonnes"] if c not in entete_avant]
                        self.assertEqual(contenu["entete"], entete_avant + nouvelles)
                        for ligne in contenu["lignes"]:
                            self.assertEqual({c: ligne[c] for c in nouvelles},
                                             {c: schema[table]["defauts"][c] for c in nouvelles})
                        self.assertEqual(r["formats"][table], FORMAT_COURANT)
                self.assertEqual(sorted(apres["tables"]), sorted(schema))
                # Les tables des formats suivants sont créées (vides) ; celles du jeu sont gardées
                for table in tables_ajoutees_apres(de):
                    self.assertNotIn(table, avant["tables"])
                    self.assertIn(table, apres["tables"])
                self.assertEqual([l["valeur"] for l in apres["tables"]["parametres"]["lignes"]
                                  if l["cle"] == "version_schema"], [str(FORMAT_COURANT)])
                # Rejouée d'après la version relue : aucun changement, journal vide
                self.assertEqual(r["deRejoue"], FORMAT_COURANT)
                self.assertEqual(r["rejoue"]["journal"], [])
                self.assertEqual(r["rejoue"]["etapes"], [])
                self.assertEqual(r["rejoue"]["base"], apres)
                # Rejouée depuis le format d'origine : mêmes étapes, même base (chaque étape est idempotente)
                self.assertEqual(r["depuisOrigine"]["base"], apres)
                self.assertEqual(r["depuisOrigine"]["journal"], r["premier"]["journal"])

    def test_migration_f1_et_f2_detail(self):
        r1 = self.migrer_jeu("f1")
        apres = r1["premier"]["base"]["tables"]
        self.assertEqual(sorted(r1["base"]["tables"]), ["demandes", "equipements", "ordres_travail", "parametres"])
        self.assertEqual(len(apres), NB_TABLES)
        self.assertEqual(apres["ordres_travail"]["entete"][-3:], ["anomalie_constatee", "astuce", "habilitation_requise"])
        self.assertEqual(apres["demandes"]["entete"][-2:], ["symptome_code", "ot_origine_id"])
        self.assertEqual(apres["equipements"]["entete"][-2:], ["valeur_remplacement", "cout_arret_h"])
        self.assertTrue(all(l["anomalie_constatee"] == "0" and l["astuce"] == "" and l["habilitation_requise"] == ""
                            for l in apres["ordres_travail"]["lignes"]))
        self.assertEqual(len(apres["ordres_travail"]["lignes"]), 12)
        r2 = self.migrer_jeu("f2-v1.1.0")
        avant2, apres2 = r2["base"]["tables"], r2["premier"]["base"]["tables"]
        self.assertEqual(len(avant2), 22)
        self.assertEqual(sorted(set(apres2) - set(avant2)), sorted(tables_ajoutees_apres(2)))
        self.assertEqual(apres2["ordres_travail"]["entete"],
                         avant2["ordres_travail"]["entete"] + ["astuce", "habilitation_requise"])
        for table in avant2:
            self.assertEqual(apres2[table]["entete"],
                             avant2[table]["entete"] + COLONNES_AJOUTEES[3].get(table, [])
                             + COLONNES_AJOUTEES[4].get(table, []), table)

    def test_migration_f3_au_format_4_detail(self):
        """Bases 2.1.0 (f3-v2.1.0 et sa variante reserves-a-reprendre) : une étape, 3→4 ; seules equipements,
        ordres_travail, habilitations et controles_reglementaires changent (colonnes en fin, source_periodicite =
        saisie, les autres vides) ; les trois tables du format 4 sont créées vides (reprise des réserves : T386) ;
        la colonne inconnue remarque_maison reste à sa place, AVANT les colonnes du format 4 (règle de 2→3)."""
        for jeu in ("f3-v2.1.0", "reserves-a-reprendre"):
            with self.subTest(jeu=jeu):
                r = self.migrer_jeu(jeu)
                avant, apres = r["base"]["tables"], r["premier"]["base"]["tables"]
                self.assertEqual(r["premier"]["journal"], ["passage au format 4 du fichier"])
                self.assertEqual(r["premier"]["etapes"], [{"de": 3, "vers": 4, "description": DESCRIPTION_FORMAT_4}])
                self.assertEqual(sorted(set(apres) - set(avant)), sorted(TABLES_AJOUTEES[4]))
                for table in TABLES_AJOUTEES[4]:
                    self.assertEqual(apres[table]["lignes"], [], table)
                for table in avant:
                    ajoutees = COLONNES_AJOUTEES[4].get(table, [])
                    if table == "parametres" or ajoutees:
                        continue
                    self.assertEqual(apres[table], avant[table], "%s : réécrite sans colonne nouvelle" % table)
                for table, ajoutees in COLONNES_AJOUTEES[4].items():
                    self.assertEqual(apres[table]["entete"], avant[table]["entete"] + ajoutees, table)
                    self.assertTrue(avant[table]["lignes"], "%s : aucune ligne dans le jeu" % table)
                    for ligne_avant, ligne in zip(avant[table]["lignes"], apres[table]["lignes"]):
                        self.assertEqual(ligne, dict(ligne_avant, **{c: DEFAUTS_AJOUTES[c] for c in ajoutees}))
        r = self.migrer_jeu("reserves-a-reprendre")
        controles = r["premier"]["base"]["tables"]["controles_reglementaires"]
        self.assertEqual(controles["entete"][-6:], ["observations_levees", "remarque_maison", "source_periodicite",
                                                    "nature_source", "catalogue_id", "catalogue_relu_le"])
        self.assertEqual([l["remarque_maison"] for l in controles["lignes"]],
                         [l["remarque_maison"] for l in r["base"]["tables"]["controles_reglementaires"]["lignes"]])
        self.assertEqual({l["source_periodicite"] for l in controles["lignes"]}, {"saisie"})

    def test_plus_recent_rien_ne_change(self):
        r = self.evaluer("""(fichiers) => {
          const base = baseDesFichiers(fichiers);
          const avant = JSON.stringify(base);
          const de = Formats.versionDeBase(base.tables.parametres.lignes);
          const resultat = Formats.migrer(base, de, Formats.courant);
          return { de, courant: Formats.courant, journal: resultat.journal, etapes: resultat.etapes,
            meme: resultat.base === base, intacte: JSON.stringify(resultat.base) === avant,
            formatOt: Formats.formatDuFichier('ordres_travail', base.tables.ordres_travail.entete),
            formatPieces: Formats.formatDuFichier('pieces_v5', base.tables.pieces_v5.entete),
            derniere: base.tables.ordres_travail.entete.slice(-1)[0] };
        }""", self.fichiers["plus-recent"])
        self.assertEqual(r["de"], 5)
        self.assertGreater(r["de"], r["courant"])
        self.assertEqual(r["journal"], [])
        self.assertEqual(r["etapes"], [])
        self.assertTrue(r["meme"])
        self.assertTrue(r["intacte"])
        self.assertEqual(r["formatOt"], 3)
        self.assertIsNone(r["formatPieces"])
        self.assertEqual(r["derniere"], "nouvelle_colonne_v5")

    # -----------------------------------------------------------------------------------------------------------
    # ETAPES : registre, pureté, idempotence
    # -----------------------------------------------------------------------------------------------------------

    def test_etapes_chaine_sans_trou_et_descriptions(self):
        etapes = self.evaluer("""() => Formats.ETAPES.map((e) => ({ de: e.de, vers: e.vers, description: e.description,
          appliquer: typeof e.appliquer, figee: Object.isFrozen(e) }))""")
        self.assertEqual([(e["de"], e["vers"]) for e in etapes], [(1, 2), (2, 3), (3, 4)])
        self.assertEqual(etapes[-1]["vers"], FORMAT_COURANT)
        for etape in etapes:
            with self.subTest(etape=etape["vers"]):
                self.assertEqual(etape["appliquer"], "function")
                self.assertTrue(etape["figee"])
                for table, colonnes in COLONNES_AJOUTEES[etape["vers"]].items():
                    for colonne in colonnes:
                        self.assertIn("%s.%s" % (table, colonne), etape["description"])
                for table in TABLES_AJOUTEES[etape["vers"]]:
                    self.assertIn(table, etape["description"])
        self.assertEqual(etapes[2]["description"], DESCRIPTION_FORMAT_4)

    def test_ligne_de_journal_relue_par_la_suggestion_s4(self):
        texte = (RACINE / "js" / "modules" / "suggestions-regles.js").read_text(encoding="utf-8")
        marque = re.search(r"const MARQUE_FORMAT_2 = '([^']+)';", texte).group(1)
        journal = self.evaluer("""() => Formats.migrer({ tables: {} }, 1, 2).journal""")
        self.assertEqual(journal, [marque])
        self.assertEqual(marque, "passage au format 2 du fichier")

    def test_appliquer_pure_et_idempotente_sur_chaque_jeu(self):
        for jeu in JEUX:
            with self.subTest(jeu=jeu):
                r = self.evaluer("""(fichiers) => {
                  const base = baseDesFichiers(fichiers);
                  const avant = JSON.stringify(base);
                  return Formats.ETAPES.map((etape) => {
                    const une = etape.appliquer(base);
                    const intacte = JSON.stringify(base) === avant;
                    const deux = etape.appliquer(une);
                    // La nouvelle base ne partage ni lignes ni en-têtes avec l'entrée
                    const partage = Object.keys(base.tables).some((t) => une.tables[t] === base.tables[t]
                      || une.tables[t].entete === base.tables[t].entete
                      || une.tables[t].lignes.some((ligne, i) => ligne === base.tables[t].lignes[i]));
                    return { vers: etape.vers, intacte, partage, une, deux, nouvelObjet: une !== base };
                  });
                }""", self.fichiers[jeu])
                for etape in r:
                    self.assertTrue(etape["intacte"], "étape vers %d : entrée modifiée" % etape["vers"])
                    self.assertFalse(etape["partage"], "étape vers %d : lignes partagées" % etape["vers"])
                    self.assertTrue(etape["nouvelObjet"])
                    self.assertEqual(etape["deux"], etape["une"], "étape vers %d : pas idempotente" % etape["vers"])
                    versions = [l["valeur"] for l in etape["une"]["tables"]["parametres"]["lignes"]
                                if l["cle"] == "version_schema"]
                    self.assertEqual(versions[:1], [str(etape["vers"])])

    def test_appliquer_cas_fabriques(self):
        r = self.evaluer("""(bom) => {
          const base = { autre: 'gardé', tables: {
            equipements: { entete: ['id', 'colonne_maison', 'designation', 'actif'], lignes: [
              { id: 'EQ-0001', colonne_maison: 'm1', designation: 'Presse', actif: '0' },
              { id: 'EQ-0002', colonne_maison: '', designation: 'Tour', actif: '1', valeur_remplacement: '1200' },
            ] },
            ordres_travail: { entete: [bom + 'id', ' titre '], lignes: [{ [bom + 'id']: 'OT-1', ' titre ': 'T' }] },
            demandes: { entete: Formats.colonnes('demandes', 3).map((n) => ' ' + n + ' '), lignes: [] },
            pieces_v4: { entete: ['id', 'stock'], lignes: [{ id: 'P-1', stock: '3' }], note: 'table inconnue' },
          } };
          const avant = JSON.stringify(base);
          const deux = Formats.ETAPES[0].appliquer(base);
          const trois = Formats.ETAPES[1].appliquer(deux);
          const avecParametres = Formats.ETAPES[1].appliquer({ tables: {
            parametres: { entete: ['cle', 'valeur', 'note'], lignes: [{ cle: 'entreprise_nom', valeur: 'A', note: 'n' }] } } });
          const plusRecente = Formats.ETAPES[1].appliquer({ tables: { parametres: { entete: ['cle', 'valeur'],
            lignes: [{ cle: 'version_schema', valeur: '3' }, { cle: 'version_schema', valeur: '9' }] } } });
          return { intacte: JSON.stringify(base) === avant, deux, trois, avecParametres, plusRecente,
            rien: Formats.ETAPES[0].appliquer(null), indefinie: Formats.ETAPES[1].appliquer(undefined),
            colonnesOt: Formats.colonnes('ordres_travail', 2) };
        }""", CARACTERE_BOM)
        self.assertTrue(r["intacte"])
        deux, trois = r["deux"], r["trois"]
        self.assertEqual(deux["autre"], "gardé")
        equipements = deux["tables"]["equipements"]
        # Colonne inconnue gardée à sa place, colonnes manquantes en fin, dans l'ordre du schéma
        self.assertEqual(equipements["entete"][:4], ["id", "colonne_maison", "designation", "actif"])
        self.assertEqual(equipements["entete"][-1], "valeur_remplacement")
        self.assertIn("repere", equipements["entete"][4:])
        self.assertEqual(equipements["lignes"][0]["colonne_maison"], "m1")
        self.assertEqual(equipements["lignes"][0]["actif"], "0")           # valeur gardée, pas le défaut '1'
        self.assertEqual(equipements["lignes"][0]["criticite"], "B")        # défaut du schéma
        self.assertEqual(equipements["lignes"][0]["valeur_remplacement"], "")
        self.assertEqual(equipements["lignes"][1]["valeur_remplacement"], "1200")   # déjà là : jamais écrasée
        # Noms avec BOM ou espaces : reconnus, pas de colonne en double
        ordres = deux["tables"]["ordres_travail"]
        self.assertEqual(ordres["entete"][:2], [CARACTERE_BOM + "id", " titre "])
        self.assertNotIn("id", ordres["entete"])
        self.assertNotIn("titre", ordres["entete"])
        self.assertEqual(len(ordres["entete"]), len(r["colonnesOt"]))
        self.assertEqual(deux["tables"]["demandes"]["entete"], [" %s " % n for n in self.evaluer(
            "() => Formats.colonnes('demandes', 3)")])
        # Table inconnue gardée telle quelle ; parametres créé avec la version ; wiki seulement au format 3
        self.assertEqual(deux["tables"]["pieces_v4"], {"entete": ["id", "stock"], "lignes": [{"id": "P-1", "stock": "3"}],
                                                       "note": "table inconnue"})
        self.assertEqual(deux["tables"]["parametres"], {"entete": ["cle", "valeur"],
                                                        "lignes": [{"cle": "version_schema", "valeur": "2"}]})
        self.assertNotIn("wiki_pages", deux["tables"])
        self.assertEqual(trois["tables"]["parametres"]["lignes"], [{"cle": "version_schema", "valeur": "3"}])
        self.assertEqual(trois["tables"]["ordres_travail"]["entete"][-1], "astuce")
        self.assertEqual(trois["tables"]["wiki_journal"]["lignes"], [])
        self.assertEqual(r["avecParametres"]["tables"]["parametres"]["lignes"], [
            {"cle": "entreprise_nom", "valeur": "A", "note": "n"},
            {"cle": "version_schema", "valeur": "3", "note": ""}])
        # Clé en double : la première ligne porte la version (comme Donnees.parametre)
        self.assertEqual(r["plusRecente"]["tables"]["parametres"]["lignes"], [
            {"cle": "version_schema", "valeur": "3"}, {"cle": "version_schema", "valeur": "9"}])
        self.assertEqual(len(r["rien"]["tables"]), 22)
        self.assertEqual(len(r["indefinie"]["tables"]), 24)

    def test_etape_3_4_cas_fabriques(self):
        """Étape 3→4 générique : colonnes du format 4 en fin d'en-tête, après les colonnes inconnues (à leur place),
        défaut saisie ; valeur déjà là jamais écrasée ; table du format 4 déjà là gardée telle quelle (lignes
        comprises) ; tables absentes créées vides ; colonnes avec BOM ou espaces reconnues ; pure et idempotente."""
        r = self.evaluer("""() => {
          const colonnes3 = Formats.colonnes('controles_reglementaires', 3);
          const base = { tables: {
            controles_reglementaires: { entete: colonnes3.concat(['remarque_maison']), lignes: [
              Object.assign(Object.fromEntries(colonnes3.map((c) => [c, ''])), { id: 'CTR-0001', remarque_maison: 'r' }),
              Object.assign(Object.fromEntries(colonnes3.map((c) => [c, ''])),
                { id: 'CTR-0002', remarque_maison: '', source_periodicite: 'catalogue' }),
            ] },
            habilitations: { entete: ['id', 'note', 'intitule', ' Recyclage Mois '], lignes: [
              { id: 'HAB-0001', note: 'n', intitule: 'B1V', ' Recyclage Mois ': '36' }] },
            reserves_controle: { entete: ['id', 'controle_id', 'texte'], lignes: [
              { id: 'RES-00007', controle_id: 'CTR-0001', texte: 'garde-corps' }] },
            parametres: { entete: ['cle', 'valeur'], lignes: [{ cle: 'version_schema', valeur: '3' }] },
          } };
          const avant = JSON.stringify(base);
          const quatre = Formats.ETAPES[2].appliquer(base);
          return { intacte: JSON.stringify(base) === avant, quatre, rejouee: Formats.ETAPES[2].appliquer(quatre),
            rien: Formats.ETAPES[2].appliquer(null), schemaReserves: Formats.colonnes('reserves_controle') };
        }""")
        self.assertTrue(r["intacte"])
        quatre = r["quatre"]["tables"]
        self.assertEqual(r["rejouee"]["tables"], quatre)
        controles = quatre["controles_reglementaires"]
        self.assertEqual(controles["entete"][-5:], ["remarque_maison"] + COLONNES_AJOUTEES[4]["controles_reglementaires"])
        self.assertEqual([(l["remarque_maison"], l["source_periodicite"], l["nature_source"], l["catalogue_relu_le"])
                          for l in controles["lignes"]], [("r", "saisie", "", ""), ("", "catalogue", "", "")])
        # Colonne déjà là (nom avec espaces et majuscules) : reconnue, pas de doublon ; les autres en fin
        habilitations = quatre["habilitations"]
        self.assertEqual(habilitations["entete"], ["id", "note", "intitule", " Recyclage Mois ", "technicien_id",
                                                   "date_obtention", "date_echeance", "justificatif", "catalogue_id",
                                                   "nature_source"])
        self.assertEqual(habilitations["lignes"][0][" Recyclage Mois "], "36")
        self.assertNotIn("recyclage_mois", habilitations["lignes"][0])
        # Table du format 4 déjà là : lignes gardées, colonnes manquantes en fin (levee : défaut 0)
        reserves = quatre["reserves_controle"]
        self.assertEqual(reserves["entete"][:3], ["id", "controle_id", "texte"])
        self.assertEqual(sorted(reserves["entete"]), sorted(r["schemaReserves"]))
        self.assertEqual(reserves["lignes"][0]["texte"], "garde-corps")
        self.assertEqual(reserves["lignes"][0]["levee"], "0")
        self.assertEqual(len(reserves["lignes"]), 1)
        self.assertEqual(quatre["garanties"]["lignes"], [])
        self.assertEqual(quatre["contrats_prestataires"]["lignes"], [])
        self.assertEqual(quatre["parametres"]["lignes"], [{"cle": "version_schema", "valeur": "4"}])
        self.assertEqual(len(r["rien"]["tables"]), NB_TABLES)

    def test_migrer_etapes_choisies_et_erreurs(self):
        r = self.evaluer("""() => {
          const base = { tables: { ordres_travail: { entete: Formats.colonnes('ordres_travail', 1), lignes: [] } } };
          const versDeux = Formats.migrer(base, 1, 2);
          const erreur = (fonction) => { try { fonction(); return null; } catch (e) { return e.name + ' : ' + e.message; } };
          return {
            versDeux: { journal: versDeux.journal, entete: versDeux.base.tables.ordres_travail.entete.slice(-1),
              tables: Object.keys(versDeux.base.tables).length,
              version: versDeux.base.tables.parametres.lignes[0].valeur },
            depuisZero: Formats.migrer(base, 0, Formats.courant).journal,
            depuisDemi: Formats.migrer(base, 2.5, Formats.courant).journal,
            versTrois: Formats.migrer(base, 1, 3).journal,
            egal: Formats.migrer(base, 2, 2).base === base,
            cibleTropGrande: erreur(() => Formats.migrer(base, 1, Formats.courant + 1)),
            cibleNulle: erreur(() => Formats.migrer(base, 0, 0)),
            cibleDecimale: erreur(() => Formats.migrer(base, 1, 2.5)),
            departIllisible: erreur(() => Formats.migrer(base, NaN, 3)),
            departTexte: erreur(() => Formats.migrer(base, '1', 3)),
          };
        }""")
        self.assertEqual(r["versDeux"], {"journal": ["passage au format 2 du fichier"], "entete": ["anomalie_constatee"],
                                         "tables": 22, "version": "2"})
        self.assertEqual(r["depuisZero"], LIGNES_DE_JOURNAL[1])
        self.assertEqual(r["depuisDemi"], LIGNES_DE_JOURNAL[2])
        self.assertEqual(r["versTrois"], LIGNES_DE_JOURNAL[1][:2])
        self.assertTrue(r["egal"])
        for cle in ("cibleTropGrande", "cibleNulle", "cibleDecimale"):
            self.assertRegex(r[cle] or "", r"^RangeError : Formats\.migrer : format cible inconnu", cle)
        for cle in ("departIllisible", "departTexte"):
            self.assertRegex(r[cle] or "", r"^TypeError : Formats\.migrer : format de départ illisible", cle)

    # -----------------------------------------------------------------------------------------------------------
    # manifeste
    # -----------------------------------------------------------------------------------------------------------

    def test_manifeste_empreintes_egales_a_hashlib(self):
        for jeu in ("f3-v2.0.0", "vide", "windows-1252"):
            with self.subTest(jeu=jeu):
                fichiers = self.octets[jeu]
                manifeste = self.evaluer("""async (fichiers) => Formats.manifeste(
                  Object.keys(fichiers).reverse().map((nom) => ({ nom, octets: new Uint8Array(fichiers[nom]) })),
                  { version_appli: '2.0.0', format: 3, date: '2026-11-04 08:30:00', motif: 'export', mode: 'dossier' })""",
                                         {nom: list(octets) for nom, octets in fichiers.items()})
                self.assertEqual(list(manifeste), ["application", "version_appli", "format", "date", "motif", "mode",
                                                   "fichiers"])
                self.assertEqual(manifeste["application"], "Prévo")
                self.assertEqual((manifeste["version_appli"], manifeste["format"], manifeste["date"], manifeste["motif"],
                                  manifeste["mode"]), ("2.0.0", 3, "2026-11-04 08:30:00", "export", "dossier"))
                attendu = [{"nom": nom, "octets": len(fichiers[nom]), "sha256": hashlib.sha256(fichiers[nom]).hexdigest()}
                           for nom in sorted(fichiers)]
                self.assertEqual(manifeste["fichiers"], attendu)
        self.assertIn("acces/comptes.json", [f["nom"] for f in self.evaluer(
            "async (noms) => (await Formats.manifeste(noms.map((nom) => ({ nom, octets: new Uint8Array(0) })))).fichiers",
            sorted(self.octets["f3-v2.0.0"]))])

    def test_manifeste_contexte_partiel_et_octets_varies(self):
        r = self.evaluer("""async () => {
          const texte = new TextEncoder().encode('xxabcxx');
          const partiel = await Formats.manifeste([{ nom: 'été.csv', octets: texte.subarray(2, 5) },
            { nom: 'documents/b.pdf', octets: texte.buffer }, { nom: 'Z.csv', octets: new Uint8Array(0) }],
            { format: 3, date: undefined, motif: null });
          const sansContexte = await Formats.manifeste([]);
          let refus = null;
          try { await Formats.manifeste([{ nom: 'x', octets: 'pas des octets' }]); } catch (e) { refus = e.name; }
          return { partiel, sansContexte, refus };
        }""")
        self.assertEqual(list(r["partiel"]), ["application", "format", "fichiers"])
        noms = ["été.csv", "documents/b.pdf", "Z.csv"]
        self.assertEqual([f["nom"] for f in r["partiel"]["fichiers"]], sorted(noms))
        par_nom = {f["nom"]: f for f in r["partiel"]["fichiers"]}
        self.assertEqual(par_nom["été.csv"], {"nom": "été.csv", "octets": 3, "sha256": hashlib.sha256(b"abc").hexdigest()})
        self.assertEqual(par_nom["documents/b.pdf"]["sha256"], hashlib.sha256(b"xxabcxx").hexdigest())
        self.assertEqual(par_nom["Z.csv"]["octets"], 0)
        self.assertEqual(r["sansContexte"], {"application": "Prévo", "fichiers": []})
        self.assertEqual(r["refus"], "TypeError")


if __name__ == "__main__":
    unittest.main()
