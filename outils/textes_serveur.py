# -*- coding: utf-8 -*-
"""Textes de serveur.py (chantier i18n, T246 ; D157) : extraction et contrôle, en Python (module ast).

Bibliothèque standard seulement. Depuis la racine du dépôt :
  py -X utf8 outils/textes_serveur.py            # contrôle (code retour 0 : rien à signaler, 1 sinon)
  py -X utf8 outils/textes_serveur.py --ecrire   # extraction : complète la section serveur de js/i18n/fr.js
Le contrôle passe aussi par « py -X utf8 outils/controler_textes.py --domaine serveur » (et sans --domaine).

D157 : un message que le navigateur peut afficher s'écrit traduisible('<code>', '<français>', nom=valeur…) dans
serveur.py ; le navigateur affiche la clé serveur.<code> de js/i18n/fr.js, le français reçu sinon.

Ce qui est contrôlé :
1. chaque appel traduisible(…) : code écrit en clair (« groupe.element », minuscules) ; français écrit en clair (ou
   pluriel {'one': …, 'other': …}) ; variables {…} du français = noms passés (n pour un pluriel) ; un même code a
   partout le même français ;
2. js/i18n/fr.js, section serveur : chaque code y a sa clé serveur.<code>, de même valeur (au caractère près, pluriel
   compris) ; aucune clé de la section n'est orpheline ;
3. textes restés en dur : toute chaîne de serveur.py qui ressemble à du texte (deux mots au moins : un mot seul
   n'est pas vu) est soit le français d'un traduisible(…), soit hors codes par une règle ci-dessous ; sinon elle est
   signalée ;
4. le nom « traduisible » n'est la variable locale d'aucune fonction (elle cacherait la fonction : erreur à
   l'exécution, sur un chemin d'erreur rarement essayé).

Règle des textes hors codes (D157, D156, D155) : docstrings ; arguments des appels techniques de console
(APPELS_CONSOLE : ligne de commande, journal des requêtes) ; fonctions entières qui écrivent un lanceur, un script, les
données ou l'aide de la ligne de commande (FONCTIONS_HORS_CODES) ; constantes de même nature (CONSTANTES_HORS_CODES) ;
commandes à taper (RE_COMMANDE). Chaque entrée dit pourquoi. La console du serveur et son journal, eux, sont dans la
langue de l'installation (T297) : leurs textes s'écrivent traduisible(…) comme les messages du navigateur (afficher
écrit la clé anglaise de js/i18n/en.js pour une installation en anglais).
"""
import argparse
import ast
import re
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
if str(ICI) not in sys.path:
    sys.path.insert(0, str(ICI))
import extraire_textes as ext  # noqa: E402
from jslex import decoder  # noqa: E402

FICHIER = 'serveur.py'
SECTION = 'serveur'
FONCTION = 'traduisible'
RE_CODE = re.compile(r'^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$')
RE_VARIABLE = re.compile(r'\{([A-Za-z_][A-Za-z0-9_]*)\}')          # MOTIF_VARIABLE de js/i18n.js
# « Ressemble à du texte » : deux mots au moins (le second peut être un guillemet français).
RE_TEXTE = re.compile(r"[A-Za-zÀ-ÿœŒ]{2,}[’']?\s+[A-Za-zÀ-ÿœŒ«»]")

