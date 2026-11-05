# -*- coding: utf-8 -*-
"""Extraction des textes visibles de Prévo vers js/i18n/fr.js (chantier i18n, Lot 2, T236).

Bibliothèque standard seulement. Depuis la racine du dépôt :
  py -X utf8 outils/extraire_textes.py --section planning js/modules/planning-ecrans.js [autres fichiers…]
  py -X utf8 outils/extraire_textes.py --domaine planning --essai
Options :
  --essai              rien n'est écrit : seulement le rapport de ce qui serait fait ;
  --dictionnaire CHEM  dictionnaire à compléter (défaut js/i18n/fr.js ; js/i18n/aide/fr.js pour l'aide longue,
                       domaine à part « aide-longue » : js/modules/aide-ecrans-textes.js) ;
  --commun             un texte répété dans plusieurs domaines prend une clé commun.* (section commun) ;
  --commun-existant    un texte identique à une valeur de la section commun reprend sa clé, sans jamais créer de
                       clé commun.* (domaines extraits en parallèle, T257) ; chaque reprise est listée au rapport,
                       pour vérifier même sens ET même rôle (sinon : clé du domaine, à la main) ;
  --rapport CHEM       écrit aussi le rapport dans ce fichier ; --racine, --exceptions : pour les essais.

Ce que fait l'outil (contrat du Lot 2, .chantier) :
- chaque texte visible devient I18n.t('<clé>', { … }) (texte brut) ou I18n.html('<clé>', { … }) (phrase avec du
  balisage au milieu, dans un gabarit UI.html), et sa valeur est écrite, triée, dans le bloc de la section du
  dictionnaire. La valeur est le texte d'avant à l'octet près, échappements compris ;
- gabarits : chaque ${expr} d'une phrase devient {nom} et l'appel passe { nom: expr } ; phrases coupées par
  concaténation : regroupées en une clé ; pluriels locaux (« (s) », « > 1 ? 's' : '' », petites fonctions
  pluriel(n, mot)) : une entrée { one, other } et la variable n ;
- ce qui figure dans outils/exceptions_textes.json n'est jamais extrait ;
- rien n'est deviné : tout cas incertain va au rapport de relecture (fichier, ligne, texte, raison) sans être
  réécrit (texte figé au chargement d'un module, texte comparé ou calculé, choix de mots au milieu d'une phrase,
  HTML compliqué, pluriel incertain…) ;
- déterministe : fichiers triés, clés attribuées dans l'ordre des fichiers et des positions ; un second passage ne
  trouve plus rien et ne change plus aucun octet.
outils/controler_textes.py reprend le même classement (textes restés en dur, critère CS147).
"""
import argparse
import fnmatch
import html
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

ICI = Path(__file__).resolve().parent
if str(ICI) not in sys.path:
    sys.path.insert(0, str(ICI))
from jslex import (FERMANT, MOTS_CLES, ErreurAnalyse, Groupe, Jeton, Lignes,  # noqa: E402
                   construire_arbre, decoder, nom_appele, normaliser)

RACINE_DEPOT = ICI.parent
DICTIONNAIRE = 'js/i18n/fr.js'
EXCEPTIONS = 'outils/exceptions_textes.json'

# ---------------------------------------------------------------------------------------------------------
# Sections du dictionnaire et domaines (lien domaine → fichiers, partagé avec controler_textes.py)
# ---------------------------------------------------------------------------------------------------------
SECTIONS = ('commun', 'schema', 'valeurs', 'socle', 'planning', 'causes', 'dictee', 'mise', 'aide', 'ordres',
            'demandes', 'parc', 'preventif', 'controles', 'wiki', 'suggestions', 'import', 'magasin',
            'indicateurs', 'rapport', 'accueil', 'equipe', 'acces', 'connexion', 'poste', 'apropos',
            'installation', 'porte', 'parametres', 'sauvegardes', 'zip', 'serveur', 'ia')
# Domaine d'un module js/modules/<préfixe>-….js ou <préfixe>.js : son préfixe, sauf ceux-là.
MODULES_PARTICULIERS = {'parametres-sauvegardes.js': 'sauvegardes', 'parametres-zip.js': 'zip',
                        'aide-ecrans-textes.js': 'aide-longue'}
# Domaines qui ne sont pas une section de fr.js : domaine → (section, dictionnaire). L'aide longue générée
# (aide-ecrans-textes.js) va dans js/i18n/aide/fr.js (clés aide.*, T247) : un domaine à part, pour que le contrôle
# du domaine « aide » (aide courte, aide-ecrans.js) ne la compte pas (T237).
DOMAINES_A_PART = {'aide-longue': ('aide', 'js/i18n/aide/fr.js')}
DOMAINES = SECTIONS + tuple(sorted(DOMAINES_A_PART))
# Fichiers hors de js/modules (le socle et deux domaines à part).
FICHIERS_HORS_MODULES = {
    'socle': ('index.html', 'js/app.js', 'js/interface.js', 'js/donnees.js', 'js/formats.js', 'js/prechargement.js',
              'js/stockage-demo.js', 'js/stockage-dossier.js', 'js/stockage-serveur.js', 'js/i18n.js'),
    'schema': ('js/schema.js',),
    'porte': ('acces/porte.js', 'acces/porte.html'),
}
# Domaine pilote du Lot 2 (planning, causes fréquentes, dictée, mise à jour, aide).
DOMAINE_PILOTE = ('planning', 'causes', 'dictee', 'mise', 'aide')


def section_du_domaine(domaine):
    """Section du dictionnaire où vont les textes d'un domaine (le domaine lui-même, sauf DOMAINES_A_PART)."""
    return DOMAINES_A_PART[domaine][0] if domaine in DOMAINES_A_PART else domaine


def dictionnaire_du_domaine(domaine):
    """Dictionnaire que complètent les textes d'un domaine (js/i18n/fr.js, sauf DOMAINES_A_PART)."""
    return DOMAINES_A_PART[domaine][1] if domaine in DOMAINES_A_PART else DICTIONNAIRE


def domaine_du_fichier(rel):
    """Domaine (section de fr.js, ou domaine à part) d'un fichier du dépôt, ou None (données de démo, bibliothèques,
    dictionnaires)."""
    rel = rel.replace('\\', '/')
    for domaine, fichiers in FICHIERS_HORS_MODULES.items():
        if rel in fichiers:
            return domaine
    if rel.startswith('js/modules/') and rel.endswith('.js') and rel.count('/') == 2:
        nom = rel.rsplit('/', 1)[1]
        if nom in MODULES_PARTICULIERS:
            return MODULES_PARTICULIERS[nom]
        prefixe = nom[:-3].split('-', 1)[0]
        return prefixe if prefixe in SECTIONS else None
    return None


def fichiers_du_domaine(racine, domaine):
    """Fichiers existants d'un domaine, triés (chemins relatifs à la racine, barres obliques)."""
    racine = Path(racine)
    res = [f for f in FICHIERS_HORS_MODULES.get(domaine, ()) if (racine / f).is_file()]
    dossier = racine / 'js' / 'modules'
    if dossier.is_dir():
        for chemin in sorted(dossier.glob('*.js')):
            rel = 'js/modules/' + chemin.name
            if domaine_du_fichier(rel) == domaine:
                res.append(rel)
    return sorted(set(res))


def tous_les_fichiers(racine):
    """{domaine: [fichiers]} pour tous les domaines qui ont des fichiers."""
    res = {}
    for domaine in DOMAINES:
        fichiers = fichiers_du_domaine(racine, domaine)
        if fichiers:
            res[domaine] = fichiers
    return res


# ---------------------------------------------------------------------------------------------------------
# Classement des textes (repris de l'inventaire du Lot 0, inventaire.py)
# ---------------------------------------------------------------------------------------------------------
ACCENTS = 'àâäçéèêëîïôöùûüÿœæÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŸŒÆ«»…’'
RE_ACCENT = re.compile('[' + ACCENTS + ']')
RE_LETTRE = re.compile(r'[A-Za-z' + ACCENTS + ']')
RE_MOT = re.compile(r"[A-Za-zÀ-ÿœŒæÆ][A-Za-zÀ-ÿœŒæÆ'’\-]*")
RE_BALISE = re.compile(r'<(/?)([a-zA-Z][\w-]*)((?:[^>"\']|"[^"]*"|\'[^\']*\')*)>', re.S)
RE_SELECTEUR = re.compile(r"^[\w\-#.\[\]=\"':()>*+~^$|, ]+$")
RE_SVG = re.compile(r'^[MLHVCSQTAZmlhvcsqtaz0-9.,\s\-]+$')
RE_CSS = re.compile(r'^\s*[a-z\-]+\s*:\s*[^;]+;?(\s*[a-z\-]+\s*:\s*[^;]+;?)*\s*$')
RE_MIME = re.compile(r'^[a-z]+/[a-z0-9.+\-]+(;.*)?$')
RE_IDENT = re.compile(r'^[A-Za-z_$][\w$\-.:/]*$')
RE_ABREVIATION = re.compile(r'^[a-zà-ÿ]{2,6}\.$')
MOTS_TECHNIQUES = {'Enter', 'Escape', 'Tab', 'Backspace', 'Delete', 'Home', 'End', 'Space', 'Shift', 'Control',
                   'Alt', 'Meta', 'Error', 'Object', 'Promise', 'Array', 'Infinity', 'Math', 'Prevo', 'Function',
                   'Symbol', 'String', 'Number', 'Boolean', 'Map', 'Set', 'Spacebar', 'Esc', 'Unidentified',
                   'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'PageUp', 'PageDown', 'GET', 'POST', 'PUT',
                   'DELETE', 'HEAD', 'OPTIONS', 'UTF', 'NaN'}
CLES_CLASSE = {'classe', 'className', 'class', 'ton', 'icone', 'cls'}
CLES_TECHNIQUES = {'classe', 'className', 'class', 'type', 'mime', 'cle', 'id', 'nom', 'table', 'champ', 'ecran',
                   'route', 'icone', 'ton', 'href', 'adresse', 'url', 'chemin', 'fichier', 'cible', 'selecteur',
                   'methode', 'valeur', 'mode', 'format', 'accept', 'autocomplete', 'inputmode', 'name',
                   'contentType', 'extension', 'pattern', 'ancre', 'profil', 'famille'}
RE_APPELS_TECHNIQUES = re.compile(
    r'(querySelector(All)?|closest|matches|getElementById|getElementsBy\w+|\$\$?|classList\.\w+|addEventListener|'
    r'removeEventListener|getAttribute|removeAttribute|hasAttribute|toggleAttribute|createElement\w*|getItem|'
    r'setItem|removeItem|dispatchEvent|CustomEvent|Event|fetch|appel\w*Api|api\w*|require|importScripts|'
    r'getPropertyValue|setProperty|insertAdjacentHTML|split|join|replace\w*|startsWith|endsWith|includes|indexOf|'
    r'RegExp|localeCompare|padStart|padEnd|toLocale\w+String|Intl\.\w+|Collator|NumberFormat|DateTimeFormat|'
    r'lireParametre|parametre|encodeURIComponent|decodeURIComponent|URL|URLSearchParams|Blob|File|has|get|set|'
    r'delete)$')
RE_ENVELOPPES_ERREUR = re.compile(r'(Error|Erreur\w*|ErreurApi|TypeError|RangeError)$')
# Appels dont l'argument est une valeur cherchée, comparée ou une clé : un texte visible y est signalé, jamais
# réécrit (traduire l'argument changerait ce que fait le code). Valeur : rangs d'arguments concernés (None : tous).
APPELS_VALEUR = {'includes': None, 'startsWith': None, 'endsWith': None, 'indexOf': None, 'lastIndexOf': None,
                 'split': None, 'match': None, 'matchAll': None, 'search': None, 'has': None, 'localeCompare': None,
                 'get': (0,), 'set': (0,), 'delete': None, 'replace': (0,), 'replaceAll': (0,)}
# Appels dont l'argument n'est jamais un texte affiché (sélecteur, nom d'événement, clé de stockage…) : silence.
APPELS_TECHNIQUES = {'querySelector': None, 'querySelectorAll': None, 'closest': None, 'matches': None,
                     'getElementById': None, 'getAttribute': None, 'hasAttribute': None, 'removeAttribute': None,
                     'toggleAttribute': None, 'setAttribute': (0,), 'createElement': None, 'addEventListener': (0,),
                     'removeEventListener': (0,), 'dispatchEvent': None, 'CustomEvent': (0,), 'Event': (0,),
                     'RegExp': None, 'padStart': None, 'padEnd': None, 'getPropertyValue': None, 'setProperty': None,
                     'matchMedia': None, 'getItem': None, 'setItem': (0,), 'removeItem': None}
COMPARAISONS = {'===', '!==', '==', '!=', '<', '>', '<=', '>=', 'case', 'in', 'instanceof'}
ATTRIBUTS_VISIBLES = ('title', 'placeholder', 'aria-label', 'alt', 'label', 'aria-description',
                      'aria-roledescription', 'aria-placeholder', 'aria-valuetext', 'data-titre')
# Balises « en ligne » : elles restent dans la phrase (I18n.html) ; les autres coupent les textes.
BALISES_EN_LIGNE = {'a', 'abbr', 'b', 'bdi', 'bdo', 'br', 'cite', 'code', 'data', 'dfn', 'em', 'i', 'kbd', 'mark',
                    'q', 's', 'samp', 'small', 'span', 'strong', 'sub', 'sup', 'time', 'u', 'var', 'wbr'}
BALISES_VIDES = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr'}
# Caractères écrits par leur échappement dans fr.js (test_depot refuse les invisibles en clair).
INVISIBLES = {' ', ' ', ' ', '​', '‌', '‍', '⁠', '﻿', '­', ' ',
              ' ', ' ', ' ', ' '}
PONCTUATION_FIN = '.!?:;…'
CATEGORIES_PLURIEL = ('zero', 'one', 'two', 'few', 'many', 'other')
# Saut de ligne de mise en page (avec les espaces et tabulations qui l'entourent) dans un texte entre balises d'un
# gabarit UI.html : rendu comme une espace (white-space normal) ; jamais dans <pre> ni <textarea>.
RE_SAUT_DE_MISE_EN_PAGE = re.compile(r'[ \t]*\n[ \t\n]*')
BALISES_ESPACES_GARDES = {'pre', 'textarea', 'listing', 'plaintext', 'xmp'}
SENTINELLE = 0xE000           # ${…} d'un gabarit pendant le découpage HTML (zone d'usage privé)
FORMATEURS = {'dateFr', 'nombreFr', 'heures', 'texte', 'String', 'Number', 'dateHeureFr', 'montantFr', 'heureFr',
              'echapper', 'trim', 'nombre', 'pourcentage', 'montant'}
NOMS_GENERIQUES = {'id', 'length', 'value', 'nom', 'libelle', 'texte', 'titre', 'message', 'code', 'valeur',
                   'type', 'statut', 'size', 'count'}
MOTS_VIDES = {'le', 'la', 'les', 'l', 'de', 'du', 'des', 'd', 'un', 'une', 'et', 'ou', 'a', 'à', 'au', 'aux', 'en',
              'pour', 'par', 'sur', 'dans', 'ce', 'cet', 'cette', 'ces', 'se', 'sa', 'son', 'ses', 'qui', 'que',
              'qu', 'ne', 'n', 'est', 'il', 'elle', 'on', 'y', 's', 'c', 'j', 'm', 't', 'vous', 'nous', 'votre',
              'vos', 'notre', 'nos', 'leur', 'leurs', 'avec'}


def nettoyer(s):
    s = html.unescape(s)
    return re.sub(r'\s+', ' ', s).strip()


