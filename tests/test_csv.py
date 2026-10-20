"""Tests de la couche CSV de js/donnees.js (ARCHITECTURE.md §3 et §5.2, tâche T05).

Couvre :
    (a) protection par apostrophe : relireValeur(ecrireValeur(v)) === v (valeurs piégées + aléatoires) ;
    (b) octets écrits par serialiser (BOM, CRLF, « ; », ordre des en-têtes, guillemets, apostrophes) ;
    (c) lecture tolérante (dates, nombres, booléens, choix, colonnes, séparateur, encodage…) ;
    (d) fichiers réellement réenregistrés par Excel (tests/fixtures/excel/) ;
    (e) aller-retour Excel à la volée si Excel est installé (sinon test ignoré) ;
    (f) performance : 5 000 lignes × 31 colonnes (ordres_travail, format v2) analysées en moins de 300 ms.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_csv.py" -v

Régénérer les fichiers de tests/fixtures/excel/ (Excel requis) :
    py tests/test_csv.py --generer-fixtures
"""
import base64
import datetime
import random
import sys
import tempfile
import unittest
from pathlib import Path

from commun import RACINE, CasNavigateur, charger_scripts
import excel

SCRIPTS = ["js/lib/papaparse.min.js", "js/schema.js", "js/donnees.js"]
DOSSIER_FIXTURES = RACINE / "tests" / "fixtures" / "excel"
BOM = b"\xef\xbb\xbf"
INSECABLE = chr(0xA0)

# Petites fonctions installées dans la page pour échanger des octets avec Python (base64).
AIDE_JS = """
window.versOctets = (texteBase64) => Uint8Array.from(atob(texteBase64), (c) => c.charCodeAt(0));
window.versBase64 = (octets) => {
  let binaire = '';
  for (let i = 0; i < octets.length; i += 1) { binaire += String.fromCharCode(octets[i]); }
  return btoa(binaire);
};
'aides installées';   // valeur finale qui n'est pas une fonction : Playwright l'appellerait sinon
"""

# ---------------------------------------------------------------------------
# Jeu d'exemple : table equipements (17 champs, dans l'ordre du schéma : les 16 du brief, puis
# valeur_remplacement, ajouté par la version 2 du format, ARCHITECTURE.md §14.1)
# ---------------------------------------------------------------------------

CHAMPS_EQUIPEMENTS = [
    "id", "repere", "designation", "localisation_id", "parent_id", "marque", "modele",
    "num_serie", "date_mes", "criticite", "statut", "heures_fonct_jour",
    "habilitation_requise", "consignation", "document", "actif",
    "valeur_remplacement",
]
# Colonnes de la version 2 du format : absentes des fichiers écrits avant elle (dont les fichiers
# de tests/fixtures/excel/, produits au lot 1 par le vrai Excel) ; leur absence est une « info ».
COLONNES_V2_EQUIPEMENTS = ["valeur_remplacement"]


def equipement(**valeurs):
    """Ligne d'equipements : tous les champs à '' sauf ceux donnés."""
    ligne = dict.fromkeys(CHAMPS_EQUIPEMENTS, "")
    ligne.update(valeurs)
    return ligne


# 4 lignes qui couvrent les pièges connus d'Excel : accents, guillemets, « ; », saut de ligne,
# dates, décimales, numéros de série à zéros en tête et à 15 chiffres, repère « 1-2 »,
# désignations commençant par « - » et par « = », champ vide, apostrophe déjà présente.
LIGNES_EXEMPLE = [
    equipement(
        id="EQ-0001", repere="TR-01", designation="Tour parallèle « Tournelle » HB 575",
        localisation_id="LOC-0002", marque="Tournelle", modele='HB 575 ; version "longue"',
        num_serie="00123", date_mes="2019-03-15", criticite="A", statut="en service",
        heures_fonct_jour="7.5", habilitation_requise="B1V",
        consignation="Couper le sectionneur Q1\nCadenasser\nVérifier l'absence de tension",
        document="tour-tr01.pdf", actif="1"),
    equipement(
        id="EQ-0002", repere="1-2", designation="- Presse hydraulique (à contrôler)",
        localisation_id="LOC-0002", marque="Würth", modele="1/2", num_serie="123456789012345",
        date_mes="2021-11-02", criticite="B", statut="en service", heures_fonct_jour="12.25",
        habilitation_requise="8:30", consignation='Purger l\'accumulateur "avant" toute intervention',
        actif="1"),
    equipement(
        id="EQ-0003", repere="CMP-03", designation="=Compresseur à vis", localisation_id="LOC-0003",
        marque="'Atlas Copco", modele="50%", num_serie="0612345678", date_mes="", criticite="C",
        statut="arrêt", heures_fonct_jour="1.12", actif="1"),
    equipement(
        id="EQ-0004", repere="BR-04", designation='Broche "haute vitesse" ; moteur',
        localisation_id="LOC-0002", parent_id="EQ-0001", marque="Kessler", modele="1e3",
        num_serie="SN-000777", date_mes="2026-01-05", criticite="B", statut="rebut",
        heures_fonct_jour="24", habilitation_requise="H0B0", consignation="+ voir notice",
        actif="0"),
]

# Ligne ajoutée « à la main » dans Excel (ligne 6 de la feuille : en-tête + 4 lignes + 1).
# (ligne, colonne, valeur) : colonnes 1 = id, 2 = repere, 3 = designation, 9 = date_mes, 10 = criticite.
SAISIES_AJOUT = [
    (6, 1, "EQ-0099"),
    (6, 2, "TR-09"),
    (6, 3, "Tour à commande numérique « Ébène »"),
    (6, 9, "15/03/2024"),
    (6, 10, "b"),
]
LIGNE_AJOUTEE_ATTENDUE = equipement(
    id="EQ-0099", repere="TR-09", designation="Tour à commande numérique « Ébène »",
    date_mes="2024-03-15", criticite="B")


