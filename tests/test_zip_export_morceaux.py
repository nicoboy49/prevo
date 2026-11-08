"""Export ZIP par morceaux (T228, morceau 3 de T215) : js/modules/zip-donnees.js écrit le ZIP par ZipFlux
(js/modules/zip-flux.js), un document à la fois, sans JSZip.generateAsync ; les limites de l'import sont contrôlées sur
les TAILLES des documents, avant toute lecture de leur contenu.

    compatibilité  ServeurPrevo sur une copie de la démo (dossier temporaire) qui cite une photo JPEG, une notice PDF
                   et un document absent (fictifs) ; ZipDonnees.contenu() ne garde aucun octet de document (tailles
                   seulement ; taille de manifeste.json exacte avant l'écriture) ; export par le vrai bouton ; le ZIP
                   est relu :
                     - par Python (zipfile) : testzip() à None, photo stockée (méthode 0), CSV, PDF et manifeste
                       compressés (méthode 8), date DOS = date du manifeste, octets et manifeste exacts ;
                     - par l'import courant (ZipLecture.lire de cette copie) ;
                     - par l'import de la bêta 2 publiée : zip-lecture.js de l'étiquette v2.0.0-beta.2 et ses
                       dépendances de la même étiquette (dont JSZip), tirés par « git show » dans une page vide ;
    navigateur     CompressionStream sans « deflate-raw » (décision de Nicolas : pas de JSZip en secours) : fenêtre
                   « Export ZIP impossible » avec ZipFlux.MESSAGE_NAVIGATEUR, aucun document demandé, aucun ZIP écrit
                   ni téléchargé, pour l'export complet comme pour les données seules ;
    mémoire        8 documents fictifs incompressibles de 4 Mo (32 Mo : 4 notices PDF, 4 photos JPEG), mode serveur :
                     - ordre exact des appels (espions sur App.adaptateur.lireDocument et ZipFlux.ecrivain) : passe 1,
                       chaque document demandé puis rendu avant le suivant, aucun ajout ; puis l'écrivain, les CSV, et
                       pour chaque document : demandé, rendu, ajouté, avant que le suivant ne soit demandé ;
                       manifeste.json en dernier ;
                     - mesure : à chaque demande d'un document (16 points d'arrêt), le ramasse-miettes est forcé
                       (CDP HeapProfiler.collectGarbage) et la mémoire des ArrayBuffer de la page est lue
                       (Runtime.getHeapUsage, backingStorageSize : exacte, les Blob n'y comptent pas) ; elle ne dépasse
                       jamais la première mesure de plus d'un document (4 Mo), alors que garder les documents la ferait
                       monter de 4 Mo par document (28 Mo au dernier).
                   Choix : l'ordre des appels prouve qu'un seul document est en cours à la fois ; la mesure prouve qu'il
                   est bien oublié ensuite (aucune référence gardée). performance.memory n'est pas retenu : grossier
                   (arrondi) et sans les ArrayBuffer.

Règle numéro un : jamais de données réelles (démo et documents fictifs, dossiers temporaires).

Lancer depuis la racine du projet (à travers le verrou du navigateur) :
    py -X utf8 -m unittest discover -s tests -p "test_zip_export_morceaux.py" -v
"""
import base64
import hashlib
import io
import json
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from datetime import datetime
from pathlib import Path

from commun import RACINE, CasNavigateur, ServeurPrevo, attendre_pret, charger_scripts, preregler_profil
from test_zip_import import TABLES, fichiers_demo
from test_zip_limites import ecrire_dossier, octets_fictifs, poser_documents

MIO = 1024 * 1024
TAILLE_DOCUMENT = 4 * MIO
LONG_MS = 120000
ETIQUETTE_BETA2 = "v2.0.0-beta.2"
# Scripts de la page de l'import de la bêta 2 (tirés de l'étiquette, JSZip compris : il n'est plus dans le dépôt).
SCRIPTS_IMPORT = ["js/lib/papaparse.min.js", "js/lib/jszip.min.js", "js/schema.js", "js/formats.js", "js/donnees.js",
                  "js/modules/zip-tables.js", "js/modules/zip-lecture.js"]
