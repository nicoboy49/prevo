"""Recette du L1 « format de données 4 » (chantier 2.2, T397 ; CDC CS169, CS170 pour la reprise des observations des
contrôles en réserves, CS177 ; décision D183 ; CONCEPTION-L1 §3 ; docs/FORMAT.md §2, §5, §9). De bout en bout, comme à
l'installation de la 2.2 sur une base existante ; les tests de chaque partie (test_formats_serveur,
test_formats_navigateur, test_migration_serveur, test_formats_js, test_format4_zip) ne sont pas recopiés ici.

Chaque cas travaille sur une COPIE d'un jeu de tests/fixtures/formats/ (tests/jeux_formats.py) dans un dossier
temporaire, ou dans l'OPFS du navigateur de test : jamais de données réelles. Jeux : f1, f2-v1.1.0, f3-v1.2.0,
f3-v2.0.0, f3-v2.1.0, reserves-a-reprendre (bases des versions 1.0 à 2.1, formats 1 à 3) et f4-v2.2.0 (base déjà au
format 4 : rien à faire).

1. TestServeur (sans navigateur) — serveur.py réel (ServeurPrevo) démarré sur la copie, sans comptes ; f3-v2.0.0 aussi
   avec comptes exigés, sur SES comptes (acces/comptes.json du jeu, responsable claire.essai) : passage fait au
   démarrage, avant toute connexion (/api/info : 401 sans session), puis /api/info lu par ce compte ; octets des
   données identiques à ceux du démarrage sans comptes.
2. TestDossier (navigateur, au travers du verrou) — application entière (index.html) en mode dossier simulé (OPFS),
   profil demandeur (pas d'OT préventifs générés à l'ouverture), puis seconde ouverture ; les fichiers écrits par le
   navigateur comparés à ceux du serveur pour le même jeu.
   Pour chaque jeu et chaque mode :
     - une seule sauvegarde « AAAA-MM-JJ_HHMMSS_avant-format-v4 » (aucune pour f4-v2.2.0), aux octets d'origine (CSV,
       et acces/ en mode serveur), conforme à son manifeste.json : application, motif avant-format-v4, format
       d'origine, mode, date ; chaque fichier de la sauvegarde avec sa taille et son SHA-256, ni plus ni moins ;
     - version_schema 4 ; une ligne de journal par étape (« passage au format N du fichier ; sauvegarde … faite juste
       avant »), rien d'autre au journal, ses lignes d'origine intactes ;
     - chaque valeur existante inchangée champ à champ (même colonne, même ligne), colonnes du format 4 (et des formats
       2 et 3 pour f1 et f2) ajoutées avec leur défaut ; tables sans colonne nouvelle identiques à l'octet ; acces/
       intact ; aucune table créée sauf reserves_controle (garanties et contrats_prestataires jamais créés) ;
     - reserves_controle.csv : exactement les réserves de D183 (LISEZMOI des jeux : 1 pour les bases tirées des démos,
       15 pour reserves-a-reprendre), écrites comme Prévo les écrit ; créée seulement s'il y a des réserves (f1 : aucun
       contrôle) ; f4-v2.2.0 garde ses 3 réserves à l'octet ;
     - seconde ouverture (dossier) ou second démarrage (serveur) : aucun octet écrit (verrou.txt mis à part) ;
     - octets du navigateur égaux à ceux du serveur, CSV par CSV (journal : mêmes lignes ajoutées, identifiant, heure,
       poste et nom de la sauvegarde mis à part). Un seul écart, connu et documenté (écart A de test_formats_serveur,
       décision T382 : Donnees.csv.serialiser non touché au L1) : dans controles_reglementaires.csv de
       reserves-a-reprendre, la colonne inconnue remarque_maison est écrite en fin par le navigateur, avant les
       colonnes du format 4 par le serveur ; mêmes cellules sous les mêmes colonnes, rien d'autre ne diffère ;
     - navigateur : aucune requête hors de 127.0.0.1 (prevo.pro/version.json de la 2.1 mis à part : servi par le
       contexte de test, voir commun.servir_version_des_tests).
3. TestBibliothequesEtReseau (CS177, sans navigateur) — aucune bibliothèque nouvelle : js/lib/ contient les mêmes
   fichiers qu'en 2.1.0 ; index.html ne charge que des fichiers du dépôt (aucune adresse externe), ses bibliothèques
   sont celles de la 2.1 ; serveur.py n'importe que la bibliothèque standard de Python. Aucune adresse réseau
   nouvelle : les hôtes cités par index.html, serveur.py et js/ (hors js/lib/) sont ceux de la 2.1.0 (relevés à
   l'étiquette v2.1.0 le 2026-11-08), sauf ceux du catalogue (js/catalogue/, T400) : liens vers les textes de
   référence, tous en valeur de « url » d'un lien, jamais appelés par le code.

Lecture seule par une 2.1 (et une 2.0) d'une base au format 4 (CS169, seconde moitié) : prouvée par
tests/test_format4_lecture_2_1.py (T396 : serveurs et navigateur de v2.1.0 et v2.0.0 sur f4-v2.2.0, bandeau, 409 sur
toute écriture, aucun octet changé), relancé par la commande verif de T397, pas recopié ici.

Lancer depuis la racine du projet (au travers du verrou à navigateur) :
    py -X utf8 -m unittest discover -s tests -p "test_recette_format4.py" -v
"""
import ast
import functools
import hashlib
import json
import re
import shutil
import sys
import tempfile
import unittest
import urllib.parse
import urllib.request
from pathlib import Path

