"""Outil de fabrication du wiki de démo (lot 6 refondu, tâche T121 ; ARCHITECTURE.md §20.10 ; D98, D112 ; CS105, CS111).

Toujours avec un faux `claude` (tests/fixtures/wiki/faux_claude.py), jamais un vrai modèle :
    fabrication : tous les OT clôturés administrativement de la démo, 5 agents ; une trace par OT ; chaque agent reçoit
                  la requête de Prévo octet pour octet (message système en --system-prompt, message utilisateur sur
                  l'entrée standard) avec les options d'un agent sans outil ; propositions validées sauf celles des
                  14 derniers jours d'intervention ; intégrité ok ;
    reprise     : une requête identique à l'octet reprend la réponse de la trace, sans nouvel appel ;
    arrêts      : modèle autre que Sonnet, plus d'un tour, réponse en erreur, réponse refusée par Prévo ;
    figer       : les fichiers figés repris par le générateur donnent une démo identique à l'octet d'une génération
                  à l'autre ; vérification (traces, une entrée par OT, intégrité) ; page de relecture par type ; un
                  fichier figé qui cite un OT inexistant arrête le générateur ;
    À propos    : mention « construit par Claude (<modèle>) avec la consigne de Prévo, un agent par OT ».

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_wiki_demo.py" -v
"""
import csv
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from commun import CasNavigateur, attendre_pret, preregler_profil, url_fichier

RACINE = Path(__file__).resolve().parent.parent
OUTIL = RACINE / 'outils' / 'wiki_demo.py'
GENERATEUR = RACINE / 'outils' / 'generer_demo.py'
FAUX = RACINE / 'tests' / 'fixtures' / 'wiki' / 'faux_claude.py'
DEMO = RACINE / 'donnees' / 'demo'
OPTIONS_AGENT = ['-p', '--model', 'sonnet', '--tools', '', '--system-prompt', None, '--setting-sources', '',
                 '--strict-mcp-config', '--no-session-persistence', '--disable-slash-commands', '--output-format', 'json']


def lancer(script, arguments, environnement=None, delai=900):
    env = dict(os.environ, **(environnement or {}))
    return subprocess.run([sys.executable, '-X', 'utf8', str(script)] + [str(a) for a in arguments], cwd=str(RACINE),
                          capture_output=True, text=True, encoding='utf-8', env=env, timeout=delai)


def lignes_csv(chemin):
    lignes = list(csv.reader(io.StringIO(Path(chemin).read_bytes().decode('utf-8-sig'), newline=''), delimiter=';'))
    return [dict(zip(lignes[0], ligne)) for ligne in lignes[1:]]


def wiki_de(resultat):
    """Pages (titre → texte, type, OT cités) et propositions (OT → statut, changements) d'un résultat."""
    pages = {p['titre']: (p['texte'], p['type'], p['ot_cites']) for p in lignes_csv(Path(resultat) / 'wiki_pages.csv')}
    propositions = {e['ot_id']: (e['statut'], [(c['titre'], c['apres']) for c in json.loads(e['changements'] or '[]')])
                    for e in lignes_csv(Path(resultat) / 'wiki_journal.csv')}
    return pages, propositions


