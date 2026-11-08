"""Lot 7 — migration depuis 1.2 et dossier C:\\Prevo (ARCHITECTURE.md §22.10 « Migration et dossier » ; CDC D131, dernier
point ; CS130 ; tâche T171) : serveur.py (étapes « deplacer » et « terminer », deplacer_installation,
installer_jeu_de_demo), installation-etapes.js et installation-ecrans.js, js/app.js (profils, T155).

Ce qui est vérifié :
    base 1.2      serveur du processus sans configuration sur une copie de la démo : l'état dit les CSV présents (NB_TABLES,
                  dernière modification) ; parcours Solo « ce PC » jusqu'à « terminer » : chaque CSV égal octet à octet
                  à l'original sauf parametres.csv (lignes d'origine toutes présentes, mode_solo ajouté, version_schema
                  inchangé) ; « demo » refusé (400) sur une base présente, rien d'écrit ;
    base absente  « demo » en Solo « dehors » (faux Tailscale) : les tables (NB_TABLES) de js/demo-donnees.js écrites, dates
                  décalées de semaines entières (attendu calculé ici d'après les colonnes date et date_heure de
                  js/schema.js, horloge du serveur fixée), technicien « moi » recréé (TEC-0005), compte responsable
                  relié, parametres.csv de la démo avec mode_solo ; « demo » pour l'informaticien : sans mode_solo ;
                  « vide » : rien de plus que ce que Solo pose ; base inconnue 400 ; jeu de démo illisible : 500 et rien
                  d'écrit ;
    langue        (T296) langue_defaut à « terminer » : base présente jamais touchée ; base absente : « fr » sans le
                  champ, « en » avec la démo (après ses lignes) et pour « vide » hors Solo (parametres.csv seul,
                  version_schema en tête) ; « xx », « EN », vide, null, nombre, liste : 400 par code
                  (installation.langue_inconnue, les langues déclarées en valeur), rien d'écrit ; serveur et outils
                  lisent les mêmes langues dans js/i18n/langues.js ;
    cohérence     lire_jeu_de_demo rend exactement donnees/demo/*.csv ; les cellules que decaler_texte_csv décale sont
                  exactement les colonnes date et date_heure du schéma ;
    deplacer      deplacer_installation (module) vers un dossier temporaire : compte des fichiers, SHA-256 de chaque
                  fichier, brouillon dans la copie, relance notée avec le bon dossier, dossier d'origine intact ; la
                  route l'appelle ; « Rester ici » mémorisé (deplacement_refuse) puis effacé par un déplacement ; cible
                  non vide, dans la source, chemin relatif : 400 ; C:\\Prevo est le dossier conseillé ;
    profils       navigateur, prevo.profil « responsable » de 1.2 préréglé : serveur en mode comptes → écran de
                  connexion (jamais l'écran de profil), App.profil déduit de la session (technicien) ; sans comptes →
                  profil mémorisé gardé ;
    écran         Solo sur la démo : étape 1 avec la ligne de migration, étape 8 sans « Par quoi commencer ? »,
                  « Rester ici » puis rechargement sans la carte ; base absente : « Par quoi commencer ? », « demo » puis
                  Terminer → tables écrites, attente de la relance, accueil ; « Déplacer » (dossier conseillé remplacé
                  par un dossier temporaire) → copie, attente du serveur relancé, reprise à l'étape 8.
Aucune commande d'administrateur, aucune relance réelle (config.relancer remplacée), aucune sortie réseau, jamais le
vrai C:\\Prevo ni le dossier donnees/ réel.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_installation_migration.py" -v
"""
import csv
import datetime
import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import commun
from commun import RACINE, CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil
from test_installation_api import (CasAssistant, Enregistreur, MOT_DE_PASSE, NOM_TAILSCALE, configuration, lire_csv,
                                   parametres_de, serveur, sha256)
from test_installation_ecrans import CasInstallation

sys.path.insert(0, str(RACINE / "outils"))
from textes_langues import langues_declarees  # noqa: E402  (lecteur de js/i18n/langues.js des outils, T296)

MOTIF_DEBUT_DE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")
MOTIF_TABLE_SCHEMA = re.compile(r"^    ([a-z_]+): \{$")
MOTIF_CHAMP_DATE_SCHEMA = re.compile(r"champ\('([a-z_]+)', '(date|date_heure)'")
# Horloge du serveur pendant « terminer » : 6 semaines entières après la date de référence de la démo (2026-10-19).
INSTANT_FIXE = datetime.datetime(2026, 11, 30, 12, 0, 0).timestamp()
ERREUR_401_SONDE = re.compile(r"status of 401 .*/api/versions")        # sans session : la sonde d'App (appareil refusé ?)
SUIVI_ETATS_JS = """
window.__etats = [];
new MutationObserver(() => {
  const etat = document.documentElement && document.documentElement.dataset.etat;
  if (etat && window.__etats[window.__etats.length - 1] !== etat) window.__etats.push(etat);
}).observe(document, { subtree: true, attributes: true, attributeFilter: ['data-etat'] });
"""


