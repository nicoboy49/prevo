"""Faux `claude` (la commande de Claude Code) pour les essais de outils/wiki_demo.py : mêmes options, réponse JSON
de `claude -p --output-format json`, dont le texte est construit par tests/faux_wiki.py (variante faux-textes : tous
les textes de la refonte 2, §20.12) à partir du seul message reçu sur l'entrée standard.

Variables d'environnement :
    FAUX_CLAUDE_MODE     sonnet (défaut) | opus (un autre modèle) | deux-tours | refus (réponse que Prévo refuse :
                         un OT cité hors de la liste, relance comprise) | relance (réponse que Prévo refuse — une
                         phrase sans OT — puis, à la relance avec la raison, une réponse valable) | erreur (réponse en
                         erreur) | lent (répond après 8 s)
    FAUX_CLAUDE_RELANCE  mode relance : OT concernés, séparés par des virgules (défaut : tous)
    FAUX_CLAUDE_DELAIS   1 : chaque réponse attend de 0 à 1,6 s selon le numéro de l'OT (réponses dans le désordre,
                         comme le vrai modèle)
    FAUX_CLAUDE_TRACES   dossier : chaque appel y écrit appel-<identifiant>.json (arguments, entrée standard et
                         variables CLAUDE*/ANTHROPIC* reçus)
"""
import json
import os
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))       # tests/
from faux_wiki import MOTIF_OT_INGERE, est_relance, reponse_ingestion  # noqa: E402


def variante(mode, entree):
    """Variante du faux modèle (tests/faux_wiki.py) selon le mode et le message reçu."""
    if mode == 'refus':
        return 'faux-invente'
    if mode == 'relance' and not est_relance(entree):
        concernes = [ot.strip() for ot in os.environ.get('FAUX_CLAUDE_RELANCE', '').split(',') if ot.strip()]
        if not concernes or MOTIF_OT_INGERE.search(entree).group(1) in concernes:
            return 'faux-sans-ot'
    return 'faux-textes'


def principal():
    arguments = sys.argv[1:]
    entree = sys.stdin.buffer.read().decode('utf-8')
    dossier = os.environ.get('FAUX_CLAUDE_TRACES')
    if dossier:
        Path(dossier).mkdir(parents=True, exist_ok=True)
        (Path(dossier) / ('appel-%s.json' % uuid.uuid4().hex)).write_text(
            json.dumps({'arguments': arguments, 'entree': entree, 'environnement': {cle: valeur for cle, valeur in os.environ.items()
                        if cle.startswith(('CLAUDE', 'ANTHROPIC', 'DISABLE_AUTOUPDATER'))}}, ensure_ascii=False), encoding='utf-8')
    mode = os.environ.get('FAUX_CLAUDE_MODE', 'sonnet')
    if os.environ.get('FAUX_CLAUDE_DELAIS') == '1':
        trouve = MOTIF_OT_INGERE.search(entree)
        time.sleep(((int(trouve.group(1)[-4:]) * 7) % 5) * 0.4 if trouve else 0)
    if mode == 'lent':                            # répond après 8 s ; « fini » prouve qu'on ne l'a pas coupé
        time.sleep(8)
        if dossier:
            (Path(dossier) / ('fini-%s' % uuid.uuid4().hex)).write_text('fini', encoding='utf-8')
    modele = 'claude-opus-5-5' if mode == 'opus' else 'claude-sonnet-5-5'
    reponse = reponse_ingestion(entree, variante(mode, entree))
    sortie = {
        'type': 'result', 'subtype': 'error_during_execution' if mode == 'erreur' else 'success',
        'is_error': mode == 'erreur', 'num_turns': 2 if mode == 'deux-tours' else 1,
        'result': json.dumps(reponse, ensure_ascii=False), 'total_cost_usd': 0.0123, 'duration_ms': 12,
        'duration_api_ms': 10, 'usage': {'input_tokens': len(entree) // 4, 'output_tokens': 200},
        'modelUsage': {modele: {'inputTokens': len(entree) // 4, 'outputTokens': 200, 'costUSD': 0.0123}},
    }
    sys.stdout.buffer.write(json.dumps(sortie, ensure_ascii=False).encode('utf-8'))


if __name__ == '__main__':
    principal()
