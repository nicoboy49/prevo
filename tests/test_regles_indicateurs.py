"""Tests des règles des indicateurs (ARCHITECTURE.md §15.3 ; CDC du lot 3, D35 et D36 ; tâche T43).

Deux familles :
    - jeu construit À LA MAIN dans ce fichier (valeurs attendues calculées à la main dans les
      commentaires) : périodes, pannes (DI d'origine, arrêt, annulées, hors période), temps requis
      (heures inconnues, mise en service dans la période, rebut), MTBF, MTTR, disponibilité, attente
      de pièces lue dans le journal (historique complet ou non, motif accentué, plafond à la durée
      d'arrêt, sortie absente), part et respect du préventif (déclencheurs date et compteur), délais
      de prise en charge par priorité, coûts (égaux à Ordres.cout), valeur du stock, Pareto, causes,
      heures par mois, filtres criticité et atelier, aucun NaN ni Infinity ;
    - jeu de démo (donnees/demo, sans décalage, aujourd'hui = date de référence) : pour les 3
      équipements du rôle `equipements_calcul_main`, sur 12 mois glissants, temps requis, pannes,
      durée d'arrêt, MTBF, MTTR, disponibilité, attente de pièces et coût = un CALCUL PYTHON
      INDÉPENDANT écrit ici à partir des CSV (scénario du brief « indicateurs identiques à un calcul
      à la main ») ; le coût de chaque OT clôturé de la démo = Ordres.cout(ot).total.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_regles_indicateurs.py" -v
"""
import calendar
import csv as module_csv
import datetime
import io
import json
import math
import re
import unicodedata
import unittest
from pathlib import Path

from commun import CasNavigateur, charger_scripts, scenarios_demo

RACINE = Path(__file__).resolve().parent.parent
SCRIPTS = [
    "js/lib/papaparse.min.js", "js/schema.js", "js/donnees.js", "js/stockage-demo.js", "js/interface.js",
    "js/modules/accueil.js", "js/modules/ordres-regles.js", "js/modules/planning-regles.js",
    "js/modules/indicateurs-regles.js", "js/modules/indicateurs-series.js",
]
AUJOURDHUI = "2026-10-20"
MARS = ["du-au", AUJOURDHUI, "2026-03-01", "2026-03-31"]


def csv(entete, lignes):
    return "\r\n".join([entete] + list(lignes)) + "\r\n"


PARAMETRES = csv("cle;valeur", ["tolerance_preventif_pct;10", "delai_p1_h;1", "delai_p2_h;24", "delai_p3_h;168"])
LOCALISATIONS = csv("id;libelle;parent_id;type", [
    "LOC-0001;Site;;site", "LOC-0002;Atelier A;LOC-0001;atelier", "LOC-0003;Ligne A1;LOC-0002;ligne",
    "LOC-0004;Atelier B;LOC-0001;atelier"])
EQUIPEMENTS = csv("id;repere;criticite;statut;heures_fonct_jour;date_mes;localisation_id;actif", [
    "EQ-0001;PO-01;A;en service;10;2020-01-01;LOC-0003;1",
    "EQ-0002;PO-02;B;en service;;2020-01-01;LOC-0003;1",          # heures inconnues
    "EQ-0003;PO-03;B;en service;8;2026-10-11;LOC-0004;1",         # mis en service le 11/10/2026
    "EQ-0004;PO-04;C;rebut;8;2020-01-01;LOC-0004;1"])
TECHNICIENS = csv("id;nom;prenom;taux_horaire;capacite_h_semaine;actif", [
    "TEC-0001;Moreau;Julien;40;35;1", "TEC-0002;Benali;Karim;35.5;35;1"])
DEMANDES = csv("id;date_heure;equipement_id;statut;ot_id", [
    "DI-2026-0001;2026-03-01 08:00;EQ-0001;Acceptée;OT-2026-0001",
    "DI-2026-0002;2026-03-01 18:00;EQ-0001;Regroupée;OT-2026-0001",   # regroupée après coup : ne date pas la panne
    "DI-2026-0003;2026-03-10 07:00;EQ-0001;Acceptée;OT-2026-0002",    # OT-0002 sans di_id : la DI acceptée compte
    "DI-2026-0004;2026-03-10 11:00;EQ-0001;Regroupée;OT-2026-0002",
    "DI-2026-0005;2026-03-21 08:00;EQ-0001;Regroupée;OT-2026-0003"])  # seule DI de OT-0003 : regroupée, ne date pas
CODES = csv("id;famille;code;libelle", ["CD-0001;cause;C01;Roulement usé", "CD-0002;cause;C02;Joint fuyard"])
GAMMES = csv("id;equipement_id;libelle;declencheur;periodicite_jours;compteur_id;periodicite_unites;actif", [
    "GAM-0001;EQ-0001;Graissage;date;30;;;1",
    "GAM-0002;EQ-0001;Vidange 500 h;compteur;;CPT-0001;500;1",     # 500 h / 10 h par jour = 50 jours
    "GAM-0003;EQ-0001;Sans période;date;;;;1"])
