"""Tests des règles pures des types d'habilitation (equipe-regles.js, T430 ; CS172, CS179).

Jeu construit dans ce fichier, date fixe passée en argument (aujourd'hui = 20/10/2026). Le catalogue est
js/catalogue/fr.js (CatalogueFR.habilitations, H01 à H15).

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_habilitations_regles.py" -v
"""
import unittest
from pathlib import Path

from commun import CasNavigateur, charger_scripts

RACINE = Path(__file__).resolve().parent.parent
SCRIPTS_BASE = [
    "js/lib/papaparse.min.js",
    "js/schema.js",
    "js/donnees.js",
    "js/stockage-demo.js",
    "js/interface.js",
    "js/modules/controles-regles.js",
    "js/modules/equipe-regles.js",
]
AUJOURDHUI = "2026-10-20"


def csv(entete, lignes):
    return "\r\n".join([entete] + list(lignes)) + "\r\n"


TECHNICIENS = csv("id;nom;prenom;actif", [
    "TEC-0001;Moreau;Julien;1",
    "TEC-0002;Benali;Karim;1",
    "TEC-0003;Garnier;Thomas;1",
    "TEC-0004;Sans;Papier;1",
])

HABILITATIONS = csv(
    "id;technicien_id;intitule;date_obtention;date_echeance;recyclage_mois;justificatif;catalogue_id;nature_source",
    [
        # Moreau : BR (H02) à 36 mois, CACES R489 (H12) valable avec justificatif, sans autorisation
        "HAB-0001;TEC-0001;BR;2024-01-15;2027-01-15;36;;H02;recommandation",
        "HAB-0002;TEC-0001;CACES R489;2022-03-01;2027-03-01;60;habilitation-TEC-0001-CACES-R489-2022-03-01.pdf;H12;obligation",
        # Benali : CACES R489 et autorisation de conduite H14 sans échéance
        "HAB-0003;TEC-0002;CACES R489;2022-03-01;2027-03-01;60;;H12;obligation",
        "HAB-0004;TEC-0002;Autorisation de conduite (employeur);2024-01-15;;;;H14;obligation",
        # Garnier : CACES R489 échu, recyclage saisi différent du type (24 au lieu de 36), BR sans type
        "HAB-0005;TEC-0003;CACES R489;2015-01-01;2020-01-01;60;;H12;obligation",
        "HAB-0006;TEC-0003;B2V;2024-01-15;2026-01-15;24;;H02;recommandation",
        "HAB-0007;TEC-0003;H0V;2024-01-15;2027-01-15;36;;;",
        # Sans papier : autorisation de conduite échue, CACES valable
        "HAB-0008;TEC-0004;Autorisation de conduite (employeur);2020-01-01;2021-01-01;;;H14;obligation",
        "HAB-0009;TEC-0004;CACES R486;2025-01-01;2030-01-01;60;;H10;obligation",
    ])


class CasRegles(CasNavigateur):
    def charger(self, avec_catalogue=True):
        scripts = (["js/catalogue/fr.js"] if avec_catalogue else []) + SCRIPTS_BASE
        charger_scripts(self.page, scripts)
        self.page.evaluate("""async (tables) => {
          Donnees.initialiser(StockageDemo.creer(tables), { poste: 'Poste test', profil: 'Responsable test' });
          await Donnees.chargerTout();
        }""", {"techniciens": TECHNICIENS, "habilitations": HABILITATIONS})

    def js(self, script, argument=None):
        return self.page.evaluate(script, argument)


