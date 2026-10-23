#!/usr/bin/env python3
"""Fabrication du wiki de démo de Prévo (lot 6, ARCHITECTURE.md §20.10 ; D98, D109, D110, D112).

Le wiki de la démo est fabriqué comme Prévo le ferait chez un client. La démo SANS wiki est ouverte dans Chromium
(Playwright, horloge à la date de référence du jeu) ; les OT clôturés administrativement sont mis en file
(Wiki.mettreEnFile) et Wiki.traiterFile de Prévo les traite dans l'ordre des dates d'intervention, jusqu'à 5 à la
fois sur des pages distinctes. Pour chaque requête de Prévo, un agent Claude Sonnet NEUF est lancé :

    claude -p --model sonnet --tools "" --system-prompt <message système> --setting-sources "" --strict-mcp-config
           --no-session-persistence --disable-slash-commands --output-format json

avec le message utilisateur sur l'entrée standard, octet pour octet. Claude Sonnet seulement : jamais Ollama, qwen ni
modèle local. Ce que l'agent répond passe les contrôles de Prévo (Ia.lireReponse, §20.6). Une réponse refusée est
relancée avec la raison, comme chez un client (§20.5, D106 révisée) : Prévo envoie une requête neuve (message
d'origine, réponse refusée, raisons du refus), qui lance un agent neuf de plus, tracé dans la même trace.

    py outils/wiki_demo.py fabriquer [--agents 5]   fabrication ; reprend les réponses déjà obtenues (même requête)
    py outils/wiki_demo.py fabriquer --limite 40     temps 1 (D115) : les 40 premiers OT par date d'intervention ;
                                                      résultat, état de départ de la suite et page de relecture dans
                                                      .chantier/wiki-demo/temps-1/ (relecture.html)
    py outils/wiki_demo.py fabriquer --suite         temps 2 : repart de l'état exact du temps 1 (tables du wiki et
                                                      journal avant validation) et ne traite que les OT qui n'y sont
                                                      pas ; validations comme d'un seul tenant ; résultat à figer
    py outils/wiki_demo.py figer                      copie le résultat dans outils/demo_wiki_pages.csv et
                                                      outils/demo_wiki_journal.csv (puis : py outils/generer_demo.py)
    py outils/wiki_demo.py verifier                   traces (Sonnet, un tour), une entrée par OT reliée à la réponse
                                                      acceptée (relance comprise), intégrité
    py outils/wiki_demo.py relecture                  .chantier/wiki-demo/relecture.html (pages par type)

Fabrication en deux temps (D115) : le temps 1 garde, à côté de son résultat, les tables du wiki AVANT les validations
(etat-avant-validation/) et temps-1.json (OT intégrés, empreinte des données de la démo et de la consigne, bilan,
coût). --suite charge cet état, met en file les OT clôturés administrativement qui n'y ont pas d'entrée, les traite
dans le même ordre, puis valide tout comme une fabrication d'un seul tenant : avec un agent, même wiki à l'octet. Elle
refuse de partir sans temps 1, ou si les données de la démo ou la consigne ont changé depuis (rejouer alors le temps
1 : les réponses déjà obtenues pour des requêtes identiques sont reprises sans nouvel appel).

Chaque appel laisse une trace dans .chantier/wiki-demo/chaine/<OT>.json : requête (système et utilisateur),
empreinte, réponse brute, modèle relevé (modelUsage), nombre de tours, jetons, coût, durée ; une réponse reprise
d'une trace (requête identique à l'octet) y est marquée. Une réponse reprise est rendue après sa durée d'origine
(--reprise-duree, 1 par défaut ; 0 : tout de suite) : les réponses arrivent dans le même ordre, donc, même avec
plusieurs agents, les mêmes requêtes partent (le catalogue d'une requête dépend des OT déjà finis ailleurs) et tout
est repris ; à deux réponses très proches près (quelques millisecondes), l'ordre peut s'inverser : la requête qui
suit est alors renvoyée. --reprise-seule n'appelle jamais Claude : une requête absente des traces arrête la
fabrication (aucun coût imprévu). Une requête de relance identique à l'octet est reprise de même. La fabrication s'arrête (code
retour 1) sur un modèle autre que Sonnet, plus d'un tour, une réponse en erreur, une relance refusée par les contrôles
de Prévo (défaut de la fonction : on corrige le code, puis on relance — les réponses déjà obtenues sont reprises sans
nouvel appel), une IA injoignable ou une intégrité en défaut. Les propositions acceptées sont validées au nom du
responsable, sauf celles des demoAValiderJours derniers jours d'intervention, laissées « à valider », et celles
qui dépendent d'une proposition laissée (Wiki.valider les refuserait avant elle). Un agent ne met jamais Claude
Code à jour ; si claude.exe disparaît un instant (mise à jour faite ailleurs), l'agent attend qu'il revienne.
"""
import argparse
import asyncio
import csv
import hashlib
import html
import io
import json
import os
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
DOSSIER_TEMPS_1 = DOSSIER_TRAVAIL / 'temps-1'       # résultat du temps 1 (--limite) et départ de --suite (D115)
FICHIER_TEMPS_1 = 'temps-1.json'                     # OT intégrés, empreintes, bilan et coût du temps 1
DOSSIER_ETAT = 'etat-avant-validation'               # tables du wiki du temps 1 avant les validations
RELECTURE_TEMPS_1 = 'relecture.html'
DOSSIER_FIGE = RACINE / 'outils'
FICHIERS_FIGES = {'wiki_pages': 'demo_wiki_pages.csv', 'wiki_journal': 'demo_wiki_journal.csv'}
sys.path.insert(0, str(RACINE / 'outils'))
from generer_demo import DATE_REFERENCE  # noqa: E402  (« aujourd'hui » du jeu de démo)
HEURE_REFERENCE = 9                     # il est 9 h à la date de référence
DELAI_APPEL_S = 300
ATTENTE_COMMANDE_S = 120     # claude.exe absent au lancement (mise à jour de Claude Code en cours) : attente maximale
# Début de la suite d'un message de relance avec la raison (consigne ingestionWiki, ia-prompts.js) : avant lui, le
# message d'origine tel quel ; après, la réponse refusée et les raisons du refus.
MARQUE_RELANCE = '\n\nTa réponse précédente :\n'
SCRIPTS = [
    'js/lib/papaparse.min.js', 'js/schema.js', 'js/donnees.js', 'js/stockage-demo.js',
    'js/modules/causes-frequentes.js', 'js/modules/indicateurs-regles.js', 'js/modules/ia.js', 'js/modules/ia-prompts.js',
    'js/modules/wiki-regles.js', 'js/modules/wiki-calculs.js', 'js/modules/wiki-entites.js', 'js/modules/wiki-texte.js',
    'js/modules/wiki-recherche.js',
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
  // Suite du temps 1 : un OT qui a déjà son entrée (à valider, rien à ajouter) n'est pas remis en file.
  const ajoutes = await Wiki.mettreEnFile(ids);
  const arret = new AbortController();
  const bilan = await Wiki.traiterFile({ agents, signal: arret.signal,
    appeler: (requete, donnees) => window.appelerClaude(requete, donnees.ot.id),
    surProgres: (etat) => { window.progresFabrication(etat); if (etat.refusees) arret.abort(); } });
  window.dernierBilan = bilan;
  const entrees = Donnees.lignes('wiki_journal').filter((e) => e.nature === 'ingestion');
  return { ot: ids.length, ids, ajoutes, acceptees: bilan.acceptees, rien: bilan.rien, refusees: bilan.refusees,
    rejouees: bilan.rejouees, erreur: bilan.erreur ? (bilan.erreur.message || String(bilan.erreur)) : null,
    enFile: Wiki.file().length,
    refus: entrees.filter((e) => e.statut === 'refusée').map((e) => [e.ot_id, e.raisons]),
    // Acceptées à la relance avec la raison : l'entrée garde les raisons du premier refus.
    relances: entrees.filter((e) => ['à valider', 'rien à ajouter'].includes(e.statut) && e.raisons).map((e) => e.ot_id) };
}"""
VALIDER_JS = """async (limite) => {
  const resultat = { validees: 0, laissees: [], bloquees: [] };
  const entrees = Donnees.lignes('wiki_journal').filter((e) => e.statut === 'à valider')
    .sort((a, b) => Number(a.ordre) - Number(b.ordre));
  const laissees = [];                        // identifiants des entrées laissées « à valider »
  for (const entree of entrees) {
    if (String(entree.date_intervention).slice(0, 10) > limite) {
      laissees.push(entree.id);
      resultat.laissees.push(entree.ot_id);
      continue;
    }
    try {
      const bilan = await Wiki.valider([entree.id]);
      resultat.validees += bilan.validees.length;
      bilan.aRefaire.forEach((id) => resultat.bloquees.push([entree.ot_id, 'à refaire : ' + id]));
    } catch (erreur) {
      // Construite sur une proposition laissée « à valider » : laissée aussi (Wiki.valider la refuse avant elle).
      const dependante = /^Validez d'abord /.test(erreur.message) && laissees.some((id) => erreur.message.includes(id));
      if (dependante) { laissees.push(entree.id); resultat.laissees.push(entree.ot_id + ' (suit une proposition laissée)'); }
      else resultat.bloquees.push([entree.ot_id, erreur.message]);
    }
  }
  resultat.integrite = Wiki.verifierIntegrite({ envois: (window.dernierBilan || {}).envois || [] });
  const fichiers = Donnees.instantane();
  resultat.fichiers = { wiki_pages: new TextDecoder().decode(fichiers.wiki_pages),
    wiki_journal: new TextDecoder().decode(fichiers.wiki_journal) };
  return resultat;
}"""
# Tables du wiki telles quelles (temps 1 : avant les validations, départ de --suite).
TABLES_WIKI_JS = """() => { const fichiers = Donnees.instantane();
  return { wiki_pages: new TextDecoder().decode(fichiers.wiki_pages), wiki_journal: new TextDecoder().decode(fichiers.wiki_journal) }; }"""
# OT qui ont déjà une entrée d'ingestion (suite du temps 1 : ils ne repartent pas).
DEJA_JS = """() => Donnees.lignes('wiki_journal').filter((e) => e.nature === 'ingestion').map((e) => e.ot_id)"""
CONSIGNE_JS = "() => Ia.PROMPTS.ingestionWiki.systeme"


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
    if not trouve:
        raise ErreurFabrication('commande « claude » introuvable')
    if trouve.lower().endswith(('.cmd', '.bat')):
        # Jamais de repli sur cmd.exe : il couperait le message système et perdrait les options d'isolement.
        exe = Path(trouve).parent / 'node_modules' / '@anthropic-ai' / 'claude-code' / 'bin' / 'claude.exe'
        if not exe.is_file():
            raise ErreurFabrication('claude.exe introuvable à côté de %s (passer --claude CHEMIN de claude.exe)' % trouve)
        return [str(exe)]
    return [trouve]


def options_agent(systeme):
    """Arguments d'un agent après la commande : modèle, aucun outil, message système, isolement (D98)."""
    return ['-p', '--model', 'sonnet', '--tools', '', '--system-prompt', systeme] + OPTIONS_CLAUDE


