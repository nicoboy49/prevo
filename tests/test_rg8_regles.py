"""Tests des règles pures de RG8 bloquante (T436 ; D186, D191 ; CS178, CS180 ; conception L2-L3 §7.1, §7.2,
§7.5) : Ordres.habilitationsExigees, controleHabilitation, marqueurDerogation, lireDerogation,
derogationAccordee, et Ordres.verifierHabilitation réécrite au-dessus (même message).

Deux familles :
    - jeu construit À LA MAIN dans ce fichier, date fixe passée en argument (date prévue des OT : vendredi
      20/11/2026) ;
    - jeu de démo (donnees/demo, SANS décalage de dates, à la date de référence du générateur) : l'OT de
      l'armoire AE-03 (rôle equipement_br) et le technicien à BR échue (rôle technicien_br_echue).

Rien n'est écrit : seules les règles pures sont appelées (les écritures et les écrans sont T437 à T439).

Lancer depuis la racine du projet (tests à navigateur : au travers du verrou du chantier) :
    py -X utf8 -m unittest discover -s tests -p "test_rg8_regles.py" -v
"""
import csv as module_csv
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
    "js/modules/ordres-regles.js",
    "js/modules/equipe-regles.js",
]

DATE = "2026-11-20"                # date prévue des OT du jeu construit


def csv(entete, lignes):
    """Texte CSV au format §3.1 (séparateur ;, fins de ligne CRLF, champs à « ; » entre guillemets)."""
    sortie = io.StringIO()
    ecrivain = module_csv.writer(sortie, delimiter=";", lineterminator="\r\n")
    ecrivain.writerow(entete.split(";"))
    for ligne in lignes:
        ecrivain.writerow(ligne if isinstance(ligne, (list, tuple)) else ligne.split(";"))
    return sortie.getvalue()


EQUIPEMENTS = csv("id;repere;designation;statut;actif;habilitation_requise", [
    "EQ-0001;PR-01;Presse;en service;1;",                                  # aucune exigence
    "EQ-0002;AE-03;Armoire électrique;en service;1;BR",
    "EQ-0003;TR-01;Transformateur;en service;1;BR, B2V / H0V",
    "EQ-0004;CH-01;Chariot élévateur;en service;1;CACES R489",
])

TECHNICIENS = csv("id;nom;prenom;actif", [
    "TEC-0001;Moreau;Julien;1",
    "TEC-0002;Benali;Karim;1",
    "TEC-0003;Petit;Sophie;1",
    "TEC-0004;Garnier;Thomas;1",
    "TEC-0005;Roux;Léa;1",
    "TEC-0006;Nouveau;Sans habilitation;1",
])

HABILITATIONS = csv("id;technicien_id;intitule;date_obtention;date_echeance", [
    "HAB-0001;TEC-0001;BR;2025-03-10;2028-03-10",           # tout valide
    "HAB-0002;TEC-0001;B2V;2025-03-10;2028-03-10",
    "HAB-0003;TEC-0001;H0V;2025-03-10;2028-03-10",
    "HAB-0004;TEC-0004;BR;2023-06-01;2026-05-31",           # BR échue le 31/05/2026
    "HAB-0005;TEC-0004;H0V;2025-11-10;2028-11-10",
    "HAB-0006;TEC-0002;BR;2023-01-01;2026-03-01",           # échue…
    "HAB-0007;TEC-0002;BR;2026-12-01;2029-12-01",           # … et renouvelée le 01/12 : pas encore obtenue
    "HAB-0008;TEC-0003;caces  r489;2024-02-20;2029-02-20",  # casse et espaces ignorés
    "HAB-0009;TEC-0003;BR;2020-01-01;",                     # échéance vide : pas de borne haute (Q10)
    "HAB-0010;TEC-0003;B2V;;2027-01-01",                    # obtention vide : pas de borne basse (Q10)
    "HAB-0011;TEC-0003;H0V;2025-01-01;2026-02-30",          # échéance illisible : échue
    "HAB-0012;TEC-0005;BR;2026-11-20;2029-11-20",           # obtenue le jour même
    "HAB-0013;TEC-0005;H0V;2023-11-20;2026-11-20",          # échue le soir du 20/11 (borne comprise)
])

