#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Générateur du jeu de démo de Prévo (docs/ARCHITECTURE.md §11, brief §13).

Ce script fabrique, de façon REPRODUCTIBLE (graine fixe, date de référence fixe), un atelier
fictif complet : équipements, techniciens, articles, gammes, six mois d'historique de pannes et de
préventif... Aucune personne ni entreprise réelle : tous les noms sont inventés.

Sorties par défaut :
    donnees/demo/<table>.csv    les 22 fichiers CSV (format ARCHITECTURE.md §3.1)
    js/demo-donnees.js          les mêmes textes, prêts à être chargés par la page (mode démo)

Utilisation (depuis la racine du projet) :
    py outils/generer_demo.py                          jeu de démo, 6 mois d'historique
    py outils/generer_demo.py --mois 13                historique plus long (13 mois)
    py outils/generer_demo.py --sans-js                CSV seulement
    py outils/generer_demo.py --volume 500,5000 --sortie C:\\temp\\charge
                                                       jeu de charge (500 équipements, 5 000 OT, 24 mois)

Le script s'auto-vérifie (clés étrangères, listes de valeurs, règles RG1 à RG4, stock) et
s'arrête avec un message clair au moindre défaut.

Organisation du fichier :
    1. Schéma et écriture CSV (règles §3.1 et §3.2)
    2. Petits outils (dates, heures ouvrées, nombres)
    3. Catalogue de contenu (équipements, scénarios de pannes, articles, gammes...)
    4. Génération table par table
    5. Génération de l'historique (DI, OT, préventif)
    6. Stock, achats, mouvements
    7. Identifiants, auto-vérification, écriture, ligne de commande
