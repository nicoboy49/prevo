#!/usr/bin/env python3
"""Fabrication du wiki de démo de Prévo (lot 6, ARCHITECTURE.md §20.10 ; D98, D109, D110, D112).

Le wiki de la démo est fabriqué comme Prévo le ferait chez un client. La démo SANS wiki est ouverte dans Chromium
(Playwright, horloge à la date de référence du jeu) ; les OT clôturés administrativement sont mis en file
(Wiki.mettreEnFile) et Wiki.traiterFile de Prévo les traite dans l'ordre des dates d'intervention, jusqu'à 5 à la
fois sur des pages distinctes. Pour chaque requête de Prévo, un agent Claude Sonnet NEUF est lancé :

    claude -p --model sonnet --tools "" --system-prompt <message système> --setting-sources "" --strict-mcp-config
           --no-session-persistence --disable-slash-commands --output-format json

avec le message utilisateur sur l'entrée standard, octet pour octet. Claude Sonnet seulement : jamais Ollama, qwen ni
modèle local. Ce que l'agent répond passe les contrôles de Prévo (Ia.lireReponse, §20.6).

    py outils/wiki_demo.py fabriquer [--agents 5]   fabrication ; reprend les réponses déjà obtenues (même requête)
    py outils/wiki_demo.py figer                      copie le résultat dans outils/demo_wiki_pages.csv et
                                                      outils/demo_wiki_journal.csv (puis : py outils/generer_demo.py)
    py outils/wiki_demo.py verifier                   traces (Sonnet, un tour), une entrée par OT, intégrité
    py outils/wiki_demo.py relecture                  .chantier/wiki-demo/relecture.html (pages par type)

Chaque appel laisse une trace dans .chantier/wiki-demo/chaine/<OT>.json : requête (système et utilisateur),
empreinte, réponse brute, modèle relevé (modelUsage), nombre de tours, jetons, coût, durée ; une réponse reprise
d'une trace (requête identique à l'octet) y est marquée. Avec un seul agent, une nouvelle fabrication envoie les
mêmes requêtes et reprend tout ; avec plusieurs, le catalogue d'une requête peut différer d'une fabrication à
l'autre (pages créées par des OT traités en même temps sur d'autres pages, déjà finis ou non) : cette requête est
alors renvoyée. La fabrication s'arrête (code retour 1) sur un modèle autre
que Sonnet, plus d'un tour, une réponse en erreur, une réponse refusée par les contrôles de Prévo (défaut de la
fonction : on corrige le code, puis on relance — les réponses déjà obtenues sont reprises sans nouvel appel), une
IA injoignable ou une intégrité en défaut. Les propositions acceptées sont validées au nom du responsable, sauf
celles des demoAValiderJours derniers jours d'intervention, laissées « à valider ».
"""
import argparse
import asyncio
import csv
import hashlib
import html
import io
import json
import shutil
import sys
import tempfile
import time
from datetime import date, datetime, timedelta
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_DEMO = RACINE / 'donnees' / 'demo'
DOSSIER_TRAVAIL = RACINE / '.chantier' / 'wiki-demo'
DOSSIER_TRACES = DOSSIER_TRAVAIL / 'chaine'
DOSSIER_RESULTAT = DOSSIER_TRAVAIL / 'resultat'
DOSSIER_FIGE = RACINE / 'outils'
FICHIERS_FIGES = {'wiki_pages': 'demo_wiki_pages.csv', 'wiki_journal': 'demo_wiki_journal.csv'}
DATE_REFERENCE = '2026-10-19'           # celle de outils/generer_demo.py (« aujourd'hui » du jeu de démo)
HEURE_REFERENCE = 9                     # il est 9 h à la date de référence
DELAI_APPEL_S = 300
SCRIPTS = [
    'js/lib/papaparse.min.js', 'js/schema.js', 'js/donnees.js', 'js/stockage-demo.js',
    'js/modules/causes-frequentes.js', 'js/modules/indicateurs-regles.js', 'js/modules/ia.js', 'js/modules/ia-prompts.js',
    'js/modules/wiki-regles.js', 'js/modules/wiki-calculs.js', 'js/modules/wiki-texte.js', 'js/modules/wiki-recherche.js',
    'js/modules/wiki-ingestion.js', 'js/modules/wiki-journal.js',
]
# Options de chaque agent : aucun outil, aucun réglage, aucun serveur MCP, aucune session gardée (D98).
OPTIONS_CLAUDE = ['--setting-sources', '', '--strict-mcp-config', '--no-session-persistence', '--disable-slash-commands',
                  '--output-format', 'json']
