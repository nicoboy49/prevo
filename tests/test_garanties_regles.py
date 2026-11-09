"""Tests des règles pures des garanties et des contrats de prestataires (garanties-regles.js, T451 ; CS173, D187, D190).

Jeu écrit à la main dans ce fichier (aucune donnée réelle), date passée en argument. Règles : conception L4 §2.2 et
§2.6, QUESTIONS L4-L6 Q1 (alerte avant la fin sans reconduction tacite) et Q3 (période reconduite calculée avec
reconduction_mois, rien d'écrit) ; T463 (décision de l'orchestrateur, remplace Q1 pour ces contrats) : sans
reconduction tacite, dont un contrat dont la résiliation est notée, jamais « à décider » ni « préavis dépassé »,
seulement « se termine bientôt » avant la fin ; la résiliation notée se lit au journal (Garanties.resiliationNotee).

Lancer depuis la racine du projet (navigateur : au travers du verrou) :
    py -X utf8 -m unittest discover -s tests -p "test_garanties_regles.py" -v
"""
import unittest

from commun import CasNavigateur, charger_scripts

SCRIPTS = [
    "js/lib/papaparse.min.js",
    "js/schema.js",
    "js/donnees.js",
    "js/stockage-demo.js",
    "js/interface.js",
    "js/modules/controles-regles.js",
    "js/modules/garanties-regles.js",
]


def csv(entete, lignes):
    return "\r\n".join([entete] + list(lignes)) + "\r\n"


EQUIPEMENTS = csv("id;repere;designation;statut;actif", [
    "EQ-0001;CP-01;Compresseur à vis;en service;1",
    "EQ-0002;PR-02;Presse hydraulique;en service;1",
    "EQ-0003;TO-03;Tour ancien;rebut;1",
    "EQ-0004;PE-04;Perceuse retirée;en service;0",
])

FOURNISSEURS = csv("id;nom;contact;telephone;email", [
    "FOU-0001;Hydraulique Services;M. Roux;04 65 71 00 99;contact@hydraulique.test",
    "FOU-0002;Air Maintenance;;;",
])

GARANTIES = csv("id;equipement_id;fournisseur_id;date_debut;date_fin;conditions;document;actif", [
    "GAR-0001;EQ-0001;FOU-0001;2025-06-01;2027-05-31;Pièces et main-d'œuvre;;1",
    "GAR-0002;EQ-0001;;2024-01-01;2026-09-30;Pièces seules;;1",
    "GAR-0003;EQ-0002;;2027-01-01;2029-01-01;;;1",
    "GAR-0004;EQ-0002;FOU-0001;2020-01-01;2025-01-01;;;1",
    "GAR-0005;EQ-0003;;2024-01-01;2026-09-30;;;1",
    "GAR-0006;EQ-0002;;;2026-02-30;;;1",
    "GAR-0007;EQ-0002;;2024-01-01;2026-09-30;;;0",
])

CONTRATS = csv("id;fournisseur_id;objet;equipement_ids;perimetre;date_debut;date_fin;preavis_mois;reconduction_tacite;"
               "reconduction_mois;montant_annuel;document;actif", [
    # CS173 : fin 31/12/2026, préavis 3 mois, reconduction tacite
    "CTP-0001;FOU-0002;Maintenance des compresseurs;EQ-0001;;2026-01-01;2026-12-31;3;1;12;4800;;1",
    # sans reconduction tacite, préavis vide, sans montant
    "CTP-0002;FOU-0002;Nettoyage;;Bâtiment B;2026-01-01;2026-12-31;;0;;;;1",
    # reconduit tacitement, fin passée, durée d'une reconduction inconnue
    "CTP-0003;FOU-0001;Vérification des presses;EQ-0002;;2025-01-01;2025-12-31;3;1;;1200,50;;1",
    # reconduit tacitement, fin passée, durée d'une reconduction connue (période calculée)
    "CTP-0004;FOU-0001;Thermographie;;;2025-01-01;2025-12-31;3;1;12;1350;;1",
    # terminé
    "CTP-0005;FOU-0002;Ancien contrat;;;2024-07-01;2025-06-30;1;0;;1000;;1",
    # fin illisible
    "CTP-0006;FOU-0002;Fin illisible;;;;2026-02-30;3;1;12;500;;1",
    # retiré
    "CTP-0007;FOU-0002;Contrat retiré;EQ-0001;;2026-01-01;2026-08-31;3;1;12;9999;;0",
    # équipements séparés de plusieurs façons, doublon
    "CTP-0008;FOU-0001;Graissage;\"EQ-0002, EQ-0001 ; EQ-0002\";;;2027-03-31;;0;;;;1",
    # sans reconduction tacite, préavis 3 mois
    "CTP-0009;FOU-0001;Dépannage;;;2026-01-01;2026-12-31;3;0;;2000;;1",
])