def lire_schema(racine):
    """Colonnes CSV, valeurs stockées des listes (D155) et noms de fichiers lus dans js/schema.js."""
    chemin = Path(racine) / 'js' / 'schema.js'
    if not chemin.is_file():
        return set(), set(), set()
    src = chemin.read_text(encoding='utf-8')
    colonnes = set(re.findall(r"(?:champ|choix|reference|codeDefaillance|booleen)\('([a-z_0-9]+)'", src))
    colonnes |= {'id', 'actif'}
    valeurs = set()
    for m in re.finditer(r"choix\('[a-z_]+',\s*'[^']*',\s*(\[[^\]]*\]|[A-Z_]+)", src, re.S):
        if m.group(1).startswith('['):
            valeurs |= set(re.findall(r"'([^']*)'", m.group(1)))
    for nom in ('CRITICITES', 'PRIORITES'):
        m = re.search(nom + r"\s*=\s*\[([^\]]*)\]", src)
        if m:
            valeurs |= set(re.findall(r"'([^']*)'", m.group(1)))
    fichiers = set(re.findall(r"fichier: '([^']+)'", src))
    return colonnes, valeurs, fichiers


class Classement:
    """Visible ou technique, et exceptions justifiées (outils/exceptions_textes.json) : partagé par les deux outils."""

    def __init__(self, racine, chemin_exceptions=None):
        self.racine = Path(racine)
        self.colonnes, self.valeurs, self.fichiers_csv = lire_schema(racine)
        chemin = Path(chemin_exceptions) if chemin_exceptions else self.racine / EXCEPTIONS
        if not chemin.is_file():
            chemin = RACINE_DEPOT / EXCEPTIONS
        self.exceptions = json.loads(chemin.read_text(encoding='utf-8'))
        regles = {r['regle']: r for r in self.exceptions.get('regles', [])}
        self.regle_valeurs = regles.get('valeurs-schema')

    @staticmethod
    def _fichier_concerne(regle, rel):
        motifs = regle.get('fichiers')
        return not motifs or any(fnmatch.fnmatchcase(rel, m) for m in motifs)

    def exception_fichier(self, rel):
        for regle in self.exceptions.get('fichiers', []):
            if fnmatch.fnmatchcase(rel, regle['chemin']):
                return regle
        return None

    def exception_contexte(self, rel, ctx):
        """Règle d'exception qui couvre cet endroit du code (appel englobant, clé d'objet), ou None."""
        for regle in self.exceptions.get('appels', []):
            if not self._fichier_concerne(regle, rel):
                continue
            for nom, rang in ctx.appels:
                if nom and fnmatch.fnmatchcase(nom, regle['appel']) and \
                        (regle.get('argument') is None or regle['argument'] == rang):
                    return regle
        for regle in self.exceptions.get('variables', []):
            if self._fichier_concerne(regle, rel) and ctx.variable == regle['variable']:
                return regle
        for regle in self.exceptions.get('cles', []):
            if not self._fichier_concerne(regle, rel) or ctx.cle != regle['cle']:
                continue
            if regle.get('appel') and not any(nom and fnmatch.fnmatchcase(nom, regle['appel'])
                                              for nom, _ in ctx.appels):
                continue
            return regle
        return None

    def exception_texte(self, rel, texte):
        t = texte.strip()
        for regle in self.exceptions.get('textes', []):
            if regle['texte'].strip() == t and self._fichier_concerne(regle, rel):
                return regle
        if self.regle_valeurs and t in self.valeurs:
            return self.regle_valeurs
        return None

    def technique(self, t):
        """Vrai (raison) si la chaîne (sans HTML) ressemble à du code plutôt qu'à du texte."""
        s = t.strip()
        if not s:
            return 'vide'
        if not RE_LETTRE.search(s):
            return 'sans lettre'
        if s == 'use strict':
            return 'directive'
        if re.match(r'^(https?:|file:|data:|mailto:|tel:|blob:|/api/|/acces/|\./|\.\./|js/|css/|i18n/|#/)', s):
            return 'url'
        if RE_MIME.match(s):
            return 'mime'
        if s in self.colonnes or s in self.fichiers_csv:
            return 'colonne csv'
        if RE_ACCENT.search(s) is None:
            if RE_SVG.match(s) and re.search(r'\d', s):
                return 'svg'
            if RE_CSS.match(s) and ':' in s:
                return 'css'
            if RE_SELECTEUR.match(s) and re.search(r'(^|[\s,>(])[.#\[]|:not\(|:checked|\[data-|\[name=|\[aria-', s):
                return 'selecteur'
            if RE_IDENT.match(s) and not RE_ABREVIATION.match(s):
                return 'identifiant'
            if re.match(r'^[a-z0-9_\-]+( [a-z0-9_\-]+)+$', s) and '-' in s:
                return 'classes css'
            if re.match(r'^\d', s) and re.match(r'^[\d.,%\s\w()+-]+$', s) and len(RE_MOT.findall(s)) <= 2:
                return 'mesure'
        return None

    def visible_js(self, t, brut, ctx):
        """Texte d'une chaîne JS (sans HTML) visible à l'écran ? (classes texte, mot isolé, fragment, erreur)."""
        t = t.strip()
        sans = re.sub(r'\s+', ' ', t.replace('{}', ' ')).strip(' .,:;!?()[]«»–—-/|•·')
        if not sans or not RE_LETTRE.search(sans):
            return False
        appel = (ctx.appels[-1][0] if ctx.appels else '') or ''
        cle = ctx.cle_directe or ''
        tech = self.technique(t.replace('{}', 'x'))
        if tech:
            if tech == 'identifiant' and re.match(r'^[A-ZÀ-Ý][a-zà-ÿ]+$', sans) and sans not in MOTS_TECHNIQUES \
                    and cle not in CLES_TECHNIQUES:
                return True                                      # mot isolé (« Statut »)
            if tech == 'identifiant' and re.match(r'^[a-zà-ÿ]+$', sans) and (brut[:1] == ' ' or brut[-1:] == ' ') \
                    and cle not in CLES_CLASSE and 'classList' not in appel:
                return True                                      # fragment de phrase (« le », « h »)
            return False
        if RE_APPELS_TECHNIQUES.search(appel) and not RE_ACCENT.search(t) and not re.search(r'[A-Z].* ', t):
            return False
        if cle in CLES_TECHNIQUES and not RE_ACCENT.search(t) and not re.match(r'^[A-ZÀ-Ý]', t):
            return False
        if RE_ENVELOPPES_ERREUR.search(appel):
            return True
        if re.search(r'\s', sans) or RE_ACCENT.search(t) or RE_ABREVIATION.match(t):
            return True
        return bool(re.match(r'^[A-ZÀ-Ý][a-zà-ÿ]+$', sans))

    def visible_html(self, t):
        """Texte entre balises (ou valeur d'attribut visible) : visible sauf s'il ressemble à du code."""
        t = t.strip()
        sans = t.replace('{}', '').strip()
        if not sans or not RE_LETTRE.search(sans):
            return False
        tech = self.technique(t)
        return not tech or (tech == 'identifiant' and bool(re.match(r'^[A-ZÀ-Ýa-zà-ÿ]', t)))


# ---------------------------------------------------------------------------------------------------------
# Petits outils
# ---------------------------------------------------------------------------------------------------------

def est_ponct(n, *valeurs):
    return isinstance(n, Jeton) and n.genre == 'ponct' and (not valeurs or n.valeur in valeurs)


def est_nom(n, *valeurs):
    return isinstance(n, Jeton) and n.genre == 'nom' and (not valeurs or n.valeur in valeurs)


def est_groupe(n, ouvrant=None):
    return isinstance(n, Groupe) and (ouvrant is None or n.ouvrant == ouvrant)


def est_nom_libre(n):
    return isinstance(n, Jeton) and n.genre == 'nom' and n.valeur not in MOTS_CLES


def vers_simple(brut, guillemet):
    """Contenu brut d'un littéral ('…', "…" ou `…`) réécrit pour une chaîne entre apostrophes, échappements gardés.
    Rend None pour une continuation de ligne (barre oblique inverse en fin de ligne)."""
    out = []
    i = 0
    n = len(brut)
    while i < n:
        c = brut[i]
        if c == '\\':
            suivant = brut[i + 1] if i + 1 < n else ''
            if suivant in ('\n', '\r', ''):
                return None
            out.append(brut[i:i + 2])
            i += 2
            continue
        if c == "'":
            out.append("\\'")
        elif c == '\n':
            out.append('\\n')
        elif c == '\r':
            out.append('\\r')
        elif c == '\t':
            out.append('\\t')
        elif c in INVISIBLES or ord(c) < 0x20:
            out.append('\\u%04x' % ord(c))
        else:
            out.append(c)
        i += 1
    return ''.join(out)


def echapper_texte(texte):
    """Texte décodé (HTML de index.html) écrit pour une chaîne entre apostrophes."""
    out = []
    for c in texte:
        if c == '\\':
            out.append('\\\\')
        elif c == "'":
            out.append("\\'")
        elif c == '\n':
            out.append('\\n')
        elif c == '\t':
            out.append('\\t')
        elif c == '\r':
            out.append('\\r')
        elif c in INVISIBLES or ord(c) < 0x20:
            out.append('\\u%04x' % ord(c))
        else:
            out.append(c)
    return ''.join(out)


def sans_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if not unicodedata.combining(c))


def serpent(nom):
    """carteOt → carte_ot ; afficherRefus → afficher_refus."""
    s = re.sub(r'(?<=[a-z0-9])([A-Z])', r'_\1', nom)
    s = sans_accents(s).lower()
    return re.sub(r'[^a-z0-9]+', '_', s).strip('_')


def resume(valeur):
    """Élément de clé : jusqu'à quatre mots significatifs du texte (variables comprises s'il en a moins de deux)."""
    if isinstance(valeur, dict):
        valeur = valeur.get('other') or next(iter(valeur.values()))
    t = decoder(valeur)
    t = re.sub(r'<[^>]*>', ' ', t)
    t = re.sub(r'&[#\w]+;', ' ', t)
    jetons = re.findall(r'\{(\w+)\}|([^\W\d_]+|\d+)', t)
    pleins = [m for v, m in jetons if m and m.lower() not in MOTS_VIDES]
    if len(pleins) >= 2:
        mots = pleins[:4]
    else:
        mots = [serpent(v) if v else m for v, m in jetons if v or (m and m.lower() not in MOTS_VIDES)][:4]
        if not mots:
            mots = [m for v, m in jetons if m][:4]
    element = '_'.join(serpent(m) for m in mots)
    element = re.sub(r'_+', '_', element).strip('_')
    return element or 'texte'


def nom_composant(cadres, rel, section):
    """Écran ou composant : la fonction nommée la plus extérieure (hors module), sinon le nom du fichier."""
    for cadre in cadres:
        if cadre.differe and cadre.nom:
            nom = serpent(cadre.nom)
            nom = re.sub(r'_html$', '', nom)
            if nom == 'afficher':
                return 'ecran'
            nom = re.sub(r'^afficher_', '', nom)
            return nom or 'ecran'
    base = rel.rsplit('/', 1)[-1].rsplit('.', 1)[0]
    if '-' in base:
        base = base.split('-', 1)[1]
    base = serpent(base)
    return base if base and base != section else 'module'


def canon(valeur):
    return tuple(sorted(valeur.items())) if isinstance(valeur, dict) else valeur


def affichage(valeur):
    """Valeur de fr.js lisible dans le rapport (une ligne)."""
    if isinstance(valeur, dict):
        return '{ ' + ', '.join("%s: '%s'" % (k, valeur[k]) for k in CATEGORIES_PLURIEL if k in valeur) + ' }'
    return "'" + valeur + "'"


def court(texte, n=140):
    texte = re.sub(r'\s+', ' ', texte).strip()
    return texte if len(texte) <= n else texte[:n - 1] + '…'


# ---------------------------------------------------------------------------------------------------------
# Découpage HTML (gabarits UI.html avec sentinelles, index.html)
# ---------------------------------------------------------------------------------------------------------
RE_NOM_BALISE = re.compile(r'[A-Za-z][\w:-]*')
RE_NOM_ATTRIBUT = re.compile(r'[^\s=>/"\'-]+')


class Element:
    """Morceau de HTML : genre 'texte', 'balise', 'commentaire', 'brut' (contenu de script/style)."""
    __slots__ = ('genre', 'a', 'b', 'nom', 'fermante', 'attrs', 'fin_nom')

    def __init__(self, genre, a, b, nom=None, fermante=False, attrs=None, fin_nom=None):
        self.genre = genre
        self.a = a
        self.b = b
        self.nom = nom
        self.fermante = fermante
        self.attrs = attrs or []
        self.fin_nom = fin_nom


def _lire_balise(t, i):
    """Balise qui commence en t[i] == '<' : Element ou None si elle n'est pas lisible."""
    fermante = t.startswith('</', i)
    m = RE_NOM_BALISE.match(t, i + (2 if fermante else 1))
    if not m:
        return None
    j = m.end()
    attrs = []
    n = len(t)
    while j < n:
        while j < n and t[j] in ' \t\r\n':
            j += 1
        if j >= n:
            return None
        if t[j] == '>':
            return Element('balise', i, j + 1, m.group(0).lower(), fermante, attrs, m.end())
        if t.startswith('/>', j):
            return Element('balise', i, j + 2, m.group(0).lower(), fermante, attrs, m.end())
        if '' <= t[j] <= '':
            attrs.append((None, j, j + 1))
            j += 1
            continue
        ma = RE_NOM_ATTRIBUT.match(t, j)
        if not ma:
            return None
        nom = ma.group(0).lower()
        j = ma.end()
        k = j
        while k < n and t[k] in ' \t\r\n':
            k += 1
        if k < n and t[k] == '=':
            k += 1
            while k < n and t[k] in ' \t\r\n':
                k += 1
            if k < n and t[k] in '"\'':
                fin = t.find(t[k], k + 1)
                if fin < 0:
                    return None
                attrs.append((nom, k + 1, fin))
                j = fin + 1
            else:
                mv = re.compile(r'[^\s>]+').match(t, k)
                if not mv:
                    return None
                attrs.append((nom, mv.start(), mv.end()))
                j = mv.end()
        else:
            attrs.append((nom, None, None))
    return None


def decouper_html(t):
    """Liste d'Element (textes, balises, commentaires) ou None si le HTML n'est pas lisible simplement."""
    elements = []
    i = 0
    n = len(t)
    debut_texte = 0

    def vider(jusque):
        if jusque > debut_texte:
            elements.append(Element('texte', debut_texte, jusque))

    while i < n:
        if t[i] != '<':
            i += 1
            continue
        if t.startswith('<!--', i):
            j = t.find('-->', i + 4)
            if j < 0:
                return None
            vider(i)
            elements.append(Element('commentaire', i, j + 3))
            i = debut_texte = j + 3
            continue
        if t.startswith('<!', i):
            j = t.find('>', i)
            if j < 0:
                return None
            vider(i)
            elements.append(Element('commentaire', i, j + 1))
            i = debut_texte = j + 1
            continue
        if i + 1 < n and (t[i + 1].isalpha() or t[i + 1] == '/'):
            balise = _lire_balise(t, i)
            if balise is None:
                return None
            vider(i)
            elements.append(balise)
            i = debut_texte = balise.b
            if not balise.fermante and balise.nom in ('script', 'style'):
                fin = t.lower().find('</' + balise.nom, i)
                if fin < 0:
                    return None
                if fin > i:
                    elements.append(Element('brut', i, fin))
                i = debut_texte = fin
            continue
        i += 1
    vider(n)
    return elements


# ---------------------------------------------------------------------------------------------------------
# Morceaux d'une phrase
# ---------------------------------------------------------------------------------------------------------

class Morceau:
    """txt (brut, guillemet) ; var (noeuds de l'expression) ; choix (pluriel : compte, un, autre) ; bar (gardé hors
    de la phrase : choix de textes, fragment HTML, balise à variable) ; balise (balisage gardé dans la valeur)."""
    __slots__ = ('genre', 'brut', 'guillemet', 'noeuds', 'debut', 'fin', 'a', 'b', 'un', 'autre', 'compte',
                 'nom', 'fermante', 'partenaire', 'op', 'force_n', 'k', 'espaces')

    def __init__(self, genre, **kw):
        self.genre = genre
        for cle in self.__slots__[1:]:
            setattr(self, cle, kw.get(cle))


