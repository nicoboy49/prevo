"""Tests des règles pures du coût de l'arrêt (Prévo 2.2, lot L5, T470 ; D188, CS174 ; conception L4-L5-L6 §3.1, §3.4).

Coût de l'arrêt = Σ durées d'arrêt des pannes × coût d'une heure d'arrêt de l'équipement (equipements.cout_arret_h),
au centime, calculé en entiers (durée en dix-millièmes d'heure, coût horaire en centimes, arrondi au centime moitié
vers le haut une fois par équipement ; total = somme des lignes). Aucun coût horaire par défaut : un équipement sans
coût est listé « non chiffré », une panne sans durée est listée, jamais estimés ; 0 saisi = chiffré à 0.

Trois familles :
    - le jeu d'essai de la conception (mars 2026) : total 591,62 € (59162 centimes), demi-centime arrondi vers le
      haut, un équipement non chiffré et une panne sans durée listés ; OT annulé, préventif avec arrêt, panne sans
      arrêt et panne du mois précédent ignorés ;
    - des cas aux limites (avril 2026) : coût à 0, négatif, illisible, au format « 1 250,50 », équipement
      introuvable, durée négative, panne datée par sa DI, durée à plus de 4 décimales, piège des flottants ;
    - un jeu tiré au hasard (graine fixe) : chaque montant comparé à un calcul Python `decimal` (ROUND_HALF_UP).

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_cout_arret_regles.py" -v
"""
import random
import unittest
from decimal import ROUND_HALF_UP, Decimal

from commun import CasNavigateur, charger_scripts

SCRIPTS = [
    "js/lib/papaparse.min.js", "js/schema.js", "js/donnees.js", "js/stockage-demo.js", "js/interface.js",
    "js/modules/accueil.js", "js/modules/ordres-regles.js", "js/modules/planning-regles.js",
    "js/modules/indicateurs-regles.js", "js/modules/indicateurs-series.js",
]
AUJOURDHUI = "2026-10-20"
MARS = ["du-au", AUJOURDHUI, "2026-03-01", "2026-03-31"]
AVRIL = ["du-au", AUJOURDHUI, "2026-04-01", "2026-04-30"]
JUIN = ["du-au", AUJOURDHUI, "2026-06-01", "2026-06-30"]
CLOS = "Clôturé techniquement"


def csv(entete, lignes):
    return "\r\n".join([entete] + list(lignes)) + "\r\n"


LOCALISATIONS = csv("id;libelle;parent_id;type", [
    "LOC-0001;Site;;site", "LOC-0002;Atelier A;LOC-0001;atelier", "LOC-0003;Atelier B;LOC-0001;atelier"])
EQUIPEMENTS = csv("id;repere;criticite;statut;localisation_id;actif;cout_arret_h", [
    "EQ-0001;PO-01;A;en service;LOC-0002;1;150",          # A de la conception
    "EQ-0002;PO-02;B;en service;LOC-0002;1;87.35",        # B
    "EQ-0003;PO-03;A;en service;LOC-0003;1;",             # C : sans coût horaire
    "EQ-0004;PO-04;C;rebut;LOC-0003;0;0.10",              # D : au rebut et désactivé, compté quand même
    "EQ-0005;PO-05;B;en service;LOC-0003;1;0",            # 0 saisi : arrêt sans coût, chiffré à 0
    "EQ-0006;PO-06;B;en service;LOC-0003;1;-5",           # négatif : non chiffré
    "EQ-0007;PO-07;B;en service;LOC-0003;1;abc",          # illisible : non chiffré
    "EQ-0008;PO-08;B;en service;LOC-0003;1;2.01",         # 0,5 h × 2,01 = 1,005 : piège des flottants
    "EQ-0009;PO-09;A;en service;LOC-0002;1;1 250,50",     # forme saisie (espace, virgule)
])
DEMANDES = csv("id;date_heure;equipement_id;statut;ot_id", [
    "DI-2026-0001;2026-04-30 22:00;EQ-0009;Acceptée;OT-2026-0019"])
