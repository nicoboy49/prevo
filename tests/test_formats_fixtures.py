"""Jeux de fichiers d'exemple des formats de données (T182) : tests/fixtures/formats/.

Couvre : chaque jeu se matérialise ; version_schema et nombre de tables attendus (plus-recent : format 5 simulé) ;
12 enregistrements au plus par table ; BOM présent ou absent selon le jeu ; données fictives ; les jeux de la 2.2
(T378) : f3-v2.1.0 et reserves-a-reprendre lus au format 3 par le serveur (format_du_fichier, version_de_base ; côté
navigateur : tests/test_formats_js.py), controles_reglementaires.csv de reserves-a-reprendre écrit comme Prévo
l'écrit, réserves attendues (règle D183 de CONCEPTION-L1 §3.2, recopiée ici) égales à celles de LISEZMOI.md ; et, si
git et les étiquettes v1.1.0, v1.2.0 et v2.1.0 sont là, le générateur rejoué redonne exactement les mêmes octets.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_formats_fixtures.py" -v
"""
import base64
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jeux_formats import DOSSIER_JEUX, JEUX, copier_jeu, lire_variante

RACINE = Path(__file__).resolve().parent.parent
GENERATEUR = RACINE / "outils" / "generer_fixtures_formats.py"
LISEZMOI = DOSSIER_JEUX / "LISEZMOI.md"
ETIQUETTES = ("v1.1.0", "v1.2.0", "v2.1.0")
BOM = b"\xef\xbb\xbf"
MAX_ENREGISTREMENTS = 12
# Même règle que tests/test_audit_divers.py (G3) : aucun numéro français hors des plages fictives de l'ARCEP
MOTIF_TELEPHONE = re.compile(r"(?<![\w.,])(?:(?:\+|00)33[ .-]?(?:\(0\)[ .-]?)?|0)([1-9])([ .-]?)(\d{2})\2(\d{2})\2(\d{2})\2(\d{2})(?!\w)")
PLAGES_FICTIVES = ("04657100", "06399800")

# jeu -> version_schema attendu (None : absent, soit le format 1)
VERSION_SCHEMA = {"f1": None, "f2-v1.1.0": "2", "f3-v1.2.0": "3", "f3-v2.0.0": "3", "plus-recent": "5",
                  "melange": "3", "f3-v2.1.0": "3", "reserves-a-reprendre": "3"}
NB_TABLES = {"f2-v1.1.0": 22, "f3-v1.2.0": 24, "f3-v2.0.0": 24, "table-absente": 22, "plus-recent": 25,
             "f3-v2.1.0": 24, "reserves-a-reprendre": 24}
# Jeux de la 2.2 (T378), au format 3 : chaque fichier, et la base
JEUX_DE_LA_2_2 = ("f3-v2.1.0", "reserves-a-reprendre")
COMMENTAIRE_LEVEE_REPRISE = "levée avant la 2.2, date inconnue"
# Réserves attendues de la reprise des observations (D183), dans l'ordre : (id, controle_id, date_controle, texte,
# levee) ; gravite, echeance_levee, date_levee et ot_id vides ; commentaire_levee : COMMENTAIRE_LEVEE_REPRISE si levee
# vaut '1', vide sinon.
RESERVES_ATTENDUES = {
    "f3-v2.1.0": [
        ("RES-00001", "CTR-0004", "2025-04-03",
         "Purgeur automatique du réservoir défectueux : à remplacer avant la prochaine inspection.", "0"),
    ],
    "reserves-a-reprendre": [
        ("RES-00001", "CTR-0001", "2026-02-10", "Garde-corps de la passerelle desserré", "0"),
        ("RES-00002", "CTR-0001", "2026-02-10", "Fin de course haut à régler", "0"),
        ("RES-00003", "CTR-0001", "2026-02-10", "Câble de levage : un toron cassé", "0"),
        ("RES-00004", "CTR-0002", "2026-03-18", "Klaxon de recul inaudible", "1"),
        ("RES-00005", "CTR-0002", "2026-03-18", "Ceinture du siège conducteur usée", "1"),
        ("RES-00006", "CTR-0005", "2026-03-24", "- Raccord de la vanne 3 suintant", "0"),
        ("RES-00007", "CTR-0005", "2026-03-24", "= Pression basse à surveiller", "0"),
        ("RES-00008", "CTR-0005", "2026-03-24", "- Étiquette du fluide illisible", "0"),
        ("RES-00009", "CTR-0006", "2026-06-02", 'Gaine "B" percée ; débit insuffisant', "0"),
        ("RES-00010", "CTR-0006", "2026-06-02", 'Filtre du caisson "F7" colmaté', "0"),
        ("RES-00011", "CTR-0007", "2026-01-15", "Cellule de sécurité inopérante", "0"),
        ("RES-00012", "CTR-0007", "2026-01-15", "Bord sensible fendu", "0"),
        ("RES-00013", "CTR-0007", "2026-01-15", "Signalisation au sol effacée", "0"),
        ("RES-00014", "CTR-0007", "2026-01-15", "Notice absente du local", "0"),
        ("RES-00015", "CTR-0008", "", "Rapport du contrôle initial non retrouvé", "0"),
    ],
}# Fichiers sans BOM, par jeu (tous les autres CSV non vides en ont un) ; « * » : aucun CSV n'en a.
SANS_BOM = {"sans-bom": "*", "windows-1252": {"equipements.csv"}}


