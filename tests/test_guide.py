"""Guide utilisateur GUIDE.html, ses captures intégrées et le README vitrine (tâche T72, ARCHITECTURE.md §17.8 ;
lot 7, T177 : chapitres de l'accès et de l'installation, CS134 M4 et I4, CS135, CS137).

Familles (le nom du test le dit) :
    source     : GUIDE.html lu comme texte, sans navigateur : aucun script ni ressource externe déclarée,
                 sommaire et liens internes, chapitres attendus, captures intégrées (JPEG en base64, 1,5 Mo
                 au plus en tout, PNG correspondants dans docs/captures/), mentions clés, mentions interdites
                 (plus de consigne OLLAMA_ORIGINS=*, audit M4 ; aucune adresse https:8443, CS137 ; plus
                 « pas d'authentification ») ;
    readme     : README.md montre docs/captures/accueil.png (qui existe) en tête, renvoie au guide et à la
                 fiche technique ;
    fichier    : GUIDE.html ouvert en file:// dans Chromium : aucune requête hors de la page, aucune
                 erreur console (CasNavigateur), images décodées, liens internes valides, pas de
                 défilement horizontal à 375 px ;
    impression : rendu imprimé noir sur blanc, page.pdf() sans erreur ;
    serveur    : servi par serveur.py (200, mêmes octets, text/html), aucune requête hors du serveur.

Les captures sont produites par outils/generer_captures.py (à relancer quand un écran change ; les écrans du
lot 7 y sont pris sur des serveurs de test, jamais lancés ici).
Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_guide.py" -v
"""
import base64
import html
import html.parser
import re
import unittest
import urllib.request

from commun import RACINE, CasNavigateur, ServeurPrevo, preregler_profil, url_fichier

GUIDE = RACINE / "GUIDE.html"
GUIDE_EN = RACINE / "GUIDE.en.html"          # Lot 6 (T338, D181) : le guide en anglais, même structure
DOSSIER_CAPTURES_EN = RACINE / "docs" / "captures" / "en"
README = RACINE / "README.md"
README_FR = RACINE / "README.fr.md"          # Lot 6 : README.md en anglais (principal), README.fr.md en français
DOSSIER_CAPTURES = RACINE / "docs" / "captures"
CAPTURE_README = "docs/captures/accueil.png"
BUDGET_CAPTURES = 1500000          # octets de texte base64, toutes images comprises (§17.8)
CAPTURES = {"accueil", "signaler", "ot", "indicateurs", "planning", "suggestions", "poste", "import",
            "wiki", "wiki-page",
            # Lot 7 (T177) : connexion, assistant (étape 1 et récapitulatif avec la fiche d'accès), Équipe › Accès,
            # porte d'entrée vue d'un Android et d'un iPhone (profils Playwright).
            "connexion", "equipe-acces", "installation", "installation-fiche", "porte-android", "porte-iphone",
            # 2.2 (L4, T497) : garanties et contrats de prestataires.
            "garanties"}
PREFIXE_JPEG = "data:image/jpeg;base64,"

# Chapitres demandés par §17.8, puis par le lot 6 (§20, T125 : « Le wiki de maintenance »), §21 (mise à jour
# signalée) et le lot 7 (§22, T177 : chapitre 2 autour de l'assistant, chapitre 8 « Accès et installation ») :
# identifiants des sections du guide.
CHAPITRES = ["demarrer", "demo", "mode-dossier", "installer", "assistant", "parcours", "pare-feu", "telephones",
             "choisir-mode", "mise-a-jour", "profils", "modules", "equipe", "suggestions", "indicateurs", "rapport",
             "parametres", "ce-poste", "ia", "ia-activer", "ia-en-ligne", "ia-mentions", "ia-problemes",
             "modele-conseille", "dictee", "wiki", "wiki-principe", "wiki-pages", "wiki-astuce", "wiki-file",
             "wiki-journal", "wiki-contradictions", "wiki-ecrire", "wiki-recherche", "wiki-demo",
             "acces", "se-connecter", "equipe-acces", "confiance", "confiance-android", "confiance-iphone",
             "tailscale", "demarrage-pc", "solo", "rgpd", "annuaire",
             "sauvegardes", "reprendre", "excel", "limites", "mots"]

