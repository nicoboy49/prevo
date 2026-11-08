"""Export « données seules (sans les documents) », importable comme l'export complet (T214, décision de Nicolas : « Si
l'import d'un ZIP sans documents remplace une base qui en a, la confirmation doit le dire clairement, et les documents
existants ne doivent jamais être supprimés en silence. »).

Code visé : js/modules/zip-donnees.js (contenu({ sansDocuments }), manifeste « documents »: « exclus »),
js/modules/parametres.js (bouton #btn-export-donnees-seules), js/modules/zip-lecture.js (manifeste « exclus » et
documents dans le ZIP : refus), js/modules/parametres-zip.js (confirmation, aucun document écrit ni supprimé).

Base A (deux modes) : la démo avec des documents cités dans les trois colonnes et deux rapports figés (base_a de
test_zip_import : 6 documents présents, 2 références sans document : un absent, un nom piégé), plus un document que rien
ne cite. Le responsable clique sur « Exporter les données seules (sans les documents) » :
    - ZIP prevo-export-AAAA-MM-JJ-sans-documents.zip : les CSV (NB_TABLES) et manifeste.json, aucune entrée documents/ ;
      manifeste exact (clés dans l'ordre, « documents »: « exclus » juste avant « fichiers », pas de « manquants ») ;
      message « Export téléchargé : NB_TABLES fichiers CSV, sans les documents (données seules). » ;
    - (serveur) le même ZIP avec un document ajouté (et décrit au manifeste) : refusé, rien n'est écrit ;
    - réimport dans la même base : confirmation « Ce ZIP ne contient pas les documents : les 6 documents déjà présents
      sont gardés tels quels ; 2 documents cités par les données importées n'existent pas ici. » ; après l'import, le
      dossier des documents est identique à l'octet (aucun supprimé, aucun ajouté, le document non cité compris),
      les tables sont celles du ZIP (lignes), le journal le dit.
    serveur  ServeurPrevo sur une copie (dossier temporaire) ;
    dossier  OPFS (installer_dossier_simule).

Règle numéro un : jamais de données réelles (copies dans des dossiers temporaires, OPFS du navigateur de test).

Lancer depuis la racine du projet (à travers le verrou du navigateur) :
    py -X utf8 -m unittest discover -s tests -p "test_zip_donnees_seules.py" -v
"""
import base64
import hashlib
import io
import json
import re
import unittest
import zipfile

from commun import NB_TABLES, RACINE, ServeurPrevo, ServeurStatique, attendre_pret, installer_dossier_simule, preregler_profil
from test_zip_export import NOTER_TOASTS_JS
from test_zip_import import (BOUTON_REMPLACER, ECRIRE_OPFS_JS, ERREUR_DOCUMENT_ABSENT, ERREUR_PING_ABSENT,
                             INSTANTANE_OPFS_JS, TABLES, CasImport, base_a, en_base64, lire_csv, octets_pdf)

NOM_DOSSIER = "donnees-zip-donnees-seules"
MOTIF_NOM_ZIP = re.compile(r"^prevo-export-\d{4}-\d{2}-\d{2}-sans-documents\.zip$")
CLES_MANIFESTE = ["application", "version_appli", "format", "date", "motif", "mode", "documents", "fichiers"]
MESSAGE_EXPORT = "Export téléchargé : %d fichiers CSV, sans les documents (données seules)." % NB_TABLES
CONFIRMATION = ("Ce ZIP ne contient pas les documents : les 6 documents déjà présents sont gardés tels quels ; "
                "2 documents cités par les données importées n'existent pas ici.")
FIN = "sans les documents (données seules : aucun document existant supprimé ni remplacé)"
JOURNAL = "données seules : documents gardés tels quels"
NON_CITE = "orphelin-non-cite.pdf"


def base_avec_documents():
    """{chemin : octets} de la base A : CSV, documents/ (cités, plus un document que rien ne cite)."""
    csv_a, documents_a = base_a()
    documents_a[NON_CITE] = octets_pdf("document que rien ne cite")
    return dict(csv_a, **{"documents/" + nom: octets for nom, octets in documents_a.items()})


def octets_zip(entrees):
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as archive:
        for nom, octets in entrees.items():
            archive.writestr(zipfile.ZipInfo(nom, date_time=(2026, 11, 4, 9, 30, 0)), octets, zipfile.ZIP_DEFLATED)
    return tampon.getvalue()


