"""Construit le zip de la release de Prévo : dist/prevo-<version>.zip (brief de lancement, point 7).

Contenu (liste blanche, rien d'autre) : l'application (index.html, favicon.svg, css/, js/), les
lanceurs (Lancer_GMAO.bat, lancer.sh, Reinitialiser_mot_de_passe.bat, serveur.py), GUIDE.html, README.md,
LICENSE, NOTICE, FICHE_TECHNIQUE_CSV.md et outils/empreintes-tiers.json ; jamais les tests, les autres outils,
docs/, les captures ni les données (ni fichier caché ni cache Python).

Binaires tiers (lot 7, ARCHITECTURE.md §22.14) : le Python embarqué officiel pour Windows 64 bits (python/, avec sa
licence LICENSE.txt) et mkcert pour Windows 64 bits avec sa licence (outils-tiers/), pour que l'installation ne
demande plus rien sous Windows. Ils sont pris dans le cache dist/tiers/ ou téléchargés depuis leur page officielle,
et leur empreinte SHA-256 est comparée à outils/empreintes-tiers.json avant d'entrer dans le zip (écart : rien n'est
écrit). --sans-tiers construit le zip sans eux (développement, tests du contenu de l'application). Le dépôt ne
contient jamais ces binaires (.gitignore). Tout est rangé sous un dossier prevo-<version>/ : le zip se décompresse
proprement. Aucun dossier donnees/ : serveur.py le crée au premier lancement (avec documents/ et
sauvegardes/), et une base vide propose « Partir des données de démo » (jeu de démo dans
js/demo-donnees.js) ou « Créer une base vide ». Le mode dossier et la démo n'ont besoin de rien de plus.

Version lue dans js/app.js (const VERSION) ; le drapeau VERSION_WEB doit y être faux : la release
n'est jamais la démo en ligne (outils/construire_demo_web.py).

Zip déterministe : entrées triées, date fixe (DATE_VERSION de js/app.js, à minuit), droits fixes
(0644 ; 0755 pour lancer.sh et serveur.py, exécutables sur Mac et Linux), compression DEFLATE de
niveau 9 : deux constructions des mêmes fichiers donnent les mêmes octets.

Fichier manquant (NOTICE…) : tous les absents sont listés et rien n'est écrit.

Les fichiers sont pris tels qu'ils sont sur le disque : pour une release, construire depuis une copie
propre de l'étiquette, pas depuis un chantier en cours, par exemple :
    git worktree add ../prevo-v2.0.0-beta.2 v2.0.0-beta.2
    py outils/construire_release.py --source ../prevo-v2.0.0-beta.2
    git worktree remove ../prevo-v2.0.0-beta.2

Bibliothèque standard seulement. Lancer depuis la racine du projet :
    py outils/construire_release.py                          → dist/prevo-<version>.zip
    py outils/construire_release.py [--source COPIE_DU_DEPOT] [--sortie DOSSIER] [--sans-tiers] [--cache-tiers DOSSIER]
"""
import argparse
import hashlib
import hmac
import io
import json
import os
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SORTIE_PAR_DEFAUT = RACINE / "dist"
FICHIERS = ["index.html", "favicon.svg", "GUIDE.html", "README.md", "LICENSE", "NOTICE", "FICHE_TECHNIQUE_CSV.md",
            "Lancer_GMAO.bat", "lancer.sh", "Reinitialiser_mot_de_passe.bat", "serveur.py", "outils/empreintes-tiers.json"]
CACHE_TIERS_PAR_DEFAUT = SORTIE_PAR_DEFAUT / "tiers"
DELAI_TELECHARGEMENT_S = 120
DOSSIERS = ["css", "js", "acces"]      # acces/ : la porte d'entrée et ses schémas (lot 7, §22.6)
EXECUTABLES = {"lancer.sh", "serveur.py"}
DROITS_FICHIER = 0o100644
DROITS_EXECUTABLE = 0o100755
SYSTEME_UNIX = 3                      # les droits ci-dessus sont lus par unzip (Mac, Linux)
MOTIF_VERSION = re.compile(r"^\s*const VERSION = '([0-9A-Za-z.+-]+)';", re.MULTILINE)
MOTIF_DATE = re.compile(r"^\s*const DATE_VERSION = '(\d{4})-(\d{2})-(\d{2})';", re.MULTILINE)
DRAPEAU_DEPOT = "const VERSION_WEB = false;"


class ErreurConstruction(Exception):
    """Construction impossible : le message dit pourquoi, en français."""


