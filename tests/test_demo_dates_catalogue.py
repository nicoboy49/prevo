"""La démo ne décale pas catalogue_relu_le (2.2, T424, CS171).

catalogue_relu_le est la date de relecture de la source du catalogue, pas un événement de la démo : décalée, elle
affichait « relu le 29/11/2026 » (date future). Même règle des deux côtés, une liste de colonnes non décalées par
côté : COLONNES_NON_DECALEES de js/stockage-demo.js (navigateur) et de serveur.py (installation de la démo).
Les autres colonnes date du même fichier (derniere_date, prochaine_date) sont bien décalées.
"""

import csv
import io
import sys
import unittest

from commun import DOSSIER_DEMO, RACINE, CasNavigateur, charger_scripts

sys.path.insert(0, str(RACINE))
import serveur  # noqa: E402

TABLE = "controles_reglementaires"


def lignes_demo():
    texte = (DOSSIER_DEMO / (TABLE + ".csv")).read_bytes().decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte), delimiter=";"))


class TestDemoDatesCatalogueServeur(unittest.TestCase):

    def test_liste_cote_serveur(self):
        self.assertEqual(serveur.COLONNES_NON_DECALEES, {TABLE: ("catalogue_relu_le",)})

    def test_decalage_serveur_epargne_catalogue_relu_le(self):
        origine = [ligne for ligne in lignes_demo() if ligne["catalogue_relu_le"]]
        self.assertGreater(len(origine), 0)
        _, textes = serveur.lire_jeu_de_demo()
        decale = list(csv.DictReader(io.StringIO(serveur.decaler_texte_csv(textes[TABLE], 28, TABLE)
                                                 .decode("utf-8-sig")), delimiter=";"))
        self.assertEqual([ligne["catalogue_relu_le"] for ligne in decale],
                         [ligne["catalogue_relu_le"] for ligne in lignes_demo()])
        avec_date = [(a, b) for a, b in zip(lignes_demo(), decale) if a["prochaine_date"]]
        self.assertGreater(len(avec_date), 0)
        for avant, apres in avec_date:
            self.assertNotEqual(avant["prochaine_date"], apres["prochaine_date"])


class TestDemoDatesCatalogueNavigateur(CasNavigateur):

    def test_decalage_navigateur_epargne_catalogue_relu_le(self):
        charger_scripts(self.page, ["js/lib/papaparse.min.js", "js/schema.js", "js/donnees.js",
                                    "js/stockage-demo.js", "js/demo-donnees.js"])
        decale = self.page.evaluate("""() => {
            const octets = StockageDemo.decalerDates({ controles_reglementaires: DEMO_DONNEES.tables.controles_reglementaires },
              DEMO_DONNEES.dateReference, '2027-03-01');
            return Donnees.csv.analyser('controles_reglementaires', octets.controles_reglementaires).lignes
              .map((l) => [l.catalogue_relu_le, l.prochaine_date]);
        }""")
        origine = lignes_demo()
        self.assertEqual(len(decale), len(origine))
        self.assertEqual([d[0] for d in decale], [o["catalogue_relu_le"] for o in origine])
        changees = [d[1] != o["prochaine_date"] for d, o in zip(decale, origine) if o["prochaine_date"]]
        self.assertTrue(changees and all(changees))


if __name__ == "__main__":
    unittest.main()