# Appels techniques dont les arguments vont à la console (D157). Depuis T297, afficher, noter_au_journal_serveur et
# SystemExit n'y sont plus : la console est dans la langue de l'installation, ses textes sont des traduisible(…).
APPELS_CONSOLE = {
    'print': 'console (afficher seulement, qui écrit un texte déjà traduit)',
    'log_message': 'journal des requêtes',
    'ArgumentParser': 'aide de la ligne de commande',
    'add_argument': 'aide de la ligne de commande',
    'error': 'erreur de la ligne de commande (argparse)',
}
# Fonctions dont tous les textes sont hors codes.
FONCTIONS_HORS_CODES = {
    'texte_aide_configuration': 'console : « serveur.py --aide »',
    'lire_arguments': 'aide de la ligne de commande',
    'relancer_prevo': 'programme Python de la relance (aucun texte affiché)',
    'script_installer_windows': 'lanceur (D157) : script PowerShell écrit pour l\'administrateur',
    'script_retirer_windows': 'lanceur (D157) : script PowerShell',
    'script_session_windows': 'lanceur (D157) : script PowerShell',
    'commande_powershell': 'lanceur (D157) : commande PowerShell',
    'unite_systemd': 'lanceur (D157) : unité systemd',
    'commandes_systemd': 'lanceur (D157) : commandes à taper',
    'plist_launchd': 'lanceur (D157) : fichier launchd',
    'lire_fichier_de_donnees': 'pertes d\'un fichier : console (signaler_fichiers_laisses) ; les deux pertes '
                               'montrées au navigateur sont des constantes traduisibles',
    'libelle_appareil': 'donnée (D156) : libellé de l\'appareil écrit dans appareils.json',
    'ligne_de_journal_de_format': 'donnée (D156) : ligne de journal.csv',
    'migrer_tables': 'erreur de programmation (ValueError, TypeError), jamais montrée',
    'passer_les_fichiers_au_format_courant': 'donnée (D156) : lignes de journal.csv du passage de format (sa console '
                                             'est en traduisible)',
}
# Constantes du module dont tous les textes sont hors codes.
CONSTANTES_HORS_CODES = {
    'CLES_CONFIGURATION': 'console : aide des clés de configuration (« serveur.py --aide »)',
    'AIDE_CONFIGURATION': 'donnée : commentaire « _aide » écrit dans prevo.config.json',
    'POSTE_DU_SERVEUR': 'donnée (D156) : colonne « poste » de journal.csv',
    'SECTION_SERVEUR_JS': 'marqueur relu par le code (section serveur de js/i18n/en.js, T297), jamais affiché',
    'PHOTOS_DE_DEMANDES': 'marqueur relu par le code (règle d\'un rôle), jamais affiché',
    'DOCUMENTS_DU_DEMANDEUR': 'marqueur relu par le code (règle d\'un rôle), jamais affiché',
    'CHEMINS_TAILSCALE': 'technique : chemins de l\'exécutable',
    'DEFAUTS_DES_CHAMPS': 'valeurs stockées des listes (D155)',
    'ETAPES_FORMAT': 'registre des formats (même texte que js/formats.js), jamais montré par le serveur',
    'COMMENTAIRE_LEVEE_REPRISE': 'donnée (D156) : commentaire_levee de reserves_controle.csv écrit par la reprise des '
                                 'observations (D183), même texte que js/formats.js',
    'POLITIQUE_CONTENU': 'technique : en-tête Content-Security-Policy',
    'POLITIQUE_PORTE': 'technique : en-tête Content-Security-Policy',
}
# Commandes à taper ou à lancer (technique : jamais traduites).
RE_COMMANDE = re.compile(r'^(sudo|launchctl|systemctl|tailscale|schtasks|netsh|powercfg) ')


class Signalement:
    __slots__ = ('genre', 'fichier', 'ligne', 'message')

    def __init__(self, genre, fichier, ligne, message):
        self.genre, self.fichier, self.ligne, self.message = genre, fichier, ligne, message

    def __repr__(self):
        return 'Signalement(%s, %s:%s, %s)' % (self.genre, self.fichier, self.ligne, self.message)


class Appel:
    """Un appel traduisible(code, modele, **valeurs) : modele est une chaîne ou {catégorie: chaîne} ; variables : noms
    passés (None si **valeurs)."""
    __slots__ = ('ligne', 'code', 'modele', 'variables')

    def __init__(self, ligne, code, modele, variables):
        self.ligne, self.code, self.modele, self.variables = ligne, code, modele, variables


def variables_du_modele(modele):
    formes = modele.values() if isinstance(modele, dict) else [modele]
    return {nom for forme in formes for nom in RE_VARIABLE.findall(forme)}


def _chaine(noeud):
    return noeud.value if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str) else None


def _modele(noeud):
    """Chaîne, ou pluriel {'one': …, 'other': …} écrit en clair ; None sinon."""
    texte = _chaine(noeud)
    if texte is not None:
        return texte
    if isinstance(noeud, ast.Dict) and noeud.keys and all(_chaine(k) is not None for k in noeud.keys) \
            and all(_chaine(v) is not None for v in noeud.values):
        return {_chaine(k): _chaine(v) for k, v in zip(noeud.keys, noeud.values)}
    return None