def lignes_csv(octets):
    """(en-tête, lignes) d'un CSV de Prévo lu par le module csv (BOM retiré, « ; »)."""
    texte = octets.decode("utf-8-sig")
    lignes = [l for l in csv.reader(io.StringIO(texte, newline=""), delimiter=";") if l]
    return lignes[0], lignes[1:]


def colonnes_dates_du_schema():
    """{table: {colonnes typées date ou date_heure}} lu dans js/schema.js (jamais dans serveur.py)."""
    types, table = {}, None
    for ligne in (RACINE / "js" / "schema.js").read_text(encoding="utf-8").splitlines():
        trouvee = MOTIF_TABLE_SCHEMA.match(ligne)
        if trouvee:
            table = trouvee.group(1)
            types[table] = set()
            continue
        trouvee = MOTIF_CHAMP_DATE_SCHEMA.search(ligne)
        if trouvee and table:
            types[table].add(trouvee.group(1))
    return types


def jeu_de_demo_decale(jours):
    """{table: (en-tête, lignes)} de donnees/demo avec les colonnes date et date_heure du schéma décalées de « jours »
    (comme StockageDemo.decalerDates), calculé ici sans serveur.py : l'oracle du test « demo »."""
    types = colonnes_dates_du_schema()
    resultat = {}
    for chemin in sorted(commun.DOSSIER_DEMO.glob("*.csv")):
        entete, lignes = lignes_csv(chemin.read_bytes())
        positions = [entete.index(colonne) for colonne in types.get(chemin.stem, ()) if colonne in entete]
        for ligne in lignes:
            for position in positions:
                cellule = ligne[position] if position < len(ligne) else ""
                if MOTIF_DEBUT_DE_DATE.match(cellule):
                    jour = datetime.date.fromisoformat(cellule[:10]) + datetime.timedelta(days=jours)
                    ligne[position] = jour.isoformat() + cellule[10:]
        resultat[chemin.stem] = (entete, lignes)
    return resultat


def fabriquer_prevo(dossier):
    """Un dossier de Prévo simulé (serveur, lanceur, un script, .git et __pycache__ à ne pas copier)."""
    for relatif, contenu in (("serveur.py", b"# serveur\r\n"), ("Lancer_GMAO.bat", b"@echo off\r\n"),
                             ("js/app.js", b"'use strict';\n"), ("outils-tiers/mkcert.exe", bytes(range(256)) * 4),
                             (".git/HEAD", b"ref: refs/heads/main\n"), ("js/__pycache__/x.pyc", b"\x00")):
        chemin = dossier / relatif
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_bytes(contenu)
    return dossier


def empreintes(dossier):
    return {str(p.relative_to(dossier)): sha256(p) for p in dossier.rglob("*") if p.is_file()}


def empreintes_a_copier(dossier):
    return {chemin: empreinte for chemin, empreinte in empreintes(dossier).items()
            if not chemin.startswith(".git") and "__pycache__" not in chemin}


# ---------------------------------------------------------------------------
# Base 1.2 gardée, base absente : vide ou démo (API)
# ---------------------------------------------------------------------------

