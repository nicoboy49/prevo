"""Passage des données au format courant au démarrage du serveur, et lecture seule des données plus récentes
(chantier « socle de données », T185 ; décisions D168 et D169 ; format 4 et reprise des observations des contrôles en
réserves : T392, D183, note de conception du format 4 §3.3 à §3.5 ; serveur.py : migrer_donnees_au_demarrage,
reserves_du_passage, verifier_ecriture_permise, GET /api/info « format » ; mêmes règles que Donnees.etatDuFormat et
Donnees.migrerAuFormatCourant de js/donnees.js).

Sans navigateur, sauf TestAdaptateurServeur. Chaque jeu de tests/fixtures/formats (tests/jeux_formats.py) est
copié dans un dossier temporaire (règle du chantier : jamais ailleurs, jamais de données réelles).

1. TestDemarrage — serveur réel (ServeurPrevo de tests/commun.py, --donnees sur la copie), contrôles sur le disque :
     f1, f2-v1.1.0, melange, f3-v1.2.0, f3-v2.0.0, f3-v2.1.0, reserves-a-reprendre   passés au format courant : la
                     sauvegarde « *_avant-format-vN » d'abord (aux octets d'origine), en-têtes complétés en fin
                     (colonnes du format, valeur par défaut), cellules d'origine intactes champ à champ, autres fichiers
                     à l'octet près (acces/ compris), reserves_controle.csv créé avec les réserves de D183 (LISEZMOI des
                     jeux) quand un contrôle a des observations et listé parmi les fichiers complétés (console), aucune
                     autre table créée, une ligne de journal par étape, version_schema = format courant ; second
                     démarrage : aucun octet changé, aucune sauvegarde de plus ;
     entete-tronque, vide   le fichier n'est pas réécrit, il est signalé (tables_abimees, tables_vides ; console) et le
                     reste passe au format courant ; de même pour un en-tête tronqué dans une base au format 2 ;
     plus-recent     aucun octet changé ; PUT /api/csv, POST …/ajout, PUT /api/documents, POST /api/restauration :
                     409 « format_plus_recent » ; lectures et sauvegarde manuelle permises ;
     comptes         copie de f3-v2.0.0 avec comptes exigés : passée au format courant sans aucune connexion
                     (/api/info : 401 sans session).
2. TestCasLimites — serveur.py importé comme module, migrer_donnees_au_demarrage appelée sur une copie (la console est
   relevée) : sauvegarde impossible (dossier des sauvegardes inutilisable) → rien d'écrit ; fichier tenu par un autre
   programme (Windows : fichier ouvert, comme Excel ; ordres_travail.csv, reserves_controle.csv, parametres.csv) →
   arrêt propre, version_schema pas avancé, reprise au démarrage suivant, sans doublon de réserve ; contrôle qui a déjà
   une réserve (créée avant la reprise) : il la garde et ne reçoit rien, les autres sont numérotés à la suite ;
   controles_reglementaires ou reserves_controle abîmés : rien n'est repris ; base au format courant dont
   controles_reglementaires est revenu au format 3 (« fichiers complétés au format 4 ») ; fichiers d'un format ancien
   qu'une réécriture abîmerait (guillemet non fermé, colonnes en double, valeurs au-delà de l'en-tête) laissés tels
   quels ; parametres.csv illisible → rien d'écrit ; Windows-1252 réécrit en UTF-8 sans perte ; liste des routes
   gardées, motif de sauvegarde.
3. TestAdaptateurServeur — seul contrôle avec un navigateur (à lancer au travers du verrou) : js/stockage-serveur.js
   rend le « format » de /api/info (info()) et change un 409 « format_plus_recent » en ErreurLectureSeule.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_migration_serveur.py" -v
"""
import csv
import importlib.util
import io
import json
import os
import re
import shutil
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

from commun import (FORMAT_COURANT, FORMAT_PLUS_RECENT, RACINE, SCRIPTS_TRADUCTION, CasNavigateur, ServeurPrevo,
                    format_du_jeu)
from jeux_formats import copier_jeu

MOTIF_SAUVEGARDE_DE_FORMAT = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}_avant-format-v%d$" % FORMAT_COURANT)
MOTIF_ID_JOURNAL = re.compile(r"^J-\d{14}-[A-Z0-9]{4}$")
COLONNES_JOURNAL = ["id", "date_heure", "poste", "profil", "table", "id_ligne", "action"]
# Colonnes que chaque format ajoute en fin de table (js/schema.js, depuisVersion ; note de conception du format 4,
# §2.1), avec leur valeur par défaut ; formats des fichiers des jeux (une base 3.x : versions 1.2 à 2.1).
AJOUTS_PAR_FORMAT = {
    2: {"equipements": [("valeur_remplacement", "")],
        "demandes": [("symptome_code", ""), ("ot_origine_id", "")],
        "ordres_travail": [("anomalie_constatee", "0")]},
    3: {"ordres_travail": [("astuce", "")]},
    4: {"equipements": [("cout_arret_h", "")],
        "ordres_travail": [("habilitation_requise", "")],
        "habilitations": [("recyclage_mois", ""), ("justificatif", ""), ("catalogue_id", ""), ("nature_source", "")],
        "controles_reglementaires": [("source_periodicite", "saisie"), ("nature_source", ""), ("catalogue_id", ""),
                                     ("catalogue_relu_le", "")]},
}
ORDRE_DES_TABLES = ("equipements", "demandes", "ordres_travail", "habilitations", "controles_reglementaires")
FORMATS_DE_F1 = {"equipements": 1, "demandes": 1, "ordres_travail": 1}
FORMATS_D_UNE_BASE_3 = {"equipements": 3, "ordres_travail": 3, "habilitations": 3, "controles_reglementaires": 3}
FORMATS_DE_F2 = dict(FORMATS_D_UNE_BASE_3, ordres_travail=2)     # f2-v1.1.0 et melange : ordres_travail sans astuce
CLES_DE_L_ETAT = {"base", "courant", "plus_recent", "migration", "tables_abimees", "tables_vides", "table_bloquee",
                  "abimes_depuis"}          # T206 : {table: date} de donnees/fichiers-abimes.json

# Reprise des observations en réserves (D183, CS170) : reserves_controle.csv, ses colonnes (note de conception du
# format 4, §2.2), le commentaire fixe des réserves reprises levées, et les réserves attendues des jeux, recopiées de
# tests/fixtures/formats/LISEZMOI.md : (id, controle_id, date_controle, texte, levee). Les jeux tirés des démos
# (f2-v1.1.0, f3-v1.2.0, f3-v2.0.0 et leurs variantes) ont le même seul contrôle à observations que f3-v2.1.0.
TABLE_RESERVES = "reserves_controle"
RESERVES = TABLE_RESERVES + ".csv"
BOM = b"\xef\xbb\xbf"
COLONNES_RESERVES = ["id", "controle_id", "date_controle", "texte", "gravite", "echeance_levee", "levee", "date_levee",
                     "commentaire_levee", "ot_id"]
