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
                  [--servir-tests]

ATTENTION : aucune authentification. Usage sur un réseau local de confiance uniquement.
"""

import argparse
import csv
import datetime
import hashlib
import http.client
import http.server
import io
import ipaddress
import json
import math
import os
import re
import shutil
import socket
import socketserver
import ssl
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.request
import webbrowser
from urllib.parse import unquote, urlsplit


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

NOM_APPLICATION = 'Prévo'
VERSION_APPLICATION = '0.1.0'
VERSION_API = 1

PORT_PAR_DEFAUT = 8080
NOMBRE_PORTS_SUPPLEMENTAIRES = 20          # 8080 occupé → 8081, … jusqu'à 8100
TAILLE_MAX_CORPS = 10 * 1024 * 1024        # 10 Mo
ESSAIS_SI_VERROUILLE = 3                   # fichier ouvert dans Excel : 3 essais…
PAUSE_ENTRE_ESSAIS_S = 0.1                 # … espacés de 100 ms
# Relais vers le fournisseur d'IA (lot 4, ARCHITECTURE.md §17.2) : liste fermée des chemins (Ollama :
# api/chat, api/tags ; API compatible OpenAI : chat/completions, models), délai et taille plafonnés.
# Limite connue : le délai s'applique à CHAQUE opération réseau (connexion, envoi, chaque lecture), pas à
# la durée totale de l'appel ; un fournisseur qui envoie sa réponse goutte à goutte peut donc le dépasser.
CHEMINS_IA = ('api/chat', 'api/tags', 'chat/completions', 'models')
DELAI_IA_PAR_DEFAUT_S = 120
DELAI_IA_MAX_S = 300
TAILLE_MAX_REPONSE_IA = 2 * 1024 * 1024    # 2 Mo

# Dossier où se trouve serveur.py : c'est la racine des fichiers statiques.
DOSSIER_APPLICATION = os.path.dirname(os.path.abspath(__file__))

BOM_UTF8 = b'\xef\xbb\xbf'
FIN_DE_LIGNE = b'\r\n'

# Les 22 tables de la GMAO (fichier = <nom>.csv dans le dossier de données).
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
)

# Noms autorisés (re.ASCII : \d et \w ne reconnaissent que les caractères ASCII).
MOTIF_NOM_DOCUMENT = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', re.ASCII)
# Nom d'une sauvegarde (mêmes règles que js/stockage-dossier.js) :
#   AAAA-MM-JJ                               quotidienne
#   AAAA-MM-JJ_HHMMSS                        manuelle
#   AAAA-MM-JJ_HHMMSS_avant-restauration     copie de sécurité faite avant une restauration
#   AAAA-MM-JJ_HHMMSS_avant-format-v<N>      faite juste avant le passage au format N des fichiers
MOTIF_NOM_SAUVEGARDE = re.compile(
    r'[0-9]{4}-[0-9]{2}-[0-9]{2}(_[0-9]{6}(_avant-restauration|_avant-format-v[0-9]+)?)?', re.ASCII)
# Motifs acceptés par POST /api/sauvegarde {"motif": "…"} : liste FERMÉE (tout autre motif → 400).
# Le motif devient la fin du nom de la sauvegarde (« _avant-format-v2 »). Règle générale :
# « avant-format-v<N> » ; on n'ajoute ici que les versions que Prévo sait vraiment produire.
MOTIFS_SAUVEGARDE = ('avant-format-v2',)

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
DOSSIERS_PUBLICS = (('css',), ('js',))                               # avec tout leur contenu
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
    if sys.stdout is None:          # lancé sans console (pythonw)
        return
    try:
        print(texte, flush=True)
    except (OSError, ValueError):
        pass


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class Configuration:
    """Réglages du serveur, calculés une fois au démarrage."""

    def __init__(self, dossier_donnees, hotes_supplementaires, servir_tests=False):
        self.dossier_donnees = os.path.abspath(dossier_donnees)
        self.dossier_documents = os.path.join(self.dossier_donnees, 'documents')
        self.dossier_sauvegardes = os.path.join(self.dossier_donnees, 'sauvegardes')
        self.nom_pc = socket.gethostname().lower()
        self.hotes_supplementaires = [hote.lower().strip() for hote in hotes_supplementaires]
        self.servir_tests = servir_tests    # --servir-tests : tests/fixtures/ servi en plus
        self.port = None            # renseigné quand le port est trouvé
        self.contexte_ssl = None    # lot 4 : https en option (--certificat, --cle)
        # Dossiers jamais servis en statique : le dossier de données choisi et donnees/
        # à côté de serveur.py (même si --donnees pointe ailleurs).
        self.dossiers_interdits_statique = [
            self.dossier_donnees, os.path.join(DOSSIER_APPLICATION, 'donnees')]

    @property
    def schema(self):
        return 'https' if self.contexte_ssl is not None else 'http'

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
MESSAGE_DISTANT_REFUSE = 'Le responsable n\'a pas autorisé les fournisseurs en ligne.'


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


def lire_demande_ia(corps):
    """Demande de relais vérifiée : { cible, methode, octets, entetes, delai }. ErreurHttp(400) sinon."""
    try:
        demande = json.loads(corps.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        raise ErreurHttp(400, 'Demande illisible (JSON attendu).')
    if not isinstance(demande, dict):
        raise ErreurHttp(400, 'Demande illisible (objet JSON attendu).')
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
    cle = demande.get('cle')
    if cle:
        # Caractères ASCII visibles (et espace) seulement : l'en-tête HTTP ne sait pas en porter d'autres.
        if not isinstance(cle, str) or not all(' ' <= caractere <= '~' for caractere in cle):
            raise ErreurHttp(400, 'Clé du fournisseur d\'IA illisible.')
        entetes['Authorization'] = 'Bearer ' + cle
    delai = demande.get('delai', DELAI_IA_PAR_DEFAUT_S)
    if isinstance(delai, float) and not math.isfinite(delai):      # 1e999, -Infinity, NaN
        raise ErreurHttp(400, 'Délai de l\'IA invalide (un nombre de secondes est attendu).')
    try:
        delai = int(delai)
    except (TypeError, ValueError):
        delai = DELAI_IA_PAR_DEFAUT_S
    return {'cible': adresse_fournisseur(demande.get('url')) + '/' + chemin, 'methode': methode, 'octets': octets,
            'entetes': entetes, 'delai': min(max(delai, 1), DELAI_IA_MAX_S)}


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


def valeur_parametre(octets, cle):
    """Valeur de `cle` dans le contenu de parametres.csv, ou '' (fichier, colonne ou clé absents).

    Première ligne qui porte la clé, comme Donnees.parametre. Lecture tolérante (§3.3) : BOM retiré,
    UTF-8 sinon windows-1252, séparateur « ; » (« , » si l'en-tête n'a aucun « ; »), guillemets,
    colonnes « cle » et « valeur » trouvées par leur nom, espaces de fin retirés, apostrophe de
    protection retirée (§3.2 : « '1 » → « 1 » ; « ''1 » → « '1 »).
    """
    if octets.startswith(BOM_UTF8):
        octets = octets[len(BOM_UTF8):]
    try:
        texte = octets.decode('utf-8')
    except UnicodeDecodeError:
        texte = octets.decode('cp1252', 'replace')
    entete = texte.split('\n', 1)[0]
    separateur = ',' if ';' not in entete and ',' in entete else ';'
    try:
        lignes = list(csv.reader(io.StringIO(texte, newline=''), delimiter=separateur))
    except csv.Error:
        return ''
    noms = [nom.strip().lower() for nom in lignes[0]] if lignes else []
    if 'cle' not in noms or 'valeur' not in noms:
        return ''
    colonne_cle, colonne_valeur = noms.index('cle'), noms.index('valeur')
    for ligne in lignes[1:]:
        if len(ligne) > colonne_cle and ligne[colonne_cle].strip() == cle:
            valeur = ligne[colonne_valeur].rstrip() if len(ligne) > colonne_valeur else ''
            return valeur[1:] if valeur.startswith("'") else valeur
    return ''


def distant_autorise(config):
    """Réglage partagé du responsable (D67) : fournisseurs en ligne autorisés si ia_distant_autorise
    vaut 1 dans parametres.csv. Défaut : non (fichier, clé ou valeur absents ou illisibles)."""
    with VERROU_ECRITURE:
        octets = lire_octets(chemin_table(config, 'parametres'))
    return valeur_parametre(octets or b'', 'ia_distant_autorise') == '1'


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


def morceaux_resolus(chemin, dossier):
    """Morceaux de « chemin » (déjà résolu par chemin_sous) relatifs à « dossier ».

    Sert à recontrôler la liste blanche APRÈS résolution : un raccourci Windows (jonction,
    lien) rangé dans js/ ne doit pas permettre de lire un fichier situé ailleurs.
    """
    return os.path.relpath(chemin, os.path.realpath(dossier)).split(os.sep)


def chemin_table(config, table):
    """Chemin du CSV d'une table ; 404 si la table n'est pas une des 22 du schéma."""
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
    """Avant la première écriture CSV du jour : copie dans sauvegardes/AAAA-MM-JJ/.

    Rien n'est fait si la sauvegarde du jour existe déjà ou s'il n'y a encore aucun CSV.
    À appeler en tenant VERROU_ECRITURE.
    """
    nom_du_jour = datetime.date.today().strftime('%Y-%m-%d')
    dossier_du_jour = os.path.join(config.dossier_sauvegardes, nom_du_jour)
    if sauvegarde_complete(dossier_du_jour):
        return
    if os.path.isdir(dossier_du_jour):          # sauvegarde du jour laissée incomplète : on la refait
        shutil.rmtree(dossier_du_jour, ignore_errors=True)
    if not tables_presentes(config.dossier_donnees):
        return
    copier_tables_dans_sauvegarde(config, nom_du_jour)


def nouveau_nom_horodate(config, suffixe=''):
    """« AAAA-MM-JJ_HHMMSS » + suffixe, en attendant la seconde suivante si le nom est pris."""
    while True:
        nom = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S') + suffixe
        if not os.path.exists(os.path.join(config.dossier_sauvegardes, nom)):
            return nom
        time.sleep(0.2)


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


# ---------------------------------------------------------------------------
# Opérations sur les CSV
# ---------------------------------------------------------------------------

def versions_des_tables(config):
    """{"table": {"version", "modifie"} ou None} pour les 22 tables."""
    resultat = {}
    for table in TABLES:
        chemin = chemin_table(config, table)
        octets = lire_octets(chemin)
        if octets is None:
            resultat[table] = None
        else:
            resultat[table] = {'version': empreinte(octets), 'modifie': date_modification(chemin)}
    return resultat


def enregistrer_csv(config, table, octets, version_attendue):
    """Remplace le CSV si sa version actuelle est celle attendue ; sinon 409 (conflit)."""
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


def ajouter_au_csv(config, table, corps):
    """Ajoute des lignes en fin de fichier (journal) ; 409 si en-tête ou encodage différent."""
    chemin = chemin_table(config, table)
    corps, entete, lignes = decouper_corps_ajout(corps)
    actuel = lire_octets(chemin)
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
    # Toutes les réponses portent Content-Length (envoyer) ; le corps des requêtes est toujours lu.
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
        # Corps de la requête entièrement lu ? Sinon la connexion (persistante) doit être fermée
        # après la réponse : les octets non lus seraient pris pour la requête suivante.
        self.corps_lu = methode not in ('PUT', 'POST')
        try:
            corps = b''
            if methode in ('PUT', 'POST'):
                # Le corps est lu AVANT tout refus : fermer une connexion dont le corps
                # n'est pas lu ferait perdre la réponse au navigateur (« connexion réinitialisée »).
                corps = self.lire_corps()
                self.corps_lu = True
            if not hote_autorise(self.headers.get('Host'), self.config):
                raise ErreurHttp(403, 'Nom d\'hôte refusé. Utilisez l\'adresse IP du PC.')
            if methode in ('PUT', 'POST'):
                self.verifier_entete_prevo()
            morceaux = analyser_chemin(self.path)
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
        """Choisit la fonction de l'API d'après la méthode et le chemin (après /api/)."""
        if len(morceaux) == 1:
            routes_simples = {
                ('GET', 'ping'): self.api_ping,
                ('GET', 'info'): self.api_info,
                ('GET', 'versions'): self.api_versions,
                ('GET', 'sauvegardes'): self.api_sauvegardes,
                ('POST', 'sauvegarde'): lambda: self.api_sauvegarde(corps),
                ('POST', 'restauration'): lambda: self.api_restauration(corps),
                ('POST', 'ia'): lambda: self.api_ia(corps),
            }
            fonction = routes_simples.get((methode, morceaux[0]))
            if fonction is not None:
                return fonction()
            if morceaux[0] in {nom for (_, nom) in routes_simples}:
                raise ErreurHttp(405, 'Méthode non autorisée.')
        elif len(morceaux) == 2 and morceaux[0] == 'csv':
            return self.api_csv(methode, morceaux[1], corps)
        elif len(morceaux) == 3 and morceaux[0] == 'csv' and morceaux[2] == 'ajout':
            chemin_table(self.config, morceaux[1])          # 404 si table inconnue
            if methode != 'POST':
                raise ErreurHttp(405, 'Méthode non autorisée.')
            return self.api_ajout(morceaux[1], corps)
        elif len(morceaux) == 2 and morceaux[0] == 'documents':
            return self.api_document(methode, morceaux[1], corps)
        raise ErreurHttp(404, 'Adresse inconnue dans l\'API.')

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

    # --- Fonctions de l'API ------------------------------------------------

    def api_ping(self):
        self.envoyer_json(200, {'application': NOM_APPLICATION,
                                'version': VERSION_APPLICATION, 'api': VERSION_API})

    def api_info(self):
        self.envoyer_json(200, {'port': self.config.port,
                                'adresse_locale': self.config.adresse_locale(),
                                'adresses_reseau': self.config.adresses_reseau()})

    def api_ia(self, corps):
        """Relais vers le fournisseur d'IA choisi sur le poste (lot 4, ARCHITECTURE.md §17.2).

        Rend { statut, corps } : le statut et le corps (JSON, sinon texte) du fournisseur. La clé
        éventuelle est transmise au fournisseur et oubliée : jamais écrite, affichée ni renvoyée.
        Demande invalide → 400 ; fournisseur en ligne sans l'accord du responsable (D67) → 403, avant
        tout appel sortant ; échec réseau ou réponse coupée → 502 ; délai dépassé → 504.
        """
        demande = lire_demande_ia(corps)
        if fournisseur_distant(demande['cible']) and not distant_autorise(self.config):
            raise ErreurHttp(403, MESSAGE_DISTANT_REFUSE)
        statut, octets = appeler_fournisseur(demande)
        if len(octets) > TAILLE_MAX_REPONSE_IA:
            raise ErreurHttp(502, 'Réponse du fournisseur d\'IA trop grande (2 Mo au maximum).')
        self.envoyer_json(200, {'statut': statut, 'corps': corps_lisible(octets)})

    def api_versions(self):
        with VERROU_ECRITURE:
            tables = versions_des_tables(self.config)
        self.envoyer_json(200, {'tables': tables})

    def api_csv(self, methode, table, corps):
        chemin = chemin_table(self.config, table)            # 404 si table inconnue
        if methode == 'GET':
            with VERROU_ECRITURE:
                octets = lire_octets(chemin)
            if octets is None:
                raise ErreurHttp(404, 'Le fichier %s.csv n\'existe pas encore.' % table)
            self.envoyer(200, octets, 'text/csv; charset=utf-8',
                         {'X-Version': empreinte(octets)})
        elif methode == 'PUT':
            version_attendue = self.headers.get('X-Version-Attendue')
            if not version_attendue:
                raise ErreurHttp(400, 'En-tête X-Version-Attendue manquant.')
            with VERROU_ECRITURE:
                version = enregistrer_csv(self.config, table, corps, version_attendue.strip())
            self.envoyer_json(200, {'version': version})
        else:
            raise ErreurHttp(405, 'Méthode non autorisée.')

    def api_ajout(self, table, corps):
        with VERROU_ECRITURE:
            version = ajouter_au_csv(self.config, table, corps)
        self.envoyer_json(200, {'version': version})

    def api_document(self, methode, nom, corps):
        chemin = chemin_document(self.config, nom)          # 400 si nom refusé
        if methode == 'GET':
            octets = lire_octets(chemin)
            if octets is None:
                raise ErreurHttp(404, 'Document introuvable : %s.' % nom)
            # nosniff + sandbox : un document ne peut jamais s'exécuter comme une page.
            self.envoyer(200, octets, TYPES_DOCUMENTS[extension(nom)],
                         {'Content-Security-Policy': 'sandbox'})
        elif methode == 'PUT':
            with VERROU_ECRITURE:
                enregistrer_document(self.config, nom, corps)
            self.envoyer_json(201, {'nom': nom})
        else:
            raise ErreurHttp(405, 'Méthode non autorisée.')

    def api_sauvegarde(self, corps):
        """Sauvegarde manuelle (corps vide) ou automatique avec un motif de la liste fermée
        (corps {"motif": "avant-format-v2"} → nom « AAAA-MM-JJ_HHMMSS_avant-format-v2 »)."""
        motif = lire_motif_sauvegarde(corps)            # 400 si motif refusé, avant toute écriture
        suffixe = '_' + motif if motif else ''
        with VERROU_ECRITURE:
            nom = nouveau_nom_horodate(self.config, suffixe)
            verifier_nom_sauvegarde(nom)                # sécurité : le nom reste dans les règles
            copier_tables_dans_sauvegarde(self.config, nom)
        self.envoyer_json(200, {'sauvegarde': nom})

    def api_sauvegardes(self):
        self.envoyer_json(200, {'sauvegardes': lister_sauvegardes(self.config)})

    def api_restauration(self, corps):
        demande = lire_objet_json(corps)
        with VERROU_ECRITURE:
            resultat = restaurer(self.config, demande.get('sauvegarde'), demande.get('tables'))
        self.envoyer_json(200, resultat)

    # --- Fichiers statiques ------------------------------------------------

    def servir_statique(self, morceaux):
        """Sert un fichier de la liste blanche (index.html, favicon.svg, GUIDE.html, css/, js/ ;
        tests/fixtures/ avec --servir-tests). Jamais donnees/ ni les fichiers cachés."""
        if morceaux == ['']:
            morceaux = ['index.html']
        if morceaux[0].lower() == 'donnees':
            raise ErreurHttp(403, 'Accès refusé.')
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
        self.envoyer(200, octets, TYPES_STATIQUES.get(extension(chemin), TYPE_PAR_DEFAUT))

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

    def envoyer_json(self, statut, donnees):
        octets = json.dumps(donnees, ensure_ascii=False).encode('utf-8')
        self.envoyer(statut, octets, 'application/json; charset=utf-8')

    def envoyer_erreur(self, erreur):
        donnees = {'erreur': erreur.message}
        donnees.update(erreur.champs_supplementaires)
        if not getattr(self, 'corps_lu', False):
            self.close_connection = True     # le corps n'a pas (entièrement) été lu
        self.envoyer_json(erreur.statut, donnees)


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

    def __init__(self, adresse, config):
        self.config = config
        super().__init__(adresse, GestionnaireRequetes)

    def get_request(self):
        """https (lot 4) : la connexion acceptée est enveloppée en TLS ; la poignée de main est faite
        plus tard, dans le fil de la requête (GestionnaireRequetes.setup)."""
        connexion, adresse = self.socket.accept()
        if self.config.contexte_ssl is not None:
            connexion = self.config.contexte_ssl.wrap_socket(connexion, server_side=True, do_handshake_on_connect=False)
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


def demarrer_serveur(port_demande, config):
    """Ouvre le premier port libre à partir de port_demande (jusqu'à +20)."""
    derniere_erreur = None
    port_maximum = min(port_demande + NOMBRE_PORTS_SUPPLEMENTAIRES, 65535)
    for port in range(port_demande, port_maximum + 1):
        try:
            return ServeurPrevo(('0.0.0.0', port), config), port
        except OSError as erreur:
            derniere_erreur = erreur
    raise SystemExit('Impossible d\'ouvrir un port entre %d et %d (%s).'
                     % (port_demande, port_maximum, derniere_erreur))


def afficher_accueil(config, port_demande):
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
    afficher('  Ctrl+C pour arrêter.')
    afficher('  Attention : usage réseau local uniquement, aucune authentification.')


def lire_arguments(arguments=None):
    analyseur = argparse.ArgumentParser(
        description='Serveur local de la GMAO Prévo. Sert index.html, favicon.svg, '
                    'GUIDE.html, css/ et js/ ; tout autre fichier répond 404.')
    analyseur.add_argument('--port', type=int, default=PORT_PAR_DEFAUT,
                           help='port d\'écoute (défaut 8080 ; le suivant si occupé)')
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
    analyseur.add_argument('--servir-tests', action='store_true',
                           help='servir aussi tests/fixtures/ (pages des tests automatiques ; '
                                'inutile en usage normal)')
    options = analyseur.parse_args(arguments)
    if not 1 <= options.port <= 65535:
        analyseur.error('le port doit être compris entre 1 et 65535')
    if bool(options.certificat) != bool(options.cle):
        analyseur.error('--certificat et --cle vont ensemble : donnez les deux fichiers PEM '
                        '(certificat et clé privée) pour passer en https')
    return options


def main(arguments=None):
    preparer_console()
    options = lire_arguments(arguments)
    config = Configuration(options.donnees, options.hote, options.servir_tests)
    if options.certificat:
        config.contexte_ssl = creer_contexte_ssl(options.certificat, options.cle)
    creer_dossiers(config)
    serveur, config.port = demarrer_serveur(options.port, config)
    afficher_accueil(config, options.port)
    if not options.sans_navigateur:
        webbrowser.open(config.adresse_locale())
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        afficher('Serveur arrêté.')
    finally:
        serveur.server_close()


if __name__ == '__main__':
    main()
