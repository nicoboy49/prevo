"""Encyclopédie de l'atelier (refonte 2 du lot 6, ARCHITECTURE.md §20.12 ; D113, D114 ; tâche T135).

Wiki.entite, Wiki.listeEntites, Wiki.accueilEncyclopedie, Wiki.ordreInterventions et Wiki.references, comparés au calcul
Python indépendant de tests/calcul_wiki.py (qui relit les CSV) :
    - jeu de démo (donnees/demo, lu tel quel), trois profils : toutes les machines, pannes, articles et techniciens,
      quelques interventions (dont les ouvertes et l'annulée), les six listes, l'accueil ; le stock reconstitué par les
      mouvements est égal à la colonne articles.stock (écart rapporté article par article) ; visibilité (D114) ;
    - base d'essai construite ici pour les cas limites, valeurs attendues écrites à la main ET égalité avec le calcul
      Python : ordre des interventions (en cours, planifiés, sans date prévue, annulé, clôturés le même jour), pannes
      comptées sur les seuls OT correctifs clôturés (code sans cas, symptôme d'un préventif : pas de page), code à
      caractères spéciaux, stock dans le temps (retour qui remonte le stock, inventaire qui fixe la quantité, sortie sans
      OT, rupture qui dure encore, article jamais sorti, sortie sur un OT inconnu), habilitations (échue, à renouveler le
      jour même et à 90 jours, valide, sans échéance, illisible), sous-ensembles (petit-fils, parent inconnu, cycle),
      intervention en lecture seule (demande d'origine, techniciens, temps, opérations, pièces nettes, « Cité dans le
      wiki », motifs d'attente et d'annulation — T137), savoir-faire (rattachement direct, par la page de la machine,
      sous-page, libre ; archivé, mode, ancrage disparu → null), textes et références (rubriques remises dans l'ordre du
      type ; « À trancher » numéroté d'abord, en tête de la page — T137), identifiants
      inconnus → null, suivi du wiki (mêmes définitions que Wiki.compteurs) ;
    - pureté : aucune écriture, aucun appel réseau ; durée d'une page sur le jeu de charge (D101 : moins de 500 ms).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_wiki_entites.py" -v
"""
import csv
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from calcul_wiki import CalculWiki, nombre
from commun import CasNavigateur, charger_scripts

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_DEMO = RACINE / "donnees" / "demo"
SCRIPTS = [
    "js/lib/papaparse.min.js", "js/schema.js", "js/donnees.js", "js/stockage-demo.js",
    "js/modules/causes-frequentes.js", "js/modules/indicateurs-regles.js", "js/modules/equipe-regles.js",
    "js/modules/wiki-regles.js", "js/modules/wiki-calculs.js", "js/modules/wiki-entites.js",
]
MAINTENANT = "2026-10-19 10:00"
PROFILS = ("demandeur", "technicien", "responsable")
NL = chr(10)
BUDGET_PAGE_MS = 500                 # D101


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


def sans_wiki_page(entite):
    """Entité d'un savoir-faire sans ce qui vient de Wiki.page (en-tête, mère, sous-pages), comparé à part."""
    if not entite or entite["type"] != "savoir-faire":
        return entite
    return dict(entite, sections={"rattachement": entite["sections"]["rattachement"]})


def faits(entite):
    return {f["libelle"]: f["valeur"] for f in entite["faits"]}


def ids(elements):
    return [e["id"] for e in elements]


# ---------------------------------------------------------------------------------------------------
# Base d'essai
# ---------------------------------------------------------------------------------------------------

LOCALISATIONS = table_csv("id;libelle;parent_id;type", [
    "LOC-0001;Usine;;site", "LOC-0002;Atelier A;LOC-0001;atelier", "LOC-0003;Ligne 1;LOC-0002;ligne"])

EQUIPEMENTS = table_csv("id;repere;designation;localisation_id;parent_id;marque;modele;num_serie;date_mes;criticite;statut;"
                        "habilitation_requise;consignation;document;actif", [
    "EQ-0001;'PO-01;Pompe A;LOC-0003;;Hydro;HC 50;'SN-1;2020-05-04;A;en service;BR;Couper Q1 et cadenasser.;;1",
    "EQ-0002;'PO-01.M;Moteur de PO-01;LOC-0003;EQ-0001;;;;;B;en service;;;;1",          # sous-ensemble
    "EQ-0003;'PO-01.M.R;Roulement moteur;LOC-0003;EQ-0002;;;;;C;en service;;;;1",       # petit-fils
    "EQ-0004;'CV-01;Convoyeur;LOC-0002;;;;;;B;arrêt;;;;1",
    "EQ-0005;'XA-01;Cycle A;;EQ-0006;;;;;C;en service;;;;1",                            # cycle de parents
    "EQ-0006;'XB-01;Cycle B;;EQ-0005;;;;;C;en service;;;;1",
    "EQ-0007;'ZZ-01;Orphelin;LOC-0002;EQ-0099;;;;;C;rebut;;;;0",                         # parent inconnu
])

CODES = table_csv("id;famille;code;libelle", [
    "CD-0001;symptôme;S01;Fuite", "CD-0002;symptôme;S02;Bruit", "CD-0003;symptôme;S03;Blocage",
    "CD-0004;symptôme;S04;Vibration", "CD-0005;symptôme;S 05/A;Défaut d'étanchéité",
    "CD-0006;cause;C01;Usure", "CD-0007;cause;C02;Desserrage",
    "CD-0008;remède;R01;Remplacement", "CD-0009;remède;R02;Resserrage",
])

TECHNICIENS = table_csv("id;nom;prenom;metier;taux_horaire;capacite_h_semaine;actif", [
    "TEC-0001;Martin;Paul;Mécanicien;40;35;1", "TEC-0002;Durand;Léa;Électricienne;45.5;30;1",
    "TEC-0003;Petit;Jean;Polyvalent;38;35;0"])

HABILITATIONS = table_csv("id;technicien_id;intitule;date_obtention;date_echeance", [
    "HAB-0001;TEC-0001;BR;2024-01-10;2026-10-01",        # échue, mais renouvelée par HAB-0004 : ne compte plus
    "HAB-0002;TEC-0001;B1V;2024-01-10;2026-12-18",       # aujourd'hui + 60 jours : à renouveler (RG8)
    "HAB-0003;TEC-0001;H0V;2024-01-10;2026-12-19",       # aujourd'hui + 61 jours : valide
    "HAB-0004;TEC-0001;br ;2026-10-02;2029-10-02",       # renouvellement (même intitulé, casse et espaces ignorés) : valide
    "HAB-0005;TEC-0002;CACES;2025-01-01;",               # sans échéance : valide
    "HAB-0006;TEC-0002;H0V;2025-01-01;2026-02-30",       # échéance illisible : échue
    "HAB-0007;TEC-0002;B2V;2025-01-01;2026-10-19",       # le jour même : à renouveler
    "HAB-0008;TEC-0002;SST;2026-11-02;2028-11-02",       # obtention future : pas encore valable
    "HAB-0009;TEC-0003;BR;2024-01-10;2026-01-10",        # échue, technicien inactif : hors de l'accueil
])

ENTETE_OT = ("id;origine;di_id;equipement_id;type;priorite;statut;titre;travail_a_faire;date_creation;date_prevue;technicien_id;"
             "date_debut;date_fin;arret_production;duree_arret_h;symptome_code;cause_code;remede_code;compte_rendu;"
             "date_cloture_tech;date_cloture_admin;astuce;motif_attente;motif_annulation")


def ot(id_, equipement, type_, statut, titre, creation, prevue="", technicien="", debut="", fin="", symptome="", cause="",
       remede="", di="", arret="0", duree="", compte_rendu="", cloture_tech="", cloture_admin="", travail="", astuce="",
       motif_attente="", motif_annulation=""):
    return [id_, "manuel", di, equipement, type_, "P2", statut, titre, travail, creation, prevue, technicien, debut, fin,
            arret, duree, symptome, cause, remede, compte_rendu, cloture_tech, cloture_admin, astuce, motif_attente,
            motif_annulation]


