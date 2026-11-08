"""Génère les jeux de fichiers d'exemple des formats de données (tests/fixtures/formats/), T182, T378.

Quatre jeux de base, tirés des fichiers de référence, chaque table réduite à 12 enregistrements :
    f1          tests/fixtures/v1/                      (format 1)
    f2-v1.1.0   donnees/demo/ à l'étiquette v1.1.0      (format 2, 22 tables)
    f3-v1.2.0   donnees/demo/ à l'étiquette v1.2.0      (format 3, 24 tables)
    f3-v2.1.0   donnees/demo/ à l'étiquette v2.1.0      (format 3, 24 tables)
et des variantes stockées comme différences (variante.json + seulement les fichiers qui changent), dont
plus-recent (format 5 simulé : version_schema 5, colonne nouvelle_colonne_v5, table pieces_v5) et
reserves-a-reprendre (f3-v2.1.0 dont controles_reglementaires.csv est fabriqué pour la reprise des observations
en réserves, D183 ; réserves attendues : tests/fixtures/formats/LISEZMOI.md).

Reproductible octet pour octet : mêmes entrées, mêmes sorties (aucune date du jour, aucun hasard ; le sel du
compte fictif est fixe). Bibliothèque standard seulement ; git doit connaître les étiquettes v1.1.0, v1.2.0 et
v2.1.0.

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

# Cellule entre guillemets : même règle que celluleCsv (js/donnees.js) et cellule_csv (serveur.py)
MOTIF_A_GUILLEMETER = re.compile(r'[;"\r\n]|\A[ \t]|[ \t]\Z')

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


def cellule_prevo(texte):
    return '"' + texte.replace('"', '""') + '"' if MOTIF_A_GUILLEMETER.search(texte) else texte


def table_prevo(entete, lignes):
    """Octets d'une table telle que Prévo l'écrit (BOM, « ; », CRLF après chaque ligne, guillemets de celluleCsv) ;
    les cellules sont données sous leur forme dans le fichier (apostrophe de protection comprise)."""
    texte = "".join(";".join(cellule_prevo(c) for c in ligne) + "\r\n" for ligne in [entete] + list(lignes))
    return BOM + texte.encode("utf-8")


# Variante reserves-a-reprendre : controles_reglementaires.csv fabriqué (cellules sous leur forme dans le fichier).
# Jeu canonique (dates AAAA-MM-JJ ou vides, booléens 0/1) : lu de la même façon par le navigateur et le serveur ;
# aucune cellule ne finit par une espace, une tabulation ou un CR (Donnees.csv.analyser les retirerait).
COLONNE_INCONNUE_CONTROLES = "remarque_maison"
CONTROLES_A_REPRENDRE = [
    # 3 lignes non vides entre des lignes blanches (espaces, tabulation), bords blancs de chaque ligne
    ["CTR-0001", "EQ-0018", "Vérification générale périodique du pont roulant", "Arrêté du 1er mars 2004 (VGP), art. 23",
     "12", "Bureau Alpin de Contrôle (démo)", "2026-02-10", "2027-02-10", "",
     "\n \nGarde-corps de la passerelle desserré\n\n\t\n   Fin de course haut à régler \n \n"
     "Câble de levage : un toron cassé\n\n", "0"],
    # observations levées : réserves levées, date de levée vide
    ["CTR-0002", "EQ-0030", "Vérification générale périodique du chariot élévateur",
     "Arrêté du 1er mars 2004 (VGP), art. 23", "6", "Bureau Alpin de Contrôle (démo)", "2026-03-18", "2026-09-18", "",
     "Klaxon de recul inaudible\nCeinture du siège conducteur usée", "1"],
    # observations vides, levées puis non levées : aucune réserve
    ["CTR-0003", "EQ-0010", "Vérification périodique des installations électriques",
     "Code du travail, art. R4226-16 ; arrêté du 26 décembre 2011", "12", "Certif-Elec Services (démo)", "2025-11-12",
     "2026-11-12", "", "", "1"],
    ["CTR-0004", "EQ-0003", "Inspection périodique du réservoir d'air comprimé", "Arrêté du 20 novembre 2017", "36",
     "Bureau Alpin de Contrôle (démo)", "2025-04-03", "2028-04-03", "", "", "0"],
    # lignes qui commencent par « - » ou « = » (puces gardées) ; la cellule commence par « - » : apostrophe
    ["CTR-0005", "EQ-0007", "Contrôle d'étanchéité du circuit frigorifique", "Règlement (UE) 2024/573", "12",
     "Frigo-Contrôle Sud (démo)", "2026-03-24", "2027-03-24", "",
     "'- Raccord de la vanne 3 suintant\n= Pression basse à surveiller\n- Étiquette du fluide illisible", "0"],
    # « ; » et guillemets
    ["CTR-0006", "EQ-0009", "Contrôle de l'aération et de l'assainissement des locaux", "Code du travail, art. R4222-20",
     "12", "Bureau Alpin de Contrôle (démo)", "2026-06-02", "2027-06-02", "",
     'Gaine "B" percée ; débit insuffisant\nFiltre du caisson "F7" colmaté', "0"],
    # CRLF, LF et CR dans une même cellule
    ["CTR-0007", "EQ-0011", "Vérification périodique de la porte automatique de l'atelier",
     "Code du travail, art. R4224-12 ; arrêté du 21 décembre 1993", "6", "Portes Contrôle Alpes (démo)", "2026-01-15",
     "2026-07-15", "",
     "Cellule de sécurité inopérante\r\nBord sensible fendu\nSignalisation au sol effacée\rNotice absente du local",
     "0"],
    # derniere_date vide : date du contrôle vide
    ["CTR-0008", "EQ-0010", "Vérification de l'éclairage de sécurité", "Arrêté du 14 décembre 2011", "12",
     "Certif-Elec Services (démo)", "", "", "", "Rapport du contrôle initial non retrouvé", "0"],
    # observations faites de lignes blanches seulement : aucune réserve
    ["CTR-0009", "EQ-0012", "Vérification des extincteurs de l'atelier", "Code du travail, art. R4227-39", "12",
     "Sécurité Incendie Savoie (démo)", "2026-05-20", "2027-05-20", "", "\n \t\n", "0"],
]


def controles_a_reprendre(octets_base):
    """controles_reglementaires.csv de la variante : en-tête de la base (2.1.0) suivi d'une colonne inconnue."""
    _, entete, _ = lire_table(octets_base)
    if any(len(cellules) != len(entete) for cellules in CONTROLES_A_REPRENDRE):
        raise ValueError("CONTROLES_A_REPRENDRE : nombre de cellules différent de l'en-tête de la base")
    lignes = [cellules + ["maison-%d" % (n + 1)] for n, cellules in enumerate(CONTROLES_A_REPRENDRE)]
    return table_prevo(entete + [COLONNE_INCONNUE_CONTROLES], lignes)


