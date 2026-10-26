"""Lot 7 — textes d'aide de l'accès et de l'installation, une seule source (D131 ; CS124, CS130 ; tâche T169).

Ce qui est vérifié :
    à jour       js/modules/acces-textes.js est exactement ce que produit outils/generer_acces_textes.py ;
    options      chaque clé de CLES_CONFIGURATION (serveur.py) a son texte d'aide, identique à celui de
                 « serveur.py --aide » ;
    choix        chaque choix de l'assistant a son titre, qui est concerné, ce que ça change, pourquoi, et un conseil
                 pour chacune des trois situations (seul, équipe, informaticien) ;
    chargement   le module est chargé par index.html et AccesTextes est lisible dans la page (mode démo).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_acces_textes.py" -v
"""
import importlib.util
import json
import subprocess
import sys
import unittest

from commun import RACINE, CasNavigateur, attendre_pret, preregler_profil, url_fichier

OUTIL = RACINE / "outils" / "generer_acces_textes.py"
CIBLE = RACINE / "js" / "modules" / "acces-textes.js"


def charger(chemin, nom):
    specification = importlib.util.spec_from_file_location(nom, chemin)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def lire_textes():
    texte = CIBLE.read_text(encoding="utf-8")
    debut = texte.index("const AccesTextes = ") + len("const AccesTextes = ")
    return json.loads(texte[debut:texte.rindex(";")])


class TestSource(unittest.TestCase):

    def test_fichier_a_jour(self):
        outil = charger(OUTIL, "generer_acces_textes_test")
        self.assertEqual(CIBLE.read_bytes().decode("utf-8"), outil.contenu(),
                         "js/modules/acces-textes.js n'est pas à jour : py outils/generer_acces_textes.py")

    def test_options_identiques_a_serveur_aide(self):
        serveur = charger(RACINE / "serveur.py", "serveur_prevo_textes_test")
        textes = lire_textes()
        aide = subprocess.run([sys.executable, str(RACINE / "serveur.py"), "--aide"], capture_output=True,
                              encoding="utf-8", errors="replace", timeout=30,
                              env=dict(__import__("os").environ, PYTHONIOENCODING="utf-8")).stdout
        self.assertEqual(set(textes["options"]), {cle for cle, _, _, _ in serveur.CLES_CONFIGURATION})
        for cle, _, _, texte_aide in serveur.CLES_CONFIGURATION:
            with self.subTest(cle=cle):
                self.assertEqual(textes["options"][cle]["aide"], texte_aide)
                self.assertIn(texte_aide, aide.replace("\n      ", " "))

    def test_choix_complets(self):
        textes = lire_textes()
        self.assertEqual(set(textes["situations"]), {"seul", "equipe", "informaticien"})
        attendus = {"installation", "mot_de_passe", "etiquettes", "exterieur", "demarrage", "veille", "certificat",
                    "sauvegardes", "ia"}
        self.assertEqual(set(textes["choix"]), attendus)
        for nom, choix in textes["choix"].items():
            with self.subTest(choix=nom):
                for champ in ("titre", "qui", "change", "pourquoi"):
                    self.assertTrue(choix[champ].strip(), champ)
                self.assertEqual(set(choix["conseil"]), {"seul", "equipe", "informaticien"})
                for conseil in choix["conseil"].values():
                    self.assertTrue(conseil.strip())
        self.assertIn("pas à pas", textes["choix"]["certificat"]["change"])
        self.assertIn("jamais votre box", textes["choix"]["exterieur"]["pourquoi"])


class TestChargement(CasNavigateur):

    def test_accestextes_dans_la_page(self):
        preregler_profil(self.contexte, "responsable", "Responsable")
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        self.assertEqual(self.page.evaluate("Object.keys(AccesTextes.choix).length"), 9)
        self.assertIn("127.0.0.1", self.page.evaluate("AccesTextes.options.ecoute.aide"))


if __name__ == "__main__":
    unittest.main()