ORDRES = csv("id;statut;type;priorite;equipement_id;technicien_id;date_prevue;habilitation_requise", [
    "OT-2026-0001;Préparé;correctif différé;P2;EQ-0001;TEC-0004;2026-11-20;",           # aucune exigence
    "OT-2026-0002;Préparé;correctif différé;P2;EQ-0002;TEC-0004;2026-11-20;",           # BR (équipement)
    "OT-2026-0003;Préparé;correctif différé;P2;EQ-0002;;2026-11-20;H0V",                # BR (éq.) + H0V (OT)
    "OT-2026-0004;Préparé;correctif différé;P2;EQ-0003;;2026-11-20;b r/ CACES R489 ,, h0v",
    "OT-2026-0005;Créé;correctif différé;P2;EQ-0001;;;CACES R489",                       # exigence de l'OT seul
    "OT-2026-0006;Préparé;correctif différé;P2;EQ-9999;;2026-11-20;BR",                 # équipement introuvable
    "OT-2026-0007;Préparé;correctif différé;P2;EQ-0001;;2026-11-20; , / ",              # séparateurs seuls
])

MOTIF = "Électricien du site présent ; consignation faite par lui"


def marqueur(technicien, date, liste, motif=MOTIF):
    return "dérogation habilitation : %s le %s sans %s ; motif : %s" % (technicien, date, liste, motif)


ENTETE_JOURNAL = "id;date_heure;poste;profil;table;id_ligne;action"
JOURNAL_LIGNES = [
    ["J-20261108104200-AAAA", "2026-11-08 10:42", "Poste test", "Responsable test", "ordres_travail",
     "OT-2026-0003", "modification : technicien_id, date_prevue — préparation ; "
     + marqueur("TEC-0004", DATE, "BR (échue)")],
    ["J-20261109090000-BBBB", "2026-11-09 09:00", "Poste test", "Responsable test", "ordres_travail",
     "OT-2026-0003", marqueur("TEC-0002", DATE, "BR (pas encore obtenue)")],
    ["J-20261109093000-CCCC", "2026-11-09 09:30", "Poste test", "Responsable test", "ordres_travail",
     "OT-2026-0003", marqueur("TEC-0004", "2026-11-21", "BR (échue)")],
    ["J-20261109100000-DDDD", "2026-11-09 10:00", "Poste test", "Responsable test", "ordres_travail",
     "OT-2026-0002", marqueur("TEC-0004", DATE, "BR (échue)")],
    ["J-20261109110000-EEEE", "2026-11-09 11:00", "Poste test", "Responsable test", "ordres_travail",
     "OT-2026-0003", marqueur("TEC-0004", DATE, "BR (échue), H0V (absente)")],
    ["J-20261109113000-FFFF", "2026-11-09 11:30", "Poste test", "Responsable test", "equipements",
     "OT-2026-0003", marqueur("TEC-0004", DATE, "BR (échue)")],
    ["J-20261109114500-GGGG", "2026-11-09 11:45", "Poste test", "Responsable test", "ordres_travail",
     "OT-2026-0003", marqueur("TEC-0004", DATE, "BR (échue)", motif="")],
    ["J-20261109120000-HHHH", "2026-11-09 12:00", "Poste test", "Responsable test", "ordres_travail",
     "OT-2026-0003", "planification ; " + marqueur("TEC-0004", DATE, "b r (échue)", motif="second acte")],
    ["J-20261109130000-IIII", "2026-11-09 13:00", "Poste test", "Responsable test", "ordres_travail",
     "OT-2026-0003", "avertissement habilitation : TEC-0004 sans BR valide au 2026-11-20"],
]
JOURNAL = csv(ENTETE_JOURNAL, JOURNAL_LIGNES)