from commun import FORMAT_COURANT, RACINE, ServeurPrevo, ServeurStatique
from jeux_formats import copier_jeu
import test_formats_navigateur as navigateur
from test_migration_serveur import (AJOUTS_PAR_FORMAT, COLONNES_RESERVES, FORMATS_D_UNE_BASE_3, FORMATS_DE_F1,
                                    FORMATS_DE_F2, QUINZE_RESERVES, RESERVES, SERVEUR, UNE_RESERVE, ajouts_depuis,
                                    fichiers_de, lire_table, octets_csv, requete)

# ---------------------------------------------------------------------------
# Ce que la recette attend de chaque jeu
# ---------------------------------------------------------------------------

# jeu → (format d'origine, formats des fichiers que le passage complète, réserves reprises : lignes de
# reserves_controle.csv, None : le fichier n'est pas créé). Une ligne de journal par étape, du format d'origine + 1 au
# format courant.
ATTENDUS = {
    "f1": (1, FORMATS_DE_F1, None),
    "f2-v1.1.0": (2, FORMATS_DE_F2, UNE_RESERVE),
    "f3-v1.2.0": (3, FORMATS_D_UNE_BASE_3, UNE_RESERVE),
    "f3-v2.0.0": (3, FORMATS_D_UNE_BASE_3, UNE_RESERVE),
    "f3-v2.1.0": (3, FORMATS_D_UNE_BASE_3, UNE_RESERVE),
    "reserves-a-reprendre": (3, FORMATS_D_UNE_BASE_3, QUINZE_RESERVES),
    "f4-v2.2.0": (4, {}, None),
}
JEUX_DE_LA_RECETTE = tuple(ATTENDUS)
JEU_AVEC_COMPTES = "f3-v2.0.0"
COMPTE_DU_JEU = ("claire.essai", "essai-formats-prevo")     # LISEZMOI des jeux : compte fictif, tests seulement
# Écart A (voir l'en-tête) : la seule table dont les octets du navigateur et du serveur diffèrent, et la colonne en cause.
ECART_A = ("reserves-a-reprendre", "controles_reglementaires.csv", "remarque_maison")

JOURNAL = "journal.csv"
PARAMETRES = "parametres.csv"
MANIFESTE = "manifeste.json"
DERNIERE_VERSION = "derniere-version.json"
MOTIF_AVANT_FORMAT = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}_avant-format-v%d$" % FORMAT_COURANT)
MOTIF_DATE_MANIFESTE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
CHAMPS_DU_MANIFESTE = ["application", "version_appli", "format", "date", "motif", "mode", "fichiers"]
DEFAUTS = {colonne: defaut for ajouts in AJOUTS_PAR_FORMAT.values() for colonnes in ajouts.values()
           for colonne, defaut in colonnes}