class TestBaseDeDepart(CasAssistant):

    def solo_ce_pc_jusqu_au_recapitulatif(self, client, prenom, nom):
        self.ok(client.post("situation", {"situation": "seul"}))
        self.ok(client.post("portee", {"portee": "ce-pc"}))
        reponse = self.ok(client.post("compte", {"prenom": prenom, "nom": nom}))
        self.ok(client.post("demarrage", {"demarrage": "aucun", "veille_desactivee": False}))
        self.ok(client.post("sauvegardes", {"dossier": ""}))
        return reponse["technicien_id"]

    def test_base_1_2_gardee_jusqu_a_terminer(self):
        client, instance = self.lancer(source=commun.DOSSIER_DEMO)       # la démo tient lieu de base 1.2
        donnees = Path(instance.config.dossier_donnees)
        originaux = {p.name: p.read_bytes() for p in donnees.glob("*.csv")}
        self.assertEqual(len(originaux), commun.NB_TABLES)
        etat = self.ok(client.get("etat"))
        self.assertTrue(etat["csv_presents"])
        self.assertEqual(etat["nombre_csv"], commun.NB_TABLES)
        plus_recent = max(p.stat().st_mtime for p in donnees.glob("*.csv"))
        self.assertEqual(etat["derniere_modification"],
                         datetime.datetime.fromtimestamp(plus_recent).strftime("%Y-%m-%dT%H:%M:%S"))
        reponse = self.ok(client.post("situation", {"situation": "seul"}))
        self.assertTrue(reponse["brouillon"]["base_presente"])
        self.ok(client.post("portee", {"portee": "ce-pc"}))
        # Le technicien « moi » porte le nom d'un technicien de la démo : reconnu, techniciens.csv n'est pas réécrit.
        reponse = self.ok(client.post("compte", {"prenom": "Julien", "nom": "Moreau"}))
        self.assertEqual(reponse["technicien_id"], "TEC-0001")
        self.ok(client.post("demarrage", {"demarrage": "aucun", "veille_desactivee": False}))
        self.ok(client.post("sauvegardes", {"dossier": ""}))
        refus = client.post("terminer", {"base": "demo"})                   # jamais sur une base existante
        self.assertEqual(refus.statut, 400, refus.octets)
        self.assertIn("existante", refus.json()["erreur"])
        self.assertFalse(Path(instance.config.reglages["_fichier"]).exists())
        self.assertEqual({p.name: p.read_bytes() for p in donnees.glob("*.csv")}, originaux)
        # T296 : une langue envoyée sur une base présente au départ ne la change pas (aucune ligne langue_defaut).
        fin = self.ok(client.post("terminer", {"langue_defaut": "en"}))
        self.assertEqual((fin["base"], fin["relance"], self.enregistreur.relances), ("vide", True, [None]))
        apres = {p.name: p.read_bytes() for p in donnees.glob("*.csv")}
        self.assertEqual(sorted(apres), sorted(originaux))                   # aucun CSV ajouté ni retiré
        for nom in originaux:
            if nom != "parametres.csv":
                with self.subTest(fichier=nom):
                    self.assertEqual(apres[nom], originaux[nom], "%s a été réécrit" % nom)
        entete_avant, lignes_avant = lignes_csv(originaux["parametres.csv"])
        entete_apres, lignes_apres = lignes_csv(apres["parametres.csv"])
        self.assertEqual(entete_apres, entete_avant)
        for ligne in lignes_avant:
            self.assertIn(ligne, lignes_apres)                               # toutes les lignes d'origine, telles quelles
        parametres = parametres_de(donnees)
        self.assertEqual((parametres["mode_solo"], parametres["cloture_une_etape"], parametres["solo_technicien_id"]),
                         ("1", "1", "TEC-0001"))
        self.assertEqual(parametres["version_schema"], "'%d" % commun.FORMAT_COURANT)                  # présent : jamais réécrit (apostrophe gardée)
        self.assertEqual(parametres["entreprise_nom"], "Atelier des Trois Vallées (démo)")
        self.assertNotIn("langue_defaut", parametres)
        self.assertTrue(Path(instance.config.reglages["_fichier"]).is_file())
        self.assertTrue(any(p.is_dir() for p in Path(instance.config.dossier_sauvegardes).iterdir()))   # sauvegarde du jour

    def test_base_absente_demo_en_solo_dehors_relie_le_technicien_moi(self):
        self.faux_tailscale()
        client, instance = self.lancer()                                     # dossier de données vide
        instance.config.horloge = lambda: INSTANT_FIXE
        reponse = self.ok(client.post("situation", {"situation": "seul"}))
        self.assertFalse(reponse["brouillon"]["base_presente"])
        self.ok(client.post("portee", {"portee": "dehors"}))
        reponse = self.ok(client.post("compte", {"prenom": "Nicolas", "nom": "Briand", "mot_de_passe": MOT_DE_PASSE}))
        self.assertEqual((reponse["technicien_id"], reponse["compte"]["technicien_id"]), ("TEC-0001", "TEC-0001"))
        self.assertTrue(self.ok(client.get("etat"))["csv_presents"])         # techniciens.csv créé par l'assistant lui-même
        self.ok(client.post("certificat", {"mode": "reseau_prive"}))
        self.ok(client.post("tailscale", {"action": "appliquer"}))
        self.ok(client.post("demarrage", {"demarrage": "aucun", "veille_desactivee": False}))
        self.ok(client.post("sauvegardes", {"dossier": ""}))
        refus = client.post("terminer", {"base": "autre"})
        self.assertEqual(refus.statut, 400, refus.octets)
        self.assertIn("vide", refus.json()["erreur"])
        fin = self.ok(client.post("terminer", {"base": "demo"}))
        self.assertEqual((fin["base"], self.enregistreur.relances), ("demo", [None]))
        donnees = Path(instance.config.dossier_donnees)
        self.assertEqual(sorted(p.stem for p in donnees.glob("*.csv")), sorted(serveur.TABLES))
        attendus = jeu_de_demo_decale(6 * 7)                                  # 2026-10-19 → 2026-11-30 : 6 semaines
        for table, (entete, lignes) in attendus.items():
            if table in ("techniciens", "parametres"):
                continue
            with self.subTest(table=table):
                self.assertEqual(lignes_csv((donnees / (table + ".csv")).read_bytes()), (entete, lignes))
        # Les dates ont bien bougé (l'oracle n'est pas une recopie).
        entete, lignes = lire_csv(donnees / "ordres_travail.csv")
        premiere = lignes[0][entete.index("date_creation")]
        entete_demo, lignes_demo = lire_csv(commun.DOSSIER_DEMO / "ordres_travail.csv")
        self.assertNotEqual(premiere, lignes_demo[0][entete_demo.index("date_creation")])
        self.assertEqual(premiere[10:], lignes_demo[0][entete_demo.index("date_creation")][10:])     # l'heure gardée
        # Technicien « moi » recréé après les quatre de la démo ; le compte responsable le suit.
        entete, lignes = lire_csv(donnees / "techniciens.csv")
        self.assertEqual(lignes[:4], lire_csv(commun.DOSSIER_DEMO / "techniciens.csv")[1])
        self.assertEqual(lignes[4][:3] + lignes[4][-1:], ["TEC-0005", "Briand", "Nicolas", "1"])
        comptes = json.loads((donnees / "acces" / "comptes.json").read_text(encoding="utf-8"))
        self.assertEqual([(c["identifiant"], c["technicien_id"]) for c in comptes["comptes"]], [("nicolas.briand", "TEC-0005")])
        parametres = parametres_de(donnees)
        self.assertEqual((parametres["mode_solo"], parametres["cloture_une_etape"], parametres["solo_technicien_id"]),
                         ("1", "1", "TEC-0005"))
        self.assertEqual(parametres["entreprise_nom"], "Atelier des Trois Vallées (démo)")
        self.assertEqual(parametres["version_schema"], "'%d" % commun.FORMAT_COURANT)
        self.assertTrue(Path(instance.config.reglages["_fichier"]).is_file())
        self.assertFalse((donnees / "installation.json").exists())

    def test_base_absente_demo_pour_l_informaticien_sans_solo(self):
        client, instance = self.lancer()
        instance.config.horloge = lambda: INSTANT_FIXE
        self.ok(client.post("situation", {"situation": "informaticien"}))
        self.ok(client.post("portee", {"portee": "atelier", "noms": ["gmao.entreprise.lan"]}))
        self.ok(client.post("compte", {"prenom": "Nicolas", "nom": "Briand", "mot_de_passe": MOT_DE_PASSE}))
        self.ok(client.post("certificat", {"mode": "mandataire"}))
        self.ok(client.post("demarrage", {"demarrage": "aucun", "veille_desactivee": False}))
        self.ok(client.post("sauvegardes", {"dossier": ""}))
        fin = self.ok(client.post("terminer", {"base": "demo", "langue_defaut": "en"}))
        self.assertEqual(fin["base"], "demo")
        donnees = Path(instance.config.dossier_donnees)
        self.assertEqual(sorted(p.stem for p in donnees.glob("*.csv")), sorted(serveur.TABLES))
        attendus = jeu_de_demo_decale(6 * 7)
        # parametres.csv : les lignes de la démo, puis la langue choisie (T296).
        entete, lignes = attendus["parametres"]
        attendus["parametres"] = (entete, lignes + [["langue_defaut", "en"]])
        for table, (entete, lignes) in attendus.items():
            with self.subTest(table=table):
                self.assertEqual(lignes_csv((donnees / (table + ".csv")).read_bytes()), (entete, lignes))
        self.assertNotIn("mode_solo", parametres_de(donnees))
        comptes = json.loads((donnees / "acces" / "comptes.json").read_text(encoding="utf-8"))
        self.assertEqual(comptes["comptes"][0]["technicien_id"], "")

    def test_base_absente_vide_rien_de_plus_que_ce_que_solo_pose(self):
        client, instance = self.lancer()
        self.solo_ce_pc_jusqu_au_recapitulatif(client, "Nicolas", "Briand")
        fin = self.ok(client.post("terminer", {"base": "vide"}))
        self.assertEqual(fin["base"], "vide")
        donnees = Path(instance.config.dossier_donnees)
        self.assertEqual(sorted(p.name for p in donnees.glob("*.csv")), ["parametres.csv", "techniciens.csv"])
        parametres = parametres_de(donnees)
        self.assertEqual((parametres["mode_solo"], parametres["solo_technicien_id"], parametres["version_schema"]),
                         ("1", "TEC-0001", "3"))
        self.assertEqual(parametres["langue_defaut"], "fr")                  # T296 : sans langue_defaut reçue, le français

    def test_base_absente_vide_hors_solo_parametres_avec_la_langue(self):
        # T296 : hors Solo, « vide » crée parametres.csv seul (format courant et langue de Prévo).
        client, instance = self.lancer()
        self.ok(client.post("situation", {"situation": "informaticien"}))
        self.ok(client.post("portee", {"portee": "atelier", "noms": ["gmao.entreprise.lan"]}))
        self.ok(client.post("compte", {"prenom": "Nicolas", "nom": "Briand", "mot_de_passe": MOT_DE_PASSE}))
        self.ok(client.post("certificat", {"mode": "mandataire"}))
        self.ok(client.post("demarrage", {"demarrage": "aucun", "veille_desactivee": False}))
        self.ok(client.post("sauvegardes", {"dossier": ""}))
        self.ok(client.post("terminer", {"base": "vide", "langue_defaut": "en"}))
        donnees = Path(instance.config.dossier_donnees)
        self.assertEqual(sorted(p.name for p in donnees.glob("*.csv")), ["parametres.csv"])
        self.assertEqual(lire_csv(donnees / "parametres.csv"), (["cle", "valeur"], [["version_schema", "3"],
                                                                                     ["langue_defaut", "en"]]))

    def test_langue_non_declaree_400_et_rien_d_ecrit(self):
        # T296 : langue_defaut n'est acceptée que si js/i18n/langues.js la déclare ; message par code (T246).
        self.assertEqual(serveur.langues_declarees(), langues_declarees(RACINE))
        self.assertEqual(serveur.langues_declarees()[:2], ["fr", "en"])
        client, instance = self.lancer()
        self.solo_ce_pc_jusqu_au_recapitulatif(client, "Nicolas", "Briand")
        donnees = Path(instance.config.dossier_donnees)
        avant = {p.name: p.read_bytes() for p in donnees.glob("*.csv")}
        for valeur in ("xx", "EN", "", None, 3, ["en"]):
            with self.subTest(valeur=valeur):
                reponse = client.post("terminer", {"base": "vide", "langue_defaut": valeur})
                self.assertEqual(reponse.statut, 400, reponse.octets)
                corps = reponse.json()
                self.assertEqual(corps["erreur_code"], "installation.langue_inconnue")
                self.assertEqual(corps["erreur_valeurs"], {"langues": serveur.langues_declarees()})
                self.assertIn("fr, en", corps["erreur"])
        self.assertEqual({p.name: p.read_bytes() for p in donnees.glob("*.csv")}, avant)
        self.assertFalse(Path(instance.config.reglages["_fichier"]).exists())
        self.assertTrue((donnees / "installation.json").exists())
        self.assertEqual(self.enregistreur.relances, [])
        self.ok(client.post("terminer", {"base": "vide", "langue_defaut": "en"}))
        self.assertEqual(parametres_de(donnees)["langue_defaut"], "en")

    def test_jeu_de_demo_illisible_500_et_rien_d_ecrit(self):
        client, instance = self.lancer()
        self.solo_ce_pc_jusqu_au_recapitulatif(client, "Nicolas", "Briand")
        donnees = Path(instance.config.dossier_donnees)
        avant = {p.name: p.read_bytes() for p in donnees.glob("*.csv")}
        tronque = self.dossier / "demo-tronque.js"
        tronque.write_text("const DEMO_DONNEES = {\n  dateReference: \"2026-10-19\",\n  tables: {\n"
                           "    localisations: \"id;libelle\\r\\n\",\n  },\n};\n", encoding="utf-8")
        for fichier in (str(self.dossier / "absent.js"), str(tronque)):
            with self.subTest(fichier=fichier):
                with mock.patch.object(serveur, "FICHIER_JEU_DE_DEMO", fichier):
                    reponse = client.post("terminer", {"base": "demo"})
                self.assertEqual(reponse.statut, 500, reponse.octets)
                self.assertIn("demo-donnees.js", reponse.json()["erreur"])
        self.assertEqual({p.name: p.read_bytes() for p in donnees.glob("*.csv")}, avant)
        self.assertFalse(Path(instance.config.reglages["_fichier"]).exists())
        self.assertTrue((donnees / "installation.json").exists())
        self.assertEqual(self.enregistreur.relances, [])


