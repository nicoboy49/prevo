"""Fiche technique des CSV (lot 4, ARCHITECTURE.md §17.8 ; CS75).

FICHE_TECHNIQUE_CSV.md doit être exactement ce que outils/generer_fiche_csv.py écrit d'après le
schéma réel (js/schema.js lu dans Chromium) : toute modification du schéma sans régénération fait
échouer ce test. Contrôles de fond : les 23 fichiers, chacune de leurs colonnes et la version du
format y figurent.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_fiche_csv.py" -v
"""
import importlib.util
import json
import unittest

from commun import RACINE, CasNavigateur, charger_scripts

CHEMIN_OUTIL = RACINE / "outils" / "generer_fiche_csv.py"
spec = importlib.util.spec_from_file_location("generer_fiche_csv", CHEMIN_OUTIL)
generer_fiche_csv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generer_fiche_csv)


class TestFicheCsv(CasNavigateur):

    def setUp(self):
        super().setUp()
        charger_scripts(self.page, ["js/schema.js"])
        self.schema = json.loads(self.page.evaluate(
            "() => JSON.stringify({ version: Schema.version, ordre: Schema.nomsTables(), tables: Schema.tables })"))
        self.fiche = generer_fiche_csv.FICHIER_FICHE.read_text(encoding="utf-8")

    def test_fiche_a_jour_avec_le_schema(self):
        self.assertEqual(self.fiche, generer_fiche_csv.rediger_fiche(self.schema),
                         "FICHE_TECHNIQUE_CSV.md n'est plus à jour : lancez py outils/generer_fiche_csv.py")

    def test_toutes_les_tables_et_colonnes_documentees(self):
        self.assertEqual(len(self.schema["ordre"]), 23)
        self.assertIn("format **version %d**" % self.schema["version"], self.fiche)
        for nom in self.schema["ordre"]:
            table = self.schema["tables"][nom]
            with self.subTest(table=nom):
                self.assertIn("`%s` — %s" % (table["fichier"], table["libelle"]), self.fiche)
                section = self.fiche.split("`%s` — " % table["fichier"], 1)[1].split("\n### ", 1)[0]
                for champ in table["champs"]:
                    self.assertIn("| `%s` |" % champ["nom"], section)

    def test_regles_communes_presentes(self):
        for attendu in ("UTF-8 avec BOM", "point-virgule", "CRLF", "Apostrophe de protection", "Jamais de suppression",
                        "`DI-AAAA-NNNN`", "`J-AAAAMMJJHHMMSS-XXXX`"):
            self.assertIn(attendu, self.fiche)


if __name__ == "__main__":
    unittest.main()
