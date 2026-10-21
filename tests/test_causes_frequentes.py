"""Solidité de l'encart « Causes fréquentes ici » (lot 3 bis, ARCHITECTURE.md §16.7 ; CDC D59 (a) ;
tâche T58).

Couvre :
    - CausesFrequentes.fourchette(k, n) : intervalle de Wilson à 95 % égal à un calcul Python
      indépendant (cas limites k = 0, k = n, n = 1, grands n ; n = 0 → null) ;
    - CausesFrequentes.texteFourchette(k, n) : « entre 32 % et 81 % des cas », arrondi à l'unité,
      demi vers le haut ;
    - l'encart : mention « Peu de cas : à prendre comme une piste. » quand une cause affichée a une
      demi-largeur de plus de 20 points, absente au-delà ; détail « Précision de ces chiffres »
      toujours présent dans un encart suffisant ; lignes existantes inchangées ;
    - jeu de démo (mode serveur) : encart de la fiche OT du rôle « ot_fuite_garniture_po02 »,
      fourchettes égales au calcul Python sur les CSV.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_causes_frequentes.py" -v
"""
import csv as module_csv
import io
import math
import unittest
from pathlib import Path

from commun import CasNavigateur, ServeurPrevo, attendre_pret, charger_scripts, preregler_profil, scenarios_demo

SCRIPTS = [
    "js/lib/papaparse.min.js",
    "js/schema.js",
    "js/donnees.js",
    "js/stockage-demo.js",
    "js/interface.js",
    "js/modules/causes-frequentes.js",
]

Z = 1.96
CLOS = ("Clôturé techniquement", "Clôturé administrativement")
MENTION_PISTE = "Peu de cas : à prendre comme une piste."


def wilson(k, n):
    """Intervalle de Wilson à 95 % (même formule que §16.7), bornes ramenées dans [0, 1]."""
    if n <= 0:
        return None
    p = k / n
    z2 = Z * Z
    denominateur = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denominateur
    marge = (Z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))) / denominateur
    return (0.0 if k == 0 else max(0.0, centre - marge)), (1.0 if k == n else min(1.0, centre + marge))


def pourcent(part):
    """0,3195 → '32 %' : arrondi à l'unité, demi vers le haut (espace insécable avant %)."""
    return "%d %%" % math.floor(part * 100 + 0.5)


def texte_fourchette(k, n):
    bas, haut = wilson(k, n)
    return "entre %s et %s des cas" % (pourcent(bas), pourcent(haut))


def peu_de_cas(nombres, total):
    return any((lambda f: (f[1] - f[0]) / 2 > 0.20)(wilson(k, total)) for k in nombres)


def csv(entete, lignes):
    return "\r\n".join([entete] + list(lignes)) + "\r\n"


CODES = csv("id;famille;code;libelle", [
    "CD-0001;symptôme;FUI;fuite",
    "CD-0002;cause;GAR;garniture usée",
    "CD-0003;cause;JOI;joint détérioré",
    "CD-0004;cause;ROU;roulement hors service",
    "CD-0005;remède;REM;remplacement pièce",
])


def jeu(repartition):
    """Une pompe et ses correctifs clôturés « fuite » : repartition = {cause: nombre de cas}."""
    lignes, numero = [], 0
    for cause, nombre in repartition.items():
        for _ in range(nombre):
            numero += 1
            jour = "2026-%02d-%02d" % (1 + numero % 9, 1 + numero % 27)
            lignes.append("OT-2026-%04d;EQ-0001;correctif immédiat;Clôturé techniquement;%s 08:00;%s 10:00;FUI;%s;REM"
                          % (numero, jour, jour, cause))
    return {
        "equipements": csv("id;repere;designation;marque;modele;actif", ["EQ-0001;PO-01;Pompe;Grundfos;CR 10;1"]),
        "codes_defaillance": CODES,
        "ordres_travail": csv("id;equipement_id;type;statut;date_creation;date_fin;symptome_code;cause_code;remede_code", lignes),
    }


