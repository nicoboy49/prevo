"""Couche calculée du wiki : Wiki.page et Wiki.listePages (lot 6, ARCHITECTURE.md §20.3 ; tâche T96).

Deux familles :
    - jeu de démo (donnees/demo, lu tel quel, sans décalage des dates ; « maintenant » = date de
      référence) : la page des 31 équipements et la liste des pages = le calcul Python indépendant de
      tests/calcul_wiki.py, qui relit les CSV ;
    - base d'essai construite ici pour les cas limites, valeurs attendues calculées à la main dans les
      commentaires ET égalité avec le calcul Python : récidive à J + 30 (comptée, datée par la DI
      d'origine) et à J + 31 (non), le même jour après la clôture (comptée), OT annulé ou préventif
      jamais pris pour une récidive ; retour qui annule une sortie ; symptôme à 4 cas (insuffisant) et
      à 5 cas ; OT annulé et OT préventif ignorés ; clôture administrative comptée ; équipement sans
      consignation ; jumeaux de même marque et modèle écrits avec une autre casse et d'autres espaces,
      jumeau inactif écarté, récidive jamais comptée d'un équipement à l'autre ; synthèse validée suivie
      de 2 OT clôturés (à revoir, depuis = 2) et synthèse remplacée ignorée ;
    - pureté : aucune écriture (tables identiques, Donnees.modifier jamais appelé), aucun appel réseau.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_wiki_regles.py" -v
"""
import csv
import io
import re
import unittest
from pathlib import Path

from calcul_wiki import CalculWiki
from commun import CasNavigateur, charger_scripts

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_DEMO = RACINE / "donnees" / "demo"
SCRIPTS = [
    "js/lib/papaparse.min.js", "js/schema.js", "js/donnees.js", "js/stockage-demo.js",
    "js/modules/causes-frequentes.js", "js/modules/indicateurs-regles.js", "js/modules/wiki-regles.js",
]
MAINTENANT = "2026-10-19 10:00"


def date_reference():
    texte = (RACINE / "js" / "demo-donnees.js").read_text(encoding="utf-8")
    return re.search(r"""dateReference:\s*["'](\d{4}-\d{2}-\d{2})["']""", texte).group(1)


def table_csv(entete, lignes):
    """Texte CSV de Prévo (« ; », CRLF, guillemets RFC 4180 si besoin)."""
    sortie = io.StringIO()
    ecrivain = csv.writer(sortie, delimiter=";", lineterminator="\r\n")
    ecrivain.writerow(entete.split(";"))
    for ligne in lignes:
        ecrivain.writerow(ligne.split(";") if isinstance(ligne, str) else ligne)
    return sortie.getvalue()


# ---------------------------------------------------------------------------------------------------
# Base d'essai
# ---------------------------------------------------------------------------------------------------

COMPTE_RENDU_LONG = ("Vibrations importantes côté accouplement.\nMesures : 7,2 mm/s au palier avant, 3,1 mm/s au "
                     "palier arrière. Accouplement réaligné au comparateur, cales reprises, silentblocs changés. "
                     "Nouvelle mesure : 1,8 mm/s.")

EQUIPEMENTS = table_csv("id;repere;designation;marque;modele;statut;consignation;document;actif", [
    ["EQ-0001", "'PO-01", "Pompe de process A", "Hydro Nel", "HC 50", "en service",
     "1. Arrêter la pompe.\n2. Cadenasser le sectionneur Q1.", "proc-po01.pdf", "1"],
    # Jumeau : même marque et modèle, autre casse, sans espaces ; aucune consignation.
    "EQ-0002;'PO-02;Pompe de process B;hydronel;hc50;en service;;;1",
    # Jumeau inactif : jamais dans « même marque et modèle » des autres.
    "EQ-0003;'PO-03;Pompe déposée;HYDRONEL;HC 50;rebut;Voir PO-01.;;0",
    # Sans texte de consignation mais avec un document : la consignation est gardée (précision T96).
    "EQ-0004;'CP-01;Compresseur;Aerovis;AV 30;en service;;consignation-cp01.pdf;1",
    "EQ-0005;'CV-01;Convoyeur;;;en service;;;1",
])

