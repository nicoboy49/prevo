"""Le principe de la 2.2 (D182, CS175 ; T416, CONCEPTION-L2-L3 §1.1) : « Prévo est une aide au suivi ; la
responsabilité reste celle de l'employeur. », affiché sur les écrans concernés, et aucun texte qui dise « conforme ».

Sans navigateur (TestTextes) :
  - aucune valeur de js/i18n/fr.js ni de js/i18n/aide/fr.js ne contient le mot « conforme » ou « conformes » (mot
    entier, casse ignorée ; les clés, comme accueil.tuile_conformite.*, ne sont pas des textes) ;
  - aucune valeur de js/i18n/en.js ni de js/i18n/aide/en.js ne contient « compliant » (cinq langues dès chaque
    tâche : QUESTIONS-L2-L6, L2-L3 Q2 ; « compliance » du respect du préventif n'est pas visé) ;
  - la phrase est, mot pour mot, la valeur française de controles.principe.texte (une clé par domaine : la section
    commun est figée), traduite dans chaque langue déclarée.
En démo (TestEcransControles, index.html en file://, profil Responsable) : la phrase est affichée sur la liste
#/controles, sur le formulaire #/controles/nouveau (en saisie libre comme avec une ligne du catalogue choisie) et sur
la fiche d'un contrôle ; aucun de ces écrans ne dit « conforme », même avec la ligne C18 du catalogue choisie (son
résumé validé dit « équipement fixe conforme » : réponse provisoire n° 1, remplacé à l'affichage).
Les écrans Habilitations (T432) et Garanties et contrats (L4) s'ajouteront ici.

Bibliothèque standard + Playwright. Lancer depuis la racine du projet (au travers du verrou des navigateurs) :
    py -X utf8 -m unittest discover -s tests -p "test_principe_suivi.py" -v
"""
import re
import sys
import unittest

from commun import RACINE, CasNavigateur, attendre_pret, url_fichier

if str(RACINE / "outils") not in sys.path:
    sys.path.insert(0, str(RACINE / "outils"))
import textes_langues  # noqa: E402  (lecture des dictionnaires, celle de outils/controler_textes.py)
from jslex import decoder  # noqa: E402

PHRASE = "Prévo est une aide au suivi ; la responsabilité reste celle de l'employeur."
CLE_PHRASE = "controles.principe.texte"
MOT_CONFORME = re.compile(r"(?<![\w-])conformes?(?![\w-])", re.IGNORECASE)
MOT_COMPLIANT = re.compile(r"(?<![\w-])compliant(?![\w-])", re.IGNORECASE)
LANGUES = ["en", "tr", "it", "pt-PT"]


def valeurs(code):
    """{clé: [textes]} d'une langue (dictionnaire et aide longue), échappements décodés, pluriels dépliés."""
    entrees = textes_langues.Langue(code, RACINE, textes_langues.fichiers_de(code)).entrees
    return {cle: [decoder(brute) for brute in (valeur.values() if isinstance(valeur, dict) else [valeur])]
            for cle, (_, valeur, _) in entrees.items()}


def contenant(code, motif):
    return sorted(cle for cle, textes in valeurs(code).items() if any(motif.search(texte) for texte in textes))


class TestTextes(unittest.TestCase):

    def test_aucune_valeur_francaise_ne_dit_conforme(self):
        francais = valeurs("fr")
        self.assertGreater(len(francais), 1000, "dictionnaire français mal lu")
        self.assertTrue(any(cle.startswith("aide.") for cle in francais), "aide longue (js/i18n/aide/fr.js) non lue")
        self.assertEqual(contenant("fr", MOT_CONFORME), [])
        # Le motif reconnaît bien le mot, pas ses voisins.
        for texte, attendu in (("équipement conforme", True), ("Conformes à", True), ("conformité", False),
                               ("non-conforme", False), ("conformer", False)):
            with self.subTest(texte=texte):
                self.assertEqual(bool(MOT_CONFORME.search(texte)), attendu)

    def test_aucune_valeur_anglaise_ne_dit_compliant(self):
        self.assertEqual(contenant("en", MOT_COMPLIANT), [])
        self.assertTrue(MOT_COMPLIANT.search("fully compliant"))
        self.assertFalse(MOT_COMPLIANT.search("Preventive compliance"))

    def test_la_phrase_mot_pour_mot_dans_les_cinq_langues(self):
        self.assertEqual(valeurs("fr")[CLE_PHRASE], [PHRASE])
        self.assertEqual(textes_langues.Langue("fr", RACINE, textes_langues.fichiers_de("fr")).entrees[CLE_PHRASE][0],
                         "controles")
        for code in LANGUES:
            with self.subTest(langue=code):
                traduite = valeurs(code)[CLE_PHRASE]
                self.assertEqual(len(traduite), 1)
                self.assertNotEqual(traduite[0], PHRASE, "phrase restée en français")
        self.assertEqual(valeurs("en")[CLE_PHRASE],
                         ["Prévo is an aid to keeping track; responsibility remains with the employer."])


# Textes de l'écran : #contenu (titres, notes, formulaires, options des listes comprises).
TEXTE_JS = "() => document.querySelector('#contenu').innerText"


class TestEcransControles(CasNavigateur):
    """Démo, profil Responsable : liste, formulaire de création, fiche."""

    def setUp(self):
        super().setUp()
        page = self.page
        page.goto(url_fichier("index.html"))
        page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        page.click("#btn-demo")
        page.wait_for_function("document.documentElement.dataset.etat === 'profil'")
        page.click("#profil-responsable")
        attendre_pret(page)

    def aller(self, route, selecteur):
        self.page.evaluate("(route) => { location.hash = route; }", route)
        self.page.wait_for_selector(selecteur)

    def phrases(self):
        return self.page.eval_on_selector_all("#contenu .controles-principe",
                                              "elements => elements.filter((e) => e.getClientRects().length)"
                                              ".map((e) => e.textContent.trim())")

    def verifier_ecran(self, nom):
        with self.subTest(ecran=nom):
            self.assertEqual(self.phrases(), [PHRASE])
            texte = self.page.evaluate(TEXTE_JS)
            self.assertIn(PHRASE, texte)
            self.assertIsNone(MOT_CONFORME.search(texte), "« conforme » sur l'écran %s" % nom)

    def test_phrase_sur_les_ecrans_controles_et_jamais_conforme(self):
        self.aller("#/controles", ".controles-liste a.controles-lien")
        self.verifier_ecran("liste")
        self.aller("#/controles/nouveau", "#form-controle [name=catalogue_id]")
        self.verifier_ecran("formulaire, saisie libre")
        for ligne in ("C14", "C04", "C18"):
            self.page.select_option("#form-controle [name=catalogue_id]", ligne)
            self.page.wait_for_selector("#form-controle .controles-catalogue-encart:not([hidden])")
            self.verifier_ecran("formulaire, %s choisie" % ligne)
        identifiant = self.page.evaluate("() => Donnees.lignes('controles_reglementaires')[0].id")
        self.aller("#/controles/" + identifiant, "#contenu .controles-source")
        self.verifier_ecran("fiche")


if __name__ == "__main__":
    unittest.main()
