# -*- coding: utf-8 -*-
"""Lecture des dictionnaires et comparaison d'une langue au français (chantier multilingue, Lot 3, T264 ;
critères CS149 et CS151).

Appelé par outils/controler_textes.py : « --langue <code> » (répétable) compare cette langue, déclarée ou non ; sans
--langue, chaque langue déclarée par js/i18n/langues.js autre que le français est comparée. --domaine limite la
comparaison aux sections de ces domaines (par nom de section, comme les clés orphelines du français).

Une langue <code> se lit dans js/i18n/<code>.js et js/i18n/aide/<code>.js (aide longue, facultative). Écarts
signalés (chacun rend le code retour non nul) :
- clé du français absente de la langue (« manquante ») ; exception : tant que js/i18n/aide/<code>.js n'existe pas
  ou ne définit aucune clé (une langue déclarée le fournit, « vide s'il le faut » : js/i18n/langues.js), les clés de
  l'aide longue (js/i18n/aide/fr.js) manquantes ne sont qu'un avertissement compté à part : js/i18n.js les prend en
  français sans rien dire, c'est voulu. Dès que ce fichier a une clé, ses clés manquantes comptent ;
- clé de la langue absente du français (« orpheline ») ;
- variables {…} différentes : ensemble des variables de l'entrée, toutes catégories de pluriel réunies ;
- pluriel : une entrée plurielle en français l'est dans la langue, avec exactement les catégories requises par la
  langue (CATEGORIES_REQUISES) ; une entrée simple en français reste simple ;
- clé rangée dans une autre section (ou un autre fichier) que dans le français ;
- clé définie deux fois ; bloc écrit pour une autre langue (I18n.ajouter('fr', …) dans en.js écraserait le
  français) ; I18n.ajouter hors d'une section « // ==== section … ==== » (ses clés ne seraient pas lues ici).
Une valeur identique au français (MTBF, Prévo…) n'est pas un écart.
"""
import re
from pathlib import Path

import extraire_textes as ext
from jslex import ErreurAnalyse, Groupe, Jeton, Lignes, construire_arbre, decoder

REFERENCE = 'fr'
DECLARATIONS = 'js/i18n/langues.js'
RE_VARIABLE = re.compile(r'\{(\w+)\}')
RE_CODE = re.compile(r'^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$')          # même motif que js/i18n.js
RE_AJOUTER = re.compile(r'^[ \t]*I18n\.ajouter\s*\(', re.M)
PLAFOND = 50                                                         # lignes au plus par rubrique du rapport

# Catégories de pluriel REQUISES par langue, pour des nombres entiers seulement (Prévo compte des ordres, des jours,
# des pièces : jamais de décimales dans un pluriel). Règles CLDR, celles d'Intl.PluralRules qu'emploie js/i18n.js.
# « many » existe en français, en italien et en portugais, mais il n'est pas requis : pour un entier, il ne sert
# qu'aux multiples exacts d'un million (« 1 000 000 de pièces ») et aux grands nombres en notation compacte
# (« 2 M »), que Prévo n'affiche pas ; s'il venait à servir, js/i18n.js prendrait « other », la forme juste à un
# « de » près. Une catégorie en plus des requises est un écart (personne ne la relirait).
CATEGORIES_REQUISES = {
    'fr': ('one', 'other'),
    'en': ('one', 'other'),
    'tr': ('one', 'other'),
    'it': ('one', 'other'),
    'pt-PT': ('one', 'other'),
}
CATEGORIES_PAR_DEFAUT = ('one', 'other')                             # code absent de la table


def categories_requises(code):
    return CATEGORIES_REQUISES.get(code, CATEGORIES_PAR_DEFAUT)


def fichiers_de(code):
    """(dictionnaire, aide longue) d'une langue : js/i18n/<code>.js, js/i18n/aide/<code>.js."""
    return 'js/i18n/%s.js' % code, 'js/i18n/aide/%s.js' % code


def variables_de(valeur):
    formes = valeur.values() if isinstance(valeur, dict) else [valeur]
    return {nom for forme in formes for nom in RE_VARIABLE.findall(decoder(forme))}


