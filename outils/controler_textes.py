# -*- coding: utf-8 -*-
"""Contrôle des textes de Prévo (chantier i18n, Lot 2, T236 ; critère CS147).

Bibliothèque standard seulement. Depuis la racine du dépôt :
  py -X utf8 outils/controler_textes.py                      # tout le dépôt
  py -X utf8 outils/controler_textes.py --domaine planning   # répétable : limite aux fichiers de ces domaines
Code retour : 0 si rien n'est à signaler, 1 sinon (2 : fichier illisible ou usage incorrect).

Ce qui est contrôlé :
1. textes visibles restés en dur : le même classement que outils/extraire_textes.py (un texte qu'il extrairait ou
   qu'il mettrait au rapport de relecture est signalé ; outils/exceptions_textes.json n'est jamais signalé) ;
2. clés utilisées (I18n.t, I18n.html, data-i18n, data-i18n-attr) et clés définies (js/i18n/fr.js,
   js/i18n/aide/fr.js) : clés manquantes, clés orphelines, variables {…} différentes entre un appel et sa valeur,
   variables au nom générique ({v1}, {pourcent2} : le traducteur ne saurait pas ce qu'elles contiennent) ;
3. index.html : le texte laissé dans la page sous un data-i18n est bien la valeur du dictionnaire ;
4. serveur.py (domaine « serveur », T246, D157) : contrôle en Python de outils/textes_serveur.py (messages
   traduisible(…) et section serveur de fr.js, textes en dur hors des règles de la console et des données).

Le lien domaine → fichiers est celui de extraire_textes.py (préfixes de js/modules, plus le socle, schema, porte ;
l'aide longue générée, js/modules/aide-ecrans-textes.js, est le domaine à part « aide-longue », hors du domaine
« aide »).

Lot 3 (préparé, pas fait) : comparer chaque langue au français (clés manquantes ou orphelines par langue,
mêmes variables, catégories de pluriel) — voir la classe Langue et la note « Lot 3 » plus bas.
"""
import argparse
import html
import re
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
if str(ICI) not in sys.path:
    sys.path.insert(0, str(ICI))
import extraire_textes as ext  # noqa: E402
import textes_serveur  # noqa: E402
from jslex import ErreurAnalyse, Groupe, Jeton, Lignes, construire_arbre, decoder  # noqa: E402

DICTIONNAIRES = ('js/i18n/fr.js', 'js/i18n/aide/fr.js')
RE_DATA_I18N = re.compile(r'\bdata-i18n="([^"]*)"')
RE_DATA_I18N_ATTR = re.compile(r'\bdata-i18n-attr="([^"]*)"')
RE_VARIABLE = re.compile(r'\{(\w+)\}')


class Signalement:
    __slots__ = ('genre', 'fichier', 'ligne', 'message')

    def __init__(self, genre, fichier, ligne, message):
        self.genre = genre
        self.fichier = fichier
        self.ligne = ligne
        self.message = message

    def __repr__(self):
        return 'Signalement(%s, %s:%s, %s)' % (self.genre, self.fichier, self.ligne, self.message)


class Utilisation:
    """Une clé employée dans le code : cle (None si dynamique), prefixe (clé construite : 'valeurs.' + x),
    variables passées (None si on ne peut pas les lire), fonction ('t', 'html', 'data-i18n', 'data-i18n-attr')."""
    __slots__ = ('fichier', 'ligne', 'cle', 'prefixe', 'variables', 'fonction')

    def __init__(self, fichier, ligne, cle=None, prefixe=None, variables=None, fonction='t'):
        self.fichier = fichier
        self.ligne = ligne
        self.cle = cle
        self.prefixe = prefixe
        self.variables = variables
        self.fonction = fonction


# ---------------------------------------------------------------------------------------------------------
# Dictionnaires (structure prête pour les autres langues du Lot 3)
# ---------------------------------------------------------------------------------------------------------

