"""Chantier multilingue, Lot 4 — rapport mensuel figé dans la langue choisie au moment de le figer (T302 ; D160, CS156, D156).

Mode démo (file://, profil responsable), installation en français (la démo n'a pas de langue_defaut) :
    - écran en français, « Langue du rapport » = Français par défaut (celle de l'installation) ; English choisi :
      document enregistré en anglais (titre, mois « September », nombres au format en-GB, lang="en", lien du courriel) alors
      que l'écran reste en français ; son dictionnaire n'était PAS chargé : il l'est à la demande ;
    - rien choisi : document en français, lang="fr", nombres à la française ;
    - écran en anglais, installation française : la langue proposée est le français, document en français ;
    - I18n.chargerLangue : langue chargée = rien à faire, langue inconnue = refus clair ; I18n.enLangue refuse un
      dictionnaire non chargé et les fonctions asynchrones, et rend la langue de l'écran.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_rapport_langue.py" -v
"""
import re
import unittest
import urllib.parse

from commun import CasNavigateur, attendre_pret, preregler_profil, url_fichier

DOCUMENT_JS = "async (nom) => (await App.adaptateur.lireDocument(nom)).text()"
SCRIPT_EN_JS = "document.querySelectorAll('script[src$=\"i18n/en.js\"]').length"
NOMS_MOIS = {"fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
                    "novembre", "décembre"],
             "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
                    "November", "December"]}