CODES = table_csv("id;famille;code;libelle", [
    "CD-0001;symptôme;S01;Fuite", "CD-0002;symptôme;S02;Bruit anormal", "CD-0003;symptôme;S03;Vibration",
    "CD-0004;cause;C01;Garniture usée", "CD-0005;cause;C02;Roulement hors service", "CD-0006;cause;C03;Desserrage",
    "CD-0007;remède;R01;Remplacement de la pièce", "CD-0008;remède;R02;Réglage", "CD-0009;remède;R03;Resserrage",
])

# La DI d'origine date la panne (Indicateurs.datePanne) : OT-0002 le 04/02 à 23:00 (créé le 05/02),
# OT-0003 le 08/03 à 08:00.
DEMANDES = table_csv("id;date_heure;equipement_id;symptome;impact;statut;ot_id", [
    "DI-2026-0001;2026-02-04 23:00;EQ-0001;Fuite au presse-étoupe;arrêt;Acceptée;OT-2026-0002",
    "DI-2026-0002;2026-03-08 08:00;EQ-0001;Fuite encore;arrêt;Acceptée;OT-2026-0003",
])

ENTETE_OT = ("id;di_id;equipement_id;type;priorite;statut;titre;date_creation;date_fin;arret_production;duree_arret_h;"
             "symptome_code;cause_code;remede_code;compte_rendu;date_cloture_tech;date_cloture_admin")