PASSAGE = "passage au format %d du fichier ; sauvegarde %s faite juste avant"

# CS177 : relevés à l'étiquette v2.1.0 (git show v2.1.0:…, 2026-11-08).
FICHIERS_JS_LIB_2_1 = {"LICENCES.txt", "echarts.min.js", "jsQR.js", "papaparse.min.js", "qrcode.js", "xlsx.full.min.js"}
SCRIPTS_JS_LIB_DE_L_INDEX_2_1 = ["js/lib/papaparse.min.js", "js/lib/qrcode.js", "js/lib/jsQR.js"]
# Hôtes des adresses http(s) écrites dans index.html, serveur.py et js/**/*.js (hors js/lib/) de la 2.1.0 : adresses
# locales et d'exemple, l'IA en ligne choisie par le responsable, Tailscale, prevo.pro, github.com, et des espaces de
# noms (w3.org, apple.com) qui ne sont jamais appelés.
HOTES_DE_LA_2_1 = {
    "http://127.0.0.1", "http://192.168", "http://192.168.1.10", "http://192.168.x.x", "http://192.168.x.x.",
    "http://localhost", "http://www.apple.com", "http://www.w3.org", "https://api.mistral.ai", "https://github.com",
    "https://login.tailscale.com", "https://prevo.pro", "https://tailscale.com",
}
MOTIF_HOTE = re.compile(r"https?://[A-Za-z0-9._-]+")
MOTIF_URL_DE_LIEN = re.compile(r'"url": "(https?://[^"]+)"')
DOSSIER_CATALOGUE = "js/catalogue/"
# Navigateur : seules adresses que la page peut demander (le serveur de test, et la vérification de version de la 2.1,
# servie par le contexte de test).
HOTES_PERMIS_AU_NAVIGATEUR = {"127.0.0.1", "prevo.pro"}


def etapes(format_origine):
    return list(range(format_origine + 1, FORMAT_COURANT + 1))


def empreinte(octets):
    return hashlib.sha256(octets).hexdigest()


def racine_des_donnees(fichiers):
    """Les fichiers à la racine du dossier de données (ni sauvegardes/, ni acces/)."""
    return {chemin: octets for chemin, octets in fichiers.items() if "/" not in chemin}


def csv_de_la_racine(fichiers):
    return {chemin: octets for chemin, octets in racine_des_donnees(fichiers).items() if chemin.endswith(".csv")}


def dictionnaires(octets):
    """(en-tête, lignes en {colonne: cellule}) d'un CSV, cellules brutes ; une ligne courte complétée de vides."""
    entete, lignes = lire_table(octets)
    return entete, [{nom: (ligne[i] if i < len(ligne) else "") for i, nom in enumerate(entete)} for ligne in lignes]


def lignes_ajoutees_au_journal(avant, apres):
    """Lignes (dict) ajoutées à journal.csv (octets avant, None : absent ; octets après)."""
    deja = len(dictionnaires(avant)[1]) if avant is not None else 0
    return dictionnaires(apres)[1][deja:] if apres is not None else []


# ---------------------------------------------------------------------------
# Mode serveur : deux démarrages sur une copie (résultat gardé pour la comparaison avec le navigateur)
# ---------------------------------------------------------------------------

def connexion(serveur, identifiant, mot_de_passe):
    """Cookie « id=<jeton> » d'une session ouverte par POST /api/connexion."""
    corps = json.dumps({"identifiant": identifiant, "mot_de_passe": mot_de_passe, "rester": False}).encode("utf-8")
    demande = urllib.request.Request(serveur.url + "/api/connexion", data=corps, method="POST", headers={
        "Content-Type": "application/json; charset=utf-8", "X-Prevo": "1"})
    with urllib.request.urlopen(demande, timeout=10) as reponse:
        return reponse.headers.get("Set-Cookie", "").split(";")[0]


