"""Planche des écrans principaux dans les cinq langues (chantier multilingue, Lot 5, T375 ; CS162).

Ouvre la démo (profil Responsable, file://, horloge du jeu de démo) dans chaque langue déclarée (fr, en, tr, it,
pt-PT) sur trois appareils — bureau 1440 px, Android (Pixel 7, 412 px), iPhone (iPhone 14, 390 px) — et, pour
chaque écran principal :
    - détecte automatiquement un débordement horizontal de la page (largeur de défilement > largeur visible) ;
    - détecte un texte coupé : élément visible, avec du texte à lui, dont le contenu dépasse sa boîte alors que son
      débordement est caché (overflow hidden ou clip, ellipsis), coupé dans la langue et pas en français au même
      écran (une coupure voulue, l'ellipsis d'une liste, l'est aussi en français) ; textes des lecteurs d'écran
      (.visuellement-cache) exclus ;
    - prend une capture de la fenêtre (JPEG).
Écrit une planche HTML (un tableau par appareil : un écran par ligne, une langue par colonne) et un rapport texte
dans le dossier de sortie (hors du dépôt), et rend 1 si un débordement ou un texte coupé est trouvé.

Usage : py -X utf8 outils/planche_langues.py --sortie DOSSIER [--langue tr ...] [--appareil android ...]
"""
import argparse
import html
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "tests"))
import commun  # noqa: E402

LANGUES = ["fr", "en", "tr", "it", "pt-PT"]
APPAREILS = {"bureau": {"viewport": {"width": 1440, "height": 900}, "device_scale_factor": 1},
             "android": "Pixel 7", "iphone": "iPhone 14"}
ECRANS = [("accueil", "#/accueil"), ("demandes", "#/di"), ("nouvelle demande", "#/di/nouvelle"),
          ("ordres de travail", "#/ot"), ("parc", "#/parc"), ("préventif", "#/preventif"), ("planning", "#/planning"),
          ("magasin", "#/magasin"), ("contrôles", "#/controles"),
          ("garanties et contrats", "#/garanties"),          # 2.2 (L4, T497)
          ("indicateurs", "#/indicateurs"),
          ("wiki", "#/wiki"), ("équipe", "#/equipe"), ("paramètres", "#/parametres"), ("ce poste", "#/poste"),
          ("à propos", "#/apropos")]

MESURE_JS = """() => {
  const doc = document.documentElement;
  const deborde = Math.max(0, doc.scrollWidth - doc.clientWidth);
  const coupes = [];
  for (const el of document.querySelectorAll('#app *')) {
    if (!el.offsetParent || el.clientWidth <= 2 || el.closest('.visuellement-cache')) continue;   // lecteurs d'écran
    const propre = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if (!propre) continue;
    const style = getComputedStyle(el);
    const cache = ['hidden', 'clip'].includes(style.overflowX) || style.textOverflow === 'ellipsis';
    if (cache && el.scrollWidth > el.clientWidth + 1) {
      coupes.push(el.id ? '#' + el.id : el.tagName.toLowerCase() + '.' + [...el.classList].join('.'));
    }
  }
  return { deborde, coupes: coupes.slice(0, 8) };
}"""


def contexte_pour(navigateur, playwright, appareil, langue):
    reglage = APPAREILS[appareil]
    options = dict(playwright.devices[reglage]) if isinstance(reglage, str) else dict(reglage)
    options["locale"] = {"fr": "fr-FR", "en": "en-GB", "tr": "tr-TR", "it": "it-IT", "pt-PT": "pt-PT"}[langue]
    contexte = navigateur.new_context(**options)
    contexte.add_init_script("try { localStorage.setItem('prevo.langue', %s); } catch (e) {}" % json.dumps(langue))
    commun.preregler_profil(contexte, "responsable", "Test Responsable")
    return contexte


def relever(sortie, langues, appareils):
    from playwright.sync_api import sync_playwright
    index = (RACINE / "index.html").resolve().as_uri()
    resultats = {}
    with sync_playwright() as p:
        navigateur = p.chromium.launch()
        for appareil in appareils:
            for langue in langues:
                contexte = contexte_pour(navigateur, p, appareil, langue)
                page = contexte.new_page()
                page.goto(index)
                page.click("#btn-demo")
                commun.attendre_pret(page, 30000)
                for nom, route in ECRANS:
                    page.evaluate("(r) => { location.hash = r; }", route)
                    page.wait_for_timeout(700)
                    mesure = page.evaluate(MESURE_JS)
                    image = "%s-%s-%s.jpg" % (appareil, langue, route.strip("#/").replace("/", "-") or "accueil")
                    page.screenshot(path=str(sortie / image), type="jpeg", quality=60)
                    resultats[(appareil, nom, langue)] = dict(mesure, image=image)
                contexte.close()
        navigateur.close()
    return resultats


def ecrire(sortie, resultats, langues, appareils):
    problemes = []
    morceaux = ["<!doctype html><meta charset='utf-8'><title>Planche des langues</title><style>body{font:14px sans-serif;"
                "margin:16px}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:4px;vertical-align:top}"
                "img{display:block}.ko{background:#fdd}</style><h1>Écrans principaux dans les cinq langues</h1>"]
    for appareil in appareils:
        largeur = 300 if appareil == "bureau" else 180
        morceaux.append("<h2>%s</h2><table><tr><th>écran</th>%s</tr>" % (
            appareil, "".join("<th>%s</th>" % l for l in langues)))
        for nom, _ in ECRANS:
            ligne = ["<tr><th>%s</th>" % html.escape(nom)]
            for langue in langues:
                r = resultats[(appareil, nom, langue)]
                # Coupé dans cette langue et pas en français (même écran, même appareil) : la traduction est trop
                # longue ; une coupure voulue (ellipsis d'une liste) l'est aussi en français.
                francais = set(resultats.get((appareil, nom, "fr"), {}).get("coupes", []))
                coupes = [] if langue == "fr" else [c for c in r["coupes"] if c not in francais]
                ko = r["deborde"] > 0 or coupes
                if ko:
                    problemes.append("%s, %s, %s : débordement %d px ; coupés : %s" % (
                        appareil, langue, nom, r["deborde"], "; ".join(coupes) or "aucun"))
                ligne.append("<td class='%s'><a href='%s'><img src='%s' width='%d'></a>%s</td>" % (
                    "ko" if ko else "", r["image"], r["image"], largeur,
                    ("<small>%s</small>" % html.escape("débordement %d px ; %s" % (r["deborde"], "; ".join(coupes))))
                    if ko else ""))
            morceaux.append("".join(ligne) + "</tr>")
        morceaux.append("</table>")
    (sortie / "planche.html").write_text("\n".join(morceaux), encoding="utf-8")
    (sortie / "rapport.txt").write_text("\n".join(problemes or ["aucun débordement ni texte coupé"]) + "\n",
                                        encoding="utf-8")
    return problemes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--sortie", required=True)
    parser.add_argument("--langue", action="append", choices=LANGUES)
    parser.add_argument("--appareil", action="append", choices=list(APPAREILS))
    options = parser.parse_args(argv)
    sortie = Path(options.sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    langues = options.langue or LANGUES
    appareils = options.appareil or list(APPAREILS)
    resultats = relever(sortie, langues, appareils)
    problemes = ecrire(sortie, resultats, langues, appareils)
    print("%d captures ; %s" % (len(resultats), "%d problème(s), voir rapport.txt" % len(problemes) if problemes
                                else "aucun débordement ni texte coupé"))
    print("planche : %s" % (sortie / "planche.html"))
    return 1 if problemes else 0


if __name__ == "__main__":
    sys.exit(main())
