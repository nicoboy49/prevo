"""Règles des suggestions de préventif (lot 3 bis, ARCHITECTURE.md §16.2 à §16.5 ; tâche T57).

Deux familles :
    - jeu construit À LA MAIN dans ce fichier, date fixe passée en argument (aujourd'hui = mardi
      20/10/2026 ; fenêtre de 12 mois : du 21/10/2025 au 20/10/2026) : chaque règle au seuil et juste
      sous le seuil, fenêtre au jour près, équipement au rebut ou inactif, gamme « seuil » ou inactive,
      S2 avant la première visite, S3 par la case et par une DI liée, S4 refusée pour la criticité A,
      pour un correctif pendant la série et pour des visites antérieures au passage au format 2,
      décisions (ignorée, revenue, la dernière l'emporte), motif obligatoire, journal en échec,
      réglages, textes ;
    - jeu de démo (donnees/demo, SANS décalage de dates, aujourd'hui = date de référence du
      générateur) : toutes les suggestions égales à un calcul Python indépendant sur les CSV, et
      rôles du §16.8 (tests/fixtures/demo-scenarios.json).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_regles_suggestions.py" -v
"""
import calendar
import csv as module_csv
import datetime
import io
import re
import unittest
from pathlib import Path

from commun import CasNavigateur, charger_scripts, scenarios_demo

RACINE = Path(__file__).resolve().parent.parent
SCRIPTS = [
    "js/lib/papaparse.min.js",
    "js/schema.js",
    "js/donnees.js",
    "js/stockage-demo.js",
    "js/interface.js",
    "js/modules/suggestions-regles.js",
]

AUJOURDHUI = "2026-10-20"
MOTS_INTERDITS = ("NaN", "Infinity", "undefined", "null")


def csv(entete, lignes):
    """Texte CSV au format §3.1 (séparateur ;, fins de ligne CRLF)."""
    return "\r\n".join([entete] + list(lignes)) + "\r\n"


# ---------------------------------------------------------------------------
# Jeu construit
# ---------------------------------------------------------------------------

EQUIPEMENTS = [
    "EQ-0001;CV-02;Convoyeur;B;en service;1",       # S1 : 3 pannes C04 ; C05 : 2 pannes (sous le seuil)
    "EQ-0002;PO-02;Pompe;B;en service;1",           # S2 : 3 pannes C01 après la 1re visite (1 avant)
    "EQ-0003;PO-03;Pompe au rebut;B;rebut;1",        # 5 pannes : au rebut, rien
    "EQ-0004;PO-04;Pompe désactivée;B;en service;0", # 5 pannes : inactive, rien
    "EQ-0005;PR-01;Presse;A;en service;1",          # S3 : anomalies aux visites 2 (case) et 4 (DI liée)
    "EQ-0006;VE-01;Ventilation;C;en service;1",     # S4 : 6 visites sans anomalie, aucune panne
    "EQ-0007;GF-01;Groupe froid;A;en service;1",    # S4 refusée : criticité A
    "EQ-0008;AE-01;Aérotherme;B;en service;1",      # S4 refusée : correctif En cours pendant la série
    "EQ-0009;AE-02;Aérotherme;B;en service;1",      # gamme « seuil » active : ni S1 ni S2
    "EQ-0010;SC-01;Scie;B;en service;1",            # gamme inactive : S1 (3 pannes C03)
    "EQ-0011;ET-01;Étuve;C;en service;1",           # S1 : fenêtre au jour près (le 20/10/2025 est dehors)
    "EQ-0012;RB-01;Robot;B;en service;1",           # S1 ignorée le 15/04, 2 pannes depuis : fermée
]

GAMMES = [
    "GAM-0001;EQ-0002;Contrôle trimestriel;date;90;;1",
    "GAM-0002;EQ-0005;Graissage;date;60;;1",
    "GAM-0003;EQ-0006;Contrôle mensuel;date;30;;1",
    "GAM-0004;EQ-0007;Contrôle mensuel;date;30;;1",
    "GAM-0005;EQ-0008;Contrôle mensuel;date;30;;1",
    "GAM-0006;EQ-0009;Remplacement du filtre;seuil;;CPT-0001;1",
    "GAM-0007;EQ-0010;Ancienne gamme;date;30;;0",
]

CODES = [
    "CD-0001;cause;C01;Garniture usée", "CD-0002;cause;C02;Roulement hors service", "CD-0003;cause;C03;Courroie détendue",
    "CD-0004;cause;C04;Capteur encrassé", "CD-0005;cause;C05;Filtre colmaté", "CD-0006;cause;C06;Desserrage",
]


