"""Messages de serveur.py en codes traduits par le navigateur (T246, D157) et leur outil Python
(outils/textes_serveur.py).

Sans navigateur, bibliothèque standard seulement. Petits fichiers d'essai dans un dossier temporaire ; le vrai
serveur.py est lu comme module (rien n'est lancé), sauf la dernière classe (un serveur sur un dossier vide). Depuis la
racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_serveur_textes.py" -v
"""
import ast
import importlib.util
import io
import json
import shutil
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stdout
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'outils'))
sys.path.insert(0, str(RACINE / 'tests'))
import controler_textes as ctl  # noqa: E402
import textes_serveur as ts  # noqa: E402
from commun import ServeurPrevo  # noqa: E402

_specification = importlib.util.spec_from_file_location('serveur_prevo_textes', RACINE / 'serveur.py')
serveur = importlib.util.module_from_spec(_specification)
_specification.loader.exec_module(serveur)

# serveur.py d'essai : chaque cas que l'outil doit voir (ou laisser passer, par règle).
SERVEUR_ESSAI = '''"""Docstring : jamais signalée, même avec des mots."""


class ErreurHttp(Exception):
    pass


def traduisible(code, modele, **valeurs):
    return modele


MESSAGE_PROPRE = traduisible('essai.propre', 'Un message propre.')


def afficher(texte):
    print(texte)


def route(nom, n):
    afficher('Console du démarrage, jamais signalée.')
    if nom == 'a':
        raise ErreurHttp(400, 'Texte resté en dur ici.')
    if nom == 'b':
        raise ErreurHttp(400, traduisible('essai.variables', 'Table {table} inconnue.', nom=nom))
    if nom == 'c':
        raise ErreurHttp(400, traduisible('essai.pluriel', {'one': '{n} essai.', 'other': '{n} essais.'}, n=n))
    if nom == 'd':
        raise ErreurHttp(400, traduisible('essai.propre', 'Un autre français.'))
    if nom == 'e':
        raise ErreurHttp(400, traduisible('essai.absent', 'Code absent du dictionnaire.'))
    return traduisible(nom, 'Code calculé.')


def libelle_appareil(agent):
    return 'Téléphone ou tablette Android'


def cache(traduisible):
    return traduisible
'''

DICTIONNAIRE_ESSAI = """'use strict';
// ==== section serveur ====
I18n.ajouter('fr', {
  'serveur.essai.orpheline': 'Plus personne ne m\\'emploie.',
  'serveur.essai.pluriel': { one: '{n} essai.', other: '{n} essais !' },
  'serveur.essai.propre': 'Un message propre.',
  'serveur.essai.variables': 'Table {table} inconnue.',
});
// ==== fin serveur ====
"""


class CasDepot(unittest.TestCase):
    """Dossier temporaire avec serveur.py et js/i18n/fr.js d'essai."""

    def setUp(self):
        self.racine = Path(tempfile.mkdtemp(prefix='prevo-textes-serveur-'))
        self.addCleanup(shutil.rmtree, self.racine, ignore_errors=True)
        (self.racine / 'js' / 'i18n').mkdir(parents=True)
        (self.racine / 'serveur.py').write_text(SERVEUR_ESSAI, encoding='utf-8')
        (self.racine / 'js' / 'i18n' / 'fr.js').write_text(DICTIONNAIRE_ESSAI, encoding='utf-8')

    def signalements(self):
        return ts.controler(self.racine)[0]

    def messages(self, genre):
        return [s.message for s in self.signalements() if s.genre == genre]