def environnement_agent():
    """Environnement d'un agent : sans les variables de la session Claude Code qui le lance ni ce qui changerait le
    modèle ou l'adresse de l'API ; CLAUDE.md et mémoire automatique désactivés ; jamais de mise à jour de Claude Code
    (elle remplace claude.exe pendant que les autres agents le lancent)."""
    retirees = ('CLAUDECODE', 'CLAUDE_EFFORT', 'ANTHROPIC_BASE_URL', 'ANTHROPIC_MODEL', 'ANTHROPIC_SMALL_FAST_MODEL')
    env = {cle: valeur for cle, valeur in os.environ.items()
           if not cle.startswith(('CLAUDE_CODE_', 'ANTHROPIC_DEFAULT_')) and cle not in retirees}
    env.update({'CLAUDE_CODE_DISABLE_CLAUDE_MDS': '1', 'CLAUDE_CODE_DISABLE_AUTO_MEMORY': '1', 'DISABLE_AUTOUPDATER': '1'})
    return env


def empreinte(systeme, utilisateur):
    """Empreinte d'une requête : options de l'agent (sans le message système) et les deux messages. Une option
    changée invalide toutes les réponses gardées."""
    options = json.dumps(options_agent(''), ensure_ascii=False)
    return hashlib.sha256((options + '\x00' + systeme + '\x00' + utilisateur).encode('utf-8')).hexdigest()