class TestJeuDeDemo(unittest.TestCase):

    def test_lire_jeu_de_demo_rend_les_csv_de_donnees_demo(self):
        date_reference, textes = serveur.lire_jeu_de_demo()
        self.assertEqual(date_reference, re.search(r'dateReference: "([0-9-]+)"', (RACINE / "js" / "demo-donnees.js")
                                                   .read_text(encoding="utf-8")).group(1))
        self.assertEqual(sorted(textes), sorted(serveur.TABLES))
        for table, texte in textes.items():
            with self.subTest(table=table):
                self.assertEqual(serveur.BOM_UTF8 + texte.encode("utf-8"), (commun.DOSSIER_DEMO / (table + ".csv")).read_bytes())

    def test_cellules_decalees_sont_les_colonnes_date_du_schema(self):
        types = colonnes_dates_du_schema()
        self.assertEqual(sorted(types), sorted(serveur.TABLES))
        _, textes = serveur.lire_jeu_de_demo()
        for table, texte in textes.items():
            with self.subTest(table=table):
                entete, avant = lignes_csv(serveur.BOM_UTF8 + texte.encode("utf-8"))
                entete_apres, apres = lignes_csv(serveur.decaler_texte_csv(texte, 7))
                self.assertEqual(entete_apres, entete)
                changees = {entete[i] for a, b in zip(avant, apres) for i in range(len(a)) if a[i] != b[i]}
                dates_presentes = {entete[i] for a in avant for i in range(len(a)) if MOTIF_DEBUT_DE_DATE.match(a[i])}
                self.assertEqual(dates_presentes, types[table])              # le serveur décale par la valeur : même jeu
                self.assertEqual(changees, dates_presentes)
                self.assertEqual(serveur.decaler_texte_csv(texte, 0), serveur.BOM_UTF8 + texte.encode("utf-8"))