class Jeu:
    """Lignes d'OT, de DI et de journal du jeu construit (identifiants attribués dans l'ordre)."""

    def __init__(self):
        self.ots, self.dis, self.journal, self.numero = [], [], [], 0

    def ot(self, equipement, jour, type_ot="correctif immédiat", statut="Clôturé techniquement", cause="",
           gamme="", anomalie="0", fin=True, creation=None):
        self.numero += 1
        identifiant = "OT-2026-%04d" % self.numero
        creation = creation or jour
        self.ots.append(";".join([identifiant, equipement, gamme, type_ot, statut, creation + " 08:00",
                                  (jour + " 10:00") if fin else "", cause, anomalie]))
        return identifiant

    def panne(self, equipement, jour, cause, **options):
        return self.ot(equipement, jour, cause=cause, **options)

    def visite(self, gamme, equipement, jour, anomalie="0"):
        return self.ot(equipement, jour, type_ot="préventif systématique", gamme=gamme, anomalie=anomalie)

    def di(self, ot_origine, jour):
        self.dis.append("DI-2026-%04d;%s;%s 10:30;Nouvelle" % (len(self.dis) + 1, ot_origine, jour))

    def decision(self, moment, table, ligne, action, profil="Responsable"):
        self.journal.append("J-%s-%04d;%s;Poste test;%s;%s;%s;%s"
                            % (moment.replace("-", "").replace(" ", "").replace(":", ""), len(self.journal) + 1,
                               moment, profil, table, ligne, action))

    def tables(self, parametres=()):
        return {
            "equipements": csv("id;repere;designation;criticite;statut;actif", EQUIPEMENTS),
            "gammes": csv("id;equipement_id;libelle;declencheur;periodicite_jours;compteur_id;actif", GAMMES),
            "compteurs": csv("id;equipement_id;libelle;unite", ["CPT-0001;EQ-0009;Perte de charge;mbar"]),
            "codes_defaillance": csv("id;famille;code;libelle", CODES),
            "ordres_travail": csv("id;equipement_id;gamme_id;type;statut;date_creation;date_fin;cause_code;anomalie_constatee", self.ots),
            "demandes": csv("id;ot_origine_id;date_heure;statut", self.dis),
            "journal": csv("id;date_heure;poste;profil;table;id_ligne;action", self.journal),
            "parametres": csv("cle;valeur", list(parametres)),
        }


def jeu_de_base():
    j = Jeu()
    # S1 de CV-02 : 3 pannes C04 (écarts 31 et 31 jours) ; C05 : 2 pannes seulement
    for jour in ("2026-07-01", "2026-08-01", "2026-09-01"):
        j.panne("EQ-0001", jour, "C04")
    for jour in ("2026-05-01", "2026-06-01"):
        j.panne("EQ-0001", jour, "C05")
    # S2 de PO-02 : une panne avant la première visite (10/01), 3 après (écarts 59 et 61 jours)
    j.panne("EQ-0002", "2026-01-05", "C01")
    for jour in ("2026-01-10", "2026-04-10", "2026-07-10"):
        j.visite("GAM-0001", "EQ-0002", jour)
    for jour in ("2026-02-01", "2026-04-01", "2026-06-01"):
        j.panne("EQ-0002", jour, "C01")
    # Au rebut et inactive : 5 pannes chacune, rien
    for equipement in ("EQ-0003", "EQ-0004"):
        for mois in range(3, 8):
            j.panne(equipement, "2026-%02d-15" % mois, "C02")
    # S3 de GAM-0002 : 5 visites ; les 4 dernières ont une anomalie à la 2e (case) et à la 4e (DI liée)
    j.visite("GAM-0002", "EQ-0005", "2026-01-12", anomalie="1")            # 5e en partant de la fin : pas regardée
    j.visite("GAM-0002", "EQ-0005", "2026-03-12")
    j.visite("GAM-0002", "EQ-0005", "2026-05-12", anomalie="1")
    j.visite("GAM-0002", "EQ-0005", "2026-07-12")
    derniere = j.visite("GAM-0002", "EQ-0005", "2026-09-12")
    j.di(derniere, "2026-09-12")
    # S4 de GAM-0003 (VE-01, C) : 6 visites mensuelles sans anomalie, aucune panne
    for mois in range(4, 10):
        j.visite("GAM-0003", "EQ-0006", "2026-%02d-15" % mois)
    # GAM-0004 (GF-01, A) : même histoire, refusée pour la criticité
    for mois in range(4, 10):
        j.visite("GAM-0004", "EQ-0007", "2026-%02d-15" % mois)
    # GAM-0005 (AE-01, B) : 6 visites sans anomalie, mais un correctif En cours créé pendant la série
    for mois in range(4, 10):
        j.visite("GAM-0005", "EQ-0008", "2026-%02d-15" % mois)
    j.ot("EQ-0008", "2026-06-20", statut="En cours", fin=False)
    # Un correctif annulé ne compte pas (sur VE-01, après la 1re visite)
    j.ot("EQ-0006", "2026-06-20", statut="Annulé", fin=False)
    # AE-02 : gamme « seuil » active et 3 pannes : ni S1 (gamme active) ni S2 (gamme non suivie)
    j.visite("GAM-0006", "EQ-0009", "2026-02-01")
    for jour in ("2026-03-01", "2026-04-01", "2026-05-01"):
        j.panne("EQ-0009", jour, "C02")
    # SC-01 : gamme inactive → S1 sur 3 pannes C03
    for jour in ("2026-02-03", "2026-03-03", "2026-04-03"):
        j.panne("EQ-0010", jour, "C03")
    # ET-01 : le 20/10/2025 est hors de la fenêtre, le 21/10/2025 dedans → 3 pannes, pas 4
    for jour in ("2025-10-20", "2025-10-21", "2026-03-01", "2026-06-01"):
        j.panne("EQ-0011", jour, "C06")
    # Date illisible : OT ignoré
    j.ot("EQ-0011", "2026-13-45", cause="C06")
    # RB-01 : 3 pannes, ignorée le 15/04, puis 2 pannes seulement → fermée
    for jour in ("2026-02-01", "2026-03-01", "2026-04-01", "2026-05-01", "2026-06-01"):
        j.panne("EQ-0012", jour, "C04")
    j.decision("2026-04-15 10:00", "equipements", "EQ-0012", "suggestion S1-EQ-0012-C04 ignorée : capteur changé sous garantie")
    return j


