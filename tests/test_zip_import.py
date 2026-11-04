"""Import ZIP (chantier « socle de données », T191 ; décision D172 ; ARCHITECTURE.md §22.11 « Import ZIP ») :
js/modules/parametres-zip.js (ParametresZip), bouton « Importer un ZIP… » de Paramètres › Sauvegardes.

Le ZIP arrive par le vrai <input type="file"> de la carte (page.set_input_files) ; il est fabriqué en Python (zipfile,
manifeste exact calculé par hashlib) ou par l'export de Prévo (vrai bouton « Exporter en ZIP », téléchargement capturé).
Chaque écriture est contrôlée sur le disque (serveur) ou dans l'OPFS du navigateur (mode dossier) :

    serveur   ServeurPrevo (copies de jeux dans des dossiers temporaires) :
              aller-retour : base A (démo + documents cités dans les trois colonnes, deux rapports figés, deux photos au
              même nom demandé, un document cité absent) exportée par le responsable, puis importée dans une base B
              (f3-v1.2.0 + un document déjà là), comptes exigés : confirmation (nombres de lignes, aucun format changé,
              avertissement), mêmes données champ à champ (journal : une ligne de plus), documents présents à l'octet et
              références réécrites vers les noms rendus par le serveur, ancien document gardé, sauvegarde
              « avant-import-zip » avec les CSV d'avant à l'octet, documents/ et manifeste, acces/ inchangé ; puis
              rechargement de l'application ;
              technicien connecté : ni Paramètres ni bouton, ParametresZip.importer refusé ;
              ZIP au format 2 (f2-v1.1.0, sans manifeste) : confirmation « mises au format 3 », deux tables vidées ;
              base au format 3, lignes intactes, colonne astuce vide, tables du wiki vides ; colonnes inconnues du
              ZIP (jeu colonnes-en-trop) gardées avec leurs valeurs ;
              annulation à la confirmation : aucun octet changé ; ZIP hostile (« ../x.csv ») et ZIP plus récent
              (format 4) : refus, aucun octet changé ;
              échec simulé pendant l'écriture de ordres_travail : tables remises à l'octet depuis la sauvegarde,
              message qui la nomme ;
    dossier   OPFS (installer_dossier_simule) : f3-v2.0.0 (avec acces/) + deux documents déjà là ; import d'un ZIP
              (démo + documents, manifeste) : document identique repris, nom pris par un autre contenu → « -2 »,
              sauvegarde « avant-import-zip » (CSV d'avant, documents/), acces/ intact ; rechargement puis
              « Reprendre » ; base en lecture seule (jeu plus-recent) : import refusé, aucun octet écrit ;
    démo      bouton inactif, « indisponible en démo ».

Règle numéro un : jamais de données réelles (copies dans des dossiers temporaires, OPFS du navigateur de test).

Lancer depuis la racine du projet (à travers le verrou du navigateur) :
    py -X utf8 -m unittest discover -s tests -p "test_zip_import.py" -v
"""
import base64
import csv
import hashlib
import io
import json
import re
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from commun import (RACINE, CasNavigateur, ServeurPrevo, ServeurStatique, attendre_pret, installer_dossier_simule,
                    preregler_profil, url_fichier)
from jeux_formats import copier_jeu

DOSSIER_DEMO = RACINE / "donnees" / "demo"
TABLES = sorted(chemin.stem for chemin in DOSSIER_DEMO.glob("*.csv"))         # les 24 tables du format 3
CHAMPS_DOCUMENTS = {"equipements": "document", "demandes": "photo", "controles_reglementaires": "rapport"}
AVERTISSEMENT = ("Toutes les données actuelles seront remplacées ; une sauvegarde complète, documents compris, est "
                 "faite juste avant ; les comptes et l'accès ne sont pas touchés.")
RAISON_RESERVE = "L'import ZIP est réservé au responsable : il remplace toutes les données."
BOUTON_REMPLACER = "dialog button:has-text('Remplacer toutes les données')"
BOUTON_ANNULER = "dialog button:has-text('Annuler')"
BOUTON_FERMER = "dialog .fenetre-actions button:has-text('Fermer')"
PREFIXE_SERVEUR = re.compile(r"^\d{8}-\d{6}-")
MOTIF_AVANT_IMPORT_ZIP = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}_avant-import-zip$")
MOTIF_AVANT_RESTAURATION = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}_avant-restauration$")
NOM_DOSSIER = "donnees-zip-import"
NOM_PIEGE = "../acces/comptes.json"

# Chromium note en console.error toute réponse HTTP >= 400 : seules celles-ci sont attendues.
ERREUR_PING_ABSENT = re.compile(r"status of 404.*/api/ping")              # serveur statique : pas de /api/ping
ERREUR_DOCUMENT_ABSENT = re.compile(r"status of 404.*/api/documents/vgp-chariot-absent\.pdf")
ERREUR_TABLE_REFUSEE = re.compile(r"status of 403 .*/api/csv/")

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

# Écriture d'une table qui échoue (panne simulée côté page) : l'adaptateur protégé de l'application est une vue de
# l'adaptateur ; une méthode remplacée sur la vue l'est sur l'adaptateur (Donnees.protegerEcritures).
PANNE_ENREGISTRER_JS = """(table) => {
  const vrai = App.adaptateur.enregistrer;
  App.adaptateur.enregistrer = function (nomTable, ...reste) {
    if (nomTable === table) {
      return Promise.reject(new Donnees.ErreurStockage('panne simulée pendant l\\'écriture de ' + table + '.'));
    }
    return vrai.call(this, nomTable, ...reste);
  };
}"""


