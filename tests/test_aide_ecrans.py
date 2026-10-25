"""Aide à l'écran : encart d'explication à la première visite de chaque écran (ARCHITECTURE.md §23 ; décision de
Nicolas du 2026-10-25, démo et version installée).

Ce qui est vérifié :
    textes        chaque entrée vise un écran enregistré par un module et une ancre de GUIDE.html ; chaque variante a
                  son texte et son geste ; À propos n'a pas d'entrée ;
    première fois l'encart est en tête du contenu, après l'en-tête, non bloquant ; « Compris » le retire et le retient ;
                  la visite suivante n'affiche rien ; Échap ferme sans retenir ;
    profils       l'accueil change de texte avec le profil ; la page du wiki a la variante du demandeur ;
    héritage      un formulaire sans entrée prend celle de son parent ; rien sur À propos ;
    Ce poste      la case coupe l'aide ; « Revoir toutes les explications » la remet ; le lien « Explications » du menu
                  rouvre l'encart de l'écran courant ;
    sans mémoire  localStorage refusé : l'encart s'affiche, aucune erreur JavaScript ;
    démo web      la phrase de la démo est en tête de l'accueil et dans le journal du wiki.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_aide_ecrans.py" -v
"""
import json
import re
import unittest

from commun import RACINE, CasNavigateur, ServeurStatique, attendre_pret, preregler_profil, url_fichier
from test_version_web import demo_web_construite

TEXTES = RACINE / "js" / "modules" / "aide-ecrans-textes.js"
ENCART = "#aide-ecran"


def lire_textes():
    contenu = TEXTES.read_text(encoding="utf-8")
    debut = contenu.index("const AideEcransTextes = ") + len("const AideEcransTextes = ")
    return json.loads(contenu[debut:contenu.rindex(";")])


def ecrans_enregistres():
    """Identifiants des écrans déclarés par App.ecran dans les modules."""
    ids = set()
    for chemin in (RACINE / "js" / "modules").glob("*.js"):
        ids.update(re.findall(r"App\.ecran\(\{\s*id: '([a-z-]+)'", chemin.read_text(encoding="utf-8")))
    return ids


class TestTextes(unittest.TestCase):

    def test_textes_ecrans_ancres_et_variantes(self):
        textes = lire_textes()
        ecrans = ecrans_enregistres()
        guide = (RACINE / "GUIDE.html").read_text(encoding="utf-8")
        self.assertNotIn("apropos", textes)
        self.assertGreaterEqual(len(textes), 28)
        for id_ecran, entree in textes.items():
            with self.subTest(ecran=id_ecran):
                self.assertIn(id_ecran, ecrans)
                self.assertIn('id="%s"' % entree["ancre"], guide)
                self.assertTrue(entree["titre"])
                variantes = entree["profils"].values() if "profils" in entree else [entree]
                for variante in variantes:
                    self.assertTrue(variante["texte"].strip())
                    self.assertTrue(variante["essayez"].strip())
        self.assertEqual(set(textes["wiki-page"]["profils"]), {"responsable", "technicien", "demandeur"})
        self.assertEqual(textes["wiki-page"]["profils"]["demandeur"]["essayez"], "cherchez votre machine.")
        self.assertIn("démo", textes["accueil"]["demo"])
        self.assertIn("démo", textes["wiki-journal"]["demo"])


class CasAide(CasNavigateur):
    AIDE_ECRANS = True

    def ouvrir(self, profil="responsable", **options):
        preregler_profil(self.contexte, profil, **options)
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        return self.page

    def aller(self, route, selecteur="#contenu > *"):
        self.page.evaluate("(route) => { location.hash = route; }", route)
        self.page.wait_for_function("(route) => location.hash === route", arg=route)
        self.page.wait_for_selector(selecteur)

    def encart_visible(self):
        return self.page.locator(ENCART).count() == 1 and self.page.is_visible(ENCART)

    def texte_encart(self):
        return self.page.text_content(ENCART)


