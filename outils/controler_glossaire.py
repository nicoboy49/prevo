"""Contrôle de cohérence du glossaire (chantier multilingue, Lot 5, T375 ; CS160) : chaque terme de docs/GLOSSAIRE.md
est-il traduit partout de la même façon dans js/i18n/<code>.js ?

Pour chaque ligne d'un tableau du glossaire (fr | en | tr | it | pt-PT | remarque) et chaque langue demandée : les
clés dont le texte français contient le terme français (mot entier, sans tenir compte de la casse ni des accents) ;
parmi elles, celles dont le texte traduit ne contient pas le terme de la langue sont des écarts. Le terme de la
langue est pris en racine (début de mot) pour suivre les accords et, en turc, les suffixes (iş emri → iş emrini) :
racine = le mot en entier jusqu'à 5 lettres, sinon ses 5 premières lettres (4 en turc). Une case de glossaire qui
propose plusieurs formes (« A / B », « A ou B », parenthèses) accepte chacune. Les abréviations (OT, DI…), les termes
de moins de 4 lettres et les lignes dont le terme est identique en français et dans la langue sont ignorés.

C'est une heuristique : un écart peut être une tournure juste (synonyme voulu, phrase reformulée). L'outil sert à
relire, il ne refuse rien : il écrit un rapport par langue et le taux de cohérence, terme par terme.

Usage : py -X utf8 outils/controler_glossaire.py [--langue tr] [--detail N] [--racine DOSSIER]
"""
import argparse
import re
import sys
import unicodedata
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "outils"))
import textes_langues  # noqa: E402

COLONNES = ["fr", "en", "tr", "it", "pt-PT"]


def sans_accents(texte):
    texte = unicodedata.normalize("NFD", texte.replace("ı", "i").replace("İ", "I"))
    return "".join(c for c in texte if not unicodedata.combining(c)).lower()


def formes(case):
    """« ordem de trabalho (OT) » → ['ordem de trabalho'] ; « A / B », « A ou B » → [A, B]."""
    case = re.sub(r"\([^)]*\)", " ", case)
    case = re.sub(r"[«»“”\"`*]", " ", case)
    morceaux = re.split(r"\s*/\s*|\s+ou\s+|\s+or\s+|\s*;\s*|\s*,\s*", case)
    return [m.strip() for m in morceaux if len(m.strip()) >= 4 and not m.strip().isupper()]


def racine(terme, code):
    longueur = 4 if code == "tr" else 5
    mots = sans_accents(terme).split()
    return " ".join(m if len(m) <= longueur else m[:longueur] for m in mots)


def contient(texte, terme_fr):
    return re.search(r"(?<![a-z0-9])" + re.escape(sans_accents(terme_fr)) + r"(?![a-z0-9])", sans_accents(texte)) is not None


def contient_racine(texte, terme, code):
    motif = r"(?<![a-z0-9])" + r"[a-z0-9]*\s+".join(re.escape(m) for m in racine(terme, code).split())
    return re.search(motif, sans_accents(texte)) is not None


def lignes_du_glossaire(racine_depot):
    texte = (Path(racine_depot) / "docs" / "GLOSSAIRE.md").read_text(encoding="utf-8")
    entrees = []
    for ligne in texte.splitlines():
        if not ligne.startswith("| ") or ligne.startswith("| fr |") or ligne.startswith("|---"):
            continue
        cases = [c.strip() for c in ligne.strip().strip("|").split("|")]
        if len(cases) < 5:
            continue
        entrees.append(dict(zip(COLONNES, cases[:5])))
    return entrees


def valeurs(langue):
    """{clé: texte} d'un dictionnaire, pluriels réunis (formes séparées par un saut de ligne)."""
    sortie = {}
    for cle, valeur in langue.entrees.items():
        sortie[cle] = "\n".join(valeur.values()) if isinstance(valeur, dict) else str(valeur)
    return sortie


def controler(racine_depot, code):
    fr = valeurs(textes_langues.Langue("fr", racine_depot, textes_langues.fichiers_de("fr")))
    cible = valeurs(textes_langues.Langue(code, racine_depot, textes_langues.fichiers_de(code)))
    resultats = []
    for entree in lignes_du_glossaire(racine_depot):
        termes_fr = formes(entree["fr"])
        termes_cible = formes(entree[code])
        if not termes_fr or not termes_cible:
            continue
        if {sans_accents(t) for t in termes_fr} == {sans_accents(t) for t in termes_cible}:
            continue
        cles = [cle for cle, texte in fr.items() if cle in cible and any(contient(texte, t) for t in termes_fr)]
        if not cles:
            continue
        ecarts = [cle for cle in cles if not any(contient_racine(cible[cle], t, code) for t in termes_cible)]
        resultats.append((entree["fr"], entree[code], len(cles), ecarts))
    return resultats


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--langue", action="append", help="tr, it, pt-PT (défaut : les trois)")
    parser.add_argument("--detail", type=int, default=3, help="clés en écart montrées par terme (défaut 3)")
    parser.add_argument("--racine", default=str(RACINE))
    options = parser.parse_args(argv)
    for code in options.langue or ["tr", "it", "pt-PT"]:
        resultats = controler(options.racine, code)
        total = sum(n for _, _, n, _ in resultats)
        ecarts = sum(len(e) for _, _, _, e in resultats)
        print("== %s : %d termes, %d emplois, %d écarts (%.0f %% cohérents)"
              % (code, len(resultats), total, ecarts, 100.0 * (total - ecarts) / total if total else 100))
        for fr, terme, n, liste in sorted(resultats, key=lambda r: -len(r[3])):
            if liste:
                print("   %-34s → %-30s %3d/%d en écart : %s" % (fr[:34], terme[:30], len(liste), n,
                                                               ", ".join(liste[:options.detail])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