ENTETE_OT = "id;di_id;equipement_id;type;statut;date_creation;arret_production;duree_arret_h"
ORDRES = csv(ENTETE_OT, [
    # Mars : le jeu d'essai de la conception
    "OT-2026-0001;;EQ-0001;correctif immédiat;%s;2026-03-02 08:00;1;1.5" % CLOS,
    "OT-2026-0002;;EQ-0001;correctif différé;Clôturé administrativement;2026-03-09 08:00;1;2.25",
    "OT-2026-0003;;EQ-0001;correctif immédiat;En cours;2026-03-20 08:00;1;",          # sans durée : listée
    "OT-2026-0004;;EQ-0002;correctif immédiat;%s;2026-03-05 08:00;1;0.3333" % CLOS,
    "OT-2026-0005;;EQ-0003;correctif différé;%s;2026-03-06 08:00;1;4" % CLOS,
    "OT-2026-0006;;EQ-0004;correctif immédiat;%s;2026-03-07 08:00;1;0.05" % CLOS,
    # Mars, ignorés : annulé, préventif avec arrêt, panne du mois précédent, correctif sans arrêt
    "OT-2026-0007;;EQ-0001;correctif immédiat;Annulé;2026-03-10 08:00;1;10",
    "OT-2026-0008;;EQ-0001;préventif systématique;%s;2026-03-11 08:00;1;5" % CLOS,
    "OT-2026-0009;;EQ-0001;correctif immédiat;%s;2026-02-27 08:00;1;3" % CLOS,
    "OT-2026-0010;;EQ-0002;correctif différé;%s;2026-03-12 08:00;0;7" % CLOS,
    # Avril : cas aux limites
    "OT-2026-0012;;EQ-0005;correctif immédiat;%s;2026-04-02 08:00;1;2" % CLOS,
    "OT-2026-0013;;EQ-0006;correctif immédiat;%s;2026-04-03 08:00;1;1" % CLOS,
    "OT-2026-0014;;EQ-0007;correctif immédiat;%s;2026-04-04 08:00;1;1.25" % CLOS,
    "OT-2026-0015;;EQ-0008;correctif immédiat;%s;2026-04-05 08:00;1;0.5" % CLOS,
    "OT-2026-0016;;EQ-0002;correctif différé;%s;2026-04-06 08:00;1;" % CLOS,           # clôturé sans durée
    "OT-2026-0017;;EQ-0099;correctif immédiat;%s;2026-04-07 08:00;1;3" % CLOS,         # équipement introuvable
    "OT-2026-0018;;EQ-0003;correctif immédiat;%s;2026-04-08 08:00;1;-2" % CLOS,        # durée négative
    "OT-2026-0019;DI-2026-0001;EQ-0009;correctif immédiat;%s;2026-05-01 08:00;1;2" % CLOS,   # daté par sa DI (30/04)
    "OT-2026-0020;;EQ-0008;correctif immédiat;%s;2026-04-09 08:00;1;0.33335" % CLOS,   # 5 décimales → 0,3334 h
])


def jeu_de_test():
    return {"localisations": LOCALISATIONS, "equipements": EQUIPEMENTS, "demandes": DEMANDES,
            "ordres_travail": ORDRES}


def centimes_decimal(durees, cout_horaire):
    """Calcul de référence, indépendant du code : Σ durées (au dix-millième d'heure) × coût horaire (au centime),
    arrondi au centime ROUND_HALF_UP, en centimes."""
    heures = sum((Decimal(d).quantize(Decimal("0.0001"), ROUND_HALF_UP) for d in durees), Decimal(0))
    cout = Decimal(cout_horaire).quantize(Decimal("0.01"), ROUND_HALF_UP)
    return int((heures * cout * 100).quantize(Decimal("1"), ROUND_HALF_UP))


class CasCoutArret(CasNavigateur):

    def charger(self, tables):
        charger_scripts(self.page, SCRIPTS)
        self.page.evaluate("""async (tables) => {
          Donnees.initialiser(StockageDemo.creer(tables), { poste: 'Poste test', profil: 'Responsable test' });
          await Donnees.chargerTout();
          window.periodeDe = (code, jour, du, au) => Indicateurs.periode(code, jour, du, au);
        }""", tables)

    def js(self, script, argument=None):
        return self.page.evaluate(script, argument)

    def cout(self, periode, filtres=None):
        return self.js("([p, f]) => Indicateurs.coutArret(periodeDe(...p), f)", [periode, filtres])

    def pareto(self, periode, n=None, filtres=None):
        return self.js("([p, n, f]) => Indicateurs.paretoCoutArret(periodeDe(...p), n, f)", [periode, n, filtres])