# ---------------------------------------------------------------------------
# Fichiers, CSV et ZIP
# ---------------------------------------------------------------------------

def octets_pdf(graine):
    return b"%PDF-1.4\n% document de test : " + graine.encode("utf-8") + b"\n" + bytes(range(256))


def octets_png(graine):
    return b"\x89PNG\r\n\x1a\n" + graine.encode("utf-8") + bytes(range(255, -1, -1))


def page_rapport(mois):
    return ('<!doctype html><html lang="fr"><meta charset="utf-8"><title>Rapport %s</title>'
            '<p>Rapport figé de test — %s</p></html>' % (mois, mois)).encode("utf-8")


def en_base64(octets):
    return base64.b64encode(octets).decode("ascii")


def remplacer_une_fois(fichiers, nom, avant, apres):
    """Remplace dans un CSV ({nom: octets}) un passage qui doit y être exactement une fois."""
    texte = fichiers[nom].decode("utf-8")
    if texte.count(avant) != 1:
        raise AssertionError("%s : %r trouvé %d fois" % (nom, avant, texte.count(avant)))
    fichiers[nom] = texte.replace(avant, apres).encode("utf-8")


def fichiers_du_jeu(nom):
    """{chemin relatif (« / ») : octets} d'une copie du jeu, faite dans un dossier temporaire."""
    with tempfile.TemporaryDirectory(prefix="prevo-zip-import-") as temporaire:
        dossier = copier_jeu(nom, Path(temporaire) / "donnees")
        return {p.relative_to(dossier).as_posix(): p.read_bytes() for p in sorted(dossier.rglob("*")) if p.is_file()}


def fichiers_demo():
    return {chemin.name: chemin.read_bytes() for chemin in sorted(DOSSIER_DEMO.glob("*.csv"))}


# Base A de l'aller-retour (et contenu du ZIP du mode dossier) : la démo, avec des documents cités dans les trois
# colonnes, deux rapports figés (dont un au nom horodaté par le serveur), deux photos au même nom demandé
# (« photo-tapis.png ») et deux références sans document (absent, nom piégé).
DOCUMENTS_A = {
    "notice-perceuse.pdf": octets_pdf("perceuse"),
    "20261019-101500-photo-tapis.png": octets_png("tapis"),
    "20261020-111500-photo-tapis.png": octets_png("tapis, deuxième photo"),
    "vgp-pont-2026.pdf": octets_pdf("vgp"),
    "rapport-mensuel-2026-08.html": page_rapport("2026-08"),
    "20261001-083000-rapport-mensuel-2026-09.html": page_rapport("2026-09"),
}


def base_a():
    """{nom de fichier CSV : octets} de la base A et {nom : octets} de ses documents."""
    fichiers = fichiers_demo()
    remplacer_une_fois(fichiers, "equipements.csv", ";rebut;8;;;;0;2400", ";rebut;8;;;notice-perceuse.pdf;0;2400")
    remplacer_une_fois(fichiers, "demandes.csv", "clignote.;arrêt;;;Acceptée",
                       "clignote.;arrêt;;20261019-101500-photo-tapis.png;Acceptée")
    remplacer_une_fois(fichiers, "demandes.csv",
                       "en sécurité.;arrêt;Le problème apparaît surtout quand la machine est chaude.;;Acceptée",
                       "en sécurité.;arrêt;Le problème apparaît surtout quand la machine est chaude.;%s;Acceptée"
                       % NOM_PIEGE)
    remplacer_une_fois(fichiers, "controles_reglementaires.csv", "2026-02-10;2027-02-10;;;1",
                       "2026-02-10;2027-02-10;vgp-pont-2026.pdf;;1")
    remplacer_une_fois(fichiers, "controles_reglementaires.csv", "2026-03-18;2026-09-18;;;1",
                       "2026-03-18;2026-09-18;vgp-chariot-absent.pdf;;1")
    remplacer_une_fois(fichiers, "controles_reglementaires.csv", "2025-11-12;2026-11-12;;;1",
                       "2025-11-12;2026-11-12;20261020-111500-photo-tapis.png;;1")
    fichiers["parametres.csv"] += ("rapports_mensuels;rapport-mensuel-2026-08.html,"
                                   "20261001-083000-rapport-mensuel-2026-09.html\r\n").encode("utf-8")
    return fichiers, dict(DOCUMENTS_A)


def manifeste(fichiers, format=3):
    """Octets d'un manifeste exact (comme Formats.manifeste) des fichiers donnés."""
    contenu = {"application": "Prévo", "version_appli": "2.0.1", "format": format, "date": "2026-11-04T09:30:00",
               "motif": "export", "mode": "dossier",
               "fichiers": [{"nom": nom, "octets": len(octets), "sha256": hashlib.sha256(octets).hexdigest()}
                            for nom, octets in sorted(fichiers.items())]}
    return json.dumps(contenu, ensure_ascii=False, indent=2).encode("utf-8")