class Analyse:
    """Lecture de serveur.py : appels de traduisible, textes en dur, variables locales qui cachent la fonction."""

    def __init__(self, source, fichier=FICHIER):
        self.fichier = fichier
        self.appels = []
        self.signalements = []
        self.hors_codes = 0
        arbre = ast.parse(source)
        self.parents = {}
        for noeud in ast.walk(arbre):
            for enfant in ast.iter_child_nodes(noeud):
                self.parents[enfant] = noeud
        self.docstrings = set()
        for noeud in ast.walk(arbre):
            if isinstance(noeud, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and noeud.body \
                    and isinstance(noeud.body[0], ast.Expr) and _chaine(noeud.body[0].value) is not None:
                self.docstrings.add(noeud.body[0].value)
        self.modeles = set()
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name) and noeud.func.id == FONCTION:
                self.lire_appel(noeud)
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
                self.voir_chaine(noeud)
            elif isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                self.voir_locales(noeud)

    def signaler(self, genre, ligne, message):
        self.signalements.append(Signalement(genre, self.fichier, ligne, message))

    def lire_appel(self, noeud):
        if len(noeud.args) != 2:
            self.signaler('appel', noeud.lineno, '%s(…) attend deux arguments : le code et le français' % FONCTION)
            return
        code, modele = _chaine(noeud.args[0]), _modele(noeud.args[1])
        for sous in ast.walk(noeud.args[1]):        # le français d'un appel n'est jamais un texte « en dur »
            self.modeles.add(sous)
        if code is None:
            self.signaler('appel', noeud.lineno, 'code calculé : il doit être écrit en clair')
            return
        if not RE_CODE.match(code):
            self.signaler('appel', noeud.lineno, 'code mal formé : %s (groupe.element, minuscules)' % code)
        if modele is None:
            self.signaler('appel', noeud.lineno, '%s : français calculé, il doit être écrit en clair' % code)
            return
        variables = None if any(k.arg is None for k in noeud.keywords) else {k.arg for k in noeud.keywords}
        self.appels.append(Appel(noeud.lineno, code, modele, variables))

    # « dur » : chaîne de texte hors d'un traduisible et hors des règles d'exclusion
    def exclusion(self, noeud):
        if noeud in self.docstrings:
            return 'docstring'
        courant = noeud
        while courant in self.parents:
            courant = self.parents[courant]
            if isinstance(courant, ast.Call):
                fonction = courant.func
                nom = fonction.id if isinstance(fonction, ast.Name) else getattr(fonction, 'attr', None)
                if nom in APPELS_CONSOLE:
                    return APPELS_CONSOLE[nom]
            elif isinstance(courant, (ast.FunctionDef, ast.AsyncFunctionDef)) and courant.name in FONCTIONS_HORS_CODES:
                return FONCTIONS_HORS_CODES[courant.name]
            elif isinstance(courant, (ast.Assign, ast.AnnAssign)) and courant in self.parents \
                    and isinstance(self.parents[courant], ast.Module):
                cibles = courant.targets if isinstance(courant, ast.Assign) else [courant.target]
                for cible in cibles:
                    if isinstance(cible, ast.Name) and cible.id in CONSTANTES_HORS_CODES:
                        return CONSTANTES_HORS_CODES[cible.id]
        return None

    def voir_chaine(self, noeud):
        if noeud in self.modeles or not RE_TEXTE.search(noeud.value):
            return
        if RE_COMMANDE.match(noeud.value):
            self.hors_codes += 1
            return
        if self.exclusion(noeud) is not None:
            self.hors_codes += 1
            return
        self.signaler('dur', noeud.lineno, '« %s »' % ext.court(noeud.value.replace('\n', '\\n'), 90))

    def voir_locales(self, noeud):
        arguments = noeud.args
        noms = {a.arg for a in arguments.args + arguments.kwonlyargs + arguments.posonlyargs}
        for sous in ast.walk(noeud):
            if isinstance(sous, ast.Name) and isinstance(sous.ctx, ast.Store):
                noms.add(sous.id)
        if FONCTION in noms:
            self.signaler('appel', noeud.lineno, 'variable locale « %s » : elle cache la fonction' % FONCTION)


def codes(appels):
    """{code: français} : le français du premier appel de chaque code (le contrôle signale un code à deux français)."""
    par_code = {}
    for appel in appels:
        par_code.setdefault(appel.code, appel.modele)
    return par_code


def valeur_js(modele):
    """Valeur d'une entrée de fr.js (brute, entre apostrophes) : chaîne ou {catégorie: chaîne}."""
    if isinstance(modele, dict):
        return {c: ext.echapper_texte(modele[c]) for c in ext.CATEGORIES_PLURIEL if c in modele}
    return ext.echapper_texte(modele)


def valeur_lue(brute):
    return {c: decoder(v) for c, v in brute.items()} if isinstance(brute, dict) else decoder(brute)


def entrees_de_la_section(racine):
    for section, (_, entrees) in ext.lire_dictionnaire(Path(racine) / ext.DICTIONNAIRE).items():
        if section == SECTION:
            return entrees
    return None


