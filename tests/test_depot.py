"""Tests du dépôt : bibliothèques tierces, police, licences, favicon, règles git, découpage des
modules JavaScript (taille, ordre de chargement dans index.html) et documentation du lot 7 (README,
docs/INSTALLATION.md, ARCHITECTURE §22).

Bibliothèque standard seulement. Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_depot.py" -v
"""
import hashlib
import importlib.util
import json
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
    "js/lib/echarts.min.js": "e84270bd0cd5bdf60fefc26d00c2a391cb2e81f4d26a7a9ee16185a54773a3cf",
    # SheetJS CE 0.20.3 (lot 5), CDN officiel cdn.sheetjs.com, téléchargé le 2026-10-21
    "js/lib/xlsx.full.min.js": "cc015130aa8521e7f088f88898eba949ccdcbfb38df0bd129b44b7273c3a6f41",
    "css/polices/sora-latin-wght-normal.woff2": "714cfbc8e4b3f224102a517dd5f39c85e114b27163602159deee4d8c4a8602f0",
    # Sora latin-ext (Lot 5, T343, D162) : @fontsource-variable/sora 5.2.5 (même paquet que latin), jsDelivr, 2026-11-08
    "css/polices/sora-latin-ext-wght-normal.woff2": "41687c928ef86e57644e21d12cd97450d7690d3a4a2c66def192b14a7de527e7",
}

IGNORES = [
    "donnees/essai.csv", "donnees/sauvegardes/x", "donnees/documents/x.jpg",
    "verrou.txt", ".chantier/x", "reference-design/x", "LISEZMOI.md",
    "tests/resultats/x", "__pycache__/x.pyc",
]
NON_IGNORES = ["donnees/demo/equipements.csv", "donnees/.gitkeep", "docs/brief-gmao.md"]

# Ordre exact des scripts js/modules/ dans index.html : RECOPIE de docs/ARCHITECTURE.md §15.1
# (ordre du lot 3, qui complète celui du §14.2). Le contrat et ce test changent ensemble.
ORDRE_MODULES = [
    "apropos.js", "mise-a-jour.js", "aide-ecrans-textes.js", "aide-ecrans.js", "acces-textes.js", "connexion-ecrans.js",
    "installation-etapes.js", "installation-ecrans.js", "installation-fiche.js",
    "accueil.js", "accueil-bento.js", "causes-frequentes.js",
    "ia.js", "ia-prompts.js", "ia-encadre.js", "ia-serveur.js", "dictee.js", "poste.js", "brouillons.js",
    "parc-regles.js", "parc-arbre.js", "parc-formulaires.js", "parc-etiquettes.js", "parc-fiche.js",
    "demandes-regles.js", "demandes-ecritures.js", "demandes-signaler.js", "demandes-liste.js", "demandes-fiche.js",
    "ordres-regles.js", "ordres-ecritures.js", "ordres-liste.js", "ordres-fiche.js", "ordres-onglets.js",
    "ordres-pieces.js", "ordres-impression.js",
    "preventif-regles.js", "preventif-ecritures.js", "preventif-ecrans.js", "preventif-calendrier.js",
    "suggestions-regles.js", "suggestions-ecrans.js",
    "magasin-regles.js", "magasin-ecritures.js", "magasin-articles.js", "magasin-mouvements.js", "magasin-achats.js",
    "equipe-regles.js", "equipe-ecritures.js", "equipe-ecrans.js", "equipe-acces.js",
    "controles-regles.js", "controles-ecritures.js", "controles-ecrans.js",
    "planning-regles.js", "planning-ecritures.js", "planning-ecrans.js",
    "indicateurs-regles.js", "indicateurs-series.js", "indicateurs-graphiques.js", "indicateurs-ecrans.js",
    "rapport-contenu.js", "rapport-ecrans.js",
    "zip-donnees.js", "zip-tables.js", "zip-flux.js", "zip-lecture.js",
    "parametres.js", "parametres-codes.js", "parametres-solo.js", "parametres-sauvegardes.js", "parametres-zip.js",
    "parametres-acces.js",
    "import-regles.js", "import-historique.js", "import-controles.js", "import-lecture.js", "import-ecritures.js",
    "import-modeles.js",
    "import-ecrans.js", "import-apercu.js",
    "wiki-regles.js", "wiki-calculs.js", "wiki-entites.js", "wiki-texte.js", "wiki-recherche.js", "wiki-ingestion.js",
    "wiki-journal.js", "wiki-ecrans.js", "wiki-page-ecrans.js", "wiki-sections-ecrans.js", "wiki-entites-ecrans.js",
    "wiki-journal-ecrans.js", "wiki-ecrire-ecrans.js",
]
LIGNES_MAX_MODULE = 700   # décision D28 : aucun fichier de js/modules/ au-delà
# Ordre exact des scripts du socle dans index.html, avant ceux de js/modules/ : RECOPIE de docs/ARCHITECTURE.md §1
# (« Ordre de chargement dans index.html »). js/formats.js juste après js/schema.js (chantier socle de données, T183).
# Chantier multilingue (T234) : le moteur de traduction, les langues, le français, l'aide française et le chargeur de la
# langue active juste avant js/schema.js.
ORDRE_SOCLE = [
    "js/lib/papaparse.min.js", "js/lib/qrcode.js", "js/lib/jsQR.js",
    "js/i18n.js", "js/i18n/langues.js", "js/i18n/fr.js", "js/i18n/aide/fr.js", "js/i18n-chargeur.js",
    "js/schema.js", "js/formats.js", "js/donnees.js",
    "js/stockage-serveur.js", "js/stockage-dossier.js", "js/stockage-demo.js", "js/interface.js",
]

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

    def test_jszip_retire(self):
        # T229 : le ZIP est lu et écrit par js/modules/zip-flux.js (T226 à T228) ; JSZip n'est plus embarqué.
        self.assertFalse((RACINE / "js" / "lib" / "jszip.min.js").exists())
        for chemin in ("index.html", "js/lib/LICENCES.txt", "js/modules/apropos.js", "README.md"):
            with self.subTest(fichier=chemin):
                self.assertNotIn("jszip", lire(chemin).lower())


