# Construire le zip d'une release

Le zip d'une release (`dist/prevo-<version>.zip`, produit par `outils/construire_release.py`) se
construit **toujours depuis une copie propre de l'étiquette**, jamais depuis le dossier de travail : le
script prend les fichiers tels qu'ils sont sur le disque, et un travail en cours (fichiers modifiés ou
pas encore versionnés) se retrouverait sinon dans le zip.

Dans le dossier du dépôt, pour l'étiquette `v2.0.0-beta.2` par exemple (remplacez par l'étiquette voulue ;
elle doit contenir `NOTICE` et ce script, donc `v1.2.0` ou une suivante ; `v2.0.0-beta.1` ou une suivante pour Python et mkcert dans le zip) :

```
git worktree add ../prevo-v2.0.0-beta.2 v2.0.0-beta.2
py outils/construire_release.py --source ../prevo-v2.0.0-beta.2
git worktree remove ../prevo-v2.0.0-beta.2
```

- `git worktree add` crée à côté du dépôt une copie exacte de l'étiquette, sans toucher au dossier de
  travail ; `git worktree remove` la supprime ensuite.
- Le zip est écrit dans `dist/prevo-<version>.zip` (version lue dans la copie, `js/app.js`). Il ne
  contient que l'application, les lanceurs, `GUIDE.html` et `GUIDE.en.html`, `README.md` et `README.fr.md`,
  `LICENSE`, `NOTICE` et `FICHE_TECHNIQUE_CSV.md` ; jamais les tests, les outils, `docs/` ni les données.
- Deux constructions de la même étiquette donnent exactement les mêmes octets.
- Le script refuse une copie dont la version web est activée : la release n'est jamais la démo en
  ligne.

Joignez ensuite ce zip à la release GitHub créée à partir de la même étiquette.

## Signaler la nouvelle version (version.json)

Cette section est la **seule source** des règles de `version.json` (décision du 06/11/2026) : le site prevo.pro les
applique à chaque sortie.

Le script écrit aussi `dist/version.json` à côté du zip : le numéro, la date, l'adresse de la release GitHub et
les deux premières nouveautés du CHANGELOG de cette version. Prévo le lit (activé par défaut depuis la 2.0.0,
désactivable dans Paramètres › Mises à jour ; au plus une fois par jour et par poste, ARCHITECTURE.md §21) pour
signaler la nouvelle version sur l'accueil du responsable et dans « À propos ». Prévo ne fait qu'une simple lecture
du fichier : il n'envoie rien (ni identifiant, ni numéro d'installation, ni statistique, ni cookie, ni adresse de
page), jamais dans la démo en ligne.

### À chaque release

1. **Seulement pour une version stable déjà publiée** : `version.json` annonce uniquement la **dernière version
   stable publiée**, jamais une version qui n'est pas encore sur GitHub (la release d'abord, `version.json`
   ensuite), jamais une bêta (`x.y.z-beta.N`).
2. Publier `dist/version.json` à la racine du site, à l'adresse exacte `https://prevo.pro/version.json` (HTTPS).
3. Le servir avec `Content-Type: application/json` et l'en-tête `Access-Control-Allow-Origin: *` (nginx :
   `add_header Access-Control-Allow-Origin *;` dans le `location = /version.json`) : Prévo le lit depuis le
   navigateur, même ouvert en fichier local ; sans cet en-tête, la lecture est refusée et Prévo ne signale rien.
   `Cache-Control: no-cache` conseillé.
4. Vérifier : `curl -I https://prevo.pro/version.json` montre `200`, `application/json` et l'en-tête ;
   `curl -s https://prevo.pro/version.json` montre la bonne version.

### Champs

| champ | obligatoire | règle |
|---|---|---|
| `version` | oui | version stable `x.y.z` seulement (chaque nombre de 1 à 4 chiffres), jamais `-beta.N` : une 1.2.x ignore tout le fichier si la forme est autre (aucun bandeau). Une bêta 2.0 installée est prévenue de la finale. |
| `adresse` | oui | `https://…`, la page de la release ou de téléchargement ; à partir de la 2.0.0, sur `prevo.pro` ou `github.com/nicoboy49/prevo` seulement, sinon aucun bandeau. |
| `date` | non | `AAAA-MM-JJ`, date de publication, affichée dans le bandeau. |
| `nouveautes` | non | liste de 3 phrases au plus (les suivantes sont ignorées), 200 caractères au plus chacune (au-delà : coupée), texte brut sans HTML, en **français**. |
| `nouveautes_en` | non | mêmes règles que `nouveautes`, en **anglais** : une installation en anglais l'affiche s'il existe, sinon `nouveautes` en français. Lu à partir de la 2.0.0, ignoré par les 1.2.x ; pas encore écrit par le script (à ajouter à la main). |

Tout autre champ est ignoré : on peut en ajouter sans casser ni les 1.2.x ni la 2.0.

Exemple complet :

```json
{
  "version": "2.0.0",
  "date": "2026-11-20",
  "adresse": "https://github.com/nicoboy49/prevo/releases/tag/v2.0.0",
  "nouveautes": [
    "Prévo en anglais : choisissez la langue à l'écran « Ce poste ».",
    "Deuxième nouveauté, en une phrase.",
    "Troisième nouveauté, en une phrase."
  ],
  "nouveautes_en": [
    "Prévo in English: choose the language on the “This workstation” screen.",
    "Second new feature, in one sentence.",
    "Third new feature, in one sentence."
  ]
}
```

Rien ne s'installe tout seul : le bandeau mène à la page de la release, l'installation reste celle du guide.

La démo en ligne se construit de la même façon, depuis la même copie : voir
[DEPLOIEMENT_DEMO.md](DEPLOIEMENT_DEMO.md), étape 1.