def ecrire_zip(chemin, entrees, avec_manifeste=True):
    """Écrit un ZIP ({nom: octets}, noms TELS QUELS, chemins hostiles compris), avec le manifeste exact au besoin."""
    entrees = dict(entrees)
    if avec_manifeste:
        entrees["manifeste.json"] = manifeste(entrees)
    with zipfile.ZipFile(chemin, "w", zipfile.ZIP_DEFLATED) as archive:
        for nom, octets in entrees.items():
            info = zipfile.ZipInfo("provisoire", date_time=(2026, 11, 4, 9, 30, 0))
            info.filename = nom
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, octets)
    return chemin


def lire_csv(octets):
    """(en-tête, [ligne en dictionnaire]) d'un CSV de Prévo (BOM, « ; », guillemets, lignes vides ignorées)."""
    lignes = [ligne for ligne in csv.reader(io.StringIO(octets.decode("utf-8-sig"), newline=""), delimiter=";")
              if any(cellule.strip() for cellule in ligne)]
    return lignes[0], [dict(zip(lignes[0], ligne)) for ligne in lignes[1:]]


def sans_apostrophe(valeur):
    """Valeur lue d'une cellule : l'apostrophe de protection (§3.1) n'en fait pas partie."""
    return valeur[1:] if valeur.startswith("'") else valeur


def sans_prefixe(nom):
    """Nom demandé d'un document : sans le préfixe « AAAAMMJJ-HHMMSS- » imposé par le serveur."""
    return PREFIXE_SERVEUR.sub("", nom)


def instantane(dossier):
    """{chemin relatif (« / ») : octets} de tout un dossier."""
    return {p.relative_to(dossier).as_posix(): p.read_bytes() for p in sorted(Path(dossier).rglob("*")) if p.is_file()}


def sauvegardes_de(fichiers, motif):
    """Noms des sauvegardes (dossiers de sauvegardes/) dont le nom suit le motif."""
    return sorted({chemin.split("/")[1] for chemin in fichiers
                   if chemin.startswith("sauvegardes/") and chemin.count("/") >= 2 and motif.match(chemin.split("/")[1])})


def contenu_sauvegarde(fichiers, nom):
    prefixe = "sauvegardes/%s/" % nom
    return {chemin[len(prefixe):]: octets for chemin, octets in fichiers.items() if chemin.startswith(prefixe)}


# ---------------------------------------------------------------------------
# Cas commun
# ---------------------------------------------------------------------------

class CasImport(CasNavigateur):

    def setUp(self):
        super().setUp()
        self.temporaire = Path(tempfile.mkdtemp(prefix="prevo-zip-import-"))
        self.addCleanup(shutil.rmtree, self.temporaire, ignore_errors=True)

    def choisir_zip(self, page, chemin):
        page.wait_for_selector("#btn-import-zip")
        page.set_input_files("#fichier-import-zip", str(chemin))

    def confirmation(self, page):
        """Attend la fenêtre de confirmation → ses informations (attributs, textes, nombres par table)."""
        page.wait_for_selector("#confirmation-import-zip")
        return page.evaluate("""() => {
          const zone = document.getElementById('confirmation-import-zip');
          const nombres = (attribut) => Object.fromEntries(Array.from(zone.querySelectorAll('[' + attribut + ']'))
            .map((e) => [e.getAttribute(attribut), Number(e.textContent)]));
          const texte = (id) => { const e = document.getElementById(id); return e ? e.textContent.replace(/\\s+/g, ' ').trim() : null; };
          return { format: zone.dataset.format, migre: zone.dataset.migre, documents: Number(zone.dataset.documents),
            actuel: nombres('data-actuel'), importe: nombres('data-importe'),
            videes: Array.from(zone.querySelectorAll('[data-videe]')).map((e) => e.dataset.videe),
            origine: texte('origine-import-zip'), formatTexte: texte('format-import-zip'),
            tablesVidees: texte('tables-videes-import-zip'), documentsTexte: texte('documents-import-zip'),
            problemes: texte('problemes-import-zip'), avertissement: texte('avertissement-import-zip') };
        }""")

    def texte_fenetre(self, page, identifiant):
        page.wait_for_selector("#" + identifiant)
        return re.sub(r"\s+", " ", page.inner_text("#" + identifiant)).strip()

    def fermer_fenetre(self, page, identifiant):
        page.click(BOUTON_FERMER)
        page.wait_for_selector("#" + identifiant, state="detached")

    def verifier_donnees(self, attendus, obtenus, documents_zip, documents_cible, nom_zip):
        """Compare, champ à champ, les tables écrites ({table: octets}) à celles du ZIP ({table: octets}, format
        courant). Une référence à un document du ZIP doit viser un document de documents_cible au même contenu et au
        même nom demandé (préfixe du serveur ou « -N » permis) ; toute autre valeur est identique. Le journal a une
        ligne de plus, celle de l'import. Rend {nom dans le ZIP : nom rendu}."""
        rendus = {}

        def document(valeur_zip, valeur, ou):
            if valeur_zip not in documents_zip:
                self.assertEqual(valeur, valeur_zip, ou)
                return
            self.assertIn(valeur, documents_cible, ou)
            self.assertEqual(documents_cible[valeur], documents_zip[valeur_zip], ou)
            base, point, extension = sans_prefixe(valeur_zip).rpartition(".")
            self.assertRegex(valeur, r"^(\d{8}-\d{6}-)?%s(-\d+)?\.%s$" % (re.escape(base), re.escape(extension)), ou)
            self.assertEqual(rendus.setdefault(valeur_zip, valeur), valeur, ou)

        for table in TABLES:
            entete_a, lignes_a = lire_csv(attendus[table])
            entete_o, lignes_o = lire_csv(obtenus[table])
            self.assertEqual(entete_o, entete_a, table)
            if table == "journal":
                self.assertEqual(len(lignes_o), len(lignes_a) + 1)
                derniere = lignes_o.pop()
                self.assertEqual(derniere["table"], "parametres")
                self.assertRegex(derniere["action"], r"^import ZIP : %s, 24 tables, %d documents? ; sauvegarde "
                                 r"\d{4}-\d{2}-\d{2}_\d{6}_avant-import-zip faite juste avant$"
                                 % (re.escape(nom_zip), len(documents_zip)))
            self.assertEqual(len(lignes_o), len(lignes_a), table)
            for rang, (ligne_a, ligne_o) in enumerate(zip(lignes_a, lignes_o)):
                for colonne in entete_a:
                    ou = "%s ligne %d colonne %s" % (table, rang + 2, colonne)
                    if CHAMPS_DOCUMENTS.get(table) == colonne:
                        document(ligne_a[colonne], ligne_o[colonne], ou)
                    elif table == "parametres" and colonne == "valeur" and ligne_a["cle"] == "rapports_mensuels":
                        noms_a, noms_o = ligne_a[colonne].split(","), ligne_o[colonne].split(",")
                        self.assertEqual(len(noms_o), len(noms_a), ou)
                        for nom_a, nom_o in zip(noms_a, noms_o):
                            document(nom_a, nom_o, ou)
                    else:
                        self.assertEqual(ligne_o[colonne], ligne_a[colonne], ou)
        return rendus


