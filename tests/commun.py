"""Outils communs à tous les tests de Prévo (ARCHITECTURE.md §12).

Contenu :
    RACINE                      dossier du projet
    port_libre()                un port TCP libre sur 127.0.0.1
    url_fichier(chemin)         URL file:// d'un fichier du projet
    ServeurPrevo               serveur.py lancé sur une COPIE du jeu de démo (jamais donnees/ réel)
    ServeurStatique(racine)     petit serveur HTTP de fichiers (pour le dossier simulé OPFS)
    CasNavigateur               TestCase Playwright : Chromium headless, erreurs JS = échec
    preregler_profil(...)       profil et poste mémorisés dans localStorage avant le chargement
    attendre_pret(page)         attend document.documentElement.dataset.etat === 'pret'
    installer_dossier_simule()  remplace showDirectoryPicker par un sous-dossier OPFS
    charger_scripts(...)        ouvre page-vide.html (file://) et y ajoute des scripts du projet

Bibliothèque standard + Playwright (Python) ; Playwright n'est importé que s'il est installé :
les tests qui n'ont pas besoin du navigateur (serveur, dépôt) marchent sans lui.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -v
"""
import functools
import http.server
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

try:  # Playwright est facultatif pour les tests qui n'ouvrent pas de navigateur
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_DEMO = RACINE / "donnees" / "demo"
PAGE_VIDE = RACINE / "tests" / "fixtures" / "page-vide.html"

# Valeur par défaut de ServeurPrevo(source=...) : « le jeu de démo s'il existe, sinon vide ».
SOURCE_AUTO = "auto"


# ---------------------------------------------------------------------------
# Réseau et fichiers
# ---------------------------------------------------------------------------

def port_libre():
    """Retourne un port TCP libre sur 127.0.0.1 (le système en choisit un)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as prise:
        prise.bind(("127.0.0.1", 0))
        return prise.getsockname()[1]


def url_fichier(chemin):
    """URL file:// d'un fichier. Un chemin relatif est lu depuis la racine du projet."""
    chemin = Path(chemin)
    if not chemin.is_absolute():
        chemin = RACINE / chemin
    return chemin.resolve().as_uri()


def _supprimer_dossier(dossier):
    """Supprime un dossier temporaire ; sous Windows un fichier peut rester verrouillé un instant."""
    for _ in range(5):
        try:
            shutil.rmtree(dossier)
            return
        except FileNotFoundError:
            return
        except OSError:
            time.sleep(0.2)
    shutil.rmtree(dossier, ignore_errors=True)


# ---------------------------------------------------------------------------
# Serveur Prévo (serveur.py)
# ---------------------------------------------------------------------------