ORDRES = table_csv(ENTETE_OT, [
    # --- PO-01, symptôme S01 « Fuite » : 5 cas (0001 à 0005), suffisant.
    # 0001 clôturé le 05/01 14:00 ; 0002 (C01) tombe en panne le 04/02 23:00 = J + 30 → récidive comptée.
    "OT-2026-0001;;EQ-0001;correctif immédiat;P1;Clôturé techniquement;Fuite garniture;2026-01-05 08:00;"
    "2026-01-05 12:00;1;4;S01;C01;R01;Garniture remplacée.;2026-01-05 14:00;",
    # 0002 clôturé administrativement (compté) le 05/02 16:00 ; 0003 (C01) en panne le 08/03 = J + 31 → non.
    "OT-2026-0002;DI-2026-0001;EQ-0001;correctif différé;P2;Clôturé administrativement;Fuite garniture (bis);"
    "2026-02-05 07:00;2026-02-05 15:00;1;2.5;S01;C01;R01;Garniture remplacée à nouveau.;2026-02-05 16:00;2026-02-10 09:00",
    # 0003 : pas de date de clôture technique → J = date de fin ; compte rendu protégé par apostrophe.
    "OT-2026-0003;DI-2026-0002;EQ-0001;correctif immédiat;P1;Clôturé techniquement;Fuite garniture (ter);"
    "2026-03-08 10:00;2026-03-08 12:00;1;;S01;C01;R02;'- Presse-étoupe réglé, plus de fuite.;;",
    # 0004 (C02) clôturé le 10/05 11:30 ; 0010 (C02, en cours) en panne le même jour à 20:00 → récidive.
    "OT-2026-0004;;EQ-0001;correctif différé;P2;Clôturé techniquement;Fuite côté palier;2026-05-10 08:00;"
    "2026-05-10 11:00;1;3;S01;C02;R01;Roulement changé.;2026-05-10 11:30;",
    # 0005 (C03) : suivi seulement d'un OT annulé (0011) et d'un préventif (0012) de même cause → pas de récidive.
    "OT-2026-0005;;EQ-0001;correctif immédiat;P1;Clôturé administrativement;Fuite bride;2026-07-01 08:00;"
    "2026-07-01 10:00;0;;S01;C03;R03;Bride resserrée.;2026-07-01 10:30;2026-07-03 09:00",
    # --- PO-01, symptôme S02 « Bruit anormal » : 4 cas (0006 à 0009) → insuffisant ; 0013 (annulé) et
    # 0014 (préventif) en feraient 6.
    "OT-2026-0006;;EQ-0001;correctif différé;P3;Clôturé techniquement;Bruit au démarrage;2025-10-20 08:00;"
    "2025-10-20 11:00;0;;S02;C02;R01;Roulement remplacé.;2025-10-20 11:30;",
    "OT-2026-0007;;EQ-0001;correctif différé;P3;Clôturé techniquement;Bruit persistant;2025-11-05 08:00;"
    "2025-11-05 10:00;0;;S02;C02;R02;Alignement repris.;2025-11-05 10:30;",
    # 0008 : panne le 19/10/2025, un jour avant la fenêtre des 12 mois (20/10/2025 → 19/10/2026).
    "OT-2026-0008;;EQ-0001;correctif différé;P3;Clôturé techniquement;Bruit léger;2025-10-19 08:00;"
    "2025-10-19 09:00;0;;S02;;;Rien trouvé.;2025-10-19 09:30;",
    "OT-2026-0009;;EQ-0001;correctif immédiat;P2;Clôturé techniquement;Bruit de cavitation;2026-04-15 08:00;"
    "2026-04-15 12:00;1;1;S02;C01;R09;Garniture et réglage.;2026-04-15 12:30;",
    "OT-2026-0010;;EQ-0001;correctif différé;P2;En cours;Fuite palier revenue;2026-05-10 20:00;;1;;S01;C02;;;;",
    "OT-2026-0011;;EQ-0001;correctif immédiat;P1;Annulé;Fuite bride (doublon);2026-07-05 08:00;;0;;S01;C03;;;;",
    "OT-2026-0012;;EQ-0001;préventif systématique;P3;Clôturé techniquement;Vidange et resserrage;2026-07-08 08:00;"
    "2026-07-10 10:00;0;;;C03;R03;Vidange faite.;2026-07-10 11:00;",
    "OT-2026-0013;;EQ-0001;correctif différé;P3;Annulé;Bruit (erreur de saisie);2026-02-10 08:00;;0;;S02;C02;;;;",
    "OT-2026-0014;;EQ-0001;préventif systématique;P3;Clôturé techniquement;Contrôle vibratoire;2026-07-18 08:00;"
    "2026-07-20 10:00;0;;S02;C02;R02;Contrôle fait.;2026-07-20 11:00;",
    ["OT-2026-0015", "", "EQ-0001", "correctif immédiat", "P1", "Clôturé techniquement", "Vibrations",
     "2026-08-18 08:00", "2026-08-20 08:00", "1", "6", "S03", "C02", "R02", COMPTE_RENDU_LONG, "2026-08-20 09:00", ""],
    # 0016 : correctif clôturé sans code symptôme → pas un cas.
    "OT-2026-0016;;EQ-0001;correctif différé;P3;Clôturé techniquement;Goutte à goutte;2026-06-10 08:00;"
    "2026-06-15 10:00;0;;;C01;R02;Surveillance.;2026-06-15 11:00;",
    # --- PO-02 (jumeau) : 0020 (C01) clôturé le 20/01 ; la panne de 0002 (PO-01, C01) 15 jours plus tard
    # n'est pas une récidive : autre équipement.
    "OT-2026-0020;;EQ-0002;correctif immédiat;P1;Clôturé techniquement;Fuite garniture PO-02;2026-01-20 08:00;"
    "2026-01-20 10:00;1;2;S01;C01;R01;Garniture changée.;2026-01-20 10:30;",
    "OT-2026-0021;;EQ-0002;correctif différé;P2;Clôturé administrativement;Fuite garniture PO-02;2026-06-01 08:00;"
    "2026-06-01 09:00;0;;S01;C01;R02;Réglage.;2026-06-01 09:30;2026-06-02 08:00",
    "OT-2026-0022;;EQ-0002;correctif différé;P3;Clôturé techniquement;Bruit PO-02;2026-03-01 08:00;"
    "2026-03-01 10:00;0;;S02;C02;R01;Roulement.;2026-03-01 10:30;",
    # --- PO-03 (jumeau inactif), CP-01, CV-01 (aucun OT clôturé : absent de la liste des pages).
    "OT-2026-0023;;EQ-0003;correctif immédiat;P1;Clôturé techniquement;Fuite PO-03;2026-05-01 08:00;"
    "2026-05-01 09:00;0;;S01;C01;R01;Ancienne pompe.;2026-05-01 09:30;",
    "OT-2026-0024;;EQ-0004;correctif immédiat;P1;Clôturé techniquement;Arrêt compresseur;2026-09-01 08:00;"
    "2026-09-01 10:00;1;2;S03;C03;R03;Raccord resserré.;2026-09-01 10:30;",
    "OT-2026-0025;;EQ-0004;préventif systématique;P3;Clôturé administrativement;Entretien;2026-09-15 08:00;"
    "2026-09-15 10:00;0;;;;;Fait.;2026-09-15 10:30;2026-09-20 08:00",
    "OT-2026-0026;;EQ-0005;correctif différé;P3;Planifié;Courroie à changer;2026-10-10 08:00;;0;;S02;;;;;",
])