@functools.lru_cache(maxsize=None)
def passage_serveur(nom_jeu, comptes=False):
    """Démarre serveur.py sur une copie du jeu, puis une seconde fois sur le dossier ainsi laissé. Rend un dict :
    origine, apres (relevé juste après le démarrage, avant toute requête), etat (/api/info « format »), sans_session
    (statut de /api/info sans session, comptes seulement), console, avant_second, second, etat_second."""
    with tempfile.TemporaryDirectory(prefix="prevo-t397-serveur-") as temporaire:
        temporaire = Path(temporaire)
        source = copier_jeu(nom_jeu, temporaire / "jeu" / "donnees")
        resultat = {"origine": fichiers_de(source), "sans_session": None}
        arguments = []
        if comptes:
            configuration = temporaire / "prevo.config.json"
            configuration.write_text(json.dumps({"comptes": True}), encoding="utf-8")
            arguments = ["--config", str(configuration)]

        def etat_du_format(serveur):
            entetes = {"Cookie": connexion(serveur, *COMPTE_DU_JEU)} if comptes else None
            statut, donnees = requete(serveur, "GET", "/api/info", entetes=entetes)
            return donnees["format"] if statut == 200 else (statut, donnees)

        with ServeurPrevo(source=source, arguments=arguments) as serveur:
            resultat["apres"] = fichiers_de(serveur.dossier)
            if comptes:
                resultat["sans_session"] = requete(serveur, "GET", "/api/info")[0]
            resultat["etat"] = etat_du_format(serveur)
            resultat["console"] = serveur.sortie_console()
            copie = temporaire / "apres"
            shutil.copytree(serveur.dossier, copie)
        resultat["avant_second"] = fichiers_de(copie)
        with ServeurPrevo(source=copie, arguments=arguments) as second:
            resultat["second"] = fichiers_de(second.dossier)
            resultat["etat_second"] = etat_du_format(second)
        return resultat


# ---------------------------------------------------------------------------
# Vérifications communes aux deux modes
# ---------------------------------------------------------------------------

