"""Couches calculées du composant et du mode, pages et catalogue du wiki (lot 6, ARCHITECTURE.md §20.3 ; tâche T112).

Trois familles :
    - jeu de démo (donnees/demo, lu tel quel) : la couche de chaque article (Wiki.pageComposant) et de chaque
      cause (Wiki.pageMode) = le calcul Python indépendant de tests/calcul_wiki.py, qui relit les CSV ;
    - base d'essai construite ici pour les cas limites, valeurs attendues écrites à la main ET égalité avec
      le calcul Python : retour qui annule une sortie (et retour partiel), article monté jamais consommé,
      article consommé hors de la liste, un seul remplacement (null), deux remplacements le même jour (0),
      nombre pair d'écarts (moyenne des deux du milieu) et impair (écarts non triés), OT annulé, en cours ou
      inconnu ignorés, préventif consommé compté, cause sans remède, OT préventif de même cause ignoré pour
      les cas, équipement inconnu écarté ; Wiki.page pour chaque forme d'identifiant (EQ, ART, WP d'équipement
      ou de composant ancré → identifiant canonique, mode ancré, mode libre, composant libre, savoir-faire
      rattaché à un équipement, à un article, à une page de composant, ancrage disparu), identifiant inconnu
      et page archivée → null ; en-tête du savoir-faire (consignation identique à la fiche : CRLF, espaces,
      tabulation, caractères spéciaux) ; retours ; crochets de wiki-journal.js ; catalogue (ordre, plafond) ;
      sous-pages (T131) : mère, sous-pages de la mère (actives, ordre alphabétique français), pas de couche
      calculée, en-tête d'une sous-page d'équipement = consignation de la fiche de l'équipement de sa mère,
      sous-page de savoir-faire = en-tête de sa mère, mère archivée, absente, sans équipement ; catalogue ;
    - pureté : aucune écriture (tables identiques, Donnees.modifier jamais appelé), aucun appel réseau.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_wiki_calculs.py" -v
"""
import csv
import io
import unittest
from pathlib import Path

from calcul_wiki import CalculWiki
from commun import CasNavigateur, charger_scripts

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_DEMO = RACINE / "donnees" / "demo"
SCRIPTS = [
    "js/lib/papaparse.min.js", "js/schema.js", "js/donnees.js", "js/stockage-demo.js",
    "js/modules/causes-frequentes.js", "js/modules/indicateurs-regles.js", "js/modules/wiki-regles.js",
    "js/modules/wiki-calculs.js", "js/modules/wiki-entites.js",
]
MAINTENANT = "2026-10-19 10:00"
PHRASE = "Ce savoir-faire ne remplace pas la consignation de l'équipement"
CRLF, TAB, NL = chr(13) + chr(10), chr(9), chr(10)


def table_csv(entete, lignes):
    """Texte CSV de Prévo (« ; », CRLF, guillemets RFC 4180 si besoin)."""
    sortie = io.StringIO()
    ecrivain = csv.writer(sortie, delimiter=";", lineterminator="\r\n")
    ecrivain.writerow(entete.split(";"))
    for ligne in lignes:
        ecrivain.writerow(ligne.split(";") if isinstance(ligne, str) else ligne)
    return sortie.getvalue()


def comparable(valeur):
    """Forme comparable d'un résultat : flottants arrondis à 12 décimales."""
    if isinstance(valeur, dict):
        return {cle: comparable(contenu) for cle, contenu in valeur.items()}
    if isinstance(valeur, list):
        return [comparable(element) for element in valeur]
    if isinstance(valeur, float):
        return round(valeur, 12)
    return valeur


# ---------------------------------------------------------------------------------------------------
# Base d'essai
# ---------------------------------------------------------------------------------------------------

# Consignation de PO-01 : deux espaces en tête, « ; », « & », guillemets, balise, CRLF, ligne vide, tabulation.
CONSIGNATION = ("  1. Arrêter la pompe ; fermer V1 & V2." + CRLF + "2. Cadenasser Q1 « rouge » <b>sans HTML</b>" + CRLF
                + CRLF + TAB + "3. Vérifier « 0 bar » — \"manomètre\" ; 'purge' = 100 %")
DOCUMENT = "Consignation PO-01 v2.pdf"

EQUIPEMENTS = table_csv("id;repere;designation;marque;modele;statut;consignation;document;actif", [
    ["EQ-0001", "'PO-01", "Pompe de process A", "Hydro Nel", "HC 50", "en service", CONSIGNATION, DOCUMENT, "1"],
    "EQ-0002;'PO-02;Pompe de process B;;;en service;;;1",
    "EQ-0003;'CV-01;Convoyeur;;;en service;Voir la procédure générale.;;1",
    "EQ-0004;'CP-01;Compresseur;;;en service;;;1",
    "EQ-0005;'BR-01;Broyeur;;;en service;;;1",
])

CODES = table_csv("id;famille;code;libelle", [
    "CD-0001;symptôme;S01;Fuite", "CD-0002;symptôme;S02;Bruit anormal", "CD-0003;symptôme;S03;Blocage",
    "CD-0004;cause;C01;Garniture usée", "CD-0005;cause;C02;Roulement hors service", "CD-0006;cause;C03;Desserrage",
    "CD-0007;cause;C04;Encrassement",
    "CD-0008;remède;R01;Remplacement de la pièce", "CD-0009;remède;R02;Réglage", "CD-0010;remède;R03;Nettoyage",
])

