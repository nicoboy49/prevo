"""Jeux de fichiers d'exemple des formats de données (T182) : tests/fixtures/formats/.

Couvre : chaque jeu se matérialise ; version_schema et nombre de tables attendus ; 12 enregistrements au plus par
table ; BOM présent ou absent selon le jeu ; données fictives ; et, si git et les étiquettes v1.1.0 / v1.2.0 sont
là, le générateur rejoué redonne exactement les mêmes octets.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_formats_fixtures.py" -v
"""
import base64
import hashlib
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
BOM = b"\xef\xbb\xbf"
MAX_ENREGISTREMENTS = 12
# Même règle que tests/test_audit_divers.py (G3) : aucun numéro français hors des plages fictives de l'ARCEP
MOTIF_TELEPHONE = re.compile(r"(?<![\w.,])(?:(?:\+|00)33[ .-]?(?:\(0\)[ .-]?)?|0)([1-9])([ .-]?)(\d{2})\2(\d{2})\2(\d{2})\2(\d{2})(?!\w)")
PLAGES_FICTIVES = ("04657100", "06399800")

# jeu -> version_schema attendu (None : absent, soit le format 1)
VERSION_SCHEMA = {"f1": None, "f2-v1.1.0": "2", "f3-v1.2.0": "3", "f3-v2.0.0": "3", "plus-recent": "4",
                  "melange": "3"}
NB_TABLES = {"f2-v1.1.0": 22, "f3-v1.2.0": 24, "f3-v2.0.0": 24, "table-absente": 22, "plus-recent": 25}
# Fichiers sans BOM, par jeu (tous les autres CSV non vides en ont un) ; « * » : aucun CSV n'en a.
SANS_BOM = {"sans-bom": "*", "windows-1252": {"equipements.csv"}}


def etiquettes_presentes():
    try:
        for etiquette in ("v1.1.0", "v1.2.0"):
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
            "colonnes-en-trop", "sans-bom", "table-absente", "melange", "windows-1252", "plus-recent"]))

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
        self.assertTrue(entete.endswith(b";nouvelle_colonne_v4"))
        self.assertTrue((self.jeu("plus-recent") / "pieces_v4.csv").is_file())
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
            self.skipTest("git ou les étiquettes v1.1.0 / v1.2.0 sont indisponibles")
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
