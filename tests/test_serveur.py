# -*- coding: utf-8 -*-
"""Tests de serveur.py (API du §7 et liste blanche des fichiers servis du §14.7 de
docs/ARCHITECTURE.md ; les tests de la liste blanche ont « liste_blanche » dans leur nom).

Chaque classe lance le vrai serveur dans un sous-processus, sur un port libre et avec un
dossier de données TEMPORAIRE (jamais donnees/ réel), puis l'arrête et efface le dossier.
Les requêtes passent par http.client : les chemins sont envoyés BRUTS, sans normalisation
(indispensable pour tester « ..%2F », « %5C »…).

Fichier autonome : il ne dépend d'aucun autre fichier de tests.
Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_serveur.py" -v
"""
import ast
import datetime
import hashlib
import http.client
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest

DOSSIER_PROJET = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_SERVEUR = os.path.join(DOSSIER_PROJET, 'serveur.py')
BOM = b'\xef\xbb\xbf'


# ---------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------

def empreinte(octets):
    """Version attendue d'un fichier : SHA-256, 16 premiers caractères hexadécimaux."""
    return hashlib.sha256(octets).hexdigest()[:16]


def empreinte_fichier(chemin):
    with open(chemin, 'rb') as fichier:
        return hashlib.sha256(fichier.read()).hexdigest()


def port_libre():
    """Un port TCP libre (jamais 8080, réservé à l'usage réel)."""
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as essai:
            essai.bind(('127.0.0.1', 0))
            port = essai.getsockname()[1]
        if port != 8080:
            return port


def lire_tables_du_serveur():
    """La liste TABLES de serveur.py, lue sans importer le module."""
    with open(SCRIPT_SERVEUR, encoding='utf-8') as fichier:
        arbre = ast.parse(fichier.read())
    for noeud in arbre.body:
        if isinstance(noeud, ast.Assign) and getattr(noeud.targets[0], 'id', '') == 'TABLES':
            return list(ast.literal_eval(noeud.value))
    raise AssertionError('TABLES introuvable dans serveur.py')


TABLES = lire_tables_du_serveur()


def lire_colonnes_du_serveur():
    """Le dictionnaire COLONNES_PAR_TABLE de serveur.py, lu sans importer le module."""
    with open(SCRIPT_SERVEUR, encoding='utf-8') as fichier:
        arbre = ast.parse(fichier.read())
    for noeud in arbre.body:
        if isinstance(noeud, ast.Assign) and getattr(noeud.targets[0], 'id', '') == 'COLONNES_PAR_TABLE':
            return ast.literal_eval(noeud.value)
    raise AssertionError('COLONNES_PAR_TABLE introuvable dans serveur.py')


COLONNES_PAR_TABLE = lire_colonnes_du_serveur()


def entete(table, *en_plus):
    """Ligne d'en-tête du schéma de la table (octets, sans fin de ligne), suivie des colonnes en plus.

    Le serveur refuse un CSV dont l'en-tête ne commence pas par les colonnes du schéma (audit E2)."""
    return ';'.join(list(COLONNES_PAR_TABLE[table]) + list(en_plus)).encode('utf-8')


class Reponse:
    def __init__(self, statut, entetes, corps):
        self.statut = statut
        self.entetes = entetes          # noms en minuscules
        self.corps = corps

    def json(self):
        return json.loads(self.corps.decode('utf-8'))


class ServeurLance:
    """serveur.py lancé dans un sous-processus, avec lecture continue de sa console."""

    def __init__(self, dossier_donnees=None, port=None, script=SCRIPT_SERVEUR, options=()):
        self.dossier_donnees = dossier_donnees
        self.port_demande = port or port_libre()
        self.script = script
        self.options = list(options)        # options en plus, ex. ['--servir-tests']
        self.lignes = []
        self.port = None

    def demarrer(self):
        commande = [sys.executable, self.script, '--sans-navigateur',
                    '--port', str(self.port_demande)] + self.options
        if self.dossier_donnees:
            commande += ['--donnees', self.dossier_donnees]
        if '--config' not in self.options:
            # Lot 7 : réglages par défaut, quel que soit le prevo.config.json d'une installation à côté du script.
            commande += ['--config', os.path.join(tempfile.gettempdir(), 'prevo-tests-sans-configuration.json')]
        environnement = dict(os.environ, PYTHONIOENCODING='utf-8')
        self.processus = subprocess.Popen(
            commande, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            env=environnement, cwd=os.path.dirname(self.script))
        # La console est lue en continu : sinon le serveur se bloquerait, tuyau plein.
        self.lecteur = threading.Thread(target=self._lire_console, daemon=True)
        self.lecteur.start()
        self.port = self._attendre_port()
        self._attendre_ping()
        return self

    def _lire_console(self):
        for ligne in iter(self.processus.stdout.readline, b''):
            self.lignes.append(ligne.decode('utf-8', 'replace').rstrip())

    def console(self):
        return '\n'.join(self.lignes)

    def _attendre_port(self):
        limite = time.time() + 20
        while time.time() < limite:
            trouve = re.search(r'http://localhost:(\d+)/', self.console())
            if trouve:
                return int(trouve.group(1))
            if self.processus.poll() is not None:
                break
            time.sleep(0.05)
        self.arreter()
        raise AssertionError('Le serveur n\'a pas démarré :\n' + self.console())

    def _attendre_ping(self):
        limite = time.time() + 10
        while time.time() < limite:
            try:
                if self.requete('GET', '/api/ping').statut == 200:
                    return
            except OSError:
                pass
            time.sleep(0.05)
        self.arreter()
        raise AssertionError('/api/ping ne répond pas :\n' + self.console())

    def arreter(self):
        if self.processus.poll() is None:
            self.processus.terminate()
        self.processus.wait(timeout=10)
        self.lecteur.join(timeout=5)
        self.processus.stdout.close()

    def requete(self, methode, chemin, corps=None, entetes=None, hote=None, avec_prevo=True):
        """Envoie une requête brute. corps=None : pas de Content-Length automatique."""
        connexion = http.client.HTTPConnection('127.0.0.1', self.port, timeout=20)
        try:
            connexion.putrequest(methode, chemin, skip_host=True, skip_accept_encoding=True)
            connexion.putheader('Host', hote if hote is not None else '127.0.0.1:%d' % self.port)
            if methode in ('PUT', 'POST') and avec_prevo:
                connexion.putheader('X-Prevo', '1')
            for nom, valeur in (entetes or {}).items():
                connexion.putheader(nom, valeur)
            if corps is not None:
                connexion.putheader('Content-Length', str(len(corps)))
            connexion.endheaders()
            if corps:
                connexion.send(corps)
            reponse = connexion.getresponse()
            entetes_reponse = {nom.lower(): valeur for nom, valeur in reponse.getheaders()}
            return Reponse(reponse.status, entetes_reponse, reponse.read())
        finally:
            connexion.close()