ARTICLES = table_csv("id;reference;designation;actif", [
    "ART-0001;'ROU-6205;Roulement 6205;1", "ART-0002;'GAR-35;Garniture mécanique 35 mm;1",
    "ART-0003;'JNT-01;Joint de bride;1", "ART-0004;'HUI-01;Huile ISO VG 68 (litre);1",
])

MOUVEMENTS = table_csv("id;date;article_id;type;quantite;ot_id", [
    "MVT-000001;2026-01-01 08:00;ART-0001;inventaire;10;",
    "MVT-000002;2026-01-05 10:00;ART-0002;sortie;1;OT-2026-0001",
    "MVT-000003;2026-02-05 09:00;ART-0002;sortie;1;OT-2026-0002",
    "MVT-000004;2026-03-08 11:00;ART-0002;sortie;1;OT-2026-0003",
    # Roulement : 2 sortis puis 2 rendus sur 0004 (net 0, l'OT ne compte pas), 1 sorti sur 0006.
    "MVT-000005;2026-05-10 10:00;ART-0001;sortie;2;OT-2026-0004",
    "MVT-000006;2026-05-10 11:00;ART-0001;retour;2;OT-2026-0004",
    "MVT-000007;2025-10-20 10:00;ART-0001;sortie;1;OT-2026-0006",
    # Joint : sorti puis rendu → absent des pièces.
    "MVT-000008;2026-07-01 09:00;ART-0003;sortie;1;OT-2026-0005",
    "MVT-000009;2026-07-01 10:00;ART-0003;retour;1;OT-2026-0005",
    "MVT-000010;2026-07-10 08:00;ART-0004;sortie;5;OT-2026-0012",
    "MVT-000011;2026-01-05 12:00;ART-0002;inventaire;3;OT-2026-0001",
    "MVT-000012;2026-01-20 09:00;ART-0002;sortie;1;OT-2026-0020",
    "MVT-000013;2026-07-01 08:00;ART-0004;entrée;10;",
    "MVT-000014;2026-08-20 07:00;ART-0004;sortie;0.5;OT-2026-0015",
])

SOURCES_PO01 = ";".join("OT-2026-%04d" % n for n in (1, 2, 3, 4, 5, 6, 7, 8, 9, 16, 14))
SYNTHESES = table_csv("id;equipement_id;texte;ot_cites;ot_sources;statut;modele;date_proposition;corrigee_par;"
                      "date_modification;valide_par;date_validation", [
    # La plus récente de PO-01 est remplacée : jamais la synthèse courante.
    ["WIKI-0001", "EQ-0001", "Ce qui revient\n- Fuite. [OT-2026-0001]", "OT-2026-0001", "OT-2026-0001", "remplacée",
     "démo", "2026-09-01 10:00", "", "", "Responsable", "2026-09-01 10:05"],
    # Validée le 02/07 ; clôturés après elle et absents des sources : 0012 (10/07) et 0015 (20/08) → depuis = 2
    # (0014, clôturé le 20/07, est dans les sources).
    ["WIKI-0002", "EQ-0001", "Ce qui revient\n- Garniture. [OT-2026-0001]", "OT-2026-0001", SOURCES_PO01, "validée",
     "démo", "2026-07-02 09:00", "", "", "Responsable", "2026-07-02 09:30"],
    ["WIKI-0003", "EQ-0002", "Ce qui revient\n- Fuite. [OT-2026-0020]", "OT-2026-0020",
     "OT-2026-0020;OT-2026-0021;OT-2026-0022", "à valider", "démo", "2026-10-01 09:00", "", "", "", ""],
    ["WIKI-0004", "EQ-0004", "Ce qui revient\n- Raccord. [OT-2026-0024]", "OT-2026-0024",
     "OT-2026-0024;OT-2026-0025", "validée", "démo", "2026-10-01 09:00", "", "", "Responsable", "2026-10-01 09:10"],
])