def jeu_de_test():
    return {"equipements": EQUIPEMENTS, "techniciens": TECHNICIENS, "habilitations": HABILITATIONS,
            "ordres_travail": ORDRES, "journal": JOURNAL}


class CasRg8(CasNavigateur):
    """Page vide + scripts des règles des OT et de l'équipe + jeu passé à StockageDemo (sans décalage)."""

    def charger(self, tables):
        charger_scripts(self.page, SCRIPTS)
        self.page.evaluate("""async (tables) => {
          Donnees.initialiser(StockageDemo.creer(tables), { poste: 'Poste test', profil: 'Responsable test' });
          await Donnees.chargerTout();
        }""", tables)

    def js(self, script, argument=None):
        return self.page.evaluate(script, argument)

    def controle(self, ot, technicien, date=DATE):
        return self.js("([ot, technicien, date]) => Ordres.controleHabilitation(ot, technicien, date)",
                       [ot, technicien, date])

    def raisons(self, ot, technicien, date=DATE):
        return [(m["intitule"], m["raison"]) for m in self.controle(ot, technicien, date)["manquantes"]]


# ---------------------------------------------------------------------------
# §7.1 Ce que l'OT exige
# ---------------------------------------------------------------------------

class TestExigences(CasRg8):

    def setUp(self):
        super().setUp()
        self.charger(jeu_de_test())

    def exigees(self, ot):
        return [(e["intitule"], e["origines"]) for e in self.js("(ot) => Ordres.habilitationsExigees(ot)", ot)]

    def test_equipement_et_ot_reunis_avec_leur_origine(self):
        self.assertEqual(self.exigees("OT-2026-0001"), [])
        self.assertEqual(self.exigees("OT-2026-0002"), [("BR", ["equipement"])])
        self.assertEqual(self.exigees("OT-2026-0003"), [("BR", ["equipement"]), ("H0V", ["ot"])])
        self.assertEqual(self.exigees("OT-2026-0005"), [("CACES R489", ["ot"])])
        self.assertEqual(self.exigees("OT-2026-0006"), [("BR", ["ot"])])      # équipement introuvable
        self.assertEqual(self.exigees("OT-2026-0007"), [])                    # séparateurs seuls

    def test_separateurs_casse_et_espaces_ignores_doublons_reunis(self):
        # Équipement « BR, B2V / H0V », OT « b r/ CACES R489 ,, h0v » : la première écriture est gardée.
        self.assertEqual(self.exigees("OT-2026-0004"), [
            ("BR", ["equipement", "ot"]), ("B2V", ["equipement"]), ("H0V", ["equipement", "ot"]),
            ("CACES R489", ["ot"])])

    def test_ligne_ou_identifiant_et_colonnes_lues_sur_leur_ligne(self):
        # Une ligne d'OT en cours de saisie (pas encore écrite) : sa colonne est lue telle quelle, celle de
        # l'équipement sur l'équipement (jamais un Object.assign des deux).
        self.assertEqual(self.js("""() => Ordres.habilitationsExigees({ equipement_id: 'EQ-0004', habilitation_requise: 'BR' })
                                   .map((e) => e.intitule + ':' + e.origines.join('+'))"""),
                         ["CACES R489:equipement", "BR:ot"])
        self.assertEqual(self.js("() => Ordres.habilitationsExigees(null)"), [])
        self.assertEqual(self.js("() => Ordres.habilitationsExigees('OT-2099-9999')"), [])
        self.assertEqual(self.js("() => Ordres.ORIGINES_HABILITATION"), ["equipement", "ot"])


# ---------------------------------------------------------------------------
# §7.2 Le contrôle
# ---------------------------------------------------------------------------