class Cadre:
    __slots__ = ('nom', 'differe')

    def __init__(self, nom, differe):
        self.nom = nom
        self.differe = differe


class Ctx:
    """Où l'on se trouve : fonctions englobantes, appels englobants (nom, rang d'argument), clé d'objet."""
    __slots__ = ('cadres', 'appels', 'cle', 'cle_directe', 'appel_en_cours', 'groupe', 'suivi_appel', 'direct',
                 'variable')

    def __init__(self, cadres=(), appels=(), cle=None, cle_directe=None, appel_en_cours=None, groupe=None,
                 suivi_appel=False, direct=False, variable=None):
        self.cadres = cadres            # fonctions englobantes (Cadre), de l'extérieur vers l'intérieur
        self.appels = appels            # appels englobants : (nom appelé, rang de l'argument)
        self.cle = cle                  # clé d'objet la plus proche (transmise aux expressions incluses)
        self.cle_directe = cle_directe  # clé d'objet dont on est directement la valeur
        self.appel_en_cours = appel_en_cours  # (suite d'arguments d'un appel) nom appelé
        self.groupe = groupe            # ouvrant du groupe de la suite : '(', '[', '{' ou None
        self.suivi_appel = suivi_appel  # groupe ( … ) suivi d'un appel : (() => { … })()
        self.direct = direct            # directement argument du dernier appel de « appels »
        self.variable = variable        # variable qui reçoit la valeur (const action = …)

    def avec(self, **kw):
        valeurs = {cle: getattr(self, cle) for cle in self.__slots__}
        valeurs.update(kw)
        return Ctx(**valeurs)

    @property
    def fige(self):
        return not any(c.differe for c in self.cadres)


class Unite:
    """Texte extrait (avant attribution de la clé)."""
    __slots__ = ('fichier', 'position', 'ligne', 'section', 'composant', 'element', 'valeur', 'appel', 'texte',
                 'marqueur', 'cle', 'commun', 'original', 'vars')

    def __init__(self, **kw):
        for cle in self.__slots__:
            setattr(self, cle, kw.get(cle))


# Formes connues des petites fonctions pluriel locales (paramètres A = nombre, B = singulier, C = pluriel).
FORMES_PLURIEL = {
    'F1': ['A', '+', "' '", '+', '(', 'A', '>', '1', '?', '(', 'C', '||', 'B', '+', "'s'", ')', ':', 'B', ')'],
    'F2': ['A', '+', "' '", '+', 'B', '+', '(', 'A', '>', '1', '?', "'s'", ':', "''", ')'],
    'F3': ['A', '+', "' '", '+', 'B', '+', '(', 'Math', '.', 'abs', '(', 'A', ')', '>', '1', '?', "'s'", ':',
           "''", ')'],
    'F4': ['A', '+', "' '", '+', '(', 'A', '>', '1', '?', 'C', ':', 'B', ')'],
}


def jetons_plats(noeuds, remplacement=None):
    out = []
    for n in noeuds:
        if isinstance(n, Groupe):
            out.append(n.ouvrant)
            out.extend(jetons_plats(n.enfants, remplacement))
            out.append(FERMANT[n.ouvrant])
        elif n.genre == 'chaine':
            out.append("'" + decoder(n.valeur) + "'")
        elif n.genre == 'nom' and remplacement and n.valeur in remplacement:
            out.append(remplacement[n.valeur])
        else:
            out.append(n.valeur)
    return out


def couper_virgules(noeuds):
    parts, cur = [], []
    for n in noeuds:
        if est_ponct(n, ','):
            parts.append(cur)
            cur = []
        else:
            cur.append(n)
    parts.append(cur)
    return parts


def fonctions_pluriel(arbre):
    """{nom: forme} des fonctions pluriel locales du fichier dont le corps a une forme connue."""
    trouvees = {}

    def examiner(nom, params, corps):
        if not re.match(r'^plur', nom, re.I) or not 2 <= len(params) <= 3:
            return
        remplacement = dict(zip(params, 'ABC'))
        plats = jetons_plats(corps, remplacement)
        if plats[:1] == ['return']:
            plats = plats[1:]
        if plats[-1:] == [';']:
            plats = plats[:-1]
        for forme, modele in FORMES_PLURIEL.items():
            if plats == modele and (len(params) == 3 or forme in ('F2', 'F3')):
                trouvees[nom] = forme

    def parcourir(seq):
        for i, n in enumerate(seq):
            if isinstance(n, Groupe):
                parcourir(n.enfants)
            elif n.genre == 'gabarit':
                for sous, _, _ in n.exprs:
                    parcourir(sous)
            if est_nom(n, 'function') and i + 3 < len(seq) and est_nom_libre(seq[i + 1]) \
                    and est_groupe(seq[i + 2], '(') and est_groupe(seq[i + 3], '{'):
                params = [p[0].valeur for p in couper_virgules(seq[i + 2].enfants) if len(p) == 1 and est_nom(p[0])]
                if len(params) == len(couper_virgules(seq[i + 2].enfants)):
                    examiner(seq[i + 1].valeur, params, seq[i + 3].enfants)
            if est_nom(n, 'const', 'let', 'var') and i + 4 < len(seq) and est_nom_libre(seq[i + 1]) \
                    and est_ponct(seq[i + 2], '=') and est_groupe(seq[i + 3], '(') and est_ponct(seq[i + 4], '=>'):
                params = [p[0].valeur for p in couper_virgules(seq[i + 3].enfants) if len(p) == 1 and est_nom(p[0])]
                fin = i + 5
                while fin < len(seq) and not est_ponct(seq[fin], ';', ','):
                    fin += 1
                if len(params) == len(couper_virgules(seq[i + 3].enfants)):
                    examiner(seq[i + 1].valeur, params, seq[i + 5:fin])
    parcourir(arbre)
    return trouvees


# ---------------------------------------------------------------------------------------------------------
# Analyse et réécriture d'un fichier JS
# ---------------------------------------------------------------------------------------------------------
DELIM_PONCT = {',', ';', '?', ':', '=', '+=', '-=', '*=', '/=', '%=', '**=', '<<=', '>>=', '>>>=', '&=', '|=',
               '^=', '&&=', '||=', '??=', '==', '===', '!=', '!==', '<', '>', '<=', '>=', '&&', '||', '??', '=>',
               '&', '|', '^', '<<', '>>', '>>>', '...'}
DELIM_NOMS = {'return', 'throw', 'case', 'else', 'do', 'in', 'of', 'instanceof', 'yield', 'const', 'let', 'var',
              'if', 'while', 'for', 'switch', 'catch', 'class', 'extends', 'export', 'import', 'default', 'try',
              'finally', 'break', 'continue'}
FIN_OPERANDE_NOMS = {'this', 'super', 'null', 'true', 'false', 'undefined'}
RE_ATTRIBUTS_SEULS = re.compile(r'^\s*([\w-]+(="[^"]*")?\s*)*$')
APPELS_TABLEAU = {'map', 'filter', 'flatMap', 'concat', 'slice', 'split', 'sort', 'reverse', 'keys', 'values',
                  'entries'}
ETIQUETTES_HTML = ('UI.html', 'html')     # html`…` : le nom local de UI.html dans js/interface.js
APPELS_FRAGMENT = {'UI.brut', 'UI.vide', 'UI.icone', 'UI.element', 'UI.logo', 'I18n.html'}


def est_delimiteur(n):
    if not isinstance(n, Jeton):
        return False
    return (n.genre == 'ponct' and n.valeur in DELIM_PONCT) or (n.genre == 'nom' and n.valeur in DELIM_NOMS)


def fin_d_operande(n):
    if isinstance(n, Groupe):
        return n.ouvrant in '(['
    if n.genre in ('nombre', 'chaine', 'gabarit', 'regex'):
        return True
    if n.genre == 'nom':
        return n.valeur not in MOTS_CLES or n.valeur in FIN_OPERANDE_NOMS
    return n.valeur in ('++', '--')


def etiquette_gabarit(seq, i):
    """Nom placé devant un gabarit (« UI.html » pour UI.html`…`), ou None."""
    if i >= 1 and est_nom(seq[i - 1]):
        parties = [seq[i - 1].valeur]
        k = i - 2
        while k >= 1 and est_ponct(seq[k], '.') and est_nom(seq[k - 1]):
            parties.append(seq[k - 1].valeur)
            k -= 2
        return '.'.join(reversed(parties))
    return None


def contient_fragment(noeuds, fragments=(), fonctions=(), tableaux=False):
    """Vrai si l'expression produit (ou contient) un fragment HTML : UI.html`…`, UI.brut, UI.badge…, …Html(), l'appel
    ou la référence d'une fonction du dépôt qui rend un fragment (fonctions : noms simples), une variable qui en
    reçoit un (fragments). Avec tableaux (expression d'un gabarit UI.html) : aussi tout tableau (.map(), .filter(),
    [ … ]), que UI.html joint sans séparateur alors que I18n.t le joindrait par des virgules."""
    if len(noeuds) == 1 and est_nom(noeuds[0]) and noeuds[0].valeur in fragments:
        return True
    for i, n in enumerate(noeuds):
        if isinstance(n, Groupe):
            if contient_fragment(n.enfants, fragments, fonctions, tableaux):
                return True
            if n.ouvrant == '(':
                appel = nom_appele(noeuds, i) or ''
                dernier = appel.rsplit('.', 1)[-1]
                if appel in APPELS_FRAGMENT or appel.startswith('UI.badge') or re.search(r'(Html|HTML)$', dernier) \
                        or dernier in fonctions or (tableaux and dernier in APPELS_TABLEAU and '.' in appel):
                    return True
                if dernier in ('map', 'flatMap') and any(est_nom(x) and x.valeur in fonctions for x in n.enfants):
                    return True                              # .map(carte) : fonction qui rend un fragment
            elif n.ouvrant == '[' and tableaux and not (i >= 1 and fin_d_operande(noeuds[i - 1])):
                return True
        elif n.genre == 'gabarit':
            if etiquette_gabarit(noeuds, i) in ETIQUETTES_HTML:
                return True
            if any(contient_fragment(sous, fragments, fonctions, tableaux) for sous, _, _ in n.exprs):
                return True
        elif est_nom(n) and not (i >= 1 and est_ponct(noeuds[i - 1], '.', '?.')) \
                and not (i + 1 < len(noeuds) and (est_ponct(noeuds[i + 1], '.', '?.') or est_groupe(noeuds[i + 1], '('))):
            if n.valeur in fragments or re.search(r'.(Html|HTML)$', n.valeur):
                return True                                  # variable fragment ou fonction passée : .map(carteHtml)
    return False


def declarations(arbre):
    """[(nom, noeuds de la valeur)] des déclarations const/let/var NOM = … du fichier (toutes profondeurs)."""
    res = []

    def parcourir(seq):
        for i, n in enumerate(seq):
            if isinstance(n, Groupe):
                parcourir(n.enfants)
            elif n.genre == 'gabarit':
                for sous, _, _ in n.exprs:
                    parcourir(sous)
            if est_nom(n, 'const', 'let', 'var') and i + 2 < len(seq) and est_nom_libre(seq[i + 1]) \
                    and est_ponct(seq[i + 2], '='):
                fin = i + 3
                while fin < len(seq) and not est_ponct(seq[fin], ';', ','):
                    fin += 1
                res.append((seq[i + 1].valeur, seq[i + 3:fin]))
    parcourir(arbre)
    return res


def texte_de_branche(noeuds, valeurs):
    """Texte d'une branche de ternaire : littéral seul, ou I18n.t('clé') sans variable lu dans le dictionnaire."""
    if len(noeuds) == 1 and isinstance(noeuds[0], Jeton) and noeuds[0].genre == 'chaine':
        return decoder(noeuds[0].valeur)
    if len(noeuds) == 4 and est_nom(noeuds[0], 'I18n') and est_ponct(noeuds[1], '.') and est_nom(noeuds[2], 't') \
            and est_groupe(noeuds[3], '(') and len(noeuds[3].enfants) == 1 \
            and isinstance(noeuds[3].enfants[0], Jeton) and noeuds[3].enfants[0].genre == 'chaine':
        valeur = valeurs.get(decoder(noeuds[3].enfants[0].valeur))
        return decoder(valeur) if isinstance(valeur, str) else None
    return None


def mots_calcules(decls, valeurs):
    """Constantes qui reçoivent un mot choisi par le code (const verbe = x ? 'planifié' : 'replanifié'), avant comme
    après extraction (un I18n.t('clé') est lu dans le dictionnaire : un second passage voit la même chose)."""
    noms = set()
    for nom, valeur in decls:
        q = [k for k, x in enumerate(valeur) if est_ponct(x, '?')]
        c = [k for k, x in enumerate(valeur) if est_ponct(x, ':')]
        if len(q) == 1 and len(c) == 1 and q[0] < c[0]:
            mots = [texte_de_branche(b, valeurs) for b in (valeur[q[0] + 1:c[0]], valeur[c[0] + 1:])]
            if all(m is not None for m in mots):
                mots = [m.strip() for m in mots]
                if any(re.match(r'^[a-zà-ÿœæ]+$', m) for m in mots) and all(' ' not in m for m in mots):
                    noms.add(nom)
    return noms


def variables_fragments(decls, fonctions=()):
    """Constantes qui reçoivent un fragment HTML : jamais une variable de phrase."""
    noms = set()
    for nom, valeur in decls:
        if contient_fragment(valeur, (), fonctions):
            noms.add(nom)
    return noms


def corps_de_fonctions(arbre):
    """[(nom, noeuds rendus)] : pour chaque fonction nommée (function f, méthode f() {}, const f = () => …), les
    expressions de ses « return » (ou le corps d'une flèche sans accolades)."""
    res = []

    def retours(corps):
        out = []
        for i, n in enumerate(corps):
            if est_nom(n, 'return'):
                fin = i + 1
                while fin < len(corps) and not est_ponct(corps[fin], ';'):
                    fin += 1
                out.append(corps[i + 1:fin])
            elif isinstance(n, Groupe) and n.ouvrant == '{':
                out.extend(retours(n.enfants))
        return out

    def parcourir(seq):
        for i, n in enumerate(seq):
            if isinstance(n, Groupe):
                parcourir(n.enfants)
            elif n.genre == 'gabarit':
                for sous, _, _ in n.exprs:
                    parcourir(sous)
            nom = corps = None
            if est_nom(n, 'function') and i + 3 < len(seq) and est_nom_libre(seq[i + 1]) \
                    and est_groupe(seq[i + 2], '(') and est_groupe(seq[i + 3], '{'):
                nom, corps = seq[i + 1].valeur, retours(seq[i + 3].enfants)
            elif est_nom_libre(n) and i + 2 < len(seq) and est_groupe(seq[i + 1], '(') \
                    and est_groupe(seq[i + 2], '{') and not (i >= 1 and (est_ponct(seq[i - 1], '.', '?.')
                                                                         or est_nom(seq[i - 1], 'function'))):
                nom, corps = n.valeur, retours(seq[i + 2].enfants)
            elif est_nom_libre(n) and i + 3 < len(seq) and est_ponct(seq[i + 1], '=', ':') \
                    and (est_groupe(seq[i + 2], '(') or est_nom_libre(seq[i + 2])) and est_ponct(seq[i + 3], '=>'):
                if i + 4 < len(seq) and est_groupe(seq[i + 4], '{'):
                    nom, corps = n.valeur, retours(seq[i + 4].enfants)
                else:
                    fin = i + 4
                    while fin < len(seq) and not est_ponct(seq[fin], ';', ','):
                        fin += 1
                    nom, corps = n.valeur, [seq[i + 4:fin]]
            if nom:
                res.append((nom, corps))
    parcourir(arbre)
    return res