def lire_version(source):
    """(version, date du zip) lues dans js/app.js ; le drapeau de la version web doit y être faux."""
    chemin = source / "js" / "app.js"
    if not chemin.is_file():
        raise ErreurConstruction("js/app.js introuvable dans %s : version inconnue, rien n'a été écrit." % source)
    texte = chemin.read_text(encoding="utf-8")
    versions = MOTIF_VERSION.findall(texte)
    dates = MOTIF_DATE.findall(texte)
    if len(versions) != 1 or len(dates) != 1:
        raise ErreurConstruction("js/app.js : « const VERSION = '…'; » et « const DATE_VERSION = 'AAAA-MM-JJ'; » "
                                 "attendus une fois chacun. Rien n'a été écrit.")
    if texte.count(DRAPEAU_DEPOT) != 1:
        raise ErreurConstruction("js/app.js : « %s » attendu une fois (la release n'est jamais la version web). "
                                 "Rien n'a été écrit." % DRAPEAU_DEPOT)
    annee, mois, jour = (int(nombre) for nombre in dates[0])
    return versions[0], (annee, mois, jour, 0, 0, 0)


def cache(relatif):
    return any(morceau.startswith(".") or morceau == "__pycache__" for morceau in relatif.parts) \
        or relatif.suffix == ".pyc"


def fichiers_a_inclure(source):
    """Chemins relatifs (a/b.js) à mettre dans le zip, triés ; tous les absents signalés d'un coup."""
    manquants = [nom for nom in FICHIERS if not (source / nom).is_file()]
    manquants += [nom + "/" for nom in DOSSIERS if not (source / nom).is_dir()]
    if manquants:
        raise ErreurConstruction("fichiers manquants dans %s : %s. Rien n'a été écrit." % (source, ", ".join(manquants)))
    retenus = list(FICHIERS)
    for nom in DOSSIERS:
        for chemin in (source / nom).rglob("*"):
            relatif = chemin.relative_to(source)
            if chemin.is_file() and not cache(relatif):
                retenus.append(relatif.as_posix())
    return sorted(retenus)


def telecharger_par_http(adresse):
    with urllib.request.urlopen(adresse, timeout=DELAI_TELECHARGEMENT_S) as reponse:
        return reponse.read()


def obtenir_tiers(nom, adresse, sha256, cache, telecharger):
    """Octets d'un binaire tiers : du cache s'il y est intact, sinon téléchargé ; l'empreinte est toujours vérifiée."""
    chemin = Path(cache) / nom
    if chemin.is_file():
        octets = chemin.read_bytes()
        if hmac.compare_digest(hashlib.sha256(octets).hexdigest(), sha256):
            return octets
    try:
        octets = telecharger(adresse)
    except OSError as erreur:
        raise ErreurConstruction("téléchargement de %s impossible (%s). Rien n'a été écrit ; --sans-tiers construit "
                                 "le zip sans les binaires tiers." % (nom, erreur))
    obtenue = hashlib.sha256(octets).hexdigest()
    if not hmac.compare_digest(obtenue, sha256):
        raise ErreurConstruction("empreinte inattendue pour %s (%s au lieu de %s) : fichier écarté, rien n'a été écrit."
                                 % (nom, obtenue, sha256))
    Path(cache).mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(octets)
    return octets


def contenu_tiers(source, cache, telecharger=telecharger_par_http):
    """[(chemin relatif dans le zip, octets)] : python/ (paquet embarqué déplié) et outils-tiers/ (mkcert + licence)."""
    empreintes = json.loads((Path(source) / "outils" / "empreintes-tiers.json").read_text(encoding="utf-8"))
    entrees = []
    python = empreintes["python"]
    nom_python = "python-%s-embed-amd64.zip" % python["version"]
    octets = obtenir_tiers(nom_python, python["source"] + nom_python, python["fichiers"][nom_python]["sha256"],
                           cache, telecharger)
    with zipfile.ZipFile(io.BytesIO(octets)) as paquet:
        for info in sorted(paquet.infolist(), key=lambda i: i.filename):
            if not info.is_dir():
                entrees.append(("python/" + info.filename, paquet.read(info)))
    mkcert = empreintes["mkcert"]
    nom_mkcert = "mkcert-v%s-windows-amd64.exe" % mkcert["version"]
    entrees.append(("outils-tiers/" + nom_mkcert, obtenir_tiers(
        nom_mkcert, mkcert["source"] + nom_mkcert, mkcert["fichiers"][nom_mkcert]["sha256"], cache, telecharger)))
    licence = mkcert["texte_licence"]
    entrees.append(("outils-tiers/LICENCE-mkcert.txt", obtenir_tiers(
        "LICENCE-mkcert.txt", licence["adresse"], licence["sha256"], cache, telecharger)))
    return entrees


def ecrire_zip(source, chemin_zip, prefixe, date, fichiers, supplementaires=()):
    """Écrit le zip dans un fichier temporaire, mis à la place du zip final à la fin seulement. supplementaires :
    [(chemin relatif, octets)] ajoutés à la liste triée (binaires tiers)."""
    temporaire = chemin_zip.with_name(chemin_zip.name + ".en-cours")
    entrees = [(relatif, None) for relatif in fichiers] + list(supplementaires)
    entrees.sort(key=lambda entree: entree[0])
    try:
        with zipfile.ZipFile(str(temporaire), "w") as archive:
            for relatif, octets in entrees:
                info = zipfile.ZipInfo(prefixe + relatif, date_time=date)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = SYSTEME_UNIX
                info.external_attr = (DROITS_EXECUTABLE if relatif in EXECUTABLES else DROITS_FICHIER) << 16
                archive.writestr(info, octets if octets is not None else (source / relatif).read_bytes(), compresslevel=9)
        os.replace(str(temporaire), str(chemin_zip))
    finally:
        if temporaire.exists():
            temporaire.unlink()


