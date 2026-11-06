"""Chantier multilingue, Lot 4 — langue du navigateur sans réglage, avertissement de la démo (T299 ; D150 ; ARCHITECTURE.md §24.11).

Dans Chromium, la démo (index.html en file://, bouton « Essayer avec des données de démonstration »), sauf mention :
    - sans réglage (ni choix du poste, ni langue d'installation retenue), la démo prend la langue du navigateur :
      en-US → anglais ; fr-CA → français ; de-DE (langue non déclarée) → anglais ; pt-BR → anglais aujourd'hui
      (pt-PT n'est pas déclaré) ;
    - I18n.langueDuNavigateur (fonction pure) : liste dans l'ordre, code exact puis langue sans région, toute variante
      du portugais (pt-BR…) ramenée à pt-PT quand pt-PT est déclaré, sinon l'anglais ;
    - un choix du poste (« prevo.langue ») l'emporte ; une langue d'installation connue (« prevo.langue.installation »)
      l'emporte sur la langue du navigateur ;
    - avertissement : changer de langue dans la démo (« Ce poste » et pied du menu) demande d'abord confirmation ;
      Annuler garde la langue, la page (rien n'est rechargé, les modifications restent) et remet la liste sur la
      langue actuelle ; Confirmer recharge la page dans la nouvelle langue ;
    - hors démo (serveur.py), aucun avertissement : la page se recharge aussitôt.
Les textes attendus sont lus dans js/i18n/fr.js et js/i18n/en.js, pas par le moteur.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_langue_navigateur.py" -v
"""
import unittest

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, url_fichier
from test_langue_installation import CHOIX_UNE_FOIS_JS, texte_du_dictionnaire

CLE = "socle.selecteur_langue.recharge_demo"
LISTE_POSTE = "#poste-langue-liste"
LISTE_MENU = "#menu-langue-liste"
ETAT_JS = """() => ({ langue: I18n.langue, lang: document.documentElement.lang,
  poste: localStorage.getItem('prevo.langue'), mode: App.mode })"""