# Journal des contrats (T463) : CTP-0010 à CTP-0012 ne sont pas dans la table (la règle reçoit la ligne en argument).
JOURNAL = csv("id;date_heure;poste;profil;table;id_ligne;action", [
    "J-0001;2026-01-05 08:00;Poste test;Responsable test;contrats_prestataires;CTP-0010;création — contrat enregistré",
    "J-0002;2026-07-30 10:15;Poste test;Responsable test;contrats_prestataires;CTP-0010;\"modification : "
    "reconduction_tacite — résiliation notée : lettre du 29/07/2026 ; Lettre recommandée\"",
    # résiliation notée, puis une nouvelle période saisie : elle n'est plus résiliée
    "J-0003;2026-03-01 09:00;Poste test;Responsable test;contrats_prestataires;CTP-0011;modification : "
    "reconduction_tacite — résiliation notée : lettre du 01/03/2026",
    "J-0004;2026-04-01 09:00;Poste test;Responsable test;contrats_prestataires;CTP-0011;modification : "
    "date_debut, date_fin — modification du contrat",
    # deux lettres (la seconde sur un contrat déjà sans reconduction tacite), puis le montant modifié
    "J-0005;2026-09-10 09:00;Poste test;Responsable test;contrats_prestataires;CTP-0012;modification : "
    "reconduction_tacite — résiliation notée : lettre du 09/09/2026",
    "J-0006;2026-09-16 14:00;Poste test;Responsable test;contrats_prestataires;CTP-0012;\"résiliation notée : "
    "lettre du 15/09/2026 ; seconde lettre\"",
    "J-0007;2026-09-20 09:00;Poste test;Responsable test;contrats_prestataires;CTP-0012;modification : "
    "montant_annuel — modification du contrat",
    # CTP-0001 se reconduit tacitement (la résiliation a été annulée par « Modifier ») ; une garantie au même numéro
    "J-0008;2026-08-02 09:00;Poste test;Responsable test;contrats_prestataires;CTP-0001;résiliation notée : "
    "lettre du 01/08/2026",
    "J-0009;2026-08-02 09:00;Poste test;Responsable test;garanties;CTP-0002;résiliation notée : lettre du 01/08/2026",
])


class CasGaranties(CasNavigateur):
    PARAMETRES = None

    def setUp(self):
        super().setUp()
        charger_scripts(self.page, SCRIPTS)
        tables = {"equipements": EQUIPEMENTS, "fournisseurs": FOURNISSEURS, "garanties": GARANTIES,
                  "contrats_prestataires": CONTRATS, "journal": JOURNAL}
        if self.PARAMETRES is not None:
            tables["parametres"] = csv("cle;valeur", self.PARAMETRES)
        self.page.evaluate("""async (tables) => {
          Donnees.initialiser(StockageDemo.creer(tables), { poste: 'Poste test', profil: 'Responsable test' });
          await Donnees.chargerTout();
        }""", tables)

    def js(self, script, argument=None):
        return self.page.evaluate(script, argument)

    def etat_contrat(self, contrat_id, jour, delai=None):
        return self.js("([id, jour, delai]) => Garanties.etatContrat(Donnees.trouver('contrats_prestataires', id), "
                       "jour, delai === null ? undefined : delai)", [contrat_id, jour, delai])

    def etat_garantie(self, valeurs, jour, delai=None):
        return self.js("([g, jour, delai]) => Garanties.etatGarantie(g, jour, delai === null ? undefined : delai)",
                       [valeurs, jour, delai])


class TestCS173(CasGaranties):
    """CS173 : fin 31/12/2026, préavis 3 mois → date limite 30/09/2026 ; à l'accueil à partir du 01/08 (60 jours)."""

    def test_cs173_date_limite_30_09(self):
        self.assertEqual(self.js("() => Garanties.dateLimiteResiliation(Donnees.trouver('contrats_prestataires', "
                                 "'CTP-0001'))"), "2026-09-30")

    def test_cs173_a_decider_du_01_08_au_30_09(self):
        for jour in ("2026-08-01", "2026-09-01", "2026-09-30"):
            with self.subTest(jour=jour):
                etat = self.etat_contrat("CTP-0001", jour, 60)
                self.assertEqual(etat["statut"], "a_decider")
                self.assertTrue(etat["alerte"])
                self.assertEqual(etat["dateLimite"], "2026-09-30")
        self.assertEqual(self.etat_contrat("CTP-0001", "2026-08-01", 60)["joursAvantLimite"], 60)
        self.assertEqual(self.etat_contrat("CTP-0001", "2026-09-30", 60)["joursAvantLimite"], 0)

    def test_cs173_pas_le_31_07(self):
        etat = self.etat_contrat("CTP-0001", "2026-07-31", 60)
        self.assertEqual(etat["statut"], "en_cours")
        self.assertFalse(etat["alerte"])
        self.assertEqual(etat["raison"], "jusqu'au 31/12/2026 (date limite de résiliation le 30/09/2026)")

    def test_cs173_preavis_depasse_le_01_10(self):
        etat = self.etat_contrat("CTP-0001", "2026-10-01", 60)
        self.assertEqual(etat["statut"], "preavis_depasse")
        self.assertFalse(etat["alerte"])
        self.assertEqual(etat["raison"], "date limite de résiliation passée (30/09/2026) : sans résiliation, il est "
                                         "reconduit le 31/12/2026")
        # reconduction tacite : jamais « se termine bientôt », jusqu'à la fin comprise
        self.assertEqual(self.etat_contrat("CTP-0001", "2026-12-31", 60)["statut"], "preavis_depasse")

    def test_cs173_delai_30_a_partir_du_31_08(self):
        self.assertEqual(self.etat_contrat("CTP-0001", "2026-08-30", 30)["statut"], "en_cours")
        self.assertEqual(self.etat_contrat("CTP-0001", "2026-08-31", 30)["statut"], "a_decider")
        self.assertEqual(self.etat_contrat("CTP-0001", "2026-08-01", 30)["statut"], "en_cours")

    def test_cs173_raison_a_decider(self):
        self.assertEqual(self.etat_contrat("CTP-0001", "2026-08-16", 60)["raison"],
                         "à résilier au plus tard le 30/09/2026 (dans 45 jours), sinon il est reconduit le 31/12/2026")
        self.assertEqual(self.etat_contrat("CTP-0001", "2026-09-29", 60)["raison"],
                         "à résilier au plus tard le 30/09/2026 (dans 1 jour), sinon il est reconduit le 31/12/2026")
        self.assertEqual(self.etat_contrat("CTP-0001", "2026-09-30", 60)["raison"],
                         "à résilier au plus tard le 30/09/2026 (aujourd'hui), sinon il est reconduit le 31/12/2026")

    def test_cs173_a_l_accueil_a_partir_du_01_08(self):
        echeances = "(jour) => Garanties.aEcheance(jour).contrats.map((c) => c.id)"
        self.assertNotIn("CTP-0001", self.js(echeances, "2026-07-31"))
        self.assertIn("CTP-0001", self.js(echeances, "2026-08-01"))
        self.assertIn("CTP-0001", self.js(echeances, "2026-09-30"))
        self.assertNotIn("CTP-0001", self.js(echeances, "2026-10-01"))