ORDRES = table_csv("id;equipement_id;type;priorite;statut;titre;date_creation;date_fin;symptome_code;cause_code;"
                   "remede_code;compte_rendu;date_cloture_tech;date_cloture_admin", [
    # --- PO-01 : trois consommations de roulement (10/01, 20/01, 20/02 → écarts 10 et 31 : médiane 20,5).
    "OT-2026-0001;EQ-0001;correctif immédiat;P1;Clôturé techniquement;Fuite garniture;2026-01-10 08:00;"
    "2026-01-10 12:00;S01;C01;R01;Garniture et joint changés.;2026-01-10 12:30;",
    "OT-2026-0002;EQ-0001;correctif différé;P2;Clôturé administrativement;Fuite garniture (bis);2026-01-20 08:00;"
    "2026-01-20 15:00;S01;C01;R01;Roulement changé.;2026-01-20 15:30;2026-01-25 09:00",
    # 0003 : 3 sortis, 1 rendu → 2.
    "OT-2026-0003;EQ-0001;correctif immédiat;P1;Clôturé techniquement;Fuite garniture (ter);2026-02-20 08:00;"
    "2026-02-20 12:00;S01;C01;R02;Deux roulements.;2026-02-20 12:30;",
    # 0004 : 2 sortis, 2 rendus → aucune consommation ; cause C02 sans remède.
    "OT-2026-0004;EQ-0001;correctif différé;P2;Clôturé techniquement;Bruit palier;2026-02-25 08:00;"
    "2026-02-25 12:00;S02;C02;;Roulement sorti puis rendu.;2026-02-25 12:30;",
    # 0005 en cours et 0006 annulé : ni consommation ni cas.
    "OT-2026-0005;EQ-0001;correctif immédiat;P1;En cours;Fuite encore;2026-03-02 08:00;;S01;C01;;;;",
    "OT-2026-0006;EQ-0001;correctif immédiat;P1;Annulé;Doublon;2026-03-03 08:00;;S01;C01;R01;;;",
    # --- BR-01 : quatre consommations (01/03, 31/03, 05/04, 17/04 → écarts 30, 5, 12 : médiane 12).
    "OT-2026-0010;EQ-0005;correctif différé;P2;Clôturé techniquement;Bruit broyeur;2026-03-01 08:00;"
    "2026-03-01 11:00;S02;C02;R01;Roulement.;2026-03-01 11:30;",
    "OT-2026-0011;EQ-0005;correctif différé;P2;Clôturé administrativement;Bruit broyeur (bis);2026-03-31 08:00;"
    "2026-03-31 10:00;S02;C02;;Roulement.;2026-03-31 10:30;2026-04-02 08:00",
    # 0012 : préventif clôturé de cause C01 — consommation comptée, cas du mode non.
    "OT-2026-0012;EQ-0005;préventif systématique;P3;Clôturé techniquement;Graissage et roulement;2026-04-05 08:00;"
    "2026-04-05 10:00;;C01;R01;Préventif.;2026-04-05 10:30;",
    "OT-2026-0013;EQ-0005;correctif immédiat;P1;Clôturé techniquement;Garniture broyeur;2026-04-17 08:00;"
    "2026-04-17 09:00;S01;C01;R03;Roulement.;2026-04-17 09:30;",
    # --- CV-01 : une seule consommation (médiane null) ; cause C09 absente des codes ; C04 sans remède.
    "OT-2026-0020;EQ-0003;correctif immédiat;P1;Clôturé techniquement;Rouleau bloqué;2026-04-20 08:00;"
    "2026-04-20 09:00;S03;C09;R02;Roulement.;2026-04-20 09:30;",
    "OT-2026-0023;EQ-0003;correctif différé;P3;Clôturé techniquement;Encrassement;2026-07-01 08:00;"
    "2026-07-01 10:00;S03;C04;;Nettoyé.;2026-07-01 10:30;",
    # Équipement inconnu : compté dans les cas de C04, absent de la liste de ses équipements.
    "OT-2026-0024;EQ-0099;correctif différé;P3;Clôturé techniquement;Ancienne machine;2026-07-02 08:00;"
    "2026-07-02 10:00;S03;C04;;Nettoyé.;2026-07-02 10:30;",
    # --- CP-01 : deux consommations le même jour (écart 0).
    "OT-2026-0021;EQ-0004;correctif immédiat;P1;Clôturé techniquement;Bruit compresseur;2026-05-05 08:00;"
    "2026-05-05 10:00;S02;C01;R01;Roulement.;2026-05-05 10:30;",
    "OT-2026-0022;EQ-0004;amélioration;P3;Clôturé techniquement;Second roulement;2026-05-05 14:00;"
    "2026-05-05 16:00;;;;Deux roulements.;2026-05-05 16:30;",
    # --- PO-02 : préventif qui consomme un joint (hors de la liste de montage).
    "OT-2026-0030;EQ-0002;préventif systématique;P3;Clôturé techniquement;Visite annuelle;2026-06-01 08:00;"
    "2026-06-01 11:00;;;;Joint changé.;2026-06-01 11:30;",
])

ARTICLES = table_csv("id;reference;designation;fabricant;ref_fabricant;emplacement;stock;actif", [
    # Stock du fichier volontairement faux : la page prend Donnees.stockArticle (mouvements).
    "ART-0001;'ROU-6205;Roulement 6205;Rouloran;'6205-2RS;A1-02;99;1",
    "ART-0002;'GAR-35;Garniture mécanique 35 mm;Étanchéa;'GM35;B2-01;4;1",
    "ART-0003;'JNT-01;Joint de bride;;;C1-05;10;1",
    "ART-0004;'FIL-01;Filtre à huile;Filtrex;'FH-10;;2;0",
])

ARTICLE_EQUIPEMENT = table_csv("id;article_id;equipement_id;quantite", [
    "AEQ-00001;ART-0001;EQ-0001;2", "AEQ-00002;ART-0001;EQ-0002;1", "AEQ-00003;ART-0001;EQ-0005;4",
    "AEQ-00004;ART-0002;EQ-0001;1", "AEQ-00005;ART-0002;EQ-0002;1.5",
    "AEQ-00006;ART-0002;EQ-0099;3",          # équipement inconnu : écarté
    "AEQ-00007;ART-0001;EQ-0001;3",          # seconde ligne du même couple : la première fait foi
])

MOUVEMENTS = table_csv("id;date;article_id;type;quantite;ot_id", [
    "MVT-000001;2026-01-01 08:00;ART-0001;inventaire;20;",
    "MVT-000002;2026-01-10 09:00;ART-0001;sortie;1;OT-2026-0001",
    "MVT-000003;2026-01-10 09:05;ART-0003;sortie;0.5;OT-2026-0001",
    "MVT-000004;2026-01-20 09:00;ART-0001;sortie;2;OT-2026-0002",
    "MVT-000005;2026-02-20 08:00;ART-0001;sortie;3;OT-2026-0003",
    "MVT-000006;2026-02-20 11:00;ART-0001;retour;1;OT-2026-0003",
    "MVT-000007;2026-02-25 08:00;ART-0001;sortie;2;OT-2026-0004",
    "MVT-000008;2026-02-25 10:00;ART-0001;retour;2;OT-2026-0004",
    "MVT-000009;2026-03-02 08:00;ART-0001;sortie;1;OT-2026-0005",
    "MVT-000010;2026-03-03 08:00;ART-0001;sortie;1;OT-2026-0006",
    "MVT-000011;2026-03-01 08:00;ART-0001;sortie;1;OT-2026-0010",
    "MVT-000012;2026-03-31 08:00;ART-0001;sortie;1;OT-2026-0011",
    "MVT-000013;2026-04-05 08:00;ART-0001;sortie;1;OT-2026-0012",
    "MVT-000014;2026-04-17 08:00;ART-0001;sortie;1;OT-2026-0013",
    "MVT-000015;2026-04-20 08:00;ART-0001;sortie;1;OT-2026-0020",
    "MVT-000016;2026-05-05 08:00;ART-0001;sortie;1;OT-2026-0021",
    "MVT-000017;2026-05-05 15:00;ART-0001;sortie;2;OT-2026-0022",
    "MVT-000018;2026-06-01 08:00;ART-0003;sortie;1;OT-2026-0030",
    "MVT-000019;2026-06-02 08:00;ART-0001;entrée;5;",
    "MVT-000020;2026-06-03 08:00;ART-0001;sortie;1;",
    "MVT-000021;2026-06-04 08:00;ART-0004;sortie;1;OT-2026-0999",     # OT inconnu : ignoré
])

