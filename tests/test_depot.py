"""Tests du dépôt : bibliothèques tierces, police, licences, favicon, règles git et découpage des
modules JavaScript (taille, ordre de chargement dans index.html).

Bibliothèque standard seulement. Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_depot.py" -v
"""
import hashlib
import re
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

# Ordre exact des scripts js/modules/ dans index.html : RECOPIE de docs/ARCHITECTURE.md §15.1
# (ordre du lot 3, qui complète celui du §14.2). Le contrat et ce test changent ensemble.
ORDRE_MODULES = [
    "apropos.js", "accueil.js", "causes-frequentes.js",
    "parc-regles.js", "parc-arbre.js", "parc-formulaires.js", "parc-etiquettes.js", "parc-fiche.js",
    "demandes-regles.js", "demandes-ecritures.js", "demandes-signaler.js", "demandes-liste.js", "demandes-fiche.js",
    "ordres-regles.js", "ordres-ecritures.js", "ordres-liste.js", "ordres-fiche.js", "ordres-onglets.js",
    "ordres-pieces.js", "ordres-impression.js",
    "preventif-regles.js", "preventif-ecritures.js", "preventif-ecrans.js", "preventif-calendrier.js",
    "suggestions-regles.js", "suggestions-ecrans.js",
    "magasin-regles.js", "magasin-ecritures.js", "magasin-articles.js", "magasin-mouvements.js", "magasin-achats.js",
    "equipe-regles.js", "equipe-ecritures.js", "equipe-ecrans.js",
    "controles-regles.js", "controles-ecritures.js", "controles-ecrans.js",
    "planning-regles.js", "planning-ecritures.js", "planning-ecrans.js",
    "indicateurs-regles.js", "indicateurs-series.js", "indicateurs-graphiques.js", "indicateurs-ecrans.js",
    "rapport-contenu.js", "rapport-ecrans.js",
    "parametres.js", "parametres-codes.js",
]
LIGNES_MAX_MODULE = 700   # décision D28 : aucun fichier de js/modules/ au-delà

# Lecture des <script src="…"> d'une page : les commentaires HTML sont retirés d'abord (une balise
# mise en commentaire n'est pas chargée), puis d'autres attributs sont acceptés avant src
# (<script defer src="…">). Guillemets doubles ou simples.
MOTIF_COMMENTAIRE_HTML = re.compile(r"<!--.*?-->", re.DOTALL)
MOTIF_SCRIPT_SRC = re.compile(r"""<script\b[^>]*?\ssrc\s*=\s*["']([^"']+)["']""", re.IGNORECASE)


def lire(chemin):
    return (RACINE / chemin).read_text(encoding="utf-8")


def scripts_de_la_page(texte_html):
    """Valeurs des <script src="…"> réellement chargés par une page HTML, dans l'ordre."""
    return MOTIF_SCRIPT_SRC.findall(MOTIF_COMMENTAIRE_HTML.sub("", texte_html))


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
            "Apache ECharts 5.5.1", "Sora", "MIT License", "Apache License",
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


class TestModules(unittest.TestCase):
    """Découpage des modules (ARCHITECTURE.md §14.2, décision D28)."""

    @staticmethod
    def scripts_index():
        """Valeurs des <script src="…"> réellement chargés par index.html, dans l'ordre."""
        return scripts_de_la_page(lire("index.html"))

    def test_lecture_des_scripts_ignore_les_commentaires_et_accepte_les_attributs(self):
        page = (
            '<script src="js/a.js"></script>\n'
            '<!-- <script src="js/en-commentaire.js"></script> -->\n'
            '<!--\n  <script src="js/commentaire-multiligne.js"></script>\n-->\n'
            '<script defer src="js/b.js"></script>\n'
            "<script type=\"text/javascript\" src='js/c.js'></script>\n"
            '<script>\n  // script en ligne, sans src\n</script>\n'
            '<script data-src="js/pas-un-src.js"></script>\n'
        )
        self.assertEqual(scripts_de_la_page(page), ["js/a.js", "js/b.js", "js/c.js"])

    @staticmethod
    def fichiers_modules():
        return sorted((RACINE / "js" / "modules").glob("*.js"))

    def test_modules_700_lignes_au_plus(self):
        fichiers = self.fichiers_modules()
        self.assertTrue(fichiers, "aucun fichier dans js/modules/")
        for fichier in fichiers:
            with self.subTest(fichier=fichier.name):
                nombre = len(fichier.read_text(encoding="utf-8").splitlines())
                self.assertLessEqual(nombre, LIGNES_MAX_MODULE,
                                     "%s : %d lignes, à découper (un module = un préfixe de fichiers)"
                                     % (fichier.name, nombre))

    def test_modules_charges_dans_l_ordre_du_contrat(self):
        scripts = self.scripts_index()
        modules = [s[len("js/modules/"):] for s in scripts if s.startswith("js/modules/")]
        self.assertEqual(modules, ORDRE_MODULES)
        # Un seul bloc, juste après js/interface.js et juste avant js/app.js (chargé en dernier)
        debut = scripts.index("js/interface.js") + 1
        self.assertEqual(scripts[debut:debut + len(ORDRE_MODULES)], ["js/modules/" + m for m in ORDRE_MODULES])
        self.assertEqual(scripts[debut + len(ORDRE_MODULES):], ["js/app.js"])

    def test_modules_tous_charges_par_index_html(self):
        charges = set(self.scripts_index())
        for fichier in self.fichiers_modules():
            with self.subTest(fichier=fichier.name):
                self.assertIn("js/modules/" + fichier.name, charges,
                              "fichier orphelin : js/modules/%s n'est pas chargé par index.html" % fichier.name)


# Documents publics du dépôt : aucun chemin ni outil personnel du poste de développement
# (lettre de lecteur Windows, dossier synchronisé, chemin Git Bash).
DOCUMENTS_PUBLICS = ["README.md", "docs/PILOTAGE.md"]
MOTIF_CHEMIN_PERSONNEL = re.compile(r"\b[A-Za-z]:\\|pcloud|sync[\\/]nicolas|/c/sync", re.IGNORECASE)


def chemins_personnels(texte):
    """Extraits du texte qui ressemblent à un chemin ou un outil personnel (liste vide sinon)."""
    return [m.group(0) for m in MOTIF_CHEMIN_PERSONNEL.finditer(texte)]


class TestDocumentsPublics(unittest.TestCase):

    def test_pilotage_et_readme_sans_chemin_personnel(self):
        for nom in DOCUMENTS_PUBLICS:
            with self.subTest(document=nom):
                texte = (RACINE / nom).read_text(encoding="utf-8")
                self.assertEqual(chemins_personnels(texte), [], nom)

    def test_pilotage_le_motif_reconnait_les_chemins_personnels(self):
        # Le contrôle doit pouvoir échouer (un ancien contrôle par grep ne voyait pas « C:\ »).
        for sonde in ("voir C:\\temp\\x", "dossier pCloud", "sync\\nicolas\\sites", "sync/nicolas/x", "cd /c/sync/x"):
            with self.subTest(sonde=sonde):
                self.assertTrue(chemins_personnels(sonde), sonde)
        for propre in ("Remarque : lot C et D.", "https://exemple.org/a:b", "C : la criticité"):
            with self.subTest(propre=propre):
                self.assertEqual(chemins_personnels(propre), [], propre)


if __name__ == "__main__":
    unittest.main()