"""
import argparse
import calendar
import json
import random
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_DEMO = RACINE / 'donnees' / 'demo'
FICHIER_JS = RACINE / 'js' / 'demo-donnees.js'

GRAINE = 42                      # graine fixe : deux exécutions donnent des fichiers identiques
DATE_REFERENCE = '2026-10-19'    # « aujourd'hui » du jeu de démo (un lundi)
MOIS_PAR_DEFAUT = 6              # durée de l'historique
HEURE_COURANTE = 9.0             # il est 9 h 00 à la date de référence
FACTEUR_TAUX_DEMO = 1.3          # règle le nombre de pannes « de fond » du jeu de démo

NOM_ENTREPRISE = 'Atelier des Trois Vallées (démo)'


# =============================================================================
# 1. SCHÉMA ET ÉCRITURE CSV
# =============================================================================

# Copie en Python de js/schema.js (champs et ordre EXACTS de chaque table). Le test
# tests/test_demo.py compare cette description au vrai Schema lu dans Chromium : en cas de
# modification de js/schema.js, mettre à jour ce tableau (le test échoue sinon).
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
        'habilitation_requise:texte consignation:texte_long document:document actif:booleen'),
    'demandes': (
        'id:id date_heure:date_heure demandeur:texte equipement_id:ref>equipements '
        'symptome:texte_long impact:choix[sécurité|arrêt|dégradé|gêne] description:texte_long '
        'photo:document statut:choix[Nouvelle|Acceptée|Regroupée|Différée|Refusée] '
        'motif_decision:texte_long date_decision:date_heure ot_id:ref>ordres_travail'),
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
        'ot_lie_id:ref>ordres_travail'),
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
        'id:id technicien_id:ref>techniciens intitule:texte date_obtention:date date_echeance:date'),
    'compteurs': 'id:id equipement_id:ref>equipements libelle:texte unite:texte',
    'releves': 'id:id compteur_id:ref>compteurs date:date valeur:decimal utilisateur:texte',
    'controles_reglementaires': (
        'id:id equipement_id:ref>equipements nature:texte texte_reference:texte periodicite_mois:entier '
        'organisme:texte derniere_date:date prochaine_date:date rapport:document observations:texte_long '
        'observations_levees:booleen'),
    'codes_defaillance': (
        'id:id famille:choix[symptôme|cause|remède] code:texte libelle:texte'),
    'fournisseurs': 'id:id nom:texte contact:texte telephone:texte! email:texte',
    'achats': (
        'id:id date:date article_id:ref>articles fournisseur_id:ref>fournisseurs quantite:decimal '
        'prix_unitaire:decimal statut:choix[demandée|commandée|reçue] date_reception:date'),
    'parametres': 'cle:id valeur:texte',
    'journal': (
        'id:id date_heure:date_heure poste:texte profil:texte table:texte id_ligne:texte action:texte'),
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
    """Écrit les 22 fichiers CSV (BOM UTF-8 + CRLF) octet pour octet."""
    dossier.mkdir(parents=True, exist_ok=True)
    for table, texte in textes.items():
        (dossier / (table + '.csv')).write_bytes(b'\xef\xbb\xbf' + texte.encode('utf-8'))


def ecrire_js(chemin, textes):
    """Écrit js/demo-donnees.js : un objet DEMO_DONNEES qui contient le texte CSV de chaque table."""
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
        lignes.append("    %s: %s," % (table, json.dumps(textes[table], ensure_ascii=False)))
    lignes += ["  },", "};", ""]
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes('\n'.join(lignes).encode('utf-8'))


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
    definir_equipement('CV-03', 'Convoyeur de sortie de ligne', 'ligne_cond', None, 'Convexa', 'CB-400',
                       'CX-400-19-0411', '2019-10-07', 'C', 8, '', 'elec,meca', '', 'convoyeur', 0.25),
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

# Les 10 gammes de la démo. `derniere` = date de la dernière réalisation.
# `ouvert` : statut de l'OT préventif ouvert à la date de référence (None = aucun OT ouvert).
# `sans_ot` : la gamme est échue mais RIEN n'a encore généré d'OT (scénario de recette « gamme échue »).
GAMMES_DEMO = [
    {'repere': 'CP-01', 'libelle': 'Entretien mensuel du compresseur CP-01', 'periode': 30, 'avance': 3,
     'derniere': '2026-09-29', 'temps': 1.5, 'ops': OPS_COMPRESSEUR_MENSUEL, 'metiers': [MECA],
     'pieces': [], 'remede': 'R03', 'consignes': CONSIGNE_STANDARD},
    {'repere': 'CP-01', 'libelle': 'Entretien des 2000 heures du compresseur CP-01', 'compteur': 'cp01',
     'unites': 2000, 'avance': 5, 'ecart': 0.5, 'temps': 4.0, 'ops': OPS_COMPRESSEUR_2000H,
     'metiers': [MECA], 'pieces': [('filtre_air_cp', 1), ('filtre_huile_cp', 1), ('huile_cp', 1)],
     'remede': 'R01', 'consignes': CONSIGNE_STANDARD},
    {'repere': 'PO-02', 'libelle': 'Contrôle trimestriel de la pompe PO-02', 'periode': 90, 'avance': 7,
     'derniere': '2026-08-04', 'temps': 2.0, 'ops': OPS_POMPE, 'metiers': [MECA, POLY],
     'pieces': [('graisse', 1)], 'remede': 'R05', 'consignes': CONSIGNE_STANDARD},
    {'repere': 'CV-01', 'libelle': 'Contrôle mensuel du convoyeur CV-01', 'periode': 30, 'avance': 3,
     'derniere': '2026-09-14', 'temps': 1.0, 'ops': OPS_CONVOYEUR, 'metiers': [POLY, MECA],
     'pieces': [('graisse', 1)], 'remede': 'R05', 'consignes': CONSIGNE_STANDARD, 'sans_ot': True,
     'sans_decalage': True},
    {'repere': 'VE-01', 'libelle': 'Contrôle mensuel de la ventilation VE-01', 'periode': 30, 'avance': 3,
     'derniere': '2026-10-06', 'temps': 1.0, 'ops': OPS_VENTILATION, 'metiers': [POLY],
     'pieces': [], 'remede': 'R03', 'consignes': CONSIGNE_STANDARD, 'toujours_ras': True},
    {'repere': 'PR-01', 'libelle': 'Contrôle hydraulique et graissage de la presse PR-01', 'periode': 60,
     'avance': 5, 'derniere': '2026-09-02', 'temps': 2.5, 'ops': OPS_PRESSE, 'metiers': [MECA],
     'pieces': [('graisse', 1)], 'remede': 'R05', 'consignes': CONSIGNE_STANDARD},
    {'repere': 'AE-01', 'libelle': 'Thermographie et serrage des armoires électriques', 'periode': 180,
     'avance': 14, 'derniere': '2026-06-10', 'temps': 3.0, 'ops': OPS_ARMOIRES, 'metiers': [ELEC, AUTO],
     'pieces': [], 'remede': 'R04',
     'consignes': "Intervention hors tension uniquement : consigner l'armoire. Habilitation BR requise."},
    {'repere': 'GF-01', 'libelle': 'Entretien trimestriel du groupe froid GF-01', 'periode': 90, 'avance': 7,
     'derniere': '2026-08-24', 'temps': 3.0, 'ops': OPS_FROID, 'metiers': [MECA, ELEC],
     'pieces': [('filtre_eau', 1)], 'remede': 'R03', 'consignes': CONSIGNE_STANDARD},
    {'repere': 'CH-01', 'libelle': 'Vérification du chariot CH-01 toutes les 200 heures', 'compteur': 'ch01',
     'unites': 200, 'avance': 5, 'ecart': 'echue', 'temps': 1.5, 'ops': OPS_CHARIOT, 'metiers': [MECA, POLY],
     'pieces': [('graisse', 1)], 'remede': 'R05', 'consignes': 'Débrancher la batterie avant toute intervention.',
     'ouvert': 'Créé'},
    {'repere': 'CN-01', 'libelle': 'Graissage et contrôle mensuel du tour CN-01', 'periode': 30, 'avance': 3,
     'derniere': '2026-09-17', 'temps': 1.5, 'ops': OPS_TOUR, 'metiers': [POLY, AUTO],
     'pieces': [('graisse', 1), ('liq_coupe', 1)], 'remede': 'R05', 'consignes': CONSIGNE_STANDARD,
     'ouvert': 'Planifié', 'tech_ouvert': 4},
]

COMPTEURS_DEMO = [      # clé, repère, libellé, unité, valeur au premier relevé, rythme par jour calendaire
    {'cle': 'cp01', 'repere': 'CP-01', 'libelle': 'Compteur horaire de marche', 'unite': 'h',
     'depart': 11480, 'par_jour': 11.4},
    {'cle': 'pr01', 'repere': 'PR-01', 'libelle': 'Compteur de cycles de la presse', 'unite': 'cycles',
     'depart': 1482000, 'par_jour': 1100},
    {'cle': 'ch01', 'repere': 'CH-01', 'libelle': 'Compteur horaire du chariot', 'unite': 'h',
     'depart': 3120, 'par_jour': 4.6},
]

# Contrôles réglementaires : (repère, nature, texte de référence, périodicité en mois, organisme,
# date du dernier contrôle, observations, observations levées ?)
ORGANISME_1 = 'Bureau Alpin de Contrôle (démo)'
CONTROLES_DEMO = [
    ('PT-01', 'Vérification générale périodique du pont roulant', 'Arrêté du 1er mars 2004 (VGP)', 12,
     ORGANISME_1, '2026-02-10', '', 1),
    ('CH-01', 'Vérification générale périodique du chariot élévateur', 'Arrêté du 1er mars 2004 (VGP)', 12,
     ORGANISME_1, '2025-09-18', '', 1),
    ('AE-01', 'Vérification périodique des installations électriques', 'Code du travail, art. R4226-14', 12,
     'Certif-Elec Services (démo)', '2025-11-12', '', 1),
    ('RA-01', "Inspection périodique du réservoir d'air comprimé", 'Arrêté du 20 novembre 2017', 36,
     'Bureau Alpin de Contrôle (démo)', '2025-04-03',
     'Purgeur automatique du réservoir défectueux : à remplacer avant la prochaine inspection.', 0),
    ('GF-01', "Contrôle d'étanchéité du circuit frigorifique", 'Règlement (UE) 2024/573', 12,
     'Frigo-Contrôle Sud (démo)', '2026-03-24', '', 1),
    ('VE-02', "Contrôle de l'aération et de l'assainissement des locaux", 'Code du travail, art. R4222-20', 12,
     ORGANISME_1, '2026-06-02', '', 1),
]

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
        self.mois = mois
        self.volume = volume                          # None ou (nombre d'équipements, nombre d'OT)
        self.ref = jour_depuis_texte(DATE_REFERENCE)
        self.maintenant = instant(self.ref, HEURE_COURANTE)
        self.debut = ajouter_mois(self.ref, -mois)    # premier jour de l'historique
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

    @property
    def fin_historique(self):
        """Dernier jour où l'on peut avoir terminé une intervention (la veille de la date de référence)."""
        return self.ref - timedelta(days=1)


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
            actif=0 if entree['statut'] == 'rebut' else 1)
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
    """Un relevé par mois (vers le 12), à partir du mois qui précède le début de l'historique."""
    premier = ajouter_mois(ctx.debut, -1)
    jour = date(premier.year, premier.month, 12)
    dates = []
    while jour <= ctx.fin_historique:
        dates.append(jour_ouvre_avant(jour))
        jour = ajouter_mois(jour, 1)
    return dates