class Langue:
    """Entrées d'une langue : {clé: (section, valeur, fichier)} ; valeur brute entre apostrophes ou
    {catégorie: valeur} pour un pluriel."""

    def __init__(self, code, racine, fichiers):
        self.code = code
        self.entrees = {}
        self.doublons = []
        for rel in fichiers:
            for section, (langue, entrees) in ext.lire_dictionnaire(Path(racine) / rel).items():
                for cle, valeur in entrees.items():
                    if cle in self.entrees:
                        self.doublons.append((cle, rel))
                    self.entrees[cle] = (section, valeur, rel)


def variables_de(valeur):
    formes = valeur.values() if isinstance(valeur, dict) else [valeur]
    return {nom for forme in formes for nom in RE_VARIABLE.findall(decoder(forme))}


# Lot 3 : la comparaison d'une langue avec le français (clés manquantes ou orphelines, variables {…} différentes,
# catégories de pluriel attendues par Intl.PluralRules de la langue) viendra ici, avec ses tests ; le Lot 2 n'a que
# le français. La classe Langue et variables_de() ci-dessus lui serviront telles quelles.


# ---------------------------------------------------------------------------------------------------------
# Clés employées dans le code
# ---------------------------------------------------------------------------------------------------------

def _parcourir(seq, rappel):
    for i, n in enumerate(seq):
        rappel(seq, i)
        if isinstance(n, Groupe):
            _parcourir(n.enfants, rappel)
        elif n.genre == 'gabarit':
            for sous, _, _ in n.exprs:
                _parcourir(sous, rappel)


def _variables_passees(args):
    """Noms des variables d'un objet littéral { a, b: expr } ; None si on ne peut pas les lire."""
    if len(args) < 2:
        return set()
    if len(args[1]) != 1 or not ext.est_groupe(args[1][0], '{'):
        return None
    noms = set()
    for partie in ext.couper_virgules(args[1][0].enfants):
        if not partie:
            continue
        premier = partie[0]
        if ext.est_ponct(premier, '...'):
            return None
        if len(partie) == 1 and ext.est_nom(premier):
            noms.add(premier.valeur)
        elif len(partie) >= 3 and ext.est_ponct(partie[1], ':') and isinstance(premier, Jeton) \
                and premier.genre in ('nom', 'chaine'):
            noms.add(decoder(premier.valeur) if premier.genre == 'chaine' else premier.valeur)
        else:
            return None
    return noms


def _cles_html(texte, rel, ligne, res):
    for m in RE_DATA_I18N.finditer(texte):
        res.append(Utilisation(rel, ligne(m.start()) if callable(ligne) else ligne, cle=html.unescape(m.group(1)),
                               variables=set(), fonction='data-i18n'))
    for m in RE_DATA_I18N_ATTR.finditer(texte):
        for paire in html.unescape(m.group(1)).split(';'):
            if ':' in paire:
                res.append(Utilisation(rel, ligne(m.start()) if callable(ligne) else ligne,
                                       cle=paire.split(':', 1)[1].strip(), variables=set(),
                                       fonction='data-i18n-attr'))


RE_CLE_LITTERALE = re.compile(r'^[a-z][a-z0-9_-]*(\.[a-z0-9_-]+)+$')


