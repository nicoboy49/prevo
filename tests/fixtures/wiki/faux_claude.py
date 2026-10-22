"""Faux `claude` (la commande de Claude Code) pour les essais de outils/wiki_demo.py : mêmes options, réponse JSON
de `claude -p --output-format json`, dont le texte est construit par tests/faux_wiki.py (variante faux-mode-cause)
à partir du seul message reçu sur l'entrée standard.

Variables d'environnement :
    FAUX_CLAUDE_MODE     sonnet (défaut) | opus (un autre modèle) | deux-tours | refus (réponse que Prévo refuse :
                         un OT cité hors de la liste) | erreur (réponse en erreur)
    FAUX_CLAUDE_TRACES   dossier : chaque appel y écrit appel-<identifiant>.json (arguments et entrée standard reçus)
"""
import json
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))       # tests/
from faux_wiki import reponse_ingestion  # noqa: E402


def principal():
    arguments = sys.argv[1:]
    entree = sys.stdin.buffer.read().decode('utf-8')
    dossier = os.environ.get('FAUX_CLAUDE_TRACES')
    if dossier:
        Path(dossier).mkdir(parents=True, exist_ok=True)
        (Path(dossier) / ('appel-%s.json' % uuid.uuid4().hex)).write_text(
            json.dumps({'arguments': arguments, 'entree': entree}, ensure_ascii=False), encoding='utf-8')
    mode = os.environ.get('FAUX_CLAUDE_MODE', 'sonnet')
    modele = 'claude-opus-5-5' if mode == 'opus' else 'claude-sonnet-5-5'
    reponse = reponse_ingestion(entree, 'faux-invente' if mode == 'refus' else 'faux-mode-cause')
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