class CasSuggestions(CasNavigateur):

    def setUp(self):
        super().setUp()
        charger_scripts(self.page, SCRIPTS)

    def charger(self, tables):
        self.page.evaluate("""async (tables) => {
          Donnees.initialiser(StockageDemo.creer(tables), { poste: 'Poste test', profil: 'Responsable' });
          await Donnees.chargerTout();
        }""", tables)

    def calculer(self, jour=AUJOURDHUI, remplacements=None):
        return self.page.evaluate("([jour, r]) => Suggestions.calculer(jour, r || undefined)", [jour, remplacements])

    def cles(self, resultat):
        return [s["cle"] for s in resultat["ouvertes"]]


class TestRegles(CasSuggestions):

    def setUp(self):
        super().setUp()
        self.charger(jeu_de_base().tables())
        self.resultat = self.calculer()
        self.par_cle = {s["cle"]: s for s in self.resultat["ouvertes"]}

    def test_liste_et_ordre(self):
        # S2, puis S3, puis S1, puis S4 ; criticité A, B, C ; nombre décroissant ; clé
        self.assertEqual(self.cles(self.resultat), [
            "S2-EQ-0002-C01", "S3-GAM-0002", "S1-EQ-0001-C04", "S1-EQ-0010-C03", "S1-EQ-0011-C06", "S4-GAM-0003"])
        self.assertEqual(self.resultat["reglages"], {"seuilPannes": 3, "visitesSansConstat": 5, "fenetreMois": 12,
                                                     "debutFenetre": "2025-10-21", "passageFormat2": ""})

    def test_s1_creer_une_gamme(self):
        s = self.par_cle["S1-EQ-0001-C04"]
        self.assertEqual((s["regle"], s["titre"], s["equipementId"], s["repere"], s["criticite"], s["causeCode"], s["causeLibelle"]),
                         ("S1", "Créer une gamme", "EQ-0001", "CV-02", "B", "C04", "Capteur encrassé"))
        self.assertEqual((s["nombre"], s["intervalleMedianJours"], s["gammeIds"]), (3, 31, []))
        self.assertEqual(s["dates"], ["2026-07-01", "2026-08-01", "2026-09-01"])
        self.assertEqual(s["ots"], ["OT-2026-0003", "OT-2026-0002", "OT-2026-0001"])     # du plus récent au plus ancien
        self.assertEqual(s["texte"], "CV-02 : 3 pannes « Capteur encrassé » en 12 mois (environ une toutes les 4 semaines), aucune gamme active.")
        self.assertEqual(s["question"], "Créer une gamme pour prévenir cette panne ?")
        self.assertIsNone(s["decisionPrecedente"])
        self.assertNotIn("S1-EQ-0001-C05", self.par_cle)                                # 2 pannes : sous le seuil

    def test_s1_fenetre_au_jour_pres_et_date_illisible(self):
        s = self.par_cle["S1-EQ-0011-C06"]
        self.assertEqual(s["dates"], ["2025-10-21", "2026-03-01", "2026-06-01"])
        self.assertEqual(s["nombre"], 3)

    def test_s1_gamme_inactive_compte_comme_aucune_gamme(self):
        self.assertIn("S1-EQ-0010-C03", self.par_cle)

    def test_rebut_inactif_et_gamme_seuil_ne_suggerent_rien(self):
        for prefixe in ("S1-EQ-0003", "S1-EQ-0004", "S2-EQ-0003", "S2-EQ-0004", "S1-EQ-0009", "S2-EQ-0009", "S3-GAM-0006", "S4-GAM-0006"):
            with self.subTest(prefixe=prefixe):
                self.assertFalse([c for c in self.par_cle if c.startswith(prefixe)])

    def test_s2_revoir_le_preventif(self):
        s = self.par_cle["S2-EQ-0002-C01"]
        self.assertEqual((s["titre"], s["gammeIds"], s["nombre"], s["intervalleMedianJours"]),
                         ("Revoir le préventif", ["GAM-0001"], 3, 60))
        self.assertEqual(s["dates"], ["2026-02-01", "2026-04-01", "2026-06-01"])      # la panne du 05/01 précède la 1re visite
        self.assertEqual(s["texte"], "PO-02 : 3 pannes « Garniture usée » en 12 mois malgré la gamme GAM-0001 (tous les 90 j) ; "
                                     "intervalle médian entre ces pannes : 60 jours.")
        self.assertIn("À examiner : la gamme ne dit pas quelles pannes elle prévient.", s["question"])

    def test_s3_anomalies_par_la_case_et_par_une_di_liee(self):
        s = self.par_cle["S3-GAM-0002"]
        self.assertEqual((s["titre"], s["equipementId"], s["gammeIds"], s["nombre"], s["sur"]),
                         ("Anomalies répétées", "EQ-0005", ["GAM-0002"], 2, 4))
        self.assertEqual(s["dates"], ["2026-05-12", "2026-09-12"])
        self.assertEqual(s["dis"], ["DI-2026-0001"])
        self.assertEqual(s["texte"], "GAM-0002 (PR-01) : anomalie constatée à 2 des 4 dernières visites (12/05/2026, 12/09/2026).")
        self.assertEqual(s["question"], "Raccourcir la périodicité ou compléter la check-list ?")

    def test_s4_allonger_et_ses_refus(self):
        s = self.par_cle["S4-GAM-0003"]
        self.assertEqual((s["titre"], s["equipementId"], s["criticite"], s["nombre"]), ("Allonger une gamme", "EQ-0006", "C", 6))
        self.assertEqual(s["dates"][0], "2026-04-15")
        self.assertEqual(s["texte"], "VE-01 : 6 visites de suite sans anomalie (gamme GAM-0003, tous les 30 j), "
                                     "aucune panne depuis la première (15/04/2026).")
        self.assertIn("Vérifiez d'abord qu'aucune obligation (réglementaire, constructeur, garantie) ne l'impose.", s["question"])
        self.assertNotIn("S4-GAM-0004", self.par_cle)          # criticité A
        self.assertNotIn("S4-GAM-0005", self.par_cle)          # correctif En cours pendant la série
        self.assertNotIn("S4-GAM-0002", self.par_cle)          # dernière visite avec anomalie : série vide

    def test_decision_ignoree_ferme_tant_que_les_faits_restent_sous_le_seuil(self):
        self.assertNotIn("S1-EQ-0012-C04", self.par_cle)
        decision = self.resultat["decisions"][0]
        self.assertEqual({k: decision[k] for k in ("cle", "regle", "decision", "texte", "dateHeure", "table", "idLigne", "revenue")},
                         {"cle": "S1-EQ-0012-C04", "regle": "S1", "decision": "ignorée", "texte": "capteur changé sous garantie",
                          "dateHeure": "2026-04-15 10:00", "table": "equipements", "idLigne": "EQ-0012", "revenue": False})

    def test_aucun_texte_vide_ou_illisible(self):
        for s in self.resultat["ouvertes"]:
            for champ in ("texte", "question", "titre"):
                with self.subTest(cle=s["cle"], champ=champ):
                    self.assertTrue(s[champ])
                    for mot in MOTS_INTERDITS:
                        self.assertNotIn(mot, s[champ])

    def test_reglages_changent_la_liste(self):
        self.assertEqual(self.cles(self.calculer(remplacements={"seuilPannes": 4})), ["S3-GAM-0002", "S4-GAM-0003"])
        self.assertNotIn("S4-GAM-0003", self.cles(self.calculer(remplacements={"visitesSansConstat": 7})))
        # Fenêtre de 3 mois (du 21/07/2026) : la panne de CV-02 du 01/07 sort, il en reste 2
        trois_mois = self.calculer(remplacements={"fenetreMois": 3})
        self.assertEqual(trois_mois["reglages"]["debutFenetre"], "2026-07-21")
        self.assertNotIn("S1-EQ-0001-C04", self.cles(trois_mois))

    def test_parametres_lus_et_valeurs_hors_bornes_ignorees(self):
        self.charger(jeu_de_base().tables(parametres=["suggestion_seuil_pannes;4", "suggestion_visites_sans_constat;7"]))
        self.assertEqual(self.cles(self.calculer()), ["S3-GAM-0002"])
        self.charger(jeu_de_base().tables(parametres=["suggestion_seuil_pannes;1", "suggestion_visites_sans_constat;abc",
                                                      "suggestion_fenetre_mois;30"]))
        resultat = self.calculer()
        self.assertEqual((resultat["reglages"]["seuilPannes"], resultat["reglages"]["visitesSansConstat"],
                          resultat["reglages"]["fenetreMois"]), (3, 5, 12))


