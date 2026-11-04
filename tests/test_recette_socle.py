"""Recette du Lot 1 « socle de données » (chantier i18n-socle, tâche T193 ; CDC CS138 à CS145, CS167, CS168 ;
docs/FORMAT.md). Parcours de BOUT EN BOUT, comme un utilisateur, à travers l'interface quand c'est possible ; les tests
unitaires de chaque partie (test_formats_*, test_migration_serveur, test_sauvegardes_socle, test_sauvegardes_dossier,
test_zip_export, test_zip_lecture) ne sont pas recopiés ici.

Chaque parcours travaille sur une COPIE d'un jeu de tests/fixtures/formats/ (tests/jeux_formats.py) dans un dossier
temporaire, ou dans l'OPFS du navigateur de test (mode dossier simulé) ; CS167 : setUpModule et tearDownModule
vérifient que le dossier donnees/ du dépôt n'a pas changé d'un octet pendant la recette.

    TestMiseAJourServeur      CS143, CS138 : f3-v1.2.0 sans derniere-version.json (une installation 1.2) ; premier
                              démarrage de la 2.0 : sauvegarde « avant-mise-a-jour » aux octets d'origine, aucune
                              migration (format 3), version notée ; le responsable ouvre l'accueil sans bandeau, voit
                              la sauvegarde dans Paramètres et signale une demande par l'interface ; aucune perte.
    TestElevesServeurComptes  CS138, CS139, CS143 : f2-v1.1.0 (données d'élèves des versions 1.0 et 1.1) avec
                              acces/comptes.json ; démarrage : « avant-mise-a-jour » PUIS « avant-format-v3 », toutes
                              deux aux octets d'origine, tables migrées sans perte champ à champ, ligne de journal ;
                              connexion du responsable puis d'un technicien par l'écran de connexion : aucun bandeau,
                              OT préventifs générés comme d'habitude (une seule fois).
    TestFormat1Dossier        CS138, CS139, CS143 : f1 en mode dossier : sauvegardes, passage 1 → 2 → 3, deux lignes
                              de journal, aucune perte ; seconde ouverture : rien d'écrit (verrou.txt mis à part).
    TestAbimesServeur,        CS140 : melange, colonnes-en-trop, windows-1252 et entete-tronque, dans les deux modes :
    TestAbimesDossier         le responsable ouvre (OT préventifs générés), lit Paramètres › Contrôle de la base,
                              modifie un équipement par le formulaire ; aucune perte silencieuse (chaque cellule
                              d'origine retrouvée), message ou problème visible, et chaque fichier changé a ses octets
                              d'origine dans une sauvegarde. entete-tronque : parcours du demandeur (le fichier n'est
                              jamais réécrit) ; le défaut trouvé par la recette (voir plus bas) est corrigé par T197.
    TestPlusRecent            CS141 : jeu plus-recent (format 4) dans les deux modes : bandeau de lecture seule, demande
                              et modification d'équipement refusées par l'interface avec un message, AUCUN octet de
                              données modifié (mode dossier : aucun octet du tout), export ZIP possible (format 4).
    TestRotation              CS142 : fausses sauvegardes anciennes, horloge simulée (serveur du processus,
                              config.horloge ; navigateur, contexte.clock) : quotidiennes de plus de 30 jours supprimées
                              à la sauvegarde du jour, « avant-… », manuelles et noms étrangers jamais touchés ;
                              « Sauvegarder maintenant » garde les 60 dernières manuelles.
    TestExportServeur         CS144 : responsable connecté, document joint par le formulaire, rapport figé ; export par
                              Paramètres : ZIP complet (24 CSV, documents, manifeste exact), sans acces/, puis relu par
                              ZipLecture.lire dans une page (ok).
CS145 (import ZIP) : l'aller-retour export puis import est dans tests/test_zip_import.py (T191), pas ici. CS168 : la
liste des changements du lot qui touchent la sécurité est dans le compte rendu de T193.

Défaut trouvé par la recette, CORRIGÉ par T197 (ErreurFichierAbime : un fichier abîmé n'est plus jamais réécrit hors
import ZIP et restauration ; les deux tests ci-dessous en sont la preuve) :
    entete-tronque : ordres_travail.csv a un en-tête coupé ; le serveur (console : « laissé tel quel, jamais
    réécrit ») et le passage au format le laissent tel quel, mais à l'ouverture par un technicien ou le responsable,
    la génération des OT préventifs le réécrit par Donnees.modifier (aucune garde pour une table abîmée hors du
    passage au format) : les valeurs au-delà de l'en-tête (date_debut … astuce de chaque OT, 110 valeurs dans ce jeu)
    sont perdues, sans bandeau. La sauvegarde du jour garde l'original. Tests : TestAbimesServeur et
    TestAbimesDossier, test_entete_tronque_*_jamais_reecrit_a_l_ouverture.

Lancer depuis la racine du projet (à travers le verrou du navigateur) :
    py -X utf8 -m unittest discover -s tests -p "test_recette_socle.py" -v
"""
import base64
import csv
import datetime
import hashlib
import importlib.util
import io
import json
import re
import shutil
import tempfile
import threading
import unittest
import urllib.request
import zipfile
from pathlib import Path
from unittest import mock

from commun import (COMPTES_DE_TEST, RACINE, CasNavigateur, ServeurPrevo, ServeurStatique, attendre_pret,
                    charger_scripts, comptes_json, installer_dossier_simule, preregler_profil)
from jeux_formats import copier_jeu


def charger_serveur():
    """serveur.py importé comme module (rotation : serveur du processus avec une horloge simulée)."""
    specification = importlib.util.spec_from_file_location("serveur_prevo_t193", RACINE / "serveur.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


SERVEUR = charger_serveur()

VERSION_APPLI = re.search(r"const VERSION = '([^']+)';",
                          (RACINE / "js" / "app.js").read_text(encoding="utf-8")).group(1)
FORMAT_COURANT = 3
BOM = b"\xef\xbb\xbf"
VERROU = "verrou.txt"
DERNIERE_VERSION = "derniere-version.json"
MANIFESTE = "manifeste.json"
NOM_DOSSIER = "donnees-recette-socle"
EQUIPEMENT = "EQ-0005"                       # PO-02 : présent dans tous les jeux sauf f1
MOTIF_AVANT_MISE_A_JOUR = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}_avant-mise-a-jour$")
MOTIF_AVANT_FORMAT = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}_avant-format-v3$")
MOTIF_QUOTIDIENNE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MOTIF_DATE_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
MOTIF_DATE_JMA = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
CLES_MANIFESTE_EXPORT = ["application", "version_appli", "format", "date", "motif", "mode", "fichiers"]
# Valeur par défaut des colonnes que les formats 2 et 3 ajoutent (js/schema.js).
DEFAUTS = {"valeur_remplacement": "", "symptome_code": "", "ot_origine_id": "", "anomalie_constatee": "0", "astuce": ""}
TABLES = list(SERVEUR.TABLES)                # les 24 tables du format 3, dans l'ordre du schéma
VERSION_SCHEMA_ECRITE = {"parametres.csv": {("version_schema", "valeur")}}     # seule cellule que le passage change

# Chromium note en console.error toute réponse HTTP >= 400 : seules celles-ci sont attendues.
ERREUR_PING_ABSENT = re.compile(r"status of 404.*/api/ping")      # serveur statique (mode dossier) : pas de /api/ping
ERREUR_CSV_ABSENT = re.compile(r"status of 404.*/api/csv/")       # mode serveur : table absente = table vide
ERREUR_SANS_SESSION = re.compile(r"status of 401")                 # comptes exigés : sonde avant la connexion

# Tous les messages montrés (UI.toast), dans l'ordre : un message peut en remplacer un autre très vite.
# (UI.toast remplit la zone #toast à chaque message, même répété : chaque remplissage est noté.)
NOTER_TOASTS_JS = """(() => {
  window.__toasts = [];
  new MutationObserver((mutations) => {
    const zone = document.getElementById('toast');
    if (!zone || !mutations.some((m) => m.addedNodes.length && zone.contains(m.target))) return;
    const texte = zone.textContent.trim();
    if (texte) window.__toasts.push(texte);
  }).observe(document, { subtree: true, childList: true });
})();"""