def compteurs_du_jeu_de_charge(ctx):
    """Dix compteurs horaires sur des compresseurs, presses et appareils de levage."""
    retenus = [e for e in ctx.equipements if e['famille'] in ('compresseur', 'presse', 'levage')][:10]
    return [{'cle': 'c%d' % numero, 'repere': e['repere'], 'libelle': 'Compteur horaire', 'unite': 'h',
             'depart': 2000 + numero * 137, 'par_jour': 5.0 + numero} for numero, e in enumerate(retenus, 1)]


def generer_compteurs_et_releves(ctx):
    rng = ctx.rng
    noms = ['%s %s' % (t['prenom'], t['nom']) for t in ctx.techniciens]
    definitions = compteurs_du_jeu_de_charge(ctx) if ctx.volume else COMPTEURS_DEMO
    for definition in definitions:
        equipement = ctx.equipement[definition['repere']]
        ligne = creer_ligne(ctx, 'compteurs', equipement_id=equipement['id'],
                            libelle=definition['libelle'], unite=definition['unite'])
        compteur = dict(definition, id=ligne['id'], releves=[])
        valeur = float(definition['depart'])
        precedent = None
        for jour in dates_de_releve(ctx):
            if precedent is not None:
                valeur += definition['par_jour'] * (jour - precedent).days * rng.uniform(0.9, 1.1)
            precedent = jour
            compteur['releves'].append((jour, int(round(valeur))))
            creer_ligne(ctx, 'releves', compteur_id=ligne['id'], date=texte_date(jour),
                        valeur=int(round(valeur)), utilisateur=rng.choice(noms))
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