class TestCS173Reglage(CasGaranties):
    """Le réglage alerte_echeances_jours déplace l'alerte (CS173 : « changer le réglage déplace l'alerte »)."""
    PARAMETRES = ["alerte_echeances_jours;30"]

    def test_cs173_reglage_a_30_deplace_l_alerte(self):
        self.assertEqual(self.js("() => Garanties.delaiAlerte()"), 30)
        self.assertEqual(self.etat_contrat("CTP-0001", "2026-08-30")["statut"], "en_cours")
        self.assertEqual(self.etat_contrat("CTP-0001", "2026-08-31")["statut"], "a_decider")
        echeances = "(jour) => Garanties.aEcheance(jour).contrats.map((c) => c.id)"
        self.assertNotIn("CTP-0001", self.js(echeances, "2026-08-01"))
        self.assertIn("CTP-0001", self.js(echeances, "2026-08-31"))


class TestDelaiAlerte(CasGaranties):

    def test_delai_par_defaut_sans_reglage(self):
        self.assertEqual(self.js("() => Garanties.delaiAlerte()"), 60)
        self.assertEqual(self.js("() => Garanties.PARAMETRE_DELAI"), "alerte_echeances_jours")

    def test_delai_de_1_a_365_sinon_60(self):
        cas = {"": 60, "abc": 60, "0": 60, "-5": 60, "366": 60, "45,5": 60, "365": 365, "1": 1, " 30 ": 30,
               "30,0": 30}
        for valeur, attendu in cas.items():
            with self.subTest(valeur=valeur):
                self.assertEqual(self.js("(v) => Garanties.delaiAlerte(v)", valeur), attendu)
        self.assertEqual(self.js("() => Garanties.delaiAlerte(90)"), 90)


class TestDelaiIllisible(CasGaranties):
    PARAMETRES = ["alerte_echeances_jours;soixante"]

    def test_reglage_illisible_donne_60(self):
        self.assertEqual(self.js("() => Garanties.delaiAlerte()"), 60)
        self.assertEqual(self.etat_contrat("CTP-0001", "2026-08-01")["statut"], "a_decider")


class TestDateLimite(CasGaranties):

    def limite(self, fin, preavis):
        return self.js("([fin, preavis]) => Garanties.dateLimiteResiliation({ date_fin: fin, preavis_mois: preavis })",
                       [fin, preavis])

    def test_fins_de_mois(self):
        self.assertEqual(self.limite("2028-05-31", "3"), "2028-02-29")
        self.assertEqual(self.limite("2027-05-31", "3"), "2027-02-28")
        self.assertEqual(self.limite("2026-12-31", "3"), "2026-09-30")
        self.assertEqual(self.limite("2026-03-31", "1"), "2026-02-28")
        self.assertEqual(self.limite("2027-01-15", "14"), "2025-11-15")

    def test_preavis_vide_zero_ou_illisible_donne_la_fin(self):
        for preavis in ("", "0", "trois", "-2", "1,5"):
            with self.subTest(preavis=preavis):
                self.assertEqual(self.limite("2026-12-31", preavis), "2026-12-31")

    def test_fin_illisible_donne_vide(self):
        for fin in ("", "31/12/2026", "2026-02-30", "fin d'année"):
            with self.subTest(fin=fin):
                self.assertEqual(self.limite(fin, "3"), "")


