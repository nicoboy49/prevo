"""Une 2.1 (et une 2.0) rouvre une base au format 4 en lecture seule, sans erreur et sans rien changer aux données
(chantier 2.2, T396 ; CS169 ; note de conception du format 4, §5 risque 3 ; garde « données plus récentes » des
versions publiées : D169).

Le code des versions publiées est tiré des étiquettes git `v2.1.0` et `v2.0.0` par `git archive`, extrait dans un
dossier temporaire du module (l'étiquette n'est jamais touchée ; sans dépôt git ni étiquette, les tests sont sautés,
en le disant). Les données sont des copies de f4-v2.2.0 (tests/fixtures/formats, T394 : 27 tables, version_schema 4),
toujours dans un dossier temporaire : jamais de données réelles.

1. TestServeurPublie — sans navigateur : serveur.py de v2.1.0, puis de v2.0.0 (le même code, VERSION_APPLICATION
   mise à part), démarré sur une copie de f4-v2.2.0 :
     - démarrage sans erreur : /api/ping répond, console « LECTURE SEULE » sans trace d'exception ; /api/info
       « format » : base 4, courant 3, plus_recent, migration « rien », aucune table abîmée ni vide ;
     - lectures permises : chacune des 24 tables de la version publiée, rendue à l'octet ; les 3 tables du format 4
       (garanties, contrats_prestataires, reserves_controle) lui sont inconnues : ni lues, ni écrites ;
     - toute écriture refusée : PUT /api/csv, POST …/ajout, PUT /api/documents, POST /api/restauration (de la
       sauvegarde faite au démarrage) → 409 « format_plus_recent », format 4, message « version plus récente » ;
     - aucun octet des 27 CSV changé, aucun document écrit ;
     - ce que le démarrage écrit hors des tables (risque 3, à dire dans FORMAT §7) : derniere-version.json (la version
       publiée), une sauvegarde « avant-mise-a-jour » et la quotidienne, chacune avec les 24 tables de la version
       publiée SEULEMENT (copiées à l'octet ; les 3 tables du format 4 absentes) et un manifeste « format » 4 :
       sauvegarde incomplète marquée format 4 ; la sauvegarde manuelle (permise) est faite de même ;
     - second démarrage sur le dossier ainsi laissé : aucun octet changé, aucune sauvegarde de plus.
2. TestNavigateurPublie — navigateur (à lancer au travers du verrou), index.html de v2.1.0, profil responsable :
     dossier  : dossier simulé (OPFS) qui contient la copie de f4-v2.2.0 : mode dossier, bandeau « Lecture seule »
                (format 4) sur chaque écran visité, écrans principaux affichés sans erreur de console ni « Cet écran
                n'a pas pu s'afficher », écritures directes refusées (ErreurLectureSeule, Donnees et adaptateur),
                aucun octet du dossier modifié (ni sauvegarde, ni journal, ni verrou.txt, ni derniere-version.json) ;
                seconde ouverture : rien non plus ;
     serveur  : l'application servie par le serveur.py de v2.1.0 sur une copie de f4-v2.2.0 : mêmes écrans, même
                bandeau, mêmes refus ; le navigateur n'écrit aucun octet (fichiers relevés après le démarrage).

Lancer depuis la racine du projet (au travers du verrou à navigateur) :
    py -X utf8 -m unittest discover -s tests -p "test_format4_lecture_2_1.py" -v
"""
import ast
import base64
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

import commun
from commun import (RACINE, CasNavigateur, ServeurPrevo, ServeurStatique, attendre_pret, format_du_jeu,
                    installer_dossier_simule, preregler_profil)
from jeux_formats import copier_jeu

JEU = "f4-v2.2.0"
JEU_DE_LA_2_1 = "f3-v2.1.0"                 # donnees/demo de v2.1.0 : les 24 tables de la 2.1, au format 3
ETIQUETTES_DU_SERVEUR = ("v2.1.0", "v2.0.0")
ETIQUETTE_DU_NAVIGATEUR = "v2.1.0"
FORMAT_DES_VERSIONS_PUBLIEES = 3            # VERSION_SCHEMA_CSV de serveur.py et version de js/schema.js (2.0, 2.1)
TABLES_DU_FORMAT_4 = {"garanties", "contrats_prestataires", "reserves_controle"}
CODE_FORMAT_PLUS_RECENT = "format_plus_recent"
MANIFESTE = "manifeste.json"
DERNIERE_VERSION = "derniere-version.json"
MOTIF_AVANT_MISE_A_JOUR = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}_avant-mise-a-jour$")
MOTIF_QUOTIDIENNE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MOTIF_MANUELLE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}$")