COMPTEURS = csv("id;equipement_id;libelle;unite", ["CPT-0001;EQ-0001;Heures;h"])
ENTETE_OT = ("id;di_id;gamme_id;equipement_id;type;priorite;statut;date_creation;date_prevue;date_debut;date_fin;"
             "arret_production;duree_arret_h;cause_code;cout_soustraitance")
ORDRES = csv(ENTETE_OT, [
    # Pannes de PO-01 en mars : 3 (la 1re datée par sa DI : 01/03 08:00)
    "OT-2026-0001;DI-2026-0001;;EQ-0001;correctif différé;P2;Clôturé techniquement;2026-03-01 10:00;2026-03-02;2026-03-01 12:00;2026-03-02 12:00;1;20;C01;100",
    "OT-2026-0002;;;EQ-0001;correctif immédiat;P1;Clôturé administrativement;2026-03-10 08:00;2026-03-10;2026-03-10 09:00;2026-03-10 14:00;1;6;C01;",
    "OT-2026-0003;;;EQ-0001;correctif immédiat;P1;En cours;2026-03-20 08:00;2026-03-20;2026-03-20 08:30;;1;;;",
    # Pas des pannes : sans arrêt, annulée ; hors période (28/02)
    "OT-2026-0004;;;EQ-0001;correctif différé;P3;Clôturé techniquement;2026-03-15 08:00;2026-03-16;;2026-03-16 10:00;0;;;",
    "OT-2026-0005;;;EQ-0001;correctif différé;P3;Annulé;2026-03-16 08:00;2026-03-17;;;1;3;;",
    "OT-2026-0006;;;EQ-0001;correctif différé;P2;Clôturé techniquement;2026-02-28 23:00;2026-03-01;;2026-03-01 05:00;1;2;C02;",
    # Autres équipements
    "OT-2026-0007;;;EQ-0002;correctif différé;P2;Clôturé techniquement;2026-03-05 08:00;2026-03-05;;2026-03-05 12:00;1;4;C02;",
    "OT-2026-0008;;;EQ-0003;correctif immédiat;P1;Clôturé techniquement;2026-10-15 08:00;2026-10-15;;2026-10-15 12:00;1;;;",
    "OT-2026-0009;;;EQ-0001;correctif différé;P2;Clôturé techniquement;2026-04-01 06:00;2026-04-01;2026-04-01 07:00;2026-04-01 18:00;1;;;",
    # Préventif (tolérance 10 % : 3 jours pour GAM-0001, 5 jours pour GAM-0002)
    "OT-2026-0010;;GAM-0001;EQ-0001;préventif systématique;P3;Clôturé techniquement;2026-03-01 08:00;2026-03-05;2026-03-07 08:00;2026-03-07 10:00;0;;;",
    "OT-2026-0011;;;EQ-0001;réglementaire;P3;Clôturé techniquement;2026-03-06 08:00;2026-03-06;;2026-03-06 10:00;0;;;",
    "OT-2026-0012;;GAM-0001;EQ-0001;préventif systématique;P3;Clôturé techniquement;2026-03-15 08:00;2026-03-20;2026-03-24 08:00;2026-03-24 10:00;0;;;",   # fini à J+4 : hors tolérance (3 j)
    "OT-2026-0013;;GAM-0002;EQ-0001;préventif systématique;P3;Planifié;2026-03-20 08:00;2026-03-24;;;0;;;",
    "OT-2026-0014;;GAM-0001;EQ-0001;préventif systématique;P3;Clôturé techniquement;2026-03-25 08:00;2026-03-30;;2026-03-30 10:00;0;;;",
    "OT-2026-0015;;GAM-0003;EQ-0001;préventif systématique;P3;Clôturé techniquement;2026-03-02 08:00;2026-03-10;;2026-03-10 10:00;0;;;",
    "OT-2026-0016;;;EQ-0001;préventif conditionnel;P3;Clôturé techniquement;2026-03-02 08:00;2026-03-12;;2026-03-12 10:00;0;;;",
    "OT-2026-0017;;GAM-0001;EQ-0001;préventif systématique;P3;Annulé;2026-03-02 08:00;2026-03-12;;;0;;;",
    # Équipement au rebut : son coût compte quand même dans le coût global (relecture)
    "OT-2026-0018;;;EQ-0004;amélioration;P3;Clôturé techniquement;2026-03-18 08:00;2026-03-20;;2026-03-20 10:00;0;;;",
    # Début saisi avant la création : délai négatif, exclu des délais de prise en charge
    "OT-2026-0019;;;EQ-0001;correctif différé;P2;Clôturé techniquement;2026-03-21 10:00;2026-03-21;2026-03-21 09:00;2026-03-21 11:00;0;;;",
])
OT_TEMPS = csv("id;ot_id;technicien_id;date;heures", [
    "OTT-000001;OT-2026-0001;TEC-0001;2026-03-01;4", "OTT-000002;OT-2026-0001;TEC-0001;2026-02-27;1",
    "OTT-000003;OT-2026-0002;TEC-0002;2026-03-10;3", "OTT-000004;OT-2026-0010;TEC-0001;2026-03-05;2",
    "OTT-000005;OT-2026-0011;TEC-0001;2026-03-06;1", "OTT-000006;OT-2026-0005;TEC-0001;2026-03-16;5",
    "OTT-000007;OT-2026-0018;TEC-0001;2026-03-20;1"])