def lire_trace(dossier, ot):
    chemin = dossier / (ot + '.json')
    return json.loads(chemin.read_text(encoding='utf-8')) if chemin.is_file() else {'ot': ot, 'appels': []}


def ecrire_trace(dossier, trace):
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / (trace['ot'] + '.json')).write_text(json.dumps(trace, ensure_ascii=False, indent=1), encoding='utf-8')


def reponse_valable(appel):
    """Une réponse gardée n'est reprise que si elle venait de Sonnet, en un seul tour, sans erreur."""
    modeles = [m.strip() for m in str(appel.get('modele', '')).split(',') if m.strip()]
    return (not appel.get('erreur') and bool(modeles) and all('sonnet' in m.lower() for m in modeles)
            and appel.get('tours') == 1)


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

    def __init__(self, commande, traces, delai=DELAI_APPEL_S, attente_commande=ATTENTE_COMMANDE_S, reprise_duree=1.0,
                 reprise_seule=False):
        self.commande = commande
        self.traces = traces
        self.delai = delai
        self.reprise_duree = reprise_duree        # fraction de la durée d'origine d'une réponse reprise
        self.reprise_seule = reprise_seule        # jamais d'agent : une requête absente des traces arrête tout
        self.attente_commande = attente_commande
        self.appels = 0
        self.reprises = 0
        self.relances = 0
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
        relance = MARQUE_RELANCE in utilisateur        # relance avec la raison : une requête de plus pour le même OT
        self.relances += relance
        trace = lire_trace(self.traces, ot)
        deja = next((a for a in reversed(trace['appels']) if a.get('empreinte') == cle and not a.get('reprise')
                     and a.get('contenu') and reponse_valable(a)), None)
        if deja:
            self.reprises += 1
            trace['appels'].append({'empreinte': cle, 'reprise': True, 'relance': relance,
                                    'date': datetime.now().isoformat(timespec='seconds')})
            ecrire_trace(self.traces, trace)
            # Rendue après sa durée d'origine : les réponses arrivent dans le même ordre, les mêmes requêtes suivent.
            if self.reprise_duree > 0:
                await asyncio.sleep(float(deja.get('duree_s') or 0) * self.reprise_duree)
            return {'contenu': deja['contenu'], 'modele': deja['modele']}
        if self.reprise_seule:
            self.arret = self.arret or '%s : requête absente des traces (reprise seule : aucun agent lancé)' % ot
            raise ErreurFabrication(self.arret)
        try:
            return await self.appeler_agent(ot, systeme, utilisateur, cle, trace)
        except ErreurFabrication as erreur:
            self.arret = self.arret or '%s : %s' % (ot, erreur)
            raise

    async def lancer_agent(self, systeme):
        """Processus d'un agent. Commande introuvable (claude.exe retiré par une mise à jour de Claude Code faite hors
        de l'outil) : on attend qu'elle revienne, attente_commande secondes au plus, et on relance une fois — aucun appel
        n'a encore été fait."""
        arguments = self.commande + options_agent(systeme)
        for essai in (1, 2):
            try:
                return await asyncio.create_subprocess_exec(
                    *arguments, cwd=str(self.dossier_neutre), env=environnement_agent(),
                    stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            except FileNotFoundError:
                if essai == 2:
                    raise
                fin = time.time() + self.attente_commande
                while not Path(arguments[0]).is_file() and time.time() < fin:
                    await asyncio.sleep(1)

    async def appeler_agent(self, ot, systeme, utilisateur, cle, trace):
        depart = time.time()
        appel = {'empreinte': cle, 'reprise': False, 'relance': MARQUE_RELANCE in utilisateur,
                 'date': datetime.now().isoformat(timespec='seconds'), 'systeme': systeme, 'utilisateur': utilisateur}
        trace['appels'].append(appel)
        self.appels += 1                          # tout agent lancé compte, même arrêté ensuite
        try:
            processus = await self.lancer_agent(systeme)
        except OSError as erreur:
            appel['erreur'] = 'agent injoignable : %s' % erreur
            ecrire_trace(self.traces, trace)
            raise ErreurFabrication(appel['erreur'])
        try:
            sortie, erreurs = await asyncio.wait_for(processus.communicate(utilisateur.encode('utf-8')), self.delai)
        except asyncio.TimeoutError:
            processus.kill()                      # l'agent ne survit pas au délai
            await processus.wait()
            appel.update({'erreur': 'délai dépassé (%d s)' % self.delai, 'duree_s': round(time.time() - depart, 2)})
            ecrire_trace(self.traces, trace)
            raise ErreurFabrication('agent injoignable : délai dépassé (%d s)' % self.delai)
        brute = sortie.decode('utf-8', 'replace')
        appel.update({'reponse_brute': brute, 'stderr': erreurs.decode('utf-8', 'replace')[-2000:],
                      'code_retour': processus.returncode, 'duree_s': round(time.time() - depart, 2)})
        try:
            donnees = json.loads(brute)
            appel.update({'modele': ', '.join(sorted((donnees.get('modelUsage') or {}).keys())),
                          'tours': donnees.get('num_turns'), 'jetons': donnees.get('usage'),
                          'cout_usd': donnees.get('total_cost_usd'), 'duree_api_ms': donnees.get('duration_api_ms')})
            self.cout += float(donnees.get('total_cost_usd') or 0)
            modeles = controler_reponse(donnees)
        except ValueError:
            appel['erreur'] = 'réponse illisible'
            ecrire_trace(self.traces, trace)
            raise ErreurFabrication('réponse illisible (code %s) : %s' % (processus.returncode, brute[:300] or appel['stderr'][-300:]))
        except ErreurFabrication as erreur:
            appel['erreur'] = str(erreur)
            ecrire_trace(self.traces, trace)
            raise
        appel['contenu'] = donnees.get('result') or ''
        ecrire_trace(self.traces, trace)
        return {'contenu': appel['contenu'], 'modele': modeles[0]}

    def noter_verdicts(self, entrees):
        """Verdict de Prévo sur la dernière réponse de chaque OT (CS105) : statut de son entrée, raisons, motif."""
        for entree in entrees:
            chemin = self.traces / (entree['ot'] + '.json')
            if not chemin.is_file():
                continue
            trace = lire_trace(self.traces, entree['ot'])
            trace['verdict'] = {'entree': entree['id'], 'statut': entree['statut'], 'raisons': entree['raisons'],
                                'motif': entree['motif']}
            ecrire_trace(self.traces, trace)

    async def progres(self, etat):
        faits = (etat.get('acceptees') or 0) + (etat.get('rien') or 0)
        resume = (faits // 25, etat.get('refusees'), etat.get('rejouees'), etat.get('restants') == 0)
        if resume != self.dernier:
            self.dernier = resume
            ecrire('  en cours %(enCours)s · restants %(restants)s · acceptées %(acceptees)s · rien %(rien)s · '
                   'refusées %(refusees)s · rejouées %(rejouees)s' % etat)


ENTREES_JS = """() => Donnees.lignes('wiki_journal').filter((e) => e.nature === 'ingestion')
  .map((e) => ({ id: e.id, ot: e.ot_id, statut: e.statut, raisons: e.raisons, motif: e.motif }))"""


def empreinte_donnees(tables):
    """Empreinte des données de la démo dont part une fabrication (toutes les tables, celles du wiki réduites à leur
    en-tête) : le temps 1 la garde, --suite la compare."""
    return hashlib.sha256(json.dumps(sorted(tables.items()), ensure_ascii=False).encode('utf-8')).hexdigest()


def empreinte_consigne(systeme):
    """Empreinte de la consigne : options d'un agent et message système d'ingestionWiki (le même pour chaque OT)."""
    return hashlib.sha256((json.dumps(options_agent(''), ensure_ascii=False) + '\x00' + systeme).encode('utf-8')).hexdigest()


def lire_depart(dossier, sortie, donnees):
    """État du temps 1 dont part --suite → { temps (temps-1.json), tables (wiki_pages, wiki_journal avant les
    validations) } ; arrêt clair sans résultat de temps 1, ou s'il a été fabriqué sur d'autres données de démo."""
    if dossier.resolve() == sortie.resolve():
        raise ErreurFabrication('--suite : --resultat doit être un autre dossier que celui du temps 1 (%s)' % dossier)
    etat = dossier / DOSSIER_ETAT
    if not (dossier / FICHIER_TEMPS_1).is_file() or not all((etat / (t + '.csv')).is_file() for t in FICHIERS_FIGES):
        raise ErreurFabrication('--suite : aucun résultat de temps 1 dans %s (%s et %s/ absents) : lancer d\'abord '
                                '« py outils/wiki_demo.py fabriquer --limite 40 »' % (dossier, FICHIER_TEMPS_1, DOSSIER_ETAT))
    temps = json.loads((dossier / FICHIER_TEMPS_1).read_text(encoding='utf-8'))
    if temps.get('empreinte_donnees') != donnees:
        raise ErreurFabrication('--suite : le temps 1 de %s a été fabriqué sur d\'autres données de démo que celles-ci '
                                '(empreinte différente) : rejouer le temps 1 sur ces données' % dossier)
    return {'temps': temps, 'tables': {t: (etat / (t + '.csv')).read_bytes().decode('utf-8-sig') for t in FICHIERS_FIGES}}


def effacer_temps_1(dossier):
    """Ce qu'écrit un temps 1 (jamais l'estimation ni un autre fichier) : retiré au départ, pour qu'un temps 1 arrêté ne
    laisse jamais l'état d'un temps 1 précédent à la suite."""
    for nom in (FICHIER_TEMPS_1, RELECTURE_TEMPS_1):
        (dossier / nom).unlink(missing_ok=True)
    shutil.rmtree(dossier / DOSSIER_ETAT, ignore_errors=True)


def ecrire_temps_1(dossier, etat, temps):
    """État de départ de la suite (tables du wiki avant les validations) puis temps-1.json, écrit en dernier."""
    (dossier / DOSSIER_ETAT).mkdir(parents=True, exist_ok=True)
    for table, texte in etat.items():
        (dossier / DOSSIER_ETAT / (table + '.csv')).write_bytes(texte.encode('utf-8'))
    (dossier / FICHIER_TEMPS_1).write_text(json.dumps(temps, ensure_ascii=False, indent=1), encoding='utf-8')


async def fabriquer_async(arguments):
    commande = commande_claude(arguments.claude)
    sortie = Path(arguments.resultat)
    temps_1 = bool(arguments.limite)              # premier temps (D115) : sa suite repartira de son état
    tables = lire_tables(arguments.demo, sans_wiki=True)
    donnees = empreinte_donnees(tables)
    depart = lire_depart(Path(arguments.depart), sortie, donnees) if arguments.suite else None
    if depart:
        tables.update(depart['tables'])
    for table in FICHIERS_FIGES:                  # jamais de résultat périmé à figer après une fabrication arrêtée
        (sortie / (table + '.csv')).unlink(missing_ok=True)
    if temps_1:
        effacer_temps_1(sortie)
    fabrique = Fabrique(commande, Path(arguments.traces), arguments.delai_appel, reprise_duree=arguments.reprise_duree,
                        reprise_seule=arguments.reprise_seule)
    from playwright.async_api import async_playwright
    async with async_playwright() as playwright:
        navigateur, page, erreurs = await ouvrir_page(playwright, tables)
        try:
            consigne = empreinte_consigne(await page.evaluate(CONSIGNE_JS))
            deja = set(await page.evaluate(DEJA_JS))
            if depart:
                if depart['temps'].get('empreinte_consigne') != consigne:
                    raise ErreurFabrication('--suite : la consigne (message système d\'ingestionWiki ou options d\'un agent) a '
                                            'changé depuis le temps 1 de %s : rejouer le temps 1 (les réponses à des requêtes '
                                            'identiques sont reprises des traces, sans nouvel appel)' % arguments.depart)
                manquants = [ot for ot in depart['temps'].get('ot', []) if ot not in deja]
                if manquants:
                    raise ErreurFabrication('--suite : état du temps 1 incomplet (%s) : OT sans entrée au journal : %s'
                                            % (arguments.depart, ', '.join(manquants[:10])))
                ecrire('Suite du temps 1 (%s) : %d OT déjà intégrés, repris tels quels, sans nouvel appel.'
                       % (arguments.depart, len(deja)))
            await page.expose_function('appelerClaude', fabrique.appeler)
            await page.expose_function('progresFabrication', fabrique.progres)
            ecrire('Fabrication du wiki de démo : %s agent(s), commande %s' % (arguments.agents, ' '.join(commande)))
            bilan = await page.evaluate(TRAITER_JS, {'agents': arguments.agents, 'limite': arguments.limite or 0})
            fabrique.noter_verdicts(await page.evaluate(ENTREES_JS))
            bilan['relances'] = [ot for ot in bilan['relances'] if ot not in deja]
            ecrire('OT : %(ot)s (%(ajoutes)s mis en file) · acceptées %(acceptees)s · rien à ajouter %(rien)s · refusées '
                   '%(refusees)s · rejouées %(rejouees)s · encore en file %(enFile)s' % bilan)
            ecrire('Agents lancés : %d · réponses reprises des traces : %d · relances avec la raison : %d · coût : %.2f $'
                   % (fabrique.appels, fabrique.reprises, fabrique.relances, fabrique.cout))
            if bilan['relances']:
                ecrire('Acceptées à la relance avec la raison : %s' % ', '.join(bilan['relances']))
            if fabrique.arret or bilan['erreur']:
                ecrire('ARRÊT : %s' % (fabrique.arret or bilan['erreur']))
                return 1
            if bilan['refusees']:
                for ot, raisons in bilan['refus']:
                    ecrire('REFUSÉE %s :\n    %s' % (ot, '\n    '.join(str(raisons).splitlines())))
                ecrire('ARRÊT : réponse refusée par les contrôles de Prévo, même à sa relance avec la raison (défaut de la '
                       'fonction à corriger, puis relancer).')
                return 1
            if bilan['enFile']:
                ecrire('ARRÊT : %d OT encore en file.' % bilan['enFile'])
                return 1
            # Temps 1 : l'état d'où repartira la suite est pris AVANT les validations, que la suite fera toutes à la fin,
            # comme une fabrication d'un seul tenant (les pages créées gardent leur clé TITRE:… d'ici là).
            etat = await page.evaluate(TABLES_WIKI_JS) if temps_1 else None
            jours = arguments.a_valider_jours
            if jours is None:
                jours = await page.evaluate('Wiki.SEUILS.demoAValiderJours')
            limite = (date.fromisoformat(DATE_REFERENCE) - timedelta(days=jours)).isoformat()
            resultat = await page.evaluate(VALIDER_JS, limite)
            fabrique.noter_verdicts(await page.evaluate(ENTREES_JS))
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
            sortie.mkdir(parents=True, exist_ok=True)
            for table, texte in resultat['fichiers'].items():
                (sortie / (table + '.csv')).write_bytes(texte.encode('utf-8'))
            if not temps_1:
                ecrire('Intégrité ok. Résultat : %s (puis : py outils/wiki_demo.py figer)' % sortie)
                return 0
            temps = {'temps': 1, 'limite': arguments.limite, 'ot': bilan['ids'], 'empreinte_donnees': donnees,
                     'empreinte_consigne': consigne, 'fabrique_le': datetime.now().isoformat(timespec='seconds'),
                     'agents': arguments.agents, 'agents_lances': fabrique.appels, 'reprises': fabrique.reprises,
                     'relances': fabrique.relances, 'cout_usd': round(fabrique.cout, 4),
                     'bilan': {cle: bilan[cle] for cle in ('acceptees', 'rien', 'rejouees')},
                     'acceptees_a_la_relance': bilan['relances']}
            lu = await page.evaluate(RELECTURE_JS)
            (sortie / RELECTURE_TEMPS_1).write_text(document_relecture(lu, temps), encoding='utf-8')
            ecrire_temps_1(sortie, etat, temps)
            ecrire('Intégrité ok. Temps 1 : %s (relecture : %s ; suite : py outils/wiki_demo.py fabriquer --suite)'
                   % (sortie, sortie / RELECTURE_TEMPS_1))
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


def espaces(texte):
    return ' '.join(str(texte or '').split())


def reponse_acceptee(appels, entree):
    """Réponse d'agent dont vient une entrée du journal figé → (appel, défaut). Sans raisons au journal : la dernière
    réponse Sonnet valable à une requête d'origine. Acceptée à la relance (l'entrée garde les raisons du premier refus,
    §20.5) : la dernière réponse valable à une relance qui cite chacune de ces raisons, précédée dans la trace de la
    réponse refusée à la requête d'origine (le message de la relance commence par le message d'origine)."""
    valables = [a for a in appels if not a.get('reprise') and a.get('contenu') and reponse_valable(a)]
    raisons = [espaces(raison) for raison in str(entree.get('raisons') or '').splitlines() if raison.strip()]
    if not raisons:
        retenue = next((a for a in reversed(valables) if MARQUE_RELANCE not in a.get('utilisateur', '')), None)
        return retenue, None if retenue else 'aucune réponse Sonnet à sa requête dans les traces'
    for rang in range(len(valables) - 1, -1, -1):
        origine, marque, suite = valables[rang].get('utilisateur', '').partition(MARQUE_RELANCE)
        if marque and all(raison in espaces(suite) for raison in raisons) \
                and any(a.get('utilisateur') == origine for a in valables[:rang]):
            return valables[rang], None
    return None, ('acceptée à la relance (raisons du premier refus au journal), sans la réponse refusée puis la relance '
                  'qui cite ces raisons dans les traces')


def verifier(arguments):
    defauts = []
    appels = 0
    sans_reponse = 0
    traces = {}
    for chemin in sorted(Path(arguments.traces).glob('*.json')):
        traces[chemin.stem] = json.loads(chemin.read_text(encoding='utf-8')).get('appels', [])
        for appel in traces[chemin.stem]:
            if appel.get('reprise'):
                continue
            appels += 1
            if 'modele' not in appel:            # agent coupé avant de répondre (délai, lancement impossible)
                sans_reponse += 1
                continue
            if not reponse_valable(appel):
                defauts.append('%s : réponse de %s en %s tour(s)%s' % (chemin.stem, appel.get('modele') or 'modèle inconnu',
                               appel.get('tours'), (' (' + appel['erreur'] + ')') if appel.get('erreur') else ''))
    journal = lignes_csv((Path(arguments.wiki) / FICHIERS_FIGES['wiki_journal']).read_bytes().decode('utf-8'))
    entrees = [ligne for ligne in journal if ligne.get('nature') == 'ingestion']
    integres = {ligne['ot_id'] for ligne in entrees}
    # Chaque entrée reliée à la réponse que Prévo a acceptée (relance comprise), du modèle noté sur l'entrée.
    sans_trace = []
    for entree in sorted(entrees, key=lambda ligne: ligne['ot_id']):
        appel, defaut = reponse_acceptee(traces.get(entree['ot_id'], []), entree)
        if defaut and not entree.get('raisons'):
            sans_trace.append(entree['ot_id'])
        elif defaut:
            defauts.append('%s : %s' % (entree['ot_id'], defaut))
        elif entree.get('modele') not in [m.strip() for m in str(appel.get('modele', '')).split(',')]:
            defauts.append('%s : modèle %s au journal figé, %s dans la réponse acceptée' % (entree['ot_id'],
                           entree.get('modele') or 'absent', appel.get('modele')))
    if sans_trace:
        defauts.append('entrées du journal figé sans réponse Sonnet dans les traces : %s' % ', '.join(sans_trace))
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
    ecrire('Traces : %d appels d\'agents (%d sans réponse) · modèles du journal figé : %s · OT clôturés administrativement : '
           '%d, intégrés : %d' % (appels, sans_reponse, ', '.join(modeles) or 'aucun', len(clotures),
                                  len([ot for ot in clotures if ot in integres])))
    for defaut in defauts:
        ecrire('DÉFAUT : ' + defaut)
    ecrire('Vérification : ' + ('OK' if not defauts else 'ÉCHEC'))
    return 0 if not defauts else 1


RELECTURE_JS = """() => {
  // Refonte 2 (§20.12) : textes d'une machine, d'un article, et savoir-faire ; plus de pages de mode.
  const types = ['équipement', 'composant', 'savoir-faire'];
  const entrees = Donnees.lignes('wiki_journal').filter((e) => e.nature === 'ingestion');
  const entreeDe = new Map(entrees.map((e) => [e.ot_id, e]));
  const detail = (id) => { const o = Donnees.trouver('ordres_travail', id) || {}; const e = entreeDe.get(id) || {};
    return { id, date: o.date_fin, titre: o.titre, compteRendu: o.compte_rendu, astuce: o.astuce, statut: e.statut || '',
      essais: Number(e.essais) || 0, raisons: e.raisons || '', motif: e.motif || '' }; };
  const ids = new Set(Donnees.lignes('wiki_pages').filter((l) => l.statut !== 'archivée' && l.texte)
    .map((l) => Wiki.page(l.id) && Wiki.page(l.id).id).filter(Boolean));
  const pages = Array.from(ids).map((id) => Wiki.page(id, { responsable: true })).filter((p) => types.includes(p.type))
    .map((p) => ({ id: p.id, type: p.type, titre: p.titre, mere: p.mere ? p.mere.titre : '', origine: p.origine,
      modele: p.modele, validePar: p.validePar, valideLe: p.valideLe, phrases: Wiki.phrasesDe(p.texte).length,
      rubriques: Wiki.lireTexte(p.texte).rubriques.map((r) => ({ nom: r.nom, phrases: r.phrases.map((f) => ({
        texte: f.texte.replace(/\\s*\\[OT-\\d{4}-\\d{4,}\\]/g, '').trim(), ot: f.ot })) })),
      contradictions: p.contradictions, enAttente: p.enAttente,
      ot: Array.from(new Set(Wiki.citationsDe(p.texte))).map(detail) }));
  pages.sort((a, b) => types.indexOf(a.type) - types.indexOf(b.type) || b.ot.length - a.ot.length
    || b.phrases - a.phrases || (a.titre < b.titre ? -1 : 1));
  // Propositions laissées « à valider » : elles seront visibles dans la démo (profil responsable), donc relues aussi.
  const lire = (valeur) => { try { return JSON.parse(valeur || '[]') || []; } catch (e) { return []; } };
  const attente = entrees.filter((e) => e.statut === 'à valider').sort((a, b) => Number(a.ordre) - Number(b.ordre)).map((e) =>
    Object.assign(detail(e.ot_id), { entree: e.id, anterieure: e.anterieure === '1', modele: e.modele,
      contradictions: lire(e.contradictions), changements: lire(e.changements).map((c) => ({ titre: c.titre, type: c.type,
        creation: Boolean(c.creation), avant: c.avant || '', apres: c.apres || '' })) }));
  const parDate = (a, b) => (a.date < b.date ? -1 : (a.date > b.date ? 1 : (a.id < b.id ? -1 : 1)));
  return { pages, attente,
    rien: entrees.filter((e) => e.statut === 'rien à ajouter').map((e) => detail(e.ot_id)).sort(parDate),
    relances: entrees.filter((e) => Number(e.essais) > 1 || e.motif || e.statut === 'refusée').map((e) => detail(e.ot_id))
      .sort(parDate) };
}"""
TITRES_RELECTURE = {'équipement': 'Machines — « En bref » et « Astuces »', 'composant': 'Articles — « À quoi il sert »',
                    'savoir-faire': 'Savoir-faire'}


async def relecture_async(dossier):
    from playwright.async_api import async_playwright
    async with async_playwright() as playwright:
        navigateur, page, _erreurs = await ouvrir_page(playwright, lire_tables(dossier, sans_wiki=False))
        try:
            return await page.evaluate(RELECTURE_JS)
        finally:
            await navigateur.close()


def verdict_html(ot):
    """Refus, relance ou rejeu d'un OT (son entrée du journal), '' s'il est passé du premier coup."""
    e = html.escape
    morceaux = []
    if ot['statut'] == 'refusée':
        morceaux.append('<b>Refusée</b> (%d essais) : %s' % (ot['essais'], e(ot['raisons'])))
    elif ot['essais'] > 1 and ot['raisons']:
        morceaux.append('<b>Relancée avec la raison</b> (%d essais) — premier refus : %s' % (ot['essais'], e(ot['raisons'])))
    if ot['motif']:
        morceaux.append('<b>Rejouée</b> : %s' % e(ot['motif']))
    return '<br><span class="verdict">%s</span>' % '<br>'.join(morceaux) if morceaux else ''


def ot_html(ot):
    e = html.escape
    return '<li id="%s"><b>%s</b> (%s) %s<br>%s%s%s</li>' % (e(ot['id']), e(ot['id']), e(ot['date'] or ''), e(ot['titre'] or ''),
                                                            e(ot['compteRendu'] or ''),
                                                            ('<br><i>Astuce : %s</i>' % e(ot['astuce'])) if ot['astuce'] else '',
                                                            verdict_html(ot))


def page_html(page):
    e = html.escape
    lignes = ['<section class="page"><h3>%s <small>%s · %d OT · %d phrases%s</small></h3>'
              % (e(page['titre']), e(page['type']), len(page['ot']), page['phrases'],
                 (' · sous-page de « %s »' % e(page['mere'])) if page['mere'] else '')]
    for contradiction in page['contradictions']:
        lignes.append('<p class="contradiction"><b>À trancher</b> — « %s » ; %s : %s (%s)</p>'
                      % (e(contradiction['phrase']), e(contradiction['libelle']), e(contradiction['observation']),
                         e(contradiction['otSource'])))
    if page['enAttente']:
        lignes.append('<p class="attente">Proposition à valider : %s</p>' % e(', '.join(a['ot'] for a in page['enAttente'])))
    lignes.append('<p class="origine">Origine : %s (%s) — validé par %s le %s</p>'
                  % (e(page['origine'] or '—'), e(page['modele'] or '—'), e(page['validePar'] or '—'), e(page['valideLe'] or '—')))
    for rubrique in page['rubriques']:
        lignes.append('<h4>%s</h4><ul>' % e(rubrique['nom']))
        lignes.extend('<li>%s <span class="ot">%s</span></li>' % (e(phrase['texte']), ' '.join(
            '<a href="#%s">%s</a>' % (e(ot), e(ot)) for ot in phrase['ot'])) for phrase in rubrique['phrases'])
        lignes.append('</ul>')
    relances = [ot for ot in page['ot'] if verdict_html(ot)]
    lignes.append('<details><summary>OT cités (%d)%s</summary><ul>' % (len(page['ot']), (' — dont %d relancé(s) ou rejoué(s)'
                  % len(relances)) if relances else ''))
    lignes.extend(ot_html(ot) for ot in page['ot'])
    lignes.append('</ul></details></section>')
    return '\n'.join(lignes)


def attente_html(entree):
    e = html.escape
    lignes = ['<section class="page attente-proposition"><h3>%s — %s <small>%s · intervention du %s%s</small></h3>'
              % (e(entree['id']), e(entree['titre'] or ''), e(entree['entree']), e(entree['date'] or ''),
                 ' · intervention antérieure' if entree['anterieure'] else '')]
    for contradiction in entree['contradictions']:
        lignes.append('<p class="contradiction"><b>Contradiction</b> sur « %s » : « %s » — %s</p>'
                      % (e(contradiction.get('page', '')), e(contradiction.get('phrase', '')), e(contradiction.get('observation', ''))))
    lignes.append('<p>%s%s%s</p>' % (e(entree['compteRendu'] or ''),
                  ('<br><i>Astuce : %s</i>' % e(entree['astuce'])) if entree['astuce'] else '', verdict_html(entree)))
    for changement in entree['changements']:
        lignes.append('<h4>%s « %s » (%s)</h4><pre>%s</pre>' % ('Page créée' if changement['creation'] else 'Page modifiée',
                      e(changement['titre']), e(changement['type']), e(changement['apres'])))
        if changement['avant']:
            lignes.append('<details><summary>Texte d\'avant</summary><pre>%s</pre></details>' % e(changement['avant']))
    lignes.append('</section>')
    return '\n'.join(lignes)


def document_relecture(lu, temps=None):
    """Page de relecture : propositions à valider, puis les textes par type (refonte 2), les plus riches d'abord
    (OT cités distincts, puis phrases), chacun avec ses OT et leurs refus, relances ou rejeux ; puis les OT relancés et
    ceux « rien à ajouter ». temps : temps-1.json (bilan et coût du temps 1, en tête)."""
    e = html.escape
    pages = lu['pages']
    corps = []
    if temps:
        corps.append('<p class="bilan">Temps 1 : %d premiers OT par date d\'intervention · acceptés %d · rien à ajouter %d · '
                     'rejoués %d · agents lancés %d (dont %d relances avec la raison) · réponses reprises des traces %d · '
                     'coût %.2f $.</p>' % (len(temps['ot']), temps['bilan']['acceptees'], temps['bilan']['rien'],
                                          temps['bilan']['rejouees'], temps['agents_lances'], temps['relances'],
                                          temps['reprises'], temps['cout_usd']))
    corps.append('<h2>Propositions à valider (%d)</h2><p>Laissées « à valider » dans la démo (les derniers jours '
                 'd\'intervention) : le profil responsable les verra.</p>' % len(lu['attente']))
    corps.extend(attente_html(entree) for entree in lu['attente'])
    for type_page, titre in TITRES_RELECTURE.items():
        du_type = [p for p in pages if p['type'] == type_page]
        corps.append('<h2>%s (%d)</h2>' % (titre, len(du_type)))
        corps.extend(page_html(p) for p in du_type)
    corps.append('<h2>Refus, relances et rejeux (%d)</h2><ul>' % len(lu['relances']))
    corps.extend(ot_html(ot) for ot in lu['relances'])
    corps.append('</ul><h2>Rien à ajouter (%d)</h2><p>OT que l\'IA a jugés sans rien à apprendre : à vérifier aussi.</p><ul>'
                 % len(lu['rien']))
    corps.extend(ot_html(ot) for ot in lu['rien'])
    corps.append('</ul>')
    titre = 'Wiki de démo — relecture du temps 1' if temps else 'Wiki de démo — relecture'
    return ('<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<title>%s</title><style>body{font-family:system-ui,sans-serif;max-width:60rem;margin:auto;padding:1rem;'
            'color:#1b1f24}pre{white-space:pre-wrap;background:#f4f6f8;padding:.6rem}.page{border-top:1px solid #ccd;'
            'padding:.4rem 0}.contradiction{background:#fff3cd;padding:.4rem}.attente{color:#6b4e00}small,.ot{color:#555}'
            '.verdict{color:#8a1c1c}.bilan{background:#eef4ff;padding:.6rem}h4{margin:.6rem 0 .2rem}</style></head><body>'
            '<h1>%s</h1><p>Textes par type, les plus riches d\'abord (OT cités distincts, puis phrases), chacun avec ses OT '
            'et leurs refus ou relances. Ce qui est refusé se corrige dans la fonction, puis la fabrication est rejouée ; '
            'aucun texte n\'est retouché à la main.</p>' % (e(titre), e(titre)) + '\n'.join(corps) + '</body></html>')


def relecture(arguments):
    lu = asyncio.run(relecture_async(arguments.demo))
    sortie = Path(arguments.sortie)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(document_relecture(lu), encoding='utf-8')
    ecrire('Relecture : %s (%d pages, %d propositions à valider)' % (sortie, len(lu['pages']), len(lu['attente'])))
    return 0


def lire_arguments(argv):
    analyseur = argparse.ArgumentParser(description='Fabrication du wiki de démo de Prévo (Claude Sonnet, claude -p).')
    sous = analyseur.add_subparsers(dest='action', required=True)
    commun = argparse.ArgumentParser(add_help=False)
    commun.add_argument('--demo', default=str(DOSSIER_DEMO), help='dossier du jeu de démo (défaut : donnees/demo)')
    commun.add_argument('--traces', default=str(DOSSIER_TRACES), help='dossier des traces des agents')
    commun.add_argument('--resultat', default=None,
                        help='dossier du résultat (défaut : .chantier/wiki-demo/resultat ; fabriquer --limite : '
                             '.chantier/wiki-demo/temps-1)')
    commun.add_argument('--wiki', default=str(DOSSIER_FIGE), help='dossier des fichiers figés (défaut : outils)')
    fabrication = sous.add_parser('fabriquer', parents=[commun], help='fabrique le wiki de démo')
    fabrication.add_argument('--agents', type=int, default=5, help='agents en même temps (1 à 5, défaut 5)')
    fabrication.add_argument('--claude', default='', help='commande claude (essais : un script .py)')
    fabrication.add_argument('--limite', type=int, default=0,
                             help='temps 1 : seulement les N premiers OT par date d\'intervention ; garde aussi l\'état '
                                  'de départ de la suite et la page de relecture dans le dossier du résultat')
    fabrication.add_argument('--suite', action='store_true',
                             help='temps 2 : repart de l\'état du temps 1 (--depart) et ne traite que les OT restants')
    fabrication.add_argument('--depart', default=str(DOSSIER_TEMPS_1),
                             help='--suite : dossier du temps 1 (défaut : .chantier/wiki-demo/temps-1)')
    fabrication.add_argument('--a-valider-jours', type=int, default=None,
                             help='jours laissés « à valider » (défaut : Wiki.SEUILS.demoAValiderJours)')
    fabrication.add_argument('--delai-appel', type=int, default=DELAI_APPEL_S, help='délai d\'un agent en secondes')
    fabrication.add_argument('--reprise-duree', type=float, default=1.0,
                             help='réponse reprise rendue après cette fraction de sa durée d\'origine (défaut 1 : même '
                                  'ordre d\'arrivée, mêmes requêtes avec plusieurs agents ; 0 : tout de suite)')
    fabrication.add_argument('--reprise-seule', action='store_true',
                             help='jamais d\'agent : une requête absente des traces arrête la fabrication')
    sous.add_parser('figer', parents=[commun], help='copie le résultat dans les fichiers figés')
    sous.add_parser('verifier', parents=[commun], help='vérifie traces, journal figé et intégrité')
    lecture = sous.add_parser('relecture', parents=[commun], help='page de relecture du wiki de démo')
    lecture.add_argument('--sortie', default=str(DOSSIER_TRAVAIL / 'relecture.html'))
    arguments = analyseur.parse_args(argv)
    if arguments.action == 'fabriquer' and not 1 <= arguments.agents <= 5:
        analyseur.error('--agents : de 1 à 5')
    if arguments.action == 'fabriquer' and arguments.suite and arguments.limite:
        analyseur.error('--suite et --limite ne vont pas ensemble : la suite traite tous les OT restants')
    if arguments.resultat is None:
        temps_1 = arguments.action == 'fabriquer' and arguments.limite
        arguments.resultat = str(DOSSIER_TEMPS_1 if temps_1 else DOSSIER_RESULTAT)
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
