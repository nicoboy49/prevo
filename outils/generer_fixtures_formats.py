"""Génère les jeux de fichiers d'exemple des formats de données (tests/fixtures/formats/), T182, T378, T394.

Quatre jeux de base, tirés des fichiers de référence, chaque table réduite à 12 enregistrements :
    f1          tests/fixtures/v1/                      (format 1)
    f2-v1.1.0   donnees/demo/ à l'étiquette v1.1.0      (format 2, 22 tables)
    f3-v1.2.0   donnees/demo/ à l'étiquette v1.2.0      (format 3, 24 tables)
    f3-v2.1.0   donnees/demo/ à l'étiquette v2.1.0      (format 3, 24 tables)
et des variantes stockées comme différences (variante.json + seulement les fichiers qui changent), dont
f4-v2.2.0 (base au format 4, 27 tables : f3-v2.1.0 complétée PAR CE SCRIPT, jamais par serveur.py ni js/formats.js,
avec des valeurs dans les colonnes et les tables nouvelles), plus-recent (f4-v2.2.0 au format 5 simulé :
version_schema 5, colonne nouvelle_colonne_v5, table pieces_v5) et reserves-a-reprendre (f3-v2.1.0 dont
controles_reglementaires.csv est fabriqué pour la reprise des observations en réserves, D183 ; réserves attendues :
tests/fixtures/formats/LISEZMOI.md).

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


# ---------------------------------------------------------------- jeu f4-v2.2.0 (base au format 4)
# Noms, ordre et défauts : .chantier/v2.2/CONCEPTION-L1.md §2 (recopiés ici : le jeu ne doit rien à serveur.py ni à
# js/). Cellules sous leur forme dans le fichier ; jeu canonique (dates AAAA-MM-JJ ou vides, booléens 0/1, nombres
# avec un point, aucune cellule à protéger par l'apostrophe), écrit comme Prévo l'écrit : un lecteur au format 4 le
# relit et le réécrit aux mêmes octets, des deux côtés.
COLONNES_DU_FORMAT_4 = {
    "equipements.csv": [("cout_arret_h", "")],
    "ordres_travail.csv": [("habilitation_requise", "")],
    "habilitations.csv": [("recyclage_mois", ""), ("justificatif", ""), ("catalogue_id", ""), ("nature_source", "")],
    "controles_reglementaires.csv": [("source_periodicite", "saisie"), ("nature_source", ""), ("catalogue_id", ""),
                                     ("catalogue_relu_le", "")],
}
# Valeurs des colonnes nouvelles, par identifiant (les autres lignes : défaut)
VALEURS_DU_FORMAT_4 = {
    "equipements.csv": {"EQ-0001": {"cout_arret_h": "180"}, "EQ-0007": {"cout_arret_h": "312.5"}},
    "ordres_travail.csv": {"OT-2025-0005": {"habilitation_requise": "BR"}},
    "habilitations.csv": {
        "HAB-0001": {"recyclage_mois": "36", "justificatif": "20250310-090000-titre-habilitation-BR.pdf",
                     "catalogue_id": "H02", "nature_source": "recommandation"},
        "HAB-0004": {"recyclage_mois": "60", "justificatif": "20211202-090000-caces-r489.pdf",
                     "catalogue_id": "H12", "nature_source": "recommandation"}},
    "controles_reglementaires.csv": {
        "CTR-0001": {"source_periodicite": "catalogue", "nature_source": "obligation", "catalogue_id": "C01",
                     "catalogue_relu_le": "2026-11-08"},
        "CTR-0002": {"source_periodicite": "catalogue", "nature_source": "obligation", "catalogue_id": "C03",
                     "catalogue_relu_le": "2026-11-08"}},
}
COLONNES_RESERVES = ["id", "controle_id", "date_controle", "texte", "gravite", "echeance_levee", "levee", "date_levee",
                     "commentaire_levee", "ot_id"]
COLONNES_GARANTIES = ["id", "equipement_id", "fournisseur_id", "date_debut", "date_fin", "conditions", "document",
                      "actif"]
COLONNES_CONTRATS = ["id", "fournisseur_id", "objet", "equipement_ids", "perimetre", "date_debut", "date_fin",
                     "preavis_mois", "reconduction_tacite", "reconduction_mois", "montant_annuel", "document", "actif"]
# Après la réserve reprise des observations de la 2.1 (RES-00001) : une réserve ouverte, une levée datée
RESERVES_DE_LA_2_2 = [
    ["CTR-0001", "2026-02-10", "Fin de course haut du palan à régler", "majeure", "2026-03-12", "0", "", "", ""],
    ["CTR-0002", "2026-03-18", "Avertisseur sonore de recul inaudible", "mineure", "2026-04-17", "1", "2026-04-02",
     "Avertisseur remplacé, essai concluant", ""],
]
GARANTIES = [
    ["GAR-0001", "EQ-0005", "FOU-0005", "2025-06-01", "2027-05-31",
     "Pièces et main-d'œuvre, hors garniture mécanique (pièce d'usure)", "", "1"],
    ["GAR-0002", "EQ-0007", "", "2024-09-15", "2026-09-14",
     "Garantie du constructeur : pièces seules, compresseur frigorifique compris", "", "1"],
]
CONTRATS = [
    # reconduction tacite (12 mois), préavis de 3 mois, deux équipements (« ; » : cellule entre guillemets)
    ["CTP-0001", "FOU-0002", "Maintenance préventive des compresseurs d'air", "EQ-0001;EQ-0002",
     "Deux visites par an, dépannage sous 24 h ouvrées", "2025-01-01", "2026-12-31", "3", "1", "12", "4800", "", "1"],
    ["CTP-0002", "FOU-0003", "Thermographie des armoires électriques", "",
     "Armoires électriques de l'atelier (AE-01 à AE-03), une campagne par an", "2026-01-01", "2026-12-31", "1", "0",
     "", "1350", "", "1"],
]
# Comme aProteger (js/donnees.js) : un texte qui commence ainsi, ou qui ressemble à un nombre, une date, une heure ou
# un pourcentage, prendrait l'apostrophe de protection ; le jeu n'en a pas besoin (refusé s'il en avait).
MOTIF_TEXTE_A_PROTEGER = re.compile(r"\A(?:[=+\-@\t\r']|[0-9][0-9.,:/%eE+\- ]*\Z)")


def table_canonique(octets):
    """(en-tête, lignes) d'une table de la base, refusée si Prévo ne la réécrivait pas aux mêmes octets."""
    avec_bom, entete, lignes = lire_table(octets)
    if not avec_bom or table_prevo(entete, lignes) != octets or any(len(l) != len(entete) for l in lignes):
        raise ValueError("table de f3-v2.1.0 que Prévo ne réécrirait pas à l'identique")
    return entete, lignes