class Signalement:
    __slots__ = ('genre', 'fichier', 'ligne', 'message')

    def __init__(self, genre, fichier, ligne, message):
        self.genre = genre
        self.fichier = fichier
        self.ligne = ligne
        self.message = message

    def __repr__(self):
        return 'Signalement(%s, %s:%s, %s)' % (self.genre, self.fichier, self.ligne, self.message)


# ---------------------------------------------------------------------------------------------------------
# Lecture d'une langue
# ---------------------------------------------------------------------------------------------------------

class Langue:
    """Entrées d'une langue : {clé: (section, valeur, fichier)} ; valeur brute entre apostrophes ou
    {catégorie: valeur} pour un pluriel. lignes : {clé: ligne de sa dernière définition} ; doublons :
    [(clé, fichier, ligne)] ; problemes : [(fichier, ligne, message)] (bloc d'une autre langue, I18n.ajouter hors
    d'une section). Lève ErreurAnalyse pour un fichier illisible."""

    def __init__(self, code, racine, fichiers):
        self.code = code
        self.entrees = {}
        self.lignes = {}
        self.doublons = []
        self.problemes = []
        self.fichiers = []
        for rel in fichiers:
            chemin = Path(racine) / rel
            if chemin.is_file():
                self.fichiers.append(rel)
                self._lire(rel, chemin.read_text(encoding='utf-8'))

    def _lire(self, rel, texte):
        ligne = Lignes(texte)
        blocs = list(ext.RE_BLOC.finditer(texte))
        for m in RE_AJOUTER.finditer(texte):
            if not any(b.start(2) <= m.start() < b.end(2) for b in blocs):
                self.problemes.append((rel, ligne(m.start()), 'I18n.ajouter hors d\'une section '
                                       '« // ==== section … ==== » : ses clés ne sont pas lues'))
        for bloc in blocs:
            section, contenu, debut = bloc.group(1), bloc.group(2), bloc.start(2)
            try:
                arbre = construire_arbre(contenu)
            except ErreurAnalyse as erreur:
                raise ErreurAnalyse('section %s : %s' % (section, erreur))
            for i, n in enumerate(arbre):
                if not (ext.est_nom(n, 'I18n') and i + 3 < len(arbre) and ext.est_nom(arbre[i + 2], 'ajouter')
                        and ext.est_groupe(arbre[i + 3], '(')):
                    continue
                args = ext.couper_virgules(arbre[i + 3].enfants)
                langue = decoder(args[0][0].valeur) if args and args[0] and isinstance(args[0][0], Jeton) else '?'
                if langue != self.code:
                    self.problemes.append((rel, ligne(debut + n.debut), 'section %s : bloc écrit pour la langue '
                                           '« %s » (attendu : « %s »)' % (section, langue, self.code)))
                if len(args) > 1 and args[1] and ext.est_groupe(args[1][0], '{'):
                    self._entrees(rel, section, args[1][0], contenu, lambda p: ligne(debut + p))

    def _entrees(self, rel, section, groupe, source, ligne):
        """Même lecture que extraire_textes.lire_objet, en gardant la ligne et les doublons."""
        def valeur(jeton):
            if not (isinstance(jeton, Jeton) and jeton.genre == 'chaine'):
                raise ErreurAnalyse('section %s : valeur illisible ligne %d' % (section, ligne(jeton.debut)))
            guillemet = source[jeton.debut]
            return jeton.valeur if guillemet == "'" else ext.vers_simple(jeton.valeur, guillemet)

        for partie in ext.couper_virgules(groupe.enfants):
            if not partie:
                continue
            if len(partie) != 3 or not ext.est_ponct(partie[1], ':'):
                raise ErreurAnalyse('section %s : entrée illisible ligne %d' % (section, ligne(partie[0].debut)))
            cle = decoder(partie[0].valeur) if partie[0].genre == 'chaine' else partie[0].valeur
            v = partie[2]
            if isinstance(v, Groupe):
                v = {(s[0].valeur if s[0].genre == 'nom' else decoder(s[0].valeur)): valeur(s[2])
                     for s in ext.couper_virgules(v.enfants) if s}
            else:
                v = valeur(v)
            if cle in self.entrees:
                self.doublons.append((cle, rel, ligne(partie[0].debut)))
            self.entrees[cle] = (section, v, rel)
            self.lignes[cle] = ligne(partie[0].debut)