class CasAvecServeur(unittest.TestCase):
    """Classe de base : un serveur et un dossier temporaire par classe de tests."""

    OPTIONS_SERVEUR = ()                # à redéfinir : options en plus, ex. ('--servir-tests',)

    def preparer_donnees(self_ou_classe, dossier_donnees):
        """À redéfinir : fichiers à créer AVANT le lancement du serveur."""

    @classmethod
    def setUpClass(cls):
        cls.dossier_temporaire = tempfile.mkdtemp(prefix='prevo-test-serveur-')
        cls.donnees = os.path.join(cls.dossier_temporaire, 'donnees')
        cls.preparer_donnees(cls, cls.donnees)
        cls.empreinte_serveur_py = empreinte_fichier(SCRIPT_SERVEUR)
        cls.serveur = ServeurLance(cls.donnees, options=cls.OPTIONS_SERVEUR).demarrer()

    @classmethod
    def tearDownClass(cls):
        cls.serveur.arreter()
        shutil.rmtree(cls.dossier_temporaire, ignore_errors=True)

    # Raccourcis
    def requete(self, *arguments, **options):
        return self.serveur.requete(*arguments, **options)

    def mettre_csv(self, table, octets, version='aucune'):
        return self.requete('PUT', '/api/csv/' + table, octets, {'X-Version-Attendue': version})

    def chemin_donnee(self, *morceaux):
        return os.path.join(self.donnees, *morceaux)

    def ecrire_fichier(self, chemin, octets):
        with open(chemin, 'wb') as fichier:
            fichier.write(octets)

    def lire_fichier(self, chemin):
        with open(chemin, 'rb') as fichier:
            return fichier.read()

    # Liste blanche (§14.7) : vérifications communes aux classes qui lancent le vrai projet.

    def verifier_non_servi(self, chemin):
        """GET chemin → 404 « Fichier introuvable. », sans aucun octet du fichier du projet."""
        reponse = self.requete('GET', chemin)
        self.assertEqual(reponse.statut, 404, 'GET %s → %d' % (chemin, reponse.statut))
        self.assertEqual(reponse.json(), {'erreur': 'Fichier introuvable.', 'erreur_code': 'statique.introuvable'})
        fichier = os.path.join(DOSSIER_PROJET, *chemin.lstrip('/').split('/'))
        if os.path.isfile(fichier):
            debut = self.lire_fichier(fichier)[:64]
            if debut:
                self.assertNotIn(debut, reponse.corps)

    def verifier_servi(self, chemin, fichier, type_attendu):
        """GET chemin → 200, le bon type MIME et exactement les octets du fichier du projet."""
        reponse = self.requete('GET', chemin)
        self.assertEqual(reponse.statut, 200, 'GET %s → %d' % (chemin, reponse.statut))
        self.assertEqual(reponse.entetes['content-type'], type_attendu)
        self.assertEqual(reponse.entetes['cache-control'], 'no-cache')
        self.assertEqual(reponse.corps, self.lire_fichier(os.path.join(DOSSIER_PROJET, fichier)))

    def fichiers_temporaires_restants(self):
        restants = []
        for dossier, _, fichiers in os.walk(self.donnees):
            restants += [os.path.join(dossier, nom) for nom in fichiers
                         if nom.startswith('.') or nom.endswith('.tmp')]
            restants += [dossier] if os.path.basename(dossier).startswith('.') else []
        return restants


# ---------------------------------------------------------------------------
# API principale (un seul serveur pour toute la classe)
# ---------------------------------------------------------------------------

