"""Coût de l'arrêt dans le rapport mensuel figé (Prévo 2.2, lot L5, T472 ; D188, CS174 ; conception L4-L5-L6 §3.2).

Le rapport (rapport-contenu.js) gagne une 4ᵉ tuile « Coût de l'arrêt » (data-cle="coutArret", même balisage que les
trois autres), un 2ᵉ Pareto (coût de l'arrêt du mois par équipement, 5 premiers), une entrée « Comprendre » et, quand le
calcul est incomplet, une entrée « Non calculable » (équipements non chiffrés, OT sans durée : 8 repères au plus, puis
« … et n autres »). Rien n'est estimé (D188).

Application complète en mode démo (file://), données remplacées par le jeu d'essai des règles (tests/
test_cout_arret_regles.py, mars 2026 : 591,62 €) complété de mois choisis :
    - juillet et août 2026 : deux mois complets (300,00 € puis 450,00 €) : seule comparaison chiffrée ;
    - septembre 2026 : des pannes, aucun équipement chiffré : « non chiffré » ;
    - octobre 2026 : 10 équipements non chiffrés et 2 OT sans durée : 8 repères puis « … et 4 autres ».
Familles :
    au centime     la tuile vaut Indicateurs.coutArret du mois au centime (et le calcul Python `decimal`) : données
                   du rapport, document figé, courriel ; Pareto par coût ; anglais (D156) ;
    comparaison    seulement entre deux mois complets, sinon « non comparable : coût incomplet » ; aucune panne :
                   « 0,00 € » et « aucun arrêt ce mois » ;
    non chiffré    listé, jamais estimé : tuile, Pareto vide, liste plafonnée à 8 repères ;
    page unique    le document figé tient sur une page A4 : démo chargée (pannes non chiffrées ajoutées) avec un
                   commentaire de six phrases proposé par l'IA, le cas le plus long.

Lancer depuis la racine du projet (navigateur : au travers du verrou) :
    py -X utf8 -m unittest discover -s tests -p "test_rapport_cout_arret.py" -v
"""
import html
import re
import shutil
import tempfile
import unittest
import urllib.parse
from pathlib import Path

from commun import CasNavigateur, attendre_pret, preregler_profil, url_fichier
from test_cout_arret_regles import CLOS, DEMANDES, ENTETE_OT, EQUIPEMENTS, LOCALISATIONS, ORDRES, centimes_decimal, csv

AUJOURDHUI = "2026-10-20"
MAINTENANT = "2026-10-20 09:00"

# Équipements sans coût horaire pour octobre (repères NC-01 à NC-10) ; le jeu des règles garde ses neuf équipements.
NON_CHIFFRES_OCTOBRE = ["EQ-%04d;NC-%02d;B;en service;LOC-0003;1;" % (20 + rang, rang + 1) for rang in range(10)]
ORDRES_EN_PLUS = [
    # Juillet et août : mois complets, PO-01 à 150 €/h : 2 h → 300,00 € ; 3 h → 450,00 € (+ 50 %)
    "OT-2026-0101;;EQ-0001;correctif immédiat;%s;2026-07-07 08:00;1;2" % CLOS,
    "OT-2026-0102;;EQ-0001;correctif différé;%s;2026-08-11 08:00;1;3" % CLOS,
    # Septembre : une panne, sur un équipement sans coût horaire (PO-03) : non chiffré
    "OT-2026-0103;;EQ-0003;correctif immédiat;%s;2026-09-08 08:00;1;2" % CLOS,
    # Octobre : PO-02 chiffré (1 h × 87,35 €), dix équipements non chiffrés (1 h à 10 h), deux OT de PO-01 sans durée
    "OT-2026-0104;;EQ-0002;correctif immédiat;%s;2026-10-01 08:00;1;1" % CLOS,
] + ["OT-2026-%04d;;EQ-%04d;correctif immédiat;%s;2026-10-%02d 08:00;1;%d" % (110 + rang, 20 + rang, CLOS, 2 + rang, rang + 1)
     for rang in range(10)] + [
    "OT-2026-0120;;EQ-0001;correctif immédiat;En cours;2026-10-15 08:00;1;",
    "OT-2026-0121;;EQ-0001;correctif différé;En attente de pièces;2026-10-16 08:00;1;",
]


def tables_du_jeu():
    equipements = EQUIPEMENTS.rstrip("\r\n") + "\r\n" + "\r\n".join(NON_CHIFFRES_OCTOBRE) + "\r\n"
    ordres = ORDRES.rstrip("\r\n") + "\r\n" + "\r\n".join(ORDRES_EN_PLUS) + "\r\n"
    assert ordres.startswith(ENTETE_OT)
    return {"localisations": LOCALISATIONS, "equipements": equipements, "demandes": DEMANDES, "ordres_travail": ordres}


