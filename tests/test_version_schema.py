"""Tests du passage de parametres.version_schema au format courant (tâche T37, ARCHITECTURE.md §14.1 ;
format 3 depuis le lot 6, §20.2 ; chantier « socle de données », T186 : étapes explicites, D168).

Décision de Nicolas (2026-10-20) : JUSTE AVANT que version_schema passe au format courant sur une base
existante, Prévo fait une sauvegarde automatique « AAAA-MM-JJ_HHMMSS_avant-format-vN » (N = format
visé, 3 depuis le lot 6 ; une base au format 1 passe directement au format 3, une seule sauvegarde),
restaurable depuis Paramètres comme les autres (Donnees.migrerAuFormatCourant(), ancien nom
Donnees.mettreAJourVersionSchema()). Depuis T186 (D168), le NAVIGATEUR ne fait ce passage qu'en mode dossier
et en démo, par étapes explicites (Formats.migrer) : chaque table que le passage complète est réécrite, puis
version_schema, avec une ligne de journal par étape. En mode serveur, c'est le serveur qui le fait à son
démarrage (T185) : le navigateur n'écrit rien et montre un bandeau au responsable.

    serveur  : le navigateur ne fait plus le passage : appel sans effet (ni sauvegarde, ni écriture, ni
               journal) ; une base au format 2 (sans wiki_pages.csv ni wiki_journal.csv, ordres_travail.csv
               sans la colonne astuce) ouverte par le responsable : aucun fichier changé à l'octet, pas d'OT
               préventif généré, bandeau ; les tables du wiki lues vides, la colonne astuce signalée en
               simple information ; écran Paramètres « Avant format 3 » (sauvegarde demandée à l'API) puis
               restauration de toutes les tables ; API brute (motif inconnu, « ../x », corps vide) ;
    dossier  : passage avec StockageDossier (dossier simulé dans l'OPFS) : sauvegarde d'abord, tables du
               format 1 complétées, version 3, deux lignes de journal (une par étape), second appel sans
               effet, restauration ; sauvegarde impossible → rien n'est écrit, ErreurStockage claire ; un
               autre poste passé au format 3 entre-temps : version_schema pas réécrite ; règles de noms
               identiques à celles du serveur ;
    démo     : aucune sauvegarde, aucune erreur ; passage en mémoire seulement.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_version_schema.py" -v
"""
import csv
import datetime
import io
import http.client
import json
import re
import shutil
import unittest

from commun import FORMAT_COURANT as FORMAT_COURANT_NUM
from commun import (CasNavigateur, RACINE, ServeurPrevo, ServeurStatique, attendre_pret,
                    charger_scripts, installer_dossier_simule, preregler_profil, url_fichier)

PARAMETRES_V1 = RACINE / "tests" / "fixtures" / "v1" / "parametres.csv"
TABLES_V1 = ("demandes", "equipements", "ordres_travail", "parametres")   # fichiers de tests/fixtures/v1
MOTIF_NOM_AVANT_FORMAT_2 = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}_avant-format-v2$")
FORMAT_COURANT = str(FORMAT_COURANT_NUM)                # Schema.version (js/schema.js)
MOTIF_NOM_AVANT_FORMAT_COURANT = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}_avant-format-v%d$" % FORMAT_COURANT_NUM)
MOTIF_AVANT_FORMAT_COURANT = "avant-format-v%d" % FORMAT_COURANT_NUM
MOTIF_AVANT_FORMAT_TROP_RECENT = "avant-format-v%d" % (FORMAT_COURANT_NUM + 1)   # hors de la liste fermée
MOTIF_NOM_MANUEL = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}$")
DEBUT_ERREUR_SAUVEGARDE = "Sauvegarde avant le passage au format %d impossible : " % FORMAT_COURANT_NUM
FIN_ERREUR_SAUVEGARDE = " ; la mise à jour sera retentée à la prochaine ouverture."

# Appel de Donnees.mettreAJourVersionSchema() dans la page : { ok, valeur } ou { ok: false, nom, message }.
APPELER_MISE_A_JOUR = """async () => {
  try {
    return { ok: true, valeur: await Donnees.mettreAJourVersionSchema() };
  } catch (erreur) {
    return { ok: false, nom: erreur.name, message: erreur.message };
  }
}"""


# ---------------------------------------------------------------------------
# Lecture des CSV (comme un autre poste ou Excel)
# ---------------------------------------------------------------------------

def lignes_csv(octets):
    """Lignes (dictionnaires) d'un CSV Prévo donné en octets ; valeurs telles que dans le fichier."""
    texte = octets.decode("utf-8-sig")
    lecteur = csv.reader(texte.splitlines(), delimiter=";")
    entete = next(lecteur)
    return [dict(zip(entete, cellules)) for cellules in lecteur if any(cellules)]


def version_schema(octets):
    """Valeur de version_schema dans un parametres.csv (sans l'apostrophe de protection), ou None."""
    for ligne in lignes_csv(octets):
        if ligne["cle"] == "version_schema":
            valeur = ligne["valeur"]
            return valeur[1:] if valeur.startswith("'") else valeur
    return None


