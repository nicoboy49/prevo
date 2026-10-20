"""Tests des règles pures du lot 2 (ARCHITECTURE.md §14.3, §14.4, §14.5 ; tâche T26).

Couvre, sur un petit jeu de données construit À LA MAIN dans ce fichier (indépendant de la démo),
avec des dates fixes passées en argument (aujourd'hui = mardi 20/10/2026) :
    - Preventif.etatGamme : déclencheurs date, compteur (heures et cycles), seuil ; statuts
      inactive, ot_ouvert, echue, bientot, a_jour, incomplete ; Preventif.dernierReleve ;
    - Preventif.calendrier : semaines du lundi au dimanche, placement des échéances et des OT ;
    - Magasin.suggestionPointCommande (D23), Magasin.aCommander, Magasin.sortiesDeLOt ;
    - CausesFrequentes.calculer (portées équipement et modèle, cas ignorés, tri, limite à 3)
      et CausesFrequentes.encart (textes exacts, échappement d'un libellé piégé).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_regles_lot2.py" -v
"""
import datetime
import re
import unittest

from commun import CasNavigateur, charger_scripts

SCRIPTS = [
    "js/lib/papaparse.min.js",
    "js/schema.js",
    "js/donnees.js",
    "js/stockage-demo.js",
    "js/interface.js",
    "js/modules/causes-frequentes.js",
    "js/modules/preventif-regles.js",
    "js/modules/magasin-regles.js",
]

AUJOURDHUI = "2026-10-20"          # un mardi : la semaine commence le lundi 19/10/2026


# ---------------------------------------------------------------------------
# Jeu de données construit à la main (seules les colonnes utiles sont écrites :
# une colonne absente prend la valeur par défaut du schéma)
# ---------------------------------------------------------------------------

def csv(entete, lignes):
    """Texte CSV au format §3.1 (séparateur ;, fins de ligne CRLF)."""
    return "\r\n".join([entete] + list(lignes)) + "\r\n"


def decaler(date_iso, jours):
    return (datetime.date.fromisoformat(date_iso) + datetime.timedelta(days=jours)).isoformat()


PARAMETRES = csv("cle;valeur", ["heures_fonct_defaut;8", "horizon_calendrier_semaines;12"])

EQUIPEMENTS = csv("id;repere;designation;marque;modele;heures_fonct_jour;actif", [
    "EQ-0001;PO-01;Pompe A;Grundfos;CR 10;20;1",
    "EQ-0002;PO-02;Pompe B;GRUNDFOS;cr10;;1",         # même marque et modèle (casse, espaces)
    "EQ-0003;CP-01;Compresseur;Atlas;GA30;;1",         # sans heures par jour : paramètre (8)
    "EQ-0004;PO-03;Pompe C;Grundfos;CR 15;;1",         # autre modèle
    "EQ-0005;VE-01;Ventilateur;;;;1",                  # ni marque ni modèle
])

COMPTEURS = csv("id;equipement_id;libelle;unite", [
    "CPT-0001;EQ-0001;Heures de marche;h",
    "CPT-0002;EQ-0003;Cycles;cycles",
    "CPT-0003;EQ-0001;Température palier;°C",
    "CPT-0004;EQ-0003;Heures;heures",
    "CPT-0005;EQ-0005;Heures;h",                       # aucun relevé
])

RELEVES = csv("id;compteur_id;date;valeur", [
    "REL-000009;CPT-0001;2026-09-01;3000",             # identifiant plus grand, date plus ancienne
    "REL-000005;CPT-0001;2026-10-10;3999",             # même date que REL-000002 : identifiant plus grand
    "REL-000002;CPT-0001;2026-10-10;3990",
    "REL-000003;CPT-0002;2026-10-15;52000",
    "REL-000004;CPT-0003;2026-10-12;74",
    "REL-000006;CPT-0004;2026-10-16;1500",
    "REL-000008;CPT-0004;2026-10-18;illisible",        # valeur illisible : ignoré
])