def fonctions_fragments(arbres):
    """Noms des fonctions (de tous les fichiers donnés) qui rendent un fragment HTML, jusqu'à stabilité."""
    corps = [c for arbre in arbres for c in corps_de_fonctions(arbre)]
    noms = set()
    change = True
    while change:
        change = False
        for nom, retours in corps:
            if nom not in noms and any(contient_fragment(r, (), noms) for r in retours):
                noms.add(nom)
                change = True
    return noms


class Infos:
    __slots__ = ('ctx', 'corps')

    def __init__(self, ctx, corps):
        self.ctx = ctx
        self.corps = corps


class AnalyseFichier:
    """Analyse un fichier JS : unités de texte à extraire, cas à relire, et source réécrite (marqueurs de clés)."""

    def __init__(self, outil, rel, source, section):
        self.outil = outil
        self.classement = outil.classement
        self.rel = rel
        self.src = source
        self.section = section
        self.ligne = Lignes(source)
        self.unites = []
        self.relectures = []
        self.exclus = 0
        self.arbre = construire_arbre(source)
        self.pluriels = fonctions_pluriel(self.arbre)
        decls = declarations(self.arbre)
        self.calcules = mots_calcules(decls, outil.valeurs)
        self.fonctions_fragments = outil.fonctions_fragments() | fonctions_fragments([self.arbre])
        self.fragments = variables_fragments(decls, self.fonctions_fragments)

    # -- résultats ------------------------------------------------------------------------------------
    def relire(self, position, texte, raison):
        self.relectures.append((position, self.ligne(position), court(texte), raison))

    def enregistrer(self, position, valeur, appel, variables, texte, ctx, original=None, formes_vars=None):
        """Retient l'unité et rend le texte de l'appel I18n (la clé est un marqueur remplacé plus tard).
        original : texte affiché d'avant ({forme: texte}, expressions écrites ⟦…⟧) ; formes_vars : nom → ⟦…⟧."""
        marqueur = '\x00CLE%d\x00' % len(self.outil.toutes_unites)
        unite = Unite(fichier=self.rel, position=position, ligne=self.ligne(position), section=self.section,
                      composant=nom_composant(ctx.cadres, self.rel, self.section), element=resume(valeur),
                      valeur=valeur, appel=appel, texte=court(texte), marqueur=marqueur, original=original,
                      vars=formes_vars or {})
        self.unites.append(unite)
        self.outil.toutes_unites.append(unite)
        args = ''
        if variables:
            args = ', { ' + ', '.join(nom if expr == nom else '%s: %s' % (nom, expr) for nom, expr in variables) + ' }'
        return "I18n.%s('%s'%s)" % (appel, marqueur, args)

    # -- parcours -------------------------------------------------------------------------------------
    def rendre(self):
        return self.rendre_suite(self.arbre, Ctx(), 0, len(self.src))

    def preparer(self, seq, ctx):
        """Contexte de chaque nœud de la suite, et corps de fonctions (index du groupe { } → Cadre)."""
        L = len(seq)
        corps = {}
        zones = []
        for i, n in enumerate(seq):
            if est_nom(n, 'function'):
                j = i + 1
                if j < L and est_ponct(seq[j], '*'):
                    j += 1
                nom = None
                if j < L and est_nom_libre(seq[j]):
                    nom = seq[j].valeur
                    j += 1
                if j + 1 < L and est_groupe(seq[j], '(') and est_groupe(seq[j + 1], '{'):
                    b = j + 1
                    debut = i - 1 if i >= 1 and est_nom(seq[i - 1], 'async') else i
                    nom = nom or self.nom_affecte(seq, debut)
                    iife = (b + 1 < L and est_groupe(seq[b + 1], '(')) or (debut == 0 and b == L - 1 and ctx.suivi_appel)
                    corps[b] = Cadre(nom, not (iife or self.rappel_chargement(seq, debut, ctx)))
            elif est_ponct(n, '=>') and i >= 1:
                p = i - 1
                debut = p - 1 if p >= 1 and est_nom(seq[p - 1], 'async') else p
                nom = self.nom_affecte(seq, debut)
                charge = self.rappel_chargement(seq, debut, ctx)
                if i + 1 < L and est_groupe(seq[i + 1], '{'):
                    iife = debut == 0 and i + 2 == L and ctx.suivi_appel
                    corps[i + 1] = Cadre(nom, not (iife or charge))
                else:
                    fin = i + 1
                    while fin < L and not est_ponct(seq[fin], ',', ';'):
                        fin += 1
                    iife = debut == 0 and fin == L and ctx.suivi_appel
                    zones.append((i + 1, fin, Cadre(nom, not (iife or charge))))
            elif est_nom_libre(n) and i + 2 < L and est_groupe(seq[i + 1], '(') and est_groupe(seq[i + 2], '{') \
                    and not (i >= 1 and (est_nom(seq[i - 1], 'function') or est_ponct(seq[i - 1], '.', '?.'))):
                corps[i + 2] = Cadre(n.valeur, True)            # méthode : nom(…) { … }
        contextes = []
        rang = 0
        cle = None
        variable = None
        direct = ctx.appel_en_cours is not None
        for i, n in enumerate(seq):
            if i >= 2 and est_ponct(seq[i - 1], '=') and est_nom_libre(seq[i - 2]) \
                    and not (i >= 3 and est_ponct(seq[i - 3], '.', '?.')):
                variable = seq[i - 2].valeur
            if ctx.groupe == '{' and (i == 0 or est_ponct(seq[i - 1], ',')) and i + 1 < L \
                    and est_ponct(seq[i + 1], ':') and isinstance(n, Jeton) and n.genre in ('nom', 'chaine', 'nombre'):
                cle = decoder(n.valeur) if n.genre == 'chaine' else n.valeur
            cadres = ctx.cadres + tuple(z[2] for z in zones if z[0] <= i < z[1])
            appels = ctx.appels + ((ctx.appel_en_cours, rang),) if direct else ctx.appels
            cle_directe = cle if ctx.groupe == '{' else None
            contextes.append(ctx.avec(cadres=cadres, appels=appels, cle=cle_directe or ctx.cle,
                                      cle_directe=cle_directe, appel_en_cours=None, direct=direct,
                                      variable=variable or ctx.variable))
            if est_ponct(n, ','):
                rang += 1
                cle = None
            if est_ponct(n, ',', ';'):
                variable = None
        return Infos(contextes, corps)

    @staticmethod
    def nom_affecte(seq, debut):
        k = debut - 1
        if k >= 1 and est_ponct(seq[k], '=') and est_nom_libre(seq[k - 1]):
            return seq[k - 1].valeur
        if k >= 1 and est_ponct(seq[k], ':') and (est_nom_libre(seq[k - 1]) or
                                                  (isinstance(seq[k - 1], Jeton) and seq[k - 1].genre == 'chaine')):
            return decoder(seq[k - 1].valeur)
        return None

    @staticmethod
    def rappel_chargement(seq, debut, ctx):
        """Fonction passée à document.addEventListener('DOMContentLoaded', …) : exécutée une fois au démarrage."""
        appel = ctx.appel_en_cours or ''
        if not appel.endswith('addEventListener') or debut == 0 or not seq:
            return False
        premier = seq[0]
        if not (isinstance(premier, Jeton) and premier.genre == 'chaine'):
            return False
        evenement = decoder(premier.valeur)
        return evenement == 'DOMContentLoaded' or (evenement == 'load' and appel.startswith('window'))

    def rendre_suite(self, seq, ctx, pos_debut, pos_fin):
        infos = self.preparer(seq, ctx)
        actions, raisons = self.analyser_segments(seq, infos)
        out = []
        pos = pos_debut
        i = 0
        while i < len(seq):
            noeud = seq[i]
            out.append(self.src[pos:noeud.debut])
            if i in actions:
                fin, texte = actions[i]
                out.append(texte)
                pos = seq[fin - 1].fin
                i = fin
                continue
            out.append(self.rendre_noeud(seq, i, infos, raisons))
            pos = noeud.fin
            i += 1
        out.append(self.src[pos:pos_fin])
        return ''.join(out)

    def rendre_plage(self, seq, i0, i1, ctx):
        """Source réécrite des nœuds seq[i0:i1] (dans le contexte donné)."""
        if i0 >= i1:
            return ''
        return self.rendre_suite(seq[i0:i1], ctx, seq[i0].debut, seq[i1 - 1].fin)

    def rendre_expr(self, noeuds, ctx):
        if not noeuds:
            return ''
        return self.rendre_suite(noeuds, ctx.avec(groupe=None, appel_en_cours=None), noeuds[0].debut,
                                 noeuds[-1].fin).strip()

    def rendre_noeud(self, seq, i, infos, raisons):
        noeud = seq[i]
        ci = infos.ctx[i]
        if isinstance(noeud, Groupe):
            cadres = ci.cadres + ((infos.corps[i],) if i in infos.corps else ())
            appel = None
            suivi = False
            if noeud.ouvrant == '(':
                definition = (i + 1) in infos.corps or (i >= 1 and est_nom(seq[i - 1], 'function')) \
                    or (i >= 2 and est_nom(seq[i - 2], 'function'))
                if not definition:
                    appel = nom_appele(seq, i)
                suivi = i + 1 < len(seq) and est_groupe(seq[i + 1], '(')
            enfant = ci.avec(cadres=cadres, appel_en_cours=appel, groupe=noeud.ouvrant, suivi_appel=suivi)
            return self.src[noeud.debut] + self.rendre_suite(noeud.enfants, enfant, noeud.debut + 1, noeud.fin - 1) \
                + self.src[noeud.fin - 1]
        if noeud.genre == 'gabarit':
            etiquette = etiquette_gabarit(seq, i)
            if etiquette in ETIQUETTES_HTML:
                return self.rendre_gabarit(noeud, ci, 'html', seul=False)
            if not (i in raisons and raisons[i] is None):
                raison = raisons.get(i) or ('gabarit étiqueté %s' % etiquette if etiquette
                                            else 'texte calculé ou utilisé dans une expression')
                if self.signaler_gabarit(noeud, ci, raison):
                    return self.src[noeud.debut:noeud.fin]
            return self.gabarit_tel_quel(noeud, ci)
        if noeud.genre == 'chaine' and not (i in raisons and raisons[i] is None):
            self.signaler_chaine(noeud, ci, raisons.get(i) or 'texte calculé ou utilisé dans une expression')
        return self.src[noeud.debut:noeud.fin]

    def gabarit_tel_quel(self, noeud, ctx):
        out = ['`']
        for k, (d, f) in enumerate(noeud.morceaux):
            out.append(self.src[d:f])
            if k < len(noeud.exprs):
                sous, ed, ef = noeud.exprs[k]
                out.append('${' + self.rendre_suite(sous, ctx.avec(appel_en_cours=None, groupe=None), ed, ef) + '}')
        out.append('`')
        return ''.join(out)

    def texte_visible(self, texte, ctx):
        """Texte décodé d'un littéral (avec {} pour les ${…}) visible ? (HTML découpé entre balises)."""
        if self.classement.exception_contexte(self.rel, ctx) or self.classement.exception_texte(self.rel, texte):
            return False
        if RE_BALISE.search(texte):
            return any(self.classement.visible_html(nettoyer(m)) for m in RE_BALISE.split(texte)[::4])
        return self.classement.visible_js(nettoyer(texte), texte, ctx)

    def signaler_chaine(self, noeud, ctx, raison):
        texte = decoder(noeud.valeur)
        if self.texte_visible(texte, ctx):
            self.relire(noeud.debut, texte, raison)
            return True
        return False

    def signaler_gabarit(self, noeud, ctx, raison):
        texte = '{}'.join(decoder(self.src[d:f]) for d, f in noeud.morceaux)
        if self.texte_visible(texte, ctx):
            self.relire(noeud.debut, texte.replace('{}', '${…}'), raison)
            return True
        return False

    def contient_visible(self, noeuds, ctx):
        for n in noeuds:
            if isinstance(n, Groupe):
                if self.contient_visible(n.enfants, ctx):
                    return True
            elif n.genre == 'chaine':
                if self.texte_visible(decoder(n.valeur), ctx):
                    return True
            elif n.genre == 'gabarit':
                if self.texte_visible('{}'.join(decoder(self.src[d:f]) for d, f in n.morceaux), ctx):
                    return True
                if any(self.contient_visible(sous, ctx) for sous, _, _ in n.exprs):
                    return True
        return False

    # -- segments et concaténations ---------------------------------------------------------------------
    def analyser_segments(self, seq, infos):
        actions, raisons = {}, {}
        debut = 0
        for k in range(len(seq) + 1):
            if k == len(seq) or est_delimiteur(seq[k]):
                if k > debut:
                    self.analyser_segment(seq, debut, k, infos, actions, raisons)
                debut = k + 1
        return actions, raisons

    @staticmethod
    def operandes(seq, a, b):
        ops, debut, moins = [], a, False
        for k in range(a, b):
            n = seq[k]
            if est_ponct(n, '+', '-') and k > debut and fin_d_operande(seq[k - 1]):
                moins = moins or n.valeur == '-'
                ops.append((debut, k))
                debut = k + 1
        ops.append((debut, b))
        return ops, moins

    def genre_operande(self, seq, i0, i1):
        if i1 - i0 == 1:
            n = seq[i0]
            if isinstance(n, Jeton) and n.genre == 'chaine':
                return 'lit'
            if isinstance(n, Jeton) and n.genre == 'gabarit':
                return 'gab'
            if est_groupe(n, '('):
                genre = self.genre_expr(n.enfants, 'chaine')
                return 'expr' if genre == 'var' else genre
        if i1 - i0 == 2 and est_nom(seq[i0]) and seq[i0].valeur in self.pluriels and est_groupe(seq[i0 + 1], '('):
            if self.arguments_pluriel(seq[i0].valeur, seq[i0 + 1]) is not None:
                return 'pluriel_appel'
        return 'expr'

    def arguments_pluriel(self, nom, groupe):
        args = couper_virgules(groupe.enfants)
        forme = self.pluriels[nom]
        if not args[0] or not 2 <= len(args) <= 3:
            return None
        mots = args[1:]
        if not all(len(m) == 1 and isinstance(m[0], Jeton) and m[0].genre == 'chaine' for m in mots):
            return None
        if (forme == 'F4' and len(mots) < 2) or (forme in ('F2', 'F3') and len(mots) != 1):
            return None
        return forme, args[0], [m[0] for m in mots]

    @staticmethod
    def ternaire(noeuds):
        q = next((k for k, x in enumerate(noeuds) if est_ponct(x, '?')), None)
        if q is None:
            return None
        c = next((k for k in range(q + 1, len(noeuds)) if est_ponct(noeuds[k], ':')), None)
        if c is None:
            return None
        return noeuds[:q], noeuds[q + 1:c], noeuds[c + 1:]

    @staticmethod
    def condition_pluriel(cond):
        """(noeuds du compte, sens) : sens 'autre' si la condition vraie demande le pluriel, 'un' à l'inverse,
        'incertain' pour « == 1 » (zéro au pluriel, alors que le français CLDR le met au singulier)."""
        def vaut(n, v):
            return isinstance(n, Jeton) and n.genre == 'nombre' and n.valeur == v
        if len(cond) < 3:
            return None
        if est_ponct(cond[-2], '>') and vaut(cond[-1], '1'):
            compte = cond[:-2]
            if len(compte) == 4 and est_nom(compte[0], 'Math') and est_ponct(compte[1], '.') \
                    and est_nom(compte[2], 'abs') and est_groupe(compte[3], '('):
                compte = compte[3].enfants
            return compte, 'autre'
        if est_ponct(cond[-2], '>=') and vaut(cond[-1], '2'):
            return cond[:-2], 'autre'
        if vaut(cond[0], '1') and est_ponct(cond[1], '<'):
            return cond[2:], 'autre'
        if est_ponct(cond[-2], '<=') and vaut(cond[-1], '1'):
            return cond[:-2], 'un'
        if est_ponct(cond[-2], '<') and vaut(cond[-1], '2'):
            return cond[:-2], 'un'
        if est_ponct(cond[-2], '===', '==', '!==', '!=') and vaut(cond[-1], '1'):
            return cond[:-2], 'incertain'
        return None

    def genre_expr(self, noeuds, mode):
        """'choix' (pluriel sûr), 'choix_incertain', 'fragment' (HTML, mode html), 'choix_texte' (texte choisi par
        le code) ou 'var'."""
        t = self.ternaire(noeuds)
        if t:
            cond, oui, non = t
            if len(oui) == 1 and len(non) == 1 and all(isinstance(x[0], Jeton) and x[0].genre == 'chaine'
                                                       for x in (oui, non)):
                trouve = self.condition_pluriel(cond)
                if trouve and trouve[0] and not any(est_ponct(x, '&&', '||', '??', '?') for x in trouve[0]):
                    return 'choix_incertain' if trouve[1] == 'incertain' else 'choix'
        if mode == 'html' and contient_fragment(noeuds, self.fragments, self.fonctions_fragments, tableaux=True):
            return 'fragment'
        if t and (self.texte_visible_dans(t[1]) or self.texte_visible_dans(t[2])):
            return 'choix_texte'
        k = next((k for k, x in enumerate(noeuds) if est_ponct(x, '&&')), None)
        if k is not None and self.texte_visible_dans(noeuds[k + 1:]):
            return 'choix_texte'
        return 'var'

    @classmethod
    def fragment_optionnel(cls, noeuds):
        """Variable de phrase « cond ? ' (' + x + ')' : '' » (parenthèses comprises) : une branche vide, l'autre avec
        un littéral de ponctuation. Devenue {v1}, elle cacherait au traducteur un morceau de la phrase (T237)."""
        while len(noeuds) == 1 and est_groupe(noeuds[0], '('):
            noeuds = noeuds[0].enfants
        t = cls.ternaire(noeuds)
        if not t:
            return False

        def vide(branche):
            return len(branche) == 1 and isinstance(branche[0], Jeton) and branche[0].genre in ('chaine', 'gabarit') \
                and decoder(branche[0].valeur if branche[0].genre == 'chaine' else branche[0].valeur[1:-1]) == ''

        def ponctuation(branche):
            for n in branche:
                if isinstance(n, Jeton) and n.genre in ('chaine', 'gabarit'):
                    brut = n.valeur if n.genre == 'chaine' else re.sub(r'\$\{[^}]*\}', '', n.valeur[1:-1])
                    if decoder(brut).strip():
                        return True
            return False

        _, oui, non = t
        return (vide(non) and ponctuation(oui)) or (vide(oui) and ponctuation(non))

    @staticmethod
    def texte_visible_dans(noeuds):
        """Une branche contient-elle un littéral qui ressemble à du texte (au premier niveau) ?"""
        for n in noeuds:
            if isinstance(n, Jeton) and n.genre in ('chaine', 'gabarit'):
                brut = n.valeur if n.genre == 'chaine' else n.valeur[1:-1]
                t = nettoyer(decoder(re.sub(r'\$\{[^}]*\}', '{}', brut)))
                if RE_LETTRE.search(t.replace('{}', '')) and (RE_ACCENT.search(t) or ' ' in t
                                                             or re.match(r'^[A-ZÀ-Ý][a-zà-ÿ]+', t)):
                    return True
        return False

    def analyser_segment(self, seq, a, b, infos, actions, raisons):
        ci = infos.ctx[a]
        precedent = seq[a - 1] if a > 0 else None
        suivant = seq[b] if b < len(seq) else None
        # clé d'objet ('Texte': …) : jamais affichée telle quelle
        if b - a == 1 and isinstance(seq[a], Jeton) and seq[a].genre == 'chaine' and est_ponct(suivant, ':') \
                and ci.groupe == '{' and (precedent is None or est_ponct(precedent, ',')):
            raisons[a] = None
            return
        ops, moins = self.operandes(seq, a, b)
        genres = [self.genre_operande(seq, i0, i1) for i0, i1 in ops]
        if not any(g in ('lit', 'gab', 'pluriel_appel', 'choix', 'choix_incertain') for g in genres):
            return
        litteraux = [i0 for (i0, i1), g in zip(ops, genres) if g in ('lit', 'gab')]

        def taire(raison=None):
            for i in litteraux:
                raisons[i] = raison

        # premier argument de I18n.t / I18n.html : la clé
        if ci.direct and ci.appels and ci.appels[-1][0] in ('I18n.t', 'I18n.html') and ci.appels[-1][1] == 0:
            taire()
            return
        if self.classement.exception_contexte(self.rel, ci):
            self.exclus += len(litteraux)
            taire()
            return
        if (isinstance(precedent, Jeton) and precedent.valeur in COMPARAISONS) or \
                (isinstance(suivant, Jeton) and suivant.valeur in COMPARAISONS):
            taire('texte comparé dans le code (valeur, pas affichage)')
            return
        if ci.direct and ci.appels:
            nom, rang = ci.appels[-1]
            dernier = (nom or '').rsplit('.', 1)[-1]
            if dernier in APPELS_VALEUR and (APPELS_VALEUR[dernier] is None or rang in APPELS_VALEUR[dernier]):
                taire('texte passé à %s() (recherche, comparaison ou clé)' % dernier)
                return
            rangs = APPELS_TECHNIQUES.get(dernier, ())
            if dernier in APPELS_TECHNIQUES and (rangs is None or rang in rangs):
                taire()
                return
        if ci.direct and ci.appels and ci.appels[-1][0] == 'UI.brut':
            for i in litteraux:
                brut = decoder(seq[i].valeur) if seq[i].genre == 'chaine' else ''
                raisons[i] = None if RE_ATTRIBUTS_SEULS.match(brut) else 'HTML brut (UI.brut) à relire'
            return
        if est_ponct(precedent, '=', '+=') and a >= 2 and est_nom(seq[a - 2], 'className'):
            taire()
            return
        verbatim = (b, self.src[seq[a].debut:seq[b - 1].fin])
        if moins:
            if self.contient_visible(seq[a:b], ci):
                self.relire(seq[a].debut, self.texte_plage(seq, a, b), "concaténation mêlée d'une soustraction")
                actions[a] = verbatim
            return
        if len(ops) == 1 and genres[0] == 'gab':
            actions[a] = (b, self.rendre_gabarit(seq[a], ci, 'brut', seul=True))
            return
        self.concatenation(seq, ops, genres, ci, actions, raisons)

    def texte_plage(self, seq, a, b):
        morceaux = []
        for n in seq[a:b]:
            if isinstance(n, Jeton) and n.genre == 'chaine':
                morceaux.append(decoder(n.valeur))
            elif isinstance(n, Jeton) and n.genre == 'gabarit':
                morceaux.append('${…}'.join(decoder(self.src[d:f]) for d, f in n.morceaux))
            elif est_ponct(n, '+'):
                continue
            elif not morceaux or morceaux[-1] != '${…}':
                morceaux.append('${…}')
        return ''.join(morceaux)

    def morceaux_concatenation(self, seq, ops, genres):
        """Morceaux d'une concaténation, ou (None, raison) si un opérande rend la phrase incertaine."""
        morceaux = []
        # opérandes non textuels en tête : additionnés avant la première chaîne → une seule variable
        tete = 0
        while tete < len(genres) and genres[tete] == 'expr':
            tete += 1
        for k, ((i0, i1), genre) in enumerate(zip(ops, genres)):
            if k < tete:
                if k == 0:
                    fin = ops[tete - 1][1]
                    morceaux.append(Morceau('var', noeuds=seq[i0:fin], op=(0, tete)))
                continue
            n = seq[i0]
            op = (k, k + 1)
            if genre == 'lit':
                morceaux.append(Morceau('txt', brut=n.valeur, guillemet=self.src[n.debut], op=op))
            elif genre == 'gab':
                texte = '{}'.join(decoder(self.src[d:f]) for d, f in n.morceaux)
                if RE_BALISE.search(texte):
                    return None, 'HTML dans une concaténation'
                for j, (d, f) in enumerate(n.morceaux):
                    morceaux.append(Morceau('txt', brut=self.src[d:f], guillemet='`', op=op))
                    if j < len(n.exprs):
                        m = self.morceau_expr(n.exprs[j][0], 'chaine')
                        if m is None:
                            return None, 'pluriel incertain (« == 1 » : zéro serait au pluriel)'
                        if m.genre == 'bar':
                            return None, 'gabarit avec un choix de texte dans une concaténation'
                        m.op = op
                        morceaux.append(m)
            elif genre == 'pluriel_appel':
                forme, compte, mots = self.arguments_pluriel(n.valeur, seq[i0 + 1])
                var = Morceau('var', noeuds=compte, force_n=True, op=op)
                morceaux.append(var)
                morceaux.append(Morceau('txt', brut=' ', guillemet="'", op=op))
                b = mots[0]
                qb = self.src[b.debut]
                if forme in ('F1', 'F4'):
                    autre = (mots[1].valeur, self.src[mots[1].debut]) if len(mots) == 2 else (b.valeur + 's', qb)
                    morceaux.append(Morceau('choix', un=(b.valeur, qb), autre=autre, compte=var, op=op))
                else:
                    morceaux.append(Morceau('txt', brut=b.valeur, guillemet=qb, op=op))
                    morceaux.append(Morceau('choix', un=('', "'"), autre=('s', "'"), compte=var, op=op))
            elif genre == 'choix':
                m = self.morceau_expr(n.enfants, 'chaine')
                m.op = op
                morceaux.append(m)
            elif genre == 'choix_incertain':
                return None, 'pluriel incertain (« == 1 » : zéro serait au pluriel)'
            elif genre == 'choix_texte':
                morceaux.append(Morceau('bar', op=op))
            else:
                morceaux.append(Morceau('var', noeuds=seq[i0:i1], op=op))
        return morceaux, None

    def morceau_expr(self, noeuds, mode):
        """Morceau pour l'expression d'un ${…} ou d'une parenthèse : var, choix, bar ; None si pluriel incertain."""
        genre = self.genre_expr(noeuds, mode)
        if genre == 'choix_incertain':
            return None
        if genre == 'choix':
            cond, oui, non = self.ternaire(noeuds)
            compte, sens = self.condition_pluriel(cond)
            var = Morceau('var', noeuds=compte, force_n=True)
            branche_oui = (oui[0].valeur, self.src[oui[0].debut])
            branche_non = (non[0].valeur, self.src[non[0].debut])
            un, autre = (branche_non, branche_oui) if sens == 'autre' else (branche_oui, branche_non)
            return Morceau('choix', un=un, autre=autre, compte=var)
        if genre in ('fragment', 'choix_texte'):
            return Morceau('bar', noeuds=noeuds)
        return Morceau('var', noeuds=list(noeuds))

    def litteral(self, m):
        if m.guillemet == '`':
            return "'" + vers_simple(m.brut, '`') + "'"
        return m.guillemet + m.brut + m.guillemet

    def concatenation(self, seq, ops, genres, ci, actions, raisons):
        a, b = ops[0][0], ops[-1][1]
        verbatim = (b, self.src[seq[a].debut:seq[b - 1].fin])

        def signaler(raison):
            if self.contient_visible(seq[a:b], ci):
                self.relire(seq[a].debut, self.texte_plage(seq, a, b), raison)
                actions[a] = verbatim

        # marqueur relu par le code (D156) au milieu d'une phrase : à découper à la main
        regles = [(k, self.classement.exception_texte(self.rel, decoder(seq[ops[k][0]].valeur)))
                  for k, g in enumerate(genres) if g == 'lit']
        regles = [(k, r) for k, r in regles if r]
        if regles:
            self.exclus += len(regles)
            exclus = {k for k, _ in regles}
            if any(self.contient_visible(seq[ops[k][0]:ops[k][1]], ci) for k in range(len(ops)) if k not in exclus):
                self.relire(seq[a].debut, self.texte_plage(seq, a, b),
                            'phrase mêlée à une exception (%s) : à découper à la main' % regles[0][1]['classe'])
                actions[a] = verbatim
            else:
                for k in exclus:
                    raisons[ops[k][0]] = None
            return
        morceaux, probleme = self.morceaux_concatenation(seq, ops, genres)
        if morceaux is None:
            signaler(probleme)
            return
        resultat = self.decouper_phrase(morceaux)
        if isinstance(resultat, str):
            signaler(resultat)
            return
        decisions = []
        for genre, contenu in resultat:
            if genre == 'garde':
                decisions.append(('garde', contenu, None))
                continue
            g, m, d = contenu
            plages = sorted({x.op for x in g + m + d})
            litt = [decoder(seq[ops[k][0]].valeur) for k0, k1 in plages for k in range(k0, k1) if genres[k] == 'lit']
            decisions.append(('phrase', contenu, self.juger(g, m, d, ci, 'js', None, litt)))
        relire = next((d[1] for _, _, d in decisions if isinstance(d, tuple)), None)
        if relire:
            signaler(relire)
            return
        if not any(d == 'extraire' for _, _, d in decisions):
            return
        sorties = []
        for genre, contenu, decision in decisions:
            if genre == 'garde':
                k0, k1 = contenu.op
                sorties.append(self.rendre_plage(seq, ops[k0][0], ops[k1 - 1][1], ci))
                continue
            g, m, d = contenu
            if decision != 'extraire':
                k0 = min(x.op[0] for x in g + m + d)
                k1 = max(x.op[1] for x in g + m + d)
                sorties.append(self.rendre_plage(seq, ops[k0][0], ops[k1 - 1][1], ci))
                continue
            sorties.extend(self.litteral(x) for x in g)
            sorties.append(self.appel(m, ci, False, seq[ops[m[0].op[0]][0]].debut))
            sorties.extend(self.litteral(x) for x in d)
        actions[a] = (b, ' + '.join(sorties))

    # -- découpage d'une phrase (bords et barrières) -----------------------------------------------------
    @staticmethod
    def brut_de(m, texte_html):
        if texte_html is None:
            return m.brut
        brut = texte_html[m.a:m.b]
        return RE_SAUT_DE_MISE_EN_PAGE.sub(' ', brut) if m.espaces else brut

    def texte_morceaux(self, ms, texte_html=None, variables=True):
        """Texte affiché (décodé) des morceaux ; {} à la place des variables ; forme « autre » des pluriels."""
        out = []
        for m in ms:
            if m.genre == 'txt':
                t = decoder(self.brut_de(m, texte_html))
                out.append(t if texte_html is None else html.unescape(t))
            elif m.genre == 'var' and variables:
                out.append('{}')
            elif m.genre == 'choix':
                out.append(decoder(m.autre[0]))
        return ''.join(out)

    @staticmethod
    def est_barriere(m):
        return m.genre == 'bar' or (m.genre == 'balise' and m.k == 'barriere')

    def decouper_phrase(self, morceaux, texte_html=None):
        """[('phrase', (gauche, milieu, droite)) | ('garde', morceau)] ou une raison (str) de relecture.
        Une barrière (choix de texte, fragment HTML, balise à variable) coupe la phrase si elle tombe entre deux
        phrases (fin de phrase avant elle, ou rien après) ; au milieu d'une phrase : relecture."""
        sorties = []
        courant = []
        ms = list(morceaux)
        for idx, m in enumerate(ms):
            if not self.est_barriere(m):
                courant.append(m)
                continue
            avant = self.texte_morceaux(courant, texte_html).strip()
            suite = []
            for x in ms[idx + 1:]:
                if self.est_barriere(x):
                    break
                suite.append(x)
            apres = self.texte_morceaux(suite, texte_html).strip()
            if RE_LETTRE.search(avant.replace('{}', '')) and RE_LETTRE.search(apres.replace('{}', '')) \
                    and avant[-1] not in PONCTUATION_FIN:
                return ("choix de texte ou fragment HTML au milieu d'une phrase" if m.genre == 'bar'
                        else "balisage avec variable au milieu d'une phrase")
            if courant:
                sorties.append(courant)
            sorties.append(m)
            courant = []
        if courant:
            sorties.append(courant)
        return [('garde', s) if isinstance(s, Morceau) else ('phrase', self.rogner(s, texte_html)) for s in sorties]

    def rogner(self, ms, texte_html=None):
        """(gauche, milieu, droite) : espaces de bord et, en HTML, balises qui enveloppent la phrase ou qui n'ont
        pas de texte (astérisque, <br>) laissés hors de la clé."""
        gauche, droite = [], []
        ms = list(ms)
        while ms:
            if self.rogner_bord(ms, gauche, droite, True, texte_html):
                continue
            if ms and self.rogner_bord(ms, gauche, droite, False, texte_html):
                continue
            break
        return gauche, ms, droite

    def rogner_bord(self, ms, gauche, droite, a_gauche, texte_html):
        i = 0 if a_gauche else len(ms) - 1
        x = ms[i]

        def ranger(m):
            if a_gauche:
                gauche.append(m)
            else:
                droite.insert(0, m)

        if x.genre == 'txt':
            s = x.brut if texte_html is None else texte_html[x.a:x.b]      # positions : texte d'origine
            reste = s.lstrip(' \t\n\r') if a_gauche else s.rstrip(' \t\n\r')
            n = len(s) - len(reste)
            if n == 0 or (not a_gauche and reste.endswith('\\')):
                return False
            if not reste:
                ranger(ms.pop(i))
                return True
            if texte_html is None:
                bord = Morceau('txt', brut=s[:n] if a_gauche else s[len(s) - n:], guillemet=x.guillemet, op=x.op)
                interieur = Morceau('txt', brut=reste, guillemet=x.guillemet, op=x.op)
            elif a_gauche:
                bord = Morceau('txt', a=x.a, b=x.a + n, guillemet='`', espaces=x.espaces)
                interieur = Morceau('txt', a=x.a + n, b=x.b, guillemet='`', espaces=x.espaces)
            else:
                bord = Morceau('txt', a=x.b - n, b=x.b, guillemet='`', espaces=x.espaces)
                interieur = Morceau('txt', a=x.a, b=x.b - n, guillemet='`', espaces=x.espaces)
            ranger(bord)
            ms[i] = interieur
            return True
        if texte_html is None:
            return False
        action = self.bord(ms, i, texte_html)
        if action is None:
            return False
        if action == 'seul':
            ranger(ms.pop(i))
        elif action == 'enveloppe':
            gauche.append(ms.pop(0))
            droite.insert(0, ms.pop())
        else:
            j = next(k for k, y in enumerate(ms) if y is x.partenaire)
            if a_gauche:
                gauche.extend(ms[:j + 1])
                del ms[:j + 1]
            else:
                droite[:0] = ms[j:]
                del ms[j:]
        return True

    @staticmethod
    def bord(ms, i, texte_html):
        x = ms[i]
        if x.genre == 'bar':
            return 'seul'
        if x.genre != 'balise':
            return None
        if x.nom in BALISES_VIDES or x.k == 'barriere':
            return 'seul'
        j = next((k for k, y in enumerate(ms) if y is x.partenaire), None)
        if j is None:
            return 'seul'
        if {i, j} == {0, len(ms) - 1}:
            return 'enveloppe'
        if (i == 0 and j > i) or (i == len(ms) - 1 and j < i):
            a, b = sorted((i, j))
            if not any((y.genre == 'txt' and RE_LETTRE.search(texte_html[y.a:y.b])) or y.genre in ('var', 'choix')
                       for y in ms[a + 1:b]):
                return 'element'
        return None

    # -- jugement et appel ---------------------------------------------------------------------------
    def juger(self, gauche, milieu, droite, ci, visibilite, texte_html=None, litteraux=()):
        """'extraire', 'garder' (pas de texte visible, exception) ou ('relire', raison)."""
        if not milieu:
            return 'garder'
        texte = self.texte_morceaux(milieu, texte_html)
        net = nettoyer(texte)
        if not RE_LETTRE.search(net.replace('{}', '')):
            return 'garder'
        if self.classement.exception_contexte(self.rel, ci) or self.classement.exception_texte(self.rel, net):
            self.exclus += 1
            return 'garder'
        if visibilite == 'js':
            brut_complet = self.texte_morceaux(gauche + milieu + droite, texte_html)
            visible = self.classement.visible_js(net, brut_complet, ci) or \
                any(self.classement.visible_js(nettoyer(t), t, ci) for t in litteraux)
        else:
            visible = self.classement.visible_html(net)
        if not visible:
            return 'garder'
        if ci.fige:
            return ('relire', 'texte figé au chargement du module (calculé une seule fois)')
        sans_variables = self.texte_morceaux(milieu, texte_html, variables=False)
        if '{' in sans_variables or '}' in sans_variables:
            return ('relire', 'accolade dans le texte (confusion avec une variable {…})')
        if texte_html is None and RE_BALISE.search(sans_variables):
            return ('relire', 'HTML dans une chaîne')
        for m in milieu:
            if m.genre == 'txt' and vers_simple(self.brut_de(m, texte_html), m.guillemet or '`') is None:
                return ('relire', 'continuation de ligne dans le texte')
            if m.genre == 'var' and len(m.noeuds) == 1 and est_nom(m.noeuds[0]) and m.noeuds[0].valeur in self.calcules:
                return ('relire', "mot choisi par le code au milieu d'une phrase (« %s » : accord, texte calculé)"
                        % m.noeuds[0].valeur)
            if m.genre == 'var' and self.fragment_optionnel(m.noeuds):
                return ('relire', "fragment optionnel au milieu d'une phrase (x ? ' (' + y + ')' : '' : une clé "
                                  "par forme de la phrase)")
        if texte_html is not None:
            pile = []
            for m in milieu:
                if m.genre == 'balise' and m.nom not in BALISES_VIDES:
                    if not m.fermante:
                        pile.append(m.nom)
                    elif pile and pile[-1] == m.nom:
                        pile.pop()
                    else:
                        return ('relire', 'HTML compliqué (balises non appariées dans la phrase)')
            if pile:
                return ('relire', 'HTML compliqué (balises non appariées dans la phrase)')
        if self.compte_pluriel(milieu, texte_html) == 'incertain':
            return ('relire', 'pluriel incertain (plusieurs nombres différents)')
        return 'extraire'

    def compte_pluriel(self, milieu, texte_html=None):
        """('choix', var) pour un pluriel du code, ('s', var) pour « (s) » après un nombre sûr, None sinon ;
        'incertain' si deux nombres différents commandent le pluriel."""
        choix = [m for m in milieu if m.genre == 'choix']
        if choix:
            formes = {normaliser(self.src, m.compte.noeuds) for m in choix}
            return 'incertain' if len(formes) > 1 else ('choix', choix[0].compte)
        dernier = None
        mots = 0
        trouves = []
        for m in milieu:
            if m.genre == 'var':
                dernier = m
                mots = 0
                continue
            if m.genre != 'txt':
                continue
            for mot in self.texte_morceaux([m], texte_html).split():
                if re.search(r'\w\(s\)', mot):
                    trouves.append(dernier if dernier is not None and mots <= 1 else None)
                if RE_LETTRE.search(mot):
                    mots += 1
        # « (s) » sans nombre sûr juste avant : texte simple (la forme française ne change pas)
        if not trouves or any(t is None for t in trouves) or len({id(t) for t in trouves}) > 1:
            return None
        if not self.expression_de_compte(trouves[0].noeuds):
            return None
        return ('s', trouves[0])

    def expression_de_compte(self, noeuds):
        """Identifiant, membre (x.length) ou formateur d'un tel nombre (UI.nombreFr(x)) : les nœuds du nombre."""
        noms = [n for n in noeuds if not est_ponct(n, '.', '?.')]
        if noms and all(est_nom(n) for n in noms) and len(noeuds) == 2 * len(noms) - 1:
            return noeuds
        if len(noeuds) >= 2 and est_groupe(noeuds[-1], '('):
            appel = nom_appele(noeuds, len(noeuds) - 1) or ''
            if appel.rsplit('.', 1)[-1] in FORMATEURS and len(couper_virgules(noeuds[-1].enfants)) == 1:
                return self.expression_de_compte(noeuds[-1].enfants)
        return None

    def nom_variable(self, noeuds):
        if not noeuds:
            return None
        if len(noeuds) == 1 and est_nom_libre(noeuds[0]):
            return noeuds[0].valeur
        noms = [n for n in noeuds if not est_ponct(n, '.', '?.')]
        if noms and all(est_nom(n) for n in noms) and len(noeuds) == 2 * len(noms) - 1:
            dernier = noms[-1].valeur
            if dernier == 'length' and len(noms) > 1:
                return 'nb' + noms[-2].valeur[:1].upper() + noms[-2].valeur[1:]
            if dernier in NOMS_GENERIQUES and len(noms) > 1 and noms[-2].valeur != 'this':
                return noms[-2].valeur + dernier[:1].upper() + dernier[1:]
            return dernier
        if len(noeuds) >= 2 and est_groupe(noeuds[-1], '('):
            appel = nom_appele(noeuds, len(noeuds) - 1)
            if appel and '…' not in appel and len(noeuds) == 2 * len(appel.split('.')):
                dernier = appel.rsplit('.', 1)[-1]
                args = couper_virgules(noeuds[-1].enfants)
                if dernier in FORMATEURS:
                    return self.nom_variable(args[0]) if len(args) == 1 else None
                return dernier
        return None

    def appel(self, milieu, ci, html_permis, position, texte_html=None):
        """Texte de l'appel I18n.t / I18n.html pour une phrase jugée sûre (enregistre l'unité)."""
        pluriel = self.compte_pluriel(milieu, texte_html)
        noms = {}            # nom → forme normalisée de l'expression
        par_forme = {}
        variables = []       # (nom, expression réécrite)
        orig_un, orig_autre = [], []

        def ajouter(noeuds, voulu=None):
            forme = normaliser(self.src, noeuds)
            if forme in par_forme:
                return par_forme[forme]
            nom = voulu or self.nom_variable(noeuds)
            if nom is not None and (not re.match(r'^[A-Za-z_]\w*$', nom) or nom in MOTS_CLES):
                nom = None
            if nom is None or (nom in noms and noms[nom] != forme):
                base = nom or 'v'
                k = 1 if nom is None else 2
                while base + str(k) in noms:
                    k += 1
                nom = base + str(k)
            noms[nom] = forme
            par_forme[forme] = nom
            variables.append((nom, self.rendre_expr(noeuds, ci)))
            return nom

        if isinstance(pluriel, tuple):
            genre, var = pluriel
            noeuds_n = var.noeuds if genre == 'choix' else (self.expression_de_compte(var.noeuds) or var.noeuds)
            ajouter(noeuds_n, 'n')
        un, autre, affiche = [], [], []
        a_balise = False
        for m in milieu:
            if m.genre == 'txt':
                brut = self.brut_de(m, texte_html)
                v = vers_simple(brut, m.guillemet or '`')
                un.append(v)
                autre.append(v)
                affiche.append(decoder(brut))
                orig_un.append(decoder(brut))
                orig_autre.append(decoder(brut))
                if texte_html is not None and '&' in brut:
                    a_balise = True
            elif m.genre == 'balise':
                v = vers_simple(texte_html[m.a:m.b], '`')
                un.append(v)
                autre.append(v)
                affiche.append(texte_html[m.a:m.b])
                orig_un.append(decoder(texte_html[m.a:m.b]))
                orig_autre.append(decoder(texte_html[m.a:m.b]))
                a_balise = True
            elif m.genre == 'var':
                nom = ajouter(m.noeuds)
                un.append('{' + nom + '}')
                autre.append('{' + nom + '}')
                affiche.append('{' + nom + '}')
                forme = '\u27e6' + normaliser(self.src, m.noeuds) + '\u27e7'
                orig_un.append(forme)
                orig_autre.append(forme)
            elif m.genre == 'choix':
                un.append(vers_simple(m.un[0], m.un[1]))
                autre.append(vers_simple(m.autre[0], m.autre[1]))
                affiche.append('{%s|%s}' % (decoder(m.un[0]), decoder(m.autre[0])))
                orig_un.append(decoder(m.un[0]))
                orig_autre.append(decoder(m.autre[0]))
        valeur = {'one': ''.join(un), 'other': ''.join(autre)} if isinstance(pluriel, tuple) else ''.join(autre)
        fonction = 'html' if html_permis and a_balise else 't'
        if isinstance(valeur, dict):
            original = {'one': ''.join(orig_un), 'other': ''.join(orig_autre)}
        else:
            original = {'': ''.join(orig_autre)}
        formes_vars = {nom: '\u27e6' + forme + '\u27e7' for nom, forme in noms.items()}
        return self.enregistrer(position, valeur, fonction, variables, ''.join(affiche), ci, original, formes_vars)

    # -- gabarits ------------------------------------------------------------------------------------
    def rendre_gabarit(self, noeud, ci, mode, seul):
        """Gabarit UI.html (mode 'html' : I18n.t échappé, I18n.html pour une phrase balisée) ou gabarit seul non
        étiqueté (mode 'brut' : rien n'est échappé, I18n.t seulement)."""
        expr_ctx = ci.avec(appel_en_cours=None, groupe=None)
        morceaux_texte = []
        carte = []
        for k, (d, f) in enumerate(noeud.morceaux):
            brut = self.src[d:f]
            if any('' <= c <= '' for c in brut):
                if self.signaler_gabarit(noeud, ci, "caractère d'usage privé dans le gabarit"):
                    return self.src[noeud.debut:noeud.fin]
                return self.gabarit_tel_quel(noeud, ci)
            morceaux_texte.append(brut)
            carte.extend(range(d, f))
            if k < len(noeud.exprs):
                morceaux_texte.append(chr(SENTINELLE + k))
                carte.append(-1)
        texte = ''.join(morceaux_texte)
        elements = decouper_html(texte)
        if elements is None:
            if self.signaler_gabarit(noeud, ci, 'HTML compliqué (gabarit illisible)'):
                return self.src[noeud.debut:noeud.fin]
            return self.gabarit_tel_quel(noeud, ci)
        html_permis = mode == 'html'
        visibilite = 'html' if mode == 'html' or any(el.genre == 'balise' for el in elements) else 'js'
        # Gabarit UI.html sans <pre> ni <textarea> : un saut de ligne de mise en page dans un texte entre balises
        # s'affiche comme une espace ; la valeur du dictionnaire le garde en une espace (T237).
        espaces = mode == 'html' and not any(el.genre == 'balise' and el.nom.lower() in BALISES_ESPACES_GARDES
                                             for el in elements)
        mode_expr = 'html' if mode == 'html' else 'chaine'

        def tel_quel(a, b):
            out = []
            for p in range(a, b):
                c = texte[p]
                if '' <= c <= '':
                    sous, ed, ef = noeud.exprs[ord(c) - SENTINELLE]
                    out.append('${' + self.src[ed:ef] + '}')
                else:
                    out.append(c)
            return ''.join(out)

        def position(a):
            for p in range(a, len(carte)):
                if carte[p] >= 0:
                    return carte[p]
            return noeud.debut

        remplacements = []          # (a, b, texte)
        couverts = []               # plages couvertes par une phrase extraite ou signalée
        entier = False

        def signaler(a, b, raison):
            if self.suite_visible(texte, a, b, ci):
                self.relire(position(a), tel_quel(a, b), raison)
                remplacements.append((a, b, tel_quel(a, b)))
                couverts.append((a, b))

        # 1. textes : suites de textes et de balises en ligne
        suites, courant = [], []
        for el in elements:
            if el.genre == 'texte' or (el.genre == 'balise' and el.nom in BALISES_EN_LIGNE):
                courant.append(el)
            else:
                if courant:
                    suites.append(courant)
                courant = []
        if courant:
            suites.append(courant)
        for suite in suites:
            a, b = suite[0].a, suite[-1].b
            morceaux, probleme = self.morceaux_html(suite, texte, noeud, mode_expr, espaces)
            if morceaux is None:
                signaler(a, b, probleme)
                continue
            resultat = self.decouper_phrase(morceaux, texte)
            if isinstance(resultat, str):
                signaler(a, b, resultat)
                continue
            phrases = []
            for genre, contenu in resultat:
                if genre == 'phrase' and contenu[1]:
                    g, m, d = contenu
                    phrases.append((m, self.juger(g, m, d, ci, visibilite, texte)))
            relire = next((d[1] for _, d in phrases if isinstance(d, tuple)), None)
            if relire:
                signaler(a, b, relire)
                continue
            for m, decision in phrases:
                if decision != 'extraire':
                    continue
                appel = self.appel(m, ci, html_permis, position(m[0].a), texte)
                remplacements.append((m[0].a, m[-1].b, '${' + appel + '}'))
                couverts.append((m[0].a, m[-1].b))
                entier = entier or (m[0].a == 0 and m[-1].b == len(texte))
        # 2. attributs visibles des balises hors des phrases extraites ou signalées
        for el in elements:
            if el.genre != 'balise' or any(a <= el.a < b for a, b in couverts):
                continue
            for nom, va, vb in el.attrs:
                if nom not in ATTRIBUTS_VISIBLES or va is None or va == vb:
                    continue
                morceaux = []
                for p0, p1, k in self.decouper_sentinelles(texte, va, vb):
                    if k is None:
                        morceaux.append(Morceau('txt', a=p0, b=p1, guillemet='`'))
                        continue
                    m = self.morceau_expr(noeud.exprs[k][0], mode_expr) or Morceau('bar', noeuds=noeud.exprs[k][0])
                    m.a, m.b, m.k = p0, p1, k
                    morceaux.append(m)
                resultat = self.decouper_phrase(morceaux, texte)
                phrases = [] if isinstance(resultat, str) else [c for g, c in resultat if g == 'phrase' and c[1]]
                if isinstance(resultat, str) or len(phrases) > 1:
                    signaler(va, vb, 'attribut %s : %s' % (nom, resultat if isinstance(resultat, str)
                                                          else 'texte coupé par une expression'))
                    continue
                for g, m, d in phrases:
                    decision = self.juger(g, m, d, ci, 'html', texte)
                    if isinstance(decision, tuple):
                        signaler(va, vb, 'attribut %s : %s' % (nom, decision[1]))
                    elif decision == 'extraire':
                        appel = self.appel(m, ci, html_permis, position(va), texte)
                        remplacements.append((m[0].a, m[-1].b, '${' + appel + '}'))
        # 3. assemblage (les ${…} gardés sont réécrits récursivement)
        remplacements.sort()
        out = []
        p = 0
        for a, b, rep in remplacements:
            out.append(self.rendre_texte_gabarit(texte, p, a, noeud, expr_ctx))
            out.append(rep)
            p = b
        out.append(self.rendre_texte_gabarit(texte, p, len(texte), noeud, expr_ctx))
        if mode == 'brut' and seul and entier and len(remplacements) == 1:
            return remplacements[0][2][2:-1]
        return '`' + ''.join(out) + '`'

    def rendre_texte_gabarit(self, texte, a, b, noeud, ctx):
        out = []
        for p in range(a, b):
            c = texte[p]
            if '' <= c <= '':
                sous, ed, ef = noeud.exprs[ord(c) - SENTINELLE]
                out.append('${' + self.rendre_suite(sous, ctx, ed, ef) + '}')
            else:
                out.append(c)
        return ''.join(out)

    @staticmethod
    def decouper_sentinelles(texte, a, b):
        """[(p0, p1, None)] pour du texte, [(p, p + 1, k)] pour le ${…} numéro k."""
        res = []
        debut = a
        for p in range(a, b):
            c = texte[p]
            if '' <= c <= '':
                if p > debut:
                    res.append((debut, p, None))
                res.append((p, p + 1, ord(c) - SENTINELLE))
                debut = p + 1
        if b > debut:
            res.append((debut, b, None))
        return res

    def suite_visible(self, texte, a, b, ci):
        t = re.sub('[-]', '{}', texte[a:b])
        t = re.sub(r'<[^>]*>', ' ', decoder(t))
        net = nettoyer(t)
        if self.classement.exception_contexte(self.rel, ci) or self.classement.exception_texte(self.rel, net):
            return False
        return self.classement.visible_html(net)

    def morceaux_html(self, suite, texte, noeud, mode_expr, espaces=False):
        """Morceaux d'une suite (textes et balises en ligne) d'un gabarit ; (None, raison) si illisible. espaces :
        les sauts de ligne de mise en page des textes deviennent une espace dans la valeur (gabarit UI.html)."""
        morceaux = []
        pile = []
        for el in suite:
            if el.genre == 'texte':
                for p0, p1, k in self.decouper_sentinelles(texte, el.a, el.b):
                    if k is None:
                        morceaux.append(Morceau('txt', a=p0, b=p1, guillemet='`', espaces=espaces))
                        continue
                    m = self.morceau_expr(noeud.exprs[k][0], mode_expr)
                    if m is None:
                        return None, 'pluriel incertain (« == 1 » : zéro serait au pluriel)'
                    if m.genre == 'var' and not m.noeuds:
                        return None, 'expression vide dans le gabarit'
                    m.a, m.b, m.k = p0, p1, k
                    morceaux.append(m)
                continue
            variable = any(nom is None or (va is not None and any('' <= c <= '' for c in texte[va:vb]))
                           for nom, va, vb in el.attrs)
            m = Morceau('balise', a=el.a, b=el.b, nom=el.nom, fermante=el.fermante,
                        k='barriere' if variable else None)
            if el.nom not in BALISES_VIDES:
                if not el.fermante:
                    pile.append(m)
                else:
                    for j in range(len(pile) - 1, -1, -1):
                        if pile[j].nom == el.nom:
                            ouvrante = pile.pop(j)
                            ouvrante.partenaire = m
                            m.partenaire = ouvrante
                            if ouvrante.k == 'barriere':
                                m.k = 'barriere'
                            break
            morceaux.append(m)
        return morceaux, None