class VerificationsDuPassage:
    """À mêler à un unittest.TestCase."""

    def verifier_sauvegarde_avant_format(self, nom_jeu, mode, origine, apres):
        """Une seule sauvegarde avant-format-v4 (aucune pour une base déjà au format 4), aux octets d'origine, conforme
        à son manifeste. Rend son nom (None : aucune)."""
        format_origine = ATTENDUS[nom_jeu][0]
        noms = sorted({chemin.split("/")[1] for chemin in apres if chemin.startswith("sauvegardes/")})
        avant_format = [nom for nom in noms if MOTIF_AVANT_FORMAT.match(nom)]
        self.assertEqual(len(avant_format), 0 if format_origine == FORMAT_COURANT else 1, noms)
        if not avant_format:
            return None
        nom = avant_format[0]
        prefixe = "sauvegardes/%s/" % nom
        contenu = {chemin[len(prefixe):]: octets for chemin, octets in apres.items() if chemin.startswith(prefixe)}
        manifeste = json.loads(contenu.pop(MANIFESTE).decode("utf-8"))
        # Aux octets d'origine : toutes les tables du jeu (et acces/, que le serveur sauvegarde aussi), rien d'autre.
        attendu = {chemin: octets for chemin, octets in origine.items()
                   if ("/" not in chemin and chemin.endswith(".csv")) or (mode == "serveur" and chemin.startswith("acces/"))}
        self.assertEqual(contenu, attendu, "sauvegarde %s" % nom)
        # Conforme à son manifeste (FORMAT.md §9).
        self.assertEqual(list(manifeste), CHAMPS_DU_MANIFESTE, manifeste)
        self.assertEqual((manifeste["application"], manifeste["version_appli"], manifeste["format"],
                          manifeste["motif"], manifeste["mode"]),
                         (SERVEUR.NOM_APPLICATION, SERVEUR.VERSION_APPLICATION, format_origine,
                          "avant-format-v%d" % FORMAT_COURANT, mode))
        self.assertRegex(manifeste["date"], MOTIF_DATE_MANIFESTE)
        self.assertEqual(manifeste["fichiers"], [{"nom": chemin, "octets": len(octets), "sha256": empreinte(octets)}
                                                 for chemin, octets in sorted(contenu.items())])
        return nom

    def verifier_cellules(self, chemin, avant, apres, ajouts):
        """Toute cellule d'origine sous le même nom de colonne et à la même ligne (version_schema mise à part) ; les
        colonnes ajoutées sont exactement celles attendues, avec leur défaut."""
        entete_avant, lignes_avant = dictionnaires(avant)
        entete_apres, lignes_apres = dictionnaires(apres)
        self.assertEqual(sorted(entete_apres), sorted(entete_avant + [colonne for colonne, _ in ajouts]), chemin)
        self.assertEqual(len(entete_apres), len(set(entete_apres)), chemin)
        self.assertEqual(len(lignes_apres), len(lignes_avant), chemin)
        for numero, (ligne_avant, ligne_apres) in enumerate(zip(lignes_avant, lignes_apres), 2):
            attendue = dict(ligne_avant, **{colonne: defaut for colonne, defaut in ajouts})
            if chemin == PARAMETRES and ligne_avant.get("cle") == "version_schema":
                attendue["valeur"] = "'%d" % FORMAT_COURANT
            self.assertEqual(ligne_apres, attendue, "%s, ligne %d" % (chemin, numero))

    def verifier_ecritures_du_passage(self, nom_jeu, mode, origine, apres, ajoutes_par_le_mode):
        """Ce qu'une ouverture (dossier) ou un démarrage (serveur) a écrit. ajoutes_par_le_mode : fichiers de la racine
        que le mode écrit en plus de ceux du passage (derniere-version.json, verrou.txt). Rend le nom de la sauvegarde."""
        format_origine, formats, reserves = ATTENDUS[nom_jeu]
        ajouts = ajouts_depuis(formats)
        passage = format_origine < FORMAT_COURANT
        nom_sauvegarde = self.verifier_sauvegarde_avant_format(nom_jeu, mode, origine, apres)

        # Fichiers de la racine : ceux d'origine, le journal (créé s'il manquait), reserves_controle.csv s'il y a des
        # réserves à reprendre, et ce que le mode écrit toujours ; aucune autre table (ni garanties, ni contrats).
        crees = ({JOURNAL} if passage else set()) | ({RESERVES} if reserves else set())
        self.assertEqual(set(racine_des_donnees(apres)),
                         set(racine_des_donnees(origine)) | crees | set(ajoutes_par_le_mode))
        for chemin in origine:
            if chemin.startswith("acces/"):
                self.assertEqual(apres.get(chemin), origine[chemin], chemin)
        self.assertEqual({c for c in apres if c.startswith("acces/")}, {c for c in origine if c.startswith("acces/")})

        # Tables complétées champ à champ ; les autres (sans colonne nouvelle) identiques à l'octet.
        changes = set(ajouts) | ({"parametres", "journal"} if passage else set())
        for chemin, octets in sorted(csv_de_la_racine(origine).items()):
            table = chemin[:-len(".csv")]
            if table in ajouts or (passage and table == "parametres"):
                self.verifier_cellules(chemin, octets, apres[chemin], ajouts.get(table, []))
                self.assertTrue(apres[chemin].startswith(b"\xef\xbb\xbf"), chemin)
            elif table not in changes:
                self.assertEqual(apres[chemin], octets, chemin)
        version = dict((l["cle"], l["valeur"]) for l in dictionnaires(apres[PARAMETRES])[1])["version_schema"]
        self.assertEqual(version, "'%d" % FORMAT_COURANT)

        # Réserves de D183, écrites comme Prévo les écrit.
        if reserves:
            self.assertEqual(lire_table(apres[RESERVES]), (COLONNES_RESERVES, reserves))
            self.assertEqual(apres[RESERVES], octets_csv(COLONNES_RESERVES, reserves))
        else:
            self.assertEqual(apres.get(RESERVES), origine.get(RESERVES))

        # Journal : une ligne par étape, rien d'autre ; les lignes d'origine intactes.
        ajoutees = lignes_ajoutees_au_journal(origine.get(JOURNAL), apres.get(JOURNAL))
        self.assertEqual([(l["table"], l["id_ligne"], l["action"]) for l in ajoutees],
                         [("parametres", "version_schema", PASSAGE % (n, nom_sauvegarde)) for n in etapes(format_origine)])
        if JOURNAL in origine:
            self.assertEqual(dictionnaires(apres[JOURNAL])[1][:len(dictionnaires(origine[JOURNAL])[1])],
                             dictionnaires(origine[JOURNAL])[1])
        return nom_sauvegarde