class TestEtatContrat(CasGaranties):

    def test_preavis_vide_alerte_avant_la_fin(self):
        # sans reconduction tacite, préavis vide : date limite = fin ; « se termine bientôt » avant la fin (T463)
        etat = self.etat_contrat("CTP-0002", "2026-11-01", 60)
        self.assertEqual(etat["statut"], "bientot")
        self.assertTrue(etat["alerte"])
        self.assertEqual(etat["dateLimite"], "2026-12-31")
        self.assertEqual(etat["raison"], "se termine dans 60 jours, le 31/12/2026")
        # préavis connu, sans reconduction tacite : la date limite ne compte pas, la raison dit la fin seulement
        self.assertEqual(self.etat_contrat("CTP-0009", "2026-08-16", 60)["raison"], "jusqu'au 31/12/2026")
        self.assertEqual(self.etat_contrat("CTP-0002", "2026-10-31", 60)["statut"], "en_cours")
        self.assertEqual(self.etat_contrat("CTP-0002", "2026-10-31", 60)["raison"], "jusqu'au 31/12/2026")
        self.assertEqual(self.etat_contrat("CTP-0002", "2027-01-01", 60)["statut"], "termine")

    def test_sans_reconduction_tacite_toutes_les_etapes(self):
        # T463 : sans reconduction tacite, rien à décider : ni « à décider » ni « préavis dépassé » autour de la date
        # limite (30/09/2026) ; « se termine bientôt » dans le délai avant la fin, puis « terminé »
        attendus = [("2026-07-31", "en_cours"), ("2026-08-01", "en_cours"), ("2026-09-30", "en_cours"),
                    ("2026-10-01", "en_cours"), ("2026-10-31", "en_cours"),
                    ("2026-11-01", "bientot"), ("2026-12-31", "bientot"), ("2027-01-01", "termine")]
        for jour, statut in attendus:
            with self.subTest(jour=jour):
                etat = self.etat_contrat("CTP-0009", jour, 60)
                self.assertEqual(etat["statut"], statut)
                self.assertEqual(etat["alerte"], statut == "bientot")
                self.assertEqual(etat["dateLimite"], "2026-09-30")
        self.assertEqual(self.etat_contrat("CTP-0009", "2026-11-01", 60)["raison"],
                         "se termine dans 60 jours, le 31/12/2026")
        self.assertEqual(self.etat_contrat("CTP-0009", "2026-12-31", 60)["raison"],
                         "se termine aujourd'hui, le 31/12/2026")
        self.assertEqual(self.etat_contrat("CTP-0009", "2026-10-15", 60)["raison"], "jusqu'au 31/12/2026")
        self.assertEqual(self.etat_contrat("CTP-0009", "2027-01-01", 60)["raison"], "terminé le 31/12/2026")
        # le délai réglé déplace « se termine bientôt » : 30 jours → à partir du 01/12/2026
        self.assertEqual(self.etat_contrat("CTP-0009", "2026-11-30", 30)["statut"], "en_cours")
        self.assertEqual(self.etat_contrat("CTP-0009", "2026-12-01", 30)["statut"], "bientot")

    def test_fin_illisible(self):
        etat = self.etat_contrat("CTP-0006", "2026-08-01", 60)
        self.assertEqual(etat["statut"], "fin_inconnue")
        self.assertEqual(etat["dateLimite"], "")
        self.assertIsNone(etat["joursAvantFin"])
        self.assertFalse(etat["alerte"])
        self.assertEqual(etat["raison"], "date de fin inconnue : saisissez la fin de la période en cours")
        self.assertEqual(self.js("() => Garanties.etatContrat({}, '2026-08-01').statut"), "fin_inconnue")

    def test_reconduction_tacite_passee_sans_duree(self):
        etat = self.etat_contrat("CTP-0003", "2026-08-01", 60)
        self.assertEqual(etat["statut"], "a_mettre_a_jour")
        self.assertFalse(etat["alerte"])
        self.assertFalse(etat["periodeCalculee"])
        self.assertEqual(etat["fin"], "2025-12-31")
        self.assertEqual(etat["raison"], "reconduit tacitement le 31/12/2025 : saisissez la nouvelle période")
        # le lendemain de la fin, déjà « dates à mettre à jour »
        self.assertEqual(self.etat_contrat("CTP-0003", "2026-01-01", 60)["statut"], "a_mettre_a_jour")
        self.assertEqual(self.etat_contrat("CTP-0003", "2025-12-31", 60)["statut"], "preavis_depasse")

    def test_reconduction_tacite_passee_periode_calculee(self):
        # Q3 : reconduction_mois connu → date limite de la période reconduite calculée pour l'alerte
        etat = self.etat_contrat("CTP-0004", "2026-08-01", 60)
        self.assertEqual(etat["statut"], "a_decider")
        self.assertTrue(etat["alerte"])
        self.assertTrue(etat["periodeCalculee"])
        self.assertEqual(etat["fin"], "2025-12-31")
        self.assertEqual(etat["finPeriode"], "2026-12-31")
        self.assertEqual(etat["dateLimite"], "2026-09-30")
        self.assertEqual(etat["raison"], "reconduit tacitement le 31/12/2025 ; période calculée : à résilier au plus "
                                         "tard le 30/09/2026 (dans 60 jours) ; saisissez la nouvelle période")
        # hors de la fenêtre d'alerte : « dates à mettre à jour »
        self.assertEqual(self.etat_contrat("CTP-0004", "2026-03-01", 60)["statut"], "a_mettre_a_jour")
        self.assertEqual(self.etat_contrat("CTP-0004", "2026-10-01", 60)["statut"], "a_mettre_a_jour")
        # deux reconductions plus tard
        etat = self.etat_contrat("CTP-0004", "2027-08-15", 60)
        self.assertEqual((etat["statut"], etat["finPeriode"], etat["dateLimite"]),
                         ("a_decider", "2027-12-31", "2027-09-30"))
        # rien n'est écrit
        self.assertEqual(self.js("() => Donnees.trouver('contrats_prestataires', 'CTP-0004').date_fin"), "2025-12-31")

    def test_periode_calculee_fins_de_mois(self):
        calcul = ("([fin, mois, jour]) => Garanties.etatContrat({ date_fin: fin, preavis_mois: '0', "
                  "reconduction_tacite: '1', reconduction_mois: mois }, jour, 60).finPeriode")
        self.assertEqual(self.js(calcul, ["2026-09-30", "3", "2026-10-15"]), "2026-12-31")
        self.assertEqual(self.js(calcul, ["2027-02-28", "12", "2027-03-01"]), "2028-02-29")
        self.assertEqual(self.js(calcul, ["2026-06-15", "1", "2026-09-20"]), "2026-10-15")

    def test_libelles_des_statuts(self):
        attendus = {"fin_inconnue": "fin inconnue", "a_venir": "à venir", "terminee": "terminée",
                    "bientot": "se termine bientôt", "en_cours": "en cours", "a_decider": "à décider",
                    "a_mettre_a_jour": "dates à mettre à jour", "preavis_depasse": "préavis dépassé",
                    "termine": "terminé"}
        for statut, libelle in attendus.items():
            with self.subTest(statut=statut):
                self.assertEqual(self.js("(s) => Garanties.libelleStatut(s)", statut), libelle)
        self.assertEqual(self.js("() => Garanties.libelleStatut('autre')"), "autre")
        self.assertEqual(self.js("() => Garanties.STATUTS_CONTRAT"),
                         ["fin_inconnue", "a_decider", "a_mettre_a_jour", "bientot", "preavis_depasse", "termine",
                          "en_cours"])
        self.assertEqual(self.js("() => Garanties.STATUTS_GARANTIE"),
                         ["fin_inconnue", "a_venir", "terminee", "bientot", "en_cours"])