# ---------------------------------------------------------------------------------------------------------
# index.html : data-i18n et data-i18n-attr
# ---------------------------------------------------------------------------------------------------------

class AnalyseHtml:
    """Textes d'une page HTML statique : data-i18n sur un élément qui ne contient que du texte, data-i18n-attr pour
    les attributs visibles ; texte mêlé à des balises ou bordé d'espaces : au rapport."""

    def __init__(self, outil, rel, source, section):
        self.outil = outil
        self.classement = outil.classement
        self.rel = rel
        self.src = source
        self.section = section
        self.ligne = Lignes(source)
        self.unites = []
        self.relectures = []
        self.exclus = 0
        self.insertions = {}        # position → [(genre, attribut, unite)]
        self.elements = decouper_html(source)
        if self.elements is None:
            raise ErreurAnalyse('HTML illisible')

    def relire(self, position, texte, raison):
        self.relectures.append((position, self.ligne(position), court(texte), raison))

    def enregistrer(self, position, valeur, texte, composant):
        marqueur = '\x00CLE%d\x00' % len(self.outil.toutes_unites)
        unite = Unite(fichier=self.rel, position=position, ligne=self.ligne(position), section=self.section,
                      composant=composant, element=resume(valeur), valeur=valeur, appel='data-i18n',
                      texte=court(texte), marqueur=marqueur, original={'': texte}, vars={})
        self.unites.append(unite)
        self.outil.toutes_unites.append(unite)
        return unite

    @staticmethod
    def attributs(source, el):
        res = {}
        for nom, va, vb in el.attrs:
            if nom:
                res[nom] = source[va:vb] if va is not None else ''
        return res

    def rendre(self):
        src = self.src
        # arbre des éléments
        racine = {'el': None, 'enfants': [], 'parent': None}
        pile = [racine]
        for el in self.elements:
            if el.genre == 'balise' and not el.fermante:
                noeud = {'el': el, 'enfants': [], 'parent': pile[-1]}
                pile[-1]['enfants'].append(noeud)
                if el.nom not in BALISES_VIDES and not src[el.a:el.b].endswith('/>'):
                    pile.append(noeud)
            elif el.genre == 'balise':
                for j in range(len(pile) - 1, 0, -1):
                    if pile[j]['el'].nom == el.nom:
                        del pile[j:]
                        break
            else:
                pile[-1]['enfants'].append({'el': el, 'enfants': [], 'parent': pile[-1]})
        self.parcourir(racine, None)
        out = []
        p = 0
        for position in sorted(self.insertions):
            out.append(src[p:position])
            for texte in self.insertions[position]:
                out.append(texte)
            p = position
        out.append(src[p:])
        return ''.join(out)

    def composant(self, noeud):
        while noeud is not None:
            el = noeud['el']
            if el is not None:
                ident = self.attributs(self.src, el).get('id')
                if ident:
                    return serpent(ident.replace('-', '_'))
            noeud = noeud['parent']
        return 'page'

    def parcourir(self, noeud, ctx_id):
        el = noeud['el']
        src = self.src
        if el is not None and el.genre == 'balise' and el.nom in ('script', 'style', 'template'):
            return
        attrs = self.attributs(src, el) if el is not None and el.genre == 'balise' else {}
        if el is not None and el.genre == 'balise':
            self.traiter_attributs(noeud, el, attrs)
        textes = [e for e in noeud['enfants'] if e['el'].genre == 'texte']
        balises = [e for e in noeud['enfants'] if e['el'].genre == 'balise']
        visibles = [e for e in textes if self.classement.visible_html(nettoyer(src[e['el'].a:e['el'].b]))
                    and not self.classement.exception_texte(self.rel, nettoyer(src[e['el'].a:e['el'].b]))]
        if el is not None and visibles and 'data-i18n' not in attrs:
            brut = src[visibles[0]['el'].a:visibles[0]['el'].b]
            if balises or len(textes) > 1 or any(e['el'].genre == 'commentaire' for e in noeud['enfants']):
                tout = src[el.b:self.fin_contenu(noeud)]
                self.relire(el.a, tout, 'texte mêlé à des balises (data-i18n remplacerait tout le contenu)')
                return
            if brut != brut.strip():
                self.relire(visibles[0]['el'].a, brut, 'espaces en bord de texte (data-i18n les remplacerait)')
            else:
                texte = html.unescape(brut)
                if '{' in texte or '}' in texte:
                    self.relire(visibles[0]['el'].a, brut, 'accolade dans le texte (confusion avec une variable {…})')
                else:
                    unite = self.enregistrer(visibles[0]['el'].a, echapper_texte(texte), texte, self.composant(noeud))
                    self.inserer(el, ' data-i18n="%s"' % unite.marqueur)
            return
        for enfant in noeud['enfants']:
            if enfant['el'].genre == 'balise':
                self.parcourir(enfant, ctx_id)

    def fin_contenu(self, noeud):
        # fin approximative du contenu : dernière position couverte par les enfants
        fin = noeud['el'].b
        pile = [noeud]
        while pile:
            n = pile.pop()
            for e in n['enfants']:
                fin = max(fin, e['el'].b)
                pile.append(e)
        return fin

    def traiter_attributs(self, noeud, el, attrs):
        deja = {}
        for paire in attrs.get('data-i18n-attr', '').split(';'):
            if ':' in paire:
                nom, cle = paire.split(':', 1)
                deja[nom.strip()] = cle.strip()
        nouveaux = []
        for nom, va, vb in el.attrs:
            if nom not in ATTRIBUTS_VISIBLES or va is None or nom in deja:
                continue
            brut = self.src[va:vb]
            net = nettoyer(brut)
            if not self.classement.visible_html(net) or self.classement.exception_texte(self.rel, net):
                continue
            texte = html.unescape(brut)
            if '{' in texte or '}' in texte:
                self.relire(va, brut, 'accolade dans le texte (confusion avec une variable {…})')
                continue
            unite = self.enregistrer(va, echapper_texte(texte), texte, self.composant(noeud))
            nouveaux.append('%s:%s' % (nom, unite.marqueur))
        if not nouveaux:
            return
        if 'data-i18n-attr' in attrs:
            for nom, va, vb in el.attrs:
                if nom == 'data-i18n-attr' and va is not None:
                    self.insertions.setdefault(vb, []).append(';' + ';'.join(nouveaux))
        else:
            self.inserer(el, ' data-i18n-attr="%s"' % ';'.join(nouveaux))

    def inserer(self, el, texte):
        fin = el.b - 1
        if self.src[fin - 1] == '/':
            fin -= 1
        self.insertions.setdefault(fin, []).append(texte)