class TestApiServeur(CasAvecServeur):

    # --- ping, info, versions ---------------------------------------------

    def test_ping(self):
        reponse = self.requete('GET', '/api/ping')
        self.assertEqual(reponse.statut, 200)
        donnees = reponse.json()
        self.assertEqual(donnees['application'], 'Prévo')
        self.assertEqual(donnees['api'], 1)
        self.assertTrue(donnees['version'])
        self.assertEqual(reponse.entetes['cache-control'], 'no-store')
        self.assertTrue(reponse.entetes['content-type'].startswith('application/json'))

    def test_rafale_de_connexions_simultanees_ni_refus_ni_attente(self):
        """Un navigateur ouvre ~6 connexions d'un coup par page (HTTP/1.0 : une par requête),
        plusieurs postes et téléphones s'ajoutent. Avec la file d'écoute par défaut de socketserver
        (5), Windows réinitialise (WinError 10054, ERR_CONNECTION_RESET) ou retarde d'une seconde
        (nouvel envoi du SYN) les connexions en trop : le ping de détection (2 s) échouait alors."""
        nombre = 60
        resultats = []
        depart = threading.Event()

        def ping():
            depart.wait()
            debut = time.monotonic()
            try:
                connexion = http.client.HTTPConnection('127.0.0.1', self.serveur.port, timeout=10)
                connexion.request('GET', '/api/ping')
                statut = connexion.getresponse().status
                connexion.close()
                resultats.append((statut, time.monotonic() - debut))
            except OSError as erreur:
                resultats.append((repr(erreur), time.monotonic() - debut))

        for _ in range(3):
            resultats.clear()
            depart.clear()
            fils = [threading.Thread(target=ping) for _ in range(nombre)]
            for fil in fils:
                fil.start()
            depart.set()
            for fil in fils:
                fil.join()
            self.assertEqual([r for r in resultats if r[0] != 200], [])
            lents = sorted(round(duree, 2) for _, duree in resultats if duree > 0.9)
            self.assertEqual(lents, [], "réponses de plus de 0,9 s (connexion mise en attente par le système)")

    def test_connexion_persistante_http_1_1(self):
        """Plusieurs requêtes (lecture, écriture, erreur 404) sur UNE connexion : le navigateur
        réutilise ses connexions au lieu d'en ouvrir une par requête (ERR_NO_BUFFER_SPACE)."""
        connexion = http.client.HTTPConnection('127.0.0.1', self.serveur.port, timeout=10)
        try:
            connexion.request('GET', '/api/ping')
            premiere = connexion.getresponse()
            premiere.read()
            self.assertEqual((premiere.status, premiere.version), (200, 11))
            self.assertFalse(premiere.will_close, 'le serveur ferme la connexion après chaque réponse')
            prise = connexion.sock
            for methode, chemin, corps, attendu in (
                    ('GET', '/index.html', None, 200),
                    ('GET', '/api/csv/table_inconnue', None, 404),
                    ('PUT', '/api/documents/persistante-test.txt', b'texte', 201),
                    ('GET', '/api/versions', None, 200)):
                entetes = {'X-Prevo': '1', 'Content-Type': 'text/csv; charset=utf-8'} if corps is not None else {}
                connexion.request(methode, chemin, corps, entetes)
                reponse = connexion.getresponse()
                reponse.read()
                with self.subTest(chemin=chemin):
                    self.assertEqual(reponse.status, attendu)
                    self.assertIs(connexion.sock, prise, 'nouvelle connexion ouverte')
        finally:
            connexion.close()

    def test_aucune_entete_cors(self):
        for chemin in ('/api/ping', '/api/versions', '/index.html', '/serveur.py'):
            reponse = self.requete('GET', chemin, entetes={'Origin': 'http://evil.example'})
            self.assertFalse([nom for nom in reponse.entetes if nom.startswith('access-control')])

    def test_info(self):
        donnees = self.requete('GET', '/api/info').json()
        self.assertEqual(donnees['port'], self.serveur.port)
        self.assertEqual(donnees['adresse_locale'], 'http://localhost:%d/' % self.serveur.port)
        self.assertIsInstance(donnees['adresses_reseau'], list)
        for adresse in donnees['adresses_reseau']:
            self.assertRegex(adresse, r'^http://[0-9.]+:%d/$' % self.serveur.port)
            self.assertFalse(adresse.startswith('http://127.'))

    def test_versions_24_tables(self):
        # 22 tables du brief, puis wiki_pages et wiki_journal (format 3, lot 6, ARCHITECTURE.md §20.2).
        self.assertEqual(len(TABLES), 24)
        self.assertEqual(list(TABLES[-2:]), ['wiki_pages', 'wiki_journal'])
        self.mettre_csv('localisations', BOM + b'id;libelle;parent_id;type\r\n')
        tables = self.requete('GET', '/api/versions').json()['tables']
        self.assertEqual(set(tables), set(TABLES))
        info = tables['localisations']
        self.assertEqual(info['version'], empreinte(BOM + b'id;libelle;parent_id;type\r\n'))
        self.assertRegex(info['modifie'], r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')
        self.assertIsNone(tables['achats'])

    def test_dossiers_documents_et_sauvegardes_crees(self):
        self.assertTrue(os.path.isdir(self.chemin_donnee('documents')))
        self.assertTrue(os.path.isdir(self.chemin_donnee('sauvegardes')))

    # --- CSV : lecture et écriture complète --------------------------------

    def test_csv_absent_404(self):
        self.assertEqual(self.requete('GET', '/api/csv/achats').statut, 404)

    def test_csv_put_puis_get(self):
        contenu = BOM + entete('techniciens') + '\r\nTEC-0001;Dupré;Élodie\r\n'.encode('utf-8')
        reponse = self.mettre_csv('techniciens', contenu)
        self.assertEqual(reponse.statut, 200)
        version = reponse.json()['version']
        self.assertEqual(version, empreinte(contenu))
        lecture = self.requete('GET', '/api/csv/techniciens')
        self.assertEqual(lecture.statut, 200)
        self.assertEqual(lecture.corps, contenu)
        self.assertEqual(lecture.entetes['x-version'], version)
        self.assertEqual(lecture.entetes['cache-control'], 'no-store')
        self.assertEqual(self.lire_fichier(self.chemin_donnee('techniciens.csv')), contenu)
        # Écriture suivante avec la bonne version : acceptée.
        suite = contenu + b'TEC-0002;Martin;Paul\r\n'
        reponse = self.mettre_csv('techniciens', suite, version)
        self.assertEqual(reponse.statut, 200)
        self.assertEqual(reponse.json()['version'], empreinte(suite))

    def test_csv_put_aucune_sur_fichier_existant_conflit(self):
        contenu = BOM + entete('fournisseurs') + b'\r\n'
        self.assertEqual(self.mettre_csv('fournisseurs', contenu).statut, 200)
        reponse = self.mettre_csv('fournisseurs', BOM + entete('fournisseurs') + b'\r\nFOU-0001\r\n', 'aucune')
        self.assertEqual(reponse.statut, 409)
        self.assertEqual(reponse.json()['version_actuelle'], empreinte(contenu))
        self.assertIn('erreur', reponse.json())
        self.assertEqual(self.lire_fichier(self.chemin_donnee('fournisseurs.csv')), contenu)

    def test_csv_put_version_perimee_conflit(self):
        premier = BOM + entete('compteurs') + b'\r\nCPT-0001;Heures\r\n'
        version_1 = self.mettre_csv('compteurs', premier).json()['version']
        second = premier + b'CPT-0002;Coups\r\n'
        self.assertEqual(self.mettre_csv('compteurs', second, version_1).statut, 200)
        # Un autre poste écrit avec la version 1, devenue périmée.
        reponse = self.mettre_csv('compteurs', premier + b'CPT-0003;Km\r\n', version_1)
        self.assertEqual(reponse.statut, 409)
        self.assertEqual(reponse.json()['version_actuelle'], empreinte(second))
        self.assertEqual(self.lire_fichier(self.chemin_donnee('compteurs.csv')), second)

    def test_csv_put_version_sur_fichier_absent_conflit(self):
        reponse = self.mettre_csv('releves', BOM + entete('releves') + b'\r\n', '0123456789abcdef')
        self.assertEqual(reponse.statut, 409)
        self.assertIsNone(reponse.json()['version_actuelle'])

    def test_csv_put_sans_version_attendue_400(self):
        reponse = self.requete('PUT', '/api/csv/gammes', BOM + entete('gammes') + b'\r\n')
        self.assertEqual(reponse.statut, 400)
        self.assertFalse(os.path.exists(self.chemin_donnee('gammes.csv')))

    def test_table_inconnue_404(self):
        self.assertEqual(self.requete('GET', '/api/csv/inconnue').statut, 404)
        self.assertEqual(self.mettre_csv('inconnue', b'x').statut, 404)
        self.assertEqual(self.requete('POST', '/api/csv/inconnue/ajout', b'a\r\n').statut, 404)
        self.assertEqual(self.requete('GET', '/api/inexistant').statut, 404)
        self.assertFalse(os.path.exists(self.chemin_donnee('inconnue.csv')))

    # --- CSV : ajout (journal) ------------------------------------------

    def test_ajout_creation_avec_bom(self):
        corps = entete('journal') + b'\r\nJ-1;creation\r\n'
        reponse = self.requete('POST', '/api/csv/journal/ajout', corps)
        self.assertEqual(reponse.statut, 200)
        self.assertEqual(self.lire_fichier(self.chemin_donnee('journal.csv')), BOM + corps)
        self.assertEqual(reponse.json()['version'], empreinte(BOM + corps))

    def test_ajout_ajoute_les_lignes(self):
        # Fichier existant SANS fin de ligne finale : le serveur doit en ajouter une.
        existant = BOM + entete('habilitations') + '\r\nHAB-0001;Électrique'.encode('utf-8')
        self.ecrire_fichier(self.chemin_donnee('habilitations.csv'), existant)
        reponse = self.requete('POST', '/api/csv/habilitations/ajout',
                               entete('habilitations') + b'\r\nHAB-0002;H0V\r\nHAB-0003;BR\r\n')
        self.assertEqual(reponse.statut, 200)
        attendu = existant + b'\r\nHAB-0002;H0V\r\nHAB-0003;BR\r\n'
        self.assertEqual(self.lire_fichier(self.chemin_donnee('habilitations.csv')), attendu)
        self.assertEqual(reponse.json()['version'], empreinte(attendu))

    def test_ajout_entete_different_conflit(self):
        # Fichier existant : en-tête du schéma plus une colonne ajoutée dans Excel ;
        # corps : en-tête du schéma seul.
        existant = BOM + entete('ot_temps', 'autre') + b'\r\nA;B\r\n'
        self.ecrire_fichier(self.chemin_donnee('ot_temps.csv'), existant)
        reponse = self.requete('POST', '/api/csv/ot_temps/ajout', entete('ot_temps') + b'\r\nC;D\r\n')
        self.assertEqual(reponse.statut, 409)
        self.assertEqual(reponse.json()['version_actuelle'], empreinte(existant))
        self.assertEqual(self.lire_fichier(self.chemin_donnee('ot_temps.csv')), existant)

    def test_ajout_fichier_windows1252_conflit(self):
        # Réenregistré par Excel en Windows-1252 ; le corps envoyé, lui, est en UTF-8 correct.
        existant = (entete('ot_pieces').decode('utf-8') + '\r\nX;Réparé\r\n').encode('cp1252')
        self.ecrire_fichier(self.chemin_donnee('ot_pieces.csv'), existant)
        reponse = self.requete('POST', '/api/csv/ot_pieces/ajout', entete('ot_pieces') + b'\r\nY;Z\r\n')
        self.assertEqual(reponse.statut, 409)
        self.assertEqual(self.lire_fichier(self.chemin_donnee('ot_pieces.csv')), existant)

    # --- Documents ----------------------------------------------------------

    def test_document_envoi_puis_lecture(self):
        octets = b'\xff\xd8\xff\xe0 fausse photo JPEG'
        reponse = self.requete('PUT', '/api/documents/photo-DI_2026.0001.jpg', octets)
        self.assertEqual(reponse.statut, 201)
        # Audit F4 (T159) : le serveur impose le nom « AAAAMMJJ-HHMMSS-<nom demandé> », rendu dans la réponse.
        nom = reponse.json()['nom']
        self.assertRegex(nom, r'^[0-9]{8}-[0-9]{6}-photo-DI_2026\.0001\.jpg$')
        lecture = self.requete('GET', '/api/documents/' + nom)
        self.assertEqual(lecture.statut, 200)
        self.assertEqual(lecture.corps, octets)
        self.assertEqual(lecture.entetes['content-type'], 'image/jpeg')
        self.assertEqual(lecture.entetes['x-content-type-options'], 'nosniff')
        self.assertEqual(lecture.entetes['content-security-policy'], 'sandbox')
        self.assertEqual(self.lire_fichier(self.chemin_donnee('documents', nom)), octets)
        self.assertEqual(self.requete('GET', '/api/documents/photo-DI_2026.0001.jpg').statut, 404)

    def test_document_jamais_ecrase(self):
        # Même nom demandé deux fois : même seconde ⇒ 409 (prouvé sans aléa dans test_audit_reseau), seconde suivante ⇒
        # un autre nom imposé. Dans les deux cas, le premier document reste intact.
        premiere = self.requete('PUT', '/api/documents/rapport.pdf', b'v1')
        self.assertEqual(premiere.statut, 201)
        nom = premiere.json()['nom']
        seconde = self.requete('PUT', '/api/documents/rapport.pdf', b'v2')
        self.assertIn(seconde.statut, (201, 409))
        if seconde.statut == 201:
            self.assertNotEqual(seconde.json()['nom'], nom)
        self.assertEqual(self.lire_fichier(self.chemin_donnee('documents', nom)), b'v1')
        self.assertFalse(os.path.exists(self.chemin_donnee('documents', 'rapport.pdf')))

    def test_document_extension_415_ou_nom_interdit_400(self):
        # « page.html » est accepté depuis le lot 3 (rapport mensuel figé, §15.1) : « .htm » reste refusé.
        # Audit F4 (T159) : une extension inconnue répond 415, un nom refusé 400.
        for nom in ('page.htm', 'image.svg', 'script.js', 'sans-extension', 'lettre.doc', 'classeur.xls'):
            with self.subTest(nom=nom):
                self.assertEqual(self.requete('PUT', '/api/documents/' + nom, b'<b>x</b>').statut, 415)
                self.assertEqual(self.requete('GET', '/api/documents/' + nom).statut, 415)
        for nom in ('CON.txt', '-tiret.jpg', 'a%20b.jpg', 'a..b.jpg', 'x' * 130 + '.jpg', '%C3%A9t%C3%A9.jpg'):
            with self.subTest(nom=nom):
                self.assertEqual(self.requete('PUT', '/api/documents/' + nom, b'<b>x</b>').statut, 400)
        self.assertEqual([nom for nom in os.listdir(self.chemin_donnee('documents'))
                          if nom.endswith(('.htm', '.svg', '.js', '.doc', '.xls', 'sans-extension'))], [])

    def test_document_absent_404(self):
        self.assertEqual(self.requete('GET', '/api/documents/absent.png').statut, 404)

    # --- Traversées de dossiers ---------------------------------------------

    CHEMINS_TRAVERSEE = (
        '/api/documents/../serveur.py',
        '/api/documents/..%2Fserveur.py',
        '/api/documents/%2e%2e%2fserveur.py',
        '/api/documents/..%5Cserveur.py',
        '/api/documents/..\\serveur.py',
        '/api/documents/....//serveur.py',
        '/api/documents/%252e%252e%252fserveur.py',
        '/api/csv/../serveur',
        '/api/csv/..%2F..%2Fserveur',
        '/api/csv/..%5C..%5Cserveur',
        '/api/csv/%2e%2e%2f%2e%2e%2fserveur',
        '/donnees/x.csv',
        '/DONNEES/x.csv',
        '/donnees./x.csv',
        '/%2e%2e/',
        '/%2e%2e/%2e%2e/Windows/win.ini',
        '/....//serveur.py',
        '/.git/config',
        '/%2Egit/config',
        '/serveur.py::$DATA',
        '/css/..%2F..%2Fserveur.py',
    )

    def test_traversee_refusee_en_lecture(self):
        for chemin in self.CHEMINS_TRAVERSEE:
            with self.subTest(chemin=chemin):
                statut = self.requete('GET', chemin).statut
                self.assertTrue(400 <= statut < 500, 'GET %s → %d' % (chemin, statut))

    def test_traversee_refusee_en_ecriture(self):
        for chemin in self.CHEMINS_TRAVERSEE:
            for methode in ('PUT', 'POST'):
                with self.subTest(chemin=chemin, methode=methode):
                    statut = self.requete(methode, chemin, b'pirate\r\n',
                                          {'X-Version-Attendue': 'aucune'}).statut
                    self.assertTrue(400 <= statut < 500, '%s %s → %d' % (methode, chemin, statut))
                    statut = self.requete(methode, chemin + '/ajout', b'pirate\r\n').statut
                    self.assertTrue(400 <= statut < 500)
        # Rien n'a bougé hors du dossier de données.
        self.assertEqual(empreinte_fichier(SCRIPT_SERVEUR), self.empreinte_serveur_py)
        self.assertEqual(os.listdir(self.dossier_temporaire), ['donnees'])
        for dossier in (DOSSIER_PROJET, self.dossier_temporaire, os.path.dirname(DOSSIER_PROJET)):
            for nom in ('serveur', 'serveur.csv'):
                self.assertFalse(os.path.exists(os.path.join(dossier, nom)), (dossier, nom))
        for dossier, _, fichiers in os.walk(self.donnees):
            for nom in fichiers:
                self.assertNotIn(b'pirate', self.lire_fichier(os.path.join(dossier, nom)), nom)

    # --- Contrôles de sécurité des requêtes ---------------------------------

    def test_corps_trop_gros_413(self):
        trop = str(10 * 1024 * 1024 + 1)
        reponse = self.requete('PUT', '/api/documents/gros.pdf', None, {'Content-Length': trop})
        self.assertEqual(reponse.statut, 413)
        self.assertFalse(os.path.exists(self.chemin_donnee('documents', 'gros.pdf')))

    def test_corps_de_10_mo_accepte(self):
        octets = b'0' * (10 * 1024 * 1024)
        self.assertEqual(self.requete('PUT', '/api/documents/pile-10-mo.txt', octets).statut, 201)

    def test_sans_content_length_411(self):
        reponse = self.requete('PUT', '/api/csv/achats', None, {'X-Version-Attendue': 'aucune'})
        self.assertEqual(reponse.statut, 411)
        self.assertEqual(self.requete('POST', '/api/sauvegarde').statut, 411)

    def test_sans_x_prevo_403(self):
        reponse = self.requete('PUT', '/api/csv/achats', entete('achats') + b'\r\n',
                               {'X-Version-Attendue': 'aucune'}, avec_prevo=False)
        self.assertEqual(reponse.statut, 403)
        reponse = self.requete('POST', '/api/sauvegarde', b'', {'X-Prevo': '0'}, avec_prevo=False)
        self.assertEqual(reponse.statut, 403)
        self.assertFalse(os.path.exists(self.chemin_donnee('achats.csv')))

    def test_host_evil_403(self):
        nom_pc = socket.gethostname()
        # Le nom du PC suivi d'un domaine quelconque ouvrirait la porte au « DNS rebinding ».
        for hote in ('evil.example', 'evil.example:%d' % self.serveur.port, '', 'localhost.evil.example',
                     '%s.attacker.example' % nom_pc, '%s.attacker.example:%d' % (nom_pc, self.serveur.port)):
            with self.subTest(hote=hote):
                self.assertEqual(self.requete('GET', '/api/ping', hote=hote).statut, 403)
        reponse = self.requete('PUT', '/api/csv/achats', entete('achats') + b'\r\n',
                               {'X-Version-Attendue': 'aucune'}, hote='evil.example')
        self.assertEqual(reponse.statut, 403)
        self.assertFalse(os.path.exists(self.chemin_donnee('achats.csv')))

    def test_host_accepte_200(self):
        port = self.serveur.port
        nom_pc = socket.gethostname()
        for hote in ('127.0.0.1:%d' % port, 'localhost:%d' % port, '192.168.1.10:%d' % port,
                     '[::1]:%d' % port, nom_pc, '%s:%d' % (nom_pc.upper(), port),
                     '%s.local:%d' % (nom_pc, port), '%s.lan' % nom_pc, '%s.home.arpa' % nom_pc):
            with self.subTest(hote=hote):
                self.assertEqual(self.requete('GET', '/api/ping', hote=hote).statut, 200)

    def test_peripherique_windows_refuse_sans_erreur_interne(self):
        # « nul », « con »… désignent des périphériques sous Windows : refus propre, jamais 500.
        for chemin in ('/nul', '/con', '/NUL.txt', '/api/documents/nul.pdf'):
            with self.subTest(chemin=chemin):
                self.assertIn(self.requete('GET', chemin).statut, (400, 404))

    def test_dossier_dans_documents_404(self):
        os.makedirs(self.chemin_donnee('documents', 'rep.pdf'), exist_ok=True)
        self.assertEqual(self.requete('GET', '/api/documents/rep.pdf').statut, 404)

    def test_aucun_fichier_temporaire_apres_ecriture(self):
        version = self.mettre_csv('articles', BOM + entete('articles') + b'\r\n').json()['version']
        for numero in range(5):
            contenu = BOM + entete('articles') + b'\r\nART-000%d\r\n' % numero
            version = self.mettre_csv('articles', contenu, version).json()['version']
        self.requete('POST', '/api/csv/mouvements_stock/ajout', entete('mouvements_stock') + b'\r\nMVT-1\r\n')
        self.requete('POST', '/api/csv/mouvements_stock/ajout', entete('mouvements_stock') + b'\r\nMVT-2\r\n')
        self.requete('PUT', '/api/documents/temp-test.png', b'\x89PNG\r\n\x1a\n' + b'png')     # signature PNG (audit F4)
        self.assertEqual(self.fichiers_temporaires_restants(), [])

    # --- Sauvegardes ----------------------------------------------------------

    def test_sauvegarde_manuelle_liste_et_restauration(self):
        etat_a = BOM + entete('codes_defaillance') + b'\r\nFOU-A;Avant\r\n'
        etat_b = BOM + entete('codes_defaillance') + b'\r\nFOU-B;Apres\r\n'
        chemin = self.chemin_donnee('codes_defaillance.csv')
        version = self.mettre_csv('codes_defaillance', etat_a).json()['version']
        # Sauvegarde manuelle.
        reponse = self.requete('POST', '/api/sauvegarde', b'')
        self.assertEqual(reponse.statut, 200)
        nom = reponse.json()['sauvegarde']
        self.assertRegex(nom, r'^\d{4}-\d{2}-\d{2}_\d{6}$')
        self.assertEqual(self.lire_fichier(self.chemin_donnee('sauvegardes', nom,
                                                              'codes_defaillance.csv')), etat_a)
        # Liste : elle contient la sauvegarde et ses tables.
        liste = self.requete('GET', '/api/sauvegardes').json()['sauvegardes']
        trouvee = [s for s in liste if s['nom'] == nom]
        self.assertEqual(len(trouvee), 1)
        self.assertIn('codes_defaillance', trouvee[0]['tables'])
        self.assertEqual([s['nom'] for s in liste], sorted([s['nom'] for s in liste], reverse=True))
        # Modification puis restauration de la seule table demandée.
        self.mettre_csv('codes_defaillance', etat_b, version)
        demande = json.dumps({'sauvegarde': nom, 'tables': ['codes_defaillance']}).encode()
        reponse = self.requete('POST', '/api/restauration', demande)
        self.assertEqual(reponse.statut, 200, reponse.corps)
        resultat = reponse.json()
        self.assertEqual(resultat['restaurees'], ['codes_defaillance'])
        self.assertRegex(resultat['copie_securite'], r'^\d{4}-\d{2}-\d{2}_\d{6}_avant-restauration$')
        self.assertEqual(self.lire_fichier(chemin), etat_a)
        copie = self.chemin_donnee('sauvegardes', resultat['copie_securite'], 'codes_defaillance.csv')
        self.assertEqual(self.lire_fichier(copie), etat_b)
        # Sans liste de tables : toutes les tables de la sauvegarde.
        demande = json.dumps({'sauvegarde': nom}).encode()
        resultat = self.requete('POST', '/api/restauration', demande).json()
        self.assertIn('codes_defaillance', resultat['restaurees'])
        self.assertEqual(self.fichiers_temporaires_restants(), [])

    def test_restauration_noms_refuses(self):
        for demande, statut in (({'sauvegarde': '../donnees'}, 400),
                                ({'sauvegarde': '2026-01-01/../..'}, 400),
                                ({}, 400),
                                ({'sauvegarde': '1999-01-01'}, 404)):
            with self.subTest(demande=demande):
                reponse = self.requete('POST', '/api/restauration', json.dumps(demande).encode())
                self.assertEqual(reponse.statut, statut)
        # Sauvegarde à motif : la manuelle est limitée à une par minute (T175, D133) et ce serveur sert toute la classe.
        nom = self.requete('POST', '/api/sauvegarde', b'{"motif": "avant-import"}').json()['sauvegarde']
        demande = {'sauvegarde': nom, 'tables': ['../serveur']}
        reponse = self.requete('POST', '/api/restauration', json.dumps(demande).encode())
        self.assertEqual(reponse.statut, 400)
        self.assertEqual(self.requete('POST', '/api/restauration', b'pas du json').statut, 400)

    # --- Fichiers statiques et journal console ------------------------------

    def test_liste_blanche_serveur_py_non_servi(self):
        """Lot 2 (§14.7) : serveur.py n'est plus public (il l'était au lot 1)."""
        reponse = self.requete('GET', '/serveur.py')
        self.assertEqual(reponse.statut, 404)
        self.assertEqual(reponse.json(), {'erreur': 'Fichier introuvable.', 'erreur_code': 'statique.introuvable'})
        self.assertNotIn(self.lire_fichier(SCRIPT_SERVEUR)[:64], reponse.corps)
        self.assertNotIn(b'VERROU_ECRITURE', reponse.corps)
        self.assertEqual(reponse.entetes['content-type'], 'application/json; charset=utf-8')

    # Fichiers du projet qui ne sont jamais servis (présents ou non sur ce poste).
    CHEMINS_HORS_LISTE_BLANCHE = (
        '/docs/brief-gmao.md', '/README.md', '/LISEZMOI.md', '/docs/ARCHITECTURE.md',
        '/tests/commun.py', '/tests/fixtures/page-vide.html', '/outils/generer_demo.py',
        '/reference-design/style.css', '/reference-design/absent.txt',
        '/serveur.py', '/Serveur.py', '/SERVEUR.PY', '/LICENSE', '/Lancer_GMAO.bat', '/lancer.sh',
        '/css', '/js', '/tests', '/index.html/x', '/favicon.svg/x',
    )

    def test_liste_blanche_fichiers_du_projet_non_servis(self):
        for chemin in self.CHEMINS_HORS_LISTE_BLANCHE:
            with self.subTest(chemin=chemin):
                self.verifier_non_servi(chemin)
        # GUIDE.html est servi seulement s'il existe (lot 4) : absent → 404.
        if not os.path.exists(os.path.join(DOSSIER_PROJET, 'GUIDE.html')):
            self.verifier_non_servi('/GUIDE.html')

    def test_liste_blanche_fichier_cache_refuse(self):
        # « .gitattributes » commence par « . » : refusé avant même la liste blanche (400, §7).
        reponse = self.requete('GET', '/.gitattributes')
        self.assertTrue(400 <= reponse.statut < 500, reponse.statut)
        self.assertEqual(set(reponse.json()), {'erreur', 'erreur_code'})          # D157 : le message et son code
        chemin = os.path.join(DOSSIER_PROJET, '.gitattributes')
        if os.path.isfile(chemin):
            self.assertNotIn(self.lire_fichier(chemin)[:64], reponse.corps)

    FICHIERS_LISTE_BLANCHE = (
        ('/', 'index.html', 'text/html; charset=utf-8'),
        ('/index.html', 'index.html', 'text/html; charset=utf-8'),
        ('/favicon.svg', 'favicon.svg', 'image/svg+xml; charset=utf-8'),
        ('/css/style.css', 'css/style.css', 'text/css; charset=utf-8'),
        ('/js/app.js', 'js/app.js', 'text/javascript; charset=utf-8'),
        ('/js/lib/LICENCES.txt', 'js/lib/LICENCES.txt', 'text/plain; charset=utf-8'),
        ('/css/polices/sora-latin-wght-normal.woff2', 'css/polices/sora-latin-wght-normal.woff2',
         'font/woff2'),
    )

    def test_liste_blanche_fichiers_de_l_application_servis(self):
        for chemin, fichier, type_attendu in self.FICHIERS_LISTE_BLANCHE:
            with self.subTest(chemin=chemin):
                self.verifier_servi(chemin, fichier, type_attendu)
        self.assertEqual(self.requete('GET', '/index.html?v=2').statut, 200)

    @unittest.skipUnless(os.name == 'nt', 'Windows (NTFS) ne distingue pas les majuscules')
    def test_liste_blanche_casse_ignoree(self):
        for chemin, fichier, type_attendu in (
                ('/Index.html', 'index.html', 'text/html; charset=utf-8'),
                ('/FAVICON.SVG', 'favicon.svg', 'image/svg+xml; charset=utf-8'),
                ('/CSS/style.css', 'css/style.css', 'text/css; charset=utf-8'),
                ('/Js/app.js', 'js/app.js', 'text/javascript; charset=utf-8')):
            with self.subTest(chemin=chemin):
                self.verifier_servi(chemin, fichier, type_attendu)

    def test_statique_absent_404_et_methode_405(self):
        self.assertEqual(self.requete('GET', '/inexistant-xyz.js').statut, 404)
        self.assertEqual(self.requete('PUT', '/serveur.py', b'x').statut, 405)
        self.assertEqual(empreinte_fichier(SCRIPT_SERVEUR), self.empreinte_serveur_py)

    def test_journal_console_une_ligne_par_ecriture(self):
        self.requete('GET', '/api/csv/parametres')
        self.mettre_csv('parametres', BOM + b'cle;valeur\r\n')
        limite = time.time() + 5
        while "PUT '/api/csv/parametres'" not in self.serveur.console() and time.time() < limite:
            time.sleep(0.05)
        lignes = [l for l in self.serveur.lignes if '/api/csv/parametres' in l]
        self.assertEqual(len(lignes), 1, lignes)
        # Audit I2 (T159) : le chemin, venu du client, est écrit en repr (entre apostrophes).
        self.assertRegex(lignes[0], r"^\d{2}:\d{2}:\d{2}\s+127\.0\.0\.1\s+PUT '/api/csv/parametres'\s+200$")

    def test_console_de_demarrage(self):
        console = self.serveur.console()
        self.assertIn('Prévo', console)
        self.assertIn('http://localhost:%d/' % self.serveur.port, console)
        self.assertIn(self.donnees, console)
        self.assertIn('Ctrl+C', console)
        # Lot 7 (§22.1) : la console dit où le serveur écoute ; sans configuration, ce PC seulement.
        self.assertIn('ce PC seulement (127.0.0.1)', console)


# ---------------------------------------------------------------------------
# Sauvegarde quotidienne (serveur neuf : la première écriture du jour est maîtrisée)
# ---------------------------------------------------------------------------

class TestSauvegardeQuotidienne(CasAvecServeur):

    ETAT_AVANT = BOM + entete('techniciens') + b'\r\nTEC-0001;Avant\r\n'
    # T185 : base au format courant (version_schema 3), sinon le serveur la passerait au format courant à son
    # démarrage (parametres.csv et journal.csv créés, sauvegarde « avant-format-v3 »).
    PARAMETRES = BOM + entete('parametres') + b"\r\nversion_schema;'3\r\n"

    def preparer_donnees(cls, dossier_donnees):
        os.makedirs(dossier_donnees)
        with open(os.path.join(dossier_donnees, 'techniciens.csv'), 'wb') as fichier:
            fichier.write(cls.ETAT_AVANT)
        with open(os.path.join(dossier_donnees, 'parametres.csv'), 'wb') as fichier:
            fichier.write(cls.PARAMETRES)

    def test_sauvegarde_quotidienne_contient_etat_avant(self):
        # T187 (D170) : la sauvegarde du jour est faite au démarrage du serveur, donc avant toute écriture, avec son
        # manifeste ; ni une lecture ni les écritures du même jour ne la refont.
        aujourd_hui = datetime.date.today().strftime('%Y-%m-%d')
        dossier_du_jour = self.chemin_donnee('sauvegardes', aujourd_hui)
        self.assertEqual(sorted(os.listdir(dossier_du_jour)), ['manifeste.json', 'parametres.csv', 'techniciens.csv'])
        self.requete('GET', '/api/versions')
        version = empreinte(self.ETAT_AVANT)
        etat_apres = BOM + entete('techniciens') + b'\r\nTEC-0001;Apres\r\n'
        self.assertEqual(self.mettre_csv('techniciens', etat_apres, version).statut, 200)
        self.assertEqual(sorted(os.listdir(dossier_du_jour)), ['manifeste.json', 'parametres.csv', 'techniciens.csv'])
        self.assertEqual(self.lire_fichier(os.path.join(dossier_du_jour, 'techniciens.csv')),
                         self.ETAT_AVANT)
        # Deuxième écriture du jour : la sauvegarde du jour n'est pas refaite.
        self.mettre_csv('techniciens', etat_apres + b'TEC-0002;X\r\n', empreinte(etat_apres))
        self.assertEqual(self.lire_fichier(os.path.join(dossier_du_jour, 'techniciens.csv')),
                         self.ETAT_AVANT)
        liste = self.requete('GET', '/api/sauvegardes').json()['sauvegardes']
        self.assertEqual([s for s in liste if '_' not in s['nom']],
                         [{'nom': aujourd_hui, 'tables': ['techniciens', 'parametres']}])
        # La seule autre : « avant-mise-a-jour », faite au premier démarrage (aucune version de Prévo notée).
        self.assertEqual([s['nom'][len('AAAA-MM-JJ_HHMMSS_'):] for s in liste if '_' in s['nom']],
                         ['avant-mise-a-jour'])
        self.assertEqual(self.fichiers_temporaires_restants(), [])

    def test_sauvegarde_incomplete_du_mode_dossier_ignoree(self):
        # Une sauvegarde laissée avec la marque « .en-cours » (mode dossier interrompu) n'est ni
        # listée ni restaurable.
        nom = '2020-01-02'
        dossier = self.chemin_donnee('sauvegardes', nom)
        os.makedirs(dossier)
        with open(os.path.join(dossier, 'techniciens.csv'), 'wb') as fichier:
            fichier.write(self.ETAT_AVANT)
        with open(os.path.join(dossier, '.en-cours'), 'wb') as fichier:
            fichier.write(b'')
        try:
            noms = [s['nom'] for s in self.requete('GET', '/api/sauvegardes').json()['sauvegardes']]
            self.assertNotIn(nom, noms)
            reponse = self.requete('POST', '/api/restauration',
                                   json.dumps({'sauvegarde': nom}).encode('utf-8'))
            self.assertEqual(reponse.statut, 404)
        finally:
            # Le dossier de données est partagé par la classe : ne rien laisser derrière soi.
            shutil.rmtree(dossier, ignore_errors=True)


# ---------------------------------------------------------------------------
# Option --servir-tests : tests/fixtures/ servi en plus, et rien d'autre de tests/
# ---------------------------------------------------------------------------

class TestListeBlancheServirTests(CasAvecServeur):

    OPTIONS_SERVEUR = ('--servir-tests',)

    def test_liste_blanche_servir_tests_sert_les_fixtures(self):
        self.verifier_servi('/tests/fixtures/page-vide.html', 'tests/fixtures/page-vide.html',
                            'text/html; charset=utf-8')
        self.verifier_servi('/tests/fixtures/excel/source.csv', 'tests/fixtures/excel/source.csv',
                            'text/csv; charset=utf-8')
        # L'application reste servie normalement.
        self.verifier_servi('/', 'index.html', 'text/html; charset=utf-8')

    def test_liste_blanche_servir_tests_rien_d_autre_de_tests(self):
        for chemin in ('/tests/commun.py', '/tests/test_serveur.py', '/tests/fixtures',
                       '/tests/fixturesx/page-vide.html', '/tests', '/serveur.py',
                       '/docs/brief-gmao.md', '/outils/generer_demo.py', '/docs/ARCHITECTURE.md'):
            with self.subTest(chemin=chemin):
                self.verifier_non_servi(chemin)
        # Remonter de tests/fixtures/ vers tests/ : refusé (traversée, §7).
        for chemin in ('/tests/fixtures/../commun.py', '/tests/fixtures/%2e%2e/commun.py',
                       '/tests/fixtures/..%2Fcommun.py'):
            with self.subTest(chemin=chemin):
                reponse = self.requete('GET', chemin)
                self.assertTrue(400 <= reponse.statut < 500, '%s → %d' % (chemin, reponse.statut))
                self.assertNotIn(b'import', reponse.corps)


# ---------------------------------------------------------------------------
# Fichier verrouillé par un autre programme (Excel)
# ---------------------------------------------------------------------------

@unittest.skipUnless(os.name == 'nt', 'le verrouillage par un handle ouvert est propre à Windows')
class TestFichierVerrouille(CasAvecServeur):

    def preparer_donnees(cls, dossier_donnees):
        os.makedirs(dossier_donnees)
        with open(os.path.join(dossier_donnees, 'achats.csv'), 'wb') as fichier:
            fichier.write(BOM + entete('achats') + b'\r\n')

    def test_fichier_ouvert_ailleurs_423(self):
        chemin = self.chemin_donnee('achats.csv')
        version = empreinte(BOM + entete('achats') + b'\r\n')
        with open(chemin, 'r+b'):              # comme Excel : le fichier reste ouvert
            debut = time.time()
            reponse = self.mettre_csv('achats', BOM + entete('achats') + b'\r\nACH-0001\r\n', version)
            duree = time.time() - debut
        self.assertEqual(reponse.statut, 423)
        # T232 : le message nomme le fichier et dit quoi faire (texte de Nicolas, le même dans le mode dossier).
        self.assertEqual(reponse.json()['erreur'], 'Le fichier « achats.csv » est ouvert dans Excel ou un autre '
                                                   'logiciel : fermez-le, puis réessayez.')
        self.assertGreaterEqual(duree, 0.2)    # 3 essais espacés de 100 ms
        self.assertEqual(self.lire_fichier(chemin), BOM + entete('achats') + b'\r\n')
        self.assertEqual(self.fichiers_temporaires_restants(), [])
        # Fichier fermé : l'écriture passe.
        reponse = self.mettre_csv('achats', BOM + entete('achats') + b'\r\nACH-0001\r\n', version)
        self.assertEqual(reponse.statut, 200)

    def test_restauration_interrompue_donne_la_copie_de_securite(self):
        sauvegarde = self.requete('POST', '/api/sauvegarde', b'').json()['sauvegarde']
        chemin = self.chemin_donnee('achats.csv')
        with open(chemin, 'r+b'):              # Excel tient le fichier pendant la restauration
            reponse = self.requete('POST', '/api/restauration',
                                   json.dumps({'sauvegarde': sauvegarde}).encode('utf-8'))
        self.assertEqual(reponse.statut, 423)
        corps = reponse.json()
        self.assertTrue(corps['copie_securite'].endswith('_avant-restauration'))
        self.assertIn(corps['copie_securite'], corps['erreur'])
        self.assertTrue(corps['erreur'].startswith('Le fichier « achats.csv » est ouvert dans Excel ou un autre '
                                                   'logiciel : fermez-le, puis réessayez. Restauration interrompue'),
                        corps['erreur'])
        self.assertTrue(os.path.isdir(self.chemin_donnee('sauvegardes', corps['copie_securite'])))


# ---------------------------------------------------------------------------
# Port occupé
# ---------------------------------------------------------------------------

class TestPortOccupe(unittest.TestCase):

    def test_port_occupe_prend_le_suivant(self):
        dossier = tempfile.mkdtemp(prefix='prevo-test-port-')
        occupant = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            occupant.bind(('0.0.0.0', 0))
            occupant.listen(1)
            port_occupe = occupant.getsockname()[1]
            serveur = ServeurLance(os.path.join(dossier, 'donnees'), port=port_occupe).demarrer()
            try:
                self.assertNotEqual(serveur.port, port_occupe)
                self.assertTrue(port_occupe < serveur.port <= port_occupe + 20)
                self.assertIn('Le port %d est occupé' % port_occupe, serveur.console())
                self.assertEqual(serveur.requete('GET', '/api/info').json()['port'], serveur.port)
            finally:
                serveur.arreter()
        finally:
            occupant.close()
            shutil.rmtree(dossier, ignore_errors=True)


# ---------------------------------------------------------------------------
# Copie de l'application dans un dossier temporaire : statique, donnees/ par défaut
# ---------------------------------------------------------------------------

class TestCopieApplication(unittest.TestCase):
    """serveur.py copié avec une fausse application : on maîtrise index.html, .git, donnees/."""

    FICHIERS = {
        'index.html': '<!doctype html><title>Prévo</title>'.encode('utf-8'),
        'css/style.css': b'body{}',
        'js/app.js': b"'use strict';",
        'favicon.svg': b'<svg xmlns="http://www.w3.org/2000/svg"/>',
        'css/polices/Sora.woff2': b'wOF2',
        'donnees/demo/equipements.csv': b'id\r\n',
        'donnees/x.csv': b'secret',
        '.git/config': b'[core]',
        '.cache': b'cache',
        # Liste blanche (§14.7) : GUIDE.html servi s'il existe ; le reste jamais.
        'GUIDE.html': b'<!doctype html><title>Guide</title>',
        'brief-gmao.md': b'# BRIEF-PRIVE',
        'outils/outil.py': b'OUTIL_PRIVE = 1',
        'tests/fixtures/page.html': b'<!doctype html><title>FIXTURE-PRIVEE</title>',
    }
    TYPES = {
        '/': 'text/html; charset=utf-8',
        '/index.html': 'text/html; charset=utf-8',
        '/css/style.css': 'text/css; charset=utf-8',
        '/js/app.js': 'text/javascript; charset=utf-8',
        '/favicon.svg': 'image/svg+xml; charset=utf-8',
        '/css/polices/Sora.woff2': 'font/woff2',
    }

    @classmethod
    def setUpClass(cls):
        cls.dossier_application = tempfile.mkdtemp(prefix='prevo-test-copie-')
        for chemin, octets in cls.FICHIERS.items():
            complet = os.path.join(cls.dossier_application, *chemin.split('/'))
            os.makedirs(os.path.dirname(complet), exist_ok=True)
            with open(complet, 'wb') as fichier:
                fichier.write(octets)
        script = os.path.join(cls.dossier_application, 'serveur.py')
        shutil.copyfile(SCRIPT_SERVEUR, script)
        cls.serveur = ServeurLance(None, script=script).demarrer()     # sans --donnees

    @classmethod
    def tearDownClass(cls):
        cls.serveur.arreter()
        shutil.rmtree(cls.dossier_application, ignore_errors=True)

    def test_statique_types_mime_et_index(self):
        for chemin, type_attendu in self.TYPES.items():
            with self.subTest(chemin=chemin):
                reponse = self.serveur.requete('GET', chemin)
                self.assertEqual(reponse.statut, 200)
                self.assertEqual(reponse.entetes['content-type'], type_attendu)
                self.assertEqual(reponse.entetes['cache-control'], 'no-cache')
        self.assertEqual(self.serveur.requete('GET', '/').corps, self.FICHIERS['index.html'])
        self.assertEqual(self.serveur.requete('GET', '/index.html?v=2').statut, 200)

    def test_traversee_donnees_et_fichiers_caches_refuses(self):
        for chemin in ('/donnees/x.csv', '/donnees/demo/equipements.csv', '/Donnees/x.csv',
                       '/donnees%2Fx.csv', '/donnees./x.csv', '/donnees%20/x.csv',
                       '/.git/config', '/%2egit/config', '/.cache', '/css/../donnees/x.csv',
                       '/css/%2e%2e/donnees/x.csv', '/donnees', '/donnees/', '/css/', '/css'):
            with self.subTest(chemin=chemin):
                reponse = self.serveur.requete('GET', chemin)
                self.assertTrue(400 <= reponse.statut < 500, '%s → %d' % (chemin, reponse.statut))
                self.assertNotIn(b'secret', reponse.corps)
                self.assertNotIn(b'[core]', reponse.corps)

    def test_liste_blanche_guide_html_servi_s_il_existe(self):
        reponse = self.serveur.requete('GET', '/GUIDE.html')
        self.assertEqual(reponse.statut, 200)
        self.assertEqual(reponse.corps, self.FICHIERS['GUIDE.html'])
        self.assertEqual(reponse.entetes['content-type'], 'text/html; charset=utf-8')

    def test_liste_blanche_copie_hors_liste_non_servie(self):
        # Sans --servir-tests : tests/fixtures/ n'est pas servi non plus.
        for chemin, marque in (('/brief-gmao.md', b'BRIEF-PRIVE'), ('/outils/outil.py', b'OUTIL_PRIVE'),
                               ('/tests/fixtures/page.html', b'FIXTURE-PRIVEE'),
                               ('/serveur.py', b'VERROU_ECRITURE')):
            with self.subTest(chemin=chemin):
                reponse = self.serveur.requete('GET', chemin)
                self.assertEqual(reponse.statut, 404)
                self.assertNotIn(marque, reponse.corps)

    @unittest.skipUnless(os.name == 'nt', 'jonction de dossiers : propre à Windows')
    def test_liste_blanche_jonction_vers_un_dossier_non_public(self):
        """Une jonction rangée dans js/ et qui mène à outils/ ne donne pas accès à outils/ :
        la liste blanche est recontrôlée sur le chemin résolu."""
        try:
            import _winapi
            creer_jonction = _winapi.CreateJunction
        except (ImportError, AttributeError):
            self.skipTest('_winapi.CreateJunction indisponible')
        jonction = os.path.join(self.dossier_application, 'js', 'raccourci')
        creer_jonction(os.path.join(self.dossier_application, 'outils'), jonction)
        try:
            self.assertTrue(os.path.isfile(os.path.join(jonction, 'outil.py')))
            reponse = self.serveur.requete('GET', '/js/raccourci/outil.py')
            self.assertEqual(reponse.statut, 404)
            self.assertNotIn(b'OUTIL_PRIVE', reponse.corps)
        finally:
            os.rmdir(jonction)          # supprime la jonction, jamais le dossier visé

    def test_dossier_donnees_par_defaut(self):
        donnees = os.path.join(self.dossier_application, 'donnees')
        self.assertTrue(os.path.isdir(os.path.join(donnees, 'documents')))
        self.assertTrue(os.path.isdir(os.path.join(donnees, 'sauvegardes')))
        reponse = self.serveur.requete('PUT', '/api/csv/equipements', BOM + entete('equipements') + b'\r\n',
                                       {'X-Version-Attendue': 'aucune'})
        self.assertEqual(reponse.statut, 200)
        self.assertTrue(os.path.isfile(os.path.join(donnees, 'equipements.csv')))


# ---------------------------------------------------------------------------
# Code source : compatibilité Python 3.8 et cohérence avec js/schema.js
# ---------------------------------------------------------------------------

class TestCodeSource(unittest.TestCase):

    def setUp(self):
        with open(SCRIPT_SERVEUR, encoding='utf-8') as fichier:
            self.source = fichier.read()

    def test_compatibilite_python_38(self):
        ast.parse(self.source, filename='serveur.py', feature_version=(3, 8))
        self.assertNotIn('removeprefix', self.source)
        self.assertNotIn('removesuffix', self.source)

    def test_bibliotheque_standard_seulement(self):
        modules = set()
        for noeud in ast.walk(ast.parse(self.source)):
            if isinstance(noeud, ast.Import):
                modules |= {alias.name.split('.')[0] for alias in noeud.names}
            elif isinstance(noeud, ast.ImportFrom):
                modules.add(noeud.module.split('.')[0])
        if hasattr(sys, 'stdlib_module_names'):
            self.assertEqual(modules - set(sys.stdlib_module_names), set())

    def test_24_tables_et_renvoi_vers_schema_js(self):
        self.assertEqual(len(TABLES), 24)
        self.assertEqual(len(set(TABLES)), 24)
        self.assertIn('js/schema.js', self.source)

    def test_tables_coherentes_avec_schema_js(self):
        chemin_schema = os.path.join(DOSSIER_PROJET, 'js', 'schema.js')
        if not os.path.isfile(chemin_schema):
            self.skipTest('js/schema.js absent')
        with open(chemin_schema, encoding='utf-8') as fichier:
            tables_schema = re.findall(r"fichier:\s*'([a-z_]+)\.csv'", fichier.read())
        if not tables_schema:
            self.skipTest('aucune table trouvée dans js/schema.js')
        self.assertEqual(tables_schema, TABLES)


if __name__ == '__main__':
    unittest.main()