class TestResiliationNotee(CasGaranties):
    """T463 (signalé par la recette T461) : « Noter la résiliation » met reconduction_tacite à 0 ; la décision est
    prise, le contrat n'est plus jamais « à décider » ; la fiche dit « résiliation notée le … » (journal)."""

    # Le contrat de CS173 après « Noter la résiliation » (lettre du 29/07/2026, journal J-0002).
    RESILIE = {"id": "CTP-0010", "fournisseur_id": "FOU-0002", "objet": "Maintenance résiliée",
               "date_debut": "2026-01-01", "date_fin": "2026-12-31", "preavis_mois": "3", "reconduction_tacite": "0",
               "reconduction_mois": "12", "montant_annuel": "4800", "actif": "1"}

    def etat(self, contrat, jour, delai=60):
        return self.js("([c, jour, delai]) => Garanties.etatContrat(c, jour, delai)", [contrat, jour, delai])

    def notee(self, contrat):
        return self.js("(c) => Garanties.resiliationNotee(c)", contrat)

    def test_resilie_jamais_a_decider_se_termine_bientot_avant_la_fin(self):
        attendus = [("2026-07-31", "en_cours"), ("2026-08-01", "en_cours"), ("2026-09-30", "en_cours"),
                    ("2026-10-01", "en_cours"), ("2026-10-31", "en_cours"), ("2026-11-01", "bientot"),
                    ("2026-12-31", "bientot"), ("2027-01-01", "termine")]
        for jour, statut in attendus:
            with self.subTest(jour=jour):
                self.assertEqual(self.etat(self.RESILIE, jour)["statut"], statut)
        etat = self.etat(self.RESILIE, "2026-08-16")
        self.assertEqual((etat["raison"], etat["alerte"], etat["dateLimite"]), ("jusqu'au 31/12/2026", False, "2026-09-30"))
        etat = self.etat(self.RESILIE, "2026-11-16")
        self.assertEqual((etat["raison"], etat["alerte"]), ("se termine dans 45 jours, le 31/12/2026", True))
        # La même ligne avec reconduction tacite : CS173 inchangé (à décider du 01/08 au 30/09, puis préavis dépassé)
        tacite = dict(self.RESILIE, reconduction_tacite="1")
        for jour, statut in (("2026-07-31", "en_cours"), ("2026-08-01", "a_decider"), ("2026-09-30", "a_decider"),
                             ("2026-10-01", "preavis_depasse"), ("2026-12-31", "preavis_depasse")):
            with self.subTest(tacite=jour):
                self.assertEqual(self.etat(tacite, jour)["statut"], statut)

    def test_resilie_compte_au_total_jusqu_a_sa_fin(self):
        total = "([c, jour]) => Garanties.totalMontants([c], jour)"
        self.assertEqual(self.js(total, [self.RESILIE, "2026-08-01"]), {"centimes": 480000, "sansMontant": 0})
        self.assertEqual(self.js(total, [self.RESILIE, "2026-12-31"]), {"centimes": 480000, "sansMontant": 0})
        self.assertEqual(self.js(total, [self.RESILIE, "2027-01-01"]), {"centimes": 0, "sansMontant": 0})

    def test_resiliation_notee_lue_au_journal(self):
        self.assertEqual(self.notee(self.RESILIE), {"notee": "2026-07-30", "lettre": "2026-07-29"})
        # deux lettres : la plus récente ; une modification qui ne touche pas la fin ne l'efface pas
        self.assertEqual(self.notee(dict(self.RESILIE, id="CTP-0012")), {"notee": "2026-09-16", "lettre": "2026-09-15"})
        # nouvelle période saisie après la lettre : elle n'est pas résiliée
        self.assertIsNone(self.notee(dict(self.RESILIE, id="CTP-0011")))
        # reconduction tacite (résiliation annulée par « Modifier ») : rien, même si le journal porte une lettre
        self.assertIsNone(self.notee(dict(self.RESILIE, reconduction_tacite="1")))
        self.assertIsNone(self.js("() => Garanties.resiliationNotee(Donnees.trouver('contrats_prestataires', 'CTP-0001'))"))
        # aucune entrée pour ce contrat (celle de J-0009 est d'une autre table) ; ligne sans identifiant
        self.assertIsNone(self.js("() => Garanties.resiliationNotee(Donnees.trouver('contrats_prestataires', 'CTP-0002'))"))
        self.assertIsNone(self.notee({}))
        self.assertIsNone(self.js("() => Garanties.resiliationNotee(null)"))