# ---------------------------------------------------------------------------
# 1. Mode serveur
# ---------------------------------------------------------------------------

class TestServeur(VerificationsDuPassage, unittest.TestCase):

    def verifier_demarrages(self, nom_jeu, comptes=False):
        resultat = passage_serveur(nom_jeu, comptes)
        passage = ATTENDUS[nom_jeu][0] < FORMAT_COURANT
        self.verifier_ecritures_du_passage(nom_jeu, "serveur", resultat["origine"], resultat["apres"],
                                           {DERNIERE_VERSION})
        self.assertEqual(resultat["etat"]["migration"], "faite" if passage else "rien", resultat["etat"])
        self.assertEqual((resultat["etat"]["base"], resultat["etat"]["plus_recent"], resultat["etat"]["tables_abimees"]),
                         (FORMAT_COURANT, False, []))
        if passage:
            # La console liste les fichiers complétés, reserves_controle.csv compris (aucun texte nouveau).
            completes = list(ajouts_depuis(ATTENDUS[nom_jeu][1])) + (["reserves_controle"] if ATTENDUS[nom_jeu][2] else [])
            self.assertIn("fichiers complétés : %s." % ", ".join(t + ".csv" for t in completes), resultat["console"])
        # Le journal grandit par la fin : ses octets d'origine en tête.
        if JOURNAL in resultat["origine"]:
            self.assertTrue(resultat["apres"][JOURNAL].startswith(resultat["origine"][JOURNAL]))
        # Les tables complétées : colonnes ajoutées en fin d'en-tête, dans l'ordre du schéma.
        for table, colonnes in ajouts_depuis(ATTENDUS[nom_jeu][1]).items():
            entete_avant = lire_table(resultat["origine"][table + ".csv"])[0]
            self.assertEqual(lire_table(resultat["apres"][table + ".csv"])[0],
                             entete_avant + [colonne for colonne, _ in colonnes], table)
        # Second démarrage : aucun octet écrit, aucune sauvegarde de plus, rien à faire.
        self.assertEqual(resultat["second"], resultat["avant_second"])
        self.assertEqual(resultat["etat_second"]["migration"], "rien")
        return resultat

    def test_chaque_jeu_passe_au_format_4_sans_perte_second_demarrage_sans_ecriture(self):
        for nom_jeu in JEUX_DE_LA_RECETTE:
            with self.subTest(jeu=nom_jeu):
                self.verifier_demarrages(nom_jeu)

    def test_avec_comptes_passage_fait_avant_toute_connexion_memes_octets_que_sans_comptes(self):
        resultat = self.verifier_demarrages(JEU_AVEC_COMPTES, comptes=True)
        self.assertIn("acces/comptes.json", resultat["origine"])
        self.assertEqual(resultat["sans_session"], 401)                   # /api/info n'est pas publique
        self.assertEqual(resultat["etat"]["migration"], "faite")          # lu par le responsable du jeu
        sans_comptes = passage_serveur(JEU_AVEC_COMPTES)
        donnees = lambda fichiers: {c: o for c, o in csv_de_la_racine(fichiers).items() if c != JOURNAL}
        self.assertEqual(donnees(resultat["apres"]), donnees(sans_comptes["apres"]))
        self.assertEqual([(l["table"], l["id_ligne"], l["poste"]) for l in lignes_ajoutees_au_journal(
                             resultat["origine"][JOURNAL], resultat["apres"][JOURNAL])],
                         [("parametres", "version_schema", "Serveur Prévo")])


# ---------------------------------------------------------------------------
# 2. Mode dossier (navigateur), comparé au serveur
# ---------------------------------------------------------------------------