def octets_csv(texte, encodage="utf-8-sig"):
    """Texte → octets d'un fichier (UTF-8 avec BOM par défaut)."""
    return texte.encode(encodage)


# ---------------------------------------------------------------------------
# Base : page avec Papa, Schema et Donnees chargés
# ---------------------------------------------------------------------------

class CasCsv(CasNavigateur):
    """Charge les scripts du projet dans une page vide et offre des raccourcis Python."""

    def setUp(self):
        super().setUp()
        charger_scripts(self.page, SCRIPTS)
        self.page.evaluate(AIDE_JS)

    def analyser(self, table, octets):
        return self.page.evaluate(
            "([table, b64]) => Donnees.csv.analyser(table, versOctets(b64))",
            [table, base64.b64encode(octets).decode("ascii")])

    def serialiser(self, table, lignes, inconnues=None, options=None):
        b64 = self.page.evaluate(
            "([table, lignes, inconnues, options]) => "
            "versBase64(Donnees.csv.serialiser(table, lignes, inconnues, options))",
            [table, lignes, inconnues, options])
        return base64.b64decode(b64)

    def problemes_de_type(self, resultat, type_probleme):
        return [p for p in resultat["problemes"] if p["type"] == type_probleme]

    def problemes_hors_colonnes_v2(self, resultat):
        """Problèmes d'une lecture d'equipements écrit avant la version 2 du format : vérifie que
        chaque colonne v2 absente donne exactement une « info » de type colonne (ARCHITECTURE.md
        §14.1), puis renvoie tous les AUTRES problèmes."""
        v2 = [p for p in resultat["problemes"] if p["type"] == "colonne" and p["champ"] in COLONNES_V2_EQUIPEMENTS]
        self.assertEqual([(p["gravite"], p["champ"]) for p in v2], [("info", nom) for nom in COLONNES_V2_EQUIPEMENTS])
        return [p for p in resultat["problemes"] if p not in v2]


# ---------------------------------------------------------------------------
# 1. Erreurs, nombres, dates (sections 1 et 2 de donnees.js)
# ---------------------------------------------------------------------------