class TestControle(CasRg8):

    def setUp(self):
        super().setUp()
        self.charger(jeu_de_test())

    def test_ot_sans_exigence_jamais_bloque(self):
        # CS180 : ni l'équipement ni l'OT n'exigent rien → aucun technicien n'est bloqué, à aucune date.
        for ot in ("OT-2026-0001", "OT-2026-0007"):
            for technicien in ("TEC-0001", "TEC-0002", "TEC-0004", "TEC-0006", "TEC-9999"):
                for date in (DATE, "2020-01-01", "2040-12-31"):
                    with self.subTest(ot=ot, technicien=technicien, date=date):
                        resultat = self.controle(ot, technicien, date)
                        self.assertEqual(resultat["exigees"], [])
                        self.assertEqual(resultat["manquantes"], [])
                        self.assertFalse(resultat["bloque"])

    def test_echue_avec_sa_date_d_echeance(self):
        resultat = self.controle("OT-2026-0002", "TEC-0004")
        self.assertTrue(resultat["bloque"])
        self.assertEqual(resultat["date"], DATE)
        self.assertEqual(resultat["technicienId"], "TEC-0004")
        self.assertEqual(resultat["manquantes"], [{"intitule": "BR", "origines": ["equipement"], "raison": "echue",
                                                   "echeance": "2026-05-31", "obtention": ""}])
        # Avant l'échéance, la même habilitation était valide.
        self.assertFalse(self.controle("OT-2026-0002", "TEC-0004", "2026-05-31")["bloque"])

    def test_absente(self):
        resultat = self.controle("OT-2026-0003", "TEC-0006")
        self.assertTrue(resultat["bloque"])
        self.assertEqual(resultat["manquantes"], [
            {"intitule": "BR", "origines": ["equipement"], "raison": "absente", "echeance": "", "obtention": ""},
            {"intitule": "H0V", "origines": ["ot"], "raison": "absente", "echeance": "", "obtention": ""}])
        # Technicien inconnu : aucune ligne, donc absente aussi.
        self.assertEqual(self.raisons("OT-2026-0002", "TEC-9999"), [("BR", "absente")])

    def test_pas_encore_obtenue_l_emporte_sur_l_ancienne_ligne_echue(self):
        manquante = self.controle("OT-2026-0002", "TEC-0002")["manquantes"]
        self.assertEqual(manquante, [{"intitule": "BR", "origines": ["equipement"], "raison": "pas_encore_obtenue",
                                      "echeance": "", "obtention": "2026-12-01"}])
        # Le jour de l'obtention, la ligne nouvelle vaut.
        self.assertFalse(self.controle("OT-2026-0002", "TEC-0002", "2026-12-01")["bloque"])

    def test_exigence_de_l_ot_controlee_comme_celle_de_l_equipement(self):
        # OT-2026-0003 : BR (équipement) et H0V (OT). TEC-0004 a H0V valide : seule BR manque.
        self.assertEqual(self.raisons("OT-2026-0003", "TEC-0004"), [("BR", "echue")])
        # OT-2026-0005 : un équipement sans exigence, l'OT exige un CACES R489.
        self.assertEqual(self.raisons("OT-2026-0005", "TEC-0001", DATE), [("CACES R489", "absente")])
        self.assertEqual(self.raisons("OT-2026-0005", "TEC-0003", DATE), [])

    def test_casse_espaces_bornes_vides_et_echeance_illisible(self):
        # TEC-0003 : « caces  r489 » vaut « CACES R489 » ; BR sans échéance et B2V sans obtention valent ;
        # H0V à l'échéance illisible (2026-02-30) est tenue pour échue, sans date.
        self.assertEqual(self.controle("OT-2026-0004", "TEC-0003")["manquantes"], [
            {"intitule": "H0V", "origines": ["equipement", "ot"], "raison": "echue", "echeance": "", "obtention": ""}])
        # En 2040, BR (sans échéance) vaut encore ; en 1990, B2V (sans obtention) vaut déjà ; l'échéance
        # illisible reste échue à toute date.
        self.assertEqual(self.raisons("OT-2026-0004", "TEC-0003", "2040-01-01"),
                         [("B2V", "echue"), ("H0V", "echue"), ("CACES R489", "echue")])
        self.assertEqual(self.raisons("OT-2026-0004", "TEC-0003", "1990-01-01"),
                         [("BR", "pas_encore_obtenue"), ("H0V", "echue"), ("CACES R489", "pas_encore_obtenue")])

    def test_bornes_comprises(self):
        # TEC-0005 : BR obtenue le 20/11/2026, H0V échue après le 20/11/2026 (OT-2026-0003 exige les deux).
        self.assertEqual(self.raisons("OT-2026-0003", "TEC-0005", "2026-11-20"), [])
        self.assertEqual(self.raisons("OT-2026-0003", "TEC-0005", "2026-11-19"), [("BR", "pas_encore_obtenue")])
        self.assertEqual(self.raisons("OT-2026-0003", "TEC-0005", "2026-11-21"), [("H0V", "echue")])

    def test_date_donnee_sinon_date_prevue_sinon_aujourd_hui(self):
        self.assertEqual(self.js("() => Ordres.controleHabilitation('OT-2026-0002', 'TEC-0004').date"), DATE)
        self.assertEqual(self.js("() => Ordres.controleHabilitation('OT-2026-0002', 'TEC-0004', '').date"), DATE)
        self.assertEqual(self.js("() => Ordres.controleHabilitation('OT-2026-0002', 'TEC-0004', '2026-05-01T08:00').date"),
                         "2026-05-01")
        self.assertEqual(self.js("() => Ordres.controleHabilitation('OT-2026-0005', 'TEC-0001').date"),
                         self.js("() => Donnees.aujourdhui()"))

    def test_sans_technicien_rien_a_controler(self):
        for technicien in ("", None):
            with self.subTest(technicien=technicien):
                resultat = self.controle("OT-2026-0002", technicien)
                self.assertEqual([e["intitule"] for e in resultat["exigees"]], ["BR"])
                self.assertEqual(resultat["manquantes"], [])
                self.assertFalse(resultat["bloque"])

    def test_raisons_exposees(self):
        self.assertEqual(self.js("() => Ordres.RAISONS_HABILITATION"), ["absente", "echue", "pas_encore_obtenue"])