class TestCoutArretJeuDeLaConception(CasCoutArret):

    def setUp(self):
        super().setUp()
        self.charger(jeu_de_test())

    def test_jeu_de_la_conception_59162_centimes(self):
        r = self.cout(MARS)
        self.assertEqual(r["totalCentimes"], 59162)
        self.assertEqual(r["total"], 591.62)
        self.assertEqual(r["parEquipement"], [
            {"equipementId": "EQ-0001", "heures": 3.75, "coutHoraireCentimes": 15000, "centimes": 56250,
             "ots": ["OT-2026-0001", "OT-2026-0002"]},
            {"equipementId": "EQ-0002", "heures": 0.3333, "coutHoraireCentimes": 8735, "centimes": 2911,
             "ots": ["OT-2026-0004"]},
            {"equipementId": "EQ-0004", "heures": 0.05, "coutHoraireCentimes": 10, "centimes": 1,   # 0,005 € → 0,01 €
             "ots": ["OT-2026-0006"]},
        ])
        self.assertEqual(r["nonChiffres"], [{"equipementId": "EQ-0003", "heures": 4, "ots": ["OT-2026-0005"]}])
        self.assertEqual(r["sansDuree"], [{"otId": "OT-2026-0003", "equipementId": "EQ-0001", "raison": "non clôturé"}])
        self.assertFalse(r["complet"])
        # Le total est la somme des lignes affichées, et chaque ligne est le calcul decimal de référence.
        self.assertEqual(r["totalCentimes"], sum(ligne["centimes"] for ligne in r["parEquipement"]))
        self.assertEqual([centimes_decimal(["1.5", "2.25"], "150"), centimes_decimal(["0.3333"], "87.35"),
                          centimes_decimal(["0.05"], "0.10")], [56250, 2911, 1])
        # Sans arrondi préalable (aucune valeur du jeu n'a plus de 4 ou 2 décimales), le calcul decimal direct
        # donne le même total.
        direct = sum(((Decimal(h) * Decimal(c)).quantize(Decimal("0.01"), ROUND_HALF_UP)
                      for h, c in [("3.75", "150"), ("0.3333", "87.35"), ("0.05", "0.10")]), Decimal(0))
        self.assertEqual(direct, Decimal("591.62"))

    def test_pareto_du_cout_de_l_arret(self):
        lignes = self.pareto(MARS)
        self.assertEqual([(l["equipementId"], l["centimes"], l["valeur"]) for l in lignes],
                         [("EQ-0001", 56250, 562.5), ("EQ-0002", 2911, 29.11), ("EQ-0004", 1, 0.01)])
        self.assertAlmostEqual(lignes[0]["cumulPct"], 56250 / 59162 * 100, places=9)
        self.assertAlmostEqual(lignes[1]["cumulPct"], 59161 / 59162 * 100, places=9)
        self.assertAlmostEqual(lignes[2]["cumulPct"], 100, places=9)
        self.assertEqual(lignes[0]["heures"], 3.75)
        self.assertEqual(lignes[0]["ots"], ["OT-2026-0001", "OT-2026-0002"])
        deux = self.pareto(MARS, 2)
        self.assertEqual([l["equipementId"] for l in deux], ["EQ-0001", "EQ-0002"])
        self.assertAlmostEqual(deux[1]["cumulPct"], 59161 / 59162 * 100, places=9)   # cumul en % du total, pas des 2

    def test_filtres_criticite_et_atelier(self):
        a = self.cout(MARS, {"criticite": "A"})
        self.assertEqual(a["totalCentimes"], 56250)
        self.assertEqual([l["equipementId"] for l in a["parEquipement"]], ["EQ-0001"])
        self.assertEqual([l["equipementId"] for l in a["nonChiffres"]], ["EQ-0003"])
        self.assertEqual([l["otId"] for l in a["sansDuree"]], ["OT-2026-0003"])
        atelier_b = self.cout(MARS, {"atelier": "LOC-0003"})
        self.assertEqual(atelier_b["totalCentimes"], 1)
        self.assertEqual([l["equipementId"] for l in atelier_b["nonChiffres"]], ["EQ-0003"])
        self.assertEqual(atelier_b["sansDuree"], [])
        self.assertEqual([l["equipementId"] for l in self.pareto(MARS, None, {"atelier": "LOC-0003"})], ["EQ-0004"])

    def test_aucune_panne_dans_la_periode(self):
        r = self.cout(JUIN)
        self.assertEqual(r, {"totalCentimes": 0, "total": 0, "parEquipement": [], "nonChiffres": [], "sansDuree": [],
                             "complet": True})
        self.assertEqual(self.pareto(JUIN), [])