class TestRapportLangue(CasNavigateur):

    def setUp(self):
        super().setUp()
        preregler_profil(self.contexte, "responsable")
        self.cles_absentes = []
        self.page.on("console", lambda message: self.cles_absentes.append(message.text)
                     if message.type == "warning" and "(traduction)" in message.text else None)

    # -- outils ---------------------------------------------------------------------------------

    def ouvrir_demo(self, ecran):
        page = self.page
        page.goto(url_fichier("index.html"))
        if ecran != "fr":
            page.evaluate("(code) => localStorage.setItem('prevo.langue', code)", ecran)
            page.reload()
        page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        page.click("#btn-demo")
        attendre_pret(page)
        self.assertEqual(page.evaluate("[I18n.langue, I18n.installation]"), [ecran, "fr"])

    def ouvrir_onglet(self):
        self.page.evaluate("Rapport.afficherOnglet(document.querySelector('#contenu'))")
        self.page.wait_for_selector("#rapports-langue")
        return self.page.evaluate("Rapport.moisAProposer(Donnees.aujourdhui())")

    def figer(self, mois, langue=None):
        """Fige depuis le formulaire (langue choisie si donnée) ; rend le document enregistré."""
        page = self.page
        if langue:
            page.select_option("#rapports-langue", langue)
        page.select_option("#rapports-mois", mois)
        page.click(".rapports-formulaire button[type=submit]")
        nom = "rapport-mensuel-%s.html" % mois
        page.wait_for_function("(nom) => App.adaptateur.documentsEnMemoire().some((d) => d.nom === nom)", arg=nom)
        page.wait_for_function("document.querySelector('#rapports-message').textContent.trim() !== ''")
        return page.evaluate(DOCUMENT_JS, nom)

    def libelle_mois(self, mois, langue):
        return NOMS_MOIS[langue][int(mois[5:7]) - 1] + " " + mois[:4]

    def titre(self, mois, langue):
        return self.page.evaluate("([cle, valeurs, langue]) => I18n.enLangue(langue, () => I18n.t(cle, valeurs))",
                                  ["rapport.texte_courriel.rapport_mensuel_maintenance_2",
                                   {"libelleMois": self.libelle_mois(mois, langue)}, langue])

    def valeurs_des_tuiles(self, document):
        valeurs = re.findall(r'<div class="val">([^<]*)</div>', document)
        self.assertEqual(len(valeurs), 4)                   # 2.2 (T472) : 4ᵉ tuile, le coût de l'arrêt
        return valeurs

    # -- tests ----------------------------------------------------------------------------------

    def test_ecran_francais_rapport_fige_en_anglais(self):
        self.ouvrir_demo("fr")
        # English n'est pas chargé : il l'est à la demande au moment de figer.
        self.assertEqual(self.page.evaluate(SCRIPT_EN_JS), 0)
        mois = self.ouvrir_onglet()
        self.assertTrue(mois)
        options = self.page.evaluate("[...document.querySelectorAll('#rapports-langue option')].map((o) => [o.value, o.textContent])")
        self.assertEqual(options, [["fr", "Français"], ["en", "English"], ["tr", "Türkçe"], ["it", "Italiano"],
                                   ["pt-PT", "Português"]])                     # Lot 5 (T375)
        self.assertEqual(self.page.input_value("#rapports-langue"), "fr")           # proposée : langue de l'installation
        document = self.figer(mois, "en")
        self.assertEqual(self.page.evaluate(SCRIPT_EN_JS), 1)
        self.assertIn('<html lang="en">', document)
        self.assertIn("<h1>%s</h1>" % self.titre(mois, "en"), document)
        self.assertIn(self.libelle_mois(mois, "en"), document)                     # « September 2026 »
        self.assertNotIn(self.libelle_mois(mois, "fr"), document)
        # Nombres en-GB : point décimal, jamais « 92,4 ».
        for valeur in self.valeurs_des_tuiles(document):
            with self.subTest(valeur=valeur):
                self.assertIsNone(re.search(r"\d,\d(?!\d{2})", valeur))
        courriel = re.search(r'mailto:\?subject=([^&"]*)', document)
        self.assertIsNotNone(courriel)
        self.assertIn(self.libelle_mois(mois, "en"), urllib.parse.unquote(courriel.group(1)))
        for cle in ("rapport.html.faits_marquants", "rapport.html.comprendre"):
            with self.subTest(cle=cle):
                anglais = self.page.evaluate("(cle) => I18n.enLangue('en', () => I18n.t(cle))", cle)
                francais = self.page.evaluate("(cle) => I18n.reference(cle)", cle)
                self.assertNotEqual(anglais, francais)
                self.assertIn(anglais, document)
                self.assertNotIn(francais, document)
        # L'écran est resté en français.
        self.assertEqual(self.page.evaluate("[I18n.langue, I18n.locale, document.documentElement.lang]"), ["fr", "fr-FR", "fr"])
        self.assertEqual(self.cles_absentes, [])

    def test_rien_choisi_langue_de_l_installation(self):
        self.ouvrir_demo("fr")
        mois = self.ouvrir_onglet()
        document = self.figer(mois)
        self.assertIn('<html lang="fr">', document)
        self.assertIn("<h1>%s</h1>" % self.titre(mois, "fr"), document)
        self.assertIn(self.libelle_mois(mois, "fr"), document)
        self.assertEqual(self.page.evaluate(SCRIPT_EN_JS), 0)
        for valeur in self.valeurs_des_tuiles(document):
            with self.subTest(valeur=valeur):
                self.assertIsNone(re.search(r"\d\.\d", valeur))

    def test_ecran_anglais_installation_francaise_proposee_en_francais(self):
        self.ouvrir_demo("en")
        mois = self.ouvrir_onglet()
        self.assertEqual(self.page.input_value("#rapports-langue"), "fr")
        self.assertEqual(self.page.inner_text("label[for=rapports-langue]").strip(), "Report language")
        document = self.figer(mois)
        self.assertIn('<html lang="fr">', document)
        self.assertIn("<h1>%s</h1>" % self.titre(mois, "fr"), document)
        self.assertIn(self.libelle_mois(mois, "fr"), document)
        self.assertEqual(self.page.evaluate("[I18n.langue, I18n.locale]"), ["en", "en-GB"])
        self.assertEqual(self.cles_absentes, [])

    def test_moteur_chargement_a_la_demande(self):
        self.ouvrir_demo("fr")
        page = self.page
        self.assertEqual(page.evaluate("I18n.enLangue('fr', () => I18n.locale)"), "fr-FR")
        erreur = page.evaluate("() => { try { I18n.enLangue('en', () => 1); return ''; } catch (e) { return e.message; } }")
        self.assertIn("non chargé", erreur)                              # dictionnaire absent : refus, pas de repli
        erreur = page.evaluate("async () => { try { await I18n.chargerLangue('zz'); return ''; } catch (e) { return e.message; } }")
        self.assertIn("non déclarée", erreur)
        self.assertEqual(page.evaluate("""async () => {
          await I18n.chargerLangue('en'); await I18n.chargerLangue('en');          // deuxième appel : rien à faire
          return [document.querySelectorAll('script[src$="i18n/en.js"]').length, I18n.enLangue('en', () => I18n.locale)];
        }"""), [1, "en-GB"])
        erreur = page.evaluate("() => { try { I18n.enLangue('en', async () => 1); return ''; } catch (e) { return e.message; } }")
        self.assertIn("synchrone", erreur)
        self.assertEqual(page.evaluate("I18n.langue"), "fr")                 # la langue de l'écran est revenue


if __name__ == "__main__":
    unittest.main()