# ---------------------------------------------------------------------------
# Code des versions publiées : git archive de l'étiquette, extrait une fois par module
# ---------------------------------------------------------------------------

_CODES = {}
_DOSSIER_DES_CODES = []


def tearDownModule():
    for dossier in _DOSSIER_DES_CODES:
        shutil.rmtree(dossier, ignore_errors=True)


def code_de(etiquette):
    """Dossier (Path) où le code de l'étiquette est extrait (git archive, une fois pour tout le module). Sans git, hors
    d'un dépôt, ou sans l'étiquette : unittest.SkipTest, en le disant. L'étiquette n'est que lue."""
    if etiquette in _CODES:
        return _CODES[etiquette]
    git = shutil.which("git")
    if git is None:
        raise unittest.SkipTest("git introuvable : le code de %s ne peut pas être extrait" % etiquette)
    verification = subprocess.run([git, "-C", str(RACINE), "rev-parse", "-q", "--verify",
                                   "refs/tags/%s^{commit}" % etiquette], capture_output=True)
    if verification.returncode != 0:
        raise unittest.SkipTest("étiquette git %s absente de ce dépôt (clone sans étiquettes ?)" % etiquette)
    if not _DOSSIER_DES_CODES:
        _DOSSIER_DES_CODES.append(Path(tempfile.mkdtemp(prefix="prevo-t396-code-")))
    dossier = _DOSSIER_DES_CODES[0] / etiquette
    archive = _DOSSIER_DES_CODES[0] / (etiquette + ".tar")
    subprocess.run([git, "-C", str(RACINE), "archive", "--format=tar", "-o", str(archive), etiquette],
                   check=True, capture_output=True)
    with tarfile.open(archive) as paquet:
        paquet.extractall(dossier, filter="data")
    archive.unlink()
    _CODES[etiquette] = dossier
    return dossier


def tables_du_code(code):
    """Les tables (TABLES) que le serveur.py de ce code connaît, dans l'ordre de son schéma."""
    arbre = ast.parse((code / "serveur.py").read_text(encoding="utf-8"))
    for noeud in arbre.body:
        if isinstance(noeud, ast.Assign) and any(getattr(cible, "id", None) == "TABLES" for cible in noeud.targets):
            return list(ast.literal_eval(noeud.value))
    raise AssertionError("TABLES introuvable dans %s" % (code / "serveur.py"))


class ServeurPublie(ServeurPrevo):
    """ServeurPrevo (tests/commun.py : copie temporaire des données, port libre, attente du ping, arrêt) qui lance le
    serveur.py d'un code extrait au lieu de celui du dépôt : même ligne de commande, dossier de travail = ce code."""

    def __init__(self, code, **options):
        super().__init__(**options)
        self.code = Path(code)

    def demarrer(self):
        with mock.patch.object(commun, "RACINE", self.code):
            super().demarrer()


# ---------------------------------------------------------------------------
# Aides
# ---------------------------------------------------------------------------

def fichiers_de(dossier):
    """{chemin relatif (« / ») : octets} de tous les fichiers du dossier."""
    dossier = Path(dossier)
    return {p.relative_to(dossier).as_posix(): p.read_bytes() for p in sorted(dossier.rglob("*")) if p.is_file()}


def fichiers_du_jeu(nom):
    with tempfile.TemporaryDirectory(prefix="prevo-t396-") as temporaire:
        return fichiers_de(copier_jeu(nom, Path(temporaire) / "donnees"))


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


def sauvegardes_de(fichiers):
    """{nom de sauvegarde : {fichier : octets}} relevés dans fichiers_de(dossier des données)."""
    resultat = {}
    for chemin, octets in fichiers.items():
        if chemin.startswith("sauvegardes/"):
            _, nom, fichier = chemin.split("/", 2)
            resultat.setdefault(nom, {})[fichier] = octets
    return resultat


# ---------------------------------------------------------------------------
# 1. Serveur des versions publiées sur une base au format 4
# ---------------------------------------------------------------------------

