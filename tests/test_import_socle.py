"""Socle du lot 5 — assistant d'import (tâche T77, ARCHITECTURE.md §18.1 ; CS79, CS80, CS93).

    - écran #/import « Importer des données » : ouvert au responsable ; technicien et demandeur
      renvoyés à l'accueil avec le message des écrans réservés ;
    - SheetJS CE 0.20.3 (js/lib/xlsx.full.min.js) n'est jamais chargé au démarrage (aucune requête,
      `XLSX` absent), ni en mode serveur ni en démo ; App.chargerSheetJS() le charge (version 0.20.3) ;
    - motif de sauvegarde « avant-import » : accepté par le serveur (nom « AAAA-MM-JJ_HHMMSS_avant-import »,
      listé, restaurable) et par le stockage « dossier » ; noms valides et invalides contrôlés pareil des
      deux côtés ; Paramètres l'affiche « Avant import ».

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_import_socle.py" -v
"""
import re
import unittest

from commun import (RACINE, CasNavigateur, ServeurPrevo, ServeurStatique, attendre_pret, installer_dossier_simule,
                    preregler_profil, url_fichier)
from test_app import ERREUR_PING_ABSENT
from test_version_schema import demander_restauration, demander_sauvegarde, requete

MOTIF_NOM_AVANT_IMPORT = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}_avant-import$")
NOMS = (
    ("1999-01-01_120000_avant-import", True),
    ("1999-01-01_avant-import", False),
    ("1999-01-01_120000_avant-importx", False),
    ("1999-01-01_120000_avant-import/../x", False),
)
NOTER_TOASTS_JS = """(() => {
  window.__toasts = [];
  let dernier = '';
  new MutationObserver(() => {
    const zone = document.getElementById('toast');
    const texte = zone && zone.classList.contains('visible') ? zone.textContent.trim() : '';
    if (texte && texte !== dernier) window.__toasts.push(texte);
    dernier = texte;
  }).observe(document, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['class'] });
})();"""


class TestEcranEtSheetJS(CasNavigateur):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serveur = ServeurPrevo()
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)

    def setUp(self):
        super().setUp()
        self.adresses = []
        self.page.on("request", lambda requete: self.adresses.append(requete.url))
        self.contexte.add_init_script(NOTER_TOASTS_JS)

    def ouvrir(self, route, profil="responsable", **options):
        preregler_profil(self.contexte, profil, **options)
        self.page.goto(self.serveur.url + "/" + route)
        attendre_pret(self.page)
        return self.page

    def test_responsable_ouvre_l_ecran(self):
        page = self.ouvrir("#/import")
        page.wait_for_selector("#contenu h1")
        self.assertEqual(page.inner_text("#contenu h1").strip(), "Importer des données")

    def test_technicien_et_demandeur_renvoyes(self):
        for profil, options in (("technicien", {"nom": "Technicien essai", "technicien_id": "TEC-0001"}),
                                ("demandeur", {"nom": "Paul Essai"})):
            with self.subTest(profil=profil):
                contexte = self.navigateur.new_context(locale="fr-FR")
                try:
                    contexte.add_init_script(NOTER_TOASTS_JS)
                    preregler_profil(contexte, profil, **options)
                    page = contexte.new_page()
                    self.surveiller(page)
                    page.goto(self.serveur.url + "/#/import")
                    attendre_pret(page)
                    page.wait_for_function("location.hash === '#/accueil'")
                    page.wait_for_function("(window.__toasts || []).some((t) => t.includes('Importer des données')"
                                           " && t.includes(\"n'est pas disponible pour le profil\"))")
                finally:
                    contexte.close()

    def test_sheetjs_jamais_charge_au_demarrage_puis_a_la_demande(self):
        page = self.ouvrir("#/accueil")
        page.wait_for_load_state("networkidle")
        self.assertTrue(page.evaluate("typeof XLSX === 'undefined'"))
        self.assertEqual([a for a in self.adresses if "xlsx" in a], [])
        # Même en ouvrant l'écran d'import : le chargement est demandé par l'assistant, pas au démarrage
        self.assertEqual(page.evaluate("App.chargerSheetJS().then((x) => x.version)"), "0.20.3")
        self.assertEqual(len([a for a in self.adresses if a.endswith("/js/lib/xlsx.full.min.js")]), 1)
        # Un second appel réutilise la même bibliothèque
        self.assertEqual(page.evaluate("App.chargerSheetJS().then((x) => x.version)"), "0.20.3")
        self.assertEqual(len([a for a in self.adresses if a.endswith("/js/lib/xlsx.full.min.js")]), 1)

    def test_demo_file_sheetjs_absent_au_demarrage_puis_charge(self):
        preregler_profil(self.contexte, "responsable")
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        self.assertTrue(self.page.evaluate("typeof XLSX === 'undefined'"))
        self.assertEqual(self.page.evaluate("App.chargerSheetJS().then((x) => x.version)"), "0.20.3")

    def test_parametres_affiche_avant_import(self):
        statut, reponse = demander_sauvegarde(self.serveur, {"motif": "avant-import"})
        self.assertEqual(statut, 200, reponse)
        page = self.ouvrir("#/parametres")
        page.wait_for_selector(".sauvegarde-nom")
        self.assertIn("Avant import", page.inner_text("#contenu"))