class TestGaranties(CasGaranties):

    def test_bornes_de_garantie_incluses(self):
        garantie = {"date_debut": "2026-08-01", "date_fin": "2026-12-31"}
        self.assertEqual(self.etat_garantie(garantie, "2026-07-31")["statut"], "a_venir")
        self.assertEqual(self.etat_garantie(garantie, "2026-08-01")["statut"], "en_cours")
        etat = self.etat_garantie(garantie, "2026-12-31")
        self.assertEqual((etat["statut"], etat["joursRestants"], etat["alerte"]), ("bientot", 0, True))
        self.assertEqual(etat["raison"], "se termine aujourd'hui, le 31/12/2026")
        etat = self.etat_garantie(garantie, "2027-01-01")
        self.assertEqual((etat["statut"], etat["alerte"], etat["raison"]), ("terminee", False, "terminée le 31/12/2026"))
        # sous garantie le jour du début et le jour de la fin
        self.assertIsNotNone(self.js("() => Garanties.sousGarantie('EQ-0001', '2027-05-31')"))
        self.assertIsNone(self.js("() => Garanties.sousGarantie('EQ-0001', '2027-06-01')"))
        self.assertIsNone(self.js("() => Garanties.sousGarantie('EQ-0002', '2026-12-31')"))
        self.assertEqual(self.js("() => Garanties.sousGarantie('EQ-0002', '2027-01-01').garantie.id"), "GAR-0003")

    def test_delai_de_la_garantie(self):
        garantie = {"date_debut": "", "date_fin": "2026-12-31"}
        self.assertEqual(self.etat_garantie(garantie, "2026-11-01", 60)["statut"], "bientot")
        self.assertEqual(self.etat_garantie(garantie, "2026-10-31", 60)["statut"], "en_cours")
        self.assertEqual(self.etat_garantie(garantie, "2026-10-31", 60)["raison"], "jusqu'au 31/12/2026")
        self.assertEqual(self.etat_garantie(garantie, "2026-12-01", 30)["statut"], "bientot")
        self.assertEqual(self.etat_garantie(garantie, "2026-11-30", 30)["statut"], "en_cours")
        self.assertEqual(self.etat_garantie(garantie, "2026-11-16", 60)["raison"], "se termine dans 45 jours, le 31/12/2026")

    def test_fin_inconnue_et_a_venir(self):
        for fin in ("", "2026-02-30", "31/12/2026"):
            with self.subTest(fin=fin):
                etat = self.etat_garantie({"date_debut": "2026-01-01", "date_fin": fin}, "2026-08-01")
                self.assertEqual((etat["statut"], etat["fin"], etat["joursRestants"]), ("fin_inconnue", "", None))
        etat = self.etat_garantie({"date_debut": "2027-01-01", "date_fin": "2029-01-01"}, "2026-08-01")
        self.assertEqual((etat["statut"], etat["raison"]), ("a_venir", "commence le 01/01/2027"))
        # début illisible : compté comme vide (déjà commencée)
        self.assertEqual(self.etat_garantie({"date_debut": "bientôt", "date_fin": "2029-01-01"}, "2026-08-01")["statut"],
                         "en_cours")

    def test_sous_garantie_la_fin_la_plus_lointaine(self):
        sous = self.js("() => { const s = Garanties.sousGarantie('EQ-0001', '2026-08-01'); "
                       "return { id: s.garantie.id, fin: s.fin, fournisseur: s.fournisseur && s.fournisseur.nom }; }")
        self.assertEqual(sous, {"id": "GAR-0001", "fin": "2027-05-31", "fournisseur": "Hydraulique Services"})
        # fournisseur vide : null
        sous = self.js("() => Garanties.sousGarantie('EQ-0002', '2027-06-01')")
        self.assertEqual(sous["garantie"]["id"], "GAR-0003")
        self.assertIsNone(sous["fournisseur"])
        # garantie retirée (GAR-0007) jamais comptée
        self.assertIsNone(self.js("() => Garanties.sousGarantie('EQ-0002', '2026-08-01')"))
        self.assertIsNone(self.js("() => Garanties.sousGarantie('', '2026-08-01')"))
        self.assertIsNone(self.js("() => Garanties.sousGarantie('EQ-0099', '2026-08-01')"))

    def test_garanties_de_l_equipement(self):
        self.assertEqual(self.js("() => Garanties.garantiesDeLEquipement('EQ-0002').map((g) => g.id)"),
                         ["GAR-0003", "GAR-0004", "GAR-0006"])
        self.assertEqual(self.js("() => Garanties.garantiesDeLEquipement('EQ-0001').map((g) => g.id)"),
                         ["GAR-0001", "GAR-0002"])
        self.assertEqual(self.js("() => Garanties.garantiesDeLEquipement('EQ-0099')"), [])


