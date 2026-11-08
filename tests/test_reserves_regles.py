"""Tests des règles pures des réserves des contrôles (controles-reserves.js, T411 ; CS170, D183, D187).

Deux familles :
    - jeu construit À LA MAIN dans ce fichier, date fixe passée en argument (aujourd'hui = 20/10/2026) :
      Controles.lignesDeReserves, reserveLevee, echeanceReserve (échéance saisie, sinon date du contrôle + 30 jours,
      sinon inconnue), etatReserve, reservesDuControle, reservesOuvertes, reservesEnRetard, adresseOtReserve ; une
      réserve reprise par la migration D183 (Formats.reservesReprises : levée avant la 2.2, date inconnue) ;
    - jeu de démo (donnees/demo, sans décalage, aujourd'hui = date de référence du générateur) : rôles de T417
      (controle_reserves, reserve_en_retard, reserve_levee, reserve_a_echeance) et réserves en retard comparées à un
      calcul Python indépendant.
Aucune de ces règles n'écrit : les lignes sont relues identiques après les appels.

Lancer depuis la racine du projet (navigateur : au travers du verrou du chantier) :
    py -X utf8 -m unittest discover -s tests -p "test_reserves_regles.py" -v
"""
import csv as module_csv
import datetime
import io
import re
import unittest
import urllib.parse
from pathlib import Path

from commun import CasNavigateur, charger_scripts, scenarios_demo

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_DEMO = RACINE / "donnees" / "demo"
SCRIPTS = [
    "js/lib/papaparse.min.js",
    "js/schema.js",
    "js/donnees.js",
    "js/stockage-demo.js",
    "js/interface.js",
    "js/modules/controles-regles.js",
    "js/modules/controles-reserves.js",
]
# js/formats.js (Formats.reservesReprises, D183) se charge juste après js/schema.js, comme dans index.html.
SCRIPTS_REPRISE = SCRIPTS[:2] + ["js/formats.js"] + SCRIPTS[2:]
AUJOURDHUI = "2026-10-20"
COMMENTAIRE_D183 = "levée avant la 2.2, date inconnue"
DELAI_D187 = datetime.timedelta(days=30)


def csv(entete, lignes):
    """Texte CSV au format §3.1 (séparateur ;, fins de ligne CRLF)."""
    return "\r\n".join([entete] + list(lignes)) + "\r\n"


EQUIPEMENTS = csv("id;repere;designation;statut;actif", [
    "EQ-0001;PR-01;Presse;en service;1",
    "EQ-0002;PR-02;Vieille presse;rebut;1",
    "EQ-0003;PR-03;Presse désactivée;en service;0",
])

CONTROLES = csv("id;equipement_id;nature;periodicite_mois;derniere_date;prochaine_date", [
    "CTR-0001;EQ-0001;Installations électriques;12;2025-11-12;2026-11-12",
    "CTR-0002;EQ-0002;VGP rebut;12;2025-01-10;2026-01-10",
    "CTR-0003;EQ-0003;VGP inactif;12;2025-01-10;2026-01-10",
    "CTR-0004;EQ-0001;Réservoir d'air;48;2026-09-19;2030-09-19",
    "CTR-0005;EQ-0001;Sans réserve;12;2026-01-01;2027-01-01",
])