class CasDonneesSeules(CasImport):

    def setUp(self):
        super().setUp()
        self.contexte.add_init_script(NOTER_TOASTS_JS)

    def exporter_donnees_seules(self, page):
        """Clic sur le vrai bouton ; ZIP et message vérifiés → {nom: octets} des entrées."""
        page.wait_for_selector("#btn-export-donnees-seules")
        with page.expect_download() as attente:
            page.click("#btn-export-donnees-seules")
        self.assertRegex(attente.value.suggested_filename, MOTIF_NOM_ZIP)
        with zipfile.ZipFile(attente.value.path()) as archive:
            entrees = {nom: archive.read(nom) for nom in archive.namelist()}
        csv = sorted(table + ".csv" for table in TABLES)
        self.assertEqual(sorted(entrees), sorted(csv + ["manifeste.json"]))
        self.assertEqual([nom for nom in entrees if nom.startswith("documents")], [])
        manifeste = json.loads(entrees["manifeste.json"].decode("utf-8"))
        self.assertEqual(list(manifeste), CLES_MANIFESTE)
        self.assertEqual(manifeste["documents"], "exclus")
        self.assertEqual(manifeste["motif"], "export")
        self.assertEqual(manifeste["fichiers"], [{"nom": nom, "octets": len(entrees[nom]),
                                                  "sha256": hashlib.sha256(entrees[nom]).hexdigest()} for nom in csv])
        page.wait_for_function("(m) => (window.__toasts || []).includes(m)", arg=MESSAGE_EXPORT)
        return entrees

    def reimporter(self, page, entrees, documents_actuels, csv_actuels):
        """Réimport dans la même base : confirmation, dossier des documents identique, tables du ZIP."""
        avant = documents_actuels()
        self.assertEqual(len(avant), 7)
        chemin = self.temporaire / "prevo-export-sans-documents.zip"
        chemin.write_bytes(octets_zip(entrees))
        self.choisir_zip(page, chemin)
        info = self.confirmation(page)
        self.assertEqual(page.get_attribute("#confirmation-import-zip", "data-sans-documents"), "1")
        self.assertEqual(info["documents"], 0)
        self.assertEqual(info["documentsTexte"], CONFIRMATION)
        page.click(BOUTON_REMPLACER)
        termine = self.texte_fenetre(page, "import-zip-termine")
        self.assertIn(FIN, termine)
        self.assertEqual(documents_actuels(), avant)                  # aucun supprimé, remplacé ni ajouté
        apres = csv_actuels()
        for table in TABLES:
            if table != "journal":
                self.assertEqual(len(lire_csv(apres[table])[1]), len(lire_csv(entrees[table + ".csv"])[1]), table)
        self.assertIn(JOURNAL, apres["journal"].decode("utf-8"))


class TestServeur(CasDonneesSeules):

    def test_serveur_export_donnees_seules_puis_reimport_documents_gardes(self):
        self.autoriser_erreur(ERREUR_DOCUMENT_ABSENT)                 # présence de vgp-chariot-absent.pdf
        source = self.temporaire / "a"
        for chemin, octets in base_avec_documents().items():
            (source / chemin).parent.mkdir(parents=True, exist_ok=True)
            (source / chemin).write_bytes(octets)
        preregler_profil(self.contexte, "responsable")
        page = self.page
        with ServeurPrevo(source=source) as serveur:
            dossier = serveur.dossier
            page.goto(serveur.url + "/#/parametres")
            attendre_pret(page)
            entrees = self.exporter_donnees_seules(page)

            def documents_actuels():
                return {p.name: p.read_bytes() for p in sorted((dossier / "documents").iterdir()) if p.is_file()}

            def csv_actuels():
                return {table: (dossier / (table + ".csv")).read_bytes() for table in TABLES}

            # Manifeste « exclus » et un document dans le ZIP (décrit au manifeste) : refusé, rien d'écrit.
            ajout = octets_pdf("glissé après l'export")
            manifeste = json.loads(entrees["manifeste.json"].decode("utf-8"))
            manifeste["fichiers"].append({"nom": "documents/ajout.pdf", "octets": len(ajout),
                                          "sha256": hashlib.sha256(ajout).hexdigest()})
            truque = dict(entrees, **{"documents/ajout.pdf": ajout,
                                      "manifeste.json": json.dumps(manifeste, ensure_ascii=False, indent=2).encode()})
            chemin = self.temporaire / "truque.zip"
            chemin.write_bytes(octets_zip(truque))
            page.wait_for_load_state("networkidle")
            avant = (csv_actuels(), documents_actuels())
            self.choisir_zip(page, chemin)
            texte = self.texte_fenetre(page, "import-zip-refus")
            self.assertIn("Le manifeste dit que ce ZIP ne contient pas les documents (données seules), mais il en "
                          "contient", texte)
            self.fermer_fenetre(page, "import-zip-refus")
            self.assertEqual((csv_actuels(), documents_actuels()), avant)
            self.reimporter(page, entrees, documents_actuels, csv_actuels)


class TestDossier(CasDonneesSeules):

    def setUp(self):
        super().setUp()
        self.autoriser_erreur(ERREUR_PING_ABSENT)

    def opfs(self, page):
        return {chemin: base64.b64decode(valeur)
                for chemin, valeur in page.evaluate(INSTANTANE_OPFS_JS, NOM_DOSSIER).items()}

    def test_dossier_export_donnees_seules_puis_reimport_documents_gardes(self):
        base = base_avec_documents()
        installer_dossier_simule(self.contexte, NOM_DOSSIER)
        preregler_profil(self.contexte, "responsable")
        page = self.page
        with ServeurStatique(RACINE) as statique:
            page.goto(statique.url + "/index.html")
            page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
            page.evaluate(ECRIRE_OPFS_JS, [NOM_DOSSIER, {chemin: en_base64(o) for chemin, o in base.items()}])
            page.click("#btn-dossier")
            attendre_pret(page)
            self.assertEqual(page.evaluate("App.mode"), "dossier")
            page.evaluate("location.hash = '#/parametres'")
            page.wait_for_selector("#btn-import-zip")
            entrees = self.exporter_donnees_seules(page)
            page.wait_for_load_state("networkidle")

            def documents_actuels():
                return {c: o for c, o in self.opfs(page).items() if c.startswith("documents/")}

            def csv_actuels():
                fichiers = self.opfs(page)
                return {table: fichiers[table + ".csv"] for table in TABLES}

            self.assertEqual(documents_actuels(), {c: o for c, o in base.items() if c.startswith("documents/")})
            self.reimporter(page, entrees, documents_actuels, csv_actuels)


if __name__ == "__main__":
    unittest.main()
