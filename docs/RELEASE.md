# Construire le zip d'une release

Le zip d'une release (`dist/prevo-<version>.zip`, produit par `outils/construire_release.py`) se
construit **toujours depuis une copie propre de l'étiquette**, jamais depuis le dossier de travail : le
script prend les fichiers tels qu'ils sont sur le disque, et un travail en cours (fichiers modifiés ou
pas encore versionnés) se retrouverait sinon dans le zip.

Dans le dossier du dépôt, pour l'étiquette `v1.1.0` par exemple (remplacez par l'étiquette voulue ;
elle doit contenir `NOTICE` et ce script, donc `v1.1.0` ou une suivante) :

```
git worktree add ../prevo-v1.1.0 v1.1.0
py outils/construire_release.py --source ../prevo-v1.1.0
git worktree remove ../prevo-v1.1.0
```

- `git worktree add` crée à côté du dépôt une copie exacte de l'étiquette, sans toucher au dossier de
  travail ; `git worktree remove` la supprime ensuite.
- Le zip est écrit dans `dist/prevo-<version>.zip` (version lue dans la copie, `js/app.js`). Il ne
  contient que l'application, les lanceurs, `GUIDE.html`, `README.md`, `LICENSE`, `NOTICE` et
  `FICHE_TECHNIQUE_CSV.md` ; jamais les tests, les outils, `docs/` ni les données.
- Deux constructions de la même étiquette donnent exactement les mêmes octets.
- Le script refuse une copie dont la version web est activée : la release n'est jamais la démo en
  ligne.

Joignez ensuite ce zip à la release GitHub créée à partir de la même étiquette.

La démo en ligne se construit de la même façon, depuis la même copie : voir
[DEPLOIEMENT_DEMO.md](DEPLOIEMENT_DEMO.md), étape 1.