class TestControle(CasDepot):

    def test_texte_en_dur_signale_hors_des_regles(self):
        dur = self.messages('dur')
        self.assertEqual(dur, ['« Texte resté en dur ici. »'])          # ni la console, ni la docstring, ni D156

    def test_variables_differentes_entre_l_appel_et_le_francais(self):
        self.assertEqual(self.messages('variables'), ['essai.variables : appel { nom }, français { table }'])

    def test_un_code_deux_francais(self):
        self.assertEqual(self.messages('doublon'), ['essai.propre : deux français différents pour un même code'])

    def test_code_calcule_et_variable_locale_qui_cache_la_fonction(self):
        appels = self.messages('appel')
        self.assertIn('code calculé : il doit être écrit en clair', appels)
        self.assertIn('variable locale « traduisible » : elle cache la fonction', appels)

    def test_dictionnaire_manquante_differente_orpheline(self):
        self.assertEqual(self.messages('manquante'), ['clé absente du dictionnaire : serveur.essai.absent'])
        differentes = self.messages('differente')
        self.assertEqual(len(differentes), 1)
        self.assertTrue(differentes[0].startswith('serveur.essai.pluriel : '), differentes)
        self.assertEqual(self.messages('orpheline'), ['clé jamais employée par serveur.py : serveur.essai.orpheline'])

    def test_extraction_complete_la_section_puis_plus_rien_ne_manque(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(ts.main(['--racine', str(self.racine), '--ecrire']), 1)   # le reste est à reprendre
        self.assertEqual(self.messages('manquante'), [])
        francais = ts.entrees_de_la_section(self.racine)
        self.assertEqual(francais['serveur.essai.absent'], 'Code absent du dictionnaire.')
        self.assertEqual(francais['serveur.essai.pluriel'], {'one': '{n} essai.', 'other': '{n} essais.'})
        self.assertEqual(self.messages('differente'), [])
        self.assertIn('serveur.essai.orpheline', francais)                 # l'orpheline reste : signalée

    def test_controler_textes_domaine_serveur_passe_par_l_outil_python(self):
        controle = ctl.Controle(self.racine)
        controle.lancer(['serveur'])
        self.assertIn('serveur.py', controle.fichiers)
        genres = {s.genre for s in controle.signalements}
        self.assertTrue({'dur', 'variables', 'doublon', 'manquante', 'differente', 'orpheline', 'appel'} <= genres,
                        genres)
        rapport = ctl.rapport(controle)
        self.assertIn('domaines : serveur (1 fichiers)', rapport)
        self.assertIn('Texte resté en dur ici.', rapport)


class TestVraiDepot(unittest.TestCase):

    def test_serveur_py_et_fr_js_rien_a_signaler(self):
        signalements, analyse = ts.controler(RACINE)
        self.assertEqual(signalements, [], ts.rapport(signalements, analyse))
        self.assertGreater(len(analyse.appels), 200)

    def test_chaque_erreur_http_porte_un_message_traduisible(self):
        """Le message de chaque ErreurHttp(statut, message) est un appel de traduisible, un nom (constante ou
        variable) ou traduisible_de(erreur) : jamais une chaîne, un % ou un + (le contrôle « dur » les verrait
        aussi)."""
        arbre = ast.parse((RACINE / 'serveur.py').read_text(encoding='utf-8'))
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name) and noeud.func.id == 'ErreurHttp' \
                    and len(noeud.args) >= 2:
                message = noeud.args[1]
                with self.subTest(ligne=noeud.lineno):
                    self.assertNotIsInstance(message, (ast.Constant, ast.JoinedStr, ast.BinOp))


