# -*- coding: utf-8 -*-
"""Analyse lexicale et structurelle minimale du JavaScript de Prévo (bibliothèque standard seulement).

Sert aux outils de textes (outils/extraire_textes.py, outils/controler_textes.py). Repris et nettoyé de
l'analyseur du Lot 0 (inventaire des textes) : mêmes règles pour les chaînes, gabarits, commentaires et
expressions régulières, mais avec un arbre (groupes de parenthèses, crochets, accolades) et les positions exactes
dans la source, pour pouvoir réécrire un littéral sans toucher au reste.

  jetons = lexer(source)            # liste plate de Jeton (les gabarits portent leurs expressions)
  arbre = construire_arbre(source)  # liste de nœuds : Jeton ou Groupe (récursif)

Un Jeton « chaine » garde le contenu BRUT entre ses guillemets (échappements compris) ; un Jeton « gabarit » garde
les positions de ses morceaux de texte bruts et, pour chaque ${…}, l'arbre de son expression.
"""
import bisect
import re

IDENT = re.compile(r'[A-Za-z_$\u00c0-\uffff][\w$\u00c0-\uffff]*')
NOMBRE = re.compile(r'0[xXoObB][0-9a-fA-F_]+n?|(?:\d[\d_]*(?:\.[\d_]*)?|\.\d[\d_]*)(?:[eE][+-]?\d+)?n?')
OPERATEURS = sorted(['>>>=', '...', '===', '!==', '**=', '<<=', '>>=', '>>>', '&&=', '||=', '??=', '=>', '==', '!=',
                     '<=', '>=', '&&', '||', '??', '?.', '+=', '-=', '*=', '/=', '%=', '&=', '|=', '^=', '++', '--',
                     '<<', '>>', '**'], key=len, reverse=True)
# Après ces mots, une barre oblique ouvre une expression régulière (et non une division).
MOTS_AVANT_REGEX = {'return', 'typeof', 'case', 'in', 'of', 'new', 'delete', 'void', 'throw', 'else', 'do',
                    'instanceof', 'yield', 'await'}
MOTS_CLES = MOTS_AVANT_REGEX | {'if', 'for', 'while', 'switch', 'catch', 'with', 'function', 'var', 'let', 'const',
                                'class', 'extends', 'super', 'this', 'null', 'undefined', 'true', 'false', 'try',
                                'finally', 'break', 'continue', 'default', 'import', 'export', 'async', 'static',
                                'get', 'set'}
FERMANT = {'(': ')', '[': ']', '{': '}'}


class ErreurAnalyse(Exception):
    """Source que l'analyseur ne sait pas lire (groupe non fermé, gabarit sans fin…)."""


class Jeton:
    """genre : 'nom', 'nombre', 'chaine', 'gabarit', 'regex', 'ponct'.
    valeur : le texte du jeton ; pour une chaîne, son contenu brut sans les guillemets.
    morceaux (gabarit) : [(debut, fin)] des textes bruts ; exprs (gabarit) : [(noeuds, debut, fin)] des ${…}."""
    __slots__ = ('genre', 'valeur', 'debut', 'fin', 'morceaux', 'exprs')

    def __init__(self, genre, valeur, debut, fin, morceaux=None, exprs=None):
        self.genre = genre
        self.valeur = valeur
        self.debut = debut
        self.fin = fin
        self.morceaux = morceaux
        self.exprs = exprs

    def est(self, genre, valeur=None):
        return self.genre == genre and (valeur is None or self.valeur == valeur)

    def __repr__(self):
        return 'Jeton(%s, %r)' % (self.genre, self.valeur)


class Groupe:
    """( … ), [ … ] ou { … } : ouvrant, enfants (nœuds), debut (position de l'ouvrant), fin (après le fermant)."""
    __slots__ = ('ouvrant', 'enfants', 'debut', 'fin')
    genre = 'groupe'

    def __init__(self, ouvrant, debut):
        self.ouvrant = ouvrant
        self.enfants = []
        self.debut = debut
        self.fin = None

    def est(self, genre, valeur=None):
        return genre == 'groupe' and (valeur is None or self.ouvrant == valeur)

    def __repr__(self):
        return 'Groupe(%s, %d)' % (self.ouvrant, len(self.enfants))


