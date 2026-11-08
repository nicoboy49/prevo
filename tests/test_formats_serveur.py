"""Tests du registre des formats côté serveur (serveur.py, section « Formats des données (miroir de js/formats.js,
T184) ») : cle_de_colonne, colonnes_du_format, tables_du_format, format_du_fichier, version_de_base, ETAPES_FORMAT,
migrer_tables, reserves_reprises (chantier « socle de données », T184 ; format 4 de la 2.2, T385 ; reprise des
observations en réserves, T390 ; décisions D167, D168, D183 ; ARCHITECTURE.md §5.6, §14.1, §20.2 ; CS169, CS170).

Chaque jeu de tests/fixtures/formats (tests/jeux_formats.py) est copié dans un dossier temporaire (règle du chantier :
jamais ailleurs). Côté serveur, une base est {table: {'entete', 'lignes': [{colonne: cellule}]}}, cellules lues par
lire_csv_tolerant (apostrophe de protection comprise) et réécrites par ecrire_tableau_csv.

1. TestRegistreServeur (Python seul, sans navigateur) : colonnes et tables de chaque format, cohérence des listes
   ajoutées avec COLONNES_PAR_TABLE et COLONNES_DES_FORMATS_SUIVANTS ; pour chaque jeu, format_du_fichier,
   version_de_base et migrer_tables : aucune cellule d'origine perdue ni modifiée (champ à champ), colonnes nouvelles
   en fin avec leur défaut (après les colonnes inconnues, qui restent à leur place), tables créées (wiki et format 4
   compris), journal (f1 3 lignes, f2 2, f3 1), idempotence, pureté (entrée inchangée), plus-recent (version 5)
   laissé intact par migrer_tables(base, 5, 4) ; détail de l'étape 3→4 sur les bases 2.1.0 ; cas fabriqués et
   erreurs. Reprise des observations en réserves (D183, CS170) : réserves du LISEZMOI des jeux (cellules écrites
   comme Prévo les écrit), cas fabriqués (formes d'Excel, numérotation en texte au-delà de la limite de chiffres de
   int(), réserve déjà là), étape 3→4 rejouée sans rien de plus.
2. TestConcordanceNavigateur (Chromium, page-vide.html en file://) : mêmes listes que Schema et Formats (colonnes,
   tables, défauts, étapes) ; mêmes résultats que Formats.formatDuFichier, Formats.versionDeBase, Formats.ETAPES et
   Donnees.csv.relireValeur / ecrireValeur sur des cas fabriqués ; pour chaque jeu, lecture + migration + écriture
   côté navigateur (Donnees.csv.analyser, Formats.migrer, Donnees.csv.serialiser) et côté serveur
   (lire_csv_tolerant, migrer_tables, ecrire_tableau_csv) → mêmes octets par table (reserves_controle reprise
   comprise), mêmes formats, même journal ; reserves_reprises donne les lignes de Formats.reservesReprises (écrites
   par Donnees.csv.ecrireValeur) sur des fichiers fabriqués (oui, x, vrai, JJ/MM/AAAA, U+2028 et U+0085 qui ne
   coupent pas une ligne, apostrophes, « ; », guillemets, réserve déjà là), et ses copies de lecture des dates et
   des booléens les résultats de Donnees.normaliser.

Écarts PRÉEXISTANTS entre les deux lecteurs/écrivains CSV (pas entre Formats.migrer et migrer_tables, qui rendent les
mêmes en-têtes), documentés par des tests expectedFailure, et cernés chacun par un test qui passe (l'écart est
exactement celui décrit, rien d'autre) ; à trancher par l'orchestrateur :
    A. colonnes-en-trop, reserves-a-reprendre : Donnees.csv.serialiser réécrit les colonnes inconnues en fin de
       fichier, après toutes les colonnes du schéma ; ecrire_tableau_csv garde l'en-tête migré tel quel (colonne_maison
       reste après designation ; remarque_maison reste avant les colonnes que l'étape 3→4 ajoute en fin de
       controles_reglementaires). Seule la place de la colonne inconnue diffère.
    B. colonnes-manquantes : Donnees.csv.analyser complète chaque ligne avec tous les champs du schéma (défaut) et
       serialiser écrit toujours toutes les colonnes du schéma à leur place ; l'étape 3→4 ajoute aux deux en-têtes
       migrés (identiques) les colonnes manquantes en fin (modele, valeur_remplacement, cout_arret_h), et le serveur
       réécrit cet en-tête tel quel (modele en fin). Même écart pour plus-recent (base au format 5, rien n'est migré) :
       ses fichiers, fabriqués avant le format 4, n'ont pas les colonnes du format 4 (equipements, ordres_travail,
       habilitations, controles_reglementaires), que serialiser écrit (test_concordance_plus_recent). Le jeu melange
       (ordres_travail sans astuce dans une base au format 3) n'est plus un écart depuis le format 4 : l'étape 3→4
       ajoute astuce puis habilitation_requise en fin, à leur place du schéma.
    C. windows-1252 : Donnees.csv.analyser normalise les valeurs à la lecture (date_mes 12/03/2019 → 2019-03-12) ;
       lire_csv_tolerant garde les cellules brutes. Les deux lecteurs acceptent le fichier (Windows-1252).
Pour vide et entete-tronque : même format détecté des deux côtés (0), aucune exception (octets non comparés).

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_formats_serveur.py" -v
"""
import base64
import copy
import importlib.util
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from commun import NB_TABLES, RACINE, CasNavigateur, charger_scripts  # noqa: E402
from jeux_formats import JEUX, copier_jeu  # noqa: E402


