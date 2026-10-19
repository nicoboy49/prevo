"""Tests du dépôt : bibliothèques tierces, police, licences, favicon et règles git.

Bibliothèque standard seulement. Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_depot.py" -v
"""
import hashlib
import subprocess
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

# Empreintes SHA-256 : empreinte du paquet vérifié le 2026-10-19
EMPREINTES = {
    "js/lib/papaparse.min.js": "4d5d2d6e3282b66aafaa5e6de8ca3ae06f8d3440111ae99c6a30f6c00cfac33e",
    "js/lib/qrcode.js": "79ec86f82856005b1c887905cfccfcfbec3821ca61c7fd5a952faa5f778f791c",
    "js/lib/jsQR.js": "bc40c8a15196236b2314db0856f72ca0b49980cd5413b8c852a7349f5fee0859",
    "js/lib/jszip.min.js": "7f839b2d4688b845c105ebf5d2f9803075f91ea0fe72bdaac176c3a04dd3d2c1",
    "js/lib/echarts.min.js": "e84270bd0cd5bdf60fefc26d00c2a391cb2e81f4d26a7a9ee16185a54773a3cf",
    "css/polices/sora-latin-wght-normal.woff2": "714cfbc8e4b3f224102a517dd5f39c85e114b27163602159deee4d8c4a8602f0",
}

IGNORES = [
    "donnees/essai.csv", "donnees/sauvegardes/x", "donnees/documents/x.jpg",
    "verrou.txt", ".chantier/x", "reference-design/x", "LISEZMOI.md",
    "tests/resultats/x", "__pycache__/x.pyc",
]
NON_IGNORES = ["donnees/demo/equipements.csv", "donnees/.gitkeep", "brief-gmao.md"]


def lire(chemin):
    return (RACINE / chemin).read_text(encoding="utf-8")


class TestBibliotheques(unittest.TestCase):
    def test_empreintes(self):
        for chemin, attendue in EMPREINTES.items():
            with self.subTest(fichier=chemin):
                fichier = RACINE / chemin
                self.assertTrue(fichier.is_file(), "fichier absent : " + chemin)
                reelle = hashlib.sha256(fichier.read_bytes()).hexdigest()
                self.assertEqual(reelle, attendue)


class TestLicences(unittest.TestCase):
    def test_licences_tierces(self):
        texte = lire("js/lib/LICENCES.txt")
        attendus = [
            "PapaParse 5.7.0", "qrcode-generator 2.0.4", "jsQR 1.4.0", "JSZip 3.10.2",
            "Apache ECharts 5.6.0", "Sora", "MIT License", "Apache License",
            "Version 2.0", "The Apache Software Foundation", "SIL OPEN FONT LICENSE", "pako",
        ]
        for attendu in attendus:
            with self.subTest(attendu=attendu):
                self.assertIn(attendu, texte)

    def test_licence_du_projet(self):
        texte = lire("LICENSE")
        self.assertIn("MIT License", texte)
        self.assertIn("Nicolas Briand — SELECTIS", texte)


class TestFavicon(unittest.TestCase):
    def test_favicon_valide(self):
        texte = lire("favicon.svg")
        ET.fromstring(texte)  # lève une erreur si le XML est mal formé
        self.assertIn("linearGradient", texte)
        self.assertNotIn("€", texte)


class TestGit(unittest.TestCase):
    def test_gitattributes_protege_les_csv(self):
        self.assertIn("*.csv -text", lire(".gitattributes"))

    def _est_ignore(self, chemin):
        resultat = subprocess.run(["git", "check-ignore", "-q", chemin], cwd=RACINE)
        return resultat.returncode == 0

    def test_fichiers_ignores(self):
        for chemin in IGNORES:
            with self.subTest(chemin=chemin):
                self.assertTrue(self._est_ignore(chemin), "devrait être ignoré : " + chemin)

    def test_fichiers_versionnes(self):
        for chemin in NON_IGNORES:
            with self.subTest(chemin=chemin):
                self.assertFalse(self._est_ignore(chemin), "ne devrait pas être ignoré : " + chemin)


if __name__ == "__main__":
    unittest.main()