# ---------------------------------------------------------------------------
# Déplacer Prévo (deplacer_installation, la route, « Rester ici »)
# ---------------------------------------------------------------------------

class TestDeplacement(CasAssistant):

    def test_deplacer_installation_copie_tout_puis_relance(self):
        self.assertEqual(serveur.DOSSIER_CONSEILLE_WINDOWS, "C:\\Prevo")
        source = fabriquer_prevo(self.dossier / "Prevo-telechargement")
        config = configuration(source)
        enregistreur = Enregistreur()
        config.relancer = enregistreur.relancer
        brouillon = serveur.brouillon_neuf(config, "seul")
        brouillon["etapes"]["deplacer"] = "fait"                             # comme la route : noté avant la copie
        serveur.ecrire_brouillon(config, brouillon)
        avant = empreintes(source)
        cible = self.dossier / "cible" / "Prevo"
        resultat = serveur.deplacer_installation(config, str(cible), brouillon)
        self.assertEqual((resultat["vers"], resultat["relance"]), (str(cible), True))
        self.assertEqual(enregistreur.relances, [str(cible)])
        attendus = empreintes_a_copier(source)
        self.assertEqual(empreintes(cible), attendus)                        # chaque fichier, SHA-256 égal
        self.assertEqual(resultat["copie"], len(attendus))
        self.assertGreaterEqual(len(attendus), 5)
        self.assertFalse((cible / ".git").exists())
        self.assertFalse((cible / "js" / "__pycache__").exists())
        copie = json.loads((cible / "donnees" / "installation.json").read_text(encoding="utf-8"))
        self.assertEqual((copie["etapes"]["deplacer"], copie["situation"]), ("fait", "seul"))
        self.assertEqual(empreintes(source), avant)                          # dossier d'origine intact
        # Cibles refusées : non vide, dans la source, au-dessus, relative ; rien de relancé.
        occupee = self.dossier / "occupee"
        occupee.mkdir()
        (occupee / "x.txt").write_text("x", encoding="ascii")
        for vers, attendu in ((str(occupee), "n'est pas vide"), (str(source / "sous"), "ni dans"),
                              (str(self.dossier), "ni dans"), ("Prevo", "complet"), (str(source), "déjà")):
            with self.subTest(vers=vers):
                with self.assertRaises(serveur.ErreurHttp) as refus:
                    serveur.deplacer_installation(config, vers, brouillon)
                self.assertEqual(refus.exception.statut, 400)
                self.assertIn(attendu, str(refus.exception))
        self.assertEqual(enregistreur.relances, [str(cible)])
        self.assertEqual(empreintes(source), avant)

    def test_route_appelle_deplacer_installation_et_rester_ici(self):
        source = fabriquer_prevo(self.dossier / "Prevo-bureau")
        client, instance = self.lancer(source)
        self.ok(client.post("situation", {"situation": "seul"}))
        self.assertFalse(self.ok(client.get("etat"))["dans_dossier_conseille"])
        # « Rester ici » : mémorisé dans le brouillon, étape à faire, rien de copié ni relancé.
        reponse = self.ok(client.post("deplacer", {"rester": True}))
        self.assertTrue(reponse["brouillon"]["deplacement_refuse"])
        self.assertEqual(reponse["etapes"]["deplacer"], "a_faire")
        etat = self.ok(client.get("etat"))
        self.assertTrue(etat["brouillon"]["deplacement_refuse"])
        self.assertEqual(self.enregistreur.relances, [])
        # Un déplacement refusé laisse l'étape à faire et le refus noté.
        self.assertEqual(client.post("deplacer", {"vers": "Prevo"}).statut, 400)
        etat = self.ok(client.get("etat"))
        self.assertEqual((etat["etapes"]["deplacer"], etat["brouillon"]["deplacement_refuse"]), ("a_faire", True))
        # Puis le déplacement : la route passe par deplacer_installation (câblage), le refus est effacé.
        cible = self.dossier / "cible" / "Prevo"
        with mock.patch.object(serveur, "deplacer_installation", wraps=serveur.deplacer_installation) as fonction:
            reponse = self.ok(client.post("deplacer", {"vers": str(cible)}))
        fonction.assert_called_once()
        self.assertIs(fonction.call_args.args[0], instance.config)
        self.assertEqual(fonction.call_args.args[1], str(cible))
        self.assertEqual((reponse["vers"], reponse["relance"], reponse["etapes"]["deplacer"]), (str(cible), True, "fait"))
        self.assertEqual(self.enregistreur.relances, [str(cible)])
        self.assertEqual(empreintes(cible), empreintes_a_copier(source))
        self.assertEqual(reponse["copie"], len(empreintes_a_copier(source)))
        copie = json.loads((cible / "donnees" / "installation.json").read_text(encoding="utf-8"))
        self.assertNotIn("deplacement_refuse", copie)
        self.assertEqual(copie["etapes"]["deplacer"], "fait")
        self.assertNotIn("deplacement_refuse", json.loads((source / "donnees" / "installation.json").read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# Profils de 1.2 : remplacés par la connexion avec les comptes, gardés sans
# ---------------------------------------------------------------------------

class TestProfils(CasNavigateur):

    def nouvelle_page(self, role=None, serveur_reel=None):
        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
        contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        self.addCleanup(contexte.close)
        preregler_profil(contexte, "responsable")                             # le profil de 1.2, mémorisé sur le poste
        if role:
            serveur_reel.poser_session(contexte, role, profil=False)
        page = contexte.new_page()
        self.surveiller(page)
        page.add_init_script(SUIVI_ETATS_JS)
        return page

    def test_profil_memorise_ignore_avec_les_comptes(self):
        self.autoriser_erreur(ERREUR_401_SONDE)
        with ServeurPrevo(comptes=True) as serveur_reel:
            page = self.nouvelle_page()
            page.goto(serveur_reel.url + "/")
            page.wait_for_function("document.documentElement.dataset.etat === 'connexion'")
            self.assertTrue(page.is_visible("#ecran-connexion"))
            self.assertTrue(page.is_hidden("#ecran-profil"))
            self.assertNotIn("profil", page.evaluate("window.__etats"))
            self.assertEqual(page.evaluate("JSON.parse(localStorage.getItem('prevo.profil')).type"), "responsable")
            self.assertTrue(page.evaluate("App.comptesExiges()"))
            # Avec une session de technicien : le profil vient du compte, pas du poste.
            page = self.nouvelle_page("technicien", serveur_reel)
            page.goto(serveur_reel.url + "/")
            attendre_pret(page)
            self.assertNotIn("profil", page.evaluate("window.__etats"))
            self.assertEqual(page.evaluate("App.profil"), {"type": "technicien", "nom": "Julien Moreau", "technicienId": "TEC-0001"})
            self.assertTrue(page.evaluate("App.estTechnicien() && !App.estResponsable()"))
            self.assertNotIn("Paramètres", page.inner_text("#menu"))
            self.assertEqual(page.evaluate("JSON.parse(localStorage.getItem('prevo.profil')).type"), "responsable")   # jamais réécrit

    def test_profil_memorise_garde_sans_comptes(self):
        with ServeurPrevo() as serveur_reel:                                  # portée « ce PC » : Solo, aucun compte
            page = self.nouvelle_page()
            page.goto(serveur_reel.url + "/")
            attendre_pret(page)
            self.assertEqual(page.evaluate("window.__etats"), ["chargement", "pret"])
            self.assertEqual(page.evaluate("App.profil.type"), "responsable")
            self.assertFalse(page.evaluate("App.comptesExiges()"))
            self.assertIsNone(page.evaluate("App.session"))
            self.assertIn("Responsable ·", page.inner_text("#libelle-profil"))


# ---------------------------------------------------------------------------
# L'écran : ligne de migration, « Par quoi commencer ? », « Rester ici », « Déplacer »
# ---------------------------------------------------------------------------

class TestEcran(CasInstallation):

    def solo_jusqu_au_recapitulatif(self, prenom, nom):
        page = self.page
        self.cocher("situation", "seul")
        self.continuer()
        self.attendre_etape("portee")
        self.continuer()
        self.attendre_etape("compte")
        page.fill("#inst-prenom", prenom)
        page.fill("#inst-nom", nom)
        self.continuer()
        self.attendre_etape("demarrage")
        self.cocher("demarrage", "aucun")
        self.continuer()
        self.attendre_etape("sauvegardes")
        page.click("#inst-sauvegardes-plus-tard")
        self.attendre_etape("recapitulatif")

    def test_base_1_2_annoncee_sans_choix_et_rester_ici(self):
        page = self.page
        instance = self.lancer(source=commun.DOSSIER_DEMO)
        self.ouvrir_assistant(instance)
        self.assertIn("Tant que l'installation n'est pas terminée", page.inner_text("#installation-premiere-ligne"))
        migration = page.inner_text("#inst-migration")
        self.assertIn("Vos données de Prévo 1.2 sont là", migration)
        self.assertIn("%d fichiers" % commun.NB_TABLES, migration)
        self.assertIn("dernière modification le", migration)
        self.assertIn("gardées", migration)
        self.solo_jusqu_au_recapitulatif("Julien", "Moreau")
        self.assertEqual(page.locator("#inst-base").count(), 0)              # base présente : rien à demander
        page.wait_for_selector("#inst-dossier", state="visible")
        dossier = page.inner_text("#inst-dossier")
        self.assertIn("Déplacer Prévo dans C:\\Prevo (recommandé)", dossier)
        self.assertIn("Rester ici", dossier)
        self.assertIn("vérifié", dossier)
        self.assertIn("pas supprimé", dossier)
        page.click("#inst-dossier-garder")
        page.wait_for_selector("#inst-dossier", state="hidden")
        brouillon = json.loads((self.dossier / "donnees" / "installation.json").read_text(encoding="utf-8"))
        self.assertTrue(brouillon["deplacement_refuse"])
        self.assertEqual(self.enregistreur.relances, [])
        page.reload()
        page.wait_for_function("document.documentElement.dataset.etat === 'installation'")
        self.attendre_etape("recapitulatif")
        page.wait_for_selector("#fiche-qr-ouvrir svg")
        self.assertEqual(page.locator("#inst-dossier").count(), 0)           # plus reproposé
        self.assertEqual(page.locator("#inst-migration").count(), 0)         # (étape 8 : la ligne est à l'étape 1)

    def test_base_absente_demo_puis_terminer(self):
        page = self.page
        instance = self.lancer()
        instance.config.horloge = lambda: INSTANT_FIXE
        self.ouvrir_assistant(instance)
        self.assertEqual(page.locator("#inst-migration").count(), 0)
        self.solo_jusqu_au_recapitulatif("Nicolas", "Briand")
        page.wait_for_selector("#inst-base", state="visible")
        self.assertIn("Par quoi commencer", page.inner_text("#inst-base"))
        self.assertTrue(page.is_checked('#inst-base input[name="base"][value="vide"]'))
        self.cocher("base", "demo")
        page.click("#inst-dossier-garder")
        page.wait_for_selector("#inst-dossier", state="hidden")
        page.click("#inst-terminer")
        page.wait_for_selector("#inst-attente", state="visible")
        page.wait_for_function("document.getElementById('inst-terminer').disabled")
        donnees = self.dossier / "donnees"
        self.assertEqual(sorted(p.stem for p in donnees.glob("*.csv")), sorted(serveur.TABLES))
        entete, lignes = lire_csv(donnees / "techniciens.csv")
        self.assertEqual(lignes[4][:3], ["TEC-0005", "Briand", "Nicolas"])
        self.assertEqual(parametres_de(donnees)["solo_technicien_id"], "TEC-0005")
        self.assertEqual(self.enregistreur.relances, [None])
        instance.config.reglages["_present"] = True                         # « le serveur relancé » : installation faite
        page.wait_for_function("location.hash === '#/accueil' && document.documentElement.dataset.etat === 'profil'")

    def test_deplacer_depuis_l_ecran_puis_reprise_a_l_etape_8(self):
        page = self.page
        # Tient lieu de C:\Prevo (jamais le vrai) : hors du dossier de Prévo simulé (self.dossier), sinon 400.
        ailleurs = Path(tempfile.mkdtemp(prefix="prevo-installation-cible-"))
        self.addCleanup(shutil.rmtree, ailleurs, True)
        cible = ailleurs / "Prevo"
        patch = mock.patch.object(serveur, "DOSSIER_CONSEILLE_WINDOWS", str(cible))
        patch.start()
        self.addCleanup(patch.stop)
        instance = self.lancer(source=commun.DOSSIER_DEMO)
        self.ouvrir_assistant(instance)
        self.solo_jusqu_au_recapitulatif("Julien", "Moreau")
        page.wait_for_selector("#inst-dossier", state="visible")
        self.assertIn(str(cible), page.inner_text("#inst-dossier"))
        page.click("#inst-deplacer")
        page.wait_for_selector("#inst-attente", state="visible")
        self.assertIn("copié", page.inner_text("#inst-attente"))
        self.assertIn("n'est pas supprimé", page.inner_text("#inst-attente"))
        page.wait_for_function("document.getElementById('inst-terminer').disabled")
        self.assertEqual(self.enregistreur.relances, [str(cible)])
        self.assertEqual(empreintes(cible), empreintes_a_copier(self.dossier))
        self.assertTrue((cible / "donnees" / "installation.json").is_file())
        self.assertEqual(page.evaluate("location.hash"), "#/installation")  # pas encore relancé : la page attend
        instance.config.dossier_application = str(cible)                     # « le serveur relancé » tourne depuis la copie
        # La page se recharge (le bouton n'existe plus un instant) puis l'assistant revient, boutons actifs.
        page.wait_for_function("""(() => { const bouton = document.getElementById('inst-terminer');
          return document.documentElement.dataset.etat === 'installation' && Boolean(bouton) && !bouton.disabled; })()""")
        self.attendre_etape("recapitulatif")
        self.assertEqual(page.locator("#inst-dossier").count(), 0)           # déjà dans le dossier conseillé
        self.assertEqual(page.locator("#inst-base").count(), 0)


if __name__ == "__main__":
    unittest.main()