class TestTextes(CasSuggestions):

    def test_frequence_en_clair_selon_l_intervalle_median(self):
        j = jeu_de_base()
        for jour in ("2026-08-10", "2026-08-10", "2026-08-10"):          # médiane 0 : pannes groupées
            j.panne("EQ-0001", jour, "C01")
        for jour in ("2026-08-01", "2026-08-02", "2026-08-03"):          # médiane 1 jour
            j.panne("EQ-0001", jour, "C02")
        for jour in ("2026-08-01", "2026-08-06", "2026-08-11"):          # médiane 5 jours
            j.panne("EQ-0001", jour, "C03")
        self.charger(j.tables())
        par_cle = {s["cle"]: s for s in self.calculer()["ouvertes"]}
        self.assertEqual(par_cle["S1-EQ-0001-C01"]["intervalleMedianJours"], 0)
        self.assertEqual(par_cle["S1-EQ-0001-C01"]["texte"], "CV-02 : 3 pannes « Garniture usée » en 12 mois, aucune gamme active.")
        self.assertEqual(par_cle["S1-EQ-0001-C02"]["texte"],
                         "CV-02 : 3 pannes « Roulement hors service » en 12 mois (environ une par jour), aucune gamme active.")
        self.assertEqual(par_cle["S1-EQ-0001-C03"]["texte"],
                         "CV-02 : 3 pannes « Courroie détendue » en 12 mois (environ une tous les 5 jours), aucune gamme active.")

    def test_calculer_sans_jour_prend_aujourd_hui(self):
        self.charger(jeu_de_base().tables())
        resultat = self.page.evaluate("() => Suggestions.calculer()")
        self.assertIsInstance(resultat["ouvertes"], list)
        self.assertEqual(resultat["reglages"]["debutFenetre"], self.page.evaluate(
            "() => Suggestions.calculer(Donnees.aujourdhui()).reglages.debutFenetre"))