def actions_journal_version(octets_journal):
    """Actions du journal qui concernent la ligne version_schema de parametres.csv."""
    if octets_journal is None:
        return []
    return [ligne["action"] for ligne in lignes_csv(octets_journal)
            if ligne["table"] == "parametres" and ligne["id_ligne"] == "version_schema"]


# ---------------------------------------------------------------------------
# Mode serveur
# ---------------------------------------------------------------------------

class CasServeurV1(CasNavigateur):
    """Serveur de test sur le jeu de démo, dont parametres.csv est celui du lot 1 (version_schema = 1)."""

    def ouvrir_application_v1(self, serveur, route="#/accueil"):
        # Depuis T28, le DÉMARRAGE de l'application fait lui-même le passage au format courant (js/app.js ;
        # testé dans tests/test_preventif.py, famille « demarrage »). Pour tester ici l'appel
        # explicite sur une base au format 1, l'application est ouverte (jeu de démo, déjà au format
        # courant : rien n'est fait), puis le parametres.csv du lot 1 est installé et relu par la page.
        preregler_profil(self.contexte, "responsable")
        self.page.goto(serveur.url + "/" + route)
        attendre_pret(self.page)
        self.assertEqual(self.sauvegardes(serveur, "*_avant-format-v*"), [])
        shutil.copyfile(str(PARAMETRES_V1), str(serveur.dossier / "parametres.csv"))
        self.page.evaluate("Donnees.rechargerTable('parametres')")
        self.assertEqual(self.page.evaluate("Donnees.parametre('version_schema')"), "1")
        return self.page

    def mettre_a_jour(self):
        return self.page.evaluate(APPELER_MISE_A_JOUR)

    @staticmethod
    def sauvegardes(serveur, motif="*"):
        dossier = serveur.dossier / "sauvegardes"
        return sorted(p.name for p in dossier.glob(motif) if p.is_dir()) if dossier.is_dir() else []

    @staticmethod
    def octets(serveur, *chemin):
        fichier = serveur.dossier.joinpath(*chemin)
        return fichier.read_bytes() if fichier.is_file() else None


def resultat_sans_effet(depart):
    """Valeur rendue par Donnees.migrerAuFormatCourant() quand il n'écrit rien."""
    return {"misAJour": False, "sauvegarde": None, "depart": depart, "tables": [], "abimees": []}


class TestServeur(CasServeurV1):
    """D168 (T186) : en mode serveur, le navigateur ne fait plus le passage au format courant (le serveur le fait
    à son démarrage, T185)."""

    def test_le_navigateur_ne_fait_plus_le_passage_ni_sauvegarde_ni_ecriture_ni_journal(self):
        with ServeurPrevo() as serveur:
            self.ouvrir_application_v1(serveur)
            journal_avant = self.octets(serveur, "journal.csv")
            sauvegardes_avant = self.sauvegardes(serveur)
            for _ in range(2):
                resultat = self.mettre_a_jour()
                self.assertTrue(resultat["ok"], resultat)
                self.assertEqual(resultat["valeur"], resultat_sans_effet(1))
            self.assertEqual(self.sauvegardes(serveur), sauvegardes_avant)
            self.assertEqual(self.sauvegardes(serveur, "*_avant-format-v*"), [])
            self.assertEqual(self.octets(serveur, "parametres.csv"), PARAMETRES_V1.read_bytes())
            self.assertEqual(self.page.evaluate("Donnees.parametre('version_schema')"), "1")
            self.assertEqual(self.octets(serveur, "journal.csv"), journal_avant)

    def test_ecran_parametres_avant_format_courant_puis_restauration_de_toutes_les_tables(self):
        with ServeurPrevo() as serveur:
            page = self.ouvrir_application_v1(serveur)
            # La sauvegarde « avant-format-v3 » est celle que le serveur fait avant son passage (ici demandée à l'API).
            statut, reponse = demander_sauvegarde(serveur, {"motif": MOTIF_AVANT_FORMAT_COURANT})
            self.assertEqual(statut, 200, reponse)
            nom = reponse["sauvegarde"]
            self.assertRegex(nom, MOTIF_NOM_AVANT_FORMAT_COURANT)
            # Puis le passage (fait ailleurs) : version 3 sur le disque.
            passe = PARAMETRES_V1.read_bytes().replace(b"version_schema;'1", ("version_schema;'" + FORMAT_COURANT).encode())
            (serveur.dossier / "parametres.csv").write_bytes(passe)
            page.evaluate("Donnees.rechargerTable('parametres')")
            self.assertEqual(version_schema(self.octets(serveur, "parametres.csv")), FORMAT_COURANT)

            page.evaluate("location.hash = '#/parametres'")
            page.wait_for_selector('#carte-sauvegardes button[data-restaurer="%s"]' % nom)
            ligne = page.locator('#carte-sauvegardes tr:has(button[data-restaurer="%s"])' % nom)
            self.assertEqual(ligne.locator(".badge").inner_text().strip(), "Avant format %d" % FORMAT_COURANT_NUM)
            self.assertIn("info", ligne.locator(".badge").get_attribute("class").split())
            heure = "%s:%s:%s" % (nom[11:13], nom[13:15], nom[15:17])
            self.assertIn(" à " + heure, ligne.inner_text())
            self.assertEqual(page.evaluate("n => Parametres.decrireSauvegarde(n).type", nom), "Avant format %d" % FORMAT_COURANT_NUM)

            # « Restaurer… » → toutes les tables (choix par défaut).
            page.click('button[data-restaurer="%s"]' % nom)
            page.wait_for_selector("#fenetre-restauration")
            self.assertIn("avant format %d" % FORMAT_COURANT_NUM, page.inner_text("#fenetre-restauration"))
            page.click("dialog .fenetre-actions .btn-danger")
            page.wait_for_selector("#nom-copie-securite")
            self.assertIn("parametres", page.inner_text("#message-action"))
            self.assertEqual(self.octets(serveur, "parametres.csv"), PARAMETRES_V1.read_bytes())
            self.assertEqual(version_schema(self.octets(serveur, "parametres.csv")), "1")
            self.assertEqual(page.evaluate("Donnees.parametre('version_schema')"), "1")