class TestCoutArretCasAuxLimites(CasCoutArret):

    def setUp(self):
        super().setUp()
        self.charger(jeu_de_test())

    def test_cas_aux_limites_d_avril(self):
        r = self.cout(AVRIL)
        self.assertEqual(r["parEquipement"], [
            {"equipementId": "EQ-0009", "heures": 2, "coutHoraireCentimes": 125050, "centimes": 250100,
             "ots": ["OT-2026-0019"]},                                   # daté par sa DI du 30/04
            {"equipementId": "EQ-0008", "heures": 0.8334, "coutHoraireCentimes": 201, "centimes": 168,
             "ots": ["OT-2026-0015", "OT-2026-0020"]},                   # (0,5 + 0,3334) × 2,01 = 1,675134
            {"equipementId": "EQ-0005", "heures": 2, "coutHoraireCentimes": 0, "centimes": 0,
             "ots": ["OT-2026-0012"]},                                   # 0 saisi : chiffré à 0
        ])
        self.assertEqual(r["nonChiffres"], [
            {"equipementId": "EQ-0099", "heures": 3, "ots": ["OT-2026-0017"]},     # introuvable
            {"equipementId": "EQ-0007", "heures": 1.25, "ots": ["OT-2026-0014"]},  # coût illisible
            {"equipementId": "EQ-0006", "heures": 1, "ots": ["OT-2026-0013"]},     # coût négatif
            {"equipementId": "EQ-0003", "heures": 0, "ots": []},                   # sa seule panne n'a pas de durée
        ])
        self.assertEqual(r["sansDuree"], [
            {"otId": "OT-2026-0016", "equipementId": "EQ-0002", "raison": "sans durée d'arrêt"},
            {"otId": "OT-2026-0018", "equipementId": "EQ-0003", "raison": "sans durée d'arrêt"},
        ])
        self.assertEqual(r["totalCentimes"], 250268)
        self.assertFalse(r["complet"])
        self.assertEqual([centimes_decimal(["2"], "1250.50"), centimes_decimal(["0.5", "0.33335"], "2.01")], [250100, 168])
        # Le pareto écarte l'équipement chiffré à 0 ; avec un filtre, l'équipement introuvable est écarté.
        self.assertEqual([l["equipementId"] for l in self.pareto(AVRIL)], ["EQ-0009", "EQ-0008"])
        self.assertNotIn("EQ-0099", [l["equipementId"] for l in self.cout(AVRIL, {"criticite": "B"})["nonChiffres"]])

    def test_piege_des_flottants(self):
        # 0,5 h × 2,01 €/h = 1,005 € : en flottants, Math.round(100,4999…) donne 1,00 € ; en entiers, 1,01 €.
        self.assertEqual(self.js("() => Math.round(0.5 * 2.01 * 100)"), 100)
        avril = self.cout(AVRIL)
        self.assertEqual(centimes_decimal(["0.5"], "2.01"), 101)
        self.assertTrue(all(isinstance(l["centimes"], int) for l in avril["parEquipement"]))
        self.assertIsInstance(avril["totalCentimes"], int)

    def test_conversions_en_entiers(self):
        cas_durees = [("1.5", 15000), ("2,25", 22500), ("0.3333", 3333), ("0.33335", 3334), ("0.333349", 3333),
                      (" 1 234,5 ", 12345000), (".5", 5000), ("0", 0), ("+3", 30000), ("0.99995", 10000),
                      ("", None), ("abc", None), ("-1", None), ("-0.00001", None), ("1e3", None)]
        cas_couts = [("150", 15000), ("87.35", 8735), ("87,35", 8735), ("0.10", 10), ("0", 0), ("1 250,50", 125050),
                     ("87.355", 8736), ("87.354", 8735), ("+12", 1200), ("", None), ("n/a", None), ("-5", None)]
        durees = self.js("(cas) => cas.map((v) => Indicateurs.interne.dixMilliemesDHeure(v))", [v for v, _ in cas_durees])
        couts = self.js("(cas) => cas.map((v) => Indicateurs.interne.centimesDuCoutHoraire(v))", [v for v, _ in cas_couts])
        self.assertEqual(list(zip([v for v, _ in cas_durees], durees)), cas_durees)
        self.assertEqual(list(zip([v for v, _ in cas_couts], couts)), cas_couts)
        self.assertEqual(self.js("() => [Indicateurs.interne.dixMilliemesDHeure(2.25), Indicateurs.interne.centimesDuCoutHoraire(undefined)]"),
                         [22500, None])