LIRE_ENCART_JS = """() => {
  const element = CausesFrequentes.encart('EQ-0001', 'FUI');
  document.body.appendChild(element);
  const details = element.querySelector('details.causes-precision');
  return {
    lignes: Array.from(element.querySelectorAll('li')).map((li) => li.textContent),
    mention: element.querySelector('.note').textContent,
    piste: element.querySelector('.causes-piste') ? element.querySelector('.causes-piste').textContent.trim() : null,
    resume: details ? details.querySelector('summary').textContent.trim() : null,
    ouvert: details ? details.open : null,
    fourchettes: details ? Array.from(details.querySelectorAll('.causes-fourchettes > div')).map((d) => d.textContent.replace(/[ \\t\\n\\r]+/g, ' ').trim()) : [],
    explication: details ? details.querySelector('.causes-explication').textContent : '',
  };
}"""


class CasCauses(CasNavigateur):

    def setUp(self):
        super().setUp()
        charger_scripts(self.page, SCRIPTS)

    def charger(self, tables):
        self.page.evaluate("""async (tables) => {
          Donnees.initialiser(StockageDemo.creer(tables), { poste: 'Poste test', profil: 'Responsable test' });
          await Donnees.chargerTout();
        }""", tables)

    def js(self, script, argument=None):
        return self.page.evaluate(script, argument)