ORDRES = table_csv(ENTETE_OT, [
    ot("OT-2026-0001", "EQ-0001", "correctif immédiat", "Clôturé administrativement", "Fuite garniture", "2026-01-10 07:45",
       "2026-01-10", "TEC-0001", "2026-01-10 08:00", "2026-01-10 12:00", "S01", "C01", "R01", di="DI-0001", arret="1",
       duree="2.5", compte_rendu="Garniture changée.", cloture_tech="2026-01-10 12:30", cloture_admin="2026-01-15 09:00",
       travail="Changer la garniture", astuce="Graisser le joint avant montage."),
    ot("OT-2026-0002", "EQ-0001", "correctif différé", "Clôturé techniquement", "Fuite garniture (bis)", "2026-03-04 08:00",
       "2026-03-05", "TEC-0002", "2026-03-05 14:00", "2026-03-05 16:00", "S01", "C01", "R01", cloture_tech="2026-03-05 16:30"),
    # Même jour que 0002, plus tôt : après lui.
    ot("OT-2026-0003", "EQ-0001", "correctif immédiat", "Clôturé techniquement", "Bruit palier", "2026-03-04 10:30", "",
       "TEC-0001", "2026-03-05 07:30", "2026-03-05 09:00", "S02", "C02", "R02", cloture_tech="2026-03-05 09:30"),
    ot("OT-2026-0004", "EQ-0001", "préventif systématique", "Clôturé administrativement", "Visite semestrielle",
       "2026-05-25 08:00", "2026-06-01", "TEC-0002", "2026-06-01 08:00", "2026-06-01 10:00",
       cloture_tech="2026-06-01 10:30", cloture_admin="2026-06-03 08:00"),
    # Ouverts : 0005 et 0010 en cours (dates prévues 25 et 30/10), 0006 planifié et 0008 en attente (20/10), 0007 sans date.
    ot("OT-2026-0005", "EQ-0001", "correctif différé", "En cours", "Fuite encore", "2026-10-17 08:00", "2026-10-25",
       "TEC-0001", "2026-10-18 08:00", symptome="S01"),
    ot("OT-2026-0006", "EQ-0001", "correctif différé", "Planifié", "Reprise du joint", "2026-10-10 08:00", "2026-10-20",
       symptome="S01"),
    ot("OT-2026-0007", "EQ-0001", "correctif immédiat", "Créé", "Pompe bloquée", "2026-10-19 08:00", symptome="S03"),
    ot("OT-2026-0008", "EQ-0001", "correctif différé", "En attente", "Bruit en attente de pièce", "2026-10-12 08:00",
       "2026-10-20", symptome="S02", motif_attente="  Pièce : roulement commandé chez Mécaroule "),
    ot("OT-2026-0009", "EQ-0001", "correctif immédiat", "Annulé", "Doublon de la fuite", "2026-09-01 08:00", symptome="S01",
       motif_annulation="Doublon de OT-2026-0001"),
    ot("OT-2026-0010", "EQ-0001", "amélioration", "En cours", "Capotage", "2026-10-01 08:00", "2026-10-30",
       debut="2026-10-15 08:00"),
    ot("OT-2026-0011", "EQ-0002", "correctif différé", "Clôturé administrativement", "Roulement moteur", "2026-04-09 08:00",
       "2026-04-10", "TEC-0002", "2026-04-10 08:00", "2026-04-10 10:00", "S02", "C02", "R02", cloture_tech="2026-04-10 10:30",
       cloture_admin="2026-04-12 08:00"),
    ot("OT-2026-0012", "EQ-0004", "correctif immédiat", "Clôturé techniquement", "Fuite convoyeur", "2026-05-02 07:00", "",
       "TEC-0002", "2026-05-02 08:00", "2026-05-02 11:00", "S01", "C02", cloture_tech="2026-05-02 11:30"),
    # Symptôme sur un préventif : ni cas ni page de panne.
    ot("OT-2026-0013", "EQ-0004", "préventif systématique", "Clôturé techniquement", "Graissage convoyeur", "2026-06-28 08:00",
       "2026-07-01", "TEC-0003", "2026-07-01 08:00", "2026-07-01 10:00", "S04", cloture_tech="2026-07-01 10:30"),
    # Équipement inconnu : compté dans les cas de S01, absent de ses machines.
    ot("OT-2026-0014", "EQ-0099", "correctif différé", "Clôturé techniquement", "Ancienne machine", "2026-08-20 07:00", "", "",
       "", "2026-08-20 10:00", "S01", "C01", "R01", cloture_tech="2026-08-20 10:30"),
    ot("OT-2026-0015", "EQ-0004", "correctif immédiat", "Clôturé administrativement", "Joint d'étanchéité", "2026-09-10 08:00",
       "", "TEC-0001", "2026-09-10 09:00", "2026-09-10 11:00", "S 05/A", "C01", "R01", cloture_tech="2026-09-10 11:30",
       cloture_admin="2026-09-12 08:00"),
])

DEMANDES = table_csv("id;date_heure;demandeur;equipement_id;symptome;impact;description;statut;ot_id", [
    "DI-0001;2026-01-10 07:30;Lucie Martin;EQ-0001;Fuite sous la pompe;arrêt;Flaque d'huile;Acceptée;OT-2026-0001",
    "DI-0003;2026-03-04 09:00;Marc Roux;EQ-0001;Bruit (doublon);gêne;;Refusée;OT-2026-0003",
    "DI-0002;2026-03-04 10:00;Marc Roux;EQ-0001;Bruit au palier;dégradé;Bruit sourd;Acceptée;OT-2026-0003",
])

ARTICLES = table_csv("id;reference;designation;fabricant;ref_fabricant;emplacement;unite;stock;stock_securite;point_commande;"
                     "qte_commande;delai_jours;prix_unitaire;fournisseur_id;critique;actif", [
    "ART-0001;'ROU-6205;Roulement 6205;Rouloran;'6205-2RS;A1-02;u;7;2;4;10;5;12.5;FOU-0001;1;1",
    "ART-0002;'JNT-01;Joint torique;;;B1-01;u;5;1;5;20;3;0.8;FOU-0002;0;1",           # jamais sorti, sous le seuil
    "ART-0003;'GRA-01;Graisse EP2;Lubrix;;C1-01;kg;0;0;1;5;7;9.9;FOU-0099;0;1",        # rupture qui dure encore
    "ART-0004;'FIL-01;Filtre;;;;u;0;;;;;;;0;1",                                        # sortie sur un OT inconnu
    "ART-0005;'CRO-01;Courroie;;;D1-01;u;0;;;;;;;0;1",                                 # aucun mouvement
])

FOURNISSEURS = table_csv("id;nom;contact;telephone;email", ["FOU-0001;Mécaroule;;;", "FOU-0002;Joints Ouest;;;"])

ACHATS = table_csv("id;date;article_id;fournisseur_id;quantite;prix_unitaire;statut;date_reception", [
    "ACH-0002;2026-10-15;ART-0001;FOU-0001;10;13;commandée;",
    "ACH-0001;2026-03-06;ART-0001;FOU-0001;4;12.5;reçue;2026-03-10",
    "ACH-0003;2026-01-15;ART-0002;FOU-0002;2;0.8;reçue;2026-02-01",
])

ARTICLE_EQUIPEMENT = table_csv("id;article_id;equipement_id;quantite", [
    "AEQ-0001;ART-0001;EQ-0001;2", "AEQ-0002;ART-0001;EQ-0002;1", "AEQ-0003;ART-0002;EQ-0001;4",
    "AEQ-0004;ART-0001;EQ-0001;9",           # second couple : la première ligne fait foi
    "AEQ-0005;ART-0003;EQ-0099;1",           # équipement inconnu
    "AEQ-0006;ART-0099;EQ-0001;1",           # article inconnu
])