PROFIL_JS = """() => { window.App = { estResponsable: () => true, libelleProfil: () => 'Responsable',
  profil: { type: 'responsable', nom: '' } }; }"""
CHARGER_JS = """async (tables) => {
  Donnees.initialiser(StockageDemo.creer(tables), { poste: 'Fabrication du wiki de démo', profil: 'Responsable' });
  await Donnees.chargerTout();
}"""
TRAITER_JS = """async ({ agents, limite }) => {
  let ids = Donnees.lignes('ordres_travail').filter((o) => o.statut === 'Clôturé administrativement')
    .sort((a, b) => (a.date_fin < b.date_fin ? -1 : (a.date_fin > b.date_fin ? 1 : (a.id < b.id ? -1 : 1)))).map((o) => o.id);
  if (limite) ids = ids.slice(0, limite);
  await Wiki.mettreEnFile(ids);
  const arret = new AbortController();
  const bilan = await Wiki.traiterFile({ agents, signal: arret.signal,
    appeler: (requete, donnees) => window.appelerClaude(requete, donnees.ot.id),
    surProgres: (etat) => { window.progresFabrication(etat); if (etat.refusees) arret.abort(); } });
  window.dernierBilan = bilan;
  return { ot: ids.length, acceptees: bilan.acceptees, rien: bilan.rien, refusees: bilan.refusees, rejouees: bilan.rejouees,
    erreur: bilan.erreur ? (bilan.erreur.message || String(bilan.erreur)) : null, enFile: Wiki.file().length,
    refus: Donnees.lignes('wiki_journal').filter((e) => e.statut === 'refusée').map((e) => [e.ot_id, e.raisons]) };
}"""
VALIDER_JS = """async (limite) => {
  const resultat = { validees: 0, laissees: [], bloquees: [] };
  const entrees = Donnees.lignes('wiki_journal').filter((e) => e.statut === 'à valider')
    .sort((a, b) => Number(a.ordre) - Number(b.ordre));
  for (const entree of entrees) {
    if (String(entree.date_intervention).slice(0, 10) > limite) { resultat.laissees.push(entree.ot_id); continue; }
    try {
      const bilan = await Wiki.valider([entree.id]);
      resultat.validees += bilan.validees.length;
      bilan.aRefaire.forEach((id) => resultat.bloquees.push([entree.ot_id, 'à refaire : ' + id]));
    } catch (erreur) { resultat.bloquees.push([entree.ot_id, erreur.message]); }
  }
  resultat.integrite = Wiki.verifierIntegrite({ envois: (window.dernierBilan || {}).envois || [] });
  const fichiers = Donnees.instantane();
  resultat.fichiers = { wiki_pages: new TextDecoder().decode(fichiers.wiki_pages),
    wiki_journal: new TextDecoder().decode(fichiers.wiki_journal) };
  return resultat;
}"""


class ErreurFabrication(Exception):
    """Arrêt de la fabrication : modèle, tours, réponse en erreur, appel impossible."""


def ecrire(texte=''):
    print(texte, flush=True)


# ---------------------------------------------------------------------------------------------------
# Données et navigateur
# ---------------------------------------------------------------------------------------------------