class TestFabrication(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.dossier = Path(tempfile.mkdtemp(prefix='prevo-wiki-demo-'))
        cls.addClassCleanup(shutil.rmtree, cls.dossier, True)
        cls.traces = cls.dossier / 'chaine'
        cls.appels = cls.dossier / 'appels'
        cls.resultat = cls.dossier / 'resultat'
        cls.sortie = lancer(OUTIL, ['fabriquer', '--agents', 5, '--claude', FAUX, '--traces', cls.traces,
                                    '--resultat', cls.resultat], {'FAUX_CLAUDE_TRACES': str(cls.appels)})

    def test_fabrication_complete(self):
        self.assertEqual(self.sortie.returncode, 0, self.sortie.stdout + self.sortie.stderr)
        self.assertIn('Intégrité ok.', self.sortie.stdout)
        ordres = lignes_csv(DEMO / 'ordres_travail.csv')
        clotures = {o['id']: o for o in ordres if o['statut'] == 'Clôturé administrativement'}
        self.assertGreater(len(clotures), 200)
        self.assertEqual(sorted(p.stem for p in self.traces.glob('*.json')), sorted(clotures))
        journal = lignes_csv(self.resultat / 'wiki_journal.csv')
        self.assertEqual(sorted(e['ot_id'] for e in journal if e['nature'] == 'ingestion'), sorted(clotures))
        self.assertEqual({e['modele'] for e in journal}, {'claude-sonnet-5-5'})
        # Les 14 derniers jours d'intervention restent « à valider » (dont la PO-02 du scénario), le reste est validé.
        for entree in journal:
            recent = clotures[entree['ot_id']]['date_fin'][:10] > '2026-10-05'
            self.assertEqual(entree['statut'], 'à valider' if recent else 'validée', entree['ot_id'])
        self.assertEqual({e['ot_id']: e['statut'] for e in journal if e['ot_id'] in ('OT-2026-0213', 'OT-2026-0214')},
                         {'OT-2026-0213': 'validée', 'OT-2026-0214': 'à valider'})
        # Horloge arrêtée à la date de référence : les dates écrites par Prévo sont celles du jour de référence.
        self.assertEqual({e['traite_le'][:10] for e in journal}, {'2026-10-19'})
        pages = lignes_csv(self.resultat / 'wiki_pages.csv')
        self.assertGreater(len(pages), 50)
        self.assertEqual({p['valide_par'] for p in pages}, {'Responsable'})

    def test_requete_octet_pour_octet_et_options_d_un_agent_sans_outil(self):
        recus = [json.loads(p.read_text(encoding='utf-8')) for p in self.appels.glob('*.json')]
        traces = {p.stem: json.loads(p.read_text(encoding='utf-8')) for p in self.traces.glob('*.json')}
        envoyes = [a for t in traces.values() for a in t['appels'] if not a['reprise']]
        self.assertEqual(len(recus), len(envoyes))
        par_systeme_entree = {(a['systeme'], a['utilisateur']) for a in envoyes}
        for recu in recus:
            arguments = recu['arguments']
            attendu = list(OPTIONS_AGENT)
            attendu[attendu.index(None)] = arguments[6]
            self.assertEqual(arguments, attendu)
            self.assertIn((arguments[6], recu['entree']), par_systeme_entree)
        # Ce qui est tracé est la requête de Prévo : premier mot du système, OT de l'entrée.
        for ot, trace in traces.items():
            appel = trace['appels'][0]
            self.assertTrue(appel['systeme'].startswith('Fonction : ingestionWiki'), ot)
            self.assertIn('OT à intégrer : ' + ot + ' ·', appel['utilisateur'])
            self.assertEqual((appel['modele'], appel['tours']), ('claude-sonnet-5-5', 1))
            self.assertTrue(appel['reponse_brute'] and appel['contenu'] and appel['empreinte'])
            self.assertIn('cout_usd', appel)

    def test_reprise_sans_nouvel_appel(self):
        # Un seul agent : les requêtes d'une fabrication à l'autre sont identiques à l'octet (avec plusieurs agents,
        # le catalogue d'une requête dépend des OT déjà finis ailleurs : elle est alors renvoyée).
        traces, appels = self.dossier / 'chaine-1', self.dossier / 'appels-1'
        resultats = []
        for numero in (1, 2):
            resultat = self.dossier / ('resultat-1-agent-%d' % numero)
            sortie = lancer(OUTIL, ['fabriquer', '--agents', 1, '--limite', 40, '--claude', FAUX, '--traces', traces,
                                    '--resultat', resultat], {'FAUX_CLAUDE_TRACES': str(appels)})
            self.assertEqual(sortie.returncode, 0, sortie.stdout + sortie.stderr)
            resultats.append((sortie.stdout, resultat))
        self.assertIn('Agents lancés : 40 · réponses reprises des traces : 0', resultats[0][0])
        self.assertIn('Agents lancés : 0 · réponses reprises des traces : 40', resultats[1][0])
        self.assertEqual(len(list(appels.glob('*.json'))), 40)
        self.assertEqual(wiki_de(resultats[1][1]), wiki_de(resultats[0][1]))
        self.assertEqual((resultats[1][1] / 'wiki_pages.csv').read_bytes(), (resultats[0][1] / 'wiki_pages.csv').read_bytes())
        trace = json.loads(next(traces.glob('*.json')).read_text(encoding='utf-8'))
        self.assertEqual([a['reprise'] for a in trace['appels']], [False, True])

    def test_figer_generer_verifier_et_relecture(self):
        fige = self.dossier / 'fige'
        sortie = lancer(OUTIL, ['figer', '--resultat', self.resultat, '--wiki', fige])
        self.assertEqual(sortie.returncode, 0, sortie.stdout + sortie.stderr)
        generations = []
        for numero in (1, 2):
            cible = self.dossier / ('generation-%d' % numero)
            sortie = lancer(GENERATEUR, ['--wiki', fige, '--sortie', cible / 'csv', '--fichier-js', cible / 'demo.js',
                                         '--fichier-scenarios', cible / 'scenarios.json'])
            self.assertEqual(sortie.returncode, 0, sortie.stdout + sortie.stderr)
            generations.append({p.relative_to(cible).as_posix(): p.read_bytes() for p in cible.rglob('*') if p.is_file()})
        self.assertEqual(generations[0], generations[1])                       # identique à l'octet
        csv_demo = self.dossier / 'generation-1' / 'csv'
        for table, nom in (('wiki_pages', 'demo_wiki_pages.csv'), ('wiki_journal', 'demo_wiki_journal.csv')):
            self.assertEqual(lignes_csv(csv_demo / (table + '.csv')), lignes_csv(fige / nom), table)
        self.assertIn('wiki_journal: "id;nature;ot_id', generations[0]['demo.js'].decode('utf-8'))
        # Le reste de la démo ne bouge pas.
        for fichier in DEMO.glob('*.csv'):
            if not fichier.stem.startswith('wiki_'):
                self.assertEqual((csv_demo / fichier.name).read_bytes(), fichier.read_bytes(), fichier.name)
        sortie = lancer(OUTIL, ['verifier', '--demo', csv_demo, '--wiki', fige, '--traces', self.traces])
        self.assertEqual(sortie.returncode, 0, sortie.stdout + sortie.stderr)
        self.assertIn('Vérification : OK', sortie.stdout)
        relecture = self.dossier / 'relecture.html'
        sortie = lancer(OUTIL, ['relecture', '--demo', csv_demo, '--sortie', relecture])
        self.assertEqual(sortie.returncode, 0, sortie.stdout + sortie.stderr)
        texte = relecture.read_text(encoding='utf-8')
        positions = [texte.index('<h2>' + titre) for titre in ('Équipements', 'Composants', 'Modes de défaillance', 'Savoir-faire')]
        self.assertEqual(positions, sorted(positions))
        # Les plus riches d'abord, dans chaque type (nombre d'OT cités).
        import re
        section = texte[positions[0]:positions[1]]
        nombres = [int(n) for n in re.findall(r'<small>équipement · (\d+) OT', section)]
        self.assertGreater(len(nombres), 5)
        self.assertEqual(nombres, sorted(nombres, reverse=True))
        # Vérification en échec : une entrée du journal figé retirée.
        abime = self.dossier / 'fige-abime'
        shutil.copytree(fige, abime)
        lignes = (abime / 'demo_wiki_journal.csv').read_bytes().decode('utf-8').split('\r\n')
        (abime / 'demo_wiki_journal.csv').write_bytes('\r\n'.join(lignes[:1] + lignes[2:]).encode('utf-8'))
        sortie = lancer(OUTIL, ['verifier', '--demo', csv_demo, '--wiki', abime, '--traces', self.traces])
        self.assertEqual(sortie.returncode, 1)
        self.assertIn('OT sans entrée au journal figé', sortie.stdout)

    def test_generateur_refuse_un_wiki_fige_incoherent(self):
        fige = self.dossier / 'fige-incoherent'
        lancer(OUTIL, ['figer', '--resultat', self.resultat, '--wiki', fige])
        lignes = list(csv.reader(io.StringIO((fige / 'demo_wiki_pages.csv').read_bytes().decode('utf-8-sig'), newline=''),
                                 delimiter=';'))
        colonne = lignes[0].index('ot_cites')
        lignes[1][colonne] = 'OT-2099-0001;' + lignes[1][colonne]
        sortie_csv = io.StringIO()
        csv.writer(sortie_csv, delimiter=';', lineterminator='\r\n').writerows(lignes)
        (fige / 'demo_wiki_pages.csv').write_bytes(sortie_csv.getvalue().encode('utf-8'))
        sortie = lancer(GENERATEUR, ['--wiki', fige, '--sortie', self.dossier / 'incoherent', '--sans-js'])
        self.assertEqual(sortie.returncode, 1)
        self.assertIn('OT cité inexistant OT-2099-0001', sortie.stderr)


class TestArrets(unittest.TestCase):

    def arreter(self, mode, attendu):
        dossier = Path(tempfile.mkdtemp(prefix='prevo-wiki-arret-'))
        self.addCleanup(shutil.rmtree, dossier, True)
        sortie = lancer(OUTIL, ['fabriquer', '--agents', 2, '--limite', 3, '--claude', FAUX, '--traces', dossier / 'chaine',
                                '--resultat', dossier / 'resultat'], {'FAUX_CLAUDE_MODE': mode})
        self.assertEqual(sortie.returncode, 1, sortie.stdout + sortie.stderr)
        self.assertIn(attendu, sortie.stdout)
        self.assertFalse((dossier / 'resultat').exists())
        return sortie.stdout

    def test_modele_autre_que_sonnet(self):
        self.arreter('opus', 'modèle autre que Sonnet : claude-opus-5-5')

    def test_plus_d_un_tour(self):
        self.arreter('deux-tours', '2 tours au lieu d\'un seul')

    def test_reponse_en_erreur(self):
        self.arreter('erreur', 'réponse en erreur')

    def test_reponse_refusee_par_prevo(self):
        sortie = self.arreter('refus', 'ARRÊT : réponse refusée par les contrôles de Prévo')
        self.assertIn('OT cité hors des OT permis : OT-1999-9999', sortie)


class TestAPropos(CasNavigateur):

    def test_mention_du_wiki_de_demo(self):
        preregler_profil(self.contexte, 'responsable')
        self.page.goto(url_fichier('index.html'))
        self.page.click('#btn-demo')
        attendre_pret(self.page)
        self.page.evaluate("""() => Donnees.modifier('wiki_journal', (lignes) => { lignes.push({ id: 'WJ-00001',
          nature: 'ingestion', ot_id: '', statut: 'validée', modele: 'claude-sonnet-5-5' }); }, { journal: false })""")
        self.page.goto(url_fichier('index.html') + '#/apropos')
        self.page.wait_for_selector('.apropos-liste')
        texte = ' '.join(self.page.inner_text('#contenu').split())
        self.assertIn("Son wiki de maintenance a été construit par Claude (claude-sonnet-5-5) avec la consigne de Prévo, "
                      "un agent par OT, dans l'ordre des interventions ; la démo n'appelle aucune IA.", texte)


if __name__ == '__main__':
    unittest.main()