class TestPremiereVisite(CasAide):

    def test_accueil_compris_retenu_puis_absent(self):
        page = self.ouvrir()
        page.wait_for_selector(ENCART)
        self.assertIn("Votre tableau de bord", self.texte_encart())
        self.assertIn("Essayez :", self.texte_encart())
        self.assertEqual(page.get_attribute(ENCART, "role"), "status")
        # en tête du contenu, juste après l'en-tête de page s'il existe
        place = page.evaluate("""() => {
            const e = document.querySelector('#aide-ecran');
            const precedent = e.previousElementSibling;
            return { parent: e.parentElement.id, precedent: precedent ? precedent.className : '' };
        }""")
        self.assertEqual(place["parent"], "contenu")
        self.assertTrue(place["precedent"] in ("", "entete-page") or "entete-page" in place["precedent"], place)
        lien = page.locator(ENCART + " a.aide-ecran-guide")
        self.assertEqual(lien.get_attribute("href"), "GUIDE.html#accueil")
        self.assertEqual(lien.get_attribute("target"), "_blank")
        # non bloquant : un lien du contenu reste cliquable
        page.click(ENCART + " .aide-ecran-compris")
        self.assertEqual(page.locator(ENCART).count(), 0)
        self.assertEqual(page.evaluate("JSON.parse(localStorage.getItem('prevo.aideVue'))"), ["accueil"])
        self.aller("#/parc")
        page.wait_for_selector(ENCART)
        self.assertIn("arborescence", self.texte_encart())
        self.aller("#/accueil")
        page.wait_for_timeout(200)
        self.assertEqual(page.locator(ENCART).count(), 0)

    def test_echap_ferme_sans_retenir(self):
        page = self.ouvrir()
        page.wait_for_selector(ENCART)
        page.focus(ENCART + " .aide-ecran-compris")
        page.keyboard.press("Escape")
        self.assertEqual(page.locator(ENCART).count(), 0)
        self.assertIsNone(page.evaluate("localStorage.getItem('prevo.aideVue')"))
        self.aller("#/parc")
        self.aller("#/accueil")
        page.wait_for_selector(ENCART)

    def test_heritage_du_parent_et_rien_sur_a_propos(self):
        page = self.ouvrir()
        page.wait_for_selector(ENCART)
        page.click(ENCART + " .aide-ecran-compris")
        self.aller("#/ot/nouveau")
        page.wait_for_selector(ENCART)
        self.assertIn("Tous les ordres de travail", self.texte_encart())
        self.assertEqual(page.get_attribute(ENCART, "data-ecran"), "liste-ot")
        page.click(ENCART + " .aide-ecran-compris")
        self.aller("#/ot")
        page.wait_for_timeout(200)
        self.assertEqual(page.locator(ENCART).count(), 0)
        self.aller("#/apropos")
        page.wait_for_timeout(200)
        self.assertEqual(page.locator(ENCART).count(), 0)


class TestProfils(CasAide):

    def test_accueil_du_technicien(self):
        page = self.ouvrir("technicien", nom="Julien Moreau", technicien_id="TEC-0001")
        page.wait_for_selector(ENCART)
        self.assertIn("Vos ordres de travail ouverts", self.texte_encart())

    def test_accueil_et_page_du_wiki_du_demandeur(self):
        page = self.ouvrir("demandeur", nom="Lucie Martin")
        page.wait_for_selector(ENCART)
        self.assertIn("Vos demandes d'intervention", self.texte_encart())
        page.click(ENCART + " .aide-ecran-compris")
        self.aller("#/wiki/machines")
        page.wait_for_selector(ENCART)
        self.assertEqual(page.get_attribute(ENCART, "data-ecran"), "wiki-liste")
        page.click(ENCART + " .aide-ecran-compris")
        page.click("#contenu a[href^='#/wiki/']:not([href$='/machines'])")
        page.wait_for_function(r"!/^#\/wiki\/(machines|pannes|articles|techniciens|savoir-faire|interventions)$/.test(location.hash)")
        page.wait_for_selector(ENCART)
        self.assertIn("donnent la date de l'intervention citée", self.texte_encart())
        self.assertIn("cherchez votre machine", self.texte_encart())


