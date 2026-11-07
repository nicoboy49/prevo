#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
serveur.py — serveur local de la GMAO « Prévo ».

Rôle : servir l'application (fichiers HTML/CSS/JS) et une petite API HTTP qui lit et écrit
les fichiers CSV du dossier de données, les documents (photos, PDF…) et les sauvegardes.

Fichiers servis (liste blanche) : « / » (= index.html), index.html, favicon.svg, GUIDE.html
s'il existe, et tout ce qui est sous css/ et js/. Tout le reste du dossier (brief, README,
docs/, tests/, outils/, serveur.py, lanceurs…) répond 404. L'option --servir-tests sert en
plus tests/fixtures/ (pages utilisées par les tests automatiques).

Contrat complet : docs/ARCHITECTURE.md, sections 7 et 14.7.
Contraintes : Python 3.8 minimum, bibliothèque standard seulement, un seul fichier.

Lancement :
    py serveur.py [--port 8080] [--donnees CHEMIN] [--sans-navigateur] [--hote NOM]...
                  [--ia-url URL] [--ia-fournisseur ollama|openai] [--ia-en-ligne] [--servir-tests]
    (clé du fournisseur d'IA : « ia_cle » de prevo.config.json ou variable PREVO_IA_CLE, jamais une option)
    (exécutable Tailscale, §22.8 : chemin standard du système, ou variable PREVO_TAILSCALE — les tests y mettent
     tests/faux_tailscale.py ; un chemin qui n'existe pas vaut « Tailscale absent » —, jamais une option)

Accès : en portée « ce PC » (défaut), écoute sur 127.0.0.1 seulement et aucun compte. Avec « comptes » (lot 7,
ARCHITECTURE.md §22.3, §22.4), toute route /api/ autre que ping, session, connexion et enrôlement exige une session (cookie « id ») ou un
appareil enrôlé (cookie « appareil », D125, rôle demandeur), puis le rôle (ROLES_PAR_ROUTE, §22.5 : 403 sinon).
"""

import argparse
import base64
import csv
import datetime
import hashlib
import hmac
import http.client
import http.server
import io
import ipaddress
import json
import os
import platform
import re
import secrets
import shutil
import socket
import socketserver
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import unicodedata
import urllib.error
import urllib.request
import webbrowser
from urllib.parse import unquote, urlsplit


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

NOM_APPLICATION = 'Prévo'
VERSION_APPLICATION = '2.0.0-beta.2'
VERSION_API = 1

PORT_PAR_DEFAUT = 8080
NOMBRE_PORTS_SUPPLEMENTAIRES = 20          # 8080 occupé → 8081, … jusqu'à 8100
# Corps d'une requête (lire_corps, 413 au-delà) : 10 Mo (un document, du JSON ; = LIMITES.document de
# js/modules/zip-lecture.js, l'import ZIP en mode serveur envoie ainsi chaque document). T208 (Nicolas : tout ce que
# Prévo exporte, Prévo peut le réimporter) : l'envoi d'une table (ROUTES_CORPS_CSV) suit la limite d'un CSV de l'import
# ZIP (LIMITES.racine) : à 20 000 OT, ordres_travail.csv dépasse 10 Mo. Les autres routes gardent 10 Mo (audit F2).
# tests/test_zip_limites.py compare ces valeurs à celles de zip-lecture.js.
TAILLE_MAX_CORPS = 10 * 1024 * 1024        # 10 Mo
TAILLE_MAX_CORPS_CSV = 50 * 1024 * 1024    # 50 Mo
ROUTES_CORPS_CSV = (('PUT', 'csv/<table>'), ('POST', 'csv/<table>/ajout'))
# T204 (comme le correctif 1.2.1) : une cellule peut dépasser la limite par défaut du module csv (131 072 caractères :
# page du wiki, compte rendu très long) ; sans cette limite relevée, une fois pour tout ce fichier, un fichier sain
# serait pris pour un fichier abîmé (raisons_fichier_abime) et son enregistrement refusé. T207 (Nicolas) : relevée à
# la limite d'un CSV dans l'import ZIP (LIMITES.racine de js/modules/zip-lecture.js, 50 Mo depuis T208), et non sans
# limite.
TAILLE_MAX_CELLULE_CSV = 50 * 1024 * 1024
csv.field_size_limit(TAILLE_MAX_CELLULE_CSV)
# Audit F2 (§22.12) : requêtes en cours en même temps, tous écouteurs confondus (porte et application) ; une place
# est prise dès le premier octet d'une requête et rendue avec sa réponse (une requête lente ou laissée à moitié la
# tient) ; une connexion keep-alive inactive, qui attend la requête suivante, n'en tient aucune (défaut trouvé par
# la recette du lot 7). La suivante attend son tour dans son fil (SEMAPHORE_CONNEXIONS), ni refusée ni perdue.
CONNEXIONS_MAX = 32
ESSAIS_SI_VERROUILLE = 3                   # fichier ouvert dans Excel : 3 essais…
PAUSE_ENTRE_ESSAIS_S = 0.1                 # … espacés de 100 ms
# Relais vers le fournisseur d'IA (lot 4, ARCHITECTURE.md §17.2) : liste fermée des chemins (Ollama :
# api/chat, api/tags ; API compatible OpenAI : chat/completions, models), délai et taille plafonnés.
# Audit M1, M3 (§22.12) : le fournisseur, son adresse et sa clé sont réglés sur le PC serveur (ia_fournisseur,
# ia_url, ia_cle ou PREVO_IA_CLE), jamais par la requête ; le délai est fixé ici (DELAI_IA_S).
# Limite connue : le délai s'applique à CHAQUE opération réseau (connexion, envoi, chaque lecture), pas à
# la durée totale de l'appel ; un fournisseur qui envoie sa réponse goutte à goutte peut donc le dépasser.
CHEMINS_IA = ('api/chat', 'api/tags', 'chat/completions', 'models')
CLES_DEMANDE_IA = ('chemin', 'methode', 'corps')     # seules clés acceptées dans le corps de POST /api/ia
DELAI_IA_S = 120
TAILLE_MAX_REPONSE_IA = 2 * 1024 * 1024    # 2 Mo
VARIABLE_CLE_IA = 'PREVO_IA_CLE'           # clé du fournisseur : passe avant « ia_cle » du fichier, jamais en option
VARIABLE_TAILSCALE = 'PREVO_TAILSCALE'     # exécutable tailscale (tests : le faux) ; sinon le chemin standard (§22.8)
VARIABLE_MKCERT = 'PREVO_MKCERT'           # exécutable mkcert (tests : le faux) ; sinon outils-tiers/, empreinte vérifiée (§22.6)

# Dossier où se trouve serveur.py : c'est la racine des fichiers statiques.
DOSSIER_APPLICATION = os.path.dirname(os.path.abspath(__file__))

BOM_UTF8 = b'\xef\xbb\xbf'
FIN_DE_LIGNE = b'\r\n'

# Les 24 tables de la GMAO (fichier = <nom>.csv dans le dossier de données) ; wiki_pages et
# wiki_journal depuis le format 3 (lot 6, ARCHITECTURE.md §20.2).
# RENVOI CROISÉ : cette liste est recopiée de js/schema.js (Schema.tables).
# Si vous ajoutez ou renommez une table, modifiez les DEUX fichiers
# (un test vérifie qu'ils restent cohérents).
TABLES = (
    'localisations',
    'equipements',
    'demandes',
    'ordres_travail',
    'ot_operations',
    'ot_pieces',
    'ot_temps',
    'gammes',
    'gamme_operations',
    'articles',
    'article_equipement',
    'mouvements_stock',
    'techniciens',
    'habilitations',
    'compteurs',
    'releves',
    'controles_reglementaires',
    'codes_defaillance',
    'fournisseurs',
    'achats',
    'parametres',
    'journal',
    'wiki_pages',
    'wiki_journal',
)

# Colonnes de chaque table, dans l'ordre où Prévo les écrit (recopie de js/schema.js, version 3 ; cohérence
# vérifiée par tests/test_audit_csv.py). Le serveur exige qu'un CSV reçu commence par ces colonnes (audit E2) ;
# les colonnes ajoutées à la main dans Excel restent permises après elles (lecture tolérante, §3.3).
COLONNES_PAR_TABLE = {
    'localisations': ('id', 'libelle', 'parent_id', 'type'),
    'equipements': (
        'id', 'repere', 'designation', 'localisation_id', 'parent_id', 'marque', 'modele', 'num_serie', 'date_mes',
        'criticite', 'statut', 'heures_fonct_jour', 'habilitation_requise', 'consignation', 'document', 'actif',
        'valeur_remplacement',
    ),
    'demandes': (
        'id', 'date_heure', 'demandeur', 'equipement_id', 'symptome', 'impact', 'description', 'photo', 'statut',
        'motif_decision', 'date_decision', 'ot_id', 'symptome_code', 'ot_origine_id',
    ),
    'ordres_travail': (
        'id', 'origine', 'di_id', 'gamme_id', 'equipement_id', 'type', 'priorite', 'statut', 'motif_attente',
        'titre', 'travail_a_faire', 'consignes', 'date_creation', 'date_prevue', 'technicien_id', 'temps_prevu_h',
        'date_debut', 'date_fin', 'arret_production', 'duree_arret_h', 'symptome_code', 'cause_code', 'remede_code',
        'compte_rendu', 'remise_service', 'cout_soustraitance', 'date_cloture_tech', 'date_cloture_admin',
        'motif_annulation', 'ot_lie_id', 'anomalie_constatee', 'astuce',
    ),
    'ot_operations': ('id', 'ot_id', 'ordre', 'operation', 'valeur_attendue', 'fait', 'valeur_mesuree'),
    'ot_pieces': ('id', 'ot_id', 'article_id', 'quantite_prevue'),
    'ot_temps': ('id', 'ot_id', 'technicien_id', 'date', 'heures'),
    'gammes': (
        'id', 'equipement_id', 'libelle', 'declencheur', 'periodicite_jours', 'compteur_id', 'periodicite_unites',
        'seuil', 'avance_jours', 'derniere_realisation', 'releve_derniere_realisation', 'prochaine_echeance',
        'temps_prevu_h', 'consignes', 'actif',
    ),
    'gamme_operations': ('id', 'gamme_id', 'ordre', 'operation', 'valeur_attendue'),
    'articles': (
        'id', 'reference', 'designation', 'fabricant', 'ref_fabricant', 'emplacement', 'unite', 'stock',
        'stock_securite', 'point_commande', 'qte_commande', 'delai_jours', 'prix_unitaire', 'fournisseur_id',
        'critique', 'actif',
    ),
    'article_equipement': ('id', 'article_id', 'equipement_id', 'quantite'),
    'mouvements_stock': ('id', 'date', 'article_id', 'type', 'quantite', 'ot_id', 'utilisateur', 'commentaire'),
    'techniciens': ('id', 'nom', 'prenom', 'metier', 'taux_horaire', 'capacite_h_semaine', 'actif'),
    'habilitations': ('id', 'technicien_id', 'intitule', 'date_obtention', 'date_echeance'),
    'compteurs': ('id', 'equipement_id', 'libelle', 'unite'),
    'releves': ('id', 'compteur_id', 'date', 'valeur', 'utilisateur'),
    'controles_reglementaires': (
        'id', 'equipement_id', 'nature', 'texte_reference', 'periodicite_mois', 'organisme', 'derniere_date',
        'prochaine_date', 'rapport', 'observations', 'observations_levees',
    ),
    'codes_defaillance': ('id', 'famille', 'code', 'libelle'),
    'fournisseurs': ('id', 'nom', 'contact', 'telephone', 'email'),
    'achats': ('id', 'date', 'article_id', 'fournisseur_id', 'quantite', 'prix_unitaire', 'statut', 'date_reception'),
    'parametres': ('cle', 'valeur'),
    'journal': ('id', 'date_heure', 'poste', 'profil', 'table', 'id_ligne', 'action'),
    'wiki_pages': (
        'id', 'type', 'titre', 'cle', 'equipement_id', 'article_id', 'cause_code', 'rattache_a', 'texte', 'ot_cites',
        'liens', 'version', 'origine', 'modele', 'derniere_entree', 'valide_par', 'valide_le', 'cree_le',
        'modifie_le', 'statut',
    ),
    'wiki_journal': (
        'id', 'nature', 'ot_id', 'date_intervention', 'statut', 'anterieure', 'ordre', 'pages', 'changements',
        'contradictions', 'raisons', 'modele', 'essais', 'cree_le', 'traite_le', 'decide_par', 'decide_le', 'motif',
    ),
}

# Noms autorisés (re.ASCII : \d et \w ne reconnaissent que les caractères ASCII).
# Nom DEMANDÉ d'un document (PUT /api/documents/<nom>) ; le serveur l'enregistre sous « AAAAMMJJ-HHMMSS-<nom demandé> »
# (audit F4, nom_de_document_impose) : un nom enregistré est un nom demandé avec ce préfixe facultatif (les documents
# d'avant le lot 7 n'en ont pas).
MOTIF_NOM_DOCUMENT = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', re.ASCII)
PREFIXE_NOM_DOCUMENT = r'([0-9]{8}-[0-9]{6}-)?'
MOTIF_NOM_DOCUMENT_ENREGISTRE = re.compile(PREFIXE_NOM_DOCUMENT + MOTIF_NOM_DOCUMENT.pattern, re.ASCII)
# Nom d'une sauvegarde (mêmes règles que js/stockage-dossier.js) :
#   AAAA-MM-JJ                               quotidienne
#   AAAA-MM-JJ_HHMMSS                        manuelle
#   AAAA-MM-JJ_HHMMSS_avant-restauration     copie de sécurité faite avant une restauration
#   AAAA-MM-JJ_HHMMSS_avant-format-v<N>      faite juste avant le passage au format N des fichiers
#   AAAA-MM-JJ_HHMMSS_avant-import           faite juste avant un import de données (lot 5)
#   AAAA-MM-JJ_HHMMSS_avant-import-zip       faite juste avant un import ZIP, documents/ compris (T187, D170)
#   AAAA-MM-JJ_HHMMSS_avant-mise-a-jour      faite au premier démarrage d'une autre version de Prévo (T187, D170)
MOTIF_NOM_SAUVEGARDE = re.compile(
    r'[0-9]{4}-[0-9]{2}-[0-9]{2}(_[0-9]{6}(_avant-restauration|_avant-format-v[0-9]+|_avant-import-zip|_avant-import'
    r'|_avant-mise-a-jour)?)?', re.ASCII)
# Motifs acceptés par POST /api/sauvegarde {"motif": "…"} : liste FERMÉE (tout autre motif → 400).
# Le motif devient la fin du nom de la sauvegarde (« _avant-format-v2 »). Règle générale :
# « avant-format-v<N> » ; on n'ajoute ici que les versions que Prévo sait vraiment produire.
MOTIFS_SAUVEGARDE = ('avant-format-v2', 'avant-format-v3', 'avant-import', 'avant-import-zip', 'avant-mise-a-jour')

# Types MIME des documents acceptés (l'extension décide du type, jamais le contenu ; toute autre extension : 415).
# Audit F4 (§22.12) : « .doc » et « .xls » (formats binaires à macros) ne sont plus acceptés.
TYPES_DOCUMENTS = {
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'png': 'image/png',
    'gif': 'image/gif',
    'webp': 'image/webp',
    'pdf': 'application/pdf',
    'txt': 'text/plain; charset=utf-8',
    'csv': 'text/csv; charset=utf-8',
    'html': 'text/html; charset=utf-8',     # rapport mensuel figé (lot 3, ARCHITECTURE.md §15.1), servi en bac à sable
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'odt': 'application/vnd.oasis.opendocument.text',
    'ods': 'application/vnd.oasis.opendocument.spreadsheet',
}
# Documents que la page affiche elle-même (<img>, aperçu PDF) ou ouvre dans un onglet (rapport mensuel figé en html,
# « Ouvrir » de rapport-ecrans.js : « sandbox » interdit scripts et formulaires, ce qui est l'objet de l'audit F4) ;
# tout autre document est servi en téléchargement (Content-Disposition: attachment), toujours avec « sandbox » et nosniff.
TYPES_AFFICHABLES = ('jpg', 'jpeg', 'png', 'gif', 'webp', 'pdf', 'html')
# Signature (premiers octets) d'une image : un « .jpg » qui commence par « %PDF » est refusé (audit F4).
SIGNATURES_IMAGES = {
    'jpg': (b'\xff\xd8\xff',),
    'jpeg': (b'\xff\xd8\xff',),
    'png': (b'\x89PNG\r\n\x1a\n',),
    'gif': (b'GIF87a', b'GIF89a'),
    'webp': (b'RIFF',),                     # puis « WEBP » aux octets 8 à 11 (verifier_signature_image)
}

# Types MIME des fichiers statiques de l'application.
TYPES_STATIQUES = {
    'html': 'text/html; charset=utf-8',
    'js': 'text/javascript; charset=utf-8',
    'css': 'text/css; charset=utf-8',
    'svg': 'image/svg+xml; charset=utf-8',
    'woff2': 'font/woff2',
    'csv': 'text/csv; charset=utf-8',
    'json': 'application/json; charset=utf-8',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'png': 'image/png',
    'pdf': 'application/pdf',
    'txt': 'text/plain; charset=utf-8',
}
TYPE_PAR_DEFAUT = 'application/octet-stream'

# Liste blanche des fichiers statiques (ARCHITECTURE.md §14.7). Tout le reste répond 404.
# Les noms sont en minuscules : la comparaison ignore la casse, car Windows (NTFS) ne
# distingue pas « Index.html » de « index.html » ni « CSS/ » de « css/ ».
FICHIERS_PUBLICS = ('index.html', 'favicon.svg', 'guide.html')     # à la racine seulement
DOSSIERS_PUBLICS = (('css',), ('js',), ('acces',))                   # avec tout leur contenu ; acces/ : la porte (§22.6)
DOSSIER_FIXTURES = ('tests', 'fixtures')                             # seulement avec --servir-tests

# Noms réservés de Windows : « CON.txt » ou « nul.pdf » désignent un périphérique, pas un fichier.
NOMS_RESERVES_WINDOWS = (
    {'con', 'prn', 'aux', 'nul'}
    | {'com%d' % i for i in range(1, 10)}
    | {'lpt%d' % i for i in range(1, 10)}
)

# Un seul verrou pour TOUTES les écritures (et les lectures de CSV, pour qu'une version
# rendue corresponde toujours au contenu rendu). Deux postes qui écrivent en même temps
# sont donc traités l'un après l'autre.
VERROU_ECRITURE = threading.Lock()
# Audit F2 : au plus CONNEXIONS_MAX requêtes en cours en même temps, pour tout le processus (la porte et l'application
# partagent la limite, §22.6) ; une place est prise au premier octet d'une requête et rendue avec sa réponse
# (GestionnaireRequetes.handle_one_request) : une connexion keep-alive inactive n'en tient aucune. La 33e requête
# attend dans son fil : elle n'est ni refusée ni perdue.
SEMAPHORE_CONNEXIONS = threading.BoundedSemaphore(CONNEXIONS_MAX)


# ---------------------------------------------------------------------------
# Messages pour le navigateur (D157, T246)
# ---------------------------------------------------------------------------
# Un message que le navigateur peut afficher s'écrit traduisible('<code>', '<français>', nom=valeur…). Le français
# est la valeur de la clé serveur.<code> de js/i18n/fr.js, au caractère près (« py -X utf8 outils/controler_textes.py
# --domaine serveur » le vérifie) ; {nom} y est remplacé par la valeur, comme I18n.t. Le résultat est une chaîne
# (Traduisible, sous-classe de str) : le français d'avant, à l'identique, partout où le message était une chaîne
# (réponse, tests, console, journal). envoyer_json ajoute à côté de chaque champ qui en porte un « <champ>_code » et
# « <champ>_valeurs » (avec_codes) ; le navigateur affiche la clé dans sa langue, et le français reçu quand il ne
# connaît pas le code (StockageServeur.texte, js/stockage-serveur.js). Seules les valeurs écrites dans le français
# partent avec le code : la réponse n'en dit jamais plus qu'avant.
# Hors codes, par règle (outils/textes_serveur.py) : la console, le journal du serveur et les lanceurs (D157, Lot 4),
# les textes écrits dans les données (D156) et les marqueurs relus par le code.
# Le nom « traduisible » n'est jamais celui d'une variable locale (le contrôle le vérifie) : « texte » l'est souvent.
MOTIF_VARIABLE_TEXTE = re.compile(r'\{([A-Za-z_][A-Za-z0-9_]*)\}')     # MOTIF_VARIABLE de js/i18n.js
SUFFIXES_DU_CODE = ('_code', '_valeurs', '_sans_point')              # champs ajoutés à côté d'un message


class Traduisible(str):
    """Message pour le navigateur : le texte français (la chaîne elle-même), son code (clé serveur.<code>) et ses
    valeurs. sans_point : point final retiré (forme_sans_point), le navigateur le retire aussi de sa traduction."""
    code = None
    valeurs = None
    sans_point = False


def forme_du_pluriel_fr(n):
    """Catégorie du pluriel en français, celle de Intl.PluralRules('fr') pour one et other (0 et 1 au singulier)."""
    try:
        return 'one' if int(abs(float(n))) in (0, 1) else 'other'
    except (TypeError, ValueError):
        return 'other'


def valeur_gardee(valeur):
    """Valeur d'un message telle qu'elle part : un Traduisible (traduit à son tour par le navigateur), un entier, une
    liste (jointe par « , » dans le message) ; sinon sa forme écrite dans le message (str)."""
    if isinstance(valeur, Traduisible) or (isinstance(valeur, int) and not isinstance(valeur, bool)):
        return valeur
    if isinstance(valeur, (list, tuple)):
        return [element if isinstance(element, Traduisible) else str(element) for element in valeur]
    return str(valeur)


def traduisible(code, modele, **valeurs):
    """Message « code » : modele (le français, ou un pluriel {'one': …, 'other': …} choisi sur valeurs['n'], gardé
    pour le navigateur) où chaque {nom} est remplacé par sa valeur ; une variable sans valeur reste écrite, une valeur
    sans variable n'est pas gardée (elle ne part jamais)."""
    if isinstance(modele, dict):
        gabarit = modele.get(forme_du_pluriel_fr(valeurs.get('n')), modele['other'])
        noms = {nom for forme in modele.values() for nom in MOTIF_VARIABLE_TEXTE.findall(forme)} | {'n'}
    else:
        gabarit = modele
        noms = set(MOTIF_VARIABLE_TEXTE.findall(modele))
    gardees = {nom: valeur_gardee(valeur) for nom, valeur in valeurs.items() if nom in noms}

    def remplacer(trouve):
        valeur = gardees.get(trouve.group(1))
        if valeur is None:
            return trouve.group(0)
        return ', '.join(valeur) if isinstance(valeur, list) else str(valeur)
    resultat = Traduisible(MOTIF_VARIABLE_TEXTE.sub(remplacer, gabarit))
    resultat.code, resultat.valeurs = code, gardees
    return resultat


def forme_sans_point(message):
    """Le message sans son point final (une raison mise entre parenthèses) ; un Traduisible garde son code et ses
    valeurs, marqué sans_point."""
    if not isinstance(message, Traduisible):
        return str(message).rstrip('.')
    resultat = Traduisible(message.rstrip('.'))
    resultat.code, resultat.valeurs, resultat.sans_point = message.code, message.valeurs, True
    return resultat


def traduisible_de(erreur):
    """Message d'une exception levée avec un Traduisible (str(erreur) en ferait une chaîne sans code)."""
    message = erreur.args[0] if erreur.args else None
    return message if isinstance(message, Traduisible) else str(erreur)


def objet_du_message(message):
    """{"code", "texte" (le français), "valeurs"?, "sans_point"?} : un message dans une valeur ou dans une liste."""
    objet = {'code': message.code, 'texte': str(message)}
    if message.valeurs:
        objet['valeurs'] = valeurs_json(message.valeurs)
    if message.sans_point:
        objet['sans_point'] = True
    return objet


def valeurs_json(valeurs):
    """Valeurs d'un message pour la réponse : chaque Traduisible (seul ou dans une liste) devient objet_du_message."""
    def convertir(valeur):
        return objet_du_message(valeur) if isinstance(valeur, Traduisible) else valeur
    return {nom: [convertir(element) for element in valeur] if isinstance(valeur, list) else convertir(valeur)
            for nom, valeur in (valeurs or {}).items()}


def champs_du_message(champ, message):
    """{"<champ>_code", "<champ>_valeurs" (s'il en a), "<champ>_sans_point" (si vrai)} d'un Traduisible ; {} sinon."""
    if not isinstance(message, Traduisible) or not message.code:
        return {}
    champs = {champ + '_code': message.code}
    if message.valeurs:
        champs[champ + '_valeurs'] = valeurs_json(message.valeurs)
    if message.sans_point:
        champs[champ + '_sans_point'] = True
    return champs


def avec_codes(donnees):
    """Copie de donnees où chaque champ qui porte un Traduisible est suivi de son code et de ses valeurs
    (champs_du_message) ; une liste qui en porte (« rappels ») reçoit « <champ>_codes », un objet_du_message par
    élément (null pour une simple chaîne)."""
    if isinstance(donnees, dict):
        resultat = {}
        for cle, valeur in donnees.items():
            resultat[cle] = avec_codes(valeur)
            if isinstance(cle, str) and isinstance(valeur, Traduisible):
                resultat.update(champs_du_message(cle, valeur))
            elif isinstance(cle, str) and isinstance(valeur, (list, tuple)) \
                    and any(isinstance(element, Traduisible) for element in valeur):
                resultat[cle + '_codes'] = [objet_du_message(element) if isinstance(element, Traduisible) else None
                                            for element in valeur]
        return resultat
    if isinstance(donnees, (list, tuple)):
        return [avec_codes(element) for element in donnees]
    return donnees


def traduisible_relu(message, code, valeurs):
    """Message relu dans un fichier d'état (copie-externe.json, écrit par avec_codes) : le français, son code et ses
    valeurs ; le français seul sans code."""
    if not isinstance(message, str) or not isinstance(code, str) or not code:
        return message
    resultat = Traduisible(message)
    resultat.code, resultat.valeurs = code, valeurs if isinstance(valeurs, dict) else {}
    return resultat


# ---------------------------------------------------------------------------
# Erreurs HTTP
# ---------------------------------------------------------------------------

class ErreurHttp(Exception):
    """Erreur renvoyée au navigateur sous la forme {"erreur": "message"} + champs en plus."""

    entetes = None          # en-têtes en plus de la réponse (lot 7 : Retry-After d'un 429), posés après coup

    def __init__(self, statut, message, **champs_supplementaires):
        super().__init__(message)
        self.statut = statut
        self.message = message
        self.champs_supplementaires = champs_supplementaires


# T232 (texte de Nicolas, mêmes mots que js/stockage-dossier.js messageFichierOuvert) : fichier tenu par Excel ou un
# autre logiciel (423). Le message nomme le fichier ; le repli ne sert que si son nom n'est pas connu.
def message_fichier_verrouille(chemin):
    """Message du 423 pour ce fichier : son nom de base (celui que montre la fenêtre d'Excel), ou le repli."""
    nom = os.path.basename(str(chemin or ''))
    if nom:
        return traduisible('fichier.verrouille',
                           'Le fichier « {nom} » est ouvert dans Excel ou un autre logiciel : fermez-le, puis '
                           'réessayez.', nom=nom)
    return traduisible('fichier.verrouille_sans_nom',
                       'Un fichier du dossier de données est ouvert dans Excel ou un autre logiciel : fermez-le, '
                       'puis réessayez.')


# ---------------------------------------------------------------------------
# Console
# ---------------------------------------------------------------------------

def preparer_console():
    """Évite qu'un caractère non affichable (accent, tiret long…) fasse planter un print."""
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(errors='replace')
        except (AttributeError, ValueError):
            pass


def afficher(texte):
    """Affiche une ligne tout de suite (flush) : les tests lisent la console en direct."""
    if JOURNAL_SERVEUR is not None:
        JOURNAL_SERVEUR.ecrire(texte)
    if sys.stdout is None:          # lancé sans console (pythonw)
        return
    try:
        print(texte, flush=True)
    except (OSError, ValueError):
        pass


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Configuration du serveur : prevo.config.json (lot 7, ARCHITECTURE.md §22.1 et §22.2)
# ---------------------------------------------------------------------------

NOM_FICHIER_CONFIGURATION = 'prevo.config.json'
# En-têtes de sécurité des fichiers de l'application (audit F1, §22.13) ; les documents gardent « sandbox ».
ADRESSE_VERSION_PUBLIEE = 'https://prevo.pro'       # mise à jour signalée (§21) : seule origine extérieure lue
POLITIQUE_CONTENU = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                     "img-src 'self' data: blob:; connect-src 'self' %s; frame-ancestors 'none'; base-uri 'none'; "
                     "form-action 'self'; object-src 'none'")
ENTETES_SECURITE = {
    'X-Frame-Options': 'DENY',
    'Referrer-Policy': 'no-referrer',
    'Permissions-Policy': 'camera=(self), microphone=(self), geolocation=()',
}
DUREE_HSTS_S = 180 * 24 * 3600
CODE_SORTIE_REGLES = 2          # démarrage refusé : règle de portée non respectée (§22.1)
TAILLE_JOURNAL_SERVEUR = 1024 * 1024
NOMBRE_JOURNAUX_SERVEUR = 5
PORT_HTTPS_PAR_DEFAUT = 8443
PORTEES = ('ce-pc', 'atelier', 'dehors')
ECOUTES = ('127.0.0.1', '0.0.0.0')
# Porte d'entrée (lot 7, §22.6 ; D127, CS125, CS137) : hors de « ce PC », port_http ne sert à un client du réseau que
# la page acces/porte.html (autonome, sans donnée), ses fichiers et le certificat public de l'autorité ; la page
# interroge https://<même hôte>:<port_https>/api/ping et conduit le téléphone à l'application en https. Le port https
# est injecté dans l'attribut data-port-https de la page au moment de la servir : jamais une adresse codée en dur.
DOSSIER_PORTE = ('acces',)
DOSSIER_TEXTES = ('js', 'i18n')            # textes de l'interface par langue, servis aussi par la porte (multilingue)
PAGE_PORTE = os.path.join(DOSSIER_APPLICATION, 'acces', 'porte.html')
ATTRIBUT_PORT_HTTPS = 'data-port-https=""'
CHEMIN_CERTIFICAT_AUTORITE = ['acces', 'ca.crt']
TYPE_CERTIFICAT_AUTORITE = 'application/x-x509-ca-cert'
NOM_FICHIER_CERTIFICAT_AUTORITE = 'prevo-ca.crt'
# La politique de la porte n'autorise au dehors que l'origine https du même hôte (le ping de porte.js).
POLITIQUE_PORTE = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                   "connect-src 'self' %s; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'")
MESSAGE_SANS_AUTORITE = traduisible('porte.sans_autorite',
                                    'Aucune autorité locale sur ce serveur : le certificat a été fourni par votre '
                                    'informaticien, demandez-lui comment le faire reconnaître par le téléphone.')

# T250 : 4 Go par défaut, comme l'import ZIP (4 Go) : tout ce que Prévo exporte, Prévo peut le réimporter, d'un mode
# à l'autre (un export du mode dossier, qui n'a pas de plafond, entre dans le dossier des documents du serveur).
QUOTA_DOCUMENTS_MO_PAR_DEFAUT = 4096

# (clé, type, défaut, texte d'aide) : la même liste sert à lire le fichier, à --aide et au contrat.
CLES_CONFIGURATION = [
    ('portee', 'choix:ce-pc|atelier|dehors', 'ce-pc',
     "D'où Prévo peut être ouvert : ce PC seulement, le Wi-Fi de l'atelier, ou aussi hors de l'atelier. "
     "Au-delà de ce PC, mot de passe et https sont obligatoires."),
    ('ecoute', 'choix:127.0.0.1|0.0.0.0', '127.0.0.1',
     "Adresse d'écoute : 127.0.0.1 (ce PC seulement) ou 0.0.0.0 (le réseau)."),
    ('port_http', 'entier', PORT_PAR_DEFAUT,
     "Port de l'application sur ce PC et de la porte d'entrée sur le réseau. Changer de port rend les étiquettes "
     "imprimées caduques."),
    ('port_https', 'entier', PORT_HTTPS_PAR_DEFAUT, "Port de l'application en https sur le réseau."),
    ('noms', 'liste', [],
     "Noms par lesquels on appelle ce PC, en plus de son adresse et de son nom Windows (nom Tailscale, nom du "
     "réseau de l'entreprise). Un nom inconnu est refusé, par sécurité."),
    ('certificat', 'texte', '', "Certificat https du serveur (fichier PEM), avec sa clé."),
    ('cle', 'texte', '', "Clé privée du certificat (fichier PEM)."),
    ('certificat_auto', 'booleen', True,
     "Certificat fabriqué par Prévo pour l'atelier, à faire reconnaître une fois par appareil."),
    ('mandataire', 'booleen', False,
     "Prévo est derrière un mandataire (tailscale serve, Caddy, nginx, IIS) qui porte le https : les en-têtes "
     "X-Forwarded-Proto et X-Forwarded-Host venus de ce PC sont crus."),
    ('comptes', 'booleen', False,
     "Connexion obligatoire : chaque personne a son compte, ou son appareil enrôlé pour les demandeurs."),
    ('demandeurs_avec_compte', 'booleen', False,
     "Non : un demandeur donne son nom sur un appareil enrôlé par QR. Oui : chaque demandeur a un mot de passe."),
    ('session_heures', 'entier', 12,
     "Au bout de ce temps sans activité, il faut se reconnecter."),
    ('session_longue_jours', 'entier', 30, "Durée de « rester connecté sur cet appareil »."),
    ('invitation_heures', 'entier', 24, "Durée de validité d'une invitation d'appareils (1 à 168 heures)."),
    ('demarrage', 'choix:aucun|systeme|session', 'aucun',
     "Prévo démarre avec le PC (systeme), à l'ouverture de session (session), ou à la main (aucun)."),
    ('veille_desactivee', 'booleen', False, "Le PC ne se met plus en veille quand il est sur secteur."),
    ('copie_sauvegardes', 'texte', '',
     "Dossier où la sauvegarde du jour est copiée chaque nuit (clé USB, NAS, dossier synchronisé) ; vide : aucune copie."),
    ('quota_documents_mo', 'entier', QUOTA_DOCUMENTS_MO_PAR_DEFAUT,
     "Place maximale des documents joints, en mégaoctets."),
    ('ia_fournisseur', 'choix:ollama|openai', 'ollama',
     "Type du service d'IA : ollama (Ollama) ou openai (toute API compatible OpenAI : LM Studio, Mistral…)."),
    ('ia_url', 'texte', 'http://localhost:11434',
     "Adresse du service d'IA que tous les postes utilisent. Réglée ici seulement, jamais sur un téléphone."),
    ('ia_cle', 'texte', '', "Clé du service d'IA, gardée sur ce PC, jamais envoyée aux navigateurs. La variable "
                            "d'environnement PREVO_IA_CLE passe avant ; jamais en ligne de commande."),
    ('ia_en_ligne', 'booleen', False,
     "Autoriser un service d'IA en ligne : les textes envoyés partent chez ce fournisseur."),
]
CLES_CONNUES = {cle for cle, _, _, _ in CLES_CONFIGURATION}
BORNES_ENTIERS = {'port_http': (1, 65535), 'port_https': (1, 65535), 'session_heures': (1, 720),
                  'session_longue_jours': (1, 365), 'invitation_heures': (1, 168), 'quota_documents_mo': (1, 1048576)}


class ErreurConfiguration(Exception):
    """Configuration illisible ou règle de portée non respectée : le serveur ne démarre pas (code 2)."""


def reglages_par_defaut():
    return {cle: (list(defaut) if isinstance(defaut, list) else defaut) for cle, _, defaut, _ in CLES_CONFIGURATION}


def valeur_valide(cle, genre, valeur):
    """Contrôle une valeur lue dans le fichier ; ErreurConfiguration avec la clé fautive sinon."""
    if genre == 'booleen':
        if isinstance(valeur, bool):
            return valeur
    elif genre == 'entier':
        if isinstance(valeur, int) and not isinstance(valeur, bool):
            minimum, maximum = BORNES_ENTIERS.get(cle, (0, 10 ** 9))
            if minimum <= valeur <= maximum:
                return valeur
    elif genre == 'texte':
        if isinstance(valeur, str):
            return valeur.strip()
    elif genre == 'liste':
        if isinstance(valeur, list) and all(isinstance(element, str) for element in valeur):
            return [element.lower().strip() for element in valeur if element.strip()]
    elif genre.startswith('choix:'):
        if valeur in genre[len('choix:'):].split('|'):
            return valeur
    raise ErreurConfiguration(traduisible('config.valeur_invalide',
                                          'Configuration : la valeur de « {cle} » est invalide ({valeur}).',
                                          cle=cle, valeur=repr(valeur)))


def lire_configuration(chemin):
    """Réglages du fichier fusionnés aux défauts ; fichier absent : défauts. Clé inconnue : ignorée et signalée."""
    reglages = reglages_par_defaut()
    reglages['_fichier'] = chemin
    reglages['_present'] = False
    reglages['_inconnues'] = []
    if not chemin or not os.path.isfile(chemin):
        return reglages
    try:
        with open(chemin, 'rb') as fichier:
            contenu = json.loads(fichier.read().decode('utf-8-sig'))
    except (OSError, UnicodeDecodeError, ValueError) as erreur:
        raise ErreurConfiguration('Configuration illisible (%s) : %s. Corrigez le fichier ou supprimez-le pour '
                                  'repartir des réglages par défaut.' % (chemin, erreur))
    if not isinstance(contenu, dict):
        raise ErreurConfiguration('Configuration illisible (%s) : un objet JSON est attendu.' % chemin)
    genres = {cle: genre for cle, genre, _, _ in CLES_CONFIGURATION}
    for cle, valeur in contenu.items():
        if cle.startswith('_'):
            continue
        if cle not in CLES_CONNUES:
            reglages['_inconnues'].append(cle)
            continue
        reglages[cle] = valeur_valide(cle, genres[cle], valeur)
    reglages['_present'] = True
    return reglages


AIDE_CONFIGURATION = ('Configuration de Prévo. Chaque clé est décrite par « serveur.py --aide ». '
                      'Le CDC et docs/ARCHITECTURE.md §22 en donnent les règles.')


def ecrire_configuration(chemin, reglages):
    """Écrit le fichier de configuration (atomique), avec un commentaire d'en-tête « _aide »."""
    contenu = {'_aide': AIDE_CONFIGURATION}
    for cle, _, _, _ in CLES_CONFIGURATION:
        contenu[cle] = reglages.get(cle)
    ecrire_atomique(chemin, (json.dumps(contenu, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def modifier_configuration(chemin, modifications):
    """Change quelques clés du fichier de configuration sans toucher au reste : les clés inconnues et « _aide » sont
    gardées telles quelles (fichier absent : créé avec « _aide »). Écriture atomique ; rend le contenu écrit.
    OSError ou ValueError (fichier illisible) vers l'appelant, qui décide."""
    contenu = {}
    if chemin and os.path.isfile(chemin):
        with open(chemin, 'rb') as fichier:
            lu = json.loads(fichier.read().decode('utf-8-sig'))
        if isinstance(lu, dict):
            contenu = lu
    contenu.setdefault('_aide', AIDE_CONFIGURATION)
    contenu.update(modifications)
    ecrire_atomique(chemin, (json.dumps(contenu, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    return contenu


def texte_aide_configuration():
    lignes = ['Configuration de %s (fichier %s à côté de serveur.py ; la ligne de commande passe avant) :'
              % (NOM_APPLICATION, NOM_FICHIER_CONFIGURATION), '']
    for cle, genre, defaut, aide in CLES_CONFIGURATION:
        lignes.append('  %s  (%s ; défaut : %s)' % (cle, genre.replace('choix:', 'un parmi ').replace('|', ', '),
                                                    json.dumps(defaut, ensure_ascii=False)))
        lignes.append('      ' + aide)
    return '\n'.join(lignes)


def il_existe_un_responsable(config):
    """Vrai si un compte responsable actif existe (comptes du lot 7 : T150) ; faux tant qu'il n'y en a aucun."""
    fonction = globals().get('responsable_actif_existe')
    return bool(fonction and fonction(config))


def verifier_regles_portee(reglages, responsable_existe):
    """Règles de §22.1 : rend la liste des avertissements ; ErreurConfiguration (code 2) si une règle est violée.

    Écoute hors de ce PC ⇒ comptes exigés et (https ou mandataire) ; mandataire ⇒ comptes exigés ; comptes exigés
    sans aucun compte responsable ⇒ repli sur ce PC (l'assistant crée le compte), jamais d'écoute réseau.
    """
    avertissements = []
    https = bool(reglages.get('certificat') and reglages.get('cle')) or bool(reglages.get('_https_auto'))
    if bool(reglages.get('certificat')) != bool(reglages.get('cle')):
        raise ErreurConfiguration(traduisible('config.certificat_et_cle',
                                              'Certificat et clé vont ensemble : donnez les deux fichiers PEM, ou '
                                              'aucun.'))
    if reglages['ecoute'] != '127.0.0.1':
        if not reglages['comptes']:
            raise ErreurConfiguration(
                traduisible('config.reseau_sans_comptes',
                            'Prévo refuse d\'écouter sur le réseau sans mot de passe. Activez les comptes '
                            '(« comptes »: true) ou revenez à « ecoute »: "127.0.0.1" ; l\'assistant '
                            'd\'installation fait les deux (ouvrez Prévo sur ce PC).'))
        if not https and not reglages['mandataire']:
            raise ErreurConfiguration(
                traduisible('config.reseau_sans_https',
                            'Prévo refuse d\'écouter sur le réseau sans https. Donnez un certificat (« certificat » '
                            'et « cle »), laissez Prévo fabriquer le sien (« certificat_auto ») ou placez-le '
                            'derrière un mandataire ; l\'assistant d\'installation le fait pour vous.'))
    if reglages['mandataire'] and not reglages['comptes']:
        raise ErreurConfiguration(
            traduisible('config.mandataire_sans_comptes',
                        'Derrière un mandataire, les comptes sont obligatoires (« comptes »: true) : le mandataire '
                        'rend Prévo joignable au-delà de ce PC.'))
    if reglages['comptes'] and not responsable_existe and reglages['ecoute'] != '127.0.0.1':
        reglages['ecoute'] = '127.0.0.1'
        avertissements.append(traduisible('config.ecoute_ce_pc_sans_responsable',
                                          'Aucun compte responsable : Prévo n\'écoute que sur ce PC tant que '
                                          'l\'installation n\'est pas terminée.'))
    for cle in reglages.get('_inconnues', []):
        avertissements.append(traduisible('config.cle_inconnue', 'Configuration : clé inconnue « {cle} » ignorée.',
                                          cle=cle))
    return avertissements


class JournalServeur:
    """Journal du serveur sans console (pythonw) : donnees/journal-serveur.log, 5 fichiers de 1 Mo au plus."""

    def __init__(self, chemin):
        self.chemin = chemin
        self.verrou = threading.Lock()

    def ecrire(self, texte):
        with self.verrou:
            try:
                if os.path.exists(self.chemin) and os.path.getsize(self.chemin) >= TAILLE_JOURNAL_SERVEUR:
                    self.tourner()
                horodatage = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                with open(self.chemin, 'a', encoding='utf-8', newline='\n') as fichier:
                    fichier.write('%s %s\n' % (horodatage, texte))
            except OSError:
                pass

    def tourner(self):
        for numero in range(NOMBRE_JOURNAUX_SERVEUR - 1, 0, -1):
            ancien = '%s.%d' % (self.chemin, numero)
            suivant = '%s.%d' % (self.chemin, numero + 1)
            if os.path.exists(ancien):
                if numero + 1 >= NOMBRE_JOURNAUX_SERVEUR:
                    os.remove(ancien)
                else:
                    os.replace(ancien, suivant)
        os.replace(self.chemin, self.chemin + '.1')


JOURNAL_SERVEUR = None          # JournalServeur quand le serveur tourne sans console ou avec --journal


# ---------------------------------------------------------------------------
# Comptes (lot 7, ARCHITECTURE.md §22.3 ; D124) : donnees/acces/, lu et écrit par le serveur seul
# ---------------------------------------------------------------------------

LONGUEUR_MIN_MOT_DE_PASSE = 12
LONGUEUR_MAX_MOT_DE_PASSE = 256
ROLES_COMPTES = ('responsable', 'technicien', 'demandeur')
ALGO_SCRYPT = 'scrypt-n15-r8-p3'                 # OWASP : N = 2^15, r = 8, p = 3 (tenable sur un Raspberry Pi)
ALGO_PBKDF2 = 'pbkdf2-sha256-600000'             # repli si hashlib.scrypt manque (OpenSSL ancien)
SCRYPT_MEMOIRE_MAX = 64 * 1024 * 1024
LONGUEUR_PROVISOIRE = 16
ALPHABET_PROVISOIRE = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'   # sans 0/O, 1/l/I
COLONNES_JOURNAL_ACCES = ['date', 'qui', 'adresse', 'agent', 'resultat', 'tailscale']
RESULTATS_JOURNAL_ACCES = ('connexion', 'echec', 'bloque', 'deconnexion', 'appareil', 'invitation', 'revocation',
                           'reinitialisation', 'creation', 'modification')
DUREE_JOURNAL_ACCES_JOURS = 366
# Jamais sauvegardés : une session ne se restaure jamais ; la clé privée du certificat de l'atelier ne quitte pas le PC
# (copie externe sur une clé USB ou un NAS) et se refabrique au démarrage si elle manque (preparer_certificat_local).
FICHIERS_ACCES_NON_SAUVEGARDES = ('sessions.json', 'cle.pem')
VERROU_ACCES = threading.Lock()


class ErreurCompte(Exception):
    """Compte introuvable, mot de passe refusé, identifiant pris… (message en français pour l'utilisateur)."""


def dossier_acces(config):
    return os.path.join(config.dossier_donnees, 'acces')


def chemin_comptes(config):
    return os.path.join(dossier_acces(config), 'comptes.json')


def maintenant_s(config=None):
    """Heure du serveur en secondes : config.horloge, injectable pour les tests (blocage, durées de session)."""
    horloge = getattr(config, 'horloge', None) if config is not None else None
    return horloge() if horloge else time.time()


def maintenant_iso(config=None):
    return datetime.datetime.fromtimestamp(maintenant_s(config)).strftime('%Y-%m-%dT%H:%M:%S')


def hacher_mot_de_passe(mot_de_passe, sel=None, algo=None):
    """(algo, sel en base64, empreinte en base64). scrypt si disponible, sinon PBKDF2-SHA256 600 000."""
    sel = sel if sel is not None else os.urandom(16)
    if algo is None:
        algo = ALGO_SCRYPT if hasattr(hashlib, 'scrypt') else ALGO_PBKDF2
    octets = mot_de_passe.encode('utf-8')
    if algo == ALGO_SCRYPT:
        empreinte = hashlib.scrypt(octets, salt=sel, n=2 ** 15, r=8, p=3, maxmem=SCRYPT_MEMOIRE_MAX, dklen=32)
    elif algo == ALGO_PBKDF2:
        empreinte = hashlib.pbkdf2_hmac('sha256', octets, sel, 600000, dklen=32)
    else:
        raise ErreurCompte(traduisible('comptes.algorithme_inconnu',
                                       'Algorithme de mot de passe inconnu : {algo}.', algo=algo))
    return algo, base64.b64encode(sel).decode('ascii'), base64.b64encode(empreinte).decode('ascii')


def mot_de_passe_juste(compte, mot_de_passe):
    """Comparaison à temps constant ; faux pour un compte sans mot de passe ou un algorithme inconnu."""
    if not compte.get('empreinte') or not isinstance(mot_de_passe, str):
        return False
    try:
        _, _, calcule = hacher_mot_de_passe(mot_de_passe, base64.b64decode(compte['sel']), compte['algo'])
    except (ErreurCompte, ValueError, KeyError):
        return False
    return hmac.compare_digest(calcule.encode('ascii'), compte['empreinte'].encode('ascii'))


def verifier_mot_de_passe_choisi(mot_de_passe):
    """12 à 256 caractères, aucune règle de composition (CNIL 2022, ANSSI R21, R22)."""
    if not isinstance(mot_de_passe, str) or len(mot_de_passe) < LONGUEUR_MIN_MOT_DE_PASSE:
        raise ErreurCompte(traduisible('comptes.mot_de_passe_trop_court',
                                       {'one': 'Le mot de passe doit faire au moins {n} caractères ; une phrase de '
                                               'quelques mots est le plus simple à retenir.',
                                        'other': 'Le mot de passe doit faire au moins {n} caractères ; une phrase '
                                                 'de quelques mots est le plus simple à retenir.'},
                                       n=LONGUEUR_MIN_MOT_DE_PASSE))
    if len(mot_de_passe) > LONGUEUR_MAX_MOT_DE_PASSE:
        raise ErreurCompte(traduisible('comptes.mot_de_passe_trop_long',
                                       {'one': 'Le mot de passe fait plus de {n} caractères.',
                                        'other': 'Le mot de passe fait plus de {n} caractères.'},
                                       n=LONGUEUR_MAX_MOT_DE_PASSE))


def mot_de_passe_provisoire():
    return ''.join(secrets.choice(ALPHABET_PROVISOIRE) for _ in range(LONGUEUR_PROVISOIRE))


def lire_comptes(config):
    chemin = chemin_comptes(config)
    if not os.path.isfile(chemin):
        return []
    with open(chemin, 'rb') as fichier:
        contenu = json.loads(fichier.read().decode('utf-8'))
    return list(contenu.get('comptes', []))


def ecrire_comptes(config, comptes):
    os.makedirs(dossier_acces(config), exist_ok=True)
    octets = json.dumps({'version': 1, 'comptes': comptes}, ensure_ascii=False, indent=2).encode('utf-8')
    ecrire_atomique(chemin_comptes(config), octets)


def sans_accents(texte):
    decompose = unicodedata.normalize('NFKD', texte)
    return ''.join(c for c in decompose if not unicodedata.combining(c))


# T301 (D164, règle de Nicolas du 06/11 : une même personne n'a jamais deux identifiants, deux personnes jamais le
# même) : İ, I, ı et i sont une seule lettre pour Prévo (le turc les distingue ; « ı » n'a pas de décomposition).
PLIAGE_DES_I = str.maketrans({'İ': 'i', 'I': 'i', 'ı': 'i'})


def plier_nom(texte):
    """Nom, prénom ou identifiant ramené à des lettres simples, la seule règle pour les fabriquer et les comparer
    (T301) : İ, I, ı, i → i ; casse pliée (casefold : ß → ss) ; accents retirés (ş → s, ğ → g, ç → c, ö → o, ü → u,
    é → e). « Yılmaz » → « yilmaz » ; « IŞIK » et « Işık » → « isik » ; « Élodie » → « elodie »."""
    return sans_accents((texte or '').translate(PLIAGE_DES_I).casefold())


def identifiant_tape(texte):
    """Identifiant tapé (connexion, réinitialisation, recherche d'un compte) ramené à la forme des identifiants."""
    return plier_nom((texte or '').strip())


def ancienne_forme_identifiant(texte):
    """L'identifiant que la règle d'avant T301 tirait du texte tapé, segment par segment entre les points (« Işık » →
    « is-k » : le « ı » devenait un tiret). Les comptes créés avant T301 gardent leur identifiant (jamais renommés)."""
    return '.'.join(re.sub(r'[^a-z0-9]+', '-', sans_accents(segment).lower()).strip('-')
                    for segment in (texte or '').strip().split('.'))


def identifiant_depuis(prenom, nom, pris):
    """« Élodie Le Gall » → « elodie.le-gall » ; « Ayşe Işık » → « ayse.isik » (plier_nom, T301) ; « .2 », « .3 »… si
    l'identifiant est déjà pris."""
    def morceau(texte):
        texte = re.sub(r'[^a-z0-9]+', '-', plier_nom(texte)).strip('-')
        return texte or 'compte'
    base = morceau(prenom) + '.' + morceau(nom) if nom.strip() else morceau(prenom)
    candidat, numero = base, 2
    while candidat in pris:
        candidat, numero = '%s.%d' % (base, numero), numero + 1
    return candidat


def comptes_designes(comptes, identifiant):
    """Comptes que désigne un identifiant tapé (T301) : celui dont l'identifiant est exactement le texte tapé, s'il
    existe (l'identifiant exact tranche toujours) ; sinon tous ceux que le texte désigne une fois ramené à des lettres
    simples (« YILMAZ », « Yılmaz », « YİLMAZ » → yilmaz) ou par la règle d'avant T301 (« Işık » → is-k). Plusieurs :
    Prévo ne choisit jamais un compte à la place de la personne (règle de Nicolas, 07/11 ; trouver_compte,
    verifier_tentative)."""
    tape = (identifiant or '').strip()
    exact = [compte for compte in comptes if compte['identifiant'] == tape]
    if exact:
        return exact[:1]
    formes = {identifiant_tape(tape), ancienne_forme_identifiant(tape)} - {''}
    return [compte for compte in comptes if plier_nom(compte['identifiant']) in formes]


def trouver_compte(comptes, identifiant):
    """Le compte que désigne l'identifiant (comptes_designes), ou None : aucun, ou plusieurs (jamais un choix)."""
    designes = comptes_designes(comptes, identifiant)
    return designes[0] if len(designes) == 1 else None


def erreur_compte_introuvable(comptes, identifiant):
    """Compte introuvable, ou plusieurs comptes désignés (T301 : l'identifiant exact est demandé ; la liste est donnée
    au responsable et en ligne de commande sur le PC serveur, jamais à l'écran de connexion)."""
    designes = comptes_designes(comptes, identifiant)
    if len(designes) > 1:
        return ErreurCompte(traduisible('comptes.plusieurs',
                                        'Plusieurs comptes correspondent à « {identifiant} » : {identifiants}. Donnez '
                                        'l\'identifiant exact.', identifiant=identifiant,
                                        identifiants=', '.join(compte['identifiant'] for compte in designes)))
    return ErreurCompte(traduisible('comptes.introuvable', 'Compte introuvable : {identifiant}.',
                                    identifiant=identifiant))


def meme_personne(comptes, prenom, nom):
    """Le compte, actif ou non, au même prénom et au même nom une fois ramenés à des lettres simples (forme_de_nom),
    ou None (T301 : « Ayşe IŞIK » et « Ayşe Işık » sont la même personne)."""
    voulu = (forme_de_nom(prenom), forme_de_nom(nom))
    return next((compte for compte in comptes
                 if (forme_de_nom(compte.get('prenom', '')), forme_de_nom(compte.get('nom', ''))) == voulu), None)


def creer_compte(config, prenom, nom, role, mot_de_passe, technicien_id='', a_changer=False, identifiant=None,
                 origine=('', '', ''), autre_personne=False):
    """Crée un compte (rôle, technicien lié pour un technicien) ; rend le compte créé (sans son empreinte).
    origine : (adresse, agent, Tailscale) de la ligne du journal (T152 : la requête du responsable), vide sinon.
    T301 : un compte existe déjà au même prénom et au même nom (meme_personne) → refus (comptes.meme_personne, avec
    son identifiant), sauf autre_personne (le responsable a coché « C'est une autre personne »)."""
    prenom, nom = (prenom or '').strip(), (nom or '').strip()
    if not prenom:
        raise ErreurCompte(traduisible('comptes.prenom_obligatoire', 'Le prénom est obligatoire.'))
    if role not in ROLES_COMPTES:
        raise ErreurCompte(traduisible('comptes.role_inconnu', 'Rôle inconnu : {role}.', role=role))
    if role == 'technicien' and not technicien_id:
        raise ErreurCompte(traduisible('comptes.technicien_obligatoire',
                                       'Un compte de technicien est lié à un technicien de l\'équipe.'))
    verifier_mot_de_passe_choisi(mot_de_passe)
    with VERROU_ACCES:
        comptes = lire_comptes(config)
        pris = {c['identifiant'] for c in comptes}
        meme = None if autre_personne else meme_personne(comptes, prenom, nom)
        if meme is not None:
            raise ErreurCompte(traduisible('comptes.meme_personne',
                                           'Un compte existe déjà pour {personne} : « {identifiant} ». Réactivez-le ou '
                                           'donnez un autre nom ; si c\'est une autre personne, cochez « C\'est une '
                                           'autre personne ».', personne=(prenom + ' ' + nom).strip(),
                                           identifiant=meme['identifiant']))
        if identifiant:
            identifiant = identifiant_tape(identifiant)
            if identifiant in {plier_nom(existant) for existant in pris}:
                raise ErreurCompte(traduisible('comptes.identifiant_pris',
                                               'L\'identifiant « {identifiant} » est déjà pris.',
                                               identifiant=identifiant))
        else:
            identifiant = identifiant_depuis(prenom, nom, pris)
        algo, sel, empreinte = hacher_mot_de_passe(mot_de_passe)
        instant = maintenant_iso(config)
        compte = {'identifiant': identifiant, 'prenom': prenom, 'nom': nom, 'role': role,
                  'technicien_id': technicien_id or '', 'actif': True, 'algo': algo, 'sel': sel,
                  'empreinte': empreinte, 'a_changer': bool(a_changer), 'cree_le': instant,
                  'modifie_le': instant, 'mot_de_passe_le': instant}
        comptes.append(compte)
        ecrire_comptes(config, comptes)
    ecrire_journal_acces(config, identifiant, origine[0], origine[1], 'creation', origine[2])
    return compte_public(compte)


def compte_public(compte):
    """Le compte sans son sel ni son empreinte (ce qui peut partir vers un navigateur)."""
    return {cle: valeur for cle, valeur in compte.items() if cle not in ('sel', 'empreinte', 'algo')}


def changer_mot_de_passe(config, identifiant, nouveau, a_changer=False, journal='modification', origine=('', '', '')):
    """Nouveau mot de passe (changé ou réinitialisé) : toutes les sessions du compte sont fermées (§22.3).
    origine : (adresse, agent, Tailscale) de la ligne du journal, vide en ligne de commande."""
    verifier_mot_de_passe_choisi(nouveau)
    with VERROU_ACCES:
        comptes = lire_comptes(config)
        compte = trouver_compte(comptes, identifiant)
        if compte is None:
            raise erreur_compte_introuvable(comptes, identifiant)
        compte['algo'], compte['sel'], compte['empreinte'] = hacher_mot_de_passe(nouveau)
        compte['a_changer'] = bool(a_changer)
        compte['modifie_le'] = compte['mot_de_passe_le'] = maintenant_iso(config)
        ecrire_comptes(config, comptes)
    fermer_sessions_apres_changement(config, compte['identifiant'])
    ecrire_journal_acces(config, compte['identifiant'], origine[0], origine[1], journal, origine[2])


def reinitialiser_compte(config, identifiant, origine=('', '', '')):
    """Mot de passe provisoire (16 caractères, à changer à la première connexion) ; rendu une seule fois."""
    if not os.path.isfile(chemin_comptes(config)):
        raise ErreurCompte(traduisible('comptes.aucun_compte',
                                       'Aucun compte dans {dossier} : rien à réinitialiser. Terminez d\'abord '
                                       'l\'installation.', dossier=dossier_acces(config)))
    provisoire = mot_de_passe_provisoire()
    changer_mot_de_passe(config, identifiant, provisoire, a_changer=True, journal='reinitialisation', origine=origine)
    return provisoire


def modifier_compte(config, identifiant, origine=('', '', ''), **champs):
    """Prénom, nom, rôle, technicien lié ou actif ; jamais l'identifiant ni le mot de passe par cette voie."""
    permis = {'prenom', 'nom', 'role', 'technicien_id', 'actif'}
    with VERROU_ACCES:
        comptes = lire_comptes(config)
        compte = trouver_compte(comptes, identifiant)
        if compte is None:
            raise erreur_compte_introuvable(comptes, identifiant)
        for cle, valeur in champs.items():
            if cle not in permis:
                raise ErreurCompte(traduisible('comptes.champ_non_modifiable',
                                               'Champ non modifiable : {champ}.', champ=cle))
            if cle == 'role' and valeur not in ROLES_COMPTES:
                raise ErreurCompte(traduisible('comptes.role_inconnu', 'Rôle inconnu : {role}.', role=valeur))
            compte[cle] = bool(valeur) if cle == 'actif' else valeur
        if compte['role'] == 'technicien' and not compte.get('technicien_id'):
            raise ErreurCompte(traduisible('comptes.technicien_obligatoire',
                                           'Un compte de technicien est lié à un technicien de l\'équipe.'))
        if not any(c['role'] == 'responsable' and c.get('actif') for c in comptes):
            raise ErreurCompte(traduisible('comptes.dernier_responsable',
                                           'Il faut garder au moins un compte responsable actif.'))
        compte['modifie_le'] = maintenant_iso(config)
        ecrire_comptes(config, comptes)
    if not compte.get('actif'):
        fermer_sessions_apres_changement(config, compte['identifiant'])
    ecrire_journal_acces(config, compte['identifiant'], origine[0], origine[1], 'modification', origine[2])
    return compte_public(compte)


def responsable_actif_existe(config):
    try:
        return any(c.get('role') == 'responsable' and c.get('actif') for c in lire_comptes(config))
    except (OSError, ValueError):
        return False


def aucun_responsable_sur(config):
    """Vrai seulement quand on SAIT qu'aucun compte responsable actif n'existe (§22.10) : comptes.json absent, ou
    lisible sans responsable actif. Illisible ou de forme inattendue : faux — rien ne s'ouvre sans session (un
    compte créé par l'assistant écraserait alors tous les comptes) et la connexion dit pourquoi."""
    try:
        comptes = lire_comptes(config)
        return not any(c.get('role') == 'responsable' and c.get('actif') for c in comptes)
    except (OSError, ValueError, AttributeError, TypeError):
        return False


def cellule_journal(valeur):
    """Cellule du journal des connexions : texte d'une ligne, apostrophe devant = + - @ (§3.2)."""
    texte = re.sub(r'[\x00-\x1f\x7f]+', ' ', str(valeur or ''))[:200]
    if re.match(r'^[=+\-@\t\r]', texte):
        texte = "'" + texte
    return texte


def ecrire_journal_acces(config, qui, adresse, agent, resultat, tailscale=''):
    """Une ligne de donnees/acces/journal-acces.csv ; à la première écriture du jour, lignes de plus d'un an purgées."""
    chemin = os.path.join(dossier_acces(config), 'journal-acces.csv')
    jour = maintenant_iso(config)[:10]
    with VERROU_ACCES_JOURNAL:
        try:
            os.makedirs(dossier_acces(config), exist_ok=True)
            if getattr(config, '_purge_journal_acces', None) != jour and os.path.isfile(chemin):
                limite = (datetime.date.fromisoformat(jour) - datetime.timedelta(days=DUREE_JOURNAL_ACCES_JOURS)).isoformat()
                with open(chemin, encoding='utf-8-sig', newline='') as fichier:
                    lignes = list(csv.reader(fichier, delimiter=';'))
                gardees = [lignes[0]] + [l for l in lignes[1:] if l and l[0][:10] >= limite] if lignes else []
                if len(gardees) != len(lignes):
                    tampon = io.StringIO()
                    csv.writer(tampon, delimiter=';', lineterminator='\r\n').writerows(gardees)
                    ecrire_atomique(chemin, b'\xef\xbb\xbf' + tampon.getvalue().encode('utf-8'))
            config._purge_journal_acces = jour
            nouveau = not os.path.isfile(chemin)
            tampon = io.StringIO()
            ecrivain = csv.writer(tampon, delimiter=';', lineterminator='\r\n')
            if nouveau:
                ecrivain.writerow(COLONNES_JOURNAL_ACCES)
            ecrivain.writerow([cellule_journal(v) for v in (maintenant_iso(config), qui, adresse, agent, resultat, tailscale)])
            with open(chemin, 'ab') as fichier:
                fichier.write((b'\xef\xbb\xbf' if nouveau else b'') + tampon.getvalue().encode('utf-8'))
        except OSError:
            pass


VERROU_ACCES_JOURNAL = threading.Lock()


# ---------------------------------------------------------------------------
# Sessions et connexion (lot 7, ARCHITECTURE.md §22.3, §22.4 ; D124) : donnees/acces/sessions.json
# ---------------------------------------------------------------------------

NOM_COOKIE_SESSION = 'id'
MOTIF_JETON = re.compile(r'[A-Za-z0-9_-]{32,128}', re.ASCII)      # secrets.token_urlsafe(32) : 43 caractères
LONGUEUR_MAX_IDENTIFIANT = 200
GLISSEMENT_MIN_S = 60                   # « vu_le » réécrit au plus une fois par minute et par session
ECHECS_AVANT_ATTENTE = 5                # dès le 5e échec consécutif : min(2^(n-5), 8) s avant de répondre
ATTENTE_MAX_S = 8
ECHECS_AVANT_BLOCAGE = 10               # au 10e : blocage de 15 minutes, sans vérifier le mot de passe
DUREE_BLOCAGE_S = 15 * 60
ECHECS_PAR_ADRESSE = 20                 # au-delà de 20 échecs dans l'heure pour une adresse : 1 s par tentative
FENETRE_ADRESSE_S = 3600
ATTENTE_ADRESSE_S = 1
COMPTEURS_MAX = 10000                   # identifiants ou adresses suivis en mémoire ; au-delà, les plus anciens oubliés
TAILLE_MAX_CORPS_JETE = 64 * 1024       # refus avant la lecture du corps : au plus 64 Ko lus et jetés (audit F2)
QUI_INCONNU = '(inconnu)'               # journal : un identifiant sans compte n'est jamais recopié (un mot de passe
                                        # tapé dans la mauvaise case y finirait en clair)
SEL_FACTICE = bytes(16)                 # empreinte factice d'un identifiant inconnu : même calcul, même durée
CHAMPS_SESSION = ('identifiant', 'role', 'prenom', 'nom', 'technicien_id', 'a_changer', 'appareil')
MESSAGE_CONNEXION_REFUSEE = traduisible('sessions.connexion_refusee', 'Identifiant ou mot de passe incorrect.')
MESSAGE_IDENTIFIANT_AMBIGU = traduisible('sessions.identifiant_ambigu',
                                         'Plusieurs comptes correspondent à cet identifiant : tapez-le exactement, tel '
                                         'qu\'il vous a été donné.')
MESSAGE_SESSION_ABSENTE = traduisible('sessions.absente',
                                      'Connexion nécessaire : votre session est absente ou a expiré.')
MESSAGE_MOT_DE_PASSE_PROVISOIRE = traduisible('sessions.mot_de_passe_provisoire',
                                              'Mot de passe provisoire : choisissez votre mot de passe d\'abord.')
MESSAGE_ACTUEL_FAUX = traduisible('sessions.mot_de_passe_actuel_faux', 'Mot de passe actuel incorrect.')
MESSAGE_SANS_COMPTES = traduisible('sessions.sans_comptes',
                                   'Les comptes ne sont pas activés sur ce serveur (portée « ce PC ») : aucune '
                                   'connexion n\'est nécessaire.')
MESSAGE_COMPTES_ILLISIBLES = traduisible('comptes.fichier_illisible',
                                         'Fichier des comptes illisible (donnees/acces/comptes.json) : remettez-le '
                                         'depuis une sauvegarde.')
VERROU_SESSIONS = threading.Lock()


def chemin_sessions(config):
    return os.path.join(dossier_acces(config), 'sessions.json')


def empreinte_jeton(jeton):
    """Seule l'empreinte SHA-256 du jeton est gardée : sessions.json ne permet d'ouvrir aucune session."""
    return hashlib.sha256(jeton.encode('ascii')).hexdigest()


def secondes_de(texte_iso):
    """« 2026-10-26T10:00:00 » (heure locale, comme maintenant_iso) → secondes ; 0 si illisible (session expirée)."""
    try:
        return datetime.datetime.strptime(texte_iso, '%Y-%m-%dT%H:%M:%S').timestamp()
    except (TypeError, ValueError, OverflowError, OSError):
        return 0.0


def session_expiree(config, session, maintenant):
    """12 h sans activité (session_heures, glissantes) ; avec « rester », 30 jours depuis la connexion
    (session_longue_jours, comme le Max-Age du cookie)."""
    reglages = getattr(config, 'reglages', None) or {}
    if session.get('longue'):
        duree, depuis = reglages.get('session_longue_jours', 30) * 86400, session.get('cree_le')
    else:
        duree, depuis = reglages.get('session_heures', 12) * 3600, session.get('vu_le')
    return maintenant - secondes_de(depuis) > duree


def lire_sessions(config):
    """{empreinte du jeton: session} ; fichier absent ou illisible : aucune session (chacun se reconnecte)."""
    try:
        with open(chemin_sessions(config), 'rb') as fichier:
            contenu = json.loads(fichier.read().decode('utf-8'))
    except (OSError, ValueError, RecursionError):
        return {}
    if not isinstance(contenu, dict):
        return {}
    return {cle: session for cle, session in contenu.items() if isinstance(session, dict)}


def ecrire_sessions(config, sessions):
    """Écrit sessions.json (atomique), sessions expirées purgées ; à appeler sous VERROU_SESSIONS."""
    maintenant = maintenant_s(config)
    gardees = {cle: session for cle, session in sessions.items() if not session_expiree(config, session, maintenant)}
    os.makedirs(dossier_acces(config), exist_ok=True)
    ecrire_atomique(chemin_sessions(config), json.dumps(gardees, ensure_ascii=False, indent=1).encode('utf-8'))


def ouvrir_session(config, identifiant, longue, agent):
    """Nouvelle session : rend le jeton du cookie (secrets.token_urlsafe(32), neuf à chaque connexion), dont seule
    l'empreinte est écrite."""
    jeton = secrets.token_urlsafe(32)
    instant_iso = maintenant_iso(config)
    with VERROU_SESSIONS:
        sessions = lire_sessions(config)
        sessions[empreinte_jeton(jeton)] = {'identifiant': identifiant, 'cree_le': instant_iso, 'vu_le': instant_iso,
                                            'longue': bool(longue), 'agent': str(agent or '')[:200]}
        ecrire_sessions(config, sessions)
    return jeton


def session_du_jeton(config, jeton):
    """(empreinte, session) d'un jeton connu et non expiré, sinon None. Une session expirée est supprimée ; « vu_le »
    est réécrit au plus une fois par minute (12 h glissantes)."""
    if not isinstance(jeton, str) or not MOTIF_JETON.fullmatch(jeton):
        return None
    cle = empreinte_jeton(jeton)
    maintenant = maintenant_s(config)
    with VERROU_SESSIONS:
        sessions = lire_sessions(config)
        session = sessions.get(cle)
        if session is None:
            return None
        if session_expiree(config, session, maintenant):
            del sessions[cle]
            ecrire_sessions(config, sessions)
            return None
        if maintenant - secondes_de(session.get('vu_le')) >= GLISSEMENT_MIN_S:
            session['vu_le'] = maintenant_iso(config)
            ecrire_sessions(config, sessions)
    return cle, session


def fermer_session(config, cle):
    """Supprime une session (déconnexion, nouvelle connexion depuis le même navigateur)."""
    with VERROU_SESSIONS:
        sessions = lire_sessions(config)
        if sessions.pop(cle, None) is not None:
            ecrire_sessions(config, sessions)


def fermer_sessions_de(config, identifiant):
    """Supprime toutes les sessions d'un compte (déconnecter partout, mot de passe changé ou réinitialisé, compte
    désactivé) ; rend leur nombre."""
    identifiant = identifiant_tape(identifiant)
    with VERROU_SESSIONS:
        sessions = lire_sessions(config)
        restantes = {cle: session for cle, session in sessions.items() if session.get('identifiant') != identifiant}
        if len(restantes) != len(sessions):
            ecrire_sessions(config, restantes)
    return len(sessions) - len(restantes)


def fermer_sessions_apres_changement(config, identifiant):
    """Mot de passe changé, compte désactivé : ses sessions sont fermées. Si sessions.json ne peut pas être réécrit
    (verrouillé par un autre programme), chaque requête les refuse quand même : verifier_session revérifie le compte."""
    try:
        fermer_sessions_de(config, identifiant)
    except (ErreurHttp, OSError):
        pass


def comptes_du_serveur(config):
    """Comptes lus sous VERROU_ACCES (une lecture ne croise jamais une écriture) ; 500 au message clair si illisible."""
    with VERROU_ACCES:
        try:
            return lire_comptes(config)
        except (OSError, ValueError, AttributeError):
            raise ErreurHttp(500, MESSAGE_COMPTES_ILLISIBLES)


def identite_du_compte(compte, cle, longue):
    """Ce que le serveur sait de la requête : le compte et sa session (empreinte, « rester »), jamais le jeton."""
    return {'identifiant': compte['identifiant'], 'role': compte.get('role', ''), 'prenom': compte.get('prenom', ''),
            'nom': compte.get('nom', ''), 'technicien_id': compte.get('technicien_id', ''),
            'a_changer': bool(compte.get('a_changer')), 'appareil': False, 'cle': cle, 'longue': bool(longue)}


def session_publique(identite):
    """L'identité telle que GET /api/session la rend (§22.4), ou None."""
    return None if identite is None else {champ: identite[champ] for champ in CHAMPS_SESSION}


def valeurs_cookie(entete, nom):
    """Valeurs du cookie « nom » dans l'en-tête Cookie (4 au plus : un navigateur n'en envoie qu'une)."""
    valeurs = []
    for morceau in (entete or '').split(';'):
        cle, egal, valeur = morceau.strip().partition('=')
        if egal and cle.strip() == nom:
            valeurs.append(valeur.strip().strip('"'))
    return valeurs[:4]


def entete_cookie_session(jeton, https, max_age=None, nom=NOM_COOKIE_SESSION):
    """Set-Cookie de la session (§22.3) : id=<jeton>; Path=/; HttpOnly; SameSite=Lax[; Secure][; Max-Age=…] ;
    jeton vide et Max-Age=0 : le cookie est effacé. Le cookie d'appareil (nom « appareil », D125) a les mêmes
    attributs, avec un Max-Age d'un an."""
    morceaux = ['%s=%s' % (nom, jeton), 'Path=/', 'HttpOnly', 'SameSite=Lax']
    if https:
        morceaux.append('Secure')
    if max_age is not None:
        morceaux.append('Max-Age=%d' % max_age)
    return '; '.join(morceaux)


def verifier_session(config, entete_cookie):
    """Identité de la requête d'après le cookie « id » : jeton connu, session non expirée, compte actif dont le mot de
    passe n'a pas changé depuis la connexion ; sinon l'appareil enrôlé du cookie « appareil » (verifier_appareil,
    D125, rôle demandeur) ; sinon None."""
    for jeton in valeurs_cookie(entete_cookie, NOM_COOKIE_SESSION):
        trouvee = session_du_jeton(config, jeton)
        if trouvee is None:
            continue
        cle, session = trouvee
        try:
            compte = trouver_compte(comptes_du_serveur(config), session.get('identifiant'))
        except ErreurHttp:          # comptes illisibles : personne n'est reconnu ; /api/ping répond toujours,
            return None             # la connexion dit pourquoi
        if (compte is None or not compte.get('actif')
                or str(session.get('cree_le', '')) < str(compte.get('mot_de_passe_le', ''))):
            fermer_session(config, cle)
            continue
        return identite_du_compte(compte, cle, session.get('longue'))
    return verifier_appareil(config, entete_cookie)


# ---------------------------------------------------------------------------
# Appareils enrôlés (lot 7, ARCHITECTURE.md §22.3, §22.4 ; D125, CS123) : donnees/acces/appareils.json
# ---------------------------------------------------------------------------

NOM_COOKIE_APPAREIL = 'appareil'
DUREE_APPAREIL_JOURS = 365              # jeton d'appareil : 1 an glissant depuis sa dernière activité (vu_le)
INVITATION_HEURES_MIN, INVITATION_HEURES_MAX = 1, 168
LONGUEUR_MAX_NOM_DEMANDEUR = 60
LONGUEUR_MAX_LIBELLE_APPAREIL = 80
OUBLI_APPAREILS_JOURS = 30              # invitations finies, appareils révoqués ou expirés : oubliés après 30 jours
PREFIXE_INVITATION, PREFIXE_APPAREIL = 'INV-', 'AP-'
CHEMIN_ENROLEMENT = '/#/enroler/'       # lien d'une invitation : adresse http de la porte + ce chemin + le jeton
MESSAGE_INVITATION_REFUSEE = traduisible('appareils.invitation_refusee',
                                         'Invitation inconnue, expirée ou révoquée : demandez-en une nouvelle au '
                                         'responsable.')
MESSAGE_ENROLEMENT_DESACTIVE = traduisible('appareils.enrolement_desactive',
                                           'Enrôlement d\'appareils désactivé sur ce serveur '
                                           '(demandeurs_avec_compte) : chaque demandeur se connecte avec son compte.')
MESSAGE_APPAREIL_REFUSE = traduisible('appareils.refuse',
                                      'Cet appareil n\'est plus autorisé (révoqué, expiré ou enrôlement désactivé) : '
                                      'demandez une nouvelle invitation au responsable.')
VERROU_APPAREILS = threading.Lock()


def chemin_appareils(config):
    return os.path.join(dossier_acces(config), 'appareils.json')


def instant_iso(secondes):
    """Secondes → « AAAA-MM-JJTHH:MM:SS » en heure locale, comme maintenant_iso."""
    return datetime.datetime.fromtimestamp(secondes).strftime('%Y-%m-%dT%H:%M:%S')


def lire_appareils(config):
    """{'invitations': [...], 'appareils': [...]} ; fichier absent ou illisible : aucune invitation, aucun appareil
    (chaque appareil se réenrôle avec une invitation neuve)."""
    try:
        with open(chemin_appareils(config), 'rb') as fichier:
            contenu = json.loads(fichier.read().decode('utf-8'))
    except (OSError, ValueError, RecursionError):
        contenu = {}
    resultat = {}
    for cle in ('invitations', 'appareils'):
        liste = contenu.get(cle) if isinstance(contenu, dict) else None
        resultat[cle] = [element for element in liste if isinstance(element, dict)] if isinstance(liste, list) else []
    return resultat


def invitation_valide(invitation, maintenant):
    """Ni révoquée ni expirée (expire_le, heure locale)."""
    return not invitation.get('revoquee') and maintenant <= secondes_de(invitation.get('expire_le'))


def appareil_valide(appareil, maintenant):
    """Ni révoqué ni expiré : un an glissant depuis sa dernière activité (vu_le)."""
    return (not appareil.get('revoque')
            and maintenant - secondes_de(appareil.get('vu_le')) <= DUREE_APPAREIL_JOURS * 86400)


def ecrire_appareils(config, contenu):
    """Écrit appareils.json (atomique) ; à appeler sous VERROU_APPAREILS. Oubliés : les invitations finies depuis plus
    de 30 jours et les appareils révoqués ou expirés dont la dernière activité date de plus de 30 jours."""
    maintenant = maintenant_s(config)
    oubli = OUBLI_APPAREILS_JOURS * 86400
    invitations = [invitation for invitation in contenu['invitations']
                   if invitation_valide(invitation, maintenant)
                   or maintenant - secondes_de(invitation.get('expire_le')) <= oubli]
    appareils = [appareil for appareil in contenu['appareils']
                 if appareil_valide(appareil, maintenant) or maintenant - secondes_de(appareil.get('vu_le')) <= oubli]
    os.makedirs(dossier_acces(config), exist_ok=True)
    ecrire_atomique(chemin_appareils(config), json.dumps({'invitations': invitations, 'appareils': appareils},
                                                          ensure_ascii=False, indent=1).encode('utf-8'))


def identifiant_neuf(elements, prefixe):
    """INV-3F9A, AP-7C21… : quatre caractères hexadécimaux tirés au sort, jamais déjà pris dans la liste (un numéro
    ne se réemploie pas après l'oubli d'un ancien élément : le journal des connexions le cite)."""
    pris = {str(element.get('id', '')) for element in elements}
    while True:
        identifiant = prefixe + secrets.token_hex(2).upper()
        if identifiant not in pris:
            return identifiant


def invitation_publique(invitation, maintenant):
    """Ce que le responsable voit d'une invitation : jamais l'empreinte."""
    return {'id': str(invitation.get('id', '')), 'cree_le': str(invitation.get('cree_le', '')),
            'expire_le': str(invitation.get('expire_le', '')), 'revoquee': bool(invitation.get('revoquee')),
            'valide': invitation_valide(invitation, maintenant)}


def appareil_public(appareil, maintenant):
    """Ce que le responsable voit d'un appareil : jamais l'empreinte."""
    return {'id': str(appareil.get('id', '')), 'libelle': str(appareil.get('libelle', '')),
            'nom_demandeur': str(appareil.get('nom_demandeur', '')), 'cree_le': str(appareil.get('cree_le', '')),
            'vu_le': str(appareil.get('vu_le', '')), 'revoque': bool(appareil.get('revoque')),
            'valide': appareil_valide(appareil, maintenant)}


def libelle_appareil(agent):
    """Libellé d'un appareil d'après son navigateur (User-Agent) : la famille, jamais la chaîne entière."""
    agent = str(agent or '')
    for marque, libelle in (('iPhone', 'iPhone'), ('iPad', 'iPad'), ('Android', 'Téléphone ou tablette Android'),
                            ('Windows', 'PC Windows'), ('Macintosh', 'Mac'), ('CrOS', 'Chromebook'),
                            ('Linux', 'PC Linux')):
        if marque in agent:
            return libelle
    return ' '.join(agent.split())[:LONGUEUR_MAX_LIBELLE_APPAREIL] or 'Appareil'


def creer_invitation(config, heures=None):
    """Invitation du responsable (D125) : jeton rendu une seule fois (seule son empreinte est écrite), valable
    « heures » (1 à 168 ; invitation_heures de la configuration par défaut) ; rend (jeton, invitation publique)."""
    if heures is None:
        heures = (getattr(config, 'reglages', None) or {}).get('invitation_heures', 24)
    if (isinstance(heures, bool) or not isinstance(heures, int)
            or not INVITATION_HEURES_MIN <= heures <= INVITATION_HEURES_MAX):
        raise ErreurHttp(400, traduisible('appareils.invitation_heures',
                                          '« heures » : un entier de {minimum} à {maximum} est attendu.',
                                          minimum=INVITATION_HEURES_MIN, maximum=INVITATION_HEURES_MAX))
    jeton = secrets.token_urlsafe(32)
    maintenant = maintenant_s(config)
    with VERROU_APPAREILS:
        contenu = lire_appareils(config)
        invitation = {'id': identifiant_neuf(contenu['invitations'], PREFIXE_INVITATION),
                      'empreinte': empreinte_jeton(jeton), 'cree_le': instant_iso(maintenant),
                      'expire_le': instant_iso(maintenant + heures * 3600), 'revoquee': False}
        contenu['invitations'].append(invitation)
        ecrire_appareils(config, contenu)
    return jeton, invitation_publique(invitation, maintenant)


def enroler_appareil(config, jeton_invitation, nom, agent):
    """Téléphone qui ouvre une invitation (D125) : appareil écrit (libellé, nom du demandeur, dates), jeton d'appareil
    rendu une seule fois (seule son empreinte est écrite) ; 403 enrôlement désactivé (demandeurs_avec_compte), 400
    nom manquant, 401 au même message pour une invitation inconnue, expirée ou révoquée."""
    if (getattr(config, 'reglages', None) or {}).get('demandeurs_avec_compte'):
        raise ErreurHttp(403, MESSAGE_ENROLEMENT_DESACTIVE)
    nom = ' '.join(str(nom or '').split())
    if not nom or len(nom) > LONGUEUR_MAX_NOM_DEMANDEUR:
        raise ErreurHttp(400, traduisible('appareils.nom_attendu',
                                          {'one': 'Votre nom est attendu ({n} caractères au plus).',
                                           'other': 'Votre nom est attendu ({n} caractères au plus).'},
                                          n=LONGUEUR_MAX_NOM_DEMANDEUR))
    if not isinstance(jeton_invitation, str) or not MOTIF_JETON.fullmatch(jeton_invitation):
        raise ErreurHttp(401, MESSAGE_INVITATION_REFUSEE)
    cle = empreinte_jeton(jeton_invitation)
    jeton = secrets.token_urlsafe(32)
    maintenant = maintenant_s(config)
    with VERROU_APPAREILS:
        contenu = lire_appareils(config)
        invitation = next((i for i in contenu['invitations'] if i.get('empreinte') == cle), None)
        if invitation is None or not invitation_valide(invitation, maintenant):
            raise ErreurHttp(401, MESSAGE_INVITATION_REFUSEE)
        appareil = {'id': identifiant_neuf(contenu['appareils'], PREFIXE_APPAREIL), 'empreinte': empreinte_jeton(jeton),
                    'libelle': libelle_appareil(agent), 'nom_demandeur': nom, 'cree_le': instant_iso(maintenant),
                    'vu_le': instant_iso(maintenant), 'revoque': False, 'invitation': str(invitation.get('id', ''))}
        contenu['appareils'].append(appareil)
        ecrire_appareils(config, contenu)
    return jeton, appareil


def identite_de_l_appareil(appareil, cle):
    """Identité d'un appareil enrôlé : rôle demandeur, « appareil » vrai, le nom saisi comme nom (prénom vide),
    jamais le jeton."""
    return {'identifiant': 'appareil:' + str(appareil.get('id', '')), 'role': 'demandeur', 'prenom': '',
            'nom': str(appareil.get('nom_demandeur', '')), 'technicien_id': '', 'a_changer': False, 'appareil': True,
            'cle': cle, 'longue': True}


def verifier_appareil(config, entete_cookie):
    """Identité de la requête d'après le cookie « appareil » (D125) : jeton connu, appareil ni révoqué ni expiré ;
    « vu_le » réécrit au plus une fois par minute (un an glissant) ; None sinon, et toujours None quand
    demandeurs_avec_compte est vrai (enrôlement désactivé : les appareils déjà enrôlés ne comptent plus)."""
    if (getattr(config, 'reglages', None) or {}).get('demandeurs_avec_compte'):
        return None
    for jeton in valeurs_cookie(entete_cookie, NOM_COOKIE_APPAREIL):
        if not MOTIF_JETON.fullmatch(jeton):
            continue
        cle = empreinte_jeton(jeton)
        maintenant = maintenant_s(config)
        with VERROU_APPAREILS:
            contenu = lire_appareils(config)
            appareil = next((a for a in contenu['appareils'] if a.get('empreinte') == cle), None)
            if appareil is None or not appareil_valide(appareil, maintenant):
                continue
            if maintenant - secondes_de(appareil.get('vu_le')) >= GLISSEMENT_MIN_S:
                appareil['vu_le'] = instant_iso(maintenant)
                try:
                    ecrire_appareils(config, contenu)
                except (ErreurHttp, OSError):
                    pass                    # fichier verrouillé : l'appareil reste reconnu, vu_le attendra
        return identite_de_l_appareil(appareil, cle)
    return None


def revoquer(config, genre, identifiant=None):
    """Révoque une invitation (genre « invitations ») ou un appareil (« appareils ») par son id, ou tous les appareils
    (identifiant None) ; effet immédiat (chaque requête relit le fichier) ; rend les ids nouvellement révoqués ;
    404 id inconnu."""
    champ = 'revoquee' if genre == 'invitations' else 'revoque'
    trouves, revoques = [], []
    with VERROU_APPAREILS:
        contenu = lire_appareils(config)
        for element in contenu[genre]:
            if identifiant is None or element.get('id') == identifiant:
                trouves.append(element)
                if not element.get(champ):
                    element[champ] = True
                    revoques.append(str(element.get('id', '')))
        if identifiant is not None and not trouves:
            raise ErreurHttp(404, traduisible('appareils.introuvable',
                                              'Introuvable : {identifiant}.', identifiant=str(identifiant)[:40]))
        if revoques:
            ecrire_appareils(config, contenu)
    return revoques


class CompteursEchecs:
    """Échecs de connexion, en mémoire seulement (un redémarrage du serveur les remet à zéro) : par identifiant saisi
    (normalisé, qu'il existe ou non) et par adresse. Une tentative compte dès son début (reserver) : des tentatives
    lancées en même temps ne dépassent jamais les 10 essais avant le blocage."""

    def __init__(self):
        self.verrou = threading.Lock()
        self.par_identifiant = {}       # identifiant → {'echecs', 'dernier', 'bloque_jusqua'}
        self.par_adresse = {}           # adresse → instants de ses derniers échecs

    def adresse_ralentie(self, adresse, maintenant):
        """Vrai au-delà de 20 échecs venus de cette adresse dans l'heure écoulée."""
        with self.verrou:
            recents = [t for t in self.par_adresse.get(adresse, []) if maintenant - t < FENETRE_ADRESSE_S]
            if recents:
                self.par_adresse[adresse] = recents
            else:
                self.par_adresse.pop(adresse, None)
            return len(recents) >= ECHECS_PAR_ADRESSE

    def reserver(self, identifiant, maintenant):
        """Avant toute vérification : secondes de blocage restantes (refus sans vérifier), sinon 0 et la tentative
        est comptée."""
        with self.verrou:
            entree = self.par_identifiant.get(identifiant)
            if entree is not None and entree['bloque_jusqua']:
                if entree['bloque_jusqua'] > maintenant:
                    return entree['bloque_jusqua'] - maintenant
                entree = None                       # blocage écoulé : l'identifiant repart de zéro
            if entree is None:
                self.oublier_les_plus_anciens()
                entree = self.par_identifiant[identifiant] = {'echecs': 0, 'dernier': maintenant, 'bloque_jusqua': 0}
            if entree['echecs'] >= ECHECS_AVANT_BLOCAGE:          # dix essais déjà comptés, en cours en même temps
                entree['bloque_jusqua'] = maintenant + DUREE_BLOCAGE_S
                return DUREE_BLOCAGE_S
            entree['echecs'] += 1
            entree['dernier'] = maintenant
            return 0

    def echec(self, identifiant, adresse, maintenant):
        """Après un mot de passe faux : (échecs consécutifs, bloqué ou non) ; le 10e bloque pour 15 minutes."""
        with self.verrou:
            entree = self.par_identifiant.get(identifiant)
            if entree is None:                      # remis à zéro pendant la vérification (réussite en même temps)
                self.oublier_les_plus_anciens()
                entree = self.par_identifiant[identifiant] = {'echecs': 1, 'dernier': maintenant, 'bloque_jusqua': 0}
            entree['dernier'] = maintenant
            if entree['echecs'] >= ECHECS_AVANT_BLOCAGE and entree['bloque_jusqua'] <= maintenant:
                entree['bloque_jusqua'] = maintenant + DUREE_BLOCAGE_S
            if adresse not in self.par_adresse:
                self.oublier_les_plus_anciens()
            instants = self.par_adresse.setdefault(adresse, [])
            instants.append(maintenant)
            del instants[:-2 * ECHECS_PAR_ADRESSE]
            return entree['echecs'], entree['bloque_jusqua'] > maintenant

    def reussite(self, identifiant):
        """Mot de passe juste : le compteur de cet identifiant repart de zéro."""
        with self.verrou:
            self.par_identifiant.pop(identifiant, None)

    def oublier_les_plus_anciens(self):
        """Au-delà de COMPTEURS_MAX, la moitié la moins récente est oubliée (blocages en dernier) ; sous le verrou."""
        if len(self.par_identifiant) >= COMPTEURS_MAX:
            ordre = sorted(self.par_identifiant, key=lambda cle: (self.par_identifiant[cle]['bloque_jusqua'] > 0,
                                                                   self.par_identifiant[cle]['dernier']))
            for cle in ordre[:len(ordre) - COMPTEURS_MAX // 2]:
                del self.par_identifiant[cle]
        if len(self.par_adresse) >= COMPTEURS_MAX:
            ordre = sorted(self.par_adresse, key=lambda adresse: max(self.par_adresse[adresse], default=0))
            for adresse in ordre[:len(ordre) - COMPTEURS_MAX // 2]:
                del self.par_adresse[adresse]


def empreinte_factice(mot_de_passe):
    """Identifiant inconnu ou compte désactivé : le même calcul qu'une vraie vérification (la durée de la réponse ne
    dit pas si le compte existe) ; toujours faux."""
    hacher_mot_de_passe(mot_de_passe, sel=SEL_FACTICE)
    return False


def erreur_blocage(reste):
    """429 avec le temps restant : champ « attente_secondes » et en-tête Retry-After."""
    secondes = max(1, int(-(-reste // 1)))
    erreur = ErreurHttp(429, traduisible('sessions.trop_d_essais',
                                         {'one': 'Trop d\'essais : la connexion est bloquée pour cet identifiant. '
                                                 'Réessayez dans {n} min.',
                                          'other': 'Trop d\'essais : la connexion est bloquée pour cet '
                                                   'identifiant. Réessayez dans {n} min.'},
                                         n=-(-secondes // 60)), attente_secondes=secondes)
    erreur.entetes = {'Retry-After': str(secondes)}
    return erreur


def verifier_tentative(config, identifiant, mot_de_passe, origine, refus, journal_reussite='connexion'):
    """Vérifie un mot de passe saisi (§22.3) : rend le compte, sinon lève « refus » (ErreurHttp), ou 429 pendant un
    blocage, sans rien vérifier. Identifiant inconnu, compte désactivé et mot de passe faux suivent le même chemin
    (une empreinte calculée, même attente, même réponse). Dès le 5e échec consécutif, min(2^(n-5), 8) s d'attente
    avant de répondre ; au 10e, blocage de 15 minutes ; au-delà de 20 échecs dans l'heure pour une adresse, 1 s de
    plus par tentative. Chaque tentative va au journal des connexions, jamais le mot de passe.
    origine : (adresse, agent, Tailscale)."""
    adresse, agent, tailscale = origine
    tape = (identifiant or '').strip()[:LONGUEUR_MAX_IDENTIFIANT]
    echecs = config.echecs
    if echecs.adresse_ralentie(adresse, maintenant_s(config)):
        config.dormir(ATTENTE_ADRESSE_S)
    designes = comptes_designes(comptes_du_serveur(config), tape)
    compte = designes[0] if len(designes) == 1 else None
    # T301 : les essais comptent par compte désigné (« YILMAZ » et « yilmaz » ensemble), sinon par texte ramené.
    cle = compte['identifiant'] if compte is not None else identifiant_tape(tape)[:LONGUEUR_MAX_IDENTIFIANT]
    qui = compte['identifiant'] if compte is not None else QUI_INCONNU
    reste = echecs.reserver(cle, maintenant_s(config))
    if reste:
        ecrire_journal_acces(config, qui, adresse, agent, 'bloque', tailscale)
        raise erreur_blocage(reste)
    if len(designes) > 1:
        # T301 (règle de Nicolas, 07/11) : plusieurs comptes désignés (anciens comptes nés de « IŞIK » et « Işık ») :
        # refus sans vérifier aucun mot de passe, l'identifiant exact est demandé ; l'essai compte comme un échec.
        juste = empreinte_factice(mot_de_passe)              # même attente qu'un mot de passe vérifié ; toujours faux
        refus = ErreurHttp(refus.statut, MESSAGE_IDENTIFIANT_AMBIGU)
    elif compte is not None and compte.get('actif'):
        juste = mot_de_passe_juste(compte, mot_de_passe)
    else:
        juste = empreinte_factice(mot_de_passe)
    if juste:
        echecs.reussite(cle)
        if journal_reussite:
            ecrire_journal_acces(config, qui, adresse, agent, journal_reussite, tailscale)
        return compte
    nombre, bloque = echecs.echec(cle, adresse, maintenant_s(config))
    ecrire_journal_acces(config, qui, adresse, agent, 'echec', tailscale)
    if bloque:
        raise erreur_blocage(DUREE_BLOCAGE_S)
    if nombre >= ECHECS_AVANT_ATTENTE:
        config.dormir(min(2 ** (nombre - ECHECS_AVANT_ATTENTE), ATTENTE_MAX_S))
    raise refus


# ---------------------------------------------------------------------------
# Certificat local par mkcert (lot 7, ARCHITECTURE.md §22.6 ; D127) : empreinte vérifiée avant toute exécution
# ---------------------------------------------------------------------------

FICHIER_EMPREINTES_TIERS = os.path.join(DOSSIER_APPLICATION, 'outils', 'empreintes-tiers.json')
DOSSIER_OUTILS_TIERS = os.path.join(DOSSIER_APPLICATION, 'outils-tiers')
DELAI_MKCERT_S = 120


def nom_binaire_mkcert(version='1.4.4', systeme=None, machine=None):
    """« mkcert-v1.4.4-windows-amd64.exe », « mkcert-v1.4.4-linux-arm64 »… pour ce système."""
    systeme = (systeme or sys.platform).lower()
    machine = (machine or platform.machine()).lower()
    if systeme.startswith('win'):
        nom_systeme, suffixe = 'windows', '.exe'
    elif systeme == 'darwin':
        nom_systeme, suffixe = 'darwin', ''
    else:
        nom_systeme, suffixe = 'linux', ''
    if machine in ('amd64', 'x86_64', 'x64'):
        architecture = 'amd64'
    elif machine in ('arm64', 'aarch64'):
        architecture = 'arm64'
    elif machine.startswith('arm'):
        architecture = 'arm'
    else:
        architecture = machine
    return 'mkcert-v%s-%s-%s%s' % (version, nom_systeme, architecture, suffixe)


def lire_empreintes_tiers(chemin=None):
    with open(chemin or FICHIER_EMPREINTES_TIERS, 'rb') as fichier:
        return json.loads(fichier.read().decode('utf-8'))


def empreinte_fichier(chemin):
    calcul = hashlib.sha256()
    with open(chemin, 'rb') as fichier:
        for morceau in iter(lambda: fichier.read(1024 * 1024), b''):
            calcul.update(morceau)
    return calcul.hexdigest()


def verifier_empreinte(chemin, attendue):
    """ErreurConfiguration si le fichier manque ou si son SHA-256 n'est pas celui attendu (rien n'est exécuté)."""
    if not os.path.isfile(chemin):
        raise ErreurConfiguration(traduisible('mkcert.outil_introuvable',
                                              'Outil introuvable : {chemin}.', chemin=chemin))
    obtenue = empreinte_fichier(chemin)
    if not hmac.compare_digest(obtenue, (attendue or '').lower()):
        raise ErreurConfiguration(traduisible('mkcert.empreinte_inattendue',
                                              'Empreinte inattendue pour {fichier} : le fichier a été modifié ou '
                                              'n\'est pas celui livré avec Prévo. Il n\'a pas été exécuté.',
                                              fichier=os.path.basename(chemin)))


def trouver_mkcert(empreintes=None, dossier=None, nom=None):
    """Chemin de mkcert, empreinte vérifiée : outils-tiers/<nom> (livré dans le zip). ErreurConfiguration sinon."""
    empreintes = empreintes or lire_empreintes_tiers()
    nom = nom or nom_binaire_mkcert(empreintes['mkcert']['version'])
    fiche = empreintes['mkcert']['fichiers'].get(nom)
    if fiche is None:
        raise ErreurConfiguration(traduisible('mkcert.systeme_non_prevu',
                                              'Aucun mkcert prévu pour ce système ({systeme}).', systeme=nom))
    chemin = os.path.join(dossier or DOSSIER_OUTILS_TIERS, nom)
    verifier_empreinte(chemin, fiche['sha256'])
    return chemin


def executable_mkcert():
    """Chemin de mkcert pour l'assistant et le démarrage (§22.6, §22.10) : la variable d'environnement PREVO_MKCERT
    quand elle est posée (tests : tests/faux_mkcert.py ; un chemin qui n'existe pas vaut « absent », pour qu'un test ne
    lance jamais le vrai), sinon trouver_mkcert (outils-tiers/, empreinte vérifiée). ErreurConfiguration s'il manque."""
    variable = os.environ.get(VARIABLE_MKCERT, '').strip()
    if variable:
        if os.path.isfile(variable):
            return variable
        raise ErreurConfiguration(traduisible('mkcert.introuvable',
                                              'mkcert introuvable ({variable} = {chemin}).',
                                              variable=VARIABLE_MKCERT, chemin=variable))
    return trouver_mkcert()


def telecharger_mkcert(empreintes=None, dossier=None, nom=None, adresse=None):
    """Téléchargement de secours depuis la page des releases ; l'empreinte est vérifiée avant de garder le fichier."""
    empreintes = empreintes or lire_empreintes_tiers()
    nom = nom or nom_binaire_mkcert(empreintes['mkcert']['version'])
    fiche = empreintes['mkcert']['fichiers'].get(nom)
    if fiche is None:
        raise ErreurConfiguration(traduisible('mkcert.systeme_non_prevu',
                                              'Aucun mkcert prévu pour ce système ({systeme}).', systeme=nom))
    dossier = dossier or DOSSIER_OUTILS_TIERS
    os.makedirs(dossier, exist_ok=True)
    cible = os.path.join(dossier, nom)
    temporaire = cible + '.telechargement'
    adresse = adresse or (empreintes['mkcert']['source'] + nom)
    try:
        with urllib.request.urlopen(adresse, timeout=60) as reponse, open(temporaire, 'wb') as fichier:
            shutil.copyfileobj(reponse, fichier)
        verifier_empreinte(temporaire, fiche['sha256'])
        os.replace(temporaire, cible)
    except (OSError, urllib.error.URLError) as erreur:
        raise ErreurConfiguration(traduisible('mkcert.telechargement_impossible',
                                              'Téléchargement de mkcert impossible ({erreur}) : vérifiez la '
                                              'connexion à Internet, ou utilisez le zip de Prévo qui le contient.',
                                              erreur=erreur))
    finally:
        if os.path.exists(temporaire):
            os.remove(temporaire)
    if not nom.endswith('.exe'):
        os.chmod(cible, 0o755)
    return cible


def dossier_autorite(config):
    return os.path.join(dossier_acces(config), 'autorite')


def noms_du_certificat(config, adresses=None, noms_acceptes=None):
    """Noms couverts : adresses IP du PC, <nom>.local, <nom>, localhost, 127.0.0.1, puis les noms acceptés (ceux de
    la configuration, ou « noms_acceptes » : le brouillon de l'assistant, §22.10)."""
    noms = list(adresses if adresses is not None else adresses_ip_reseau())
    noms += [config.nom_pc + '.local', config.nom_pc, 'localhost', '127.0.0.1']
    noms += list(noms_acceptes if noms_acceptes is not None else config.reglages.get('noms', []))
    vus, uniques = set(), []
    for nom in noms:
        if nom and nom not in vus:
            vus.add(nom)
            uniques.append(nom)
    return uniques


def lancer_mkcert(executable, arguments, autorite):
    """Lance mkcert avec CAROOT = l'autorité de Prévo ; rend la sortie ; ErreurConfiguration si l'outil échoue."""
    environnement = dict(os.environ, CAROOT=autorite)
    commande = ([sys.executable, executable] if executable.endswith('.py') else [executable]) + list(arguments)
    try:
        resultat = subprocess.run(commande, capture_output=True, timeout=DELAI_MKCERT_S, env=environnement)
    except (OSError, subprocess.TimeoutExpired) as erreur:
        raise ErreurConfiguration(traduisible('mkcert.lancement_impossible',
                                              'mkcert n\'a pas pu être lancé ({erreur}).', erreur=erreur))
    sortie = (resultat.stdout + resultat.stderr).decode('utf-8', 'replace')
    if resultat.returncode != 0:
        raise ErreurConfiguration(traduisible('mkcert.echec',
                                              'mkcert a échoué : {sortie}', sortie=sortie.strip()[-400:]))
    return sortie


def preparer_certificat_local(config, executable, adresses=None, forcer=False, noms_acceptes=None):
    """Certificat de l'atelier dans donnees/acces/ (certificat.pem, cle.pem, certificat.json) ; refait si les noms
    ont changé (nouvelle adresse du PC, nouveau nom accepté). L'autorité reste dans donnees/acces/autorite/ ; sa clé
    (rootCA-key.pem) n'est jamais lue ni copiée par Prévo. Rend (certificat, clé, noms). « noms_acceptes » : les noms
    du brouillon de l'assistant (§22.10) à la place de ceux de la configuration."""
    acces = dossier_acces(config)
    autorite = dossier_autorite(config)
    os.makedirs(autorite, exist_ok=True)
    certificat = os.path.join(acces, 'certificat.pem')
    cle = os.path.join(acces, 'cle.pem')
    fiche = os.path.join(acces, 'certificat.json')
    noms = noms_du_certificat(config, adresses, noms_acceptes)
    if not forcer and os.path.isfile(certificat) and os.path.isfile(cle) and os.path.isfile(fiche):
        try:
            with open(fiche, 'rb') as lecture:
                if json.loads(lecture.read().decode('utf-8')).get('noms') == noms:
                    return certificat, cle, noms
        except ValueError:
            pass
    lancer_mkcert(executable, ['-cert-file', certificat, '-key-file', cle] + noms, autorite)
    if not (os.path.isfile(certificat) and os.path.isfile(cle)):
        raise ErreurConfiguration(traduisible('mkcert.certificat_absent',
                                              'mkcert n\'a pas produit le certificat attendu.'))
    ecrire_atomique(fiche, json.dumps({'noms': noms, 'cree_le': maintenant_iso(config)}, ensure_ascii=False).encode('utf-8'))
    return certificat, cle, noms


def certificat_du_serveur(config, reglages, mkcert=None):
    """(certificat, clé) du serveur (§22.1, §22.6) : ceux de la configuration s'ils sont donnés ; sinon, hors de
    « ce PC », ceux que mkcert fabrique (certificat_auto) ; (None, None) sur ce PC sans certificat (http, comme avant).
    ErreurConfiguration (démarrage refusé, code 2) quand Prévo devrait écouter sur le réseau et qu'aucun certificat ne
    vaut — mkcert absent, empreinte fausse ou échec compris : jamais d'écoute réseau en clair. « mkcert » : l'exécutable
    (tests) ; sinon trouver_mkcert (outils-tiers/, empreinte vérifiée)."""
    if reglages.get('certificat'):
        return reglages['certificat'], reglages['cle']
    if reglages['ecoute'] == '127.0.0.1':
        return None, None
    if not reglages.get('certificat_auto'):
        raise ErreurConfiguration(
            'Prévo refuse d\'écouter sur le réseau sans https. Donnez un certificat (« certificat » et « cle ») ou '
            'laissez Prévo fabriquer le sien (« certificat_auto »: true).')
    try:
        certificat, cle, _ = preparer_certificat_local(config, mkcert or executable_mkcert())
    except ErreurConfiguration as erreur:
        raise ErreurConfiguration(
            'Certificat de l\'atelier impossible (%s). Prévo n\'écoute pas sur le réseau sans https : remettez mkcert '
            'dans le dossier outils-tiers/ (il est dans le zip de Prévo), ou donnez « certificat » et « cle » dans %s.'
            % (str(erreur).rstrip('.'), NOM_FICHIER_CONFIGURATION))
    return certificat, cle



# ---------------------------------------------------------------------------
# Démarrer avec la machine (lot 7, ARCHITECTURE.md §22.9 ; D130) : scripts écrits par Prévo, jamais exécutés ici
# ---------------------------------------------------------------------------

NOM_TACHE_WINDOWS = 'Prevo'
NOM_REGLE_PARE_FEU = 'Prevo'
ECRAN_ETEINT_MINUTES = 15


def chaine_powershell(texte):
    """Littéral PowerShell entre apostrophes (une apostrophe se double)."""
    return "'" + str(texte).replace("'", "''") + "'"


def python_sans_console(dossier_prevo):
    """pythonw.exe du Python embarqué (zip de release), sinon celui qui fait tourner ce serveur."""
    embarque = os.path.join(dossier_prevo, 'python', 'pythonw.exe')
    if os.path.isfile(embarque):
        return embarque
    courant = sys.executable
    voisin = os.path.join(os.path.dirname(courant), 'pythonw.exe')
    return voisin if os.path.isfile(voisin) else courant


def script_installer_windows(dossier_prevo, python, ports, veille, mkcert=None, autorite=None):
    """Installer_demarrage.ps1 : tâche au démarrage (compte Système), règle du pare-feu (réseau privé, sous-réseau
    local), autorité mkcert, veille sur secteur ; les réglages de veille d'avant sont gardés pour le retrait."""
    serveur_py = os.path.join(dossier_prevo, 'serveur.py')
    sauvegarde_veille = os.path.join(dossier_prevo, 'donnees', 'acces', 'veille-avant.json')
    ports_texte = ','.join(str(p) for p in ports)
    lignes = [
        '# Installer_demarrage.ps1 : écrit par Prévo (assistant d\'installation, ARCHITECTURE.md §22.9).',
        '# Lancé par l\'assistant avec les droits d\'administrateur (une seule demande). À relire avant de l\'accepter.',
        '$ErrorActionPreference = \'Stop\'',
        '',
        '# 1. Prévo démarre avec le PC, sous le compte Système, sans fenêtre, 30 secondes après le démarrage.',
        'schtasks.exe --%% /create /tn "%s" /sc onstart /delay 0000:30 /ru System /rl HIGHEST /f /tr "\\"%s\\" \\"%s\\" --sans-navigateur"'
        % (NOM_TACHE_WINDOWS, python, serveur_py),
        'if ($LASTEXITCODE -ne 0) { throw "La tâche planifiée n\'a pas été créée (code $LASTEXITCODE)." }',
        '',
        '# 2. Pare-feu : les appareils du réseau privé de l\'atelier, et eux seuls, joignent Prévo.',
        'netsh.exe --%% advfirewall firewall delete rule name="%s"' % NOM_REGLE_PARE_FEU,
        'netsh.exe --%% advfirewall firewall add rule name="%s" dir=in action=allow protocol=TCP localport=%s profile=private remoteip=localsubnet program="%s"'
        % (NOM_REGLE_PARE_FEU, ports_texte, python),
        'if ($LASTEXITCODE -ne 0) { throw "La règle du pare-feu n\'a pas été créée (code $LASTEXITCODE)." }',
    ]
    if mkcert:
        lignes += [
            '',
            '# 3. Les navigateurs de ce PC font confiance au certificat de l\'atelier (autorité de Prévo).',
            '$env:CAROOT = %s' % chaine_powershell(autorite),
            '& %s -install' % chaine_powershell(mkcert),
            'if ($LASTEXITCODE -ne 0) { throw "L\'autorité de l\'atelier n\'a pas été installée (code $LASTEXITCODE)." }',
        ]
    if veille:
        lignes += [
            '',
            '# 4. Sur secteur, le PC ne se met plus en veille (l\'écran s\'éteint après %d minutes). Les réglages '
            'd\'avant sont gardés pour le retrait.' % ECRAN_ETEINT_MINUTES,
            'function Valeur-Secteur($sous, $reglage) {',
            '  $hex = (powercfg.exe /query SCHEME_CURRENT $sous $reglage | Select-String -Pattern \'0x[0-9a-fA-F]{8}\' -AllMatches).Matches.Value',
            '  return [Convert]::ToInt32($hex[-2], 16) / 60',
            '}',
            '$avant = @{ veille = Valeur-Secteur SUB_SLEEP STANDBYIDLE; veille_prolongee = Valeur-Secteur SUB_SLEEP HIBERNATEIDLE; '
            'ecran = Valeur-Secteur SUB_VIDEO VIDEOIDLE }',
            '$avant | ConvertTo-Json | Set-Content -Encoding UTF8 -Path %s' % chaine_powershell(sauvegarde_veille),
            'powercfg.exe /change standby-timeout-ac 0',
            'powercfg.exe /change hibernate-timeout-ac 0',
            'powercfg.exe /change monitor-timeout-ac %d' % ECRAN_ETEINT_MINUTES,
        ]
    lignes += ['', 'Write-Output "Prévo démarrera avec ce PC."', '']
    return '\r\n'.join(lignes)


def script_retirer_windows(dossier_prevo):
    """Retirer_demarrage.ps1 : l'inverse d'Installer_demarrage.ps1 (tâche, règle, réglages de veille d'avant)."""
    sauvegarde_veille = os.path.join(dossier_prevo, 'donnees', 'acces', 'veille-avant.json')
    lignes = [
        '# Retirer_demarrage.ps1 : écrit par Prévo (Paramètres, Accès et installation). Défait Installer_demarrage.ps1.',
        'schtasks.exe --%% /delete /tn "%s" /f' % NOM_TACHE_WINDOWS,
        'netsh.exe --%% advfirewall firewall delete rule name="%s"' % NOM_REGLE_PARE_FEU,
        '$fichier = %s' % chaine_powershell(sauvegarde_veille),
        'if (Test-Path $fichier) {',
        '  $avant = Get-Content -Raw -Path $fichier | ConvertFrom-Json',
        '  powercfg.exe /change standby-timeout-ac $avant.veille',
        '  powercfg.exe /change hibernate-timeout-ac $avant.veille_prolongee',
        '  powercfg.exe /change monitor-timeout-ac $avant.ecran',
        '  Remove-Item -Path $fichier',
        '}',
        'Write-Output "Prévo ne démarre plus avec ce PC."',
        '',
    ]
    return '\r\n'.join(lignes)


def script_session_windows(dossier_prevo, python):
    """Repli sans droits d'administrateur : tâche à l'ouverture de session ; sinon lanceur dans le dossier Démarrage."""
    serveur_py = os.path.join(dossier_prevo, 'serveur.py')
    lignes = [
        '# Demarrage_session.ps1 : écrit par Prévo. Sans droits d\'administrateur : Prévo démarre à l\'ouverture de',
        '# session de cet utilisateur (les téléphones n\'ont Prévo qu\'une fois la session ouverte).',
        'schtasks.exe --%% /create /tn "%s" /sc onlogon /rl LIMITED /f /tr "\\"%s\\" \\"%s\\" --sans-navigateur"'
        % (NOM_TACHE_WINDOWS, python, serveur_py),
        'if ($LASTEXITCODE -ne 0) {',
        '  $lanceur = Join-Path ([Environment]::GetFolderPath(\'Startup\')) \'Prevo.cmd\'',
        '  Set-Content -Encoding ASCII -Path $lanceur -Value (\'@start "" "%s" "%s" --sans-navigateur\')'
        % (python.replace("'", "''"), serveur_py.replace("'", "''")),
        '}',
        'Write-Output "Prévo démarrera à l\'ouverture de session."',
        '',
    ]
    return '\r\n'.join(lignes)


def unite_systemd(dossier_prevo, dossier_donnees, python='/usr/bin/python3', utilisateur='prevo'):
    return '\n'.join([
        '# /etc/systemd/system/prevo.service : écrit par Prévo (ARCHITECTURE.md §22.9).',
        '[Unit]',
        'Description=Prévo (GMAO)',
        'After=network-online.target',
        'Wants=network-online.target',
        '',
        '[Service]',
        'User=%s' % utilisateur,
        'Group=%s' % utilisateur,
        'WorkingDirectory=%s' % dossier_prevo,
        'ExecStart=%s %s/serveur.py --sans-navigateur' % (python, dossier_prevo.rstrip('/')),
        'Restart=on-failure',
        'RestartSec=5',
        'NoNewPrivileges=yes',
        'ProtectSystem=full',
        'ProtectHome=yes',
        'ReadWritePaths=%s' % dossier_donnees,
        '',
        '[Install]',
        'WantedBy=multi-user.target',
        '',
    ])


def commandes_systemd(dossier_prevo, utilisateur='prevo'):
    return [
        'sudo useradd --system --home %s --shell /usr/sbin/nologin %s' % (dossier_prevo, utilisateur),
        'sudo chown -R %s:%s %s' % (utilisateur, utilisateur, dossier_prevo),
        'sudo cp prevo.service /etc/systemd/system/prevo.service',
        'sudo systemctl daemon-reload',
        'sudo systemctl enable --now prevo',
    ]


def plist_launchd(dossier_prevo, python='/usr/bin/python3'):
    serveur_py = dossier_prevo.rstrip('/') + '/serveur.py'
    journal = dossier_prevo.rstrip('/') + '/donnees/journal-serveur.log'
    return '\n'.join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">',
        '<plist version="1.0"><dict>',
        '  <key>Label</key><string>pro.prevo.serveur</string>',
        '  <key>ProgramArguments</key><array><string>%s</string><string>%s</string><string>--sans-navigateur</string></array>'
        % (html_texte(python), html_texte(serveur_py)),
        '  <key>WorkingDirectory</key><string>%s</string>' % html_texte(dossier_prevo),
        '  <key>RunAtLoad</key><true/>',
        '  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>',
        '  <key>StandardOutPath</key><string>%s</string>' % html_texte(journal),
        '  <key>StandardErrorPath</key><string>%s</string>' % html_texte(journal),
        '</dict></plist>',
        '',
    ])


def html_texte(texte):
    return str(texte).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def produire_scripts_demarrage(config, dossier_sortie=None, dossier_prevo=None, python=None, veille=False,
                               mkcert=None, ports=None, systeme=None):
    """Écrit les scripts de démarrage du système (sans les exécuter) ; rend { nom de fichier : chemin }."""
    dossier_prevo = dossier_prevo or DOSSIER_APPLICATION
    dossier_sortie = dossier_sortie or dossier_prevo
    ports = ports or (config.reglages.get('port_http', PORT_PAR_DEFAUT), config.reglages.get('port_https', PORT_HTTPS_PAR_DEFAUT))
    systeme = systeme or sys.platform
    ecrits = {}

    def ecrire(nom, texte, bom=False):
        chemin = os.path.join(dossier_sortie, nom)
        ecrire_atomique(chemin, (b'\xef\xbb\xbf' if bom else b'') + texte.encode('utf-8'))
        ecrits[nom] = chemin

    if systeme.startswith('win'):
        python = python or python_sans_console(dossier_prevo)
        # BOM : PowerShell 5.1 lit un .ps1 sans BOM dans la page de code du système (accents abîmés).
        ecrire('Installer_demarrage.ps1', script_installer_windows(dossier_prevo, python, ports, veille, mkcert,
                                                                   dossier_autorite(config)), bom=True)
        ecrire('Retirer_demarrage.ps1', script_retirer_windows(dossier_prevo), bom=True)
        ecrire('Demarrage_session.ps1', script_session_windows(dossier_prevo, python), bom=True)
    elif systeme == 'darwin':
        ecrire('pro.prevo.serveur.plist', plist_launchd(dossier_prevo, python or '/usr/bin/python3'))
    else:
        ecrire('prevo.service', unite_systemd(dossier_prevo, config.dossier_donnees, python or '/usr/bin/python3'))
    return ecrits


DELAI_ELEVATION_S = 600                 # l'invite UAC puis le script : dix minutes au plus


def commande_powershell(script, eleve=True):
    """Ligne de commande qui lance un script PowerShell écrit par Prévo (§22.9, §22.10) : avec « eleve », une seule
    invite UAC (Start-Process -Verb RunAs, attendu, code de sortie rendu) ; sinon le script tel quel (repli à
    l'ouverture de session, sans droits)."""
    if not eleve:
        return ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', script]
    arguments = ','.join(chaine_powershell(a) for a in ('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', script))
    return ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command',
            '$p = Start-Process -FilePath powershell.exe -ArgumentList @(%s) -Verb RunAs -Wait -PassThru; '
            'exit $p.ExitCode' % arguments]


def lancer_script_powershell(script, eleve=True):
    """Lance Installer_demarrage.ps1 avec les droits d'administrateur (une seule élévation, sur le clic de
    l'assistant) ou Demarrage_session.ps1 sans eux ; rend {"ok", "code", "message"}. Jamais appelée par les tests
    (config.lancer_eleve y est remplacée) : elle demande l'élévation et change le système."""
    if not sys.platform.startswith('win'):
        return {'ok': False, 'code': None,
                'message': traduisible('powershell.windows_seulement', 'Scripts PowerShell : Windows seulement.')}
    try:
        resultat = subprocess.run(commande_powershell(script, eleve), capture_output=True, timeout=DELAI_ELEVATION_S)
    except (OSError, subprocess.TimeoutExpired) as erreur:
        return {'ok': False, 'code': None,
                'message': traduisible('powershell.lancement_impossible',
                                       'PowerShell n\'a pas pu lancer {script} ({erreur}).',
                                       script=os.path.basename(script), erreur=erreur)}
    sortie = (resultat.stdout + resultat.stderr).decode('utf-8', 'replace').strip()
    if resultat.returncode != 0:
        if sortie:
            message = traduisible('powershell.echec_sortie',
                                  'Élévation refusée ou script en échec ({script}, code {code}) : rien n\'a été '
                                  'installé. Vous pouvez relancer, ou choisir « à l\'ouverture de session » (sans '
                                  'droits d\'administrateur).\n{sortie}',
                                  script=os.path.basename(script), code=resultat.returncode, sortie=sortie[-300:])
        else:
            message = traduisible('powershell.echec',
                                  'Élévation refusée ou script en échec ({script}, code {code}) : rien n\'a été '
                                  'installé. Vous pouvez relancer, ou choisir « à l\'ouverture de session » (sans '
                                  'droits d\'administrateur).',
                                  script=os.path.basename(script), code=resultat.returncode)
        return {'ok': False, 'code': resultat.returncode, 'message': message}
    # La sortie du script (Write-Output du lanceur, D157 : Lot 4) est rendue telle quelle.
    return {'ok': True, 'code': 0,
            'message': sortie[-300:] or traduisible('powershell.script_execute', 'Script exécuté.')}


def certificat_de_l_autorite(config):
    """Octets du certificat PUBLIC de l'autorité (rootCA.pem), servi aux téléphones ; None s'il n'existe pas."""
    return lire_octets(os.path.join(dossier_autorite(config), 'rootCA.pem'))


def copier_acces_dans_sauvegarde(config, dossier_sauvegarde):
    """Copie donnees/acces/ (comptes, appareils, journal ; jamais les sessions) dans une sauvegarde. Jamais
    restauré par /api/restauration : un compte révoqué ne revient pas avec une vieille sauvegarde."""
    source = dossier_acces(config)
    if not os.path.isdir(source):
        return
    cible = os.path.join(dossier_sauvegarde, 'acces')
    os.makedirs(cible, exist_ok=True)
    for nom in os.listdir(source):
        chemin = os.path.join(source, nom)
        if os.path.isfile(chemin) and nom not in FICHIERS_ACCES_NON_SAUVEGARDES and not nom.startswith('.'):
            shutil.copy2(chemin, os.path.join(cible, nom))


# ---------------------------------------------------------------------------
# Tailscale (lot 7, ARCHITECTURE.md §22.8 ; D128, CS127) : détecté et guidé, jamais installé ; commandes locales
# seulement (« tailscale version », « status --json », « serve … », « serve status --json », « set --unattended »
# sur un clic), jamais une requête réseau de Prévo vers Tailscale, jamais « tailscale up ».
# ---------------------------------------------------------------------------

DELAI_TAILSCALE_S = 5
INTERVALLE_TAILSCALE_S = 600            # /api/info rafraîchit la détection au plus une fois par 10 minutes
JOURS_ALERTE_CLE_TAILSCALE = 14         # l'accueil du responsable signale une clé qui expire sous 14 jours
LIEN_TELECHARGEMENT_TAILSCALE = 'https://tailscale.com/download'        # montré à l'utilisateur, jamais ouvert ici
CONSOLE_TAILSCALE = 'https://login.tailscale.com/admin/machines'        # idem : où désactiver l'expiration de clé
CHEMINS_TAILSCALE = {
    'win32': [r'C:\Program Files\Tailscale\tailscale.exe'],
    'darwin': ['/Applications/Tailscale.app/Contents/MacOS/Tailscale'],
    'linux': ['/usr/bin/tailscale'],
}
COMMANDES_TAILSCALE_INTERDITES = ('up', 'down', 'login', 'logout', 'install', 'update')   # jamais lancées par Prévo
VERROU_TAILSCALE = threading.Lock()     # une détection à la fois ; config.tailscale lu et posé sous ce verrou
RAPPELS_TAILSCALE = (
    traduisible('tailscale.rappel_expiration',
                'Désactivez l\'expiration de clé de ce PC dans la console Tailscale ({adresse} : Machines › ce PC › '
                'Disable key expiry) ; sinon, au bout de quelques mois, les téléphones ne joignent plus Prévo.',
                adresse=CONSOLE_TAILSCALE),
    traduisible('tailscale.rappel_veille',
                'Empêchez la veille du PC serveur (Démarrer avec la machine, D130) : un PC en veille ne répond plus, '
                'Tailscale ou pas.'),
)


class ErreurTailscale(Exception):
    """tailscale n'a pas pu être lancé, a dépassé le délai ou a rendu un code non nul : la raison est lisible."""


def executable_tailscale(executable=None):
    """Chemin de tailscale : celui donné ; sinon PREVO_TAILSCALE (tests : le faux tailscale ; un chemin qui n'existe
    pas vaut « absent », pour qu'un test ne lance jamais le vrai) ; sinon le chemin standard du système, puis le
    PATH. None quand rien n'est trouvé."""
    if executable:
        return executable
    variable = os.environ.get(VARIABLE_TAILSCALE, '').strip()
    if variable:
        return variable if os.path.isfile(variable) else None
    systeme = 'win32' if sys.platform.startswith('win') else ('darwin' if sys.platform == 'darwin' else 'linux')
    for chemin in CHEMINS_TAILSCALE[systeme]:
        if os.path.isfile(chemin):
            return chemin
    return shutil.which('tailscale')


def lancer_tailscale(executable, arguments, delai=DELAI_TAILSCALE_S):
    """Lance tailscale avec ces arguments (jamais par un shell, sans fenêtre sous Windows, jamais une commande de
    COMMANDES_TAILSCALE_INTERDITES) ; rend sa sortie standard (texte). ErreurTailscale si l'outil manque, dépasse le
    délai ou rend un code non nul."""
    arguments = [str(argument) for argument in arguments]
    if not arguments or arguments[0] in COMMANDES_TAILSCALE_INTERDITES:
        raise ErreurTailscale(traduisible('tailscale.commande_interdite',
                                          'Prévo ne lance jamais « tailscale {commande} » : c\'est à vous de le '
                                          'faire.', commande=' '.join(arguments)))
    commande = ([sys.executable, executable] if executable.endswith('.py') else [executable]) + arguments
    options = {'creationflags': subprocess.CREATE_NO_WINDOW} if hasattr(subprocess, 'CREATE_NO_WINDOW') else {}
    try:
        resultat = subprocess.run(commande, capture_output=True, timeout=delai, **options)
    except subprocess.TimeoutExpired:
        raise ErreurTailscale(traduisible('tailscale.delai_depasse',
                                          {'one': 'tailscale {commande} ne répond pas (délai de {n} s dépassé).',
                                           'other': 'tailscale {commande} ne répond pas (délai de {n} s dépassé).'},
                                          commande=arguments[0], n=delai))
    except OSError as erreur:
        raise ErreurTailscale(traduisible('tailscale.lancement_impossible',
                                          'tailscale n\'a pas pu être lancé ({erreur}).', erreur=erreur))
    if resultat.returncode != 0:
        sortie = (resultat.stderr or resultat.stdout).decode('utf-8', 'replace').strip()
        if sortie:
            raise ErreurTailscale(traduisible('tailscale.echec', 'tailscale {commande} a échoué : {sortie}',
                                              commande=' '.join(arguments), sortie=sortie[-300:]))
        raise ErreurTailscale(traduisible('tailscale.echec_code', 'tailscale {commande} a échoué : code {code}',
                                          commande=' '.join(arguments), code=resultat.returncode))
    return resultat.stdout.decode('utf-8', 'replace')


def lire_json_tailscale(texte):
    """Objet JSON d'une sortie de tailscale ; None si elle ne s'y lit pas (« No serve config », vide…)."""
    try:
        valeur = json.loads(texte)
    except (TypeError, ValueError):
        return None
    return valeur if isinstance(valeur, dict) else None


def expiration_cle_tailscale(valeur, maintenant=None):
    """(« AAAA-MM-JJTHH:MM:SS » en heure locale, jours entiers restants — négatif si la clé a expiré) d'après
    Self.KeyExpiry (RFC 3339, UTC) ; (None, None) si la valeur manque, est vide, ne se lit pas ou vaut la date zéro de
    Go (0001-01-01 : expiration désactivée)."""
    if not isinstance(valeur, str) or not valeur.strip():
        return None, None
    texte = valeur.strip()
    if texte.endswith('Z'):
        texte = texte[:-1] + '+00:00'
    try:
        instant = datetime.datetime.fromisoformat(texte)
    except ValueError:
        return None, None
    if instant.year < 1971:
        return None, None
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=datetime.timezone.utc)
    maintenant = maintenant if maintenant is not None else time.time()
    jours = int((instant.timestamp() - maintenant) // 86400)
    return instant.astimezone().strftime('%Y-%m-%dT%H:%M:%S'), jours


def detecter_tailscale(executable=None, delai=DELAI_TAILSCALE_S, maintenant=None):
    """État de Tailscale sur ce PC par « tailscale version », « tailscale status --json » puis « tailscale serve status
    --json » (commandes locales, jamais une requête réseau) : {"present": False, "raison"} quand l'exécutable manque,
    que « version » échoue ou que le délai est dépassé ; sinon {"present": True, "version", "connecte" (BackendState
    « Running »), "nom" (Self.DNSName sans le point final, minuscules ; None sans nom), "expiration_cle" (heure
    locale ; None sans expiration), "jours_avant_expiration" (entier ; None sans expiration), "serve" (sortie de
    « serve status --json » si elle se lit ; None sinon), "raison" (None, ou pourquoi « status » n'a rien dit)}.
    Jamais d'exception vers l'appelant (console, /api/info, assistant)."""
    try:
        chemin = executable_tailscale(executable)
        if not chemin:
            return {'present': False,
                    'raison': traduisible('tailscale.raison_introuvable', 'Tailscale introuvable sur ce PC')}
        version = lancer_tailscale(chemin, ['version'], delai).strip().splitlines()
        resultat = {'present': True, 'version': version[0].strip() if version else '', 'connecte': False, 'nom': None,
                    'expiration_cle': None, 'jours_avant_expiration': None, 'serve': None, 'raison': None}
        try:
            etat = lire_json_tailscale(lancer_tailscale(chemin, ['status', '--json'], delai))
        except ErreurTailscale as erreur:
            resultat['raison'] = traduisible_de(erreur)
            return resultat
        if etat is None:
            resultat['raison'] = traduisible('tailscale.raison_status_illisible',
                                             'tailscale status --json : réponse illisible')
            return resultat
        soi = etat.get('Self') if isinstance(etat.get('Self'), dict) else {}
        nom = soi.get('DNSName') if isinstance(soi.get('DNSName'), str) else ''
        resultat['connecte'] = etat.get('BackendState') == 'Running'
        resultat['nom'] = nom.strip().rstrip('.').lower() or None
        resultat['expiration_cle'], resultat['jours_avant_expiration'] = expiration_cle_tailscale(soi.get('KeyExpiry'),
                                                                                                  maintenant)
        try:
            resultat['serve'] = lire_json_tailscale(lancer_tailscale(chemin, ['serve', 'status', '--json'], delai))
        except ErreurTailscale:
            resultat['serve'] = None
        return resultat
    except ErreurTailscale as erreur:
        return {'present': False, 'raison': forme_sans_point(traduisible_de(erreur))}
    except Exception as erreur:         # jamais d'exception vers l'appelant
        return {'present': False, 'raison': traduisible('tailscale.raison_detection_impossible',
                                                        'détection impossible ({erreur})', erreur=erreur)}


def tailscale_attendu(reglages):
    """Vrai quand la configuration laisse penser que Tailscale sert Prévo : « mandataire » vrai, ou un nom en .ts.net
    dans « noms ». La détection n'est lancée qu'alors (au démarrage, puis par /api/info), jamais à chaque requête."""
    return bool(reglages.get('mandataire')) or any(nom.endswith('.ts.net') for nom in reglages.get('noms', []))


def detecter_tailscale_pour(config, forcer=False):
    """Détection gardée dans config.tailscale, refaite au plus une fois par INTERVALLE_TAILSCALE_S (config.horloge),
    sous VERROU_TAILSCALE (une commande à la fois, dans le fil de l'appelant). Rend config.tailscale."""
    with VERROU_TAILSCALE:
        maintenant = maintenant_s(config)
        if (forcer or config.tailscale is None or config.tailscale_lu_a is None
                or maintenant - config.tailscale_lu_a >= INTERVALLE_TAILSCALE_S):
            config.tailscale = detecter_tailscale(maintenant=maintenant)
            config.tailscale_lu_a = maintenant
        return config.tailscale


def etat_tailscale_public(config):
    """« tailscale » de GET /api/info : None tant que la détection n'est pas attendue (portée « ce PC » sans mandataire
    ni nom en .ts.net : aucune commande lancée) ; sinon {"present", "connecte", "nom", "jours_avant_expiration"},
    rafraîchi au plus une fois par 10 minutes. Jamais la sortie brute de « status » : ni version, ni adresse d'un
    autre appareil du tailnet."""
    if config.tailscale is None:
        return None
    detection = detecter_tailscale_pour(config)
    return {'present': bool(detection.get('present')), 'connecte': bool(detection.get('connecte')),
            'nom': detection.get('nom'), 'jours_avant_expiration': detection.get('jours_avant_expiration')}


def resume_tailscale(detection):
    """Ligne de la console : « prevo.tail1234.ts.net, connecté, clé valable 83 jours », ou « non détecté (raison) »."""
    if not detection or not detection.get('present'):
        raison = (detection or {}).get('raison')
        return 'non détecté' + (' (%s)' % raison if raison else '')
    morceaux = [detection.get('nom') or 'sans nom', 'connecté' if detection.get('connecte') else 'déconnecté']
    jours = detection.get('jours_avant_expiration')
    if jours is None:
        morceaux.append('clé sans expiration')
    elif jours < 0:
        morceaux.append('clé expirée')
    else:
        morceaux.append('clé valable %d jour%s' % (jours, '' if jours == 1 else 's'))
    return ', '.join(morceaux)


def commande_serve_tailscale(port_http):
    """Arguments de « tailscale serve --bg --https=443 http://127.0.0.1:<port_http> » (D128)."""
    return ['serve', '--bg', '--https=443', 'http://127.0.0.1:%d' % int(port_http)]


def cible_serve_tailscale(serve, port_http):
    """Hôte (« nom:443 ») sous lequel « tailscale serve status --json » relaie vers http://127.0.0.1:<port_http> (ou
    localhost) ; None si la cible n'y figure pas."""
    cibles = ('http://127.0.0.1:%d' % int(port_http), 'http://localhost:%d' % int(port_http))
    web = serve.get('Web') if isinstance(serve, dict) and isinstance(serve.get('Web'), dict) else {}
    for hote, site in web.items():
        gestionnaires = site.get('Handlers') if isinstance(site, dict) and isinstance(site.get('Handlers'), dict) else {}
        for gestionnaire in gestionnaires.values():
            if isinstance(gestionnaire, dict) and str(gestionnaire.get('Proxy', '')).rstrip('/') in cibles:
                return hote
    return None


def preparer_tailscale(config, detection, systeme=None, reglages=None):
    """Ce que l'assistant propose (§22.8, T167) d'après une détection, sans rien lancer ni écrire : {"present": False,
    "raison", "telechargement" (lien officiel, montré seulement)} quand Tailscale manque ; sinon "present" vrai,
    "connecte", "nom", "adresse" (https://<nom>/), "noms" (les noms acceptés, le nom ajouté s'il manque),
    "ajouter_nom", "mandataire" (vrai), "serve" (texte de la commande) et "arguments_serve", "unattended" (« tailscale
    set --unattended=true », Windows seulement ; None ailleurs), "rappels" (expiration de clé, veille : D130).
    « reglages » : ceux à lire (noms, port_http) à la place de config.reglages — le brouillon de l'assistant (§22.10)."""
    systeme = systeme or sys.platform
    reglages = reglages if reglages is not None else config.reglages
    if not detection or not detection.get('present'):
        return {'present': False, 'raison': (detection or {}).get('raison'),
                'telechargement': LIEN_TELECHARGEMENT_TAILSCALE}
    nom = detection.get('nom')
    noms = list(reglages.get('noms', []))
    ajouter = bool(nom) and nom not in noms
    if ajouter:
        noms.append(nom)
    arguments = commande_serve_tailscale(reglages.get('port_http', PORT_PAR_DEFAUT))
    return {'present': True, 'connecte': bool(detection.get('connecte')), 'nom': nom,
            'adresse': 'https://%s/' % nom if nom else None, 'noms': noms, 'ajouter_nom': ajouter, 'mandataire': True,
            'serve': 'tailscale ' + ' '.join(arguments), 'arguments_serve': arguments,
            'unattended': 'tailscale set --unattended=true' if systeme.startswith('win') else None,
            'rappels': list(RAPPELS_TAILSCALE), 'telechargement': None}


def appliquer_tailscale(config, executable=None, delai=DELAI_TAILSCALE_S, reglages=None, ecrire=True):
    """Applique la proposition de preparer_tailscale (clic de l'assistant, T167) : écrit « noms » (nom ajouté) et
    « mandataire » vrai dans le fichier de configuration (modifier_configuration : le reste du fichier est gardé),
    lance « tailscale serve --bg --https=443 http://127.0.0.1:<port_http> » puis vérifie par « tailscale serve status
    --json » que la cible y figure. Rend {"ok", "serve" (état lu, ou None), "message", "nom", "adresse", "noms"}. Jamais
    « tailscale up », jamais d'installation, jamais « set --unattended » (activer_unattended, sur un clic à part). Les
    réglages en mémoire ne changent pas : la configuration écrite vaut au prochain démarrage (l'assistant relance le
    serveur, §22.10) ; config.tailscale reprend la détection faite ici. « reglages » : le brouillon de l'assistant à
    lire à la place de config.reglages ; « ecrire » faux : le fichier de configuration n'est pas touché (l'assistant
    ne l'écrit qu'à « terminer »), l'appelant reprend « noms » et « mandataire » de la réponse."""
    reglages = reglages if reglages is not None else config.reglages
    detection = detecter_tailscale(executable, delai, maintenant_s(config))
    proposition = preparer_tailscale(config, detection, reglages=reglages)
    refus = {'ok': False, 'serve': None, 'nom': detection.get('nom'), 'adresse': proposition.get('adresse'),
             'noms': proposition.get('noms')}
    if not proposition['present']:
        if detection.get('raison'):
            return dict(refus, message=traduisible('tailscale.non_detecte',
                                                   'Tailscale non détecté ({raison}) : installez-le et '
                                                   'connectez-vous, puis réessayez.', raison=detection['raison']))
        return dict(refus, message=traduisible('tailscale.non_detecte_inconnu',
                                               'Tailscale non détecté (inconnu) : installez-le et connectez-vous, '
                                               'puis réessayez.'))
    if not detection.get('nom') or not detection.get('connecte'):
        return dict(refus, message=traduisible('tailscale.non_connecte',
                                               'Tailscale n\'est pas connecté sur ce PC : ouvrez Tailscale, '
                                               'connectez-vous, puis réessayez.'))
    if ecrire:
        chemin = config.reglages.get('_fichier') or os.path.join(DOSSIER_APPLICATION, NOM_FICHIER_CONFIGURATION)
        try:
            modifier_configuration(chemin, {'noms': proposition['noms'], 'mandataire': True})
        except (OSError, ValueError) as erreur:
            return dict(refus, message=traduisible('tailscale.configuration_non_ecrite',
                                                   'Configuration non écrite ({erreur}) : rien n\'a été lancé.',
                                                   erreur=erreur))
    port_http = reglages.get('port_http', PORT_PAR_DEFAUT)
    chemin_tailscale = executable_tailscale(executable)
    try:
        lancer_tailscale(chemin_tailscale, proposition['arguments_serve'], delai)
        serve = lire_json_tailscale(lancer_tailscale(chemin_tailscale, ['serve', 'status', '--json'], delai))
    except ErreurTailscale as erreur:
        return dict(refus, message=traduisible_de(erreur))
    detection['serve'] = serve
    with VERROU_TAILSCALE:
        config.tailscale, config.tailscale_lu_a = detection, maintenant_s(config)
    resultat = dict(refus, serve=serve)
    if cible_serve_tailscale(serve, port_http) is None:
        return dict(resultat, message=traduisible('tailscale.serve_absent',
                                                  '« tailscale serve status » ne montre pas http://127.0.0.1:{port} : '
                                                  'vérifiez la commande « {commande} » sur ce PC.',
                                                  port=port_http, commande=proposition['serve']))
    return dict(resultat, ok=True, message=traduisible('tailscale.relais_en_place',
                                                       'Tailscale relaie {adresse} vers http://127.0.0.1:{port} ; la '
                                                       'configuration vaut au prochain démarrage de Prévo.',
                                                       adresse=proposition['adresse'], port=port_http))


def activer_unattended(executable=None, delai=DELAI_TAILSCALE_S):
    """« tailscale set --unattended=true » (Windows : Tailscale reste connecté sans session ouverte), lancé seulement
    sur ce clic explicite de l'assistant, jamais par appliquer_tailscale. Rend {"ok", "message"}."""
    chemin = executable_tailscale(executable)
    if not chemin:
        return {'ok': False, 'message': traduisible('tailscale.introuvable', 'Tailscale introuvable sur ce PC.')}
    try:
        lancer_tailscale(chemin, ['set', '--unattended=true'], delai)
    except ErreurTailscale as erreur:
        return {'ok': False, 'message': traduisible_de(erreur)}
    return {'ok': True, 'message': traduisible('tailscale.unattended',
                                               'Tailscale reste connecté même sans session Windows ouverte (« Run '
                                               'unattended »).')}


# ---------------------------------------------------------------------------
# Assistant d'installation (lot 7, ARCHITECTURE.md §22.10 ; D131, D132, CS130) : routes /api/installation/<etape>
# servies au PC serveur seulement (404 au réseau et au mandataire, comme une adresse inconnue) ; brouillon dans
# donnees/installation.json ; prevo.config.json écrit à « terminer », jamais avant ; mot de passe jamais dans le
# brouillon (comptes.json, haché, dès l'étape « compte »).
# ---------------------------------------------------------------------------

NOM_FICHIER_BROUILLON = 'installation.json'
ROUTE_INSTALLATION = '#/installation'
SITUATIONS = ('seul', 'equipe', 'informaticien')
ETAPES_INSTALLATION = ('situation', 'portee', 'compte', 'certificat', 'tailscale', 'demarrage', 'sauvegardes', 'deplacer')
ETAPES_DE_LECTURE = ('etat', 'fiche', 'journal')
# Paramètres › Accès et installation (T170, D131 dernier point) : « reprendre » (brouillon repris de la configuration
# en cours), « reglages » (clés simples), « ia » (fournisseur, adresse, IA en ligne ; jamais la clé) et « annuler »
# (brouillon jeté) s'ajoutent aux étapes de l'assistant ; mêmes routes, même garde (PC serveur, responsable).
ETAPES_D_ECRITURE = ETAPES_INSTALLATION + ('terminer', 'reprendre', 'reglages', 'ia', 'annuler')
ETAPES_SANS_BROUILLON = ('situation', 'reprendre', 'annuler')       # jouables quand le brouillon n'existe pas
CLES_REGLAGES_SIMPLES = ('demandeurs_avec_compte', 'session_heures', 'session_longue_jours', 'invitation_heures',
                         'quota_documents_mo')
CLES_IA_DU_CORPS = {'fournisseur': 'ia_fournisseur', 'url': 'ia_url', 'en_ligne': 'ia_en_ligne'}
NOM_JOURNAL_SERVEUR = 'journal-serveur.log'
LIGNES_DU_JOURNAL = 20                  # « journal » : les 20 dernières lignes de donnees/journal-serveur.log
# Par prudence, aucune ligne contenant « cle » (ia_cle, PREVO_IA_CLE…) ne sort du journal, même si le serveur n'y écrit
# jamais une clé ni un mot de passe.
MOTIF_LIGNE_JOURNAL_RETIREE = re.compile(r'cle', re.IGNORECASE)
ETAT_FAIT, ETAT_A_FAIRE, ETAT_SANS_OBJET = 'fait', 'a_faire', 'sans_objet'
MODES_CERTIFICAT = ('automatique', 'reseau_prive', 'fichiers', 'mandataire')
ACTIONS_TAILSCALE = ('detecter', 'appliquer', 'unattended', 'plus_tard')
# Dossier conseillé sous Windows : C:\Prevo (D131 ; l'assistant propose d'y déplacer Prévo, T171).
DOSSIER_CONSEILLE_WINDOWS = 'C:\\Prevo'
DOSSIERS_JAMAIS_COPIES = ('.git', '__pycache__')
NOM_LANCEUR_WINDOWS, NOM_LANCEUR_AUTRE = 'Lancer_GMAO.bat', 'lancer.sh'
NOM_SCRIPT_REINITIALISATION = 'Reinitialiser_mot_de_passe.bat'
VERSION_SCHEMA_CSV = 3                  # « version » de js/schema.js (§14.1) : posée dans un parametres.csv créé ici
DELAI_RELANCE_S = 2                     # le serveur s'arrête 2 s après la réponse de « terminer » ou « deplacer »
ATTENTE_AVANT_RELANCE_S = 3             # le lanceur repart 3 s plus tard, une fois le port rendu
# « terminer » sur une base absente au départ (T171) : rien de plus (« vide » : parametres.csv seul, avec version_schema
# et langue_defaut, T296), ou le jeu de démo, lu dans
# js/demo-donnees.js — le seul jeu livré (§22.14 : le zip n'a pas de dossier donnees/), produit par
# outils/generer_demo.py : une ligne par table (chaîne JSON, ou morceaux recollés pour le wiki) et la date de référence.
BASES_AU_DEPART = ('vide', 'demo')
FICHIER_JEU_DE_DEMO = os.path.join(DOSSIER_APPLICATION, 'js', 'demo-donnees.js')
MOTIF_TABLE_DU_JEU_DE_DEMO = re.compile(r'^    ([a-z_]+): ')
MOTIF_DATE_DU_JEU_DE_DEMO = re.compile(r'^  dateReference: "([0-9]{4}-[0-9]{2}-[0-9]{2})",?$')
PREFIXE_MORCEAUX_DU_JEU_DE_DEMO = "((m, s) => s.map((r) => m[r]).join(''))("
MOTIF_DEBUT_DE_DATE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')     # comme MOTIF_DATE de js/stockage-demo.js
# Langue de Prévo d'une base neuve (T296 ; D149, D165) : « terminer » reçoit langue_defaut, une langue déclarée par
# js/i18n/langues.js (une ligne « I18n.declarer({ code: 'xx', … }) » par langue, la même liste que le navigateur), le
# français sans elle.
FICHIER_LANGUES = os.path.join(DOSSIER_APPLICATION, 'js', 'i18n', 'langues.js')
MOTIF_LANGUE_DECLAREE = re.compile(r"^I18n\.declarer\(\{\s*code:\s*'([^'\\]+)'", re.MULTILINE)
LANGUE_PAR_DEFAUT = 'fr'
MESSAGE_JEU_DE_DEMO_ILLISIBLE = traduisible('installation.demo_illisible',
                                            'Jeu de démo illisible (js/demo-donnees.js) : commencez vide, ou remettez '
                                            'le fichier du zip.')
MESSAGE_ADRESSE_INCONNUE = traduisible('requete.adresse_inconnue', 'Adresse inconnue dans l\'API.')
MESSAGE_SANS_BROUILLON = traduisible('installation.sans_brouillon',
                                     'Commencez par dire qui utilise Prévo (étape « situation »).')
# Clés du brouillon = celles de la configuration, sauf la clé du fournisseur d'IA (un secret : jamais ici).
CLES_DU_BROUILLON = tuple(cle for cle, _, _, _ in CLES_CONFIGURATION if cle != 'ia_cle')
VERROU_INSTALLATION = threading.Lock()  # une étape à la fois (mkcert, Tailscale, copie : le brouillon reste cohérent)

# Défauts de l'étude §6.1 par situation (ce qui diffère des défauts de CLES_CONFIGURATION) ; « mode_solo » en plus
# (D132 : parametres.csv à « terminer »). Solo : « ce PC » tant qu'aucun téléphone n'est voulu, certificat par le réseau
# privé (Tailscale) ; Atelier : le Wi-Fi, certificat automatique, démarre avec le PC sans veille ; Intranet : comptes
# pour tous, certificat et démarrage de l'entreprise, le serveur ne se met pas en veille de lui-même.
DEFAUTS_PAR_SITUATION = {
    'seul': {'portee': 'ce-pc', 'comptes': False, 'demandeurs_avec_compte': False, 'certificat_auto': False,
             'demarrage': 'aucun', 'veille_desactivee': False, 'mode_solo': True},
    'equipe': {'portee': 'atelier', 'comptes': True, 'demandeurs_avec_compte': False, 'certificat_auto': True,
               'demarrage': 'systeme', 'veille_desactivee': True, 'mode_solo': False},
    'informaticien': {'portee': 'atelier', 'comptes': True, 'demandeurs_avec_compte': True, 'certificat_auto': False,
                      'demarrage': 'systeme', 'veille_desactivee': False, 'mode_solo': False},
}


def chemin_brouillon(config):
    return os.path.join(config.dossier_donnees, NOM_FICHIER_BROUILLON)


def lire_brouillon(config):
    """Le brouillon de l'assistant (dict), ou None s'il n'existe pas ; un fichier illisible vaut None (l'assistant
    repart de la situation, rien n'est perdu d'autre)."""
    octets = lire_octets(chemin_brouillon(config))
    if octets is None:
        return None
    try:
        brouillon = json.loads(octets.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(brouillon, dict) or brouillon.get('situation') not in SITUATIONS:
        return None
    return brouillon


def octets_du_brouillon(brouillon):
    return (json.dumps(brouillon, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def ecrire_brouillon(config, brouillon, chemin=None):
    """Écriture atomique de donnees/installation.json (un rechargement ou un redémarrage avant « terminer » ne perd
    rien) ; sous VERROU_INSTALLATION par l'appelant. « chemin » : un autre fichier (le brouillon copié avec Prévo)."""
    chemin = chemin or chemin_brouillon(config)
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    ecrire_atomique(chemin, octets_du_brouillon(brouillon))


def supprimer_brouillon(config):
    try:
        os.remove(chemin_brouillon(config))
    except FileNotFoundError:
        pass


def dans_dossier_conseille(config):
    """Vrai quand Prévo tourne déjà dans C:\\Prevo, ou dans un dossier juste dessous (le zip dézippé dans C:\\Prevo
    donne C:\\Prevo\\prevo-<version> : l'y redéplacer serait refusé, « au-dessus » de la source) ; faux ailleurs et sur
    les autres systèmes."""
    if not config.systeme.startswith('win'):
        return False
    dossier = os.path.abspath(config.dossier_application)
    return (chemins_egaux(dossier, DOSSIER_CONSEILLE_WINDOWS)
            or chemins_egaux(os.path.dirname(dossier), DOSSIER_CONSEILLE_WINDOWS))


def ecoute_du_brouillon(brouillon):
    """Axe d'écoute déduit du brouillon (§22.1) : 127.0.0.1 en portée « ce PC », et quand un mandataire sur ce PC porte
    seul le https (réseau privé Tailscale sans certificat local, mandataire de l'entreprise) ; 0.0.0.0 sinon."""
    if brouillon.get('portee') == 'ce-pc':
        return '127.0.0.1'
    if brouillon.get('mandataire') and not brouillon.get('certificat_auto') and not brouillon.get('certificat'):
        return '127.0.0.1'
    return '0.0.0.0'


def etapes_du_brouillon(config, brouillon):
    """État de chaque étape (fait, a_faire, sans_objet) : celui noté dans le brouillon, corrigé par ce qui n'a pas
    d'objet — compte et certificat sur « ce PC » (le compte reste proposé en Solo : il crée le technicien « moi »),
    « hors de l'atelier » hors de la portée « dehors », le dossier conseillé hors de Windows ou déjà dedans — et par
    les faits : un responsable actif vaut l'étape « compte » faite."""
    etapes = dict(brouillon.get('etapes') or {})
    for etape in ETAPES_INSTALLATION:
        etapes.setdefault(etape, ETAT_A_FAIRE)
    ce_pc = brouillon.get('portee') == 'ce-pc'

    def poser(etape, sans_objet):
        if sans_objet:
            etapes[etape] = ETAT_SANS_OBJET
        elif etapes[etape] == ETAT_SANS_OBJET:
            etapes[etape] = ETAT_A_FAIRE

    poser('compte', ce_pc and not brouillon.get('mode_solo'))
    poser('certificat', ce_pc)
    poser('tailscale', brouillon.get('portee') != 'dehors')
    poser('deplacer', not config.systeme.startswith('win') or dans_dossier_conseille(config))
    if etapes['compte'] != ETAT_SANS_OBJET and responsable_actif_existe(config):
        etapes['compte'] = ETAT_FAIT
    return etapes


def completer_brouillon(config, brouillon):
    """Clés dérivées avant chaque écriture du brouillon : « ecoute » et les états des étapes."""
    brouillon['ecoute'] = ecoute_du_brouillon(brouillon)
    brouillon['etapes'] = etapes_du_brouillon(config, brouillon)
    return brouillon


def brouillon_neuf(config, situation):
    """Brouillon réinitialisé aux défauts de l'étude §6.1 pour cette situation (clé à clé) ; étape « situation » faite."""
    brouillon = {cle: valeur for cle, valeur in reglages_par_defaut().items() if cle in CLES_DU_BROUILLON}
    brouillon.update(DEFAUTS_PAR_SITUATION[situation])
    brouillon['situation'] = situation
    brouillon['etapes'] = {etape: ETAT_A_FAIRE for etape in ETAPES_INSTALLATION}
    brouillon['etapes']['situation'] = ETAT_FAIT
    # Migration depuis 1.2 (T171) : des CSV au départ de l'assistant (ceux de l'utilisateur, jamais touchés) ; noté ici
    # parce que l'assistant lui-même en crée ensuite en Solo (techniciens.csv à « compte », parametres.csv à « terminer »).
    brouillon['base_presente'] = bool(tables_presentes(config.dossier_donnees))
    return completer_brouillon(config, brouillon)


def valeur_parametre_csv(config, cle):
    """Valeur d'une clé de parametres.csv (texte, '' si la ligne ou le fichier manque) ; lecture tolérante."""
    for ligne in dictionnaires_csv(lire_octets(chemin_table(config, 'parametres')), 'parametres'):
        if str(ligne.get('cle', '')).strip() == cle:
            return str(ligne.get('valeur', '')).strip()
    return ''


def situation_de_la_configuration(config):
    """Situation de l'étude (§6.1) d'une installation faite, pour reprendre son brouillon (Paramètres, T170) : « seul »
    quand parametres.csv dit mode_solo = 1, « informaticien » quand les demandeurs ont un compte, « equipe » sinon."""
    if valeur_parametre_csv(config, 'mode_solo') == '1':
        return 'seul'
    return 'informaticien' if config.reglages.get('demandeurs_avec_compte') else 'equipe'


def brouillon_depuis_configuration(config):
    """POST /api/installation/reprendre (T170) : brouillon repris de la configuration en cours (config.reglages : le
    fichier et la ligne de commande, ce que « terminer » réécrira clé à clé), toutes les étapes faites sauf
    « deplacer » ; mode_solo faux (parametres.csv n'est pas touché à « terminer »), base présente (jamais la démo)."""
    brouillon = {cle: (list(config.reglages[cle]) if isinstance(config.reglages.get(cle), list) else config.reglages.get(cle))
                 for cle in CLES_DU_BROUILLON}
    brouillon['situation'] = situation_de_la_configuration(config)
    brouillon['etapes'] = {etape: ETAT_FAIT for etape in ETAPES_INSTALLATION}
    brouillon['etapes']['deplacer'] = ETAT_A_FAIRE
    brouillon['mode_solo'] = False
    brouillon['base_presente'] = True
    return completer_brouillon(config, brouillon)


def dernieres_lignes_du_journal(config, nombre=LIGNES_DU_JOURNAL):
    """GET /api/installation/journal (T170, D130 : « Paramètres montre l'état… dernières erreurs ») : les « nombre »
    dernières lignes de donnees/journal-serveur.log, sans celles qui contiennent « cle » (prudence) ; {"fichier": None,
    "lignes": []} quand le journal n'existe pas (serveur avec console et sans --journal)."""
    chemin = os.path.join(config.dossier_donnees, NOM_JOURNAL_SERVEUR)
    octets = lire_octets(chemin)
    if octets is None:
        return {'fichier': None, 'lignes': []}
    lignes = octets.decode('utf-8', 'replace').splitlines()[-nombre:]
    return {'fichier': chemin, 'lignes': [ligne for ligne in lignes if not MOTIF_LIGNE_JOURNAL_RETIREE.search(ligne)]}


def valeur_du_brouillon(cle, valeur):
    """Valeur d'une clé de configuration reçue par l'assistant, contrôlée comme à la lecture du fichier (bornes de
    CLES_CONFIGURATION) ; ErreurHttp 400 au message clair sinon."""
    genres = {nom: genre for nom, genre, _, _ in CLES_CONFIGURATION}
    try:
        return valeur_valide(cle, genres[cle], valeur)
    except ErreurConfiguration as erreur:
        bornes = BORNES_ENTIERS.get(cle)
        if not bornes:
            raise ErreurHttp(400, traduisible_de(erreur))
        raise ErreurHttp(400, traduisible('config.valeur_invalide_bornes', '{erreur} Bornes : {minimum} à {maximum}.',
                                          erreur=traduisible_de(erreur), minimum=bornes[0], maximum=bornes[1]))


def mkcert_disponible():
    """Vrai quand executable_mkcert trouve un mkcert (variable PREVO_MKCERT ou outils-tiers/ à l'empreinte juste)."""
    try:
        executable_mkcert()
        return True
    except ErreurConfiguration:
        return False


def detection_tailscale_publique(detection):
    """Sous-ensemble d'une détection rendu par l'assistant : jamais la sortie brute (§22.8)."""
    return {'present': bool(detection.get('present')), 'connecte': bool(detection.get('connecte')),
            'nom': detection.get('nom'), 'jours_avant_expiration': detection.get('jours_avant_expiration'),
            'raison': detection.get('raison')}


def derniere_modification_csv(dossier, tables):
    """Date et heure (AAAA-MM-JJTHH:MM:SS, heure locale) du CSV modifié le plus récemment parmi « tables » ; None sans
    table ou sans fichier lisible."""
    instants = []
    for table in tables:
        try:
            instants.append(os.path.getmtime(os.path.join(dossier, table + '.csv')))
        except OSError:
            pass
    if not instants:
        return None
    return datetime.datetime.fromtimestamp(max(instants)).strftime('%Y-%m-%dT%H:%M:%S')


def etat_installation(config):
    """GET /api/installation/etat : la configuration est-elle présente, le brouillon et ses étapes, des CSV dans le
    dossier des données (migration depuis 1.2 : combien, modifiés quand), le dossier de Prévo, le Python embarqué, un
    responsable, Tailscale (detecter_tailscale : commandes locales, jamais gardée dans config.tailscale pour ne pas
    changer /api/info), mkcert disponible, le système et la version."""
    brouillon = lire_brouillon(config)
    if brouillon is not None:
        brouillon = completer_brouillon(config, brouillon)
    reglages = brouillon if brouillon is not None else config.reglages
    windows = config.systeme.startswith('win')
    tables = tables_presentes(config.dossier_donnees)
    return {'configuration_presente': bool(config.reglages.get('_present')),
            # T170 : la configuration en cours (jamais ia_cle), pour que Paramètres montre chaque réglage avant tout
            # brouillon ; None tant que l'installation n'est pas terminée.
            'configuration': ({cle: (list(config.reglages[cle]) if isinstance(config.reglages.get(cle), list)
                                     else config.reglages.get(cle)) for cle in CLES_DU_BROUILLON}
                              if config.reglages.get('_present') else None),
            'portee': reglages.get('portee'),
            'situation': brouillon.get('situation') if brouillon is not None else None,
            'etapes': brouillon['etapes'] if brouillon is not None else {etape: ETAT_A_FAIRE for etape in ETAPES_INSTALLATION},
            'brouillon': brouillon,
            'csv_presents': bool(tables),
            'nombre_csv': len(tables),
            'derniere_modification': derniere_modification_csv(config.dossier_donnees, tables),
            'dossier': os.path.abspath(config.dossier_application),
            'dossier_conseille': DOSSIER_CONSEILLE_WINDOWS if windows else None,
            'dans_dossier_conseille': dans_dossier_conseille(config),
            'python_embarque': os.path.isfile(os.path.join(config.dossier_application, 'python', 'python.exe')),
            'responsable_existe': responsable_actif_existe(config),
            'tailscale': detection_tailscale_publique(detecter_tailscale(maintenant=maintenant_s(config))),
            'mkcert_present': mkcert_disponible(),
            'systeme': 'windows' if windows else ('macos' if config.systeme == 'darwin' else 'linux'),
            'version': VERSION_APPLICATION}


def fiche_acces(config):
    """GET /api/installation/fiche : les données de la fiche d'accès imprimable (T168 la met en page), d'après le
    brouillon s'il existe, sinon la configuration : adresses de la porte (adresses réseau du PC et noms acceptés, en
    http sur port_http : jamais l'adresse https, §22.6), adresse Tailscale (nom en .ts.net derrière un mandataire),
    adresses du mandataire (les autres noms), autorité locale présente (QR « faire confiance » = la porte, qui sert
    /acces/ca.crt), comment arrêter et relancer, le dossier des données, comment réinitialiser un mot de passe. Sans
    brouillon, la fiche lit le fichier de configuration (ce que « terminer » vient d'écrire, avant la relance) ; sans
    fichier lisible, les réglages du serveur."""
    brouillon = lire_brouillon(config)
    reglages = brouillon
    if reglages is None:
        try:
            reglages = lire_configuration(config.reglages.get('_fichier'))
        except ErreurConfiguration:
            reglages = config.reglages
    port = reglages.get('port_http', PORT_PAR_DEFAUT)
    noms = list(reglages.get('noms', []))
    mandataire = bool(reglages.get('mandataire'))
    reseau = reglages.get('ecoute') == '0.0.0.0' or (reglages.get('portee') != 'ce-pc' and brouillon is not None
                                                     and ecoute_du_brouillon(brouillon) == '0.0.0.0')
    adresses = ['http://%s:%d/' % (ip, port) for ip in adresses_ip_reseau()] if reseau else []
    adresses += ['http://%s:%d/' % (nom, port) for nom in noms if reseau and not nom.endswith('.ts.net')]
    tailscale = next(('https://%s/' % nom for nom in noms if mandataire and nom.endswith('.ts.net')), None)
    windows = config.systeme.startswith('win')
    responsables = [compte['identifiant'] for compte in comptes_du_serveur(config)
                    if compte.get('role') == 'responsable' and compte.get('actif')]
    return {'situation': brouillon.get('situation') if brouillon is not None else None,
            'portee': reglages.get('portee'),
            'comptes': bool(reglages.get('comptes')),
            'adresse_locale': 'http://127.0.0.1:%d/' % port,
            'adresses': adresses,
            'adresse_tailscale': tailscale,
            'adresses_mandataire': ['https://%s/' % nom for nom in noms if mandataire and not nom.endswith('.ts.net')],
            'autorite_presente': certificat_de_l_autorite(config) is not None,
            'adresse_confiance': adresses[0] if adresses else None,
            'lanceur': NOM_LANCEUR_WINDOWS if windows else NOM_LANCEUR_AUTRE,
            'demarrage': reglages.get('demarrage', 'aucun'),
            'dossier': os.path.abspath(config.dossier_application),
            'dossier_donnees': config.dossier_donnees,
            'copie_sauvegardes': reglages.get('copie_sauvegardes', ''),
            'reinitialisation': {'script': NOM_SCRIPT_REINITIALISATION if windows else None,
                                 'commande': 'serveur.py --reinitialiser <identifiant>'},
            'responsables': responsables}


def forme_de_nom(texte):
    """Nom ou prénom réduit pour une comparaison : lettres simples (plier_nom, T301 : İ/ı, casse, accents) et espaces
    multiples ignorés."""
    return ' '.join(plier_nom(texte).split())


def ecrire_table(config, table, entete, lignes):
    """Réécrit un CSV entier au format de Prévo, la sauvegarde du jour faite d'abord ; en tenant VERROU_ECRITURE.
    409 en lecture seule (T185, données plus récentes) ; 409 « fichier_abime » si le fichier en place est abîmé
    (T200, ecrire_fichier_de_donnees : rien n'est écrit)."""
    verifier_ecriture_permise(config)
    ecrire_fichier_de_donnees(config, table, ecrire_tableau_csv(entete, lignes), sauvegarde_du_jour=True)


def technicien_moi(config, prenom, nom):
    """Technicien de la personne seule (D132, §22.11) : celui de techniciens.csv qui porte déjà ce prénom et ce nom
    (actif ; casse et accents ignorés), sinon une ligne nouvelle (TEC-nnnn suivant, métier vide, actif), les colonnes
    du fichier gardées telles quelles. Rend son identifiant. En tenant VERROU_ECRITURE."""
    octets = lire_octets(chemin_table(config, 'techniciens'))
    entete, lignes = lire_tableau('techniciens', octets)
    if not entete:
        entete, lignes = list(COLONNES_PAR_TABLE['techniciens']), []
    cles = [cle_entete(colonne) for colonne in entete]
    colonnes = {}
    for nom_colonne in ('id', 'nom', 'prenom', 'actif'):
        if nom_colonne not in cles:
            raise ErreurHttp(500, traduisible('technicien.colonne_absente',
                                              'techniciens.csv sans colonne « {colonne} » : impossible d\'y ajouter '
                                              'votre fiche.', colonne=nom_colonne))
        colonnes[nom_colonne] = cles.index(nom_colonne)
    voulu = (forme_de_nom(nom), forme_de_nom(prenom))
    numero = 0
    for ligne in lignes:
        while len(ligne) < len(entete):
            ligne.append('')
        identifiant = ligne[colonnes['id']].strip()
        trouve = re.fullmatch(r'TEC-([0-9]+)', identifiant)
        if trouve:
            numero = max(numero, int(trouve.group(1)))
        if (ligne[colonnes['actif']].strip().lstrip('\'') != '0'
                and (forme_de_nom(ligne[colonnes['nom']]), forme_de_nom(ligne[colonnes['prenom']])) == voulu):
            return identifiant
    identifiant = 'TEC-%04d' % (numero + 1)
    nouvelle = [''] * len(entete)
    nouvelle[colonnes['id']], nouvelle[colonnes['nom']], nouvelle[colonnes['prenom']] = identifiant, nom, prenom
    nouvelle[colonnes['actif']] = '1'
    ecrire_table(config, 'techniciens', entete, lignes + [nouvelle])
    return identifiant


def langues_declarees():
    """Codes des langues déclarées par js/i18n/langues.js, dans l'ordre, relus à chaque appel (T296) ; fichier absent
    ou illisible : le français seul."""
    octets = lire_octets(FICHIER_LANGUES)
    try:
        codes = MOTIF_LANGUE_DECLAREE.findall(octets.decode('utf-8')) if octets is not None else []
    except UnicodeDecodeError:
        codes = []
    return codes or [LANGUE_PAR_DEFAUT]


def valeurs_du_mode_solo(technicien_id=''):
    """Lignes de parametres.csv du mode Solo (D132, §22.11) : mode_solo = 1, cloture_une_etape = 1 et, s'il existe,
    solo_technicien_id."""
    valeurs = {'mode_solo': '1', 'cloture_une_etape': '1'}
    if technicien_id:
        valeurs['solo_technicien_id'] = technicien_id
    return valeurs


def poser_mode_solo(config, technicien_id=''):
    """Le mode Solo posé dans parametres.csv (valeurs_du_mode_solo, poser_parametres). En tenant VERROU_ECRITURE."""
    poser_parametres(config, valeurs_du_mode_solo(technicien_id))


def poser_parametres(config, valeurs):
    """Lignes « valeurs » ({cle: texte}) de parametres.csv ajoutées ou remplacées, toutes les autres gardées (mode Solo,
    D132 ; langue d'une base neuve, T296), par une écriture de table normale (sauvegarde du jour d'abord) ; le fichier
    est créé avec version_schema s'il manque (le premier démarrage ne propose alors plus « démo ou vide » : la base
    existe). En tenant VERROU_ECRITURE."""
    valeurs = dict(valeurs)
    octets = lire_octets(chemin_table(config, 'parametres'))
    entete, lignes = lire_tableau('parametres', octets)
    if not entete:
        entete, lignes = list(COLONNES_PAR_TABLE['parametres']), []
    cles = [cle_entete(colonne) for colonne in entete]
    if 'cle' not in cles or 'valeur' not in cles:
        raise ErreurHttp(500, traduisible('parametres.colonnes_absentes',
                                          'parametres.csv sans colonnes « cle » et « valeur » : réglages de '
                                          'l\'installation non posés.'))
    position_cle, position_valeur = cles.index('cle'), cles.index('valeur')
    if octets is None:
        valeurs = dict({'version_schema': str(VERSION_SCHEMA_CSV)}, **valeurs)      # en tête du fichier créé
    for ligne in lignes:
        while len(ligne) < len(entete):
            ligne.append('')
        cle = ligne[position_cle].strip()
        if cle in valeurs:
            ligne[position_valeur] = valeurs.pop(cle)
    for cle, valeur in valeurs.items():
        ligne = [''] * len(entete)
        ligne[position_cle], ligne[position_valeur] = cle, valeur
        lignes.append(ligne)
    ecrire_table(config, 'parametres', entete, lignes)


def verifier_dossier_de_copie(config, dossier):
    """Dossier de copie externe choisi dans l'assistant (D133) : il existe, on peut y écrire (un fichier témoin créé
    puis supprimé) et il n'est ni le dossier des données ni un de ses sous-dossiers (une panne du disque emporterait
    les deux) ; 400 au message clair sinon, qui ne cite que le nom du dossier. Rend le chemin absolu."""
    chemin = os.path.abspath(os.path.expanduser(dossier.strip()))
    nom = nom_du_dossier(chemin)
    if not os.path.isdir(chemin):
        raise ErreurHttp(400, traduisible('copie.dossier_introuvable_branchez',
                                          'Dossier de copie « {nom} » introuvable : branchez la clé ou créez le '
                                          'dossier, puis réessayez.', nom=nom))
    if est_sous_dossier(os.path.realpath(chemin), config.dossier_donnees):
        raise ErreurHttp(400, traduisible('copie.dossier_dans_donnees',
                                          'Le dossier de copie ne peut pas être dans le dossier des données de '
                                          'Prévo : une panne du disque emporterait les données et leur copie.'))
    try:
        descripteur, temoin = tempfile.mkstemp(prefix='.prevo-temoin-', dir=chemin)
        os.close(descripteur)
        os.remove(temoin)
    except OSError as erreur:
        raise ErreurHttp(400, traduisible('copie.ecriture_impossible',
                                          'Dossier de copie « {nom} » : écriture impossible ({erreur}).',
                                          nom=nom, erreur=erreur.strerror or erreur))
    return chemin


def verifier_dossier_cible(source, cible):
    """Cible de « deplacer » : un chemin absolu qui n'est ni le dossier de Prévo, ni dedans, ni au-dessus, et qui
    n'existe pas encore ou est vide ; 400 sinon."""
    if not os.path.isabs(cible):
        raise ErreurHttp(400, traduisible('deplacement.chemin_complet',
                                          'Donnez un chemin complet (par exemple {exemple}).',
                                          exemple=DOSSIER_CONSEILLE_WINDOWS))
    source_reelle, cible_reelle = os.path.realpath(source), os.path.realpath(cible)
    if chemins_egaux(source_reelle, cible_reelle):
        raise ErreurHttp(400, traduisible('deplacement.deja_dans_ce_dossier', 'Prévo est déjà dans ce dossier.'))
    if est_sous_dossier(cible_reelle, source_reelle) or est_sous_dossier(source_reelle, cible_reelle):
        raise ErreurHttp(400, traduisible('deplacement.dossier_interdit',
                                          'Le dossier de destination ne peut être ni dans le dossier de Prévo ni '
                                          'au-dessus.'))
    if os.path.exists(cible) and (not os.path.isdir(cible) or os.listdir(cible)):
        raise ErreurHttp(400, traduisible('deplacement.dossier_non_vide',
                                          'Le dossier « {dossier} » existe déjà et n\'est pas vide : choisissez un '
                                          'dossier vide ou nouveau.', dossier=cible))


def copier_prevo(source, cible):
    """Copie le dossier de Prévo entier (données comprises) vers « cible », sans .git ni __pycache__ ; chaque fichier
    copié est relu (taille et SHA-256 égaux, sinon ErreurHttp 500 et la copie est retirée). L'ancien dossier n'est
    jamais touché. Rend le nombre de fichiers copiés."""
    source = os.path.abspath(source)
    cree = not os.path.exists(cible)
    nombre = 0
    try:
        for racine, dossiers, fichiers in os.walk(source):
            dossiers[:] = sorted(d for d in dossiers if d not in DOSSIERS_JAMAIS_COPIES)
            relatif = os.path.relpath(racine, source)
            destination = cible if relatif == '.' else os.path.join(cible, relatif)
            os.makedirs(destination, exist_ok=True)
            for nom in sorted(fichiers):
                origine, copie = os.path.join(racine, nom), os.path.join(destination, nom)
                shutil.copy2(origine, copie)
                if (os.path.getsize(origine) != os.path.getsize(copie)
                        or empreinte_fichier(origine) != empreinte_fichier(copie)):
                    raise ErreurHttp(500, traduisible('deplacement.copie_incomplete',
                                                      'Copie incomplète ({fichier}) : l\'ancien dossier est intact, '
                                                      'rien n\'a été relancé.',
                                                      fichier=os.path.relpath(origine, source)))
                nombre += 1
    except OSError as erreur:
        if cree:
            shutil.rmtree(cible, ignore_errors=True)
        raise ErreurHttp(500, traduisible('deplacement.copie_impossible',
                                          'Copie impossible ({erreur}) : l\'ancien dossier est intact, rien n\'a '
                                          'été relancé.', erreur=erreur))
    except ErreurHttp:
        if cree:
            shutil.rmtree(cible, ignore_errors=True)
        raise
    return nombre


def lanceur_de(dossier, systeme=None):
    """Chemin du lanceur de Prévo dans ce dossier : Lancer_GMAO.bat sous Windows, lancer.sh ailleurs."""
    systeme = systeme or sys.platform
    return os.path.join(dossier, NOM_LANCEUR_WINDOWS if systeme.startswith('win') else NOM_LANCEUR_AUTRE)


def relancer_prevo(config, dossier=None):
    """Relance Prévo depuis « dossier » (None : le dossier courant) par son lanceur, puis arrête ce serveur
    DELAI_RELANCE_S après (la réponse en cours est partie). Un processus détaché attend ATTENTE_AVANT_RELANCE_S que ce
    serveur ait rendu son port, puis lance Lancer_GMAO.bat dans une nouvelle console (Windows) ou lancer.sh : le
    serveur repart avec la configuration écrite. Rend vrai si la relance est programmée (lanceur présent), faux sinon
    (le serveur continue, l'utilisateur relance à la main). Jamais appelée par les tests (config.relancer y est
    remplacée) : elle arrête le processus."""
    dossier = os.path.abspath(dossier or config.dossier_application)
    lanceur = lanceur_de(dossier, config.systeme)
    if not os.path.isfile(lanceur):
        return False
    windows = sys.platform.startswith('win')
    options = {'creationflags': subprocess.CREATE_NEW_CONSOLE} if windows else {'start_new_session': True}
    code = ('import subprocess, time\n'
            'time.sleep(%d)\n'
            'subprocess.Popen(%r, cwd=%r, **%r)\n' % (ATTENTE_AVANT_RELANCE_S, [lanceur], dossier, options))
    detache = ({'creationflags': subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP} if windows
               else {'start_new_session': True})
    try:
        subprocess.Popen([sys.executable, '-c', code], cwd=dossier, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True, **detache)
    except OSError as erreur:
        afficher('Relance impossible (%s) : relancez Prévo à la main par %s.' % (erreur, os.path.basename(lanceur)))
        return False

    def arreter():
        time.sleep(DELAI_RELANCE_S)
        afficher('Prévo se relance depuis %s.' % dossier)
        os._exit(0)

    threading.Thread(target=arreter, name='relance', daemon=True).start()
    return True


def deplacer_installation(config, cible, brouillon=None):
    """Déplace Prévo dans « cible » (D131, étape « Dossier » : C:\\Prevo conseillé) : cible vérifiée
    (verifier_dossier_cible ; les données doivent être dans le dossier de Prévo), copie du dossier entier avec chaque
    fichier relu (copier_prevo), brouillon de l'assistant écrit dans la copie (l'assistant y reprend où il en était,
    étape « deplacer » faite), puis relance depuis la copie (config.relancer, injectable, jamais lancée par les tests).
    Rend {'copie': nombre de fichiers, 'vers', 'relance'} ; ErreurHttp 400 ou 500 au message clair. L'ancien dossier
    n'est jamais supprimé : l'utilisateur l'efface à la main ensuite."""
    source = os.path.abspath(config.dossier_application)
    if not est_sous_dossier(os.path.realpath(config.dossier_donnees), source):
        raise ErreurHttp(400, traduisible('deplacement.donnees_hors_prevo',
                                          'Le dossier des données n\'est pas dans le dossier de Prévo (option '
                                          '--donnees) : déplacez Prévo à la main.'))
    verifier_dossier_cible(source, cible)               # chemin complet exigé : jamais résolu depuis le dossier courant
    cible = os.path.abspath(cible)
    nombre = copier_prevo(source, cible)
    if brouillon is not None:
        ecrire_brouillon(config, brouillon, os.path.join(cible, os.path.relpath(chemin_brouillon(config), source)))
    return {'copie': nombre, 'vers': cible, 'relance': bool(config.relancer(cible))}


def lire_jeu_de_demo():
    """(date de référence, {table: texte CSV}) lus dans js/demo-donnees.js (format d'outils/generer_demo.py : une
    ligne par table, chaîne JSON ou morceaux recollés pour le wiki) ; ErreurHttp 500 au message clair s'il manque, ne
    se lit pas ou n'a pas toutes les tables."""
    octets = lire_octets(FICHIER_JEU_DE_DEMO)
    if octets is None:
        raise ErreurHttp(500, MESSAGE_JEU_DE_DEMO_ILLISIBLE)
    decodeur = json.JSONDecoder()
    date_reference, textes = None, {}
    try:
        for ligne in octets.decode('utf-8').splitlines():
            trouvee = MOTIF_DATE_DU_JEU_DE_DEMO.match(ligne)
            if trouvee:
                date_reference = trouvee.group(1)
                continue
            trouvee = MOTIF_TABLE_DU_JEU_DE_DEMO.match(ligne)
            if not trouvee:
                continue
            reste = ligne[trouvee.end():]
            if reste.startswith(PREFIXE_MORCEAUX_DU_JEU_DE_DEMO):
                morceaux, fin = decodeur.raw_decode(reste[len(PREFIXE_MORCEAUX_DU_JEU_DE_DEMO):])
                ordre, _ = decodeur.raw_decode(reste[len(PREFIXE_MORCEAUX_DU_JEU_DE_DEMO) + fin:].lstrip(', '))
                texte = ''.join(morceaux[rang] for rang in ordre)
            else:
                texte, _ = decodeur.raw_decode(reste)
            if trouvee.group(1) in TABLES and isinstance(texte, str):
                textes[trouvee.group(1)] = texte
    except (UnicodeDecodeError, ValueError, TypeError, IndexError):
        raise ErreurHttp(500, MESSAGE_JEU_DE_DEMO_ILLISIBLE)
    if date_reference is None or len(textes) != len(TABLES):
        raise ErreurHttp(500, MESSAGE_JEU_DE_DEMO_ILLISIBLE)
    return date_reference, textes


def decaler_texte_csv(texte, jours):
    """Octets d'un CSV du jeu de démo avec ses dates décalées de « jours » (comme StockageDemo.decalerDates : toute
    cellule qui commence par AAAA-MM-JJ, le reste de la cellule gardé ; test_installation_migration vérifie que ces
    cellules sont exactement celles des colonnes date et date_heure du schéma). 0 jour : le texte tel quel."""
    if jours == 0:
        return BOM_UTF8 + texte.encode('utf-8')
    entete, lignes = lire_csv_tolerant(texte.encode('utf-8'))
    for ligne in lignes:
        for position, cellule in enumerate(ligne):
            if MOTIF_DEBUT_DE_DATE.match(cellule):
                jour = datetime.date.fromisoformat(cellule[:10]) + datetime.timedelta(days=jours)
                ligne[position] = jour.isoformat() + cellule[10:]
    return ecrire_tableau_csv(entete, lignes)


def technicien_par_id(config, identifiant):
    """Ligne de techniciens.csv (dict) qui porte cet identifiant, ou None."""
    lignes = dictionnaires_csv(lire_octets(chemin_table(config, 'techniciens')), 'techniciens')
    return next((ligne for ligne in lignes if ligne.get('id', '').strip() == identifiant), None)


def installer_jeu_de_demo(config, brouillon, origine=('', '', '')):
    """« terminer » avec base « demo » sur une base absente au départ (T171) : les tables du jeu de démo écrites dans
    le dossier des données, dates décalées du nombre de semaines entières écoulées depuis la date de référence
    (comme « Partir des données de démo » du navigateur, §11), sauvegarde du jour d'abord. En Solo, le technicien
    « moi » créé à l'étape « compte » est recréé dans la table de la démo (technicien_moi : même prénom et nom), le
    brouillon et le compte responsable lié suivent son nouvel identifiant. En tenant VERROU_ECRITURE. T200 : un
    fichier en place abîmé (techniciens.csv de l'étape « compte ») arrête tout avant la moindre écriture dans les
    tables (409 « fichier_abime ») ; T206 : la sauvegarde du jour est faite avant ces gardes."""
    verifier_ecriture_permise(config)
    date_reference, textes = lire_jeu_de_demo()
    ancien = brouillon.get('solo_technicien_id', '')
    moi = technicien_par_id(config, ancien) if ancien else None
    aujourd_hui = datetime.date.fromtimestamp(maintenant_s(config))
    jours = int((aujourd_hui - datetime.date.fromisoformat(date_reference)).days / 7) * 7
    faire_sauvegarde_quotidienne(config)
    actuels = {table: lire_octets(chemin_table(config, table)) for table in TABLES}
    for table in TABLES:
        verifier_fichier_en_place(table, actuels[table])
    for table in TABLES:
        ecrire_fichier_de_donnees(config, table, decaler_texte_csv(textes[table], jours), actuels[table],
                                  sauvegarde_du_jour=False)
    if moi is not None:
        nouveau = technicien_moi(config, moi.get('prenom', ''), moi.get('nom', ''))
        brouillon['solo_technicien_id'] = nouveau
        if nouveau != ancien:
            for compte in lire_comptes(config):
                if compte.get('technicien_id') == ancien:
                    modifier_compte(config, compte['identifiant'], origine, technicien_id=nouveau)
    return len(TABLES)


class Configuration:
    """Réglages du serveur, calculés une fois au démarrage."""

    def __init__(self, dossier_donnees, hotes_supplementaires, servir_tests=False):
        self.dossier_donnees = os.path.abspath(dossier_donnees)
        self.dossier_documents = os.path.join(self.dossier_donnees, 'documents')
        self.dossier_sauvegardes = os.path.join(self.dossier_donnees, 'sauvegardes')
        self.nom_pc = socket.gethostname().lower()
        self.hotes_supplementaires = [hote.lower().strip() for hote in hotes_supplementaires]
        self.servir_tests = servir_tests    # --servir-tests : tests/fixtures/ servi en plus
        self.port = None            # renseigné quand le port est trouvé (port_http : l'application, ou la porte)
        # Lot 7 (§22.1) : axes du serveur, posés par main() d'après la configuration et la ligne de commande.
        self.reglages = reglages_par_defaut()
        self.ecoute = '127.0.0.1'
        self.contexte_ssl = None    # lot 4 : https en option (--certificat, --cle) ; lot 7 : obligatoire sur le réseau
        # Lot 7 (§22.6) : hors de « ce PC », deux écouteurs — la porte en http sur « port » et l'application en https
        # sur « port_https » ; « porte » vrai dès que les deux sont ouverts (demarrer_serveur).
        self.porte = False
        self.port_https = None
        # Lot 7 (§22.3) : horloge et attente injectables (tests du blocage et des durées de session) ; échecs de
        # connexion en mémoire, remis à zéro à chaque démarrage du serveur.
        self.horloge = time.time
        self.dormir = time.sleep
        self.echecs = CompteursEchecs()
        # Lot 7 (D130, T170) : instant du démarrage, rendu par GET /api/info (« actif depuis » de Paramètres › Accès et
        # installation ; il change quand le serveur s'est relancé).
        self.actif_depuis = maintenant_iso(self)
        # Lot 7 (D133, §22.11) : jour de la dernière copie externe lancée par une écriture après 2 h du matin, et fil
        # de la dernière copie lancée (les tests l'attendent).
        self.copie_externe_jour = None
        self.fil_copie_externe = None
        # Lot 7 (§22.8) : détection de Tailscale (detecter_tailscale) faite au démarrage quand elle est attendue
        # (tailscale_attendu), puis rafraîchie par /api/info au plus une fois par 10 minutes ; None sinon.
        self.tailscale = None
        self.tailscale_lu_a = None
        # Lot 7 (§22.10, T167) : assistant d'installation — dossier de Prévo et système injectables (les tests déplacent
        # une copie et simulent Linux) ; élévation (Installer_demarrage.ps1) et relance remplaçables, jamais lancées
        # par les tests.
        self.dossier_application = DOSSIER_APPLICATION
        self.systeme = sys.platform
        self.lancer_eleve = lancer_script_powershell
        self.relancer = lambda dossier=None: relancer_prevo(self, dossier)
        # T185 (D168, D169) : état du format des données, posé par migrer_donnees_au_demarrage (main, avant les
        # écouteurs) ; rendu par GET /api/info, lu par verifier_ecriture_permise (lecture seule). None hors de main.
        self.format_donnees = None
        # Dossiers jamais servis en statique : le dossier de données choisi et donnees/
        # à côté de serveur.py (même si --donnees pointe ailleurs).
        self.dossiers_interdits_statique = [
            self.dossier_donnees, os.path.join(DOSSIER_APPLICATION, 'donnees')]

    @property
    def schema(self):
        """Schéma des adresses que Prévo donne (console, /api/info, QR, étiquettes) : avec la porte, toujours http sur
        port_http — l'adresse https:<port_https> n'est jamais donnée (CS137), la porte y conduit les téléphones."""
        return 'https' if self.contexte_ssl is not None and not self.porte else 'http'

    def adresse_locale(self):
        return '%s://localhost:%d/' % (self.schema, self.port)

    @property
    def ce_pc_seulement(self):
        """Portée « ce PC » (§22.1) : Prévo n'écoute que sur 127.0.0.1 et aucun mandataire ne le publie ; aucun
        téléphone ne le joint (défaut trouvé par la recette du lot 7 : les écrans le disent)."""
        return self.ecoute == '127.0.0.1' and not self.reglages.get('mandataire')

    def adresses_reseau(self):
        """Adresses données pour les téléphones et les QR. Derrière un mandataire sur ce PC (Tailscale, Intranet :
        écoute 127.0.0.1), celles des noms acceptés en https, par lesquels le mandataire publie Prévo. Sinon les
        adresses du PC sur port_http : la porte hors de « ce PC » ; en portée « ce PC », la même adresse, qui ne
        répond pas encore mais répondra dès que Prévo sera ouvert au Wi-Fi (porte sur le même port : une étiquette
        imprimée reste valable) — les écrans le disent (ce_pc_seulement de /api/info)."""
        noms = [nom for nom in (self.reglages.get('noms') or []) if nom]
        if self.ecoute == '127.0.0.1' and self.reglages.get('mandataire') and noms:
            return ['https://%s/' % nom for nom in noms]
        return ['%s://%s:%d/' % (self.schema, ip, self.port) for ip in adresses_ip_reseau()]


# ---------------------------------------------------------------------------
# Relais vers le fournisseur d'IA (lot 4)
# ---------------------------------------------------------------------------

class _SansRedirection(urllib.request.HTTPRedirectHandler):
    """Le relais ne suit jamais une redirection : il rend la réponse 3xx telle quelle."""

    def redirect_request(self, *arguments, **options):
        return None


OUVREUR_SANS_REDIRECTION = urllib.request.build_opener(_SansRedirection)

# Portée du fournisseur (D67, ARCHITECTURE.md §17.1 ; même règle que Ia.portee de js/modules/ia.js) :
# boucle locale et adresses privées restent dans l'atelier ; toute autre adresse est « distante ».
RESEAUX_ATELIER = tuple(ipaddress.ip_network(reseau) for reseau in (
    '127.0.0.0/8', '::1/128',                                               # boucle locale
    '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '169.254.0.0/16',      # adresses privées IPv4
    'fc00::/7', 'fe80::/10'))                                               # adresses privées IPv6
MOTIF_NOM_LOCAL = re.compile(r'[a-z0-9_-]+(\.[a-z0-9_-]+)*\.local', re.ASCII)     # mDNS : pc-atelier.local
MESSAGE_DISTANT_REFUSE = traduisible('ia.en_ligne_refuse',
                                     'Les fournisseurs d\'IA en ligne ne sont pas autorisés sur le PC serveur.')
MESSAGE_REGLE_SUR_LE_SERVEUR = traduisible('ia.demande_refusee',
                                           'Demande refusée : seuls « chemin », « methode » et « corps » sont '
                                           'acceptés ; l\'adresse et la clé du fournisseur sont réglées sur le PC '
                                           'serveur.')
LIBELLES_FOURNISSEURS_IA = {'ollama': 'Ollama', 'openai': 'API compatible OpenAI'}


def adresse_fournisseur(url):
    """Adresse de base du fournisseur, contrôlée : http ou https, un hôte, ni identifiant, ni
    paramètres, ni fragment, ni espace ou caractère de contrôle. ErreurHttp(400) sinon (le message
    ne reprend jamais l'adresse)."""
    if not isinstance(url, str) or not url.strip():
        raise ErreurHttp(400, traduisible('ia.adresse_manquante', 'Adresse du fournisseur d\'IA manquante.'))
    texte = url.strip()
    if any(caractere.isspace() or ord(caractere) < 0x20 or ord(caractere) == 0x7f for caractere in texte):
        raise ErreurHttp(400, traduisible('ia.adresse_invalide_espace',
                                          'Adresse du fournisseur d\'IA invalide (espace ou caractère de contrôle).'))
    try:
        morceaux = urlsplit(texte)
        morceaux.port                               # lève ValueError si le port est illisible
    except ValueError:
        raise ErreurHttp(400, traduisible('ia.adresse_invalide', 'Adresse du fournisseur d\'IA invalide.'))
    if morceaux.scheme not in ('http', 'https') or not morceaux.hostname:
        raise ErreurHttp(400, traduisible('ia.adresse_invalide_protocole',
                                          'Adresse du fournisseur d\'IA invalide (http:// ou https:// attendu).'))
    if '@' in morceaux.netloc or morceaux.query or morceaux.fragment or '?' in texte or '#' in texte:
        raise ErreurHttp(400, traduisible('ia.adresse_invalide_parametres',
                                          'Adresse du fournisseur d\'IA invalide (ni identifiant, ni paramètres).'))
    return texte.rstrip('/')


def cle_ia(reglages):
    """Clé du fournisseur d'IA du PC serveur : PREVO_IA_CLE lue au démarrage (« _ia_cle »), sinon « ia_cle » du
    fichier ; '' sans clé. Jamais écrite dans un fichier, une réponse, un message ou la console."""
    return reglages.get('_ia_cle', reglages.get('ia_cle', '')) or ''


def cle_ia_lisible(cle):
    """Caractères ASCII visibles (et espace) seulement : l'en-tête HTTP ne sait pas en porter d'autres."""
    return all(' ' <= caractere <= '~' for caractere in cle)


def lire_demande_ia(corps, reglages):
    """Demande de relais vérifiée : { cible, methode, octets, entetes, delai }. ErreurHttp(400) sinon.

    Audit M1, M3 (§22.12) : le corps ne porte que chemin, methode et corps (toute autre clé, « url », « cle » ou
    « delai » compris → 400) ; l'adresse vient de « ia_url », la clé du PC serveur (cle_ia) est la seule mise dans
    « Authorization » et le délai est DELAI_IA_S. Aucun message ne reprend l'adresse ni la clé.
    """
    try:
        demande = json.loads(corps.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        raise ErreurHttp(400, traduisible('ia.demande_illisible', 'Demande illisible (JSON attendu).'))
    if not isinstance(demande, dict):
        raise ErreurHttp(400, traduisible('ia.demande_pas_un_objet', 'Demande illisible (objet JSON attendu).'))
    if any(nom not in CLES_DEMANDE_IA for nom in demande):
        raise ErreurHttp(400, MESSAGE_REGLE_SUR_LE_SERVEUR)
    chemin = demande.get('chemin')
    if chemin not in CHEMINS_IA:
        raise ErreurHttp(400, traduisible('ia.chemin_non_autorise', 'Chemin non autorisé pour l\'IA ({chemins}).',
                                          chemins=', '.join(CHEMINS_IA)))
    methode = demande.get('methode', 'POST')
    if methode not in ('GET', 'POST'):
        raise ErreurHttp(400, traduisible('ia.methode_non_autorisee',
                                          'Méthode non autorisée pour l\'IA (GET ou POST).'))
    entetes = {'Accept': 'application/json'}
    octets = None
    if methode == 'POST':
        octets = json.dumps(demande.get('corps') or {}, ensure_ascii=False).encode('utf-8')
        entetes['Content-Type'] = 'application/json'
    cle = cle_ia(reglages)
    if cle:
        if not cle_ia_lisible(cle):
            raise ErreurHttp(400, traduisible('ia.cle_illisible',
                                              'Clé du fournisseur d\'IA illisible (réglage du PC serveur : '
                                              'caractères ASCII seulement).'))
        entetes['Authorization'] = 'Bearer ' + cle
    return {'cible': adresse_fournisseur(reglages.get('ia_url')) + '/' + chemin, 'methode': methode, 'octets': octets,
            'entetes': entetes, 'delai': DELAI_IA_S}


def fournisseur_distant(adresse):
    """Vrai si l'adresse (déjà contrôlée par adresse_fournisseur) sort de l'atelier (D67).

    Décidé SANS résolution DNS, qui pourrait faire désigner n'importe quelle machine à un nom : une
    adresse IP écrite est classée par ipaddress (RESEAUX_ATELIER) ; parmi les noms, seuls « localhost »
    et les noms en « .local » restent dans l'atelier. « *.localhost » est distant : Windows ne le
    résout pas forcément vers ce PC.
    """
    hote = urlsplit(adresse).hostname or ''
    try:
        ip = ipaddress.ip_address(hote)
    except ValueError:
        return not (hote == 'localhost' or MOTIF_NOM_LOCAL.fullmatch(hote))
    if getattr(ip, 'ipv4_mapped', None) is not None:                # ::ffff:192.168.1.20 = 192.168.1.20
        ip = ip.ipv4_mapped
    return not any(ip in reseau for reseau in RESEAUX_ATELIER)


def portee_fournisseur(adresse):
    """Où vont les textes (même classement que fournisseur_distant et Ia.portee en mode serveur) :
    'pc-atelier' (boucle locale : le PC serveur), 'atelier' (adresse privée, nom en .local) ou 'distant'."""
    if fournisseur_distant(adresse):
        return 'distant'
    hote = urlsplit(adresse).hostname or ''
    try:
        ip = ipaddress.ip_address(hote)
    except ValueError:
        return 'pc-atelier' if hote == 'localhost' else 'atelier'
    if getattr(ip, 'ipv4_mapped', None) is not None:
        ip = ip.ipv4_mapped
    return 'pc-atelier' if ip.is_loopback else 'atelier'


def distant_autorise(config):
    """Fournisseurs d'IA en ligne autorisés (D67) : décision du PC serveur seulement, « ia_en_ligne » de la
    configuration ou --ia-en-ligne (audit M2, §22.12). parametres.csv n'y est plus pour rien : tout appareil du
    réseau peut l'écrire. Défaut : non."""
    return config.reglages.get('ia_en_ligne') is True


def adresse_ia_configuree(reglages):
    """Adresse du fournisseur réglée sur le PC serveur, contrôlée par adresse_fournisseur ; '' si elle est
    invalide (jamais l'adresse brute : elle pourrait porter un identifiant)."""
    try:
        return adresse_fournisseur(reglages.get('ia_url'))
    except ErreurHttp:
        return ''


def reglages_ia_publics(config):
    """GET /api/ia/reglages (audit M1, M2, M3 ; §22.12) : ce que les postes affichent, jamais la clé."""
    reglages = config.reglages
    url = adresse_ia_configuree(reglages)
    return {'fournisseur': reglages.get('ia_fournisseur') or 'ollama', 'url': url,
            'cle_reglee': bool(cle_ia(reglages)), 'en_ligne': distant_autorise(config),
            'portee': portee_fournisseur(url) if url else 'distant'}


def sans_la_cle(octets, cle):
    """Réponse du fournisseur sans la clé du PC serveur : un fournisseur qui la recopierait ne la fait pas sortir.
    Clés de 8 caractères ou plus (une vraie clé en a bien plus ; masquer un mot court abîmerait la réponse)."""
    if len(cle) < 8 or not cle_ia_lisible(cle):
        return octets
    return octets.replace(cle.encode('ascii'), b'[cle masquee]')


def resume_ia(config):
    """Ligne « Assistant IA » de la console au démarrage : fournisseur, adresse, état de la clé, IA en ligne."""
    reglages = config.reglages
    url = adresse_ia_configuree(reglages)
    cle = cle_ia(reglages)
    etat_cle = ('clé illisible (caractères ASCII attendus)' if cle and not cle_ia_lisible(cle)
                else 'clé réglée' if cle else 'sans clé')
    return '%s, %s ; %s ; fournisseurs en ligne %s.' % (
        LIBELLES_FOURNISSEURS_IA.get(reglages.get('ia_fournisseur'), 'Ollama'),
        url or 'adresse invalide (« ia_url »)', etat_cle, 'autorisés' if distant_autorise(config) else 'refusés')


def lire_reponse_fournisseur(reponse):
    """Corps rendu par le fournisseur, TAILLE_MAX_REPONSE_IA + 1 octets au plus (au-delà : refusé).

    HTTPResponse.read(n) rend sans rien dire le début d'une réponse plus courte que son Content-Length
    (connexion coupée) : ce cas lève ici http.client.IncompleteRead, comme une réponse « chunked » coupée.
    """
    octets = reponse.read(TAILLE_MAX_REPONSE_IA + 1)
    manquants = getattr(reponse, 'length', None)
    if manquants and len(octets) <= TAILLE_MAX_REPONSE_IA:
        raise http.client.IncompleteRead(octets, manquants)
    return octets


def appeler_fournisseur(demande):
    """Envoie la demande vérifiée (lire_demande_ia) sans suivre de redirection ; rend (statut, octets)
    du fournisseur, même pour un statut 3xx, 4xx ou 5xx. ErreurHttp sinon : 400 si l'adresse ne peut
    pas être écrite sur le réseau, 502 si le fournisseur est injoignable ou sa réponse coupée ou
    illisible, 504 si le délai est dépassé. Aucun message ne reprend l'adresse ni la clé."""
    requete = urllib.request.Request(demande['cible'], data=demande['octets'], method=demande['methode'],
                                     headers=demande['entetes'])
    try:
        try:
            reponse = OUVREUR_SANS_REDIRECTION.open(requete, timeout=demande['delai'])
            statut = reponse.status
        except urllib.error.HTTPError as erreur:       # le fournisseur répond 3xx, 4xx ou 5xx : on le rend tel quel
            reponse, statut = erreur, erreur.code
        try:
            octets = lire_reponse_fournisseur(reponse)
        finally:
            reponse.close()
    except urllib.error.URLError as erreur:
        if isinstance(erreur.reason, (socket.timeout, TimeoutError)):
            raise ErreurHttp(504, traduisible('ia.delai_depasse',
                                              'Le fournisseur d\'IA n\'a pas répondu dans le délai.'))
        raise ErreurHttp(502, traduisible('ia.injoignable', 'Fournisseur d\'IA injoignable.'))
    except (socket.timeout, TimeoutError):
        raise ErreurHttp(504, traduisible('ia.delai_depasse', 'Le fournisseur d\'IA n\'a pas répondu dans le délai.'))
    except OSError:
        raise ErreurHttp(502, traduisible('ia.injoignable', 'Fournisseur d\'IA injoignable.'))
    except http.client.InvalidURL:
        raise ErreurHttp(400, traduisible('ia.adresse_invalide', 'Adresse du fournisseur d\'IA invalide.'))
    except http.client.HTTPException:                   # IncompleteRead, BadStatusLine, LineTooLong…
        raise ErreurHttp(502, traduisible('ia.reponse_illisible',
                                          'Réponse du fournisseur d\'IA incomplète ou illisible.'))
    except ValueError:          # adresse que le réseau ne sait pas écrire (nom vide « a..b », non ASCII…)
        raise ErreurHttp(400, traduisible('ia.adresse_invalide', 'Adresse du fournisseur d\'IA invalide.'))
    return statut, octets


def corps_lisible(octets):
    """Corps rendu par le fournisseur : objet JSON si possible, sinon texte."""
    texte = octets.decode('utf-8', 'replace')
    try:
        return json.loads(texte)
    except ValueError:
        return texte


def creer_contexte_ssl(certificat, cle):
    """Contexte TLS du serveur (https en option, lot 4) ; SystemExit avec un message clair sinon."""
    contexte = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contexte.minimum_version = ssl.TLSVersion.TLSv1_2
    try:
        contexte.load_cert_chain(certfile=certificat, keyfile=cle)
    except (OSError, ssl.SSLError, ValueError) as erreur:
        raise SystemExit(traduisible('certificat.illisible',
                                     'Certificat ou clé illisible ({erreur}) : vérifiez les deux fichiers PEM '
                                     'passés à --certificat et --cle.', erreur=erreur))
    return contexte


def creer_dossiers(config):
    """Crée donnees/, donnees/documents/ et donnees/sauvegardes/ s'ils n'existent pas."""
    for dossier in (config.dossier_donnees, config.dossier_documents, config.dossier_sauvegardes):
        os.makedirs(dossier, exist_ok=True)


# ---------------------------------------------------------------------------
# Adresses réseau
# ---------------------------------------------------------------------------

def ip_de_sortie():
    """Adresse IP de la carte réseau qui sert à sortir du PC.

    Un connect() UDP ne fait que choisir l'interface : aucun paquet n'est envoyé.
    """
    connexion = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        connexion.connect(('10.255.255.255', 1))
        return connexion.getsockname()[0]
    except OSError:
        return None
    finally:
        connexion.close()


def ips_du_nom_du_pc():
    """Adresses IPv4 associées au nom du PC."""
    try:
        return socket.gethostbyname_ex(socket.gethostname())[2]
    except OSError:
        return []


def adresses_ip_reseau():
    """Adresses IPv4 du PC joignables par les téléphones (sans les adresses de bouclage)."""
    resultat = []
    for ip in [ip_de_sortie()] + ips_du_nom_du_pc():
        if not ip or ip in resultat:
            continue
        try:
            adresse = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if adresse.is_loopback or adresse.is_unspecified:
            continue
        resultat.append(ip)
    return resultat


# ---------------------------------------------------------------------------
# Contrôle de l'en-tête Host (protection contre le « DNS rebinding »)
# ---------------------------------------------------------------------------

def extraire_nom_hote(valeur_host):
    """« 192.168.1.10:8080 » → « 192.168.1.10 » ; « [::1]:8080 » → « ::1 »."""
    valeur = valeur_host.strip().lower()
    if valeur.startswith('['):
        fin = valeur.find(']')
        return valeur[1:fin] if fin > 0 else ''
    if valeur.count(':') == 1:
        valeur = valeur.split(':')[0]
    if valeur.endswith('.'):
        valeur = valeur[:-1]
    return valeur


def est_une_adresse_ip(texte):
    try:
        ipaddress.ip_address(texte)
        return True
    except ValueError:
        return False


# Suffixes de réseau local acceptés derrière le nom du PC (« pc-atelier.local »…). Un suffixe
# quelconque (« pc-atelier.site-pirate.example ») ouvrirait la porte au « DNS rebinding » : un site
# web malveillant ferait pointer son propre nom vers ce PC. D'autres noms : option --hote.
SUFFIXES_RESEAU_LOCAL = ('.local', '.lan', '.home', '.localdomain', '.home.arpa', '.internal', '.intranet')


def hote_autorise(valeur_host, config):
    """Accepte une adresse IP, « localhost », le nom du PC (seul ou suivi d'un suffixe de réseau
    local) et les noms donnés par --hote."""
    if not valeur_host:
        return False
    hote = extraire_nom_hote(valeur_host)
    if not hote:
        return False
    if est_une_adresse_ip(hote) or hote == 'localhost':
        return True
    if hote == config.nom_pc:
        return True
    if hote.startswith(config.nom_pc + '.') and hote[len(config.nom_pc):] in SUFFIXES_RESEAU_LOCAL:
        return True
    return hote in config.hotes_supplementaires


# ---------------------------------------------------------------------------
# Derrière un mandataire (lot 7, ARCHITECTURE.md §22.7 ; D129, CS128)
# ---------------------------------------------------------------------------

ADRESSES_DE_CE_PC = ('127.0.0.1', '::1')
PROTOCOLES_MANDATES = ('http', 'https')
MESSAGE_HOTE_ORIGINE_REFUSE = traduisible('requete.hote_origine_refuse',
                                          'Nom d\'hôte d\'origine refusé (X-Forwarded-Host) : ajoutez-le aux noms '
                                          'acceptés (« noms » de la configuration).')


def origine_mandatee(gestionnaire):
    """Origine d'une requête derrière un mandataire attesté (§22.7) : {'protocole', 'hote', 'adresse'}, ou None pour
    un client direct. Attestée seulement si « mandataire » est vrai, que la connexion vient de 127.0.0.1 ou ::1 (le
    mandataire tourne sur ce PC : tailscale serve, Caddy, nginx, IIS) et qu'elle porte X-Forwarded-Proto (http ou
    https) et X-Forwarded-Host. Sinon les en-têtes X-Forwarded-* sont ignorés, jamais crus (un client direct peut
    les forger). L'adresse d'origine est la dernière de X-Forwarded-For (celle que le mandataire a vue), si elle se
    lit ; sinon celle de la connexion. L'hôte d'origine garde son port éventuel (adresses données par Prévo)."""
    config = gestionnaire.config
    reglages = getattr(config, 'reglages', None) or {}
    if not reglages.get('mandataire') or gestionnaire.client_address[0] not in ADRESSES_DE_CE_PC:
        return None
    protocole = (gestionnaire.headers.get('X-Forwarded-Proto') or '').split(',')[0].strip().lower()
    hote = (gestionnaire.headers.get('X-Forwarded-Host') or '').split(',')[0].strip().lower()
    if protocole not in PROTOCOLES_MANDATES or not hote or any(c.isspace() or c in '/\\?#' for c in hote):
        return None
    adresse = gestionnaire.client_address[0]
    pour = (gestionnaire.headers.get('X-Forwarded-For') or '').split(',')[-1].strip().strip('[]')
    if pour and est_une_adresse_ip(pour):
        adresse = pour
    return {'protocole': protocole, 'hote': hote, 'adresse': adresse}


# ---------------------------------------------------------------------------
# Analyse et contrôle des chemins
# ---------------------------------------------------------------------------

def segment_dangereux(segment):
    """Un morceau de chemin refusé : « .. », « .git », « a:b » (flux NTFS), « x. » …"""
    if segment.startswith('.'):
        return True
    if ':' in segment or '\x00' in segment:
        return True
    # Windows ignore les points et espaces finaux : « donnees. » = « donnees ».
    return segment.endswith('.') or segment.endswith(' ')


def analyser_chemin(chemin_brut):
    """Découpe le chemin de la requête en morceaux décodés, ou lève ErreurHttp 400.

    On contrôle le chemin brut ET le chemin décodé : « ..%2F » ou « %2e%2e » doivent être
    refusés comme « ../ ». Les barres obliques inverses (« \\ » ou « %5C ») sont refusées.
    """
    chemin_brut = chemin_brut.split('?', 1)[0].split('#', 1)[0]
    if not chemin_brut.startswith('/'):
        raise ErreurHttp(400, traduisible('chemin.refuse', 'Chemin refusé.'))
    if '\\' in chemin_brut or '%5c' in chemin_brut.lower():
        raise ErreurHttp(400, traduisible('chemin.refuse', 'Chemin refusé.'))
    chemin_decode = unquote(chemin_brut)
    # « % » restant = double encodage (« %252e ») : refusé par prudence.
    if '\\' in chemin_decode or '%' in chemin_decode:
        raise ErreurHttp(400, traduisible('chemin.refuse', 'Chemin refusé.'))
    for chemin in (chemin_brut, chemin_decode):
        morceaux = chemin[1:].split('/')
        if morceaux == ['']:
            continue                     # « / » tout seul : la page d'accueil
        for morceau in morceaux:
            if morceau == '' or segment_dangereux(morceau):
                raise ErreurHttp(400, traduisible('chemin.refuse', 'Chemin refusé.'))
    return chemin_decode[1:].split('/')


def chemins_egaux(chemin_a, chemin_b):
    return os.path.normcase(chemin_a) == os.path.normcase(chemin_b)


def est_sous_dossier(chemin, dossier):
    """Vrai si « chemin » (déjà résolu) est dans « dossier » ou en est un sous-dossier."""
    dossier_resolu = os.path.realpath(dossier)
    try:
        commun = os.path.commonpath([dossier_resolu, chemin])
    except ValueError:                   # disques différents sous Windows
        return False
    return chemins_egaux(commun, dossier_resolu)


def chemin_sous(dossier, *morceaux):
    """Chemin résolu de dossier/morceaux…, refusé (400) s'il sort du dossier."""
    base = os.path.realpath(dossier)
    chemin = os.path.realpath(os.path.join(base, *morceaux))
    if chemins_egaux(chemin, base) or not est_sous_dossier(chemin, base):
        raise ErreurHttp(400, traduisible('chemin.refuse', 'Chemin refusé.'))
    # Après résolution (raccourcis Windows « GIT~1 », liens…), aucun morceau caché.
    try:
        relatif = os.path.relpath(chemin, base)
    except ValueError:                  # « nul », « con »… : périphériques Windows, autre « lecteur »
        raise ErreurHttp(400, traduisible('chemin.refuse', 'Chemin refusé.'))
    for morceau in relatif.split(os.sep):
        if morceau.startswith('.'):
            raise ErreurHttp(400, traduisible('chemin.refuse', 'Chemin refusé.'))
    return chemin


def commence_par(morceaux, dossier):
    """Vrai si « morceaux » désigne un fichier SOUS « dossier » (tuple de noms en minuscules).

    (['js', 'lib', 'x.js'], ('js',)) → vrai ; (['js'], ('js',)) → faux (le dossier lui-même).
    """
    return len(morceaux) > len(dossier) and tuple(morceaux[:len(dossier)]) == dossier


def chemin_public(morceaux, servir_tests):
    """Vrai si le chemin (morceaux déjà contrôlés par analyser_chemin) est dans la liste blanche.

    servir_tests : vrai avec l'option --servir-tests (tests/fixtures/ servi en plus).
    """
    minuscules = [morceau.lower() for morceau in morceaux]
    if len(minuscules) == 1:
        return minuscules[0] in FICHIERS_PUBLICS
    dossiers = DOSSIERS_PUBLICS + ((DOSSIER_FIXTURES,) if servir_tests else ())
    return any(commence_par(minuscules, dossier) for dossier in dossiers)


def fichier_de_la_porte(minuscules):
    """Vrai si la porte sert ce chemin (minuscules) tel quel à un client du réseau (§22.6) : ses fichiers sous acces/
    (sauf porte.html, toujours rendue avec son port https), le favicon, les polices de la charte et les textes de
    l'interface (js/i18n.js et js/i18n/, chantier multilingue : textes publics, aucune donnée). Rien d'autre : ni
    index.html, ni le reste de js/, ni css/ hors polices — aucune donnée, aucun écran de l'application."""
    if minuscules == ['favicon.svg'] or minuscules == ['js', 'i18n.js']:
        return True
    if commence_par(minuscules, ('css', 'polices')) or commence_par(minuscules, DOSSIER_TEXTES):
        return True
    return commence_par(minuscules, DOSSIER_PORTE) and minuscules != ['acces', 'porte.html']


def morceaux_resolus(chemin, dossier):
    """Morceaux de « chemin » (déjà résolu par chemin_sous) relatifs à « dossier ».

    Sert à recontrôler la liste blanche APRÈS résolution : un raccourci Windows (jonction,
    lien) rangé dans js/ ne doit pas permettre de lire un fichier situé ailleurs.
    """
    return os.path.relpath(chemin, os.path.realpath(dossier)).split(os.sep)


def chemin_table(config, table):
    """Chemin du CSV d'une table ; 404 si la table n'est pas une des 24 du schéma."""
    if table not in TABLES:
        raise ErreurHttp(404, traduisible('csv.table_inconnue', 'Table inconnue : {table}.', table=table))
    return chemin_sous(config.dossier_donnees, table + '.csv')


def extension(nom):
    return nom.rsplit('.', 1)[-1].lower() if '.' in nom else ''


def verifier_nom_document(nom, demande=False):
    """Lève ErreurHttp 400 si le nom de document n'est pas autorisé, 415 si son type (extension) ne l'est pas.
    « demande » : nom demandé par un envoi (MOTIF_NOM_DOCUMENT) ; sinon nom d'un document enregistré, avec le préfixe
    d'horodatage facultatif que le serveur impose depuis le lot 7 (MOTIF_NOM_DOCUMENT_ENREGISTRE)."""
    motif = MOTIF_NOM_DOCUMENT if demande else MOTIF_NOM_DOCUMENT_ENREGISTRE
    if not motif.fullmatch(nom) or '..' in nom:
        raise ErreurHttp(400, traduisible('documents.nom_refuse',
                                          'Nom de document refusé : lettres, chiffres, « . », « _ » ou « - ».'))
    if extension(nom) not in TYPES_DOCUMENTS:
        raise ErreurHttp(415, traduisible('documents.type_refuse',
                                          'Type de document refusé. Types acceptés : {types}.',
                                          types=', '.join(sorted(TYPES_DOCUMENTS))))
    if nom.split('.', 1)[0].lower() in NOMS_RESERVES_WINDOWS:
        raise ErreurHttp(400, traduisible('documents.nom_reserve_windows', 'Nom de document réservé par Windows.'))


def verifier_signature_image(nom, octets):
    """Audit F4 : un document d'image (jpg, jpeg, png, gif, webp) doit commencer par la signature de son format,
    sinon 400 et rien n'est écrit. Les autres types ne sont pas contrôlés (l'extension décide du type MIME)."""
    type_image = extension(nom)
    signatures = SIGNATURES_IMAGES.get(type_image)
    if signatures is None:
        return
    reconnue = any(octets.startswith(signature) for signature in signatures)
    if type_image == 'webp':
        reconnue = reconnue and octets[8:12] == b'WEBP'
    if not reconnue:
        raise ErreurHttp(400, traduisible('documents.pas_une_image',
                                          'Le contenu n\'est pas une image {format}.', format=type_image))


def verifier_nom_sauvegarde(nom):
    if not isinstance(nom, str) or not MOTIF_NOM_SAUVEGARDE.fullmatch(nom):
        raise ErreurHttp(400, traduisible('sauvegardes.nom_invalide', 'Nom de sauvegarde invalide.'))


def lire_objet_json(corps):
    """Corps d'une requête → objet JSON (dict), ou ErreurHttp 400.

    Refuse proprement (400, jamais 500) : UTF-8 invalide, JSON invalide, JSON qui n'est pas un
    objet, et JSON trop imbriqué (« [[[[… » : json.loads lève alors RecursionError).
    """
    try:
        demande = json.loads(corps.decode('utf-8'))
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise ErreurHttp(400, traduisible('requete.json_invalide', 'Corps JSON invalide.'))
    if not isinstance(demande, dict):
        raise ErreurHttp(400, traduisible('requete.json_invalide', 'Corps JSON invalide.'))
    return demande


def lire_motif_sauvegarde(corps):
    """Motif demandé dans le corps de POST /api/sauvegarde, ou None (sauvegarde manuelle).

    Corps vide (ou seulement des blancs) : None, comme avant. Sinon le corps doit être un objet
    JSON ; sa clé « motif », si elle est présente, doit être un des MOTIFS_SAUVEGARDE (400 sinon :
    jamais un texte libre, qui pourrait contenir « ../ » ou un nom réservé).
    """
    if not corps.strip():
        return None
    demande = lire_objet_json(corps)
    motif = demande.get('motif')
    if motif is None:
        return None
    if not isinstance(motif, str) or motif not in MOTIFS_SAUVEGARDE:
        raise ErreurHttp(400, traduisible('sauvegardes.motif_refuse',
                                          'Motif de sauvegarde refusé. Motifs acceptés : {motifs}.',
                                          motifs=', '.join(MOTIFS_SAUVEGARDE)))
    return motif


# ---------------------------------------------------------------------------
# Fichiers : lecture, versions, écriture atomique
# ---------------------------------------------------------------------------

def empreinte(octets):
    """Version d'un fichier = SHA-256 du contenu, 16 premiers caractères hexadécimaux."""
    return hashlib.sha256(octets).hexdigest()[:16]


def lire_octets(chemin):
    """Contenu du fichier, ou None s'il n'existe pas (un dossier compte comme absent)."""
    if os.path.isdir(chemin):
        return None
    try:
        with open(chemin, 'rb') as fichier:
            return fichier.read()
    except FileNotFoundError:
        return None


def date_modification(chemin):
    horodatage = os.path.getmtime(chemin)
    return datetime.datetime.fromtimestamp(horodatage).strftime('%Y-%m-%d %H:%M:%S')


def remplacer_avec_essais(source, cible):
    """os.replace, réessayé si la cible est verrouillée (Excel) ; 423 au bout de 3 essais."""
    for numero_essai in range(1, ESSAIS_SI_VERROUILLE + 1):
        try:
            os.replace(source, cible)
            return
        except PermissionError:
            if numero_essai == ESSAIS_SI_VERROUILLE:
                raise ErreurHttp(423, message_fichier_verrouille(cible))
            time.sleep(PAUSE_ENTRE_ESSAIS_S)


def ecrire_atomique(chemin, octets):
    """Écrit le fichier d'un coup : soit l'ancien contenu reste, soit le nouveau est complet.

    1. écriture dans un fichier temporaire du même dossier (nom commençant par « . ») ;
    2. flush + fsync : les octets sont vraiment sur le disque ;
    3. os.replace : remplacement instantané de l'ancien fichier.
    """
    dossier, nom = os.path.split(chemin)
    descripteur, chemin_temporaire = tempfile.mkstemp(
        prefix='.' + nom + '.', suffix='.tmp', dir=dossier)
    try:
        with os.fdopen(descripteur, 'wb') as fichier:
            fichier.write(octets)
            fichier.flush()
            os.fsync(fichier.fileno())
        remplacer_avec_essais(chemin_temporaire, chemin)
    finally:
        if os.path.exists(chemin_temporaire):
            os.remove(chemin_temporaire)


def premiere_ligne(octets):
    """Première ligne d'un contenu CSV (sans BOM, sans fin de ligne) et le reste du contenu."""
    if octets.startswith(BOM_UTF8):
        octets = octets[len(BOM_UTF8):]
    position = octets.find(b'\n')
    if position == -1:
        return octets.rstrip(b'\r'), b''
    return octets[:position].rstrip(b'\r'), octets[position + 1:]


def est_utf8(octets):
    try:
        octets.decode('utf-8')
        return True
    except UnicodeDecodeError:
        return False


# ---------------------------------------------------------------------------
# Formats des données (miroir de js/formats.js, T184)
# ---------------------------------------------------------------------------

# Registre des formats des fichiers de données, mêmes règles que js/formats.js (décisions D167 et D168 ;
# ARCHITECTURE.md §5.6, §14.1, §20.2) : colonnes et tables de chaque format, format d'un fichier d'après son en-tête,
# format d'une base (parametres.version_schema), étapes de passage pures et idempotentes, une ligne de journal par
# étape. Le format est un entier, distinct de la version de l'application ; le format courant est VERSION_SCHEMA_CSV,
# ses colonnes sont COLONNES_PAR_TABLE et ses tables TABLES. Rien ici ne lit ni n'écrit de fichier ; le passage au
# format courant au démarrage du serveur (T185, migrer_donnees_au_demarrage) s'en sert, aucune route.
# Une base a la forme {<table>: {'entete': [noms…], 'lignes': [{<colonne>: '<cellule>'}]}} : les cellules sont celles
# du fichier, telles que lire_csv_tolerant les rend (apostrophe de protection comprise), pour être réécrites telles
# quelles par ecrire_tableau_csv. C'est la seule différence avec la base en mémoire de js/formats.js (valeurs relues
# sans l'apostrophe) : version_de_base retire l'apostrophe avant de lire le nombre (Donnees.csv.relireValeur), et
# l'étape écrit version_schema comme Prévo l'écrit dans le fichier (« '3 », Donnees.csv.ecrireValeur). Les tests
# tests/test_formats_serveur.py comparent ces fonctions à js/formats.js et à Donnees.csv, octet pour octet.

PREMIER_FORMAT = 1
CLE_VERSION_SCHEMA = 'version_schema'
VERSION_SCHEMA_PAR_DEFAUT = 1           # version_schema absent ou illisible : fichiers du lot 1 (format 1)
# Premier format des tables et des colonnes apparues après le format 1 (depuisVersion de js/schema.js), toujours en fin
# de table pour les colonnes ; les autres existent depuis le format 1. RENVOI CROISÉ : cohérence avec js/schema.js et
# avec COLONNES_DES_FORMATS_SUIVANTS vérifiée par tests/test_formats_serveur.py.
PREMIER_FORMAT_DES_TABLES = {'wiki_pages': 3, 'wiki_journal': 3}
PREMIER_FORMAT_DES_COLONNES = {
    'equipements': {'valeur_remplacement': 2},
    'demandes': {'symptome_code': 2, 'ot_origine_id': 2},
    'ordres_travail': {'anomalie_constatee': 2, 'astuce': 3},
}
# Valeur par défaut des champs qui en ont une (« defaut » de js/schema.js ; les autres : ''), mise par une étape dans
# chaque ligne d'une colonne qu'elle ajoute. Aucun de ces champs n'est un texte : la cellule écrite est la valeur même,
# sans apostrophe. RENVOI CROISÉ : cohérence avec js/schema.js vérifiée par tests/test_formats_serveur.py.
DEFAUTS_DES_CHAMPS = {
    'equipements': {'criticite': 'B', 'statut': 'en service', 'actif': '1'},
    'demandes': {'statut': 'Nouvelle'},
    'ordres_travail': {'statut': 'Créé', 'arret_production': '0', 'remise_service': '0', 'anomalie_constatee': '0'},
    'ot_operations': {'fait': '0'},
    'gammes': {'declencheur': 'date', 'actif': '1'},
    'articles': {'critique': '0', 'actif': '1'},
    'techniciens': {'actif': '1'},
    'controles_reglementaires': {'observations_levees': '0'},
    'achats': {'statut': 'demandée'},
    'wiki_pages': {'version': '0', 'statut': 'active'},
    'wiki_journal': {'anterieure': '0', 'essais': '0'},
}
# Blancs de JavaScript (\s et trim : espaces Unicode, fins de ligne, BOM), pour lire les noms de colonne et les nombres
# comme le navigateur ; codes en clair, jamais de caractère invisible dans ce fichier.
BLANCS_JS = frozenset(chr(code) for code in (0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x20, 0xA0, 0x1680, 0x2028, 0x2029, 0x202F,
                                             0x205F, 0x3000, 0xFEFF) + tuple(range(0x2000, 0x200B)))
CARACTERE_BOM = chr(0xFEFF)
PREMIERE_MARQUE_D_ACCENT, DERNIERE_MARQUE_D_ACCENT = 0x0300, 0x036F     # MOTIF_ACCENTS de js/formats.js
# Protection par apostrophe d'un champ texte (Donnees.csv, §3.2) : début de formule, ou valeur qu'Excel prendrait pour
# un nombre, une date, une fraction, une heure ou un pourcentage (motifs recopiés de js/donnees.js).
MOTIF_DEBUT_DANGEREUX_JS = re.compile(r'[=+\-@\t\r]')
MOTIFS_NOMBRE_DATE_FRACTION_JS = tuple(re.compile(motif) for motif in (
    r'[0-9]+([.,][0-9]+)?',
    r'[0-9]+([.,][0-9]+)?[eE][+-]?[0-9]+',
    r'[0-9]{1,4}[/.-][0-9]{1,2}([/.-][0-9]{1,4})?',
    r'[0-9]{1,2}:[0-9]{2}(:[0-9]{2})?',
    r'[0-9]+([.,][0-9]+)?[' + ''.join(re.escape(blanc) for blanc in sorted(BLANCS_JS)) + ']?%',
))
MOTIF_NOMBRE_JS = re.compile(r'([+-]?)([0-9]*)(?:\.([0-9]*))?')      # Donnees.nombre, après retrait des blancs


def sans_blancs_js_aux_bords(texte):
    """texte.trim() de JavaScript : blancs JS (BLANCS_JS) retirés aux deux bords."""
    debut, fin = 0, len(texte)
    while debut < fin and texte[debut] in BLANCS_JS:
        debut += 1
    while fin > debut and texte[fin - 1] in BLANCS_JS:
        fin -= 1
    return texte[debut:fin]


def cle_de_colonne(nom):
    """Clé de comparaison d'un nom de colonne, celle de Formats.formatDuFichier (js/formats.js, cleDeColonne) : BOM et
    blancs de bord retirés, accents retirés, minuscules, blancs et soulignés ignorés. None → ''."""
    texte = '' if nom is None else str(nom)
    if texte.startswith(CARACTERE_BOM):
        texte = texte[1:]
    texte = unicodedata.normalize('NFD', sans_blancs_js_aux_bords(texte))
    texte = ''.join(caractere for caractere in texte
                    if not PREMIERE_MARQUE_D_ACCENT <= ord(caractere) <= DERNIERE_MARQUE_D_ACCENT).lower()
    return ''.join(caractere for caractere in texte if caractere not in BLANCS_JS and caractere != '_')


def premier_format_de_table(table):
    """Premier format où la table existe : 1 pour les tables du brief, 3 pour celles du wiki."""
    return PREMIER_FORMAT_DES_TABLES.get(table, PREMIER_FORMAT)


def colonnes_du_format(table, format=None):
    """Noms des colonnes de la table dans ce format (None : le format courant), dans l'ordre du schéma ; [] si la table
    n'existe pas encore dans ce format ou n'est pas dans le schéma (Formats.colonnes)."""
    voulu = VERSION_SCHEMA_CSV if format is None else format
    if not isinstance(table, str) or table not in COLONNES_PAR_TABLE or premier_format_de_table(table) > voulu:
        return []
    depuis = PREMIER_FORMAT_DES_COLONNES.get(table, {})
    return [colonne for colonne in COLONNES_PAR_TABLE[table] if depuis.get(colonne, PREMIER_FORMAT) <= voulu]


def tables_du_format(format=None):
    """Noms des tables qui existent dans ce format (None : le format courant), dans l'ordre du schéma
    (Formats.tables)."""
    voulu = VERSION_SCHEMA_CSV if format is None else format
    return [table for table in TABLES if premier_format_de_table(table) <= voulu]


def format_du_fichier(table, entete):
    """Format d'un fichier d'après son en-tête (liste de noms, ordre indifférent), comme Formats.formatDuFichier : le
    plus grand format N, du premier format de la table au format courant, dont toutes les colonnes sont dans l'en-tête
    (noms comparés par cle_de_colonne) ; 0 si même les colonnes du premier format manquent (fichier abîmé, en-tête vide
    ou illisible) ; None pour une table inconnue du schéma. Ne lève jamais d'exception."""
    if not isinstance(table, str) or table not in COLONNES_PAR_TABLE:
        return None
    try:
        presentes = {cle_de_colonne(nom) for nom in (entete if isinstance(entete, (list, tuple)) else [])}
        trouve = 0
        for format in range(premier_format_de_table(table), VERSION_SCHEMA_CSV + 1):
            if not all(cle_de_colonne(nom) in presentes for nom in colonnes_du_format(table, format)):
                break                       # les colonnes d'un format contiennent celles des formats précédents
            trouve = format
        return trouve
    except Exception:                       # nom de colonne qui refuse d'être converti en texte
        return 0


def ressemble_nombre_date_fraction_js(valeur):
    """ressembleNombreDateFraction de js/donnees.js : après retrait de [ \\t\\r\\n] aux deux bords."""
    sans_espaces_aux_bords = valeur.strip(' \t\r\n')
    return any(motif.fullmatch(sans_espaces_aux_bords) for motif in MOTIFS_NOMBRE_DATE_FRACTION_JS)


def a_proteger_texte(valeur):
    """Donnees.csv.aProteger pour un champ texte non « protege » (parametres.valeur, colonne inconnue)."""
    return valeur != '' and (MOTIF_DEBUT_DANGEREUX_JS.match(valeur) is not None or valeur.startswith("'")
                             or ressemble_nombre_date_fraction_js(valeur))


def relire_valeur_texte(cellule):
    """Cellule d'un champ texte non « protege » → valeur en mémoire, apostrophe de protection retirée
    (Donnees.csv.relireValeur). None → ''."""
    texte = '' if cellule is None else str(cellule)
    return texte[1:] if texte.startswith("'") and a_proteger_texte(texte[1:]) else texte


def ecrire_valeur_texte(valeur):
    """Valeur en mémoire d'un champ texte non « protege » → cellule écrite, apostrophe ajoutée si besoin
    (Donnees.csv.ecrireValeur). None → ''."""
    texte = '' if valeur is None else str(valeur)
    return "'" + texte if a_proteger_texte(texte) else texte


def nombre_js(valeur):
    """Copie de Donnees.nombre (js/donnees.js) : valeur → nombre (int s'il est entier), ou None si vide ou illisible ;
    virgule décimale et blancs (insécables compris) acceptés."""
    if isinstance(valeur, bool):
        valeur = 'true' if valeur else 'false'
    elif isinstance(valeur, (int, float)):
        return valeur if valeur == valeur and abs(valeur) != float('inf') else None
    texte = sans_blancs_js_aux_bords('' if valeur is None else str(valeur))
    if texte == '':
        return None
    compact = ''.join(caractere for caractere in texte if caractere not in BLANCS_JS).replace(',', '.', 1)
    morceaux = MOTIF_NOMBRE_JS.fullmatch(compact)
    if not morceaux or (morceaux.group(2) == '' and not morceaux.group(3)):
        return None
    signe = '-' if morceaux.group(1) == '-' else ''
    partie_decimale = '.' + morceaux.group(3) if morceaux.group(3) else ''
    converti = float(signe + (morceaux.group(2) or '0') + partie_decimale)
    if abs(converti) == float('inf'):
        return None
    return int(converti) if converti.is_integer() else converti


def colonne_de_champ(noms, champ):
    """Premier nom de « noms » (en-tête, ou clés d'une ligne) qui désigne ce champ (cle_de_colonne) ; None sinon."""
    if champ in noms:
        return champ
    cle = cle_de_colonne(champ)
    return next((nom for nom in noms if cle_de_colonne(nom) == cle), None)


def cle_de_parametre(ligne):
    """Clé d'une ligne de parametres, lue comme Donnees.csv.analyser lit un identifiant (blancs de bord retirés)."""
    colonne = colonne_de_champ(list(ligne), 'cle')
    return sans_blancs_js_aux_bords('' if colonne is None or ligne[colonne] is None else str(ligne[colonne]))


def version_de_base(lignes_parametres):
    """Format d'une base d'après les lignes de parametres.csv ([{colonne: cellule}], cellules du fichier) : même règle
    que Formats.versionDeBase, sur les valeurs relues sans l'apostrophe de protection (« '3 » → 3) : version_schema de
    la première ligne qui porte cette clé, lu comme Donnees.nombre ; absent, vide ou illisible → 1."""
    lignes = lignes_parametres if isinstance(lignes_parametres, (list, tuple)) else []
    for ligne in lignes:
        if isinstance(ligne, dict) and cle_de_parametre(ligne) == CLE_VERSION_SCHEMA:
            colonne = colonne_de_champ(list(ligne), 'valeur')
            lue = nombre_js(relire_valeur_texte(None if colonne is None else ligne[colonne]))
            return VERSION_SCHEMA_PAR_DEFAUT if lue is None else lue
    return VERSION_SCHEMA_PAR_DEFAUT


def copier_table_de_base(table):
    """Copie d'une table de la base : en-tête et lignes copiés (les autres clés de la table sont gardées)."""
    source = table if isinstance(table, dict) else {}
    copie = dict(source)
    entete, lignes = source.get('entete'), source.get('lignes')
    copie['entete'] = list(entete) if isinstance(entete, (list, tuple)) else []
    copie['lignes'] = ([dict(ligne) if isinstance(ligne, dict) else {} for ligne in lignes]
                       if isinstance(lignes, (list, tuple)) else [])
    return copie


def completer_colonnes(table, contenu, format):
    """Ajoute en fin d'en-tête les colonnes du format absentes de la table (comparées par cle_de_colonne), avec la
    valeur par défaut du champ (sinon '') dans chaque ligne qui n'a pas déjà cette colonne. Les colonnes inconnues
    restent à leur place, avec leurs valeurs. Modifie la COPIE reçue."""
    presentes = {cle_de_colonne(nom) for nom in contenu['entete']}
    defauts = DEFAUTS_DES_CHAMPS.get(table, {})
    for colonne in colonnes_du_format(table, format):
        if cle_de_colonne(colonne) in presentes:
            continue
        contenu['entete'].append(colonne)
        presentes.add(cle_de_colonne(colonne))
        for ligne in contenu['lignes']:
            if colonne not in ligne:
                ligne[colonne] = defauts.get(colonne, '')


def poser_version_de_base(parametres, format):
    """parametres.version_schema = format, écrit comme Prévo l'écrit (« '3 ») : la première ligne qui porte la clé,
    sinon une ligne ajoutée en fin (ses autres colonnes à ''). Modifie la COPIE reçue (colonnes cle et valeur
    présentes : completer_colonnes est passé avant)."""
    colonne_cle = colonne_de_champ(parametres['entete'], 'cle')
    colonne_valeur = colonne_de_champ(parametres['entete'], 'valeur')
    cellule = ecrire_valeur_texte(str(format))
    for ligne in parametres['lignes']:
        if cle_de_parametre(ligne) == CLE_VERSION_SCHEMA:
            ligne[colonne_valeur] = cellule
            return
    nouvelle = {colonne: '' for colonne in parametres['entete']}
    nouvelle[colonne_cle] = CLE_VERSION_SCHEMA
    nouvelle[colonne_valeur] = cellule
    parametres['lignes'].append(nouvelle)


def passer_au_format(base, format):
    """Passage d'une base au format « format » (étape additive, §14.1 et §20.2), comme passerAuFormat de
    js/formats.js. Rend une NOUVELLE base où chaque table du format absente est créée vide (en-tête = ses colonnes),
    chaque colonne du format absente d'une table est ajoutée en fin d'en-tête avec sa valeur par défaut, les colonnes
    et tables inconnues sont gardées telles quelles, et parametres.version_schema vaut le format. La base reçue n'est
    pas modifiée ; appliquée deux fois, l'étape donne le même résultat qu'une fois."""
    source = base if isinstance(base, dict) else {}
    nouvelle = {table: copier_table_de_base(contenu) for table, contenu in source.items()}
    for table in tables_du_format(format):
        if table not in nouvelle:
            nouvelle[table] = {'entete': [], 'lignes': []}
        completer_colonnes(table, nouvelle[table], format)
    poser_version_de_base(nouvelle['parametres'], format)
    return nouvelle


class EtapeDeFormat:
    """Une étape du registre : de N à N+1, sa description, et appliquer(base) → nouvelle base (pure, idempotente)."""

    __slots__ = ('de', 'vers', 'description')

    def __init__(self, de, vers, description):
        self.de, self.vers, self.description = de, vers, description

    def appliquer(self, base):
        return passer_au_format(base, self.vers)


# Le registre, dans l'ordre, mêmes étapes et mêmes descriptions que Formats.ETAPES. Un format futur ajoute son étape
# ici ET dans js/formats.js (et VERSION_SCHEMA_CSV) : tests/test_formats_serveur.py compare les deux registres.
ETAPES_FORMAT = (
    EtapeDeFormat(1, 2, 'Format 2 (versions 1.0 et 1.1, §14.1) : colonnes equipements.valeur_remplacement, '
                        'demandes.symptome_code, demandes.ot_origine_id et ordres_travail.anomalie_constatee '
                        '(défaut 0), en fin de table.'),
    EtapeDeFormat(2, 3, 'Format 3 (versions 1.2 et 2.0, §20.2) : colonne ordres_travail.astuce en fin de table, '
                        'tables wiki_pages et wiki_journal (vides).'),
)


def ligne_de_journal_de_format(format):
    """Ligne de journal d'une étape, texte exact de js/formats.js (relu par la suggestion S4 : ne pas le changer)."""
    return 'passage au format %d du fichier' % format


def migrer_tables(base, de, vers):
    """Enchaîne les étapes de « de » à « vers », comme Formats.migrer → (base, journal, etapes) :
    base au format « vers » (nouvel objet ; la base reçue n'est pas modifiée), une ligne de journal « passage au format
    N du fichier » par étape appliquée, et les étapes appliquées ([{'de', 'vers', 'description'}]). « de » est le
    format actuel (version_de_base) ; de >= vers (base déjà au format, ou plus récente) : base rendue telle quelle,
    journal et étapes vides. « vers » : un format entier de 1 au format courant (ValueError sinon) ; « de » illisible :
    TypeError."""
    entier = not isinstance(vers, bool) and (isinstance(vers, int) or (isinstance(vers, float) and vers.is_integer()))
    if not entier or not PREMIER_FORMAT <= vers <= VERSION_SCHEMA_CSV:
        raise ValueError('migrer_tables : format cible inconnu (%s) ; formats connus : %d à %d.'
                         % (vers, PREMIER_FORMAT, VERSION_SCHEMA_CSV))
    if isinstance(de, bool) or not isinstance(de, (int, float)) or de != de:
        raise TypeError('migrer_tables : format de départ illisible (%s).' % (de,))
    vers = int(vers)
    if de >= vers:
        return base, [], []
    courante, journal, etapes = base, [], []
    for etape in ETAPES_FORMAT:
        if etape.vers <= de or etape.vers > vers:
            continue
        courante = etape.appliquer(courante)
        journal.append(ligne_de_journal_de_format(etape.vers))
        etapes.append({'de': etape.de, 'vers': etape.vers, 'description': etape.description})
    return courante, journal, etapes


# ---------------------------------------------------------------------------
# Sauvegardes
# ---------------------------------------------------------------------------

# Lot 7 (D133, ARCHITECTURE.md §22.11) : une sauvegarde manuelle par minute au plus (429), les 60 dernières gardées ;
# copie externe de la sauvegarde quotidienne (clé « copie_sauvegardes ») au démarrage et à la première écriture après
# 2 h du matin, dans un fil à part, les 30 dernières gardées ; « Tester une sauvegarde » relit chaque CSV sans rien
# écrire. Dates et heures des sauvegardes : horloge de la configuration (config.horloge, injectable pour les tests).
MOTIF_NOM_QUOTIDIENNE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', re.ASCII)
MOTIF_NOM_MANUELLE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{6}', re.ASCII)
DELAI_ENTRE_MANUELLES_S = 60
MANUELLES_GARDEES = 60
COPIES_EXTERNES_GARDEES = 30
HEURE_COPIE_EXTERNE = 2                 # la copie de la nuit part à la première écriture après 2 h du matin
ESSAIS_NOM_HORODATE = 25                # nom pris : la seconde suivante est attendue (5 s au plus)
NOM_ETAT_COPIE_EXTERNE = 'copie-externe.json'
PREFIXE_COPIE_EN_COURS = '.prevo-copie-en-cours-'
# T187 (D170, docs/FORMAT.md §8 et §9) : quotidiennes de plus de 30 jours supprimées à chaque nouvelle quotidienne
# (« avant-… » jamais) ; manifeste.json dans chaque sauvegarde ; documents/ dans la seule « avant-import-zip » ;
# sauvegarde « avant-mise-a-jour » au premier démarrage d'une autre version (donnees/derniere-version.json).
QUOTIDIENNES_GARDEES_JOURS = 30
# T206 : les 7 quotidiennes les plus récentes sans fichier abîmé ne sont jamais supprimées, quel que soit leur âge.
QUOTIDIENNES_SAINES_GARDEES = 7
MARQUE_ABIME = 'abime'                          # "abime": true sur l'entrée d'un CSV abîmé du manifeste (T206)
NOM_FICHIERS_ABIMES = 'fichiers-abimes.json'
MOTIF_QUOTIDIENNE = 'quotidienne'               # « motif » du manifeste d'une sauvegarde AAAA-MM-JJ
MOTIF_MANUELLE = 'manuelle'                     # … et d'une sauvegarde AAAA-MM-JJ_HHMMSS
MOTIF_AVANT_MISE_A_JOUR = 'avant-mise-a-jour'
MOTIFS_AVEC_DOCUMENTS = ('avant-import-zip',)
NOM_MANIFESTE = 'manifeste.json'
MODE_DU_MANIFESTE = 'serveur'
TAILLE_MORCEAU_EMPREINTE = 1024 * 1024
NOM_DERNIERE_VERSION = 'derniere-version.json'
VERSION_INCONNUE = 'inconnue'                   # « de » du manifeste quand derniere-version.json manque ou est illisible
# Colonnes ajoutées par un format après le premier (depuisVersion de js/schema.js), toujours en fin de table : une
# sauvegarde faite avant ce format ne les a pas, sans être abîmée (« Tester une sauvegarde »). RENVOI CROISÉ : cohérence
# avec js/schema.js vérifiée par tests/test_sauvegardes_lot7.py.
COLONNES_DES_FORMATS_SUIVANTS = {
    'equipements': ('valeur_remplacement',),
    'demandes': ('symptome_code', 'ot_origine_id'),
    'ordres_travail': ('anomalie_constatee', 'astuce'),
}
VERROU_COPIE_EXTERNE = threading.Lock()     # jamais deux copies externes à la fois


def instant_local(config):
    """Heure locale du serveur (datetime), lue sur config.horloge : nom du jour, nom horodaté, 2 h du matin."""
    return datetime.datetime.fromtimestamp(maintenant_s(config))


def tables_presentes(dossier):
    """Tables (dans l'ordre du schéma) dont le CSV existe dans « dossier »."""
    return [table for table in TABLES if os.path.isfile(os.path.join(dossier, table + '.csv'))]


def motif_du_nom_de_sauvegarde(nom):
    """« motif » du manifeste d'après le nom : « quotidienne » (AAAA-MM-JJ), « manuelle » (AAAA-MM-JJ_HHMMSS), sinon
    la fin du nom (« avant-format-v3 », « avant-restauration », « avant-import-zip »…)."""
    if MOTIF_NOM_QUOTIDIENNE.fullmatch(nom):
        return MOTIF_QUOTIDIENNE
    if MOTIF_NOM_MANUELLE.fullmatch(nom):
        return MOTIF_MANUELLE
    return nom[len('AAAA-MM-JJ_HHMMSS_'):]


def format_des_tables_copiees(dossier):
    """Format des données d'une sauvegarde : version_schema de son parametres.csv (version_de_base, même règle que
    Formats.versionDeBase) ; 1 sans parametres.csv, comme etat_des_fichiers."""
    octets = lire_octets(os.path.join(dossier, 'parametres.csv'))
    if octets is None:
        return VERSION_SCHEMA_PAR_DEFAUT
    return version_de_base(lignes_en_dictionnaires(lire_fichier_de_donnees(octets)))


def est_un_csv_de_table(relatif):
    """Vrai pour « <table>.csv » à la racine d'une sauvegarde (table du schéma)."""
    return relatif.endswith('.csv') and relatif[:-len('.csv')] in TABLES


def fichiers_du_manifeste(dossier):
    """[{"nom", "octets", "sha256"}] de chaque fichier du dossier (chemin relatif en « / », triés par nom), sans le
    manifeste lui-même ; empreinte SHA-256 complète, lue par morceaux (documents volumineux). T206 : l'entrée d'un CSV
    de table abîmé (raisons_fichier_abime, le critère de la garde) porte aussi "abime": true, absente sinon."""
    fichiers = []
    for racine, _, noms in os.walk(dossier):
        for nom in noms:
            chemin = os.path.join(racine, nom)
            relatif = os.path.relpath(chemin, dossier).replace(os.sep, '/')
            if relatif == NOM_MANIFESTE:
                continue
            hachage, taille = hashlib.sha256(), 0
            with open(chemin, 'rb') as fichier:
                for morceau in iter(lambda: fichier.read(TAILLE_MORCEAU_EMPREINTE), b''):
                    hachage.update(morceau)
                    taille += len(morceau)
            decrit = {'nom': relatif, 'octets': taille, 'sha256': hachage.hexdigest()}
            if est_un_csv_de_table(relatif) and raisons_fichier_abime(lire_octets(chemin)):
                decrit[MARQUE_ABIME] = True
            fichiers.append(decrit)
    fichiers.sort(key=lambda decrit: decrit['nom'])
    return fichiers


def ecrire_manifeste(config, dossier, nom_sauvegarde, complement=None):
    """manifeste.json d'une sauvegarde (FORMAT.md §9 ; mêmes champs, dans le même ordre, que Formats.manifeste de
    js/formats.js) : {"application", "version_appli", "format", "date", "motif", "mode": "serveur", …complement,
    "fichiers"}. Écrit en dernier, dans le dossier temporaire, avant son renommage."""
    manifeste = {'application': NOM_APPLICATION, 'version_appli': VERSION_APPLICATION,
                 'format': format_des_tables_copiees(dossier), 'date': maintenant_iso(config),
                 'motif': motif_du_nom_de_sauvegarde(nom_sauvegarde), 'mode': MODE_DU_MANIFESTE}
    manifeste.update(complement or {})
    manifeste['fichiers'] = fichiers_du_manifeste(dossier)
    with open(os.path.join(dossier, NOM_MANIFESTE), 'wb') as fichier:
        fichier.write((json.dumps(manifeste, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    return manifeste


def copier_documents_dans_sauvegarde(config, dossier_sauvegarde):
    """Copie les fichiers de donnees/documents/ (ni sous-dossier, ni fichier caché ou temporaire) dans documents/ de la
    sauvegarde : sauvegarde « avant-import-zip » seulement (T187, D170). Rend le nombre de fichiers copiés."""
    if not os.path.isdir(config.dossier_documents):
        return 0
    cible = os.path.join(dossier_sauvegarde, 'documents')
    os.makedirs(cible, exist_ok=True)
    copies = 0
    for nom in sorted(os.listdir(config.dossier_documents)):
        chemin = os.path.join(config.dossier_documents, nom)
        if nom.startswith('.') or not os.path.isfile(chemin) or est_un_lien(chemin):
            continue
        try:
            shutil.copy2(chemin, os.path.join(cible, nom))
        except PermissionError:
            raise ErreurHttp(423, message_fichier_verrouille(nom))
        copies += 1
    return copies


def copier_tables_dans_sauvegarde(config, nom_sauvegarde, complement=None):
    """Copie tous les CSV présents dans sauvegardes/<nom>/ et renvoie la liste des tables.

    La copie se fait dans un dossier temporaire renommé à la fin : une sauvegarde
    interrompue (panne, disque plein) ne laisse jamais un dossier à moitié rempli.
    T187 (D170) : acces/ (sans sessions.json ni cle.pem), documents/ pour le motif « avant-import-zip » seulement,
    puis manifeste.json en dernier (complement : champs ajoutés au manifeste, ex. « de » et « vers »).
    T206 : la sauvegarde faite, fichiers-abimes.json suit les marques « abime » de son manifeste.
    """
    tables = tables_presentes(config.dossier_donnees)
    dossier_final = os.path.join(config.dossier_sauvegardes, nom_sauvegarde)
    dossier_temporaire = tempfile.mkdtemp(prefix='.en-cours-', dir=config.dossier_sauvegardes)
    try:
        for table in tables:
            nom_fichier = table + '.csv'
            try:
                shutil.copy2(os.path.join(config.dossier_donnees, nom_fichier),
                             os.path.join(dossier_temporaire, nom_fichier))
            except PermissionError:
                raise ErreurHttp(423, message_fichier_verrouille(nom_fichier))
        copier_acces_dans_sauvegarde(config, dossier_temporaire)      # lot 7 : comptes, appareils, journal
        if motif_du_nom_de_sauvegarde(nom_sauvegarde) in MOTIFS_AVEC_DOCUMENTS:
            copier_documents_dans_sauvegarde(config, dossier_temporaire)
        manifeste = ecrire_manifeste(config, dossier_temporaire, nom_sauvegarde, complement)
        os.rename(dossier_temporaire, dossier_final)
    finally:
        if os.path.isdir(dossier_temporaire):
            shutil.rmtree(dossier_temporaire, ignore_errors=True)
    noter_fichiers_abimes(config, [decrit['nom'][:-len('.csv')] for decrit in manifeste['fichiers']
                                   if decrit.get(MARQUE_ABIME) and est_un_csv_de_table(decrit['nom'])])
    return tables


# Marque posée par le mode dossier (js/stockage-dossier.js) pendant qu'il copie une sauvegarde :
# un dossier qui la contient encore est une sauvegarde incomplète (onglet fermé pendant la copie).
MARQUE_SAUVEGARDE_EN_COURS = '.en-cours'


def sauvegarde_complete(dossier):
    return os.path.isdir(dossier) and not os.path.exists(os.path.join(dossier, MARQUE_SAUVEGARDE_EN_COURS))


def faire_sauvegarde_du_jour(config):
    """Copie dans sauvegardes/AAAA-MM-JJ/ si la sauvegarde du jour manque (rien s'il n'y a encore aucun CSV) ; chaque
    nouvelle quotidienne supprime celles de plus de 30 jours (T187), sauf les 7 plus récentes sans fichier abîmé
    (T206, purger_sauvegardes_quotidiennes). Le jour est celui de l'horloge du serveur. Rend
    le nom de la sauvegarde faite, ou None. À appeler en tenant VERROU_ECRITURE."""
    nom_du_jour = instant_local(config).strftime('%Y-%m-%d')
    dossier_du_jour = os.path.join(config.dossier_sauvegardes, nom_du_jour)
    if sauvegarde_complete(dossier_du_jour):
        return None
    if os.path.isdir(dossier_du_jour):          # sauvegarde du jour laissée incomplète : on la refait
        shutil.rmtree(dossier_du_jour, ignore_errors=True)
    if not tables_presentes(config.dossier_donnees):
        return None
    copier_tables_dans_sauvegarde(config, nom_du_jour)
    purger_sauvegardes_quotidiennes(config)
    return nom_du_jour


def marques_du_manifeste(dossier):
    """Noms des fichiers que manifeste.json de la sauvegarde marque « abime » (T206) ; [] s'il n'en marque aucun, ou
    s'il manque ou est illisible. Ne modifie rien."""
    try:
        with open(os.path.join(dossier, NOM_MANIFESTE), 'rb') as fichier:
            fichiers = json.loads(fichier.read().decode('utf-8-sig'))['fichiers']
        return [decrit['nom'] for decrit in fichiers if decrit.get(MARQUE_ABIME) is True]
    except (OSError, UnicodeDecodeError, ValueError, RecursionError, KeyError, TypeError, AttributeError):
        return []


def tables_abimees_de_la_sauvegarde(dossier):
    """Tables dont le CSV de la sauvegarde est abîmé (raisons_fichier_abime), lues sans rien y écrire."""
    return [table for table in TABLES if raisons_fichier_abime(lire_octets(os.path.join(dossier, table + '.csv')))]


def quotidienne_saine(dossier, analyser):
    """Vrai pour une quotidienne sans fichier abîmé (T206). Au moins une marque « abime » au manifeste : abîmée, sans
    analyse ; incomplète (MARQUE_SAUVEGARDE_EN_COURS) : pas saine. Sans marque (manifeste sain d'après T206, manifeste
    plus ancien, ou pas de manifeste : rien ne les distingue), ses CSV sont analysés si « analyser » (la rotation se
    demande si elle compte parmi les 7 saines : candidate à la suppression), même critère que la garde, résultat
    jamais écrit dans la sauvegarde ; sinon elle compte comme saine."""
    if not sauvegarde_complete(dossier) or marques_du_manifeste(dossier):
        return False
    if not analyser:
        return True
    try:
        return not tables_abimees_de_la_sauvegarde(dossier)
    except OSError:                                     # illisible : pas une bonne sauvegarde
        return False


def purger_sauvegardes_quotidiennes(config):
    """Supprime les sauvegardes quotidiennes de plus de 30 jours (D170) : dossiers dont le nom est exactement une vraie
    date AAAA-MM-JJ, plus vieux de 31 jours ou davantage que le jour de l'horloge du serveur. Jamais un autre nom
    (manuelles, « …_avant-… »), un fichier, un lien ni une jonction. T206 : jamais non plus l'une des 7 quotidiennes
    les plus récentes sans fichier abîmé (QUOTIDIENNES_SAINES_GARDEES, quotidienne_saine), quel que soit son âge.
    En partant de la plus récente : rien n'est examiné s'il n'y en a aucune de plus de 30 jours, ni une fois les 7
    saines retenues ; une quotidienne sans marque n'est analysée que si elle a plus de 30 jours (contrat T206, le même
    que le mode dossier). Rend les noms supprimés."""
    aujourd_hui = instant_local(config).date()
    try:
        noms = sorted(os.listdir(config.dossier_sauvegardes), reverse=True)        # la plus récente d'abord
    except OSError:
        return []
    ages = {}
    for nom in noms:
        chemin = os.path.join(config.dossier_sauvegardes, nom)
        if est_une_date(nom) and os.path.isdir(chemin) and not est_un_lien(chemin):
            ages[nom] = (aujourd_hui - datetime.datetime.strptime(nom, '%Y-%m-%d').date()).days
    if all(age <= QUOTIDIENNES_GARDEES_JOURS for age in ages.values()):
        return []                                       # rien à décider : rien n'est examiné
    supprimees, saines = [], 0
    for nom, age in ages.items():
        chemin = os.path.join(config.dossier_sauvegardes, nom)
        ancienne = age > QUOTIDIENNES_GARDEES_JOURS
        if saines < QUOTIDIENNES_SAINES_GARDEES and quotidienne_saine(chemin, analyser=ancienne):
            saines += 1                                 # parmi les 7 plus récentes saines : gardée
        elif ancienne:
            shutil.rmtree(chemin, ignore_errors=True)
            supprimees.append(nom)
    return supprimees


# T206 (contrat, point 4) : donnees/fichiers-abimes.json, {"depuis": {"<table>": "AAAA-MM-JJTHH:MM:SS"}} (heure
# locale, comme les manifestes), date à laquelle Prévo a vu la table abîmée la première fois (raisons_fichier_abime).
# Tenu à jour chaque fois que le serveur connaît l'état de toutes les tables : au démarrage (après le passage au
# format), à chaque sauvegarde (marques de son manifeste), après une restauration. Table abîmée : date gardée si elle
# y est, sinon « maintenant » ; table redevenue saine : retirée ; plus rien d'abîmé : fichier supprimé. Jamais dans
# une sauvegarde (copier_tables_dans_sauvegarde ne copie que les CSV et acces/), jamais remplacé par une restauration ;
# rien en lecture seule (données plus récentes). Rendu par GET /api/info, « format » → « abimes_depuis ».
MOTIF_DATE_DEPUIS = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}', re.ASCII)


def chemin_fichiers_abimes(config):
    return os.path.join(config.dossier_donnees, NOM_FICHIERS_ABIMES)


def lire_fichiers_abimes(config):
    """{table: "AAAA-MM-JJTHH:MM:SS"} de fichiers-abimes.json (tables du schéma, dates bien formées), dans l'ordre du
    schéma ; {} si le fichier manque ou est illisible."""
    try:
        with open(chemin_fichiers_abimes(config), 'rb') as fichier:
            depuis = json.loads(fichier.read().decode('utf-8-sig')).get('depuis')
    except (OSError, UnicodeDecodeError, ValueError, RecursionError, AttributeError):
        return {}
    if not isinstance(depuis, dict):
        return {}
    return {table: depuis[table] for table in TABLES
            if isinstance(depuis.get(table), str) and MOTIF_DATE_DEPUIS.fullmatch(depuis[table])}


def noter_fichiers_abimes(config, abimees=None):
    """Met fichiers-abimes.json à jour (en tête de cette partie) ; abimees : les tables abîmées, ou None pour les
    trouver en lisant donnees/. Jamais d'exception vers l'appelant : un échec est dit sur la console."""
    etat = getattr(config, 'format_donnees', None)
    if etat and etat.get('plus_recent'):
        return
    try:
        if abimees is None:
            abimees = [table for table in TABLES if raisons_fichier_abime(lire_octets(chemin_table(config, table)))]
        ancien = lire_fichiers_abimes(config)
        maintenant = maintenant_iso(config)
        neuf = {table: ancien.get(table, maintenant) for table in TABLES if table in abimees}
        chemin = chemin_fichiers_abimes(config)
        if neuf == ancien and (neuf or not os.path.exists(chemin)):
            return
        if neuf:
            ecrire_atomique(chemin, (json.dumps({'depuis': neuf}, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        else:
            os.remove(chemin)
    except (ErreurHttp, OSError) as erreur:
        afficher(PREFIXE_CONSOLE_SAUVEGARDES + '%s non mis à jour (%s).'
                 % (NOM_FICHIERS_ABIMES, getattr(erreur, 'message', None) or erreur))


def noter_table_importee(config, table, abimee, depuis=None):
    """T213 : après l'écriture d'une table par l'import ZIP (PUT avec X-Prevo-Remplacer-Abime: 1), fichiers-abimes.json
    suit cette table : abîmée → « depuis » (date du manifeste du ZIP, X-Prevo-Abime-Depuis : gardée telle quelle,
    jamais remise à zéro par l'import), sinon la date déjà notée, sinon maintenant ; saine → retirée. Jamais
    d'exception vers l'appelant : un échec est dit sur la console (la table, elle, est écrite)."""
    try:
        ancien = lire_fichiers_abimes(config)
        dates = dict(ancien)
        if abimee:
            dates[table] = depuis or ancien.get(table) or maintenant_iso(config)
        else:
            dates.pop(table, None)
        neuf = {nom: dates[nom] for nom in TABLES if nom in dates}
        chemin = chemin_fichiers_abimes(config)
        if neuf == ancien and (neuf or not os.path.exists(chemin)):
            return
        if neuf:
            ecrire_atomique(chemin, (json.dumps({'depuis': neuf}, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        else:
            os.remove(chemin)
    except (ErreurHttp, OSError) as erreur:
        afficher(PREFIXE_CONSOLE_SAUVEGARDES + '%s non mis à jour (%s).'
                 % (NOM_FICHIERS_ABIMES, getattr(erreur, 'message', None) or erreur))


def faire_sauvegarde_quotidienne(config):
    """Avant chaque écriture CSV : la sauvegarde du jour si elle manque (faire_sauvegarde_du_jour, rotation comprise),
    puis, à la première écriture après 2 h du matin, la copie externe du jour, lancée dans son propre fil (D133). À
    appeler en tenant VERROU_ECRITURE.
    """
    faire_sauvegarde_du_jour(config)
    lancer_copie_externe_si_due(config)


def nouveau_nom_horodate(config, suffixe=''):
    """« AAAA-MM-JJ_HHMMSS » (horloge du serveur) + suffixe, en attendant la seconde suivante si le nom est pris ;
    503 si l'horloge n'avance plus (5 s sans nom libre)."""
    for _ in range(ESSAIS_NOM_HORODATE):
        nom = instant_local(config).strftime('%Y-%m-%d_%H%M%S') + suffixe
        if not os.path.exists(os.path.join(config.dossier_sauvegardes, nom)):
            return nom
        time.sleep(0.2)
    raise ErreurHttp(503, traduisible('sauvegardes.aucun_nom_libre',
                                      'Sauvegarde impossible : aucun nom horodaté libre (l\'horloge du serveur '
                                      'n\'avance plus ?).'))


def sauvegardes_manuelles(config):
    """Noms des sauvegardes manuelles (AAAA-MM-JJ_HHMMSS, sans suffixe), de la plus ancienne à la plus récente."""
    try:
        noms = os.listdir(config.dossier_sauvegardes)
    except OSError:
        return []
    return sorted(nom for nom in noms if MOTIF_NOM_MANUELLE.fullmatch(nom)
                  and os.path.isdir(os.path.join(config.dossier_sauvegardes, nom)))


def instant_du_nom(nom):
    """« AAAA-MM-JJ_HHMMSS… » (heure locale) → secondes ; None si le début du nom n'est pas une date et une heure."""
    try:
        return datetime.datetime.strptime(nom[:17], '%Y-%m-%d_%H%M%S').timestamp()
    except (ValueError, OverflowError, OSError):
        return None


def verifier_plafond_manuelles(config):
    """Une sauvegarde manuelle par minute au plus (D133) : 429 avec Retry-After quand la dernière date de moins de
    60 s. La minute se lit sur le nom horodaté de la dernière sauvegarde manuelle, ce qui tient après un redémarrage ;
    un nom « dans le futur » (horloge reculée, passage à l'heure d'hiver) ne bloque pas. À appeler en tenant
    VERROU_ECRITURE, avant de créer la sauvegarde."""
    manuelles = sauvegardes_manuelles(config)
    instant = instant_du_nom(manuelles[-1]) if manuelles else None
    if instant is None:
        return
    ecoule = maintenant_s(config) - instant
    if 0 <= ecoule < DELAI_ENTRE_MANUELLES_S:
        secondes = max(1, int(-(-(DELAI_ENTRE_MANUELLES_S - ecoule) // 1)))
        erreur = ErreurHttp(429, traduisible('sauvegardes.plafond_manuelles',
                                             {'one': 'Une sauvegarde manuelle par minute au plus : réessayez dans '
                                                     '{n} s.',
                                              'other': 'Une sauvegarde manuelle par minute au plus : réessayez dans '
                                                       '{n} s.'}, n=secondes),
                            attente_secondes=secondes)
        erreur.entetes = {'Retry-After': str(secondes)}
        raise erreur


def est_un_lien(chemin):
    """Lien symbolique ou jonction Windows : jamais compté ni supprimé par une purge."""
    jonction = getattr(os.path, 'isjunction', None)         # Python 3.12 et suivants
    return os.path.islink(chemin) or bool(jonction and jonction(chemin))


def purger_sauvegardes_manuelles(config):
    """Au-delà de 60 sauvegardes manuelles, supprime les plus anciennes (D133) ; les quotidiennes et les copies de
    sécurité « …_avant-… » ne sont ni comptées ni touchées. Rend les noms supprimés. À appeler en tenant
    VERROU_ECRITURE, après chaque sauvegarde manuelle."""
    manuelles = [nom for nom in sauvegardes_manuelles(config)
                 if not est_un_lien(os.path.join(config.dossier_sauvegardes, nom))]
    anciennes = manuelles[:max(0, len(manuelles) - MANUELLES_GARDEES)]
    for nom in anciennes:
        shutil.rmtree(os.path.join(config.dossier_sauvegardes, nom), ignore_errors=True)
    return anciennes


def lister_sauvegardes(config):
    """[{"nom", "tables"}], la plus récente d'abord."""
    noms = [nom for nom in os.listdir(config.dossier_sauvegardes)
            if MOTIF_NOM_SAUVEGARDE.fullmatch(nom)
            and sauvegarde_complete(os.path.join(config.dossier_sauvegardes, nom))]
    noms.sort(reverse=True)
    return [{'nom': nom, 'tables': tables_presentes(os.path.join(config.dossier_sauvegardes, nom))}
            for nom in noms]


def tables_a_restaurer(dossier_sauvegarde, tables_demandees):
    """Tables à restaurer : toutes celles de la sauvegarde, ou celles demandées (contrôlées)."""
    disponibles = tables_presentes(dossier_sauvegarde)
    if tables_demandees is None:
        return disponibles
    if not isinstance(tables_demandees, list):
        raise ErreurHttp(400, traduisible('restauration.tables_liste',
                                          '« tables » doit être une liste de noms de tables.'))
    for table in tables_demandees:
        if not isinstance(table, str) or table not in TABLES:
            raise ErreurHttp(400, traduisible('csv.table_inconnue', 'Table inconnue : {table}.', table=table))
        if table not in disponibles:
            raise ErreurHttp(400, traduisible('restauration.table_absente',
                                              'La table {table} est absente de cette sauvegarde.', table=table))
    return [table for table in TABLES if table in tables_demandees]


def restaurer(config, nom_sauvegarde, tables_demandees):
    """Copie de sécurité de l'état actuel, puis copie des tables depuis la sauvegarde. T200 : la restauration est le
    remède à un fichier abîmé, elle le remplace (ecrire_fichier_de_donnees, remplacer_abime). T206 : puis
    fichiers-abimes.json à jour (une table restaurée saine en est retirée)."""
    verifier_ecriture_permise(config)                   # T185 : lecture seule (données plus récentes), 409
    verifier_nom_sauvegarde(nom_sauvegarde)
    dossier_sauvegarde = chemin_sous(config.dossier_sauvegardes, nom_sauvegarde)
    if not sauvegarde_complete(dossier_sauvegarde):
        raise ErreurHttp(404, traduisible('sauvegardes.introuvable',
                                          'Sauvegarde introuvable ou incomplète : {nom}.', nom=nom_sauvegarde))
    tables = tables_a_restaurer(dossier_sauvegarde, tables_demandees)
    copie_securite = nouveau_nom_horodate(config, '_avant-restauration')
    copier_tables_dans_sauvegarde(config, copie_securite)
    restaurees = []
    for table in tables:
        octets = lire_octets(os.path.join(dossier_sauvegarde, table + '.csv'))
        try:
            ecrire_fichier_de_donnees(config, table, octets, remplacer_abime=True, sauvegarde_du_jour=False)
        except ErreurHttp as erreur:
            # Restauration partielle : on le dit clairement, avec la copie de sécurité à utiliser.
            if restaurees:
                message = traduisible('restauration.interrompue',
                                      '{erreur} Restauration interrompue à la table {table} ; tables déjà '
                                      'restaurées : {tables}. L\'état d\'avant la restauration est dans la '
                                      'sauvegarde {copie}.',
                                      erreur=erreur.message, table=table, tables=', '.join(restaurees),
                                      copie=copie_securite)
            else:
                message = traduisible('restauration.interrompue_aucune',
                                      '{erreur} Restauration interrompue à la table {table} ; tables déjà '
                                      'restaurées : aucune. L\'état d\'avant la restauration est dans la '
                                      'sauvegarde {copie}.',
                                      erreur=erreur.message, table=table, copie=copie_securite)
            raise ErreurHttp(erreur.statut, message, restaurees=restaurees, copie_securite=copie_securite)
        restaurees.append(table)
    noter_fichiers_abimes(config)
    return {'restaurees': restaurees, 'copie_securite': copie_securite}


# --- « Tester une sauvegarde » (D133) : relire chaque CSV, compter les lignes, ne rien écrire ----------------------

MOTIF_PREMIERE_LIGNE_NON_VIDE = re.compile(r'^[^\r\n]*\S[^\r\n]*', re.MULTILINE)


def lire_csv_tolerant(octets):
    """Lecture tolérante d'un CSV, comme Donnees.analyser (§3.3) : BOM retiré, UTF-8 sinon Windows-1252, « ; » (ou
    « , » si l'en-tête n'a aucun « ; »), lignes entièrement vides ignorées. Rend (en-tête, lignes de données) ;
    csv.Error si le fichier ne se découpe pas."""
    if octets.startswith(BOM_UTF8):
        octets = octets[len(BOM_UTF8):]
    try:
        texte = octets.decode('utf-8')
    except UnicodeDecodeError:
        texte = octets.decode('cp1252', errors='replace')
    trouvee = MOTIF_PREMIERE_LIGNE_NON_VIDE.search(texte)
    entete = trouvee.group(0) if trouvee else ''
    separateur = ',' if ';' not in entete and ',' in entete else ';'
    lignes = [ligne for ligne in csv.reader(io.StringIO(texte, newline=''), delimiter=separateur)
              if any(cellule.strip() for cellule in ligne)]
    return (lignes[0], lignes[1:]) if lignes else ([], [])


def cle_entete(nom):
    """Nom de colonne → clé de comparaison : casse, accents, espaces et « _ » ignorés (cleEntete de js/donnees.js)."""
    return re.sub(r'[\s_]+', '', sans_accents(nom).lower())


def tester_table_de_sauvegarde(table, chemin):
    """{"table", "lignes", "erreur"} d'un CSV de sauvegarde : lignes de données comptées (None si illisible) ; erreur
    (None si tout va bien) quand le fichier est illisible ou vide, ou qu'une colonne du schéma manque à l'en-tête,
    hors celles d'un format plus récent que la sauvegarde (COLONNES_DES_FORMATS_SUIVANTS)."""
    resultat = {'table': table, 'lignes': None, 'erreur': None}
    try:
        with open(chemin, 'rb') as fichier:
            entete, lignes = lire_csv_tolerant(fichier.read())
    except OSError as erreur:
        resultat['erreur'] = traduisible('sauvegardes.test_illisible', 'Fichier illisible ({erreur}).',
                                         erreur=erreur.strerror or erreur.__class__.__name__)
        return resultat
    except csv.Error as erreur:
        resultat['erreur'] = traduisible('sauvegardes.test_illisible', 'Fichier illisible ({erreur}).',
                                         erreur=erreur)
        return resultat
    if not entete:
        resultat['erreur'] = traduisible('sauvegardes.test_vide', 'Fichier vide : la ligne d\'en-tête manque.')
        return resultat
    resultat['lignes'] = len(lignes)
    presentes = {cle_entete(nom) for nom in entete}
    manquantes = [colonne for colonne in COLONNES_PAR_TABLE[table] if cle_entete(colonne) not in presentes]
    if not set(manquantes) <= set(COLONNES_DES_FORMATS_SUIVANTS.get(table, ())):
        resultat['erreur'] = traduisible('sauvegardes.test_colonnes_absentes',
                                         {'one': 'Colonne du schéma absente de l\'en-tête : {colonnes}.',
                                          'other': 'Colonnes du schéma absentes de l\'en-tête : {colonnes}.'},
                                         n=len(manquantes), colonnes=', '.join(manquantes))
    return resultat


def tester_sauvegarde(config, nom):
    """POST /api/sauvegarde/tester : {"nom", "ok", "tables": [{"table", "lignes", "erreur"}]} pour chaque CSV de la
    sauvegarde, dans l'ordre du schéma ; ok si elle contient au moins une table et qu'aucune n'a d'erreur. N'écrit
    rien. 400 nom refusé, 404 sauvegarde introuvable ou incomplète."""
    verifier_nom_sauvegarde(nom)
    dossier = chemin_sous(config.dossier_sauvegardes, nom)
    if not sauvegarde_complete(dossier):
        raise ErreurHttp(404, traduisible('sauvegardes.introuvable',
                                          'Sauvegarde introuvable ou incomplète : {nom}.', nom=nom))
    tables = [tester_table_de_sauvegarde(table, os.path.join(dossier, table + '.csv'))
              for table in tables_presentes(dossier)]
    return {'nom': nom, 'ok': bool(tables) and all(table['erreur'] is None for table in tables), 'tables': tables}


# --- Copie externe (D133) : la sauvegarde du jour copiée vers une clé USB, un NAS, un dossier synchronisé ---------

class ErreurCopieExterne(Exception):
    """Copie externe impossible. Le message, en français, ne cite que le nom du dossier : /api/info le montre aux
    autres postes, jamais le chemin complet du disque."""


def dossier_copie_externe(config):
    """Chemin absolu du dossier de copie (clé « copie_sauvegardes » ; relatif : au dossier de Prévo), '' sans copie."""
    reglage = (config.reglages.get('copie_sauvegardes') or '').strip()
    if not reglage:
        return ''
    return os.path.abspath(os.path.join(DOSSIER_APPLICATION, os.path.expanduser(reglage)))


def nom_du_dossier(chemin):
    """Dernier morceau d'un chemin : « Sauvegardes » pour …\\Sauvegardes, « E: » pour la racine E:\\."""
    morceaux = [morceau for morceau in re.split(r'[\\/]+', chemin) if morceau]
    return morceaux[-1] if morceaux else chemin


def chemin_etat_copie_externe(config):
    return os.path.join(config.dossier_donnees, NOM_ETAT_COPIE_EXTERNE)


def lire_etat_copie_externe(config):
    """donnees/copie-externe.json : {"derniere_reussie", "sauvegarde_copiee", "erreur"} ; {} s'il manque ou est
    illisible (ce n'est qu'un rappel pour l'accueil du responsable, gardé d'un démarrage à l'autre)."""
    try:
        with open(chemin_etat_copie_externe(config), 'rb') as fichier:
            etat = json.loads(fichier.read().decode('utf-8'))
    except (OSError, UnicodeDecodeError, ValueError, RecursionError):
        return {}
    return etat if isinstance(etat, dict) else {}


def ecrire_etat_copie_externe(config, etat):
    try:
        ecrire_atomique(chemin_etat_copie_externe(config),          # D157 : l'erreur garde son code et ses valeurs
                        (json.dumps(avec_codes(etat), ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    except (OSError, ErreurHttp) as erreur:
        afficher('Copie externe des sauvegardes : état non enregistré (%s).' % getattr(erreur, 'message', erreur))


def noter_au_journal_serveur(config, texte):
    """Console, et donnees/journal-serveur.log même quand le serveur a une console : un échec de la copie externe doit
    pouvoir se relire après coup (D133)."""
    afficher(texte)
    if JOURNAL_SERVEUR is None:
        JournalServeur(os.path.join(config.dossier_donnees, 'journal-serveur.log')).ecrire(texte)


def est_une_date(nom):
    """Vrai pour un texte « AAAA-MM-JJ » qui est une vraie date."""
    if not isinstance(nom, str) or not MOTIF_NOM_QUOTIDIENNE.fullmatch(nom):
        return False
    try:
        datetime.datetime.strptime(nom, '%Y-%m-%d')
    except ValueError:
        return False
    return True


def derniere_sauvegarde_quotidienne(config):
    """Nom (AAAA-MM-JJ) de la sauvegarde quotidienne complète la plus récente, ou None."""
    try:
        noms = os.listdir(config.dossier_sauvegardes)
    except OSError:
        return None
    completes = [nom for nom in noms if MOTIF_NOM_QUOTIDIENNE.fullmatch(nom)
                 and sauvegarde_complete(os.path.join(config.dossier_sauvegardes, nom))]
    return max(completes) if completes else None


def ignorer_dans_la_copie(dossier, noms):
    """Pour shutil.copytree : jamais sessions.json (§22.3), ni un fichier caché (marque, fichier temporaire)."""
    return [nom for nom in noms if nom in FICHIERS_ACCES_NON_SAUVEGARDES or nom.startswith('.')]


def copier_vers_l_exterieur(config, cible):
    """Copie la sauvegarde quotidienne la plus récente (acces/ compris, sans sessions.json) vers cible/AAAA-MM-JJ/, par
    un dossier temporaire renommé à la fin ; rien si cette copie existe déjà. Rend le nom de la sauvegarde présente
    dans la copie, ou None s'il n'y a encore aucune sauvegarde quotidienne. ErreurCopieExterne sinon."""
    nom_cible = nom_du_dossier(cible)
    if est_sous_dossier(os.path.realpath(cible), config.dossier_donnees):
        raise ErreurCopieExterne(traduisible('copie.dossier_dans_donnees_nom',
                                             'Le dossier de copie « {nom} » est dans le dossier des données de '
                                             'Prévo : choisissez une clé USB, un NAS ou un dossier synchronisé.',
                                             nom=nom_cible))
    if not os.path.isdir(cible):
        raise ErreurCopieExterne(traduisible('copie.dossier_introuvable',
                                             'Dossier de copie « {nom} » introuvable (clé USB absente ou partage '
                                             'réseau injoignable ?).', nom=nom_cible))
    nom = derniere_sauvegarde_quotidienne(config)
    if nom is None or os.path.isdir(os.path.join(cible, nom)):
        return nom
    temporaire = None
    try:
        temporaire = tempfile.mkdtemp(prefix=PREFIXE_COPIE_EN_COURS, dir=cible)
        shutil.copytree(os.path.join(config.dossier_sauvegardes, nom), temporaire, ignore=ignorer_dans_la_copie,
                        dirs_exist_ok=True)
        os.rename(temporaire, os.path.join(cible, nom))
    except shutil.Error as erreur:
        raise ErreurCopieExterne(traduisible('copie.incomplete',
                                             {'one': 'Copie vers « {nom} » incomplète : {n} fichier(s) non '
                                                     'copié(s) (disque plein ou fichier verrouillé ?).',
                                              'other': 'Copie vers « {nom} » incomplète : {n} fichier(s) non '
                                                       'copié(s) (disque plein ou fichier verrouillé ?).'},
                                             nom=nom_cible, n=len(erreur.args[0]) if erreur.args else 0))
    except OSError as erreur:
        raise ErreurCopieExterne(traduisible('copie.impossible',
                                             'Copie vers « {nom} » impossible : {erreur}.',
                                             nom=nom_cible, erreur=erreur.strerror or erreur.__class__.__name__))
    finally:
        if temporaire and os.path.isdir(temporaire):
            shutil.rmtree(temporaire, ignore_errors=True)
    return nom


def purger_copies_externes(cible):
    """Garde les 30 copies les plus récentes. Seuls les dossiers dont le nom est une date AAAA-MM-JJ sont comptés et
    supprimés : jamais un autre fichier ou dossier du dossier choisi par l'utilisateur. Rend les noms supprimés."""
    copies = sorted(nom for nom in os.listdir(cible) if est_une_date(nom)
                    and os.path.isdir(os.path.join(cible, nom)) and not est_un_lien(os.path.join(cible, nom)))
    anciennes = copies[:max(0, len(copies) - COPIES_EXTERNES_GARDEES)]
    for nom in anciennes:
        shutil.rmtree(os.path.join(cible, nom))
    return anciennes


def faire_copie_externe(config):
    """Une copie externe, dans le fil appelant. Rend l'état écrit dans donnees/copie-externe.json, ou None si aucun
    dossier n'est réglé ou qu'une copie est déjà en cours (jamais deux à la fois). Un échec est noté dans l'état, sur
    la console et dans journal-serveur.log, jamais levé ; une copie réussie efface l'erreur."""
    cible = dossier_copie_externe(config)
    if not cible or not VERROU_COPIE_EXTERNE.acquire(blocking=False):
        return None
    try:
        etat = lire_etat_copie_externe(config)
        for suffixe in SUFFIXES_DU_CODE:                                # code de l'erreur précédente (D157)
            etat.pop('erreur' + suffixe, None)
        try:
            nom = copier_vers_l_exterieur(config, cible)
        except ErreurCopieExterne as erreur:
            etat['erreur'] = traduisible_de(erreur)
            noter_au_journal_serveur(config, 'Copie externe des sauvegardes impossible vers %r : %s' % (cible, erreur))
        else:
            etat['erreur'] = None
            if nom is not None:
                etat['derniere_reussie'] = instant_local(config).strftime('%Y-%m-%d')
                etat['sauvegarde_copiee'] = nom
                afficher('Copie externe des sauvegardes : sauvegarde du %s à jour dans %r.' % (nom, cible))
                try:
                    purger_copies_externes(cible)
                except OSError as erreur:
                    noter_au_journal_serveur(config, 'Copie externe des sauvegardes : ancienne copie non supprimée '
                                                     'dans %r (%s).' % (cible, erreur.strerror or erreur))
        ecrire_etat_copie_externe(config, etat)
        return etat
    finally:
        VERROU_COPIE_EXTERNE.release()


def lancer_copie_externe(config):
    """Lance faire_copie_externe dans un fil à part : une clé USB lente ou un partage réseau ne retient ni le démarrage
    ni l'écriture. None si aucun dossier n'est réglé ou qu'une copie est en cours. Le fil est gardé dans
    config.fil_copie_externe (les tests l'attendent)."""
    if not dossier_copie_externe(config) or VERROU_COPIE_EXTERNE.locked():
        return None
    fil = threading.Thread(target=faire_copie_externe, args=(config,), name='copie-externe', daemon=True)
    config.fil_copie_externe = fil
    fil.start()
    return fil


def lancer_copie_externe_si_due(config):
    """Après la sauvegarde du jour, à chaque écriture CSV : la première écriture après 2 h du matin lance la copie
    externe du jour (une fois par jour ; à l'écriture suivante si une copie était déjà en cours)."""
    if not dossier_copie_externe(config):
        return None
    instant = instant_local(config)
    jour = instant.strftime('%Y-%m-%d')
    if instant.hour < HEURE_COPIE_EXTERNE or config.copie_externe_jour == jour:
        return None
    fil = lancer_copie_externe(config)
    if fil is not None:
        config.copie_externe_jour = jour
    return fil


def etat_copie_externe_public(config):
    """« copie_externe » de GET /api/info : None sans dossier réglé ; sinon {"derniere_reussie": "AAAA-MM-JJ" | None,
    "jours_sans_copie": N | None, "erreur": "…" | None}. jours_sans_copie compte les jours depuis la dernière copie
    réussie quand la dernière tentative a échoué ou qu'une sauvegarde quotidienne plus récente attend sa copie ; 0
    quand la copie est à jour (ou en cours) ; None sans aucune copie réussie. Jamais un chemin complet du disque."""
    if not dossier_copie_externe(config):
        return None
    etat = lire_etat_copie_externe(config)
    derniere = etat.get('derniere_reussie') if est_une_date(etat.get('derniere_reussie')) else None
    erreur = traduisible_relu(etat.get('erreur'), etat.get('erreur_code'), etat.get('erreur_valeurs')) \
        if isinstance(etat.get('erreur'), str) else None
    jours = None
    if derniere is not None:
        copiee = etat.get('sauvegarde_copiee') if isinstance(etat.get('sauvegarde_copiee'), str) else ''
        en_attente = (derniere_sauvegarde_quotidienne(config) or '') > copiee and not VERROU_COPIE_EXTERNE.locked()
        jours = 0
        if erreur or en_attente:
            depuis = datetime.datetime.strptime(derniere, '%Y-%m-%d').date()
            jours = max(0, (instant_local(config).date() - depuis).days)
    return {'derniere_reussie': derniere, 'jours_sans_copie': jours, 'erreur': erreur}


# ---------------------------------------------------------------------------
# Passage au format courant au démarrage du serveur, lecture seule (T185 ; décisions D168 et D169)
# ---------------------------------------------------------------------------

# En mode serveur, c'est le serveur qui passe les fichiers de données au format courant (D168), une fois, à son
# démarrage : avant d'ouvrir ses écouteurs (main), donc avant toute connexion, que la configuration existe ou non
# (assistant d'installation). Mêmes règles que Donnees.etatDuFormat et Donnees.migrerAuFormatCourant (js/donnees.js,
# §4.11), appliquées aux fichiers :
#   1. point de départ = le plus petit format entre version_schema (version_de_base) et celui de chaque fichier
#      présent et lisible (format_du_fichier) ; fichiers vides, fichiers laissés (ci-dessous) et tables absentes
#      ignorés ; base vide (aucun CSV) ou déjà au format courant : rien ;
#   2. la sauvegarde « AAAA-MM-JJ_HHMMSS_avant-format-vN » (N = format courant, motif de MOTIFS_SAUVEGARDE) d'abord ;
#      impossible : rien n'est écrit, nouvel essai au prochain démarrage ;
#   3. chaque table présente que les étapes (migrer_tables) complètent est réécrite d'un coup (ecrire_atomique) :
#      ses colonnes dans leur ordre, ses cellules telles quelles, les colonnes du format en fin d'en-tête avec la
#      valeur par défaut du champ ; une table absente n'est pas créée ; une table à l'en-tête illisible (format 0), ou
#      d'un format plus ancien qu'une réécriture ferait perdre en partie (structure abîmée, valeurs au-delà de
#      l'en-tête, noms de colonnes en double), n'est jamais réécrite : laissée telle quelle et signalée ;
#   4. puis version_schema (parametres.csv, créé s'il manque) ; 5. puis une ligne de journal par étape (journal.csv),
#      mêmes textes que le navigateur. Un fichier tenu par un autre programme (Excel, 423) arrête le passage : ce qui
#      est écrit l'est en entier, version_schema n'avance pas, le démarrage suivant reprend (étapes idempotentes).
# Données d'un format plus récent (version_schema > format courant, D169) : rien n'est écrit, et jusqu'au prochain
# démarrage toute écriture de données est refusée (409, code « format_plus_recent ») ; les lectures et la sauvegarde
# manuelle restent permises. L'état est gardé dans config.format_donnees et rendu par GET /api/info (« format »).

MIGRATIONS_DU_FORMAT = ('faite', 'rien', 'impossible', 'incomplete')
CODE_FORMAT_PLUS_RECENT = 'format_plus_recent'
# Routes qui écrivent dans les données, refusées en lecture seule (traiter_api). Les étapes de l'assistant qui écrivent
# une table (« compte » en Solo, « terminer » en Solo ou avec la démo) le vérifient elles-mêmes, avant toute écriture.
ROUTES_ECRITURE_DES_DONNEES = (('PUT', 'csv/<table>'), ('POST', 'csv/<table>/ajout'), ('PUT', 'documents/<nom>'),
                               ('POST', 'restauration'))
PREFIXE_CONSOLE_FORMAT = 'Format des données : '
POSTE_DU_SERVEUR = 'Serveur Prévo'          # colonne « poste » des lignes de journal écrites par le serveur
CARACTERES_ID_JOURNAL = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'     # CARACTERES_ALEATOIRES de js/donnees.js
OCTETS_HORS_CP1252 = frozenset((0x81, 0x8D, 0x8F, 0x90, 0x9D))      # sans caractère en cp1252 (WHATWG : même code)
RAISONS_DE_LAISSER = {
    'entete': 'en-tête illisible : des colonnes du format 1 y manquent',
    'illisible': 'fichier illisible',
}
# Pertes d'une réécriture (lire_fichier_de_donnees) que le navigateur compte aussi (entree.abime) : celles de la garde
# « fichier abîmé » (raisons_fichier_abime, T200).
PERTE_STRUCTURE = traduisible('abime.perte_structure',
                              'structure du fichier abîmée (guillemet non fermé, ou texte collé à un guillemet)')
PERTE_AU_DELA_DE_L_ENTETE = traduisible('abime.perte_au_dela_entete', 'valeurs au-delà de l\'en-tête')


def texte_du_format(format):
    """Format pour un message : « 4 », ou « 4.5 » s'il n'est pas entier."""
    return str(int(format)) if float(format).is_integer() else str(format)


def verifier_ecriture_permise(config):
    """Lecture seule (D169) : 409 {"erreur", "code": "format_plus_recent", "format"} quand le serveur a trouvé à son
    démarrage des données d'un format plus récent que le sien ; rien sinon (ni avant le démarrage, ni hors de main)."""
    etat = getattr(config, 'format_donnees', None)
    if etat and etat.get('plus_recent'):
        raise ErreurHttp(409, traduisible('format.plus_recent',
                                          'Lecture seule : ces données viennent d\'une version plus récente de Prévo '
                                          '(format {format} des fichiers ; ce serveur lit jusqu\'au format '
                                          '{courant}). Rien n\'est enregistré : mettez Prévo à jour sur le PC '
                                          'serveur, puis relancez-le.',
                                          format=texte_du_format(etat['base']), courant=VERSION_SCHEMA_CSV),
                         code=CODE_FORMAT_PLUS_RECENT, format=etat['base'])


def decoder_windows_1252(octets):
    """Octets → texte, comme TextDecoder('windows-1252') du navigateur : les cinq octets sans caractère en cp1252
    donnent le caractère de même code (rien n'est perdu à la réécriture en UTF-8)."""
    try:
        return octets.decode('cp1252')
    except UnicodeDecodeError:
        return ''.join(chr(octet) if octet in OCTETS_HORS_CP1252 else bytes((octet,)).decode('cp1252')
                       for octet in octets)


def lire_fichier_de_donnees(octets):
    """Lecture d'un CSV de données pour le passage au format courant, comme Donnees.csv.analyser (§3.3) : BOM retiré,
    UTF-8 sinon Windows-1252, « ; » (« , » si la première ligne non vide n'a aucun « ; » et a une virgule), lignes
    entièrement blanches ignorées, cellules telles quelles (apostrophe de protection comprise). Rend {"vide",
    "entete", "lignes", "pertes", "utf8", "separateur", "octets"} : vide si le fichier n'a aucun enregistrement (0
    octet, ou seulement des blancs) ; entete : les noms de la ligne d'en-tête tels qu'écrits ; lignes : listes de
    cellules ; pertes : ce qu'une réécriture ferait perdre (structure abîmée — guillemet non fermé, texte collé à un
    guillemet fermant, comme les erreurs de PapaParse —, valeurs au-delà de l'en-tête, noms de colonnes en double),
    [] sinon."""
    lu = {'vide': True, 'entete': [], 'lignes': [], 'pertes': [], 'utf8': True, 'separateur': ';', 'octets': octets}
    if octets.startswith(BOM_UTF8):
        octets = octets[len(BOM_UTF8):]
    try:
        texte = octets.decode('utf-8')
    except UnicodeDecodeError:
        texte, lu['utf8'] = decoder_windows_1252(octets), False
    if sans_blancs_js_aux_bords(texte) == '':
        return lu
    trouvee = MOTIF_PREMIERE_LIGNE_NON_VIDE.search(texte)
    premiere = trouvee.group(0) if trouvee else ''
    lu['separateur'] = ',' if ';' not in premiere and ',' in premiere else ';'

    def decouper(strict):
        lecteur = csv.reader(io.StringIO(texte, newline=''), delimiter=lu['separateur'], strict=strict)
        return [ligne for ligne in lecteur if any(sans_blancs_js_aux_bords(cellule) for cellule in ligne)]

    try:
        enregistrements = decouper(True)
    except csv.Error:
        lu['pertes'].append(PERTE_STRUCTURE)
        try:
            enregistrements = decouper(False)
        except csv.Error:
            enregistrements = []
    lu['vide'] = not enregistrements and not lu['pertes']
    if not enregistrements:
        return lu
    entete = enregistrements[0]
    lu['entete'], lu['lignes'] = entete, enregistrements[1:]
    if any(sans_blancs_js_aux_bords(cellule) for ligne in lu['lignes'] for cellule in ligne[len(entete):]):
        lu['pertes'].append(PERTE_AU_DELA_DE_L_ENTETE)
    cles = [cle_de_colonne(nom) for nom in entete]
    doubles = sorted({nom for nom, cle in zip(entete, cles) if cle and cles.count(cle) > 1})
    if doubles:
        lu['pertes'].append('colonnes en double (%s)' % ', '.join(doubles))
    return lu


def raison_de_laisser(lu):
    """Pourquoi le passage au format courant ne réécrit jamais ce fichier (raisonDeLaisser de js/donnees.js), ou
    None : « entete » (en-tête illisible, format 0) ; « contenu » (format plus ancien que le courant et une réécriture
    ferait perdre une partie du fichier : lu['pertes'])."""
    if lu['format'] == 0:
        return 'entete'
    return 'contenu' if lu['pertes'] and lu['format'] < VERSION_SCHEMA_CSV else None


def lignes_en_dictionnaires(lu):
    """Lignes d'un fichier lu en {colonne: cellule} (première colonne d'un nom en double), pour version_de_base."""
    lignes = []
    for cellules in lu['lignes']:
        ligne = {}
        for position, nom in enumerate(lu['entete']):
            ligne.setdefault(nom, cellules[position] if position < len(cellules) else '')
        lignes.append(ligne)
    return lignes


def etat_des_fichiers(config):
    """État du format des fichiers de données, sans rien écrire (Donnees.etatDuFormat) : {"base", "depart",
    "plus_recent", "lus", "laissees", "vides"} ; lus : {table: lecture (lire_fichier_de_donnees, plus « format »)} des
    tables du schéma présentes, dans l'ordre du schéma ; laissees : [(table, raison)] des fichiers que le passage ne
    réécrit jamais (raison_de_laisser, ou « illisible » si la lecture échoue) ; vides : fichiers sans enregistrement,
    lus comme des tables vides. Les fichiers laissés et vides ne comptent pas pour le point de départ."""
    lus, laissees, vides = {}, [], []
    for table in TABLES:
        try:
            octets = lire_octets(chemin_table(config, table))
        except OSError:
            laissees.append((table, 'illisible'))
            continue
        if octets is None:
            continue
        lu = lire_fichier_de_donnees(octets)
        lu['format'] = 0 if lu['vide'] else format_du_fichier(table, lu['entete'])
        lus[table] = lu
    parametres = lus.get('parametres')
    base = (version_de_base(lignes_en_dictionnaires(parametres)) if parametres is not None
            else VERSION_SCHEMA_PAR_DEFAUT)
    depart = base
    for table, lu in lus.items():
        if lu['vide']:
            vides.append(table)
            continue
        raison = raison_de_laisser(lu)
        if raison:
            laissees.append((table, raison))
            continue
        depart = min(depart, lu['format'])
    ordre = {table: position for position, table in enumerate(TABLES)}
    laissees.sort(key=lambda laissee: ordre[laissee[0]])
    return {'base': base, 'depart': depart, 'plus_recent': base > VERSION_SCHEMA_CSV, 'lus': lus, 'laissees': laissees,
            'vides': vides}


def etapes_du_passage(depart, entetes):
    """Étapes du passage depuis « depart » sur les en-têtes donnés ({table: en-tête}, ordre du schéma), comme
    etapesDuPassage de js/donnees.js : [{"vers", "passage", "tables"}], où passage est la ligne de journal de l'étape
    et tables les tables données que l'étape complète."""
    base = {table: {'entete': list(entete), 'lignes': []} for table, entete in entetes.items()}
    etapes = []
    for etape in ETAPES_FORMAT:
        if etape.vers <= depart or etape.vers > VERSION_SCHEMA_CSV:
            continue
        suivante, journal, _ = migrer_tables(base, etape.de, etape.vers)
        etapes.append({'vers': etape.vers, 'passage': journal[0],
                       'tables': [table for table in entetes
                                  if len(suivante[table]['entete']) != len(base[table]['entete'])]})
        base = suivante
    return etapes


def cellules_alignees(cellules, largeur):
    """Les cellules d'une ligne sur « largeur » colonnes : complétées par des cellules vides, ou coupées (seules des
    cellules blanches dépassent l'en-tête d'un fichier réécrit : lire_fichier_de_donnees)."""
    return (list(cellules) + [''] * largeur)[:largeur]


def table_au_format_courant(table, lu):
    """(en-tête, lignes) d'une table lisible passée de son format au format courant (ecrireAuFormatCourant) : les
    colonnes que les étapes ajoutent (migrer_tables) en fin d'en-tête, avec la valeur par défaut du champ dans chaque
    ligne ; les colonnes et les cellules du fichier telles quelles, dans leur ordre."""
    entete = list(lu['entete'])
    sonde = migrer_tables({table: {'entete': list(entete), 'lignes': [{}]}}, lu['format'], VERSION_SCHEMA_CSV)[0][table]
    ajoutees = sonde['entete'][len(entete):]
    defauts = [sonde['lignes'][0].get(colonne, '') for colonne in ajoutees]
    return entete + ajoutees, [cellules_alignees(cellules, len(entete)) + defauts for cellules in lu['lignes']]


def parametres_au_format_courant(lu):
    """(en-tête, lignes) de parametres.csv avec version_schema au format courant, écrit comme Prévo l'écrit (« '3 »,
    poser_version_de_base) : dans la première ligne qui porte la clé, sinon dans une ligne ajoutée en fin ; fichier
    absent ou vide : l'en-tête du format courant. Les autres lignes et colonnes telles quelles."""
    if lu is None or lu['vide']:
        entete, lignes = colonnes_du_format('parametres'), []
    else:
        entete = list(lu['entete'])
        lignes = [cellules_alignees(cellules, len(entete)) for cellules in lu['lignes']]
    position_cle = entete.index(colonne_de_champ(entete, 'cle'))
    position_valeur = entete.index(colonne_de_champ(entete, 'valeur'))
    cellule = ecrire_valeur_texte(str(VERSION_SCHEMA_CSV))
    for ligne in lignes:
        if sans_blancs_js_aux_bords(ligne[position_cle]) == CLE_VERSION_SCHEMA:
            ligne[position_valeur] = cellule
            break
    else:
        nouvelle = [''] * len(entete)
        nouvelle[position_cle], nouvelle[position_valeur] = CLE_VERSION_SCHEMA, cellule
        lignes.append(nouvelle)
    return entete, lignes


def lignes_de_journal_du_format(config, actions):
    """Lignes de journal ({colonne: cellule}) des actions du passage, comme entreeJournal : identifiant
    « J-AAAAMMJJHHMMSS-XXXX » (distincts dans le lot), date et heure du serveur, poste « Serveur Prévo », table
    parametres, ligne version_schema."""
    instant = instant_local(config)
    pris, lignes = set(), []
    for action in actions:
        identifiant = None
        while identifiant is None or identifiant in pris:
            identifiant = 'J-%s-%s' % (instant.strftime('%Y%m%d%H%M%S'),
                                       ''.join(secrets.choice(CARACTERES_ID_JOURNAL) for _ in range(4)))
        pris.add(identifiant)
        lignes.append({'id': identifiant, 'date_heure': instant.strftime('%Y-%m-%d %H:%M'),
                       'poste': ecrire_valeur_texte(POSTE_DU_SERVEUR), 'profil': '', 'table': 'parametres',
                       'id_ligne': CLE_VERSION_SCHEMA, 'action': ecrire_valeur_texte(action)})
    return lignes


def ecrire_journal_du_format(config, lu, lignes):
    """Ajoute les lignes à journal.csv ; rend vrai si c'est fait. Fichier absent ou vide : créé avec l'en-tête du
    format courant. En UTF-8 et en « ; » : lignes ajoutées en fin (le reste du fichier à l'octet près), dans l'ordre de
    ses colonnes (celles du fichier inconnues du schéma laissées vides) ; en Windows-1252 ou en « , » : le fichier
    réécrit en entier, cellules telles quelles. Fichier laissé (format 0) ou qu'une réécriture abîmerait : rien
    (faux). ErreurHttp 423 ou OSError si l'écriture échoue, 409 « fichier_abime » si la garde la refuse (T200,
    ecrire_fichier_de_donnees : l'ajout en fin de fichier passe par elle comme un ajout)."""
    colonnes = colonnes_du_format('journal')
    if lu is None or lu['vide']:
        neuf = ecrire_tableau_csv(colonnes, [[ligne[colonne] for colonne in colonnes] for ligne in lignes])
        ecrire_fichier_de_donnees(config, 'journal', neuf, sauvegarde_du_jour=False)
        return True
    if lu['pertes'] or lu['format'] == 0:
        return False
    entete = lu['entete']
    champs = {cle_de_colonne(colonne): colonne for colonne in colonnes}
    nouvelles = [[ligne.get(champs.get(cle_de_colonne(nom)), '') for nom in entete] for ligne in lignes]
    if lu['utf8'] and lu['separateur'] == ';':
        ajout = ''.join(';'.join(cellule_csv(cellule) for cellule in ligne) + '\r\n' for ligne in nouvelles)
        octets = lu['octets']
        ecrire_fichier_de_donnees(config, 'journal', octets + (b'' if octets.endswith(b'\n') else FIN_DE_LIGNE)
                                  + ajout.encode('utf-8'), ajout=True, sauvegarde_du_jour=False)
    else:
        anciennes = [cellules_alignees(cellules, len(entete)) for cellules in lu['lignes']]
        ecrire_fichier_de_donnees(config, 'journal', ecrire_tableau_csv(entete, anciennes + nouvelles),
                                  sauvegarde_du_jour=False)
    return True


def noms_de_fichiers(tables):
    """« a.csv, b.csv » pour un message de la console."""
    return ', '.join(table + '.csv' for table in tables)


def signaler_fichiers_laisses(etat):
    """Console : fichiers laissés tels quels (jamais réécrits) et fichiers vides, à chaque démarrage."""
    lus = etat['lus']
    for table, raison in etat['laissees']:
        detail = ('fichier abîmé : %s' % ', '.join(lus[table]['pertes']) if raison == 'contenu'
                  else RAISONS_DE_LAISSER[raison])
        afficher(PREFIXE_CONSOLE_FORMAT + '%s laissé tel quel, jamais réécrit (%s). Corrigez le fichier, ou '
                 'restaurez une sauvegarde.' % (table + '.csv', detail))
    if etat['vides']:
        afficher(PREFIXE_CONSOLE_FORMAT + 'sans aucune ligne, lu comme une table vide : %s.'
                 % noms_de_fichiers(etat['vides']))


def migrer_donnees_au_demarrage(config):
    """Passage des fichiers de données au format courant au démarrage du serveur (T185, D168 ; règles en tête de cette
    partie), et garde des données plus récentes (D169). Appelée par main avant l'ouverture des écouteurs ; idempotente
    (un second démarrage n'écrit rien et ne refait pas de sauvegarde). Rend l'état public et le garde dans
    config.format_donnees (GET /api/info, « format ») : {"base", "courant", "plus_recent", "migration": "faite" | "rien"
    | "impossible" | "incomplete", "tables_abimees", "tables_vides", "table_bloquee"} ; base : version_schema après ce
    démarrage ; table_bloquee : la table qui a arrêté un passage incomplet. Aucune donnée des fichiers."""
    etat = etat_des_fichiers(config)
    public = {'base': etat['base'], 'courant': VERSION_SCHEMA_CSV, 'plus_recent': etat['plus_recent'],
              'migration': 'rien', 'tables_abimees': [table for table, _ in etat['laissees']],
              'tables_vides': list(etat['vides']), 'table_bloquee': None}
    config.format_donnees = public
    if not etat['lus'] and not etat['laissees']:
        return public                                   # base vide : aucun CSV
    signaler_fichiers_laisses(etat)
    if etat['plus_recent']:
        afficher(PREFIXE_CONSOLE_FORMAT + 'format %s, plus récent que celui de cette version de Prévo (%d) : données '
                 'en LECTURE SEULE, rien n\'est enregistré. Mettez Prévo à jour sur ce PC, puis relancez-le.'
                 % (texte_du_format(etat['base']), VERSION_SCHEMA_CSV))
        return public
    if etat['depart'] >= VERSION_SCHEMA_CSV:
        return public
    suivi = {'sauvegarde': None, 'ecrites': []}
    try:
        passer_les_fichiers_au_format_courant(config, etat, public, suivi)
    except Exception:                       # bogue : tracé ; le serveur démarre quand même, rien de plus n'est écrit
        traceback.print_exc()
        if public['migration'] != 'faite':
            public['migration'] = 'incomplete' if suivi['sauvegarde'] else 'impossible'
        afficher(PREFIXE_CONSOLE_FORMAT + 'passage au format %d arrêté par une erreur interne (%s) ; nouvel essai au '
                 'prochain démarrage.' % (VERSION_SCHEMA_CSV, 'sauvegarde %s faite juste avant' % suivi['sauvegarde']
                                          if suivi['sauvegarde'] else 'rien n\'a été écrit'))
    return public


def passer_les_fichiers_au_format_courant(config, etat, public, suivi):
    """Étapes 2 à 5 du passage (en tête de cette partie) ; suivi : {"sauvegarde", "ecrites"} tenu à jour."""
    courant = VERSION_SCHEMA_CSV
    lus = etat['lus']
    version_a_ecrire = etat['base'] < courant
    parametres = lus.get('parametres')
    laissees = {table for table, _ in etat['laissees']}
    if version_a_ecrire and ('parametres' in laissees or (parametres is not None and parametres['pertes'])):
        # version_schema ne s'écrirait pas sans perte (en-tête illisible, fichier abîmé ou illisible) : rien n'est fait
        # (sinon une sauvegarde à chaque démarrage, et jamais de version_schema).
        if 'parametres' not in public['tables_abimees']:
            public['tables_abimees'].append('parametres')
        public['migration'] = 'impossible'
        afficher(PREFIXE_CONSOLE_FORMAT + 'passage au format %d impossible : parametres.csv ne se réécrit pas sans '
                 'perte (%s) ; rien n\'a été écrit. Corrigez parametres.csv, ou restaurez une sauvegarde, puis '
                 'relancez Prévo.' %(courant, ', '.join(parametres['pertes']) if parametres and parametres['pertes']
                             else RAISONS_DE_LAISSER[dict(etat['laissees'])['parametres']]))
        return

    # 2. La sauvegarde d'abord : sans elle, on ne touche à rien.
    motif = 'avant-format-v%d' % courant
    try:
        with VERROU_ECRITURE:
            nom = nouveau_nom_horodate(config, '_' + motif)
            verifier_nom_sauvegarde(nom)
            copier_tables_dans_sauvegarde(config, nom)
    except (ErreurHttp, OSError) as erreur:
        public['migration'] = 'impossible'
        afficher(PREFIXE_CONSOLE_FORMAT + 'passage au format %d impossible : la sauvegarde « %s » n\'a pas pu être '
                 'faite (%s). Rien n\'a été écrit ; nouvel essai au prochain démarrage.'
                 % (courant, motif, getattr(erreur, 'message', None) or erreur))
        return
    suivi['sauvegarde'] = nom

    # 3. Les tables que les étapes complètent, dans l'ordre du schéma (parametres à part).
    lisibles =[table for table in lus if not lus[table]['vide'] and table not in laissees]
    etapes = etapes_du_passage(etat['depart'], {table: lus[table]['entete'] for table in lisibles})
    a_ecrire = [table for table in lisibles
                if table != 'parametres' and any(table in etape['tables'] for etape in etapes)]
    for table in a_ecrire + (['parametres'] if version_a_ecrire else []):
        if table == 'parametres':
            entete, lignes = parametres_au_format_courant(parametres)         # 4. version_schema
        else:
            entete, lignes = table_au_format_courant(table, lus[table])
        try:
            with VERROU_ECRITURE:
                ecrire_fichier_de_donnees(config, table, ecrire_tableau_csv(entete, lignes), sauvegarde_du_jour=False)
        except (ErreurHttp, OSError) as erreur:             # 423 (Excel), et 409 « fichier_abime » (T200) : arrêt propre
            public['migration'], public['table_bloquee'] = 'incomplete', table
            afficher(PREFIXE_CONSOLE_FORMAT + 'passage au format %d interrompu : %s.csv ne peut pas être écrit (%s). '
                     'Fermez Excel (ou le programme qui a ouvert ce fichier) et relancez Prévo : le passage reprendra '
                     'là (sauvegarde %s faite juste avant ; déjà complétés : %s).'
                     % (courant, table, getattr(erreur, 'message', None) or erreur, nom,
                        noms_de_fichiers(suivi['ecrites']) or 'aucun'))
            return
        if table != 'parametres':
            suivi['ecrites'].append(table)
    if version_a_ecrire:
        public['base'] = courant
    public['migration'] = 'faite'

    # 5. Le journal : une ligne par étape, mêmes textes que migrerAuFormatCourant.
    suite = 'sauvegarde %s faite juste avant' % nom
    actions = []
    for etape in etapes:
        if version_a_ecrire and etape['vers'] > etat['base']:
            actions.append(etape['passage'] + ' ; ' + suite)
            continue
        completees = [table for table in etape['tables'] if table in suivi['ecrites']]
        if completees:
            actions.append('fichiers complétés au format %d : %s ; %s' % (etape['vers'], ', '.join(completees), suite))
    if version_a_ecrire:
        afficher(PREFIXE_CONSOLE_FORMAT + 'passage au format %d fait (sauvegarde %s faite juste avant) ; fichiers '
                 'complétés : %s.' % (courant, nom, noms_de_fichiers(suivi['ecrites']) or 'aucun'))
    else:
        afficher(PREFIXE_CONSOLE_FORMAT + 'fichiers complétés au format %d : %s (sauvegarde %s faite juste avant).'
                 % (courant, noms_de_fichiers(suivi['ecrites']), nom))
    if not actions:
        return
    ecrit, detail = False, 'journal.csv laissé tel quel'
    if 'journal' not in laissees:               # illisible : jamais remplacé par un journal neuf
        try:
            with VERROU_ECRITURE:
                ecrit = ecrire_journal_du_format(config, lus.get('journal'),
                                                 lignes_de_journal_du_format(config, actions))
        except (ErreurHttp, OSError) as erreur:
            detail = getattr(erreur, 'message', None) or erreur
    if not ecrit:
        afficher(PREFIXE_CONSOLE_FORMAT + 'lignes du journal du passage non écrites (%s).' % detail)


# ---------------------------------------------------------------------------
# Sauvegardes du démarrage (T187 ; décision D170 ; docs/FORMAT.md §8)
# ---------------------------------------------------------------------------

# Au démarrage du serveur, dans main, avant d'ouvrir les écouteurs (donc avant toute connexion), dans cet ordre :
#   1. « avant-mise-a-jour » : base non vide (au moins un CSV du schéma) et donnees/derniere-version.json absent,
#      illisible ou portant une autre version que VERSION_APPLICATION → sauvegarde
#      « AAAA-MM-JJ_HHMMSS_avant-mise-a-jour » (manifeste : « de » = version notée ou « inconnue », « vers » = version
#      courante), puis, après sa réussite seulement, derniere-version.json écrit d'un coup ({"version", "depuis"}) ;
#      échec : une ligne sur la console et rien d'autre (nouvel essai au démarrage suivant) ; base vide : rien ;
#   2. le passage au format courant (migrer_donnees_au_demarrage, T185), avec sa sauvegarde « avant-format-vN » ;
#   3. la sauvegarde quotidienne si celle du jour manque (faire_sauvegarde_du_jour, rotation à 30 jours comprise) ;
#   4. T206 : fichiers-abimes.json à jour (noter_fichiers_abimes ; fait par la sauvegarde de l'étape 3 si elle a lieu).
# Aucune de ces étapes n'écrit dans les tables : elles se font aussi en lecture seule (données plus récentes, D169 ;
# fichiers-abimes.json excepté, laissé tel quel en lecture seule).
PREFIXE_CONSOLE_SAUVEGARDES = 'Sauvegardes : '


def chemin_derniere_version(config):
    return os.path.join(config.dossier_donnees, NOM_DERNIERE_VERSION)


def lire_derniere_version(config):
    """Version de Prévo notée dans donnees/derniere-version.json (texte non vide), ou None : fichier absent, illisible,
    ou sans « version »."""
    try:
        with open(chemin_derniere_version(config), 'rb') as fichier:
            contenu = json.loads(fichier.read().decode('utf-8-sig'))
    except (OSError, UnicodeDecodeError, ValueError, RecursionError):
        return None
    version = contenu.get('version') if isinstance(contenu, dict) else None
    return version.strip() if isinstance(version, str) and version.strip() else None


def sauvegarder_avant_mise_a_jour(config):
    """Étape 1 ci-dessus. Rend le nom de la sauvegarde faite, ou None (rien à faire, ou échec dit sur la console)."""
    if not tables_presentes(config.dossier_donnees):
        return None                                     # base vide : rien à garder
    notee = lire_derniere_version(config)
    if notee == VERSION_APPLICATION:
        return None
    de = notee                                          # None (JSON null) si inconnue, comme le mode dossier
    try:
        with VERROU_ECRITURE:
            nom = nouveau_nom_horodate(config, '_' + MOTIF_AVANT_MISE_A_JOUR)
            verifier_nom_sauvegarde(nom)
            copier_tables_dans_sauvegarde(config, nom, {'de': de, 'vers': VERSION_APPLICATION})
    except (ErreurHttp, OSError) as erreur:
        afficher(PREFIXE_CONSOLE_SAUVEGARDES + 'sauvegarde « %s » impossible (%s) ; nouvel essai au prochain démarrage.'
                 % (MOTIF_AVANT_MISE_A_JOUR, getattr(erreur, 'message', None) or erreur))
        return None
    afficher(PREFIXE_CONSOLE_SAUVEGARDES + 'version de Prévo précédente : %s, version actuelle : %s ; sauvegarde %s '
             'faite avant la mise à jour.' % (de or VERSION_INCONNUE, VERSION_APPLICATION, nom))
    contenu = {'version': VERSION_APPLICATION, 'depuis': maintenant_iso(config)}
    try:
        ecrire_atomique(chemin_derniere_version(config),
                        (json.dumps(contenu, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    except (ErreurHttp, OSError) as erreur:
        afficher(PREFIXE_CONSOLE_SAUVEGARDES + '%s non écrit (%s) : une autre sauvegarde « %s » sera faite au prochain '
                 'démarrage.' % (NOM_DERNIERE_VERSION, getattr(erreur, 'message', None) or erreur,
                                 MOTIF_AVANT_MISE_A_JOUR))
    return nom


def sauvegarder_le_jour_au_demarrage(config):
    """Étape 3 ci-dessus : la sauvegarde quotidienne si celle du jour manque (rotation comprise). Échec dit sur la
    console (la première écriture du jour la retente). Rend son nom, ou None."""
    try:
        with VERROU_ECRITURE:
            return faire_sauvegarde_du_jour(config)
    except (ErreurHttp, OSError) as erreur:
        afficher(PREFIXE_CONSOLE_SAUVEGARDES + 'sauvegarde du jour impossible au démarrage (%s) ; elle sera refaite '
                 'avant la première modification.' % (getattr(erreur, 'message', None) or erreur))
        return None


def preparer_donnees_au_demarrage(config):
    """Étapes 1 à 4 ci-dessus, dans cet ordre (main, avant les écouteurs). Rend l'état du format des données
    (migrer_donnees_au_demarrage)."""
    sauvegarder_avant_mise_a_jour(config)
    etat = migrer_donnees_au_demarrage(config)
    if sauvegarder_le_jour_au_demarrage(config) is None:
        noter_fichiers_abimes(config)
    return etat


# ---------------------------------------------------------------------------
# Opérations sur les CSV
# ---------------------------------------------------------------------------

def versions_des_tables(config):
    """{"table": {"version", "modifie"} ou None} pour les 24 tables."""
    resultat = {}
    for table in TABLES:
        chemin = chemin_table(config, table)
        octets = lire_octets(chemin)
        if octets is None:
            resultat[table] = None
        else:
            resultat[table] = {'version': empreinte(octets), 'modifie': date_modification(chemin)}
    return resultat


# Cellule qu'Excel exécuterait à l'ouverture d'un CSV (audit E2) : =, +, @, tabulation, retour chariot, ou un tiret qui
# n'introduit pas un nombre. Prévo protège ces valeurs par une apostrophe à l'écriture (§3.2) ; le serveur refuse ce
# qu'un autre client enverrait sans elle. Un texte qui commence par une espace n'est pas une formule pour Excel.
MOTIF_CELLULE_DANGEREUSE = re.compile(r'^(?:[=+@\t\r]|-(?![0-9.,]))')


def verifier_contenu_csv(table, octets, corps_d_ajout=False, entete_libre=False):
    """UTF-8, en-tête qui commence par les colonnes du schéma, aucune cellule dangereuse sans apostrophe ; 400 sinon.
    entete_libre (T213) : l'en-tête n'est pas comparé au schéma (CSV abîmé importé tel quel, enregistrer_csv)."""
    if not est_utf8(octets):
        raise ErreurHttp(400, traduisible('csv.encodage',
                                          'Le fichier {table}.csv doit être encodé en UTF-8.', table=table))
    texte = octets.decode('utf-8')
    if texte.startswith('﻿'):
        texte = texte[1:]
    try:
        lignes = list(csv.reader(io.StringIO(texte, newline=''), delimiter=';'))
    except csv.Error as erreur:
        raise ErreurHttp(400, traduisible('csv.illisible',
                                          'Le fichier {table}.csv est illisible ({erreur}).',
                                          table=table, erreur=erreur))
    if not lignes:
        raise ErreurHttp(400, traduisible('csv.vide',
                                          'Le fichier {table}.csv est vide : la ligne d\'en-tête manque.',
                                          table=table))
    attendues = list(COLONNES_PAR_TABLE.get(table, ()))
    recues = [nom.strip() for nom in lignes[0]]
    if not entete_libre and recues[:len(attendues)] != attendues:
        raise ErreurHttp(400, traduisible('csv.entete_inattendu',
                                          'En-tête de {table}.csv inattendu : il doit commencer par {colonnes}.',
                                          table=table, colonnes=';'.join(attendues)))
    for numero, ligne in enumerate(lignes[1:], 2):
        for cellule in ligne:
            if MOTIF_CELLULE_DANGEREUSE.match(cellule):
                raise ErreurHttp(400, traduisible('csv.formule',
                                                  'Ligne {numero} de {table}.csv : une cellule commence par un '
                                                  'caractère de formule (« {caractere} ») ; Prévo la protège par '
                                                  'une apostrophe.',
                                                  numero=numero, table=table, caractere=cellule[:1]))


# ---------------------------------------------------------------------------
# Écriture des CSV de données : la fonction commune et sa garde « fichier abîmé » (T200 ; suite de T197)
# ---------------------------------------------------------------------------

# Toutes les écritures de donnees/<table>.csv du serveur passent par ecrire_fichier_de_donnees (PUT et ajout de l'API,
# assistant et Solo, jeu de démo, passage au format, restauration ; tests/test_garde_abime_serveur.py le vérifie sur le
# code : aucun autre ecrire_atomique d'un chemin venu de chemin_table). Avant d'écrire, elle regarde le fichier en place
# (verifier_fichier_en_place), comme Donnees.enregistrerLignes du navigateur (ErreurFichierAbime) :
#   - réécriture : refusée si le fichier en place est abîmé (raisons_fichier_abime : la réécrire en perdrait une
#     partie sans le dire) ;
#   - ajout en fin de fichier : refusé s'il se termine au milieu d'un texte entre guillemets (les lignes ajoutées y
#     seraient avalées, donc perdues) ; un fichier abîmé ailleurs reçoit l'ajout (rien de ce qui est en place ne change).
# Dérogations à la réécriture : la restauration d'une sauvegarde (le remède) et un PUT /api/csv/<table> qui porte
# l'en-tête X-Prevo-Remplacer-Abime: 1 (l'import ZIP du navigateur). L'en-tête n'ajoute aucun droit : les règles des
# rôles (§22.5 : routes permises, controle_d_ecriture) et le contrôle de version restent les mêmes. Refus : 409
# {"erreur", "code": "fichier_abime", "table"}, la table reste identique à l'octet. T206 (règle de Nicolas : « un
# fichier abîmé bloque l'écriture dans les données, jamais la sauvegarde quotidienne ») : la sauvegarde du jour passe
# AVANT la garde, une écriture refusée la fait donc si elle manque (son manifeste marque le fichier abîmé).
CODE_FICHIER_ABIME = 'fichier_abime'
ENTETE_REMPLACER_ABIME = 'X-Prevo-Remplacer-Abime'
ENTETE_ABIME_DEPUIS = 'X-Prevo-Abime-Depuis'   # T213 : CSV abîmé importé tel quel (avec la dérogation) et sa date
MOTIF_PREMIERE_LIGNE_NON_VIDE_OCTETS = re.compile(rb'[^\r\n]*\S[^\r\n]*')
A_LIRE = object()           # ecrire_fichier_de_donnees : le fichier en place est lu par la fonction elle-même


def separateur_des_octets(octets):
    """« ; », ou « , » si la première ligne non vide n'a aucun « ; » et a une virgule (choisirSeparateur de
    js/donnees.js), sur les octets bruts : lignes coupées en CR ou LF, « non vide » = un octet autre qu'un blanc."""
    trouvee = MOTIF_PREMIERE_LIGNE_NON_VIDE_OCTETS.search(octets)
    premiere = trouvee.group(0) if trouvee else b''
    return b',' if b';' not in premiere and b',' in premiere else b';'


def finit_dans_un_guillemet_ouvert(octets):
    """Vrai si le CSV se termine au milieu d'un texte entre guillemets (cellule « "… » jamais fermée) : à la relecture,
    une ligne ajoutée à la suite serait avalée dans cette cellule. Sur les octets bruts, sans décodage (BOM UTF-8 de
    tête ignoré ; séparateur : separateur_des_octets), par l'automate que le navigateur applique aussi :
      - début de champ : « " » → entre guillemets ; séparateur, CR ou LF → début de champ ; autre → dans le champ ;
      - dans le champ : séparateur, CR ou LF → début de champ ; tout autre octet (« " » compris) → dans le champ ;
      - entre guillemets : « " » → guillemet vu ; tout autre octet (CR et LF compris) → entre guillemets ;
      - guillemet vu : « " » → entre guillemets (guillemet doublé) ; séparateur, CR ou LF → début de champ ; autre →
        dans le champ.
    Vrai si et seulement si l'état final est « entre guillemets » ; aucun blanc n'est sauté. « Guillemet vu » se
    comporte comme « début de champ » : la lecture va donc d'un guillemet au suivant (bytes.find : un journal de
    plusieurs Mo se lit vite), l'état devant un guillemet se déduisant de l'octet qui le précède."""
    if octets.startswith(BOM_UTF8):
        octets = octets[len(BOM_UTF8):]
    fins_de_champ = (separateur_des_octets(octets)[0], 0x0D, 0x0A)
    position, dans_le_champ = 0, False      # état à « position » : début de champ (ou guillemet vu), ou dans le champ
    while True:
        guillemet = octets.find(b'"', position)
        if guillemet < 0:
            return False                    # plus de guillemet : l'état final n'est pas « entre guillemets »
        if guillemet > position:
            dans_le_champ = octets[guillemet - 1] not in fins_de_champ
        if dans_le_champ:
            position = guillemet + 1        # guillemet ordinaire d'un champ non guillemeté : on reste dans le champ
            continue
        fermant = octets.find(b'"', guillemet + 1)          # entre guillemets jusqu'au guillemet suivant
        if fermant < 0:
            return True
        position, dans_le_champ = fermant + 1, False        # guillemet vu


def raisons_fichier_abime(octets):
    """Ce qu'une réécriture du fichier ferait perdre, même critère que entree.abime du navigateur (csv.analyser de
    js/donnees.js) : structure abîmée (guillemet non fermé, texte collé à un guillemet fermant) et valeurs au-delà de
    l'en-tête, lues par lire_fichier_de_donnees ; [] si rien (fichier sain, vide ou absent). Les colonnes en double
    n'y sont pas : le navigateur garde la seconde colonne d'un même nom (associerColonnes : colonne inconnue
    « nom (2) », réécrite en fin de fichier), rien ne s'en perd."""
    if octets is None:
        return []
    return [perte for perte in lire_fichier_de_donnees(octets)['pertes']
            if perte in (PERTE_STRUCTURE, PERTE_AU_DELA_DE_L_ENTETE)]


def fichier_sans_contenu(octets):
    """Vrai pour un fichier absent (None), de 0 octet, ou qui n'a que des blancs (après un BOM de tête)."""
    if octets is None:
        return True
    return not (octets[len(BOM_UTF8):] if octets.startswith(BOM_UTF8) else octets).strip()


def verifier_fichier_en_place(table, actuel, ajout=False, remplacer_abime=False):
    """Garde « fichier abîmé » (en tête de cette partie) sur « actuel », les octets du fichier en place (None s'il est
    absent) ; rien si le fichier est sans contenu (fichier_sans_contenu). Ajout : 409 s'il se termine au milieu d'un
    texte entre guillemets (finit_dans_un_guillemet_ouvert). Réécriture : 409 s'il est abîmé (raisons_fichier_abime),
    sauf remplacer_abime. 409 {"erreur", "code": "fichier_abime", "table"}."""
    if fichier_sans_contenu(actuel):
        return
    if ajout:
        if finit_dans_un_guillemet_ouvert(actuel):
            raise ErreurHttp(409, traduisible('abime.guillemet_ouvert',
                                              'Le fichier {table}.csv se termine au milieu d\'un texte entre '
                                              'guillemets (guillemet jamais fermé) : Prévo n\'y ajoute plus rien, '
                                              'pour ne rien perdre (les lignes ajoutées seraient avalées dans ce '
                                              'texte). Corrigez-le, restaurez une sauvegarde ou importez un ZIP '
                                              '(Paramètres) ; le détail est dans Paramètres › Contrôle de la base.',
                                              table=table), code=CODE_FICHIER_ABIME, table=table)
        return
    raisons = [] if remplacer_abime else raisons_fichier_abime(actuel)
    if raisons:
        raise ErreurHttp(409, traduisible('abime.fichier',
                                          'Le fichier {table}.csv est abîmé ({raisons}) : Prévo ne l\'enregistre '
                                          'plus, pour ne rien perdre. Corrigez-le, restaurez une sauvegarde ou '
                                          'importez un ZIP (Paramètres) ; le détail est dans Paramètres › Contrôle '
                                          'de la base.', table=table, raisons=raisons),
                         code=CODE_FICHIER_ABIME, table=table)


def ecrire_fichier_de_donnees(config, table, octets, actuel=A_LIRE, *, ajout=False, remplacer_abime=False,
                              sauvegarde_du_jour):
    """LA fonction d'écriture des CSV de données (donnees/<table>.csv ; en tête de cette partie), dans cet ordre :
      1. la sauvegarde du jour si « sauvegarde_du_jour » (faire_sauvegarde_quotidienne), AVANT la garde (T206) : un
         fichier abîmé bloque l'écriture dans les données, jamais la sauvegarde quotidienne ;
      2. la garde (verifier_fichier_en_place) sur le fichier en place : « actuel », ses octets (None s'il est absent),
         lus ici s'ils ne sont pas donnés ; ajout : « octets » est le fichier en place suivi des lignes ajoutées ;
         remplacer_abime : la réécriture d'un fichier abîmé est voulue (restauration, import ZIP) ;
      3. ecrire_atomique (423 si le fichier est verrouillé, Excel).
    Refus de la garde : 409 « fichier_abime », la table reste identique à l'octet (la sauvegarde du jour, elle, est
    faite si elle manquait ; son manifeste marque le fichier abîmé). Rend l'empreinte des octets écrits. À appeler en
    tenant VERROU_ECRITURE (ou au démarrage, avant les écouteurs)."""
    chemin = chemin_table(config, table)
    if sauvegarde_du_jour:
        faire_sauvegarde_quotidienne(config)
    if ajout or not remplacer_abime:
        verifier_fichier_en_place(table, lire_octets(chemin) if actuel is A_LIRE else actuel, ajout, remplacer_abime)
    ecrire_atomique(chemin, octets)
    return empreinte(octets)


def enregistrer_csv(config, table, octets, version_attendue, controle=None, remplacer_abime=False,
                    abime_depuis=None):
    """Remplace le CSV si sa version actuelle est celle attendue ; sinon 409 (conflit). Contenu vérifié d'abord (E2).
    controle (lot 7, §22.5) : (octets reçus, octets actuels) → octets à écrire, appelé après le contrôle de version
    (colonnes cachées remises pour le technicien, demandes en ajout seulement pour le demandeur ; 403 sinon). Puis
    ecrire_fichier_de_donnees (T200) : 409 « fichier_abime » si le fichier en place est abîmé, sauf remplacer_abime
    (PUT avec l'en-tête X-Prevo-Remplacer-Abime: 1, l'import ZIP). T213 : abime_depuis (en-tête X-Prevo-Abime-Depuis,
    avec remplacer_abime) : l'import écrit tel quel un CSV que son ZIP marque abîmé ; son en-tête n'est alors pas
    comparé au schéma si le serveur le voit abîmé lui aussi (raisons_fichier_abime ; UTF-8 et cellules dangereuses
    toujours contrôlés). Après une écriture avec remplacer_abime, fichiers-abimes.json suit la table
    (noter_table_importee)."""
    verifier_ecriture_permise(config)                   # T185 : lecture seule (données plus récentes), 409
    abimee = bool(remplacer_abime and raisons_fichier_abime(octets))
    verifier_contenu_csv(table, octets, entete_libre=abimee and abime_depuis is not None)
    chemin = chemin_table(config, table)
    actuel = lire_octets(chemin)
    version_actuelle = empreinte(actuel) if actuel is not None else None
    attendue = None if version_attendue == 'aucune' else version_attendue
    if attendue != version_actuelle:
        if version_actuelle is None:
            message = traduisible('csv.n_existe_plus', 'Le fichier {table}.csv n\'existe plus.', table=table)
        elif attendue is None:
            message = traduisible('csv.existe_deja', 'Le fichier {table}.csv existe déjà.', table=table)
        else:
            message = traduisible('csv.modifie_ailleurs', 'Le fichier {table}.csv a été modifié par un autre poste.',
                                  table=table)
        raise ErreurHttp(409, message, version_actuelle=version_actuelle)
    if controle is not None:
        octets = controle(octets, actuel)
    version = ecrire_fichier_de_donnees(config, table, octets, actuel, remplacer_abime=remplacer_abime,
                                        sauvegarde_du_jour=True)
    if remplacer_abime:
        noter_table_importee(config, table, abimee, abime_depuis)
    return version


def decouper_corps_ajout(corps):
    """Corps d'un ajout = ligne d'en-tête + lignes de données (UTF-8 sans BOM)."""
    if not est_utf8(corps):
        raise ErreurHttp(400, traduisible('csv.corps_encodage', 'Le corps doit être encodé en UTF-8.'))
    if corps.startswith(BOM_UTF8):
        corps = corps[len(BOM_UTF8):]
    entete, lignes = premiere_ligne(corps)
    if not entete:
        raise ErreurHttp(400, traduisible('csv.corps_sans_entete',
                                          'Le corps doit commencer par la ligne d\'en-tête.'))
    return corps, entete, lignes


def ajouter_au_csv(config, table, corps, controle=None):
    """Ajoute des lignes en fin de fichier (journal) ; 409 si en-tête ou encodage différent.
    controle (lot 7, §22.5) : (en-tête, lignes, octets actuels) → lignes à ajouter (colonnes cachées vidées pour le
    technicien, demandes nouvelles seulement pour le demandeur ; 403 sinon). T200 : 409 « fichier_abime » si le
    fichier en place (non vide) se termine au milieu d'un texte entre guillemets, avant les contrôles d'UTF-8 et
    d'en-tête (verifier_fichier_en_place, puis ecrire_fichier_de_donnees en ajout). T206 : la sauvegarde du jour est
    faite juste avant cette garde, même si elle refuse."""
    verifier_ecriture_permise(config)                   # T185 : lecture seule (données plus récentes), 409
    chemin = chemin_table(config, table)
    verifier_contenu_csv(table, corps, corps_d_ajout=True)
    corps, entete, lignes = decouper_corps_ajout(corps)
    actuel = lire_octets(chemin)
    if controle is not None:
        lignes = controle(entete, lignes, actuel)
        corps = entete + FIN_DE_LIGNE + lignes
    faire_sauvegarde_quotidienne(config)                # T206 : avant la garde (faite ici, pas dans les écritures)
    verifier_fichier_en_place(table, actuel, ajout=True)
    if actuel is None or not actuel.replace(BOM_UTF8, b'', 1).strip():
        return ecrire_fichier_de_donnees(config, table, BOM_UTF8 + corps, actuel, ajout=True, sauvegarde_du_jour=False)
    if not est_utf8(actuel):
        raise ErreurHttp(409, traduisible('csv.ajout_encodage',
                                          'Le fichier {table}.csv n\'est pas en UTF-8 (réenregistré par Excel ?).',
                                          table=table), version_actuelle=empreinte(actuel))
    if premiere_ligne(actuel)[0] != entete:
        raise ErreurHttp(409, traduisible('csv.ajout_entete_different',
                                          'L\'en-tête de {table}.csv est différent.', table=table),
                         version_actuelle=empreinte(actuel))
    if not lignes:
        return empreinte(actuel)
    separateur = b'' if actuel.endswith(b'\n') else FIN_DE_LIGNE
    return ecrire_fichier_de_donnees(config, table, actuel + separateur + lignes, actuel, ajout=True,
                                     sauvegarde_du_jour=False)


# ---------------------------------------------------------------------------
# Opérations sur les documents
# ---------------------------------------------------------------------------

def chemin_document(config, nom):
    verifier_nom_document(nom)
    return chemin_sous(config.dossier_documents, nom)


def nom_de_document_impose(config, nom_demande):
    """Audit F4 : nom sous lequel le serveur enregistre un document, « AAAAMMJJ-HHMMSS-<nom demandé> » (horodatage du
    serveur, extension en minuscules). Le navigateur garde le nom rendu par la réponse 201, jamais celui qu'il a
    demandé. 400 ou 415 si le nom demandé n'est pas autorisé."""
    verifier_nom_document(nom_demande, demande=True)
    base, _, ext = nom_demande.rpartition('.')
    horodatage = maintenant_iso(config).replace('-', '').replace(':', '').replace('T', '-')
    return '%s-%s.%s' % (horodatage, base, ext.lower())


def taille_des_documents(config):
    """Octets occupés par le dossier documents/ (fichiers seulement). Parcours du dossier à chaque envoi de document :
    un compteur en mémoire se tromperait dès qu'on fait de la place à la main (le message du 413 le demande) ; un
    envoi est rare et os.scandir rend la taille sans appel système par fichier sous Windows."""
    total = 0
    try:
        with os.scandir(config.dossier_documents) as entrees:
            for entree in entrees:
                try:
                    if entree.is_file(follow_symlinks=False):
                        total += entree.stat(follow_symlinks=False).st_size
                except OSError:
                    pass
    except FileNotFoundError:
        pass
    return total


def verifier_quota_documents(config, taille_ajoutee):
    """Audit F2 : 413 si le dossier documents/ et le document envoyé dépassent quota_documents_mo (4 Go par défaut
    depuis T250). Le refus dit où se règle le quota (T250) : Paramètres › Accès et installation, sur le PC serveur
    (carte du responsable, section « Comptes des demandeurs, durées de session, documents ») ; aussi dans
    prevo.config.json. À appeler en tenant VERROU_ECRITURE, avant d'écrire."""
    quota_mo = config.reglages.get('quota_documents_mo', QUOTA_DOCUMENTS_MO_PAR_DEFAUT)
    occupe = taille_des_documents(config) + taille_ajoutee
    if occupe > quota_mo * 1024 * 1024:
        raise ErreurHttp(413, traduisible('documents.dossier_plein',
                                          'Dossier des documents plein ({occupe} Mo sur {quota} Mo avec ce '
                                          'document) : faites de la place, ou agrandissez la place des documents '
                                          'dans Paramètres › Accès et installation, sur le PC serveur.',
                                          occupe=('%.1f' % (occupe / (1024 * 1024))).replace('.', ','), quota=quota_mo))


def enregistrer_document(config, nom_demande, octets):
    """Enregistre un nouveau document sous le nom imposé par le serveur (nom_de_document_impose) et rend ce nom ;
    409 s'il existe déjà (même nom demandé dans la même seconde : jamais d'écrasement), 413 si le quota du dossier
    serait dépassé. La signature d'une image est contrôlée avant (verifier_signature_image, api_document_ecrire)."""
    verifier_ecriture_permise(config)                   # T185 : lecture seule (données plus récentes), 409
    nom = nom_de_document_impose(config, nom_demande)
    chemin = chemin_document(config, nom)
    if os.path.exists(chemin):
        raise ErreurHttp(409, traduisible('documents.existe_deja', 'Le document {nom} existe déjà.', nom=nom))
    verifier_quota_documents(config, len(octets))
    ecrire_atomique(chemin, octets)
    return nom


# ---------------------------------------------------------------------------
# Routes de l'API (lot 7, ARCHITECTURE.md §22.4) : une seule table, lue par l'aiguillage, le contrôle d'accès
# et les tests
# ---------------------------------------------------------------------------

# (méthode, motif du chemin après /api/) → fonction du gestionnaire, appelée avec (segment, corps). « <table> » (une
# des 24 tables), « <nom> » (nom de document), « <identifiant> » (identifiant d'un compte) et « <id> » (invitation ou
# appareil) valent un segment. Une
# route ajoutée ici est aussitôt fermée sans session quand les comptes sont exigés (tests/test_acces_sessions.py
# parcourt la table) ; elle doit aussi avoir sa ligne dans ROLES_PAR_ROUTE (tests/test_acces_roles.py le vérifie).
ROUTES_API = {
    ('GET', 'ping'): 'api_ping',
    ('GET', 'info'): 'api_info',
    ('GET', 'versions'): 'api_versions',
    ('GET', 'session'): 'api_session',
    ('POST', 'connexion'): 'api_connexion',
    ('POST', 'deconnexion'): 'api_deconnexion',
    ('POST', 'mot-de-passe'): 'api_mot_de_passe',
    ('POST', 'acces/deconnecter-partout'): 'api_deconnecter_partout',
    ('GET', 'acces/comptes'): 'api_comptes',
    ('POST', 'acces/comptes'): 'api_compte_creer',
    ('POST', 'acces/comptes/<identifiant>'): 'api_compte_changer',
    ('GET', 'acces/journal'): 'api_journal_acces',
    ('POST', 'enroler'): 'api_enroler',
    ('GET', 'acces/invitations'): 'api_invitations',
    ('POST', 'acces/invitations'): 'api_invitation_creer',
    ('POST', 'acces/invitations/<id>/revoquer'): 'api_invitation_revoquer',
    ('POST', 'acces/appareils/<id>/revoquer'): 'api_appareil_revoquer',
    ('POST', 'acces/appareils/revoquer-tous'): 'api_appareils_revoquer_tous',
    ('GET', 'csv/<table>'): 'api_csv_lire',
    ('PUT', 'csv/<table>'): 'api_csv_ecrire',
    ('POST', 'csv/<table>/ajout'): 'api_ajout',
    ('GET', 'documents/<nom>'): 'api_document_lire',
    ('PUT', 'documents/<nom>'): 'api_document_ecrire',
    ('POST', 'sauvegarde'): 'api_sauvegarde',
    ('POST', 'sauvegarde/tester'): 'api_sauvegarde_tester',
    ('GET', 'sauvegardes'): 'api_sauvegardes',
    ('POST', 'restauration'): 'api_restauration',
    ('POST', 'ia'): 'api_ia',
    ('GET', 'ia/reglages'): 'api_ia_reglages',
    ('GET', 'installation/<etape>'): 'api_installation_lire',           # §22.10 : PC serveur seulement (traiter)
    ('POST', 'installation/<etape>'): 'api_installation_ecrire',
}
# Ouvertes sans session : le navigateur détecte le serveur (/api/ping) et demande qui il est avant toute connexion.
ROUTES_PUBLIQUES = (('GET', 'ping'), ('GET', 'session'), ('POST', 'connexion'), ('POST', 'enroler'))
# Seules routes d'une session au mot de passe provisoire (« a_changer ») : 403 partout ailleurs.
ROUTES_MOT_DE_PASSE_PROVISOIRE = (('GET', 'session'), ('POST', 'mot-de-passe'), ('POST', 'deconnexion'))
# Motifs à essayer : les chemins fixes avant ceux qui ont un segment variable.
MOTIFS_API = sorted({motif for _, motif in ROUTES_API}, key=lambda motif: ('<' in motif, motif))


def motif_de_route(morceaux):
    """Morceaux du chemin après /api/ → motif de ROUTES_API (« csv/<table> »…), ou None : adresse inconnue."""
    for motif in MOTIFS_API:
        modele = motif.split('/')
        if len(modele) == len(morceaux) and all(attendu == morceau or (attendu.startswith('<') and morceau)
                                                for attendu, morceau in zip(modele, morceaux)):
            return motif
    return None


def segment_de_route(motif, morceaux):
    """Valeur du segment variable du chemin (« <table> », « <nom> », « <identifiant> », « <id> »), ou None."""
    for attendu, morceau in zip((motif or '').split('/'), morceaux):
        if attendu.startswith('<'):
            return morceau
    return None


# ---------------------------------------------------------------------------
# Rôles par route (lot 7, ARCHITECTURE.md §22.5 ; D126) : une seule table, appliquée par verifier_role dans
# controler_acces, après la session et avant la lecture du corps ; recopiée dans le contrat et dans
# tests/test_acces_roles.py, qui en parcourt chaque case
# ---------------------------------------------------------------------------

OUI, NON = 'oui', 'non'
# Colonnes de ROLES_PAR_ROUTE, dans cet ordre. « appareil » : téléphone enrôlé (D125, T153), droits du demandeur.
ORDRE_DES_ROLES = ('demandeur', 'appareil', 'technicien', 'responsable')
# Tables lues par le demandeur (liste fermée, D126 : aucune table de coût ni de techniciens) : celles de ses écrans
# (accueil, Signaler, demandes, parc, fiche d'équipement avec ses compteurs et relevés, wiki, Ce poste).
TABLES_DU_DEMANDEUR = ('localisations', 'equipements', 'demandes', 'compteurs', 'releves', 'codes_defaillance',
                       'parametres', 'wiki_pages')
# Écritures : le demandeur crée des demandes (PUT de demandes.csv en ajout seulement) et la ligne de journal qui va
# avec ; le technicien écrit tout sauf ces trois tables, qu'il lit (techniciens sans taux horaire).
TABLES_DU_DEMANDEUR_EN_ECRITURE = ('demandes',)
TABLES_DU_DEMANDEUR_EN_AJOUT = ('demandes', 'journal')
TABLES_DU_RESPONSABLE_EN_ECRITURE = ('parametres', 'techniciens', 'fournisseurs')
TABLES_DU_TECHNICIEN_EN_ECRITURE = tuple(table for table in TABLES if table not in TABLES_DU_RESPONSABLE_EN_ECRITURE)
# Documents du demandeur : les photos de demandes (nom donné par nomPhoto de js/modules/demandes-ecritures.js) et les
# documents des équipements (noms de la colonne « document » d'equipements.csv). Le serveur ne sait pas qui a pris
# une photo (« demandeur » est un nom libre) : le demandeur lit toutes les photos de demandes. Le nom enregistré porte
# le préfixe d'horodatage du serveur (audit F4) ; le nom demandé par l'envoi n'en a pas : préfixe facultatif.
MOTIF_PHOTO_DE_DEMANDE = re.compile(PREFIXE_NOM_DOCUMENT + r'photo-[0-9]{8}-[0-9]{6}-[A-Z0-9]{4}\.(jpg|jpeg|png|gif|webp)',
                                    re.ASCII)
PHOTOS_DE_DEMANDES = 'photos de demandes'
DOCUMENTS_DU_DEMANDEUR = 'photos de demandes et documents des équipements'
TOUS = (OUI, OUI, OUI, OUI)
RESPONSABLE = (NON, NON, NON, OUI)
INTERVENANTS = (NON, NON, OUI, OUI)     # technicien et responsable (l'IA : arbitrage de Nicolas du 2026-10-28)

# Route → règle de chaque rôle (ORDRE_DES_ROLES) : OUI, NON (403), ou ce que le rôle y peut (tables permises, règle
# des documents). Chaque route de ROUTES_API a sa ligne. Les routes publiques et celles du mot de passe provisoire
# sont contrôlées avant (controler_acces) ; « déconnecter partout » pour un autre compte : responsable seulement
# (api_deconnecter_partout).
ROLES_PAR_ROUTE = {
    # route                                 demandeur, appareil, technicien, responsable
    ('GET', 'ping'): TOUS,
    ('GET', 'session'): TOUS,
    ('POST', 'connexion'): TOUS,
    ('POST', 'deconnexion'): TOUS,
    ('POST', 'mot-de-passe'): TOUS,
    ('GET', 'info'): TOUS,
    ('GET', 'versions'): TOUS,
    ('POST', 'acces/deconnecter-partout'): TOUS,
    ('GET', 'acces/comptes'): RESPONSABLE,
    ('POST', 'acces/comptes'): RESPONSABLE,
    ('POST', 'acces/comptes/<identifiant>'): RESPONSABLE,
    ('GET', 'acces/journal'): RESPONSABLE,
    ('POST', 'enroler'): TOUS,
    ('GET', 'acces/invitations'): RESPONSABLE,
    ('POST', 'acces/invitations'): RESPONSABLE,
    ('POST', 'acces/invitations/<id>/revoquer'): RESPONSABLE,
    ('POST', 'acces/appareils/<id>/revoquer'): RESPONSABLE,
    ('POST', 'acces/appareils/revoquer-tous'): RESPONSABLE,
    ('GET', 'csv/<table>'): (TABLES_DU_DEMANDEUR, TABLES_DU_DEMANDEUR, OUI, OUI),
    ('PUT', 'csv/<table>'): (TABLES_DU_DEMANDEUR_EN_ECRITURE, TABLES_DU_DEMANDEUR_EN_ECRITURE,
                             TABLES_DU_TECHNICIEN_EN_ECRITURE, OUI),
    ('POST', 'csv/<table>/ajout'): (TABLES_DU_DEMANDEUR_EN_AJOUT, TABLES_DU_DEMANDEUR_EN_AJOUT,
                                    TABLES_DU_TECHNICIEN_EN_ECRITURE, OUI),
    ('GET', 'documents/<nom>'): (DOCUMENTS_DU_DEMANDEUR, DOCUMENTS_DU_DEMANDEUR, OUI, OUI),
    ('PUT', 'documents/<nom>'): (PHOTOS_DE_DEMANDES, PHOTOS_DE_DEMANDES, OUI, OUI),
    ('POST', 'sauvegarde'): RESPONSABLE,
    ('POST', 'sauvegarde/tester'): RESPONSABLE,
    ('GET', 'sauvegardes'): RESPONSABLE,
    ('POST', 'restauration'): RESPONSABLE,
    ('POST', 'ia'): INTERVENANTS,
    ('GET', 'ia/reglages'): INTERVENANTS,
    ('GET', 'installation/<etape>'): RESPONSABLE,
    ('POST', 'installation/<etape>'): RESPONSABLE,
}

# Ce qu'un rôle ne reçoit pas d'une table, retiré des octets renvoyés par GET /api/csv/<table> (la version X-Version
# reste celle du fichier entier). D126 : ni taux horaire ni prix pour le technicien ; à chacun de ses PUT, le serveur
# remet ces colonnes depuis le fichier actuel (remettre_colonnes_cachees) : il ne peut ni les lire ni les changer.
COLONNES_CACHEES_PAR_ROLE = {
    'technicien': {'techniciens': ('taux_horaire',), 'articles': ('prix_unitaire',), 'achats': ('prix_unitaire',)},
}
# Lignes retirées : (colonne, valeurs). D114 : ni page Technicien ni page Intervention pour le demandeur.
LIGNES_CACHEES_PAR_ROLE = {
    'demandeur': {'wiki_pages': ('type', ('technicien', 'intervention'))},
}
# Demande créée par le demandeur : statut « Nouvelle », champs de la décision du responsable vides.
STATUT_DEMANDE_NOUVELLE = 'Nouvelle'
CHAMPS_DE_DECISION = ('motif_decision', 'date_decision', 'ot_id')
MESSAGE_RESERVE_AU_RESPONSABLE = traduisible('acces.reserve_au_responsable', 'Accès refusé : réservé au responsable.')


def role_effectif(identite):
    """Rôle dont la session a les droits : celui du compte, « demandeur » pour un appareil enrôlé (D125)."""
    return 'demandeur' if identite.get('appareil') else str(identite.get('role') or '')


def regle_du_role(identite, route):
    """Règle de ROLES_PAR_ROUTE pour la colonne de cette identité (« appareil » pour un téléphone enrôlé) ; NON pour
    une route absente ou un rôle inconnu (un comptes.json abîmé n'ouvre rien)."""
    colonne = 'appareil' if identite.get('appareil') else identite.get('role')
    regles = ROLES_PAR_ROUTE.get(route)
    if regles is None or colonne not in ORDRE_DES_ROLES:
        return NON
    return regles[ORDRE_DES_ROLES.index(colonne)]


def tables_lisibles(identite):
    """Tables que la session lit (GET /api/csv/<table>) : None pour toutes (sans comptes, technicien, responsable)."""
    if identite is None:
        return None
    regle = regle_du_role(identite, ('GET', 'csv/<table>'))
    if regle == OUI:
        return None
    return set(regle) if isinstance(regle, tuple) else set()


def documents_des_equipements(config):
    """Noms de la colonne « document » d'equipements.csv (apostrophe de protection retirée, §3.2)."""
    with VERROU_ECRITURE:
        octets = lire_octets(chemin_table(config, 'equipements'))
    noms = set()
    for ligne in dictionnaires_csv(octets):
        nom = ligne.get('document', '').strip()
        noms.add(nom[1:] if nom.startswith("'") else nom)
    noms.discard('')
    return noms


def segment_permis(config, regle, segment):
    """Vrai si la règle d'un rôle (liste de tables, règle des documents) permet ce segment du chemin."""
    if segment is None:
        return False
    if isinstance(regle, tuple):
        return segment in regle
    if regle in (PHOTOS_DE_DEMANDES, DOCUMENTS_DU_DEMANDEUR) and MOTIF_PHOTO_DE_DEMANDE.fullmatch(segment):
        return True
    return regle == DOCUMENTS_DU_DEMANDEUR and segment in documents_des_equipements(config)


def message_refus(identite, route, segment):
    """Message du 403 d'un rôle refusé : il dit ce qui est réservé, à qui."""
    role = role_effectif(identite) or 'inconnu'
    methode, motif = route
    if ROLES_PAR_ROUTE.get(route) == RESPONSABLE:
        return MESSAGE_RESERVE_AU_RESPONSABLE
    if motif == 'csv/<table>' and methode == 'GET':
        return traduisible('acces.table_fermee', 'Accès refusé : la table « {table} » n\'est pas ouverte au {role}.',
                           table=segment, role=role)
    if motif.startswith('csv/') and role == 'technicien':
        return traduisible('acces.table_du_responsable',
                           'Accès refusé : la table « {table} » ne se modifie que par le responsable.', table=segment)
    if motif.startswith('csv/'):
        return traduisible('acces.demande_seulement',
                           'Accès refusé : le {role} ne peut que créer une demande (et la ligne du journal qui va '
                           'avec).', role=role)
    if motif == 'documents/<nom>' and methode == 'PUT':
        return traduisible('acces.photo_seulement', 'Accès refusé : le {role} ne joint que la photo d\'une demande.',
                           role=role)
    if motif == 'documents/<nom>':
        return traduisible('acces.document_ferme', 'Accès refusé : ce document n\'est pas ouvert au {role}.',
                           role=role)
    return traduisible('acces.role_refuse', 'Accès refusé : votre rôle ({role}) ne permet pas cette action.',
                       role=role)


def verifier_role(config, identite, route, segment):
    """Rôle de la session pour cette route (ROLES_PAR_ROUTE, §22.5 ; D126) : 403 {"erreur": …} au message clair si
    le rôle n'a pas la route, ou pas ce segment (table, document). Une adresse inconnue ou une méthode non prévue
    passe : l'aiguillage répond 404 ou 405, comme avant. Appelée par controler_acces après la session et le mot de
    passe provisoire, avant la lecture du corps (audit F2). Le contenu d'une écriture (demandes en ajout seulement,
    colonnes cachées remises) se contrôle ensuite, corps lu (controle_d_ecriture, controle_d_ajout)."""
    if route not in ROLES_PAR_ROUTE:
        return
    regle = regle_du_role(identite, route)
    if regle == OUI or (regle != NON and segment_permis(config, regle, segment)):
        return
    raise ErreurHttp(403, message_refus(identite, route, segment))


# --- CSV d'un rôle : colonnes et lignes retirées à la lecture, remises ou contrôlées à l'écriture -----------------

# Cellule mise entre guillemets, comme celluleCsv de js/donnees.js (§3.1).
MOTIF_A_GUILLEMETER = re.compile(r'[;"\r\n]|\A[ \t]|[ \t]\Z')
MOTIF_DATE_AMJ = re.compile(r'([0-9]{4})-([0-9]{1,2})-([0-9]{1,2})(?:[ t]([0-9]{1,2}):([0-9]{2})(?::[0-9]{2})?)?',
                            re.ASCII)
MOTIF_DATE_JMA = re.compile(r'([0-9]{1,2})[/.-]([0-9]{1,2})[/.-]([0-9]{4})(?:[ t]([0-9]{1,2}):([0-9]{2})(?::[0-9]{2})?)?',
                            re.ASCII)
MOTIF_DECIMAL_VIRGULE = re.compile(r'-?[0-9]+,[0-9]+', re.ASCII)


def cellule_csv(texte):
    """Cellule écrite comme celluleCsv de js/donnees.js : entre guillemets (doublés dedans) si elle contient « ; »,
    « " », CR ou LF, ou si elle commence ou finit par une espace ou une tabulation."""
    return '"' + texte.replace('"', '""') + '"' if MOTIF_A_GUILLEMETER.search(texte) else texte


def ecrire_tableau_csv(entete, lignes):
    """Octets d'un CSV au format de Prévo (§3.1) : BOM UTF-8, « ; », CRLF après chaque ligne, la dernière comprise."""
    texte = ''.join(';'.join(cellule_csv(cellule) for cellule in ligne) + '\r\n' for ligne in [entete] + list(lignes))
    return BOM_UTF8 + texte.encode('utf-8')


def lire_tableau(table, octets):
    """(en-tête, lignes) d'un CSV, lu comme Donnees.analyser (lire_csv_tolerant) ; 500 au message clair s'il ne se
    découpe pas ; ([], []) pour un fichier absent."""
    if octets is None:
        return [], []
    try:
        return lire_csv_tolerant(octets)
    except csv.Error as erreur:
        raise ErreurHttp(500, traduisible('csv.illisible',
                                          'Le fichier {table}.csv est illisible ({erreur}).',
                                          table=table, erreur=erreur))


def dictionnaires_csv(octets, table=''):
    """Lignes d'un CSV en dictionnaires {clé d'en-tête (cle_entete) : valeur} ; [] pour un fichier absent."""
    entete, lignes = lire_tableau(table, octets)
    cles = [cle_entete(nom) for nom in entete]
    return [{cle: (ligne[position] if position < len(ligne) else '') for position, cle in enumerate(cles)}
            for ligne in lignes]


def forme_comparable(valeur):
    """Valeur d'une cellule réduite à ce que Prévo en lit (§3.2, §3.3) : espaces de bord, casse, accents, apostrophe de
    protection, écriture d'une date ou d'une date-heure (secondes comprises) et virgule décimale ignorées. Sert à
    reconnaître une ligne inchangée, jamais à écrire."""
    texte = sans_accents(str(valeur or '')).strip().lower()
    if texte.startswith("'"):
        texte = texte[1:].strip()
    for motif, ordre in ((MOTIF_DATE_AMJ, (0, 1, 2)), (MOTIF_DATE_JMA, (2, 1, 0))):
        trouve = motif.fullmatch(texte)
        if trouve:
            groupes = trouve.groups()
            annee, mois, jour = (groupes[position] for position in ordre)
            texte = '%s-%02d-%02d' % (annee, int(mois), int(jour))
            return texte + (' %02d:%s' % (int(groupes[3]), groupes[4]) if groupes[3] is not None else '')
    if MOTIF_DECIMAL_VIRGULE.fullmatch(texte):
        return texte.replace(',', '.')
    return texte


def filtrer_csv_pour(identite, table, octets):
    """Octets de GET /api/csv/<table> pour cette session : sans les colonnes ni les lignes que son rôle ne reçoit pas
    (COLONNES_CACHEES_PAR_ROLE, LIGNES_CACHEES_PAR_ROLE ; en-têtes et valeurs comparés comme Prévo les lit), CSV
    réécrit au format §3.1 ; inchangés sinon (sans comptes, responsable)."""
    if identite is None:
        return octets
    role = role_effectif(identite)
    cachees = {cle_entete(colonne) for colonne in COLONNES_CACHEES_PAR_ROLE.get(role, {}).get(table, ())}
    lignes_cachees = LIGNES_CACHEES_PAR_ROLE.get(role, {}).get(table)
    if not cachees and not lignes_cachees:
        return octets
    entete, lignes = lire_tableau(table, octets)
    cles = [cle_entete(nom) for nom in entete]
    if lignes_cachees and cle_entete(lignes_cachees[0]) in cles:
        position = cles.index(cle_entete(lignes_cachees[0]))
        refusees = {forme_comparable(valeur) for valeur in lignes_cachees[1]}
        lignes = [ligne for ligne in lignes if position >= len(ligne) or forme_comparable(ligne[position]) not in refusees]
    retirees = {position for position, cle in enumerate(cles) if cle in cachees}
    if retirees:
        entete = [nom for position, nom in enumerate(entete) if position not in retirees]
        lignes = [[cellule for position, cellule in enumerate(ligne) if position not in retirees] for ligne in lignes]
    return ecrire_tableau_csv(entete, lignes)


def valeurs_actuelles_par_id(table, octets_actuels, colonnes):
    """{id : {colonne : valeur}} des colonnes données, lues dans le fichier actuel (première ligne d'un id gardée,
    comme Donnees.indexer ; espaces de fin retirés comme à la lecture tolérante)."""
    valeurs = {}
    for ligne in dictionnaires_csv(octets_actuels, table):
        identifiant = ligne.get('id', '').strip()
        if identifiant and identifiant not in valeurs:
            valeurs[identifiant] = {colonne: ligne.get(cle_entete(colonne), '').rstrip(' \t\r') for colonne in colonnes}
    return valeurs


def remettre_colonnes_cachees(table, octets_recus, octets_actuels, colonnes):
    """PUT d'une table dont le rôle ne reçoit pas toutes les colonnes (technicien : articles, achats ; §22.5, écart
    voulu au refus : la sortie d'une pièce réécrit articles pour la colonne stock). Chaque colonne cachée reprend la
    valeur du fichier actuel, ligne par ligne d'après « id » ; vide pour une ligne nouvelle. Rend les octets à écrire."""
    entete, lignes = lire_tableau(table, octets_recus)
    cles = [cle_entete(nom) for nom in entete]
    actuelles = valeurs_actuelles_par_id(table, octets_actuels, colonnes)
    position_id = cles.index('id') if 'id' in cles else None
    for colonne in colonnes:
        if cle_entete(colonne) not in cles:
            continue
        position = cles.index(cle_entete(colonne))
        for ligne in lignes:
            identifiant = ligne[position_id].strip() if position_id is not None and position_id < len(ligne) else ''
            ligne.extend([''] * (position + 1 - len(ligne)))
            ligne[position] = actuelles.get(identifiant, {}).get(colonne, '')
    return ecrire_tableau_csv(entete, lignes)


def refus_ajout_seulement(raison):
    """403 d'une écriture de demandes.csv par le demandeur ; raison : un message (traduisible) en minuscule."""
    return ErreurHttp(403, traduisible('acces.ajout_seulement',
                                       'Accès refusé : le demandeur ne peut qu\'ajouter une demande (statut '
                                       '« Nouvelle », sans décision) ; {raison}', raison=raison))


def verifier_demande_nouvelle(ligne, deja_prises):
    """Ligne nouvelle du demandeur : id présent et pas déjà pris, statut « Nouvelle », champs de décision vides ; 403
    sinon. deja_prises : ids du fichier et des nouvelles lignes déjà vues (complété ici)."""
    identifiant = ligne.get('id', '').strip()
    if not identifiant:
        raise refus_ajout_seulement(traduisible('demandes.numero_obligatoire',
                                                'une nouvelle demande doit avoir un numéro.'))
    if identifiant in deja_prises:
        raise refus_ajout_seulement(traduisible('demandes.numero_pris',
                                                'le numéro {numero} est déjà pris.', numero=identifiant))
    deja_prises.add(identifiant)
    if ligne.get('statut', '').strip() != STATUT_DEMANDE_NOUVELLE:
        raise refus_ajout_seulement(traduisible('demandes.statut_nouvelle',
                                                'une nouvelle demande a le statut « {statut} ».',
                                                statut=STATUT_DEMANDE_NOUVELLE))
    if any(ligne.get(cle_entete(champ), '').strip() for champ in CHAMPS_DE_DECISION):
        raise refus_ajout_seulement(traduisible('demandes.decision_reservee',
                                                'la décision (motif, date, ordre de travail) revient au responsable.'))


def garder_les_demandes_actuelles(octets_recus, octets_actuels):
    """PUT de demandes.csv par le demandeur (§22.5 ; Signaler écrit la demande par Donnees.modifier) : en ajout
    seulement. Chaque ligne actuelle doit s'y retrouver inchangée (même id, mêmes valeurs à la forme près,
    forme_comparable) et les seules lignes nouvelles avoir un id absent du fichier, le statut « Nouvelle » et des
    champs de décision vides ; 403 sinon. Les lignes actuelles sont réécrites telles qu'elles sont dans le fichier
    (rien d'une ligne existante ne vient du demandeur), dans l'ordre des colonnes reçues, puis les nouvelles."""
    entete, lignes = lire_tableau('demandes', octets_recus)
    cles = [cle_entete(nom) for nom in entete]
    actuelles = dictionnaires_csv(octets_actuels, 'demandes')
    # Lignes actuelles pas encore retrouvées, par id (un id en double ou vide dans le fichier, abîmé à la main, compte
    # autant de fois qu'il y est : Prévo réécrit ces lignes telles quelles).
    restantes = {}
    for ligne in actuelles:
        restantes.setdefault(ligne.get('id', '').strip(), []).append(ligne)
    prises = {identifiant for identifiant in restantes if identifiant}

    def inchangee(ancienne, recue):
        return all(forme_comparable(ancienne.get(cle, '')) == forme_comparable(recue.get(cle, ''))
                   for cle in set(ancienne) | set(recue))

    nouvelles = []
    for brute in lignes:
        recue = {cle: (brute[position] if position < len(brute) else '') for position, cle in enumerate(cles)}
        identifiant = recue.get('id', '').strip()
        candidates = restantes.get(identifiant, [])
        retrouvee = next((ancienne for ancienne in candidates if inchangee(ancienne, recue)), None)
        if retrouvee is not None:
            candidates.remove(retrouvee)
        elif identifiant in prises:
            raise refus_ajout_seulement(traduisible('demandes.non_modifiable',
                                                    'la demande {numero} existe déjà : elle ne se modifie pas ici.',
                                                    numero=identifiant))
        else:
            verifier_demande_nouvelle(recue, prises)
            nouvelles.append(brute)
    manquantes = [identifiant or traduisible('demandes.sans_numero', 'sans numéro')
                  for identifiant, reste in restantes.items() if reste]
    if manquantes:
        raise refus_ajout_seulement(traduisible('demandes.non_supprimable',
                                                'une demande ne se supprime pas ({demandes}).',
                                                demandes=sorted(manquantes)[:5]))
    gardees = [[ancienne.get(cle, '') for cle in cles] for ancienne in actuelles]
    return ecrire_tableau_csv(entete, gardees + nouvelles)


def controle_d_ecriture(identite, table):
    """Contrôle d'un PUT /api/csv/<table> propre au rôle (§22.5), appelé par enregistrer_csv après le contrôle de version
    (un 409 reste un 409) : (octets reçus, octets actuels) → octets à écrire ; None sans contrôle."""
    if identite is None:
        return None
    role = role_effectif(identite)
    colonnes = COLONNES_CACHEES_PAR_ROLE.get(role, {}).get(table)
    if colonnes:
        return lambda recus, actuels: remettre_colonnes_cachees(table, recus, actuels, colonnes)
    if role == 'demandeur' and table == 'demandes':
        return garder_les_demandes_actuelles
    return None


def controle_d_ajout(identite, table):
    """Contrôle d'un POST /api/csv/<table>/ajout propre au rôle, appelé par ajouter_au_csv : (en-tête, lignes, octets
    actuels) → lignes à ajouter. Technicien : colonnes cachées vides dans les lignes ajoutées ; demandeur, demandes :
    lignes nouvelles seulement (verifier_demande_nouvelle) ; None sans contrôle."""
    if identite is None:
        return None
    role = role_effectif(identite)
    colonnes = COLONNES_CACHEES_PAR_ROLE.get(role, {}).get(table)
    if not colonnes and not (role == 'demandeur' and table == 'demandes'):
        return None

    def controler(entete, lignes, actuels):
        cles = [cle_entete(nom) for nom in next(csv.reader(io.StringIO(entete.decode('utf-8')), delimiter=';'), [])]
        rangees = [rangee for rangee in csv.reader(io.StringIO(lignes.decode('utf-8'), newline=''), delimiter=';')
                   if any(cellule.strip() for cellule in rangee)]
        if colonnes:
            for colonne in colonnes:
                if cle_entete(colonne) in cles:
                    position = cles.index(cle_entete(colonne))
                    for rangee in rangees:
                        if position < len(rangee):
                            rangee[position] = ''
            return ''.join(';'.join(cellule_csv(cellule) for cellule in rangee) + '\r\n'
                           for rangee in rangees).encode('utf-8')
        prises = {ligne.get('id', '').strip() for ligne in dictionnaires_csv(actuels, table)}
        for rangee in rangees:
            verifier_demande_nouvelle({cle: (rangee[position] if position < len(rangee) else '')
                                       for position, cle in enumerate(cles)}, prises)
        return lignes
    return controler


# --- Comptes gérés par le responsable (GET/POST /api/acces/comptes…, §22.4) ----------------------------------------

CHAMPS_COMPTE_MODIFIABLES = ('prenom', 'nom', 'role', 'technicien_id')
ACTIONS_COMPTE = ('modifier', 'reinitialiser', 'desactiver', 'activer')


def technicien_existe(config, technicien_id):
    """Vrai si techniciens.csv a une ligne de cet identifiant (technicien lié à un compte)."""
    with VERROU_ECRITURE:
        octets = lire_octets(chemin_table(config, 'techniciens'))
    return any(ligne.get('id', '').strip() == technicien_id for ligne in dictionnaires_csv(octets, 'techniciens'))


def champs_de_compte(config, demande, obligatoires=()):
    """Champs d'un compte reçus par /api/acces/comptes (création, modification) : des textes, un rôle connu, un technicien
    lié présent dans techniciens.csv ; 400 sinon, champ inconnu compris (jamais un mot de passe, un sel ni « actif » par
    cette voie)."""
    champs = {}
    for cle, valeur in demande.items():
        if cle not in CHAMPS_COMPTE_MODIFIABLES:
            raise ErreurHttp(400, traduisible('comptes.champ_inconnu',
                                              'Champ inconnu ou non modifiable ici : « {champ} » (prenom, nom, '
                                              'role, technicien_id).', champ=str(cle)[:60]))
        if not isinstance(valeur, str):
            raise ErreurHttp(400, traduisible('comptes.texte_attendu',
                                              '« {champ} » : un texte est attendu.', champ=cle))
        champs[cle] = valeur.strip()
    for cle in obligatoires:
        if not champs.get(cle):
            raise ErreurHttp(400, traduisible('comptes.champ_obligatoire', '« {champ} » est obligatoire.', champ=cle))
    if 'role' in champs and champs['role'] not in ROLES_COMPTES:
        raise ErreurHttp(400, traduisible('comptes.role_inconnu_liste',
                                          'Rôle inconnu : « {role} » (responsable, technicien ou demandeur).',
                                          role=champs['role'][:60]))
    if champs.get('technicien_id') and not technicien_existe(config, champs['technicien_id']):
        raise ErreurHttp(400, traduisible('comptes.technicien_inconnu',
                                          'Technicien inconnu : « {technicien} » (voir Équipe).',
                                          technicien=champs['technicien_id'][:60]))
    return champs


# ---------------------------------------------------------------------------
# Gestionnaire des requêtes HTTP
# ---------------------------------------------------------------------------

class GestionnaireRequetes(http.server.BaseHTTPRequestHandler):
    """Traite une requête : contrôles de sécurité, puis API (/api/…) ou fichier statique."""

    server_version = '%s/%s' % (NOM_APPLICATION, VERSION_APPLICATION)
    sys_version = ''                    # ne pas annoncer la version de Python
    timeout = 60                        # une connexion muette est coupée au bout de 60 s
    # Connexions persistantes (HTTP/1.1) : un navigateur réutilise ses ~6 connexions au lieu d'en
    # ouvrir une par requête (~45 par chargement en HTTP/1.0). Sous Windows, ce renouvellement
    # incessant de connexions faisait échouer de temps en temps l'ouverture d'une connexion
    # (ERR_NO_BUFFER_SPACE) : l'application retombait alors sur l'écran de démarrage.
    # Toutes les réponses portent Content-Length (envoyer) ; le corps des requêtes est lu après les contrôles, ou
    # jeté (64 Ko au plus) avant un refus ; sinon la connexion est fermée après la réponse (traiter).
    protocol_version = 'HTTP/1.1'

    # --- Points d'entrée appelés par http.server ---------------------------

    def handle_one_request(self):
        """Une requête de la connexion (audit F2, §22.12). On attend son premier octet SANS place : une connexion
        keep-alive inactive ne tient rien (sinon 32 connexions ouvertes par cinq navigateurs bloquaient le sixième,
        défaut trouvé par la recette du lot 7) ; puis la place de SEMAPHORE_CONNEXIONS est tenue de la ligne de
        requête à la réponse, requête lente ou laissée à moitié comprise ; la 33e attend son tour."""
        try:
            premier = self.rfile.peek(1)
        except (OSError, ValueError):                   # délai de 60 s dépassé, connexion coupée ou fermée
            self.close_connection = True
            return
        if not premier:
            self.close_connection = True
            return
        with SEMAPHORE_CONNEXIONS:
            super().handle_one_request()

    def do_GET(self):
        self.traiter('GET')

    def do_PUT(self):
        self.traiter('PUT')

    def do_POST(self):
        self.traiter('POST')

    def setup(self):
        # https (lot 4) : la poignée de main TLS se fait ici, dans le fil de la requête, jamais dans
        # la boucle qui accepte les connexions (un client lent ne bloque pas les autres).
        if isinstance(self.request, ssl.SSLSocket):
            self.request.settimeout(30)
            self.request.do_handshake()
        super().setup()

    # --- Journal console ---------------------------------------------------

    def log_message(self, format, *args):
        """Silence : http.server écrirait une ligne par requête, lectures comprises."""

    def log_request(self, code='-', size='-'):
        """Une ligne par écriture : heure, IP, méthode, chemin, statut. Le chemin vient du client : il est écrit en
        repr (audit I2), un retour à la ligne ou un caractère de contrôle ne peut abîmer ni la console ni
        journal-serveur.log."""
        if self.command in ('PUT', 'POST'):
            afficher('%s  %s  %s %s  %s' % (time.strftime('%H:%M:%S'), self.client_address[0],
                                            self.command, repr(self.path[:200]), code))

    # --- Aiguillage --------------------------------------------------------

    @property
    def config(self):
        return self.server.config

    def est_requete_api(self):
        chemin = self.path.split('?', 1)[0]
        return chemin == '/api' or chemin.startswith('/api/')

    def traiter(self, methode):
        # Ordre des contrôles (audit F2, §22.4) : hôte, chemin, accès à l'API (session quand les comptes sont
        # exigés), X-Prevo, puis seulement la lecture du corps : un client sans session ne fait jamais lire 10 Mo (50 Mo
        # pour l'envoi d'une table, T208).
        # Un refus prononcé avant la lecture jette au plus 64 Ko de corps (envoyer_erreur) pour que le navigateur
        # reçoive la réponse ; au-delà, la connexion persistante est fermée après la réponse (les octets non lus
        # seraient pris pour la requête suivante).
        self.corps_lu = methode not in ('PUT', 'POST')
        self.lecture_commencee = False
        self.session = None
        self.mandat = origine_mandatee(self)        # §22.7 : None pour un client direct
        try:
            if not hote_autorise(self.headers.get('Host'), self.config):
                raise ErreurHttp(403, traduisible('requete.hote_refuse',
                                                  'Nom d\'hôte refusé. Utilisez l\'adresse IP du PC.'))
            if self.mandat is not None and not hote_autorise(self.mandat['hote'], self.config):
                raise ErreurHttp(403, MESSAGE_HOTE_ORIGINE_REFUSE)
            morceaux = analyser_chemin(self.path)
            if self.sur_la_porte():
                self.servir_porte(methode, morceaux)       # client du réseau sur port_http : la porte, rien d'autre
                return
            if morceaux[0] == 'api':
                # Assistant d'installation (§22.10) : vu du réseau ou d'un mandataire, il n'existe pas — 404 identique
                # à une adresse inconnue, avant tout contrôle d'accès et avant l'aiguillage.
                if len(morceaux) > 1 and morceaux[1] == 'installation' and not self.client_local():
                    raise ErreurHttp(404, MESSAGE_ADRESSE_INCONNUE)
                self.session = self.controler_acces(methode, morceaux[1:])
            corps = b''
            if methode in ('PUT', 'POST'):
                self.verifier_entete_prevo()
                self.lecture_commencee = True
                corps = self.lire_corps()
                self.corps_lu = True
            if morceaux[0] == 'api':
                self.traiter_api(methode, morceaux[1:], corps)
            elif methode == 'GET':
                self.servir_statique(morceaux)
            else:
                raise ErreurHttp(405, traduisible('requete.methode_non_autorisee', 'Méthode non autorisée.'))
        except ErreurHttp as erreur:
            self.envoyer_erreur(erreur)
        except (ConnectionError, socket.timeout):
            pass                        # le navigateur a fermé la connexion
        except Exception:               # bogue : on le trace sans arrêter le serveur
            traceback.print_exc()
            self.envoyer_erreur(ErreurHttp(500, traduisible('requete.erreur_interne', 'Erreur interne du serveur.')))

    def traiter_api(self, methode, morceaux, corps):
        """Aiguillage d'après ROUTES_API (chemin après /api/) : 404 adresse inconnue, 405 autre méthode. Le segment
        variable est contrôlé avant la méthode, comme avant le lot 7 : table inconnue 404, nom de document refusé
        400."""
        motif = motif_de_route(morceaux)
        if motif is None:
            raise ErreurHttp(404, MESSAGE_ADRESSE_INCONNUE)
        segment = segment_de_route(motif, morceaux)
        if '<table>' in motif:
            chemin_table(self.config, segment)
        elif '<nom>' in motif:
            chemin_document(self.config, segment)
        fonction = ROUTES_API.get((methode, motif))
        if fonction is None:
            raise ErreurHttp(405, traduisible('requete.methode_non_autorisee', 'Méthode non autorisée.'))
        if (methode, motif) in ROUTES_ECRITURE_DES_DONNEES:
            verifier_ecriture_permise(self.config)          # T185 (D169) : données plus récentes, 409
        getattr(self, fonction)(segment, corps)

    # --- Accès à l'API (lot 7, §22.3, §22.4) -------------------------------

    def controler_acces(self, methode, morceaux):
        """Point unique de vérification de l'accès à l'API (D126), avant la lecture du corps (audit F2). Sans comptes
        exigés : rien (portée « ce PC »). Sinon l'identité de la requête (verifier_session) ; hors des routes
        publiques, 401 sans elle, 403 avec un mot de passe provisoire hors des trois routes qui servent à le changer,
        puis le rôle (verifier_role, ROLES_PAR_ROUTE : 403 au message clair)."""
        if not self.config.reglages.get('comptes'):
            return None
        identite = verifier_session(self.config, self.headers.get('Cookie'))
        motif = motif_de_route(morceaux)
        route = (methode, motif)
        if route in ROUTES_PUBLIQUES:
            return identite
        if identite is None:
            if valeurs_cookie(self.headers.get('Cookie'), NOM_COOKIE_APPAREIL):
                # Appareil révoqué, expiré ou enrôlement désactivé (D125) : son cookie est effacé, le navigateur
                # revoit la page d'invitation.
                erreur = ErreurHttp(401, MESSAGE_APPAREIL_REFUSE, appareil_refuse=True)
                erreur.entetes = {'Set-Cookie': entete_cookie_session('', self.en_https(), 0, NOM_COOKIE_APPAREIL)}
                raise erreur
            if motif == 'installation/<etape>' and self.client_local() and aucun_responsable_sur(self.config):
                # §22.10 : comptes exigés mais aucun compte responsable (configuration écrite à la main, comptes.json
                # absent) ; personne ne peut se connecter, l'assistant, depuis ce PC seulement, crée le premier compte.
                return None
            raise ErreurHttp(401, MESSAGE_SESSION_ABSENTE)
        if identite['a_changer'] and route not in ROUTES_MOT_DE_PASSE_PROVISOIRE:
            raise ErreurHttp(403, MESSAGE_MOT_DE_PASSE_PROVISOIRE)
        verifier_role(self.config, identite, route, segment_de_route(motif, morceaux))
        return identite

    mandat = None               # origine_mandatee(self), posée au début de chaque requête (§22.7)

    def adresse_client(self):
        """Adresse du client pour le journal et le ralentissement : celle d'origine derrière un mandataire attesté."""
        return self.mandat['adresse'] if self.mandat is not None else self.client_address[0]

    def en_https(self):
        """Requête arrivée en https (cookie Secure, HSTS) : TLS sur ce serveur, ou mandataire attesté en https."""
        if self.mandat is not None:
            return self.mandat['protocole'] == 'https'
        return isinstance(self.request, ssl.SSLSocket)

    def hote_de_la_requete(self):
        """Nom d'hôte vu par le navigateur (sans port) : l'hôte d'origine derrière un mandataire, sinon Host."""
        return extraire_nom_hote(self.mandat['hote'] if self.mandat is not None else self.headers.get('Host', ''))

    def adresses_donnees(self):
        """(adresse locale, adresses réseau) que Prévo donne à ce client (/api/info, QR, étiquettes) : derrière un
        mandataire attesté, l'adresse d'origine (protocole et hôte des en-têtes, port compris) ; sinon celles du
        serveur (la porte hors de « ce PC », §22.6)."""
        if self.mandat is not None:
            origine = '%s://%s/' % (self.mandat['protocole'], self.mandat['hote'])
            return origine, [origine]
        return self.config.adresse_locale(), self.config.adresses_reseau()

    def origine(self):
        """(adresse, agent, Tailscale) d'une ligne du journal des connexions. L'en-tête Tailscale-User-Login n'est cru
        que d'un mandataire sur ce PC (« mandataire » vrai, connexion venue de 127.0.0.1) ; sinon colonne vide."""
        tailscale = ''
        if self.config.reglages.get('mandataire') and self.client_address[0] in ('127.0.0.1', '::1'):
            tailscale = self.headers.get('Tailscale-User-Login', '')
        return self.adresse_client(), self.headers.get('User-Agent', ''), tailscale

    def exiger_comptes(self):
        """Connexion, déconnexion, mot de passe : seulement quand les comptes sont exigés (400 clair sinon)."""
        if not self.config.reglages.get('comptes'):
            raise ErreurHttp(400, MESSAGE_SANS_COMPTES)

    def repondre_avec_session(self, compte, longue):
        """Ouvre une session pour ce compte et la rend avec son cookie (Max-Age seulement avec « rester »)."""
        jeton = ouvrir_session(self.config, compte['identifiant'], longue, self.headers.get('User-Agent', ''))
        duree = self.config.reglages.get('session_longue_jours', 30) * 86400 if longue else None
        self.session = identite_du_compte(compte, empreinte_jeton(jeton), longue)
        self.envoyer_json(200, {'comptes': True, 'session': session_publique(self.session)},
                          {'Set-Cookie': entete_cookie_session(jeton, self.en_https(), duree)})

    # --- Porte d'entrée (lot 7, §22.6) -------------------------------------

    def client_de_confiance(self):
        """Client servi comme l'application même sur la porte : le PC serveur lui-même (127.0.0.1, ::1), dont le
        navigateur est en contexte sécurisé en http, et le mandataire attesté (§22.7 : « mandataire » vrai, en-têtes
        X-Forwarded-* venus de ce PC), qui porte lui-même le https."""
        return self.client_address[0] in ADRESSES_DE_CE_PC or self.mandat is not None

    def sur_la_porte(self):
        """Requête d'un client du réseau arrivée sur la porte (port_http hors de « ce PC ») : seule la page de porte."""
        return self.server.porte and not self.client_de_confiance()

    def servir_porte(self, methode, morceaux):
        """Porte d'entrée pour un client du réseau : ses propres fichiers (acces/, le favicon, les polices de la
        charte), /acces/ca.crt, et pour toute autre adresse — /api/ compris — la page de porte, 200, sans rien lire
        ni rien servir de l'application. Un corps n'est jamais lu : la connexion est fermée après la réponse."""
        if methode != 'GET':
            self.close_connection = True
        minuscules = [morceau.lower() for morceau in morceaux]
        if minuscules == CHEMIN_CERTIFICAT_AUTORITE:
            self.servir_certificat_autorite()
        elif (methode == 'GET' and fichier_de_la_porte(minuscules)
              and os.path.isfile(chemin_sous(DOSSIER_APPLICATION, *morceaux))):
            self.servir_statique(morceaux, self.entetes_porte())
        else:
            self.envoyer(200, self.page_de_porte(), TYPES_STATIQUES['html'], self.entetes_porte())

    def page_de_porte(self):
        """acces/porte.html avec le port https de ce serveur dans data-port-https (porte.js interroge
        https://<même hôte>:<ce port>/api/ping ; le port vient toujours de la page servie)."""
        octets = lire_octets(PAGE_PORTE)
        if octets is None:
            raise ErreurHttp(500, traduisible('porte.page_introuvable',
                                              'Page de porte introuvable (acces/porte.html).'))
        attribut = 'data-port-https="%d"' % self.config.port_https
        return octets.replace(ATTRIBUT_PORT_HTTPS.encode('ascii'), attribut.encode('ascii'), 1)

    def origine_https(self):
        """Origine https de ce serveur vue par ce client (même hôte que la requête, port_https)."""
        hote = extraire_nom_hote(self.headers.get('Host', ''))
        if ':' in hote:
            hote = '[%s]' % hote
        return 'https://%s:%d' % (hote, self.config.port_https)

    def entetes_porte(self):
        """En-têtes de la porte : ceux de §22.13, la politique n'autorisant au dehors que l'origine https du même
        hôte (le ping de porte.js) ; jamais HSTS (la porte est en http et doit le rester)."""
        entetes = dict(ENTETES_SECURITE)
        entetes['Content-Security-Policy'] = POLITIQUE_PORTE % self.origine_https()
        return entetes

    def servir_certificat_autorite(self):
        """GET /acces/ca.crt : le certificat PUBLIC de l'autorité locale (rootCA.pem seul ; rootCA-key.pem n'est jamais
        lu ni servi), en téléchargement, pour que le téléphone l'installe ; 404 clair sans autorité locale (certificat
        fourni par l'informaticien). Servi par la porte comme par l'application : rien de privé."""
        octets = certificat_de_l_autorite(self.config)
        if octets is None:
            raise ErreurHttp(404, MESSAGE_SANS_AUTORITE)
        self.envoyer(200, octets, TYPE_CERTIFICAT_AUTORITE,
                     {'Content-Disposition': 'attachment; filename="%s"' % NOM_FICHIER_CERTIFICAT_AUTORITE})

    # --- Contrôles des requêtes qui écrivent --------------------------------

    def verifier_entete_prevo(self):
        """X-Prevo: 1 obligatoire : une page d'un autre site ne peut pas l'envoyer."""
        if self.headers.get('X-Prevo') != '1':
            raise ErreurHttp(403, traduisible('requete.entete_prevo_manquant', 'En-tête X-Prevo manquant.'))

    def lire_corps(self):
        """Lit le corps : Content-Length obligatoire (411) et au plus TAILLE_MAX_CORPS (413), TAILLE_MAX_CORPS_CSV pour
        l'envoi d'une table (ROUTES_CORPS_CSV, T208)."""
        longueur_texte = self.headers.get('Content-Length')
        if longueur_texte is None:
            raise ErreurHttp(411, traduisible('requete.longueur_obligatoire', 'En-tête Content-Length obligatoire.'))
        try:
            longueur = int(longueur_texte)
        except ValueError:
            raise ErreurHttp(400, traduisible('requete.longueur_invalide', 'En-tête Content-Length invalide.'))
        if longueur < 0:
            raise ErreurHttp(400, traduisible('requete.longueur_invalide', 'En-tête Content-Length invalide.'))
        morceaux = analyser_chemin(self.path)          # déjà contrôlé par traiter
        route = (self.command, motif_de_route(morceaux[1:])) if morceaux[0] == 'api' else None
        limite = TAILLE_MAX_CORPS_CSV if route in ROUTES_CORPS_CSV else TAILLE_MAX_CORPS
        if longueur > limite:
            raise ErreurHttp(413, traduisible('requete.envoi_trop_gros',
                                              {'one': 'Envoi trop gros ({n} Mo au maximum).',
                                               'other': 'Envoi trop gros ({n} Mo au maximum).'},
                                              n=limite // (1024 * 1024)))
        corps = self.rfile.read(longueur)
        if len(corps) != longueur:
            raise ErreurHttp(400, traduisible('requete.corps_incomplet', 'Corps de la requête incomplet.'))
        return corps

    # --- Fonctions de l'API (appelées avec le segment variable du chemin, ou None, et le corps) ------

    def api_ping(self, segment, corps):
        self.envoyer_json(200, {'application': NOM_APPLICATION,
                                'version': VERSION_APPLICATION, 'api': VERSION_API})

    def api_info(self, segment, corps):
        """GET /api/info : port, adresses (celles de la porte hors de « ce PC », §22.6), « porte » vrai quand elle est
        ouverte (la carte « Connecter un téléphone » rappelle alors « Faites confiance au PC atelier »), et l'état de
        la copie externe des sauvegardes (D133 ; None sans dossier) et de Tailscale (D128, §22.8 ; None quand il n'est
        pas attendu). Jamais le port https : il n'est pas une adresse que Prévo donne (CS137)."""
        adresse_locale, adresses_reseau = self.adresses_donnees()
        self.envoyer_json(200, {'port': self.config.port,
                                'adresse_locale': adresse_locale,
                                'adresses_reseau': adresses_reseau,
                                'porte': self.config.porte and self.mandat is None,
                                # Recette du lot 7 : en portée « ce PC », aucun téléphone ne joint Prévo ; les
                                # écrans le disent (carte « Connecter un téléphone », étiquettes).
                                'ce_pc_seulement': self.config.ce_pc_seulement and self.mandat is None,
                                'actif_depuis': self.config.actif_depuis,        # D130, T170 : instant du démarrage
                                'copie_externe': etat_copie_externe_public(self.config),
                                'tailscale': etat_tailscale_public(self.config),
                                # §22.10 : l'écran propose l'assistant tant que prevo.config.json manque (jamais
                                # imposé : les tests des lots 1 à 6 tournent sans configuration).
                                'installation_a_faire': not self.config.reglages.get('_present'),
                                # T185 : format des données trouvé au démarrage et passage fait ou non (le bandeau
                                # du responsable en dit la raison) ; None quand le serveur ne l'a pas regardé.
                                # T206 : « abimes_depuis », {table: date} des tables abîmées (fichiers-abimes.json).
                                'format': self.config.format_donnees and dict(
                                    self.config.format_donnees, abimes_depuis=lire_fichiers_abimes(self.config))})

    def api_session(self, segment, corps):
        """GET /api/session : comptes exigés ou non, et l'identité de la session (jamais le jeton). Pour un appareil
        enrôlé, son cookie repart pour un an (D125 : un an glissant, à chaque ouverture de l'application)."""
        entetes = None
        if self.session is not None and self.session.get('appareil'):
            for jeton in valeurs_cookie(self.headers.get('Cookie'), NOM_COOKIE_APPAREIL):
                if empreinte_jeton(jeton) == self.session.get('cle'):
                    entetes = {'Set-Cookie': entete_cookie_session(jeton, self.en_https(), DUREE_APPAREIL_JOURS * 86400,
                                                                   NOM_COOKIE_APPAREIL)}
        reponse = {'comptes': bool(self.config.reglages.get('comptes')), 'session': session_publique(self.session)}
        if reponse['comptes'] and self.session is None and aucun_responsable_sur(self.config):
            # §22.10 : aucun compte responsable : l'écran ouvre l'assistant sur le PC serveur au lieu de la connexion.
            reponse['installation_inachevee'] = True
        self.envoyer_json(200, reponse, entetes)

    def api_connexion(self, segment, corps):
        """POST /api/connexion {identifiant, mot_de_passe, rester} : 200 et cookie « id » (jeton neuf ; l'ancienne
        session de ce navigateur est fermée) ; 401 au message neutre ; 429 pendant un blocage (§22.3)."""
        self.exiger_comptes()
        demande = lire_objet_json(corps)
        identifiant, mot_de_passe = demande.get('identifiant'), demande.get('mot_de_passe')
        rester = demande.get('rester', False)
        if not (isinstance(identifiant, str) and isinstance(mot_de_passe, str) and isinstance(rester, bool)):
            raise ErreurHttp(400, traduisible('sessions.connexion_champs',
                                              'Connexion : « identifiant » et « mot_de_passe » (textes) sont '
                                              'attendus, « rester » vaut vrai ou faux.'))
        compte = verifier_tentative(self.config, identifiant, mot_de_passe, self.origine(),
                                    ErreurHttp(401, MESSAGE_CONNEXION_REFUSEE))
        if self.session is not None:
            fermer_session(self.config, self.session['cle'])
        self.repondre_avec_session(compte, rester)

    def api_deconnexion(self, segment, corps):
        """POST /api/deconnexion : la session est supprimée et le cookie effacé."""
        self.exiger_comptes()
        fermer_session(self.config, self.session['cle'])
        adresse, agent, tailscale = self.origine()
        ecrire_journal_acces(self.config, self.session['identifiant'], adresse, agent, 'deconnexion', tailscale)
        self.envoyer_json(200, {'comptes': True, 'session': None},
                          {'Set-Cookie': entete_cookie_session('', self.en_https(), 0)})

    def api_mot_de_passe(self, segment, corps):
        """POST /api/mot-de-passe {actuel, nouveau} : 200 et une session neuve, toutes les autres sessions du compte
        fermées ; 400 si le nouveau est refusé (12 à 256 caractères, différent de l'actuel) ; 403 si l'actuel est faux
        (compté comme un échec de connexion) ; 429 pendant un blocage."""
        self.exiger_comptes()
        demande = lire_objet_json(corps)
        actuel, nouveau = demande.get('actuel'), demande.get('nouveau')
        if not (isinstance(actuel, str) and isinstance(nouveau, str)):
            raise ErreurHttp(400, traduisible('sessions.mot_de_passe_champs',
                                              'Mot de passe : « actuel » et « nouveau » (textes) sont attendus.'))
        try:
            verifier_mot_de_passe_choisi(nouveau)
        except ErreurCompte as erreur:
            raise ErreurHttp(400, traduisible_de(erreur))
        if nouveau == actuel:
            raise ErreurHttp(400, traduisible('sessions.mot_de_passe_identique',
                                              'Choisissez un mot de passe différent de l\'actuel.'))
        identifiant, origine = self.session['identifiant'], self.origine()
        verifier_tentative(self.config, identifiant, actuel, origine, ErreurHttp(403, MESSAGE_ACTUEL_FAUX),
                           journal_reussite=None)
        try:
            changer_mot_de_passe(self.config, identifiant, nouveau, origine=origine)
        except ErreurCompte as erreur:
            raise ErreurHttp(400, traduisible_de(erreur))
        compte = trouver_compte(comptes_du_serveur(self.config), identifiant)
        self.repondre_avec_session(compte, self.session['longue'])

    def api_enroler(self, segment, corps):
        """POST /api/enroler {invitation, nom} (route publique, D125) : l'appareil est enrôlé, reçoit son cookie
        « appareil » (un an) et l'identité d'un demandeur ; 401 invitation inconnue, expirée ou révoquée ; 403
        enrôlement désactivé (demandeurs_avec_compte) ; 400 corps ou nom invalide."""
        self.exiger_comptes()
        demande = lire_objet_json(corps)
        invitation, nom = demande.get('invitation'), demande.get('nom')
        if not (isinstance(invitation, str) and isinstance(nom, str)):
            raise ErreurHttp(400, traduisible('appareils.enrolement_champs',
                                              'Enrôlement : « invitation » et « nom » (textes) sont attendus.'))
        jeton, appareil = enroler_appareil(self.config, invitation, nom, self.headers.get('User-Agent', ''))
        self.session = identite_de_l_appareil(appareil, empreinte_jeton(jeton))
        adresse, agent, tailscale = self.origine()
        ecrire_journal_acces(self.config, self.session['identifiant'], adresse, agent, 'appareil', tailscale)
        self.envoyer_json(200, {'comptes': True, 'session': session_publique(self.session)},
                          {'Set-Cookie': entete_cookie_session(jeton, self.en_https(), DUREE_APPAREIL_JOURS * 86400,
                                                               NOM_COOKIE_APPAREIL)})

    def api_deconnecter_partout(self, segment, corps):
        """POST /api/acces/deconnecter-partout : sans corps (ou {}), toutes les sessions de la personne connectée, la
        sienne comprise ; {"identifiant": X} pour un autre compte : responsable seulement (403), 404 compte inconnu."""
        self.exiger_comptes()
        demande = lire_objet_json(corps) if corps.strip() else {}
        cible = demande.get('identifiant', self.session['identifiant'])
        if not isinstance(cible, str) or not cible.strip():
            raise ErreurHttp(400, traduisible('sessions.identifiant_attendu',
                                              '« identifiant » : l\'identifiant d\'un compte est attendu.'))
        cible = identifiant_tape(cible)
        soi_meme = cible == self.session['identifiant']
        if not soi_meme:
            if self.session['role'] != 'responsable':
                raise ErreurHttp(403, traduisible('sessions.reserve_au_responsable',
                                                  'Réservé au responsable : vous ne pouvez fermer que vos propres '
                                                  'sessions.'))
            if trouver_compte(comptes_du_serveur(self.config), cible) is None:
                raise ErreurHttp(404, traduisible('comptes.introuvable',
                                                  'Compte introuvable : {identifiant}.', identifiant=cible))
        nombre = fermer_sessions_de(self.config, cible)
        adresse, agent, tailscale = self.origine()
        ecrire_journal_acces(self.config, cible, adresse, agent, 'deconnexion', tailscale)
        entetes = {'Set-Cookie': entete_cookie_session('', self.en_https(), 0)} if soi_meme else None
        self.envoyer_json(200, {'identifiant': cible, 'sessions_fermees': nombre}, entetes)

    def api_comptes(self, segment, corps):
        """GET /api/acces/comptes (responsable, §22.4) : les comptes par compte_public, jamais d'empreinte ni de sel."""
        self.exiger_comptes()
        self.envoyer_json(200, {'comptes': [compte_public(compte) for compte in comptes_du_serveur(self.config)]})

    def api_compte_creer(self, segment, corps):
        """POST /api/acces/comptes (responsable) {prenom, nom, role, technicien_id, autre_personne} : compte créé avec un
        mot de passe provisoire de 16 caractères, à changer à la première connexion (a_changer), rendu une seule fois
        dans la réponse : jamais écrit dans un fichier, le journal ou la console. T301 : même prénom et même nom qu'un
        compte existant → 400 comptes.meme_personne, sauf autre_personne vrai."""
        self.exiger_comptes()
        demande = lire_objet_json(corps)
        autre_personne = demande.pop('autre_personne', False)       # T301 : case « C'est une autre personne »
        if not isinstance(autre_personne, bool):
            raise ErreurHttp(400, traduisible('comptes.autre_personne_booleen',
                                              '« autre_personne » vaut vrai ou faux.'))
        champs = champs_de_compte(self.config, demande, obligatoires=('prenom', 'role'))
        provisoire = mot_de_passe_provisoire()
        try:
            compte = creer_compte(self.config, champs['prenom'], champs.get('nom', ''), champs['role'], provisoire,
                                  technicien_id=champs.get('technicien_id', ''), a_changer=True,
                                  origine=self.origine(), autre_personne=autre_personne)
        except ErreurCompte as erreur:
            raise ErreurHttp(400, traduisible_de(erreur))
        self.envoyer_json(200, {'compte': compte, 'mot_de_passe_provisoire': provisoire})

    def api_compte_changer(self, identifiant, corps):
        """POST /api/acces/comptes/<identifiant> (responsable) {"action": "modifier" (prenom, nom, role, technicien_id)
        | "reinitialiser" | "desactiver" | "activer"} : fonctions de T150 (au moins un responsable actif reste : 400) ;
        « reinitialiser » rend le mot de passe provisoire une seule fois ; 404 compte inconnu, 400 action inconnue."""
        self.exiger_comptes()
        demande = lire_objet_json(corps)
        action = demande.pop('action', None)
        if action not in ACTIONS_COMPTE:
            raise ErreurHttp(400, traduisible('comptes.action_attendue',
                                              '« action » attendue : {actions}.', actions=', '.join(ACTIONS_COMPTE)))
        if action != 'modifier' and demande:
            raise ErreurHttp(400, traduisible('comptes.action_sans_champ',
                                              'L\'action « {action} » ne prend aucun autre champ.', action=action))
        champs = champs_de_compte(self.config, demande) if action == 'modifier' else {}
        cible = trouver_compte(comptes_du_serveur(self.config), identifiant)
        if cible is None:
            raise ErreurHttp(404, traduisible('comptes.introuvable',
                                              'Compte introuvable : {identifiant}.',
                                              identifiant=identifiant[:LONGUEUR_MAX_IDENTIFIANT]))
        reponse = {}
        try:
            if action == 'reinitialiser':
                reponse['mot_de_passe_provisoire'] = reinitialiser_compte(self.config, cible['identifiant'],
                                                                          origine=self.origine())
                compte = compte_public(trouver_compte(comptes_du_serveur(self.config), cible['identifiant']))
            elif action == 'modifier':
                compte = modifier_compte(self.config, cible['identifiant'], origine=self.origine(), **champs)
            else:
                compte = modifier_compte(self.config, cible['identifiant'], origine=self.origine(),
                                         actif=(action == 'activer'))
        except ErreurCompte as erreur:
            raise ErreurHttp(400, traduisible_de(erreur))
        reponse['compte'] = compte
        self.envoyer_json(200, reponse)

    def api_journal_acces(self, segment, corps):
        """GET /api/acces/journal (responsable) : le journal des connexions (CSV), en téléchargement ; l'en-tête seul
        tant qu'il n'existe pas."""
        self.exiger_comptes()
        with VERROU_ACCES_JOURNAL:
            octets = lire_octets(os.path.join(dossier_acces(self.config), 'journal-acces.csv'))
        if octets is None:
            octets = BOM_UTF8 + (';'.join(COLONNES_JOURNAL_ACCES) + '\r\n').encode('utf-8')
        self.envoyer(200, octets, 'text/csv; charset=utf-8',
                     {'Content-Disposition': 'attachment; filename="journal-acces.csv"'})

    def api_invitations(self, segment, corps):
        """GET /api/acces/invitations (responsable, §22.4) : invitations et appareils, sans empreinte, et si
        l'enrôlement est actif (demandeurs_avec_compte faux)."""
        self.exiger_comptes()
        maintenant = maintenant_s(self.config)
        with VERROU_APPAREILS:
            contenu = lire_appareils(self.config)
        self.envoyer_json(200, {'invitations': [invitation_publique(i, maintenant) for i in contenu['invitations']],
                                'appareils': [appareil_public(a, maintenant) for a in contenu['appareils']],
                                'enrolement_actif': not self.config.reglages.get('demandeurs_avec_compte')})

    def api_invitation_creer(self, segment, corps):
        """POST /api/acces/invitations {heures} (responsable ; sans corps : invitation_heures) : invitation neuve ;
        le jeton et le chemin du lien sont rendus une seule fois (le QR et le lien se font côté navigateur, avec
        l'adresse http de la porte), jamais écrits."""
        self.exiger_comptes()
        demande = lire_objet_json(corps) if corps.strip() else {}
        inconnus = sorted(set(demande) - {'heures'})
        if inconnus:
            raise ErreurHttp(400, traduisible('appareils.champ_inconnu',
                                              'Champ inconnu : « {champ} » (« heures » seulement).',
                                              champ=str(inconnus[0])[:60]))
        jeton, invitation = creer_invitation(self.config, demande.get('heures'))
        adresse, agent, tailscale = self.origine()
        ecrire_journal_acces(self.config, self.session['identifiant'], adresse, agent, 'invitation', tailscale)
        self.envoyer_json(200, {'invitation': invitation, 'jeton': jeton, 'chemin': CHEMIN_ENROLEMENT + jeton})

    def api_invitation_revoquer(self, identifiant, corps):
        """POST /api/acces/invitations/<id>/revoquer (responsable) : plus personne ne s'enrôle avec ; 404 inconnue."""
        self.exiger_comptes()
        revoquees = revoquer(self.config, 'invitations', identifiant)
        adresse, agent, tailscale = self.origine()
        for revoquee in revoquees:
            ecrire_journal_acces(self.config, 'invitation:' + revoquee, adresse, agent, 'revocation', tailscale)
        self.envoyer_json(200, {'invitation': identifiant, 'revoquee': True})

    def api_appareil_revoquer(self, identifiant, corps):
        """POST /api/acces/appareils/<id>/revoquer (responsable) : l'appareil est refusé dès sa requête suivante
        (401, cookie effacé) ; 404 inconnu."""
        self.exiger_comptes()
        revoques = revoquer(self.config, 'appareils', identifiant)
        adresse, agent, tailscale = self.origine()
        for revoque in revoques:
            ecrire_journal_acces(self.config, 'appareil:' + revoque, adresse, agent, 'revocation', tailscale)
        self.envoyer_json(200, {'appareil': identifiant, 'revoque': True})

    def api_appareils_revoquer_tous(self, segment, corps):
        """POST /api/acces/appareils/revoquer-tous (responsable) : tous les appareils enrôlés, d'un coup."""
        self.exiger_comptes()
        revoques = revoquer(self.config, 'appareils')
        adresse, agent, tailscale = self.origine()
        for revoque in revoques:
            ecrire_journal_acces(self.config, 'appareil:' + revoque, adresse, agent, 'revocation', tailscale)
        self.envoyer_json(200, {'appareils_revoques': revoques})

    def api_ia(self, segment, corps):
        """Relais vers le fournisseur d'IA réglé sur le PC serveur (lot 4, §17.2 ; audit M1, M2, M3, §22.12).

        Rend { statut, corps } : le statut et le corps (JSON, sinon texte) du fournisseur, sans la clé.
        Demande invalide (une adresse, une clé ou un délai dans le corps compris) → 400 ; fournisseur en
        ligne sans « ia_en_ligne » (D67) → 403, avant tout appel sortant ; échec réseau ou réponse coupée
        → 502 ; délai dépassé → 504. La clé ne quitte le PC serveur que vers le fournisseur.
        """
        demande = lire_demande_ia(corps, self.config.reglages)
        if fournisseur_distant(demande['cible']) and not distant_autorise(self.config):
            raise ErreurHttp(403, MESSAGE_DISTANT_REFUSE)
        statut, octets = appeler_fournisseur(demande)
        if len(octets) > TAILLE_MAX_REPONSE_IA:
            raise ErreurHttp(502, traduisible('ia.reponse_trop_grande',
                                              'Réponse du fournisseur d\'IA trop grande (2 Mo au maximum).'))
        octets = sans_la_cle(octets, cle_ia(self.config.reglages))
        self.envoyer_json(200, {'statut': statut, 'corps': corps_lisible(octets)})

    def api_ia_reglages(self, segment, corps):
        """GET /api/ia/reglages : fournisseur, adresse, clé réglée ou non, IA en ligne, portée (jamais la clé)."""
        self.envoyer_json(200, reglages_ia_publics(self.config))

    def api_versions(self, segment, corps):
        """GET /api/versions : version de chaque table ; pour le demandeur, seulement celles qu'il lit (§22.5)."""
        with VERROU_ECRITURE:
            tables = versions_des_tables(self.config)
        lisibles = tables_lisibles(self.session)
        if lisibles is not None:
            tables = {table: version for table, version in tables.items() if table in lisibles}
        self.envoyer_json(200, {'tables': tables})

    def api_csv_lire(self, table, corps):
        """GET /api/csv/<table> : le fichier, sans les colonnes ni les lignes que le rôle de la session ne reçoit pas
        (§22.5) ; X-Version est celle du fichier entier, pour que les écritures restent possibles."""
        chemin = chemin_table(self.config, table)            # 404 si table inconnue
        with VERROU_ECRITURE:
            octets = lire_octets(chemin)
        if octets is None:
            raise ErreurHttp(404, traduisible('csv.absent',
                                              'Le fichier {table}.csv n\'existe pas encore.', table=table))
        self.envoyer(200, filtrer_csv_pour(self.session, table, octets), 'text/csv; charset=utf-8',
                     {'X-Version': empreinte(octets)})

    def api_csv_ecrire(self, table, corps):
        version_attendue = self.headers.get('X-Version-Attendue')
        if not version_attendue:
            raise ErreurHttp(400, traduisible('csv.version_manquante', 'En-tête X-Version-Attendue manquant.'))
        # T200 : « X-Prevo-Remplacer-Abime: 1 » (import ZIP) permet de remplacer un fichier abîmé ; aucun droit de plus.
        # Avec les comptes, l'import ZIP est réservé au responsable (D172) : la dérogation aussi (403 sinon, rien écrit).
        remplacer_abime = (self.headers.get(ENTETE_REMPLACER_ABIME) or '').strip() == '1'
        if remplacer_abime and self.session is not None and role_effectif(self.session) != 'responsable':
            raise ErreurHttp(403, traduisible('csv.remplacer_abime_reserve',
                                              'Accès refusé : seul le responsable remplace un fichier abîmé (import '
                                              'ZIP).'))
        # T213 : « X-Prevo-Abime-Depuis: AAAA-MM-JJTHH:MM:SS », seulement avec la dérogation (400 sinon, rien écrit).
        abime_depuis = self.headers.get(ENTETE_ABIME_DEPUIS)
        if abime_depuis is not None:
            abime_depuis = abime_depuis.strip()
            if not remplacer_abime or not MOTIF_DATE_DEPUIS.fullmatch(abime_depuis):
                raise ErreurHttp(400, traduisible('csv.entete_abime_depuis',
                                                  'En-tête {entete} refusé : une date AAAA-MM-JJTHH:MM:SS, avec '
                                                  '{derogation}: 1.',
                                                  entete=ENTETE_ABIME_DEPUIS, derogation=ENTETE_REMPLACER_ABIME))
        with VERROU_ECRITURE:
            version = enregistrer_csv(self.config, table, corps, version_attendue.strip(),
                                      controle_d_ecriture(self.session, table), remplacer_abime=remplacer_abime,
                                      abime_depuis=abime_depuis)
        self.envoyer_json(200, {'version': version})

    def api_ajout(self, table, corps):
        with VERROU_ECRITURE:
            version = ajouter_au_csv(self.config, table, corps, controle_d_ajout(self.session, table))
        self.envoyer_json(200, {'version': version})

    def api_document_lire(self, nom, corps):
        chemin = chemin_document(self.config, nom)          # 400 si nom refusé, 415 si type refusé
        octets = lire_octets(chemin)
        if octets is None:
            raise ErreurHttp(404, traduisible('documents.introuvable', 'Document introuvable : {nom}.', nom=nom))
        # nosniff + sandbox : un document ne peut jamais s'exécuter comme une page. Hors images et PDF (audit F4) :
        # en téléchargement, jamais affiché dans la page (le nom ne contient que lettres, chiffres, « . », « _ », « - »).
        entetes = {'Content-Security-Policy': 'sandbox'}
        if extension(nom) not in TYPES_AFFICHABLES:
            entetes['Content-Disposition'] = 'attachment; filename="%s"' % nom
        self.envoyer(200, octets, TYPES_DOCUMENTS[extension(nom)], entetes)

    def api_document_ecrire(self, nom, corps):
        """PUT /api/documents/<nom> : 201 {"nom"} avec le nom imposé par le serveur (audit F4, nom_de_document_impose) ;
        400 nom ou signature d'image refusés, 415 type refusé, 413 quota du dossier (audit F2), 409 même nom demandé
        dans la même seconde ; rien n'est écrit dans ces cas."""
        verifier_nom_document(nom, demande=True)
        verifier_signature_image(nom, corps)
        with VERROU_ECRITURE:
            nom_enregistre = enregistrer_document(self.config, nom, corps)
        self.envoyer_json(201, {'nom': nom_enregistre})

    def api_sauvegarde(self, segment, corps):
        """Sauvegarde manuelle (corps vide) ou automatique avec un motif de la liste fermée
        (corps {"motif": "avant-format-v2"} → nom « AAAA-MM-JJ_HHMMSS_avant-format-v2 »).
        Manuelle (D133) : une par minute au plus (429 et Retry-After), les 60 dernières gardées ; une sauvegarde à
        motif n'est ni limitée ni comptée."""
        motif = lire_motif_sauvegarde(corps)            # 400 si motif refusé, avant toute écriture
        # T187 : « avant-import-zip » copie aussi donnees/documents/ ; manifeste.json dans toute sauvegarde.
        suffixe = '_' + motif if motif else ''
        with VERROU_ECRITURE:
            if not motif:
                verifier_plafond_manuelles(self.config)
            nom = nouveau_nom_horodate(self.config, suffixe)
            verifier_nom_sauvegarde(nom)                # sécurité : le nom reste dans les règles
            copier_tables_dans_sauvegarde(self.config, nom)
            if not motif:
                purger_sauvegardes_manuelles(self.config)
        self.envoyer_json(200, {'sauvegarde': nom})

    def api_sauvegarde_tester(self, segment, corps):
        """POST /api/sauvegarde/tester {"nom"} (D133) : relit chaque CSV de la sauvegarde et compte ses lignes, sans
        rien écrire ; 400 corps ou nom refusé, 404 sauvegarde introuvable ou incomplète."""
        demande = lire_objet_json(corps)
        self.envoyer_json(200, tester_sauvegarde(self.config, demande.get('nom')))

    def api_sauvegardes(self, segment, corps):
        self.envoyer_json(200, {'sauvegardes': lister_sauvegardes(self.config)})

    def api_restauration(self, segment, corps):
        demande = lire_objet_json(corps)
        with VERROU_ECRITURE:
            resultat = restaurer(self.config, demande.get('sauvegarde'), demande.get('tables'))
        self.envoyer_json(200, resultat)

    # --- Assistant d'installation (lot 7, §22.10 ; D131, CS130) -------------

    def client_local(self):
        """Le PC serveur lui-même (127.0.0.1, ::1) sans mandataire : seul client des routes /api/installation/…"""
        return self.client_address[0] in ADRESSES_DE_CE_PC and self.mandat is None

    def api_installation_lire(self, etape, corps):
        """GET /api/installation/etat, /fiche et /journal (§22.10) ; toute autre étape : 404 comme une adresse
        inconnue."""
        if etape == 'etat':
            self.envoyer_json(200, etat_installation(self.config))
        elif etape == 'fiche':
            self.envoyer_json(200, fiche_acces(self.config))
        elif etape == 'journal':
            self.envoyer_json(200, dernieres_lignes_du_journal(self.config))
        else:
            raise ErreurHttp(404, MESSAGE_ADRESSE_INCONNUE)

    def api_installation_ecrire(self, etape, corps):
        """POST /api/installation/<etape> (situation, portee, compte, certificat, tailscale, demarrage, sauvegardes,
        deplacer, terminer ; Paramètres (T170) : reprendre, reglages, ia, annuler ; 404 sinon), X-Prevo exigé par
        traiter : lit le brouillon (400 s'il manque, sauf pour « situation » et « reprendre » qui le créent et
        « annuler » qui le jette), joue l'étape sous VERROU_INSTALLATION et rend sa réponse."""
        if etape not in ETAPES_D_ECRITURE:
            raise ErreurHttp(404, MESSAGE_ADRESSE_INCONNUE)
        demande = lire_objet_json(corps) if corps.strip() else {}
        with VERROU_INSTALLATION:
            brouillon = lire_brouillon(self.config)
            if brouillon is None and etape not in ETAPES_SANS_BROUILLON:
                raise ErreurHttp(400, MESSAGE_SANS_BROUILLON)
            reponse = getattr(self, 'installation_' + etape)(brouillon, demande)
        self.envoyer_json(200, reponse)

    def garder_brouillon(self, brouillon, etape=None, etat=ETAT_FAIT):
        """Note l'état de l'étape, complète (ecoute, étapes) et écrit le brouillon ; rend {"brouillon", "etapes"}."""
        if etape:
            brouillon.setdefault('etapes', {})[etape] = etat
        completer_brouillon(self.config, brouillon)
        ecrire_brouillon(self.config, brouillon)
        return {'brouillon': brouillon, 'etapes': brouillon['etapes']}

    def installation_situation(self, brouillon, demande):
        """{"situation": seul | equipe | informaticien} : brouillon réinitialisé aux défauts de cette situation."""
        situation = demande.get('situation')
        if situation not in SITUATIONS:
            raise ErreurHttp(400, traduisible('installation.situation_inconnue',
                                              'Situation inconnue : « seul », « equipe » ou « informaticien ».'))
        return self.garder_brouillon(brouillon_neuf(self.config, situation))

    # --- Paramètres › Accès et installation (T170 ; D131 dernier point, CS130) : chaque réglage refaisable -----

    def installation_reprendre(self, brouillon, demande):
        """{} : brouillon repris de la configuration en cours (brouillon_depuis_configuration), pour refaire un réglage
        depuis Paramètres sans repasser par les défauts d'une situation ; 400 tant que l'installation n'est pas
        terminée (l'assistant s'en charge). Un brouillon déjà là est rendu tel quel (« repris » faux) : les
        modifications en attente ne sont jamais perdues par un rechargement de l'écran."""
        if brouillon is not None:
            return {'brouillon': brouillon, 'etapes': brouillon.get('etapes'), 'repris': False}
        if not self.config.reglages.get('_present'):
            raise ErreurHttp(400, traduisible('installation.non_terminee',
                                              'L\'installation n\'est pas terminée : réglez l\'accès par '
                                              'l\'assistant ({adresse}).', adresse=ROUTE_INSTALLATION))
        return dict(self.garder_brouillon(brouillon_depuis_configuration(self.config)), repris=True)

    def installation_reglages(self, brouillon, demande):
        """{"demandeurs_avec_compte"?, "session_heures"?, "session_longue_jours"?, "invitation_heures"?,
        "quota_documents_mo"?} (CLES_REGLAGES_SIMPLES, une au moins) : chaque valeur contrôlée comme dans le fichier
        (bornes de CLES_CONFIGURATION ; 400 au message, qui cite les bornes) ; toute autre clé 400."""
        if not demande:
            raise ErreurHttp(400, traduisible('installation.aucun_reglage',
                                              'Aucun réglage reçu : {cles}.', cles=', '.join(CLES_REGLAGES_SIMPLES)))
        for cle, valeur in demande.items():
            if cle not in CLES_REGLAGES_SIMPLES:
                raise ErreurHttp(400, traduisible('installation.reglage_inconnu',
                                                  'Réglage inconnu « {cle} » : {cles}.',
                                                  cle=cle, cles=', '.join(CLES_REGLAGES_SIMPLES)))
            brouillon[cle] = valeur_du_brouillon(cle, valeur)
        return self.garder_brouillon(brouillon)

    def installation_ia(self, brouillon, demande):
        """{"fournisseur": ollama | openai, "url", "en_ligne": bool} (chacune facultative, une au moins) : fournisseur
        d'IA côté serveur (§22.12). La clé ne passe jamais par l'API (400 si elle est envoyée) : ia_cle du fichier ou
        PREVO_IA_CLE, comme à T158 ; la réponse dit seulement si une clé est réglée."""
        if not demande:
            raise ErreurHttp(400, traduisible('installation.ia_aucun_reglage',
                                              'Aucun réglage reçu : fournisseur, url, en_ligne.'))
        for nom, valeur in demande.items():
            if nom not in CLES_IA_DU_CORPS:
                raise ErreurHttp(400, traduisible('installation.ia_reglage_inconnu',
                                                  'Réglage inconnu « {cle} » : fournisseur, url, en_ligne. La clé '
                                                  'se règle dans le fichier de configuration (ia_cle) ou par '
                                                  'PREVO_IA_CLE, jamais par l\'API.', cle=nom))
            brouillon[CLES_IA_DU_CORPS[nom]] = valeur_du_brouillon(CLES_IA_DU_CORPS[nom], valeur)
        if not brouillon.get('ia_url'):
            raise ErreurHttp(400, traduisible('installation.ia_adresse',
                                              'Donnez l\'adresse du service d\'IA (« url »).'))
        return dict(self.garder_brouillon(brouillon), cle_reglee=bool(cle_ia(self.config.reglages)))

    def installation_annuler(self, brouillon, demande):
        """{} : le brouillon est supprimé, rien d'autre ne change (la configuration en cours reste celle du fichier)."""
        supprimer_brouillon(self.config)
        return {'brouillon': None, 'etapes': {etape: ETAT_A_FAIRE for etape in ETAPES_INSTALLATION}}

    def installation_portee(self, brouillon, demande):
        """{"portee": ce-pc | atelier | dehors, "port_http"?, "port_https"?, "noms"?} : « ce PC » ⇒ comptes faux et
        aucun mandataire ; au-delà ⇒ comptes exigés ; ports et noms contrôlés comme dans le fichier (400 sinon)."""
        portee = demande.get('portee')
        if portee not in PORTEES:
            raise ErreurHttp(400, traduisible('installation.portee_inconnue',
                                              'Portée inconnue : « ce-pc », « atelier » ou « dehors ».'))
        for cle in ('port_http', 'port_https', 'noms'):
            if cle in demande:
                brouillon[cle] = valeur_du_brouillon(cle, demande[cle])
        if brouillon['port_http'] == brouillon['port_https']:
            raise ErreurHttp(400, traduisible('installation.ports_identiques',
                                              'Les ports http et https doivent être différents.'))
        brouillon['portee'] = portee
        if portee == 'ce-pc':
            brouillon['comptes'] = False
            brouillon['mandataire'] = False
        else:
            brouillon['comptes'] = True
        return self.garder_brouillon(brouillon, 'portee')

    def installation_compte(self, brouillon, demande):
        """{"prenom", "nom", "mot_de_passe"} : compte responsable créé tout de suite dans comptes.json (12 caractères
        au moins, règles du serveur ; 409 s'il existe déjà un responsable actif : l'assistant propose de passer) ; en
        Solo, technicien « moi » créé dans techniciens.csv à partir du prénom et du nom, lié au compte. Sur « ce PC »
        en Solo : le technicien seul, sans compte ni mot de passe (aucun compte n'y sert) ; 400 ailleurs. Rend le compte
        public, jamais le mot de passe."""
        prenom = demande.get('prenom') if isinstance(demande.get('prenom'), str) else ''
        nom = demande.get('nom') if isinstance(demande.get('nom'), str) else ''
        prenom, nom = prenom.strip(), nom.strip()
        if not prenom:
            raise ErreurHttp(400, traduisible('comptes.prenom_obligatoire', 'Le prénom est obligatoire.'))
        solo = bool(brouillon.get('mode_solo'))
        if solo:
            verifier_ecriture_permise(self.config)          # T185 : techniciens.csv serait écrit (lecture seule)
        if brouillon.get('portee') == 'ce-pc':
            if not solo:
                raise ErreurHttp(400, traduisible('installation.compte_inutile',
                                                  'Sur ce PC seulement, aucun compte n\'est nécessaire : passez '
                                                  'cette étape.'))
            with VERROU_ECRITURE:
                technicien_id = technicien_moi(self.config, prenom, nom)
            brouillon['solo_technicien_id'] = technicien_id
            reponse = self.garder_brouillon(brouillon, 'compte')
            return dict(reponse, compte=None, technicien_id=technicien_id)
        existant = next((c for c in comptes_du_serveur(self.config) if c.get('role') == 'responsable' and c.get('actif')),
                        None)
        if existant is not None:
            raise ErreurHttp(409, traduisible('installation.responsable_existe',
                                              'Un compte responsable existe déjà (« {identifiant} ») : passez cette '
                                              'étape, ou réinitialisez son mot de passe par {script}.',
                                              identifiant=existant['identifiant'], script=NOM_SCRIPT_REINITIALISATION))
        try:
            verifier_mot_de_passe_choisi(demande.get('mot_de_passe'))
        except ErreurCompte as erreur:
            raise ErreurHttp(400, traduisible_de(erreur))
        technicien_id = ''
        if solo:
            with VERROU_ECRITURE:
                technicien_id = technicien_moi(self.config, prenom, nom)
        try:
            compte = creer_compte(self.config, prenom, nom, 'responsable', demande['mot_de_passe'],
                                  technicien_id=technicien_id, origine=self.origine())
        except ErreurCompte as erreur:
            raise ErreurHttp(400, traduisible_de(erreur))
        brouillon['solo_technicien_id'] = technicien_id
        reponse = self.garder_brouillon(brouillon, 'compte')
        return dict(reponse, compte=compte, technicien_id=technicien_id)

    def installation_certificat(self, brouillon, demande):
        """{"mode": automatique | reseau_prive | fichiers | mandataire, "certificat"?, "cle"?, "noms"?} : automatique ⇒
        certificat fabriqué tout de suite par mkcert (PREVO_MKCERT ou outils-tiers/ ; 503 au message clair sans lui,
        brouillon inchangé) ; fichiers ⇒ les deux PEM lus pour vérifier (400 sinon) ; réseau privé ⇒ Tailscale porte le
        https (mandataire sur ce PC) ; mandataire ⇒ noms obligatoires. Rend ce que la fiche d'accès montrera."""
        mode = demande.get('mode')
        if mode not in MODES_CERTIFICAT:
            raise ErreurHttp(400, traduisible('installation.certificat_mode_inconnu',
                                              'Mode inconnu : « automatique », « reseau_prive », « fichiers » ou '
                                              '« mandataire ».'))
        if brouillon.get('portee') == 'ce-pc':
            raise ErreurHttp(400, traduisible('installation.certificat_inutile',
                                              'Sur ce PC seulement, Prévo reste en http : aucun certificat à '
                                              'préparer.'))
        noms_certificat = []
        if mode == 'automatique':
            try:
                executable = executable_mkcert()
            except ErreurConfiguration as erreur:
                raise ErreurHttp(503, traduisible('installation.certificat_sans_mkcert',
                                                  'Certificat automatique impossible : {erreur} Remettez mkcert '
                                                  'dans le dossier outils-tiers/ (il est dans le zip de Prévo), ou '
                                                  'choisissez le réseau privé ou vos propres fichiers.',
                                                  erreur=traduisible_de(erreur)))
            try:
                _, _, noms_certificat = preparer_certificat_local(self.config, executable,
                                                                  noms_acceptes=brouillon.get('noms', []))
            except ErreurConfiguration as erreur:
                raise ErreurHttp(503, traduisible('installation.certificat_impossible',
                                                  'Certificat automatique impossible : {erreur}',
                                                  erreur=traduisible_de(erreur)))
            brouillon.update(certificat_auto=True, certificat='', cle='')
        elif mode == 'fichiers':
            certificat, cle = demande.get('certificat'), demande.get('cle')
            if not (isinstance(certificat, str) and certificat.strip() and isinstance(cle, str) and cle.strip()):
                raise ErreurHttp(400, traduisible('installation.certificat_fichiers',
                                                  'Donnez les deux fichiers PEM : « certificat » et « cle ».'))
            certificat, cle = os.path.abspath(certificat.strip()), os.path.abspath(cle.strip())
            try:
                creer_contexte_ssl(certificat, cle)
            except SystemExit as erreur:
                raise ErreurHttp(400, traduisible_de(erreur))
            brouillon.update(certificat=certificat, cle=cle, certificat_auto=False, mandataire=False)
        elif mode == 'reseau_prive':
            brouillon.update(certificat_auto=False, certificat='', cle='', mandataire=True)
        else:
            noms = valeur_du_brouillon('noms', demande['noms']) if 'noms' in demande else brouillon.get('noms', [])
            if not noms:
                raise ErreurHttp(400, traduisible('installation.mandataire_noms',
                                                  'Donnez le nom par lequel le mandataire appelle Prévo (« noms »).'))
            brouillon.update(noms=noms, certificat_auto=False, certificat='', cle='', mandataire=True)
        reponse = self.garder_brouillon(brouillon, 'certificat')
        return dict(reponse, mode=mode, noms_certificat=noms_certificat,
                    autorite_presente=certificat_de_l_autorite(self.config) is not None)

    def installation_tailscale(self, brouillon, demande):
        """{"action": detecter | appliquer | unattended | plus_tard} : détection et proposition (rien d'écrit) ;
        appliquer ⇒ « tailscale serve » lancée et vérifiée (§22.8), brouillon : noms + nom Tailscale, mandataire vrai
        (503 au message si Tailscale manque ou n'est pas connecté) ; unattended ⇒ « tailscale set --unattended=true »
        (503 si refusé) ; plus tard ⇒ rien, étape à faire. Jamais « up », jamais d'installation (T165)."""
        action = demande.get('action')
        if action not in ACTIONS_TAILSCALE:
            raise ErreurHttp(400, traduisible('installation.tailscale_action_inconnue',
                                              'Action inconnue : « detecter », « appliquer », « unattended » ou '
                                              '« plus_tard ».'))
        if action == 'detecter':
            detection = detecter_tailscale(maintenant=maintenant_s(self.config))
            proposition = preparer_tailscale(self.config, detection, systeme=self.config.systeme, reglages=brouillon)
            return {'detection': detection_tailscale_publique(detection), 'proposition': proposition,
                    'brouillon': brouillon, 'etapes': brouillon.get('etapes')}
        if action == 'appliquer':
            resultat = appliquer_tailscale(self.config, reglages=brouillon, ecrire=False)
            if not resultat['ok']:
                raise ErreurHttp(503, resultat['message'])
            brouillon.update(noms=resultat['noms'], mandataire=True)
            reponse = self.garder_brouillon(brouillon, 'tailscale')
            return dict(reponse, ok=True, message=resultat['message'], nom=resultat['nom'], adresse=resultat['adresse'])
        if action == 'unattended':
            resultat = activer_unattended()
            if not resultat['ok']:
                raise ErreurHttp(503, resultat['message'])
            return dict(resultat, brouillon=brouillon, etapes=brouillon.get('etapes'))
        return self.garder_brouillon(brouillon, 'tailscale', ETAT_A_FAIRE)

    def installation_demarrage(self, brouillon, demande):
        """{"demarrage": systeme | session | aucun, "veille_desactivee": bool, "retirer"?: bool} : scripts de §22.9
        écrits (jamais exécutés ici) puis, sous Windows et si ≠ aucun, une seule élévation (config.lancer_eleve :
        Installer_demarrage.ps1 avec RunAs, ou Demarrage_session.ps1 sans droits) ; ailleurs, les commandes à lancer à
        la main. « aucun » avec « retirer » vrai (Paramètres, CS129) : Retirer_demarrage.ps1 lancé avec l'élévation
        (tâche, règle du pare-feu et réglages de veille défaits) ; hors Windows, la commande de retrait. Étape faite si
        rien n'était à lancer ou si le script a réussi ; à faire si l'élévation a été refusée (repli proposé)."""
        demarrage = demande.get('demarrage')
        if demarrage not in ('systeme', 'session', 'aucun'):
            raise ErreurHttp(400, traduisible('installation.demarrage_inconnu',
                                              'Démarrage inconnu : « systeme », « session » ou « aucun ».'))
        veille = demande.get('veille_desactivee', False)
        if not isinstance(veille, bool):
            raise ErreurHttp(400, traduisible('installation.veille_booleen',
                                              '« veille_desactivee » : vrai ou faux attendu.'))
        retirer = demande.get('retirer', False)
        if not isinstance(retirer, bool):
            raise ErreurHttp(400, traduisible('installation.retirer_booleen', '« retirer » : vrai ou faux attendu.'))
        retirer = retirer and demarrage == 'aucun'
        brouillon.update(demarrage=demarrage, veille_desactivee=veille)
        mkcert = None
        if brouillon.get('certificat_auto'):
            try:
                mkcert = executable_mkcert()
            except ErreurConfiguration:
                mkcert = None
        dossier = os.path.abspath(self.config.dossier_application)
        scripts = produire_scripts_demarrage(self.config, dossier_prevo=dossier, veille=veille, mkcert=mkcert,
                                             ports=(brouillon['port_http'], brouillon['port_https']),
                                             systeme=self.config.systeme)
        lance, commandes = None, []
        if self.config.systeme.startswith('win'):
            if demarrage == 'systeme':
                lance = self.config.lancer_eleve(scripts['Installer_demarrage.ps1'], True)
            elif demarrage == 'session':
                lance = self.config.lancer_eleve(scripts['Demarrage_session.ps1'], False)
            elif retirer:
                lance = self.config.lancer_eleve(scripts['Retirer_demarrage.ps1'], True)
        elif retirer:
            commandes = (['launchctl unload -w %s' % scripts['pro.prevo.serveur.plist']] if self.config.systeme == 'darwin'
                         else ['sudo systemctl disable --now prevo'])
        elif demarrage != 'aucun':
            if self.config.systeme == 'darwin':
                commandes = ['launchctl load -w %s' % scripts['pro.prevo.serveur.plist']]
            else:
                commandes = commandes_systemd(dossier)
        fait = (demarrage == 'aucun' and lance is None) or bool(commandes) or bool(lance and lance.get('ok'))
        reponse = self.garder_brouillon(brouillon, 'demarrage', ETAT_FAIT if fait else ETAT_A_FAIRE)
        return dict(reponse, scripts=scripts, lance=lance, commandes=commandes)

    def installation_sauvegardes(self, brouillon, demande):
        """{"dossier": chemin | ""} : vide = plus tard ; sinon le dossier existe, s'écrit (fichier témoin) et n'est pas
        dans les données (400 sinon) ; brouillon copie_sauvegardes."""
        dossier = demande.get('dossier', '')
        if not isinstance(dossier, str):
            raise ErreurHttp(400, traduisible('installation.sauvegardes_dossier',
                                              '« dossier » : un chemin (texte) est attendu, vide pour plus tard.'))
        brouillon['copie_sauvegardes'] = verifier_dossier_de_copie(self.config, dossier) if dossier.strip() else ''
        return self.garder_brouillon(brouillon, 'sauvegardes')

    def installation_deplacer(self, brouillon, demande):
        """{"vers": chemin} (défaut C:\\Prevo ; Windows seulement, 400 ailleurs) : deplacer_installation — copie du
        dossier de Prévo entier (données et brouillon compris, .git exclu) vers un dossier nouveau ou vide, chaque
        fichier vérifié, puis relance depuis la nouvelle place (config.relancer) ; l'ancien dossier n'est jamais
        supprimé. Rend {copie, vers, relance}. {"rester": true} (« Rester ici ») : refus mémorisé dans le brouillon
        (deplacement_refuse), l'étape reste à faire et l'écran ne la propose plus."""
        if not self.config.systeme.startswith('win'):
            raise ErreurHttp(400, traduisible('installation.deplacement_windows',
                                              'Le déplacement vers {dossier} n\'existe que sous Windows.',
                                              dossier=DOSSIER_CONSEILLE_WINDOWS))
        if demande.get('rester') is True:
            brouillon['deplacement_refuse'] = True
            return self.garder_brouillon(brouillon, 'deplacer', ETAT_A_FAIRE)
        vers = demande.get('vers', DOSSIER_CONSEILLE_WINDOWS)
        if not isinstance(vers, str) or not vers.strip():
            vers = DOSSIER_CONSEILLE_WINDOWS
        if not os.path.isabs(vers.strip()):
            raise ErreurHttp(400, traduisible('deplacement.chemin_complet',
                                              'Donnez un chemin complet (par exemple {exemple}).',
                                              exemple=DOSSIER_CONSEILLE_WINDOWS))
        brouillon.pop('deplacement_refuse', None)
        self.garder_brouillon(brouillon, 'deplacer')          # noté avant la copie : le brouillon copié le sait
        try:
            resultat = deplacer_installation(self.config, vers.strip(), brouillon)
        except ErreurHttp:
            self.garder_brouillon(brouillon, 'deplacer', ETAT_A_FAIRE)
            raise
        return dict(resultat, etapes=brouillon['etapes'])

    def installation_terminer(self, brouillon, demande):
        """{"base": "vide" | "demo", "langue_defaut": code} (base : défaut vide ; demo seulement sur une base absente au
        départ, 400 sinon : les CSV existants ne sont jamais remplacés ; langue_defaut : une langue déclarée par
        js/i18n/langues.js, 400 sinon, défaut fr, T296). Règles de portée sur le brouillon (400 au message : comptes sans
        responsable, réseau sans https…), jeu de démo écrit s'il est demandé (installer_jeu_de_demo), puis
        prevo.config.json écrit (seulement ici : ecrire_configuration, ou modifier_configuration s'il existe déjà,
        les clés inconnues gardées) ; Solo ⇒ mode_solo dans parametres.csv, base absente au départ ⇒ langue_defaut
        (les autres lignes gardées ; une base présente au départ n'a jamais sa langue changée ici) ; brouillon
        supprimé ; puis le serveur se relance avec la configuration (config.relancer). Rend {configuration, fichier,
        relance, base}."""
        base = demande.get('base', 'vide')
        if base not in BASES_AU_DEPART:
            raise ErreurHttp(400, traduisible('installation.base_inconnue',
                                              'Base de départ inconnue : « vide » ou « demo ».'))
        langue = demande.get('langue_defaut', LANGUE_PAR_DEFAUT)
        declarees = langues_declarees()
        if not isinstance(langue, str) or langue not in declarees:
            raise ErreurHttp(400, traduisible('installation.langue_inconnue',
                                              'Langue de Prévo inconnue : une langue déclarée est attendue '
                                              '({langues}).', langues=declarees))
        base_neuve = not brouillon.get('base_presente', True)
        if base == 'demo' and not base_neuve:
            raise ErreurHttp(400, traduisible('installation.demo_sur_donnees',
                                              'Des fichiers de données sont déjà là : la démonstration ne remplace '
                                              'jamais une base existante. Terminez avec « vide » (vos fichiers sont '
                                              'gardés).'))
        if base == 'demo' or brouillon.get('mode_solo') or base_neuve:
            verifier_ecriture_permise(self.config)          # T185 : tables écrites (lecture seule), avant la config
        reglages = reglages_par_defaut()
        reglages.update({cle: brouillon[cle] for cle in CLES_DU_BROUILLON if cle in brouillon})
        reglages['ecoute'] = ecoute_du_brouillon(brouillon)
        reglages['_https_auto'] = bool(reglages['certificat_auto']) and not reglages['certificat']
        responsable = responsable_actif_existe(self.config)
        if reglages['comptes'] and not responsable:
            raise ErreurHttp(400, traduisible('installation.sans_responsable',
                                              'Aucun compte responsable : créez-le (étape « compte ») avant de '
                                              'terminer.'))
        try:
            verifier_regles_portee(dict(reglages), responsable)
        except ErreurConfiguration as erreur:
            raise ErreurHttp(400, traduisible_de(erreur))
        if reglages['ecoute'] != '127.0.0.1' and reglages['_https_auto'] and not mkcert_disponible():
            raise ErreurHttp(400, traduisible('installation.certificat_auto_sans_mkcert',
                                              'Certificat automatique impossible sans mkcert (outils-tiers/) : '
                                              'Prévo refuserait de démarrer sur le réseau. Faites l\'étape '
                                              '« certificat » autrement.'))
        chemin = self.config.reglages.get('_fichier') or os.path.join(self.config.dossier_application,
                                                                      NOM_FICHIER_CONFIGURATION)
        a_ecrire = {cle: reglages[cle] for cle in CLES_DU_BROUILLON}
        if base == 'demo':
            with VERROU_ECRITURE:                             # avant la configuration : un échec ne laisse rien d'écrit
                installer_jeu_de_demo(self.config, brouillon, origine=self.origine())
        try:
            if os.path.isfile(chemin):
                modifier_configuration(chemin, a_ecrire)
            else:
                ecrire_configuration(chemin, reglages)
        except (OSError, ValueError) as erreur:
            raise ErreurHttp(500, traduisible('installation.configuration_non_ecrite',
                                              'Configuration non écrite ({erreur}) : rien n\'a changé.',
                                              erreur=erreur))
        # Après le jeu de démo (il change solo_technicien_id) : Solo, et la langue de la base neuve (T296).
        a_poser = valeurs_du_mode_solo(brouillon.get('solo_technicien_id', '')) if brouillon.get('mode_solo') else {}
        if base_neuve:
            a_poser['langue_defaut'] = langue
        if a_poser:
            with VERROU_ECRITURE:
                poser_parametres(self.config, a_poser)
        supprimer_brouillon(self.config)
        relance = bool(self.config.relancer(None))
        return {'configuration': a_ecrire, 'fichier': chemin, 'relance': relance, 'base': base}

    # --- Fichiers statiques ------------------------------------------------

    def servir_statique(self, morceaux, entetes=None):
        """Sert un fichier de la liste blanche (index.html, favicon.svg, GUIDE.html, css/, js/, acces/ ;
        tests/fixtures/ avec --servir-tests) et /acces/ca.crt (certificat public de l'autorité, §22.6). Jamais
        donnees/ ni les fichiers cachés. « entetes » : ceux de la porte ; sinon ceux de l'application."""
        if morceaux == ['']:
            morceaux = ['index.html']
        if morceaux[0].lower() == 'donnees':
            raise ErreurHttp(403, traduisible('statique.acces_refuse', 'Accès refusé.'))
        if [morceau.lower() for morceau in morceaux] == CHEMIN_CERTIFICAT_AUTORITE:
            self.servir_certificat_autorite()
            return
        servir_tests = self.config.servir_tests
        # Hors liste blanche : même réponse qu'un fichier absent (on ne dit pas qu'il existe).
        if not chemin_public(morceaux, servir_tests):
            raise ErreurHttp(404, traduisible('statique.introuvable', 'Fichier introuvable.'))
        chemin = chemin_sous(DOSSIER_APPLICATION, *morceaux)
        if not chemin_public(morceaux_resolus(chemin, DOSSIER_APPLICATION), servir_tests):
            raise ErreurHttp(404, traduisible('statique.introuvable', 'Fichier introuvable.'))
        for dossier_interdit in self.config.dossiers_interdits_statique:
            if est_sous_dossier(chemin, dossier_interdit):
                raise ErreurHttp(403, traduisible('statique.acces_refuse', 'Accès refusé.'))
        if not os.path.isfile(chemin):
            raise ErreurHttp(404, traduisible('statique.introuvable', 'Fichier introuvable.'))
        octets = lire_octets(chemin)
        if octets is None:
            raise ErreurHttp(404, traduisible('statique.introuvable', 'Fichier introuvable.'))
        if entetes is None:
            entetes = None if morceaux[0].lower() == 'tests' else self.entetes_securite()
        self.envoyer(200, octets, TYPES_STATIQUES.get(extension(chemin), TYPE_PAR_DEFAUT), entetes)

    def entetes_securite(self):
        """En-têtes des fichiers de l'application (§22.13). Avec --servir-tests, la politique laisse aussi passer les
        faux services des tests sur ce PC (faux prevo.pro, faux fournisseur) : jamais en usage normal."""
        origines = ADRESSE_VERSION_PUBLIEE
        if self.config.servir_tests:
            origines += ' http://127.0.0.1:* http://localhost:*'
        entetes = dict(ENTETES_SECURITE)
        entetes['Content-Security-Policy'] = POLITIQUE_CONTENU % origines
        # HSTS seulement pour un nom déclaré (jamais une adresse IP : un retour en http serait bloqué), sur une
        # requête arrivée en https (jamais par la porte, ni pour le PC servi en http).
        hote = self.hote_de_la_requete()
        if (self.en_https() and hote and not est_une_adresse_ip(hote)
                and hote in self.config.hotes_supplementaires):
            entetes['Strict-Transport-Security'] = 'max-age=%d' % DUREE_HSTS_S
        return entetes

    # --- Envoi des réponses ------------------------------------------------

    def envoyer(self, statut, octets, type_contenu, entetes_supplementaires=None):
        """Envoie une réponse complète. Aucune en-tête CORS, jamais."""
        try:
            self.send_response(statut)
            self.send_header('Content-Type', type_contenu)
            self.send_header('Content-Length', str(len(octets)))
            self.send_header('Cache-Control', 'no-store' if self.est_requete_api() else 'no-cache')
            self.send_header('X-Content-Type-Options', 'nosniff')
            for nom, valeur in (entetes_supplementaires or {}).items():
                self.send_header(nom, valeur)
            if self.close_connection:
                self.send_header('Connection', 'close')     # annoncé : le client ne la réutilise pas
            self.end_headers()
            self.wfile.write(octets)
        except (ConnectionError, socket.timeout):
            pass

    def envoyer_json(self, statut, donnees, entetes_supplementaires=None):
        octets = json.dumps(avec_codes(donnees), ensure_ascii=False).encode('utf-8')     # D157 : codes des messages
        self.envoyer(statut, octets, 'application/json; charset=utf-8', entetes_supplementaires)

    def envoyer_erreur(self, erreur):
        donnees = {'erreur': erreur.message}
        donnees.update(erreur.champs_supplementaires)
        if not getattr(self, 'corps_lu', False) and not getattr(self, 'lecture_commencee', True):
            self.jeter_le_corps()           # refus avant la lecture du corps (hôte, session, X-Prevo…)
        if not getattr(self, 'corps_lu', False):
            self.close_connection = True     # le corps n'a pas (entièrement) été lu
        self.envoyer_json(erreur.statut, donnees, erreur.entetes)

    def jeter_le_corps(self):
        """Refus prononcé avant la lecture du corps : le lit et le jette s'il fait au plus 64 Ko, pour que le navigateur
        reçoive la réponse (sinon « connexion réinitialisée ») ; au-delà, ou sans Content-Length lisible, rien n'est
        lu et la connexion est fermée après la réponse (audit F2)."""
        try:
            longueur = int(self.headers.get('Content-Length', ''))
        except ValueError:
            return
        if 0 <= longueur <= TAILLE_MAX_CORPS_JETE:
            try:
                self.corps_lu = len(self.rfile.read(longueur)) == longueur
            except (OSError, ValueError):
                pass


# ---------------------------------------------------------------------------
# Démarrage
# ---------------------------------------------------------------------------

class ServeurPrevo(http.server.ThreadingHTTPServer):
    """Serveur HTTP multi-connexions (un fil d'exécution par requête)."""

    daemon_threads = True
    # File d'attente des connexions pas encore acceptées. La valeur par défaut de socketserver (5)
    # est trop courte : un navigateur ouvre ~6 connexions d'un coup par page (une par requête en
    # HTTP/1.0), et plusieurs postes s'ajoutent ; au-delà, Windows réinitialise la connexion
    # (ERR_CONNECTION_RESET) ou la retarde d'une seconde ou plus (le ping de détection échoue).
    request_queue_size = 128
    # Sous Windows, SO_REUSEADDR permettrait d'écouter sur un port DÉJÀ utilisé :
    # on le désactive et on demande l'usage exclusif du port.
    allow_reuse_address = (os.name != 'nt')

    def __init__(self, adresse, config, porte=False):
        """« porte » (lot 7, §22.6) : cet écouteur est la porte d'entrée, en http ; un client du réseau n'y reçoit que
        la page de porte, le PC serveur lui-même y reçoit l'application. Sinon : l'application (https avec un
        certificat, http en portée « ce PC »)."""
        self.config = config
        self.porte = porte
        self.contexte_ssl = None if porte else config.contexte_ssl
        super().__init__(adresse, GestionnaireRequetes)

    def get_request(self):
        """https (lot 4) : la connexion acceptée est enveloppée en TLS ; la poignée de main est faite
        plus tard, dans le fil de la requête (GestionnaireRequetes.setup)."""
        connexion, adresse = self.socket.accept()
        if self.contexte_ssl is not None:
            connexion = self.contexte_ssl.wrap_socket(connexion, server_side=True, do_handshake_on_connect=False)
        return connexion, adresse

    def handle_error(self, request, client_address):
        # Client parti, ou http simple envoyé au serveur https : rien à signaler sur la console.
        if isinstance(sys.exc_info()[1], (ssl.SSLError, ConnectionError, socket.timeout)):
            return
        super().handle_error(request, client_address)

    def server_bind(self):
        if os.name == 'nt' and hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        # On n'appelle pas HTTPServer.server_bind, qui interroge le DNS (lent sur certains PC).
        socketserver.TCPServer.server_bind(self)
        self.server_name = 'localhost'
        self.server_port = self.server_address[1]


def port_pris_ailleurs(port):
    """Vrai si un autre programme écoute déjà sur ce port, toutes interfaces : sous Windows, écouter sur 127.0.0.1
    réussit même dans ce cas (adresse plus précise), et Prévo partagerait le port sans le dire (lot 7, §22.1)."""
    sonde = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if os.name == 'nt' and hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            sonde.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        sonde.bind(('0.0.0.0', port))
        return False
    except OSError:
        return True
    finally:
        sonde.close()


def ouvrir_ecouteur(port_demande, config, porte=False):
    """Ouvre un écouteur sur le premier port libre à partir de port_demande (jusqu'à +20) ; rend (serveur, port)."""
    derniere_erreur = None
    port_maximum = min(port_demande + NOMBRE_PORTS_SUPPLEMENTAIRES, 65535)
    for port in range(port_demande, port_maximum + 1):
        try:
            if config.ecoute != '0.0.0.0' and port_pris_ailleurs(port):
                raise OSError('port %d déjà utilisé par un autre programme' % port)
            return ServeurPrevo((config.ecoute, port), config, porte), port
        except OSError as erreur:
            derniere_erreur = erreur
    raise SystemExit('Impossible d\'ouvrir un port entre %d et %d (%s).'
                     % (port_demande, port_maximum, derniere_erreur))


def demarrer_serveur(port_demande, config):
    """Écouteurs du serveur (§22.1, §22.6). Portée « ce PC » (127.0.0.1) : un seul, sur port_demande, l'application
    en http (ou en https avec un certificat donné, lot 4). Hors de « ce PC » : la porte en http sur port_demande et
    l'application en https sur port_https (config.contexte_ssl est alors obligatoire : main l'a vérifié). Rend (liste
    des serveurs, le dernier à servir dans le fil principal ; port de la porte ou de l'application)."""
    if config.ecoute == '127.0.0.1':
        serveur, port = ouvrir_ecouteur(port_demande, config)
        return [serveur], port
    if config.contexte_ssl is None:
        raise SystemExit('Prévo n\'écoute pas sur le réseau sans https (certificat absent).')
    porte, port = ouvrir_ecouteur(port_demande, config, porte=True)
    try:
        application, config.port_https = ouvrir_ecouteur(config.reglages['port_https'], config)
    except SystemExit:
        porte.server_close()
        raise
    config.porte = True
    return [porte, application], port


def afficher_accueil(config, port_demande, avertissements=()):
    afficher('%s %s - serveur local de GMAO' % (NOM_APPLICATION, VERSION_APPLICATION))
    if config.port != port_demande:
        afficher('  Le port %d est occupé : port %d utilisé.' % (port_demande, config.port))
    afficher('  Sur ce PC        : %s' % config.adresse_locale())
    adresses = [] if config.ce_pc_seulement else config.adresses_reseau()
    if adresses:
        for adresse in adresses:
            afficher('  Sur le réseau    : %s   (téléphones, tablettes)' % adresse)
    elif not config.ce_pc_seulement:
        afficher('  Sur le réseau    : aucune adresse trouvée (PC non connecté ?)')
    afficher('  Données          : %s' % config.dossier_donnees)
    if not config.reglages.get('_present'):
        afficher('  Installation     : pas encore faite ; l\'assistant est sur %s%s (sur ce PC seulement).'
                 % (config.adresse_locale(), ROUTE_INSTALLATION))
    elif config.reglages.get('comptes') and aucun_responsable_sur(config):
        afficher('  Installation     : aucun compte responsable ; créez-le avec l\'assistant sur %s%s (sur ce PC '
                 'seulement).' % (config.adresse_locale(), ROUTE_INSTALLATION))
    if config.ecoute == '127.0.0.1':
        afficher('  Écoute           : ce PC seulement (127.0.0.1) ; les autres appareils ne joignent pas Prévo.')
    else:
        afficher('  Écoute           : le réseau (%s), comptes exigés.' % config.ecoute)
    if config.porte:
        # Jamais l'adresse https elle-même (CS137) : les téléphones passent par la porte, qui les y conduit.
        afficher('  Application      : en https sur le port %d ; l\'adresse ci-dessus (la porte) y conduit les '
                 'téléphones%s.' % (config.port_https, ' avec le certificat fabriqué par Prévo'
                                     if config.reglages.get('_https_auto') else ''))
    afficher('  Assistant IA     : %s' % resume_ia(config))
    if dossier_copie_externe(config):
        afficher('  Copie externe    : %s (chaque nuit, %d copies gardées)'
                 % (dossier_copie_externe(config), COPIES_EXTERNES_GARDEES))
    if config.tailscale is not None:
        afficher('  Tailscale        : %s' % resume_tailscale(config.tailscale))
    for avertissement in avertissements:
        afficher('  ' + avertissement)
    afficher('  Ctrl+C pour arrêter.')


def lire_arguments(arguments=None):
    analyseur = argparse.ArgumentParser(
        description='Serveur local de la GMAO Prévo. Sert index.html, favicon.svg, '
                    'GUIDE.html, css/, js/ et acces/ (la porte d\'entrée) ; tout autre fichier répond 404.')
    analyseur.add_argument('--port', type=int, default=None,
                           help='port d\'écoute (défaut 8080 ; le suivant si occupé) ; sur le réseau, celui de la '
                                'porte d\'entrée, l\'application étant en https sur « port_https » (8443)')
    analyseur.add_argument('--donnees', default=os.path.join(DOSSIER_APPLICATION, 'donnees'),
                           help='dossier des données (défaut : donnees/ à côté de serveur.py)')
    analyseur.add_argument('--sans-navigateur', action='store_true',
                           help='ne pas ouvrir le navigateur au démarrage')
    analyseur.add_argument('--hote', action='append', default=[],
                           help='nom d\'hôte supplémentaire accepté (répétable)')
    analyseur.add_argument('--certificat', metavar='FICHIER',
                           help='https en option : certificat du serveur (PEM), avec --cle')
    analyseur.add_argument('--cle', metavar='FICHIER',
                           help='https en option : clé privée du certificat (PEM), avec --certificat')
    analyseur.add_argument('--ecoute', choices=ECOUTES,
                           help='adresse d\'écoute : 127.0.0.1 (défaut, ce PC seulement) ou 0.0.0.0 (le réseau, '
                                'comptes et https exigés)')
    analyseur.add_argument('--ia-url', metavar='URL',
                           help='adresse du service d\'IA de tous les postes (défaut http://localhost:11434) ; '
                                'la clé, elle, vient de « ia_cle » ou de la variable PREVO_IA_CLE, jamais d\'une option')
    analyseur.add_argument('--ia-fournisseur', choices=tuple(LIBELLES_FOURNISSEURS_IA),
                           help='type du service d\'IA : ollama (défaut) ou openai (API compatible OpenAI)')
    analyseur.add_argument('--ia-en-ligne', action='store_true',
                           help='autoriser un service d\'IA en ligne (les textes envoyés quittent l\'atelier)')
    analyseur.add_argument('--config', metavar='FICHIER',
                           help='fichier de configuration (défaut : %s à côté de serveur.py)' % NOM_FICHIER_CONFIGURATION)
    analyseur.add_argument('--aide', action='store_true',
                           help='afficher chaque clé de la configuration avec son aide, puis quitter')
    analyseur.add_argument('--journal', action='store_true',
                           help='écrire aussi la console dans donnees/journal-serveur.log (automatique sans console)')
    analyseur.add_argument('--reinitialiser', metavar='IDENTIFIANT',
                           help='donner un mot de passe provisoire à un compte (affiché une fois), puis quitter')
    analyseur.add_argument('--servir-tests', action='store_true',
                           help='servir aussi tests/fixtures/ (pages des tests automatiques ; '
                                'inutile en usage normal)')
    options = analyseur.parse_args(arguments)
    if options.port is not None and not 1 <= options.port <= 65535:
        analyseur.error('le port doit être compris entre 1 et 65535')
    if bool(options.certificat) != bool(options.cle):
        analyseur.error('--certificat et --cle vont ensemble : donnez les deux fichiers PEM '
                        '(certificat et clé privée) pour passer en https')
    return options


def reglages_du_lancement(options):
    """Réglages effectifs : défauts < fichier de configuration < ligne de commande (§22.2)."""
    chemin = options.config or os.path.join(DOSSIER_APPLICATION, NOM_FICHIER_CONFIGURATION)
    reglages = lire_configuration(chemin)
    if options.port is not None:
        reglages['port_http'] = options.port
    if options.ecoute:
        reglages['ecoute'] = options.ecoute
    if options.hote:
        reglages['noms'] = reglages['noms'] + [hote.lower().strip() for hote in options.hote]
    if options.certificat:
        reglages['certificat'], reglages['cle'] = options.certificat, options.cle
    if options.ia_url is not None:
        reglages['ia_url'] = options.ia_url.strip()
    if options.ia_fournisseur:
        reglages['ia_fournisseur'] = options.ia_fournisseur
    if options.ia_en_ligne:
        reglages['ia_en_ligne'] = True
    # Clé du fournisseur (audit M3) : la variable d'environnement passe avant le fichier ; gardée à part
    # (« _ia_cle ») pour qu'une réécriture du fichier de configuration ne la recopie jamais.
    reglages['_ia_cle'] = os.environ.get(VARIABLE_CLE_IA, '').strip() or reglages['ia_cle']
    # Certificat fabriqué par Prévo (§22.6) : sans certificat donné, « certificat_auto » vaut https pour les règles
    # de portée ; main le fabrique ensuite (certificat_du_serveur), et refuse de démarrer si mkcert fait défaut.
    reglages['_https_auto'] = bool(reglages.get('certificat_auto')) and not reglages['certificat']
    return reglages


def adresse_de_demarrage(config):
    """Adresse ouverte dans le navigateur au démarrage : l'application, ou l'assistant d'installation (#/installation)
    tant que prevo.config.json n'existe pas (§22.10 ; --sans-navigateur respecté par main)."""
    adresse = config.adresse_locale()
    return adresse if config.reglages.get('_present') else adresse + ROUTE_INSTALLATION


def reinitialiser_en_ligne_de_commande(config, identifiant):
    """serveur.py --reinitialiser IDENTIFIANT : sur le PC serveur, qui a la main sur le PC a la main sur Prévo."""
    try:
        provisoire = reinitialiser_compte(config, identifiant)
    except (ErreurCompte, OSError, ValueError) as erreur:
        afficher('Réinitialisation impossible : %s' % erreur)
        sys.exit(1)
    compte = trouver_compte(lire_comptes(config), identifiant)        # T301 : l'identifiant réel du compte
    afficher('Mot de passe provisoire de « %s » : %s' % (compte['identifiant'] if compte else identifiant, provisoire))
    afficher('Notez-le : il ne sera plus affiché. Il faudra le changer à la première connexion.')


def main(arguments=None):
    global JOURNAL_SERVEUR
    preparer_console()
    options = lire_arguments(arguments)
    if options.aide:
        afficher(texte_aide_configuration())
        return
    try:
        reglages = reglages_du_lancement(options)
        config = Configuration(options.donnees, reglages['noms'], options.servir_tests)
        config.reglages = reglages
        creer_dossiers(config)
        if options.journal or sys.stdout is None:
            JOURNAL_SERVEUR = JournalServeur(os.path.join(config.dossier_donnees, 'journal-serveur.log'))
        if options.reinitialiser:
            reinitialiser_en_ligne_de_commande(config, options.reinitialiser)
            return
        avertissements = verifier_regles_portee(reglages, il_existe_un_responsable(config))
        config.ecoute = reglages['ecoute']
        # Hors de « ce PC » : certificat de la configuration, sinon fabriqué par mkcert ; refus (code 2) sans lui.
        certificat, cle = certificat_du_serveur(config, reglages)
    except ErreurConfiguration as erreur:
        afficher('Démarrage refusé. %s' % erreur)
        sys.exit(CODE_SORTIE_REGLES)
    if certificat:
        config.contexte_ssl = creer_contexte_ssl(certificat, cle)
    # T185 (D168) : les données au format courant, après la sauvegarde « avant-format-vN », AVANT d'ouvrir les
    # écouteurs (aucune connexion ne voit une base à moitié passée) ; avec ou sans configuration (assistant) ; données
    # plus récentes : lecture seule (D169). T187 (D170) : la sauvegarde « avant-mise-a-jour » d'abord (nouvelle
    # version de Prévo), la sauvegarde du jour ensuite (rotation à 30 jours).
    preparer_donnees_au_demarrage(config)
    serveurs, config.port = demarrer_serveur(reglages['port_http'], config)
    if tailscale_attendu(reglages):
        detecter_tailscale_pour(config)         # §22.8 : commandes locales, une fois au démarrage (ligne de console)
    afficher_accueil(config, reglages['port_http'], avertissements)
    lancer_copie_externe(config)        # D133 : copie externe au démarrage, dans son propre fil
    if not options.sans_navigateur:
        webbrowser.open(adresse_de_demarrage(config))
    # Deux écouteurs (§22.6) : la porte tourne dans son propre fil, l'application dans celui-ci (Ctrl+C).
    for serveur in serveurs[:-1]:
        threading.Thread(target=serveur.serve_forever, name='porte', daemon=True).start()
    try:
        serveurs[-1].serve_forever()
    except KeyboardInterrupt:
        afficher('Serveur arrêté.')
    finally:
        for serveur in serveurs:
            serveur.server_close()


if __name__ == '__main__':
    main()