# ---------------------------------------------------------------------------
# Mode serveur
# ---------------------------------------------------------------------------

class TestServeur(CasImport):

    def ouvrir_parametres(self, serveur, role=None):
        if role:
            serveur.poser_session(self.contexte, role)
        else:
            preregler_profil(self.contexte, "responsable")
        page = self.page
        page.goto(serveur.url + "/#/parametres")
        attendre_pret(page)
        page.wait_for_selector("#btn-import-zip")
        return page

    def dossier_source(self, nom, fichiers):
        dossier = self.temporaire / nom
        for chemin, octets in fichiers.items():
            (dossier / chemin).parent.mkdir(parents=True, exist_ok=True)
            (dossier / chemin).write_bytes(octets)
        return dossier

    def csv_du_dossier(self, dossier):
        return {table: (Path(dossier) / (table + ".csv")).read_bytes() for table in TABLES}

    def test_serveur_aller_retour_export_puis_import_memes_donnees_documents_sauvegarde_acces(self):
        self.autoriser_erreur(ERREUR_DOCUMENT_ABSENT)
        # 1. Base A exportée par le responsable (vrai bouton).
        csv_a, documents_a = base_a()
        source_a = self.dossier_source("a", dict(csv_a, **{"documents/" + nom: o for nom, o in documents_a.items()}))
        chemin_zip = self.temporaire / "prevo-export-a.zip"
        with ServeurPrevo(source=source_a, comptes=True) as serveur_a:
            page = self.ouvrir_parametres(serveur_a, "responsable")
            with page.expect_download() as attente:
                page.click("#btn-export-zip")
            attente.value.save_as(str(chemin_zip))
        with zipfile.ZipFile(chemin_zip) as archive:
            entrees = {nom: archive.read(nom) for nom in archive.namelist()}
        documents_zip = {nom[len("documents/"):]: o for nom, o in entrees.items() if nom.startswith("documents/")}
        self.assertEqual(documents_zip, documents_a)
        csv_zip = {table: entrees[table + ".csv"] for table in TABLES}

        # 2. Base B (f3-v1.2.0 et un document déjà là), comptes exigés : import par le responsable.
        ancien = octets_pdf("ancien document de B")
        source_b = self.dossier_source("b", dict(fichiers_du_jeu("f3-v1.2.0"), **{"documents/ancien.pdf": ancien}))
        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
        self.addCleanup(contexte.close)
        contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        with ServeurPrevo(source=source_b, comptes=True) as serveur:
            serveur.poser_session(contexte, "responsable")
            page = contexte.new_page()
            self.surveiller(page)
            page.goto(serveur.url + "/#/parametres")
            attendre_pret(page)
            self.assertEqual(page.evaluate("ParametresZip.etat()"), {"visible": True, "permis": True, "raison": ""})
            avant = instantane(serveur.dossier)
            csv_b = self.csv_du_dossier(serveur.dossier)
            self.choisir_zip(page, chemin_zip)
            info = self.confirmation(page)
            self.assertEqual((info["format"], info["migre"], info["documents"]), ("3", "0", 6))
            self.assertEqual(info["actuel"], {table: len(lire_csv(csv_b[table])[1]) for table in TABLES})
            self.assertEqual(info["importe"], {table: len(lire_csv(csv_zip[table])[1]) for table in TABLES})
            self.assertEqual(info["videes"], [])
            self.assertIsNone(info["tablesVidees"])
            self.assertRegex(info["origine"], r"^Exporté le \d{2}/\d{2}/\d{4} à \d{2}:\d{2} par Prévo [0-9.]+ "
                                              r"\(mode serveur\)\.$")
            self.assertEqual(info["formatTexte"], "Format des données : 3 (format de cette version).")
            self.assertIn("6 documents joints", info["documentsTexte"])
            self.assertIn("vgp-chariot-absent.pdf", info["problemes"])       # cité, introuvable à l'export
            self.assertEqual(info["avertissement"], AVERTISSEMENT)
            page.click(BOUTON_REMPLACER)
            termine = self.texte_fenetre(page, "import-zip-termine")
            self.assertIn("24 tables remplacées, 6 documents", termine)
            apres = instantane(serveur.dossier)

            # Données : champ à champ, références vers les noms rendus par le serveur (horodatés, « -2 » au besoin).
            documents_b = {chemin[len("documents/"):]: o for chemin, o in apres.items() if chemin.startswith("documents/")}
            rendus = self.verifier_donnees(csv_zip, self.csv_du_dossier(serveur.dossier), documents_zip, documents_b,
                                           chemin_zip.name)
            self.assertEqual(sorted(rendus), sorted(documents_zip))
            for nom_zip, rendu in rendus.items():
                self.assertRegex(rendu, PREFIXE_SERVEUR, nom_zip)            # nom imposé par le serveur
            demandes = sorted(sans_prefixe(rendu) for rendu in rendus.values())
            self.assertIn("photo-tapis.png", demandes)
            self.assertIn("photo-tapis-2.png", demandes)                     # même nom demandé : « -2 »
            self.assertEqual(documents_b["ancien.pdf"], ancien)              # jamais supprimé
            self.assertEqual(len(documents_b), len(documents_zip) + 1)
            self.assertIn(b"version_schema;'3", apres["parametres.csv"])

            # Sauvegarde « avant-import-zip » : CSV d'avant à l'octet, documents/, comptes, manifeste.
            noms = sauvegardes_de(apres, MOTIF_AVANT_IMPORT_ZIP)
            self.assertEqual(len(noms), 1, noms)
            self.assertIn(noms[0], termine)
            sauvegarde = contenu_sauvegarde(apres, noms[0])
            for table in TABLES:
                self.assertEqual(sauvegarde[table + ".csv"], avant[table + ".csv"], table)
            self.assertEqual(sauvegarde["documents/ancien.pdf"], ancien)
            self.assertEqual(sauvegarde["acces/comptes.json"], avant["acces/comptes.json"])
            self.assertEqual(json.loads(sauvegarde["manifeste.json"])["motif"], "avant-import-zip")

            # acces/ : octet pour octet (sessions.json : mêmes sessions, « vu_le » peut glisser d'une minute).
            acces_avant = {c: o for c, o in avant.items() if c.startswith("acces/")}
            acces_apres = {c: o for c, o in apres.items() if c.startswith("acces/")}
            self.assertEqual(sorted(acces_apres), sorted(acces_avant))
            for chemin, octets in acces_avant.items():
                if chemin == "acces/sessions.json":
                    oublier_vu = lambda o: {k: {c: v for c, v in s.items() if c != "vu_le"} for k, s in json.loads(o).items()}
                    self.assertEqual(oublier_vu(acces_apres[chemin]), oublier_vu(octets))
                else:
                    self.assertEqual(acces_apres[chemin], octets, chemin)

            # Rechargement de l'application : elle repart des données importées.
            with page.expect_navigation():
                page.click("dialog button:has-text('Recharger Prévo')")
            attendre_pret(page)
            self.assertEqual(page.evaluate("Donnees.lignes('equipements').length"),
                             len(lire_csv(csv_zip["equipements"])[1]))
            self.assertEqual(page.evaluate("Donnees.parametre('rapports_mensuels', '')").split(","),
                             [rendus["rapport-mensuel-2026-08.html"],
                              rendus["20261001-083000-rapport-mensuel-2026-09.html"]])

    def test_serveur_technicien_n_a_pas_l_import(self):
        self.autoriser_erreur(ERREUR_TABLE_REFUSEE)
        with ServeurPrevo(comptes=True) as serveur:
            serveur.poser_session(self.contexte, "technicien")
            page = self.page
            page.goto(serveur.url + "/#/accueil")
            attendre_pret(page)
            self.assertEqual(page.evaluate("App.profil.type"), "technicien")
            avant = instantane(serveur.dossier)
            page.evaluate("location.hash = '#/parametres'")
            page.wait_for_function("location.hash === '#/accueil'")
            attendre_pret(page)
            self.assertEqual(page.locator("#btn-import-zip, #fichier-import-zip").count(), 0)
            self.assertEqual(page.evaluate("ParametresZip.etat()"),
                             {"visible": False, "permis": False, "raison": RAISON_RESERVE})
            self.assertEqual(page.evaluate("Parametres.interne.blocImportZip()"), "")
            # Appel direct : refusé avant toute lecture, rien d'écrit.
            page.evaluate("() => { window.__resultat = ParametresZip.importer(new Blob(['x'])); }")
            self.assertEqual(self.texte_fenetre(page, "import-zip-refus"), RAISON_RESERVE)
            self.fermer_fenetre(page, "import-zip-refus")
            self.assertEqual(page.evaluate("window.__resultat.then((r) => r.etape)"), "refus")
            self.assertEqual(instantane(serveur.dossier), avant)

    def test_serveur_zip_au_format_2_mis_au_format_3_donnees_intactes(self):
        f2 = {chemin: o for chemin, o in fichiers_du_jeu("f2-v1.1.0").items() if chemin.endswith(".csv")}
        self.assertEqual(len(f2), 22)
        chemin_zip = ecrire_zip(self.temporaire / "prevo-export-2025-10-01.zip", f2, avec_manifeste=False)
        with ServeurPrevo() as serveur:
            page = self.ouvrir_parametres(serveur)
            self.choisir_zip(page, chemin_zip)
            info = self.confirmation(page)
            self.assertEqual((info["format"], info["migre"], info["documents"]), ("2", "1", 0))
            self.assertEqual(info["formatTexte"], "Format des données : 2 ; elles seront mises au format 3 (format de "
                                                  "cette version) à l'import.")
            self.assertIn("sans manifeste", info["origine"])
            self.assertEqual(sorted(info["videes"]), ["wiki_journal", "wiki_pages"])
            self.assertIn("2 tables absentes du ZIP seront vidées", info["tablesVidees"])
            self.assertIn("wiki_pages.csv", info["tablesVidees"])
            self.assertEqual(info["importe"]["wiki_pages"], 0)
            self.assertGreater(info["actuel"]["wiki_pages"], 0)
            self.assertIn("Aucun document joint", info["documentsTexte"])
            page.click(BOUTON_REMPLACER)
            self.texte_fenetre(page, "import-zip-termine")
            ecrits = {table: (serveur.dossier / (table + ".csv")).read_bytes() for table in TABLES}

        self.assertIn(b"version_schema;'3", ecrits["parametres"])
        for table in TABLES:
            entete, lignes = lire_csv(ecrits[table])
            if table + ".csv" not in f2:
                self.assertEqual(lignes, [], table)                        # tables du format 3 : vides
                continue
            entete_f2, lignes_f2 = lire_csv(f2[table + ".csv"])
            self.assertEqual(entete[:len(entete_f2)], entete_f2, table)
            nouvelles = entete[len(entete_f2):]
            self.assertEqual(nouvelles, ["astuce"] if table == "ordres_travail" else [], table)
            if table == "journal":
                self.assertRegex(lignes.pop()["action"], r"^import ZIP : prevo-export-2025-10-01\.zip, 24 tables, "
                                                         r"0 document ; sauvegarde .*_avant-import-zip faite juste avant$")
            self.assertEqual(len(lignes), len(lignes_f2), table)
            for rang, (ligne, ligne_f2) in enumerate(zip(lignes, lignes_f2)):
                for colonne in entete_f2:
                    if table == "parametres" and ligne_f2["cle"] == "version_schema":
                        continue
                    self.assertEqual(sans_apostrophe(ligne[colonne]), sans_apostrophe(ligne_f2[colonne]),
                                     "%s ligne %d colonne %s" % (table, rang + 2, colonne))
                for colonne in nouvelles:
                    self.assertEqual(ligne[colonne], "", (table, rang, colonne))

    def test_serveur_colonnes_inconnues_du_zip_gardees(self):
        # Jeu colonnes-en-trop : colonne_maison au milieu d'equipements.csv, note_maison à la fin. Remplacer la table
        # ne doit rien perdre : les colonnes du schéma, puis les colonnes inconnues, chaque valeur gardée.
        zip_csv = {c: o for c, o in fichiers_du_jeu("colonnes-en-trop").items() if c.endswith(".csv")}
        schema, _ = lire_csv(fichiers_du_jeu("f3-v1.2.0")["equipements.csv"])
        chemin_zip = ecrire_zip(self.temporaire / "colonnes-en-trop.zip", zip_csv)
        with ServeurPrevo() as serveur:
            page = self.ouvrir_parametres(serveur)
            self.choisir_zip(page, chemin_zip)
            self.confirmation(page)
            page.click(BOUTON_REMPLACER)
            self.texte_fenetre(page, "import-zip-termine")
            entete, lignes = lire_csv((serveur.dossier / "equipements.csv").read_bytes())
        entete_zip, lignes_zip = lire_csv(zip_csv["equipements.csv"])
        self.assertEqual(entete, schema + ["colonne_maison", "note_maison"])
        self.assertEqual(len(lignes), len(lignes_zip))
        self.assertTrue(any(ligne["colonne_maison"] for ligne in lignes_zip))
        for ligne, ligne_zip in zip(lignes, lignes_zip):
            self.assertEqual({c: ligne[c] for c in entete_zip}, ligne_zip)

    def test_serveur_annulation_zip_hostile_ou_plus_recent_aucun_octet_change(self):
        f3 = {chemin: o for chemin, o in fichiers_du_jeu("f3-v1.2.0").items() if chemin.endswith(".csv")}
        valide = ecrire_zip(self.temporaire / "valide.zip", f3)
        hostile = ecrire_zip(self.temporaire / "hostile.zip", dict(f3, **{"../x.csv": b"id;nom\r\n"}),
                             avec_manifeste=False)
        recent = ecrire_zip(self.temporaire / "recent.zip", f3, avec_manifeste=False)
        with zipfile.ZipFile(recent, "a") as archive:          # même ZIP, manifeste au format 4
            archive.writestr("manifeste.json", manifeste(f3, format=4))
        with ServeurPrevo() as serveur:
            page = self.ouvrir_parametres(serveur)
            avant = instantane(serveur.dossier)
            # Annulation à la confirmation.
            self.choisir_zip(page, valide)
            self.confirmation(page)
            page.click(BOUTON_ANNULER)
            page.wait_for_selector("#confirmation-import-zip", state="detached")
            page.wait_for_function("!document.getElementById('btn-import-zip').disabled")
            self.assertEqual(instantane(serveur.dossier), avant)
            # ZIP hostile, puis ZIP plus récent : refus, rien d'écrit.
            for chemin, attendus in ((hostile, ["chemin dangereux", "« ../x.csv »", "Rien n'a été écrit."]),
                                     (recent, ["version plus récente de Prévo", "format 4", "Rien n'a été écrit."])):
                with self.subTest(zip=chemin.name):
                    self.choisir_zip(page, chemin)
                    texte = self.texte_fenetre(page, "import-zip-refus")
                    for attendu in attendus:
                        self.assertIn(attendu, texte)
                    self.assertEqual(page.locator("#confirmation-import-zip").count(), 0)
                    self.fermer_fenetre(page, "import-zip-refus")
                    page.wait_for_function("!document.getElementById('btn-import-zip').disabled")
            self.assertEqual(instantane(serveur.dossier), avant)

    def test_serveur_echec_pendant_l_ecriture_tables_remises_depuis_la_sauvegarde(self):
        f3 = {chemin: o for chemin, o in fichiers_du_jeu("f3-v1.2.0").items() if chemin.endswith(".csv")}
        chemin_zip = ecrire_zip(self.temporaire / "f3.zip", dict(f3, **{"documents/notice.pdf": octets_pdf("n")}))
        with ServeurPrevo() as serveur:
            page = self.ouvrir_parametres(serveur)
            avant = instantane(serveur.dossier)
            page.evaluate(PANNE_ENREGISTRER_JS, "ordres_travail")
            self.choisir_zip(page, chemin_zip)
            self.confirmation(page)
            page.click(BOUTON_REMPLACER)
            message = self.texte_fenetre(page, "import-zip-echec")
            apres = instantane(serveur.dossier)
            # Tables d'avant l'import ordres_travail (equipements, demandes…) écrites puis remises : à l'octet.
            for table in TABLES:
                self.assertEqual(apres[table + ".csv"], avant[table + ".csv"], table)
            noms = sauvegardes_de(apres, MOTIF_AVANT_IMPORT_ZIP)
            self.assertEqual(len(noms), 1, noms)
            copies = sauvegardes_de(apres, MOTIF_AVANT_RESTAURATION)
            self.assertEqual(len(copies), 1, copies)
            self.assertIn("L'import ZIP a échoué (panne simulée pendant l'écriture de ordres_travail)", message)
            self.assertIn("remises dans leur état d'avant, depuis la sauvegarde « %s »" % noms[0], message)
            self.assertIn(copies[0], message)
            # La copie de sécurité garde l'état interrompu : equipements (écrit avant ordres_travail) est celui du ZIP,
            # ordres_travail celui d'avant (jamais écrit).
            interrompu = contenu_sauvegarde(apres, copies[0])
            self.assertEqual(interrompu["equipements.csv"], f3["equipements.csv"])
            self.assertNotEqual(interrompu["equipements.csv"], avant["equipements.csv"])
            self.assertEqual(interrompu["ordres_travail.csv"], avant["ordres_travail.csv"])
            # Le document déjà copié reste ; acces/ et le reste du dossier documents sont inchangés.
            self.assertEqual(len([c for c in apres if c.startswith("documents/")]),
                             len([c for c in avant if c.startswith("documents/")]) + 1)
            self.fermer_fenetre(page, "import-zip-echec")
            self.assertEqual(page.evaluate("Donnees.lignes('equipements').length"),
                             len(lire_csv(avant["equipements.csv"])[1]))


