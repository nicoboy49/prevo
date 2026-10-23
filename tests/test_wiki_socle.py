"""Socle du lot 6 refondu (tâche T110, ARCHITECTURE.md §20.1 et §20.2) : wiki de maintenance.

    routes   : #/wiki et #/wiki/<id> ouverts aux trois profils, entrée « Wiki » du menu avec son icône, entre Parc
               et Magasin ; #/wiki-journal réservé au responsable (le technicien et le demandeur ne l'atteignent
               pas) ; le module Wiki et ses seuils (D100, §20.1) existent ;
    format 3 : la démo porte version_schema = 3, les tables wiki_pages et wiki_journal (vides au socle) et la
               colonne astuce des OT ; l'export ZIP contient les 24 tables, en-têtes exacts ;
    modules  : la synthèse de la première version a disparu (Wiki.controlerSynthese, Wiki.afficherSynthese,
               consigne syntheseWiki) ; Wiki.page(id) rend la page d'un équipement ;
    API      : Indicateurs.datePanne est publique (date de la DI d'origine, sinon création de l'OT).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_wiki_socle.py" -v
"""
import unittest
import zipfile

from commun import CasNavigateur, attendre_pret, preregler_profil, url_fichier

BOM = b"\xef\xbb\xbf"
ENTETES = {
    "wiki_pages.csv": b"id;type;titre;cle;equipement_id;article_id;cause_code;rattache_a;texte;ot_cites;liens;version;"
                      b"origine;modele;derniere_entree;valide_par;valide_le;cree_le;modifie_le;statut\r\n",
    "wiki_journal.csv": b"id;nature;ot_id;date_intervention;statut;anterieure;ordre;pages;changements;contradictions;"
                        b"raisons;modele;essais;cree_le;traite_le;decide_par;decide_le;motif\r\n",
}
# Profil : (type, nom, technicienId) ; un technicien choisit sa fiche, un demandeur donne son nom.
PROFILS = {"demandeur": ("Lucie Martin", ""), "technicien": ("", "TEC-0001"), "responsable": ("", "")}
SEUILS = {"pagesCreeesMax": 3, "phrasesMax": 12, "motsMax": 250, "relancesMax": 1, "pagesEnvoyeesMax": 8, "catalogueMax": 400,
          "agentsSimultanes": 5, "astuceMax": 500, "otMinimum": 5, "recidiveJours": 30, "dernieres": 10,
          "symptomesMax": 5, "contradictionAncienneJours": 30, "demoAValiderJours": 14}