# ---------------------------------------------------------------------------------------------------------
# Dictionnaire (fr.js) : lecture et écriture des blocs de section
# ---------------------------------------------------------------------------------------------------------
RE_BLOC = re.compile(r'^// ==== section ([\w-]+) ====\n(.*?)^// ==== fin \1 ====\n?', re.M | re.S)


def lire_bloc(contenu):
    """(langue, {clé: valeur}) d'un bloc I18n.ajouter('xx', { … }) ; valeurs au format entre apostrophes."""
    arbre = construire_arbre(contenu)
    for i, n in enumerate(arbre):
        if est_nom(n, 'I18n') and i + 3 < len(arbre) and est_nom(arbre[i + 2], 'ajouter') and \
                est_groupe(arbre[i + 3], '('):
            args = couper_virgules(arbre[i + 3].enfants)
            langue = decoder(args[0][0].valeur)
            return langue, lire_objet(args[1][0], contenu)
    return 'fr', {}


def lire_objet(groupe, source):
    """{clé: valeur} d'un objet de dictionnaire ; valeur entre apostrophes (brute) ou {catégorie: valeur}."""
    def valeur(jeton):
        if not (isinstance(jeton, Jeton) and jeton.genre == 'chaine'):
            raise ErreurAnalyse('valeur de dictionnaire illisible à la position %d' % jeton.debut)
        guillemet = source[jeton.debut]
        return jeton.valeur if guillemet == "'" else vers_simple(jeton.valeur, guillemet)

    entrees = {}
    for partie in couper_virgules(groupe.enfants):
        if not partie:
            continue
        if len(partie) != 3 or not est_ponct(partie[1], ':'):
            raise ErreurAnalyse('entrée de dictionnaire illisible à la position %d' % partie[0].debut)
        cle = decoder(partie[0].valeur) if partie[0].genre == 'chaine' else partie[0].valeur
        v = partie[2]
        if isinstance(v, Groupe):
            formes = {}
            for sous in couper_virgules(v.enfants):
                if sous:
                    formes[sous[0].valeur if sous[0].genre == 'nom' else decoder(sous[0].valeur)] = valeur(sous[2])
            entrees[cle] = formes
        else:
            entrees[cle] = valeur(v)
    return entrees


