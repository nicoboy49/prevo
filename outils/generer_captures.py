"""Met à jour les captures d'écran de Prévo (ARCHITECTURE.md §17.8).

Écrit :
  - docs/captures/<nom>.png : captures en taille réelle, pour le README (docs/captures/accueil.png) ;
  - GUIDE.html : l'attribut src de chaque <img data-capture="<nom>"> reçoit la capture en JPEG
    réduit, intégrée en base64 (« data:image/jpeg;base64,… »), avec sa largeur et sa hauteur.
    Toutes les images du guide pèsent 1,5 Mo au plus (texte base64 compris) : la qualité JPEG
    baisse, puis la largeur, jusqu'à tenir dans ce budget.

Outil de développement (Playwright et Chromium, déjà utilisés par les tests ; aucune autre
bibliothèque) : Prévo est ouvert en file:// puis « Essayer avec les données de démo ». La démo vit
en mémoire : rien n'est écrit dans donnees/. Chaque capture a son propre navigateur neuf (profil
réglé avant le chargement, comme tests/commun.py preregler_profil) : l'assistant IA n'y est jamais
actif, le thème est celui par défaut (sombre). La réduction en JPEG est faite par Chromium (canvas).

Lancer depuis la racine du projet :
    py outils/generer_captures.py                     toutes les captures
    py outils/generer_captures.py accueil planning    seulement celles-ci (les autres images du
                                                      guide restent telles quelles)
    py outils/generer_captures.py --vider             retire les images du guide (src vide), pour
                                                      relire ou modifier son texte ; relancer ensuite
                                                      sans option pour les remettre
Code de sortie : 0 si tout est fait, 1 si une capture a échoué (son ancienne image est gardée).
"""
import argparse
import base64
import datetime
import json
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_CAPTURES = RACINE / "docs" / "captures"
FICHIER_GUIDE = RACINE / "GUIDE.html"
FICHIER_SCENARIOS = RACINE / "tests" / "fixtures" / "demo-scenarios.json"   # écrit par outils/generer_demo.py

BUDGET_GUIDE = 1500000          # octets de texte base64, toutes images du guide comprises (§17.8)
QUALITES_JPEG = (0.82, 0.76, 0.70, 0.64, 0.58, 0.52, 0.46)
REDUCTION_LARGEUR = 0.9         # si la qualité la plus basse ne suffit pas, les images rétrécissent
DELAI_MS = 20000
# Heure des captures (date du jour) : l'accueil du responsable dit « Ce matin dans l'atelier » (T91).
HEURE_CAPTURES = "09:30:00"

# Appareils : écran de bureau 1440 × 900, téléphone 375 × 812 (pixels doublés, comme un vrai téléphone).
APPAREILS = {
    "bureau": {"contexte": {"viewport": {"width": 1440, "height": 900}, "device_scale_factor": 1},
               "largeur_guide": 1200},
    "telephone": {"contexte": {"viewport": {"width": 375, "height": 812}, "device_scale_factor": 2,
                               "is_mobile": True, "has_touch": True},
                  "largeur_guide": 500},
}

PROFILS = {
    "responsable": {"type": "responsable", "nom": "Responsable", "technicienId": ""},
    "demandeur": {"type": "demandeur", "nom": "Lucie Martin", "technicienId": ""},
}


def scenario(role):
    """Identifiant d'un objet de scénario du jeu de démo (aucun identifiant écrit en dur ici)."""
    return json.loads(FICHIER_SCENARIOS.read_text(encoding="utf-8"))[role]


# Chaque capture : appareil, profil, route, élément attendu avant la photo, préparation éventuelle.
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


def prendre_capture(navigateur, capture):
    """Ouvre Prévo en démo, va à l'écran demandé et rend la capture PNG (octets)."""
    appareil = APPAREILS[capture["appareil"]]
    contexte = navigateur.new_context(locale="fr-FR", **appareil["contexte"])
    contexte.set_default_timeout(DELAI_MS)
    contexte.clock.set_fixed_time(datetime.date.today().isoformat() + "T" + HEURE_CAPTURES)
    try:
        profil = PROFILS[capture["profil"]]
        poste = "Téléphone" if capture["appareil"] == "telephone" else "PC atelier"
        contexte.add_init_script(SCRIPT_PROFIL % (json.dumps(json.dumps(profil)), json.dumps(poste)))
        page = contexte.new_page()
        erreurs = []
        page.on("pageerror", lambda erreur: erreurs.append(str(erreur)))
        page.goto((RACINE / "index.html").resolve().as_uri())
        page.click("#btn-demo")
        page.wait_for_function("document.documentElement.dataset.etat === 'pret'", timeout=DELAI_MS)
        route = capture["route"]() if callable(capture["route"]) else capture["route"]
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
    options = analyseur.parse_args(arguments)
    if hasattr(sys.stdout, "reconfigure"):      # accents lisibles dans toutes les consoles
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if options.vider:
        if not FICHIER_GUIDE.is_file():
            print("GUIDE.html introuvable.")
            return 1
        print("Images retirées du guide : %s" % ", ".join(mettre_a_jour_guide({}, vider=True)))
        return 0

    inconnus = [nom for nom in options.noms if nom not in {c["nom"] for c in CAPTURES}]
    if inconnus:
        analyseur.error("capture inconnue : " + ", ".join(inconnus))
    choisies = [c for c in CAPTURES if not options.noms or c["nom"] in options.noms]

    from playwright.sync_api import sync_playwright   # outil de développement, comme les tests
    DOSSIER_CAPTURES.mkdir(parents=True, exist_ok=True)
    pngs, echecs = {}, []
    with sync_playwright() as p:
        navigateur = p.chromium.launch(headless=True)
        try:
            for capture in choisies:
                try:
                    png = prendre_capture(navigateur, capture)
                except Exception as erreur:      # une capture ratée n'empêche pas les autres
                    echecs.append(capture["nom"])
                    print("ÉCHEC  %-12s %s" % (capture["nom"], str(erreur).splitlines()[0]))
                    continue
                (DOSSIER_CAPTURES / (capture["nom"] + ".png")).write_bytes(png)
                pngs[capture["nom"]] = (png, capture["appareil"])
                print("Écrit  docs/captures/%s.png (%d octets)" % (capture["nom"], len(png)))

            if not FICHIER_GUIDE.is_file():
                print("GUIDE.html introuvable : seules les captures PNG ont été écrites.")
            elif pngs:
                page_outil = navigateur.new_page()
                page_outil.set_content("<!doctype html><title>captures</title>")
                images = images_du_guide(page_outil, pngs)
                modifies = mettre_a_jour_guide(images)
                print("GUIDE.html : images mises à jour : %s" % (", ".join(modifies) or "aucune"))
                sans_place = sorted(set(images) - set(modifies))
                if sans_place:
                    print("  (sans <img data-capture> dans le guide : %s)" % ", ".join(sans_place))
                vides = sorted(nom for nom, adresse in adresses_actuelles().items() if not adresse)
                if vides:
                    print("  ATTENTION : images encore vides dans le guide : %s" % ", ".join(vides))
        finally:
            navigateur.close()
    if echecs:
        print("Captures ratées (ancienne image gardée) : %s" % ", ".join(echecs))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
