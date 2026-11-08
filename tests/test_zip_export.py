"""Export ZIP complet (chantier « socle de données », T189 ; décisions D167 et D171 ; CS144) : js/modules/zip-donnees.js
(ZipDonnees), App.exporterZip qui lui délègue, et le repli SHA-256 de js/formats.js (Formats.manifeste sans
crypto.subtle).

Chaque export est déclenché par un vrai bouton (téléchargement capturé par page.expect_download), puis le ZIP est
ouvert en Python (zipfile) et contrôlé entièrement (verifier_export) :
    - les CSV (NB_TABLES) à la racine (BOM UTF-8), les documents attendus sous documents/ octet pour octet, manifeste.json, et
      rien d'autre (ni sauvegardes/, ni document non cité, ni aucun chemin acces/, absolu ou avec « .. ») ;
    - manifeste.json exact : clés dans l'ordre, application « Prévo », version_appli = VERSION de js/app.js, format de
      la base, date « AAAA-MM-JJTHH:MM:SS » du jour du nom du fichier, motif « export », mode, fichiers = toutes les
      autres entrées triées par nom avec leur taille et hashlib.sha256 de leurs octets, `manquants` s'il y en a ;
    - le message montré à l'utilisateur (documents introuvables nommés).

    serveur      ServeurPrevo (comptes) sur une COPIE de la démo (dossier temporaire) où le test ajoute : un document
                 cité par equipements.document, une photo (nom horodaté du serveur) par demandes.photo, un rapport de
                 contrôle par controles_reglementaires.rapport, deux rapports figés cités par rapports_mensuels (dont
                 un au nom horodaté), un document non cité, un document cité absent et un nom piégé
                 « ../acces/comptes.json » ; le responsable exporte par Paramètres ; les CSV du ZIP sont ceux du
                 disque à l'octet. Technicien et demandeur connectés : aucun bouton d'export (accueil, Paramètres,
                 feuille « Plus »), App.exporterZip refusé avec la phrase d'explication, aucun téléchargement ;
    dossier      jeu f3-v2.0.0 (avec acces/comptes.json) et un document non cité copiés dans l'OPFS ; documents et
                 rapports écrits par Prévo (App.adaptateur.ecrireDocument, Donnees.modifier) ; CSV du ZIP = dossier ;
    démo         mêmes ajouts en mémoire, bouton du bandeau de la démo ; CSV d'un format plus récent déposés :
                 lecture seule, l'export reste permis (format du jeu plus-recent, colonne inconnue gardée) ;
    repli        crypto.subtle retiré de la page : Formats.manifeste rend les empreintes de hashlib.sha256 (vide,
                 « abc », 1 Mio, octets 0 à 255, longueurs aux bords d'un bloc, sous-tableau) ; export de la démo
                 sans crypto.subtle : manifeste exact.

Règle numéro un : jamais de données réelles (copies dans des dossiers temporaires, OPFS du navigateur de test).

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_zip_export.py" -v
"""
import base64
import hashlib
import json
import re
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from commun import (RACINE, CasNavigateur, ServeurPrevo, ServeurStatique, attendre_pret, charger_scripts,
                    installer_dossier_simule, preregler_profil, url_fichier)
from commun import FORMAT_COURANT, NB_TABLES, format_du_jeu
from jeux_formats import copier_jeu

DOSSIER_DEMO = RACINE / "donnees" / "demo"
VERSION_APPLI = re.search(r"const VERSION = '([^']+)';", (RACINE / "js" / "app.js").read_text(encoding="utf-8")).group(1)
BOM = b"\xef\xbb\xbf"
CLES_MANIFESTE = ["application", "version_appli", "format", "date", "motif", "mode", "fichiers"]
MOTIF_NOM_ZIP = re.compile(r"^prevo-export-(\d{4}-\d{2}-\d{2})\.zip$")
MOTIF_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
NOM_PIEGE = "../acces/comptes.json"
RAISON_RESERVE = ("L'export ZIP est réservé au responsable : avec les comptes, les autres rôles ne voient qu'une partie "
                  "des données, et l'export serait incomplet.")
NOM_DOSSIER = "donnees-zip-export"