def blancs(texte):
    """Espaces insécables (Intl : « 591,62 € », « 4 h ») ramenées à l'espace simple, entités HTML décodées."""
    return html.unescape(texte).replace("\u00a0", " ").replace("\u202f", " ")


# Commentaire de six phrases (le plus long que l'IA propose : « trois à six phrases »), avec la mention de l'IA.
COMMENTAIRE = ("La disponibilité baisse légèrement ce mois-ci, surtout à cause du long arrêt de la presse PO-01. "
               "Le coût de maintenance recule par rapport au mois précédent, grâce à moins de pièces sorties. "
               "La part du préventif diminue : plusieurs visites ont été reportées faute de techniciens disponibles. "
               "Le coût de l'arrêt reste partiel tant que trois équipements n'ont pas de coût horaire saisi. "
               "Un contrôle réglementaire est en retard sur le chariot élévateur et une réserve reste à lever sur le "
               "réservoir d'air. Points à examiner : le remplacement du purgeur, la commande des articles critiques "
               "et la planification des visites reportées.")


class CasRapportCoutArret(CasNavigateur):

    def ouvrir(self, horloge="2026-10-20T09:00:00", tables=None):
        self.contexte.clock.set_fixed_time(horloge)
        preregler_profil(self.contexte, "responsable", "Responsable")
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        if tables:
            self.page.evaluate("""async (tables) => {
              Donnees.initialiser(StockageDemo.creer(tables), { poste: 'Poste test', profil: 'Responsable test' });
              await Donnees.chargerTout();
            }""", tables)

    def donnees(self, mois, langue=None):
        return self.page.evaluate("""async ([mois, jour, maintenant, langue]) => {
            if (langue) await I18n.chargerLangue(langue);
            const r = Rapport.donnees(mois, jour, maintenant, langue || undefined);
            return { tuiles: r.tuiles, coutArret: r.coutArret, paretoCout: r.paretoCout, nonCalculables: r.nonCalculables,
                     comprendre: r.comprendre, courriel: r.courriel.corps, faits: r.faits }; }""",
                                  [mois, AUJOURDHUI, MAINTENANT, langue])

    def document(self, mois, commentaire=None, aujourdhui=AUJOURDHUI):
        options = {"aujourdhui": aujourdhui, "maintenant": MAINTENANT}
        if commentaire:
            options["commentaire"] = {"texte": commentaire, "aideIa": True}
        return self.page.evaluate("([mois, options]) => Rapport.html(mois, options)", [mois, options])

    def regle(self, mois):
        """Indicateurs.coutArret du mois : la règle de T470, référence de la tuile."""
        return self.page.evaluate("(mois) => Indicateurs.coutArret(Indicateurs.periodeDuMois(mois))", mois)

    def euro(self, centimes):
        return blancs(self.page.evaluate("(c) => UI.euro(c / 100, 2)", centimes))

    @staticmethod
    def tuile(donnees):
        tuiles = [t for t in donnees["tuiles"] if t["cle"] == "coutArret"]
        assert len(tuiles) == 1, donnees["tuiles"]
        return tuiles[0]

    @staticmethod
    def bloc_tuile(document, cle):
        bloc = re.search(r'<div class="tuile" data-cle="%s">(.*?)</div>\s*(?:<div class="tuile"|</section>)' % cle, document, re.S)
        return blancs(bloc.group(1)) if bloc else None