class TestCePoste(CasAide):

    def test_case_revoir_et_lien_explications(self):
        page = self.ouvrir()
        page.wait_for_selector(ENCART)
        page.click(ENCART + " .aide-ecran-compris")
        self.aller("#/poste", "#carte-aide")
        page.wait_for_selector(ENCART)
        page.click(ENCART + " .aide-ecran-compris")
        self.assertTrue(page.is_checked("#poste-aide-active"))
        page.uncheck("#poste-aide-active")
        self.assertEqual(page.evaluate("localStorage.getItem('prevo.aideActive')"), "0")
        self.aller("#/parc")
        page.wait_for_timeout(200)
        self.assertEqual(page.locator(ENCART).count(), 0)
        # « Explications » rouvre l'encart de l'écran courant, même aide coupée
        page.click("#btn-explications")
        page.wait_for_selector(ENCART)
        self.assertEqual(page.get_attribute(ENCART, "data-ecran"), "parc")
        page.click(ENCART + " .aide-ecran-compris")
        # « Revoir toutes les explications » : liste vidée, aide remise
        self.aller("#/poste", "#carte-aide")
        page.click("#btn-revoir-aide")
        self.assertTrue(page.is_checked("#poste-aide-active"))
        self.assertIsNone(page.evaluate("localStorage.getItem('prevo.aideVue')"))
        self.aller("#/accueil")
        page.wait_for_selector(ENCART)

    def test_telephone_bouton_explications(self):
        page = self.ouvrir()
        page.set_viewport_size({"width": 375, "height": 800})
        page.wait_for_selector(ENCART)
        page.click(ENCART + " .aide-ecran-compris")
        self.assertTrue(page.is_visible("#btn-explications-mobile"))
        page.click("#btn-explications-mobile")
        page.wait_for_selector(ENCART)
        largeur = page.evaluate("document.documentElement.scrollWidth")
        self.assertLessEqual(largeur, 375)


class TestSansMemoire(CasAide):

    def test_localstorage_refuse(self):
        self.contexte.add_init_script("""
            Object.defineProperty(window, 'localStorage', { get() { throw new Error('stockage refusé'); } });
        """)
        page = self.page
        page.goto(url_fichier("index.html"))
        page.click("#btn-demo")
        page.wait_for_function("document.documentElement.dataset.etat === 'profil'")
        page.click("#profil-responsable")
        attendre_pret(page)
        page.wait_for_selector(ENCART)
        page.click(ENCART + " .aide-ecran-compris")
        self.assertEqual(page.locator(ENCART).count(), 0)


class TestDemoWeb(CasAide):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        sortie, resultat = demo_web_construite()
        cls.sortie = sortie if resultat.returncode == 0 else None
        cls.statique = ServeurStatique(sortie if cls.sortie else RACINE)
        cls.statique.demarrer()
        cls.addClassCleanup(cls.statique.arreter)

    def test_phrase_de_la_demo(self):
        self.assertIsNotNone(self.sortie, "construction de la démo web en échec")
        preregler_profil(self.contexte, "responsable", "Responsable")
        page = self.page
        page.goto(self.statique.url + "/index.html")
        page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        page.click("#btn-demo")
        attendre_pret(page)
        page.wait_for_selector(ENCART)
        self.assertTrue(self.texte_encart().strip().startswith("Vous êtes dans la démo"))
        page.click(ENCART + " .aide-ecran-compris")
        self.aller("#/wiki-journal")
        page.wait_for_selector(ENCART)
        self.assertIn("l'assistant IA est coupé", self.texte_encart())


if __name__ == "__main__":
    unittest.main()