def cles_utilisees(racine, fichiers, litterales=None):
    """Utilisation de clés dans les fichiers (JS : I18n.t, I18n.html, data-i18n dans les chaînes ; HTML : data-i18n).
    litterales (ensemble, facultatif) : reçoit chaque chaîne du JS qui a la forme d'une clé (« wiki.fait.fin ») ; une
    clé écrite ainsi puis passée à I18n.t par une variable compte comme employée (T262)."""
    res = []
    erreurs = []
    for rel in fichiers:
        chemin = Path(racine) / rel
        try:
            source = ext.lire_source(chemin)[0]
        except (OSError, UnicodeDecodeError) as erreur:
            erreurs.append((rel, str(erreur)))
            continue
        ligne = Lignes(source)
        if rel.endswith('.html'):
            _cles_html(source, rel, ligne, res)
            continue
        try:
            arbre = construire_arbre(source)
        except ErreurAnalyse as erreur:
            erreurs.append((rel, str(erreur)))
            continue

        def voir(seq, i):
            n = seq[i]
            if isinstance(n, Jeton) and n.genre in ('chaine', 'gabarit') and 'data-i18n' in n.valeur:
                _cles_html(n.valeur, rel, ligne(n.debut), res)
            if litterales is not None and isinstance(n, Jeton) and n.genre == 'chaine':
                valeur = decoder(n.valeur)
                if RE_CLE_LITTERALE.match(valeur):
                    litterales.add(valeur)
            if not (ext.est_nom(n, 'I18n') and i + 3 < len(seq) and ext.est_ponct(seq[i + 1], '.')
                    and ext.est_nom(seq[i + 2], 't', 'html') and ext.est_groupe(seq[i + 3], '(')):
                return
            args = ext.couper_virgules(seq[i + 3].enfants)
            premier = args[0]
            utilisation = Utilisation(rel, ligne(n.debut), variables=_variables_passees(args),
                                      fonction=seq[i + 2].valeur)
            if len(premier) == 1 and isinstance(premier[0], Jeton) and premier[0].genre == 'chaine':
                utilisation.cle = decoder(premier[0].valeur)
            elif premier and isinstance(premier[0], Jeton) and premier[0].genre == 'chaine':
                utilisation.prefixe = decoder(premier[0].valeur)        # 'valeurs.' + table + …
            elif premier and isinstance(premier[0], Jeton) and premier[0].genre == 'gabarit':
                d, f = premier[0].morceaux[0]
                utilisation.prefixe = decoder(source[d:f])              # `valeurs.${table}.…`
            else:
                utilisation.prefixe = ''                                # clé entièrement calculée
            res.append(utilisation)
        _parcourir(arbre, voir)
    return res, erreurs


# ---------------------------------------------------------------------------------------------------------
# Contrôle
# ---------------------------------------------------------------------------------------------------------