def gammes_du_jeu_de_charge(ctx):
    """Une gamme pour environ 22 % des équipements, périodicité 30 à 180 jours."""
    rng = ctx.rng
    eligibles = [e for e in ctx.equipements if e['famille'] in GAMME_PAR_FAMILLE and e['statut'] == 'en service']
    nombre = max(10, int(len(ctx.equipements) * 0.22))
    gammes = []
    for equipement in rng.sample(eligibles, min(nombre, len(eligibles))):
        ops, temps, remede = GAMME_PAR_FAMILLE[equipement['famille']]
        periode = rng.choice([30, 30, 60, 90, 180])
        avance = rng.choice([3, 5, 7])
        if rng.random() < 0.15:     # gamme échue : un OT préventif est ouvert
            derniere = ctx.ref - timedelta(days=periode - avance + rng.randint(0, 10))
            ouvert = rng.choice(['Créé', 'Créé', 'Préparé', 'Planifié'])
        else:
            derniere = ctx.ref - timedelta(days=rng.randint(3, max(3, periode - avance - 3)))
            ouvert = None
        gammes.append({'repere': equipement['repere'],
                       'libelle': 'Contrôle périodique de %s' % equipement['designation'].lower(),
                       'periode': periode, 'avance': avance, 'derniere': texte_date(jour_ouvre_avant(derniere)),
                       'temps': temps, 'ops': ops, 'metiers': [MECA, POLY, ELEC],
                       'pieces': [('graisse', 1)], 'remede': remede, 'consignes': CONSIGNE_STANDARD,
                       'ouvert': ouvert})
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


def generer_gammes(ctx):
    """Crée les gammes (lignes + opérations) et prépare leurs métadonnées de planification."""
    specifications = gammes_du_jeu_de_charge(ctx) if ctx.volume else GAMMES_DEMO
    for specification in specifications:
        equipement = ctx.equipement[specification['repere']]
        gamme = dict(specification, eq=equipement, occurrences=[], ouvert=specification.get('ouvert'))
        compteur = ctx.compteurs.get(specification.get('compteur'))
        if compteur:
            derniere, releve = choisir_derniere_realisation_compteur(
                compteur, specification['unites'], specification['ecart'])
            prochaine = date_pour_valeur(compteur, releve + specification['unites'])
            gamme.update(compteur=compteur, derniere=derniere, releve=releve, prochaine=prochaine)
            ligne = creer_ligne(
                ctx, 'gammes', equipement_id=equipement['id'], libelle=specification['libelle'],
                declencheur='compteur', compteur_id=compteur['id'], periodicite_unites=specification['unites'],
                avance_jours=specification['avance'], derniere_realisation=texte_date(derniere),
                releve_derniere_realisation=releve, prochaine_echeance=texte_date(prochaine),
                temps_prevu_h=specification['temps'], consignes=specification['consignes'])
        else:
            derniere = jour_depuis_texte(specification['derniere'])
            prochaine = derniere + timedelta(days=specification['periode'])
            gamme.update(compteur=None, derniere=derniere, releve=None, prochaine=prochaine)
            ligne = creer_ligne(
                ctx, 'gammes', equipement_id=equipement['id'], libelle=specification['libelle'],
                declencheur='date', periodicite_jours=specification['periode'],
                avance_jours=specification['avance'], derniere_realisation=texte_date(derniere),
                prochaine_echeance=texte_date(prochaine), temps_prevu_h=specification['temps'],
                consignes=specification['consignes'])
        gamme['ligne'] = ligne
        gamme['id'] = ligne['id']
        for ordre, (operation, attendue, _mesure) in enumerate(specification['ops'], 1):
            creer_ligne(ctx, 'gamme_operations', gamme_id=ligne['id'], ordre=ordre, operation=operation,
                        valeur_attendue=attendue)
        gamme['echue'] = est_gamme_echue(ctx, gamme)
        if ctx.volume and gamme['echue'] and not gamme['ouvert']:
            gamme['ouvert'] = 'Créé'          # une gamme échue a toujours son OT (RG5)
        ctx.gammes.append(gamme)


def est_gamme_echue(ctx, gamme):
    """RG5 : échue si (échéance - avance) est atteinte, ou si le compteur a dépassé l'intervalle."""
    if gamme['compteur']:
        courant = gamme['compteur']['releves'][-1][1]
        return courant - gamme['releve'] >= gamme['unites']
    return gamme['prochaine'] - timedelta(days=gamme['avance']) <= ctx.ref


# ---------------------------------------------------------------------------
# Contrôles réglementaires
# ---------------------------------------------------------------------------

