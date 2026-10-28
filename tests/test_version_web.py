"""Démo en ligne (version web) et zip de la release (brief de finition du lancement, point 7).

Quatre familles (le nom de la classe le dit) :
    construction : outils/construire_demo_web.py produit un dossier qui ne contient que la liste
                   blanche (index.html, favicon.svg, GUIDE.html, css/, js/), identique au dépôt à
                   l'octet près, sauf js/app.js où le drapeau VERSION_WEB passe à vrai ; remplacement
                   contrôlé (ligne absente ou en double : échec clair) ; dossier étranger jamais écrasé ;
    navigateur   : la démo web servie comme sur le VPS (serveur de fichiers statiques) : l'accueil ne
                   propose que la démo et « Télécharger Prévo » ; l'assistant IA reste visible mais
                   tout appel (bouton d'un écran, « Tester la connexion », activation, vérification à
                   l'ouverture, IA pourtant réglée sur le poste) rend le message du brief, mot pour mot,
                   sans aucune requête hors du dossier ;
    depot        : dans le dépôt (drapeau faux), rien ne change : mode dossier proposé, IA appelée ;
    release      : outils/construire_release.py : contenu du zip, dates fixes, ordre trié, octets
                   identiques d'une construction à l'autre, lanceurs exécutables, serveur.py qui démarre
                   depuis le zip décompressé ; fichier manquant (NOTICE…) signalé clairement.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_version_web.py" -v
"""
import functools
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from commun import (RACINE, CasNavigateur, ServeurStatique, attendre_pret, port_libre, preregler_profil,
                    scenarios_demo, url_fichier)
from faux_fournisseur_ia import FauxFournisseur
from test_dictee import NOTER_TOASTS_JS
from test_ia_regles import regler_ia, taire_coupures

SCRIPT_DEMO_WEB = RACINE / "outils" / "construire_demo_web.py"
SCRIPT_RELEASE = RACINE / "outils" / "construire_release.py"
SCENARIOS = scenarios_demo()

# Texte du brief (point 7), mot pour mot : les guillemets extérieurs du brief ne font pas partie du message ;
# la section du guide est nommée comme dans GUIDE.html (« 5. L'assistant IA »), à la demande de Nicolas.
MESSAGE_IA = (
    "L'assistant IA n'est pas proposé dans cette démo en ligne : Prévo fonctionne entièrement sans lui. "
    "Sur votre installation, vous choisirez de l'activer ou non, entre deux options : un assistant local "
    "et gratuit (Ollama, sur un PC de l'atelier ; vos textes ne quittent pas l'entreprise), ou un service "
    "en ligne via une clé d'API (plus rapide, mais les textes envoyés partent chez le fournisseur choisi). "
    "Tout est expliqué dans le guide, section « 5. L'assistant IA »."
)
SOUS_TITRE_TELECHARGER = "Gratuit et libre : installez-le pour travailler sur vos propres données."
TITRE_DONNEES_DEMO = "Où sont les données de cette démo ?"
NOTE_DONNEES_DEMO = ("Nulle part : elles vivent dans cette page et disparaissent quand vous la fermez. Sur votre "
                     "installation, ce sont des fichiers CSV sur votre PC, lisibles dans Excel.")
ADRESSE_RELEASES = "https://github.com/nicoboy49/prevo/releases/latest"
LISTE_BLANCHE_WEB = ["GUIDE.html", "css", "favicon.svg", "index.html", "js"]
DRAPEAU_DEPOT = "const VERSION_WEB = false;"
DRAPEAU_WEB = "const VERSION_WEB = true;"
CONTENU_RELEASE = ["FICHE_TECHNIQUE_CSV.md", "GUIDE.html", "LICENSE", "Lancer_GMAO.bat", "NOTICE", "README.md",
                   "Reinitialiser_mot_de_passe.bat", "acces", "css", "favicon.svg", "index.html", "js", "lancer.sh",
                   "outils", "serveur.py"]
# outils/ : seulement la liste des empreintes des binaires tiers (lot 7, §22.14), que serveur.py lit pour vérifier mkcert.
FICHIERS_OUTILS_RELEASE = ["outils/empreintes-tiers.json"]
EXECUTABLES = ["lancer.sh", "serveur.py"]