def langues_declarees(racine):
    """Codes déclarés par js/i18n/langues.js (I18n.declarer({ code: 'xx', … })), dans l'ordre."""
    chemin = Path(racine) / DECLARATIONS
    if not chemin.is_file():
        return []
    arbre = construire_arbre(chemin.read_text(encoding='utf-8'))
    codes = []
    for i, n in enumerate(arbre):
        if not (ext.est_nom(n, 'I18n') and i + 3 < len(arbre) and ext.est_nom(arbre[i + 2], 'declarer')
                and ext.est_groupe(arbre[i + 3], '(')):
            continue
        objet = arbre[i + 3].enfants
        if len(objet) == 1 and ext.est_groupe(objet[0], '{'):
            for partie in ext.couper_virgules(objet[0].enfants):
                if len(partie) == 3 and ext.est_nom(partie[0], 'code') and isinstance(partie[2], Jeton) \
                        and partie[2].genre == 'chaine':
                    codes.append(decoder(partie[2].valeur))
    return codes


# ---------------------------------------------------------------------------------------------------------
# Comparaison au français
# ---------------------------------------------------------------------------------------------------------

def _liste(categories):
    ordre = {c: i for i, c in enumerate(ext.CATEGORIES_PLURIEL)}
    return ', '.join(sorted(categories, key=lambda c: (ordre.get(c, len(ordre)), c)))


class Comparaison:
    """Écarts d'une langue avec le français : signalements, clés de l'aide longue en repli (avertissement), erreurs
    (fichier illisible)."""

    def __init__(self, code, sections=None):
        self.code = code
        self.sections = sections
        self.requises = categories_requises(code)
        self.fichiers = []
        self.aide = False                   # js/i18n/aide/<code>.js existe et définit au moins une clé
        self.signalements = []
        self.repli_aide = []                # clés de l'aide longue absentes, prises en français (voulu)
        self.erreurs = []

    def signaler(self, genre, fichier, ligne, message):
        self.signalements.append(Signalement(genre, fichier, ligne, message))

    def retenue(self, section):
        return self.sections is None or section in self.sections

    def lancer(self, racine, francais):
        principal, aide = fichiers_de(self.code)
        try:
            langue = Langue(self.code, racine, (principal, aide))
        except ErreurAnalyse as erreur:
            self.erreurs.append((principal, str(erreur)))
            return self
        self.fichiers = langue.fichiers
        self.aide = any(rel == aide for _, _, rel in langue.entrees.values())

        def lieu(rel, section):
            return 'section %s' % section + ('' if rel == principal else ' de %s' % rel)

        for cle, (section, valeur, rel_fr) in sorted(francais.entrees.items()):
            # retenue par sa section française, ou par celle où la langue l'a rangée (rangée ailleurs : signalée)
            if not (self.retenue(section) or (cle in langue.entrees and self.retenue(langue.entrees[cle][0]))):
                continue
            rel = rel_fr.replace('/%s.js' % REFERENCE, '/%s.js' % self.code)   # même place que dans le français
            if cle not in langue.entrees:
                if rel == aide and not self.aide:
                    self.repli_aide.append(cle)
                else:
                    self.signaler('manquante', rel, None, '%s — absente (%s)' % (cle, lieu(rel, section)))
                continue
            section_l, valeur_l, rel_l = langue.entrees[cle]
            ligne = langue.lignes[cle]
            if (section_l, rel_l) != (section, rel):
                self.signaler('section', rel_l, ligne, '%s — %s, en français : %s' % (
                    cle, lieu(rel_l, section_l), lieu(rel, section)))
            self.comparer(cle, valeur, valeur_l, rel_l, ligne)
        for cle, (section, valeur, rel) in sorted(langue.entrees.items()):
            if cle not in francais.entrees and self.retenue(section):
                self.signaler('orpheline', rel, langue.lignes[cle], '%s — absente du français' % cle)
        for cle, rel, ligne in langue.doublons:
            if self.retenue(langue.entrees[cle][0]):
                self.signaler('doublon', rel, ligne, '%s — définie deux fois' % cle)
        for rel, ligne, message in langue.problemes:
            self.signaler('bloc', rel, ligne, message)
        self.signalements.sort(key=lambda s: (s.genre, s.fichier, s.ligne or 0, s.message))
        return self

    def comparer(self, cle, francais, valeur, rel, ligne):
        attendues, trouvees = variables_de(francais), variables_de(valeur)
        if attendues != trouvees:
            ecarts = []
            if attendues - trouvees:
                ecarts.append('manque {%s}' % '}, {'.join(sorted(attendues - trouvees)))
            if trouvees - attendues:
                ecarts.append('en trop {%s}' % '}, {'.join(sorted(trouvees - attendues)))
            self.signaler('variables', rel, ligne, '%s — %s' % (cle, ' ; '.join(ecarts)))
        if isinstance(francais, dict) and not isinstance(valeur, dict):
            self.signaler('pluriel', rel, ligne, '%s — pluriel en français, texte simple ici (attendu : { %s })' % (
                cle, _liste(self.requises)))
        elif isinstance(valeur, dict) and not isinstance(francais, dict):
            self.signaler('pluriel', rel, ligne, '%s — texte simple en français, pluriel ici' % cle)
        elif isinstance(valeur, dict):
            manquantes = set(self.requises) - set(valeur)
            en_trop = set(valeur) - set(self.requises)
            if manquantes:
                self.signaler('pluriel', rel, ligne, '%s — catégorie manquante : %s' % (cle, _liste(manquantes)))
            if en_trop:
                self.signaler('pluriel', rel, ligne, '%s — catégorie en trop : %s (requises en %s : %s)' % (
                    cle, _liste(en_trop), self.code, _liste(self.requises)))