ECRIRE_OPFS_JS = """async ([nom, fichiers]) => {
  const racine = await (await navigator.storage.getDirectory()).getDirectoryHandle(nom, { create: true });
  for (const [chemin, enBase64] of Object.entries(fichiers)) {
    const morceaux = chemin.split('/');
    let dossier = racine;
    for (const sous of morceaux.slice(0, -1)) { dossier = await dossier.getDirectoryHandle(sous, { create: true }); }
    const binaire = atob(enBase64);
    const octets = new Uint8Array(binaire.length);
    for (let i = 0; i < binaire.length; i += 1) { octets[i] = binaire.charCodeAt(i); }
    const flux = await (await dossier.getFileHandle(morceaux[morceaux.length - 1], { create: true })).createWritable();
    await flux.write(octets);
    await flux.close();
  }
}"""

INSTANTANE_OPFS_JS = """async (nom) => {
  const resultat = {};
  async function parcourir(dossier, prefixe) {
    for await (const entree of dossier.values()) {
      if (entree.kind === 'directory') { await parcourir(entree, prefixe + entree.name + '/'); continue; }
      const octets = new Uint8Array(await (await entree.getFile()).arrayBuffer());
      let binaire = '';
      for (let i = 0; i < octets.length; i += 0x8000) {
        binaire += String.fromCharCode.apply(null, octets.subarray(i, i + 0x8000));
      }
      resultat[prefixe + entree.name] = btoa(binaire);
    }
  }
  await parcourir(await (await navigator.storage.getDirectory()).getDirectoryHandle(nom, { create: true }), '');
  return resultat;
}"""

# Problèmes de lecture d'une table (ceux que Paramètres › Contrôle de la base affiche).
PROBLEMES_JS = """(table) => Donnees.problemes().filter((p) => p.table === table)
  .map((p) => ({ gravite: p.gravite, type: p.type, message: p.message }))"""

SCRIPTS_LECTURE_ZIP = ["js/lib/papaparse.min.js", "js/lib/jszip.min.js", "js/schema.js", "js/formats.js",
                       "js/donnees.js", "js/modules/zip-lecture.js"]
LIRE_ZIP_JS = """async () => {
  const r = await ZipLecture.lire(document.getElementById('zip-recette').files[0]);
  if (!r.ok) { return { ok: false, refus: r.refus }; }
  const tables = {};
  for (const [nom, t] of Object.entries(r.tables)) { tables[nom] = t.lignes.length; }
  const documents = [];          // relus un par un depuis le ZIP (seconde passe, T205)
  for (const d of r.documents) { documents.push([d.nom, (await ZipLecture.lireDocument(r, d.nom)).length]); }
  return { ok: true, refus: r.refus, format: r.format, formatOrigine: r.formatOrigine, migre: r.migre,
    motif: r.manifeste && r.manifeste.motif, absentes: r.absentes, tables: tables, documents: documents,
    problemes: r.problemes.filter((p) => p.type === 'document').map((p) => p.message) };
}"""


# ---------------------------------------------------------------------------
# Règle numéro un (CS167) : le dossier donnees/ du dépôt ne change pas pendant la recette
# ---------------------------------------------------------------------------

def empreintes(dossier):
    dossier = Path(dossier)
    if not dossier.is_dir():
        return {}
    return {p.relative_to(dossier).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(dossier.rglob("*")) if p.is_file()}


DONNEES_DU_DEPOT = {}


def setUpModule():
    DONNEES_DU_DEPOT.update(empreintes(RACINE / "donnees"))


def tearDownModule():
    if empreintes(RACINE / "donnees") != DONNEES_DU_DEPOT:
        raise AssertionError("CS167 : le dossier donnees/ du dépôt a changé pendant la recette (seules des copies "
                             "doivent être ouvertes).")


# ---------------------------------------------------------------------------
# Fichiers (cellules brutes, comme Excel ou un autre poste les lit)
# ---------------------------------------------------------------------------

def fichiers_de(dossier):
    """{chemin relatif « / »: octets} de tous les fichiers d'un dossier."""
    dossier = Path(dossier)
    return {p.relative_to(dossier).as_posix(): p.read_bytes() for p in sorted(dossier.rglob("*")) if p.is_file()}


def fichiers_du_jeu(nom):
    """{chemin : octets} d'une copie du jeu faite dans un dossier temporaire (pour l'OPFS)."""
    with tempfile.TemporaryDirectory(prefix="prevo-t193-") as temporaire:
        return fichiers_de(copier_jeu(nom, Path(temporaire) / "donnees"))


def csv_de_la_racine(fichiers):
    return {chemin: octets for chemin, octets in fichiers.items() if "/" not in chemin and chemin.endswith(".csv")}


def lire_table(octets):
    """(en-tête, lignes) d'un CSV : BOM retiré, UTF-8 sinon Windows-1252, « ; », lignes blanches ignorées."""
    try:
        texte = octets.decode("utf-8-sig")
    except UnicodeDecodeError:
        texte = octets.decode("cp1252")
    lignes = [ligne for ligne in csv.reader(io.StringIO(texte, newline=""), delimiter=";")
              if any(cellule.strip() for cellule in ligne)]
    return (lignes[0], lignes[1:]) if lignes else ([], [])


def cellule(ligne, position):
    return ligne[position] if position < len(ligne) else ""


def lignes_en_dictionnaires(octets):
    entete, lignes = lire_table(octets)
    return [{nom: cellule(ligne, i) for i, nom in enumerate(entete)} for ligne in lignes]


def valeur_comparable(valeur):
    """Valeur d'une cellule aux réécritures documentées près (ARCHITECTURE.md §3) : apostrophe de protection retirée,
    date JJ/MM/AAAA (Excel) écrite AAAA-MM-JJ."""
    if valeur.startswith("'"):
        valeur = valeur[1:]
    date = MOTIF_DATE_JMA.match(valeur)
    return "%s-%s-%s" % (date.group(3), date.group(2), date.group(1)) if date else valeur


def version_schema(octets):
    for ligne in lignes_en_dictionnaires(octets):
        if ligne.get("cle") == "version_schema":
            return valeur_comparable(ligne.get("valeur", ""))
    return None


def actions_du_format(octets, deja=0):
    """Actions du journal (à partir de la ligne n° deja) qui concernent parametres.version_schema."""
    if octets is None:
        return []
    return [ligne for ligne in lignes_en_dictionnaires(octets)[deja:]
            if ligne.get("table") == "parametres" and ligne.get("id_ligne") == "version_schema"]


def sauvegardes(fichiers):
    """{nom de la sauvegarde: {chemin dans la sauvegarde: octets}} d'un instantané."""
    resultat = {}
    for chemin, octets in fichiers.items():
        morceaux = chemin.split("/", 2)
        if len(morceaux) == 3 and morceaux[0] == "sauvegardes":
            resultat.setdefault(morceaux[1], {})[morceaux[2]] = octets
    return resultat


def une_seule(noms, motif):
    trouves = [nom for nom in noms if motif.match(nom)]
    if len(trouves) != 1:
        raise AssertionError("une seule sauvegarde %s attendue : %r" % (motif.pattern, sorted(noms)))
    return trouves[0]


def sans_manifeste(contenu):
    return {chemin: octets for chemin, octets in contenu.items() if chemin != MANIFESTE}


def octets_pdf(graine):
    return b"%PDF-1.4\n% document de recette : " + graine.encode("utf-8") + b"\n" + bytes(range(256))