# ---------------------------------------------------------------------------
# Ordres.verifierHabilitation réécrite au-dessus du contrôle : même message ; verifierPassage inchangé
# ---------------------------------------------------------------------------

class TestVerifierHabilitation(CasRg8):

    def setUp(self):
        super().setUp()
        self.charger(jeu_de_test())

    def test_meme_message_qu_avant(self):
        self.assertEqual(self.js("() => Ordres.verifierHabilitation('EQ-0002', 'TEC-0004', '2026-11-20')"),
                         "TEC-0004 sans BR valide au 2026-11-20")
        self.assertEqual(self.js("() => Ordres.verifierHabilitation(Donnees.trouver('equipements', 'EQ-0003'), 'TEC-0006', '2026-11-20', true)"),
                         "TEC-0006 sans BR, B2V, H0V valide au 2026-11-20")
        self.assertIsNone(self.js("() => Ordres.verifierHabilitation('EQ-0002', 'TEC-0004', '2026-05-01')"))
        self.assertIsNone(self.js("() => Ordres.verifierHabilitation('EQ-0002', 'TEC-0001', '2026-11-20')"))
        self.assertIsNone(self.js("() => Ordres.verifierHabilitation('EQ-0001', 'TEC-0006', '2026-11-20')"))
        self.assertIsNone(self.js("() => Ordres.verifierHabilitation('EQ-0002', '', '2026-11-20')"))
        self.assertIsNone(self.js("() => Ordres.verifierHabilitation('EQ-9999', 'TEC-0004', '2026-11-20')"))
        # Casse et espaces ignorés comme à l'écran Équipe (Q11) : « caces  r489 » vaut « CACES R489 ».
        self.assertIsNone(self.js("() => Ordres.verifierHabilitation('EQ-0004', 'TEC-0003', '2026-11-20')"))
        self.assertEqual(self.js("() => Ordres.interne.habilitationsManquantes(Donnees.trouver('equipements', 'EQ-0003'), 'TEC-0003', '2026-11-20')"),
                         ["H0V"])

    def test_verifier_passage_garde_l_avertissement(self):
        # Ici RG8 reste un avertissement de « Planifié » : le blocage est T437.
        passage = self.js("() => Ordres.verifierPassage(Donnees.trouver('ordres_travail', 'OT-2026-0002'), 'Planifié')")
        self.assertTrue(passage["ok"], passage["erreurs"])
        self.assertEqual(len(passage["avertissements"]), 1)
        self.assertIn("TEC-0004 sans BR valide au 2026-11-20", passage["avertissements"][0])


