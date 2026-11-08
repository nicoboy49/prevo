"""Met à jour les captures d'écran de Prévo (ARCHITECTURE.md §17.8 ; lot 7, T177).

Écrit :
  - docs/captures/<nom>.png : captures en taille réelle, pour le README (docs/captures/accueil.png) ;
  - GUIDE.html : l'attribut src de chaque <img data-capture="<nom>"> reçoit la capture en JPEG
    réduit, intégrée en base64 (« data:image/jpeg;base64,… »), avec sa largeur et sa hauteur.
    Toutes les images du guide pèsent 1,5 Mo au plus (texte base64 compris) : la qualité JPEG
    baisse, puis la largeur, jusqu'à tenir dans ce budget.

Outil de développement (Playwright et Chromium, déjà utilisés par les tests ; aucune autre
bibliothèque), jamais lancé par les tests. Deux sortes de captures :
  - les écrans de l'application : Prévo est ouvert en file:// puis « Essayer avec les données de démo ».
    La démo vit en mémoire : rien n'est écrit dans donnees/ ;
  - les écrans du lot 7 qui exigent un serveur (connexion, assistant d'installation, Équipe › Accès,
    porte d'entrée sur un téléphone) : l'outil lance les serveurs de test de tests/commun.py et
    tests/atelier.py (serveur.py sur une copie temporaire, comptes fictifs, faux mkcert : aucune commande
    d'administrateur, aucune sortie du PC, jamais le dossier donnees/ réel). Les captures de la porte
    jouent les profils Playwright « Pixel 7 » et « iPhone 14 » sur l'adresse réseau de ce PC (comme
    tests/test_acces_porte.py) : sans adresse réseau ou sans openssl, ces deux captures échouent et
    leur ancienne image est gardée. L'étape « démarrage » de l'assistant (jouée en « aucun » pour le
    récapitulatif) écrit ses scripts à côté de serveur.py sans les lancer : l'outil les retire à la fin.
Chaque capture a son propre contexte de navigateur neuf (profil réglé avant le chargement, comme
tests/commun.py preregler_profil) : l'assistant IA n'y est jamais actif, le thème est celui par défaut
(sombre). La réduction en JPEG est faite par Chromium (canvas).

Lancer depuis la racine du projet :
    py outils/generer_captures.py                     toutes les captures
    py outils/generer_captures.py accueil planning    seulement celles-ci (les autres images du
                                                      guide restent telles quelles)
    py outils/generer_captures.py --vider             retire les images du guide (src vide), pour
                                                      relire ou modifier son texte ; relancer ensuite
                                                      sans option pour les remettre
    py outils/generer_captures.py --langue en         les mêmes captures, Prévo en anglais (T338) :
                                                      docs/captures/en/<nom>.png (README.md) et les
                                                      images de GUIDE.en.html ; les données de la démo
                                                      restent en français (elles ne sont pas traduites)
Code de sortie : 0 si tout est fait, 1 si une capture a échoué (son ancienne image est gardée).
"""
import argparse
import base64
import csv
import datetime
import importlib.util
import json
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_CAPTURES = RACINE / "docs" / "captures"
FICHIER_GUIDE = RACINE / "GUIDE.html"
# T338 : langue des captures (« fr » : GUIDE.html et docs/captures/ ; « en » : GUIDE.en.html et docs/captures/en/).
# Posée par choisir_langue avant toute capture ; le navigateur reçoit la locale et le choix du poste (prevo.langue).
LANGUES_CAPTURES = {
    "fr": {"guide": RACINE / "GUIDE.html", "dossier": RACINE / "docs" / "captures", "locale": "fr-FR",
           "postes": {"telephone": "Téléphone", "bureau": "PC atelier"}},
    "en": {"guide": RACINE / "GUIDE.en.html", "dossier": RACINE / "docs" / "captures" / "en", "locale": "en-GB",
           "postes": {"telephone": "Phone", "bureau": "Workshop PC"}},
}
LANGUE = "fr"


def choisir_langue(code):
    """Langue des captures : fichiers écrits (guide, dossier des PNG) et réglages du navigateur."""
    global LANGUE, FICHIER_GUIDE, DOSSIER_CAPTURES
    LANGUE = code
    FICHIER_GUIDE = LANGUES_CAPTURES[code]["guide"]
    DOSSIER_CAPTURES = LANGUES_CAPTURES[code]["dossier"]