ENTETE_WIKI = ("id;type;titre;cle;equipement_id;article_id;cause_code;rattache_a;texte;ot_cites;liens;version;origine;"
               "modele;derniere_entree;valide_par;valide_le;cree_le;modifie_le;statut")


def page_wiki(id_, type_, titre, texte="", liens="", equipement="", article="", cause="", rattache="",
              statut="active", origine="IA"):
    return [id_, type_, titre, "", equipement, article, cause, rattache, texte, "", liens, "1",
            origine if texte else "", "claude-sonnet-5-5" if texte else "", "", "Responsable fictif" if texte else "",
            "2026-10-01 10:00" if texte else "", "2026-10-01 09:00", "2026-10-01 10:00", statut]


TEXTE_PO01 = "## Ce qui revient" + NL + "- Fuite de garniture fréquente ici [OT-2026-0001] [OT-2026-0002]"
LIGNES_WIKI = [
    page_wiki("WP-0001", "équipement", "PO-01 — Pompe de process A", TEXTE_PO01, "WP-0004; ART-0001", equipement="EQ-0001"),
    page_wiki("WP-0002", "composant", "Roulement 6205", "## Défaillances" + NL + "- Usure rapide [OT-2026-0003]",
              "EQ-0001", article="ART-0001", origine="manuel"),
    page_wiki("WP-0003", "mode", "Usure de garniture", "## Causes" + NL + "- Garniture [OT-2026-0001]", "WP-0001",
              cause="C01"),
    page_wiki("WP-0004", "mode", "Cavitation", "## Symptômes" + NL + "- Bruit de gravier [OT-2026-0010]",
              "ART-0001;WP-0005"),
    page_wiki("WP-0005", "composant", "Courroie crantée", "## Signes d'usure" + NL + "- Craquelures [OT-2026-0020]"),
    page_wiki("WP-0006", "savoir-faire", "Changer la garniture de PO-01", "## Étapes" + NL + "- Repérer [OT-2026-0001]",
              "EQ-0001", equipement="EQ-0001"),
    page_wiki("WP-0007", "savoir-faire", "Monter un roulement 6205", "## Étapes" + NL + "- Chauffer [OT-2026-0003]",
              "WP-0002", article="ART-0001"),
    page_wiki("WP-0008", "savoir-faire", "Retendre une courroie", "## Étapes" + NL + "- Tendre [OT-2026-0020]",
              "WP-0005", rattache="WP-0005"),
    page_wiki("WP-0009", "savoir-faire", "Graisser un roulement", "## Étapes" + NL + "- Graisser [OT-2026-0012]",
              rattache="WP-0002"),
    page_wiki("WP-0010", "mode", "Ancienne page", "## Causes" + NL + "- Vieux [OT-2026-0001]",
              "EQ-0001;ART-0001;WP-0004", statut="archivée"),
    page_wiki("WP-0011", "savoir-faire", "Amorcer PO-02", "## Étapes" + NL + "- Purger [OT-2026-0030]",
              equipement="EQ-0002"),
    page_wiki("WP-0012", "mode", "Bouchage d'aspiration", cause="C02"),
    page_wiki("WP-0013", "équipement", "Ancienne presse", "## Astuces" + NL + "- Caler [OT-2026-0024]", "WP-0004",
              equipement="EQ-0099"),
]
WIKI_PAGES = table_csv(ENTETE_WIKI, LIGNES_WIKI)

# Sous-pages (§20.4, T131), ajoutées à la base pour leurs seuls tests : rattache_a = la ligne de la mère, de même type.
PHRASE_SOUS_PAGE = "Cette page ne remplace pas la consignation de l'équipement"
SOUS_PAGES = [
    page_wiki("WP-0020", "équipement", "PO-01 — garniture", "## Ce qui revient" + NL + "- Garniture sèche [OT-2026-0001]",
              rattache="WP-0001"),
    page_wiki("WP-0021", "équipement", "PO-01 — Étanchéité", "## À surveiller" + NL + "- Joint de corps [OT-2026-0002]",
              rattache="WP-0001"),
    page_wiki("WP-0022", "équipement", "PO-01 — accouplement", "## Astuces" + NL + "- Aligner [OT-2026-0001]",
              rattache="WP-0001", statut="archivée"),
    page_wiki("WP-0023", "composant", "Roulement 6205 — montage", "## Montage et remplacement" + NL + "- Chauffer [OT-2026-0003]",
              rattache="WP-0002"),
    page_wiki("WP-0024", "mode", "Cavitation — bruit", "## Symptômes" + NL + "- Gravier [OT-2026-0010]", rattache="WP-0004"),
    page_wiki("WP-0025", "savoir-faire", "Changer la garniture de PO-01 — remontage", "## Étapes" + NL + "- Serrer [OT-2026-0001]",
              rattache="WP-0006"),
    page_wiki("WP-0026", "équipement", "Ancienne presse — vérin", "## Astuces" + NL + "- Purger [OT-2026-0024]",
              rattache="WP-0013"),
    page_wiki("WP-0027", "mode", "Ancienne page — détail", "## Causes" + NL + "- Vieux [OT-2026-0001]", rattache="WP-0010"),
    page_wiki("WP-0028", "équipement", "XX-01 — mère perdue", "## Astuces" + NL + "- Rien [OT-2026-0001]", rattache="WP-0099"),
    # Savoir-faire rattaché à la page de PO-01 par rattache_a (pas une sous-page : autre type), et sa sous-page :
    # l'en-tête remonte deux rattachements jusqu'à la consignation (relecture de T130, CS98).
    page_wiki("WP-0029", "savoir-faire", "Graisser le palier de PO-01", "## Étapes" + NL + "- Graisser [OT-2026-0001]",
              rattache="WP-0001"),
    page_wiki("WP-0030", "savoir-faire", "Graisser le palier de PO-01 — graisse", "## Pièces et outillage" + NL
              + "- Graisse au lithium [OT-2026-0001]", rattache="WP-0029"),
]

BASE = {"equipements": EQUIPEMENTS, "codes_defaillance": CODES, "ordres_travail": ORDRES, "articles": ARTICLES,
        "article_equipement": ARTICLE_EQUIPEMENT, "mouvements_stock": MOUVEMENTS, "wiki_pages": WIKI_PAGES,
        "parametres": table_csv("cle;valeur", ["version_schema;3"])}
ARTICLES_BASE = ["ART-0001", "ART-0002", "ART-0003", "ART-0004"]
CAUSES_BASE = ["C01", "C02", "C03", "C04", "C09"]


# ---------------------------------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------------------------------