class TestAuCentime(CasRapportCoutArret):

    def setUp(self):
        super().setUp()
        self.ouvrir(tables=tables_du_jeu())

    def test_donnees_du_rapport_egales_a_la_regle_au_centime(self):
        r = self.donnees("2026-03")
        regle = self.regle("2026-03")
        attendu = sum([centimes_decimal(["1.5", "2.25"], "150"), centimes_decimal(["0.3333"], "87.35"),
                       centimes_decimal(["0.05"], "0.10")])
        self.assertEqual(attendu, 59162)
        self.assertEqual(regle["totalCentimes"], attendu)
        self.assertEqual(r["coutArret"]["totalCentimes"], attendu)
        self.assertEqual({k: v for k, v in r["coutArret"].items() if k != "tendance"}, regle)
        tuile = self.tuile(r)
        self.assertEqual([t["cle"] for t in r["tuiles"]], ["disponibilite", "cout", "partPreventif", "coutArret"])
        self.assertEqual(tuile["libelle"], "Coût de l'arrêt")
        self.assertEqual(tuile["valeur"], 591.62)
        self.assertEqual(blancs(tuile["texteValeur"]), "591,62 €")
        self.assertEqual(blancs(tuile["texteValeur"]), self.euro(regle["totalCentimes"]))
        self.assertEqual(tuile["precision"], "Partiel : 1 équipement non chiffré, 1 OT sans durée")
        self.assertFalse(tuile["hausseFavorable"])
        self.assertEqual(r["coutArret"]["tendance"], tuile["tendance"])
        # Février n'est pas couvert par l'historique (premier OT le 27/02) : règle commune aux quatre tuiles
        self.assertEqual(tuile["tendance"]["precedent"]["texte"], "non comparable avec février 2026 (historique trop court)")
        # Pareto par coût : les 5 premiers, au centime
        self.assertEqual([(l["repere"], l["centimes"]) for l in r["paretoCout"]], [("PO-01", 56250), ("PO-02", 2911), ("PO-04", 1)])
        self.assertEqual(sum(l["centimes"] for l in r["paretoCout"]), attendu)
        # Comprendre : la formule ; Non calculable : ce qui manque, jamais estimé
        comprendre = dict(r["comprendre"])
        self.assertIn("durée d'arrêt × coût d'une heure d'arrêt", comprendre["Coût de l'arrêt"])
        self.assertIn("Rien n'est estimé", comprendre["Coût de l'arrêt"])
        self.assertIn({"libelle": "Coût de l'arrêt — non chiffré",
                       "raison": "PO-03 (4\u00a0h d'arrêt) ; OT sans durée : OT-2026-0003 (PO-01, non clôturé)"},
                      r["nonCalculables"])
        # Courriel : la tuile, sa précision et sa comparaison
        self.assertIn("• Coût de l'arrêt : 591,62 € — Partiel : 1 équipement non chiffré, 1 OT sans durée "
                      "(non comparable avec février 2026 (historique trop court))", blancs(r["courriel"]))

    def test_document_fige_tuile_pareto_comprendre_non_calculable(self):
        document = self.document("2026-03")
        self.assertEqual(re.findall(r'<div class="tuile" data-cle="([^"]+)">', document),
                         ["disponibilite", "cout", "partPreventif", "coutArret"])
        self.assertIn("grid-template-columns: repeat(4, 1fr)", document)
        tuile = self.bloc_tuile(document, "coutArret")
        self.assertIsNotNone(tuile)
        self.assertRegex(tuile, r'^\s*<div class="lib">Coût de l\'arrêt</div><div class="val">591,62 €</div>')
        self.assertIn('<div class="raison">Partiel : 1 équipement non chiffré, 1 OT sans durée</div>', tuile)
        self.assertEqual(re.search(r'<div class="val">([^<]*)</div>', tuile).group(1), self.euro(self.regle("2026-03")["totalCentimes"]))
        texte = blancs(document)
        self.assertIn("<figcaption>Coût de l'arrêt du mois par équipement (€)</figcaption>", texte)
        figure = texte.split("Coût de l'arrêt du mois par équipement (€)</figcaption>")[1].split("</figure>")[0]
        for etiquette in ("562,50 €", "29,11 €", "0,01 €", "PO-01", "PO-02", "PO-04"):
            self.assertIn(etiquette, figure)
        self.assertIn("<figcaption>Durée d'arrêt du mois par équipement (heures)</figcaption>", texte)
        self.assertEqual(texte.count("<figure>"), 3)
        self.assertIn("<dt>Coût de l'arrêt :</dt>", texte)
        self.assertIn("<li><b>Coût de l'arrêt — non chiffré</b> : PO-03 (4 h d'arrêt) ; OT sans durée : OT-2026-0003 "
                      "(PO-01, non clôturé)</li>", texte)
        lien = re.search(r'href="(mailto:[^"]*)"', document).group(1)
        self.assertIn("Coût de l'arrêt : 591,62 € — Partiel", blancs(urllib.parse.unquote(lien.replace("&amp;", "&"))))
        for interdit in ("NaN", "Infinity", "undefined"):
            self.assertNotIn(interdit, texte)

    def test_rapport_en_anglais(self):
        r = self.donnees("2026-03", "en")
        tuile = self.tuile(r)
        self.assertEqual(tuile["libelle"], "Downtime cost")
        self.assertEqual(blancs(tuile["texteValeur"]), "€591.62")
        self.assertEqual(tuile["precision"], "Partial: 1 equipment not costed, 1 WO with no duration")
        self.assertIn({"libelle": "Downtime cost — not costed",
                       "raison": "PO-03 (4\u00a0h of downtime); WOs with no duration: OT-2026-0003 (PO-01, not closed)"},
                      r["nonCalculables"])
        self.assertIn("Downtime cost", dict(r["comprendre"]))
        self.assertEqual(self.page.evaluate("I18n.langue"), "fr")