FICHIER_SCENARIOS = RACINE / "tests" / "fixtures" / "demo-scenarios.json"   # écrit par outils/generer_demo.py
FICHIER_PARC = RACINE / "tests" / "fixtures" / "import" / "equipements.xlsx"   # fichier d'essai du lot 5
FICHIER_EQUIPEMENTS_DEMO = RACINE / "donnees" / "demo" / "equipements.csv"      # écrit par outils/generer_demo.py

BUDGET_GUIDE = 1500000          # octets de texte base64, toutes images du guide comprises (§17.8)
QUALITES_JPEG = (0.82, 0.76, 0.70, 0.64, 0.58, 0.52, 0.46)
REDUCTION_LARGEUR = 0.9         # si la qualité la plus basse ne suffit pas, les images rétrécissent
DELAI_MS = 20000
# Heure des captures (date du jour) : l'accueil du responsable dit « Ce matin dans l'atelier » (T91).
HEURE_CAPTURES = "09:30:00"

# Appareils : écran de bureau 1440 × 900, téléphone 375 × 812 (pixels doublés, comme un vrai téléphone) ;
# « android » et « iphone » : les profils Playwright (agent, écran, tactile) d'un Pixel 7 et d'un iPhone 14, pour la
# porte d'entrée, qui reconnaît le système du téléphone (ARCHITECTURE.md §22.6).
APPAREILS = {
    "bureau": {"contexte": {"viewport": {"width": 1440, "height": 900}, "device_scale_factor": 1},
               "largeur_guide": 1200},
    "telephone": {"contexte": {"viewport": {"width": 375, "height": 812}, "device_scale_factor": 2,
                               "is_mobile": True, "has_touch": True},
                  "largeur_guide": 500},
    "android": {"profil_playwright": "Pixel 7", "largeur_guide": 500},
    "iphone": {"profil_playwright": "iPhone 14", "largeur_guide": 500},
}

PROFILS = {
    "responsable": {"type": "responsable", "nom": "Responsable", "technicienId": ""},
    "demandeur": {"type": "demandeur", "nom": "Lucie Martin", "technicienId": ""},
}

# Comptes fictifs des captures en mode comptes (lot 7) : aucune personne réelle ; le technicien est celui de la démo.
COMPTES_CAPTURES = [
    ("claire.fontaine", "Claire", "Fontaine", "responsable", "une phrase de passe de demo", ""),
    ("julien.moreau", "Julien", "Moreau", "technicien", "cle a molette et graisse", "TEC-0001"),
    ("lucie.martin", "Lucie", "Martin", "demandeur", "une demande de lucie 2026", ""),
]
AGENT_CAPTURES = "Captures-Prevo/1.0"
# Scripts que l'étape « démarrage » de l'assistant écrit à côté de serveur.py (§22.9), retirés après la capture.
SCRIPTS_DEMARRAGE = tuple(RACINE / nom for nom in ("Installer_demarrage.ps1", "Retirer_demarrage.ps1", "Demarrage_session.ps1"))


def scenario(role):
    """Identifiant d'un objet de scénario du jeu de démo (aucun identifiant écrit en dur ici)."""
    return json.loads(FICHIER_SCENARIOS.read_text(encoding="utf-8"))[role]


def equipement_demo(repere):
    """Identifiant d'un équipement du jeu de démo d'après son repère (lot 6 : page du wiki d'une machine)."""
    with open(FICHIER_EQUIPEMENTS_DEMO, encoding="utf-8-sig", newline="") as fichier:
        for ligne in csv.DictReader(fichier, delimiter=";"):
            if (ligne.get("repere") or "").lstrip("'") == repere:     # apostrophe de protection Excel
                return ligne["id"]
    raise KeyError("équipement de démo introuvable : " + repere)