class TestDossier(VerificationsDuPassage, navigateur.CasFormats):

    def setUp(self):
        super().setUp()
        self.requetes = []
        self.page.on("request", lambda demande: self.requetes.append(demande.url))

    def verifier_requetes(self):
        hotes = {urllib.parse.urlsplit(adresse).hostname for adresse in self.requetes
                 if urllib.parse.urlsplit(adresse).scheme in ("http", "https", "ws", "wss")}
        self.assertTrue(hotes, "aucune requête relevée")
        self.assertLessEqual(hotes, HOTES_PERMIS_AU_NAVIGATEUR, sorted(set(self.requetes)))

    def verifier_parite(self, nom_jeu, apres, serveur):
        """CSV par CSV, les octets du navigateur égaux à ceux du serveur (journal et écart A : voir l'en-tête)."""
        dossier, chez_le_serveur = csv_de_la_racine(apres), csv_de_la_racine(serveur["apres"])
        self.assertEqual(set(dossier), set(chez_le_serveur))
        for chemin in sorted(set(dossier) - {JOURNAL}):
            if (nom_jeu, chemin) == ECART_A[:2]:
                colonne = ECART_A[2]
                entete_n, lignes_n = dictionnaires(dossier[chemin])
                entete_s, lignes_s = dictionnaires(chez_le_serveur[chemin])
                self.assertNotEqual(dossier[chemin], chez_le_serveur[chemin], "écart A disparu : à retirer d'ici")
                self.assertEqual(entete_n, [nom for nom in entete_s if nom != colonne] + [colonne])
                self.assertEqual(lignes_n, lignes_s)
                continue
            self.assertEqual(dossier[chemin], chez_le_serveur[chemin], "%s : navigateur ≠ serveur" % chemin)
        # Journal : mêmes lignes ajoutées (identifiant, heure, poste, profil et nom de la sauvegarde mis à part).
        resume = lambda lignes: [(l["table"], l["id_ligne"], re.sub(r"sauvegarde \S+ faite", "sauvegarde … faite",
                                                                    l["action"])) for l in lignes]
        origine = serveur["origine"].get(JOURNAL)
        self.assertEqual(resume(lignes_ajoutees_au_journal(origine, dossier.get(JOURNAL))),
                         resume(lignes_ajoutees_au_journal(origine, chez_le_serveur.get(JOURNAL))))

    def verifier_dossier(self, nom_jeu):
        serveur = passage_serveur(nom_jeu)
        origine = navigateur.fichiers_du_jeu(nom_jeu)
        self.assertEqual(origine, serveur["origine"])
        with ServeurStatique(RACINE) as statique:
            self.ouvrir_dossier(statique, origine)
            apres = self.instantane()
            self.verifier_ecritures_du_passage(nom_jeu, "dossier", origine, apres,
                                               {navigateur.VERROU, DERNIERE_VERSION})
            etat = self.page.evaluate("Donnees.etatDuFormat()")
            self.assertEqual((etat["depart"], etat["aCompleter"]), (FORMAT_COURANT, []), etat)
            self.assertFalse(self.page.evaluate("Donnees.lectureSeule()"))
            self.assertEqual(self.page.locator("#bandeau-lecture-seule").count(), 0)
            self.verifier_parite(nom_jeu, apres, serveur)
            # Seconde ouverture : rien n'est écrit (verrou.txt mis à part).
            self.rouvrir_dossier()
            sans_verrou = lambda fichiers: {c: o for c, o in fichiers.items() if c != navigateur.VERROU}
            self.assertEqual(sans_verrou(self.instantane()), sans_verrou(apres))
        self.verifier_requetes()

    def test_f1_trois_etapes_sans_controle_memes_octets_que_le_serveur(self):
        self.verifier_dossier("f1")

    def test_f2_v1_1_0_deux_etapes_une_reserve_memes_octets_que_le_serveur(self):
        self.verifier_dossier("f2-v1.1.0")

    def test_f3_v1_2_0_une_etape_une_reserve_memes_octets_que_le_serveur(self):
        self.verifier_dossier("f3-v1.2.0")

    def test_f3_v2_0_0_acces_intact_memes_octets_que_le_serveur(self):
        self.verifier_dossier("f3-v2.0.0")

    def test_f3_v2_1_0_base_2_1_une_reserve_memes_octets_que_le_serveur(self):
        self.verifier_dossier("f3-v2.1.0")

    def test_reserves_a_reprendre_quinze_reserves_seul_l_ecart_a(self):
        self.verifier_dossier("reserves-a-reprendre")

    def test_f4_v2_2_0_rien_a_faire_aucun_octet_ecrit(self):
        self.verifier_dossier("f4-v2.2.0")