BASE = {"equipements": EQUIPEMENTS, "codes_defaillance": CODES, "demandes": DEMANDES, "ordres_travail": ORDRES,
        "articles": ARTICLES, "mouvements_stock": MOUVEMENTS, "wiki_syntheses": SYNTHESES,
        "parametres": table_csv("cle;valeur", ["version_schema;3"])}
EQUIPEMENTS_BASE = ["EQ-0001", "EQ-0002", "EQ-0003", "EQ-0004", "EQ-0005"]


def comparable(valeur):
    """Forme comparable d'un résultat : flottants arrondis à 12 décimales ; synthèse réduite à ce que le
    calcul établit (identifiant, statut, état, depuis) ; synthèses remplacées réduites à leur identifiant."""
    if isinstance(valeur, dict):
        resultat = {}
        for cle, contenu in valeur.items():
            if cle == "synthese" and isinstance(contenu, dict):
                resultat[cle] = {c: contenu.get(c) for c in ("id", "statut", "etat", "depuis")}
            elif cle == "remplacees":
                resultat[cle] = [s["id"] for s in contenu]
            else:
                resultat[cle] = comparable(contenu)
        return resultat
    if isinstance(valeur, list):
        return [comparable(element) for element in valeur]
    if isinstance(valeur, float):
        return round(valeur, 12)
    return valeur


# ---------------------------------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------------------------------

class CasWiki(CasNavigateur):

    def charger(self, tables):
        self.requetes = []
        self.page.on("request", lambda requete: self.requetes.append(requete.url))
        charger_scripts(self.page, SCRIPTS)
        self.page.evaluate("""async (tables) => {
          Donnees.initialiser(StockageDemo.creer(tables), { poste: 'Poste test', profil: 'Responsable test' });
          await Donnees.chargerTout();
        }""", tables)

    def pages(self, equipements, maintenant=MAINTENANT):
        return self.page.evaluate("([ids, maintenant]) => ids.map((id) => Wiki.page(id, { maintenant }))",
                                  [equipements, maintenant])

    def page_de(self, equipement, maintenant=MAINTENANT):
        return self.pages([equipement], maintenant)[0]

    def liste(self, maintenant=MAINTENANT):
        return self.page.evaluate("(maintenant) => Wiki.listePages({ maintenant })", maintenant)

    def requetes_reseau(self):
        return [url for url in self.requetes if not url.startswith(("file:", "data:", "blob:"))]


