"""Messages de serveur.py en codes traduits par le navigateur (T246, D157) et leur outil Python
(outils/textes_serveur.py).

Sans navigateur, bibliothèque standard seulement. Petits fichiers d'essai dans un dossier temporaire ; le vrai
serveur.py est lu comme module (rien n'est lancé), sauf TestReponseDuServeur (un serveur sur un dossier vide) et la
console (T297 : un serveur sur une copie de la démo en anglais, puis en français). Console dans la langue de
l'installation (T297) : langue_defaut ramenée à fr ou en, sinon la langue du système (locale simulée) ; afficher
écrit la clé anglaise de js/i18n/en.js (valeurs traduites à leur tour, pluriel anglais), le français sans elle ;
chaque message de la console a son anglais. Depuis la racine du projet :
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
from unittest import mock

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / 'outils'))
sys.path.insert(0, str(RACINE / 'tests'))
import controler_textes as ctl  # noqa: E402
import textes_serveur as ts  # noqa: E402
from commun import DOSSIER_DEMO, ServeurPrevo  # noqa: E402

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
    log_message('Journal des requêtes, jamais signalé.')
    afficher(traduisible('essai.propre', 'Un message propre.'))
    if nom == 'z':
        afficher('Console restée en dur.')
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
        # Ni le journal des requêtes, ni la docstring, ni D156 ; la console, si (T297 : langue de l'installation).
        self.assertEqual(dur, ['« Console restée en dur. »', '« Texte resté en dur ici. »'])

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


# ---------------------------------------------------------------------------
# Console du serveur dans la langue de l'installation (T297)
# ---------------------------------------------------------------------------

class TestConsoleDansLaLangue(unittest.TestCase):

    def setUp(self):
        avant = dict(serveur.CONSOLE)
        self.addCleanup(serveur.CONSOLE.update, avant)
        self.dossier = Path(tempfile.mkdtemp(prefix='prevo-console-'))
        self.addCleanup(shutil.rmtree, self.dossier, ignore_errors=True)

    def config(self, langue=None):
        """Configuration sur un dossier dont parametres.csv a langue_defaut = langue (sans la ligne pour None)."""
        donnees = self.dossier / 'donnees'
        donnees.mkdir(exist_ok=True)
        lignes = 'cle;valeur\r\nversion_schema;3\r\n' + ('langue_defaut;%s\r\n' % langue if langue else '')
        (donnees / 'parametres.csv').write_bytes(('\ufeff' + lignes).encode('utf-8'))
        return serveur.Configuration(str(donnees), [])

    def ecrire(self, message, langue):
        """Ce que afficher écrit pour message, la console étant dans cette langue."""
        serveur.CONSOLE['langue'] = langue
        sortie = io.StringIO()
        with redirect_stdout(sortie):
            serveur.afficher(message)
        return sortie.getvalue().rstrip('\n')

    def test_langue_de_l_installation_ramenee_a_fr_ou_en(self):
        with mock.patch.object(serveur.locale, 'getlocale', return_value=('fr_FR', 'cp1252')):
            self.assertEqual(serveur.langue_de_la_console(self.config('en')), 'en')
            self.assertEqual(serveur.langue_de_la_console(self.config('fr')), 'fr')
        with mock.patch.object(serveur.locale, 'getlocale', return_value=('en_GB', 'UTF-8')):
            self.assertEqual(serveur.langue_de_la_console(self.config('fr')), 'fr')
            self.assertEqual(serveur.choisir_langue_console(self.config('en')), 'en')
            self.assertEqual(serveur.CONSOLE['langue'], 'en')

    def test_sans_reglage_la_langue_du_systeme(self):
        cas = ((('fr_FR', 'cp1252'), 'fr'), (('French_France', '1252'), 'fr'), (('fr_CA', 'UTF-8'), 'fr'),
               (('en_US', 'UTF-8'), 'en'), (('de_DE', 'UTF-8'), 'en'), ((None, None), 'en'))
        for systeme, attendue in cas:
            with self.subTest(systeme=systeme), mock.patch.object(serveur.locale, 'getlocale', return_value=systeme):
                self.assertEqual(serveur.langue_de_la_console(self.config()), attendue)          # sans réglage
                self.assertEqual(serveur.langue_de_la_console(self.config('de')), attendue)      # non déclarée
                self.assertEqual(serveur.langue_de_la_console(self.config('x"<b>')), attendue)  # mal formée
                self.assertEqual(serveur.langue_de_la_console(None), attendue)                  # avant la config
        (self.dossier / 'donnees' / 'parametres.csv').unlink()
        with mock.patch.object(serveur.locale, 'getlocale', return_value=('en_US', 'UTF-8')):
            self.assertEqual(serveur.langue_de_la_console(serveur.Configuration(str(self.dossier / 'donnees'), [])), 'en')
        with mock.patch.object(serveur.locale, 'getlocale', side_effect=ValueError('locale inconnue')):
            self.assertEqual(serveur.langue_de_la_console(None), 'en')

    def test_afficher_ecrit_dans_la_langue_de_la_console(self):
        arret = serveur.traduisible('console.serveur_arrete', 'Serveur arrêté.')
        self.assertEqual(self.ecrire(arret, 'fr'), 'Serveur arrêté.')
        self.assertEqual(self.ecrire(arret, 'en'), 'Server stopped.')
        # Valeurs traduites à leur tour, pluriel anglais.
        for jours, francais, anglais in ((1, '1 jour', '1 day'), (30, '30 jours', '30 days')):
            resume = serveur.resume_tailscale({'present': True, 'nom': 'prevo.ts.net', 'connecte': True,
                                               'jours_avant_expiration': jours})
            ligne = serveur.traduisible('console.accueil.tailscale', '  Tailscale        : {resume}', resume=resume)
            self.assertEqual(self.ecrire(ligne, 'fr'), '  Tailscale        : prevo.ts.net, connecté, clé valable ' + francais)
            self.assertEqual(self.ecrire(ligne, 'en'), '  Tailscale        : prevo.ts.net, connected, key valid for ' + anglais)
        refus = serveur.traduisible('console.demarrage_refuse', 'Démarrage refusé. {erreur}', erreur=serveur.traduisible(
            'config.cle_inconnue', 'Configuration : clé inconnue « {cle} » ignorée.', cle='porte'))
        self.assertEqual(self.ecrire(refus, 'en'), 'Start refused. Configuration: unknown key “porte” ignored.')
        # Texte qui n'est pas un message, clé anglaise absente : tels quels.
        self.assertEqual(self.ecrire('12:00:00  127.0.0.1  GET /api/ping 200', 'en'), '12:00:00  127.0.0.1  GET /api/ping 200')
        self.assertEqual(self.ecrire(serveur.traduisible('essai.sans_anglais', 'Sans anglais.'), 'en'), 'Sans anglais.')

    def test_chaque_message_de_la_console_a_son_anglais(self):
        anglais = serveur.lire_textes_anglais()
        francais = ts.entrees_de_la_section(RACINE)
        console = [cle[len('serveur.'):] for cle in francais if cle.startswith('serveur.console.')]
        self.assertGreater(len(console), 60)
        self.assertEqual([code for code in console if code not in anglais], [])
        self.assertEqual(len(anglais), len(francais))
        self.assertEqual(anglais['config.cle_inconnue'], 'Configuration: unknown key “{cle}” ignored.')
        self.assertEqual(anglais['console.tailscale.cle_valable'],
                         {'one': 'key valid for {n} day', 'other': 'key valid for {n} days'})
        self.assertEqual(serveur.chaine_js("Pr\u00e9vo\\'s\\u00a0x \\\\ y\\n"), "Prévo's\u00a0x \\ y\n")
        self.assertEqual(serveur.lire_textes_anglais(str(self.dossier / 'absent.js')), {})

    def demarrer(self, langue):
        """Console d'un serveur lancé sur une copie de la démo avec langue_defaut = langue."""
        source = self.dossier / 'source'
        shutil.copytree(DOSSIER_DEMO, source)
        with open(source / 'parametres.csv', 'ab') as fichier:
            fichier.write(('langue_defaut;%s\r\n' % langue).encode('utf-8'))
        prevo = ServeurPrevo(source=source)
        prevo.demarrer()
        self.addCleanup(prevo.arreter)
        return prevo, prevo.sortie_console()

    def test_console_du_serveur_en_anglais_pour_une_installation_en_anglais(self):
        prevo, console = self.demarrer('en')
        for attendu in ('- local CMMS server', '  On this PC       : http://localhost:%d/' % prevo.port,
                        '  Data             : ', '  Listening        : this PC only (127.0.0.1)',
                        '  AI assistant     : Ollama, ', '  Ctrl+C to stop.', 'Backups: previous version of Prévo: unknown'):
            self.assertIn(attendu, console)
        for francais in ('Sur ce PC', 'Données', 'Écoute', 'pour arrêter', 'Sauvegardes :'):
            self.assertNotIn(francais, console)

    def test_console_du_serveur_en_francais_pour_une_installation_en_francais(self):
        prevo, console = self.demarrer('fr')
        for attendu in ('- serveur local de GMAO', '  Sur ce PC        : http://localhost:%d/' % prevo.port,
                        '  Écoute           : ce PC seulement (127.0.0.1)', '  Ctrl+C pour arrêter.',
                        'Sauvegardes : version de Prévo précédente : inconnue'):
            self.assertIn(attendu, console)
        self.assertNotIn('On this PC', console)


if __name__ == '__main__':
    unittest.main()