RESERVES = csv("id;controle_id;date_controle;texte;gravite;echeance_levee;levee;date_levee;commentaire_levee;ot_id", [
    # CTR-0001, réalisation du 12/11/2025 : en retard (30 jours : 12/12/2025), à lever (échéance saisie), levée
    "RES-00001;CTR-0001;2025-11-12;Différentiel 30 mA à remplacer;majeure;;0;;;",
    "RES-00002;CTR-0001;2025-11-12;Schéma unifilaire à mettre à jour;;2026-12-15;0;;;",
    "RES-00003;CTR-0001;2025-11-12;Prise de terre à reprendre;;;1;2025-12-09;Prise refaite;OT-2025-0026",
    # CTR-0001, réalisation du 05/11/2024 : reprise D183 levée (date vide), puis deux ouvertes au 05/12/2024
    "RES-00004;CTR-0001;2024-11-05;Éclairage de secours absent;;;1;;" + COMMENTAIRE_D183 + ";",
    "RES-00005;CTR-0001;2024-11-05;Armoire non fermée à clé;;;0;;;",
    "RES-00014;CTR-0001;2024-11-05;Armoire sans plan;;2024-12-05;0;;;",
    # équipement au rebut, équipement désactivé, contrôle introuvable : jamais « en retard » à l'accueil
    "RES-00006;CTR-0002;2025-01-10;Câble usé;;2025-02-10;0;;;",
    "RES-00007;CTR-0003;2025-01-10;Crochet usé;;2025-02-10;0;;;",
    "RES-00008;CTR-9999;2025-01-10;Contrôle disparu;;2025-02-10;0;;;",
    # CTR-0004 : date du contrôle inconnue ; échéance aujourd'hui (20/09 + 30 jours = 20/10) ; hier (19/09 + 30) ;
    # levée (« oui », relu 1) ; même texte qu'une autre (doublon gardé), échéance saisie à venir
    "RES-00009;CTR-0004;;Date du contrôle inconnue;;;0;;;",
    "RES-00010;CTR-0004;2026-09-20;Manomètre à remplacer;;;0;;;",
    "RES-00011;CTR-0004;2026-09-19;Purgeur défectueux;;;0;;;",
    "RES-00012;CTR-0004;2026-09-19;Soupape à tarer;;;oui;2026-10-01;Soupape tarée;",
    "RES-00013;CTR-0004;2026-09-19;Purgeur défectueux;critique;2026-10-25;0;;;",
])


def jeu_de_test():
    return {"equipements": EQUIPEMENTS, "controles_reglementaires": CONTROLES, "reserves_controle": RESERVES}


class CasReserves(CasNavigateur):
    """Page vide + scripts des contrôles + jeu passé à StockageDemo (sans décalage)."""

    def charger(self, tables):
        charger_scripts(self.page, SCRIPTS)
        self.page.evaluate("""async (tables) => {
          Donnees.initialiser(StockageDemo.creer(tables), { poste: 'Poste test', profil: 'Responsable test' });
          await Donnees.chargerTout();
        }""", tables)

    def js(self, script, argument=None):
        return self.page.evaluate(script, argument)

    def etat(self, reserve_id, jour=AUJOURDHUI):
        return self.js("([id, jour]) => Controles.etatReserve(Donnees.trouver('reserves_controle', id), jour)",
                       [reserve_id, jour])

    def groupes(self, controle_id):
        return self.js("""(id) => Controles.reservesDuControle(id)
          .map((g) => [g.date_controle, g.reserves.map((r) => r.id)])""", controle_id)

    def ouvertes(self, controle_id):
        return self.js("(id) => Controles.reservesOuvertes(id).map((r) => r.id)", controle_id)

    def en_retard(self, jour):
        return self.js("""(jour) => Controles.reservesEnRetard(jour)
          .map((e) => [e.reserve.id, e.controle.id, e.etat.statut, e.etat.echeance])""", jour)

    def adresse(self, script, argument=None):
        """Adresse rendue → (chemin, [(clé, valeur)] dans l'ordre)."""
        adresse = self.js(script, argument)
        chemin, _, requete = adresse.partition("?")
        return chemin, urllib.parse.parse_qsl(requete, keep_blank_values=True)


# ---------------------------------------------------------------------------
# Jeu construit à la main
# ---------------------------------------------------------------------------