GAMMES = csv("id;equipement_id;libelle;declencheur;periodicite_jours;compteur_id;periodicite_unites;seuil;"
             "avance_jours;derniere_realisation;releve_derniere_realisation;prochaine_echeance;actif", [
    "GAM-0001;EQ-0001;Graissage mensuel;date;30;;;;0;;;;1",
    "GAM-0002;EQ-0001;Contrôle courroies;date;30;;;;7;;;2026-10-27;1",
    "GAM-0003;EQ-0001;Vidange 2 000 h;compteur;;CPT-0001;2000;;;;2999;;1",
    "GAM-0004;EQ-0003;Révision 50 000 cycles;compteur;;CPT-0002;50000;;;;0;;1",
    "GAM-0005;EQ-0001;Palier chaud;seuil;;CPT-0003;;70;;2026-10-14;;;1",
    "GAM-0006;EQ-0001;Ancienne gamme;date;30;;;;;;;;0",
    "GAM-0007;EQ-0003;Contrôle soupapes;date;90;;;;;2026-08-01;;;1",
    "GAM-0008;EQ-0003;Graissage 400 h;compteur;;CPT-0004;400;;;;1200;;1",
    "GAM-0009;EQ-0004;Révision annuelle;date;365;;;;;;;2027-03-01;1",
    "GAM-0010;EQ-0004;Contrôle mensuel;date;30;;;;;2026-09-01;;;1",
    "GAM-0011;EQ-0005;Gamme sans périodicité;date;;;;;;2026-09-01;;;1",
])

ENTETE_OT = "id;origine;gamme_id;equipement_id;type;priorite;statut;titre;date_prevue;date_fin;" \
            "symptome_code;cause_code;remede_code"


def ot_correctif(numero, equipement, statut, date_fin, symptome, cause, remede, type_ot="correctif différé"):
    fin = date_fin + " 10:00" if date_fin else ""
    return "OT-2026-%04d;DI;;%s;%s;P2;%s;Panne;;%s;%s;%s;%s" % (
        numero, equipement, type_ot, statut, fin, symptome, cause, remede)


CLOS = "Clôturé techniquement"

ORDRES = csv(ENTETE_OT, [
    # Préventif
    "OT-2026-0009;préventif;GAM-0007;EQ-0003;préventif systématique;P3;Clôturé techniquement;Contrôle soupapes;2026-08-01;2026-08-01 10:00;;;",
    "OT-2026-0010;préventif;GAM-0007;EQ-0003;préventif systématique;P3;Planifié;Contrôle soupapes;2026-10-28;;;;",
    "OT-2026-0011;manuel;;EQ-0004;préventif systématique;P3;Créé;Préventif manuel;2026-12-15;;;;",
    "OT-2026-0012;DI;;EQ-0004;correctif différé;P2;Créé;Fuite;2026-10-22;;;;",
    "OT-2026-0013;préventif;GAM-0010;EQ-0004;préventif systématique;P3;Annulé;Contrôle mensuel;2026-10-21;;;;",
    # Symptôme VIB sur EQ-0005 : exactement 5 cas valables…
    ot_correctif(101, "EQ-0005", CLOS, "2026-01-10", "VIB", "GAR", "REM"),
    ot_correctif(102, "EQ-0005", "Clôturé administrativement", "2026-03-10", "VIB", "GAR", "RES", "correctif immédiat"),
    ot_correctif(103, "EQ-0005", CLOS, "2026-05-10", "VIB", "GAR", "REM"),
    ot_correctif(104, "EQ-0005", CLOS, "2026-02-10", "VIB", "JOI", "REM"),
    ot_correctif(105, "EQ-0005", CLOS, "2026-06-10", "VIB", "JOI", "NET"),
    # … et des OT à ignorer : non clôturé, préventif, cause vide, annulé
    ot_correctif(106, "EQ-0005", "En cours", "", "VIB", "GAR", ""),
    ot_correctif(107, "EQ-0005", CLOS, "2026-07-10", "VIB", "GAR", "REM", "préventif systématique"),
    ot_correctif(108, "EQ-0005", CLOS, "2026-07-11", "VIB", "", "REM"),
    ot_correctif(109, "EQ-0005", "Annulé", "", "VIB", "GAR", ""),
    ot_correctif(110, "EQ-0003", CLOS, "2026-04-10", "VIB", "GAR", "REM"),      # autre équipement
    # Symptôme FUI : 4 cas sur EQ-0001, 2 sur EQ-0002 (même modèle), 3 sur EQ-0004 (autre modèle)
    ot_correctif(201, "EQ-0001", CLOS, "2026-02-10", "FUI", "GAR", "REM"),
    ot_correctif(202, "EQ-0001", CLOS, "2026-05-10", "FUI", "GAR", "REM"),
    ot_correctif(203, "EQ-0001", CLOS, "2026-07-10", "FUI", "XSS", "NET"),
    ot_correctif(204, "EQ-0001", CLOS, "2026-09-20", "FUI", "JOI", "RES"),
    ot_correctif(205, "EQ-0002", CLOS, "2026-08-15", "FUI", "GAR", "RES"),
    ot_correctif(206, "EQ-0002", CLOS, "2026-03-15", "FUI", "SER", "RES"),
    ot_correctif(207, "EQ-0004", CLOS, "2026-09-25", "FUI", "ROU", "REM"),
    ot_correctif(208, "EQ-0004", CLOS, "2026-09-26", "FUI", "ROU", "REM"),
    ot_correctif(209, "EQ-0004", CLOS, "2026-09-27", "FUI", "ROU", "REM"),
    # Symptôme BRU sur EQ-0005 : 2 cas seulement
    ot_correctif(301, "EQ-0005", CLOS, "2026-04-01", "BRU", "ROU", "REM"),
    ot_correctif(302, "EQ-0005", CLOS, "2026-05-01", "BRU", "ROU", "REM"),
])