def comparer(racine, code, francais, sections=None):
    """Comparaison de la langue `code` au français (Langue des dictionnaires français) ; sections : noms de section
    à comparer (None : toutes)."""
    return Comparaison(code, sections).lancer(racine, francais)


# ---------------------------------------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------------------------------------

TITRES = {
    'manquante': 'Clés du français absentes de la langue',
    'orpheline': 'Clés de la langue absentes du français',
    'variables': 'Variables {…} différentes du français',
    'pluriel': 'Pluriels différents de ceux requis par la langue',
    'section': 'Clés rangées ailleurs que dans le français',
    'doublon': 'Clés définies deux fois',
    'bloc': 'Blocs mal écrits',
}


def rapport(comparaison):
    """Lignes du rapport d'une langue : une rubrique par genre (compte, puis au plus PLAFOND lignes)."""
    c = comparaison
    principal, aide = fichiers_de(c.code)
    fichiers = principal + (', ' + aide if aide in c.fichiers else ' (%s absent)' % aide)
    lignes = ['Langue %s comparée au français — %s ; sections : %s ; pluriels requis : %s' % (
        c.code, fichiers, ', '.join(sorted(c.sections)) if c.sections else 'toutes', _liste(c.requises))]
    par_genre = {}
    for s in c.signalements:
        par_genre.setdefault(s.genre, []).append(s)
    for genre in ('manquante', 'orpheline', 'variables', 'pluriel', 'section', 'doublon', 'bloc'):
        liste = par_genre.get(genre, [])
        lignes.append('%s (%s) : %d' % (TITRES[genre], c.code, len(liste)))
        for s in liste[:PLAFOND]:
            lignes.append('  %s%s' % ('%s:%d  ' % (s.fichier, s.ligne) if s.ligne else '', s.message))
        if len(liste) > PLAFOND:
            lignes.append('  … et %d de plus' % (len(liste) - PLAFOND))
    if c.repli_aide:
        lignes.append('Avertissement (%s) : %d clé(s) de l\'aide longue sans traduction, prises en français sans '
                      'avertissement (%s %s) — voulu, ne compte pas' % (
                          c.code, len(c.repli_aide), aide, 'sans clé' if aide in c.fichiers else 'absent'))
    return lignes