class TestTexteSaisi(CasReserves):
    """lignesDeReserves : une réserve par ligne non vide, comme le rapport les liste."""

    def setUp(self):
        super().setUp()
        self.charger(jeu_de_test())

    def lignes(self, texte):
        return self.js("(texte) => Controles.lignesDeReserves(texte)", texte)

    def test_trois_lignes_non_vides_donnent_trois_reserves(self):
        texte = "Purgeur défectueux\n\n  - Schéma à mettre à jour  \r\n2) Extincteur absent\r\n   \n"
        self.assertEqual(self.lignes(texte), ["Purgeur défectueux", "Schéma à mettre à jour", "Extincteur absent"])

    def test_puces_de_debut_retirees(self):
        texte = "- a\n• b\n* c\n1. d\n12) e\n– f\n-g\n•h"
        self.assertEqual(self.lignes(texte), ["a", "b", "c", "d", "e", "f", "g", "h"])

    def test_signes_et_nombres_gardes(self):
        texte = "-20 °C mesurés en chambre froide\n1.5 bar au-dessus du tarage\n2026 : plaque illisible\n- - double"
        self.assertEqual(self.lignes(texte), ["-20 °C mesurés en chambre froide", "1.5 bar au-dessus du tarage",
                                              "2026 : plaque illisible", "- double"])

    def test_puce_seule_ne_donne_rien(self):
        self.assertEqual(self.lignes("-\n•\n2)\n3.\n*  \nVraie réserve"), ["Vraie réserve"])

    def test_doublons_exacts_gardes_et_fins_de_ligne(self):
        self.assertEqual(self.lignes("Fuite\nFuite"), ["Fuite", "Fuite"])
        self.assertEqual(self.lignes("a\rb\r\nc\nd"), ["a", "b", "c", "d"])

    def test_rien(self):
        for valeur in ("", "   \n\r\n\t", None):
            with self.subTest(valeur=valeur):
                self.assertEqual(self.lignes(valeur), [])
        self.assertEqual(self.js("() => Controles.lignesDeReserves()"), [])