class TestFourchette(CasCauses):

    def setUp(self):
        super().setUp()
        self.charger(jeu({"GAR": 1}))

    def test_fourchette_egale_au_calcul_python(self):
        couples = [(k, n) for n in (1, 2, 3, 5, 12, 19, 20, 23, 50, 100, 1000) for k in sorted({0, 1, n // 3, n // 2, n - 1, n}) if 0 <= k <= n]
        resultats = self.js("(couples) => couples.map(([k, n]) => CausesFrequentes.fourchette(k, n))", couples)
        for (k, n), resultat in zip(couples, resultats):
            with self.subTest(k=k, n=n):
                bas, haut = wilson(k, n)
                self.assertAlmostEqual(resultat["bas"], bas, places=12)
                self.assertAlmostEqual(resultat["haut"], haut, places=12)
                self.assertTrue(0 <= resultat["bas"] <= k / n <= resultat["haut"] <= 1)
        self.assertIsNone(self.js("() => CausesFrequentes.fourchette(0, 0)"))
        # Bornes exactes aux extrêmes : 0 cas → 0 %, tous les cas → 100 %
        self.assertEqual(self.js("() => CausesFrequentes.fourchette(0, 12).bas"), 0)
        self.assertEqual(self.js("() => CausesFrequentes.fourchette(12, 12).haut"), 1)

    def test_texte_de_la_fourchette_arrondi_demi_vers_le_haut(self):
        # Exemple du CDC : 7 cas sur 12 → entre 32 % et 81 %
        self.assertEqual(self.js("() => CausesFrequentes.texteFourchette(7, 12)"), "entre 32 % et 81 % des cas")
        couples = [(k, n) for n in range(1, 61) for k in range(0, n + 1)]
        textes = self.js("(couples) => couples.map(([k, n]) => CausesFrequentes.texteFourchette(k, n))", couples)
        for (k, n), texte in zip(couples, textes):
            with self.subTest(k=k, n=n):
                self.assertEqual(texte, texte_fourchette(k, n))
        self.assertEqual(self.js("() => CausesFrequentes.texteFourchette(0, 0)"), "")


class TestEncart(CasCauses):

    def test_peu_de_cas_mention_et_detail(self):
        self.charger(jeu({"GAR": 7, "JOI": 5}))
        encart = self.js(LIRE_ENCART_JS)
        # Lignes du lot 2 inchangées (une ligne par cause) ; mention du lot 2 toujours la première .note
        self.assertEqual(len(encart["lignes"]), 2)
        self.assertTrue(encart["lignes"][0].startswith("garniture usée — 7 cas sur 12 · "))
        self.assertEqual(encart["mention"], "Statistique de l'historique, pas un diagnostic")
        self.assertTrue(peu_de_cas([7, 5], 12))
        self.assertEqual(encart["piste"], MENTION_PISTE)
        self.assertEqual(encart["resume"], "Précision de ces chiffres")
        self.assertFalse(encart["ouvert"])                       # replié : on le déplie si l'on veut
        self.assertEqual(encart["fourchettes"], ["garniture usée : " + texte_fourchette(7, 12),
                                                 "joint détérioré : " + texte_fourchette(5, 12)])
        self.assertIn("95", encart["explication"])
        self.assertNotIn("autre", encart["explication"])          # pas de « et n autres » parasite

    def test_beaucoup_de_cas_pas_de_mention_mais_le_detail(self):
        repartition = {"GAR": 30, "JOI": 20, "ROU": 10}
        self.charger(jeu(repartition))
        encart = self.js(LIRE_ENCART_JS)
        self.assertFalse(peu_de_cas(repartition.values(), 60))
        self.assertIsNone(encart["piste"])
        self.assertEqual(encart["fourchettes"], ["garniture usée : " + texte_fourchette(30, 60),
                                                 "joint détérioré : " + texte_fourchette(20, 60),
                                                 "roulement hors service : " + texte_fourchette(10, 60)])

    def test_seuil_des_vingt_points(self):
        # Une seule cause, n cas : la demi-largeur passe sous 20 points quand n grandit
        for n in range(5, 40):
            with self.subTest(n=n):
                self.charger(jeu({"GAR": n // 2, "JOI": n - n // 2}))
                encart = self.js(LIRE_ENCART_JS)
                attendu = MENTION_PISTE if peu_de_cas([n // 2, n - n // 2], n) else None
                self.assertEqual(encart["piste"], attendu)

    def test_pas_assez_de_cas_ni_mention_ni_detail(self):
        self.charger(jeu({"GAR": 3}))
        texte = self.js("() => CausesFrequentes.encart('EQ-0001', 'FUI').textContent")
        self.assertIn("Pas encore assez de cas", texte)
        self.assertNotIn("Précision", texte)
        self.assertNotIn("piste", texte)


def lire_csv(dossier, nom):
    texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
    return [{k: (v or "").lstrip("'") for k, v in ligne.items()}
            for ligne in module_csv.DictReader(io.StringIO(texte), delimiter=";")]


class TestDemo(CasNavigateur):
    """Encart de la fiche OT du jeu de démo (mode serveur) : fourchettes = calcul Python sur les CSV."""

    def test_encart_de_la_fiche_ot_egal_au_calcul_python(self):
        scenarios = scenarios_demo()
        ot_id = scenarios["ot_fuite_garniture_po02"]
        with ServeurPrevo() as serveur:
            ots = lire_csv(serveur.dossier, "ordres_travail.csv")
            codes = {(c["famille"], c["code"]): c["libelle"] for c in lire_csv(serveur.dossier, "codes_defaillance.csv")}
            ot = next(o for o in ots if o["id"] == ot_id)
            cas = [o for o in ots if o["equipement_id"] == ot["equipement_id"] and o["type"].startswith("correctif")
                   and o["statut"] in CLOS and o["symptome_code"] == ot["symptome_code"] and o["cause_code"]]
            self.assertGreaterEqual(len(cas), 5)                  # portée « cet équipement »
            parcause = {}
            for o in cas:
                jour = (o["date_fin"] or o["date_cloture_tech"] or o["date_creation"])[:10]
                compte, dernier = parcause.get(o["cause_code"], (0, ""))
                parcause[o["cause_code"]] = (compte + 1, max(dernier, jour))
            # Tri de l'encart : nombre décroissant, puis dernier cas le plus récent, puis code
            ordre = sorted(parcause.items(), key=lambda e: e[0])
            ordre.sort(key=lambda e: e[1][1], reverse=True)
            ordre.sort(key=lambda e: e[1][0], reverse=True)
            ordre = ordre[:3]
            attendues = ["%s : %s" % (codes.get(("cause", code), code), texte_fourchette(nombre, len(cas)))
                         for code, (nombre, _) in ordre]

            page = self.page
            preregler_profil(self.contexte, "responsable")
            page.goto(serveur.url + "/#/ot/" + ot_id)
            attendre_pret(page)
            page.wait_for_load_state("networkidle")
            page.wait_for_function(
                "(id) => { const n = document.querySelector('.ot-fiche .ot-numero'); return n && n.textContent === id; }", arg=ot_id)
            page.click(".onglet[data-onglet='compte-rendu']")
            encart = ".panneau-onglet[data-onglet='compte-rendu'] .ot-causes .causes-frequentes"
            page.wait_for_selector(encart + " details.causes-precision")
            fourchettes = page.eval_on_selector_all(
                encart + " .causes-fourchettes > div", "(divs) => divs.map((d) => d.textContent.replace(/[ \\t\\n\\r]+/g, ' ').trim())")
            self.assertEqual(fourchettes, attendues)
            piste = page.locator(encart + " .causes-piste").count()
            self.assertEqual(piste, 1 if peu_de_cas([n for _, (n, _) in ordre], len(cas)) else 0)


if __name__ == "__main__":
    unittest.main()
