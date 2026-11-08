#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Générateur du jeu de démo de Prévo (docs/ARCHITECTURE.md §11, brief §13).

Ce script fabrique, de façon REPRODUCTIBLE (graine fixe, date de référence fixe), un atelier
fictif complet : équipements, techniciens, articles, gammes, treize mois d'historique de pannes, de
préventif, de mouvements de stock et d'achats... Aucune personne ni entreprise réelle : tous les
noms sont inventés.

Depuis le lot 3 (ARCHITECTURE.md §15.12, D49), le jeu contient aussi : des contrôles réglementaires
dans les quatre statuts (§15.7), un planning chargé sur les 4 semaines qui commencent à la date de
référence (dont une semaine en surcharge, l'arrêt programmé de fin octobre), des OT « Préparé » à
planifier, une panne clôturée sans durée d'arrêt et, au journal, l'historique des statuts des pannes
des 3 derniers mois (dont une panne qui a attendu une pièce). Ces ajouts tirent leur hasard dans un
générateur à part (GRAINE_LOT3) : le reste du jeu des lots 1 et 2 ne change pas.

Depuis le lot 3 bis (ARCHITECTURE.md §16.8, D62), le jeu montre aussi le préventif suggéré (§16.3) : deux
gammes récentes, l'une avec une anomalie à 2 de ses 4 dernières visites (S3), l'autre sur un équipement
de criticité A qui remplirait S4 sans sa criticité ; et, au journal, une suggestion ignorée (avec son motif)
revenue depuis avec assez de nouvelles pannes. Ces ajouts tirent leur hasard dans un troisième générateur
(GRAINE_LOT3BIS) : le contenu des lignes des lots 1 à 3 ne change pas (seuls les numéros des OT et des DI
postérieurs aux nouvelles lignes se décalent, puisqu'ils suivent l'ordre chronologique).

Sorties par défaut :
    donnees/demo/<table>.csv          les 23 fichiers CSV (format ARCHITECTURE.md §3.1)
    js/demo-donnees.js                les mêmes textes, prêts à être chargés par la page (mode démo)
    tests/fixtures/demo-scenarios.json  identifiants des objets de scénario (voir plus bas)

Utilisation (depuis la racine du projet) :
    py outils/generer_demo.py                          jeu de démo, 13 mois d'historique
    py outils/generer_demo.py --mois 6                 historique plus court (6 mois)
    py outils/generer_demo.py --sans-js                CSV (et identifiants de scénario) seulement
    py outils/generer_demo.py --volume 500,5000 --sortie C:\\temp\\charge
                                                       jeu de charge (500 équipements, 5 000 OT, 24 mois)

Le script s'auto-vérifie (clés étrangères, listes de valeurs, règles RG1 à RG6, stock, scénarios ; au
lot 3 : statuts des contrôles, surcharge du planning, cohérence du journal avec les OT ; au lot 3 bis :
règles des suggestions recalculées en Python à la date de référence) et s'arrête avec un message clair
au moindre défaut.

Identifiants de scénario (tests/fixtures/demo-scenarios.json, ARCHITECTURE.md §14.8)
-----------------------------------------------------------------------------------
Écrit seulement pour le jeu de démo par défaut (ni avec --sortie, ni avec --volume ; l'option
--fichier-scenarios l'écrit ailleurs). Les tests lisent ce fichier (tests/commun.py,
scenarios_demo()) au lieu d'écrire des numéros d'OT ou de DI en dur. Chaque clé désigne une ligne
du jeu (ou une liste triée de lignes, ou un code) qui a la propriété annoncée :

  OT par statut et OT remarquables (table ordres_travail)
    ot_statut_cree                   OT « Créé » : le préventif de la gamme compteur échue de CH-01
    ot_statut_prepare                OT correctif « Préparé », en retard (VE-02, P4)
    ot_statut_planifie               OT correctif « Planifié », pas en retard (CU-01)
    ot_statut_en_cours               OT correctif « En cours », P2, qui porte une DI regroupée (EM-01)
    ot_statut_en_attente             OT « En attente » (motif pièce), en retard (AE-02)
    ot_statut_cloture_technique      OT « Clôturé techniquement » le plus récent
    ot_statut_cloture_administratif  OT « Clôturé administrativement » le plus récent
    ot_statut_annule                 OT « Annulé » (doublon, motif d'annulation renseigné)
    ot_p1_ouvert                     le seul OT P1 ouvert : CP-01 en cours de dépannage
    ot_en_retard                     liste : OT ouverts dont la date prévue est passée (date de référence)
    ot_en_cours_regroupe             le seul OT ouvert de son équipement, « En cours », avec une DI regroupée
    ot_preventif_ouvert              OT préventif ouvert « Planifié » et en retard (CN-01, TEC-0004)
    ot_preventif_cloture             le plus ancien OT préventif clôturé
    ot_fuite_garniture_po02          dernière fuite de garniture de PO-02 : correctif clôturé, 1 kit prévu
    ot_de_di_acceptee                OT créé par la DI di_statut_acceptee
    preventif_anomalie               OT préventif clôturé avec anomalie constatée, DI liée acceptée (PR-01)
    preventif_anomalie_nouvelle      OT préventif clôturé avec anomalie constatée, DI liée « Nouvelle » (GF-01)
    ot_correctif_anomalie            correctif clôturé, issu de la DI liée de preventif_anomalie
  DI (table demandes)
    di_statut_nouvelle               une DI « Nouvelle » (ET-01)
    di_statut_acceptee               la plus ancienne DI « Acceptée » (avec son OT)
    di_acceptee_autre                la deuxième DI « Acceptée » (avec son OT)
    di_statut_regroupee              DI « Regroupée » sur ot_en_cours_regroupe
    di_statut_differee               DI « Différée » (motif renseigné, CV-01)
    di_statut_refusee                la seule DI « Refusée » (motif renseigné, CU-01)
    di_nouvelles                     liste : toutes les DI « Nouvelle »
    di_securite                      DI « Nouvelle » d'impact sécurité (AE-04, donc P1)
    di_nouvelle_p4                   DI « Nouvelle », criticité C × gêne = P4 (PO-03)
    di_nouvelle_sans_ot_ouvert       DI « Nouvelle » d'un équipement sans OT ouvert, P4 (ET-01)
    di_nouvelle_degradee             DI « Nouvelle » d'impact dégradé (PR-01, demandeur Sarah Colin)
    di_plus_ancienne                 DI de plus petit numéro (première ligne du fichier), acceptée
    di_anomalie_acceptee             DI liée (ot_origine_id) à preventif_anomalie, acceptée
    di_anomalie_nouvelle             DI liée (ot_origine_id) à preventif_anomalie_nouvelle, « Nouvelle »
    di_causes_equipement             dernière DI de PO-02 avec le code symptôme S01 (fuite)
    di_causes_insuffisantes          DI « Nouvelle » de PO-03 avec le code symptôme S02 (bruit)
    di_sans_symptome_code            DI sans code symptôme (la DI différée)
  Préventif, compteurs
    gamme_mensuelle_echue            gamme date de 30 jours échue SANS OT ouvert (CV-01)
    gamme_compteur_echue             gamme compteur échue avec un OT ouvert (CH-01)
    gamme_compteur_sans_ot           gamme compteur non échue, sans OT ouvert (CP-01, 2000 h)
    gamme_seuil                      gamme seuil, dernier relevé SOUS le seuil (séparateur de CP-01)
    gamme_sans_constat               gamme mensuelle de VE-01 : préventifs successifs sans constat
    compteur_horaire                 compteur horaire de marche de CP-01
    compteur_seuil                   point de mesure de la gamme seuil (perte de charge, bar)
  Magasin
    kit_garniture                    article « Kit garniture mécanique PO-02 » (stock >= 2)
    articles_sous_point_commande     liste : les 3 articles dont le stock est sous le point de commande
    achat_statut_demandee            premier achat « demandée »
    achat_statut_commandee           achat « commandée »
    achat_statut_recue               dernier achat « reçue » (entrée de stock correspondante)
  Parc, techniciens
    equipement_br                    AE-03 : habilitation BR requise
    equipement_panne_unique          BA-01 : une seule panne dans tout l'historique
    technicien_br_valide             TEC-0001 : BR valide à la date de référence
    technicien_br_echue              TEC-0004 : BR échue à la date de référence
  Causes fréquentes (ARCHITECTURE.md §14.5, minimum 5 cas)
    causes_equipement                PO-02 : au moins 5 correctifs clôturés de ce symptôme sur l'équipement
    causes_equipement_symptome       S01 (fuite) ; au moins 2 causes, la plus fréquente C01 (garniture usée)
    causes_equipement_2              CP-01 : un autre équipement à au moins 5 cas d'un même symptôme
    causes_equipement_2_symptome     S04 (échauffement)
    causes_modele                    CV-03 : moins de 5 cas propres, au moins 5 avec sa marque et son modèle
    causes_modele_symptome           S05 (arrêt intempestif)
    causes_insuffisantes             PO-03 : de 1 à 4 cas en tout (aucun autre équipement du même modèle)
    causes_insuffisantes_symptome    S02 (bruit anormal)
  Lot 3 (ARCHITECTURE.md §15.12) : contrôles réglementaires (statut à la date de référence, §15.7)
    controle_en_retard               VGP du chariot CH-01 (6 mois) : prochaine date dépassée
    controle_observations            inspection du réservoir RA-01 : observations non levées
    controle_a_planifier             installations électriques (AE-01) : prochaine date dans moins de 30 jours
    controle_a_jour                  VGP du pont roulant PT-01 : à jour
  2.2 (T417) : réserves des contrôles (D193, CONCEPTION-L2-L3 §3)
    controle_reserves                contrôle d'AE-01 (12/11/2025) : une réserve levée avec son OT, une ouverte à échéance à venir
    reserve_en_retard                réserve du purgeur de RA-01 (03/04/2025) : ouverte, échéance par défaut passée
    reserve_levee                    réserve d'AE-01 levée le 09/12/2025 (levee 1, commentaire, OT réglementaire clôturé lié)
    reserve_a_echeance               réserve ouverte d'AE-01 : échéance saisie le 15/12/2026, à venir
  Lot 3 : planning des 4 semaines qui commencent à la date de référence (§15.5)
    technicien_surcharge             TEC-0002 : plus d'heures prévues que sa capacité dans la semaine_surcharge
    semaine_surcharge                lundi (AAAA-MM-JJ) de la semaine en surcharge : l'arrêt programmé
    ot_a_planifier                   OT « Préparé » sans technicien, pièces en stock, sans habilitation (CV-02.M)
    ot_a_planifier_br                OT « Préparé » sans technicien sur l'équipement qui exige BR (AE-03)
    ot_a_planifier_piece_manquante   OT « Préparé » dont une pièce manque en stock : refus RG3 (CU-01.CH)
  Lot 3 : pannes et indicateurs (§15.3)
    panne_attente_pieces             panne clôturée de PO-01 passée par « En attente : Pièce : … » (journal)
    panne_sans_duree                 panne clôturée de CV-02 sans durée d'arrêt (duree_arret_h vide)
    equipements_calcul_main          liste : CP-01 (A), PO-01, CV-02 : heures connues, pannes sur 12 mois
  Lot 3 bis (§16.8) : préventif suggéré, règles du §16.3 à la date de référence, réglages par défaut
    suggestion_creer                 clé S1 ouverte : CV-02, capteur encrassé (C04), aucune gamme active
    suggestion_revoir                clé S2 ouverte : PO-02, garniture usée (C01) malgré sa gamme
    suggestion_anomalies             clé S3 ouverte : gamme de RA-01, anomalie à 2 des 4 dernières visites
    suggestion_allonger              clé S4 ouverte : gamme mensuelle de VE-01, visites de suite sans anomalie
    suggestion_refus_criticite_a     gamme de GF-01 (criticité A) : remplirait S4, refusée pour sa seule criticité
    suggestion_sous_seuil            {equipement, cause} : CP-01.SEC, C05, 2 correctifs (seuil - 1), sans gamme
    suggestion_ignoree_revenue       clé S2 de CP-01 (C05) : ignorée au journal, revenue avec 3 pannes depuis

Journal (lot 3) : pour chaque panne des 3 derniers mois (OT correctif avec arrêt de production, plus une
semaine de marge pour le décalage de la démo), les entrées que Prévo aurait écrites, au format exact de
Donnees.modifier (« création — acceptation de DI-… », « modification : statut, date_debut — statut
Créé → En cours »…), horodatées par les dates de l'OT et de sa DI, poste « Poste démo ». Depuis le lot 3
bis, il porte aussi une décision sur une suggestion, écrite comme Donnees.journaliser l'écrit (action
brute « suggestion <clé> ignorée : <motif> », table equipements, §16.4).

Organisation du fichier :
    1. Schéma et écriture CSV (règles §3.1 et §3.2)
    2. Petits outils (dates, heures ouvrées, nombres)
    3. Catalogue de contenu (équipements, scénarios de pannes, articles, gammes...)
    4. Génération table par table
    5. Génération de l'historique (DI, OT, préventif)
    5 bis. Lot 3 : planning, OT à planifier, pannes remarquables, journal des statuts
    5 ter. Lot 3 bis : gammes récentes et leurs visites, suggestion ignorée au journal
    6. Stock, achats, mouvements
    7. Identifiants, auto-vérification (dont 7 bis : règles des suggestions en Python), identifiants de
       scénario, écriture, ligne de commande
"""
import argparse
import calendar
import csv
import io
import json
import math
import random
import re
import sys
import time
import urllib.parse
from contextlib import contextmanager, nullcontext
from datetime import date, datetime, timedelta
from itertools import groupby
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_DEMO = RACINE / 'donnees' / 'demo'
FICHIER_JS = RACINE / 'js' / 'demo-donnees.js'
FICHIER_SCENARIOS = RACINE / 'tests' / 'fixtures' / 'demo-scenarios.json'
DOSSIER_WIKI_FIGE = RACINE / 'outils'   # demo_wiki_pages.csv et demo_wiki_journal.csv (outils/wiki_demo.py figer)

GRAINE = 42                      # graine fixe : deux exécutions donnent des fichiers identiques
GRAINE_LOT3 = 4203               # graine des ajouts du lot 3 (générateur à part : le reste ne bouge pas)
GRAINE_LOT3BIS = 4204            # graine des ajouts du lot 3 bis (même principe : les lots 1 à 3 ne bougent pas)
GRAINE_LOT6 = 4206               # graine des ajouts du lot 6 : astuces et OT de scénario du wiki (D109, D110)
DATE_REFERENCE = '2026-10-19'    # « aujourd'hui » du jeu de démo (un lundi)
MOIS_PAR_DEFAUT = 13             # durée de l'historique (ARCHITECTURE.md §14.8)
PART_DI_AVEC_CODE = 0.8          # proportion des DI dont le demandeur a choisi un code symptôme
HEURE_COURANTE = 9.0             # il est 9 h 00 à la date de référence
FACTEUR_TAUX_DEMO = 1.3          # règle le nombre de pannes « de fond » du jeu de démo

NOM_ENTREPRISE = 'Atelier des Trois Vallées (démo)'


# =============================================================================
# 1. SCHÉMA ET ÉCRITURE CSV
# =============================================================================

# Copie en Python de js/schema.js (champs et ordre EXACTS de chaque table). Le test
# tests/test_demo.py compare cette description au vrai Schema lu dans Chromium : en cas de
# modification de js/schema.js, mettre à jour ce tableau (le test échoue sinon).
# Les derniers champs d'equipements (valeur_remplacement), de demandes (symptome_code,
# ot_origine_id) et d'ordres_travail (anomalie_constatee) sont ceux de la version 2 du format
# (ARCHITECTURE.md §14.1) : valeur de remplacement de chaque équipement, code symptôme de la plupart
# des DI, DI liée à un OT préventif qui a constaté une anomalie (anomalie_constatee = 1).
# Syntaxe d'un champ :  nom:type    nom:type!    (« ! » = champ protégé, §3.2)
#   ref>table            clé étrangère vers table.clé
#   ref>table.champ=fam  clé étrangère vers table.champ, filtrée sur famille = fam
#   choix[a|b|c]         liste de valeurs canoniques
DEFINITION_SCHEMA = {
    'localisations': 'id:id libelle:texte parent_id:ref>localisations type:choix[site|atelier|ligne]',
    'equipements': (
        'id:id repere:texte! designation:texte localisation_id:ref>localisations '
        'parent_id:ref>equipements marque:texte modele:texte num_serie:texte! date_mes:date '
        'criticite:choix[A|B|C] statut:choix[en service|arrêt|rebut] heures_fonct_jour:decimal '
        'habilitation_requise:texte consignation:texte_long document:document actif:booleen '
        'valeur_remplacement:decimal cout_arret_h:decimal'),
    'demandes': (
        'id:id date_heure:date_heure demandeur:texte equipement_id:ref>equipements '
        'symptome:texte_long impact:choix[sécurité|arrêt|dégradé|gêne] description:texte_long '
        'photo:document statut:choix[Nouvelle|Acceptée|Regroupée|Différée|Refusée] '
        'motif_decision:texte_long date_decision:date_heure ot_id:ref>ordres_travail '
        'symptome_code:ref>codes_defaillance.code=symptôme ot_origine_id:ref>ordres_travail'),
    'ordres_travail': (
        'id:id origine:choix[DI|préventif|urgence|manuel] di_id:ref>demandes gamme_id:ref>gammes '
        'equipement_id:ref>equipements '
        'type:choix[correctif immédiat|correctif différé|préventif systématique|préventif conditionnel|'
        'amélioration|réglementaire] priorite:choix[P1|P2|P3|P4] '
        'statut:choix[Créé|Préparé|Planifié|En cours|En attente|Clôturé techniquement|'
        'Clôturé administrativement|Annulé] '
        'motif_attente:texte_long titre:texte travail_a_faire:texte_long consignes:texte_long '
        'date_creation:date_heure date_prevue:date technicien_id:ref>techniciens '
        'temps_prevu_h:decimal date_debut:date_heure date_fin:date_heure arret_production:booleen '
        'duree_arret_h:decimal symptome_code:ref>codes_defaillance.code=symptôme '
        'cause_code:ref>codes_defaillance.code=cause remede_code:ref>codes_defaillance.code=remède '
        'compte_rendu:texte_long remise_service:booleen cout_soustraitance:decimal '
        'date_cloture_tech:date_heure date_cloture_admin:date_heure motif_annulation:texte_long '
        'ot_lie_id:ref>ordres_travail anomalie_constatee:booleen astuce:texte_long habilitation_requise:texte'),
    'ot_operations': (
        'id:id ot_id:ref>ordres_travail ordre:entier operation:texte valeur_attendue:texte '
        'fait:booleen valeur_mesuree:texte'),
    'ot_pieces': 'id:id ot_id:ref>ordres_travail article_id:ref>articles quantite_prevue:decimal',
    'ot_temps': 'id:id ot_id:ref>ordres_travail technicien_id:ref>techniciens date:date heures:decimal',
    'gammes': (
        'id:id equipement_id:ref>equipements libelle:texte declencheur:choix[date|compteur|seuil] '
        'periodicite_jours:entier compteur_id:ref>compteurs periodicite_unites:decimal seuil:decimal '
        'avance_jours:entier derniere_realisation:date releve_derniere_realisation:decimal '
        'prochaine_echeance:date temps_prevu_h:decimal consignes:texte_long actif:booleen'),
    'gamme_operations': (
        'id:id gamme_id:ref>gammes ordre:entier operation:texte valeur_attendue:texte'),
    'articles': (
        'id:id reference:texte! designation:texte fabricant:texte ref_fabricant:texte! '
        'emplacement:texte unite:texte stock:decimal stock_securite:decimal point_commande:decimal '
        'qte_commande:decimal delai_jours:entier prix_unitaire:decimal fournisseur_id:ref>fournisseurs '
        'critique:booleen actif:booleen'),
    'article_equipement': (
        'id:id article_id:ref>articles equipement_id:ref>equipements quantite:decimal'),
    'mouvements_stock': (
        'id:id date:date_heure article_id:ref>articles type:choix[entrée|sortie|inventaire|retour] '
        'quantite:decimal ot_id:ref>ordres_travail utilisateur:texte commentaire:texte_long'),
    'techniciens': (
        'id:id nom:texte prenom:texte metier:texte taux_horaire:decimal capacite_h_semaine:decimal '
        'actif:booleen'),
    'habilitations': (
        'id:id technicien_id:ref>techniciens intitule:texte date_obtention:date date_echeance:date '
        'recyclage_mois:entier justificatif:document catalogue_id:texte '
        'nature_source:choix[obligation|norme|recommandation]'),
    'compteurs': 'id:id equipement_id:ref>equipements libelle:texte unite:texte',
    'releves': 'id:id compteur_id:ref>compteurs date:date valeur:decimal utilisateur:texte',
    'controles_reglementaires': (
        'id:id equipement_id:ref>equipements nature:texte texte_reference:texte periodicite_mois:entier '
        'organisme:texte derniere_date:date prochaine_date:date rapport:document observations:texte_long '
        'observations_levees:booleen source_periodicite:choix[catalogue|saisie] '
        'nature_source:choix[obligation|norme|recommandation] catalogue_id:texte catalogue_relu_le:date'),
    'codes_defaillance': (
        'id:id famille:choix[symptôme|cause|remède] code:texte libelle:texte'),
    'fournisseurs': 'id:id nom:texte contact:texte telephone:texte! email:texte',
    'achats': (
        'id:id date:date article_id:ref>articles fournisseur_id:ref>fournisseurs quantite:decimal '
        'prix_unitaire:decimal statut:choix[demandée|commandée|reçue] date_reception:date'),
    'parametres': 'cle:id valeur:texte',
    'journal': (
        'id:id date_heure:date_heure poste:texte profil:texte table:texte id_ligne:texte action:texte'),
    # Format 3 (lot 6 refondu, ARCHITECTURE.md §20.2) : pages et journal du wiki de maintenance.
    'wiki_pages': (
        'id:id type:choix[équipement|composant|savoir-faire] titre:texte cle:texte '
        'equipement_id:ref>equipements article_id:ref>articles cause_code:ref>codes_defaillance.code=cause '
        'rattache_a:ref>wiki_pages texte:texte_long ot_cites:texte liens:texte version:entier '
        'origine:choix[IA|manuel|IA et manuel] modele:texte derniere_entree:ref>wiki_journal valide_par:texte '
        'valide_le:date_heure cree_le:date_heure modifie_le:date_heure statut:choix[active|archivée]'),
    'wiki_journal': (
        'id:id nature:choix[ingestion|manuel|décision] ot_id:ref>ordres_travail date_intervention:date_heure '
        'statut:choix[en file|à valider|validée|rejetée|à refaire|refusée|rien à ajouter|appliquée] '
        'anterieure:booleen ordre:entier pages:texte changements:texte_long contradictions:texte_long '
        'raisons:texte_long modele:texte essais:entier cree_le:date_heure traite_le:date_heure '
        'decide_par:texte decide_le:date_heure motif:texte_long'),
    # Format 4 (2.2, CONCEPTION-L1 §2.2) : réserves des contrôles, garanties et contrats de prestataires.
    'reserves_controle': (
        'id:id controle_id:ref>controles_reglementaires date_controle:date texte:texte_long '
        'gravite:choix[mineure|majeure|critique] echeance_levee:date levee:booleen date_levee:date '
        'commentaire_levee:texte_long ot_id:ref>ordres_travail'),
    'garanties': (
        'id:id equipement_id:ref>equipements fournisseur_id:ref>fournisseurs date_debut:date date_fin:date '
        'conditions:texte_long document:document actif:booleen'),
    'contrats_prestataires': (
        'id:id fournisseur_id:ref>fournisseurs objet:texte equipement_ids:texte perimetre:texte_long '
        'date_debut:date date_fin:date preavis_mois:entier reconduction_tacite:booleen reconduction_mois:entier '
        'montant_annuel:decimal document:document actif:booleen'),
}

# Format des identifiants : (préfixe, nombre de chiffres, numérotation annuelle ?).
# Copie de Schema.tables[...].identifiant (js/schema.js), comparée par le test.
IDENTIFIANTS = {
    'localisations': ('LOC-', 4, False), 'equipements': ('EQ-', 4, False),
    'demandes': ('DI-', 4, True), 'ordres_travail': ('OT-', 4, True),
    'ot_operations': ('OTO-', 6, False), 'ot_pieces': ('OTP-', 6, False),
    'ot_temps': ('OTT-', 6, False), 'gammes': ('GAM-', 4, False),
    'gamme_operations': ('GOP-', 6, False), 'articles': ('ART-', 4, False),
    'article_equipement': ('AEQ-', 5, False), 'mouvements_stock': ('MVT-', 6, False),
    'techniciens': ('TEC-', 4, False), 'habilitations': ('HAB-', 4, False),
    'compteurs': ('CPT-', 4, False), 'releves': ('REL-', 6, False),
    'controles_reglementaires': ('CTR-', 4, False), 'codes_defaillance': ('CD-', 4, False),
    'fournisseurs': ('FOU-', 4, False), 'achats': ('ACH-', 4, False),
    'journal': ('J-', 4, False),     # J-AAAAMMJJHHMMSS-XXXX : 4 caractères aléatoires (écrit par l'application)
    'wiki_pages': ('WP-', 4, False), 'wiki_journal': ('WJ-', 5, False),
    'reserves_controle': ('RES-', 5, False), 'garanties': ('GAR-', 4, False),
    'contrats_prestataires': ('CTP-', 4, False),
}


def lire_definition(texte):
    """Transforme la description d'une table en liste de dictionnaires (un par champ)."""
    champs = []
    for jeton in re.findall(r'[^\s\[\]]+(?:\[[^\]]*\])?', texte):
        nom, description = jeton.split(':', 1)
        champ = {'nom': nom, 'protege': description.endswith('!')}
        description = description.rstrip('!')
        if description.startswith('ref>'):
            champ['type'] = 'ref'
            cible, _, filtre = description[4:].partition('=')
            table, _, champ_cible = cible.partition('.')
            champ['table'] = table
            champ['champCible'] = champ_cible
            champ['famille'] = filtre
        elif description.startswith('choix['):
            champ['type'] = 'choix'
            champ['valeurs'] = description[6:-1].split('|')
        else:
            champ['type'] = description
        champs.append(champ)
    return champs


CHAMPS = {table: lire_definition(texte) for table, texte in DEFINITION_SCHEMA.items()}
NOMS_TABLES = list(DEFINITION_SCHEMA.keys())


def decrire_schema():
    """Description du schéma Python, comparée par les tests à celle de js/schema.js."""
    return {table: {'champs': CHAMPS[table],
                    'identifiant': list(IDENTIFIANTS.get(table, ('', 0, False)))}
            for table in NOMS_TABLES}


# ---------------------------------------------------------------------------
# Protection par apostrophe (ARCHITECTURE.md §3.2)
# ---------------------------------------------------------------------------

# ATTENTION : ces règles sont la copie EXACTE de Donnees.csv.aProteger (js/donnees.js).
# Les deux implémentations doivent rester identiques : si l'une change, changer l'autre.
MOTIFS_FORME_NUMERIQUE = [
    re.compile(r'[0-9]+([.,][0-9]+)?'),                          # nombre, zéros en tête, > 11 chiffres
    re.compile(r'[0-9]+([.,][0-9]+)?[eE][+-]?[0-9]+'),           # notation à exposant
    re.compile(r'[0-9]{1,4}[/.\-][0-9]{1,2}([/.\-][0-9]{1,4})?'),  # date ou fraction (1/2, 01-12)
    re.compile(r'[0-9]{1,2}:[0-9]{2}(:[0-9]{2})?'),              # heure
    re.compile(r'[0-9]+([.,][0-9]+)?\s?%'),                      # pourcentage
]
DEBUT_DANGEREUX = re.compile(r'[=+\-@\t\r]')   # formule ou tiret en tête


def ressemble_nombre_date_fraction(valeur):
    """Vrai si Excel risque d'abîmer la valeur (nombre, date, fraction, heure, pourcentage)."""
    # Retrait explicite de [ \t\r\n] aux deux bords (et non strip()) : identique à
    # ressembleNombreDateFraction dans js/donnees.js.
    valeur = valeur.strip(' \t\r\n')
    return any(motif.fullmatch(valeur) for motif in MOTIFS_FORME_NUMERIQUE)


def a_proteger(type_champ, protege, valeur):
    """Équivalent de Donnees.csv.aProteger : faut-il préfixer la valeur par une apostrophe ?"""
    if type_champ not in ('texte', 'texte_long') or valeur == '':
        return False
    return bool(protege
                or DEBUT_DANGEREUX.match(valeur)
                or valeur.startswith("'")
                or ressemble_nombre_date_fraction(valeur))


def ecrire_valeur(champ, valeur):
    """Valeur telle qu'elle est écrite dans le CSV (apostrophe de protection éventuelle)."""
    return "'" + valeur if a_proteger(champ['type'], champ['protege'], valeur) else valeur


# ---------------------------------------------------------------------------
# Sérialisation CSV (ARCHITECTURE.md §3.1)
# ---------------------------------------------------------------------------

def champ_csv(texte):
    """Guillemets RFC 4180 : seulement si le champ contient ; \" CR ou LF."""
    if any(caractere in texte for caractere in ';"\r\n'):
        return '"' + texte.replace('"', '""') + '"'
    return texte


def serialiser_table(table, lignes):
    """Texte CSV d'une table, SANS BOM : en-tête puis une ligne par enregistrement, CRLF partout."""
    champs = CHAMPS[table]
    morceaux = [';'.join(champ['nom'] for champ in champs)]
    for ligne in lignes:
        morceaux.append(';'.join(champ_csv(ecrire_valeur(champ, ligne[champ['nom']]))
                                 for champ in champs))
    return '\r\n'.join(morceaux) + '\r\n'


def ecrire_csv(dossier, textes):
    """Écrit les 23 fichiers CSV (BOM UTF-8 + CRLF) octet pour octet."""
    dossier.mkdir(parents=True, exist_ok=True)
    for table, texte in textes.items():
        (dossier / (table + '.csv')).write_bytes(b'\xef\xbb\xbf' + texte.encode('utf-8'))


def texte_scenarios(scenarios):
    """Texte JSON des identifiants de scénario : UTF-8, clés triées, indenté, fin de ligne LF (déterministe)."""
    return json.dumps(scenarios, ensure_ascii=False, indent=2, sort_keys=True) + '\n'


def ecrire_scenarios(chemin, scenarios):
    """Écrit tests/fixtures/demo-scenarios.json (octets identiques d'une exécution à l'autre)."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(texte_scenarios(scenarios).encode('utf-8'))


# Tables du wiki (le journal surtout : chaque changement porte le texte d'avant et d'après de sa page) : écrites par
# morceaux dans js/demo-donnees.js, qui reste ainsi sous 1 Mo avec un wiki complet (CS105 : chargement rapide ; wiki
# de la passe 6 : 1,32 Mo en chaînes JSON). Le texte est coupé après chaque fin de ligne (CRLF, ou « \n » écrit dans le
# JSON des changements), après chaque « "" » et avant chaque citation « [OT-… » ; chaque morceau distinct est écrit
# une fois, puis l'ordre des morceaux, et le navigateur les recolle en chargeant le fichier : même texte, caractère
# pour caractère (test_demo). Seulement quand c'est plus court : sans wiki, le fichier ne change pas.
TABLES_PAR_MORCEAUX = ('wiki_pages', 'wiki_journal')
COUPURES_MORCEAUX = re.compile(r'(?<=\\n)|(?<=\r\n)|(?<="")|(?= \[OT-)')
TAILLE_JS_MAX = 1000000          # octets : js/demo-donnees.js reste sous 1 Mo (CS105, ARCHITECTURE.md §20.12)


def litteral_table(table, texte):
    """Expression JavaScript du texte CSV d'une table : une chaîne JSON ; pour une table du wiki, quand c'est plus
    court, ses morceaux distincts suivis de leur ordre, recollés au chargement."""
    chaine = json.dumps(texte, ensure_ascii=False)
    if table not in TABLES_PAR_MORCEAUX:
        return chaine
    rangs, distincts, suite = {}, [], []
    for morceau in (m for m in COUPURES_MORCEAUX.split(texte) if m):
        if morceau not in rangs:
            rangs[morceau] = len(distincts)
            distincts.append(morceau)
        suite.append(rangs[morceau])
    if ''.join(distincts[rang] for rang in suite) != texte:
        raise ErreurCoherence('%s : découpe en morceaux infidèle' % table)
    morceaux = "((m, s) => s.map((r) => m[r]).join(''))(%s, %s)" % (json.dumps(distincts, ensure_ascii=False),
                                                                     json.dumps(suite, separators=(',', ':')))
    return morceaux if len(morceaux.encode('utf-8')) < len(chaine.encode('utf-8')) else chaine


def octets_js(textes):
    """Octets de js/demo-donnees.js : un objet DEMO_DONNEES qui contient le texte CSV de chaque table (litteral_table)."""
    lignes = [
        "'use strict';",
        "// Fichier généré, ne pas modifier : produit par outils/generer_demo.py (py outils/generer_demo.py).",
        "// Jeu de démo de Prévo : atelier fictif, aucune donnée réelle (ARCHITECTURE.md §11).",
        "",
        "const DEMO_DONNEES = {",
        "  dateReference: %s," % json.dumps(DATE_REFERENCE),
        "  tables: {",
    ]
    for table in NOMS_TABLES:
        lignes.append("    %s: %s," % (table, litteral_table(table, textes[table])))
    lignes += ["  },", "};", ""]
    return '\n'.join(lignes).encode('utf-8')


def ecrire_js(chemin, textes, octets=None):
    """Écrit js/demo-donnees.js (octets déjà calculés par octets_js, ou calculés ici)."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(octets if octets is not None else octets_js(textes))


# =============================================================================
# 2. PETITS OUTILS : DATES, HEURES OUVRÉES, NOMBRES
# =============================================================================

DEBUT_JOURNEE = 7.5     # 7 h 30
FIN_JOURNEE = 16.5      # 16 h 30


class ErreurCoherence(Exception):
    """Levée par l'auto-vérification quand le jeu généré n'est pas cohérent."""


def jour_depuis_texte(texte):
    return date.fromisoformat(texte)


def texte_date(jour):
    return jour.isoformat()


def texte_date_heure(instant_):
    return instant_.strftime('%Y-%m-%d %H:%M')


def ajouter_mois(jour, nombre):
    """Même jour du mois, `nombre` mois plus tôt ou plus tard (ramené à la fin du mois si besoin)."""
    total = jour.year * 12 + jour.month - 1 + nombre
    annee, mois = divmod(total, 12)
    mois += 1
    return date(annee, mois, min(jour.day, calendar.monthrange(annee, mois)[1]))


def jour_ouvre_apres(jour):
    """Le jour lui-même s'il est ouvré (lundi à vendredi), sinon le lundi suivant."""
    while jour.weekday() >= 5:
        jour += timedelta(days=1)
    return jour


def jour_ouvre_avant(jour):
    """Le jour lui-même s'il est ouvré, sinon le vendredi précédent."""
    while jour.weekday() >= 5:
        jour -= timedelta(days=1)
    return jour


def instant(jour, heure):
    """Date-heure à partir d'un jour et d'une heure décimale (7.5 = 7 h 30)."""
    return datetime(jour.year, jour.month, jour.day) + timedelta(minutes=int(round(heure * 60)))


def heure_decimale(moment):
    return moment.hour + moment.minute / 60.0


def arrondir_minute(moment):
    return (moment + timedelta(seconds=30)).replace(second=0, microsecond=0)


def heure_aleatoire(rng, jour, heure_min, heure_max):
    """Instant aléatoire (arrondi à 5 minutes) entre deux heures décimales d'un jour donné."""
    minutes = rng.randrange(int(heure_min * 60), int(heure_max * 60), 5)
    return datetime(jour.year, jour.month, jour.day) + timedelta(minutes=minutes)


def apres_minutes_ouvrees(moment, minutes):
    """Ajoute des minutes ; si l'on dépasse 16 h 15 (ou un week-end), reprend le jour ouvré suivant."""
    resultat = moment + timedelta(minutes=minutes)
    if resultat.weekday() >= 5 or heure_decimale(resultat) > 16.25:
        lendemain = jour_ouvre_apres(resultat.date() + timedelta(days=1))
        resultat = instant(lendemain, 7.75) + timedelta(minutes=minutes % 45)
    return resultat


def debut_jour_suivant(moment):
    return instant(jour_ouvre_apres(moment.date() + timedelta(days=1)), DEBUT_JOURNEE)


def repartir_heures(debut, heures):
    """Répartit `heures` de travail à partir de `debut` sur les jours ouvrés (7 h 30 - 16 h 30).

    Retourne (fin, [(jour, heures), ...]). Une intervention qui déborde continue le lendemain.
    """
    courant = debut
    restant = heures
    jours = []
    for _ in range(60):
        if courant.weekday() >= 5 or heure_decimale(courant) >= FIN_JOURNEE:
            courant = debut_jour_suivant(courant)
        if heure_decimale(courant) < DEBUT_JOURNEE:
            courant = instant(courant.date(), DEBUT_JOURNEE)
        capacite = FIN_JOURNEE - heure_decimale(courant)
        if restant <= capacite + 1e-9:
            jours.append((courant.date(), restant))
            return arrondir_minute(courant + timedelta(hours=restant)), jours
        jours.append((courant.date(), capacite))
        restant -= capacite
        courant = debut_jour_suivant(courant)
    raise ErreurCoherence('Intervention trop longue pour être répartie')


def quart_heure(heures):
    """Arrondi au quart d'heure, minimum 0,25 h."""
    return max(0.25, round(heures * 4) / 4.0)


def nombre_texte(valeur):
    """Nombre au format du fichier : point décimal, sans zéros inutiles (12.0 -> 12, 0.50 -> 0.5)."""
    if isinstance(valeur, float):
        if valeur == int(valeur):
            return str(int(valeur))
        return ('%.2f' % valeur).rstrip('0').rstrip('.')
    return str(valeur)


def valeur_en_texte(valeur):
    """Toute valeur en mémoire est une chaîne (ARCHITECTURE.md §2). Un dict = renvoi vers une ligne."""
    if isinstance(valeur, dict):
        return valeur
    if valeur is None:
        return ''
    if isinstance(valeur, bool):
        return '1' if valeur else '0'
    if isinstance(valeur, (int, float)):
        return nombre_texte(valeur)
    return str(valeur)


def priorite_calculee(criticite, impact):
    """RG2 : matrice criticité x impact ; un impact « sécurité » donne toujours P1."""
    if impact == 'sécurité':
        return 'P1'
    matrice = {'A': {'gêne': 'P2', 'dégradé': 'P1', 'arrêt': 'P1'},
               'B': {'gêne': 'P3', 'dégradé': 'P2', 'arrêt': 'P1'},
               'C': {'gêne': 'P4', 'dégradé': 'P3', 'arrêt': 'P2'}}
    return matrice[criticite][impact]


def date_prevue_par_defaut(jour_creation, priorite):
    """Date prévue = création + délai de la priorité (P1 immédiat, P2 24 h, P3 7 j, P4 14 j)."""
    delais = {'P1': 0, 'P2': 1, 'P3': 7, 'P4': 14}
    return jour_ouvre_apres(jour_creation + timedelta(days=delais[priorite]))


# =============================================================================
# 3. CATALOGUE DE CONTENU (tout est inventé)
# =============================================================================

ELEC, MECA, AUTO, POLY = 'Électricien', 'Mécanicien', 'Automaticien', 'Polyvalent'

DEMANDEURS = ['Léa Fontaine', 'Mathieu Roux', 'Camille Girard', 'Hugo Lefèvre', 'Inès Marchand',
              'Paul Dubois', 'Sarah Colin', 'Antoine Mercier', 'Manon Duval', 'Lucas Perrot']

DESCRIPTIONS_DI = ['', '', '', '', 'Constaté en début de poste.', 'Ça dure depuis hier.',
                   'Le problème apparaît surtout quand la machine est chaude.',
                   'Merci de passer dès que possible.', 'Rien de spécial avant.']

FINS_COMPTE_RENDU = ['', '', '', ' Remise en service validée avec le conducteur.',
                     ' Essai en marche concluant.', ' Zone nettoyée, consignation levée.',
                     ' À surveiller lors du prochain préventif.', ' Conducteur informé.']

# ---------------------------------------------------------------------------
# Localisations : 1 site, 3 ateliers, 3 lignes
# ---------------------------------------------------------------------------

LOCALISATIONS = [   # (clé interne, libellé, clé du parent, type)
    ('site', 'Site des Trois Vallées', None, 'site'),
    ('usinage', 'Atelier Usinage', 'site', 'atelier'),
    ('assemblage', 'Atelier Assemblage-conditionnement', 'site', 'atelier'),
    ('utilites', 'Atelier Utilités', 'site', 'atelier'),
    ('ligne_cond', 'Ligne de conditionnement', 'assemblage', 'ligne'),
    ('ligne_asm', "Ligne d'assemblage", 'assemblage', 'ligne'),
    ('cellule_cn', "Cellule d'usinage CN", 'usinage', 'ligne'),
]

# ---------------------------------------------------------------------------
# Codes de défaillance (stables : on ne renumérote jamais)
# ---------------------------------------------------------------------------

CODES_SYMPTOMES = [
    ('S01', 'Fuite'), ('S02', 'Bruit anormal'), ('S03', 'Vibration'), ('S04', 'Échauffement'),
    ('S05', 'Arrêt intempestif'), ('S06', 'Ne démarre pas'), ('S07', 'Défaut qualité'),
    ('S08', 'Pression ou débit bas'), ('S09', 'Déclenchement disjoncteur'),
    ('S10', 'Odeur de brûlé'), ('S99', 'Autre symptôme')]
CODES_CAUSES = [
    ('C01', 'Garniture usée'), ('C02', 'Roulement hors service'), ('C03', 'Courroie détendue'),
    ('C04', 'Capteur encrassé'), ('C05', 'Filtre colmaté'), ('C06', 'Desserrage'),
    ('C07', 'Défaut de lubrification'), ('C08', 'Surcharge moteur'), ('C09', 'Contacteur hors service'),
    ('C10', 'Flexible percé'), ('C11', 'Dérive de réglage'), ('C12', 'Erreur de manœuvre'),
    ('C13', 'Corrosion'), ('C14', 'Pièce cassée'), ('C99', 'Autre cause')]
CODES_REMEDES = [
    ('R01', 'Remplacement de pièce'), ('R02', 'Réglage'), ('R03', 'Nettoyage'), ('R04', 'Resserrage'),
    ('R05', 'Graissage'), ('R06', 'Réparation'), ('R07', 'Remplacement de composant électrique'),
    ('R08', 'Réarmement'), ('R09', 'Modification'), ('R10', 'Sous-traitance')]

# ---------------------------------------------------------------------------
# Techniciens et habilitations
# ---------------------------------------------------------------------------

TECHNICIENS_DEMO = [    # (nom, prénom, métier, taux horaire)
    ('Moreau', 'Julien', ELEC, 44), ('Benali', 'Karim', MECA, 42),
    ('Lambert', 'Sophie', AUTO, 48), ('Garnier', 'Thomas', POLY, 38)]

HABILITATIONS_DEMO = [  # (numéro du technicien, intitulé, obtention, échéance)
    (1, 'BR', '2025-03-10', '2028-03-10'), (1, 'B2V', '2025-03-10', '2028-03-10'),
    (1, 'H0V', '2025-03-10', '2028-03-10'),
    (2, 'CACES R489', '2021-12-02', '2026-12-02'),      # expire dans 44 jours : à renouveler
    (2, 'H0V', '2024-05-14', '2027-05-14'),
    (3, 'BR', '2025-09-22', '2028-09-22'), (3, 'H0V', '2025-09-22', '2028-09-22'),
    (4, 'BR', '2023-06-01', '2026-05-31'),              # ÉCHUE à la date de référence
    (4, 'CACES R489', '2024-02-20', '2029-02-20'), (4, 'H0V', '2025-11-10', '2028-11-10')]

NOMS_SUPPLEMENTAIRES = [    # techniciens ajoutés par le jeu de charge
    ('Colin', 'Maxime'), ('Perrin', 'Élodie'), ('Fabre', 'Nicolas'), ('Roche', 'Aurélie'),
    ('Guillot', 'Bastien'), ('Leroy', 'Chloé')]

# ---------------------------------------------------------------------------
# Fournisseurs (téléphones dans la plage réservée à la fiction, avec zéro en tête)
# ---------------------------------------------------------------------------

FOURNISSEURS = [        # (nom, contact, téléphone, e-mail)
    ('Mécaroule Distribution', 'Claire Rousseau', '0465710001', 'commandes@mecaroule-demo.example'),
    ('Fluidalpes Services', 'Bruno Faure', '0465710002', 'ventes@fluidalpes-demo.example'),
    ('Électro-Alpes Distribution', 'Émilie Vasseur', '0465710003', 'comptoir@electro-alpes-demo.example'),
    ('Lubrifix Industrie', 'Olivier Brun', '0465710004', 'contact@lubrifix-demo.example'),
    ('Garnitech Pompes', 'Nathalie Joly', '0465710005', 'sav@garnitech-demo.example')]

# ---------------------------------------------------------------------------
# Équipements
# ---------------------------------------------------------------------------

ETAPES_CONSIGNATION = [     # (énergie, étape) dans l'ordre où l'on consigne
    ('pneu', "Fermer la vanne d'isolement d'air comprimé, la cadenasser, puis purger le circuit jusqu'à 0 bar."),
    ('hydr', 'Arrêter le groupe hydraulique, décomprimer le circuit et vérifier 0 bar au manomètre.'),
    ('fluide', "Isoler la partie concernée du circuit d'eau et la vidanger."),
    ('charge', "Poser toute charge au sol : aucune charge ne reste suspendue pendant l'intervention."),
    ('batt', 'Débrancher la batterie de traction et retirer la clé du chariot.'),
    ('meca', 'Immobiliser les masses mobiles (cales, béquilles ou goupilles de sécurité).'),
    ('therm', "Attendre le refroidissement (au moins 30 minutes) avant d'ouvrir le circuit."),
]


def texte_consignation(energies, precision=''):
    """Procédure de consignation numérotée, une étape par ligne, selon les énergies présentes."""
    energies = [e for e in energies.split(',') if e]
    if not energies:
        return ''
    etapes = ["Arrêter l'équipement en fin de cycle et prévenir le conducteur."]
    if 'elec' in energies:
        etapes.append("Ouvrir le sectionneur de l'équipement (ou le départ dans l'armoire) et le cadenasser "
                      "avec son cadenas personnel.")
    etapes += [etape for energie, etape in ETAPES_CONSIGNATION if energie in energies]
    if 'elec' in energies:
        etapes.append("Vérifier l'absence de tension (VAT) avant de toucher à quoi que ce soit.")
    if precision:
        etapes.append(precision)
    etapes.append('Afficher la pancarte « Consignation en cours » et garder la clé du cadenas sur soi.')
    return '\n'.join('%d. %s' % (numero, etape) for numero, etape in enumerate(etapes, 1))


def definir_equipement(repere, designation, loc, parent, marque, modele, num_serie, mise_en_service,
                       criticite, heures, habilitation, energies, precision, famille, taux,
                       statut='en service'):
    """Un équipement du catalogue (dictionnaire lisible, une ligne par appel)."""
    return {'repere': repere, 'designation': designation, 'loc': loc, 'parent': parent,
            'marque': marque, 'modele': modele, 'num_serie': num_serie, 'mes': mise_en_service,
            'crit': criticite, 'heures': heures, 'hab': habilitation, 'energies': energies,
            'precision': precision, 'famille': famille, 'taux': taux, 'statut': statut}


# `taux` = nombre moyen de pannes « de fond » par mois (0 = scénario écrit à la main, voir §5).
EQUIPEMENTS_DEMO = [
    # --- Atelier Utilités
    definir_equipement('CP-01', 'Compresseur à vis 30 kW', 'utilites', None, 'Aerovis', 'AV 30 D',
                       'AV30-2019-04571', '2019-03-12', 'A', 16, '', 'elec,pneu,therm', '',
                       'compresseur', 0),
    definir_equipement('CP-01.SEC', "Sécheur d'air par réfrigération", 'utilites', 'CP-01', 'Aerovis',
                       'SD-40', 'SD40-2019-0233', '2019-03-12', 'B', 16, '', 'elec,pneu', '',
                       'froid', 0.15),
    definir_equipement('RA-01', "Réservoir d'air comprimé 1000 L", 'utilites', None, 'Cuveltech',
                       'RV-1000', '00481723', '2019-03-12', 'B', None, '', 'pneu',
                       "Le réservoir reste sous pression tant que la vanne de départ réseau n'est pas fermée.",
                       'reservoir', 0),
    definir_equipement('PO-01', "Pompe de circulation d'eau glacée", 'utilites', None, 'Hydronel',
                       'HC 65-200', 'HY-65-18-3321', '2018-06-04', 'B', 16, '', 'elec,fluide', '',
                       'pompe', 0.25),
    definir_equipement('PO-02', 'Pompe centrifuge eau de refroidissement', 'utilites', None, 'Hydronel',
                       'HC 50-160', 'HY-50-17-2987', '2017-09-18', 'B', 16, '', 'elec,fluide', '',
                       'pompe', 0),
    definir_equipement('PO-03', 'Pompe de relevage des eaux pluviales', 'utilites', None, 'Submersa',
                       'VR-7', 'SU-7-20-0415', '2020-02-10', 'C', 4, '', 'elec', '', 'pompe', 0.2),
    definir_equipement('GF-01', 'Groupe froid 80 kW', 'utilites', None, 'Frigora', 'GF-80 R',
                       'FR80-2020-0771', '2020-05-25', 'A', 16, 'BR', 'elec,fluide,therm', '',
                       'froid', 0.3),
    definir_equipement('VE-01', "Centrale de traitement d'air de l'atelier", 'utilites', None, 'Aéraulys',
                       'CTA-12', 'AE-12-2016-118', '2016-10-03', 'B', 10, '', 'elec,meca', '',
                       'ventilation', 0),
    definir_equipement('VE-02', 'Extracteur des fumées de soudage', 'utilites', None, 'Aéraulys', 'EX-4',
                       'AE-04-2021-044', '2021-04-12', 'C', 6, '', 'elec,meca', '', 'ventilation', 0.15),
    definir_equipement('AE-01', 'Armoire électrique générale basse tension (TGBT)', 'utilites', None,
                       'Voltavel', 'TGBT-400', 'VT-400-15-0092', '2015-01-20', 'A', 24, 'BR', 'elec',
                       "Armoire alimentée par le transformateur : prévenir le chef d'atelier avant de couper.",
                       'electrique', 0.1),
    definir_equipement('AE-02', "Armoire de distribution de l'atelier Usinage", 'usinage', None,
                       'Voltavel', 'AD-250', 'VT-250-15-0310', '2015-01-20', 'B', 16, 'BR', 'elec', '',
                       'electrique', 0.15),
    definir_equipement('AE-03', 'Armoire de commande de la ligne de conditionnement', 'ligne_cond', None,
                       'Voltavel', 'AC-160', 'VT-160-19-0654', '2019-08-26', 'B', 16, 'BR', 'elec', '',
                       'electrique', 0.25),
    definir_equipement('AE-04', "Armoire de distribution de l'atelier Assemblage", 'assemblage', None,
                       'Voltavel', 'AD-160', 'VT-160-17-0508', '2017-02-13', 'C', None, 'BR', 'elec', '',
                       'electrique', 0.1),
    # --- Atelier Usinage
    definir_equipement('CN-01', 'Tour à commande numérique', 'cellule_cn', None, 'Tornex', 'T-520',
                       'TX-520-14-0087', '2014-11-17', 'B', 14, '', 'elec,pneu,meca', '', 'usinage', 0.4),
    definir_equipement('CN-01.BR', 'Broche du tour CN-01', 'cellule_cn', 'CN-01', 'Tornex', 'BR-12',
                       'TXB-12-14-0087', '2014-11-17', 'B', 14, '', 'elec,meca', '', 'broche', 0.1),
    definir_equipement('CU-01', "Centre d'usinage 3 axes", 'cellule_cn', None, 'Fraistral', 'VMC-760',
                       'FS-760-18-0213', '2018-03-05', 'A', 14, '', 'elec,pneu,meca', '', 'usinage', 0.45),
    definir_equipement('CU-01.CH', "Changeur d'outils du centre CU-01", 'cellule_cn', 'CU-01', 'Fraistral',
                       'CO-24', 'FSC-24-18-0213', '2018-03-05', 'B', 14, '', 'elec,pneu,meca', '',
                       'changeur', 0.1),
    definir_equipement('PT-01', 'Pont roulant 5 t', 'usinage', None, 'Levamax', 'PR-5T',
                       'LV-5-12-0044', '2012-07-09', 'B', 4, '', 'elec,charge', '', 'levage', 0.15),
    definir_equipement('SC-01', 'Scie à ruban', 'usinage', None, 'Sciatek', 'SB-280', 'ST-280-16-1190',
                       '2016-05-30', 'C', 3, '', 'elec,meca', '', 'usinage', 0.15),
    # --- Atelier Assemblage-conditionnement
    definir_equipement('PR-01', 'Presse hydraulique 100 t', 'ligne_asm', None, 'Presto-Form', 'PH-100',
                       'PF-100-13-0021', '2013-09-23', 'A', 8, '', 'elec,hydr,meca', '', 'presse', 0.45),
    definir_equipement('PR-01.GH', 'Groupe hydraulique de la presse PR-01', 'ligne_asm', 'PR-01',
                       'Presto-Form', 'GH-15', 'PFG-15-13-0021', '2013-09-23', 'A', 8, '', 'elec,hydr', '',
                       'hydraulique', 0.15),
    definir_equipement('CV-01', "Convoyeur à bande d'entrée de ligne", 'ligne_cond', None, 'Convexa',
                       'CB-600', 'CX-600-17-0305', '2017-06-12', 'B', 8, '', 'elec,meca', '', 'convoyeur',
                       0.35),
    definir_equipement('CV-02', 'Convoyeur à rouleaux motorisé', 'ligne_cond', None, 'Convexa', 'CR-450',
                       'CX-450-17-0306', '2017-06-12', 'B', 8, '', 'elec,meca', '', 'convoyeur', 0),
    definir_equipement('CV-02.M', 'Motoréducteur du convoyeur CV-02', 'ligne_cond', 'CV-02', 'Motorvel',
                       'MR-0.75', 'MO-075-17-5521', '2017-06-12', 'B', 8, '', 'elec,meca', '', 'moteur',
                       0.1),
    # CV-03 est du même modèle que CV-02 : l'encart « causes fréquentes » de CV-03 passe à la portée
    # « modèle » (ARCHITECTURE.md §14.5).
    definir_equipement('CV-03', 'Convoyeur de sortie de ligne', 'ligne_cond', None, 'Convexa', 'CR-450',
                       'CX-450-19-0411', '2019-10-07', 'C', 8, '', 'elec,meca', '', 'convoyeur', 0.25),
    definir_equipement('EM-01', 'Fardeleuse sous film rétractable', 'ligne_cond', None, 'Emballor', 'FX-90',
                       'EX-90-18-0140', '2018-04-16', 'B', 8, '', 'elec,pneu,meca,therm', '', 'emballage',
                       0.5),
    definir_equipement('ET-01', 'Étiqueteuse automatique', 'ligne_cond', None, 'Étiquex', 'ES-300',
                       'EQ-300-20-0952', '2020-01-27', 'C', 8, '', 'elec,pneu', '', 'emballage', 0.35),
    definir_equipement('RB-01', 'Robot de palettisation', 'ligne_cond', None, 'Robalys', 'PAL-6',
                       '202409871234567', '2024-09-02', 'B', 8, '', 'elec,pneu,meca',
                       'Arrêter le robot et ouvrir la barrière de la zone avant de consigner.',
                       'emballage', 0.3),
    definir_equipement('BA-01', 'Balance de contrôle pondéral', 'ligne_cond', None, 'Pesatec', 'CP-60',
                       'PT-60-21-0377', '2021-03-15', 'C', 8, '', 'elec', '', 'emballage', 0),
    definir_equipement('CH-01', 'Chariot élévateur électrique 2 t', 'assemblage', None, 'Manutrel', 'E20',
                       'MV-E20-19-1043', '2019-06-04', 'B', 6, '', 'batt,charge', '', 'levage', 0.3),
    definir_equipement('PE-01', 'Perceuse à colonne (réformée en 2025)', 'usinage', None, 'Foradel',
                       'PC-32', 'FT-32-09-0710', '2009-02-02', 'C', 8, '', '', '', 'usinage', 0,
                       statut='rebut'),
]

# Valeur de remplacement à neuf (€ HT) de chaque équipement de la démo : ordres de grandeur réalistes
# (compresseur à vis 25-40 k€, pompe 3-9 k€, convoyeur 8-20 k€, presse 60-120 k€, tour CN 80-150 k€,
# armoire 5-15 k€, chariot 20-35 k€, groupe froid 15-30 k€).
VALEURS_REMPLACEMENT_DEMO = {
    'CP-01': 32400, 'CP-01.SEC': 6800, 'RA-01': 4200, 'PO-01': 7400, 'PO-02': 5650, 'PO-03': 3300,
    'GF-01': 27500, 'VE-01': 18500, 'VE-02': 6900, 'AE-01': 14800, 'AE-02': 9600, 'AE-03': 12400,
    'AE-04': 7850, 'CN-01': 118000, 'CN-01.BR': 16500, 'CU-01': 135000, 'CU-01.CH': 14200,
    'PT-01': 42000, 'SC-01': 8900, 'PR-01': 96000, 'PR-01.GH': 18000, 'CV-01': 14500, 'CV-02': 11800,
    'CV-02.M': 1450, 'CV-03': 10900, 'EM-01': 68000, 'ET-01': 24000, 'RB-01': 145000, 'BA-01': 12500,
    'CH-01': 28500, 'PE-01': 2400,
}

# Fourchettes de valeur de remplacement (€ HT) par famille, pour le jeu de charge.
FOURCHETTES_VALEUR = {
    'pompe': (3000, 9000), 'convoyeur': (8000, 20000), 'compresseur': (25000, 40000),
    'presse': (60000, 120000), 'usinage': (80000, 150000), 'electrique': (5000, 15000),
    'ventilation': (6000, 20000), 'froid': (15000, 30000), 'levage': (20000, 45000),
    'emballage': (20000, 70000),
}

# Familles du jeu de charge : (famille, préfixe, désignation, marque, modèle, énergies, heures/jour,
# taux de pannes par mois, poids dans le parc, habilitation)
FAMILLES_VOLUME = [
    ('pompe', 'PO', 'Pompe centrifuge', 'Hydronel', 'HC 50-160', 'elec,fluide', 16, 0.35, 12, ''),
    ('convoyeur', 'CV', 'Convoyeur', 'Convexa', 'CB-600', 'elec,meca', 8, 0.5, 16, ''),
    ('compresseur', 'CP', 'Compresseur à vis', 'Aerovis', 'AV 30 D', 'elec,pneu,therm', 16, 0.4, 3, ''),
    ('presse', 'PR', 'Presse hydraulique', 'Presto-Form', 'PH-100', 'elec,hydr,meca', 8, 0.6, 5, ''),
    ('usinage', 'MO', "Machine d'usinage", 'Fraistral', 'VMC-760', 'elec,pneu,meca', 14, 0.6, 9, ''),
    ('electrique', 'AE', 'Armoire électrique', 'Voltavel', 'AD-250', 'elec', 24, 0.2, 12, 'BR'),
    ('ventilation', 'VE', 'Ventilation', 'Aéraulys', 'EX-4', 'elec,meca', 10, 0.25, 8, ''),
    ('froid', 'GF', 'Groupe froid', 'Frigora', 'GF-80 R', 'elec,fluide,therm', 16, 0.4, 3, 'BR'),
    ('levage', 'PT', 'Appareil de levage', 'Levamax', 'PR-5T', 'elec,charge', 5, 0.3, 5, ''),
    ('emballage', 'EM', "Machine d'emballage", 'Emballor', 'FX-90', 'elec,pneu,meca', 8, 0.7, 12, ''),
]


# ---------------------------------------------------------------------------
# Scénarios de pannes : une chaîne symptôme -> cause -> remède COHÉRENTE par famille
# ---------------------------------------------------------------------------

def scenario(symptome, cause, remede, poids, metiers, duree, impacts, pieces, titre, travail,
             textes_di, comptes_rendus, soustraitance=None):
    """Un type de panne.

    poids          probabilité relative de ce scénario dans sa famille
    metiers        métiers des techniciens qui interviennent d'habitude
    duree          (min, max) d'heures d'intervention
    impacts        ((impact, poids), ...) : ce que l'opérateur déclare le plus souvent
    pieces         ((clé d'article, quantité min, quantité max, probabilité), ...)
    textes_di      façons dont les opérateurs décrivent le symptôme ({rep} = repère)
    comptes_rendus façons dont les techniciens racontent l'intervention ({rep} = repère)
    soustraitance  (min, max) en euros si une entreprise extérieure intervient
    """
    return {'symptome': symptome, 'cause': cause, 'remede': remede, 'poids': poids,
            'metiers': metiers, 'duree': duree, 'impacts': impacts, 'pieces': pieces,
            'titre': titre, 'travail': travail, 'di': textes_di, 'cr': comptes_rendus,
            'soustraitance': soustraitance}


SCENARIOS = {
    'pompe': [
        scenario('S01', 'C01', 'R01', 4, [MECA, POLY], (2.0, 4.0),
                 (('dégradé', 5), ('arrêt', 2), ('gêne', 2)), (('kit_gar_u', 1, 1, 1.0),),
                 'Fuite à la garniture mécanique',
                 "Consigner la pompe, remplacer la garniture mécanique, contrôler l'alignement et l'étanchéité à la remise en route.",
                 ["La pompe fuit au niveau de l'arbre, il y a une flaque sous le groupe.",
                  'Gouttes d\'eau régulières sous la pompe {rep}, le sol est mouillé.',
                  "Fuite importante côté accouplement de {rep}."],
                 ["Garniture mécanique usée (faces rayées). Remplacée par un kit neuf, alignement contrôlé, aucune fuite à la remise en service.",
                  "Fuite à l'arbre : garniture HS remplacée, joints toriques changés, essai sous pression sans fuite.",
                  "Garniture mécanique remplacée après dépose du moteur ; accouplement recentré, étanchéité vérifiée 15 minutes en marche."]),
        scenario('S01', 'C06', 'R04', 1, [MECA, POLY], (0.75, 1.5),
                 (('gêne', 4), ('dégradé', 3)), (('joints_tor', 1, 1, 0.3),),
                 'Fuite au raccord de refoulement',
                 "Consigner la pompe, resserrer la bride de refoulement au couple, changer le joint s'il est abîmé.",
                 ["De l'eau suinte à la bride de refoulement de {rep}.",
                  'Petite fuite sur la tuyauterie de sortie de la pompe {rep}.'],
                 ["Bride de refoulement desserrée par les vibrations : boulons resserrés au couple en croix, aucune fuite à la remise en pression.",
                  "Raccord de refoulement desserré, joint en bon état : resserrage au couple et marquage au vernis témoin, étanchéité contrôlée."]),
        scenario('S02', 'C02', 'R01', 3, [MECA, POLY], (2.0, 4.5),
                 (('dégradé', 4), ('gêne', 3), ('arrêt', 1)), (('roul_6305', 2, 2, 1.0),),
                 'Bruit anormal, roulement à remplacer',
                 'Contrôler les roulements, remplacer ceux qui présentent du jeu, graisser et vérifier les vibrations.',
                 ['Bruit de grincement côté moteur de la pompe.',
                  'La pompe {rep} fait un bruit de ferraille depuis ce matin.',
                  'Roulement qui siffle, le bruit augmente.'],
                 ["Roulement côté accouplement hors service (jeu important). Remplacé, graissage correct, niveau sonore normal.",
                  "Deux roulements remplacés, arbre contrôlé : pas de rayure. Essai en marche sans bruit.",
                  "Bruit dû à un roulement grippé ; remplacement des roulements et contrôle des vibrations après remise en service."]),
        scenario('S03', 'C06', 'R04', 2, [MECA, POLY], (0.5, 1.5),
                 (('gêne', 4), ('dégradé', 2)), (),
                 'Vibrations anormales, resserrage', "Contrôler la fixation du groupe et de l'accouplement, resserrer au couple.",
                 ['La pompe vibre fortement, le tuyau tremble.', 'Vibrations sur {rep}, on les sent sur le châssis.'],
                 ["Boulons de fixation du groupe desserrés. Resserrés au couple, vibrations revenues à la normale.",
                  "Desserrage des vis de l'accouplement ; resserrage au couple et marquage au vernis témoin."]),
        scenario('S08', 'C05', 'R03', 2, [MECA, POLY], (0.75, 2.0),
                 (('dégradé', 4), ('gêne', 2), ('arrêt', 1)), (('nettoyant', 1, 1, 0.4),),
                 'Pression basse en sortie de pompe', "Contrôler et nettoyer la crépine et les filtres à l'aspiration.",
                 ['La pression de refoulement est basse sur {rep}.', "Débit d'eau faible, la pompe semble s'essouffler."],
                 ["Crépine d'aspiration colmatée par des dépôts. Nettoyée, pression retrouvée.",
                  "Filtre à l'aspiration encrassé : démonté, nettoyé, pression de refoulement conforme."]),
    ],
    'convoyeur': [
        scenario('S05', 'C04', 'R03', 4, [AUTO, ELEC, POLY], (0.5, 1.5),
                 (('dégradé', 4), ('arrêt', 3)), (('nettoyant', 1, 1, 0.5), ('capteur_m18', 1, 1, 0.2)),
                 'Arrêts intempestifs, capteur à nettoyer', 'Nettoyer et régler les capteurs de présence, contrôler le câblage.',
                 ['Le convoyeur s\'arrête tout seul plusieurs fois par heure.',
                  'Arrêts intempestifs sur {rep}, il faut réarmer à chaque fois.',
                  'Le tapis stoppe sans raison, le voyant de défaut capteur clignote.'],
                 ["Capteur de présence encrassé par la poussière : nettoyé, distance de détection contrôlée. Plus d'arrêt intempestif.",
                  "Cellule de fin de course souillée ; nettoyage et vérification du câblage, fonctionnement normal pendant 30 minutes.",
                  "Capteur inductif encrassé et mal aligné : nettoyé et réaligné, essais concluants."]),
        scenario('S02', 'C07', 'R05', 2, [MECA, POLY], (0.75, 1.75),
                 (('gêne', 4), ('dégradé', 2)), (('graisse', 1, 2, 1.0),),
                 'Bruit de roulement, graissage insuffisant', 'Graisser les paliers et les galets, contrôler leur état.',
                 ['Ça grince sur le convoyeur {rep}.', 'Bruit de frottement continu sous le tapis.'],
                 ["Paliers insuffisamment graissés : graissage complet de la ligne d'arbre, bruit disparu.",
                  "Galets secs, graissage effectué sur l'ensemble des paliers ; à intégrer à la gamme."]),
        scenario('S02', 'C03', 'R02', 2, [MECA, POLY], (0.75, 1.5),
                 (('gêne', 4), ('dégradé', 3)), (),
                 'Courroie qui patine', "Retendre la courroie, contrôler l'alignement des poulies.",
                 ["La courroie du convoyeur {rep} patine, ça couine au démarrage.", 'Entraînement qui glisse, le tapis avance par à-coups.'],
                 ["Courroie détendue : tension réglée au tensiomètre, alignement des poulies vérifié.",
                  "Entraînement qui patinait : courroie retendue, usure acceptable, à surveiller."]),
        scenario('S06', 'C09', 'R07', 2, [ELEC, AUTO], (1.0, 2.5),
                 (('arrêt', 4), ('dégradé', 2)), (('contacteur_25', 1, 1, 1.0),),
                 'Ne démarre pas, contacteur à remplacer', "Rechercher l'origine du défaut de démarrage, remplacer le contacteur défectueux.",
                 ['Le convoyeur {rep} ne démarre plus du tout.', 'Rien ne se passe quand on appuie sur marche.'],
                 ["Contacteur moteur collé puis hors service : remplacé, bornes resserrées, démarrage normal.",
                  "Le convoyeur ne démarrait pas : contacteur de puissance défectueux remplacé, essai concluant."]),
        scenario('S03', 'C02', 'R01', 1, [MECA, POLY], (2.0, 4.0),
                 (('dégradé', 3), ('gêne', 2)), (('roul_6205', 2, 2, 1.0), ('palier_ucp', 1, 1, 0.4)),
                 "Vibration du tambour d'entraînement", "Remplacer les roulements du tambour d'entraînement.",
                 ["Le tambour d'entraînement de {rep} vibre fort.", 'Vibrations et bruit sourd au niveau du tambour moteur.'],
                 ["Roulements du tambour d'entraînement hors service : remplacés, tambour contrôlé, vibrations normales.",
                  "Roulement grippé côté réducteur, remplacement et graissage ; vibrations revenues à la normale."]),
    ],
    'compresseur': [
        scenario('S04', 'C05', 'R01', 3, [MECA, POLY], (1.5, 3.0),
                 (('arrêt', 4), ('dégradé', 3)), (('filtre_huile_cp', 1, 1, 1.0),),
                 'Échauffement du compresseur, filtre colmaté', "Remplacer le filtre à huile, nettoyer le radiateur, contrôler la température en charge.",
                 ['Le compresseur chauffe et se met en défaut température.',
                  'Température haute sur {rep}, il s\'arrête puis redémarre.',
                  'Alarme échauffement sur le compresseur, le carter est très chaud.'],
                 ["Filtre à huile colmaté : cartouche remplacée, niveau d'huile contrôlé, température de refoulement redescendue à 84 °C.",
                  "Échauffement dû à un filtre encrassé ; cartouche changée, radiateur soufflé, essai en charge 1 h sans alarme.",
                  "Circuit d'huile restreint par un filtre colmaté : cartouche remplacée, température normale après 30 minutes de marche."]),
        scenario('S04', 'C07', 'R05', 2, [MECA, POLY], (1.0, 2.5),
                 (('arrêt', 3), ('dégradé', 3)), (('huile_cp', 1, 1, 0.8),),
                 "Échauffement, niveau d'huile bas", "Contrôler le niveau d'huile, compléter, rechercher une fuite.",
                 ['Le compresseur {rep} chauffe plus que d\'habitude.', 'Défaut température haute, il est tombé en sécurité.'],
                 ["Niveau d'huile trop bas : appoint effectué, aucune fuite visible, température normale.",
                  "Lubrification insuffisante : huile complétée, circuit contrôlé, température de refoulement à 82 °C."]),
        scenario('S08', 'C10', 'R01', 2, [MECA, POLY], (1.0, 2.5),
                 (('dégradé', 4), ('arrêt', 2)), (('flex_air', 1, 2, 1.0), ('raccord', 1, 2, 0.5)),
                 "Chute de pression du réseau d'air", 'Rechercher la fuite, remplacer le flexible percé.',
                 ["La pression d'air chute dans l'atelier, le compresseur tourne sans arrêt.", "On entend une grosse fuite d'air près de {rep}."],
                 ["Flexible de départ percé : remplacé, raccords contrôlés, pression réseau stabilisée à 7 bar.",
                  "Fuite d'air sur un flexible usé ; remplacement et contrôle du réseau au détecteur de fuite."]),
        scenario('S05', 'C08', 'R08', 1, [ELEC, AUTO], (0.5, 1.5),
                 (('arrêt', 3), ('dégradé', 2)), (),
                 'Arrêt sur surcharge moteur', "Contrôler l'intensité absorbée, réarmer le relais thermique.",
                 ['Le compresseur s\'est arrêté, défaut moteur.', 'Déclenchement thermique sur {rep}.'],
                 ["Relais thermique déclenché sur surcharge ; réarmé, intensité contrôlée dans la plage, pas de défaut persistant.",
                  "Surcharge moteur ponctuelle : réarmement et mesure d'intensité (valeurs normales), suivi demandé."]),
    ],
    'presse': [
        scenario('S01', 'C10', 'R01', 3, [MECA, POLY], (2.0, 4.0),
                 (('dégradé', 4), ('arrêt', 3)), (('flex_hydr', 1, 2, 1.0), ('huile_hlp46', 1, 1, 0.5)),
                 "Fuite d'huile hydraulique", 'Remplacer le flexible hydraulique percé, compléter le niveau, purger le circuit.',
                 ["Fuite d'huile sous la presse, une flaque se forme.", "De l'huile coule le long du vérin de {rep}."],
                 ["Flexible hydraulique percé près du vérin : remplacé, complément d'huile, essai sous pression sans fuite.",
                  "Flexible usé par frottement ; remplacement et pose d'une gaine de protection, purge du circuit."]),
        scenario('S08', 'C05', 'R01', 2, [MECA, POLY], (1.0, 2.5),
                 (('dégradé', 4), ('arrêt', 2)), (('filtre_hydr', 1, 1, 1.0),),
                 'Pression hydraulique basse', 'Remplacer le filtre hydraulique colmaté et contrôler la pression.',
                 ['La presse manque de pression, elle monte lentement.', 'Pression de travail insuffisante sur {rep}.'],
                 ["Filtre hydraulique colmaté : cartouche remplacée, pression de travail retrouvée.",
                  "Perte de pression due à un filtre encrassé ; cartouche changée, pression contrôlée à 190 bar."]),
        scenario('S07', 'C11', 'R02', 2, [MECA, AUTO], (1.0, 2.5),
                 (('dégradé', 4), ('gêne', 2)), (),
                 'Pièces hors cote à la presse', 'Contrôler et régler la course et les butées, valider sur des pièces témoins.',
                 ['Les pièces sortent hors cote de la presse.', 'Défaut de profondeur sur les pièces pressées.'],
                 ["Dérive du réglage de course : butée réglée, 5 pièces contrôlées conformes.",
                  "Réglage de la butée basse décalé ; recalé, essais sur pièces témoins conformes."]),
    ],
    'usinage': [
        scenario('S07', 'C11', 'R02', 3, [AUTO, MECA], (1.0, 2.5),
                 (('gêne', 4), ('dégradé', 3)), (),
                 'Défaut de cotes sur les pièces usinées', "Contrôler les origines pièce et outils, corriger les compensations.",
                 ['Les cotes des pièces dérivent sur {rep}.', 'Pièces hors tolérance depuis le changement de lot.'],
                 ["Dérive du zéro pièce : recalage des outils et correction d'usure, 3 pièces contrôlées conformes.",
                  "Jeu dans la compensation d'outil ; réglage et contrôle sur 5 pièces, cotes dans la tolérance."]),
        scenario('S02', 'C02', 'R10', 1, [MECA, AUTO], (4.0, 8.0),
                 (('arrêt', 4), ('dégradé', 2)), (),
                 'Bruit anormal de broche', "Faire diagnostiquer la broche, organiser le reconditionnement chez le fabricant.",
                 ['La broche de {rep} fait un bruit de roulement.', 'Bruit sourd à haute vitesse de broche.'],
                 ["Roulements de broche hors service : broche déposée et envoyée en reconditionnement chez le fabricant, remontage et contrôle du faux-rond.",
                  "Broche bruyante : diagnostic puis reconditionnement en sous-traitance, remontage et essai à toutes les vitesses."],
                 soustraitance=(900, 1800)),
        scenario('S01', 'C10', 'R01', 2, [MECA, POLY], (0.75, 2.0),
                 (('gêne', 4), ('dégradé', 3)), (('raccord', 1, 2, 1.0),),
                 'Fuite de liquide de coupe', "Remplacer le flexible ou le raccord d'arrosage qui fuit, compléter le niveau.",
                 ['Du liquide de coupe fuit sous {rep}.', "Le sol est mouillé autour de la machine, ça vient de l'arrosage."],
                 ["Flexible d'arrosage fendu, remplacé ; niveau de liquide complété.",
                  "Raccord d'arrosage fissuré remplacé, étanchéité contrôlée en marche."]),
        scenario('S05', 'C12', 'R08', 2, [AUTO, POLY], (0.25, 0.75),
                 (('arrêt', 4), ('dégradé', 2)), (),
                 'Machine en défaut après fausse manœuvre', 'Réarmer la machine, réinitialiser les axes, contrôler.',
                 ['{rep} est en défaut, plus rien ne bouge.', 'Alarme course dépassée sur la machine.'],
                 ["Défaut consécutif à une mauvaise manœuvre (course axe dépassée) : réarmement, référencement des axes, aucun dommage constaté.",
                  "Alarme déclenchée par une fausse manœuvre : réarmement et réinitialisation, rappel de la procédure au conducteur."]),
    ],
    'electrique': [
        scenario('S09', 'C08', 'R08', 3, [ELEC, AUTO], (0.5, 1.5),
                 (('arrêt', 3), ('dégradé', 3)), (),
                 'Disjoncteur déclenché', "Rechercher la cause du déclenchement, mesurer les intensités, réarmer.",
                 ['Le disjoncteur déclenche régulièrement sur {rep}.', 'Disjoncteur tombé, plus de courant sur la machine.'],
                 ["Disjoncteur moteur déclenché sur surcharge : intensité correcte après réarmement, cause = pic de charge ; surveillance demandée.",
                  "Déclenchement sur surcharge ponctuelle ; réarmement et mesure d'intensité dans la plage, pas de défaut persistant."]),
        scenario('S10', 'C09', 'R07', 2, [ELEC, AUTO], (1.5, 3.0),
                 (('sécurité', 3), ('arrêt', 3)), (('contacteur_25', 1, 1, 1.0),),
                 'Odeur de brûlé, contacteur à remplacer', "Consigner l'armoire, remplacer le contacteur brûlé, contrôler le câblage.",
                 ["Odeur de brûlé près de l'armoire {rep}.", "Ça sent le chaud dans l'armoire, le contacteur est très chaud."],
                 ["Contacteur de puissance brûlé (contacts soudés) : remplacé, câbles contrôlés, serrage des bornes, pas d'autre trace d'échauffement.",
                  "Contacteur en fin de vie, bobine et contacts brûlés : remplacement et contrôle thermique après remise sous tension."]),
        scenario('S06', 'C09', 'R07', 2, [ELEC, AUTO], (1.0, 2.5),
                 (('arrêt', 4), ('dégradé', 2)), (('contacteur_25', 1, 1, 0.7), ('fusible', 1, 1, 0.3)),
                 'Départ moteur qui ne démarre pas', 'Diagnostiquer le départ moteur, remplacer le composant défectueux.',
                 ["Le départ moteur ne s'enclenche plus sur {rep}.", "Le moteur ne démarre plus, l'armoire est sous tension."],
                 ["Contacteur de puissance défectueux : remplacé, essai de démarrage et mesure d'intensité normaux.",
                  "Départ moteur hors service : contacteur remplacé et fusible contrôlé, remise en service validée."]),
        scenario('S09', 'C06', 'R04', 2, [ELEC, AUTO], (1.0, 2.0),
                 (('dégradé', 3), ('arrêt', 2)), (),
                 'Déclenchements dus à une connexion desserrée', "Contrôler et resserrer toutes les bornes, thermographie rapide.",
                 ['Disjonctions intermittentes sur {rep}.', "Le courant saute de temps en temps sans raison apparente."],
                 ["Borne desserrée en échauffement sur le départ moteur : resserrage de toutes les bornes de l'armoire, thermographie sans point chaud.",
                  "Connexion desserrée sur le jeu de barres : resserrage au couple de tout le départ, essais sur 1 h sans déclenchement."]),
    ],
    'ventilation': [
        scenario('S02', 'C03', 'R02', 3, [MECA, POLY], (0.75, 1.75),
                 (('gêne', 4), ('dégradé', 2)), (('cour_spz', 1, 1, 0.4),),
                 'Bruit de courroie de ventilateur', 'Retendre ou remplacer la courroie, aligner les poulies.',
                 ['Sifflement au démarrage du ventilateur {rep}.', 'Bruit de courroie qui patine sur la ventilation.'],
                 ["Courroie détendue : retendue, poulies alignées, bruit disparu.",
                  "Courroie vitrifiée et détendue ; tension réglée (remplacement prévu au prochain préventif)."]),
        scenario('S03', 'C02', 'R01', 2, [MECA, POLY], (2.0, 3.5),
                 (('gêne', 3), ('dégradé', 3)), (('roul_6206', 2, 2, 1.0),),
                 'Vibration du ventilateur, roulement usé', 'Remplacer les roulements du ventilateur, équilibrer.',
                 ['Le ventilateur {rep} vibre et fait du bruit.', 'Grosse vibration sur la ventilation, ça secoue le caisson.'],
                 ["Roulements du ventilateur hors service : remplacés, rotor contrôlé, vibrations normales.",
                  "Roulement côté poulie usé : remplacement des deux roulements, graissage et contrôle des vibrations."]),
        scenario('S08', 'C05', 'R01', 3, [MECA, POLY], (0.75, 2.0),
                 (('gêne', 4), ('dégradé', 3)), (('filtre_g4', 2, 4, 1.0),),
                 "Débit d'air faible, filtres colmatés", 'Remplacer les filtres colmatés, contrôler le débit.',
                 ["Le débit d'air est faible, les filtres semblent encrassés ({rep}).", "Plus d'aspiration à la ventilation de l'atelier."],
                 ["Filtres colmatés par les poussières : remplacés, débit contrôlé et conforme.",
                  "Perte de charge élevée due aux filtres : changement complet, débit retrouvé."]),
    ],
    'froid': [
        scenario('S04', 'C05', 'R03', 3, [MECA, ELEC], (1.5, 3.0),
                 (('arrêt', 3), ('dégradé', 3)), (('filtre_eau', 1, 1, 0.4), ('nettoyant', 1, 1, 0.3)),
                 'Haute pression et échauffement du groupe froid', 'Nettoyer le condenseur, contrôler les pressions.',
                 ['Le groupe froid se met en sécurité haute pression.', 'Alarme température sur {rep}, la température de départ monte.'],
                 ["Condenseur encrassé : nettoyage à l'air et au produit adapté, pressions HP/BP normales.",
                  "Échange thermique dégradé par l'encrassement du condenseur ; nettoyé, groupe redémarré sans alarme."]),
        scenario('S01', 'C13', 'R10', 1, [MECA, ELEC], (2.0, 5.0),
                 (('dégradé', 3), ('arrêt', 2)), (),
                 'Fuite de fluide sur une tuyauterie corrodée', 'Faire intervenir un frigoriste : remplacement du tronçon et recharge.',
                 ["Traces d'huile et de givre sur une tuyauterie de {rep}.", 'Le groupe froid perd en performance, on soupçonne une fuite.'],
                 ["Fuite sur une tuyauterie corrodée : intervention d'un frigoriste (sous-traitance), remplacement du tronçon et recharge, contrôle d'étanchéité.",
                  "Corrosion sur un raccord : réparation par un frigoriste, recharge en fluide et contrôle d'étanchéité satisfaisant."],
                 soustraitance=(600, 1400)),
        scenario('S05', 'C11', 'R02', 2, [ELEC, AUTO], (0.75, 2.0),
                 (('dégradé', 3), ('gêne', 2)), (),
                 'Arrêts répétés du groupe froid', 'Contrôler et régler la régulation et les consignes de température.',
                 ['Le groupe froid démarre et s\'arrête toutes les dix minutes.', 'Cycles très courts sur {rep}.'],
                 ["Consigne et différentiel de la régulation déréglés : réglages remis aux valeurs nominales, cycles normaux.",
                  "Dérive du réglage du thermostat : recalage de la sonde et du différentiel, fonctionnement stable."]),
    ],
    'levage': [
        scenario('S06', 'C09', 'R07', 2, [ELEC, AUTO], (1.0, 2.5),
                 (('arrêt', 4), ('dégradé', 2)), (('contacteur_40', 1, 1, 1.0),),
                 'Ne démarre pas, contacteur à remplacer', 'Diagnostiquer et remplacer le contacteur de puissance.',
                 ["{rep} ne répond plus aux commandes.", 'Le palan ne monte plus, on entend juste un claquement.'],
                 ["Contacteur de puissance hors service : remplacé, essais de levage à vide et en charge concluants.",
                  "Contacteur collé puis défectueux ; remplacement et vérification des fins de course."]),
        scenario('S05', 'C04', 'R03', 3, [AUTO, ELEC, POLY], (0.5, 1.5),
                 (('dégradé', 4), ('arrêt', 2)), (('nettoyant', 1, 1, 0.6),),
                 'Arrêts intempestifs, fin de course encrassé', 'Nettoyer et régler les fins de course.',
                 ['{rep} s\'arrête en cours de mouvement.', 'Arrêts intempestifs pendant le déplacement.'],
                 ["Fin de course encrassé : nettoyé et réglé, mouvements complets sans arrêt.",
                  "Capteur de fin de course encrassé par la poussière ; nettoyage et contrôle du réglage, essais concluants."]),
        scenario('S02', 'C07', 'R05', 2, [MECA, POLY], (0.75, 1.75),
                 (('gêne', 4), ('dégradé', 2)), (('graisse', 1, 2, 1.0),),
                 'Bruit de grincement, graissage', 'Graisser les articulations, galets et chaîne, contrôler les jeux.',
                 ["Grincement au déplacement de {rep}.", 'Ça frotte et ça grince, il faudrait graisser.'],
                 ["Défaut de lubrification : graissage complet des points prévus, bruit disparu.",
                  "Galets et chaîne secs ; graissage, bruit disparu."]),
        scenario('S03', 'C14', 'R01', 1, [MECA, POLY], (1.5, 3.0),
                 (('dégradé', 3), ('arrêt', 2)), (('roue_chariot', 1, 2, 0.7),),
                 'Roue ou galet cassé', 'Remplacer la roue ou le galet cassé, contrôler le châssis.',
                 ["Vibrations anormales sur {rep}, une roue semble abîmée.", "Un galet est cassé, l'engin tire d'un côté."],
                 ["Roue polyuréthane fissurée et cassée : remplacée, châssis contrôlé, déplacement sans vibration.",
                  "Galet cassé : remplacement et contrôle de l'axe, essais de déplacement concluants."]),
    ],
    'emballage': [
        scenario('S07', 'C11', 'R02', 3, [AUTO, MECA], (0.75, 2.0),
                 (('dégradé', 4), ('gêne', 3)), (),
                 'Défaut de qualité de soudure ou de pose', 'Régler la température, la vitesse et les capteurs, contrôler sur des colis témoins.',
                 ['Les colis sortent mal soudés sur {rep}.', 'Les étiquettes sont posées de travers.'],
                 ["Dérive du réglage de la température de soudure : réajusté, 20 colis contrôlés conformes.",
                  "Réglage du capteur de bord de matière et de la vitesse d'applique corrigé, produits conformes."]),
        scenario('S05', 'C04', 'R03', 3, [AUTO, ELEC, POLY], (0.5, 1.5),
                 (('dégradé', 4), ('arrêt', 3)), (('nettoyant', 1, 1, 0.5), ('cellule', 1, 1, 0.3)),
                 'Arrêts intempestifs, cellule encrassée', 'Nettoyer et régler les cellules et capteurs.',
                 ["La machine {rep} s'arrête sans arrêt de cause visible.", 'Défaut cellule à répétition sur la ligne.'],
                 ["Cellule photoélectrique encrassée : nettoyée et réalignée, plus de défaut sur 1 h de marche.",
                  "Capteur souillé par des résidus de film ; nettoyage et réglage de la sensibilité."]),
        scenario('S02', 'C03', 'R02', 2, [MECA, POLY], (0.75, 1.75),
                 (('gêne', 4), ('dégradé', 2)), (('cour_htd', 1, 1, 0.3),),
                 'Bruit de courroie', "Retendre la courroie crantée, contrôler l'alignement.",
                 ["Bruit de courroie sur {rep}.", 'Claquement régulier dans le carter.'],
                 ["Courroie crantée détendue : tension réglée, alignement contrôlé, bruit disparu.",
                  "Courroie détendue : retendue (remplacement à prévoir si le bruit revient)."]),
        scenario('S06', 'C09', 'R07', 1, [ELEC, AUTO], (1.0, 2.5),
                 (('arrêt', 4), ('dégradé', 2)), (('contacteur_25', 1, 1, 1.0),),
                 'Ne démarre pas, contacteur défectueux', 'Diagnostiquer le départ moteur, remplacer le contacteur.',
                 ["{rep} ne démarre plus.", 'Plus de mouvement sur la machine, elle est pourtant sous tension.'],
                 ["Contacteur de puissance défectueux : remplacé, essai de démarrage correct.",
                  "Contacteur hors service ; remplacement, bornes resserrées, redémarrage normal."]),
        scenario('S08', 'C10', 'R01', 2, [MECA, POLY], (1.0, 2.5),
                 (('dégradé', 4), ('arrêt', 2)), (('flex_air', 1, 2, 1.0), ('raccord', 1, 2, 0.5)),
                 "Manque de pression d'air", "Rechercher la fuite d'air, remplacer le flexible percé.",
                 ["Manque d'air sur {rep}, les vérins sont mous.", "On entend de l'air qui fuit derrière la machine."],
                 ["Flexible d'alimentation percé : remplacé, raccord changé, pression stable à 6 bar.",
                  "Fuite d'air sur un flexible usé ; remplacement et contrôle des raccords."]),
    ],
    'divers': [
        scenario('S99', 'C99', 'R06', 1, [POLY, MECA, ELEC], (0.75, 2.0),
                 (('gêne', 3), ('dégradé', 3)), (),
                 'Dysfonctionnement non identifié', 'Contrôler la machine, rechercher l\'origine du défaut signalé.',
                 ["Comportement bizarre de {rep}, difficile à décrire.", 'Un défaut qui revient de temps en temps sur {rep}.'],
                 ["Dysfonctionnement ponctuel non reproduit après essais prolongés ; connexions contrôlées et resserrées, suivi demandé.",
                  "Aucune cause franche trouvée ; contrôle général et nettoyage, remise en service et surveillance par le conducteur."]),
    ],
}
# Sous-ensembles : leurs pannes sont plus restreintes que celles de la machine entière.
SCENARIOS['hydraulique'] = [SCENARIOS['presse'][0], SCENARIOS['presse'][1]]
SCENARIOS['moteur'] = [
    scenario('S02', 'C02', 'R01', 3, [MECA, POLY], (1.5, 3.0), (('gêne', 3), ('dégradé', 3)),
             (('roul_6204', 2, 2, 1.0),), 'Bruit de roulement du moteur',
             "Remplacer les roulements du moteur, contrôler l'alignement et le graissage.",
             ['Le moteur {rep} fait un bruit de roulement.', 'Moteur bruyant, ça grince quand il tourne.'],
             ["Roulements du moteur hors service : remplacés, alignement et graissage contrôlés, bruit disparu.",
              "Roulement avant grippé : remplacement des deux roulements, essai sans bruit anormal."]),
    SCENARIOS['electrique'][0],
]
SCENARIOS['broche'] = [
    SCENARIOS['usinage'][1],
    scenario('S04', 'C07', 'R05', 2, [MECA, AUTO], (1.0, 2.5), (('arrêt', 3), ('dégradé', 3)),
             (('graisse', 1, 1, 0.8),), 'Échauffement de la broche',
             'Contrôler la lubrification de la broche, graisser, relever les températures.',
             ["La broche de {rep} chauffe, l'alarme température se déclenche.",
              'Température de broche trop élevée après quelques minutes de marche.'],
             ["Lubrification insuffisante de la broche : graissage complet, températures normales après 1 h d'essai.",
              "Échauffement dû à un manque de graisse : cycle de graissage effectué, température stable à 45 °C."]),
]
SCENARIOS['changeur'] = [
    scenario('S05', 'C04', 'R03', 3, [AUTO, ELEC, POLY], (0.5, 1.5), (('arrêt', 3), ('dégradé', 3)),
             (('nettoyant', 1, 1, 0.6), ('capteur_m18', 1, 1, 0.2)), "Changeur d'outils bloqué, capteur encrassé",
             "Nettoyer les capteurs de position du changeur, tester un cycle complet.",
             ["Le changeur d'outils de {rep} se bloque en cours de cycle.",
              "Défaut de position du magasin d'outils, la machine s'arrête."],
             ["Capteur de position du magasin d'outils encrassé par des copeaux : nettoyé, cycle complet testé 10 fois sans défaut.",
              "Capteur souillé par le liquide de coupe : nettoyage et réglage, changeur à nouveau fluide."]),
    scenario('S02', 'C07', 'R05', 2, [MECA, POLY], (0.75, 1.5), (('gêne', 3), ('dégradé', 3)),
             (('graisse', 1, 1, 1.0),), "Bruit du changeur d'outils, graissage",
             'Graisser la came et les guidages du changeur.',
             ["Le changeur d'outils de {rep} grince.", "Bruit sec à chaque changement d'outil."],
             ["Came et guidages du changeur à sec : graissage effectué, mouvement silencieux.",
              "Manque de graisse sur les guidages : graissage complet, bruit disparu."]),
]


# ---------------------------------------------------------------------------
# Articles (pièces détachées) : tout est fictif
# ---------------------------------------------------------------------------

def definir_article(cle, categorie, designation, fabricant, ref_fabricant, unite, prix, stock_securite,
                    point_commande, qte_commande, delai, fournisseur, critique, liens, qte_par_equipement=1,
                    **options):
    """Un article du catalogue. `liens` = repères d'équipements ou « @famille »."""
    article = {'cle': cle, 'categorie': categorie, 'designation': designation, 'fabricant': fabricant,
               'ref_fab': ref_fabricant, 'unite': unite, 'prix': prix, 'sec': stock_securite,
               'pc': point_commande, 'qte': qte_commande, 'delai': delai, 'fournisseur': fournisseur,
               'critique': critique, 'liens': liens, 'qte_eq': qte_par_equipement,
               'cible': None, 'stock_final_min': 0}
    article.update(options)
    return article


ARTICLES = [
    # --- Roulements, transmission (Mécaroule)
    definir_article('roul_6204', 'ROU', 'Roulement à billes 6204-2RS', 'Rouloran', '6204-2RS', 'u', 4.8, 4, 8, 20, 3, 1, 0, ['CV-01', 'CV-03', 'VE-02', 'CV-02.M'], 2),
    definir_article('roul_6205', 'ROU', 'Roulement à billes 6205-2RS', 'Rouloran', '6205-2RS', 'u', 5.6, 4, 8, 20, 3, 1, 0, ['@convoyeur', 'EM-01', 'ET-01'], 2),
    definir_article('roul_6206', 'ROU', 'Roulement à billes 6206-2RS', 'Rouloran', '6206-2RS', 'u', 6.9, 4, 8, 16, 3, 1, 0, ['VE-01', 'VE-02', 'SC-01'], 2),
    definir_article('roul_6305', 'ROU', 'Roulement à billes 6305-2RS', 'Rouloran', '6305-2RS', 'u', 8.5, 4, 8, 16, 3, 1, 0, ['@pompe'], 2),
    definir_article('roul_6308', 'ROU', 'Roulement à billes 6308-2Z', 'Rouloran', '6308-2Z', 'u', 12.4, 2, 4, 8, 4, 1, 0, ['@pompe', 'CP-01'], 2),
    definir_article('roul_22210', 'ROU', 'Roulement à rotule sur rouleaux 22210', 'Rouloran', '22210-E', 'u', 38.0, 1, 2, 4, 6, 1, 0, ['CN-01.BR', 'PT-01', 'PR-01']),
    definir_article('palier_ucp', 'ROU', 'Palier à semelle UCP205', 'Rouloran', 'UCP-205', 'u', 24.0, 2, 4, 6, 5, 1, 0, ['CV-01', 'CV-02', 'CV-03'], 4),
    definir_article('cour_spz', 'TRA', 'Courroie trapézoïdale SPZ 1000', 'Cordalpe', 'SPZ-1000', 'u', 9.9, 2, 4, 8, 3, 1, 0, ['VE-01', 'VE-02'], 2),
    definir_article('cour_spa', 'TRA', 'Courroie trapézoïdale SPA 1250', 'Cordalpe', 'SPA-1250', 'u', 14.5, 2, 3, 6, 3, 1, 0, ['CP-01', 'VE-01'], 2),
    definir_article('cour_htd', 'TRA', 'Courroie crantée HTD 8M-1200', 'Cordalpe', '8M-1200', 'u', 26.0, 1, 2, 4, 5, 1, 0, ['CN-01', 'EM-01', 'ET-01']),
    definir_article('galet', 'TRA', 'Galet de convoyeur Ø50', 'Convexa', 'GC-50', 'u', 11.0, 6, 10, 20, 5, 1, 0, ['@convoyeur'], 12),
    definir_article('chaine', 'TRA', 'Chaîne à rouleaux 08B-1 (au mètre)', 'Cordalpe', '08B-1', 'm', 18.0, 3, 5, 10, 5, 1, 0, ['CV-03', 'EM-01'], 3),
    definir_article('bande', 'TRA', 'Bande transporteuse PVC (au mètre)', 'Convexa', 'BT-600-PVC', 'm', 42.0, 2, 4, 10, 10, 1, 0, ['CV-01'], 6),
    # --- Pompes et étanchéité (Garnitech)
    definir_article('accoup', 'ETA', 'Accouplement élastique Ø28', 'Garnitec', 'AE-28', 'u', 31.0, 1, 2, 3, 6, 5, 0, ['@pompe']),
    definir_article('joint_spi', 'ETA', 'Joint à lèvres 35x52x7', 'Garnitec', 'JL-35-52-7', 'u', 3.2, 4, 8, 20, 3, 5, 0, ['@pompe', 'CV-02.M'], 2),
    definir_article('kit_gar_po02', 'ETA', 'Kit garniture mécanique PO-02', 'Garnitec', '0044172', 'kit', 86.0, 1, 1, 2, 10, 5, 1, ['PO-02'], 1, stock_final_min=2),
    definir_article('kit_gar_po01', 'ETA', 'Kit garniture mécanique PO-01', 'Garnitec', '0044168', 'kit', 74.0, 1, 1, 2, 10, 5, 1, ['PO-01']),
    definir_article('kit_gar_u', 'ETA', 'Kit garniture mécanique universelle Ø25', 'Garnitec', 'GU-25-C', 'kit', 59.0, 1, 2, 2, 8, 5, 0, ['@pompe']),
    definir_article('joints_tor', 'ETA', 'Assortiment de joints toriques (boîte)', 'Garnitec', 'JT-382', 'boîte', 29.0, 1, 2, 3, 4, 5, 0, ['@pompe', '@presse', '@compresseur']),
    # --- Filtres et lubrifiants (Lubrifix)
    definir_article('filtre_air_cp', 'FIL', 'Filtre à air compresseur CP-01', 'Filtravel', 'FA-3011', 'u', 38.0, 1, 2, 4, 5, 4, 0, ['CP-01']),
    definir_article('filtre_huile_cp', 'FIL', 'Cartouche filtre à huile CP-01', 'Filtravel', 'FH-2208', 'u', 27.5, 2, 3, 6, 5, 4, 1, ['CP-01'], 1, cible=2),
    definir_article('separ_cp', 'FIL', 'Séparateur air/huile CP-01', 'Filtravel', 'SO-5520', 'u', 142.0, 1, 1, 2, 8, 4, 1, ['CP-01']),
    definir_article('huile_cp', 'LUB', 'Huile compresseur à vis (bidon 20 L)', 'Lubrazur', 'HC-20', 'bidon', 118.0, 1, 2, 3, 4, 4, 0, ['CP-01']),
    definir_article('filtre_hydr', 'FIL', 'Filtre hydraulique presse PR-01', 'Filtravel', 'FHY-410', 'u', 46.0, 1, 2, 3, 5, 4, 0, ['PR-01', 'PR-01.GH']),
    definir_article('huile_hlp46', 'LUB', 'Huile hydraulique HLP 46 (bidon 20 L)', 'Lubrazur', 'HL-46-20', 'bidon', 72.0, 1, 2, 3, 4, 4, 0, ['PR-01', 'PR-01.GH']),
    definir_article('graisse', 'LUB', 'Graisse EP2 (cartouche 400 g)', 'Lubrazur', 'GR-EP2', 'cartouche', 6.5, 10, 20, 48, 3, 4, 0, ['@convoyeur', '@pompe', '@usinage', '@levage', '@emballage', '@presse', '@ventilation', '@broche', '@changeur', '@moteur']),
    definir_article('liq_coupe', 'LUB', 'Liquide de coupe soluble (bidon 20 L)', 'Lubrazur', 'LC-20', 'bidon', 94.0, 1, 2, 3, 5, 4, 0, ['CN-01', 'CU-01']),
    definir_article('filtre_g4', 'FIL', 'Filtre à air G4 592x592', 'Filtravel', 'G4-592', 'u', 22.0, 4, 8, 16, 5, 4, 0, ['VE-01', 'VE-02']),
    definir_article('filtre_eau', 'FIL', 'Cartouche filtrante circuit eau glacée', 'Filtravel', 'CE-25', 'u', 16.0, 2, 4, 8, 5, 4, 0, ['GF-01', 'PO-01']),
    definir_article('cart_secheur', 'FIL', "Cartouche déshydratante du sécheur d'air", 'Filtravel', 'CD-80', 'u', 49.0, 1, 2, 4, 6, 4, 0, ['CP-01.SEC']),
    definir_article('nettoyant', 'LUB', 'Nettoyant contacts et capteurs (aérosol)', 'Lubrazur', 'NC-400', 'u', 7.2, 4, 8, 24, 3, 4, 0, ['@convoyeur', '@emballage', '@levage', '@froid', '@pompe', '@usinage', '@changeur']),
    # --- Électricité et automatisme (Électro-Alpes)
    definir_article('contacteur_25', 'ELE', 'Contacteur tripolaire 25 A bobine 24 V', 'Voltavel', 'VC-25-24', 'u', 29.0, 2, 3, 6, 4, 3, 1, ['@electrique', '@convoyeur', '@emballage'], 1, cible=1),
    definir_article('contacteur_40', 'ELE', 'Contacteur tripolaire 40 A bobine 230 V', 'Voltavel', 'VC-40-230', 'u', 41.0, 1, 2, 3, 4, 3, 0, ['PT-01', 'CH-01', 'CP-01', '@pompe']),
    definir_article('relais_th', 'ELE', 'Relais thermique 9-13 A', 'Voltavel', 'RT-913', 'u', 38.0, 1, 2, 3, 4, 3, 0, ['@pompe', 'CP-01']),
    definir_article('disj_moteur', 'ELE', 'Disjoncteur moteur 10-16 A', 'Voltavel', 'DM-1016', 'u', 52.0, 1, 2, 3, 4, 3, 0, ['@electrique', 'CP-01']),
    definir_article('fusible', 'ELE', 'Fusibles gG 25 A (boîte de 10)', 'Voltavel', 'FU-25-10', 'boîte', 17.0, 1, 2, 4, 3, 3, 0, ['@electrique']),
    definir_article('capteur_m18', 'ELE', 'Capteur inductif M18 PNP', 'Detectis', 'DI-M18-PNP', 'u', 17.5, 3, 4, 8, 4, 3, 1, ['@convoyeur', '@emballage', 'PR-01', '@changeur'], 1, cible=3),
    definir_article('cellule', 'ELE', 'Cellule photoélectrique réflex', 'Detectis', 'PE-R30', 'u', 36.0, 1, 2, 4, 5, 3, 0, ['@convoyeur', '@emballage', 'PT-01']),
    definir_article('arret_urg', 'ELE', "Bouton d'arrêt d'urgence à clé", 'Voltavel', 'AU-22-K', 'u', 24.0, 1, 2, 3, 4, 3, 1, ['@electrique', '@convoyeur']),
    definir_article('relais_secu', 'ELE', 'Relais de sécurité 24 V', 'Voltavel', 'RS-24', 'u', 128.0, 1, 1, 2, 8, 3, 1, ['PR-01', 'RB-01', 'CN-01']),
    definir_article('alim_24v', 'ELE', 'Alimentation 24 V 10 A', 'Voltavel', 'AL-2410', 'u', 92.0, 1, 1, 2, 6, 3, 0, ['@electrique', 'RB-01', 'EM-01']),
    definir_article('variateur', 'ELE', 'Variateur de fréquence 2,2 kW', 'Voltavel', 'VF-22', 'u', 310.0, 1, 1, 2, 12, 3, 1, ['@convoyeur', 'VE-01']),
    definir_article('res_soudure', 'ELE', 'Résistance de soudure de fardeleuse', 'Emballor', 'RS-90', 'u', 46.0, 1, 2, 3, 8, 3, 0, ['EM-01']),
    # --- Pneumatique, hydraulique, outillage (Fluidalpes et Mécaroule)
    definir_article('flex_hydr', 'HYD', 'Flexible hydraulique DN10 serti (1 m)', 'Hydronel', 'FX-DN10', 'u', 34.0, 2, 3, 6, 5, 2, 0, ['PR-01', 'PR-01.GH']),
    definir_article('flex_air', 'PNE', 'Flexible air comprimé DN13 (au mètre)', 'Hydronel', 'FA-DN13', 'm', 5.6, 5, 10, 30, 4, 2, 0, ['CP-01', '@emballage', '@presse']),
    definir_article('raccord', 'PNE', 'Raccord rapide pneumatique G1/4', 'Hydronel', 'RR-14', 'u', 6.4, 6, 10, 30, 3, 2, 0, ['CP-01', '@emballage', '@usinage']),
    definir_article('electrovanne', 'PNE', 'Électrovanne 5/2 24 V G1/4', 'Hydronel', 'EV-52-24', 'u', 74.0, 1, 2, 3, 6, 2, 0, ['@emballage', 'PR-01', 'CN-01']),
    definir_article('verin', 'PNE', 'Vérin pneumatique ISO Ø40 course 100', 'Hydronel', 'VP-40-100', 'u', 118.0, 1, 1, 2, 8, 2, 0, ['@emballage', 'CV-03']),
    definir_article('plaquettes', 'OUT', 'Plaquettes de tournage CNMG 120408 (boîte de 10)', 'Outilix', 'CN-120408', 'boîte', 62.0, 2, 4, 8, 4, 1, 0, ['CN-01']),
    definir_article('foret', 'OUT', 'Foret carbure Ø8', 'Outilix', 'FC-08', 'u', 21.0, 3, 5, 10, 4, 1, 0, ['CU-01']),
    definir_article('pince_er32', 'OUT', 'Pince de serrage ER32 Ø10', 'Outilix', 'ER32-10', 'u', 38.0, 1, 2, 3, 5, 1, 0, ['CU-01', 'CU-01.CH']),
    definir_article('roue_chariot', 'DIV', 'Roue polyuréthane de chariot Ø200', 'Manutrel', 'RP-200', 'u', 54.0, 2, 3, 4, 10, 1, 0, ['CH-01'], 4),
]

# Quelques pièces ont une version propre à un équipement : (repère, clé générique) -> clé spécifique.
PIECES_SPECIFIQUES = {('PO-02', 'kit_gar_u'): 'kit_gar_po02', ('PO-01', 'kit_gar_u'): 'kit_gar_po01'}

# Achats « en cours » à la date de référence : (clé d'article, statut, jours avant la date de référence).
ACHATS_EN_COURS = [('filtre_huile_cp', 'demandée', 3), ('contacteur_25', 'demandée', 11),
                   ('capteur_m18', 'commandée', 7)]

# Inventaire annuel (début janvier) : écart entre le stock compté et le stock théorique, par article
# (cartouches de graisse entamées, aérosol perdu, raccord retrouvé). Les autres articles : aucun écart.
ECARTS_INVENTAIRE = {'graisse': -2, 'nettoyant': -1, 'raccord': 1}

# ---------------------------------------------------------------------------
# Gammes de préventif : opérations (texte, valeur attendue, mesure simulée)
# mesure : None = rien à mesurer, 'ok' = simple constat,
# (min, max, décimales, unité, libellé court) = valeur relevée
# ---------------------------------------------------------------------------

OPS_COMPRESSEUR_MENSUEL = [
    ('Relever les heures de marche et la pression de service', '6 à 7,5 bar', (6.3, 7.2, 1, ' bar', 'pression de service')),
    ("Contrôler le niveau d'huile", 'Entre mini et maxi', 'ok'),
    ('Purger les condensats du réservoir et du sécheur', 'Purge fonctionnelle', 'ok'),
    ("Nettoyer les ailettes du radiateur d'huile", 'Propres', 'ok'),
    ('Relever la température de refoulement', '< 95 °C', (78, 92, 0, ' °C', 'température de refoulement')),
    ("Vérifier l'absence de fuite d'huile ou d'air", 'Aucune fuite', 'ok'),
    ('Contrôler le serrage des raccords et des protecteurs', 'Serrés', 'ok'),
]
OPS_COMPRESSEUR_2000H = [
    ("Remplacer le filtre à air", 'Filtre neuf posé', 'ok'),
    ("Remplacer la cartouche du filtre à huile", 'Cartouche neuve posée', 'ok'),
    ("Remplacer l'huile du compresseur", 'Niveau entre mini et maxi', 'ok'),
    ('Mesurer la perte de charge du séparateur', '< 0,8 bar', (0.2, 0.6, 1, ' bar', 'perte de charge du séparateur')),
    ("Contrôler l'état de la courroie et son alignement", 'Pas de fissure', 'ok'),
    ('Contrôler le pressostat et la soupape de sécurité', 'Déclenchement à 8,5 bar', (8.3, 8.6, 1, ' bar', 'tarage de la soupape')),
    ('Relever la température de refoulement en charge', '< 95 °C', (80, 91, 0, ' °C', 'température en charge')),
    ('Remettre à zéro le compteur de maintenance', 'Compteur remis à zéro', 'ok'),
]
OPS_SEPARATEUR = [
    ('Relever la perte de charge du séparateur avant intervention', '>= 0,8 bar (seuil atteint)',
     (0.80, 0.86, 2, ' bar', 'perte de charge avant')),
    ("Consigner le compresseur et purger le circuit d'air jusqu'à 0 bar", 'Circuit à 0 bar', 'ok'),
    ('Remplacer le séparateur air/huile et ses joints', 'Séparateur neuf posé', 'ok'),
    ("Contrôler le niveau d'huile après remise en route", 'Entre mini et maxi', 'ok'),
    ('Relever la perte de charge après remplacement', '< 0,3 bar', (0.18, 0.27, 2, ' bar', 'perte de charge après')),
]
OPS_POMPE = [
    ("Relever l'intensité absorbée", '< 12 A', (8.5, 11.2, 1, ' A', 'intensité absorbée')),
    ("Contrôler l'étanchéité de la garniture", 'Moins de 5 gouttes par minute', 'ok'),
    ('Mesurer les vibrations au palier côté moteur', '< 4,5 mm/s', (1.8, 3.9, 1, ' mm/s', 'vibrations au palier')),
    ('Graisser les paliers', 'Graissage effectué', 'ok'),
    ("Contrôler le serrage de l'accouplement et du socle", 'Serrés', 'ok'),
]
OPS_CONVOYEUR = [
    ('Contrôler la tension et le centrage de la bande', 'Bande centrée', 'ok'),
    ("Contrôler l'état des galets et des paliers", 'Aucun galet bloqué', 'ok'),
    ('Nettoyer les capteurs de présence', 'Capteurs propres', 'ok'),
    ('Graisser les paliers', 'Graissage effectué', 'ok'),
    ("Tester l'arrêt d'urgence", 'Arrêt immédiat', 'ok'),
]
OPS_VENTILATION = [
    ('Mesurer la perte de charge des filtres', '< 150 Pa', (70, 130, 0, ' Pa', 'perte de charge des filtres')),
    ('Contrôler la tension de la courroie', 'Flèche conforme', 'ok'),
    ('Écouter les paliers (bruit, vibration)', 'Pas de bruit anormal', 'ok'),
    ("Relever l'intensité du moteur", '< 6,5 A', (4.2, 5.9, 1, ' A', 'intensité du moteur')),
]
OPS_PRESSE = [
    ("Contrôler le niveau d'huile hydraulique", 'Entre mini et maxi', 'ok'),
    ('Relever la pression de service', '180 à 200 bar', (184, 197, 0, ' bar', 'pression de service')),
    ('Rechercher les fuites sur les flexibles et les vérins', 'Aucune fuite', 'ok'),
    ('Graisser les colonnes de guidage', 'Graissage effectué', 'ok'),
    ('Tester le rideau lumineux de sécurité', 'Arrêt immédiat à la coupure', 'ok'),
    ("Relever la température de l'huile", '< 55 °C', (41, 52, 0, ' °C', "température de l'huile")),
]
OPS_ARMOIRES = [
    ('Faire une thermographie des jonctions et des départs', 'Écart < 10 K', (2, 8, 0, ' K', 'écart thermographique maximal')),
    ('Resserrer les bornes de puissance', 'Bornes serrées au couple', 'ok'),
    ("Dépoussiérer l'armoire et nettoyer les filtres de ventilation", 'Armoire propre', 'ok'),
    ('Tester les disjoncteurs différentiels', 'Déclenchement < 30 ms', (12, 24, 0, ' ms', 'temps de déclenchement du différentiel')),
    ("Contrôler la ventilation de l'armoire", 'Ventilateur en marche', 'ok'),
]
OPS_FROID = [
    ('Relever la pression haute (HP)', '< 18 bar', (14.0, 17.0, 1, ' bar', 'pression haute')),
    ('Nettoyer le condenseur', 'Condenseur propre', 'ok'),
    ('Rechercher les fuites de fluide au détecteur', 'Aucune fuite', 'ok'),
    ("Relever la température de départ d'eau glacée", '6 à 8 °C', (6.2, 7.8, 1, ' °C', "température de départ d'eau glacée")),
    ('Relever l\'intensité du compresseur', '< 85 A', (62, 80, 0, ' A', 'intensité du compresseur')),
    ("Changer la cartouche du filtre à eau", 'Cartouche neuve posée', 'ok'),
]
OPS_CHARIOT = [
    ("Contrôler l'état des fourches et du tablier", 'Pas de fissure ni de déformation', 'ok'),
    ('Contrôler le niveau de la batterie', 'Niveau correct', 'ok'),
    ('Tester les freins et le frein de parking', 'Chariot immobilisé en pente', 'ok'),
    ('Rechercher les fuites hydrauliques du mât', 'Aucune fuite', 'ok'),
    ("Mesurer l'épaisseur des bandages de roues", '> 20 mm', (24, 32, 0, ' mm', 'épaisseur des bandages')),
]
OPS_TOUR = [
    ('Contrôler le niveau de lubrifiant des glissières', 'Entre mini et maxi', 'ok'),
    ('Graisser la broche et la contre-pointe', 'Graissage effectué', 'ok'),
    ('Mesurer la concentration du liquide de coupe', '7 à 9 %', (7.4, 8.8, 1, ' %', 'concentration du liquide de coupe')),
    ('Nettoyer les filtres et le bac à copeaux', 'Filtres propres', 'ok'),
    ("Contrôler l'état des soufflets et des protections", 'Pas de déchirure', 'ok'),
    ("Tester la sécurité d'ouverture du capot", "Arrêt de la broche à l'ouverture", 'ok'),
]

# Gamme type par famille (jeu de charge) : (opérations, temps prévu, code remède)
GAMME_PAR_FAMILLE = {
    'compresseur': (OPS_COMPRESSEUR_MENSUEL, 1.5, 'R03'), 'pompe': (OPS_POMPE, 2.0, 'R05'),
    'convoyeur': (OPS_CONVOYEUR, 1.0, 'R05'), 'ventilation': (OPS_VENTILATION, 1.0, 'R03'),
    'presse': (OPS_PRESSE, 2.5, 'R05'), 'electrique': (OPS_ARMOIRES, 3.0, 'R04'),
    'froid': (OPS_FROID, 3.0, 'R03'), 'levage': (OPS_CHARIOT, 1.5, 'R05'),
    'usinage': (OPS_TOUR, 1.5, 'R05'), 'emballage': (OPS_CONVOYEUR, 1.0, 'R05'),
}

CONSIGNE_STANDARD = "Consigner l'équipement avant d'ouvrir un capot (voir la fiche de l'équipement)."

# Anomalies constatées pendant un préventif (ARCHITECTURE.md §14.6) : le technicien coche « anomalie
# constatée » et crée une DI liée (ot_origine_id). `suite` : 'acceptee' (la DI devient un correctif
# clôturé) ou 'nouvelle' (DI encore à traiter). Rattachées à une gamme par sa clé `anomalies`
# {rang de l'occurrence en partant de la plus récente : anomalie}.
ANOMALIE_PR01 = {
    'suite': 'acceptee', 'impact': 'gêne', 'symptome': 'S01', 'famille': 'presse', 'cause': 'C10',
    'roles': ('preventif_anomalie', 'di_anomalie_acceptee', 'ot_correctif_anomalie'),
    'texte': "Suintement d'huile sur le flexible du vérin gauche, vu pendant le contrôle préventif.",
    'constat': "Anomalie constatée : suintement d'huile sur le flexible du vérin gauche ; "
               "demande d'intervention créée pour son remplacement."}
ANOMALIE_GF01 = {
    'suite': 'nouvelle', 'impact': 'gêne', 'symptome': 'S02',
    'roles': ('preventif_anomalie_nouvelle', 'di_anomalie_nouvelle'),
    'texte': 'Ventilateur du condenseur de GF-01 bruyant (roulement probable), vu pendant le préventif.',
    'constat': "Anomalie constatée : ventilateur du condenseur bruyant, roulement probablement usé ; "
               "demande d'intervention créée."}

# Les 10 gammes de la démo (les trois déclencheurs). `derniere` = date de la dernière réalisation.
# `ouvert` : statut de l'OT préventif ouvert à la date de référence (None = aucun OT ouvert).
# `sans_ot` : la gamme est échue mais RIEN n'a encore généré d'OT (scénario de recette « gamme échue »).
# Gamme seuil : sa dernière réalisation se déduit des relevés de son point de mesure (§5).
# `role` / `role_ot` : rôle de scénario de la gamme / de son OT ouvert (tests/fixtures/demo-scenarios.json).
GAMMES_DEMO = [
    {'repere': 'CP-01', 'libelle': 'Entretien mensuel du compresseur CP-01', 'periode': 30, 'avance': 3,
     'derniere': '2026-09-29', 'temps': 1.5, 'ops': OPS_COMPRESSEUR_MENSUEL, 'metiers': [MECA],
     'pieces': [], 'remede': 'R03', 'consignes': CONSIGNE_STANDARD},
    {'repere': 'CP-01', 'libelle': 'Entretien des 2000 heures du compresseur CP-01', 'compteur': 'cp01',
     'unites': 2000, 'avance': 5, 'ecart': 0.5, 'temps': 4.0, 'ops': OPS_COMPRESSEUR_2000H,
     'metiers': [MECA], 'pieces': [('filtre_air_cp', 1), ('filtre_huile_cp', 1), ('huile_cp', 1)],
     'remede': 'R01', 'consignes': CONSIGNE_STANDARD, 'role': 'gamme_compteur_sans_ot'},
    {'repere': 'PO-02', 'libelle': 'Contrôle trimestriel de la pompe PO-02', 'periode': 90, 'avance': 7,
     'derniere': '2026-08-04', 'temps': 2.0, 'ops': OPS_POMPE, 'metiers': [MECA, POLY],
     'pieces': [('graisse', 1)], 'remede': 'R05', 'consignes': CONSIGNE_STANDARD},
    {'repere': 'CV-01', 'libelle': 'Contrôle mensuel du convoyeur CV-01', 'periode': 30, 'avance': 3,
     'derniere': '2026-09-14', 'temps': 1.0, 'ops': OPS_CONVOYEUR, 'metiers': [POLY, MECA],
     'pieces': [('graisse', 1)], 'remede': 'R05', 'consignes': CONSIGNE_STANDARD, 'sans_ot': True,
     'sans_decalage': True, 'role': 'gamme_mensuelle_echue'},
    {'repere': 'VE-01', 'libelle': 'Contrôle mensuel de la ventilation VE-01', 'periode': 30, 'avance': 3,
     'derniere': '2026-10-06', 'temps': 1.0, 'ops': OPS_VENTILATION, 'metiers': [POLY],
     'pieces': [], 'remede': 'R03', 'consignes': CONSIGNE_STANDARD, 'toujours_ras': True,
     'role': 'gamme_sans_constat'},
    {'repere': 'PR-01', 'libelle': 'Contrôle hydraulique et graissage de la presse PR-01', 'periode': 60,
     'avance': 5, 'derniere': '2026-09-02', 'temps': 2.5, 'ops': OPS_PRESSE, 'metiers': [MECA],
     'pieces': [('graisse', 1)], 'remede': 'R05', 'consignes': CONSIGNE_STANDARD,
     'anomalies': {3: ANOMALIE_PR01}},
    {'repere': 'CP-01', 'libelle': 'Remplacement du séparateur air/huile de CP-01 (perte de charge)',
     'compteur': 'cp01_sep', 'declencheur': 'seuil', 'avance': 0, 'temps': 2.0, 'ops': OPS_SEPARATEUR,
     'metiers': [MECA], 'pieces': [('separ_cp', 1)], 'remede': 'R01', 'consignes': CONSIGNE_STANDARD,
     'role': 'gamme_seuil'},
    {'repere': 'GF-01', 'libelle': 'Entretien trimestriel du groupe froid GF-01', 'periode': 90, 'avance': 7,
     'derniere': '2026-10-13', 'temps': 3.0, 'ops': OPS_FROID, 'metiers': [MECA, ELEC],
     'pieces': [('filtre_eau', 1)], 'remede': 'R03', 'consignes': CONSIGNE_STANDARD,
     'anomalies': {1: ANOMALIE_GF01}},
    {'repere': 'CH-01', 'libelle': 'Vérification du chariot CH-01 toutes les 200 heures', 'compteur': 'ch01',
     'unites': 200, 'avance': 5, 'ecart': 'echue', 'temps': 1.5, 'ops': OPS_CHARIOT, 'metiers': [MECA, POLY],
     'pieces': [('graisse', 1)], 'remede': 'R05', 'consignes': 'Débrancher la batterie avant toute intervention.',
     'ouvert': 'Créé', 'role': 'gamme_compteur_echue', 'role_ot': 'ot_statut_cree'},
    {'repere': 'CN-01', 'libelle': 'Graissage et contrôle mensuel du tour CN-01', 'periode': 30, 'avance': 3,
     'derniere': '2026-09-17', 'temps': 1.5, 'ops': OPS_TOUR, 'metiers': [POLY, AUTO],
     'pieces': [('graisse', 1), ('liq_coupe', 1)], 'remede': 'R05', 'consignes': CONSIGNE_STANDARD,
     'ouvert': 'Planifié', 'tech_ouvert': 4, 'role_ot': 'ot_preventif_ouvert'},
]

COMPTEURS_DEMO = [      # clé, repère, libellé, unité, valeur au premier relevé, rythme par jour calendaire
    {'cle': 'cp01', 'repere': 'CP-01', 'libelle': 'Compteur horaire de marche', 'unite': 'h',
     'depart': 11480, 'par_jour': 11.4, 'role': 'compteur_horaire'},
    {'cle': 'pr01', 'repere': 'PR-01', 'libelle': 'Compteur de cycles de la presse', 'unite': 'cycles',
     'depart': 1482000, 'par_jour': 1100},
    {'cle': 'ch01', 'repere': 'CH-01', 'libelle': 'Compteur horaire du chariot', 'unite': 'h',
     'depart': 3120, 'par_jour': 4.6},
    # Point de MESURE (gamme seuil) : la valeur monte avec l'encrassement, retombe à `apres` quand
    # l'intervention est faite. `seuil` = valeur qui déclenche la gamme.
    {'cle': 'cp01_sep', 'repere': 'CP-01', 'libelle': 'Perte de charge du séparateur air/huile', 'unite': 'bar',
     'mesure': True, 'depart': 0.40, 'par_jour': 0.0021, 'seuil': 0.8, 'apres': 0.22, 'decimales': 2,
     'role': 'compteur_seuil'},
]

# Contrôles réglementaires : (repère, nature, texte de référence, périodicité en mois, organisme,
# date du dernier contrôle, observations, observations levées ?). Prochaine date = dernière +
# périodicité. À la date de référence (§15.7), ils couvrent les quatre statuts : chariot en retard,
# réservoir avec observations à lever, installations électriques à planifier (moins de 30 jours), les
# autres à jour.
# Textes (lot 3) : VGP tous les 6 mois pour les chariots élévateurs (arrêté du 1er mars 2004, art. 23 a,
# qui renvoie à l'art. 20 II), 12 mois pour le pont roulant ; installations électriques : vérification
# PÉRIODIQUE (art. R4226-16 ; R4226-14 est la vérification initiale) et son arrêté du 26 décembre 2011.
ORGANISME_1 = 'Bureau Alpin de Contrôle (démo)'
CATALOGUE_CONTROLES = RACINE / 'docs' / 'catalogue' / 'controles-fr.json'   # catalogue validé (D193)
# (repère, identifiant du catalogue, organisme, date du dernier contrôle, observations, observations levées ?).
# Nature, référence et périodicité viennent du catalogue validé : PT-01 C01, CH-01 C03, AE-01 C12, RA-01 C14 (48 mois ;
# 36 mois = première inspection), GF-01 C16 (5 à < 50 t éq. CO2, 12 mois), VE-02 C20 (arrêté du 8 octobre 1987).
CONTROLES_DEMO = [
    ('PT-01', 'C01', ORGANISME_1, '2026-02-10', '', 1),
    ('CH-01', 'C03', ORGANISME_1, '2026-03-18', '', 1),
    ('AE-01', 'C12', 'Certif-Elec Services (démo)', '2025-11-12', '', 1),
    ('RA-01', 'C14', 'Bureau Alpin de Contrôle (démo)', '2025-04-03',
     'Purgeur automatique du réservoir défectueux : à remplacer avant la prochaine inspection.', 0),
    ('GF-01', 'C16', 'Frigo-Contrôle Sud (démo)', '2026-03-24', '', 1),
    ('VE-02', 'C20', ORGANISME_1, '2026-06-02', '', 1),
]
# Réserves relevées au contrôle d'AE-01 du 12/11/2025 (T417) : une levée (avec l'OT réglementaire du contrôle), une
# ouverte dont l'échéance saisie est à venir. Dates fixes, aucun tirage.
RESERVES_AE01 = [
    {'texte': "Différentiel 30 mA du tableau de l'atelier à remplacer.", 'levee': 1, 'date_levee': '2025-12-09',
     'commentaire_levee': "Différentiel remplacé, essai de déclenchement conforme."},
    {'texte': 'Schéma unifilaire du tableau général à mettre à jour.', 'levee': 0, 'echeance_levee': '2026-12-15'},
]


def ligne_catalogue(identifiant):
    """Ligne du catalogue validé des contrôles (docs/catalogue/controles-fr.json) pour un identifiant Cnn."""
    lignes = json.loads(CATALOGUE_CONTROLES.read_text(encoding='utf-8'))['lignes']
    return next(ligne for ligne in lignes if ligne['id'] == identifiant)
# Contrôles dont la dernière date a été recalée au lot 3 (chariot : passage de 12 à 6 mois, dernière VGP
# en mars 2026 pour rester en retard). L'OT réglementaire de cette VGP tire son hasard dans le
# générateur du lot 3 : le reste du jeu reste identique.
CONTROLES_RECALES_LOT3 = ('CH-01',)
STATUTS_CONTROLE = ('en retard', 'observations à lever', 'à planifier', 'à jour')     # §15.7, dans l'ordre

# Opérations ponctuelles écrites à la main : titre, équipement, jours avant la date de référence, etc.
AMELIORATIONS_DEMO = [
    {'repere': 'CV-03', 'jours': 95, 'titre': 'Ajout du carter de protection sur le tambour de CV-03',
     'travail': "Fabriquer et poser un carter fixe sur le tambour d'entraînement (demande de sécurité).",
     'compte_rendu': "Carter en tôle pliée posé sur le tambour d'entraînement, fixé par vis imperdables. Contrôle de l'accessibilité pour le nettoyage : conforme.",
     'heures': 4.0, 'metiers': [MECA, POLY]},
    {'repere': 'CP-01', 'jours': 60, 'titre': 'Pose de la sonde de température supplémentaire sur CP-01',
     'travail': "Installer une seconde sonde de température au refoulement et l'afficher sur l'armoire.",
     'compte_rendu': "Sonde PT100 posée au refoulement et câblée sur l'automate, seuil d'alerte à 90 °C configuré avant le seuil d'arrêt à 100 °C. Essais validés.",
     'heures': 3.5, 'metiers': [AUTO, ELEC]},
]


# =============================================================================
# 4. GÉNÉRATION TABLE PAR TABLE
# =============================================================================

# Tables dont les identifiants sont attribués à la fin, dans l'ordre chronologique (§7).
TABLES_ID_DIFFERE = ('demandes', 'ordres_travail', 'ot_operations', 'ot_pieces', 'ot_temps',
                     'mouvements_stock', 'achats')


class Contexte:
    """Tout l'état de la génération : graine, dates, tables en construction, catalogues."""

    def __init__(self, mois, volume=None):
        self.rng = random.Random(GRAINE)
        self.rng_lot3 = random.Random(GRAINE_LOT3)    # hasard des ajouts du lot 3 (voir hasard_du_lot3)
        self.rng_lot3bis = random.Random(GRAINE_LOT3BIS)   # hasard des ajouts du lot 3 bis (hasard_du_lot3bis)
        self.rng_lot6 = random.Random(GRAINE_LOT6)    # hasard des ajouts du lot 6 (hasard_du_lot6)
        self.mois = mois
        self.volume = volume                          # None ou (nombre d'équipements, nombre d'OT)
        self.ref = jour_depuis_texte(DATE_REFERENCE)
        self.maintenant = instant(self.ref, HEURE_COURANTE)
        self.debut = ajouter_mois(self.ref, -mois)    # premier jour de l'historique
        self.avis_wiki = ''                           # wiki figé non repris (autre jeu que la démo standard)
        self.base = {table: [] for table in NOMS_TABLES}
        self.numeros = {}                             # compteurs d'identifiants
        self.localisations = {}                       # clé interne -> identifiant
        self.codes = {}                               # code (S01...) -> ligne
        self.fournisseurs = []                        # identifiants
        self.techniciens = []                         # dictionnaires {id, nom, prenom, metier}
        self.habilitations = {}                       # (technicien, intitulé en minuscules) -> [(du, au)]
        self.equipements = []                         # dictionnaires (catalogue + id)
        self.equipement = {}                          # repère -> dictionnaire
        self.articles = {}                            # clé -> dictionnaire (catalogue + id + ligne)
        self.liens = {}                               # (clé article, repère) -> quantité
        self.compteurs = {}                           # clé -> dictionnaire (relevés...)
        self.gammes = []                              # dictionnaires (gamme + occurrences)
        self.controles = []                           # contrôles réglementaires (équipement + champs)
        self.sorties = []                             # sorties de stock prévues (voir §6)
        self.retours = []
        self.specifications_gammes = []               # gammes à créer (démo ou jeu de charge)
        self.definitions_compteurs = []               # compteurs à créer (démo ou jeu de charge)
        self.marques = {}                             # rôle de scénario -> ligne (voir §7, scénarios)
        self.attentes = []                            # périodes « En attente » passées des OT (§5 bis, journal)
        self.anomalies_sans_di = []                   # préventifs à case cochée, réglés sur place (§5 ter)
        self.di_apres_verrou = []                     # DI liées à une visite déjà verrouillée (§5 ter)
        self.gammes_lot3bis = {}                      # 'anomalies' / 'refus' -> ligne de gammes.csv (§5 ter)

    def marquer(self, role, ligne):
        """Retient la ligne qui joue un rôle de scénario (son identifiant n'est connu qu'à la fin)."""
        if role in self.marques:
            raise ErreurCoherence('Rôle de scénario attribué deux fois : ' + role)
        self.marques[role] = ligne
        return ligne

    @property
    def fin_historique(self):
        """Dernier jour où l'on peut avoir terminé une intervention (la veille de la date de référence)."""
        return self.ref - timedelta(days=1)


@contextmanager
def hasard_du_lot3(ctx):
    """Pendant le bloc, ctx.rng est le générateur du lot 3 (graine GRAINE_LOT3).

    Les ajouts du lot 3 tirent ainsi leurs nombres au hasard à part : la suite des tirages du générateur
    principal reste la même qu'au lot 2, donc toutes les autres lignes du jeu restent identiques.
    """
    principal = ctx.rng
    ctx.rng = ctx.rng_lot3
    try:
        yield
    finally:
        ctx.rng = principal


@contextmanager
def hasard_du_lot3bis(ctx):
    """Pendant le bloc, ctx.rng est le générateur du lot 3 bis (graine GRAINE_LOT3BIS).

    Même principe que hasard_du_lot3 : les tirages des lots 1 à 3 restent les mêmes, donc le contenu de
    leurs lignes aussi.
    """
    principal = ctx.rng
    ctx.rng = ctx.rng_lot3bis
    try:
        yield
    finally:
        ctx.rng = principal


@contextmanager
def hasard_du_lot6(ctx):
    """Pendant le bloc, ctx.rng est le générateur du lot 6 (graine GRAINE_LOT6).

    Même principe que hasard_du_lot3 : les tirages des lots précédents restent les mêmes, donc le contenu de
    leurs lignes aussi (seule la colonne astuce s'ajoute).
    """
    principal = ctx.rng
    ctx.rng = ctx.rng_lot6
    try:
        yield
    finally:
        ctx.rng = principal


def nouvel_identifiant(ctx, table, annee=None):
    """Identifiant suivant d'une table (LOC-0001, DI-2026-0001...), selon le format du schéma."""
    prefixe, chiffres, annuel = IDENTIFIANTS[table]
    cle = (table, annee if annuel else None)
    numero = ctx.numeros.get(cle, 0) + 1
    ctx.numeros[cle] = numero
    return prefixe + ('%s-' % annee if annuel else '') + str(numero).zfill(chiffres)


def creer_ligne(ctx, table, **valeurs):
    """Ajoute une ligne à une table. Les champs non fournis prennent '' (ou 0 / 1 pour booléen / actif)."""
    ligne = {}
    for champ in CHAMPS[table]:
        nom = champ['nom']
        if nom in valeurs:
            ligne[nom] = valeur_en_texte(valeurs.pop(nom))
        elif nom == 'id' and table not in TABLES_ID_DIFFERE and table in IDENTIFIANTS:
            ligne[nom] = nouvel_identifiant(ctx, table)
        elif nom == 'actif':
            ligne[nom] = '1'
        elif champ['type'] == 'booleen':
            ligne[nom] = '0'
        else:
            ligne[nom] = ''
    if valeurs:
        raise KeyError('Champs inconnus pour %s : %s' % (table, ', '.join(valeurs)))
    ctx.base[table].append(ligne)
    return ligne


def renseigner(ligne, **valeurs):
    """Modifie des champs d'une ligne existante (valeurs converties en texte)."""
    for nom, valeur in valeurs.items():
        if nom not in ligne:
            raise KeyError('Champ inconnu : ' + nom)
        ligne[nom] = valeur_en_texte(valeur)


# ---------------------------------------------------------------------------
# Localisations, codes de défaillance, fournisseurs
# ---------------------------------------------------------------------------

def generer_localisations(ctx):
    for cle, libelle, parent, type_localisation in LOCALISATIONS:
        ligne = creer_ligne(ctx, 'localisations', libelle=libelle,
                            parent_id=ctx.localisations.get(parent, ''), type=type_localisation)
        ctx.localisations[cle] = ligne['id']


def generer_codes_defaillance(ctx):
    for famille, liste in (('symptôme', CODES_SYMPTOMES), ('cause', CODES_CAUSES), ('remède', CODES_REMEDES)):
        for code, libelle in liste:
            ctx.codes[code] = creer_ligne(ctx, 'codes_defaillance', famille=famille, code=code,
                                          libelle=libelle)


def generer_fournisseurs(ctx):
    for nom, contact, telephone, courriel in FOURNISSEURS:
        ligne = creer_ligne(ctx, 'fournisseurs', nom=nom, contact=contact, telephone=telephone,
                            email=courriel)
        ctx.fournisseurs.append(ligne['id'])


# ---------------------------------------------------------------------------
# Techniciens et habilitations
# ---------------------------------------------------------------------------

def generer_techniciens(ctx):
    """4 techniciens en démo ; 10 en jeu de charge (les 6 de plus ont toutes leurs habilitations)."""
    techniciens = list(TECHNICIENS_DEMO)
    if ctx.volume:
        metiers = [ELEC, MECA, AUTO, POLY]
        for numero, (nom, prenom) in enumerate(NOMS_SUPPLEMENTAIRES):
            techniciens.append((nom, prenom, metiers[numero % 4], 38 + (numero * 2) % 11))
    for nom, prenom, metier, taux in techniciens:
        ligne = creer_ligne(ctx, 'techniciens', nom=nom, prenom=prenom, metier=metier,
                            taux_horaire=taux, capacite_h_semaine=35)
        ctx.techniciens.append({'id': ligne['id'], 'nom': nom, 'prenom': prenom, 'metier': metier,
                                'taux': taux})
    habilitations = list(HABILITATIONS_DEMO)
    for numero in range(5, len(techniciens) + 1):
        habilitations += [(numero, 'BR', '2025-01-10', '2028-01-10'), (numero, 'H0V', '2025-01-10', '2028-01-10')]
    for numero, intitule, obtention, echeance in habilitations:
        technicien = ctx.techniciens[numero - 1]
        creer_ligne(ctx, 'habilitations', technicien_id=technicien['id'], intitule=intitule,
                    date_obtention=obtention, date_echeance=echeance)
        ctx.habilitations.setdefault((technicien['id'], intitule.lower()), []).append(
            (jour_depuis_texte(obtention), jour_depuis_texte(echeance)))


def habilitation_valide(ctx, technicien_id, intitule, jour):
    """Vrai si le technicien a une habilitation d'intitulé identique valide ce jour-là (RG8)."""
    for debut, fin in ctx.habilitations.get((technicien_id, intitule.strip().lower()), []):
        if debut <= jour <= fin:
            return True
    return False


def habilitations_exigees(equipement):
    return [h.strip() for h in re.split(r'[,/]', equipement['hab']) if h.strip()]


def choisir_technicien(ctx, metiers, equipement, jour, exclure=None):
    """Un technicien du bon métier, qui a les habilitations exigées par l'équipement ce jour-là."""
    exigees = habilitations_exigees(equipement)

    def convient(technicien):
        return (technicien is not exclure
                and all(habilitation_valide(ctx, technicien['id'], h, jour) for h in exigees))

    candidats = [t for t in ctx.techniciens if t['metier'] in metiers and convient(t)]
    if not candidats:
        candidats = [t for t in ctx.techniciens if convient(t)]
    if not candidats:
        candidats = [t for t in ctx.techniciens if t is not exclure] or ctx.techniciens
    return ctx.rng.choice(candidats)


# ---------------------------------------------------------------------------
# Équipements
# ---------------------------------------------------------------------------

def equipements_du_jeu_de_charge(ctx, nombre):
    """Parc du jeu de charge : `nombre` équipements répartis par famille (repères PO-001, CV-002...)."""
    rng = ctx.rng
    poids_total = sum(famille[8] for famille in FAMILLES_VOLUME)
    quantites = [max(1, int(round(nombre * famille[8] / poids_total))) for famille in FAMILLES_VOLUME]
    quantites[1] += nombre - sum(quantites)           # ajuste pour tomber pile sur `nombre`
    emplacement = {'pompe': 'utilites', 'convoyeur': 'ligne_cond', 'compresseur': 'utilites',
                   'presse': 'ligne_asm', 'usinage': 'cellule_cn', 'electrique': 'utilites',
                   'ventilation': 'utilites', 'froid': 'utilites', 'levage': 'assemblage',
                   'emballage': 'ligne_cond'}
    catalogue = []
    for (famille, prefixe, designation, marque, modele, energies, heures, taux, _poids, habilitation), quantite \
            in zip(FAMILLES_VOLUME, quantites):
        for numero in range(1, quantite + 1):
            serie = ('%s-%d-%04d' % (prefixe, rng.randint(10, 24), rng.randint(1, 9999)) if numero % 7
                     else '%08d' % rng.randint(1, 9999999))
            catalogue.append(definir_equipement(
                '%s-%03d' % (prefixe, numero), '%s %d' % (designation, numero), emplacement[famille], None,
                marque, modele, serie, '%d-%02d-%02d' % (rng.randint(2008, 2025), rng.randint(1, 12), rng.randint(1, 28)),
                rng.choices(['A', 'B', 'C'], weights=[2, 5, 3])[0], heures, habilitation, energies, '',
                famille, round(taux * rng.uniform(0.5, 1.5), 3)))
            minimum, maximum = FOURCHETTES_VALEUR[famille]
            catalogue[-1]['valeur'] = rng.randrange(minimum, maximum + 1, 100)     # arrondi à la centaine
    return catalogue


def generer_equipements(ctx):
    catalogue = (equipements_du_jeu_de_charge(ctx, ctx.volume[0]) if ctx.volume else EQUIPEMENTS_DEMO)
    for entree in catalogue:
        parent = ctx.equipement.get(entree['parent']) if entree['parent'] else None
        ligne = creer_ligne(
            ctx, 'equipements', repere=entree['repere'], designation=entree['designation'],
            localisation_id=ctx.localisations[entree['loc']], parent_id=parent['id'] if parent else '',
            marque=entree['marque'], modele=entree['modele'], num_serie=entree['num_serie'],
            date_mes=entree['mes'], criticite=entree['crit'], statut=entree['statut'],
            heures_fonct_jour=entree['heures'] if entree['heures'] is not None else '',
            habilitation_requise=entree['hab'],
            consignation=texte_consignation(entree['energies'], entree['precision']),
            actif=0 if entree['statut'] == 'rebut' else 1,
            valeur_remplacement=entree.get('valeur') or VALEURS_REMPLACEMENT_DEMO[entree['repere']])
        meta = dict(entree, id=ligne['id'], ligne=ligne)
        ctx.equipements.append(meta)
        ctx.equipement[entree['repere']] = meta


# ---------------------------------------------------------------------------
# Articles et liens article-équipement
# ---------------------------------------------------------------------------

FAMILLE_PAR_REPERE_DEMO = {e['repere']: e['famille'] for e in EQUIPEMENTS_DEMO}


def generer_articles(ctx):
    """Crée les articles (le stock est calculé plus tard, depuis les mouvements, §6)."""
    compteur_emplacement = {}
    compteur_reference = {}
    for definition in ARTICLES:
        fournisseur = definition['fournisseur']
        compteur_emplacement[fournisseur] = compteur_emplacement.get(fournisseur, 0) + 1
        place = compteur_emplacement[fournisseur] - 1
        emplacement = '%s%d-%02d' % ('ABCDE'[fournisseur - 1], place // 8 + 1, place % 8 + 1)
        compteur_reference[definition['categorie']] = compteur_reference.get(definition['categorie'], 0) + 1
        reference = '%s-%03d' % (definition['categorie'], compteur_reference[definition['categorie']])
        ligne = creer_ligne(
            ctx, 'articles', reference=reference, designation=definition['designation'],
            fabricant=definition['fabricant'], ref_fabricant=definition['ref_fab'], emplacement=emplacement,
            unite=definition['unite'], stock_securite=definition['sec'], point_commande=definition['pc'],
            qte_commande=definition['qte'], delai_jours=definition['delai'], prix_unitaire=definition['prix'],
            fournisseur_id=ctx.fournisseurs[fournisseur - 1], critique=definition['critique'])
        ctx.articles[definition['cle']] = dict(definition, id=ligne['id'], ligne=ligne)
        for cible in definition['liens']:
            if cible.startswith('@'):
                reperes = [e['repere'] for e in ctx.equipements
                           if e['famille'] == cible[1:] and e['statut'] != 'rebut']
            elif cible in ctx.equipement:
                reperes = [cible]
            elif ctx.volume and cible in FAMILLE_PAR_REPERE_DEMO:      # jeu de charge : par famille
                reperes = [e['repere'] for e in ctx.equipements
                           if e['famille'] == FAMILLE_PAR_REPERE_DEMO[cible] and e['statut'] != 'rebut']
            else:
                reperes = []
            for repere in reperes:
                ctx.liens.setdefault((definition['cle'], repere), definition['qte_eq'])


def generer_liens_article_equipement(ctx):
    """Écrit article_equipement (appelé en fin de génération, quand tous les liens sont connus)."""
    for (cle, repere), quantite in ctx.liens.items():
        creer_ligne(ctx, 'article_equipement', article_id=ctx.articles[cle]['id'],
                    equipement_id=ctx.equipement[repere]['id'], quantite=quantite)


# ---------------------------------------------------------------------------
# Compteurs et relevés
# ---------------------------------------------------------------------------

def dates_de_releve(ctx):
    """Un relevé par mois (vers le 12), à partir du mois où commence l'historique."""
    jour = date(ctx.debut.year, ctx.debut.month, 12)
    dates = []
    while jour <= ctx.fin_historique:
        dates.append(jour_ouvre_avant(jour))
        jour = ajouter_mois(jour, 1)
    return dates


def simuler_compteur(ctx, definition, dates):
    """Relevés d'un compteur qui ne fait que monter (heures, cycles) : [(jour, valeur entière)]."""
    valeur = float(definition['depart'])
    precedent = None
    releves = []
    for jour in dates:
        if precedent is not None:
            valeur += definition['par_jour'] * (jour - precedent).days * ctx.rng.uniform(0.9, 1.1)
        precedent = jour
        releves.append((jour, int(round(valeur))))
    return releves


def simuler_mesure(ctx, definition, dates):
    """Relevés d'un point de MESURE (gamme seuil) : la valeur monte avec l'usure ou l'encrassement ;
    quand un relevé atteint le seuil, l'intervention est faite quelques jours plus tard et la valeur
    retombe à `apres`.

    Retourne (relevés [(jour, valeur)], déclenchements [(jour du relevé, valeur, jour d'exécution)]).
    Le jour d'exécution vaut None si l'intervention n'est pas encore faite à la date de référence
    (la gamme est alors échue).
    """
    rng = ctx.rng
    valeur = float(definition['depart'])
    precedent = None
    releves, declenchements = [], []
    for jour in dates:
        if precedent is not None:
            valeur += definition['par_jour'] * (jour - precedent).days * rng.uniform(0.85, 1.15)
        precedent = jour
        mesure = round(valeur, definition['decimales'])
        releves.append((jour, mesure))
        if mesure >= definition['seuil']:
            execution = jour_ouvre_apres(jour + timedelta(days=rng.randint(2, 5)))
            if execution <= ctx.ref - timedelta(days=2):
                declenchements.append((jour, mesure, execution))
                valeur, precedent = float(definition['apres']), execution     # remise à niveau
            else:
                declenchements.append((jour, mesure, None))
    return releves, declenchements


def generer_compteurs_et_releves(ctx):
    """Compteurs (heures, cycles) et points de mesure, avec un relevé par mois."""
    rng = ctx.rng
    noms = ['%s %s' % (t['prenom'], t['nom']) for t in ctx.techniciens]
    dates = dates_de_releve(ctx)
    for definition in ctx.definitions_compteurs:
        equipement = ctx.equipement[definition['repere']]
        ligne = creer_ligne(ctx, 'compteurs', equipement_id=equipement['id'],
                            libelle=definition['libelle'], unite=definition['unite'])
        compteur = dict(definition, id=ligne['id'], releves=[], declenchements=[])
        if definition.get('mesure'):
            compteur['releves'], compteur['declenchements'] = simuler_mesure(ctx, definition, dates)
        else:
            compteur['releves'] = simuler_compteur(ctx, definition, dates)
        for jour, valeur in compteur['releves']:
            creer_ligne(ctx, 'releves', compteur_id=ligne['id'], date=texte_date(jour), valeur=valeur,
                        utilisateur=rng.choice(noms))
        if definition.get('role'):
            ctx.marquer(definition['role'], ligne)
        ctx.compteurs[definition['cle']] = compteur


def date_pour_valeur(compteur, valeur):
    """Date (estimée par interpolation, puis extrapolation au rythme du compteur) où le compteur atteint `valeur`."""
    releves = compteur['releves']
    for (jour_a, valeur_a), (jour_b, valeur_b) in zip(releves, releves[1:]):
        if valeur_a <= valeur <= valeur_b:
            part = (valeur - valeur_a) / float(max(1, valeur_b - valeur_a))
            return jour_a + timedelta(days=int(round(part * (jour_b - jour_a).days)))
    dernier_jour, derniere_valeur = releves[-1]
    return dernier_jour + timedelta(days=int(round((valeur - derniere_valeur) / compteur['par_jour'])))


# ---------------------------------------------------------------------------
# Gammes de préventif
# ---------------------------------------------------------------------------

def preparer_gammes_et_compteurs(ctx):
    """Choisit les gammes à créer et les compteurs dont elles ont besoin (avant les relevés)."""
    if ctx.volume:
        ctx.specifications_gammes = gammes_du_jeu_de_charge(ctx)
    else:
        ctx.specifications_gammes = GAMMES_DEMO
        ctx.definitions_compteurs = list(COMPTEURS_DEMO)


def gammes_du_jeu_de_charge(ctx):
    """Jeu de charge : une gamme pour environ un équipement sur trois, avec les trois déclencheurs
    (70 % à date, 20 % au compteur horaire, 10 % sur seuil d'un point de mesure). Les compteurs
    nécessaires sont ajoutés à ctx.definitions_compteurs."""
    rng = ctx.rng
    eligibles = [e for e in ctx.equipements if e['famille'] in GAMME_PAR_FAMILLE and e['statut'] == 'en service']
    nombre = max(10, len(ctx.equipements) // 3)
    gammes = []
    for numero, equipement in enumerate(rng.sample(eligibles, min(nombre, len(eligibles))), 1):
        ops, temps, remede = GAMME_PAR_FAMILLE[equipement['famille']]
        commun = {'repere': equipement['repere'], 'temps': temps, 'ops': ops, 'metiers': [MECA, POLY, ELEC],
                  'pieces': [('graisse', 1)], 'remede': remede, 'consignes': CONSIGNE_STANDARD, 'ouvert': None}
        designation = equipement['designation'].lower()
        tirage = rng.random()
        if tirage < 0.2:            # compteur horaire : une visite toutes les N heures de marche
            cle = 'h%d' % numero
            ctx.definitions_compteurs.append({
                'cle': cle, 'repere': equipement['repere'], 'libelle': 'Compteur horaire', 'unite': 'h',
                'depart': rng.randint(2000, 30000),
                'par_jour': round((equipement['heures'] or 8) * 5 / 7.0 * rng.uniform(0.8, 1.1), 2)})
            unites = rng.choice([250, 500, 1000])
            ecart = 'echue' if rng.random() < 0.15 else round(rng.uniform(0.1, 0.85), 2)
            gammes.append(dict(commun, libelle='Entretien toutes les %d heures de %s' % (unites, designation),
                               declencheur='compteur', compteur=cle, unites=unites, avance=5, ecart=ecart))
        elif tirage < 0.3:          # seuil : température de palier mesurée chaque mois
            cle = 'm%d' % numero
            ctx.definitions_compteurs.append({
                'cle': cle, 'repere': equipement['repere'], 'libelle': 'Température du palier principal',
                'unite': '°C', 'mesure': True, 'depart': round(rng.uniform(45, 70), 1),
                'par_jour': round(rng.uniform(0.05, 0.12), 3), 'seuil': 75, 'apres': 42, 'decimales': 1})
            gammes.append(dict(commun, libelle='Graissage et contrôle du palier de %s (température)' % designation,
                               declencheur='seuil', compteur=cle, avance=0))
        else:                       # date : période de 30 à 180 jours
            periode = rng.choice([30, 30, 60, 90, 180])
            avance = rng.choice([3, 5, 7])
            if rng.random() < 0.15:     # gamme échue : un OT préventif est ouvert
                derniere = ctx.ref - timedelta(days=periode - avance + rng.randint(0, 10))
                ouvert = rng.choice(['Créé', 'Créé', 'Préparé', 'Planifié'])
            else:
                derniere = ctx.ref - timedelta(days=rng.randint(3, max(3, periode - avance - 3)))
                ouvert = None
            gammes.append(dict(commun, libelle='Contrôle périodique de %s' % designation, declencheur='date',
                               periode=periode, avance=avance, derniere=texte_date(jour_ouvre_avant(derniere)),
                               ouvert=ouvert))
    return gammes


def choisir_derniere_realisation_compteur(compteur, unites, ecart):
    """Relevé (date, valeur) de la dernière réalisation d'une gamme au compteur.

    ecart = 'echue' : la gamme vient de dépasser son échéance ; sinon c'est la fraction des unités
    déjà consommée depuis la dernière réalisation (la gamme n'est pas échue).
    """
    releves = compteur['releves']
    courant = releves[-1][1]
    cible = unites + 10 if ecart == 'echue' else ecart * unites
    for jour, valeur in reversed(releves):
        if courant - valeur >= cible:
            return jour, valeur
    return releves[0]


def creer_ligne_gamme(ctx, gamme, equipement, specification):
    """Ligne de gammes.csv selon le déclencheur (date, compteur ou seuil)."""
    communs = dict(equipement_id=equipement['id'], libelle=specification['libelle'],
                   declencheur=gamme['declencheur'], avance_jours=specification['avance'],
                   temps_prevu_h=specification['temps'], consignes=specification['consignes'])
    if gamme['declencheur'] == 'seuil':
        return creer_ligne(
            ctx, 'gammes', compteur_id=gamme['compteur']['id'], seuil=gamme['seuil'],
            derniere_realisation=texte_date(gamme['derniere']) if gamme['derniere'] else '',
            releve_derniere_realisation=gamme['releve'] if gamme['releve'] is not None else '', **communs)
    if gamme['declencheur'] == 'compteur':
        return creer_ligne(
            ctx, 'gammes', compteur_id=gamme['compteur']['id'], periodicite_unites=specification['unites'],
            derniere_realisation=texte_date(gamme['derniere']), releve_derniere_realisation=gamme['releve'],
            prochaine_echeance=texte_date(gamme['prochaine']), **communs)
    return creer_ligne(
        ctx, 'gammes', periodicite_jours=specification['periode'], derniere_realisation=texte_date(gamme['derniere']),
        prochaine_echeance=texte_date(gamme['prochaine']), **communs)


def generer_gammes(ctx):
    """Crée les gammes (lignes + opérations) et prépare leurs métadonnées de planification."""
    for specification in ctx.specifications_gammes:
        equipement = ctx.equipement[specification['repere']]
        compteur = ctx.compteurs.get(specification.get('compteur'))
        declencheur = specification.get('declencheur') or ('compteur' if compteur else 'date')
        gamme = dict(specification, eq=equipement, occurrences=[], ouvert=specification.get('ouvert'),
                     declencheur=declencheur, compteur=compteur, seuil=None)
        if declencheur == 'seuil':
            # Dernière réalisation = dernière intervention faite après un relevé au-dessus du seuil.
            faites = [d for d in compteur['declenchements'] if d[2] is not None]
            _jour, releve, derniere = faites[-1] if faites else (None, None, None)
            gamme.update(derniere=derniere, releve=releve, prochaine=None, seuil=compteur['seuil'])
        elif declencheur == 'compteur':
            derniere, releve = choisir_derniere_realisation_compteur(
                compteur, specification['unites'], specification['ecart'])
            prochaine = date_pour_valeur(compteur, releve + specification['unites'])
            gamme.update(derniere=derniere, releve=releve, prochaine=prochaine)
        else:
            derniere = jour_depuis_texte(specification['derniere'])
            gamme.update(derniere=derniere, releve=None, prochaine=derniere + timedelta(days=specification['periode']))
        ligne = creer_ligne_gamme(ctx, gamme, equipement, specification)
        gamme['ligne'] = ligne
        gamme['id'] = ligne['id']
        for ordre, (operation, attendue, _mesure) in enumerate(specification['ops'], 1):
            creer_ligne(ctx, 'gamme_operations', gamme_id=ligne['id'], ordre=ordre, operation=operation,
                        valeur_attendue=attendue)
        gamme['echue'] = est_gamme_echue(ctx, gamme)
        if ctx.volume and gamme['echue'] and not gamme['ouvert']:
            gamme['ouvert'] = 'Créé'          # une gamme échue a toujours son OT (RG5)
        if specification.get('role'):
            ctx.marquer(specification['role'], ligne)
        ctx.gammes.append(gamme)


def est_gamme_echue(ctx, gamme):
    """RG5, même règle que Preventif.etatGamme (ARCHITECTURE.md §14.3) :
    date     : échue si aujourd'hui >= échéance - avance ;
    compteur : échue si dernier relevé - relevé de la dernière réalisation >= périodicité ;
    seuil    : échue si dernier relevé >= seuil ET ce relevé est postérieur à la dernière réalisation."""
    if gamme['declencheur'] == 'seuil':
        dernier_jour, derniere_valeur = gamme['compteur']['releves'][-1]
        return derniere_valeur >= gamme['seuil'] and (gamme['derniere'] is None or dernier_jour > gamme['derniere'])
    if gamme['declencheur'] == 'compteur':
        courant = gamme['compteur']['releves'][-1][1]
        return courant - gamme['releve'] >= gamme['unites']
    return gamme['prochaine'] - timedelta(days=gamme['avance']) <= ctx.ref


# ---------------------------------------------------------------------------
# Contrôles réglementaires
# ---------------------------------------------------------------------------

def generer_controles(ctx):
    """Contrôles réglementaires. Dans le jeu de charge, ils portent sur des équipements de même famille."""
    familles_par_repere = {e['repere']: e['famille'] for e in EQUIPEMENTS_DEMO}
    for rang, (repere, catalogue_id, organisme, derniere, observations, levees) in enumerate(CONTROLES_DEMO):
        catalogue = ligne_catalogue(catalogue_id)
        nature, texte_reference, periodicite = catalogue['nature'], catalogue['reference'], catalogue['periodicite_mois']
        if repere not in ctx.equipement:
            famille = familles_par_repere[repere]
            parc = [e for e in ctx.equipements if e['famille'] == famille]
            if not parc:
                continue
            equipement = parc[rang % len(parc)]
        else:
            equipement = ctx.equipement[repere]
        derniere_date = jour_depuis_texte(derniere)
        creer_ligne(ctx, 'controles_reglementaires', equipement_id=equipement['id'],
                    nature=nature, texte_reference=texte_reference, periodicite_mois=periodicite,
                    organisme=organisme, derniere_date=derniere,
                    prochaine_date=texte_date(ajouter_mois(derniere_date, periodicite)),
                    observations=observations, observations_levees=levees,
                    source_periodicite='catalogue', nature_source=catalogue['nature_source'],
                    catalogue_id=catalogue_id, catalogue_relu_le=catalogue['relu_le'])
        ctx.controles.append({'eq': equipement, 'nature': nature, 'organisme': organisme,
                              'derniere': derniere, 'observations': observations, 'repere': repere,
                              'ligne': ctx.base['controles_reglementaires'][-1], 'ot': None,
                              'recale_lot3': repere in CONTROLES_RECALES_LOT3})


# Listes facultatives du format 4 : vides dans la démo (CONCEPTION-L1 §2.1, §2.2).
CHOIX_FACULTATIFS = {('habilitations', 'nature_source'), ('controles_reglementaires', 'nature_source'),
                     ('reserves_controle', 'gravite')}


COMMENTAIRE_LEVEE_REPRISE = 'levée avant la 2.2, date inconnue'     # texte fixe de CONCEPTION-L1 §3.2


def generer_reserves(ctx):
    """Réserves des contrôles : règle de reprise des observations (CONCEPTION-L1 §3.2, D183), appliquée au
    jeu de démo. Un contrôle sans réserve et avec des observations reçoit une réserve par ligne non vide ;
    la date du contrôle est derniere_date, la gravité, l'échéance et la date de levée restent vides."""
    avec_reserve = {r['controle_id'].strip() for r in ctx.base['reserves_controle']}
    for controle in ctx.base['controles_reglementaires']:
        identifiant = controle['id'].strip()
        if not identifiant or identifiant in avec_reserve or not controle['observations'].strip():
            continue
        levee = controle['observations_levees'] == '1'
        for morceau in re.split(r'\r\n|\r|\n', controle['observations']):
            texte = morceau.strip()
            if texte:
                creer_ligne(ctx, 'reserves_controle', controle_id=identifiant,
                            date_controle=controle['derniere_date'], texte=texte, levee='1' if levee else '0',
                            commentaire_levee=COMMENTAIRE_LEVEE_REPRISE if levee else '')


def generer_reserves_ae01(ctx):
    """Réserves d'AE-01 (T417), après l'attribution des identifiants : la levée est liée à l'OT réglementaire du
    contrôle (clôturé), l'ouverte a une échéance saisie à venir."""
    controle = next(c for c in ctx.controles if c['repere'] == 'AE-01')
    if controle['ot'] is None:
        return
    for reserve in RESERVES_AE01:
        creer_ligne(ctx, 'reserves_controle', controle_id=controle['ligne']['id'], date_controle=controle['derniere'],
                    texte=reserve['texte'], levee=reserve['levee'], date_levee=reserve.get('date_levee', ''),
                    commentaire_levee=reserve.get('commentaire_levee', ''),
                    echeance_levee=reserve.get('echeance_levee', ''),
                    ot_id=controle['ot']['id'] if reserve['levee'] else '')


def generer_parametres(ctx):
    # version_schema = Schema.version (js/schema.js : 4 depuis la 2.2, 3 depuis le lot 6, §20.2) ; priorite_preventif et
    # horizon_calendrier_semaines sont les clés ajoutées par le lot 2 (ARCHITECTURE.md §14.1).
    for cle, valeur in [('entreprise_nom', NOM_ENTREPRISE), ('delai_p1_h', 0), ('delai_p2_h', 24),
                        ('delai_p3_h', 168), ('delai_p4', 'prochain arrêt'), ('heures_fonct_defaut', 8),
                        ('tolerance_preventif_pct', 10), ('rafraichissement_s', 20),
                        ('priorite_preventif', 'P3'), ('horizon_calendrier_semaines', 12),
                        ('version_schema', 4)]:
        creer_ligne(ctx, 'parametres', cle=cle, valeur=valeur)


# =============================================================================
# 5. HISTORIQUE : DEMANDES, ORDRES DE TRAVAIL, PRÉVENTIF
# =============================================================================

CR_PAUVRES = ['RAS, rien à signaler', 'Fait, RAS.', 'Rien à signaler.', 'Contrôle fait, RAS',
              'Tout est conforme, RAS', 'RAS - gamme faite']
CR_PREVENTIF_FIN = ['Aucune anomalie constatée.', "Aucune anomalie, l'équipement est en bon état.",
                    'Usure normale, à surveiller au prochain passage.', 'Petit nettoyage complémentaire effectué.',
                    "Rien d'anormal ; équipement remis en service."]
MOTIFS_DIFFEREE = ["Différée : à traiter lors du prochain arrêt programmé, sans impact sur la production.",
                   "Différée : pièce à commander, intervention reportée à la semaine prochaine."]
MOTIFS_REFUSEE = ['Refusée : hors périmètre de la maintenance, à adresser au service méthodes.',
                  'Refusée : demande déjà traitée par une autre intervention.']


def texte_dh(moment):
    return texte_date_heure(moment)


def jours_avant_reference(ctx, nombre):
    """Jour ouvré le plus proche, `nombre` jours avant la date de référence (ou avant)."""
    return jour_ouvre_avant(ctx.ref - timedelta(days=nombre))


def trouver_scenario(famille, cause, symptome=None):
    for scenario_ in SCENARIOS[famille]:
        if scenario_['cause'] == cause and (symptome is None or scenario_['symptome'] == symptome):
            return scenario_
    raise KeyError('Scénario introuvable : %s %s %s' % (famille, cause, symptome))


def choisir_scenario(ctx, famille):
    if ctx.rng.random() < 0.03:
        return SCENARIOS['divers'][0]
    scenarios = SCENARIOS[famille]
    return ctx.rng.choices(scenarios, weights=[s['poids'] for s in scenarios])[0]


def choisir_impact(ctx, scenario_):
    impacts, poids = zip(*scenario_['impacts'])
    return ctx.rng.choices(impacts, weights=poids)[0]


def tirer_pieces(ctx, scenario_, equipement):
    """Pièces consommées par une intervention : liste de (clé d'article, quantité).

    Seules les pièces rattachées à l'équipement dans article_equipement sont proposées.
    """
    pieces = []
    for cle, minimum, maximum, probabilite in scenario_['pieces']:
        if ctx.rng.random() < probabilite:
            quantite = ctx.rng.randint(minimum, maximum)
            if (PIECES_SPECIFIQUES.get((equipement['repere'], cle), cle), equipement['repere']) in ctx.liens:
                pieces.append((cle, quantite))
    return pieces


def consignes_ot(equipement):
    """Consignes recopiées sur l'OT : consignation et habilitation de l'équipement."""
    consignes = []
    if equipement['energies']:
        consignes.append("Consignation obligatoire avant intervention : appliquer la procédure de la fiche équipement.")
    if equipement['hab']:
        consignes.append('Habilitation requise : %s.' % equipement['hab'])
    return ' '.join(consignes)


def nom_complet(technicien):
    return '%s %s' % (technicien['prenom'], technicien['nom'])


def ajouter_pieces_ot(ctx, ot, equipement, pieces, sortie_a=None, technicien=None):
    """Pièces prévues d'un OT (ot_pieces) et, si l'intervention a eu lieu, sorties de stock imputées."""
    for cle, quantite in pieces:
        cle = PIECES_SPECIFIQUES.get((equipement['repere'], cle), cle)
        article = ctx.articles[cle]
        creer_ligne(ctx, 'ot_pieces', ot_id=ot, article_id=article['id'], quantite_prevue=quantite)
        ctx.liens.setdefault((cle, equipement['repere']), article['qte_eq'])
        if sortie_a is None:
            continue
        utilisateur = nom_complet(technicien) if technicien else 'Magasin'
        ctx.sorties.append({'article': article, 'quand': sortie_a, 'quantite': quantite, 'ot': ot,
                            'utilisateur': utilisateur, 'repere': equipement['repere']})
        if quantite >= 2 and ctx.rng.random() < 0.06:     # une pièce rendue au magasin
            ctx.retours.append({'article': article, 'quand': sortie_a + timedelta(minutes=90), 'quantite': 1,
                                'ot': ot, 'utilisateur': utilisateur, 'repere': equipement['repere']})


def enregistrer_temps(ctx, ot, equipe, debut, heures):
    """Crée les temps passés (ot_temps) de l'équipe et retourne la date-heure de fin.

    equipe : liste de (technicien, part) ; part = proportion des heures faites par ce technicien.
    """
    fin, jours = repartir_heures(debut, heures)
    for technicien, part in equipe:
        total = 0
        for jour, heures_du_jour in jours:
            if heures_du_jour * part >= 0.12:
                heures_technicien = quart_heure(heures_du_jour * part)
                creer_ligne(ctx, 'ot_temps', ot_id=ot, technicien_id=technicien['id'], date=texte_date(jour),
                            heures=heures_technicien)
                total += heures_technicien
        if total == 0:
            creer_ligne(ctx, 'ot_temps', ot_id=ot, technicien_id=technicien['id'],
                        date=texte_date(jours[0][0]), heures=0.25)
    return fin


def cloturer_ot(ctx, ot, fin, symptome, cause, remede, compte_rendu, cout_soustraitance=0):
    """Clôture technique (RG4 respectée) puis, le plus souvent, clôture administrative."""
    rng = ctx.rng
    cloture_technique = apres_minutes_ouvrees(fin, rng.randint(5, 90))
    age = (ctx.ref - fin.date()).days
    seulement_technique = age <= 7 or (age <= 21 and rng.random() < 0.4) or rng.random() < 0.03
    valeurs = dict(date_fin=texte_dh(fin), remise_service=1, cause_code=cause, remede_code=remede,
                   compte_rendu=compte_rendu, date_cloture_tech=texte_dh(cloture_technique),
                   statut='Clôturé techniquement' if seulement_technique else 'Clôturé administrativement')
    if symptome:
        valeurs['symptome_code'] = symptome
    if cout_soustraitance:
        valeurs['cout_soustraitance'] = cout_soustraitance
    if not seulement_technique:
        jour_admin = jour_ouvre_apres(cloture_technique.date() + timedelta(days=rng.randint(1, max(1, min(7, age - 1)))))
        jour_admin = min(jour_admin, jour_ouvre_avant(ctx.fin_historique))
        valeurs['date_cloture_admin'] = texte_dh(instant(jour_admin, 8.5 + rng.randint(0, 8) / 4.0))
    renseigner(ot, **valeurs)


def compte_rendu_correctif(ctx, scenario_, equipement):
    texte = ctx.rng.choice(scenario_['cr']).format(rep=equipement['repere'])
    return texte + ctx.rng.choice(FINS_COMPTE_RENDU)


def heures_ouvrees_entre(debut, fin):
    """Heures ouvrées écoulées entre deux instants (7 h 30 - 16 h 30, lundi au vendredi)."""
    total = 0.0
    jour = debut.date()
    while jour <= fin.date():
        if jour.weekday() < 5:
            heure_debut = heure_decimale(debut) if jour == debut.date() else DEBUT_JOURNEE
            heure_fin = heure_decimale(fin) if jour == fin.date() else FIN_JOURNEE
            total += max(0.0, min(heure_fin, FIN_JOURNEE) - max(heure_debut, DEBUT_JOURNEE))
        jour += timedelta(days=1)
    return total


# ---------------------------------------------------------------------------
# Correctif : une demande (DI), son OT et le déroulé
# ---------------------------------------------------------------------------

def creer_correctif(ctx, equipement, scenario_, quand, impact, etat='clos', **options):
    """Crée une DI et, si elle est acceptée, son OT correctif. Retourne (demande, ordre de travail).

    etat : 'clos' (OT clôturé), 'Nouvelle' / 'Différée' / 'Refusée' (DI sans OT) ou le statut d'un
    OT ouvert ('Créé', 'Préparé', 'Planifié', 'En cours', 'En attente').
    Options : texte_di, demandeur, description, delai_decision, motif, date_prevue, temps_prevu, debut,
    technicien, pieces, motif_attente, heures, compte_rendu, ot_lie, urgence (OT sans DI),
    regroupees (liste de (quand, texte, demandeur) : DI regroupées sur cet OT),
    symptome_code (code choisi par le demandeur ; sinon tiré : celui du scénario, ou vide une fois sur 5),
    ot_origine (OT préventif pendant lequel l'anomalie a été vue : DI liée, ARCHITECTURE.md §14.6).
    """
    rng = ctx.rng
    texte_di = options.get('texte_di') or rng.choice(scenario_['di']).format(rep=equipement['repere'])
    if options.get('ot_lie') is not None:
        texte_di = 'Le problème est revenu après la dernière intervention. ' + texte_di
    urgence = options.get('urgence', False)
    demande = None
    if not urgence:
        demande = creer_ligne(
            ctx, 'demandes', date_heure=texte_dh(quand), demandeur=options.get('demandeur') or rng.choice(DEMANDEURS),
            equipement_id=equipement['id'], symptome=texte_di, impact=impact,
            description=options['description'] if 'description' in options else rng.choice(DESCRIPTIONS_DI),
            statut='Nouvelle', symptome_code=code_symptome_di(ctx, scenario_, options),
            ot_origine_id=options.get('ot_origine') or '')
        if etat == 'Nouvelle':
            return demande, None
    decision = apres_minutes_ouvrees(quand, options.get('delai_decision', rng.randint(15, 150)))
    if etat in ('Différée', 'Refusée'):
        motif = options.get('motif') or rng.choice(MOTIFS_DIFFEREE if etat == 'Différée' else MOTIFS_REFUSEE)
        renseigner(demande, statut=etat, motif_decision=motif, date_decision=texte_dh(decision))
        return demande, None

    priorite = priorite_calculee(equipement['crit'], impact)
    immediat = priorite == 'P1' or impact in ('arrêt', 'sécurité') or urgence
    date_prevue = options.get('date_prevue') or date_prevue_par_defaut(decision.date(), priorite)
    ot = creer_ligne(
        ctx, 'ordres_travail', origine='urgence' if urgence else 'DI', di_id=demande if demande else '',
        equipement_id=equipement['id'], type='correctif immédiat' if immediat else 'correctif différé',
        priorite=priorite, statut='Créé' if etat == 'clos' else etat,
        titre='%s — %s' % (equipement['repere'], scenario_['titre']), travail_a_faire=scenario_['travail'],
        consignes=consignes_ot(equipement), date_creation=texte_dh(decision), date_prevue=texte_date(date_prevue),
        temps_prevu_h=options.get('temps_prevu') or quart_heure(sum(scenario_['duree']) / 2.0),
        symptome_code=scenario_['symptome'], ot_lie_id=options.get('ot_lie') or '')
    if demande is not None:
        renseigner(demande, statut='Acceptée', date_decision=texte_dh(decision), ot_id=ot)
    for quand_regroupee, texte, demandeur in options.get('regroupees', []):
        ajouter_demande_regroupee(ctx, equipement, ot, quand_regroupee, texte, demandeur, impact, scenario_)

    if etat == 'clos':
        derouler_correctif(ctx, equipement, scenario_, ot, decision, immediat, date_prevue, impact, options)
    else:
        preparer_ot_ouvert(ctx, equipement, scenario_, ot, etat, decision, date_prevue, impact, options)
    return demande, ot


def code_symptome_di(ctx, scenario_, options):
    """Code symptôme d'une DI (ARCHITECTURE.md §14.6) : celui que le demandeur a choisi dans les
    suggestions. Il est COHÉRENT avec l'OT : c'est le symptôme du scénario, que l'OT reprend.
    Environ une DI sur cinq n'en a pas (texte libre, sans choisir de suggestion)."""
    if 'symptome_code' in options:
        return options['symptome_code']
    if scenario_ is None or ctx.rng.random() >= PART_DI_AVEC_CODE:
        return ''
    return scenario_['symptome']


def ajouter_demande_regroupee(ctx, equipement, ot, quand, texte, demandeur, impact, scenario_):
    """Une seconde DI sur le même équipement, rattachée à l'OT déjà ouvert (RG1 : Regroupée)."""
    return creer_ligne(
        ctx, 'demandes', date_heure=texte_dh(quand), demandeur=demandeur, equipement_id=equipement['id'],
        symptome=texte, impact=impact, description='Même problème que la demande précédente.',
        statut='Regroupée', motif_decision="Regroupée avec l'OT déjà ouvert pour cet équipement.",
        date_decision=texte_dh(apres_minutes_ouvrees(quand, 20)), ot_id=ot,
        symptome_code=code_symptome_di(ctx, scenario_, {}))


def derouler_correctif(ctx, equipement, scenario_, ot, decision, immediat, date_prevue, impact, options):
    """Intervention terminée : temps passés, pièces, arrêt de production, clôture."""
    rng = ctx.rng
    if immediat:
        debut = apres_minutes_ouvrees(decision, rng.randint(10, 75))
    else:
        jour_debut = max(jour_ouvre_apres(date_prevue - timedelta(days=rng.choice([0, 0, 1, 1, 2]))), decision.date())
        # Une intervention terminée ne peut pas être dans le futur : on la ramène avant la date de référence.
        jour_debut = min(jour_debut, max(decision.date(), jour_ouvre_avant(ctx.ref - timedelta(days=3))))
        debut = max(heure_aleatoire(rng, jour_debut, 7.75, 13.0), apres_minutes_ouvrees(decision, 60))
    heures = options.get('heures') or quart_heure(rng.uniform(*scenario_['duree']))
    principal = choisir_technicien(ctx, scenario_['metiers'], equipement, debut.date())
    equipe = [(principal, 1.0)]
    if heures >= 2 and rng.random() < 0.25:
        equipe.append((choisir_technicien(ctx, scenario_['metiers'], equipement, debut.date(), exclure=principal),
                       rng.choice([0.5, 0.75, 1.0])))
    pieces = options['pieces'] if 'pieces' in options else tirer_pieces(ctx, scenario_, equipement)
    ajouter_pieces_ot(ctx, ot, equipement, pieces, apres_minutes_ouvrees(debut, rng.randint(10, 40)), principal)
    renseigner(ot, technicien_id=principal['id'], date_debut=texte_dh(debut))
    if rng.random() < {'arrêt': 0.95, 'sécurité': 0.5, 'dégradé': 0.2, 'gêne': 0.0}[impact]:
        attente = min(1.5, (debut - decision).total_seconds() / 3600.0) if immediat else 0.0
        renseigner(ot, arret_production=1, duree_arret_h=quart_heure(heures + attente))
    fin = enregistrer_temps(ctx, ot, equipe, debut, heures)
    cout = rng.randrange(scenario_['soustraitance'][0], scenario_['soustraitance'][1] + 1, 50) \
        if scenario_['soustraitance'] else 0
    compte_rendu = options.get('compte_rendu') or compte_rendu_correctif(ctx, scenario_, equipement)
    cloturer_ot(ctx, ot, fin, scenario_['symptome'], scenario_['cause'], scenario_['remede'], compte_rendu, cout)
    if not immediat and debut > decision + timedelta(hours=6) and rng.random() < 0.10:
        # Une seconde demande arrive avant le début des travaux : elle est regroupée sur l'OT.
        jours_possibles = jours_ouvres_entre(decision.date(), debut.date())
        quand = heure_aleatoire(rng, rng.choice(jours_possibles), 7.0, 15.5)
        if not decision + timedelta(minutes=30) < quand < debut - timedelta(minutes=30):
            quand = apres_minutes_ouvrees(decision, 45)
        ajouter_demande_regroupee(ctx, equipement, ot, quand, rng.choice(scenario_['di']).format(rep=equipement['repere']),
                                  rng.choice(DEMANDEURS), 'gêne', scenario_)


def preparer_ot_ouvert(ctx, equipement, scenario_, ot, etat, decision, date_prevue, impact, options):
    """OT encore ouvert à la date de référence : renseigne ce qui correspond à son statut."""
    rng = ctx.rng
    if 'pieces' in options:
        pieces = options['pieces']
    elif ctx.volume and etat in ('Préparé', 'En attente'):
        pieces = tirer_pieces(ctx, scenario_, equipement)
    else:
        pieces = []
    technicien = None
    if etat in ('Planifié', 'En cours', 'En attente'):
        technicien = options.get('technicien') or choisir_technicien(ctx, scenario_['metiers'], equipement, date_prevue)
        renseigner(ot, technicien_id=technicien['id'])
    if etat != 'Créé':
        ajouter_pieces_ot(ctx, ot, equipement, pieces)
    if etat == 'En attente':
        renseigner(ot, motif_attente=options.get('motif_attente') or (
            'Pièce : en attente de livraison.' if pieces else "Attente d'un arrêt de la machine (production en cours)."))
    if etat in ('En cours', 'En attente') and (etat == 'En cours' or 'debut' in options):
        debut = options.get('debut') or apres_minutes_ouvrees(decision, rng.randint(20, 90))
        debut = min(debut, ctx.maintenant - timedelta(minutes=30))
        renseigner(ot, date_debut=texte_dh(debut))
        if etat == 'En cours':
            heures = options.get('heures_passees') or quart_heure(max(0.25, heures_ouvrees_entre(debut, ctx.maintenant) - 0.25))
        else:
            heures = options.get('heures_passees') or 1.0
        enregistrer_temps(ctx, ot, [(technicien, 1.0)], debut, heures)
        if impact == 'arrêt' and etat == 'En cours':
            renseigner(ot, arret_production=1)


def etat_selon_age(ctx, jour):
    """Jeu de charge : une demande récente peut être encore ouverte, une ancienne est toujours clôturée."""
    age = (ctx.ref - jour).days
    if age >= 12:
        return 'clos'
    etats = ['Nouvelle', 'Différée', 'Refusée', 'Créé', 'Préparé', 'Planifié', 'En cours', 'En attente']
    poids = [3, 1, 1, 2, 3, 3, 4, 2]
    if age >= 4:
        etats.append('clos')
        poids.append(4)
    return ctx.rng.choices(etats, weights=poids)[0]


# ---------------------------------------------------------------------------
# OT ponctuels : amélioration, contrôle réglementaire
# ---------------------------------------------------------------------------

def creer_ot_manuel(ctx, equipement, titre, travail, jour, heures, metiers, compte_rendu, type_ot,
                    cause, remede, cout_soustraitance=0, priorite='P3'):
    """OT créé à la main (origine « manuel »), réalisé puis clôturé."""
    rng = ctx.rng
    jour = jour_ouvre_apres(jour)
    debut = heure_aleatoire(rng, jour, 7.75, 9.5)
    technicien = choisir_technicien(ctx, metiers, equipement, jour)
    ot = creer_ligne(
        ctx, 'ordres_travail', origine='manuel', equipement_id=equipement['id'], type=type_ot,
        priorite=priorite, statut='Créé', titre=titre, travail_a_faire=travail, consignes=consignes_ot(equipement),
        date_creation=texte_dh(instant(jour_ouvre_avant(jour - timedelta(days=3)), 8.0)),
        date_prevue=texte_date(jour), technicien_id=technicien['id'], temps_prevu_h=heures,
        date_debut=texte_dh(debut))
    fin = enregistrer_temps(ctx, ot, [(technicien, 1.0)], debut, heures)
    cloturer_ot(ctx, ot, fin, None, cause, remede, compte_rendu, cout_soustraitance)
    return ot


def generer_ot_reglementaires_et_ameliorations(ctx):
    for controle in ctx.controles:
        jour = jour_depuis_texte(controle['derniere'])
        if ctx.debut <= jour <= ctx.fin_historique:
            observation = (" Observation de l'organisme à lever : " + controle['observations']
                           if controle['observations'] else ' Aucune observation.')
            if controle['repere'] == 'AE-01':
                observation = " Réserves relevées par l'organisme : %s" % ' '.join(r['texte'] for r in RESERVES_AE01)
            # Contrôle recalé au lot 3 : son OT tire son hasard à part (le reste du jeu ne bouge pas).
            with hasard_du_lot3(ctx) if controle['recale_lot3'] else nullcontext():
                controle['ot'] = creer_ot_manuel(
                    ctx, controle['eq'], controle['nature'], 'Accompagner l\'organisme de contrôle et récupérer le rapport.',
                    jour, 1.0, [POLY, MECA], 'Contrôle réalisé par %s, rapport reçu.%s' % (controle['organisme'], observation),
                    'réglementaire', 'C99', 'R10', cout_soustraitance=ctx.rng.randrange(250, 650, 50))
    if ctx.volume:
        return
    for amelioration in AMELIORATIONS_DEMO:
        jour = jours_avant_reference(ctx, amelioration['jours'])
        if jour >= ctx.debut:
            creer_ot_manuel(ctx, ctx.equipement[amelioration['repere']], amelioration['titre'], amelioration['travail'],
                            jour, amelioration['heures'], amelioration['metiers'], amelioration['compte_rendu'],
                            'amélioration', 'C99', 'R09', priorite='P4')


# ---------------------------------------------------------------------------
# Préventif : un OT par échéance de gamme, avec ses opérations copiées
# ---------------------------------------------------------------------------

def mesure_simulee(rng, mesure):
    """Valeur « mesurée » plausible pour une opération de gamme."""
    if mesure is None:
        return ''
    if mesure == 'ok':
        return rng.choice(['OK', 'OK', 'Conforme'])
    minimum, maximum, decimales, unite, _libelle = mesure
    valeur = rng.uniform(minimum, maximum)
    return ('%.*f' % (decimales, valeur)) + unite


def compte_rendu_preventif(ctx, gamme, mesures):
    rng = ctx.rng
    if gamme.get('toujours_ras') or rng.random() < 0.12:
        return rng.choice(CR_PAUVRES)
    morceaux = ['Gamme réalisée en totalité.']
    if mesures:
        morceaux.append('Relevés : ' + ', '.join('%s %s' % (libelle, valeur) for libelle, valeur in mesures[:3]) + '.')
    morceaux.append(rng.choice(CR_PREVENTIF_FIN))
    return ' '.join(morceaux)


def occurrences_par_date(ctx, gamme):
    """Échéances passées d'une gamme à date : on remonte depuis la dernière réalisation, période par période."""
    rng = ctx.rng
    occurrences = []
    realisee = gamme['derniere']
    while realisee >= ctx.debut:
        retard = 0 if gamme.get('sans_decalage') else rng.choice([0, 0, 1, 1, 2, 3])
        echeance = realisee - timedelta(days=retard)
        occurrences.append({'creation': min(jour_ouvre_apres(echeance - timedelta(days=gamme['avance'])), realisee),
                            'prevue': jour_ouvre_avant(echeance), 'exec': realisee, 'releve': None})
        realisee = jour_ouvre_apres(echeance - timedelta(days=gamme['periode']))
    occurrences.reverse()
    return occurrences


def occurrences_par_compteur(ctx, gamme):
    """Échéances passées d'une gamme au compteur : une tous les `unites`, dates déduites des relevés."""
    rng = ctx.rng
    compteur = gamme['compteur']
    premier = compteur['releves'][0][1]
    occurrences = []
    if gamme['derniere'] >= ctx.debut:
        creation = jour_ouvre_apres(gamme['derniere'] - timedelta(days=rng.randint(3, 6)))
        occurrences.append({'creation': creation, 'prevue': jour_ouvre_apres(creation + timedelta(days=8)),
                            'exec': gamme['derniere'], 'releve': gamme['releve']})
    rang = 1
    while gamme['releve'] - rang * gamme['unites'] >= premier:
        valeur = gamme['releve'] - rang * gamme['unites']
        atteinte = date_pour_valeur(compteur, valeur)
        creation = jour_ouvre_apres(atteinte + timedelta(days=1))
        execution = jour_ouvre_apres(creation + timedelta(days=rng.randint(2, 6)))
        if execution >= ctx.debut:
            occurrences.append({'creation': creation, 'prevue': jour_ouvre_apres(creation + timedelta(days=8)),
                                'exec': execution, 'releve': valeur})
        rang += 1
    occurrences.sort(key=lambda occurrence: occurrence['exec'])
    return occurrences


def occurrences_par_seuil(ctx, gamme):
    """Interventions passées d'une gamme seuil : une par relevé qui a atteint le seuil (l'OT est créé
    le jour ouvré suivant le relevé, puis réalisé à la date calculée par simuler_mesure)."""
    occurrences = []
    for jour_releve, valeur, execution in gamme['compteur']['declenchements']:
        if execution is not None and execution >= ctx.debut:
            creation = jour_ouvre_apres(jour_releve + timedelta(days=1))
            occurrences.append({'creation': creation, 'prevue': execution, 'exec': execution, 'releve': valeur})
    return occurrences


def occurrence_ouverte(ctx, gamme):
    """Échéance en cours d'une gamme échue (l'OT n'est pas terminé)."""
    if gamme['declencheur'] in ('compteur', 'seuil'):
        creation = jour_ouvre_apres(gamme['compteur']['releves'][-1][0] + timedelta(days=1))
        prevue = jour_ouvre_apres(creation + timedelta(days=10))
    else:
        creation = jour_ouvre_apres(gamme['prochaine'] - timedelta(days=gamme['avance']))
        prevue = jour_ouvre_avant(gamme['prochaine'])
    return {'creation': min(creation, ctx.ref), 'prevue': prevue, 'exec': None, 'releve': None}


def creer_preventif(ctx, gamme, occurrence, etat, anomalie=None):
    """OT préventif issu d'une gamme (RG5) : opérations copiées dans ot_operations.

    Type (ARCHITECTURE.md §14.3) : « préventif conditionnel » pour une gamme seuil, « préventif
    systématique » pour une gamme à date ou au compteur. `anomalie` : voir ANOMALIE_PR01 (§3)."""
    rng = ctx.rng
    equipement = gamme['eq']
    creation = instant(occurrence['creation'], 7.0) + timedelta(minutes=rng.randint(10, 40))
    ot = creer_ligne(
        ctx, 'ordres_travail', origine='préventif', gamme_id=gamme['id'], equipement_id=equipement['id'],
        type='préventif conditionnel' if gamme['declencheur'] == 'seuil' else 'préventif systématique',
        priorite='P4' if equipement['crit'] == 'C' else 'P3', statut='Créé' if etat == 'clos' else etat,
        titre=gamme['libelle'], travail_a_faire='Réaliser les %d opérations de la gamme.' % len(gamme['ops']),
        consignes=gamme['consignes'], date_creation=texte_dh(creation), date_prevue=texte_date(occurrence['prevue']),
        temps_prevu_h=gamme['temps'])
    fait = etat == 'clos'
    mesures = []
    for ordre, (operation, attendue, mesure) in enumerate(gamme['ops'], 1):
        valeur = mesure_simulee(rng, mesure) if fait else ''
        creer_ligne(ctx, 'ot_operations', ot_id=ot, ordre=ordre, operation=operation, valeur_attendue=attendue,
                    fait=1 if fait else 0, valeur_mesuree=valeur)
        if fait and isinstance(mesure, tuple):
            mesures.append((mesure[4], valeur))
    if fait:
        jour = occurrence['exec']
        technicien = choisir_technicien(ctx, gamme['metiers'], equipement, jour)
        debut = heure_aleatoire(rng, jour, 7.75, 10.5)
        ajouter_pieces_ot(ctx, ot, equipement, gamme['pieces'], apres_minutes_ouvrees(debut, 20), technicien)
        renseigner(ot, technicien_id=technicien['id'], date_debut=texte_dh(debut))
        fin = enregistrer_temps(ctx, ot, [(technicien, 1.0)], debut, quart_heure(gamme['temps'] * rng.uniform(0.8, 1.3)))
        compte_rendu = compte_rendu_preventif(ctx, gamme, mesures)
        if anomalie:
            compte_rendu = 'Gamme réalisée en totalité. ' + anomalie['constat']
        cloturer_ot(ctx, ot, fin, None, 'C99', gamme['remede'], compte_rendu)
        if anomalie:
            signaler_anomalie(ctx, gamme, ot, technicien, debut, anomalie)
        return ot
    if etat != 'Créé':
        ajouter_pieces_ot(ctx, ot, equipement, gamme['pieces'])
    if etat == 'Planifié':
        numero = gamme.get('tech_ouvert')
        technicien = (ctx.techniciens[numero - 1] if numero else
                      choisir_technicien(ctx, gamme['metiers'], equipement, occurrence['prevue']))
        renseigner(ot, technicien_id=technicien['id'])
    return ot


def signaler_anomalie(ctx, gamme, ot, technicien, debut, anomalie):
    """Anomalie vue pendant un préventif (RG5, ARCHITECTURE.md §14.6) : case « anomalie constatée »
    cochée sur l'OT et DI liée (ot_origine_id) créée par le technicien pendant l'intervention."""
    renseigner(ot, anomalie_constatee=1)
    quand = debut + timedelta(minutes=50)
    options = dict(texte_di=anomalie['texte'], demandeur=nom_complet(technicien), symptome_code=anomalie['symptome'],
                   description="Signalée pendant l'OT préventif de la gamme « %s »." % gamme['libelle'],
                   ot_origine=ot)
    if anomalie['suite'] == 'acceptee':
        scenario_ = trouver_scenario(anomalie['famille'], anomalie['cause'], anomalie['symptome'])
        demande, correctif = creer_correctif(ctx, gamme['eq'], scenario_, quand, anomalie['impact'], 'clos', **options)
        lignes = (ot, demande, correctif)
    else:
        demande, _ = creer_correctif(ctx, gamme['eq'], None, quand, anomalie['impact'], 'Nouvelle', **options)
        lignes = (ot, demande)
    for role, ligne in zip(anomalie['roles'], lignes):
        ctx.marquer(role, ligne)


def generer_preventifs(ctx):
    """OT préventifs de l'historique (clôturés) et OT ouverts des gammes échues."""
    for gamme in ctx.gammes:
        if gamme['declencheur'] == 'seuil':
            gamme['occurrences'] = occurrences_par_seuil(ctx, gamme)
        elif gamme['declencheur'] == 'compteur':
            gamme['occurrences'] = occurrences_par_compteur(ctx, gamme)
        else:
            gamme['occurrences'] = occurrences_par_date(ctx, gamme)
        anomalies = gamme.get('anomalies', {})
        nombre = len(gamme['occurrences'])
        for rang, occurrence in enumerate(gamme['occurrences']):
            creer_preventif(ctx, gamme, occurrence, 'clos', anomalies.get(nombre - rang))
        if gamme['echue'] and gamme['ouvert'] and not gamme.get('sans_ot'):
            ot = creer_preventif(ctx, gamme, occurrence_ouverte(ctx, gamme), gamme['ouvert'])
            if gamme.get('role_ot'):
                ctx.marquer(gamme['role_ot'], ot)


# ---------------------------------------------------------------------------
# Pannes « de fond » (tirées au hasard) et jeu de charge
# ---------------------------------------------------------------------------

def jours_ouvres_entre(premier, dernier):
    jours = []
    jour = premier
    while jour <= dernier:
        if jour.weekday() < 5:
            jours.append(jour)
        jour += timedelta(days=1)
    return jours


def generer_pannes_de_fond(ctx, nombre=None, cible_ot=None):
    """Tire des pannes au hasard sur les équipements, pondérées par leur taux.

    Démo : `nombre` pannes, toutes clôturées (les OT ouverts sont écrits à la main, §5 plus bas).
    Charge : on s'arrête quand le nombre d'OT atteint `cible_ot` ; les demandes récentes peuvent être
    encore ouvertes.
    """
    rng = ctx.rng
    candidats = [e for e in ctx.equipements if e['taux'] > 0 and e['statut'] == 'en service'
                 and e['famille'] in SCENARIOS]
    poids = [e['taux'] for e in candidats]
    dernier_jour = ctx.fin_historique if ctx.volume else ctx.ref - timedelta(days=9)
    jours = jours_ouvres_entre(ctx.debut, dernier_jour)
    nombre_ot = lambda: len(ctx.base['ordres_travail'])
    fait = 0
    while (fait < nombre) if cible_ot is None else (nombre_ot() < cible_ot):
        fait += 1
        equipement = rng.choices(candidats, weights=poids)[0]
        jour = rng.choice(jours)
        scenario_ = choisir_scenario(ctx, equipement['famille'])
        impact = choisir_impact(ctx, scenario_)
        quand = heure_aleatoire(rng, jour, 7.0, 15.5)
        etat = etat_selon_age(ctx, jour) if ctx.volume else 'clos'
        urgence = etat == 'clos' and rng.random() < (0.15 if ctx.volume else 0.10)
        if urgence:                                   # une urgence a toujours un vrai impact sur la production
            impact = rng.choice(['arrêt', 'arrêt', 'dégradé'])
        _demande, ot = creer_correctif(ctx, equipement, scenario_, quand, impact, etat, urgence=urgence)
        marge_reprise = cible_ot is None or nombre_ot() + 2 <= cible_ot
        if ot is not None and etat == 'clos' and marge_reprise and not urgence and rng.random() < 0.05:
            jour_reprise = jour_ouvre_apres(jour + timedelta(days=rng.randint(3, 10)))
            if jour_reprise <= dernier_jour - timedelta(days=12 if ctx.volume else 0):
                creer_correctif(ctx, equipement, scenario_, heure_aleatoire(rng, jour_reprise, 7.0, 15.0),
                                choisir_impact(ctx, scenario_), 'clos', ot_lie=ot)


# ---------------------------------------------------------------------------
# Scénarios de démo écrits à la main
# ---------------------------------------------------------------------------

def evenements_fixes_demo(ctx):
    """Les cas démontrables : PO-02 (fuites de garniture à 58 jours, plus deux fuites de raccord),
    CV-02 (capteur encrassé), CP-01 (échauffements), une panne unique (BA-01), une panne entre deux
    préventifs (PR-01), un arrêt intempestif sur CV-03 (même modèle que CV-02 : causes fréquentes à la
    portée « modèle ») et un bruit sur PO-03 (pas encore assez de cas)."""
    rng = ctx.rng
    equipement = ctx.equipement
    # PO-02 : fuite de garniture tous les 58 jours environ, depuis la plus récente (il y a 19 jours).
    # Le demandeur choisit toujours la suggestion « Fuite » (code S01).
    scenario_ = trouver_scenario('pompe', 'C01', 'S01')
    dates = []
    jour = ctx.ref - timedelta(days=19)
    while jour_ouvre_avant(jour) >= ctx.debut:
        dates.append(jour_ouvre_avant(jour))
        jour -= timedelta(days=58)
    dates.reverse()
    for rang, jour in enumerate(dates, 1):
        compte_rendu = compte_rendu_correctif(ctx, scenario_, equipement['PO-02'])
        if rang > 1:
            compte_rendu += (" Cette garniture avait déjà été remplacée il y a %d jours : analyse de cause à "
                             "prévoir (alignement, vibrations, qualité de l'eau)." % (jour - dates[rang - 2]).days)
        demande, ot = creer_correctif(ctx, equipement['PO-02'], scenario_, heure_aleatoire(rng, jour, 7.0, 14.0),
                                      'dégradé', 'clos', compte_rendu=compte_rendu, pieces=[('kit_gar_u', 1)],
                                      heures=quart_heure(rng.uniform(2.5, 4.0)), symptome_code='S01')
    if dates:
        ctx.marquer('ot_fuite_garniture_po02', ot)
        ctx.marquer('di_causes_equipement', demande)
    # PO-02 : deux fuites d'une autre cause (bride de refoulement desserrée) : l'encart « causes
    # fréquentes » de PO-02 montre au moins deux causes, la garniture usée en tête.
    for decalage in (160, 330):
        jour = jours_avant_reference(ctx, decalage)
        if jour >= ctx.debut:
            creer_correctif(ctx, equipement['PO-02'], trouver_scenario('pompe', 'C06', 'S01'),
                            heure_aleatoire(rng, jour, 7.0, 14.0), 'gêne', 'clos', symptome_code='S01')
    # CV-02 : arrêts intempestifs répétés, capteur encrassé (environ un par mois).
    scenario_ = trouver_scenario('convoyeur', 'C04', 'S05')
    rang = 0
    while True:
        jour = jour_ouvre_avant(ctx.ref - timedelta(days=12 + 29 * rang + rng.randint(-2, 2)))
        if jour < ctx.debut:
            break
        pieces = [('nettoyant', 1), ('capteur_m18', 1)] if rang == 2 else [('nettoyant', 1)]
        creer_correctif(ctx, equipement['CV-02'], scenario_, heure_aleatoire(rng, jour, 7.0, 15.0),
                        'arrêt' if rang % 3 == 1 else 'dégradé', 'clos', pieces=pieces)
        rang += 1
    # CP-01 : échauffements récurrents, un tous les 35 jours : filtre colmaté (C05) ou manque de
    # lubrification (C07, une fois sur trois).
    for rang in range(1, 12):
        cause = 'C07' if rang % 3 == 2 else 'C05'
        jour = jour_ouvre_avant(ctx.ref - timedelta(days=35 * rang + rng.randint(-3, 3)))
        if jour >= ctx.debut:
            creer_correctif(ctx, equipement['CP-01'], trouver_scenario('compresseur', cause, 'S04'),
                            heure_aleatoire(rng, jour, 7.0, 14.0), 'arrêt' if rang % 2 == 1 else 'dégradé', 'clos')
    # BA-01 : une seule panne dans tout l'historique.
    jour = jours_avant_reference(ctx, 75)
    if jour >= ctx.debut:
        creer_correctif(
            ctx, equipement['BA-01'], trouver_scenario('emballage', 'C11', 'S07'), heure_aleatoire(rng, jour, 7.0, 14.0),
            'dégradé', 'clos', texte_di='La balance de contrôle rejette des colis conformes : le poids affiché dérive.',
            compte_rendu='Dérive du zéro de la balance : retarage avec la masse étalon, 20 colis conformes pesés correctement.',
            pieces=[], heures=1.0)
    # PR-01 : une panne qui survient ENTRE deux visites préventives.
    gamme_presse = [g for g in ctx.gammes if g['repere'] == 'PR-01' and g['declencheur'] == 'date']
    if gamme_presse and len(gamme_presse[0]['occurrences']) >= 2:
        avant, apres = gamme_presse[0]['occurrences'][-2]['exec'], gamme_presse[0]['occurrences'][-1]['exec']
        jour = jour_ouvre_apres(avant + (apres - avant) // 2)
        creer_correctif(ctx, equipement['PR-01'], trouver_scenario('presse', 'C10', 'S01'),
                        heure_aleatoire(rng, jour, 7.0, 13.0), 'dégradé', 'clos',
                        texte_di="Fuite d'huile sur un flexible de la presse, elle goutte sur le sol.")
    # CV-03 : un arrêt intempestif (capteur encrassé), comme sur CV-02 qui est du même modèle.
    jour = jours_avant_reference(ctx, 110)
    if jour >= ctx.debut:
        creer_correctif(ctx, equipement['CV-03'], trouver_scenario('convoyeur', 'C04', 'S05'),
                        heure_aleatoire(rng, jour, 7.0, 14.0), 'dégradé', 'clos', symptome_code='S05',
                        pieces=[('nettoyant', 1)])
    # PO-03 : un bruit de roulement, seul cas de ce symptôme (encart « pas encore assez de cas »).
    jour = jours_avant_reference(ctx, 150)
    if jour >= ctx.debut:
        creer_correctif(ctx, equipement['PO-03'], trouver_scenario('pompe', 'C02', 'S02'),
                        heure_aleatoire(rng, jour, 7.0, 14.0), 'gêne', 'clos', symptome_code='S02')


def etat_courant_demo(ctx):
    """Ce qui est ouvert à la date de référence : DI à traiter, OT dans tous les statuts, un P1, des retards."""
    equipement = ctx.equipement
    jour = ctx.ref
    hier = lambda nombre, heure: instant(jour - timedelta(days=nombre), heure)

    # --- OT ouverts (le préventif CH-01 « Créé » et CN-01 « Planifié » viennent des gammes)
    # P1 ouvert : le compresseur, en cours de dépannage ce matin.
    _demande, ot = creer_correctif(
        ctx, equipement['CP-01'], trouver_scenario('compresseur', 'C05', 'S04'), instant(jour, 7.6), 'arrêt', 'En cours',
        texte_di="Le compresseur CP-01 s'est arrêté en sécurité : alarme température haute, le carter est brûlant.",
        description='Arrêt constaté à la prise de poste.', demandeur='Paul Dubois', delai_decision=14,
        debut=instant(jour, 8.2), technicien=ctx.techniciens[1], temps_prevu=3.0, pieces=[('filtre_huile_cp', 1)],
        heures_passees=0.5, symptome_code='S04')
    ctx.marquer('ot_p1_ouvert', ot)
    renseigner(equipement['CP-01']['ligne'], statut='arrêt')
    # P2 en cours avec une seconde DI regroupée.
    _demande, ot = creer_correctif(
        ctx, equipement['EM-01'], trouver_scenario('emballage', 'C11', 'S07'), instant(jour - timedelta(days=3), 14.2),
        'dégradé', 'En cours', texte_di="Les films sont mal soudés sur la fardeleuse, des colis s'ouvrent à la sortie.",
        demandeur='Manon Duval', delai_decision=20, debut=instant(jour, 7.5), technicien=ctx.techniciens[2],
        temps_prevu=2.0, pieces=[('res_soudure', 1)], heures_passees=1.25, symptome_code='S07',
        regroupees=[(instant(jour, 7.33), "La fardeleuse EM-01 refait des films mal soudés ce matin aussi.", 'Lucas Perrot')])
    ctx.marquer('ot_statut_en_cours', ot)
    ctx.marquer('ot_en_cours_regroupe', ot)
    ctx.marquer('di_statut_regroupee', [d for d in ctx.base['demandes'] if d['ot_id'] is ot and d['statut'] == 'Regroupée'][0])
    # Planifié (pas en retard).
    _demande, ot = creer_correctif(
        ctx, equipement['CU-01'], trouver_scenario('usinage', 'C11', 'S07'), instant(jour - timedelta(days=5), 10.25),
        'gêne', 'Planifié', texte_di="Les cotes des pièces dérivent légèrement sur le centre d'usinage.",
        demandeur='Camille Girard', delai_decision=50, date_prevue=jour + timedelta(days=2),
        technicien=ctx.techniciens[2], temps_prevu=2.0, pieces=[])
    ctx.marquer('ot_statut_planifie', ot)
    # Préparé, pas en retard (priorité P4).
    creer_correctif(
        ctx, equipement['CV-03'], trouver_scenario('convoyeur', 'C03', 'S02'), instant(jour - timedelta(days=7), 8.7),
        'gêne', 'Préparé', texte_di='La courroie du convoyeur CV-03 patine, bruit de glissement au démarrage.',
        demandeur='Inès Marchand', pieces=[('cour_htd', 1)], temps_prevu=1.0)
    # Préparé et EN RETARD (priorité P4, échéance dépassée).
    _demande, ot = creer_correctif(
        ctx, equipement['VE-02'], trouver_scenario('ventilation', 'C05', 'S08'), instant(jour - timedelta(days=21), 9.1),
        'gêne', 'Préparé', texte_di="Débit d'air faible sur l'extracteur VE-02, le filtre semble très encrassé.",
        demandeur='Hugo Lefèvre', pieces=[('filtre_g4', 2)], temps_prevu=1.0)
    ctx.marquer('ot_statut_prepare', ot)
    # En attente d'une pièce, EN RETARD : le contacteur du départ est en rupture.
    _demande, ot = creer_correctif(
        ctx, equipement['AE-02'], trouver_scenario('electrique', 'C09', 'S10'), instant(jour - timedelta(days=12), 13.3),
        'dégradé', 'En attente', texte_di="Légère odeur de chaud près du départ ventilation de l'armoire AE-02.",
        demandeur='Antoine Mercier', delai_decision=45, technicien=ctx.techniciens[0], temps_prevu=2.0,
        debut=instant(jour - timedelta(days=11), 8.0), heures_passees=1.0, pieces=[('contacteur_25', 2)],
        motif_attente='Pièce : contacteur tripolaire 25 A en rupture de stock, achat demandé au fournisseur.')
    ctx.marquer('ot_statut_en_attente', ot)
    # Annulé : OT saisi en double (jamais effacé, motif obligatoire).
    sc01 = equipement['SC-01']
    creation = jour_ouvre_avant(jour - timedelta(days=30))
    ctx.marquer('ot_statut_annule', creer_ligne(
        ctx, 'ordres_travail', origine='manuel', equipement_id=sc01['id'], type='correctif différé', priorite='P3',
        statut='Annulé', titre='SC-01 — Remplacement de la lame de scie',
        travail_a_faire='Remplacer la lame de la scie à ruban et régler sa tension.', consignes=consignes_ot(sc01),
        date_creation=texte_dh(instant(creation, 9.0)), date_prevue=texte_date(jour_ouvre_apres(creation + timedelta(days=7))),
        temps_prevu_h=1.0,
        motif_annulation='Doublon : la lame a déjà été changée par le conducteur au changement de série, '
                         'aucune intervention de maintenance nécessaire.'))

    # --- DI encore à traiter (le demandeur a choisi une suggestion de symptôme), différée, refusée
    nouvelles = [
        (equipement['AE-04'], 'sécurité', instant(jour, 7.25), 'Paul Dubois', 'S10', ('di_securite',),
         "Odeur de brûlé près de l'armoire AE-04, un peu de fumée à l'ouverture de la porte."),
        (equipement['PR-01'], 'dégradé', hier(3, 16.1), 'Sarah Colin', 'S01', ('di_nouvelle_degradee',),
         "Fuite d'huile sous la presse PR-01, une petite flaque se forme depuis ce matin."),
        (equipement['ET-01'], 'gêne', hier(3, 11.3), 'Léa Fontaine', 'S07',
         ('di_statut_nouvelle', 'di_nouvelle_sans_ot_ouvert'),
         "Les étiquettes sortent décalées de quelques millimètres sur l'étiqueteuse."),
        (equipement['PO-03'], 'gêne', instant(jour, 6.97), 'Mathieu Roux', 'S02',
         ('di_nouvelle_p4', 'di_causes_insuffisantes'),
         'La pompe de relevage est très bruyante au démarrage.'),
    ]
    for equipement_nouvelle, impact, quand, demandeur, code, roles, texte in nouvelles:
        demande, _ = creer_correctif(ctx, equipement_nouvelle, None, quand, impact, 'Nouvelle', texte_di=texte,
                                     demandeur=demandeur, description='', symptome_code=code)
        for role in roles:
            ctx.marquer(role, demande)
    demande, _ = creer_correctif(
        ctx, equipement['CV-01'], None, hier(6, 10.7), 'gêne', 'Différée', demandeur='Lucas Perrot', delai_decision=200,
        texte_di='Le garde-corps du convoyeur CV-01 est légèrement tordu, à redresser.', description='',
        motif="Différée : à traiter lors de l'arrêt programmé de fin octobre, sans impact sur la production.",
        symptome_code='')
    ctx.marquer('di_statut_differee', demande)
    ctx.marquer('di_sans_symptome_code', demande)
    demande, _ = creer_correctif(
        ctx, equipement['CU-01'], None, hier(10, 9.5), 'gêne', 'Refusée', demandeur='Hugo Lefèvre', delai_decision=120,
        texte_di='Demande de repeindre le carter du centre d\'usinage en bleu.', description='',
        motif="Refusée : demande esthétique, hors périmètre de la maintenance. À adresser au service méthodes.",
        symptome_code='')
    ctx.marquer('di_statut_refusee', demande)


# =============================================================================
# 5 bis. LOT 3 : PLANNING, OT À PLANIFIER, PANNES REMARQUABLES, JOURNAL (ARCHITECTURE.md §15.12)
# =============================================================================
# Tout ce bloc est appelé sous hasard_du_lot3 (voir construire_jeu) : ses tirages au hasard ne
# changent pas ceux des lots 1 et 2.

def ot_prevu(repere, jour, technicien, heures, titre, travail, type_ot='correctif différé', priorite='P3',
             pieces=(), cree=7):
    """Un OT « Planifié » du planning de démo (dictionnaire lisible, une ligne par appel).

    jour        jours après la date de référence (0 = lundi de la semaine 1, 7 = lundi de la semaine 2…)
    technicien  numéro du technicien (1 à 4, ordre de TECHNICIENS_DEMO)
    pieces      pièces prévues [(clé d'article, quantité)] : toutes en stock (RG3)
    cree        l'OT a été créé ce nombre de jours avant la date de référence
    """
    return {'repere': repere, 'jour': jour, 'technicien': technicien, 'heures': heures, 'titre': titre,
            'travail': travail, 'type': type_ot, 'priorite': priorite, 'pieces': list(pieces), 'cree': cree}


ARRET = ' (arrêt programmé)'

# Les 4 semaines qui commencent à la date de référence (un lundi). La semaine 2 est l'arrêt programmé
# de fin octobre (celui qu'annonce la DI différée de CV-01) : le mécanicien (n° 2) y a 38,5 h de travaux
# pour 35 h de capacité, une surcharge que le responsable doit répartir. Les OT déjà ouverts (CU-01
# « Planifié », CP-01 et EM-01 « En cours ») complètent la semaine 1. Les armoires (habilitation BR)
# vont à un technicien dont le BR est valide : le seul avertissement d'habilitation de la démo reste
# celui que l'on provoque en planifiant ot_a_planifier_br.
PLANNING_DEMO = [
    # --- semaine 1 (celle de la date de référence)
    ot_prevu('AE-01', 1, 1, 2.5, 'Remplacement du parafoudre du TGBT (voyant de fin de vie allumé)',
             "Consigner le départ du parafoudre, remplacer la cartouche, contrôler le voyant et la continuité de la terre.",
             cree=6),
    ot_prevu('PT-01', 2, 2, 4.0, 'Remplacement des galets de guidage du chariot du pont',
             "Consigner le pont, poser la charge au sol, remplacer les galets de guidage usés et régler le jeu.", cree=9),
    ot_prevu('SC-01', 3, 4, 2.0, 'Réglage du guide-lame et remplacement des brosses de nettoyage',
             "Régler le guide-lame au jeu préconisé, remplacer les brosses de nettoyage de la lame, faire une coupe d'essai.",
             priorite='P4', cree=8),
    ot_prevu('RB-01', 4, 3, 2.5, 'Sauvegarde du programme du robot et contrôle des butées logicielles',
             "Sauvegarder le programme et les paramètres du robot sur la clé du service, contrôler les butées logicielles des axes.",
             type_ot='amélioration', cree=5),
    # --- semaine 2 : arrêt programmé de fin octobre (le mécanicien est en surcharge)
    ot_prevu('PR-01.GH', 7, 2, 8.0, 'Remplacement des flexibles usés du groupe hydraulique' + ARRET,
             "Décomprimer le circuit, remplacer les flexibles marqués lors des préventifs, compléter le niveau d'huile, "
             "purger et contrôler l'étanchéité sous pression.", pieces=[('flex_hydr', 2), ('huile_hlp46', 1)], cree=18),
    ot_prevu('CV-02', 8, 2, 7.5, "Remplacement des rouleaux grippés de la zone d'accumulation" + ARRET,
             "Déposer les rouleaux grippés, poser des galets neufs, contrôler l'alignement et la tension de la transmission.",
             pieces=[('galet', 6)], cree=18),
    ot_prevu('PO-01', 9, 2, 4.0, "Alignement laser du groupe motopompe et remplacement de l'accouplement" + ARRET,
             "Consigner la pompe, remplacer l'accouplement élastique, aligner moteur et pompe au laser, relever les "
             "vibrations à la remise en route.", pieces=[('accoup', 1)], cree=17),
    ot_prevu('CN-01', 10, 2, 7.0, 'Contrôle de la géométrie et réglage des lardons du tour' + ARRET,
             "Mesurer les jeux des glissières, régler les lardons, contrôler la géométrie au comparateur et noter les valeurs.",
             cree=17),
    ot_prevu('CH-01', 11, 2, 6.0, 'Remplacement des roues porteuses du chariot' + ARRET,
             "Débrancher la batterie, lever le chariot sur chandelles, remplacer les deux roues porteuses usées, essai de roulage.",
             pieces=[('roue_chariot', 2)], cree=16),
    ot_prevu('RB-01', 11, 2, 6.0, 'Remplacement des ventouses et des flexibles de vide de la pince' + ARRET,
             "Remplacer les ventouses et les flexibles de vide de la pince, contrôler le vide et la prise des colis à "
             "vitesse réduite.", cree=16),
    ot_prevu('AE-01', 7, 1, 7.0, 'Resserrage des jeux de barres et thermographie du TGBT' + ARRET,
             "Consigner le TGBT pendant l'arrêt programmé, resserrer au couple les jeux de barres et les départs, faire une "
             "thermographie à la remise sous tension.", cree=18),
    ot_prevu('CP-01.SEC', 9, 4, 3.0, 'Nettoyage du condenseur du sécheur et contrôle du purgeur' + ARRET,
             "Nettoyer le condenseur du sécheur, contrôler le purgeur de condensats et le point de rosée à la remise en route.",
             pieces=[('nettoyant', 1)], cree=15),
    ot_prevu('CN-01', 11, 3, 3.0, 'Mise à jour des compensations de la commande numérique après le réglage de la géométrie',
             "Reprendre les compensations des axes dans la commande numérique avec les mesures du réglage, usiner une pièce "
             "témoin.", type_ot='amélioration', cree=15),
    # --- semaine 3
    ot_prevu('RA-01', 15, 4, 2.0, "Remplacement du purgeur automatique du réservoir (observation du dernier contrôle)",
             "Isoler le réservoir et le purger jusqu'à 0 bar, remplacer le purgeur automatique, contrôler son fonctionnement ; "
             "garder la preuve pour lever l'observation de l'organisme.", cree=10),
    ot_prevu('AE-02', 16, 1, 1.5, "Remplacement des voyants de présence tension de l'armoire",
             "Consigner l'armoire, remplacer les voyants de présence tension défectueux, contrôler leur allumage.",
             priorite='P4', cree=6),
    ot_prevu('CU-01', 17, 3, 2.0, "Réglage du palpeur de mesure d'outils",
             "Contrôler et régler le palpeur de mesure d'outils, vérifier les longueurs mesurées sur trois outils étalons.",
             cree=4),
    # --- semaine 4
    ot_prevu('PO-01', 22, 2, 1.0, "Contrôle des vibrations du groupe motopompe après l'alignement",
             "Relever les vibrations aux paliers et les comparer aux valeurs relevées après l'alignement de l'arrêt "
             "programmé.", priorite='P4', cree=17),
    ot_prevu('CN-01.BR', 24, 1, 1.5, "Contrôle de l'isolement et de l'intensité du moteur de broche",
             "Mesurer l'isolement du moteur de broche au mégohmmètre et son intensité à vide et en charge, noter les valeurs.",
             cree=3),
]

# OT « Préparé » à planifier (sans technicien) : chacun vient d'une DI acceptée puis préparée (pièces
# prévues). `jour` = date prévue en jours après la date de référence (aucun n'est en retard).
A_PLANIFIER_DEMO = [
    {'role': 'ot_a_planifier', 'repere': 'CV-02.M', 'cree': 4, 'heure': 10.1, 'delai': 35, 'jour': 3,
     'demandeur': 'Inès Marchand', 'impact': 'gêne', 'heures': 1.5, 'pieces': [('joint_spi', 1)],
     'texte_di': "De l'huile coule sous le motoréducteur du convoyeur CV-02, une petite flaque se forme.",
     'scenario': scenario('S01', 'C01', 'R01', 1, [MECA], (1.0, 2.0), (('gêne', 1),), (),
                          "Fuite d'huile au joint de sortie du motoréducteur",
                          "Remplacer le joint à lèvres de sortie du motoréducteur, compléter le niveau d'huile et nettoyer "
                          "le carter.", [], [])},
    # Scénario « habilitation » : AE-03 exige BR ; le planifier sur TEC-0004 (BR échue) avertit (RG8).
    {'role': 'ot_a_planifier_br', 'repere': 'AE-03', 'cree': 3, 'heure': 13.65, 'delai': 50, 'jour': 4,
     'demandeur': 'Camille Girard', 'impact': 'gêne', 'heures': 1.5, 'pieces': [],
     'texte_di': "Le ventilateur de l'armoire de commande AE-03 fait un bruit de frottement.",
     'scenario': scenario('S02', 'C02', 'R01', 1, [ELEC], (1.0, 2.0), (('gêne', 1),), (),
                          "Ventilateur de l'armoire bruyant",
                          "Consigner l'armoire (habilitation BR), remplacer le ventilateur et nettoyer la grille du filtre.",
                          [], [])},
    # Refus RG3 au planning : 4 capteurs prévus, 3 en stock (l'achat de capteurs est « commandée »).
    {'role': 'ot_a_planifier_piece_manquante', 'repere': 'CU-01.CH', 'cree': 5, 'heure': 9.35, 'delai': 40, 'jour': 2,
     'demandeur': 'Camille Girard', 'impact': 'gêne', 'heures': 2.5, 'pieces': [('capteur_m18', 4)],
     'texte_di': "Le changeur d'outils de CU-01 se met en défaut de position plusieurs fois par jour.",
     'scenario': scenario('S05', 'C04', 'R01', 1, [AUTO], (2.0, 3.0), (('gêne', 1),), (),
                          "Défauts de position du magasin d'outils",
                          "Remplacer les quatre capteurs de position du magasin d'outils (réglage instable), les régler et "
                          "tester dix changements d'outil.", [], [])},
]

# Équipements dont un test recalcule les indicateurs à la main (§15.13) : un de criticité A, heures de
# fonctionnement connues, des pannes sur les 12 derniers mois ; ensemble, ils portent la panne non
# clôturée (CP-01), la panne qui a attendu une pièce (PO-01) et la panne sans durée d'arrêt (CV-02).
EQUIPEMENTS_CALCUL_MAIN = ('CP-01', 'PO-01', 'CV-02')

MOTIF_ATTENTE_PIECE = ('Pièce : moteur 5,5 kW de rechange (non tenu en stock) commandé chez Électro-Alpes '
                       'Distribution, livraison demain matin.')


def creer_ot_planifie(ctx, prevu):
    """OT « Planifié » créé par le responsable (origine « manuel ») : technicien, date prévue, temps prévu."""
    equipement = ctx.equipement[prevu['repere']]
    jour_creation = jour_ouvre_avant(ctx.ref - timedelta(days=prevu['cree']))
    creation = instant(jour_creation, 8.0) + timedelta(minutes=ctx.rng.randrange(0, 300, 5))
    ot = creer_ligne(
        ctx, 'ordres_travail', origine='manuel', equipement_id=equipement['id'], type=prevu['type'],
        priorite=prevu['priorite'], statut='Planifié', titre='%s — %s' % (prevu['repere'], prevu['titre']),
        travail_a_faire=prevu['travail'], consignes=consignes_ot(equipement), date_creation=texte_dh(creation),
        date_prevue=texte_date(ctx.ref + timedelta(days=prevu['jour'])),
        technicien_id=ctx.techniciens[prevu['technicien'] - 1]['id'], temps_prevu_h=prevu['heures'])
    ajouter_pieces_ot(ctx, ot, equipement, prevu['pieces'])
    return ot


def creer_ot_a_planifier(ctx, definition):
    """OT « Préparé » à planifier : DI acceptée, OT préparé (pièces prévues), sans technicien."""
    quand = instant(jour_ouvre_avant(ctx.ref - timedelta(days=definition['cree'])), definition['heure'])
    _demande, ot = creer_correctif(
        ctx, ctx.equipement[definition['repere']], definition['scenario'], quand, definition['impact'], 'Préparé',
        texte_di=definition['texte_di'], demandeur=definition['demandeur'], description='',
        delai_decision=definition['delai'], date_prevue=ctx.ref + timedelta(days=definition['jour']),
        temps_prevu=definition['heures'], pieces=definition['pieces'], symptome_code=definition['scenario']['symptome'])
    ctx.marquer(definition['role'], ot)


def creer_panne_attente_pieces(ctx):
    """Panne de PO-01 (pompe d'eau glacée, 16 h par jour) qui a attendu une pièce non tenue en stock :
    diagnostic le matin, « En attente : Pièce : … » vers 10 h, reprise le lendemain à la livraison.
    L'attente (environ 22 h) est plus courte que la durée d'arrêt (du signalement à la remise en route)."""
    equipement = ctx.equipement['PO-01']
    jour = jour_ouvre_avant(ctx.ref - timedelta(days=41))
    if jour < ctx.debut:
        return
    lendemain = jour_ouvre_apres(jour + timedelta(days=1))
    mecanicien, electricien = ctx.techniciens[1], ctx.techniciens[0]
    signalement = instant(jour, 7 + 40 / 60.0)
    decision = signalement + timedelta(minutes=12)
    debut = decision + timedelta(minutes=13)
    mise_en_attente = instant(jour, 9 + 50 / 60.0)
    reprise = instant(lendemain, 8.25)
    fin = instant(lendemain, 11.5)
    demande = creer_ligne(
        ctx, 'demandes', date_heure=texte_dh(signalement), demandeur='Mathieu Roux', equipement_id=equipement['id'],
        symptome="La pompe d'eau glacée PO-01 s'est arrêtée, le moteur a fait un bruit de ferraille avant de caler.",
        impact='arrêt', description="Plus d'eau glacée sur la ligne.", statut='Acceptée', date_decision=texte_dh(decision),
        symptome_code='S02')
    ot = creer_ligne(
        ctx, 'ordres_travail', origine='DI', di_id=demande, equipement_id=equipement['id'], type='correctif immédiat',
        priorite=priorite_calculee(equipement['crit'], 'arrêt'), statut='Clôturé administrativement',
        motif_attente=MOTIF_ATTENTE_PIECE, titre='PO-01 — Moteur de pompe bloqué, roulements grippés',
        travail_a_faire="Diagnostiquer le moteur, le remplacer si les roulements ou le bobinage sont hors service.",
        consignes=consignes_ot(equipement), date_creation=texte_dh(decision), date_prevue=texte_date(jour),
        technicien_id=mecanicien['id'], temps_prevu_h=3.0, date_debut=texte_dh(debut), date_fin=texte_dh(fin),
        arret_production=1, duree_arret_h=quart_heure((fin - signalement).total_seconds() / 3600.0),
        symptome_code='S02', cause_code='C02', remede_code='R01', remise_service=1,
        compte_rendu="Roulements du moteur grippés et bobinage échauffé : moteur remplacé par un moteur neuf, livré le "
                     "lendemain matin (non tenu en stock), alignement contrôlé, intensité absorbée normale. Proposition : "
                     "garder un moteur de rechange au magasin, la pompe alimente toute l'eau glacée.",
        date_cloture_tech=texte_dh(fin + timedelta(minutes=20)),
        date_cloture_admin=texte_dh(instant(jour_ouvre_apres(lendemain + timedelta(days=2)), 9.0)))
    renseigner(demande, ot_id=ot)
    # Temps passés : diagnostic le premier jour, remplacement le lendemain (l'électricien raccorde le moteur).
    for technicien, jour_temps, heures in ((mecanicien, jour, 1.75), (mecanicien, lendemain, 3.25),
                                           (electricien, lendemain, 1.5)):
        creer_ligne(ctx, 'ot_temps', ot_id=ot, technicien_id=technicien['id'], date=texte_date(jour_temps), heures=heures)
    ctx.attentes.append({'ot': ot, 'debut': mise_en_attente, 'fin': reprise, 'motif': MOTIF_ATTENTE_PIECE})
    ctx.marquer('panne_attente_pieces', ot)


def creer_panne_sans_duree(ctx):
    """Panne clôturée de CV-02 dont la durée d'arrêt n'a pas été relevée (duree_arret_h vide) : le
    MTTR la met à part (« sans durée d'arrêt », §15.3)."""
    equipement = ctx.equipement['CV-02']
    jour = jour_ouvre_avant(ctx.ref - timedelta(days=24))
    if jour < ctx.debut:
        return
    signalement = instant(jour, 10 + 20 / 60.0)
    _demande, ot = creer_correctif(
        ctx, equipement, trouver_scenario('convoyeur', 'C04', 'S05'), signalement, 'arrêt', 'clos',
        texte_di="Le convoyeur CV-02 s'arrête à chaque passage de colis, la ligne de conditionnement est bloquée.",
        demandeur='Lucas Perrot', description='', delai_decision=10, symptome_code='S05', pieces=[], heures=1.0,
        compte_rendu="Cellule de détection d'entrée encrassée par des résidus de film : nettoyée et réalignée, essais "
                     "sur 30 minutes sans arrêt. Durée d'arrêt de la ligne non relevée.")
    renseigner(ot, arret_production=1, duree_arret_h='', statut='Clôturé administrativement',
               date_cloture_admin=texte_dh(instant(jour_ouvre_apres(jour + timedelta(days=3)), 9.5)))
    ctx.marquer('panne_sans_duree', ot)


def completer_demo_lot3(ctx):
    """Ajouts du lot 3 au jeu de démo (§15.12) : planning, OT à planifier, pannes remarquables."""
    for prevu in PLANNING_DEMO:
        creer_ot_planifie(ctx, prevu)
    for definition in A_PLANIFIER_DEMO:
        creer_ot_a_planifier(ctx, definition)
    creer_panne_attente_pieces(ctx)
    creer_panne_sans_duree(ctx)


# ---------------------------------------------------------------------------
# Journal : historique des statuts des pannes récentes (format exact de Donnees.modifier)
# ---------------------------------------------------------------------------

POSTE_DEMO = 'Poste démo'
CARACTERES_JOURNAL = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'   # comme CARACTERES_ALEATOIRES (js/donnees.js)
MARGE_HISTORIQUE_JOURS = 7          # la démo décale ses dates par semaines entières (§11)
TYPES_CORRECTIFS = ('correctif immédiat', 'correctif différé')


def instant_depuis_texte(texte):
    """'AAAA-MM-JJ HH:MM' → datetime."""
    return datetime.strptime(texte, '%Y-%m-%d %H:%M')


def debut_historique_statuts(ctx):
    """Premier jour des pannes dont l'historique des statuts est au journal : 3 mois avant la date de
    référence, moins une semaine de marge."""
    return ajouter_mois(ctx.ref, -3) - timedelta(days=MARGE_HISTORIQUE_JOURS)


def est_panne(ot):
    """Panne (§15.3) : OT correctif, arrêt de production, non annulé."""
    return ot['type'] in TYPES_CORRECTIFS and ot['arret_production'] == '1' and ot['statut'] != 'Annulé'


def date_de_panne(ot, demandes, demandes_par_ot):
    """§15.3 : date_heure de la DI de l'OT (di_id, sinon une DI dont ot_id est l'OT), sinon date_creation."""
    if ot['di_id'] in demandes:
        return jour_depuis_texte(demandes[ot['di_id']]['date_heure'][:10])
    liees = sorted(d['date_heure'] for d in demandes_par_ot.get(ot['id'], []))
    return jour_depuis_texte((liees[0] if liees else ot['date_creation'])[:10])


def profil_demandeur(ctx, nom):
    """Profil inscrit au journal pour l'auteur d'une DI : un technicien est connu par son identifiant."""
    for technicien in ctx.techniciens:
        if nom_complet(technicien) == nom:
            return 'Technicien ' + technicien['id']
    return 'Demandeur ' + nom


def moments_de_preparation(ctx, creation, debut):
    """Heures des passages « Préparé » puis « Planifié » d'un correctif différé, entre sa création et son
    démarrage (quelques minutes de travail du responsable, en heures ouvrées)."""
    prepare = apres_minutes_ouvrees(creation, ctx.rng.randint(5, 30))
    planifie = apres_minutes_ouvrees(prepare, ctx.rng.randint(5, 20))
    if not creation < prepare < planifie < debut:
        ecart = (debut - creation) / 3
        prepare, planifie = arrondir_minute(creation + ecart), arrondir_minute(creation + 2 * ecart)
    return prepare, planifie


def entrees_de_l_ot(ctx, ot, attentes):
    """Entrées du journal d'un OT, dans l'ordre où Prévo les écrit : [(instant, profil, action)].

    Création : « création — acceptation de DI-… » (demandes-ecritures.js) ou « création — création de
    l'OT (urgence) » (ordres-ecritures.js). Puis un passage de statut par changement (RG3 : un correctif
    différé passe par Préparé et Planifié ; un correctif immédiat démarre directement), avec la liste des
    champs modifiés que Donnees.modifier écrit avant « — ».
    """
    technicien = 'Technicien ' + ot['technicien_id']
    creation = instant_depuis_texte(ot['date_creation'])
    if ot['origine'] == 'DI':
        entrees = [(creation, 'Responsable', 'création — acceptation de ' + ot['di_id'])]
    else:
        auteur = technicien if ot['origine'] == 'urgence' else 'Responsable'
        entrees = [(creation, auteur, "création — création de l'OT (%s)" % ot['origine'])]
    statut = 'Créé'

    def passer(moment, profil, cible, champs, motif=''):
        nonlocal statut
        action = 'modification : %s — statut %s → %s' % (champs, statut, cible) + (' : ' + motif if motif else '')
        entrees.append((moment, profil, action))
        statut = cible

    if not ot['date_debut']:
        raise ErreurCoherence('%s : panne sans date de début, historique impossible' % ot['id'])
    debut = instant_depuis_texte(ot['date_debut'])
    if ot['type'] == 'correctif différé' and ot['origine'] != 'urgence':
        prepare, planifie = moments_de_preparation(ctx, creation, debut)
        passer(prepare, 'Responsable', 'Préparé', 'statut')
        passer(planifie, 'Responsable', 'Planifié', 'statut')
    passer(debut, technicien, 'En cours', 'statut, date_debut')
    for attente in sorted(attentes, key=lambda a: a['debut']):
        passer(attente['debut'], technicien, 'En attente', 'statut, motif_attente', attente['motif'])
        passer(attente['fin'], technicien, 'En cours', 'statut')
    if ot['date_cloture_tech']:
        passer(instant_depuis_texte(ot['date_cloture_tech']), technicien, 'Clôturé techniquement',
               'statut, date_cloture_tech')
    if ot['date_cloture_admin']:
        passer(instant_depuis_texte(ot['date_cloture_admin']), 'Responsable', 'Clôturé administrativement',
               'statut, date_cloture_admin')
    return entrees


def entrees_des_demandes(ctx, ot, demandes):
    """Entrées du journal des DI d'un OT : signalement, puis acceptation (ou regroupement) par le responsable."""
    entrees = []
    for demande in demandes:
        signalee = 'création — demande signalée' + (' pendant ' + demande['ot_origine_id'] if demande['ot_origine_id'] else '')
        entrees.append((instant_depuis_texte(demande['date_heure']), demande['id'],
                        profil_demandeur(ctx, demande['demandeur']), signalee))
        if demande['statut'] == 'Acceptée':
            decision = 'modification : statut, date_decision, ot_id — acceptée → ' + ot['id']
        else:
            decision = 'modification : statut, motif_decision, date_decision, ot_id — regroupée avec ' + ot['id']
        entrees.append((instant_depuis_texte(demande['date_decision']), demande['id'], 'Responsable', decision))
    return entrees


def identifiant_journal(ctx, moment, seconde, pris):
    """J-AAAAMMJJHHMMSS-XXXX (§4) : la minute de l'entrée, une seconde, 4 caractères tirés au hasard."""
    while True:
        identifiant = 'J-%s%02d-%s' % (moment.strftime('%Y%m%d%H%M'), seconde,
                                       ''.join(ctx.rng.choice(CARACTERES_JOURNAL) for _ in range(4)))
        if identifiant not in pris:
            pris.add(identifiant)
            return identifiant


def generer_journal(ctx, garder=None):
    """Journal de la démo : historique des statuts des pannes récentes et de leurs DI (voir la docstring).

    Les entrées d'une même minute reçoivent des secondes croissantes dans l'ordre où Prévo les écrit :
    trier le fichier par date_heure puis identifiant redonne cet ordre (§15.3).
    `garder(ot)` : seuls les OT retenus ont leurs entrées (défaut : tous) ; les OT de scénario du lot 6 sont écrits
    à part, sous hasard_du_lot6, pour que les entrées des autres OT ne changent pas.
    """
    base = ctx.base
    demandes = {d['id']: d for d in base['demandes']}
    demandes_par_ot = {}
    for demande in base['demandes']:
        if demande['ot_id']:
            demandes_par_ot.setdefault(demande['ot_id'], []).append(demande)
    attentes = {}
    for attente in ctx.attentes:
        attentes.setdefault(attente['ot']['id'], []).append(attente)
    debut = debut_historique_statuts(ctx)
    entrees = []                      # (instant, table, id_ligne, profil, action), dans l'ordre d'écriture
    for ot in base['ordres_travail']:
        if garder is not None and not garder(ot):
            continue
        if not (est_panne(ot) and date_de_panne(ot, demandes, demandes_par_ot) >= debut):
            continue
        entrees += [(moment, 'ordres_travail', ot['id'], profil, action)
                    for moment, profil, action in entrees_de_l_ot(ctx, ot, attentes.get(ot['id'], []))]
        liees = sorted(demandes_par_ot.get(ot['id'], []), key=lambda d: (d['date_heure'], d['id']))
        entrees += [(moment, 'demandes', identifiant, profil, action)
                    for moment, identifiant, profil, action in entrees_des_demandes(ctx, ot, liees)]
    # Ordre du temps ; à la même minute, l'ordre d'écriture (rang dans la liste).
    ordonnees = [entree for _rang, entree in sorted(enumerate(entrees), key=lambda e: (e[1][0], e[0]))]
    pris = {ligne['id'] for ligne in base['journal']}
    for minute, groupe in groupby(ordonnees, key=lambda entree: entree[0]):
        groupe = list(groupe)
        secondes = sorted(ctx.rng.sample(range(60), len(groupe)))
        for (_moment, table, id_ligne, profil, action), seconde in zip(groupe, secondes):
            ligne = creer_ligne(ctx, 'journal', id=identifiant_journal(ctx, minute, seconde, pris),
                                date_heure=texte_dh(minute), poste=POSTE_DEMO, profil=profil, id_ligne=id_ligne,
                                action=action)
            renseigner(ligne, table=table)     # « table » est aussi le nom d'un paramètre de creer_ligne


# =============================================================================
# 5 ter. LOT 3 BIS : PRÉVENTIF SUGGÉRÉ (ARCHITECTURE.md §16.8, D62)
# =============================================================================
# Tout ce bloc est appelé sous hasard_du_lot3bis (voir construire_jeu) : ses tirages au hasard ne changent
# pas ceux des lots 1 à 3. Les cas déjà présents restent : S1 de CV-02 (capteur encrassé), S2 de PO-02
# (garniture usée), S4 de la gamme mensuelle de VE-01, et CP-01.SEC (2 filtres colmatés, sans gamme : sous
# le seuil). On ajoute deux gammes RÉCENTES (mises en place cet été) et une décision au journal :
#   - RA-01 (réservoir d'air, criticité B) : son purgeur automatique se bloque (c'est l'observation du
#     dernier contrôle réglementaire). Anomalie à 2 des 4 dernières visites, l'une par la case « anomalie
#     constatée », l'autre par une DI liée → S3. Son remplacement est déjà planifié (PLANNING_DEMO).
#   - GF-01 (groupe froid, criticité A) : visites de suite sans anomalie et aucune panne depuis la
#     première ; S4 la refuse pour sa seule criticité A (une obligation peut imposer la fréquence).
#   - CP-01 : la suggestion S2 « filtre colmaté » a été ignorée au printemps (motif au journal) ; trois
#     pannes de même cause sont arrivées depuis : elle est revenue.
# Périodicité de 14 jours et dernière visite récente : aucune de ces gammes ne devient échue dans la
# semaine qui suit la date de référence (la démo décale ses dates par semaines entières, §11).

STATUTS_CLOTURES = ('Clôturé techniquement', 'Clôturé administrativement')

OPS_RESERVOIR = [
    ('Purger manuellement le réservoir par la vanne basse', "Peu d'eau (moins d'un verre)", 'ok'),
    ('Tester le purgeur automatique (bouton test)', 'Purge franche au test', 'ok'),
    ('Relever la pression du réservoir au manomètre', '6,5 à 7,5 bar', (6.7, 7.3, 1, ' bar', 'pression du réservoir')),
    ("Contrôler l'absence de fuite aux raccords et à la soupape", 'Aucune fuite', 'ok'),
]
OPS_FROID_SUIVI = [
    ('Relever la pression haute (HP)', '< 18 bar', (14.0, 17.0, 1, ' bar', 'pression haute')),
    ('Relever la pression basse (BP)', '3 à 5 bar', (3.4, 4.6, 1, ' bar', 'pression basse')),
    ("Relever la température de départ d'eau glacée", '6 à 8 °C', (6.2, 7.8, 1, ' °C', "température de départ d'eau glacée")),
    ("Contrôler l'afficheur de la régulation", 'Aucune alarme active', 'ok'),
    ("Rechercher les traces d'huile ou de givre sur les tuyauteries", 'Aucune trace', 'ok'),
]

# Anomalie vue à une visite, deux façons de la noter (§16.2 : case cochée OU DI liée).
# Case cochée seule : le technicien a réglé sur place, il n'y a rien à demander.
ANOMALIE_RA01_CASE = {
    'constat': "Anomalie constatée : purgeur automatique de nouveau bloqué, beaucoup d'eau à la purge manuelle ; "
               "réservoir purgé à la main. Son remplacement est déjà planifié."}
# DI liée (ot_origine_id) envoyée juste APRÈS la clôture administrative de la visite (le responsable a clôturé
# pendant que le technicien saisissait sa demande) : l'OT, déjà verrouillé, n'est pas marqué « anomalie
# constatée » (ARCHITECTURE.md §14.6, écart retenu ; Demandes.marquerAnomalie). La DI est acceptée le jour
# même ; le correctif, fait le lendemain, propose de remplacer le purgeur.
ANOMALIE_RA01_DI = {
    'di': True,
    'constat': "Purgeur automatique bloqué : beaucoup d'eau à la purge manuelle, réservoir purgé à la main. "
               "Demande d'intervention à envoyer pour le nettoyer.",
    'texte_di': "Le purgeur automatique du réservoir RA-01 ne purge plus : beaucoup d'eau à la purge manuelle.",
    'impact': 'gêne', 'symptome': 'S99', 'cause': 'C05', 'remede': 'R03', 'heures': 1.0, 'metiers': [MECA, POLY],
    'titre': 'Purgeur automatique du réservoir bloqué',
    'travail': "Isoler le réservoir et le purger jusqu'à 0 bar, démonter le purgeur automatique, nettoyer son filtre "
               "et son clapet, contrôler la purge au bouton test.",
    'compte_rendu': "Filtre du purgeur automatique colmaté par des boues : purgeur démonté, filtre et clapet nettoyés, "
                    "purge de nouveau franche au bouton test. Purgeur en fin de vie : à remplacer (observation du "
                    "dernier contrôle réglementaire)."}

# Les deux gammes du lot 3 bis. `derniere` = dernière visite, en jours avant la date de référence ; `visites`
# = nombre de visites, tous les `periode` jours en remontant (même jour de la semaine) ; `anomalies` = {rang
# de la visite en partant de la plus récente : anomalie}. `suggestion` : nom du cas (ctx.gammes_lot3bis).
GAMMES_LOT3BIS = [
    {'suggestion': 'anomalies', 'repere': 'RA-01', 'libelle': "Purge et contrôle du réservoir d'air RA-01",
     'periode': 14, 'avance': 1, 'derniere': 5, 'visites': 5, 'temps': 0.5, 'ops': OPS_RESERVOIR,
     'metiers': [MECA, POLY], 'remede': 'R03',
     'consignes': "Le réservoir reste sous pression : ne jamais démonter le purgeur sans avoir isolé et purgé "
                  "le réservoir.",
     'anomalies': {1: ANOMALIE_RA01_CASE, 3: ANOMALIE_RA01_DI}},
    {'suggestion': 'refus', 'role': 'suggestion_refus_criticite_a', 'repere': 'GF-01',
     'libelle': 'Contrôle de fonctionnement du groupe froid GF-01', 'periode': 14, 'avance': 0, 'derniere': 7,
     'visites': 6, 'temps': 0.5, 'ops': OPS_FROID_SUIVI, 'metiers': [ELEC, MECA], 'remede': 'R03',
     'consignes': "Contrôle en marche, capots fermés : toute intervention sur le groupe exige l'habilitation BR."},
]

# Suggestion ignorée puis revenue (§16.4) : (règle, repère, cause). CP-01 a des gammes suivies : S2.
DECISION_IGNOREE_DEMO = ('S2', 'CP-01', 'C05')
MOTIF_IGNOREE_DEMO = ("Cartouches de filtre à huile d'un lot défectueux, échangées par le fournisseur sous "
                      "garantie. On surveille avant de modifier les gammes.")


def creer_gamme_lot3bis(ctx, specification):
    """Gamme récente (date) : sa ligne, ses opérations, puis ses visites (OT préventifs clôturés).
    Dernière réalisation et prochaine échéance suivent la dernière visite (RG5)."""
    equipement = ctx.equipement[specification['repere']]
    jours = [ctx.ref - timedelta(days=specification['derniere'] + rang * specification['periode'])
             for rang in reversed(range(specification['visites']))]
    jours = [jour for jour in jours if jour >= ctx.debut]          # --mois : historique plus court
    ligne = creer_ligne(ctx, 'gammes', equipement_id=equipement['id'], libelle=specification['libelle'],
                        declencheur='date', periodicite_jours=specification['periode'],
                        avance_jours=specification['avance'], temps_prevu_h=specification['temps'],
                        consignes=specification['consignes'])
    for ordre, (operation, attendue, _mesure) in enumerate(specification['ops'], 1):
        creer_ligne(ctx, 'gamme_operations', gamme_id=ligne['id'], ordre=ordre, operation=operation,
                    valeur_attendue=attendue)
    gamme = dict(specification, eq=equipement, id=ligne['id'], ligne=ligne, declencheur='date', compteur=None,
                 seuil=None, ouvert=None, occurrences=[])
    anomalies = specification.get('anomalies', {})
    derniere = None
    for rang, jour in enumerate(jours):
        derniere = creer_visite_lot3bis(ctx, gamme, jour, anomalies.get(len(jours) - rang)).date()
    if derniere is None:
        raise ErreurCoherence('%s : aucune visite dans l\'historique' % specification['libelle'])
    gamme.update(derniere=derniere, prochaine=derniere + timedelta(days=specification['periode']))
    renseigner(ligne, derniere_realisation=texte_date(derniere), prochaine_echeance=texte_date(gamme['prochaine']))
    gamme['echue'] = est_gamme_echue(ctx, gamme)
    ctx.gammes.append(gamme)
    ctx.gammes_lot3bis[specification['suggestion']] = ligne
    if specification.get('role'):
        ctx.marquer(specification['role'], ligne)


def creer_visite_lot3bis(ctx, gamme, jour, anomalie=None):
    """Visite d'une gamme du lot 3 bis le jour `jour` : OT préventif clôturé ; retourne sa date-heure de fin.

    Même déroulé que creer_preventif (opérations copiées, mesures, temps passés, aucune pièce), avec une
    clôture maîtrisée : administrative le jour ouvré suivant, ou seulement technique pour la dernière
    semaine (comme les OT récents) ; aussitôt pour la visite dont la DI arrive après le verrou."""
    rng = ctx.rng
    equipement = gamme['eq']
    jour_creation = min(jour_ouvre_apres(jour - timedelta(days=gamme['avance'])), jour)
    creation = instant(jour_creation, 7.0) + timedelta(minutes=rng.randint(10, 40))
    ot = creer_ligne(
        ctx, 'ordres_travail', origine='préventif', gamme_id=gamme['id'], equipement_id=equipement['id'],
        type='préventif systématique', priorite='P4' if equipement['crit'] == 'C' else 'P3', statut='Créé',
        titre=gamme['libelle'], travail_a_faire='Réaliser les %d opérations de la gamme.' % len(gamme['ops']),
        consignes=gamme['consignes'], date_creation=texte_dh(creation), date_prevue=texte_date(jour),
        temps_prevu_h=gamme['temps'])
    mesures = []
    for ordre, (operation, attendue, mesure) in enumerate(gamme['ops'], 1):
        valeur = mesure_simulee(rng, mesure)
        creer_ligne(ctx, 'ot_operations', ot_id=ot, ordre=ordre, operation=operation, valeur_attendue=attendue,
                    fait=1, valeur_mesuree=valeur)
        if isinstance(mesure, tuple):
            mesures.append((mesure[4], valeur))
    technicien = choisir_technicien(ctx, gamme['metiers'], equipement, jour)
    debut = heure_aleatoire(rng, jour, 7.75, 10.5)
    renseigner(ot, technicien_id=technicien['id'], date_debut=texte_dh(debut))
    fin = enregistrer_temps(ctx, ot, [(technicien, 1.0)], debut, quart_heure(gamme['temps'] * rng.uniform(0.8, 1.3)))
    compte_rendu = ('Gamme réalisée en totalité. ' + anomalie['constat'] if anomalie
                    else compte_rendu_preventif(ctx, gamme, mesures))
    cloture_technique = fin + timedelta(minutes=rng.randint(5, 20))
    renseigner(ot, date_fin=texte_dh(fin), remise_service=1, cause_code='C99', remede_code=gamme['remede'],
               compte_rendu=compte_rendu, date_cloture_tech=texte_dh(cloture_technique),
               statut='Clôturé techniquement')
    if anomalie and anomalie.get('di'):
        cloture_admin = cloture_technique + timedelta(minutes=10)
    elif (ctx.ref - fin.date()).days > 7:
        cloture_admin = instant(jour_ouvre_apres(fin.date() + timedelta(days=1)), 8.5 + rng.randint(0, 4) / 4.0)
    else:
        cloture_admin = None
    if cloture_admin:
        renseigner(ot, statut='Clôturé administrativement', date_cloture_admin=texte_dh(cloture_admin))
    if anomalie and anomalie.get('di'):
        signaler_anomalie_apres_verrou(ctx, gamme, ot, technicien, cloture_admin + timedelta(minutes=5), anomalie)
    elif anomalie:
        renseigner(ot, anomalie_constatee=1)
        ctx.anomalies_sans_di.append(ot)
    return fin


def signaler_anomalie_apres_verrou(ctx, gamme, visite, technicien, envoi, anomalie):
    """DI liée à une visite déjà clôturée administrativement (voir ANOMALIE_RA01_DI) : la visite garde
    anomalie_constatee = 0. La DI est acceptée (RG1, priorité de la matrice RG2) et son correctif, fait le
    lendemain matin, est clôturé (RG4) ; sans arrêt de production (impact « gêne ») : ce n'est pas une panne."""
    equipement = gamme['eq']
    demande = creer_ligne(
        ctx, 'demandes', date_heure=texte_dh(envoi), demandeur=nom_complet(technicien), equipement_id=equipement['id'],
        symptome=anomalie['texte_di'], impact=anomalie['impact'],
        description="Signalée pendant l'OT préventif de la gamme « %s »." % gamme['libelle'], statut='Acceptée',
        symptome_code=anomalie['symptome'], ot_origine_id=visite)
    ctx.di_apres_verrou.append(demande)
    decision = apres_minutes_ouvrees(envoi, ctx.rng.randint(20, 60))
    priorite = priorite_calculee(equipement['crit'], anomalie['impact'])
    immediat = priorite == 'P1' or anomalie['impact'] in ('arrêt', 'sécurité')
    debut = instant(jour_ouvre_apres(decision.date() + timedelta(days=1)), 8.0)
    reparateur = choisir_technicien(ctx, anomalie['metiers'], equipement, debut.date())
    ot = creer_ligne(
        ctx, 'ordres_travail', origine='DI', di_id=demande, equipement_id=equipement['id'],
        type='correctif immédiat' if immediat else 'correctif différé', priorite=priorite,
        statut='Clôturé administrativement', titre='%s — %s' % (equipement['repere'], anomalie['titre']),
        travail_a_faire=anomalie['travail'], consignes=consignes_ot(equipement), date_creation=texte_dh(decision),
        date_prevue=texte_date(date_prevue_par_defaut(decision.date(), priorite)), technicien_id=reparateur['id'],
        temps_prevu_h=anomalie['heures'], date_debut=texte_dh(debut), symptome_code=anomalie['symptome'])
    fin = enregistrer_temps(ctx, ot, [(reparateur, 1.0)], debut, anomalie['heures'])
    renseigner(ot, date_fin=texte_dh(fin), cause_code=anomalie['cause'], remede_code=anomalie['remede'],
               compte_rendu=anomalie['compte_rendu'], remise_service=1,
               date_cloture_tech=texte_dh(fin + timedelta(minutes=15)),
               date_cloture_admin=texte_dh(instant(jour_ouvre_apres(fin.date() + timedelta(days=1)), 9.0)))
    renseigner(demande, date_decision=texte_dh(decision), ot_id=ot)


def completer_demo_lot3bis(ctx):
    """Ajouts du lot 3 bis au jeu de démo (§16.8) : les deux gammes récentes et leurs visites."""
    for specification in GAMMES_LOT3BIS:
        creer_gamme_lot3bis(ctx, specification)


def ajouter_decision_ignoree(ctx):
    """Décision au journal (§16.4), écrite comme Donnees.journaliser l'écrit : le responsable a ignoré la
    suggestion DECISION_IGNOREE_DEMO quelques jours après une panne, à un moment où elle était ouverte, et
    exactement SEUIL_PANNES pannes de même cause sont arrivées depuis : elle est revenue (§16.3).

    Appelé après generer_journal (OT et identifiants définitifs) : la ligne est rangée à sa place (tri par
    date_heure puis identifiant), sans toucher aux entrées du lot 3."""
    regle, repere, cause = DECISION_IGNOREE_DEMO
    equipement = ctx.equipement[repere]
    pannes = sorted(instant_depuis_texte(o['date_fin']) for o in ctx.base['ordres_travail']
                    if o['equipement_id'] == equipement['id'] and o['type'] in TYPES_CORRECTIFS
                    and o['statut'] in STATUTS_CLOTURES and o['cause_code'] == cause)
    if len(pannes) < 2 * SEUIL_PANNES:            # historique trop court (--mois) : pas de décision
        return
    apres_la_panne = pannes[-SEUIL_PANNES - 1].date() + timedelta(days=3)
    moment = instant(jour_ouvre_apres(apres_la_panne), 10.0) + timedelta(minutes=ctx.rng.randrange(0, 60, 5))
    pris = {ligne['id'] for ligne in ctx.base['journal']}
    ligne = creer_ligne(
        ctx, 'journal', id=identifiant_journal(ctx, moment, ctx.rng.randrange(60), pris), date_heure=texte_dh(moment),
        poste=POSTE_DEMO, profil='Responsable', id_ligne=equipement['id'],
        action='suggestion %s-%s-%s ignorée : %s' % (regle, equipement['id'], cause, MOTIF_IGNOREE_DEMO))
    renseigner(ligne, table='equipements')        # « table » est aussi le nom d'un paramètre de creer_ligne
    ctx.base['journal'].sort(key=lambda entree: (entree['date_heure'], entree['id']))


# =============================================================================
# 6. STOCK, ACHATS ET MOUVEMENTS
# =============================================================================

def rejouer_stock(ctx, article, evenements, stock_initial, reapprovisionner):
    """Rejoue les mouvements d'un article dans l'ordre du temps.

    Retourne (stock minimal atteint, stock final, commandes). Si `reapprovisionner`, une commande est
    passée dès que le stock tombe au point de commande ; elle arrive après le délai de l'article.
    Un inventaire applique son écart (perte, casse, pièce retrouvée) et note le stock compté dans
    evenement['valeur'] (valeur absolue écrite dans le mouvement d'inventaire).
    """
    limite = instant(ctx.fin_historique, 17.0)
    stock = minimum = stock_initial
    commandes = []
    en_attente = None
    for genre, evenement in evenements:
        # Réception strictement AVANT le mouvement : à la même minute, la sortie est écrite avant
        # l'entrée dans mouvements_stock.csv (même ordre que le recalcul du stock).
        if en_attente and en_attente['arrivee'] < evenement['quand']:
            stock += en_attente['quantite']
            en_attente['recue'] = True
            en_attente = None
        if genre == 'inventaire':
            stock += evenement['ecart']
            evenement['valeur'] = stock
        else:
            stock += evenement['quantite'] if genre == 'retour' else -evenement['quantite']
        minimum = min(minimum, stock)
        if reapprovisionner and genre == 'sortie' and en_attente is None and stock <= article['pc']:
            commande = jour_ouvre_apres(evenement['quand'].date() + timedelta(days=1))
            en_attente = {'commande': commande, 'quantite': article['qte'], 'recue': False,
                          'arrivee': instant(jour_ouvre_apres(commande + timedelta(days=article['delai'])), 10.5)}
            commandes.append(en_attente)
    if en_attente and en_attente['arrivee'] <= limite:
        stock += en_attente['quantite']
        en_attente['recue'] = True
    return minimum, stock, commandes


def choisir_stock_initial(ctx, article, evenements):
    """Stock au début de l'historique, choisi pour que le stock final soit « raisonnable » (RG6).

    Article « sous le point de commande » (clé `cible`) : aucun réapprovisionnement, le stock final vaut
    exactement `cible`. Les autres : le stock reste positif et, à la date de référence, au-dessus du
    point de commande (sans commande en attente).
    """
    if article['cible'] is not None:
        sorti = sum(e['quantite'] for genre, e in evenements if genre == 'sortie')
        rendu = sum(e['quantite'] for genre, e in evenements if genre == 'retour')
        ecarts = sum(e['ecart'] for genre, e in evenements if genre == 'inventaire')
        return article['cible'] + sorti - rendu - ecarts, False
    stock_initial = article['pc'] + 1
    for _ in range(5000):
        minimum, final, commandes = rejouer_stock(ctx, article, evenements, stock_initial, True)
        manque = max(-minimum, article['pc'] + 1 - final, article['stock_final_min'] - final, 0)
        if manque == 0 and all(commande['recue'] for commande in commandes):
            return stock_initial, True
        stock_initial += max(1, manque)
    raise ErreurCoherence('Stock impossible à équilibrer pour ' + article['designation'])


def jours_inventaire(ctx):
    """Inventaire annuel : le premier jour ouvré à partir du 5 janvier, à 6 h 45 (avant le travail)."""
    instants = []
    for annee in range(ctx.debut.year, ctx.ref.year + 1):
        jour = jour_ouvre_apres(date(annee, 1, 5))
        if ctx.debut < jour <= ctx.fin_historique:
            instants.append(instant(jour, 6.75))
    return instants


def ajuster_reapprovisionnement(ctx, evenements_par_article):
    """Jeu de charge : un grand parc consomme bien plus de pièces que l'atelier de démo. Le stock de
    sécurité, le point de commande (RG6) et la quantité commandée suivent cette consommation : le
    magasin commande souvent (une semaine de consommation à la fois, et au moins deux fois la
    consommation pendant le délai, puisqu'une seule commande est en cours), les achats restent en
    proportion des OT au lieu d'un énorme inventaire de départ."""
    jours = float(max(1, (ctx.ref - ctx.debut).days))
    for cle, article in ctx.articles.items():
        sorti = sum(e['quantite'] for genre, e in evenements_par_article[cle] if genre == 'sortie')
        if sorti == 0:
            continue
        par_jour = sorti / jours
        pendant_le_delai = int(math.ceil(par_jour * article['delai']))
        # Les sorties arrivent par à-coups : sécurité = une consommation moyenne pendant le délai, et
        # point de commande = sécurité + deux fois cette consommation.
        article['sec'] = max(article['sec'], pendant_le_delai)
        article['pc'] = max(article['pc'], article['sec'] + 2 * pendant_le_delai)
        article['qte'] = max(1, int(math.ceil(par_jour * 7)), 2 * pendant_le_delai)
        renseigner(article['ligne'], stock_securite=article['sec'], point_commande=article['pc'],
                   qte_commande=article['qte'])


def construire_stock(ctx):
    """Inventaire de départ, sorties imputées aux OT, retours, inventaires annuels, réceptions et achats
    d'un jeu cohérent (aucun stock négatif à aucun moment ; colonne stock = stock recalculé)."""
    rng = ctx.rng
    evenements_par_article = {cle: [] for cle in ctx.articles}
    for sortie in ctx.sorties:
        evenements_par_article[sortie['article']['cle']].append(('sortie', sortie))
    for retour in ctx.retours:
        evenements_par_article[retour['article']['cle']].append(('retour', retour))
    for quand in jours_inventaire(ctx):
        for cle in ctx.articles:
            evenements_par_article[cle].append(('inventaire', {'quand': quand, 'ecart': ECARTS_INVENTAIRE.get(cle, 0),
                                                               'valeur': None}))
    if ctx.volume:
        ajuster_reapprovisionnement(ctx, evenements_par_article)
    mouvements = []            # (instant, numéro d'ordre, valeurs)
    achats = []
    debut = instant(jour_ouvre_apres(ctx.debut), 6.5)
    for cle, article in ctx.articles.items():
        evenements = sorted(evenements_par_article[cle], key=lambda element: element[1]['quand'])
        stock_initial, reapprovisionner = choisir_stock_initial(ctx, article, evenements)
        # Dernier rejeu avec le stock initial retenu : il fixe aussi les quantités comptées aux inventaires.
        _minimum, _final, commandes = rejouer_stock(ctx, article, evenements, stock_initial, reapprovisionner)
        mouvements.append((debut, len(mouvements), dict(
            article=article, type='inventaire', quantite=stock_initial, utilisateur='Magasin',
            commentaire='Inventaire de départ')))
        for genre, evenement in evenements:
            if genre == 'inventaire':
                ecart = evenement['ecart']
                mouvements.append((evenement['quand'], len(mouvements), dict(
                    article=article, type='inventaire', quantite=evenement['valeur'], utilisateur='Magasin',
                    commentaire='Inventaire annuel' + (' (écart de %+d)' % ecart if ecart else ''))))
                continue
            mouvements.append((evenement['quand'], len(mouvements), dict(
                article=article, type=genre, quantite=evenement['quantite'], ot_id=evenement['ot'],
                utilisateur=evenement['utilisateur'],
                commentaire=('Utilisée sur %s' if genre == 'sortie' else 'Retour au magasin (non utilisée) de %s')
                % evenement['repere'])))
        for commande in commandes:
            achats.append({'article': article, 'date': commande['commande'], 'quantite': commande['quantite'],
                           'statut': 'reçue', 'reception': commande['arrivee']})
    for cle, statut, jours in ACHATS_EN_COURS:           # les achats qui expliquent les articles « à commander »
        if cle in ctx.articles:
            article = ctx.articles[cle]
            achats.append({'article': article, 'date': jours_avant_reference(ctx, jours), 'quantite': article['qte'],
                           'statut': statut, 'reception': None})
    achats.sort(key=lambda achat: achat['date'])
    for achat in achats:
        article = achat['article']
        reception = achat['reception']
        ligne = creer_ligne(
            ctx, 'achats', id=nouvel_identifiant(ctx, 'achats'), date=texte_date(achat['date']),
            article_id=article['id'], fournisseur_id=article['ligne']['fournisseur_id'], quantite=achat['quantite'],
            prix_unitaire=round(article['prix'] * rng.uniform(0.97, 1.03), 2), statut=achat['statut'],
            date_reception=texte_date(reception.date()) if reception else '')
        if reception:
            mouvements.append((reception, len(mouvements), dict(
                article=article, type='entrée', quantite=achat['quantite'], utilisateur='Magasin',
                commentaire='Réception de la commande %s' % ligne['id'])))
    mouvements.sort(key=lambda element: (element[0], element[1]))
    for quand, _ordre, valeurs in mouvements:
        article = valeurs.pop('article')
        creer_ligne(ctx, 'mouvements_stock', id=nouvel_identifiant(ctx, 'mouvements_stock'),
                    date=texte_dh(quand), article_id=article['id'], **valeurs)
    stocks = stocks_recalcules(ctx.base['mouvements_stock'])
    for article in ctx.articles.values():
        renseigner(article['ligne'], stock=stocks.get(article['id'], 0))


def stocks_recalcules(mouvements):
    """Stock de chaque article recalculé depuis les mouvements, dans l'ordre du fichier (un inventaire fixe la valeur)."""
    stocks = {}
    for mouvement in mouvements:
        quantite = float(mouvement['quantite'])
        article = mouvement['article_id']
        if mouvement['type'] == 'inventaire':
            stocks[article] = quantite
        elif mouvement['type'] in ('entrée', 'retour'):
            stocks[article] = stocks.get(article, 0) + quantite
        else:
            stocks[article] = stocks.get(article, 0) - quantite
    return {article: (int(valeur) if valeur == int(valeur) else valeur) for article, valeur in stocks.items()}


# =============================================================================
# 7. IDENTIFIANTS, AUTO-VÉRIFICATION, ÉCRITURE, LIGNE DE COMMANDE
# =============================================================================

def attribuer_identifiants_historique(ctx):
    """DI et OT numérotés dans l'ordre chronologique, par année ; puis leurs lignes liées."""
    for table, champ_date in (('demandes', 'date_heure'), ('ordres_travail', 'date_creation')):
        lignes = ctx.base[table]
        lignes.sort(key=lambda ligne: ligne[champ_date])      # tri stable : l'ordre de création départage
        for ligne in lignes:
            ligne['id'] = nouvel_identifiant(ctx, table, int(ligne[champ_date][:4]))
    for table, cle_tri in (('ot_operations', lambda l: (l['ot_id']['id'], int(l['ordre']))),
                           ('ot_pieces', lambda l: l['ot_id']['id']),
                           ('ot_temps', lambda l: (l['date'], l['ot_id']['id']))):
        ctx.base[table].sort(key=cle_tri)
        for ligne in ctx.base[table]:
            ligne['id'] = nouvel_identifiant(ctx, table)


def resoudre_references(ctx):
    """Remplace les renvois vers des lignes (dictionnaires) par leur identifiant."""
    for lignes in ctx.base.values():
        for ligne in lignes:
            for nom, valeur in ligne.items():
                if isinstance(valeur, dict):
                    ligne[nom] = valeur['id']


MOTIFS_VALEUR = {
    'date': re.compile(r'\d{4}-\d{2}-\d{2}'), 'date_heure': re.compile(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}'),
    'entier': re.compile(r'-?\d+'), 'decimal': re.compile(r'-?\d+(\.\d+)?'),
    'booleen': re.compile(r'[01]'),
}


def verifier_jeu(ctx):
    """Auto-vérification : structure, valeurs, clés étrangères, règles RG1 à RG4 et stock. Lève ErreurCoherence."""
    base = ctx.base
    erreurs = []

    def erreur(message):
        if len(erreurs) < 30:
            erreurs.append(message)

    # --- 1. Structure, formats, identifiants uniques
    cles = {}
    for table in NOMS_TABLES:
        noms = [champ['nom'] for champ in CHAMPS[table]]
        champ_cle = 'cle' if table == 'parametres' else 'id'
        vus = set()
        for ligne in base[table]:
            if list(ligne.keys()) != noms:
                erreur('%s : colonnes inattendues' % table)
                break
            identifiant = ligne[champ_cle]
            if identifiant in vus or identifiant == '':
                erreur('%s : identifiant en double ou vide (%r)' % (table, identifiant))
            vus.add(identifiant)
        cles[table] = vus
    codes_par_famille = {}
    for ligne in base['codes_defaillance']:
        codes_par_famille.setdefault(ligne['famille'], set()).add(ligne['code'])
    for table in NOMS_TABLES:
        for ligne in base[table]:
            for champ in CHAMPS[table]:
                valeur = ligne[champ['nom']]
                if not isinstance(valeur, str):
                    erreur('%s.%s : valeur non résolue' % (table, champ['nom']))
                    continue
                if champ['type'] in MOTIFS_VALEUR and valeur != '' and not MOTIFS_VALEUR[champ['type']].fullmatch(valeur):
                    erreur('%s %s.%s : format invalide %r' % (ligne.get('id'), table, champ['nom'], valeur))
                if (champ['type'] == 'choix' and valeur not in champ['valeurs']
                        and (valeur != '' or (table, champ['nom']) not in CHOIX_FACULTATIFS)):
                    erreur('%s %s.%s : valeur %r hors liste' % (ligne.get('id'), table, champ['nom'], valeur))
                if champ['type'] == 'ref' and valeur != '':
                    if champ['champCible']:
                        valides = codes_par_famille.get(champ['famille'], set())
                    else:
                        valides = cles[champ['table']]
                    if valeur not in valides:
                        erreur('%s %s.%s : référence cassée %r' % (ligne.get('id'), table, champ['nom'], valeur))
    if erreurs:
        raise ErreurCoherence('\n'.join(erreurs))

    # --- 2. Règles métier
    maintenant = texte_dh(ctx.maintenant)
    demandes = {ligne['id']: ligne for ligne in base['demandes']}
    equipements = {ligne['id']: ligne for ligne in base['equipements']}
    temps_par_ot = {}
    for ligne in base['ot_temps']:
        temps_par_ot[ligne['ot_id']] = temps_par_ot.get(ligne['ot_id'], 0.0) + float(ligne['heures'])
    ouverts_par_gamme = {}
    for ot in base['ordres_travail']:
        ident, statut = ot['id'], ot['statut']
        if statut.startswith('Clôturé'):                               # RG4
            manques = [nom for nom in ('date_fin', 'cause_code', 'remede_code', 'date_cloture_tech') if not ot[nom]]
            if len(ot['compte_rendu']) < 10:
                manques.append('compte_rendu (10 caractères)')
            if ot['remise_service'] != '1':
                manques.append('remise_service')
            if temps_par_ot.get(ident, 0) <= 0:
                manques.append('temps passés')
            if (statut == 'Clôturé administrativement') != bool(ot['date_cloture_admin']):
                manques.append('date_cloture_admin incohérente')
            if manques:
                erreur('%s clôturé sans : %s' % (ident, ', '.join(manques)))
            if ot['type'].startswith('correctif') and ot['compte_rendu'].strip().lower().rstrip('.') in ('ras', 'rien à signaler'):
                erreur('%s : compte rendu « RAS » sur un correctif' % ident)
        else:
            if ot['date_fin'] or ot['date_cloture_tech']:
                erreur('%s ouvert mais terminé' % ident)
            if ot['gamme_id']:
                ouverts_par_gamme[ot['gamme_id']] = ouverts_par_gamme.get(ot['gamme_id'], 0) + 1
        if statut == 'En attente' and not ot['motif_attente']:
            erreur('%s en attente sans motif' % ident)
        if statut in ('Planifié', 'En cours', 'En attente') and not ot['technicien_id']:
            erreur('%s %s sans technicien' % (ident, statut))
        if statut == 'En cours' and not ot['date_debut']:
            erreur('%s en cours sans date de début' % ident)
        dates = [ot['date_creation'], ot['date_debut'], ot['date_fin'], ot['date_cloture_tech'], ot['date_cloture_admin']]
        dates = [d for d in dates if d]
        if dates != sorted(dates):
            erreur('%s : dates dans le désordre %s' % (ident, dates))
        if dates and dates[-1] > maintenant:
            erreur('%s : date dans le futur' % ident)
        if ot['origine'] == 'DI':                                      # RG1 et RG2
            demande = demandes.get(ot['di_id'])
            if demande is None or demande['ot_id'] != ident or demande['statut'] != 'Acceptée':
                erreur('%s : demande liée incohérente' % ident)
            elif ot['priorite'] != priorite_calculee(equipements[ot['equipement_id']]['criticite'], demande['impact']):
                erreur('%s : priorité %s contraire à la matrice' % (ident, ot['priorite']))
    for demande in base['demandes']:                                   # RG1
        statut = demande['statut']
        if statut in ('Acceptée', 'Regroupée') and not demande['ot_id']:
            erreur('%s %s sans OT' % (demande['id'], statut))
        if statut in ('Nouvelle', 'Différée', 'Refusée') and demande['ot_id']:
            erreur('%s %s avec un OT' % (demande['id'], statut))
        if statut in ('Refusée', 'Différée') and not demande['motif_decision']:
            erreur('%s %s sans motif' % (demande['id'], statut))
        if statut != 'Nouvelle' and demande['date_decision'] < demande['date_heure']:
            erreur('%s décidée avant sa création' % demande['id'])
        if demande['date_heure'] > maintenant:
            erreur('%s : date dans le futur' % demande['id'])
    for identifiant, nombre in ouverts_par_gamme.items():              # RG5
        if nombre > 1:
            erreur('%s : %d OT ouverts pour la même gamme' % (identifiant, nombre))
    for gamme in ctx.gammes:
        if gamme['echue'] and not gamme.get('sans_ot') and gamme['id'] not in ouverts_par_gamme:
            erreur('%s échue sans OT ouvert' % gamme['id'])
        if not gamme['echue'] and gamme['id'] in ouverts_par_gamme:
            erreur('%s non échue mais avec un OT ouvert' % gamme['id'])

    # --- 3. Stock (RG6)
    stock_courant = {}
    for mouvement in base['mouvements_stock']:
        article = mouvement['article_id']
        quantite = float(mouvement['quantite'])
        if mouvement['type'] == 'inventaire':
            stock_courant[article] = quantite
        elif mouvement['type'] in ('entrée', 'retour'):
            stock_courant[article] = stock_courant.get(article, 0) + quantite
        else:
            stock_courant[article] = stock_courant.get(article, 0) - quantite
            if not mouvement['ot_id']:
                erreur('%s : sortie non imputée à un OT' % mouvement['id'])
        if stock_courant[article] < 0:
            erreur('%s : stock négatif pour %s' % (mouvement['id'], article))
    sous_le_seuil = 0
    for article in base['articles']:
        if float(article['stock']) != stock_courant.get(article['id'], 0):
            erreur('%s : colonne stock différente du stock recalculé' % article['id'])
        if float(article['stock']) <= float(article['point_commande']):
            sous_le_seuil += 1
    if sous_le_seuil != 3:
        erreur('%d articles sous le point de commande au lieu de 3' % sous_le_seuil)
    pieces_par_ot = {}
    for piece in base['ot_pieces']:
        pieces_par_ot.setdefault(piece['ot_id'], []).append(piece)
    for ot in base['ordres_travail']:                                  # RG3 : Planifié exige les pièces en stock
        if ot['statut'] == 'Planifié':
            for piece in pieces_par_ot.get(ot['id'], []):
                if float(piece['quantite_prevue']) > stock_courant.get(piece['article_id'], 0):
                    erreur('%s planifié alors que la pièce %s manque' % (ot['id'], piece['article_id']))
    recu = {}
    for achat in base['achats']:
        if achat['statut'] == 'reçue':
            recu[achat['article_id']] = recu.get(achat['article_id'], 0) + float(achat['quantite'])
            if not achat['date_reception']:
                erreur('%s reçu sans date de réception' % achat['id'])
    entrees = {}
    for mouvement in base['mouvements_stock']:
        if mouvement['type'] == 'entrée':
            entrees[mouvement['article_id']] = entrees.get(mouvement['article_id'], 0) + float(mouvement['quantite'])
    if recu != entrees:
        erreur('Les achats reçus ne correspondent pas aux entrées de stock')

    # --- 4. Champs du format v2 (ARCHITECTURE.md §14.1, §14.6)
    ordres = {ot['id']: ot for ot in base['ordres_travail']}
    for equipement in base['equipements']:
        if not equipement['valeur_remplacement']:
            erreur('%s sans valeur de remplacement' % equipement['id'])
    origines = set()
    apres_verrou = {di['id'] for di in ctx.di_apres_verrou}           # seules DI admises sans case cochée (§5 ter)
    for demande in base['demandes']:
        ot = ordres.get(demande['ot_id'])
        if demande['symptome_code'] and ot is not None and ot['symptome_code'] != demande['symptome_code']:
            erreur('%s : code symptôme %s différent de celui de %s' % (demande['id'], demande['symptome_code'], ot['id']))
        if demande['ot_origine_id']:
            origine = ordres[demande['ot_origine_id']]
            origines.add(origine['id'])
            # Une DI envoyée quand l'OT d'origine est déjà verrouillé (Clôturé administrativement) ne le
            # marque pas : l'application ne modifie jamais un OT verrouillé (§14.6, écart retenu).
            verrouille = (demande['id'] in apres_verrou and origine['statut'] == 'Clôturé administrativement'
                          and origine['date_cloture_admin'] <= demande['date_heure'])
            if origine['origine'] != 'préventif' or (origine['anomalie_constatee'] != '1' and not verrouille):
                erreur('%s : OT d\'origine %s sans anomalie constatée' % (demande['id'], origine['id']))
    reglees_sur_place = {ot['id'] for ot in ctx.anomalies_sans_di}     # case cochée sans DI (§5 ter)
    for ot in base['ordres_travail']:
        if ot['anomalie_constatee'] == '1' and ot['id'] not in origines and ot['id'] not in reglees_sur_place:
            erreur('%s : anomalie constatée sans DI liée' % ot['id'])
    if erreurs:
        raise ErreurCoherence('\n'.join(erreurs))


# ---------------------------------------------------------------------------
# Auto-vérification du lot 3 : contrôles, planning, journal, pannes (ARCHITECTURE.md §15.12)
# ---------------------------------------------------------------------------

MOTIF_ACTION_STATUT = re.compile(r'statut (.+?) → (.+?)(?: : (.+))?')
MOTIF_ID_JOURNAL = re.compile(r'J-(\d{12})\d{2}-[A-Z0-9]{4}')


def statut_controle(controle, aujourdhui):
    """Statut d'un contrôle réglementaire à une date (§15.7, comme Controles.etat) : le premier vrai parmi
    « en retard », « observations à lever », « à planifier » (30 jours ou moins, ou date inconnue), « à jour »."""
    if controle['prochaine_date']:
        prochaine = jour_depuis_texte(controle['prochaine_date'])
    elif controle['derniere_date'] and controle['periodicite_mois']:
        prochaine = ajouter_mois(jour_depuis_texte(controle['derniere_date']), int(controle['periodicite_mois']))
    else:
        prochaine = None
    if prochaine is not None and prochaine < aujourdhui:
        return 'en retard'
    if controle['observations'].strip() and controle['observations_levees'] != '1':
        return 'observations à lever'
    if prochaine is None or prochaine <= aujourdhui + timedelta(days=30):
        return 'à planifier'
    return 'à jour'


def lundis_du_planning(ctx):
    """Les lundis des 4 semaines du planning de démo (la date de référence est un lundi)."""
    return [ctx.ref + timedelta(weeks=rang) for rang in range(4)]


def semaine_du_planning(ctx, date_prevue):
    """Lundi de la semaine du planning qui contient cette date prévue, ou None (hors des 4 semaines)."""
    if not date_prevue:
        return None
    for lundi in lundis_du_planning(ctx):
        if lundi <= jour_depuis_texte(date_prevue) < lundi + timedelta(days=7):
            return lundi
    return None


def charges_du_planning(ctx):
    """{(technicien, lundi AAAA-MM-JJ): heures prévues} : même règle que Planning.chargeSemaine (§15.5),
    somme des temps prévus des OT ni clôturés ni annulés, avec technicien et date prévue dans la semaine."""
    charges = {}
    for ot in ctx.base['ordres_travail']:
        lundi = semaine_du_planning(ctx, ot['date_prevue'])
        if ot['statut'] not in STATUTS_FERMES and ot['technicien_id'] and lundi:
            cle = (ot['technicien_id'], texte_date(lundi))
            charges[cle] = charges.get(cle, 0.0) + float(ot['temps_prevu_h'] or 0)
    return charges


def surcharges_du_planning(ctx):
    """Couples (technicien, lundi) dont la charge dépasse la capacité hebdomadaire du technicien."""
    capacites = {t['id']: float(t['capacite_h_semaine']) for t in ctx.base['techniciens']}
    return sorted(cle for cle, heures in charges_du_planning(ctx).items() if heures > capacites[cle[0]])


def historiques_du_journal(base):
    """{OT: [entrées du journal de la table ordres_travail]}, triées par date_heure puis identifiant."""
    historiques = {}
    for ligne in sorted(base['journal'], key=lambda l: (l['date_heure'], l['id'])):
        if ligne['table'] == 'ordres_travail':
            historiques.setdefault(ligne['id_ligne'], []).append(ligne)
    return historiques


def attente_pieces(entrees, ot):
    """Heures passées « En attente » pour une pièce (§15.3), lues au journal, sans plafond."""
    total, debut = 0.0, None
    for entree in entrees:
        correspondance = MOTIF_ACTION_STATUT.fullmatch(entree['action'].partition(' — ')[2])
        if not correspondance:
            continue
        depart, arrivee, motif = correspondance.groups()
        if arrivee == 'En attente' and (motif or '').lower().startswith('pièce'):
            debut = instant_depuis_texte(entree['date_heure'])
        elif depart == 'En attente' and debut is not None:
            total += (instant_depuis_texte(entree['date_heure']) - debut).total_seconds() / 3600.0
            debut = None
    if debut is not None and ot['date_fin']:
        total += (instant_depuis_texte(ot['date_fin']) - debut).total_seconds() / 3600.0
    return total


def verifier_historique_ot(ot, entrees, erreur):
    """Un historique au journal : création à date_creation, puis chaque passage part du statut précédent,
    à des heures croissantes égales aux dates de l'OT (démarrage, clôtures), et finit sur son statut."""
    if ot['origine'] == 'DI':
        attendue = 'création — acceptation de ' + ot['di_id']
    else:
        attendue = "création — création de l'OT (%s)" % ot['origine']
    if entrees[0]['action'] != attendue or entrees[0]['date_heure'] != ot['date_creation']:
        erreur('%s : le journal ne commence pas par sa création (%r)' % (ot['id'], entrees[0]['action']))
    statut, precedent, demarre = 'Créé', entrees[0]['date_heure'], False
    dates_attendues = {'Clôturé techniquement': ot['date_cloture_tech'],
                       'Clôturé administrativement': ot['date_cloture_admin']}
    for entree in entrees[1:]:
        correspondance = MOTIF_ACTION_STATUT.fullmatch(entree['action'].partition(' — ')[2])
        if not correspondance or correspondance.group(1) != statut or entree['date_heure'] <= precedent:
            erreur('%s : passage incohérent après « %s » : %r' % (ot['id'], statut, entree['action']))
            return
        statut = correspondance.group(2)
        if statut == 'En cours' and not demarre:
            dates_attendues['En cours'], demarre = ot['date_debut'], True
        if statut in dates_attendues and entree['date_heure'] != dates_attendues.pop(statut):
            erreur('%s : « %s » le %s, différent de la date de l\'OT' % (ot['id'], statut, entree['date_heure']))
        precedent = entree['date_heure']
    if statut != ot['statut']:
        erreur('%s : le journal finit sur « %s », l\'OT est « %s »' % (ot['id'], statut, ot['statut']))


def verifier_demo_lot3(ctx):
    """Auto-vérification des ajouts du lot 3 (jeu de démo seulement). Lève ErreurCoherence."""
    base = ctx.base
    erreurs = []
    erreur = erreurs.append
    # --- 1. Contrôles : prochaine date = dernière + périodicité ; les quatre statuts à la date de référence
    statuts = set()
    for controle in base['controles_reglementaires']:
        attendue = ajouter_mois(jour_depuis_texte(controle['derniere_date']), int(controle['periodicite_mois']))
        if controle['prochaine_date'] != texte_date(attendue):
            erreur('%s : prochaine date différente de dernière + périodicité' % controle['id'])
        statuts.add(statut_controle(controle, ctx.ref))
    if statuts != set(STATUTS_CONTROLE):
        erreur('Contrôles : statuts %s au lieu des quatre' % sorted(statuts))
    # --- 2. Planning des 4 semaines
    ordres = {ot['id']: ot for ot in base['ordres_travail']}
    equipements = {e['id']: e for e in base['equipements']}
    grille = [ot for ot in base['ordres_travail'] if ot['statut'] not in STATUTS_FERMES and ot['technicien_id']
              and semaine_du_planning(ctx, ot['date_prevue'])]
    planifies = [ot for ot in grille if ot['statut'] == 'Planifié']
    if {ot['technicien_id'] for ot in planifies} != {t['id'] for t in base['techniciens']}:
        erreur('Planning : un technicien sans OT planifié')
    if {semaine_du_planning(ctx, ot['date_prevue']) for ot in planifies} != set(lundis_du_planning(ctx)):
        erreur('Planning : une semaine sans OT planifié')
    for ot in grille:
        if float(ot['temps_prevu_h'] or 0) <= 0:
            erreur('%s : dans le planning sans temps prévu' % ot['id'])
        exigees = [h.strip() for h in re.split(r'[,/]', equipements[ot['equipement_id']]['habilitation_requise']) if h.strip()]
        if not all(habilitation_valide(ctx, ot['technicien_id'], h, jour_depuis_texte(ot['date_prevue'])) for h in exigees):
            erreur('%s : technicien non habilité (RG8) dans le planning de démo' % ot['id'])
    if len(surcharges_du_planning(ctx)) != 1:
        erreur('Planning : %r en surcharge au lieu d\'une seule semaine' % surcharges_du_planning(ctx))
    a_planifier = [ot for ot in base['ordres_travail'] if ot['statut'] == 'Préparé'
                   and not (ot['technicien_id'] and semaine_du_planning(ctx, ot['date_prevue']))]
    if not 3 <= len(a_planifier) <= 5:
        erreur('Planning : %d OT « Préparé » à planifier au lieu de 3 à 5' % len(a_planifier))
    stocks = {a['id']: float(a['stock']) for a in base['articles']}
    manques = {}
    for piece in base['ot_pieces']:
        if float(piece['quantite_prevue']) > stocks[piece['article_id']]:
            manques.setdefault(piece['ot_id'], []).append(piece['article_id'])
    roles = {role: ligne['id'] for role, ligne in ctx.marques.items()}
    for role, manque_attendu in (('ot_a_planifier', False), ('ot_a_planifier_br', False),
                                 ('ot_a_planifier_piece_manquante', True)):
        if role in roles and (roles[role] not in [ot['id'] for ot in a_planifier] or bool(manques.get(roles[role])) != manque_attendu):
            erreur('%s : pas un OT « Préparé » à planifier avec ses pièces %s' % (role, 'manquantes' if manque_attendu else 'en stock'))
    # --- 3. Journal : historique de chaque panne récente, cohérent avec les dates de l'OT
    demandes = {d['id']: d for d in base['demandes']}
    demandes_par_ot = {}
    for demande in base['demandes']:
        demandes_par_ot.setdefault(demande['ot_id'], []).append(demande)
    historiques = historiques_du_journal(base)
    for ot in base['ordres_travail']:
        if est_panne(ot) and date_de_panne(ot, demandes, demandes_par_ot) >= debut_historique_statuts(ctx) \
                and ot['id'] not in historiques:
            erreur('%s : panne récente sans historique au journal' % ot['id'])
    for ot_id, entrees in historiques.items():
        verifier_historique_ot(ordres[ot_id], entrees, erreur)
    vus = set()
    for ligne in base['journal']:
        forme = MOTIF_ID_JOURNAL.fullmatch(ligne['id'])
        if not forme or forme.group(1) != re.sub(r'\D', '', ligne['date_heure']) or ligne['id'] in vus:
            erreur('%s : identifiant de journal invalide ou en double' % ligne['id'])
        vus.add(ligne['id'])
        if ligne['date_heure'] > texte_dh(ctx.maintenant):
            erreur('%s : entrée de journal dans le futur' % ligne['id'])
    # --- 4. Pannes remarquables
    if 'panne_attente_pieces' in roles:
        ot = ordres[roles['panne_attente_pieces']]
        attente = attente_pieces(historiques.get(ot['id'], []), ot)
        if not (2 <= attente <= 7 * 24 and attente < float(ot['duree_arret_h'] or 0)):
            erreur('%s : attente de pièce de %.1f h (durée d\'arrêt %s h)' % (ot['id'], attente, ot['duree_arret_h']))
    if 'panne_sans_duree' in roles:
        ot = ordres[roles['panne_sans_duree']]
        if not (est_panne(ot) and ot['statut'].startswith('Clôturé') and ot['duree_arret_h'] == ''):
            erreur('%s : pas une panne clôturée sans durée d\'arrêt' % ot['id'])
    if erreurs:
        raise ErreurCoherence('\n'.join(erreurs[:30]))


def verifier_calcul_main(ctx, scenarios):
    """Rôle equipements_calcul_main (jeu livré, 13 mois) : un équipement de criticité A, heures de
    fonctionnement connues, au moins deux pannes sur les 12 derniers mois chacun ; ensemble, ils portent
    les cas limites (panne non clôturée, sans durée d'arrêt, attente de pièce). Renvoie les erreurs."""
    base = ctx.base
    erreurs = []
    demandes = {d['id']: d for d in base['demandes']}
    demandes_par_ot = {}
    for demande in base['demandes']:
        demandes_par_ot.setdefault(demande['ot_id'], []).append(demande)
    equipements = {e['id']: e for e in base['equipements']}
    debut_12_mois = ajouter_mois(ctx.ref, -12) + timedelta(days=1)
    vues = set()
    for identifiant in scenarios['equipements_calcul_main']:
        pannes = [ot['id'] for ot in base['ordres_travail'] if ot['equipement_id'] == identifiant and est_panne(ot)
                  and debut_12_mois <= date_de_panne(ot, demandes, demandes_par_ot) <= ctx.ref]
        vues.update(pannes)
        if float(equipements[identifiant]['heures_fonct_jour'] or 0) <= 0 or len(pannes) < 2:
            erreurs.append('%s : calcul à la main impossible (%d pannes sur 12 mois)' % (identifiant, len(pannes)))
    if 'A' not in [equipements[identifiant]['criticite'] for identifiant in scenarios['equipements_calcul_main']]:
        erreurs.append('equipements_calcul_main : aucun équipement de criticité A')
    for role in ('ot_p1_ouvert', 'panne_sans_duree', 'panne_attente_pieces'):
        if scenarios.get(role) not in vues:
            erreurs.append('equipements_calcul_main : %s absent de leurs pannes' % role)
    return erreurs


# ---------------------------------------------------------------------------
# 7 bis. Lot 3 bis : règles du préventif suggéré recalculées en Python (ARCHITECTURE.md §16.2 à §16.4)
# ---------------------------------------------------------------------------
# Copie lisible des règles du contrat, pour que le générateur prouve lui-même ses rôles de scénario. Les
# moments sont des textes « AAAA-MM-JJ HH:MM » : « postérieur à » = texte strictement plus grand (§16.2).

SEUIL_PANNES = 3                    # suggestion_seuil_pannes par défaut (§16.1) : S1, S2
VISITES_SANS_CONSTAT = 5            # suggestion_visites_sans_constat par défaut : S4
FENETRE_MOIS = 12                   # suggestion_fenetre_mois par défaut
VISITES_REGARDEES_S3 = 4            # S3 (fixe) : parmi les 4 dernières visites…
ANOMALIES_S3 = 2                    # … au moins 2 avec anomalie
MINIMUM_REFUS_CRITICITE_A = 6       # rôle suggestion_refus_criticite_a : au moins 6 visites de suite sans anomalie
MOTIF_DECISION = re.compile(r'suggestion (S[1-4]-\S+) (ignorée|traitée) : (.*)')     # action entière (§16.4)


def moment_ot(ot):
    """§16.2 : date_fin, sinon date_cloture_tech, sinon date_creation, ramené à « AAAA-MM-JJ HH:MM »."""
    return (ot['date_fin'] or ot['date_cloture_tech'] or ot['date_creation']).replace('T', ' ')[:16]


def jour_ot(ot):
    """Jour du moment d'un OT, ou None si sa date est illisible (l'OT est alors ignoré, §16.2)."""
    try:
        return jour_depuis_texte(moment_ot(ot)[:10])
    except ValueError:
        return None


def decisions_du_journal(base, limite=None):
    """Dernière décision de chaque clé (§16.4) : {clé: ligne du journal + cle, decision, texte}.
    La plus récente l'emporte (date_heure, puis identifiant). limite : décisions antérieures à ce moment."""
    dernieres = {}
    for ligne in sorted(base['journal'], key=lambda entree: (entree['date_heure'], entree['id'])):
        forme = MOTIF_DECISION.fullmatch(ligne['action'])
        if forme and (limite is None or ligne['date_heure'] < limite):
            dernieres[forme.group(1)] = dict(ligne, cle=forme.group(1), decision=forme.group(2), texte=forme.group(3))
    return dernieres


def passage_au_format_2(base):
    """Moment du passage au format 2 (§16.2), ou None : base créée au format 2, comme la démo."""
    lignes = [l for l in base['journal'] if l['table'] == 'parametres' and l['id_ligne'] == 'version_schema'
              and 'passage au format 2 du fichier' in l['action']]
    return max((l['date_heure'], l['id']) for l in lignes)[0] if lignes else None


def calculer_suggestions(base, jour, seuil=SEUIL_PANNES, sans_constat=VISITES_SANS_CONSTAT, fenetre=FENETRE_MOIS,
                         limite=None, criticites=None):
    """Suggestions ouvertes au jour `jour` (date) selon les règles du §16.3 : {clé: suggestion}.

    Suggestion : {regle, equipement, gammes, cause, faits (identifiants d'OT, du plus ancien au plus récent),
    sur (S3 : visites regardées), depuis (moment de la décision précédente ou None)}.
    limite : moment « AAAA-MM-JJ HH:MM » ; seuls les OT, DI et décisions antérieurs comptent (état de la base
    à ce moment). criticites : {équipement: criticité} qui remplace celle du fichier (preuve d'un refus S4)."""
    debut = ajouter_mois(jour, -fenetre) + timedelta(days=1)
    decisions = decisions_du_journal(base, limite)
    format2 = passage_au_format_2(base)
    criticite = {e['id']: (criticites or {}).get(e['id'], e['criticite']) for e in base['equipements']}
    suivis = {e['id'] for e in base['equipements'] if e['actif'] != '0' and e['statut'] != 'rebut'}
    ordres = [o for o in base['ordres_travail']
              if jour_ot(o) is not None and (limite is None or moment_ot(o) <= limite)]
    origines = {d['ot_origine_id'] for d in base['demandes']
                if d['ot_origine_id'] and (limite is None or d['date_heure'] <= limite)}
    actives = [g for g in base['gammes'] if g['actif'] != '0']
    suivies = [g for g in actives if g['declencheur'] in ('date', 'compteur') and g['equipement_id'] in suivis]
    visites = {g['id']: sorted((o for o in ordres if o['gamme_id'] == g['id'] and o['statut'] in STATUTS_CLOTURES
                                and jour_ot(o) <= jour), key=lambda o: (moment_ot(o), o['id'])) for g in suivies}
    correctifs = [o for o in ordres if o['type'] in TYPES_CORRECTIFS and o['statut'] in STATUTS_CLOTURES
                  and o['cause_code'] and debut <= jour_ot(o) <= jour]
    ouvertes = {}

    def apres_decision(cle, ot):
        return cle not in decisions or moment_ot(ot) > decisions[cle]['date_heure']

    def proposer(cle, regle, faits, equipement, gammes, cause='', sur=None):
        ouvertes[cle] = {'regle': regle, 'equipement': equipement, 'gammes': gammes, 'cause': cause,
                         'faits': [o['id'] for o in faits], 'sur': sur,
                         'depuis': decisions[cle]['date_heure'] if cle in decisions else None}

    # S1 (aucune gamme active) et S2 (gammes suivies déjà visitées) : correctifs de même cause.
    for equipement in sorted(suivis):
        if any(g['equipement_id'] == equipement for g in actives):
            regle = 'S2'
            gammes = [g['id'] for g in suivies if g['equipement_id'] == equipement and visites[g['id']]]
            if not gammes:
                continue
            premiere_visite = min(moment_ot(visites[g][0]) for g in gammes)
        else:
            regle, gammes, premiere_visite = 'S1', [], ''
        par_cause = {}
        for ot in correctifs:
            if ot['equipement_id'] == equipement and moment_ot(ot) > premiere_visite:
                par_cause.setdefault(ot['cause_code'], []).append(ot)
        for cause, liste in par_cause.items():
            cle = '%s-%s-%s' % (regle, equipement, cause)
            faits = sorted((ot for ot in liste if apres_decision(cle, ot)), key=lambda o: (moment_ot(o), o['id']))
            if len(faits) >= seuil:
                proposer(cle, regle, faits, equipement, gammes, cause)
    # S3 (anomalies répétées) et S4 (allonger) : visites d'une gamme suivie.
    for gamme in suivies:
        cle = 'S3-' + gamme['id']
        regardees = [ot for ot in visites[gamme['id']] if apres_decision(cle, ot)][-VISITES_REGARDEES_S3:]
        avec_anomalie = [ot for ot in regardees if ot['anomalie_constatee'] == '1' or ot['id'] in origines]
        if len(avec_anomalie) >= ANOMALIES_S3:
            proposer(cle, 'S3', avec_anomalie, gamme['equipement_id'], [gamme['id']], sur=len(regardees))
        cle = 'S4-' + gamme['id']
        comptees = [ot for ot in visites[gamme['id']]
                    if (format2 is None or moment_ot(ot) > format2) and apres_decision(cle, ot)]
        serie = serie_sans_anomalie(comptees, origines)
        if criticite[gamme['equipement_id']] in ('B', 'C') and len(serie) >= sans_constat \
                and not correctifs_depuis(ordres, gamme['equipement_id'], jour_ot(serie[0])):
            proposer(cle, 'S4', serie, gamme['equipement_id'], [gamme['id']])
    return ouvertes


def serie_sans_anomalie(visites, origines):
    """S4 : les dernières visites consécutives sans anomalie (ni case cochée, ni DI liée), dans l'ordre."""
    serie = []
    for ot in reversed(visites):
        if ot['anomalie_constatee'] == '1' or ot['id'] in origines:
            break
        serie.insert(0, ot)
    return serie


def correctifs_depuis(ordres, equipement, premier_jour):
    """S4 : correctifs de l'équipement (tout statut sauf Annulé, toute cause) créés à partir de premier_jour."""
    return [o for o in ordres if o['equipement_id'] == equipement and o['type'] in TYPES_CORRECTIFS
            and o['statut'] != 'Annulé' and o['date_creation'][:10] >= texte_date(premier_jour)]


def verifier_suggestions(ctx, scenarios):
    """Rôles du lot 3 bis prouvés par calculer_suggestions à la date de référence (réglages par défaut,
    décisions du journal comprises). Renvoie la liste des erreurs."""
    base = ctx.base
    erreurs = []
    ouvertes = calculer_suggestions(base, ctx.ref)
    equipements = {e['id']: e for e in base['equipements']}
    ordres = {o['id']: o for o in base['ordres_travail']}

    def ouverte(role, regle, repere=None, cause=None):
        suggestion = ouvertes.get(scenarios[role])
        if suggestion is None or suggestion['regle'] != regle \
                or (repere and equipements[suggestion['equipement']]['repere'] != repere) \
                or (cause and suggestion['cause'] != cause):
            erreurs.append('%s : %s n\'est pas une suggestion %s ouverte (%s %s)' % (role, scenarios[role], regle,
                                                                                  repere or '', cause or ''))
            return None
        return suggestion

    ouverte('suggestion_creer', 'S1', 'CV-02', 'C04')
    ouverte('suggestion_revoir', 'S2', 'PO-02', 'C01')
    ouverte('suggestion_allonger', 'S4', 'VE-01')
    s3 = ouverte('suggestion_anomalies', 'S3')
    if s3:
        erreurs += verifier_cas_anomalies(base, ouvertes, scenarios['suggestion_anomalies'], s3)
    erreurs += verifier_refus_criticite_a(ctx, ouvertes, scenarios['suggestion_refus_criticite_a'])
    erreurs += verifier_sous_seuil(ctx, ouvertes, scenarios['suggestion_sous_seuil'])
    revenue = ouverte('suggestion_ignoree_revenue', DECISION_IGNOREE_DEMO[0], DECISION_IGNOREE_DEMO[1],
                      DECISION_IGNOREE_DEMO[2])
    if revenue:
        erreurs += verifier_ignoree_revenue(ctx, scenarios['suggestion_ignoree_revenue'], revenue)
    for cle, suggestion in ouvertes.items():          # aucun fait ni décision dans le futur
        if any(moment_ot(ordres[ot]) > texte_dh(ctx.maintenant) for ot in suggestion['faits']):
            erreurs.append('%s : un fait est postérieur à la date de référence' % cle)
    return erreurs


def verifier_cas_anomalies(base, ouvertes, cle, suggestion):
    """S3 : criticité B ou C ; 2 anomalies parmi les 4 dernières visites, l'une par la case seule (sans DI),
    l'autre par une DI liée sur une visite verrouillée avant la DI (case à 0) ; aucune autre suggestion sur
    l'équipement ou la gamme."""
    erreurs = []
    equipement = {e['id']: e for e in base['equipements']}[suggestion['equipement']]
    ordres = {o['id']: o for o in base['ordres_travail']}
    liees = {}
    for demande in base['demandes']:
        if demande['ot_origine_id']:
            liees.setdefault(demande['ot_origine_id'], []).append(demande)
    visites = [ordres[identifiant] for identifiant in suggestion['faits']]
    par_case = [v for v in visites if v['anomalie_constatee'] == '1' and v['id'] not in liees]
    par_di = [v for v in visites if v['anomalie_constatee'] == '0' and v['id'] in liees]
    if equipement['criticite'] not in ('B', 'C') or (suggestion['sur'], len(visites)) != (VISITES_REGARDEES_S3, 2):
        erreurs.append('%s : %d anomalies sur %s visites (criticité %s)' % (cle, len(visites), suggestion['sur'],
                                                                         equipement['criticite']))
    if len(par_case) != 1 or len(par_di) != 1:
        erreurs.append('%s : il faut une anomalie par la case seule et une par une DI liée' % cle)
    for visite in par_di:
        for demande in liees[visite['id']]:
            correctif = ordres.get(demande['ot_id'])
            if not (visite['statut'] == 'Clôturé administrativement'
                    and visite['date_cloture_admin'] <= demande['date_heure']
                    and demande['equipement_id'] == visite['equipement_id'] and demande['statut'] == 'Acceptée'
                    and correctif and correctif['statut'] in STATUTS_CLOTURES
                    and correctif['symptome_code'] == demande['symptome_code']):
                erreurs.append('%s : DI liée %s incohérente avec la visite %s' % (cle, demande['id'], visite['id']))
    autres = [c for c, s in ouvertes.items() if c != cle and (s['equipement'] == suggestion['equipement']
                                                             or set(s['gammes']) & set(suggestion['gammes']))]
    if autres:
        erreurs.append('%s : autres suggestions sur le même équipement : %s' % (cle, autres))
    return erreurs


def verifier_refus_criticite_a(ctx, ouvertes, gamme_id):
    """Gamme suivie à date, équipement de criticité A, au moins 6 visites de suite sans anomalie et aucun
    correctif depuis la première : S4 la refuse, et l'ouvrirait si l'équipement était de criticité B."""
    gamme = {g['id']: g for g in ctx.base['gammes']}.get(gamme_id)
    if gamme is None:
        return ['suggestion_refus_criticite_a : gamme %s introuvable' % gamme_id]
    equipement = {e['id']: e for e in ctx.base['equipements']}[gamme['equipement_id']]
    cle = 'S4-' + gamme_id
    sans_criticite = calculer_suggestions(ctx.base, ctx.ref, criticites={equipement['id']: 'B'})
    if (gamme['declencheur'], gamme['actif'], equipement['criticite']) != ('date', '1', 'A') or cle in ouvertes \
            or cle not in sans_criticite or len(sans_criticite[cle]['faits']) < MINIMUM_REFUS_CRITICITE_A:
        return ['suggestion_refus_criticite_a : %s ne remplit pas S4 à la seule criticité A près' % gamme_id]
    return []


def verifier_sous_seuil(ctx, ouvertes, cas):
    """Équipement sans gamme active, exactement seuil - 1 correctifs de la cause dans la fenêtre : S1 n'est
    pas ouverte, et le serait avec un seuil abaissé d'un cran."""
    cle = 'S1-%s-%s' % (cas['equipement'], cas['cause'])
    debut = ajouter_mois(ctx.ref, -FENETRE_MOIS) + timedelta(days=1)
    nombre = len([o for o in ctx.base['ordres_travail'] if o['equipement_id'] == cas['equipement']
                  and o['type'] in TYPES_CORRECTIFS and o['statut'] in STATUTS_CLOTURES
                  and o['cause_code'] == cas['cause'] and jour_ot(o) and debut <= jour_ot(o) <= ctx.ref])
    actives = [g for g in ctx.base['gammes'] if g['equipement_id'] == cas['equipement'] and g['actif'] != '0']
    if actives or nombre != SEUIL_PANNES - 1 or cle in ouvertes \
            or cle not in calculer_suggestions(ctx.base, ctx.ref, seuil=SEUIL_PANNES - 1):
        return ['suggestion_sous_seuil : %s (%d correctifs, %d gammes actives)' % (cle, nombre, len(actives))]
    return []


def verifier_ignoree_revenue(ctx, cle, suggestion):
    """Dernière décision de la clé « ignorée » avec un motif, écrite comme Donnees.journaliser (§16.4) ; la
    suggestion était ouverte au moment de la décision ; au moins seuil faits postérieurs l'ont rouverte."""
    decision = decisions_du_journal(ctx.base).get(cle)
    if decision is None or decision['decision'] != 'ignorée' or not decision['texte'].strip() \
            or len(decision['texte']) > 300 or '\n' in decision['texte']:
        return ['suggestion_ignoree_revenue : %s sans décision « ignorée » avec motif' % cle]
    erreurs = []
    if (decision['table'], decision['id_ligne'], decision['profil'], decision['poste']) \
            != ('equipements', suggestion['equipement'], 'Responsable', POSTE_DEMO):
        erreurs.append('suggestion_ignoree_revenue : ligne de journal %s mal formée' % decision['id'])
    if suggestion['depuis'] != decision['date_heure'] or len(suggestion['faits']) < SEUIL_PANNES:
        erreurs.append('suggestion_ignoree_revenue : %d faits depuis la décision' % len(suggestion['faits']))
    avant = calculer_suggestions(ctx.base, jour_depuis_texte(decision['date_heure'][:10]), limite=decision['date_heure'])
    if cle not in avant:
        erreurs.append('suggestion_ignoree_revenue : %s n\'était pas ouverte quand elle a été ignorée' % cle)
    return erreurs


# ---------------------------------------------------------------------------
# Identifiants de scénario (tests/fixtures/demo-scenarios.json, ARCHITECTURE.md §14.8)
# ---------------------------------------------------------------------------

STATUTS_FERMES = ('Clôturé techniquement', 'Clôturé administrativement', 'Annulé')

# Équipement et symptôme de chaque cas de « causes fréquentes » (ARCHITECTURE.md §14.5).
CAUSES_DEMO = {'causes_equipement': ('PO-02', 'S01'), 'causes_equipement_2': ('CP-01', 'S04'),
               'causes_modele': ('CV-03', 'S05'), 'causes_insuffisantes': ('PO-03', 'S02')}
MINIMUM_CAUSES = 5
# Lot 3 bis (§16.8) : suggestions S1 / S2 de la démo, (règle, repère, cause) ; cas « sous le seuil ».
SUGGESTIONS_DEMO = {'suggestion_creer': ('S1', 'CV-02', 'C04'), 'suggestion_revoir': ('S2', 'PO-02', 'C01'),
                    'suggestion_ignoree_revenue': DECISION_IGNOREE_DEMO}
SOUS_SEUIL_DEMO = ('CP-01.SEC', 'C05')


def cles_documentees():
    """Clés de scénario décrites dans la docstring du module (section « Identifiants de scénario »)."""
    section = __doc__.split('Identifiants de scénario', 1)[1].split('Organisation du fichier', 1)[0]
    return re.findall(r'^    ([a-z0-9_]+) {2,}\S', section, re.MULTILINE)


def cas_causes(base, equipements, symptome):
    """OT comptés par l'encart des causes fréquentes : correctifs clôturés de ce symptôme, cause renseignée."""
    return [o for o in base['ordres_travail']
            if o['equipement_id'] in equipements and o['type'].startswith('correctif')
            and o['statut'].startswith('Clôturé') and o['symptome_code'] == symptome and o['cause_code']]


def equipements_du_modele(base, equipement):
    """Identifiants des équipements de même marque et même modèle (casse ignorée), lui compris."""
    cle = (equipement['marque'].strip().lower(), equipement['modele'].strip().lower())
    return {e['id'] for e in base['equipements'] if (e['marque'].strip().lower(), e['modele'].strip().lower()) == cle}


def scenarios_du_jeu(ctx):
    """Identifiants des objets de scénario (voir la docstring du module), après attribution des
    identifiants. Les rôles marqués pendant la génération sont complétés par des recherches."""
    base = ctx.base
    scenarios = {role: ligne['id'] for role, ligne in ctx.marques.items()}
    ordres = base['ordres_travail']
    ouverts = [o for o in ordres if o['statut'] not in STATUTS_FERMES]
    scenarios['ot_en_retard'] = sorted(o['id'] for o in ouverts if o['date_prevue'] and o['date_prevue'] < DATE_REFERENCE)
    techniques = [o for o in ordres if o['statut'] == 'Clôturé techniquement']
    scenarios['ot_statut_cloture_technique'] = max(techniques, key=lambda o: (o['date_cloture_tech'], o['id']))['id']
    administratifs = [o for o in ordres if o['statut'] == 'Clôturé administrativement']
    scenarios['ot_statut_cloture_administratif'] = max(
        administratifs, key=lambda o: (o['date_cloture_admin'], o['id']))['id']
    preventifs = [o for o in ordres if o['origine'] == 'préventif' and o['statut'].startswith('Clôturé')]
    scenarios['ot_preventif_cloture'] = min(preventifs, key=lambda o: (o['date_creation'], o['id']))['id']
    acceptees = [d for d in base['demandes'] if d['statut'] == 'Acceptée' and d['ot_id']]     # ordre chronologique
    scenarios['di_statut_acceptee'] = acceptees[0]['id']
    scenarios['ot_de_di_acceptee'] = acceptees[0]['ot_id']
    scenarios['di_acceptee_autre'] = acceptees[1]['id']
    scenarios['di_plus_ancienne'] = min(d['id'] for d in base['demandes'])
    scenarios['di_nouvelles'] = sorted(d['id'] for d in base['demandes'] if d['statut'] == 'Nouvelle')
    scenarios['kit_garniture'] = ctx.articles['kit_gar_po02']['id']
    scenarios['articles_sous_point_commande'] = sorted(
        a['id'] for a in base['articles'] if float(a['stock']) <= float(a['point_commande']))
    for statut, role, position in (('demandée', 'achat_statut_demandee', 0), ('commandée', 'achat_statut_commandee', 0),
                                   ('reçue', 'achat_statut_recue', -1)):
        scenarios[role] = [a for a in base['achats'] if a['statut'] == statut][position]['id']
    scenarios['equipement_br'] = ctx.equipement['AE-03']['id']
    scenarios['equipement_panne_unique'] = ctx.equipement['BA-01']['id']
    scenarios['technicien_br_valide'] = ctx.techniciens[0]['id']
    scenarios['technicien_br_echue'] = ctx.techniciens[3]['id']
    for role, (repere, symptome) in CAUSES_DEMO.items():
        scenarios[role] = ctx.equipement[repere]['id']
        scenarios[role + '_symptome'] = symptome
    # Lot 3 : un contrôle par statut à la date de référence (le premier dans l'ordre du fichier), la
    # seule surcharge du planning, les équipements du calcul à la main (liste triée).
    for statut, role in zip(STATUTS_CONTROLE, ('controle_en_retard', 'controle_observations',
                                               'controle_a_planifier', 'controle_a_jour')):
        scenarios[role] = [c['id'] for c in base['controles_reglementaires'] if statut_controle(c, ctx.ref) == statut][0]
    reserves = {r['texte']: r for r in base['reserves_controle']}
    scenarios['reserve_en_retard'] = [r['id'] for r in base['reserves_controle']
                                      if r['controle_id'] == scenarios['controle_observations']][0]
    scenarios['controle_reserves'] = reserves[RESERVES_AE01[0]['texte']]['controle_id']
    scenarios['reserve_levee'] = reserves[RESERVES_AE01[0]['texte']]['id']
    scenarios['reserve_a_echeance'] = reserves[RESERVES_AE01[1]['texte']]['id']
    surcharge = surcharges_du_planning(ctx)[0]          # la seule (vérifié par verifier_demo_lot3)
    scenarios['technicien_surcharge'], scenarios['semaine_surcharge'] = surcharge
    scenarios['equipements_calcul_main'] = sorted(ctx.equipement[repere]['id'] for repere in EQUIPEMENTS_CALCUL_MAIN)
    # Lot 3 bis : clés des suggestions (§16.2) ; suggestion_refus_criticite_a est marqué à la création de sa gamme.
    for role, (regle, repere, cause) in SUGGESTIONS_DEMO.items():
        scenarios[role] = '%s-%s-%s' % (regle, ctx.equipement[repere]['id'], cause)
    scenarios['suggestion_anomalies'] = 'S3-' + ctx.gammes_lot3bis['anomalies']['id']
    scenarios['suggestion_allonger'] = 'S4-' + ctx.marques['gamme_sans_constat']['id']
    repere, cause = SOUS_SEUIL_DEMO
    scenarios['suggestion_sous_seuil'] = {'equipement': ctx.equipement[repere]['id'], 'cause': cause}
    return scenarios


def verifier_scenarios(ctx, scenarios):
    """Auto-vérification des scénarios qui dépendent des tirages au hasard (causes fréquentes) et de la
    liste des clés (exactement celles de la docstring). Lève ErreurCoherence."""
    base = ctx.base
    erreurs = []
    documentees = cles_documentees()
    if sorted(documentees) != sorted(scenarios):
        erreurs.append('Clés de scénario non documentées ou absentes : %s'
                       % sorted(set(documentees) ^ set(scenarios)))
    equipements = {e['id']: e for e in base['equipements']}

    def compter(role):
        identifiant, symptome = scenarios[role], scenarios[role + '_symptome']
        propres = cas_causes(base, {identifiant}, symptome)
        modele = cas_causes(base, equipements_du_modele(base, equipements[identifiant]), symptome)
        return propres, modele

    for role in ('causes_equipement', 'causes_equipement_2'):
        propres, _ = compter(role)
        if len(propres) < MINIMUM_CAUSES:
            erreurs.append('%s : %d cas seulement' % (role, len(propres)))
    propres, _ = compter('causes_equipement')
    causes = {}
    for ot in propres:
        causes[ot['cause_code']] = causes.get(ot['cause_code'], 0) + 1
    if len(causes) < 2 or max(causes, key=lambda code: (causes[code], code == 'C01')) != 'C01':
        erreurs.append('causes_equipement : causes %r (au moins deux, garniture usée en tête)' % causes)
    propres, modele = compter('causes_modele')
    if not 1 <= len(propres) < MINIMUM_CAUSES or len(modele) < MINIMUM_CAUSES:
        erreurs.append('causes_modele : %d cas propres, %d avec le modèle' % (len(propres), len(modele)))
    propres, modele = compter('causes_insuffisantes')
    if not 1 <= len(modele) < MINIMUM_CAUSES or len(propres) != len(modele):
        erreurs.append('causes_insuffisantes : %d cas propres, %d avec le modèle' % (len(propres), len(modele)))
    avec_code = [d for d in base['demandes'] if d['symptome_code']]
    if not 0.7 <= len(avec_code) / float(len(base['demandes'])) <= 0.9:
        erreurs.append('%d DI sur %d avec un code symptôme (environ 80 %% attendus)' % (len(avec_code), len(base['demandes'])))
    erreurs += verifier_calcul_main(ctx, scenarios)
    erreurs += verifier_suggestions(ctx, scenarios)
    if erreurs:
        raise ErreurCoherence('\n'.join(erreurs))


# ---------------------------------------------------------------------------
# Lot 6 (ARCHITECTURE.md §20.10) : astuces des OT (D110) et deux OT de scénario qui contredisent ce que
# l'atelier croyait (D109), pour le wiki de maintenance
# ---------------------------------------------------------------------------

# Astuces « pour la prochaine fois » (lot 6, D110), par titre de scénario : ce qu'un technicien aurait aimé savoir
# avant d'intervenir. Jamais de consigne de sécurité ni de consignation (elles restent dans la fiche de
# l'équipement) : le vocabulaire de la sécurité du wiki y est interdit (test_demo le vérifie).
ASTUCES = {
    'Fuite à la garniture mécanique': [
        "Nettoyer les faces de frottement de la garniture neuve juste avant le montage : une poussière suffit à la faire fuir.",
        "Prévoir deux joints toriques de rechange : ceux du kit se pincent facilement au remontage.",
        "Repérer la position du grain fixe au feutre avant la dépose : le remontage est deux fois plus rapide.",
    ],
    'Fuite au raccord de refoulement': [
        "Serrer la bride en croix en trois passes, puis poser un trait de vernis témoin pour voir tout de suite si elle bouge.",
        "Regarder aussi les supports de tuyauterie : c'est leur jeu qui desserre la bride.",
    ],
    'Bruit anormal, roulement à remplacer': [
        "Chauffer le roulement neuf à l'inducteur plutôt que de le frapper : la piste ne se marque pas.",
        "Noter le relevé de vibrations avant et après : il sert de référence au prochain contrôle.",
    ],
    'Vibrations anormales, resserrage': [
        "Après resserrage, refaire un contrôle au bout d'une semaine : les vis de l'accouplement reprennent du jeu.",
    ],
    'Pression basse en sortie de pompe': [
        "Commencer par la crépine d'aspiration : c'est elle dans la plupart des cas, avant de démonter la pompe.",
    ],
    'Arrêts intempestifs, capteur à nettoyer': [
        "Nettoyer la face du capteur au chiffon sec puis au nettoyant contacts : l'eau laisse un film qui fausse la détection.",
        "Après nettoyage, contrôler la distance de détection avec une pièce de la production, pas avec la main.",
        "Le capteur d'entrée s'encrasse plus vite que les autres : le regarder en premier.",
    ],
    'Bruit de roulement, graissage insuffisant': [
        "Un coup de pompe à graisse suffit sur chaque palier : trop de graisse fait chauffer le roulement.",
    ],
    'Courroie qui patine': [
        "Régler la tension au tensiomètre et noter la valeur sur le carter : la prochaine fois, il suffit de la reprendre.",
    ],
    'Ne démarre pas, contacteur à remplacer': [
        "Vérifier d'abord la bobine au multimètre : si elle est bonne, ce sont souvent les contacts collés.",
        "Garder un contacteur de rechange au magasin : c'est la panne qui immobilise le plus longtemps.",
    ],
    "Vibration du tambour d'entraînement": [
        "Remplacer les deux roulements du tambour en même temps : le second lâche peu après.",
    ],
    'Échauffement du compresseur, filtre colmaté': [
        "Écrire la date de pose au marqueur sur le filtre neuf : on voit tout de suite depuis quand il est en place.",
        "Noter la température de refoulement avant l'intervention : elle montre si c'était bien le filtre.",
    ],
    "Échauffement, niveau d'huile bas": [
        "Faire l'appoint avec la même huile que celle en place : un mélange mousse et fait remonter la température.",
    ],
    "Chute de pression du réseau d'air": [
        "Chercher la fuite au détecteur à ultrasons à l'arrêt de la production : on l'entend beaucoup mieux.",
    ],
    "Fuite d'huile hydraulique": [
        "Poser une gaine de protection sur le flexible neuf là où il frotte : c'est toujours au même endroit qu'il se perce.",
        "Mesurer la longueur du flexible sur l'ancien avant de le jeter : le magasin a deux longueurs proches.",
    ],
    'Pression hydraulique basse': [
        "Changer la cartouche avant que l'indicateur de colmatage soit au rouge : la pompe souffre moins.",
    ],
    'Pièces hors cote à la presse': [
        "Valider le réglage sur trois pièces témoins de la même série, pas sur une seule.",
    ],
    'Défaut de cotes sur les pièces usinées': [
        "Contrôler le zéro pièce avant de toucher aux correcteurs d'outil : c'est lui qui dérive le plus souvent.",
    ],
    'Fuite de liquide de coupe': [
        "Remplacer le raccord en même temps que le flexible d'arrosage : le vieux raccord fuit au remontage.",
    ],
    'Machine en défaut après fausse manœuvre': [
        "Faire refaire le référencement des axes par le conducteur avec vous : il saura le faire la prochaine fois.",
    ],
    'Odeur de brûlé, contacteur à remplacer': [
        "Resserrer toutes les bornes du départ en même temps que le contacteur : l'échauffement vient souvent d'une borne.",
    ],
    'Départ moteur qui ne démarre pas': [
        "Regarder le fusible de commande avant de démonter le contacteur.",
    ],
    'Déclenchements dus à une connexion desserrée': [
        "Une thermographie rapide de l'armoire en marche montre la borne qui chauffe en deux minutes.",
    ],
    'Bruit de courroie de ventilateur': [
        "Aligner les poulies à la règle avant de retendre : une courroie mal alignée se vitrifie.",
    ],
    "Débit d'air faible, filtres colmatés": [
        "Noter la perte de charge relevée au manomètre : elle dit quand changer les filtres la prochaine fois.",
    ],
    'Haute pression et échauffement du groupe froid': [
        "Nettoyer le condenseur de l'intérieur vers l'extérieur : la poussière ne s'enfonce pas dans les ailettes.",
    ],
    'Arrêts intempestifs, fin de course encrassé': [
        "Après nettoyage, faire un cycle complet à vide : un fin de course mal réglé ne se voit qu'en fin de course.",
    ],
    'Bruit de grincement, graissage': [
        "Graisser la chaîne sur toute sa longueur en déplaçant le chariot : les maillons du milieu sont toujours secs.",
    ],
    'Roue ou galet cassé': [
        "Contrôler l'axe du galet en même temps : un axe usé casse le galet neuf.",
    ],
    'Défaut de qualité de soudure ou de pose': [
        "Faire valider la température de soudure sur dix colis témoins avant de relancer la ligne.",
    ],
    'Arrêts intempestifs, cellule encrassée': [
        "Nettoyer le réflecteur en même temps que la cellule : on l'oublie et le défaut revient.",
    ],
    'Bruit de courroie': [
        "Repérer la tension sur le carter après réglage : elle évite de retendre à l'oreille.",
    ],
    "Manque de pression d'air": [
        "Changer le raccord avec le flexible : c'est souvent à la sertissure que l'air fuit.",
    ],
}

PART_OT_AVEC_ASTUCE = 1 / 3          # environ un OT correctif clôturé sur trois porte une astuce

# Les deux OT de scénario (D109) : (repère, jours avant la référence, scénario, astuce), dans l'ordre des dates
# (leurs numéros suivent). CP-01 tombe avant les deux dernières semaines (sa contradiction est ouverte sur la
# page) ; PO-02 dedans (sa proposition reste « à valider » dans le wiki de démo).
SCENARIOS_CONTRADICTOIRES = [
    ('CP-01', 25, scenario(
        'S04', 'C99', 'R03', 1, [MECA, POLY], (1.5, 2.5), (('arrêt', 1),), (),
        'Échauffement du compresseur, cause trouvée',
        "Rechercher pourquoi le compresseur chauffe encore avec un filtre à huile neuf.",
        ['Le compresseur {rep} chauffe de nouveau, le filtre a pourtant été changé.'],
        ["Échauffement avec un filtre à huile propre : ce n'est pas le filtre. Le radiateur d'huile est "
         "colmaté par la poussière et l'huile ; nettoyé au dégraissant puis soufflé, température de "
         "refoulement revenue à 80 °C après 1 h en charge."]),
     "Quand le compresseur chauffe, regarder le radiateur d'huile avant de changer le filtre : s'il est gras, "
     "c'est lui."),
    ('PO-02', 9, scenario(
        'S01', 'C11', 'R02', 1, [MECA, POLY], (2.0, 3.0), (('dégradé', 1),), (),
        'Fuite à la garniture mécanique, cause trouvée',
        "Rechercher la cause des fuites répétées de la garniture : alignement, vibrations, qualité de l'eau.",
        ["La pompe {rep} fuit encore à l'arbre, alors que sa garniture vient d'être changée."],
        ["Fuite naissante à la garniture. Contrôle de l'alignement au comparateur : accouplement désaligné de "
         "0,4 mm, c'est lui qui use la garniture, pas l'usure normale. Accouplement réaligné et calé ; la "
         "garniture, peu marquée, est gardée : plus de fuite après rodage, à contrôler dans un mois."]),
     "Contrôler l'alignement de l'accouplement au comparateur à chaque garniture : 0,4 mm de désalignement "
     "suffit à user une garniture neuve en deux mois."),
]


def ajouter_ot_de_scenario_lot6(ctx):
    """Les deux OT de scénario du wiki (D109), créés après la numérotation de l'historique : ils prennent les
    numéros suivants (DI, OT, temps), aucun autre numéro ne bouge. Clôturés administrativement (le wiki ne
    lit que ceux-là), sans pièce sortie (le stock du jeu ne change pas)."""
    tables = ('demandes', 'ordres_travail', 'ot_temps', 'ot_pieces', 'ot_operations')
    deja = {table: len(ctx.base[table]) for table in tables}
    ctx.ot_scenario_lot6 = []
    for repere, jours, scenario_, astuce in SCENARIOS_CONTRADICTOIRES:
        jour = jour_ouvre_avant(ctx.ref - timedelta(days=jours))
        _, ot = creer_correctif(ctx, ctx.equipement[repere], scenario_, heure_aleatoire(ctx.rng, jour, 7.5, 9.0),
                                scenario_['impacts'][0][0], 'clos', pieces=[], heures=quart_heure(sum(scenario_['duree']) / 2.0),
                                symptome_code=scenario_['symptome'], description='Problème déjà signalé plusieurs fois.')
        fin_technique = instant_depuis_texte(ot['date_cloture_tech'])
        admin = instant(jour_ouvre_apres(fin_technique.date() + timedelta(days=1)), 9.0)
        renseigner(ot, statut='Clôturé administrativement', date_cloture_admin=texte_dh(min(admin, ctx.maintenant)),
                   astuce=astuce)
        ctx.ot_scenario_lot6.append(ot)
    for table in tables:
        for ligne in ctx.base[table][deja[table]:]:
            if ligne['id']:
                continue
            champ_date = {'demandes': 'date_heure', 'ordres_travail': 'date_creation'}.get(table)
            ligne['id'] = nouvel_identifiant(ctx, table, int(ligne[champ_date][:4]) if champ_date else None)


def poser_astuces_lot6(ctx):
    """Astuces (D110) sur environ un OT correctif clôturé sur trois, tirées parmi celles de son scénario (titre de
    l'OT après le repère) ; ordre des OT par identifiant, tirages du générateur du lot 6 seulement."""
    for ot in sorted(ctx.base['ordres_travail'], key=lambda ligne: ligne['id']):
        if ot.get('astuce') or not ot['type'].startswith('correctif') or not ot['statut'].startswith('Clôturé'):
            continue
        titre = ot['titre'].split(' — ', 1)[-1]
        if titre in ASTUCES and ctx.rng.random() < PART_OT_AVEC_ASTUCE:
            renseigner(ot, astuce=ctx.rng.choice(ASTUCES[titre]))


# ---------------------------------------------------------------------------
# Construction complète et ligne de commande
# ---------------------------------------------------------------------------

FICHIERS_WIKI_FIGES = (('wiki_pages', 'demo_wiki_pages.csv'), ('wiki_journal', 'demo_wiki_journal.csv'))
AVIS_WIKI_VIDE = ('Wiki de démo non repris pour %s : le wiki figé (outils/demo_wiki_pages.csv, demo_wiki_journal.csv) '
                  'ne vaut que pour la démo standard (%d mois, sans --volume) ; tables du wiki vides.' % ('%s', MOIS_PAR_DEFAUT))


def lire_valeur(champ, valeur):
    """Valeur lue dans un CSV écrit par Prévo : apostrophe de protection retirée (inverse de ecrire_valeur)."""
    if valeur.startswith("'") and a_proteger(champ['type'], champ['protege'], valeur[1:]):
        return valeur[1:]
    return valeur


def charger_wiki_fige(ctx, dossier):
    """Tables du wiki de démo (§20.10) : les fichiers figés par outils/wiki_demo.py, jamais régénérés (absents :
    tables vides). Contrôle : OT cités, OT des entrées et pages liées existants, sinon arrêt."""
    for table, nom in FICHIERS_WIKI_FIGES:
        chemin = Path(dossier) / nom
        if not chemin.is_file():
            continue
        lignes = list(csv.reader(io.StringIO(chemin.read_bytes().decode('utf-8-sig'), newline=''), delimiter=';'))
        if not lignes or lignes[0] != [champ['nom'] for champ in CHAMPS[table]]:
            raise ErreurCoherence('%s : en-tête différent du schéma de %s' % (chemin, table))
        ctx.base[table] = [{champ['nom']: lire_valeur(champ, valeur) for champ, valeur in zip(CHAMPS[table], ligne)}
                           for ligne in lignes[1:]]
    ordres = {ot['id'] for ot in ctx.base['ordres_travail']}
    # Une panne (refonte 2, §20.12) se lie par « PANNE- » + son code symptôme encodé comme encodeURIComponent.
    pannes = {'PANNE-' + urllib.parse.quote(c['code'], safe="-_.!~*'()") for c in ctx.base['codes_defaillance']
              if c['famille'] == 'symptôme'}
    cibles = {'EQ-': {e['id'] for e in ctx.base['equipements']}, 'ART-': {a['id'] for a in ctx.base['articles']},
              'WP-': {p['id'] for p in ctx.base['wiki_pages'] if p['statut'] != 'archivée'}, 'PANNE-': pannes}
    erreurs = []
    for page in ctx.base['wiki_pages']:
        erreurs += ['%s : OT cité inexistant %s' % (page['id'], ot) for ot in page['ot_cites'].split(';') if ot and ot not in ordres]
        erreurs += ['%s : page liée inexistante %s' % (page['id'], lien) for lien in page['liens'].split(';')
                    if lien and not any(lien.startswith(debut) and lien in ids for debut, ids in cibles.items())]
    erreurs += ['%s : OT inexistant %s' % (e['id'], e['ot_id']) for e in ctx.base['wiki_journal'] if e['ot_id'] and e['ot_id'] not in ordres]
    fins = {ot['id']: ot['date_fin'] for ot in ctx.base['ordres_travail']}
    erreurs += ['%s : date d\'intervention %s, l\'OT %s a fini le %s' % (e['id'], e['date_intervention'], e['ot_id'], fins[e['ot_id']])
                for e in ctx.base['wiki_journal']
                if e['nature'] == 'ingestion' and e['ot_id'] in fins and e['date_intervention'] != fins[e['ot_id']]]
    if erreurs:
        raise ErreurCoherence('Wiki de démo figé incohérent :\n' + '\n'.join(erreurs))


def construire_jeu(mois=MOIS_PAR_DEFAUT, volume=None, dossier_wiki=None):
    """Construit toutes les tables en mémoire (liste de dictionnaires) et vérifie leur cohérence."""
    ctx = Contexte(mois, volume)
    generer_localisations(ctx)
    generer_codes_defaillance(ctx)
    generer_fournisseurs(ctx)
    generer_techniciens(ctx)
    generer_equipements(ctx)
    generer_articles(ctx)
    preparer_gammes_et_compteurs(ctx)
    generer_compteurs_et_releves(ctx)
    generer_gammes(ctx)
    generer_controles(ctx)
    generer_reserves(ctx)
    generer_preventifs(ctx)
    generer_ot_reglementaires_et_ameliorations(ctx)
    if volume:
        generer_pannes_de_fond(ctx, cible_ot=volume[1])
    else:
        evenements_fixes_demo(ctx)
        etat_courant_demo(ctx)
        taux_total = sum(e['taux'] for e in ctx.equipements if e['famille'] in SCENARIOS)
        generer_pannes_de_fond(ctx, nombre=int(round(taux_total * FACTEUR_TAUX_DEMO * mois)))
        with hasard_du_lot3(ctx):
            completer_demo_lot3(ctx)
        with hasard_du_lot3bis(ctx):
            completer_demo_lot3bis(ctx)
    attribuer_identifiants_historique(ctx)
    generer_reserves_ae01(ctx)
    if not volume:
        with hasard_du_lot6(ctx):
            ajouter_ot_de_scenario_lot6(ctx)
            poser_astuces_lot6(ctx)
    construire_stock(ctx)
    generer_liens_article_equipement(ctx)
    generer_parametres(ctx)
    resoudre_references(ctx)
    if not volume:                    # le jeu de charge garde un journal vide
        scenario_lot6 = {id(ot) for ot in ctx.ot_scenario_lot6}
        with hasard_du_lot3(ctx):
            generer_journal(ctx, garder=lambda ot: id(ot) not in scenario_lot6)
        with hasard_du_lot3bis(ctx):
            ajouter_decision_ignoree(ctx)
        with hasard_du_lot6(ctx):
            generer_journal(ctx, garder=lambda ot: id(ot) in scenario_lot6)
        ctx.base['journal'].sort(key=lambda entree: (entree['date_heure'], entree['id']))
    # Le wiki figé a été fabriqué sur la démo standard (ses OT, leurs numéros et leurs dates) : une autre durée
    # d'historique ou le jeu de charge garde les tables du wiki vides (§20.12, D115).
    if not volume and mois == MOIS_PAR_DEFAUT:
        charger_wiki_fige(ctx, dossier_wiki or DOSSIER_WIKI_FIGE)
    else:
        ctx.avis_wiki = AVIS_WIKI_VIDE % ('le jeu de charge' if volume else '%d mois d\'historique' % mois)
    verifier_jeu(ctx)
    if not volume:
        verifier_demo_lot3(ctx)
    return ctx


def lire_arguments(argv):
    analyseur = argparse.ArgumentParser(
        description="Génère le jeu de démo de Prévo (donnees/demo/*.csv, js/demo-donnees.js et "
                    "tests/fixtures/demo-scenarios.json).")
    analyseur.add_argument('--mois', type=int, default=None,
                           help="durée de l'historique en mois (défaut : %d, ou 24 avec --volume)" % MOIS_PAR_DEFAUT)
    analyseur.add_argument('--volume', metavar='EQUIPEMENTS,OT', default=None,
                           help='jeu de charge, ex. 500,5000 (exige --sortie)')
    analyseur.add_argument('--sortie', metavar='DOSSIER', default=None,
                           help='dossier des CSV (défaut : donnees/demo ; dans ce cas js/demo-donnees.js et '
                                'tests/fixtures/demo-scenarios.json sont aussi écrits)')
    analyseur.add_argument('--sans-js', action='store_true', help="n'écrit pas js/demo-donnees.js")
    analyseur.add_argument('--wiki', metavar='DOSSIER', default=None,
                           help='dossier des fichiers figés du wiki de démo (défaut : outils)')
    analyseur.add_argument('--fichier-js', metavar='CHEMIN', default=None,
                           help="écrit le fichier JavaScript à cet emplacement (utile aux tests)")
    analyseur.add_argument('--fichier-scenarios', metavar='CHEMIN', default=None,
                           help="écrit les identifiants de scénario à cet emplacement (utile aux tests)")
    arguments = analyseur.parse_args(argv)
    if arguments.volume:
        try:
            nombre_equipements, nombre_ot = [int(morceau) for morceau in arguments.volume.split(',')]
        except ValueError:
            analyseur.error('--volume attend deux nombres : EQUIPEMENTS,OT (ex. 500,5000)')
        if nombre_equipements < 40 or nombre_ot < 200:
            analyseur.error('--volume : au moins 40 équipements et 200 OT')
        if not arguments.sortie:
            analyseur.error('--volume exige --sortie DOSSIER (pour ne pas écraser le jeu de démo)')
        if arguments.fichier_scenarios:
            analyseur.error("--fichier-scenarios : le jeu de charge n'a pas d'identifiants de scénario")
        arguments.volume = (nombre_equipements, nombre_ot)
    if arguments.mois is None:
        arguments.mois = 24 if arguments.volume else MOIS_PAR_DEFAUT
    if not 1 <= arguments.mois <= 60:
        analyseur.error('--mois doit être compris entre 1 et 60')
    return arguments


def principal(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    arguments = lire_arguments(argv)
    depart = time.time()
    ctx = construire_jeu(arguments.mois, arguments.volume, arguments.wiki)
    textes = {table: serialiser_table(table, ctx.base[table]) for table in NOMS_TABLES}
    dossier = Path(arguments.sortie) if arguments.sortie else DOSSIER_DEMO
    fichier_js = Path(arguments.fichier_js) if arguments.fichier_js else (
        FICHIER_JS if not arguments.sans_js and not arguments.sortie else None)
    octets = octets_js(textes) if fichier_js else None
    # La démo (pas le jeu de charge) se charge vite : au-delà de 1 Mo, rien n'est écrit (CS105).
    if octets is not None and not arguments.volume and len(octets) > TAILLE_JS_MAX:
        raise ErreurCoherence('%s : %d octets, %d au plus (CS105 : chargement rapide de la démo)'
                              % (fichier_js.name, len(octets), TAILLE_JS_MAX))
    ecrire_csv(dossier, textes)
    if fichier_js:
        ecrire_js(fichier_js, textes, octets)
    # Les identifiants de scénario ne valent que pour le jeu de démo livré (donnees/demo) : ils sont
    # calculés et vérifiés seulement quand on les écrit.
    if arguments.fichier_scenarios or not arguments.sortie:
        scenarios = scenarios_du_jeu(ctx)
        verifier_scenarios(ctx, scenarios)
        ecrire_scenarios(Path(arguments.fichier_scenarios) if arguments.fichier_scenarios else FICHIER_SCENARIOS,
                         scenarios)
    print('Jeu généré en %.1f s (%d mois d\'historique, date de référence %s).'
          % (time.time() - depart, arguments.mois, DATE_REFERENCE))
    if ctx.avis_wiki:
        print(ctx.avis_wiki)
    for table in NOMS_TABLES:
        print('  %-26s %6d lignes' % (table, len(ctx.base[table])))
    print('CSV : %s' % dossier)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(principal())
    except ErreurCoherence as probleme:
        sys.stderr.write("Jeu de démo incohérent :\n%s\n" % probleme)
        sys.exit(1)