# Chaque capture : appareil, profil, route, élément attendu avant la photo, préparation éventuelle.
# Lot 7 : « serveur » (comptes | assistant | atelier) remplace la démo en file:// ; « session » pose la session du
# compte de ce rôle ; « preparer_serveur » joue d'abord des appels à l'API (l'assistant jusqu'au récapitulatif).
CAPTURES = [
    {"nom": "accueil", "appareil": "bureau", "profil": "responsable", "route": "#/accueil",
     "attendre": "#contenu .accueil-instruments"},
    {"nom": "signaler", "appareil": "telephone", "profil": "demandeur",
     "route": lambda: "#/di/nouvelle?equipement=" + scenario("causes_equipement"),     # comme après un QR scanné
     "attendre": "#contenu textarea[name=description]", "preparer": "signaler"},
    {"nom": "ot", "appareil": "bureau", "profil": "responsable", "route": lambda: "#/ot/" + scenario("ot_statut_en_cours"),
     "attendre": "#contenu .ot-onglets"},
    {"nom": "indicateurs", "appareil": "bureau", "profil": "responsable", "route": "#/indicateurs",
     "attendre": "#contenu [data-graphique]", "preparer": "graphiques"},
    {"nom": "planning", "appareil": "bureau", "profil": "responsable", "route": "#/planning",
     "attendre": "#contenu .pl-case"},
    {"nom": "suggestions", "appareil": "bureau", "profil": "responsable", "route": "#/preventif?onglet=suggestions",
     "attendre": "#contenu .sg-carte"},
    {"nom": "poste", "appareil": "bureau", "profil": "responsable", "route": "#/poste",
     "attendre": "#contenu #carte-ia"},
    {"nom": "import", "appareil": "bureau", "profil": "responsable", "route": "#/import",
     "attendre": '#contenu .import-etape[data-etape="1"]', "preparer": "import"},
    # Lot 6 (T125) : l'accueil du wiki (responsable : « Suivi du wiki » affiché) et la page d'une machine de la
    # démo dont le texte « En bref » a des petits numéros de référence (CP-01, compresseur).
    {"nom": "wiki", "appareil": "bureau", "profil": "responsable", "route": "#/wiki",
     "attendre": "#contenu .wiki-accueil #wiki-suivi"},
    {"nom": "wiki-page", "appareil": "bureau", "profil": "responsable",
     "route": lambda: "#/wiki/" + equipement_demo("CP-01"),
     "attendre": "#contenu .wiki-page[data-type=machine] .wiki-ref"},
    # Lot 7 (T177) : écrans de l'accès et de l'installation, sur des serveurs de test.
    {"nom": "connexion", "appareil": "bureau", "serveur": "comptes", "route": "/",
     "attendre": "#connexion-formulaire:not([hidden])", "preparer": "connexion"},
    {"nom": "equipe-acces", "appareil": "bureau", "serveur": "comptes", "session": "responsable",
     "route": "/#/equipe/acces", "attendre": "#acces-comptes tbody tr"},
    {"nom": "installation", "appareil": "bureau", "serveur": "assistant", "route": "/#/installation",
     "attendre": '#installation-contenu section.installation-etape[data-etape="situation"] .installation-choix'},
    {"nom": "installation-fiche", "appareil": "bureau", "serveur": "assistant", "route": "/#/installation",
     "attendre": "#inst-fiche #fiche-qr-ouvrir svg", "preparer_serveur": "assistant_solo_jusqu_au_recapitulatif"},
    {"nom": "porte-android", "appareil": "android", "serveur": "atelier",
     "route": lambda: "/#/equipement/" + scenario("causes_equipement"), "attendre": "#etapes-android:not([hidden])"},
    {"nom": "porte-iphone", "appareil": "iphone", "serveur": "atelier",
     "route": lambda: "/#/equipement/" + scenario("causes_equipement"), "attendre": "#etapes-iphone:not([hidden])"},
]

# Avant le chargement : profil et nom du poste mémorisés (le choix du profil est sauté).
SCRIPT_PROFIL = """
(() => {
  try {
    localStorage.setItem('prevo.profil', %s);
    localStorage.setItem('prevo.poste', %s);
  } catch (erreur) { /* page sans stockage : rien à faire */ }
})();
"""