# Mentions qui doivent figurer dans le guide (faits du code et du contrat).
MENTIONS = [
    "file://", "qwen2.5:7b", "ollama pull qwen2.5:7b", "http://localhost:11434",
    "L'IA propose, vous validez", "Utiliser", "Modifier", "Ignorer",
    "Autoriser les fournisseurs d'IA en ligne", "Le responsable n'a pas autorisé les fournisseurs en ligne",
    "IA : reste sur ce PC", "IA : reste sur le PC atelier", "IA : reste dans l'atelier", "IA : données envoyées à",
    "Dans Chrome et Edge, la voix est envoyée aux serveurs de Google ou Microsoft pour être transcrite.",
    "Dictée : utilisez le micro du clavier de votre téléphone.",
    "mkcert", "rootCA.pem", "rootCA-key.pem", "--certificat", "--cle", "prevo-ca.crt",
    "Android", "iPhone", "Réglages de confiance des certificats", "Installer quand même", "Profil téléchargé",
    "Lancer_GMAO.bat", "Réseaux privés", "Essayer avec les données de démo", "Choisir le dossier de données",
    "Sauvegarder maintenant", "Restaurer…", "_avant-restauration", "Exporter en ZIP",
    "Excel", "FICHE_TECHNIQUE_CSV.md", "Contrôle de la base",
    # Lot 6 (T125) : le wiki de maintenance et la mise à jour signalée (§21).
    # Aide à l'écran (§23).
    "Aide à l'écran", "Revoir toutes les explications", "Afficher l'explication à la première visite de chaque écran",
    "Le wiki de maintenance", "ingestion", "Astuce pour la prochaine fois", "OT ajouté à la file du wiki",
    "Traiter la file", "À trancher", "0,026 $ par OT", "claude-sonnet-5-5",
    "Me signaler les nouvelles versions de Prévo", "https://prevo.pro/version.json", "Ignorer cette version",
    # Lot 7 (T177, D135, D138, CS134 I4, CS135, CS137) : l'assistant, la connexion, la porte, Tailscale, le
    # démarrage avec le PC, le mode Solo, la rubrique RGPD, l'annuaire.
    "C:\\Prevo", "python", "prevo.config.json", "Moi seul", "Une petite équipe", "Je suis l'informaticien de l'entreprise",
    "Paramètres › Accès et installation", "docs/INSTALLATION.fr.md", "Solo", "Atelier", "Intranet",
    "Se connecter", "prenom.nom", "mot de passe provisoire", "Rester connecté sur cet appareil", "rester connecté",
    "12 caractères au moins", "Reinitialiser_mot_de_passe.bat", "Aucun courriel n'est envoyé",
    "Équipe › Accès", "Inviter un appareil", "Révoquer", "Journal des connexions",
    "Faites confiance au PC atelier", "Faire confiance au PC atelier", "porte d'entrée", "http://192.168.1.20:8080",
    "Réessayer", "Tailscale", "https://tailscale.com/download", "tailscale serve", "unattended", "expiration de clé",
    "n'ouvre jamais votre box", "tâche planifiée", "Installer_demarrage.ps1", "Retirer_demarrage.ps1",
    "journal-serveur.log", "veille", "Mode Solo", "technicien « moi »", "Clôture en une étape", "Nouvel OT",
    "RGPD", "journal-acces.csv", "12 mois", "[téléphone]", "[courriel]", "scrypt",
    "annuaire", "Active Directory", "comptes locaux", "mandataire inverse", "VPN de l'entreprise",
    "SELECTIS",
]