class TestMotifServeur(unittest.TestCase):

    def test_motif_avant_import_accepte_liste_restaurable_et_noms_controles(self):
        with ServeurPrevo() as serveur:
            statut, reponse = demander_sauvegarde(serveur, {"motif": "avant-import"})
            self.assertEqual(statut, 200, reponse)
            nom = reponse["sauvegarde"]
            self.assertRegex(nom, MOTIF_NOM_AVANT_IMPORT)
            self.assertTrue((serveur.dossier / "sauvegardes" / nom / "equipements.csv").is_file())
            statut, liste = requete(serveur, "GET", "/api/sauvegardes")
            self.assertIn(nom, [s["nom"] for s in liste["sauvegardes"]])
            statut, reponse = demander_restauration(serveur, nom, ["equipements"])
            self.assertEqual(statut, 200, reponse)
            self.assertEqual(reponse["restaurees"], ["equipements"])
            for essai, valide in NOMS:
                with self.subTest(nom=essai):
                    statut, reponse = demander_restauration(serveur, essai, ["equipements"])
                    self.assertEqual(statut, 404 if valide else 400, reponse)


class TestMotifDossier(CasNavigateur):

    def test_stockage_dossier_accepte_avant_import_et_controle_les_noms(self):
        self.autoriser_erreur(ERREUR_PING_ABSENT)
        installer_dossier_simule(self.contexte, "donnees-import")
        preregler_profil(self.contexte, "responsable")
        page = self.page
        with ServeurStatique(RACINE) as statique:
            page.goto(statique.url + "/index.html")
            page.wait_for_selector("#btn-dossier")
            page.click("#btn-dossier")
            page.wait_for_selector("#ecran-base-vide", state="visible")
            page.click("#btn-base-demo")
            attendre_pret(page)
            self.assertEqual(page.evaluate("App.mode"), "dossier")
            nom = page.evaluate("App.adaptateur.sauvegarder('avant-import')")
            self.assertRegex(nom, MOTIF_NOM_AVANT_IMPORT)
            noms = page.evaluate("App.adaptateur.listerSauvegardes().then((l) => l.map((s) => s.nom || s))")
            self.assertIn(nom, noms)
            for essai, valide in NOMS:
                with self.subTest(nom=essai):
                    message = page.evaluate("""(nom) => App.adaptateur.restaurer(nom, ['equipements'])
                      .then(() => 'ok', (erreur) => erreur.message)""", essai)
                    if valide:
                        self.assertIn("introuvable", message)
                    else:
                        self.assertIn("invalide", message)


if __name__ == "__main__":
    unittest.main()