class TestWikiSocle(CasNavigateur):

    def ouvrir_demo(self, profil="responsable"):
        nom, technicien = PROFILS[profil]
        preregler_profil(self.contexte, profil, nom, technicien)
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)

    def verifier_routes_et_menu(self, profil):
        self.ouvrir_demo(profil)
        page = self.page
        lien = page.locator('#menu a[data-ecran="wiki"]')
        self.assertEqual(lien.count(), 1)
        self.assertEqual(lien.get_attribute("href"), "#/wiki")
        self.assertEqual(lien.locator("svg.icone").count(), 1)
        page.evaluate("location.hash = '#/wiki'")
        page.wait_for_selector(".wiki-liste", state="attached")
        self.assertEqual(page.inner_text("#contenu h1").strip(), "Wiki de maintenance")
        page.evaluate("location.hash = '#/wiki/EQ-0001'")
        page.wait_for_selector(".wiki-page", state="attached")
        self.assertEqual(lien.get_attribute("aria-current"), "page")
        # Journal du wiki : responsable seulement ; ailleurs, l'écran n'est pas montré.
        page.evaluate("location.hash = '#/wiki-journal'")
        if profil == "responsable":
            page.wait_for_selector(".wiki-journal", state="attached")
            self.assertEqual(page.inner_text("#contenu h1").strip(), "Journal du wiki")
        else:
            page.wait_for_function("!document.querySelector('.wiki-page')")
            self.assertEqual(page.locator(".wiki-journal").count(), 0)

    def test_routes_et_menu_demandeur(self):
        self.verifier_routes_et_menu("demandeur")

    def test_routes_et_menu_technicien(self):
        self.verifier_routes_et_menu("technicien")

    def test_routes_et_menu_responsable(self):
        self.verifier_routes_et_menu("responsable")

    def test_entree_du_menu_entre_parc_et_magasin(self):
        self.ouvrir_demo("responsable")
        ordre = self.page.evaluate("Array.from(document.querySelectorAll('#menu a')).map((a) => a.dataset.ecran)")
        self.assertLess(ordre.index("parc"), ordre.index("wiki"))
        self.assertLess(ordre.index("wiki"), ordre.index("magasin"))
        self.assertNotIn("wiki-journal", ordre)          # le journal n'a pas d'entrée de menu propre

    def test_module_et_seuils(self):
        self.ouvrir_demo("technicien")
        self.assertEqual(self.page.evaluate("Wiki.SEUILS"), SEUILS)
        self.assertTrue(self.page.evaluate("Object.isFrozen(Wiki.SEUILS)"))
        absents = self.page.evaluate("""() => ['controlerSynthese', 'afficherSynthese', 'enregistrer', 'requetesDemo',
          'donneesSynthese', 'ETATS_SYNTHESE'].filter((nom) => nom in Wiki)""")
        self.assertEqual(absents, [])
        self.assertFalse(self.page.evaluate("'syntheseWiki' in Ia.PROMPTS"))
        page = self.page.evaluate("Wiki.page('EQ-0001')")
        self.assertEqual((page["id"], page["type"]), ("EQ-0001", "équipement"))
        self.assertEqual(page["calcul"], self.page.evaluate("Wiki.pageEquipement('EQ-0001')"))
        self.assertIsNone(self.page.evaluate("Wiki.page('EQ-9999')"))

    def test_demo_au_format_3_et_export_zip(self):
        self.ouvrir_demo("responsable")
        self.assertEqual(self.page.evaluate("Donnees.parametre('version_schema')"), "3")
        self.assertEqual(self.page.evaluate("Schema.version"), 3)
        self.assertEqual(self.page.evaluate("Schema.nomsTables().slice(-2)"), ["wiki_pages", "wiki_journal"])
        self.assertEqual(self.page.evaluate("Donnees.lignes('wiki_pages').length"), 0)
        self.assertEqual(self.page.evaluate("Donnees.lignes('wiki_journal').length"), 0)
        self.assertTrue(self.page.evaluate("Donnees.lignes('ordres_travail').every((ot) => 'astuce' in ot)"))
        self.assertEqual(self.page.evaluate(
            "Donnees.problemes().filter((p) => p.gravite !== 'info' && p.table.startsWith('wiki_')).length"), 0)
        with self.page.expect_download() as attente:
            self.page.click("#btn-export-accueil")
        with zipfile.ZipFile(attente.value.path()) as archive:
            noms = [n for n in archive.namelist() if n.endswith(".csv")]
            self.assertEqual(len(noms), 24)
            self.assertNotIn("wiki_syntheses.csv", noms)
            for nom, entete in ENTETES.items():
                with self.subTest(fichier=nom):
                    self.assertEqual(archive.read(nom), BOM + entete)
            ordres = archive.read("ordres_travail.csv")
            self.assertTrue(ordres.split(b"\r\n", 1)[0].endswith(b";anomalie_constatee;astuce"))

    def test_date_panne_publique(self):
        self.ouvrir_demo("responsable")
        resultat = self.page.evaluate("""() => {
          const ordres = Donnees.lignes('ordres_travail');
          const demandes = Donnees.lignes('demandes');
          const avecDi = ordres.find((ot) => ot.di_id && demandes.some((di) => di.id === ot.di_id));
          const sansDi = ordres.find((ot) => !ot.di_id && !demandes.some((di) => di.ot_id === ot.id));
          const ctx = Indicateurs.contexte();
          return {
            avecDi: Indicateurs.datePanne(avecDi), diDate: demandes.find((di) => di.id === avecDi.di_id).date_heure,
            sansDi: Indicateurs.datePanne(sansDi), creation: sansDi.date_creation,
            avecContexte: Indicateurs.datePanne(avecDi, ctx),
          };
        }""")
        self.assertEqual(resultat["avecDi"], resultat["diDate"])
        self.assertEqual(resultat["avecContexte"], resultat["diDate"])
        self.assertEqual(resultat["sansDi"], resultat["creation"])


if __name__ == "__main__":
    unittest.main()