# Chromium note en console.error toute réponse HTTP >= 400 : seules celles-ci sont attendues.
ERREUR_PING_ABSENT = re.compile(r"status of 404.*/api/ping")              # serveur statique : pas de /api/ping
ERREUR_DOCUMENT_ABSENT = re.compile(r"status of 404.*/api/documents/vgp-chariot-absent\.pdf")
ERREUR_TABLE_REFUSEE = re.compile(r"status of 403 .*/api/csv/")          # demandeur connecté : tables refusées

# Pages sans crypto.subtle, comme en http par le réseau (contexte non sécurisé, ARCHITECTURE.md §2).
SANS_SUBTLE_JS = """(() => {
  try { Object.defineProperty(Crypto.prototype, 'subtle', { get() { return undefined; }, configurable: true }); }
  catch (erreur) { /* rien */ }
  try { Object.defineProperty(window.crypto, 'subtle', { value: undefined, configurable: true }); }
  catch (erreur) { /* rien */ }
})();"""

# Tous les messages montrés (UI.toast), dans l'ordre : un message peut en remplacer un autre très vite.
NOTER_TOASTS_JS = """(() => {
  window.__toasts = [];
  let dernier = '';
  new MutationObserver(() => {
    const zone = document.getElementById('toast');
    const texte = zone ? zone.textContent.trim() : '';
    if (texte && texte !== dernier) window.__toasts.push(texte);
    dernier = texte;
  }).observe(document, { subtree: true, childList: true, characterData: true, attributes: true });
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

LIRE_OPFS_CSV_JS = """async (nom) => {
  const resultat = {};
  const racine = await (await navigator.storage.getDirectory()).getDirectoryHandle(nom);
  for await (const entree of racine.values()) {
    if (entree.kind !== 'file' || !entree.name.endsWith('.csv')) continue;
    const octets = new Uint8Array(await (await entree.getFile()).arrayBuffer());
    let binaire = '';
    for (let i = 0; i < octets.length; i += 0x8000) binaire += String.fromCharCode.apply(null, octets.subarray(i, i + 0x8000));
    resultat[entree.name] = btoa(binaire);
  }
  return resultat;
}"""

# Écrit les documents par Prévo (noms rendus par l'adaptateur), puis les cite par Donnees.modifier :
# citations = [[table, champ, rang de la ligne, nom demandé ou nom brut]], rapports = noms (rapports_mensuels).
PREPARER_PAR_PREVO_JS = """async ({ documents, citations, rapports }) => {
  const octets = (enBase64) => Uint8Array.from(atob(enBase64), (c) => c.charCodeAt(0));
  const noms = {};
  for (const [nom, enBase64] of Object.entries(documents)) {
    noms[nom] = await App.adaptateur.ecrireDocument(nom, new Blob([octets(enBase64)]));
  }
  const nomRendu = (nom) => (Object.prototype.hasOwnProperty.call(noms, nom) ? noms[nom] : nom);
  for (const [table, champ, rang, nom] of citations) {
    await Donnees.modifier(table, (lignes) => {
      if (!lignes[rang]) {                       // table vide dans la démo (garanties, contrats) : une ligne complète
        const nouvelle = {};
        Schema.table(table).champs.forEach((c) => { nouvelle[c.nom] = ''; });
        nouvelle.id = Schema.table(table).identifiant.prefixe + '0001';
        lignes.push(nouvelle);
      }
      lignes[rang][champ] = nomRendu(nom);
    }, { action: 'test : document cité' });
  }
  await Donnees.modifier('parametres', (lignes) => {
    let ligne = lignes.find((l) => l.cle === 'rapports_mensuels');
    if (!ligne) { ligne = { cle: 'rapports_mensuels', valeur: '' }; lignes.push(ligne); }
    ligne.valeur = rapports.map(nomRendu).join(',');
  }, { action: 'test : rapports figés' });
  return noms;
}"""


def octets_pdf(graine):
    return b"%PDF-1.4\n% document de test : " + graine.encode("utf-8") + b"\n" + bytes(range(256))


def octets_png(graine):
    return b"\x89PNG\r\n\x1a\n" + graine.encode("utf-8") + bytes(range(255, -1, -1))


def page_rapport(mois):
    return ('<!doctype html><html lang="fr"><meta charset="utf-8"><title>Rapport %s</title>'
            '<p>Rapport figé de test — %s</p></html>' % (mois, mois)).encode("utf-8")


def noms_csv_attendus():
    """Les fichiers CSV de Prévo (NB_TABLES) (ceux du jeu de démo)."""
    return sorted(chemin.name for chemin in DOSSIER_DEMO.glob("*.csv"))


def remplacer_une_fois(chemin, avant, apres):
    """Remplace dans un CSV (octets UTF-8) un passage qui doit y être exactement une fois."""
    texte = chemin.read_bytes().decode("utf-8")
    if texte.count(avant) != 1:
        raise AssertionError("%s : %r trouvé %d fois" % (chemin.name, avant, texte.count(avant)))
    chemin.write_bytes(texte.replace(avant, apres).encode("utf-8"))


def lire_csv_zip(octets):
    """Lignes ({colonne: valeur}) d'un CSV de Prévo (BOM, « ; », CRLF), sans guillemets dans ces tests."""
    lignes = octets.decode("utf-8-sig").split("\r\n")
    entete = lignes[0].split(";")
    return [dict(zip(entete, ligne.split(";"))) for ligne in lignes[1:] if ligne]