def retirer_derniere_colonne(chemin, nom):
    """Réécrit un CSV de Prévo (BOM, « ; », CRLF) sans sa dernière colonne, qui doit s'appeler `nom` : le
    fichier tel qu'une base au format 2 l'avait (lot 6 : ordres_travail.csv sans la colonne astuce)."""
    texte = chemin.read_bytes().decode("utf-8-sig")
    lignes = list(csv.reader(io.StringIO(texte, newline=""), delimiter=";"))
    assert lignes[0][-1] == nom, lignes[0][-3:]
    sortie = io.StringIO(newline="")
    csv.writer(sortie, delimiter=";", lineterminator="\r\n").writerows(ligne[:-1] for ligne in lignes)
    chemin.write_bytes(b"\xef\xbb\xbf" + sortie.getvalue().encode("utf-8"))


class TestFormat2ModeServeur(CasServeurV1):
    """Lot 6 (§20.2) et T186 (D168) : une base au format 2 (la démo sans wiki_pages.csv, wiki_journal.csv ni colonne
    astuce) ouverte en mode serveur : le navigateur n'écrit rien, il le dit au responsable."""

    def test_ouverture_d_une_base_au_format_2_aucun_fichier_change_bandeau_au_responsable(self):
        with ServeurPrevo() as serveur:
            parametres = serveur.dossier / "parametres.csv"
            octets_v3 = parametres.read_bytes()
            self.assertIn(("version_schema;'" + FORMAT_COURANT).encode(), octets_v3)
            parametres.write_bytes(octets_v3.replace(("version_schema;'" + FORMAT_COURANT).encode(), b"version_schema;'2"))
            for nom in ("wiki_pages.csv", "wiki_journal.csv"):
                (serveur.dossier / nom).unlink()
            retirer_derniere_colonne(serveur.dossier / "ordres_travail.csv", "habilitation_requise")   # format 4
            retirer_derniere_colonne(serveur.dossier / "ordres_travail.csv", "astuce")
            avant = {p.name: p.read_bytes() for p in serveur.dossier.glob("*.csv")}
            sauvegardes_avant = self.sauvegardes(serveur)   # T187 : celles du démarrage (du jour, avant-mise-a-jour)
            self.assertNotIn("wiki_pages.csv", avant)
            self.assertNotIn(b";astuce", avant["ordres_travail.csv"].split(b"\r\n", 1)[0])

            # Responsable : il verrait le bandeau, et générerait les OT préventifs échus (RG5) si la base était au
            # format courant ; ici rien n'est généré (ordres_travail.csv et ot_operations.csv inchangés).
            preregler_profil(self.contexte, "responsable")
            self.autoriser_erreur(re.compile(r"status of 404.*/api/csv/wiki_(pages|journal)"))   # fichier absent = table vide
            self.page.goto(serveur.url + "/#/accueil")
            attendre_pret(self.page)

            # Aucune sauvegarde, aucun fichier changé à l'octet ni créé.
            self.assertEqual(self.sauvegardes(serveur), sauvegardes_avant)
            apres = {p.name: p.read_bytes() for p in serveur.dossier.glob("*.csv")}
            self.assertEqual(apres, avant)
            self.assertEqual(self.page.evaluate("Donnees.parametre('version_schema')"), "2")
            alertes = self.page.inner_text("#alertes-app")
            self.assertIn("pas encore au format %d" % FORMAT_COURANT_NUM, alertes)
            self.assertIn("relancez Prévo", alertes)
            # Les tables du wiki absentes sont lues vides ; la colonne astuce absente : lue vide, simple information.
            self.assertEqual(self.page.evaluate("Donnees.lignes('wiki_pages').length"), 0)
            self.assertEqual(self.page.evaluate("Donnees.lignes('wiki_journal').length"), 0)
            self.assertEqual(self.page.evaluate(
                "Donnees.lignes('ordres_travail').filter((ot) => ot.astuce !== '').length"), 0)
            self.assertEqual(self.page.evaluate(
                "Donnees.problemes().filter((p) => p.table === 'ordres_travail' && p.champ === 'astuce')"
                ".map((p) => p.gravite)"), ["info"])
            self.assertEqual(self.page.evaluate(
                "Donnees.problemes().filter((p) => p.gravite !== 'info' && p.table.startsWith('wiki_')).length"), 0)

    def test_demandeur_aucun_bandeau_rien_n_est_ecrit(self):
        with ServeurPrevo() as serveur:
            shutil.copyfile(str(PARAMETRES_V1), str(serveur.dossier / "parametres.csv"))
            avant = {p.name: p.read_bytes() for p in serveur.dossier.glob("*.csv")}
            sauvegardes_avant = self.sauvegardes(serveur)   # T187 : celles du démarrage (du jour, avant-mise-a-jour)
            preregler_profil(self.contexte, "demandeur", nom="Lucie Martin")
            self.page.goto(serveur.url + "/#/accueil")
            attendre_pret(self.page)
            self.assertEqual({p.name: p.read_bytes() for p in serveur.dossier.glob("*.csv")}, avant)
            self.assertEqual(self.sauvegardes(serveur), sauvegardes_avant)
            self.assertNotIn("pas encore au format", self.page.inner_text("#app"))