ARTICLES = csv("id;reference;designation;prix_unitaire;actif", [
    "ART-0001;ROU-001;Roulement;15.5;1", "ART-0002;DIV-001;Sans prix;;1", "ART-0003;DIV-002;Inactif;10;0"])
MOUVEMENTS = csv("id;date;article_id;type;quantite;ot_id", [
    "MVT-000001;2026-01-01 08:00;ART-0001;inventaire;10;", "MVT-000002;2026-03-01 13:00;ART-0001;sortie;2;OT-2026-0001",
    "MVT-000003;2026-03-02 11:00;ART-0001;retour;1;OT-2026-0001"])


def journal():
    lignes = []

    def ajouter(date_heure, ot, action):
        lignes.append("J-%04d;%s;Poste test;Responsable;ordres_travail;%s;%s" % (len(lignes) + 1, date_heure, ot, action))

    # Format réel du journal (Donnees.modifier) : « <description> — <action> ».
    # OT-0001 : historique complet, 18 h d'attente de pièce (une autre attente ne compte pas)
    ajouter("2026-03-01 10:00", "OT-2026-0001", "création — acceptation de DI-2026-0001")
    ajouter("2026-03-01 12:00", "OT-2026-0001", "modification : statut, date_debut — statut Planifié → En cours")
    ajouter("2026-03-01 14:00", "OT-2026-0001", "modification : statut, motif_attente — statut En cours → En attente : Pièce : roulement commandé")
    ajouter("2026-03-02 08:00", "OT-2026-0001", "modification : statut — statut En attente → En cours")
    ajouter("2026-03-02 09:00", "OT-2026-0001", "modification : statut, motif_attente — statut En cours → En attente : Arrêt de production")
    ajouter("2026-03-02 10:00", "OT-2026-0001", "modification : statut — statut En attente → En cours")
    ajouter("2026-03-02 12:00", "OT-2026-0001", "modification : statut, date_cloture_tech — statut En cours → Clôturé techniquement")
    # OT-0002 : 10 h d'attente « PIÈCE » (casse, accent), plafonnées à sa durée d'arrêt (6 h)
    ajouter("2026-03-10 08:00", "OT-2026-0002", "création — création de l'OT (urgence)")
    ajouter("2026-03-10 10:00", "OT-2026-0002", "modification : statut, motif_attente — statut En cours → En attente : PIÈCE manquante")
    ajouter("2026-03-10 20:00", "OT-2026-0002", "modification : statut — statut En attente → En cours")
    # OT-0009 : action sans description (texte brut, accepté aussi) ; attente sans sortie → jusqu'à
    # la date de fin (08:00 → 18:00 = 10 h), sans plafond
    ajouter("2026-04-01 06:00", "OT-2026-0009", "création de l'OT (manuel)")
    ajouter("2026-04-01 08:00", "OT-2026-0009", "statut En cours → En attente : Pièces à recevoir")
    # OT-0007 : pas de création au journal → historique incomplet
    ajouter("2026-03-05 09:00", "OT-2026-0007", "modification : statut — statut Créé → En cours")
    return csv("id;date_heure;poste;profil;table;id_ligne;action", lignes)


def jeu_de_test():
    return {"parametres": PARAMETRES, "localisations": LOCALISATIONS, "equipements": EQUIPEMENTS,
            "techniciens": TECHNICIENS, "demandes": DEMANDES, "codes_defaillance": CODES, "gammes": GAMMES,
            "compteurs": COMPTEURS, "ordres_travail": ORDRES, "ot_temps": OT_TEMPS, "articles": ARTICLES,
            "mouvements_stock": MOUVEMENTS, "journal": journal()}


class CasIndicateurs(CasNavigateur):

    def charger(self, tables):
        charger_scripts(self.page, SCRIPTS)
        self.page.evaluate("""async (tables) => {
          Donnees.initialiser(StockageDemo.creer(tables), { poste: 'Poste test', profil: 'Responsable test' });
          await Donnees.chargerTout();
          window.periodeDe = (code, jour, du, au) => Indicateurs.periode(code, jour, du, au);
        }""", tables)

    def js(self, script, argument=None):
        return self.page.evaluate(script, argument)