LIBELLE_PIEGE = "<img src=x onerror=window.piege=1>"

CODES = csv("id;famille;code;libelle", [
    "CD-0001;symptôme;FUI;Fuite",
    "CD-0002;symptôme;VIB;Vibrations",
    "CD-0003;symptôme;BRU;Bruit anormal",
    "CD-0004;cause;GAR;garniture usée",
    "CD-0005;cause;JOI;joint détérioré",
    "CD-0006;cause;SER;serrage insuffisant",
    "CD-0007;cause;ROU;roulement HS",
    "CD-0008;cause;XSS;" + LIBELLE_PIEGE,
    "CD-0009;remède;REM;remplacement pièce",
    "CD-0010;remède;RES;resserrage",
    "CD-0011;remède;NET;nettoyage",
])

ARTICLES = csv("id;reference;designation;stock_securite;point_commande;qte_commande;delai_jours;critique;actif", [
    "ART-0001;REF-001;Garniture;2;5;;10;0;1",
    "ART-0002;REF-002;Joint;1;;;30;0;1",
    "ART-0003;REF-003;Roulement;;;;10;0;1",
    "ART-0004;REF-004;Courroie;;4;10;;0;1",        # stock = point : à commander, quantité fixe 10
    "ART-0005;REF-005;Filtre;2;5;;;1;1",           # stock 3, critique : 5 − 3 + 2 = 4
    "ART-0006;REF-006;Ancien;;5;;;0;0",            # inactif
    "ART-0007;REF-007;Sans point;;;;;0;1",         # point de commande vide
    "ART-0008;REF-008;Bien stocké;;5;;;0;1",       # stock 6 > 5
    "ART-0009;REF-009;Point zéro;;0;;;0;1",        # stock 0 = point 0 : au moins 1
])


def mouvements():
    lignes = []

    def ajouter(date, article, type_mouvement, quantite, ot=""):
        lignes.append("MVT-%06d;%s 08:00;%s;%s;%s;%s" % (len(lignes) + 1, date, article, type_mouvement, quantite, ot))

    # ART-0001 : 73 sorties d'une unité dans les 365 derniers jours (du 21/10/2025 au 16/10/2026),
    # plus deux sorties trop anciennes (le 20/10/2025, il y a 365 jours, et le 01/06/2025).
    ajouter("2024-12-01", "ART-0001", "inventaire", 100)
    for rang in range(73):
        ajouter(decaler("2025-10-21", 5 * rang), "ART-0001", "sortie", 1, "OT-2026-0010" if rang == 72 else "")
    ajouter("2025-10-20", "ART-0001", "sortie", 5)
    ajouter("2025-06-01", "ART-0001", "sortie", 10)
    # ART-0002 : 50 sortis puis 13 retournés pour OT-2026-0010 (et une entrée qui ne compte pas)
    ajouter("2024-12-01", "ART-0002", "inventaire", 100)
    ajouter("2026-05-01", "ART-0002", "sortie", 50, "OT-2026-0010")
    ajouter("2026-05-02", "ART-0002", "retour", 13, "OT-2026-0010")
    ajouter("2026-05-03", "ART-0002", "entrée", 5, "OT-2026-0010")
    # ART-0003 : une entrée récente et une seule sortie, vieille de plus d'un an
    ajouter("2026-01-01", "ART-0003", "entrée", 10)
    ajouter("2025-01-15", "ART-0003", "sortie", 2)
    # Stocks des articles « à commander »
    ajouter("2026-01-01", "ART-0004", "inventaire", 4)
    ajouter("2026-01-01", "ART-0005", "inventaire", 3)
    ajouter("2026-01-01", "ART-0008", "inventaire", 6)
    return csv("id;date;article_id;type;quantite;ot_id", lignes)


def jeu_de_test():
    return {
        "parametres": PARAMETRES, "equipements": EQUIPEMENTS, "compteurs": COMPTEURS, "releves": RELEVES,
        "gammes": GAMMES, "ordres_travail": ORDRES, "codes_defaillance": CODES, "articles": ARTICLES,
        "mouvements_stock": mouvements(),
    }


def espaces(texte):
    """Remplace les espaces insécables (séparateur de milliers de fr-FR) par des espaces simples."""
    return re.sub("[  ]", " ", texte)