# Mentions qui ne doivent plus figurer (audit M4 : plus de consigne OLLAMA_ORIGINS=* ; CS137 : jamais l'adresse https
# de l'application ; lot 7 : Prévo a des comptes).
MENTIONS_INTERDITES = ["OLLAMA_ORIGINS=*", 'OLLAMA_ORIGINS "*"', "setx OLLAMA_ORIGINS", "launchctl setenv OLLAMA_ORIGINS",
                       "Environment=\"OLLAMA_ORIGINS", ":8443", "https://192.168", "Pas d'authentification",
                       "Prévo n'a pas de mot de passe"]


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
        self.titres = []
        self._dans_sommaire = 0
        self._dans_style = False
        self._dans_titre = None

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
        if balise in ("h2", "h3") and not self._dans_sommaire:
            self._dans_titre = [balise, ""]

    def handle_startendtag(self, balise, attributs):
        self.handle_starttag(balise, attributs)

    def handle_endtag(self, balise):
        if balise == "nav" and self._dans_sommaire:
            self._dans_sommaire -= 1
        if balise == "style":
            self._dans_style = False
        if balise in ("h2", "h3") and self._dans_titre:
            self.titres.append((balise, re.sub(r"\s+", " ", self._dans_titre[1].replace("\xa0", " ")).strip()))
            self._dans_titre = None

    def handle_data(self, donnees):
        if self._dans_style:
            self.styles.append(donnees)
        if self._dans_titre:
            self._dans_titre[1] += donnees


def lire_guide(chemin=None):
    lecteur = LecteurGuide()
    texte = (chemin or GUIDE).read_text(encoding="utf-8")
    lecteur.feed(texte)
    lecteur.close()
    return texte, lecteur


def texte_affiche(texte):
    """Texte tel qu'affiché : entités décodées (&nbsp; devant « : » ou dans « … » compte pour une espace), une
    phrase pouvant être coupée en fin de ligne."""
    return re.sub(r"\s+", " ", html.unescape(texte).replace("\xa0", " "))


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
        self.assertEqual(manquants, [], "chapitres du §17.8 et du §22 absents")
        self.assertEqual([c for c in CHAPITRES if c not in self.page.liens_sommaire], [], "chapitres hors sommaire")
        # Les chapitres gardent leur numéro (la démo en ligne cite « 5. L'assistant IA », test_version_web) ; le
        # chapitre 8 est désormais « Accès et installation » et ses sous-sections suivent le sommaire.
        titres_h2 = [titre for balise, titre in self.page.titres if balise == "h2"]
        self.assertIn("2. Démarrer", titres_h2)
        self.assertIn("3. Les rôles et les profils", titres_h2)
        self.assertIn("5. L'assistant IA", titres_h2)
        self.assertIn("8. Accès et installation", titres_h2)
        self.assertIn("12. Limites à connaître", titres_h2)
        titres_h3 = [titre for balise, titre in self.page.titres if balise == "h3"]
        for attendu in ("8.1 Se connecter", "8.3 Faire confiance au PC atelier", "8.4 Sur un téléphone Android",
                        "8.5 Sur un iPhone", "8.6 Hors de l'atelier avec Tailscale", "8.7 Prévo démarre avec le PC",
                        "8.8 Le mode Solo", "8.9 Vos données et le RGPD", "8.10 L'annuaire de l'entreprise",
                        "2.4 L'assistant d'installation"):
            self.assertIn(attendu, titres_h3)
        # Numérotation continue des sous-sections de chaque chapitre (le 5.6 OLLAMA_ORIGINS a disparu).
        numeros = [titre.split(" ")[0] for balise, titre in self.page.titres if balise == "h3" and re.match(r"\d+\.\d+ ", titre)]
        par_chapitre = {}
        for numero in numeros:
            chapitre, rang = numero.split(".")
            par_chapitre.setdefault(chapitre, []).append(int(rang))
        for chapitre, rangs in par_chapitre.items():
            with self.subTest(chapitre=chapitre):
                self.assertEqual(rangs, list(range(1, len(rangs) + 1)), "numérotation des sous-sections")

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
        # L'outil connaît chaque capture du guide, et le guide chaque capture de l'outil.
        outil = (RACINE / "outils" / "generer_captures.py").read_text(encoding="utf-8")
        self.assertEqual(sorted(set(re.findall(r'\{"nom": "([a-z-]+)"', outil))), sorted(CAPTURES))

    def test_source_mentions_cles(self):
        texte = texte_affiche(self.texte)
        manquantes = [mention for mention in MENTIONS if mention not in texte]
        self.assertEqual(manquantes, [], "mentions absentes du guide")

    def test_source_mentions_interdites_ollama_origins_https_8443_authentification(self):
        texte = texte_affiche(self.texte)
        presentes = [mention for mention in MENTIONS_INTERDITES if mention in texte]
        self.assertEqual(presentes, [], "mentions qui ne doivent plus figurer dans le guide")
        # Aucune adresse https vers une IP ni vers un port de l'application (CS137 : la porte seule est donnée).
        self.assertEqual(re.findall(r"https://(?:\d{1,3}\.){3}\d{1,3}", self.texte), [])
        self.assertEqual(re.findall(r"https://[^\s\"'<>()]*:\d{4,5}", self.texte), [])
        # Le guide ne conseille plus d'ouvrir Ollama à toutes les pages : le nom de la variable n'apparaît qu'en
        # citant un message de Prévo, jamais suivi d'une valeur.
        self.assertEqual(re.findall(r"OLLAMA_ORIGINS\s*[=:]", texte), [])

    def test_source_rubrique_rgpd_et_annuaire(self):
        # Audit I4 : la rubrique RGPD dit où sont les données, qui y accède, la durée du journal des connexions,
        # l'export, et pour l'IA le fournisseur, le pays, le masquage et qui décide ; D135 : réponse honnête sur
        # l'annuaire.
        texte = texte_affiche(self.texte)
        debut = texte.index("8.9 Vos données et le RGPD")
        fin = texte.index("8.10 L'annuaire de l'entreprise")
        rgpd = texte[debut:fin]
        for attendu in ("Où", "Qui accède", "Journal des connexions", "12 mois", "export", "Fournisseur", "Pays",
                        "[téléphone]", "[courriel]", "Qui décide"):
            self.assertIn(attendu, rgpd)
        annuaire = texte[fin:texte.index("Retour au sommaire", fin)]
        for attendu in ("pas de connexion unique", "comptes locaux", "export du journal des connexions",
                        "mandataire inverse", "VPN de l'entreprise"):
            self.assertIn(attendu, annuaire)