# ---------------------------------------------------------------------------
# 3. CS177 : aucune bibliothèque nouvelle, aucune adresse réseau nouvelle
# ---------------------------------------------------------------------------

def scripts_de_l_index():
    texte = re.sub(r"<!--.*?-->", "", (RACINE / "index.html").read_text(encoding="utf-8"), flags=re.DOTALL)
    return re.findall(r"""<script\b[^>]*?\ssrc\s*=\s*["']([^"']+)["']""", texte, re.IGNORECASE), texte


def fichiers_de_code():
    """index.html, serveur.py et js/**/*.js hors js/lib/ (chemins relatifs en « / »)."""
    chemins = [RACINE / "index.html", RACINE / "serveur.py"] + sorted((RACINE / "js").rglob("*.js"))
    return {p.relative_to(RACINE).as_posix(): p.read_text(encoding="utf-8") for p in chemins
            if not p.relative_to(RACINE).as_posix().startswith("js/lib/")}


class TestBibliothequesEtReseau(unittest.TestCase):

    def test_js_lib_et_scripts_de_l_index_comme_en_2_1(self):
        self.assertEqual({p.name for p in (RACINE / "js" / "lib").iterdir()}, FICHIERS_JS_LIB_2_1)
        scripts, texte = scripts_de_l_index()
        self.assertTrue(scripts)
        for script in scripts:
            self.assertFalse(re.match(r"^([a-z]+:)?//", script, re.IGNORECASE), script)   # aucun script externe
            self.assertTrue((RACINE / script).is_file(), script)
        self.assertEqual([s for s in scripts if s.startswith("js/lib/")], SCRIPTS_JS_LIB_DE_L_INDEX_2_1)
        # Aucune ressource chargée d'ailleurs (feuille de style, image, cadre…) ; un lien <a href> est ouvert par
        # l'utilisateur (ses hôtes : test_aucune_adresse_reseau_nouvelle).
        self.assertEqual(re.findall(r"""<(?!a\b)[a-z]+\b[^>]*\s(?:src|href)\s*=\s*["'](?:https?:)?//""", texte,
                                    re.IGNORECASE), [])

    def test_serveur_n_importe_que_la_bibliotheque_standard(self):
        arbre = ast.parse((RACINE / "serveur.py").read_text(encoding="utf-8"))
        modules = set()
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                modules |= {alias.name.split(".")[0] for alias in noeud.names}
            elif isinstance(noeud, ast.ImportFrom) and noeud.level == 0:
                modules.add(noeud.module.split(".")[0])
        self.assertTrue(modules)
        self.assertEqual(sorted(modules - set(sys.stdlib_module_names)), [])

    def test_aucune_adresse_reseau_nouvelle(self):
        nouveaux = {}
        for chemin, texte in fichiers_de_code().items():
            if chemin.startswith(DOSSIER_CATALOGUE):
                # Catalogue : des liens vers les textes de référence, ouverts par l'utilisateur, jamais appelés.
                self.assertEqual(sorted(MOTIF_HOTE.findall(texte)),
                                 sorted(MOTIF_HOTE.match(url).group(0) for url in MOTIF_URL_DE_LIEN.findall(texte)),
                                 chemin)
                continue
            for hote in set(MOTIF_HOTE.findall(texte)) - HOTES_DE_LA_2_1:
                nouveaux.setdefault(hote, []).append(chemin)
        self.assertEqual(nouveaux, {}, "adresses réseau absentes de la 2.1.0 (CS177)")


if __name__ == "__main__":
    unittest.main()
