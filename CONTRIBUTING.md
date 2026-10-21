# Contribuer à Prévo

## Lancer les tests

```
py -m unittest discover -s tests -v
```

Les tests de navigateur demandent Playwright et Chromium (`pip install playwright`, puis
`playwright install chromium`) ; ils ne servent qu'aux tests, pas à l'utilisation de Prévo. Pour
exécuter aussi l'aller-retour par le vrai Excel (Excel doit être installé sur le poste), définissez
`PREVO_TEST_EXCEL=1` ; pour l'essai avec un vrai Ollama et `qwen2.5:7b`, `PREVO_TEST_IA=1`. Sans
ces variables, ces tests sont sautés. La suite complète prend plusieurs minutes.

Outils de développement (Playwright aussi) : `py outils/generer_captures.py` refait les captures
d'écran (`docs/captures/` et images du guide) sur le jeu de démo ; `py outils/generer_fiche_csv.py`
refait la fiche technique d'après le schéma.