class TestPeriodes(CasIndicateurs):

    def setUp(self):
        super().setUp()
        self.charger(jeu_de_test())

    def test_periodes(self):
        cas = [
            (["mois", AUJOURDHUI], ("2026-10-01", "2026-10-20")),
            (["mois-precedent", AUJOURDHUI], ("2026-09-01", "2026-09-30")),
            (["3-mois", AUJOURDHUI], ("2026-07-21", "2026-10-20")),
            (["12-mois", AUJOURDHUI], ("2025-10-21", "2026-10-20")),
            (["inconnu", AUJOURDHUI], ("2025-10-21", "2026-10-20")),
            (["du-au", AUJOURDHUI, "2026-05-10", "2026-03-01"], ("2026-03-01", "2026-05-10")),
            (["3-mois", "2026-03-31"], ("2026-01-01", "2026-03-31")),
            (["mois-precedent", "2026-03-31"], ("2026-02-01", "2026-02-28")),
        ]
        for arguments, (debut, fin) in cas:
            with self.subTest(arguments=arguments):
                p = self.js("(a) => periodeDe(...a)", arguments)
                self.assertEqual((p["debut"], p["fin"]), (debut, fin))
                self.assertTrue(p["libelle"])


class TestFiabilite(CasIndicateurs):

    def setUp(self):
        super().setUp()
        self.charger(jeu_de_test())

    def equipement(self, equipement_id, periode=MARS):
        return self.js("([id, p]) => Indicateurs.parEquipement(id, periodeDe(...p))", [equipement_id, periode])

    def test_pannes_datees_par_la_di_et_filtrees(self):
        pannes = self.js("(p) => Indicateurs.pannes(periodeDe(...p), { equipementId: 'EQ-0001' }).map((x) => [x.ot.id, x.date, x.duree])", MARS)
        # OT-0003 n'a qu'une DI regroupée (21/03) : datée par sa création (20/03), relecture
        self.assertEqual(pannes, [["OT-2026-0001", "2026-03-01 08:00", 20], ["OT-2026-0002", "2026-03-10 07:00", 6],
                                  ["OT-2026-0003", "2026-03-20 08:00", None]])

    def test_mtbf_mttr_disponibilite_duree_d_arret_d_un_equipement(self):
        r = self.equipement("EQ-0001")
        self.assertEqual(r["tempsRequis"]["valeur"], 310)                  # 10 h × 31 jours
        self.assertEqual(r["pannes"]["valeur"], 3)
        self.assertEqual(r["dureeArret"]["valeur"], 26)                    # 20 + 6 (la panne en cours exclue)
        self.assertEqual(r["dureeArret"]["exclus"], [{"id": "OT-2026-0003", "raison": "non clôturée"}])
        self.assertAlmostEqual(r["mtbf"]["valeur"], (310 - 26) / 3, places=9)
        self.assertAlmostEqual(r["mttr"]["valeur"], 13, places=9)        # (20 + 6) / 2
        self.assertEqual(r["mttr"]["effectif"], 2)
        # Ajustement 3 de Nicolas (lot 5) : la disponibilité ne compte que les pannes AVEC durée d'arrêt ;
        # la panne en cours sans durée (OT-0003) n'y est jamais comptée comme 0 h (elle reste dans le MTBF).
        mtbf_avec_duree = (310 - 26) / 2
        self.assertAlmostEqual(r["disponibilite"]["valeur"], mtbf_avec_duree / (mtbf_avec_duree + 13), places=9)
        self.assertEqual(r["disponibilite"]["effectif"], 2)
        self.assertEqual(r["disponibilite"]["exclus"], [{"id": "OT-2026-0003", "raison": "non clôturée"}])
        self.assertAlmostEqual(r["attentePieces"]["valeur"], 12, places=9)  # (18 + plafond 6) / 2
        self.assertEqual(r["attentePieces"]["effectif"], 2)

    def test_cas_non_calculables_avec_raison(self):
        sans_heures = self.equipement("EQ-0002")
        self.assertIsNone(sans_heures["mtbf"]["valeur"])
        self.assertIn("heures de fonctionnement par jour non renseignées", sans_heures["mtbf"]["raison"])
        self.assertIsNone(sans_heures["disponibilite"]["valeur"])
        self.assertEqual(sans_heures["mttr"]["valeur"], 4)                 # le MTTR n'a pas besoin des heures
        self.assertIn("mis en service après la période", self.equipement("EQ-0003")["tempsRequis"]["raison"])
        self.assertIn("désactivé ou au rebut", self.equipement("EQ-0004")["tempsRequis"]["raison"])
        sans_panne = self.equipement("EQ-0001", ["du-au", AUJOURDHUI, "2026-05-01", "2026-05-31"])
        self.assertIsNone(sans_panne["mtbf"]["valeur"])
        self.assertEqual(sans_panne["mtbf"]["raison"], "aucune panne sur la période")
        self.assertEqual(sans_panne["disponibilite"]["valeur"], 1)
        self.assertEqual(sans_panne["disponibilite"]["note"], "aucune panne sur la période")
        # Mise en service dans la période (12 mois) : 8 h × 10 jours ; une panne sans durée d'arrêt
        # Période d'un jour : 20 h d'arrêt pour 10 h requises → non calculable, jamais négatif (relecture)
        un_jour = self.equipement("EQ-0001", ["du-au", AUJOURDHUI, "2026-03-01", "2026-03-01"])
        self.assertEqual(un_jour["tempsRequis"]["valeur"], 10)
        self.assertIsNone(un_jour["mtbf"]["valeur"])
        self.assertIn("dépasse le temps requis", un_jour["mtbf"]["raison"])
        self.assertIsNone(un_jour["disponibilite"]["valeur"])
        recente = self.equipement("EQ-0003", ["12-mois", AUJOURDHUI])
        self.assertEqual(recente["tempsRequis"]["valeur"], 80)
        self.assertIsNone(recente["mttr"]["valeur"])
        self.assertIn("aucune panne clôturée avec une durée", recente["mttr"]["raison"])
        self.assertEqual(recente["mttr"]["exclus"], [{"id": "OT-2026-0008", "raison": "sans durée d'arrêt"}])
        # Seule panne sans durée d'arrêt : disponibilité non calculable (jamais 100 % ni 0 h inventées)
        self.assertIsNone(recente["disponibilite"]["valeur"])
        self.assertIn("aucune panne avec une durée d'arrêt", recente["disponibilite"]["raison"])
        self.assertEqual(recente["disponibilite"]["exclus"], [{"id": "OT-2026-0008", "raison": "sans durée d'arrêt"}])

    def test_attente_de_pieces_lue_dans_le_journal(self):
        attente = "(id) => Indicateurs.attentePieces(id)"
        self.assertEqual(self.js(attente, "OT-2026-0001"), {"heures": 18, "complet": True})
        self.assertEqual(self.js(attente, "OT-2026-0002"), {"heures": 6, "complet": True})
        self.assertEqual(self.js(attente, "OT-2026-0009"), {"heures": 10, "complet": True})
        self.assertEqual(self.js(attente, "OT-2026-0007"), {"heures": 0, "complet": False})
        self.assertEqual(self.js(attente, "OT-2026-0010"), {"heures": 0, "complet": False})

    def test_global_filtres_et_exclusions(self):
        g = self.js("(p) => Indicateurs.global(periodeDe(...p), {}, '2026-10-20')", MARS)
        self.assertEqual(g["tempsRequis"]["valeur"], 310)
        self.assertEqual(sorted(e["id"] for e in g["tempsRequis"]["exclus"]), ["EQ-0002", "EQ-0003"])
        self.assertAlmostEqual(g["mtbf"]["valeur"], (310 - 26) / 3, places=9)
        self.assertEqual(g["pannes"]["valeur"], 3)                          # la panne de PO-02 n'est pas comptée
        atelier_b = self.js("(p) => Indicateurs.global(periodeDe(...p), { atelier: 'LOC-0004' }, '2026-10-20')", MARS)
        self.assertIsNone(atelier_b["mtbf"]["valeur"])
        # Coût global : tous les OT, équipement au rebut compris = Σ coût par équipement (relecture)
        self.assertEqual(g["cout"]["valeur"], 582)                          # 542 (PO-01) + 0 (PO-02) + 40 (PO-04, au rebut)
        somme = self.js("(p) => Indicateurs.coutParEquipement(periodeDe(...p)).reduce((s, l) => s + l.valeur, 0)", MARS)
        self.assertEqual(somme, 582)
        criticite_b = self.js("(p) => Indicateurs.global(periodeDe(...p), { criticite: 'B' }, '2026-10-20').cout.valeur", MARS)
        self.assertEqual(criticite_b, 0)                                    # PO-02 : OT clôturé sans temps ni pièce
        texte = json.dumps(g)
        for interdit in ("NaN", "Infinity"):
            self.assertNotIn(interdit, texte)