def etiquettes_presentes():
    try:
        for etiquette in ETIQUETTES:
            subprocess.check_output(["git", "rev-parse", "--verify", "--quiet", etiquette + "^{commit}"],
                                    cwd=str(RACINE), stderr=subprocess.DEVNULL)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def enregistrements(octets):
    """Nombre d'enregistrements CSV (en-tête exclu) : une fin de ligne entre guillemets n'en ouvre pas un."""
    n, entre_guillemets, debut = 0, False, 0
    for i, octet in enumerate(octets):
        if octet == 0x22:
            entre_guillemets = not entre_guillemets
        elif octet == 0x0A and not entre_guillemets:
            n, debut = n + 1, i + 1
    if debut < len(octets):
        n += 1
    return max(n - 1, 0)


def numeros_hors_plage(texte):
    return [m.group(0) for m in MOTIF_TELEPHONE.finditer(texte)
            if not ("0" + "".join(m.group(i) for i in (1, 3, 4, 5, 6))).startswith(PLAGES_FICTIVES)]


def version_schema(dossier):
    for ligne in (dossier / "parametres.csv").read_bytes().decode("utf-8-sig").splitlines():
        if ligne.startswith("version_schema;"):
            return ligne.split(";", 1)[1].lstrip("'")
    return None


def charger_serveur():
    specification = importlib.util.spec_from_file_location("serveur_prevo_formats_fixtures", RACINE / "serveur.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


serveur = charger_serveur()


def lignes_en_dictionnaires(octets):
    """Lignes d'un CSV lu par le serveur (lire_csv_tolerant, cellules brutes) : {colonne: cellule}."""
    entete, lignes = serveur.lire_csv_tolerant(octets)
    return [{nom: (ligne[i] if i < len(ligne) else "") for i, nom in enumerate(entete)} for ligne in lignes]


def reserves_reprises(octets_controles):
    """Réserves que la reprise des observations (D183) doit créer à partir de controles_reglementaires.csv, sans
    réserve existante : règle de CONCEPTION-L1 §3.2 recopiée pour un jeu canonique (dates AAAA-MM-JJ ou vides, booléens
    0/1 : dateLue et booleenLu rendent la cellule telle quelle). (id, controle_id, date_controle, texte, levee)."""
    trim = serveur.sans_blancs_js_aux_bords
    reserves = []
    for controle in lignes_en_dictionnaires(octets_controles):
        identifiant = trim(controle["id"])
        texte = serveur.relire_valeur_texte(controle["observations"])
        if not identifiant or not trim(texte):
            continue
        levee = "1" if controle["observations_levees"] == "1" else "0"
        for morceau in re.split(r"\r\n|\r|\n", texte):
            if trim(morceau):
                reserves.append(("RES-%05d" % (len(reserves) + 1), identifiant, controle["derniere_date"], trim(morceau),
                                 levee))
    return reserves


class TestJeux(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def jeu(self, nom):
        return copier_jeu(nom, self.tmp / nom)

    def test_liste_des_jeux(self):
        self.assertEqual(sorted(JEUX), sorted([
            "f1", "f2-v1.1.0", "f3-v1.2.0", "f3-v2.0.0", "vide", "entete-tronque", "colonnes-manquantes",
            "colonnes-en-trop", "sans-bom", "table-absente", "melange", "windows-1252", "plus-recent", "f3-v2.1.0",
            "reserves-a-reprendre"]))

    def test_chaque_jeu_se_materialise(self):
        for nom in JEUX:
            with self.subTest(jeu=nom):
                dossier = self.jeu(nom)
                self.assertTrue((dossier / "parametres.csv").is_file())
                self.assertFalse((dossier / "variante.json").exists())
        with self.assertRaises(KeyError):
            copier_jeu("inconnu", self.tmp / "x")

    def test_les_variantes_ont_une_base_connue_et_une_description(self):
        for nom in JEUX:
            variante = lire_variante(nom)
            if variante is None:
                continue
            with self.subTest(jeu=nom):
                self.assertIn(variante["base"], JEUX)
                self.assertTrue(variante["description"])
                self.assertIsInstance(variante["supprimer"], list)
                self.assertIsInstance(variante["vider"], list)

    def test_version_schema(self):
        for nom, attendu in VERSION_SCHEMA.items():
            with self.subTest(jeu=nom):
                obtenu = version_schema(self.jeu(nom))
                if attendu is None:
                    self.assertIn(obtenu, (None, "1"))
                else:
                    self.assertEqual(obtenu, attendu)

    def test_nombre_de_tables(self):
        for nom, attendu in NB_TABLES.items():
            with self.subTest(jeu=nom):
                self.assertEqual(len(list(self.jeu(nom).glob("*.csv"))), attendu)

    def test_douze_enregistrements_au_plus(self):
        for nom in JEUX:
            dossier = self.jeu(nom)
            for chemin in sorted(dossier.glob("*.csv")):
                if chemin.name == "parametres.csv":
                    continue
                with self.subTest(jeu=nom, table=chemin.name):
                    self.assertLessEqual(enregistrements(chemin.read_bytes()), MAX_ENREGISTREMENTS)

    def test_les_bases_sont_tronquees(self):
        dossier = self.jeu("f3-v1.2.0")
        self.assertEqual(enregistrements((dossier / "equipements.csv").read_bytes()), 12)
        # une cellule multiligne reste entière : le premier enregistrement d'equipements en porte une
        corps = (dossier / "equipements.csv").read_bytes().split(b"\r\n", 1)[1]
        self.assertIn(b"\n", corps.split(b'"')[1])

    def test_bom(self):
        for nom in JEUX:
            dossier = self.jeu(nom)
            sans = SANS_BOM.get(nom, set())
            for chemin in sorted(dossier.glob("*.csv")):
                if chemin.stat().st_size == 0:
                    continue
                attendu = not (sans == "*" or chemin.name in sans)
                with self.subTest(jeu=nom, fichier=chemin.name):
                    self.assertEqual(chemin.read_bytes().startswith(BOM), attendu)

    def test_variantes_specifiques(self):
        self.assertEqual((self.jeu("vide") / "equipements.csv").stat().st_size, 0)
        self.assertFalse((self.jeu("table-absente") / "wiki_pages.csv").exists())
        self.assertFalse((self.jeu("table-absente") / "articles.csv").exists())
        entete = (self.jeu("entete-tronque") / "ordres_travail.csv").read_bytes().split(b"\r\n", 1)[0]
        self.assertTrue(entete.endswith(b"temps_pr"))
        entete = (self.jeu("melange") / "ordres_travail.csv").read_bytes().split(b"\r\n", 1)[0]
        self.assertNotIn(b"astuce", entete)
        entete = (self.jeu("plus-recent") / "ordres_travail.csv").read_bytes().split(b"\r\n", 1)[0]
        self.assertTrue(entete.endswith(b";nouvelle_colonne_v5"))
        self.assertTrue((self.jeu("plus-recent") / "pieces_v5.csv").is_file())
        self.assertFalse((self.jeu("plus-recent") / "pieces_v4.csv").exists())
        eq = (self.jeu("windows-1252") / "equipements.csv").read_bytes()
        with self.assertRaises(UnicodeDecodeError):
            eq.decode("utf-8")
        self.assertRegex(eq.decode("cp1252"), r";\d{2}/\d{2}/\d{4};")
        en_trop = (self.jeu("colonnes-en-trop") / "equipements.csv").read_bytes().decode("utf-8-sig").split("\r\n", 1)[0]
        self.assertIn("designation;colonne_maison;localisation_id", en_trop)
        self.assertTrue(en_trop.endswith(";note_maison"))
        manquantes = (self.jeu("colonnes-manquantes") / "equipements.csv").read_bytes().decode("utf-8-sig").split("\r\n", 1)[0].split(";")
        self.assertNotIn("modele", manquantes)
        self.assertNotIn("valeur_remplacement", manquantes)

    def test_jeux_de_la_2_2_au_format_3_cote_serveur(self):
        # Chaque fichier porte exactement les colonnes du format 3 (plus la colonne inconnue de reserves-a-reprendre)
        # et la base vaut 3 : ni plus récente, ni à passer au format 3 (lecture du navigateur : test_formats_js.py).
        for nom in JEUX_DE_LA_2_2:
            dossier = self.jeu(nom)
            with self.subTest(jeu=nom):
                self.assertEqual(serveur.version_de_base(lignes_en_dictionnaires(
                    (dossier / "parametres.csv").read_bytes())), 3)
                self.assertEqual(sorted(c.stem for c in dossier.glob("*.csv")), sorted(serveur.tables_du_format(3)))
                for chemin in sorted(dossier.glob("*.csv")):
                    entete, _ = serveur.lire_csv_tolerant(chemin.read_bytes())
                    attendu = serveur.colonnes_du_format(chemin.stem, 3)
                    if (nom, chemin.stem) == ("reserves-a-reprendre", "controles_reglementaires"):
                        attendu = attendu + ["remarque_maison"]
                    self.assertEqual(entete, attendu, chemin.name)
        self.assertNotEqual((self.jeu("f3-v2.1.0") / "controles_reglementaires.csv").read_bytes(),
                            (self.jeu("reserves-a-reprendre") / "controles_reglementaires.csv").read_bytes())

    def test_controles_a_reprendre_ecrits_comme_prevo(self):
        octets = (self.jeu("reserves-a-reprendre") / "controles_reglementaires.csv").read_bytes()
        entete, lignes = serveur.lire_csv_tolerant(octets)
        # Réécrites par Prévo, les cellules redonnent les octets du fichier (BOM, « ; », CRLF, guillemets)
        self.assertEqual(serveur.ecrire_tableau_csv(entete, lignes), octets)
        self.assertLessEqual(len(lignes), MAX_ENREGISTREMENTS)
        for numero, controle in enumerate(lignes_en_dictionnaires(octets), start=2):
            with self.subTest(ligne=numero):
                for colonne in ("derniere_date", "prochaine_date"):
                    self.assertRegex(controle[colonne], r"\A(\d{4}-\d{2}-\d{2})?\Z")
                self.assertIn(controle["observations_levees"], ("0", "1"))
                for colonne, cellule in controle.items():
                    # Donnees.csv.analyser retirerait une espace, une tabulation ou un CR en fin de cellule
                    self.assertNotRegex(cellule, r"[ \t\r]\Z", colonne)
                texte = serveur.relire_valeur_texte(controle["observations"])
                self.assertEqual(serveur.ecrire_valeur_texte(texte), controle["observations"])  # apostrophe juste
        observations = [serveur.relire_valeur_texte(c["observations"]) for c in lignes_en_dictionnaires(octets)]
        tout = "\n".join(observations)
        for motif in (r"\r\n", r"\r(?!\n)", r"(?<!\r)\n", ";", '"', r"(?m)^- ", r"(?m)^= ", r"(?m)^[ \t]+$"):
            self.assertRegex(tout, motif)
        self.assertTrue(any(re.search(r"\r\n", t) and re.search(r"\r(?!\n)", t) and re.search(r"(?<!\r)\n", t)
                            for t in observations), "CRLF, LF et CR dans une même cellule")
        self.assertTrue(observations[4].startswith("- "))
        self.assertTrue(lignes[4][entete.index("observations")].startswith("'- "))
        sans_date = [c for c in lignes_en_dictionnaires(octets) if c["observations"] and not c["derniere_date"]]
        self.assertEqual(len(sans_date), 1)
        vides = {(c["observations"], c["observations_levees"]) for c in lignes_en_dictionnaires(octets)}
        self.assertTrue({("", "0"), ("", "1")} <= vides)

    def test_reserves_attendues_selon_d183(self):
        lisezmoi = LISEZMOI.read_text(encoding="utf-8")
        self.assertIn(COMMENTAIRE_LEVEE_REPRISE, lisezmoi)
        for nom, attendues in sorted(RESERVES_ATTENDUES.items()):
            dossier = self.jeu(nom)
            with self.subTest(jeu=nom):
                self.assertFalse((dossier / "reserves_controle.csv").exists())
                self.assertEqual(reserves_reprises((dossier / "controles_reglementaires.csv").read_bytes()), attendues)
                for identifiant, controle, date, texte, levee in attendues:
                    ligne = "| %s | %s | %s | %s | %s |" % (identifiant, controle, date or "(vide)", texte, levee)
                    self.assertIn(ligne, lisezmoi)

    def test_comptes_de_la_2_0(self):
        dossier = self.jeu("f3-v2.0.0")
        contenu = json.loads((dossier / "acces" / "comptes.json").read_text(encoding="utf-8"))
        self.assertEqual(contenu["version"], 1)
        self.assertEqual([c["role"] for c in contenu["comptes"]], ["responsable"])
        parametres = (dossier / "parametres.csv").read_bytes().decode("utf-8-sig")
        for cle in ("mode_solo;'1", "cloture_une_etape;'1", "solo_technicien_id;TEC-0001"):
            self.assertIn(cle, parametres)
        # le mot de passe documenté retombe sur l'empreinte stockée
        compte = contenu["comptes"][0]
        calcule = hashlib.scrypt(b"essai-formats-prevo", salt=base64.b64decode(compte["sel"]), n=2 ** 15, r=8, p=3,
                                 maxmem=64 * 1024 * 1024, dklen=32)
        self.assertEqual(base64.b64encode(calcule).decode("ascii"), compte["empreinte"])

    def test_donnees_fictives(self):
        for nom in JEUX:
            for chemin in sorted(self.jeu(nom).rglob("*.csv")):
                texte = chemin.read_bytes().decode("cp1252" if nom == "windows-1252" else "utf-8", "replace")
                with self.subTest(jeu=nom, fichier=chemin.name):
                    self.assertEqual(numeros_hors_plage(texte), [])
                    for courriel in re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*", texte):
                        self.assertTrue(courriel.endswith(".example"), courriel)


class TestGenerateurReproductible(unittest.TestCase):
    def test_le_generateur_redonne_les_memes_octets(self):
        if not etiquettes_presentes():
            self.skipTest("git ou les étiquettes %s sont indisponibles" % ", ".join(ETIQUETTES))
        with tempfile.TemporaryDirectory() as tmp:
            sortie = Path(tmp) / "formats"
            subprocess.check_call([sys.executable, "-I", str(GENERATEUR), "--sortie", str(sortie)],
                                  stdout=subprocess.DEVNULL, cwd=str(RACINE))
            attendus = {c.relative_to(DOSSIER_JEUX).as_posix(): c.read_bytes() for c in DOSSIER_JEUX.rglob("*")
                        if c.is_file() and c.name != "LISEZMOI.md"}
            obtenus = {c.relative_to(sortie).as_posix(): c.read_bytes() for c in sortie.rglob("*")
                       if c.is_file() and c.name != "LISEZMOI.md"}
            self.assertEqual(sorted(obtenus), sorted(attendus))
            for nom in sorted(attendus):
                with self.subTest(fichier=nom):
                    self.assertEqual(obtenus[nom], attendus[nom])


if __name__ == "__main__":
    unittest.main()