class TestLicences(unittest.TestCase):
    def test_licences_tierces(self):
        texte = lire("js/lib/LICENCES.txt")
        attendus = [
            "PapaParse 5.7.0", "qrcode-generator 2.0.4", "jsQR 1.4.0",
            "Apache ECharts 5.5.1", "Sora", "MIT License", "Apache License",
            "Version 2.0", "The Apache Software Foundation", "SIL OPEN FONT LICENSE",
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

    def test_socle_charge_dans_l_ordre_du_contrat(self):
        scripts = self.scripts_index()
        # Seul js/prechargement.js (dans <head>, §22.13 : ancien script en ligne) précède le socle
        debut = scripts.index(ORDRE_SOCLE[0])
        self.assertEqual(scripts[:debut], ["js/prechargement.js"])
        self.assertEqual(scripts[debut:debut + len(ORDRE_SOCLE)], ORDRE_SOCLE)
        # Le bloc des modules suit le socle sans rien entre les deux
        suivant = scripts[debut + len(ORDRE_SOCLE)]
        self.assertTrue(suivant.startswith("js/modules/"), suivant)

    def test_socle_recopie_l_ordre_d_architecture(self):
        texte = lire("docs/ARCHITECTURE.md")
        debut = texte.index("**Ordre de chargement dans `index.html`**")
        fin = texte.index("les fichiers de `js/modules/`", debut)
        self.assertEqual(re.findall(r"`(js/[^`]+\.js)`", texte[debut:fin]), ORDRE_SOCLE)

    def test_modules_tous_charges_par_index_html(self):
        charges = set(self.scripts_index())
        for fichier in self.fichiers_modules():
            with self.subTest(fichier=fichier.name):
                self.assertIn("js/modules/" + fichier.name, charges,
                              "fichier orphelin : js/modules/%s n'est pas chargé par index.html" % fichier.name)

    def test_aucun_caractere_invisible_en_clair_dans_les_sources(self):
        # Lot 4 (§17.9) : espaces insécables, fines ou de largeur nulle écrits par leur échappement
        # ( …), jamais en clair (invisibles à la relecture). Bibliothèques tierces exclues.
        invisibles = {" ": "U+00A0", " ": "U+202F", " ": "U+2009", "​": "U+200B"}
        sources = [f for f in sorted((RACINE / "js").rglob("*.js")) if "lib" not in f.relative_to(RACINE).parts]
        sources += sorted((RACINE / "css").rglob("*.css")) + sorted(RACINE.glob("*.html"))
        # Lot 7 (T161) : les fichiers de la porte d'entrée (acces/porte.html, porte.js, porte.css), servis aussi.
        sources += sorted(f for f in (RACINE / "acces").glob("*.*") if f.suffix in (".html", ".js", ".css"))
        self.assertGreater(len(sources), 40)
        self.assertTrue(any(f.name == "porte.js" for f in sources))
        for fichier in sources:
            with self.subTest(fichier=fichier.relative_to(RACINE).as_posix()):
                texte = fichier.read_text(encoding="utf-8")
                trouves = ["%s ligne %d" % (code, texte.count("\n", 0, texte.index(car)) + 1)
                           for car, code in invisibles.items() if car in texte]
                self.assertEqual(trouves, [])


# Documents publics du dépôt : aucun chemin ni outil personnel du poste de développement
# (lettre de lecteur Windows, dossier d'utilisateur, dossier synchronisé, service de synchronisation,
# chemin Git Bash). Motifs génériques (audit G5) : le test ne cite aucun dossier réel du poste.
# Lot 6 : versions anglaises (principales) et françaises, fichiers communautaires.
DOCUMENTS_PUBLICS = ["README.md", "README.fr.md", "docs/PILOTAGE.md", "GUIDE.html", "GUIDE.en.html",
                     "FICHE_TECHNIQUE_CSV.md", "docs/INSTALLATION.md", "docs/INSTALLATION.fr.md", "docs/METHODE.md",
                     "docs/METHODE.fr.md", "CONTRIBUTING.md", "CONTRIBUTING.fr.md", "ROADMAP.md", "ROADMAP.fr.md",
                     "SECURITY.md", "CODE_OF_CONDUCT.md", "CHANGELOG.md", "NOTICE"]
MOTIF_CHEMIN_PERSONNEL = re.compile(
    r"\b[A-Za-z]:\\(?!Prevo\b)"                            # lecteur Windows : X:\… (sauf C:\Prevo, le dossier
                                                            # conseillé par l'assistant, D131 : un chemin du produit)
    r"|\b(?:users|home)[\\/]\w"                             # dossier d'utilisateur : Users\<nom>, /home/<nom>
    r"|\bsync[\\/]\w"                                       # dossier synchronisé : sync\<nom>, sync/<nom>
    r"|\b\w*cloud\b|\bdropbox\b|\bonedrive\b"               # services de synchronisation (tout « …cloud »)
    r"|(?:^|(?<=[\s\"'`(]))/[a-z]/\w",                      # chemin Git Bash : /x/<dossier>
    re.IGNORECASE)


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
        for sonde in ("voir C:\\temp\\x", "D:\\prenom\\x", "C:\\Users\\prenom", "/home/prenom/x", "dossier MonCloud",
                      "dossier XCloud\\x", "dans Dropbox", "OneDrive\\x", "sync\\prenom\\sites", "sync/prenom/x",
                      "cd /d/partage/x", "(/e/sites)", "`/z/dossier`"):
            with self.subTest(sonde=sonde):
                self.assertTrue(chemins_personnels(sonde), sonde)
        for propre in ("Remarque : lot C et D.", "https://exemple.org/a:b", "C : la criticité", "https://exemple.org/a/b",
                       "docs/a/x", "base64 +/w/Erl6L7", "rsync -a", "nuage de points"):
            with self.subTest(propre=propre):
                self.assertEqual(chemins_personnels(propre), [], propre)



# CS165 (Lot 6) : aucun lien relatif mort dans les documents publics en Markdown (liens « [texte](cible) » et
# références « [nom]: cible », hors blocs de code) ; les adresses web, les courriels et les ancres seules ne sont pas
# vérifiés ici (une ancre de fichier, « fichier.md#ancre », l'est par son fichier).
MOTIF_LIEN_MARKDOWN = re.compile(r"\]\(<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\)")
MOTIF_REFERENCE_MARKDOWN = re.compile(r"^\[[^\]]+\]:\s*(\S+)", re.MULTILINE)


def documents_markdown_publics():
    racine = sorted(p.name for p in RACINE.glob("*.md") if p.name not in ("LISEZMOI.md", "BRIEF_design_accueil.md"))
    return racine + sorted("docs/" + p.name for p in (RACINE / "docs").glob("*.md"))


def liens_relatifs_morts(nom):
    chemin = RACINE / nom
    texte = re.sub(r"^```.*?^```", "", chemin.read_text(encoding="utf-8"), flags=re.MULTILINE | re.DOTALL)
    morts = []
    for cible in MOTIF_LIEN_MARKDOWN.findall(texte) + MOTIF_REFERENCE_MARKDOWN.findall(texte):
        if re.match(r"^(?:[a-z][a-z0-9+.-]*:|#)", cible, re.IGNORECASE):
            continue
        fichier = cible.split("#", 1)[0].split("?", 1)[0]
        if fichier and not (chemin.parent / fichier).exists():
            morts.append(cible)
    return morts


class TestLiensRelatifs(unittest.TestCase):

    def test_aucun_lien_relatif_mort(self):
        documents = documents_markdown_publics()
        self.assertIn("README.md", documents)
        self.assertIn("docs/INSTALLATION.md", documents)
        for nom in documents:
            with self.subTest(document=nom):
                self.assertEqual(liens_relatifs_morts(nom), [], nom)

    def test_le_controle_voit_un_lien_mort(self):
        # Le contrôle doit pouvoir échouer.
        sonde = RACINE / "tests" / "resultats"
        sonde.mkdir(parents=True, exist_ok=True)
        fichier = sonde / "sonde-liens.md"
        fichier.write_text("[a](absent.md) [b](https://exemple.org/x) [c](#ancre) [d](sonde-liens.md#x)\n"
                           "```\n[e](dans-un-bloc.md)\n```\n[f]: autre-absent.md\n", encoding="utf-8")
        try:
            self.assertEqual(liens_relatifs_morts("tests/resultats/sonde-liens.md"), ["absent.md", "autre-absent.md"])
        finally:
            fichier.unlink()


# Documentation du lot 7 (T178 ; CS135, D136, D138) : le README porte la grille Solo / Atelier / Intranet / Hébergé
# (aucun prix) et ses limites revues (plus de « pas d'authentification »), renvoie à docs/INSTALLATION.md, qui
# documente les mandataires et recopie toutes les clés de la configuration (CLES_CONFIGURATION de serveur.py, la
# seule source, celle que « serveur.py --aide » imprime) ; ARCHITECTURE garde le contrat du lot (§22).
# Lot 6 (D179, D181) : README.md et docs/INSTALLATION.md en anglais (principaux), README.fr.md et
# docs/INSTALLATION.fr.md en français ; la grille et les clés de configuration dans les deux langues.
INSTALLATION = "docs/INSTALLATION.md"
INSTALLATION_FR = "docs/INSTALLATION.fr.md"
GRILLE = ("Solo", "Workshop", "Intranet", "Hosted")
GRILLE_FR = ("Solo", "Atelier", "Intranet", "Hébergé")
DEBUT_CLES = "<!-- cles-configuration:debut -->"
FIN_CLES = "<!-- cles-configuration:fin -->"
MOTIF_LIGNE_CLE = re.compile(r"^\| `([a-z_]+)` \| (.*?) \| (.*?) \| (.*) \|$", re.MULTILINE)


def charger_serveur():
    """serveur.py lu comme module (rien n'est lancé), comme tests/test_acces_config.py."""
    specification = importlib.util.spec_from_file_location("serveur_prevo_depot", RACINE / "serveur.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def tableaux_markdown(texte):
    """Tableaux Markdown d'un texte : chacun est la liste de ses lignes (lignes consécutives commençant par « | »)."""
    tableaux, courant = [], []
    for ligne in texte.splitlines():
        if ligne.lstrip().startswith("|"):
            courant.append(ligne.strip())
        elif courant:
            tableaux.append(courant)
            courant = []
    return tableaux + ([courant] if courant else [])


def cellules(ligne):
    return [cellule.strip() for cellule in ligne.strip().strip("|").split("|")]


class TestDocumentationLot7(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.readme = lire("README.md")
        cls.readme_fr = lire("README.fr.md")
        cls.installation = lire(INSTALLATION) if (RACINE / INSTALLATION).is_file() else ""
        cls.installation_fr = lire(INSTALLATION_FR) if (RACINE / INSTALLATION_FR).is_file() else ""

    def test_readme_limites_revues(self):
        # « ollama_origins » : le guide ne conseille plus ce réglage (D134, M4).
        for nom, texte, interdits in (
                ("README.fr.md", self.readme_fr, ("pas d'authentification", "réseau local uniquement", "ollama_origins")),
                ("README.md", self.readme, ("no authentication", "local network only", "ollama_origins"))):
            texte = texte.lower().replace("’", "'")
            for interdit in interdits:
                with self.subTest(readme=nom, interdit=interdit):
                    self.assertFalse(interdit in texte, "%s contient encore « %s »" % (nom, interdit))

    def test_readme_grille_dans_un_meme_tableau_sans_prix(self):
        for nom, texte, mots, sur_demande in (("README.md", self.readme, GRILLE, "on request"),
                                              ("README.fr.md", self.readme_fr, GRILLE_FR, "sur demande")):
            with self.subTest(readme=nom):
                grilles = [t for t in tableaux_markdown(texte) if all(mot in cellules(t[0]) for mot in mots)]
                self.assertEqual(len(grilles), 1, "%s : un tableau dont l'en-tête porte %s" % (nom, ", ".join(mots)))
                grille = "\n".join(grilles[0])
                self.assertIn(sur_demande, grille.lower())
                self.assertIn("SELECTIS", grille)
                self.assertIsNone(re.search(r"€|\$|\beuros?\b|\bHT\b|\bTTC\b|/ ?mois|per month|a month", grille,
                                            re.IGNORECASE), "aucun prix dans la grille (D136)")

    def test_readme_renvoie_a_installation(self):
        self.assertIn("(%s)" % INSTALLATION, self.readme)
        self.assertIn("Hosted", self.readme)
        self.assertIn("(%s)" % INSTALLATION_FR, self.readme_fr)
        self.assertIn("Hébergé", self.readme_fr)

    def test_readme_lies_l_un_a_l_autre_en_tete(self):
        # D179 : chacun renvoie à l'autre dans ses premières lignes.
        self.assertIn("(README.fr.md)", "\n".join(self.readme.splitlines()[:5]))
        self.assertIn("(README.md)", "\n".join(self.readme_fr.splitlines()[:5]))
        for texte, attendus in ((self.readme, ("(ROADMAP.md)", "(CONTRIBUTING.md", "(docs/METHODE.md)")),
                                (self.readme_fr, ("(ROADMAP.fr.md)", "(CONTRIBUTING.fr.md", "(docs/METHODE.fr.md)"))):
            for attendu in attendus:
                with self.subTest(attendu=attendu):
                    self.assertIn(attendu, texte)

    def test_installation_mandataires(self):
        communs = ("X-Forwarded-Proto", "X-Forwarded-Host", "tailscale serve", "Caddy", "nginx", "IIS",
                   "Cloudflare Tunnel", '"mandataire": true', "127.0.0.1", "systemd", "Retirer_demarrage.ps1",
                   "Reinitialiser_mot_de_passe.bat", "--reinitialiser", "journal-acces.csv", "sessions.json",
                   "prevo.config.json")
        for nom, texte, propres in ((INSTALLATION, self.installation, ("directory", "GDPR")),
                                    (INSTALLATION_FR, self.installation_fr, ("annuaire", "RGPD"))):
            self.assertTrue((RACINE / nom).is_file(), nom + " absent")
            for attendu in communs + propres:
                with self.subTest(document=nom, attendu=attendu):
                    self.assertIn(attendu, texte)

    def test_installation_anglaise_recopie_les_cles_et_leurs_defauts(self):
        # La version anglaise traduit le type et l'aide ; les clés et les défauts sont ceux de serveur.py.
        serveur = charger_serveur()
        section = self.installation.split(DEBUT_CLES, 1)[1].split(FIN_CLES, 1)[0]
        lignes = MOTIF_LIGNE_CLE.findall(section)
        self.assertEqual([(ligne[0], ligne[2]) for ligne in lignes],
                         [(cle, "`%s`" % json.dumps(defaut, ensure_ascii=False))
                          for cle, _, defaut, _ in serveur.CLES_CONFIGURATION])

    def test_installation_recopie_toutes_les_cles_de_configuration(self):
        serveur = charger_serveur()
        self.assertIn(DEBUT_CLES, self.installation_fr)
        self.assertIn(FIN_CLES, self.installation_fr)
        section = self.installation_fr.split(DEBUT_CLES, 1)[1].split(FIN_CLES, 1)[0]
        lignes = MOTIF_LIGNE_CLE.findall(section)
        self.assertEqual([ligne[0] for ligne in lignes], [cle for cle, _, _, _ in serveur.CLES_CONFIGURATION])
        # Recopie fidèle : type, défaut (en JSON, tel qu'on l'écrit dans le fichier) et aide de chaque clé, comme
        # « serveur.py --aide » les imprime (texte_aide_configuration).
        for (cle, genre, defaut, aide), (_, genre_doc, defaut_doc, aide_doc) in zip(serveur.CLES_CONFIGURATION, lignes):
            with self.subTest(cle=cle):
                self.assertEqual(genre_doc, genre.replace("choix:", "un parmi ").replace("|", ", "))
                self.assertEqual(defaut_doc, "`%s`" % json.dumps(defaut, ensure_ascii=False))
                self.assertEqual(aide_doc, aide)

    def test_architecture_contrat_du_lot_7(self):
        self.assertIn("\n## 22. ", lire("docs/ARCHITECTURE.md"))


if __name__ == "__main__":
    unittest.main()