# Texte du message IA affiché dans l'encadré d'un écran (même mécanisme que les autres erreurs de l'IA).
MESSAGE_ENCADRE = ".ia-encadre .ia-erreur > span"


# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------

def lancer(script, *arguments):
    """Lance un script de outils/ ; rend le CompletedProcess (sortie en texte UTF-8)."""
    environnement = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, str(script)] + [str(a) for a in arguments], cwd=str(RACINE),
                          capture_output=True, encoding="utf-8", errors="replace", env=environnement, timeout=120)


def fichiers_sous(dossier):
    """Chemins relatifs (a/b.js) des fichiers d'un dossier, triés ; fichiers cachés et caches Python exclus."""
    dossier = Path(dossier)
    retenus = []
    for chemin in dossier.rglob("*"):
        relatif = chemin.relative_to(dossier)
        if any(morceau.startswith(".") or morceau == "__pycache__" for morceau in relatif.parts):
            continue
        if chemin.is_file():
            retenus.append(relatif.as_posix())
    return sorted(retenus)


def fichiers_du_depot(*dossiers):
    """Fichiers du dépôt sous css/, js/… (chemins relatifs à la racine), triés."""
    return sorted(nom + "/" + chemin for nom in dossiers for chemin in fichiers_sous(RACINE / nom))


def version_et_date():
    texte = (RACINE / "js" / "app.js").read_text(encoding="utf-8")
    version = re.search(r"const VERSION = '([^']+)';", texte).group(1)
    date = tuple(int(n) for n in re.search(r"const DATE_VERSION = '(\d{4})-(\d{2})-(\d{2})';", texte).groups())
    return version, date


def charger_outil(chemin):
    """Importe un script de outils/ comme module (pour essayer ses fonctions sans le lancer)."""
    specification = importlib.util.spec_from_file_location(chemin.stem, chemin)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


@functools.lru_cache(maxsize=1)
def demo_web_construite():
    """Construit la démo web une seule fois pour tout le fichier : (dossier, CompletedProcess)."""
    racine = Path(tempfile.mkdtemp(prefix="prevo-demo-web-"))
    sortie = racine / "demo-web"
    resultat = lancer(SCRIPT_DEMO_WEB, "--sortie", sortie)
    return sortie, resultat


def tearDownModule():
    if demo_web_construite.cache_info().currsize:
        sortie, _ = demo_web_construite()
        shutil.rmtree(sortie.parent, ignore_errors=True)


class OutilsConstruction:
    """Mélange : échec clair si le script de construction a échoué."""

    def dossier_demo_web(self):
        sortie, resultat = demo_web_construite()
        self.assertEqual(resultat.returncode, 0, "construction de la démo web en échec :\n%s%s"
                         % (resultat.stdout, resultat.stderr))
        return sortie


# ---------------------------------------------------------------------------
# Construction de la démo web
# ---------------------------------------------------------------------------