def lire_tables(dossier, sans_wiki):
    """Texte CSV de chaque table du dossier ; sans_wiki : tables du wiki réduites à leur en-tête."""
    tables = {}
    for fichier in sorted(Path(dossier).glob('*.csv')):
        texte = fichier.read_bytes().decode('utf-8-sig')
        if sans_wiki and fichier.stem in FICHIERS_FIGES:
            texte = texte.split('\r\n', 1)[0].split('\n', 1)[0] + '\r\n'
        tables[fichier.stem] = texte
    return tables


def script_horloge(reference):
    """Script posé avant la page : la date du jour est arrêtée à la date de référence, 9 h (les dates écrites par
    Prévo ne dépendent pas de la durée de la fabrication ; les minuteries, elles, tournent normalement)."""
    return """(() => { const fixe = %d; const Reelle = Date;
  class Arretee extends Reelle {
    constructor(...valeurs) { if (valeurs.length) super(...valeurs); else super(fixe); }
    static now() { return fixe; }
  }
  window.Date = Arretee; })();""" % int(reference.timestamp() * 1000)


async def ouvrir_page(playwright, tables):
    """Chromium sans tête, scripts de Prévo chargés, horloge à la date de référence, profil responsable."""
    navigateur = await playwright.chromium.launch(headless=True)
    contexte = await navigateur.new_context(locale='fr-FR')
    reference = datetime.strptime(DATE_REFERENCE, '%Y-%m-%d').replace(hour=HEURE_REFERENCE)
    await contexte.add_init_script(script_horloge(reference))
    page = await contexte.new_page()
    page.set_default_timeout(0)
    erreurs = []
    page.on('pageerror', lambda erreur: erreurs.append(str(erreur)))
    await page.set_content('<!doctype html><html lang="fr"><head><meta charset="utf-8"></head><body></body></html>')
    for chemin in SCRIPTS:
        await page.add_script_tag(path=str(RACINE / chemin))
    await page.evaluate(PROFIL_JS)
    await page.evaluate(CHARGER_JS, tables)
    return navigateur, page, erreurs


# ---------------------------------------------------------------------------------------------------
# Agents Claude et traces
# ---------------------------------------------------------------------------------------------------

def commande_claude(chemin):
    """Commande de base d'un agent : claude.exe de npm (jamais cmd.exe, qui abîmerait le message système)."""
    if chemin:
        absolu = str(Path(chemin).resolve())          # l'agent tourne dans un dossier neutre
        return [sys.executable, absolu] if chemin.endswith('.py') else [absolu]
    trouve = shutil.which('claude')
    if trouve and trouve.lower().endswith(('.cmd', '.bat')):
        exe = Path(trouve).parent / 'node_modules' / '@anthropic-ai' / 'claude-code' / 'bin' / 'claude.exe'
        if exe.is_file():
            return [str(exe)]
    if not trouve:
        raise ErreurFabrication('commande « claude » introuvable')
    return [trouve]


def empreinte(systeme, utilisateur):
    return hashlib.sha256((systeme + '\x00' + utilisateur).encode('utf-8')).hexdigest()


def lire_trace(dossier, ot):
    chemin = dossier / (ot + '.json')
    return json.loads(chemin.read_text(encoding='utf-8')) if chemin.is_file() else {'ot': ot, 'appels': []}


def ecrire_trace(dossier, trace):
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / (trace['ot'] + '.json')).write_text(json.dumps(trace, ensure_ascii=False, indent=1), encoding='utf-8')


def controler_reponse(donnees):
    """Modèles relevés (modelUsage) et nombre de tours d'une réponse JSON de claude -p ; arrêt sinon."""
    if donnees.get('is_error') or donnees.get('subtype') not in (None, 'success'):
        raise ErreurFabrication('réponse en erreur : %s' % str(donnees.get('result') or donnees.get('subtype'))[:300])
    modeles = sorted((donnees.get('modelUsage') or {}).keys())
    if not modeles or any('sonnet' not in modele.lower() for modele in modeles):
        raise ErreurFabrication('modèle autre que Sonnet : %s' % (', '.join(modeles) or 'aucun'))
    if donnees.get('num_turns') != 1:
        raise ErreurFabrication('%s tours au lieu d\'un seul' % donnees.get('num_turns'))
    return modeles


