"""Jeux de fichiers abîmés des tests de la garde « fichier abîmé » (version corrective 1.2.1).

Chaque jeu est une COPIE du jeu de démo du dépôt (donnees/demo, format 3 de la 1.2.0) dans un dossier temporaire,
dont un fichier est abîmé par programme, comme il peut l'être hors de Prévo (règle numéro un : jamais de données
réelles, jamais de jeu lu ou écrit en place) :

    entete_tronque(octets)         en-tête coupé au milieu du nom de colonne temps_prevu_h (il finit par « temps_pr »),
                                   lignes de données intactes et plus larges que l'en-tête : la recette du jeu
                                   « entete-tronque » de tests/fixtures/formats (branche 2.0), qui a révélé le défaut ;
    avec_note_en_trop(octets)      une valeur tapée à droite du tableau sur la dernière ligne (« valeur au-delà de
                                   l'en-tête », le cas le plus probable : une note ajoutée dans Excel) ;
    avec_guillemet_ouvert(octets)  une ligne coupée dans un texte entre guillemets jamais fermé, sans fin de ligne
                                   (copie ou synchronisation interrompue) ;
    avec_version_schema(octets, v) parametres.csv dont version_schema vaut v.

    copier_demo(destination)       copie de donnees/demo ; rend le dossier.
    fichiers_de(dossier)           {chemin relatif : octets} de tous les fichiers (sauvegardes comprises).
"""
import shutil
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DEMO = RACINE / "donnees" / "demo"

# Ligne coupée dans une cellule entre guillemets, sans fin de ligne (exemple de la tâche T200 de la 2.0).
LIGNE_COUPEE = 'J-20261104120000-ABCD;2026-11-04 12:00;"Poste coupé'.encode("utf-8")
NOTE_EN_TROP = "Note ajoutée dans Excel"


def copier_demo(destination):
    destination = Path(destination)
    shutil.copytree(str(DEMO), str(destination))
    return destination


def fichiers_de(dossier):
    dossier = Path(dossier)
    return {p.relative_to(dossier).as_posix(): p.read_bytes() for p in sorted(dossier.rglob("*")) if p.is_file()}


def donnees_de(fichiers):
    """Les seuls CSV de données d'un {chemin : octets} (ni sauvegardes, ni documents)."""
    return {chemin: octets for chemin, octets in fichiers.items() if "/" not in chemin and chemin.endswith(".csv")}


def entete_tronque(octets):
    entete, reste = octets.split(b"\r\n", 1)
    coupe = entete.index(b"temps_prevu_h") + len(b"temps_pr")
    return entete[:coupe] + b"\r\n" + reste


def avec_note_en_trop(octets):
    if not octets.endswith(b"\r\n"):
        raise AssertionError("le fichier devrait finir par CRLF : %r" % octets[-20:])
    return octets[:-2] + b";" + NOTE_EN_TROP.encode("utf-8") + b"\r\n"


def avec_guillemet_ouvert(octets):
    if not octets.endswith(b"\r\n"):
        raise AssertionError("le fichier devrait finir par CRLF : %r" % octets[-20:])
    return octets + LIGNE_COUPEE


def avec_version_schema(octets, version):
    ancienne = b"\r\nversion_schema;'3\r\n"
    if ancienne not in octets:
        raise AssertionError("version_schema;'3 introuvable dans parametres.csv")
    return octets.replace(ancienne, b"\r\nversion_schema;'" + str(version).encode("ascii") + b"\r\n")