class TestPreventifDelaisCouts(CasIndicateurs):

    def setUp(self):
        super().setUp()
        self.charger(jeu_de_test())

    def test_part_du_preventif(self):
        part = self.js("(p) => Indicateurs.partPreventif(periodeDe(...p))", MARS)
        self.assertAlmostEqual(part["valeur"], 2 / 11, places=9)           # 2 h sur 11 h (4 + 3 + 2 + 1 + 1)
        self.assertEqual(part["effectif"], 5)                              # cinq saisies de temps

    def test_respect_du_preventif_date_et_compteur(self):
        r = self.js("(p) => Indicateurs.respectPreventif(periodeDe(...p))", MARS)
        self.assertEqual(sorted(r["ots"]), ["OT-2026-0010", "OT-2026-0012", "OT-2026-0013"])
        self.assertAlmostEqual(r["valeur"], 1 / 3, places=9)
        self.assertEqual(r["exclus"], [{"id": "OT-2026-0015", "raison": "période de la gamme inconnue"}])

    def test_delais_de_prise_en_charge_par_priorite(self):
        d = self.js("(p) => Indicateurs.delaisPriseEnCharge(periodeDe(...p))", MARS)
        # P1 : OT-0002 datée par sa DI acceptée (07:00 → 09:00 = 2 h, pas la DI regroupée), OT-0003 0,5 h
        self.assertEqual((d["P1"]["mediane"], d["P1"]["partDansLeDelai"], d["P1"]["effectif"]), (1.25, 0.5, 2))
        self.assertEqual((d["P2"]["mediane"], d["P2"]["partDansLeDelai"]), (4, 1))    # DI 08:00 → début 12:00
        self.assertEqual(d["P2"]["exclus"], [{"id": "OT-2026-0019", "raison": "début avant la demande"}])
        self.assertEqual((d["P3"]["mediane"], d["P3"]["partDansLeDelai"]), (180, 0.5))      # 144 h et 216 h, cible 168 h
        self.assertEqual((d["P4"]["effectif"], d["P4"]["mediane"], d["P4"]["partDansLeDelai"]), (0, None, None))
        # Cible P1 « immédiat » (0 h) : médiane seule, jamais un 0 % trompeur
        self.js("""async () => Donnees.modifier('parametres', (lignes) => {
            lignes.find((ligne) => ligne.cle === 'delai_p1_h').valeur = '0'; })""")
        d0 = self.js("(p) => Indicateurs.delaisPriseEnCharge(periodeDe(...p))", MARS)
        self.assertEqual((d0["P1"]["mediane"], d0["P1"]["partDansLeDelai"]), (1.25, None))

    def test_couts_egaux_a_ordres_cout_et_par_equipement(self):
        ecarts = self.js("""() => Donnees.lignes('ordres_travail').map((ot) =>
            [ot.id, Indicateurs.interne.coutDeLOt(ot, Indicateurs.interne.contexte()), Ordres.cout(ot).total])
            .filter(([, a, b]) => Math.abs(a - b) > 1e-9)""")
        self.assertEqual(ecarts, [])
        self.assertEqual(self.js("(id) => Ordres.cout(Donnees.trouver('ordres_travail', id)).total", "OT-2026-0001"), 315.5)
        par_equipement = self.js("(p) => Indicateurs.coutParEquipement(periodeDe(...p))", MARS)
        self.assertEqual(par_equipement[0]["equipementId"], "EQ-0001")
        self.assertEqual(par_equipement[0]["valeur"], 542)                 # 315,5 + 106,5 + 80 (OT-0010) + 40 (OT-0011)
        mois = self.js("Indicateurs.coutsParMois('2026-02', 3)")
        self.assertEqual([m["mois"] for m in mois], ["2026-02", "2026-03", "2026-04"])

    def test_valeur_du_stock(self):
        v = self.js("Indicateurs.valeurStock()")
        self.assertEqual(v["valeur"], 139.5)                               # 9 × 15,5
        self.assertEqual(v["exclus"], [{"id": "ART-0002", "raison": "sans prix unitaire"}])

    def test_series_des_graphiques(self):
        pareto = self.js("(p) => Indicateurs.paretoPannes(periodeDe(...p), 10).map((l) => [l.equipementId, l.valeur, l.cumulPct])", MARS)
        self.assertEqual(pareto, [["EQ-0001", 3, 75], ["EQ-0002", 1, 100]])
        arrets = self.js("(p) => Indicateurs.paretoArrets(periodeDe(...p), 10).map((l) => [l.equipementId, l.valeur])", MARS)
        self.assertEqual(arrets, [["EQ-0001", 26], ["EQ-0002", 4]])
        causes = self.js("(p) => Indicateurs.causes(periodeDe(...p)).map((c) => [c.code, c.libelle, c.nombre])", MARS)
        self.assertEqual(causes, [["C01", "Roulement usé", 2], ["C02", "Joint fuyard", 1], ["", "sans code", 1]])
        heures = self.js("Indicateurs.heuresParMois('2026-03', 2)")
        self.assertEqual(heures, [{"mois": "2026-02", "correctif": 1, "preventif": 0, "autres": 0},
                                  {"mois": "2026-03", "correctif": 7, "preventif": 2, "autres": 2}])
        a = self.js("(p) => Indicateurs.mtbfMttrCriticiteA(periodeDe(...p)).map((l) => l.equipementId)", MARS)
        self.assertEqual(a, ["EQ-0001"])
        retard = self.js("Indicateurs.otEnRetard('2026-10-20')")
        self.assertEqual(sorted(retard["ots"]), ["OT-2026-0003", "OT-2026-0013"])