class TestComparaisonEtNonChiffre(CasRapportCoutArret):

    def setUp(self):
        super().setUp()
        self.ouvrir(tables=tables_du_jeu())

    def test_comparaison_seulement_entre_deux_mois_complets(self):
        aout = self.tuile(self.donnees("2026-08"))
        self.assertEqual((aout["valeur"], aout["precedent"], aout["precision"]), (450, 300, ""))
        self.assertEqual(aout["tendance"]["precedent"], {"sens": "hausse", "texte": "en hausse de 50 % par rapport à juillet 2026"})
        self.assertEqual(aout["tendance"]["annee"]["texte"], "non comparable avec août 2025 (historique trop court)")
        tuile = self.bloc_tuile(self.document("2026-08"), "coutArret")
        self.assertIn('<span class="feu mauvais">▲ en hausse de 50 % par rapport à juillet 2026 (à surveiller)</span>', tuile)
        self.assertNotIn('class="raison"', tuile)
        # Avril (incomplet) contre mars (incomplet), septembre (non chiffré) contre août (complet) : pas de chiffre
        avril = self.tuile(self.donnees("2026-04"))
        self.assertEqual(avril["tendance"]["precedent"], {"sens": None, "texte": "non comparable avec mars 2026 : coût incomplet"})
        septembre = self.tuile(self.donnees("2026-09"))
        self.assertEqual(septembre["tendance"]["precedent"], {"sens": None, "texte": "non comparable avec août 2026 : coût incomplet"})
        # Juin contre mai : deux mois sans panne, complets : 0,00 €, « aucun arrêt ce mois », stable
        juin = self.tuile(self.donnees("2026-06"))
        self.assertEqual((juin["valeur"], blancs(juin["texteValeur"]), juin["precision"]), (0, "0,00 €", "aucun arrêt ce mois"))
        self.assertEqual(juin["tendance"]["precedent"], {"sens": "stable", "texte": "stable par rapport à mai 2026"})
        document = blancs(self.document("2026-06"))
        self.assertNotIn("Coût de l'arrêt —", document)                           # rien de non calculable
        figure = document.split("Coût de l'arrêt du mois par équipement (€)</figcaption>")[1].split("</figure>")[0]
        self.assertEqual(figure, "<p>Aucun arrêt ce mois-ci.</p>")

    def test_pannes_sans_aucun_equipement_chiffre_non_chiffre_jamais_estime(self):
        r = self.donnees("2026-09")
        tuile = self.tuile(r)
        self.assertIsNone(tuile["valeur"])
        self.assertEqual(tuile["texteValeur"], "non chiffré")
        self.assertEqual((tuile["raison"], tuile["precision"]), ("1 équipement non chiffré", "1 équipement non chiffré"))
        self.assertEqual(r["paretoCout"], [])
        self.assertEqual(r["coutArret"]["totalCentimes"], 0)
        self.assertIn({"libelle": "Coût de l'arrêt — non chiffré", "raison": "PO-03 (2\u00a0h d'arrêt)"}, r["nonCalculables"])
        self.assertNotIn("Coût de l'arrêt", [element["libelle"] for element in r["nonCalculables"]])
        self.assertIn("• Coût de l'arrêt : non chiffré — 1 équipement non chiffré (", blancs(r["courriel"]))
        document = blancs(self.document("2026-09"))
        tuile_html = self.bloc_tuile(document, "coutArret")
        self.assertIn('<div class="val">non chiffré</div>', tuile_html)
        self.assertNotIn("0,00", tuile_html)
        figure = document.split("Coût de l'arrêt du mois par équipement (€)</figcaption>")[1].split("</figure>")[0]
        self.assertEqual(figure, "<p>Aucun coût d'arrêt chiffré ce mois-ci.</p>")

    def test_huit_reperes_au_plus_puis_et_n_autres(self):
        r = self.donnees("2026-10")
        tuile = self.tuile(r)
        self.assertEqual(blancs(tuile["texteValeur"]), "87,35 €")
        self.assertEqual(tuile["precision"], "Partiel : 10 équipements non chiffrés, 2 OT sans durée")
        regle = self.regle("2026-10")
        self.assertEqual((len(regle["nonChiffres"]), len(regle["sansDuree"])), (10, 2))
        entree = [e for e in r["nonCalculables"] if e["libelle"].startswith("Coût de l'arrêt")]
        self.assertEqual(len(entree), 1)
        raison = blancs(entree[0]["raison"])
        # Les plus longs arrêts d'abord : NC-10 (10 h) … NC-03 (3 h) ; NC-02, NC-01 et les deux OT sans durée restent
        attendu = ", ".join(["NC-10 (10 h d'arrêt)"] + ["NC-%02d (%d h)" % (n, n) for n in range(9, 2, -1)])
        self.assertEqual(raison, attendu + " … et 4 autres (liste complète : écran Indicateurs)")
        self.assertEqual(len(re.findall(r"\bNC-\d\d\b", raison)), 8)

    def test_ot_sans_duree_seuls(self):
        # Les deux OT de PO-01 sans durée, sans équipement non chiffré : « Coût de l'arrêt — OT sans durée »
        self.page.evaluate("""async () => { await Donnees.modifier('ordres_travail', (lignes) => {
            lignes.forEach((ot) => { if (/^OT-2026-01(0[4]|1\\d)$/.test(ot.id) && ot.id !== 'OT-2026-0110') ot.statut = 'Annulé'; });
            lignes.forEach((ot) => { if (ot.id === 'OT-2026-0110') ot.equipement_id = 'EQ-0002'; }); }); }""")
        r = self.donnees("2026-10")
        tuile = self.tuile(r)
        self.assertEqual(tuile["precision"], "Partiel : 2 OT sans durée")
        self.assertIn({"libelle": "Coût de l'arrêt — OT sans durée",
                       "raison": "OT-2026-0120 (PO-01, non clôturé), OT-2026-0121 (PO-01, non clôturé)"}, r["nonCalculables"])