def decoder(brut):
    """Décode les échappements JS d'un texte brut de chaîne ou de gabarit (comme le ferait le moteur)."""
    def remplacer(m):
        e = m.group(1)
        if e[0] == 'u':
            return chr(int(e[2:-1], 16)) if e[1] == '{' else chr(int(e[1:], 16))
        if e[0] == 'x':
            return chr(int(e[1:], 16))
        if e in ('\n', '\r\n', '\r', '\u2028', '\u2029'):
            return ''
        return {'n': '\n', 't': '\t', 'r': '\r', '0': '\0', 'b': '\b', 'f': '\f', 'v': '\v'}.get(e, e)
    return re.sub(r'\\(u\{[0-9a-fA-F]+\}|u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|\r\n|.)', remplacer, brut, flags=re.S)


class Lignes:
    """Numéro de ligne (1…) d'une position de la source."""

    def __init__(self, source):
        self.debuts = [0] + [m.end() for m in re.finditer('\n', source)]

    def __call__(self, position):
        return bisect.bisect_right(self.debuts, position)


def _fin_chaine(src, i, guillemet):
    j = i + 1
    n = len(src)
    while j < n and src[j] != guillemet:
        if src[j] == '\\':
            j += 2
            continue
        if src[j] == '\n':
            raise ErreurAnalyse('chaîne non fermée à la position %d' % i)
        j += 1
    if j >= n:
        raise ErreurAnalyse('chaîne non fermée à la position %d' % i)
    return j + 1


def _regex_possible(precedent):
    if precedent is None:
        return True
    if precedent.genre == 'nom':
        return precedent.valeur in MOTS_AVANT_REGEX
    if precedent.genre == 'ponct':
        return precedent.valeur not in (')', ']', '}', '++', '--')
    return False


def lexer(src, i=0, arret_accolade=False):
    """Jetons de src à partir de i. Avec arret_accolade, s'arrête sur l'accolade fermante d'un ${…} et rend
    (jetons, position après l'accolade) ; sinon rend la liste des jetons."""
    n = len(src)
    jetons = []
    profondeur = 0
    while i < n:
        c = src[i]
        if c in ' \t\r\n\ufeff\u00a0\u2028\u2029':
            i += 1
            continue
        if src.startswith('//', i):
            j = src.find('\n', i)
            i = n if j < 0 else j
            continue
        if src.startswith('/*', i):
            j = src.find('*/', i + 2)
            if j < 0:
                raise ErreurAnalyse('commentaire non fermé à la position %d' % i)
            i = j + 2
            continue
        if c in '\'"':
            j = _fin_chaine(src, i, c)
            jetons.append(Jeton('chaine', src[i + 1:j - 1], i, j))
            i = j
            continue
        if c == '`':
            debut = i
            morceaux, exprs = [], []
            j = i + 1
            debut_morceau = j
            while True:
                if j >= n:
                    raise ErreurAnalyse('gabarit non fermé à la position %d' % debut)
                d = src[j]
                if d == '\\':
                    j += 2
                    continue
                if d == '`':
                    break
                if src.startswith('${', j):
                    morceaux.append((debut_morceau, j))
                    sous, fin_expr = lexer(src, j + 2, True)
                    exprs.append((sous, j + 2, fin_expr - 1))
                    j = fin_expr
                    debut_morceau = j
                    continue
                j += 1
            morceaux.append((debut_morceau, j))
            jetons.append(Jeton('gabarit', src[debut:j + 1], debut, j + 1, morceaux, exprs))
            i = j + 1
            continue
        precedent = jetons[-1] if jetons else None
        if c == '/' and _regex_possible(precedent):
            j = i + 1
            classe = False
            while j < n:
                d = src[j]
                if d == '\\':
                    j += 2
                    continue
                if d == '\n':
                    raise ErreurAnalyse('expression régulière non fermée à la position %d' % i)
                if d == '[':
                    classe = True
                elif d == ']':
                    classe = False
                elif d == '/' and not classe:
                    break
                j += 1
            j += 1
            while j < n and (src[j].isalpha()):
                j += 1
            jetons.append(Jeton('regex', src[i:j], i, j))
            i = j
            continue
        m = IDENT.match(src, i)
        if m and not c.isdigit():
            jetons.append(Jeton('nom', m.group(0), i, m.end()))
            i = m.end()
            continue
        if c.isdigit() or (c == '.' and i + 1 < n and src[i + 1].isdigit()):
            m = NOMBRE.match(src, i)
            jetons.append(Jeton('nombre', m.group(0), i, m.end()))
            i = m.end()
            continue
        if c == '{':
            profondeur += 1
        elif c == '}':
            if arret_accolade and profondeur == 0:
                return jetons, i + 1
            profondeur -= 1
        for op in OPERATEURS:
            if src.startswith(op, i):
                jetons.append(Jeton('ponct', op, i, i + len(op)))
                i += len(op)
                break
        else:
            jetons.append(Jeton('ponct', c, i, i + 1))
            i += 1
    if arret_accolade:
        raise ErreurAnalyse('expression ${…} non fermée')
    return jetons