class TestErreursEtNormalisation(CasCsv):

    def test_erreurs(self):
        resultat = self.page.evaluate("""() => {
          const conflit = new Donnees.ErreurConflit('périmé', 'v7');
          const validation = new Donnees.ErreurValidation('refusé');
          const stockage = new Donnees.ErreurStockage('fichier ouvert dans Excel');
          return [conflit, validation, stockage].map((e) => [e instanceof Error, e.name, e.message])
            .concat([[conflit.versionActuelle, new Donnees.ErreurConflit('x').versionActuelle]]);
        }""")
        self.assertEqual(resultat[0], [True, "ErreurConflit", "périmé"])
        self.assertEqual(resultat[1], [True, "ErreurValidation", "refusé"])
        self.assertEqual(resultat[2], [True, "ErreurStockage", "fichier ouvert dans Excel"])
        self.assertEqual(resultat[3], ["v7", None])

    def test_nombre(self):
        resultat = self.page.evaluate(
            "(valeurs) => valeurs.map((v) => Donnees.nombre(v))",
            ["7.5", "7,5", "", None, "abc", "-2", "1 234,5", 3])
        self.assertEqual(resultat, [7.5, 7.5, None, None, None, -2, 1234.5, 3])

    def test_aujourdhui_et_maintenant(self):
        resultat = self.page.evaluate("""() => {
          const d = new Date();
          const deux = (n) => String(n).padStart(2, '0');
          return [Donnees.aujourdhui(), Donnees.maintenant(),
                  d.getFullYear() + '-' + deux(d.getMonth() + 1) + '-' + deux(d.getDate())];
        }""")
        aujourdhui, maintenant, attendu = resultat
        self.assertRegex(aujourdhui, r"^\d{4}-\d{2}-\d{2}$")
        self.assertRegex(maintenant, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
        self.assertEqual(aujourdhui, attendu)

    def test_fonctions_de_normalisation(self):
        resultat = self.page.evaluate("""() => {
          const n = Donnees.normaliser;
          return {
            date: n.date('5/3/2024'), dateKo: n.date('31/02/2024'),
            dateHeure: n.dateHeure('15/03/2026 8:30'), decimal: n.decimal('7,5'),
            entier: n.entier('12'), booleen: n.booleen('Oui'),
            choix: n.choix('arret', ['en service', 'arrêt', 'rebut']), vide: n.choix('', ['A']),
          };
        }""")
        self.assertEqual(resultat["date"], {"valeur": "2024-03-05", "ok": True})
        self.assertEqual(resultat["dateKo"], {"valeur": "31/02/2024", "ok": False})
        self.assertEqual(resultat["dateHeure"], {"valeur": "2026-03-15 08:30", "ok": True})
        self.assertEqual(resultat["decimal"], {"valeur": "7.5", "ok": True})
        self.assertEqual(resultat["entier"], {"valeur": "12", "ok": True})
        self.assertEqual(resultat["booleen"], {"valeur": "1", "ok": True})
        self.assertEqual(resultat["choix"], {"valeur": "arrêt", "ok": True})
        self.assertEqual(resultat["vide"], {"valeur": "", "ok": True})


# ---------------------------------------------------------------------------
# (a) Protection par apostrophe
# ---------------------------------------------------------------------------

VALEURS_PIEGEES = [
    "", " ", "  ", "abc", "'", "''", "'abc", "''abc", "'00123", "' espace", "x'y",
    "00123", "0", "123456789012345", "0612345678", "1e3", "1E+03", "1,23457E+14",
    "7.5", "7,5", "12.25", "1.12", "-3", "+33 6 12 34 56 78",
    "=1+1", "=SOMME(A1:A2)", "+", "-", "@", "- remplacer joint", "-- x", "@utilisateur",
    "\tTabulation", "\rRetour chariot", "\nSaut de ligne en tête",
    "1/2", "01-12", "2026-10", "2019-03-15", "15/03/2019", "15.03.2019", "2026-03-15 08:30",
    "8:30", "08:30:15", "50%", "50 %", "12,5%", " 00123", "00123 ", " 12 ",
    "a;b", 'guillemet " seul', '""', "ligne1\nligne2", "ligne1\r\nligne2", "fin\r",
    "é à ü « » œ €", "Tour à commande numérique « Ébène »", "'=1+1", "'- remplacer joint",
    "'8:30", "'50%", "1-2", "TR-01", "#NOM?", "1 234,5", "1" + INSECABLE + "234,5",
    "0x1F", "Infinity", "NaN", "true", "null", "undefined", chr(0x1D11E) + " clé de sol",
    INSECABLE + "insécable en tête",
]


def chaines_aleatoires(nombre=500, graine=20261019):
    """Chaînes aléatoires (graine fixe) faites des caractères qui piègent Excel et le CSV."""
    generateur = random.Random(graine)
    alphabet = list("0123456789 .,;:/-+=@'\"%eEabxyzé«»\t\r\n") + [INSECABLE]
    debuts = ["", "", "", "'", "''", "=", "-", " ", "0", "+"]
    resultat = []
    for _ in range(nombre):
        longueur = generateur.randint(0, 12)
        corps = "".join(generateur.choice(alphabet) for _ in range(longueur))
        resultat.append(generateur.choice(debuts) + corps)
    return resultat


class TestProtectionApostrophe(CasCsv):

    CHAMPS_ESSAYES = """{
      protege: Schema.champ('equipements', 'num_serie'),
      texte: Schema.champ('equipements', 'designation'),
      texteLong: Schema.champ('equipements', 'consignation'),
    }"""

    def test_champs_essayes(self):
        resultat = self.page.evaluate("() => { const c = " + self.CHAMPS_ESSAYES + ";"
                                      " return [c.protege.type, c.protege.protege === true,"
                                      " c.texte.type, c.texte.protege === true, c.texteLong.type]; }")
        self.assertEqual(resultat, ["texte", True, "texte", False, "texte_long"])

    def test_aller_retour_exact(self):
        valeurs = VALEURS_PIEGEES + chaines_aleatoires()
        self.assertGreaterEqual(len(VALEURS_PIEGEES), 60)
        echecs = self.page.evaluate("""(valeurs) => {
          const champs = """ + self.CHAMPS_ESSAYES + """;
          const echecs = [];
          for (const [nom, champ] of Object.entries(champs)) {
            for (const valeur of valeurs) {
              const ecrite = Donnees.csv.ecrireValeur(champ, valeur);
              const relue = Donnees.csv.relireValeur(champ, ecrite);
              if (relue !== valeur) { echecs.push([nom, valeur, ecrite, relue]); }
            }
          }
          return echecs;
        }""", valeurs)
        self.assertEqual(echecs, [], "valeurs qui ne reviennent pas à l'identique")

    def test_valeurs_ecrites(self):
        cas = [
            # (table, champ, valeur, valeur écrite attendue)
            ("equipements", "designation", "abc", "abc"),
            ("equipements", "designation", "", ""),
            ("equipements", "designation", "00123", "'00123"),
            ("equipements", "designation", "- remplacer joint", "'- remplacer joint"),
            ("equipements", "designation", "=1+1", "'=1+1"),
            ("equipements", "designation", "@x", "'@x"),
            ("equipements", "designation", "'abc", "''abc"),
            ("equipements", "designation", "1/2", "'1/2"),
            ("equipements", "designation", "8:30", "'8:30"),
            ("equipements", "designation", "50%", "'50%"),
            ("equipements", "designation", "1e3", "'1e3"),
            ("equipements", "designation", "7.5", "'7.5"),
            ("equipements", "designation", " 12 ", "' 12 "),
            ("equipements", "designation", "Tour 1/2", "Tour 1/2"),
            ("equipements", "designation", "x-1", "x-1"),
            ("equipements", "num_serie", "SN-1", "'SN-1"),
            ("equipements", "num_serie", "", ""),
            ("equipements", "consignation", "-> couper Q1", "'-> couper Q1"),
            ("equipements", "date_mes", "2019-03-15", "2019-03-15"),
            ("equipements", "heures_fonct_jour", "7.5", "7.5"),
            ("equipements", "id", "=EQ", "=EQ"),
            ("equipements", "actif", "1", "1"),
            ("equipements", "criticite", "A", "A"),
        ]
        resultat = self.page.evaluate("""(cas) => cas.map(([table, champ, valeur]) =>
            Donnees.csv.ecrireValeur(Schema.champ(table, champ), valeur))""", cas)
        self.assertEqual(resultat, [attendu for (_, _, _, attendu) in cas])

    def test_aller_retour_par_fichier(self):
        """serialiser puis analyser rend les valeurs (hors espaces de fin, retirés à la lecture)."""
        valeurs = [v for v in VALEURS_PIEGEES + chaines_aleatoires(200)
                   if v.strip(" \t\r" + INSECABLE) != "" and v == v.rstrip(" \t\r")]
        lignes = [equipement(id="EQ-%04d" % (i + 1), designation=v, num_serie=v, consignation=v)
                  for i, v in enumerate(valeurs)]
        resultat = self.analyser("equipements", self.serialiser("equipements", lignes))
        self.assertEqual(self.problemes_de_type(resultat, "valeur"), [])
        self.assertEqual(len(resultat["lignes"]), len(lignes))
        for attendue, lue in zip(lignes, resultat["lignes"]):
            self.assertEqual(lue["designation"], attendue["designation"])
            self.assertEqual(lue["num_serie"], attendue["num_serie"])
            self.assertEqual(lue["consignation"], attendue["consignation"])


# ---------------------------------------------------------------------------
# (b) Octets écrits par serialiser
# ---------------------------------------------------------------------------

class TestSerialiser(CasCsv):

    def test_octets_exacts(self):
        octets = self.serialiser("equipements", LIGNES_EXEMPLE[:2])
        entete = ";".join(CHAMPS_EQUIPEMENTS)
        # (dernière cellule vide : valeur_remplacement, colonne de la version 2 du format)
        ligne1 = ("EQ-0001;'TR-01;Tour parallèle « Tournelle » HB 575;LOC-0002;;Tournelle;"
                  "\"HB 575 ; version \"\"longue\"\"\";'00123;2019-03-15;A;en service;7.5;B1V;"
                  "\"Couper le sectionneur Q1\nCadenasser\nVérifier l'absence de tension\";tour-tr01.pdf;1;")
        ligne2 = ("EQ-0002;'1-2;'- Presse hydraulique (à contrôler);LOC-0002;;Würth;'1/2;'123456789012345;"
                  "2021-11-02;B;en service;12.25;'8:30;"
                  "\"Purger l'accumulateur \"\"avant\"\" toute intervention\";;1;")
        attendu = BOM + (entete + "\r\n" + ligne1 + "\r\n" + ligne2 + "\r\n").encode("utf-8")
        self.assertEqual(octets, attendu)

    def test_entetes_dans_l_ordre_du_schema(self):
        for table in ["equipements", "ordres_travail", "journal", "parametres"]:
            noms = self.page.evaluate("(t) => Schema.table(t).champs.map((c) => c.nom)", table)
            octets = self.serialiser(table, [])
            self.assertTrue(octets.startswith(BOM))
            self.assertEqual(octets[3:].decode("utf-8"), ";".join(noms) + "\r\n")

    def test_colonnes_inconnues_a_la_fin_et_guillemets(self):
        ligne = equipement(id="EQ-0001", designation=" espace devant", marque="fin ",
                           actif=1)  # nombre : écrit comme chaîne
        ligne["Commentaire atelier"] = 'dit "urgent"'
        ligne["Code SAP"] = " 42 "
        octets = self.serialiser("equipements", [ligne], ["Commentaire atelier", "Code SAP"])
        lignes_texte = octets[3:].decode("utf-8").split("\r\n")
        self.assertEqual(lignes_texte[0], ";".join(CHAMPS_EQUIPEMENTS) + ";Commentaire atelier;Code SAP")
        cellules = lignes_texte[1].split(";")
        self.assertEqual(cellules[2], '" espace devant"')
        self.assertEqual(cellules[5], '"fin "')
        self.assertEqual(cellules[15], "1")
        self.assertEqual(cellules[16], "")       # valeur_remplacement (version 2 du format), vide
        self.assertEqual(cellules[17:], ['"dit ""urgent"""', '" 42 "'])
        self.assertEqual(lignes_texte[2], "")   # le fichier se termine par CRLF

    def test_sans_bom_et_champs_manquants(self):
        octets = self.serialiser("journal", [{"id": "J-1", "action": "création"}], None, {"bom": False})
        self.assertFalse(octets.startswith(BOM))
        self.assertEqual(octets.decode("utf-8"),
                         "id;date_heure;poste;profil;table;id_ligne;action\r\nJ-1;;;;;;création\r\n")

    def test_table_inconnue(self):
        message = self.page.evaluate(
            "() => { try { Donnees.csv.serialiser('nimporte', []); return 'aucune erreur'; }"
            " catch (e) { return e.message; } }")
        self.assertIn("nimporte", message)


# ---------------------------------------------------------------------------
# (c) Lecture tolérante (ARCHITECTURE.md §3.3)
# ---------------------------------------------------------------------------

class TestLectureTolerante(CasCsv):

    def verifier_colonne(self, table, champ, cas_lisibles, cas_illisibles):
        """Fichier « id;<champ> » : vérifie les valeurs normalisées et les problèmes « valeur »."""
        tous = list(cas_lisibles) + [(brut, brut.strip()) for brut in cas_illisibles]
        texte = "id;%s\r\n" % champ + "".join(
            "X-%d;%s\r\n" % (i + 1, brut) for i, (brut, _) in enumerate(tous))
        resultat = self.analyser(table, octets_csv(texte))
        lues = [ligne[champ] for ligne in resultat["lignes"]]
        self.assertEqual(lues, [attendu for (_, attendu) in tous])
        problemes = self.problemes_de_type(resultat, "valeur")
        premier_illisible = len(cas_lisibles)
        self.assertEqual(
            [(p["gravite"], p["ligne"], p["id"], p["champ"], p["valeur"]) for p in problemes],
            [("erreur", premier_illisible + i + 2, "X-%d" % (premier_illisible + i + 1), champ, brut.strip())
             for i, brut in enumerate(cas_illisibles)])
        for probleme in problemes:
            self.assertIn("ligne %d" % probleme["ligne"], probleme["message"])
            self.assertIn(probleme["valeur"], probleme["message"])
        return resultat

    def test_dates(self):
        resultat = self.verifier_colonne("equipements", "date_mes", [
            ("2024-03-15", "2024-03-15"), ("15/03/2024", "2024-03-15"), ("5/3/2024", "2024-03-05"),
            ("15-03-2024", "2024-03-15"), ("15.03.2024", "2024-03-15"), (" 15/03/2024 ", "2024-03-15"),
            ("29/02/2024", "2024-02-29"), ("", ""),
        ], ["31/02/2024", "demain", "2024-13-01", "15/03/24"])
        self.assertIn("Date de mise en service", self.problemes_de_type(resultat, "valeur")[0]["message"])

    def test_dates_heures(self):
        self.verifier_colonne("demandes", "date_heure", [
            ("2026-03-15 08:30", "2026-03-15 08:30"), ("15/03/2026 08:30", "2026-03-15 08:30"),
            ("15/03/2026 8:30:59", "2026-03-15 08:30"), ("2026-03-15T08:30", "2026-03-15 08:30"),
            ("2026-03-15T08:30:00", "2026-03-15 08:30"), ("15/03/2026", "2026-03-15 00:00"),
            ("", ""),
        ], ["15/03/2026 25:00", "15/03/2026 08h30", "hier soir"])

    def test_decimales(self):
        self.verifier_colonne("equipements", "heures_fonct_jour", [
            ("7,5", "7.5"), ("7.5", "7.5"), ("1 234,50", "1234.50"), ("1" + INSECABLE + "234,5", "1234.5"),
            ("-2,25", "-2.25"), (",5", "0.5"), ("24", "24"), (" 8 ", "8"), ("", ""),
        ], ["7,5 h", "1,00E+03", "1.234,5", "huit"])

    def test_entiers(self):
        self.verifier_colonne("ot_operations", "ordre", [
            ("3", "3"), (" 12 ", "12"), ("12,0", "12"), ("1 000", "1000"), ("", ""),
        ], ["2,5", "deux"])

    def test_booleens(self):
        self.verifier_colonne("equipements", "actif", [
            ("1", "1"), ("0", "0"), ("VRAI", "1"), ("faux", "0"), ("Oui", "1"), ("NON", "0"),
            ("true", "1"), ("False", "0"), ("x", "1"), ("X", "1"), ("", ""),
        ], ["peut-être", "2"])

    def test_choix(self):
        resultat = self.verifier_colonne("equipements", "criticite", [
            ("A", "A"), ("b", "B"), (" c ", "C"), ("", ""),
        ], ["Z", "AB"])
        self.assertIn("A, B, C", self.problemes_de_type(resultat, "valeur")[0]["message"])
        self.verifier_colonne("equipements", "statut", [
            ("en service", "en service"), ("En Service", "en service"), ("ARRET", "arrêt"),
            ("Arrêt", "arrêt"), ("Rebut", "rebut"), ("en  service", "en service"),
        ], ["hors service"])
        self.verifier_colonne("ordres_travail", "statut", [
            ("cloture techniquement", "Clôturé techniquement"), ("EN ATTENTE", "En attente"),
        ], ["Clos"])

    def test_colonnes_dans_le_desordre_et_entetes_approximatifs(self):
        texte = ("Désignation;Statut;ID;Repère;Date MES;HEURES_FONCT_JOUR\r\n"
                 "Tour;Arrêt;EQ-0007;'TR-07;15/03/2024;7,5\r\n")
        resultat = self.analyser("equipements", octets_csv(texte))
        self.assertEqual(resultat["colonnesInconnues"], [])
        ligne = resultat["lignes"][0]
        self.assertEqual(list(ligne.keys()), CHAMPS_EQUIPEMENTS)   # tous les champs, ordre du schéma
        self.assertEqual(
            (ligne["id"], ligne["designation"], ligne["statut"], ligne["repere"], ligne["date_mes"],
             ligne["heures_fonct_jour"]),
            ("EQ-0007", "Tour", "arrêt", "TR-07", "2024-03-15", "7.5"))
        # colonnes absentes : valeur par défaut du schéma, sinon chaîne vide
        self.assertEqual((ligne["criticite"], ligne["actif"], ligne["marque"]), ("B", "1", ""))

    def test_colonne_absente(self):
        resultat = self.analyser("equipements", octets_csv("id;repere\r\nEQ-0001;'TR-01\r\n"))
        ligne = resultat["lignes"][0]
        self.assertEqual((ligne["criticite"], ligne["statut"], ligne["actif"], ligne["heures_fonct_jour"]),
                         ("B", "en service", "1", ""))
        # Les 14 colonnes du brief absentes sont « attention » ; la colonne de la version 2 du
        # format (valeur_remplacement) n'est qu'une « info » (ARCHITECTURE.md §14.1).
        problemes = [p for p in self.problemes_de_type(resultat, "colonne")
                     if p["champ"] not in COLONNES_V2_EQUIPEMENTS]
        self.assertEqual(len(problemes), 14)
        self.assertTrue(all(p["gravite"] == "attention" and p["ligne"] == 1 for p in problemes))
        self.assertEqual(self.problemes_hors_colonnes_v2(resultat), problemes)
        criticite = [p for p in problemes if p["champ"] == "criticite"][0]
        self.assertIn("« B »", criticite["message"])
        self.assertIn("Criticité", criticite["message"])

    def test_colonnes_inconnues_conservees_puis_reecrites_a_la_fin(self):
        texte = ("id;Commentaire atelier;repere;Code SAP\r\n"
                 "EQ-0001;À revoir;'TR-01;SAP-9\r\n"
                 "EQ-0002;;'TR-02;\r\n")
        resultat = self.analyser("equipements", octets_csv(texte))
        self.assertEqual(resultat["colonnesInconnues"], ["Commentaire atelier", "Code SAP"])
        self.assertEqual(resultat["lignes"][0]["Commentaire atelier"], "À revoir")
        self.assertEqual(resultat["lignes"][0]["Code SAP"], "SAP-9")
        self.assertEqual(resultat["lignes"][1]["Commentaire atelier"], "")
        infos = [p for p in self.problemes_hors_colonnes_v2(resultat)
                 if p["type"] == "colonne" and p["gravite"] == "info"]
        self.assertEqual([p["champ"] for p in infos], ["Commentaire atelier", "Code SAP"])

        octets = self.serialiser("equipements", resultat["lignes"], resultat["colonnesInconnues"])
        lignes_texte = octets[3:].decode("utf-8").split("\r\n")
        self.assertTrue(lignes_texte[0].endswith(";actif;valeur_remplacement;Commentaire atelier;Code SAP"))
        self.assertTrue(lignes_texte[1].startswith("EQ-0001;'TR-01;"))
        self.assertTrue(lignes_texte[1].endswith(";À revoir;SAP-9"))
        relu = self.analyser("equipements", octets)
        self.assertEqual(relu["lignes"], resultat["lignes"])
        self.assertEqual(relu["colonnesInconnues"], resultat["colonnesInconnues"])

    def test_separateur_virgule(self):
        texte = 'id,repere,designation,heures_fonct_jour\r\nEQ-0001,TR-01,"Tour, parallèle","7,5"\r\n'
        resultat = self.analyser("equipements", octets_csv(texte))
        self.assertEqual(resultat["separateur"], ",")
        ligne = resultat["lignes"][0]
        self.assertEqual((ligne["id"], ligne["repere"], ligne["designation"], ligne["heures_fonct_jour"]),
                         ("EQ-0001", "TR-01", "Tour, parallèle", "7.5"))
        self.assertEqual(self.analyser("equipements", octets_csv("id;designation\r\nEQ-1;a, b\r\n"))["separateur"], ";")

    def test_windows_1252(self):
        texte = "id;designation;statut\r\nEQ-0001;Tour à commande « Ébène » œ €;arrêt\r\n"
        resultat = self.analyser("equipements", octets_csv(texte, "cp1252"))
        self.assertEqual(resultat["encodage"], "windows-1252")
        self.assertEqual(resultat["lignes"][0]["designation"], "Tour à commande « Ébène » œ €")
        self.assertEqual(resultat["lignes"][0]["statut"], "arrêt")
        encodage = self.problemes_de_type(resultat, "encodage")
        self.assertEqual(len(encodage), 1)
        self.assertEqual(encodage[0]["gravite"], "info")
        # le même texte en UTF-8 sans BOM est lu en UTF-8, sans problème d'encodage
        sans_bom = self.analyser("equipements", octets_csv(texte, "utf-8"))
        self.assertEqual(sans_bom["encodage"], "utf-8")
        self.assertEqual(self.problemes_de_type(sans_bom, "encodage"), [])
        self.assertEqual(sans_bom["lignes"], resultat["lignes"])

    def test_lignes_vides_espaces_de_fin_et_numeros_de_ligne(self):
        texte = ("id;designation;date_mes\r\n"        # 1
                 "\r\n"                                # 2
                 'EQ-1;"Ligne A\r\n'                   # 3
                 'Ligne B";2024-03-15\r\n'             # 4
                 ";;\r\n"                              # 5
                 "   \r\n"                             # 6
                 "EQ-2;Fraiseuse   ;31/02/2024\r\n"    # 7
                 "\r\n"                                # 8
                 "EQ-3;Perceuse\t;\r\n")               # 9
        resultat = self.analyser("equipements", octets_csv(texte))
        self.assertEqual([l["id"] for l in resultat["lignes"]], ["EQ-1", "EQ-2", "EQ-3"])
        self.assertEqual(resultat["lignes"][0]["designation"], "Ligne A\r\nLigne B")
        self.assertEqual(resultat["lignes"][1]["designation"], "Fraiseuse")
        self.assertEqual(resultat["lignes"][2]["designation"], "Perceuse")
        problemes = self.problemes_de_type(resultat, "valeur")
        self.assertEqual([(p["ligne"], p["id"]) for p in problemes], [(7, "EQ-2")])

    def test_retours_chariot_parasites(self):
        texte = "id;designation\nEQ-1;Tour\r\nEQ-2;Fraiseuse\n"
        resultat = self.analyser("equipements", octets_csv(texte))
        self.assertEqual([l["designation"] for l in resultat["lignes"]], ["Tour", "Fraiseuse"])

    def test_notation_scientifique_et_formule_abimees_par_excel(self):
        texte = "id;num_serie;designation\r\nEQ-1;1,23457E+14;Tour\r\nEQ-2;'00123;#NOM?\r\n"
        resultat = self.analyser("equipements", octets_csv(texte))
        self.assertEqual(resultat["lignes"][0]["num_serie"], "1,23457E+14")   # conservée telle quelle
        self.assertEqual(resultat["lignes"][1]["num_serie"], "00123")
        problemes = self.problemes_de_type(resultat, "excel")
        self.assertEqual([(p["gravite"], p["ligne"], p["id"], p["champ"]) for p in problemes],
                         [("attention", 2, "EQ-1", "num_serie"), ("attention", 3, "EQ-2", "designation")])
        self.assertIn("Excel", problemes[0]["message"])

    def test_valeurs_en_trop_et_lignes_courtes(self):
        texte = "id;repere;designation\r\nEQ-1;'R1;Tour;surplus\r\nEQ-2\r\n"
        resultat = self.analyser("equipements", octets_csv(texte))
        self.assertEqual(resultat["lignes"][1]["designation"], "")
        en_trop = [p for p in self.problemes_de_type(resultat, "colonne") if p["ligne"] == 2]
        self.assertEqual(len(en_trop), 1)
        self.assertEqual(en_trop[0]["valeur"], "surplus")

    def test_guillemet_non_ferme(self):
        texte = 'id;designation\r\nEQ-1;"Tour\r\nEQ-2;Fraiseuse\r\n'
        resultat = self.analyser("equipements", octets_csv(texte))
        erreurs = [p for p in self.problemes_de_type(resultat, "valeur") if p["gravite"] == "erreur"]
        self.assertGreaterEqual(len(erreurs), 1)
        self.assertIn("guillemet", erreurs[0]["message"])

    def test_fichier_vide(self):
        for octets in [b"", BOM, BOM + b"\r\n"]:
            resultat = self.analyser("equipements", octets)
            self.assertEqual((resultat["lignes"], resultat["problemes"]), ([], []))

    def test_forme_des_problemes(self):
        resultat = self.analyser("equipements", octets_csv("id;date_mes;Inconnue\r\nEQ-1;jamais;x\r\n"))
        for probleme in resultat["problemes"]:
            self.assertEqual(sorted(probleme.keys()),
                             sorted(["gravite", "type", "table", "ligne", "id", "champ", "valeur", "message"]))
            self.assertIn(probleme["gravite"], ["erreur", "attention", "info"])
            self.assertEqual(probleme["table"], "equipements")
            self.assertTrue(probleme["message"])


# ---------------------------------------------------------------------------
# (d) Fichiers réenregistrés par le vrai Excel (tests/fixtures/excel/)
# ---------------------------------------------------------------------------

def lire_fixture(nom):
    return (DOSSIER_FIXTURES / nom).read_bytes()


def avec_colonnes_v2_vides(octets_v1):
    """Octets d'un CSV equipements écrit avant la version 2 du format → octets attendus de
    serialiser aujourd'hui : mêmes cellules, colonnes v2 ajoutées en fin (vides). Valable quand
    CRLF ne sert qu'à terminer les enregistrements (les sauts de ligne internes sont des LF)."""
    lignes = octets_v1[len(BOM):].split(b"\r\n")
    assert lignes[-1] == b"", "le fichier doit finir par CRLF"
    entete = lignes[0] + "".join(";" + nom for nom in COLONNES_V2_EQUIPEMENTS).encode("utf-8")
    enregistrements = [ligne + b";" * len(COLONNES_V2_EQUIPEMENTS) for ligne in lignes[1:-1]]
    return BOM + b"\r\n".join([entete] + enregistrements) + b"\r\n"


class TestFixturesExcel(CasCsv):
    """Les fichiers de tests/fixtures/excel/ ont été produits au lot 1 (format v1, sans la colonne
    valeur_remplacement) par le vrai Excel : ils ne peuvent pas être régénérés sans lui. Leur
    lecture ne doit signaler, en plus du lot 1, que l'« info » de la colonne v2 absente."""

    def test_source_ecrite_par_serialiser(self):
        source = lire_fixture("source.csv")
        self.assertEqual(source.count(b"\r\n"), 1 + len(LIGNES_EXEMPLE))   # CRLF = fin d'enregistrement seulement
        self.assertEqual(avec_colonnes_v2_vides(source), self.serialiser("equipements", LIGNES_EXEMPLE))
        resultat = self.analyser("equipements", source)
        self.assertEqual(resultat["lignes"], LIGNES_EXEMPLE)
        self.assertEqual(self.problemes_hors_colonnes_v2(resultat), [])

    def test_excel_utf8(self):
        octets = lire_fixture("excel-utf8.csv")
        self.assertTrue(octets.startswith(BOM))
        self.assertIn("15/03/2019".encode("ascii"), octets)   # preuve qu'Excel a bien réécrit le fichier
        resultat = self.analyser("equipements", octets)
        self.assertEqual(resultat["encodage"], "utf-8")
        self.assertEqual(resultat["lignes"], self.analyser("equipements", lire_fixture("source.csv"))["lignes"])
        self.assertEqual(self.problemes_hors_colonnes_v2(resultat), [])

    def test_excel_ansi(self):
        octets = lire_fixture("excel-ansi.csv")
        self.assertFalse(octets.startswith(BOM))
        self.assertIn("« Tournelle »".encode("cp1252"), octets)
        resultat = self.analyser("equipements", octets)
        self.assertEqual(resultat["encodage"], "windows-1252")
        self.assertEqual(resultat["lignes"], self.analyser("equipements", lire_fixture("source.csv"))["lignes"])
        self.assertEqual([p["type"] for p in self.problemes_hors_colonnes_v2(resultat)], ["encodage"])

    def test_excel_ligne_ajoutee_a_la_main(self):
        resultat = self.analyser("equipements", lire_fixture("excel-ajout.csv"))
        self.assertEqual(resultat["lignes"][:4], LIGNES_EXEMPLE)
        self.assertEqual(resultat["lignes"][4], LIGNE_AJOUTEE_ATTENDUE)
        self.assertEqual(self.problemes_hors_colonnes_v2(resultat), [])


# ---------------------------------------------------------------------------
# (e) Aller-retour Excel à la volée
# ---------------------------------------------------------------------------

class TestExcelReel(CasCsv):

    def setUp(self):
        if not excel.excel_reel_demande():
            self.skipTest("Excel réel non demandé : définir PREVO_TEST_EXCEL=1")
        if not excel.excel_disponible():
            self.skipTest("Microsoft Excel n'est pas disponible sur ce poste")
        super().setUp()

    def test_aller_retour_reel(self):
        with tempfile.TemporaryDirectory(prefix="prevo-test-excel-") as dossier:
            dossier = Path(dossier)
            source = dossier / "equipements.csv"
            source.write_bytes(self.serialiser("equipements", LIGNES_EXEMPLE))
            cas = [
                ("utf8", None, "utf-8", LIGNES_EXEMPLE),
                ("ansi", None, "windows-1252", LIGNES_EXEMPLE),
                ("utf8", SAISIES_AJOUT, "utf-8", LIGNES_EXEMPLE + [LIGNE_AJOUTEE_ATTENDUE]),
            ]
            for numero, (format_excel, saisies, encodage, attendues) in enumerate(cas):
                with self.subTest(format=format_excel, saisies=bool(saisies)):
                    sortie = dossier / ("sortie-%d.csv" % numero)
                    excel.aller_retour_excel(source, sortie, format_excel, saisies)
                    resultat = self.analyser("equipements", sortie.read_bytes())
                    self.assertEqual(resultat["encodage"], encodage)
                    self.assertEqual(resultat["lignes"], attendues)
                    self.assertEqual([p for p in resultat["problemes"] if p["type"] != "encodage"], [])


# ---------------------------------------------------------------------------
# (f) Performance
# ---------------------------------------------------------------------------

class TestPerformance(CasCsv):

    def test_5000_lignes_30_colonnes_en_moins_de_300_ms(self):
        mesure = self.page.evaluate("""() => {
          const champs = Schema.table('ordres_travail').champs;
          const lignes = [];
          for (let i = 0; i < 5000; i += 1) {
            const ligne = {};
            for (const champ of champs) {
              let valeur = '';
              switch (champ.type) {
                case 'id': valeur = 'OT-2026-' + String(i + 1).padStart(4, '0'); break;
                case 'texte': valeur = 'Remplacer le roulement n°' + i + ' côté « moteur »'; break;
                case 'texte_long': valeur = i % 3 ? 'Ligne 1 ; "consigne"\\nLigne 2 ' + i : ''; break;
                case 'decimal': valeur = i % 2 ? '12.5' : '3'; break;
                case 'entier': valeur = String(i); break;
                case 'date': valeur = i % 2 ? '2026-03-15' : '15/03/2026'; break;
                case 'date_heure': valeur = i % 2 ? '2026-03-15 08:30' : '15/03/2026 08:30'; break;
                case 'booleen': valeur = i % 2 ? '1' : 'oui'; break;
                case 'choix': valeur = champ.valeurs[i % champ.valeurs.length]; break;
                case 'ref': valeur = 'EQ-' + String(i % 300).padStart(4, '0'); break;
                default: valeur = '';
              }
              ligne[champ.nom] = valeur;
            }
            lignes.push(ligne);
          }
          const octets = Donnees.csv.serialiser('ordres_travail', lignes);
          Donnees.csv.analyser('ordres_travail', octets);          // échauffement
          const durees = [];
          let resultat = null;
          for (let essai = 0; essai < 3; essai += 1) {
            const debut = performance.now();
            resultat = Donnees.csv.analyser('ordres_travail', octets);
            durees.push(performance.now() - debut);
          }
          durees.sort((a, b) => a - b);
          return { colonnes: champs.length, lignes: resultat.lignes.length,
                   problemes: resultat.problemes.length, mediane: durees[1], durees: durees,
                   octets: octets.length };
        }""")
        # 30 colonnes du brief + anomalie_constatee (version 2 du format) : seuil inchangé.
        self.assertEqual(mesure["colonnes"], 31)
        self.assertEqual(mesure["lignes"], 5000)
        self.assertEqual(mesure["problemes"], 0)
        print("\n    analyse de 5 000 lignes × %d colonnes (%d Ko) : médiane %.0f ms (essais : %s)"
              % (mesure["colonnes"], mesure["octets"] // 1024, mesure["mediane"],
                 ", ".join("%.0f" % d for d in mesure["durees"])), file=sys.stderr)
        self.assertLess(mesure["mediane"], 300)


# ---------------------------------------------------------------------------
# Régénération des fichiers de tests/fixtures/excel/ (Excel requis)
# ---------------------------------------------------------------------------

def generer_fixtures():
    """Écrit source.csv avec Donnees.csv.serialiser, puis le fait réenregistrer par le vrai Excel."""
    from playwright.sync_api import sync_playwright

    if not excel.excel_disponible():
        raise SystemExit("Microsoft Excel n'est pas disponible : impossible de produire les fichiers.")
    DOSSIER_FIXTURES.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        navigateur = playwright.chromium.launch(headless=True)
        try:
            page = navigateur.new_page()
            charger_scripts(page, SCRIPTS)
            page.evaluate(AIDE_JS)
            b64 = page.evaluate(
                "(lignes) => versBase64(Donnees.csv.serialiser('equipements', lignes))", LIGNES_EXEMPLE)
        finally:
            navigateur.close()
    source = DOSSIER_FIXTURES / "source.csv"
    source.write_bytes(base64.b64decode(b64))
    excel.aller_retour_excel(source, DOSSIER_FIXTURES / "excel-utf8.csv", "utf8")
    excel.aller_retour_excel(source, DOSSIER_FIXTURES / "excel-ansi.csv", "ansi")
    excel.aller_retour_excel(source, DOSSIER_FIXTURES / "excel-ajout.csv", "utf8", SAISIES_AJOUT)

    lisezmoi = """Fichiers de test produits par le vrai Microsoft Excel (tâche T05)
================================================================

Produits le {date} sur un poste Windows avec Excel {version} en français (fr-FR :
séparateur de liste « ; », virgule décimale), par la commande :

    py tests/test_csv.py --generer-fixtures

- source.csv      : 4 lignes de la table equipements écrites par Donnees.csv.serialiser
                    (accents, guillemets, « ; », saut de ligne, dates, décimales, numéros de
                    série à zéros en tête et à 15 chiffres, repère 1-2, désignations commençant
                    par « - » et par « = », champ vide, apostrophe déjà présente).
- excel-utf8.csv  : source.csv ouvert dans Excel (Local:=True) puis « Enregistrer sous »
                    CSV UTF-8 (format 62).
- excel-ansi.csv  : même chose, « Enregistrer sous » CSV simple (format 6, Windows-1252 sans BOM).
- excel-ajout.csv : source.csv ouvert dans Excel, une ligne saisie en ligne 6 (EQ-0099, TR-09,
                    « Tour à commande numérique « Ébène » », date 15/03/2024, criticité « b »),
                    puis CSV UTF-8.

Excel est piloté par VBScript (tests/excel.py). Ces fichiers sont gardés dans le dépôt pour que
tests/test_csv.py vérifie la lecture même sur un poste sans Excel. Ne pas les modifier à la main.
""".format(date=datetime.date.today().strftime("%d/%m/%Y"), version=excel.version_excel() or "?")
    (DOSSIER_FIXTURES / "LISEZMOI.txt").write_text(lisezmoi, encoding="utf-8", newline="\r\n")
    print("Fichiers écrits dans", DOSSIER_FIXTURES)


if __name__ == "__main__":
    if "--generer-fixtures" in sys.argv:
        generer_fixtures()
    else:
        unittest.main()