# ---------------------------------------------------------------------------
# Jeu de démo : calcul Python indépendant (scénario du brief §14)
# ---------------------------------------------------------------------------

DOSSIER_DEMO = RACINE / "donnees" / "demo"


def lire_demo(nom):
    return list(module_csv.DictReader(io.StringIO((DOSSIER_DEMO / (nom + ".csv")).read_text(encoding="utf-8-sig")), delimiter=";"))


def brut(valeur):
    valeur = (valeur or "").strip()
    return valeur[1:] if valeur.startswith("'") else valeur


def nombre(valeur):
    texte = brut(valeur).replace(",", ".").replace(" ", "").replace("\u00A0", "")
    try:
        return float(texte) if texte else None
    except ValueError:
        return None


def jour(valeur):
    texte = brut(valeur)[:10]
    return datetime.date.fromisoformat(texte) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", texte) else None


def instant(valeur):
    texte = brut(valeur)
    if not re.match(r"\d{4}-\d{2}-\d{2}", texte):
        return None
    return datetime.datetime.fromisoformat(texte[:16] if len(texte) >= 16 else texte[:10] + " 00:00")


def simplifier(texte):
    return "".join(c for c in unicodedata.normalize("NFD", texte) if not unicodedata.combining(c)).lower()


def arrondi(valeur):
    """Arrondi à 2 décimales comme Math.round de JavaScript (le round de Python arrondit au pair)."""
    return math.floor(valeur * 100 + 0.5) / 100