# ---------------------------------------------------------------------------
# API brute du serveur (http.client) : motif de sauvegarde
# ---------------------------------------------------------------------------

def requete(serveur, methode, chemin, corps=b"", entetes=None):
    """(statut, objet JSON) d'une requête envoyée telle quelle au serveur de test."""
    connexion = http.client.HTTPConnection("127.0.0.1", serveur.port, timeout=15)
    try:
        envoyees = {"X-Prevo": "1", "Content-Length": str(len(corps))}
        envoyees.update(entetes or {})
        connexion.request(methode, chemin, body=corps, headers=envoyees)
        reponse = connexion.getresponse()
        return reponse.status, json.loads(reponse.read().decode("utf-8"))
    finally:
        connexion.close()


def demander_sauvegarde(serveur, corps):
    if not isinstance(corps, bytes):
        corps = json.dumps(corps).encode("utf-8")
    return requete(serveur, "POST", "/api/sauvegarde", corps, {"Content-Type": "application/json"})


def demander_restauration(serveur, nom, tables=None):
    demande = {"sauvegarde": nom}
    if tables is not None:
        demande["tables"] = tables
    return requete(serveur, "POST", "/api/restauration", json.dumps(demande).encode("utf-8"),
                   {"Content-Type": "application/json"})


# Noms de sauvegarde : (nom, valide). Un nom valide mais absent → 404 (serveur) / « introuvable »
# (dossier) ; un nom invalide → 400 / « Nom de sauvegarde invalide ». Mêmes réponses des deux côtés.
NOMS_A_CONTROLER = (
    ("1999-01-01", True),
    ("1999-01-01_120000", True),
    ("1999-01-01_120000_avant-restauration", True),
    ("1999-01-01_120000_avant-format-v2", True),
    ("1999-01-01_120000_avant-format-v12", True),
    ("1999-01-01_avant-format-v2", False),           # sans heure
    ("1999-01-01_120000_avant-format-v", False),
    ("1999-01-01_120000_avant-format-vx", False),
    ("1999-01-01_120000_avant-format-v2x", False),
    ("1999-01-01_120000_avant-format-v2/../..", False),
    ("1999-01-01_120000_avant-format-v２", False),  # chiffre « pleine largeur »
    ("1999-01-01_120000_inconnu", False),
    ("../x", False),
)