class Controle:
    def __init__(self, racine=ext.RACINE_DEPOT, exceptions=None):
        self.racine = Path(racine)
        self.exceptions = exceptions
        self.signalements = []
        self.erreurs = []
        self.fichiers = []
        self.domaines = []

    def signaler(self, genre, fichier, ligne, message):
        self.signalements.append(Signalement(genre, fichier, ligne, message))

    def lancer(self, domaines=None):
        tous = ext.tous_les_fichiers(self.racine)
        if domaines:
            inconnus = [d for d in domaines if d not in ext.DOMAINES]
            if inconnus:
                raise ValueError('domaine inconnu : %s' % ', '.join(inconnus))
            choisis = {d: tous.get(d, []) for d in domaines}
        else:
            choisis = tous
        self.domaines = sorted(choisis)
        # serveur.py : contrôle en Python (T246, outils/textes_serveur.py), pour le domaine serveur ou tout le dépôt.
        serveur = (not domaines or textes_serveur.SECTION in domaines) \
            and (self.racine / textes_serveur.FICHIER).is_file()
        if serveur:
            self.domaines = sorted(set(self.domaines) | {textes_serveur.SECTION})
        self.fichiers = sorted({f for fichiers in choisis.values() for f in fichiers}
                               | ({textes_serveur.FICHIER} if serveur else set()))
        self.textes_en_dur(choisis)
        self.cles(choisis, tous)
        self.page_html()
        if serveur:
            self.signalements.extend(textes_serveur.controler(self.racine)[0])
        self.signalements.sort(key=lambda s: (s.genre, s.fichier, s.ligne or 0, s.message))
        return self.signalements

    # 1. textes visibles restés en dur ---------------------------------------------------------------
    def textes_en_dur(self, choisis):
        extracteur = ext.Extracteur(self.racine, self.exceptions)
        for domaine in sorted(choisis):
            if not choisis[domaine]:
                continue
            res = extracteur.extraire(ext.section_du_domaine(domaine), choisis[domaine], essai=True,
                                      dictionnaire=ext.dictionnaire_du_domaine(domaine))
            for rel, message in res.erreurs:
                self.erreurs.append((rel, message))
            for u in res.unites:
                self.signaler('dur', u.fichier, u.ligne, '« %s »' % u.texte)
            for rel, ligne, texte, raison in res.relectures:
                self.signaler('dur', rel, ligne, '« %s » (à relire : %s)' % (texte, raison))

    # 2. clés -----------------------------------------------------------------------------------
    def cles(self, choisis, tous):
        francais = Langue('fr', self.racine, DICTIONNAIRES)
        for cle, rel in francais.doublons:
            self.signaler('doublon', rel, None, 'clé définie deux fois : %s' % cle)
        tous_fichiers = sorted({f for fichiers in tous.values() for f in fichiers})
        litterales = set()
        utilisations, erreurs = cles_utilisees(self.racine, tous_fichiers, litterales)
        self.erreurs.extend(erreurs)
        retenus = set(self.fichiers)
        for u in utilisations:
            if u.fichier not in retenus or u.cle is None:
                continue
            if u.cle not in francais.entrees:
                self.signaler('manquante', u.fichier, u.ligne, 'clé absente du dictionnaire : %s' % u.cle)
                continue
            section, valeur, _ = francais.entrees[u.cle]
            if u.variables is None:
                continue
            attendues = variables_de(valeur)
            passees = set(u.variables)
            if isinstance(valeur, dict):
                if 'n' not in passees:
                    self.signaler('variables', u.fichier, u.ligne, '%s : pluriel sans la variable n' % u.cle)
                passees.discard('n')
                attendues.discard('n')
            if attendues != passees:
                self.signaler('variables', u.fichier, u.ligne, '%s : appel { %s }, valeur { %s }' % (
                    u.cle, ', '.join(sorted(passees)) or '—', ', '.join(sorted(attendues)) or '—'))
        # orphelines : clés des sections contrôlées qu'aucun fichier du dépôt n'emploie
        # une clé entièrement calculée (I18n.t(cle)) ne couvre plus tout le dictionnaire (T262) : seules comptent les
        # clés écrites en chaîne quelque part dans le code (litterales) et les préfixes littéraux (« valeurs. » + x)
        employees = {u.cle for u in utilisations if u.cle is not None} | litterales
        prefixes = {u.prefixe for u in utilisations if u.prefixe}
        sections = {ext.section_du_domaine(d) for d in choisis} if self.domaines != sorted(tous) else None
        for cle, (section, valeur, rel) in sorted(francais.entrees.items()):
            if sections is not None and section not in sections:
                continue
            # variable au nom qui ne dit rien au traducteur ({v1}, {pourcent2}, {MINIMUM}) : à renommer (T237)
            generiques = sorted(nom for nom in variables_de(valeur) if nom != 'n' and ext.RE_NOM_GENERIQUE.match(nom))
            if generiques:
                self.signaler('nommer', rel, None, '%s : {%s}' % (cle, '}, {'.join(generiques)))
            if cle in employees or any(cle.startswith(p) for p in prefixes):
                continue
            self.signaler('orpheline', rel, None, 'clé jamais employée : %s' % cle)

    # 3. index.html : texte laissé sous data-i18n = valeur du dictionnaire -------------------------------
    def page_html(self):
        francais = Langue('fr', self.racine, DICTIONNAIRES)
        for rel in self.fichiers:
            if not rel.endswith('.html'):
                continue
            source = ext.lire_source(self.racine / rel)[0]
            elements = ext.decouper_html(source)
            if elements is None:
                self.erreurs.append((rel, 'HTML illisible'))
                continue
            ligne = Lignes(source)
            for k, el in enumerate(elements):
                if el.genre != 'balise' or el.fermante:
                    continue
                attrs = {nom: source[va:vb] for nom, va, vb in el.attrs if nom and va is not None}
                cle = attrs.get('data-i18n')
                if cle and cle in francais.entrees:
                    suivant = elements[k + 1] if k + 1 < len(elements) else None
                    texte = html.unescape(source[suivant.a:suivant.b]) if suivant is not None and \
                        suivant.genre == 'texte' else ''
                    self.comparer(rel, ligne(el.a), cle, texte, francais.entrees[cle][1])
                for paire in attrs.get('data-i18n-attr', '').split(';'):
                    if ':' not in paire:
                        continue
                    nom, cle_attr = (x.strip() for x in paire.split(':', 1))
                    if cle_attr in francais.entrees and nom in attrs:
                        self.comparer(rel, ligne(el.a), cle_attr, html.unescape(attrs[nom]),
                                      francais.entrees[cle_attr][1])

    def comparer(self, rel, ligne, cle, texte, valeur):
        if isinstance(valeur, dict) or decoder(valeur) != texte:
            self.signaler('page', rel, ligne, '%s : la page dit « %s », le dictionnaire « %s »' % (
                cle, ext.court(texte, 60), ext.court(decoder(valeur) if isinstance(valeur, str) else '…', 60)))