def compte_responsable():
    """Un compte responsable fictif, au format exact de serveur.creer_compte (scrypt N=2^15, r=8, p=3)."""
    empreinte = hashlib.scrypt(MOT_DE_PASSE_ESSAI.encode("utf-8"), salt=SEL_FIXE, n=2 ** 15, r=8, p=3,
                               maxmem=64 * 1024 * 1024, dklen=32)
    return {"identifiant": "claire.essai", "prenom": "Claire", "nom": "Essai", "role": "responsable",
            "technicien_id": "", "actif": True, "algo": "scrypt-n15-r8-p3",
            "sel": base64.b64encode(SEL_FIXE).decode("ascii"), "empreinte": base64.b64encode(empreinte).decode("ascii"),
            "a_changer": False, "cree_le": INSTANT_COMPTE, "modifie_le": INSTANT_COMPTE, "mot_de_passe_le": INSTANT_COMPTE}


# ---------------------------------------------------------------- variantes

def definir_variantes(f3, f3_21):
    """{nom: (description, base, supprimer, vider, {fichier: octets})} : seuls les fichiers qui changent.
    f3 : base f3-v1.2.0 ; f3_21 : base f3-v2.1.0."""
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
            "Données d'une version plus récente : version_schema 5, colonne inconnue nouvelle_colonne_v5 en fin de "
            "ordres_travail.csv, table inconnue pieces_v5.csv.", b, [], [],
            {"parametres.csv": avec_parametres(f3["parametres.csv"], {"version_schema": "'5"}, []),
             "ordres_travail.csv": avec_colonne(ordres, "nouvelle_colonne_v5", None, "v5"),
             "pieces_v5.csv": ecrire_table(True, ["id", "designation", "stock"],
                                           [["PIE-0001", "Pièce du futur A", "3"], ["PIE-0002", "Pièce du futur B", "0"]])}),
        "reserves-a-reprendre": (
            "Base f3-v2.1.0 dont controles_reglementaires.csv est fabriqué pour la reprise des observations en "
            "réserves (D183) : 9 contrôles (lignes non vides entre des lignes blanches, observations levées, "
            "observations vides levées et non levées, lignes qui commencent par « - » ou « = », « ; » et guillemets, "
            "CRLF, LF et CR dans une même cellule, derniere_date vide, lignes blanches seulement) et une colonne "
            "inconnue remarque_maison en fin ; dates AAAA-MM-JJ et booléens 0/1 (jeu canonique), format 3.",
            "f3-v2.1.0", [], [],
            {"controles_reglementaires.csv": controles_a_reprendre(f3_21["controles_reglementaires.csv"])}),
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
             "f3-v1.2.0": construire_base(sources_git("v1.2.0")),
             "f3-v2.1.0": construire_base(sources_git("v2.1.0"))}
    for nom, fichiers in bases.items():
        for fichier, octets in fichiers.items():
            ecrire_fichier(sortie / nom, fichier, octets)
    variantes = definir_variantes(bases["f3-v1.2.0"], bases["f3-v2.1.0"])
    for nom, (description, base, supprimer, vider, fichiers) in variantes.items():
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