# ---------------------------------------------------------------------------
# Base des tests : page vide + scripts + jeu construit à la main
# ---------------------------------------------------------------------------

class CasRegles(CasNavigateur):

    def setUp(self):
        super().setUp()
        charger_scripts(self.page, SCRIPTS)
        self.page.evaluate("""async (tables) => {
          Donnees.initialiser(StockageDemo.creer(tables), { poste: 'Poste test', profil: 'Responsable test' });
          await Donnees.chargerTout();
        }""", jeu_de_test())

    def js(self, script, argument=None):
        return self.page.evaluate(script, argument)

    def etat(self, gamme_id, jour=AUJOURDHUI, modifications=None):
        """Preventif.etatGamme sur la gamme du jeu, éventuellement modifiée (copie) pour le test."""
        return self.js("""([id, jour, modifications]) => Preventif.etatGamme(
            modifications ? Object.assign({}, Donnees.trouver('gammes', id), modifications) : id, jour)""",
                       [gamme_id, jour, modifications])


# ---------------------------------------------------------------------------
# Preventif.etatGamme — déclencheur date
# ---------------------------------------------------------------------------

class TestEtatGammeDate(CasRegles):

    def test_jamais_realisee_est_echue(self):
        etat = self.etat("GAM-0001")
        self.assertEqual(etat["statut"], "echue")
        self.assertEqual(etat["echeance"], AUJOURDHUI)
        self.assertEqual(etat["declenchement"], AUJOURDHUI)
        self.assertEqual(etat["raison"], "jamais réalisée")
        self.assertEqual(etat["otOuvertId"], "")
        self.assertIsNone(etat["releveActuel"])

    def test_echeance_moins_avance(self):
        # prochaine_echeance 27/10/2026, avance 7 jours : déclenchement le 20/10/2026
        etat = self.etat("GAM-0002")
        self.assertEqual((etat["statut"], etat["echeance"], etat["declenchement"]),
                         ("echue", "2026-10-27", "2026-10-20"))
        self.assertEqual(etat["raison"], "échéance le 27/10/2026 (déclenchement le 20/10/2026, avance de 7 j)")
        self.assertEqual(etat["reste"], 7)
        # la veille du déclenchement : bientôt ; 14 jours avant : bientôt ; 15 jours avant : à jour
        self.assertEqual(self.etat("GAM-0002", "2026-10-19")["statut"], "bientot")
        self.assertEqual(self.etat("GAM-0002", "2026-10-06")["statut"], "bientot")
        self.assertEqual(self.etat("GAM-0002", "2026-10-05")["statut"], "a_jour")
        # sans prochaine_echeance : dernière réalisation + périodicité
        etat = self.etat("GAM-0002", AUJOURDHUI, {"prochaine_echeance": "", "derniere_realisation": "2026-10-10"})
        self.assertEqual((etat["echeance"], etat["declenchement"], etat["statut"]),
                         ("2026-11-09", "2026-11-02", "bientot"))

    def test_echue_depuis_une_date_passee(self):
        etat = self.etat("GAM-0010")       # 01/09/2026 + 30 jours ; son seul OT est annulé
        self.assertEqual((etat["statut"], etat["echeance"], etat["reste"]), ("echue", "2026-10-01", -19))
        self.assertEqual(etat["raison"], "échue depuis le 01/10/2026")
        self.assertEqual(etat["otOuvertId"], "")

    def test_date_loin_dans_le_futur_a_jour(self):
        etat = self.etat("GAM-0009")
        self.assertEqual((etat["statut"], etat["echeance"]), ("a_jour", "2027-03-01"))
        self.assertEqual(etat["raison"], "échéance le 01/03/2027")


# ---------------------------------------------------------------------------
# Preventif.etatGamme — déclencheurs compteur et seuil
# ---------------------------------------------------------------------------