MOUVEMENTS = table_csv("id;date;article_id;type;quantite;ot_id", [
    "MVT-000001;2026-01-01 08:00;ART-0001;inventaire;3;",
    "MVT-000002;2026-01-10 09:00;ART-0001;sortie;2;OT-2026-0001",      # 1
    "MVT-000003;2026-01-10 10:00;ART-0001;retour;1;OT-2026-0001",      # 2
    "MVT-000004;2026-03-05 08:00;ART-0001;sortie;2;OT-2026-0003",      # 0 : rupture
    "MVT-000005;2026-03-05 15:00;ART-0001;sortie;1;OT-2026-0002",      # -1
    "MVT-000006;2026-03-10 08:00;ART-0001;entrée;4;",                  # 3 : fin de rupture
    "MVT-000007;2026-04-01 08:00;ART-0001;inventaire;5;",              # 5 (fixé, pas ajouté)
    "MVT-000008;2026-04-10 09:00;ART-0001;sortie;5;OT-2026-0011",      # 0 : rupture
    "MVT-000009;2026-04-10 11:00;ART-0001;retour;2;OT-2026-0011",      # 2 : le retour la finit
    "MVT-000010;2026-05-02 10:00;ART-0001;sortie;1;OT-2026-0012",      # 1
    "MVT-000011;2026-06-02 08:00;ART-0001;sortie;1;",                  # 0 sans OT : rupture
    "MVT-000012;2026-06-05 08:00;ART-0001;entrée;6;",                  # 6
    "MVT-000013;2026-10-18 09:00;ART-0001;sortie;1;OT-2026-0005",      # 5 (OT en cours)
    "MVT-000014;2026-01-01 08:00;ART-0002;inventaire;3;",
    "MVT-000015;2026-02-01 08:00;ART-0002;entrée;2;",
    "MVT-000016;2026-02-01 08:00;ART-0003;inventaire;1;",
    "MVT-000017;2026-06-01 09:00;ART-0003;sortie;0.5;OT-2026-0004",
    "MVT-000018;2026-07-01 09:00;ART-0003;sortie;0.5;OT-2026-0013",    # 0 : rupture qui dure encore
    "MVT-000019;2026-07-02 08:00;ART-0004;sortie;1;OT-2026-0999",      # OT inconnu
])

OT_TEMPS = table_csv("id;ot_id;technicien_id;date;heures", [
    "OTT-0001;OT-2026-0001;TEC-0001;2026-01-10;2.5", "OTT-0002;OT-2026-0001;TEC-0002;2026-01-10;1",
    "OTT-0003;OT-2026-0012;TEC-0001;2026-05-02;0.75", "OTT-0004;OT-2026-0005;TEC-0001;2026-10-18;3",
    "OTT-0005;OT-2026-0001;TEC-0099;2026-01-10;1"])

OT_OPERATIONS = table_csv("id;ot_id;ordre;operation;valeur_attendue;fait;valeur_mesuree", [
    "OP-0001;OT-2026-0004;2;Graisser;;1;", "OP-0002;OT-2026-0004;1;Contrôler le jeu;0,1 mm au plus;1;0,05 mm",
    "OP-0003;OT-2026-0004;10;Essai;;0;"])

GAMMES = table_csv("id;equipement_id;libelle;declencheur;periodicite_jours;prochaine_echeance;actif", [
    "GAM-0001;EQ-0001;Graissage mensuel;date;30;2026-11-01;1", "GAM-0002;EQ-0001;Visite annuelle;date;365;2026-10-25;1",
    "GAM-0003;EQ-0001;Ancienne gamme;date;90;2026-01-01;0", "GAM-0004;EQ-0001;Selon compteur;compteur;;;1"])

CONTROLES = table_csv("id;equipement_id;nature;organisme;derniere_date;prochaine_date", [
    "CR-0001;EQ-0001;Appareil à pression;Bureau de contrôle;2025-11-01;2026-11-01",
    "CR-0002;EQ-0004;Levage;Organisme agréé;2026-01-01;2027-01-01"])

ENTETE_WIKI = ("id;type;titre;cle;equipement_id;article_id;cause_code;rattache_a;texte;ot_cites;liens;version;origine;"
               "modele;derniere_entree;valide_par;valide_le;cree_le;modifie_le;statut")


def page_wiki(id_, type_, titre, texte="", equipement="", article="", rattache="", statut="active", origine="IA"):
    return [id_, type_, titre, "", equipement, article, "", rattache, texte, "", "", "1", origine if texte else "",
            "claude-sonnet-5-5" if texte else "", "", "Responsable fictif" if texte else "", "2026-10-01 10:00" if texte else "",
            "2026-10-01 09:00", "2026-10-01 10:00", statut]


# Texte de PO-01 écrit dans le désordre : une rubrique ancienne, « Astuces », puis « En bref ».
TEXTE_PO01 = NL.join(["## Ce qui revient", "- Ancienne phrase [OT-2026-0011]", "## Astuces",
                      "- Purger avant de démonter [OT-2026-0002]", "## En bref",
                      "- Fuite de garniture fréquente, voir [[Changer le roulement de PO-01]] [OT-2026-0001] [OT-2026-0002]",
                      "- Bruit de palier [OT-2026-0003]"])
WIKI_PAGES = table_csv(ENTETE_WIKI, [
    page_wiki("WP-0001", "équipement", "PO-01 — Pompe A", TEXTE_PO01, equipement="EQ-0001"),
    page_wiki("WP-0002", "composant", "Roulement 6205", "## À quoi il sert" + NL + "- Guide l'arbre du moteur [OT-2026-0011]",
              article="ART-0001", origine="manuel"),
    page_wiki("WP-0003", "savoir-faire", "Changer le roulement de PO-01", NL.join([
        "## Étapes", "- Chauffer la bague [OT-2026-0003]", "## Pièges", "- Ne pas frapper [OT-2026-0001]",
        "## Quand le faire", "- Au premier bruit [OT-2026-0003]"]), equipement="EQ-0001"),
    page_wiki("WP-0004", "savoir-faire", "Graisser un roulement", "## Étapes" + NL + "- Graisser [OT-2026-0012]", article="ART-0001"),
    page_wiki("WP-0005", "savoir-faire", "Purger la pompe", "## Étapes" + NL + "- Purger [OT-2026-0002]", rattache="WP-0001"),
    page_wiki("WP-0006", "savoir-faire", "Changer le roulement de PO-01 — remontage", "## Étapes" + NL + "- Serrer [OT-2026-0003]",
              rattache="WP-0003"),
    page_wiki("WP-0007", "mode", "Cavitation", "## Causes" + NL + "- Aspiration [OT-2026-0001]"),
    page_wiki("WP-0008", "savoir-faire", "Ancien geste", "## Étapes" + NL + "- Vieux [OT-2026-0001]", equipement="EQ-0001",
              statut="archivée"),
    page_wiki("WP-0009", "équipement", "Ancienne presse", "## En bref" + NL + "- Presse [OT-2026-0014]", equipement="EQ-0099"),
    page_wiki("WP-0010", "savoir-faire", "Règles de l'atelier", "## Étapes" + NL + "- Ranger [OT-2026-0004]"),
])

CONTRADICTIONS = ('[{"statut":"ouverte","phrase":"Fuite [OT-2026-0001]","observation":"Pas de fuite","ot":["OT-2026-0002"]},'
                  '{"statut":"fermée","phrase":"a","observation":"b","ot":[]}]')
WIKI_JOURNAL = table_csv("id;nature;ot_id;statut;contradictions", [
    ["WJ-00001", "ingestion", "OT-2026-0001", "validée", CONTRADICTIONS],
    "WJ-00002;ingestion;OT-2026-0002;à valider;", "WJ-00003;ingestion;OT-2026-0003;refusée;",
    "WJ-00004;ingestion;OT-2026-0004;refusée;", "WJ-00005;ingestion;OT-2026-0004;en file;",
    "WJ-00006;ingestion;OT-2026-0011;rejetée;", "WJ-00007;ingestion;OT-2026-0011;refusée;",
    "WJ-00008;ingestion;OT-2026-0012;refusée;", "WJ-00009;ingestion;OT-2026-0012;rejetée;",
    "WJ-00010;ingestion;OT-2026-0013;à valider;",
])

BASE = {"localisations": LOCALISATIONS, "equipements": EQUIPEMENTS, "codes_defaillance": CODES, "techniciens": TECHNICIENS,
        "habilitations": HABILITATIONS, "ordres_travail": ORDRES, "demandes": DEMANDES, "articles": ARTICLES,
        "fournisseurs": FOURNISSEURS, "achats": ACHATS, "article_equipement": ARTICLE_EQUIPEMENT,
        "mouvements_stock": MOUVEMENTS, "ot_temps": OT_TEMPS, "ot_operations": OT_OPERATIONS, "gammes": GAMMES,
        "controles_reglementaires": CONTROLES, "wiki_pages": WIKI_PAGES, "wiki_journal": WIKI_JOURNAL,
        "parametres": table_csv("cle;valeur", ["version_schema;3"])}
IDS_BASE = (["EQ-%04d" % n for n in range(1, 8)] + ["ART-%04d" % n for n in range(1, 6)]
            + ["TEC-0001", "TEC-0002", "TEC-0003"] + ["OT-2026-%04d" % n for n in range(1, 16)]
            + ["WP-%04d" % n for n in range(1, 11)]
            + ["PANNE-S01", "PANNE-S02", "PANNE-S03", "PANNE-S04", "PANNE-S%2005%2FA", "PANNE-S 05/A", "PANNE-S99", "PANNE-",
               "PANNE-%E0%A4%A", "EQ-9999", "ART-9999", "TEC-9999", "OT-2026-0999", "WP-9999", "C01", ""])