def lire_dictionnaire(chemin):
    """{section: (langue, {clé: valeur})} d'un fichier de dictionnaire (vide s'il n'existe pas)."""
    chemin = Path(chemin)
    if not chemin.is_file():
        return {}
    texte = chemin.read_text(encoding='utf-8')
    res = {}
    for m in RE_BLOC.finditer(texte):
        res[m.group(1)] = lire_bloc(m.group(2))
    return res


def ecrire_bloc(section, langue, entrees):
    lignes = ['// ==== section %s ====' % section, "I18n.ajouter('%s', {" % langue]
    for cle in sorted(entrees):
        valeur = entrees[cle]
        if isinstance(valeur, dict):
            formes = ', '.join("%s: '%s'" % (c, valeur[c]) for c in CATEGORIES_PLURIEL if c in valeur)
            lignes.append("  '%s': { %s }," % (cle, formes))
        else:
            lignes.append("  '%s': '%s'," % (cle, valeur))
    lignes.append('});')
    lignes.append('// ==== fin %s ====' % section)
    return '\n'.join(lignes) + '\n'


def completer_dictionnaire(texte, ajouts):
    """Texte du dictionnaire avec les entrées ajoutées ({section: {clé: valeur}}), blocs triés."""
    for section in sorted(ajouts):
        m = None
        for bloc in RE_BLOC.finditer(texte):
            if bloc.group(1) == section:
                m = bloc
                break
        if m:
            langue, entrees = lire_bloc(m.group(2))
            entrees.update(ajouts[section])
            texte = texte[:m.start()] + ecrire_bloc(section, langue, entrees) + texte[m.end():]
        else:
            bloc = ecrire_bloc(section, 'fr', ajouts[section])
            if texte and not texte.endswith('\n'):
                texte += '\n'
            texte = texte + ('\n' if texte else '') + bloc
    return texte