class TestEtatGammeCompteurSeuil(CasRegles):

    def test_compteur_en_heures(self):
        # dernier relevé 3 999 h le 10/10/2026, base 2 999 : 1 000 h sur 2 000, reste 1 000 h,
        # échéance estimée = 10/10/2026 + 1 000 / 20 h par jour (équipement) = 29/11/2026
        etat = self.etat("GAM-0003")
        self.assertEqual((etat["statut"], etat["echeance"], etat["declenchement"]), ("a_jour", "2026-11-29", "2026-11-29"))
        self.assertEqual((etat["releveActuel"], etat["reste"]), (3999, 1000))
        self.assertEqual(espaces(etat["raison"]), "1 000 h sur 2 000")
        # 1 999 h sur 2 000 : pas échue (échéance estimée le lendemain du relevé)
        etat = self.etat("GAM-0003", AUJOURDHUI, {"releve_derniere_realisation": "2000"})
        self.assertNotEqual(etat["statut"], "echue")
        self.assertEqual((etat["reste"], etat["echeance"]), (1, "2026-10-11"))
        self.assertEqual(espaces(etat["raison"]), "1 999 h sur 2 000")
        # 2 000 h sur 2 000 : échue
        etat = self.etat("GAM-0003", AUJOURDHUI, {"releve_derniere_realisation": "1999"})
        self.assertEqual((etat["statut"], etat["reste"]), ("echue", 0))
        self.assertEqual(espaces(etat["raison"]), "2 000 h sur 2 000")

    def test_compteur_heures_par_defaut_et_arrondi(self):
        # équipement sans heures par jour → paramètre 8 h ; reste 100 h → 12,5 j → 13 j après le
        # 16/10/2026 (le relevé illisible du 18/10 est ignoré) ; dans les 14 jours → bientôt
        etat = self.etat("GAM-0008")
        self.assertEqual((etat["statut"], etat["echeance"], etat["releveActuel"], etat["reste"]),
                         ("bientot", "2026-10-29", 1500, 100))
        self.assertEqual(etat["raison"], "300 heures sur 400")

    def test_compteur_en_cycles_sans_echeance(self):
        etat = self.etat("GAM-0004")
        self.assertEqual((etat["statut"], etat["echeance"], etat["reste"]), ("echue", "", -2000))
        self.assertEqual(espaces(etat["raison"]), "52 000 cycles sur 50 000")
        etat = self.etat("GAM-0004", AUJOURDHUI, {"releve_derniere_realisation": "10000"})
        self.assertEqual((etat["statut"], etat["echeance"]), ("a_jour", ""))

    def test_seuil(self):
        # relevé 74 °C le 12/10/2026, seuil 70, dernière réalisation le 14/10 : relevé antérieur
        etat = self.etat("GAM-0005")
        self.assertEqual((etat["statut"], etat["releveActuel"], etat["reste"]), ("a_jour", 74, -4))
        self.assertEqual(etat["raison"], "relevé 74 °C ≥ seuil 70 °C, relevé antérieur à la dernière réalisation (14/10/2026)")
        # relevé postérieur à la dernière réalisation (ou jamais réalisée) : échue
        for derniere in ("2026-10-01", ""):
            with self.subTest(derniere=derniere):
                etat = self.etat("GAM-0005", AUJOURDHUI, {"derniere_realisation": derniere})
                self.assertEqual(etat["statut"], "echue")
                self.assertEqual(etat["raison"], "relevé 74 °C ≥ seuil 70 °C")
                self.assertEqual((etat["echeance"], etat["declenchement"]), ("", ""))
        # relevé du jour même de la réalisation : pas postérieur
        self.assertEqual(self.etat("GAM-0005", AUJOURDHUI, {"derniere_realisation": "2026-10-12"})["statut"], "a_jour")
        # sous le seuil
        etat = self.etat("GAM-0005", AUJOURDHUI, {"seuil": "80", "derniere_realisation": ""})
        self.assertEqual((etat["statut"], etat["raison"]), ("a_jour", "relevé 74 °C < seuil 80 °C"))


# ---------------------------------------------------------------------------
# Preventif.etatGamme — inactive, OT ouvert, incomplète ; dernierReleve ; constantes
# ---------------------------------------------------------------------------

