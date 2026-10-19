"""Régressions de la lecture/écriture CSV (js/donnees.js, section 3).

Couvre :
    - une cellule faite seulement d'espaces ou de tabulations, protégée ou non, ne revient jamais sous la forme « ' » ;
    - une valeur protégée « '1,5E+3 » est voulue : aucun problème « excel » ; « 1,5E+3 » brut en lève un.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_csv_regressions.py" -v
"""
import base64
import unittest

from commun import CasNavigateur, charger_scripts

SCRIPTS = ["js/lib/papaparse.min.js", "js/schema.js", "js/donnees.js"]

AIDE_JS = """
window.versOctets = (texteBase64) => Uint8Array.from(atob(texteBase64), (c) => c.charCodeAt(0));
"""


class TestRegressionsCsv(CasNavigateur):

    def setUp(self):
        super().setUp()
        charger_scripts(self.page, SCRIPTS)
        self.page.evaluate(AIDE_JS)

    def lire(self, colonnes, cellules):
        """Analyse un petit CSV « equipements » (en-tête + une ligne) et renvoie le résultat."""
        texte = "﻿" + ";".join(colonnes) + "\r\n" + ";".join(cellules) + "\r\n"
        b64 = base64.b64encode(texte.encode("utf-8")).decode("ascii")
        return self.page.evaluate(
            "(b64) => Donnees.csv.analyser('equipements', versOctets(b64))", b64)

    def test_blancs_seuls_ne_reviennent_jamais_en_apostrophe(self):
        # « designation » (texte) et « repere » (protégé) : cellules brutes « '\t », « '  », « \t », « (deux espaces) »
        # Cellules que l'écriture peut produire : « '\t » (texte et repère), « '  » (repère protégé seulement :
        # dans un champ non protégé, deux espaces s'écrivent tels quels), plus les blancs bruts.
        cas = [("'\t", "'\t"), ("'  ", "  "), ("\t", "\t"), ("  ", "  ")]
        for brut_repere, brut_designation in cas:
            resultat = self.lire(["id", "repere", "designation"], ["EQ-0001", brut_repere, brut_designation])
            ligne = resultat["lignes"][0]
            for champ, brut in (("repere", brut_repere), ("designation", brut_designation)):
                self.assertNotEqual(ligne[champ], "'", "%s depuis %r" % (champ, brut))
                self.assertFalse(ligne[champ].startswith("'"), "%s depuis %r" % (champ, brut))

    def test_ecrire_blancs_puis_relire_ne_donne_pas_apostrophe(self):
        for valeur in ["\t", "  "]:
            for nom in ("repere", "designation"):
                relu = self.page.evaluate(
                    """([nom, v]) => { const champ = Schema.champ('equipements', nom);
                         return Donnees.csv.relireValeur(champ, Donnees.csv.ecrireValeur(champ, v)); }""",
                    [nom, valeur])
                self.assertEqual(relu, valeur, "%s %r" % (nom, valeur))

    def test_notation_scientifique_protegee_n_est_pas_un_probleme_excel(self):
        resultat = self.lire(["id", "repere", "designation"], ["EQ-0001", "R-1", "'1,5E+3"])
        self.assertEqual([p for p in resultat["problemes"] if p["type"] == "excel"], [])
        self.assertEqual(resultat["lignes"][0]["designation"], "1,5E+3")

    def test_notation_scientifique_brute_leve_un_probleme_excel(self):
        resultat = self.lire(["id", "repere", "designation"], ["EQ-0001", "R-1", "1,5E+3"])
        self.assertEqual(len([p for p in resultat["problemes"] if p["type"] == "excel"]), 1)


if __name__ == "__main__":
    unittest.main()