class TestServeurPublie(unittest.TestCase):

    def setUp(self):
        self.temporaire = Path(tempfile.mkdtemp(prefix="prevo-t396-"))
        self.addCleanup(shutil.rmtree, self.temporaire, True)

    def test_v2_1_0_lecture_seule_ecritures_refusees_aucun_octet_change(self):
        self.verifier_serveur("v2.1.0")

    def test_v2_0_0_lecture_seule_ecritures_refusees_aucun_octet_change(self):
        self.verifier_serveur("v2.0.0")

    def verifier_sauvegarde(self, nom, contenu, origine, tables, version, motif):
        """Sauvegarde faite par la version publiée sur la base au format 4 (risque 3) : ses tables seulement, copiées
        à l'octet, aucune des tables du format 4 ; manifeste « format » 4 (sauvegarde incomplète marquée format 4)."""
        manifeste = json.loads(contenu[MANIFESTE].decode("utf-8"))
        self.assertEqual(set(contenu) - {MANIFESTE}, {table + ".csv" for table in tables}, nom)
        for fichier, octets in contenu.items():
            if fichier != MANIFESTE:
                self.assertEqual(octets, origine[fichier], "%s/%s" % (nom, fichier))
        self.assertFalse({table + ".csv" for table in TABLES_DU_FORMAT_4} & set(contenu), nom)
        self.assertEqual((manifeste["version_appli"], manifeste["format"], manifeste["motif"], manifeste["mode"]),
                         (version, format_du_jeu(JEU), motif, "serveur"), nom)
        self.assertEqual(sorted(decrit["nom"] for decrit in manifeste["fichiers"]),
                         sorted(table + ".csv" for table in tables), nom)

    def verifier_serveur(self, etiquette):
        code = code_de(etiquette)
        version = etiquette[1:]
        self.assertIn("VERSION_APPLICATION = '%s'" % version, (code / "serveur.py").read_text(encoding="utf-8"))
        tables = tables_du_code(code)
        self.assertEqual(sorted(t + ".csv" for t in tables),
                         sorted(c for c in fichiers_du_jeu(JEU_DE_LA_2_1) if c.endswith(".csv")))
        source = copier_jeu(JEU, self.temporaire / etiquette / "donnees")
        origine = fichiers_de(source)
        self.assertEqual(format_du_jeu(JEU), 4)
        self.assertEqual({c[:-len(".csv")] for c in origine} - set(tables), TABLES_DU_FORMAT_4)

        with ServeurPublie(code, source=source) as serveur:
            # Démarrage sans erreur, en lecture seule.
            console = serveur.sortie_console()
            self.assertIn("LECTURE SEULE", console)
            self.assertNotIn("Traceback", console)
            statut, info = requete(serveur, "GET", "/api/info")
            self.assertEqual(statut, 200, info)
            etat = info["format"]
            self.assertEqual((etat["base"], etat["courant"], etat["plus_recent"], etat["migration"],
                              etat["tables_abimees"], etat["tables_vides"], etat["table_bloquee"]),
                             (4, FORMAT_DES_VERSIONS_PUBLIEES, True, "rien", [], [], None), etat)

            # Lectures permises : ses 24 tables, à l'octet ; les tables du format 4 lui sont inconnues.
            for table in tables:
                with self.subTest(lecture=table):
                    self.assertEqual(requete(serveur, "GET", "/api/csv/" + table), (200, origine[table + ".csv"]))
            for table in sorted(TABLES_DU_FORMAT_4):
                with self.subTest(table_inconnue=table):
                    statut, reponse = requete(serveur, "GET", "/api/csv/" + table)
                    self.assertEqual((statut, reponse["erreur_code"]), (404, "csv.table_inconnue"), reponse)

            # Écritures refusées : 409 « format_plus_recent », format 4 (la restauration de la sauvegarde du jour,
            # qui n'a que 24 tables, comprise).
            quotidienne = [nom for nom in sauvegardes_de(fichiers_de(serveur.dossier)) if MOTIF_QUOTIDIENNE.match(nom)]
            self.assertEqual(len(quotidienne), 1, quotidienne)
            ligne_de_journal = ("id;date_heure;poste;profil;table;id_ligne;action\r\n"
                                "J-1;2026-11-08 10:00;P;;t;i;a\r\n").encode("utf-8")
            ecritures = [
                ("PUT", "/api/csv/equipements", origine["equipements.csv"], {"X-Version-Attendue": "aucune"}),
                ("PUT", "/api/csv/parametres", b"", {}),
                ("POST", "/api/csv/journal/ajout", ligne_de_journal, {}),
                ("PUT", "/api/documents/essai.pdf", b"%PDF-1.4\n", {"Content-Type": "application/pdf"}),
                ("POST", "/api/restauration", json.dumps({"sauvegarde": quotidienne[0]}).encode("utf-8"),
                 {"Content-Type": "application/json"}),
            ]
            for methode, chemin, corps, entetes in ecritures:
                with self.subTest(ecriture=methode + " " + chemin):
                    statut, reponse = requete(serveur, methode, chemin, corps, entetes)
                    self.assertEqual(statut, 409, reponse)
                    self.assertEqual((reponse["code"], reponse["format"]), (CODE_FORMAT_PLUS_RECENT, 4), reponse)
                    self.assertIn("version plus récente de Prévo", reponse["erreur"])
                    self.assertIn("format 4", reponse["erreur"])
            for table in sorted(TABLES_DU_FORMAT_4):
                with self.subTest(ecriture_table_inconnue=table):
                    statut, reponse = requete(serveur, "PUT", "/api/csv/" + table, origine[table + ".csv"],
                                              {"X-Version-Attendue": "aucune"})
                    self.assertEqual((statut, reponse["erreur_code"]), (404, "csv.table_inconnue"), reponse)

            # Sauvegarde manuelle permise (D169).
            statut, reponse = requete(serveur, "POST", "/api/sauvegarde")
            self.assertEqual(statut, 200, reponse)

            # Aucun octet des 27 CSV changé, aucun document ; seuls derniere-version.json et les sauvegardes s'ajoutent.
            apres = fichiers_de(serveur.dossier)
            for chemin, octets in origine.items():
                self.assertEqual(apres.get(chemin), octets, chemin)
            ajoutes = sorted(c for c in set(apres) - set(origine) if not c.startswith("sauvegardes/"))
            self.assertEqual(ajoutes, [DERNIERE_VERSION])
            self.assertEqual(json.loads(apres[DERNIERE_VERSION].decode("utf-8"))["version"], version)
            self.assertEqual(list((serveur.dossier / "documents").iterdir()), [])

            # Risque 3 : les sauvegardes faites par la version publiée n'ont que ses 24 tables (marquées format 4).
            sauvegardes = sauvegardes_de(apres)
            motifs = {}
            for nom in sauvegardes:
                motif = ("avant-mise-a-jour" if MOTIF_AVANT_MISE_A_JOUR.match(nom) else
                         "quotidienne" if MOTIF_QUOTIDIENNE.match(nom) else
                         "manuelle" if MOTIF_MANUELLE.match(nom) else nom)
                motifs[motif] = motifs.get(motif, 0) + 1
                self.verifier_sauvegarde(nom, sauvegardes[nom], origine, tables, version, motif)
            self.assertEqual(motifs, {"avant-mise-a-jour": 1, "quotidienne": 1, "manuelle": 1})
            laisse = shutil.copytree(serveur.dossier, self.temporaire / etiquette / "laisse")

        # Second démarrage sur le dossier ainsi laissé : rien de plus.
        avant = fichiers_de(laisse)
        with ServeurPublie(code, source=laisse) as serveur:
            self.assertIn("LECTURE SEULE", serveur.sortie_console())
            self.assertNotIn("Traceback", serveur.sortie_console())
            self.assertEqual(fichiers_de(serveur.dossier), avant)