class TestUneReserve(CasReserves):
    """reserveLevee, echeanceReserve (D187), etatReserve."""

    def setUp(self):
        super().setUp()
        self.charger(jeu_de_test())

    def echeance(self, reserve):
        return self.js("(r) => Controles.echeanceReserve(r)", reserve)

    def test_reserve_levee(self):
        calcul = "(id) => Controles.reserveLevee(Donnees.trouver('reserves_controle', id))"
        self.assertTrue(self.js(calcul, "RES-00003"))
        self.assertTrue(self.js(calcul, "RES-00012"))          # « oui » relu 1 par Donnees
        self.assertFalse(self.js(calcul, "RES-00001"))
        for reserve in ({"levee": ""}, {"levee": "0"}, {}, None):
            with self.subTest(reserve=reserve):
                self.assertFalse(self.js("(r) => Controles.reserveLevee(r)", reserve))

    def test_levee_avant_la_2_2_date_inconnue_compte_comme_levee(self):
        """D183 : réserve reprise levée, date de levée vide, commentaire « levée avant la 2.2, date inconnue »."""
        reserve = self.js("() => Donnees.trouver('reserves_controle', 'RES-00004')")
        self.assertEqual((reserve["date_levee"], reserve["commentaire_levee"]), ("", COMMENTAIRE_D183))
        etat = self.etat("RES-00004")
        self.assertEqual(etat["statut"], "levée")
        self.assertIsNone(etat["joursRestants"])
        self.assertNotIn("RES-00004", self.ouvertes("CTR-0001"))

    def test_echeance_saisie(self):
        self.assertEqual(self.echeance({"date_controle": "2025-11-12", "echeance_levee": "2026-12-15"}),
                         {"date": "2026-12-15", "parDefaut": False})

    def test_sans_echeance_30_jours_apres_le_controle(self):
        for controle in ("2025-11-12", "2026-01-31", "2028-01-31", "2026-12-15", "2026-03-15", "2024-02-29"):
            with self.subTest(controle=controle):
                attendue = (datetime.date.fromisoformat(controle) + DELAI_D187).isoformat()
                self.assertEqual(self.echeance({"date_controle": controle, "echeance_levee": ""}),
                                 {"date": attendue, "parDefaut": True})
        self.assertEqual(self.echeance({"date_controle": "2025-11-12"})["date"], "2025-12-12")
        # échéance illisible : comme vide
        self.assertEqual(self.echeance({"date_controle": "2025-11-12", "echeance_levee": "bientôt"}),
                         {"date": "2025-12-12", "parDefaut": True})

    def test_date_du_controle_inconnue(self):
        for reserve in ({"date_controle": ""}, {"date_controle": "2026-02-30"}, {"date_controle": "pas une date"},
                        {}, None):
            with self.subTest(reserve=reserve):
                self.assertEqual(self.echeance(reserve), {"date": "", "parDefaut": False})

    def test_etats_a_la_date_passee_en_argument(self):
        attendus = {
            "RES-00001": ("en retard", "2025-12-12", True, -312),
            "RES-00002": ("à lever", "2026-12-15", False, 56),
            "RES-00009": ("à lever", "", False, None),           # date du contrôle inconnue : jamais en retard
            "RES-00010": ("à lever", "2026-10-20", True, 0),     # échéance aujourd'hui : pas encore en retard
            "RES-00011": ("en retard", "2026-10-19", True, -1),
            "RES-00013": ("à lever", "2026-10-25", False, 5),
        }
        for reserve_id, (statut, echeance, par_defaut, jours) in attendus.items():
            with self.subTest(reserve=reserve_id):
                self.assertEqual(self.etat(reserve_id), {"statut": statut, "echeance": echeance,
                                                         "parDefaut": par_defaut, "joursRestants": jours})
        # la date compte : la veille de l'échéance, RES-00011 est encore à lever
        self.assertEqual(self.etat("RES-00011", "2026-10-18")["statut"], "à lever")

    def test_levee_quelle_que_soit_l_echeance(self):
        self.assertEqual(self.etat("RES-00003"), {"statut": "levée", "echeance": "2025-12-12", "parDefaut": True,
                                                  "joursRestants": None})
        self.assertEqual(self.etat("RES-00012")["statut"], "levée")

    def test_statuts_exposes(self):
        self.assertEqual(self.js("() => Controles.STATUTS_RESERVE"), ["en retard", "à lever", "levée"])
        self.assertTrue(self.js("() => Object.isFrozen(Controles.STATUTS_RESERVE)"))
        self.assertEqual(self.js("() => Controles.interne.DELAI_LEVEE_PAR_DEFAUT_JOURS"), 30)