class TestLangueNavigateur(CasNavigateur):

    def setUp(self):
        super().setUp()
        self.chargements = 0
        self.page.on("load", self._compter)

    def _compter(self, _page):
        self.chargements += 1

    def nouveau_poste(self, locale, script=None):
        """Remplace le contexte du test par un navigateur de la langue `locale` (script d'initialisation facultatif)."""
        self.contexte.close()
        self.contexte = self.navigateur.new_context(locale=locale, viewport={"width": 1280, "height": 800})
        self.contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        preregler_profil(self.contexte, "responsable")
        if script:
            self.contexte.add_init_script(script)
        self.page = self.contexte.new_page()
        self.surveiller(self.page)
        self.chargements = 0
        self.page.on("load", self._compter)

    def ouvrir_demo(self, locale, script=None):
        self.nouveau_poste(locale, script)
        self.page.goto(url_fichier("index.html"))
        self.page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        return self.page.evaluate(ETAT_JS)

    def ouvrir_poste(self):
        self.page.evaluate("location.hash = '#/poste'")
        self.page.wait_for_selector(LISTE_POSTE)

    # -- langue sans réglage ---------------------------------------------------------------------

    def test_langue_du_navigateur_a_la_demo(self):
        for locale, attendue in (("en-US", "en"), ("fr-CA", "fr"), ("de-DE", "en"), ("pt-BR", "en")):
            with self.subTest(locale=locale):
                etat = self.ouvrir_demo(locale)
                self.assertEqual((etat["langue"], etat["lang"], etat["poste"], etat["mode"]),
                                 (attendue, attendue, None, "demo"))

    def test_fonction_pure(self):
        self.page.goto(url_fichier("index.html"))
        self.page.wait_for_function("typeof I18n !== 'undefined'")
        cas = self.page.evaluate("""() => {
          const f = (liste) => I18n.langueDuNavigateur(liste);
          const avant = [f(['en-US']), f(['fr-CA', 'en']), f(['de-DE', 'fr']), f(['de-DE', 'it']), f([]), f(undefined),
            f(['pt-BR']), f(['EN-gb'])];
          I18n.declarer({ code: 'pt-PT', nom: 'Português', locale: 'pt-PT', statut: 'automatique' });
          const apres = [f(['pt-BR']), f(['pt']), f(['pt-PT']), f(['de', 'pt-BR', 'fr']), f(['pt_BR'])];
          return { avant, apres, installation: I18n.langueAAfficher('', '', ['pt-BR']),
                   poste: I18n.langueAAfficher('fr', 'en', ['pt-BR']), sans: I18n.langueAAfficher('', '') };
        }""")
        self.assertEqual(cas["avant"], ["en", "fr", "fr", "en", "en", "en", "en", "en"])
        self.assertEqual(cas["apres"], ["pt-PT", "pt-PT", "pt-PT", "pt-PT", "pt-PT"])
        self.assertEqual((cas["installation"], cas["poste"], cas["sans"]), ("pt-PT", "fr", "fr"))

    def test_choix_du_poste_l_emporte(self):
        etat = self.ouvrir_demo("en-US", CHOIX_UNE_FOIS_JS % "localStorage.setItem('prevo.langue', 'fr');")
        self.assertEqual((etat["langue"], etat["poste"]), ("fr", "fr"))

    def test_langue_d_installation_connue_l_emporte(self):
        script = CHOIX_UNE_FOIS_JS % "localStorage.setItem('prevo.langue.installation', 'fr');"
        etat = self.ouvrir_demo("en-US", script)
        self.assertEqual((etat["langue"], etat["poste"]), ("fr", None))
        script = CHOIX_UNE_FOIS_JS % "localStorage.setItem('prevo.langue.installation', 'en');"
        etat = self.ouvrir_demo("fr-FR", script)
        self.assertEqual(etat["langue"], "en")

    # -- avertissement avant de changer de langue dans la démo ----------------------------------

    def test_demo_annuler_garde_la_langue_et_la_page(self):
        self.ouvrir_demo("fr-FR")
        self.ouvrir_poste()
        self.page.evaluate("window.__marque = 42")
        chargements = self.chargements
        self.page.select_option(LISTE_POSTE, "en")
        dialogue = self.page.locator("dialog[open]")
        dialogue.wait_for()
        self.assertIn(texte_du_dictionnaire("fr", CLE), dialogue.inner_text())
        self.assertIsNone(self.page.evaluate("localStorage.getItem('prevo.langue')"))
        dialogue.get_by_role("button", name=texte_du_dictionnaire("fr", "commun.bouton.annuler")).click()
        self.page.locator("dialog[open]").wait_for(state="detached")
        self.page.wait_for_timeout(800)
        self.assertEqual(self.chargements, chargements)
        self.assertEqual(self.page.evaluate("window.__marque"), 42)
        self.assertEqual(self.page.input_value(LISTE_POSTE), "fr")
        self.assertEqual(self.page.evaluate(ETAT_JS)["langue"], "fr")
        self.assertIsNone(self.page.evaluate("localStorage.getItem('prevo.langue')"))

    def test_demo_confirmer_recharge_dans_la_nouvelle_langue(self):
        self.ouvrir_demo("fr-FR")
        self.ouvrir_poste()
        self.page.select_option(LISTE_POSTE, "en")
        dialogue = self.page.locator("dialog[open]")
        dialogue.wait_for()
        with self.page.expect_navigation():
            dialogue.get_by_role("button", name=texte_du_dictionnaire("fr", "socle.selecteur_langue.changer")).click()
        self.page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        self.assertEqual(self.page.evaluate("[I18n.langue, localStorage.getItem('prevo.langue')]"), ["en", "en"])

    def test_demo_avertissement_au_pied_du_menu_en_anglais(self):
        self.ouvrir_demo("en-US")
        self.page.wait_for_selector(LISTE_MENU, state="attached")
        self.page.evaluate("""() => { const l = document.querySelector('#menu-langue-liste'); l.value = 'fr';
          l.dispatchEvent(new Event('change', { bubbles: true })); }""")
        dialogue = self.page.locator("dialog[open]")
        dialogue.wait_for()
        self.assertIn(texte_du_dictionnaire("en", CLE), dialogue.inner_text())
        dialogue.get_by_role("button", name=texte_du_dictionnaire("en", "commun.bouton.annuler")).click()
        self.page.locator("dialog[open]").wait_for(state="detached")
        self.assertEqual(self.page.eval_on_selector(LISTE_MENU, "l => l.value"), "en")
        self.assertEqual(self.page.evaluate(ETAT_JS)["langue"], "en")

    def test_hors_demo_pas_d_avertissement(self):
        with ServeurPrevo() as serveur:
            preregler_profil(self.contexte, "responsable")
            self.page.goto(serveur.url + "/#/poste")
            attendre_pret(self.page)
            self.page.wait_for_selector(LISTE_POSTE)
            with self.page.expect_navigation():
                self.page.select_option(LISTE_POSTE, "en")
            attendre_pret(self.page)
            self.assertEqual(self.page.locator("dialog[open]").count(), 0)
            self.assertEqual(self.page.evaluate(ETAT_JS)["langue"], "en")


if __name__ == "__main__":
    unittest.main()