CSV = sorted(table + ".csv" for table in TABLES)
ERREUR_ABSENT = re.compile(r"status of 404.*/api/documents/notice-absente\.pdf")

# ZipLecture.lire sur des octets donnés en base64 → { ok, refus, documents: [[nom, taille, empreinte]], manquants }.
LIRE_ZIP_JS = """async (enBase64) => {
  const r = await ZipLecture.lire(Uint8Array.from(atob(enBase64), (c) => c.charCodeAt(0)));
  return { ok: r.ok, refus: r.refus, documents: r.ok ? r.documents.map((d) => [d.nom, d.taille, d.empreinte]) : null,
    manquants: r.ok && r.manifeste ? (r.manifeste.manquants || null) : null };
}"""

# Espions de l'ordre des appels (et points d'arrêt pour la mesure si `pause`) : journal window.__journal.
ESPIONS_JS = """(pause) => {
  window.__journal = [];
  window.__pause = null;
  const adaptateur = App.adaptateur;
  const lire = adaptateur.lireDocument;
  adaptateur.lireDocument = async function (nom) {
    window.__journal.push('lire ' + nom);
    if (pause) await new Promise((reprendre) => { window.__pause = { nom, reprendre }; });
    const lu = await lire.apply(this, arguments);
    window.__journal.push('lu ' + nom);
    return lu;
  };
  const creer = ZipFlux.ecrivain;
  ZipFlux.ecrivain = function () {
    const ecrivain = creer.apply(this, arguments);
    window.__journal.push('ecrivain');
    const ajouter = ecrivain.ajouter;
    ecrivain.ajouter = function (nom) {
      window.__journal.push('ajouter ' + nom);
      return ajouter.apply(this, arguments).then((resultat) => { window.__journal.push('ajouté ' + nom); return resultat; });
    };
    return ecrivain;
  };
}"""

# Navigateur sans « deflate-raw » : CompressionStream refuse ce format (comme un navigateur trop ancien).
SANS_DEFLATE_BRUT_JS = """(() => {
  const Origine = window.CompressionStream;
  window.CompressionStream = function (format) {
    if (format === 'deflate-raw') throw new TypeError('format non pris en charge');
    return new Origine(format);
  };
})();"""


def sha256(octets):
    return hashlib.sha256(octets).hexdigest()


def en_base64(octets):
    return base64.b64encode(octets).decode("ascii")


