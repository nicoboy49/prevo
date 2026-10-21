"""Guide utilisateur GUIDE.html, ses captures intégrées et le README vitrine (tâche T72, ARCHITECTURE.md §17.8).

Familles (le nom du test le dit) :
    source     : GUIDE.html lu comme texte, sans navigateur : aucun script ni ressource externe déclarée,
                 sommaire et liens internes, chapitres attendus, captures intégrées (JPEG en base64, 1,5 Mo
                 au plus en tout, PNG correspondants dans docs/captures/), mentions clés ;
    readme     : README.md montre docs/captures/accueil.png (qui existe) en tête, renvoie au guide et à la
                 fiche technique ;
    fichier    : GUIDE.html ouvert en file:// dans Chromium : aucune requête hors de la page, aucune
                 erreur console (CasNavigateur), images décodées, liens internes valides, pas de
                 défilement horizontal à 375 px ;
    impression : rendu imprimé noir sur blanc, page.pdf() sans erreur ;
    serveur    : servi par serveur.py (200, mêmes octets, text/html), aucune requête hors du serveur.

Les captures sont produites par outils/generer_captures.py (à relancer quand un écran change).
Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_guide.py" -v
"""
import base64
import html
import html.parser
import re
import unittest
import urllib.request

from commun import RACINE, CasNavigateur, ServeurPrevo, url_fichier

GUIDE = RACINE / "GUIDE.html"
README = RACINE / "README.md"
DOSSIER_CAPTURES = RACINE / "docs" / "captures"
CAPTURE_README = "docs/captures/accueil.png"
BUDGET_CAPTURES = 1500000          # octets de texte base64, toutes images comprises (§17.8)
CAPTURES = {"accueil", "signaler", "ot", "indicateurs", "planning", "suggestions", "poste"}
PREFIXE_JPEG = "data:image/jpeg;base64,"

# Chapitres demandés par §17.8 (identifiants des sections du guide).
CHAPITRES = ["demarrer", "demo", "mode-dossier", "mode-serveur", "pare-feu", "profils", "modules",
             "suggestions", "indicateurs", "rapport", "ce-poste", "ia", "ollama-origins", "ia-en-ligne",
             "ia-mentions", "modele-conseille", "dictee", "https", "https-android", "https-iphone",
             "sauvegardes", "excel", "limites"]

# Mentions qui doivent figurer dans le guide (faits du code et du contrat).
MENTIONS = [
    "OLLAMA_ORIGINS", "file://", "qwen2.5:7b", "ollama pull qwen2.5:7b", "http://localhost:11434",
    "L'IA propose, vous validez", "Utiliser", "Modifier", "Ignorer",
    "Autoriser les fournisseurs d'IA en ligne", "Le responsable n'a pas autorisé les fournisseurs en ligne",
    "IA : reste sur ce PC", "IA : reste sur le PC atelier", "IA : reste dans l'atelier", "IA : données envoyées à",
    "Dans Chrome et Edge, la voix est envoyée aux serveurs de Google ou Microsoft pour être transcrite.",
    "Dictée : utilisez le micro du clavier de votre téléphone.",
    "mkcert", "mkcert -install", "-CAROOT", "rootCA.pem", "rootCA-key.pem", "--certificat", "--cle",
    "Android", "iPhone", "Réglages des certificats",
    "Lancer_GMAO.bat", "Réseaux privés", "Essayer avec les données de démo", "Choisir le dossier de données",
    "Sauvegarder maintenant", "Restaurer…", "_avant-restauration", "Exporter en ZIP",
    "Excel", "FICHE_TECHNIQUE_CSV.md", "Contrôle de la base", "Pas d'authentification",
]


