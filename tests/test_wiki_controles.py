"""Vocabulaire de la sécurité du wiki (D97, ARCHITECTURE.md §20.6) — socle du lot 6 refondu (T110).

    vocabulaire : chaque entrée de Wiki.VOCABULAIRE_SECURITE est trouvée par Wiki.termesDeSecurite (début de
                  mot pour les entrées finies par « * », mot entier sinon), avec accents et apostrophes réels ;
                  les faux amis (« épisodique », « Vatican », « soupape de sécurité »…) ne sont pas refusés.
    Les contrôles d'une proposition (§20.6) s'ajoutent à ce fichier avec T113.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_wiki_controles.py" -v
"""
import unittest

from commun import CasNavigateur, attendre_pret, preregler_profil, url_fichier


class TestVocabulaireDeSecurite(CasNavigateur):
    """Fonctions pures de wiki-regles.js, dans la démo (aucun fournisseur d'IA)."""

    def setUp(self):
        super().setUp()
        preregler_profil(self.contexte, "responsable")
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)

    def termes(self, texte):
        return self.page.evaluate("(t) => Wiki.termesDeSecurite(t)", texte)

    def test_vocabulaire_de_securite_chaque_entree_et_faux_amis(self):
        vocabulaire = self.page.evaluate("Wiki.VOCABULAIRE_SECURITE")
        self.assertTrue(self.page.evaluate("Object.isFrozen(Wiki.VOCABULAIRE_SECURITE)"))
        for entree in vocabulaire:
            mot = entree[:-1] + "ation" if entree.endswith("*") else entree
            with self.subTest(entree=entree):
                self.assertNotEqual(self.termes("Pendant l'intervention, %s du poste" % mot.upper()), [], entree)
        # Avec accents et apostrophes réelles.
        for phrase in ("Couper l'alimentation générale", "Vérifier l'absence de tension", "Porter des gants",
                       "Mise en sécurité de la machine", "Poser le cadenas", "Habilitation BR requise"):
            with self.subTest(phrase=phrase):
                self.assertNotEqual(self.termes(phrase), [])
        # Faux amis : rien ne doit être refusé.
        for phrase in ("Panne épisodique du capteur", "Retour du Vatican", "La soupape de sécurité fuit",
                       "Le pressostat de sécurité déclenche", "Graissage du portique (gantry)", "Épingle cassée"):
            with self.subTest(faux_ami=phrase):
                self.assertEqual(self.termes(phrase), [])

    def test_messages_de_refus_de_securite(self):
        self.assertEqual(self.page.evaluate("Wiki.MESSAGE_SECURITE_IA"),
                         "L'IA ne rédige jamais de consigne de sécurité : voir la consignation de l'équipement")
        self.assertTrue(self.page.evaluate("Wiki.MESSAGE_SECURITE_MAIN").startswith(
            "Le wiki ne contient pas de consigne de sécurité"))


if __name__ == "__main__":
    unittest.main()