def en_base64(octets):
    return base64.b64encode(octets).decode("ascii")


# Ajouts faits par Prévo (modes dossier et démo) : documents écrits, puis cités. Le premier rapport figé, le premier
# document de chaque colonne et le second de demandes (nom piégé) / controles_reglementaires (absent).
DOCUMENTS_PAR_PREVO = {
    "notice-machine.pdf": octets_pdf("notice"),
    "photo-fuite.png": octets_png("fuite"),
    "vgp-pont-2026.pdf": octets_pdf("vgp"),
    "rapport-mensuel-2026-08.html": page_rapport("2026-08"),
    "rapport-mensuel-2026-09.html": page_rapport("2026-09"),
    "habilitation-caces.pdf": octets_pdf("caces"),
    "garantie-presse.pdf": octets_pdf("garantie"),
    "contrat-maintenance.pdf": octets_pdf("contrat"),
}
CITATIONS_PAR_PREVO = [
    ["equipements", "document", 0, "notice-machine.pdf"],
    ["demandes", "photo", 0, "photo-fuite.png"],
    ["demandes", "photo", 1, NOM_PIEGE],
    ["controles_reglementaires", "rapport", 0, "vgp-pont-2026.pdf"],
    ["controles_reglementaires", "rapport", 1, "vgp-chariot-absent.pdf"],
    ["habilitations", "justificatif", 0, "habilitation-caces.pdf"],
    ["garanties", "document", 0, "garantie-presse.pdf"],
    ["contrats_prestataires", "document", 0, "contrat-maintenance.pdf"],
]
RAPPORTS_PAR_PREVO = ["rapport-mensuel-2026-08.html", "rapport-mensuel-2026-09.html"]
MANQUANTS_PAR_PREVO = [NOM_PIEGE, "vgp-chariot-absent.pdf"]