# ---------------------------------------------------------------------------
# 2. Navigateur de la 2.1 sur une base au format 4 (dossier, puis serveur)
# ---------------------------------------------------------------------------

ERREUR_PING_ABSENT = re.compile(r"status of 404.*/api/ping")      # serveur statique : pas de /api/ping
NOM_DOSSIER = "donnees-t396"

ECRIRE_OPFS_JS = """async ([nom, fichiers]) => {
  let racine = await (await navigator.storage.getDirectory()).getDirectoryHandle(nom, { create: true });
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

# Écritures directes par l'API de la 2.1 (js/donnees.js, adaptateurs) : toutes refusées en lecture seule.
TENTER_ECRITURES_JS = """async () => {
  const essais = {
    modifier: () => Donnees.modifier('parametres', (lignes) => { lignes.push({ cle: 'essai', valeur: '1' }); }),
    ajouter: () => Donnees.ajouter('journal', [{ table: 'parametres', id_ligne: 'essai', action: 'essai' }]),
    enregistrer: () => App.adaptateur.enregistrer('parametres', new Uint8Array([1]), null),
    ecrireDocument: () => App.adaptateur.ecrireDocument('essai.txt', new Blob(['essai'])),
    sauvegarder: () => App.adaptateur.sauvegarder(),
    restaurer: () => App.adaptateur.restaurer('2000-01-01'),
    migrer: () => Donnees.migrerAuFormatCourant(),
  };
  const resultats = {};
  for (const [nom, essai] of Object.entries(essais)) {
    try {
      resultats[nom] = { ok: true, valeur: await essai() };
    } catch (erreur) {
      resultats[nom] = { ok: false, nom: erreur.name, lectureSeule: erreur instanceof Donnees.ErreurLectureSeule,
        stockage: erreur instanceof Donnees.ErreurStockage, message: erreur.message };
    }
  }
  return resultats;
}"""

# Écran suivant : les enfants de #contenu sont marqués, puis l'adresse change ; l'écran est affiché quand un enfant non
# marqué apparaît (rendre() de js/app.js vide #contenu avant d'afficher l'écran). Certains écrans complètent l'adresse
# (« #/preventif?onglet=gammes ») : seul le chemin est comparé.
ALLER_JS = """(route) => {
  for (const enfant of document.getElementById('contenu').children) enfant.dataset.t396Ancien = '1';
  location.hash = route;
}"""
ECRAN_AFFICHE_JS = """(route) => location.hash.split('?')[0] === route
  && document.querySelector('#contenu > :not([data-t396-ancien])') !== null"""
# Écrans principaux du responsable dans la 2.1 (menu de la 2.1), avec des fiches touchées par les colonnes du format 4
# (EQ-0001 et EQ-0007 : cout_arret_h ; OT-2025-0005 : habilitation_requise ; CTR-0001 : source_periodicite
# « catalogue » ; CTR-0004 : la réserve reprise RES-00001) ; habilitations (recyclage_mois, justificatif) dans l'équipe.
# L'application s'ouvre sur l'accueil : il vient après un autre écran (même adresse : rien ne serait réaffiché).
ECRANS = ("#/parc", "#/accueil", "#/equipement/EQ-0001", "#/equipement/EQ-0007", "#/ot", "#/ot/OT-2025-0005",
          "#/preventif", "#/planning", "#/controles", "#/controles/CTR-0001", "#/controles/CTR-0004", "#/equipe",
          "#/magasin", "#/indicateurs", "#/wiki", "#/di", "#/di/nouvelle", "#/parametres", "#/poste", "#/apropos")


class TestNavigateurPublie(CasNavigateur):

    @classmethod
    def setUpClass(cls):
        cls.code = code_de(ETIQUETTE_DU_NAVIGATEUR)          # avant le navigateur : rien à lancer sans l'étiquette
        super().setUpClass()

    # -- aides -------------------------------------------------------------------------------

    def instantane(self):
        brut = self.page.evaluate(INSTANTANE_OPFS_JS, NOM_DOSSIER)
        return {chemin: base64.b64decode(valeur) for chemin, valeur in brut.items()}

    def verifier_bandeau(self, ou):
        bandeau = self.page.locator("#alertes-app #bandeau-lecture-seule")
        self.assertTrue(bandeau.is_visible(), ou)
        texte = bandeau.inner_text()
        self.assertIn("Lecture seule", texte, ou)
        self.assertIn("format 4", texte, ou)
        self.assertEqual(bandeau.locator("button").count(), 0, ou)       # pas de « Fermer »

    def verifier_ecrans(self):
        """Chaque écran de ECRANS s'affiche (ni « Écran introuvable », ni « Cet écran n'a pas pu s'afficher »), avec le
        bandeau de lecture seule ; les erreurs de console font échouer le test (CasNavigateur)."""
        for route in ECRANS:
            with self.subTest(ecran=route):
                self.page.evaluate(ALLER_JS, route)
                self.page.wait_for_function(ECRAN_AFFICHE_JS, arg=route)
                self.page.wait_for_load_state("networkidle")
                contenu = self.page.inner_text("#contenu")
                self.assertNotIn("pas pu s'afficher", contenu)
                self.assertNotIn("Écran introuvable", contenu)
                self.verifier_bandeau(route)

    def verifier_refus(self, resultats):
        migrer = resultats.pop("migrer")
        self.assertEqual((migrer["ok"], migrer["valeur"]["misAJour"]), (True, False), migrer)
        for nom, resultat in resultats.items():
            with self.subTest(ecriture=nom):
                self.assertFalse(resultat["ok"], resultat)
                self.assertEqual(resultat["nom"], "ErreurLectureSeule")
                self.assertTrue(resultat["lectureSeule"] and resultat["stockage"])
                self.assertIn("version plus récente de Prévo", resultat["message"])
                self.assertIn("format 4", resultat["message"])

    def verifier_ouverture(self, mode):
        self.assertEqual(self.page.evaluate("App.mode"), mode)
        self.assertTrue(self.page.evaluate("Donnees.lectureSeule()"))
        etat = self.page.evaluate("Donnees.etatDuFormat()")
        self.assertEqual((etat["base"], etat["courant"], etat["plusRecent"], etat["aCompleter"], etat["abimees"]),
                         (4, FORMAT_DES_VERSIONS_PUBLIEES, True, [], []), etat)
        # Les tables qu'elle connaît sont lues (les colonnes du format 4 en plus ne la gênent pas).
        lues = self.page.evaluate("""() => ({ equipements: Donnees.lignes('equipements').length,
          ordres: Donnees.lignes('ordres_travail').length, controles: Donnees.lignes('controles_reglementaires').length,
          habilitations: Donnees.lignes('habilitations').length })""")
        self.assertTrue(all(nombre > 0 for nombre in lues.values()), lues)
        self.verifier_bandeau("ouverture")

    # -- cas -----------------------------------------------------------------------------------

    def test_dossier_bandeau_ecrans_sans_erreur_aucun_octet_ecrit(self):
        self.autoriser_erreur(ERREUR_PING_ABSENT)
        origine = fichiers_du_jeu(JEU)
        with ServeurStatique(self.code) as statique:
            installer_dossier_simule(self.contexte, NOM_DOSSIER)
            preregler_profil(self.contexte, "responsable", nom="Claire Essai")
            self.page.goto(statique.url + "/index.html")
            self.page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
            self.assertEqual(self.page.evaluate("[App.version, Schema.version]"),
                             [ETIQUETTE_DU_NAVIGATEUR[1:], FORMAT_DES_VERSIONS_PUBLIEES])     # le code de l'étiquette
            envoyes = {chemin: base64.b64encode(octets).decode("ascii") for chemin, octets in origine.items()}
            self.page.evaluate(ECRIRE_OPFS_JS, [NOM_DOSSIER, envoyes])
            self.assertEqual(self.instantane(), origine)
            self.page.click("#btn-dossier")
            attendre_pret(self.page)
            self.page.wait_for_load_state("networkidle")
            self.verifier_ouverture("dossier")
            self.verifier_ecrans()
            self.verifier_refus(self.page.evaluate(TENTER_ECRITURES_JS))
            # Aucun octet modifié : ni sauvegarde, ni journal, ni verrou.txt, ni derniere-version.json.
            self.assertEqual(self.instantane(), origine)

            # Seconde ouverture : toujours rien.
            self.page.wait_for_load_state("networkidle")
            self.page.reload()
            self.page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
            self.page.click("#btn-reprendre")
            attendre_pret(self.page)
            self.page.wait_for_load_state("networkidle")
            self.verifier_ouverture("dossier")
            self.assertEqual(self.instantane(), origine)

    def test_serveur_bandeau_ecrans_sans_erreur_le_navigateur_n_ecrit_rien(self):
        with tempfile.TemporaryDirectory(prefix="prevo-t396-") as temporaire:
            source = copier_jeu(JEU, Path(temporaire) / "donnees")
            with ServeurPublie(self.code, source=source) as serveur:
                avant = fichiers_de(serveur.dossier)
                preregler_profil(self.contexte, "responsable", nom="Claire Essai")
                self.page.goto(serveur.url + "/#/accueil")
                attendre_pret(self.page)
                self.page.wait_for_load_state("networkidle")
                self.assertEqual(self.page.evaluate("[App.version, Schema.version]"),
                                 [ETIQUETTE_DU_NAVIGATEUR[1:], FORMAT_DES_VERSIONS_PUBLIEES])
                self.verifier_ouverture("serveur")
                self.verifier_ecrans()
                self.verifier_refus(self.page.evaluate(TENTER_ECRITURES_JS))
                self.assertEqual(fichiers_de(serveur.dossier), avant)
                self.assertNotIn("Traceback", serveur.sortie_console())


if __name__ == "__main__":
    unittest.main()
