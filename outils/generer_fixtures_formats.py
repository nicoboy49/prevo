"""Génère les jeux de fichiers d'exemple des formats de données (tests/fixtures/formats/), T182.

Trois jeux de base, tirés des fichiers de référence, chaque table réduite à 12 enregistrements :
    f1          tests/fixtures/v1/                      (format 1)
    f2-v1.1.0   donnees/demo/ à l'étiquette v1.1.0      (format 2, 22 tables)
    f3-v1.2.0   donnees/demo/ à l'étiquette v1.2.0      (format 3, 24 tables)
et des variantes stockées comme différences (variante.json + seulement les fichiers qui changent).

Reproductible octet pour octet : mêmes entrées, mêmes sorties (aucune date du jour, aucun hasard ; le sel du
compte fictif est fixe). Bibliothèque standard seulement ; git doit connaître les étiquettes v1.1.0 et v1.2.0.

Lancer depuis la racine du projet :
    python -I outils/generer_fixtures_formats.py [--sortie DOSSIER]
"""
import argparse
import base64
import csv
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import zlib
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SORTIE_DEFAUT = RACINE / "tests" / "fixtures" / "formats"
MAX_ENREGISTREMENTS = 12
BOM = b"\xef\xbb\xbf"

# Compte fictif de la variante f3-v2.0.0 (mot de passe documenté dans le LISEZMOI)
MOT_DE_PASSE_ESSAI = "essai-formats-prevo"
SEL_FIXE = bytes(range(16))
INSTANT_COMPTE = "2026-10-28T09:00:00"

MOTIF_COURRIEL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*")
MOTIF_TELEPHONE = re.compile(r"(?<![\w.,])(?:(?:\+|00)33[ .-]?(?:\(0\)[ .-]?)?|0)([1-9])([ .-]?)(\d{2})\2(\d{2})\2(\d{2})\2(\d{2})(?!\w)")
PREFIXES_FICTIFS = ("04657100", "06399800")


# ---------------------------------------------------------------- lecture des sources

def git_show(etiquette, chemin):
    return subprocess.check_output(["git", "show", "%s:%s" % (etiquette, chemin)], cwd=str(RACINE))


def sources_git(etiquette):
    noms = subprocess.check_output(["git", "ls-tree", "--name-only", etiquette, "donnees/demo/"], cwd=str(RACINE), text=True).split()
    return {n.rsplit("/", 1)[1]: git_show(etiquette, n) for n in sorted(noms) if n.endswith(".csv")}


def sources_f1():
    dossier = RACINE / "tests" / "fixtures" / "v1"
    return {c.name: c.read_bytes() for c in sorted(dossier.glob("*.csv"))}


# ---------------------------------------------------------------- enregistrements CSV (octets d'origine)

def enregistrements(octets):
    """Découpe en enregistrements CSV (octets d'origine, fin de ligne comprise) : une fin de ligne dans une
    cellule entre guillemets ne termine pas l'enregistrement. Le premier est l'en-tête (BOM compris)."""
    morceaux, debut, entre_guillemets = [], 0, False
    for i, octet in enumerate(octets):
        if octet == 0x22:
            entre_guillemets = not entre_guillemets
        elif octet == 0x0A and not entre_guillemets:
            morceaux.append(octets[debut:i + 1])
            debut = i + 1
    if debut < len(octets):
        morceaux.append(octets[debut:])
    return morceaux


def rendre_fictif(octets):
    """Remplace de façon déterministe courriels et téléphones hors plages fictives (rien à faire le plus souvent)."""
    texte = octets.decode("utf-8")

    def courriel(m):
        return m.group(0) if m.group(0).endswith(".example") else m.group(0).split("@")[0] + "@atelier-demo.example"

    def telephone(m):
        national = "0" + "".join(m.group(i) for i in (1, 3, 4, 5, 6))
        if national.startswith(PREFIXES_FICTIFS):
            return m.group(0)
        return "04 65 71 00 %02d" % (zlib.crc32(national.encode("ascii")) % 100)

    nouveau = MOTIF_TELEPHONE.sub(telephone, MOTIF_COURRIEL.sub(courriel, texte))
    return nouveau.encode("utf-8") if nouveau != texte else octets


def tronquer(octets, maximum=MAX_ENREGISTREMENTS):
    morceaux = enregistrements(octets)
    gardes = morceaux[:1 + maximum]
    if len(gardes) > 1 and not gardes[-1].endswith(b"\n") and len(morceaux) > len(gardes):
        gardes[-1] += b"\r\n"                      # ne se produit pas : seul le dernier enregistrement peut en manquer
    return b"".join(rendre_fictif(m) for m in gardes)


def construire_base(sources):
    return {nom: (octets if nom == "parametres.csv" else tronquer(octets)) for nom, octets in sources.items()}