class TestDecisionsEtFormat2(CasSuggestions):

    def test_suggestion_revenue_apres_de_nouveaux_faits(self):
        j = jeu_de_base()
        j.panne("EQ-0012", "2026-07-01", "C04")                 # 3e panne depuis la décision du 15/04
        self.charger(j.tables())
        resultat = self.calculer()
        s = next(s for s in resultat["ouvertes"] if s["cle"] == "S1-EQ-0012-C04")
        self.assertEqual((s["nombre"], s["depuis"]), (3, "2026-04-15 10:00"))
        self.assertEqual(s["dates"], ["2026-05-01", "2026-06-01", "2026-07-01"])
        self.assertEqual(s["decisionPrecedente"]["decision"], "ignorée")
        self.assertEqual(s["decisionPrecedente"]["texte"], "capteur changé sous garantie")
        self.assertTrue(s["texte"].startswith("RB-01 : 3 pannes « Capteur encrassé » depuis le 15/04/2026"))
        self.assertTrue(resultat["decisions"][0]["revenue"])

    def test_la_derniere_decision_l_emporte(self):
        j = jeu_de_base()
        j.decision("2026-09-02 08:00", "equipements", "EQ-0001", "suggestion S1-EQ-0001-C04 ignorée : premier avis")
        j.decision("2026-08-01 08:00", "equipements", "EQ-0001", "suggestion S1-EQ-0001-C04 traitée : gamme GAM-0099 créée")
        self.charger(j.tables())
        resultat = self.calculer()
        self.assertNotIn("S1-EQ-0001-C04", self.cles(resultat))     # 0 panne après le 02/09
        self.assertEqual([d["texte"] for d in resultat["decisions"] if d["cle"] == "S1-EQ-0001-C04"],
                         ["premier avis", "gamme GAM-0099 créée"])

    def test_un_fait_au_moment_meme_de_la_decision_n_est_pas_posterieur(self):
        j = jeu_de_base()
        j.panne("EQ-0012", "2026-07-01", "C04")
        j.panne("EQ-0012", "2026-04-15", "C04")                 # finie le 15/04 à 10:00 : la minute de la décision
        self.charger(j.tables())
        s = next(s for s in self.calculer()["ouvertes"] if s["cle"] == "S1-EQ-0012-C04")
        self.assertEqual(s["dates"], ["2026-05-01", "2026-06-01", "2026-07-01"])

    def test_s4_sans_les_visites_d_avant_le_passage_au_format_2(self):
        j = jeu_de_base()
        j.decision("2026-08-01 09:00", "parametres", "version_schema",
                   "modification : valeur — passage au format 2 du fichier ; sauvegarde x faite juste avant")
        self.charger(j.tables())
        resultat = self.calculer()
        self.assertEqual(resultat["reglages"]["passageFormat2"], "2026-08-01 09:00")
        self.assertNotIn("S4-GAM-0003", self.cles(resultat))        # 2 visites comptées (15/08, 15/09)
        self.assertIn("S3-GAM-0002", self.cles(resultat))           # S3 n'est pas concernée

    def test_decisions_sur_s3_et_s4(self):
        j = jeu_de_base()
        j.decision("2026-07-01 12:00", "gammes", "GAM-0003", "suggestion S4-GAM-0003 ignorée : périodicité imposée par le constructeur")
        j.decision("2026-08-01 12:00", "gammes", "GAM-0002", "suggestion S3-GAM-0002 traitée : check-list modifiée")
        self.charger(j.tables())
        resultat = self.calculer()
        self.assertNotIn("S4-GAM-0003", self.cles(resultat))    # 3 visites depuis le 01/07 : sous le seuil de 5
        self.assertNotIn("S3-GAM-0002", self.cles(resultat))    # 1 visite depuis le 01/08 : 1 anomalie sur 1
        self.assertEqual([(d["cle"], d["table"], d["idLigne"]) for d in resultat["decisions"][:2]],
                         [("S3-GAM-0002", "gammes", "GAM-0002"), ("S4-GAM-0003", "gammes", "GAM-0003")])
        # De nouvelles visites sans anomalie font revenir S4 (5 visites postérieures à la décision)
        j.visite("GAM-0003", "EQ-0006", "2026-10-01")
        j.visite("GAM-0003", "EQ-0006", "2026-10-15")
        self.charger(j.tables())
        s = next(s for s in self.calculer()["ouvertes"] if s["cle"] == "S4-GAM-0003")
        self.assertEqual((s["nombre"], s["depuis"], s["decisionPrecedente"]["decision"]), (5, "2026-07-01 12:00", "ignorée"))

    def test_meme_minute_l_identifiant_departage(self):
        j = jeu_de_base()
        j.decision("2026-06-15 09:00", "equipements", "EQ-0001", "suggestion S1-EQ-0001-C04 ignorée : a")
        j.decision("2026-06-15 09:00", "equipements", "EQ-0001", "suggestion S1-EQ-0001-C04 traitée : b")   # identifiant plus grand
        self.charger(j.tables())
        s = next(s for s in self.calculer()["ouvertes"] if s["cle"] == "S1-EQ-0001-C04")   # 3 pannes après le 15/06
        self.assertEqual((s["decisionPrecedente"]["decision"], s["decisionPrecedente"]["texte"]), ("traitée", "b"))

    def test_s2_avant_la_premiere_visite_ne_compte_pas(self):
        j = jeu_de_base()
        j.panne("EQ-0002", "2026-01-06", "C02")
        j.panne("EQ-0002", "2026-01-07", "C02")
        j.panne("EQ-0002", "2026-01-09", "C02")
        self.charger(j.tables())
        self.assertNotIn("S2-EQ-0002-C02", self.cles(self.calculer()))