TYPES = ("machine", "panne", "article", "technicien", "savoir-faire", "intervention")


# ---------------------------------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------------------------------

class CasEntites(CasNavigateur):

    def charger(self, tables, scripts=SCRIPTS):
        self.requetes = []
        self.page.on("request", lambda requete: self.requetes.append(requete.url))
        charger_scripts(self.page, scripts)
        self.page.evaluate("""async (tables) => {
          Donnees.initialiser(StockageDemo.creer(tables), { poste: 'Poste test', profil: 'Responsable test' });
          await Donnees.chargerTout();
        }""", tables)

    def entites(self, identifiants, profil, maintenant=MAINTENANT):
        return self.page.evaluate("([ids, profil, maintenant]) => ids.map((id) => Wiki.entite(id, { profil, maintenant }))",
                                  [identifiants, profil, maintenant])

    def entite(self, identifiant, profil="responsable"):
        return self.entites([identifiant], profil)[0]

    def listes(self, profil, maintenant=MAINTENANT):
        return self.page.evaluate("""([types, profil, maintenant]) => Object.fromEntries(types.map((type) =>
          [type, Wiki.listeEntites(type, { profil, maintenant })]))""", [list(TYPES), profil, maintenant])

    def accueil(self, profil, maintenant=MAINTENANT):
        return self.page.evaluate("([profil, maintenant]) => Wiki.accueilEncyclopedie({ profil, maintenant })", [profil, maintenant])

    def requetes_reseau(self):
        return [url for url in self.requetes if not url.startswith(("file:", "data:", "blob:"))]

    def verifier_comme_le_calcul(self, calcul, identifiants, profil):
        obtenues = self.entites(identifiants, profil)
        pages = self.page.evaluate("(ids) => ids.map((id) => Wiki.page(id))", identifiants)
        for identifiant, obtenue, page in zip(identifiants, obtenues, pages):
            with self.subTest(entite=identifiant, profil=profil):
                self.assertEqual(comparable(sans_wiki_page(obtenue)), comparable(calcul.entite(identifiant, profil, MAINTENANT)))
                if obtenue and obtenue["type"] == "savoir-faire":       # en-tête, mère, sous-pages : ceux de Wiki.page
                    self.assertEqual((obtenue["sections"]["entete"], obtenue["sections"]["mere"], obtenue["sections"]["sousPages"]),
                                     (page["entete"], page["mere"], page["sousPages"]))
        return obtenues