def au_format_4(nom, octets):
    """Table de f3-v2.1.0 complétée au format 4 : colonnes nouvelles en fin, défaut ou valeur de VALEURS_DU_FORMAT_4."""
    entete, lignes = table_canonique(octets)
    colonnes = COLONNES_DU_FORMAT_4[nom]
    valeurs = VALEURS_DU_FORMAT_4[nom]
    if not set(valeurs) <= {l[0] for l in lignes}:
        raise ValueError("%s : identifiant absent de f3-v2.1.0" % nom)
    return table_prevo(entete + [c for c, _ in colonnes],
                       [l + [valeurs.get(l[0], {}).get(c, defaut) for c, defaut in colonnes] for l in lignes])


def reserve_reprise_de_la_2_1(octets_controles):
    """Réserves que le passage au format 4 tire des observations de f3-v2.1.0 (D183, CONCEPTION-L1 §3.2), pour cette
    base canonique : une par ligne non vide (coupée sur CRLF, CR ou LF, bords blancs retirés), date = derniere_date,
    levée si observations_levees vaut 1 (commentaire fixe), le reste vide."""
    entete, lignes = table_canonique(octets_controles)
    i = {nom: entete.index(nom) for nom in ("id", "observations", "observations_levees", "derniere_date")}
    reserves = []
    for ligne in lignes:
        if ligne[i["observations"]].startswith("'"):
            raise ValueError("observations protégées : hors du cas canonique")
        levee = "1" if ligne[i["observations_levees"]] == "1" else "0"
        for morceau in re.split(r"\r\n|\r|\n", ligne[i["observations"]]):
            if morceau.strip():
                reserves.append(["RES-%05d" % (len(reserves) + 1), ligne[i["id"]], ligne[i["derniere_date"]],
                                 morceau.strip(), "", "", levee, "",
                                 "levée avant la 2.2, date inconnue" if levee == "1" else "", ""])
    return reserves