class TestReservesDuControle(CasReserves):
    """reservesDuControle, reservesOuvertes, reservesEnRetard."""

    def setUp(self):
        super().setUp()
        self.charger(jeu_de_test())

    def test_groupees_par_realisation_la_plus_recente_d_abord(self):
        self.assertEqual(self.groupes("CTR-0001"), [
            ["2025-11-12", ["RES-00001", "RES-00002", "RES-00003"]],
            ["2024-11-05", ["RES-00005", "RES-00014", "RES-00004"]],    # ouvertes avant levées
        ])
        self.assertEqual(self.groupes("CTR-0004"), [
            ["2026-09-20", ["RES-00010"]],
            ["2026-09-19", ["RES-00011", "RES-00013", "RES-00012"]],
            ["", ["RES-00009"]],                                        # date inconnue : en dernier
        ])

    def test_controle_sans_reserve(self):
        for controle_id in ("CTR-0005", "CTR-4242", "", None):
            with self.subTest(controle=controle_id):
                self.assertEqual(self.groupes(controle_id), [])
                self.assertEqual(self.ouvertes(controle_id), [])

    def test_reserves_ouvertes(self):
        self.assertEqual(self.ouvertes("CTR-0001"), ["RES-00001", "RES-00002", "RES-00005", "RES-00014"])
        self.assertEqual(self.ouvertes("CTR-0004"), ["RES-00010", "RES-00011", "RES-00013", "RES-00009"])

    def test_reserves_en_retard_des_equipements_suivis(self):
        self.assertEqual(self.en_retard(AUJOURDHUI), [
            ["RES-00005", "CTR-0001", "en retard", "2024-12-05"],
            ["RES-00014", "CTR-0001", "en retard", "2024-12-05"],     # même échéance : par identifiant
            ["RES-00001", "CTR-0001", "en retard", "2025-12-12"],
            ["RES-00011", "CTR-0004", "en retard", "2026-10-19"],
        ])

    def test_reserves_en_retard_a_une_autre_date(self):
        self.assertEqual([ligne[0] for ligne in self.en_retard("2024-12-06")], ["RES-00005", "RES-00014"])
        self.assertEqual(self.en_retard("2024-12-05"), [])

    def test_aucune_ecriture(self):
        avant = self.js("""() => JSON.stringify(['reserves_controle', 'controles_reglementaires', 'equipements']
          .map((table) => Donnees.lignes(table)))""")
        self.js("""() => {
          Donnees.lignes('reserves_controle').forEach((r) => {
            Controles.reserveLevee(r); Controles.echeanceReserve(r); Controles.etatReserve(r, '2026-10-20');
            Controles.adresseOtReserve(r);
          });
          ['CTR-0001', 'CTR-0004'].forEach((id) => { Controles.reservesDuControle(id); Controles.reservesOuvertes(id); });
          Controles.reservesEnRetard('2026-10-20');
        }""")
        apres = self.js("""() => JSON.stringify(['reserves_controle', 'controles_reglementaires', 'equipements']
          .map((table) => Donnees.lignes(table)))""")
        self.assertEqual(avant, apres)


class TestAdresseOt(CasReserves):
    """adresseOtReserve : #/ot/nouveau pré-rempli, rien n'est créé."""

    def setUp(self):
        super().setUp()
        self.charger(jeu_de_test())

    def test_adresse_d_une_reserve(self):
        chemin, parametres = self.adresse(
            "(id) => Controles.adresseOtReserve(Donnees.trouver('reserves_controle', id))", "RES-00001")
        self.assertEqual(chemin, "#/ot/nouveau")
        self.assertEqual(parametres, [("equipement", "EQ-0001"), ("type", "réglementaire"),
                                      ("titre", "Différentiel 30 mA à remplacer"),
                                      ("travail", "Différentiel 30 mA à remplacer"), ("reserve", "RES-00001")])

    def test_titre_coupe_a_80_caracteres_travail_entier(self):
        texte = "Garde-corps de la passerelle & échelle #2 = à refixer ; " + "x" * 30 + " fin après quatre-vingts"
        self.assertGreater(len(texte), 80)
        _, parametres = self.adresse("(texte) => Controles.adresseOtReserve({ id: 'RES-00099', controle_id: 'CTR-0004', "
                                     "texte: texte })", texte)
        valeurs = dict(parametres)
        self.assertEqual(valeurs["titre"], texte[:80])
        self.assertEqual(valeurs["travail"], texte)
        self.assertEqual(valeurs["equipement"], "EQ-0001")

    def test_textes_composes_par_l_ecran(self):
        _, parametres = self.adresse("""(id) => Controles.adresseOtReserve(Donnees.trouver('reserves_controle', id),
          { titre: ' Levée de la réserve — Purgeur défectueux ', travail: 'Purgeur défectueux\\nContrôle du 19/09/2026' })""",
                                     "RES-00011")
        self.assertEqual(parametres, [("equipement", "EQ-0001"), ("type", "réglementaire"),
                                      ("titre", "Levée de la réserve — Purgeur défectueux"),
                                      ("travail", "Purgeur défectueux\nContrôle du 19/09/2026"), ("reserve", "RES-00011")])

    def test_controle_introuvable_et_reserve_absente(self):
        _, parametres = self.adresse(
            "(id) => Controles.adresseOtReserve(Donnees.trouver('reserves_controle', id))", "RES-00008")
        self.assertEqual(dict(parametres)["equipement"], "")
        self.assertEqual(dict(parametres)["reserve"], "RES-00008")
        for reserve in (None, {}, {"id": "  "}):
            with self.subTest(reserve=reserve):
                self.assertEqual(self.js("(r) => Controles.adresseOtReserve(r)", reserve), "")