class TestDemo(CasEntites):
    """Jeu de démo : JavaScript = calcul Python indépendant, pour les trois profils."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tables = {f.stem: f.read_bytes().decode("utf-8-sig") for f in DOSSIER_DEMO.glob("*.csv")}
        cls.calcul = CalculWiki(cls.tables)

    def setUp(self):
        super().setUp()
        self.charger(self.tables)

    def test_machines_pannes_articles_techniciens_egaux_au_calcul_python(self):
        machines = sorted(self.calcul.par_id)
        articles = sorted(self.calcul.articles)
        techniciens = sorted(t["id"] for t in self.calcul.tables["techniciens"])
        codes = sorted({ot["symptome_code"].strip() for ot in self.calcul.ordres if ot["symptome_code"].strip()})
        pannes = ["PANNE-" + code for code in codes] + ["PANNE-S00"]
        self.assertGreater(len(machines), 20)
        self.assertGreater(len(articles), 40)
        self.assertGreater(len(codes), 5)
        for profil in PROFILS:
            obtenues = self.verifier_comme_le_calcul(self.calcul, machines + articles + techniciens + pannes, profil)
            # Le calcul n'est pas vide sur la démo : interventions, pannes, articles consommés, ruptures, habilitations.
            par_id = {e["id"]: e for e in obtenues if e}
            self.assertTrue(any(e["sections"]["pannes"] and e["sections"]["articlesConsommes"]
                                for e in par_id.values() if e["type"] == "machine"))
            self.assertTrue(any(e["sections"]["sorties"] for e in par_id.values() if e["type"] == "article"))
            self.assertEqual(sum(1 for e in obtenues if e and e["type"] == "panne"), len(codes))
            self.assertEqual(sum(1 for e in obtenues if e and e["type"] == "technicien"), 0 if profil == "demandeur" else len(techniciens))
        self.assertEqual(self.requetes_reseau(), [])

    def test_quelques_interventions_egales_au_calcul_python(self):
        ordres = self.calcul.ordres
        choisis = [ot["id"] for ot in ordres[:12]] + [ot["id"] for ot in ordres
                                                       if ot["statut"] not in ("Clôturé techniquement", "Clôturé administrativement")]
        self.assertTrue(any(self.calcul.ordre_par_id[i]["statut"] == "Annulé" for i in choisis))
        for profil in PROFILS:
            obtenues = self.verifier_comme_le_calcul(self.calcul, choisis, profil)
            if profil == "demandeur":
                self.assertEqual(obtenues, [None] * len(choisis))
        self.assertTrue(any(e["sections"]["temps"] and e["sections"]["pieces"] for e in self.entites(choisis, "technicien")))

    def test_listes_et_accueil_egaux_au_calcul_python(self):
        for profil in PROFILS:
            listes = self.listes(profil)
            for type_ in TYPES:
                with self.subTest(liste=type_, profil=profil):
                    self.assertEqual(comparable(listes[type_]), comparable(self.calcul.liste_entites(type_, profil, MAINTENANT)))
            with self.subTest(accueil=profil):
                self.assertEqual(comparable(self.accueil(profil)), comparable(self.calcul.accueil(profil, MAINTENANT)))
        listes = self.listes("responsable")
        self.assertEqual(listes["savoir-faire"], [])          # le wiki de la démo est vide au socle
        self.assertEqual(len(listes["intervention"]), len(self.calcul.ordres))
        statuts = [e["statut"] for e in listes["intervention"]]
        ouverts = [s for s in statuts if s in ("Créé", "Préparé", "Planifié", "En cours", "En attente")]
        self.assertEqual(statuts[:len(ouverts)], ouverts)       # les ouverts en tête
        self.assertEqual(statuts[0], "En cours")

    def test_stock_reconstitue_egal_a_articles_stock(self):
        # Écarts entre la colonne stock (copie lisible dans Excel) et le stock rejoué par les mouvements : aucun sur la démo.
        ecarts = [(a, article["stock"], self.calcul.stock_dans_le_temps(a, "responsable")[0])
                  for a, article in sorted(self.calcul.articles.items())
                  if nombre(article["stock"]) != self.calcul.stock_dans_le_temps(a, "responsable")[0]]
        self.assertEqual(ecarts, [])
        resultat = self.page.evaluate("""() => Donnees.lignes('articles').map((a) => [a.id,
          Wiki.entite(a.id, { profil: 'responsable' }).faits.find((f) => f.libelle === 'Stock').valeur, Donnees.stockArticle(a.id)])""")
        self.assertEqual([r for r in resultat if r[1] != r[2]], [])

    def test_visibilite_du_demandeur_sur_la_demo(self):
        resultat = self.page.evaluate("""() => {
          const options = { profil: 'demandeur' };
          const articles = Donnees.lignes('articles').map((a) => Wiki.entite(a.id, options));
          const machines = Donnees.lignes('equipements').map((e) => Wiki.entite(e.id, options));
          const liens = (liste) => liste.flatMap((e) => [e.lien].concat((e.techniciens || []).map((t) => t.lien)));
          return {
            techniciens: Donnees.lignes('techniciens').map((t) => Wiki.entite(t.id, options)),
            ot: Donnees.lignes('ordres_travail').map((o) => Wiki.entite(o.id, options)),
            prix: articles.filter((a) => a.faits.some((f) => /prix/i.test(f.libelle))
              || a.sections.commandes.some((c) => 'prixUnitaire' in c)).length,
            liensOt: liens(machines.flatMap((m) => m.sections.interventions)).filter(Boolean),
            listes: [Wiki.listeEntites('technicien', options), Wiki.listeEntites('intervention', options)],
          };
        }""")
        self.assertTrue(all(e is None for e in resultat["techniciens"]))
        self.assertTrue(all(e is None for e in resultat["ot"]))
        self.assertEqual((resultat["prix"], resultat["liensOt"], resultat["listes"]), (0, [], [None, None]))


class TestBaseEssai(CasEntites):
    """Base construite pour les cas limites : valeurs à la main et égalité avec le calcul Python."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.calcul = CalculWiki(BASE)

    def setUp(self):
        super().setUp()
        self.charger(BASE)

    def test_toutes_les_entites_listes_et_accueil_egales_au_calcul_python(self):
        for profil in PROFILS:
            self.verifier_comme_le_calcul(self.calcul, IDS_BASE, profil)
            listes = self.listes(profil)
            for type_ in TYPES:
                with self.subTest(liste=type_, profil=profil):
                    self.assertEqual(comparable(listes[type_]), comparable(self.calcul.liste_entites(type_, profil, MAINTENANT)))
            with self.subTest(accueil=profil):
                self.assertEqual(comparable(self.accueil(profil)), comparable(self.calcul.accueil(profil, MAINTENANT)))
        self.assertIsNone(self.page.evaluate("Wiki.listeEntites('mode', { profil: 'responsable' })"))

    def test_ordre_des_interventions(self):
        # Ouverts : en cours (date prévue 25 puis 30/10), puis planifié et en attente (20/10, par identifiant), puis sans date
        # prévue ; ensuite l'annulé (créé le 01/09) et les clôturés, du plus récent au plus ancien (0002 avant 0003, même jour).
        attendu = ["OT-2026-0005", "OT-2026-0010", "OT-2026-0006", "OT-2026-0008", "OT-2026-0007", "OT-2026-0009",
                   "OT-2026-0004", "OT-2026-0002", "OT-2026-0003", "OT-2026-0001"]
        machine = self.entite("EQ-0001")
        self.assertEqual(ids(machine["sections"]["interventions"]), attendu)
        self.assertEqual([e["statut"] for e in machine["sections"]["interventions"]][:6],
                         ["En cours", "En cours", "Planifié", "En attente", "Créé", "Annulé"])
        melange = ["OT-2026-0001", "OT-2026-0009", "OT-2999-0001", "OT-2026-0005", "OT-2026-0001", "OT-2026-0003"]
        self.assertEqual(self.page.evaluate("(ids) => Wiki.ordreInterventions(ids)", melange),
                         ["OT-2026-0005", "OT-2026-0009", "OT-2026-0003", "OT-2026-0001"])
        self.assertEqual(self.calcul.ordre_interventions(melange), ["OT-2026-0005", "OT-2026-0009", "OT-2026-0003", "OT-2026-0001"])
        # Même règle dans toutes les listes : panne, article, technicien.
        self.assertEqual(ids(self.entite("PANNE-S01")["sections"]["interventions"]), [
            "OT-2026-0005", "OT-2026-0006", "OT-2026-0009", "OT-2026-0014", "OT-2026-0012", "OT-2026-0002", "OT-2026-0001"])
        self.assertEqual(ids(self.entite("ART-0001")["sections"]["interventions"]), [
            "OT-2026-0005", "OT-2026-0012", "OT-2026-0011", "OT-2026-0002", "OT-2026-0003", "OT-2026-0001"])
        self.assertEqual(ids(self.entite("TEC-0001")["sections"]["interventions"]), [
            "OT-2026-0005", "OT-2026-0015", "OT-2026-0012", "OT-2026-0003", "OT-2026-0001"])

    def test_pannes_sur_les_seuls_ot_correctifs_clotures(self):
        machine = self.entite("EQ-0001")
        # 0005, 0006 (S01) et 0008 (S02) ouverts, 0009 (S01) annulé : pas des cas.
        self.assertEqual(machine["sections"]["pannes"], [
            {"code": "S01", "libelle": "Fuite", "cas": 2, "derniere": "2026-03-05", "lien": "PANNE-S01"},
            {"code": "S02", "libelle": "Bruit", "cas": 1, "derniere": "2026-03-05", "lien": "PANNE-S02"}])
        panne = self.entite("PANNE-S01", "technicien")
        self.assertEqual((panne["titre"], faits(panne)), ("Fuite", {
            "Code": "S01", "Cas": 4, "Machines touchées": 2, "Premier cas": "2026-01-10", "Dernier cas": "2026-08-20"}))
        self.assertEqual(panne["sections"]["machines"], [
            {"equipementId": "EQ-0001", "titre": "PO-01 — Pompe A", "lien": "EQ-0001", "cas": 2},
            {"equipementId": "EQ-0004", "titre": "CV-01 — Convoyeur", "lien": "EQ-0004", "cas": 1}])
        self.assertEqual(panne["sections"]["causes"], [{"code": "C01", "libelle": "Usure", "cas": 3},
                                                       {"code": "C02", "libelle": "Desserrage", "cas": 1}])
        self.assertEqual(panne["sections"]["remedes"], [{"code": "R01", "libelle": "Remplacement", "cas": 3}])
        self.assertEqual(panne["sections"]["articles"], [{"articleId": "ART-0001", "titre": "Roulement 6205", "lien": "ART-0001",
                                                          "quantite": 3, "ot": ["OT-2026-0012", "OT-2026-0002", "OT-2026-0001"]}])
        self.assertEqual((panne["textes"], panne["references"]), (None, []))
        # Code sans OT clôturé (S03 : un OT ouvert), symptôme d'un préventif (S04), code inconnu : pas de page.
        for identifiant in ("PANNE-S03", "PANNE-S04", "PANNE-S99", "PANNE-", "PANNE-%E0%A4%A"):
            with self.subTest(panne=identifiant):
                self.assertIsNone(self.entite(identifiant))
        self.assertEqual([(p["code"], p["cas"], p["machines"]) for p in self.listes("demandeur")["panne"]],
                         [("S01", 4, 2), ("S02", 2, 2), ("S 05/A", 1, 1)])
        # Un code à caractères spéciaux : identifiant encodé, sûr dans une adresse.
        self.assertEqual(self.page.evaluate("Wiki.idPanne('S 05/A')"), "PANNE-S%2005%2FA")
        self.assertEqual(self.entite("PANNE-S%2005%2FA")["titre"], "Défaut d'étanchéité")
        self.assertIsNone(self.entite("PANNE-S 05/A"))
        lien = [e["panne"] for e in self.entite("EQ-0004")["sections"]["interventions"] if e["id"] == "OT-2026-0015"][0]
        self.assertEqual(lien, {"code": "S 05/A", "libelle": "Défaut d'étanchéité", "lien": "PANNE-S%2005%2FA"})
        sans_page = [e["panne"] for e in self.entite("EQ-0001")["sections"]["interventions"] if e["id"] == "OT-2026-0007"][0]
        self.assertEqual(sans_page, {"code": "S03", "libelle": "Blocage", "lien": None})

    def test_stock_dans_le_temps(self):
        roulement = self.entite("ART-0001")
        self.assertEqual((faits(roulement)["Stock"], faits(roulement)["État du stock"]), (5, "en stock"))
        self.assertEqual(self.page.evaluate("Donnees.stockArticle('ART-0001')"), 5)
        # Sorties imputées à un OT avec le stock restant (retours compris ; la sortie sans OT n'y est pas).
        self.assertEqual([(s["id"][-2:], s["date"], s["type"], s["quantite"], s["ot"][-4:], s["stock"])
                          for s in roulement["sections"]["sorties"]], [
            ("02", "2026-01-10", "sortie", 2, "0001", 1), ("03", "2026-01-10", "retour", 1, "0001", 2),
            ("04", "2026-03-05", "sortie", 2, "0003", 0), ("05", "2026-03-05", "sortie", 1, "0002", -1),
            ("08", "2026-04-10", "sortie", 5, "0011", 0), ("09", "2026-04-10", "retour", 2, "0011", 2),
            ("10", "2026-05-02", "sortie", 1, "0012", 1), ("13", "2026-10-18", "sortie", 1, "0005", 5)])
        # Ruptures : la deuxième finit au retour ; la troisième vient d'une sortie sans OT.
        self.assertEqual(roulement["sections"]["ruptures"], [
            {"debut": "2026-03-05", "fin": "2026-03-10"}, {"debut": "2026-04-10", "fin": "2026-04-10"},
            {"debut": "2026-06-02", "fin": "2026-06-05"}])
        self.assertEqual([(c["id"], c["fournisseur"], c["statut"], c["prixUnitaire"]) for c in roulement["sections"]["commandes"]],
                         [("ACH-0001", "Mécaroule", "reçue", 12.5), ("ACH-0002", "Mécaroule", "commandée", 13)])
        self.assertEqual(roulement["sections"]["consommeSur"], [
            {"equipementId": "EQ-0001", "titre": "PO-01 — Pompe A", "lien": "EQ-0001", "nombreOt": 3, "quantite": 4},
            {"equipementId": "EQ-0004", "titre": "CV-01 — Convoyeur", "lien": "EQ-0004", "nombreOt": 1, "quantite": 1},
            {"equipementId": "EQ-0002", "titre": "PO-01.M — Moteur de PO-01", "lien": "EQ-0002", "nombreOt": 1, "quantite": 3}])
        self.assertEqual([(m["equipementId"], m["quantite"]) for m in roulement["sections"]["montee"]], [("EQ-0001", 2), ("EQ-0002", 1)])
        # Jamais sorti, sous le seuil ; rupture qui dure encore ; sortie sur un OT inconnu ; aucun mouvement.
        joint, graisse, filtre, courroie = self.entites(["ART-0002", "ART-0003", "ART-0004", "ART-0005"], "technicien")
        self.assertEqual((faits(joint)["Stock"], faits(joint)["État du stock"], joint["sections"]["sorties"],
                          joint["sections"]["ruptures"], joint["sections"]["interventions"]), (5, "sous le seuil", [], [], []))
        self.assertEqual((faits(graisse)["Stock"], faits(graisse)["État du stock"], graisse["sections"]["ruptures"]),
                         (0, "rupture", [{"debut": "2026-07-01", "fin": ""}]))
        self.assertEqual(faits(graisse)["Fournisseur"], "FOU-0099")                       # fournisseur inconnu : son identifiant
        self.assertEqual([(s["ot"], s["machine"], s["lien"], s["stock"]) for s in filtre["sections"]["sorties"]],
                         [("OT-2026-0999", None, None, -1)])
        self.assertEqual((filtre["sections"]["ruptures"], filtre["sections"]["interventions"]), ([{"debut": "2026-07-02", "fin": ""}], []))
        self.assertEqual((faits(courroie)["Stock"], faits(courroie)["État du stock"], courroie["sections"]["ruptures"]), (0, "rupture", []))
        self.assertEqual(self.accueil("technicien")["articles"], {"sousLeSeuil": 1, "enRupture": 3})

    def test_machine_fiche_sous_ensembles_articles_savoir_faire_preventif(self):
        pompe = self.entite("EQ-0001")
        self.assertEqual(pompe["faits"], [
            {"libelle": "Repère", "valeur": "PO-01", "lien": None}, {"libelle": "Lieu", "valeur": "Usine › Atelier A › Ligne 1", "lien": None},
            {"libelle": "Marque et modèle", "valeur": "Hydro HC 50", "lien": None}, {"libelle": "N° de série", "valeur": "SN-1", "lien": None},
            {"libelle": "Mise en service", "valeur": "2020-05-04", "lien": None}, {"libelle": "Criticité", "valeur": "A", "lien": None},
            {"libelle": "État", "valeur": "en service", "lien": None}, {"libelle": "Habilitation requise", "valeur": "BR", "lien": None},
            {"libelle": "Interventions", "valeur": 10, "lien": None}])
        sections = pompe["sections"]
        self.assertEqual(sections["consignation"], {"texte": "Couper Q1 et cadenasser.", "document": ""})
        self.assertEqual(sections["sousEnsembles"], [{"equipementId": "EQ-0002", "titre": "PO-01.M — Moteur de PO-01", "lien": "EQ-0002"}])
        self.assertEqual([(a["articleId"], a["quantite"]) for a in sections["articlesMontes"]], [("ART-0002", 4), ("ART-0001", 2)])
        self.assertEqual([(a["articleId"], a["quantite"], a["ot"]) for a in sections["articlesConsommes"]], [
            ("ART-0001", 4, ["OT-2026-0002", "OT-2026-0003", "OT-2026-0001"]), ("ART-0003", 0.5, ["OT-2026-0004"])])
        self.assertEqual([(s["id"], s["titre"]) for s in sections["savoirFaire"]],
                         [("WP-0003", "Changer le roulement de PO-01"), ("WP-0005", "Purger la pompe")])
        self.assertEqual([g["id"] for g in sections["gammes"]], ["GAM-0002", "GAM-0001", "GAM-0004"])
        self.assertEqual([c["id"] for c in sections["controles"]], ["CR-0001"])
        moteur, orphelin = self.entites(["EQ-0002", "EQ-0007"], "demandeur")
        self.assertEqual(moteur["faits"][-2], {"libelle": "Fait partie de", "valeur": "PO-01 — Pompe A", "lien": "EQ-0001"})
        self.assertEqual(orphelin["faits"][-2], {"libelle": "Fait partie de", "valeur": "EQ-0099", "lien": None})
        # Liste : par lieu (sans lieu en dernier), sous-ensembles sous leur machine ; le cycle reste en tête.
        arbre = [(g["lieu"], [(m["equipementId"], [(s["equipementId"], [x["equipementId"] for x in s["sousEnsembles"]])
                                                   for s in m["sousEnsembles"]]) for m in g["machines"]])
                 for g in self.listes("demandeur")["machine"]]
        self.assertEqual(arbre, [
            ("Usine › Atelier A", [("EQ-0004", []), ("EQ-0007", [])]),
            ("Usine › Atelier A › Ligne 1", [("EQ-0001", [("EQ-0002", ["EQ-0003"])])]),
            ("", [("EQ-0005", []), ("EQ-0006", [])])])

    def test_technicien_habilitations_et_heures(self):
        paul = self.entite("TEC-0001")
        self.assertEqual((paul["titre"], faits(paul)), ("Paul Martin", {
            "Métier": "Mécanicien", "Capacité (h par semaine)": 35, "Heures pointées": 6.25, "Interventions": 5, "Actif": True,
            "Taux horaire": 40}))
        # Les règles du module Équipe : une habilitation par intitulé (le renouvellement compte, l'ancienne ligne reste
        # pour l'historique), « à renouveler » sous 60 jours (RG8), « pas encore valable » ; l'accueil, comme l'alerte
        # « à renouveler » de Prévo, ne compte que les techniciens actifs.
        self.assertEqual(paul["sections"]["habilitations"], [
            {"id": "HAB-0002", "intitule": "B1V", "obtention": "2024-01-10", "echeance": "2026-12-18", "etat": "à renouveler"},
            {"id": "HAB-0004", "intitule": "br", "obtention": "2026-10-02", "echeance": "2029-10-02", "etat": "valide"},
            {"id": "HAB-0003", "intitule": "H0V", "obtention": "2024-01-10", "echeance": "2026-12-19", "etat": "valide"}])
        lea = self.entite("TEC-0002", "technicien")
        self.assertEqual([(h["intitule"], h["etat"]) for h in lea["sections"]["habilitations"]],
                         [("B2V", "à renouveler"), ("CACES", "valide"), ("H0V", "échue"), ("SST", "pas encore valable")])
        self.assertEqual([h["etat"] for h in self.entite("TEC-0003")["sections"]["habilitations"]], ["échue"])
        self.assertEqual(self.accueil("responsable")["habilitations"], {"suivies": 7, "aRenouveler": 2, "echues": 1})
        alerte = self.page.evaluate("(jour) => Equipe.aRenouveler(jour).map((x) => x.etat.statut)", MAINTENANT)
        self.assertEqual(sorted(alerte), ["à renouveler", "à renouveler", "échue"])        # même compte que l'accueil de Prévo

    def test_intervention_en_lecture_seule(self):
        intervention = self.entite("OT-2026-0001", "technicien")
        self.assertEqual(faits(intervention), {
            "Machine": "PO-01 — Pompe A", "Type": "correctif immédiat", "Priorité": "P2", "Statut": "Clôturé administrativement",
            "Technicien": "Paul Martin", "Créé le": "2026-01-10 07:45", "Prévu le": "2026-01-10", "Début": "2026-01-10 08:00",
            "Fin": "2026-01-10 12:00", "Arrêt de production": True, "Durée d'arrêt (h)": 2.5, "Panne": "Fuite", "Cause": "Usure",
            "Remède": "Remplacement", "Demande d'origine": "DI-0001", "Clôture technique": "2026-01-10 12:30",
            "Clôture administrative": "2026-01-15 09:00"})
        self.assertEqual([f["lien"] for f in intervention["faits"] if f["lien"]], ["EQ-0001", "TEC-0001", "PANNE-S01"])
        sections = intervention["sections"]
        self.assertEqual((sections["travail"], sections["compteRendu"], sections["astuce"], sections["ficheOT"]),
                         ("Changer la garniture", "Garniture changée.", "Graisser le joint avant montage.", "#/ot/OT-2026-0001"))
        self.assertEqual(sections["demande"]["id"], "DI-0001")
        self.assertEqual([(t["technicienId"], t["nom"]) for t in sections["techniciens"]],
                         [("TEC-0001", "Paul Martin"), ("TEC-0002", "Léa Durand")])
        self.assertEqual([(t["id"], t["nom"], t["heures"], t["lien"]) for t in sections["temps"]], [
            ("OTT-0001", "Paul Martin", 2.5, "TEC-0001"), ("OTT-0002", "Léa Durand", 1, "TEC-0002"), ("OTT-0005", "", 1, None)])
        self.assertEqual(sections["pieces"], [{"articleId": "ART-0001", "titre": "Roulement 6205", "lien": "ART-0001", "quantite": 1}])
        # Cité par le texte de PO-01 et par un savoir-faire ; ni la page de mode ni la page archivée.
        self.assertEqual([(p["id"], p["type"]) for p in sections["citeDans"]], [("WP-0003", "savoir-faire"), ("EQ-0001", "machine")])
        # Sans di_id : la plus ancienne demande ACCEPTÉE qui pointe vers l'OT (DI-0003, refusée, est plus ancienne).
        self.assertEqual(self.entite("OT-2026-0003")["sections"]["demande"]["id"], "DI-0002")
        self.assertEqual([o["ordre"] for o in self.entite("OT-2026-0004")["sections"]["operations"]], [1, 2, 10])
        self.assertEqual([(p["id"], p["type"]) for p in self.entite("OT-2026-0011")["sections"]["citeDans"]],
                         [("EQ-0001", "machine"), ("ART-0001", "article")])
        # Motifs d'attente et d'annulation de l'OT (T137) : '' sans motif, espaces retirés.
        self.assertEqual((sections["motifAttente"], sections["motifAnnulation"]), ("", ""))
        self.assertEqual(self.entite("OT-2026-0008")["sections"]["motifAttente"], "Pièce : roulement commandé chez Mécaroule")
        self.assertEqual((self.entite("OT-2026-0009")["sections"]["motifAnnulation"],
                          self.entite("OT-2026-0009")["sections"]["motifAttente"]), ("Doublon de OT-2026-0001", ""))

    def test_savoir_faire_et_identifiants(self):
        self.assertEqual(self.entite("WP-0001"), self.entite("EQ-0001"))           # texte d'une machine : sa page
        self.assertEqual(self.entite("WP-0002"), self.entite("ART-0001"))          # texte d'un article : sa page
        sous_page = self.entite("WP-0006")
        self.assertEqual(sous_page["faits"], [
            {"libelle": "Rattaché à", "valeur": "PO-01 — Pompe A", "lien": "EQ-0001"},
            {"libelle": "Sous-page de", "valeur": "Changer le roulement de PO-01", "lien": "WP-0003"}])
        self.assertEqual(self.entite("WP-0005")["sections"]["rattachement"],
                         {"type": "machine", "id": "EQ-0001", "titre": "PO-01 — Pompe A", "lien": "EQ-0001"})
        self.assertEqual(self.entite("WP-0004")["sections"]["rattachement"]["type"], "article")
        self.assertIsNone(self.entite("WP-0010")["sections"]["rattachement"])
        for identifiant in ("WP-0007", "WP-0008", "WP-0009", "WP-9999", "EQ-9999", "ART-9999", "TEC-9999", "OT-2026-0999", "C01", ""):
            with self.subTest(identifiant=identifiant):
                self.assertIsNone(self.entite(identifiant))
        self.assertEqual([(s["id"], s["mere"] and s["mere"]["id"]) for s in self.listes("demandeur")["savoir-faire"]], [
            ("WP-0003", None), ("WP-0006", "WP-0003"), ("WP-0004", None), ("WP-0005", None), ("WP-0010", None)])

    def test_textes_et_references(self):
        pompe = self.entite("EQ-0001")
        # Rubriques dans l'ordre du type (« En bref », « Astuces »), l'ancienne rubrique après.
        self.assertEqual([(r["nom"], len(r["phrases"])) for r in pompe["textes"]["rubriques"]],
                         [("En bref", 2), ("Astuces", 1), ("Ce qui revient", 1)])
        self.assertEqual((pompe["textes"]["pageId"], pompe["textes"]["origine"]), ("WP-0001", "IA"))
        self.assertEqual([(r["numero"], r["id"], r["date"], r["lien"]) for r in pompe["references"]], [
            (1, "OT-2026-0001", "2026-01-10", "OT-2026-0001"), (2, "OT-2026-0002", "2026-03-05", "OT-2026-0002"),
            (3, "OT-2026-0003", "2026-03-05", "OT-2026-0003"), (4, "OT-2026-0011", "2026-04-10", "OT-2026-0011")])
        self.assertEqual(pompe["references"][3]["machine"], {"equipementId": "EQ-0002", "titre": "PO-01.M — Moteur de PO-01",
                                                             "lien": "EQ-0002"})
        self.assertEqual([r["id"] for r in self.entite("WP-0003")["references"]], ["OT-2026-0003", "OT-2026-0001"])
        self.assertEqual([r["lien"] for r in self.entite("EQ-0001", "demandeur")["references"]], [None] * 4)
        # « À trancher » d'abord (en tête de la page, T137) : la phrase, puis les OT observés, sinon l'OT de l'entrée ;
        # puis les textes.
        resultat = self.page.evaluate("""() => {
          const recus = [];
          Wiki.contradictionsDe = (reperes, options) => {
            recus.push([reperes, options.profil, options.responsable]);
            return reperes.id === 'EQ-0001' ? [{ phrase: 'Fuite [OT-2026-0012]', ot: ['OT-2026-0014'], otSource: 'OT-2026-0013' },
              { phrase: 'Bruit', ot: [], otSource: 'OT-2026-0015' }, { phrase: 'Redite [OT-2026-0001]', ot: [], otSource: 'OT-2026-0001' }] : [];
          };
          Wiki.enAttenteDe = (reperes, options) => (options.responsable ? [{ page: reperes.id }] : []);
          try {
            return { pompe: Wiki.entite('EQ-0001', { profil: 'responsable' }), joint: Wiki.entite('ART-0002', { profil: 'technicien' }),
                     panne: Wiki.entite('PANNE-S01', { profil: 'responsable' }), recus };
          } finally {
            delete Wiki.contradictionsDe;
            delete Wiki.enAttenteDe;
          }
        }""")
        self.assertEqual([r["id"] for r in resultat["pompe"]["references"]], [
            "OT-2026-0012", "OT-2026-0014", "OT-2026-0015", "OT-2026-0001", "OT-2026-0002", "OT-2026-0003", "OT-2026-0011"])
        self.assertEqual([r["numero"] for r in resultat["pompe"]["references"]], list(range(1, 8)))
        self.assertEqual(resultat["pompe"]["enAttente"], [{"page": "EQ-0001"}])
        self.assertEqual((resultat["joint"]["aTrancher"], resultat["joint"]["enAttente"]), ([], []))
        self.assertEqual((resultat["panne"]["aTrancher"], resultat["panne"]["enAttente"]), ([], []))    # page calculée
        self.assertEqual(resultat["recus"], [
            [{"id": "EQ-0001", "pageId": "WP-0001", "type": "équipement", "titre": "PO-01 — Pompe A"}, "responsable", True],
            [{"id": "ART-0002", "pageId": "", "type": "composant", "titre": "Joint torique"}, "technicien", False]])
        # Wiki.references seule, et le calcul Python.
        textes = {"rubriques": [{"nom": "En bref", "phrases": ["A [OT-2026-0003] [OT-2026-0001]", "B [OT-2026-0003]"]},
                                {"nom": "Astuces", "phrases": ["C [OT-2026-0002]"]}]}
        a_trancher = [{"phrase": "D [OT-2026-0004]", "ot": [], "otSource": "OT-2026-0001"}, {"phrase": "E", "ot": ["OT-2026-0005"]}]
        attendu = ["OT-2026-0004", "OT-2026-0001", "OT-2026-0005", "OT-2026-0003", "OT-2026-0002"]
        self.assertEqual(self.page.evaluate("([t, a]) => Wiki.references(t, a)", [textes, a_trancher]), attendu)
        from calcul_wiki import references
        self.assertEqual(references(textes, a_trancher), attendu)

    def test_visibilite_par_profil(self):
        demandeur = {p: self.entites(["TEC-0001", "OT-2026-0001", "ART-0001", "EQ-0001"], p) for p in PROFILS}
        tec, intervention, article, machine = demandeur["demandeur"]
        self.assertEqual((tec, intervention), (None, None))
        self.assertNotIn("Prix unitaire", faits(article))
        self.assertTrue(all("prixUnitaire" not in c for c in article["sections"]["commandes"]))
        self.assertEqual(article["liens"], {"machine": True, "panne": True, "article": True, "savoir-faire": True,
                                            "technicien": False, "intervention": False})
        self.assertEqual({e["lien"] for e in machine["sections"]["interventions"]}, {None})
        self.assertEqual({t["lien"] for e in machine["sections"]["interventions"] for t in e["techniciens"]}, {None})
        self.assertEqual({s["lien"] for s in article["sections"]["sorties"]}, {None})
        self.assertEqual([t["nom"] for t in machine["sections"]["interventions"][0]["techniciens"]], ["Paul Martin"])
        self.assertEqual((self.listes("demandeur")["technicien"], self.listes("demandeur")["intervention"]), (None, None))
        # Sans profil donné ni application : le plus restreint (demandeur).
        self.assertEqual(self.page.evaluate("""() => [Wiki.entite('TEC-0001'), Wiki.entite('OT-2026-0001'),
          Wiki.entite('ART-0001').faits.some((f) => f.libelle === 'Prix unitaire')]"""), [None, None, False])
        self.assertEqual((self.accueil("demandeur")["nombres"]["techniciens"], self.accueil("demandeur")["habilitations"],
                          self.accueil("demandeur")["suivi"]), (None, None, None))
        # Technicien : tout sauf le taux horaire ; responsable : tout.
        tec, intervention, article, _ = demandeur["technicien"]
        self.assertNotIn("Taux horaire", faits(tec))
        self.assertEqual((faits(article)["Prix unitaire"], intervention["id"]), (12.5, "OT-2026-0001"))
        self.assertEqual(self.accueil("technicien")["suivi"], None)
        tec, _, article, _ = demandeur["responsable"]
        self.assertEqual((faits(tec)["Taux horaire"], faits(article)["Prix unitaire"]), (40, 12.5))
        self.assertTrue(all(t.get("lien") for t in self.listes("technicien")["technicien"]))

    def test_accueil_suivi_du_wiki(self):
        accueil = self.accueil("responsable")
        self.assertEqual(accueil["suivi"], {"aValider": 2, "aTrancher": 1, "enEchec": 2})
        self.assertEqual(accueil["nombres"], {"machines": 7, "pannes": 3, "articles": 5, "techniciens": 3, "savoirFaire": 5,
                                              "interventions": 15, "cloturees": 9})
        self.assertEqual([m["equipementId"] for m in accueil["machinesPlusDInterventions"]], ["EQ-0001", "EQ-0004", "EQ-0002"])
        self.assertEqual(accueil["pannePlusFrequente"]["id"], "PANNE-S01")
        self.assertEqual(ids(accueil["dernieres"]), ["OT-2026-0015", "OT-2026-0014", "OT-2026-0013", "OT-2026-0004",
                                                     "OT-2026-0012", "OT-2026-0011", "OT-2026-0002", "OT-2026-0003", "OT-2026-0001"])

    def test_aucune_ecriture_ni_appel_reseau(self):
        resultat = self.page.evaluate("""([ids, types, maintenant]) => {
          const photo = () => JSON.stringify(Schema.nomsTables().map((nom) => [nom, Donnees.lignes(nom)]));
          const avant = photo();
          let ecritures = 0;
          const modifier = Donnees.modifier;
          Donnees.modifier = async (...arguments_) => { ecritures += 1; return modifier(...arguments_); };
          let pages = 0;
          try {
            ['demandeur', 'technicien', 'responsable'].forEach((profil) => {
              ids.forEach((id) => { if (Wiki.entite(id, { profil, maintenant })) pages += 1; });
              types.forEach((type) => Wiki.listeEntites(type, { profil, maintenant }));
              Wiki.accueilEncyclopedie({ profil, maintenant });
            });
          } finally {
            Donnees.modifier = modifier;
          }
          return { identique: photo() === avant, ecritures, pages };
        }""", [IDS_BASE, list(TYPES), MAINTENANT])
        self.assertEqual((resultat["identique"], resultat["ecritures"]), (True, 0))
        self.assertGreater(resultat["pages"], 80)
        self.assertEqual(self.requetes_reseau(), [])