class TestEtatGammeAutres(CasRegles):

    def test_inactive_et_ot_ouvert(self):
        self.assertEqual(self.etat("GAM-0006")["statut"], "inactive")
        etat = self.etat("GAM-0007")       # OT-2026-0009 clôturé, OT-2026-0010 planifié
        self.assertEqual((etat["statut"], etat["otOuvertId"], etat["echeance"]), ("ot_ouvert", "OT-2026-0010", "2026-10-30"))
        self.assertEqual(etat["raison"], "OT-2026-0010 ouvert (Planifié)")

    def test_parametres_manquants(self):
        cas = {
            "date sans périodicité": ("GAM-0011", None),
            "compteur non choisi": ("GAM-0003", {"compteur_id": ""}),
            "compteur introuvable": ("GAM-0003", {"compteur_id": "CPT-0099"}),
            "compteur sans relevé": ("GAM-0003", {"compteur_id": "CPT-0005"}),
            "compteur sans périodicité": ("GAM-0003", {"periodicite_unites": ""}),
            "seuil vide": ("GAM-0005", {"seuil": ""}),
            "déclencheur inconnu": ("GAM-0001", {"declencheur": "lune"}),
        }
        for nom, (gamme, modifications) in cas.items():
            with self.subTest(nom):
                etat = self.etat(gamme, AUJOURDHUI, modifications)
                self.assertEqual(etat["statut"], "incomplete")
                self.assertTrue(etat["raison"])
                self.assertEqual(etat["echeance"], "")

    def test_dernier_releve_et_constantes(self):
        resultat = self.js("""() => ({
          cpt1: Preventif.dernierReleve('CPT-0001'), cpt4: Preventif.dernierReleve('CPT-0004'),
          aucun: Preventif.dernierReleve('CPT-0005'), inconnu: Preventif.dernierReleve('CPT-0099'),
          declencheurs: Object.keys(Preventif.DECLENCHEURS), statuts: Object.keys(Preventif.STATUTS_GAMME),
          libelleEchue: Preventif.STATUTS_GAMME.echue, parIdentifiant: Preventif.etatGamme('GAM-0001', '2026-10-20').statut,
        })""")
        self.assertEqual(resultat["cpt1"], {"valeur": 3999, "date": "2026-10-10"})
        self.assertEqual(resultat["cpt4"], {"valeur": 1500, "date": "2026-10-16"})
        self.assertIsNone(resultat["aucun"])
        self.assertIsNone(resultat["inconnu"])
        self.assertEqual(resultat["declencheurs"], ["date", "compteur", "seuil"])
        self.assertEqual(sorted(resultat["statuts"]), sorted(["inactive", "ot_ouvert", "echue", "bientot", "a_jour", "incomplete"]))
        self.assertEqual(resultat["libelleEchue"], "Échue")
        self.assertEqual(resultat["parIdentifiant"], "echue")


# ---------------------------------------------------------------------------
# Preventif.calendrier
# ---------------------------------------------------------------------------

class TestCalendrier(CasRegles):

    def calendrier(self, jour=AUJOURDHUI, semaines=None):
        return self.js("([jour, semaines]) => Preventif.calendrier(jour, semaines === null ? undefined : semaines)",
                       [jour, semaines])

    def test_douze_semaines_du_lundi_au_dimanche(self):
        semaines = self.calendrier()        # 12 semaines : paramètre horizon_calendrier_semaines
        self.assertEqual(len(semaines), 12)
        for rang, semaine in enumerate(semaines):
            lundi = datetime.date.fromisoformat(semaine["lundi"])
            self.assertEqual(lundi.weekday(), 0)
            self.assertEqual(semaine["lundi"], decaler("2026-10-19", 7 * rang))
            self.assertEqual(semaine["dimanche"], decaler(semaine["lundi"], 6))
        self.assertEqual(semaines[-1]["dimanche"], "2027-01-10")
        # un dimanche reste dans la semaine commencée le lundi précédent
        self.assertEqual(self.calendrier("2026-10-25")[0]["lundi"], "2026-10-19")
        self.assertEqual(len(self.calendrier(AUJOURDHUI, 4)), 4)

    def test_placement_des_echeances_et_des_ot(self):
        semaines = self.calendrier()
        places = {rang: [(e["gammeId"], e["otId"], e["date"], e["estimee"]) for e in semaine["elements"]]
                  for rang, semaine in enumerate(semaines) if semaine["elements"]}
        self.assertEqual(places, {
            # échéance passée (en retard) : première semaine, avec sa vraie date
            0: [("GAM-0010", "", "2026-10-01", False), ("GAM-0001", "", "2026-10-20", False)],
            # GAM-0007 a un OT ouvert : c'est l'OT qui est placé, à sa date prévue
            1: [("GAM-0002", "", "2026-10-27", False), ("GAM-0007", "OT-2026-0010", "2026-10-28", False),
                ("GAM-0008", "", "2026-10-29", True)],
            5: [("GAM-0003", "", "2026-11-29", True)],       # dimanche de la semaine du 23/11
            8: [("", "OT-2026-0011", "2026-12-15", False)],  # OT préventif manuel ouvert
        })
        self.assertEqual(semaines[0]["elements"][0]["equipementId"], "EQ-0004")
        # 4 semaines : l'échéance du 29/11 n'est plus placée
        quatre = self.calendrier(AUJOURDHUI, 4)
        self.assertNotIn("GAM-0003", [e["gammeId"] for s in quatre for e in s["elements"]])


# ---------------------------------------------------------------------------
# Magasin
# ---------------------------------------------------------------------------