# ---------------------------------------------------------------- réécriture de colonnes (variantes)

def lire_table(octets):
    """(avec_bom, en-tête, lignes) d'un CSV ; cellules entre guillemets, fins de ligne CRLF."""
    avec_bom = octets.startswith(BOM)
    texte = octets[3:].decode("utf-8") if avec_bom else octets.decode("utf-8")
    lignes = list(csv.reader(io.StringIO(texte, newline=""), delimiter=";"))
    return avec_bom, lignes[0], lignes[1:]


def ecrire_table(avec_bom, entete, lignes, encodage="utf-8"):
    sortie = io.StringIO(newline="")
    ecrivain = csv.writer(sortie, delimiter=";", lineterminator="\r\n")
    ecrivain.writerow(entete)
    ecrivain.writerows(lignes)
    octets = sortie.getvalue().encode(encodage, errors="replace")
    return (BOM + octets) if avec_bom else octets


def sans_colonnes(octets, noms):
    avec_bom, entete, lignes = lire_table(octets)
    gardees = [i for i, n in enumerate(entete) if n not in noms]
    return ecrire_table(avec_bom, [entete[i] for i in gardees], [[l[i] for i in gardees] for l in lignes])


def avec_colonne(octets, nom, apres=None, valeur="x"):
    """Ajoute une colonne inconnue après la colonne « apres » (en fin de table si apres est None)."""
    avec_bom, entete, lignes = lire_table(octets)
    place = len(entete) if apres is None else entete.index(apres) + 1
    entete = entete[:place] + [nom] + entete[place:]
    lignes = [l[:place] + ["%s-%d" % (valeur, n + 1)] + l[place:] for n, l in enumerate(lignes)]
    return ecrire_table(avec_bom, entete, lignes)


def dates_jjmmaaaa(octets, colonne):
    avec_bom, entete, lignes = lire_table(octets)
    i = entete.index(colonne)
    for l in lignes:
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", l[i])
        if m:
            l[i] = "%s/%s/%s" % (m.group(3), m.group(2), m.group(1))
    return ecrire_table(False, entete, lignes, encodage="cp1252")


def avec_parametres(octets, remplacements, ajouts):
    """parametres.csv : remplace la valeur de clés existantes, ajoute des lignes clé;valeur en fin de fichier."""
    lignes = enregistrements(octets)
    for i, ligne in enumerate(lignes):
        cle = ligne.lstrip(BOM).split(b";", 1)[0].decode("utf-8")
        if cle in remplacements:
            lignes[i] = (BOM if ligne.startswith(BOM) else b"") + ("%s;%s\r\n" % (cle, remplacements[cle])).encode("utf-8")
    if not lignes[-1].endswith(b"\n"):
        lignes[-1] += b"\r\n"
    lignes += [("%s;%s\r\n" % (cle, valeur)).encode("utf-8") for cle, valeur in ajouts]
    return b"".join(lignes)


def compte_responsable():
    """Un compte responsable fictif, au format exact de serveur.creer_compte (scrypt N=2^15, r=8, p=3)."""
    empreinte = hashlib.scrypt(MOT_DE_PASSE_ESSAI.encode("utf-8"), salt=SEL_FIXE, n=2 ** 15, r=8, p=3,
                               maxmem=64 * 1024 * 1024, dklen=32)
    return {"identifiant": "claire.essai", "prenom": "Claire", "nom": "Essai", "role": "responsable",
            "technicien_id": "", "actif": True, "algo": "scrypt-n15-r8-p3",
            "sel": base64.b64encode(SEL_FIXE).decode("ascii"), "empreinte": base64.b64encode(empreinte).decode("ascii"),
            "a_changer": False, "cree_le": INSTANT_COMPTE, "modifie_le": INSTANT_COMPTE, "mot_de_passe_le": INSTANT_COMPTE}


# ---------------------------------------------------------------- variantes