class CasExport(CasNavigateur):

    def setUp(self):
        super().setUp()
        self.contexte.add_init_script(NOTER_TOASTS_JS)

    # -- export -----------------------------------------------------------------------------

    def exporter(self, page, selecteur):
        """Clique sur le bouton, capture le téléchargement → (nom proposé, noms dans l'ordre, {nom: octets})."""
        with page.expect_download() as attente:
            page.click(selecteur)
        telechargement = attente.value
        with zipfile.ZipFile(telechargement.path()) as archive:
            noms = archive.namelist()
            entrees = {nom: archive.read(nom) for nom in noms}
        return telechargement.suggested_filename, noms, entrees

    def attendre_toast(self, page, morceau):
        page.wait_for_function("(morceau) => (window.__toasts || []).some((t) => t.includes(morceau))", arg=morceau)
        return next(t for t in page.evaluate("window.__toasts") if morceau in t)

    def verifier_export(self, nom_zip, noms, entrees, documents, manquants, mode, format_base):
        """Contrôle complet d'un ZIP exporté ; documents = {nom: octets} attendus sous documents/. Rend le manifeste."""
        jour = MOTIF_NOM_ZIP.match(nom_zip)
        self.assertIsNotNone(jour, nom_zip)
        self.assertEqual(len(noms), len(set(noms)), "entrée en double")
        for nom in noms:
            self.assertFalse(nom.startswith("acces/") or "/acces/" in nom or nom.startswith("acces"), nom)
            self.assertNotIn("..", nom)
            self.assertNotIn("\\", nom)
            self.assertFalse(nom.startswith("/") or re.match(r"^[A-Za-z]:", nom), nom)
        csv_du_zip = sorted(nom for nom in noms if "/" not in nom and nom.endswith(".csv"))
        self.assertEqual(csv_du_zip, noms_csv_attendus())
        for nom in csv_du_zip:
            self.assertTrue(entrees[nom].startswith(BOM), nom)
        documents_du_zip = {nom[len("documents/"):]: octets for nom, octets in entrees.items()
                            if nom.startswith("documents/")}
        self.assertEqual(sorted(documents_du_zip), sorted(documents))
        for nom, octets in documents.items():
            self.assertEqual(documents_du_zip[nom], octets, nom)
        self.assertEqual(set(noms), set(csv_du_zip) | {"documents/" + nom for nom in documents} | {"manifeste.json"})
        # T388 : un document cité par une colonne de type document (justificatif, garantie, contrat) est cité dans le CSV
        for table, colonne in (("habilitations", "justificatif"), ("garanties", "document"),
                               ("contrats_prestataires", "document")):
            if not documents:
                break
            cites = {ligne[colonne] for ligne in lire_csv_zip(entrees[table + ".csv"]) if ligne[colonne]}
            self.assertTrue(cites, table)
            self.assertLessEqual(cites, set(documents), table)

        manifeste = json.loads(entrees["manifeste.json"].decode("utf-8"))
        self.assertEqual(list(manifeste), CLES_MANIFESTE + (["manquants"] if manquants else []))
        self.assertEqual(manifeste["application"], "Prévo")
        self.assertEqual(manifeste["version_appli"], VERSION_APPLI)
        self.assertEqual(manifeste["format"], format_base)
        self.assertEqual(manifeste["motif"], "export")
        self.assertEqual(manifeste["mode"], mode)
        self.assertRegex(manifeste["date"], MOTIF_DATE)
        self.assertEqual(manifeste["date"][:10], jour.group(1))
        attendus = [{"nom": nom, "octets": len(entrees[nom]), "sha256": hashlib.sha256(entrees[nom]).hexdigest()}
                    for nom in sorted(nom for nom in noms if nom != "manifeste.json")]
        self.assertEqual(manifeste["fichiers"], attendus)
        if manquants:
            self.assertEqual(manifeste["manquants"], manquants)
        return manifeste

    # -- préparation par Prévo (dossier, démo) ------------------------------------------------

    def preparer_par_prevo(self, page):
        """Écrit et cite les documents par Prévo ; rend {nom demandé: nom rendu par l'adaptateur}."""
        return page.evaluate(PREPARER_PAR_PREVO_JS, {
            "documents": {nom: en_base64(octets) for nom, octets in DOCUMENTS_PAR_PREVO.items()},
            "citations": CITATIONS_PAR_PREVO, "rapports": RAPPORTS_PAR_PREVO})

    def verifier_message_manquants(self, page, nombre_documents):
        texte = self.attendre_toast(page, "Export téléchargé")
        self.assertIn("Export téléchargé : %d fichiers CSV et %d document(s)" % (NB_TABLES, nombre_documents), texte)
        self.assertIn("2 document(s) introuvable(s) : %s, vgp-chariot-absent.pdf" % NOM_PIEGE, texte)
        self.assertIn("manifeste.json", texte)


# ---------------------------------------------------------------------------
# Mode serveur (comptes) : responsable, technicien, demandeur
# ---------------------------------------------------------------------------