class TestTypes(CasRegles):
    def setUp(self):
        super().setUp()
        self.charger()

    def test_types_et_recherche_par_identifiant(self):
        self.assertEqual(self.js("() => Equipe.typesHabilitation().length"), 15)
        self.assertEqual(self.js("() => Equipe.typeHabilitation('h12').type"),
                         "CACES R489 – Chariots de manutention automoteurs à conducteur porté")
        self.assertIsNone(self.js("() => Equipe.typeHabilitation('H99')"))
        self.assertIsNone(self.js("() => Equipe.typeHabilitation('')"))

    def test_type_de_par_catalogue_id(self):
        calcul = "(id) => { const t = Equipe.typeDe(Donnees.trouver('habilitations', id)); return t && t.id; }"
        self.assertEqual(self.js(calcul, "HAB-0001"), "H02")
        self.assertEqual(self.js(calcul, "HAB-0004"), "H14")
        self.assertIsNone(self.js(calcul, "HAB-0007"))

    def test_intitule_propose(self):
        calcul = "(id) => Equipe.intitulePropose(Equipe.typeHabilitation(id))"
        self.assertEqual(self.js(calcul, "H12"), "CACES R489")
        self.assertEqual(self.js(calcul, "H14"), "Autorisation de conduite (employeur)")
        for identifiant in ("H01", "H02", "H05"):
            with self.subTest(type=identifiant):
                self.assertEqual(self.js(calcul, identifiant), "")
        self.assertEqual(self.js("() => Equipe.intitulePropose(null)"), "")

    def test_valeurs_depuis_type(self):
        calcul = "(id) => Equipe.valeursDepuisType(Equipe.typeHabilitation(id))"
        self.assertEqual(self.js(calcul, "H02"), {"intitule": "", "recyclage_mois": 36, "catalogue_id": "H02",
                                                  "nature_source": "recommandation"})
        self.assertEqual(self.js(calcul, "H12")["recyclage_mois"], 60)
        self.assertEqual(self.js(calcul, "H12")["intitule"], "CACES R489")
        # H14 : pas de durée, donc pas de recyclage proposé
        self.assertEqual(self.js(calcul, "H14")["recyclage_mois"], "")
        self.assertEqual(self.js("() => Equipe.valeursDepuisType(null)"),
                         {"intitule": "", "recyclage_mois": "", "catalogue_id": "", "nature_source": ""})

    def test_h01_et_h02_sont_des_recommandations(self):
        for identifiant in ("H01", "H02"):
            with self.subTest(type=identifiant):
                self.assertEqual(self.js("(id) => Equipe.valeursDepuisType(id).nature_source", identifiant),
                                 "recommandation")

    def test_echeance_proposee_cs172(self):
        calcul = "([o, m]) => Equipe.echeanceProposee(o, m)"
        self.assertEqual(self.js(calcul, ["2024-01-15", 36]), "2027-01-15")
        self.assertEqual(self.js(calcul, ["2024-01-15", "36"]), "2027-01-15")
        self.assertEqual(self.js(calcul, ["2024-02-29", 12]), "2025-02-28")
        for obtention, mois in (("", 36), ("pas une date", 36), ("2024-01-15", ""), ("2024-01-15", 0),
                                ("2024-01-15", -3), ("2024-01-15", 1.5)):
            with self.subTest(obtention=obtention, mois=mois):
                self.assertEqual(self.js(calcul, [obtention, mois]), "")

    def test_recyclage_du_type(self):
        calcul = "(id) => Equipe.recyclageDuType(Donnees.trouver('habilitations', id))"
        self.assertEqual(self.js(calcul, "HAB-0001"), {"propose": 36, "egal": True})
        self.assertEqual(self.js(calcul, "HAB-0006"), {"propose": 36, "egal": False})
        self.assertEqual(self.js(calcul, "HAB-0004"), {"propose": None, "egal": True})   # H14 sans durée
        self.assertEqual(self.js(calcul, "HAB-0007"), {"propose": None, "egal": True})   # sans type

    def test_autorisation_de_conduite_distincte_des_caces(self):
        for identifiant in ("H14",):
            self.assertTrue(self.js("(id) => Equipe.estAutorisationDeConduite(Equipe.typeHabilitation(id))", identifiant))
            self.assertFalse(self.js("(id) => Equipe.estCaces(Equipe.typeHabilitation(id))", identifiant))
        for numero in range(6, 14):
            identifiant = "H%02d" % numero
            with self.subTest(type=identifiant):
                self.assertTrue(self.js("(id) => Equipe.estCaces(Equipe.typeHabilitation(id))", identifiant))
                self.assertFalse(self.js("(id) => Equipe.estAutorisationDeConduite(Equipe.typeHabilitation(id))",
                                         identifiant))
        for identifiant in ("H01", "H05", "H15"):
            with self.subTest(type=identifiant):
                self.assertFalse(self.js("(id) => Equipe.estCaces(Equipe.typeHabilitation(id))", identifiant))
        self.assertFalse(self.js("() => Equipe.estCaces(null)"))
        self.assertFalse(self.js("() => Equipe.estAutorisationDeConduite(null)"))

    def test_caces_sans_autorisation(self):
        calcul = ("([id, jour]) => Equipe.cacesSansAutorisation(id, jour).map((h) => h.id)")
        self.assertEqual(self.js(calcul, ["TEC-0001", AUJOURDHUI]), ["HAB-0002"])   # CACES, pas d'autorisation
        self.assertEqual(self.js(calcul, ["TEC-0002", AUJOURDHUI]), [])             # autorisation H14 valable
        self.assertEqual(self.js(calcul, ["TEC-0003", AUJOURDHUI]), [])             # son CACES est échu
        self.assertEqual(self.js(calcul, ["TEC-0004", AUJOURDHUI]), ["HAB-0009"])   # autorisation échue ne compte pas

    def test_justificatifs_reprenables(self):
        calcul = "(id) => Equipe.justificatifsReprenables(id).map((h) => h.id)"
        self.assertEqual(self.js(calcul, "TEC-0001"), ["HAB-0002"])
        self.assertEqual(self.js(calcul, "TEC-0002"), [])     # CACES sans justificatif
        self.assertEqual(self.js(calcul, "TEC-0099"), [])


class TestSansCatalogue(CasRegles):
    def test_sans_catalogue_tout_est_vide(self):
        self.charger(avec_catalogue=False)
        self.assertEqual(self.js("() => Equipe.typesHabilitation()"), [])
        self.assertIsNone(self.js("() => Equipe.typeHabilitation('H02')"))
        self.assertIsNone(self.js("() => Equipe.typeDe(Donnees.trouver('habilitations', 'HAB-0001'))"))
        self.assertEqual(self.js("() => Equipe.valeursDepuisType('H02')")["catalogue_id"], "")
        self.assertEqual(self.js("() => Equipe.cacesSansAutorisation('TEC-0001', '2026-10-20')"), [])


if __name__ == "__main__":
    unittest.main()