def definir_variantes(f3):
    """{nom: (description, base, supprimer, vider, {fichier: octets})} : seuls les fichiers qui changent."""
    ordres = f3["ordres_travail.csv"]
    entete_ordres = ordres.split(b"\r\n", 1)[0]
    coupe = entete_ordres.index(b"technicien_id") + len(b"technicien_id;temps_pr")
    comptes = json.dumps({"version": 1, "comptes": [compte_responsable()]}, ensure_ascii=False, indent=2).encode("utf-8")
    _, entete_eq, lignes_eq = lire_table(f3["equipements.csv"])
    b = "f3-v1.2.0"
    return {
        "f3-v2.0.0": (
            "Base f3-v1.2.0 plus les réglages de la 2.0 (mode Solo, clôture en une étape, technicien « moi ») et un "
            "compte responsable fictif dans acces/comptes.json (format 3 inchangé).", b, [], [],
            {"parametres.csv": avec_parametres(f3["parametres.csv"], {}, [("mode_solo", "'1"), ("cloture_une_etape", "'1"),
                                                                           ("solo_technicien_id", "TEC-0001")]),
             "acces/comptes.json": comptes}),
        "vide": ("equipements.csv de 0 octet (fichier créé puis jamais écrit).", b, [], ["equipements.csv"], {}),
        "entete-tronque": (
            "En-tête de ordres_travail.csv coupé au milieu du nom de colonne temps_prevu_h (fichier abîmé) ; les "
            "lignes de données sont intactes et plus larges que l'en-tête.", b, [], [],
            {"ordres_travail.csv": ordres[:coupe] + ordres[len(entete_ordres):]}),
        "colonnes-manquantes": (
            "equipements.csv sans les colonnes modele et valeur_remplacement.", b, [], [],
            {"equipements.csv": sans_colonnes(f3["equipements.csv"], {"modele", "valeur_remplacement"})}),
        "colonnes-en-trop": (
            "equipements.csv avec une colonne inconnue (colonne_maison) au milieu, après designation, et une autre "
            "(note_maison) en fin de table.", b, [], [],
            {"equipements.csv": avec_colonne(avec_colonne(f3["equipements.csv"], "colonne_maison", "designation", "maison"),
                                             "note_maison", None, "note")}),
        "sans-bom": ("Tous les fichiers sans BOM UTF-8.", b, [], [],
                     {nom: octets[3:] for nom, octets in f3.items() if octets.startswith(BOM)}),
        "table-absente": ("Sans wiki_pages.csv ni articles.csv : 22 tables.", b, ["wiki_pages.csv", "articles.csv"], [], {}),
        "melange": (
            "ordres_travail.csv au format 2 (sans la colonne astuce) dans une base dont version_schema vaut 3.", b, [], [],
            {"ordres_travail.csv": sans_colonnes(ordres, {"astuce"})}),
        "windows-1252": (
            "equipements.csv enregistré en Windows-1252, sans BOM, dates date_mes en JJ/MM/AAAA, comme après un "
            "enregistrement par Excel.", b, [], [],
            {"equipements.csv": dates_jjmmaaaa(f3["equipements.csv"], "date_mes")}),
        "plus-recent": (
            "Données d'une version plus récente : version_schema 4, colonne inconnue nouvelle_colonne_v4 en fin de "
            "ordres_travail.csv, table inconnue pieces_v4.csv.", b, [], [],
            {"parametres.csv": avec_parametres(f3["parametres.csv"], {"version_schema": "'4"}, []),
             "ordres_travail.csv": avec_colonne(ordres, "nouvelle_colonne_v4", None, "v4"),
             "pieces_v4.csv": ecrire_table(True, ["id", "designation", "stock"],
                                           [["PIE-0001", "Pièce du futur A", "3"], ["PIE-0002", "Pièce du futur B", "0"]])}),
    }


# ---------------------------------------------------------------- écriture

def ecrire_fichier(dossier, nom, octets):
    chemin = dossier / nom
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(octets)


def generer(sortie):
    sortie = Path(sortie)
    if sortie.exists():
        shutil.rmtree(str(sortie))
    sortie.mkdir(parents=True)
    bases = {"f1": construire_base(sources_f1()),
             "f2-v1.1.0": construire_base(sources_git("v1.1.0")),
             "f3-v1.2.0": construire_base(sources_git("v1.2.0"))}
    for nom, fichiers in bases.items():
        for fichier, octets in fichiers.items():
            ecrire_fichier(sortie / nom, fichier, octets)
    for nom, (description, base, supprimer, vider, fichiers) in definir_variantes(bases["f3-v1.2.0"]).items():
        manifeste = json.dumps({"base": base, "description": description, "supprimer": supprimer, "vider": vider},
                               ensure_ascii=False, indent=2) + "\n"
        ecrire_fichier(sortie / nom, "variante.json", manifeste.encode("utf-8"))
        for fichier, octets in fichiers.items():
            ecrire_fichier(sortie / nom, fichier, octets)
    return sortie


def main(argv=None):
    analyseur = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    analyseur.add_argument("--sortie", default=str(SORTIE_DEFAUT), help="dossier de sortie (vidé d'abord)")
    # Le LISEZMOI.md à côté des jeux est écrit à la main : on le garde s'il existe
    args = analyseur.parse_args(argv)
    sortie = Path(args.sortie)
    lisezmoi = sortie / "LISEZMOI.md"
    conserve = lisezmoi.read_bytes() if lisezmoi.is_file() else None
    generer(sortie)
    if conserve is not None:
        lisezmoi.write_bytes(conserve)
    print("Jeux écrits dans %s" % sortie)
    return 0


if __name__ == "__main__":
    sys.exit(main())