class TestRepriseD183(CasReserves):
    """Une base 2.1 reprise (Formats.reservesReprises, D183) : observations sur trois lignes, levées ou non."""

    def setUp(self):
        super().setUp()
        charger_scripts(self.page, SCRIPTS_REPRISE)        # règles pures : aucune base chargée

    def test_observations_reprises_puis_lues_par_les_regles(self):
        reprises = self.js("""(jour) => {
          const controles = [
            { id: 'CTR-0101', derniere_date: '2025-04-03', observations: 'Purgeur\\n\\nSoupape\\r\\nManomètre', observations_levees: '1' },
            { id: 'CTR-0102', derniere_date: '2025-04-03', observations: 'Fuite au raccord', observations_levees: '0' },
          ];
          return Formats.reservesReprises(controles, []).map((r) => ({ id: r.id, controle: r.controle_id, texte: r.texte,
            date_levee: r.date_levee, commentaire: r.commentaire_levee, etat: Controles.etatReserve(r, jour) }));
        }""", AUJOURDHUI)
        self.assertEqual([r["texte"] for r in reprises], ["Purgeur", "Soupape", "Manomètre", "Fuite au raccord"])
        for reprise in reprises[:3]:
            with self.subTest(reserve=reprise["id"]):
                self.assertEqual((reprise["date_levee"], reprise["commentaire"]), ("", COMMENTAIRE_D183))
                self.assertEqual(reprise["etat"]["statut"], "levée")
        # non levée : échéance vide à la reprise, 30 jours après le contrôle à l'affichage (D187) → en retard
        self.assertEqual(reprises[3]["etat"], {"statut": "en retard", "echeance": "2025-05-03", "parDefaut": True,
                                               "joursRestants": -535})


# ---------------------------------------------------------------------------
# Jeu de démo : rôles de T417 et calcul Python indépendant
# ---------------------------------------------------------------------------

def lire_demo(nom):
    texte = (DOSSIER_DEMO / (nom + ".csv")).read_bytes().decode("utf-8-sig")
    return list(module_csv.DictReader(io.StringIO(texte, newline=""), delimiter=";"))


def brut(valeur):
    valeur = (valeur or "").strip()
    return valeur[1:] if valeur.startswith("'") else valeur


def date_reference():
    texte = (RACINE / "js" / "demo-donnees.js").read_text(encoding="utf-8")
    return re.search(r"""dateReference:\s*["'](\d{4}-\d{2}-\d{2})["']""", texte).group(1)


def jour(texte):
    texte = brut(texte)[:10]
    return datetime.date.fromisoformat(texte) if texte else None


def echeance_python(reserve):
    saisie = jour(reserve["echeance_levee"])
    if saisie:
        return saisie
    controle = jour(reserve["date_controle"])
    return controle + DELAI_D187 if controle else None