class TestTraduisible(unittest.TestCase):

    def test_francais_identique_code_et_seules_les_valeurs_ecrites(self):
        message = serveur.traduisible('csv.table_inconnue', 'Table inconnue : {table}.', table='achats',
                                      chemin='C:/secret')
        self.assertEqual(message, 'Table inconnue : achats.')
        self.assertIsInstance(message, str)
        self.assertEqual((message.code, message.valeurs), ('csv.table_inconnue', {'table': 'achats'}))

    def test_pluriel_francais_et_nombre_garde(self):
        modele = {'one': 'Colonne absente : {colonnes}.', 'other': 'Colonnes absentes : {colonnes}.'}
        un = serveur.traduisible('x.y', modele, n=1, colonnes='a')
        deux = serveur.traduisible('x.y', modele, n=2, colonnes='a, b')
        self.assertEqual((un, deux), ('Colonne absente : a.', 'Colonnes absentes : a, b.'))
        self.assertEqual(deux.valeurs, {'n': 2, 'colonnes': 'a, b'})        # n part, même s'il n'est pas écrit
        self.assertEqual(serveur.forme_du_pluriel_fr(0), 'one')
        self.assertEqual(serveur.forme_du_pluriel_fr(1.5), 'one')

    def test_constantes_et_fonctions_gardent_le_texte_attendu_par_les_tests(self):
        self.assertEqual(serveur.MESSAGE_ACTUEL_FAUX, 'Mot de passe actuel incorrect.')
        self.assertEqual(serveur.message_fichier_verrouille('C:/d/achats.csv'),
                         'Le fichier « achats.csv » est ouvert dans Excel ou un autre logiciel : fermez-le, puis '
                         'réessayez.')
        self.assertEqual(serveur.message_fichier_verrouille(None).code, 'fichier.verrouille_sans_nom')

    def test_reponse_json_code_valeurs_message_imbrique_et_liste(self):
        raison = serveur.traduisible('demandes.numero_pris', 'le numéro {numero} est déjà pris.', numero='DI-7')
        erreur = serveur.refus_ajout_seulement(raison)
        corps = serveur.avec_codes({'erreur': erreur.message, 'table': 'demandes'})
        self.assertEqual(corps['erreur'], erreur.message)
        self.assertEqual(corps['erreur_code'], 'acces.ajout_seulement')
        self.assertEqual(corps['erreur_valeurs'], {'raison': {'code': 'demandes.numero_pris',
                                                              'texte': 'le numéro DI-7 est déjà pris.',
                                                              'valeurs': {'numero': 'DI-7'}}})
        liste = serveur.traduisible('demandes.non_supprimable', 'une demande ne se supprime pas ({demandes}).',
                                    demandes=['DI-1', serveur.traduisible('demandes.sans_numero', 'sans numéro')])
        self.assertEqual(liste, 'une demande ne se supprime pas (DI-1, sans numéro).')
        self.assertEqual(serveur.avec_codes({'erreur': liste})['erreur_valeurs'],
                         {'demandes': ['DI-1', {'code': 'demandes.sans_numero', 'texte': 'sans numéro'}]})
        rappels = serveur.avec_codes({'rappels': list(serveur.RAPPELS_TAILSCALE)})
        self.assertEqual([objet['code'] for objet in rappels['rappels_codes']],
                         ['tailscale.rappel_expiration', 'tailscale.rappel_veille'])
        self.assertEqual(serveur.avec_codes({'erreur': 'brut', 'n': 1}), {'erreur': 'brut', 'n': 1})

    def test_point_final_retire_et_message_d_une_exception(self):
        try:
            raise serveur.ErreurTailscale(serveur.traduisible('tailscale.lancement_impossible',
                                                              'tailscale n\'a pas pu être lancé ({erreur}).',
                                                              erreur='x'))
        except serveur.ErreurTailscale as erreur:
            message = serveur.traduisible_de(erreur)
        sans_point = serveur.forme_sans_point(message)
        self.assertEqual(sans_point, 'tailscale n\'a pas pu être lancé (x)')
        self.assertEqual(serveur.avec_codes({'raison': sans_point})['raison_sans_point'], True)
        self.assertEqual(serveur.traduisible_de(ValueError('brut')), 'brut')

    def test_etat_de_la_copie_externe_relu_avec_son_code(self):
        relu = serveur.traduisible_relu('Dossier absent.', 'copie.dossier_introuvable', {'nom': 'Cle'})
        self.assertEqual(serveur.avec_codes({'erreur': relu}),
                         {'erreur': 'Dossier absent.', 'erreur_code': 'copie.dossier_introuvable',
                          'erreur_valeurs': {'nom': 'Cle'}})
        self.assertEqual(serveur.traduisible_relu('Ancien état.', None, None), 'Ancien état.')


class TestReponseDuServeur(unittest.TestCase):

    def test_erreur_http_porte_son_code_et_ses_valeurs(self):
        with ServeurPrevo(source=None) as prevo:
            try:
                urllib.request.urlopen(prevo.url + '/api/csv/inconnue', timeout=10)
                self.fail('404 attendu')
            except urllib.error.HTTPError as erreur:
                corps = json.loads(erreur.read().decode('utf-8'))
                statut = erreur.code
        self.assertEqual(statut, 404)
        self.assertEqual(corps, {'erreur': 'Table inconnue : inconnue.', 'erreur_code': 'csv.table_inconnue',
                                 'erreur_valeurs': {'table': 'inconnue'}})


if __name__ == '__main__':
    unittest.main()