# ---------------------------------------------------------------------------
# Mode dossier (OPFS)
# ---------------------------------------------------------------------------

class TestDossier(CasImport):

    def setUp(self):
        super().setUp()
        self.autoriser_erreur(ERREUR_PING_ABSENT)

    def ouvrir_dossier(self, statique, fichiers):
        installer_dossier_simule(self.contexte, NOM_DOSSIER)
        preregler_profil(self.contexte, "responsable")
        page = self.page
        page.goto(statique.url + "/index.html")
        page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        page.evaluate(ECRIRE_OPFS_JS, [NOM_DOSSIER, {chemin: en_base64(o) for chemin, o in fichiers.items()}])
        page.click("#btn-dossier")
        attendre_pret(page)
        self.assertEqual(page.evaluate("App.mode"), "dossier")
        page.evaluate("location.hash = '#/parametres'")
        page.wait_for_selector("#btn-import-zip")
        return page

    def opfs(self, page):
        return {chemin: base64.b64decode(valeur) for chemin, valeur in page.evaluate(INSTANTANE_OPFS_JS, NOM_DOSSIER).items()}

    def test_dossier_import_documents_repris_ou_renommes_sauvegarde_et_acces_intact(self):
        csv_a, documents_a = base_a()
        chemin_zip = ecrire_zip(self.temporaire / "prevo-export-2026-11-04.zip",
                                dict(csv_a, **{"documents/" + nom: o for nom, o in documents_a.items()}))
        csv_zip = {nom[:-4]: o for nom, o in csv_a.items()}
        base = fichiers_du_jeu("f3-v2.0.0")
        self.assertIn("acces/comptes.json", base)
        base["documents/notice-perceuse.pdf"] = documents_a["notice-perceuse.pdf"]      # identique : repris
        base["documents/photo-tapis.png"] = octets_png("autre photo déjà là")          # autre contenu : « -2 »
        with ServeurStatique(RACINE) as statique:
            page = self.ouvrir_dossier(statique, base)
            avant = self.opfs(page)
            self.choisir_zip(page, chemin_zip)
            info = self.confirmation(page)
            self.assertEqual((info["format"], info["migre"], info["documents"]), ("3", "0", 6))
            self.assertIn("Exporté le 04/11/2026 à 09:30 par Prévo 2.0.1 (mode dossier).", info["origine"])
            page.click(BOUTON_REMPLACER)
            termine = self.texte_fenetre(page, "import-zip-termine")
            self.assertIn("1 déjà présent(s), repris", termine)
            apres = self.opfs(page)
            documents = {c[len("documents/"):]: o for c, o in apres.items() if c.startswith("documents/")}
            rendus = self.verifier_donnees(csv_zip, {t: apres[t + ".csv"] for t in TABLES}, documents_a, documents,
                                           chemin_zip.name)
            self.assertEqual(rendus["notice-perceuse.pdf"], "notice-perceuse.pdf")
            self.assertEqual(rendus["20261019-101500-photo-tapis.png"], "photo-tapis-2.png")
            self.assertEqual(rendus["20261020-111500-photo-tapis.png"], "photo-tapis-3.png")
            self.assertEqual(rendus["20261001-083000-rapport-mensuel-2026-09.html"], "rapport-mensuel-2026-09.html")
            self.assertEqual(documents["photo-tapis.png"], base["documents/photo-tapis.png"])   # jamais remplacé
            # Sauvegarde « avant-import-zip » : CSV d'avant et documents/ à l'octet ; acces/ jamais touché.
            noms = sauvegardes_de(apres, MOTIF_AVANT_IMPORT_ZIP)
            self.assertEqual(len(noms), 1, noms)
            self.assertIn(noms[0], termine)
            sauvegarde = contenu_sauvegarde(apres, noms[0])
            for table in TABLES:
                self.assertEqual(sauvegarde[table + ".csv"], avant[table + ".csv"], table)
            self.assertEqual(sauvegarde["documents/photo-tapis.png"], base["documents/photo-tapis.png"])
            self.assertEqual(sauvegarde["documents/notice-perceuse.pdf"], base["documents/notice-perceuse.pdf"])
            self.assertEqual(json.loads(sauvegarde["manifeste.json"])["motif"], "avant-import-zip")
            self.assertEqual(apres["acces/comptes.json"], base["acces/comptes.json"])
            self.assertEqual(sorted(c for c in apres if c.startswith("acces/")), ["acces/comptes.json"])
            # Rechargement : écran de démarrage, « Reprendre », données importées.
            with page.expect_navigation():
                page.click("dialog button:has-text('Recharger Prévo')")
            page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
            page.click("#btn-reprendre")
            attendre_pret(page)
            self.assertEqual(page.evaluate("Donnees.lignes('equipements').length"),
                             len(lire_csv(csv_zip["equipements"])[1]))

    def test_dossier_lecture_seule_import_refuse_rien_ecrit(self):
        base = fichiers_du_jeu("plus-recent")
        f3 = {chemin: o for chemin, o in fichiers_du_jeu("f3-v1.2.0").items() if chemin.endswith(".csv")}
        chemin_zip = ecrire_zip(self.temporaire / "f3.zip", f3)
        with ServeurStatique(RACINE) as statique:
            page = self.ouvrir_dossier(statique, base)
            self.assertTrue(page.evaluate("Donnees.lectureSeule()"))
            avant = self.opfs(page)
            etat = page.evaluate("ParametresZip.etat()")
            self.assertEqual((etat["visible"], etat["permis"]), (True, False))
            # Le bouton dit le refus avant le choix du fichier ; un fichier donné quand même est refusé aussi.
            page.click("#btn-import-zip")
            texte = self.texte_fenetre(page, "import-zip-refus")
            self.assertIn("Import ZIP refusé.", texte)
            self.assertIn("version plus récente de Prévo (format 4", texte)
            self.assertIn("lecture seule", texte)
            self.fermer_fenetre(page, "import-zip-refus")
            page.wait_for_function("!document.getElementById('btn-import-zip').disabled")
            page.set_input_files("#fichier-import-zip", str(chemin_zip))
            self.assertIn("lecture seule", self.texte_fenetre(page, "import-zip-refus"))
            self.fermer_fenetre(page, "import-zip-refus")
            self.assertEqual(page.locator("#confirmation-import-zip").count(), 0)
            self.assertEqual(self.opfs(page), avant)


# ---------------------------------------------------------------------------
# Démo
# ---------------------------------------------------------------------------

class TestDemo(CasImport):

    def test_demo_bouton_inactif_indisponible(self):
        preregler_profil(self.contexte, "responsable")
        page = self.page
        page.goto(url_fichier("index.html"))
        page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        page.click("#btn-demo")
        attendre_pret(page)
        page.evaluate("location.hash = '#/parametres'")
        page.wait_for_selector("#btn-import-zip")
        self.assertTrue(page.is_disabled("#btn-import-zip"))
        self.assertEqual(page.inner_text("#note-import-zip"), "Import ZIP indisponible en démo : rien n'y est enregistré.")
        self.assertEqual(page.evaluate("ParametresZip.etat().permis"), False)


if __name__ == "__main__":
    unittest.main()