class TestSuiviDuWiki(CasEntites):
    """Suivi du wiki de l'accueil (à valider, à trancher, en échec) : valeurs écrites à la main et calcul Python
    (relecture de T136 : le test qui le comparait à Wiki.compteurs, retiré par la refonte 2, était toujours sauté)."""

    def test_suivi_egal_au_calcul_python(self):
        self.charger(BASE)
        suivi = self.page.evaluate("Wiki.accueilEncyclopedie({ profil: 'responsable', maintenant: '2026-10-19 10:00' }).suivi")
        # À valider : WJ-00002, WJ-00010 ; à trancher : la contradiction ouverte de WJ-00001 ; en échec : OT-2026-0003
        # (refusé seulement) et OT-2026-0011 (rejeté puis refusé) — pas OT-2026-0004 (relancé, en file) ni OT-2026-0012
        # (refusé puis rejeté : sa dernière entrée est rejetée).
        self.assertEqual(suivi, {"aValider": 2, "aTrancher": 1, "enEchec": 2})
        self.assertEqual(suivi, CalculWiki(BASE).suivi())
        for profil in ("demandeur", "technicien"):
            self.assertIsNone(self.accueil(profil)["suivi"], profil)


class TestJeuDeCharge(CasEntites):
    """D101 : une page d'entité, une liste et l'accueil en moins de 500 ms sur le jeu de charge (500 équipements, 5 000 OT)."""

    def test_pages_rapides_sur_le_jeu_de_charge(self):
        with tempfile.TemporaryDirectory() as dossier:
            resultat = subprocess.run([sys.executable, str(RACINE / "outils" / "generer_demo.py"), "--volume", "500,5000",
                                       "--sortie", dossier, "--sans-js"], capture_output=True, cwd=RACINE)
            self.assertEqual(resultat.returncode, 0, resultat.stdout.decode("utf-8", "replace"))
            tables = {f.stem: f.read_bytes().decode("utf-8-sig") for f in Path(dossier).glob("*.csv")}
        self.charger(tables)
        durees = self.page.evaluate("""() => {
          const mesurer = (calcul) => { const debut = performance.now(); calcul(); return performance.now() - debut; };
          const plus = (champ) => {
            const nombres = new Map();
            Donnees.lignes('ordres_travail').forEach((ot) => nombres.set(ot[champ], (nombres.get(ot[champ]) || 0) + 1));
            return Array.from(nombres).filter(([cle]) => cle).sort((a, b) => b[1] - a[1])[0][0];
          };
          const ids = [plus('equipement_id'), Donnees.lignes('articles')[0].id, Wiki.idPanne(plus('symptome_code')),
            plus('technicien_id'), Donnees.lignes('ordres_travail')[0].id];
          const resultat = {};
          ids.forEach((id) => { resultat[id] = mesurer(() => Wiki.entite(id, { profil: 'responsable' })); });
          ['machine', 'article', 'intervention'].forEach((type) => {
            resultat['liste ' + type] = mesurer(() => Wiki.listeEntites(type, { profil: 'responsable' }));
          });
          resultat.accueil = mesurer(() => Wiki.accueilEncyclopedie({ profil: 'responsable' }));
          resultat.ordres = Donnees.lignes('ordres_travail').length;
          return resultat;
        }""")
        self.assertEqual(durees.pop("ordres"), 5000)
        sys.stderr.write("\n  durées sur le jeu de charge (ms) : %s\n" % ", ".join("%s %.0f" % (k, v) for k, v in durees.items()))
        for nom, duree in durees.items():
            with self.subTest(mesure=nom):
                self.assertLess(duree, BUDGET_PAGE_MS)


if __name__ == "__main__":
    unittest.main()