def scripts_beta2(dossier):
    """Écrit dans `dossier` les SCRIPTS_IMPORT de l'étiquette v2.0.0-beta.2 → leurs chemins ; None si git ou
    l'étiquette manquent (copie sans étiquettes)."""
    chemins = []
    for script in SCRIPTS_IMPORT:
        try:
            sortie = subprocess.run(["git", "show", "%s:%s" % (ETIQUETTE_BETA2, script)], cwd=str(RACINE),
                                    capture_output=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            return None
        if sortie.returncode != 0:
            return None
        chemin = dossier / script
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_bytes(sortie.stdout)
        chemins.append(str(chemin))
    return chemins


class CasMorceaux(CasNavigateur):

    def setUp(self):
        super().setUp()
        self.contexte.set_default_timeout(LONG_MS)
        self.temporaire = Path(tempfile.mkdtemp(prefix="prevo-zip-morceaux-"))
        self.addCleanup(shutil.rmtree, self.temporaire, True)
        preregler_profil(self.contexte, "responsable")

    def ouvrir(self, serveur):
        page = self.page
        page.goto(serveur.url + "/#/parametres")
        attendre_pret(page)
        page.wait_for_selector("#btn-export-zip")
        page.wait_for_load_state("networkidle")
        return page

    def exporter(self, page):
        """Clic sur « Exporter en ZIP » → octets du ZIP téléchargé."""
        with page.expect_download(timeout=LONG_MS) as attente:
            page.click("#btn-export-zip")
        return Path(attente.value.path()).read_bytes()

    def verifier_zip_python(self, octets, documents):
        """ZIP relu par zipfile : intègre, méthodes, date DOS, octets et manifeste exacts → le manifeste."""
        with zipfile.ZipFile(io.BytesIO(octets)) as archive:
            self.assertIsNone(archive.testzip())
            infos = archive.infolist()
            entrees = {info.filename: archive.read(info) for info in infos}
        noms = [info.filename for info in infos]
        self.assertEqual(noms[-1], "manifeste.json")
        self.assertEqual(sorted(noms), sorted(CSV + ["documents/" + nom for nom in documents] + ["manifeste.json"]))
        for info in infos:
            stocke = info.filename.lower().endswith((".jpg", ".jpeg"))
            self.assertEqual(info.compress_type, zipfile.ZIP_STORED if stocke else zipfile.ZIP_DEFLATED, info.filename)
        for nom, contenu in documents.items():
            self.assertTrue(entrees["documents/" + nom] == contenu, nom)
        manifeste = json.loads(entrees["manifeste.json"].decode("utf-8"))
        self.assertEqual(manifeste["fichiers"], [{"nom": nom, "octets": len(entrees[nom]), "sha256": sha256(entrees[nom])}
                                                 for nom in sorted(noms) if nom != "manifeste.json"])
        # Date DOS (heure locale, secondes paires) = date du manifeste (même Date à l'écriture).
        date = datetime.strptime(manifeste["date"], "%Y-%m-%dT%H:%M:%S")
        attendue = (date.year, date.month, date.day, date.hour, date.minute, date.second - date.second % 2)
        self.assertEqual({info.date_time for info in infos}, {attendue})
        return manifeste


# ---------------------------------------------------------------------------
# 1. Compatibilité : Python, import courant, import de la bêta 2
# ---------------------------------------------------------------------------

class TestCompatibilite(CasMorceaux):

    def test_zip_relu_par_python_par_l_import_courant_et_par_la_beta_2(self):
        self.autoriser_erreur(ERREUR_ABSENT)
        documents = {
            "photo-pompe.jpg": octets_fictifs(300 * 1024, "photo-pompe", b"\xff\xd8\xff\xe0"),
            "notice-moteur.pdf": b"%PDF-1.4\n" + b"% notice fictive du moteur, page de texte compressible\n" * 4000,
        }
        demo = fichiers_demo()
        demo["equipements.csv"] = poser_documents(demo["equipements.csv"], "document",
                                                  ["notice-moteur.pdf", "notice-absente.pdf"])
        demo["demandes.csv"] = poser_documents(demo["demandes.csv"], "photo", ["photo-pompe.jpg"])
        source = ecrire_dossier(self.temporaire / "source",
                                dict(demo, **{"documents/" + nom: octets for nom, octets in documents.items()}))
        beta2 = scripts_beta2(self.temporaire / "beta2")
        if beta2 is None:
            self.skipTest("étiquette %s introuvable (ou git indisponible)" % ETIQUETTE_BETA2)
        with ServeurPrevo(source=source) as serveur:
            page = self.ouvrir(serveur)
            # contenu() : tailles seulement pour les documents (aucun octet), manifeste.json en dernier.
            prevu = page.evaluate("async () => { const r = await ZipDonnees.contenu(); return { manifeste: r.manifeste, "
                                  "fichiers: r.fichiers.map((f) => [f.nom, f.taille, 'octets' in f]) }; }")
            self.assertIsNone(prevu["manifeste"])
            fichiers = {nom: (taille, a_des_octets) for nom, taille, a_des_octets in prevu["fichiers"]}
            self.assertEqual(prevu["fichiers"][-1][0], "manifeste.json")
            for nom, contenu in documents.items():
                self.assertEqual(fichiers["documents/" + nom], (len(contenu), False), nom)
            self.assertTrue(all(fichiers[nom][1] for nom in CSV))
            octets = self.exporter(page)
            manifeste = self.verifier_zip_python(octets, documents)
            self.assertEqual(manifeste["manquants"], ["notice-absente.pdf"])
            with zipfile.ZipFile(io.BytesIO(octets)) as archive:
                taille_manifeste = archive.getinfo("manifeste.json").file_size
            self.assertEqual(fichiers["manifeste.json"], (taille_manifeste, False))     # taille exacte, avant écriture
            attendus = sorted([nom, len(contenu), sha256(contenu)] for nom, contenu in documents.items())
            # Import courant (ZipLecture de cette copie), dans la page de l'application.
            courant = page.evaluate(LIRE_ZIP_JS, en_base64(octets))
            self.assertEqual((courant["ok"], courant["refus"]), (True, None))
            self.assertEqual(sorted(courant["documents"]), attendus)
            self.assertEqual(courant["manquants"], ["notice-absente.pdf"])
            page.goto("about:blank")            # plus aucune requête de fond vers le serveur arrêté
        # Import de la bêta 2 publiée, dans une page vide.
        page_beta2 = self.contexte.new_page()
        self.surveiller(page_beta2)
        charger_scripts(page_beta2, beta2)
        # Bêta 2 : import par JSZip, sans ZipFlux.
        self.assertEqual(page_beta2.evaluate("[typeof ZipFlux, typeof JSZip, typeof ZipLecture.lire]"),
                         ["undefined", "function", "function"])
        lu = page_beta2.evaluate(LIRE_ZIP_JS, en_base64(octets))
        self.assertEqual((lu["ok"], lu["refus"]), (True, None))
        self.assertEqual(sorted(lu["documents"]), attendus)
        self.assertEqual(lu["manquants"], ["notice-absente.pdf"])


# ---------------------------------------------------------------------------
# 2. Navigateur sans « deflate-raw »
# ---------------------------------------------------------------------------

class TestNavigateur(CasMorceaux):

    def test_sans_deflate_brut_export_refuse_avec_le_message_du_navigateur(self):
        self.contexte.add_init_script(SANS_DEFLATE_BRUT_JS)
        demo = fichiers_demo()
        demo["equipements.csv"] = poser_documents(demo["equipements.csv"], "document", ["notice.pdf"])
        source = ecrire_dossier(self.temporaire / "source", dict(demo, **{
            "documents/notice.pdf": b"%PDF-1.4\n% notice fictive\n"}))
        telechargements = []
        with ServeurPrevo(source=source) as serveur:
            page = self.ouvrir(serveur)
            page.on("download", lambda telechargement: telechargements.append(telechargement))
            self.assertFalse(page.evaluate("ZipFlux.disponible()"))
            message = page.evaluate("ZipFlux.MESSAGE_NAVIGATEUR")
            self.assertTrue(message.startswith("Ce navigateur est trop ancien pour lire ou écrire un ZIP de Prévo."))
            page.evaluate(ESPIONS_JS, False)
            for bouton in ("#btn-export-zip", "#btn-export-donnees-seules"):
                with self.subTest(bouton=bouton):
                    page.click(bouton)
                    page.wait_for_selector("#export-zip-refus")
                    fenetre = page.locator("dialog").filter(has=page.locator("#export-zip-refus"))
                    self.assertEqual(fenetre.locator("h2").inner_text().strip(), "Export ZIP impossible")
                    texte = re.sub(r"\s+", " ", page.inner_text("#export-zip-refus")).strip()
                    self.assertEqual(texte, message)
                    page.click("dialog .fenetre-actions button:has-text('Fermer')")
                    page.wait_for_selector("#export-zip-refus", state="detached")
            self.assertEqual(page.evaluate("window.__journal"), [])      # aucun document demandé, aucun écrivain
            page.wait_for_timeout(300)
            self.assertEqual(telechargements, [])
            page.goto("about:blank")


# ---------------------------------------------------------------------------
# 3. Mémoire bornée à un document près
# ---------------------------------------------------------------------------

class TestMemoire(CasMorceaux):

    def mesurer(self, cdp):
        """Octets des ArrayBuffer vivants de la page, après un ramasse-miettes complet."""
        cdp.send("HeapProfiler.collectGarbage")
        usage = cdp.send("Runtime.getHeapUsage")
        self.assertIn("backingStorageSize", usage, "Chromium trop ancien pour cette mesure")
        return usage["backingStorageSize"]

    def test_quelques_dizaines_de_mo_un_document_a_la_fois_memoire_bornee(self):
        notices = {"notice-lourde-%d.pdf" % n: octets_fictifs(TAILLE_DOCUMENT, "notice-%d" % n, b"%PDF-1.4\n")
                   for n in range(4)}
        photos = {"photo-lourde-%d.jpg" % n: octets_fictifs(TAILLE_DOCUMENT, "photo-%d" % n, b"\xff\xd8\xff\xe0")
                  for n in range(4)}
        documents = dict(notices, **photos)
        demo = fichiers_demo()
        demo["equipements.csv"] = poser_documents(demo["equipements.csv"], "document", sorted(notices))
        demo["demandes.csv"] = poser_documents(demo["demandes.csv"], "photo", sorted(photos))
        source = ecrire_dossier(self.temporaire / "source",
                                dict(demo, **{"documents/" + nom: octets for nom, octets in documents.items()}))
        with ServeurPrevo(source=source) as serveur:
            page = self.ouvrir(serveur)
            noms = page.evaluate("ZipDonnees.nomsDocuments()")
            self.assertEqual(noms, sorted(notices) + sorted(photos))
            csv = page.evaluate("Schema.nomsTables().map((table) => Schema.table(table).fichier)")
            page.evaluate(ESPIONS_JS, True)
            cdp = self.contexte.new_cdp_session(page)
            cdp.send("HeapProfiler.enable")
            mesures = []
            with page.expect_download(timeout=LONG_MS) as attente:
                page.click("#btn-export-zip")
                for _ in range(2 * len(noms)):                      # passe 1 puis passe 2 : 16 demandes
                    page.wait_for_function("() => window.__pause !== null")
                    nom = page.evaluate("window.__pause.nom")
                    mesures.append((nom, self.mesurer(cdp)))
                    page.evaluate("() => { const pause = window.__pause; window.__pause = null; pause.reprendre(); }")
            octets = Path(attente.value.path()).read_bytes()
            journal = page.evaluate("window.__journal")
            page.goto("about:blank")
        # Ordre exact : un seul document à la fois, dans les deux passes.
        attendu = [etape for nom in noms for etape in ("lire " + nom, "lu " + nom)] + ["ecrivain"]
        attendu += [etape for nom in csv for etape in ("ajouter " + nom, "ajouté " + nom)]
        attendu += [etape for nom in noms for etape in ("lire " + nom, "lu " + nom, "ajouter documents/" + nom,
                                                        "ajouté documents/" + nom)]
        attendu += ["ajouter manifeste.json", "ajouté manifeste.json"]
        self.assertEqual(journal, attendu)
        # Mémoire : jamais plus d'un document au-dessus de la première mesure.
        self.assertEqual([nom for nom, _ in mesures], noms + noms)
        base = mesures[0][1]
        trop = [(nom, valeur) for nom, valeur in mesures if valeur - base >= TAILLE_DOCUMENT]
        self.assertEqual(trop, [], "mesures (octets) : %r" % mesures)
        # Le ZIP est complet et juste.
        self.verifier_zip_python(octets, documents)


if __name__ == "__main__":
    unittest.main()
