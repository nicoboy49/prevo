"""Le principe de la 2.2 en un seul endroit (D182, CS175 ; T490) : « Prévo est une aide au suivi ; la responsabilité
reste celle de l'employeur. » figure dans les écrans Contrôles, Habilitations (Équipe) et Garanties et contrats, dans
le guide et dans les deux README, et aucun texte ne dit « conforme ».

Sans navigateur (TestPhraseEtMotInterdit) :
  - la valeur française des clés controles.principe.texte, equipe.principe.texte et garanties.principe.texte est la
    phrase, mot pour mot ; chacune de ces clés est utilisée par les modules d'écran de son domaine ;
  - GUIDE.html (texte visible, entités décodées), README.md et README.fr.md contiennent la phrase ;
  - ni js/i18n/fr.js, ni js/i18n/aide/fr.js (valeurs, pas clés), ni GUIDE.html, ni les README ne contiennent le mot
    « conforme » ou « conformes » (mot entier ; « non-conforme », « conformité » ne sont pas visés).
En démo (TestEcransPrincipe, profil Responsable) : la phrase est affichée sur la liste des contrôles, la fiche d'un
technicien (carte Habilitations) et, pour Garanties et contrats, la liste et les deux fiches (les trois écrans de D182).

Lancer depuis la racine du projet (la partie navigateur au travers du verrou) :
    py -X utf8 -m unittest discover -s tests -p "test_principe_d182.py" -v
"""
import html
import re
import sys
import unittest

from commun import RACINE
from test_principe_suivi import CasDemoResponsable, MOT_CONFORME, PHRASE

if str(RACINE / "outils") not in sys.path:
    sys.path.insert(0, str(RACINE / "outils"))
import textes_langues  # noqa: E402
from jslex import decoder  # noqa: E402

CLES = {"controles.principe.texte": ["controles-catalogue.js", "controles-ecrans.js"],
        "equipe.principe.texte": ["equipe-ecrans.js", "equipe-habilitations.js"],
        "garanties.principe.texte": ["garanties-ecrans.js"]}
DOCUMENTS = ["GUIDE.html", "README.md", "README.fr.md"]


def texte_visible(chemin):
    """Texte d'une page HTML sans balises, scripts ni styles, entités décodées, espaces normalisés."""
    brut = (RACINE / chemin).read_text(encoding="utf-8")
    brut = re.sub(r"<(script|style)\b.*?</\1>", " ", brut, flags=re.S | re.I)
    brut = re.sub(r"<[^>]+>", " ", brut)
    return re.sub(r"\s+", " ", html.unescape(brut))


def normaliser(texte):
    return re.sub(r"\s+", " ", html.unescape(texte).replace(" ", " "))


def valeurs_fr():
    entrees = textes_langues.Langue("fr", RACINE, textes_langues.fichiers_de("fr")).entrees
    return {cle: [decoder(brute) for brute in (valeur.values() if isinstance(valeur, dict) else [valeur])]
            for cle, (_, valeur, _) in entrees.items()}


class TestPhraseEtMotInterdit(unittest.TestCase):

    def test_la_phrase_est_la_meme_dans_les_trois_domaines(self):
        francais = valeurs_fr()
        for cle in CLES:
            with self.subTest(cle=cle):
                self.assertEqual(francais[cle], [PHRASE])

    def test_chaque_domaine_affiche_sa_phrase(self):
        for cle, modules in CLES.items():
            for module in modules:
                with self.subTest(cle=cle, module=module):
                    source = (RACINE / "js" / "modules" / module).read_text(encoding="utf-8")
                    self.assertIn("I18n.t('%s')" % cle, source)

    def test_la_phrase_est_dans_le_guide_et_les_deux_readme(self):
        for chemin in DOCUMENTS:
            with self.subTest(document=chemin):
                texte = texte_visible(chemin) if chemin.endswith(".html") else normaliser(
                    (RACINE / chemin).read_text(encoding="utf-8"))
                self.assertIn(PHRASE, texte)

    def test_le_guide_a_la_section_garanties(self):
        guide = (RACINE / "GUIDE.html").read_text(encoding="utf-8")
        self.assertEqual(guide.count('id="garanties"'), 1)
        self.assertIn('<a href="#garanties">', guide)

    def test_aucun_texte_ne_dit_conforme(self):
        francais = valeurs_fr()
        self.assertTrue(any(cle.startswith("aide.") for cle in francais), "aide longue (js/i18n/aide/fr.js) non lue")
        self.assertEqual(sorted(cle for cle, textes in francais.items()
                                if any(MOT_CONFORME.search(texte) for texte in textes)), [])
        for chemin in DOCUMENTS:
            with self.subTest(document=chemin):
                texte = texte_visible(chemin) if chemin.endswith(".html") else normaliser(
                    (RACINE / chemin).read_text(encoding="utf-8"))
                self.assertIsNone(MOT_CONFORME.search(texte))


class TestEcransPrincipe(CasDemoResponsable):
    """Démo, profil Responsable : la phrase est visible, une seule fois, sur chaque écran."""

    def verifier(self, nom, classe):
        with self.subTest(ecran=nom):
            phrases = self.page.eval_on_selector_all(
                "#contenu ." + classe,
                "elements => elements.filter((e) => e.getClientRects().length).map((e) => e.textContent.trim())")
            self.assertEqual(phrases, [PHRASE])
            self.assertIsNone(MOT_CONFORME.search(self.page.inner_text("#contenu")), "« conforme » sur " + nom)

    def test_phrase_sur_les_ecrans_des_trois_domaines(self):
        self.aller("#/controles", ".controles-liste a.controles-lien")
        self.verifier("contrôles, liste", "controles-principe")
        technicien = self.page.evaluate("() => Donnees.lignes('techniciens')[0].id")
        self.aller("#/equipe/" + technicien, "#contenu .equipe-carte-habilitations")
        self.verifier("habilitations, fiche d'un technicien", "equipe-principe")
        garantie, contrat = self.page.evaluate(
            "() => [Donnees.lignes('garanties')[0].id, Donnees.lignes('contrats_prestataires')[0].id]")
        for nom, route in (("liste", "#/garanties"),
                           ("fiche de garantie", "#/garanties/garantie/" + garantie),
                           ("fiche de contrat", "#/garanties/contrat/" + contrat)):
            self.aller(route, "#contenu .garanties-principe")
            self.verifier("garanties et contrats, " + nom, "garanties-principe")


if __name__ == "__main__":
    unittest.main()