# Mise à jour signalée (ARCHITECTURE.md §21, D120) : version.json publié à la racine de prevo.pro avec chaque release.
ADRESSE_RELEASE = "https://github.com/nicoboy49/prevo/releases/tag/v%s"
NOUVEAUTES_MAX = 2
MOTIF_LIEN = re.compile(r"\[([^\]]+)\]\([^)]*\)")


def texte_simple(puce):
    """Une puce du CHANGELOG sans sa mise en forme Markdown (liens, gras, code), espaces réduits, 200 caractères au plus."""
    puce = MOTIF_LIEN.sub(r"\1", puce).replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", puce).strip()[:200]


def nouveautes_du_changelog(source, version, nombre=NOUVEAUTES_MAX):
    """Les premières puces de la section « ## [version] » de CHANGELOG.md (lignes de suite jointes) ; [] sans section."""
    chemin = Path(source) / "CHANGELOG.md"
    if not chemin.is_file():
        return []
    lignes = chemin.read_text(encoding="utf-8").splitlines()
    debut = next((i for i, l in enumerate(lignes) if l.startswith("## [%s]" % version)), None)
    if debut is None:
        return []
    puces = []
    for ligne in lignes[debut + 1:]:
        if ligne.startswith("## "):
            break
        if ligne.startswith("- "):
            puces.append(ligne[2:].strip())
        elif ligne.startswith("  ") and ligne.strip() and puces:
            puces[-1] += " " + ligne.strip()
    return [texte_simple(p) for p in puces[:nombre]]


def ecrire_version_json(source, sortie, version, date):
    """Écrit sortie/version.json ({version, date, adresse, nouveautes}, UTF-8, LF) ; renvoie son chemin."""
    contenu = {"version": version, "date": "%04d-%02d-%02d" % tuple(date[:3]), "adresse": ADRESSE_RELEASE % version,
               "nouveautes": nouveautes_du_changelog(source, version)}
    chemin = Path(sortie) / "version.json"
    chemin.write_bytes((json.dumps(contenu, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return chemin


def construire(source, sortie, tiers=True, cache=None, telecharger=telecharger_par_http):
    """Construit prevo-<version>.zip dans `sortie` ; renvoie (chemin du zip, nombre de fichiers). tiers : ajoute le
    Python embarqué et mkcert (empreintes vérifiées) ; tout est contrôlé avant d'écrire."""
    source = Path(source).resolve()
    sortie = Path(sortie).resolve()
    version, date = lire_version(source)
    fichiers = fichiers_a_inclure(source)
    supplementaires = contenu_tiers(source, cache or CACHE_TIERS_PAR_DEFAUT, telecharger) if tiers else []
    sortie.mkdir(parents=True, exist_ok=True)
    chemin_zip = sortie / ("prevo-%s.zip" % version)
    ecrire_zip(source, chemin_zip, "prevo-%s/" % version, date, fichiers, supplementaires)
    ecrire_version_json(source, sortie, version, date)
    return chemin_zip, len(fichiers) + len(supplementaires)


def main(arguments=None):
    analyseur = argparse.ArgumentParser(description="Construit dist/prevo-<version>.zip (release de Prévo).")
    analyseur.add_argument("--source", default=str(RACINE),
                           help="copie du dépôt à empaqueter (défaut : ce dépôt ; conseillé : une copie propre de l'étiquette)")
    analyseur.add_argument("--sortie", default=str(SORTIE_PAR_DEFAUT), help="dossier du zip (défaut : dist/)")
    analyseur.add_argument("--sans-tiers", action="store_true",
                           help="sans le Python embarqué ni mkcert (développement, tests du contenu de l'application)")
    analyseur.add_argument("--cache-tiers", default=str(CACHE_TIERS_PAR_DEFAUT),
                           help="dossier des binaires tiers déjà téléchargés (défaut : dist/tiers/)")
    options = analyseur.parse_args(arguments)
    try:
        chemin_zip, nombre = construire(Path(options.source), Path(options.sortie), tiers=not options.sans_tiers,
                                        cache=Path(options.cache_tiers))
    except ErreurConstruction as erreur:
        print("Erreur : %s" % erreur, file=sys.stderr)
        return 1
    print("Release construite : %s (%d fichiers, %d octets)." % (chemin_zip, nombre, chemin_zip.stat().st_size))
    print("À joindre à la release GitHub (Releases > Draft a new release, depuis l'étiquette).")
    print("Mise à jour signalée : %s à publier à la racine de prevo.pro (https://prevo.pro/version.json), servi avec "
          "l'en-tête Access-Control-Allow-Origin: * (docs/RELEASE.md)." % (chemin_zip.parent / "version.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
