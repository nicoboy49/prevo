"""Tests des règles pures du lot 3 : contrôles réglementaires, équipe, planning
(ARCHITECTURE.md §15.5, §15.7, §15.8 ; tâche T44).

Deux familles :
    - jeu construit À LA MAIN dans ce fichier, date fixe passée en argument (aujourd'hui = mardi
      20/10/2026 ; la semaine du 19 au 25/10/2026 traverse le passage à l'heure d'hiver) :
      Controles.ajouterMois / prochaineDate / etat / sous30Jours, Equipe.etatHabilitation /
      habilitationsQuiComptent / aRenouveler, Planning.lundiDe / joursDeLaSemaine /
      ordresDeLaSemaine / chargeSemaine / semaine ;
    - jeu de démo (donnees/demo, SANS décalage de dates, aujourd'hui = date de référence du
      générateur) : rôles de scénario du lot 3 (tests/fixtures/demo-scenarios.json) et égalité avec
      un calcul Python indépendant (contrôles sous 30 jours, habilitations à renouveler, charges des
      4 semaines du planning).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_regles_lot3.py" -v
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
    "js/modules/controles-regles.js",
    "js/modules/equipe-regles.js",
    "js/modules/planning-regles.js",
]

AUJOURDHUI = "2026-10-20"          # un mardi ; semaine du lundi 19 au dimanche 25/10/2026


def csv(entete, lignes):
    """Texte CSV au format §3.1 (séparateur ;, fins de ligne CRLF)."""
    return "\r\n".join([entete] + list(lignes)) + "\r\n"


EQUIPEMENTS = csv("id;repere;designation;statut;actif", [
    "EQ-0001;PR-01;Presse;en service;1",
    "EQ-0002;PR-02;Vieille presse;rebut;1",
    "EQ-0003;PR-03;Presse désactivée;en service;0",
])

CONTROLES = csv("id;equipement_id;nature;periodicite_mois;derniere_date;prochaine_date;observations;observations_levees", [
    "CTR-0001;EQ-0001;VGP;12;2025-10-01;2026-10-01;Crochet usé;0",       # en retard (+ observations)
    "CTR-0002;EQ-0001;Électricité;12;2025-11-19;2026-11-19;;1",          # à planifier (30 j pile)
    "CTR-0003;EQ-0001;Aération;12;2025-11-20;2026-11-20;;1",             # à jour (31 j)
    "CTR-0004;EQ-0001;Pression;1;2026-01-31;;;1",                        # prochaine calculée : 28/02 → en retard
    "CTR-0005;EQ-0001;Inconnu;;;;;1",                                    # date inconnue → à planifier
    "CTR-0006;EQ-0001;Réservoir;36;2024-05-01;2027-05-01;Purgeur à remplacer;0",   # observations à lever
    "CTR-0007;EQ-0001;Levage;12;2026-05-01;2027-05-01;Remarque levée;1",          # à jour
    "CTR-0008;EQ-0002;VGP rebut;12;2025-10-01;2026-10-01;;1",            # équipement au rebut
    "CTR-0009;EQ-0003;VGP inactif;12;2025-10-25;2026-10-25;;1",          # équipement inactif
    "CTR-0010;EQ-0001;Aujourd'hui;12;2025-10-20;2026-10-20;;1",          # à planifier, aujourd'hui
    "CTR-0011;EQ-9999;Absent;12;2025-10-21;2026-10-21;;1",               # équipement introuvable
    "CTR-0012;EQ-0001;Froid;12;2025-11-19;2026-11-19;Fuite;0",           # observations + à planifier
])

TECHNICIENS = csv("id;nom;prenom;capacite_h_semaine;actif", [
    "TEC-0001;Moreau;Julien;35;1",
    "TEC-0002;Benali;Karim;35;1",
    "TEC-0003;Ancien;Paul;35;0",
    "TEC-0004;Garnier;Thomas;;1",
])

HABILITATIONS = csv("id;technicien_id;intitule;date_obtention;date_echeance", [
    "HAB-0001;TEC-0001;BR;2023-01-01;2026-03-01",          # échue, mais renouvelée par HAB-0002
    "HAB-0002;TEC-0001;BR;2026-02-20;2029-02-20",
    "HAB-0003;TEC-0001;caces  r489;2021-12-02;2026-12-02",  # 43 jours → à renouveler
    "HAB-0004;TEC-0002;H0V;2024-05-14;2026-10-20",          # échéance aujourd'hui → à renouveler (0)
    "HAB-0005;TEC-0002;B2V;2026-11-01;2029-11-01",          # pas encore valable
    "HAB-0006;TEC-0002;BR;2020-01-01;",                     # valide, sans échéance
    "HAB-0007;TEC-0003;BR;2020-01-01;2026-01-01",           # échue, technicien inactif
    "HAB-0008;TEC-0004;BR;2023-06-01;2026-05-31",           # échue (−142 jours)
    "HAB-0009;TEC-0004;CACES R489;2021-12-19;2026-12-19",   # 60 jours… mais HAB-0010 compte
    "HAB-0010;TEC-0004;CACES R489;2021-12-20;2026-12-20",   # 61 jours → valide
])

ORDRES = csv("id;statut;technicien_id;date_prevue;temps_prevu_h;priorite;equipement_id", [
    "OT-2026-0001;Planifié;TEC-0001;2026-10-19;8;P2;EQ-0001",
    "OT-2026-0002;En cours;TEC-0001;2026-10-21;;P1;EQ-0001",
    "OT-2026-0003;Planifié;TEC-0001;2026-10-25;30;P3;EQ-0001",              # dimanche : dans la semaine
    "OT-2026-0004;Clôturé techniquement;TEC-0001;2026-10-20;5;P2;EQ-0001",
    "OT-2026-0005;Annulé;TEC-0002;2026-10-20;5;P2;EQ-0001",
    "OT-2026-0006;Planifié;TEC-0002;2026-10-26;4;P2;EQ-0001",              # semaine suivante
    "OT-2026-0007;Préparé;;2026-10-22;3;P2;EQ-0001",                       # sans technicien
    "OT-2026-0008;Préparé;TEC-0002;2026-10-22;2;P3;EQ-0001",               # dans la grille
    "OT-2026-0009;Préparé;TEC-0002;2026-11-05;2;P1;EQ-0001",               # autre semaine
    "OT-2026-0010;Préparé;;;1;P1;EQ-0001",                                 # ni technicien ni date
    "OT-2026-0011;Planifié;TEC-0003;2026-10-23;6;P3;EQ-0001",              # technicien inactif
    "OT-2026-0012;Créé;TEC-0004;2026-10-24;2.5;P4;EQ-0001",
    "OT-2026-0013;Planifié;TEC-9999;2026-10-19;1;P4;EQ-0001",              # technicien inconnu
])


def jeu_de_test():
    return {"equipements": EQUIPEMENTS, "controles_reglementaires": CONTROLES, "techniciens": TECHNICIENS,
            "habilitations": HABILITATIONS, "ordres_travail": ORDRES}


class CasRegles(CasNavigateur):
    """Page vide + scripts du lot 3 + jeu de données passé à StockageDemo (sans décalage)."""

    def charger(self, tables):
        charger_scripts(self.page, SCRIPTS)
        self.page.evaluate("""async (tables) => {
          Donnees.initialiser(StockageDemo.creer(tables), { poste: 'Poste test', profil: 'Responsable test' });
          await Donnees.chargerTout();
        }""", tables)

    def js(self, script, argument=None):
        return self.page.evaluate(script, argument)


# ---------------------------------------------------------------------------
# Contrôles réglementaires (§15.7)
# ---------------------------------------------------------------------------

class TestControles(CasRegles):

    def setUp(self):
        super().setUp()
        self.charger(jeu_de_test())

    def etat(self, controle_id, jour=AUJOURDHUI):
        return self.js("([id, jour]) => Controles.etat(Donnees.trouver('controles_reglementaires', id), jour)",
                       [controle_id, jour])

    def test_ajouter_mois_fin_de_mois_annees_bissextiles_et_valeurs_invalides(self):
        cas = [("2026-01-31", 1, "2026-02-28"), ("2028-01-31", 1, "2028-02-29"), ("2026-12-15", 1, "2027-01-15"),
               ("2026-03-31", -1, "2026-02-28"), ("2026-10-20", 6, "2027-04-20"), ("2026-10-20", 12, "2027-10-20"),
               ("2026-08-31", 6, "2027-02-28"), ("2026-10-20", "3", "2027-01-20"), ("2026-10-20", 0, "2026-10-20"),
               ("2026-10-20", "", ""), ("pas une date", 1, ""), ("2026-10-20", 1.5, ""), ("2026-10-20 14:30", 1, "2026-11-20")]
        for depart, mois, attendu in cas:
            with self.subTest(depart=depart, mois=mois):
                self.assertEqual(self.js("([d, n]) => Controles.ajouterMois(d, n)", [depart, mois]), attendu)

    def test_prochaine_date_enregistree_sinon_calculee_sinon_vide(self):
        prochaine = "(id) => Controles.prochaineDate(Donnees.trouver('controles_reglementaires', id))"
        self.assertEqual(self.js(prochaine, "CTR-0001"), "2026-10-01")
        self.assertEqual(self.js(prochaine, "CTR-0004"), "2026-02-28")
        self.assertEqual(self.js(prochaine, "CTR-0005"), "")

    def test_statuts_dans_l_ordre_de_priorite_et_secondaires(self):
        attendus = {
            "CTR-0001": ("en retard", ["observations à lever"], -19),
            "CTR-0002": ("à planifier", [], 30),
            "CTR-0003": ("à jour", [], 31),
            "CTR-0004": ("en retard", [], -234),
            "CTR-0005": ("à planifier", [], None),
            "CTR-0006": ("observations à lever", [], 193),
            "CTR-0007": ("à jour", [], 193),
            "CTR-0010": ("à planifier", [], 0),
            "CTR-0012": ("observations à lever", ["à planifier"], 30),
        }
        for controle_id, (statut, secondaires, jours) in attendus.items():
            with self.subTest(controle=controle_id):
                etat = self.etat(controle_id)
                self.assertEqual(etat["statut"], statut)
                self.assertEqual(etat["secondaires"], secondaires)
                self.assertEqual(etat["joursRestants"], jours)
                self.assertTrue(etat["raison"])
        self.assertIn("date inconnue", self.etat("CTR-0005")["raison"])
        self.assertIn("aujourd'hui", self.etat("CTR-0010")["raison"])
        self.assertIn("19 jours", self.etat("CTR-0001")["raison"])
        self.assertEqual(self.js("Controles.STATUTS"), ["en retard", "observations à lever", "à planifier", "à jour"])

    def test_sous_30_jours_equipements_suivis_seulement_dates_inconnues_d_abord(self):
        ids = self.js("(jour) => Controles.sous30Jours(jour).map((c) => c.id)", AUJOURDHUI)
        self.assertEqual(ids, ["CTR-0005", "CTR-0004", "CTR-0001", "CTR-0010", "CTR-0002", "CTR-0012"])


# ---------------------------------------------------------------------------
# Équipe et habilitations (§15.8)
# ---------------------------------------------------------------------------

class TestEquipe(CasRegles):

    def setUp(self):
        super().setUp()
        self.charger(jeu_de_test())

    def etat(self, habilitation_id, jour=AUJOURDHUI):
        return self.js("([id, jour]) => Equipe.etatHabilitation(Donnees.trouver('habilitations', id), jour)",
                       [habilitation_id, jour])

    def test_etat_d_une_habilitation(self):
        attendus = {
            "HAB-0001": ("échue", -233, False), "HAB-0002": ("valide", 854, False),
            "HAB-0003": ("à renouveler", 43, False), "HAB-0004": ("à renouveler", 0, False),
            "HAB-0005": ("pas encore valable", 1108, False), "HAB-0006": ("valide", None, True),
            "HAB-0008": ("échue", -142, False), "HAB-0009": ("à renouveler", 60, False),
            "HAB-0010": ("valide", 61, False),
        }
        for habilitation_id, (statut, jours, sans_echeance) in attendus.items():
            with self.subTest(habilitation=habilitation_id):
                etat = self.etat(habilitation_id)
                self.assertEqual((etat["statut"], etat["joursRestants"], etat["sansEcheance"]),
                                 (statut, jours, sans_echeance))

    def test_habilitations_qui_comptent_la_plus_lointaine_par_intitule(self):
        comptent = "(id) => Equipe.habilitationsQuiComptent(id).map((h) => h.id)"
        self.assertEqual(self.js(comptent, "TEC-0001"), ["HAB-0002", "HAB-0003"])      # BR renouvelée
        self.assertEqual(self.js(comptent, "TEC-0002"), ["HAB-0005", "HAB-0006", "HAB-0004"])
        self.assertEqual(self.js(comptent, "TEC-0004"), ["HAB-0008", "HAB-0010"])
        self.assertEqual(self.js(comptent, "TEC-0099"), [])

    def test_a_renouveler_techniciens_actifs_les_plus_urgentes_d_abord(self):
        resultat = self.js("""(jour) => Equipe.aRenouveler(jour).map((e) =>
            [e.technicien.id, e.habilitation.id, e.etat.statut, e.etat.joursRestants])""", AUJOURDHUI)
        self.assertEqual(resultat, [["TEC-0004", "HAB-0008", "échue", -142],
                                    ["TEC-0002", "HAB-0004", "à renouveler", 0],
                                    ["TEC-0001", "HAB-0003", "à renouveler", 43]])


# ---------------------------------------------------------------------------
# Planning (§15.5)
# ---------------------------------------------------------------------------

class TestPlanning(CasRegles):

    def setUp(self):
        super().setUp()
        self.charger(jeu_de_test())

    def test_lundi_et_jours_de_la_semaine_en_utc(self):
        self.assertEqual(self.js("Planning.lundiDe('2026-10-25')"), "2026-10-19")     # dimanche du changement d'heure
        self.assertEqual(self.js("Planning.lundiDe('2026-10-26')"), "2026-10-26")
        self.assertEqual(self.js("Planning.lundiDe('2026-03-29')"), "2026-03-23")     # passage à l'heure d'été
        self.assertEqual(self.js("Planning.joursDeLaSemaine('2026-10-21')"),
                         ["2026-10-19", "2026-10-20", "2026-10-21", "2026-10-22", "2026-10-23", "2026-10-24", "2026-10-25"])

    def test_ordres_de_la_semaine_ouverts_avec_technicien_et_date_tries(self):
        self.assertEqual(self.js("Planning.ordresDeLaSemaine('2026-10-19').map((ot) => ot.id)"),
                         ["OT-2026-0002", "OT-2026-0001", "OT-2026-0008", "OT-2026-0011", "OT-2026-0003",
                          "OT-2026-0013", "OT-2026-0012"])

    def test_charge_d_une_semaine_temps_vide_compte_zero(self):
        self.assertEqual(self.js("Planning.chargeSemaine('TEC-0001', '2026-10-21')"), 38)
        self.assertEqual(self.js("Planning.chargeSemaine('TEC-0002', '2026-10-19')"), 2)
        self.assertEqual(self.js("Planning.chargeSemaine('TEC-0002', '2026-10-26')"), 4)
        self.assertEqual(self.js("Planning.chargeSemaine('TEC-0004', '2026-10-19')"), 2.5)

    def test_grille_de_la_semaine(self):
        grille = self.js("""() => { const s = Planning.semaine('2026-10-22');
            return { lundi: s.lundi, jours: s.jours,
              lignes: s.lignes.map((l) => ({ id: l.technicien.id, charge: l.charge, capacite: l.capacite,
                surcharge: l.surcharge, inactif: Boolean(l.inactif),
                cases: Object.fromEntries(Object.entries(l.cases).filter(([, ots]) => ots.length)
                  .map(([jour, ots]) => [jour, ots.map((ot) => ot.id)])) })),
              aPlanifier: s.aPlanifier.map((ot) => ot.id) }; }""")
        self.assertEqual(grille["lundi"], "2026-10-19")
        self.assertEqual(len(grille["jours"]), 7)
        self.assertEqual([l["id"] for l in grille["lignes"]], ["TEC-0002", "TEC-0004", "TEC-0001", "TEC-0003", "TEC-9999"])
        par_id = {l["id"]: l for l in grille["lignes"]}
        self.assertEqual(par_id["TEC-0001"]["cases"], {"2026-10-19": ["OT-2026-0001"], "2026-10-21": ["OT-2026-0002"],
                                                        "2026-10-25": ["OT-2026-0003"]})
        self.assertEqual((par_id["TEC-0001"]["charge"], par_id["TEC-0001"]["capacite"], par_id["TEC-0001"]["surcharge"]),
                         (38, 35, True))
        self.assertEqual((par_id["TEC-0002"]["charge"], par_id["TEC-0002"]["surcharge"]), (2, False))
        self.assertEqual((par_id["TEC-0004"]["capacite"], par_id["TEC-0004"]["surcharge"]), (None, False))
        self.assertTrue(par_id["TEC-0003"]["inactif"])
        self.assertTrue(par_id["TEC-9999"]["inactif"])
        self.assertEqual(grille["aPlanifier"], ["OT-2026-0009", "OT-2026-0010", "OT-2026-0007"])


# ---------------------------------------------------------------------------
# Jeu de démo : rôles de scénario et calcul Python indépendant
# ---------------------------------------------------------------------------

DOSSIER_DEMO = RACINE / "donnees" / "demo"


def lire_demo(nom):
    texte = (DOSSIER_DEMO / (nom + ".csv")).read_text(encoding="utf-8-sig")
    return list(module_csv.DictReader(io.StringIO(texte), delimiter=";"))


def brut(valeur):
    valeur = (valeur or "").strip()
    return valeur[1:] if valeur.startswith("'") else valeur


def date_reference():
    texte = (RACINE / "js" / "demo-donnees.js").read_text(encoding="utf-8")
    return re.search(r"""dateReference:\s*["'](\d{4}-\d{2}-\d{2})["']""", texte).group(1)


def jour(texte):
    return datetime.date.fromisoformat(brut(texte)[:10]) if brut(texte)[:10] else None


def ajouter_mois(date, mois):
    total = date.year * 12 + date.month - 1 + mois
    annee, mois0 = divmod(total, 12)
    return datetime.date(annee, mois0 + 1, min(date.day, calendar.monthrange(annee, mois0 + 1)[1]))


def nombre(valeur):
    texte = brut(valeur).replace(",", ".")
    try:
        return float(texte) if texte else None
    except ValueError:
        return None


class TestDemo(CasRegles):
    """Les règles sur le jeu de démo brut (sans décalage), à la date de référence du générateur."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reference = date_reference()
        cls.scenarios = scenarios_demo()
        cls.tables = {fichier.stem: fichier.read_bytes().decode("utf-8-sig") for fichier in DOSSIER_DEMO.glob("*.csv")}

    def setUp(self):
        super().setUp()
        self.charger(self.tables)

    def test_roles_des_controles_donnent_leur_statut(self):
        for role, statut in (("controle_en_retard", "en retard"), ("controle_a_planifier", "à planifier"),
                             ("controle_observations", "observations à lever"), ("controle_a_jour", "à jour")):
            with self.subTest(role=role):
                etat = self.js("([id, jour]) => Controles.etat(Donnees.trouver('controles_reglementaires', id), jour)",
                               [self.scenarios[role], self.reference])
                self.assertEqual(etat["statut"], statut)

    def test_sous_30_jours_egal_au_calcul_python(self):
        aujourdhui = datetime.date.fromisoformat(self.reference)
        equipements = {e["id"]: e for e in lire_demo("equipements")}
        attendus = []
        for controle in lire_demo("controles_reglementaires"):
            equipement = equipements.get(controle["equipement_id"])
            if not equipement or brut(equipement["actif"]) == "0" or equipement["statut"] == "rebut":
                continue
            prochaine = jour(controle["prochaine_date"])
            periodicite = nombre(controle["periodicite_mois"])
            if prochaine is None and jour(controle["derniere_date"]) and periodicite and periodicite > 0:
                prochaine = ajouter_mois(jour(controle["derniere_date"]), int(periodicite))
            if prochaine is None or prochaine <= aujourdhui + datetime.timedelta(days=30):
                attendus.append(controle["id"])
        obtenus = self.js("(jour) => Controles.sous30Jours(jour).map((c) => c.id)", self.reference)
        self.assertEqual(sorted(obtenus), sorted(attendus))
        for role in ("controle_en_retard", "controle_a_planifier"):
            self.assertIn(self.scenarios[role], obtenus)
        self.assertNotIn(self.scenarios["controle_a_jour"], obtenus)

    def test_habilitations_a_renouveler_egal_au_calcul_python(self):
        aujourdhui = datetime.date.fromisoformat(self.reference)
        actifs = {t["id"] for t in lire_demo("techniciens") if brut(t["actif"]) != "0"}
        comptent = {}
        for habilitation in lire_demo("habilitations"):
            cle = (habilitation["technicien_id"], re.sub(r"\s+", "", habilitation["intitule"].lower()))
            echeance = jour(habilitation["date_echeance"]) or datetime.date.max
            if cle not in comptent or echeance > comptent[cle][0]:
                comptent[cle] = (echeance, habilitation["id"])
        attendus = sorted(identifiant for (technicien, _), (echeance, identifiant) in comptent.items()
                          if technicien in actifs and echeance != datetime.date.max
                          and (echeance - aujourdhui).days <= 60)
        obtenus = self.js("(jour) => Equipe.aRenouveler(jour).map((e) => e.habilitation.id)", self.reference)
        self.assertEqual(sorted(obtenus), attendus)
        self.assertTrue(attendus, "la démo doit contenir des habilitations à renouveler")

    def test_charges_des_quatre_semaines_egales_au_calcul_python_et_surcharge(self):
        lundi = datetime.date.fromisoformat(self.js("(jour) => Planning.lundiDe(jour)", self.reference))
        ordres = lire_demo("ordres_travail")
        fermes = ("Clôturé techniquement", "Clôturé administrativement", "Annulé")
        for numero in range(4):
            debut = lundi + datetime.timedelta(days=7 * numero)
            fin = debut + datetime.timedelta(days=6)
            for technicien in lire_demo("techniciens"):
                attendue = sum((nombre(ot["temps_prevu_h"]) or 0) for ot in ordres
                               if ot["statut"] not in fermes and ot["technicien_id"] == technicien["id"]
                               and jour(ot["date_prevue"]) and debut <= jour(ot["date_prevue"]) <= fin)
                with self.subTest(semaine=debut.isoformat(), technicien=technicien["id"]):
                    obtenue = self.js("([t, l]) => Planning.chargeSemaine(t, l)", [technicien["id"], debut.isoformat()])
                    self.assertAlmostEqual(obtenue, attendue, places=6)
        surcharge = self.js("""([t, l]) => Planning.semaine(l).lignes.find((ligne) => ligne.technicien.id === t).surcharge""",
                            [self.scenarios["technicien_surcharge"], self.scenarios["semaine_surcharge"]])
        self.assertTrue(surcharge)

    def test_ot_a_planifier_dans_la_colonne_a_planifier(self):
        a_planifier = self.js("(jour) => Planning.semaine(jour).aPlanifier.map((ot) => ot.id)", self.reference)
        for role in ("ot_a_planifier", "ot_a_planifier_br", "ot_a_planifier_piece_manquante"):
            with self.subTest(role=role):
                self.assertIn(self.scenarios[role], a_planifier)


if __name__ == "__main__":
    unittest.main()