def generer_controles(ctx):
    """Contrôles réglementaires. Dans le jeu de charge, ils portent sur des équipements de même famille."""
    familles_par_repere = {e['repere']: e['famille'] for e in EQUIPEMENTS_DEMO}
    for rang, (repere, nature, texte_reference, periodicite, organisme, derniere, observations, levees)             in enumerate(CONTROLES_DEMO):
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
                    observations=observations, observations_levees=levees)
        ctx.controles.append({'eq': equipement, 'nature': nature, 'organisme': organisme,
                              'derniere': derniere, 'observations': observations})


def generer_parametres(ctx):
    for cle, valeur in [('entreprise_nom', NOM_ENTREPRISE), ('delai_p1_h', 0), ('delai_p2_h', 24),
                        ('delai_p3_h', 168), ('delai_p4', 'prochain arrêt'), ('heures_fonct_defaut', 8),
                        ('tolerance_preventif_pct', 10), ('rafraichissement_s', 20), ('version_schema', 1)]:
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
    regroupees (liste de (quand, texte, demandeur) : DI regroupées sur cet OT).
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
            statut='Nouvelle')
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
        ajouter_demande_regroupee(ctx, equipement, ot, quand_regroupee, texte, demandeur, impact)

    if etat == 'clos':
        derouler_correctif(ctx, equipement, scenario_, ot, decision, immediat, date_prevue, impact, options)
    else:
        preparer_ot_ouvert(ctx, equipement, scenario_, ot, etat, decision, date_prevue, impact, options)
    return demande, ot


def ajouter_demande_regroupee(ctx, equipement, ot, quand, texte, demandeur, impact):
    """Une seconde DI sur le même équipement, rattachée à l'OT déjà ouvert (RG1 : Regroupée)."""
    creer_ligne(ctx, 'demandes', date_heure=texte_dh(quand), demandeur=demandeur, equipement_id=equipement['id'],
                symptome=texte, impact=impact, description='Même problème que la demande précédente.',
                statut='Regroupée', motif_decision="Regroupée avec l'OT déjà ouvert pour cet équipement.",
                date_decision=texte_dh(apres_minutes_ouvrees(quand, 20)), ot_id=ot)


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
                                  rng.choice(DEMANDEURS), 'gêne')


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
    rng = ctx.rng
    for controle in ctx.controles:
        jour = jour_depuis_texte(controle['derniere'])
        if ctx.debut <= jour <= ctx.fin_historique:
            observation = (" Observation de l'organisme à lever : " + controle['observations']
                           if controle['observations'] else ' Aucune observation.')
            creer_ot_manuel(
                ctx, controle['eq'], controle['nature'], 'Accompagner l\'organisme de contrôle et récupérer le rapport.',
                jour, 1.0, [POLY, MECA], 'Contrôle réalisé par %s, rapport reçu.%s' % (controle['organisme'], observation),
                'réglementaire', 'C99', 'R10', cout_soustraitance=rng.randrange(250, 650, 50))
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


def occurrence_ouverte(ctx, gamme):
    """Échéance en cours d'une gamme échue (l'OT n'est pas terminé)."""
    if gamme['compteur']:
        creation = jour_ouvre_apres(gamme['compteur']['releves'][-1][0] + timedelta(days=1))
        prevue = jour_ouvre_apres(creation + timedelta(days=10))
    else:
        creation = jour_ouvre_apres(gamme['prochaine'] - timedelta(days=gamme['avance']))
        prevue = jour_ouvre_avant(gamme['prochaine'])
    return {'creation': min(creation, ctx.ref), 'prevue': prevue, 'exec': None, 'releve': None}