class TestEcritureDesDecisions(CasSuggestions):

    def setUp(self):
        super().setUp()
        self.charger(jeu_de_base().tables())

    def appeler(self, fonction, *arguments):
        return self.page.evaluate("""async ([fonction, args]) => {
          try { return { ok: await Suggestions[fonction](...args) }; }
          catch (erreur) { return { erreur: erreur.name, message: erreur.message }; }
        }""", [fonction, list(arguments)])

    def journal(self):
        return self.page.evaluate("() => Donnees.lignes('journal').map((l) => [l.table, l.id_ligne, l.action, l.profil])")

    def test_ignorer_exige_un_motif_puis_ecrit_le_journal(self):
        avant = len(self.journal())
        for motif in ("", "   ", "x" * 301):
            with self.subTest(motif=motif[:5]):
                retour = self.appeler("ignorer", "S1-EQ-0001-C04", motif)
                self.assertIn("erreur", retour)
                self.assertEqual(len(self.journal()), avant)
        retour = self.appeler("ignorer", "S1-EQ-0001-C04", "  nettoyage fait\nà chaque passage  ")
        self.assertIn("ok", retour)
        self.assertEqual(self.journal()[-1], ["equipements", "EQ-0001",
                                              "suggestion S1-EQ-0001-C04 ignorée : nettoyage fait à chaque passage", "Responsable"])
        self.assertNotIn("S1-EQ-0001-C04", self.page.evaluate("(j) => Suggestions.calculer(j).ouvertes.map((s) => s.cle)", AUJOURDHUI))
        # Plus ouverte : un second « Ignorer » est refusé
        self.assertIn("erreur", self.appeler("ignorer", "S1-EQ-0001-C04", "encore"))

    def test_marquer_traitee_sur_la_gamme_ou_l_equipement(self):
        self.assertIn("ok", self.appeler("marquerTraitee", "S3-GAM-0002", "gamme modifiée : periodicite_jours"))
        self.assertEqual(self.journal()[-1][:3], ["gammes", "GAM-0002", "suggestion S3-GAM-0002 traitée : gamme modifiée : periodicite_jours"])
        self.assertIn("ok", self.appeler("marquerTraitee", "S2-EQ-0002-C01", ""))
        self.assertEqual(self.journal()[-1][:3], ["equipements", "EQ-0002", "suggestion S2-EQ-0002-C01 traitée : traitée"])
        self.assertEqual(self.appeler("marquerTraitee", "S9-EQ-0002-C01", "x")["erreur"], "ErreurValidation")
        self.assertEqual(self.appeler("marquerTraitee", "S1-EQ-9999-C01", "x")["erreur"], "ErreurValidation")

    def test_journal_en_echec_la_suggestion_reste_ouverte(self):
        self.page.evaluate("() => { Donnees.journaliser = async () => null; }")
        retour = self.appeler("ignorer", "S1-EQ-0001-C04", "motif")
        self.assertEqual(retour["erreur"], "ErreurStockage")
        self.assertIn("S1-EQ-0001-C04", self.page.evaluate("(j) => Suggestions.calculer(j).ouvertes.map((s) => s.cle)", AUJOURDHUI))


# ---------------------------------------------------------------------------
# Jeu de démo : calcul Python indépendant des règles du §16.3
# ---------------------------------------------------------------------------

DOSSIER_DEMO = RACINE / "donnees" / "demo"
CORRECTIFS = ("correctif immédiat", "correctif différé")
CLOS = ("Clôturé techniquement", "Clôturé administrativement")
DECISION = re.compile(r"^suggestion (S[1-4]-\S+) (ignorée|traitée) : (.*)$")


def lire_demo(nom, dossier=DOSSIER_DEMO):
    texte = (Path(dossier) / (nom + ".csv")).read_text(encoding="utf-8-sig")
    return [{k: (v or "").strip().lstrip("'") for k, v in ligne.items()}
            for ligne in module_csv.DictReader(io.StringIO(texte), delimiter=";")]


def date_reference():
    texte = (RACINE / "js" / "demo-donnees.js").read_text(encoding="utf-8")
    return re.search(r"""dateReference:\s*["'](\d{4}-\d{2}-\d{2})["']""", texte).group(1)


def jour_valide(texte):
    try:
        datetime.date.fromisoformat(texte)
        return True
    except ValueError:
        return False


def moment(ot):
    brut = ot["date_fin"] or ot["date_cloture_tech"] or ot["date_creation"]
    m = brut.replace("T", " ")[:16]
    return m if jour_valide(m[:10]) else ""


def ajouter_mois(jour, mois):
    total = jour.year * 12 + jour.month - 1 + mois
    annee, mois0 = divmod(total, 12)
    return datetime.date(annee, mois0 + 1, min(jour.day, calendar.monthrange(annee, mois0 + 1)[1]))


def mediane_jours(jours):
    ecarts = sorted((datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a)).days for a, b in zip(jours, jours[1:]))
    if not ecarts:
        return None
    milieu = len(ecarts) // 2
    valeur = ecarts[milieu] if len(ecarts) % 2 else (ecarts[milieu - 1] + ecarts[milieu]) / 2
    return int(valeur + 0.5)


