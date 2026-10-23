"""Outil de fabrication du wiki de démo (lot 6 refondu, tâche T121 ; ARCHITECTURE.md §20.10 ; D98, D112 ; CS105, CS111).

Toujours avec un faux `claude` (tests/fixtures/wiki/faux_claude.py), jamais un vrai modèle :
    fabrication : tous les OT clôturés administrativement de la démo, 5 agents ; une trace par OT ; chaque agent reçoit
                  la requête de Prévo octet pour octet (message système en --system-prompt, message utilisateur sur
                  l'entrée standard) avec les options d'un agent sans outil ; propositions validées sauf celles des
                  14 derniers jours d'intervention ; intégrité ok ;
    reprise     : une requête identique à l'octet reprend la réponse de la trace, sans nouvel appel (relance comprise) ;
    relance     : (D106 révisée, §20.10) une réponse refusée par Prévo est relancée avec la raison : un agent neuf
                  de plus, dans la même trace, et la fabrication continue ; une relance refusée l'arrête ;
    arrêts      : modèle autre que Sonnet, plus d'un tour, réponse en erreur, réponse refusée par Prévo deux fois ;
    deux temps  : (D115) --limite N garde l'état de départ de la suite (avant validations), temps-1.json (OT,
                  empreintes, bilan, coût) et sa page de relecture ; --suite donne le même wiki à l'octet qu'une
                  fabrication d'un seul tenant, sans aucun appel pour les N premiers, dans le même ordre ; refusée sans
                  temps 1, sur d'autres données de démo, avec une autre consigne, ou avec --limite ;
    figer       : les fichiers figés repris par le générateur donnent une démo identique à l'octet d'une génération
                  à l'autre ; vérification (traces, une entrée par OT reliée à la réponse acceptée — relance
                  comprise —, intégrité) ; page de relecture par type (refonte 2 : machines, articles, savoir-faire ;
                  chaque texte avec ses OT et leurs relances) ; un fichier figé qui cite un OT inexistant arrête le
                  générateur ;
    À propos    : mention « construit par Claude (<modèle>) avec la consigne de Prévo, un agent par OT ».

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_wiki_demo.py" -v
"""
import asyncio
import csv
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
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
MARQUE_RELANCE = '\n\nTa réponse précédente :\n'
REFUS_SANS_OT = 'phrase sans OT cité'          # premier refus du faux claude en mode « relance »