class TestApiMotif(unittest.TestCase):

    def test_motif_inconnu_ou_traversee_400_corps_vide_nom_manuel_et_motif_accepte(self):
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier / "sauvegardes"
            avant = sorted(p.name for p in dossier.iterdir())
            for corps in ({"motif": "inconnu"}, {"motif": "../x"}, {"motif": MOTIF_AVANT_FORMAT_TROP_RECENT},
                          {"motif": "avant-format-v2/../.."}, {"motif": 2}, {"motif": ["avant-format-v2"]},
                          ["avant-format-v2"], b"pas du json", b"\xff\xfe"):
                with self.subTest(corps=corps):
                    statut, reponse = demander_sauvegarde(serveur, corps)
                    self.assertEqual(statut, 400, reponse)
                    self.assertIn("erreur", reponse)
            self.assertEqual(sorted(p.name for p in dossier.iterdir()), avant)    # rien n'a été créé
            statut, reponse = demander_sauvegarde(serveur, {"motif": "inconnu"})
            self.assertIn("Motif de sauvegarde refusé", reponse["erreur"])

            # Corps vide : comme avant, sauvegarde manuelle « AAAA-MM-JJ_HHMMSS ».
            statut, reponse = requete(serveur, "POST", "/api/sauvegarde", b"")
            self.assertEqual(statut, 200, reponse)
            self.assertRegex(reponse["sauvegarde"], MOTIF_NOM_MANUEL)
            # Objet sans motif (ou motif null) : sauvegarde manuelle aussi, donc soumise au plafond d'une par minute
            # (T175, D133) : 429 tant que la précédente a moins d'une minute ; acceptée une fois la précédente vieillie
            # de deux minutes (la minute se lit sur son nom).
            statut, refus = demander_sauvegarde(serveur, {"motif": None})
            self.assertEqual(statut, 429, refus)
            premiere = reponse["sauvegarde"]
            vieillie = (datetime.datetime.strptime(premiere, "%Y-%m-%d_%H%M%S")
                        - datetime.timedelta(minutes=2)).strftime("%Y-%m-%d_%H%M%S")
            (dossier / premiere).rename(dossier / vieillie)
            statut, reponse = demander_sauvegarde(serveur, {"motif": None})
            self.assertEqual(statut, 200, reponse)
            self.assertRegex(reponse["sauvegarde"], MOTIF_NOM_MANUEL)

            # Motifs de la liste fermée : « …_avant-format-v2 » (lot 2) et « …_avant-format-v3 » (lot 6),
            # listés et restaurables.
            statut, reponse = demander_sauvegarde(serveur, {"motif": MOTIF_AVANT_FORMAT_COURANT})
            self.assertEqual(statut, 200, reponse)
            self.assertRegex(reponse["sauvegarde"], MOTIF_NOM_AVANT_FORMAT_COURANT)
            statut, reponse = demander_sauvegarde(serveur, {"motif": "avant-format-v2"})
            self.assertEqual(statut, 200, reponse)
            nom = reponse["sauvegarde"]
            self.assertRegex(nom, MOTIF_NOM_AVANT_FORMAT_2)
            self.assertTrue((dossier / nom / "parametres.csv").is_file())
            statut, liste = requete(serveur, "GET", "/api/sauvegardes")
            self.assertIn(nom, [s["nom"] for s in liste["sauvegardes"]])
            statut, reponse = demander_restauration(serveur, nom, ["parametres"])
            self.assertEqual(statut, 200, reponse)
            self.assertEqual(reponse["restaurees"], ["parametres"])

    def test_json_trop_imbrique_400_et_non_500(self):
        # Relecture de la vague 2 : « [[[[… » faisait lever RecursionError à json.loads → 500.
        imbrique = b"[" * 200000 + b"]" * 200000
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier / "sauvegardes"
            avant = sorted(p.name for p in dossier.iterdir())
            for chemin in ("/api/sauvegarde", "/api/restauration"):
                with self.subTest(chemin=chemin):
                    statut, reponse = requete(serveur, "POST", chemin, imbrique,
                                              {"Content-Type": "application/json"})
                    self.assertEqual(statut, 400, reponse)
                    self.assertEqual(reponse["erreur"], "Corps JSON invalide.")
            self.assertEqual(sorted(p.name for p in dossier.iterdir()), avant)    # rien n'a été créé
            self.assertNotIn("RecursionError", serveur.sortie_console())
            statut, _ = requete(serveur, "GET", "/api/ping")
            self.assertEqual(statut, 200)                                        # toujours en service

    def test_regles_de_noms_pour_la_restauration(self):
        with ServeurPrevo() as serveur:
            for nom, valide in NOMS_A_CONTROLER:
                with self.subTest(nom=nom):
                    statut, reponse = demander_restauration(serveur, nom)
                    self.assertEqual(statut, 404 if valide else 400, reponse)


# ---------------------------------------------------------------------------
# Mode dossier (dossier simulé dans l'OPFS du navigateur)
# ---------------------------------------------------------------------------

NOM_DOSSIER_SIMULE = "donnees-version-schema"
PAGE_DOSSIER = "/tests/fixtures/page-stockage-dossier.html"

# Outils ajoutés à la page de test : copie des fichiers de tests/fixtures/v1 dans le dossier simulé,
# lecture et liste de l'OPFS, ouverture de l'adaptateur et de Donnees.
AIDE_DOSSIER_JS = """
window.aideVersion = (() => {
  const nomDossier = %s;
  async function dossier(chemin) {
    let courant = await (await navigator.storage.getDirectory()).getDirectoryHandle(nomDossier, { create: true });
    for (const morceau of chemin.split('/').filter(Boolean)) { courant = await courant.getDirectoryHandle(morceau); }
    return courant;
  }
  async function lire(chemin) {
    const morceaux = chemin.split('/');
    try {
      const poignee = await (await dossier(morceaux.slice(0, -1).join('/'))).getFileHandle(morceaux[morceaux.length - 1]);
      return Array.from(new Uint8Array(await (await poignee.getFile()).arrayBuffer()));
    } catch (erreur) {
      if (erreur.name === 'NotFoundError') { return null; }
      throw erreur;
    }
  }
  async function lister(chemin) {
    const noms = [];
    try {
      for await (const entree of (await dossier(chemin)).values()) { noms.push(entree.name); }
    } catch (erreur) {
      if (erreur.name === 'NotFoundError') { return []; }
      throw erreur;
    }
    return noms.sort();
  }
  async function installerFichiersV1(tables) {
    const racine = await dossier('');
    for (const table of tables) {
      const reponse = await fetch('/tests/fixtures/v1/' + table + '.csv', { cache: 'no-store' });
      const octets = new Uint8Array(await reponse.arrayBuffer());
      const flux = await (await racine.getFileHandle(table + '.csv', { create: true })).createWritable();
      await flux.write(octets);
      await flux.close();
    }
  }
  async function ouvrir() {
    window.dos = await StockageDossier.creer(await window.showDirectoryPicker(), { poste: 'Poste test' });
    Donnees.initialiser(window.dos, { poste: 'Poste test', profil: 'Responsable' });
    await Donnees.chargerTout();
  }
  async function appeler(methode, args) {
    try {
      return { ok: true, valeur: await window.dos[methode](...(args || [])) };
    } catch (erreur) {
      return { ok: false, nom: erreur.name, message: erreur.message };
    }
  }
  return { lire, lister, installerFichiersV1, ouvrir, appeler };
})();
""" % json.dumps(NOM_DOSSIER_SIMULE)