def calcul_python(reference, seuil=3, sans_constat=5, fenetre=12, dossier=DOSSIER_DEMO):
    """Suggestions ouvertes {clé: champs comparés} au jour `reference`, d'après §16.2 à §16.4, sur les
    CSV de `dossier` (jeu de démo brut par défaut ; tests/test_accueil_lot3bis.py s'en sert aussi)."""
    equipements = {e["id"]: e for e in lire_demo("equipements", dossier)}
    gammes = lire_demo("gammes", dossier)
    ots = lire_demo("ordres_travail", dossier)
    journal = lire_demo("journal", dossier)
    debut = (ajouter_mois(datetime.date.fromisoformat(reference), -fenetre) + datetime.timedelta(days=1)).isoformat()
    dis_par_ot = {}
    for di in lire_demo("demandes", dossier):
        if di["ot_origine_id"]:
            dis_par_ot.setdefault(di["ot_origine_id"], []).append(di["id"])
    codes = {c["code"]: c["libelle"] for c in lire_demo("codes_defaillance", dossier) if c["famille"] == "cause"}
    derniere, decisions = {}, {}
    for ligne in sorted(journal, key=lambda l: (l["date_heure"].replace("T", " ")[:16], l["id"]), reverse=True):
        trouve = DECISION.match(ligne["action"])
        if trouve and trouve.group(1) not in derniere:
            derniere[trouve.group(1)] = ligne["date_heure"].replace("T", " ")[:16]
            decisions[trouve.group(1)] = {"decision": trouve.group(2), "dateHeure": derniere[trouve.group(1)],
                                          "texte": trouve.group(3), "profil": ligne["profil"]}
    passage = max([l["date_heure"].replace("T", " ")[:16] for l in journal if l["table"] == "parametres"
                   and l["id_ligne"] == "version_schema" and "passage au format 2 du fichier" in l["action"]], default="")
    suivi = {i for i, e in equipements.items() if e["actif"] != "0" and e["statut"] != "rebut"}
    actives = [g for g in gammes if g["actif"] != "0"]
    suivies = [g for g in actives if (g["declencheur"] or "date") in ("date", "compteur") and g["equipement_id"] in suivi]
    visites = {}
    for ot in ots:
        m = moment(ot)
        if ot["gamme_id"] and ot["statut"] in CLOS and m and m[:10] <= reference:
            visites.setdefault(ot["gamme_id"], []).append((m, ot["id"], ot["anomalie_constatee"] == "1" or ot["id"] in dis_par_ot))
    for liste in visites.values():
        liste.sort()
    pannes = {}
    for ot in ots:
        m = moment(ot)
        if ot["type"] in CORRECTIFS and ot["statut"] in CLOS and ot["cause_code"] and m and debut <= m[:10] <= reference:
            pannes.setdefault(ot["equipement_id"], []).append((m, ot["id"], ot["cause_code"]))
    for liste in pannes.values():
        liste.sort()
    resultat = {}

    def ajouter(cle, regle, equipement, faits, **autres):
        if "causeCode" in autres:
            autres["causeLibelle"] = codes.get(autres["causeCode"], autres["causeCode"])
        resultat[cle] = dict({"regle": regle, "equipementId": equipement, "nombre": len(faits),
                              "repere": equipements[equipement]["repere"] or equipement,
                              "criticite": equipements[equipement]["criticite"],
                              "depuis": derniere.get(cle), "decisionPrecedente": decisions.get(cle),
                              "ots": [f[1] for f in reversed(faits)], "dates": [f[0][:10] for f in faits]}, **autres)

    for eq in sorted(suivi):
        par_cause = {}
        for fait in pannes.get(eq, []):
            par_cause.setdefault(fait[2], []).append(fait)
        if not [g for g in actives if g["equipement_id"] == eq]:
            for cause, faits in par_cause.items():
                cle = "S1-%s-%s" % (eq, cause)
                faits = [f for f in faits if f[0] > derniere.get(cle, "")]
                if len(faits) >= seuil:
                    ajouter(cle, "S1", eq, faits, gammeIds=[], causeCode=cause, intervalleMedianJours=mediane_jours([f[0][:10] for f in faits]))
        avec_visite = [g for g in suivies if g["equipement_id"] == eq and visites.get(g["id"])]
        if avec_visite:
            premiere = min(visites[g["id"]][0][0] for g in avec_visite)
            for cause, faits in par_cause.items():
                cle = "S2-%s-%s" % (eq, cause)
                faits = [f for f in faits if f[0] > premiere and f[0] > derniere.get(cle, "")]
                if len(faits) >= seuil:
                    ajouter(cle, "S2", eq, faits, gammeIds=sorted(g["id"] for g in avec_visite), causeCode=cause,
                            intervalleMedianJours=mediane_jours([f[0][:10] for f in faits]))
    for g in suivies:
        eq = g["equipement_id"]
        cle = "S3-" + g["id"]
        regardees = [v for v in visites.get(g["id"], []) if v[0] > derniere.get(cle, "")][-4:]
        anomalies = [v for v in regardees if v[2]]
        if len(anomalies) >= 2:
            ajouter(cle, "S3", eq, anomalies, gammeIds=[g["id"]], sur=len(regardees),
                    dis=sorted(d for v in anomalies for d in dis_par_ot.get(v[1], [])))
        cle = "S4-" + g["id"]
        if equipements[eq]["criticite"] not in ("B", "C"):
            continue
        comptees = [v for v in visites.get(g["id"], []) if v[0] > passage and v[0] > derniere.get(cle, "")]
        serie = []
        for v in reversed(comptees):
            if v[2]:
                break
            serie.insert(0, v)
        if len(serie) < sans_constat:
            continue
        correctifs = [o for o in ots if o["equipement_id"] == eq and o["type"] in CORRECTIFS and o["statut"] != "Annulé"
                      and jour_valide(o["date_creation"][:10]) and o["date_creation"][:10] >= serie[0][0][:10]]
        if not correctifs:
            ajouter(cle, "S4", eq, serie, gammeIds=[g["id"]])
    return resultat


