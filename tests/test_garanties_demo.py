"""Tests des garanties et des contrats du jeu de démo (T460 ; outils/generer_demo.py, GRAINE_V22 ; CS173).

Les statuts calculés par le module Garanties (garanties-regles.js) sur donnees/demo/*.csv, à la date de référence de
la démo, sont égaux à ceux que le générateur recalcule en Python ; les rôles de tests/fixtures/demo-scenarios.json
pointent sur les bonnes lignes ; la démo est reproductible.

Lancer depuis la racine du projet (navigateur : au travers du verrou) :
    py -X utf8 -m unittest discover -s tests -p "test_garanties_demo.py" -v
"""
import importlib.util
import unittest
from datetime import date

from commun import CasNavigateur, RACINE, charger_scripts, scenarios_demo

DOSSIER_DEMO = RACINE / "donnees" / "demo"
JOUR = "2026-10-19"
SCRIPTS = [
    "js/lib/papaparse.min.js",
    "js/schema.js",
    "js/donnees.js",
    "js/stockage-demo.js",
    "js/interface.js",
    "js/modules/controles-regles.js",
    "js/modules/garanties-regles.js",
]
TABLES = ("equipements", "fournisseurs", "garanties", "contrats_prestataires")


def generateur():
    spec = importlib.util.spec_from_file_location("generer_demo_t460", RACINE / "outils" / "generer_demo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def lire(table):
    texte = (DOSSIER_DEMO / (table + ".csv")).read_bytes().decode("utf-8-sig")
    import csv
    import io
    return list(csv.DictReader(io.StringIO(texte, newline=""), delimiter=";"))


class TestGarantiesDemo(CasNavigateur):
    def setUp(self):
        super().setUp()
        charger_scripts(self.page, SCRIPTS)
        textes = {t: (DOSSIER_DEMO / (t + ".csv")).read_bytes().decode("utf-8-sig") for t in TABLES}
        self.page.evaluate("""async (tables) => {
          Donnees.initialiser(StockageDemo.creer(tables), { poste: 'Poste test', profil: 'Responsable test' });
          await Donnees.chargerTout();
        }""", textes)

    def test_statuts_de_la_demo_egaux_au_calcul_python(self):
        g = generateur()
        jour = date.fromisoformat(JOUR)
        for ligne in lire("garanties"):
            attendu = g.statut_garantie_v22(ligne, jour)
            obtenu = self.page.evaluate(
                "([id, jour]) => Garanties.etatGarantie(Donnees.trouver('garanties', id), jour, 60).statut",
                [ligne["id"], JOUR])
            self.assertEqual(obtenu, attendu, ligne["id"])
        for ligne in lire("contrats_prestataires"):
            attendu = g.statut_contrat_v22(ligne, jour)
            obtenu = self.page.evaluate(
                "([id, jour]) => Garanties.etatContrat(Donnees.trouver('contrats_prestataires', id), jour, 60).statut",
                [ligne["id"], JOUR])
            self.assertEqual(obtenu, attendu, ligne["id"])

    def test_roles_et_statuts_attendus(self):
        s = scenarios_demo()
        etat = lambda table, ligne, fonction: self.page.evaluate(
            "([t, id, jour, f]) => Garanties[f](Donnees.trouver(t, id), jour, 60)", [table, ligne, JOUR, fonction])
        self.assertEqual(etat("garanties", s["garantie_en_cours"], "etatGarantie")["statut"], "en_cours")
        bientot = etat("garanties", s["garantie_bientot_finie"], "etatGarantie")
        self.assertEqual((bientot["statut"], bientot["alerte"]), ("bientot", True))
        a_decider = etat("contrats_prestataires", s["contrat_a_decider"], "etatContrat")
        self.assertEqual(a_decider["statut"], "a_decider")
        self.assertTrue(0 <= a_decider["joursAvantLimite"] <= 60)
        self.assertEqual(etat("contrats_prestataires", s["contrat_a_mettre_a_jour"], "etatContrat")["statut"],
                         "a_mettre_a_jour")

    def test_les_trois_garanties_et_les_quatre_contrats_couvrent_les_cas(self):
        g = generateur()
        jour = date.fromisoformat(JOUR)
        self.assertEqual(sorted(g.statut_garantie_v22(x, jour) for x in lire("garanties")),
                         ["bientot", "en_cours", "terminee"])
        contrats = lire("contrats_prestataires")
        self.assertEqual(sorted(g.statut_contrat_v22(x, jour) for x in contrats),
                         ["a_decider", "a_mettre_a_jour", "en_cours", "termine"])
        self.assertTrue(any(x["reconduction_tacite"] == "1" for x in contrats))
        self.assertTrue(any(not x["montant_annuel"] for x in contrats))

    def test_garantie_sur_un_equipement_qui_a_des_pannes(self):
        s = scenarios_demo()
        garantie = next(x for x in lire("garanties") if x["id"] == s["garantie_en_cours"])
        pannes = [o for o in lire("ordres_travail")
                  if o["equipement_id"] == garantie["equipement_id"] and o["type"].startswith("correctif")]
        self.assertGreaterEqual(len(pannes), 3)

    def test_equipements_du_contrat_separes_par_point_virgule(self):
        contrat = next(x for x in lire("contrats_prestataires") if x["id"] == scenarios_demo()["contrat_a_decider"])
        self.assertEqual(len(contrat["equipement_ids"].split(";")), 2)
        ids = self.page.evaluate(
            "(id) => Garanties.equipementsDuContrat(Donnees.trouver('contrats_prestataires', id))", contrat["id"])
        self.assertEqual(ids, contrat["equipement_ids"].split(";"))


class TestReproductibilite(unittest.TestCase):
    def test_deux_executions_donnent_les_memes_fichiers(self):
        g = generateur()
        premier = g.construire_jeu()
        second = g.construire_jeu()
        for table in ("garanties", "contrats_prestataires"):
            self.assertEqual(premier.base[table], second.base[table])
            self.assertEqual(g.serialiser_table(table, premier.base[table]),
                             (DOSSIER_DEMO / (table + ".csv")).read_bytes().decode("utf-8-sig"))


if __name__ == "__main__":
    unittest.main()