class TestContrats(CasGaranties):

    def test_equipements_du_contrat(self):
        self.assertEqual(self.js("() => Garanties.equipementsDuContrat(Donnees.trouver('contrats_prestataires', "
                                 "'CTP-0008'))"), ["EQ-0002", "EQ-0001"])
        self.assertEqual(self.js("() => Garanties.equipementsDuContrat({ equipement_ids: 'EQ-0001;EQ-0004' })"),
                         ["EQ-0001", "EQ-0004"])
        self.assertEqual(self.js("() => Garanties.equipementsDuContrat({ equipement_ids: '' })"), [])
        self.assertEqual(self.js("() => Garanties.equipementsDuContrat({})"), [])

    def test_contrats_de_l_equipement(self):
        # CTP-0007 (retiré) cite EQ-0001 : absent
        self.assertEqual(self.js("() => Garanties.contratsDeLEquipement('EQ-0001').map((c) => c.id)"),
                         ["CTP-0001", "CTP-0008"])
        self.assertEqual(self.js("() => Garanties.contratsDeLEquipement('EQ-0002').map((c) => c.id)"),
                         ["CTP-0003", "CTP-0008"])
        self.assertEqual(self.js("() => Garanties.contratsDeLEquipement('EQ-0003')"), [])

    def test_proposition_de_reconduction(self):
        proposer = "(c) => Garanties.propositionReconduction(c)"
        self.assertEqual(self.js("() => Garanties.propositionReconduction(Donnees.trouver('contrats_prestataires', "
                                 "'CTP-0001'))"), {"date_debut": "2027-01-01", "date_fin": "2027-12-31", "mois": 12})
        # sans durée d'une reconduction : la durée de la période en mois entiers
        self.assertEqual(self.js(proposer, {"date_debut": "2026-01-01", "date_fin": "2026-06-30"}),
                         {"date_debut": "2026-07-01", "date_fin": "2026-12-31", "mois": 6})
        self.assertEqual(self.js(proposer, {"date_debut": "2025-03-01", "date_fin": "2027-02-28"}),
                         {"date_debut": "2027-03-01", "date_fin": "2029-02-28", "mois": 24})
        # ni durée ni début : 12 mois
        self.assertEqual(self.js(proposer, {"date_debut": "", "date_fin": "2026-12-31"}),
                         {"date_debut": "2027-01-01", "date_fin": "2027-12-31", "mois": 12})
        # fins de mois gardées
        self.assertEqual(self.js(proposer, {"date_fin": "2026-09-30", "reconduction_mois": "3"}),
                         {"date_debut": "2026-10-01", "date_fin": "2026-12-31", "mois": 3})
        self.assertEqual(self.js(proposer, {"date_fin": "2027-02-28", "reconduction_mois": "12"}),
                         {"date_debut": "2027-03-01", "date_fin": "2028-02-29", "mois": 12})
        self.assertIsNone(self.js(proposer, {"date_fin": "31/12/2026"}))

    def test_total_des_montants(self):
        # le 01/08/2026 : CTP-0001 (à décider, 4 800), CTP-0002 (en cours, sans montant), CTP-0003 (dates à mettre à
        # jour, 1 200,50), CTP-0004 (à décider, période calculée, 1 350), CTP-0008 (en cours, sans montant),
        # CTP-0009 (en cours, 2 000) ; CTP-0005 terminé, CTP-0006 fin inconnue, CTP-0007 retiré : hors du total
        total = self.js("() => Garanties.totalMontants(undefined, '2026-08-01')")
        self.assertEqual(total, {"centimes": 480000 + 120050 + 135000 + 200000, "sansMontant": 2})
        total = self.js("() => Garanties.totalMontants(Donnees.lignes('contrats_prestataires'), '2027-01-01')")
        self.assertEqual(total, {"centimes": 480000 + 120050 + 135000, "sansMontant": 1})

    def test_montants_au_centime(self):
        total = "(montants) => Garanties.totalMontants(montants.map((m, i) => ({ id: 'CTP-' + i, date_fin: " \
                "'2030-12-31', montant_annuel: m })), '2026-08-01')"
        self.assertEqual(self.js(total, ["0,29", "0.1", "0,2"]), {"centimes": 59, "sansMontant": 0})
        self.assertEqual(self.js(total, ["4 800,505", "1234.564"]), {"centimes": 480051 + 123456, "sansMontant": 0})
        self.assertEqual(self.js(total, ["0", "", "abc", "-5"]), {"centimes": 0, "sansMontant": 3})


class TestEcheances(CasGaranties):

    def test_a_echeance(self):
        echeances = self.js("() => { const e = Garanties.aEcheance('2026-08-01'); return { "
                            "garanties: e.garanties.map((g) => g.id), contrats: e.contrats.map((c) => c.id), "
                            "aMettreAJour: e.aMettreAJour.map((c) => c.id) }; }")
        # GAR-0002 finit le 30/09 ; GAR-0005 (équipement au rebut) et GAR-0007 (retirée) écartées
        self.assertEqual(echeances["garanties"], ["GAR-0002"])
        # triés par date de l'alerte : deux dates limites le 30/09/2026, puis par identifiant ; CTP-0009 (même date
        # limite, sans reconduction tacite) n'a rien à décider (T463)
        self.assertEqual(echeances["contrats"], ["CTP-0001", "CTP-0004"])
        self.assertEqual(echeances["aMettreAJour"], ["CTP-0003"])

    def test_a_echeance_tri_par_date(self):
        echeances = self.js("() => { const e = Garanties.aEcheance('2026-11-05'); return { "
                            "contrats: e.contrats.map((c) => c.id), aMettreAJour: e.aMettreAJour.map((c) => c.id) }; }")
        # CTP-0002 (préavis vide) et CTP-0009 (préavis 3 mois) se terminent bientôt : fin 31/12/2026
        self.assertEqual(echeances["contrats"], ["CTP-0002", "CTP-0009"])
        self.assertEqual(echeances["aMettreAJour"], ["CTP-0003", "CTP-0004"])
        # délai passé en argument
        self.assertEqual(self.js("() => Garanties.aEcheance('2026-11-05', 30).contrats.map((c) => c.id)"), [])