COMMENTAIRE_LEVEE_REPRISE = "levée avant la 2.2, date inconnue"
RESERVES_DU_LISEZMOI = {
    "reserves-a-reprendre": [
        ("RES-00001", "CTR-0001", "2026-02-10", "Garde-corps de la passerelle desserré", "0"),
        ("RES-00002", "CTR-0001", "2026-02-10", "Fin de course haut à régler", "0"),
        ("RES-00003", "CTR-0001", "2026-02-10", "Câble de levage : un toron cassé", "0"),
        ("RES-00004", "CTR-0002", "2026-03-18", "Klaxon de recul inaudible", "1"),
        ("RES-00005", "CTR-0002", "2026-03-18", "Ceinture du siège conducteur usée", "1"),
        ("RES-00006", "CTR-0005", "2026-03-24", "- Raccord de la vanne 3 suintant", "0"),
        ("RES-00007", "CTR-0005", "2026-03-24", "= Pression basse à surveiller", "0"),
        ("RES-00008", "CTR-0005", "2026-03-24", "- Étiquette du fluide illisible", "0"),
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
MOTIF_DEBUT_DANGEREUX = re.compile(r"^[=+\-@\t\r]")       # js/donnees.js : cellule texte écrite après une apostrophe
MOTIF_A_GUILLEMETER = re.compile(r'[;"\r\n]|^[ \t]|[ \t]$')     # celluleCsv de js/donnees.js


def ligne_reprise(identifiant, controle_id, date_controle, texte, levee):
    """Cellules (telles que dans le fichier) d'une réserve reprise : texte écrit comme un champ texte (« - … »
    devient « '- … ») ; gravité, échéance, date de levée et OT vides ; commentaire fixe seulement si levée."""
    cellule_texte = "'" + texte if MOTIF_DEBUT_DANGEREUX.match(texte) else texte
    return [identifiant, controle_id, date_controle, cellule_texte, "", "", levee, "",
            COMMENTAIRE_LEVEE_REPRISE if levee == "1" else "", ""]


UNE_RESERVE = [ligne_reprise(*r) for r in RESERVES_DU_LISEZMOI["f3-v2.1.0"]]
QUINZE_RESERVES = [ligne_reprise(*r) for r in RESERVES_DU_LISEZMOI["reserves-a-reprendre"]]
RESERVES_DES_JEUX = {"f2-v1.1.0": UNE_RESERVE, "melange": UNE_RESERVE, "f3-v1.2.0": UNE_RESERVE,
                     "f3-v2.0.0": UNE_RESERVE, "f3-v2.1.0": UNE_RESERVE, "reserves-a-reprendre": QUINZE_RESERVES}


def ajouts_depuis(formats_des_tables):
    """{table: [(colonne, défaut)]} des colonnes que le passage au format courant ajoute à chaque table d'après le
    format de son fichier, dans l'ordre du schéma (tables sans colonne à ajouter omises)."""
    ajouts = {}
    for table in ORDRE_DES_TABLES:
        if table in formats_des_tables:
            colonnes = [ajout for format_ in range(formats_des_tables[table] + 1, FORMAT_COURANT + 1)
                        for ajout in AJOUTS_PAR_FORMAT[format_].get(table, [])]
            if colonnes:
                ajouts[table] = colonnes
    return ajouts


def passages(depuis):
    """Lignes de journal « passage au format N du fichier » des étapes, de « depuis » au format courant."""
    return ["passage au format %d du fichier" % format_ for format_ in range(depuis, FORMAT_COURANT + 1)]


def noms_de_fichiers(tables):
    """« a.csv, b.csv », comme la console du serveur."""
    return ", ".join(table + ".csv" for table in tables)


def octets_csv(entete, lignes):
    """Octets d'un CSV écrit comme Prévo l'écrit (§3.1) : BOM, « ; », CRLF après chaque ligne ; cellule entre
    guillemets (doublés dedans) si elle contient « ; », « " », CR ou LF, ou commence ou finit par une espace ou une
    tabulation."""
    def cellule(texte):
        return '"' + texte.replace('"', '""') + '"' if MOTIF_A_GUILLEMETER.search(texte) else texte
    return BOM + "".join(";".join(cellule(c) for c in ligne) + "\r\n" for ligne in [entete] + list(lignes)).encode("utf-8")


def charger_serveur():
    """serveur.py importé comme module (le serveur lancé par ServeurPrevo est un autre processus)."""
    specification = importlib.util.spec_from_file_location("serveur_prevo_t185", RACINE / "serveur.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


SERVEUR = charger_serveur()


# ---------------------------------------------------------------------------
# Lecture des fichiers (comme Excel ou un autre poste : cellules brutes)
# ---------------------------------------------------------------------------

def lire_table(octets):
    """(en-tête, lignes) d'un CSV : BOM retiré, UTF-8 sinon Windows-1252, « ; », lignes blanches ignorées."""
    if octets.startswith(b"\xef\xbb\xbf"):
        octets = octets[3:]
    try:
        texte = octets.decode("utf-8")
    except UnicodeDecodeError:
        texte = octets.decode("cp1252")
    lignes = [ligne for ligne in csv.reader(io.StringIO(texte, newline=""), delimiter=";")
              if any(cellule.strip() for cellule in ligne)]
    return (lignes[0], lignes[1:]) if lignes else ([], [])


def fichiers_de(dossier):
    """{chemin relatif: octets} de tous les fichiers du dossier."""
    dossier = Path(dossier)
    return {p.relative_to(dossier).as_posix(): p.read_bytes() for p in sorted(dossier.rglob("*")) if p.is_file()}


# T187 (D170) : à son premier démarrage sur ces jeux (aucune version de Prévo notée), le serveur fait aussi la
# sauvegarde « avant-mise-a-jour » (et écrit derniere-version.json) et la sauvegarde du jour (AAAA-MM-JJ), vérifiées
# par tests/test_sauvegardes_socle.py ; chaque sauvegarde a son manifeste.json.
MOTIF_SAUVEGARDE_DU_DEMARRAGE = re.compile(r"^sauvegardes/\d{4}-\d{2}-\d{2}(_\d{6}_avant-mise-a-jour)?/")


def sans_le_demarrage(fichiers):
    """Les fichiers (fichiers_de) sans ce que T187 ajoute au démarrage : derniere-version.json, les sauvegardes du jour
    et « avant-mise-a-jour » ; ni fichiers-abimes.json (T206, écrit quand une table est abîmée)."""
    return {chemin: octets for chemin, octets in fichiers.items()
            if chemin not in ("derniere-version.json", "fichiers-abimes.json")
            and not MOTIF_SAUVEGARDE_DU_DEMARRAGE.match(chemin)}


def sauvegardes_de_format(dossier):
    dossier = Path(dossier) / "sauvegardes"
    if not dossier.is_dir():
        return []
    return sorted(p.name for p in dossier.iterdir() if MOTIF_SAUVEGARDE_DE_FORMAT.match(p.name))


def version_schema(octets):
    entete, lignes = lire_table(octets)
    for ligne in lignes:
        valeurs = dict(zip(entete, ligne))
        if valeurs.get("cle", "").strip() == "version_schema":
            return valeurs.get("valeur", "")
    return None


def lignes_de_journal_du_format(octets):
    """Lignes (dict) du journal qui concernent parametres.version_schema."""
    if octets is None:
        return []
    entete, lignes = lire_table(octets)
    return [dict(zip(entete, ligne)) for ligne in lignes
            if dict(zip(entete, ligne)).get("table") == "parametres"
            and dict(zip(entete, ligne)).get("id_ligne") == "version_schema"]


def actions_ajoutees(avant, apres):
    """Actions des lignes de journal du format ajoutées à journal.csv (octets avant, octets après ; None : absent)."""
    return [ligne["action"] for ligne in lignes_de_journal_du_format(apres)[len(lignes_de_journal_du_format(avant)):]]


def requete(serveur, methode, chemin, corps=b"", entetes=None):
    """(statut, objet JSON ou octets) d'une requête au serveur de test ; X-Prevo pour PUT et POST."""
    entetes = dict(entetes or {})
    if methode in ("PUT", "POST"):
        entetes.setdefault("X-Prevo", "1")
    demande = urllib.request.Request(serveur.url + chemin, data=corps if methode in ("PUT", "POST") else None,
                                     method=methode, headers=entetes)
    try:
        with urllib.request.urlopen(demande, timeout=10) as reponse:
            statut, octets, type_contenu = reponse.status, reponse.read(), reponse.headers.get("Content-Type", "")
    except urllib.error.HTTPError as erreur:
        statut, octets, type_contenu = erreur.code, erreur.read(), erreur.headers.get("Content-Type", "")
    return statut, json.loads(octets.decode("utf-8")) if "json" in type_contenu else octets


# ---------------------------------------------------------------------------
# 1. Serveur réel
# ---------------------------------------------------------------------------

class CasJeux(unittest.TestCase):

    def setUp(self):
        self.temporaire = Path(tempfile.mkdtemp(prefix="prevo-t185-"))
        self.addCleanup(shutil.rmtree, self.temporaire, True)

    def jeu(self, nom, sous_dossier="donnees"):
        return copier_jeu(nom, self.temporaire / sous_dossier / "donnees")

    def info_format(self, serveur, entetes=None):
        statut, donnees = requete(serveur, "GET", "/api/info", entetes=entetes)
        self.assertEqual(statut, 200, donnees)
        self.assertEqual(set(donnees["format"]), CLES_DE_L_ETAT)
        self.assertIn(donnees["format"]["migration"], SERVEUR.MIGRATIONS_DU_FORMAT)
        return donnees["format"]

    def verifier_table_completee(self, nom, avant, apres, ajouts):
        """Les colonnes d'origine et leurs cellules intactes (champ à champ), les colonnes du format en fin d'en-tête
        avec leur valeur par défaut dans chaque ligne."""
        entete_avant, lignes_avant = lire_table(avant)
        entete_apres, lignes_apres = lire_table(apres)
        self.assertEqual(entete_apres, entete_avant + [colonne for colonne, _ in ajouts], nom)
        self.assertEqual(len(lignes_apres), len(lignes_avant), nom)
        largeur = len(entete_avant)
        for numero, (ligne_avant, ligne_apres) in enumerate(zip(lignes_avant, lignes_apres), 2):
            attendue = (ligne_avant + [""] * largeur)[:largeur] + [defaut for _, defaut in ajouts]
            self.assertEqual(ligne_apres, attendue, "%s, ligne %d" % (nom, numero))
        self.assertTrue(apres.startswith(b"\xef\xbb\xbf"), nom)

    def verifier_reserves(self, octets, attendues):
        """reserves_controle.csv : en-tête du format 4, réserves attendues (cellules), octets écrits comme Prévo les
        écrit (BOM, « ; », CRLF, guillemets)."""
        self.assertIsNotNone(octets, RESERVES + " absent")
        self.assertEqual(lire_table(octets), (COLONNES_RESERVES, attendues))
        self.assertEqual(octets, octets_csv(COLONNES_RESERVES, attendues))

    def verifier_migration(self, nom_jeu, formats, actions, version_avant, sous_dossier="donnees"):
        """Passage d'un jeu au format courant au démarrage d'un serveur réel, puis second démarrage sans effet.
        formats : formats des fichiers que le passage complète (ajouts_depuis) ; actions : lignes de journal attendues,
        sans la suite « ; sauvegarde … faite juste avant » ; réserves attendues : RESERVES_DES_JEUX (aucune : jamais
        créé)."""
        ajouts = ajouts_depuis(formats)
        reserves = RESERVES_DES_JEUX.get(nom_jeu, [])
        source = self.jeu(nom_jeu, sous_dossier)
        origine = fichiers_de(source)
        self.assertNotIn(RESERVES, origine)
        with ServeurPrevo(source=source) as serveur:
            apres = fichiers_de(serveur.dossier)
            etat = self.info_format(serveur)
            console = serveur.sortie_console()
            copie = self.temporaire / sous_dossier / "apres"
            shutil.copytree(serveur.dossier, copie)
        self.assertEqual(etat, {"base": FORMAT_COURANT, "courant": FORMAT_COURANT, "plus_recent": False,
                                "migration": "faite", "tables_abimees": [], "tables_vides": [], "table_bloquee": None,
                                "abimes_depuis": {}})
        # La sauvegarde « avant-format-vN » d'abord : aux octets d'origine (données, et acces/ depuis T187).
        sauvegardes = sauvegardes_de_format(copie)
        self.assertEqual(len(sauvegardes), 1, sauvegardes)
        sauvegarde = sauvegardes[0]
        contenu = {chemin.split("/", 2)[2]: octets for chemin, octets in apres.items()
                   if chemin.startswith("sauvegardes/" + sauvegarde + "/")}
        self.assertIn("manifeste.json", contenu)                        # T187 : chaque sauvegarde a son manifeste
        del contenu["manifeste.json"]
        self.assertEqual(contenu, {chemin: octets for chemin, octets in origine.items()
                                   if chemin.endswith(".csv") or chemin.startswith("acces/")})
        # Les tables complétées, les réserves reprises, version_schema, le journal ; tout le reste à l'octet près ;
        # aucune autre table créée.
        for table, colonnes in ajouts.items():
            self.verifier_table_completee(table, origine[table + ".csv"], apres[table + ".csv"], colonnes)
        if reserves:
            self.verifier_reserves(apres.get(RESERVES), reserves)
        else:
            self.assertNotIn(RESERVES, apres)
        self.assertEqual(version_schema(origine["parametres.csv"]), version_avant)
        self.assertEqual(version_schema(apres["parametres.csv"]), "'%d" % FORMAT_COURANT)
        avant_p, apres_p = lire_table(origine["parametres.csv"]), lire_table(apres["parametres.csv"])
        self.assertEqual(apres_p[0], avant_p[0])
        self.assertEqual([l for l in apres_p[1] if l[0] != "version_schema"],
                         [l for l in avant_p[1] if l[0] != "version_schema"])
        journal_avant = origine.get("journal.csv")
        journal = apres["journal.csv"]
        if journal_avant is not None:
            self.assertTrue(journal.startswith(journal_avant), "lignes ajoutées en fin, le reste à l'octet près")
        self.assertEqual(lire_table(journal)[0], COLONNES_JOURNAL)
        lignes = lignes_de_journal_du_format(journal)[len(lignes_de_journal_du_format(journal_avant)):]
        suite = " ; sauvegarde %s faite juste avant" % sauvegarde
        self.assertEqual([ligne["action"] for ligne in lignes], [action + suite for action in actions])
        for ligne in lignes:
            self.assertRegex(ligne["id"], MOTIF_ID_JOURNAL)
            self.assertRegex(ligne["date_heure"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
        crees = {RESERVES} if reserves else set()
        changes = set(ajouts) | {"journal", "parametres"} | ({TABLE_RESERVES} if reserves else set())
        donnees_apres = {c: o for c, o in sans_le_demarrage(apres).items() if "/" not in c}
        self.assertEqual(set(donnees_apres), {c for c in origine if "/" not in c} | {"journal.csv"} | crees)
        for chemin, octets in origine.items():
            if chemin[:-len(".csv")] not in changes:
                self.assertEqual(apres[chemin], octets, chemin)
        # Console : reserves_controle.csv parmi les fichiers complétés (aucun texte nouveau).
        completes = list(ajouts) + ([TABLE_RESERVES] if reserves else [])
        self.assertIn("fichiers complétés : %s." % noms_de_fichiers(completes), console)
        # Second démarrage : rien n'est écrit, aucune sauvegarde de plus.
        avant_second = fichiers_de(copie)
        with ServeurPrevo(source=copie) as second:
            self.assertEqual(fichiers_de(second.dossier), avant_second)
            self.assertEqual(self.info_format(second)["migration"], "rien")
        return sauvegarde


class TestDemarrage(CasJeux):

    def test_f1_passe_au_format_courant_puis_second_demarrage_sans_effet(self):
        self.verifier_migration("f1", FORMATS_DE_F1, passages(2), version_avant="'1")

    def test_f2_passe_au_format_courant_puis_second_demarrage_sans_effet(self):
        self.verifier_migration("f2-v1.1.0", FORMATS_DE_F2, passages(3), version_avant="'2")

    def test_melange_ordres_travail_complete_au_format_3_puis_passage_au_format_4(self):
        self.verifier_migration("melange", FORMATS_DE_F2,
                                ["fichiers complétés au format 3 : ordres_travail"] + passages(4), version_avant="'3")

    def test_bases_3x_passent_au_format_courant_reserves_reprises_acces_intact(self):
        self.assertIn("acces/comptes.json", fichiers_de(copier_jeu("f3-v2.0.0", self.temporaire / "sonde")))
        for nom in ("f3-v1.2.0", "f3-v2.0.0", "f3-v2.1.0", "reserves-a-reprendre"):
            with self.subTest(jeu=nom):
                self.verifier_migration(nom, FORMATS_D_UNE_BASE_3, passages(4), version_avant="'3", sous_dossier=nom)

    def test_entete_tronque_et_vide_non_reecrits_signales_le_reste_passe_au_format_courant(self):
        for nom, table, cle in (("entete-tronque", "ordres_travail", "tables_abimees"),
                                ("vide", "equipements", "tables_vides")):
            with self.subTest(jeu=nom):
                source = self.jeu(nom, nom)
                origine = fichiers_de(source)
                with ServeurPrevo(source=source) as serveur:
                    apres = fichiers_de(serveur.dossier)
                    sauvegardes = sauvegardes_de_format(serveur.dossier)
                    etat = self.info_format(serveur)
                    console = serveur.sortie_console()
                self.assertEqual((etat["migration"], etat["base"], etat[cle]), ("faite", FORMAT_COURANT, [table]))
                self.assertEqual(apres[table + ".csv"], origine[table + ".csv"])
                self.assertIn(table + ".csv", console)
                self.assertEqual(len(sauvegardes), 1, sauvegardes)
                self.assertEqual(version_schema(apres["parametres.csv"]), "'%d" % FORMAT_COURANT)
                ajouts = ajouts_depuis({t: f for t, f in FORMATS_D_UNE_BASE_3.items() if t != table})
                for completee, colonnes in ajouts.items():
                    self.verifier_table_completee(completee, origine[completee + ".csv"], apres[completee + ".csv"],
                                                  colonnes)
                self.verifier_reserves(apres.get(RESERVES), UNE_RESERVE)
                self.assertIn("fichiers complétés : %s." % noms_de_fichiers(list(ajouts) + [TABLE_RESERVES]), console)
                # T206 : un en-tête tronqué est un fichier abîmé (depuis ce démarrage) ; un fichier vide ne l'est pas.
                self.assertEqual(table in etat["abimes_depuis"], cle == "tables_abimees", etat["abimes_depuis"])

    def test_base_au_format_2_avec_un_entete_tronque_le_reste_passe_au_format_courant(self):
        source = self.jeu("f2-v1.1.0")
        tronque = copier_jeu("entete-tronque", self.temporaire / "tronque") / "ordres_travail.csv"
        shutil.copyfile(tronque, source / "ordres_travail.csv")
        origine = fichiers_de(source)
        with ServeurPrevo(source=source) as serveur:
            apres = fichiers_de(serveur.dossier)
            etat = self.info_format(serveur)
            sauvegardes = sauvegardes_de_format(serveur.dossier)
        self.assertEqual((etat["migration"], etat["base"], etat["tables_abimees"]),
                         ("faite", FORMAT_COURANT, ["ordres_travail"]))
        self.assertEqual(apres["ordres_travail.csv"], origine["ordres_travail.csv"])
        self.assertEqual(version_schema(apres["parametres.csv"]), "'%d" % FORMAT_COURANT)
        self.assertEqual(len(sauvegardes), 1, sauvegardes)
        actions = [ligne["action"] for ligne in lignes_de_journal_du_format(apres["journal.csv"])]
        self.assertTrue(actions and actions[-1].startswith(passages(FORMAT_COURANT)[0] + " ; sauvegarde "), actions)
        ajouts = ajouts_depuis({t: f for t, f in FORMATS_DE_F2.items() if t != "ordres_travail"})
        for table, colonnes in ajouts.items():
            self.verifier_table_completee(table, origine[table + ".csv"], apres[table + ".csv"], colonnes)
        self.verifier_reserves(apres.get(RESERVES), UNE_RESERVE)
        for chemin, octets in origine.items():
            if chemin[:-len(".csv")] not in set(ajouts) | {"parametres", "journal"}:
                self.assertEqual(apres[chemin], octets, chemin)

    def test_plus_recent_lecture_seule_ecritures_refusees_409(self):
        source = self.jeu("plus-recent")
        origine = fichiers_de(source)
        with ServeurPrevo(source=source) as serveur:
            self.assertEqual(sans_le_demarrage(fichiers_de(serveur.dossier)), origine)
            etat = self.info_format(serveur)
            self.assertEqual((etat["base"], etat["plus_recent"], etat["migration"]),
                             (format_du_jeu("plus-recent"), True, "rien"))
            self.assertIn("LECTURE SEULE", serveur.sortie_console())
            # Lecture permise.
            statut, octets = requete(serveur, "GET", "/api/csv/equipements")
            self.assertEqual((statut, octets), (200, origine["equipements.csv"]))
            # Écritures refusées : 409 « format_plus_recent », message clair.
            ecritures = [
                ("PUT", "/api/csv/equipements", origine["equipements.csv"], {"X-Version-Attendue": "aucune"}),
                ("PUT", "/api/csv/equipements", b"", {}),
                ("POST", "/api/csv/journal/ajout", "id;date_heure;poste;profil;table;id_ligne;action\r\n"
                 "J-1;2026-11-04 10:00;P;;t;i;a\r\n".encode("utf-8"), {}),
                ("PUT", "/api/documents/x.pdf", b"%PDF-1.4\n", {"Content-Type": "application/pdf"}),
                ("POST", "/api/restauration", json.dumps({"sauvegarde": "2026-01-01"}).encode("utf-8"),
                 {"Content-Type": "application/json"}),
            ]
            for methode, chemin, corps, entetes in ecritures:
                with self.subTest(methode=methode, chemin=chemin):
                    statut, reponse = requete(serveur, methode, chemin, corps, entetes)
                    self.assertEqual(statut, 409, reponse)
                    self.assertEqual(reponse["code"], "format_plus_recent")
                    self.assertEqual(reponse["format"], format_du_jeu("plus-recent"))
                    self.assertIn("version plus récente de Prévo", reponse["erreur"])
                    self.assertIn("format %d" % format_du_jeu("plus-recent"), reponse["erreur"])
            self.assertEqual(sans_le_demarrage(fichiers_de(serveur.dossier)), origine)
            self.assertEqual(os.listdir(serveur.dossier / "documents"), [])
            # Sauvegarde manuelle permise ; les données restent intactes.
            statut, reponse = requete(serveur, "POST", "/api/sauvegarde")
            self.assertEqual(statut, 200, reponse)
            donnees = {c: o for c, o in sans_le_demarrage(fichiers_de(serveur.dossier)).items()
                       if not c.startswith("sauvegardes/")}
            self.assertEqual(donnees, origine)

    def test_comptes_exiges_passage_fait_sans_aucune_connexion(self):
        source = self.jeu("f3-v2.0.0")
        origine = fichiers_de(source)
        with ServeurPrevo(source=source, comptes=True) as serveur:
            # Aucune connexion n'a eu lieu : le passage est déjà fait sur le disque.
            apres = fichiers_de(serveur.dossier)
            self.assertEqual(version_schema(apres["parametres.csv"]), "'%d" % FORMAT_COURANT)
            self.assertEqual(len(sauvegardes_de_format(serveur.dossier)), 1)
            for table, colonnes in ajouts_depuis(FORMATS_D_UNE_BASE_3).items():
                self.verifier_table_completee(table, origine[table + ".csv"], apres[table + ".csv"], colonnes)
            self.verifier_reserves(apres.get(RESERVES), UNE_RESERVE)
            statut, _ = requete(serveur, "GET", "/api/info")
            self.assertEqual(statut, 401)                               # /api/info n'est pas publique
            etat = self.info_format(serveur, {"Cookie": serveur.session("responsable")})
            self.assertEqual(etat["migration"], "faite")
            journal = lignes_de_journal_du_format(apres["journal.csv"])
            self.assertTrue(journal[-1]["action"].startswith(passages(FORMAT_COURANT)[0] + " ; sauvegarde "))
            self.assertEqual(journal[-1]["poste"], "Serveur Prévo")


# ---------------------------------------------------------------------------
# 2. Cas limites : la fonction du module sur une copie
# ---------------------------------------------------------------------------

class TestCasLimites(CasJeux):

    def migrer(self, dossier, creer=True):
        """migrer_donnees_au_demarrage sur ce dossier ; rend (état, lignes de la console)."""
        config = SERVEUR.Configuration(str(dossier), [])
        if creer:
            SERVEUR.creer_dossiers(config)
        messages = []
        with mock.patch.object(SERVEUR, "afficher", side_effect=messages.append):
            etat = SERVEUR.migrer_donnees_au_demarrage(config)
        self.assertIs(config.format_donnees, etat)
        return etat, messages

    def test_sauvegarde_impossible_rien_n_est_ecrit(self):
        dossier = self.jeu("f2-v1.1.0")
        (dossier / "documents").mkdir()
        (dossier / "sauvegardes").write_bytes(b"un fichier a la place du dossier des sauvegardes")
        origine = fichiers_de(dossier)
        etat, messages = self.migrer(dossier, creer=False)
        self.assertEqual(fichiers_de(dossier), origine)
        self.assertEqual((etat["migration"], etat["base"]), ("impossible", 2))
        self.assertTrue(any("sauvegarde « avant-format-v%d » n'a pas pu être faite" % FORMAT_COURANT in m
                            for m in messages), messages)
        self.assertTrue(any("Rien n'a été écrit" in m for m in messages), messages)

    @unittest.skipUnless(os.name == "nt", "verrou d'un fichier ouvert : Windows (comme Excel)")
    def test_fichier_tenu_par_un_autre_programme_arret_propre_puis_reprise(self):
        dossier = self.jeu("f1")
        origine = fichiers_de(dossier)
        ajouts = ajouts_depuis(FORMATS_DE_F1)
        with open(dossier / "ordres_travail.csv", "rb"):                    # comme Excel : remplacement refusé
            etat, messages = self.migrer(dossier)
        self.assertEqual((etat["migration"], etat["table_bloquee"], etat["base"]), ("incomplete", "ordres_travail", 1))
        self.assertTrue(any("Fermez Excel" in m and "ordres_travail.csv" in m for m in messages), messages)
        apres = fichiers_de(dossier)
        self.assertEqual(apres["ordres_travail.csv"], origine["ordres_travail.csv"])
        self.assertEqual(apres["parametres.csv"], origine["parametres.csv"])      # version_schema pas avancé
        self.assertNotIn("journal.csv", apres)
        for table in ("equipements", "demandes"):                                 # écrits en entier, d'un coup
            self.verifier_table_completee(table, origine[table + ".csv"], apres[table + ".csv"], ajouts[table])
        self.assertEqual(len(sauvegardes_de_format(dossier)), 1)
        # Démarrage suivant, Excel fermé : le passage reprend et se termine.
        etat, _ = self.migrer(dossier)
        self.assertEqual((etat["migration"], etat["base"], etat["table_bloquee"]), ("faite", FORMAT_COURANT, None))
        fin = fichiers_de(dossier)
        self.verifier_table_completee("ordres_travail", origine["ordres_travail.csv"], fin["ordres_travail.csv"],
                                      ajouts["ordres_travail"])
        for table in ("equipements", "demandes"):
            self.assertEqual(fin[table + ".csv"], apres[table + ".csv"])
        self.assertEqual(version_schema(fin["parametres.csv"]), "'%d" % FORMAT_COURANT)
        self.assertNotIn(RESERVES, fin)                                           # f1 : aucun contrôle
        sauvegardes = sauvegardes_de_format(dossier)
        self.assertEqual(len(sauvegardes), 2, sauvegardes)
        self.assertEqual(actions_ajoutees(None, fin["journal.csv"]),
                         ["%s ; sauvegarde %s faite juste avant" % (passage, sauvegardes[-1])
                          for passage in passages(2)])
        # Et le suivant n'écrit plus rien.
        etat, _ = self.migrer(dossier)
        self.assertEqual(etat["migration"], "rien")
        self.assertEqual(fichiers_de(dossier), fin)

    @unittest.skipUnless(os.name == "nt", "verrou d'un fichier ouvert : Windows (comme Excel)")
    def test_reserves_controle_tenu_par_un_autre_programme_puis_libere_reprise_sans_doublon(self):
        """Une réserve créée dans la 2.2 avant la reprise (CTR-0001, RES-00007) : son contrôle la garde et ne reçoit
        rien, les autres sont repris à la suite de son numéro. reserves_controle.csv tenu (Excel) : passage
        incomplet, version_schema pas avancé, rien au journal ; libéré : reprise faite au démarrage suivant, une fois."""
        dossier = self.jeu("reserves-a-reprendre")
        existante = ["RES-00007", "CTR-0001", "2026-02-10", "Garde-corps resserré, à revoir", "", "", "0", "", "", ""]
        (dossier / RESERVES).write_bytes(octets_csv(COLONNES_RESERVES, [existante]))
        origine = fichiers_de(dossier)
        ajouts = ajouts_depuis(FORMATS_D_UNE_BASE_3)
        with open(dossier / RESERVES, "rb"):                                       # comme Excel : remplacement refusé
            etat, messages = self.migrer(dossier)
        self.assertEqual((etat["migration"], etat["table_bloquee"], etat["base"]), ("incomplete", TABLE_RESERVES, 3))
        self.assertTrue(any("Fermez Excel" in m and RESERVES + " ne peut pas" in m
                            and "déjà complétés : %s)" % noms_de_fichiers(ajouts) in m for m in messages), messages)
        apres = fichiers_de(dossier)
        for chemin in (RESERVES, "parametres.csv", "journal.csv"):
            self.assertEqual(apres[chemin], origine[chemin], chemin)
        for table, colonnes in ajouts.items():                                    # écrites avant, en entier
            self.verifier_table_completee(table, origine[table + ".csv"], apres[table + ".csv"], colonnes)
        self.assertEqual(len(sauvegardes_de_format(dossier)), 1)
        # Démarrage suivant, Excel fermé : les tables déjà au format ne sont pas réécrites, la reprise se fait.
        etat, messages = self.migrer(dossier)
        self.assertEqual((etat["migration"], etat["base"], etat["table_bloquee"]), ("faite", FORMAT_COURANT, None))
        fin = fichiers_de(dossier)
        reprises = [reserve for reserve in RESERVES_DU_LISEZMOI["reserves-a-reprendre"] if reserve[1] != "CTR-0001"]
        self.verifier_reserves(fin[RESERVES], [existante] + [ligne_reprise("RES-%05d" % numero, *reserve[1:])
                                                             for numero, reserve in enumerate(reprises, 8)])
        for table in ajouts:
            self.assertEqual(fin[table + ".csv"], apres[table + ".csv"], table)
        self.assertEqual(version_schema(fin["parametres.csv"]), "'%d" % FORMAT_COURANT)
        sauvegardes = sauvegardes_de_format(dossier)
        self.assertEqual(len(sauvegardes), 2, sauvegardes)
        self.assertTrue(any("fichiers complétés : %s." % RESERVES in m for m in messages), messages)
        self.assertEqual(actions_ajoutees(origine["journal.csv"], fin["journal.csv"]),
                         ["%s ; sauvegarde %s faite juste avant" % (passage, sauvegardes[-1])
                          for passage in passages(4)])
        # Et le suivant n'écrit plus rien.
        etat, _ = self.migrer(dossier)
        self.assertEqual(etat["migration"], "rien")
        self.assertEqual(fichiers_de(dossier), fin)

    @unittest.skipUnless(os.name == "nt", "verrou d'un fichier ouvert : Windows (comme Excel)")
    def test_parametres_tenu_apres_la_reprise_aucun_doublon_au_demarrage_suivant(self):
        dossier = self.jeu("reserves-a-reprendre")
        origine = fichiers_de(dossier)
        with open(dossier / "parametres.csv", "rb"):                              # comme Excel : remplacement refusé
            etat, messages = self.migrer(dossier)
        self.assertEqual((etat["migration"], etat["table_bloquee"], etat["base"]), ("incomplete", "parametres", 3))
        self.assertTrue(any("Fermez Excel" in m and "parametres.csv ne peut pas" in m and RESERVES + ")" in m
                            for m in messages), messages)
        apres = fichiers_de(dossier)
        self.verifier_reserves(apres.get(RESERVES), QUINZE_RESERVES)                # 3 bis avant 4
        self.assertEqual(apres["parametres.csv"], origine["parametres.csv"])
        self.assertEqual(apres["journal.csv"], origine["journal.csv"])
        # Démarrage suivant : la reprise rejouée ne donne rien de plus ; version_schema écrit, une ligne de journal.
        etat, _ = self.migrer(dossier)
        self.assertEqual((etat["migration"], etat["base"], etat["table_bloquee"]), ("faite", FORMAT_COURANT, None))
        fin = fichiers_de(dossier)
        self.assertEqual(fin[RESERVES], apres[RESERVES])
        for table in ajouts_depuis(FORMATS_D_UNE_BASE_3):
            self.assertEqual(fin[table + ".csv"], apres[table + ".csv"], table)
        self.assertEqual(version_schema(fin["parametres.csv"]), "'%d" % FORMAT_COURANT)
        sauvegardes = sauvegardes_de_format(dossier)
        self.assertEqual(len(sauvegardes), 2, sauvegardes)
        self.assertEqual(actions_ajoutees(origine["journal.csv"], fin["journal.csv"]),
                         ["%s ; sauvegarde %s faite juste avant" % (passage, sauvegardes[-1])
                          for passage in passages(4)])

    def test_controles_ou_reserves_abimes_rien_n_est_repris(self):
        """controles_reglementaires abîmé (laissé tel quel), reserves_controle abîmé ou à l'en-tête illisible : aucune
        réserve reprise, le fichier gardé à l'octet ; le reste passe au format courant."""
        controles = (copier_jeu("reserves-a-reprendre", self.temporaire / "sonde") / "controles_reglementaires.csv")
        entete = ";".join(COLONNES_RESERVES).encode("utf-8")
        cas = {
            "controles-abimes": ("controles_reglementaires.csv",
                                 controles.read_bytes() + b'CTR-9999;"jamais ferm\xc3\xa9\r\n'),
            "reserves-abimees": (RESERVES, BOM + entete + b'\r\nRES-00001;CTR-0001;;"jamais ferm\xc3\xa9\r\n'),
            "reserves-entete-illisible": (RESERVES, BOM + b"id;texte\r\nRES-00001;Garde-corps\r\n"),
        }
        for nom, (fichier, octets) in cas.items():
            with self.subTest(cas=nom):
                dossier = self.jeu("reserves-a-reprendre", nom)
                (dossier / fichier).write_bytes(octets)
                etat, _ = self.migrer(dossier)
                self.assertEqual((etat["migration"], etat["base"]), ("faite", FORMAT_COURANT))
                self.assertEqual((dossier / fichier).read_bytes(), octets)
                if fichier != RESERVES:
                    self.assertEqual(etat["tables_abimees"], ["controles_reglementaires"])
                    self.assertFalse((dossier / RESERVES).exists())
                self.assertEqual(version_schema((dossier / "parametres.csv").read_bytes()), "'%d" % FORMAT_COURANT)

    def test_base_au_format_courant_dont_les_controles_sont_revenus_au_format_3(self):
        """Base au format courant dont controles_reglementaires.csv est remplacé par sa copie au format 3 (copie de
        fichier, restauration partielle) : colonnes complétées ; reprise seulement pour les contrôles sans réserve
        (réserves gardées : rien de plus ; reserves_controle.csv supprimé : recréé) ; journal et console « fichiers
        complétés au format 4 : … », version_schema inchangé."""
        dossier = self.jeu("f3-v2.1.0")
        controles_au_format_3 = (dossier / "controles_reglementaires.csv").read_bytes()
        self.migrer(dossier)
        au_format = fichiers_de(dossier)
        self.verifier_reserves(au_format.get(RESERVES), UNE_RESERVE)
        for supprimer, completes in ((False, ["controles_reglementaires"]),
                                     (True, ["controles_reglementaires", TABLE_RESERVES])):
            with self.subTest(reserves_supprimees=supprimer):
                (dossier / "controles_reglementaires.csv").write_bytes(controles_au_format_3)
                if supprimer:
                    (dossier / RESERVES).unlink()
                avant = fichiers_de(dossier)
                etat, messages = self.migrer(dossier)
                apres = fichiers_de(dossier)
                self.assertEqual((etat["migration"], etat["base"]), ("faite", FORMAT_COURANT))
                self.assertEqual(apres["controles_reglementaires.csv"], au_format["controles_reglementaires.csv"])
                self.assertEqual(apres[RESERVES], au_format[RESERVES])
                self.assertEqual(apres["parametres.csv"], avant["parametres.csv"])
                nom = sauvegardes_de_format(dossier)[-1]
                self.assertTrue(any("fichiers complétés au format %d : %s (sauvegarde %s faite juste avant)"
                                    % (FORMAT_COURANT, noms_de_fichiers(completes), nom) in m for m in messages),
                                messages)
                self.assertEqual(actions_ajoutees(avant["journal.csv"], apres["journal.csv"]),
                                 ["fichiers complétés au format %d : %s ; sauvegarde %s faite juste avant"
                                  % (FORMAT_COURANT, ", ".join(completes), nom)])

    def test_format_ancien_qu_une_reecriture_abimerait_laisse_tel_quel(self):
        ordres = (RACINE / "tests" / "fixtures" / "formats" / "f2-v1.1.0" / "ordres_travail.csv").read_bytes()
        entete, reste = ordres.split(b"\r\n", 1)
        cas = {
            "guillemet non fermé": ordres + b'OT-9999;"jamais ferm\xc3\xa9\r\n',
            "colonnes en double": entete + b";titre\r\n" + reste,
            "valeurs au-delà de l'en-tête": ordres + b"OT-9998" + b";" * entete.count(b";") + b";en trop\r\n",
        }
        for nom, octets in cas.items():
            with self.subTest(cas=nom):
                dossier = self.jeu("f2-v1.1.0", nom.replace(" ", "-").replace("'", ""))
                (dossier / "ordres_travail.csv").write_bytes(octets)
                etat, messages = self.migrer(dossier)
                self.assertEqual(etat["tables_abimees"], ["ordres_travail"])
                self.assertEqual((etat["migration"], etat["base"]), ("faite", FORMAT_COURANT))
                self.assertEqual((dossier / "ordres_travail.csv").read_bytes(), octets)
                self.assertTrue(any("ordres_travail.csv laissé tel quel" in m for m in messages), messages)

    def test_parametres_qui_ne_se_reecrit_pas_sans_perte_rien_n_est_ecrit(self):
        dossier = self.jeu("f2-v1.1.0")
        parametres = (dossier / "parametres.csv").read_bytes() + b"cle_maison;valeur;en trop\r\n"
        (dossier / "parametres.csv").write_bytes(parametres)
        origine = fichiers_de(dossier)
        etat, messages = self.migrer(dossier)
        self.assertEqual((etat["migration"], etat["tables_abimees"]), ("impossible", ["parametres"]))
        self.assertEqual({c: o for c, o in fichiers_de(dossier).items()}, origine)
        self.assertEqual(sauvegardes_de_format(dossier), [])
        self.assertTrue(any("parametres.csv ne se réécrit pas sans perte" in m for m in messages), messages)

    def test_windows_1252_reecrit_en_utf8_sans_perte(self):
        dossier = self.jeu("f2-v1.1.0")
        texte = (dossier / "ordres_travail.csv").read_bytes().decode("utf-8-sig")
        ancien = texte.encode("cp1252", errors="replace")
        (dossier / "ordres_travail.csv").write_bytes(ancien)
        etat, _ = self.migrer(dossier)
        self.assertEqual(etat["migration"], "faite")
        nouveau = (dossier / "ordres_travail.csv").read_bytes()
        nouveau.decode("utf-8")
        self.verifier_table_completee("ordres_travail", ancien, nouveau, ajouts_depuis(FORMATS_DE_F2)["ordres_travail"])

    def test_base_vide_rien(self):
        dossier = self.temporaire / "vide" / "donnees"
        dossier.mkdir(parents=True)
        etat, messages = self.migrer(dossier)
        self.assertEqual((etat["migration"], etat["base"], etat["plus_recent"]), ("rien", 1, False))
        self.assertEqual(messages, [])
        self.assertEqual(fichiers_de(dossier), {})

    def test_routes_gardees_et_motif_de_sauvegarde(self):
        self.assertIn("avant-format-v%d" % SERVEUR.VERSION_SCHEMA_CSV, SERVEUR.MOTIFS_SAUVEGARDE)
        self.assertEqual(SERVEUR.VERSION_SCHEMA_CSV, FORMAT_COURANT)
        ecritures = {route for route in SERVEUR.ROUTES_API if route[0] in ("PUT", "POST")
                     and (route[1].startswith(("csv/", "documents/")) or route[1] == "restauration")}
        self.assertEqual(set(SERVEUR.ROUTES_ECRITURE_DES_DONNEES), ecritures)
        # Hors du démarrage normal (config.format_donnees None) ou base au format : rien n'est refusé.
        config = SERVEUR.Configuration(str(self.temporaire / "x"), [])
        SERVEUR.verifier_ecriture_permise(config)
        config.format_donnees = {"base": FORMAT_PLUS_RECENT, "plus_recent": True}
        with self.assertRaises(SERVEUR.ErreurHttp) as refus:
            SERVEUR.ecrire_table(config, "parametres", ["cle", "valeur"], [])
        self.assertEqual((refus.exception.statut, refus.exception.champs_supplementaires["code"]),
                         (409, "format_plus_recent"))


# ---------------------------------------------------------------------------
# 3. L'adaptateur du navigateur (js/stockage-serveur.js) : seul contrôle avec un navigateur
# ---------------------------------------------------------------------------

# Moteur de traduction d'abord, comme dans index.html (Lot 2).
SCRIPTS_ADAPTATEUR = SCRIPTS_TRADUCTION + ["js/lib/papaparse.min.js", "js/schema.js", "js/donnees.js",
                                           "js/stockage-serveur.js"]
PAGE_VIDE_HTML = ("<!DOCTYPE html><html lang=\"fr\"><head><meta charset=\"UTF-8\">"
                  "<title>Test T185</title></head><body></body></html>")
ESSAYER_LES_ECRITURES_JS = """async () => {
  const adaptateur = StockageServeur.creer();
  const info = await adaptateur.info();
  const erreur = async (promesse) => {
    try { await promesse; return 'aucune erreur'; } catch (e) { return e.name + ' ' + e.format; }
  };
  const octets = new TextEncoder().encode('x');
  return {
    format: info.format,
    enregistrer: await erreur(adaptateur.enregistrer('equipements', octets, null)),
    ajouter: await erreur(adaptateur.ajouter('journal', octets)),
    document: await erreur(adaptateur.ecrireDocument('x.pdf', new Blob(['%PDF-1.4'], { type: 'application/pdf' }))),
    restaurer: await erreur(adaptateur.restaurer('2026-01-01')),
  };
}"""


class TestAdaptateurServeur(CasNavigateur):
    """info() rend le « format » de /api/info (T185) ; un 409 « format_plus_recent » devient ErreurLectureSeule (jamais
    un conflit à réessayer), pour les tables, l'ajout, les documents et la restauration."""

    def ouvrir(self, serveur):
        adresse = serveur.url + "/test-migration-serveur.html"
        self.page.route(adresse, lambda route: route.fulfill(
            status=200, content_type="text/html; charset=utf-8", body=PAGE_VIDE_HTML))
        self.page.goto(adresse)
        for chemin in SCRIPTS_ADAPTATEUR:
            self.page.add_script_tag(url=serveur.url + "/" + chemin)

    def test_format_lu_et_ecritures_refusees_en_lecture_seule(self):
        self.autoriser_erreur(re.compile(r"status of 409"))
        with tempfile.TemporaryDirectory(prefix="prevo-t185-") as temporaire:
            source = copier_jeu("plus-recent", Path(temporaire) / "donnees")
            with ServeurPrevo(source=source) as serveur:
                self.ouvrir(serveur)
                resultat = self.page.evaluate(ESSAYER_LES_ECRITURES_JS)
        self.assertEqual(resultat["format"], {"base": format_du_jeu("plus-recent"), "courant": FORMAT_COURANT, "plusRecent": True, "migration": "rien",
                                              "tablesAbimees": [], "tablesVides": [], "tableBloquee": None,
                                              "abimesDepuis": {}})
        for ecriture in ("enregistrer", "ajouter", "document", "restaurer"):
            self.assertEqual(resultat[ecriture], "ErreurLectureSeule %d" % format_du_jeu("plus-recent"), ecriture)

    def test_format_lu_apres_un_passage(self):
        with tempfile.TemporaryDirectory(prefix="prevo-t185-") as temporaire:
            source = copier_jeu("f1", Path(temporaire) / "donnees")
            with ServeurPrevo(source=source) as serveur:
                self.ouvrir(serveur)
                format_lu = self.page.evaluate("async () => (await StockageServeur.creer().info()).format")
        self.assertEqual(format_lu, {"base": FORMAT_COURANT, "courant": FORMAT_COURANT, "plusRecent": False,
                                     "migration": "faite", "tablesAbimees": [], "tablesVides": [], "tableBloquee": None,
                                     "abimesDepuis": {}})


if __name__ == "__main__":
    unittest.main()