class Fabrique:
    """Pont entre Wiki.traiterFile (page) et les agents Claude (Python)."""

    def __init__(self, commande, traces):
        self.commande = commande
        self.traces = traces
        self.appels = 0
        self.reprises = 0
        self.cout = 0.0
        self.arret = None
        self.dernier = None
        self.dossier_neutre = Path(tempfile.mkdtemp(prefix='prevo-agent-'))

    async def appeler(self, requete, ot):
        messages = requete.get('messages') or []
        if [m.get('role') for m in messages] != ['system', 'user']:
            raise ErreurFabrication('requête inattendue pour %s : %s' % (ot, [m.get('role') for m in messages]))
        systeme, utilisateur = messages[0]['content'], messages[1]['content']
        cle = empreinte(systeme, utilisateur)
        trace = lire_trace(self.traces, ot)
        deja = next((a for a in trace['appels'] if a.get('empreinte') == cle and not a.get('reprise') and a.get('contenu')), None)
        if deja:
            self.reprises += 1
            trace['appels'].append({'empreinte': cle, 'reprise': True, 'date': datetime.now().isoformat(timespec='seconds')})
            ecrire_trace(self.traces, trace)
            return {'contenu': deja['contenu'], 'modele': deja['modele']}
        try:
            return await self.appeler_agent(ot, systeme, utilisateur, cle, trace)
        except ErreurFabrication as erreur:
            self.arret = self.arret or '%s : %s' % (ot, erreur)
            raise

    async def appeler_agent(self, ot, systeme, utilisateur, cle, trace):
        arguments = self.commande + ['-p', '--model', 'sonnet', '--tools', '', '--system-prompt', systeme] + OPTIONS_CLAUDE
        depart = time.time()
        try:
            processus = await asyncio.create_subprocess_exec(
                *arguments, cwd=str(self.dossier_neutre), stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            sortie, erreurs = await asyncio.wait_for(processus.communicate(utilisateur.encode('utf-8')), DELAI_APPEL_S)
        except (OSError, asyncio.TimeoutError) as erreur:
            raise ErreurFabrication('agent injoignable : %s' % (erreur or 'délai dépassé'))
        brute = sortie.decode('utf-8', 'replace')
        appel = {'empreinte': cle, 'reprise': False, 'date': datetime.now().isoformat(timespec='seconds'),
                 'systeme': systeme, 'utilisateur': utilisateur, 'reponse_brute': brute,
                 'stderr': erreurs.decode('utf-8', 'replace')[-2000:], 'code_retour': processus.returncode,
                 'duree_s': round(time.time() - depart, 2)}
        trace['appels'].append(appel)
        try:
            donnees = json.loads(brute)
            appel.update({'modele': ', '.join(sorted((donnees.get('modelUsage') or {}).keys())),
                          'tours': donnees.get('num_turns'), 'jetons': donnees.get('usage'),
                          'cout_usd': donnees.get('total_cost_usd'), 'duree_api_ms': donnees.get('duration_api_ms')})
            modeles = controler_reponse(donnees)
        except ValueError:
            ecrire_trace(self.traces, trace)
            raise ErreurFabrication('réponse illisible (code %s) : %s' % (processus.returncode, brute[:300] or appel['stderr'][-300:]))
        except ErreurFabrication:
            ecrire_trace(self.traces, trace)
            raise
        appel['contenu'] = donnees.get('result') or ''
        ecrire_trace(self.traces, trace)
        self.appels += 1
        self.cout += float(donnees.get('total_cost_usd') or 0)
        return {'contenu': appel['contenu'], 'modele': modeles[0]}

    async def progres(self, etat):
        faits = (etat.get('acceptees') or 0) + (etat.get('rien') or 0)
        resume = (faits // 25, etat.get('refusees'), etat.get('rejouees'), etat.get('restants') == 0)
        if resume != self.dernier:
            self.dernier = resume
            ecrire('  en cours %(enCours)s · restants %(restants)s · acceptées %(acceptees)s · rien %(rien)s · '
                   'refusées %(refusees)s · rejouées %(rejouees)s' % etat)


async def fabriquer_async(arguments):
    commande = commande_claude(arguments.claude)
    fabrique = Fabrique(commande, Path(arguments.traces))
    from playwright.async_api import async_playwright
    async with async_playwright() as playwright:
        navigateur, page, erreurs = await ouvrir_page(playwright, lire_tables(arguments.demo, sans_wiki=True))
        try:
            await page.expose_function('appelerClaude', fabrique.appeler)
            await page.expose_function('progresFabrication', fabrique.progres)
            ecrire('Fabrication du wiki de démo : %s agent(s), commande %s' % (arguments.agents, ' '.join(commande)))
            bilan = await page.evaluate(TRAITER_JS, {'agents': arguments.agents, 'limite': arguments.limite or 0})
            ecrire('OT : %(ot)s · acceptées %(acceptees)s · rien à ajouter %(rien)s · refusées %(refusees)s · '
                   'rejouées %(rejouees)s · encore en file %(enFile)s' % bilan)
            ecrire('Agents lancés : %d · réponses reprises des traces : %d · coût : %.2f $'
                   % (fabrique.appels, fabrique.reprises, fabrique.cout))
            if fabrique.arret or bilan['erreur']:
                ecrire('ARRÊT : %s' % (fabrique.arret or bilan['erreur']))
                return 1
            if bilan['refusees']:
                for ot, raisons in bilan['refus']:
                    ecrire('REFUSÉE %s :\n    %s' % (ot, '\n    '.join(str(raisons).splitlines())))
                ecrire('ARRÊT : réponse refusée par les contrôles de Prévo (défaut de la fonction à corriger, puis relancer).')
                return 1
            if bilan['enFile']:
                ecrire('ARRÊT : %d OT encore en file.' % bilan['enFile'])
                return 1
            limite = (date.fromisoformat(DATE_REFERENCE) - timedelta(days=arguments.a_valider_jours)).isoformat()
            resultat = await page.evaluate(VALIDER_JS, limite)
            ecrire('Validées : %d · laissées « à valider » (après le %s) : %s'
                   % (resultat['validees'], limite, ', '.join(resultat['laissees']) or 'aucune'))
            if resultat['bloquees']:
                ecrire('ARRÊT : validations impossibles : %s' % resultat['bloquees'])
                return 1
            if not resultat['integrite']['ok']:
                ecrire('ARRÊT : intégrité en défaut : %s' % json.dumps(resultat['integrite']['ecarts'][:10], ensure_ascii=False))
                return 1
            if erreurs:
                ecrire('ARRÊT : erreurs JavaScript : %s' % erreurs[:5])
                return 1
            sortie = Path(arguments.resultat)
            sortie.mkdir(parents=True, exist_ok=True)
            for table, texte in resultat['fichiers'].items():
                (sortie / (table + '.csv')).write_bytes(texte.encode('utf-8'))
            ecrire('Intégrité ok. Résultat : %s (puis : py outils/wiki_demo.py figer)' % sortie)
            return 0
        finally:
            await navigateur.close()
            shutil.rmtree(fabrique.dossier_neutre, ignore_errors=True)


# ---------------------------------------------------------------------------------------------------
# Figer, vérifier, relecture
# ---------------------------------------------------------------------------------------------------

def figer(arguments):
    source, cible = Path(arguments.resultat), Path(arguments.wiki)
    for table, nom in FICHIERS_FIGES.items():
        if not (source / (table + '.csv')).is_file():
            ecrire('ARRÊT : %s absent (lancer d\'abord « fabriquer »).' % (source / (table + '.csv')))
            return 1
    cible.mkdir(parents=True, exist_ok=True)
    for table, nom in FICHIERS_FIGES.items():
        (cible / nom).write_bytes((source / (table + '.csv')).read_bytes())
        ecrire('Figé : %s' % (cible / nom))
    ecrire('Suite : py outils/generer_demo.py')
    return 0


def lignes_csv(texte):
    lecteur = csv.reader(io.StringIO(texte.lstrip('﻿'), newline=''), delimiter=';')
    lignes = list(lecteur)
    return [dict(zip(lignes[0], ligne)) for ligne in lignes[1:]] if lignes else []


async def integrite_async(dossier):
    from playwright.async_api import async_playwright
    async with async_playwright() as playwright:
        navigateur, page, erreurs = await ouvrir_page(playwright, lire_tables(dossier, sans_wiki=False))
        try:
            return await page.evaluate('() => Wiki.verifierIntegrite()'), erreurs
        finally:
            await navigateur.close()


def verifier(arguments):
    defauts = []
    appels = 0
    for chemin in sorted(Path(arguments.traces).glob('*.json')):
        for appel in json.loads(chemin.read_text(encoding='utf-8')).get('appels', []):
            if appel.get('reprise'):
                continue
            if not appel.get('contenu'):
                continue                         # appel arrêté (déjà signalé à la fabrication), sans réponse gardée
            appels += 1
            modeles = [m.strip() for m in str(appel.get('modele', '')).split(',') if m.strip()]
            if not modeles or any('sonnet' not in m.lower() for m in modeles) or appel.get('tours') != 1:
                defauts.append('%s : modèle %s, %s tour(s)' % (chemin.stem, appel.get('modele'), appel.get('tours')))
    journal = lignes_csv((Path(arguments.wiki) / FICHIERS_FIGES['wiki_journal']).read_bytes().decode('utf-8'))
    integres = {ligne['ot_id'] for ligne in journal if ligne.get('nature') == 'ingestion'}
    ordres = lignes_csv((Path(arguments.demo) / 'ordres_travail.csv').read_bytes().decode('utf-8'))
    clotures = sorted(o['id'] for o in ordres if o['statut'] == 'Clôturé administrativement')
    manquants = [ot for ot in clotures if ot not in integres]
    if manquants:
        defauts.append('OT sans entrée au journal figé : %s' % ', '.join(manquants))
    modeles = sorted({ligne['modele'] for ligne in journal if ligne.get('modele')})
    if any('sonnet' not in m.lower() for m in modeles):
        defauts.append('modèle autre que Sonnet au journal figé : %s' % modeles)
    for table, nom in FICHIERS_FIGES.items():
        demo = lignes_csv((Path(arguments.demo) / (table + '.csv')).read_bytes().decode('utf-8'))
        fige = lignes_csv((Path(arguments.wiki) / nom).read_bytes().decode('utf-8'))
        if len(demo) != len(fige):
            defauts.append('%s : %d lignes dans la démo, %d figées (relancer py outils/generer_demo.py)' % (table, len(demo), len(fige)))
    integrite, erreurs = asyncio.run(integrite_async(arguments.demo))
    if not integrite['ok']:
        defauts.append('intégrité : %s' % json.dumps(integrite['ecarts'][:10], ensure_ascii=False))
    if erreurs:
        defauts.append('erreurs JavaScript : %s' % erreurs[:5])
    ecrire('Traces : %d appels d\'agents · modèles du journal figé : %s · OT clôturés administrativement : %d, intégrés : %d'
           % (appels, ', '.join(modeles) or 'aucun', len(clotures), len([ot for ot in clotures if ot in integres])))
    for defaut in defauts:
        ecrire('DÉFAUT : ' + defaut)
    ecrire('Vérification : ' + ('OK' if not defauts else 'ÉCHEC'))
    return 0 if not defauts else 1


RELECTURE_JS = """() => {
  const types = ['équipement', 'composant', 'mode', 'savoir-faire'];
  const ids = new Set(Donnees.lignes('wiki_pages').filter((l) => l.statut !== 'archivée' && l.texte)
    .map((l) => Wiki.page(l.id) && Wiki.page(l.id).id).filter(Boolean));
  const pages = Array.from(ids).map((id) => Wiki.page(id, { responsable: true })).map((p) => {
    const ot = Array.from(new Set(Wiki.citationsDe(p.texte)));
    return { id: p.id, type: p.type, titre: p.titre, texte: p.texte, origine: p.origine, modele: p.modele,
      validePar: p.validePar, valideLe: p.valideLe, phrases: Wiki.phrasesDe(p.texte).length, calcul: p.calcul || null,
      entete: p.entete || null, retours: p.retours, contradictions: p.contradictions, enAttente: p.enAttente,
      ot: ot.map((id) => { const o = Donnees.trouver('ordres_travail', id) || {};
        return { id, date: o.date_fin, titre: o.titre, compteRendu: o.compte_rendu, astuce: o.astuce }; }) };
  });
  pages.sort((a, b) => types.indexOf(a.type) - types.indexOf(b.type) || b.ot.length - a.ot.length
    || b.phrases - a.phrases || (a.titre < b.titre ? -1 : 1));
  return pages;
}"""


async def relecture_async(dossier):
    from playwright.async_api import async_playwright
    async with async_playwright() as playwright:
        navigateur, page, _erreurs = await ouvrir_page(playwright, lire_tables(dossier, sans_wiki=False))
        try:
            return await page.evaluate(RELECTURE_JS)
        finally:
            await navigateur.close()


def resume_calcul(calcul):
    """Résumé lisible de la couche calculée : valeurs simples et taille des listes."""
    if not isinstance(calcul, dict):
        return ''
    morceaux = []
    for cle, valeur in calcul.items():
        if isinstance(valeur, list):
            morceaux.append('%s : %d' % (cle, len(valeur)))
        elif isinstance(valeur, (str, int, float)) and str(valeur) != '':
            morceaux.append('%s : %s' % (cle, valeur))
    return ' · '.join(morceaux)


def page_html(page):
    e = html.escape
    lignes = ['<section class="page"><h3>%s <small>%s · %d OT · %d phrases</small></h3>'
              % (e(page['titre']), e(page['type']), len(page['ot']), page['phrases'])]
    for contradiction in page['contradictions']:
        lignes.append('<p class="contradiction"><b>À trancher</b> — « %s » ; %s : %s (%s)</p>'
                      % (e(contradiction['phrase']), e(contradiction['libelle']), e(contradiction['observation']),
                         e(contradiction['otSource'])))
    if page['enAttente']:
        lignes.append('<p class="attente">Proposition à valider : %s</p>' % e(', '.join(a['ot'] for a in page['enAttente'])))
    lignes.append('<p class="origine">Origine : %s (%s) — validé par %s le %s</p>'
                  % (e(page['origine'] or '—'), e(page['modele'] or '—'), e(page['validePar'] or '—'), e(page['valideLe'] or '—')))
    if page['calcul']:
        lignes.append('<p class="calcul">Couche calculée : %s</p>' % e(resume_calcul(page['calcul'])))
    lignes.append('<pre>%s</pre>' % e(page['texte']))
    lignes.append('<details><summary>OT cités (%d)</summary><ul>' % len(page['ot']))
    for ot in page['ot']:
        lignes.append('<li><b>%s</b> (%s) %s<br>%s%s</li>' % (e(ot['id']), e(ot['date'] or ''), e(ot['titre'] or ''),
                      e(ot['compteRendu'] or ''), ('<br><i>Astuce : %s</i>' % e(ot['astuce'])) if ot['astuce'] else ''))
    lignes.append('</ul></details></section>')
    return '\n'.join(lignes)


def relecture(arguments):
    pages = asyncio.run(relecture_async(arguments.demo))
    titres = {'équipement': 'Équipements', 'composant': 'Composants', 'mode': 'Modes de défaillance', 'savoir-faire': 'Savoir-faire'}
    corps = []
    for type_page, titre in titres.items():
        du_type = [p for p in pages if p['type'] == type_page]
        corps.append('<h2>%s (%d)</h2>' % (titre, len(du_type)))
        corps.extend(page_html(p) for p in du_type)
    document = ('<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
                '<title>Wiki de démo — relecture</title><style>body{font-family:system-ui,sans-serif;max-width:60rem;margin:auto;'
                'padding:1rem;color:#1b1f24}pre{white-space:pre-wrap;background:#f4f6f8;padding:.6rem}.page{border-top:1px solid #ccd;'
                'padding:.4rem 0}.contradiction{background:#fff3cd;padding:.4rem}.attente{color:#6b4e00}small{color:#555}</style>'
                '</head><body><h1>Wiki de démo — relecture</h1><p>Pages par type, les plus riches d\'abord (OT cités distincts, '
                'puis phrases). Ce qui est refusé se corrige dans la fonction, puis la fabrication est rejouée.</p>'
                + '\n'.join(corps) + '</body></html>')
    sortie = Path(arguments.sortie)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(document, encoding='utf-8')
    ecrire('Relecture : %s (%d pages)' % (sortie, len(pages)))
    return 0


def lire_arguments(argv):
    analyseur = argparse.ArgumentParser(description='Fabrication du wiki de démo de Prévo (Claude Sonnet, claude -p).')
    sous = analyseur.add_subparsers(dest='action', required=True)
    commun = argparse.ArgumentParser(add_help=False)
    commun.add_argument('--demo', default=str(DOSSIER_DEMO), help='dossier du jeu de démo (défaut : donnees/demo)')
    commun.add_argument('--traces', default=str(DOSSIER_TRACES), help='dossier des traces des agents')
    commun.add_argument('--resultat', default=str(DOSSIER_RESULTAT), help='dossier du résultat de la fabrication')
    commun.add_argument('--wiki', default=str(DOSSIER_FIGE), help='dossier des fichiers figés (défaut : outils)')
    fabrication = sous.add_parser('fabriquer', parents=[commun], help='fabrique le wiki de démo')
    fabrication.add_argument('--agents', type=int, default=5, help='agents en même temps (1 à 5, défaut 5)')
    fabrication.add_argument('--claude', default='', help='commande claude (essais : un script .py)')
    fabrication.add_argument('--limite', type=int, default=0, help='seulement les N premiers OT (essais)')
    fabrication.add_argument('--a-valider-jours', type=int, default=14, help='jours laissés « à valider » (défaut 14)')
    sous.add_parser('figer', parents=[commun], help='copie le résultat dans les fichiers figés')
    sous.add_parser('verifier', parents=[commun], help='vérifie traces, journal figé et intégrité')
    lecture = sous.add_parser('relecture', parents=[commun], help='page de relecture du wiki de démo')
    lecture.add_argument('--sortie', default=str(DOSSIER_TRAVAIL / 'relecture.html'))
    arguments = analyseur.parse_args(argv)
    if arguments.action == 'fabriquer' and not 1 <= arguments.agents <= 5:
        analyseur.error('--agents : de 1 à 5')
    return arguments


def principal(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    arguments = lire_arguments(argv)
    if arguments.action == 'fabriquer':
        return asyncio.run(fabriquer_async(arguments))
    return {'figer': figer, 'verifier': verifier, 'relecture': relecture}[arguments.action](arguments)


if __name__ == '__main__':
    try:
        sys.exit(principal())
    except ErreurFabrication as erreur:
        ecrire('ARRÊT : %s' % erreur)
        sys.exit(1)