def controler(racine=ext.RACINE_DEPOT, fichier=FICHIER):
    """(signalements, analyse) du contrôle de serveur.py contre la section serveur de fr.js."""
    racine = Path(racine)
    analyse = Analyse((racine / fichier).read_text(encoding='utf-8'), fichier)
    signalements = list(analyse.signalements)

    def signaler(genre, ligne, message, ou=fichier):
        signalements.append(Signalement(genre, ou, ligne, message))

    par_code = codes(analyse.appels)
    deja = set()
    for appel in analyse.appels:
        if par_code[appel.code] != appel.modele and appel.code not in deja:
            deja.add(appel.code)
            signaler('doublon', appel.ligne, '%s : deux français différents pour un même code' % appel.code)
        attendues = variables_du_modele(appel.modele)
        if isinstance(appel.modele, dict):
            if set(appel.modele) - set(ext.CATEGORIES_PLURIEL) or 'other' not in appel.modele:
                signaler('appel', appel.ligne, '%s : pluriel sans forme « other » ou de catégorie inconnue'
                         % appel.code)
            attendues.add('n')          # le nombre qui choisit la forme, écrit ou non dans le français
        if appel.variables is not None and appel.variables != attendues:
            signaler('variables', appel.ligne, '%s : appel { %s }, français { %s }' % (
                appel.code, ', '.join(sorted(appel.variables)) or '—', ', '.join(sorted(attendues)) or '—'))
        generiques = sorted(nom for nom in attendues if nom != 'n' and ext.RE_NOM_GENERIQUE.match(nom))
        if generiques:
            signaler('nommer', appel.ligne, '%s : {%s}' % (appel.code, '}, {'.join(generiques)))
    entrees = entrees_de_la_section(racine)
    dictionnaire = ext.DICTIONNAIRE
    if entrees is None:
        signaler('manquante', None, 'section « %s » absente du dictionnaire' % SECTION, dictionnaire)
        entrees = {}
    for code, modele in sorted(par_code.items()):
        cle = '%s.%s' % (SECTION, code)
        if cle not in entrees:
            signaler('manquante', None, 'clé absente du dictionnaire : %s' % cle)
        elif valeur_lue(entrees[cle]) != modele:
            signaler('differente', None, '%s : le dictionnaire dit « %s », serveur.py « %s »' % (
                cle, ext.court(str(valeur_lue(entrees[cle])), 60), ext.court(str(modele), 60)))
    for cle in sorted(entrees):
        if not cle.startswith(SECTION + '.') or cle[len(SECTION) + 1:] not in par_code:
            signaler('orpheline', None, 'clé jamais employée par %s : %s' % (fichier, cle), dictionnaire)
    signalements.sort(key=lambda s: (s.genre, s.fichier, s.ligne or 0, s.message))
    return signalements, analyse


def extraire(racine=ext.RACINE_DEPOT, fichier=FICHIER):
    """Complète la section serveur de fr.js avec les codes de serveur.py (valeur = le français) ; rend le nombre de
    clés écrites. Les clés orphelines restent (le contrôle les signale)."""
    racine = Path(racine)
    analyse = Analyse((racine / fichier).read_text(encoding='utf-8'), fichier)
    par_code = codes(analyse.appels)
    chemin = racine / ext.DICTIONNAIRE
    texte = chemin.read_text(encoding='utf-8')
    ajouts = {'%s.%s' % (SECTION, code): valeur_js(modele) for code, modele in par_code.items()}
    chemin.write_bytes(ext.completer_dictionnaire(texte, {SECTION: ajouts}).encode('utf-8'))
    return len(ajouts)


TITRES = {
    'dur': 'Textes restés en dur (ni traduisible, ni hors codes par règle)',
    'appel': 'Appels de traduisible mal écrits',
    'variables': 'Variables {…} différentes entre un appel et son français',
    'nommer': 'Variables au nom générique (à renommer)',
    'doublon': 'Codes qui ont deux français',
    'manquante': 'Codes absents du dictionnaire',
    'differente': 'Valeur du dictionnaire différente du français de serveur.py',
    'orpheline': 'Clés de la section serveur jamais employées',
}


def rapport(signalements, analyse):
    lignes = ['Textes de %s — %d appels de %s (%d codes), %d textes hors codes par règle'
              % (analyse.fichier, len(analyse.appels), FONCTION, len(codes(analyse.appels)), analyse.hors_codes)]
    for genre, titre in TITRES.items():
        liste = [s for s in signalements if s.genre == genre]
        lignes.append('%s : %d' % (titre, len(liste)))
        for s in liste:
            lignes.append('  %s%s  %s' % (s.fichier, ':%d' % s.ligne if s.ligne else '', s.message))
    lignes.append('Résultat : %s.' % ('%d point(s) à reprendre' % len(signalements) if signalements
                                      else 'rien à signaler'))
    return '\n'.join(lignes) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description='Textes de serveur.py (D157) : contrôle, ou extraction (--ecrire).')
    parser.add_argument('--racine', default=str(ext.RACINE_DEPOT))
    parser.add_argument('--ecrire', action='store_true', help='complète la section serveur de js/i18n/fr.js')
    args = parser.parse_args(argv)
    if args.ecrire:
        sys.stdout.write('%d clés écrites dans la section %s de %s.\n' % (extraire(args.racine), SECTION,
                                                                          ext.DICTIONNAIRE))
    signalements, analyse = controler(args.racine)
    sys.stdout.write(rapport(signalements, analyse))
    return 1 if signalements else 0


if __name__ == '__main__':
    sys.exit(main())
