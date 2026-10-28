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
VERSION_APPLICATION = '1.2.0'
VERSION_API = 1

PORT_PAR_DEFAUT = 8080
NOMBRE_PORTS_SUPPLEMENTAIRES = 20          # 8080 occupé → 8081, … jusqu'à 8100
TAILLE_MAX_CORPS = 10 * 1024 * 1024        # 10 Mo
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
MOTIF_NOM_DOCUMENT = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', re.ASCII)
# Nom d'une sauvegarde (mêmes règles que js/stockage-dossier.js) :
#   AAAA-MM-JJ                               quotidienne
#   AAAA-MM-JJ_HHMMSS                        manuelle
#   AAAA-MM-JJ_HHMMSS_avant-restauration     copie de sécurité faite avant une restauration
#   AAAA-MM-JJ_HHMMSS_avant-format-v<N>      faite juste avant le passage au format N des fichiers
#   AAAA-MM-JJ_HHMMSS_avant-import           faite juste avant un import de données (lot 5)
MOTIF_NOM_SAUVEGARDE = re.compile(
    r'[0-9]{4}-[0-9]{2}-[0-9]{2}(_[0-9]{6}(_avant-restauration|_avant-format-v[0-9]+|_avant-import)?)?', re.ASCII)
# Motifs acceptés par POST /api/sauvegarde {"motif": "…"} : liste FERMÉE (tout autre motif → 400).
# Le motif devient la fin du nom de la sauvegarde (« _avant-format-v2 »). Règle générale :
# « avant-format-v<N> » ; on n'ajoute ici que les versions que Prévo sait vraiment produire.
MOTIFS_SAUVEGARDE = ('avant-format-v2', 'avant-format-v3', 'avant-import')

# Types MIME des documents acceptés (l'extension décide du type, jamais le contenu).
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
    'doc': 'application/msword',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'xls': 'application/vnd.ms-excel',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'odt': 'application/vnd.oasis.opendocument.text',
    'ods': 'application/vnd.oasis.opendocument.spreadsheet',
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


MESSAGE_FICHIER_VERROUILLE = (
    'Le fichier est verrouillé par un autre programme (probablement Excel) : '
    'fermez le fichier dans Excel puis réessayez.')


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
PAGE_PORTE = os.path.join(DOSSIER_APPLICATION, 'acces', 'porte.html')
ATTRIBUT_PORT_HTTPS = 'data-port-https=""'
CHEMIN_CERTIFICAT_AUTORITE = ['acces', 'ca.crt']
TYPE_CERTIFICAT_AUTORITE = 'application/x-x509-ca-cert'
NOM_FICHIER_CERTIFICAT_AUTORITE = 'prevo-ca.crt'
# La politique de la porte n'autorise au dehors que l'origine https du même hôte (le ping de porte.js).
POLITIQUE_PORTE = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                   "connect-src 'self' %s; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'")
MESSAGE_SANS_AUTORITE = ('Aucune autorité locale sur ce serveur : le certificat a été fourni par votre informaticien, '
                         'demandez-lui comment le faire reconnaître par le téléphone.')

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
    ('quota_documents_mo', 'entier', 2048, "Place maximale des documents joints, en mégaoctets."),
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
    raise ErreurConfiguration('Configuration : la valeur de « %s » est invalide (%r).' % (cle, valeur))


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


