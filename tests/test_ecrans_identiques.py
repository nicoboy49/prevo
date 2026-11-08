"""Chantier i18n, Lot 2 — l'écran ne change en rien (critère CS148 ; tâche T235).

Refait la photographie des écrans (outils/photographier_ecrans.py : textes visibles et attributs lus, en démo et en
mode serveur, pour les trois profils, écrans et onglets du routeur, fenêtres courantes, connexion, porte, assistant)
et la compare à la référence prise avant le Lot 2 (tests/fixtures/ecrans-reference/demo.json et serveur.json).
Tout écart fait échouer le test ; le message donne, pour chaque écran touché, le mode, le profil, l'écran et les
entrées avant/après (voir « LIRE UN ÉCART » dans la docstring de l'outil). Ce test ne reprend JAMAIS la référence :
seul le chef de chantier le fait (py -X utf8 outils/photographier_ecrans.py --reference), quand un changement d'écran
est voulu.

Lancé à chaque tâche de domaine du Lot 2 (au travers du verrou du navigateur), depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_ecrans_identiques.py" -v
Durée : environ quatre minutes pour les deux modes (Chromium headless, un seul navigateur pour les deux tests).
"""
import importlib.util
import sys
import tempfile
import time
import unittest
from pathlib import Path

from commun import RACINE, sync_playwright

_specification = importlib.util.spec_from_file_location("photographier_ecrans", RACINE / "outils" / "photographier_ecrans.py")
photo = importlib.util.module_from_spec(_specification)
sys.modules.setdefault("photographier_ecrans", photo)
_specification.loader.exec_module(photo)

ECARTS_MONTRES = 40          # au-delà, le message dit combien d'autres écrans diffèrent (le relevé complet est gardé)
LIGNES_PAR_ECART = 30


def resumer(ecarts):
    """Les écarts, lisibles même quand un module entier est cassé : 40 écrans, 30 lignes chacun au plus."""
    morceaux = []
    for ecart in ecarts[:ECARTS_MONTRES]:
        lignes = ecart.split("\n")
        if len(lignes) > LIGNES_PAR_ECART + 1:
            lignes = lignes[:LIGNES_PAR_ECART + 1] + ["    … et %d autres lignes" % (len(lignes) - LIGNES_PAR_ECART - 1)]
        morceaux.append("\n".join(lignes))
    if len(ecarts) > ECARTS_MONTRES:
        morceaux.append("… et %d autres écrans différents" % (len(ecarts) - ECARTS_MONTRES))
    return "\n\n".join(morceaux)


class TestEcransIdentiques(unittest.TestCase):
    """Un test par mode : le relevé complet du mode, comparé entrée par entrée à sa référence."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if sync_playwright is None:
            raise unittest.SkipTest("Playwright pour Python n'est pas installé")
        cls._playwright = sync_playwright().start()
        cls.addClassCleanup(cls._playwright.stop)
        cls.navigateur = cls._playwright.chromium.launch(headless=True)
        cls.addClassCleanup(cls.navigateur.close)

    def verifier_mode(self, mode):
        reference = photo.lire_reference(mode)
        debut = time.monotonic()
        try:
            releve = photo.Releveur(self._playwright, self.navigateur, mode).relever()
        except photo.ErreurReleve as erreur:
            self.fail("photographie du mode %s impossible : %s" % (mode, erreur))
        duree = time.monotonic() - debut
        ecarts = photo.comparer(reference, releve)
        if ecarts:
            # Le relevé complet est gardé pour une comparaison à loisir avec la référence (diff, éditeur).
            chemin = photo.ecrire(releve, Path(tempfile.gettempdir()) / "prevo-ecrans-identiques")
            self.fail("%d écran(s) différent(s) de la référence en mode %s (relevé en %.0f s) :\n\n%s\n\n"
                      "Relevé complet : %s (référence : tests/fixtures/ecrans-reference/%s.json).\n"
                      "Si ce changement d'écran est voulu, le chef de chantier reprend la référence "
                      "(py -X utf8 outils/photographier_ecrans.py --reference)."
                      % (len(ecarts), mode, duree, resumer(ecarts), chemin, mode))
        self.assertEqual(len(releve["ecrans"]), len(reference["ecrans"]))
        sys.stderr.write("\n  [%s] %d écrans identiques à la référence, relevés en %.0f s " % (mode, len(releve["ecrans"]), duree))

    def test_demo(self):
        self.verifier_mode("demo")

    def test_serveur(self):
        self.verifier_mode("serveur")


class TestComparaison(unittest.TestCase):
    """La comparaison elle-même (sans navigateur) : un mot changé, un écran manquant, une espace insécable."""

    def releve(self, texte, ecrans=None):
        if ecrans is None:
            ecrans = [{"profil": "responsable", "ecran": "accueil", "titre": "Accueil — Prévo",
                       "texte": photo.compter(texte), "attributs": photo.compter(["title=Priorité P2"])}]
        return {"mode": "demo", "conditions": {"horloge": "x"}, "masques": [], "ecrans": ecrans}

    def test_releves_identiques(self):
        self.assertEqual(photo.comparer(self.releve(["Bonjour", "OT en retard"]), self.releve(["Bonjour", "OT en retard"])), [])

    def test_mot_change(self):
        ecarts = photo.comparer(self.releve(["Bonjour", "OT en retard"]), self.releve(["Bonjour", "OT en avance"]))
        self.assertEqual(len(ecarts), 1)
        self.assertIn("[demo] responsable / accueil", ecarts[0])
        self.assertIn("- avant, texte : « OT en retard »", ecarts[0])
        self.assertIn("+ après, texte : « OT en avance »", ecarts[0])
        self.assertLess(ecarts[0].index("- avant"), ecarts[0].index("+ après"))

    def test_nombre_change(self):
        ecarts = photo.comparer(self.releve(["gêne", "gêne"]), self.releve(["gêne"]))
        self.assertIn("(2 fois avant, 1 après)", ecarts[0])

    def test_espace_insecable_remplacee(self):
        ecarts = photo.comparer(self.releve(["12 h"]), self.releve(["12 h"]))
        self.assertIn("« 12\\u00a0h »", ecarts[0])
        self.assertIn("« 12 h »", ecarts[0])

    def test_ecran_absent(self):
        ecarts = photo.comparer(self.releve(["Bonjour"]), self.releve([], ecrans=[]))
        self.assertEqual(ecarts, ["[demo] responsable / accueil : écran absent du nouveau relevé"])

    def test_message_borne(self):
        ecarts = ["[demo] responsable / e%d\n" % i + "\n".join("    + après, texte : « %d »" % j for j in range(50))
                  for i in range(45)]
        message = resumer(ecarts)
        self.assertIn("… et 5 autres écrans différents", message)
        self.assertIn("… et 20 autres lignes", message)
        self.assertNotIn("e44", message)

    def test_json_stable_et_invisibles_echappes(self):
        texte = photo.en_json(self.releve(["12 h", "b", "a"]))
        self.assertIn('"12\\u00a0h"', texte)
        self.assertNotIn(" ", texte)
        self.assertLess(texte.index('"a"'), texte.index('"b"'))
        self.assertEqual(texte, photo.en_json(self.releve(["a", "b", "12 h"])))


if __name__ == "__main__":
    unittest.main()