def date_reference():
    texte = (RACINE / "js" / "demo-donnees.js").read_text(encoding="utf-8")
    return re.search(r"""dateReference:\s*["'](\d{4}-\d{2}-\d{2})["']""", texte).group(1)


class CalculPython:
    """Calcul indépendant des indicateurs d'un équipement, à partir des CSV (définitions §15.3)."""

    def __init__(self, aujourdhui):
        self.fin = aujourdhui
        moins_un_an = aujourdhui.replace(year=aujourdhui.year - 1) if not (aujourdhui.month == 2 and aujourdhui.day == 29) \
            else aujourdhui.replace(year=aujourdhui.year - 1, day=28)
        self.debut = moins_un_an + datetime.timedelta(days=1)
        self.equipements = {e["id"]: e for e in lire_demo("equipements")}
        self.ordres = lire_demo("ordres_travail")
        # DI d'origine (D35) : celle que l'OT désigne (di_id) ; sinon, parmi les DI qui pointent vers
        # l'OT, l'acceptée, sinon la plus ancienne (jamais une DI regroupée après coup).
        self.di_par_ot = {}
        demandes = lire_demo("demandes")
        par_id = {d["id"]: d for d in demandes}
        vers_ot = {}
        for di in demandes:
            if brut(di["ot_id"]):
                vers_ot.setdefault(brut(di["ot_id"]), []).append(di)
        for ot in self.ordres:
            candidates = sorted(vers_ot.get(ot["id"], []), key=lambda di: brut(di["date_heure"]))
            origine = par_id.get(brut(ot["di_id"])) or next((di for di in candidates if di["statut"] == "Acceptée"), None)
            if origine:
                self.di_par_ot[ot["id"]] = origine
        self.journal = {}
        for entree in lire_demo("journal"):
            if entree["table"] == "ordres_travail":
                self.journal.setdefault(entree["id_ligne"], []).append(entree)
        self.temps = {}
        for ligne in lire_demo("ot_temps"):
            self.temps.setdefault(ligne["ot_id"], []).append(ligne)
        self.taux = {t["id"]: nombre(t["taux_horaire"]) or 0 for t in lire_demo("techniciens")}
        self.prix = {a["id"]: nombre(a["prix_unitaire"]) or 0 for a in lire_demo("articles")}
        self.mouvements = {}
        for mouvement in lire_demo("mouvements_stock"):
            self.mouvements.setdefault(brut(mouvement["ot_id"]), []).append(mouvement)

    def date_panne(self, ot):
        di = self.di_par_ot.get(ot["id"])
        return brut(di["date_heure"]) if di and brut(di["date_heure"]) else brut(ot["date_creation"])

    def attente(self, ot):
        entrees = sorted(self.journal.get(ot["id"], []), key=lambda e: (brut(e["date_heure"]), e["id"]))
        def action(entree):
            texte = entree["action"].strip()
            return texte.split(" — ", 1)[1] if " — " in texte else texte
        complet = any(e["action"].strip().startswith("création") for e in entrees)
        total = 0.0
        debut = None
        for entree in entrees:
            m = re.match(r"^statut (.+?) → (.+?)(?: : (.*))?$", action(entree))
            if not m:
                continue
            moment = instant(entree["date_heure"])
            if debut is not None and m.group(1) == "En attente":
                total += (moment - debut).total_seconds() / 3600
                debut = None
            if m.group(2) == "En attente" and simplifier(m.group(3) or "").startswith("piece"):
                debut = moment
        if debut is not None and instant(ot["date_fin"]):
            total += max(0.0, (instant(ot["date_fin"]) - debut).total_seconds() / 3600)
        duree = nombre(ot["duree_arret_h"])
        return (min(total, duree) if duree is not None and duree >= 0 else total), complet

    def cout(self, ot):
        heures = sum((nombre(l["heures"]) or 0) * self.taux.get(l["technicien_id"], 0) for l in self.temps.get(ot["id"], []))
        quantites = {}
        for mouvement in self.mouvements.get(ot["id"], []):
            if mouvement["type"] in ("sortie", "retour"):
                signe = 1 if mouvement["type"] == "sortie" else -1
                quantites[mouvement["article_id"]] = quantites.get(mouvement["article_id"], 0) + signe * (nombre(mouvement["quantite"]) or 0)
        pieces = sum(q * self.prix.get(a, 0) for a, q in quantites.items())
        return arrondi(heures + pieces + (nombre(ot["cout_soustraitance"]) or 0))

    def equipement(self, equipement_id):
        e = self.equipements[equipement_id]
        heures = nombre(e["heures_fonct_jour"])
        debut = max(self.debut, jour(e["date_mes"]) or self.debut)
        requis = heures * ((self.fin - debut).days + 1)
        pannes = [ot for ot in self.ordres if ot["equipement_id"] == equipement_id
                  and ot["type"] in ("correctif immédiat", "correctif différé") and brut(ot["arret_production"]) == "1"
                  and ot["statut"] != "Annulé" and jour(self.date_panne(ot)) and self.debut <= jour(self.date_panne(ot)) <= self.fin]
        clos = ("Clôturé techniquement", "Clôturé administrativement")
        durees = [nombre(ot["duree_arret_h"]) for ot in pannes if nombre(ot["duree_arret_h"]) is not None]
        arret = sum(durees)
        mesurables = [ot for ot in pannes if ot["statut"] in clos and nombre(ot["duree_arret_h"]) is not None]
        mtbf = (requis - arret) / len(pannes) if pannes and arret <= requis else None
        mttr = sum(nombre(ot["duree_arret_h"]) for ot in mesurables) / len(mesurables) if mesurables else None
        # Disponibilité sur les seules pannes avec durée d'arrêt (ajustement 3 de Nicolas, lot 5)
        mtbf_avec_duree = (requis - arret) / len(durees) if durees and arret <= requis else None
        dispo = mtbf_avec_duree / (mtbf_avec_duree + mttr) if mtbf_avec_duree is not None and mttr is not None else None
        attentes = [a for a, complet in (self.attente(ot) for ot in mesurables) if complet]
        cout = arrondi(sum(self.cout(ot) for ot in self.ordres if ot["equipement_id"] == equipement_id and ot["statut"] in clos
                         and jour(ot["date_fin"]) and self.debut <= jour(ot["date_fin"]) <= self.fin))
        return {"tempsRequis": requis, "pannes": len(pannes), "dureeArret": arret, "mtbf": mtbf, "mttr": mttr,
                "disponibilite": dispo, "attentePieces": sum(attentes) / len(attentes) if attentes else None, "cout": cout}