class TestPageUnique(CasRapportCoutArret):

    def test_demo_avec_pannes_non_chiffrees_et_commentaire_de_six_phrases_une_page_a4(self):
        # Démo à sa date de référence (dates non décalées), rapport de septembre 2026 : douze pannes de plus sur des
        # équipements sans coût horaire (trois sans durée), commentaire de six phrases proposé par l'IA.
        self.ouvrir(horloge="2026-10-19T09:00:00")
        self.page.evaluate("""async () => {
          const sansCout = Donnees.lignes('equipements').filter((e) => !String(e.cout_arret_h || '').trim()).slice(0, 12);
          await Donnees.modifier('ordres_travail', (lignes) => {
            sansCout.forEach((e, rang) => { const k = rang + 1;
              lignes.push({ id: 'OT-2026-' + (9000 + k), equipement_id: e.id, type: 'correctif immédiat',
                statut: k <= 3 ? 'En cours' : 'Clôturé techniquement', date_creation: '2026-09-' + String(k + 1).padStart(2, '0') + ' 08:00',
                arret_production: '1', duree_arret_h: k <= 3 ? '' : String(k / 2), titre: 'Panne (test T472) ' + k }); });
          }); }""")
        regle = self.regle("2026-09")
        self.assertGreater(len(regle["nonChiffres"]) + len(regle["sansDuree"]), 8)
        self.assertTrue(regle["parEquipement"])                     # la démo chiffre CP-01 (rôle de T475)
        document = self.document("2026-09", COMMENTAIRE, "2026-10-19")
        tuile = self.bloc_tuile(document, "coutArret")
        self.assertEqual(re.search(r'<div class="val">([^<]*)</div>', tuile).group(1), self.euro(regle["totalCentimes"]))
        self.assertIn("Partiel : ", tuile)
        self.assertIn("(liste complète : écran Indicateurs)", blancs(document))
        self.assertIn("Commentaire rédigé avec l'aide de l'IA", blancs(document))
        dossier = Path(tempfile.mkdtemp(prefix="rapport-cout-arret-"))
        self.addCleanup(shutil.rmtree, dossier, True)
        fichier = dossier / "rapport-mensuel-2026-09.html"
        fichier.write_text(document, encoding="utf-8")
        page = self.contexte.new_page()
        self.surveiller(page)
        page.goto(fichier.resolve().as_uri())
        pdf = page.pdf(prefer_css_page_size=True)
        self.assertEqual(len(re.findall(rb"/Type\s*/Page[^s]", pdf)), 1, "le rapport doit tenir sur une page A4")


if __name__ == "__main__":
    unittest.main()