class TestServeur(CasExport):

    def preparer_copie_demo(self, dossier):
        """Copie de la démo + documents dans `dossier` ; rend les documents attendus dans le ZIP ({nom: octets})."""
        shutil.copytree(DOSSIER_DEMO, dossier)
        documents = dossier / "documents"
        documents.mkdir()
        attendus = {
            "notice-perceuse.pdf": octets_pdf("perceuse"),
            "20261019-101500-photo-tapis.png": octets_png("tapis"),
            "vgp-pont-2026.pdf": octets_pdf("vgp"),
            "rapport-mensuel-2026-08.html": page_rapport("2026-08"),
            "20261001-083000-rapport-mensuel-2026-09.html": page_rapport("2026-09"),
            "habilitation-caces.pdf": octets_pdf("caces"),
            "garantie-presse.pdf": octets_pdf("garantie"),
            "contrat-maintenance.pdf": octets_pdf("contrat"),
        }
        for nom, octets in attendus.items():
            (documents / nom).write_bytes(octets)
        (documents / "orphelin-non-cite.pdf").write_bytes(octets_pdf("orphelin"))     # jamais exporté
        remplacer_une_fois(dossier / "equipements.csv", ";rebut;8;;;;0;2400", ";rebut;8;;;notice-perceuse.pdf;0;2400")
        remplacer_une_fois(dossier / "demandes.csv", "clignote.;arrêt;;;Acceptée",
                           "clignote.;arrêt;;20261019-101500-photo-tapis.png;Acceptée")
        remplacer_une_fois(dossier / "demandes.csv",
                           "DI-2025-0002;2025-09-30 13:30;Camille Girard;EQ-0001;Défaut température haute, il est tombé "
                           "en sécurité.;arrêt;Le problème apparaît surtout quand la machine est chaude.;;Acceptée",
                           "DI-2025-0002;2025-09-30 13:30;Camille Girard;EQ-0001;Défaut température haute, il est tombé "
                           "en sécurité.;arrêt;Le problème apparaît surtout quand la machine est chaude.;%s;Acceptée"
                           % NOM_PIEGE)
        remplacer_une_fois(dossier / "controles_reglementaires.csv", "2026-02-10;2027-02-10;;;1",
                           "2026-02-10;2027-02-10;vgp-pont-2026.pdf;;1")
        remplacer_une_fois(dossier / "controles_reglementaires.csv", "2026-03-18;2026-09-18;;;1",
                           "2026-03-18;2026-09-18;vgp-chariot-absent.pdf;;1")
        remplacer_une_fois(dossier / "habilitations.csv", "HAB-0001;TEC-0001;BR;2025-03-10;2028-03-10;;;;",
                           "HAB-0001;TEC-0001;BR;2025-03-10;2028-03-10;;habilitation-caces.pdf;;")
        for table, ligne in (("garanties", "GAR-0001;EQ-0001;;2026-01-01;2027-01-01;;garantie-presse.pdf;1"),
                             ("contrats_prestataires",
                              "CTP-0001;;Maintenance;;;2026-01-01;2027-01-01;;;;;contrat-maintenance.pdf;1")):
            csv = dossier / (table + ".csv")
            csv.write_bytes(csv.read_bytes() + (ligne + "\r\n").encode("utf-8"))
        parametres = dossier / "parametres.csv"
        parametres.write_bytes(parametres.read_bytes() + (
            "rapports_mensuels;rapport-mensuel-2026-08.html,20261001-083000-rapport-mensuel-2026-09.html\r\n"
        ).encode("utf-8"))
        return attendus

    def test_serveur_responsable_export_complet_manifeste_exact_sans_acces(self):
        self.autoriser_erreur(ERREUR_DOCUMENT_ABSENT)
        with tempfile.TemporaryDirectory(prefix="prevo-zip-export-") as temporaire:
            source = Path(temporaire) / "donnees"
            documents = self.preparer_copie_demo(source)
            with ServeurPrevo(source=source, comptes=True) as serveur:
                self.assertTrue((serveur.dossier / "acces" / "comptes.json").is_file())
                serveur.poser_session(self.contexte, "responsable")
                page = self.page
                page.goto(serveur.url + "/#/parametres")
                attendre_pret(page)
                self.assertTrue(page.evaluate("App.comptesExiges()"))
                self.assertEqual(page.evaluate("ZipDonnees.exportPermis()"), {"permis": True, "raison": ""})
                page.wait_for_selector("#btn-export-zip")
                nom_zip, noms, entrees = self.exporter(page, "#btn-export-zip")
                self.verifier_export(nom_zip, noms, entrees, documents, MANQUANTS_SERVEUR, "serveur", FORMAT_COURANT)
                self.verifier_message_manquants(page, len(documents))
                # Les CSV du ZIP sont ceux du disque, à l'octet (journal compris : relu avant l'export).
                for nom in noms_csv_attendus():
                    self.assertEqual(entrees[nom], (serveur.dossier / nom).read_bytes(), nom)

    def test_serveur_fichier_abime_marque_au_manifeste_de_l_export(self):
        """T210 : un CSV abîmé (jeu entete-tronque : ordres_travail.csv) porte « abime »: true dans le manifeste de
        l'export, comme dans les sauvegardes (T206) ; les autres fichiers n'ont pas la clé ; octets du disque."""
        with tempfile.TemporaryDirectory(prefix="prevo-zip-export-") as temporaire:
            source = copier_jeu("entete-tronque", Path(temporaire) / "donnees")
            with ServeurPrevo(source=source) as serveur:
                preregler_profil(self.contexte, "responsable", nom="Claire Export")
                page = self.page
                page.goto(serveur.url + "/#/parametres")
                attendre_pret(page)
                page.wait_for_selector("#btn-export-zip")
                _, _, entrees = self.exporter(page, "#btn-export-zip")
                manifeste = json.loads(entrees["manifeste.json"].decode("utf-8"))
                marques = sorted(f["nom"] for f in manifeste["fichiers"] if f.get("abime") is True)
                self.assertEqual(marques, ["ordres_travail.csv"])
                self.assertTrue(all("abime" not in f for f in manifeste["fichiers"] if f["nom"] != "ordres_travail.csv"))
                self.assertEqual(entrees["ordres_travail.csv"], (serveur.dossier / "ordres_travail.csv").read_bytes())

    def test_serveur_technicien_et_demandeur_n_ont_pas_l_export(self):
        self.autoriser_erreur(ERREUR_TABLE_REFUSEE)
        with ServeurPrevo(comptes=True) as serveur:
            for role in ("technicien", "demandeur"):
                with self.subTest(role=role):
                    contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
                    try:
                        contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
                        contexte.add_init_script(NOTER_TOASTS_JS)
                        serveur.poser_session(contexte, role)
                        page = contexte.new_page()
                        self.surveiller(page)
                        telechargements = []
                        page.on("download", lambda telechargement: telechargements.append(telechargement))
                        page.goto(serveur.url + "/#/accueil")
                        attendre_pret(page)
                        self.assertTrue(page.evaluate("App.comptesExiges()"))
                        self.assertEqual(page.evaluate("App.profil.type"), role)
                        self.verifier_sans_bouton_d_export(page)
                        # Paramètres (et sa carte « Exporter les données ») n'est pas ouvert à ce rôle.
                        page.evaluate("location.hash = '#/parametres'")
                        self.attendre_toast(page, "n'est pas disponible pour le profil")
                        page.wait_for_function("location.hash === '#/accueil'")
                        attendre_pret(page)
                        self.verifier_sans_bouton_d_export(page)
                        # Appel direct : refusé avec la phrase d'explication, rien n'est téléchargé.
                        self.assertEqual(page.evaluate("ZipDonnees.exportPermis()"),
                                         {"permis": False, "raison": RAISON_RESERVE})
                        self.assertEqual(page.evaluate(
                            "ZipDonnees.exporter().then(() => 'accepté', (e) => e.name + ' : ' + e.message)"),
                            "ErreurValidation : " + RAISON_RESERVE)
                        self.assertTrue(page.evaluate("App.exporterZip().then((r) => r === undefined)"))
                        self.assertEqual(self.attendre_toast(page, "réservé au responsable"), RAISON_RESERVE)
                        # Téléphone : la feuille « Plus » ne propose pas l'export non plus.
                        page.set_viewport_size({"width": 360, "height": 740})
                        page.click("#btn-plus")
                        page.wait_for_selector(".liste-plus")
                        self.assertEqual(page.locator('.liste-plus [data-action="zip"]').count(), 0)
                        self.assertNotIn("Exporter en ZIP", page.inner_text(".liste-plus"))
                        page.wait_for_timeout(300)
                        self.assertEqual(telechargements, [])
                    finally:
                        contexte.close()

    def verifier_sans_bouton_d_export(self, page):
        self.assertEqual(page.locator("#btn-export-accueil, #btn-export-zip").count(), 0)
        self.assertFalse(page.is_visible("#btn-export-demo"))
        self.assertTrue(page.evaluate("document.getElementById('bandeau-demo').hidden"))