class TestDemoCalculPython(CasIndicateurs):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reference = date_reference()
        cls.scenarios = scenarios_demo()
        cls.tables = {f.stem: f.read_bytes().decode("utf-8-sig") for f in DOSSIER_DEMO.glob("*.csv")}

    def setUp(self):
        super().setUp()
        self.charger(self.tables)

    def test_indicateurs_de_trois_equipements_egaux_au_calcul_python(self):
        calcul = CalculPython(datetime.date.fromisoformat(self.reference))
        equipements = self.scenarios["equipements_calcul_main"]
        self.assertEqual(len(equipements), 3)
        criticites = [calcul.equipements[e]["criticite"] for e in equipements]
        self.assertIn("A", criticites)
        for equipement_id in equipements:
            attendu = calcul.equipement(equipement_id)
            self.assertGreater(attendu["pannes"], 0, equipement_id)
            obtenu = self.js("([id, jour]) => Indicateurs.parEquipement(id, periodeDe('12-mois', jour))", [equipement_id, self.reference])
            for cle, valeur in attendu.items():
                with self.subTest(equipement=equipement_id, indicateur=cle):
                    if valeur is None:
                        self.assertIsNone(obtenu[cle]["valeur"])
                        self.assertTrue(obtenu[cle]["raison"])
                    else:
                        self.assertTrue(math.isclose(obtenu[cle]["valeur"], valeur, rel_tol=1e-9, abs_tol=1e-6),
                                        "%s : %r ≠ %r" % (cle, obtenu[cle]["valeur"], valeur))

    def test_attente_de_pieces_du_role_de_scenario(self):
        heures = self.js("(id) => Indicateurs.attentePieces(id)", self.scenarios["panne_attente_pieces"])
        self.assertTrue(heures["complet"])
        self.assertGreater(heures["heures"], 0)

    def test_cout_de_chaque_ot_cloture_egal_a_ordres_cout(self):
        ecarts = self.js("""() => { const ctx = Indicateurs.interne.contexte();
            return Donnees.lignes('ordres_travail').filter((ot) => /^Clôturé/.test(ot.statut))
              .map((ot) => [ot.id, Indicateurs.interne.coutDeLOt(ot, ctx), Ordres.cout(ot).total])
              .filter(([, a, b]) => Math.abs(a - b) > 1e-9); }""")
        self.assertEqual(ecarts, [])


if __name__ == "__main__":
    unittest.main()