# ---------------------------------------------------------------------------
# readme : vitrine
# ---------------------------------------------------------------------------

class TestReadme(unittest.TestCase):

    # Lot 6 : README.fr.md (capture française) et README.md (anglais, capture de Prévo en anglais, T338).
    LECTURES = (
        (README_FR, "docs/captures/accueil.png", "Pour qui, pourquoi", "## Essayer en 30 secondes", "(GUIDE.html)",
         ("Assistant IA", "Dictée", "Ce poste", "thème clair", "https")),
        (README, "docs/captures/en/accueil.png", "Who it is for, and why", "## Try it in 30 seconds", "(GUIDE.en.html)",
         ("AI assistant", "Dictation", "This workstation", "light theme", "https")),
    )

    def test_readme_capture_en_tete_et_renvois(self):
        for chemin, capture, introduction, essayer, guide, fonctions in self.LECTURES:
            with self.subTest(readme=chemin.name):
                texte = chemin.read_text(encoding="utf-8")
                image = re.search(r"!\[[^\]]+\]\((%s)\)" % re.escape(capture), texte)
                self.assertIsNotNone(image, "image Markdown de %s attendue" % capture)
                self.assertTrue((RACINE / capture).is_file(), capture + " absent")
                self.assertTrue((RACINE / capture).read_bytes().startswith(b"\x89PNG"))
                # L'introduction (passe de lancement) précède la présentation : la capture doit venir avant le
                # premier vrai chapitre qui la suit.
                chapitres = [m for m in re.finditer(r"^## (.*)$", texte, re.MULTILINE) if m.group(1) != introduction]
                self.assertLess(image.start(), chapitres[0].start(),
                                "la capture doit être en tête, avant le premier chapitre (hors « %s »)" % introduction)
                self.assertIn(essayer, texte)
                self.assertIn(guide, texte)
                self.assertIn("(FICHE_TECHNIQUE_CSV.md)", texte)
                for fonction in fonctions:
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