def _arbre(jetons):
    racine = []
    pile = [(None, racine)]
    for jeton in jetons:
        if jeton.genre == 'gabarit':
            jeton.exprs = [(_arbre(sous), d, f) for sous, d, f in jeton.exprs]
        if jeton.genre == 'ponct' and jeton.valeur in FERMANT:
            groupe = Groupe(jeton.valeur, jeton.debut)
            pile[-1][1].append(groupe)
            pile.append((groupe, groupe.enfants))
            continue
        if jeton.genre == 'ponct' and jeton.valeur in (')', ']', '}'):
            groupe = pile[-1][0]
            if groupe is None or FERMANT[groupe.ouvrant] != jeton.valeur:
                raise ErreurAnalyse('« %s » inattendu à la position %d' % (jeton.valeur, jeton.debut))
            groupe.fin = jeton.fin
            pile.pop()
            continue
        pile[-1][1].append(jeton)
    if len(pile) > 1:
        raise ErreurAnalyse('« %s » non fermé à la position %d' % (pile[-1][0].ouvrant, pile[-1][0].debut))
    return racine


def construire_arbre(source):
    """Arbre de la source : liste de nœuds (Jeton ou Groupe)."""
    return _arbre(lexer(source))


# ---------------------------------------------------------------------------------------------------------
# Petits outils sur une suite de nœuds
# ---------------------------------------------------------------------------------------------------------

def texte_source(source, noeuds):
    """Texte source couvert par une suite de nœuds (vide si la suite est vide)."""
    if not noeuds:
        return ''
    return source[noeuds[0].debut:noeuds[-1].fin]


def normaliser(source, noeuds):
    """Forme compacte d'une expression (sans espaces ni commentaires), pour comparer deux expressions."""
    morceaux = []

    def parcourir(liste):
        for noeud in liste:
            if isinstance(noeud, Groupe):
                morceaux.append(noeud.ouvrant)
                parcourir(noeud.enfants)
                morceaux.append(FERMANT[noeud.ouvrant])
            elif noeud.genre == 'gabarit':
                morceaux.append(source[noeud.debut:noeud.fin])
            elif noeud.genre == 'chaine':
                morceaux.append(source[noeud.debut:noeud.fin])
            else:
                morceaux.append(noeud.valeur)
    parcourir(noeuds)
    return ' '.join(morceaux)


def nom_appele(noeuds, index):
    """Pour un Groupe « ( » en noeuds[index], le nom appelé (« UI.vide », « evenement.target.closest ») ou None.
    Une chaîne d'appels (x.map(…).join) donne « ….join »."""
    parties = []
    k = index - 1
    while k >= 0:
        noeud = noeuds[k]
        apres_point = k >= 1 and isinstance(noeuds[k - 1], Jeton) and noeuds[k - 1].genre == 'ponct' \
            and noeuds[k - 1].valeur in ('.', '?.')
        if isinstance(noeud, Jeton) and noeud.genre == 'nom':
            if not apres_point and noeud.valeur in MOTS_CLES and noeud.valeur not in ('this', 'super'):
                break
            parties.append(noeud.valeur)
            if apres_point:
                k -= 2
                continue
            break
        if parties and isinstance(noeud, Groupe):
            parties.append('…')
        break
    if not parties:
        return None
    return '.'.join(reversed(parties))