# Ordre des manquants : colonnes dans l'ordre (equipements, demandes, controles_reglementaires), lignes dans l'ordre.
MANQUANTS_SERVEUR = [NOM_PIEGE, "vgp-chariot-absent.pdf"]


# ---------------------------------------------------------------------------
# Mode dossier (OPFS)
# ---------------------------------------------------------------------------

class TestDossier(CasExport):

    def setUp(self):
        super().setUp()
        self.autoriser_erreur(ERREUR_PING_ABSENT)

    def test_dossier_export_complet_sans_acces_ni_document_non_cite(self):
        with tempfile.TemporaryDirectory(prefix="prevo-zip-export-") as temporaire:
            dossier = copier_jeu("f3-v2.0.0", Path(temporaire) / "donnees")
            fichiers = {p.relative_to(dossier).as_posix(): p.read_bytes() for p in sorted(dossier.rglob("*"))
                        if p.is_file()}
        self.assertIn("acces/comptes.json", fichiers)
        fichiers["documents/orphelin-non-cite.pdf"] = octets_pdf("orphelin")
        with ServeurStatique(RACINE) as statique:
            installer_dossier_simule(self.contexte, NOM_DOSSIER)
            preregler_profil(self.contexte, "responsable")
            page = self.page
            page.goto(statique.url + "/index.html")
            page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
            page.evaluate(ECRIRE_OPFS_JS, [NOM_DOSSIER, {chemin: en_base64(o) for chemin, o in fichiers.items()}])
            page.click("#btn-dossier")
            attendre_pret(page)
            self.assertEqual(page.evaluate("App.mode"), "dossier")
            self.assertFalse(page.evaluate("App.comptesExiges()"))
            noms_rendus = self.preparer_par_prevo(page)
            self.assertEqual(noms_rendus, {nom: nom for nom in DOCUMENTS_PAR_PREVO})
            page.evaluate("location.hash = '#/parametres'")
            page.wait_for_selector("#btn-export-zip")
            nom_zip, noms, entrees = self.exporter(page, "#btn-export-zip")
            self.verifier_export(nom_zip, noms, entrees, DOCUMENTS_PAR_PREVO, MANQUANTS_PAR_PREVO, "dossier",
                                 FORMAT_COURANT)
            self.verifier_message_manquants(page, len(DOCUMENTS_PAR_PREVO))
            # Les CSV du ZIP sont ceux du dossier, à l'octet.
            sur_le_disque = {nom: base64.b64decode(valeur)
                             for nom, valeur in page.evaluate(LIRE_OPFS_CSV_JS, NOM_DOSSIER).items()}
            for nom in noms_csv_attendus():
                self.assertEqual(entrees[nom], sur_le_disque[nom], nom)