def ecrire_configuration(chemin, reglages):
    """Écrit le fichier de configuration (atomique), avec un commentaire d'en-tête « _aide »."""
    contenu = {'_aide': 'Configuration de Prévo. Chaque clé est décrite par « serveur.py --aide ». '
                        'Le CDC et docs/ARCHITECTURE.md §22 en donnent les règles.'}
    for cle, _, _, _ in CLES_CONFIGURATION:
        contenu[cle] = reglages.get(cle)
    ecrire_atomique(chemin, (json.dumps(contenu, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


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
        raise ErreurConfiguration('Certificat et clé vont ensemble : donnez les deux fichiers PEM, ou aucun.')
    if reglages['ecoute'] != '127.0.0.1':
        if not reglages['comptes']:
            raise ErreurConfiguration(
                'Prévo refuse d\'écouter sur le réseau sans mot de passe. Activez les comptes (« comptes »: true) '
                'ou revenez à « ecoute »: "127.0.0.1" ; l\'assistant d\'installation fait les deux (ouvrez Prévo sur ce PC).')
        if not https and not reglages['mandataire']:
            raise ErreurConfiguration(
                'Prévo refuse d\'écouter sur le réseau sans https. Donnez un certificat (« certificat » et « cle »), '
                'laissez Prévo fabriquer le sien (« certificat_auto ») ou placez-le derrière un mandataire ; '
                'l\'assistant d\'installation le fait pour vous.')
    if reglages['mandataire'] and not reglages['comptes']:
        raise ErreurConfiguration(
            'Derrière un mandataire, les comptes sont obligatoires (« comptes »: true) : le mandataire rend Prévo '
            'joignable au-delà de ce PC.')
    if reglages['comptes'] and not responsable_existe and reglages['ecoute'] != '127.0.0.1':
        reglages['ecoute'] = '127.0.0.1'
        avertissements.append('Aucun compte responsable : Prévo n\'écoute que sur ce PC tant que l\'installation '
                              'n\'est pas terminée.')
    for cle in reglages.get('_inconnues', []):
        avertissements.append('Configuration : clé inconnue « %s » ignorée.' % cle)
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
FICHIERS_ACCES_NON_SAUVEGARDES = ('sessions.json',)     # une session ne se restaure jamais
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
        raise ErreurCompte('Algorithme de mot de passe inconnu : %s.' % algo)
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
        raise ErreurCompte('Le mot de passe doit faire au moins %d caractères ; une phrase de quelques mots est le '
                           'plus simple à retenir.' % LONGUEUR_MIN_MOT_DE_PASSE)
    if len(mot_de_passe) > LONGUEUR_MAX_MOT_DE_PASSE:
        raise ErreurCompte('Le mot de passe fait plus de %d caractères.' % LONGUEUR_MAX_MOT_DE_PASSE)


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


def identifiant_depuis(prenom, nom, pris):
    """« Élodie Le Gall » → « elodie.le-gall » ; « .2 », « .3 »… si l'identifiant est déjà pris."""
    def morceau(texte):
        texte = re.sub(r'[^a-z0-9]+', '-', sans_accents(texte).lower()).strip('-')
        return texte or 'compte'
    base = morceau(prenom) + '.' + morceau(nom) if nom.strip() else morceau(prenom)
    candidat, numero = base, 2
    while candidat in pris:
        candidat, numero = '%s.%d' % (base, numero), numero + 1
    return candidat


def trouver_compte(comptes, identifiant):
    identifiant = (identifiant or '').strip().lower()
    return next((c for c in comptes if c['identifiant'] == identifiant), None)


def creer_compte(config, prenom, nom, role, mot_de_passe, technicien_id='', a_changer=False, identifiant=None,
                 origine=('', '', '')):
    """Crée un compte (rôle, technicien lié pour un technicien) ; rend le compte créé (sans son empreinte).
    origine : (adresse, agent, Tailscale) de la ligne du journal (T152 : la requête du responsable), vide sinon."""
    prenom, nom = (prenom or '').strip(), (nom or '').strip()
    if not prenom:
        raise ErreurCompte('Le prénom est obligatoire.')
    if role not in ROLES_COMPTES:
        raise ErreurCompte('Rôle inconnu : %s.' % role)
    if role == 'technicien' and not technicien_id:
        raise ErreurCompte('Un compte de technicien est lié à un technicien de l\'équipe.')
    verifier_mot_de_passe_choisi(mot_de_passe)
    with VERROU_ACCES:
        comptes = lire_comptes(config)
        pris = {c['identifiant'] for c in comptes}
        if identifiant:
            identifiant = identifiant.strip().lower()
            if identifiant in pris:
                raise ErreurCompte('L\'identifiant « %s » est déjà pris.' % identifiant)
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
            raise ErreurCompte('Compte introuvable : %s.' % identifiant)
        compte['algo'], compte['sel'], compte['empreinte'] = hacher_mot_de_passe(nouveau)
        compte['a_changer'] = bool(a_changer)
        compte['modifie_le'] = compte['mot_de_passe_le'] = maintenant_iso(config)
        ecrire_comptes(config, comptes)
    fermer_sessions_apres_changement(config, compte['identifiant'])
    ecrire_journal_acces(config, compte['identifiant'], origine[0], origine[1], journal, origine[2])


def reinitialiser_compte(config, identifiant, origine=('', '', '')):
    """Mot de passe provisoire (16 caractères, à changer à la première connexion) ; rendu une seule fois."""
    if not os.path.isfile(chemin_comptes(config)):
        raise ErreurCompte('Aucun compte dans %s : rien à réinitialiser. Terminez d\'abord l\'installation.'
                           % dossier_acces(config))
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
            raise ErreurCompte('Compte introuvable : %s.' % identifiant)
        for cle, valeur in champs.items():
            if cle not in permis:
                raise ErreurCompte('Champ non modifiable : %s.' % cle)
            if cle == 'role' and valeur not in ROLES_COMPTES:
                raise ErreurCompte('Rôle inconnu : %s.' % valeur)
            compte[cle] = bool(valeur) if cle == 'actif' else valeur
        if compte['role'] == 'technicien' and not compte.get('technicien_id'):
            raise ErreurCompte('Un compte de technicien est lié à un technicien de l\'équipe.')
        if not any(c['role'] == 'responsable' and c.get('actif') for c in comptes):
            raise ErreurCompte('Il faut garder au moins un compte responsable actif.')
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
MESSAGE_CONNEXION_REFUSEE = 'Identifiant ou mot de passe incorrect.'
MESSAGE_SESSION_ABSENTE = 'Connexion nécessaire : votre session est absente ou a expiré.'
MESSAGE_MOT_DE_PASSE_PROVISOIRE = 'Mot de passe provisoire : choisissez votre mot de passe d\'abord.'
MESSAGE_ACTUEL_FAUX = 'Mot de passe actuel incorrect.'
MESSAGE_SANS_COMPTES = ('Les comptes ne sont pas activés sur ce serveur (portée « ce PC ») : aucune connexion '
                        'n\'est nécessaire.')
MESSAGE_COMPTES_ILLISIBLES = ('Fichier des comptes illisible (donnees/acces/comptes.json) : remettez-le depuis une '
                              'sauvegarde.')
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
    identifiant = (identifiant or '').strip().lower()
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
MESSAGE_INVITATION_REFUSEE = 'Invitation inconnue, expirée ou révoquée : demandez-en une nouvelle au responsable.'
MESSAGE_ENROLEMENT_DESACTIVE = ('Enrôlement d\'appareils désactivé sur ce serveur (demandeurs_avec_compte) : chaque '
                                'demandeur se connecte avec son compte.')
MESSAGE_APPAREIL_REFUSE = ('Cet appareil n\'est plus autorisé (révoqué, expiré ou enrôlement désactivé) : demandez '
                           'une nouvelle invitation au responsable.')
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
        raise ErreurHttp(400, '« heures » : un entier de %d à %d est attendu.'
                         % (INVITATION_HEURES_MIN, INVITATION_HEURES_MAX))
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
        raise ErreurHttp(400, 'Votre nom est attendu (%d caractères au plus).' % LONGUEUR_MAX_NOM_DEMANDEUR)
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
            raise ErreurHttp(404, 'Introuvable : %s.' % str(identifiant)[:40])
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
    erreur = ErreurHttp(429, 'Trop d\'essais : la connexion est bloquée pour cet identifiant. Réessayez dans %d min.'
                        % -(-secondes // 60), attente_secondes=secondes)
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
    cle = (identifiant or '').strip().lower()[:LONGUEUR_MAX_IDENTIFIANT]
    echecs = config.echecs
    if echecs.adresse_ralentie(adresse, maintenant_s(config)):
        config.dormir(ATTENTE_ADRESSE_S)
    compte = trouver_compte(comptes_du_serveur(config), cle)
    qui = compte['identifiant'] if compte is not None else QUI_INCONNU
    reste = echecs.reserver(cle, maintenant_s(config))
    if reste:
        ecrire_journal_acces(config, qui, adresse, agent, 'bloque', tailscale)
        raise erreur_blocage(reste)
    if compte is not None and compte.get('actif'):
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
        raise ErreurConfiguration('Outil introuvable : %s.' % chemin)
    obtenue = empreinte_fichier(chemin)
    if not hmac.compare_digest(obtenue, (attendue or '').lower()):
        raise ErreurConfiguration('Empreinte inattendue pour %s : le fichier a été modifié ou n\'est pas celui livré '
                                  'avec Prévo. Il n\'a pas été exécuté.' % os.path.basename(chemin))


def trouver_mkcert(empreintes=None, dossier=None, nom=None):
    """Chemin de mkcert, empreinte vérifiée : outils-tiers/<nom> (livré dans le zip). ErreurConfiguration sinon."""
    empreintes = empreintes or lire_empreintes_tiers()
    nom = nom or nom_binaire_mkcert(empreintes['mkcert']['version'])
    fiche = empreintes['mkcert']['fichiers'].get(nom)
    if fiche is None:
        raise ErreurConfiguration('Aucun mkcert prévu pour ce système (%s).' % nom)
    chemin = os.path.join(dossier or DOSSIER_OUTILS_TIERS, nom)
    verifier_empreinte(chemin, fiche['sha256'])
    return chemin


def telecharger_mkcert(empreintes=None, dossier=None, nom=None, adresse=None):
    """Téléchargement de secours depuis la page des releases ; l'empreinte est vérifiée avant de garder le fichier."""
    empreintes = empreintes or lire_empreintes_tiers()
    nom = nom or nom_binaire_mkcert(empreintes['mkcert']['version'])
    fiche = empreintes['mkcert']['fichiers'].get(nom)
    if fiche is None:
        raise ErreurConfiguration('Aucun mkcert prévu pour ce système (%s).' % nom)
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
        raise ErreurConfiguration('Téléchargement de mkcert impossible (%s) : vérifiez la connexion à Internet, ou '
                                  'utilisez le zip de Prévo qui le contient.' % erreur)
    finally:
        if os.path.exists(temporaire):
            os.remove(temporaire)
    if not nom.endswith('.exe'):
        os.chmod(cible, 0o755)
    return cible


def dossier_autorite(config):
    return os.path.join(dossier_acces(config), 'autorite')


def noms_du_certificat(config, adresses=None):
    """Noms couverts : adresses IP du PC, <nom>.local, <nom>, localhost, 127.0.0.1, puis les noms acceptés."""
    noms = list(adresses if adresses is not None else adresses_ip_reseau())
    noms += [config.nom_pc + '.local', config.nom_pc, 'localhost', '127.0.0.1']
    noms += list(config.reglages.get('noms', []))
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
        raise ErreurConfiguration('mkcert n\'a pas pu être lancé (%s).' % erreur)
    sortie = (resultat.stdout + resultat.stderr).decode('utf-8', 'replace')
    if resultat.returncode != 0:
        raise ErreurConfiguration('mkcert a échoué : %s' % sortie.strip()[-400:])
    return sortie


def preparer_certificat_local(config, executable, adresses=None, forcer=False):
    """Certificat de l'atelier dans donnees/acces/ (certificat.pem, cle.pem, certificat.json) ; refait si les noms
    ont changé (nouvelle adresse du PC, nouveau nom accepté). L'autorité reste dans donnees/acces/autorite/ ; sa clé
    (rootCA-key.pem) n'est jamais lue ni copiée par Prévo. Rend (certificat, clé, noms)."""
    acces = dossier_acces(config)
    autorite = dossier_autorite(config)
    os.makedirs(autorite, exist_ok=True)
    certificat = os.path.join(acces, 'certificat.pem')
    cle = os.path.join(acces, 'cle.pem')
    fiche = os.path.join(acces, 'certificat.json')
    noms = noms_du_certificat(config, adresses)
    if not forcer and os.path.isfile(certificat) and os.path.isfile(cle) and os.path.isfile(fiche):
        try:
            with open(fiche, 'rb') as lecture:
                if json.loads(lecture.read().decode('utf-8')).get('noms') == noms:
                    return certificat, cle, noms
        except ValueError:
            pass
    lancer_mkcert(executable, ['-cert-file', certificat, '-key-file', cle] + noms, autorite)
    if not (os.path.isfile(certificat) and os.path.isfile(cle)):
        raise ErreurConfiguration('mkcert n\'a pas produit le certificat attendu.')
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
        certificat, cle, _ = preparer_certificat_local(config, mkcert or trouver_mkcert())
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
        # Lot 7 (D133, §22.11) : jour de la dernière copie externe lancée par une écriture après 2 h du matin, et fil
        # de la dernière copie lancée (les tests l'attendent).
        self.copie_externe_jour = None
        self.fil_copie_externe = None
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

    def adresses_reseau(self):
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
MESSAGE_DISTANT_REFUSE = 'Les fournisseurs d\'IA en ligne ne sont pas autorisés sur le PC serveur.'
MESSAGE_REGLE_SUR_LE_SERVEUR = ('Demande refusée : seuls « chemin », « methode » et « corps » sont acceptés ; '
                                'l\'adresse et la clé du fournisseur sont réglées sur le PC serveur.')
LIBELLES_FOURNISSEURS_IA = {'ollama': 'Ollama', 'openai': 'API compatible OpenAI'}


def adresse_fournisseur(url):
    """Adresse de base du fournisseur, contrôlée : http ou https, un hôte, ni identifiant, ni
    paramètres, ni fragment, ni espace ou caractère de contrôle. ErreurHttp(400) sinon (le message
    ne reprend jamais l'adresse)."""
    if not isinstance(url, str) or not url.strip():
        raise ErreurHttp(400, 'Adresse du fournisseur d\'IA manquante.')
    texte = url.strip()
    if any(caractere.isspace() or ord(caractere) < 0x20 or ord(caractere) == 0x7f for caractere in texte):
        raise ErreurHttp(400, 'Adresse du fournisseur d\'IA invalide (espace ou caractère de contrôle).')
    try:
        morceaux = urlsplit(texte)
        morceaux.port                               # lève ValueError si le port est illisible
    except ValueError:
        raise ErreurHttp(400, 'Adresse du fournisseur d\'IA invalide.')
    if morceaux.scheme not in ('http', 'https') or not morceaux.hostname:
        raise ErreurHttp(400, 'Adresse du fournisseur d\'IA invalide (http:// ou https:// attendu).')
    if '@' in morceaux.netloc or morceaux.query or morceaux.fragment or '?' in texte or '#' in texte:
        raise ErreurHttp(400, 'Adresse du fournisseur d\'IA invalide (ni identifiant, ni paramètres).')
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
        raise ErreurHttp(400, 'Demande illisible (JSON attendu).')
    if not isinstance(demande, dict):
        raise ErreurHttp(400, 'Demande illisible (objet JSON attendu).')
    if any(nom not in CLES_DEMANDE_IA for nom in demande):
        raise ErreurHttp(400, MESSAGE_REGLE_SUR_LE_SERVEUR)
    chemin = demande.get('chemin')
    if chemin not in CHEMINS_IA:
        raise ErreurHttp(400, 'Chemin non autorisé pour l\'IA (' + ', '.join(CHEMINS_IA) + ').')
    methode = demande.get('methode', 'POST')
    if methode not in ('GET', 'POST'):
        raise ErreurHttp(400, 'Méthode non autorisée pour l\'IA (GET ou POST).')
    entetes = {'Accept': 'application/json'}
    octets = None
    if methode == 'POST':
        octets = json.dumps(demande.get('corps') or {}, ensure_ascii=False).encode('utf-8')
        entetes['Content-Type'] = 'application/json'
    cle = cle_ia(reglages)
    if cle:
        if not cle_ia_lisible(cle):
            raise ErreurHttp(400, 'Clé du fournisseur d\'IA illisible (réglage du PC serveur : caractères ASCII seulement).')
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
            raise ErreurHttp(504, 'Le fournisseur d\'IA n\'a pas répondu dans le délai.')
        raise ErreurHttp(502, 'Fournisseur d\'IA injoignable.')
    except (socket.timeout, TimeoutError):
        raise ErreurHttp(504, 'Le fournisseur d\'IA n\'a pas répondu dans le délai.')
    except OSError:
        raise ErreurHttp(502, 'Fournisseur d\'IA injoignable.')
    except http.client.InvalidURL:
        raise ErreurHttp(400, 'Adresse du fournisseur d\'IA invalide.')
    except http.client.HTTPException:                   # IncompleteRead, BadStatusLine, LineTooLong…
        raise ErreurHttp(502, 'Réponse du fournisseur d\'IA incomplète ou illisible.')
    except ValueError:          # adresse que le réseau ne sait pas écrire (nom vide « a..b », non ASCII…)
        raise ErreurHttp(400, 'Adresse du fournisseur d\'IA invalide.')
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
        raise SystemExit('Certificat ou clé illisible (%s) : vérifiez les deux fichiers PEM '
                         'passés à --certificat et --cle.' % erreur)
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
MESSAGE_HOTE_ORIGINE_REFUSE = ('Nom d\'hôte d\'origine refusé (X-Forwarded-Host) : ajoutez-le aux noms acceptés '
                               '(« noms » de la configuration).')


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
        raise ErreurHttp(400, 'Chemin refusé.')
    if '\\' in chemin_brut or '%5c' in chemin_brut.lower():
        raise ErreurHttp(400, 'Chemin refusé.')
    chemin_decode = unquote(chemin_brut)
    # « % » restant = double encodage (« %252e ») : refusé par prudence.
    if '\\' in chemin_decode or '%' in chemin_decode:
        raise ErreurHttp(400, 'Chemin refusé.')
    for chemin in (chemin_brut, chemin_decode):
        morceaux = chemin[1:].split('/')
        if morceaux == ['']:
            continue                     # « / » tout seul : la page d'accueil
        for morceau in morceaux:
            if morceau == '' or segment_dangereux(morceau):
                raise ErreurHttp(400, 'Chemin refusé.')
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
        raise ErreurHttp(400, 'Chemin refusé.')
    # Après résolution (raccourcis Windows « GIT~1 », liens…), aucun morceau caché.
    try:
        relatif = os.path.relpath(chemin, base)
    except ValueError:                  # « nul », « con »… : périphériques Windows, autre « lecteur »
        raise ErreurHttp(400, 'Chemin refusé.')
    for morceau in relatif.split(os.sep):
        if morceau.startswith('.'):
            raise ErreurHttp(400, 'Chemin refusé.')
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
    (sauf porte.html, toujours rendue avec son port https), le favicon et les polices de la charte. Rien d'autre : ni
    index.html, ni js/, ni css/ hors polices — aucune donnée, aucun écran de l'application."""
    if minuscules == ['favicon.svg']:
        return True
    if commence_par(minuscules, ('css', 'polices')):
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
        raise ErreurHttp(404, 'Table inconnue : %s.' % table)
    return chemin_sous(config.dossier_donnees, table + '.csv')


def extension(nom):
    return nom.rsplit('.', 1)[-1].lower() if '.' in nom else ''


def verifier_nom_document(nom):
    """Lève ErreurHttp 400 si le nom de document n'est pas autorisé."""
    if not MOTIF_NOM_DOCUMENT.fullmatch(nom) or '..' in nom:
        raise ErreurHttp(400, 'Nom de document refusé : lettres, chiffres, « . », « _ » ou « - ».')
    if extension(nom) not in TYPES_DOCUMENTS:
        raise ErreurHttp(400, 'Type de document refusé. Types acceptés : %s.'
                         % ', '.join(sorted(TYPES_DOCUMENTS)))
    if nom.split('.', 1)[0].lower() in NOMS_RESERVES_WINDOWS:
        raise ErreurHttp(400, 'Nom de document réservé par Windows.')


def verifier_nom_sauvegarde(nom):
    if not isinstance(nom, str) or not MOTIF_NOM_SAUVEGARDE.fullmatch(nom):
        raise ErreurHttp(400, 'Nom de sauvegarde invalide.')


def lire_objet_json(corps):
    """Corps d'une requête → objet JSON (dict), ou ErreurHttp 400.

    Refuse proprement (400, jamais 500) : UTF-8 invalide, JSON invalide, JSON qui n'est pas un
    objet, et JSON trop imbriqué (« [[[[… » : json.loads lève alors RecursionError).
    """
    try:
        demande = json.loads(corps.decode('utf-8'))
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise ErreurHttp(400, 'Corps JSON invalide.')
    if not isinstance(demande, dict):
        raise ErreurHttp(400, 'Corps JSON invalide.')
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
        raise ErreurHttp(400, 'Motif de sauvegarde refusé. Motifs acceptés : %s.'
                         % ', '.join(MOTIFS_SAUVEGARDE))
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
                raise ErreurHttp(423, MESSAGE_FICHIER_VERROUILLE)
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
MESSAGE_PLAFOND_MANUELLES = 'Une sauvegarde manuelle par minute au plus : réessayez dans %d s.'
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


def copier_tables_dans_sauvegarde(config, nom_sauvegarde):
    """Copie tous les CSV présents dans sauvegardes/<nom>/ et renvoie la liste des tables.

    La copie se fait dans un dossier temporaire renommé à la fin : une sauvegarde
    interrompue (panne, disque plein) ne laisse jamais un dossier à moitié rempli.
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
                raise ErreurHttp(423, MESSAGE_FICHIER_VERROUILLE)
        copier_acces_dans_sauvegarde(config, dossier_temporaire)      # lot 7 : comptes, appareils, journal
        os.rename(dossier_temporaire, dossier_final)
    finally:
        if os.path.isdir(dossier_temporaire):
            shutil.rmtree(dossier_temporaire, ignore_errors=True)
    return tables


# Marque posée par le mode dossier (js/stockage-dossier.js) pendant qu'il copie une sauvegarde :
# un dossier qui la contient encore est une sauvegarde incomplète (onglet fermé pendant la copie).
MARQUE_SAUVEGARDE_EN_COURS = '.en-cours'


def sauvegarde_complete(dossier):
    return os.path.isdir(dossier) and not os.path.exists(os.path.join(dossier, MARQUE_SAUVEGARDE_EN_COURS))


def faire_sauvegarde_quotidienne(config):
    """Avant chaque écriture CSV : copie dans sauvegardes/AAAA-MM-JJ/ si la sauvegarde du jour manque (rien s'il n'y
    a encore aucun CSV), puis, à la première écriture après 2 h du matin, la copie externe du jour, lancée dans son
    propre fil (D133). Le jour est celui de l'horloge du serveur. À appeler en tenant VERROU_ECRITURE.
    """
    nom_du_jour = instant_local(config).strftime('%Y-%m-%d')
    dossier_du_jour = os.path.join(config.dossier_sauvegardes, nom_du_jour)
    if not sauvegarde_complete(dossier_du_jour):
        if os.path.isdir(dossier_du_jour):      # sauvegarde du jour laissée incomplète : on la refait
            shutil.rmtree(dossier_du_jour, ignore_errors=True)
        if tables_presentes(config.dossier_donnees):
            copier_tables_dans_sauvegarde(config, nom_du_jour)
    lancer_copie_externe_si_due(config)


def nouveau_nom_horodate(config, suffixe=''):
    """« AAAA-MM-JJ_HHMMSS » (horloge du serveur) + suffixe, en attendant la seconde suivante si le nom est pris ;
    503 si l'horloge n'avance plus (5 s sans nom libre)."""
    for _ in range(ESSAIS_NOM_HORODATE):
        nom = instant_local(config).strftime('%Y-%m-%d_%H%M%S') + suffixe
        if not os.path.exists(os.path.join(config.dossier_sauvegardes, nom)):
            return nom
        time.sleep(0.2)
    raise ErreurHttp(503, 'Sauvegarde impossible : aucun nom horodaté libre (l\'horloge du serveur n\'avance plus ?).')


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
        erreur = ErreurHttp(429, MESSAGE_PLAFOND_MANUELLES % secondes, attente_secondes=secondes)
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
        raise ErreurHttp(400, '« tables » doit être une liste de noms de tables.')
    for table in tables_demandees:
        if not isinstance(table, str) or table not in TABLES:
            raise ErreurHttp(400, 'Table inconnue : %s.' % table)
        if table not in disponibles:
            raise ErreurHttp(400, 'La table %s est absente de cette sauvegarde.' % table)
    return [table for table in TABLES if table in tables_demandees]


def restaurer(config, nom_sauvegarde, tables_demandees):
    """Copie de sécurité de l'état actuel, puis copie des tables depuis la sauvegarde."""
    verifier_nom_sauvegarde(nom_sauvegarde)
    dossier_sauvegarde = chemin_sous(config.dossier_sauvegardes, nom_sauvegarde)
    if not sauvegarde_complete(dossier_sauvegarde):
        raise ErreurHttp(404, 'Sauvegarde introuvable ou incomplète : %s.' % nom_sauvegarde)
    tables = tables_a_restaurer(dossier_sauvegarde, tables_demandees)
    copie_securite = nouveau_nom_horodate(config, '_avant-restauration')
    copier_tables_dans_sauvegarde(config, copie_securite)
    restaurees = []
    for table in tables:
        octets = lire_octets(os.path.join(dossier_sauvegarde, table + '.csv'))
        try:
            ecrire_atomique(chemin_table(config, table), octets)
        except ErreurHttp as erreur:
            # Restauration partielle : on le dit clairement, avec la copie de sécurité à utiliser.
            raise ErreurHttp(
                erreur.statut,
                '%s Restauration interrompue à la table %s ; tables déjà restaurées : %s. '
                "L'état d'avant la restauration est dans la sauvegarde %s."
                % (erreur.message, table, ', '.join(restaurees) or 'aucune', copie_securite),
                restaurees=restaurees, copie_securite=copie_securite)
        restaurees.append(table)
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
        resultat['erreur'] = 'Fichier illisible (%s).' % (erreur.strerror or erreur.__class__.__name__)
        return resultat
    except csv.Error as erreur:
        resultat['erreur'] = 'Fichier illisible (%s).' % erreur
        return resultat
    if not entete:
        resultat['erreur'] = 'Fichier vide : la ligne d\'en-tête manque.'
        return resultat
    resultat['lignes'] = len(lignes)
    presentes = {cle_entete(nom) for nom in entete}
    manquantes = [colonne for colonne in COLONNES_PAR_TABLE[table] if cle_entete(colonne) not in presentes]
    if not set(manquantes) <= set(COLONNES_DES_FORMATS_SUIVANTS.get(table, ())):
        resultat['erreur'] = ('Colonne%s du schéma absente%s de l\'en-tête : %s.'
                              % ('s' if len(manquantes) > 1 else '', 's' if len(manquantes) > 1 else '',
                                 ', '.join(manquantes)))
    return resultat


def tester_sauvegarde(config, nom):
    """POST /api/sauvegarde/tester : {"nom", "ok", "tables": [{"table", "lignes", "erreur"}]} pour chaque CSV de la
    sauvegarde, dans l'ordre du schéma ; ok si elle contient au moins une table et qu'aucune n'a d'erreur. N'écrit
    rien. 400 nom refusé, 404 sauvegarde introuvable ou incomplète."""
    verifier_nom_sauvegarde(nom)
    dossier = chemin_sous(config.dossier_sauvegardes, nom)
    if not sauvegarde_complete(dossier):
        raise ErreurHttp(404, 'Sauvegarde introuvable ou incomplète : %s.' % nom)
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
        ecrire_atomique(chemin_etat_copie_externe(config),
                        (json.dumps(etat, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
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
        raise ErreurCopieExterne('Le dossier de copie « %s » est dans le dossier des données de Prévo : choisissez une '
                                 'clé USB, un NAS ou un dossier synchronisé.' % nom_cible)
    if not os.path.isdir(cible):
        raise ErreurCopieExterne('Dossier de copie « %s » introuvable (clé USB absente ou partage réseau '
                                 'injoignable ?).' % nom_cible)
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
        raise ErreurCopieExterne('Copie vers « %s » incomplète : %d fichier(s) non copié(s) (disque plein ou fichier '
                                 'verrouillé ?).' % (nom_cible, len(erreur.args[0]) if erreur.args else 0))
    except OSError as erreur:
        raise ErreurCopieExterne('Copie vers « %s » impossible : %s.'
                                 % (nom_cible, erreur.strerror or erreur.__class__.__name__))
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
        try:
            nom = copier_vers_l_exterieur(config, cible)
        except ErreurCopieExterne as erreur:
            etat['erreur'] = str(erreur)
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
    erreur = etat.get('erreur') if isinstance(etat.get('erreur'), str) else None
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


def verifier_contenu_csv(table, octets, corps_d_ajout=False):
    """UTF-8, en-tête qui commence par les colonnes du schéma, aucune cellule dangereuse sans apostrophe ; 400 sinon."""
    if not est_utf8(octets):
        raise ErreurHttp(400, 'Le fichier %s.csv doit être encodé en UTF-8.' % table)
    texte = octets.decode('utf-8')
    if texte.startswith('﻿'):
        texte = texte[1:]
    try:
        lignes = list(csv.reader(io.StringIO(texte, newline=''), delimiter=';'))
    except csv.Error as erreur:
        raise ErreurHttp(400, 'Le fichier %s.csv est illisible (%s).' % (table, erreur))
    if not lignes:
        raise ErreurHttp(400, 'Le fichier %s.csv est vide : la ligne d\'en-tête manque.' % table)
    attendues = list(COLONNES_PAR_TABLE.get(table, ()))
    recues = [nom.strip() for nom in lignes[0]]
    if recues[:len(attendues)] != attendues:
        raise ErreurHttp(400, 'En-tête de %s.csv inattendu : il doit commencer par %s.' % (table, ';'.join(attendues)))
    for numero, ligne in enumerate(lignes[1:], 2):
        for cellule in ligne:
            if MOTIF_CELLULE_DANGEREUSE.match(cellule):
                raise ErreurHttp(400, 'Ligne %d de %s.csv : une cellule commence par un caractère de formule '
                                      '(« %s ») ; Prévo la protège par une apostrophe.' % (numero, table, cellule[:1]))


def enregistrer_csv(config, table, octets, version_attendue, controle=None):
    """Remplace le CSV si sa version actuelle est celle attendue ; sinon 409 (conflit). Contenu vérifié d'abord (E2).
    controle (lot 7, §22.5) : (octets reçus, octets actuels) → octets à écrire, appelé après le contrôle de version
    (colonnes cachées remises pour le technicien, demandes en ajout seulement pour le demandeur ; 403 sinon)."""
    verifier_contenu_csv(table, octets)
    chemin = chemin_table(config, table)
    actuel = lire_octets(chemin)
    version_actuelle = empreinte(actuel) if actuel is not None else None
    attendue = None if version_attendue == 'aucune' else version_attendue
    if attendue != version_actuelle:
        if version_actuelle is None:
            message = 'Le fichier %s.csv n\'existe plus.' % table
        elif attendue is None:
            message = 'Le fichier %s.csv existe déjà.' % table
        else:
            message = 'Le fichier %s.csv a été modifié par un autre poste.' % table
        raise ErreurHttp(409, message, version_actuelle=version_actuelle)
    if controle is not None:
        octets = controle(octets, actuel)
    faire_sauvegarde_quotidienne(config)
    ecrire_atomique(chemin, octets)
    return empreinte(octets)


def decouper_corps_ajout(corps):
    """Corps d'un ajout = ligne d'en-tête + lignes de données (UTF-8 sans BOM)."""
    if not est_utf8(corps):
        raise ErreurHttp(400, 'Le corps doit être encodé en UTF-8.')
    if corps.startswith(BOM_UTF8):
        corps = corps[len(BOM_UTF8):]
    entete, lignes = premiere_ligne(corps)
    if not entete:
        raise ErreurHttp(400, 'Le corps doit commencer par la ligne d\'en-tête.')
    return corps, entete, lignes


def ajouter_au_csv(config, table, corps, controle=None):
    """Ajoute des lignes en fin de fichier (journal) ; 409 si en-tête ou encodage différent.
    controle (lot 7, §22.5) : (en-tête, lignes, octets actuels) → lignes à ajouter (colonnes cachées vidées pour le
    technicien, demandes nouvelles seulement pour le demandeur ; 403 sinon)."""
    chemin = chemin_table(config, table)
    verifier_contenu_csv(table, corps, corps_d_ajout=True)
    corps, entete, lignes = decouper_corps_ajout(corps)
    actuel = lire_octets(chemin)
    if controle is not None:
        lignes = controle(entete, lignes, actuel)
        corps = entete + FIN_DE_LIGNE + lignes
    if actuel is None or not actuel.replace(BOM_UTF8, b'', 1).strip():
        faire_sauvegarde_quotidienne(config)
        nouveau = BOM_UTF8 + corps
        ecrire_atomique(chemin, nouveau)
        return empreinte(nouveau)
    if not est_utf8(actuel):
        raise ErreurHttp(409, 'Le fichier %s.csv n\'est pas en UTF-8 (réenregistré par Excel ?).'
                         % table, version_actuelle=empreinte(actuel))
    if premiere_ligne(actuel)[0] != entete:
        raise ErreurHttp(409, 'L\'en-tête de %s.csv est différent.' % table,
                         version_actuelle=empreinte(actuel))
    if not lignes:
        return empreinte(actuel)
    separateur = b'' if actuel.endswith(b'\n') else FIN_DE_LIGNE
    nouveau = actuel + separateur + lignes
    faire_sauvegarde_quotidienne(config)
    ecrire_atomique(chemin, nouveau)
    return empreinte(nouveau)


# ---------------------------------------------------------------------------
# Opérations sur les documents
# ---------------------------------------------------------------------------

def chemin_document(config, nom):
    verifier_nom_document(nom)
    return chemin_sous(config.dossier_documents, nom)


def enregistrer_document(config, nom, octets):
    """Enregistre un nouveau document ; 409 s'il existe déjà (jamais d'écrasement)."""
    chemin = chemin_document(config, nom)
    if os.path.exists(chemin):
        raise ErreurHttp(409, 'Le document %s existe déjà.' % nom)
    ecrire_atomique(chemin, octets)


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
# une photo (« demandeur » est un nom libre) : le demandeur lit toutes les photos de demandes.
MOTIF_PHOTO_DE_DEMANDE = re.compile(r'photo-[0-9]{8}-[0-9]{6}-[A-Z0-9]{4}\.(jpg|jpeg|png|gif|webp)', re.ASCII)
PHOTOS_DE_DEMANDES = 'photos de demandes'
DOCUMENTS_DU_DEMANDEUR = 'photos de demandes et documents des équipements'
TOUS = (OUI, OUI, OUI, OUI)
RESPONSABLE = (NON, NON, NON, OUI)

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
    ('POST', 'ia'): TOUS,
    ('GET', 'ia/reglages'): TOUS,
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
MESSAGE_RESERVE_AU_RESPONSABLE = 'Accès refusé : réservé au responsable.'
MESSAGE_AJOUT_SEULEMENT = ('Accès refusé : le demandeur ne peut qu\'ajouter une demande (statut « Nouvelle », sans '
                           'décision) ; %s')


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
        return 'Accès refusé : la table « %s » n\'est pas ouverte au %s.' % (segment, role)
    if motif.startswith('csv/') and role == 'technicien':
        return 'Accès refusé : la table « %s » ne se modifie que par le responsable.' % segment
    if motif.startswith('csv/'):
        return ('Accès refusé : le %s ne peut que créer une demande (et la ligne du journal qui va avec).' % role)
    if motif == 'documents/<nom>' and methode == 'PUT':
        return 'Accès refusé : le %s ne joint que la photo d\'une demande.' % role
    if motif == 'documents/<nom>':
        return 'Accès refusé : ce document n\'est pas ouvert au %s.' % role
    return 'Accès refusé : votre rôle (%s) ne permet pas cette action.' % role


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
        raise ErreurHttp(500, 'Le fichier %s.csv est illisible (%s).' % (table, erreur))


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
    return ErreurHttp(403, MESSAGE_AJOUT_SEULEMENT % raison)


def verifier_demande_nouvelle(ligne, deja_prises):
    """Ligne nouvelle du demandeur : id présent et pas déjà pris, statut « Nouvelle », champs de décision vides ; 403
    sinon. deja_prises : ids du fichier et des nouvelles lignes déjà vues (complété ici)."""
    identifiant = ligne.get('id', '').strip()
    if not identifiant:
        raise refus_ajout_seulement('une nouvelle demande doit avoir un numéro.')
    if identifiant in deja_prises:
        raise refus_ajout_seulement('le numéro %s est déjà pris.' % identifiant)
    deja_prises.add(identifiant)
    if ligne.get('statut', '').strip() != STATUT_DEMANDE_NOUVELLE:
        raise refus_ajout_seulement('une nouvelle demande a le statut « %s ».' % STATUT_DEMANDE_NOUVELLE)
    if any(ligne.get(cle_entete(champ), '').strip() for champ in CHAMPS_DE_DECISION):
        raise refus_ajout_seulement('la décision (motif, date, ordre de travail) revient au responsable.')


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
            raise refus_ajout_seulement('la demande %s existe déjà : elle ne se modifie pas ici.' % identifiant)
        else:
            verifier_demande_nouvelle(recue, prises)
            nouvelles.append(brute)
    manquantes = [identifiant or 'sans numéro' for identifiant, reste in restantes.items() if reste]
    if manquantes:
        raise refus_ajout_seulement('une demande ne se supprime pas (%s).' % ', '.join(sorted(manquantes)[:5]))
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
            raise ErreurHttp(400, 'Champ inconnu ou non modifiable ici : « %s » (prenom, nom, role, technicien_id).'
                             % str(cle)[:60])
        if not isinstance(valeur, str):
            raise ErreurHttp(400, '« %s » : un texte est attendu.' % cle)
        champs[cle] = valeur.strip()
    for cle in obligatoires:
        if not champs.get(cle):
            raise ErreurHttp(400, '« %s » est obligatoire.' % cle)
    if 'role' in champs and champs['role'] not in ROLES_COMPTES:
        raise ErreurHttp(400, 'Rôle inconnu : « %s » (responsable, technicien ou demandeur).' % champs['role'][:60])
    if champs.get('technicien_id') and not technicien_existe(config, champs['technicien_id']):
        raise ErreurHttp(400, 'Technicien inconnu : « %s » (voir Équipe).' % champs['technicien_id'][:60])
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
        """Une ligne par écriture : heure, IP, méthode, chemin, statut."""
        if self.command in ('PUT', 'POST'):
            afficher('%s  %s  %s %s  %s' % (time.strftime('%H:%M:%S'), self.client_address[0],
                                            self.command, self.path[:200], code))

    # --- Aiguillage --------------------------------------------------------

    @property
    def config(self):
        return self.server.config

    def est_requete_api(self):
        chemin = self.path.split('?', 1)[0]
        return chemin == '/api' or chemin.startswith('/api/')

    def traiter(self, methode):
        # Ordre des contrôles (audit F2, §22.4) : hôte, chemin, accès à l'API (session quand les comptes sont
        # exigés), X-Prevo, puis seulement la lecture du corps : un client sans session ne fait jamais lire 10 Mo.
        # Un refus prononcé avant la lecture jette au plus 64 Ko de corps (envoyer_erreur) pour que le navigateur
        # reçoive la réponse ; au-delà, la connexion persistante est fermée après la réponse (les octets non lus
        # seraient pris pour la requête suivante).
        self.corps_lu = methode not in ('PUT', 'POST')
        self.lecture_commencee = False
        self.session = None
        self.mandat = origine_mandatee(self)        # §22.7 : None pour un client direct
        try:
            if not hote_autorise(self.headers.get('Host'), self.config):
                raise ErreurHttp(403, 'Nom d\'hôte refusé. Utilisez l\'adresse IP du PC.')
            if self.mandat is not None and not hote_autorise(self.mandat['hote'], self.config):
                raise ErreurHttp(403, MESSAGE_HOTE_ORIGINE_REFUSE)
            morceaux = analyser_chemin(self.path)
            if self.sur_la_porte():
                self.servir_porte(methode, morceaux)       # client du réseau sur port_http : la porte, rien d'autre
                return
            if morceaux[0] == 'api':
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
                raise ErreurHttp(405, 'Méthode non autorisée.')
        except ErreurHttp as erreur:
            self.envoyer_erreur(erreur)
        except (ConnectionError, socket.timeout):
            pass                        # le navigateur a fermé la connexion
        except Exception:               # bogue : on le trace sans arrêter le serveur
            traceback.print_exc()
            self.envoyer_erreur(ErreurHttp(500, 'Erreur interne du serveur.'))

    def traiter_api(self, methode, morceaux, corps):
        """Aiguillage d'après ROUTES_API (chemin après /api/) : 404 adresse inconnue, 405 autre méthode. Le segment
        variable est contrôlé avant la méthode, comme avant le lot 7 : table inconnue 404, nom de document refusé
        400."""
        motif = motif_de_route(morceaux)
        if motif is None:
            raise ErreurHttp(404, 'Adresse inconnue dans l\'API.')
        segment = segment_de_route(motif, morceaux)
        if '<table>' in motif:
            chemin_table(self.config, segment)
        elif '<nom>' in motif:
            chemin_document(self.config, segment)
        fonction = ROUTES_API.get((methode, motif))
        if fonction is None:
            raise ErreurHttp(405, 'Méthode non autorisée.')
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
            raise ErreurHttp(500, 'Page de porte introuvable (acces/porte.html).')
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
            raise ErreurHttp(403, 'En-tête X-Prevo manquant.')

    def lire_corps(self):
        """Lit le corps : Content-Length obligatoire (411) et au plus 10 Mo (413)."""
        longueur_texte = self.headers.get('Content-Length')
        if longueur_texte is None:
            raise ErreurHttp(411, 'En-tête Content-Length obligatoire.')
        try:
            longueur = int(longueur_texte)
        except ValueError:
            raise ErreurHttp(400, 'En-tête Content-Length invalide.')
        if longueur < 0:
            raise ErreurHttp(400, 'En-tête Content-Length invalide.')
        if longueur > TAILLE_MAX_CORPS:
            raise ErreurHttp(413, 'Envoi trop gros (10 Mo au maximum).')
        corps = self.rfile.read(longueur)
        if len(corps) != longueur:
            raise ErreurHttp(400, 'Corps de la requête incomplet.')
        return corps

    # --- Fonctions de l'API (appelées avec le segment variable du chemin, ou None, et le corps) ------

    def api_ping(self, segment, corps):
        self.envoyer_json(200, {'application': NOM_APPLICATION,
                                'version': VERSION_APPLICATION, 'api': VERSION_API})

    def api_info(self, segment, corps):
        """GET /api/info : port, adresses (celles de la porte hors de « ce PC », §22.6), « porte » vrai quand elle est
        ouverte (la carte « Connecter un téléphone » rappelle alors « Faites confiance au PC atelier »), et l'état de
        la copie externe des sauvegardes (D133 ; None sans dossier). Jamais le port https : il n'est pas une adresse
        que Prévo donne (CS137)."""
        adresse_locale, adresses_reseau = self.adresses_donnees()
        self.envoyer_json(200, {'port': self.config.port,
                                'adresse_locale': adresse_locale,
                                'adresses_reseau': adresses_reseau,
                                'porte': self.config.porte and self.mandat is None,
                                'copie_externe': etat_copie_externe_public(self.config)})

    def api_session(self, segment, corps):
        """GET /api/session : comptes exigés ou non, et l'identité de la session (jamais le jeton). Pour un appareil
        enrôlé, son cookie repart pour un an (D125 : un an glissant, à chaque ouverture de l'application)."""
        entetes = None
        if self.session is not None and self.session.get('appareil'):
            for jeton in valeurs_cookie(self.headers.get('Cookie'), NOM_COOKIE_APPAREIL):
                if empreinte_jeton(jeton) == self.session.get('cle'):
                    entetes = {'Set-Cookie': entete_cookie_session(jeton, self.en_https(), DUREE_APPAREIL_JOURS * 86400,
                                                                   NOM_COOKIE_APPAREIL)}
        self.envoyer_json(200, {'comptes': bool(self.config.reglages.get('comptes')),
                                'session': session_publique(self.session)}, entetes)

    def api_connexion(self, segment, corps):
        """POST /api/connexion {identifiant, mot_de_passe, rester} : 200 et cookie « id » (jeton neuf ; l'ancienne
        session de ce navigateur est fermée) ; 401 au message neutre ; 429 pendant un blocage (§22.3)."""
        self.exiger_comptes()
        demande = lire_objet_json(corps)
        identifiant, mot_de_passe = demande.get('identifiant'), demande.get('mot_de_passe')
        rester = demande.get('rester', False)
        if not (isinstance(identifiant, str) and isinstance(mot_de_passe, str) and isinstance(rester, bool)):
            raise ErreurHttp(400, 'Connexion : « identifiant » et « mot_de_passe » (textes) sont attendus, '
                                  '« rester » vaut vrai ou faux.')
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
            raise ErreurHttp(400, 'Mot de passe : « actuel » et « nouveau » (textes) sont attendus.')
        try:
            verifier_mot_de_passe_choisi(nouveau)
        except ErreurCompte as erreur:
            raise ErreurHttp(400, str(erreur))
        if nouveau == actuel:
            raise ErreurHttp(400, 'Choisissez un mot de passe différent de l\'actuel.')
        identifiant, origine = self.session['identifiant'], self.origine()
        verifier_tentative(self.config, identifiant, actuel, origine, ErreurHttp(403, MESSAGE_ACTUEL_FAUX),
                           journal_reussite=None)
        try:
            changer_mot_de_passe(self.config, identifiant, nouveau, origine=origine)
        except ErreurCompte as erreur:
            raise ErreurHttp(400, str(erreur))
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
            raise ErreurHttp(400, 'Enrôlement : « invitation » et « nom » (textes) sont attendus.')
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
            raise ErreurHttp(400, '« identifiant » : l\'identifiant d\'un compte est attendu.')
        cible = cible.strip().lower()
        soi_meme = cible == self.session['identifiant']
        if not soi_meme:
            if self.session['role'] != 'responsable':
                raise ErreurHttp(403, 'Réservé au responsable : vous ne pouvez fermer que vos propres sessions.')
            if trouver_compte(comptes_du_serveur(self.config), cible) is None:
                raise ErreurHttp(404, 'Compte introuvable : %s.' % cible)
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
        """POST /api/acces/comptes (responsable) {prenom, nom, role, technicien_id} : compte créé avec un mot de passe
        provisoire de 16 caractères, à changer à la première connexion (a_changer), rendu une seule fois dans la
        réponse : jamais écrit dans un fichier, le journal ou la console."""
        self.exiger_comptes()
        champs = champs_de_compte(self.config, lire_objet_json(corps), obligatoires=('prenom', 'role'))
        provisoire = mot_de_passe_provisoire()
        try:
            compte = creer_compte(self.config, champs['prenom'], champs.get('nom', ''), champs['role'], provisoire,
                                  technicien_id=champs.get('technicien_id', ''), a_changer=True,
                                  origine=self.origine())
        except ErreurCompte as erreur:
            raise ErreurHttp(400, str(erreur))
        self.envoyer_json(200, {'compte': compte, 'mot_de_passe_provisoire': provisoire})

    def api_compte_changer(self, identifiant, corps):
        """POST /api/acces/comptes/<identifiant> (responsable) {"action": "modifier" (prenom, nom, role, technicien_id)
        | "reinitialiser" | "desactiver" | "activer"} : fonctions de T150 (au moins un responsable actif reste : 400) ;
        « reinitialiser » rend le mot de passe provisoire une seule fois ; 404 compte inconnu, 400 action inconnue."""
        self.exiger_comptes()
        demande = lire_objet_json(corps)
        action = demande.pop('action', None)
        if action not in ACTIONS_COMPTE:
            raise ErreurHttp(400, '« action » attendue : %s.' % ', '.join(ACTIONS_COMPTE))
        if action != 'modifier' and demande:
            raise ErreurHttp(400, 'L\'action « %s » ne prend aucun autre champ.' % action)
        champs = champs_de_compte(self.config, demande) if action == 'modifier' else {}
        cible = trouver_compte(comptes_du_serveur(self.config), identifiant)
        if cible is None:
            raise ErreurHttp(404, 'Compte introuvable : %s.' % identifiant[:LONGUEUR_MAX_IDENTIFIANT])
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
            raise ErreurHttp(400, str(erreur))
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
            raise ErreurHttp(400, 'Champ inconnu : « %s » (« heures » seulement).' % str(inconnus[0])[:60])
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
            raise ErreurHttp(502, 'Réponse du fournisseur d\'IA trop grande (2 Mo au maximum).')
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
            raise ErreurHttp(404, 'Le fichier %s.csv n\'existe pas encore.' % table)
        self.envoyer(200, filtrer_csv_pour(self.session, table, octets), 'text/csv; charset=utf-8',
                     {'X-Version': empreinte(octets)})

    def api_csv_ecrire(self, table, corps):
        version_attendue = self.headers.get('X-Version-Attendue')
        if not version_attendue:
            raise ErreurHttp(400, 'En-tête X-Version-Attendue manquant.')
        with VERROU_ECRITURE:
            version = enregistrer_csv(self.config, table, corps, version_attendue.strip(),
                                      controle_d_ecriture(self.session, table))
        self.envoyer_json(200, {'version': version})

    def api_ajout(self, table, corps):
        with VERROU_ECRITURE:
            version = ajouter_au_csv(self.config, table, corps, controle_d_ajout(self.session, table))
        self.envoyer_json(200, {'version': version})

    def api_document_lire(self, nom, corps):
        chemin = chemin_document(self.config, nom)          # 400 si nom refusé
        octets = lire_octets(chemin)
        if octets is None:
            raise ErreurHttp(404, 'Document introuvable : %s.' % nom)
        # nosniff + sandbox : un document ne peut jamais s'exécuter comme une page.
        self.envoyer(200, octets, TYPES_DOCUMENTS[extension(nom)],
                     {'Content-Security-Policy': 'sandbox'})

    def api_document_ecrire(self, nom, corps):
        with VERROU_ECRITURE:
            enregistrer_document(self.config, nom, corps)
        self.envoyer_json(201, {'nom': nom})

    def api_sauvegarde(self, segment, corps):
        """Sauvegarde manuelle (corps vide) ou automatique avec un motif de la liste fermée
        (corps {"motif": "avant-format-v2"} → nom « AAAA-MM-JJ_HHMMSS_avant-format-v2 »).
        Manuelle (D133) : une par minute au plus (429 et Retry-After), les 60 dernières gardées ; une sauvegarde à
        motif n'est ni limitée ni comptée."""
        motif = lire_motif_sauvegarde(corps)            # 400 si motif refusé, avant toute écriture
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

    # --- Fichiers statiques ------------------------------------------------

    def servir_statique(self, morceaux, entetes=None):
        """Sert un fichier de la liste blanche (index.html, favicon.svg, GUIDE.html, css/, js/, acces/ ;
        tests/fixtures/ avec --servir-tests) et /acces/ca.crt (certificat public de l'autorité, §22.6). Jamais
        donnees/ ni les fichiers cachés. « entetes » : ceux de la porte ; sinon ceux de l'application."""
        if morceaux == ['']:
            morceaux = ['index.html']
        if morceaux[0].lower() == 'donnees':
            raise ErreurHttp(403, 'Accès refusé.')
        if [morceau.lower() for morceau in morceaux] == CHEMIN_CERTIFICAT_AUTORITE:
            self.servir_certificat_autorite()
            return
        servir_tests = self.config.servir_tests
        # Hors liste blanche : même réponse qu'un fichier absent (on ne dit pas qu'il existe).
        if not chemin_public(morceaux, servir_tests):
            raise ErreurHttp(404, 'Fichier introuvable.')
        chemin = chemin_sous(DOSSIER_APPLICATION, *morceaux)
        if not chemin_public(morceaux_resolus(chemin, DOSSIER_APPLICATION), servir_tests):
            raise ErreurHttp(404, 'Fichier introuvable.')
        for dossier_interdit in self.config.dossiers_interdits_statique:
            if est_sous_dossier(chemin, dossier_interdit):
                raise ErreurHttp(403, 'Accès refusé.')
        if not os.path.isfile(chemin):
            raise ErreurHttp(404, 'Fichier introuvable.')
        octets = lire_octets(chemin)
        if octets is None:
            raise ErreurHttp(404, 'Fichier introuvable.')
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
        octets = json.dumps(donnees, ensure_ascii=False).encode('utf-8')
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
    adresses = config.adresses_reseau()
    if adresses:
        for adresse in adresses:
            afficher('  Sur le réseau    : %s   (téléphones, tablettes)' % adresse)
    else:
        afficher('  Sur le réseau    : aucune adresse trouvée (PC non connecté ?)')
    afficher('  Données          : %s' % config.dossier_donnees)
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


def reinitialiser_en_ligne_de_commande(config, identifiant):
    """serveur.py --reinitialiser IDENTIFIANT : sur le PC serveur, qui a la main sur le PC a la main sur Prévo."""
    try:
        provisoire = reinitialiser_compte(config, identifiant)
    except (ErreurCompte, OSError, ValueError) as erreur:
        afficher('Réinitialisation impossible : %s' % erreur)
        sys.exit(1)
    afficher('Mot de passe provisoire de « %s » : %s' % (identifiant.strip().lower(), provisoire))
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
    serveurs, config.port = demarrer_serveur(reglages['port_http'], config)
    afficher_accueil(config, reglages['port_http'], avertissements)
    lancer_copie_externe(config)        # D133 : copie externe au démarrage, dans son propre fil
    if not options.sans_navigateur:
        webbrowser.open(config.adresse_locale())
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