def requete_json(url):
    with urllib.request.urlopen(url, timeout=10) as reponse:
        return json.loads(reponse.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Gestes et vérifications communs
# ---------------------------------------------------------------------------

class CasRecetteSocle(CasNavigateur):

    def setUp(self):
        super().setUp()
        self.temporaire = Path(tempfile.mkdtemp(prefix="prevo-t193-"))
        self.addCleanup(shutil.rmtree, self.temporaire, True)
        self.contexte.add_init_script(NOTER_TOASTS_JS)

    def jeu(self, nom, sous_dossier="jeu"):
        """Copie du jeu dans un dossier temporaire (règle numéro un) ; rend son chemin."""
        return copier_jeu(nom, self.temporaire / sous_dossier / "donnees")

    # -- ouvrir ------------------------------------------------------------------------------

    def ouvrir_serveur(self, url, profil, technicien_id="", route="#/accueil"):
        """Application du serveur (adresse url) ouverte, sans comptes : profil mémorisé sur le poste."""
        preregler_profil(self.contexte, profil, nom="Claire Recette", technicien_id=technicien_id)
        self.page.goto(url + "/" + route)
        attendre_pret(self.page)
        self.page.wait_for_load_state("networkidle")

    def se_connecter(self, page, role):
        """Écran de connexion (comptes exigés) : identifiant, mot de passe, « Se connecter »."""
        identifiant, _, _, mot_de_passe, _ = COMPTES_DE_TEST[role]
        page.wait_for_selector("#connexion-formulaire", state="visible")
        page.fill("#connexion-identifiant", identifiant)
        page.fill("#connexion-mot-de-passe", mot_de_passe)
        page.click("#connexion-valider")
        attendre_pret(page)

    def demarrer_statique(self):
        self.autoriser_erreur(ERREUR_PING_ABSENT)
        self.statique = ServeurStatique(RACINE)
        self.statique.demarrer()
        self.addCleanup(self.statique.arreter)

    def instantane(self):
        brut = self.page.evaluate(INSTANTANE_OPFS_JS, NOM_DOSSIER)
        return {chemin: base64.b64decode(valeur) for chemin, valeur in brut.items()}

    def ouvrir_dossier(self, fichiers, profil, technicien_id=""):
        """Application ouverte (état « prêt ») sur un dossier simulé (OPFS) qui contient `fichiers`."""
        installer_dossier_simule(self.contexte, NOM_DOSSIER)
        preregler_profil(self.contexte, profil, nom="Claire Recette", technicien_id=technicien_id)
        self.page.goto(self.statique.url + "/index.html")
        self.page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        envoyes = {chemin: base64.b64encode(octets).decode("ascii") for chemin, octets in fichiers.items()}
        self.page.evaluate(ECRIRE_OPFS_JS, [NOM_DOSSIER, envoyes])
        self.assertEqual(self.instantane(), fichiers)
        self.page.click("#btn-dossier")
        attendre_pret(self.page)
        self.page.wait_for_load_state("networkidle")
        self.assertEqual(self.page.evaluate("App.mode"), "dossier")

    def rouvrir_dossier(self):
        self.page.reload()
        self.page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        self.page.click("#btn-reprendre")
        attendre_pret(self.page)
        self.page.wait_for_load_state("networkidle")

    # -- gestes ------------------------------------------------------------------------------

    def aller(self, route, attendre, page=None):
        page = page or self.page
        page.evaluate("(route) => { location.hash = route; }", route)
        page.wait_for_selector(attendre)

    def attendre_toast(self, morceau, page=None):
        page = page or self.page
        page.wait_for_function("(m) => (window.__toasts || []).some((t) => t.includes(m))", arg=morceau)
        return next(t for t in page.evaluate("window.__toasts") if morceau in t)

    def remplir_demande(self, symptome, equipement=EQUIPEMENT):
        """« Signaler un problème » sur l'équipement : symptôme, impact, description, « Envoyer »."""
        self.aller("#/di/nouvelle?equipement=" + equipement, ".di-envoyer")
        self.page.fill("input[name=symptome]", symptome)
        self.page.click("label.tuile:has(input[value='dégradé'])")
        self.page.fill("textarea[name=description]", "Parcours de recette du socle de données.")
        self.page.click(".di-envoyer")

    def signaler(self, symptome, equipement=EQUIPEMENT):
        """Demande envoyée par l'interface ; rend son numéro."""
        self.remplir_demande(symptome, equipement)
        self.page.wait_for_selector(".di-numero")
        self.page.wait_for_load_state("networkidle")
        return self.page.inner_text(".di-numero").strip()

    def remplir_equipement(self, designation, document=None, equipement=EQUIPEMENT):
        """Formulaire « Modifier l'équipement » : désignation (et un document joint), « Enregistrer »."""
        self.aller("#/equipement/%s/modifier" % equipement, "#parc-formulaire")
        self.page.fill("#parc-formulaire [name=designation]", designation)
        if document is not None:
            self.page.set_input_files("[data-champ=document_fichier] input[type=file]", document)
        self.page.click("#parc-formulaire button[type=submit]")

    def modifier_equipement(self, designation, document=None, equipement=EQUIPEMENT):
        self.remplir_equipement(designation, document, equipement)
        self.page.wait_for_function("(h) => location.hash === h", arg="#/equipement/" + equipement)
        self.attendre_toast("Équipement enregistré")
        self.page.wait_for_load_state("networkidle")

    def texte_du_controle(self):
        """Paramètres › Contrôle de la base (responsable) : texte de l'écran."""
        self.aller("#/controle", "#btn-relire")
        return self.page.inner_text("#contenu")

    def carte_des_sauvegardes(self):
        """Paramètres › Sauvegardes (responsable) : texte de la carte."""
        self.aller("#/parametres", "#carte-sauvegardes")
        return self.page.inner_text("#carte-sauvegardes")

    def aucun_bandeau(self, page=None):
        page = page or self.page
        self.assertEqual(page.locator("#alertes-app > *").count(), 0, page.inner_text("#alertes-app"))
        self.assertFalse(page.evaluate("Donnees.lectureSeule()"))

    def exporter(self, selecteur="#btn-export-zip"):
        """Clique sur le bouton d'export ; rend (nom proposé, noms dans l'ordre, {nom: octets}, chemin du ZIP)."""
        with self.page.expect_download() as attente:
            self.page.click(selecteur)
        telechargement = attente.value
        chemin = self.temporaire / ("export-%d.zip" % len(list(self.temporaire.glob("export-*.zip"))))
        telechargement.save_as(str(chemin))
        with zipfile.ZipFile(chemin) as archive:
            noms = archive.namelist()
            entrees = {nom: archive.read(nom) for nom in noms}
        return telechargement.suggested_filename, noms, entrees, chemin

    # -- vérifications -----------------------------------------------------------------------

    def verifier_cellules_gardees(self, nom, avant, apres, changees=()):
        """Aucune perte (CS138, CS140) : chaque colonne d'origine existe encore ; chaque cellule d'origine se retrouve
        sous le même nom de colonne, à la même ligne (aux réécritures documentées près : valeur_comparable) ; les
        colonnes ajoutées portent leur valeur par défaut ; les lignes ajoutées sont après les lignes d'origine.
        changees : {(identifiant de la ligne, colonne)} que le parcours a lui-même modifiées."""
        entete_avant, lignes_avant = lire_table(avant)
        entete_apres, lignes_apres = lire_table(apres)
        for colonne in entete_avant:
            self.assertIn(colonne, entete_apres, "%s : colonne %s perdue" % (nom, colonne))
        self.assertGreaterEqual(len(lignes_apres), len(lignes_avant), nom + " : lignes perdues")
        ajoutees = [colonne for colonne in entete_apres if colonne not in entete_avant]
        for rang, ligne in enumerate(lignes_avant):
            nouvelle = lignes_apres[rang]
            self.assertLessEqual(len(ligne), len(entete_avant), "%s, ligne %d : valeurs au-delà de l'en-tête"
                                 % (nom, rang + 2))
            identifiant = cellule(ligne, 0)
            for position, colonne in enumerate(entete_avant):
                if (identifiant, colonne) in changees:
                    continue
                self.assertEqual(valeur_comparable(cellule(nouvelle, entete_apres.index(colonne))),
                                 valeur_comparable(cellule(ligne, position)),
                                 "%s, ligne %d (%s), colonne %s" % (nom, rang + 2, identifiant, colonne))
            for colonne in ajoutees:
                self.assertIn(colonne, DEFAUTS, "%s : colonne %s ajoutée" % (nom, colonne))
                self.assertEqual(cellule(nouvelle, entete_apres.index(colonne)), DEFAUTS[colonne],
                                 "%s, ligne %d, colonne ajoutée %s" % (nom, rang + 2, colonne))

    def verifier_aucune_perte(self, origine, apres, changees=None):
        """verifier_cellules_gardees pour chaque CSV de données changé ; aucun CSV d'origine disparu. changees :
        {fichier: {(identifiant, colonne)}}. Rend les fichiers changés."""
        changees = changees or {}
        modifies = sorted(chemin for chemin, octets in csv_de_la_racine(origine).items() if apres.get(chemin) != octets)
        for chemin in modifies:
            self.assertIn(chemin, apres, chemin + " a disparu")
            self.verifier_cellules_gardees(chemin, origine[chemin], apres[chemin], changees.get(chemin, ()))
        return modifies

    def verifier_rien_sans_sauvegarde(self, origine, apres):
        """Aucune écriture sans sauvegarde (CS138, CS140) : chaque CSV de données changé a ses octets d'origine dans
        au moins une sauvegarde (faite avant l'écriture, puisqu'elle a l'état d'avant)."""
        contenus = sauvegardes(apres).values()
        for chemin, octets in csv_de_la_racine(origine).items():
            if apres.get(chemin) != octets:
                self.assertTrue(any(contenu.get(chemin) == octets for contenu in contenus),
                                "%s a changé sans sauvegarde de ses octets d'origine" % chemin)

    def verifier_manifeste(self, contenu, motif, format_, mode, complement=None):
        """manifeste.json d'une sauvegarde : champs, motif, format, mode, fichiers (tailles et SHA-256 recalculés)."""
        manifeste = json.loads(contenu[MANIFESTE].decode("utf-8"))
        self.assertEqual((manifeste["application"], manifeste["format"], manifeste["motif"], manifeste["mode"]),
                         ("Prévo", format_, motif, mode))
        self.assertRegex(manifeste["date"], MOTIF_DATE_ISO)
        for cle, valeur in (complement or {}).items():
            self.assertEqual(manifeste[cle], valeur, cle)
        self.assertEqual(manifeste["fichiers"], [
            {"nom": nom, "octets": len(octets), "sha256": hashlib.sha256(octets).hexdigest()}
            for nom, octets in sorted(sans_manifeste(contenu).items())])
        return manifeste

    def verifier_zip_export(self, nom_zip, noms, entrees, documents, mode, format_):
        """ZIP d'export complet (CS144) : tous les CSV, les documents attendus, manifeste.json exact, et rien d'autre
        (ni acces/, ni sauvegardes/, ni chemin absolu ou avec « .. »). Rend le manifeste."""
        self.assertRegex(nom_zip, r"^prevo-export-\d{4}-\d{2}-\d{2}\.zip$")
        self.assertEqual(len(noms), len(set(noms)), "entrée en double")
        for nom in noms:
            self.assertFalse(nom.startswith("acces") or "/acces/" in nom, nom)
            self.assertFalse(nom.startswith(("/", "sauvegardes/")) or ".." in nom or "\\" in nom, nom)
        self.assertEqual(sorted(nom for nom in noms if "/" not in nom and nom.endswith(".csv")),
                         sorted(table + ".csv" for table in TABLES))
        self.assertEqual(set(noms), {table + ".csv" for table in TABLES} | {"documents/" + nom for nom in documents}
                         | {MANIFESTE})
        for nom, octets in documents.items():
            self.assertEqual(entrees["documents/" + nom], octets, nom)
        manifeste = json.loads(entrees[MANIFESTE].decode("utf-8"))
        self.assertEqual(list(manifeste), CLES_MANIFESTE_EXPORT)
        self.assertEqual((manifeste["application"], manifeste["version_appli"], manifeste["format"],
                          manifeste["motif"], manifeste["mode"]), ("Prévo", VERSION_APPLI, format_, "export", mode))
        self.assertRegex(manifeste["date"], MOTIF_DATE_ISO)
        self.assertEqual(manifeste["fichiers"], [
            {"nom": nom, "octets": len(entrees[nom]), "sha256": hashlib.sha256(entrees[nom]).hexdigest()}
            for nom in sorted(nom for nom in noms if nom != MANIFESTE)])
        return manifeste


# ---------------------------------------------------------------------------
# 1. Mise à jour 1.2 → 2.0.x en mode serveur (CS143, CS138)
# ---------------------------------------------------------------------------

class TestMiseAJourServeur(CasRecetteSocle):

    def test_f3_v1_2_0_premier_demarrage_sauvegarde_puis_accueil_sans_bandeau_et_demande(self):
        source = self.jeu("f3-v1.2.0")
        origine = fichiers_de(source)
        self.assertNotIn(DERNIERE_VERSION, origine)                       # une installation 1.2 : rien de noté
        with ServeurPrevo(source=source) as serveur:
            demarre = fichiers_de(serveur.dossier)
            console = serveur.sortie_console()
            # Au démarrage : « avant-mise-a-jour » aux octets d'origine, la quotidienne, et rien d'autre.
            copies = sauvegardes(demarre)
            maj = une_seule(copies, MOTIF_AVANT_MISE_A_JOUR)
            self.assertEqual(sans_manifeste(copies[maj]), origine)
            self.verifier_manifeste(copies[maj], "avant-mise-a-jour", FORMAT_COURANT, "serveur",
                                    {"de": None, "vers": VERSION_APPLI})
            self.assertEqual(sorted(copies), sorted([maj, datetime.date.today().isoformat()]))
            self.assertIn("sauvegarde %s faite avant la mise à jour" % maj, console)
            # Aucune migration (déjà au format 3) : les données à l'octet près, la version notée.
            self.assertEqual(csv_de_la_racine(demarre), origine)
            self.assertNotIn(SERVEUR.PREFIXE_CONSOLE_FORMAT, console)
            note = json.loads(demarre[DERNIERE_VERSION].decode("utf-8"))
            self.assertEqual(note["version"], VERSION_APPLI)

            # Le responsable ouvre l'accueil : aucun bandeau ; la sauvegarde est dans Paramètres.
            self.ouvrir_serveur(serveur.url, "responsable")
            self.aucun_bandeau()
            self.assertEqual(self.page.evaluate("Donnees.etatDuFormat().depart"), FORMAT_COURANT)
            self.assertIn("Avant la mise à jour de Prévo", self.carte_des_sauvegardes())
            # Une écriture par l'interface : une demande.
            numero = self.signaler("Fuite d'huile au joint de la pompe")
            apres = fichiers_de(serveur.dossier)
            self.page.goto("about:blank")                  # la page quitte le serveur avant son arrêt

        demande = next(l for l in lignes_en_dictionnaires(apres["demandes.csv"]) if l["id"] == numero)
        self.assertEqual((demande["equipement_id"], demande["statut"], demande["symptome"]),
                         (EQUIPEMENT, "Nouvelle", "Fuite d'huile au joint de la pompe"))
        self.assertIn("demandes.csv", self.verifier_aucune_perte(origine, apres))
        self.verifier_rien_sans_sauvegarde(origine, apres)


# ---------------------------------------------------------------------------
# 2. Données des élèves (format 2) en mode serveur, avec comptes (CS138, CS139, CS143)
# ---------------------------------------------------------------------------

class TestElevesServeurComptes(CasRecetteSocle):

    def test_f2_v1_1_0_avec_comptes_mise_a_jour_puis_format_3_connexions_et_ot_preventifs(self):
        self.autoriser_erreur(ERREUR_CSV_ABSENT)                         # wiki_pages, wiki_journal : absentes
        self.autoriser_erreur(ERREUR_SANS_SESSION)
        source = self.jeu("f2-v1.1.0")
        (source / "acces").mkdir()
        (source / "acces" / "comptes.json").write_bytes(comptes_json())
        origine = fichiers_de(source)
        with ServeurPrevo(source=source, comptes=True) as serveur:
            demarre = fichiers_de(serveur.dossier)
            console = serveur.sortie_console()

            # « avant-mise-a-jour » PUIS « avant-format-v3 », toutes deux aux octets d'origine (acces/ compris).
            copies = sauvegardes(demarre)
            maj = une_seule(copies, MOTIF_AVANT_MISE_A_JOUR)
            avant_format = une_seule(copies, MOTIF_AVANT_FORMAT)
            self.assertEqual(sorted(copies), sorted([maj, avant_format, datetime.date.today().isoformat()]))
            self.assertLessEqual(maj[:17], avant_format[:17])
            self.assertLess(console.index("faite avant la mise à jour"), console.index(SERVEUR.PREFIXE_CONSOLE_FORMAT))
            dates = []
            for nom, motif in ((maj, "avant-mise-a-jour"), (avant_format, "avant-format-v3")):
                self.assertEqual(sans_manifeste(copies[nom]), origine, nom)
                dates.append(self.verifier_manifeste(copies[nom], motif, 2, "serveur")["date"])
            self.assertLessEqual(dates[0], dates[1])

            # Tables migrées sans perte, champ à champ ; ligne de journal du serveur ; acces/ intact.
            self.assertEqual(version_schema(demarre["parametres.csv"]), "3")
            self.assertEqual(self.verifier_aucune_perte(origine, demarre, VERSION_SCHEMA_ECRITE),
                             ["journal.csv", "ordres_travail.csv", "parametres.csv"])
            self.assertEqual(lire_table(demarre["ordres_travail.csv"])[0][-1], "astuce")
            self.assertNotIn("wiki_pages.csv", demarre)
            journal = actions_du_format(demarre["journal.csv"], len(lignes_en_dictionnaires(origine["journal.csv"])))
            self.assertEqual([(l["action"], l["poste"]) for l in journal],
                             [("passage au format 3 du fichier ; sauvegarde %s faite juste avant" % avant_format,
                               "Serveur Prévo")])
            self.assertEqual(demarre["acces/comptes.json"], origine["acces/comptes.json"])
            ot_apres_demarrage = len(lignes_en_dictionnaires(demarre["ordres_travail.csv"]))

            # Le responsable se connecte : aucun bandeau, OT préventifs générés à l'ouverture, comme d'habitude.
            self.page.goto(serveur.url + "/#/accueil")
            self.se_connecter(self.page, "responsable")
            self.assertEqual(self.page.evaluate("App.profil.type"), "responsable")
            self.aucun_bandeau()
            self.assertEqual(self.page.evaluate("Donnees.etatDuFormat().depart"), FORMAT_COURANT)
            toast = self.attendre_toast("préventif")
            ordres = lignes_en_dictionnaires((serveur.dossier / "ordres_travail.csv").read_bytes())
            nouveaux = ordres[ot_apres_demarrage:]
            self.assertTrue(nouveaux, "aucun OT préventif généré à l'ouverture")
            self.assertIn("%d OT préventif" % len(nouveaux), toast)
            self.assertEqual({(ot["origine"], ot["statut"]) for ot in nouveaux}, {("préventif", "Créé")})
            self.assertTrue(all(ot["gamme_id"] for ot in nouveaux))
            self.assertEqual(self.page.evaluate("Preventif.genererOTEchus().then((crees) => crees.length)"), 0)

            # Un technicien se connecte sur un autre poste : aucun bandeau, rien de généré deux fois.
            contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
            self.addCleanup(contexte.close)
            contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
            technicien = contexte.new_page()
            self.surveiller(technicien)
            technicien.goto(serveur.url + "/#/accueil")
            self.se_connecter(technicien, "technicien")
            self.assertEqual(technicien.evaluate("App.profil.type"), "technicien")
            self.aucun_bandeau(technicien)
            apres = fichiers_de(serveur.dossier)
            self.assertEqual(len(lignes_en_dictionnaires(apres["ordres_travail.csv"])), len(ordres))
            technicien.goto("about:blank")
            self.page.goto("about:blank")

        self.verifier_aucune_perte(origine, apres, VERSION_SCHEMA_ECRITE)
        self.verifier_rien_sans_sauvegarde(origine, apres)


# ---------------------------------------------------------------------------
# 3. Format 1 en mode dossier (CS138, CS139, CS143)
# ---------------------------------------------------------------------------

class TestFormat1Dossier(CasRecetteSocle):

    def setUp(self):
        super().setUp()
        self.demarrer_statique()

    def test_f1_sauvegardes_passage_1_2_3_journal_sans_perte_puis_seconde_ouverture_sans_ecriture(self):
        origine = fichiers_du_jeu("f1")
        self.assertEqual(version_schema(origine["parametres.csv"]), "1")
        self.ouvrir_dossier(origine, "responsable")
        apres = self.instantane()

        # Sauvegardes : « avant-mise-a-jour » et « avant-format-v3 » aux octets d'origine (la quotidienne aussi).
        copies = sauvegardes(apres)
        maj = une_seule(copies, MOTIF_AVANT_MISE_A_JOUR)
        avant_format = une_seule(copies, MOTIF_AVANT_FORMAT)
        for nom, contenu in copies.items():
            self.assertTrue(nom in (maj, avant_format) or MOTIF_QUOTIDIENNE.match(nom), sorted(copies))
            self.assertEqual(sans_manifeste(contenu), origine, nom)
        self.verifier_manifeste(copies[avant_format], "avant-format-v3", 1, "dossier")
        # Passage 1 → 2 → 3 : deux lignes de journal ; aucune perte, colonnes ajoutées à leur valeur par défaut.
        self.assertEqual(version_schema(apres["parametres.csv"]), "3")
        self.assertEqual([l["action"] for l in actions_du_format(apres["journal.csv"])],
                         ["passage au format %d du fichier ; sauvegarde %s faite juste avant" % (n, avant_format)
                          for n in (2, 3)])
        self.assertEqual(self.verifier_aucune_perte(origine, apres, VERSION_SCHEMA_ECRITE),
                         ["demandes.csv", "equipements.csv", "ordres_travail.csv", "parametres.csv"])
        self.verifier_rien_sans_sauvegarde(origine, apres)
        nouveaux = {c for c in set(apres) - set(origine) if not c.startswith("sauvegardes/")}
        self.assertEqual(nouveaux, {VERROU, DERNIERE_VERSION, "journal.csv"})
        # À l'écran : aucun bandeau, le parc du fichier, les sauvegardes dans Paramètres.
        self.aucun_bandeau()
        premier = lignes_en_dictionnaires(origine["equipements.csv"])[0]
        self.aller("#/parc", "#contenu")
        self.page.wait_for_function("(t) => document.getElementById('contenu').innerText.includes(t)",
                                    arg=valeur_comparable(premier["designation"]))
        carte = self.carte_des_sauvegardes()
        self.assertIn("Avant format 3", carte)
        self.assertIn("Avant la mise à jour de Prévo", carte)

        # Seconde ouverture : rien n'est écrit (verrou.txt mis à part).
        self.rouvrir_dossier()
        sans_verrou = lambda instantane: {c: o for c, o in instantane.items() if c != VERROU}  # noqa: E731
        self.assertEqual(sans_verrou(self.instantane()), sans_verrou(apres))


# ---------------------------------------------------------------------------
# 4. Base mélangée et fichiers abîmés, dans les deux modes (CS140)
# ---------------------------------------------------------------------------

DESIGNATION = "Pompe de refroidissement (recette)"
CHANGEES_PAR_LE_FORMULAIRE = {"equipements.csv": {(EQUIPEMENT, "designation")}}


class ParcoursAbimes:
    """Parcours communs aux deux modes ; la classe fille donne ouvrir(nom_jeu, profil) → origine et apres()."""

    def parcours_du_responsable(self, nom_jeu):
        """Le responsable ouvre (OT préventifs générés), lit le Contrôle de la base, modifie EQ-0005 par le
        formulaire ; aucune perte et rien sans sauvegarde. Rend (origine, apres, texte du contrôle)."""
        origine = self.ouvrir(nom_jeu, "responsable")
        controle = self.texte_du_controle()
        self.modifier_equipement(DESIGNATION)
        apres = self.apres()
        changes = self.verifier_aucune_perte(origine, apres, CHANGEES_PAR_LE_FORMULAIRE)
        self.assertIn("equipements.csv", changes)
        self.verifier_rien_sans_sauvegarde(origine, apres)
        equipement = next(l for l in lignes_en_dictionnaires(apres["equipements.csv"]) if l["id"] == EQUIPEMENT)
        self.assertEqual(equipement["designation"], DESIGNATION)
        return origine, apres, controle

    def verifier_melange(self):
        """melange : ordres_travail.csv au format 2 dans une base au format 3 → complété (sauvegarde avant, ligne de
        journal « fichiers complétés »), version_schema inchangé ; la sauvegarde se voit dans Paramètres."""
        origine, apres, _ = self.parcours_du_responsable("melange")
        self.assertEqual(lire_table(apres["ordres_travail.csv"])[0][-1], "astuce")
        self.assertEqual(version_schema(apres["parametres.csv"]), "3")
        avant_format = une_seule(sauvegardes(apres), MOTIF_AVANT_FORMAT)
        self.assertEqual(sauvegardes(apres)[avant_format]["ordres_travail.csv"], origine["ordres_travail.csv"])
        deja = len(lignes_en_dictionnaires(origine["journal.csv"]))
        self.assertEqual([l["action"] for l in actions_du_format(apres["journal.csv"], deja)],
                         ["fichiers complétés au format 3 : ordres_travail ; sauvegarde %s faite juste avant"
                          % avant_format])
        self.assertIn("Avant format 3", self.carte_des_sauvegardes())

    def verifier_colonnes_en_trop(self):
        """colonnes-en-trop : les colonnes inconnues sont signalées (Contrôle), gardées avec leurs valeurs à la
        réécriture, à la fin du fichier (ARCHITECTURE.md §3.3), jamais confondues avec une colonne du schéma."""
        origine, apres, controle = self.parcours_du_responsable("colonnes-en-trop")
        for colonne in ("colonne_maison", "note_maison"):
            self.assertIn("« %s »" % colonne, controle)
        self.assertIn("conservée telle quelle", controle)
        entete = lire_table(apres["equipements.csv"])[0]
        self.assertEqual(entete[-2:], ["colonne_maison", "note_maison"])
        self.assertEqual(entete[:-2], list(SERVEUR.COLONNES_PAR_TABLE["equipements"]))

    def verifier_windows_1252(self):
        """windows-1252 : le fichier est signalé (Contrôle) ; réécrit en UTF-8 avec BOM, dates AAAA-MM-JJ, sans perte ;
        la sauvegarde du jour garde l'original."""
        origine, apres, controle = self.parcours_du_responsable("windows-1252")
        self.assertIn("Windows-1252", controle)
        self.assertTrue(apres["equipements.csv"].startswith(BOM))
        apres["equipements.csv"].decode("utf-8")
        dates = [l["date_mes"] for l in lignes_en_dictionnaires(apres["equipements.csv"]) if l["date_mes"]]
        self.assertTrue(dates and all(re.match(r"^\d{4}-\d{2}-\d{2}$", d) for d in dates), dates)

    def verifier_entete_tronque_demandeur(self):
        """entete-tronque, profil demandeur (aucun OT préventif généré) : le fichier abîmé est signalé et n'est
        jamais réécrit ; la demande s'écrit, après une sauvegarde."""
        origine = self.ouvrir("entete-tronque", "demandeur")
        problemes = self.page.evaluate(PROBLEMES_JS, "ordres_travail")
        self.assertTrue(any(p["gravite"] == "attention" and "plus de valeurs que l'en-tête" in p["message"]
                            for p in problemes), problemes)
        self.assertTrue(any("« temps_pr »" in p["message"] for p in problemes), problemes)
        numero = self.signaler("Bruit anormal au démarrage")
        apres = self.apres()
        self.assertEqual(apres["ordres_travail.csv"], origine["ordres_travail.csv"])
        self.assertIn("demandes.csv", self.verifier_aucune_perte(origine, apres))
        self.verifier_rien_sans_sauvegarde(origine, apres)
        self.assertTrue(any(l["id"] == numero for l in lignes_en_dictionnaires(apres["demandes.csv"])))
        return origine, apres

    def verifier_entete_tronque_jamais_reecrit(self):
        """DÉFAUT : à l'ouverture par le responsable, la génération des OT préventifs réécrit ordres_travail.csv
        (en-tête coupé), que le passage au format et le serveur laissent « tel quel, jamais réécrit » (FORMAT.md §6 :
        un fichier illisible n'est jamais réécrit) : les valeurs au-delà de l'en-tête (date_debut … astuce de chaque
        OT) sont perdues, sans bandeau. Attendu : le fichier reste à l'octet près tant qu'il n'est pas corrigé."""
        origine = self.ouvrir("entete-tronque", "responsable")
        apres = self.apres()
        self.verifier_rien_sans_sauvegarde(origine, apres)                   # vrai : la quotidienne a l'original
        entete, lignes = lire_table(origine["ordres_travail.csv"])
        nouvelles = lire_table(apres["ordres_travail.csv"])[1]
        perdues = sum(1 for rang, ligne in enumerate(lignes) for valeur in ligne[len(entete):]
                      if valeur.strip() and valeur not in (nouvelles[rang] if rang < len(nouvelles) else []))
        self.assertEqual(apres["ordres_travail.csv"], origine["ordres_travail.csv"],
                         "ordres_travail.csv réécrit à l'ouverture : %d valeurs au-delà de l'en-tête perdues" % perdues)


class TestAbimesServeur(ParcoursAbimes, CasRecetteSocle):

    def ouvrir(self, nom_jeu, profil):
        """Serveur réel sur une copie du jeu ; le profil ouvre l'accueil. Rend les fichiers d'origine."""
        source = self.jeu(nom_jeu)
        origine = fichiers_de(source)
        self.serveur = ServeurPrevo(source=source)
        self.serveur.demarrer()
        self.addCleanup(self.serveur.arreter)
        self.ouvrir_serveur(self.serveur.url, profil)
        return origine

    def apres(self):
        self.page.wait_for_load_state("networkidle")
        return fichiers_de(self.serveur.dossier)

    def test_melange_complete_au_demarrage_sans_perte(self):
        self.verifier_melange()
        self.assertIn("fichiers complétés au format 3", self.serveur.sortie_console())

    def test_colonnes_en_trop_signalees_et_gardees(self):
        self.verifier_colonnes_en_trop()

    def test_windows_1252_signale_et_reecrit_en_utf8_sans_perte(self):
        self.verifier_windows_1252()

    def test_entete_tronque_signale_jamais_reecrit_pour_le_demandeur(self):
        self.verifier_entete_tronque_demandeur()
        self.assertIn("ordres_travail.csv laissé tel quel", self.serveur.sortie_console())
        etat = requete_json(self.serveur.url + "/api/info")["format"]
        self.assertEqual((etat["tables_abimees"], etat["migration"]), (["ordres_travail"], "rien"))

    def test_entete_tronque_serveur_jamais_reecrit_a_l_ouverture(self):
        self.verifier_entete_tronque_jamais_reecrit()


class TestAbimesDossier(ParcoursAbimes, CasRecetteSocle):

    def setUp(self):
        super().setUp()
        self.demarrer_statique()

    def ouvrir(self, nom_jeu, profil):
        origine = fichiers_du_jeu(nom_jeu)
        self.ouvrir_dossier(origine, profil)
        return origine

    def apres(self):
        self.page.wait_for_load_state("networkidle")
        return self.instantane()

    def test_melange_complete_a_l_ouverture_sans_perte(self):
        self.verifier_melange()

    def test_colonnes_en_trop_signalees_et_gardees(self):
        self.verifier_colonnes_en_trop()

    def test_windows_1252_signale_et_reecrit_en_utf8_sans_perte(self):
        self.verifier_windows_1252()

    def test_entete_tronque_signale_jamais_reecrit_pour_le_demandeur(self):
        self.verifier_entete_tronque_demandeur()

    def test_entete_tronque_dossier_jamais_reecrit_a_l_ouverture(self):
        self.verifier_entete_tronque_jamais_reecrit()


# ---------------------------------------------------------------------------
# 5. Données plus récentes (plus-recent), dans les deux modes (CS141)
# ---------------------------------------------------------------------------

class ParcoursPlusRecent:

    def tenter_les_ecritures(self):
        """Bandeau visible ; une demande et une modification d'équipement par l'interface : refusées avec le message."""
        bandeau = self.page.locator("#alertes-app #bandeau-lecture-seule")
        self.assertTrue(bandeau.is_visible())
        self.assertIn("Lecture seule", bandeau.inner_text())
        self.assertIn("format 4", bandeau.inner_text())
        self.assertEqual(self.page.evaluate("Donnees.lectureSeule()"), True)
        self.assertEqual(self.page.evaluate("Donnees.lignes('ordres_travail').length"),
                         len(lire_table(self.origine["ordres_travail.csv"])[1]))     # aucun OT préventif généré
        self.remplir_demande("Fuite d'huile")
        self.assertIn("lecture seule", self.attendre_toast("lecture seule"))
        self.assertEqual(self.page.locator(".di-numero").count(), 0)
        self.page.evaluate("window.__toasts = []")
        self.remplir_equipement("Ne doit pas être enregistré")
        self.assertIn("version plus récente de Prévo", self.attendre_toast("lecture seule"))
        self.assertEqual(self.page.evaluate("location.hash"), "#/equipement/%s/modifier" % EQUIPEMENT)
        self.assertTrue(self.page.locator("#bandeau-lecture-seule").is_visible())       # sur cet écran aussi

    def exporter_en_lecture_seule(self, mode):
        """Paramètres : « Sauvegarder maintenant » refusé avec le message (le navigateur n'écrit rien) ; export ZIP
        possible : format 4, colonne inconnue gardée, table inconnue non exportée."""
        self.aller("#/parametres", "#btn-export-zip")
        self.page.evaluate("window.__toasts = []")
        self.page.click("#btn-sauvegarder")
        self.assertIn("version plus récente de Prévo", self.attendre_toast("lecture seule"))
        nom_zip, noms, entrees, _ = self.exporter()
        self.verifier_zip_export(nom_zip, noms, entrees, {}, mode, 4)
        self.assertNotIn("pieces_v4.csv", noms)
        self.assertIn(b"nouvelle_colonne_v4", entrees["ordres_travail.csv"].split(b"\r\n", 1)[0])
        for chemin, octets in csv_de_la_racine(self.origine).items():
            if chemin != "pieces_v4.csv":
                self.assertEqual(entrees[chemin], octets, chemin)


class TestPlusRecent(ParcoursPlusRecent, CasRecetteSocle):

    def test_plus_recent_serveur_lecture_seule_aucun_octet_modifie_export_possible(self):
        source = self.jeu("plus-recent")
        self.origine = fichiers_de(source)
        with ServeurPrevo(source=source) as serveur:
            demarre = fichiers_de(serveur.dossier)
            self.assertIn("LECTURE SEULE", serveur.sortie_console())
            # Le démarrage n'écrit aucune donnée (seulement ses sauvegardes et derniere-version.json).
            donnees = {c: o for c, o in demarre.items() if not c.startswith("sauvegardes/") and c != DERNIERE_VERSION}
            self.assertEqual(donnees, self.origine)
            self.ouvrir_serveur(serveur.url, "responsable")
            self.tenter_les_ecritures()
            self.exporter_en_lecture_seule("serveur")
            self.page.wait_for_load_state("networkidle")
            # AUCUN octet modifié par la session (ni donnée, ni sauvegarde, ni document).
            self.assertEqual(fichiers_de(serveur.dossier), demarre)
            self.page.goto("about:blank")

    def test_plus_recent_dossier_lecture_seule_aucun_octet_ecrit_export_possible(self):
        self.demarrer_statique()
        self.origine = fichiers_du_jeu("plus-recent")
        self.ouvrir_dossier(self.origine, "responsable")
        self.tenter_les_ecritures()
        self.exporter_en_lecture_seule("dossier")
        # Aucun octet écrit dans le dossier : ni sauvegarde, ni derniere-version.json, ni verrou.txt.
        self.assertEqual(self.instantane(), self.origine)
        self.rouvrir_dossier()
        self.assertTrue(self.page.locator("#bandeau-lecture-seule").is_visible())
        self.assertEqual(self.instantane(), self.origine)


# ---------------------------------------------------------------------------
# 6. Rotation des sauvegardes, horloge simulée, dans les deux modes (CS142)
# ---------------------------------------------------------------------------

JOUR = datetime.date(2026, 6, 15)
# T206 : au moins 7 quotidiennes sans fichier abîmé plus récentes que les anciennes (1 à 5 jours en plus), sinon la
# rotation garderait celles de 31 et 45 jours (les 7 quotidiennes saines les plus récentes sont toujours gardées).
AGES_GARDES = (1, 2, 3, 4, 5, 10, 29, 30)
AGES_SUPPRIMES = (31, 45)
AVANT = ["2025-01-02_101010_avant-format-v3", "2025-01-02_101011_avant-import", "2025-01-02_101012_avant-restauration",
         "2025-01-02_101013_avant-import-zip", "2025-01-02_101014_avant-mise-a-jour"]
ETRANGERS = ["2025-02-30", "Mes sauvegardes", "2025-01-04-copie"]


def quotidienne(age, jour=JOUR):
    return (jour - datetime.timedelta(days=age)).isoformat()


def fausses_sauvegardes(parametres, manuelles):
    """{chemin : octets} de fausses sauvegardes anciennes (un parametres.csv chacune)."""
    noms = [quotidienne(age) for age in AGES_GARDES + AGES_SUPPRIMES] + AVANT + manuelles + ETRANGERS
    return {"sauvegardes/%s/parametres.csv" % nom: parametres for nom in noms}


class TestRotation(CasRecetteSocle):

    def test_rotation_serveur_horloge_simulee(self):
        """Serveur du processus (serveur.py importé) avec config.horloge : démarrage le 15 juin (ce que fait main),
        puis le responsable signale une demande le 16 juin (première écriture du jour) et sauvegarde à la main."""
        donnees = self.jeu("f3-v1.2.0")
        (donnees / DERNIERE_VERSION).write_text(json.dumps({"version": VERSION_APPLI, "depuis": "2026-06-01T08:00:00"}),
                                                encoding="utf-8")
        manuelles = ["2025-01-03_080000", "2026-05-01_120000"]
        for chemin, octets in fausses_sauvegardes((donnees / "parametres.csv").read_bytes(), manuelles).items():
            (donnees / chemin).parent.mkdir(parents=True, exist_ok=True)
            (donnees / chemin).write_bytes(octets)
        anciennes = fichiers_de(donnees)
        console = []                                   # console du serveur relevée (et tue pendant le test)
        espion = mock.patch.object(SERVEUR, "afficher", side_effect=console.append)
        espion.start()
        self.addCleanup(espion.stop)
        horloge = {"instant": datetime.datetime(2026, 6, 15, 7, 30).timestamp()}
        config = SERVEUR.Configuration(str(donnees), [])
        config.horloge = lambda: horloge["instant"]
        SERVEUR.creer_dossiers(config)

        # Démarrage du 15 juin : la quotidienne du jour, puis la rotation (31 et 45 jours supprimées).
        SERVEUR.preparer_donnees_au_demarrage(config)
        gardes = sorted([quotidienne(age) for age in AGES_GARDES] + AVANT + manuelles + ETRANGERS + ["2026-06-15"])
        self.assertEqual(sorted(sauvegardes(fichiers_de(donnees))), gardes)
        http = SERVEUR.ServeurPrevo(("127.0.0.1", 0), config)
        config.port = http.server_address[1]
        fil = threading.Thread(target=http.serve_forever, daemon=True)
        fil.start()

        def arreter():
            http.shutdown()
            http.server_close()
            fil.join(timeout=5)
        self.addCleanup(arreter)                       # après tearDown : la page est déjà fermée
        self.ouvrir_serveur("http://127.0.0.1:%d" % config.port, "responsable")

        # Le 16 juin : la demande est la première écriture du jour → nouvelle quotidienne, rotation (30 jours la
        # veille = 31 ce jour-là : supprimée) ; puis « Sauvegarder maintenant » (deux manuelles : aucune supprimée).
        horloge["instant"] = datetime.datetime(2026, 6, 16, 8, 0).timestamp()
        self.signaler("Vibrations sur la pompe")
        attendues = sorted(set(gardes) - {quotidienne(30)} | {"2026-06-16"})
        self.assertEqual(sorted(sauvegardes(fichiers_de(donnees))), attendues)
        self.aller("#/parametres", "#btn-sauvegarder")
        self.page.click("#btn-sauvegarder")
        self.attendre_toast("Sauvegarde créée")
        noms = sorted(sauvegardes(fichiers_de(donnees)))
        self.assertEqual(noms, sorted(attendues + ["2026-06-16_080000"]))
        # Les « avant-… », les manuelles et les noms étrangers n'ont pas bougé d'un octet.
        apres = fichiers_de(donnees)
        for nom in AVANT + manuelles + ETRANGERS:
            chemin = "sauvegardes/%s/parametres.csv" % nom
            self.assertEqual(apres[chemin], anciennes[chemin], nom)

    def test_rotation_dossier_horloge_simulee(self):
        """Mode dossier, horloge du navigateur au 15 juin : la première écriture du jour (une demande) fait la
        quotidienne puis la rotation ; « Sauvegarder maintenant » avec 60 manuelles supprime la plus ancienne."""
        self.demarrer_statique()
        self.contexte.clock.install(time="2026-06-15T09:00:00")
        fichiers = fichiers_du_jeu("f3-v1.2.0")
        fichiers[DERNIERE_VERSION] = json.dumps({"version": VERSION_APPLI, "depuis": "2026-06-01T08:00:00"}).encode()
        debut = datetime.datetime(2026, 1, 1, 8, 0, 0)
        manuelles = [(debut + datetime.timedelta(hours=h)).strftime("%Y-%m-%d_%H%M%S") for h in range(60)]
        fichiers.update(fausses_sauvegardes(fichiers["parametres.csv"], manuelles))
        self.ouvrir_dossier(fichiers, "demandeur")
        self.assertEqual(self.page.evaluate("Donnees.aujourdhui()"), "2026-06-15")
        self.assertEqual(sorted(sauvegardes(self.instantane())), sorted(sauvegardes(fichiers)))   # rien à l'ouverture

        self.signaler("Vibrations sur la pompe")
        gardes = sorted([quotidienne(age) for age in AGES_GARDES] + AVANT + manuelles + ETRANGERS + ["2026-06-15"])
        self.assertEqual(sorted(sauvegardes(self.instantane())), gardes)

        # Le responsable sauvegarde à la main : 61 manuelles → la plus ancienne est supprimée, rien d'autre.
        self.page.evaluate("""() => { localStorage.setItem('prevo.profil', JSON.stringify(
            { type: 'responsable', nom: 'Claire Recette', technicienId: '' })); }""")
        self.rouvrir_dossier()
        self.aller("#/parametres", "#btn-sauvegarder")
        self.page.click("#btn-sauvegarder")
        nouvelle = re.search(r"Sauvegarde créée : (\S+)\.", self.attendre_toast("Sauvegarde créée")).group(1)
        self.assertTrue(nouvelle.startswith("2026-06-15_"), nouvelle)
        apres = self.instantane()
        self.assertEqual(sorted(sauvegardes(apres)), sorted(set(gardes) - {manuelles[0]} | {nouvelle}))
        for nom in AVANT + ETRANGERS:
            self.assertEqual(apres["sauvegardes/%s/parametres.csv" % nom], fichiers["parametres.csv"], nom)


# ---------------------------------------------------------------------------
# 7. Export depuis Paramètres, responsable, mode serveur ; relu par ZipLecture.lire (CS144)
# ---------------------------------------------------------------------------

class TestExportServeur(CasRecetteSocle):

    def test_export_complet_sans_acces_puis_relu_par_zip_lecture(self):
        self.autoriser_erreur(ERREUR_SANS_SESSION)
        source = self.jeu("f3-v2.0.0")
        self.assertTrue((source / "acces" / "comptes.json").is_file())
        rapport = ('<!doctype html><html lang="fr"><meta charset="utf-8"><title>Rapport 2026-10</title>'
                   '<p>Rapport figé de recette</p></html>').encode("utf-8")
        (source / "documents").mkdir()
        (source / "documents" / "rapport-mensuel-2026-10.html").write_bytes(rapport)
        (source / "documents" / "orphelin-non-cite.pdf").write_bytes(octets_pdf("orphelin"))      # jamais exporté
        parametres = source / "parametres.csv"
        parametres.write_bytes(parametres.read_bytes() + b"rapports_mensuels;rapport-mensuel-2026-10.html\r\n")
        notice = octets_pdf("notice de la pompe")
        with ServeurPrevo(source=source, comptes=True) as serveur:
            self.page.goto(serveur.url + "/#/accueil")
            self.se_connecter(self.page, "responsable")
            # Un document joint à l'équipement par le formulaire (nom imposé par le serveur).
            self.modifier_equipement(DESIGNATION, {"name": "notice-pompe.pdf", "mimeType": "application/pdf",
                                                   "buffer": notice})
            cite = next(l for l in lignes_en_dictionnaires((serveur.dossier / "equipements.csv").read_bytes())
                        if l["id"] == EQUIPEMENT)["document"]
            self.assertRegex(cite, r"^\d{8}-\d{6}-.*\.pdf$")
            avant_export = fichiers_de(serveur.dossier)
            self.aller("#/parametres", "#btn-export-zip")
            nom_zip, noms, entrees, chemin_zip = self.exporter()
            self.attendre_toast("Export téléchargé")
            self.page.wait_for_load_state("networkidle")
            self.assertEqual(fichiers_de(serveur.dossier), avant_export)            # l'export n'écrit rien
            self.assertIn("acces/comptes.json", avant_export)
            self.page.goto("about:blank")
        documents = {cite: notice, "rapport-mensuel-2026-10.html": rapport}
        self.verifier_zip_export(nom_zip, noms, entrees, documents, "serveur", FORMAT_COURANT)
        for table in TABLES:
            self.assertEqual(entrees[table + ".csv"], avant_export[table + ".csv"], table)

        # Relu par ZipLecture.lire dans une page, comme le fichier choisi par l'utilisateur.
        lecteur = self.contexte.new_page()
        self.surveiller(lecteur)
        charger_scripts(lecteur, SCRIPTS_LECTURE_ZIP)
        lecteur.evaluate("""() => { const champ = document.createElement('input'); champ.type = 'file';
            champ.id = 'zip-recette'; document.body.appendChild(champ); }""")
        lecteur.set_input_files("#zip-recette", str(chemin_zip))
        lu = lecteur.evaluate(LIRE_ZIP_JS)
        self.assertTrue(lu["ok"], lu)
        self.assertEqual((lu["refus"], lu["format"], lu["formatOrigine"], lu["migre"], lu["motif"], lu["absentes"]),
                         (None, FORMAT_COURANT, FORMAT_COURANT, False, "export", []))
        self.assertEqual(sorted(lu["documents"]), sorted([nom, len(octets)] for nom, octets in documents.items()))
        self.assertEqual(lu["problemes"], [])
        self.assertEqual(lu["tables"], {table: len(lire_table(avant_export[table + ".csv"])[1]) for table in TABLES})


if __name__ == "__main__":
    unittest.main()
