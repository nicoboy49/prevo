"""Socle du lot 6 refondu (tâche T110, ARCHITECTURE.md §20.1 et §20.2) : wiki de maintenance.

    routes   : #/wiki et #/wiki/<id> ouverts aux trois profils, entrée « Wiki » du menu avec son icône, entre Parc
               et Magasin ; #/wiki-journal réservé au responsable (le technicien et le demandeur ne l'atteignent
               pas) ; le module Wiki, ses seuils (D100, §20.1) et les limites des textes rédigés (refonte 2,
               D100 révisée 2, §20.12 : Wiki.LIMITES par type et par rubrique, d'où viennent phrasesMax et motsMax
               d'un savoir-faire ; « En bref » 3 phrases et 60 mots, D100 révisée 3, D117, T142) existent ;
    format 3 : la démo porte version_schema = 3, les tables wiki_pages et wiki_journal (vides au socle) et la
               colonne astuce des OT ; l'export ZIP contient les 24 tables, en-têtes exacts ;
    modules  : la synthèse de la première version a disparu (Wiki.controlerSynthese, Wiki.afficherSynthese,
               consigne syntheseWiki) ; Wiki.page(id) rend la page d'un équipement ; Wiki.entite (encyclopédie,
               §20.12, T135) est chargé par l'application et prend son profil quand on ne lui en donne pas ;
    API      : Indicateurs.datePanne est publique (date de la DI d'origine, sinon création de l'OT).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_wiki_socle.py" -v
"""
import csv
import io
import unittest
import zipfile

from commun import DOSSIER_DEMO, CasNavigateur, attendre_pret, preregler_profil, url_fichier

BOM = b"\xef\xbb\xbf"
ENTETES = {
    "wiki_pages.csv": b"id;type;titre;cle;equipement_id;article_id;cause_code;rattache_a;texte;ot_cites;liens;version;"
                      b"origine;modele;derniere_entree;valide_par;valide_le;cree_le;modifie_le;statut\r\n",
    "wiki_journal.csv": b"id;nature;ot_id;date_intervention;statut;anterieure;ordre;pages;changements;contradictions;"
                        b"raisons;modele;essais;cree_le;traite_le;decide_par;decide_le;motif\r\n",
}
# Profil : (type, nom, technicienId) ; un technicien choisit sa fiche, un demandeur donne son nom.
PROFILS = {"demandeur": ("Lucie Martin", ""), "technicien": ("", "TEC-0001"), "responsable": ("", "")}
SEUILS = {"pagesCreeesMax": 3, "phrasesMax": 30, "motsMax": 600, "relancesMax": 1, "pagesEnvoyeesMax": 8, "catalogueMax": 400,
          "agentsSimultanes": 5, "astuceMax": 500, "otMinimum": 5, "recidiveJours": 30, "dernieres": 10,
          "symptomesMax": 5, "contradictionAncienneJours": 30, "demoAValiderJours": 14}
LIMITES = {
    "équipement": {"page": None, "rubriques": {"En bref": {"phrases": 3, "mots": 60}, "Astuces": {"phrases": 10, "mots": None}}},
    "composant": {"page": None, "rubriques": {"À quoi il sert": {"phrases": 3, "mots": 80}}},
    "savoir-faire": {"page": {"phrases": 30, "mots": 600}, "rubriques": {}},
}


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
        page.wait_for_selector(".wiki-accueil", state="attached")
        # Accueil de l'encyclopédie (refonte 2, T136) : la phrase-résumé est le titre de l'écran.
        self.assertRegex(page.inner_text("#contenu h1").strip(), r"^\d+ machines?, \d+ pannes?, \d+ articles?")
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
        # Limites des textes rédigés (§20.12) : un type par type de Wiki.RUBRIQUES (plus de « mode ») ; les seuils de page
        # (phrasesMax, motsMax) sont ceux d'un savoir-faire.
        self.assertEqual(self.page.evaluate("Wiki.LIMITES"), LIMITES)
        self.assertTrue(self.page.evaluate("Object.isFrozen(Wiki.LIMITES) && Object.isFrozen(Wiki.LIMITES['équipement'].rubriques)"))
        self.assertEqual(sorted(self.page.evaluate("Object.keys(Wiki.RUBRIQUES)")), sorted(LIMITES))
        self.assertEqual((SEUILS["phrasesMax"], SEUILS["motsMax"]),
                         (LIMITES["savoir-faire"]["page"]["phrases"], LIMITES["savoir-faire"]["page"]["mots"]))
        absents = self.page.evaluate("""() => ['controlerSynthese', 'afficherSynthese', 'enregistrer', 'requetesDemo',
          'donneesSynthese', 'ETATS_SYNTHESE'].filter((nom) => nom in Wiki)""")
        self.assertEqual(absents, [])
        self.assertFalse(self.page.evaluate("'syntheseWiki' in Ia.PROMPTS"))
        page = self.page.evaluate("Wiki.page('EQ-0001')")
        self.assertEqual((page["id"], page["type"]), ("EQ-0001", "équipement"))
        self.assertEqual(page["calcul"], self.page.evaluate("Wiki.pageEquipement('EQ-0001')"))
        self.assertIsNone(self.page.evaluate("Wiki.page('EQ-9999')"))
        # Encyclopédie (§20.12, T135) : wiki-entites.js chargé par l'application ; sans profil donné, celui de l'application
        # (ici un technicien, qui ouvre la page d'un technicien), le demandeur non.
        entite = self.page.evaluate("Wiki.entite('EQ-0001')")
        self.assertEqual((entite["id"], entite["type"], entite["liens"]["technicien"]), ("EQ-0001", "machine", True))
        self.assertEqual(self.page.evaluate("Wiki.entite('TEC-0001').type"), "technicien")
        self.assertIsNone(self.page.evaluate("Wiki.entite('TEC-0001', { profil: 'demandeur' })"))
        self.assertTrue(self.page.evaluate("Wiki.listeEntites('panne').every((panne) => panne.id.startsWith('PANNE-'))"))

    def test_demo_au_format_3_et_export_zip(self):
        self.ouvrir_demo("responsable")
        self.assertEqual(self.page.evaluate("Donnees.parametre('version_schema')"), "3")
        self.assertEqual(self.page.evaluate("Schema.version"), 3)
        self.assertEqual(self.page.evaluate("Schema.nomsTables().slice(-2)"), ["wiki_pages", "wiki_journal"])
        # Depuis T139 (D119), la démo a son wiki figé : autant de lignes que les CSV de donnees/demo.
        for table in ("wiki_pages", "wiki_journal"):
            texte = (DOSSIER_DEMO / (table + ".csv")).read_bytes().decode("utf-8-sig")
            attendu = len(list(csv.reader(io.StringIO(texte, newline=""), delimiter=";"))) - 1   # sans l'en-tête
            self.assertEqual(self.page.evaluate("Donnees.lignes('%s').length" % table), attendu, table)
            self.assertGreater(attendu, 0, table)
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
                    # L'export porte l'en-tête du schéma puis les lignes du wiki figé de la démo (T139).
                    contenu = archive.read(nom)
                    self.assertTrue(contenu.startswith(BOM + entete), nom)
                    lignes = list(csv.reader(io.StringIO(contenu.decode("utf-8-sig"), newline=""), delimiter=";"))
                    attendu = (DOSSIER_DEMO / nom).read_bytes().decode("utf-8-sig")
                    self.assertEqual(len(lignes), len(list(csv.reader(io.StringIO(attendu, newline=""), delimiter=";"))))
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