class TestDemo(CasWiki):
    """Les 31 équipements de la démo : JavaScript = calcul Python indépendant."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tables = {f.stem: f.read_bytes().decode("utf-8-sig") for f in DOSSIER_DEMO.glob("*.csv")}
        cls.reference = date_reference()
        cls.calcul = CalculWiki(cls.tables)

    def setUp(self):
        super().setUp()
        self.charger(self.tables)

    def test_page_des_31_equipements_egale_au_calcul_python(self):
        ids = [e["id"] for e in self.calcul.equipements]
        self.assertEqual(len(ids), 31)
        obtenues = self.pages(ids, self.reference)
        recidives = 0
        for equipement_id, obtenue in zip(ids, obtenues):
            attendue = self.calcul.page(equipement_id, self.reference)
            with self.subTest(equipement=equipement_id):
                self.assertEqual(comparable(obtenue), comparable(attendue))
            recidives += sum(r["recidives"] for s in attendue["pannes"] for c in s["causes"] for r in c["remedes"])
        # Le calcul n'est pas vide sur la démo : des symptômes suffisants, des récidives, des pièces, des jumeaux.
        self.assertTrue(any(s["suffisant"] for p in obtenues for s in p["pannes"]))
        self.assertGreater(recidives, 0)
        self.assertTrue(any(p["pieces"] for p in obtenues))
        self.assertTrue(any(p["memeModele"] for p in obtenues))
        self.assertEqual(self.requetes_reseau(), [])

    def test_liste_des_pages_egale_au_calcul_python(self):
        obtenue = self.liste(self.reference)
        self.assertEqual(obtenue, self.calcul.liste_pages(self.reference))
        self.assertGreater(len(obtenue), 20)
        self.assertGreater(obtenue[0]["pannes12Mois"], 0)


class TestBaseEssai(CasWiki):
    """Base construite pour les cas limites : valeurs à la main et égalité avec le calcul Python."""

    def setUp(self):
        super().setUp()
        self.charger(BASE)

    def symptome(self, pannes, code):
        return next(s for s in pannes if s["code"] == code)

    def test_base_egale_au_calcul_python(self):
        calcul = CalculWiki(BASE)
        for equipement_id, obtenue in zip(EQUIPEMENTS_BASE, self.pages(EQUIPEMENTS_BASE)):
            with self.subTest(equipement=equipement_id):
                self.assertEqual(comparable(obtenue), comparable(calcul.page(equipement_id, MAINTENANT)))
        self.assertEqual(self.liste(), calcul.liste_pages(MAINTENANT))

    def test_recidive_a_j30_comptee_et_a_j31_non(self):
        fuite = self.symptome(self.page_de("EQ-0001")["pannes"], "S01")
        causes = {c["code"]: c for c in fuite["causes"]}
        # C01 : 0001 (R01) suivi de 0002 à J + 30 → récidive ; 0002 (R01) suivi de 0003 à J + 31 → non ;
        # 0003 (R02) : rien dans les 30 jours.
        self.assertEqual(causes["C01"]["remedes"], [
            {"code": "R01", "libelle": "Remplacement de la pièce", "fois": 2, "recidives": 1},
            {"code": "R02", "libelle": "Réglage", "fois": 1, "recidives": 0}])
        # C02 : 0004 suivi le même jour, après la clôture, de 0010 (en cours) → récidive.
        self.assertEqual(causes["C02"]["remedes"], [
            {"code": "R01", "libelle": "Remplacement de la pièce", "fois": 1, "recidives": 1}])
        # C03 : seuls un OT annulé (0011) et un préventif (0012) suivent 0005 → aucune récidive.
        self.assertEqual(causes["C03"]["remedes"], [{"code": "R03", "libelle": "Resserrage", "fois": 1, "recidives": 0}])

    def test_symptome_a_5_cas_et_a_4_cas_annule_et_preventif_ignores(self):
        pannes = self.page_de("EQ-0001")["pannes"]
        self.assertEqual([(s["code"], s["cas"], s["suffisant"]) for s in pannes],
                         [("S01", 5, True), ("S02", 4, False), ("S03", 1, False)])
        fuite, bruit = pannes[0], pannes[1]
        # 5 cas dont 2 clôturés administrativement (0002, 0005), tous avec une cause.
        self.assertEqual((fuite["libelle"], fuite["debut"], fuite["fin"], fuite["casAvecCause"]),
                         ("Fuite", "2026-01-05", "2026-07-01", 5))
        # C01 3 cas ; C02 et C03 1 cas chacun, C03 plus récent (01/07) que C02 (10/05).
        self.assertEqual([(c["code"], c["libelle"], c["nombre"], c["dernierCas"]) for c in fuite["causes"]], [
            ("C01", "Garniture usée", 3, "2026-03-08"), ("C03", "Desserrage", 1, "2026-07-01"),
            ("C02", "Roulement hors service", 1, "2026-05-10")])
        fourchette = fuite["causes"][0]["fourchette"]
        attendue = self.page.evaluate("CausesFrequentes.fourchette(3, 5)")
        self.assertEqual(fourchette, attendue)
        self.assertTrue(fuite["peuDeCas"])                                      # 5 cas : fourchettes larges (D59)
        # 4 cas (0013 annulé et 0014 préventif ignorés) : pas de causes, « 4 sur 5 ».
        self.assertEqual((bruit["cas"], bruit["casAvecCause"], bruit["causes"], bruit["debut"], bruit["fin"]),
                         (4, 3, [], "2025-10-19", "2026-04-15"))

    def test_pieces_sorties_moins_retours(self):
        pieces = self.page_de("EQ-0001")["pieces"]
        # Garniture : 3 OT ; huile : 5 + 0,5 sur 2 OT (le préventif compte) ; roulement : 2 sortis et
        # rendus sur 0004 (OT non compté), 1 sur 0006 ; joint rendu → absent ; inventaire ignoré.
        self.assertEqual([(p["reference"], p["designation"], p["quantite"], p["nombreOt"], p["derniereDate"]) for p in pieces], [
            ("GAR-35", "Garniture mécanique 35 mm", 3, 3, "2026-03-08"),
            ("HUI-01", "Huile ISO VG 68 (litre)", 5.5, 2, "2026-08-20"),
            ("ROU-6205", "Roulement 6205", 1, 1, "2025-10-20")])
        self.assertEqual([p["articleId"] for p in self.page_de("EQ-0002")["pieces"]], ["ART-0002"])

    def test_dernieres_interventions(self):
        page = self.page_de("EQ-0001")
        self.assertEqual(page["total"], 13)
        self.assertTrue(page["peutProposer"])
        self.assertEqual([d["id"][-4:] for d in page["dernieres"]],
                         ["0015", "0014", "0012", "0005", "0016", "0004", "0009", "0003", "0002", "0001"])
        par_id = {d["id"]: d for d in page["dernieres"]}
        long = par_id["OT-2026-0015"]["extrait"]
        self.assertEqual(len(long), 160)
        self.assertTrue(long.startswith("Vibrations importantes côté accouplement. Mesures : 7,2"))
        self.assertTrue(long.endswith("…"))
        self.assertEqual(par_id["OT-2026-0003"]["extrait"], "- Presse-étoupe réglé, plus de fuite.")
        self.assertIsNone(par_id["OT-2026-0003"]["dureeArret"])
        self.assertEqual(par_id["OT-2026-0002"]["dureeArret"], 2.5)
        self.assertEqual(par_id["OT-2026-0009"]["codes"], {"symptome": "Bruit anormal", "cause": "Garniture usée", "remede": "R09"})
        self.assertEqual(par_id["OT-2026-0012"]["codes"], {"symptome": "", "cause": "Desserrage", "remede": "Resserrage"})
        self.assertFalse(self.page_de("EQ-0002")["peutProposer"])

    def test_consignation_telle_quelle(self):
        pages = dict(zip(EQUIPEMENTS_BASE, self.pages(EQUIPEMENTS_BASE)))
        self.assertEqual(pages["EQ-0001"]["consignation"],
                         {"texte": "1. Arrêter la pompe.\n2. Cadenasser le sectionneur Q1.", "document": "proc-po01.pdf"})
        self.assertIsNone(pages["EQ-0002"]["consignation"])
        self.assertEqual(pages["EQ-0004"]["consignation"], {"texte": "", "document": "consignation-cp01.pdf"})
        self.assertEqual(pages["EQ-0001"]["equipement"]["repere"], "PO-01")

    def test_meme_marque_et_modele(self):
        pages = dict(zip(EQUIPEMENTS_BASE, self.pages(EQUIPEMENTS_BASE)))
        self.assertEqual(pages["EQ-0001"]["memeModele"]["equipements"], [{"id": "EQ-0002", "repere": "PO-02"}])
        self.assertEqual(pages["EQ-0002"]["memeModele"]["equipements"], [{"id": "EQ-0001", "repere": "PO-01"}])
        self.assertEqual([e["repere"] for e in pages["EQ-0003"]["memeModele"]["equipements"]], ["PO-01", "PO-02"])
        self.assertIsNone(pages["EQ-0004"]["memeModele"])
        self.assertIsNone(pages["EQ-0005"]["memeModele"])
        groupe = pages["EQ-0001"]["memeModele"]["pannes"]
        # PO-01 + PO-02 (PO-03, inactif, écarté) : fuite 5 + 2 = 7 cas, bruit 4 + 1 = 5 → suffisant.
        self.assertEqual([(s["code"], s["cas"], s["suffisant"]) for s in groupe], [("S01", 7, True), ("S02", 5, True), ("S03", 1, False)])
        fuite = self.symptome(groupe, "S01")
        # C01 / R01 : 0001 (récidive), 0002 et 0020 (la panne de 0002 sur PO-01 ne compte pas pour PO-02).
        self.assertEqual(fuite["causes"][0]["remedes"], [
            {"code": "R01", "libelle": "Remplacement de la pièce", "fois": 3, "recidives": 1},
            {"code": "R02", "libelle": "Réglage", "fois": 2, "recidives": 0}])
        bruit = self.symptome(groupe, "S02")
        # C02 : 0006 (R01) suivi de 0007 en 16 jours → récidive ; 0022 (R01, PO-02) non ; 0007 (R02) non.
        self.assertEqual([(c["code"], c["nombre"]) for c in bruit["causes"]], [("C02", 3), ("C01", 1)])
        # 5 cas dont 4 avec une cause (0008 n'en a pas) : la fourchette porte sur 3 / 4, comme l'encart.
        self.assertEqual(bruit["casAvecCause"], 4)
        self.assertEqual(bruit["causes"][0]["fourchette"], self.page.evaluate("CausesFrequentes.fourchette(3, 4)"))
        self.assertEqual(bruit["causes"][0]["remedes"], [
            {"code": "R01", "libelle": "Remplacement de la pièce", "fois": 2, "recidives": 1},
            {"code": "R02", "libelle": "Réglage", "fois": 1, "recidives": 0}])

    def test_etat_des_syntheses(self):
        pages = dict(zip(EQUIPEMENTS_BASE, self.pages(EQUIPEMENTS_BASE)))
        po01 = pages["EQ-0001"]
        self.assertEqual((po01["etat"], po01["synthese"]["id"], po01["synthese"]["statut"], po01["synthese"]["depuis"]),
                         ("a_revoir", "WIKI-0002", "validée", 2))
        self.assertEqual(po01["synthese"]["etat"], "a_revoir")
        self.assertEqual([s["id"] for s in po01["remplacees"]], ["WIKI-0001"])
        self.assertEqual((pages["EQ-0002"]["etat"], pages["EQ-0002"]["synthese"]["depuis"]), ("a_valider", 0))
        self.assertEqual((pages["EQ-0004"]["etat"], pages["EQ-0004"]["synthese"]["depuis"]), ("validee", 0))
        self.assertEqual((pages["EQ-0003"]["etat"], pages["EQ-0003"]["synthese"]), ("aucune", None))

    def test_liste_des_pages(self):
        # PO-01 : 10 cas, dont 0008 hors des 365 jours → 9 ; CP-01 et PO-03 à égalité (1) : par repère.
        self.assertEqual(self.liste(), [
            {"equipementId": "EQ-0001", "repere": "PO-01", "designation": "Pompe de process A", "pannes12Mois": 9, "etat": "a_revoir"},
            {"equipementId": "EQ-0002", "repere": "PO-02", "designation": "Pompe de process B", "pannes12Mois": 3, "etat": "a_valider"},
            {"equipementId": "EQ-0004", "repere": "CP-01", "designation": "Compresseur", "pannes12Mois": 1, "etat": "validee"},
            {"equipementId": "EQ-0003", "repere": "PO-03", "designation": "Pompe déposée", "pannes12Mois": 1, "etat": "aucune"},
        ])
        self.assertEqual(self.page_de("EQ-0001")["pannes12Mois"], 9)
        # Un jour plus tard, la panne du 20/10/2025 sort de la fenêtre.
        self.assertEqual(self.liste("2026-10-20")[0]["pannes12Mois"], 8)

    def test_equipement_inconnu(self):
        self.assertIsNone(self.page_de("EQ-9999"))

    def test_aucune_ecriture_ni_appel_reseau(self):
        resultat = self.page.evaluate("""(maintenant) => {
          const photo = () => JSON.stringify(Schema.nomsTables().map((nom) => [nom, Donnees.lignes(nom)]));
          const avant = photo();
          let ecritures = 0;
          const modifier = Donnees.modifier;
          Donnees.modifier = async (...arguments_) => { ecritures += 1; return modifier(...arguments_); };
          try {
            Donnees.lignes('equipements').forEach((e) => Wiki.page(e.id, { maintenant }));
            Wiki.listePages({ maintenant });
          } finally {
            Donnees.modifier = modifier;
          }
          return { identique: photo() === avant, ecritures };
        }""", MAINTENANT)
        self.assertEqual(resultat, {"identique": True, "ecritures": 0})
        self.assertEqual(self.requetes_reseau(), [])


if __name__ == "__main__":
    unittest.main()