def charger_serveur():
    specification = importlib.util.spec_from_file_location("serveur_prevo_formats_serveur", RACINE / "serveur.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


serveur = charger_serveur()

SCRIPTS = ["js/lib/papaparse.min.js", "js/schema.js", "js/formats.js", "js/donnees.js"]
FORMAT_COURANT = 4
CARACTERE_BOM = chr(0xFEFF)
INSECABLE, INSECABLE_FINE, CADRATIN, IDEOGRAPHIQUE = chr(0xA0), chr(0x202F), chr(0x2003), chr(0x3000)
ESPACE_NULLE, LIGNE_SUIVANTE, SEPARATEUR_DE_FICHIER = chr(0x200B), chr(0x85), chr(0x1C)

# Ce que chaque format ajoute : recopie de ARCHITECTURE.md §14.1 (format 2), §20.2 (format 3) et de la note de
# conception du format 4 (2.2, §2.1 à §2.3), indépendante de serveur.py et de js/ (les tests les comparent).
COLONNES_AJOUTEES = {
    2: {"equipements": ["valeur_remplacement"], "demandes": ["symptome_code", "ot_origine_id"],
        "ordres_travail": ["anomalie_constatee"]},
    3: {"ordres_travail": ["astuce"]},
    4: {"equipements": ["cout_arret_h"], "ordres_travail": ["habilitation_requise"],
        "habilitations": ["recyclage_mois", "justificatif", "catalogue_id", "nature_source"],
        "controles_reglementaires": ["source_periodicite", "nature_source", "catalogue_id", "catalogue_relu_le"]},
}
TABLES_AJOUTEES = {2: [], 3: ["wiki_pages", "wiki_journal"], 4: ["reserves_controle", "garanties",
                                                                 "contrats_prestataires"]}
DEFAUTS_AJOUTES = {"valeur_remplacement": "", "symptome_code": "", "ot_origine_id": "", "anomalie_constatee": "0",
                   "astuce": "", "cout_arret_h": "", "habilitation_requise": "", "recyclage_mois": "",
                   "justificatif": "", "catalogue_id": "", "nature_source": "", "source_periodicite": "saisie",
                   "catalogue_relu_le": ""}
# Défauts des champs des tables du format 4 (note de conception §2.3), sans apostrophe.
DEFAUTS_DES_TABLES_AJOUTEES = {"reserves_controle": {"levee": "0"}, "garanties": {"actif": "1"},
                               "contrats_prestataires": {"reconduction_tacite": "0", "actif": "1"}}
# Description de l'étape 3→4, au mot près (note de conception du format 4, §2.4 ; la même dans js/formats.js).
DESCRIPTION_FORMAT_4 = (
    "Format 4 (version 2.2) : colonnes equipements.cout_arret_h, ordres_travail.habilitation_requise, "
    "habilitations.recyclage_mois, habilitations.justificatif, habilitations.catalogue_id, habilitations.nature_source, "
    "controles_reglementaires.source_periodicite (défaut saisie), controles_reglementaires.nature_source, "
    "controles_reglementaires.catalogue_id et controles_reglementaires.catalogue_relu_le en fin de table ; tables "
    "reserves_controle (observations reprises, une réserve par ligne, D183), garanties et contrats_prestataires "
    "(vides).")
# Format des fichiers de chaque jeu et format de la base (version_schema) ; les autres jeux : format 3 (2.0 et 2.1).
FORMAT_DES_JEUX = 3
FORMAT_DES_FICHIERS = {"f1": 1, "f2-v1.1.0": 2}
VERSION_DE_BASE = {"f1": 1, "f2-v1.1.0": 2, "plus-recent": 5}
FORMATS_PARTICULIERS = {
    ("entete-tronque", "ordres_travail"): 0,     # en-tête coupé dans temps_prevu_h : colonnes du format 1 manquantes
    ("colonnes-manquantes", "equipements"): 0,   # sans modele (format 1) ni valeur_remplacement
    ("vide", "equipements"): 0,                  # 0 octet : aucun en-tête
    ("melange", "ordres_travail"): 2,            # sans astuce, dans une base au format 3
    ("plus-recent", "pieces_v5"): None,          # table inconnue du schéma
}
LIGNES_DE_JOURNAL = {
    1: ["passage au format 2 du fichier", "passage au format 3 du fichier", "passage au format 4 du fichier"],
    2: ["passage au format 3 du fichier", "passage au format 4 du fichier"],
    3: ["passage au format 4 du fichier"],
}
# Concordance navigateur / serveur : jeux dont les octets doivent être identiques, table par table.
JEUX_CONCORDANTS = ("f1", "f2-v1.1.0", "f3-v1.2.0", "f3-v2.0.0", "sans-bom", "table-absente", "plus-recent",
                    "f3-v2.1.0", "melange")
# Écarts préexistants entre lecteurs/écrivains (docstring du module) : jeu → (table touchée, nature de l'écart).
ECARTS_DOCUMENTES = {
    "colonnes-en-trop": ("equipements", "colonnes"),      # A : colonnes inconnues réécrites en fin par serialiser
    "reserves-a-reprendre": ("controles_reglementaires", "colonnes"),     # A : remarque_maison
    "colonnes-manquantes": ("equipements", "colonnes"),   # B : colonnes du schéma toujours écrites par serialiser
    "windows-1252": ("equipements", "valeurs"),           # C : dates normalisées par analyser
}
JEUX_ABIMES = {"vide": "equipements", "entete-tronque": "ordres_travail"}

# Reprise des observations en réserves (D183, CS170) : texte fixe du commentaire de levée, colonnes de
# reserves_controle (note de conception du format 4, §2.2) et réserves attendues des deux jeux de la 2.2, recopiées de
# tests/fixtures/formats/LISEZMOI.md, en CELLULES du fichier (« - Raccord… » s'écrit « '- Raccord… ») :
# (id, controle_id, date_controle, texte, levee).
COMMENTAIRE_LEVEE_REPRISE = "levée avant la 2.2, date inconnue"
COLONNES_RESERVES = ["id", "controle_id", "date_controle", "texte", "gravite", "echeance_levee", "levee", "date_levee",
                     "commentaire_levee", "ot_id"]
RESERVES_DU_LISEZMOI = {
    "reserves-a-reprendre": [
        ("RES-00001", "CTR-0001", "2026-02-10", "Garde-corps de la passerelle desserré", "0"),
        ("RES-00002", "CTR-0001", "2026-02-10", "Fin de course haut à régler", "0"),
        ("RES-00003", "CTR-0001", "2026-02-10", "Câble de levage : un toron cassé", "0"),
        ("RES-00004", "CTR-0002", "2026-03-18", "Klaxon de recul inaudible", "1"),
        ("RES-00005", "CTR-0002", "2026-03-18", "Ceinture du siège conducteur usée", "1"),
        ("RES-00006", "CTR-0005", "2026-03-24", "'- Raccord de la vanne 3 suintant", "0"),
        ("RES-00007", "CTR-0005", "2026-03-24", "'= Pression basse à surveiller", "0"),
        ("RES-00008", "CTR-0005", "2026-03-24", "'- Étiquette du fluide illisible", "0"),
        ("RES-00009", "CTR-0006", "2026-06-02", 'Gaine "B" percée ; débit insuffisant', "0"),
        ("RES-00010", "CTR-0006", "2026-06-02", 'Filtre du caisson "F7" colmaté', "0"),
        ("RES-00011", "CTR-0007", "2026-01-15", "Cellule de sécurité inopérante", "0"),
        ("RES-00012", "CTR-0007", "2026-01-15", "Bord sensible fendu", "0"),
        ("RES-00013", "CTR-0007", "2026-01-15", "Signalisation au sol effacée", "0"),
        ("RES-00014", "CTR-0007", "2026-01-15", "Notice absente du local", "0"),
        ("RES-00015", "CTR-0008", "", "Rapport du contrôle initial non retrouvé", "0"),
    ],
    "f3-v2.1.0": [
        ("RES-00001", "CTR-0004", "2025-04-03", "Purgeur automatique du réservoir défectueux : à remplacer avant la "
                                                "prochaine inspection.", "0"),
    ],
}


def reserve_complete(id, controle_id, date_controle, texte, levee):
    """Ligne entière de reserves_controle d'une réserve reprise, en cellules (D183 : gravité, échéance, date de levée
    et OT vides ; commentaire fixe seulement si levée), dans l'ordre des colonnes du schéma."""
    return {"id": id, "controle_id": controle_id, "date_controle": date_controle, "texte": texte, "gravite": "",
            "echeance_levee": "", "levee": levee, "date_levee": "",
            "commentaire_levee": COMMENTAIRE_LEVEE_REPRISE if levee == "1" else "", "ot_id": ""}


def controle_fabrique(identifiant, observations, levees, date):
    """Ligne de controles_reglementaires en cellules (None : colonne absente de la ligne)."""
    ligne = {"id": identifiant, "equipement_id": "EQ-0001", "observations": observations,
             "observations_levees": levees, "derniere_date": date}
    return {colonne: cellule for colonne, cellule in ligne.items() if cellule is not None}


# Cas fabriqués de la reprise, en CELLULES du fichier (formes d'Excel, apostrophes, bords blancs, U+2028 et U+0085 qui
# ne coupent pas une ligne) ; les mêmes que tests/test_formats_js.py (test_reserves_reprises_cas_fabriques), plus les
# apostrophes de protection. Réserves reçues : plus grand identifiant exact RES-12 (bords blancs retirés), donc
# numérotation depuis RES-00013 ; CTR-0002 en a déjà une (controle_id aux bords blancs).
CONTROLES_FABRIQUES = [
    controle_fabrique("CTR-0001", "Un\r\nDeux\rTrois\nQuatre", "oui", "15/01/2024"),
    controle_fabrique("CTR-0002", "Déjà repris", "0", "2024-02-01"),
    controle_fabrique("", "Sans identifiant", "1", "2024-02-02"),
    controle_fabrique("   ", "Identifiant blanc", "1", "2024-02-03"),
    controle_fabrique(" CTR-0003 ", "  - puce gardée  \n" + IDEOGRAPHIQUE + "• autre \n1. numérotée\t", "X",
                      " 5.3.2024 "),
    controle_fabrique("CTR-0004", "ligne même ligne\u0085encore\u000bet\u000cfin toujours", "non", "31/02/2024"),
    controle_fabrique("CTR-0005", "Premier doublon", "1", ""),
    controle_fabrique("CTR-0005", "Second doublon", "faux", "demain"),
    controle_fabrique("CTR-0006", "", "1", "2024-01-01"),
    controle_fabrique("CTR-0007", " \t\r\n  ", "1", "2024-01-01"),
    {"id": "CTR-0008"},
    controle_fabrique("CTR-0009", "Levée par vrai", " Vrai ", "2024-1-5"),
    controle_fabrique("CTR-0010", "\u0085bord NEL\u0085\n﻿bord BOM﻿\n bord LS ", "peut-être", None),
    controle_fabrique("CTR-0011", "'- garde-corps\n=SOMME(A1)\n'abc\n12/03\nGaine \"B\" ; percée", "1", "'2024-01-15"),
    controle_fabrique("CTR-0012", "'", "constructor", "29/02/0000"),
    controle_fabrique("CTR-0013", "Bissextile de Date.UTC", "TRUE", "29/02/0004"),
]
RESERVES_FABRIQUEES = [
    {"id": "RES-00007", "controle_id": " CTR-0002 ", "texte": "gardée"},
    {"id": " RES-12 ", "controle_id": "CTR-0099"},
    {"id": "RES-0003", "controle_id": ""},
    {"id": "res-00099", "controle_id": "CTR-0098"},
    {"id": "RES-00050x"}, {"id": "RES-"}, {"id": "RES-1e3"}, {"id": "RES-١٢٣"}, {"id": "RES--5"},
    {"id": "RES-１００"},
]
RESERVES_FABRIQUEES_ATTENDUES = [
    ("RES-00013", "CTR-0001", "2024-01-15", "Un", "1"),
    ("RES-00014", "CTR-0001", "2024-01-15", "Deux", "1"),
    ("RES-00015", "CTR-0001", "2024-01-15", "Trois", "1"),
    ("RES-00016", "CTR-0001", "2024-01-15", "Quatre", "1"),
    # CTR-0002 a déjà une réserve ; identifiants vide et blanc : rien
    ("RES-00017", "CTR-0003", "2024-03-05", "'- puce gardée", "1"),
    ("RES-00018", "CTR-0003", "2024-03-05", "• autre", "1"),
    ("RES-00019", "CTR-0003", "2024-03-05", "1. numérotée", "1"),
    ("RES-00020", "CTR-0004", "31/02/2024", "ligne même ligne\u0085encore\u000bet\u000cfin toujours", "0"),
    ("RES-00021", "CTR-0005", "", "Premier doublon", "1"),
    ("RES-00022", "CTR-0005", "demain", "Second doublon", "0"),
    # CTR-0006 et CTR-0007 : vide ou blanc ; CTR-0008 : sans observations
    ("RES-00023", "CTR-0009", "2024-01-05", "Levée par vrai", "1"),
    ("RES-00024", "CTR-0010", "", "\u0085bord NEL\u0085", "0"),
    ("RES-00025", "CTR-0010", "", "bord BOM", "0"),
    ("RES-00026", "CTR-0010", "", "bord LS", "0"),
    # Cellule protégée (« '- garde-corps… ») relue sans l'apostrophe, chaque ligne réécrite comme un champ texte
    ("RES-00027", "CTR-0011", "'2024-01-15", "'- garde-corps", "1"),
    ("RES-00028", "CTR-0011", "'2024-01-15", "'=SOMME(A1)", "1"),
    ("RES-00029", "CTR-0011", "'2024-01-15", "''abc", "1"),
    ("RES-00030", "CTR-0011", "'2024-01-15", "'12/03", "1"),
    ("RES-00031", "CTR-0011", "'2024-01-15", 'Gaine "B" ; percée', "1"),
    ("RES-00032", "CTR-0012", "29/02/0000", "''", "0"),
    ("RES-00033", "CTR-0013", "0004-02-29", "Bissextile de Date.UTC", "1"),
]


def fichier_fabrique(entete, lignes):
    """Octets d'un CSV écrit comme Prévo l'écrit, depuis des lignes {colonne: cellule} (cellule absente : '')."""
    return serveur.ecrire_tableau_csv(entete, [[ligne.get(nom, "") for nom in entete] for ligne in lignes])


def reserves_attendues(controles):
    """Réserves que la reprise tire de lignes de contrôles CANONIQUES (cellules d'un jeu d'essai : dates AAAA-MM-JJ ou
    vides, booléens 0/1), sans réserve existante : recopie de la règle de la note de conception du format 4 (§3.2),
    indépendante de reserves_reprises (seules relire_valeur_texte et ecrire_valeur_texte, comparées au navigateur, sont
    prises au serveur). Une valeur non canonique fait échouer le test (elle relève des cas fabriqués)."""
    reserves = []
    for controle in controles:
        identifiant = controle.get("id", "").strip()
        observations = serveur.relire_valeur_texte(controle.get("observations", ""))
        if identifiant == "" or observations.strip() == "":
            continue
        date = controle.get("derniere_date", "").strip()
        levee = controle.get("observations_levees", "").strip()
        assert date == "" or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", date), date
        assert levee in ("", "0", "1"), levee
        for morceau in re.split(r"\r\n|\r|\n", observations):
            if morceau.strip() != "":
                reserves.append(reserve_complete("RES-%05d" % (len(reserves) + 1), identifiant, date,
                                                 serveur.ecrire_valeur_texte(morceau.strip()),
                                                 "1" if levee == "1" else "0"))
    return reserves


def tables_ajoutees_apres(format):
    """Tables que les formats suivants (jusqu'au format courant) ajoutent."""
    return [table for f in range(format + 1, FORMAT_COURANT + 1) for table in TABLES_AJOUTEES[f]]


def colonnes_attendues(table, format):
    """Colonnes de la table dans ce format, d'après COLONNES_AJOUTEES et COLONNES_PAR_TABLE (format courant)."""
    if any(table in TABLES_AJOUTEES[f] for f in range(format + 1, FORMAT_COURANT + 1)):
        return []
    retirees = {c for f in range(format + 1, FORMAT_COURANT + 1) for c in COLONNES_AJOUTEES[f].get(table, [])}
    return [c for c in serveur.COLONNES_PAR_TABLE[table] if c not in retirees]


def format_attendu(table, format_des_fichiers):
    """Plus grand format N dont l'en-tête est celui d'un fichier écrit au format donné (N avance tant que le format
    suivant n'ajoute rien à la table)."""
    attendu = min(format_des_fichiers, FORMAT_COURANT)
    for format in range(attendu + 1, FORMAT_COURANT + 1):
        if table in COLONNES_AJOUTEES.get(format, {}) or table in TABLES_AJOUTEES.get(format, []):
            break
        attendu = format
    return attendu


def fichiers_du_jeu(jeu, dossier):
    """{table: octets} des CSV du jeu (copié dans « dossier », jamais lu en place)."""
    copie = copier_jeu(jeu, Path(dossier) / jeu)
    return {chemin.stem: chemin.read_bytes() for chemin in sorted(copie.glob("*.csv"))}


def table_de_base(octets):
    """Table de la base du serveur lue par lire_csv_tolerant : cellule manquante → '', cellule au-delà de l'en-tête
    ignorée (comme Donnees.csv.analyser)."""
    entete, lignes = serveur.lire_csv_tolerant(octets)
    if len(set(entete)) != len(entete):
        raise AssertionError("nom de colonne en double dans un jeu : %r" % (entete,))
    return {"entete": list(entete),
            "lignes": [{nom: (ligne[i] if i < len(ligne) else "") for i, nom in enumerate(entete)} for ligne in lignes]}


def base_de_fichiers(fichiers):
    return {table: table_de_base(octets) for table, octets in fichiers.items()}


def octets_de_table(contenu):
    return serveur.ecrire_tableau_csv(contenu["entete"], [[ligne.get(nom, "") for nom in contenu["entete"]]
                                                          for ligne in contenu["lignes"]])


def lignes_de_parametres(base):
    return base["parametres"]["lignes"] if "parametres" in base else []


def chemin_serveur(fichiers):
    """Lecture (lire_csv_tolerant) + migrer_tables + écriture (ecrire_tableau_csv), comme le fera le serveur."""
    base = base_de_fichiers(fichiers)
    de = serveur.version_de_base(lignes_de_parametres(base))
    migree, journal, etapes = serveur.migrer_tables(base, de, FORMAT_COURANT)
    return {"formats": {table: serveur.format_du_fichier(table, contenu["entete"]) for table, contenu in base.items()},
            "de": de, "journal": journal, "etapes": [[e["de"], e["vers"]] for e in etapes],
            "entetes": {table: contenu["entete"] for table, contenu in migree.items()},
            "octets": {table: octets_de_table(contenu) for table, contenu in migree.items()}}


def ecarts_de_cellules(avant, apres):
    """Cellules d'origine perdues ou modifiées (sauf la valeur de parametres.version_schema, que l'étape pose)."""
    ecarts = []
    for table, contenu in avant.items():
        if table not in apres:
            ecarts.append("%s : table perdue" % table)
            continue
        lignes_apres = apres[table]["lignes"]
        if len(lignes_apres) < len(contenu["lignes"]):
            ecarts.append("%s : %d lignes au lieu de %d" % (table, len(lignes_apres), len(contenu["lignes"])))
        for numero, (ligne, ligne_apres) in enumerate(zip(contenu["lignes"], lignes_apres), start=1):
            for colonne, valeur in ligne.items():
                if table == "parametres" and colonne == "valeur" and ligne.get("cle") == "version_schema":
                    continue
                if colonne not in ligne_apres or ligne_apres[colonne] != valeur:
                    ecarts.append("%s ligne %d, %s : %r devenu %r" % (table, numero, colonne, valeur,
                                                                      ligne_apres.get(colonne)))
    return ecarts


class JeuxEnCopie:
    """Copie chaque jeu une fois par classe, dans un dossier temporaire supprimé à la fin."""

    @classmethod
    def copier_les_jeux(cls):
        dossier = tempfile.mkdtemp(prefix="prevo-formats-serveur-")
        cls.addClassCleanup(shutil.rmtree, dossier, True)
        cls.fichiers = {jeu: fichiers_du_jeu(jeu, dossier) for jeu in JEUX}


# ---------------------------------------------------------------------------------------------------------------
# 1. Python seul
# ---------------------------------------------------------------------------------------------------------------

class TestRegistreServeur(JeuxEnCopie, unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.copier_les_jeux()

    def base(self, jeu):
        return base_de_fichiers(self.fichiers[jeu])

    # -- Colonnes et tables de chaque format ------------------------------------------------------------------

    def test_colonnes_et_tables_de_chaque_format(self):
        self.assertEqual(serveur.VERSION_SCHEMA_CSV, FORMAT_COURANT)
        tables_du_brief = [t for t in serveur.TABLES if t not in tables_ajoutees_apres(1)]
        self.assertEqual(len(tables_du_brief), 22)
        self.assertEqual(len(serveur.TABLES), NB_TABLES)
        self.assertEqual(len(serveur.TABLES), 22 + len(tables_ajoutees_apres(1)))          # 27 au format 4
        self.assertEqual(serveur.tables_du_format(1), tables_du_brief)
        self.assertEqual(serveur.tables_du_format(2), tables_du_brief)
        self.assertEqual(serveur.tables_du_format(3), tables_du_brief + TABLES_AJOUTEES[3])
        self.assertEqual(serveur.tables_du_format(4), list(serveur.TABLES))
        self.assertEqual(serveur.tables_du_format(), list(serveur.TABLES))
        for table in serveur.TABLES:
            with self.subTest(table=table):
                for format in range(1, FORMAT_COURANT + 1):
                    self.assertEqual(serveur.colonnes_du_format(table, format), colonnes_attendues(table, format))
                self.assertEqual(serveur.colonnes_du_format(table), list(serveur.COLONNES_PAR_TABLE[table]))
        self.assertEqual(serveur.colonnes_du_format("pieces_v5", 3), [])
        self.assertEqual(serveur.colonnes_du_format("wiki_pages", 2), [])
        self.assertEqual(serveur.colonnes_du_format("reserves_controle", 3), [])
        self.assertEqual(serveur.colonnes_du_format("controles_reglementaires", 3)[-1], "observations_levees")
        self.assertEqual(serveur.colonnes_du_format(None), [])
        self.assertEqual(serveur.colonnes_du_format(["equipements"]), [])

    def test_listes_ajoutees_coherentes_avec_le_serveur(self):
        # Les colonnes des formats suivants sont celles de COLONNES_DES_FORMATS_SUIVANTS (« Tester une sauvegarde »),
        # dans le même ordre, en fin de COLONNES_PAR_TABLE, et leur format est croissant dans la table.
        self.assertEqual({t: tuple(c) for t, c in serveur.PREMIER_FORMAT_DES_COLONNES.items()},
                         serveur.COLONNES_DES_FORMATS_SUIVANTS)
        for table, formats in serveur.PREMIER_FORMAT_DES_COLONNES.items():
            with self.subTest(table=table):
                self.assertEqual(list(serveur.COLONNES_PAR_TABLE[table][-len(formats):]), list(formats))
                self.assertEqual(list(formats.values()), sorted(formats.values()))
                self.assertTrue(all(1 < f <= FORMAT_COURANT for f in formats.values()))
        # Même registre que la recopie de ce test : format de chaque colonne et de chaque table ajoutée
        self.assertEqual(serveur.PREMIER_FORMAT_DES_COLONNES,
                         {t: {c: f for f, tables in sorted(COLONNES_AJOUTEES.items()) for c in tables.get(t, [])}
                          for t in sorted({t for tables in COLONNES_AJOUTEES.values() for t in tables})})
        self.assertEqual(serveur.PREMIER_FORMAT_DES_TABLES,
                         {t: f for f, tables in TABLES_AJOUTEES.items() for t in tables})
        self.assertEqual(list(serveur.TABLES[-5:]), TABLES_AJOUTEES[3] + TABLES_AJOUTEES[4])  # après wiki_journal
        for table, defauts in serveur.DEFAUTS_DES_CHAMPS.items():
            with self.subTest(table=table):
                self.assertTrue(set(defauts) <= set(serveur.COLONNES_PAR_TABLE[table]))
                self.assertTrue(all(isinstance(v, str) for v in defauts.values()))
        self.assertEqual({c: serveur.DEFAUTS_DES_CHAMPS.get(t, {}).get(c, "")
                          for f in COLONNES_AJOUTEES.values() for t, cs in f.items() for c in cs}, DEFAUTS_AJOUTES)
        for table, defauts in DEFAUTS_DES_TABLES_AJOUTEES.items():
            self.assertEqual(serveur.DEFAUTS_DES_CHAMPS[table], defauts, table)
        # Motif de la sauvegarde faite juste avant le passage au format courant (CONCEPTION-L1 §2.3)
        self.assertEqual([m for m in serveur.MOTIFS_SAUVEGARDE if m.startswith("avant-format-v")],
                         ["avant-format-v%d" % f for f in range(2, FORMAT_COURANT + 1)])

    def test_jeux_tous_classes_pour_la_concordance(self):
        self.assertEqual(set(JEUX), set(JEUX_CONCORDANTS) | set(ECARTS_DOCUMENTES) | set(JEUX_ABIMES))

    # -- cle_de_colonne et format_du_fichier --------------------------------------------------------------------

    def test_cle_de_colonne(self):
        cas = {
            "date_creation": "datecreation", " Date Création ": "datecreation", CARACTERE_BOM + "id": "id",
            "TITRE": "titre", "ti tre": "titre", "Tîtré": "titre", INSECABLE + "titre" + INSECABLE_FINE: "titre",
            CADRATIN + "ti" + IDEOGRAPHIQUE + "tre\t\r\n": "titre", "ti" + ESPACE_NULLE + "tre": "ti" + ESPACE_NULLE + "tre",
            "titre" + LIGNE_SUIVANTE: "titre" + LIGNE_SUIVANTE, None: "", 42: "42", "": "",
        }
        for nom, cle in cas.items():
            with self.subTest(nom=nom):
                self.assertEqual(serveur.cle_de_colonne(nom), cle)

    def test_format_de_chaque_fichier_de_chaque_jeu(self):
        vus = set()
        for jeu in JEUX:
            for table, contenu in sorted(self.base(jeu).items()):
                with self.subTest(jeu=jeu, table=table):
                    if (jeu, table) in FORMATS_PARTICULIERS:
                        attendu = FORMATS_PARTICULIERS[(jeu, table)]
                        vus.add((jeu, table))
                    else:
                        attendu = format_attendu(table, FORMAT_DES_FICHIERS.get(jeu, FORMAT_DES_JEUX))
                    self.assertEqual(serveur.format_du_fichier(table, contenu["entete"]), attendu)
        self.assertEqual(vus, set(FORMATS_PARTICULIERS), "cas particuliers absents des jeux")
        # Jeux de la 2.1.0 : les quatre tables que le format 4 complète sont au format 3 (colonne inconnue en fin de
        # controles_reglementaires comprise) ; une table que le format 4 n'a pas changée est au format 4
        for jeu in ("f3-v2.1.0", "reserves-a-reprendre"):
            base = self.base(jeu)
            for table in COLONNES_AJOUTEES[4]:
                self.assertEqual(serveur.format_du_fichier(table, base[table]["entete"]), 3, (jeu, table))
            self.assertEqual(serveur.format_du_fichier("fournisseurs", base["fournisseurs"]["entete"]), 4)

    def test_format_du_fichier_en_tetes_fabriques_sans_exception(self):
        ot = lambda format: serveur.colonnes_du_format("ordres_travail", format)  # noqa: E731

        class Etrange:
            def __str__(self):
                raise ValueError("illisible")

        self.assertEqual([serveur.format_du_fichier("ordres_travail", ot(f)) for f in (1, 2, 3, 4)], [1, 2, 3, 4])
        self.assertEqual(serveur.format_du_fichier("ordres_travail", list(reversed(ot(4)))), 4)
        self.assertEqual(serveur.format_du_fichier("ordres_travail", tuple(ot(4))), 4)
        self.assertEqual(serveur.format_du_fichier(
            "ordres_travail", [CARACTERE_BOM + "id"] + ["  %s \t" % n for n in ot(4)[1:]]), 4)
        self.assertEqual(serveur.format_du_fichier("ordres_travail", ["avant"] + ot(2) + ["apres", "astuce"]), 3)
        self.assertEqual(serveur.format_du_fichier(
            "ordres_travail", ["avant"] + ot(3) + ["apres", "habilitation_requise"]), 4)
        self.assertEqual(serveur.format_du_fichier("ordres_travail", [n for n in ot(4) if n != "titre"]), 0)
        self.assertEqual(serveur.format_du_fichier("parametres", ["Cle", "Valeur"]), FORMAT_COURANT)
        self.assertEqual(serveur.format_du_fichier(
            "ordres_travail", ["Date Création" if n == "date_creation" else n for n in ot(4)]), 4)
        # wiki_pages n'a pas changé depuis le format 3 : son en-tête est aussi celui du format 4
        self.assertEqual(serveur.format_du_fichier("wiki_pages", serveur.colonnes_du_format("wiki_pages", 3)),
                         FORMAT_COURANT)
        self.assertEqual(serveur.format_du_fichier("wiki_pages", serveur.colonnes_du_format("wiki_pages", 3)[1:]), 0)
        self.assertEqual(serveur.format_du_fichier("wiki_journal", []), 0)
        controles = serveur.colonnes_du_format("controles_reglementaires", 4)
        self.assertEqual(serveur.format_du_fichier(
            "controles_reglementaires", [n for n in controles if n != "catalogue_relu_le"]), 3)
        reserves = serveur.colonnes_du_format("reserves_controle")
        self.assertEqual(serveur.format_du_fichier("reserves_controle", reserves), 4)
        self.assertEqual(serveur.format_du_fichier("reserves_controle", reserves[:-1]), 0)
        self.assertEqual(serveur.format_du_fichier("garanties", []), 0)
        self.assertEqual(serveur.format_du_fichier(
            "contrats_prestataires", serveur.colonnes_du_format("contrats_prestataires", 4)), 4)
        self.assertIsNone(serveur.format_du_fichier("pieces_v5", ["id"]))
        self.assertIsNone(serveur.format_du_fichier(None, ["id"]))
        self.assertIsNone(serveur.format_du_fichier(["ordres_travail"], ["id"]))
        etranges = [None, "id;origine", 42, {}, [None, None, 3, {}], [Etrange()], ot(3) + [Etrange()]]
        self.assertEqual([serveur.format_du_fichier("ordres_travail", e) for e in etranges], [0] * len(etranges))

    # -- version_de_base ----------------------------------------------------------------------------------------

    def test_version_de_base_de_chaque_jeu(self):
        for jeu in JEUX:
            with self.subTest(jeu=jeu):
                self.assertEqual(serveur.version_de_base(lignes_de_parametres(self.base(jeu))),
                                 VERSION_DE_BASE.get(jeu, FORMAT_DES_JEUX))

    def test_version_de_base_regle(self):
        def version(valeur, cle="version_schema"):
            return serveur.version_de_base([{"cle": "delai_p1_h", "valeur": "'9"}, {"cle": cle, "valeur": valeur}])

        # Cellules du fichier : l'apostrophe de protection est retirée comme Donnees.csv.relireValeur le fait
        cas = {"3": 3, "'3": 3, "'2": 2, " 2 ": 2, "'2,0": 2, "2.0": 2, "'2,5": 2.5, "+3": 3, "'+3": 3, "'-1": -1,
               "''3": 1, "'3 000": 1, "3 000": 3000, "'1e3": 1, "abc": 1, "'abc": 1, "": 1, "'": 1, "v3": 1,
               INSECABLE + "3" + INSECABLE_FINE: 3, "'3" + CADRATIN: 1, None: 1}
        for valeur, attendu in cas.items():
            with self.subTest(valeur=valeur):
                self.assertEqual(version(valeur), attendu)
                self.assertIs(type(version(valeur)), type(attendu))
        self.assertEqual(version("'2", cle="  version_schema\t"), 2)          # clé lue comme un identifiant
        self.assertEqual(version("'2", cle="'version_schema"), 1)
        self.assertEqual(serveur.version_de_base([{"Clé": "version_schema", " Valeur ": "'2"}]), 2)
        self.assertEqual(serveur.version_de_base([{"cle": "entreprise_nom", "valeur": "3"}]), 1)
        self.assertEqual(serveur.version_de_base([]), 1)
        for pas_une_liste in (None, "version_schema;3", {}, 3):
            self.assertEqual(serveur.version_de_base(pas_une_liste), 1)
        self.assertEqual(serveur.version_de_base([{"cle": "version_schema", "valeur": "'2"},
                                                  {"cle": "version_schema", "valeur": "'3"}]), 2)
        self.assertEqual(serveur.version_de_base([None, 3, {"cle": "version_schema", "valeur": "'2"}]), 2)
        self.assertEqual(serveur.version_de_base([{"cle": "version_schema"}]), 1)

    def test_relire_et_ecrire_une_valeur_texte(self):
        valeurs = ["", "3", "'3", "''3", "abc", "'abc", "=1+1", "-5", "@x", "\tx", "12/03", "08:30", "15 %", "1,5E+3",
                   " 3 ", "x'", "'", "3 000", "007", "2026-11-04"]
        for valeur in valeurs:
            with self.subTest(valeur=valeur):
                self.assertEqual(serveur.relire_valeur_texte(serveur.ecrire_valeur_texte(valeur)), valeur)
        self.assertEqual(serveur.ecrire_valeur_texte("3"), "'3")
        self.assertEqual(serveur.ecrire_valeur_texte("abc"), "abc")
        self.assertEqual(serveur.relire_valeur_texte("'abc"), "'abc")
        self.assertEqual(serveur.relire_valeur_texte(None), "")

    # -- migrer_tables sur chaque jeu ---------------------------------------------------------------------------

    def test_migration_de_chaque_jeu_sans_perte(self):
        for jeu in JEUX:
            with self.subTest(jeu=jeu):
                base = self.base(jeu)
                avant = copy.deepcopy(base)
                de = serveur.version_de_base(lignes_de_parametres(base))
                apres, journal, etapes = serveur.migrer_tables(base, de, FORMAT_COURANT)
                self.assertEqual(base, avant, "migrer_tables a modifié la base reçue")
                self.assertEqual(journal, LIGNES_DE_JOURNAL.get(de, []))
                self.assertEqual([(e["de"], e["vers"]) for e in etapes],
                                 [(n - 1, n) for n in range(de + 1, FORMAT_COURANT + 1)])
                self.assertEqual(ecarts_de_cellules(avant, apres), [])
                if de >= FORMAT_COURANT:
                    self.assertIs(apres, base)          # déjà au format courant (ou plus récent) : rien ne change
                    continue
                # Colonnes d'origine à leur place (inconnues comprises), colonnes nouvelles en fin, après elles, avec
                # leur défaut (comme tests/test_formats_js.py) ; une colonne du schéma absente d'un fichier abîmé ou
                # en retard sur sa base (melange, colonnes-manquantes) est complétée de même
                for table, contenu in apres.items():
                    with self.subTest(jeu=jeu, table=table):
                        self.assertEqual(serveur.format_du_fichier(table, contenu["entete"]), FORMAT_COURANT)
                        if table not in avant:
                            # Table créée : vide, sauf reserves_controle, qui reçoit les observations reprises (D183)
                            controles = avant.get("controles_reglementaires", {"lignes": []})["lignes"]
                            lignes = reserves_attendues(controles) if table == "reserves_controle" else []
                            self.assertEqual(contenu, {"entete": list(serveur.COLONNES_PAR_TABLE[table]),
                                                       "lignes": lignes})
                            continue
                        entete_avant = avant[table]["entete"]
                        nouvelles = [c for c in serveur.COLONNES_PAR_TABLE[table] if c not in entete_avant]
                        self.assertEqual(contenu["entete"], entete_avant + nouvelles)     # nouvelles en fin
                        defauts = serveur.DEFAUTS_DES_CHAMPS.get(table, {})
                        for ligne in contenu["lignes"]:
                            self.assertEqual({c: ligne[c] for c in nouvelles}, {c: defauts.get(c, "") for c in nouvelles})
                        ajoutees = [c for f in range(de + 1, FORMAT_COURANT + 1)
                                    for c in COLONNES_AJOUTEES[f].get(table, [])]
                        self.assertEqual(nouvelles[len(nouvelles) - len(ajoutees):], ajoutees)
                self.assertEqual(sorted(apres), sorted(serveur.TABLES))
                # Chaque jeu tiré de la démo a un contrôle à observations (CTR-0004) : une réserve au moins ; f1 n'a
                # pas de contrôles
                self.assertEqual(len(apres["reserves_controle"]["lignes"]) > 0, "controles_reglementaires" in avant)
                # Les tables des formats suivants sont créées (vides, sauf la reprise) ; celles du jeu sont gardées
                for table in tables_ajoutees_apres(de):
                    self.assertNotIn(table, avant)
                    if table != "reserves_controle":
                        self.assertEqual(apres[table]["lignes"], [], table)
                # version_schema écrite comme Prévo l'écrit, relue 4
                self.assertEqual([l["valeur"] for l in apres["parametres"]["lignes"] if l["cle"] == "version_schema"],
                                 ["'%d" % FORMAT_COURANT])
                self.assertEqual(serveur.version_de_base(apres["parametres"]["lignes"]), FORMAT_COURANT)
                # Rejouée d'après la version relue : rien ne change ; depuis le format d'origine : même base
                rejouee = serveur.migrer_tables(apres, serveur.version_de_base(apres["parametres"]["lignes"]),
                                                FORMAT_COURANT)
                self.assertIs(rejouee[0], apres)
                self.assertEqual(rejouee[1:], ([], []))
                depuis_origine = serveur.migrer_tables(apres, de, FORMAT_COURANT)
                self.assertEqual(depuis_origine[0], apres)
                self.assertEqual(depuis_origine[1], journal)

    def test_migration_f1_et_f2_detail(self):
        avant = self.base("f1")
        apres, journal, _ = serveur.migrer_tables(avant, 1, FORMAT_COURANT)
        self.assertEqual(sorted(avant), ["demandes", "equipements", "ordres_travail", "parametres"])
        self.assertEqual(len(apres), NB_TABLES)
        self.assertEqual(journal, LIGNES_DE_JOURNAL[1])
        self.assertEqual(apres["ordres_travail"]["entete"][-3:], ["anomalie_constatee", "astuce", "habilitation_requise"])
        self.assertEqual(apres["demandes"]["entete"][-2:], ["symptome_code", "ot_origine_id"])
        self.assertEqual(apres["equipements"]["entete"][-2:], ["valeur_remplacement", "cout_arret_h"])
        self.assertTrue(all(l["anomalie_constatee"] == "0" and l["astuce"] == "" and l["habilitation_requise"] == ""
                            for l in apres["ordres_travail"]["lignes"]))
        self.assertEqual(len(apres["ordres_travail"]["lignes"]), 12)
        # parametres.csv de f1 porte version_schema;'1 (dernière ligne) : la cellule devient '4, rien d'autre ne change
        self.assertEqual(avant["parametres"]["lignes"][-1], {"cle": "version_schema", "valeur": "'1"})
        self.assertEqual(apres["parametres"]["lignes"][:-1], avant["parametres"]["lignes"][:-1])
        self.assertEqual(apres["parametres"]["lignes"][-1], {"cle": "version_schema", "valeur": "'4"})
        sans_version = {"parametres": {"entete": avant["parametres"]["entete"],
                                       "lignes": avant["parametres"]["lignes"][:-1]}}
        self.assertEqual(serveur.version_de_base(sans_version["parametres"]["lignes"]), 1)
        ajoutee = serveur.migrer_tables(sans_version, 1, FORMAT_COURANT)[0]["parametres"]["lignes"]
        self.assertEqual(ajoutee, avant["parametres"]["lignes"][:-1] + [{"cle": "version_schema", "valeur": "'4"}])
        avant2 = self.base("f2-v1.1.0")
        apres2, journal2, _ = serveur.migrer_tables(avant2, 2, FORMAT_COURANT)
        self.assertEqual(journal2, LIGNES_DE_JOURNAL[2])
        self.assertEqual(len(avant2), 22)
        self.assertEqual(sorted(set(apres2) - set(avant2)), sorted(tables_ajoutees_apres(2)))
        self.assertEqual(apres2["ordres_travail"]["entete"],
                         avant2["ordres_travail"]["entete"] + ["astuce", "habilitation_requise"])
        for table in avant2:
            self.assertEqual(apres2[table]["entete"],
                             avant2[table]["entete"] + COLONNES_AJOUTEES[3].get(table, [])
                             + COLONNES_AJOUTEES[4].get(table, []), table)
        self.assertEqual(len(apres2["parametres"]["lignes"]), len(avant2["parametres"]["lignes"]))

    def test_migration_f3_au_format_4_detail(self):
        """Bases 2.1.0 (f3-v2.1.0 et sa variante reserves-a-reprendre) : une étape, 3→4 ; seules equipements,
        ordres_travail, habilitations et controles_reglementaires changent (colonnes en fin, source_periodicite =
        saisie, les autres vides), parametres (version_schema « '4 ») ; les trois tables du format 4 sont créées,
        garanties et contrats_prestataires vides, reserves_controle avec les réserves reprises du LISEZMOI des jeux
        (D183, CS170) ; la colonne inconnue remarque_maison reste à sa place, AVANT les colonnes du format 4 (règle de
        2→3, la même que tests/test_formats_js.py)."""
        for jeu in ("f3-v2.1.0", "reserves-a-reprendre"):
            with self.subTest(jeu=jeu):
                avant = self.base(jeu)
                apres, journal, etapes = serveur.migrer_tables(avant, 3, FORMAT_COURANT)
                self.assertEqual(journal, ["passage au format 4 du fichier"])
                self.assertEqual(etapes, [{"de": 3, "vers": 4, "description": DESCRIPTION_FORMAT_4}])
                self.assertEqual(sorted(set(apres) - set(avant)), sorted(TABLES_AJOUTEES[4]))
                for table in TABLES_AJOUTEES[4]:
                    lignes = ([reserve_complete(*reserve) for reserve in RESERVES_DU_LISEZMOI[jeu]]
                              if table == "reserves_controle" else [])
                    self.assertEqual(apres[table], {"entete": list(serveur.COLONNES_PAR_TABLE[table]),
                                                    "lignes": lignes})
                for table in avant:
                    if table == "parametres" or table in COLONNES_AJOUTEES[4]:
                        continue
                    self.assertEqual(apres[table], avant[table], "%s : réécrite sans colonne nouvelle" % table)
                    self.assertEqual(octets_de_table(apres[table]), self.fichiers[jeu][table], table)
                for table, ajoutees in COLONNES_AJOUTEES[4].items():
                    self.assertEqual(apres[table]["entete"], avant[table]["entete"] + ajoutees, table)
                    self.assertTrue(avant[table]["lignes"], "%s : aucune ligne dans le jeu" % table)
                    self.assertEqual(len(apres[table]["lignes"]), len(avant[table]["lignes"]))
                    for ligne_avant, ligne in zip(avant[table]["lignes"], apres[table]["lignes"]):
                        self.assertEqual(ligne, dict(ligne_avant, **{c: DEFAUTS_AJOUTES[c] for c in ajoutees}))
                self.assertEqual([l for l in apres["parametres"]["lignes"] if l["cle"] != "version_schema"],
                                 [l for l in avant["parametres"]["lignes"] if l["cle"] != "version_schema"])
                self.assertEqual([l["valeur"] for l in apres["parametres"]["lignes"] if l["cle"] == "version_schema"],
                                 ["'4"])
        avant = self.base("reserves-a-reprendre")
        controles = serveur.migrer_tables(avant, 3, FORMAT_COURANT)[0]["controles_reglementaires"]
        self.assertEqual(controles["entete"][-6:], ["observations_levees", "remarque_maison"]
                         + COLONNES_AJOUTEES[4]["controles_reglementaires"])
        self.assertEqual([l["remarque_maison"] for l in controles["lignes"]],
                         [l["remarque_maison"] for l in avant["controles_reglementaires"]["lignes"]])
        self.assertEqual({l["source_periodicite"] for l in controles["lignes"]}, {"saisie"})
        # Observations et observations_levees inchangées (CS169) : cellules du fichier gardées telles quelles
        self.assertEqual([(l["observations"], l["observations_levees"]) for l in controles["lignes"]],
                         [(l["observations"], l["observations_levees"])
                          for l in avant["controles_reglementaires"]["lignes"]])

    def test_plus_recent_laisse_intact(self):
        fichiers = self.fichiers["plus-recent"]
        base = base_de_fichiers(fichiers)
        avant = copy.deepcopy(base)
        de = serveur.version_de_base(base["parametres"]["lignes"])
        self.assertEqual(de, 5)
        resultat, journal, etapes = serveur.migrer_tables(base, de, FORMAT_COURANT)
        self.assertIs(resultat, base)
        self.assertEqual((journal, etapes), ([], []))
        self.assertEqual(base, avant)
        self.assertEqual(base["ordres_travail"]["entete"][-1], "nouvelle_colonne_v5")
        self.assertIsNone(serveur.format_du_fichier("pieces_v5", base["pieces_v5"]["entete"]))
        # Réécrit tel quel, chaque fichier redonne ses octets (table inconnue et colonne inconnue comprises)
        for table, octets in fichiers.items():
            with self.subTest(table=table):
                self.assertEqual(octets_de_table(resultat[table]), octets)

    # -- ETAPES_FORMAT ------------------------------------------------------------------------------------------

    def test_etapes_chaine_sans_trou_et_descriptions(self):
        self.assertEqual([(e.de, e.vers) for e in serveur.ETAPES_FORMAT], [(1, 2), (2, 3), (3, 4)])
        self.assertEqual(serveur.ETAPES_FORMAT[-1].vers, serveur.VERSION_SCHEMA_CSV)
        self.assertEqual(serveur.ETAPES_FORMAT[2].description, DESCRIPTION_FORMAT_4)
        for etape in serveur.ETAPES_FORMAT:
            with self.subTest(etape=etape.vers):
                for table, colonnes in COLONNES_AJOUTEES[etape.vers].items():
                    for colonne in colonnes:
                        self.assertIn("%s.%s" % (table, colonne), etape.description)
                for table in TABLES_AJOUTEES[etape.vers]:
                    self.assertIn(table, etape.description)
                with self.assertRaises(AttributeError):
                    etape.autre = 1                         # __slots__ : pas d'attribut ajouté par mégarde

    def test_appliquer_pure_et_idempotente_sur_chaque_jeu(self):
        for jeu in JEUX:
            base = self.base(jeu)
            avant = copy.deepcopy(base)
            for etape in serveur.ETAPES_FORMAT:
                with self.subTest(jeu=jeu, etape=etape.vers):
                    une = etape.appliquer(base)
                    self.assertEqual(base, avant, "entrée modifiée")
                    self.assertIsNot(une, base)
                    for table, contenu in base.items():         # rien de partagé avec l'entrée
                        self.assertIsNot(une[table], contenu)
                        self.assertIsNot(une[table]["entete"], contenu["entete"])
                        self.assertFalse(any(a is b for a, b in zip(une[table]["lignes"], contenu["lignes"])))
                    self.assertEqual(etape.appliquer(une), une, "pas idempotente")
                    versions = [l["valeur"] for l in une["parametres"]["lignes"] if l["cle"] == "version_schema"]
                    self.assertEqual(versions[:1], ["'%d" % etape.vers])

    def test_appliquer_cas_fabriques(self):
        base = {
            "equipements": {"entete": ["id", "colonne_maison", "designation", "actif"], "lignes": [
                {"id": "EQ-0001", "colonne_maison": "m1", "designation": "Presse", "actif": "0"},
                {"id": "EQ-0002", "colonne_maison": "", "designation": "Tour", "actif": "1",
                 "valeur_remplacement": "1200"},
            ]},
            "ordres_travail": {"entete": [CARACTERE_BOM + "id", " titre "],
                               "lignes": [{CARACTERE_BOM + "id": "OT-1", " titre ": "T"}]},
            "demandes": {"entete": [" %s " % n for n in serveur.colonnes_du_format("demandes", 3)], "lignes": []},
            "pieces_v5": {"entete": ["id", "stock"], "lignes": [{"id": "P-1", "stock": "3"}], "note": "table inconnue"},
        }
        avant = copy.deepcopy(base)
        deux = serveur.ETAPES_FORMAT[0].appliquer(base)
        trois = serveur.ETAPES_FORMAT[1].appliquer(deux)
        self.assertEqual(base, avant)
        equipements = deux["equipements"]
        self.assertEqual(equipements["entete"][:4], ["id", "colonne_maison", "designation", "actif"])
        self.assertEqual(equipements["entete"][-1], "valeur_remplacement")
        self.assertIn("repere", equipements["entete"][4:])
        self.assertEqual(equipements["lignes"][0]["colonne_maison"], "m1")
        self.assertEqual(equipements["lignes"][0]["actif"], "0")            # valeur gardée, pas le défaut '1'
        self.assertEqual(equipements["lignes"][0]["criticite"], "B")         # défaut du schéma
        self.assertEqual(equipements["lignes"][0]["statut"], "en service")
        self.assertEqual(equipements["lignes"][0]["valeur_remplacement"], "")
        self.assertEqual(equipements["lignes"][1]["valeur_remplacement"], "1200")   # déjà là : jamais écrasée
        ordres = deux["ordres_travail"]
        self.assertEqual(ordres["entete"][:2], [CARACTERE_BOM + "id", " titre "])
        self.assertNotIn("id", ordres["entete"])
        self.assertNotIn("titre", ordres["entete"])
        self.assertEqual(len(ordres["entete"]), len(serveur.colonnes_du_format("ordres_travail", 2)))
        self.assertEqual(ordres["lignes"][0]["statut"], "Créé")
        self.assertEqual(deux["demandes"]["entete"], [" %s " % n for n in serveur.colonnes_du_format("demandes", 3)])
        self.assertEqual(deux["pieces_v5"], avant["pieces_v5"])
        self.assertEqual(deux["parametres"], {"entete": ["cle", "valeur"],
                                              "lignes": [{"cle": "version_schema", "valeur": "'2"}]})
        self.assertNotIn("wiki_pages", deux)
        self.assertEqual(trois["parametres"]["lignes"], [{"cle": "version_schema", "valeur": "'3"}])
        self.assertEqual(trois["ordres_travail"]["entete"][-1], "astuce")
        self.assertEqual(trois["wiki_journal"], {"entete": list(serveur.COLONNES_PAR_TABLE["wiki_journal"]),
                                                 "lignes": []})
        avec_parametres = serveur.ETAPES_FORMAT[1].appliquer({"parametres": {"entete": ["cle", "valeur", "note"],
            "lignes": [{"cle": "entreprise_nom", "valeur": "A", "note": "n"}]}})
        self.assertEqual(avec_parametres["parametres"]["lignes"], [
            {"cle": "entreprise_nom", "valeur": "A", "note": "n"}, {"cle": "version_schema", "valeur": "'3", "note": ""}])
        # Clé en double : la première ligne porte la version ; noms de colonnes « à la main » reconnus
        plus_recente = serveur.ETAPES_FORMAT[1].appliquer({"parametres": {"entete": ["cle", "valeur"],
            "lignes": [{"cle": "version_schema", "valeur": "'3"}, {"cle": "version_schema", "valeur": "'9"}]}})
        self.assertEqual(plus_recente["parametres"]["lignes"], [{"cle": "version_schema", "valeur": "'3"},
                                                                {"cle": "version_schema", "valeur": "'9"}])
        a_la_main = serveur.ETAPES_FORMAT[1].appliquer({"parametres": {"entete": ["Clé", " Valeur"],
            "lignes": [{"Clé": " version_schema ", " Valeur": "'2"}]}})
        self.assertEqual(a_la_main["parametres"], {"entete": ["Clé", " Valeur"],
                                                   "lignes": [{"Clé": " version_schema ", " Valeur": "'3"}]})
        self.assertEqual(len(serveur.ETAPES_FORMAT[0].appliquer(None)), 22)
        self.assertEqual(len(serveur.ETAPES_FORMAT[1].appliquer("pas une base")), 24)
        self.assertEqual(serveur.ETAPES_FORMAT[0].appliquer({"equipements": None, "parametres": {"lignes": [None]}})[
            "parametres"]["lignes"], [{"cle": "", "valeur": ""}, {"cle": "version_schema", "valeur": "'2"}])

    def test_etape_3_4_cas_fabriques(self):
        """Étape 3→4 générique (miroir de tests/test_formats_js.py) : colonnes du format 4 en fin d'en-tête, après les
        colonnes inconnues (à leur place), défaut saisie ; valeur déjà là jamais écrasée ; table du format 4 déjà là
        gardée telle quelle (lignes comprises) ; tables absentes créées vides ; colonnes avec BOM ou espaces
        reconnues ; pure et idempotente."""
        colonnes3 = serveur.colonnes_du_format("controles_reglementaires", 3)
        base = {
            "controles_reglementaires": {"entete": colonnes3 + ["remarque_maison"], "lignes": [
                dict({c: "" for c in colonnes3}, id="CTR-0001", remarque_maison="r"),
                dict({c: "" for c in colonnes3}, id="CTR-0002", remarque_maison="", source_periodicite="catalogue"),
            ]},
            "habilitations": {"entete": ["id", "note", "intitule", " Recyclage Mois "], "lignes": [
                {"id": "HAB-0001", "note": "n", "intitule": "B1V", " Recyclage Mois ": "36"}]},
            "reserves_controle": {"entete": ["id", "controle_id", "texte"], "lignes": [
                {"id": "RES-00007", "controle_id": "CTR-0001", "texte": "garde-corps"}]},
            "parametres": {"entete": ["cle", "valeur"], "lignes": [{"cle": "version_schema", "valeur": "'3"}]},
        }
        avant = copy.deepcopy(base)
        quatre = serveur.ETAPES_FORMAT[2].appliquer(base)
        self.assertEqual(base, avant)
        self.assertEqual(serveur.ETAPES_FORMAT[2].appliquer(quatre), quatre)
        controles = quatre["controles_reglementaires"]
        self.assertEqual(controles["entete"][-5:], ["remarque_maison"] + COLONNES_AJOUTEES[4]["controles_reglementaires"])
        self.assertEqual([(l["remarque_maison"], l["source_periodicite"], l["nature_source"], l["catalogue_relu_le"])
                          for l in controles["lignes"]], [("r", "saisie", "", ""), ("", "catalogue", "", "")])
        # Colonne déjà là (nom avec espaces et majuscules) : reconnue, pas de doublon ; les autres en fin
        habilitations = quatre["habilitations"]
        self.assertEqual(habilitations["entete"], ["id", "note", "intitule", " Recyclage Mois ", "technicien_id",
                                                   "date_obtention", "date_echeance", "justificatif", "catalogue_id",
                                                   "nature_source"])
        self.assertEqual(habilitations["lignes"][0][" Recyclage Mois "], "36")
        self.assertNotIn("recyclage_mois", habilitations["lignes"][0])
        # Table du format 4 déjà là : lignes gardées, colonnes manquantes en fin (levee : défaut 0)
        reserves = quatre["reserves_controle"]
        self.assertEqual(reserves["entete"][:3], ["id", "controle_id", "texte"])
        self.assertEqual(sorted(reserves["entete"]), sorted(serveur.COLONNES_PAR_TABLE["reserves_controle"]))
        self.assertEqual(reserves["lignes"][0]["texte"], "garde-corps")
        self.assertEqual(reserves["lignes"][0]["levee"], "0")
        self.assertEqual(len(reserves["lignes"]), 1)
        self.assertEqual(quatre["garanties"], {"entete": list(serveur.COLONNES_PAR_TABLE["garanties"]), "lignes": []})
        self.assertEqual(quatre["contrats_prestataires"]["lignes"], [])
        self.assertEqual(quatre["parametres"]["lignes"], [{"cle": "version_schema", "valeur": "'4"}])
        self.assertEqual(len(serveur.ETAPES_FORMAT[2].appliquer(None)), NB_TABLES)

    # -- Reprise des observations en réserves (D183, CS170) -----------------------------------------------------

    def test_reprise_cs170_sur_le_jeu_reserves_a_reprendre(self):
        """CS170 : trois lignes non vides → trois réserves ; observations levées → réserves levées, date de levée vide,
        commentaire fixe ; cellules écrites comme Prévo les écrit (apostrophe de protection, guillemets doublés) ;
        contrôles inchangés ; étape rejouée : rien de plus."""
        avant = self.base("reserves-a-reprendre")
        quatre = serveur.migrer_tables(avant, 3, FORMAT_COURANT)[0]
        reserves = quatre["reserves_controle"]
        self.assertEqual(serveur.COMMENTAIRE_LEVEE_REPRISE, COMMENTAIRE_LEVEE_REPRISE)
        self.assertEqual(reserves["entete"], COLONNES_RESERVES)
        self.assertEqual(reserves["lignes"],
                         [reserve_complete(*r) for r in RESERVES_DU_LISEZMOI["reserves-a-reprendre"]])
        self.assertEqual(reserves["lignes"], reserves_attendues(avant["controles_reglementaires"]["lignes"]))
        octets = octets_de_table(reserves).decode("utf-8-sig").split("\r\n")
        self.assertEqual(octets[0], ";".join(COLONNES_RESERVES))
        self.assertEqual(octets[4], "RES-00004;CTR-0002;2026-03-18;Klaxon de recul inaudible;;;1;;"
                                    "levée avant la 2.2, date inconnue;")
        self.assertEqual(octets[6], "RES-00006;CTR-0005;2026-03-24;'- Raccord de la vanne 3 suintant;;;0;;;")
        self.assertEqual(octets[7], "RES-00007;CTR-0005;2026-03-24;'= Pression basse à surveiller;;;0;;;")
        self.assertEqual(octets[9], 'RES-00009;CTR-0006;2026-06-02;"Gaine ""B"" percée ; débit insuffisant";;;0;;;')
        self.assertEqual(octets[15], "RES-00015;CTR-0008;;Rapport du contrôle initial non retrouvé;;;0;;;")
        self.assertEqual(octets[16:], [""])
        # Contrôles sans observations (levés ou non) ou aux lignes blanches seulement : rien
        self.assertFalse({"CTR-0003", "CTR-0004", "CTR-0009"} & {l["controle_id"] for l in reserves["lignes"]})
        # Les contrôles gardent leurs cellules (CS169 ; colonnes du format 4 ajoutées en fin)
        for ligne_avant, ligne in zip(avant["controles_reglementaires"]["lignes"],
                                      quatre["controles_reglementaires"]["lignes"]):
            self.assertEqual({c: ligne[c] for c in ligne_avant}, ligne_avant)
        # Rejouée : rien de nouveau
        self.assertEqual(serveur.reserves_reprises(quatre["controles_reglementaires"]["lignes"], reserves["lignes"]),
                         [])
        self.assertEqual(serveur.ETAPES_FORMAT[2].appliquer(quatre), quatre)

    def test_reserves_reprises_cas_fabriques(self):
        """reserves_reprises sur des cellules fabriquées : formes d'Excel (oui, x, Vrai, TRUE, JJ/MM/AAAA, J.M.AAAA,
        date impossible gardée en texte, année 0004 et 0000 lues comme Date.UTC), contrôle déjà doté d'une réserve,
        identifiant vide, blanc ou en double, coupes sur CRLF, CR et LF seulement, bords blancs retirés comme trim (BOM,
        U+2028, U+2029, espace idéographique oui ; U+0085 non), apostrophes de protection relues puis réécrites,
        numérotation en texte après le plus grand RES-<chiffres> exact (au-delà de la limite de chiffres de int()),
        lignes et entrées étranges ignorées ; pure, déterministe, rejouée sans rien de plus."""
        controles = CONTROLES_FABRIQUES + [None, 3, "CTR-0014", ["CTR-0015", "x"]]
        reserves = RESERVES_FABRIQUEES + [None, "RES-00500"]
        avant = copy.deepcopy([controles, reserves])
        resultat = serveur.reserves_reprises(controles, reserves)
        self.assertEqual([controles, reserves], avant, "reserves_reprises a modifié ses entrées")
        self.assertEqual(resultat, [reserve_complete(*r) for r in RESERVES_FABRIQUEES_ATTENDUES])
        self.assertEqual({tuple(l) for l in resultat}, {tuple(COLONNES_RESERVES)})       # colonnes dans l'ordre
        self.assertEqual(serveur.reserves_reprises(controles, reserves), resultat)
        self.assertEqual(serveur.reserves_reprises(controles, reserves + resultat), [])
        for entree in ((None, None), ([{}], "x"), ("CTR", 3), ({}, {}), ([], [])):
            self.assertEqual(serveur.reserves_reprises(*entree), [])
        self.assertEqual([l["id"] for l in serveur.reserves_reprises([controle_fabrique("CTR-1", "a", "0", "")], None)],
                         ["RES-00001"])

        def un(identifiant):
            existantes = [] if identifiant is None else [{"id": identifiant, "controle_id": "Z"}]
            return serveur.reserves_reprises([controle_fabrique("A", "x", "0", "")], existantes)[0]["id"]

        tres_long = "9" * 5000
        limite = getattr(sys, "get_int_max_str_digits", lambda: 0)()     # Python 3.11 et plus : 4300 par défaut
        if limite:
            self.assertLess(limite, len(tres_long))
            with self.assertRaises(ValueError):
                int(tres_long)                      # d'où les numéros comparés et augmentés en texte
        numeros = [None, "RES-00000", "RES-999999", "RES-99999", "RES-99999999999999999999",
                   "RES-0000000000000000000000041", " RES-7\t", "RES-" + tres_long, "RES-" + "0" * 4999 + "7"]
        self.assertEqual([un(n) for n in numeros],
                         ["RES-00001", "RES-00001", "RES-1000000", "RES-100000", "RES-100000000000000000000",
                          "RES-00042", "RES-00008", "RES-1" + "0" * 5000, "RES-00008"])
        ordres = [[{"id": "RES-9"}, {"id": "RES-10"}], [{"id": "RES-10"}, {"id": "RES-9"}],
                  [{"id": "RES-099"}, {"id": "RES-100"}, {"id": "RES-0101"}]]
        self.assertEqual([serveur.reserves_reprises([controle_fabrique("A", "x", "0", "")], existantes)[0]["id"]
                          for existantes in ordres], ["RES-00011", "RES-00011", "RES-00102"])
        self.assertEqual([serveur.numero_suivant(n) for n in ("", "1", "9", "41", "99", "1099", "190")],
                         ["1", "2", "10", "42", "100", "1100", "191"])
        # Colonnes nommées comme dans le fichier (casse, espaces, accents) : reconnues comme Donnees.csv.analyser
        a_la_main = serveur.reserves_reprises(
            [{" ID ": "CTR-1", "Observations": "Fuite", "Observations levées": "oui", "Dernière date": "1/2/2024"}],
            [{"Id": "RES-00004", " Contrôle_id": "CTR-2"}])
        self.assertEqual(a_la_main, [reserve_complete("RES-00005", "CTR-1", "2024-02-01", "Fuite", "1")])

    def test_dates_et_booleens_lus_comme_donnees(self):
        """Copies de lireDate et normaliserBooleen (js/donnees.js) : quelques résultats connus ; la comparaison au
        navigateur sur une batterie de valeurs est dans TestConcordanceNavigateur."""
        dates = {"2024-01-15": "2024-01-15", " 2024-1-5 ": "2024-01-05", "15/01/2024": "2024-01-15",
                 "5.3.2024": "2024-03-05", "15-01-2024": "2024-01-15", "15/01-2024": "15/01-2024",
                 "31/02/2024": "31/02/2024", "29/02/2024": "2024-02-29", "29/02/2023": "29/02/2023",
                 "29/02/1900": "29/02/1900", "29/02/2000": "2000-02-29", "29/02/0004": "0004-02-29",
                 "29/02/0000": "29/02/0000", "29/02/0100": "29/02/0100", "0000-01-01": "0000-01-01", "": "",
                 "  ": "", "'2024-01-15": "'2024-01-15", "2024-01-15\n": "2024-01-15", "2024-01-15\n1": "2024-01-15\n1",
                 "１５/01/2024": "１５/01/2024", INSECABLE + "15/01/2024": "2024-01-15", None: ""}
        self.assertEqual({d: serveur.date_lue_js(d) for d in dates}, dates)
        booleens = {"1": "1", "0": "0", "oui": "1", " OUI ": "1", "non": "0", "Vrai": "1", "faux": "0", "TRUE": "1",
                    "false": "0", "yes": "1", "No": "0", "x": "1", "X": "1", "": "", "2": "2",
                    "constructor": "constructor", "Ｘ": "Ｘ", None: ""}
        self.assertEqual({b: serveur.booleen_lu_js(b) for b in booleens}, booleens)

    def test_etape_3_4_reprise_cas_fabriques(self):
        """Étape 3→4 avec la reprise (miroir de tests/test_formats_js.py) : base 2.1 sans reserves_controle (table
        créée avec les réserves reprises, migrer_tables = ETAPES_FORMAT[2].appliquer, rejouée : rien de plus) ; base
        déjà au format 4 dont un contrôle a une réserve créée dans la 2.2 avant la reprise (§3.5) : réserve gardée en
        tête, ce contrôle n'est pas repris, les autres le sont à la suite ; en-tête de reserves_controle écrit à la
        main (colonnes nommées comme le fichier, colonne inconnue vide) ; base sans contrôles : aucune réserve ;
        entrées jamais modifiées."""
        colonnes3 = serveur.colonnes_du_format("controles_reglementaires", 3)

        def controles():
            return {"entete": list(colonnes3), "lignes": [
                dict({c: "" for c in colonnes3}, **controle_fabrique("CTR-0001", "Garde-corps\nÉclairage", "1",
                                                                     "2024-05-06")),
                dict({c: "" for c in colonnes3}, **controle_fabrique("CTR-0002", "Fuite", "0", "")),
                dict({c: "" for c in colonnes3}, **controle_fabrique("CTR-0003", "", "1", "2024-05-07"))]}

        base21 = {"controles_reglementaires": controles(),
                  "parametres": {"entete": ["cle", "valeur"], "lignes": [{"cle": "version_schema", "valeur": "'3"}]}}
        saisie = {"id": "RES-00004", "controle_id": "CTR-0002", "date_controle": "2024-07-01",
                  "texte": "saisie dans la 2.2", "gravite": "majeure", "echeance_levee": "", "levee": "0",
                  "date_levee": "", "commentaire_levee": "", "ot_id": ""}
        base4 = {"controles_reglementaires": controles(),
                 "reserves_controle": {"entete": list(COLONNES_RESERVES), "lignes": [saisie]},
                 "parametres": {"entete": ["cle", "valeur"], "lignes": [{"cle": "version_schema", "valeur": "'4"}]}}
        avant = copy.deepcopy([base21, base4])
        une = serveur.ETAPES_FORMAT[2].appliquer(base21)
        reprise4 = serveur.ETAPES_FORMAT[2].appliquer(base4)
        self.assertEqual([base21, base4], avant)
        reprises21 = [reserve_complete("RES-00001", "CTR-0001", "2024-05-06", "Garde-corps", "1"),
                      reserve_complete("RES-00002", "CTR-0001", "2024-05-06", "Éclairage", "1"),
                      reserve_complete("RES-00003", "CTR-0002", "", "Fuite", "0")]
        self.assertEqual(une["reserves_controle"], {"entete": COLONNES_RESERVES, "lignes": reprises21})
        self.assertEqual(serveur.ETAPES_FORMAT[2].appliquer(une), une)
        self.assertEqual(serveur.migrer_tables(base21, 3, 4)[0], une)
        self.assertEqual(serveur.migrer_tables(base21, 1, 4)[0]["reserves_controle"], une["reserves_controle"])
        self.assertEqual([(l["observations"], l["observations_levees"])
                          for l in une["controles_reglementaires"]["lignes"]],
                         [("Garde-corps\nÉclairage", "1"), ("Fuite", "0"), ("", "1")])
        self.assertEqual(reprise4["reserves_controle"]["lignes"], [
            saisie, reserve_complete("RES-00005", "CTR-0001", "2024-05-06", "Garde-corps", "1"),
            reserve_complete("RES-00006", "CTR-0001", "2024-05-06", "Éclairage", "1")])
        self.assertIsNot(reprise4["reserves_controle"]["lignes"][0], base4["reserves_controle"]["lignes"][0])
        self.assertEqual(serveur.ETAPES_FORMAT[2].appliquer(reprise4), reprise4)
        # En-tête écrit à la main : la réserve reprise prend les noms du fichier, la colonne inconnue reste vide
        a_la_main = dict(base21, reserves_controle={"entete": [" Id ", "Contrôle_id", "Texte", "note_maison"],
                                                    "lignes": []})
        reserves = serveur.ETAPES_FORMAT[2].appliquer(a_la_main)["reserves_controle"]
        self.assertEqual(reserves["entete"][:4], [" Id ", "Contrôle_id", "Texte", "note_maison"])
        self.assertEqual(reserves["lignes"][0], {" Id ": "RES-00001", "Contrôle_id": "CTR-0001", "Texte": "Garde-corps",
                                                 "note_maison": "", "date_controle": "2024-05-06", "gravite": "",
                                                 "echeance_levee": "", "levee": "1", "date_levee": "",
                                                 "commentaire_levee": COMMENTAIRE_LEVEE_REPRISE, "ot_id": ""})
        self.assertEqual(octets_de_table(reserves).decode("utf-8-sig").split("\r\n")[1],
                         "RES-00001;CTR-0001;Garde-corps;;2024-05-06;;;1;;%s;" % COMMENTAIRE_LEVEE_REPRISE)
        # Base sans contrôles (appel par table, sonde du passage au démarrage) : aucune réserve
        sans_controles = serveur.ETAPES_FORMAT[2].appliquer({"ordres_travail": {"entete": ["id"], "lignes": [{}]}})
        self.assertEqual(sans_controles["reserves_controle"], {"entete": COLONNES_RESERVES, "lignes": []})
        self.assertEqual(serveur.ETAPES_FORMAT[2].appliquer(None)["reserves_controle"],
                         {"entete": COLONNES_RESERVES, "lignes": []})
        sonde = serveur.migrer_tables({"controles_reglementaires": {"entete": list(colonnes3), "lignes": [{}]}}, 3, 4)
        self.assertEqual(sonde[0]["reserves_controle"]["lignes"], [])

    def test_migrer_etapes_choisies_et_erreurs(self):
        base = {"ordres_travail": {"entete": serveur.colonnes_du_format("ordres_travail", 1), "lignes": []}}
        vers_deux, journal, etapes = serveur.migrer_tables(base, 1, 2)
        self.assertEqual(journal, ["passage au format 2 du fichier"])
        self.assertEqual(vers_deux["ordres_travail"]["entete"][-1], "anomalie_constatee")
        self.assertEqual(len(vers_deux), 22)
        self.assertEqual(vers_deux["parametres"]["lignes"], [{"cle": "version_schema", "valeur": "'2"}])
        self.assertEqual(etapes, [{"de": 1, "vers": 2, "description": serveur.ETAPES_FORMAT[0].description}])
        self.assertEqual(serveur.migrer_tables(base, 0, FORMAT_COURANT)[1], LIGNES_DE_JOURNAL[1])
        self.assertEqual(serveur.migrer_tables(base, 2.5, FORMAT_COURANT)[1], LIGNES_DE_JOURNAL[2])
        self.assertEqual(serveur.migrer_tables(base, 3.5, FORMAT_COURANT)[1], LIGNES_DE_JOURNAL[3])
        self.assertEqual(serveur.migrer_tables(base, 1, 4.0)[1], LIGNES_DE_JOURNAL[1])
        self.assertEqual(serveur.migrer_tables(base, float("-inf"), FORMAT_COURANT)[1], LIGNES_DE_JOURNAL[1])
        vers_trois = serveur.migrer_tables(base, 1, 3)
        self.assertEqual(vers_trois[1], LIGNES_DE_JOURNAL[1][:2])
        self.assertEqual(len(vers_trois[0]), 24)
        self.assertEqual(vers_trois[0]["ordres_travail"]["entete"][-1], "astuce")
        self.assertEqual(serveur.migrer_tables(base, 2.5, 3)[1], ["passage au format 3 du fichier"])
        self.assertIs(serveur.migrer_tables(base, 2, 2)[0], base)
        self.assertIs(serveur.migrer_tables(base, float("inf"), FORMAT_COURANT)[0], base)
        for vers in (FORMAT_COURANT + 1, 0, 2.5, "3", True, None, float("nan")):
            with self.subTest(vers=vers), self.assertRaisesRegex(ValueError, "format cible inconnu"):
                serveur.migrer_tables(base, 1, vers)
        for de in (float("nan"), "1", None, True):
            with self.subTest(de=de), self.assertRaisesRegex(TypeError, "format de départ illisible"):
                serveur.migrer_tables(base, de, 3)


# ---------------------------------------------------------------------------------------------------------------
# 2. Concordance navigateur / serveur
# ---------------------------------------------------------------------------------------------------------------

# Chemin du navigateur pour un jeu ({table: octets en base64}) : Donnees.csv.analyser (lecture de Prévo), en-tête du
# fichier par Papa.parse (pour Formats.formatDuFichier et Formats.migrer), Formats.versionDeBase, Formats.migrer
# jusqu'au format courant, Donnees.csv.serialiser de chaque table connue du schéma.
SCRIPT_NAVIGATEUR = """
window.octetsDeBase64 = function (texte) {
  const binaire = atob(texte);
  const octets = new Uint8Array(binaire.length);
  for (let i = 0; i < binaire.length; i += 1) { octets[i] = binaire.charCodeAt(i); }
  return octets;
};
window.base64DOctets = function (octets) {
  let binaire = '';
  for (let i = 0; i < octets.length; i += 1) { binaire += String.fromCharCode(octets[i]); }
  return btoa(binaire);
};
window.enteteDuFichier = function (octets, separateur) {
  const texte = Donnees.csv.decoder(octets).texte;
  if (texte.trim() === '') { return []; }
  return Papa.parse(texte, { delimiter: separateur, quoteChar: '"', skipEmptyLines: 'greedy', preview: 1 }).data[0] || [];
};
window.cheminNavigateur = function (jeu) {
  const base = { tables: {} };
  const inconnues = {};
  const formats = {};
  for (const table of Object.keys(jeu)) {
    const octets = octetsDeBase64(jeu[table]);
    if (!Schema.table(table)) { formats[table] = Formats.formatDuFichier(table, enteteDuFichier(octets, ';')); continue; }
    const lu = Donnees.csv.analyser(table, octets);
    const entete = enteteDuFichier(octets, lu.separateur);
    base.tables[table] = { entete: entete, lignes: lu.lignes };
    inconnues[table] = lu.colonnesInconnues;
    formats[table] = Formats.formatDuFichier(table, entete);
  }
  const de = Formats.versionDeBase(base.tables.parametres ? base.tables.parametres.lignes : []);
  const resultat = Formats.migrer(base, de, Formats.courant);
  const entetes = {};
  const octets = {};
  for (const table of Object.keys(resultat.base.tables)) {
    entetes[table] = resultat.base.tables[table].entete;
    octets[table] = base64DOctets(Donnees.csv.serialiser(table, resultat.base.tables[table].lignes,
      inconnues[table] || []));
  }
  return { formats: formats, de: de, journal: resultat.journal,
    etapes: resultat.etapes.map(function (e) { return [e.de, e.vers]; }), entetes: entetes, octets: octets };
};
"""


def au_modele_de_donnees(table, contenu):
    """Octets d'une table de la base du serveur réécrite comme Donnees.csv.serialiser l'écrit (écarts A et B) : toutes
    les colonnes du schéma dans son ordre (absente du fichier : défaut du champ), puis les colonnes inconnues dans leur
    ordre d'origine."""
    schema = list(serveur.COLONNES_PAR_TABLE[table])
    cles_du_schema = {serveur.cle_de_colonne(nom) for nom in schema}
    inconnues = [nom for nom in contenu["entete"] if serveur.cle_de_colonne(nom) not in cles_du_schema]
    defauts = serveur.DEFAUTS_DES_CHAMPS.get(table, {})

    def cellule(ligne, colonne):
        nom = serveur.colonne_de_champ(contenu["entete"], colonne)
        return defauts.get(colonne, "") if nom is None else ligne.get(nom, "")

    lignes = [[cellule(ligne, c) for c in schema] + [ligne.get(n, "") for n in inconnues] for ligne in contenu["lignes"]]
    return serveur.ecrire_tableau_csv(schema + inconnues, lignes)


class TestConcordanceNavigateur(JeuxEnCopie, CasNavigateur):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.copier_les_jeux()

    def setUp(self):
        super().setUp()
        charger_scripts(self.page, SCRIPTS)
        self.page.add_script_tag(content=SCRIPT_NAVIGATEUR)

    def evaluer(self, script, argument=None):
        return self.page.evaluate(script, argument)

    def chemins(self, jeu):
        """(navigateur, serveur) pour un jeu ; octets du navigateur décodés."""
        fichiers = self.fichiers[jeu]
        navigateur = self.evaluer("(jeu) => cheminNavigateur(jeu)",
                                  {table: base64.b64encode(octets).decode("ascii") for table, octets in fichiers.items()})
        navigateur["octets"] = {table: base64.b64decode(texte) for table, texte in navigateur["octets"].items()}
        return navigateur, chemin_serveur(fichiers)

    def verifier_concordance(self, jeu, tables_ecartees=()):
        """Mêmes formats, même version, même journal, mêmes en-têtes migrés, mêmes octets par table (hors tables
        écartées, et hors tables inconnues du schéma que le navigateur n'écrit pas)."""
        navigateur, cote_serveur = self.chemins(jeu)
        self.assertEqual(navigateur["formats"], cote_serveur["formats"])
        self.assertEqual(navigateur["de"], cote_serveur["de"])
        self.assertEqual(navigateur["journal"], cote_serveur["journal"])
        self.assertEqual(navigateur["etapes"], cote_serveur["etapes"])
        connues = {t for t in cote_serveur["octets"] if t in serveur.COLONNES_PAR_TABLE}
        self.assertEqual(set(navigateur["octets"]), connues)
        self.assertEqual({t: navigateur["entetes"][t] for t in connues}, {t: cote_serveur["entetes"][t] for t in connues})
        for table in sorted(connues - set(tables_ecartees)):
            with self.subTest(jeu=jeu, table=table):
                self.assertEqual(navigateur["octets"][table], cote_serveur["octets"][table])
        return navigateur, cote_serveur

    # -- Mêmes listes et mêmes règles que js/ -------------------------------------------------------------------

    def test_registre_identique_a_schema_et_formats(self):
        js = self.evaluer("""() => {
          const colonnes = {};
          const tables = {};
          for (let format = 1; format <= Formats.courant; format += 1) {
            tables[format] = Formats.tables(format);
            colonnes[format] = Object.fromEntries(Schema.nomsTables().map((t) => [t, Formats.colonnes(t, format)]));
          }
          const defauts = {};
          const depuis = {};
          const ecritureDesDefauts = [];
          for (const nom of Schema.nomsTables()) {
            for (const champ of Schema.table(nom).champs) {
              if (champ.defaut !== undefined) {
                (defauts[nom] = defauts[nom] || {})[champ.nom] = champ.defaut;
                if (Donnees.csv.ecrireValeur(champ, champ.defaut) !== champ.defaut) { ecritureDesDefauts.push(nom + '.' + champ.nom); }
              }
              if (champ.depuisVersion !== undefined) { (depuis[nom] = depuis[nom] || {})[champ.nom] = champ.depuisVersion; }
            }
          }
          const tablesDepuis = Object.fromEntries(Schema.nomsTables().filter((t) => Schema.table(t).depuisVersion !== undefined)
            .map((t) => [t, Schema.table(t).depuisVersion]));
          return { courant: Formats.courant, nomsTables: Schema.nomsTables(), tables, colonnes, defauts, depuis,
            tablesDepuis, ecritureDesDefauts,
            etapes: Formats.ETAPES.map((e) => ({ de: e.de, vers: e.vers, description: e.description })) };
        }""")
        self.assertEqual(js["courant"], serveur.VERSION_SCHEMA_CSV)
        self.assertEqual(js["nomsTables"], list(serveur.TABLES))
        for format in range(1, FORMAT_COURANT + 1):
            with self.subTest(format=format):
                self.assertEqual(js["tables"][str(format)], serveur.tables_du_format(format))
                self.assertEqual(js["colonnes"][str(format)],
                                 {t: serveur.colonnes_du_format(t, format) for t in serveur.TABLES})
        self.assertEqual(js["defauts"], serveur.DEFAUTS_DES_CHAMPS)
        self.assertEqual(js["ecritureDesDefauts"], [], "un défaut s'écrirait avec une apostrophe")
        self.assertEqual(js["depuis"], serveur.PREMIER_FORMAT_DES_COLONNES)
        self.assertEqual(js["tablesDepuis"], serveur.PREMIER_FORMAT_DES_TABLES)
        self.assertEqual(js["etapes"], [{"de": e.de, "vers": e.vers, "description": e.description}
                                        for e in serveur.ETAPES_FORMAT])

    def test_format_du_fichier_comme_le_navigateur(self):
        variantes = ["titre", "Titre", " titre ", "TITRE", "ti_tre", "ti tre", "Tîtré", "Tİtre", CARACTERE_BOM + "titre",
                     "titre" + INSECABLE, INSECABLE_FINE + "titre", CADRATIN + "titre", "titre" + IDEOGRAPHIQUE,
                     "ti" + ESPACE_NULLE + "tre", "titre" + LIGNE_SUIVANTE, "titre" + SEPARATEUR_DE_FICHIER,
                     "titre\t", "titre\n", "_titre_", "titres", "", CARACTERE_BOM]
        entetes = [[v if n == "titre" else n for n in serveur.colonnes_du_format("ordres_travail")] for v in variantes]
        entetes += [serveur.colonnes_du_format("ordres_travail", f) for f in (1, 2, 3)] + [[], ["id"]]
        js = self.evaluer("(entetes) => entetes.map((e) => Formats.formatDuFichier('ordres_travail', e))", entetes)
        self.assertEqual(js, [serveur.format_du_fichier("ordres_travail", e) for e in entetes])
        self.assertIn(0, js)
        self.assertIn(3, js)
        self.assertIn(FORMAT_COURANT, js)
        autres = {"pieces_v5": ["id"], "parametres": ["Clé", " VALEUR "], "wiki_pages": [],
                  "reserves_controle": serveur.colonnes_du_format("reserves_controle")[::-1], "garanties": ["id"],
                  "contrats_prestataires": serveur.colonnes_du_format("contrats_prestataires"),
                  "controles_reglementaires": serveur.colonnes_du_format("controles_reglementaires", 3) + ["note"]}
        js = self.evaluer("(cas) => Object.fromEntries(Object.entries(cas).map(([t, e]) => [t, Formats.formatDuFichier(t, e)]))",
                          autres)
        self.assertEqual(js, {t: serveur.format_du_fichier(t, e) for t, e in autres.items()})

    def test_version_de_base_et_apostrophe_comme_le_navigateur(self):
        valeurs = ["3", "'3", "''3", "'2", " 2 ", "'2,0", "2.0", "'2,5", "+3", "'+3", "'-1", "'3 000", "3 000", "'1e3",
                   "abc", "'abc", "", "'", "v3", "'=3", "'12/03", INSECABLE + "3", "'3" + INSECABLE_FINE, CADRATIN + "3",
                   "'4", "4"]
        cles = ["version_schema", " version_schema ", "'version_schema", "Version_schema"]
        cas = [(["cle", "valeur"], [cle, valeur]) for cle in cles[:1] for valeur in valeurs]
        cas += [(["cle", "valeur"], [cle, "'2"]) for cle in cles[1:]]
        cas += [(["Clé", "Valeur"], ["version_schema", "'2"]), (["cle", "valeur"], ["entreprise_nom", "3"])]
        fichiers = [serveur.ecrire_tableau_csv(entete, [ligne]) for entete, ligne in cas]
        js = self.evaluer("""(fichiers) => fichiers.map((f) =>
          Formats.versionDeBase(Donnees.csv.analyser('parametres', octetsDeBase64(f)).lignes))""",
                          [base64.b64encode(octets).decode("ascii") for octets in fichiers])
        python = [serveur.version_de_base(table_de_base(octets)["lignes"]) for octets in fichiers]
        self.assertEqual(python, js)
        self.assertEqual(python[:3], [3, 3, 1])
        textes = valeurs + ["=1+1", "-5", "@x", "\tx", "08:30", "15 %", "1,5E+3", "x'", "007", "2026-11-04", " 3"]
        js = self.evaluer("""(valeurs) => { const champ = Schema.champ('parametres', 'valeur');
          return { relues: valeurs.map((v) => Donnees.csv.relireValeur(champ, v)),
            ecrites: valeurs.map((v) => Donnees.csv.ecrireValeur(champ, v)) }; }""", textes)
        self.assertEqual([serveur.relire_valeur_texte(v) for v in textes], js["relues"])
        self.assertEqual([serveur.ecrire_valeur_texte(v) for v in textes], js["ecrites"])

    def test_etapes_cas_fabriques_comme_le_navigateur(self):
        # Même base fabriquée, mêmes étapes : mêmes tables, en-têtes et lignes ; la seule différence de forme est la
        # cellule de version_schema (« '3 » côté serveur, cellule du fichier ; « 3 » en mémoire côté navigateur).
        bases = [
            {"equipements": {"entete": ["id", "colonne_maison", "designation", "actif"], "lignes": [
                {"id": "EQ-1", "colonne_maison": "m1", "designation": "Presse", "actif": "0"},
                {"id": "EQ-2", "colonne_maison": "", "designation": "Tour", "valeur_remplacement": "1200"}]},
             "ordres_travail": {"entete": [CARACTERE_BOM + "id", " titre "],
                                "lignes": [{CARACTERE_BOM + "id": "OT-1", " titre ": "T"}]},
             "wiki_pages": {"entete": ["id", "type"], "lignes": [{"id": "WP-1", "type": "composant"}]},
             "pieces_v5": {"entete": ["id"], "lignes": [{"id": "P-1"}]}},
            {"parametres": {"entete": ["cle", "valeur", "note"], "lignes": [
                {"cle": "entreprise_nom", "valeur": "A", "note": "n"}, {"cle": "version_schema", "valeur": "1"}]}},
            {},
            # Format 4 : colonne inconnue avant les colonnes ajoutées, valeur déjà là, table du format 4 déjà là
            # (contrôles sans observations : la reprise des réserves, D183, n'y change rien)
            {"controles_reglementaires": {"entete": ["id", "remarque_maison", "observations", " Nature Source "],
                                          "lignes": [{"id": "CTR-1", "remarque_maison": "r", "observations": "",
                                                      " Nature Source ": "norme"}]},
             "habilitations": {"entete": ["id", "intitule"], "lignes": [{"id": "HAB-1", "intitule": "B1V"}]},
             "reserves_controle": {"entete": ["id", "texte"], "lignes": [{"id": "RES-00003", "texte": "t"}]},
             "garanties": {"entete": ["id", "note"], "lignes": [{"id": "GAR-0001", "note": "n"}]}},
            # Reprise des observations (D183) : valeurs canoniques, qui s'écrivent sans apostrophe (cellule = valeur)
            {"controles_reglementaires": {"entete": ["id", "observations", "observations_levees", "derniere_date"],
                                          "lignes": [controle_fabrique("CTR-1", "Un\nDeux", "1", "2024-05-06"),
                                                     controle_fabrique("CTR-2", "Trois", "0", "")]},
             "reserves_controle": {"entete": list(COLONNES_RESERVES),
                                   "lignes": [reserve_complete("RES-00009", "CTR-2", "", "saisie", "0")]}},
        ]
        js = self.evaluer("""(bases) => bases.map((tables) => Formats.ETAPES.map((etape) =>
          etape.appliquer({ tables: tables }).tables))""", bases)
        for numero, base in enumerate(bases):
            for rang, etape in enumerate(serveur.ETAPES_FORMAT):
                with self.subTest(base=numero, etape=etape.vers):
                    python = etape.appliquer(base)
                    for ligne in python["parametres"]["lignes"]:
                        if ligne["cle"] == "version_schema":
                            ligne["valeur"] = serveur.relire_valeur_texte(ligne["valeur"])
                    self.assertEqual(python, js[numero][rang])
        self.assertEqual([l["id"] for l in js[-1][2]["reserves_controle"]["lignes"]],
                         ["RES-00009", "RES-00010", "RES-00011"])

    # -- Reprise des observations en réserves (D183) : mêmes réserves, mêmes octets ------------------------------

    def test_reserves_controle_memes_octets_sur_chaque_jeu(self):
        """Sur chaque jeu (abîmés compris : leurs contrôles sont lisibles), reserves_controle migrée aux mêmes octets
        des deux côtés, avec les réserves reprises ; plus-recent (format 5, rien n'est migré) : la table n'existe
        d'aucun côté."""
        for jeu in JEUX:
            with self.subTest(jeu=jeu):
                navigateur, cote_serveur = self.chemins(jeu)
                base = base_de_fichiers(self.fichiers[jeu])
                if cote_serveur["de"] >= FORMAT_COURANT:
                    self.assertNotIn("reserves_controle", navigateur["octets"])
                    self.assertNotIn("reserves_controle", cote_serveur["octets"])
                    continue
                attendues = reserves_attendues(base.get("controles_reglementaires", {"lignes": []})["lignes"])
                if jeu in RESERVES_DU_LISEZMOI:
                    self.assertEqual(attendues, [reserve_complete(*r) for r in RESERVES_DU_LISEZMOI[jeu]])
                self.assertEqual(len(attendues) > 0, jeu != "f1")
                self.assertEqual(cote_serveur["octets"]["reserves_controle"],
                                 octets_de_table({"entete": COLONNES_RESERVES, "lignes": attendues}))
                self.assertEqual(navigateur["octets"]["reserves_controle"], cote_serveur["octets"]["reserves_controle"])

    def test_reserves_reprises_cas_fabriques_comme_le_navigateur(self):
        """Fichiers fabriqués (CONTROLES_FABRIQUES, RESERVES_FABRIQUEES ; colonnes « Observations » et « Dernière
        date » nommées à la main) lus par Donnees.csv.analyser puis repris par Formats.reservesReprises, chaque valeur
        écrite par Donnees.csv.ecrireValeur : les mêmes lignes, cellule pour cellule, que reserves_reprises sur les
        cellules lues par lire_csv_tolerant. Puis la base entière (version 3, réserves existantes dont un numéro de
        5000 chiffres) passée au format 4 des deux côtés : reserves_controle aux mêmes octets."""
        a_la_main = {"observations": "Observations", "derniere_date": "Dernière date"}
        entete = [a_la_main.get(c, c) for c in serveur.colonnes_du_format("controles_reglementaires", 3)]
        lignes = [{a_la_main.get(c, c): v for c, v in ligne.items()} for ligne in CONTROLES_FABRIQUES]
        controles = fichier_fabrique(entete, lignes)
        reserves = fichier_fabrique(COLONNES_RESERVES, RESERVES_FABRIQUEES)
        en_base64 = {nom: base64.b64encode(octets).decode("ascii")
                     for nom, octets in (("controles", controles), ("reserves", reserves))}
        js = self.evaluer("""(f) => {
          const controles = Donnees.csv.analyser('controles_reglementaires', octetsDeBase64(f.controles)).lignes;
          const reserves = Donnees.csv.analyser('reserves_controle', octetsDeBase64(f.reserves)).lignes;
          return Formats.reservesReprises(controles, reserves).map((ligne) => Object.keys(ligne).map((colonne) =>
            [colonne, Donnees.csv.ecrireValeur(Schema.champ('reserves_controle', colonne), ligne[colonne])]));
        }""", en_base64)
        python = serveur.reserves_reprises(table_de_base(controles)["lignes"], table_de_base(reserves)["lignes"])
        self.assertEqual([[list(paire) for paire in ligne.items()] for ligne in python], js)
        self.assertEqual(python, [reserve_complete(*r) for r in RESERVES_FABRIQUEES_ATTENDUES])
        # Base entière : réserves existantes canoniques (relues et réécrites à l'identique des deux côtés)
        existantes = [reserve_complete("RES-00007", "CTR-0002", "2024-07-01", "gardée", "0"),
                      dict(reserve_complete("RES-" + "9" * 5000, "CTR-0099", "", "numéro très long", "1"),
                           gravite="majeure", date_levee="2024-08-01", commentaire_levee="levée sur place")]
        fichiers = {"parametres": fichier_fabrique(["cle", "valeur"], [{"cle": "version_schema", "valeur": "'3"}]),
                    "controles_reglementaires": controles,
                    "reserves_controle": fichier_fabrique(COLONNES_RESERVES, existantes)}
        navigateur = self.evaluer("(jeu) => cheminNavigateur(jeu)",
                                  {t: base64.b64encode(o).decode("ascii") for t, o in fichiers.items()})
        cote_serveur = chemin_serveur(fichiers)
        self.assertEqual((navigateur["de"], navigateur["journal"]), (cote_serveur["de"], cote_serveur["journal"]))
        self.assertEqual(cote_serveur["journal"], ["passage au format 4 du fichier"])
        octets = cote_serveur["octets"]["reserves_controle"]
        self.assertEqual(base64.b64decode(navigateur["octets"]["reserves_controle"]), octets)
        lues = table_de_base(octets)["lignes"]
        self.assertEqual(lues[:2], existantes)
        self.assertEqual(len(lues), 2 + len(RESERVES_FABRIQUEES_ATTENDUES))
        self.assertEqual([l["id"] for l in lues[2:4]], ["RES-1" + "0" * 4999 + "0", "RES-1" + "0" * 4999 + "1"])

    def test_dates_et_booleens_lus_comme_donnees_par_le_navigateur(self):
        """date_lue_js et booleen_lu_js (copies de lireDate et normaliserBooleen) donnent les valeurs de
        Donnees.normaliser.date et .booleen sur une batterie de cellules d'Excel et de saisie (années 0000 à 0099 lues
        comme Date.UTC, chiffres non ASCII, blancs de JavaScript aux bords, U+0085 qui n'en est pas un, fin de ligne
        finale). Booléens : même lecture « vrai » ; même valeur partout où Donnees rend un texte (« constructor » et
        « __proto__ » rendent un objet du prototype, jamais « 1 »)."""
        dates = ["2024-01-15", " 2024-01-15 ", "2024-1-5", "15/01/2024", "5/1/2024", "15-01-2024", "15.01.2024",
                 "15/01-2024", "31/02/2024", "29/02/2024", "29/02/2023", "29/02/1900", "29/02/2000", "2024-13-01",
                 "00/01/2024", "15/01/24", "2024-01-15 08:30", "2024-01-15T08:30", "", "   ", "﻿15/01/2024",
                 "demain", "１５/01/2024", "١٥/01/2024", "0001-01-01", "9999-12-31", "2024-02-30",
                 "1/13/2024", "2024/01/15", "15 01 2024", "45306", "29/02/0000", "29/02/0004", "29/02/0096",
                 "29/02/0100", "0000-02-29", "0000-01-01", "1/1/0050", "2024-01-15\n", "2024-01-15\n1",
                 INSECABLE + "15/01/2024" + INSECABLE_FINE, " 2024-01-15 ", "\u00852024-01-15",
                 "'2024-01-15", "15/01/2024\t", "15/01/2024\r"]
        booleens = ["1", "0", "oui", "OUI", " Oui ", "non", "Non", "vrai", "faux", "Vrai", "true", "FALSE", "yes", "No",
                    "x", "X", " x ", "", " ", "2", "o", "n", "ouí", "oui.", "constructor", "Constructor", "__proto__",
                    "toString", "﻿1", "Ｘ", "İ", "x\u0085", INSECABLE + "oui", "oui\r"]
        js = self.evaluer("""(valeurs) => ({
          dates: valeurs.dates.map((v) => Donnees.normaliser.date(v).valeur),
          booleens: valeurs.booleens.map((v) => { const lu = Donnees.normaliser.booleen(v).valeur;
            return [typeof lu === 'string' ? lu : null, lu === '1']; }) })""", {"dates": dates, "booleens": booleens})
        self.assertEqual([serveur.date_lue_js(d) for d in dates], js["dates"])
        self.assertIn("0004-02-29", js["dates"])
        self.assertIn("29/02/0000", js["dates"])
        python = [serveur.booleen_lu_js(b) for b in booleens]
        self.assertEqual([lu == "1" for lu in python], [vrai for _, vrai in js["booleens"]])
        self.assertEqual([lu for lu, (texte, _) in zip(python, js["booleens"]) if texte is not None],
                         [texte for texte, _ in js["booleens"] if texte is not None])
        self.assertEqual([b for b, (texte, _) in zip(booleens, js["booleens"]) if texte is None],
                         ["constructor", "Constructor", "__proto__"])

    # -- Chaque jeu : lecture + migration + écriture → mêmes octets ---------------------------------------------

    def test_concordance_f1(self):
        self.verifier_concordance("f1")

    def test_concordance_f2_v1_1_0(self):
        self.verifier_concordance("f2-v1.1.0")

    def test_concordance_f3_v1_2_0(self):
        self.verifier_concordance("f3-v1.2.0")

    def test_concordance_f3_v2_0_0(self):
        self.verifier_concordance("f3-v2.0.0")

    def test_concordance_sans_bom(self):
        self.verifier_concordance("sans-bom")

    def test_concordance_table_absente(self):
        # Base au format 3 sans articles.csv ni wiki_pages.csv : l'étape 3→4 (fonction pure) crée, des deux côtés,
        # chaque table du format absente, vide (en-tête seul) ; le passage au démarrage, lui, ne crée pas de fichier
        # (tests/test_formats_navigateur.py, serveur.passer_les_fichiers_au_format_courant).
        navigateur, cote_serveur = self.verifier_concordance("table-absente")
        self.assertNotIn("articles", self.fichiers["table-absente"])
        for table in ("articles", "wiki_pages"):
            self.assertEqual(navigateur["octets"][table],
                             serveur.ecrire_tableau_csv(list(serveur.COLONNES_PAR_TABLE[table]), []), table)

    def test_concordance_plus_recent(self):
        # Base au format 5 : rien n'est migré. Tables connues : mêmes octets, sauf les tables que le format 4 complète
        # (le jeu, fabriqué en T378 avant le format 4, n'a pas leurs colonnes) : écart B, le navigateur écrit les
        # colonnes du schéma (défaut compris), le serveur le fichier tel quel ; la table inconnue pieces_v5 n'est
        # écrite que par le serveur, telle quelle.
        en_retard = tuple(COLONNES_AJOUTEES[4])
        navigateur, cote_serveur = self.verifier_concordance("plus-recent", tables_ecartees=en_retard)
        for table in en_retard:
            with self.subTest(table=table):
                contenu = table_de_base(self.fichiers["plus-recent"][table])
                self.assertNotIn(COLONNES_AJOUTEES[4][table][0], contenu["entete"])
                self.assertEqual(cote_serveur["octets"][table], self.fichiers["plus-recent"][table])
                self.assertEqual(navigateur["octets"][table], au_modele_de_donnees(table, contenu))
        self.assertEqual(cote_serveur["octets"]["pieces_v5"], self.fichiers["plus-recent"]["pieces_v5"])

    def test_concordance_f3_v2_1_0(self):
        self.verifier_concordance("f3-v2.1.0")

    def test_concordance_melange(self):
        # Ancien écart B : depuis le format 4, l'étape 3→4 complète ordres_travail (astuce puis habilitation_requise,
        # en fin, à leur place du schéma) des deux côtés : mêmes octets.
        navigateur, _ = self.verifier_concordance("melange")
        self.assertEqual(navigateur["entetes"]["ordres_travail"][-2:], ["astuce", "habilitation_requise"])

    def test_reserves_a_reprendre_seule_la_place_de_la_colonne_inconnue_differe(self):
        # Jeu canonique (T378) : toutes les tables ont les mêmes octets des deux côtés, sauf controles_reglementaires
        # (écart A) ; même en-tête migré (remarque_maison avant les colonnes du format 4) ; le navigateur écrit
        # remarque_maison en fin de fichier, le serveur à sa place ; les cellules (CRLF, LF et CR dans une cellule,
        # « ; », guillemets, apostrophe de protection) sont les mêmes.
        navigateur, cote_serveur = self.verifier_concordance("reserves-a-reprendre",
                                                             tables_ecartees=("controles_reglementaires",))
        ajoutees = COLONNES_AJOUTEES[4]["controles_reglementaires"]
        self.assertEqual(navigateur["entetes"]["controles_reglementaires"][-5:], ["remarque_maison"] + ajoutees)
        premiere_ligne = {cote: chemin["octets"]["controles_reglementaires"].split(b"\r\n", 1)[0].decode("utf-8-sig")
                          for cote, chemin in (("navigateur", navigateur), ("serveur", cote_serveur))}
        self.assertEqual(premiere_ligne["navigateur"].split(";")[-5:], ajoutees + ["remarque_maison"])
        self.assertEqual(premiere_ligne["serveur"].split(";")[-5:], ["remarque_maison"] + ajoutees)
        entete_n, lignes_n = serveur.lire_csv_tolerant(navigateur["octets"]["controles_reglementaires"])
        entete_s, lignes_s = serveur.lire_csv_tolerant(cote_serveur["octets"]["controles_reglementaires"])
        self.assertEqual(sorted(entete_n), sorted(entete_s))
        self.assertEqual([dict(zip(entete_n, ligne)) for ligne in lignes_n],
                         [dict(zip(entete_s, ligne)) for ligne in lignes_s])

    @unittest.expectedFailure
    def test_concordance_reserves_a_reprendre(self):
        """Écart A (préexistant, CONCEPTION-L1 §3.6) : Donnees.csv.serialiser écrit remarque_maison en fin de fichier,
        après les colonnes du format 4 ; ecrire_tableau_csv la garde à sa place, avant elles (en-tête migré, le même
        des deux côtés). Voir test_reserves_a_reprendre_seule_la_place_de_la_colonne_inconnue_differe."""
        self.verifier_concordance("reserves-a-reprendre")

    @unittest.expectedFailure
    def test_concordance_colonnes_en_trop(self):
        """Écart A (préexistant) : Donnees.csv.serialiser écrit colonne_maison en fin de fichier, après les colonnes du
        schéma ; ecrire_tableau_csv la garde à sa place (après designation), comme Formats.migrer et migrer_tables
        gardent l'en-tête. Voir test_ecarts_documentes_et_seulement_eux."""
        self.verifier_concordance("colonnes-en-trop")

    @unittest.expectedFailure
    def test_concordance_colonnes_manquantes(self):
        """Écart B (préexistant) : l'étape 3→4 ajoute modele, valeur_remplacement et cout_arret_h en fin des deux
        en-têtes migrés ; serialiser écrit toutes les colonnes du schéma à leur place (modele en 7e), le serveur
        réécrit l'en-tête migré tel quel (modele en fin)."""
        self.verifier_concordance("colonnes-manquantes")

    @unittest.expectedFailure
    def test_concordance_windows_1252(self):
        """Écart C (préexistant) : Donnees.csv.analyser normalise date_mes (12/03/2019 → 2019-03-12) ;
        lire_csv_tolerant garde la cellule brute. Les deux lecteurs acceptent le fichier."""
        self.verifier_concordance("windows-1252")

    def test_ecarts_documentes_et_seulement_eux(self):
        for jeu, (table_touchee, nature) in sorted(ECARTS_DOCUMENTES.items()):
            with self.subTest(jeu=jeu):
                # Formats, version, journal, en-têtes migrés et toutes les autres tables : identiques
                navigateur, cote_serveur = self.verifier_concordance(jeu, tables_ecartees=(table_touchee,))
                octets_navigateur = navigateur["octets"][table_touchee]
                octets_serveur = cote_serveur["octets"][table_touchee]
                self.assertNotEqual(octets_navigateur, octets_serveur, "écart disparu : retirer expectedFailure")
                contenu = table_de_base(self.fichiers[jeu][table_touchee])
                if nature == "colonnes":
                    # Les octets du navigateur sont ceux du serveur une fois les colonnes rangées comme Donnees les range
                    self.assertEqual(octets_navigateur, au_modele_de_donnees(table_touchee, contenu))
                    continue
                # Valeurs : mêmes en-têtes et lignes ; seules les dates de date_mes diffèrent, JJ/MM/AAAA → AAAA-MM-JJ
                entete_n, lignes_n = serveur.lire_csv_tolerant(octets_navigateur)
                entete_s, lignes_s = serveur.lire_csv_tolerant(octets_serveur)
                self.assertEqual(entete_n, entete_s)
                self.assertEqual(len(lignes_n), len(lignes_s))
                differentes = set()
                for ligne_n, ligne_s in zip(lignes_n, lignes_s):
                    for colonne, valeur_n, valeur_s in zip(entete_n, ligne_n, ligne_s):
                        if valeur_n != valeur_s:
                            differentes.add(colonne)
                            jour, mois, annee = valeur_s.split("/")
                            self.assertEqual(valeur_n, "%s-%s-%s" % (annee, mois, jour))
                self.assertEqual(differentes, {"date_mes"})

    def test_jeux_abimes_meme_format_sans_exception(self):
        for jeu, table in sorted(JEUX_ABIMES.items()):
            with self.subTest(jeu=jeu):
                navigateur, cote_serveur = self.chemins(jeu)        # aucune exception, d'un côté ni de l'autre
                self.assertEqual(navigateur["formats"], cote_serveur["formats"])
                self.assertEqual(navigateur["formats"][table], 0)
                self.assertEqual(navigateur["de"], cote_serveur["de"])
                self.assertEqual(navigateur["journal"], cote_serveur["journal"])
                # Base au format 3 : l'étape 3→4 s'applique, des deux côtés
                self.assertEqual(cote_serveur["journal"], LIGNES_DE_JOURNAL[FORMAT_DES_JEUX])


if __name__ == "__main__":
    unittest.main()