class CasCalculs(CasNavigateur):

    def charger(self, tables):
        self.requetes = []
        self.page.on("request", lambda requete: self.requetes.append(requete.url))
        charger_scripts(self.page, SCRIPTS)
        self.page.evaluate("""async (tables) => {
          Donnees.initialiser(StockageDemo.creer(tables), { poste: 'Poste test', profil: 'Responsable test' });
          await Donnees.chargerTout();
        }""", tables)

    def composants(self, ids):
        return self.page.evaluate("(ids) => ids.map((id) => Wiki.pageComposant(id))", ids)

    def modes(self, codes):
        return self.page.evaluate("(codes) => codes.map((code) => Wiki.pageMode(code))", codes)

    def page_wiki(self, identifiant, maintenant=MAINTENANT):
        return self.page.evaluate("([id, maintenant]) => Wiki.page(id, { maintenant })", [identifiant, maintenant])

    def requetes_reseau(self):
        return [url for url in self.requetes if not url.startswith(("file:", "data:", "blob:"))]


class TestDemo(CasCalculs):
    """Tous les articles et toutes les causes de la démo : JavaScript = calcul Python indépendant."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tables = {f.stem: f.read_bytes().decode("utf-8-sig") for f in DOSSIER_DEMO.glob("*.csv")}
        cls.calcul = CalculWiki(cls.tables)

    def setUp(self):
        super().setUp()
        self.charger(self.tables)

    def test_composant_de_chaque_article_egal_au_calcul_python(self):
        ids = sorted(self.calcul.articles)
        self.assertGreater(len(ids), 40)
        obtenus = self.composants(ids)
        for article_id, obtenu in zip(ids, obtenus):
            with self.subTest(article=article_id):
                self.assertEqual(comparable(obtenu), comparable(self.calcul.composant(article_id)))
        # Le calcul n'est pas vide sur la démo : consommations, médianes, montage par liste et par consommation.
        self.assertTrue(any(c["consommations"] for c in obtenus))
        self.assertTrue(any(r["intervalleMedianJours"] is not None for c in obtenus for r in c["remplacements"]))
        sources = {m["source"] for c in obtenus for m in c["montage"]}
        self.assertIn("liste", sources)
        self.assertTrue(sources & {"les deux", "consommation"})
        self.assertEqual(self.requetes_reseau(), [])

    def test_mode_de_chaque_cause_egal_au_calcul_python(self):
        # Causes de codes_defaillance et causes saisies dans les OT.
        codes = sorted({code for famille, code in self.calcul.libelles if famille == "cause"}
                       | {ot["cause_code"].strip() for ot in self.calcul.ordres if ot["cause_code"].strip()})
        self.assertGreater(len(codes), 5)
        obtenus = self.modes(codes)
        for code, obtenu in zip(codes, obtenus):
            with self.subTest(cause=code):
                self.assertEqual(comparable(obtenu), comparable(self.calcul.mode(code)))
        self.assertTrue(any(m["cas"] > 0 and m["remedes"] and len(m["equipements"]) > 1 for m in obtenus))

    def test_page_d_article_et_catalogue_de_la_demo(self):
        page = self.page_wiki("ART-0001")
        self.assertEqual((page["id"], page["type"]), ("ART-0001", "composant"))
        self.assertEqual(comparable(page["calcul"]), comparable(self.calcul.composant("ART-0001")))
        self.assertEqual(page["titre"], self.calcul.articles["ART-0001"]["designation"].strip())
        catalogue = self.page.evaluate("Wiki.catalogue()")
        attendues = {e["id"]: (" — ".join(filter(None, [e["repere"].strip(), e["designation"].strip()])), "équipement")
                     for e in self.calcul.equipements}
        attendues.update({a: (article["designation"].strip(), "composant") for a, article in self.calcul.articles.items()})
        self.assertLessEqual(len(attendues), 400)
        par_id = {e["id"]: (e["titre"], e["type"]) for e in catalogue}
        self.assertEqual({k: par_id.get(k) for k in attendues}, attendues)
        self.assertEqual(self.requetes_reseau(), [])


class TestBaseEssai(CasCalculs):
    """Base construite pour les cas limites : valeurs à la main et égalité avec le calcul Python."""

    def setUp(self):
        super().setUp()
        self.charger(BASE)

    # -- couches calculées -----------------------------------------------------------------------

    def test_composants_et_modes_egaux_au_calcul_python(self):
        calcul = CalculWiki(BASE)
        for article_id, obtenu in zip(ARTICLES_BASE + ["ART-9999"], self.composants(ARTICLES_BASE + ["ART-9999"])):
            with self.subTest(article=article_id):
                self.assertEqual(comparable(obtenu), comparable(calcul.composant(article_id)))
        for code, obtenu in zip(CAUSES_BASE, self.modes(CAUSES_BASE)):
            with self.subTest(cause=code):
                self.assertEqual(comparable(obtenu), comparable(calcul.mode(code)))
        self.assertEqual(self.modes(["", "  "]), [None, None])

    def test_article_stock_et_consommations(self):
        roulement = self.composants(["ART-0001"])[0]
        # Stock d'après les mouvements (20 − 1 − 2 − 3 + 1 − 2 + 2 − 1 − 1 − 1 − 1 − 1 − 1 − 1 − 1 − 2 + 5 − 1),
        # pas la colonne du fichier (99).
        self.assertEqual(roulement["article"], {"id": "ART-0001", "reference": "ROU-6205", "designation": "Roulement 6205",
                                                "fabricant": "Rouloran", "refFabricant": "6205-2RS",
                                                "emplacement": "A1-02", "stock": 9})
        # 0004 (sorti puis rendu), 0005 (en cours), 0006 (annulé) absents ; 0003 : 3 − 1 = 2 ; préventif 0012
        # compté ; même jour (05/05) : par identifiant d'OT.
        self.assertEqual([(c["otId"][-4:], c["date"], c["equipementId"], c["quantite"]) for c in roulement["consommations"]], [
            ("0021", "2026-05-05", "EQ-0004", 1), ("0022", "2026-05-05", "EQ-0004", 2),
            ("0020", "2026-04-20", "EQ-0003", 1), ("0013", "2026-04-17", "EQ-0005", 1),
            ("0012", "2026-04-05", "EQ-0005", 1), ("0011", "2026-03-31", "EQ-0005", 1),
            ("0010", "2026-03-01", "EQ-0005", 1), ("0003", "2026-02-20", "EQ-0001", 2),
            ("0002", "2026-01-20", "EQ-0001", 2), ("0001", "2026-01-10", "EQ-0001", 1)])

    def test_montage_liste_et_consommation(self):
        roulement, garniture, joint, filtre = self.composants(ARTICLES_BASE)
        self.assertEqual(roulement["montage"], [
            {"equipementId": "EQ-0005", "repere": "BR-01", "quantite": "4", "source": "les deux"},
            {"equipementId": "EQ-0004", "repere": "CP-01", "quantite": "", "source": "consommation"},
            {"equipementId": "EQ-0003", "repere": "CV-01", "quantite": "", "source": "consommation"},
            {"equipementId": "EQ-0001", "repere": "PO-01", "quantite": "2", "source": "les deux"},
            {"equipementId": "EQ-0002", "repere": "PO-02", "quantite": "1", "source": "liste"}])
        # Monté, jamais consommé (l'équipement inconnu EQ-0099 est écarté).
        self.assertEqual(garniture["montage"], [
            {"equipementId": "EQ-0001", "repere": "PO-01", "quantite": "1", "source": "liste"},
            {"equipementId": "EQ-0002", "repere": "PO-02", "quantite": "1.5", "source": "liste"}])
        self.assertEqual((garniture["consommations"], garniture["remplacements"]), ([], []))
        # Consommé, jamais dans la liste (dont un préventif).
        self.assertEqual([(m["repere"], m["quantite"], m["source"]) for m in joint["montage"]],
                         [("PO-01", "", "consommation"), ("PO-02", "", "consommation")])
        self.assertEqual([(c["otId"][-4:], c["quantite"]) for c in joint["consommations"]], [("0030", 1), ("0001", 0.5)])
        # Ni liste ni consommation (la sortie sur un OT inconnu ne compte pas).
        self.assertEqual((filtre["montage"], filtre["consommations"], filtre["remplacements"]), ([], [], []))
        self.assertEqual(filtre["article"]["stock"], -1)

    def test_remplacements_et_medianes(self):
        roulement, _, joint, _ = self.composants(ARTICLES_BASE)
        self.assertEqual(roulement["remplacements"], [
            # 01/03, 31/03, 05/04, 17/04 : écarts 30, 5, 12 → triés 5, 12, 30 → 12.
            {"equipementId": "EQ-0005", "repere": "BR-01", "nombre": 4, "intervalleMedianJours": 12},
            # Deux OT le même jour : écart 0.
            {"equipementId": "EQ-0004", "repere": "CP-01", "nombre": 2, "intervalleMedianJours": 0},
            # Un seul remplacement : null.
            {"equipementId": "EQ-0003", "repere": "CV-01", "nombre": 1, "intervalleMedianJours": None},
            # 10/01, 20/01, 20/02 : écarts 10 et 31 (nombre pair) → 20,5 ; 0004 (rendu) ne compte pas.
            {"equipementId": "EQ-0001", "repere": "PO-01", "nombre": 3, "intervalleMedianJours": 20.5}])
        self.assertEqual([(r["repere"], r["nombre"], r["intervalleMedianJours"]) for r in joint["remplacements"]],
                         [("PO-01", 1, None), ("PO-02", 1, None)])

    def test_modes_cas_equipements_remedes(self):
        c01, c02, c03, c04, c09 = self.modes(CAUSES_BASE)
        # C01 : 0001, 0002, 0003 (PO-01), 0013 (BR-01), 0021 (CP-01) ; 0005 en cours, 0006 annulé, 0012
        # préventif ignorés.
        self.assertEqual(c01, {
            "cause": {"code": "C01", "libelle": "Garniture usée"}, "cas": 5,
            "equipements": [{"equipementId": "EQ-0001", "repere": "PO-01", "cas": 3},
                            {"equipementId": "EQ-0005", "repere": "BR-01", "cas": 1},
                            {"equipementId": "EQ-0004", "repere": "CP-01", "cas": 1}],
            "remedes": [{"code": "R01", "libelle": "Remplacement de la pièce", "fois": 3},
                        {"code": "R02", "libelle": "Réglage", "fois": 1},
                        {"code": "R03", "libelle": "Nettoyage", "fois": 1}]})
        # C02 : 3 cas dont 2 sans remède (non comptés dans les remèdes).
        self.assertEqual((c02["cas"], c02["equipements"], c02["remedes"]), (3, [
            {"equipementId": "EQ-0005", "repere": "BR-01", "cas": 2},
            {"equipementId": "EQ-0001", "repere": "PO-01", "cas": 1}],
            [{"code": "R01", "libelle": "Remplacement de la pièce", "fois": 1}]))
        self.assertEqual(c03, {"cause": {"code": "C03", "libelle": "Desserrage"}, "cas": 0, "equipements": [], "remedes": []})
        # C04 : cause sans remède ; l'OT de l'équipement inconnu compte dans les cas, pas dans la liste.
        self.assertEqual((c04["cas"], c04["equipements"], c04["remedes"]),
                         (2, [{"equipementId": "EQ-0003", "repere": "CV-01", "cas": 1}], []))
        # Code absent de codes_defaillance : libellé = code.
        self.assertEqual((c09["cause"], c09["cas"], c09["remedes"]),
                         ({"code": "C09", "libelle": "C09"}, 1, [{"code": "R02", "libelle": "Réglage", "fois": 1}]))

    # -- pages -------------------------------------------------------------------------------------

    def test_page_d_equipement_par_EQ_et_par_WP(self):
        page = self.page_wiki("EQ-0001")
        calcul = self.page.evaluate("(maintenant) => Wiki.pageEquipement('EQ-0001', { maintenant })", MAINTENANT)
        self.assertEqual(page["calcul"], calcul)
        self.assertEqual({k: v for k, v in page.items() if k not in ("calcul", "retours")}, {
            "id": "EQ-0001", "type": "équipement", "titre": "PO-01 — Pompe de process A", "entete": None,
            "mere": None, "sousPages": [], "texte": TEXTE_PO01, "origine": "IA", "modele": "claude-sonnet-5-5", "validePar": "Responsable fictif",
            "valideLe": "2026-10-01 10:00", "liens": ["WP-0004", "ART-0001"], "contradictions": [], "enAttente": [],
            "pageId": "WP-0001"})
        # La ligne WP-0001 rend la même page (identifiant canonique EQ-0001).
        self.assertEqual(self.page_wiki("WP-0001"), page)
        # Équipement sans ligne de wiki : texte vide.
        sans_texte = self.page_wiki("EQ-0002")
        self.assertEqual((sans_texte["id"], sans_texte["titre"], sans_texte["texte"], sans_texte["origine"],
                          sans_texte["liens"], sans_texte["pageId"], sans_texte["retours"]),
                         ("EQ-0002", "PO-02 — Pompe de process B", "", "", [], "", []))

    def test_page_d_article_par_ART_et_par_WP(self):
        calcul = CalculWiki(BASE)
        page = self.page_wiki("ART-0001")
        self.assertEqual((page["id"], page["type"], page["titre"], page["pageId"], page["origine"], page["liens"]),
                         ("ART-0001", "composant", "Roulement 6205", "WP-0002", "manuel", ["EQ-0001"]))
        self.assertEqual(comparable(page["calcul"]), comparable(calcul.composant("ART-0001")))
        self.assertEqual(self.page_wiki("WP-0002"), page)
        garniture = self.page_wiki("ART-0002")
        self.assertEqual((garniture["titre"], garniture["texte"], garniture["pageId"], garniture["entete"]),
                         ("Garniture mécanique 35 mm", "", "", None))
        self.assertEqual(comparable(garniture["calcul"]), comparable(calcul.composant("ART-0002")))

    def test_pages_de_mode_ancre_et_libre_et_de_composant_libre(self):
        calcul = CalculWiki(BASE)
        ancre = self.page_wiki("WP-0003")
        self.assertEqual((ancre["id"], ancre["type"], ancre["titre"], ancre["pageId"], ancre["entete"]),
                         ("WP-0003", "mode", "Usure de garniture", "WP-0003", None))
        self.assertEqual(comparable(ancre["calcul"]), comparable(calcul.mode("C01")))
        # Mode ancré sans texte : sa couche quand même.
        self.assertEqual(self.page_wiki("WP-0012")["calcul"]["cas"], 3)
        libre = self.page_wiki("WP-0004")
        self.assertEqual((libre["id"], libre["type"], libre["titre"], libre["calcul"], libre["liens"]),
                         ("WP-0004", "mode", "Cavitation", None, ["ART-0001", "WP-0005"]))
        composant_libre = self.page_wiki("WP-0005")
        self.assertEqual((composant_libre["id"], composant_libre["type"], composant_libre["calcul"],
                          composant_libre["entete"]), ("WP-0005", "composant", None, None))
        # Page d'équipement dont l'équipement a disparu : page du wiki sans couche calculée.
        disparue = self.page_wiki("WP-0013")
        self.assertEqual((disparue["id"], disparue["type"], disparue["titre"], disparue["calcul"]),
                         ("WP-0013", "équipement", "Ancienne presse", None))

    def test_entete_des_savoir_faire(self):
        rattache_equipement = self.page_wiki("WP-0006")
        self.assertEqual((rattache_equipement["type"], rattache_equipement["calcul"]), ("savoir-faire", None))
        self.assertEqual(rattache_equipement["entete"], {
            "consignation": {"texte": CONSIGNATION, "document": DOCUMENT},
            "equipements": [{"equipementId": "EQ-0001", "repere": "PO-01"}], "phrase": PHRASE})
        montes = [{"equipementId": e, "repere": r} for e, r in (
            ("EQ-0005", "BR-01"), ("EQ-0004", "CP-01"), ("EQ-0003", "CV-01"), ("EQ-0001", "PO-01"), ("EQ-0002", "PO-02"))]
        # Rattaché à un article, ou à la page de son composant : pas de consignation, les équipements où il est monté.
        for identifiant in ("WP-0007", "WP-0009"):
            with self.subTest(page=identifiant):
                self.assertEqual(self.page_wiki(identifiant)["entete"],
                                 {"consignation": None, "equipements": montes, "phrase": PHRASE})
        # Rattaché à un composant libre : ni consignation ni équipement.
        self.assertEqual(self.page_wiki("WP-0008")["entete"], {"consignation": None, "equipements": [], "phrase": PHRASE})
        # Équipement sans consignation : null, l'équipement reste.
        self.assertEqual(self.page_wiki("WP-0011")["entete"], {
            "consignation": None, "equipements": [{"equipementId": "EQ-0002", "repere": "PO-02"}], "phrase": PHRASE})
        self.assertEqual(self.page.evaluate("Wiki.PHRASE_SAVOIR_FAIRE"), PHRASE)

    def test_consignation_identique_a_la_fiche(self):
        resultat = self.page.evaluate("""() => {
          const fiche = Donnees.trouver('equipements', 'EQ-0001');
          return { fiche: { texte: fiche.consignation, document: fiche.document },
                   entete: Wiki.page('WP-0006').entete.consignation,
                   equipement: Wiki.pageEquipement('EQ-0001').consignation };
        }""")
        self.assertEqual(resultat["entete"], resultat["fiche"])
        self.assertEqual(resultat["entete"], resultat["equipement"])
        self.assertEqual(resultat["entete"]["texte"], CONSIGNATION)
        self.assertEqual(resultat["entete"]["texte"].encode("utf-8"), CONSIGNATION.encode("utf-8"))
        self.assertTrue(resultat["entete"]["texte"].startswith("  1."))
        self.assertIn(CRLF + CRLF + TAB, resultat["entete"]["texte"])

    def test_identifiants_inconnus_et_page_archivee(self):
        for identifiant in ("EQ-9999", "ART-9999", "WP-9999", "WP-0010", "", "OT-2026-0001", "C01"):
            with self.subTest(identifiant=identifiant):
                self.assertIsNone(self.page_wiki(identifiant))

    def test_retours(self):
        def retours(identifiant):
            return [(r["id"], r["titre"], r["type"]) for r in self.page_wiki(identifiant)["retours"]]
        # EQ-0001 : par son identifiant (WP-0002, WP-0006) et par son WP-0001 (WP-0003) ; WP-0010 archivée ignorée.
        self.assertEqual(retours("EQ-0001"), [
            ("WP-0006", "Changer la garniture de PO-01", "savoir-faire"), ("ART-0001", "Roulement 6205", "composant"),
            ("WP-0003", "Usure de garniture", "mode")])
        self.assertEqual(retours("ART-0001"), [
            ("WP-0004", "Cavitation", "mode"), ("WP-0007", "Monter un roulement 6205", "savoir-faire"),
            ("EQ-0001", "PO-01 — Pompe de process A", "équipement")])
        self.assertEqual(retours("WP-0002"), retours("ART-0001"))
        self.assertEqual(retours("WP-0004"), [("WP-0013", "Ancienne presse", "équipement"),
                                              ("EQ-0001", "PO-01 — Pompe de process A", "équipement")])
        self.assertEqual(retours("WP-0005"), [("WP-0004", "Cavitation", "mode"),
                                              ("WP-0008", "Retendre une courroie", "savoir-faire")])
        self.assertEqual(retours("ART-0003"), [])

    def test_crochets_de_wiki_journal(self):
        resultat = self.page.evaluate("""() => {
          Wiki.contradictionsDe = (page, options) => [{ page: page.id, pageId: page.pageId, type: page.type,
            titre: page.titre, profil: options.profil }];
          Wiki.enAttenteDe = (page, options) => [{ page: page.id, profil: options.profil }];
          try {
            return { equipement: Wiki.page('EQ-0001', { profil: 'responsable' }),
                     savoirFaire: Wiki.page('WP-0008', { profil: 'technicien' }) };
          } finally {
            delete Wiki.contradictionsDe;
            delete Wiki.enAttenteDe;
          }
        }""")
        self.assertEqual(resultat["equipement"]["contradictions"], [{
            "page": "EQ-0001", "pageId": "WP-0001", "type": "équipement", "titre": "PO-01 — Pompe de process A",
            "profil": "responsable"}])
        self.assertEqual(resultat["equipement"]["enAttente"], [{"page": "EQ-0001", "profil": "responsable"}])
        self.assertEqual(resultat["savoirFaire"]["enAttente"], [{"page": "WP-0008", "profil": "technicien"}])
        sans = self.page_wiki("EQ-0001")
        self.assertEqual((sans["contradictions"], sans["enAttente"]), ([], []))

    def test_catalogue(self):
        catalogue = [(e["id"], e["titre"], e["type"]) for e in self.page.evaluate("Wiki.catalogue()")]
        self.assertEqual(catalogue, [
            # Pages qui ont un texte (EQ-0001 et ART-0001 par leur ligne ancrée), par titre.
            ("WP-0011", "Amorcer PO-02", "savoir-faire"), ("WP-0013", "Ancienne presse", "équipement"),
            ("WP-0004", "Cavitation", "mode"), ("WP-0006", "Changer la garniture de PO-01", "savoir-faire"),
            ("WP-0005", "Courroie crantée", "composant"), ("WP-0009", "Graisser un roulement", "savoir-faire"),
            ("WP-0007", "Monter un roulement 6205", "savoir-faire"),
            ("EQ-0001", "PO-01 — Pompe de process A", "équipement"),
            ("WP-0008", "Retendre une courroie", "savoir-faire"), ("ART-0001", "Roulement 6205", "composant"),
            ("WP-0003", "Usure de garniture", "mode"),
            # Puis les autres (WP-0012 sans texte ; WP-0001, WP-0002 ancrées, WP-0010 archivée : absentes).
            ("EQ-0005", "BR-01 — Broyeur", "équipement"), ("WP-0012", "Bouchage d'aspiration", "mode"),
            ("EQ-0004", "CP-01 — Compresseur", "équipement"), ("EQ-0003", "CV-01 — Convoyeur", "équipement"),
            ("ART-0004", "Filtre à huile", "composant"), ("ART-0002", "Garniture mécanique 35 mm", "composant"),
            ("ART-0003", "Joint de bride", "composant"), ("EQ-0002", "PO-02 — Pompe de process B", "équipement")])
        # Chaque entrée du catalogue s'ouvre avec Wiki.page, sous le même identifiant, titre et type.
        pages = self.page.evaluate("Wiki.catalogue().map((e) => { const p = Wiki.page(e.id); return [p.id, p.titre, p.type]; })")
        self.assertEqual([tuple(p) for p in pages], catalogue)

    def test_aucune_ecriture_ni_appel_reseau(self):
        resultat = self.page.evaluate("""(maintenant) => {
          const photo = () => JSON.stringify(Schema.nomsTables().map((nom) => [nom, Donnees.lignes(nom)]));
          const avant = photo();
          let ecritures = 0;
          const modifier = Donnees.modifier;
          Donnees.modifier = async (...arguments_) => { ecritures += 1; return modifier(...arguments_); };
          let pages = 0;
          try {
            const ids = ['equipements', 'articles', 'wiki_pages'].flatMap((nom) => Donnees.lignes(nom).map((l) => l.id));
            ids.concat(['EQ-9999', 'WP-9999']).forEach((id) => { if (Wiki.page(id, { maintenant })) pages += 1; });
            Donnees.lignes('articles').forEach((a) => Wiki.pageComposant(a.id));
            ['C01', 'C02', 'C03', 'C04', 'C09'].forEach((code) => Wiki.pageMode(code));
            Wiki.catalogue();
          } finally {
            Donnees.modifier = modifier;
          }
          return { identique: photo() === avant, ecritures, pages };
        }""", MAINTENANT)
        # 5 équipements + 4 articles + 12 lignes actives (WP-0010 archivée).
        self.assertEqual(resultat, {"identique": True, "ecritures": 0, "pages": 21})
        self.assertEqual(self.requetes_reseau(), [])


class TestSousPages(CasCalculs):
    """Sous-pages (§20.3, §20.4, T131) : mère, sous-pages de la mère (actives, ordre alphabétique français), pas de
    couche calculée, en-tête d'une sous-page d'équipement = la consignation de la fiche de l'équipement de sa mère."""

    def setUp(self):
        super().setUp()
        self.charger(dict(BASE, wiki_pages=table_csv(ENTETE_WIKI, LIGNES_WIKI + SOUS_PAGES)))

    def sous_pages(self, identifiant):
        return [(s["id"], s["titre"]) for s in self.page_wiki(identifiant)["sousPages"]]

    def test_mere_et_sous_pages_par_titre_archivee_exclue(self):
        # « Étanchéité » avant « garniture » (ordre français ; l'ordre des caractères mettrait « É » après « g ») ;
        # WP-0022 archivée n'est pas listée ; la ligne WP-0001 de la mère rend les mêmes sous-pages.
        attendues = [("WP-0021", "PO-01 — Étanchéité"), ("WP-0020", "PO-01 — garniture")]
        self.assertEqual(self.sous_pages("EQ-0001"), attendues)
        self.assertEqual(self.sous_pages("WP-0001"), attendues)
        # Composant, mode, savoir-faire : leurs sous-pages ; un savoir-faire rattaché à un composant n'en est pas une.
        self.assertEqual(self.sous_pages("ART-0001"), [("WP-0023", "Roulement 6205 — montage")])
        self.assertEqual(self.sous_pages("WP-0004"), [("WP-0024", "Cavitation — bruit")])
        self.assertEqual(self.sous_pages("WP-0006"), [("WP-0025", "Changer la garniture de PO-01 — remontage")])
        for identifiant in ("WP-0003", "WP-0005", "EQ-0002", "ART-0002", "WP-0020"):
            with self.subTest(page=identifiant):
                self.assertEqual(self.sous_pages(identifiant), [])
        meres = {identifiant: self.page_wiki(identifiant)["mere"] for identifiant in (
            "WP-0020", "WP-0021", "WP-0023", "WP-0024", "WP-0025", "WP-0026", "WP-0027")}
        self.assertEqual(meres, {
            "WP-0020": {"id": "EQ-0001", "titre": "PO-01 — Pompe de process A"},
            "WP-0021": {"id": "EQ-0001", "titre": "PO-01 — Pompe de process A"},
            "WP-0023": {"id": "ART-0001", "titre": "Roulement 6205"},
            "WP-0024": {"id": "WP-0004", "titre": "Cavitation"},
            "WP-0025": {"id": "WP-0006", "titre": "Changer la garniture de PO-01"},
            "WP-0026": {"id": "WP-0013", "titre": "Ancienne presse"},       # mère dont l'équipement a disparu
            "WP-0027": {"id": "WP-0010", "titre": "Ancienne page"},         # mère archivée : la sous-page reste une page
        })
        # Pas de mère : page ordinaire, savoir-faire rattaché à un article ou à un composant, mère absente.
        for identifiant in ("EQ-0001", "WP-0003", "WP-0007", "WP-0009", "WP-0028"):
            with self.subTest(page=identifiant):
                self.assertIsNone(self.page_wiki(identifiant)["mere"])
        self.assertIsNone(self.page_wiki("WP-0022"))                       # sous-page archivée : introuvable

    def test_pas_de_couche_calculee_et_en_tete_repris_de_la_mere(self):
        for identifiant, type_ in (("WP-0020", "équipement"), ("WP-0023", "composant"), ("WP-0024", "mode"),
                                   ("WP-0025", "savoir-faire"), ("WP-0026", "équipement")):
            with self.subTest(page=identifiant):
                page = self.page_wiki(identifiant)
                self.assertEqual((page["id"], page["type"], page["calcul"], page["pageId"]), (identifiant, type_, None, identifiant))
        # Sous-page d'équipement : la consignation de l'équipement de sa mère, telle quelle, et la phrase de Prévo.
        self.assertEqual(self.page_wiki("WP-0020")["entete"], {
            "consignation": {"texte": CONSIGNATION, "document": DOCUMENT},
            "equipements": [{"equipementId": "EQ-0001", "repere": "PO-01"}], "phrase": PHRASE_SOUS_PAGE})
        self.assertEqual(self.page.evaluate("Wiki.PHRASE_SOUS_PAGE"), PHRASE_SOUS_PAGE)
        resultat = self.page.evaluate("""() => {
          const fiche = Donnees.trouver('equipements', 'EQ-0001');
          return { fiche: { texte: fiche.consignation, document: fiche.document }, sousPage: Wiki.page('WP-0021').entete.consignation,
                   equipement: Wiki.pageEquipement('EQ-0001').consignation };
        }""")
        self.assertEqual(resultat["sousPage"], resultat["fiche"])
        self.assertEqual(resultat["sousPage"], resultat["equipement"])
        self.assertEqual(resultat["sousPage"]["texte"].encode("utf-8"), CONSIGNATION.encode("utf-8"))
        # Mère dont l'équipement a disparu : ni consignation ni équipement, la phrase reste.
        self.assertEqual(self.page_wiki("WP-0026")["entete"], {"consignation": None, "equipements": [], "phrase": PHRASE_SOUS_PAGE})
        # Sous-page de savoir-faire : l'en-tête de sa mère (même consignation, même phrase), que la mère soit rattachée
        # à l'équipement par equipement_id (WP-0006) ou par rattache_a vers la page de l'équipement (WP-0029).
        en_tete_po01 = {"consignation": {"texte": CONSIGNATION, "document": DOCUMENT},
                        "equipements": [{"equipementId": "EQ-0001", "repere": "PO-01"}], "phrase": PHRASE}
        for sous_page, mere in (("WP-0025", "WP-0006"), ("WP-0030", "WP-0029")):
            with self.subTest(sous_page=sous_page):
                self.assertEqual(self.page_wiki(mere)["entete"], en_tete_po01)
                self.assertEqual(self.page_wiki(sous_page)["entete"], en_tete_po01)
                self.assertEqual(self.page_wiki(sous_page)["mere"]["id"], mere)
        self.assertIsNone(self.page_wiki("WP-0029")["mere"])               # rattaché à une page d'un autre type
        self.assertIsNone(self.page_wiki("WP-0023")["entete"])
        self.assertIsNone(self.page_wiki("WP-0024")["entete"])
        # Mère absente : ce n'est pas une sous-page (rien ne dit son type) ; page d'équipement sans couche.
        absente = self.page_wiki("WP-0028")
        self.assertEqual((absente["calcul"], absente["entete"], absente["mere"]), (None, None, None))

    def test_catalogue_comprend_les_sous_pages_actives(self):
        catalogue = {e["id"]: (e["titre"], e["type"]) for e in self.page.evaluate("Wiki.catalogue()")}
        for ligne in SOUS_PAGES:
            with self.subTest(page=ligne[0]):
                self.assertEqual(catalogue.get(ligne[0]), None if ligne[-1] == "archivée" else (ligne[2], ligne[1]))
        self.assertEqual(self.requetes_reseau(), [])