class TestMagasin(CasRegles):

    def test_suggestion_point_de_commande(self):
        resultat = self.js("""(jour) => ({
          garniture: Magasin.suggestionPointCommande('ART-0001', jour),
          joint: Magasin.suggestionPointCommande('ART-0002', jour),
          vieilleSortie: Magasin.suggestionPointCommande('ART-0003', jour),
          sansSortie: Magasin.suggestionPointCommande('ART-0004', jour),
          inconnu: Magasin.suggestionPointCommande('ART-0099', jour),
          stockGarniture: Donnees.stockArticle('ART-0001'),
        })""", AUJOURDHUI)
        # 73 sorties − 0 retour sur 365 jours, délai 10, sécurité 2 : 73 / 365 × 10 + 2 = 4
        # (les sorties du 20/10/2025 et du 01/06/2025, de 365 jours ou plus, sont ignorées)
        self.assertEqual(resultat["garniture"], 4)
        # (50 − 13) / 365 × 30 + 1 = 4,04 → 5 (sans déduire les retours : 5,11 → 6)
        self.assertEqual(resultat["joint"], 5)
        self.assertIsNone(resultat["vieilleSortie"])
        self.assertIsNone(resultat["sansSortie"])
        self.assertIsNone(resultat["inconnu"])
        self.assertEqual(resultat["stockGarniture"], 12)

    def test_a_commander(self):
        liste = self.js("""() => Magasin.aCommander().map((ligne) => ({ id: ligne.article.id, stock: ligne.stock,
          point: ligne.pointCommande, quantite: ligne.quantiteProposee }))""")
        self.assertEqual(liste, [
            {"id": "ART-0005", "stock": 3, "point": 5, "quantite": 4},    # critique d'abord
            {"id": "ART-0004", "stock": 4, "point": 4, "quantite": 10},   # stock = point : inclus
            {"id": "ART-0009", "stock": 0, "point": 0, "quantite": 1},    # au moins 1
        ])

    def test_sorties_de_l_ot_et_constantes(self):
        resultat = self.js("""() => ({ ot: Magasin.sortiesDeLOt('OT-2026-0010'), aucun: Magasin.sortiesDeLOt('OT-2026-0099'),
          types: Magasin.TYPES_MOUVEMENT, statuts: Magasin.STATUTS_ACHAT })""")
        self.assertEqual(resultat["ot"], [
            {"articleId": "ART-0002", "sorti": 50, "retourne": 13, "net": 37},
            {"articleId": "ART-0001", "sorti": 1, "retourne": 0, "net": 1},
        ])
        self.assertEqual(resultat["aucun"], [])
        self.assertEqual(resultat["types"], ["entrée", "sortie", "inventaire", "retour"])
        self.assertEqual(resultat["statuts"], ["demandée", "commandée", "reçue"])


# ---------------------------------------------------------------------------
# CausesFrequentes
# ---------------------------------------------------------------------------