class TestConstructionDemoWeb(OutilsConstruction, unittest.TestCase):

    def test_construction_liste_blanche_seulement(self):
        sortie = self.dossier_demo_web()
        self.assertEqual(sorted(p.name for p in sortie.iterdir()), LISTE_BLANCHE_WEB)
        attendus = sorted(["GUIDE.html", "favicon.svg", "index.html"] + fichiers_du_depot("css", "js"))
        self.assertEqual(sorted(p.relative_to(sortie).as_posix() for p in sortie.rglob("*") if p.is_file()), attendus)
        for nom in ("tests", "outils", "docs", "donnees", "serveur.py", "README.md", "Lancer_GMAO.bat"):
            self.assertFalse((sortie / nom).exists(), nom + " ne doit pas être dans la démo web")

    def test_construction_fichiers_identiques_sauf_le_drapeau(self):
        sortie = self.dossier_demo_web()
        for relatif in fichiers_sous(sortie):
            if relatif == "js/app.js":
                continue
            with self.subTest(fichier=relatif):
                self.assertEqual((sortie / relatif).read_bytes(), (RACINE / relatif).read_bytes())
        depot = (RACINE / "js" / "app.js").read_bytes()
        self.assertEqual(depot.count(DRAPEAU_DEPOT.encode()), 1, "le drapeau du dépôt doit être faux, une seule fois")
        self.assertEqual((sortie / "js" / "app.js").read_bytes(), depot.replace(DRAPEAU_DEPOT.encode(), DRAPEAU_WEB.encode()))

    def test_construction_remplacement_controle(self):
        outil = charger_outil(SCRIPT_DEMO_WEB)
        self.assertEqual(outil.activer_version_web("a\n  " + DRAPEAU_DEPOT + "\nb\n"), "a\n  " + DRAPEAU_WEB + "\nb\n")
        for texte in ("aucun drapeau ici", DRAPEAU_DEPOT + "\n" + DRAPEAU_DEPOT, "const VERSION_WEB = vrai;"):
            with self.subTest(texte=texte):
                with self.assertRaises(outil.ErreurConstruction) as contexte:
                    outil.activer_version_web(texte)
                self.assertIn("VERSION_WEB", str(contexte.exception))

    def test_construction_refait_sa_sortie_mais_jamais_un_dossier_etranger(self):
        with tempfile.TemporaryDirectory(prefix="prevo-demo-web-") as racine:
            sortie = Path(racine) / "demo-web"
            for _ in range(2):          # une sortie déjà construite est refaite sans erreur
                resultat = lancer(SCRIPT_DEMO_WEB, "--sortie", sortie)
                self.assertEqual(resultat.returncode, 0, resultat.stderr)
            self.assertEqual(sorted(p.name for p in sortie.iterdir()), LISTE_BLANCHE_WEB)
            etranger = Path(racine) / "autre"
            etranger.mkdir()
            (etranger / "precieux.txt").write_text("à garder", encoding="utf-8")
            resultat = lancer(SCRIPT_DEMO_WEB, "--sortie", etranger)
            self.assertNotEqual(resultat.returncode, 0)
            self.assertIn("precieux.txt", resultat.stderr)
            self.assertEqual((etranger / "precieux.txt").read_text(encoding="utf-8"), "à garder")
            self.assertEqual([p.name for p in etranger.iterdir()], ["precieux.txt"])

    def test_construction_dist_ignore_par_git(self):
        if shutil.which("git") is None:
            self.skipTest("git absent")
        for chemin in ("dist/demo-web/index.html", "dist/prevo-1.2.0.zip"):
            with self.subTest(chemin=chemin):
                resultat = subprocess.run(["git", "check-ignore", "-q", chemin], cwd=str(RACINE))
                self.assertEqual(resultat.returncode, 0, chemin + " devrait être ignoré par git")


# ---------------------------------------------------------------------------
# La démo web dans le navigateur (servie comme sur le VPS)
# ---------------------------------------------------------------------------