# ---------------------------------------------------------------------------------------------------------
# L'outil
# ---------------------------------------------------------------------------------------------------------

def lire_source(chemin):
    donnees = Path(chemin).read_bytes()
    bom = donnees.startswith(b'\xef\xbb\xbf')
    return donnees[3 if bom else 0:].decode('utf-8'), bom


def ecrire_source(chemin, texte, bom=False):
    Path(chemin).parent.mkdir(parents=True, exist_ok=True)
    Path(chemin).write_bytes((b'\xef\xbb\xbf' if bom else b'') + texte.encode('utf-8'))


class Resultat:
    def __init__(self):
        self.unites = []            # Unite (avec clé)
        self.relectures = []        # (fichier, ligne, texte, raison)
        self.collisions = []        # (clé voulue, clé donnée, fichier, ligne, valeur)
        self.nouvelles = {}         # section → {clé: valeur}
        self.fichiers_modifies = []
        self.erreurs = []           # (fichier, message)
        self.fichiers_exclus = []   # (fichier, classe d'exception)
        self.exclus = 0
        self.essai = False
        self.section = None
        self.dictionnaire = None


class Extracteur:
    def __init__(self, racine=RACINE_DEPOT, exceptions=None):
        self.racine = Path(racine)
        self.classement = Classement(self.racine, exceptions)
        self.toutes_unites = []
        self.valeurs = {}           # clé → valeur des dictionnaires (lus avant l'analyse)
        self._fonctions_fragments = None

    def fonctions_fragments(self):
        """Fonctions du dépôt (js/, acces/porte.js) qui rendent un fragment HTML : jamais variables de phrase."""
        if self._fonctions_fragments is None:
            arbres = []
            for fichiers in tous_les_fichiers(self.racine).values():
                for rel in fichiers:
                    if not rel.endswith('.js') or self.classement.exception_fichier(rel):
                        continue
                    try:
                        arbres.append(construire_arbre(lire_source(self.racine / rel)[0]))
                    except (ErreurAnalyse, OSError, UnicodeDecodeError):
                        continue
            self._fonctions_fragments = fonctions_fragments(arbres)
        return self._fonctions_fragments

    def charger_valeurs(self, *dictionnaires):
        self.valeurs = {}
        for chemin in dictionnaires:
            for section, (langue, entrees) in lire_dictionnaire(self.racine / chemin).items():
                self.valeurs.update(entrees)

    def analyser(self, rel, section):
        """Analyse d'un fichier (sans rien écrire) : objet AnalyseFichier ou AnalyseHtml, et source réécrite."""
        source, bom = lire_source(self.racine / rel)
        if rel.endswith('.html'):
            analyse = AnalyseHtml(self, rel, source, section)
        else:
            analyse = AnalyseFichier(self, rel, source, section)
        return analyse, analyse.rendre(), source, bom

    def extraire(self, section, fichiers, essai=False, dictionnaire=DICTIONNAIRE, commun=False,
                 commun_existant=False):
        res = Resultat()
        res.essai = essai
        res.section = section
        res.dictionnaire = dictionnaire
        self.toutes_unites = []
        if section not in SECTIONS:
            raise ValueError('section inconnue : %s (sections : %s)' % (section, ', '.join(SECTIONS)))
        fichiers = sorted(set(f.replace('\\', '/') for f in fichiers))
        self.charger_valeurs(DICTIONNAIRE, dictionnaire)
        rendus = []
        for rel in fichiers:
            regle = self.classement.exception_fichier(rel)
            if regle:
                res.fichiers_exclus.append((rel, regle['classe']))
                continue
            try:
                analyse, nouveau, source, bom = self.analyser(rel, section)
            except (ErreurAnalyse, OSError, UnicodeDecodeError) as erreur:
                res.erreurs.append((rel, str(erreur)))
                continue
            rendus.append((rel, analyse, nouveau, source, bom))
            res.exclus += analyse.exclus
            for position, ligne, texte, raison in analyse.relectures:
                res.relectures.append((rel, ligne, texte, raison))
        repetes = self.textes_repetes(section) if commun else {}
        self.attribuer(res, dictionnaire, repetes, commun, commun_existant)
        # remplacement des marqueurs et écriture
        for rel, analyse, nouveau, source, bom in rendus:
            for unite in analyse.unites:
                nouveau = nouveau.replace(unite.marqueur, unite.cle)
            if nouveau != source:
                res.fichiers_modifies.append(rel)
                if not essai:
                    ecrire_source(self.racine / rel, nouveau, bom)
            res.unites.extend(analyse.unites)
        if res.nouvelles:
            res.fichiers_modifies.append(dictionnaire)
            if not essai:
                chemin = self.racine / dictionnaire
                texte, bom = lire_source(chemin) if chemin.is_file() else ('', False)
                ecrire_source(chemin, completer_dictionnaire(texte, res.nouvelles), bom)
        res.unites.sort(key=lambda u: (u.fichier, u.position))
        res.relectures.sort(key=lambda r: (r[0], r[1]))
        return res

    def textes_repetes(self, section):
        """{valeur: {domaines}} des textes extractibles de tout le dépôt (pour --commun)."""
        repetes = {}
        sauvegarde = self.toutes_unites
        for domaine, fichiers in tous_les_fichiers(self.racine).items():
            for rel in fichiers:
                if self.classement.exception_fichier(rel):
                    continue
                self.toutes_unites = []
                try:
                    self.analyser(rel, domaine)
                except (ErreurAnalyse, OSError, UnicodeDecodeError):
                    continue
                for unite in self.toutes_unites:
                    repetes.setdefault(canon(unite.valeur), set()).add(domaine)
        self.toutes_unites = sauvegarde
        return repetes

    def attribuer(self, res, dictionnaire, repetes, commun, commun_existant=False):
        """Clés des unités, dans l'ordre des fichiers et des positions ; collisions résolues par _2, _3…
        commun_existant : reprend une clé commun.* déjà écrite pour un texte identique, n'en crée jamais."""
        existantes = {}
        sections_existantes = lire_dictionnaire(self.racine / dictionnaire)
        for section, (langue, entrees) in sections_existantes.items():
            for cle, valeur in entrees.items():
                existantes[cle] = valeur
        par_fichier = {}
        communes = ({canon(v): c for c, v in sections_existantes.get('commun', ('fr', {}))[1].items()}
                    if commun or commun_existant else {})
        for unite in sorted(self.toutes_unites, key=lambda u: (u.fichier, u.position)):
            vk = canon(unite.valeur)
            if (unite.fichier, unite.section, vk) in par_fichier:
                unite.cle = par_fichier[(unite.fichier, unite.section, vk)]
                continue
            if (commun or commun_existant) and vk in communes:
                unite.cle = communes[vk]
                unite.commun = True
                continue
            section_cible = unite.section
            base = '%s.%s.%s' % (unite.section, unite.composant, unite.element)
            if commun and len(repetes.get(vk, ())) >= 2:
                section_cible = 'commun'
                base = 'commun.%s' % unite.element
                unite.commun = True
            cle = base
            rang = 1
            while True:
                if cle not in existantes:
                    existantes[cle] = unite.valeur
                    res.nouvelles.setdefault(section_cible, {})[cle] = unite.valeur
                    break
                if canon(existantes[cle]) == vk:
                    break
                rang += 1
                cle = '%s_%d' % (base, rang)
            if cle != base:
                res.collisions.append((base, cle, unite.fichier, unite.ligne, affichage(unite.valeur)))
            unite.cle = cle
            par_fichier[(unite.fichier, unite.section, vk)] = cle
            if section_cible == 'commun':
                communes[vk] = cle


def reconstituer(valeur, formes_vars):
    """Texte affiché par une valeur du dictionnaire, chaque {nom} remplacé par l'expression d'origine ⟦…⟧."""
    return re.sub(r'\{(\w+)\}', lambda m: formes_vars.get(m.group(1), m.group(0)), decoder(valeur))


def verifier_unite(unite):
    """Vrai si la valeur écrite dans le dictionnaire redonne exactement le texte d'avant (chaque forme)."""
    if isinstance(unite.valeur, dict):
        return all(reconstituer(unite.valeur[f], unite.vars) == unite.original[f] for f in unite.original)
    return reconstituer(unite.valeur, unite.vars) == unite.original['']


# ---------------------------------------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------------------------------------

RE_NOM_GENERIQUE = re.compile(r'^(v\d+|\w*[A-Za-z_]\d+|[A-Z][A-Z0-9_]+)$')


def variables_a_nommer(unite):
    """Variables d'une unité dont le nom ne dit rien au traducteur : v1, v2 (expression sans nom), pourcent2
    (doublon numéroté), MINIMUM (constante en capitales). Le pluriel {n} est un nom convenu (T237)."""
    return sorted(nom for nom in (unite.vars or {}) if nom != 'n' and RE_NOM_GENERIQUE.match(nom))


def rapport(res):
    lignes = []
    titre = 'Extraction des textes — section %s → %s' % (res.section, res.dictionnaire)
    if res.essai:
        titre += ' (essai : rien n\'est écrit)'
    lignes.append(titre)
    par_appel = {}
    for u in res.unites:
        genre = 'pluriels' if isinstance(u.valeur, dict) else ('I18n.html' if u.appel == 'html' else
                                                                 ('data-i18n' if u.appel == 'data-i18n' else 'I18n.t'))
        par_appel[genre] = par_appel.get(genre, 0) + 1
    detail = ', '.join('%s : %d' % (k, par_appel[k]) for k in sorted(par_appel))
    nb_entrees = sum(len(v) for v in res.nouvelles.values())
    lignes.append('Textes extraits : %d (%s) ; entrées nouvelles dans le dictionnaire : %d'
                  % (len(res.unites), detail or 'aucun', nb_entrees))
    a_nommer = [(u, noms) for u in res.unites for noms in [variables_a_nommer(u)] if noms]
    lignes.append('Exceptions (jamais extraites) : %d ; cas à relire : %d ; collisions résolues : %d ; '
                  'textes aux variables à nommer : %d'
                  % (res.exclus, len(res.relectures), len(res.collisions), len(a_nommer)))
    for rel, classe in res.fichiers_exclus:
        lignes.append('Fichier exclu en entier (%s) : %s' % (classe, rel))
    if res.relectures:
        par_raison = {}
        for r in res.relectures:
            par_raison[r[3]] = par_raison.get(r[3], 0) + 1
        lignes.append('Cas à relire par raison :')
        for raison in sorted(par_raison, key=lambda r: (-par_raison[r], r)):
            lignes.append('  %4d  %s' % (par_raison[raison], raison))
    verbe = 'seraient modifiés' if res.essai else 'modifiés'
    lignes.append('Fichiers %s : %s' % (verbe, ', '.join(res.fichiers_modifies) or 'aucun'))
    for rel, message in res.erreurs:
        lignes.append('ERREUR %s : %s' % (rel, message))
    if res.relectures:
        lignes.append('')
        lignes.append('== À relire (rien n\'est réécrit) ==')
        for rel, ligne, texte, raison in res.relectures:
            lignes.append('%s:%d [%s] « %s »' % (rel, ligne, raison, texte))
    communes = [u for u in res.unites if u.commun]
    if communes:
        lignes.append('')
        lignes.append('== Clés commun.* employées (%d) : vérifier même sens ET même rôle, sinon clé du domaine '
                      'à la main ==' % len(communes))
        for u in communes:
            lignes.append('%s:%d %s = %s' % (u.fichier, u.ligne, u.cle, affichage(u.valeur)))
    if res.collisions:
        lignes.append('')
        lignes.append('== Collisions de clés résolues ==')
        for base, cle, rel, ligne, valeur in res.collisions:
            lignes.append('%s:%d %s déjà prise par un autre texte → %s = %s' % (rel, ligne, base, cle, valeur))
    if a_nommer:
        lignes.append('')
        lignes.append('== Variables à nommer (nom donné faute de mieux, à renommer à la main dans la clé et '
                      "l'appel) ==")
        for u, noms in a_nommer:
            lignes.append('%s:%d %s : {%s} = %s' % (u.fichier, u.ligne, u.cle, '}, {'.join(noms), affichage(u.valeur)))
    if res.unites:
        lignes.append('')
        lignes.append('== Extraits ==')
        for u in res.unites:
            lignes.append('%s:%d %s %s = %s' % (u.fichier, u.ligne, {'t': 'I18n.t', 'html': 'I18n.html'}.get(
                u.appel, u.appel), u.cle, affichage(u.valeur)))
    return '\n'.join(lignes) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description='Extrait les textes visibles vers le dictionnaire (fr.js).')
    parser.add_argument('fichiers', nargs='*', help='fichiers JS ou HTML (chemins relatifs à la racine)')
    parser.add_argument('--section', help='section du dictionnaire (planning, socle, commun…)')
    parser.add_argument('--domaine', help='prend les fichiers du domaine (et sa section par défaut)')
    parser.add_argument('--essai', action='store_true', help="n'écrit rien, rapport seulement")
    parser.add_argument('--dictionnaire', help='défaut : celui du domaine (js/i18n/fr.js ; js/i18n/aide/fr.js pour '
                                               'aide-longue)')
    parser.add_argument('--commun', action='store_true', help='clé commun.* pour un texte de plusieurs domaines')
    parser.add_argument('--commun-existant', action='store_true',
                        help='reprend les clés commun.* existantes pour un texte identique, sans en créer')
    parser.add_argument('--rapport', help='écrit aussi le rapport dans ce fichier')
    parser.add_argument('--racine', default=str(RACINE_DEPOT))
    parser.add_argument('--exceptions')
    args = parser.parse_args(argv)
    racine = Path(args.racine)
    fichiers = list(args.fichiers)
    section = args.section
    dictionnaire = args.dictionnaire
    if args.domaine:
        if args.domaine not in DOMAINES:
            parser.error('domaine inconnu : %s' % args.domaine)
        fichiers += fichiers_du_domaine(racine, args.domaine)
        section = section or section_du_domaine(args.domaine)
        dictionnaire = dictionnaire or dictionnaire_du_domaine(args.domaine)
    if not section or not fichiers:
        parser.error('donnez une section et des fichiers (ou --domaine)')
    extracteur = Extracteur(racine, args.exceptions)
    try:
        res = extracteur.extraire(section, fichiers, essai=args.essai, dictionnaire=dictionnaire or DICTIONNAIRE,
                                  commun=args.commun, commun_existant=args.commun_existant)
    except ValueError as erreur:
        parser.error(str(erreur))
    texte = rapport(res)
    sys.stdout.write(texte)
    if args.rapport:
        Path(args.rapport).write_text(texte, encoding='utf-8', newline='\n')
    return 2 if res.erreurs else 0


if __name__ == '__main__':
    sys.exit(main())
