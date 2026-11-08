"""Construit la démo en ligne de Prévo : dist/demo-web/ (brief de lancement, point 7 ; mise en ligne :
docs/DEPLOIEMENT_DEMO.md).

Le dossier produit ne contient que la liste blanche : index.html, favicon.svg, GUIDE.html, GUIDE.en.html, css/ et js/
(jamais serveur.py, les lanceurs, les données, les tests ni les outils ; ni fichier caché ni cache
Python). Dans SA copie de js/app.js, la constante VERSION_WEB passe de false à true : l'écran de
démarrage ne propose alors que la démo et « Télécharger Prévo », et l'assistant IA reste visible sans
jamais rien appeler (js/modules/ia.js). Le dépôt n'est jamais modifié.

Remplacement contrôlé : la ligne « const VERSION_WEB = false; » doit se trouver exactement une fois
dans js/app.js, sinon la construction échoue avec un message clair.

Sortie : construite à côté dans un dossier temporaire, puis mise à la place de l'ancienne ; un échec
ne laisse rien à moitié construit. Un dossier de sortie existant n'est remplacé que s'il est vide ou
s'il ne contient que la liste blanche (construction précédente) : tout autre contenu est refusé et
rien n'est effacé.

Bibliothèque standard seulement. Lancer depuis la racine du projet :
    py outils/construire_demo_web.py                          → dist/demo-web/
    py outils/construire_demo_web.py --sortie AUTRE_DOSSIER
"""
import argparse
import shutil
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SORTIE_PAR_DEFAUT = RACINE / "dist" / "demo-web"
FICHIERS = ["index.html", "favicon.svg", "GUIDE.html", "GUIDE.en.html"]   # T338 : guide anglais
DOSSIERS = ["css", "js"]
LISTE_BLANCHE = FICHIERS + DOSSIERS
FICHIER_DRAPEAU = Path("js") / "app.js"
DRAPEAU_DEPOT = "const VERSION_WEB = false;"
DRAPEAU_WEB = "const VERSION_WEB = true;"


class ErreurConstruction(Exception):
    """Construction impossible : le message dit pourquoi, en français."""


def activer_version_web(texte):
    """Texte de js/app.js avec le drapeau à vrai. La ligne attendue doit y être exactement une fois."""
    nombre = texte.count(DRAPEAU_DEPOT)
    if nombre != 1:
        raise ErreurConstruction(
            "js/app.js : la ligne « %s » doit s'y trouver exactement une fois (trouvée %d fois). Le drapeau "
            "VERSION_WEB a-t-il été renommé, dédoublé ou déjà mis à vrai ? Rien n'a été construit."
            % (DRAPEAU_DEPOT, nombre))
    return texte.replace(DRAPEAU_DEPOT, DRAPEAU_WEB)


def ignorer(dossier, noms):
    """Fichiers cachés (.gitkeep…) et caches Python : jamais copiés."""
    return [nom for nom in noms if nom.startswith(".") or nom == "__pycache__" or nom.endswith(".pyc")]


def verifier_source():
    manquants = [nom for nom in FICHIERS if not (RACINE / nom).is_file()]
    manquants += [nom + "/" for nom in DOSSIERS if not (RACINE / nom).is_dir()]
    if manquants:
        raise ErreurConstruction("fichiers manquants dans le dépôt : %s. Rien n'a été construit." % ", ".join(manquants))


def est_sous(chemin, dossier):
    """Vrai si `chemin` est `dossier` ou se trouve dedans (Path.is_relative_to n'existe qu'en 3.9)."""
    try:
        chemin.relative_to(dossier)
        return True
    except ValueError:
        return False


def verifier_sortie(sortie):
    """La sortie peut être (re)faite : absente, vide, ou ne contenant que la liste blanche."""
    if est_sous(RACINE, sortie) or any(est_sous(sortie, RACINE / nom) for nom in DOSSIERS):
        raise ErreurConstruction("%s : la sortie ne peut être ni le dépôt, ni un dossier qui le contient, "
                                 "ni un dossier de css/ ou js/." % sortie)
    if not sortie.exists():
        return
    if not sortie.is_dir():
        raise ErreurConstruction("%s existe et n'est pas un dossier : rien n'a été construit." % sortie)
    etrangers = sorted(chemin.name for chemin in sortie.iterdir() if chemin.name not in LISTE_BLANCHE)
    if etrangers:
        raise ErreurConstruction(
            "%s contient autre chose que la démo web (%s) : rien n'est effacé ; choisissez un dossier vide "
            "ou absent." % (sortie, ", ".join(etrangers)))


def construire(sortie):
    """Construit la démo web dans `sortie` (Path). Renvoie le chemin absolu de la sortie."""
    sortie = Path(sortie).resolve()
    verifier_source()
    verifier_sortie(sortie)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    chantier = Path(tempfile.mkdtemp(prefix=".demo-web-en-cours-", dir=str(sortie.parent)))
    try:
        for nom in FICHIERS:
            shutil.copyfile(RACINE / nom, chantier / nom)
        for nom in DOSSIERS:
            shutil.copytree(RACINE / nom, chantier / nom, ignore=ignorer, copy_function=shutil.copyfile)
        drapeau = chantier / FICHIER_DRAPEAU
        # Octets lus et réécrits tels quels (fins de ligne comprises) : seule la ligne du drapeau change.
        drapeau.write_bytes(activer_version_web(drapeau.read_bytes().decode("utf-8")).encode("utf-8"))
        if sortie.exists():
            shutil.rmtree(sortie)
        chantier.rename(sortie)
    except BaseException:
        shutil.rmtree(chantier, ignore_errors=True)
        raise
    return sortie


def main(arguments=None):
    analyseur = argparse.ArgumentParser(
        description="Construit la démo en ligne de Prévo : liste blanche seulement, VERSION_WEB à vrai.")
    analyseur.add_argument("--sortie", default=str(SORTIE_PAR_DEFAUT),
                           help="dossier produit (défaut : dist/demo-web/ dans le dépôt)")
    options = analyseur.parse_args(arguments)
    try:
        sortie = construire(Path(options.sortie))
    except ErreurConstruction as erreur:
        print("Erreur : %s" % erreur, file=sys.stderr)
        return 1
    nombre = sum(1 for chemin in sortie.rglob("*") if chemin.is_file())
    print("Démo web construite : %s (%d fichiers, VERSION_WEB = true)." % (sortie, nombre))
    print("Mise en ligne : voir docs/DEPLOIEMENT_DEMO.md (jamais serveur.py).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