# ---------------------------------------------------------------------------
# Démo (file://), lecture seule, repli SHA-256
# ---------------------------------------------------------------------------

class TestDemo(CasExport):

    def ouvrir_demo(self, sans_subtle=False):
        if sans_subtle:
            self.contexte.add_init_script(SANS_SUBTLE_JS)
        preregler_profil(self.contexte, "responsable")
        page = self.page
        page.goto(url_fichier("index.html"))
        page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        page.click("#btn-demo")
        attendre_pret(page)
        self.assertEqual(page.evaluate("App.mode"), "demo")
        self.assertEqual(page.evaluate("typeof crypto.subtle"), "undefined" if sans_subtle else "object")
        return page

    def exporter_demo_avec_documents(self, page):
        self.assertEqual(self.preparer_par_prevo(page), {nom: nom for nom in DOCUMENTS_PAR_PREVO})
        # Bouton du bandeau de la démo (hors de l'accueil du responsable, qui a le sien).
        page.evaluate("location.hash = '#/apropos'")
        page.wait_for_selector("#bandeau-demo", state="visible")
        nom_zip, noms, entrees = self.exporter(page, "#btn-export-demo")
        manifeste = self.verifier_export(nom_zip, noms, entrees, DOCUMENTS_PAR_PREVO, MANQUANTS_PAR_PREVO, "demo",
                                         FORMAT_COURANT)
        self.verifier_message_manquants(page, len(DOCUMENTS_PAR_PREVO))
        return manifeste

    def test_demo_export_complet_par_le_bandeau(self):
        page = self.ouvrir_demo()
        self.exporter_demo_avec_documents(page)

    def test_demo_sans_crypto_subtle_manifeste_exact(self):
        page = self.ouvrir_demo(sans_subtle=True)
        self.exporter_demo_avec_documents(page)

    def test_lecture_seule_export_permis_format_de_la_base(self):
        with tempfile.TemporaryDirectory(prefix="prevo-zip-export-") as temporaire:
            dossier = copier_jeu("plus-recent", Path(temporaire) / "donnees")
            fichiers = [str(p) for p in sorted(dossier.glob("*.csv"))]
            preregler_profil(self.contexte, "responsable")
            page = self.page
            page.goto(url_fichier("index.html"))
            page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
            page.set_input_files("#fichiers-csv", fichiers)
            attendre_pret(page)
        self.assertTrue(page.evaluate("Donnees.lectureSeule()"))
        self.assertEqual(page.evaluate("ZipDonnees.exportPermis()"), {"permis": True, "raison": ""})
        page.wait_for_selector("#btn-export-accueil")
        nom_zip, noms, entrees = self.exporter(page, "#btn-export-accueil")
        self.verifier_export(nom_zip, noms, entrees, {}, [], "demo", format_du_jeu("plus-recent"))
        self.assertNotIn("pieces_v%d.csv" % format_du_jeu("plus-recent"), noms)
        self.assertIn(("nouvelle_colonne_v%d" % format_du_jeu("plus-recent")).encode(), entrees["ordres_travail.csv"].split(b"\r\n", 1)[0])
        self.assertIn(("version_schema;'%d" % format_du_jeu("plus-recent")).encode(), entrees["parametres.csv"])
        self.assertEqual(self.attendre_toast(page, "Export téléchargé"), "Export téléchargé : %d fichiers CSV." % NB_TABLES)