class TestDemo(CasReserves):
    """Les règles sur le jeu de démo brut (sans décalage), à la date de référence du générateur."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reference = date_reference()
        cls.scenarios = scenarios_demo()
        cls.tables = {fichier.stem: fichier.read_bytes().decode("utf-8-sig") for fichier in DOSSIER_DEMO.glob("*.csv")}
        cls.reserves = {brut(r["id"]): r for r in lire_demo("reserves_controle")}
        cls.controles = {brut(c["id"]): c for c in lire_demo("controles_reglementaires")}

    def setUp(self):
        super().setUp()
        self.charger(self.tables)

    def test_reserve_en_retard(self):
        identifiant = self.scenarios["reserve_en_retard"]
        reserve = self.reserves[identifiant]
        etat = self.etat(identifiant, self.reference)
        self.assertEqual(etat["statut"], "en retard")
        self.assertTrue(etat["parDefaut"])
        self.assertEqual(etat["echeance"], (jour(reserve["date_controle"]) + DELAI_D187).isoformat())
        self.assertLess(etat["joursRestants"], 0)

    def test_reserve_levee(self):
        identifiant = self.scenarios["reserve_levee"]
        reserve = self.reserves[identifiant]
        self.assertEqual(self.etat(identifiant, self.reference)["statut"], "levée")
        self.assertNotEqual(brut(reserve["date_levee"]), "")
        self.assertNotEqual(brut(reserve["ot_id"]), "")

    def test_reserve_a_echeance(self):
        identifiant = self.scenarios["reserve_a_echeance"]
        etat = self.etat(identifiant, self.reference)
        self.assertEqual(etat["statut"], "à lever")
        self.assertFalse(etat["parDefaut"])
        self.assertEqual(etat["echeance"], brut(self.reserves[identifiant]["echeance_levee"]))
        self.assertGreater(etat["joursRestants"], 0)

    def test_controle_reserves_groupe_ouvertes_avant_levees(self):
        controle_id = self.scenarios["controle_reserves"]
        attendues = sorted((r for r in self.reserves.values() if brut(r["controle_id"]) == controle_id),
                           key=lambda r: (brut(r["levee"]) == "1", brut(r["id"])))
        self.assertIn(self.scenarios["reserve_levee"], [brut(r["id"]) for r in attendues])
        self.assertIn(self.scenarios["reserve_a_echeance"], [brut(r["id"]) for r in attendues])
        dates = {brut(r["date_controle"]) for r in attendues}
        self.assertEqual(len(dates), 1)
        self.assertEqual(self.groupes(controle_id), [[dates.pop(), [brut(r["id"]) for r in attendues]]])
        self.assertEqual(self.ouvertes(controle_id),
                         [brut(r["id"]) for r in attendues if brut(r["levee"]) != "1"])

    def test_reserves_en_retard_egales_au_calcul_python(self):
        equipements = {brut(e["id"]): e for e in lire_demo("equipements")}
        reference = datetime.date.fromisoformat(self.reference)
        attendues = []
        for reserve in self.reserves.values():
            controle = self.controles.get(brut(reserve["controle_id"]))
            equipement = equipements.get(brut(controle["equipement_id"])) if controle else None
            echeance = echeance_python(reserve)
            if (brut(reserve["levee"]) != "1" and equipement and brut(equipement["actif"]) != "0"
                    and brut(equipement["statut"]) != "rebut" and echeance and echeance < reference):
                attendues.append((echeance.isoformat(), brut(reserve["id"]), brut(controle["id"])))
        attendues.sort()
        self.assertTrue(attendues)
        self.assertEqual(self.en_retard(self.reference),
                         [[reserve_id, controle_id, "en retard", echeance] for echeance, reserve_id, controle_id in attendues])
        self.assertIn(self.scenarios["reserve_en_retard"], [reserve_id for _, reserve_id, _ in attendues])

    def test_adresse_ot_de_la_reserve_en_retard(self):
        identifiant = self.scenarios["reserve_en_retard"]
        reserve = self.reserves[identifiant]
        _, parametres = self.adresse(
            "(id) => Controles.adresseOtReserve(Donnees.trouver('reserves_controle', id))", identifiant)
        valeurs = dict(parametres)
        self.assertEqual(valeurs["equipement"], brut(self.controles[brut(reserve["controle_id"])]["equipement_id"]))
        self.assertEqual(valeurs["type"], "réglementaire")
        self.assertEqual(valeurs["reserve"], identifiant)
        self.assertEqual(valeurs["travail"], brut(reserve["texte"]))
        self.assertEqual(valeurs["titre"], brut(reserve["texte"])[:80].rstrip())


if __name__ == "__main__":
    unittest.main()