class TestGuideAnglais(unittest.TestCase):
    """T338 (D181) : GUIDE.en.html, traduction de GUIDE.html : mêmes chapitres, mêmes ancres (l'aide à l'écran et
    À propos y renvoient selon la langue, UI.adresseGuide), mêmes captures, prises sur Prévo en anglais
    (py outils/generer_captures.py --langue en)."""

    @classmethod
    def setUpClass(cls):
        if not GUIDE_EN.is_file():
            raise AssertionError("GUIDE.en.html est absent de la racine du projet")
        cls.texte, cls.page = lire_guide(GUIDE_EN)
        cls.texte_fr, cls.page_fr = lire_guide(GUIDE)

    def test_langue_titre_et_autonomie(self):
        self.assertIn('<html lang="en">', self.texte)
        self.assertIn("<title>Prévo user guide</title>", self.texte)
        self.assertEqual(self.page.scripts, 0)
        self.assertEqual(self.page.ressources, [])
        self.assertRegex(self.texte, r"@media print\b")

    def test_meme_structure_que_le_guide_francais(self):
        self.assertEqual(self.page.identifiants, self.page_fr.identifiants)
        self.assertEqual(self.page.liens_internes, self.page_fr.liens_internes)
        self.assertEqual(self.page.liens_sommaire, self.page_fr.liens_sommaire)
        self.assertEqual(self.page.sections, self.page_fr.sections)
        numeros = lambda page: [titre.split(" ")[0] for balise, titre in page.titres if balise in ("h2", "h3")]
        self.assertEqual(numeros(self.page), numeros(self.page_fr))

    def test_captures_anglaises_integrees_dans_le_budget(self):
        self.assertEqual(sorted(image.get("data-capture") for image in self.page.captures), sorted(CAPTURES))
        total = 0
        for image in self.page.captures:
            with self.subTest(capture=image["data-capture"]):
                src = image.get("src") or ""
                self.assertTrue(src.startswith(PREFIXE_JPEG), "src en data:image/jpeg;base64 attendu")
                self.assertGreater(len(src), 1000, "capture vide")
                self.assertNotEqual(src, next(i.get("src") for i in self.page_fr.captures
                                              if i.get("data-capture") == image["data-capture"]),
                                    "capture identique à celle du guide français")
                self.assertTrue((image.get("alt") or "").strip(), "texte de remplacement (alt) manquant")
                total += len(src)
                fichier = DOSSIER_CAPTURES_EN / (image["data-capture"] + ".png")
                self.assertTrue(fichier.is_file(), "%s absent : py outils/generer_captures.py --langue en" % fichier)
        self.assertLessEqual(total, BUDGET_CAPTURES)

    def test_typographie_anglaise_et_renvois(self):
        # Texte affiché seulement : les commentaires et la feuille de style de l'en-tête restent ceux du guide français.
        corps = re.sub(r"<!--.*?-->|<style\b.*?</style>", " ", self.texte, flags=re.DOTALL)
        texte = texte_affiche(corps)
        self.assertEqual(re.findall(r"\w\s[:;!?](?:\s|$)", texte), [], "espace avant une ponctuation (typographie française)")
        self.assertNotIn('href="GUIDE.html', self.texte, "le guide anglais renvoie à lui-même, pas au français")
        for attendu in ("qwen2.5:7b", "Lancer_GMAO.bat", "prevo.config.json", "docs/INSTALLATION.md", "Tailscale",
                        "SELECTIS", "https://prevo.pro/version.json"):
            with self.subTest(attendu=attendu):
                self.assertIn(attendu, texte)


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
        self.page.click("nav.sommaire a[href='#confiance']")
        self.page.wait_for_function("location.hash === '#confiance'")

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

    def test_guide_de_la_langue_ouvert_par_l_application(self):
        # T338 : l'aide à l'écran et À propos ouvrent le guide de la langue active (anglais : GUIDE.en.html).
        preregler_profil(self.contexte, "responsable", "Test")
        self.page.add_init_script("try { localStorage.setItem('prevo.langue', 'en'); } catch (e) {}")
        self.page.goto(url_fichier(RACINE / "index.html"))
        self.page.click("#btn-demo")
        self.page.wait_for_function("document.documentElement.dataset.etat === 'pret'")
        self.assertEqual(self.page.evaluate("[I18n.langue, UI.adresseGuide()]"), ["en", "GUIDE.en.html"])
        self.page.evaluate("location.hash = '#/apropos'")
        self.page.wait_for_selector("#contenu a[href='GUIDE.en.html']")

    def test_serveur_guide_anglais_servi(self):
        with ServeurPrevo() as serveur:
            with urllib.request.urlopen(serveur.url + "/GUIDE.en.html", timeout=10) as reponse:
                self.assertEqual(reponse.status, 200)
                self.assertEqual(reponse.read(), GUIDE_EN.read_bytes())

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