class TestVerifier(CasGaranties):

    def erreurs(self, fonction, valeurs):
        return self.js("([f, v]) => Garanties[f](v).map((e) => e.nom + ' : ' + e.message)", [fonction, valeurs])

    def test_verifier_garantie(self):
        valide = {"equipement_id": "EQ-0001", "fournisseur_id": "FOU-0001", "date_debut": "2026-01-01",
                  "date_fin": "2028-01-01"}
        self.assertEqual(self.erreurs("verifierGarantie", valide), [])
        self.assertEqual(self.erreurs("verifierGarantie", dict(valide, fournisseur_id="", date_debut="")), [])
        self.assertEqual(self.erreurs("verifierGarantie", dict(valide, date_fin="2026-01-01")), [])
        self.assertEqual(self.erreurs("verifierGarantie", {}),
                         ["equipement_id : Choisissez l'équipement couvert.",
                          "date_fin : Saisissez la date de fin de la garantie."])
        self.assertEqual(self.erreurs("verifierGarantie", dict(valide, equipement_id="EQ-0099",
                                                               fournisseur_id="FOU-0099")),
                         ["equipement_id : L'équipement EQ-0099 est introuvable.",
                          "fournisseur_id : Le fournisseur FOU-0099 est introuvable."])
        self.assertEqual(self.erreurs("verifierGarantie", dict(valide, date_debut="01/01/2026", date_fin="2026-02-30")),
                         ["date_debut : Date de début illisible : JJ/MM/AAAA.",
                          "date_fin : Date de fin illisible : JJ/MM/AAAA."])
        self.assertEqual(self.erreurs("verifierGarantie", dict(valide, date_fin="2025-12-31")),
                         ["date_fin : La date de fin ne peut pas précéder la date de début."])

    def test_verifier_contrat(self):
        valide = {"fournisseur_id": "FOU-0002", "objet": "Maintenance", "equipement_ids": "EQ-0001;EQ-0002",
                  "date_debut": "2026-01-01", "date_fin": "2026-12-31", "preavis_mois": "3",
                  "reconduction_tacite": "1", "reconduction_mois": "12", "montant_annuel": "4 800,50"}
        self.assertEqual(self.erreurs("verifierContrat", valide), [])
        self.assertEqual(self.erreurs("verifierContrat", dict(valide, equipement_ids="", date_debut="",
                                                              preavis_mois="0", reconduction_mois="",
                                                              montant_annuel="0")), [])
        self.assertEqual(self.erreurs("verifierContrat", {}),
                         ["fournisseur_id : Choisissez le prestataire.",
                          "objet : Saisissez l'objet du contrat.",
                          "date_fin : Saisissez la date de fin de la période en cours."])
        self.assertEqual(self.erreurs("verifierContrat", dict(valide, fournisseur_id="FOU-0099",
                                                              equipement_ids="EQ-0001;EQ-0099")),
                         ["fournisseur_id : Le prestataire FOU-0099 est introuvable.",
                          "equipement_ids : L'équipement EQ-0099 est introuvable."])
        for preavis in ("trois", "-1", "1,5"):
            with self.subTest(preavis=preavis):
                self.assertEqual(self.erreurs("verifierContrat", dict(valide, preavis_mois=preavis)),
                                 ["preavis_mois : Préavis : un nombre entier de mois, 0 ou plus."])
        for mois in ("0", "douze", "-12"):
            with self.subTest(reconduction=mois):
                self.assertEqual(self.erreurs("verifierContrat", dict(valide, reconduction_mois=mois)),
                                 ["reconduction_mois : Durée d'une reconduction : un nombre entier de mois, 1 ou plus."])
        for montant in ("-5", "beaucoup", "4800 €"):
            with self.subTest(montant=montant):
                self.assertEqual(self.erreurs("verifierContrat", dict(valide, montant_annuel=montant)),
                                 ["montant_annuel : Montant : un nombre positif, ou rien."])
        self.assertEqual(self.erreurs("verifierContrat", dict(valide, date_fin="2025-12-31")),
                         ["date_fin : La date de fin ne peut pas précéder la date de début."])

    def test_avertissements_contrat(self):
        valeurs = {"date_debut": "2026-10-15", "date_fin": "2026-12-31", "preavis_mois": "3"}
        self.assertEqual(self.erreurs("avertissementsContrat", valeurs),
                         ["preavis_mois : Le préavis dépasse la durée du contrat : la date limite de résiliation "
                          "tombe avant son début."])
        self.assertEqual(self.erreurs("avertissementsContrat", dict(valeurs, preavis_mois="2")), [])
        self.assertEqual(self.erreurs("avertissementsContrat", dict(valeurs, date_debut="")), [])
        self.assertEqual(self.erreurs("avertissementsContrat", {}), [])


if __name__ == "__main__":
    unittest.main()