class ServeurPrevo:
    """Lance serveur.py sur une copie temporaire des données. Gestionnaire de contexte.

        with ServeurPrevo() as serveur:
            serveur.url       # 'http://127.0.0.1:54321'
            serveur.dossier   # Path du dossier de données temporaire
            serveur.port

    source : SOURCE_AUTO (défaut) = copie de donnees/demo s'il existe, sinon dossier vide ;
             None = dossier vide ; un chemin = copie de ce dossier.
    Ne touche jamais au dossier donnees/ réel : seul le dossier temporaire est passé à --donnees.
    """

    DELAI_DEMARRAGE_S = 15

    def __init__(self, source=SOURCE_AUTO):
        if source == SOURCE_AUTO:
            source = DOSSIER_DEMO if DOSSIER_DEMO.is_dir() else None
        self.source = Path(source) if source is not None else None
        self.port = None
        self.url = None
        self.dossier = None
        self._racine_temporaire = None
        self._processus = None
        self._fichier_journal = None
        self._chemin_journal = None

    # -- cycle de vie -------------------------------------------------------

    def __enter__(self):
        self.demarrer()
        return self

    def __exit__(self, type_exception, exception, trace):
        self.arreter()
        return False

    def demarrer(self):
        script = RACINE / "serveur.py"
        if not script.is_file():
            raise FileNotFoundError("serveur.py introuvable : " + str(script))

        # Dossier temporaire : <tmp>/donnees (les données) + <tmp>/serveur.log (sortie console)
        self._racine_temporaire = Path(tempfile.mkdtemp(prefix="prevo-test-"))
        self.dossier = self._racine_temporaire / "donnees"
        if self.source is not None:
            shutil.copytree(self.source, self.dossier)
        else:
            self.dossier.mkdir()

        self.port = port_libre()
        self.url = "http://127.0.0.1:%d" % self.port
        self._chemin_journal = self._racine_temporaire / "serveur.log"
        self._fichier_journal = open(self._chemin_journal, "wb")

        environnement = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        commande = [sys.executable, str(script), "--sans-navigateur",
                    "--port", str(self.port), "--donnees", str(self.dossier)]
        self._processus = subprocess.Popen(
            commande, cwd=str(RACINE), env=environnement,
            stdin=subprocess.DEVNULL, stdout=self._fichier_journal, stderr=subprocess.STDOUT)
        try:
            self._attendre_ping()
        except BaseException:
            self.arreter()
            raise

    def _attendre_ping(self):
        """Attend que GET /api/ping réponde (15 s maximum), sinon lève une erreur avec la console."""
        fin = time.monotonic() + self.DELAI_DEMARRAGE_S
        while time.monotonic() < fin:
            if self._processus.poll() is not None:
                raise RuntimeError("serveur.py s'est arrêté (code %s). Sortie :\n%s"
                                   % (self._processus.returncode, self.sortie_console()))
            try:
                with urllib.request.urlopen(self.url + "/api/ping", timeout=1) as reponse:
                    if reponse.status == 200:
                        return
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(0.1)
        raise RuntimeError("serveur.py n'a pas répondu à /api/ping en %d s. Sortie :\n%s"
                           % (self.DELAI_DEMARRAGE_S, self.sortie_console()))

    def arreter(self):
        """Arrête le processus (terminate, puis kill après 5 s) et supprime le dossier temporaire."""
        processus = self._processus
        if processus is not None and processus.poll() is None:
            processus.terminate()
            try:
                processus.wait(timeout=5)
            except subprocess.TimeoutExpired:
                processus.kill()
                processus.wait(timeout=5)
        self._processus = None
        if self._fichier_journal is not None:
            self._fichier_journal.close()
            self._fichier_journal = None
        if self._racine_temporaire is not None:
            _supprimer_dossier(self._racine_temporaire)
            self._racine_temporaire = None

    def sortie_console(self):
        """Texte écrit par serveur.py sur sa console (utile pour comprendre un échec)."""
        if self._chemin_journal is None or not self._chemin_journal.exists():
            return ""
        if self._fichier_journal is not None:
            self._fichier_journal.flush()
        return self._chemin_journal.read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Serveur statique (dossier simulé : l'OPFS n'existe qu'en http://127.0.0.1)
# ---------------------------------------------------------------------------

class _GestionnaireStatique(http.server.SimpleHTTPRequestHandler):
    """Sert des fichiers sans bruit en console, avec des types MIME fiables sous Windows.

    HTTP/1.1 (connexions persistantes), comme serveur.py : face à un serveur qui ouvre une
    connexion par requête (HTTP/1.0), Chromium sous Windows échoue environ une fois toutes les
    8 000 connexions avec net::ERR_NO_BUFFER_SPACE, ce qui faisait échouer des tests au hasard."""

    protocol_version = "HTTP/1.1"
    timeout = 30            # une connexion muette est fermée (le fil de service se termine)

    extensions_map = dict(http.server.SimpleHTTPRequestHandler.extensions_map, **{
        ".js": "text/javascript", ".css": "text/css", ".html": "text/html",
        ".svg": "image/svg+xml", ".json": "application/json", ".csv": "text/csv",
        ".woff2": "font/woff2",
    })

    def log_message(self, format, *arguments):  # silence
        pass

    def do_GET(self):
        # Chromium réclame /favicon.ico : on répond « rien » plutôt que 404 (qui serait une erreur console).
        if self.path == "/favicon.ico" and not Path(self.translate_path(self.path)).exists():
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        super().do_GET()


class _ServeurHttpStatique(http.server.ThreadingHTTPServer):
    """File d'écoute de 128 connexions (5 par défaut : une rafale de chargement de page serait
    réinitialisée ou retardée par Windows, comme pour serveur.py)."""
    request_queue_size = 128
    daemon_threads = True


class ServeurStatique:
    """Serveur HTTP de fichiers statiques dans un fil, sur un port libre. Gestionnaire de contexte.

        with ServeurStatique(RACINE) as statique:
            page.goto(statique.url + '/index.html')
    """

    def __init__(self, racine=RACINE):
        self.racine = Path(racine)
        self.port = None
        self.url = None
        self._serveur = None
        self._fil = None

    def __enter__(self):
        self.demarrer()
        return self

    def __exit__(self, type_exception, exception, trace):
        self.arreter()
        return False

    def demarrer(self):
        gestionnaire = functools.partial(_GestionnaireStatique, directory=str(self.racine))
        self._serveur = _ServeurHttpStatique(("127.0.0.1", 0), gestionnaire)
        self.port = self._serveur.server_address[1]
        self.url = "http://127.0.0.1:%d" % self.port
        self._fil = threading.Thread(target=self._serveur.serve_forever, daemon=True)
        self._fil.start()

    def arreter(self):
        if self._serveur is not None:
            self._serveur.shutdown()
            self._serveur.server_close()
            self._serveur = None
        if self._fil is not None:
            self._fil.join(timeout=5)
            self._fil = None


# ---------------------------------------------------------------------------
# Navigateur (Playwright)
# ---------------------------------------------------------------------------

class CasNavigateur(unittest.TestCase):
    """Base des tests qui ouvrent un navigateur.

    - un Chromium headless par classe de test (lancé dans setUpClass) ;
    - un contexte et une page NEUFS par test : self.contexte, self.page ;
    - surveillance : toute console.error et toute erreur JavaScript non attrapée (pageerror)
      sont collectées dans self.erreurs_console et FONT ÉCHOUER le test au tearDown.
      Un test qui provoque volontairement une erreur l'autorise avec
      self.autoriser_erreur('texte ou motif') (texte contenu, ou expression régulière compilée).
      Une classe fille qui redéfinit setUp/tearDown doit appeler super().
    """

    DELAI_PAR_DEFAUT_MS = 15000
    navigateur = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if sync_playwright is None:
            raise unittest.SkipTest("Playwright pour Python n'est pas installé")
        cls._playwright = sync_playwright().start()
        cls.addClassCleanup(cls._playwright.stop)
        cls.navigateur = cls._playwright.chromium.launch(headless=True)
        cls.addClassCleanup(cls.navigateur.close)

    def setUp(self):
        super().setUp()
        self.erreurs_console = []
        self._motifs_autorises = []
        self.contexte = self.navigateur.new_context(
            locale="fr-FR", viewport={"width": 1280, "height": 800})
        self.contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        self.page = self.contexte.new_page()
        self.surveiller(self.page)

    def surveiller(self, page):
        """Branche la collecte d'erreurs sur une page (appelé pour la page du test ; à rappeler
        pour toute autre page ouverte dans le contexte)."""
        page.on("console", self._noter_console)
        page.on("pageerror", self._noter_erreur_page)

    def _noter_console(self, message):
        if message.type == "error":
            emplacement = message.location or {}
            origine = "%s:%s" % (emplacement.get("url", ""), emplacement.get("lineNumber", ""))
            self.erreurs_console.append("console.error : %s (%s)" % (message.text, origine))
            if self.PANNE_RESEAU_SYSTEME in message.text:
                self._panne_reseau = True

    def _noter_erreur_page(self, erreur):
        self.erreurs_console.append("erreur JavaScript : %s" % (erreur,))

    def autoriser_erreur(self, motif):
        """Autorise les erreurs dont le texte contient `motif` (str) ou correspond à `motif` (re.compile)."""
        self._motifs_autorises.append(motif)

    def _est_autorisee(self, texte):
        for motif in self._motifs_autorises:
            if hasattr(motif, "search"):
                if motif.search(texte):
                    return True
            elif motif in texte:
                return True
        return False

    def tearDown(self):
        try:
            self.contexte.close()
        finally:
            interdites = [e for e in self.erreurs_console if not self._est_autorisee(e)]
            super().tearDown()
        if interdites:
            self.fail("Erreurs JavaScript détectées dans le navigateur :\n  " + "\n  ".join(interdites))

    # -- Panne réseau du système : une seule relance ------------------------------------------
    #
    # Sur ce poste (Windows, Chromium 148), environ une NOUVELLE connexion TCP locale sur 8 000 à
    # 30 000 échoue au hasard avec WSAENOBUFS (console : « net::ERR_NO_BUFFER_SPACE »), quel que
    # soit le serveur : reproduit hors de Prévo (serveur Python minimal, 30 000 fetch : 1 à 4
    # échecs, sur un ou trente ports ; aucun échec côté Python). Prévo n'y est pour rien ; les
    # connexions persistantes (HTTP/1.1) en réduisent la fréquence, sans l'annuler sur 400 tests.
    # Un test dont la console montre CETTE erreur est donc rejoué une fois, en le disant. Toute
    # autre erreur, ou une seconde panne, fait échouer le test normalement.

    PANNE_RESEAU_SYSTEME = "net::ERR_NO_BUFFER_SPACE"

    def run(self, result=None):
        if result is None:
            return super().run(result)
        enregistreur = _ResultatEnregistre()
        self._panne_reseau = False
        super().run(enregistreur)
        if enregistreur.echec and self._panne_reseau:
            sys.stderr.write("\n  [relance] %s : %s pendant le test, rejoué une fois\n"
                             % (self.id(), self.PANNE_RESEAU_SYSTEME))
            self._panne_reseau = False
            return super().run(result)
        enregistreur.rejouer(result)
        return result


class _ResultatEnregistre(unittest.TestResult):
    """Résultat d'unittest qui note les appels reçus pour les rejouer ensuite sur le vrai résultat."""

    METHODES = ("startTest", "stopTest", "addSuccess", "addFailure", "addError", "addSkip",
                "addExpectedFailure", "addUnexpectedSuccess", "addSubTest", "addDuration")

    def __init__(self):
        super().__init__()
        self.appels = []
        self.echec = False

    def __getattribute__(self, nom):
        if nom in _ResultatEnregistre.METHODES:
            appels = object.__getattribute__(self, "appels")

            def noter(*arguments):
                appels.append((nom, arguments))
                if nom in ("addFailure", "addError", "addUnexpectedSuccess") or (
                        nom == "addSubTest" and len(arguments) > 2 and arguments[2] is not None):
                    object.__setattr__(self, "echec", True)
            return noter
        return object.__getattribute__(self, nom)

    def rejouer(self, resultat):
        for nom, arguments in self.appels:
            methode = getattr(resultat, nom, None)
            if methode is not None:
                methode(*arguments)


# ---------------------------------------------------------------------------
# Aides pour les pages
# ---------------------------------------------------------------------------

def preregler_profil(contexte, type, nom="", technicien_id="", poste="Poste test"):
    """Mémorise un profil et un poste dans localStorage avant tout chargement de page.

    type : 'demandeur' | 'technicien' | 'responsable'. Écrit prevo.profil (JSON
    {type, nom, technicienId}, ARCHITECTURE.md §8) et prevo.poste. N'écrase pas une valeur déjà
    présente : un test qui change de profil puis recharge la page garde son nouveau profil.
    """
    profil = json.dumps({"type": type, "nom": nom, "technicienId": technicien_id})
    script = """
    (() => {
      try {
        if (localStorage.getItem('prevo.profil') === null) {
          localStorage.setItem('prevo.profil', %s);
        }
        if (localStorage.getItem('prevo.poste') === null) {
          localStorage.setItem('prevo.poste', %s);
        }
      } catch (erreur) { /* page sans stockage (about:blank) : rien à faire */ }
    })();
    """ % (json.dumps(profil), json.dumps(poste))
    contexte.add_init_script(script)


def attendre_pret(page, delai_ms=15000):
    """Attend que l'application soit prête : <html data-etat="pret">.

    En cas de dépassement, l'erreur dit où en était l'application (état, mode, texte visible),
    pour qu'un échec passager puisse être compris."""
    try:
        page.wait_for_function(
            "document.documentElement.dataset.etat === 'pret'", timeout=delai_ms)
    except Exception as erreur:
        try:
            etat = page.evaluate("""() => ({ etat: document.documentElement.dataset.etat,
                mode: (typeof App !== 'undefined' && App.mode) || null, url: location.href,
                texte: (document.body ? document.body.innerText : '').replace(/\\s+/g, ' ').slice(0, 400) })""")
        except Exception as autre:  # page fermée ou bloquée
            etat = "état illisible (%s)" % (autre,)
        raise AssertionError("application pas prête en %d ms : %r\n(%s)" % (delai_ms, etat, erreur)) from erreur


def installer_dossier_simule(contexte, nom="donnees-test"):
    """Remplace window.showDirectoryPicker par un sous-dossier de l'OPFS du navigateur.

    L'OPFS (navigator.storage.getDirectory) n'existe qu'en http://127.0.0.1 (pas en file://) :
    à utiliser avec ServeurStatique ou ServeurPrevo. Les poignées OPFS n'ont pas
    queryPermission/requestPermission : on les ajoute (réponse 'granted') si elles manquent.
    """
    script = """
    (() => {
      const nomDossier = %s;
      const prototype = (window.FileSystemHandle && window.FileSystemHandle.prototype) || null;
      if (prototype) {
        if (!prototype.queryPermission) { prototype.queryPermission = async function () { return 'granted'; }; }
        if (!prototype.requestPermission) { prototype.requestPermission = async function () { return 'granted'; }; }
      }
      window.showDirectoryPicker = async function () {
        const racineOpfs = await navigator.storage.getDirectory();
        return racineOpfs.getDirectoryHandle(nomDossier, { create: true });
      };
    })();
    """ % json.dumps(nom)
    contexte.add_init_script(script)


def charger_scripts(page, chemins):
    """Ouvre tests/fixtures/page-vide.html en file:// et y ajoute les scripts du projet, dans l'ordre.

    chemins : chemins relatifs à la racine du projet, ex. ['js/schema.js', 'js/donnees.js'].
    Les scripts sont chargés comme de vrais <script src> classiques (donc comme dans index.html).
    """
    page.goto(url_fichier(PAGE_VIDE))
    for chemin in chemins:
        fichier = (RACINE / chemin)
        if not fichier.is_file():
            raise FileNotFoundError("script introuvable : " + str(fichier))
        page.add_script_tag(url=url_fichier(fichier))