class TestRepliSha256(CasNavigateur):
    """Formats.manifeste sans crypto.subtle : empreintes calculées par js/formats.js, égales à hashlib.sha256."""

    VECTEURS_JS = """async () => {
      const motif = (n, f) => Uint8Array.from({ length: n }, (_, i) => f(i));
      const fichiers = [
        { nom: 'a-vide', octets: new Uint8Array(0) },
        { nom: 'b-abc', octets: new TextEncoder().encode('abc') },
        { nom: 'c-1-mio', octets: motif(1 << 20, (i) => (i * 31 + 7) & 255) },
        { nom: 'd-octets-0-255', octets: motif(256, (i) => i) },
        { nom: 'f-sous-tableau', octets: new TextEncoder().encode('xxabcxx').subarray(2, 5) },
        { nom: 'g-tampon', octets: motif(200, (i) => 255 - i).buffer },
      ].concat([55, 56, 63, 64, 65, 119, 120, 1000].map((n) => ({
        nom: 'e-' + String(n).padStart(4, '0'), octets: motif(n, () => 0x61) })));
      return { subtle: typeof crypto.subtle, manifeste: await Formats.manifeste(fichiers, { motif: 'export' }) };
    }"""

    @staticmethod
    def vecteurs_python():
        vecteurs = {
            "a-vide": b"",
            "b-abc": b"abc",
            "c-1-mio": bytes((i * 31 + 7) & 255 for i in range(1 << 20)),
            "d-octets-0-255": bytes(range(256)),
            "f-sous-tableau": b"abc",
            "g-tampon": bytes(255 - i for i in range(200)),
        }
        for n in (55, 56, 63, 64, 65, 119, 120, 1000):
            vecteurs["e-%04d" % n] = b"a" * n
        return vecteurs

    def verifier_vecteurs(self, resultat, subtle_attendu):
        self.assertEqual(resultat["subtle"], subtle_attendu)
        attendus = [{"nom": nom, "octets": len(octets), "sha256": hashlib.sha256(octets).hexdigest()}
                    for nom, octets in sorted(self.vecteurs_python().items())]
        self.assertEqual(resultat["manifeste"], {"application": "Prévo", "motif": "export", "fichiers": attendus})

    def test_formats_manifeste_sans_crypto_subtle_egal_a_hashlib(self):
        self.contexte.add_init_script(SANS_SUBTLE_JS)
        charger_scripts(self.page, ["js/schema.js", "js/formats.js"])
        resultat = self.page.evaluate(self.VECTEURS_JS)
        self.verifier_vecteurs(resultat, "undefined")
        # Valeur de la norme (FIPS 180-4, exemple « abc »).
        abc = next(f for f in resultat["manifeste"]["fichiers"] if f["nom"] == "b-abc")
        self.assertEqual(abc["sha256"], "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")

    def test_formats_manifeste_avec_crypto_subtle_meme_resultat(self):
        charger_scripts(self.page, ["js/schema.js", "js/formats.js"])
        self.verifier_vecteurs(self.page.evaluate(self.VECTEURS_JS), "object")


if __name__ == "__main__":
    unittest.main()