class TestCatalogueAuPlafond(CasCalculs):
    """434 pages possibles : catalogueMax (400) au plus, les pages qui ont un texte d'abord."""

    def test_catalogue_plafonne_pages_avec_texte_en_tete(self):
        equipements = table_csv("id;repere;designation;statut;actif",
                                [f"EQ-{n:04d};'M-{n:02d};Machine {n:02d};en service;1" for n in range(1, 11)])
        articles = table_csv("id;reference;designation;actif",
                             [f"ART-{n:04d};'REF-{n:03d};Article {n:03d};1" for n in range(1, 421)])
        pages = table_csv(ENTETE_WIKI, [
            page_wiki("WP-0001", "composant", "Article 420", "## Défaillances" + NL + "- Casse [OT-2026-0001]",
                      article="ART-0420"),
            page_wiki("WP-0002", "mode", "Zz page 2", "## Causes" + NL + "- Usure [OT-2026-0001]"),
            page_wiki("WP-0003", "savoir-faire", "Zz page 1", "## Étapes" + NL + "- Faire [OT-2026-0001]"),
            page_wiki("WP-0004", "composant", "Zz page 3", "## Équivalences" + NL + "- Autre [OT-2026-0001]"),
            page_wiki("WP-0005", "mode", "Aaa vide"),
        ])
        self.charger({"equipements": equipements, "articles": articles, "wiki_pages": pages,
                      "parametres": table_csv("cle;valeur", ["version_schema;3"])})
        catalogue = [(e["id"], e["titre"], e["type"]) for e in self.page.evaluate("Wiki.catalogue()")]
        avec_texte = [("ART-0420", "Article 420", "composant"), ("WP-0003", "Zz page 1", "savoir-faire"),
                      ("WP-0002", "Zz page 2", "mode"), ("WP-0004", "Zz page 3", "composant")]
        autres = sorted([("WP-0005", "Aaa vide", "mode")]
                        + [(f"ART-{n:04d}", f"Article {n:03d}", "composant") for n in range(1, 420)]
                        + [(f"EQ-{n:04d}", f"M-{n:02d} — Machine {n:02d}", "équipement") for n in range(1, 11)],
                        key=lambda e: (e[1], e[0]))
        self.assertEqual(len(avec_texte) + len(autres), 434)
        self.assertEqual(len(catalogue), 400)
        self.assertEqual(catalogue, (avec_texte + autres)[:400])
        self.assertEqual(catalogue[4], ("WP-0005", "Aaa vide", "mode"))
        self.assertNotIn("EQ-0001", [e[0] for e in catalogue])         # les machines viennent après les articles
        self.assertEqual(self.requetes_reseau(), [])


if __name__ == "__main__":
    unittest.main()
