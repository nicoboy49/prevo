"""Tests du registre des formats côté serveur (serveur.py, section « Formats des données (miroir de js/formats.js,
T184) ») : cle_de_colonne, colonnes_du_format, tables_du_format, format_du_fichier, version_de_base, ETAPES_FORMAT,
migrer_tables (chantier « socle de données », T184 ; décisions D167, D168 ; ARCHITECTURE.md §5.6, §14.1, §20.2).

Chaque jeu de tests/fixtures/formats (tests/jeux_formats.py) est copié dans un dossier temporaire (règle du chantier :
jamais ailleurs). Côté serveur, une base est {table: {'entete', 'lignes': [{colonne: cellule}]}}, cellules lues par
lire_csv_tolerant (apostrophe de protection comprise) et réécrites par ecrire_tableau_csv.

1. TestRegistreServeur (Python seul, sans navigateur) : colonnes et tables de chaque format, cohérence des listes
   ajoutées avec COLONNES_PAR_TABLE et COLONNES_DES_FORMATS_SUIVANTS ; pour chaque jeu, format_du_fichier,
   version_de_base et migrer_tables : aucune cellule d'origine perdue ni modifiée (champ à champ), colonnes nouvelles
   en fin avec leur défaut, tables créées (wiki compris), journal (f1 2 lignes, f2 1, f3 0), idempotence, pureté
   (entrée inchangée), plus-recent (version 4) laissé intact par migrer_tables(base, 4, 3) ; cas fabriqués et
   erreurs.
2. TestConcordanceNavigateur (Chromium, page-vide.html en file://) : mêmes listes que Schema et Formats (colonnes,
   tables, défauts, étapes) ; mêmes résultats que Formats.formatDuFichier, Formats.versionDeBase, Formats.ETAPES et
   Donnees.csv.relireValeur / ecrireValeur sur des cas fabriqués ; pour chaque jeu, lecture + migration + écriture
   côté navigateur (Donnees.csv.analyser, Formats.migrer, Donnees.csv.serialiser) et côté serveur
   (lire_csv_tolerant, migrer_tables, ecrire_tableau_csv) → mêmes octets par table, mêmes formats, même journal.

Écarts PRÉEXISTANTS entre les deux lecteurs/écrivains CSV (pas entre Formats.migrer et migrer_tables, qui rendent les
mêmes en-têtes), documentés par des tests expectedFailure, et cernés chacun par un test qui passe (l'écart est
exactement celui décrit, rien d'autre) ; à trancher par l'orchestrateur :
    A. colonnes-en-trop : Donnees.csv.serialiser réécrit les colonnes inconnues en fin de fichier, après toutes les
       colonnes du schéma ; ecrire_tableau_csv garde l'en-tête tel quel (colonne_maison reste après designation).
    B. colonnes-manquantes, melange : Donnees.csv.analyser complète chaque ligne avec tous les champs du schéma (défaut)
       et serialiser écrit toujours toutes les colonnes du schéma ; le serveur lit et réécrit l'en-tête tel quel. Base
       déjà au format 3 : ni Formats.migrer ni migrer_tables n'ajoutent rien (modele, valeur_remplacement ou astuce
       manquent donc dans le fichier réécrit par le serveur, pas dans celui du navigateur).
    C. windows-1252 : Donnees.csv.analyser normalise les valeurs à la lecture (date_mes 12/03/2019 → 2019-03-12) ;
       lire_csv_tolerant garde les cellules brutes. Les deux lecteurs acceptent le fichier (Windows-1252).
Pour vide et entete-tronque : même format détecté des deux côtés (0), aucune exception (octets non comparés).

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_formats_serveur.py" -v
"""
import base64
import copy
import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from commun import RACINE, CasNavigateur, charger_scripts  # noqa: E402
from jeux_formats import JEUX, copier_jeu  # noqa: E402


