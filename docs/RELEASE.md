# Construire le zip d'une release

Le zip d'une release (`dist/prevo-<version>.zip`, produit par `outils/construire_release.py`) se
construit **toujours depuis une copie propre de l'étiquette**, jamais depuis le dossier de travail : le
script prend les fichiers tels qu'ils sont sur le disque, et un travail en cours (fichiers modifiés ou
pas encore versionnés) se retrouverait sinon dans le zip.

Dans le dossier du dépôt, pour l'étiquette `v2.0.0` par exemple (remplacez par l'étiquette voulue ;
elle doit contenir `NOTICE` et ce script, donc `v1.2.0` ou une suivante ; `v2.0.0` pour Python et mkcert dans le zip) :

```
git worktree add ../prevo-v2.0.0 v2.0.0
py outils/construire_release.py --source ../prevo-v2.0.0
git worktree remove ../prevo-v2.0.0
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

## Signaler la nouvelle version (version.json)

Le script écrit aussi `dist/version.json` à côté du zip : le numéro, la date, l'adresse de la release GitHub et
les deux premières nouveautés du CHANGELOG de cette version. Prévo le lit (si le responsable l'a autorisé dans
Paramètres, au plus une fois par jour et par poste, ARCHITECTURE.md §21) pour signaler la nouvelle version sur
l'accueil du responsable et dans « À propos ». À chaque release :

1. publier `dist/version.json` à la racine du site, à l'adresse exacte `https://prevo.pro/version.json` ;
2. le servir avec l'en-tête `Access-Control-Allow-Origin: *` (nginx : `add_header Access-Control-Allow-Origin *;`
   dans le `location = /version.json`) : sans cet en-tête, le navigateur refuse la lecture depuis le poste et
   Prévo ne signale rien ;
3. vérifier : `curl -I https://prevo.pro/version.json` montre `200`, `application/json` et l'en-tête.

Rien ne s'installe tout seul : le bandeau mène à la page de la release, l'installation reste celle du guide.

La démo en ligne se construit de la même façon, depuis la même copie : voir
[DEPLOIEMENT_DEMO.md](DEPLOIEMENT_DEMO.md), étape 1.
