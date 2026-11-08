"""Jeux de fichiers d'exemple des formats de données (T182) : tests/fixtures/formats/.

    from jeux_formats import JEUX, copier_jeu
    copier_jeu("f3-v1.2.0", dossier_temporaire)

Un jeu est une base (dossier de CSV) ou une variante (dossier avec variante.json : base, supprimer, vider, et
seulement les fichiers qui changent). copier_jeu compose la base (récursivement), superpose les fichiers de la
variante, puis supprime les fichiers de « supprimer » et vide ceux de « vider ». Règle du chantier : on ne copie
jamais un jeu ailleurs que dans un dossier temporaire, et aucun test ne touche à des données réelles.
"""
import json
import shutil
from pathlib import Path

DOSSIER_JEUX = Path(__file__).resolve().parent / "fixtures" / "formats"
NOM_VARIANTE = "variante.json"
JEUX = sorted(d.name for d in DOSSIER_JEUX.iterdir() if d.is_dir())


def lire_variante(nom):
    """Le manifeste d'une variante, ou None si le jeu est une base."""
    chemin = DOSSIER_JEUX / nom / NOM_VARIANTE
    return json.loads(chemin.read_text(encoding="utf-8")) if chemin.is_file() else None


def copier_jeu(nom, destination):
    """Matérialise le jeu « nom » dans le dossier « destination » (créé au besoin) ; rend ce dossier (Path)."""
    if nom not in JEUX:
        raise KeyError("jeu inconnu : %s (jeux : %s)" % (nom, ", ".join(JEUX)))
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    _composer(nom, destination, ())
    return destination


def _composer(nom, destination, vus):
    if nom in vus:
        raise ValueError("base circulaire : %s" % " > ".join(vus + (nom,)))
    variante = lire_variante(nom)
    if variante is not None:
        _composer(variante["base"], destination, vus + (nom,))
    source = DOSSIER_JEUX / nom
    for chemin in sorted(source.rglob("*")):
        if chemin.is_file() and chemin.relative_to(source).as_posix() != NOM_VARIANTE:
            cible = destination / chemin.relative_to(source)
            cible.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(str(chemin), str(cible))
    if variante is not None:
        for fichier in variante.get("supprimer", []):
            (destination / fichier).unlink()
        for fichier in variante.get("vider", []):
            (destination / fichier).write_bytes(b"")