def charger_serveur():
    specification = importlib.util.spec_from_file_location("serveur_prevo_formats_serveur", RACINE / "serveur.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


serveur = charger_serveur()

SCRIPTS = ["js/lib/papaparse.min.js", "js/schema.js", "js/formats.js", "js/donnees.js"]
FORMAT_COURANT = 3
CARACTERE_BOM = chr(0xFEFF)
INSECABLE, INSECABLE_FINE, CADRATIN, IDEOGRAPHIQUE = chr(0xA0), chr(0x202F), chr(0x2003), chr(0x3000)
ESPACE_NULLE, LIGNE_SUIVANTE, SEPARATEUR_DE_FICHIER = chr(0x200B), chr(0x85), chr(0x1C)

# Ce que chaque format ajoute : recopie de ARCHITECTURE.md §14.1 (format 2) et §20.2 (format 3), indépendante de
# serveur.py et de js/ (les tests les comparent).
COLONNES_AJOUTEES = {
    2: {"equipements": ["valeur_remplacement"], "demandes": ["symptome_code", "ot_origine_id"],
        "ordres_travail": ["anomalie_constatee"]},
    3: {"ordres_travail": ["astuce"]},
}
TABLES_AJOUTEES = {2: [], 3: ["wiki_pages", "wiki_journal"]}
DEFAUTS_AJOUTES = {"valeur_remplacement": "", "symptome_code": "", "ot_origine_id": "", "anomalie_constatee": "0",
                   "astuce": ""}
FORMAT_DES_FICHIERS = {"f1": 1, "f2-v1.1.0": 2}
VERSION_DE_BASE = {"f1": 1, "f2-v1.1.0": 2, "plus-recent": 4}
FORMATS_PARTICULIERS = {
    ("entete-tronque", "ordres_travail"): 0,     # en-tête coupé dans temps_prevu_h : colonnes du format 1 manquantes
    ("colonnes-manquantes", "equipements"): 0,   # sans modele (format 1) ni valeur_remplacement
    ("vide", "equipements"): 0,                  # 0 octet : aucun en-tête
    ("melange", "ordres_travail"): 2,            # sans astuce, dans une base au format 3
    ("plus-recent", "pieces_v4"): None,          # table inconnue du schéma
}
LIGNES_DE_JOURNAL = {
    1: ["passage au format 2 du fichier", "passage au format 3 du fichier"],
    2: ["passage au format 3 du fichier"],
}
# Concordance navigateur / serveur : jeux dont les octets doivent être identiques, table par table.
JEUX_CONCORDANTS = ("f1", "f2-v1.1.0", "f3-v1.2.0", "f3-v2.0.0", "sans-bom", "table-absente", "plus-recent")
# Écarts préexistants entre lecteurs/écrivains (docstring du module) : jeu → (table touchée, nature de l'écart).
ECARTS_DOCUMENTES = {
    "colonnes-en-trop": ("equipements", "colonnes"),      # A : colonnes inconnues réécrites en fin par serialiser
    "colonnes-manquantes": ("equipements", "colonnes"),   # B : colonnes du schéma toujours écrites par serialiser
    "melange": ("ordres_travail", "colonnes"),            # B
    "windows-1252": ("equipements", "valeurs"),           # C : dates normalisées par analyser
}
JEUX_ABIMES = {"vide": "equipements", "entete-tronque": "ordres_travail"}


def colonnes_attendues(table, format):
    """Colonnes de la table dans ce format, d'après COLONNES_AJOUTEES et COLONNES_PAR_TABLE (format courant)."""
    if any(table in TABLES_AJOUTEES[f] for f in range(format + 1, FORMAT_COURANT + 1)):
        return []
    retirees = {c for f in range(format + 1, FORMAT_COURANT + 1) for c in COLONNES_AJOUTEES[f].get(table, [])}
    return [c for c in serveur.COLONNES_PAR_TABLE[table] if c not in retirees]


def format_attendu(table, format_des_fichiers):
    """Plus grand format N dont l'en-tête est celui d'un fichier écrit au format donné (N avance tant que le format
    suivant n'ajoute rien à la table)."""
    attendu = min(format_des_fichiers, FORMAT_COURANT)
    for format in range(attendu + 1, FORMAT_COURANT + 1):
        if table in COLONNES_AJOUTEES.get(format, {}) or table in TABLES_AJOUTEES.get(format, []):
            break
        attendu = format
    return attendu


def fichiers_du_jeu(jeu, dossier):
    """{table: octets} des CSV du jeu (copié dans « dossier », jamais lu en place)."""
    copie = copier_jeu(jeu, Path(dossier) / jeu)
    return {chemin.stem: chemin.read_bytes() for chemin in sorted(copie.glob("*.csv"))}


def table_de_base(octets):
    """Table de la base du serveur lue par lire_csv_tolerant : cellule manquante → '', cellule au-delà de l'en-tête
    ignorée (comme Donnees.csv.analyser)."""
    entete, lignes = serveur.lire_csv_tolerant(octets)
    if len(set(entete)) != len(entete):
        raise AssertionError("nom de colonne en double dans un jeu : %r" % (entete,))
    return {"entete": list(entete),
            "lignes": [{nom: (ligne[i] if i < len(ligne) else "") for i, nom in enumerate(entete)} for ligne in lignes]}


def base_de_fichiers(fichiers):
    return {table: table_de_base(octets) for table, octets in fichiers.items()}


def octets_de_table(contenu):
    return serveur.ecrire_tableau_csv(contenu["entete"], [[ligne.get(nom, "") for nom in contenu["entete"]]
                                                          for ligne in contenu["lignes"]])


def lignes_de_parametres(base):
    return base["parametres"]["lignes"] if "parametres" in base else []


def chemin_serveur(fichiers):
    """Lecture (lire_csv_tolerant) + migrer_tables + écriture (ecrire_tableau_csv), comme le fera le serveur."""
    base = base_de_fichiers(fichiers)
    de = serveur.version_de_base(lignes_de_parametres(base))
    migree, journal, etapes = serveur.migrer_tables(base, de, FORMAT_COURANT)
    return {"formats": {table: serveur.format_du_fichier(table, contenu["entete"]) for table, contenu in base.items()},
            "de": de, "journal": journal, "etapes": [[e["de"], e["vers"]] for e in etapes],
            "entetes": {table: contenu["entete"] for table, contenu in migree.items()},
            "octets": {table: octets_de_table(contenu) for table, contenu in migree.items()}}


def ecarts_de_cellules(avant, apres):
    """Cellules d'origine perdues ou modifiées (sauf la valeur de parametres.version_schema, que l'étape pose)."""
    ecarts = []
    for table, contenu in avant.items():
        if table not in apres:
            ecarts.append("%s : table perdue" % table)
            continue
        lignes_apres = apres[table]["lignes"]
        if len(lignes_apres) < len(contenu["lignes"]):
            ecarts.append("%s : %d lignes au lieu de %d" % (table, len(lignes_apres), len(contenu["lignes"])))
        for numero, (ligne, ligne_apres) in enumerate(zip(contenu["lignes"], lignes_apres), start=1):
            for colonne, valeur in ligne.items():
                if table == "parametres" and colonne == "valeur" and ligne.get("cle") == "version_schema":
                    continue
                if colonne not in ligne_apres or ligne_apres[colonne] != valeur:
                    ecarts.append("%s ligne %d, %s : %r devenu %r" % (table, numero, colonne, valeur,
                                                                      ligne_apres.get(colonne)))
    return ecarts


class JeuxEnCopie:
    """Copie chaque jeu une fois par classe, dans un dossier temporaire supprimé à la fin."""

    @classmethod
    def copier_les_jeux(cls):
        dossier = tempfile.mkdtemp(prefix="prevo-formats-serveur-")
        cls.addClassCleanup(shutil.rmtree, dossier, True)
        cls.fichiers = {jeu: fichiers_du_jeu(jeu, dossier) for jeu in JEUX}


# ---------------------------------------------------------------------------------------------------------------
# 1. Python seul
# ---------------------------------------------------------------------------------------------------------------

class TestRegistreServeur(JeuxEnCopie, unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.copier_les_jeux()

    def base(self, jeu):
        return base_de_fichiers(self.fichiers[jeu])

    # -- Colonnes et tables de chaque format ------------------------------------------------------------------

    def test_colonnes_et_tables_de_chaque_format(self):
        self.assertEqual(serveur.VERSION_SCHEMA_CSV, FORMAT_COURANT)
        tables_du_brief = [t for t in serveur.TABLES if t not in TABLES_AJOUTEES[3]]
        self.assertEqual(len(tables_du_brief), 22)
        self.assertEqual(serveur.tables_du_format(1), tables_du_brief)
        self.assertEqual(serveur.tables_du_format(2), tables_du_brief)
        self.assertEqual(serveur.tables_du_format(3), list(serveur.TABLES))
        self.assertEqual(serveur.tables_du_format(), list(serveur.TABLES))
        for table in serveur.TABLES:
            with self.subTest(table=table):
                for format in (1, 2, 3):
                    self.assertEqual(serveur.colonnes_du_format(table, format), colonnes_attendues(table, format))
                self.assertEqual(serveur.colonnes_du_format(table), list(serveur.COLONNES_PAR_TABLE[table]))
        self.assertEqual(serveur.colonnes_du_format("pieces_v4", 3), [])
        self.assertEqual(serveur.colonnes_du_format("wiki_pages", 2), [])
        self.assertEqual(serveur.colonnes_du_format(None), [])
        self.assertEqual(serveur.colonnes_du_format(["equipements"]), [])

    def test_listes_ajoutees_coherentes_avec_le_serveur(self):
        # Les colonnes des formats suivants sont celles de COLONNES_DES_FORMATS_SUIVANTS (« Tester une sauvegarde »),
        # dans le même ordre, en fin de COLONNES_PAR_TABLE, et leur format est croissant dans la table.
        self.assertEqual({t: tuple(c) for t, c in serveur.PREMIER_FORMAT_DES_COLONNES.items()},
                         serveur.COLONNES_DES_FORMATS_SUIVANTS)
        for table, formats in serveur.PREMIER_FORMAT_DES_COLONNES.items():
            with self.subTest(table=table):
                self.assertEqual(list(serveur.COLONNES_PAR_TABLE[table][-len(formats):]), list(formats))
                self.assertEqual(list(formats.values()), sorted(formats.values()))
                self.assertTrue(all(1 < f <= FORMAT_COURANT for f in formats.values()))
        self.assertEqual(set(serveur.PREMIER_FORMAT_DES_TABLES), set(TABLES_AJOUTEES[3]))
        self.assertEqual(list(serveur.TABLES[-2:]), TABLES_AJOUTEES[3])
        for table, defauts in serveur.DEFAUTS_DES_CHAMPS.items():
            with self.subTest(table=table):
                self.assertTrue(set(defauts) <= set(serveur.COLONNES_PAR_TABLE[table]))
                self.assertTrue(all(isinstance(v, str) for v in defauts.values()))
        self.assertEqual({c: serveur.DEFAUTS_DES_CHAMPS.get(t, {}).get(c, "")
                          for f in COLONNES_AJOUTEES.values() for t, cs in f.items() for c in cs}, DEFAUTS_AJOUTES)

    def test_jeux_tous_classes_pour_la_concordance(self):
        self.assertEqual(set(JEUX), set(JEUX_CONCORDANTS) | set(ECARTS_DOCUMENTES) | set(JEUX_ABIMES))

    # -- cle_de_colonne et format_du_fichier --------------------------------------------------------------------

    def test_cle_de_colonne(self):
        cas = {
            "date_creation": "datecreation", " Date Création ": "datecreation", CARACTERE_BOM + "id": "id",
            "TITRE": "titre", "ti tre": "titre", "Tîtré": "titre", INSECABLE + "titre" + INSECABLE_FINE: "titre",
            CADRATIN + "ti" + IDEOGRAPHIQUE + "tre\t\r\n": "titre", "ti" + ESPACE_NULLE + "tre": "ti" + ESPACE_NULLE + "tre",
            "titre" + LIGNE_SUIVANTE: "titre" + LIGNE_SUIVANTE, None: "", 42: "42", "": "",
        }
        for nom, cle in cas.items():
            with self.subTest(nom=nom):
                self.assertEqual(serveur.cle_de_colonne(nom), cle)

    def test_format_de_chaque_fichier_de_chaque_jeu(self):
        vus = set()
        for jeu in JEUX:
            for table, contenu in sorted(self.base(jeu).items()):
                with self.subTest(jeu=jeu, table=table):
                    if (jeu, table) in FORMATS_PARTICULIERS:
                        attendu = FORMATS_PARTICULIERS[(jeu, table)]
                        vus.add((jeu, table))
                    else:
                        attendu = format_attendu(table, FORMAT_DES_FICHIERS.get(jeu, FORMAT_COURANT))
                    self.assertEqual(serveur.format_du_fichier(table, contenu["entete"]), attendu)
        self.assertEqual(vus, set(FORMATS_PARTICULIERS), "cas particuliers absents des jeux")

    def test_format_du_fichier_en_tetes_fabriques_sans_exception(self):
        ot = lambda format: serveur.colonnes_du_format("ordres_travail", format)  # noqa: E731

        class Etrange:
            def __str__(self):
                raise ValueError("illisible")

        self.assertEqual([serveur.format_du_fichier("ordres_travail", ot(f)) for f in (1, 2, 3)], [1, 2, 3])
        self.assertEqual(serveur.format_du_fichier("ordres_travail", list(reversed(ot(3)))), 3)
        self.assertEqual(serveur.format_du_fichier("ordres_travail", tuple(ot(3))), 3)
        self.assertEqual(serveur.format_du_fichier(
            "ordres_travail", [CARACTERE_BOM + "id"] + ["  %s \t" % n for n in ot(3)[1:]]), 3)
        self.assertEqual(serveur.format_du_fichier("ordres_travail", ["avant"] + ot(2) + ["apres", "astuce"]), 3)
        self.assertEqual(serveur.format_du_fichier("ordres_travail", [n for n in ot(3) if n != "titre"]), 0)
        self.assertEqual(serveur.format_du_fichier("parametres", ["Cle", "Valeur"]), 3)
        self.assertEqual(serveur.format_du_fichier(
            "ordres_travail", ["Date Création" if n == "date_creation" else n for n in ot(3)]), 3)
        self.assertEqual(serveur.format_du_fichier("wiki_pages", serveur.colonnes_du_format("wiki_pages", 3)), 3)
        self.assertEqual(serveur.format_du_fichier("wiki_pages", serveur.colonnes_du_format("wiki_pages", 3)[1:]), 0)
        self.assertEqual(serveur.format_du_fichier("wiki_journal", []), 0)
        self.assertIsNone(serveur.format_du_fichier("pieces_v4", ["id"]))
        self.assertIsNone(serveur.format_du_fichier(None, ["id"]))
        self.assertIsNone(serveur.format_du_fichier(["ordres_travail"], ["id"]))
        etranges = [None, "id;origine", 42, {}, [None, None, 3, {}], [Etrange()], ot(3) + [Etrange()]]
        self.assertEqual([serveur.format_du_fichier("ordres_travail", e) for e in etranges], [0] * len(etranges))

    # -- version_de_base ----------------------------------------------------------------------------------------

    def test_version_de_base_de_chaque_jeu(self):
        for jeu in JEUX:
            with self.subTest(jeu=jeu):
                self.assertEqual(serveur.version_de_base(lignes_de_parametres(self.base(jeu))),
                                 VERSION_DE_BASE.get(jeu, FORMAT_COURANT))

    def test_version_de_base_regle(self):
        def version(valeur, cle="version_schema"):
            return serveur.version_de_base([{"cle": "delai_p1_h", "valeur": "'9"}, {"cle": cle, "valeur": valeur}])

        # Cellules du fichier : l'apostrophe de protection est retirée comme Donnees.csv.relireValeur le fait
        cas = {"3": 3, "'3": 3, "'2": 2, " 2 ": 2, "'2,0": 2, "2.0": 2, "'2,5": 2.5, "+3": 3, "'+3": 3, "'-1": -1,
               "''3": 1, "'3 000": 1, "3 000": 3000, "'1e3": 1, "abc": 1, "'abc": 1, "": 1, "'": 1, "v3": 1,
               INSECABLE + "3" + INSECABLE_FINE: 3, "'3" + CADRATIN: 1, None: 1}
        for valeur, attendu in cas.items():
            with self.subTest(valeur=valeur):
                self.assertEqual(version(valeur), attendu)
                self.assertIs(type(version(valeur)), type(attendu))
        self.assertEqual(version("'2", cle="  version_schema\t"), 2)          # clé lue comme un identifiant
        self.assertEqual(version("'2", cle="'version_schema"), 1)
        self.assertEqual(serveur.version_de_base([{"Clé": "version_schema", " Valeur ": "'2"}]), 2)
        self.assertEqual(serveur.version_de_base([{"cle": "entreprise_nom", "valeur": "3"}]), 1)
        self.assertEqual(serveur.version_de_base([]), 1)
        for pas_une_liste in (None, "version_schema;3", {}, 3):
            self.assertEqual(serveur.version_de_base(pas_une_liste), 1)
        self.assertEqual(serveur.version_de_base([{"cle": "version_schema", "valeur": "'2"},
                                                  {"cle": "version_schema", "valeur": "'3"}]), 2)
        self.assertEqual(serveur.version_de_base([None, 3, {"cle": "version_schema", "valeur": "'2"}]), 2)
        self.assertEqual(serveur.version_de_base([{"cle": "version_schema"}]), 1)

    def test_relire_et_ecrire_une_valeur_texte(self):
        valeurs = ["", "3", "'3", "''3", "abc", "'abc", "=1+1", "-5", "@x", "\tx", "12/03", "08:30", "15 %", "1,5E+3",
                   " 3 ", "x'", "'", "3 000", "007", "2026-11-04"]
        for valeur in valeurs:
            with self.subTest(valeur=valeur):
                self.assertEqual(serveur.relire_valeur_texte(serveur.ecrire_valeur_texte(valeur)), valeur)
        self.assertEqual(serveur.ecrire_valeur_texte("3"), "'3")
        self.assertEqual(serveur.ecrire_valeur_texte("abc"), "abc")
        self.assertEqual(serveur.relire_valeur_texte("'abc"), "'abc")
        self.assertEqual(serveur.relire_valeur_texte(None), "")

    # -- migrer_tables sur chaque jeu ---------------------------------------------------------------------------

    def test_migration_de_chaque_jeu_sans_perte(self):
        for jeu in JEUX:
            with self.subTest(jeu=jeu):
                base = self.base(jeu)
                avant = copy.deepcopy(base)
                de = serveur.version_de_base(lignes_de_parametres(base))
                apres, journal, etapes = serveur.migrer_tables(base, de, FORMAT_COURANT)
                self.assertEqual(base, avant, "migrer_tables a modifié la base reçue")
                self.assertEqual(journal, LIGNES_DE_JOURNAL.get(de, []))
                self.assertEqual([(e["de"], e["vers"]) for e in etapes],
                                 [(n - 1, n) for n in range(de + 1, FORMAT_COURANT + 1)])
                self.assertEqual(ecarts_de_cellules(avant, apres), [])
                if de >= FORMAT_COURANT:
                    self.assertIs(apres, base)          # déjà au format courant (ou plus récent) : rien ne change
                    continue
                for table, contenu in apres.items():
                    with self.subTest(jeu=jeu, table=table):
                        self.assertEqual(serveur.format_du_fichier(table, contenu["entete"]), FORMAT_COURANT)
                        if table not in avant:
                            self.assertEqual(contenu, {"entete": list(serveur.COLONNES_PAR_TABLE[table]),
                                                       "lignes": []})
                            continue
                        entete_avant = avant[table]["entete"]
                        nouvelles = [c for f in range(de + 1, FORMAT_COURANT + 1)
                                     for c in COLONNES_AJOUTEES[f].get(table, [])]
                        self.assertEqual(contenu["entete"], entete_avant + nouvelles)     # nouvelles en fin
                        for ligne in contenu["lignes"]:
                            self.assertEqual({c: ligne[c] for c in nouvelles}, {c: DEFAUTS_AJOUTES[c] for c in nouvelles})
                self.assertEqual(sorted(apres), sorted(serveur.TABLES))
                self.assertNotIn("wiki_pages", avant)
                self.assertEqual(apres["wiki_pages"]["lignes"], [])
                self.assertEqual(apres["wiki_journal"]["lignes"], [])
                # version_schema écrite comme Prévo l'écrit, relue 3
                self.assertEqual([l["valeur"] for l in apres["parametres"]["lignes"] if l["cle"] == "version_schema"],
                                 ["'3"])
                self.assertEqual(serveur.version_de_base(apres["parametres"]["lignes"]), FORMAT_COURANT)
                # Rejouée d'après la version relue : rien ne change ; depuis le format d'origine : même base
                rejouee = serveur.migrer_tables(apres, serveur.version_de_base(apres["parametres"]["lignes"]),
                                                FORMAT_COURANT)
                self.assertIs(rejouee[0], apres)
                self.assertEqual(rejouee[1:], ([], []))
                depuis_origine = serveur.migrer_tables(apres, de, FORMAT_COURANT)
                self.assertEqual(depuis_origine[0], apres)
                self.assertEqual(depuis_origine[1], journal)

    def test_migration_f1_et_f2_detail(self):
        avant = self.base("f1")
        apres, journal, _ = serveur.migrer_tables(avant, 1, FORMAT_COURANT)
        self.assertEqual(sorted(avant), ["demandes", "equipements", "ordres_travail", "parametres"])
        self.assertEqual(len(apres), 24)
        self.assertEqual(journal, ["passage au format 2 du fichier", "passage au format 3 du fichier"])
        self.assertEqual(apres["ordres_travail"]["entete"][-2:], ["anomalie_constatee", "astuce"])
        self.assertEqual(apres["demandes"]["entete"][-2:], ["symptome_code", "ot_origine_id"])
        self.assertEqual(apres["equipements"]["entete"][-1], "valeur_remplacement")
        self.assertTrue(all(l["anomalie_constatee"] == "0" and l["astuce"] == "" for l in apres["ordres_travail"]["lignes"]))
        self.assertEqual(len(apres["ordres_travail"]["lignes"]), 12)
        # parametres.csv de f1 porte version_schema;'1 (dernière ligne) : la cellule devient '3, rien d'autre ne change
        self.assertEqual(avant["parametres"]["lignes"][-1], {"cle": "version_schema", "valeur": "'1"})
        self.assertEqual(apres["parametres"]["lignes"][:-1], avant["parametres"]["lignes"][:-1])
        self.assertEqual(apres["parametres"]["lignes"][-1], {"cle": "version_schema", "valeur": "'3"})
        sans_version = {"parametres": {"entete": avant["parametres"]["entete"],
                                       "lignes": avant["parametres"]["lignes"][:-1]}}
        self.assertEqual(serveur.version_de_base(sans_version["parametres"]["lignes"]), 1)
        ajoutee = serveur.migrer_tables(sans_version, 1, FORMAT_COURANT)[0]["parametres"]["lignes"]
        self.assertEqual(ajoutee, avant["parametres"]["lignes"][:-1] + [{"cle": "version_schema", "valeur": "'3"}])
        avant2 = self.base("f2-v1.1.0")
        apres2, journal2, _ = serveur.migrer_tables(avant2, 2, FORMAT_COURANT)
        self.assertEqual(journal2, ["passage au format 3 du fichier"])
        self.assertEqual(len(avant2), 22)
        self.assertEqual(sorted(set(apres2) - set(avant2)), ["wiki_journal", "wiki_pages"])
        self.assertEqual(apres2["ordres_travail"]["entete"], avant2["ordres_travail"]["entete"] + ["astuce"])
        for table in avant2:
            if table != "ordres_travail":
                self.assertEqual(apres2[table]["entete"], avant2[table]["entete"], table)
        self.assertEqual(len(apres2["parametres"]["lignes"]), len(avant2["parametres"]["lignes"]))

    def test_plus_recent_laisse_intact(self):
        fichiers = self.fichiers["plus-recent"]
        base = base_de_fichiers(fichiers)
        avant = copy.deepcopy(base)
        de = serveur.version_de_base(base["parametres"]["lignes"])
        self.assertEqual(de, 4)
        resultat, journal, etapes = serveur.migrer_tables(base, de, FORMAT_COURANT)
        self.assertIs(resultat, base)
        self.assertEqual((journal, etapes), ([], []))
        self.assertEqual(base, avant)
        self.assertEqual(base["ordres_travail"]["entete"][-1], "nouvelle_colonne_v4")
        self.assertIsNone(serveur.format_du_fichier("pieces_v4", base["pieces_v4"]["entete"]))
        # Réécrit tel quel, chaque fichier redonne ses octets (table inconnue et colonne inconnue comprises)
        for table, octets in fichiers.items():
            with self.subTest(table=table):
                self.assertEqual(octets_de_table(resultat[table]), octets)

    # -- ETAPES_FORMAT ------------------------------------------------------------------------------------------

    def test_etapes_chaine_sans_trou_et_descriptions(self):
        self.assertEqual([(e.de, e.vers) for e in serveur.ETAPES_FORMAT], [(1, 2), (2, 3)])
        self.assertEqual(serveur.ETAPES_FORMAT[-1].vers, serveur.VERSION_SCHEMA_CSV)
        for etape in serveur.ETAPES_FORMAT:
            with self.subTest(etape=etape.vers):
                for table, colonnes in COLONNES_AJOUTEES[etape.vers].items():
                    for colonne in colonnes:
                        self.assertIn("%s.%s" % (table, colonne), etape.description)
                for table in TABLES_AJOUTEES[etape.vers]:
                    self.assertIn(table, etape.description)
                with self.assertRaises(AttributeError):
                    etape.autre = 1                         # __slots__ : pas d'attribut ajouté par mégarde

    def test_appliquer_pure_et_idempotente_sur_chaque_jeu(self):
        for jeu in JEUX:
            base = self.base(jeu)
            avant = copy.deepcopy(base)
            for etape in serveur.ETAPES_FORMAT:
                with self.subTest(jeu=jeu, etape=etape.vers):
                    une = etape.appliquer(base)
                    self.assertEqual(base, avant, "entrée modifiée")
                    self.assertIsNot(une, base)
                    for table, contenu in base.items():         # rien de partagé avec l'entrée
                        self.assertIsNot(une[table], contenu)
                        self.assertIsNot(une[table]["entete"], contenu["entete"])
                        self.assertFalse(any(a is b for a, b in zip(une[table]["lignes"], contenu["lignes"])))
                    self.assertEqual(etape.appliquer(une), une, "pas idempotente")
                    versions = [l["valeur"] for l in une["parametres"]["lignes"] if l["cle"] == "version_schema"]
                    self.assertEqual(versions[:1], ["'%d" % etape.vers])

    def test_appliquer_cas_fabriques(self):
        base = {
            "equipements": {"entete": ["id", "colonne_maison", "designation", "actif"], "lignes": [
                {"id": "EQ-0001", "colonne_maison": "m1", "designation": "Presse", "actif": "0"},
                {"id": "EQ-0002", "colonne_maison": "", "designation": "Tour", "actif": "1",
                 "valeur_remplacement": "1200"},
            ]},
            "ordres_travail": {"entete": [CARACTERE_BOM + "id", " titre "],
                               "lignes": [{CARACTERE_BOM + "id": "OT-1", " titre ": "T"}]},
            "demandes": {"entete": [" %s " % n for n in serveur.colonnes_du_format("demandes", 3)], "lignes": []},
            "pieces_v4": {"entete": ["id", "stock"], "lignes": [{"id": "P-1", "stock": "3"}], "note": "table inconnue"},
        }
        avant = copy.deepcopy(base)
        deux = serveur.ETAPES_FORMAT[0].appliquer(base)
        trois = serveur.ETAPES_FORMAT[1].appliquer(deux)
        self.assertEqual(base, avant)
        equipements = deux["equipements"]
        self.assertEqual(equipements["entete"][:4], ["id", "colonne_maison", "designation", "actif"])
        self.assertEqual(equipements["entete"][-1], "valeur_remplacement")
        self.assertIn("repere", equipements["entete"][4:])
        self.assertEqual(equipements["lignes"][0]["colonne_maison"], "m1")
        self.assertEqual(equipements["lignes"][0]["actif"], "0")            # valeur gardée, pas le défaut '1'
        self.assertEqual(equipements["lignes"][0]["criticite"], "B")         # défaut du schéma
        self.assertEqual(equipements["lignes"][0]["statut"], "en service")
        self.assertEqual(equipements["lignes"][0]["valeur_remplacement"], "")
        self.assertEqual(equipements["lignes"][1]["valeur_remplacement"], "1200")   # déjà là : jamais écrasée
        ordres = deux["ordres_travail"]
        self.assertEqual(ordres["entete"][:2], [CARACTERE_BOM + "id", " titre "])
        self.assertNotIn("id", ordres["entete"])
        self.assertNotIn("titre", ordres["entete"])
        self.assertEqual(len(ordres["entete"]), len(serveur.colonnes_du_format("ordres_travail", 2)))
        self.assertEqual(ordres["lignes"][0]["statut"], "Créé")
        self.assertEqual(deux["demandes"]["entete"], [" %s " % n for n in serveur.colonnes_du_format("demandes", 3)])
        self.assertEqual(deux["pieces_v4"], avant["pieces_v4"])
        self.assertEqual(deux["parametres"], {"entete": ["cle", "valeur"],
                                              "lignes": [{"cle": "version_schema", "valeur": "'2"}]})
        self.assertNotIn("wiki_pages", deux)
        self.assertEqual(trois["parametres"]["lignes"], [{"cle": "version_schema", "valeur": "'3"}])
        self.assertEqual(trois["ordres_travail"]["entete"][-1], "astuce")
        self.assertEqual(trois["wiki_journal"], {"entete": list(serveur.COLONNES_PAR_TABLE["wiki_journal"]),
                                                 "lignes": []})
        avec_parametres = serveur.ETAPES_FORMAT[1].appliquer({"parametres": {"entete": ["cle", "valeur", "note"],
            "lignes": [{"cle": "entreprise_nom", "valeur": "A", "note": "n"}]}})
        self.assertEqual(avec_parametres["parametres"]["lignes"], [
            {"cle": "entreprise_nom", "valeur": "A", "note": "n"}, {"cle": "version_schema", "valeur": "'3", "note": ""}])
        # Clé en double : la première ligne porte la version ; noms de colonnes « à la main » reconnus
        plus_recente = serveur.ETAPES_FORMAT[1].appliquer({"parametres": {"entete": ["cle", "valeur"],
            "lignes": [{"cle": "version_schema", "valeur": "'3"}, {"cle": "version_schema", "valeur": "'9"}]}})
        self.assertEqual(plus_recente["parametres"]["lignes"], [{"cle": "version_schema", "valeur": "'3"},
                                                                {"cle": "version_schema", "valeur": "'9"}])
        a_la_main = serveur.ETAPES_FORMAT[1].appliquer({"parametres": {"entete": ["Clé", " Valeur"],
            "lignes": [{"Clé": " version_schema ", " Valeur": "'2"}]}})
        self.assertEqual(a_la_main["parametres"], {"entete": ["Clé", " Valeur"],
                                                   "lignes": [{"Clé": " version_schema ", " Valeur": "'3"}]})
        self.assertEqual(len(serveur.ETAPES_FORMAT[0].appliquer(None)), 22)
        self.assertEqual(len(serveur.ETAPES_FORMAT[1].appliquer("pas une base")), 24)
        self.assertEqual(serveur.ETAPES_FORMAT[0].appliquer({"equipements": None, "parametres": {"lignes": [None]}})[
            "parametres"]["lignes"], [{"cle": "", "valeur": ""}, {"cle": "version_schema", "valeur": "'2"}])

    def test_migrer_etapes_choisies_et_erreurs(self):
        base = {"ordres_travail": {"entete": serveur.colonnes_du_format("ordres_travail", 1), "lignes": []}}
        vers_deux, journal, etapes = serveur.migrer_tables(base, 1, 2)
        self.assertEqual(journal, ["passage au format 2 du fichier"])
        self.assertEqual(vers_deux["ordres_travail"]["entete"][-1], "anomalie_constatee")
        self.assertEqual(len(vers_deux), 22)
        self.assertEqual(vers_deux["parametres"]["lignes"], [{"cle": "version_schema", "valeur": "'2"}])
        self.assertEqual(etapes, [{"de": 1, "vers": 2, "description": serveur.ETAPES_FORMAT[0].description}])
        self.assertEqual(serveur.migrer_tables(base, 0, 3)[1], LIGNES_DE_JOURNAL[1])
        self.assertEqual(serveur.migrer_tables(base, 2.5, 3)[1], ["passage au format 3 du fichier"])
        self.assertEqual(serveur.migrer_tables(base, 1, 3.0)[1], LIGNES_DE_JOURNAL[1])
        self.assertEqual(serveur.migrer_tables(base, float("-inf"), 3)[1], LIGNES_DE_JOURNAL[1])
        self.assertIs(serveur.migrer_tables(base, 2, 2)[0], base)
        self.assertIs(serveur.migrer_tables(base, float("inf"), 3)[0], base)
        for vers in (4, 0, 2.5, "3", True, None, float("nan")):
            with self.subTest(vers=vers), self.assertRaisesRegex(ValueError, "format cible inconnu"):
                serveur.migrer_tables(base, 1, vers)
        for de in (float("nan"), "1", None, True):
            with self.subTest(de=de), self.assertRaisesRegex(TypeError, "format de départ illisible"):
                serveur.migrer_tables(base, de, 3)


# ---------------------------------------------------------------------------------------------------------------
# 2. Concordance navigateur / serveur
# ---------------------------------------------------------------------------------------------------------------

# Chemin du navigateur pour un jeu ({table: octets en base64}) : Donnees.csv.analyser (lecture de Prévo), en-tête du
# fichier par Papa.parse (pour Formats.formatDuFichier et Formats.migrer), Formats.versionDeBase, Formats.migrer
# jusqu'au format courant, Donnees.csv.serialiser de chaque table connue du schéma.
SCRIPT_NAVIGATEUR = """
window.octetsDeBase64 = function (texte) {
  const binaire = atob(texte);
  const octets = new Uint8Array(binaire.length);
  for (let i = 0; i < binaire.length; i += 1) { octets[i] = binaire.charCodeAt(i); }
  return octets;
};
window.base64DOctets = function (octets) {
  let binaire = '';
  for (let i = 0; i < octets.length; i += 1) { binaire += String.fromCharCode(octets[i]); }
  return btoa(binaire);
};
window.enteteDuFichier = function (octets, separateur) {
  const texte = Donnees.csv.decoder(octets).texte;
  if (texte.trim() === '') { return []; }
  return Papa.parse(texte, { delimiter: separateur, quoteChar: '"', skipEmptyLines: 'greedy', preview: 1 }).data[0] || [];
};
window.cheminNavigateur = function (jeu) {
  const base = { tables: {} };
  const inconnues = {};
  const formats = {};
  for (const table of Object.keys(jeu)) {
    const octets = octetsDeBase64(jeu[table]);
    if (!Schema.table(table)) { formats[table] = Formats.formatDuFichier(table, enteteDuFichier(octets, ';')); continue; }
    const lu = Donnees.csv.analyser(table, octets);
    const entete = enteteDuFichier(octets, lu.separateur);
    base.tables[table] = { entete: entete, lignes: lu.lignes };
    inconnues[table] = lu.colonnesInconnues;
    formats[table] = Formats.formatDuFichier(table, entete);
  }
  const de = Formats.versionDeBase(base.tables.parametres ? base.tables.parametres.lignes : []);
  const resultat = Formats.migrer(base, de, Formats.courant);
  const entetes = {};
  const octets = {};
  for (const table of Object.keys(resultat.base.tables)) {
    entetes[table] = resultat.base.tables[table].entete;
    octets[table] = base64DOctets(Donnees.csv.serialiser(table, resultat.base.tables[table].lignes,
      inconnues[table] || []));
  }
  return { formats: formats, de: de, journal: resultat.journal,
    etapes: resultat.etapes.map(function (e) { return [e.de, e.vers]; }), entetes: entetes, octets: octets };
};
"""


def au_modele_de_donnees(table, contenu):
    """Octets d'une table de la base du serveur réécrite comme Donnees.csv.serialiser l'écrit (écarts A et B) : toutes
    les colonnes du schéma dans son ordre (absente du fichier : défaut du champ), puis les colonnes inconnues dans leur
    ordre d'origine."""
    schema = list(serveur.COLONNES_PAR_TABLE[table])
    cles_du_schema = {serveur.cle_de_colonne(nom) for nom in schema}
    inconnues = [nom for nom in contenu["entete"] if serveur.cle_de_colonne(nom) not in cles_du_schema]
    defauts = serveur.DEFAUTS_DES_CHAMPS.get(table, {})

    def cellule(ligne, colonne):
        nom = serveur.colonne_de_champ(contenu["entete"], colonne)
        return defauts.get(colonne, "") if nom is None else ligne.get(nom, "")

    lignes = [[cellule(ligne, c) for c in schema] + [ligne.get(n, "") for n in inconnues] for ligne in contenu["lignes"]]
    return serveur.ecrire_tableau_csv(schema + inconnues, lignes)


class TestConcordanceNavigateur(JeuxEnCopie, CasNavigateur):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.copier_les_jeux()

    def setUp(self):
        super().setUp()
        charger_scripts(self.page, SCRIPTS)
        self.page.add_script_tag(content=SCRIPT_NAVIGATEUR)

    def evaluer(self, script, argument=None):
        return self.page.evaluate(script, argument)

    def chemins(self, jeu):
        """(navigateur, serveur) pour un jeu ; octets du navigateur décodés."""
        fichiers = self.fichiers[jeu]
        navigateur = self.evaluer("(jeu) => cheminNavigateur(jeu)",
                                  {table: base64.b64encode(octets).decode("ascii") for table, octets in fichiers.items()})
        navigateur["octets"] = {table: base64.b64decode(texte) for table, texte in navigateur["octets"].items()}
        return navigateur, chemin_serveur(fichiers)

    def verifier_concordance(self, jeu, tables_ecartees=()):
        """Mêmes formats, même version, même journal, mêmes en-têtes migrés, mêmes octets par table (hors tables
        écartées, et hors tables inconnues du schéma que le navigateur n'écrit pas)."""
        navigateur, cote_serveur = self.chemins(jeu)
        self.assertEqual(navigateur["formats"], cote_serveur["formats"])
        self.assertEqual(navigateur["de"], cote_serveur["de"])
        self.assertEqual(navigateur["journal"], cote_serveur["journal"])
        self.assertEqual(navigateur["etapes"], cote_serveur["etapes"])
        connues = {t for t in cote_serveur["octets"] if t in serveur.COLONNES_PAR_TABLE}
        self.assertEqual(set(navigateur["octets"]), connues)
        self.assertEqual({t: navigateur["entetes"][t] for t in connues}, {t: cote_serveur["entetes"][t] for t in connues})
        for table in sorted(connues - set(tables_ecartees)):
            with self.subTest(jeu=jeu, table=table):
                self.assertEqual(navigateur["octets"][table], cote_serveur["octets"][table])
        return navigateur, cote_serveur

    # -- Mêmes listes et mêmes règles que js/ -------------------------------------------------------------------

    def test_registre_identique_a_schema_et_formats(self):
        js = self.evaluer("""() => {
          const colonnes = {};
          const tables = {};
          for (let format = 1; format <= Formats.courant; format += 1) {
            tables[format] = Formats.tables(format);
            colonnes[format] = Object.fromEntries(Schema.nomsTables().map((t) => [t, Formats.colonnes(t, format)]));
          }
          const defauts = {};
          const depuis = {};
          const ecritureDesDefauts = [];
          for (const nom of Schema.nomsTables()) {
            for (const champ of Schema.table(nom).champs) {
              if (champ.defaut !== undefined) {
                (defauts[nom] = defauts[nom] || {})[champ.nom] = champ.defaut;
                if (Donnees.csv.ecrireValeur(champ, champ.defaut) !== champ.defaut) { ecritureDesDefauts.push(nom + '.' + champ.nom); }
              }
              if (champ.depuisVersion !== undefined) { (depuis[nom] = depuis[nom] || {})[champ.nom] = champ.depuisVersion; }
            }
          }
          const tablesDepuis = Object.fromEntries(Schema.nomsTables().filter((t) => Schema.table(t).depuisVersion !== undefined)
            .map((t) => [t, Schema.table(t).depuisVersion]));
          return { courant: Formats.courant, nomsTables: Schema.nomsTables(), tables, colonnes, defauts, depuis,
            tablesDepuis, ecritureDesDefauts,
            etapes: Formats.ETAPES.map((e) => ({ de: e.de, vers: e.vers, description: e.description })) };
        }""")
        self.assertEqual(js["courant"], serveur.VERSION_SCHEMA_CSV)
        self.assertEqual(js["nomsTables"], list(serveur.TABLES))
        for format in range(1, FORMAT_COURANT + 1):
            with self.subTest(format=format):
                self.assertEqual(js["tables"][str(format)], serveur.tables_du_format(format))
                self.assertEqual(js["colonnes"][str(format)],
                                 {t: serveur.colonnes_du_format(t, format) for t in serveur.TABLES})
        self.assertEqual(js["defauts"], serveur.DEFAUTS_DES_CHAMPS)
        self.assertEqual(js["ecritureDesDefauts"], [], "un défaut s'écrirait avec une apostrophe")
        self.assertEqual(js["depuis"], serveur.PREMIER_FORMAT_DES_COLONNES)
        self.assertEqual(js["tablesDepuis"], serveur.PREMIER_FORMAT_DES_TABLES)
        self.assertEqual(js["etapes"], [{"de": e.de, "vers": e.vers, "description": e.description}
                                        for e in serveur.ETAPES_FORMAT])

    def test_format_du_fichier_comme_le_navigateur(self):
        variantes = ["titre", "Titre", " titre ", "TITRE", "ti_tre", "ti tre", "Tîtré", "Tİtre", CARACTERE_BOM + "titre",
                     "titre" + INSECABLE, INSECABLE_FINE + "titre", CADRATIN + "titre", "titre" + IDEOGRAPHIQUE,
                     "ti" + ESPACE_NULLE + "tre", "titre" + LIGNE_SUIVANTE, "titre" + SEPARATEUR_DE_FICHIER,
                     "titre\t", "titre\n", "_titre_", "titres", "", CARACTERE_BOM]
        entetes = [[v if n == "titre" else n for n in serveur.colonnes_du_format("ordres_travail", 3)] for v in variantes]
        entetes += [serveur.colonnes_du_format("ordres_travail", f) for f in (1, 2)] + [[], ["id"]]
        js = self.evaluer("(entetes) => entetes.map((e) => Formats.formatDuFichier('ordres_travail', e))", entetes)
        self.assertEqual(js, [serveur.format_du_fichier("ordres_travail", e) for e in entetes])
        self.assertIn(0, js)
        self.assertIn(3, js)
        autres = {"pieces_v4": ["id"], "parametres": ["Clé", " VALEUR "], "wiki_pages": []}
        js = self.evaluer("(cas) => Object.fromEntries(Object.entries(cas).map(([t, e]) => [t, Formats.formatDuFichier(t, e)]))",
                          autres)
        self.assertEqual(js, {t: serveur.format_du_fichier(t, e) for t, e in autres.items()})

    def test_version_de_base_et_apostrophe_comme_le_navigateur(self):
        valeurs = ["3", "'3", "''3", "'2", " 2 ", "'2,0", "2.0", "'2,5", "+3", "'+3", "'-1", "'3 000", "3 000", "'1e3",
                   "abc", "'abc", "", "'", "v3", "'=3", "'12/03", INSECABLE + "3", "'3" + INSECABLE_FINE, CADRATIN + "3",
                   "'4", "4"]
        cles = ["version_schema", " version_schema ", "'version_schema", "Version_schema"]
        cas = [(["cle", "valeur"], [cle, valeur]) for cle in cles[:1] for valeur in valeurs]
        cas += [(["cle", "valeur"], [cle, "'2"]) for cle in cles[1:]]
        cas += [(["Clé", "Valeur"], ["version_schema", "'2"]), (["cle", "valeur"], ["entreprise_nom", "3"])]
        fichiers = [serveur.ecrire_tableau_csv(entete, [ligne]) for entete, ligne in cas]
        js = self.evaluer("""(fichiers) => fichiers.map((f) =>
          Formats.versionDeBase(Donnees.csv.analyser('parametres', octetsDeBase64(f)).lignes))""",
                          [base64.b64encode(octets).decode("ascii") for octets in fichiers])
        python = [serveur.version_de_base(table_de_base(octets)["lignes"]) for octets in fichiers]
        self.assertEqual(python, js)
        self.assertEqual(python[:3], [3, 3, 1])
        textes = valeurs + ["=1+1", "-5", "@x", "\tx", "08:30", "15 %", "1,5E+3", "x'", "007", "2026-11-04", " 3"]
        js = self.evaluer("""(valeurs) => { const champ = Schema.champ('parametres', 'valeur');
          return { relues: valeurs.map((v) => Donnees.csv.relireValeur(champ, v)),
            ecrites: valeurs.map((v) => Donnees.csv.ecrireValeur(champ, v)) }; }""", textes)
        self.assertEqual([serveur.relire_valeur_texte(v) for v in textes], js["relues"])
        self.assertEqual([serveur.ecrire_valeur_texte(v) for v in textes], js["ecrites"])

    def test_etapes_cas_fabriques_comme_le_navigateur(self):
        # Même base fabriquée, mêmes étapes : mêmes tables, en-têtes et lignes ; la seule différence de forme est la
        # cellule de version_schema (« '3 » côté serveur, cellule du fichier ; « 3 » en mémoire côté navigateur).
        bases = [
            {"equipements": {"entete": ["id", "colonne_maison", "designation", "actif"], "lignes": [
                {"id": "EQ-1", "colonne_maison": "m1", "designation": "Presse", "actif": "0"},
                {"id": "EQ-2", "colonne_maison": "", "designation": "Tour", "valeur_remplacement": "1200"}]},
             "ordres_travail": {"entete": [CARACTERE_BOM + "id", " titre "],
                                "lignes": [{CARACTERE_BOM + "id": "OT-1", " titre ": "T"}]},
             "wiki_pages": {"entete": ["id", "type"], "lignes": [{"id": "WP-1", "type": "composant"}]},
             "pieces_v4": {"entete": ["id"], "lignes": [{"id": "P-1"}]}},
            {"parametres": {"entete": ["cle", "valeur", "note"], "lignes": [
                {"cle": "entreprise_nom", "valeur": "A", "note": "n"}, {"cle": "version_schema", "valeur": "1"}]}},
            {},
        ]
        js = self.evaluer("""(bases) => bases.map((tables) => Formats.ETAPES.map((etape) =>
          etape.appliquer({ tables: tables }).tables))""", bases)
        for numero, base in enumerate(bases):
            for rang, etape in enumerate(serveur.ETAPES_FORMAT):
                with self.subTest(base=numero, etape=etape.vers):
                    python = etape.appliquer(base)
                    for ligne in python["parametres"]["lignes"]:
                        if ligne["cle"] == "version_schema":
                            ligne["valeur"] = serveur.relire_valeur_texte(ligne["valeur"])
                    self.assertEqual(python, js[numero][rang])

    # -- Chaque jeu : lecture + migration + écriture → mêmes octets ---------------------------------------------

    def test_concordance_f1(self):
        self.verifier_concordance("f1")

    def test_concordance_f2_v1_1_0(self):
        self.verifier_concordance("f2-v1.1.0")

    def test_concordance_f3_v1_2_0(self):
        self.verifier_concordance("f3-v1.2.0")

    def test_concordance_f3_v2_0_0(self):
        self.verifier_concordance("f3-v2.0.0")

    def test_concordance_sans_bom(self):
        self.verifier_concordance("sans-bom")

    def test_concordance_table_absente(self):
        navigateur, _ = self.verifier_concordance("table-absente")
        self.assertNotIn("articles", navigateur["octets"])
        self.assertNotIn("wiki_pages", navigateur["octets"])

    def test_concordance_plus_recent(self):
        # Tables connues : mêmes octets ; la table inconnue pieces_v4 n'est écrite que par le serveur, telle quelle.
        _, cote_serveur = self.verifier_concordance("plus-recent")
        self.assertEqual(cote_serveur["octets"]["pieces_v4"], self.fichiers["plus-recent"]["pieces_v4"])

    @unittest.expectedFailure
    def test_concordance_colonnes_en_trop(self):
        """Écart A (préexistant) : Donnees.csv.serialiser écrit colonne_maison en fin de fichier, après les colonnes du
        schéma ; ecrire_tableau_csv la garde à sa place (après designation), comme Formats.migrer et migrer_tables
        gardent l'en-tête. Voir test_ecarts_documentes_et_seulement_eux."""
        self.verifier_concordance("colonnes-en-trop")

    @unittest.expectedFailure
    def test_concordance_colonnes_manquantes(self):
        """Écart B (préexistant) : Donnees.csv.analyser complète modele et valeur_remplacement (défaut '') et
        serialiser écrit toutes les colonnes du schéma ; le serveur réécrit l'en-tête tel quel (base au format 3 :
        aucune étape ne s'applique, des deux côtés)."""
        self.verifier_concordance("colonnes-manquantes")

    @unittest.expectedFailure
    def test_concordance_melange(self):
        """Écart B (préexistant) : ordres_travail sans astuce dans une base au format 3 ; le navigateur écrit astuce
        (analyser + serialiser), le serveur non (aucune étape ne s'applique)."""
        self.verifier_concordance("melange")

    @unittest.expectedFailure
    def test_concordance_windows_1252(self):
        """Écart C (préexistant) : Donnees.csv.analyser normalise date_mes (12/03/2019 → 2019-03-12) ;
        lire_csv_tolerant garde la cellule brute. Les deux lecteurs acceptent le fichier."""
        self.verifier_concordance("windows-1252")

    def test_ecarts_documentes_et_seulement_eux(self):
        for jeu, (table_touchee, nature) in sorted(ECARTS_DOCUMENTES.items()):
            with self.subTest(jeu=jeu):
                # Formats, version, journal, en-têtes migrés et toutes les autres tables : identiques
                navigateur, cote_serveur = self.verifier_concordance(jeu, tables_ecartees=(table_touchee,))
                octets_navigateur = navigateur["octets"][table_touchee]
                octets_serveur = cote_serveur["octets"][table_touchee]
                self.assertNotEqual(octets_navigateur, octets_serveur, "écart disparu : retirer expectedFailure")
                contenu = table_de_base(self.fichiers[jeu][table_touchee])
                if nature == "colonnes":
                    # Les octets du navigateur sont ceux du serveur une fois les colonnes rangées comme Donnees les range
                    self.assertEqual(octets_navigateur, au_modele_de_donnees(table_touchee, contenu))
                    continue
                # Valeurs : mêmes en-têtes et lignes ; seules les dates de date_mes diffèrent, JJ/MM/AAAA → AAAA-MM-JJ
                entete_n, lignes_n = serveur.lire_csv_tolerant(octets_navigateur)
                entete_s, lignes_s = serveur.lire_csv_tolerant(octets_serveur)
                self.assertEqual(entete_n, entete_s)
                self.assertEqual(len(lignes_n), len(lignes_s))
                differentes = set()
                for ligne_n, ligne_s in zip(lignes_n, lignes_s):
                    for colonne, valeur_n, valeur_s in zip(entete_n, ligne_n, ligne_s):
                        if valeur_n != valeur_s:
                            differentes.add(colonne)
                            jour, mois, annee = valeur_s.split("/")
                            self.assertEqual(valeur_n, "%s-%s-%s" % (annee, mois, jour))
                self.assertEqual(differentes, {"date_mes"})

    def test_jeux_abimes_meme_format_sans_exception(self):
        for jeu, table in sorted(JEUX_ABIMES.items()):
            with self.subTest(jeu=jeu):
                navigateur, cote_serveur = self.chemins(jeu)        # aucune exception, d'un côté ni de l'autre
                self.assertEqual(navigateur["formats"], cote_serveur["formats"])
                self.assertEqual(navigateur["formats"][table], 0)
                self.assertEqual(navigateur["de"], cote_serveur["de"])
                self.assertEqual(navigateur["journal"], cote_serveur["journal"])
                self.assertEqual(cote_serveur["journal"], [])


if __name__ == "__main__":
    unittest.main()