class TestDossier(CasNavigateur):

    def ouvrir_dossier_v1(self, url_base):
        installer_dossier_simule(self.contexte, NOM_DOSSIER_SIMULE)
        self.page.goto(url_base + PAGE_DOSSIER)
        self.page.add_script_tag(content=AIDE_DOSSIER_JS)
        self.page.evaluate("tables => aideVersion.installerFichiersV1(tables)", list(TABLES_V1))
        self.page.evaluate("aideVersion.ouvrir()")
        self.assertEqual(self.page.evaluate("Donnees.parametre('version_schema')"), "1")

    def lire(self, chemin):
        octets = self.page.evaluate("chemin => aideVersion.lire(chemin)", chemin)
        return None if octets is None else bytes(octets)

    def lister(self, chemin):
        return self.page.evaluate("chemin => aideVersion.lister(chemin)", chemin)

    def appeler(self, methode, *args):
        return self.page.evaluate("([m, a]) => aideVersion.appeler(m, a)", [methode, list(args)])

    def test_dossier_passage_au_format_courant_puis_restauration(self):
        with ServeurStatique(RACINE) as statique:
            self.ouvrir_dossier_v1(statique.url)
            resultat = self.page.evaluate(APPELER_MISE_A_JOUR)
            self.assertTrue(resultat["ok"], resultat)
            self.assertTrue(resultat["valeur"]["misAJour"])
            nom = resultat["valeur"]["sauvegarde"]
            self.assertRegex(nom, MOTIF_NOM_AVANT_FORMAT_COURANT)
            self.assertEqual(resultat["valeur"]["depart"], 1)
            # Écritures explicites (T186) : les trois tables du format 1 sont complétées (colonnes des formats 2 et 3).
            self.assertEqual(sorted(resultat["valeur"]["tables"]), ["demandes", "equipements", "ordres_travail"])
            self.assertEqual(resultat["valeur"]["abimees"], [])

            # Sauvegarde complète (sans marqueur « .en-cours »), avec l'état d'avant (toutes les tables, à l'octet) et
            # son manifeste.json (T188).
            self.assertEqual(self.lister("sauvegardes/" + nom), sorted([t + ".csv" for t in TABLES_V1] + ["manifeste.json"]))
            for table in TABLES_V1:
                self.assertEqual(self.lire("sauvegardes/%s/%s.csv" % (nom, table)),
                                 (PARAMETRES_V1.parent / (table + ".csv")).read_bytes(), table)
            self.assertEqual(version_schema(self.lire("parametres.csv")), FORMAT_COURANT)
            entete_ordres = self.lire("ordres_travail.csv").decode("utf-8-sig").split("\r\n", 1)[0].split(";")
            self.assertEqual(entete_ordres[-3:], ["anomalie_constatee", "astuce", "habilitation_requise"])   # formats 2, 3 puis 4
            # Une ligne de journal par étape (1 → 2, puis 2 → 3).
            actions = actions_journal_version(self.lire("journal.csv"))
            self.assertEqual(actions, ["passage au format %d du fichier ; sauvegarde %s faite juste avant" % (n, nom)
                                       for n in range(2, FORMAT_COURANT_NUM + 1)])

            # Second appel : rien.
            sauvegardes_avant = self.lister("sauvegardes")
            fichiers_avant = {t: self.lire(t + ".csv") for t in TABLES_V1 + ("journal",)}
            self.assertEqual(self.page.evaluate(APPELER_MISE_A_JOUR), {"ok": True, "valeur": resultat_sans_effet(FORMAT_COURANT_NUM)})
            self.assertEqual(self.lister("sauvegardes"), sauvegardes_avant)
            self.assertEqual({t: self.lire(t + ".csv") for t in TABLES_V1 + ("journal",)}, fichiers_avant)

            # Le nom est accepté par StockageDossier : listé, puis restauré (toutes les tables).
            liste = self.appeler("listerSauvegardes")
            self.assertTrue(liste["ok"], liste)
            self.assertIn(nom, [s["nom"] for s in liste["valeur"]])
            restauration = self.appeler("restaurer", nom)
            self.assertTrue(restauration["ok"], restauration)
            self.assertEqual(sorted(restauration["valeur"]["restaurees"]), sorted(TABLES_V1))
            self.assertEqual(self.lire("parametres.csv"), PARAMETRES_V1.read_bytes())

    def test_dossier_echec_de_la_sauvegarde_rien_n_est_ecrit_et_erreur_claire(self):
        with ServeurStatique(RACINE) as statique:
            self.ouvrir_dossier_v1(statique.url)
            fichiers_avant = {t: self.lire(t + ".csv") for t in TABLES_V1 + ("journal",)}
            # La sauvegarde échoue (méthode remplacée sur l'adaptateur : disque plein, Excel…).
            self.page.evaluate("""() => { window.vraieSauvegarde = window.dos.sauvegarder;
                window.dos.sauvegarder = async () => {
                  throw new Donnees.ErreurStockage('Le disque est plein (simulé).'); }; }""")
            resultat = self.page.evaluate(APPELER_MISE_A_JOUR)
            self.assertFalse(resultat["ok"], resultat)
            self.assertEqual(resultat["nom"], "ErreurStockage")
            self.assertEqual(resultat["message"],
                             DEBUT_ERREUR_SAUVEGARDE + "Le disque est plein (simulé)" + FIN_ERREUR_SAUVEGARDE)
            # Rien n'a bougé : aucune table réécrite, version 1 sur le disque et en mémoire, pas de journal.
            self.assertEqual({t: self.lire(t + ".csv") for t in TABLES_V1 + ("journal",)}, fichiers_avant)
            self.assertEqual(self.page.evaluate("Donnees.parametre('version_schema')"), "1")
            self.assertEqual(self.lister("sauvegardes"), [])

            # Une erreur qui n'est pas une ErreurStockage (bogue) donne le même message clair.
            self.page.evaluate("() => { window.dos.sauvegarder = async () => { throw new TypeError('panne'); }; }")
            resultat = self.page.evaluate(APPELER_MISE_A_JOUR)
            self.assertEqual((resultat["ok"], resultat["nom"]), (False, "ErreurStockage"))
            self.assertEqual(resultat["message"], DEBUT_ERREUR_SAUVEGARDE + "panne" + FIN_ERREUR_SAUVEGARDE)

            # Un stockage (hors démo) qui ne sait pas sauvegarder, ou qui ne renvoie aucun nom, n'est pas dispensé
            # de la sauvegarde → refus, rien n'est écrit.
            for remplacement, cause in (
                    ("undefined", "ce mode de stockage ne sait pas faire de sauvegarde"),
                    ("async () => undefined", "le stockage n'a pas confirmé la sauvegarde (aucun nom renvoyé)")):
                self.page.evaluate("() => { window.dos.sauvegarder = %s; }" % remplacement)
                resultat = self.page.evaluate(APPELER_MISE_A_JOUR)
                self.assertEqual((resultat["ok"], resultat["nom"]), (False, "ErreurStockage"), remplacement)
                self.assertEqual(resultat["message"], DEBUT_ERREUR_SAUVEGARDE + cause + FIN_ERREUR_SAUVEGARDE)
                self.assertEqual({t: self.lire(t + ".csv") for t in TABLES_V1 + ("journal",)}, fichiers_avant)

            # La fois suivante (sauvegarde rétablie), le passage se fait.
            self.page.evaluate("() => { window.dos.sauvegarder = window.vraieSauvegarde; }")
            resultat = self.page.evaluate(APPELER_MISE_A_JOUR)
            self.assertTrue(resultat["ok"] and resultat["valeur"]["misAJour"], resultat)
            self.assertEqual(version_schema(self.lire("parametres.csv")), FORMAT_COURANT)

    def test_dossier_autre_poste_deja_passe_au_format_courant_version_pas_reecrite(self):
        with ServeurStatique(RACINE) as statique:
            self.ouvrir_dossier_v1(statique.url)
            # Un autre poste a fait le passage juste après notre lecture (notre cache dit encore 1).
            ecrit_par_l_autre_poste = PARAMETRES_V1.read_bytes().replace(b"version_schema;'1", ("version_schema;'" + FORMAT_COURANT).encode())
            self.page.evaluate("""async (octets) => {
                const racine = await (await navigator.storage.getDirectory()).getDirectoryHandle(%s);
                const flux = await (await racine.getFileHandle('parametres.csv')).createWritable();
                await flux.write(new Uint8Array(octets));
                await flux.close();
            }""" % json.dumps(NOM_DOSSIER_SIMULE), list(ecrit_par_l_autre_poste))
            resultat = self.page.evaluate(APPELER_MISE_A_JOUR)
            self.assertTrue(resultat["ok"], resultat)
            # Notre sauvegarde est faite (sans gravité : deux copies) ; version_schema n'est pas réécrite (conflit, puis
            # relecture : déjà 3) ; nos tables complétées le sont, et le journal dit « complétés », pas « passage ».
            self.assertRegex(resultat["valeur"]["sauvegarde"], MOTIF_NOM_AVANT_FORMAT_COURANT)
            self.assertEqual(self.lire("parametres.csv"), ecrit_par_l_autre_poste)
            self.assertEqual(self.page.evaluate("Donnees.parametre('version_schema')"), FORMAT_COURANT)
            actions = actions_journal_version(self.lire("journal.csv"))
            self.assertTrue(actions and all(a.startswith("fichiers complétés au format ") for a in actions), actions)
            self.assertFalse([a for a in actions if "passage au format" in a], actions)

    def test_dossier_motif_refuse_et_regles_de_noms_identiques_au_serveur(self):
        with ServeurStatique(RACINE) as statique:
            self.ouvrir_dossier_v1(statique.url)
            avant = self.lister("sauvegardes")
            for motif in ("inconnu", "../x", MOTIF_AVANT_FORMAT_TROP_RECENT, "avant-format-v2/../..", 2):
                with self.subTest(motif=motif):
                    resultat = self.appeler("sauvegarder", motif)
                    self.assertEqual((resultat["ok"], resultat["nom"]), (False, "ErreurStockage"), resultat)
                    self.assertIn("Motif de sauvegarde refusé", resultat["message"])
            self.assertEqual(self.lister("sauvegardes"), avant)          # rien n'a été créé

            # Sans motif : sauvegarde manuelle, comme avant ; avec un motif de la liste : « …_avant-format-vN ».
            manuelle = self.appeler("sauvegarder")
            self.assertRegex(manuelle["valeur"], MOTIF_NOM_MANUEL)
            avec_motif = self.appeler("sauvegarder", "avant-format-v2")
            self.assertRegex(avec_motif["valeur"], MOTIF_NOM_AVANT_FORMAT_2)
            avec_motif = self.appeler("sauvegarder", MOTIF_AVANT_FORMAT_COURANT)
            self.assertRegex(avec_motif["valeur"], MOTIF_NOM_AVANT_FORMAT_COURANT)

            # Mêmes règles de noms que le serveur (TestApiMotif.test_regles_de_noms_pour_la_restauration).
            for nom, valide in NOMS_A_CONTROLER:
                with self.subTest(nom=nom):
                    resultat = self.appeler("restaurer", nom)
                    self.assertFalse(resultat["ok"])
                    attendu = "Sauvegarde introuvable" if valide else "Nom de sauvegarde invalide"
                    self.assertIn(attendu, resultat["message"])