class TestCausesFrequentes(CasRegles):

    def calculer(self, equipement, symptome, options=None):
        return self.js("([e, s, o]) => CausesFrequentes.calculer(e, s, o || undefined)", [equipement, symptome, options])

    def test_portee_equipement_cas_ignores(self):
        resultat = self.calculer("EQ-0005", "VIB")
        self.assertEqual((resultat["suffisant"], resultat["portee"], resultat["libellePortee"], resultat["total"]),
                         (True, "equipement", "cet équipement", 5))
        self.assertEqual(resultat["causes"], [
            {"code": "GAR", "libelle": "garniture usée", "nombre": 3, "dernierCas": "2026-05-10",
             "remede": {"code": "REM", "libelle": "remplacement pièce", "nombre": 2},
             "ots": ["OT-2026-0103", "OT-2026-0102", "OT-2026-0101"]},
            # remèdes à égalité (1 et 1) : le plus récent l'emporte
            {"code": "JOI", "libelle": "joint détérioré", "nombre": 2, "dernierCas": "2026-06-10",
             "remede": {"code": "NET", "libelle": "nettoyage", "nombre": 1},
             "ots": ["OT-2026-0105", "OT-2026-0104"]},
        ])
        # minimum 6 : pas assez, et ni marque ni modèle pour élargir
        resultat = self.calculer("EQ-0005", "VIB", {"minimum": 6})
        self.assertEqual((resultat["suffisant"], resultat["portee"], resultat["total"], resultat["causes"]),
                         (False, None, 5, []))

    def test_portee_modele_tri_et_limite(self):
        for equipement in ("EQ-0001", "EQ-0002"):
            with self.subTest(equipement=equipement):
                resultat = self.calculer(equipement, "FUI")
                self.assertEqual((resultat["suffisant"], resultat["portee"], resultat["total"]), (True, "modele", 6))
                self.assertIn("même marque et modèle", resultat["libellePortee"])
                # GAR 3 cas, puis trois causes à 1 cas départagées par le dernier cas : SER (mars) est coupée
                self.assertEqual([(c["code"], c["nombre"], c["dernierCas"]) for c in resultat["causes"]],
                                 [("GAR", 3, "2026-08-15"), ("JOI", 1, "2026-09-20"), ("XSS", 1, "2026-07-10")])
                self.assertEqual(resultat["causes"][0]["ots"], ["OT-2026-0205", "OT-2026-0202", "OT-2026-0201"])
                self.assertEqual(resultat["causes"][0]["remede"]["code"], "REM")
        self.assertEqual(self.calculer("EQ-0001", "FUI")["libellePortee"],
                         "équipements de même marque et modèle (Grundfos CR 10)")
        # autre modèle (CR 15) : ses 3 cas seulement
        resultat = self.calculer("EQ-0004", "FUI")
        self.assertEqual((resultat["suffisant"], resultat["portee"], resultat["total"]), (False, None, 3))
        # sans code symptôme, ou symptôme sans cas
        self.assertEqual(self.calculer("EQ-0005", "")["total"], 0)
        self.assertFalse(self.calculer("EQ-0005", "")["suffisant"])
        self.assertEqual(self.calculer("EQ-0005", "XXX")["total"], 0)

    def test_encart_au_dessus_du_seuil(self):
        encart = self.js("""() => {
          const element = CausesFrequentes.encart('EQ-0001', 'FUI');
          document.body.appendChild(element);
          return new Promise((fini) => setTimeout(() => fini({
            classes: Array.from(element.classList),
            titre: element.querySelector('h3').textContent,
            portee: element.querySelector('.aide').textContent,
            lignes: Array.from(element.querySelectorAll('li')).map((li) => li.textContent),
            liens: Array.from(element.querySelectorAll('li a')).map((a) => a.getAttribute('href')),
            mention: element.querySelector('.note').textContent,
            images: element.querySelectorAll('img').length,
            piege: window.piege === undefined ? null : window.piege,
            texte: element.textContent,
          }), 100));
        }""")
        self.assertIn("encadre", encart["classes"])
        self.assertEqual(encart["titre"], "Causes fréquentes ici — 6 cas")
        self.assertEqual(encart["portee"], "Portée : équipements de même marque et modèle (Grundfos CR 10)")
        self.assertEqual(encart["lignes"], [
            "garniture usée — 3 cas sur 6 · remède le plus utilisé : remplacement pièce · dernier cas : 15/08/2026"
            " · voir les OT : OT-2026-0205, OT-2026-0202, OT-2026-0201",
            "joint détérioré — 1 cas sur 6 · remède le plus utilisé : resserrage · dernier cas : 20/09/2026"
            " · voir les OT : OT-2026-0204",
            LIBELLE_PIEGE + " — 1 cas sur 6 · remède le plus utilisé : nettoyage · dernier cas : 10/07/2026"
            " · voir les OT : OT-2026-0203",
        ])
        self.assertEqual(encart["liens"], ["#/ot/OT-2026-0205", "#/ot/OT-2026-0202", "#/ot/OT-2026-0201",
                                           "#/ot/OT-2026-0204", "#/ot/OT-2026-0203"])
        self.assertEqual(encart["mention"], "Statistique de l'historique, pas un diagnostic")
        # libellé piégé : affiché comme texte, jamais interprété
        self.assertEqual(encart["images"], 0)
        self.assertIsNone(encart["piege"])
        self.assertNotIn("certaine", encart["texte"])

    def test_encart_au_seuil_en_dessous_et_sans_symptome(self):
        resultat = self.js("""() => {
          const texteDe = (element) => element ? element.textContent.replace(/\\s+/g, ' ').trim() : null;
          const auSeuil = CausesFrequentes.encart('EQ-0005', 'VIB');
          return {
            auSeuil: auSeuil.querySelector('h3').textContent,
            deuxCas: texteDe(CausesFrequentes.encart('EQ-0005', 'BRU')),
            autreModele: texteDe(CausesFrequentes.encart('EQ-0004', 'FUI')),
            classeDessous: CausesFrequentes.encart('EQ-0005', 'BRU').classList.contains('encadre'),
            listeDessous: CausesFrequentes.encart('EQ-0005', 'BRU').querySelectorAll('li').length,
            sansSymptome: CausesFrequentes.encart('EQ-0005', ''),
          };
        }""")
        self.assertEqual(resultat["auSeuil"], "Causes fréquentes ici — 5 cas")
        self.assertEqual(resultat["deuxCas"], "Pas encore assez de cas pour ce symptôme (2 sur 5)")
        self.assertEqual(resultat["autreModele"], "Pas encore assez de cas pour ce symptôme (3 sur 5)")
        self.assertTrue(resultat["classeDessous"])
        self.assertEqual(resultat["listeDessous"], 0)
        self.assertIsNone(resultat["sansSymptome"])


if __name__ == "__main__":
    unittest.main()