class TestCoutArretJeuAuHasard(CasCoutArret):
    """150 équipements, 1 à 4 pannes chacun en mars, durées et coûts tirés au hasard (graine fixe) ; quelques
    équipements sans coût et quelques pannes sans durée ; chaque montant = le calcul decimal de référence."""

    def jeu(self):
        hasard = random.Random(470)
        equipements = []
        ordres = []
        attendus = {}
        non_chiffres = set()
        sans_duree = set()
        for rang in range(150):
            equipement_id = "EQ-%04d" % (1000 + rang)
            tirage = hasard.random()
            if tirage < 0.1:
                cout = ""
            elif tirage < 0.15:
                cout = "%d.%03d" % (hasard.randint(0, 999), hasard.randint(0, 999))      # 3 décimales (import)
            else:
                cout = "%d.%02d" % (hasard.randint(0, 20000), hasard.randint(0, 99))
            equipements.append("%s;R-%d;B;en service;LOC-0002;1;%s" % (equipement_id, rang, cout))
            durees = []
            for panne in range(hasard.randint(1, 4)):
                ot_id = "OT-2026-%04d" % (1000 + 4 * rang + panne)
                chiffres = hasard.choice([0, 1, 2, 3, 4, 4, 4, 5, 6])
                duree = str(hasard.randint(0, 300)) + ("." + "".join(str(hasard.randint(0, 9)) for _ in range(chiffres)) if chiffres else "")
                if hasard.random() < 0.05:
                    duree = ""
                    sans_duree.add(ot_id)
                else:
                    durees.append(duree)
                jour = 1 + (4 * rang + panne) % 28
                ordres.append("%s;;%s;correctif immédiat;%s;2026-03-%02d %02d:%02d;1;%s"
                              % (ot_id, equipement_id, CLOS, jour, panne + 6, rang % 60, duree))
            if not cout:
                non_chiffres.add(equipement_id)
            elif durees:
                attendus[equipement_id] = centimes_decimal(durees, cout)
        tables = {"localisations": LOCALISATIONS, "demandes": csv("id;date_heure;equipement_id;statut;ot_id", []),
                  "equipements": csv("id;repere;criticite;statut;localisation_id;actif;cout_arret_h", equipements),
                  "ordres_travail": csv(ENTETE_OT, ordres)}
        return tables, attendus, non_chiffres, sans_duree

    def test_montants_egaux_au_calcul_decimal(self):
        tables, attendus, non_chiffres, sans_duree = self.jeu()
        self.charger(tables)
        r = self.cout(MARS)
        self.assertEqual({l["equipementId"]: l["centimes"] for l in r["parEquipement"]}, attendus)
        self.assertEqual({l["equipementId"] for l in r["nonChiffres"]}, non_chiffres)
        self.assertEqual({l["otId"] for l in r["sansDuree"]}, sans_duree)
        self.assertEqual(r["totalCentimes"], sum(attendus.values()))
        self.assertEqual(r["complet"], not non_chiffres and not sans_duree)
        self.assertGreater(len(attendus), 100)
        self.assertTrue(non_chiffres and sans_duree)
        centimes = [l["centimes"] for l in r["parEquipement"]]
        self.assertEqual(centimes, sorted(centimes, reverse=True))


if __name__ == "__main__":
    unittest.main()