# Réduction d'une capture PNG en JPEG par le canvas de Chromium : rend une adresse data:image/jpeg.
SCRIPT_JPEG = """
async ([png, largeur, qualite]) => {
  const image = new Image();
  image.src = 'data:image/png;base64,' + png;
  await image.decode();
  const echelle = Math.min(1, largeur / image.naturalWidth);
  const toile = document.createElement('canvas');
  toile.width = Math.round(image.naturalWidth * echelle);
  toile.height = Math.round(image.naturalHeight * echelle);
  const dessin = toile.getContext('2d');
  dessin.imageSmoothingEnabled = true;
  dessin.imageSmoothingQuality = 'high';
  dessin.drawImage(image, 0, 0, toile.width, toile.height);
  return [toile.toDataURL('image/jpeg', qualite), toile.width, toile.height];
}
"""


# ---------------------------------------------------------------------------
# Serveurs de test (lot 7) : tests/commun.py et tests/atelier.py, importés à la demande
# ---------------------------------------------------------------------------

def charger_serveur_module():
    """serveur.py importé comme module (pour créer les comptes fictifs), comme tests/atelier.py."""
    specification = importlib.util.spec_from_file_location("serveur_prevo_captures", RACINE / "serveur.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def requete_json(url, chemin, corps=None, methode=None, cookie=None):
    """Un appel à l'API du serveur de test (JSON) ; rend (statut, en-têtes, objet)."""
    donnees = None if corps is None else json.dumps(corps).encode("utf-8")
    entetes = {"User-Agent": AGENT_CAPTURES, "Accept": "application/json"}
    if donnees is not None:
        entetes["Content-Type"] = "application/json; charset=utf-8"
        entetes["X-Prevo"] = "1"
    if cookie:
        entetes["Cookie"] = cookie
    requete = urllib.request.Request(url + chemin, data=donnees, method=methode or ("POST" if donnees is not None else "GET"),
                                     headers=entetes)
    try:
        with urllib.request.urlopen(requete, timeout=30) as reponse:
            return reponse.status, dict(reponse.headers), json.loads(reponse.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as erreur:
        texte = erreur.read().decode("utf-8", "replace")
        raise RuntimeError("%s %s : %s %s" % (requete.get_method(), chemin, erreur.code, texte[:300]))


class ServeursDeCapture:
    """Serveurs de test lancés une fois chacun, à la demande, et arrêtés à la fin.

    comptes   : serveur.py sur une copie de la démo, comptes exigés, trois comptes fictifs (COMPTES_CAPTURES) ;
    assistant : serveur.py sur un dossier de données vide, sans configuration : l'assistant d'installation ;
    atelier   : tests/atelier.py ServeurAtelier (portée « atelier », porte d'entrée, certificat du faux mkcert).
    """

    def __init__(self):
        sys.path.insert(0, str(RACINE / "tests"))
        self.serveurs = {}
        self.dossiers = []
        self.cookies = {}
        self.fichiers_produits = []        # scripts écrits par l'API dans le dossier de Prévo, à retirer à la fin

    def url(self, nom):
        """Origine http du serveur (le téléphone simulé voit la porte à l'adresse réseau du PC)."""
        serveur = self.obtenir(nom)
        return serveur.url_porte if nom == "atelier" else serveur.url

    def obtenir(self, nom):
        if nom not in self.serveurs:
            self.serveurs[nom] = getattr(self, "lancer_" + nom)()
        return self.serveurs[nom]

    def lancer_comptes(self):
        import commun
        serveur_module = charger_serveur_module()
        racine = Path(tempfile.mkdtemp(prefix="prevo-captures-"))
        self.dossiers.append(racine)
        source = racine / "source"
        shutil.copytree(commun.DOSSIER_DEMO, source)
        config = serveur_module.Configuration(str(source), [])
        serveur_module.creer_dossiers(config)
        for identifiant, prenom, nom, role, mot_de_passe, technicien_id in COMPTES_CAPTURES:
            serveur_module.creer_compte(config, prenom, nom, role, mot_de_passe, technicien_id=technicien_id,
                                        identifiant=identifiant)
        configuration = racine / "prevo.config.json"
        configuration.write_text(json.dumps({"comptes": True}), encoding="utf-8")
        serveur = commun.ServeurPrevo(source=source, arguments=["--config", str(configuration)])
        serveur.demarrer()
        return serveur

    def lancer_assistant(self):
        import commun
        serveur = commun.ServeurPrevo(source=None)        # dossier vide, aucune configuration : l'assistant
        serveur.demarrer()
        return serveur

    def lancer_atelier(self):
        import atelier
        serveur = atelier.ServeurAtelier()
        serveur.demarrer()                                 # SkipTest (adresse réseau, openssl) remonte en échec
        return serveur

    def cookie(self, nom, role):
        """Cookie « id=<jeton> » d'une session du compte fictif de ce rôle (serveur « comptes »)."""
        cle = (nom, role)
        if cle not in self.cookies:
            compte = next(c for c in COMPTES_CAPTURES if c[3] == role)
            _, entetes, _ = requete_json(self.url(nom), "/api/connexion",
                                         {"identifiant": compte[0], "mot_de_passe": compte[4], "rester": False})
            self.cookies[cle] = entetes.get("Set-Cookie", "").split(";")[0]
        return self.cookies[cle]

    def preparer(self, nom_preparation):
        """Appels à l'API avant une capture (rien d'administrateur, aucune relance : voir chaque préparation)."""
        if nom_preparation == "assistant_solo_jusqu_au_recapitulatif":
            # L'assistant en Solo « ce PC » jusqu'à l'étape 8 : situation, portée, compte (le technicien « moi »,
            # sans mot de passe), démarrage « aucun » (rien n'est lancé), sauvegardes plus tard, « Rester ici ».
            url = self.url("assistant")
            for etape, corps in (("situation", {"situation": "seul"}), ("portee", {"portee": "ce-pc"}),
                                 ("compte", {"prenom": "Claire", "nom": "Fontaine"}),
                                 ("demarrage", {"demarrage": "aucun", "veille_desactivee": False}),
                                 ("sauvegardes", {"dossier": ""}), ("deplacer", {"rester": True})):
                scripts_avant = {chemin for chemin in SCRIPTS_DEMARRAGE if chemin.is_file()}
                _, _, reponse = requete_json(url, "/api/installation/" + etape, corps)
                # Les scripts de démarrage (§22.9) sont écrits dans le dossier de Prévo, jamais lancés ici
                # (demarrage « aucun ») : ceux qui n'existaient pas avant sont retirés par arreter().
                produits = [Path(c) for c in (reponse.get("scripts") or {}).values()] if isinstance(reponse, dict) else []
                for chemin in produits + list(SCRIPTS_DEMARRAGE):
                    if chemin.is_file() and chemin not in scripts_avant and chemin not in self.fichiers_produits:
                        self.fichiers_produits.append(chemin)
        else:
            raise KeyError("préparation de serveur inconnue : " + nom_preparation)

    def arreter(self):
        for serveur in self.serveurs.values():
            try:
                serveur.arreter()
            except Exception as erreur:           # l'arrêt d'un serveur n'empêche pas celui des autres
                print("  (arrêt d'un serveur de test : %s)" % erreur)
        self.serveurs = {}
        for dossier in self.dossiers:
            shutil.rmtree(dossier, ignore_errors=True)
        self.dossiers = []
        for chemin in self.fichiers_produits:
            try:
                chemin.unlink()
            except FileNotFoundError:
                pass
        self.fichiers_produits = []


# ---------------------------------------------------------------------------
# Prise des captures
# ---------------------------------------------------------------------------

def preparer(page, nom):
    """Mise en scène propre à certains écrans (rien n'est enregistré : la démo vit en mémoire)."""
    if nom == "signaler":
        # Symptôme saisi et impact choisi : la priorité calculée s'affiche. Puis retour en haut du formulaire.
        page.fill("#contenu input[name=symptome]", "Fuite d'huile")
        page.click("#contenu .tuile:has(input[name=impact][value='dégradé'])")
        page.evaluate("() => { document.activeElement && document.activeElement.blur(); window.scrollTo(0, 0); }")
    elif nom == "graphiques":
        # Les graphiques se dessinent après l'écran : attendre qu'aucun ne soit encore en chargement.
        page.wait_for_function(
            "() => !document.querySelector('#contenu [data-graphique][data-etat=\"chargement\"]')",
            timeout=DELAI_MS)
        page.wait_for_timeout(1500)          # fin des animations des graphiques
    elif nom == "import":
        # Lot 5 : la liste du parc d'essai (equipements.xlsx) jusqu'à l'aperçu ; rien n'est écrit.
        page.check('input[name="import-type"][value="equipements"]')
        page.click("#import-continuer")
        page.wait_for_selector('.import-etape[data-etape="2"]', timeout=DELAI_MS)
        page.set_input_files("#import-fichier", str(FICHIER_PARC))
        page.wait_for_selector("#import-lu:not([hidden]) #import-titres", timeout=DELAI_MS)
        for etape in (3, 4):
            page.click("#import-continuer")
            page.wait_for_selector('.import-etape[data-etape="%d"]' % etape, timeout=DELAI_MS)
        page.wait_for_selector("#contenu [data-total]", timeout=DELAI_MS)
        page.evaluate("() => window.scrollTo(0, 0)")
    elif nom == "connexion":
        # Identifiant du responsable fictif saisi, mot de passe masqué : rien n'est envoyé.
        page.fill("#connexion-identifiant", COMPTES_CAPTURES[0][0])
        page.fill("#connexion-mot-de-passe", COMPTES_CAPTURES[0][4])
        page.evaluate("() => { document.activeElement && document.activeElement.blur(); }")


def options_contexte(playwright, appareil):
    """Options du contexte Playwright d'un appareil (profil Playwright d'un téléphone, ou taille d'écran)."""
    if "profil_playwright" in appareil:
        profil = dict(playwright.devices[appareil["profil_playwright"]])
        profil.pop("default_browser_type", None)       # joué dans Chromium, comme tests/test_acces_porte.py
        return profil
    return dict(appareil["contexte"])


def prendre_capture(playwright, navigateur, serveurs, capture):
    """Ouvre Prévo (démo en file://, ou serveur de test) à l'écran demandé et rend la capture PNG (octets)."""
    appareil = APPAREILS[capture["appareil"]]
    reglages = LANGUES_CAPTURES[LANGUE]
    contexte = navigateur.new_context(locale=reglages["locale"], **options_contexte(playwright, appareil))
    contexte.set_default_timeout(DELAI_MS)
    # Aide à l'écran coupée : les captures du guide montrent l'écran lui-même.
    contexte.add_init_script("try { localStorage.setItem('prevo.aideActive', '0'); } catch (e) {}")
    if LANGUE != "fr":                      # T338 : la langue choisie sur ce poste (démo, application, porte)
        contexte.add_init_script("try { localStorage.setItem('prevo.langue', %s); } catch (e) {}" % json.dumps(LANGUE))
    contexte.clock.set_fixed_time(datetime.date.today().isoformat() + "T" + HEURE_CAPTURES)
    try:
        route = capture["route"]() if callable(capture["route"]) else capture["route"]
        if capture.get("serveur"):
            nom_serveur = capture["serveur"]
            if capture.get("preparer_serveur"):
                serveurs.preparer(capture["preparer_serveur"])
            url = serveurs.url(nom_serveur)
            if capture.get("session"):
                cookie = serveurs.cookie(nom_serveur, capture["session"])
                contexte.add_cookies([{"name": "id", "value": cookie.split("=", 1)[1], "url": url,
                                       "httpOnly": True, "sameSite": "Lax"}])
            page = contexte.new_page()
            erreurs = []
            page.on("pageerror", lambda erreur: erreurs.append(str(erreur)))
            page.goto(url + route)
        else:
            profil = PROFILS[capture["profil"]]
            poste = reglages["postes"]["telephone" if capture["appareil"] == "telephone" else "bureau"]
            contexte.add_init_script(SCRIPT_PROFIL % (json.dumps(json.dumps(profil)), json.dumps(poste)))
            page = contexte.new_page()
            erreurs = []
            page.on("pageerror", lambda erreur: erreurs.append(str(erreur)))
            page.goto((RACINE / "index.html").resolve().as_uri())
            page.click("#btn-demo")
            page.wait_for_function("document.documentElement.dataset.etat === 'pret'", timeout=DELAI_MS)
            page.evaluate("route => { location.hash = route; }", route)
        page.wait_for_selector(capture["attendre"], timeout=DELAI_MS)
        if capture.get("preparer"):
            preparer(page, capture["preparer"])
        page.evaluate("() => document.fonts.ready")
        page.wait_for_timeout(500)
        # Les notifications passagères (toasts) ne font pas partie de l'écran.
        page.evaluate("() => document.querySelectorAll('.toast.visible').forEach((t) => t.classList.remove('visible'))")
        png = page.screenshot(animations="disabled", caret="hide")
        if erreurs:
            raise RuntimeError("erreur JavaScript pendant la capture : " + " | ".join(erreurs))
        return png
    finally:
        contexte.close()


def en_jpeg(page_outil, png, largeur, qualite):
    """(adresse data:image/jpeg;base64,…, largeur, hauteur) d'une capture PNG réduite."""
    return tuple(page_outil.evaluate(SCRIPT_JPEG, [base64.b64encode(png).decode("ascii"), largeur, qualite]))


def images_du_guide(page_outil, pngs):
    """{nom: (adresse, largeur, hauteur)} pour les captures données, toutes dans le budget du guide.

    Le budget compte aussi les images du guide qui ne sont pas refaites cette fois-ci."""
    autres = sum(len(adresse) for nom, adresse in adresses_actuelles().items() if nom not in pngs)
    facteur = 1.0
    while True:
        for qualite in QUALITES_JPEG:
            images = {}
            for nom, (png, appareil) in pngs.items():
                largeur = max(200, int(APPAREILS[appareil]["largeur_guide"] * facteur))
                images[nom] = en_jpeg(page_outil, png, largeur, qualite)
            total = autres + sum(len(image[0]) for image in images.values())
            if total <= BUDGET_GUIDE:
                print("  Images du guide : qualité %d %%, largeur x %.2f, %d octets en tout (budget %d)."
                      % (round(qualite * 100), facteur, total, BUDGET_GUIDE))
                return images
        facteur *= REDUCTION_LARGEUR
        if facteur < 0.3:
            raise RuntimeError("impossible de faire tenir les images du guide dans %d octets" % BUDGET_GUIDE)


# ---------------------------------------------------------------------------
# GUIDE.html : balises <img data-capture="…">
# ---------------------------------------------------------------------------

MOTIF_IMG = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
MOTIF_NOM = re.compile(r'\bdata-capture="([^"]*)"')
MOTIF_COMMENTAIRE = re.compile(r"(<!--.*?-->)", re.DOTALL)


def hors_commentaires(texte, traiter):
    """Applique traiter(morceau) aux seuls morceaux du HTML situés hors des commentaires <!-- … -->."""
    return "".join(morceau if MOTIF_COMMENTAIRE.fullmatch(morceau) else traiter(morceau)
                   for morceau in MOTIF_COMMENTAIRE.split(texte))


def poser_attribut(balise, nom, valeur):
    """Balise <img …> avec l'attribut nom="valeur" (remplacé s'il existe, ajouté sinon)."""
    motif = re.compile(r'\b%s="[^"]*"' % re.escape(nom))
    nouveau = '%s="%s"' % (nom, valeur)
    if motif.search(balise):
        return motif.sub(lambda _: nouveau, balise, count=1)
    return balise[:-1].rstrip("/ ") + " " + nouveau + ">"


def lire_guide():
    with open(FICHIER_GUIDE, encoding="utf-8", newline="") as fichier:
        return fichier.read()


def ecrire_guide(texte):
    with open(FICHIER_GUIDE, "w", encoding="utf-8", newline="") as fichier:
        fichier.write(texte)


def adresses_actuelles():
    """{nom: valeur de src} des images data-capture du guide (vide si le guide n'existe pas)."""
    if not FICHIER_GUIDE.is_file():
        return {}
    adresses = {}

    def noter(morceau):
        for balise in MOTIF_IMG.findall(morceau):
            nom = MOTIF_NOM.search(balise)
            if nom:
                src = re.search(r'\bsrc="([^"]*)"', balise)
                adresses[nom.group(1)] = src.group(1) if src else ""
        return morceau

    hors_commentaires(lire_guide(), noter)
    return adresses


def mettre_a_jour_guide(images, vider=False):
    """Remplace src, width et height des <img data-capture> concernées ; rend les noms modifiés."""
    texte = lire_guide()
    modifies = []

    def remplacer(trouve):
        balise = trouve.group(0)
        nom = MOTIF_NOM.search(balise)
        if not nom:
            return balise
        nom = nom.group(1)
        if vider:
            modifies.append(nom)
            return poser_attribut(balise, "src", "")
        if nom not in images:
            return balise
        adresse, largeur, hauteur = images[nom]
        modifies.append(nom)
        balise = poser_attribut(balise, "src", adresse)
        balise = poser_attribut(balise, "width", str(largeur))
        return poser_attribut(balise, "height", str(hauteur))

    ecrire_guide(hors_commentaires(texte, lambda morceau: MOTIF_IMG.sub(remplacer, morceau)))
    return modifies


# ---------------------------------------------------------------------------
# Programme
# ---------------------------------------------------------------------------

def main(arguments=None):
    analyseur = argparse.ArgumentParser(description="Captures d'écran de Prévo (README et GUIDE.html).")
    analyseur.add_argument("noms", nargs="*", help="captures à refaire (défaut : toutes) : "
                           + ", ".join(c["nom"] for c in CAPTURES))
    analyseur.add_argument("--vider", action="store_true", help="retirer les images du guide (src vide)")
    analyseur.add_argument("--langue", choices=sorted(LANGUES_CAPTURES), default="fr",
                           help="langue de Prévo sur les captures (défaut fr : GUIDE.html ; en : GUIDE.en.html)")
    options = analyseur.parse_args(arguments)
    choisir_langue(options.langue)
    nom_guide = FICHIER_GUIDE.name
    dossier_affiche = DOSSIER_CAPTURES.relative_to(RACINE).as_posix()
    if hasattr(sys.stdout, "reconfigure"):      # accents lisibles dans toutes les consoles
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if options.vider:
        if not FICHIER_GUIDE.is_file():
            print("%s introuvable." % nom_guide)
            return 1
        print("Images retirées de %s : %s" % (nom_guide, ", ".join(mettre_a_jour_guide({}, vider=True))))
        return 0

    inconnus = [nom for nom in options.noms if nom not in {c["nom"] for c in CAPTURES}]
    if inconnus:
        analyseur.error("capture inconnue : " + ", ".join(inconnus))
    choisies = [c for c in CAPTURES if not options.noms or c["nom"] in options.noms]

    from playwright.sync_api import sync_playwright   # outil de développement, comme les tests
    DOSSIER_CAPTURES.mkdir(parents=True, exist_ok=True)
    pngs, echecs = {}, []
    serveurs = ServeursDeCapture()
    with sync_playwright() as p:
        navigateur = p.chromium.launch(headless=True)
        try:
            for capture in choisies:
                try:
                    png = prendre_capture(p, navigateur, serveurs, capture)
                except BaseException as erreur:      # une capture ratée (SkipTest compris) n'empêche pas les autres
                    if isinstance(erreur, KeyboardInterrupt):
                        raise
                    echecs.append(capture["nom"])
                    print("ÉCHEC  %-18s %s" % (capture["nom"], (str(erreur).splitlines() or [repr(erreur)])[0]))
                    continue
                (DOSSIER_CAPTURES / (capture["nom"] + ".png")).write_bytes(png)
                pngs[capture["nom"]] = (png, capture["appareil"])
                print("Écrit  %s/%s.png (%d octets)" % (dossier_affiche, capture["nom"], len(png)))

            if not FICHIER_GUIDE.is_file():
                print("%s introuvable : seules les captures PNG ont été écrites." % nom_guide)
            elif pngs:
                page_outil = navigateur.new_page()
                page_outil.set_content("<!doctype html><title>captures</title>")
                images = images_du_guide(page_outil, pngs)
                modifies = mettre_a_jour_guide(images)
                print("%s : images mises à jour : %s" % (nom_guide, ", ".join(modifies) or "aucune"))
                sans_place = sorted(set(images) - set(modifies))
                if sans_place:
                    print("  (sans <img data-capture> dans le guide : %s)" % ", ".join(sans_place))
                vides = sorted(nom for nom, adresse in adresses_actuelles().items() if not adresse)
                if vides:
                    print("  ATTENTION : images encore vides dans le guide : %s" % ", ".join(vides))
        finally:
            navigateur.close()
            serveurs.arreter()
    if echecs:
        print("Captures ratées (ancienne image gardée) : %s" % ", ".join(echecs))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