class TestNavigateurDemoWeb(OutilsConstruction, CasNavigateur):
    """Démo web construite, servie par un serveur de fichiers statiques (comme nginx sur le VPS).
    Le faux fournisseur d'IA tourne pendant toute la classe : il ne doit recevoir AUCUNE requête."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        sortie, resultat = demo_web_construite()
        cls.sortie = sortie if resultat.returncode == 0 else None
        cls.statique = ServeurStatique(sortie if cls.sortie else RACINE)
        cls.statique.demarrer()
        cls.addClassCleanup(cls.statique.arreter)
        cls.faux = FauxFournisseur()
        cls.faux.demarrer()
        cls.addClassCleanup(cls.faux.arreter)
        taire_coupures(cls.faux)

    def setUp(self):
        super().setUp()
        self.dossier_demo_web()
        self.faux.requetes.clear()
        self.requetes = []
        self.contexte.on("request", lambda requete: self.requetes.append(requete.url))
        self.contexte.add_init_script(NOTER_TOASTS_JS)

    # -- outils ---------------------------------------------------------------------------

    def verifier_aucune_requete_hors_du_dossier(self):
        """Chaque requête vise un fichier du dossier construit, sur le même serveur ; aucune API."""
        self.assertTrue(self.requetes, "aucune requête enregistrée : l'écoute ne marche pas")
        for adresse in self.requetes:
            if adresse.startswith(("data:", "blob:")):
                continue
            with self.subTest(requete=adresse):
                self.assertTrue(adresse.startswith(self.statique.url + "/"), "requête hors du dossier : " + adresse)
                chemin = urllib.parse.unquote(urllib.parse.urlsplit(adresse).path).lstrip("/")
                self.assertFalse(chemin.startswith("api/"), "appel d'API : " + adresse)
                self.assertTrue((self.sortie / chemin).is_file(), "fichier absent du dossier : " + adresse)
        self.assertEqual(self.faux.requetes, [], "le fournisseur d'IA a été appelé")

    def ouvrir_demo(self):
        preregler_profil(self.contexte, "responsable", "Responsable")
        page = self.page
        page.goto(self.statique.url + "/index.html")
        page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        page.click("#btn-demo")
        attendre_pret(page)
        return page

    def aller(self, route, selecteur):
        self.page.evaluate("(route) => { location.hash = route; }", route)
        self.page.wait_for_selector(selecteur)

    def message_de_l_encadre(self, portee=""):
        selecteur = (portee + " " + MESSAGE_ENCADRE).strip()
        self.page.wait_for_selector(selecteur, state="visible")
        return self.page.text_content(selecteur)

    # -- accueil --------------------------------------------------------------------------

    def test_navigateur_accueil_demo_seule_et_telecharger(self):
        page = self.page
        page.goto(self.statique.url + "/index.html")
        page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        self.assertIs(page.evaluate("App.versionWeb"), True)
        # Seuls « Essayer avec les données de démo » et « Télécharger Prévo » sont proposés.
        proposes = page.eval_on_selector_all(
            "#ecran-demarrage button, #ecran-demarrage a, #ecran-demarrage label, #ecran-demarrage input",
            "elements => elements.filter((e) => e.offsetParent !== null).map((e) => e.id)")
        self.assertEqual(proposes, ["btn-demo", "btn-telecharger"])
        for cache in ("#btn-dossier", "#btn-reprendre", "#zone-depot", "#note-mode-serveur", "#alerte-navigateur"):
            with self.subTest(cache=cache):
                self.assertFalse(page.is_visible(cache), cache + " devrait être masqué en version web")
        self.assertIn("Essayer avec les données de démo", page.inner_text("#btn-demo"))
        self.assertIn("Télécharger Prévo", page.inner_text("#btn-telecharger"))
        self.assertEqual(" ".join(page.inner_text("#btn-telecharger small").split()), SOUS_TITRE_TELECHARGER)
        self.assertEqual(page.get_attribute("#btn-telecharger", "href"), ADRESSE_RELEASES)
        # « Où sont vos données ? » est remplacé par la question et la réponse propres à la démo en ligne.
        self.assertFalse(page.is_visible("#titre-donnees"))
        self.assertEqual(page.text_content("#titre-donnees-demo").strip(), TITRE_DONNEES_DEMO)
        self.assertEqual(" ".join(page.inner_text("#note-donnees-demo").split()), NOTE_DONNEES_DEMO)
        page.wait_for_timeout(300)
        self.verifier_aucune_requete_hors_du_dossier()

    # -- assistant IA ---------------------------------------------------------------------

    def test_navigateur_ia_visible_et_message_sans_requete(self):
        """IA non réglée (cas d'un visiteur) : boutons à leur place, chaque appel rend le message."""
        page = self.ouvrir_demo()
        self.assertEqual(page.evaluate("Ia.etat()"), "inconnu")

        # « Signaler » : bouton d'un écran (Ia.bouton), après une saisie (sinon l'écran demande d'écrire d'abord)
        self.aller("#/di/nouvelle?equipement=" + SCENARIOS["causes_equipement"], ".di-formulaire")
        page.fill(".di-formulaire input[name=symptome]", "fuite huile sous le verin")
        page.click('.ia-bouton:has-text("Proposer avec l\'IA")')
        self.assertEqual(self.message_de_l_encadre(), MESSAGE_IA)

        # Fiche gamme : emplacement (Ia.emplacement) de la check-list, visible avec son bouton (le résumé IA de la
        # fiche équipement, qui servait ici, est retiré au lot 6)
        gamme = page.evaluate("Donnees.lignes('gammes')[0].id")
        self.aller("#/preventif/gamme/" + gamme, ".pv-check-liste .ia-bouton")
        self.assertTrue(page.is_visible(".pv-check-liste .ia-bouton"))
        page.click(".pv-check-liste .ia-bouton")
        self.assertEqual(self.message_de_l_encadre(".pv-check-liste"), MESSAGE_IA)

        # Compte rendu d'un OT : « Proposer les codes »
        ot_id = SCENARIOS["ot_statut_en_cours"]
        self.aller("#/ot/" + ot_id, ".ot-fiche")
        page.click(".onglet[data-onglet='compte-rendu']")
        page.wait_for_selector("#form-compte-rendu")
        page.click('.ia-bouton:has-text("Proposer les codes")')
        self.assertEqual(self.message_de_l_encadre(), MESSAGE_IA)

        # « Ce poste » : « Tester la connexion » (liste des modèles), puis activation refusée
        self.aller("#/poste", "#btn-tester-ia")
        self.assertTrue(page.is_visible("#carte-dictee"), "la dictée reste telle quelle")
        page.click("#btn-tester-ia")
        page.wait_for_function("(m) => document.querySelector('#poste-ia-resultat').textContent.includes(m)", arg=MESSAGE_IA)
        self.assertEqual(page.inner_text("#poste-ia-resultat").strip(), MESSAGE_IA)
        page.check("#poste-ia-actif")
        page.click("#btn-enregistrer-ia")
        page.wait_for_selector("#poste-ia-resultat .alerte.important")
        self.assertEqual(page.inner_text("#poste-ia-resultat").strip(), MESSAGE_IA)
        self.assertIs(page.evaluate("Ia.reglages().actif"), False)

        self.assertEqual(page.evaluate("Ia.etat()"), "inconnu")
        page.wait_for_timeout(300)
        self.verifier_aucune_requete_hors_du_dossier()

    def test_navigateur_ia_reglee_sur_le_poste_jamais_appelee(self):
        """IA réglée et active dans le navigateur (vers le faux fournisseur) : ni test à l'ouverture,
        ni appel au clic ; les fonctions de bas niveau rendent le message elles aussi."""
        regler_ia(self.contexte, url=self.faux.url)
        page = self.ouvrir_demo()
        page.wait_for_timeout(800)                  # le test d'ouverture serait parti pendant ce temps
        self.assertEqual(self.faux.requetes, [])
        self.assertFalse(page.is_visible("#ia-mention"), "aucune mention « IA : … » dans la coque")
        self.assertEqual(page.evaluate("Ia.verifierAuDemarrage()"), "inconnu")
        self.assertEqual(page.evaluate("Ia.tester().then((r) => [r.ok, r.modeles, r.message])"), [False, [], MESSAGE_IA])
        self.assertEqual(page.evaluate("Ia.tester({ url: 'http://localhost:11434' }).then((r) => r.message)"), MESSAGE_IA)
        demande = page.evaluate("Ia.demander('reformulerDI', { symptome: 'x' }).then(() => 'proposition', (e) => e.message)")
        self.assertEqual(demande, MESSAGE_IA)

        self.aller("#/di/nouvelle?equipement=" + SCENARIOS["causes_equipement"], ".di-formulaire")
        page.fill(".di-formulaire input[name=symptome]", "fuite huile sous le verin")
        page.click('.ia-bouton:has-text("Proposer avec l\'IA")')
        self.assertEqual(self.message_de_l_encadre(), MESSAGE_IA)
        page.wait_for_timeout(300)
        self.verifier_aucune_requete_hors_du_dossier()


# ---------------------------------------------------------------------------
# Le dépôt (drapeau faux) : rien ne change
# ---------------------------------------------------------------------------

class TestDepotInchange(CasNavigateur):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.faux = FauxFournisseur()
        cls.faux.demarrer()
        cls.addClassCleanup(cls.faux.arreter)
        taire_coupures(cls.faux)

    def setUp(self):
        super().setUp()
        self.faux.requetes.clear()

    def test_depot_accueil_propose_toujours_le_dossier(self):
        page = self.page
        page.goto(url_fichier("index.html"))
        page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        self.assertIs(page.evaluate("App.versionWeb"), False)
        for visible in ("#btn-dossier", "#btn-demo", "#zone-depot", "#note-mode-serveur"):
            with self.subTest(visible=visible):
                self.assertTrue(page.is_visible(visible), visible + " doit rester proposé")
        self.assertFalse(page.is_visible("#btn-telecharger"))
        self.assertIn("Choisir le dossier de données", page.inner_text("#btn-dossier"))
        self.assertEqual(page.text_content("#titre-donnees").strip(), "Où sont vos données ?")
        self.assertFalse(page.is_visible("#titre-donnees-demo"))
        self.assertFalse(page.is_visible("#note-donnees-demo"))

    def test_depot_ia_toujours_appelee_et_sans_bouton_si_inactive(self):
        regler_ia(self.contexte, url=self.faux.url)
        preregler_profil(self.contexte, "responsable", "Responsable")
        page = self.page
        page.goto(url_fichier("index.html"))
        page.click("#btn-demo")
        attendre_pret(page)
        page.wait_for_function("Ia.etat() === 'ok'")
        self.assertEqual([(r["methode"], r["chemin"]) for r in self.faux.requetes], [("GET", "/api/tags")])
        self.assertIs(page.evaluate("Ia.versionWeb()"), False)
        message = page.evaluate("Ia.tester().then((r) => r.message)")
        self.assertTrue(message.startswith("Connexion réussie"), message)
        self.assertNotIn("démo en ligne", message)
        # IA désactivée : aucun bouton (comportement du lot 4)
        page.evaluate("Ia.enregistrerReglages({ actif: false })")
        page.evaluate("(route) => { location.hash = route; }", "#/di/nouvelle?equipement=" + SCENARIOS["causes_equipement"])
        page.wait_for_selector(".di-formulaire")
        page.wait_for_timeout(300)
        self.assertEqual(page.locator(".ia-bouton").count(), 0)


# ---------------------------------------------------------------------------
# Zip de la release
# ---------------------------------------------------------------------------

class TestRelease(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.temporaire = Path(tempfile.mkdtemp(prefix="prevo-release-"))
        cls.addClassCleanup(shutil.rmtree, cls.temporaire, True)
        cls.version, cls.date = version_et_date()
        # --sans-tiers : le contenu de l'application seul ; le Python embarqué et mkcert sont vérifiés par
        # tests/test_release_lot7.py (téléchargements simulés), pour ne rien télécharger ici.
        cls.resultat = lancer(SCRIPT_RELEASE, "--sortie", cls.temporaire / "a", "--sans-tiers")

    def chemin_zip(self):
        self.assertEqual(self.resultat.returncode, 0, "construction du zip en échec :\n%s%s"
                         % (self.resultat.stdout, self.resultat.stderr))
        chemin = self.temporaire / "a" / ("prevo-%s.zip" % self.version)
        self.assertTrue(chemin.is_file(), "zip absent : " + str(chemin))
        return chemin

    def test_release_contenu(self):
        prefixe = "prevo-%s/" % self.version
        with zipfile.ZipFile(self.chemin_zip()) as archive:
            noms = archive.namelist()
            for nom in noms:
                self.assertTrue(nom.startswith(prefixe), nom)
            relatifs = [nom[len(prefixe):] for nom in noms if not nom.endswith("/")]
            self.assertEqual(sorted({r.split("/")[0] for r in relatifs}), sorted(CONTENU_RELEASE))
            attendus = sorted([n for n in CONTENU_RELEASE if n not in ("acces", "css", "js", "outils")]
                              + fichiers_du_depot("acces", "css", "js")
                              + FICHIERS_OUTILS_RELEASE)
            self.assertEqual(sorted(relatifs), attendus)
            for relatif in relatifs:
                with self.subTest(fichier=relatif):
                    self.assertEqual(archive.read(prefixe + relatif), (RACINE / relatif).read_bytes())
            self.assertEqual([n for n in relatifs if n.startswith("outils/")], FICHIERS_OUTILS_RELEASE,
                             "de outils/, seule la liste des empreintes entre dans le zip")
            # Captures d'écran du README et du guide : sous docs/, jamais dans le zip ; les schémas de la page d'entrée
            # (acces/captures/, §22.6), eux, y sont : sans eux, un téléphone ne voit pas les étapes illustrées.
            for interdit in ("tests/", "outils/construire", "outils/generer", "docs/", "donnees/",
                             "__pycache__", ".pyc", "BRIEF",
                             "brief-gmao", "CONTRIBUTING", "CHANGELOG", ".chantier", ".git", "dist/"):
                with self.subTest(interdit=interdit):
                    self.assertFalse([n for n in noms if interdit in n], interdit + " ne doit pas être dans le zip")
            self.assertFalse([n for n in relatifs if "captures" in n and not n.startswith("acces/captures/")],
                             "seules les captures de la page d'entrée entrent dans le zip")
            for fichier in ("acces/porte.html", "acces/porte.js", "acces/porte.css"):
                self.assertIn(fichier, relatifs, "page d'entrée (§22.6) absente du zip")
            self.assertTrue([n for n in relatifs if n.startswith("acces/captures/") and n.endswith(".svg")],
                            "schémas de la page d'entrée absents du zip")
            self.assertIn(DRAPEAU_DEPOT.encode(), archive.read(prefixe + "js/app.js"), "la release n'est pas la version web")
            self.assertIn(prefixe + "js/demo-donnees.js", noms, "jeu de démo : « Partir des données de démo »")

    def test_release_deterministe_dates_fixes_ordre_trie(self):
        premier = self.chemin_zip()
        second = lancer(SCRIPT_RELEASE, "--sortie", self.temporaire / "b", "--sans-tiers")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual((self.temporaire / "b" / premier.name).read_bytes(), premier.read_bytes())
        with zipfile.ZipFile(premier) as archive:
            infos = archive.infolist()
            self.assertEqual([i.filename for i in infos], sorted(i.filename for i in infos))
            for info in infos:
                with self.subTest(fichier=info.filename):
                    self.assertEqual(info.date_time, self.date + (0, 0, 0))
                    droits = (info.external_attr >> 16) & 0o777
                    nom = info.filename.split("/", 1)[1]
                    self.assertEqual(droits, 0o755 if nom in EXECUTABLES else 0o644)

    def test_release_serveur_demarre_depuis_le_zip(self):
        dossier = self.temporaire / "decompresse"
        with zipfile.ZipFile(self.chemin_zip()) as archive:
            archive.extractall(dossier)
        application = dossier / ("prevo-%s" % self.version)
        port = port_libre()
        journal = open(self.temporaire / "serveur.log", "wb")
        self.addCleanup(journal.close)
        processus = subprocess.Popen(
            [sys.executable, "serveur.py", "--sans-navigateur", "--port", str(port)], cwd=str(application),
            stdin=subprocess.DEVNULL, stdout=journal, stderr=subprocess.STDOUT,
            env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1"))

        def arreter():
            processus.terminate()
            try:
                processus.wait(timeout=5)
            except subprocess.TimeoutExpired:
                processus.kill()
        self.addCleanup(arreter)
        base = "http://127.0.0.1:%d" % port
        fin = time.monotonic() + 15
        while True:
            try:
                with urllib.request.urlopen(base + "/api/ping", timeout=1) as reponse:
                    if reponse.status == 200:
                        break
            except (urllib.error.URLError, OSError):
                pass
            self.assertIsNone(processus.poll(), "serveur.py s'est arrêté : " + (self.temporaire / "serveur.log").read_text(errors="replace"))
            self.assertLess(time.monotonic(), fin, "serveur.py n'a pas répondu en 15 s")
            time.sleep(0.1)
        with urllib.request.urlopen(base + "/", timeout=5) as reponse:
            self.assertIn("<title>Prévo", reponse.read().decode("utf-8"))
        with urllib.request.urlopen(base + "/GUIDE.html", timeout=5) as reponse:
            self.assertEqual(reponse.status, 200)
        self.assertTrue((application / "donnees").is_dir(), "serveur.py crée lui-même donnees/")

    def test_release_fichier_manquant_signale_clairement(self):
        source = self.temporaire / "source-incomplete"
        (source / "js").mkdir(parents=True)
        shutil.copy2(RACINE / "js" / "app.js", source / "js" / "app.js")
        sortie = self.temporaire / "sortie-incomplete"
        resultat = lancer(SCRIPT_RELEASE, "--source", source, "--sortie", sortie, "--sans-tiers")
        self.assertNotEqual(resultat.returncode, 0)
        self.assertIn("NOTICE", resultat.stderr)
        self.assertIn("serveur.py", resultat.stderr)
        self.assertFalse(sortie.exists() and any(sortie.iterdir()), "rien ne doit être écrit")


if __name__ == "__main__":
    unittest.main()
