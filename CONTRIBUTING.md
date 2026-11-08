# Contributing to Prévo

*Version française : [CONTRIBUTING.fr.md](CONTRIBUTING.fr.md)*

Thank you for your interest in Prévo, the free maintenance management software (CMMS) for small industrial
companies. Contributions are welcome: bug reports, ideas, fixes, translations.

## Before you start

- **Never share real company data**: issues and pull requests are public. Use the demo data or invented examples
  (screenshots, CSV files, logs). Never paste a password, a token, a cookie, an AI key, or the content of the
  `donnees/acces/` folder or of `prevo.config.json`.
- **A security flaw** is never reported in a public issue: see [SECURITY.md](SECURITY.md).
- Everyone taking part follows the [code of conduct](CODE_OF_CONDUCT.md).
- For a large change, open an issue first so that we can agree on the approach; a small fix can go straight to a pull
  request.
- Issues and pull requests can be written in English or in French. The code and its comments are in French (a choice
  made at the start of the project); you do not need to write French to contribute.

## How Prévo is built

- **No framework and no build step**: HTML, CSS and JavaScript loaded as they are (`index.html`, `js/`, `css/`); the
  server (`serveur.py`) uses only the Python standard library. Do not add a third-party library without discussing it
  in an issue first.
- **The contract is [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** (in French): file formats, the schema of the
  tables, the interfaces of the modules, the business rules. A change of behaviour updates it in the same pull
  request.
- **Data stays in CSV files** that open in Excel. The format is described in [docs/FORMAT.md](docs/FORMAT.md); any
  change to it goes through a migration, never through a silent change of the files.
- **No file of `js/modules/` goes beyond 700 lines** (checked by `tests/test_depot.py`).
- How the project is run with AI agents under human direction: [docs/METHODE.md](docs/METHODE.md).

## Running the tests

```
py -X utf8 -m unittest discover -s tests -p "test_depot.py" -v
```

Browser tests need Playwright and Chromium (`pip install playwright`, then `playwright install chromium`); they are
only used for testing, not for running Prévo. The full suite takes about an hour and a half:

```
py outils/lancer_tests.py --journal tests/resultats/suite.txt
```

Each test file runs on its own; a file that goes beyond `--delai-max` (15 minutes by default) is stopped and counted
as failed, and the suite goes on. The round trip through the real Excel runs only with `PREVO_TEST_EXCEL=1` (Excel
installed), the test with a real Ollama and `qwen2.5:7b` only with `PREVO_TEST_IA=1`; otherwise they are skipped.
No test ever reads the real `prevo.pro` or sends anything outside the PC.

Development tools (Playwright too): `py outils/generer_captures.py` remakes the screenshots (`docs/captures/` and the
images of the guide); `py outils/generer_fiche_csv.py` remakes the CSV technical sheet from the schema;
`py outils/photographier_ecrans.py` compares every screen with its reference.

## Add or fix a language

Prévo shows every text through its dictionaries; French is the reference.

| What | Where |
|---|---|
| Interface texts and server messages (keys `serveur.*`) | `js/i18n/<code>.js` (`js/i18n/fr.js` is the reference) |
| Long help of the screens | `js/i18n/aide/<code>.js` |
| Declared languages (code, name in its own language, locale, status) | `js/i18n/langues.js` |
| Business terms (one French term = one translation everywhere) | [docs/GLOSSAIRE.md](docs/GLOSSAIRE.md) |

**Report a wrong translation** without touching the code: the "Fix a translation" form on GitHub (Prévo links to
it, with the language and its version, for every machine-translated language).

**Fix a translation**: change the value in `js/i18n/<code>.js`, never the key. Keep the `{variables}` exactly as they
are, and the plural forms the language needs (for example `{ one: '…', other: '…' }`). Then check:

```
py -X utf8 outils/controler_textes.py --langue <code>
```

It must end with "Résultat : rien à signaler" (missing or extra keys, different variables, wrong plural forms).

**Add a language**:

1. Copy `js/i18n/en.js` to `js/i18n/<code>.js` and translate every value; same for `js/i18n/aide/<code>.js` (or
   declare `aide: false`: the long help then shows in French).
2. Declare the language in `js/i18n/langues.js`: `I18n.declarer({ code, nom, locale, statut })`, where `nom` is the
   name in the language itself and `statut` is `complete`, or `automatique` for a machine translation (from
   Prévo 2.1, the interface says so and invites corrections).
3. Add the language to the glossary, then run the check above.
4. Look at every screen in the new language: `tests/test_ecrans_anglais.py` shows how (no missing key, no JavaScript
   error, the right formats).

What stays in the language of the installation, whatever the screen shows: the texts Prévo writes itself into the
data (work order history, pre-filled titles…). The values of the lists (statuses, types, priorities) are stored in
French in the CSV files and translated on screen. The server console speaks French or English (any other language of
the installation gives English).

## Pull requests

Describe what changes and why, and the tests you ran (the template asks for it). Prévo is released under the
[MIT License](LICENSE): by contributing, you agree that your contribution is released under the same licence.
