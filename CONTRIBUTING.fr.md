# Contribuer à Prévo

*English version: [CONTRIBUTING.md](CONTRIBUTING.md)*

Merci de votre intérêt pour Prévo, la GMAO libre et gratuite des PME industrielles. Les contributions sont les
bienvenues : signalements de problèmes, idées, corrections, traductions.

## Avant de commencer

- **Ne partagez jamais de données réelles d'entreprise** : les issues et les pull requests sont publiques. Utilisez les
  données de démo ou des exemples inventés (captures, fichiers CSV, journaux). Ne collez jamais un mot de passe, un
  jeton, un cookie, une clé d'IA, ni le contenu du dossier `donnees/acces/` ou de `prevo.config.json`.
- **Une faille de sécurité** ne se signale jamais dans une issue publique : voir [SECURITY.md](SECURITY.md).
- Chacun suit le [code de conduite](CODE_OF_CONDUCT.md).
- Pour un changement important, ouvrez d'abord une issue pour convenir de la façon de faire ; une petite correction
  peut aller directement en pull request.
- Les issues et pull requests peuvent être écrites en français ou en anglais. Le code et ses commentaires sont en
  français (choix fait au début du projet).

## Comment Prévo est construit

- **Ni framework ni étape de construction** : HTML, CSS et JavaScript chargés tels quels (`index.html`, `js/`, `css/`) ;
  le serveur (`serveur.py`) n'utilise que la bibliothèque standard de Python. N'ajoutez pas de bibliothèque tierce sans
  en avoir parlé dans une issue.
- **Le contrat est [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** : formats de fichiers, schéma des tables, interfaces
  des modules, règles métier. Un changement de comportement le met à jour dans la même pull request.
- **Les données restent dans des fichiers CSV** lisibles dans Excel. Le format est décrit dans
  [docs/FORMAT.md](docs/FORMAT.md) ; tout changement passe par une migration, jamais par un changement silencieux des
  fichiers.
- **Aucun fichier de `js/modules/` ne dépasse 700 lignes** (vérifié par `tests/test_depot.py`).
- Comment le projet est mené avec des agents IA sous la direction d'un humain : [docs/METHODE.fr.md](docs/METHODE.fr.md).

## Lancer les tests

```
py -X utf8 -m unittest discover -s tests -p "test_depot.py" -v
```

Les tests de navigateur demandent Playwright et Chromium (`pip install playwright`, puis `playwright install chromium`) ;
ils ne servent qu'aux tests, pas à l'utilisation de Prévo. La suite complète prend environ une heure et demie :

```
py outils/lancer_tests.py --journal tests/resultats/suite.txt
```

Chaque fichier de test tourne à part ; celui qui dépasse `--delai-max` (15 min par défaut) est arrêté et compté en
échec, la suite continue. L'aller-retour par le vrai Excel ne tourne qu'avec `PREVO_TEST_EXCEL=1` (Excel installé),
l'essai avec un vrai Ollama et `qwen2.5:7b` qu'avec `PREVO_TEST_IA=1` ; sinon ces tests sont sautés. Aucun test ne lit
le vrai `prevo.pro` ni n'envoie quoi que ce soit hors du PC.

Outils de développement (Playwright aussi) : `py outils/generer_captures.py` refait les captures d'écran
(`docs/captures/` et images du guide) ; `py outils/generer_fiche_csv.py` refait la fiche technique des CSV d'après le
schéma ; `py outils/photographier_ecrans.py` compare chaque écran à sa référence.

## Ajouter ou corriger une langue

Prévo affiche tous ses textes par ses dictionnaires ; le français est la référence.

| Quoi | Où |
|---|---|
| Textes de l'interface et messages du serveur (clés `serveur.*`) | `js/i18n/<code>.js` (`js/i18n/fr.js` fait référence) |
| Aide longue des écrans | `js/i18n/aide/<code>.js` |
| Langues déclarées (code, nom dans sa langue, locale, statut) | `js/i18n/langues.js` |
| Termes métier (un terme français = une traduction, partout) | [docs/GLOSSAIRE.md](docs/GLOSSAIRE.md) |

**Corriger une traduction** : changez la valeur dans `js/i18n/<code>.js`, jamais la clé. Gardez les `{variables}`
telles quelles, et les formes de pluriel que demande la langue (par exemple `{ one: '…', other: '…' }`). Puis
vérifiez :

```
py -X utf8 outils/controler_textes.py --langue <code>
```

Le contrôle doit finir par « Résultat : rien à signaler » (clés manquantes ou en trop, variables différentes, pluriels
faux).

**Ajouter une langue** :

1. Copiez `js/i18n/en.js` en `js/i18n/<code>.js` et traduisez chaque valeur ; de même pour `js/i18n/aide/<code>.js`
   (ou déclarez `aide: false` : l'aide longue s'affiche alors en français).
2. Déclarez la langue dans `js/i18n/langues.js` : `I18n.declarer({ code, nom, locale, statut })`, où `nom` est le nom
   de la langue dans la langue elle-même et `statut` vaut `complete`, ou `automatique` pour une traduction automatique
   (à partir de Prévo 2.1, l'interface le dit et invite aux corrections).
3. Ajoutez la langue au glossaire, puis lancez le contrôle ci-dessus.
4. Regardez chaque écran dans la nouvelle langue : `tests/test_ecrans_anglais.py` montre comment (aucune clé absente,
   aucune erreur JavaScript, les bons formats).

Ce qui reste dans la langue de l'installation, quel que soit l'écran : les textes que Prévo écrit lui-même dans les
données (historique des OT, titres pré-remplis…). Les valeurs des listes (statuts, types, priorités) sont gardées en
français dans les CSV et traduites à l'écran. La console du serveur parle français ou anglais (toute autre langue de
l'installation donne l'anglais).

## Pull requests

Décrivez ce qui change et pourquoi, et les tests lancés (le modèle le demande). Prévo est publié sous
[licence MIT](LICENSE) : en contribuant, vous acceptez que votre contribution soit publiée sous la même licence.