def jeu_f4(f3_21):
    """{fichier: octets} des fichiers de f4-v2.2.0 qui diffèrent de f3-v2.1.0 (les 20 autres tables sont gardées)."""
    reserves = reserve_reprise_de_la_2_1(f3_21["controles_reglementaires.csv"])
    reserves += [["RES-%05d" % (len(reserves) + 1 + n)] + r for n, r in enumerate(RESERVES_DE_LA_2_2)]
    textes = [r[3] for r in reserves] + [r[8] for r in reserves] + [c for g in GARANTIES for c in g[5:6]] + \
             [c for t in CONTRATS for c in t[2:5]]
    if any(t and MOTIF_TEXTE_A_PROTEGER.search(t) for t in textes):
        raise ValueError("texte qui prendrait l'apostrophe de protection : hors du cas canonique")
    fichiers = {nom: au_format_4(nom, f3_21[nom]) for nom in COLONNES_DU_FORMAT_4}
    fichiers["parametres.csv"] = avec_parametres(f3_21["parametres.csv"], {"version_schema": "'4"}, [])
    fichiers["reserves_controle.csv"] = table_prevo(COLONNES_RESERVES, reserves)
    fichiers["garanties.csv"] = table_prevo(COLONNES_GARANTIES, GARANTIES)
    fichiers["contrats_prestataires.csv"] = table_prevo(COLONNES_CONTRATS, CONTRATS)
    return fichiers


def avec_colonne_en_fin(octets, nom, valeur):
    """Table écrite comme Prévo l'écrit, avec une colonne inconnue en fin (« valeur-1 », « valeur-2 »…)."""
    entete, lignes = table_canonique(octets)
    return table_prevo(entete + [nom], [l + ["%s-%d" % (valeur, n + 1)] for n, l in enumerate(lignes)])


def avec_colonne_videe(octets, nom):
    """Table écrite comme Prévo l'écrit, la colonne « nom » vidée sur chaque ligne."""
    entete, lignes = table_canonique(octets)
    i = entete.index(nom)
    return table_prevo(entete, [l[:i] + [""] + l[i + 1:] for l in lignes])


# ---------------------------------------------------------------- variantes

def definir_variantes(f3, f3_21):
    """{nom: (description, base, supprimer, vider, {fichier: octets})} : seuls les fichiers qui changent.
    f3 : base f3-v1.2.0 ; f3_21 : base f3-v2.1.0."""
    ordres = f3["ordres_travail.csv"]
    entete_ordres = ordres.split(b"\r\n", 1)[0]
    coupe = entete_ordres.index(b"technicien_id") + len(b"technicien_id;temps_pr")
    comptes = json.dumps({"version": 1, "comptes": [compte_responsable()]}, ensure_ascii=False, indent=2).encode("utf-8")
    f4 = jeu_f4(f3_21)
    b = "f3-v1.2.0"
    return {
        "f4-v2.2.0": (
            "Base au format 4 (2.2) : f3-v2.1.0 complétée par le générateur (jamais par serveur.py ni js/formats.js), "
            "version_schema 4, 27 tables ; colonnes du format 4 en fin de equipements, ordres_travail, habilitations "
            "et controles_reglementaires, avec des valeurs (coût d'une heure d'arrêt sur 2 équipements, habilitation "
            "exigée sur 1 OT, recyclage, justificatif, catalogue et nature sur 2 habilitations, périodicité tirée du "
            "catalogue et nature de la source sur 2 contrôles) ; reserves_controle (la réserve reprise de la 2.1, une "
            "ouverte, une levée datée), garanties (2), contrats_prestataires (2, dont un en reconduction tacite). "
            "Jeu canonique : rien à migrer, relu et réécrit aux mêmes octets des deux côtés.", "f3-v2.1.0", [], [],
            f4),
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
            "Données d'une version plus récente : f4-v2.2.0 (toutes les tables et colonnes du format 4) avec "
            "version_schema 5, colonne inconnue nouvelle_colonne_v5 en fin de ordres_travail.csv, table inconnue "
            "pieces_v5.csv, et habilitations.justificatif vide (aucun document cité : le jeu n'en fournit pas).",
            "f4-v2.2.0", [], [],
            {"parametres.csv": avec_parametres(f4["parametres.csv"], {"version_schema": "'5"}, []),
             "ordres_travail.csv": avec_colonne_en_fin(f4["ordres_travail.csv"], "nouvelle_colonne_v5", "v5"),
             "habilitations.csv": avec_colonne_videe(f4["habilitations.csv"], "justificatif"),
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