def creer_preventif(ctx, gamme, occurrence, etat):
    """OT préventif issu d'une gamme (RG5) : opérations copiées dans ot_operations."""
    rng = ctx.rng
    equipement = gamme['eq']
    creation = instant(occurrence['creation'], 7.0) + timedelta(minutes=rng.randint(10, 40))
    ot = creer_ligne(
        ctx, 'ordres_travail', origine='préventif', gamme_id=gamme['id'], equipement_id=equipement['id'],
        type='préventif conditionnel' if gamme['compteur'] else 'préventif systématique',
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
        cloturer_ot(ctx, ot, fin, None, 'C99', gamme['remede'], compte_rendu_preventif(ctx, gamme, mesures))
        return ot
    if etat != 'Créé':
        ajouter_pieces_ot(ctx, ot, equipement, gamme['pieces'])
    if etat == 'Planifié':
        numero = gamme.get('tech_ouvert')
        technicien = (ctx.techniciens[numero - 1] if numero else
                      choisir_technicien(ctx, gamme['metiers'], equipement, occurrence['prevue']))
        renseigner(ot, technicien_id=technicien['id'])
    return ot


def generer_preventifs(ctx):
    for gamme in ctx.gammes:
        gamme['occurrences'] = (occurrences_par_compteur(ctx, gamme) if gamme['compteur']
                                else occurrences_par_date(ctx, gamme))
        for occurrence in gamme['occurrences']:
            creer_preventif(ctx, gamme, occurrence, 'clos')
        if gamme['echue'] and gamme['ouvert'] and not gamme.get('sans_ot'):
            creer_preventif(ctx, gamme, occurrence_ouverte(ctx, gamme), gamme['ouvert'])


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
    """Les cas démontrables : PO-02 (fuites de garniture à 58 jours), CV-02 (capteur encrassé), CP-01
    (échauffements), une panne unique (BA-01), une panne entre deux préventifs (PR-01)."""
    rng = ctx.rng
    equipement = ctx.equipement
    # PO-02 : fuite de garniture tous les 58 jours environ, depuis la plus récente (il y a 19 jours).
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
        creer_correctif(ctx, equipement['PO-02'], scenario_, heure_aleatoire(rng, jour, 7.0, 14.0),
                        'dégradé', 'clos', compte_rendu=compte_rendu, pieces=[('kit_gar_u', 1)],
                        heures=quart_heure(rng.uniform(2.5, 4.0)))
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
    # CP-01 : échauffements récurrents (filtre colmaté ou manque de lubrification), un tous les 35 jours.
    for rang, (decalage, cause) in enumerate([(35, 'C05'), (70, 'C07'), (105, 'C05'), (140, 'C05'), (175, 'C07')]):
        jour = jour_ouvre_avant(ctx.ref - timedelta(days=decalage + rng.randint(-3, 3)))
        if jour >= ctx.debut:
            creer_correctif(ctx, equipement['CP-01'], trouver_scenario('compresseur', cause, 'S04'),
                            heure_aleatoire(rng, jour, 7.0, 14.0), 'arrêt' if rang % 2 == 0 else 'dégradé', 'clos')
    # BA-01 : une seule panne dans tout l'historique.
    jour = jours_avant_reference(ctx, 75)
    if jour >= ctx.debut:
        creer_correctif(
            ctx, equipement['BA-01'], trouver_scenario('emballage', 'C11', 'S07'), heure_aleatoire(rng, jour, 7.0, 14.0),
            'dégradé', 'clos', texte_di='La balance de contrôle rejette des colis conformes : le poids affiché dérive.',
            compte_rendu='Dérive du zéro de la balance : retarage avec la masse étalon, 20 colis conformes pesés correctement.',
            pieces=[], heures=1.0)
    # PR-01 : une panne qui survient ENTRE deux visites préventives.
    gamme_presse = [g for g in ctx.gammes if g['repere'] == 'PR-01' and not g['compteur']]
    if gamme_presse and len(gamme_presse[0]['occurrences']) >= 2:
        avant, apres = gamme_presse[0]['occurrences'][-2]['exec'], gamme_presse[0]['occurrences'][-1]['exec']
        jour = jour_ouvre_apres(avant + (apres - avant) // 2)
        creer_correctif(ctx, equipement['PR-01'], trouver_scenario('presse', 'C10', 'S01'),
                        heure_aleatoire(rng, jour, 7.0, 13.0), 'dégradé', 'clos',
                        texte_di="Fuite d'huile sur un flexible de la presse, elle goutte sur le sol.")


def etat_courant_demo(ctx):
    """Ce qui est ouvert à la date de référence : DI à traiter, OT dans tous les statuts, un P1, des retards."""
    equipement = ctx.equipement
    jour = ctx.ref
    hier = lambda nombre, heure: instant(jour - timedelta(days=nombre), heure)

    # --- OT ouverts (le préventif CH-01 « Créé » et CN-01 « Planifié » viennent des gammes)
    # P1 ouvert : le compresseur, en cours de dépannage ce matin.
    creer_correctif(
        ctx, equipement['CP-01'], trouver_scenario('compresseur', 'C05', 'S04'), instant(jour, 7.6), 'arrêt', 'En cours',
        texte_di="Le compresseur CP-01 s'est arrêté en sécurité : alarme température haute, le carter est brûlant.",
        description='Arrêt constaté à la prise de poste.', demandeur='Paul Dubois', delai_decision=14,
        debut=instant(jour, 8.2), technicien=ctx.techniciens[1], temps_prevu=3.0, pieces=[('filtre_huile_cp', 1)],
        heures_passees=0.5)
    renseigner(equipement['CP-01']['ligne'], statut='arrêt')
    # P2 en cours avec une seconde DI regroupée.
    creer_correctif(
        ctx, equipement['EM-01'], trouver_scenario('emballage', 'C11', 'S07'), instant(jour - timedelta(days=3), 14.2),
        'dégradé', 'En cours', texte_di="Les films sont mal soudés sur la fardeleuse, des colis s'ouvrent à la sortie.",
        demandeur='Manon Duval', delai_decision=20, debut=instant(jour, 7.5), technicien=ctx.techniciens[2],
        temps_prevu=2.0, pieces=[('res_soudure', 1)], heures_passees=1.25,
        regroupees=[(instant(jour, 7.33), "La fardeleuse EM-01 refait des films mal soudés ce matin aussi.", 'Lucas Perrot')])
    # Planifié (pas en retard).
    creer_correctif(
        ctx, equipement['CU-01'], trouver_scenario('usinage', 'C11', 'S07'), instant(jour - timedelta(days=5), 10.25),
        'gêne', 'Planifié', texte_di="Les cotes des pièces dérivent légèrement sur le centre d'usinage.",
        demandeur='Camille Girard', delai_decision=50, date_prevue=jour + timedelta(days=2),
        technicien=ctx.techniciens[2], temps_prevu=2.0, pieces=[])
    # Préparé, pas en retard (priorité P4).
    creer_correctif(
        ctx, equipement['CV-03'], trouver_scenario('convoyeur', 'C03', 'S02'), instant(jour - timedelta(days=7), 8.7),
        'gêne', 'Préparé', texte_di='La courroie du convoyeur CV-03 patine, bruit de glissement au démarrage.',
        demandeur='Inès Marchand', pieces=[('cour_htd', 1)], temps_prevu=1.0)
    # Préparé et EN RETARD (priorité P4, échéance dépassée).
    creer_correctif(
        ctx, equipement['VE-02'], trouver_scenario('ventilation', 'C05', 'S08'), instant(jour - timedelta(days=21), 9.1),
        'gêne', 'Préparé', texte_di="Débit d'air faible sur l'extracteur VE-02, le filtre semble très encrassé.",
        demandeur='Hugo Lefèvre', pieces=[('filtre_g4', 2)], temps_prevu=1.0)
    # En attente d'une pièce, EN RETARD : le contacteur du départ est en rupture.
    creer_correctif(
        ctx, equipement['AE-02'], trouver_scenario('electrique', 'C09', 'S10'), instant(jour - timedelta(days=12), 13.3),
        'dégradé', 'En attente', texte_di="Légère odeur de chaud près du départ ventilation de l'armoire AE-02.",
        demandeur='Antoine Mercier', delai_decision=45, technicien=ctx.techniciens[0], temps_prevu=2.0,
        debut=instant(jour - timedelta(days=11), 8.0), heures_passees=1.0, pieces=[('contacteur_25', 2)],
        motif_attente='Pièce : contacteur tripolaire 25 A en rupture de stock, achat demandé au fournisseur.')

    # --- DI encore à traiter, différée, refusée
    nouvelles = [
        (equipement['AE-04'], 'sécurité', instant(jour, 7.25), 'Paul Dubois',
         "Odeur de brûlé près de l'armoire AE-04, un peu de fumée à l'ouverture de la porte."),
        (equipement['PR-01'], 'dégradé', hier(3, 16.1), 'Sarah Colin',
         "Fuite d'huile sous la presse PR-01, une petite flaque se forme depuis ce matin."),
        (equipement['ET-01'], 'gêne', hier(3, 11.3), 'Léa Fontaine',
         "Les étiquettes sortent décalées de quelques millimètres sur l'étiqueteuse."),
        (equipement['PO-03'], 'gêne', instant(jour, 6.97), 'Mathieu Roux',
         'La pompe de relevage est très bruyante au démarrage.'),
    ]
    for equipement_nouvelle, impact, quand, demandeur, texte in nouvelles:
        creer_correctif(ctx, equipement_nouvelle, None, quand, impact, 'Nouvelle', texte_di=texte,
                        demandeur=demandeur, description='')
    creer_correctif(
        ctx, equipement['CV-01'], None, hier(6, 10.7), 'gêne', 'Différée', demandeur='Lucas Perrot', delai_decision=200,
        texte_di='Le garde-corps du convoyeur CV-01 est légèrement tordu, à redresser.', description='',
        motif="Différée : à traiter lors de l'arrêt programmé de fin octobre, sans impact sur la production.")
    creer_correctif(
        ctx, equipement['CU-01'], None, hier(10, 9.5), 'gêne', 'Refusée', demandeur='Hugo Lefèvre', delai_decision=120,
        texte_di='Demande de repeindre le carter du centre d\'usinage en bleu.', description='',
        motif="Refusée : demande esthétique, hors périmètre de la maintenance. À adresser au service méthodes.")


# =============================================================================
# 6. STOCK, ACHATS ET MOUVEMENTS
# =============================================================================

def rejouer_stock(ctx, article, evenements, stock_initial, reapprovisionner):
    """Rejoue les mouvements d'un article dans l'ordre du temps.

    Retourne (stock minimal atteint, stock final, commandes). Si `reapprovisionner`, une commande est
    passée dès que le stock tombe au point de commande ; elle arrive après le délai de l'article.
    """
    limite = instant(ctx.fin_historique, 17.0)
    stock = minimum = stock_initial
    commandes = []
    en_attente = None
    for genre, evenement in evenements:
        if en_attente and en_attente['arrivee'] <= evenement['quand']:
            stock += en_attente['quantite']
            en_attente['recue'] = True
            en_attente = None
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
        return article['cible'] + sorti - rendu, False
    stock_initial = article['pc'] + 1
    for _ in range(5000):
        minimum, final, commandes = rejouer_stock(ctx, article, evenements, stock_initial, True)
        manque = max(-minimum, article['pc'] + 1 - final, article['stock_final_min'] - final, 0)
        if manque == 0 and all(commande['recue'] for commande in commandes):
            return stock_initial, True
        stock_initial += max(1, manque)
    raise ErreurCoherence('Stock impossible à équilibrer pour ' + article['designation'])


def construire_stock(ctx):
    """Inventaire de départ, sorties imputées aux OT, retours, réceptions et achats d'un jeu cohérent."""
    rng = ctx.rng
    evenements_par_article = {cle: [] for cle in ctx.articles}
    for sortie in ctx.sorties:
        evenements_par_article[sortie['article']['cle']].append(('sortie', sortie))
    for retour in ctx.retours:
        evenements_par_article[retour['article']['cle']].append(('retour', retour))
    mouvements = []            # (instant, numéro d'ordre, valeurs)
    achats = []
    debut = instant(jour_ouvre_apres(ctx.debut), 6.5)
    for cle, article in ctx.articles.items():
        evenements = sorted(evenements_par_article[cle], key=lambda element: element[1]['quand'])
        stock_initial, reapprovisionner = choisir_stock_initial(ctx, article, evenements)
        mouvements.append((debut, len(mouvements), dict(
            article=article, type='inventaire', quantite=stock_initial, utilisateur='Magasin',
            commentaire='Inventaire de départ')))
        for genre, evenement in evenements:
            mouvements.append((evenement['quand'], len(mouvements), dict(
                article=article, type=genre, quantite=evenement['quantite'], ot_id=evenement['ot'],
                utilisateur=evenement['utilisateur'],
                commentaire=('Utilisée sur %s' if genre == 'sortie' else 'Retour au magasin (non utilisée) de %s')
                % evenement['repere'])))
        if reapprovisionner:
            _minimum, _final, commandes = rejouer_stock(ctx, article, evenements, stock_initial, True)
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
                if champ['type'] == 'choix' and valeur not in champ['valeurs']:
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
    if erreurs:
        raise ErreurCoherence('\n'.join(erreurs))


def construire_jeu(mois=MOIS_PAR_DEFAUT, volume=None):
    """Construit toutes les tables en mémoire (liste de dictionnaires) et vérifie leur cohérence."""
    ctx = Contexte(mois, volume)
    generer_localisations(ctx)
    generer_codes_defaillance(ctx)
    generer_fournisseurs(ctx)
    generer_techniciens(ctx)
    generer_equipements(ctx)
    generer_articles(ctx)
    generer_compteurs_et_releves(ctx)
    generer_gammes(ctx)
    generer_controles(ctx)
    generer_preventifs(ctx)
    generer_ot_reglementaires_et_ameliorations(ctx)
    if volume:
        generer_pannes_de_fond(ctx, cible_ot=volume[1])
    else:
        evenements_fixes_demo(ctx)
        etat_courant_demo(ctx)
        taux_total = sum(e['taux'] for e in ctx.equipements if e['famille'] in SCENARIOS)
        generer_pannes_de_fond(ctx, nombre=int(round(taux_total * FACTEUR_TAUX_DEMO * mois)))
    attribuer_identifiants_historique(ctx)
    construire_stock(ctx)
    generer_liens_article_equipement(ctx)
    generer_parametres(ctx)
    resoudre_references(ctx)
    verifier_jeu(ctx)
    return ctx


def lire_arguments(argv):
    analyseur = argparse.ArgumentParser(
        description="Génère le jeu de démo de Prévo (donnees/demo/*.csv et js/demo-donnees.js).")
    analyseur.add_argument('--mois', type=int, default=None,
                           help="durée de l'historique en mois (défaut : %d, ou 24 avec --volume)" % MOIS_PAR_DEFAUT)
    analyseur.add_argument('--volume', metavar='EQUIPEMENTS,OT', default=None,
                           help='jeu de charge, ex. 500,5000 (exige --sortie)')
    analyseur.add_argument('--sortie', metavar='DOSSIER', default=None,
                           help='dossier des CSV (défaut : donnees/demo ; dans ce cas js/demo-donnees.js est aussi écrit)')
    analyseur.add_argument('--sans-js', action='store_true', help="n'écrit pas js/demo-donnees.js")
    analyseur.add_argument('--fichier-js', metavar='CHEMIN', default=None,
                           help="écrit le fichier JavaScript à cet emplacement (utile aux tests)")
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
    ctx = construire_jeu(arguments.mois, arguments.volume)
    textes = {table: serialiser_table(table, ctx.base[table]) for table in NOMS_TABLES}
    dossier = Path(arguments.sortie) if arguments.sortie else DOSSIER_DEMO
    ecrire_csv(dossier, textes)
    if arguments.fichier_js:
        ecrire_js(Path(arguments.fichier_js), textes)
    elif not arguments.sans_js and not arguments.sortie:
        ecrire_js(FICHIER_JS, textes)
    print('Jeu généré en %.1f s (%d mois d\'historique, date de référence %s).'
          % (time.time() - depart, arguments.mois, DATE_REFERENCE))
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