# ---------------------------------------------------------------------------
# §7.4, §7.5 Marqueur de dérogation et dérogation déjà notée
# ---------------------------------------------------------------------------

class TestDerogation(CasRg8):

    def setUp(self):
        super().setUp()
        self.charger(jeu_de_test())

    def test_marqueur_ecrit_puis_relu(self):
        manquantes = [{"intitule": "BR", "raison": "echue", "echeance": "2026-05-31"},
                      {"intitule": "H0V", "raison": "absente"},
                      {"intitule": "CACES R489 (cat. 3)", "raison": "pas_encore_obtenue"}]
        texte = self.js("(m) => Ordres.marqueurDerogation('TEC-0004', '2026-11-20', m, '  Électricien présent,\\n consigné  ')",
                        manquantes)
        self.assertEqual(texte, "dérogation habilitation : TEC-0004 le 2026-11-20 sans BR (échue), H0V (absente), "
                                "CACES R489 (cat. 3) (pas encore obtenue) ; motif : Électricien présent, consigné")
        relu = self.js("(t) => Ordres.lireDerogation('modification : technicien_id — préparation ; ' + t)", texte)
        self.assertEqual(relu, {"technicienId": "TEC-0004", "date": "2026-11-20", "motif": "Électricien présent, consigné",
                                "manquantes": [{"intitule": "BR", "raison": "echue"},
                                               {"intitule": "H0V", "raison": "absente"},
                                               {"intitule": "CACES R489 (cat. 3)", "raison": "pas_encore_obtenue"}]})

    def test_marqueur_du_controle_et_motif_contenant_un_point_virgule(self):
        relu = self.js("""() => {
          const controle = Ordres.controleHabilitation('OT-2026-0003', 'TEC-0006');
          const action = Ordres.marqueurDerogation(controle.technicienId, controle.date, controle.manquantes,
            'Seul électricien ; habilitation en cours de renouvellement');
          return [action, Ordres.lireDerogation(action)];
        }""")
        self.assertEqual(relu[0], "dérogation habilitation : TEC-0006 le 2026-11-20 sans BR (absente), H0V (absente)"
                                  " ; motif : Seul électricien ; habilitation en cours de renouvellement")
        self.assertEqual(relu[1]["manquantes"], [{"intitule": "BR", "raison": "absente"},
                                                 {"intitule": "H0V", "raison": "absente"}])
        self.assertEqual(relu[1]["motif"], "Seul électricien ; habilitation en cours de renouvellement")

    def test_motif_obligatoire_et_marqueur_incomplet(self):
        # Q7 : pas de dérogation sans motif ; ni sans technicien, date ou habilitation manquante.
        for appel in ("Ordres.marqueurDerogation('TEC-0004', '2026-11-20', [{ intitule: 'BR', raison: 'echue' }], '')",
                      "Ordres.marqueurDerogation('TEC-0004', '2026-11-20', [{ intitule: 'BR', raison: 'echue' }], '  \\n ')",
                      "Ordres.marqueurDerogation('', '2026-11-20', [{ intitule: 'BR', raison: 'echue' }], 'motif')",
                      "Ordres.marqueurDerogation('TEC-0004', '', [{ intitule: 'BR', raison: 'echue' }], 'motif')",
                      "Ordres.marqueurDerogation('TEC-0004', '2026-11-20', [], 'motif')"):
            with self.subTest(appel=appel):
                self.assertEqual(self.js("() => " + appel), "")
        # Des intitulés seuls : le marqueur ne dit pas de raison, la relecture rend une raison vide.
        texte = self.js("() => Ordres.marqueurDerogation('TEC-0004', '2026-11-20', ['BR'], 'motif')")
        self.assertEqual(texte, "dérogation habilitation : TEC-0004 le 2026-11-20 sans BR ; motif : motif")
        self.assertEqual(self.js("(t) => Ordres.lireDerogation(t).manquantes", texte), [{"intitule": "BR", "raison": ""}])

    def test_lecture_d_une_action_sans_marqueur(self):
        for action in ("", "création", "avertissement habilitation : TEC-0004 sans BR valide au 2026-11-20",
                       "dérogation habilitation : TEC-0004 le 2026-11-20 sans BR (échue) ; motif : ",
                       "dérogation habilitation : TEC-0004 le 20/11/2026 sans BR (échue) ; motif : urgent"):
            with self.subTest(action=action):
                self.assertIsNone(self.js("(a) => Ordres.lireDerogation(a)", action))
        self.assertIsNone(self.js("() => Ordres.lireDerogation(null)"))

    def accordee(self, ot, technicien, date, manquantes):
        entree = self.js("([ot, t, d, m]) => Ordres.derogationAccordee(ot, t, d, m)", [ot, technicien, date, manquantes])
        return entree and entree["id"]

    def test_derogation_accordee_meme_ot_technicien_date_habilitations(self):
        br = [{"intitule": "BR", "raison": "echue"}]
        # Deux entrées valent (J-…AAAA et J-…HHHH, « b r » = « BR ») : la plus récente est rendue.
        self.assertEqual(self.accordee("OT-2026-0003", "TEC-0004", DATE, br), "J-20261109120000-HHHH")
        self.assertEqual(self.accordee("OT-2026-0003", "TEC-0004", DATE, ["br"]), "J-20261109120000-HHHH")
        self.assertEqual(self.accordee("OT-2026-0003", "TEC-0002", DATE, br), "J-20261109090000-BBBB")
        self.assertEqual(self.accordee("OT-2026-0003", "TEC-0004", "2026-11-21", br), "J-20261109093000-CCCC")
        self.assertEqual(self.accordee("OT-2026-0002", "TEC-0004", DATE, br), "J-20261109100000-DDDD")
        self.assertEqual(self.accordee("OT-2026-0003", "TEC-0004", DATE,
                                       [{"intitule": "H0V"}, {"intitule": "BR"}]), "J-20261109110000-EEEE")

    def test_changer_de_technicien_de_date_ou_d_habilitations_redemande(self):
        br = [{"intitule": "BR", "raison": "echue"}]
        self.assertIsNone(self.accordee("OT-2026-0003", "TEC-0006", DATE, br))          # autre technicien
        self.assertIsNone(self.accordee("OT-2026-0003", "TEC-0004", "2026-11-22", br))  # autre date
        self.assertIsNone(self.accordee("OT-2026-0003", "TEC-0004", DATE, [{"intitule": "H0V"}]))
        self.assertIsNone(self.accordee("OT-2026-0003", "TEC-0004", DATE,
                                        [{"intitule": "BR"}, {"intitule": "B2V"}]))     # plus d'habilitations
        self.assertIsNone(self.accordee("OT-2026-0001", "TEC-0004", DATE, br))          # autre OT
        self.assertIsNone(self.accordee("OT-2026-0003", "TEC-0004", DATE, []))
        self.assertIsNone(self.accordee("", "TEC-0004", DATE, br))
        # Ni l'entrée d'une autre table, ni le marqueur sans motif, ni l'ancien avertissement ne comptent : un
        # journal fait de ces seules entrées ne donne aucune dérogation.
        tables = jeu_de_test()
        tables["journal"] = csv(ENTETE_JOURNAL, [ligne for ligne in JOURNAL_LIGNES if ligne[0] in (
            "J-20261109113000-FFFF", "J-20261109114500-GGGG", "J-20261109130000-IIII")])
        self.charger(tables)
        self.assertEqual(self.js("() => Donnees.lignes('journal').length"), 3)
        self.assertIsNone(self.accordee("OT-2026-0003", "TEC-0004", DATE, br))

    def test_le_controle_et_la_derogation_s_enchainent(self):
        # Ce que fera l'écriture (T437) : contrôle, puis dérogation déjà notée pour ces manquantes ?
        entree = self.js("""() => {
          const controle = Ordres.controleHabilitation('OT-2026-0003', 'TEC-0004');
          return controle.bloque && Ordres.derogationAccordee('OT-2026-0003', 'TEC-0004', controle.date, controle.manquantes);
        }""")
        self.assertEqual(entree["id"], "J-20261109120000-HHHH")
        self.assertEqual(entree["profil"], "Responsable test")
        self.assertEqual(entree["date_heure"], "2026-11-09 12:00")