TITRES = {
    'dur': 'Textes visibles restés en dur',
    'manquante': 'Clés employées mais absentes du dictionnaire',
    'orpheline': 'Clés du dictionnaire jamais employées',
    'variables': 'Variables {…} différentes entre un appel et sa valeur',
    'doublon': 'Clés définies deux fois',
    'page': 'Texte de la page différent de sa valeur (data-i18n)',
    'nommer': 'Variables au nom générique dans le dictionnaire (à renommer)',
    'appel': 'Appels de traduisible mal écrits (serveur.py)',
    'differente': 'Valeur du dictionnaire différente du français de serveur.py',
}


def rapport(controle):
    lignes = ['Contrôle des textes — domaines : %s (%d fichiers)' % (', '.join(controle.domaines) or 'aucun',
                                                                     len(controle.fichiers))]
    par_genre = {}
    for s in controle.signalements:
        par_genre.setdefault(s.genre, []).append(s)
    for genre in ('dur', 'manquante', 'orpheline', 'variables', 'nommer', 'doublon', 'page', 'appel', 'differente'):
        liste = par_genre.get(genre, [])
        lignes.append('%s : %d' % (TITRES[genre], len(liste)))
        for s in liste:
            lieu = s.fichier + (':%d' % s.ligne if s.ligne else '')
            lignes.append('  %s  %s' % (lieu, s.message))
    for rel, message in controle.erreurs:
        lignes.append('ERREUR %s : %s' % (rel, message))
    if controle.signalements:
        lignes.append('Résultat : %d point(s) à reprendre.' % len(controle.signalements))
    else:
        lignes.append('Résultat : rien à signaler.')
    return '\n'.join(lignes) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description='Contrôle des textes : en dur, clés manquantes ou orphelines.')
    parser.add_argument('--domaine', action='append', help='limite aux fichiers de ce domaine (répétable)')
    parser.add_argument('--racine', default=str(ext.RACINE_DEPOT))
    parser.add_argument('--exceptions')
    args = parser.parse_args(argv)
    controle = Controle(args.racine, args.exceptions)
    try:
        controle.lancer(args.domaine)
    except ValueError as erreur:
        parser.error(str(erreur))
    sys.stdout.write(rapport(controle))
    if controle.erreurs:
        return 2
    return 1 if controle.signalements else 0


if __name__ == '__main__':
    sys.exit(main())