def ordre_python(suggestions):
    """Ordre du §16.3 : S2, S3, S1, S4 ; criticité A, B, C, puis le reste ; nombre décroissant ; clé."""
    regles = {"S2": 0, "S3": 1, "S1": 2, "S4": 3}
    criticites = {"A": 0, "B": 1, "C": 2}
    return [cle for cle, s in sorted(suggestions.items(), key=lambda e: (
        regles[e[1]["regle"]], criticites.get(e[1]["criticite"], 3), -e[1]["nombre"], e[0]))]


def tables_avec_criticite(tables, equipement_id, criticite):
    """Copie des CSV de la démo où un équipement change de criticité (le reste à l'identique)."""
    lecteur = module_csv.DictReader(io.StringIO(tables["equipements"]), delimiter=";")
    sortie = io.StringIO()
    ecrivain = module_csv.DictWriter(sortie, fieldnames=lecteur.fieldnames, delimiter=";", lineterminator="\r\n")
    ecrivain.writeheader()
    for ligne in lecteur:
        if ligne["id"].lstrip("'") == equipement_id:
            ligne["criticite"] = criticite
        ecrivain.writerow(ligne)
    return dict(tables, equipements=sortie.getvalue())


class TestDemo(CasSuggestions):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reference = date_reference()
        cls.scenarios = scenarios_demo()
        cls.tables = {fichier.stem: fichier.read_bytes().decode("utf-8-sig") for fichier in DOSSIER_DEMO.glob("*.csv")}

    def setUp(self):
        super().setUp()
        self.charger(self.tables)

    def test_suggestions_egales_au_calcul_python(self):
        attendu = calcul_python(self.reference)
        liste = self.calculer(self.reference)["ouvertes"]
        obtenu = {s["cle"]: s for s in liste}
        self.assertEqual(sorted(obtenu), sorted(attendu))
        self.assertEqual([s["cle"] for s in liste], ordre_python(attendu))
        for cle, valeurs in attendu.items():
            for champ, valeur in valeurs.items():
                with self.subTest(cle=cle, champ=champ):
                    self.assertEqual(obtenu[cle][champ], valeur)
        for s in obtenu.values():
            for mot in MOTS_INTERDITS:
                self.assertNotIn(mot, s["texte"] + s["question"])

    def test_reglages_changent_la_liste_egale_au_calcul_python(self):
        for reglages in ({"seuilPannes": 5}, {"visitesSansConstat": 15}, {"fenetreMois": 6}):
            with self.subTest(reglages=reglages):
                obtenu = self.calculer(self.reference, reglages)["ouvertes"]
                attendu = calcul_python(self.reference, seuil=reglages.get("seuilPannes", 3),
                                        sans_constat=reglages.get("visitesSansConstat", 5), fenetre=reglages.get("fenetreMois", 12))
                self.assertEqual(sorted(s["cle"] for s in obtenu), sorted(attendu))

    def test_roles_du_lot_3_bis(self):
        resultat = self.calculer(self.reference)
        ouvertes = {s["cle"]: s for s in resultat["ouvertes"]}
        for role, regle in (("suggestion_creer", "S1"), ("suggestion_revoir", "S2"), ("suggestion_anomalies", "S3"),
                            ("suggestion_allonger", "S4"), ("suggestion_ignoree_revenue", None)):
            with self.subTest(role=role):
                cle = self.scenarios[role]
                self.assertIn(cle, ouvertes)
                if regle:
                    self.assertEqual(ouvertes[cle]["regle"], regle)
        revenue = ouvertes[self.scenarios["suggestion_ignoree_revenue"]]
        self.assertEqual(revenue["decisionPrecedente"]["decision"], "ignorée")
        self.assertGreaterEqual(revenue["nombre"], 3)
        self.assertTrue(any(d["revenue"] and d["cle"] == revenue["cle"] for d in resultat["decisions"]))
        # Refus en criticité A : la même gamme passe dès que la criticité n'est plus A
        gamme_a = self.scenarios["suggestion_refus_criticite_a"]
        self.assertNotIn("S4-" + gamme_a, ouvertes)
        equipement_a = next(g["equipement_id"] for g in lire_demo("gammes") if g["id"] == gamme_a)
        self.charger(tables_avec_criticite(self.tables, equipement_a, "B"))      # copie : la même gamme en criticité B
        self.assertIn("S4-" + gamme_a, self.cles(self.calculer(self.reference)))
        # Sous le seuil : équipement et cause à seuil − 1 pannes, rien de suggéré
        sous = self.scenarios["suggestion_sous_seuil"]
        self.assertFalse([c for c in ouvertes if c.startswith("S1-%s-%s" % (sous["equipement"], sous["cause"]))
                          or c.startswith("S2-%s-%s" % (sous["equipement"], sous["cause"]))])
        self.assertTrue(calcul_python(self.reference, seuil=2).get("S1-%s-%s" % (sous["equipement"], sous["cause"])))


if __name__ == "__main__":
    unittest.main()