# ---------------------------------------------------------------------------
# Jeu de démo : l'armoire AE-03 et le technicien à BR échue
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


class TestDemo(CasRg8):
    """RG8 sur le jeu de démo brut (sans décalage), à la date de référence du générateur."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reference = date_reference()
        cls.scenarios = scenarios_demo()
        cls.tables = {fichier.stem: fichier.read_bytes().decode("utf-8-sig") for fichier in DOSSIER_DEMO.glob("*.csv")}

    def setUp(self):
        super().setUp()
        self.charger(self.tables)

    def ot_de_l_equipement_br(self):
        return self.js("(eq) => Donnees.lignes('ordres_travail').find((ot) => ot.equipement_id === eq).id",
                       self.scenarios["equipement_br"])

    def test_ae03_et_le_technicien_a_br_echue(self):
        equipement = next(e for e in lire_demo("equipements") if e["id"] == self.scenarios["equipement_br"])
        self.assertEqual(brut(equipement["repere"]), "AE-03")
        technicien = self.scenarios["technicien_br_echue"]
        echeances = sorted(brut(h["date_echeance"]) for h in lire_demo("habilitations")
                           if h["technicien_id"] == technicien and brut(h["intitule"]).upper() == "BR")
        self.assertTrue(echeances and echeances[-1] < self.reference)
        ot = self.ot_de_l_equipement_br()
        resultat = self.controle(ot, technicien, self.reference)
        self.assertTrue(resultat["bloque"])
        self.assertIn(("BR", ["equipement"]), [(e["intitule"], e["origines"]) for e in resultat["exigees"]])
        self.assertEqual([(m["intitule"], m["raison"], m["echeance"]) for m in resultat["manquantes"]],
                         [("BR", "echue", echeances[-1])])
        self.assertFalse(self.controle(ot, self.scenarios["technicien_br_valide"], self.reference)["bloque"])
        # Même message qu'au lot 1 (test_ordres) pour l'exigence de l'équipement.
        self.assertEqual(self.js("([eq, t]) => Ordres.verifierHabilitation(eq, t, '2026-10-21')",
                                 [self.scenarios["equipement_br"], technicien]),
                         "%s sans BR valide au 2026-10-21" % technicien)

    def test_ot_de_demo_sans_exigence_jamais_bloque(self):
        resultat = self.js("""([technicien, jour]) => {
          const sans = Donnees.lignes('ordres_travail').filter((ot) => !Ordres.habilitationsExigees(ot).length);
          return [sans.length, sans.filter((ot) => Ordres.controleHabilitation(ot, technicien, jour).bloque).length,
            sans.filter((ot) => Ordres.controleHabilitation(ot, 'TEC-9999', jour).bloque).length];
        }""", [self.scenarios["technicien_br_echue"], self.reference])
        self.assertGreater(resultat[0], 0)
        self.assertEqual(resultat[1:], [0, 0])


if __name__ == "__main__":
    unittest.main()