# ---------------------------------------------------------------------------
# Démo
# ---------------------------------------------------------------------------

class TestDemo(CasNavigateur):

    def test_demo_aucune_sauvegarde_aucune_erreur(self):
        preregler_profil(self.contexte, "responsable")
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        self.page.evaluate("""() => { window.appelsSauvegarde = 0;
            const original = App.adaptateur.sauvegarder;
            App.adaptateur.sauvegarder = function () { window.appelsSauvegarde += 1; return original.apply(this, arguments); }; }""")
        # Le jeu de démo est déjà au format courant : rien à faire.
        self.assertEqual(self.page.evaluate("Donnees.parametre('version_schema')"), FORMAT_COURANT)
        self.assertEqual(self.page.evaluate(APPELER_MISE_A_JOUR), {"ok": True, "valeur": resultat_sans_effet(FORMAT_COURANT_NUM)})
        self.assertEqual(self.page.evaluate("window.appelsSauvegarde"), 0)

    def test_demo_fichiers_au_format_1_passage_en_memoire_seulement(self):
        charger_scripts(self.page, ["js/lib/papaparse.min.js", "js/schema.js", "js/formats.js", "js/donnees.js",
                                    "js/stockage-demo.js"])
        resultat = self.page.evaluate("""async (texteParametres) => {
            const demo = StockageDemo.creer({ parametres: texteParametres });
            let appelsSauvegarde = 0;
            const original = demo.sauvegarder;
            demo.sauvegarder = function () { appelsSauvegarde += 1; return original.apply(this, arguments); };
            Donnees.initialiser(demo, { poste: 'Poste test', profil: 'Responsable' });
            await Donnees.chargerTout();
            const premier = await Donnees.mettreAJourVersionSchema();
            const second = await Donnees.mettreAJourVersionSchema();
            return {
              premier, second, appelsSauvegarde,
              version: Donnees.parametre('version_schema'),
              fichier: Donnees.csv.decoder((await demo.charger('parametres')).octets).texte,
              journal: Donnees.lignes('journal').map((ligne) => ligne.action),
            };
        }""", PARAMETRES_V1.read_bytes().decode("utf-8-sig"))
        # Seul parametres.csv existe (format 3 de fichier : cle, valeur) : aucune table à compléter, deux étapes.
        self.assertEqual(resultat["premier"], {"misAJour": True, "sauvegarde": None, "depart": 1, "tables": [],
                                               "abimees": []})
        self.assertEqual(resultat["second"], resultat_sans_effet(FORMAT_COURANT_NUM))
        self.assertEqual(resultat["appelsSauvegarde"], 0)
        self.assertEqual(resultat["version"], FORMAT_COURANT)
        self.assertIn("version_schema;'" + FORMAT_COURANT, resultat["fichier"])
        self.assertEqual(resultat["journal"], ["passage au format %d du fichier ; sans sauvegarde (démo)" % n
                                               for n in range(2, FORMAT_COURANT_NUM + 1)])


if __name__ == "__main__":
    unittest.main()