def charger_outil():
    """Module outils/wiki_demo.py, pour essayer une fonction seule."""
    spec = importlib.util.spec_from_file_location('wiki_demo_essai', OUTIL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
        # Un OT du milieu de l'historique est refusé une fois par Prévo, puis accepté à la relance avec la raison.
        clotures = sorted((o['date_fin'], o['id']) for o in lignes_csv(DEMO / 'ordres_travail.csv')
                          if o['statut'] == 'Clôturé administrativement')
        cls.relance = clotures[len(clotures) // 2][1]
        # Lancée comme depuis une session Claude Code : ses variables ne doivent pas passer aux agents.
        cls.sortie = lancer(OUTIL, ['fabriquer', '--agents', 5, '--claude', FAUX, '--traces', cls.traces,
                                    '--resultat', cls.resultat], {'FAUX_CLAUDE_TRACES': str(cls.appels),
                                                                  'FAUX_CLAUDE_MODE': 'relance', 'FAUX_CLAUDE_RELANCE': cls.relance,
                                                                  'CLAUDECODE': '1', 'CLAUDE_CODE_SESSION_ID': 'session-de-test',
                                                                  'ANTHROPIC_BASE_URL': 'http://127.0.0.1:9'})

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

    def test_relance_avec_la_raison_un_agent_de_plus_dans_la_meme_trace(self):
        """§20.10 : la réponse refusée par Prévo est relancée avec la raison (un agent neuf de plus, même trace) ; la
        fabrication continue ; l'entrée garde les raisons du premier refus et compte deux essais."""
        self.assertEqual(self.sortie.returncode, 0, self.sortie.stdout + self.sortie.stderr)
        self.assertIn('relances avec la raison : 1 ·', self.sortie.stdout)
        self.assertIn('Acceptées à la relance avec la raison : ' + self.relance + '\n', self.sortie.stdout)
        traces = {p.stem: json.loads(p.read_text(encoding='utf-8')) for p in self.traces.glob('*.json')}
        origine, relance = traces[self.relance]['appels']
        self.assertEqual((origine['reprise'], origine['relance'], relance['reprise'], relance['relance']), (False, False, False, True))
        self.assertEqual(relance['systeme'], origine['systeme'])
        self.assertTrue(relance['utilisateur'].startswith(origine['utilisateur'] + MARQUE_RELANCE + origine['contenu'] + '\n\n'))
        self.assertIn(REFUS_SANS_OT, relance['utilisateur'])
        for appel in (origine, relance):
            self.assertEqual((appel['modele'], appel['tours']), ('claude-sonnet-5-5', 1))
        # Aucune autre relance : un seul appel par OT, jamais une requête de relance.
        autres = [a for ot, t in traces.items() if ot != self.relance for a in t['appels']]
        self.assertEqual(len(autres), len(traces) - 1)
        self.assertFalse(any(a['relance'] or MARQUE_RELANCE in a['utilisateur'] for a in autres))
        entree = next(e for e in lignes_csv(self.resultat / 'wiki_journal.csv') if e['ot_id'] == self.relance)
        self.assertEqual((entree['statut'], entree['essais'], entree['modele']), ('validée', '2', 'claude-sonnet-5-5'))
        self.assertIn(REFUS_SANS_OT, entree['raisons'])
        self.assertEqual(traces[self.relance]['verdict']['statut'], 'validée')

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
            # Verdict de Prévo gardé dans la trace (CS105).
            self.assertIn(trace['verdict']['statut'], ('validée', 'à valider'), ot)
        # Environnement de chaque agent : sans les variables de la session qui lance, CLAUDE.md et mémoire désactivés,
        # jamais de mise à jour de Claude Code (elle retirerait claude.exe aux autres agents).
        for recu in recus:
            env = recu['environnement']
            self.assertNotIn('CLAUDECODE', env)
            self.assertNotIn('CLAUDE_CODE_SESSION_ID', env)
            self.assertNotIn('ANTHROPIC_BASE_URL', env)
            self.assertEqual((env.get('CLAUDE_CODE_DISABLE_CLAUDE_MDS'), env.get('CLAUDE_CODE_DISABLE_AUTO_MEMORY'),
                              env.get('DISABLE_AUTOUPDATER')), ('1', '1', '1'))

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

    def test_reprise_rendue_apres_sa_duree_d_origine(self):
        """Une réponse reprise est rendue après sa durée d'origine (--reprise-duree 1) : deux réponses demandées ensemble
        reviennent dans l'ordre de leurs durées, comme à l'origine ; avec --reprise-duree 0, tout de suite ; --reprise-seule
        n'appelle jamais d'agent pour une requête absente des traces. Essai sans minutage serré (0,2 s contre 1,2 s) : le
        rejeu de bout en bout à cinq agents dépend de la charge de la machine (deux réponses à quelques millisecondes
        peuvent s'inverser) et n'est pas testé ici ; la fabrication en deux temps repart du résultat du premier temps."""
        module = charger_outil()
        traces = self.dossier / 'reprise-duree'
        traces.mkdir()
        systeme = 'Fonction : ingestionWiki\nessai'
        requetes = {}
        for ot, duree in (('OT-2026-9001', 1.2), ('OT-2026-9002', 0.2)):
            utilisateur = 'OT à intégrer : %s · essai' % ot
            requetes[ot] = {'messages': [{'role': 'system', 'content': systeme}, {'role': 'user', 'content': utilisateur}]}
            module.ecrire_trace(traces, {'ot': ot, 'appels': [{
                'empreinte': module.empreinte(systeme, utilisateur), 'reprise': False, 'contenu': '{"rien_a_ajouter": true}',
                'modele': 'claude-sonnet-5-5', 'tours': 1, 'duree_s': duree}]})

        async def ordre_de_retour(fabrique):
            rendus = []

            async def un(ot):
                await fabrique.appeler(requetes[ot], ot)
                rendus.append(ot)
            debut = time.time()
            await asyncio.gather(un('OT-2026-9001'), un('OT-2026-9002'))
            return rendus, time.time() - debut

        rendus, duree = asyncio.run(ordre_de_retour(module.Fabrique([sys.executable], traces, reprise_duree=1.0)))
        self.assertEqual(rendus, ['OT-2026-9002', 'OT-2026-9001'])
        self.assertGreater(duree, 1.1)
        rendus, duree = asyncio.run(ordre_de_retour(module.Fabrique([sys.executable], traces, reprise_duree=0)))
        self.assertLess(duree, 0.5)
        absente = {'messages': [{'role': 'system', 'content': systeme}, {'role': 'user', 'content': 'OT à intégrer : OT-2026-9003'}]}
        fabrique = module.Fabrique([str(self.dossier / 'jamais-lance.exe')], traces, reprise_seule=True)
        with self.assertRaises(module.ErreurFabrication) as erreur:
            asyncio.run(fabrique.appeler(absente, 'OT-2026-9003'))
        self.assertIn('requête absente des traces (reprise seule : aucun agent lancé)', str(erreur.exception))
        self.assertEqual(fabrique.appels, 0)

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
        # Le journal (textes d'avant et d'après de chaque changement) est écrit par morceaux dans js/demo-donnees.js
        # (§20.10 ; recollés au chargement : test_demo le vérifie dans Chromium).
        self.assertIn("\n    wiki_journal: ((m, s) => s.map((r) => m[r]).join(''))([\"id;nature;ot_id;",
                      generations[0]['demo.js'].decode('utf-8'))
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
        # Refonte 2 (§20.12) : textes des machines, des articles, savoir-faire ; plus de pages de mode.
        positions = [texte.index('<h2>' + titre) for titre in ('Machines — « En bref » et « Astuces »',
                                                               'Articles — « À quoi il sert »', 'Savoir-faire')]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn('Modes de défaillance', texte)
        self.assertNotIn('<small>mode ·', texte)
        # Les plus riches d'abord, dans chaque type (nombre d'OT cités).
        section = texte[positions[0]:positions[1]]
        nombres = [int(n) for n in re.findall(r'<small>équipement · (\d+) OT', section)]
        self.assertGreater(len(nombres), 5)
        self.assertEqual(nombres, sorted(nombres, reverse=True))
        # Les propositions laissées « à valider » sont relues aussi, en tête : OT, texte proposé de chaque page.
        self.assertLess(texte.index('<h2>Propositions à valider (2)'), positions[0])
        attente = texte[texte.index('<h2>Propositions à valider'):positions[0]]
        self.assertIn('OT-2026-0214', attente)
        self.assertIn('Page modifiée', attente)
        self.assertIn('[OT-2026-0214]', attente)
        # Chaque texte avec ses OT et leurs relances : l'OT relancé avec la raison l'est sous son texte et dans la liste.
        relances = texte[texte.index('<h2>Refus, relances et rejeux (1)'):texte.index('<h2>Rien à ajouter')]
        self.assertIn('<b>%s</b>' % self.relance, relances)
        self.assertIn('Relancée avec la raison</b> (2 essais) — premier refus : ', relances)
        self.assertIn(REFUS_SANS_OT, relances)
        self.assertIn('dont 1 relancé(s) ou rejoué(s)', texte[positions[0]:])
        # Vérification en échec : une entrée du journal figé retirée.
        abime = self.dossier / 'fige-abime'
        shutil.copytree(fige, abime)
        lignes = (abime / 'demo_wiki_journal.csv').read_bytes().decode('utf-8').split('\r\n')
        (abime / 'demo_wiki_journal.csv').write_bytes('\r\n'.join(lignes[:1] + lignes[2:]).encode('utf-8'))
        sortie = lancer(OUTIL, ['verifier', '--demo', csv_demo, '--wiki', abime, '--traces', self.traces])
        self.assertEqual(sortie.returncode, 1)
        self.assertIn('OT sans entrée au journal figé', sortie.stdout)
        # Vérification en échec : l'entrée acceptée à la relance n'est plus reliée à sa réponse (relance, ou réponse
        # refusée, absente de la trace).
        for nom, garder in (('sans-relance', slice(0, 1)), ('sans-refus', slice(1, 2))):
            traces = self.dossier / ('chaine-' + nom)
            shutil.copytree(self.traces, traces)
            chemin = traces / (self.relance + '.json')
            trace = json.loads(chemin.read_text(encoding='utf-8'))
            trace['appels'] = trace['appels'][garder]
            chemin.write_text(json.dumps(trace, ensure_ascii=False), encoding='utf-8')
            sortie = lancer(OUTIL, ['verifier', '--demo', csv_demo, '--wiki', fige, '--traces', traces])
            self.assertEqual(sortie.returncode, 1, nom)
            self.assertIn('DÉFAUT : %s : acceptée à la relance' % self.relance, sortie.stdout, nom)

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
        # Une date d'intervention qui n'est pas la date de fin de l'OT arrête aussi le générateur.
        dates = self.dossier / 'fige-dates'
        lancer(OUTIL, ['figer', '--resultat', self.resultat, '--wiki', dates])
        lignes = list(csv.reader(io.StringIO((dates / 'demo_wiki_journal.csv').read_bytes().decode('utf-8-sig'), newline=''),
                                 delimiter=';'))
        lignes[1][lignes[0].index('date_intervention')] = '2001-01-01 08:00'
        sortie_csv = io.StringIO()
        csv.writer(sortie_csv, delimiter=';', lineterminator='\r\n').writerows(lignes)
        (dates / 'demo_wiki_journal.csv').write_bytes(sortie_csv.getvalue().encode('utf-8'))
        sortie = lancer(GENERATEUR, ['--wiki', dates, '--sortie', self.dossier / 'incoherent-dates', '--sans-js'])
        self.assertEqual(sortie.returncode, 1)
        self.assertIn("date d'intervention 2001-01-01 08:00", sortie.stderr)


def demo_reduite(cible, nombre):
    """Copie de la démo où seuls les `nombre` premiers OT clôturés administrativement (par date d'intervention) le
    restent ; les autres passent « Clôturé techniquement », hors de la file du wiki (essais courts). → les OT gardés,
    dans l'ordre des interventions."""
    shutil.copytree(DEMO, cible)
    texte = (cible / 'ordres_travail.csv').read_bytes().decode('utf-8-sig')
    clotures = [ot for _, ot in sorted((o['date_fin'], o['id']) for o in lignes_csv(DEMO / 'ordres_travail.csv')
                                       if o['statut'] == 'Clôturé administrativement')]
    retires = set(clotures[nombre:])
    lignes = texte.split('\r\n')
    for rang, ligne in enumerate(lignes):
        if ligne.split(';', 1)[0] in retires:
            lignes[rang] = ligne.replace(';Clôturé administrativement;', ';Clôturé techniquement;', 1)
    (cible / 'ordres_travail.csv').write_bytes(b'\xef\xbb\xbf' + '\r\n'.join(lignes).encode('utf-8'))
    gardes = [o['id'] for o in lignes_csv(cible / 'ordres_travail.csv') if o['statut'] == 'Clôturé administrativement']
    assert sorted(gardes) == sorted(clotures[:nombre]), gardes
    return clotures[:nombre]


class TestDeuxTemps(unittest.TestCase):
    """Fabrication en deux temps (D115, §20.12) : `fabriquer --limite N` (temps 1) garde l'état de départ de la suite,
    temps-1.json et sa page de relecture ; `fabriquer --suite` repart de cet état exact et ne traite que les OT restants,
    sans aucun appel pour ceux du temps 1, dans le même ordre, avec les validations d'une fabrication d'un seul tenant :
    même wiki à l'octet (un agent). Sur une démo réduite à ses 24 premiers OT clôturés administrativement."""
    GARDES, LIMITE = 24, 10

    @classmethod
    def setUpClass(cls):
        cls.dossier = d = Path(tempfile.mkdtemp(prefix='prevo-wiki-deux-temps-'))
        cls.addClassCleanup(shutil.rmtree, d, True)
        cls.demo = d / 'demo'
        cls.ordre = demo_reduite(cls.demo, cls.GARDES)
        commun = ['--agents', 1, '--claude', FAUX, '--demo', cls.demo]
        cls.seul = lancer(OUTIL, ['fabriquer'] + commun + ['--traces', d / 'chaine-seul', '--resultat', d / 'seul'])
        cls.temps_1 = lancer(OUTIL, ['fabriquer', '--limite', cls.LIMITE] + commun + ['--traces', d / 'chaine-1', '--resultat',
                                                                                      d / 'temps-1'])
        cls.traces_1 = {p.name: p.read_bytes() for p in (d / 'chaine-1').glob('*.json')}
        # La suite, avec des traces neuves : un OT du temps 1 redemandé lancerait forcément un agent.
        cls.suite = lancer(OUTIL, ['fabriquer', '--suite', '--depart', d / 'temps-1'] + commun
                           + ['--traces', d / 'chaine-2', '--resultat', d / 'suite'], {'FAUX_CLAUDE_TRACES': str(d / 'appels-suite')})

    def test_suite_meme_wiki_qu_une_fabrication_d_un_seul_tenant(self):
        for nom, sortie in (('seul', self.seul), ('temps 1', self.temps_1), ('suite', self.suite)):
            self.assertEqual(sortie.returncode, 0, nom + ' : ' + sortie.stdout + sortie.stderr)
        for table in ('wiki_pages', 'wiki_journal'):
            self.assertEqual((self.dossier / 'suite' / (table + '.csv')).read_bytes(),
                             (self.dossier / 'seul' / (table + '.csv')).read_bytes(), table)
        # La suite continue les pages du temps 1 : une page cite des OT des deux temps.
        premiers, suivants = set(self.ordre[:self.LIMITE]), set(self.ordre[self.LIMITE:])
        cites = [set(p['ot_cites'].split(';')) for p in lignes_csv(self.dossier / 'suite' / 'wiki_pages.csv')]
        self.assertTrue(any(ot & premiers and ot & suivants for ot in cites))
        # Même ordre chronologique : le rang de traitement suit la date d'intervention ; tout est validé.
        journal = sorted(lignes_csv(self.dossier / 'suite' / 'wiki_journal.csv'), key=lambda e: int(e['ordre']))
        self.assertEqual([e['ot_id'] for e in journal], self.ordre)
        self.assertEqual({e['statut'] for e in journal}, {'validée'})

    def test_aucun_appel_pour_les_ot_du_temps_1(self):
        self.assertEqual(self.suite.returncode, 0, self.suite.stdout + self.suite.stderr)
        self.assertIn('Suite du temps 1 (%s) : %d OT déjà intégrés, repris tels quels, sans nouvel appel.'
                      % (self.dossier / 'temps-1', self.LIMITE), self.suite.stdout)
        self.assertIn('OT : %d (%d mis en file)' % (self.GARDES, self.GARDES - self.LIMITE), self.suite.stdout)
        self.assertIn('Agents lancés : %d · réponses reprises des traces : 0 ·' % (self.GARDES - self.LIMITE), self.suite.stdout)
        appels = [json.loads(p.read_text(encoding='utf-8')) for p in (self.dossier / 'appels-suite').glob('*.json')]
        recus = sorted(re.search(r'OT à intégrer : (OT-\d{4}-\d{4,})', a['entree']).group(1) for a in appels)
        self.assertEqual(recus, sorted(self.ordre[self.LIMITE:]))
        self.assertEqual(sorted(p.stem for p in (self.dossier / 'chaine-2').glob('*.json')), sorted(self.ordre[self.LIMITE:]))
        # Les traces du temps 1 ne bougent pas (aucune réponse reprise, aucun verdict réécrit).
        self.assertEqual({p.name: p.read_bytes() for p in (self.dossier / 'chaine-1').glob('*.json')}, self.traces_1)

    def test_resultat_et_relecture_du_temps_1(self):
        self.assertEqual(self.temps_1.returncode, 0, self.temps_1.stdout + self.temps_1.stderr)
        dossier = self.dossier / 'temps-1'
        temps = json.loads((dossier / 'temps-1.json').read_text(encoding='utf-8'))
        self.assertEqual((temps['temps'], temps['limite'], temps['ot'], temps['agents_lances'], temps['reprises']),
                         (1, self.LIMITE, self.ordre[:self.LIMITE], self.LIMITE, 0))
        self.assertAlmostEqual(temps['cout_usd'], 0.0123 * self.LIMITE)
        self.assertEqual(len(temps['empreinte_donnees']), 64)
        # État de départ de la suite : avant les validations (propositions « à valider », aucune page validée).
        etat = lignes_csv(dossier / 'etat-avant-validation' / 'wiki_journal.csv')
        self.assertEqual(sorted(e['ot_id'] for e in etat), sorted(self.ordre[:self.LIMITE]))
        self.assertEqual({e['statut'] for e in etat}, {'à valider'})
        self.assertEqual(lignes_csv(dossier / 'etat-avant-validation' / 'wiki_pages.csv'), [])
        # Le résultat validé, et sa page de relecture (refonte 2 : machines, articles, savoir-faire ; bilan et coût).
        self.assertEqual({e['statut'] for e in lignes_csv(dossier / 'wiki_journal.csv')}, {'validée'})
        texte = (dossier / 'relecture.html').read_text(encoding='utf-8')
        self.assertIn('<h1>Wiki de démo — relecture du temps 1</h1>', texte)
        self.assertIn('Temps 1 : %d premiers OT par date d\'intervention · acceptés' % self.LIMITE, texte)
        self.assertIn('coût 0.12 $', texte)
        positions = [texte.index('<h2>' + titre) for titre in ('Machines — « En bref » et « Astuces »',
                                                               'Articles — « À quoi il sert »', 'Savoir-faire')]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn('Modes de défaillance', texte)
        for ot in self.ordre[:self.LIMITE]:
            self.assertIn('<li id="%s"><b>%s</b>' % (ot, ot), texte)
        self.assertIn('Temps 1 : ', self.temps_1.stdout)

    def test_suite_refusee_sans_temps_1_ou_sur_d_autres_donnees(self):
        d = self.dossier
        commun = ['--agents', 1, '--claude', FAUX, '--traces', d / 'chaine-refus']
        (d / 'vide').mkdir(exist_ok=True)
        sans = lancer(OUTIL, ['fabriquer', '--suite', '--depart', d / 'vide', '--demo', self.demo, '--resultat', d / 'r1'] + commun)
        self.assertEqual(sans.returncode, 1, sans.stdout)
        self.assertIn('ARRÊT : --suite : aucun résultat de temps 1 dans %s' % (d / 'vide'), sans.stdout)
        # Autres données : un compte rendu de la démo changé depuis le temps 1.
        autre = d / 'demo-changee'
        shutil.copytree(self.demo, autre)
        chemin = autre / 'ordres_travail.csv'
        texte = chemin.read_bytes().decode('utf-8')
        ancien = next(o['compte_rendu'] for o in lignes_csv(self.demo / 'ordres_travail.csv')
                      if o['compte_rendu'] and not set('"\r\n') & set(o['compte_rendu']) and texte.count(o['compte_rendu']) == 1)
        chemin.write_bytes(texte.replace(ancien, ancien + ' Relu.', 1).encode('utf-8'))
        changees = lancer(OUTIL, ['fabriquer', '--suite', '--depart', d / 'temps-1', '--demo', autre, '--resultat', d / 'r2'] + commun)
        self.assertEqual(changees.returncode, 1, changees.stdout)
        self.assertIn('fabriqué sur d\'autres données de démo que celles-ci', changees.stdout)
        # Consigne changée depuis le temps 1 (empreinte gardée différente).
        copie = d / 'temps-1-autre-consigne'
        shutil.copytree(d / 'temps-1', copie)
        temps = json.loads((copie / 'temps-1.json').read_text(encoding='utf-8'))
        temps['empreinte_consigne'] = '0' * 64
        (copie / 'temps-1.json').write_text(json.dumps(temps), encoding='utf-8')
        consigne = lancer(OUTIL, ['fabriquer', '--suite', '--depart', copie, '--demo', self.demo, '--resultat', d / 'r3'] + commun)
        self.assertEqual(consigne.returncode, 1, consigne.stdout)
        self.assertIn('la consigne (message système d\'ingestionWiki ou options d\'un agent) a changé depuis le temps 1',
                      consigne.stdout)
        for sortie in (sans, changees, consigne):
            self.assertNotIn('Agents lancés', sortie.stdout)
        self.assertFalse((d / 'chaine-refus').exists())
        for resultat in ('r1', 'r2', 'r3'):
            self.assertFalse((d / resultat / 'wiki_journal.csv').exists())
        ensemble = lancer(OUTIL, ['fabriquer', '--suite', '--limite', 5, '--demo', self.demo] + commun)
        self.assertEqual(ensemble.returncode, 2)
        self.assertIn('--suite et --limite ne vont pas ensemble', ensemble.stderr)


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
        sortie = self.arreter('refus', 'ARRÊT : réponse refusée par les contrôles de Prévo, même à sa relance avec la raison')
        self.assertIn('OT cité hors des OT permis : OT-1999-9999', sortie)

    def test_relance_refusee_arrete_et_trace_ses_deux_appels(self):
        """Refusée deux fois (à l'envoi puis à la relance avec la raison) : la fabrication s'arrête ; la trace de l'OT
        porte ses deux appels, la relance citant la réponse refusée et sa raison."""
        dossier = Path(tempfile.mkdtemp(prefix='prevo-wiki-arret-'))
        self.addCleanup(shutil.rmtree, dossier, True)
        sortie = self.lancer_petit(dossier, 'refus', ['--agents', 1])
        self.assertEqual(sortie.returncode, 1, sortie.stdout)
        self.assertIn('ARRÊT : réponse refusée par les contrôles de Prévo', sortie.stdout)
        # Une seule relance, et aucun envoi ne part après le refus : deux agents en tout (l'envoi et sa relance).
        self.assertIn('relances avec la raison : 1 ·', sortie.stdout)
        self.assertIn('Agents lancés : 2 ·', sortie.stdout)
        traces = [json.loads(p.read_text(encoding='utf-8')) for p in (dossier / 'chaine').glob('*.json')]
        refusees = [t for t in traces if (t.get('verdict') or {}).get('statut') == 'refusée']
        self.assertEqual(len(refusees), 1)
        origine, relance = refusees[0]['appels']
        self.assertEqual((origine['relance'], relance['relance']), (False, True))
        self.assertTrue(relance['utilisateur'].startswith(origine['utilisateur'] + MARQUE_RELANCE + origine['contenu']))
        self.assertIn('OT cité hors des OT permis : OT-1999-9999', relance['utilisateur'])
        self.assertIn('OT cité hors des OT permis : OT-1999-9999', refusees[0]['verdict']['raisons'])

    def test_relance_acceptee_reprise_par_empreinte(self):
        """Chaque OT refusé une fois puis accepté à la relance : la fabrication réussit ; une seconde fabrication
        reprend des traces la réponse refusée et la réponse à la relance (requêtes identiques à l'octet)."""
        dossier = Path(tempfile.mkdtemp(prefix='prevo-wiki-relance-'))
        self.addCleanup(shutil.rmtree, dossier, True)
        sorties = []
        for numero in (1, 2):
            sortie = lancer(OUTIL, ['fabriquer', '--agents', 1, '--limite', 3, '--claude', FAUX, '--traces', dossier / 'chaine',
                                    '--resultat', dossier / ('resultat-%d' % numero)], {'FAUX_CLAUDE_MODE': 'relance'})
            self.assertEqual(sortie.returncode, 0, sortie.stdout + sortie.stderr)
            sorties.append(sortie.stdout)
        self.assertIn('Agents lancés : 6 · réponses reprises des traces : 0 · relances avec la raison : 3 ·', sorties[0])
        self.assertIn('Agents lancés : 0 · réponses reprises des traces : 6 · relances avec la raison : 3 ·', sorties[1])
        self.assertEqual(wiki_de(dossier / 'resultat-2'), wiki_de(dossier / 'resultat-1'))
        for chemin in (dossier / 'chaine').glob('*.json'):
            appels = json.loads(chemin.read_text(encoding='utf-8'))['appels']
            self.assertEqual([(a['reprise'], a['relance']) for a in appels],
                             [(False, False), (False, True), (True, False), (True, True)], chemin.stem)
        journal = lignes_csv(dossier / 'resultat-2' / 'wiki_journal.csv')
        self.assertEqual(len(journal), 3)
        for entree in journal:
            self.assertEqual(entree['essais'], '2', entree['ot_id'])
            self.assertIn(REFUS_SANS_OT, entree['raisons'])

    def lancer_petit(self, dossier, mode='sonnet', options=()):
        return lancer(OUTIL, ['fabriquer', '--agents', 2, '--limite', 3, '--claude', FAUX, '--traces', dossier / 'chaine',
                              '--resultat', dossier / 'resultat'] + list(options), {'FAUX_CLAUDE_MODE': mode})

    def test_traces_d_un_arret_verdict_cout_et_resultat_perime(self):
        dossier = Path(tempfile.mkdtemp(prefix='prevo-wiki-arret-'))
        self.addCleanup(shutil.rmtree, dossier, True)
        # Refus : le verdict de Prévo est dans la trace de l'OT refusé.
        sortie = self.lancer_petit(dossier / 'refus', 'refus')
        self.assertEqual(sortie.returncode, 1)
        verdicts = [json.loads(p.read_text(encoding='utf-8')).get('verdict') for p in (dossier / 'refus' / 'chaine').glob('*.json')]
        self.assertTrue(any(v and v['statut'] == 'refusée' and 'OT-1999-9999' in v['raisons'] for v in verdicts), verdicts)
        # Une fabrication réussie, puis une autre arrêtée sur Opus : le résultat de la première ne reste pas à figer ;
        # les agents lancés et leur coût sont comptés même à l'arrêt.
        self.assertEqual(self.lancer_petit(dossier / 'perime').returncode, 0)
        self.assertTrue((dossier / 'perime' / 'resultat' / 'wiki_journal.csv').is_file())
        sortie = lancer(OUTIL, ['fabriquer', '--agents', 1, '--limite', 1, '--claude', FAUX, '--traces', dossier / 'perime' / 'autre',
                                '--resultat', dossier / 'perime' / 'resultat'], {'FAUX_CLAUDE_MODE': 'opus'})
        self.assertEqual(sortie.returncode, 1)
        self.assertIn('Agents lancés : 1 ·', sortie.stdout)
        self.assertIn('coût : 0.01 $', sortie.stdout)
        self.assertFalse((dossier / 'perime' / 'resultat' / 'wiki_journal.csv').exists())
        sortie = lancer(OUTIL, ['figer', '--resultat', dossier / 'perime' / 'resultat', '--wiki', dossier / 'fige'])
        self.assertEqual(sortie.returncode, 1)

    def test_delai_depasse_agent_coupe_et_trace(self):
        dossier = Path(tempfile.mkdtemp(prefix='prevo-wiki-delai-'))
        self.addCleanup(shutil.rmtree, dossier, True)
        import time
        depart = time.time()
        sortie = lancer(OUTIL, ['fabriquer', '--agents', 1, '--limite', 1, '--delai-appel', 2, '--claude', FAUX,
                                '--traces', dossier / 'chaine', '--resultat', dossier / 'resultat'],
                        {'FAUX_CLAUDE_MODE': 'lent', 'FAUX_CLAUDE_TRACES': str(dossier / 'agent')})
        self.assertEqual(sortie.returncode, 1)
        self.assertIn('délai dépassé (2 s)', sortie.stdout)
        appel = json.loads(next((dossier / 'chaine').glob('*.json')).read_text(encoding='utf-8'))['appels'][0]
        self.assertEqual(appel['erreur'], 'délai dépassé (2 s)')
        # L'agent lent (8 s) a été coupé : il n'a jamais fini.
        time.sleep(max(0, 11 - (time.time() - depart)))
        self.assertEqual(list((dossier / 'agent').glob('fini-*')), [])

    def test_reprise_refuse_une_reponse_non_sonnet_et_verifier_la_signale(self):
        dossier = Path(tempfile.mkdtemp(prefix='prevo-wiki-reprise-'))
        self.addCleanup(shutil.rmtree, dossier, True)
        self.assertEqual(self.lancer_petit(dossier, options=['--agents', 1]).returncode, 0)
        chemin = next((dossier / 'chaine').glob('*.json'))
        trace = json.loads(chemin.read_text(encoding='utf-8'))
        trace['appels'][0]['modele'] = 'claude-opus-5-5'           # réponse gardée qui n'est pas de Sonnet
        chemin.write_text(json.dumps(trace, ensure_ascii=False), encoding='utf-8')
        sortie = self.lancer_petit(dossier, options=['--agents', 1])
        self.assertEqual(sortie.returncode, 0, sortie.stdout)
        self.assertIn('Agents lancés : 1 · réponses reprises des traces : 2', sortie.stdout)
        # verifier refuse une trace qui contient une réponse d'un autre modèle.
        lancer(OUTIL, ['figer', '--resultat', dossier / 'resultat', '--wiki', dossier / 'fige'])
        sortie = lancer(OUTIL, ['verifier', '--demo', DEMO, '--wiki', dossier / 'fige', '--traces', dossier / 'chaine'])
        self.assertEqual(sortie.returncode, 1)
        self.assertIn('réponse de claude-opus-5-5 en 1 tour(s)', sortie.stdout)

    def test_jamais_de_repli_sur_cmd(self):
        module = charger_outil()
        dossier = Path(tempfile.mkdtemp(prefix='prevo-wiki-cmd-'))
        self.addCleanup(shutil.rmtree, dossier, True)
        (dossier / 'claude.cmd').write_text('@echo off\n', encoding='utf-8')
        original = module.shutil.which
        module.shutil.which = lambda nom: str(dossier / 'claude.cmd')
        try:
            with self.assertRaises(module.ErreurFabrication) as erreur:
                module.commande_claude('')
        finally:
            module.shutil.which = original
        self.assertIn('claude.exe introuvable', str(erreur.exception))

    def test_claude_exe_retire_puis_revenu(self):
        """Une mise à jour de Claude Code faite hors de l'outil retire claude.exe un instant : l'agent attend qu'il
        revienne, puis part ; s'il ne revient pas dans l'attente permise, il est injoignable (aucun appel fait)."""
        module = charger_outil()
        dossier = Path(tempfile.mkdtemp(prefix='prevo-wiki-maj-'))
        self.addCleanup(shutil.rmtree, dossier, True)
        commande = dossier / 'claude.exe'
        # Copie sous un autre nom puis renommage : claude.exe n'apparaît qu'entier (comme une mise à jour), jamais
        # pendant son écriture (WinError 32 sous charge).
        copie = dossier / 'claude.exe.part'
        minuteur = threading.Timer(2, lambda: (shutil.copyfile(shutil.which('whoami'), copie), os.replace(copie, commande)))
        minuteur.start()
        self.addCleanup(minuteur.cancel)

        async def lancer_agent(fabrique):
            processus = await fabrique.lancer_agent('essai')
            await processus.communicate()

        depart = time.time()
        asyncio.run(lancer_agent(module.Fabrique([str(commande)], dossier, attente_commande=30)))
        self.assertGreater(time.time() - depart, 1.5)
        with self.assertRaises(FileNotFoundError):
            asyncio.run(lancer_agent(module.Fabrique([str(dossier / 'jamais.exe')], dossier, attente_commande=2)))


class TestAPropos(CasNavigateur):

    def test_mention_du_wiki_de_demo(self):
        preregler_profil(self.contexte, 'responsable')
        self.page.goto(url_fichier('index.html'))
        self.page.click('#btn-demo')
        attendre_pret(self.page)
        self.page.evaluate("""() => Donnees.modifier('wiki_journal', (lignes) => { lignes.push({ id: 'WJ-99001',
          nature: 'ingestion', ot_id: '', statut: 'validée', modele: 'claude-sonnet-5-5' }); }, { journal: false })""")
        self.page.goto(url_fichier('index.html') + '#/apropos')
        self.page.wait_for_selector('.apropos-liste')
        texte = ' '.join(self.page.inner_text('#contenu').split())
        self.assertIn("Son wiki de maintenance a été construit par Claude (claude-sonnet-5-5) avec la consigne de Prévo, "
                      "un agent par OT, dans l'ordre des interventions ; la démo n'appelle aucune IA.", texte)


if __name__ == '__main__':
    unittest.main()