class LecteurGuide(html.parser.HTMLParser):
    """Relevé de la page : identifiants, liens internes (dont ceux du sommaire), images de capture,
    scripts, ressources déclarées (src, link href, url() et @import des styles)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.identifiants = []
        self.liens_internes = []
        self.liens_sommaire = []
        self.sections = []
        self.captures = []
        self.scripts = 0
        self.ressources = []
        self.styles = []
        self._dans_sommaire = 0
        self._dans_style = False

    def handle_starttag(self, balise, attributs):
        attributs = dict(attributs)
        if attributs.get("id"):
            self.identifiants.append(attributs["id"])
        if balise == "nav" and "sommaire" in (attributs.get("class") or "").split():
            self._dans_sommaire = 1
        elif balise == "nav" and self._dans_sommaire:
            self._dans_sommaire += 1
        if balise == "section" and "chapitre" in (attributs.get("class") or "").split():
            self.sections.append(attributs.get("id"))
        if balise == "a" and (attributs.get("href") or "").startswith("#"):
            self.liens_internes.append(attributs["href"][1:])
            if self._dans_sommaire:
                self.liens_sommaire.append(attributs["href"][1:])
        if balise == "img" and "data-capture" in attributs:
            self.captures.append(attributs)
        if balise == "script":
            self.scripts += 1
        if attributs.get("src") is not None and not attributs["src"].startswith("data:"):
            self.ressources.append("%s src=%s" % (balise, attributs["src"]))
        if balise == "link" and not (attributs.get("href") or "").startswith("data:"):
            self.ressources.append("link href=%s" % attributs.get("href"))
        if balise == "style":
            self._dans_style = True

    def handle_startendtag(self, balise, attributs):
        self.handle_starttag(balise, attributs)

    def handle_endtag(self, balise):
        if balise == "nav" and self._dans_sommaire:
            self._dans_sommaire -= 1
        if balise == "style":
            self._dans_style = False

    def handle_data(self, donnees):
        if self._dans_style:
            self.styles.append(donnees)


def lire_guide():
    lecteur = LecteurGuide()
    texte = GUIDE.read_text(encoding="utf-8")
    lecteur.feed(texte)
    lecteur.close()
    return texte, lecteur


# ---------------------------------------------------------------------------
# source : GUIDE.html lu comme texte
# ---------------------------------------------------------------------------

class TestGuideSource(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not GUIDE.is_file():
            raise AssertionError("GUIDE.html est absent de la racine du projet")
        cls.texte, cls.page = lire_guide()

    def test_source_autonome_sans_script_ni_ressource_externe(self):
        self.assertEqual(self.page.scripts, 0, "aucun script : le guide doit se lire sans JavaScript")
        self.assertEqual(self.page.ressources, [], "ressources déclarées hors de la page")
        styles = "\n".join(self.page.styles)
        self.assertNotIn("@import", styles)
        self.assertEqual([u for u in re.findall(r"url\(\s*['\"]?([^'\")]*)", styles) if not u.startswith("data:")], [])
        self.assertRegex(self.texte, r"@media print\b", "feuille d'impression attendue")
        self.assertIn('<html lang="fr">', self.texte)

    def test_source_sommaire_et_liens_internes(self):
        identifiants = self.page.identifiants
        doublons = sorted({i for i in identifiants if identifiants.count(i) > 1})
        self.assertEqual(doublons, [], "identifiants en double")
        self.assertGreater(len(self.page.liens_sommaire), 20, "sommaire trop court")
        casses = sorted(set(lien for lien in self.page.liens_internes if lien not in identifiants))
        self.assertEqual(casses, [], "liens internes sans cible")
        # Chaque chapitre est dans le sommaire.
        self.assertEqual([s for s in self.page.sections if s not in self.page.liens_sommaire], [])

    def test_source_chapitres_attendus(self):
        manquants = [c for c in CHAPITRES if c not in self.page.identifiants]
        self.assertEqual(manquants, [], "chapitres du §17.8 absents")
        self.assertEqual([c for c in CHAPITRES if c not in self.page.liens_sommaire], [], "chapitres hors sommaire")

    def test_source_captures_integrees_en_jpeg_dans_le_budget(self):
        noms = [image.get("data-capture") for image in self.page.captures]
        self.assertEqual(sorted(noms), sorted(CAPTURES), "captures attendues dans le guide")
        total = 0
        for image in self.page.captures:
            with self.subTest(capture=image["data-capture"]):
                src = image.get("src") or ""
                self.assertTrue(src.startswith(PREFIXE_JPEG), "src en data:image/jpeg;base64 attendu")
                donnees = src[len(PREFIXE_JPEG):]
                self.assertGreater(len(donnees), 1000, "capture vide")
                octets = base64.b64decode(donnees, validate=True)
                self.assertTrue(octets.startswith(b"\xff\xd8\xff"), "ce n'est pas un JPEG")
                self.assertTrue((image.get("alt") or "").strip(), "texte de remplacement (alt) manquant")
                self.assertTrue(image.get("width") and image.get("height"), "largeur et hauteur attendues")
                total += len(src)
        self.assertLessEqual(total, BUDGET_CAPTURES, "captures du guide : %d octets" % total)

    def test_source_captures_png_du_readme_et_de_l_outil(self):
        for nom in sorted(CAPTURES):
            with self.subTest(capture=nom):
                fichier = DOSSIER_CAPTURES / (nom + ".png")
                self.assertTrue(fichier.is_file(), "%s absent : lancer py outils/generer_captures.py" % fichier.name)
                self.assertTrue(fichier.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))

    def test_source_mentions_cles(self):
        # Texte tel qu'affiché : entités décodées (&nbsp; devant « : » ou dans « … » compte pour une
        # espace), une phrase pouvant être coupée en fin de ligne.
        texte = re.sub(r"\s+", " ", html.unescape(self.texte).replace("\xa0", " "))
        manquantes = [mention for mention in MENTIONS if mention not in texte]
        self.assertEqual(manquantes, [], "mentions absentes du guide")


# ---------------------------------------------------------------------------
# readme : vitrine
# ---------------------------------------------------------------------------

class TestReadme(unittest.TestCase):

    def test_readme_capture_en_tete_et_renvois(self):
        texte = README.read_text(encoding="utf-8")
        image = re.search(r"!\[[^\]]+\]\((docs/captures/accueil\.png)\)", texte)
        self.assertIsNotNone(image, "image Markdown de %s attendue" % CAPTURE_README)
        self.assertTrue((RACINE / CAPTURE_README).is_file(), CAPTURE_README + " absent")
        self.assertTrue((RACINE / CAPTURE_README).read_bytes().startswith(b"\x89PNG"))
        # « Pour qui, pourquoi » (passe de lancement) précède la présentation : c'est l'introduction,
        # la capture doit venir avant le premier vrai chapitre qui la suit.
        chapitres = [m for m in re.finditer(r"^## (.*)$", texte, re.MULTILINE) if m.group(1) != "Pour qui, pourquoi"]
        premier_titre = chapitres[0]
        self.assertLess(image.start(), premier_titre.start(),
                        "la capture doit être en tête, avant le premier chapitre (hors « Pour qui, pourquoi »)")
        self.assertIn("## Essayer en 30 secondes", texte)
        self.assertIn("(GUIDE.html)", texte)
        self.assertIn("(FICHE_TECHNIQUE_CSV.md)", texte)
        for fonction in ("Assistant IA", "Dictée", "Ce poste", "thème clair", "https"):
            self.assertIn(fonction, texte)


# ---------------------------------------------------------------------------
# navigateur : file://, impression, serveur
# ---------------------------------------------------------------------------

LIENS_CASSES_JS = """() => [...document.querySelectorAll('a[href^="#"]')]
  .map((a) => decodeURIComponent(a.getAttribute('href').slice(1)))
  .filter((id) => !document.getElementById(id))"""
IMAGES_JS = """() => [...document.querySelectorAll('img[data-capture]')]
  .map((i) => [i.dataset.capture, i.complete && i.naturalWidth > 0])"""
DEBORDEMENT_JS = "() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]"


class CasGuide(CasNavigateur):

    def ouvrir(self, adresse):
        """Ouvre le guide et rend la liste des requêtes faites par la page (sauf data:)."""
        requetes = []
        self.page.on("request", lambda requete: requetes.append(requete.url))
        self.page.goto(adresse)
        self.page.wait_for_load_state("load")
        return [url for url in requetes if not url.startswith("data:")]


class TestGuideNavigateur(CasGuide):

    def test_fichier_aucune_requete_externe_images_et_liens(self):
        adresse = url_fichier(GUIDE)
        requetes = self.ouvrir(adresse)
        self.assertEqual([u for u in requetes if u not in (adresse, self.page.url)], [],
                         "requêtes hors de la page")
        self.assertEqual(self.page.title(), "Guide d'utilisation de Prévo")
        images = self.page.evaluate(IMAGES_JS)
        self.assertEqual(sorted(nom for nom, _ in images), sorted(CAPTURES))
        self.assertEqual([nom for nom, decodee in images if not decodee], [], "images non décodées")
        self.assertEqual(self.page.evaluate(LIENS_CASSES_JS), [])
        # Un lien du sommaire mène à son chapitre.
        self.page.click("nav.sommaire a[href='#ollama-origins']")
        self.page.wait_for_function("location.hash === '#ollama-origins'")

    def test_fichier_telephone_sans_defilement_horizontal(self):
        self.page.set_viewport_size({"width": 375, "height": 812})
        self.ouvrir(url_fichier(GUIDE))
        largeur, visible = self.page.evaluate(DEBORDEMENT_JS)
        self.assertLessEqual(largeur, visible, "défilement horizontal à 375 px")

    def test_impression_noir_sur_blanc_et_pdf(self):
        self.ouvrir(url_fichier(GUIDE))
        self.page.emulate_media(media="print")
        fond, couleur = self.page.evaluate(
            "() => { const s = getComputedStyle(document.body); return [s.backgroundColor, s.color]; }")
        self.assertEqual(fond, "rgb(255, 255, 255)")
        self.assertEqual(couleur, "rgb(0, 0, 0)")
        self.assertEqual(self.page.evaluate("() => getComputedStyle(document.querySelector('.haut')).display"), "none")
        pdf = self.page.pdf(format="A4")
        self.assertTrue(pdf.startswith(b"%PDF"), "PDF attendu")
        self.assertGreater(len(pdf), 100000, "PDF anormalement petit : %d octets" % len(pdf))

    def test_serveur_guide_servi_sans_requete_externe(self):
        with ServeurPrevo() as serveur:
            with urllib.request.urlopen(serveur.url + "/GUIDE.html", timeout=10) as reponse:
                self.assertEqual(reponse.status, 200)
                self.assertIn("text/html", reponse.headers.get("Content-Type", ""))
                self.assertEqual(reponse.read(), GUIDE.read_bytes())
            requetes = self.ouvrir(serveur.url + "/GUIDE.html")
            self.assertEqual([u for u in requetes if not u.startswith(serveur.url + "/")], [],
                             "requêtes hors du serveur")
            self.assertEqual(self.page.evaluate(LIENS_CASSES_JS), [])


if __name__ == "__main__":
    unittest.main()
