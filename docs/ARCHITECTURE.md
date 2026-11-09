# Architecture de Prévo

Ce document est le **contrat interne** du code : tout fichier JavaScript ou Python le respecte.
Il est écrit pour être lu par un stagiaire comme par une IA qui code un lot suivant. En cas de
doute, [`brief-gmao.md`](brief-gmao.md) fait foi, puis ce document.

---

## 1. Vue d'ensemble

```
index.html                 page unique de l'application
favicon.svg                logo (engrenage dans un carré dégradé)
serveur.py                 serveur local (Python 3.8+, bibliothèque standard seulement)
Lancer_GMAO.bat            lanceur Windows      lancer.sh   lanceur Mac/Linux
css/style.css              charte « Cockpit » adaptée (écran sombre + impression noir sur blanc)
css/modules/*.css          mise en page propre à chaque module (une feuille par module : app, accueil,
                           parc, demandes, ordres, preventif, magasin, parametres, depuis le lot 3
                           equipe, controles, planning, indicateurs, etiquettes, depuis le lot 3 bis
                           suggestions, depuis le lot 4 ia, poste, et depuis le lot 5 import ;
                           chargées par index.html)
css/polices/               police Sora (OFL)
js/lib/                    bibliothèques tierces + LICENCES.txt (jamais modifiées)
js/i18n.js                 I18n      : moteur de traduction (t, html, pluriels, repli, data-i18n ; multilingue)
js/i18n/langues.js         langues déclarées (statut automatique : mention « Traduction automatique — corrections
                           bienvenues » et formulaire GitHub, Apropos.mentionTraduction ; aide: 'en' : aide longue
                           prise en anglais, I18n.langueDeLAide, D158 ; Lot 5, T343) ; js/i18n/<code>.js : textes d'une langue, un bloc par section
js/i18n/aide/<code>.js     aide longue d'une langue (clés aide.*, repli silencieux sur le français)
js/i18n-chargeur.js        ajoute la langue active (si ce n'est pas le français) avant js/schema.js
js/schema.js               Schema    : description des 22 tables (champs, types, identifiants)
js/formats.js              Formats   : registre des formats (colonnes de chaque format, étapes de migration, manifeste)
js/catalogue/fr.js         CatalogueFR : catalogue des contrôles réglementaires et des habilitations (France, 2.2 ;
                           généré par outils/generer_catalogue.py depuis docs/catalogue/*.json, gelé, lecture seule)
js/donnees.js              Donnees   : CSV, chargement, contrôle, mutation, journal, rafraîchissement
js/stockage-serveur.js     StockageServeur : adaptateur « serveur » (API HTTP)
js/stockage-dossier.js     StockageDossier : adaptateur « dossier » (File System Access)
js/stockage-demo.js        StockageDemo    : adaptateur « démo » (mémoire)
js/demo-donnees.js         DEMO_DONNEES : jeu de démo généré (chargé à la demande)
js/interface.js            UI        : helpers d'écran (html, tableaux, fenêtres, QR, photos…)
js/modules/*.js            modules métier : un module = un préfixe de fichiers (§14.2), ex.
                           ordres-regles.js … ordres-impression.js pour l'objet Ordres ; petits
                           modules en un seul fichier (accueil.js, apropos.js, causes-frequentes.js) ;
                           liste et ordre exacts au §15.1 (lot 3), complétés au §16.1 (lot 3 bis)
                           et au §17.1 (lot 4 : ia, ia-prompts, ia-encadre, dictee, poste) ;
                           lot 5 : les sept fichiers import-*.js à la fin (§18.1)
js/app.js                  App       : démarrage, choix du mode, profils, navigation
donnees/                   les CSV réels (hors dépôt git) + documents/ + sauvegardes/
donnees/demo/              le jeu de démo en CSV (versionné)
outils/generer_demo.py     génère donnees/demo/*.csv, js/demo-donnees.js et tests/fixtures/demo-scenarios.json
outils/generer_fiche_csv.py   écrit FICHE_TECHNIQUE_CSV.md d'après Schema (lot 4) et, pour les
                              colonnes reconnues à l'import, js/modules/import-regles.js (lot 5)
outils/generer_fixtures_import.py   fichiers d'essai de l'import (tests/fixtures/import/, lot 5)
outils/generer_captures.py    captures du guide et du README (docs/captures/*.png, lot 4)
GUIDE.html                 guide d'utilisation autonome et imprimable (lot 4, servi par serveur.py)
FICHE_TECHNIQUE_CSV.md     format des 22 fichiers CSV (lot 4, généré) et colonnes reconnues à
                           l'import (lot 5)
tests/                     tests automatisés (unittest + Playwright) ; tests/fixtures/ : pages et
                           fichiers d'essai (servis seulement avec serveur.py --servir-tests, §7)
```

**Ordre de chargement dans `index.html`** (scripts classiques, jamais `type="module"`) :
`js/lib/papaparse.min.js`, `js/lib/qrcode.js`, `js/lib/jsQR.js` (JSZip, retiré en T229, n'y est plus : le ZIP
passe par `zip-flux.js`), la traduction (chantier multilingue, T234) : `js/i18n.js` (le moteur, objet `I18n`),
`js/i18n/langues.js`, `js/i18n/fr.js`, `js/i18n/aide/fr.js`, `js/i18n-chargeur.js` (la langue active, voir plus bas),
`js/schema.js`, `js/formats.js` (juste après le schéma, dont il dépend seul :
chantier « socle de données »), `js/catalogue/fr.js` (2.2, T410 : le catalogue des contrôles réglementaires et des
habilitations, `window.CatalogueFR`, généré par `outils/generer_catalogue.py` en T400 ; objets gelés, en lecture seule,
lus par les modules au moment de l'appel ; sans lui, les modules rendent une liste vide),
`js/donnees.js`, `js/stockage-serveur.js`, `js/stockage-dossier.js`,
`js/stockage-demo.js`, `js/interface.js`, les fichiers de `js/modules/` dans l'ordre exact du
§15.1 (il remplace, depuis le lot 3, celui du §14.2 ; le lot 3 bis y insère `suggestions-regles.js` et
`suggestions-ecrans.js` juste après `preventif-calendrier.js`, §16.1 ; le lot 4 insère `ia.js`,
`ia-masquage.js` (Lot 5, T374 : `Ia.masquer`), `ia-prompts.js`, `ia-encadre.js`, `dictee.js`, `poste.js` juste après `causes-frequentes.js`, §17.1 ;
le lot 5 ajoute les sept fichiers `import-*.js` à la fin, après `parametres-codes.js`, §18.1, et
`accueil-bento.js` juste après `accueil.js`, §19 ; le lot 7 insère `aide-ecrans-textes.js`, `aide-ecrans.js` et
`acces-textes.js` juste après `mise-a-jour.js` (§23, §22.2), `ia-serveur.js` juste après `ia-encadre.js` (§22.12),
`parametres-solo.js` juste après `parametres-codes.js` et `parametres-sauvegardes.js` juste après `parametres-solo.js`
(§22.11) ; la 2.2 (T410) insère `controles-reserves.js` et `controles-catalogue.js` juste après `controles-regles.js`,
`controles-reserves-ecrans.js` juste après `controles-ecrans.js`, `equipe-habilitations.js` juste après
`equipe-ecrans.js` et `ordres-habilitations.js` juste après `ordres-impression.js`, §15.1 ; le lot L4 (T450) insère
les cinq fichiers `garanties-*.js` juste après `controles-reserves-ecrans.js`, §15.1), `js/app.js` (en dernier).
Langue active (T234, T295) : `js/i18n-chargeur.js` lit `localStorage` « prevo.langue » (le choix du poste, écrit par
le sélecteur de langue, §24.10) puis « prevo.langue.installation » (la langue de l'installation, §24.11 ; la langue du
compte viendra plus tard) ; la première des deux déclarée par `js/i18n/langues.js` (sinon le français) est la langue
à afficher. Autre que le français, elle devient la langue active (`I18n.choisir`, qui donne aussi l'attribut `lang`
de `<html>`) et ses deux fichiers (`js/i18n/<code>.js`, `js/i18n/aide/<code>.js`) sont
écrits par `document.write` pendant l'analyse de la page : chargés et exécutés avant `js/schema.js`, en `file://` comme
en http ; le dictionnaire de l'installation s'y ajoute quand elle n'est ni le français ni la langue affichée. Valeur
absente, non déclarée ou mal formée, stockage refusé : ignorée (français), sans erreur. `acces/porte.html`
charge `js/i18n.js`, `js/i18n/langues.js` et `js/i18n/fr.js` avant `acces/porte.js` (servis par la porte :
`fichier_de_la_porte`, §22.6). `App` applique les attributs `data-i18n` et `data-i18n-attr` de `index.html` au
démarrage (`I18n.appliquer(document)`).
`js/demo-donnees.js` n'est **pas** chargé au démarrage : `App` l'injecte (balise `<script>`
créée dynamiquement, compatible `file://`) quand on choisit la démo ou la copie du jeu de démo.
ECharts (`js/lib/echarts.min.js`, version 5.5.1) n'est pas non plus chargé au démarrage :
`App.chargerEcharts()` l'injecte de la même façon au premier graphique (lot 3, §15.1).
SheetJS (`js/lib/xlsx.full.min.js`, version 0.20.3) non plus : `App.chargerSheetJS()` l'injecte à la
première lecture d'un classeur ou au premier modèle .xlsx de l'assistant d'import (lot 5, §18.1).

**Un objet global par fichier du socle, un objet global par module** (`const Schema = …`,
`const Donnees = …`, `const Ordres = …`). Rien d'autre n'est global. Un module découpé en
plusieurs fichiers partage **un seul** objet : le premier fichier du préfixe le crée, les suivants
le complètent par `Object.assign` (règles détaillées au §14.2). Chaque fichier commence par
`'use strict';` et un commentaire qui dit son rôle ; dans un module découpé, le premier fichier
liste les fichiers du préfixe et chacun des suivants indique sa place (« Ordres (4/7) »).

## 2. Règles de code (tous les fichiers)

- Français partout : interface, commentaires, noms de variables et de fonctions explicites
  (`equipementChoisi`, pas `eq` ; `chargerTout`, pas `load`).
- **`file://` doit marcher** : pas de `fetch` vers un fichier local, pas de modules ES, pas de
  `import()`. Les seules lectures réseau sont celles de `StockageServeur` vers `/api/…`.
- **Contexte non sécurisé** : en mode serveur, les téléphones ouvrent `http://192.168.x.x:8080`.
  Interdits dans tout code qui tourne en mode serveur : `crypto.subtle`, `crypto.randomUUID`,
  `navigator.clipboard`, `getUserMedia` (le scan caméra est proposé seulement si
  `window.isSecureContext && navigator.mediaDevices`). La photo passe par
  `<input type="file" accept="image/*" capture="environment">`, qui marche partout.
- **Échappement** : tout texte venant des données passe par `UI.html` (échappe par défaut) ou
  `UI.echapper`. Jamais d'`innerHTML` avec une chaîne non échappée.
- Pas de `alert`, `confirm`, `prompt` : utiliser `UI.toast`, `UI.confirmer`, `UI.demanderMotif`.
- Aucune dépendance hors de `js/lib/`. Aucun appel vers Internet.
- Python : 3.8 minimum (pas de `str.removeprefix`, pas de `match`, pas d'annotations `list[str]`
  évaluées), bibliothèque standard seulement.
- Toute valeur en mémoire est une **chaîne** au format du fichier (dates ISO, `0`/`1`, point
  décimal). Les conversions pour calculer ou afficher passent par `Donnees.nombre(v)`,
  `UI.dateFr(v)`, etc.

## 3. Format des CSV

### 3.1 Écriture (toujours)
BOM UTF-8 (`EF BB BF`), séparateur `;`, fins de ligne CRLF, première ligne = noms de champs dans
l'ordre du schéma (puis les colonnes inconnues conservées, dans leur ordre d'origine), guillemets
RFC 4180 (un champ est entre guillemets s'il contient `;`, `"`, CR ou LF ; `"` doublé), dates
`AAAA-MM-JJ`, date-heure `AAAA-MM-JJ HH:MM`, décimales avec point, booléens `0`/`1`.
Une ligne n'est jamais supprimée (champ `actif` à `0` ou statut `Annulé`).

### 3.2 Protection par apostrophe (décision D5 validée)
Excel abîme certaines valeurs (`- remplacer joint` → `#NOM?`, `00123` → `123`,
`123456789012345` → `1,23457E+14`, `1/2` → date) mais garde intacte une valeur précédée d'une
apostrophe. Règle, pour les champs de type `texte` et `texte_long` uniquement :

```
aProteger(champ, v) = v !== '' && (
      champ.protege === true                      // num_serie, repere, reference, ref_fabricant, telephone
   || /^[=+\-@\t\r]/.test(v)                      // formule ou tiret en tête
   || v.startsWith("'")                           // apostrophe déjà présente : on la double
   || ressembleNombreDateFraction(v) )
ressembleNombreDateFraction(v) = v (sans espaces aux bords) correspond à l'un de :
   /^[0-9]+([.,][0-9]+)?$/                 nombre, zéros en tête, plus de 11 chiffres
   /^[0-9]+([.,][0-9]+)?[eE][+-]?[0-9]+$/  exposant
   /^[0-9]{1,4}[\/.\-][0-9]{1,2}([\/.\-][0-9]{1,4})?$/   date ou fraction (1/2, 01-12, 2026-10)
   /^[0-9]{1,2}:[0-9]{2}(:[0-9]{2})?$/      heure
   /^[0-9]+([.,][0-9]+)?\s?%$/              pourcentage
écrire(champ, v)  = aProteger(champ, v) ? "'" + v : v
relire(champ, s)  = (s.startsWith("'") && aProteger(champ, s.slice(1))) ? s.slice(1) : s
```
Propriété garantie (testée) : `relire(champ, écrire(champ, v)) === v` pour toute valeur.

### 3.3 Lecture tolérante (décision D6)
1. Encodage : BOM retiré s'il est présent ; décodage `TextDecoder('utf-8', {fatal: true})` ; en
   cas d'échec, `windows-1252` + problème `encodage` (information).
2. Séparateur : `;`. Si l'en-tête ne contient aucun `;` mais contient des `,`, on lit avec `,`.
3. En-tête : correspondance par nom (casse, accents et espaces ignorés). Colonnes dans le
   désordre acceptées. Colonne du schéma absente → valeur par défaut + problème `colonne`.
   Colonne inconnue → conservée telle quelle et réécrite à la fin.
4. Lignes entièrement vides ignorées. Espaces de fin et `\r` parasites retirés.
5. Normalisation par type (valeur illisible → gardée brute + problème `valeur`) :
   - `date` : `AAAA-MM-JJ`, `JJ/MM/AAAA`, `J/M/AAAA`, `JJ-MM-AAAA`, `JJ.MM.AAAA` → `AAAA-MM-JJ` ;
   - `date_heure` : idem + `HH:MM` ou `HH:MM:SS`, séparateur espace ou `T` → `AAAA-MM-JJ HH:MM` ;
   - `decimal` / `entier` : virgule → point, espaces (y compris insécables) retirés ;
   - `booleen` : `1`, `0`, `vrai`, `faux`, `oui`, `non`, `true`, `false`, `x` (casse ignorée) → `1`/`0` ;
   - `choix` : comparaison sans casse ni accents → valeur canonique du schéma ;
   - `texte`, `texte_long` : `relire()` du §3.2 ; si la valeur ressemble à une notation
     scientifique d'Excel (`/^[0-9]+,[0-9]+E\+[0-9]+$/i`) → problème `excel` (« valeur
     probablement abîmée par Excel ») ; valeur conservée telle quelle.
6. Le fichier est réécrit au format §3.1 à la prochaine modification de la table.

## 4. Schéma (`js/schema.js`)

```js
const Schema = {
  version: 4,                          // version du format des fichiers (§14.1, §20.2, §25) ; 1 au lot 1
  tables: {
    equipements: {
      fichier: 'equipements.csv', libelle: 'Équipements',
      cle: 'id',                       // champ identifiant (parametres : 'cle')
      identifiant: { prefixe: 'EQ-', chiffres: 4, annuel: false },
      ajoutSeul: false,                // true pour journal (écriture par ajout, §5.4)
      champs: [
        { nom: 'id', type: 'id', libelle: 'Identifiant' },
        { nom: 'repere', type: 'texte', libelle: 'Repère', protege: true, obligatoire: true,
          synonymes: ['code machine', 'tag', 'référence machine'] },
        { nom: 'localisation_id', type: 'ref', table: 'localisations', libelle: 'Localisation' },
        { nom: 'criticite', type: 'choix', valeurs: ['A', 'B', 'C'], defaut: 'B', libelle: 'Criticité' },
        // …
      ],
    },
    // … 27 tables (22 du brief, 2 du format 3, 3 du format 4) : d'abord exactement les champs du §6 du brief, dans
    // le même ordre, puis, en fin de table, les champs ajoutés par les formats 2 à 4 (depuisVersion: 2, 3 ou 4)
  },
};
```
Types : `id`, `texte`, `texte_long`, `entier`, `decimal`, `date`, `date_heure`, `booleen`,
`choix` (avec `valeurs`), `ref` (avec `table`, et `champCible` si ce n'est pas la clé — ex. les
`*_code` des OT visent `codes_defaillance.code` filtré par `famille`, attribut `filtre`), `document`
(nom de fichier dans `donnees/documents/`). Champs facultatifs : `libelle` (toujours renseigné ; texte du dictionnaire, voir plus bas), `obligatoire`, `defaut`, `protege`, `synonymes` (pour l'assistant d'import futur),
`depuisVersion` (version du format qui a ajouté le champ : `2` pour les quatre champs du §14.1, `3` pour
`astuce` (§20.2), `4` pour les dix du §25 ; absent pour les champs du brief).

**Libellés traduits (Lot 2 multilingue, §24).** Les `libelle` ne sont plus écrits dans `js/schema.js` : à la fin du
fichier, une boucle remplace chacun par un accesseur énumérable qui lit `schema.<table>.<champ>` à chaque lecture
(le nom d'une table, `schema.tables.<table>`) ; les lectures `.libelle` du code, ainsi que `JSON.stringify` et
`Object.assign` sur une description de champ, voient donc le texte de la langue active sans rien changer.
`Schema.libelleValeur(table, champ, valeur)` donne le texte affiché d'une valeur stockée d'un champ `choix`
(clé `valeurs.<table>.<champ>.<valeur>`) ; une valeur vide, inconnue ou d'un autre type de champ est rendue telle
quelle, une valeur retirée (`retirees`) garde son libellé. Chaque champ `choix` porte `nomTable`, le nom de sa table,
qui suit ses copies. Les colonnes de `UI.tableau` ont une option `table` : avec `cle`, la cellule est une valeur
stockée affichée par `Schema.libelleValeur(table, cle, valeur)`.

**Format v2 (lot 2).** Quatre champs sont ajoutés **en fin de table**, après ceux du brief :
`equipements.valeur_remplacement`, `demandes.symptome_code`, `demandes.ot_origine_id`,
`ordres_travail.anomalie_constatee` (détail au §14.1). Un fichier écrit au format 1 n'a pas ces
colonnes : à la lecture, chaque colonne absente marquée `depuisVersion` donne un problème de gravité
**`info`** (« colonne … ajoutée par la version 2 du format, écrite au prochain enregistrement »),
jamais `attention`, et la valeur par défaut du champ est appliquée ; la colonne est écrite à la
prochaine modification de la table. Une colonne **du brief** absente reste un problème `attention`
(§3.3). Le passage de `parametres.version_schema` à 2 est décrit au §5.6.

Identifiants (calculés **dans** la fonction de mutation, §5.3) :

| Table | Format | | Table | Format |
| --- | --- | --- | --- | --- |
| localisations | `LOC-0001` | | articles | `ART-0001` |
| equipements | `EQ-0001` | | article_equipement | `AEQ-00001` |
| demandes | `DI-AAAA-0001` (par année) | | mouvements_stock | `MVT-000001` |
| ordres_travail | `OT-AAAA-0001` (par année) | | techniciens | `TEC-0001` |
| ot_operations | `OTO-000001` | | habilitations | `HAB-0001` |
| ot_pieces | `OTP-000001` | | compteurs | `CPT-0001` |
| ot_temps | `OTT-000001` | | releves | `REL-000001` |
| gammes | `GAM-0001` | | controles_reglementaires | `CTR-0001` |
| gamme_operations | `GOP-000001` | | codes_defaillance | `CD-0001` (+ `code` lisible : `S01`, `C03`, `R02`) |
| fournisseurs | `FOU-0001` | | achats | `ACH-0001` |
| parametres | clé = `cle` | | journal | `J-AAAAMMJJHHMMSS-XXXX` (horodaté + 4 caractères aléatoires) |

Valeurs canoniques des listes (accents compris) :
- DI `statut` : `Nouvelle`, `Acceptée`, `Regroupée`, `Différée`, `Refusée` ; `impact` :
  `sécurité`, `arrêt`, `dégradé`, `gêne`.
- OT `statut` : `Créé`, `Préparé`, `Planifié`, `En cours`, `En attente`,
  `Clôturé techniquement`, `Clôturé administrativement`, `Annulé` ; `origine` : `DI`,
  `préventif`, `urgence`, `manuel` ; `type` : `correctif immédiat`, `correctif différé`,
  `préventif systématique`, `préventif conditionnel`, `amélioration`, `réglementaire` ;
  `priorite` : `P1`…`P4`.
- `equipements.statut` : `en service`, `arrêt`, `rebut` ; `criticite` : `A`, `B`, `C`.
- `localisations.type` : `site`, `atelier`, `ligne`. `codes_defaillance.famille` : `symptôme`,
  `cause`, `remède`. `mouvements_stock.type` : `entrée`, `sortie`, `inventaire`, `retour`.
  `achats.statut` : `demandée`, `commandée`, `reçue`. `gammes.declencheur` : `date`,
  `compteur`, `seuil`.

Clés de `parametres.csv` utilisées au lot 1 : `entreprise_nom`, `delai_p1_h` (0),
`delai_p2_h` (24), `delai_p3_h` (168), `delai_p4` (`prochain arrêt`), `heures_fonct_defaut`,
`tolerance_preventif_pct`, `rafraichissement_s` (20), `version_schema` (1 au lot 1, 2 depuis le
lot 2). Ajoutées au lot 2 : `priorite_preventif` (`P3` : priorité des OT préventifs générés ; valeur
hors P1–P4 → P3) et `horizon_calendrier_semaines` (`12` : nombre de semaines du calendrier du
préventif). Ces deux clés ne sont pas modifiables dans l'écran Paramètres : elles se changent dans
`parametres.csv` ; absentes, leur valeur par défaut s'applique. Une absence de `version_schema`
(ou une valeur illisible) vaut 1.

## 5. `Donnees` (`js/donnees.js`)

### 5.1 Erreurs
`Donnees.ErreurConflit` (version périmée ; porte `versionActuelle`), `Donnees.ErreurValidation`
(levée par une fonction de mutation pour refuser une action avec un message pour l'utilisateur :
jamais réessayée), `Donnees.ErreurStockage` (lecture/écriture impossible, ex. fichier ouvert
dans Excel ; message en français).

### 5.2 Lecture
```
Donnees.initialiser(adaptateur, { poste, profil })   // profil : texte pour le journal, ex. « Technicien TEC-0002 »
Donnees.definirIdentite({ poste, profil })           // change l'identité du journal sans réinitialiser (changement de profil)
await Donnees.chargerTout()          // les 22 tables en parallèle, puis contrôle de la base
await Donnees.rechargerTable(table)  // relit une table (ex. après une restauration)
Donnees.lignes(table)                // tableau des lignes (objets) — NE PAS MODIFIER directement
Donnees.trouver(table, id)           // ligne par clé (index Map), ou undefined
Donnees.version(table)
Donnees.parametre(cle, defaut)       // valeur de parametres.csv
Donnees.problemes()                  // [{ gravite: 'erreur'|'attention'|'info', type, table, ligne, id, champ, valeur, message }]
Donnees.nouvelId(table, lignesExistantes, dateIso?)  // identifiant suivant (c'est ce qu'appelle outils.nouvelId, §5.3)
Donnees.normaliser(...)              // normalisation par type (§3.3)
Donnees.nombre(v)                    // Number ou null
Donnees.aujourdhui() / Donnees.maintenant()   // 'AAAA-MM-JJ' / 'AAAA-MM-JJ HH:MM' (heure locale)
Donnees.stockArticle(articleId)      // recalculé depuis mouvements_stock (un inventaire fixe la valeur)
await Donnees.journaliser(table, idLigne, action)   // entrée de journal sans modification (ex. avertissement RG8)
Donnees.instantane()                 // { table: Uint8Array } des 22 tables sérialisées (export ZIP, copie de la démo)
Donnees.baseVide()                   // vrai si aucun des 22 fichiers n'existe
Donnees.etatDuFormat() / Donnees.lectureSeule()   // format de départ et courant ; données plus récentes (§5.6)
await Donnees.migrerAuFormatCourant()   // mode dossier : passage au format courant, sauvegarde d'abord ; mode serveur :
                                        // rien, le serveur l'a fait à son démarrage (§5.6, FORMAT.md §6)
Donnees.demarrerSurveillance() / Donnees.arreterSurveillance()   // §5.5
Donnees.csv.analyser(table, entree)  // → { lignes, colonnesInconnues, problemes, encodage }
Donnees.csv.serialiser(table, lignes, colonnesInconnues) // → Uint8Array
Donnees.csv.ecrireValeur(champ, v) / Donnees.csv.relireValeur(champ, s)   // §3.2
Donnees.evenements                   // EventTarget : 'changement' { detail: { tables: [...] , origine: 'local'|'distant' } }
Donnees.statistiques                 // { conflits, essais } — lu par les tests
```
Types de problèmes : `reference` (clé étrangère cassée), `valeur` (illisible), `excel`
(abîmée par Excel), `colonne`, `encodage`, `doublon` (identifiant en double), `identifiant`
(ligne sans identifiant), `incoherence` (ex. DI acceptée sans OT, voir D18). Un problème `colonne`
est `info` pour une colonne du format v2 absente (§4) et `attention` pour une colonne du brief
absente.

### 5.3 Écriture : `modifier`
```
const resultat = await Donnees.modifier(table, (lignes, outils) => {
  // lignes : COPIE des lignes ; on ajoute ou modifie des objets
  // outils.nouvelId(lignes, dateIso?) : identifiant suivant (recalculé à chaque essai)
  // outils.maintenant(), outils.aujourdhui()
  // lever new Donnees.ErreurValidation('message') pour refuser
  return valeur; // renvoyée par modifier (ex. l'id créé)
}, { action: 'texte libre pour le journal (facultatif)' });
```
La fonction peut être `async` (elle est attendue) : `Magasin.mettreAJourStocks` y relit
`mouvements_stock` pour calculer le stock sur des mouvements frais. Option `journal: false` : rien
n'est écrit au journal par `modifier` (l'appelant journalise lui-même, ex. l'ajustement des gammes
après la remise à zéro d'un compteur, §14.6, ou le repli de `ajouter`, §5.4).
Algorithme : copie des lignes en cache → application de la fonction → sérialisation →
`adaptateur.enregistrer(table, octets, versionConnue)`. Sur `ErreurConflit` : recharger la
table, réappliquer **la même fonction** sur les lignes fraîches, réessayer ; **3 essais au
total**, puis `ErreurConflit` avec le message « Le fichier <table> est modifié en même temps sur
un autre poste. Réessayez dans un instant. ». `Donnees.statistiques.conflits` est incrémenté à
chaque conflit détecté. Après succès : cache mis à jour, événement `changement` (`origine:
'local'`), journal écrit (§5.4) : une entrée par ligne créée (`création`) ou modifiée
(`modification : champ1, champ2`), complétée par `options.action`.

Action sur plusieurs tables (D18) : enchaîner des `modifier()` **idempotents** dans un ordre
sûr. Ex. accepter une DI = (1) `modifier('ordres_travail')` qui réutilise l'OT existant si un OT
porte déjà ce `di_id`, sinon le crée ; (2) `modifier('demandes')` qui vérifie que la DI est
encore `Nouvelle` ou `Différée` avant de la passer `Acceptée` (sinon `ErreurValidation` « déjà
traitée sur un autre poste »).

### 5.4 Écriture par ajout : `ajouter` (journal)
`await Donnees.ajouter(table, nouvellesLignes)` sérialise l'en-tête + les nouvelles lignes
(sans BOM) et appelle `adaptateur.ajouter(table, octets)`. Si l'adaptateur répond
`ErreurConflit` (fichier réenregistré par Excel : encodage ou en-tête différent), repli
automatique sur `modifier(table, l => l.push(...))`. Nos propres lignes ajoutées sont mises dans
le cache, mais la table reste **périmée** : `modifier` la relit toujours avant de la réécrire
(sinon les lignes ajoutées entre-temps par un autre poste seraient perdues). Le rafraîchissement
périodique ne la relit que si sa version a changé depuis notre ajout ; `Donnees.rafraichir()`
appelé explicitement (ex. avant l'export ZIP) relit tout.
Fichier en place qui se termine au milieu d'un texte entre guillemets (guillemet ouvert jamais fermé :
`Donnees.csv.finitDansUnGuillemetOuvert`, miroir `finit_dans_un_guillemet_ouvert` du serveur) : l'adaptateur refuse
l'ajout (`ErreurFichierAbime`, T200), sans repli sur `modifier` ; pour le journal, la ligne manquée ne fait pas
échouer l'action de l'utilisateur (le bandeau « Fichier abîmé » le dit). FORMAT.md §3.

### 5.5 Rafraîchissement
`Donnees.demarrerSurveillance()` : toutes les `rafraichissement_s` secondes (20 par défaut) et à
chaque retour sur l'onglet (`visibilitychange`), `adaptateur.listerVersions()` ; chaque table
dont la version diffère est relue ; événement `changement` (`origine: 'distant'`). Le journal,
écrit par ajout, n'est signalé que s'il a changé sur un autre poste (pas pour nos propres ajouts,
qui ne le font pas relire) : depuis le lot 4, les onglets Suggestions et Décisions en dépendent.

### 5.6 Passage au format courant : `migrerAuFormatCourant` (socle de données, D167-D169)
Vocabulaire, historique des formats, sauvegardes et ZIP : **[FORMAT.md](FORMAT.md)** (référence). Ici, seulement le
contrat de `Donnees`. Le registre d'étapes (1→2, 2→3, 3→4 ; pures, idempotentes, additives) est `Formats.ETAPES`
(`js/formats.js`) ; son miroir Python est `ETAPES_FORMAT` dans `serveur.py`.
- `Donnees.etatDuFormat()` rend le format de départ (le plus petit entre `parametres.version_schema` et la
  signature de chaque fichier) et le format courant ; `Donnees.lectureSeule()` dit si la base est d'un format plus
  récent que l'appli.
- **Mode serveur** : la migration est faite **par le serveur, au démarrage, avant toute connexion**, après une
  sauvegarde `avant-format-vN`. Le navigateur n'écrit rien pour cela (`migrerAuFormatCourant` ne fait rien).
- **Mode dossier** : `await Donnees.migrerAuFormatCourant()` (ancien nom `mettreAJourVersionSchema`, même
  fonction), appelée par `App` après `chargerTout()` et avant toute autre écriture. Elle enchaîne les étapes une à
  une ; **d'abord** une sauvegarde `avant-format-vN`, puis la migration, avec une ligne de journal « passage au
  format N du fichier ; sauvegarde … faite juste avant ». Si la sauvegarde échoue (ou si le stockage ne sait pas
  sauvegarder), `ErreurStockage` et rien n'est migré : la migration est retentée à l'ouverture suivante.
  Un fichier illisible n'est jamais réécrit. Démo : rien n'est écrit.
- **Format plus récent que l'appli** : lecture seule. Le navigateur lève `ErreurLectureSeule` pour toute écriture
  (événement `lectureSeule`) ; le serveur répond 409 `format_plus_recent`.
- **Étape 3→4 (2.2, §25)** : seule étape qui remplit une table qu'elle crée (`reserves_controle`, reprise des
  observations, D183). En mode dossier c'est une phase de plus de `migrerAuFormatCourant`, après les tables
  complétées et avant `version_schema` ; en mode serveur la même phase de `passer_les_fichiers_au_format_courant`.
  Elle passe par la garde « fichier abîmé » ; un conflit (423, Excel) interrompt le passage, `version_schema`
  n'avance pas et le démarrage suivant reprend.
- « Créer une base vide » écrit directement `version_schema` au format courant ; le jeu de démo le porte déjà.
- Deux postes ouverts ensemble sur une base ancienne peuvent faire chacun leur sauvegarde (deux copies identiques,
  sans gravité) ; un seul écrit la version.

## 6. Adaptateurs de stockage (contrat commun)

Chaque fichier `js/stockage-*.js` expose une fabrique : `await StockageServeur.creer()`,
`await StockageDossier.creer(poigneeDossier)`, `StockageDemo.creer(tablesCsv)`. L'objet rendu :

```
mode                                  'serveur' | 'dossier' | 'demo'
libelle                               texte affiché (ex. « Serveur 192.168.1.10:8080 »)
await charger(table)                  → { octets: Uint8Array|null, version: string|null }  (null = fichier absent)
await enregistrer(table, octets, versionAttendue, options?)   → { version }
                                      versionAttendue null = le fichier ne doit pas exister ; sinon ErreurConflit ;
                                      fichier en place abîmé → ErreurFichierAbime, sauf options.remplacerFichierAbime
                                      (import ZIP seulement, T200 ; FORMAT.md §3)
await ajouter(table, octets)          → { version }  (ErreurConflit si en-tête/encodage différent ;
                                      ErreurFichierAbime si le fichier finit dans un guillemet ouvert)
await listerVersions()                → { nomTable: version|null, … }
await ecrireDocument(nom, blob)       → nom   (refuse d'écraser un document existant)
await lireDocument(nom)               → Blob|null
await urlDocument(nom)                → URL affichable (serveur : /api/documents/nom ; sinon URL d'objet)
await sauvegarder(motif?)             → nom de la sauvegarde : manuelle sans motif (AAAA-MM-JJ_HHMMSS) ;
                                      avec un motif de la liste fermée (avant-format-v2, avant-format-v3,
                                      avant-import, avant-import-zip, avant-mise-a-jour)
                                      → AAAA-MM-JJ_HHMMSS_<motif> ; autre motif → ErreurStockage
                                      (avant-import-zip copie aussi documents/ ; FORMAT.md §8)
await sauvegarderAvantMiseAJour(versionAppli)   (dossier seulement) → { sauvegarde: nom ou null, de }
                                      sauvegarde « avant-mise-a-jour » puis derniere-version.json si la version
                                      notée n'est pas versionAppli (le serveur le fait à son démarrage ; FORMAT.md §8)
await listerSauvegardes()             → [{ nom, tables: [...] }]  (plus récente d'abord)
await restaurer(nom, tables?)         → { restaurees: [...], copieSecurite: nom }
await testerSauvegarde(nom)           → { nom, ok, tables: [{ table, lignes, erreur }] }  (serveur seulement, §22.11)
await info()                          → { adressesReseau: [...], port, copieExterne: { derniereReussie, joursSansCopie,
                                      erreur } | null, format: { base, courant, plusRecent, migration, … } }
                                      (serveur, §22.11 et §5.6) ou {}
```
`App` n'utilise l'adaptateur qu'au travers de `Donnees.protegerEcritures(adaptateur)` : en lecture seule (données
d'un format plus récent, §5.6), ses écritures (`enregistrer`, `ajouter`, `ecrireDocument`, `sauvegarder`,
`restaurer`, `sauvegarderAvantMiseAJour`) sont refusées par `ErreurLectureSeule` ; le serveur répond de son côté 409
`format_plus_recent`.
Version d'un fichier = empreinte SHA-256 du contenu, 16 premiers caractères hexadécimaux
(décision D7). Sauvegarde quotidienne : avant la **première écriture de la journée**, copie de
tous les CSV dans `sauvegardes/AAAA-MM-JJ/` (si ce dossier n'existe pas). Une restauration copie
d'abord l'état courant dans `sauvegardes/AAAA-MM-JJ_HHMMSS_avant-restauration/`. Le passage au
format N (§5.6 ; serveur au démarrage, navigateur en mode dossier) copie d'abord tous les CSV dans
`sauvegardes/AAAA-MM-JJ_HHMMSS_avant-format-vN/`. Noms de sauvegarde acceptés (serveur et dossier, mêmes règles) :
`AAAA-MM-JJ`, `AAAA-MM-JJ_HHMMSS`, `AAAA-MM-JJ_HHMMSS_avant-restauration`,
`AAAA-MM-JJ_HHMMSS_avant-format-vN`, `…_avant-import`, `…_avant-import-zip`, `…_avant-mise-a-jour`. Chaque
sauvegarde porte un `manifeste.json` ; les quotidiennes de plus de 30 jours et les manuelles au-delà des 60 plus
récentes sont supprimées (jamais les « avant-… ») : détail dans [FORMAT.md](FORMAT.md) §8 et §9. Le mode dossier
pose une marque `.en-cours` dans une sauvegarde pendant qu'il la copie et l'enlève à la fin : une
sauvegarde qui porte encore la marque est incomplète (ni listée, ni restaurable ; celle du jour est
refaite) — le serveur applique la même règle.

- **Serveur** : tout passe par l'API (§7) ; versions et sauvegardes calculées par le serveur.
- **Dossier** : `showDirectoryPicker({ mode: 'readwrite' })` ; poignée mémorisée dans
  IndexedDB (base `prevo`, magasin `poignees`, clé `dossier`) pour « Reprendre le dossier
  précédent » (`queryPermission` puis `requestPermission`, si ces méthodes existent) ; empreintes
  par `crypto.subtle` (le mode dossier est toujours en contexte sécurisé) ; écriture par
  `createWritable()`, en faisant d'abord la sauvegarde quotidienne, puis en relisant et
  comparant le fichier, et en vérifiant juste avant `close()` qu'il n'a pas changé (sinon
  `abort()` + `ErreurConflit`) ; un dossier devenu inaccessible lève `ErreurStockage` (jamais
  « fichier absent », qui ferait croire à une base vide) ; `verrou.txt` à la racine du dossier choisi (`poste;AAAA-MM-JJ HH:MM:SS;idSession`),
  rafraîchi toutes les 60 s : si un verrou d'une autre session a moins de 3 minutes, avertissement
  non bloquant. Sous-dossiers `documents/` et `sauvegardes/` créés au besoin.
- **Démo** : tout en mémoire ; versions = compteur ; `sauvegarder`/`restaurer` indisponibles
  (message). Décalage des dates à la création (§11). Bandeau permanent « Démo — rien n'est
  enregistré » et bouton « Exporter en ZIP » (gérés par `App`).

## 7. API du serveur (`serveur.py`)

Réponses JSON `{"erreur": "message en français"}` en cas d'erreur. D157 (T246) : le message porte aussi son code
et ses valeurs, `"erreur_code"` (clé `serveur.<code>` de `js/i18n/fr.js`) et `"erreur_valeurs"` s'il en a ; le
navigateur affiche la clé dans sa langue, le français reçu sinon (`StockageServeur.texte`). Même règle pour tout champ
qui porte un message (`message`, `raison`… ; une liste de messages : `<champ>_codes`). Toute requête qui écrit
(`PUT`, `POST`) exige l'en-tête **`X-Prevo: 1`** (sinon 403). Corps limité à **10 Mo**, **50 Mo** pour
l'envoi d'une table (`PUT /api/csv/<table>`, `POST /api/csv/<table>/ajout` : T208, `TAILLE_MAX_CORPS_CSV`)
(`Content-Length` obligatoire : 411 sinon, 413 au-delà). En-tête `Host` accepté seulement pour
une adresse IP, `localhost`, le nom du PC seul ou suivi d'un suffixe de réseau local
(`.local`, `.lan`, `.home`, `.localdomain`, `.home.arpa`, `.internal`, `.intranet`) ou un nom donné
par `--hote` — sinon 403 (un suffixe quelconque permettrait le « DNS rebinding »).

| Méthode et chemin | Réponse |
| --- | --- |
| `GET /api/ping` | `{"application": "Prévo", "version": "…", "api": 1}` |
| `GET /api/info` | `{"port": 8080, "adresse_locale": "http://localhost:8080/", "adresses_reseau": ["http://192.168.1.10:8080/"]}` |
| `GET /api/versions` | `{"tables": {"equipements": {"version": "…", "modifie": "AAAA-MM-JJ HH:MM:SS"} ou null, …}}` (les 22 tables) |
| `GET /api/csv/<table>` | octets du fichier, en-tête `X-Version` ; 404 si absent |
| `PUT /api/csv/<table>` | en-tête `X-Version-Attendue: <version>` ou `aucune` ; 200 `{"version"}` · 409 `{"erreur", "version_actuelle"}` · 409 `{"erreur", "code": "fichier_abime", "table"}` si le fichier en place est abîmé (T200 ; en-tête `X-Prevo-Remplacer-Abime: 1` pour le remplacer quand même : import ZIP seulement ; avec les comptes, 403 si la session n'est pas celle d'un responsable) · 423 si le fichier est verrouillé (Excel ouvert) |
| `POST /api/csv/<table>/ajout` | corps = en-tête + lignes (UTF-8 sans BOM) ; ajoute en fin de fichier (crée le fichier avec BOM s'il n'existe pas) ; 409 si l'en-tête ou l'encodage du fichier existant diffère · 409 `{"erreur", "code": "fichier_abime", "table"}` si le fichier en place finit dans un guillemet ouvert (T200) |
| `GET /api/documents/<nom>` | octets, type MIME d'après l'extension, `Content-Security-Policy: sandbox`, `Content-Disposition: attachment; filename="<nom>"` hors images (jpg, jpeg, png, gif, webp), PDF et rapport figé en html (ouvert dans un onglet, `sandbox`) (audit F4, §22.12) ; 404 ; 415 extension inconnue |
| `PUT /api/documents/<nom>` | 201 `{"nom"}` avec le **nom imposé par le serveur** `AAAAMMJJ-HHMMSS-<nom demandé>` (horodatage du serveur, extension en minuscules : le navigateur garde ce nom, jamais celui qu'il a demandé) · 400 nom refusé, ou image dont le contenu n'a pas la signature de son format (`verifier_signature_image` : `FF D8 FF`, `89 50 4E 47 0D 0A 1A 0A`, `GIF87a`/`GIF89a`, `RIFF…WEBP`) · 409 même nom demandé dans la même seconde (jamais d'écrasement) · 413 dossier `documents/` plein (`quota_documents_mo`, 4096 par défaut depuis T250, mesuré à chaque envoi) · 415 extension inconnue (`.doc` et `.xls` retirés) ; rien n'est écrit en cas de refus |
| `POST /api/sauvegarde` | corps vide → sauvegarde manuelle `{"sauvegarde": "AAAA-MM-JJ_HHMMSS"}` ; corps JSON facultatif `{"motif": "avant-format-v2"}` → `{"sauvegarde": "AAAA-MM-JJ_HHMMSS_avant-format-v2"}` (motif `avant-import` depuis le lot 5, §18.1) ; motif hors de la liste fermée `MOTIFS_SAUVEGARDE`, corps qui n'est pas un objet JSON, JSON invalide ou trop imbriqué → 400 (contrôlé avant toute écriture) |
| `GET /api/sauvegardes` | `{"sauvegardes": [{"nom", "tables": [...]}]}` |
| `POST /api/restauration` | corps `{"sauvegarde": "…", "tables": [...] (facultatif)}` → `{"restaurees", "copie_securite"}` |

Règles : noms de tables limités aux 22 du schéma (liste recopiée dans `serveur.py`, avec un
commentaire de renvoi vers `js/schema.js`, cohérence vérifiée par un test) ; nom de document demandé
`^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$` sans `..`, nom enregistré précédé de `AAAAMMJJ-HHMMSS-` (préfixe facultatif à la
lecture : les documents d'avant le lot 7 n'en ont pas), extensions de `TYPES_DOCUMENTS` seulement ; nom de sauvegarde
`^\d{4}-\d{2}-\d{2}(_\d{6}(_avant-restauration|_avant-format-v\d+|_avant-import-zip|_avant-import|_avant-mise-a-jour)?)?$` ; tout chemin résolu doit
rester sous `donnees/` (vérification sur le chemin brut **et** décodé, `\` compris) ; écriture
atomique (fichier temporaire dans le même dossier, `fsync`, `os.replace`) ; un verrou global
sérialise les écritures ; au plus 32 requêtes servies en même temps pour tout le processus (`BoundedSemaphore` pris
par chaque fil de service, la suivante attend son tour sans être refusée : audit F2, §22.12) ; sauvegarde quotidienne faite par le serveur avant la première écriture
du jour. Les corps JSON (`/api/sauvegarde`, `/api/restauration`) sont lus par `lire_objet_json` :
UTF-8 invalide, JSON invalide, JSON qui n'est pas un objet ou trop imbriqué (`[[[[…`) → 400, jamais
500.

**Fichiers statiques : liste blanche (lot 2, D29).** Seuls sont servis `/` (→ `index.html`),
`index.html`, `favicon.svg`, `GUIDE.html` s'il existe, et tout ce qui est sous `css/`, `js/` et `acces/` (lot 7,
porte d'entrée, §22.6)
(constantes `FICHIERS_PUBLICS`, `DOSSIERS_PUBLICS` de `serveur.py` ; comparaison sans casse, car
Windows ne distingue pas `Index.html` de `index.html`). **Tout le reste répond 404**, comme un
fichier absent : `docs/brief-gmao.md`, `README.md`, `docs/`, `tests/`, `outils/`, `reference-design/`,
`serveur.py`, les lanceurs… La liste blanche est contrôlée sur le chemin demandé **et** sur le chemin
résolu (un lien ou une jonction rangé dans `js/` ne permet pas de lire un fichier situé ailleurs).
Les contrôles du lot 1 restent en place avant elle : chemin dont un segment commence par `.`
(fichier caché, `..`), contient `:` ou finit par `.` ou une espace, `\` ou `%5C`, double encodage →
400 ; `donnees/` → 403. L'option `--servir-tests` (passée par `tests/commun.py`) sert en plus
`tests/fixtures/` (pages et fichiers d'essai des tests). Pas d'en-têtes CORS.
Le serveur parle HTTP/1.1 avec connexions persistantes (`protocol_version = 'HTTP/1.1'` : un
navigateur réutilise ses connexions au lieu d'en ouvrir une par requête), avec une file d'attente
d'écoute de 128 connexions (`request_queue_size = 128`) et un fil par connexion.
**Lot 7 (§22)** : quand les comptes sont exigés, toute route `/api/` répond **401** sans session ni appareil enrôlé et **403** hors du rôle (table `ROLES_PAR_ROUTE`, §22.5) ; routes `/api/connexion`, `/api/session`, `/api/acces/…` (§22.4), `/api/installation/…` (loopback, §22.10) ; fichiers publics `/acces/…` de la porte d'entrée (§22.6) ; sauvegardes (§22.11) : `POST /api/sauvegarde` manuelle limitée à une par minute (**429**, `Retry-After`) et purgée au-delà de 60, `POST /api/sauvegarde/tester`, `copie_externe` dans `GET /api/info`.
Lancement : `py serveur.py [--port 8080] [--donnees CHEMIN] [--sans-navigateur] [--hote NOM]
[--servir-tests]` ; port suivant si occupé (jusqu'à +20) ; affiche l'adresse locale et les adresses
réseau ; ouvre le navigateur. `--servir-tests` n'est utile qu'aux tests automatiques.
Adresses réseau : interface de sortie trouvée par un `connect()` UDP vers une adresse privée
(aucun paquet envoyé) + `gethostbyname_ex`, adresses de bouclage exclues.
Lot 4 (§17.2) : `POST /api/ia` relaie l'appel du navigateur vers le fournisseur d'IA (liste fermée de
chemins, sans redirection, délai et taille plafonnés, fournisseur en ligne refusé en 403 sans
l'autorisation du responsable) ; `--certificat FICHIER --cle FICHIER` (les deux ensemble) font passer
le serveur en https (adresses, `/api/info` et QR en `https://`).

## 8. Application (`js/app.js`, `index.html`)

**Démarrage** : si la page est en `http(s)` et que `GET /api/ping` répond (délai 2 s) → mode
serveur. Sinon écran de démarrage : « Choisir le dossier de données » (si
`showDirectoryPicker` existe), « Reprendre le dossier précédent » (si une poignée est mémorisée),
« Essayer avec les données de démo », zone de dépôt de CSV (démo à partir de fichiers déposés).
Base vide (aucun CSV) → choix « Créer une base vide » ou « Partir des données de démo ».
Navigateur sans File System Access → message « utilisez Chrome ou Edge » + démo.

Suite du démarrage (lot 2), dans cet ordre, **avant le premier écran** :
1. tables chargées → `Donnees.migrerAuFormatCourant()` (§5.6) en mode dossier, pour tous les profils et avant
   toute autre écriture (en mode serveur, le serveur a déjà migré au démarrage) ; données d'un format plus récent :
   lecture seule signalée par un bandeau ; en cas d'échec (sauvegarde impossible), l'erreur est signalée, un bandeau
   « Les fichiers n'ont pas pu passer au format courant » s'affiche dans la coque, et l'application reste utilisable
   (détail et règles : [FORMAT.md](FORMAT.md)) ;
2. profil (mémorisé ou demandé ; comptes exigés : déduit de la session, voir ci-dessous et §22.4) ;
3. technicien ou responsable : `Preventif.genererOTEchus()` (RG5, §14.3) ; toast « n OT préventifs
   générés » si n > 0 ; erreur → `App.signalerErreur`, l'application reste utilisable. **Pas de
   génération automatique si l'étape 1 a échoué** (elle écrirait avant la sauvegarde de migration, sans
   sauvegarde confirmée) : la prochaine ouverture retente tout. Puis
   `performance.mark('prevo:preventif')`, posée une seule fois, aussi pour le demandeur (rien à
   générer) ;
4. surveillance, coque, premier écran, état « prêt » (`prevo:preventif` précède donc `prevo:pret`).

**Profils** (localStorage `prevo.profil` = JSON `{type: 'demandeur'|'technicien'|'responsable',
nom, technicienId}` ; `prevo.poste` = nom du poste). Si aucun profil n'est mémorisé, l'écran de
profil s'affiche, puis l'application revient à la route demandée (cas du QR scanné).

**Comptes exigés** (lot 7, D126, T155 ; mode serveur avec `comptes` vrai) : avant la lecture des tables,
`GET /api/session` (`adaptateur.session()`) ; sans session, l'écran de connexion (`#ecran-connexion`, module
`Connexion` de `js/modules/connexion-ecrans.js`, état `'connexion'`) ; le profil est **déduit de la session** (`role` →
`type`, `prenom` + `nom` → `nom`, `technicien_id` → `technicienId` ; un appareil enrôlé : le nom saisi, type
`demandeur`), l'écran de profil de 1.2 ne s'affiche jamais et `prevo.profil` n'est plus écrit (`prevo.poste` reste).
Un mot de passe provisoire (`a_changer`) est changé avant tout. Pendant l'usage, l'événement `prevo:session-absente`
(401 relu par `stockage-serveur.js`) ramène l'écran de connexion par-dessus l'écran courant, sans changer la route.
T329 (décisions de Nicolas du 07/11) : la page ne se recharge pas (même quand la langue du compte n'est pas celle du
poste) ; l'écran de connexion reste dans la langue où la personne travaillait, avec le message
`socle.session_perdue.reconnectez_vous_meme_compte` ; l'écran courant n'est ni vidé ni reconstruit, et les fenêtres
ouvertes (`dialog[open]`) sont fermées sans être retirées (sinon, modales, elles rendraient l'écran de connexion
inerte). Le **même compte avec les mêmes droits** (identifiant, rôle, technicien lié) retrouve l'écran, le défilement
et ses fenêtres rouvertes telles quelles (toast `socle.session_perdue.reconnecte_saisie_gardee`), puis enregistre ;
le rafraîchissement habituel relit ensuite les tables. **Un autre compte**, ou des droits changés : les fenêtres sont
abandonnées (événement `cancel`, comme Échap : `UI.fenetre` rend null), puis les tables sont relues et la coque se
rouvre sur la même route (dans la langue du nouveau compte) : la saisie n'est ni montrée ni enregistrée sous un autre
nom. Pendant l'écran de connexion, une erreur 401 n'ajoute pas de toast (`App.signalerErreur`). Le bouton de profil du menu et
l'entrée « Plus » du téléphone deviennent « se déconnecter » (`POST /api/deconnexion`, puis l'écran de connexion) ;
`App.changerProfil()` fait de même ; un appareil enrôlé n'a aucun bouton (seul le responsable le révoque). Le menu
affiche « Prénom Nom · Rôle ». Sans comptes (portée « ce PC »), en modes dossier et démo : rien ne change.

**Brouillons gardés sur l'appareil** (T329, décisions de Nicolas du 07/11 ; `js/modules/brouillons.js`, objet
`Brouillons`, chargé juste après `poste.js`) : la déclaration de panne (`#/di/nouvelle`) et le compte rendu d'un OT
(onglet Compte rendu) survivent à un onglet déchargé par le navigateur (téléphone en veille), à un rechargement ou à
une session perdue. Clé `localStorage` « prevo.brouillon|<base>|<auteur>|<nom> » (`App.porteeDesBrouillons()` : base
`serveur` ou `dossier:<nom du dossier>` ; auteur `compte:<identifiant>`, `compte:appareil:<id>` pour un appareil enrôlé,
sans comptes `profil:<type>:<technicien ou nom>` ; '' en démo et en lecture seule : aucun brouillon) ; valeur
`{ le, valeurs, depart, … }` (noms `demande` et `compte-rendu|<OT>`). Règles : lié au compte qui l'a tapé, jamais montré
à un autre (la clé porte l'auteur) ; écrit 400 ms après la dernière frappe et aussitôt quand la page passe en
arrière-plan (`visibilitychange`, `pagehide`), seulement s'il diffère des valeurs enregistrées (`depart`), sinon
effacé ; effacé à l'enregistrement (`suivi.terminer()`), par « Abandonner le brouillon », ou au bout de 7 jours (lu
périmé, et `Brouillons.purger()` à l'ouverture, tous auteurs) ; **rien ne part au serveur**. Reprise : bandeau
« Brouillon repris » ; déclaration commencée pour un autre équipement ou un autre OT d'origine : bandeau « La
reprendre » (une nouvelle la remplace) ; la photo n'est jamais gardée (le bandeau le dit) ; compte rendu enregistré
ailleurs depuis (`depart` différent) : avertissement, rien n'est fusionné ; l'OT s'ouvre sur l'onglet Compte rendu ;
OT devenu non modifiable : texte montré à recopier, « Effacer le brouillon ». Sans comptes, le profil étant
déclaratif, qui prend le même profil sur le poste voit ses brouillons. Tests : `tests/test_saisie_gardee.py`.

**État prêt** : quand les tables sont chargées et le premier écran affiché,
`document.documentElement.dataset.etat = 'pret'` et `performance.mark('prevo:pret')` (lus par
les tests). Pendant le chargement : `'chargement'` ; écran de démarrage : `'demarrage'` ; écran
de profil : `'profil'` ; écran de connexion (comptes exigés) : `'connexion'`.

**Navigation** : routes en `#/…`. Les modules s'enregistrent :
```js
// App est chargé APRÈS les modules : chaque module enregistre ses écrans dans un écouteur
// DOMContentLoaded (App existe alors) ; App démarre ensuite (son écouteur est ajouté en dernier).
document.addEventListener('DOMContentLoaded', () => {
  App.ecran({
    id: 'liste-di', route: /^#\/di$/, titre: 'Demandes',
    menu: { libelle: 'Demandes', court: 'Demandes', icone: 'demandes', ordre: 20, groupe: '…', lien: '#/di' },  // facultatif
    profils: ['demandeur', 'technicien', 'responsable'],
    tables: ['demandes', 'equipements'],     // réaffichage si une de ces tables change sur un autre poste
    parent: 'parc',                          // facultatif : entrée de menu à allumer (sinon la sienne)
    afficher(conteneur, parametres) { … },   // peut être async
  });
});
```
Contrat tel qu'implémenté :
- un module a **un seul** écouteur `DOMContentLoaded`, qui enregistre tous ses écrans : dans le
  dernier fichier du préfixe (`parc-fiche.js`, `demandes-fiche.js`, `ordres-impression.js`,
  `magasin-achats.js`), sauf Préventif où c'est `preventif-ecrans.js` (§14.2) ;
- `conteneur` est `<main id="contenu">`, vidé avant chaque affichage ;
- `parametres` : les **groupes nommés** de la route (`(?<id>[^/?]+)` → `parametres.id`),
  `parametres.groupes` (tous les groupes, dans l'ordre), `parametres.requete` (`URLSearchParams` de
  la partie après `?` du hash) et `parametres.chemin` ;
- les routes sont essayées dans l'ordre d'enregistrement, la première qui correspond gagne : les
  routes précises (`#/ot/nouveau`) se déclarent avant les routes à identifiant (`#/ot/<id>`) ;
- un écran interdit au profil courant renvoie à l'accueil, avec un message ;
- **saisie en cours** : tout événement `input` ou `change` dans `#contenu` la signale, sauf dans un
  élément `[data-hors-saisie]` (ex. le formulaire de filtres d'une liste) ; `App.marquerSaisie(true|false)`
  la pose ou l'efface (`false` après un enregistrement) ; un réaffichage l'efface aussi.
Routes du lot 1 : `#/accueil`, `#/di/nouvelle`, `#/di`, `#/di/<id>`, `#/ot`, `#/ot/nouveau`,
`#/ot/<id>`, `#/parc`, `#/equipement/nouveau`, `#/equipement/<id>`,
`#/equipement/<id>/modifier`, `#/parametres`, `#/controle`, `#/apropos`.
Routes ajoutées au lot 2 : `#/preventif`, `#/preventif/gamme/nouvelle`, `#/preventif/gamme/<id>`,
`#/magasin`, `#/magasin/article/nouveau`, `#/magasin/article/<id>`. Les routes « fiche » excluent
explicitement `nouveau`/`nouvelle` (`(?!nouveau$)`), en plus d'être déclarées après la route de
création.
Routes ajoutées au lot 3 (§15.1) : `#/planning`, `#/controles`, `#/controles/nouveau`,
`#/controles/<id>`, `#/indicateurs`, `#/equipe`, `#/equipe/nouveau`, `#/equipe/<id>`,
`#/parc/etiquettes`.
Profils : l'accueil, les DI, le parc et À propos sont ouverts aux trois profils ; les OT
(`#/ot`, `#/ot/<id>`), le préventif (`#/preventif`, `#/preventif/gamme/<id>`) et le magasin
(`#/magasin`, `#/magasin/article/<id>`) au technicien et au responsable (le technicien y est en
consultation, D27) ; `#/ot/nouveau`, la création et la modification d'équipement,
`#/preventif/gamme/nouvelle`, `#/magasin/article/nouveau`, `#/parametres` et `#/controle` au
responsable seul. Le demandeur ne voit ni Préventif ni Magasin.
Lot 3 (§15.2) : le planning, les contrôles (liste et fiche) et l'équipe (liste et fiche) sont
ouverts au technicien en lecture et au responsable ; le technicien ne voit aucun taux horaire (ni à
l'écran ni dans le DOM). Les indicateurs (onglet des rapports compris), les étiquettes,
`#/controles/nouveau` et `#/equipe/nouveau` sont réservés au responsable. Le demandeur ne voit
aucun écran du lot 3.
Paramètres d'adresse lus :
- `#/di` : `?statut=` (ex. `Nouvelle`), `?portee=` (`mes` ou `toutes`), `?q=` (recherche), `?equipement=` ;
- `#/ot` : `?filtre=retard` (OT en retard) ou `?filtre=p1` (P1 ouverts), liens de l'accueil ; aussi
  `?etat=` (`ouverts`, `retard`, `clotures`, `annules`, `tous`), `?statut=`, `?priorite=`,
  `?technicien=`, `?type=`, `?recherche=`, `?equipement=` ;
- `#/di/nouvelle` : `?equipement=`, `?ot=` (OT préventif d'origine : DI liée, §14.6) ;
  `#/ot/nouveau` : `?equipement=`, `?urgence=1` ;
- `#/preventif` : `?onglet=gammes|calendrier`, `?statut=` (un statut de gamme, ex. `echue`),
  `?equipement=` ; `#/preventif/gamme/nouvelle` : `?equipement=` ;
- `#/magasin` : `?onglet=articles|mouvements|inventaire|a-commander|achats|fournisseurs` (l'onglet
  « Inventaire » est réservé au responsable) ; filtres d'un lien, appliqués une fois : articles
  `?recherche=`, `?categorie=`, `?etat=` ; mouvements `?type=`, `?article=`, `?ot=` ; achats
  `?recherche=` ;
- lot 3 : `#/ot/nouveau` lit aussi `?type=` et `?titre=` (OT réglementaire créé depuis un contrôle) ;
  `#/planning` : `?semaine=` (un lundi), `?technicien=` ; `#/controles` : `?statut=`, `?filtre=30j`,
  `?equipement=`, `?recherche=`, `?inactifs=1` ; `#/controles/nouveau` : `?equipement=` ;
  `#/indicateurs` : `?periode=` (`mois`, `mois-precedent`, `3-mois`, `12-mois`, `du-au` avec `?du=` et
  `?au=`), `?criticite=`, `?atelier=`, `?onglet=tableau|rapports` ; `#/equipe` : `?filtre=a-renouveler` ;
  `#/parc/etiquettes` : `?localisation=`, `?criticite=`, `?ids=` (identifiants séparés par des virgules).
- lot 3 bis (§16.6) : `#/preventif` : `?onglet=suggestions|decisions` (responsable ; un autre profil est
  renvoyé à l'accueil avec le message des écrans interdits) ; `#/preventif/gamme/nouvelle` :
  `?suggestion=<clé>` (avec `?equipement=`) ; `#/preventif/gamme/<id>` : `?suggestion=<clé>`.

Un écran dont un formulaire a été modifié et non enregistré n'est pas
réaffiché par un changement distant : un bandeau « Des données ont changé sur un autre poste —
Actualiser » s'affiche à la place.
`App` expose : `App.version`, `App.dateVersion`, `App.mode`, `App.profil`, `App.poste`,
`App.adaptateur`, `App.ecran(définition)`, `App.naviguer(hash)`, `App.reafficher()`,
`App.definirTitre(texte)`, `App.marquerSaisie(booléen)`, `App.estResponsable()`,
`App.estTechnicien()`, `App.estDemandeur()`, `App.libelleProfil()`, `App.changerProfil()`,
`App.urlFicheEquipement(id)` (URL réseau en mode serveur — depuis le lot 3, `adresse_qr` quand
elle est renseignée —, sinon `GMAO:<id>`), `App.chargerScriptDemo()`, `App.exporterZip()`,
`App.signalerErreur(erreur)` (texte de `App.messageErreur(erreur)` ; `App.raisonErreur(erreur)`
pour le glisser dans une phrase ; fichier abîmé : texte selon le rôle, T201), depuis le lot 3
`App.chargerEcharts()` et `App.adressesReseau()` (§15.1), et depuis le lot 5 `App.chargerSheetJS()` (§18.1).

**Menu** : latéral sur grand écran (≥ 1100 px), repliable en icônes (mémorisé
`prevo.menuReplie`), icônes seules de 641 à 1099 px, barre du bas sur téléphone (≤ 640 px :
4 entrées + « Plus »). En tête du menu latéral : « Prévo », « GMAO », puis le nom de l'entreprise
(`entreprise_nom`) sur deux lignes au plus, nom complet en infobulle (D32). Entrées ajoutées au
lot 2 : « Préventif » (ordre 35, icône `preventif`) et « Magasin » (ordre 45, icône `magasin`) ;
au lot 3 : « Planning » (33), « Contrôles » (37), « Indicateurs » (50) et « Équipe » (85, groupe
« Administration », avant Paramètres).
Badge de signature en bas du menu : « Développé par Claude (Anthropic) à
la demande de Nicolas Briand — SELECTIS » → `#/apropos`.
`#impression` doit être un enfant direct de `<body>` (la feuille d'impression masque tous les autres
enfants de `body`) ; `#toast` (vide, `role="status"`) est présent dans `index.html` dès le chargement.

**Lot 4 (§17)** : dès la lecture de `js/app.js`, le thème du poste est posé (`<html
data-theme="clair">`, `Poste.appliquerTheme`) avant le premier écran ; après le chargement des
tables, `Ia.verifierAuDemarrage()` (un seul test du fournisseur si l'IA est active sur le poste, aucun
appel sinon) et `Dictee.surveiller(document.body)` (boutons micro posés au fil des écrans). Route
`#/poste` « Ce poste » pour les trois profils.

**Lot 5 (§18)** : route `#/import` « Importer des données », **responsable seulement**, sans entrée de
menu (carte de Paramètres ; carte de l'accueil du responsable quand la base n'a aucun équipement) ;
SheetJS n'est jamais chargé au démarrage.

## 9. Interface (`js/interface.js`, `css/style.css`)

`UI.$`, `UI.$$`, `UI.echapper(s)`, `` UI.html`…${v}…` `` (échappe chaque valeur ; un tableau
est joint ; `UI.brut(s)` pour un fragment déjà sûr), `UI.dateFr`, `UI.dateHeureFr`,
`UI.nombreFr(v, decimales)`, `UI.euro`, `UI.heures`, `UI.badgePriorite(p)` (couleur **et**
libellé), `UI.badgeStatut(s)`, `UI.toast(message, type)`, `await UI.fenetre({ titre, contenu,
boutons })`, `await UI.confirmer(message)`, `await UI.demanderMotif(titre, libelle)` (texte non
vide ou `null`), `UI.tableau({ colonnes, lignes, surClic, triInitial, vide })` (tri par clic
sur l'en-tête), `UI.champ(champSchema, valeur, options)`, `UI.lireFormulaire(form)`,
`UI.selecteurEquipement(conteneur, { valeur, surChoix })` (recherche par repère/désignation +
bouton scan si caméra disponible), `await UI.scannerQR()`, `UI.qrSvg(texte, taille)`,
`await UI.redimensionnerPhoto(fichier, 1280)` (JPEG), `UI.telecharger(nom, blob)`,
`UI.onglets(conteneur, onglets)`, `UI.bandeau(type, html)`.

CSS : variables et composants de la charte Cockpit (`--fond`, `--carte`, `--bleu`, `--cyan`,
`--vert`, `--rouge`, `--ambre`, `--violet`, `--muted`, `--rayon`…), police Sora, `.btn-*`,
`.carte`, `.grille` + `.c4`…`.c12`, `.instruments`, `.alerte.attention|important`, `.table`,
`.badge`, `.dialogue`, `.toast`. Priorités : `.prio-p1` (`--rouge`), `.prio-p2` (`--ambre`),
`.prio-p3` (`--cyan`), `.prio-p4` (`--muted`), toujours avec le texte P1…P4. Texte, champs,
boutons et cellules en 16 px ; badges et en-têtes de colonnes 13–14 px. Sur téléphone, toute
zone tactile mesure au moins 48 px de haut (gants). `@media print` : noir sur blanc, menu et
boutons masqués, mise en page A4 du bon de travail (`#impression`) ; classe `.sans-impression`
pour masquer un élément à l'impression (le rapport mensuel du lot 3, document autonome, en
définit une copie dans ses propres styles).

`css/style.css` porte la charte et **tous les composants communs** ; un module n'y touche pas :
sa mise en page propre va dans `css/modules/<module>.css` (une feuille par module, même découpé en
plusieurs fichiers JS ; toutes référencées par `index.html`, dont `preventif.css` et `magasin.css`
au lot 2, `equipe.css`, `controles.css`, `planning.css`, `indicateurs.css` et `etiquettes.css` au
lot 3), en réutilisant les variables de la charte (jamais de couleur codée en dur).
`UI.icone(nom)` connaît depuis le lot 2 les icônes `preventif` (calendrier coché) et `magasin`
(carton), et depuis le lot 3 `planning`, `controles`, `indicateurs` et `equipe` ; `UI.estTelephone()` sert à masquer la carte « Connecter un téléphone » de l'accueil (D31).
Les champs `texte_long` des formulaires portent l'attribut `data-dictee` (crochet pour le bouton
micro du lot 4 ; en attendant, la dictée du clavier du téléphone fonctionne sans code).

## 10. Règles métier (lots 1 à 3 bis)

RG1 à RG4, RG7 et RG8 viennent du lot 1 (RG3 révisée au lot 2, voir ci-dessous) ; RG5 (préventif)
et RG6 (magasin) sont détaillées aux §14.3 et §14.4 ; RG9 (contrôles réglementaires, lot 3) au
§15.7. Depuis le lot 3, RG8 est aussi vérifiée quand on planifie un OT (§15.5), avec le même
avertissement au journal.

- **RG1** DI : `Nouvelle` → `Acceptée` (crée un OT, `ot_id` renseigné) · `Regroupée`
  (rattachée à un OT ouvert du même équipement) · `Différée` · `Refusée` (motif obligatoire,
  visible du demandeur). Une DI `Différée` peut ensuite être acceptée, regroupée ou refusée.
- **RG2** priorité = matrice criticité × impact ; `sécurité` → P1 et bandeau rouge.

  | Criticité \ Impact | gêne | dégradé | arrêt |
  | --- | --- | --- | --- |
  | A | P2 | P1 | P1 |
  | B | P3 | P2 | P1 |
  | C | P4 | P3 | P2 |

  Modification par le responsable avec motif obligatoire, tracé au journal
  (« priorité P2 → P1 : <motif> »). Date prévue par défaut = création + `delai_pN_h`.
- **RG3** transitions d'OT :

  | De | Vers |
  | --- | --- |
  | Créé | Préparé, En attente, Annulé ; En cours si `origine` = `urgence` ou `type` = `correctif immédiat` |
  | Préparé | Planifié, En attente, Annulé |
  | Planifié | En cours, Préparé (déplanifier), En attente, Annulé |
  | En cours | Clôturé techniquement, En attente |
  | En attente | statut de reprise (En cours si `date_debut` est renseignée, sinon Préparé), Annulé |
  | Clôturé techniquement | Clôturé administrativement ; En cours (réouverture, responsable) |
  | Clôturé administrativement, Annulé | aucun (verrouillé ; reprise par un nouvel OT lié `ot_lie_id`) |

  `En attente` exige `motif_attente`, `Annulé` exige `motif_annulation`. `Planifié` exige un
  technicien et une date prévue, et est **refusé si une pièce prévue manque en stock** : message +
  bouton « Mettre en attente (motif : pièce) ».
  **Révision du lot 2 (décision de l'orchestrateur)** : depuis que des pièces peuvent être sorties
  du magasin pour l'OT avant sa planification, le lot 1 refusait à tort un OT dont les pièces
  étaient déjà sorties. Désormais, pour chaque article prévu : besoin restant = max(0, quantité
  prévue cumulée − net déjà sorti pour **cet** OT (sorties − retours)) ; la pièce manque si
  `Donnees.stockArticle` < besoin restant. Le message cite ce qui est déjà sorti : « Stock
  insuffisant pour « … » : 3 prévu(s), 1 déjà sorti(s) pour cet OT, 1 en stock. » (sans sortie :
  « 3 prévu(s), 1 en stock », comme au lot 1). Le même calcul sert au bandeau de l'onglet
  Préparation (`Ordres.piecesManquantes`).
- **RG4** clôture technique bloquée sans : `date_fin`, au moins un temps passé (`ot_temps`),
  `cause_code`, `remede_code`, `compte_rendu` d'au moins 10 caractères (et sur un correctif,
  « RAS » / « rien à signaler » refusé), `remise_service` = 1. Le message liste **tous** les
  manques. La procédure de consignation de l'équipement s'affiche sur l'OT avec le rappel :
  « Cocher une case ne consigne rien : appliquez la procédure. » Clôture administrative
  (responsable) : `date_cloture_admin`, OT en lecture seule.
- **RG7** coût = Σ (heures × `taux_horaire` du technicien) + Σ (sorties de stock imputées à
  l'OT − retours) × `prix_unitaire` + `cout_soustraitance`. Depuis le lot 2, les sorties et
  retours se font depuis l'OT (bloc « Pièces sorties », §14.6). Le prix pris est le prix **actuel**
  de l'article (aucun prix n'est stocké dans `mouvements_stock`) : le coût d'un OT passé suit donc
  un changement de prix (limite connue de D24).
- **RG8** (lot 1 : à l'affectation) : si l'équipement a une `habilitation_requise` (une ou
  plusieurs, séparées par `,` ou `/`), le technicien doit avoir pour chacune une habilitation
  d'intitulé identique (casse ignorée) avec `date_obtention` ≤ date prévue (ou aujourd'hui) ≤
  `date_echeance`. Sinon : **avertissement** (pas de blocage) affiché et inscrit au journal
  (« avertissement habilitation : TEC-0004 sans BR valide au 2026-10-21 »).
  Limite côté serveur (T445, réponse provisoire, à confirmer) : RG8 est tenue par l'application seule ; en mode
  serveur avec comptes, le serveur réserve l'écriture de `habilitations` au responsable mais ne contrôle pas RG8 dans
  `ordres_travail` (§22.5).
- « OT en retard » : statut ni clôturé ni annulé et `date_prevue` < aujourd'hui. « P1 ouvert » :
  priorité P1, statut ni clôturé ni annulé. « DI à traiter » : statut `Nouvelle`.

Les fonctions de règles sont **pures** et exposées pour les tests :
`Demandes.prioriteCalculee(criticite, impact)`, `Ordres.transitionsPossibles(ot)`,
`Ordres.verifierPassage(ot, statutCible)` → `{ ok, erreurs, avertissements }`,
`Ordres.verifierCloture(ot)` → liste des manques, `Ordres.cout(ot)`,
`Ordres.verifierHabilitation(equipement, technicienId, dateIso)` → message ou `null`.

### API effective des modules (`js/modules/`, état du lot 3 bis)

Un module = un objet global, réparti sur un préfixe de fichiers (§14.2) ; ses écrans s'enregistrent
dans un seul écouteur `DOMContentLoaded` (§8). Les fonctions d'écriture sont `async`, passent par
`Donnees.modifier` (contrôles refaits **dans** la fonction de mutation, sur les lignes fraîches) et
lèvent `Donnees.ErreurValidation` pour un refus. Chaque module découpé a aussi un objet
`Objet.interne` (`Ordres.interne`, `Preventif.interne`…) : outils partagés entre ses fichiers,
**pas une API** (ni les autres modules ni les tests ne s'en servent ; son contenu peut changer).
La liste ci-dessous est celle des clés réellement exposées (relevée dans le code).

- **`Parc`** : `cheminLocalisation(id)`, `libelleEquipement(id)`, `verifierEquipement`,
  `verifierLocalisation` (règles : repère unique parmi les équipements actifs, aucun équipement
  ancêtre de lui-même), `afficherListe`, `afficherFiche`, `afficherFormulaire`. Lot 2 (par l'écran,
  sans fonction publique nouvelle) : valeur de remplacement, « Saisir un relevé », carte Préventif
  (§14.6). Lot 3 (`parc-etiquettes.js`, §15.6) : `FORMATS_ETIQUETTES`,
  `equipementsPourEtiquettes({ localisationId, criticite, ids })`, `planchesEtiquettes(equipements,
  format, decalage)`, `afficherEtiquettes(conteneur, parametres)` ; carte « Contrôles
  réglementaires » de la fiche (par l'écran).
- **`Demandes`** : constantes `STATUTS`, `IMPACTS`, `MATRICE_PRIORITE` ; règles pures
  `prioriteCalculee(criticite, impact)`, `normaliserImpact`, `typePropose(priorite)`,
  `datePrevue(priorite, aujourdhuiIso)`, `libelleEquipement`, **`codeSymptome(texte)`** (lot 2 :
  code de la famille « symptôme » dont le libellé est exactement ce texte, casse et espaces ignorés,
  sinon `''` ; ex. `'  FUITE '` → `'S01'`, `'Fuite d'eau'` → `''`) ; écritures `creer(valeurs)` (lot 2 :
  `symptome_code`, `ot_origine_id`), `accepter(diId, options)` (lot 2 : recopie `symptome_code` dans
  l'OT), `regrouper(diId, otId)`, `differer(diId, motif)`, `refuser(diId, motif)`.
- **`Ordres`** : constantes `STATUTS`, `TYPES`, `PRIORITES`, `RAPPEL_CONSIGNATION` ; règles pures
  `transitionsPossibles`, `verifierPassage` (→ `{ ok, erreurs, avertissements, piecesManquantes }`),
  `verifierCloture`, `cout`, `verifierHabilitation`, `estOuvert`, `enRetard`, `estVerrouille`,
  `estCorrectif`, `estRienASignaler`, `piecesManquantes(otId)` (lot 2 : `[{ article_id, libelle,
  prevu, sorti, stock, reste }]`, RG3 révisée), `filtrer(ordres, filtres)`, `datePrevueParDefaut` ;
  écritures `creer(valeurs)`, `changerStatut(otId, statutAttendu, cible, complement)` (lot 2 : après
  une clôture technique réussie d'un OT qui a un `gamme_id`, appelle `Preventif.apresCloture` ; un
  échec ne défait pas la clôture, il est signalé par un toast et un message sur la fiche),
  `changerPriorite(otId,
  nouvelle, motif)`, `creerOtLie(otId)` ; affichage et export `libelleEquipement`, `nomTechnicien`,
  `csvListe`, `bonDeTravailHtml(ot)`, `imprimerBon(otId)`. Lot 2, par l'écran : bloc « Pièces
  sorties » (`ordres-pieces.js`), carte préventif, encart des causes fréquentes (§14.6).
- **`Preventif`** (lot 2, §14.3) : constantes `DECLENCHEURS`, `STATUTS_GAMME` ; règles pures
  `dernierReleve(compteurId)`, `etatGamme(gamme, aujourdhui)`, `calendrier(aujourdhui, semaines)` ;
  écritures `genererOTEchus({ aujourdhui })` (→ identifiants des OT créés), `texteGeneration(n)`
  (« Aucune gamme échue », « 1 OT préventif généré », « n OT préventifs générés »),
  `apresCloture(otId)` (→ vrai si la gamme a changé), `verifierGamme(valeurs)` (→ `[{ nom, message
  }]`), `creerGamme(valeurs)`, `modifierGamme(gammeId, valeurs)`, `ajouterOperation(gammeId,
  valeurs)`, `modifierOperation(operationId, valeurs)`, `deplacerOperation(operationId, sens)`,
  `supprimerOperation(operationId)` (D26 : seule suppression de ligne de Prévo, journalisée).
- **`Magasin`** (lot 2, §14.4) : constantes `TYPES_MOUVEMENT`, `STATUTS_ACHAT` (lues dans le
  schéma) ; règles pures `suggestionPointCommande(articleId, aujourdhui)`, `aCommander()`,
  `sortiesDeLOt(otId)` ; écritures `sortir(otId, articleId, quantite, commentaire)`,
  `retourner(otId, articleId, quantite, commentaire)`, `entrer(articleId, quantite, commentaire)`,
  `inventorier([{ articleId, quantite }], commentaire)`, `demanderAchat(articleId, quantite,
  fournisseurId)`, `commander(achatId)`, `recevoir(achatId, quantiteRecue)`, `creerArticle(valeurs)`,
  `modifierArticle(articleId, valeurs)`, `creerFournisseur(valeurs)`,
  `modifierFournisseur(fournisseurId, valeurs)`, `mettreAJourStocks(ids)`.
- **`CausesFrequentes`** (lot 2, §14.5, un seul fichier) : `MINIMUM_PAR_DEFAUT` (5), `MENTION`
  (« Statistique de l'historique, pas un diagnostic »), `calculer(equipementId, symptomeCode,
  { minimum })`, `encart(equipementId, symptomeCode)` ; lot 3 bis (§16.7) : `MENTION_PISTE`,
  `fourchette(k, n)` (Wilson à 95 % → `{ bas, haut }` ou `null`), `texteFourchette(k, n)`.
- **`Accueil`** : `afficher`, `calculerCompteurs()` → `{ diATraiter, otEnRetard, p1Ouverts,
  preventifsSemaine, articlesACommander }` (les quatre premières : listes de lignes de demandes ou
  d'OT ; `articlesACommander` : éléments de `Magasin.aCommander()`), `otEnRetard(ot, aujourdhui)`,
  `p1Ouvert(ot)`, et depuis le lot 2 `dimancheDe(dateIso)` (dimanche de la semaine du lundi au
  dimanche, calculé en UTC) et `preventifDeLaSemaine(ot, dimanche)` (OT d'origine `préventif`,
  ouvert, date prévue ≤ ce dimanche, retards compris). Lot 3 : `calculerCompteurs()` renvoie aussi
  `controlesSous30j` et `habilitationsARenouveler` (§15.9). Lot 3 bis : instrument « Suggestions de
  préventif » du responsable (`Suggestions.ouvertes`, §16.6).
- **`Parametres`** (`parametres.js`, `parametres-codes.js`) : écrans `#/parametres` et `#/controle` ;
  `decrireSauvegarde(nom)` (lot 2 : type « Avant format 2 » pour `…_avant-format-v2`) et
  `numeroLigneFichier(probleme)` (utilitaires testés) ; lot 3 (§15.11) : `FAMILLES_CODES`,
  `codePropose(famille, lignes)`, `verifierCode(valeurs, lignes, idCourant)` (→ `[{ nom, message }]`),
  `ajouterCode({ famille, libelle, code })`, `modifierLibelleCode(id, libelle)`.
- **`Equipe`** (lot 3, §15.8) : constante `STATUTS_HABILITATION` ; règles pures
  `etatHabilitation(habilitation, aujourdhui)`, `habilitationsQuiComptent(technicienId)`,
  `aRenouveler(aujourdhui)` ; écritures `verifierTechnicien(valeurs, lignesTechniciens, idCourant)`
  (→ `[{ nom, message }]`), `creerTechnicien(valeurs)`, `modifierTechnicien(technicienId, valeurs)`,
  `ajouterHabilitation(technicienId, valeurs)`, `modifierHabilitation(habilitationId, valeurs)`,
  `renouvelerHabilitation(habilitationId, { date_obtention, date_echeance })` (→ identifiant créé).
- **`Controles`** (lot 3, §15.7) : constante `STATUTS` ; règles pures `ajouterMois(dateIso, n)`,
  `prochaineDate(controle)`, `etat(controle, aujourdhui)`, `sous30Jours(aujourdhui)` ; écritures
  `verifierControle(valeurs, aujourdhui)`, `creerControle(valeurs)`, `modifierControle(controleId,
  valeurs)`, `ecrireRapport(controleId, date, fichier)` (→ nom du document écrit),
  `enregistrerRealisation(controleId, { date, organisme, rapport, observations })`,
  `leverObservations(controleId, { date, commentaire })`.
- **`Planning`** (lot 3, §15.5) : règles pures `lundiDe(dateIso)`, `joursDeLaSemaine(lundi)`,
  `ordresDeLaSemaine(lundi)`, `chargeSemaine(technicienId, lundi)`, `semaine(lundi)` ; écriture
  `planifier(otId, statutAttendu, technicienId, dateIso)` (→ `{ statut, avertissements }`).
- **`Indicateurs`** (lot 3, §15.3 et §15.4) : constantes `PERIODES`, `COULEURS_SERIES`,
  `COULEUR_AUTRES` ; règles pures `periode(code, aujourdhui, du, au)`, `periodeDuMois('AAAA-MM')`,
  `tempsRequis`, `pannes`, `attentePieces`, `partPreventif`, `respectPreventif`, `otEnRetard`,
  `delaisPriseEnCharge`, `coutParEquipement`, `coutsParMois`, `valeurStock`, `parEquipement`,
  `global`, `paretoPannes`, `paretoArrets`, `heuresParMois`, `mtbfMttrCriticiteA`, `causes`,
  `chargeCapacite` ; graphiques `graphique(conteneur, reglages)` (→ promesse de l'instance ECharts,
  ou `null`), `libererGraphiques(racine)`, `habillerOption(option, support, titre, largeur)` (thème
  `ecran` ou `papier`, réutilisé par le rapport mensuel), `options` (constructeurs des options des
  graphiques de l'écran).
- **`Rapport`** (lot 3, §15.10) : `PREFIXE_FICHIER` (`rapport-mensuel-`) ; règles pures
  `donnees(mois, aujourdhui, maintenant)`, `moisAProposer(aujourdhui)`, `rapportsFiges()` (noms lus
  dans `rapports_mensuels`), `texteCourriel(donnees)` ; `html(mois, options)` (async, texte HTML
  autonome), `figer(mois, options)` (async, → `{ nom, rapport }`) ; écrans `afficherOnglet(conteneur)`
  (onglet de `#/indicateurs`) et `bandeauAccueil()` (élément ou `null`).
- **`Suggestions`** (lot 3 bis, §16.5 et §16.6 ; `suggestions-regles.js`, `suggestions-ecrans.js`) :
  `TITRES`, `REGLAGES` ; règles `calculer(jour?, remplacements?)` (→ `{ ouvertes, decisions,
  reglages }`), `ouvertes(jour)`, `pourEquipement(id, jour)`, `pourGamme(id, jour)`, `trouver(cle,
  jour)` ; décisions au journal `ignorer(cle, motif)`, `marquerTraitee(cle, texte)` ; écrans
  `ONGLETS`, `ongletsPreventif()`, `ongletRefuse(requete)`, `encartEquipement(id)`, `encartGamme(id)`,
  et les relais de `preventif-ecrans.js` : `preparerCreation(requete)`, `apresCreationGamme(id)`,
  `suiviFiche(gammeId, requete)`, `apresModificationGamme(gammeId, champs)`, `apresCheckListe(gammeId)`.
- **`Apropos`** : `CREDIT`, `afficher`.

Lot 4 : objets `Ia` (`ia.js`, `ia-prompts.js`, `ia-encadre.js`), `Dictee` et `Poste` — API aux
§17.3, §17.4, §17.6, §17.7, précisées au §17.11.

## 11. Données de démo

`outils/generer_demo.py` (graine fixe, date de référence fixe `DATE_REFERENCE`) écrit
`donnees/demo/*.csv` (22 fichiers, format §3.1) et `js/demo-donnees.js` :
```js
const DEMO_DONNEES = { dateReference: 'AAAA-MM-JJ', tables: { equipements: '<texte CSV>', … } };
```
`StockageDemo` (et la copie du jeu de démo vers un vrai dossier) décale toutes les dates du
nombre de **semaines entières** écoulées depuis `dateReference`, pour que l'historique se termine
toujours aujourd'hui (les identifiants gardent leur année d'origine).

Depuis le lot 2 (D30), l'historique couvre **13 mois** : `DATE_REFERENCE` = `2026-10-19` (un
lundi), premières lignes en septembre 2025. Depuis le lot 3 bis, le jeu par défaut contient
notamment 31 équipements, 156 DI, 268 OT, 12 gammes, 56 relevés, 52 articles, 302 mouvements de
stock, 36 achats, 6 contrôles réglementaires, 4 techniciens, 10 habilitations et 78 lignes de
journal (historique des statuts des pannes récentes, §15.12, et une décision sur une suggestion,
§16.8), avec les champs du format v2 renseignés (valeur de remplacement de chaque équipement, code
symptôme sur 133 DI, OT préventifs avec anomalie et leur DI liée) et au moins deux équipements qui ont 5 OT
correctifs clôturés d'un même symptôme (encart des causes fréquentes). Le générateur
s'auto-vérifie (clés étrangères, listes de valeurs, règles RG1 à RG6, aucun stock négatif à aucun
moment, colonne `stock` = stock recalculé, scénarios) et s'arrête au moindre défaut ; deux
exécutions donnent des fichiers identiques à l'octet.

Options : `--mois N` (13 par défaut, 24 avec `--volume`), `--sans-js` (pas de
`js/demo-donnees.js`), `--fichier-js CHEMIN`, `--fichier-scenarios CHEMIN`, et
`--volume EQUIPEMENTS,OT --sortie DOSSIER` : jeu de charge (tests de performance CS20 et CS34), qui
produit aussi gammes, relevés, mouvements et achats en proportion.

**Identifiants de scénario** : le jeu par défaut écrit aussi `tests/fixtures/demo-scenarios.json`
(ni avec `--sortie`, ni avec `--volume` ; `--fichier-scenarios` l'écrit ailleurs) : pour chaque rôle
de scénario (OT par statut, P1 ouvert, OT en retard, DI par statut, gamme mensuelle échue, kit
garniture, articles sous le point de commande, techniciens BR valide ou échue, préventif avec
anomalie… ; rôles du lot 3 au §15.12, du lot 3 bis au §16.8), l'identifiant de la ligne qui le joue. Les rôles sont décrits dans la docstring de
`outils/generer_demo.py`. Les tests lisent ce fichier par `commun.scenarios_demo()` au lieu
d'écrire des numéros en dur. `.gitattributes` déclare `js/demo-donnees.js` et `tests/fixtures/*.json`
en `-text` (jamais de conversion de fins de ligne : la démo régénérée reste identique à l'octet).

## 12. Tests

`py -m unittest discover -s tests -v` lance tout. Outils communs dans `tests/commun.py` :
serveur de test (copie du jeu de démo dans un dossier temporaire, `--sans-navigateur`
`--servir-tests`, port libre ; `--servir-tests` rend accessibles les pages de `tests/fixtures/`,
hors liste blanche sinon), serveur statique (pour le dossier simulé), lancement de Chromium
headless, collecte des erreurs console (**toute erreur JavaScript fait échouer le test**), dossier
simulé (OPFS substitué à `showDirectoryPicker`), profil préréglé (`prevo.profil` dans
localStorage), attente de `dataset.etat === 'pret'`, et `scenarios_demo()` (lot 2) : les
identifiants des objets de scénario lus dans `tests/fixtures/demo-scenarios.json` (§11 ; copie
neuve à chaque appel). Les tests ne touchent jamais `donnees/` réel.

Toasts : un toast disparaît au bout de 4 s (7 s pour une erreur). Un test qui doit lire un toast
l'enregistre au moment où il s'affiche, par un `MutationObserver` posé sur la page
(`window.__toasts`), au lieu de lire `#toast` après coup : un test lu trop tard sur un poste chargé
échouait au hasard. Même principe pour les états traversés de `data-etat`.

Fichiers ajoutés au lot 2 (un par sujet) : `test_format_v2.py`, `test_version_schema.py`,
`test_regles_lot2.py`, `test_preventif.py`, `test_magasin.py`, `test_demandes_lot2.py`,
`test_ordres_lot2.py`, `test_parc_lot2.py`, `test_accueil_lot2.py`, `test_recette_lot2.py` (recette du
lot 2 de bout en bout, en modes serveur et démo) ; `test_excel_reel.py` couvre aussi le format v2
et une base du lot 1 passée par Excel ; `test_performance.py` mesure le chargement génération du
préventif comprise, la création de DI et la sortie de pièce sur le jeu de charge ; `test_depot.py`
vérifie le découpage (700 lignes au plus par fichier de `js/modules/`, ordre exact du §15.1 depuis
le lot 3).

Fichiers ajoutés au lot 3 (§15.13) : `test_socle_lot3.py`, `test_regles_indicateurs.py` (dont un
calcul Python indépendant des indicateurs, `CalculPython`, sur les CSV de démo), `test_regles_lot3.py`,
`test_equipe.py`, `test_controles.py`, `test_planning.py`, `test_etiquettes.py`, `test_indicateurs.py`,
`test_rapport.py`, `test_accueil_lot3.py`, `test_recette_lot3.py` (captures d'écran dans
`tests/resultats/recette-lot3/`) ; `test_performance.py` mesure aussi l'écran Indicateurs sur 12 mois,
le planning et le rapport figé. Les tests de glisser-déposer du planning ouvrent une fenêtre haute
(1440 × 1600) : Playwright ne fait pas défiler la page pendant le geste. Les tests du rapport
calculent le mois écoulé depuis la vraie date du jour (l'application la lit aussi) : aucun mois
écrit en dur.

Fichiers ajoutés au lot 3 bis (§16.9) : `test_regles_suggestions.py` (dont `calcul_python`, calcul
indépendant des règles du §16.3 sur des CSV, réutilisé par `test_accueil_lot3bis.py`),
`test_causes_frequentes.py`, `test_suggestions.py`, `test_accueil_lot3bis.py`, `test_recette_lot3bis.py`
(captures dans `tests/resultats/recette-lot3bis/`) ; `test_performance.py` mesure aussi l'onglet
Suggestions. En mode serveur, `test_suggestions.py` et `test_recette_lot3bis.py` fixent l'horloge du
navigateur à la date de référence de la démo, 10 h (`clock.set_fixed_time` de Playwright ; les
minuteurs tournent) : `ServeurPrevo` copie la démo brute, non décalée, et les rôles du §16.8 ne
valent qu'à cette date ; le mode démo tourne, lui, à la date réelle.

Fichiers ajoutés au lot 4 (§17.10, aligné au §17.11) : `test_serveur_ia.py`, `test_https.py`,
`test_ia_regles.py`, `test_ia_fonctions.py`, `test_ia_fonctions_2.py`, `test_dictee.py`, `test_poste.py`,
`test_guide.py`, `test_fiche_csv.py`, `test_recette_lot4.py` (captures dans `tests/resultats/recette-lot4/`),
`test_ia_reel.py` ; faux fournisseur d'IA `tests/faux_fournisseur_ia.py` (jamais un vrai modèle dans la
suite) ; `test_performance.py` vérifie aussi qu'aucun appel réseau ne part à l'ouverture sans IA.
L'essai réel de l'IA (`tests/test_ia_reel.py` : vrai Ollama, `qwen2.5:7b`) ne s'exécute que si
`PREVO_TEST_IA=1`, comme le vrai Excel.

Fichiers ajoutés au lot 5 (§18.10) : `test_import_socle.py`, `test_fixtures_import.py`,
`test_import_lecture.py`, `test_import_regles.py` (dont un calcul Python indépendant de l'aperçu sur les
fichiers d'essai de `tests/fixtures/import/`, écrits par `outils/generer_fixtures_import.py`),
`test_import_historique.py`, `test_import_ecritures.py`, `test_import_ia.py`, `test_import_modeles.py`,
`test_import_ecrans.py`, `test_recette_lot5.py` (T86) ; `test_bento.py` pour l'accueil du responsable (§19) ;
`test_regles_indicateurs.py` suit l'ajustement 3 de D92 (disponibilité sur les seules pannes avec durée
d'arrêt) ; `test_fiche_csv.py` couvre aussi les colonnes reconnues à l'import ; `test_performance.py`
(T86) mesure l'aperçu et l'écriture d'un fichier de 5 000 lignes et vérifie que SheetJS n'est pas chargé au
démarrage ; `test_excel_reel.py` (T86) lit aussi la liste du parc enregistrée en .xls par le vrai Excel.

Playwright et Chromium ne sont nécessaires que pour les tests, jamais pour utiliser Prévo.
Le test d'aller-retour par le **vrai Excel** (`tests/test_excel_reel.py`, `tests/test_csv.py`) ne
s'exécute que si la variable d'environnement `PREVO_TEST_EXCEL=1` est définie ; sinon il est
sauté, avec un message explicite. Sur le poste de développement, Chromium rencontre au hasard
`net::ERR_NO_BUFFER_SPACE` (épuisement des tampons TCP de Windows, reproduit hors de Prévo avec
un serveur Python minimal) : un test dont la console montre cette erreur précise est **rejoué une
seule fois**, en le signalant sur la sortie d'erreur ; toute autre erreur, ou une seconde panne,
fait échouer le test (`CasNavigateur.run` dans `tests/commun.py`). Les connexions persistantes du
serveur (§7) en réduisent la fréquence sans l'annuler.

## 13. Points d'extension (lots suivants)

Les lots 2 à 7 sont réalisés (contrats aux §14 à §22 ; version 1.0.0 au lot 4, 1.1.0 au lot 5, 1.2.0 au
lot 6, 2.0.0 au lot 7). Un module ajouté plus tard suit les mêmes règles : préfixe de fichiers, 700 lignes au plus par
fichier, place dans l'ordre du §15.1 complété aux §16.1, §17.1 et §18.1 **et** dans `ORDRE_MODULES` de
`tests/test_depot.py`. Une table rendue importable demande une entrée dans `Import.TYPES` (et la règle de
sa clé naturelle), sa place dans `Import.ORDRE_ECRITURE`, puis `py outils/generer_fiche_csv.py`.
Restent :
- Points ouverts du lot 5 (§18.11), dont les contrôles des formulaires à appliquer ou non à l'import.
- Piste notée par Nicolas : stocker le prix unitaire dans `mouvements_stock` au moment de la sortie
  pour figer le coût des OT passés (changement de format, lève la limite de D24 ; à décider).
- Nouveau format : suivre la liste de contrôle de [FORMAT.md](FORMAT.md) §11 (champs en fin de table avec
  `depuisVersion: N`, `Schema.version` à N, étape dans `Formats.ETAPES` et son miroir `ETAPES_FORMAT` de
  `serveur.py`, `avant-format-vN` dans les listes fermées `MOTIFS_SAUVEGARDE` de `serveur.py` et de
  `js/stockage-dossier.js`). La sauvegarde puis le passage sont faits par le serveur à son démarrage (mode
  serveur) ou par `Donnees.migrerAuFormatCourant` à l'ouverture (mode dossier) : §5.6.

## 14. Contrat du lot 2 (CDC validé le 2026-10-20 : D19–D32)

Ce contrat a été écrit avant le code du lot 2, puis **relu et corrigé après coup** pour décrire le
code réel. Là où le code s'écarte du texte d'origine, une mention « écart retenu : … » dit ce qui
a été fait et pourquoi.

### 14.1 Format CSV v2
- `Schema.version` = 2 ; `parametres.version_schema` = `2`. Quatre champs ajoutés **en fin de
  table** (après les champs du brief §6), avec l'attribut `depuisVersion: 2` :

  | Table | Champ | Type | Libellé |
  | --- | --- | --- | --- |
  | `equipements` | `valeur_remplacement` | `decimal` | Valeur de remplacement (€ HT) |
  | `demandes` | `symptome_code` | `ref` → `codes_defaillance.code`, filtre `famille: 'symptôme'` | Code symptôme |
  | `demandes` | `ot_origine_id` | `ref` → `ordres_travail` | OT d'origine (préventif) |
  | `ordres_travail` | `anomalie_constatee` | `booleen`, défaut `0` | Anomalie constatée |

- Lecture d'un fichier sans une colonne `depuisVersion: 2` : problème de gravité **`info`**
  (« colonne ajoutée par la version 2 du format, écrite au prochain enregistrement »), jamais
  `attention` ; la valeur par défaut est appliquée. Les colonnes du brief manquantes restent en
  `attention` (§3.3).
- Nouvelles clés de `parametres.csv` : `priorite_preventif` (`P3`), `horizon_calendrier_semaines`
  (`12`).
- `tests/test_schema.py` vérifie : champs du brief §6 = début exact de chaque table, puis exactement
  les champs de ce tableau.
- Ajout (décision de Nicolas, tâche T37) : le passage de `version_schema` de 1 à 2 se fait au
  démarrage par `Donnees.mettreAJourVersionSchema()`, **juste après** une sauvegarde automatique
  `AAAA-MM-JJ_HHMMSS_avant-format-v2` ; sans sauvegarde confirmée, pas de passage (nouvel essai à
  la prochaine ouverture). Détail au §5.6 ; motif de sauvegarde au §6 et au §7.
  Mis à jour par le chantier « socle de données » (D168) : le passage n'est plus fait par le navigateur pour tous.
  En mode serveur, c'est le **serveur, à son démarrage**, avant toute connexion ; en mode dossier, c'est
  `Donnees.migrerAuFormatCourant()` (ancien nom `mettreAJourVersionSchema`, même fonction), à l'ouverture. Dans
  les deux cas, sauvegarde `avant-format-vN` d'abord ; voir §5.6 et [FORMAT.md](FORMAT.md) §6.

### 14.2 Découpage des modules (D28) et ordre de chargement
Un module = un préfixe de fichiers, chacun ≤ 700 lignes (dérogation assumée au « un fichier JS par
module » du brief §2). Règles :
- le **premier** fichier d'un module crée l'objet (`const Ordres = (() => { … return { … }; })();`),
  les suivants le complètent (`Object.assign(Ordres, (() => { … return { … }; })());`) ;
- une fonction dont un autre fichier du **même** module a besoin est rangée dans `Objet.interne`
  (ex. `Ordres.interne.afficherPreparation`), que les fichiers suivants complètent par
  `Object.assign(Objet.interne, …)` ; ce n'est **pas une API** : ni les autres modules ni les
  tests ne s'en servent, et son contenu peut changer ;
- un fichier qui appelle une fonction d'un fichier **chargé plus tard** passe par une petite
  fonction relais qui la cherche au moment de l'appel, pas au chargement
  (`const afficherPreparation = (panneau, ot) => Ordres.interne.afficherPreparation(panneau, ot);`
  dans `ordres-fiche.js`) ;
- un seul écouteur `DOMContentLoaded` par module, qui enregistre tous ses écrans (§8).

Ordre exact dans `index.html` (après `js/interface.js`), recopié dans `ORDRE_MODULES` de
`tests/test_depot.py` (le contrat et ce test changent ensemble) :
```
apropos.js  mise-a-jour.js  accueil.js  causes-frequentes.js
parc-regles.js  parc-arbre.js  parc-formulaires.js  parc-fiche.js
demandes-regles.js  demandes-ecritures.js  demandes-signaler.js  demandes-liste.js  demandes-fiche.js
ordres-regles.js  ordres-ecritures.js  ordres-liste.js  ordres-fiche.js  ordres-onglets.js  ordres-pieces.js  ordres-impression.js
preventif-regles.js  preventif-ecritures.js  preventif-ecrans.js  preventif-calendrier.js
magasin-regles.js  magasin-ecritures.js  magasin-articles.js  magasin-mouvements.js  magasin-achats.js
parametres.js  (puis js/app.js)
```
Écart retenu : `ordres-pieces.js` (bloc « Pièces sorties » de l'onglet Exécution) a été ajouté
après `ordres-onglets.js` par la tâche des OT du lot 2 (prévu par son énoncé ; dans
`ordres-onglets.js`, qui compte déjà plus de 500 lignes, le bloc aurait dépassé 700 lignes) ;
le module Ordres compte donc sept fichiers. Écart retenu : l'écouteur `DOMContentLoaded` du
préventif est dans `preventif-ecrans.js` (3/4) et non dans le dernier fichier, `preventif-calendrier.js`
n'ayant pas d'écran propre (il dessine un onglet).

Feuilles `css/modules/` ajoutées : `preventif.css`, `magasin.css`. Les routes sont enregistrées
dans l'ordre de chargement et la première qui correspond gagne : les routes « fiche »
(`#/equipement/<id>`, `#/di/<id>`, `#/ot/<id>`, `#/preventif/gamme/<id>`, `#/magasin/article/<id>`)
excluent explicitement `nouveau`/`nouvelle` (`(?!nouveau$)` …). Icônes ajoutées à `UI.icone` :
`magasin` (carton), `preventif` (calendrier coché).

### 14.3 Préventif (M4, RG5) — objet `Preventif`
Fonctions **pures** (`preventif-regles.js`) :
- `Preventif.dernierReleve(compteurId)` → `{ valeur, date }` ou `null` (relevés triés par date puis
  identifiant).
- `Preventif.etatGamme(gamme, aujourdhui)` → `{ statut, echeance, declenchement, raison, otOuvertId,
  releveActuel, reste }`, `statut` ∈ `inactive` (actif = 0), `ot_ouvert` (un OT de cette gamme
  n'est ni clôturé ni annulé), `echue`, `bientot` (déclenchement dans les 14 jours), `a_jour`,
  `incomplete` (paramètres manquants).
  - `date` : `echeance` = `prochaine_echeance`, sinon `derniere_realisation` + `periodicite_jours`,
    sinon aujourd'hui (jamais réalisée → à faire) ; `declenchement` = `echeance` − `avance_jours` ;
    échue si aujourd'hui ≥ `declenchement`.
  - `compteur` : base = `releve_derniere_realisation` (0 si vide) ; échue si dernier relevé − base ≥
    `periodicite_unites` ; `echeance` estimée (pour le calendrier) avec `heures_fonct_jour` de
    l'équipement quand l'unité du compteur est l'heure, sinon vide.
  - `seuil` : échue si dernier relevé ≥ `seuil` **et** ce relevé est postérieur à
    `derniere_realisation` (sinon une gamme juste réalisée se redéclencherait aussitôt).
  - Écart retenu (choix de règles non écrits au contrat, testés) : une gamme `date` sans
    `periodicite_jours` (ou ≤ 0), une gamme `compteur` sans `periodicite_unites`, une gamme
    `compteur` ou `seuil` sans compteur, avec un compteur introuvable ou **sans aucun relevé**, une
    gamme `seuil` sans seuil → `incomplete` (la `raison` dit ce qui manque). Une gamme `compteur`
    n'utilise **pas** `avance_jours` (`declenchement` = `echeance` estimée : c'est le compteur qui
    déclenche) ; elle est `bientot` si son échéance estimée tombe dans les 14 jours. Une gamme
    `seuil` n'a pas d'échéance datée, n'est jamais `bientot`, et le relevé doit être
    **strictement** postérieur à la dernière réalisation : un relevé daté du jour même de
    l'intervention ne la redéclenche pas. `reste` vaut : jours avant l'échéance (`date`), unités
    avant l'échéance (`compteur`), écart au seuil (`seuil`) ; négatif ou nul quand c'est dépassé.
    Les dates sont calculées en UTC (un changement d'heure ne décale jamais un jour).
- `Preventif.calendrier(aujourdhui, semaines)` → `[{ lundi, dimanche, elements: [{ gammeId,
  equipementId, date, estimee, otId }] }]` (échéances des gammes actives sans OT ouvert, estimées
  pour un compteur, et OT préventifs ouverts à leur date prévue). Écart retenu : sans `semaines`,
  le nombre de semaines est le paramètre `horizon_calendrier_semaines`, sinon 12 ; un élément en
  retard (avant le premier lundi) est placé dans la première semaine avec sa vraie date ; un
  élément au-delà du dernier dimanche n'est pas placé.

Écritures (`preventif-ecritures.js`) :
- `await Preventif.genererOTEchus({ aujourdhui })` → identifiants des OT créés. Une seule
  `Donnees.modifier('ordres_travail', …)` qui, **sur les lignes fraîches**, recalcule pour chaque
  gamme active si elle est échue et sans OT ouvert, et crée l'OT : origine `préventif`,
  `gamme_id`, équipement, type `préventif systématique` (date, compteur) ou `préventif
  conditionnel` (seuil), priorité `parametre('priorite_preventif', 'P3')`, statut `Créé`, titre =
  libellé de la gamme, `consignes` et `temps_prevu_h` de la gamme, date prévue = échéance si elle
  est future, sinon aujourd'hui. Puis `modifier('ot_operations', …)` copie les opérations de la gamme
  (`ordre`, `operation`, `valeur_attendue`, `fait` = 0) pour chaque OT créé **qui n'en a pas encore**
  (idempotent). Deux postes qui génèrent en même temps ne créent qu'un OT par gamme. Rien d'échu :
  aucune écriture (cas le plus courant à l'ouverture). L'OT reçoit aussi un `travail_a_faire`
  (« Réaliser les n opérations de la check-list de la gamme GAM-… Déclenchement : … »).
  Écart retenu : la copie de check-list complète aussi un OT préventif **encore « Créé »** d'une
  gamme resté sans aucune opération (copie interrompue lors d'une génération précédente) ; sans
  risque, les conditions étant vérifiées sur les lignes fraîches.
  `Preventif.texteGeneration(n)` donne le message (« Aucune gamme échue », « 1 OT préventif
  généré », « n OT préventifs générés »).
- `await Preventif.apresCloture(otId)` (appelé par `Ordres.changerStatut` après la **clôture
  technique** d'un OT qui a un `gamme_id`) : relit `ordres_travail` ; refuse
  (`ErreurValidation`) un OT qui n'est pas clôturé ; date de réalisation = `date_fin` de l'OT
  (sinon sa date de clôture). `derniere_realisation` = cette date ; `prochaine_echeance` recalculée
  (date : + `periodicite_jours` ; compteur : estimée pour un compteur en heures, sinon vide ;
  seuil : vide). Idempotent ; renvoie vrai si la gamme a changé. Un échec ne défait pas la clôture
  (toast et message d'avertissement sur la fiche OT).
  - Écart retenu (correction de relecture, D22) : la décision se prend sur les OT clôturés
    (techniquement ou administrativement) **de la gamme**. Si l'OT clôturé est celui dont la date
    de réalisation est la plus récente, sa date fait foi, **même si la gamme portait une date plus
    récente** (date de fin saisie par erreur, corrigée après réouverture puis nouvelle clôture :
    sans cette règle, la gamme restait bloquée sur la date erronée et ne générait plus rien). Un OT
    plus ancien clôturé après coup ne change rien à la gamme.
  - Écart retenu : `releve_derniere_realisation` = le relevé du compteur **à la date de
    réalisation** (le dernier relevé daté au plus tard ce jour-là, à défaut le dernier relevé), et
    non le dernier relevé tout court : un relevé saisi après l'intervention ne fausse pas la base,
    et l'appel reste idempotent.
- CRUD des gammes (`modifier('gammes')`) et de leur check-list (`gamme_operations`, ajout,
  modification, ordre, **suppression autorisée et journalisée** — D26, seule exception) :
  `verifierGamme`, `creerGamme`, `modifierGamme`, `ajouterOperation`, `modifierOperation`,
  `deplacerOperation` (renumérote 1, 2, 3…), `supprimerOperation` (renumérote les suivantes ;
  journal « suppression (D26) de l'opération « … » de la check-list de la gamme GAM-… ») ; les OT
  déjà créés gardent leur copie dans `ot_operations`.
- Écrans (`preventif-ecrans.js`, `preventif-calendrier.js`) : `#/preventif` (liste des gammes avec
  statut, filtres statut et équipement, onglet « Calendrier 12 semaines », boutons « Nouvelle
  gamme » et « Générer les OT échus » pour le responsable), `#/preventif/gamme/nouvelle`,
  `#/preventif/gamme/<id>` (fiche, éditeur, OT de la gamme). Menu « Préventif » (ordre 35, icône
  `preventif`, technicien en lecture, responsable).
- `App` appelle `Preventif.genererOTEchus()` une fois après le chargement pour un technicien ou un
  responsable (toast « n OT préventifs générés » si n > 0 ; erreur → `App.signalerErreur`).
  Écart retenu : cette génération a lieu **avant** le premier écran et l'état « prêt » (marque
  `prevo:preventif`, puis `prevo:pret`), pour que l'accueil montre déjà les OT du jour et qu'aucune
  écriture ne coure pendant la première action de l'utilisateur ; et **elle n'a pas lieu** si le
  passage au format 2 a échoué faute de sauvegarde (§5.6, choix prudent de l'orchestrateur ; le
  bouton reste disponible). La génération est aussi lancée juste après un relevé de compteur saisi
  depuis la fiche équipement (§14.6).

### 14.4 Magasin (M5, RG6) — objet `Magasin`
Fonctions pures (`magasin-regles.js`) :
- Stock = `Donnees.stockArticle(id)` (déjà en place).
- `Magasin.suggestionPointCommande(articleId, aujourdhui)` → nombre ou `null` : (sorties − retours
  des 365 derniers jours) / 365 × `delai_jours` + `stock_securite`, arrondi à l'unité supérieure ;
  `null` s'il n'y a aucune sortie (D23 : le point de commande reste **saisi**, ceci n'est qu'une
  suggestion).
- `Magasin.aCommander()` → articles actifs dont `point_commande` est renseigné et stock ≤
  `point_commande`, avec quantité proposée = `qte_commande` si renseignée, sinon
  `point_commande` − stock + `stock_securite` (au moins 1). Forme réelle : `[{ article (ligne),
  stock, pointCommande, quantiteProposee }]`, articles critiques d'abord, puis par référence.
- `Magasin.sortiesDeLOt(otId)` → `[{ articleId, sorti, retourne, net }]` (dans l'ordre de la
  première sortie).
- Catégorie d'un article (affichage et filtre `?categorie=`) : **déduite du préfixe de sa
  référence** (`ROU-001` → ROU, « Roulements » ; préfixes connus ROU, TRA, ETA, FIL, LUB, ELE, HYD,
  PNE, OUT, DIV ; autre préfixe affiché tel quel ; sans préfixe : « Sans catégorie ») — aucun champ
  n'est ajouté au schéma.
Écritures (`magasin-ecritures.js`), toutes par `Donnees.modifier` avec contrôle **sur les lignes
fraîches**, puis réécriture de `articles.stock` pour les articles touchés
(`Magasin.mettreAJourStocks(ids)` : `modifier('articles')`, idempotent). Écart retenu (correction
de relecture) : `mettreAJourStocks` **relit `mouvements_stock` dans la fonction de mutation** (à
chaque essai) au lieu de calculer sur le cache, sinon la colonne `stock` pouvait être fausse après
un conflit. Un échec de cette copie n'annule pas le mouvement (avertissement en console ; le
prochain mouvement de l'article la corrige) :
- `Magasin.sortir(otId, articleId, quantite, commentaire)` : OT obligatoire, existant, ni clôturé ni
  annulé ; quantité > 0 ; **refus si le stock deviendrait négatif** (`ErreurValidation` « Stock
  insuffisant : X en stock, Y demandé ») ; mouvement `sortie`, `ot_id`. `utilisateur` du mouvement
  = nom du technicien du profil, ou « Responsable » pour le responsable.
- `Magasin.retourner(otId, articleId, quantite, commentaire)` : OT ouvert ; pas plus que le net
  sorti pour cet OT.
- `Magasin.entrer(articleId, quantite, commentaire)` ; `Magasin.inventorier([{ articleId, quantite }],
  commentaire)` (mouvements `inventaire`, valeur absolue ; un article compté deux fois → refus).
- Achats : `Magasin.demanderAchat(articleId, quantite, fournisseurId)` (statut `demandée`, prix =
  prix de l'article, date du jour), `Magasin.commander(achatId)` (depuis `demandée` seulement),
  `Magasin.recevoir(achatId, quantiteRecue)` (statut `reçue`, `date_reception`, puis entrée en stock
  « Réception ACH-… ») ; une réception ne change **pas** `prix_unitaire` (D24). Écart retenu
  (précisions) : **une seule demande « demandée » par article** (une seconde est refusée tant que la
  première n'est pas commandée) ; la réception se fait **depuis « commandée »** seulement ; une
  réception partielle passe quand même l'achat à « reçue » et l'écart est noté dans le commentaire
  du mouvement (« Réception ACH-0036 (3 reçu sur 5 commandé) ») ; une réception interrompue entre
  ses deux écritures est complétée au nouvel essai, jamais doublée. Articles et fournisseurs :
  `creerArticle`, `modifierArticle` (référence unique parmi les articles actifs, nombres ≥ 0, délai
  entier, fournisseur existant), `creerFournisseur`, `modifierFournisseur` ; jamais de suppression
  (`actif` = 0).
- Écrans : `#/magasin?onglet=articles|mouvements|inventaire|a-commander|achats|fournisseurs`,
  `#/magasin/article/nouveau`, `#/magasin/article/<id>` (fiche : stock, mouvements, équipements
  liés, OT consommateurs, point de commande saisi + suggestion avec « Reprendre la suggestion »).
  Menu « Magasin » (ordre 45, icône `magasin`) : technicien en consultation (ses sorties et retours
  passent par l'OT ; pas d'onglet Inventaire), responsable : tout.

### 14.5 Causes fréquentes (D25) — objet `CausesFrequentes` (`causes-frequentes.js`)
- `CausesFrequentes.calculer(equipementId, symptomeCode, { minimum = 5 })` → `{ suffisant, portee
  ('equipement' | 'modele' | null), libellePortee, total, causes: [{ code, libelle, nombre, remede:
  { code, libelle, nombre }, dernierCas, ots }] }` (3 causes au plus, par nombre décroissant puis
  date du dernier cas). Base : OT de type `correctif …`, statut `Clôturé techniquement` ou
  `Clôturé administrativement`, même `symptome_code`, `cause_code` renseigné. Portée : cet
  équipement ; si moins de `minimum` cas et que marque et modèle sont renseignés, tous les
  équipements de même marque et modèle (casse ignorée) ; sinon `suffisant: false`.
- `CausesFrequentes.encart(equipementId, symptomeCode)` → élément DOM (`.encadre`) : « Causes
  fréquentes ici — n cas » puis une ligne par cause (« garniture usée — 7 cas sur 12 · remède le
  plus utilisé : remplacement pièce · dernier cas : 30/09/2026 · voir les OT ») et la mention
  « Statistique de l'historique, pas un diagnostic » ; en dessous du minimum : « Pas encore assez
  de cas pour ce symptôme (n sur 5) ». Rien si pas de code symptôme. Visible de tous les profils.
- Écart retenu (précisions et corrections de relecture) : sous le minimum, l'encart ne montre
  **que** le message d'attente, aucune cause ; sans code symptôme, `encart` renvoie `null`. Date
  d'un cas = `date_fin`, sinon date de clôture technique, sinon date de création. « voir les OT » :
  **5 liens au plus par cause** (les cas les plus récents), puis « et n autres » — un lien vers la
  liste des OT clôturés de l'équipement (`#/ot?equipement=…&etat=clotures`) quand la portée est
  l'équipement, du texte simple pour la portée « même marque et modèle » (aucune liste ne filtre
  ces OT ensemble). Pour le **demandeur**, qui n'a pas accès aux écrans des OT, les identifiants
  d'OT sont en **texte simple** (un lien le renverrait à l'accueil). Marque et modèle sont comparés
  sans casse ni espaces (« CR 10 » = « cr10 »). Égalité de remède : le plus récent l'emporte.

### 14.6 Demandes, OT, Parc, Accueil (lot 2)
- **DI** : choisir une suggestion de symptôme renseigne `symptome_code` (le texte reste libre) ; à
  l'acceptation, `symptome_code` est recopié dans l'OT ; la fiche DI montre l'encart et, si
  `ot_origine_id`, le lien vers l'OT préventif. `#/di/nouvelle?equipement=…&ot=OT-…` crée une DI liée
  (`ot_origine_id`) ; après création, l'OT d'origine passe `anomalie_constatee` = 1.
  - Précisions du code : le code suit le texte (`Demandes.codeSymptome` : libellé exact, casse et
    espaces ignorés ; un texte modifié à la main perd le code) ; un code inconnu est refusé. Sur un
    OT déjà existant pour la DI (essai précédent interrompu), le code n'est recopié que si celui de
    l'OT est vide. `?ot=` doit désigner un OT **préventif** (origine `préventif` ou type
    `préventif …`) : sinon un avertissement s'affiche et la DI est créée sans lien. Le marquage de
    l'OT est une seconde écriture, idempotente ; s'il échoue, la DI reste créée et un toast le dit.
  - Écart retenu (correction de relecture, RG3) : un OT d'origine **verrouillé** (Clôturé
    administrativement, Annulé) n'est **jamais modifié** : la DI garde le lien, mais l'OT n'est pas
    marqué ; le formulaire et l'écran de confirmation le disent. Le verrou est contrôlé sur la
    ligne fraîche.
- **OT** : onglet Exécution, bloc « Pièces sorties » (`Magasin.sortiesDeLOt`, boutons Sortir /
  Retourner, refus RG6 affiché) ; OT préventif : case « Anomalie constatée » et bouton « Signaler une
  anomalie (DI liée) » ; encart des causes fréquentes dans Préparation et Compte rendu ; à la clôture
  technique d'un OT avec `gamme_id` : `Preventif.apresCloture`.
  - Précisions du code : le bloc « Pièces sorties » est dans `ordres-pieces.js` ; « Sortir une
    pièce » propose d'abord les pièces prévues de l'OT, puis les articles actifs avec leur stock ;
    le coût RG7 compte ces mouvements. La carte préventif de la fiche montre aussi les **DI liées**
    (`demandes.ot_origine_id`) ; sur un OT verrouillé, la case est désactivée et le bouton absent.
    La case n'est acceptée que sur un OT d'origine `préventif`. Badge « anomalie constatée » sur la
    fiche et dans la liste. Le refus RG3 de « Planifié » tient compte des pièces déjà sorties
    (RG3 révisée, §10).
- **Parc** : `valeur_remplacement` (affichée, modifiable), « Saisir un relevé » par compteur
  (`releves`, avertissement si la valeur baisse), gammes de l'équipement avec leur état.
  - Précisions du code : la valeur de remplacement est visible des trois profils et modifiable par
    le responsable ; « Saisir un relevé » est proposé au technicien et au responsable ; une valeur
    plus basse que le dernier relevé demande une **confirmation** (case à cocher), contrôlée aussi
    sur les relevés frais (un relevé saisi entre-temps sur un autre poste est vu). Après
    l'enregistrement d'un relevé, `Preventif.genererOTEchus()` est lancé aussitôt (une gamme
    compteur ou seuil peut être devenue échue) et le toast dit les OT créés.
  - Écart retenu (correction de relecture, sécurité maintenance) : à une **remise à zéro
    confirmée** (compteur remplacé ou remis à zéro : baisse confirmée qui devient le dernier
    relevé), chaque gamme active `compteur` de ce compteur **garde son avancement** : nouvelle base
    `releve_derniere_realisation` = nouvelle valeur − (dernier relevé avant la baisse − ancienne
    base, vide = 0). Sans cela, la gamme aurait calculé un usage négatif et sauté un entretien
    pendant des années. Une entrée de journal par gamme ajustée (« remise à zéro du compteur CPT-… :
    base de GAM-… ajustée de A à B »). Les gammes `seuil` ne changent pas (leur seuil porte sur la
    valeur absolue).
  - Écart retenu (D27) : la carte « Préventif » de la fiche équipement est **masquée au
    demandeur**, qui ne voit pas le préventif.
- **Accueil** : « Préventifs de la semaine » = OT d'origine `préventif`, ouverts, date prévue ≤
  dimanche de la semaine en cours (retards compris) ; « Articles à commander » =
  `Magasin.aCommander().length` ; la carte « Connecter un téléphone » n'est pas affichée si
  `UI.estTelephone()`. Menu latéral : « GMAO » puis le nom de l'entreprise sur deux lignes au plus
  (nom complet en infobulle).
  - Précisions du code : `Accueil.calculerCompteurs()` renvoie les **listes** (`preventifsSemaine`,
    `articlesACommander`) et l'écran en affiche la longueur ; les indicateurs mènent à
    `#/preventif?onglet=calendrier` et `#/magasin?onglet=a-commander`. Le technicien voit d'abord
    ses préventifs de la semaine, puis ses autres OT. Règles exposées : `Accueil.dimancheDe`,
    `Accueil.preventifDeLaSemaine` (§10).

### 14.7 Serveur : liste blanche (D29)
Sont servis : `/` (→ `index.html`), `index.html`, `favicon.svg`, `GUIDE.html` s'il existe,
`css/**`, `js/**`, `acces/**` (lot 7, la porte d'entrée, §22.6 ; et `/acces/ca.crt`, le certificat public de
l'autorité locale, qui n'est pas un fichier du dépôt) ; **tout le reste répond 404** (dont `docs/brief-gmao.md`,
`README.md`, `docs/`, `tests/`, `outils/`, `reference-design/`, `serveur.py`). L'option `--servir-tests` (passée par
`tests/commun.py`) sert en plus `tests/fixtures/**`. Les autres règles (§7) sont inchangées.
Précisions du code : la liste blanche est contrôlée **deux fois**, sur le chemin demandé puis sur
le chemin résolu (lien ou jonction Windows rangé dans `js/`) ; la comparaison ignore la casse ;
une réponse hors liste est la même qu'un fichier absent (404, sans dire que le fichier existe).
Les refus du lot 1 passent avant : segments cachés et traversées → 400, `donnees/` → 403.

### 14.8 Démo 13 mois et identifiants de scénario (D30)
`outils/generer_demo.py` : `--mois 13` par défaut ; nouveaux champs renseignés ; au moins deux
équipements avec ≥ 5 OT correctifs clôturés d'un même symptôme (PO-02 : fuites) ; un OT préventif
avec anomalie et sa DI liée ; gammes, mouvements et achats sur 13 mois ; le jeu de charge
(`--volume`) produit aussi gammes, relevés et mouvements en proportion. Le générateur écrit
`tests/fixtures/demo-scenarios.json` (identifiants des objets de scénario : OT par statut, P1
ouvert, OT en retard, DI par statut, gamme mensuelle échue, kit garniture, articles sous le point de
commande, techniciens BR valide/échue, équipement BR, préventif avec anomalie…) ; les tests lisent
ce fichier (`commun.scenarios_demo()`) au lieu de numéros figés.
Précisions du code : date de référence `2026-10-19` (historique de septembre 2025 au 19/10/2026) ;
le fichier de scénarios n'est écrit que pour le jeu par défaut (option `--fichier-scenarios
CHEMIN` pour l'écrire ailleurs) ; avec `--volume`, l'historique est de 24 mois par défaut, et le
jeu contient aussi des achats ; il crée déjà l'OT de chaque gamme échue à sa date de référence (le
test de performance « vieillit » donc 20 gammes pour mesurer une vraie génération). Chiffres et
options au §11.

## 15. Contrat du lot 3 (CDC validé le 2026-10-20 : D33–D49)

Ce contrat a été écrit avant le code du lot 3, puis **relu et aligné sur le code** à la fin du lot :
là où le code s'écarte du texte d'origine, une mention « écart retenu : … » dit ce qui a été fait et
pourquoi (comme au §14). Les définitions métier du CDC sont recopiées ici : ce contrat se suffit.
Écart retenu (constaté en T41) : `js/lib/echarts.min.js`, inchangé depuis le lot 1, est la version
**5.5.1** d'ECharts (le CDC disait 5.6.0, qui est la version de zrender, le moteur de dessin qu'elle
embarque) ; elle contient `renderToSVGString`, seule fonction du rendu « serveur » utilisée.

### 15.1 Socle
- **Format CSV inchangé** : `Schema.version` reste 2, aucun champ ajouté. Nouvelles clés de
  `parametres.csv` (lues par `Donnees.parametre(cle, defaut)`, absentes → défaut) :
  `seuil_remplacement_pct` (`50`), `adresse_qr` (`''` : première adresse réseau détectée),
  `rapports_mensuels` (`''` : noms des rapports figés, séparés par des virgules, du plus ancien au
  plus récent).
- **Documents** : l'extension `html` s'ajoute aux types acceptés (`TYPES_DOCUMENTS` de `serveur.py`,
  `text/html; charset=utf-8` ; `EXTENSIONS_DOCUMENTS` de `js/stockage-dossier.js`). Comme tout
  document, il est servi avec `Content-Security-Policy: sandbox` (aucun script ne s'y exécute).
  Écart retenu (correction de relecture) : hors serveur, l'URL d'un document `.html` (modes dossier et
  démo, `urlDocument`) est celle d'une page enveloppe qui l'affiche dans un `iframe sandbox` sans
  `allow-scripts` (`Donnees.documentAffichable(nom, blob)`) : là non plus, aucun script ne s'exécute.
- **ECharts à la demande** : `App.chargerEcharts()` → promesse de l'objet `echarts` ; injecte
  `js/lib/echarts.min.js` une seule fois par une balise `<script>` (même mécanisme que
  `App.chargerScriptDemo`, compatible `file://`) ; échec → promesse rejetée avec un message clair, et
  nouvel essai possible. `index.html` ne référence **pas** ECharts : `typeof echarts === 'undefined'`
  à l'état « prêt ».
- `App.adressesReseau()` → copie de la liste des adresses réseau (mode serveur, sinon `[]`).
  `App.urlFicheEquipement(id)` prend `adresse_qr` quand elle est renseignée (base `http(s)://…/`),
  sinon la première adresse détectée (comportement du lot 1).
- Icônes ajoutées à `UI.icone` (trait, même style) : `planning`, `controles`, `indicateurs`, `equipe`.
- Menu : « Planning » (ordre 33, icône `planning`), « Contrôles » (ordre 37, `controles`),
  « Indicateurs » (ordre 50, `indicateurs`), « Équipe » (ordre 85, `equipe`, groupe
  « Administration », avant Paramètres).
- **Ordre de chargement** (remplace celui du §14.2 ; `ORDRE_MODULES` de `tests/test_depot.py` change
  avec lui ; T329 : `brouillons.js` juste après `poste.js`, voir « Brouillons gardés sur l'appareil ») :
  ```
  apropos.js  mise-a-jour.js  accueil.js  causes-frequentes.js
  parc-regles.js  parc-arbre.js  parc-formulaires.js  parc-etiquettes.js  parc-fiche.js
  demandes-regles.js  demandes-ecritures.js  demandes-signaler.js  demandes-liste.js  demandes-fiche.js
  ordres-regles.js  ordres-ecritures.js  ordres-liste.js  ordres-fiche.js  ordres-onglets.js  ordres-pieces.js  ordres-impression.js
  ordres-habilitations.js
  preventif-regles.js  preventif-ecritures.js  preventif-ecrans.js  preventif-calendrier.js
  magasin-regles.js  magasin-ecritures.js  magasin-articles.js  magasin-mouvements.js  magasin-achats.js
  equipe-regles.js  equipe-ecritures.js  equipe-ecrans.js  equipe-habilitations.js  equipe-acces.js
  controles-regles.js  controles-reserves.js  controles-catalogue.js  controles-ecritures.js  controles-ecrans.js
  controles-reserves-ecrans.js
  garanties-regles.js  garanties-ecritures.js  garanties-formulaires.js  garanties-ecrans.js  garanties-encarts.js
  planning-regles.js  planning-ecritures.js  planning-ecrans.js
  indicateurs-regles.js  indicateurs-series.js  indicateurs-graphiques.js  indicateurs-ecrans.js
  rapport-contenu.js  rapport-ecrans.js
  zip-donnees.js
  zip-tables.js  zip-flux.js  zip-lecture.js
  parametres.js  parametres-codes.js  parametres-solo.js  parametres-sauvegardes.js  parametres-zip.js  parametres-acces.js  (puis import-*.js, §18.1, et wiki-*.js, §20 ; puis js/app.js)
  ```
  Écart retenu (T43) : `indicateurs-series.js` (séries des graphiques) s'insère après
  `indicateurs-regles.js`, qui aurait dépassé 700 lignes.
  Chantier 2.2 (T410, socle des lots L2 et L3) : cinq fichiers créés vides puis remplis par les tâches suivantes, chacun
  complète l'objet de son module par `Object.assign` : `controles-reserves.js` (réserves des contrôles : règles pures,
  T411, puis écritures, T413) et `controles-catalogue.js` (catalogue des contrôles : règles pures, T414, puis bloc du
  formulaire, T416) après `controles-regles.js` ; `controles-reserves-ecrans.js` (carte « Réserves » et ses fenêtres,
  T418 à T420) après `controles-ecrans.js` ; `equipe-habilitations.js` (fenêtres et carte des habilitations, T432)
  après `equipe-ecrans.js` ; `ordres-habilitations.js` (RG8 à l'écran : bandeau, « passer outre », habilitation
  exigée, T438 à T440) après `ordres-impression.js`. Une fonction d'un fichier chargé plus tard est cherchée au moment
  de l'appel (`Controles.interne.x(...)`), comme dans `ordres-fiche.js`.
  Chantier 2.2, lot L4 (T450, squelette du module des garanties et contrats de prestataires) : cinq fichiers créés
  vides juste après le module Controles (après `controles-reserves-ecrans.js`, pour ne pas le couper), dans cet
  ordre : `garanties-regles.js` (crée l'objet `Garanties` : règles pures, T451 ; son en-tête décrit le découpage),
  `garanties-ecritures.js` (T452), `garanties-formulaires.js` (T455), `garanties-ecrans.js` (écran
  « Garanties et contrats », fiches, routes, menu, T456) et `garanties-encarts.js` (carte et badge de la fiche
  équipement, rappel à la création d'un OT correctif, T457) ; les quatre derniers complètent l'objet par
  `Object.assign(Garanties, …)`. Feuille `css/modules/garanties.css`, juste après `controles.css` ; domaine et
  section de textes « garanties », juste après « controles » (§24.3). Un autre module n'appelle `Garanties` que
  derrière `typeof Garanties !== 'undefined'`.
  Lot 7 (T155) : `connexion-ecrans.js` (objet `Connexion`,
  écran de connexion, §22.4) se charge après `acces-textes.js` (ses textes) et avant `accueil.js` ; feuille
  `css/modules/connexion.css`. Lot 7 (T168) : `installation-etapes.js` (objet `InstallationEtapes`, les formulaires des
  huit étapes), `installation-ecrans.js` (objet `Installation`, l'écran plein de l'assistant, §22.10) et
  `installation-fiche.js` (objet `InstallationFiche`, la fiche d'accès et la route `#/installation/fiche` de la coque) se
  chargent dans cet ordre après `connexion-ecrans.js` ; feuille `css/modules/installation.css` (avec `@media print`).
  Lot 7 (T170) : `parametres-acces.js` (objet `ParametresAcces`, carte « Accès et installation » de Paramètres, §22.10)
  se charge après `parametres-sauvegardes.js` et se relie à `Parametres.interne` par le même relais (`carteAcces`,
  `brancherAcces`).
  Chantier socle de données (T189, D171 ; T228 : ZIP écrit par `ZipFlux`, un document à la fois, limites de l'import contrôlées sur les tailles des documents avant toute lecture, photos stockées sans compression, plus de `JSZip.generateAsync`) : `zip-donnees.js` (objet `ZipDonnees`, export ZIP complet : 24 CSV, documents
  cités, rapports figés, `manifeste.json`, jamais `acces/` ; `App.exporterZip` délègue) se charge après `rapport-ecrans.js`.
  Socle de données (T190, D172) : `zip-lecture.js` (objet `ZipLecture`, `lire(source)` : lecture et contrôles stricts d'un ZIP de données, migration en mémoire, sans rien écrire) se charge après `zip-donnees.js`. Lecture en deux passes (T205) : `lire` décompresse chaque document pour le contrôler puis l'oublie (le résultat n'en garde que nom, taille et empreinte SHA-256) ; `lireDocument(lu, nom)` le relit depuis le même fichier, taille, CRC-32 et empreinte revérifiés, au moment de l'écrire (`parametres-zip.js`, un document à la fois) ; pic de mémoire : les tables + un document (`memoire()` : mesure de la dernière lecture, pour les tests). Lecture par morceaux (T227, morceau 2 de T215) : le ZIP est lu par `ZipFlux` (tranches, décompression contrôlée), jamais en entier ni gardé ; plus de JSZip (contrôle 4 retiré, les autres numéros gardés) ; navigateur sans « deflate-raw » : refus `ZipFlux.MESSAGE_NAVIGATEUR` avant toute lecture. Limites (T229, décisions de Nicolas du 05/11) : ZIP de 4 Go au plus sans ZIP64 (`LIMITES.zip` = `ZipFlux.LIMITES.octets`, 4 Go moins 2 octets, lu au chargement : `zip-flux.js` doit se charger avant), 4 Go décompressés, 10 000 entrées ; un message de refus dit « plus de 4 Go » quand l'arrondi égalerait la limite.
  Socle de données (T213) : `zip-tables.js` (objet `ZipTables`, `lire(contenus, fichiersTables, deja, manifeste)` : étape 11 de `ZipLecture`, les tables du ZIP lues, CSV illisibles refusés sauf fichier marqué « abime » au manifeste à l'empreinte juste, rendu dans `abimes` ; format d'origine, migration en mémoire, tables absentes) se charge juste avant `zip-lecture.js`, qui l'appelle : sorti de `zip-lecture.js`, arrivé à 700 lignes.
  Socle de données (T226, morceau 1 de T215 « ZIP par morceaux ») : `zip-flux.js` (objet `ZipFlux`, module bas niveau sans écran ni stockage : `lireRepertoire(blob)` lit le répertoire central par tranches (`Blob.slice`, jamais le fichier entier), `contenu(blob, entree)` décompresse une entrée en flux (`DecompressionStream` « deflate-raw »), taille réelle et CRC-32 contrôlés pendant et après ; `ecrivain({ date })` écrit un ZIP en Blob composé (`CompressionStream`), sans descripteur de données ni ZIP64, 4 Go et 65 534 entrées au plus ; erreurs `ErreurZip` à code ; pas de JSZip en secours : sans « deflate-raw », `MESSAGE_NAVIGATEUR`) se charge juste avant `zip-lecture.js`. L'import (T227) et l'export (T228) s'en servent à la place de JSZip, retiré du dépôt en T229 (`js/lib/jszip.min.js`, sa balise, sa licence et sa ligne d'« À propos »).
  Socle de données (T191, D172) : `parametres-zip.js` (objet `ParametresZip`, bouton « Importer un ZIP… » de la carte « Sauvegardes » : import par remplacement complet, §22.11 « Import ZIP » ; relié à `Parametres.interne` par les relais `blocImportZip` et `brancherImportZip`) se charge juste après `parametres-sauvegardes.js`.
  Objets globaux nouveaux : `Equipe`, `Controles`, `Planning`, `Indicateurs`, `Rapport` (premier
  fichier de chaque préfixe) ; `parc-etiquettes.js` complète `Parc`, `parametres-codes.js` complète
  `Parametres`. Un seul écouteur `DOMContentLoaded` par module, dans son dernier fichier
  (`parc-fiche.js` enregistre aussi l'écran des étiquettes ; `parametres.js` garde le sien et appelle
  `parametres-codes.js` par une fonction relais). Feuilles ajoutées : `css/modules/equipe.css`,
  `controles.css`, `planning.css`, `indicateurs.css` (onglet Rapports compris), `etiquettes.css`.
  Toujours 700 lignes au plus par fichier de `js/modules/`.
- Routes ajoutées (déclarées avant les routes à identifiant, qui excluent `nouveau`) : `#/planning`,
  `#/controles`, `#/controles/nouveau`, `#/controles/<id>`, `#/indicateurs`, `#/equipe`,
  `#/equipe/nouveau`, `#/equipe/<id>`, `#/parc/etiquettes`.

### 15.2 Profils (D41, D47)

| Écran | Demandeur | Technicien | Responsable |
| --- | --- | --- | --- |
| Indicateurs (+ onglet Rapports), étiquettes | — | — | tout |
| Planning | — | lecture (sa ligne en tête) | tout |
| Contrôles | — | lecture | tout |
| Équipe | — | lecture, **aucun taux horaire** (ni à l'écran ni dans le DOM) | tout |
| Paramètres (codes, réglages) | — | — | tout |

Route interdite → accueil avec message (§8). Compteurs d'accueil du lot 3 : technicien et responsable.

### 15.3 Indicateurs — règles pures (`indicateurs-regles.js`, objet `Indicateurs`)
Période = `{ debut, fin }` (dates ISO incluses). Chaque indicateur rend un **résultat** :
`{ valeur: nombre | null, raison: texte | null, effectif: entier, ots: [id…], exclus: [{ id, raison }] }`
— `valeur` null ⇒ `raison` non vide (« non calculable : … », « aucune panne sur la période »).
Valeurs non arrondies ; l'écran arrondit (heures 1 décimale, % 1 décimale, € 2 décimales).
- `Indicateurs.periode(code, aujourdhui, du, au)` : `mois`, `mois-precedent`, `3-mois` (3 mois
  calendaires se terminant aujourd'hui), `12-mois` (défaut : du même jour 12 mois plus tôt + 1 jour à
  aujourd'hui), `du-au` → `{ debut, fin, libelle }`.
- **Panne** : OT `correctif immédiat` / `correctif différé`, `arret_production` = 1, statut ≠ `Annulé`.
  Date de panne = `date_heure` de la DI d'origine, sinon `date_creation` de l'OT ; la panne compte
  dans la période qui contient cette date. Écart retenu (correction de relecture) : la DI d'origine
  est celle que l'OT désigne (`di_id`) ; à défaut, parmi les DI dont `ot_id` est l'OT, la plus ancienne
  au statut `Acceptée` ; jamais une DI `Regroupée` après coup (elle daterait la panne et les délais de
  prise en charge trop tard) : sans DI d'origine, c'est la création de l'OT qui date la panne.
  `Indicateurs.pannes(periode, { equipementId })` → `[{ ot, date, duree (nombre | null), attente }]`.
- **Temps requis** (`tempsRequis(equipement, periode)`) = `heures_fonct_jour` × jours calendaires de
  la période comptés à partir de `date_mes` si elle est postérieure au début ; équipement `rebut` ou
  inactif → exclu ; `heures_fonct_jour` vide ou ≤ 0 → `null`, raison « heures de fonctionnement par
  jour non renseignées » (**jamais** `heures_fonct_defaut` ici).
- **Durée d'arrêt** = Σ `duree_arret_h` des pannes (une panne sans durée est listée dans `exclus`).
- **MTBF** = (temps requis − durée d'arrêt) / nombre de pannes ; 0 panne → `null`, « aucune panne
  sur la période ».
- **MTTR** (D36 a) = Σ `duree_arret_h` / nombre de pannes mesurables ; mesurable = clôturée
  (techniquement ou administrativement) **et** `duree_arret_h` renseignée ; les autres dans `exclus`
  (« non clôturée », « sans durée d'arrêt ») ; aucune mesurable → `null`.
- **Disponibilité** = MTBF / (MTBF + MTTR) ; `null` si l'un des deux l'est. Écarts retenus : aucune
  panne sur la période → disponibilité 1 (100 %, note « aucune panne sur la période » : sous D36 a,
  fonctionnement / requis = 1) ; durée d'arrêt supérieure au temps requis (panne à cheval sur une
  période courte, ou heures par jour sous-estimées) → MTBF et disponibilité `null`, raison « la durée
  d'arrêt dépasse le temps requis de la période » (jamais un chiffre négatif).
- **Attente de pièces** (`attentePieces(otId)` → `{ heures, complet }`) : lecture de `journal.csv`
  (table `ordres_travail`, `id_ligne` = l'OT, triées par `date_heure` puis `id`). Écart retenu
  (constaté en écrivant T43) : `Donnees.modifier` écrit « <description> — <action> » (ex.
  « modification : statut, motif_attente — statut En cours → En attente : Pièce : … », « création —
  création de l'OT (urgence) ») : on lit l'action après « — » (un texte sans « — » est lu tel quel).
  Historique complet ⇔ la création de la ligne de l'OT est au journal (« création — … »). Attente =
  Σ des intervalles entre une action « statut X → En attente : m » où `m` commence par « pièce »
  (casse et accents ignorés) et l'action « statut En attente → Y » suivante (sans sortie : jusqu'à
  `date_fin` ; sans date de fin, non mesurable) ; plafonnée à `duree_arret_h`.
  Pour un ensemble de pannes : moyenne sur les pannes mesurables **à historique complet**, avec leur
  nombre ; aucune → `null` (raison « historique des statuts absent du journal »).
- **Part du préventif** = heures `ot_temps` datées dans la période des OT `préventif systématique` et
  `préventif conditionnel` / heures de tous les OT non annulés.
- **Respect du préventif** : OT `préventif systématique` non annulés avec `gamme_id`, dont la date
  limite = `date_prevue` + tolérance tombe dans la période ; respecté si clôturé (tech. ou admin.)
  avec `date_fin` ≤ date limite. Tolérance (jours, arrondie au supérieur, ≥ 1) =
  `tolerance_preventif_pct` / 100 × période de la gamme : `periodicite_jours` (déclencheur `date`) ou
  `periodicite_unites` / `heures_fonct_jour` de l'équipement (déclencheur `compteur`, compteur en
  heures) ; période inconnue → OT exclu (`exclus`). Résultat = respectés / comptés.
- **OT en retard** : `Accueil.otEnRetard` (lot 1) à la date donnée.
- **Délai de prise en charge** (`delaisPriseEnCharge(periode)`) : OT dont `date_debut` tombe dans la
  période ; délai (h) = `date_debut` − (`date_heure` de la DI d'origine, sinon `date_creation`) ; par
  priorité : `{ mediane, partDansLeDelai, effectif, cible, ots, exclus }` (délai cible `delai_pN_h` ;
  P4 : médiane seule). Écarts retenus : une cible de 0 h (« immédiat ») donne aussi la médiane seule
  (`partDansLeDelai` null : un 0 % serait trompeur) ; un délai négatif (début saisi avant la demande)
  ou illisible est écarté et listé dans `exclus`.
- **Coût** : `Ordres.cout(ot)` (RG7, prix actuel des pièces) des OT clôturés, rangé au mois de
  `date_fin` ; `coutParEquipement(periode)`, `coutsParMois(debutMois, nbMois)`.
- **Valeur du stock** = Σ `Donnees.stockArticle(id)` × `prix_unitaire` des articles actifs.
- Agrégats : `parEquipement(equipementId, periode, ctx)` → `{ tempsRequis, pannes, dureeArret, mtbf,
  mttr, disponibilite, attentePieces, cout }` (chacun un résultat ; `ctx` = `Indicateurs.interne.contexte()`
  à passer quand on l'appelle pour beaucoup d'équipements : sans lui, les index sont reconstruits à
  chaque appel) ; `global(periode, { criticite, atelier }, aujourdhui)` → fiabilité (pannes, arrêt,
  MTBF, MTTR, disponibilité, attente) sur les équipements suivis dont le temps requis est connu (les
  autres listés dans `tempsRequis.exclus`), plus `cout`, `partPreventif`, `respectPreventif`,
  `otEnRetard`, `delais` sur TOUS les OT des équipements filtrés (au rebut et désactivés compris :
  même périmètre que `coutParEquipement` — correction de relecture) et `valeurStock`. Le Pareto des
  pannes compte toutes les pannes (équipements sans heures compris) : son total peut dépasser le
  nombre de pannes du bandeau, qui dit son périmètre.
  Graphiques : `paretoPannes(periode, 10)`, `paretoArrets(periode, 10)` → `[{ equipementId, valeur,
  cumulPct }]` ; `heuresParMois(dernierMois, 12)` → `[{ mois, correctif, preventif, autres }]` ;
  `mtbfMttrCriticiteA(periode)` ; `causes(periode)` → `[{ code, libelle, nombre }]` (codes cause des
  pannes ; « sans code » à part) ; `chargeCapacite(lundi, 4)` (délègue à `Planning.chargeSemaine`).
- Performance : un index par équipement / par OT construit une fois par calcul (pas de recherche
  linéaire dans une boucle) ; budget CS49.

### 15.4 Indicateurs — écran (`indicateurs-graphiques.js`, `indicateurs-ecrans.js`)
- `#/indicateurs` : `?periode=mois|mois-precedent|3-mois|12-mois|du-au&du=&au=`, `?criticite=`,
  `?atelier=`, `?onglet=tableau|rapports`. Responsable seul.
- Bandeau `.instruments` : disponibilité, MTBF, MTTR (« dont attente de pièces : y h (sur n pannes à
  historique complet) » quand calculable), durée d'arrêt, part et respect du préventif, OT en retard,
  coût, valeur du stock ; chaque valeur `null` affiche sa raison ; effectifs visibles ; jamais
  `NaN`, `Infinity`, `undefined`. Encadré « Comprendre » : les définitions du §15.3 en français simple.
  Écart retenu (D35, correction de relecture) : sous chaque chiffre qui a des OT sources, une liste
  repliée « n OT sources · n OT exclus » donne un lien par OT (40 au plus) et la raison des exclus.
- Tableau par équipement (repère, criticité, pannes, arrêt, MTBF, MTTR, disponibilité, coût), tri
  par clic, lien vers la fiche.
- `Indicateurs.graphique(conteneur, { titre, option, colonnes, lignes, nomFichier })` :
  `await App.chargerEcharts()`, `echarts.init(el, null, { renderer: 'svg' })`, thème `T` de la charte
  (police Sora, couleurs de séries `#4C7DFF`, `#C4841F`, `#1498B6`, `#8E6CF0`, « autres »
  `#3A4670` ; couleurs de statut interdites aux séries), légende dès 2 séries, **jamais deux axes
  de valeurs**, tableau « Voir les valeurs » (`<details>`) sous le graphique, boutons « CSV »
  (format §3.1 : BOM, `;`, CRLF, point décimal) et « Image » (PNG fond blanc, ×2, obtenu en dessinant le
  SVG du graphique sur un `<canvas>`). Redimensionnement suivi (`resize`).
- Graphiques : Pareto du nombre de pannes et Pareto de la durée d'arrêt (top 10, barres, cumul en %
  en étiquette) ; heures correctif / préventif / autres par mois (12 mois) ; MTBF puis MTTR des
  équipements A (deux graphiques) ; causes des pannes (barres horizontales) ; charge et capacité par
  technicien sur 4 semaines (barres de charge, capacité en marque horizontale, même axe en heures).
- La palette est vérifiée lisible en deutéranopie et protanopie (test : écart de couleur simulé
  suffisant entre séries d'un même graphique).
- Écarts retenus (T49) : la légende est écrite en HTML au-dessus du graphique (lue par un lecteur
  d'écran, imprimée), pas par ECharts ; le bouton « Image » redessine le graphique avec le thème
  « papier » (`habillerOption(option, 'papier', …)`, fond blanc) au lieu de copier l'écran sombre ;
  les couleurs de texte et de grille sont lues dans les variables CSS de la charte ;
  `Indicateurs.graphique` accepte aussi `id`, `classe`, `sousTitre`, `notes` et `vide` (texte affiché
  à la place d'un graphique sans données) ; une carte « Délais de prise en charge » donne, par
  priorité, la médiane, la part dans le délai cible et l'effectif. Sous la part du préventif, une note
  dit les heures comptées (« x h de préventif sur y h »).
- Limite connue : dans « charge et capacité », les semaines 1 et 4 restent proches en protanopie ;
  elles se distinguent par leur position, la légende et « Voir les valeurs » (une rampe de bleus,
  essayée, a été écartée : 4e semaine à 1,9:1 de contraste sur le fond).
- Gardés après relecture : le lien de l'instrument « OT en retard » ouvre `#/ot?filtre=retard` sans
  reprendre les filtres de criticité et d'atelier ; les graphiques MTBF et MTTR des équipements A ne
  suivent pas le filtre de criticité (ils portent sur A par définition) ; les délais écartés
  (négatifs ou illisibles) ne sont pas listés à l'écran.

### 15.5 Planning (`planning-*.js`, objet `Planning`)
- Règles : `Planning.lundiDe(dateIso)`, `Planning.joursDeLaSemaine(lundi)` (7 dates ISO, UTC) ;
  `Planning.ordresDeLaSemaine(lundi)` → OT ni clôturés ni annulés, avec `technicien_id` et
  `date_prevue` dans la semaine ; `Planning.chargeSemaine(technicienId, lundi)` = Σ `temps_prevu_h`
  de ces OT pour ce technicien (vide = 0) ; `Planning.semaine(lundi)` → `{ lundi, jours, lignes:
  [{ technicien, cases: { date: [ot] }, charge, capacite, surcharge }], aPlanifier: [ot] }` (lignes :
  techniciens actifs par nom ; `aPlanifier` : OT `Préparé` absents de la grille de cette semaine, triés
  par priorité puis date prévue) ; `surcharge` = charge > `capacite_h_semaine`. Écarts retenus : un
  technicien inactif ou inconnu qui a encore des OT dans la semaine a sa ligne, marquée `inactif`,
  après les actifs (sinon ses OT disparaîtraient) ; seules les sept dates réelles de la semaine
  comptent (une date impossible comme « 2026-02-30 » n'est jamais rangée dans la grille).
- Écriture `await Planning.planifier(otId, statutAttendu, technicienId, dateIso)` → `{ statut,
  avertissements }` : une `Donnees.modifier('ordres_travail')` qui, sur la ligne fraîche, refuse si
  le statut a changé (« l'OT a changé sur un autre poste »), si le statut n'est ni `Préparé` ni
  `Planifié` (« préparez d'abord l'OT » pour `Créé`), si le technicien est inactif ; pose
  `technicien_id` et `date_prevue` ; depuis `Préparé`, contrôle `Ordres.verifierPassage(ligne,
  'Planifié')` (RG3, pièces) → refus `ErreurValidation` (message de RG3, `piecesManquantes` joint)
  sinon statut `Planifié`. Journal : « planification : TEC-… le AAAA-MM-JJ (Préparé → Planifié) » ou
  « replanification : … ». Puis RG8 : `Ordres.verifierHabilitation(equipement, technicienId, date)`
  → message affiché et `Donnees.journaliser('ordres_travail', otId, 'avertissement habilitation : '
  + message)` (même texte qu'au lot 1).
- Écran `#/planning` (`?semaine=AAAA-MM-JJ`, un lundi ; `?technicien=`) : grille lundi → dimanche
  (samedi et dimanche grisés), une ligne par technicien (« 38 h / 35 h », badge « surcharge » en
  texte), colonne « À planifier ». Glisser (API HTML5 drag and drop) une carte `Préparé` ou
  `Planifié` sur une case → `Planning.planifier` ; `En cours` et `En attente` non déplaçables. Refus
  RG3 → bandeau + bouton « Mettre en attente (motif : pièce) » (même comportement que la fiche OT).
  **Bouton « Planifier… »** sur chaque carte déplaçable (fenêtre : technicien, date) : même résultat
  sans glisser (WCAG 2.2, 2.5.7). Technicien : lecture, sa ligne en tête, aucun glisser ni bouton.
  Téléphone : une liste par jour (pas de grille).
- Écarts retenus (T48, recette et relecture) : sous 1 700 px de large, la colonne « À planifier » passe
  au-dessus de la grille (à 1 440 px, la grille était illisible) ; au-delà, l'écran du planning n'a
  pas le plafond de largeur de `.contenu` (`.contenu:has(> .pl-ecran)`), sinon la grille y serait plus
  étroite qu'à 1 440 px ; samedi et dimanche sont plus étroits ; le titre d'une carte tient sur trois
  lignes au plus ; `?technicien=` ne garde que la ligne de ce technicien, le dit à l'écran (« Voir toute
  l'équipe ») et suit les liens de changement de semaine ; la mise en attente pour pièce écrit le motif « Pièce : … » avec ce qui est déjà sorti,
  comme la fiche OT ; les écouteurs sont posés sur la racine de l'écran (`.pl-ecran`), jamais sur
  `#contenu`, qui survit aux changements d'écran. Gardé : la grille nomme les techniciens « Nom
  Prénom » (tri par nom), l'écran Équipe « Prénom Nom » ; un OT à date impossible n'apparaît pas dans
  la grille (Contrôle de la base le signale).

### 15.6 Étiquettes QR (`parc-etiquettes.js`, complète `Parc`)
- `Parc.FORMATS_ETIQUETTES` = `{ '24': { colonnes: 3, lignes: 8, largeurMm: 70, hauteurMm: 37 },
  '8': { colonnes: 2, lignes: 4, largeurMm: 105, hauteurMm: 74 } }`.
- `Parc.equipementsPourEtiquettes({ localisationId, criticite, ids })` → équipements actifs (hors
  rebut) de la localisation **et de ses sous-localisations**, filtrés, triés par repère.
- `Parc.planchesEtiquettes(equipements, format, decalage)` → HTML des pages A4 : par étiquette, QR
  (`UI.qrSvg(App.urlFicheEquipement(id), …)`), **repère en clair** en gros, désignation, nom de
  l'entreprise ; positions en mm (`@page { size: A4; margin: 0 }`), décalage haut/gauche en mm.
- Écran `#/parc/etiquettes` (`?localisation=`, `?criticite=`, `?ids=EQ-…,EQ-…`), bouton
  « Imprimer des étiquettes » dans le Parc : sélection, cases à cocher, format, décalage (mémorisé
  sur le poste : localStorage `prevo.etiquettes`), aperçu, « Imprimer » (remplit `#impression`, puis
  `window.print()`). Mode serveur : adresse encodée affichée, avertissement « si l'adresse IP ou le
  port du PC change, les étiquettes ne mènent plus à la fiche : demandez une adresse fixe pour ce PC
  (réservation dans la box) », choix parmi `App.adressesReseau()` quand il y en a plusieurs → écrit
  `adresse_qr` (`Donnees.modifier('parametres')`). Modes dossier et démo : « Le QR contient
  GMAO:<id>, lisible par la caméra de ce poste ». Responsable seul.
- Écarts retenus (T45) : les planches utilisent une page **nommée** (`@page etiquettes { size: A4;
  margin: 0 }`, `css/modules/etiquettes.css`) : une `@page` sans nom aurait aussi annulé les marges de
  12 mm du bon de travail ; le décalage est borné de −10 à +10 mm (pas de 0,5 mm), une valeur hors
  bornes est ramenée dans l'intervalle ; l'écran est enregistré par `parc-fiche.js`
  (`Parc.afficherEtiquettes(conteneur, parametres)`).

### 15.7 Contrôles réglementaires (`controles-*.js`, objet `Controles`)
- Règles : `Controles.STATUTS` = `['en retard', 'observations à lever', 'à planifier', 'à jour']` ;
  `Controles.ajouterMois(dateIso, n)` (même jour, ramené au dernier jour du mois : 31/01 + 1 →
  28 ou 29/02) ; `Controles.prochaineDate(controle)` = `prochaine_date`, sinon `derniere_date` +
  `periodicite_mois`, sinon `''` ; `Controles.etat(controle, aujourdhui)` → `{ statut, secondaires,
  prochaine, joursRestants, raison }` : statut = le premier vrai parmi `en retard` (prochaine <
  aujourd'hui), `observations à lever` (`observations` non vide et `observations_levees` ≠ 1),
  `à planifier` (prochaine ≤ aujourd'hui + 30 j, ou prochaine inconnue : raison « date inconnue »),
  `à jour` ; `secondaires` = les autres états vrais (une date impossible, ex. « 2026-13-05 », compte
  comme inconnue). `Controles.sous30Jours(aujourdhui)` → contrôles
  d'équipements actifs (hors rebut) dont la prochaine date est inconnue ou ≤ aujourd'hui + 30 j.
- Écritures (`Donnees.modifier('controles_reglementaires')`, contrôles sur la ligne fraîche) :
  `verifierControle(valeurs)`, `creerControle(valeurs)`, `modifierControle(id, valeurs)`,
  `enregistrerRealisation(id, { date, organisme, rapport, observations })` (`derniere_date` = date,
  `prochaine_date` = `ajouterMois(date, periodicite_mois)`, `observations_levees` = `0` si
  observations sinon `1` ; date future refusée ; le rapport est un nom de document déjà écrit par
  `App.adaptateur.ecrireDocument`), `leverObservations(id, { date, commentaire })` (journal
  « observations levées le … : … »). Jamais de suppression ; aucun OT généré.
- Écrans : `#/controles` (`?statut=`, `?filtre=30j`, `?equipement=`), `#/controles/nouveau`
  (`?equipement=`), `#/controles/<id>` (fiche, historique au journal, rapport ouvert par
  `urlDocument`, OT réglementaires de l'équipement, « Créer un OT » → `#/ot/nouveau?equipement=…&
  type=réglementaire&titre=…` pré-rempli : `#/ot/nouveau` lit désormais `?type=` et `?titre=` ;
  titre « Levée des observations — <nature> » s'il reste des observations à lever, sinon
  « Accompagnement du contrôle — <nature> », comme le dit D40 — correction de relecture).
  Carte « Contrôles réglementaires » sur la fiche équipement (technicien et responsable).
- Écarts retenus (T47) : la liste ne montre par défaut que les contrôles des équipements suivis
  (actifs, hors rebut) — `?inactifs=1` montre les autres — et accepte `?recherche=` ; la périodicité
  est un nombre entier de 1 à 240 mois ; la dernière date et la date de réalisation ne sont jamais
  futures ; lever des observations exige un commentaire ; le rapport est écrit par
  `Controles.ecrireRapport(controleId, date, fichier)` sous le nom `controle-<id>-<date>.<ext>`
  (« -2 », « -3 »… si le nom existe ; 9 Mo au plus ; une photo est réduite en JPEG de 2 400 px de côté
  au plus, et non 1 280 px comme les photos d'intervention du brief §4 : un rapport photographié doit
  rester lisible). Limite connue : le document est écrit avant l'enregistrement du contrôle ; si un
  autre poste a changé le contrôle entre-temps, l'enregistrement est refusé et le document reste dans
  les documents sans être rattaché.

### 15.8 Équipe et habilitations (`equipe-*.js`, objet `Equipe`)
- Règles : `Equipe.etatHabilitation(hab, aujourdhui)` → `{ statut, joursRestants }`, statut ∈
  `pas encore valable` (obtention future), `échue` (échéance < aujourd'hui), `à renouveler`
  (échéance ≤ aujourd'hui + 60 j), `valide` (échéance plus lointaine, ou vide : « sans échéance ») ;
  `Equipe.habilitationsQuiComptent(technicienId)` → pour chaque intitulé (casse et espaces ignorés),
  la ligne à l'échéance la plus lointaine (vide = la plus lointaine) ; une échéance saisie mais
  illisible rend l'habilitation `échue` (prudence : elle apparaît « à renouveler », jamais « valide ») ;
  `Equipe.aRenouveler(aujourdhui)`
  → `[{ technicien, habilitation, etat }]` des techniciens actifs dont une habilitation qui compte est
  `échue` ou `à renouveler`.
- Écritures : `verifierTechnicien`, `creerTechnicien`, `modifierTechnicien` (désactivation par
  `actif` = 0 ; nom obligatoire, taux ≥ 0, capacité 0–80 h), `ajouterHabilitation(technicienId,
  valeurs)`, `modifierHabilitation(id, valeurs)` (correction), `renouvelerHabilitation(id, {
  date_obtention, date_echeance })` = **nouvelle ligne** de même intitulé (l'ancienne reste) ;
  échéance ≥ obtention.
- Écarts retenus (T46) : ajouter une habilitation d'un intitulé que le technicien a déjà est refusé (le
  message renvoie à « Renouveler » ou « Corriger ») ; un renouvellement doit dépasser l'échéance
  actuelle (sinon l'ancienne ligne compterait encore), et une habilitation sans échéance ne se
  renouvelle pas (elle se corrige) ; deux techniciens actifs ne peuvent pas porter le même nom ;
  `Equipe.STATUTS_HABILITATION` et `verifierTechnicien(valeurs, lignesTechniciens, idCourant)` sont
  exposés (contrôles affichés sous les champs avant d'écrire).
- Écrans : `#/equipe` (`?filtre=a-renouveler`), `#/equipe/nouveau`, `#/equipe/<id>` (habilitations
  avec statut, historique). Pour le technicien : lecture, **sans `taux_horaire`** (absent du DOM).

### 15.9 Accueil (lot 3)
`Accueil.calculerCompteurs()` renvoie en plus `controlesSous30j` (`Controles.sous30Jours`) et
`habilitationsARenouveler` (`Equipe.aRenouveler`) ; cartes « Contrôles sous 30 j » →
`#/controles?filtre=30j`, « Habilitations à renouveler » → `#/equipe?filtre=a-renouveler`
(technicien et responsable). Pour le responsable, bandeau « Figer le rapport de <mois> ? » quand
`Rapport.moisAProposer(aujourdhui)` renvoie un mois (§15.10), boutons « Figer » et « Plus tard »
(masqué jusqu'à la prochaine ouverture : sessionStorage). Écart retenu : le bandeau, construit par
`Rapport.bandeauAccueil()`, dit « Le rapport de <mois> n'est pas encore figé. » et son bouton « Figer
le rapport de <mois> » (avec élision : « d'octobre », « d'août ») ; rien n'est écrit sans ce clic.

### 15.10 Rapport mensuel (`rapport-*.js`, objet `Rapport`)
- `Rapport.donnees(mois 'AAAA-MM', aujourdhui)` (pur) → `{ mois, libelleMois, genereLe, tuiles:
  [{ cle, libelle, valeur, precedent, anneePrecedente, tendance }], faits, decisions, pareto,
  heures12Mois, nonCalculables, comprendre }` ; tuiles : disponibilité, coût du mois, part du
  préventif (mêmes fonctions que §15.3, période = le mois) ; comparaison « non comparable » si le mois
  comparé commence avant la plus ancienne date de l'historique (première `date_creation` d'OT) ;
  faits : règles fixes (plus longue panne du mois, équipement le plus souvent en panne, contrôle ou
  préventif en retard) ; décisions (3 au plus) : équipements dont coût des 12 derniers mois /
  `valeur_remplacement` ≥ `seuil_remplacement_pct` (« à examiner », jamais « à remplacer » ; sans
  valeur : « valeur de remplacement non renseignée »), contrôles en retard, articles à commander.
- `await Rapport.html(mois)` → texte HTML **autonome** : une page A4 (`@page`), styles en ligne, pile
  de polices du système (pas de police à télécharger), graphiques en **SVG intégré** obtenus par
  `echarts.init(null, null, { renderer: 'svg', ssr: true, width, height })` puis
  `renderToSVGString()` ; aucune balise `<script>`, aucun attribut `src`/`href` vers un fichier ou une
  URL (liens `mailto:` exceptés) ; feux = forme + texte ; encadré « Comprendre » ; « données au
  JJ/MM/AAAA HH:MM ».
- `await Rapport.figer(mois)` → nom écrit : `rapport-mensuel-AAAA-MM.html`, ou `…-r2.html`, `-r3`…
  si le nom figure déjà dans `rapports_mensuels` (jamais d'écrasement : `ecrireDocument` refuse un
  nom existant) ; puis `rapports_mensuels` complété (`Donnees.modifier('parametres')`) et journal
  (« rapport mensuel figé : … »).
- `Rapport.moisAProposer(aujourdhui)` → mois précédent si aucun rapport de ce mois n'est dans
  `rapports_mensuels` et que l'historique couvre ce mois, sinon `null`.
- `Rapport.texteCourriel(donnees)` → objet et corps (résumé en texte) ; bouton « Préparer un
  courriel » = lien `mailto:?subject=…&body=…` (`encodeURIComponent`, corps < 1 800 caractères) ;
  rien n'est envoyé par Prévo.
- Onglet « Rapports mensuels » de `#/indicateurs` : liste des rapports figés (ouvrir par
  `App.adaptateur.urlDocument`, imprimer), « Figer le mois de … » (choix du mois), « Recalculer »
  (nouvelle révision). Mode démo : le document reste en mémoire, « Télécharger » (`UI.telecharger`)
  et export ZIP (documents en mémoire, déjà pris par `App.exporterZip`).
- Écarts retenus (T51 et relecture) : `Rapport.donnees` prend aussi `maintenant` (horodatage « données
  au … ») et `figer(mois, options)` renvoie `{ nom, rapport }` ; le corps du courriel a des fins de
  ligne CRLF (RFC 6068) et ne parle d'aucune pièce jointe ; faits et décisions sur les contrôles et le
  repère « réparer ou remplacer ? » ne portent que sur les équipements suivis (actifs, hors rebut) ;
  couleurs et nombres arrondis comme à l'écran ; à 375 px, la liste des rapports défile dans son cadre,
  jamais la page. Gardé : le Pareto du rapport montre les barres sans le cumul en % (gardé à l'écran).

### 15.11 Paramètres (`parametres.js`, `parametres-codes.js`)
- Réglages ajoutés au formulaire : `tolerance_preventif_pct` (0–100), `seuil_remplacement_pct`
  (1–1000), `priorite_preventif` (P1–P4), `horizon_calendrier_semaines` (1–52),
  `heures_fonct_defaut` (1–24, gammes compteur seulement ; écart retenu à la relecture : 0, que le
  préventif remplaçait par 8 sans le dire, est refusé). Les deux clés du lot 2 deviennent donc
  modifiables à l'écran.
- Carte « Codes de défaillance » : liste par famille ; `Parametres.ajouterCode({ famille, libelle,
  code })` (code proposé = lettre de la famille S / C / R + numéro suivant sur 2 chiffres,
  modifiable ; code unique, libellé non vide et unique dans la famille) ;
  `Parametres.modifierLibelleCode(id, libelle)`. Ni désactivation ni suppression (la table n'a pas
  de champ `actif`).
- Écart retenu (T46) : les réglages sont réunis dans une carte « Réglages » ;
  `Parametres.FAMILLES_CODES`, `codePropose(famille, lignes)` et `verifierCode(valeurs, lignes,
  idCourant)` sont exposés (contrôles affichés sous les champs avant d'écrire).

### 15.12 Démo (D49)
Le générateur ajoute ou corrige : contrôles couvrant les 4 statuts à la date de référence (chariot
élévateur : VGP **6 mois**, « Arrêté du 1er mars 2004 (VGP), art. 23 » ; installations électriques :
« Code du travail, art. R4226-16 ; arrêté du 26 décembre 2011 ») ; OT planifiés sur les 4 semaines qui
commencent à la date de référence pour les 4 techniciens, dont une semaine en surcharge ; des OT
`Préparé` à planifier, dont un sur l'équipement qui exige BR ; une panne clôturée sans
`duree_arret_h` ; un historique de statuts au journal (création ou acceptation, transitions,
horodatés de façon cohérente avec les dates de l'OT) pour les pannes des 3 derniers mois, dont une
panne clôturée qui a attendu une pièce ; les cas du lot 1 et du lot 2 sont conservés (2 équipements
sans heures de fonctionnement, habilitation échue et à renouveler…). Nouveaux rôles dans
`demo-scenarios.json` : `controle_en_retard`, `controle_a_planifier`, `controle_observations`,
`controle_a_jour`, `technicien_surcharge` (+ `semaine_surcharge`), `ot_a_planifier`,
`ot_a_planifier_br`, `panne_attente_pieces`, `panne_sans_duree`, `equipements_calcul_main`
(3 équipements dont un A, avec pannes, heures connues). Écarts retenus (T42) : le journal de démo
n'est plus vide (77 lignes au lot 3, au format réel « <description> — <action> » de `Donnees.modifier`,
§15.3 ; le lot 3 bis y ajoute une décision brute « suggestion … ignorée : … », §16.4) ;
le pont roulant cite aussi « art. 23 » ; la démo garde `delai_p1_h` = 0 (« immédiat ») : la cible P1
n'affiche donc que la médiane (§15.3).

### 15.13 Tests du lot 3
Un fichier par sujet : `test_socle_lot3.py`, `test_regles_indicateurs.py` (règles des indicateurs,
dont 3 équipements comparés à un calcul Python indépendant sur les CSV), `test_regles_lot3.py`
(règles des contrôles, de l'équipe et du planning),
`test_equipe.py`, `test_controles.py`, `test_planning.py`, `test_etiquettes.py`,
`test_indicateurs.py`, `test_rapport.py`, `test_accueil_lot3.py`, `test_recette_lot3.py` (recette de
bout en bout en modes serveur et démo, profils, design 1440 et 375 px) ; `test_performance.py`
complété (CS49) ; `test_depot.py` (ordre §15.1, 700 lignes).

## 16. Contrat du lot 3 bis — préventif suggéré (CDC validé le 2026-10-21 : D50–D63)

Écrit avant le code du lot 3 bis, puis **relu et aligné sur le code** à la fin du lot : là où le code
s'écarte du texte d'origine, une mention « écart retenu : … » dit ce qui a été fait et pourquoi. Décisions de Nicolas : **D53 (a)** (toutes les causes
comptent pour S2, format inchangé), **D56 (a)** (aucune périodicité proposée : les faits seulement),
**D59 (a)** (mention « peu de cas » et fourchette dans un détail). Prévo **ne modifie jamais une gamme
tout seul** : une suggestion n'écrit rien ; seules les actions du responsable écrivent (gamme créée ou
modifiée par les écrans du §14.3, décision inscrite au journal).

### 16.1 Socle
- **Format CSV inchangé** : `Schema.version` reste 2, aucun champ ajouté. Clés ajoutées à
  `parametres.csv` (lues par `Donnees.parametre`, absentes ou hors bornes → défaut) :
  `suggestion_seuil_pannes` (`3`, entier de 2 à 20 : S1, S2), `suggestion_visites_sans_constat` (`5`,
  de 3 à 20 : S4), `suggestion_fenetre_mois` (`12`, de 3 à 24). Elles s'ajoutent aux réglages de
  Paramètres (section « Suggestions de préventif », §15.11). S3 (2 sur 4) est fixe.
- **Fichiers** : `js/modules/suggestions-regles.js` (crée l'objet `Suggestions` : règles pures, lecture
  des décisions au journal, écriture d'une décision) et `js/modules/suggestions-ecrans.js` (onglets,
  cartes, encarts, actions), chargés **juste après `preventif-calendrier.js`** ; feuille
  `css/modules/suggestions.css`, après `preventif.css`. `ORDRE_MODULES` de `tests/test_depot.py`
  suit. `causes-frequentes.js` est complété (D59). Toujours 700 lignes au plus par fichier de
  `js/modules/` ; aucune nouvelle bibliothèque.
- Pas de nouvelle route : onglets « Suggestions » et « Décisions » de `#/preventif`
  (`?onglet=suggestions`, `?onglet=decisions`) ; paramètre d'adresse `?suggestion=<clé>` sur
  `#/preventif/gamme/nouvelle` et `#/preventif/gamme/<id>`.

### 16.2 Définitions (D51, affichées dans l'encadré « Comprendre » de l'onglet)
- `jour` : date du jour `AAAA-MM-JJ` (`Donnees.aujourdhui()`), passée en argument aux règles.
- **Moment** d'un OT : `date_fin`, sinon `date_cloture_tech`, sinon `date_creation`, ramené à
  `AAAA-MM-JJ HH:MM` (un `T` devient une espace ; une date seule reste `AAAA-MM-JJ`) ; son **jour** =
  ses 10 premiers caractères (date valide exigée, sinon l'OT est ignoré). « Postérieur à » un autre
  moment = texte strictement plus grand (une date seule, le jour d'une décision, n'est donc pas
  postérieure à cette décision : prudence).
- **Fenêtre** : du lendemain du même jour `suggestion_fenetre_mois` mois plus tôt jusqu'à `jour`,
  bornes incluses (même définition que la période « 12 mois » des indicateurs, §15.3).
- **Équipement suivi** : `actif` ≠ `0` et `statut` ≠ `rebut`.
- **Correctif de même cause** (S1, S2) : OT de type `correctif immédiat` ou `correctif différé`,
  `Clôturé techniquement` ou `Clôturé administrativement`, `cause_code` non vide (toutes les causes,
  « Autre cause » comprise : D53 a), jour dans la fenêtre.
- **Gamme suivie** (S2, S3, S4) : `actif` ≠ `0`, déclencheur `date` ou `compteur` (jamais `seuil`),
  équipement suivi. Écart retenu (relecture) : un déclencheur vide vaut `date`, comme dans le schéma
  (valeur par défaut) et dans le préventif.
- **Visite** d'une gamme : OT de cette gamme (`gamme_id`) clôturé (techniquement ou
  administrativement), jour ≤ `jour` ; triées par moment puis identifiant. **Visite avec anomalie** :
  `anomalie_constatee` = `1` **ou** au moins une DI dont `ot_origine_id` est cette visite.
- **Passage au format 2** : la plus récente ligne du journal de table `parametres`, `id_ligne`
  `version_schema`, dont l'action contient « passage au format 2 du fichier » (§14.1) ; son
  `date_heure` est le moment du passage. Absente (base créée au format 2, démo) : aucune restriction.
- **Intervalle médian** entre des pannes : médiane des écarts en jours entre jours consécutifs
  (triés) ; nombre pair d'écarts → moyenne des deux du milieu ; affiché arrondi au jour (demi vers le
  haut).
- **Clé** d'une suggestion : `S1-<équipement>-<cause>`, `S2-<équipement>-<cause>`, `S3-<gamme>`,
  `S4-<gamme>` (ex. `S2-EQ-0005-C01`, `S4-GAM-0005`).

### 16.3 Règles (D52–D55 ; « seuil » = `suggestion_seuil_pannes`)
Chaque règle ne compte que les faits **postérieurs à la dernière décision** sur sa clé (§16.4), s'il y
en a une. Sous les seuils, rien n'est suggéré.
- **S1 « Créer une gamme »** : équipement suivi **sans aucune gamme active** (tout déclencheur) ; par
  cause, au moins *seuil* correctifs de même cause. Faits : ces correctifs.
- **S2 « Revoir le préventif »** : équipement suivi ayant au moins une gamme suivie qui a au moins une
  visite ; *première visite* = la plus ancienne visite de ces gammes ; par cause, au moins *seuil*
  correctifs de même cause postérieurs à la première visite. Gammes citées : ces gammes. Faits : ces
  correctifs. Toutes les causes comptent (D53 a) : la carte dit « À examiner : la gamme ne dit pas
  quelles pannes elle prévient ».
- **S3 « Anomalies répétées »** : gamme suivie ; parmi ses **4 dernières visites** (ou toutes, s'il y
  en a moins), au moins **2** avec anomalie. Faits : les visites **avec anomalie** (`nombre` = leur
  nombre, `sur` = visites regardées) ; DI liées à ces visites.
- **S4 « Allonger une gamme »** : gamme suivie dont l'équipement est de criticité `B` ou `C` (jamais
  `A`, jamais vide) ; visites comptées = visites postérieures au passage au format 2 (s'il existe) ;
  *série* = les dernières visites comptées, consécutives, sans anomalie ; au moins
  `suggestion_visites_sans_constat` visites dans la série ; **aucun correctif** de l'équipement (type
  correctif, tout statut sauf `Annulé`, toute cause) dont le jour de création est ≥ le jour de la
  première visite de la série. Faits : les visites de la série. Écart retenu (relecture) : le CDC
  (D55) parle de visites « closes » après le passage au format 2 ; le code compare le **moment** de
  la visite (fin des travaux d'abord, §16.2), plus strict : une visite finie avant le passage mais
  close après ne compte pas (CS56 tenu).
- Ordre des clés à égalité : ordre des caractères (pas l'ordre alphabétique de la langue), stable.
- **Ordre** : S2, puis S3, puis S1, puis S4 ; dans chaque groupe, criticité A, B, C, puis vide ; puis
  nombre de faits décroissant ; puis clé.

### 16.4 Décisions (D57) — au journal, aucun fichier nouveau
- Écriture par `Donnees.journaliser(table, id, action)` : table `equipements` et l'équipement pour S1 et
  S2, table `gammes` et la gamme pour S3 et S4. Action : `suggestion <clé> ignorée : <motif>` ou
  `suggestion <clé> traitée : <ce qui a été fait>`. Échec d'écriture (`journaliser` rend `null`) →
  `ErreurStockage` « La décision n'a pas pu être inscrite au journal… » : la suggestion reste ouverte.
- `Suggestions.ignorer(cle, motif)` : motif obligatoire (espaces de bord retirés, sauts de ligne
  remplacés par une espace, 300 caractères au plus) sinon `Donnees.ErreurValidation` ; clé qui n'est
  pas ouverte → `ErreurValidation`. `Suggestions.marquerTraitee(cle, texte)` : texte libre
  (« gamme GAM-0011 créée », « gamme modifiée : periodicite_jours »).
- Lecture : toutes les lignes du journal dont l'action suit
  `^suggestion (S[1-4]-\S+) (ignorée|traitée) : (.*)$` ; la **dernière décision** d'une clé = la plus
  récente (`date_heure`, puis `id`). Une suggestion décidée **revient** seulement quand les faits
  postérieurs à cette décision atteignent à nouveau le seuil de sa règle ; la carte rappelle alors la
  décision précédente (date, motif).

### 16.5 API (`suggestions-regles.js`)
- `Suggestions.calculer(jour, reglages?)` → `{ ouvertes: [suggestion…], decisions: [decision…],
  reglages: { seuilPannes, visitesSansConstat, fenetreMois, debutFenetre, passageFormat2 } }` ;
  `reglages` facultatif remplace les paramètres (tests). Lecture seule.
- Suggestion : `{ cle, regle ('S1'…'S4'), titre, equipementId, repere, criticite, gammeIds: [id…],
  causeCode, causeLibelle, nombre (faits), sur (S3 : visites regardées), intervalleMedianJours (S1, S2 ;
  null sinon), ots: [id…] (du plus récent au plus ancien), dis: [id…] (S3), dates: [jour…] (faits, du
  plus ancien au plus récent), depuis (moment de la décision précédente ou null), decisionPrecedente
  ({ decision, dateHeure, texte, profil } ou null), texte, question }`.
- Décision : `{ cle, regle, decision ('ignorée' | 'traitée'), texte, dateHeure, profil, table,
  idLigne, revenue }` (`revenue` vrai si c'est la dernière décision de cette clé et que la suggestion
  est de nouveau ouverte), de la plus récente à la plus ancienne.
- `Suggestions.ouvertes(jour)`, `Suggestions.pourEquipement(id, jour)` (S1, S2 de l'équipement et S3,
  S4 de ses gammes), `Suggestions.pourGamme(id, jour)` (S2 qui la citent, S3, S4),
  `Suggestions.trouver(cle, jour)` (ouverte, sinon `null`), `Suggestions.ignorer`,
  `Suggestions.marquerTraitee`, `Suggestions.TITRES`.
- Textes (D56 a : aucune périodicité proposée, les faits seulement ; *période* = « en N mois », ou
  « depuis le JJ/MM/AAAA » après une décision) :
  - S1 « CV-02 : 14 pannes « Capteur encrassé » en 12 mois (environ une toutes les 4 semaines), aucune
    gamme active. » — question « Créer une gamme pour prévenir cette panne ? » (fréquence : intervalle
    médian ≥ 14 j → « environ une toutes les N semaines », N = arrondi de médiane / 7 ; sinon « environ
    une tous les N jours » ; écart retenu (relecture) : 1 jour → « environ une par jour », 0 jour
    (pannes le même jour) → aucune fréquence, plutôt qu'une fréquence fausse) ;
  - S2 « PO-02 : 6 pannes « Garniture usée » en 12 mois malgré la gamme GAM-0003 (tous les 90 j) ;
    intervalle médian entre ces pannes : 58 jours. » — question « Raccourcir la périodicité, ajouter une
    opération à la check-list ou créer une gamme dédiée ? À examiner : la gamme ne dit pas quelles
    pannes elle prévient. » ;
  - S3 « GAM-0006 (PR-01) : anomalie constatée à 2 des 4 dernières visites (12/03/2026, 10/07/2026). »
    — question « Raccourcir la périodicité ou compléter la check-list ? » ;
  - S4 « VE-01 : 13 visites de suite sans anomalie (gamme GAM-0005, tous les 30 j), aucune panne depuis
    la première (29/09/2025). » — question « Allonger la périodicité ? Vérifiez d'abord qu'aucune
    obligation (réglementaire, constructeur, garantie) ne l'impose. » Les contrôles réglementaires
    (§15.7) ne sont jamais suggérés.
  Périodicité : « tous les N j » (date), « toutes les N <unité> » (compteur). Aucun « NaN »,
  « Infinity », « undefined » ni « null » dans un texte.

### 16.6 Écrans (`suggestions-ecrans.js`, D57, D58, D60)
- `#/preventif` : onglets « Suggestions » (compteur = nombre ouvert) et « Décisions », **responsable
  seulement** ; pour un autre profil, `?onglet=suggestions|decisions` → accueil avec le message des
  écrans interdits (§8 : « L'écran « Suggestions de préventif » n'est pas disponible pour le profil
  … »). `preventif-ecrans.js` dessine ces onglets par une fonction relais (module chargé après).
  Écart retenu (relecture finale) : le demandeur, à qui tout le Préventif est fermé, reçoit le message
  de l'écran « Préventif » (§8), avant même que l'onglet soit regardé.
- **Carte** d'une suggestion : badge texte du type (« S2 · Revoir le préventif » : jamais la couleur
  seule), équipement (lien) et criticité, texte, question, **dates des faits** (« Dates : du 03/11/2025
  au 11/09/2026 », ou « le … » ; écart retenu à la relecture finale : le contrat d'origine les avait
  oubliées, alors que CS53 les exige), OT liés (5 au plus, les plus récents, chacun suivi de sa date,
  puis « et n autres »), DI liées (S3), décision précédente s'il y en a une, actions :
  - S1 **« Créer la gamme »** → `#/preventif/gamme/nouvelle?equipement=<id>&suggestion=<clé>` :
    formulaire pré-rempli (équipement, libellé « Prévenir : capteur encrassé » — libellé de la cause,
    première lettre en minuscule —, déclencheur `date`) et rappel de la suggestion ; **rien n'est écrit
    sans « Créer la gamme »** ; après création, `marquerTraitee(clé, 'gamme GAM-xxxx créée')` ;
  - S2, S3, S4 **« Ouvrir la gamme <id> »** (une par gamme citée) →
    `#/preventif/gamme/<id>?suggestion=<clé>` : rappel de la suggestion en tête de fiche ; un
    enregistrement de la gamme **avec au moins un changement**, ou une modification de sa check-list,
    marque la suggestion traitée (`gamme modifiée : <champs>` ou `check-list modifiée`) ;
  - **« Ignorer… »** (nom accessible « Ignorer la suggestion <clé> ») → fenêtre avec motif
    obligatoire → `Suggestions.ignorer` → la carte disparaît, message « Suggestion ignorée (inscrite au
    journal). ». Fermée par Échap pendant l'écriture, la fenêtre laisse l'écriture finir : son issue
    décide du message et du réaffichage. Tout blanc du motif (saut de ligne, U+2028, U+2029) devient
    une espace, et la lecture du journal accepte un motif sur plusieurs lignes.
- Onglet **Décisions** : tableau (cartes sur téléphone) des décisions, de la plus récente à la plus
  ancienne : date, clé et type, équipement / gamme (liens), décision, motif, profil, « revenue » le cas
  échéant.
- **Comprendre** (`<details>`) : définitions du §16.2, les 4 règles avec les seuils en vigueur, « Prévo
  ne modifie jamais une gamme tout seul ».
- Écarts retenus (T59) : une suggestion est marquée traitée **une seule fois** par session de page (une
  modification de check-list puis un enregistrement de la gamme n'écrivent qu'une décision) ; la
  check-list est comparée avant et après chaque action (une modification qui ne change rien ne marque
  rien) ; une création n'est marquée que si la gamme est sur l'équipement de la S1 ; l'encart de la
  fiche gamme omet la suggestion déjà rappelée en tête de fiche ; la décision précédente rappelée sur
  une carte perd sa ponctuation finale (« … gammes ; revenue sur de nouveaux faits »).
- Limite gardée : l'écran `#/preventif` n'est pas réaffiché quand le journal change sur un autre poste
  (une décision prise ailleurs apparaît au prochain affichage).
- `UI.onglets` (relecture finale) : l'onglet choisi est ramené dans la partie visible de la barre
  d'onglets quand elle défile (téléphone) ; seule la barre défile, jamais la page.
- **Encarts** « Suggestions de préventif » : sur la fiche équipement (`parc-fiche.js`, près de la carte
  Préventif) et sur la fiche gamme (`preventif-ecrans.js`), responsable seulement, uniquement s'il y a
  des suggestions ouvertes : mêmes cartes et mêmes actions.
- **Accueil** (`accueil.js`, responsable) : instrument « Suggestions de préventif », nombre ouvert, lien
  `#/preventif?onglet=suggestions`, complément « dont n sur criticité A » ou « à examiner ».
- Charte Cockpit, `css/modules/suggestions.css` ; 1440 et 375 px sans défilement horizontal de la
  page ; zones tactiles ≥ 48 px sur téléphone.

### 16.7 Solidité de l'encart « causes fréquentes » (D59 a, `causes-frequentes.js`)
- `CausesFrequentes.fourchette(k, n)` → `{ bas, haut }` : intervalle de Wilson à 95 % (z = 1,96) de la
  part k / n ; `n` = 0 → `null`. Pourcentages affichés arrondis à l'unité (demi vers le haut).
- Encart suffisant : si au moins une cause affichée a une demi-largeur `(haut − bas) / 2` > 0,20, la
  mention « Peu de cas : à prendre comme une piste. » s'affiche sous le titre ; toujours, un
  `<details>` « Précision de ces chiffres » liste « <cause> : entre 32 % et 81 % des cas » et explique
  la fourchette en une phrase. Visible de tous les profils (D60). Les lignes existantes ne changent pas.

### 16.8 Démo (D62)
Générateur à part (graine `GRAINE_LOT3BIS`), lignes des lots 1 à 3 inchangées autant que possible.
Ajouts : une gamme dont 2 des 4 dernières visites ont une anomalie (S3) ; un équipement de criticité
A dont une gamme remplirait S4 (refus) ; une suggestion déjà ignorée au journal (avec motif), puis
assez de nouvelles pannes pour qu'elle revienne. Rôles ajoutés à `demo-scenarios.json` :
`suggestion_creer` (clé S1 de CV-02), `suggestion_revoir` (clé S2 de PO-02), `suggestion_anomalies`
(clé S3), `suggestion_allonger` (clé S4 de VE-01), `suggestion_refus_criticite_a` (gamme refusée),
`suggestion_sous_seuil` (`{ equipement, cause }` à `seuil − 1` pannes, sans gamme active),
`suggestion_ignoree_revenue` (clé). Le générateur vérifie lui-même ces rôles par un calcul Python des
règles du §16.3. Écarts retenus (T56) : rôles réels `S1-EQ-0023-C04` (CV-02), `S2-EQ-0005-C01` (PO-02),
`S3-GAM-0011` (RA-01, une visite tous les 14 jours : case cochée, puis DI envoyée après la clôture
administrative de la visite, qui garde donc sa case à 0, §14.6), `S4-GAM-0005` (VE-01), refus A
`GAM-0012` (GF-01), sous le seuil `{ EQ-0002, C05 }`, ignorée puis revenue `S2-EQ-0001-C05` (CP-01,
décision du 23/03/2026 placée parmi des pannes existantes). Le contenu des lignes des lots 1 à 3 est
inchangé, mais l'ajout de lignes datées a **renuméroté** la suite chronologique des identifiants
(70 OT, 25 DI, opérations et temps d'OT ; références suivies) : les tests passent par les rôles,
jamais par des numéros. Les trois clés `suggestion_*` ne sont pas dans `parametres.csv` de la démo
(valeurs par défaut).

### 16.9 Tests du lot 3 bis
`test_regles_suggestions.py` (règles sur un jeu construit et sur la démo, égalité avec un calcul
Python indépendant, décisions, passage au format 2), `test_causes_frequentes.py` (fourchette de Wilson
égale au calcul Python, mention, détail), `test_suggestions.py` (écrans, actions,
profils, `gammes.csv` identique à l'octet), `test_accueil_lot3bis.py`, `test_recette_lot3bis.py`
(bout en bout, modes serveur et démo, design 1440 et 375 px) ; `test_performance.py` complété (liste
des suggestions < 1 s sur le jeu de charge) ; `test_depot.py` (ordre §16.1, 700 lignes) ;
`test_parametres.py` complété (trois réglages des suggestions).

## 17. Contrat du lot 4 — assistant IA, dictée, guide, fiche technique, finitions (CDC validé le 2026-10-21 : D64–D79)

Écrit avant le code du lot 4 ; il sera relu et aligné sur le code à la fin du lot (mentions « écart
retenu : … »). Décisions de Nicolas : **D67 (a)** (le responsable autorise ou non les fournisseurs
en ligne, défaut non), **D72 (a)** (`qwen2.5:7b` conseillé, mesuré sur le PC), **D76 (a)** (thème clair
à l'écran), **D79** (dépôt privé `nicoboy49/prevo`, poussé en fin de lot seulement). Règle de fond
(brief §10) : **l'IA propose, l'humain valide** ; sans IA, Prévo est identique et n'appelle rien.

### 17.1 Socle
- **Format CSV inchangé** (`Schema.version` = 2). Clé ajoutée à `parametres.csv` : `ia_distant_autorise`
  (`0` ou `1`, défaut `0`), réglage du responsable dans Paramètres (section « Assistant IA »).
- **Réglages propres au poste** (navigateur du poste seulement, `localStorage`, lecture protégée comme
  au §8) : `prevo.ia` = `{ actif, fournisseur: 'ollama' | 'openai', url, modele, cle, delaiS }`
  (défauts : inactif, `ollama`, `http://localhost:11434`, `qwen2.5:7b`, clé vide, 120 s) ;
  `prevo.dictee` = `{ active, avertie }` (défaut : active, non avertie ; `avertie` = `local` ou `nuage`,
  le lieu de transcription annoncé, §17.11) ; `prevo.theme` = `sombre` |
  `clair` (défaut sombre). **La clé n'est écrite nulle part ailleurs** (ni CSV, ni journal, ni
  `sessionStorage`, ni réponse ou console du serveur). Lot 7 (§22.12, audit M1 et M3) : en mode serveur,
  `prevo.ia` ne garde que `{ actif, modele, delaiS }` ; fournisseur, adresse et clé sont ceux du PC serveur.
- **Fichiers** : `ia.js` (crée `Ia` : réglages, portée, appel du fournisseur direct ou par relais,
  délai et annulation, validations), `ia-prompts.js` (complète `Ia` : `Ia.PROMPTS`, textes en français,
  un par fonction, faciles à modifier), `ia-encadre.js` (complète `Ia` : boutons « avec l'IA »,
  encadré Utiliser / Modifier / Ignorer, mention de portée), `dictee.js` (objet `Dictee`), `poste.js`
  (objet `Poste` : écran « Ce poste », thème), chargés **juste après `causes-frequentes.js`** ; feuilles
  `css/modules/ia.css` et `css/modules/poste.css` (après `accueil.css`). `ORDRE_MODULES` suit.
  700 lignes au plus par fichier ; aucune nouvelle bibliothèque. Lot 7 : `ia-serveur.js` (complète `Ia` en mode
  serveur : `Ia.reglagesServeur`, `Ia.lireReglagesServeur`, relais) juste après `ia-encadre.js` (§22.12).
- **Route** `#/poste` « Ce poste » : **tous les profils**, menu (ordre 92, icône `utilisateur`, groupe
  « Administration », visible du demandeur et du technicien). La carte « Ce poste » de Paramètres y
  renvoie (le bouton « Changer de profil » passe dans « Ce poste »).

### 17.2 Serveur (`serveur.py`)
Lot 7 (§22.12, audit M1 à M3) : le corps de `POST /api/ia` ne porte plus que `{ chemin, methode, corps }` ;
l'adresse, la clé et le délai (120 s) viennent de la configuration du PC serveur, et le 403 dépend de `ia_en_ligne`,
plus de `parametres.csv`. Le texte ci-dessous est celui du lot 4.
- **`POST /api/ia`** (en-tête Prévo des écritures, §7) — corps JSON `{ url, chemin, methode, corps,
  cle }` : `url` = adresse de base du fournisseur (`http://localhost:11434`, `https://api.mistral.ai/v1`…),
  `http` ou `https`, sans identifiant, requête ni fragment ; `chemin` ∈ **liste fermée** `api/chat`,
  `api/tags` (Ollama), `chat/completions`, `models` (API compatible OpenAI) ; `methode` `GET` ou `POST` ;
  `cle` facultative, envoyée au fournisseur en `Authorization: Bearer …` seulement. Le serveur relaie,
  **sans suivre de redirection**, avec un délai (≤ 300 s, celui demandé) et une réponse plafonnée
  (2 Mo) ; il rend `{ statut, corps }` (corps JSON du fournisseur, ou texte s'il n'est pas du JSON).
  Refus : chemin hors liste ou adresse invalide → 400 ; fournisseur injoignable → 502 ; délai → 504.
  Ajouts de la relecture : fournisseur **distant** sans `ia_distant_autorise` = 1 dans `parametres.csv`
  → **403** avant tout appel (D67 côté serveur ; hôte classé sans résolution DNS : boucle locale,
  adresses privées et noms en `.local` restent dans l'atelier, tout autre nom — `*.localhost` compris —
  est distant) ; délai non fini, adresse avec espace ou caractère de contrôle, clé non ASCII → 400 ;
  réponse coupée ou illisible → 502 ; jamais 500. Limite : le délai vaut pour chaque opération
  réseau, pas pour la durée totale.
  Jamais la clé dans un message, une erreur ou la console (la ligne de journal d'une écriture ne montre
  que `POST /api/ia`). `localhost` désigne le PC qui fait tourner le serveur (le PC atelier).
- **https en option** : `serveur.py --certificat FICHIER --cle FICHIER` (PEM, les deux ensemble, sinon
  message clair et arrêt) → serveur en https (`ssl` de la bibliothèque standard) ; adresses affichées,
  `GET /api/info` et QR en `https://` ; sans ces options, http comme avant. Certificat de test :
  fabriqué à chaque exécution par openssl (`tests/test_https.py`) — écart retenu : aucune clé privée
  n'est versionnée.

### 17.3 Règles de l'IA (`ia.js`, objet `Ia`)
- `Ia.reglages()` / `Ia.enregistrerReglages(r)` ; `Ia.distantAutorise()` (`parametres.csv`) ;
  `Ia.portee(url)` → `poste` (boucle locale appelée directement : modes dossier et démo),
  `pc-atelier` (boucle locale par le relais : mode serveur), `atelier` (adresse privée : 10/8,
  172.16/12, 192.168/16, `.local`), `distant` (toute autre adresse) ; `Ia.mention(portee, url)` →
  « reste sur ce PC », « reste sur le PC atelier », « reste dans l'atelier », « données envoyées à
  <hôte> ». **Un fournisseur `distant` n'est utilisable que si `ia_distant_autorise` = 1** (D67) ;
  sinon l'activation est refusée avec « Le responsable n'a pas autorisé les fournisseurs en ligne ».
- `Ia.active()` : activé sur le poste, réglages valides, portée autorisée. `Ia.etat()` → `inconnu` |
  `ok` | `injoignable` : **un seul test** (`api/tags` ou `models`) à l'ouverture si l'IA est active,
  aucun appel sinon ; `Ia.tester()` (bouton de « Ce poste ») → `{ ok, modeles, message }`. Les boutons
  IA n'existent que si `Ia.active()` et `Ia.etat()` = `ok`.
- `Ia.demander(fonction, donnees, { signal })` → `{ resultat, modele, fournisseur }` : messages construits
  par `Ia.PROMPTS[fonction]` (le premier message système commence par `Fonction : <nom>`), sortie JSON
  contrainte quand la fonction l'exige (Ollama : `format` = schéma JSON ; API compatible OpenAI :
  `response_format` `json_schema`, puis `json_object` si le fournisseur refuse — 400), `temperature` 0,2,
  délai `delaiS` (`AbortController`), « Annuler ». Mode serveur : toujours par `/api/ia` ; modes dossier
  et démo : appel direct (`fetch`). Erreurs nommées : `IaIndisponible`, `IaDelai`, `IaAnnulee`,
  `IaReponseInvalide` (JSON illisible ou hors schéma), `IaRefusee` (portée non autorisée), avec un
  message en français.
- **Validations pures** (`Ia.valider`, dans `ia-prompts.js` depuis la relecture) : `codes(objet, lignesCodes)` → codes gardés seulement s'ils
  existent dans `codes_defaillance` **et** dans la bonne famille, `rejetes` listés (D70) ; `impact(v)` ∈
  `gêne`, `dégradé`, `arrêt`, `sécurité` ; `checkList(objet)` → 1 à 20 opérations (texte non vide,
  200 caractères au plus, valeur attendue 120 au plus) ; `commentaire(texte, jetons)` → **refus si un
  chiffre apparaît hors d'un jeton** connu (D71), sinon texte avec les jetons remplacés ; un jeton inconnu
  → refus. Tout texte proposé : 4 000 caractères au plus.
- **Données envoyées (D69)** — rien d'autre ne part :

  | Fonction | Envoyé | Attendu |
  | --- | --- | --- |
  | `reformulerDI` | symptôme et description saisis ; repère, désignation de l'équipement ; liste des impacts | `{ symptome, impact }` |
  | `compteRendu` | texte du champ compte rendu (les notes) ; titre et type de l'OT ; repère, désignation ; pièces sorties (désignation, quantité) | `{ texte }` (Constat / Cause / Action / Pièces / Reste à faire) |
  | `codes` | compte rendu ; titre de l'OT ; symptôme de la DI d'origine ; les trois listes (code, libellé) | `{ symptome, cause, remede }` |
  | `checkList` | désignation, marque, modèle de l'équipement ; libellé, déclencheur et périodicité de la gamme ; cause visée si la gamme vient d'une suggestion | `{ operations: [{ operation, valeur_attendue }] }` |
  | `resumeHistorique` | les 20 derniers OT de l'équipement : date, type, titre, libellés des codes, compte rendu (300 caractères) | `{ texte }` |
  | `commentaireRapport` | mois ; jetons et valeurs des chiffres du rapport ; points à examiner (textes) | `{ texte }` à jetons |

  Jamais : noms des techniciens ou des demandeurs, taux horaires, coûts d'OT, documents, photos.
- **Trace (D65)** : `Ia.tracerUtilisation(table, id, champ, modele)` → `Donnees.journaliser(table, id,
  'proposition IA utilisée (<modèle>) : <champ>')`, appelée par l'écran **après** l'enregistrement
  réussi d'un champ rempli par « Utiliser » ou « Modifier ».

### 17.4 Encadré et boutons (`ia-encadre.js`)
- `Ia.bouton(libelle, surClic)` → bouton `.ia-bouton` (« Proposer avec l'IA », « Rédiger le compte
  rendu »…) ou `null` si l'IA n'est pas utilisable ; ≥ 48 px sur téléphone.
- `Ia.ouvrirEncadre({ apres, fonction, donnees, rendu, utiliser, modifier })` : encadré `.ia-encadre`
  placé après l'élément `apres`, progression (« L'IA rédige… » + « Annuler »), puis la proposition,
  la mention **« Proposition de l'IA — <fournisseur>, <modèle> »** et **Utiliser** / **Modifier** /
  **Ignorer** (ou les boutons propres à la fonction : « Ajouter les opérations cochées », « Copier »).
  Erreur → message dans l'encadré, aucune proposition. **Rien n'est écrit par l'encadré** (sauf la
  check-list, §17.5, sur le clic explicite).
- Mention permanente dans la coque quand l'IA est active : « IA : reste sur ce PC » … « IA : données
  envoyées à <hôte> » (texte, pas seulement une icône).

### 17.5 Fonctions dans les écrans
1. **DI** (`demandes-signaler.js`) : « Proposer avec l'IA » près de la description → `{ symptome,
   impact }` ; Utiliser remplit le symptôme et coche l'impact (modifiables avant « Envoyer »).
2. **Compte rendu** (`ordres-onglets.js`, onglet Compte rendu, OT non verrouillé) : « Rédiger le compte
   rendu » à partir du texte déjà saisi → Utiliser remplace le champ (le texte d'origine reste
   récupérable par « Annuler la proposition » tant que rien n'est enregistré).
3. **Codes** (même onglet) : « Proposer les codes » → les trois listes déroulantes remplies par
   Utiliser ; codes rejetés annoncés (« code inconnu proposé par l'IA, ignoré : … »).
4. **Check-list** (fiche gamme, responsable) : « Proposer une check-list » → opérations cochables ;
   « Ajouter les opérations cochées » les ajoute par `Preventif.ajouterOperation` (journal habituel).
5. **Résumé de l'historique** (fiche équipement, technicien et responsable) : carte « Résumé (IA) »,
   « Copier » / « Ignorer » ; rien n'est écrit.
6. **Commentaire du rapport** (onglet Rapports, responsable) : avant « Figer », « Proposer un
   commentaire » ; Utiliser joint le commentaire (jetons remplacés) au rapport figé, dans une section
   « Commentaire », avec « rédigé avec l'aide de l'IA ». `Rapport.figer(mois, { commentaire })`.

### 17.6 Dictée (`dictee.js`, objet `Dictee`)
- Disponible si `SpeechRecognition` (ou `webkitSpeechRecognition`) existe, que la page est sécurisée
  (`isSecureContext`) et que la dictée est active sur le poste. `Dictee.equiper(racine)` pose un bouton
  micro (≥ 48 px sur téléphone, `aria-pressed`) après chaque champ `[data-dictee]` ; appelé après chaque
  affichage d'écran et à l'ouverture d'une fenêtre (`UI.fenetre`).
- **Première utilisation** sur le poste : fenêtre « Dans Chrome et Edge, la voix est envoyée aux serveurs
  de Google ou Microsoft pour être transcrite. » (ou « La voix est transcrite sur ce PC. » si
  `SpeechRecognition.available({ langs: ['fr-FR'], processLocally: true })` rend `available`, auquel cas
  `processLocally` = vrai), boutons « Continuer » / « Désactiver la dictée » ; `avertie` mémorisé.
- `lang` = `fr-FR`, `interimResults` ; le texte reconnu **s'ajoute** à la fin du champ (une espace
  avant), jamais d'écrasement ; un second clic arrête ; erreur → message (« micro refusé », « pas de
  réseau »…).
- Page non sécurisée sur un appareil tactile (téléphone en `http://192.168…`) : pas de bouton, une aide
  discrète « Dictée : utilisez le micro du clavier de votre téléphone. » sous le premier champ dicté.

### 17.7 « Ce poste » (`poste.js`) et thème clair
- Cartes : **Identité** (nom du poste, profil, stockage, « Changer de profil ou de nom de poste… ») ;
  **Assistant IA** (activer, fournisseur, adresse, modèle — liste après « Tester la connexion » —, clé
  pour l'API compatible OpenAI, délai, portée et mention ; avertissement explicite à l'activation d'un
  fournisseur `distant` : « Les textes envoyés — descriptions, comptes rendus, désignations — partent
  chez <hôte> ; ils peuvent contenir des noms. ») ; **Dictée** (activer, état détecté) ; **Affichage**
  (sombre / clair).
- **Thème** : `<html data-theme="clair">` posé dès le démarrage (avant le premier écran) d'après
  `prevo.theme` ; variables déjà définies par la charte (`css/style.css`) ; aucune couleur codée en
  dur dans `css/modules/` qui casserait le thème clair ; contrastes AA (4,5:1 texte, 3:1 grands
  textes et traits) vérifiés sur les couples de la charte ; impression inchangée.

### 17.8 Guide, fiche technique, vitrine
- `GUIDE.html` (racine) : page autonome (styles intégrés, **aucune ressource externe**, aucun script
  nécessaire), imprimable (`@media print`), en français simple : démarrer (démo, dossier, serveur,
  pare-feu en réseau privé), profils, chaque module, préventif suggéré, indicateurs, rapport, IA
  (Ollama, `OLLAMA_ORIGINS` pour les modes dossier et démo, fournisseurs en ligne et autorisation du
  responsable, mentions), dictée (et dictée du clavier sur téléphone), https (mkcert, Android, iPhone),
  sauvegardes et restauration, Excel, limites. Captures intégrées (`<img data-capture="…"
  src="data:image/jpeg;base64,…">`, 1,5 Mo au plus en tout), mises à jour par
  `outils/generer_captures.py` (Playwright, outil de développement) qui écrit aussi
  `docs/captures/*.png` pour le README.
- `FICHE_TECHNIQUE_CSV.md` (racine) : écrit par `outils/generer_fiche_csv.py` d'après `Schema` (22
  tables : rôle, fichier, identifiant, champs avec type, obligatoire, valeurs permises, référence,
  depuis la version ; règles §3 : séparateur, encodage, CRLF, apostrophe de protection, dates).
  `test_fiche_csv.py` vérifie que le fichier est à jour.
- README vitrine (brief §14 bis) : capture du tableau de bord (`docs/captures/accueil.png`), « Essayer en
  30 secondes », fonctions par module à jour (lot 4 compris), renvois au guide et à la fiche.

### 17.9 Finitions (D78)
Caractères invisibles encore en clair dans les fichiers des lots 1-2 → échappements ; fenêtre « action
avec motif » mise en commun (`UI`) pour Contrôles et Équipe ; noms des techniciens « Prénom Nom »
partout (planning compris) ; l'onglet Suggestions et l'onglet Décisions se réaffichent quand le journal
change sur un autre poste. Tag `v1.0.0` quand toute la suite passe ; puis envoi sur GitHub (D79).
Réalisé (T71) : `UI.fenetreAction({ titre, introduction, champs, libelleValider, verifier, action,
classe })` (`verifier` et `action` reçoivent `(valeurs, contenu)` ; champs « fichier » lus par
l'écran dans `contenu`) ; `nomComplet` (Planning, Equipe) rend « Prénom Nom » et les listes restent
rangées par nom puis prénom (`ordreDesNoms`) ; `Donnees` signale le journal changé ailleurs (§5.5)
et l'écran `preventif` du responsable dépend aussi de `journal`, `demandes`, `codes_defaillance` ;
`test_depot` refuse tout caractère invisible en clair (U+00A0, U+202F, U+2009, U+200B) dans `js/`
(hors `js/lib/`), `css/` et les pages HTML.

### 17.10 Tests du lot 4
Faux fournisseur `tests/faux_fournisseur_ia.py` (serveur de test : `api/tags`, `api/chat`, `models`,
`chat/completions`, CORS ouvert ; comportement choisi par le modèle demandé : `faux`, `faux-lent`,
`faux-invente`, `faux-illisible`, `faux-chiffres`, puis `faux-schema`, `faux-enorme`, `faux-redirige`,
`faux-tronque`, `faux-tronque-morceaux`, `faux-html` ; il garde les requêtes reçues pour vérifier les
données envoyées et la clé transmise). Fichiers : `test_serveur_ia.py` (écart retenu : pas de
`test_socle_lot4.py`, le socle est vérifié par `test_depot.py` et `test_parametres.py` ;
`test_ia_fonctions_2.py` couvre la gamme, la fiche équipement et le rapport),
`test_https.py`, `test_ia_regles.py`, `test_poste.py`, `test_dictee.py` (reconnaissance simulée),
`test_ia_fonctions.py`, `test_guide.py`, `test_fiche_csv.py`, `test_recette_lot4.py`,
`test_performance.py` complété (aucun appel réseau à l'ouverture sans IA), `test_ia_reel.py`
(`PREVO_TEST_IA=1` : vrai Ollama et `qwen2.5:7b`, jeu d'essai en français, mesures affichées).

### 17.11 Alignement de fin de lot (T75) : écarts retenus et précisions
Relu sur le code final ; les décisions de Nicolas (D67 a, D72 a, D76 a, D79) sont tenues.
- **IA, règles** (`ia.js`) : `Ia.portee` en mode serveur classe `*.localhost` « distant » (même règle
  que le relais) ; la **clé** n'est gardée que pour l'API compatible OpenAI à la même origine, sauf clé
  donnée explicitement (`enregistrerReglages`, `tester`) : jamais envoyée à une autre adresse ;
  `Ia.evenements` signale aussi l'autorisation du responsable changée (`raison: 'autorisation'`) ;
  modes dossier et démo : un fournisseur en ligne qui refuse les appels du navigateur → « … ne répond pas
  à ce navigateur (hôte) : passez par le mode serveur (voir le guide) » (D66) ; liens locaux 169.254/16 et
  fe80::/10 classés « atelier » ; repli « format json » pour un vieil Ollama ; délai du navigateur =
  `delaiS` + 5 s en mode serveur (le relais coupe le premier).
- **Validations** (`Ia.valider`, `ia-prompts.js`) : le commentaire du rapport refuse aussi les nombres
  écrits en lettres (deux… seize, vingt… soixante, cent, mille, millions, milliards, moitié ; « neuf »
  permis : « un moteur neuf ») ; jeton `{mois}` ajouté.
- **Boutons** (`ia-encadre.js`) : `Ia.emplacement(libelle, surClic)` → `<div class="ia-emplacement">` qui
  pose ou retire le bouton au fil de l'état de l'IA (test d'ouverture fini, fournisseur injoignable,
  réglages, autorisation) sans réafficher l'écran ; l'encadré se place **après** l'emplacement (un message
  d'erreur reste visible). La DI et l'OT suivent le même principe par leurs propres zones.
- **Fonctions dans les écrans** : DI — un impact « sécurité » déjà choisi n'est jamais baissé ; aucune
  demande sans texte. OT — boutons seulement si le compte rendu est modifiable ; trace des seuls champs
  venus de l'IA **et gardés** (un code changé à la main n'est pas tracé), une fois. Check-list — une
  opération ajoutée n'est pas rajoutée après un échec partiel. Résumé — carte masquée sans IA.
  Commentaire du rapport — mois de la proposition retenu : figer un autre mois est refusé (avertissement
  au changement de mois) ; points à examiner envoyés **sans chiffres ni montants** ; trace en échec sans
  faire croire à l'échec du rapport ; « Recalculer » crée une révision sans le commentaire (ses chiffres
  auraient pu changer). La trace dit qu'une proposition a été reprise, même retouchée ensuite.
- **Dictée** (`dictee.js`) : `Dictee.surveiller(racine)` (MutationObserver) pose les micros au fil des
  écrans, onglets et fenêtres (au lieu d'un appel après chaque affichage) ; la dictée **repart du contenu
  du champ** s'il a changé pendant l'écoute (frappe, « Utiliser » de l'IA) : rien n'est jamais effacé ;
  `avertie` retient le lieu annoncé (`local` ou `nuage`) et l'avertissement revient si la voix doit
  partir dans le nuage.
- **« Ce poste » et thème** : le lieu de transcription est demandé sur clic (« Où la voix est-elle
  transcrite ? ») — `SpeechRecognition.available()` fait planter l'onglet dans le Chromium 148 des tests ;
  champ de clé toujours vide (vide = garder, case « Effacer la clé enregistrée ») ; thème clair : contour
  des champs `--bord-champ` (≥ 3:1), badges d'état, retards de l'accueil et sous-titres des gros boutons
  en teinte foncée (≥ 4,5:1), vérifiés **sur les textes réellement affichés** de 12 écrans
  (`test_poste.py`) ; menu latéral qui défile plutôt que de recouvrir le bouton de repli. Limite notée :
  le thème sombre de la charte n'est pas audité de la même façon (contour des champs 1,43:1).
- **Finitions** : écran « À propos » à jour (lots 1 à 4, lien vers le guide).
- **Essai réel (D72)**, 21/10/2026, RTX 3060 6 Go, Ollama 0.40.3, `qwen2.5:7b`, mode serveur, jeu de
  démo : codes 32/36 justes (89 %), 8,6 s en médiane (22 s à la première demande) ; reformulation ≈ 9 s ;
  compte rendu ≈ 16 s. Détail dans `GUIDE.html` §5.5 et `docs/PILOTAGE.md`.

## 18. Contrat du lot 5 — assistant d'import (CDC validé le 2026-10-21 : D80–D92)

Écrit avant le code du lot 5, **relu et aligné sur le code à la fin du lot (T87)** : un écart au texte
d'avant le code est signalé « écart retenu » avec sa raison ; une règle que le contrat ne fixait pas et
qu'une tâche a tranchée est une « précision ». Décisions de Nicolas : **D82 (b)** (référentiels **et**
historique des interventions), **D84 (a)** (fiches existantes complétées, au choix), **D87 (a)** (IA sur
les titres de colonnes seulement), **D88 (a)** (localisations et fournisseurs manquants créés, montrés à
l'aperçu), **D92** avec trois ajustements (ancien numéro d'OT dans le compte rendu ; doublons d'abord par
ce numéro, doublons supposés montrés avec le choix ; OT sans durée d'arrêt exclu du MTTR et de la
disponibilité). Règle de fond : **rien n'est écrit avant « Importer »** ; sauvegarde juste avant ; retour
arrière possible. Format CSV inchangé (`Schema.version` = 2, aucun champ ajouté) ; version de clôture
`v1.1.0`.

### 18.1 Socle
- **Bibliothèque** : `js/lib/xlsx.full.min.js` = **SheetJS CE 0.20.3** (CDN officiel
  `https://cdn.sheetjs.com/xlsx-0.20.3/package/dist/xlsx.full.min.js` ; le paquet npm, figé en 0.18.5, a
  deux failles corrigées depuis), empreinte SHA-256 dans `EMPREINTES` de `tests/test_depot.py`, licence
  Apache-2.0 ajoutée à `js/lib/LICENCES.txt`, ligne dans `BIBLIOTHEQUES` de « À propos ». **Pas chargée
  au démarrage** : `App.chargerSheetJS()` l'injecte comme `App.chargerEcharts()` (§15.1) ; objet global
  `XLSX`. Précision : elle est chargée à la **première lecture d'un classeur** (.xlsx, .xlsm, .xls, .ods)
  ou au premier **modèle .xlsx** demandé, pas à l'ouverture de l'assistant : un CSV ou un collage ne la
  charge jamais.
- **Module `Import`** (préfixe `import-`, chargé **à la fin** de `js/modules/`, après
  `parametres-codes.js`, dans cet ordre) : `import-regles.js` (1/7, crée `Import` : types de données,
  correspondance, conversion, clés naturelles, aperçu — fonctions pures), `import-historique.js` (2/7,
  règles de l'historique, D92), `import-lecture.js` (3/7, lecture des fichiers et du collage),
  `import-ecritures.js` (4/7, écriture, sauvegarde, annulation), `import-modeles.js` (5/7, modèles à
  remplir), `import-ecrans.js` (6/7, écran, étapes 1 à 3, crée `Import.assistant`) et `import-apercu.js`
  (7/7, étapes 4 et 5, complète `Import.assistant`). Feuille `css/modules/import.css` (après
  `poste.css`). 700 lignes au plus par fichier ; `ORDRE_MODULES` suit.
- **Route** `#/import` « Importer des données » : **responsable seulement** (même refus que les autres
  écrans réservés ; écran enregistré avec `parent: 'parametres'`, `tables: []`) ; pas d'entrée de menu
  propre : la carte « Importer des données » de Paramètres (`#carte-import`, lien `#lien-import`) et,
  sur l'accueil du responsable d'une base **sans équipement**, la carte « Votre parc est vide »
  (`#carte-import-accueil`, lien `#lien-import-accueil`, §19).
- **Sauvegarde** : nouveau motif **`avant-import`** dans les listes fermées `MOTIFS_SAUVEGARDE`
  (`serveur.py`) et `MOTIFS_SAUVEGARDE` (`js/stockage-dossier.js`), nom
  `AAAA-MM-JJ_HHMMSS_avant-import` (motifs de nom du §7 et du mode dossier complétés) ; type « Avant
  import » dans la liste des sauvegardes de Paramètres (`decrireSauvegarde`).

### 18.2 Types de données (`Import.TYPES`)
Chaque type liste ses **champs importables** (champs du schéma, plus quelques champs « virtuels »
propres à l'import), sa **clé naturelle** et ses **références**. Les identifiants Prévo ne sont jamais
pris dans le fichier (D85). La liste exacte des colonnes reconnues de chaque type, avec leurs autres
titres, est générée dans `FICHE_TECHNIQUE_CSV.md` (§4 de la fiche, lue dans `import-regles.js`).

| Type (`cle`) | Tables écrites | Clé naturelle | Champs virtuels et références |
| --- | --- | --- | --- |
| `localisations` | `localisations` | chemin `Site > Atelier > Ligne` | `chemin` (un à trois niveaux, `>` ou `/` ou `\` comme séparateur ; type déduit du niveau) |
| `equipements` | `localisations`, `equipements` | repère | `chemin_localisation` (ou une colonne par niveau : `site`, `atelier`, `ligne`) ; `parent` par repère (doit exister ou être dans le fichier) |
| `articles` | `fournisseurs`, `articles`, `mouvements_stock` | référence | `fournisseur` par nom (créé s'il manque, D88) ; `stock_initial` → un mouvement **inventaire** (commentaire « import ») |
| `fournisseurs` | `fournisseurs` | nom | — |
| `techniciens` | `techniciens` | nom + prénom | — |
| `habilitations` | `habilitations` | technicien + intitulé | `technicien` par « Prénom Nom », « Nom Prénom » ou le nom seul s'il est unique (doit exister) |
| `codes` | `codes_defaillance` | famille + code | famille tolérante (« symptome », « Causes »…, lecture signalée) |
| `compteurs` | `compteurs` | équipement + libellé | `equipement` par repère (doit exister) |
| `controles` | `controles_reglementaires` | équipement + nature | `equipement` par repère (doit exister) |
| `gammes` | `gammes`, `gamme_operations` | équipement + libellé | `equipement` par repère ; `compteur` (libellé d'un compteur du même équipement, doit exister) ; `operations` : une ligne par opération (même gamme répétée) ou une colonne d'opérations séparées par « ; » ; `valeur_attendue` (« x ; y », dans le même ordre) |
| `historique` | `ordres_travail`, `ot_temps` | ancien numéro, sinon équipement + date + titre (§18.6) | `ancien_numero`, `equipement` par repère, `technicien` par nom, `temps_passe_h`, codes par code ou libellé |

`Import.TYPES[cle]` = `{ cle, libelle, aide, tables, champs, refs }` ; `champs` = `[{ cle, libelle, table,
champ | null, type, valeurs | null, obligatoire, protege, defaut | null, cleNaturelle, synonymes, exemple }]`
(plus `ref`, `ecrit`, `niveau` ou `famille` selon le champ) ; `refs` = `[{ champ, table, creee }]`, `creee`
vrai pour les localisations et les fournisseurs (D88 a). Les `synonymes` sont ceux du schéma, complétés
dans `import-regles.js` (localisation, parent, stock initial, équipement, technicien, champs des contrôles,
des gammes et de l'historique) ; `exemple` est une valeur valable sur la base de démo (modèles, §18.8).
Précision (T80) : les clés naturelles sont comparées sans casse, sans accents ni espaces doublés,
ponctuation gardée (« CP-01 » ≠ « CP 01 ») ; parmi les fiches existantes, l'active passe d'abord (un repère
inactif est reconnu, donc mis à jour et non recréé) ; les champs de la clé ne sont jamais réécrits ; une
composante de la clé vide refuse la ligne.

### 18.3 Lecture (`import-lecture.js`)
- `Import.lire(source)` → `Promise<{ nom, format, encodage, feuilles: [{ nom, lignes: [[texte]] }] }>` ;
  `source` = `File` (ou `Blob` portant `name`) ou `{ texte, nom }` (collage). `.csv`, `.tsv`, `.txt` et
  collage : décodage par `Donnees.csv.decoder` (UTF-8 avec ou sans BOM, sinon Windows-1252, §3.3 ;
  `encodage` le dit), séparateur deviné par la régularité de son compte hors guillemets (tabulation, `;`,
  `,`), puis PapaParse ; `.xlsx`, `.xlsm`, `.xls`, `.ods` : SheetJS. Un classeur est aussi reconnu à sa
  signature (ZIP, conteneur OLE), quelle que soit son extension ; un fichier sans extension est lu comme un
  texte ; une autre extension → `ErreurImport` qui liste les formats lus. Toutes les cellules deviennent du **texte** (la conversion vient après, par le schéma) : nombres
  sans arrondi d'affichage (format « 000 » gardé : repère « 007 »), cases VRAI/FAUX en « 1 »/« 0 », lignes
  à trous rendues par SheetJS complétées par des cellules vides.
- **Écart retenu (T81)** : SheetJS est appelé avec `cellDates: false`, `cellNF: true`, `dense` et
  `sheetRows` plafonné ; les dates sont calculées depuis leur numéro de série (systèmes **1900 et 1904**)
  et rendues `AAAA-MM-JJ` ou `AAAA-MM-JJ HH:MM`. Raison : avec des objets `Date`, une date d'un `.ods`
  tombait à minuit heure locale, soit la veille en temps universel (constat des fichiers d'essai, T79).
- Plafonds `Import.PLAFONDS = { octets, lignes, colonnes }` : **10 Mo**, **20 000 lignes**, **200
  colonnes** → `ErreurImport` (« Fichier trop grand… »), rien n'est lu. Précision (T81) : pour un `.ods`,
  ils sont contrôlés sur `content.xml` **avant** SheetJS (cellules et lignes répétées : quelques octets
  peuvent valoir un million de cellules, que SheetJS déplierait sans les annoncer dans la plage de la
  feuille). Fichier chiffré (conteneur OLE portant le flux `EncryptionInfo`), vide, collage vide ou sans
  aucune ligne non vide → `ErreurImport` avec un message clair. Erreur nommée `Import.ErreurImport`.
- `Import.ligneEntete(lignes, type)` → rang de la ligne d'en-tête probable parmi les **20 premières** :
  celle qui reconnaît le plus de noms du type (clé, libellé, synonymes, en forme comparable), puis celle
  qui a le plus de cellules de texte non numériques (deux au moins, et au moins la moitié des cellules
  remplies) ; une ligne de titre (une seule cellule remplie) ne gagne jamais ; 0 par défaut. Modifiable
  dans l'assistant.
- `Import.entetes(lignes, rang, surDeuxLignes)` → titres des colonnes ; sur deux lignes, chaque titre est
  joint à celui de la ligne suivante, et le titre d'une cellule fusionnée vaut pour les colonnes
  suivantes.

### 18.4 Correspondance des colonnes (`import-regles.js`)
- `Import.comparable(texte)` : minuscules, sans accents, ponctuation et espaces réduits (« N° de série »
  ≈ « n de serie »).
- `Import.correspondance(type, entetes, echantillon, memoire)` → `[{ colonne, entete, champ, statut,
  raison }]`, `statut` ∈ `sure`, `a_confirmer`, `non_utilisee` ; `memoire` : absent ou `'auto'` = mémoire
  du poste, `null` = aucune, tableau = champ retenu par colonne. Précisions (T80) :
  - « sûre » : l'en-tête comparable est égal à la clé, au libellé ou au nom du champ du schéma (niveau 1),
    sinon à un synonyme (niveau 2) ;
  - un champ = une colonne : le niveau 1 l'emporte (la colonne battue passe « à confirmer », sans champ,
    raison « même champ que la colonne … ») ; à niveau égal, les deux colonnes passent « à confirmer » et
    la seconde reste sans champ ; plusieurs champs possibles pour un même en-tête → « à confirmer » ;
  - « à confirmer » aussi pour un titre proche : préfixe commun d'au moins 3 caractères, ou mot commun
    d'au moins 4 lettres (mots vides exclus) ; aucune proposition d'après le seul contenu d'une colonne
    au titre inconnu ;
  - échantillon : pour une date, un nombre ou un booléen, si moins de la moitié des valeurs non vides se
    lisent dans le type, la colonne baisse à « à confirmer ».
- **Mémoire** : `Import.memoriserCorrespondance(type, entetes, correspondance)` → champ par colonne, et
  `Import.correspondanceRetenue(type, entetes)` → champ par colonne ou `null` ; gardée **sur le poste**
  (`localStorage` `prevo.import`), clé = type + en-têtes comparables, **40** jeux d'en-têtes au plus (les
  plus anciens oubliés) ; JSON abîmé ou stockage refusé → pas de mémoire, sans erreur. Au même jeu
  d'en-têtes, elle revient pré-remplie (statut `sure`, raison « retenue lors d'un import précédent »).
  Précision (T85) : elle est écrite au « Continuer » de l'étape 3, même si l'import n'est pas fait ensuite.
- **IA (D87 a)** : si `Ia.active()` et `Ia.etat()` = `ok`, bouton « Proposer avec l'IA », posé par
  `Ia.emplacement` (il suit l'état de l'IA sans réafficher l'écran) ; fonction `Ia.PROMPTS.colonnesImport`.
  Envoyé : les **titres** des colonnes `non_utilisee` et `a_confirmer` (non vides, sans doublon, **60** au
  plus) et la liste des champs (clé et libellé) — **aucune valeur de cellule**. **Écart retenu (T85)** :
  seuls les champs **encore libres** sont envoyés (pas ceux des colonnes « sûres ») ; raison : l'IA ne
  peut pas proposer un champ déjà pris. Attendu = `{ colonnes: [{ entete, champ }] }`, schéma fermé (titre
  parmi ceux envoyés, `champ` parmi les clés envoyées ou `""`) ; la vérification ne garde qu'une colonne
  par champ et un champ par colonne, le reste est listé dans `rejetes` (comme D70). « Appliquer (à
  confirmer) » : chaque proposition passe « À confirmer » (raison « proposée par l'IA (modèle) : à
  confirmer ») ; une proposition sur le champ d'une colonne sûre est ignorée. Trace à l'import réussi, si
  une colonne proposée par l'IA a été gardée : `Donnees.journaliser(<table de la fiche>, '', 'proposition
  IA utilisée (<modèle>) : colonnes de l\'import <fichier> (« titre » → Champ, …)')`.

### 18.5 Aperçu à blanc (`Import.preparer`)
`Import.preparer(type, lignes, correspondance, options)` → `{ type, lignes: [{ numero, rang, action,
raisons, valeurs, changements: [{ champ, libelle, avant, apres }], cible }], ecritures: { nomTable: { creer:
[ligne complète], modifier: [{ id, changes }] } }, referencesCreees: [{ table, libelle, id }], totaux: {
lignes, references, creer, mettre_a_jour, identique, refusee, … } }` — **pure** (lit `Donnees.lignes`,
n'écrit rien) :
- `lignes` = les lignes de données seules (sans l'en-tête) ; `options` : `mettreAJour` (vrai par défaut,
  D84 a), `numeroPremiereLigne` (2 ; l'écran passe le rang de l'en-tête + 2, + 1 pour un en-tête sur deux
  lignes), `maintenant` (`AAAA-MM-JJ HH:MM`, sinon `Donnees.maintenant()`), `utilisateur`
  (« Responsable »), `importerQuandMeme` (historique, §18.6). Une entrée de correspondance sans champ ou
  `non_utilisee` est ignorée ; un champ choisi pour deux colonnes, un champ ou un type inconnu →
  `ErreurImport`. `numero` = `numeroPremiereLigne` + `rang` (indice dans `lignes`) ; une ligne entièrement
  vide est omise. `valeurs` : valeurs converties des colonnes utilisées (texte brut d'une cellule
  illisible) ; `cible` : identifiant créé ou existant, vide pour une ligne refusée. `ecritures` : une
  entrée par table du type, même vide ; `creer` porte des lignes complètes (défauts compris) avec leurs
  identifiants, dans l'ordre du fichier.
- conversion de chaque cellule par `Donnees.normaliser` selon le type du champ (dates JJ/MM/AAAA, ISO,
  date de tableur déjà rendue par la lecture ; décimaux à virgule ou à point ; booléens « oui/non/x/1/0/vrai/
  faux » ; listes fermées par `Import.comparable` et quelques équivalences affichées « lu comme », D86 :
  statut « en fonctionnement » → en service, « réformé » → rebut, criticité « classe A », type de
  localisation « usine » → site, déclencheur « calendaire » → date…) ; champs `protege` gardés tels quels ;
  valeur illisible → ligne **refusée** avec la raison (jamais de valeur inventée). Précisions (T80) : les
  textes sont relus par `Donnees.csv.relireValeur` (apostrophe de protection retirée), une apostrophe en
  tête est retirée pour les autres types (un rapport des refus corrigé se réimporte) ; une date avec heure
  dans un champ date garde la date ; les nombres sont mis sous forme canonique (« 45 000,50 » → `45000.5`)
  et comparés numériquement (« 4,80 » = 4.8 → identique) ; une valeur qui semble abîmée par Excel donne
  une note, pas un refus.
- `action` ∈ `creer`, `mettre_a_jour` (D84 a : seulement les colonnes importées et **non vides** qui
  changent ; `changements` en textes lisibles — chemin, repère, nom du fournisseur —, une entrée
  `operation` par opération ajoutée à une gamme), `identique`, `refusee` (champ obligatoire vide, valeur
  hors liste, doublon dans le fichier, référence introuvable non créable, plafond), et pour l'historique
  `doublon_sur`, `doublon_suppose` (§18.6). Précisions (T80) : avec `mettreAJour: false`, une fiche
  existante qui diffère est `identique`, raison « déjà dans Prévo : mise à jour non demandée » ; un champ
  obligatoire vide ne refuse la ligne que si elle **crée** une fiche (pour une fiche existante, la cellule
  vide n'efface rien, D84).
- références par clé naturelle : localisation (chemin) et fournisseur (nom) **créés** s'ils manquent
  (D88 a) et listés dans `referencesCreees` (seules les références utilisées par une ligne gardée sont
  créées et consomment un identifiant) ; équipement parent, équipement d'un compteur, d'un contrôle ou
  d'une gamme, compteur d'une gamme, technicien → doivent exister, sinon ligne refusée. **Écart retenu
  (T80)** : le parent est accepté **n'importe où dans le fichier**, plus bas compris (le contrat disait
  « plus haut ») ; raison : l'ordre des lignes d'une liste de parc ne doit pas compter (un ensemble peut
  y figurer après ses sous-ensembles). Parent refusé → enfant refusé (« équipement parent refusé (ligne n) ») ; une boucle
  de parents, ou un équipement son propre parent, est refusée.
- localisations (précisions, T80) : séparateur `>` s'il est présent, sinon `/` ou `\` ; trois niveaux au
  plus ; le premier niveau est cherché parmi les sites, sinon parmi toutes les localisations de ce nom
  (deux du même nom → ligne refusée, « donnez le chemin complet ») ; le type d'un niveau créé se déduit du
  parent (site → atelier → ligne) ou de sa colonne ; pour le type `localisations`, une ligne qui nomme une
  localisation déjà prévue comme parent la prend à son compte. Technicien : « Prénom Nom », « Nom
  Prénom », sinon le nom seul s'il est unique ; plusieurs possibles → refusée.
- gammes (précisions, T80) : la première ligne d'une gamme porte la fiche, les suivantes n'ajoutent que
  leurs opérations (« opération ajoutée à la gamme de la ligne n ») ; une ligne répétée sans opération est
  un doublon ; une opération déjà présente (sans casse) n'est pas recréée ; sur une gamme existante, les
  nouvelles opérations suivent le plus grand `ordre` et une valeur attendue différente et non vide est mise
  à jour.
- stock initial : `{ date: maintenant, article_id, type: 'inventaire', quantite, ot_id: '', utilisateur,
  commentaire: 'import' }` pour un article créé avec un stock (« 0 » donne un inventaire de 0, une cellule
  vide aucun mouvement), et pour un article existant dont le stock calculé (`Donnees.stockArticle`) diffère
  du fichier (avec `changes.stock`) ; la ligne d'article porte déjà le stock.
- deux lignes du fichier avec la même clé naturelle → la seconde est refusée (« doublon dans le
  fichier, ligne n ») ; au-delà de 20 000 lignes, chaque ligne est refusée (« plafond »).
- identifiants des créations par `Donnees.nouvelId` (dans l'ordre du fichier, créations prévues
  comprises) ; `defaut` du schéma pour les champs absents (`criticite` B, `statut` en service, `actif` 1…),
  signalé dans `raisons` pour une création dont la colonne est utilisée mais la cellule vide
  (« Criticité vide : « B » par défaut »).
- **Contrôles des formulaires** (T92, décision de Nicolas du 2026-10-22) : `import-controles.js`
  (`Import.controlerFormulaires`, appelé par `Import.preparer` avant `terminer`) applique à chaque ligne à
  créer ou à mettre à jour les vérifications des écrans, appelées telles quelles : `Parc.verifierLocalisation`,
  `Parc.verifierEquipement`, `Magasin.interne.verifierArticle`, `Magasin.interne.verifierFournisseur`,
  `Equipe.verifierTechnicien`, `Equipe.interne.verifierHabilitation`, `Parametres.verifierCode`,
  `Controles.verifierControle` (« aujourd'hui » = `maintenant` de l'aperçu) et `Preventif.verifierGamme`.
  Une création est contrôlée telle qu'elle sera écrite (défauts du schéma compris), une mise à jour sur la
  fiche existante complétée des changements (une cellule vide n'efface rien) ; l'unicité tient compte de la
  base, des références créées et des lignes acceptées plus haut. Refus avec le message du formulaire ; ce
  qui dépend d'une ligne refusée l'est aussi (enfant d'équipement, opérations d'une gamme) et une référence
  créée pour elle seule ne l'est plus. Rien pour les compteurs (aucun formulaire de création) ni pour
  l'historique (aucun formulaire de création d'un OT clôturé). Aucune ligne des fichiers d'essai ne change
  de sort.
- `Import.rapportRefus(apercu, lignes, entetes)` → texte CSV (format de Prévo, §3.1) des lignes
  refusées, avec une colonne « Raison » en tête (l'écran le propose sous le nom
  `lignes-refusees-<fichier>.csv`).
- `Import.interne` : outils partagés avec `import-historique.js` (`convertir`, `lireCellules`,
  `nouveauContexte`, `prevoir`, `refuser`, `terminer`, `fabriqueIdentifiants`, `trouverEquipement`,
  `trouverTechnicien`, `EQUIVALENCES`…) ; ce n'est pas une API.

### 18.6 Historique des interventions (`import-historique.js`, D92)
`Import.preparerHistorique(lignes, correspondance, options, outils)`, appelé par
`Import.preparer('historique', …)` avec `outils = Import.interne` ; même sortie que §18.5, avec : `action`
∈ `creer`, `refusee`, `doublon_sur`, `doublon_suppose` (jamais `mettre_a_jour` ni `identique`) ; sur une
ligne en doublon, `doublon` = `{ ot, ligne }` (OT doublé, et numéro de la ligne doublée du fichier ou
`null` contre la base) et `cible` = l'OT doublé (vide si la ligne doublée n'est pas importée), raison du
doublon en tête ; `totaux.doublon_sur` et `totaux.doublon_suppose` toujours présents ;
`ecritures.*.modifier` toujours vide ; `ot_temps.ot_id` = l'identifiant de l'OT calculé par l'aperçu.
Option `importerQuandMeme` = numéros de ligne des doublons supposés à importer (tableau ou `Set` ;
absent = aucun) ; `mettreAJour` est sans effet. `Import.ligneAncienNumero(numero)` → `Ancien n° : <numéro>`.
- Chaque ligne acceptée → un OT **« Clôturé administrativement »** : `origine` « manuel » (correctif,
  amélioration, réglementaire) ou « préventif » (préventif systématique ou conditionnel, sans gamme) ;
  `type` par correspondance tolérante (absent → « correctif différé », signalé) ; `priorite` absente →
  « P3 », signalée ; `titre` absent → début du compte rendu (80 caractères) ; `date_creation` = date de
  création, sinon date de début (ni l'une ni l'autre → refusée) ; `date_debut`, `date_fin` (absente → date
  de début) ; `date_cloture_tech` = `date_cloture_admin` = `date_fin` ; `arret_production` (colonne, ou 1 si
  une durée d'arrêt > 0 est donnée) ; `duree_arret_h` **vide si absente, jamais 0 inventé** ; codes par
  code ou libellé **dans la bonne famille**, sinon vides et signalés (jamais de code créé) ;
  `technicien_id` par nom (introuvable → vide, signalé) ; `temps_passe_h` → une ligne `ot_temps`
  (technicien de l'OT, jour de la date de fin) ; `cout_soustraitance` ; `remise_service` 1.
- **Ancien numéro** (ajustement 1) : la colonne « N° d'OT » de l'autre logiciel est écrite **en tête du
  compte rendu**, sur sa propre ligne `Ancien n° : <numéro>` (puis le compte rendu importé ; ses retours à
  la ligne sont gardés). Sans ancien numéro, pas de cette ligne, et seul le doublon supposé est possible.
- **Doublons** (ajustement 2) : `doublon_sur` = un OT existant (ou une ligne précédente du fichier) dont
  le compte rendu contient la ligne `Ancien n° : <même numéro>` → ignoré ; sinon `doublon_suppose` =
  même équipement, même `date_creation` à la minute et même titre (comparable) → **montré** dans l'aperçu
  avec une case « Importer quand même » (non cochée), jamais écarté en silence ; un OT existant n'est
  **jamais modifié**.
- Identifiant `OT-AAAA-NNNN` de **l'année de `date_creation`** (`Donnees.nouvelId('ordres_travail', …,
  dateIso)`, par `Import.interne.terminer`).
- Précisions (T82), là où D92 se taisait :
  - ordre des contrôles d'une ligne : le doublon sûr d'abord (il ne demande que l'ancien numéro : une
    ligne déjà importée reste « doublon sûr » même si une autre de ses cellules est devenue illisible),
    puis les refus, puis l'OT, puis le doublon supposé ;
  - doublon sûr : cherché dans les OT de la base (n'importe quelle ligne « Ancien n° : … » du compte rendu,
    lue avec tolérance : « n° », « nº » ou « no », espaces libres) et parmi les lignes précédentes **non
    refusées** du fichier (une ligne refusée ne réserve pas son numéro) ; numéro comparé sans casse,
    accents ni espaces doublés ;
  - doublon supposé : cherché parmi tous les OT de la base (tous statuts, annulés compris), puis parmi les
    lignes créées plus haut ; un titre déduit du compte rendu compte aussi ; coché, il devient une
    création, garde `doublon` et la raison « importée quand même » ;
  - type : équivalences affichées (dépannage, curatif → correctif immédiat ; préventif, entretien ou
    maintenance préventive → préventif systématique ; conditionnel → préventif conditionnel ; amélioratif →
    amélioration), ajoutées au chargement à `Import.interne.EQUIVALENCES['ordres_travail.type']` ; un type
    **inconnu** refuse la ligne (jamais remplacé en silence par le défaut) ;
  - dates : une date seule devient « 00:00 » ; `date_fin` absente → date de début, sinon date de création
    (signalé) ; `date_debut` absente reste vide ; pas de contrôle « fin avant début » ;
  - titre absent : tiré du compte rendu (sans la ligne « Ancien n° »), espaces réduits, coupé en fin de
    mot, « , ; : » finals retirés ; ni titre ni compte rendu → refusée (titre obligatoire au schéma) ;
  - arrêt : la colonne « Arrêt » l'emporte ; « non » avec une durée > 0 reste « non », signalé ; « oui »
    sans durée → durée vide, signalé (panne hors MTTR et hors disponibilité) ; une durée **0 donnée** est
    gardée ;
  - nombre négatif (durée d'arrêt, temps, sous-traitance) → refusée ; code désigné par un libellé
    ambigu → vide, signalé ; technicien ambigu → vide, signalé ;
  - temps : une ligne `ot_temps` seulement si le temps est > 0 ; temps sans technicien → ligne de temps
    sans technicien, signalée (heures comptées, coût de main-d'œuvre nul) ;
  - équipement inactif ou au rebut : accepté (vrai historique).
- **Indicateurs (ajustement 3)** : une panne sans durée d'arrêt reste comptée dans le nombre de pannes et
  le MTBF, mais elle est **exclue du MTTR** (déjà le cas) **et de la disponibilité** : la disponibilité se
  calcule sur les seules pannes **avec** durée d'arrêt (MTBF de ces pannes, MTTR) ; elle est « non
  calculable » s'il n'y en a aucune ; la liste des exclus (« sans durée d'arrêt ») l'accompagne, comme pour
  le MTTR. **Écart retenu** (au §15, lot 3, tâche T78) : l'ajustement de Nicolas visait l'OT importé ; il
  vaut pour **tous les OT, importés ou saisis**, sinon un même OT serait compté de deux façons (avant, la
  disponibilité comptait une panne sans durée comme 0 h d'arrêt) ; interprétation signalée à Nicolas.
  `CalculPython` de `test_regles_indicateurs.py` suit.

### 18.7 Écriture et annulation (`import-ecritures.js`)
- `Import.importer(apercu, { nomFichier, recalculer })` → `Promise<{ sauvegarde, tables: { nom: { crees,
  misAJour } }, tablesTouchees, nomFichier }>` :
  1. **revérification** : `recalculer()` (facultatif ; l'écran refait `Import.preparer` avec les mêmes
     lignes, correspondance et options, même `maintenant`) rend l'aperçu calculé sur les lignes fraîches ;
     s'il diffère de l'aperçu validé (identifiants ou champs à écrire), **rien n'est écrit** et
     `ErreurImport` est levée avec `perime: true` et `apercu` = le nouvel aperçu, que l'écran montre.
     **Écart retenu (T83)** : le contrat disait de passer la ligne en « identique » ou « mettre à jour » et
     d'écrire ; raison : ne jamais écrire autre chose que ce que le responsable a vu et validé. Une fiche
     créée entre-temps par un autre poste n'est donc jamais doublée. Rien à créer ni à mettre à jour →
     `ErreurImport` ;
  2. **sauvegarde** `adaptateur.sauvegarder('avant-import')` en modes serveur et dossier (échec → rien
     n'est écrit, message) ; en démo, instantané en mémoire des tables touchées ;
  3. écriture par `Donnees.modifier` table par table, dans l'ordre `Import.ORDRE_ECRITURE` (localisations,
     fournisseurs, techniciens, équipements, articles, mouvements, compteurs, contrôles, habilitations,
     gammes, opérations, codes, OT, temps) : créations puis mises à jour ; un identifiant déjà pris
     entre-temps → `ErreurImport` (« relancez l'aperçu »), jamais de doublon ;
  4. journal : chaque ligne écrite (action `import <fichier>` de `Donnees.modifier`), puis une ligne de
     bilan par table, `import <nom du fichier> : n créé(s), m mis à jour`.

  **Écart retenu (T83)** : un échec en cours d'écriture laisse un **résultat partiel** : l'erreur porte
  `resultatPartiel` (même forme, tables déjà écrites, sauvegarde), que l'écran propose d'annuler ; raison :
  l'écriture est d'un seul tenant par table, pas pour tout l'import (D83).
- `Import.annuler(resultat)` → `Promise<{ restaurees }>` : modes serveur et dossier →
  `adaptateur.restaurer(sauvegarde, tablesTouchees)` (avec la copie de sécurité habituelle,
  `_avant-restauration`), puis `Donnees.chargerTout()` ; démo → réécriture des tables touchées depuis
  l'instantané, puis rechargement de chacune. Journal (table `parametres`) : `import <fichier> annulé :
  <tables> rendues dans leur état d'avant`. La confirmation (« … les modifications faites depuis l'import,
  sur ces tables, seront perdues ») est demandée par l'écran.

### 18.8 Modèles à remplir (`import-modeles.js`)
`Import.modele(type, format)` → **`Promise<Blob>`** : `xlsx` (feuille « Données » avec les en-têtes en
libellés et une ligne d'exemple ; feuille « Aide » : présentation du type, puis une ligne par colonne :
obligatoire, valeurs permises, formats, autres titres reconnus) ou `csv` (format de Prévo : BOM, « ; »,
CRLF ; en-têtes en libellés, une ligne d'exemple). **Écart retenu (T84)** : une promesse et non un `Blob`
direct, parce que SheetJS est chargé à la demande (§18.1). Ajouts : `Import.nomModele(type, format)` → nom
du fichier proposé (`prevo-modele-<type>.xlsx` ou `.csv`) et `Import.aideModele(type)` → lignes de la
feuille « Aide ». La ligne d'exemple vient de `champ.exemple` : un modèle rempli de sa ligne d'exemple
s'importe sans refus (base de démo).

### 18.9 Écran « Importer des données » (`import-ecrans.js`, `import-apercu.js`)
Étapes, une à la fois, avec « Retour » (les choix sont gardés en revenant en arrière) ; fil des étapes en
haut (composant `.etapes` ; au téléphone, « Étape n sur 5 : … ») ; `.import-etape[data-etape]`. État neuf
à chaque affichage de l'écran (quitter l'écran abandonne l'assistant). `Import.assistant` (outils partagés
des deux fichiers : `etat()`, `allerA(n)`, `recommencer()`, `section()`, `navigation()`, `etapes`…) n'est
pas une API.

1. **Quoi** : tuiles à bouton radio `input[name=import-type]` (les 11 types, libellé et aide), ordre conseillé
   pour reprendre un atelier (localisations et équipements d'abord, l'historique en dernier) ; boutons
   `#import-modele-xlsx` et `#import-modele-csv` (désactivés sans type). Changer de type oublie la
   correspondance et repropose la ligne d'en-tête.
2. **D'où** : zone de dépôt `#import-depot` avec « Choisir un fichier » (`#import-fichier`), zone de
   collage `#import-collage` et « Lire le collage » ; erreurs de lecture dans `#import-erreur` (message de
   l'`ErreurImport` tel quel) ; puis `#import-lu` : nom et nature du fichier, feuille (`#import-feuille`,
   s'il y en a plusieurs), ligne d'en-tête (`#import-ligne-entete`, « Proposée par Prévo : ligne n »), case
   « En-tête sur deux lignes » (`#import-deux-lignes`), titres lus, nombre de lignes, extrait du haut de la
   feuille (8 lignes, 30 colonnes au plus) défilant dans son cadre. Une ligne d'en-tête sans aucun titre
   (que des nombres ou des dates) ou sans données dessous : message clair, « Continuer » désactivé
   (l'écran refait ce test, `Import.ligneEntete` rendant 0 dans ce cas).
3. **Colonnes** : tableau `table.import-colonnes` (titre et lettre de la colonne, trois valeurs d'exemple,
   champ choisi par `select.import-champ` — « — Ne pas importer — » et les champs du type, « (obligatoire) »
   pour un champ obligatoire ou une clé —, statut en texte **et** en couleur : « Sûre », « À confirmer »,
   « Non utilisée », avec sa raison ; au téléphone, une carte par colonne) ; bouton IA (§18.4) dans
   `#import-zone-ia`. Un choix à la main passe « Sûre » (« choisi à la main ») et retire le champ à la
   colonne qui l'avait : jamais deux colonnes pour un champ. Alertes : aucune colonne utilisée (« Continuer »
   refusé), champs obligatoires sans colonne, colonnes à confirmer. Précision (T85) : les colonnes encore
   « à confirmer » au « Continuer » sont importées telles quelles, avec un bandeau qui le dit (pas de
   confirmation ligne à ligne).
4. **Aperçu** : `Import.preparer` (même `maintenant` pendant tout l'aperçu) ; case « Compléter et mettre à
   jour les fiches existantes » (`#import-mettre-a-jour`) **cochée par défaut**, absente pour l'historique
   (un OT n'est jamais modifié) ; chaque case recalcule l'aperçu. Résumé (`#import-resume`, « n lignes
   lues : … à créer, … à mettre à jour, … identiques, … refusées »), références créées
   (`#import-references`), filtres `button.import-filtre` avec leur total (référentiels : toutes, à créer, à
   mettre à jour, identiques, refusées ; historique : toutes, à créer, refusées, doublons sûrs, doublons
   supposés), « Télécharger les lignes refusées (n) » (`#import-refus`), tableau `table.import-lignes`
   défilant dans son cadre (en-tête collé ; page sans défilement horizontal ; 200 lignes, puis « Afficher
   200 lignes de plus ») : n° de ligne, action, fiche (clé et identifiant), détail (changements « Champ :
   avant → après », doublon « même intervention que la ligne n / l'OT … », raisons ; refus en rouge), et
   case « Importer quand même » (`input.import-quand-meme`, non cochée) sur chaque doublon supposé.
5. **Importer** : bilan par table (`#import-bilan`, rappel de la sauvegarde « Avant import » ou, en démo,
   de l'instantané) ; bouton `#import-importer` désactivé tant qu'il n'y a rien à créer ni à mettre à jour ;
   progression table par table (`#import-progression`, d'après les événements « changement » locaux de
   `Donnees` : `Import.importer` n'a pas de rappel de progression) ; résultat (`#import-resultat`, une ligne
   par table, nom de la sauvegarde `#import-sauvegarde`) ; « Annuler cet import » (`#import-annuler`, après
   confirmation) et « Importer d'autres données » (`#import-recommencer`). Aperçu périmé → retour à l'étape
   4 avec le nouvel aperçu et un bandeau ; résultat partiel avec au moins une table écrite → « L'import
   s'est arrêté en cours de route… » et « Annuler cet import » ; autre erreur (aucune table écrite) →
   « Rien n'a été importé », bouton réactivé.

Rien n'est écrit dans la base avant l'étape 5 (la seule écriture des étapes 1 à 4 est la mémoire du poste,
§18.4) ; les CSV restent identiques à l'octet. PC 1440 px et téléphone 375 px : étapes lisibles, zones
tactiles ≥ 48 px.

### 18.10 Tests du lot 5
Fichiers d'essai `tests/fixtures/import/` écrits par `outils/generer_fixtures_import.py` (déterministe ;
`LISEZMOI.md` généré : pièges, choix retenus, ordre d'import sur une base vide) : liste d'équipements d'un
atelier `equipements.xlsx` (écrit par Python sans SheetJS : titre au-dessus de l'en-tête, colonnes dans le
désordre, noms variés, repères à zéros en tête, dates Excel 1900, un équipement créé puis cité comme parent plus bas,
un parent introuvable), la même en `.ods` et en `.xls` (écrit par SheetJS dans Chromium au moment de la génération) ;
`articles.csv` (Windows-1252, `;`), `fournisseurs.tsv` et `techniciens.tsv` (collage tabulé),
`habilitations.csv`, `codes.csv`, `compteurs.csv`, `controles.csv`, `gammes.xlsx` (une ligne par
opération), `historique.csv` d'une autre GMAO (UTF-8, `,`, « N° OT », JJ/MM/AAAA, durées manquantes,
doublons sûrs et supposés) ; fichiers piégés `trop_de_lignes.csv`, `limite_de_lignes.csv` (accepté),
`chiffre.xlsx`, `vide.csv`, `lignes_vides.csv`, `sans_entete.csv`, `cellules_repetees.ods`. Fichiers de
test : `test_import_socle.py`, `test_fixtures_import.py`, `test_import_lecture.py`, `test_import_regles.py`
(avec un **calcul Python indépendant** de l'aperçu attendu sur ces fichiers), `test_import_historique.py`,
`test_import_ecritures.py` (démo, serveur, dossier simulé, deux postes), `test_import_ia.py` (faux
fournisseur : rien d'autre que les titres ne part), `test_import_modeles.py`, `test_import_ecrans.py`, la
recette `test_recette_lot5.py` (T86) ; `test_regles_indicateurs.py` (ajustement 3), `test_depot.py`
(SheetJS, ordre), `test_performance.py` (T86 ; D89 : 5 000 lignes, aperçu < 3 s, écriture < 5 s ; chargement de
Prévo sans SheetJS) ; `test_fiche_csv.py` couvre aussi le §4 de la fiche technique (colonnes reconnues à
l'import). Vrai Excel (T86), seulement avec `PREVO_TEST_EXCEL=1` : `test_excel_reel.py` enregistre la liste
du parc en `.xls` par Excel et vérifie que la lecture et l'aperçu sont ceux du `.xlsx`.

### 18.11 Points ouverts à la fin du lot
- Contrôles des formulaires à l'import : **tranché** par Nicolas le 2026-10-22, appliqués (T92, §18.5).
- Ajustement 3 appliqué à tous les OT (§18.6) : **confirmé** par Nicolas le 2026-10-22.
- Choix de T85 (§18.4 et §18.9 : champs libres envoyés à l'IA, colonnes « à confirmer » importées
  telles quelles, mémoire écrite au « Continuer ») : **gardés** par Nicolas le 2026-10-22.
- Petites dettes notées : le test « ligne d'en-tête sans titre » est recopié de `import-lecture.js` dans
  `import-ecrans.js` (une fonction `Import.enteteValable` l'éviterait) ; la progression suit les
  événements de `Donnees` faute d'un rappel `progression` dans `Import.importer`.

## 19. Accueil du responsable « bento » (T89–T90, après le lot 5)

Demande de Nicolas (`BRIEF_design_accueil.md`, non versionné) : seul l'accueil du **responsable** change,
plus le menu latéral, la barre du bas et le toast ; accueils du technicien et du demandeur et écrans de
travail inchangés. Mêmes calculs qu'avant (`Accueil.calculerCompteurs`, `Suggestions.ouvertes`).
- **Fichiers** : `accueil-bento.js` (complète `Accueil` : `afficherResponsable`, `choisirEnPremier`,
  `momentDeLaJournee`, `phraseDemandes`, `ligneSecondaire`) chargé **juste après `accueil.js`**
  (`ORDRE_MODULES` suit) ; `accueil.js` expose `Accueil.interne` pour lui seul. Mise en page dans
  `css/modules/accueil.css` ; jetons du brief (`--fond-synthese`, `--ombre-synthese`, `--ombre-tuile`,
  `--fond-barre-verre`, `--rayon-tuile`, `--rayon-tuile-grande`) et leurs nuances dans `css/style.css`,
  dans les deux thèmes.
- **Grille** `#bento` (classe gardée `accueil-instruments`, point d'accroche des tests) : 12 colonnes
  internes (les 6 du brief), écart 16 px ; 2 colonnes au téléphone. Synthèse (`#bento-synthese`), « À
  traiter en premier » (`#bento-premier`, `data-type` = `securite` | `p1` | `retard` | `preventif`, absente
  s'il n'y a rien), 4 compteurs (`a.bento-compteur`), tuile du rapport (`#bandeau-rapport`, rendue par
  **`Rapport.tuileAccueil()`**, qui remplace `Rapport.bandeauAccueil()` du §15.10 ; mêmes boutons
  `data-action`), listes `#bento-demandes` (pas au téléphone) et `#bento-retards`, 3 tuiles « à surveiller »
  (`.bento-surveiller` ; « Contrôles et habilitations » réunit les deux liens du lot 3). Chaque tuile mène à
  la liste filtrée de l'indicateur d'avant. Alerte « Contrôle de la base » et `#carte-import-accueil` entre
  l'en-tête et la grille, `#carte-connexion` sous la grille.
- **Chiffres** : le texte du DOM est la valeur ; le dessin est un compteur CSS mené par la propriété
  enregistrée `--compte`, qui défile de 0 à la valeur à l'ouverture de l'écran (pas à un réaffichage).
  `prefers-reduced-motion: reduce` coupe tout (défilement, halos, points, soulèvement au survol).
- **Coque** : `App.definirTitreMobile(titre, détail)` (« Bonjour » et la date dans l'en-tête mobile) ;
  bandeau démo de la coque masqué sur cet accueil seulement (la mention est dans son en-tête) ; en démo,
  plus de toast « n OT préventif(s) généré(s) » à l'ouverture (la génération reste) ; toast en bulle en
  bas à droite, 3 s (4,5 s en alerte, 7 s en erreur).
- Tests : `tests/test_bento.py`.

## 20. Contrat du lot 6 — wiki de maintenance (refonte ; CDC validé le 2026-10-22 : D93–D112 ; refonte 2, l'encyclopédie, validée le 2026-10-23 : D113–D115, §20.12)

Écrit avant le code de la refonte ; relu et aligné sur le code à la fin du lot (« écart retenu » avec sa
raison, ou « précision »). Il remplace le contrat de la première version du lot 6 (une synthèse IA par
équipement, commit 53c7efd), dont restent : la couche calculée de l'équipement, le vocabulaire de la
sécurité et les contrôles de citation, la recherche BM25 et ses champs posés dans l'OT et la DI. Le
principe est celui du LLM Wiki : des **sources** (les OT clôturés administrativement, jamais modifiés par le
wiki), des **pages** (le texte du wiki) et des **règles** (la consigne de l'IA et les contrôles en code) ;
trois opérations : **ingérer**, **consulter**, **contrôler**. Règles de fond : **deux couches** (D94) — tout
ce qui est calculé l'est sans IA et reste séparé du texte ; **une phrase cite au moins un OT, jamais une
autre page** ; **l'IA ajoute et précise, elle ne retire rien** (une contradiction est signalée, jamais
écrasée) ; **jamais de consigne de sécurité dans le texte du wiki** (D97) ; **seul le responsable valide**.
Version de clôture `v1.2.0`.

### 20.1 Socle
- **Révisé par la refonte 2 (T125)** : la liste et l'ordre des modules (`wiki-entites.js`, `wiki-page-ecrans.js`,
  `wiki-sections-ecrans.js`, `wiki-entites-ecrans.js` et `wiki-ecrire-ecrans.js` en plus ; `ORDRE_MODULES` et
  `index.html` font foi), les routes (`#/wiki/<liste>`, `#/wiki/<id>` pour les six types, `#/wiki-ecrire/<id>`) et les
  longueurs (`Wiki.LIMITES` par type et par rubrique ; `phrasesMax` et `motsMax` sont celles d'un savoir-faire) sont
  dans §20.12.
- **Modules** (préfixe `wiki-`, chargés **à la fin** de `js/modules/`, dans cet ordre ; `ORDRE_MODULES`
  suit) : `wiki-regles.js` (1/8, crée `Wiki` : constantes, forme comparable, couche calculée de
  l'équipement — reprise), `wiki-calculs.js` (2/8, couches calculées du composant et du mode, pages
  virtuelles, catalogue), `wiki-texte.js` (3/8, balisage d'une page et contrôles du §20.6),
  `wiki-recherche.js` (4/8, reprise), `wiki-ingestion.js` (5/8, file, pages concernées, requête,
  ordonnanceur, lecture de la réponse), `wiki-journal.js` (6/8, propositions, validation, rejet, écriture à
  la main, contradictions, intégrité), `wiki-ecrans.js` (7/8, index, page, champ de recherche),
  `wiki-journal-ecrans.js` (8/8, journal, traitement de la file, écriture à la main, contrôle du wiki).
  **Retirés** : `wiki-ecritures.js` et `wiki-synthese.js` de la première version, la consigne
  `syntheseWiki` et `Wiki.controlerSynthese`. Feuilles `css/modules/wiki.css` et
  `css/modules/wiki-journal.css` (écrans du responsable). 700 lignes au plus par fichier.
- **Routes**, ouvertes aux trois profils sauf mention : `#/wiki` (index), `#/wiki/<id>` (une page ; `id` =
  identifiant d'équipement `EQ-…`, d'article `ART-…` ou de page `WP-…`), `#/wiki-journal` (**responsable
  seulement**). Entrée de menu et icône `wiki` inchangées (ordre 42).
- **Constantes** `Wiki.SEUILS` (D100), documentées dans le guide : `{ pagesCreeesMax: 3, phrasesMax: 30,
  motsMax: 600, relancesMax: 1, pagesEnvoyeesMax: 8, catalogueMax: 400, agentsSimultanes: 5, astuceMax: 500,
  otMinimum: 5, recidiveJours: 30, dernieres: 10, symptomesMax: 5, contradictionAncienneJours: 30,
  demoAValiderJours: 14 }` (**révision de Nicolas du 2026-10-23** : 30 phrases et 600 mots au lieu de 12 et
  250, une relance avec la raison du refus, sous-pages au-delà — §20.4, §20.5, §20.6).
- **Ajouts hors du wiki** (interface gelée, CDC point 11) : le lien « Wiki de cet équipement »
  (`#lien-wiki-equipement`, déjà là) ; un lien « Wiki de cet article » (`#lien-wiki-article`) en tête de la
  fiche article ; le champ « Astuce pour la prochaine fois » (§20.2, §20.9) ; à la clôture administrative,
  le message « OT ajouté à la file du wiki » ; les champs de recherche de l'OT et de la DI (déjà là). La
  carte « Résumé de l'historique (IA) » de la fiche équipement et la consigne `resumeHistorique` (§17.3,
  §17.5 point 5) sont **retirées** ; le faux fournisseur et les tests du lot 4 suivent.

### 20.2 Format 3 : `wiki_pages`, `wiki_journal`, `ordres_travail.astuce` (D95, D110)
- **Révisé par la refonte 2 (T125)** : le type `mode` est retiré (une panne est calculée ; une ligne `mode` restante
  est signalée « type de page retiré » par le contrôle du wiki et s'archive) ; les sous-pages ne valent que pour les
  savoir-faire ; `cause_code` ne sert plus à une page nouvelle ; voir §20.12.
- `Schema.version` = **3** ; **24 tables** : les 22 du format 2 puis `wiki_pages` et `wiki_journal`
  (attribut `depuisVersion: 3`, fichiers absents = tables vides, créés à la première écriture). La table
  `wiki_syntheses` de la première version disparaît du schéma ; une base de développement qui a encore
  `wiki_syntheses.csv` ne le lit plus et ne le supprime pas.
- **`ordres_travail.astuce`** : `depuisVersion(3, champ('astuce', 'texte_long', 'Astuce pour la prochaine
  fois'))`, en fin de table ; facultatif, `astuceMax` caractères au plus ; colonne absente → problème `info`
  et valeur vide (§4, mécanisme du format 2).
- **`wiki_pages`** (identifiant `WP-0001`, `{ prefixe: 'WP-', chiffres: 4, annuel: false }`) : seules les
  pages qui ont un texte validé ont une ligne ; les pages d'équipement et d'article existent toujours,
  calculées (§20.3).

  | Champ | Type | Règle |
  | --- | --- | --- |
  | `id` | identifiant | |
  | `type` | choix `équipement`, `composant`, `mode`, `savoir-faire` | obligatoire |
  | `titre` | texte | obligatoire ; imposé par Prévo pour une page ancrée (équipement : « <repère> — <désignation> » ; article : sa désignation) |
  | `cle` | texte | forme comparable du titre (§20.6) ; unique parmi les pages actives |
  | `equipement_id` | `ref` → `equipements` | page d'équipement, ou savoir-faire rattaché à un équipement |
  | `article_id` | `ref` → `articles` | composant ancré, ou savoir-faire rattaché à un article |
  | `cause_code` | code cause | mode ancré (facultatif) |
  | `rattache_a` | `ref` → `wiki_pages` | savoir-faire rattaché à une page de composant libre ; **sous-page** : sa page mère, de même type (§20.4) |
  | `texte` | `texte_long` | balisage du §20.4, contrôlé (§20.6) |
  | `ot_cites` | texte | identifiants séparés par « ; », tirés du texte |
  | `liens` | texte | identifiants des pages liées, séparés par « ; », tirés du texte |
  | `version` | entier | +1 à chaque changement appliqué |
  | `origine` | choix `IA`, `manuel`, `IA et manuel` | |
  | `modele` | texte | modèle de la dernière proposition IA appliquée |
  | `derniere_entree` | `ref` → `wiki_journal` | dernière entrée appliquée (rattrapage, §20.7) |
  | `valide_par`, `valide_le` | texte, `date_heure` | dernier changement appliqué |
  | `cree_le`, `modifie_le` | `date_heure` | |
  | `statut` | choix `active`, `archivée` | |

- **`wiki_journal`** (identifiant `WJ-00001`, 5 chiffres) : une ligne par OT ingéré, par écriture à la main
  et par décision sur une contradiction.

  | Champ | Type | Règle |
  | --- | --- | --- |
  | `id` | identifiant | |
  | `nature` | choix `ingestion`, `manuel`, `décision` | |
  | `ot_id` | `ref` → `ordres_travail` | ingestion |
  | `date_intervention` | `date_heure` | copie de `date_fin` de l'OT (ordre de la file, D111) |
  | `statut` | choix `en file`, `à valider`, `validée`, `rejetée`, `à refaire`, `refusée`, `rien à ajouter`, `appliquée` | |
  | `anterieure` | booléen | D111 |
  | `ordre` | entier | rang de traitement (enchaînement des propositions, D105) |
  | `pages` | texte | clés des pages concernées (§20.5), séparées par « ; » |
  | `changements` | `texte_long` | JSON `[{ page, cle, type, titre, creation, version_avant, avant, apres }]` |
  | `contradictions` | `texte_long` | JSON `[{ page, phrase, observation, ot, statut, decision, decide_par, decide_le }]` |
  | `raisons` | `texte_long` | raisons d'un refus, une par ligne |
  | `modele` | texte | modèle réellement utilisé |
  | `essais` | entier | |
  | `cree_le`, `traite_le` | `date_heure` | |
  | `decide_par`, `decide_le` | texte, `date_heure` | qui a décidé, et quand |
  | `motif` | `texte_long` | motif d'un rejet ; « rejoué : page créée entre-temps » (D112) |

- **Passage au format 3** : au lot 6, `Donnees.mettreAJourVersionSchema()` (§5.6) tel quel, motif `avant-format-v3`
  (déjà dans `MOTIFS_SAUVEGARDE` de `serveur.py` et `js/stockage-dossier.js`) ; aucun fichier réécrit sauf
  `parametres.csv` ; une base au format 1 passe directement au format 3. Une base déjà en version 3 (première
  version du lot, jamais publiée) n'a rien à faire. « Créer une base vide » et la démo portent
  `version_schema` = 3. `serveur.py` : `TABLES` à 24 (test de cohérence avec `js/schema.js`).
  Depuis le chantier « socle de données » (D167, D168), le passage se fait étape par étape (1 → 2 → 3, colonnes
  ajoutées en fin de table, une ligne de journal par étape), par le serveur à son démarrage en mode serveur et par
  `Donnees.migrerAuFormatCourant()` à l'ouverture en mode dossier : §5.6 et [FORMAT.md](FORMAT.md) §6.
- `Donnees.problemes()` : lien vers une page inexistante ou archivée, OT cité inexistant, deux pages actives
  de même `cle`, entrée « validée » dont les changements ne sont pas dans les pages (`attention`) ; page
  active sans OT cité, contradiction ouverte depuis plus de `contradictionAncienneJours` (`info`).

### 20.3 Pages et couches calculées (`wiki-regles.js`, `wiki-calculs.js` ; sans IA, sans écriture)
- **Révisé par la refonte 2 (T125)** : l'écran d'une page lit `Wiki.entite` (six types, visibilité D114,
  `wiki-entites.js`) ; `Wiki.page` reste pour l'écriture à la main et le journal ; le mode ancré disparaît ; l'en-tête
  d'un savoir-faire est la liste de ses machines (D116) ; voir §20.12.
- **`Wiki.page(id, { maintenant, profil })`** → `{ id, type, titre, calcul, texte, origine, liens, retours,
  contradictions, enAttente }` : `calcul` selon le type (ci-dessous) ; `texte` = la ligne de `wiki_pages`
  (état **validé**) ou vide ; `retours` = pages actives dont `liens` contient cette page ; `contradictions`
  = celles qui restent ouvertes ; `enAttente` = propositions « à valider » qui touchent la page
  (responsable seulement, sinon vide).
- **Équipement** (`EQ-…`) : la couche de la première version, inchangée — `consignation` telle quelle,
  `pannes` (symptômes, causes avec `CausesFrequentes.fourchette`, remèdes, récidives à `recidiveJours`),
  `pieces`, `dernieres`, `memeModele` — sans `synthese` ni `peutProposer`.
- **Composant ancré** (`ART-…`, ou page `composant` avec `article_id`) : `article` (référence, désignation,
  fabricant, référence fabricant, emplacement, stock) ; `montage` = équipements de `article_equipement`
  (quantité) et équipements où l'article a été consommé ; `consommations` = OT clôturés où la quantité nette
  sortie (sorties − retours, §20.3 de la première version) est positive, `{ otId, date, equipementId,
  quantite }` ; `remplacements` par équipement `{ equipementId, nombre, intervalleMedianJours }` (médiane des
  écarts entre dates d'intervention successives ; `null` sous 2 remplacements). Composant libre : `calcul`
  = `null`, l'écran affiche « Pas d'article au magasin ».
- **Mode ancré** (`cause_code`) : `cause` (code, libellé), `cas` (OT correctifs clôturés de cette cause),
  `equipements` `[{ equipementId, cas }]`, `remedes` `[{ code, libelle, fois }]`. Mode libre : `calcul` =
  `null`.
- **Savoir-faire** : `entete` posé par Prévo — la consignation de l'équipement rattaché, telle quelle (ou,
  pour un composant, les liens vers les équipements où il est monté) et la phrase fixe « Ce savoir-faire ne
  remplace pas la consignation de l'équipement ». Jamais de texte d'IA dans `entete`.
- **Sous-page** (§20.4) : `calcul` = `null` ; `mere` = `{ id, titre }` ; pour une sous-page d'équipement,
  `entete` = la consignation de l'équipement de sa mère, telle quelle, et la phrase fixe « Cette page ne
  remplace pas la consignation de l'équipement » (comme un savoir-faire, CS98). Une page mère porte
  `sousPages` = `[{ id, titre }]` (actives, par titre).
- **Catalogue** `Wiki.catalogue()` → `[{ id, titre, type }]` de toutes les pages actives (sous-pages
  comprises) et des pages calculées d'équipement et d'article, `catalogueMax` au plus (les pages qui ont un
  texte d'abord).
- Un calcul Python indépendant (`tests/calcul_wiki.py`, étendu) refait `montage`, `consommations`,
  `remplacements`, `cas`, `equipements` et `remedes` sur la démo et sur une base d'essai (CS97).

### 20.4 Texte d'une page : balisage et rubriques
- Lignes **`## <Rubrique>`** puis **`- <phrase> [OT-AAAA-NNNN] [OT-…]`** ; un lien s'écrit **`[[<titre exact
  d'une page>]]`** dans une phrase ; rien d'autre (une ligne vide est ignorée). Rubriques vides omises,
  ordre fixe par type (`Wiki.RUBRIQUES`) :
  - équipement : « En bref », « Astuces » (refonte 2, D117 ; les anciennes rubriques « Ce qui revient », « Ce qui a
    réglé le problème », « À surveiller » sont signalées « anciennes rubriques » par le contrôle du wiki) ;
  - composant : « À quoi il sert » (refonte 2 ; avant : « Défaillances », « Signes d'usure », « Montage et
    remplacement », « Équivalences ») ;
  - mode : type retiré par la refonte 2 (§20.12) ;
  - savoir-faire : « Quand le faire », « Étapes », « Pièces et outillage », « Pièges », « Particularités par machine »
    (D116, T141 : une phrase par machine, avec son lien `[[repère — nom]]`, pour ce qui change pour elle).
  Rubrique **réécrite en entier** à chaque OT (D117, T142) : `Wiki.RUBRIQUES_REECRITES` = `{ équipement: ['En bref'] }`
  (§20.6 : hors du non-retrait).
- `Wiki.lireTexte(texte)` → `{ rubriques: [{ nom, phrases: [{ texte, ot, liens }] }], erreurs }` ;
  `Wiki.ecrireTexte(rubriques, type)` → le balisage. Affichage par `textContent` (liens et OT cités en
  éléments construits), jamais en HTML.
- **Identité d'une phrase** : forme comparable de son texte sans citations ni crochets de lien.
- **Taille d'une page** `Wiki.mesurerTexte(texte)` → `{ phrases, mots }` : mots des phrases sans citations
  et des noms de rubriques ; la mesure des contrôles (§20.6) et de l'en-tête des pages envoyées (§20.5).
- **Sous-pages** (D96, D100, Nicolas, 2026-10-23 ; **refonte 2 : pour les savoir-faire seulement**, §20.12). Une page
  qui dépasserait `phrasesMax` phrases ou
  `motsMax` mots est découpée en sous-pages liées. Une sous-page a le **type de sa page mère** et ses
  rubriques ; `rattache_a` = l'identifiant de la ligne de sa mère ; **aucun ancrage propre**
  (`equipement_id`, `article_id`, `cause_code` vides : sa clé est `WP:<id>`, jamais celle de sa mère) ; un
  seul niveau (la mère n'est pas une sous-page). Une page est une sous-page si et seulement si `rattache_a`
  désigne une page **de même type** (un savoir-faire rattaché à un équipement ou à un composant n'en est pas
  une). Titre « <repère de l'équipement, ou titre de la mère> — <sujet> » (refonte 2 : « <titre du savoir-faire> — <sujet> »,
  ex. « Remplacer une garniture mécanique — étapes détaillées »).
  L'IA y déplace les phrases d'un même sujet, telles quelles ou regroupées avec tous leurs OT ; la mère garde
  une phrase de renvoi `[[titre de la sous-page]]` qui cite les OT des phrases déplacées : chaque phrase
  déplacée y est « reprise » (§20.6), rien n'est retiré.

### 20.5 Ingestion (`wiki-ingestion.js`, D104, D111, D112)
- **Révisé par la refonte 2 (T125)** : les pages concernées (plus de `CAUSE:` ni de pages liées depuis la machine ;
  savoir-faire du même geste, D116) et la consigne (« En bref » réécrit en entier, D117 ; seuls des savoir-faire se
  créent ; la constante `ingestionWiki` de `ia-prompts.js` fait foi) sont dans §20.12, qui prime.
- **File** : `Wiki.mettreEnFile(otIds)` crée une entrée `ingestion` « en file » par OT **clôturé
  administrativement** qui n'a pas déjà une entrée `en file`, `à valider`, `validée`, `rien à ajouter` ou
  `refusée` ; appelée **après** le passage réussi à « Clôturé administrativement » (`ordres-ecritures.js`,
  une ligne ; un échec n'annule pas la clôture : message, et l'OT apparaît dans « hors du wiki »).
  `Wiki.horsDuWiki({ equipementId })` → OT clôturés administrativement sans entrée (historique, import du
  lot 5) ; le responsable les ajoute, en tout ou par équipement, après avoir vu leur nombre.
- **Ordre** (D111) : entrées `en file` et `à refaire` triées par `date_intervention` (`date_fin` de l'OT ;
  un OT importé en a toujours une) puis `ot_id` ; jamais par saisie ni par clôture.
- **État proposé** `Wiki.etatPropose()` : pages validées, puis les changements des entrées « à valider »
  appliqués dans l'ordre de `ordre` (D105). Les requêtes sont construites sur cet état.
- **Pages concernées** `Wiki.pagesConcernees(otId, etat)` (D112) → `{ cles, envoyees }` : `cles` = `EQ:<id>`
  de son équipement, `ART:<id>` de chaque article consommé, `CAUSE:<code>` de sa cause, `WP:<id>` des
  savoir-faire rattachés à cet équipement ou à ces articles, des modes ancrés sur sa cause et des pages liées
  depuis la page de l'équipement, et **les sous-pages de chacune de ces pages, juste après leur mère**
  (2026-10-23) ; `envoyees` = ces pages (texte de l'état proposé, vide si aucun), dans cet ordre de priorité,
  `pagesEnvoyeesMax` au plus. Dans l'état proposé, une sous-page a `rattacheA` = la clé de sa mère et ni
  `equipementId` ni `articleId`. Savoir-faire communs (D116, T141) : voir §20.12.
- **Antériorité** (D111) : `anterieure` = la date d'intervention de l'OT est plus ancienne que celle d'au
  moins un OT cité dans ses pages envoyées (état proposé).
- **Données** `Wiki.donneesIngestion(otId, etat)` (liste blanche, CS99) : `{ ot: { id, dateIntervention, type,
  equipement: { repere, designation, marque, modele }, titre, travail, symptome, cause, remede (libellés),
  compteRendu, astuce, pieces: [{ designation, reference, quantite }], dureeArret, symptomeDI },
  anterieure, pages: [{ titre, type, texte, otDates: [{ id, date }], phrases, mots }], limites: { phrases,
  mots }, catalogue: [{ titre, type }] }` ; **jamais** les noms des techniciens ou des demandeurs, les coûts,
  les documents, les photos. `phrases` et `mots` = `Wiki.mesurerTexte` de la page, `limites` = `phrasesMax`
  et `motsMax` (précision du 2026-10-23 : le modèle ne compte pas ; l'en-tête de chaque page envoyée dit
  « === Page « <titre> » (<type> · N phrases sur P, M mots sur Q) === »).
- **Consigne** `Ia.PROMPTS.ingestionWiki` (`ia-prompts.js`) : première ligne « Fonction : ingestionWiki » ;
  règles communes ; tâche : intégrer cet OT aux pages fournies — modifier une page envoyée en rendant son
  texte complet, ou créer au plus `pagesCreeesMax` pages (refonte 2 : des savoir-faire seulement ; avant : mode, savoir-faire,
  composant sans article) ;
  chaque phrase cite au moins un OT (cet OT ou un OT déjà cité dans les pages) ; ne jamais retirer une
  phrase ni un OT cité (une phrase reformulée garde tous ses OT), hors « En bref », réécrit en entier (D117, §20.12) ; ce qui contredit une phrase existante va
  dans `contradictions`, la phrase reste ; aucune date, aucun nombre absent de l'OT à intégrer ou du texte
  actuel de la page écrite (§20.6) ; aucune fréquence ni aucun comptage ; jamais « cause certaine » ; **les pages savoir-faire s'écrivent d'abord à partir
  de l'astuce** ; aucune consigne de sécurité ; si `anterieure` : « intervention antérieure à des faits déjà
  intégrés », ne jamais présenter cette information comme la plus récente ; « rien à ajouter » si l'OT
  n'apprend rien. Une page est une synthèse, pas un historique ; ses limites sont celles de son en-tête ;
  **une page qui les dépasserait se découpe** : sous-page créée (`action` « creer », `type` de la mère,
  `rattache_a` = titre exact de la mère, titre « <repère ou titre de la mère> — <sujet> »), phrases d'un même
  sujet déplacées, phrase de renvoi dans la mère qui cite leurs OT (§20.4).
- **Relance avec la raison** (D106, Nicolas, 2026-10-23) : une réponse refusée par `Wiki.lireIngestion`
  (§20.6) est redemandée **une fois** (`relancesMax`), par une **requête neuve** : même message système ;
  message utilisateur = le message d'origine, puis « Ta réponse précédente : » et la réponse refusée telle
  quelle, puis « Elle a été refusée par les contrôles de Prévo : » et chaque raison sur sa ligne, puis la
  demande d'une réponse complète corrigée ; rien d'autre (liste blanche, CS99, CS112). Les données de la
  requête portent `relance: { reponse, raisons }`. Une collision (page créée ou changée pendant l'envoi,
  D112) n'est jamais relancée : elle est rejouée.
- **Réponse attendue** (schéma de `Ia.requete`) : `{ rien_a_ajouter, pages: [{ action: 'modifier' | 'creer',
  titre, type, rattache_a, rubriques: [{ rubrique, phrases: [{ texte, ot: [identifiant] }] }] }],
  contradictions: [{ page, phrase, observation, ot: [identifiant] }] }` ; `ot` : `enum` des identifiants
  permis (cet OT et ceux des pages envoyées).
- **Lecture** : `Ia.lireReponse('ingestionWiki', contenu, donnees)` → `verifier` = `Wiki.lireIngestion` :
  mise en forme (§20.4) puis contrôles (§20.6) → `{ changements, contradictions, rien }`, ou
  `IaReponseInvalide` avec les raisons. Une page renvoyée avec le texte qu'elle avait à l'envoi (une fois mis en
  forme) compte comme **non renvoyée** : ni contrôlée ni proposée ; s'il ne reste ni page ni contradiction, la
  réponse vaut « rien à ajouter » (`rien` vrai : aucune proposition vide à valider ; suites de la relecture de T140).
- **Envoi** : `Ia.envoyerRequete(requete, signal)` → `{ contenu, modele }` (nouvelle ; la partie réseau de
  `Ia.demander`, qui l'appelle : même comportement, même autorisation D67, même délai).
- **Ordonnanceur** `Wiki.prochainsEnvois(file, enCours)` (D112) : parcourt la file dans l'ordre ; un OT part
  si moins de `agentsSimultanes` sont en cours et si **aucune de ses `cles`** n'est prise par un OT en cours
  **ni par un OT plus ancien de la file resté en attente**. `Wiki.traiterFile({ appeler, surProgres, signal
  })` : boucle jusqu'à file vide ou arrêt ; `appeler(requete, donnees, signal)` → `{ contenu, modele }`,
  par défaut `Ia.envoyerRequete` (l'outil de la démo en donne un autre, §20.10). Résultat : acceptée → entrée « à
  valider » (`changements`, `contradictions`, `modele`, `anterieure`, `ordre` suivant, `traite_le`) ;
  « rien à ajouter » → statut du même nom ; refusée → **relance avec la raison** (une fois) : acceptée → « à
  valider », `essais` 2, `raisons` = celles du premier refus ; encore refusée → « refusée » avec les `raisons`
  du second refus, `essais` 2 ; collision
  (page libre créée entre-temps, D112) → « en file » à nouveau, `motif` « rejoué : page créée entre-temps » ; savoir-faire
  créé pendant l'envoi et concerné sur le nouvel état (D116) → de même, `motif` « rejoué : pages changées pendant l'envoi » ;
  IA injoignable → arrêt, l'OT reste « en file ».

### 20.6 Contrôles d'une proposition (`wiki-texte.js`, D97, D106, D111)
`Wiki.controlerProposition(proposition, contexte)` → `{ ok, raisons: [texte] }` ; chaque raison nomme la
page. Refus si :
- forme : rubrique hors de `Wiki.RUBRIQUES` du type ; page modifiée qui n'était pas envoyée ; création d'un
  type autre que savoir-faire (refonte 2 ; avant : équipement, ou composant d'un article, sauf comme sous-page) ; savoir-faire sans
  rattachement à une page envoyée ;
- **sous-page** créée (`rattache_a` = une page envoyée de même type ; refonte 2 : un savoir-faire seulement) : sa mère est une sous-page ; sa mère
  n'est pas modifiée par la même proposition, ou ne renvoie pas à elle (`[[titre]]`) ; son titre ne commence
  pas par « <repère de l'équipement de la mère, ou titre de la mère> — » suivi d'un sujet ;
- citations : phrase sans OT ; OT cité hors des OT permis ;
- **non-retrait** : un OT cité avant disparaît de la page ; une phrase existante n'est ni identique ni
  **reprise** (une phrase nouvelle la reprend si elle cite tous ses OT) ; **sauf dans une rubrique réécrite en entier**
  (D117, T142, `Wiki.RUBRIQUES_REECRITES` : « En bref ») : ses phrases et ses OT d'avant peuvent partir, et ses phrases
  d'après ne gardent pas celles d'une autre rubrique du type (une phrase d'« Astuces » passée dans « En bref » est
  retirée) ; une phrase d'une ancienne rubrique (hors du type) peut s'y réécrire ; **toutes** ses phrases sont contrôlées
  comme nouvelles (citations, nombres, comptage, dates, nouveauté, sécurité, liens, longueurs) ; une contradiction peut
  viser l'une de ses phrases ;
- **nombres** : un nombre (chiffres, virgule ou point) d'une phrase nouvelle ou reprise, ou du titre d'une page
  créée, absent du texte de référence — le texte de l'OT ingéré (tous les champs envoyés, sauf sa date) et le texte
  précédent de la page (rien pour une page créée ; le texte et le titre de sa mère pour une sous-page créée) ; les
  citations, les numéros d'OT et le titre d'un lien `[[…]]` ne comptent pas (ni dans la phrase ni dans le texte de
  référence) ; la raison dit ce texte de référence :
  « absent de l'OT intégré et du texte d'avant de cette page » (page modifiée), « absent de l'OT intégré, seule
  source des nombres d'une page créée » (page créée, et « du titre absent … » pour son titre), « absent de l'OT
  intégré, du texte et du titre de sa page mère » (sous-page créée) ; à la main : « absent des OT cités » (T140) ;
- **comptage** : « <nombre ou nombre en lettres> fois | OT | interventions | pannes | cas | remplacements » ;
- **dates** : année 19xx ou 20xx hors citation, nom de mois, date en chiffres ;
- **nouveauté** (D111) : pour un OT `anterieure`, une phrase nouvelle ou reprise dont l'OT cité le plus récent
  (date d'intervention) est cet OT et qui emploie `Wiki.VOCABULAIRE_NOUVEAUTE` (désormais, dorénavant,
  maintenant, actuellement, à présent, aujourd'hui, récemment, dernièrement, depuis peu, le plus récent,
  la plus récente, dernier, dernière, derniers, dernières) ;
- sécurité : un terme de `Wiki.VOCABULAIRE_SECURITE` (liste et règle de la première version) ;
- longueurs : plus de `phrasesMax` phrases ou de `motsMax` mots (`Wiki.mesurerTexte`) dans une page ; plus
  de `pagesCreeesMax` pages créées (sous-pages comprises) ;
- liens : `[[titre]]` qui n'est ni au catalogue ni créé par la proposition ;
- titres : titre créé dont la forme de recherche (mots vides retirés, pluriel simple, §20.8) égale celle
  d'une page existante (« titre trop proche ») ; **même geste** (D116) : savoir-faire créé (hors sous-page) dont le
  titre contient tout l'organe d'un savoir-faire connu (catalogue ou envoyé, hors sous-pages : son titre sans le premier
  mot, 2 mots au moins) — la raison dit « complète-le » s'il est envoyé, sinon « mets un lien [[…]] » ; l'en-tête
  d'une rubrique réécrite donne une cible sous sa limite (« à réécrire en entier en 45 mots environ » pour 60) ;
- contradictions : `phrase` qui n'est pas une phrase existante de la page ; `ot` autre que l'OT ingéré.

Une page que l'IA renvoie inchangée n'est pas contrôlée : `Wiki.lireIngestion` la retire avant (§20.5, lecture).

Écriture à la main (`contexte.manuel`) : mêmes contrôles, sauf le non-retrait (rubrique réécrite comprise : rien ne change,
une phrase gardée telle quelle n'est pas recontrôlée) ; les OT permis sont tous les
OT clôturés ; pour les nombres, le texte de référence est celui des OT cités, plus le texte précédent de la page
(et, pour une sous-page, le texte et le titre de sa mère).

### 20.7 Journal, validation, contradictions, écriture à la main (`wiki-journal.js`)
Toutes les écritures par `Donnees.modifier` (contrôle de version, journal général), **responsable
seulement** (même refus que les écrans réservés) :
- **`Wiki.valider(ids)`** : dans l'ordre de `ordre` ; refusé si une entrée « à valider » plus ancienne touche
  une même page (elle change une page sur laquelle l'entrée a été construite, ou crée une page vers laquelle
  l'entrée fait un lien — précision du 2026-10-23 : un lien vers une page qu'elle ne fait que modifier ne compte
  pas, la page reste si elle est rejetée ; même règle pour la cascade « à refaire »). Pour chacune : (1) **une** écriture de `wiki_pages` — chaque page du changement doit avoir
  `version` = `version_avant` (sinon l'entrée passe « à refaire ») ; texte, `ot_cites`, `liens`, `version` +
  1, `origine`, `modele`, `derniere_entree`, `valide_par`, `valide_le` ; une sous-page créée reçoit
  `rattache_a` = l'identifiant de la ligne de sa mère (créée d'abord si la mère n'en avait pas), jamais
  `equipement_id` ni `article_id` ; (2) l'entrée passe « validée »
  (`decide_par`, `decide_le`). Si (2) échoue, **rattrapage** au prochain affichage : une entrée « à valider »
  dont l'identifiant est le `derniere_entree` de ses pages est marquée « validée ».
- **`Wiki.rejeter(id, motif)`** : « rejetée » ; les entrées « à valider » suivantes qui touchent une même page
  passent « à refaire » (leurs changements sont abandonnés, leur OT est retraité sur le nouvel état) ;
  `Wiki.remettreEnFile(id)` relance un OT rejeté ou refusé.
- **`Wiki.ecrire({ pageId | nouvelle }, texte)`** : contrôles §20.6 (`manuel`) ; page écrite (`origine` mise
  à jour) et entrée `manuel` « appliquée » avec avant et après ; les entrées « à valider » qui touchent la
  page passent « à refaire ». Créer une page (refonte 2 : un savoir-faire seulement, sous-page comprise) et archiver une page passent par là.
- **`Wiki.trancher(entreeId, rang, decision, note)`** : `decision` ∈ `ancien`, `nouveau`, `les deux` ; la
  contradiction est fermée (`decision`, `decide_par`, `decide_le`) et une entrée `décision` « appliquée » la
  trace ; `nouveau` ouvre ensuite l'écriture à la main de la page. Une contradiction venue d'un OT
  `anterieure` est présentée comme « observation antérieure aux faits de la page » (D107).
- **Visibilité** : pages validées et encadré « À trancher » pour tous les profils (boutons au responsable) ;
  propositions, journal, file : responsable seulement.
- **Intégrité** `Wiki.verifierIntegrite()` → `{ ok, ecarts }` : pour chaque page, les entrées appliquées dans
  l'ordre de `ordre` forment une chaîne (l'« avant » de chacune est l'« après » de la précédente ; le texte
  de la page est l'« après » de la dernière) ; les OT intégrés à une page le sont par date d'intervention
  croissante, sauf les entrées `anterieure` ; jamais deux entrées d'un même passage en cours avec une page
  commune (CS111).

### 20.8 Recherche (`wiki-recherche.js`, sans IA, D99)
Comme dans la première version (forme comparable, mots vides, pluriel simple, `Wiki.LEXIQUE`, BM25, portées
équipement → même marque et modèle → parc, extraits surlignés, aucun appel réseau), avec : l'**astuce** dans
le document de chaque OT clôturé ; les **pages validées** (titre et texte, `type` = `page`, mènent à la page)
à la place des synthèses ; index refait quand `ordres_travail`, `demandes`, `codes_defaillance` ou
`wiki_pages` changent.
- **Précision (refonte 2, T125)** : la recherche de l'accueil `#/wiki` trouve d'abord les entités par leur nom
  (`Wiki.chercherEntites`, visibilité D114), puis les OT clôturés et les textes ; le champ « Chercher dans
  l'historique » reste dans l'onglet Préparation de l'OT et « Déjà vu sur cette machine ? » dans la saisie d'une DI ;
  la page d'une machine n'a plus de champ de recherche.

### 20.9 Écrans (`wiki-ecrans.js`, `wiki-journal-ecrans.js`)
- **Révisé par la refonte 2 (T125)** : l'accueil `#/wiki` et la page `#/wiki/<id>` sont ceux de §20.12 (encyclopédie,
  petits numéros, fiche des faits) ; l'écriture à la main et le contrôle du wiki sont dans `wiki-ecrire-ecrans.js` ; le
  contrôle du wiki signale aussi « anciennes rubriques » et « types de page retirés » ; le journal, « Traiter la
  file » et le champ « Astuce pour la prochaine fois » valent tels quels.
- **`#/wiki`** : recherche (portée parc) ; quatre sections — Équipements, Composants, Modes de défaillance,
  Savoir-faire — avec leur nombre de pages, chaque page avec son titre et son nombre d'OT cités ; une
  sous-page est dans la section de son type, comme une page. Au
  responsable, en tête : « À valider », « Contradictions ouvertes », « En file » (bouton « Traiter la
  file »), « En échec », « Hors du wiki » (bouton « Ajouter à la file »), « Contrôle du wiki » (D108), chacun
  avec son nombre et son lien.
- **`#/wiki/<id>`**, de haut en bas : en-tête (type, titre, lien vers la fiche) ; pour un savoir-faire,
  l'`entete` du §20.3 ; la **couche calculée** ; le **texte** par rubrique (OT cités en liens, sans lien pour
  le demandeur ; liens vers les pages), précédé du bandeau d'origine « Rédigé avec l'IA (<modèle>) à partir
  des OT cités — validé par <nom> le <date> » ou « Écrit par <nom> le <date> » ; l'encadré **« À
  trancher »** ; **« Pages qui renvoient ici »** ; au responsable : « Modifier », propositions en attente sur
  cette page. **Sous-page** : sous le titre, « Sous-page de <mère> » (lien) ; pour un équipement, l'`entete`
  (consignation) en tête ; pas de couche calculée. **Page mère** : « Sous-pages » (liens), après le texte.
- **`#/wiki-journal`** (responsable) : les entrées par statut (à valider d'abord, puis refusées, puis
  toutes) ; pour une proposition : OT (lien), date d'intervention, « intervention antérieure » s'il y a lieu,
  modèle, « Acceptée à la relance, après le refus : <raisons> » s'il y a lieu (D106) ; **contradictions en
  tête** ; par page, les **changements** : phrases identiques repliées, phrases
  nouvelles surlignées, phrases reprises avec l'ancienne forme barrée ; pages créées en entier ; boutons
  **Valider**, **Rejeter** (motif), cases à cocher et « Valider les propositions sélectionnées » (sans
  contradiction). « Traiter la file » : progression (en cours, au plus `agentsSimultanes` ; restants ;
  refusées), **Arrêter** (les envois en cours finissent, rien d'autre ne part) ; version web : message du lot
  4. Écriture à la main : zone de texte du balisage, aide, contrôles à l'enregistrement. **Contrôle du
  wiki** (D108) : liens cassés, pages orphelines, pages sans OT cité, titres trop proches, pages trop
  longues, contradictions anciennes, ancrages disparus (dont la mère d'une sous-page archivée ou absente ;
  une sous-page n'a pas d'ancrage propre et n'est pas « disparue » pour autant) — calculé à l'ouverture,
  rien corrigé tout seul.
- **OT** : champ « Astuce pour la prochaine fois » dans l'onglet Compte rendu, sous le compte rendu, mêmes
  règles d'édition que lui (aide : « Ce qui vous aurait fait gagner du temps. Les consignes de sécurité
  restent dans la consignation de l'équipement. ») ; montré sur l'OT clôturé ; jamais exigé (RG4 inchangée).
- Design : style actuel, 1440 et 375 px sans défilement horizontal, zones tactiles ≥ 48 px, contrastes AA
  (CS106).

### 20.10 Démo (D98, D109, D110, D112)
- **Générateur** (`outils/generer_demo.py`) : un générateur à part (`GRAINE_LOT6`) ajoute des **astuces** à
  une partie des OT correctifs (textes écrits dans les scénarios, comme les comptes rendus) et **deux OT de
  scénario** à la fin de l'historique, clôturés administrativement, qui contredisent ce que l'atelier
  croyait (PO-02 : la fuite revient, la cause trouvée est le désalignement de l'accouplement ; un second sur
  un autre équipement). Le reste du jeu ne change pas, sauf la colonne `astuce` et les numéros d'OT suivants.
  Les tables du wiki viennent des fichiers figés **`outils/demo_wiki_pages.csv`** et
  **`outils/demo_wiki_journal.csv`** (versionnés), copiés dans `donnees/demo/` et `js/demo-donnees.js` sans
  jamais être régénérés, **pour la démo standard seulement** (13 mois, sans `--volume` : une autre durée
  d'historique ou le jeu de charge garde les tables du wiki vides, avec un message, T122) ; contrôle : OT cités et
  pages liées existants (arrêt sinon) ; deux exécutions donnent des fichiers identiques à l'octet ; le décalage des
  dates (§11) s'applique aux champs date du journal et des pages. Dans `js/demo-donnees.js`, une table du wiki est
  écrite **par morceaux** quand c'est plus court (coupée après chaque fin de ligne, `\n` du JSON et `""`, et avant
  chaque citation ; morceaux distincts écrits une fois, puis leur ordre, recollés au chargement : même texte) ; le
  générateur s'arrête, sans rien écrire, si le fichier dépasserait 1 Mo (CS105 ; wiki de la passe 6 : 1,32 Mo en
  chaînes, 0,64 Mo par morceaux).
- **Fabrication** `py outils/wiki_demo.py fabriquer [--agents 5] [--limite N | --suite]` : démo **sans wiki** ouverte dans Chromium
  (Playwright, horloge à la date de référence) ; les 227 OT clôturés administrativement mis en file
  (`Wiki.mettreEnFile`) ; **`Wiki.traiterFile`** de Prévo avec un `appeler` relié à Python
  (`expose_function`) qui lance, pour chaque requête, **un agent neuf** :
  `claude -p --model sonnet --tools "" --system-prompt <message système de la requête> --setting-sources ""
  --strict-mcp-config --no-session-persistence --disable-slash-commands --output-format json`, avec le
  message utilisateur de la requête sur l'entrée standard, **octet pour octet**. **Claude Sonnet
  seulement** : jamais Ollama, qwen ni modèle local. Pour chaque appel, la trace
  (`.chantier/wiki-demo/chaine/<OT>.json`) garde la requête, la réponse brute, le modèle relevé
  (`modelUsage`), le nombre de tours, les jetons, le coût et la durée ; **un modèle autre que Sonnet ou plus
  d'un tour arrête la fabrication**. Une réponse déjà obtenue pour une requête identique à l'octet est
  reprise de la trace (reprise après correction, sans nouvel appel ; marqué dans la trace), **après sa durée
  d'origine** (`--reprise-duree`, 1 par défaut) : les réponses arrivent dans le même ordre, donc, même avec 5
  agents, les mêmes requêtes partent et tout est repris (le catalogue d'une requête dépend des OT déjà finis) ;
  `--reprise-seule` ne lance jamais d'agent (une requête absente des traces arrête la fabrication, aucun coût
  imprévu). Chaque proposition acceptée est validée au nom du responsable fictif, sauf si sa date d'intervention
  est dans les `demoAValiderJours` derniers jours (laissée « à valider »), et sauf si elle dépend d'une proposition
  laissée (laissée aussi : `Wiki.valider` la refuserait avant elle) ; une réponse refusée est relancée avec la
  raison, comme chez un client (§20.5) : **un agent neuf de plus**, tracé dans la même trace ; une relance encore
  refusée **n'arrête plus la fabrication** (D119) : l'OT reste « refusée » au journal, la fabrication continue et le
  bilan le compte.
  **Garde-fous** (D119, T144) : `fabriquer --budget D` (dollars ; absent : aucun plafond) compte les appels réels de
  cette commande (`cout_usd` des traces ; une réponse reprise des traces est gratuite) : avant chaque agent (relance
  comprise), si le coût dépensé plus le coût prévu des appels en cours et de celui-ci dépasserait D, aucun nouvel
  agent n'est lancé (coût prévu : l'appel le plus cher déjà fait, sinon 0,05 $) ; code retour 3, « ARRÊT : budget
  atteint — X $ dépensés sur Y $ ; N OT traités, M restants ». `--refus-max P` (défaut 10 ; 0 : aucun seuil) : chaque
  réponse lue par Prévo (`Ia.lireReponse`, première comme relance) est comptée ; à partir de 20 réponses, plus de P %
  de réponses refusées → aucun nouvel agent ; code retour 4, avec les raisons de refus regroupées. Dans les deux cas,
  les appels en cours finissent, les validations de fin se font sur ce qui a été traité, et les tables du wiki et
  `bilan.json` sont écrits ; les OT restants restent « en file » ; relancer la même commande reprend sans coût les
  réponses obtenues ; un temps 1 arrêté n'écrit ni `temps-1.json` ni `etat-avant-validation/`. **Bilan** de toute
  fabrication (affiché et `bilan.json`) : coût, coût par OT, réponses refusées et leur part, relances, OT refusés,
  causes ; après `--limite` : extrapolation = coût par OT × OT restants × `FACTEUR_CROISSANCE_SUITE` (1,578, passe 6).
  `verifier` compte et signale les OT refusés du journal figé, en échec au-delà de `--refus-max` %.
  **En deux temps** (D115, T122) : `--limite N` (temps 1 : les N premiers OT par date d'intervention) écrit, dans
  `.chantier/wiki-demo/temps-1/` par défaut, son résultat validé, `etat-avant-validation/` (tables du wiki après le
  traitement, avant les validations), `temps-1.json` (OT intégrés, empreinte des données de la démo et de la
  consigne, bilan, agents lancés, coût) et `relecture.html` ; `--suite` (temps 2) charge cet état exact, met en file
  les OT clôturés administrativement qui n'y ont pas d'entrée (aucune requête pour ceux du temps 1), les traite dans
  le même ordre puis valide tout comme une fabrication d'un seul tenant (avec un agent : même wiki à l'octet) ; elle
  refuse de partir sans temps 1, sur d'autres données de démo ou avec une autre consigne (rejouer alors le temps 1 :
  les réponses à des requêtes identiques sont reprises sans nouvel appel).
  Chaque agent tourne sans mise à jour de Claude Code (`DISABLE_AUTOUPDATER=1`) ; si `claude.exe` manque au
  lancement (mise à jour faite ailleurs), l'agent attend son retour (120 s au plus) puis part une fois. À la fin : `Wiki.verifierIntegrite`
  doit être `ok`, puis `figer` écrit les deux fichiers.
- `py outils/wiki_demo.py relecture` → `.chantier/wiki-demo/relecture.html` (et `relecture.html` du temps 1, avec
  son bilan et son coût) : les textes **par type** de la refonte 2 (§20.12 : machines — « En bref », « Astuces » —,
  articles — « À quoi il sert » —, savoir-faire), **les plus riches d'abord** (nombre d'OT cités distincts, puis
  nombre de phrases), chacun avec ses rubriques, ses OT cités en entier (compte rendu, astuce, et leur refus,
  relance avec la raison ou rejeu) et ses contradictions en tête ; puis les OT relancés ou rejoués et ceux « rien à
  ajouter ». Ce que Nicolas refuse est corrigé dans la fonction, puis la
  fabrication est rejouée ; aucune page retouchée à la main.
- **Mention** dans « À propos » et le guide : « Wiki de démo construit par Claude (<modèle>) avec la consigne
  de Prévo, un agent par OT, dans l'ordre des interventions ». La démo en ligne n'appelle aucune IA.
- **Résultat (T139, D119 ; T125)** : 227 OT intégrés par `claude-sonnet-5-5` en un passage, 5,16 $ soit 0,026 $ par OT
  (15 réponses refusées sur 242, toutes corrigées à la relance ; 137 acceptées, 90 « rien à ajouter », 0 OT refusé) ;
  42 pages (26 machines, 12 articles, 4 savoir-faire), 2 propositions laissées « à valider ». Le guide (chapitre 7)
  et le README citent ces chiffres, avec la réserve du fournisseur et de la longueur des comptes rendus.

### 20.11 Tests du lot 6
- **Ajouts de la refonte 2 (T125)** : `test_wiki_entites.py`, `test_wiki_ecrans.py` réécrit, `test_wiki_demo.py` étendu
  (§20.12) ; `test_guide.py` : chapitre « Le wiki de maintenance », section « mise à jour signalée », captures `wiki`
  et `wiki-page`, mentions clés.

`test_version_schema.py` et `test_schema.py` (format 3, 24 tables, colonne `astuce`, passages depuis 1 et
2) ; `test_wiki_socle.py` (routes, profils, export ZIP) ; `test_wiki_regles.py` et `test_wiki_calculs.py`
(couches calculées contre `calcul_wiki.py`, CS97, CS98) ; `test_wiki_controles.py` (chaque motif du §20.6 par
un défaut injecté, CS100) ; `test_wiki_ingestion.py` (liste blanche, pages concernées, ordre, antériorité,
ordonnanceur, faux fournisseur, CS99, CS110) ; `test_wiki_journal.py` (validation, rejet, à refaire,
rattrapage, écriture à la main, contradictions, visibilité, modes serveur, dossier et démo, CS101, CS102) ;
`test_wiki_parallele.py` (1 agent contre 5 : même wiki, intégrité, jamais deux envois sur une même page,
jamais plus de 5, CS111) ; `test_wiki_recherche.py` (astuce et pages, CS104) ; `test_wiki_ecrans.py` et
`test_wiki_journal_ecrans.py` (écrans, 1440 et 375 px, contrastes, origine, liens, CS103, CS106) ;
`test_wiki_astuce.py` (champ, aide, export, CS109) ; `test_wiki_demo.py` (fichiers figés, citations,
intégrité du journal de démo, traces : Sonnet, un tour, régénération à l'octet, mention, CS105, CS111) ;
`test_performance.py` (D101) ; `test_recette_lot6.py` (parcours complet). Révision du 2026-10-23 :
relance avec la raison dans `test_wiki_ingestion.py` (CS112) ; sous-pages dans `test_wiki_controles.py`
(chaque motif), `test_wiki_ingestion.py` (pages concernées), `test_wiki_journal.py` (découpage validé d'un
bloc, intégrité) et `test_wiki_ecrans.py` (mère, consignation, liste des sous-pages) (CS113). Le faux fournisseur
(`tests/faux_fournisseur_ia.py`) rend pour `ingestionWiki` une réponse valable construite sur les données
reçues, et sur demande une réponse piégée par motif du §20.6.

### 20.12 Refonte 2 — l'encyclopédie de l'atelier (CDC D113 à D115, validés par Nicolas le 2026-10-23)
Écrite avant le code de la refonte 2, d'après la maquette validée (`.chantier/maquette-wiki/`). Elle **prime** sur
§20.1 à §20.11 là où elle diffère ; ce qu'elle ne dit pas reste valable (journal, validation, contradictions,
relance, parallélisme, contrôles des citations, des nombres, des dates et de la sécurité). Corrections de Nicolas après
le temps 1 (2026-10-24) : **D116** savoir-faire communs (T141) et **D117** « En bref » réécrit (T142), intégrées ci-dessous.

- **Modules** : deux modules nouveaux, chargés dans cet ordre avec les autres (`ORDRE_MODULES`, `index.html`,
  listes de scripts des outils et des tests qui chargent le wiki) : `wiki-entites.js` (après `wiki-calculs.js` :
  calculs des pages Panne, Technicien, Intervention et du stock dans le temps d'un article, ordre des
  interventions, visibilité, références) et `wiki-entites-ecrans.js` (accueil, listes, outils d'affichage communs) ;
  la page d'une entité des six types (T137) : `wiki-page-ecrans.js` (cadre, en tête, textes et petits numéros,
  « Références », fiche) puis `wiki-sections-ecrans.js` (sections calculées de chaque type), tous deux avant
  `wiki-entites-ecrans.js`. 700 lignes au plus par fichier, comme partout.
- **Textes rédigés** (D96 révisée 2, D100 révisée 2) : `wiki_pages` ne garde que trois types —
  - `équipement` (texte de la machine, ancré sur `equipement_id`) : rubriques « En bref » (**3 phrases et 60 mots** au
    plus, D117 : réécrit en entier à chaque OT, §20.6 ; avant : 5 et 120) et « Astuces » (**10 phrases**) ;
  - `composant` (texte de l'article, ancré sur `article_id`) : rubrique « À quoi il sert » (**3 phrases et 80 mots**) ;
  - `savoir-faire` : « Quand le faire », « Étapes », « Pièces et outillage », « Pièges », « Particularités par machine »
    (D116), **30 phrases et 600 mots**, sous-pages au-delà (§20.4) — **les seules sous-pages** ; **un seul par geste**,
    commun aux machines (D116, T141) ;
  - `mode` disparaît (choix du schéma, `Wiki.RUBRIQUES`, consigne, contrôles, écrans) : une panne est calculée.
  Les limites sont des constantes nommées par type et par rubrique (`Wiki.LIMITES`), lues par les contrôles
  (§20.6 : « <rubrique> : N phrases, P au plus ») et par l'en-tête des pages envoyées. Un composant libre (sans
  article) ne se crée plus ; seul un savoir-faire se crée (`pagesCreeesMax` 3).
- **Pages concernées** d'un OT (D112 révisée ; D116, T141) : `EQ:<sa machine>`, `ART:<chaque article consommé>`, les
  savoir-faire rattachés à cette machine puis à ces articles, ceux dont le texte a un lien vers la machine (titres résolus
  dans l'état proposé ; le lien d'une sous-page amène sa mère), ceux **du même geste** (`Wiki.memeGeste`, `wiki-texte.js` :
  au moins 2 mots du titre et 60 % de ses mots — mots de la recherche, `Wiki.motsRecherche` — dans le titre, le remède, le
  travail, le compte rendu et l'astuce de l'OT ; 2 au plus, plus grande part puis titre), puis ceux dont le texte a un lien
  vers ses articles ; chacun suivi de ses sous-pages ; plus de clé `CAUSE:`, plus de pages liées depuis la machine ; 8
  envoyées au plus, toutes les clés réservées. Un savoir-faire créé pendant l'envoi et concerné sur le nouvel état fait
  rejouer l'OT (motif « rejoué : pages changées pendant l'envoi », §20.5). Limite connue : un OT parti en même temps qu'un
  autre qui crée le même geste ne le voit pas s'il finit le premier (le contrôle « titre trop proche » reste la défense).
- **Consigne `ingestionWiki`** : l'IA met à jour seulement « En bref » (ce qu'il faut savoir d'abord de cette
  machine : ses pannes et ce qui les a réglées ; D117, T142 : une synthèse **réécrite en entier** à chaque OT, jamais une
  phrase ajoutée à la suite, chaque phrase avec les OT qui la fondent ; l'en-tête de ses longueurs le dit : « …, à réécrire
  en entier » ; « garde toutes ses phrases » et la rubrique pleine valent hors « En bref »), « Astuces » (une astuce courte d'un OT, en une phrase qui dit l'ordre
  des vérifications ou le geste, sans adverbe de fréquence : ni « toujours », ni « plus vite »),
  « À quoi il sert » de chaque article consommé — seulement ce que les OT observent de lui (son rôle sur la machine
  si l'OT le dit, ses signes d'usure ou de casse, ce qui l'use, comment il se monte ou se change), jamais où ni quand
  il a été changé, ni la panne qu'il a réglée, ni un rôle supposé ; sinon la page n'est pas renvoyée (une page
  concernée non renvoyée reste inchangée ; renvoyée inchangée, elle compte comme non renvoyée, §20.5) —, et crée ou
  modifie des savoir-faire (d'abord à partir de l'astuce, D110 ; créé seulement avec au moins deux gestes que
  l'astuce ou le compte rendu décrivent, le travail demandé seul ne suffit pas ; D116, T141 : un seul par geste, commun
  aux machines, titre = le geste et l'organe **sans repère** ; reçu, il se complète — sa phrase de « Particularités par
  machine » pour cette machine, ses étapes —, jamais recréé ; au catalogue seulement, un lien `[[titre]]` suffit ; créé,
  il relie ses machines dans « Particularités par machine » et ses articles dans « Pièces et outillage » ; `rattache_a` :
  l'article principal du geste s'il y en a un, sinon la machine) ; une astuce à un seul endroit (« Astuces » ou un savoir-faire, jamais aux deux ni dans
  « À quoi il sert ») ; une synthèse, pas un historique ; les longueurs de l'en-tête de chaque texte — rubrique
  pleine : ajouter l'OT à la phrase qu'il confirme, regrouper deux phrases en gardant tous leurs OT, ou n'y rien
  écrire ; relevés d'un contrôle de routine non écrits sauf si l'OT les dit anormaux ou s'ils expliquent la panne ;
  aucun comptage, même dans une étape, aucune fréquence (« fréquent », « souvent », « régulièrement », « à chaque
  fois »), jamais « cause certaine » ; nombres : la règle du contrôle (§20.6) — l'OT à intégrer ou le texte actuel
  de la page écrite (page créée, titre compris : l'OT seul ; sous-page créée : aussi le texte et le titre de sa
  mère), jamais un nombre d'une autre page reçue, le titre d'un lien `[[…]]` ne comptant pas ; « rien à ajouter »
  pour un préventif sans remarque (gamme faite, relevés sans anomalie, usure normale, petit nettoyage
  complémentaire) ; étape d'arrêt : « Mettre la machine à l'arrêt selon la fiche en tête de
  sa page » ; toutes les autres règles inchangées (T140). **Seuls les OT clôturés administrativement** entrent dans
  la file (inchangé, §20.5) : l'IA ne rédige qu'à partir d'eux.
- **Pages et identifiants** (`Wiki.entite(id, { profil, maintenant })`, D113 ; l'écran d'une page ne lit que `Wiki.entite` —
  `Wiki.page` garde l'ancienne forme pour l'écriture à la main et le journal, et donne à `Wiki.entite` l'en-tête, la mère
  et les sous-pages d'un savoir-faire) : `EQ-…` machine, `ART-…` article,
  `TEC-…` technicien, `OT-…` intervention, `WP-…` savoir-faire (et texte d'une machine ou d'un article, qui mène à
  leur page), **panne** = `PANNE-<code symptôme>`. Chaque page → `{ id, type, titre, faits, sections, textes,
  aTrancher, enAttente, references, retours, liens }` : `faits` = la fiche (paires libellé, valeur ; liens vers les
  entités), `sections` = les blocs calculés dans leur ordre, `textes` = les rubriques rédigées et leur origine, `retours`
  = « Pages qui renvoient ici » (CS103, §20.9) d'une machine, d'un article, d'un savoir-faire ou d'une panne — la règle
  de `Wiki.page` (pages actives dont le champ `liens` désigne l'entité ou la ligne de son texte), réduite aux pages qui
  s'affichent ; une proposition à valider n'y entre jamais (T137). Calculé, sans IA, sans
  écriture :
  - **Machine** : fiche (repère, lieu, marque et modèle, série, mise en service, criticité, état, habilitation,
    parent, sous-ensembles, nombre d'interventions), consignation (en tête), pannes fréquentes `{ code, cas, derniere
    }` (OT correctifs clôturés), interventions, articles montés (`article_equipement`) et consommés `{ articleId,
    quantite, ot }`, savoir-faire, gammes actives et contrôles réglementaires ; textes « En bref », « Astuces ».
  - **Panne** (code symptôme qui a au moins un OT clôturé) : machines touchées `{ machine, cas }`, **causes** et
    **remèdes** `{ code, libelle, cas }` en sections, articles changés `{ articleId, quantite, ot }`, interventions,
    premier et dernier cas ; aucun texte.
  - **Article** : fiche (référence, fabricant et sa référence, emplacement, stock et unité, état « en stock » / « sous
    le seuil » / « rupture », sécurité, point et quantité de commande, délai, fournisseur, **prix**, critique) ; **stock
    dans le temps** = commandes (`achats` : date, quantité, fournisseur, statut, réception), sorties (mouvements
    imputés à un OT, avec le stock restant) et **ruptures** (périodes où le stock reconstitué par les mouvements —
    un inventaire fixe la quantité, une entrée ou un retour ajoute, une sortie retire — est à 0 ou moins) ; où il
    est monté, consommé sur (machine, nombre d'OT), interventions où il a servi, savoir-faire ; texte « À quoi il sert ».
  - **Technicien** : métier, capacité, heures pointées (`ot_temps`), habilitations `{ intitule, obtention,
    echeance, etat }` (celles qui comptent et leur état selon les règles du module Équipe : une par intitulé, « échue », « à renouveler » sous 60 jours (RG8), « pas encore valable », « valide » ; l'accueil compte les techniciens actifs), interventions (technicien de l'OT ou
    temps pointé), **taux horaire** ; aucun texte ; son nom n'est jamais dans une requête à l'IA (inchangé, CS99).
  - **Intervention** : tout l'OT en lecture seule (machine, technicien(s), type, priorité, statut, dates, arrêt,
    panne, cause, remède, demande d'origine, travail, compte rendu, astuce, motifs d'attente et d'annulation s'ils sont
    renseignés, pièces sorties, opérations, temps) ; la fiche nomme tous ses techniciens (celui de l'OT et ceux qui
    y ont pointé du temps : « Techniciens » s'ils sont plusieurs) ;
    « Cité dans le wiki » (pages dont un texte cite l'OT) ; `ficheOT` = `#/ot/<id>`.
  - **Savoir-faire** : inchangé (§20.3, en-tête de consignation ; une sous-page de savoir-faire reprend celui de
    sa mère) ; D116 (T141) : commun à plusieurs machines (sa machine de rattachement et les machines liées par son champ
    `liens` : EQ-…, ou ligne du texte d'une machine), son en-tête est la liste de ces machines, celle du rattachement
    d'abord, chacune avec un lien vers sa page où est sa consignation, sans consignation recopiée (« Ce savoir-faire sert
    sur ces machines ») ; rattaché à un article : où il est monté, puis les machines liées.
  - **Section « Savoir-faire »** d'une machine et d'un article (D116, T141) : les savoir-faire rattachés **et** ceux dont
    le champ `liens` (le leur, ou celui d'une de leurs sous-pages) désigne l'entité ou la ligne de son texte ; une fois
    chacun, sans sous-page, par titre.
  - **Ordre des interventions** dans toutes les listes (D113, réponse 5) : d'abord les OT **ouverts** (Créé,
    Planifié, Préparé, En cours, En attente : « En cours » d'abord, puis par date prévue), puis les autres (clôturés,
    annulés) du plus récent au plus ancien ; chaque ligne porte son statut.
  - Un calcul Python indépendant (`tests/calcul_wiki.py`, étendu) refait ces faits sur la démo et sur une base
    d'essai (CS114).
- **Visibilité** (D114) : `Wiki.entite` et les listes appliquent le profil — le **demandeur** n'a ni page Technicien
  (`null`, nom sans lien ailleurs), ni page Intervention (numéro sans lien), ni prix d'article ; le **taux horaire**
  n'est rendu qu'au responsable ; le **prix** au responsable et au technicien. La recherche suit la même règle.
- **Références** (D113) : `Wiki.references(textes, aTrancher)` donne les OT cités dans l'ordre d'apparition sur la
  page — « À trancher », en tête, puis les textes (T137) ; à l'écran, chaque citation est un petit numéro (`<sup class="wiki-ref">`, lien `#/wiki/<OT>`,
  bulle « <OT> · <date> · <titre> » ; pour le demandeur, un bouton sans lien qui ouvre cette bulle au toucher, au clic
  ou au clavier ; `aria-label` « Référence n : <OT> · <date> · <titre> ») et la page finit par « Références » (numéro, OT,
  date, machine, titre). Jamais `[OT-…]` affiché ; le balisage stocké ne change pas. Les OT des articles consommés (page
  Machine) et des articles changés (page Panne) sont aussi des petits numéros, les 10 plus récents de chaque article puis
  « … et n autres », et sont dans « Références » : la page numérote tous ses OT en un seul jeu, dans l'ordre où elle les
  montre, un OT déjà numéroté gardant son numéro (D118).
- **Routes** : `#/wiki` (accueil), `#/wiki/machines`, `#/wiki/pannes`, `#/wiki/articles`, `#/wiki/techniciens`
  (pas pour le demandeur), `#/wiki/savoir-faire`, `#/wiki/interventions` (pas pour le demandeur) — les listes —, et
  `#/wiki/<id>` (une page). `#/wiki-journal` et `#/wiki-ecrire/<id>` inchangés (écriture à la main : textes d'une
  machine ou d'un article, savoir-faire).
- **Écrans** (§20.9 remplacé pour l'accueil et les pages) : **accueil** = grande tuile « Ce que l'atelier sait »
  (phrase-résumé dont chaque nombre mène à sa liste, champ de recherche dedans, résultats groupés par type), cinq
  briques (Machines, Pannes, Articles, Techniciens — pas pour le demandeur —, Savoir-faire : icône et couleur
  discrète du type, nombre, une ligne utile), « Suivi du wiki » au responsable (à valider, à trancher, en échec :
  discrètes à zéro, liens vers `#/wiki-journal?vue=…`), dernières interventions, pannes les plus fréquentes ;
  **listes** : machines par lieu (sous-ensembles sous leur machine), pannes par nombre de cas, articles en tableau
  filtrable avec l'état du stock, techniciens en cartes, savoir-faire, interventions ; **page** : fil d'Ariane,
  type (icône et couleur), titre, **consignation et « À trancher » en tête**, sections, « Pages qui renvoient ici »
  (discrète, absente sans retour ; pas sur une page Intervention, dont « Cité dans le wiki » tient ce rôle),
  « Références », et la
  **fiche des faits** à droite (au-dessus sur téléphone) ; textes rédigés avec leur bandeau d'origine (§20.9) ;
  « Ouvrir la fiche OT » sur une page Intervention. Style actuel de Prévo (tuiles de l'accueil, Sora, thèmes
  sombre et clair), 1440 et 375 px sans défilement horizontal, zones tactiles ≥ 48 px, contrastes AA (CS106) ;
  longues listes (D101, jeu de charge) : seuls les premiers éléments sont créés, « Voir les n autres » crée le reste ;
  un tableau triable trie toute la liste, puis n'en crée que les premières lignes ;
  **aucun appel réseau pour afficher une page** (D101 : le rattrapage du journal ne relit pas `wiki_pages` à chaque
  affichage).
- **Contrôle du wiki** (D108 précisée) : sur les textes rédigés et les savoir-faire ; les pages calculées existent
  toujours (plus de page orpheline à chercher pour elles).
- **Démo** (D115) : `py outils/wiki_demo.py fabriquer --limite 40` (les 40 premiers OT par date d'intervention ;
  résultat, état de départ de la suite et page de relecture dans `.chantier/wiki-demo/temps-1/`), relecture de ce
  premier temps par Nicolas, puis `fabriquer --suite` : repart du résultat du temps 1 (rejoué s'il a été corrigé),
  sans aucun appel pour ses OT, validations comme d'un seul tenant (§20.10) ; **coût estimé donné avant chaque
  temps** (`.chantier/wiki-demo/temps-1/estimation.md`). `generer_demo.py` ne reprend le wiki figé que pour la démo
  standard (une autre durée d'historique ou le jeu de charge → tables du wiki vides, avec un message) ;
  `js/demo-donnees.js` reste sous 1 Mo (CS105 : chargement rapide ; tables du wiki écrites par morceaux, arrêt
  au-delà, §20.10). Nuit du 2026-10-24 (D119) : chaque commande reçoit `--budget` = ce qui reste des 15 $ (moins une
  marge de 0,25 $), et `--refus-max 10` (§20.10).
- **Tests** : `test_wiki_entites.py` (faits des six pages contre `calcul_wiki.py`, ordre des interventions,
  visibilité, références) ; `test_wiki_ecrans.py` réécrit pour l'accueil, les listes et les pages (profils, liens,
  petits numéros, 1440 et 375 px, affichage en moins de 500 ms sur le jeu de charge) ; les tests des textes rédigés suivent les nouveaux types et limites ;
  `test_wiki_demo.py` : fabrication en deux temps (même wiki qu'un seul tenant, aucun appel pour le temps 1, refus de
  la suite), relecture de la refonte 2, garde-fous (budget atteint, appels en cours et relances comptés, reprises
  gratuites, plus de 10 % de réponses refusées, refus isolé, extrapolation) ; `test_demo.py` : wiki figé de la seule démo standard, `js/demo-donnees.js`
  sous 1 Mo avec un wiki complet.

## 21. Mise à jour signalée (D120, CS118 ; T147)

Les utilisateurs ne surveillent pas GitHub : Prévo leur dit lui-même qu'une version plus récente existe, sans rien
installer.

- **Fichier** : `https://prevo.pro/version.json`, écrit par `outils/construire_release.py` dans `dist/` à côté du zip
  (`{"version": "1.2.0", "date": "AAAA-MM-JJ", "adresse": "<release GitHub>", "nouveautes": [≤ 2 puces du CHANGELOG]}`,
  UTF-8, LF) et publié à la racine du site à chaque release, servi avec `Access-Control-Allow-Origin: *` (lecture
  depuis le poste, autre origine ; docs/RELEASE.md).
- **T305 (D174-D176, décisions de Nicolas des 06 et 07/11)** : **active par défaut**, coupée par `maj_signalee` = `0`
  (Paramètres › Mises à jour : la case, cochée par défaut, dit à côté ce qui est lu, quand, ce qui part et comment
  couper ; rien dans l'assistant d'installation). Tant que le responsable n'a rien réglé (clé absente ou vide), un
  bandeau d'information unique par poste le dit sur son accueil (`#maj-information`, « Compris » : `prevo.majInformee`).
  Requête minimale : `fetch(adresse, { cache: 'no-store', credentials: 'omit', referrerPolicy: 'no-referrer',
  redirect: 'error' })`, sans paramètre ni en-tête ajouté : ni cookie, ni adresse de la page, ni identifiant, numéro
  d'installation ou statistique. Ce que prevo.pro voit quand même, comme pour toute visite : l'adresse IP publique de
  l'atelier, le navigateur (User-Agent) et l'en-tête `Origin` que le navigateur ajoute lui-même à une lecture vers un
  autre site (l'adresse locale de Prévo, par exemple `https://192.168.1.20:8443`, ou `null` en fichier local) : accepté
  par Nicolas le 07/11 et dit dans le guide (§2.9). Adresse de téléchargement en **liste blanche** (D176,
  `MiseAJour.adresseDeTelechargementPermise`) : `https://prevo.pro/…` ou `https://github.com/nicoboy49/prevo/…`, hôte
  exact, sans nom ni mot de passe, port par défaut ; sinon le fichier est ignoré (aucun bandeau). `nouveautes_en`
  (facultatif, mêmes règles que `nouveautes`) est montré dans un Prévo affiché en anglais, `nouveautes` sinon ;
  textes toujours affichés comme du texte. Règles du fichier (seule source) : docs/RELEASE.md. La seule connexion que Prévo ouvre de lui-même vers Internet est cette lecture de version.json ; s'y ajoutent, seulement si vous les utilisez, l'assistant IA en ligne et la dictée vocale.
  Le serveur n'a plus de téléchargement de secours de mkcert (`telecharger_mkcert`, sans appel, retiré par T305 :
  mkcert est dans le zip depuis 2.0.0-beta.1).
- **Lecture** (`js/modules/mise-a-jour.js`, `MiseAJour`, chargé juste après `apropos.js`) : sauf si le paramètre
  `maj_signalee` vaut `0` (Paramètres, responsable, section « Mises à jour », `1` par défaut depuis T305), sur le poste
  du responsable, jamais en version web (`App.versionWeb`) ; `App` appelle `MiseAJour.verifier()` une fois l'application
  prête (après la marque `prevo:pret`). Au plus une lecture par jour et par poste : `prevo.majLecture` (localStorage)
  garde la date et le résultat, un échec comptant pour la lecture du jour ; `fetch` sans cache, délai 5 s ; le fichier
  est vérifié (version `x.y.z`, adresse `https://`, date `AAAA-MM-JJ` facultative, nouveautés : 3 au plus, 200
  caractères chacune) sinon ignoré ; absent, injoignable ou mal formé : rien, aucune erreur montrée. L'adresse peut
  être forcée par `window.PREVO_ADRESSE_VERSION` (tests : faux serveur local).
- **Affichage** : version plus récente que `App.version` (comparaison numérique des trois nombres) et non ignorée →
  bandeau `#maj-bandeau` (`UI.bandeau('info')`) dans `#maj-zone`, juste sous l'en-tête de l'accueil du responsable
  (version, date, nouveautés, « Télécharger » vers l'adresse dans un nouvel onglet, « Ignorer cette version » :
  `prevo.majIgnoree`, une version plus récente encore sera signalée) ; ligne « Mise à jour » de À propos
  (`#apropos-maj` : disponible avec le lien / à jour, vérifié le … / injoignable aujourd'hui / non vérifiée, à
  autoriser dans Paramètres / démo en ligne : aucune vérification). Le technicien et le demandeur ne voient rien et
  aucune requête ne part pour eux. Aucune installation automatique.
- **Tests** : `test_mise_a_jour.py` — faux serveur local (compte les requêtes) : avec l'accord et une version plus
  récente, bandeau et ligne de À propos ; sans accord, technicien ou version web : aucune requête ; une seule lecture
  par jour (rechargements) ; « Ignorer » tient au rechargement ; version égale ou plus ancienne, fichier mal formé,
  absent (404) ou serveur injoignable : rien et aucune erreur JavaScript ; `version.json` de la release (champs,
  nouveautés tirées du CHANGELOG, sans Markdown) ; `test_depot.py` : ordre des modules.

### 21.1 « Suggérer une amélioration » (T306)

Lien visible par tous les profils dans « À propos » (`#apropos-suggestion-lien`, repli `#apropos-suggestion-courriel`)
et au pied du menu (`#menu-suggestion-lien`, rempli par `placerSelecteurLangue` de `js/app.js`). Il ouvre un nouvel
onglet (`target="_blank" rel="noopener noreferrer"`) sur le formulaire d'issue GitHub
`https://github.com/nicoboy49/prevo/issues/new?template=<2-proposer-une-amelioration.yml | 3-suggest-an-improvement.yml>&title=…&contexte=…`
(modèle anglais si `I18n.langue` vaut `en`) ; `contexte` ne porte que la version de Prévo, la langue active et le
navigateur réduit à « nom version, système » (`Apropos.navigateurReduit`, `navigator.userAgentData` sinon
`navigator.userAgent`) : aucune donnée de la base, aucun nom, aucun jeton. Repli : `mailto:contact@prevo.pro` au même
contenu. Les adresses sont dans `Apropos.ADRESSES` (`js/modules/apropos.js`), un seul endroit, réutilisable par la
mention « traduction automatique » du Lot 5. Aucune requête au chargement : un lien cliqué, la politique de sécurité
du contenu ne change pas. Test : `test_suggestion.py`.

## 22. Contrat du lot 7 — accès et installation (CDC validé le 2026-10-26 : D121–D140, CS119–CS137)

Le lot rend Prévo joignable au-delà du PC sans ouvrir de port sur la box, avec des comptes vérifiés par le
serveur et le https partout au-delà du PC. Ce paragraphe est le contrat des tâches T149 à T181 ; une tâche qui
s'en écarte le dit dans son commit et le corrige ici. Prévo devient **2.0.0**. Bibliothèque standard seulement ;
deux binaires tiers livrés dans le zip de release, jamais dans le dépôt : Python embeddable et mkcert.

### 22.1 Portées et axes du serveur (D122)

| Portée (assistant, Paramètres) | `ecoute` | `comptes` | `https` | `mandataire` |
| --- | --- | --- | --- | --- |
| « ce PC » (défaut, tests) | `127.0.0.1` | non (profils de 1.2) | non | non |
| « le Wi-Fi de l'atelier » | toutes les interfaces | oui | certificat local (§22.6) | non |
| « aussi hors de l'atelier » | toutes les interfaces | oui | certificat local | oui pour 127.0.0.1 (`tailscale serve`) |
| Intranet derrière un mandataire | `127.0.0.1` | oui | non (porté par le mandataire) | oui |

Règles vérifiées au démarrage par `verifier_regles_portee(config)`, avant toute écoute : écoute hors de
127.0.0.1 ⇒ `comptes` vrai **et** (`https` ou `mandataire`) ; `mandataire` ⇒ `comptes` ; `comptes` vrai et aucun
compte responsable actif ⇒ démarrage en portée « ce PC » avec l'assistant (jamais d'écoute réseau). Écart ⇒
message en français sur la console et dans `journal-serveur.log`, code de sortie **2**. Il n'existe aucune option
qui contourne ces règles.

### 22.2 Configuration (`prevo.config.json`, D123)

Fichier à côté de `serveur.py` (jamais dans `donnees/`, jamais sauvegardé ni exporté), JSON UTF-8, écrit de façon
atomique ; priorité : ligne de commande > fichier > défauts. `serveur.py --aide` imprime chaque clé, sa valeur par
défaut et son texte d'aide (le même que `js/modules/acces-textes.js`, dont les textes sont dans
`js/i18n/aide/<langue>.js`, clés `aide.acces.*`, depuis T247).

| Clé | Type, défaut | Rôle |
| --- | --- | --- |
| `portee` | `ce-pc` \| `atelier` \| `dehors` ; `ce-pc` | résumé lisible ; fixe les quatre axes |
| `ecoute` | `127.0.0.1` \| `0.0.0.0` | axe d'écoute |
| `port_http` | 8080 | porte d'entrée (et application en portée « ce PC ») |
| `port_https` | 8443 | application en https |
| `noms` | liste, `[]` | noms acceptés en plus de l'IP, `localhost`, nom du PC (Tailscale, DNS interne) |
| `certificat`, `cle` | chemins, `""` | PEM ; vide en portée « ce PC » |
| `certificat_auto` | booléen, vrai | certificat local fabriqué par mkcert (§22.6) |
| `mandataire` | booléen, faux | confiance à `X-Forwarded-*` venant de 127.0.0.1 (§22.7) |
| `comptes` | booléen | exigés ou non |
| `demandeurs_avec_compte` | booléen, faux (vrai en Intranet) | désactive l'enrôlement d'appareils |
| `session_heures`, `session_longue_jours` | 12, 30 | durées de session |
| `invitation_heures` | 24 | durée d'une invitation (1 à 168) |
| `demarrage` | `aucun` \| `systeme` \| `session` | tâche planifiée (§22.9) |
| `veille_desactivee` | booléen | réglages `powercfg` appliqués |
| `copie_sauvegardes` | chemin, `""` | copie externe nocturne (§22.11) |
| `quota_documents_mo` | 4096 (T250 ; 2048 avant) | plafond du dossier `documents/`, autant que l'import ZIP (4 Go) |
| `ia_fournisseur`, `ia_url`, `ia_cle`, `ia_en_ligne` | `ollama` \| `openai`, `http://localhost:11434`, `""`, faux | fournisseur d'IA côté serveur (§22.12) ; la variable `PREVO_IA_CLE` passe avant `ia_cle` |
| `_aide` | texte | commentaire d'en-tête pour qui ouvre le fichier |

### 22.3 Comptes, sessions, appareils (D124, D125)

Dossier `donnees/acces/`, lu et écrit par le serveur seul (jamais servi par `/api/csv`, jamais restauré par
`/api/restauration`, copié dans les sauvegardes du serveur sauf `sessions.json` ; jamais dans l'export ZIP du
navigateur, qui ne les lit pas : les empreintes ne quittent jamais le serveur) :

- `comptes.json` : `{ "version": 1, "comptes": [ { "identifiant": "prenom.nom", "prenom", "nom", "role":
  "responsable"|"technicien"|"demandeur", "technicien_id", "actif": true, "algo": "scrypt-n15-r8-p3"|
  "pbkdf2-sha256-600000", "sel": base64, "empreinte": base64, "a_changer": bool, "cree_le", "modifie_le",
  "mot_de_passe_le", "langue"? } ] }`.
  **Langue du compte (T298, D148)** : champ facultatif `langue`, absent ou vide = la langue de l'installation.
  Valeur fermée : une langue déclarée par `js/i18n/langues.js` (`langues_declarees`, la valeur exacte : ni espace ni
  autre casse), ou vide (le champ est alors retiré) ; tout le reste → 400 `comptes.langue_inconnue` (ou
  `comptes.texte_attendu` pour un non-texte à `/api/acces/comptes`), rien d'écrit (`langue_de_compte`). Elle se
  change par la personne elle-même (`POST /api/mot-de-passe {"langue"}` seul, §22.4 : seul ce champ change, ni sel, ni
  empreinte, ni `modifie_le`, aucune session fermée) ou par le responsable (création et `action: modifier` de
  `/api/acces/comptes…`). Une valeur hors liste écrite à la main est ignorée (`langue_publique` : '' dans la session).
  La 2.0.0 bêta 2 relit sans erreur un `comptes.json` qui porte `langue` et garde le champ (`compte_public` le laisse
  passer vers le responsable ; ses réécritures reprennent chaque compte tel qu'il a été lu) ; sans changement de langue,
  la 2.0.1 ne réécrit pas `comptes.json` (base bêta 2 relue à l'octet près, `tests/test_langue_compte.py`).
  **Identifiants et noms (T301, D164 ; règle de Nicolas : une même personne n'a jamais deux identifiants, deux
  personnes jamais le même)** : une seule règle, `plier_nom` (serveur.py) : İ, I, ı, i → i ; casse pliée (casefold,
  ß → ss) ; accents retirés (ş → s, ğ → g, ç → c, ö → o, ü → u) ; elle fabrique l'identifiant (`identifiant_depuis` :
  « Ayşe Işık » → `ayse.isik`, « Élodie Le Gall » → `elodie.le-gall`, inchangé) et compare les noms (`forme_de_nom`,
  lien d'un responsable à sa fiche de technicien). Création : un compte (actif ou non) au même prénom et au même nom
  ramenés ainsi → 400 `comptes.meme_personne` avec son identifiant, sauf `autre_personne` vrai (case « C'est une autre
  personne » d'Équipe › Accès, montrée après ce refus) : « .2 ». Identifiant tapé (`comptes_designes`) :
  l'identifiant exact tranche toujours ; sinon les comptes que le texte désigne ramené par `plier_nom`, ou par la règle
  d'avant T301 (« Işık » → `is-k` : les comptes créés avant ne sont jamais renommés). Plusieurs comptes désignés :
  `trouver_compte` n'en rend aucun (réinitialisation : 400 `comptes.plusieurs` avec la liste, pour le responsable ou
  la ligne de commande) ; à la connexion, 401 `sessions.identifiant_ambigu` (« tapez-le exactement ») sans vérifier
  aucun mot de passe, l'essai comptant comme un échec (blocage au 10e) ; Prévo ne choisit jamais un compte à la place
  de la personne. Les essais comptent par compte désigné (« YILMAZ » et « yilmaz » ensemble), sinon par texte ramené.
- `sessions.json` : `{ "<sha256 du jeton>": { "identifiant", "cree_le", "vu_le", "longue": bool, "agent" } }` —
  seule l'empreinte du jeton est gardée (SHA-256 en hexadécimal) ; dates en heure locale `AAAA-MM-JJTHH:MM:SS`.
- `appareils.json` : `{ "invitations": [ { "id", "empreinte", "cree_le", "expire_le", "revoquee" } ], "appareils":
  [ { "id", "empreinte", "libelle", "nom_demandeur", "cree_le", "vu_le", "revoque": bool, "invitation" } ] }` —
  seule l'empreinte SHA-256 du jeton (d'invitation ou d'appareil) est gardée ; `id` = `INV-` ou `AP-` et quatre
  caractères hexadécimaux tirés au sort, jamais réemployés ; `invitation` = l'id de l'invitation qui a servi.
- `journal-acces.csv` (`;`, UTF-8 avec BOM, apostrophe de protection) : `date;qui;adresse;agent;resultat;tailscale`,
  `resultat` ∈ `connexion`, `echec`, `bloque`, `deconnexion`, `appareil`, `invitation`, `revocation`,
  `reinitialisation`, `creation`, `modification`, et `langue:<avant>><après>` (T298 : langue d'un compte changée,
  `installation` pour vide : `langue:installation>en`, `langue:en>fr` ; après `modification` quand c'est le
  responsable ; Équipe › Accès › Journal : « Langue changée (installation → en) ») ; lignes de plus de 12 mois purgées
  à la première écriture du jour.

Mot de passe : 12 à 256 caractères, aucune règle de composition ; échec : délai `min(2^(n-5), 8)` s dès le 5e échec
consécutif, blocage 15 min au 10e (par compte), ralentissement de 1 s par adresse IP au-delà de 20 échecs par heure ;
réponse 401 `{"erreur": "Identifiant ou mot de passe incorrect."}` identique dans tous les cas, 429 pendant le blocage
avec le temps restant. Cookie `id=<jeton>; Path=/; HttpOnly; SameSite=Lax[; Secure][; Max-Age=…]` ; jeton
d'appareil : cookie `appareil=<jeton>`, mêmes attributs, 1 an glissant. L'horloge du serveur est injectable
(`config.horloge`) pour les tests.

Précisions de T151 (connexion et sessions) :

- **Échecs**, comptés en mémoire seulement (un redémarrage du serveur les remet à zéro), par identifiant saisi
  (minuscules, espaces de bord retirés), qu'un compte existe ou non (`CompteursEchecs`, rangé dans `config.echecs`).
  Identifiant inconnu, compte désactivé et mot de passe faux suivent le même chemin : une empreinte est calculée dans
  tous les cas (sel factice pour un identifiant inconnu), même code, même message, mêmes en-têtes, même attente. Du 5e
  au 9e échec consécutif, attente de 1, 2, 4, 8, 8 s avant de répondre ; le 10e répond aussitôt 429 et ouvre le
  blocage ; pendant le blocage, toute tentative sur cet identifiant rend 429 `{"erreur", "attente_secondes"}` avec
  l'en-tête `Retry-After`, sans vérifier le mot de passe ; à la fin du blocage le compteur repart de zéro, et une
  réussite le remet à zéro. Une tentative compte dès son début : des tentatives lancées en même temps ne font jamais
  plus de 10 vérifications. Adresse : dès 20 échecs dans l'heure écoulée, chaque tentative venue d'elle (même juste)
  attend 1 s de plus. Attentes par `config.dormir(secondes)` (injectable, défaut `time.sleep`), temps par
  `config.horloge` (défaut `time.time`). Au-delà de 10 000 identifiants ou adresses suivis, les moins récents sont
  oubliés (un blocage en cours en dernier).
- **Sessions** : jeton `secrets.token_urlsafe(32)` neuf à chaque connexion (la session que le navigateur présentait est
  fermée) ; session courte : 12 h sans activité (`session_heures`, glissantes ; `vu_le` réécrit au plus une fois par
  minute et par session) ; avec « rester » : 30 jours depuis `cree_le` (`session_longue_jours`), le cookie porte alors
  `Max-Age` du même temps (sans « rester », cookie de session du navigateur, sans `Max-Age`) ; sessions expirées
  purgées à chaque écriture du fichier (atomique, sous `VERROU_SESSIONS`). Mot de passe changé ou réinitialisé (ligne
  de commande comprise) et compte désactivé ⇒ toutes ses sessions supprimées ; chaque requête revérifie en plus le
  compte (actif, `mot_de_passe_le` pas plus récent que le `cree_le` de la session), ce qui couvre un `comptes.json`
  réécrit par un autre processus. `sessions.json` illisible : aucune session (chacun se reconnecte) ; `comptes.json`
  illisible : personne n'est reconnu, `/api/ping` répond toujours, la connexion rend 500 avec un message clair.
- **Journal** : `connexion`, `echec` (mot de passe faux, ou mot de passe actuel faux au changement), `bloque` (tentative
  pendant un blocage), `deconnexion` (déconnexion et « déconnecter partout », `qui` étant le compte dont les sessions
  sont fermées), `modification` (mot de passe changé, avec l'adresse) ; `qui` vaut `(inconnu)` pour un identifiant
  sans compte (un mot de passe tapé dans la mauvaise case n'y est jamais recopié) ; `adresse` par `adresse_client()` du
  gestionnaire (T164 : adresse d'origine derrière un mandataire) ; `tailscale` = en-tête `Tailscale-User-Login`
  seulement si `mandataire` est vrai et que la connexion vient de 127.0.0.1 (ou ::1), vide sinon. Jamais un mot de
  passe ni un jeton dans le journal, la console, une réponse ou `sessions.json`.

Ligne de commande : `serveur.py --reinitialiser IDENTIFIANT` (écrit un mot de passe provisoire de 16 caractères,
l'affiche une fois, marque `a_changer`, journalise ; refusée si `comptes.json` est absent). `Reinitialiser_mot_de_passe.bat`
demande l'identifiant et appelle cette commande.

Précisions de T153 (appareils enrôlés, D125, CS123) :

- **Invitation** : créée par le responsable (`creer_invitation`), valable `invitation_heures` (24 h par défaut, 1 à
  168, ou `heures` dans le corps) ; le jeton (`secrets.token_urlsafe(32)`) est rendu une seule fois avec le chemin
  `/#/enroler/<jeton>` : le QR et le lien se font côté navigateur (Équipe › Accès, T156) avec l'adresse http de la
  porte (§22.6), le serveur ne connaît pas son adresse publique. Usage multiple jusqu'à l'expiration ou la
  révocation.
- **Enrôlement** (`POST /api/enroler`, route publique) : l'invitation est reconnue par son empreinte, le nom saisi
  (1 à 60 caractères, espaces réduits) est mémorisé, le libellé vient de la famille du navigateur (iPhone, Android,
  PC Windows…, jamais la chaîne entière) ; l'appareil reçoit le cookie `appareil=<jeton>; Path=/; HttpOnly;
  SameSite=Lax[; Secure]; Max-Age=31536000` et la réponse de `GET /api/session` d'un demandeur (`appareil` vrai,
  `identifiant` = `appareil:<id>`, `nom` = le nom saisi, `prenom` vide). Invitation inconnue, expirée ou révoquée :
  401 au même message. `demandeurs_avec_compte` vrai : 403 (enrôlement désactivé).
- **Reconnaissance** (`verifier_appareil`, appelée par `verifier_session` quand aucun cookie `id` ne vaut) : jeton
  connu, appareil ni révoqué ni expiré (un an glissant depuis `vu_le`, réécrit au plus une fois par minute) ;
  `GET /api/session` renvoie le cookie avec un `Max-Age` neuf (un an glissant côté navigateur, à chaque ouverture).
  Quand `demandeurs_avec_compte` est vrai, aucun appareil n'est reconnu, même enrôlé avant.
- **Refus** : un cookie `appareil` qui ne vaut plus (révoqué, expiré, enrôlement désactivé) rend 401
  `{"erreur": …, "appareil_refuse": true}` et efface le cookie (`Max-Age=0`) : le navigateur revoit la page
  d'invitation. La révocation (`revoquer`) relit et réécrit `appareils.json` ; chaque requête le relit : effet
  immédiat. Un appareil n'a que les droits du demandeur (colonne « appareil » de §22.5, `role_effectif`) ; le mot de
  passe d'un appareil n'existe pas (`POST /api/mot-de-passe` répond 403 « mot de passe actuel incorrect ») et
  `POST /api/deconnexion` ne le révoque pas (seul le responsable révoque un appareil).
- **Oubli** : à chaque écriture, les invitations finies depuis plus de 30 jours et les appareils révoqués ou expirés
  dont la dernière activité date de plus de 30 jours sont retirés du fichier.
- **Journal des connexions** : `invitation` (qui = le responsable), `appareil` (qui = `appareil:<id>`, à
  l'enrôlement), `revocation` (qui = `appareil:<id>` ou `invitation:<id>`, adresse et agent du responsable).

### 22.4 API d'accès (`/api/connexion` et suivantes)

| Méthode et chemin | Qui | Réponse |
| --- | --- | --- |
| `GET /api/session` | tous | `{"comptes": bool, "session": null \| {"identifiant", "role", "prenom", "nom", "technicien_id", "a_changer", "appareil": bool, "langue"}}` (`langue` : celle du compte si c'est une langue déclarée, sinon "" ; toujours "" pour un appareil, T298) ; sans comptes : `{"comptes": false, "session": null}` |
| `POST /api/connexion` | tous | corps `{"identifiant", "mot_de_passe", "rester": bool}` → 200 `{"comptes": true, "session": {…}}` + cookie, 401, 429 ; 400 corps invalide |
| `POST /api/deconnexion` | session | 200 `{"comptes": true, "session": null}`, cookie effacé (`id=; …; Max-Age=0`) |
| `POST /api/mot-de-passe` | session | `{"actuel", "nouveau"}` → 200 comme la connexion (session neuve, toutes les autres sessions du compte fermées, « rester » gardé) ; 400 si le nouveau est trop court, trop long ou égal à l'actuel ; 403 si l'actuel est faux (compté comme un échec de connexion) ; 429 pendant un blocage. T298 : `{"langue": code}` **seul** → la langue du compte de la session (jamais un autre), sans mot de passe demandé ni session fermée : 200 `{"comptes": true, "session"}` à jour ; 400 `comptes.langue_inconnue` hors liste (rien d'écrit) ; `langue` avec tout autre champ (`actuel`, `nouveau`…) → 400 `sessions.langue_seule`, rien de changé ni compté ; 403 pour un appareil enrôlé (`sessions.langue_appareil`) et un mot de passe provisoire |
| `POST /api/enroler` | tous (route publique) | `{"invitation", "nom"}` → 200 `{"comptes": true, "session": {…, "appareil": true}}` + cookie `appareil` (un an) ; 401 invitation inconnue, expirée ou révoquée ; 403 enrôlement désactivé (`demandeurs_avec_compte`) ; 400 corps ou nom invalide |
| `GET /api/acces/comptes` | responsable | `{"comptes": [ … ]}` par `compte_public` : jamais d'empreinte, de sel ni d'algorithme |
| `POST /api/acces/comptes` | responsable | `{"prenom", "nom", "role", "technicien_id"}` → 200 `{"compte", "mot_de_passe_provisoire"}` : 16 caractères, `a_changer` vrai, rendu une seule fois (jamais écrit dans un fichier, le journal ni la console) ; 400 champ inconnu ou manquant, rôle inconnu, technicien absent de `techniciens.csv` |
| `POST /api/acces/comptes/<identifiant>` | responsable | `{"action": "modifier", "prenom", "nom", "role", "technicien_id"}`, `{"action": "reinitialiser"}` (rend `mot_de_passe_provisoire` une seule fois), `{"action": "desactiver"}` ou `{"action": "activer"}` → 200 `{"compte"}` ; 400 action inconnue ou s'il ne restait plus aucun responsable actif, 404 compte inconnu |
| `GET /api/acces/invitations` | responsable | `{"invitations": [{"id", "cree_le", "expire_le", "revoquee", "valide"}], "appareils": [{"id", "libelle", "nom_demandeur", "cree_le", "vu_le", "revoque", "valide"}], "enrolement_actif": bool}`, jamais d'empreinte |
| `POST /api/acces/invitations` | responsable | sans corps, `{}` ou `{"heures": 1..168}` → 200 `{"invitation": {…}, "jeton", "chemin": "/#/enroler/<jeton>"}`, le jeton rendu une seule fois ; 400 heures hors bornes ou champ inconnu |
| `POST /api/acces/invitations/<id>/revoquer` | responsable | 200 `{"invitation", "revoquee": true}` ; 404 inconnue |
| `POST /api/acces/appareils/<id>/revoquer` | responsable | 200 `{"appareil", "revoque": true}` : 401 dès la requête suivante de l'appareil ; 404 inconnu |
| `POST /api/acces/appareils/revoquer-tous` | responsable | 200 `{"appareils_revoques": [ids]}` |
| `POST /api/acces/deconnecter-partout` | responsable (ou soi-même) | sans corps ou `{}` : toutes ses propres sessions, la courante comprise (cookie effacé) ; `{"identifiant": X}` pour un autre compte : responsable seulement (403 sinon), 404 compte inconnu ; 200 `{"identifiant", "sessions_fermees"}` |
| `GET /api/acces/journal` | responsable | `journal-acces.csv` tel quel (`text/csv`, `Content-Disposition: attachment`), l'en-tête seul tant qu'il n'existe pas |
| `GET /api/ia/reglages` | technicien, responsable | `{"fournisseur", "url", "cle_reglee": bool, "en_ligne": bool, "portee"}`, jamais la clé (§22.12) |
| `GET /api/installation/<etape>` | responsable, PC serveur seulement | `etat`, `fiche` (§22.10) ; 404 « Adresse inconnue dans l'API. » à tout client qui n'est pas 127.0.0.1 ou qui est mandaté, avant tout contrôle d'accès |
| `POST /api/installation/<etape>` | responsable, PC serveur seulement | `situation`, `portee`, `compte`, `certificat`, `tailscale`, `demarrage`, `sauvegardes`, `deplacer`, `terminer` (§22.10) ; même 404 vu du réseau |

Toutes les écritures gardent l'en-tête `X-Prevo: 1` (anti-CSRF) en plus de la session.

Contrôle d'accès (T151) : un point unique, `GestionnaireRequetes.controler_acces`, avant la lecture du corps (audit F2).
Ordre dans `traiter` : en-tête `Host`, chemin, accès (`verifier_session`, puis 401 ou 403), `X-Prevo` sur toute écriture
(connexion comprise), lecture du corps, aiguillage. Un refus prononcé avant la lecture lit et jette au plus 64 Ko de
corps, pour que le navigateur reçoive la réponse ; au-delà, ou sans `Content-Length` lisible, rien n'est lu et la
connexion est fermée après la réponse. Toutes les routes sont déclarées dans `ROUTES_API` de `serveur.py`
(`(méthode, motif)` → fonction du gestionnaire ; `<table>` et `<nom>` valent un segment), que lisent l'aiguillage, le
contrôle d'accès et `tests/test_acces_sessions.py` : une route ajoutée est fermée sans session dès sa déclaration.

- Routes publiques (`ROUTES_PUBLIQUES`) : `GET /api/ping`, `GET /api/session`, `POST /api/connexion` (le navigateur
  détecte le serveur par `/api/ping` avant toute connexion). Toute autre route `/api/…`, adresse inconnue comprise,
  rend 401 `{"erreur": "Connexion nécessaire : votre session est absente ou a expiré."}` sans session valide. Les
  fichiers de l'application restent publics.
- **Mot de passe provisoire** (`a_changer`) : la session existe, mais toute route autre que `GET /api/session`,
  `POST /api/mot-de-passe` et `POST /api/deconnexion` (`ROUTES_MOT_DE_PASSE_PROVISOIRE`) rend 403 `{"erreur": "Mot de
  passe provisoire : choisissez votre mot de passe d'abord."}` ; le serveur l'impose, l'écran de connexion (T155,
  ci-dessous) le fait choisir avant toute lecture de table.
- Sans comptes (portée « ce PC », tous les tests des lots 1 à 6) : aucun contrôle de plus ; connexion, déconnexion,
  mot de passe, « déconnecter partout » et les routes des comptes et du journal rendent 400 avec un message clair
  (jamais 500).
- Le cookie porte `Secure` quand la requête arrive en https (`en_https()` du gestionnaire, que T164 étendra au
  mandataire). Le rôle (403) est vérifié dans `controler_acces` par `verifier_role` (T152, §22.5), après la session et
  le mot de passe provisoire ; le jeton d'appareil est reconnu dans `verifier_session` (`verifier_appareil`, T153,
  §22.3).
- Routes des comptes (T152, pour Équipe › Accès de T156) : `<identifiant>` vaut un segment ; création, modification,
  réinitialisation et désactivation passent par les fonctions de T150 (`creer_compte`, `modifier_compte`,
  `reinitialiser_compte`) et vont au journal des connexions (`creation`, `modification`, `reinitialisation`, `qui` = le
  compte touché, adresse et agent de la requête du responsable). Un rôle changé vaut dès la requête suivante de ses
  sessions (le compte est relu à chaque requête) ; un compte désactivé perd ses sessions.

Côté navigateur (`js/stockage-serveur.js`, T154) : toute réponse ≥ 400 autre que 409 devient une
`Donnees.ErreurStockage` portant `codeHttp` ; un **401** (session absente ou expirée, appareil refusé) porte aussi
`sessionAbsente` et `appareilRefuse`, et l'adaptateur émet sur `document` l'événement `prevo:session-absente`
(`StockageServeur.EVENEMENT_SESSION_ABSENTE`, `detail: { message, appareilRefuse }`, au plus un par seconde) que
`App` écoute (écran de connexion, T155) ; un **403** garde le message du serveur (« Accès refusé : … »). `adaptateur.session()`
rend `GET /api/session` en camelCase (`technicienId`, `aChanger`). Tests (`tests/commun.py`, CS119) :
`ServeurPrevo(comptes=True, reglages={…})` écrit les trois comptes de `COMPTES_DE_TEST` (nicolas.briand responsable,
julien.moreau technicien lié à TEC-0001, lea.martin demandeur) dans la copie et `--config` à « comptes » ;
`serveur.session(role)` rend le cookie d'une session, `serveur.poser_session(contexte, role)` le pose dans un
contexte Playwright ; l'usage par défaut (`ServeurPrevo()`, portée « ce PC ») ne change pas.

**Écran de connexion** (`#ecran-connexion` d'`index.html`, `js/modules/connexion-ecrans.js`, objet `Connexion`,
`css/modules/connexion.css`, T155, CS124) : en mode serveur avec les comptes exigés, `App.ouvrirAvec` lit
`adaptateur.session()` avant `Donnees.chargerTout()` (sinon chaque table répondrait 401, ou 403 avec un mot de passe
provisoire et la base paraîtrait vide). Sans session → `App.demanderConnexion(options)` montre l'écran (état
`'connexion'`) et attend la promesse de `Connexion.demander(options)` : la session en camelCase, une fois la personne
connectée **et** son mot de passe choisi s'il était provisoire. Trois panneaux, un seul visible :

- **Connexion** : identifiant, mot de passe, case « Rester connecté sur cet appareil » (aide = `AccesTextes.options.
  session_longue_jours.aide`, T169), « Se connecter » (`POST /api/connexion`) ; le nom du poste n'est plus demandé.
  Message du serveur tel quel : 401 « Identifiant ou mot de passe incorrect. », 429 avec le temps restant
  (`attente_secondes`, sinon `Retry-After`) : bouton désactivé le temps dit, compte à rebours à la suite du message.
  Le champ du mot de passe est vidé à chaque réponse ; champs tactiles de 48 px à 1280 comme à 375 px.
- **Enrôlement** (page ouverte sur `#/enroler/<jeton>` sans session, D125, T153) : « Entrez votre nom » →
  `POST /api/enroler` `{invitation, nom}` ; 200 → demandeur sans mot de passe, route remplacée par `#/accueil` ; 401 →
  message du serveur ; 403 (enrôlement désactivé) → message et champs de connexion classiques ; « J'ai un compte »
  revient aux champs classiques. Un appareil enrôlé (cookie `appareil`, `session.appareil` vrai) ne voit jamais
  l'écran tant que son cookie vaut ; refusé (401 `appareil_refuse`, pendant l'usage ou détecté au démarrage par une
  lecture de `/api/versions` sans session, `GET /api/session` étant publique) → écran de connexion avec le bandeau
  `#connexion-appareil-refuse` « Cet appareil n'est plus autorisé : demandez une nouvelle invitation ».
- **Mot de passe** (`a_changer`, au démarrage comme après une connexion) : actuel, nouveau, confirmation, règles du
  serveur affichées (12 à 256 caractères, aucune règle de composition, phrase de passe conseillée, indication par la
  longueur) ; `POST /api/mot-de-passe` ; 400, 403 (« Mot de passe actuel incorrect. »), 429 tels quels ; « Se
  déconnecter » ferme la session provisoire et revient aux champs classiques.

Bandeau `#connexion-motif` quand l'écran revient pendant l'usage (message du 401). `Connexion.deconnecter()` =
`POST /api/deconnexion`. `App` expose `App.session` (copie, `null` sans comptes), `App.comptesExiges()`,
`App.demanderConnexion(options)`, `App.deconnecter()`. Test : `tests/test_acces_ecrans.py` (serveur réel en mode
comptes : connexion à 1280 et 375 px, mauvais mot de passe, « rester », provisoire, technicien, appareil enrôlé puis
révoqué, enrôlement désactivé, déconnexion et session fermée ailleurs avec la route gardée, sans comptes inchangé).

Écran **Équipe › Accès** (`#/equipe/acces`, `js/modules/equipe-acces.js`, objet `EquipeAcces`, T156, CS124) :
responsable seulement (`profils: ['responsable']`, renvoyé à l'accueil sinon), en mode serveur ; bouton « Accès »
dans l'en-tête de l'écran Équipe (responsable, mode serveur). Sans comptes exigés (`GET /api/session` →
`comptes: false`), l'écran dit qu'il n'y a rien à gérer. Trois onglets (`?onglet=comptes|appareils|journal`),
chacun relu sur le serveur à chaque ouverture :

- **Comptes** : tableau par `GET /api/acces/comptes` (identifiant, personne, rôle, technicien lié, état « Actif » /
  « Désactivé » / « Mot de passe provisoire ») ; « Créer un compte » (prénom obligatoire, nom, rôle, technicien lié
  obligatoire pour un technicien et refusé pour un autre rôle, `POST /api/acces/comptes`) ; par ligne « Modifier… »
  (`action: modifier`), « Réinitialiser… » (confirmation, `action: reinitialiser`), « Désactiver » (confirmation,
  danger) ou « Activer » ; jamais de désactivation de son propre compte depuis l'écran. Le mot de passe provisoire
  (création, réinitialisation) est montré une seule fois dans une fenêtre (`#acces-mot-de-passe-provisoire`,
  champ en lecture seule à noter) et n'est ni mémorisé ni réécrit dans la page. T298 : « Créer un compte » et
  « Modifier… » ont la liste « Langue » (`langue` : « Langue de l'installation », vide, puis les langues déclarées,
  chacune sous son nom dans sa langue).
- **Appareils** : « Inviter un appareil » avec la durée (1 h, 24 h, 3 jours, 7 jours → `heures` de
  `POST /api/acces/invitations`) ; la fenêtre montre une seule fois le QR (`UI.qrSvg`) et le lien
  `<adresse des QR>/#/enroler/<jeton>`, l'adresse étant celle des étiquettes (`App.urlFicheEquipement`, donc
  `adresse_qr` ou la première adresse de `/api/info`, la porte d'entrée) ; tableaux des invitations (créée, expire,
  état Valide / Expirée / Révoquée, « Révoquer ») et des appareils (personne, appareil, enrôlé le, dernière
  activité, état Actif / Révoqué / Expiré, « Révoquer », « Révoquer tous les appareils » avec confirmation) ;
  bandeau et bouton désactivé quand `enrolement_actif` est faux (demandeurs avec compte).
- **Journal des connexions** : `GET /api/acces/journal` relu et affiché (300 lignes les plus récentes : date, qui,
  événement en badge, adresse et colonne Tailscale, navigateur), « Exporter (CSV) » télécharge le fichier tel que
  le serveur le sert (`UI.telecharger`).

Les appels passent par `fetch` avec `X-Prevo: 1` (le serveur vérifie session et rôle) ; une erreur du serveur
s'affiche avec son message. Test : `tests/test_acces_ecrans_equipe.py` (serveur réel en mode comptes, session
posée en cookie par `poser_session` ; l'écran de connexion lui-même est testé par `tests/test_acces_ecrans.py`, T155).

### 22.5 Rôles par route (D126)

`ROLES_PAR_ROUTE` dans `serveur.py`, appliquée par `verifier_role` dans `controler_acces` (T152) : quand `comptes` est
vrai, toute route `/api/` exige une session ou un appareil (401), puis le rôle : 403 `{"erreur": "Accès refusé : …"}`,
au message qui dit ce qui est réservé et à qui, avant `X-Prevo` et la lecture du corps. La table est recopiée ici et
dans `tests/test_acces_roles.py`, qui en joue chaque case (vraies sessions de demandeur, technicien et responsable ;
appareil simulé dans ce test, appareil réellement enrôlé dans `tests/test_acces_appareils.py`, T153) et vérifie que
ce tableau dit la même chose : une route ajoutée à `ROUTES_API` sans sa ligne fait échouer le test.

| Route | demandeur | appareil | technicien | responsable |
| --- | --- | --- | --- | --- |
| `GET /api/ping` | oui | oui | oui | oui |
| `GET /api/session` | oui | oui | oui | oui |
| `POST /api/connexion` | oui | oui | oui | oui |
| `POST /api/deconnexion` | oui | oui | oui | oui |
| `POST /api/mot-de-passe` | oui | oui | oui | oui |
| `GET /api/info` | oui | oui | oui | oui |
| `GET /api/versions` | oui (ses tables seulement) | oui (ses tables seulement) | oui | oui |
| `POST /api/acces/deconnecter-partout` | oui (soi-même) | oui (soi-même) | oui (soi-même) | oui |
| `GET /api/acces/comptes` | non | non | non | oui |
| `POST /api/acces/comptes` | non | non | non | oui |
| `POST /api/acces/comptes/<identifiant>` | non | non | non | oui |
| `GET /api/acces/journal` | non | non | non | oui |
| `POST /api/enroler` | oui | oui | oui | oui |
| `GET /api/acces/invitations` | non | non | non | oui |
| `POST /api/acces/invitations` | non | non | non | oui |
| `POST /api/acces/invitations/<id>/revoquer` | non | non | non | oui |
| `POST /api/acces/appareils/<id>/revoquer` | non | non | non | oui |
| `POST /api/acces/appareils/revoquer-tous` | non | non | non | oui |
| `GET /api/csv/<table>` | tables du demandeur | tables du demandeur | toutes (colonnes retirées) | toutes |
| `PUT /api/csv/<table>` | `demandes` (ajout seulement) | `demandes` (ajout seulement) | toutes sauf `parametres`, `techniciens`, `fournisseurs`, `habilitations` | toutes |
| `POST /api/csv/<table>/ajout` | `demandes`, `journal` | `demandes`, `journal` | toutes sauf `parametres`, `techniciens`, `fournisseurs`, `habilitations` | toutes |
| `GET /api/documents/<nom>` | photos de demandes, documents des équipements (sauf documents réservés) | photos de demandes, documents des équipements (sauf documents réservés) | oui (sauf documents réservés) | oui |
| `PUT /api/documents/<nom>` | photos de demandes | photos de demandes | oui | oui |
| `POST /api/sauvegarde` | non | non | non | oui |
| `POST /api/sauvegarde/tester` | non | non | non | oui |
| `GET /api/sauvegardes` | non | non | non | oui |
| `POST /api/restauration` | non | non | non | oui |
| `POST /api/ia` | non | non | oui | oui |
| `GET /api/ia/reglages` | non | non | oui | oui |
| `GET /api/installation/<etape>` | non | non | non | oui |
| `POST /api/installation/<etape>` | non | non | non | oui |

Tables du demandeur : `localisations`, `equipements`, `demandes`, `compteurs`, `releves`, `codes_defaillance`, `parametres`, `wiki_pages`.

Précisions de T152 :

- **Contrôle** : `verifier_role(config, identite, route, segment)`, après la session et le mot de passe provisoire ; une
  adresse inconnue ou une méthode non prévue répond 404 ou 405 comme avant ; un rôle inconnu (`comptes.json` abîmé)
  n'ouvre rien. Colonne « appareil » : téléphone enrôlé (D125, T153, §22.3), droits du demandeur (`role_effectif`) ;
  `POST /api/enroler` est publique (l'invitation décide), les invitations et les révocations sont au responsable. « Déconnecter
  partout » pour un autre compte reste réservé au responsable dans la route elle-même (§22.4).
- **Technicien, lecture** (D126, CS122 « ni taux horaire ni prix ») : `techniciens` sans `taux_horaire`, `articles` et
  `achats` sans `prix_unitaire` (`COLONNES_CACHEES_PAR_ROLE`) ; `achats` en plus de la consigne, car une demande d'achat
  y recopie le prix de l'article. Les colonnes sont retirées des octets renvoyés (CSV réécrit au format §3.1, en-tête
  compris, nom de colonne reconnu comme à la lecture tolérante) ; `X-Version` est celle du fichier entier, pour que les
  écritures restent possibles.
- **Technicien, écriture** — écart voulu au refus prévu d'abord : un `PUT` du technicien sur une table dont il ne voit
  pas toutes les colonnes (`articles`, `achats`) n'est pas refusé ; le serveur remet chaque colonne cachée depuis le
  fichier actuel, ligne par ligne d'après `id`, vide pour une ligne nouvelle (`remettre_colonnes_cachees`), puis écrit.
  Raison : la sortie d'une pièce réécrit `articles` pour la colonne `stock` (`Magasin.mettreAJourStocks`, dont l'échec
  serait rattrapé sans bruit et laisserait vieillir la colonne). Les prix restent intouchables par le technicien : un
  prix forgé est remplacé par celui du fichier. Un ajout (`POST …/ajout`) a ses colonnes cachées vidées. `PUT` et ajout
  sont refusés sur `parametres`, `techniciens`, `fournisseurs` (l'ajout aussi, sinon il contournerait le refus du `PUT`).
- **Demandeur, lecture** : liste fermée `TABLES_DU_DEMANDEUR` (D126 : aucune table de coût ni de techniciens) — les six
  du CDC, plus `compteurs` et `releves` pour la carte « Compteurs » de la fiche d'équipement ouverte par le QR. `wiki_pages`
  arrive sans ses lignes de `type` `technicien` ou `intervention` (D114 ; filtre de garde : le format 3 ne range pas ces
  pages, calculées). `GET /api/versions` ne liste que ses tables. Côté navigateur, `stockage-serveur.js` voit une table
  refusée (403) comme absente : `Donnees.chargerTout` aboutit et ses écrans montrent ce que ses tables permettent ; sans
  `ordres_travail` ni `articles` (coûts, techniciens), l'historique des OT de la fiche d'équipement, le statut de l'OT d'une
  demande, les causes fréquentes, les pièces de rechange et les couches du wiki tirées des OT restent vides.
- **Demandeur, écriture** : `PUT /api/csv/demandes` en ajout seulement (l'écran Signaler écrit par `Donnees.modifier`) :
  chaque ligne actuelle doit s'y retrouver inchangée (même `id`, mêmes valeurs à la forme près : casse, accents, espaces
  de bord, apostrophe de protection, écriture d'une date ou d'une date-heure, virgule décimale, soit ce que la lecture
  tolérante change), et les seules lignes nouvelles ont un `id` absent du fichier et unique, le statut `Nouvelle` et
  `motif_decision`, `date_decision`, `ot_id` vides ; sinon 403. Les lignes actuelles sont réécrites telles qu'elles sont
  dans le fichier (rien d'une ligne existante ne vient du demandeur), puis les nouvelles. Ce contrôle suit celui de la
  version : une version périmée rend toujours 409. `POST /api/csv/demandes/ajout` suit les mêmes règles pour les lignes
  ajoutées, `POST /api/csv/journal/ajout` est permis ; tout autre `PUT` ou ajout : 403.
- **Documents du demandeur** : lecture des photos de demandes (`photo-AAAAMMJJ-HHMMSS-XXXX.<jpg|jpeg|png|gif|webp>`, nom
  donné par `nomPhoto`, enregistré derrière le préfixe `AAAAMMJJ-HHMMSS-` que le serveur impose (audit F4, §22.12) :
  `MOTIF_PHOTO_DE_DEMANDE` accepte ce préfixe en option, l'envoi étant contrôlé sur le nom demandé, sans préfixe) et des
  documents des équipements (noms de la colonne `document`
  d'`equipements.csv`, relue à chaque requête) ; envoi des seules photos de demandes. « Ses » demandes : le serveur ne sait
  pas relier une photo à la personne qui l'a prise (`demandeur` est un nom libre) ; le demandeur lit donc toutes les photos
  de demandes.
- **Réponses provisoires de T445** (questions 2 et 3 du L3, nuit du 08 au 09/11/2026, **à confirmer par Nicolas**) :
  - *Habilitations* : `habilitations` s'écrit par le responsable seul ; le `PUT` et l'ajout du technicien sont refusés
    (403 `acces.table_du_responsable`, comme `parametres`) ; il la lit toujours. Aucun de ses écrans ne l'écrit (boutons
    de l'Équipe au responsable, import réservé au responsable).
  - *Documents réservés* : un document cité par `habilitations.justificatif` ou `contrats_prestataires.document`
    (relus à chaque requête, apostrophe de protection retirée, casse ignorée car le dossier ne la distingue pas sous
    Windows ni macOS) n'est servi qu'au responsable : `GET /api/documents/<nom>` répond 403 `acces.document_ferme` au
    technicien, au demandeur et à l'appareil, même si le document est aussi cité ailleurs. Les autres documents ne
    changent pas (documents de garantie lisibles du technicien) ; l'envoi (`PUT`) non plus.
  - *Limite connue (RG8)* : le blocage RG8 reste tenu par l'application (§10) ; le serveur n'en a aucune copie. Un
    compte technicien qui appelle l'API directement peut encore écrire `ordres_travail` et s'affecter un OT sans
    l'habilitation requise ; à l'écran, il n'en a aucun moyen (CS178). Même limite que RG3 et RG4.
  - *Annuler* : vider `TABLES_DU_RESPONSABLE_PROVISOIRES` ou `DOCUMENTS_DU_RESPONSABLE_PROVISOIRES` dans `serveur.py`
    (seul endroit), puis remettre ce tableau et `tests/test_droits_format4.py`.
- **Sans comptes** : rien ne change (aucune colonne ni ligne retirée, toutes les versions, aucune règle d'écriture).

`App.profil` est déduit de `/api/session` ; l'écran de profil de 1.2 ne sert qu'en portée « ce PC » et en modes dossier
et démo. **L'IA est réservée aux techniciens et au responsable** (arbitrage de Nicolas du 2026-10-28, qui revient sur
la précision de T158) : `POST /api/ia` et `GET /api/ia/reglages` répondent 403 au demandeur et à l'appareil enrôlé ;
côté navigateur, `Ia.permiseAuProfil()` est faux pour un demandeur en mode comptes, donc `Ia.active()` aussi : l'écran
Signaler ne lui propose pas « Proposer avec l'IA » et aucun réglage du serveur n'est lu pour lui. Le relais n'appelle que
le fournisseur réglé sur le PC serveur et un fournisseur en ligne reste soumis à `ia_en_ligne`.

### 22.6 Porte d'entrée et certificat local (D127, CS125, CS126, CS137)

- **Deux écouteurs** hors de la portée « ce PC » : `port_http` (la porte) et `port_https` (l'application).
- **Porte**, pour un client qui n'est ni 127.0.0.1 ni mandaté : sert seulement `/` et toute route d'application
  (la page `acces/porte.html`, autonome, charte de Prévo, sans donnée), `/acces/porte.js`, `/acces/porte.css`,
  `/acces/captures/*`, `/acces/ca.crt` (certificat de l'autorité locale, `application/x-x509-ca-cert`) ; toute
  autre route, `/api/` comprise, répond par la page de porte (200) sans rien lire. `porte.js` interroge
  `https://<même hôte>:<port_https>/api/ping` (2 s) : réponse ⇒ redirection vers la même route en https
  (`location.replace`, la route `#/…` gardée) ; échec ⇒ étapes « Faites confiance au PC atelier » du système
  reconnu (`navigator.userAgent` : Android, iPhone/iPad, sinon les deux au choix), numérotées, une par écran du
  téléphone, captures, bouton « Réessayer ».
- **Langue de la porte et de la connexion** (T297, D148 ; conception validée par Nicolas le 07/11) : serveur.py pose
  la langue de l'installation dans l'attribut `data-langue-installation` de `porte.html` (langue_defaut déclarée et
  bien formée, `MOTIF_CODE_LANGUE` + `langues_declarees()`, sinon « fr ») et de `index.html` (seulement quand
  langue_defaut est réglée ; sans elle, la page garde la langue du navigateur, D150) ; `js/i18n-chargeur.js` la lit
  (`I18n.langueDeLaPage`) : choix de l'appareil (`prevo.langue`), sinon installation, sinon français. Sélecteur en haut
  de la porte et de l'écran de connexion, sans menu : un globe et les langues écrites chacune dans sa langue, aucun mot
  autour (`aria-label` « Langue / Language »). Sans session, la porte sert un seul fichier de plus, `js/i18n-chargeur.js`
  (texte public, il ne lit que le stockage de l'appareil) ; aucune route, aucune donnée, `POLITIQUE_PORTE` inchangée.
  La porte (http) et l'application (https) n'ont pas le même stockage : la porte passe sa langue à l'application dans
  l'adresse qu'elle ouvre déjà (T324, Nicolas, 07/11 : `?langue=<code>`, et `langue_neuve=1` si elle vient d'être
  choisie sur la porte ; `Porte.adresseCible`) ; `js/i18n-chargeur.js` la reprend comme choix du poste quand il n'en a
  pas, ou quand elle vient d'être choisie (un choix fait ensuite dans l'application n'est pas écrasé), puis retire les
  deux paramètres de l'adresse (`history.replaceState`) ; valeur hors des langues déclarées : ignorée. Ordre : langue
  du compte une fois connecté, sinon choix de la porte ou du poste, sinon langue de l'installation. Aucune adresse
  nouvelle : le serveur sert la même page.
- **Langue de la console et du journal du serveur** (T297, D157) : français ou anglais selon langue_defaut (fr → fr,
  toute autre langue déclarée → en), sinon la langue du système (`locale.getlocale()`) ; choisie au démarrage
  (`choisir_langue_console`) : un changement dans Paramètres vaut au redémarrage suivant. Chaque message de console est
  un `traduisible` ; en anglais, `afficher` écrit la clé `serveur.<code>` de `js/i18n/en.js` (`lire_textes_anglais`,
  petit lecteur, aucun eval ; le français si la clé manque). Restent en français : `--aide`, le journal des requêtes,
  le détail des pertes d'un fichier abîmé. Les lanceurs (`Lancer_GMAO.bat`, `Reinitialiser_mot_de_passe.bat`,
  `lancer.sh`) écrivent leurs lignes d'avant Python en français puis en anglais.
- **Adresses données par Prévo** (QR d'accueil, étiquettes, fiche d'accès, guide, `/api/info`) : toujours la porte
  (`http://<adresse>:<port_http>/`) ; l'adresse https n'est jamais affichée.
- **Certificat local** : `outils-tiers/mkcert.exe` (ou `mkcert` sur Linux/macOS) dont l'empreinte SHA-256 est
  comparée à `outils/empreintes-tiers.json` avant toute exécution (écart ⇒ refus) ; `CAROOT` =
  `donnees/acces/autorite/` ; `mkcert -install` dans l'élévation (§22.9) ; certificat dans
  `donnees/acces/certificat.pem` et `cle.pem` pour l'IP courante, `<nom>.local`, `<nom>`, `localhost`, 127.0.0.1 et
  les `noms` ; régénéré au démarrage si l'IP ou les noms ont changé. `rootCA-key.pem` n'est jamais lu ni servi par
  Prévo.
- **En-têtes** (§22.13) sur l'application ; HSTS seulement pour un nom de la liste `noms`.
- **Précisions du code (T161).** `demarrer_serveur` : portée « ce PC » ⇒ un seul écouteur sur `port_http`
  (http, ou https avec `certificat`/`cle`, lot 4) ; sinon `ServeurPrevo(porte=True)` sur `port_http` (jamais de TLS)
  et l'application sur `port_https` (le suivant libre jusqu'à +20 pour chacun ; `config.porte`, `config.port_https`),
  la porte dans un fil à part. `certificat_du_serveur` : `certificat`/`cle` donnés, sinon hors de « ce PC »
  `preparer_certificat_local` avec `executable_mkcert` (T167 : la variable d'environnement `PREVO_MKCERT` quand elle
  est posée — tests, `tests/faux_mkcert.py` ; un chemin qui n'existe pas vaut « absent » —, sinon `trouver_mkcert`)
  (`certificat_auto`, drapeau `_https_auto` posé par
  `reglages_du_lancement` pour `verifier_regles_portee`) ; mkcert absent, empreinte fausse, échec ou
  `certificat_auto` faux ⇒ « Démarrage refusé », code 2, aucun écouteur ouvert. `GestionnaireRequetes` :
  `client_de_confiance()` (127.0.0.1, ::1 ; T164 y ajoute le mandataire attesté), `sur_la_porte()`, `servir_porte`
  (après `hote_autorise` et `analyser_chemin`, avant tout contrôle d'accès : `fichier_de_la_porte` — `acces/**` sauf
  `porte.html`, `favicon.svg`, `css/polices/**`, `js/i18n.js` et `js/i18n/**` (textes de l'interface, T234), s'ils
  existent —, `/acces/ca.crt`, sinon `page_de_porte()` ; un PUT
  ou POST n'est jamais lu, connexion fermée après la réponse). La page sur le disque porte `data-port-https=""`, rempli
  au service par `port_https` ; sa politique est `POLITIQUE_PORTE` (`connect-src 'self' https://<hôte de la
  requête>:<port_https>`, `img-src 'self' data:`), jamais HSTS. `/acces/ca.crt` (porte et application) :
  `certificat_de_l_autorite`, `Content-Disposition: attachment; filename="prevo-ca.crt"`, 404 `MESSAGE_SANS_AUTORITE`
  sans autorité locale. `acces/` est dans `DOSSIERS_PUBLICS` (§14.7). `Configuration.schema` vaut `http` dès que la
  porte est ouverte : `adresse_locale`, `adresses_reseau`, la console et `/api/info` (qui rend aussi `porte` vrai,
  d'où le rappel « Faites confiance au PC atelier » de la carte « Connecter un téléphone ») donnent la porte ; le port
  https n'apparaît sur la console que comme un numéro de port. Corrections du 28/10 (recette du lot 7) : `/api/info`
  rend `ce_pc_seulement` vrai en portée « ce PC » (écoute 127.0.0.1 sans mandataire : aucun téléphone ne joint
  Prévo) ; la carte « Connecter un téléphone » ne montre alors pas de QR, l'écran des étiquettes le dit et la console
  n'annonce aucune adresse réseau ; l'adresse des QR reste celle du PC sur `port_http`, qui répondra dès que Prévo
  sera ouvert au Wi-Fi (la porte garde ce port) ; derrière un mandataire sur ce PC, `adresses_reseau` vaut
  `https://<nom>/` pour chaque nom accepté. `porte.js` : `fetch` en mode `no-cors` (le serveur
  n'envoie aucun en-tête CORS : seule compte la réponse du réseau), `AbortController` à 2 s, `location.replace(origine
  https + pathname + search + hash)` ; système par `navigator.userAgent` (`android` ; `iPhone|iPad|iPod` ou
  `Macintosh` tactile ⇒ iPhone ; sinon choix) ; sans autorité (`/acces/ca.crt` 404), le bouton de téléchargement est
  remplacé par l'explication. Illustrations `acces/captures/<systeme>-<n>-<etape>.svg` (schémas, à remplacer par les
  captures de recette sous le même nom) ; leur version anglaise, même nom, dans `acces/captures/en/`, prise par la
  porte dans toute autre langue que le français (T341 ; D163 révisée le 08/11 : les illustrations suivent la langue
  de la porte). Tests : `tests/atelier.py` (`ServeurAtelier` : 0.0.0.0, comptes, faux mkcert
  pour l'adresse réseau du PC, le téléphone simulé se connecte à cette adresse et le PC à 127.0.0.1 ; aucune sortie du
  PC), `tests/test_acces_porte.py`.

### 22.7 Derrière un mandataire (D129, CS128)

`origine_mandatee(gestionnaire)` : si `mandataire` est vrai et que la connexion vient de 127.0.0.1 ou ::1 avec
`X-Forwarded-Proto` et `X-Forwarded-Host`, le protocole et l'hôte d'origine valent ceux des en-têtes (cookie
`Secure`, adresses, QR) et l'hôte doit être dans `noms` ; sinon la requête est un client direct et les en-têtes
sont ignorés. La porte sert alors l'application en http sur 127.0.0.1. Exemples de configuration dans
`docs/INSTALLATION.md` (`tailscale serve`, Caddy, nginx, IIS, Cloudflare Tunnel).

Précisions de T164 :

- **`origine_mandatee(gestionnaire)`** → `{'protocole', 'hote', 'adresse'}` ou `None`. Attestée seulement si
  `mandataire` est vrai, que la connexion vient de 127.0.0.1 ou ::1 (`ADRESSES_DE_CE_PC`) et qu'elle porte
  `X-Forwarded-Proto` (`http` ou `https`, première valeur d'une liste, casse ignorée) et `X-Forwarded-Host` (première
  valeur, minuscules, port gardé, refusé s'il contient une espace, `/`, `\`, `?` ou `#`) ; l'adresse d'origine est la
  dernière de `X-Forwarded-For` si elle se lit comme une adresse IP, sinon celle de la connexion. Posée dans
  `self.mandat` au début de chaque requête ; `None` pour un client direct ou `mandataire` faux : les en-têtes
  `X-Forwarded-*` sont alors ignorés, jamais crus.
- **Hôte d'origine** : après `Host`, `hote_autorise(mandat['hote'])` (adresse IP, `localhost`, nom du PC, `noms`) ;
  sinon 403 `MESSAGE_HOTE_ORIGINE_REFUSE` sur toute route, `/api/ping` compris.
- **Effets** : `en_https()` = protocole d'origine `https` (cookie `Secure`, HSTS pour un nom de `noms` par
  `hote_de_la_requete()`) ; `adresse_client()` = adresse d'origine (journal des connexions, ralentissement des
  échecs) ; `adresses_donnees()` : `/api/info` rend `adresse_locale` = `adresses_reseau[0]` =
  `<protocole>://<hôte d'origine>/` (QR, étiquettes, carte « Connecter un téléphone ») et `porte` faux pour une
  requête mandatée ; `client_de_confiance()` vrai : la porte (§22.6) sert l'application en http au mandataire. La
  colonne `tailscale` du journal garde la règle de T151 (`mandataire` vrai et connexion venue de ce PC), que la
  requête porte ou non les en-têtes `X-Forwarded-*`.
- **Tests** : `tests/mandataire_test.py` (`MandataireTest` : relais inverse en bibliothèque standard sur 127.0.0.1,
  qui ajoute `X-Forwarded-Proto`, `X-Forwarded-Host`, `X-Forwarded-For` et au choix `Tailscale-User-Login` ;
  `forwarded=False` pour un simple relais), `tests/test_acces_mandataire.py` (serveur en portée Intranet par
  `ServeurPrevo(comptes=True, reglages={'mandataire': True, 'noms': [...]})`).

### 22.8 Tailscale (D128, CS127)

`detecter_tailscale()` lance `tailscale version` et `tailscale status --json` (chemin standard de chaque système,
délai 5 s) : absent ⇒ `{"present": false}` ; présent ⇒ nom `Self.DNSName` sans le point final, état connecté,
expiration de clé (`Self.KeyExpiry`). L'assistant propose alors : ajouter le nom à `noms`, `tailscale serve --bg
--https=443 http://127.0.0.1:<port_http>`, vérifié par `tailscale serve status --json`, `mandataire` vrai,
`tailscale set --unattended=true` (Windows, sur clic), et affiche les deux rappels (expiration de clé dans la
console, veille). L'accueil du responsable signale un Tailscale déconnecté ou une clé qui expire sous 14 jours.
Aucune installation, aucune requête réseau de Prévo vers Tailscale ; les commandes sont injectables pour les tests
(`tests/faux_tailscale.py`).

Précisions de T165 (`serveur.py`, section « Tailscale ») :

- **Exécutable** : `executable_tailscale(executable)` — celui donné ; sinon la variable d'environnement
  `PREVO_TAILSCALE` (tests : le faux ; un chemin qui n'existe pas vaut « absent », pour qu'un test ne lance jamais le
  vrai : `ServeurPrevo` la pose ainsi par défaut) ; sinon le chemin standard du système (`CHEMINS_TAILSCALE` :
  `C:\Program Files\Tailscale\tailscale.exe`, `/usr/bin/tailscale`, `/Applications/Tailscale.app/Contents/MacOS/Tailscale`),
  puis le PATH. `lancer_tailscale(executable, arguments, delai)` : `subprocess.run` sans shell, `capture_output`,
  `timeout` (`DELAI_TAILSCALE_S` = 5), `CREATE_NO_WINDOW` sous Windows ; `ErreurTailscale` (raison lisible) si l'outil
  manque, dépasse le délai ou rend un code non nul ; refuse avant tout lancement `up`, `down`, `login`, `logout`,
  `install`, `update` (`COMMANDES_TAILSCALE_INTERDITES`).
- **`detecter_tailscale(executable=None, delai=5, maintenant=None)`** → `{"present": False, "raison"}` quand l'exécutable
  manque, que `tailscale version` échoue ou que le délai est dépassé ; sinon `{"present": True, "version", "connecte"
  (BackendState « Running »), "nom" (Self.DNSName sans le point final, minuscules ; None sans nom), "expiration_cle"
  (Self.KeyExpiry en heure locale `AAAA-MM-JJTHH:MM:SS` ; None si absente, vide, illisible ou date zéro de Go),
  "jours_avant_expiration" (entier, négatif si expirée ; None sans expiration), "serve" (`tailscale serve status
  --json` lu, None sinon), "raison"}`. Jamais d'exception vers l'appelant. `tailscale_attendu(reglages)` : `mandataire`
  vrai ou un nom en `.ts.net` dans `noms`.
- **Serveur** : `Configuration.tailscale` (None tant que la détection n'est pas attendue) et `tailscale_lu_a` ;
  `main` détecte une fois au démarrage quand `tailscale_attendu` (console : « Tailscale : <nom>, connecté, clé valable
  N jours » ou « non détecté (raison) », `resume_tailscale`) ; `GET /api/info` rend `tailscale` : `null` sans détection,
  sinon `{"present", "connecte", "nom", "jours_avant_expiration"}` seulement (jamais la sortie brute de `status`, ni la
  version, ni l'adresse d'un autre appareil), rafraîchi par `detecter_tailscale_pour` au plus une fois par
  `INTERVALLE_TAILSCALE_S` (10 minutes), dans le fil de la requête, sous `VERROU_TAILSCALE`.
- **Assistant (API Python pour T167)** : `preparer_tailscale(config, detection, systeme=None)` ne lance ni n'écrit
  rien → sans Tailscale `{"present": False, "raison", "telechargement"}` (lien officiel, montré seulement) ; sinon
  `{"present", "connecte", "nom", "adresse" (https://<nom>/), "noms" (nom ajouté s'il manque), "ajouter_nom",
  "mandataire": True, "serve" (texte) et "arguments_serve" (`serve --bg --https=443 http://127.0.0.1:<port_http>`),
  "unattended" (`tailscale set --unattended=true`, Windows seulement), "rappels" (expiration de clé dans la console,
  veille : D130)}`. `appliquer_tailscale(config, executable=None)` : détection, refus (`ok` faux, message) sans
  Tailscale ou sans connexion ; `modifier_configuration(chemin, {"noms", "mandataire": True})` (fichier de
  `reglages["_fichier"]` ; clés inconnues et `_aide` gardées, écriture atomique) ; puis `serve --bg …` lancée et
  vérifiée par `serve status --json` (`cible_serve_tailscale` : un `Handlers.*.Proxy` vers `http://127.0.0.1:<port>`
  ou `localhost`) → `{"ok", "serve", "message", "nom", "adresse"}` ; les réglages en mémoire ne changent pas (la
  configuration vaut au prochain démarrage), `config.tailscale` reprend la détection. Jamais `up`, jamais
  d'installation ; `activer_unattended(executable=None)` à part, sur un clic.
- **Accueil du responsable** (`accueil-bento.js`, mode serveur) : `afficherEtatServeur` lit `App.adaptateur.info()` une
  fois et pose `#alerte-copie-externe` (§22.11) et `#alerte-tailscale` (`UI.bandeau('attention')`, zone
  `#tailscale-zone` marquée `data-lu`) ; `Accueil.avertissementTailscale(tailscale)` (fonction pure) : « Tailscale est
  déconnecté : les téléphones hors de l'atelier ne joignent plus Prévo. » quand `present` et non `connecte`, sinon « La
  clé Tailscale expire dans N jours (aujourd'hui / a expiré) : désactivez l'expiration de clé dans la console Tailscale
  (Machines › <nom> › Disable key expiry)… » quand `joursAvantExpiration` ≤ 14 ; rien sinon. `stockage-serveur.js`
  `info().tailscale` = `{present, connecte, nom, joursAvantExpiration}` ou `null` (`tailscaleLu`).
- **Tests** : `tests/faux_tailscale.py` (`version`, `status --json`, `serve --bg --https=443 http://…` notée dans
  `FAUX_TAILSCALE_DOSSIER/serve.json`, `serve status --json`, `set --unattended=true` ; `up`/`install`… : code 1 ;
  variables `FAUX_TAILSCALE_ETAT` Running|Stopped|absent, `FAUX_TAILSCALE_NOM`, `FAUX_TAILSCALE_EXPIRATION`,
  `FAUX_TAILSCALE_ATTENTE` ; chaque lancement compté dans `lancements.txt`), `tests/test_acces_tailscale.py`.

### 22.9 Démarrer avec la machine (D130, CS129)

`produire_scripts_demarrage(config)` écrit, sans les exécuter, à côté de `serveur.py` :
`Installer_demarrage.ps1` (tâche `Prevo` `/sc onstart /delay 0000:30 /ru System /rl HIGHEST`, action
`python\pythonw.exe serveur.py --sans-navigateur` dans le dossier de Prévo ; règle `netsh advfirewall` entrante
`Prevo`, profil privé, `remoteip=localsubnet`, programme `pythonw.exe`, ports `port_http` et `port_https` ;
`mkcert -install` ; si `veille_desactivee`, `powercfg /change standby-timeout-ac 0`, `hibernate-timeout-ac 0`,
`monitor-timeout-ac 15`), `Retirer_demarrage.ps1` (l'inverse, et `powercfg` remis aux valeurs lues avant), et le
repli `onlogon` (tâche de l'utilisateur, sans droits). L'assistant lance `Installer_demarrage.ps1` par
`Start-Process powershell -Verb RunAs` après avoir affiché son contenu ; refus de l'élévation ⇒ repli proposé.
Linux : `prevo.service` (utilisateur `prevo`, `Restart=on-failure`, `ProtectSystem=full`, `ProtectHome=yes`,
`ReadWritePaths=<donnees>`) et les commandes à copier ; macOS : `pro.prevo.serveur.plist` (agent, `RunAtLoad`,
`KeepAlive`). Sans console, le serveur écrit `donnees/journal-serveur.log` (rotation 5 × 1 Mo) et expose son état
à `/api/installation/etat` (loopback).

### 22.10 Assistant d'installation (D131, CS130)

Sans `prevo.config.json`, `serveur.py` démarre en portée « ce PC » et ouvre `http://127.0.0.1:<port>/#/installation`.
Routes `/api/installation/<étape>` servies **seulement** à un client 127.0.0.1 non mandaté (404 sinon), écritures
avec `X-Prevo` : `etat`, `situation` (`seul` \| `equipe` \| `informaticien`), `portee`, `compte`, `certificat`,
`tailscale`, `demarrage`, `sauvegardes`, `deplacer` (copie vers `C:\Prevo`, vérification de chaque fichier, puis
relance depuis la nouvelle place), `terminer` (écrit la configuration, puis le serveur se relance avec elle) ; pour
Paramètres (T170) : `journal`, `reprendre`, `reglages`, `ia`, `annuler`. Écran
`installation-ecrans.js` (huit étapes, quatre textes chacune, « Régler autrement »), vue informaticien sur une page ;
fiche d'accès imprimable. Paramètres › Accès et installation (`parametres-acces.js`) refait chaque étape depuis le PC
serveur seulement (paragraphe « Paramètres › Accès et installation » ci-dessous). Migration 1.2 : CSV gardés ; profils mémorisés ignorés quand `comptes` est vrai (paragraphe
« Migration et dossier » ci-dessous, T171).

Contrat de l'API (T167, `serveur.py` section « Assistant d'installation ») — T168 (écran) et T170 (Paramètres) sont
écrits d'après lui :

- **Qui** : dans `traiter`, avant `controler_acces` et avant l'aiguillage, toute requête `/api/installation…` d'un
  client qui n'est pas 127.0.0.1 ou ::1, ou qui est mandaté (`self.mandat` non nul, §22.7), reçoit 404
  `{"erreur": "Adresse inconnue dans l'API."}`, identique à une route inconnue (`client_local()`) : l'assistant
  n'existe pas vu du réseau. La route n'est jamais publique : sans comptes exigés (premier lancement), rien n'est
  demandé ; avec comptes, la session du responsable est exigée comme partout (401, 403 : Paramètres › Accès et
  installation, T170). Écritures avec `X-Prevo`. `<etape>` inconnue : 404.
- **Brouillon** : `donnees/installation.json` (atomique, sous `VERROU_INSTALLATION` : une étape à la fois), clés =
  celles de `prevo.config.json` sauf `ia_cle` (`CLES_DU_BROUILLON` : jamais un secret) + `situation`, `etapes`,
  `mode_solo`, `solo_technicien_id`, `base_presente` (des CSV au départ de l'assistant, T171), `deplacement_refuse`
  (« Rester ici ») ; relu par `etat` (un rechargement ou un redémarrage avant « terminer » ne perd
  rien), copié avec Prévo par `deplacer`, supprimé par `terminer` ; illisible ⇒ comme absent. `ecoute` est toujours
  dérivée (`ecoute_du_brouillon`) : `127.0.0.1` en portée « ce PC » et quand un mandataire sur ce PC porte seul le
  https (réseau privé Tailscale sans certificat local, mandataire de l'entreprise : `mandataire` vrai sans
  `certificat_auto` ni fichiers), `0.0.0.0` sinon. Les étapes (`ETAPES_INSTALLATION` : `situation`, `portee`,
  `compte`, `certificat`, `tailscale`, `demarrage`, `sauvegardes`, `deplacer`) valent `fait`, `a_faire` ou
  `sans_objet` (`etapes_du_brouillon`) : `compte` et `certificat` sans objet sur « ce PC » (le compte reste proposé
  en Solo : il crée le technicien « moi »), `tailscale` hors de la portée `dehors`, `deplacer` hors de Windows ou
  déjà dans `C:\Prevo` ; un responsable actif vaut `compte` fait.
- `GET etat` → `{"configuration_presente", "configuration" (T170 : la configuration en cours, clés de
  `CLES_DU_BROUILLON` — jamais `ia_cle` — quand l'installation est terminée, null sinon : Paramètres montre chaque
  réglage avant tout brouillon), "portee", "situation", "etapes", "brouillon" (null sans brouillon),
  "csv_presents" (des CSV dans le dossier des données : migration 1.2), "nombre_csv", "derniere_modification"
  (`AAAA-MM-JJTHH:MM:SS` du CSV le plus récent, null sans CSV), "dossier" (celui de Prévo),
  "dossier_conseille" (`C:\Prevo` sous Windows, null ailleurs), "dans_dossier_conseille", "python_embarque"
  (`python/python.exe` présent), "responsable_existe", "tailscale" `{present, connecte, nom, jours_avant_expiration,
  raison}` (`detecter_tailscale` à chaque appel, jamais gardée dans `config.tailscale` : `/api/info` ne change pas),
  "mkcert_present", "systeme" (`windows` | `linux` | `macos`), "version"}`.
- `POST situation` `{"situation": "seul" | "equipe" | "informaticien"}` → brouillon réinitialisé aux défauts de
  l'étude §6.1 (`DEFAUTS_PAR_SITUATION` sur `reglages_par_defaut`) : Solo `portee` ce-pc, `comptes` faux,
  `certificat_auto` faux (réseau privé), `demarrage` aucun, `veille_desactivee` faux, `mode_solo` vrai ; Atelier
  `atelier`, comptes, `certificat_auto` vrai, `demarrage` systeme, veille coupée ; Intranet `atelier`, comptes,
  `demandeurs_avec_compte` vrai, `certificat_auto` faux, `demarrage` systeme, veille gardée. 400 sinon. Réponse de
  toute étape qui écrit le brouillon : `{"brouillon", "etapes"}` (plus ce qui suit).
- `POST portee` `{"portee": "ce-pc" | "atelier" | "dehors", "port_http"?, "port_https"?, "noms"?}` → valeurs
  contrôlées comme dans le fichier (`valeur_valide`, bornes de `CLES_CONFIGURATION`, noms en minuscules ; 400 au
  message, ports égaux 400) ; « ce PC » ⇒ `comptes` faux, `mandataire` faux ; au-delà ⇒ `comptes` vrai.
- `POST compte` `{"prenom", "nom", "mot_de_passe"}` → `creer_compte(… 'responsable' …)` écrit tout de suite
  `donnees/acces/comptes.json` (règles du serveur : 400 au message, 12 caractères au moins ; journal `creation`) ;
  409 au message s'il existe déjà un responsable actif (l'assistant propose de passer l'étape ; jamais de
  remplacement) ; en Solo, technicien « moi » dans `techniciens.csv` (`technicien_moi` : repris s'il existe, actif,
  même prénom et nom ; sinon `TEC-nnnn` suivant, métier vide, colonnes du fichier gardées, sauvegarde du jour d'abord)
  et lié au compte (`technicien_id`), identifiant gardé dans le brouillon (`solo_technicien_id`). Sur « ce PC » en
  Solo : le technicien seul, sans compte ni mot de passe (`compte` null) ; 400 ailleurs. Rend `{"compte"
  (compte_public, jamais le mot de passe), "technicien_id", …}`.
- `POST certificat` `{"mode": "automatique" | "reseau_prive" | "fichiers" | "mandataire", "certificat"?, "cle"?,
  "noms"?}` (400 sur « ce PC ») : automatique ⇒ `preparer_certificat_local` tout de suite avec
  `executable_mkcert()` (variable d'environnement `PREVO_MKCERT`, documentée comme `PREVO_TAILSCALE` : tests ;
  sinon `trouver_mkcert`, empreinte vérifiée) pour les adresses du PC et les `noms` du brouillon ; mkcert absent ou
  en échec ⇒ 503 au message qui dit quoi faire, brouillon inchangé ; sinon `certificat_auto` vrai. Fichiers ⇒ les
  deux PEM lus par `creer_contexte_ssl` (400 « illisible » sinon), chemins absolus dans `certificat`/`cle`,
  `certificat_auto` et `mandataire` faux. Réseau privé ⇒ `certificat_auto` faux, `mandataire` vrai (Tailscale à
  l'étape suivante ; écoute 127.0.0.1). Mandataire ⇒ `mandataire` vrai, `noms` obligatoires (du corps ou du
  brouillon ; 400 sinon). Rend `{"mode", "noms_certificat", "autorite_presente", …}`.
- `POST tailscale` `{"action": "detecter" | "appliquer" | "unattended" | "plus_tard"}` : detecter → `{"detection"
  (sous-ensemble public), "proposition"}` de `preparer_tailscale(…, reglages=brouillon)`, rien d'écrit ; appliquer →
  `appliquer_tailscale(config, reglages=brouillon, ecrire=False)` (serve lancée et vérifiée, §22.8 ; le fichier de
  configuration n'est pas touché) puis brouillon `noms` + nom Tailscale et `mandataire` vrai, étape faite, rend aussi
  `{"ok": true, "message", "nom", "adresse"}` ; 503 au message si Tailscale manque, n'est pas connecté ou si serve
  échoue ; unattended → `activer_unattended` (`{"ok", "message"}`, 503 si refusé) ; plus_tard → rien, étape
  `a_faire`. Jamais `up`, jamais d'installation.
- `POST demarrage` `{"demarrage": "systeme" | "session" | "aucun", "veille_desactivee": bool, "retirer"?: bool}` →
  `produire_scripts_demarrage` dans le dossier de Prévo (ports du brouillon, mkcert si `certificat_auto`, jamais
  exécutés ici) puis, sous Windows et si ≠ aucun, **une seule élévation** : `config.lancer_eleve(script, eleve)` =
  `lancer_script_powershell` (`commande_powershell` : `powershell.exe -NoProfile -ExecutionPolicy Bypass -File
  Installer_demarrage.ps1` lancé par `Start-Process -Verb RunAs -Wait`, code de sortie rendu ; `Demarrage_session.ps1`
  sans élévation pour `session`), injectable et jamais lancée dans les tests ; hors Windows, `commandes` à lancer à
  la main (systemd, launchctl). `aucun` avec `retirer` vrai (Paramètres, T170 ; CS129 : « scripts de retrait ») :
  `Retirer_demarrage.ps1` lancé avec la même élévation (tâche, règle du pare-feu et réglages de veille défaits) ; hors
  Windows, la commande de retrait (`systemctl disable --now prevo`, `launchctl unload`). Brouillon `demarrage`,
  `veille_desactivee` ; étape faite si rien n'était à lancer ou si le script a réussi, `a_faire` si l'élévation a été
  refusée (l'écran propose le repli ; au retrait, le script reste à lancer à la main). Rend `{"scripts": {nom:
  chemin}, "lance": {"ok", "code", "message"} | null, "commandes", …}`.
- `POST sauvegardes` `{"dossier": chemin | ""}` → vide = plus tard ; sinon `verifier_dossier_de_copie` : le dossier
  existe, s'écrit (fichier témoin créé puis supprimé) et n'est ni le dossier des données ni un de ses sous-dossiers
  (400 au message, qui ne cite que le nom du dossier) ; brouillon `copie_sauvegardes` (chemin absolu).
- `POST deplacer` `{"vers": chemin}` (défaut `C:\Prevo` ; Windows seulement, 400 ailleurs ; chemin complet exigé)
  → étape notée faite dans le brouillon (la copie l'emporte), puis `deplacer_installation(config, cible, brouillon)` :
  les données doivent être dans le dossier de Prévo (400 sinon : `--donnees`), `verifier_dossier_cible` (ni le
  dossier de Prévo, ni dedans, ni au-dessus ; absent ou vide ; 400), `copier_prevo` : le dossier entier, données
  comprises, sans `.git` ni `__pycache__`, chaque fichier relu (taille et SHA-256 ; écart ⇒ 500, copie retirée,
  ancien dossier intact), brouillon écrit dans la copie (`ecrire_brouillon` au même chemin relatif : l'assistant y
  reprend à l'étape 8), puis `config.relancer(cible)`. Rend `{"copie": nombre de fichiers, "vers", "relance": bool}`.
  L'ancien dossier n'est jamais supprimé. `{"rester": true}` (« Rester ici », T171) : `deplacement_refuse` vrai dans
  le brouillon, étape `a_faire`, rien de copié ; une demande de déplacement ultérieure l'efface.
- `POST terminer` `{"base": "vide" | "demo", "langue_defaut": code}` (`base` : défaut `vide` ; `demo` seulement si
  `base_presente` est faux dans le brouillon, 400 sinon : les CSV existants ne sont jamais remplacés ; valeur inconnue
  400 ; `langue_defaut` (T296) : défaut `fr`, sinon une langue déclarée par `js/i18n/langues.js` — `langues_declarees`
  y lit chaque ligne `I18n.declarer({ code: '…'`, la liste même du navigateur, relue à chaque appel ; fichier illisible :
  `fr` seul —, 400 `installation.langue_inconnue` sinon, rien d'écrit) → réglages = défauts +
  brouillon, `ecoute` dérivée, `_https_auto` ; 400 au message si `comptes`
  sans responsable actif, si `verifier_regles_portee` refuse (réseau sans https ni mandataire…) ou si le réseau
  compte sur mkcert absent (Prévo refuserait de démarrer) ; `demo` ⇒ `installer_jeu_de_demo` d'abord (un échec ne
  laisse rien d'écrit) ; puis `prevo.config.json` écrit **seulement ici**
  (`ecrire_configuration` s'il n'existe pas, `modifier_configuration` sinon : `_aide`, `ia_cle` et les clés inconnues
  gardés) au chemin de `--config` (défaut : à côté de `serveur.py`) ; puis `poser_parametres` dans `parametres.csv`
  (écriture de table normale, sauvegarde du jour d'abord, toutes les autres lignes gardées ; fichier créé avec
  `version_schema` en tête s'il manque, `version_schema` jamais réécrit sinon) : Solo ⇒ `mode_solo` = 1,
  `cloture_une_etape` = 1, `solo_technicien_id` (`valeurs_du_mode_solo`) ; base absente au départ (`base_presente`
  faux) ⇒ `langue_defaut` (T296), aussi après le jeu de démo ; une base présente au départ ne reçoit jamais de langue
  ici (absente, elle vaut `fr`, §24.11) ; brouillon supprimé ; `config.relancer(None)`. Rend
  `{"configuration" (les clés écrites), "fichier", "relance": bool, "base"}`.
- `GET fiche` → données de la fiche d'accès (T168 la met en page), d'après le brouillon, sinon le fichier de
  configuration (ce que `terminer` vient d'écrire), sinon les réglages du serveur : `{"situation", "portee",
  "comptes", "adresse_locale", "adresses" (la porte : `http://<adresse IP>:<port_http>/` et les noms acceptés hors
  `.ts.net`, seulement quand Prévo écoute sur le réseau ; jamais l'adresse https, §22.6), "adresse_tailscale"
  (`https://<nom .ts.net>/` derrière un mandataire), "adresses_mandataire" (`https://<nom>/` des autres noms),
  "autorite_presente", "adresse_confiance" (la porte, qui sert `/acces/ca.crt` : QR « faire confiance »),
  "lanceur" (`Lancer_GMAO.bat` | `lancer.sh`), "demarrage", "dossier", "dossier_donnees", "copie_sauvegardes",
  "reinitialisation" `{"script": Reinitialiser_mot_de_passe.bat, "commande"}`, "responsables" (identifiants)}`.
- **Paramètres › Accès et installation** (T170 ; D130 « Paramètres montre l'état », D131 dernier point, CS129,
  CS130) — mêmes routes `installation/<etape>`, même garde (PC serveur, et la session du responsable avec comptes) ;
  rien de nouveau dans `ROUTES_API` ni `ROLES_PAR_ROUTE` :
  - `GET journal` → `{"fichier": chemin | null, "lignes": [...]}` : les 20 dernières lignes de
    `donnees/journal-serveur.log` (`dernieres_lignes_du_journal`, `LIGNES_DU_JOURNAL`), sans celles qui contiennent
    « cle » (`MOTIF_LIGNE_JOURNAL_RETIREE`, prudence : le journal n'écrit jamais une clé ni un mot de passe) ;
    `[]` et `null` sans journal (serveur avec console et sans `--journal`).
  - `POST reprendre` `{}` → brouillon repris de la **configuration en cours** (`brouillon_depuis_configuration` :
    `config.reglages`, ce que `terminer` réécrira clé à clé ; `situation` déduite par `situation_de_la_configuration`
    : `seul` si `mode_solo` = 1 dans `parametres.csv`, `informaticien` si `demandeurs_avec_compte`, `equipe` sinon ;
    toutes les étapes `fait` sauf `deplacer` ; `mode_solo` faux, donc `parametres.csv` n'est pas touché à
    `terminer` ; `base_presente` vrai, donc jamais la démo), rend `{"brouillon", "etapes", "repris": true}` ; un
    brouillon déjà là est rendu tel quel (`"repris": false`) : les modifications en attente survivent à un
    rechargement ; 400 tant que `prevo.config.json` n'existe pas (l'assistant s'en charge). `POST situation`
    reste celle de l'assistant : elle remettrait les défauts de l'étude.
  - `POST reglages` `{clé: valeur, …}` pour `CLES_REGLAGES_SIMPLES` (`demandeurs_avec_compte`, `session_heures`,
    `session_longue_jours`, `invitation_heures`, `quota_documents_mo`), une au moins ; chaque valeur par
    `valeur_du_brouillon` (bornes de `CLES_CONFIGURATION`, 400 au message qui cite les bornes) ; clé inconnue 400.
  - `POST ia` `{"fournisseur"?: "ollama" | "openai", "url"?, "en_ligne"?: bool}` (`CLES_IA_DU_CORPS`), une au moins,
    `url` jamais vide ; la clé ne passe pas par l'API (400 si `cle` ou toute autre clé est envoyée) : `ia_cle` du
    fichier ou `PREVO_IA_CLE`, comme à T158 ; rend aussi `"cle_reglee"` (une clé est réglée sur ce PC).
  - `POST annuler` `{}` → brouillon supprimé, rien d'autre ne change ; rend `{"brouillon": null, "etapes"}`.
  - `GET /api/info` rend `actif_depuis` (`Configuration.actif_depuis`, `maintenant_iso` à la construction) : l'instant
    du démarrage du serveur, qui change quand il s'est relancé.
  - *Écran* (`js/modules/parametres-acces.js`, objet `ParametresAcces`, Parametres 5/5, relais `carteAcces` et
    `brancherAcces` de `parametres.js` ; styles dans `css/modules/parametres.css`) : carte `#carte-acces` dans Paramètres, rendue
    **seulement** quand `App.mode === 'serveur'`, `App.pcServeur()` et `App.estResponsable()` — depuis un client du
    réseau, en mode dossier ou démo ou pour un autre profil, ni carte ni mention. En tête, l'état du serveur
    (`#acces-etat`, bouton « Actualiser ») : actif depuis (`/api/info`), installation terminée ou lien vers
    l'assistant, portée et adresses (adresse locale, adresses réseau, adresse Tailscale derrière le mandataire),
    Tailscale (`GET etat`, détecté à chaque lecture), copie externe (`/api/info`, `copie_externe`), journal du
    serveur (`GET journal`, `pre.acces-journal` ; « Aucune erreur notée. » sinon) ; lien « Voir la fiche d'accès »
    (`#/installation/fiche`). Puis sept sous-sections `details.acces-section[data-section]` (portée, ports et noms ;
    certificat ; Tailscale ; démarrage et veille ; copie des sauvegardes ; comptes des demandeurs, durées de session
    et documents ; IA), chacune avec le résumé des valeurs en cours (`etat.configuration`, ou le brouillon), les
    formulaires d'`InstallationEtapes.formulaire` pour les étapes de l'assistant (jamais recopiés, « Régler
    autrement » compris) et des formulaires `UI.champ` pour `reglages` et `ia`, l'aide de chaque réglage prise dans
    `AccesTextes.options` ; « Sans objet » pour le certificat sur « ce PC » et Tailscale hors de « dehors ».
    « Enregistrer ce réglage » : `POST reprendre` au premier enregistrement (un brouillon repris pour un
    enregistrement refusé est jeté par `annuler`), puis `POST <étape>` ; l'erreur du serveur s'affiche telle quelle
    sous le bouton (`#acces-erreur-<section>`). Le démarrage « à la main » envoie `retirer` quand la configuration en
    force démarrait Prévo avec le PC (note `#acces-retrait-note` sous Windows). Tailscale : « J'ai installé
    Tailscale et je suis connecté » → `detecter` puis `appliquer`, rappels, `unattended` sur clic ; « Plus tard »
    caché. Copie des sauvegardes : « Ne plus copier » envoie un dossier vide. Un brouillon présent est annoncé par
    `#acces-attente` (« Modifications en attente … Prévo redémarre : les postes connectés se reconnecteront. ») avec
    « Appliquer et relancer » (`POST terminer`, puis `/api/info` relu toutes les 2 s jusqu'à ce que `actif_depuis`
    change ou que la session soit à rouvrir — 401 —, et la page se recharge sur Paramètres ; message au bout de
    60 s) et « Annuler » (`POST annuler`). Testé par `tests/test_parametres_acces.py` (serveur du processus avec
    configuration et comptes, session du responsable, faux tailscale, élévation et relance notées : carte présente
    pour le responsable sur le PC serveur avec l'état du serveur et le journal filtré, absente pour un technicien, en
    démo et pour un client du réseau ; un réglage de chaque sous-section puis « Appliquer et relancer » avec
    `prevo.config.json` relu clé à clé, `Retirer_demarrage.ps1` écrit et l'élévation notée, relance notée,
    rechargement quand `actif_depuis` change ; bornes refusées et « Annuler » à 375 px sans défilement horizontal).
- **Relance** (`relancer_prevo`, `config.relancer`, injectable) : lanceur du dossier visé (`Lancer_GMAO.bat`,
  `lancer.sh`) lancé par un processus détaché qui attend 3 s (le port est rendu), nouvelle console sous Windows ;
  ce serveur s'arrête 2 s après la réponse (`os._exit`). Sans lanceur : faux, le serveur continue. Jamais lancée par
  les tests.
- **Démarrage** : `main` ouvre `adresse_de_demarrage(config)` = `http://localhost:<port>/#/installation` tant que
  `prevo.config.json` est absent (`--sans-navigateur` respecté), la console le dit (« Installation : pas encore
  faite… ») et `GET /api/info` rend `installation_a_faire: true` — pour que l'écran propose l'assistant, jamais
  pour l'imposer : les tests des lots 1 à 6 tournent sans configuration. Le message « tant que l'installation n'est
  pas terminée, Prévo n'est joignable que sur ce PC » est un texte d'écran (T168, T169).
- **Écran** (T168 ; `js/modules/installation-ecrans.js`, `installation-etapes.js`, `installation-fiche.js`, feuille
  `css/modules/installation.css`) : écran plein `#ecran-installation` hors de la coque (état `'installation'`), ouvert par
  `App` quand la page est sur `#/installation` (ou `#/installation/fiche`), servie depuis le PC serveur
  (`location.hostname` 127.0.0.1 ou localhost) et que `/api/info` rend `installation_a_faire` (`adaptateur.info().
  installationAFaire`) ; jamais sur une autre route (les tests des lots 1 à 6 ouvrent `/` sans configuration et voient
  l'écran de profil comme avant) ; depuis le réseau, rien. Les écrans « base vide » et « profil » montrent un lien discret
  « Installer Prévo (assistant) » (`.lien-installation`) sur le PC serveur tant que l'installation n'est pas faite.
  Première ligne : « Tant que l'installation n'est pas terminée, Prévo n'est joignable que sur ce PC. »
  (`#installation-premiere-ligne` d'`index.html`, seule source du texte). Huit étapes
  (`Installation.ETAPES` : situation, portée, compte, certificat, Tailscale, démarrage, sauvegardes, récapitulatif), une
  par écran avec la progression, « Précédent » et « Continuer » ; chaque étape montre les quatre textes de son choix
  d'`AccesTextes.choix` (`installation`, `exterieur` + `mot_de_passe`, `mot_de_passe`, `certificat`, `exterieur`,
  `demarrage` + `veille`, `sauvegardes`, `etiquettes` ; conseil de la situation choisie, les trois conseils avant le choix)
  dans `.installation-textes[data-choix]` (`dd[data-texte=qui|change|pourquoi|conseil]`) et un `<details
  class="installation-autrement">` « Régler autrement » (ports, noms, fichiers PEM, mandataire, veille… avec l'aide
  d'`AccesTextes.options` ; les réglages sans étape dans l'API — durées de session, IA, quota — sont montrés avec leur aide
  et renvoyés à Paramètres › Accès et installation). Étapes `sans_objet` sautées avec une ligne `.installation-sautee`.
  Appels : `POST situation`, `portee` (ports et noms), `compte` (12 caractères au moins, indication par la longueur,
  confirmation, champs vidés à chaque réponse ; Solo sur « ce PC » : prénom et nom seuls ; 409 → l'étape se passe),
  `certificat` (automatique recommandé ; réseau privé si « dehors » ; fichiers et mandataire pour l'informaticien, sous
  « Régler autrement » sinon), `tailscale` (lien de téléchargement officiel quand absent ; « J'ai installé Tailscale et je
  suis connecté » → `detecter` puis `appliquer`, rappels, `unattended` sur clic ; « Plus tard »), `demarrage` (une seule
  invite d'administrateur annoncée ; élévation refusée → message, l'étape reste ouverte ; commandes hors Windows),
  `sauvegardes` (dossier ou « Plus tard »), `deplacer` (carte `#inst-dossier` du récapitulatif quand l'étape est à
  faire et que le brouillon n'a pas `deplacement_refuse` : « Déplacer Prévo dans C:\Prevo (recommandé) » avec ce que
  ça fait, ou « Rester ici » → `{"rester": true}`), `terminer` (avec `{"base", "langue_defaut"}` quand la carte
  `#inst-base` « Par quoi commencer ? » est montrée : `base_presente` faux dans le brouillon ; la carte porte la liste
  « Langue de Prévo » `#inst-langue_defaut`, T296 : les langues déclarées sous leur nom dans leur langue,
  `UI.optionsLangues`, proposée = `UI.langueDuNavigateur()` ; l'assistant reste dans la langue de la page, la langue
  choisie s'applique à la fin, quand Prévo s'ouvre sur la base créée) puis attente de la relance (`attendreRelance`
  interroge toutes les 2 s jusqu'à ce que le serveur relancé réponde : après `terminer`, `/api/info` avec
  `installation_a_faire` faux ou 401, rechargement sur `#/accueil` ; après `deplacer`, `GET etat` avec `dossier`
  égal au nouveau dossier, rechargement sur `#/installation` où l'assistant reprend à l'étape 8 ; message au bout de
  60 s). Toute erreur du serveur s'affiche telle quelle
  sous le bouton (`.installation-erreur`), l'étape reste ouverte. Le brouillon fait foi : `GET etat` replace l'assistant à
  la première étape à faire. Situation « informaticien » : après l'étape 1, toutes les étapes sur une page (une section
  par étape, « Enregistrer cette étape », rien d'automatique sans clic). Fiche d'accès (`InstallationFiche.rendre`,
  `GET fiche`) à l'étape 8, sur `#/installation/fiche` et dans la coque après l'installation (responsable) : adresses
  de la porte, QR « Ouvrir Prévo » (`UI.qrSvg`), QR « Faire confiance au PC atelier » si `autorite_presente`, adresse
  Tailscale, arrêter et relancer, où sont les données, mot de passe oublié ; « Imprimer » copie la fiche dans
  `#impression` (seul imprimé, règle de `style.css`) puis `window.print()` ; `@media print` : fond blanc, encre noire,
  aucun bouton, QR de 45 mm. « Ouvrir Prévo sans terminer » quitte l'assistant : démarrage normal sur l'accueil.
- **Migration et dossier** (T171 ; D131 dernier point, CS130) :
  - *CSV existants gardés (migration 1.2)* : `etat.csv_presents` vrai (un CSV du schéma dans `donnees/`) ⇒ l'étape 1
    l'annonce (`#inst-migration` : « Vos données de Prévo 1.2 sont là : N fichiers, dernière modification le … ;
    elles sont gardées. ») ; aucune étape ne touche un CSV existant, sauf `techniciens.csv` en Solo (technicien
    « moi » ajouté, ou reconnu par son prénom et son nom : fichier inchangé) et `parametres.csv` à `terminer` en Solo
    (`mode_solo`, `cloture_une_etape`, `solo_technicien_id` ajoutés ou remplacés, toutes les autres lignes gardées,
    `version_schema` écrit seulement s'il manque). `base_presente` est noté dans le brouillon à `situation` (l'assistant
    crée lui-même des CSV ensuite en Solo) : faux ⇒ l'étape 8 demande « Par quoi commencer ? » (vide, ou la démo) et
    `terminer` reçoit `base`. `demo` : `installer_jeu_de_demo` lit `js/demo-donnees.js` (`lire_jeu_de_demo` : le seul
    jeu livré, §22.14 ; une ligne par table, chaîne JSON ou morceaux du wiki recollés ; 500 au message s'il est
    illisible, rien d'écrit), décale les dates du nombre de semaines entières depuis `dateReference`
    (`decaler_texte_csv` : toute cellule qui commence par `AAAA-MM-JJ`, exactement les colonnes `date` et `date_heure`
    du schéma sur ce jeu — testé —, 0 semaine : texte tel quel ; même résultat que `StockageDemo.decalerDates`), écrit
    les 24 tables (sauvegarde du jour d'abord), puis, en Solo, recrée le technicien « moi » dans la table de la démo
    (`technicien_moi` : TEC-0005, ou un technicien de la démo du même nom), met son identifiant dans le brouillon
    (`poser_mode_solo` le prend) et dans le compte responsable lié (`modifier_compte`). `vide` : rien de plus que ce
    que Solo pose, et `langue_defaut` (T296) ; hors Solo, `parametres.csv` seul (`version_schema`, `langue_defaut`) :
    la base existe, les autres tables manquent et se lisent vides (comme en Solo), la première ouverture ne repropose
    plus « démo ou vide » (avant T296 : base sans CSV, « démo ou vide » comme en 1.2).
  - *Profils remplacés par la connexion* : avec `comptes`, `prevo.profil` mémorisé par 1.2 est ignoré (T155 : la
    session fait foi, l'écran de connexion s'affiche, `App.profil` vient de la session) ; sans comptes (Solo « ce
    PC »), le profil mémorisé reste valable. Prouvé par `test_installation_migration`.
  - *Dossier C:\Prevo* : voir `POST deplacer` et la carte `#inst-dossier` ci-dessus ; `deplacer_installation` est la
    fonction de `serveur.py` que la route appelle (copie, vérification, brouillon dans la copie, relance injectable).
- **Tests** : `tests/test_installation_migration.py` (T171 : base 1.2 = copie de la démo, Solo « ce PC » jusqu'à
  `terminer` avec chaque CSV comparé octet à octet sauf `parametres.csv` ; base absente avec `demo` — les 24 tables
  comparées à un décalage calculé d'après les colonnes typées de `js/schema.js`, technicien « moi » et compte
  relié — et avec `vide` ; `demo` refusé sur une base présente ; `deplacer_installation` vers un dossier temporaire
  (compte des fichiers, SHA-256, brouillon dans la copie, relance notée, source intacte), « Rester ici » mémorisé,
  cibles refusées ; profils : Playwright avec `prevo.profil` préréglé, serveur en mode comptes → connexion, sans
  comptes → profil gardé ; écran : étape 1 avec la ligne de migration, étape 8 avec « Par quoi commencer ? » sur une
  base absente seulement, « Rester ici » puis rechargement sans la carte, « demo » jusqu'à la relance) ;
  `tests/test_installation_ecrans.py` (T168 : serveur du processus sur une copie de la démo ou un dossier
  vide, servant l'application, `lancer_eleve` et `relancer` injectés, faux mkcert et faux tailscale par
  `PREVO_MKCERT` et `PREVO_TAILSCALE` ; parcours Solo « ce PC » à 1280 px jusqu'à « Terminer » et le fichier écrit,
  Atelier à 375 px sans défilement horizontal et zones de 48 px, informaticien sur une page, les quatre textes de chaque
  étape comparés à `AccesTextes`, « Régler autrement », impression en média `print`, client du réseau sans assistant,
  `/` sans configuration inchangé ; T296 : navigateur en-GB, English proposé, `langue_defaut` = en écrit, Prévo ouvert
  en anglais sur un poste sans choix ; fr-FR : français) ; `tests/test_installation_migration.py` couvre aussi la langue
  (T296 : base présente jamais touchée, `fr` sans le champ, démo et vide hors Solo avec la langue, « xx », « EN », vide,
  null, nombre, liste : 400 par code et rien d'écrit) ; `tests/test_installation_api.py` (serveur du processus avec `config.lancer_eleve`, `config.relancer`,
  `dossier_application` et `systeme` injectés ; faux mkcert et faux tailscale par `PREVO_MKCERT` et `PREVO_TAILSCALE`,
  jamais hérités du poste : `tests/commun.py` ; les quatre parcours comparés clé à clé ; 404 vu du réseau par un
  serveur sur 0.0.0.0 et par `tests/mandataire_test.py` ; serveur réel au premier lancement) ;
  `tests/test_acces_roles.py` joue la ligne « responsable » des deux routes.

### 22.11 Mode Solo et sauvegardes (D132, D133)

`parametres.csv` gagne `mode_solo` (0/1) et `cloture_une_etape` (0/1, posé à 1 avec `mode_solo`). Mode Solo : menu
avec « Plus » (Équipe, Planning), accueil « Nouvel OT » en premier, fiche équipement « Créer un OT » en premier,
technicien du compte pré-rempli. Clôture en une étape : `Ordres.clore(ot, valeurs)` fait la clôture technique puis
l'administrative dans la même écriture de la table, deux dates égales, deux lignes de journal, entrée dans la file du
wiki. Sauvegardes : copie externe à la première écriture après 2 h du matin (ou au démarrage), 30 copies ; échec
noté dans `journal-serveur.log` et rendu par `/api/info` (`copie_externe`) pour l'accueil du responsable ;
`POST /api/sauvegarde/tester` ; 429 pour une deuxième sauvegarde manuelle dans la minute ; purge au-delà de 60
manuelles.

Précisions de T175 (sauvegardes du serveur, `tests/test_sauvegardes_lot7.py`) :

- **Horloge** : nom du jour, nom horodaté, 2 h du matin, minute du plafond et jours sans copie se lisent sur
  `config.horloge` (défaut `time.time`, injectable comme au §22.3) ; un nom horodaté pris fait attendre la seconde
  suivante, 503 au bout de 5 s (horloge arrêtée).
- **Copie externe** (clé `copie_sauvegardes` ; vide = aucune copie, rien d'affiché ; chemin relatif = depuis le dossier
  de Prévo) : lancée au démarrage (après la console d'accueil, qui affiche la ligne « Copie externe ») et, chaque jour,
  par la première écriture CSV à partir de 2 h (`faire_sauvegarde_quotidienne`, après la sauvegarde du jour), toujours
  dans un fil à part (`lancer_copie_externe`, fil gardé dans `config.fil_copie_externe`) ; jamais deux à la fois
  (`VERROU_COPIE_EXTERNE`, pris sans attendre) ; une écriture qui tombe pendant une copie ne marque pas le jour : la
  suivante relance. Copiée : la sauvegarde quotidienne complète la plus récente (`acces/` compris, jamais
  `sessions.json` ni un fichier caché) vers `<copie_sauvegardes>/AAAA-MM-JJ/`, par un dossier temporaire
  `.prevo-copie-en-cours-…` renommé à la fin ; rien si cette copie existe déjà (réussite quand même). Puis 30 copies
  gardées : seuls les dossiers dont le nom est une vraie date `AAAA-MM-JJ` sont comptés et supprimés (ni lien ni
  jonction), jamais un autre fichier ou dossier. Refus : dossier absent (« Dossier de copie « X » introuvable (clé USB
  absente ou partage réseau injoignable ?). »), dossier rangé dans le dossier des données, erreur de copie.
- **État** : `donnees/copie-externe.json` `{"derniere_reussie": "AAAA-MM-JJ" | null, "sauvegarde_copiee", "erreur"}`
  (gardé d'un démarrage à l'autre ; une réussite efface l'erreur) ; chaque échec va sur la console et toujours dans
  `donnees/journal-serveur.log`, avec le chemin (journal local). `GET /api/info` rend `copie_externe` : `null` sans
  dossier réglé, sinon `{"derniere_reussie", "jours_sans_copie", "erreur"}` ; `jours_sans_copie` = jours depuis la
  dernière réussite quand la dernière tentative a échoué ou qu'une sauvegarde quotidienne plus récente attend sa copie,
  0 quand la copie est à jour ou en cours (un week-end sans écriture n'alerte pas), `null` sans aucune réussite. Les
  messages ne citent que le nom du dossier, jamais son chemin complet.
- **Accueil du responsable** (`accueil-bento.js`, mode serveur) : `App.adaptateur.info().copieExterne` lu à chaque
  affichage, après coup (`#copie-externe-zone`, `data-lu` posé une fois la lecture faite) ; avertissement
  `#alerte-copie-externe` (`UI.bandeau('attention')`) quand `erreur` ou `jours_sans_copie` > 1 : « Copie externe des
  sauvegardes : aucune copie depuis N jours. » (ou « la dernière copie a échoué », « aucune copie réussie pour
  l'instant »), le message du serveur, puis « La copie est refaite au prochain démarrage de Prévo et chaque nuit, à la
  première modification après 2 h. » ; rien sinon (`Accueil.avertissementCopieExterne(copie)`, fonction pure).
- **Tester une sauvegarde** : `POST /api/sauvegarde/tester` `{"nom"}` (nom contrôlé par `MOTIF_NOM_SAUVEGARDE` : 400 ;
  absente ou incomplète : 404 ; corps invalide : 400) relit chaque CSV présent, dans l'ordre du schéma, par une lecture
  tolérante (`lire_csv_tolerant` : BOM retiré, UTF-8 sinon Windows-1252, « ; » ou « , », lignes vides ignorées ; noms de
  colonnes comparés sans casse, accents, espaces ni « _ ») et rend `{"nom", "ok", "tables": [{"table", "lignes",
  "erreur"}]}` sans rien écrire. Erreur d'une table : fichier illisible ou vide, colonne du schéma (`COLONNES_PAR_TABLE`)
  absente de l'en-tête, sauf celles ajoutées par un format plus récent (`COLONNES_DES_FORMATS_SUIVANTS`, recopie des
  `depuisVersion` de `js/schema.js`, cohérence testée) ; `ok` : au moins une table et aucune erreur.
  `App.adaptateur.testerSauvegarde(nom)` (serveur seulement, §6) ; dans Paramètres, mode serveur seulement, bouton
  « Tester » (`button[data-tester]`) avant « Restaurer… » sur chaque ligne, fenêtre `#resultat-test-sauvegarde`
  (verdict, lignes par table `[data-lignes]`, erreur `[data-erreur]`) et note `#note-sauvegardes-serveur` ; module
  `js/modules/parametres-sauvegardes.js` (Parametres 4/4, relais `actionsSauvegarde` et `noteSauvegardes` de
  `parametres.js`, qui aurait dépassé 700 lignes). Modes dossier et démo : ni bouton ni note.
- **Plafond et purge** : `POST /api/sauvegarde` sans motif (corps vide ou motif `null`) : 429 `{"erreur": "Une
  sauvegarde manuelle par minute au plus : réessayez dans N s.", "attente_secondes": N}` avec `Retry-After: N` quand la
  dernière sauvegarde manuelle (lue sur son nom `AAAA-MM-JJ_HHMMSS`, ce qui tient après un redémarrage) a moins de 60 s ;
  un nom « dans le futur » (horloge reculée) ne bloque pas ; contrôle et création sous `VERROU_ECRITURE`. L'écran
  Paramètres affiche le message du serveur (toast d'erreur). Après chaque sauvegarde manuelle,
  `purger_sauvegardes_manuelles` garde les 60 plus récentes ; quotidiennes et copies `…_avant-…` ni comptées ni
  touchées. Les sauvegardes à motif (`avant-import`, `avant-format-vN`, `avant-restauration`) ne sont jamais limitées.
- **`acces/`** : copié par `copier_acces_dans_sauvegarde` (T150) dans toute sauvegarde du serveur sans `sessions.json`,
  jamais restauré par `restaurer` : une restauration complète laisse `comptes.json` et `sessions.json` tels quels.

**Import ZIP** (chantier « socle de données », T191 ; D172 ; docs/FORMAT.md §10 ; CS168 : ce changement touche la
sécurité, il est donc écrit ici). `js/modules/parametres-zip.js` (objet `ParametresZip` : `etat()`, `importer(fichier)`,
relais `blocImportZip` et `brancherImportZip` de `parametres.js`) : bouton « Importer un ZIP… » (`#btn-import-zip`,
champ caché `#fichier-import-zip`) en bas de la carte « Sauvegardes ». Remplacement complet seulement, jamais de
fusion ; aucune route serveur nouvelle (D172) : le navigateur lit le ZIP et écrit par l'API et les adaptateurs existants.
Exception unique (T319, Nicolas, 07/11) : un **réglage** de Paramètres (`Parametres.reglagesConnus` : formulaire et
mode Solo) que la base a et que le ZIP n'a pas (export 1.2, bêta 1, bêta 2, démo : `langue_defaut`, `devise`, réglages
de la 2.0) garde la valeur de la base (`reglagesGardes`), ajouté à la suite des lignes du ZIP et nommé à la
confirmation (`#reglages-gardes-import-zip`) ; le reste de `parametres.csv` (`rapports_mensuels`, clés inconnues) suit
le ZIP.
Mode Solo gardé de la base (T323, Nicolas, 07/11) : le technicien « moi » (`solo_technicien_id`) ne vaut après
l'import que si une seule fiche du ZIP porte le prénom et le nom de la fiche « moi » de la base (`moiSoloApresImport` :
même identifiant ou un autre, qu'il suit) ; sinon il est vidé, la confirmation le dit (`#solo-moi-import-zip`), et à
l'ouverture `Parametres.interne.demanderMoiSolo` (parametres-solo.js, appelé par js/app.js une fois prêt) demande au
responsable sa fiche, ou d'en créer une ; Prévo ne devine jamais. Annuler : la question revient à l'ouverture suivante.

- **Droits** : la règle de l'export (`ZipDonnees.exportPermis`) : avec les comptes, le responsable seul (bouton absent
  pour les autres rôles, qui n'ouvrent pas Paramètres ; un appel direct est refusé ; le serveur refuse de toute façon
  `POST /api/sauvegarde` et `/api/restauration` à un autre rôle, 403, donc rien n'est écrit) ; sans comptes (« ce PC »,
  mode dossier), le profil qui ouvre Paramètres. Démo : bouton inactif, note `#note-import-zip` « indisponible en
  démo ». Lecture seule (D169) : fenêtre `#import-zip-refus` dès le clic, et pour un fichier donné quand même.
- **Contrôles, avant toute écriture** : `ZipLecture.lire` (`zip-lecture.js`, §15.1 ; détail dans son en-tête) : taille
  du fichier (4 Go sans ZIP64, T229), nombre d'entrées (10 000) (T212), répertoire central lu par Prévo (noms hostiles : absolus, « .. », « . »,
  barre inverse, segment vide, caractère de contrôle, UTF-8 invalide ; doublons ; chiffrement ; méthode), tailles
  déclarées puis réelles (CRC-32), taux de compression (bombe), 50 Mo par CSV et 10 Mo par document (T208),
  4 Go décompressés (T229), noms admis (CSV des
  tables à la racine, `documents/<nom>` à la règle des noms du serveur, `manifeste.json`), manifeste et empreintes
  SHA-256 (aucun fichier ajouté, manquant ou modifié), format plus récent refusé, CSV illisible ou abîmé refusé. Un ZIP
  plus ancien est migré en mémoire. Refus : fenêtre `#import-zip-refus` (message de `ZipLecture`), rien d'écrit.
- **Fichier marqué abîmé** (T213, option B de Nicolas) : un CSV illisible ou abîmé n'est accepté (`ZipTables`,
  `lu.abimes`) que si le manifeste le marque `"abime": true` ET que son empreinte correspond (étape 10, vérifiée
  avant) ; sinon refus comme ci-dessus. Il est écrit avec les octets du ZIP, tels quels (ni sérialisation, ni
  migration, ni réparation ; ses références à des documents ne sont pas réécrites), option `abimeDepuis` = la date
  `abime_depuis` du manifeste, sinon maintenant (`fichiers-abimes.json`, adaptateur dossier ; serveur : en-tête
  `X-Prevo-Abime-Depuis`). Sécurité : l'empreinte ne prouve que l'intégrité du ZIP, pas son origine (n'importe qui
  peut la recalculer) ; la dérogation reste donc bornée : responsable seul (comme l'import), et le serveur ne relâche
  que la comparaison de l'en-tête au schéma, pour un fichier qu'il voit lui-même abîmé (`raisons_fichier_abime`) ;
  UTF-8 et cellules dangereuses restent contrôlés. En mode dossier (« ce PC »), aucune frontière de droits : la
  personne peut déjà modifier ces fichiers. Un journal abîmé importé tel quel ne reçoit pas la ligne de l'import.
- **Données seules** (T214, décision de Nicolas) : Paramètres › « Exporter les données seules (sans les documents) »
  (`#btn-export-donnees-seules`, `App.exporterZip({ sansDocuments: true })`, `ZipDonnees.contenu`) : les CSV et
  `manifeste.json` (`"documents": "exclus"`, pas de `manquants`), mêmes contrôles des limites,
  `prevo-export-AAAA-MM-JJ-sans-documents.zip`. Import : `ZipLecture` refuse un tel manifeste si le ZIP contient
  des documents ; tables remplacées comme d'habitude ; aucun document écrit, supprimé ni remplacé ; la confirmation
  (`#documents-import-zip`, `data-sans-documents="1"`) dit « Ce ZIP ne contient pas les documents : les N documents
  déjà présents sont gardés tels quels ; M documents cités par les données importées n'existent pas ici. » (N : cités
  par les données actuelles et présents ; M : cités par les données importées et absents ; chaque document n'est lu
  que pour savoir s'il est là). L'import complet non plus ne supprime jamais un document existant absent du ZIP.
- **Confirmation** `#confirmation-import-zip` : date, version et mode de l'export (manifeste ; « sans manifeste » pour
  un export plus ancien), format (« mises au format 3 » si migré), lignes actuelles → importées par table
  (`[data-actuel]`, `[data-importe]`), tables absentes du ZIP qui seront vidées (`[data-videe]`), nombre de documents,
  points relevés à la lecture (documents manquants à l'export…), et l'avertissement « Toutes les données actuelles
  seront remplacées ; une sauvegarde complète, documents compris, est faite juste avant ; les comptes et l'accès ne
  sont pas touchés. » « Annuler » (bouton par défaut) : rien d'écrit.
- **Déroulé** (surveillance arrêtée pendant les écritures) : (a) sauvegarde `avant-import-zip` d'abord (tables,
  `documents/`, et `acces/` en mode serveur, T187/T188) ; échec → arrêt, rien d'écrit ; (b) documents du ZIP écrits par
  `ecrireDocument` ; nom demandé = nom du ZIP sans le préfixe `AAAAMMJJ-HHMMSS-` ; le nom rendu (horodaté par le
  serveur) est gardé ; deux noms demandés égaux dans le même import → `-2`, `-3`… ; en mode dossier, un document du même
  nom identique à l'octet est repris, différent → `-2`… ; un document existant n'est jamais supprimé ni remplacé ;
  échec → arrêt avant les tables (les documents déjà copiés restent, inutilisés) ; (c) références réécrites vers les
  noms rendus (`equipements.document`, `demandes.photo`, `controles_reglementaires.rapport`, `rapports_mensuels`) ; une
  référence à un document absent du ZIP reste telle quelle ; (d) les 24 tables remplacées, dans l'ordre du schéma :
  `Donnees.csv.serialiser` (protection des cellules, en-tête du format courant, colonnes inconnues du ZIP gardées) puis
  `App.adaptateur.enregistrer` avec la version fraîche (`Donnees.rechargerTable` avant et après : contrôle de version ;
  écritures refusées en lecture seule) ; `version_schema` = format courant ; (e) une ligne de journal (table `parametres`)
  `import ZIP : <fichier>, 24 tables, <m> documents ; sauvegarde <nom> faite juste avant` ; (f) fenêtre `#import-zip-termine`, puis
  `location.reload()` (mode dossier : « Reprendre le dossier »).
- **Échec pendant (c) à (e)** : `App.adaptateur.restaurer(<avant-import-zip>)` remet toutes les tables (avec la copie
  de sécurité `avant-restauration` habituelle, qui garde l'état interrompu) ; une table absente de la sauvegarde (elle
  n'existait pas avant) est vidée ; fenêtre `#import-zip-echec` qui nomme la sauvegarde ; si la restauration échoue
  aussi, la fenêtre dit de restaurer cette sauvegarde à la main (Paramètres › Sauvegardes).
- **Jamais touché** : `acces/` (comptes, sessions, appareils) : rien dans ce déroulé n'y écrit, et `restaurer` ne le
  remet pas. **Pas restauré** : les documents (la restauration remet les tables seulement ; les documents copiés par
  un import interrompu restent ; ceux d'avant sont intacts, et copiés dans `documents/` de la sauvegarde).
- Écart retenu : les tables ne passent pas par `Donnees.modifier`, qui ne garde que les colonnes inconnues de la table
  actuelle (celles du ZIP seraient perdues sans le dire, CS140) et journaliserait chaque ligne ; c'est le chemin de
  `Import.annuler` (lot 5, §18.7) : sérialisation de `Donnees`, adaptateur protégé, version contrôlée.
- **Risques restants** : le ZIP est lu par morceaux (T227), jamais en entier : mémoire bornée aux tables plus un
  document, pas encore mesurée sur un gros ZIP (recette T215) ; un poste à court de mémoire pourrait encore fermer
  l'onglet (rien n'est écrit avant la confirmation) ; le contenu des documents
  n'est pas analysé au-delà des signatures d'image contrôlées par le serveur (`verifier_signature_image` ; aucune en
  mode dossier) : un document reste servi isolé (`Content-Security-Policy: sandbox`, enveloppe sans script hors
  serveur, §15.1) ; en http par le réseau (contexte non sécurisé), un ZIP avec manifeste est refusé faute de
  `crypto.subtle` (importer depuis le PC serveur ou en https) ; une sauvegarde de plus de 15 s (gros dossier
  `documents/`) dépasse le délai des requêtes : l'import s'arrête sans rien écrire ; une écriture d'un autre poste
  pendant l'import donne un conflit, donc le retour en arrière ; la ligne de journal compte les documents du ZIP, repris
  ou écrits.

### 22.12 Corrections de l'audit (D134, CS134)

E2 `verifier_contenu_csv(table, octets)` avant `enregistrer_csv` et `ajouter_au_csv` (`COLONNES_PAR_TABLE` recopié
de `js/schema.js`, test de cohérence) ; M1/M3 (précisé à T158) : le fournisseur est réglé sur le serveur seulement —
clés `ia_fournisseur` (`ollama` | `openai`, défaut `ollama`), `ia_url`, `ia_en_ligne` de la configuration, options
`--ia-url`, `--ia-fournisseur`, `--ia-en-ligne` (l'informaticien, les tests), clé par `ia_cle` ou la variable
d'environnement `PREVO_IA_CLE`, jamais en ligne de commande (visible dans la liste des processus) ; `GET /api/ia/reglages`
rend `{fournisseur, url, cle_reglee, en_ligne, portee}` (jamais la clé) ; `POST /api/ia` ne lit que `chemin`, `methode`,
`corps` (toute autre clé ⇒ 400, `url` et `cle` compris), adresse et clé lues dans la configuration, `Authorization`
posé par le serveur, délai fixé à 120 s ; en mode serveur, « Ce poste » montre l'adresse et l'état de la clé sans les
demander, et le navigateur ne garde aucune clé (I5 : en mode dossier, inchangé, avec la mention) ; M2 fournisseur
distant autorisé par `ia_en_ligne` seulement, la case « Autoriser les fournisseurs d'IA en ligne » de Paramètres
affichant en mode serveur la décision du PC serveur sans la changer ; F2 (précisé à T159) `SEMAPHORE_CONNEXIONS =
BoundedSemaphore(32)` du module, une place prise au premier octet d'une requête et rendue avec sa réponse
(`GestionnaireRequetes.handle_one_request` : le premier octet est attendu sans place, par `rfile.peek(1)`, donc une
connexion keep-alive inactive n'en tient aucune — correction du 28/10 : à T159 la place était tenue par connexion et
cinq navigateurs bloquaient le sixième) ; une requête lente ou laissée à moitié tient sa place, la 33e attend son
tour, ni refusée ni perdue, une seule limite pour la porte et l'application ;
corps lu après le contrôle de session (`traiter`, T151) ; délai IA fixé par le serveur (`DELAI_IA_S`, T158) ; une
sauvegarde manuelle par minute, 429 (T175) ; quota du dossier `documents/` : avant d'écrire, sous `VERROU_ECRITURE`,
taille du dossier (`taille_des_documents`, parcours `os.scandir` à chaque envoi : un compteur en mémoire se tromperait
dès qu'on fait de la place à la main) + taille du corps ≤ `quota_documents_mo` × 1 Mo (4 096 par défaut depuis
T250, comme l'import ZIP), sinon 413 « Dossier des documents plein (… Mo sur … Mo avec ce document) : faites de la
place, ou agrandissez la place des documents dans Paramètres › Accès et installation, sur le PC serveur. » (T250 :
le refus dit où se règle le quota) et rien d'écrit ; F4 (précisé à T159) `.doc`/`.xls` retirés de `TYPES_DOCUMENTS`
(415 « Type de document refusé » pour toute extension inconnue, à la lecture comme à l'écriture ; `docx`, `xlsx`, `odt`, `ods` restent ; les listes du navigateur,
`parc-formulaires.js` et `stockage-dossier.js`, suivent), `Content-Disposition: attachment; filename="<nom>"` sur
tout document qui n'est ni une image (`TYPES_AFFICHABLES` : jpg, jpeg, png, gif, webp), ni un PDF, ni le rapport
figé en html (que « Ouvrir » affiche dans un onglet : `sandbox` y interdit déjà scripts et formulaires, un
téléchargement d'office casserait l'écran Rapports), toujours avec `sandbox` et nosniff ; nom imposé `AAAAMMJJ-HHMMSS-<nom demandé>` (`nom_de_document_impose`, horodatage de
`maintenant_iso`, extension en minuscules, nom demandé contrôlé par `MOTIF_NOM_DOCUMENT`, nom enregistré par
`MOTIF_NOM_DOCUMENT_ENREGISTRE` au préfixe facultatif) rendu dans le 201 et gardé par le navigateur
(`ecrireDocument` rend `nom`), 409 pour le même nom demandé dans la même seconde, documents existants inchangés ;
`rapport-contenu.js` retire ce préfixe (`nomDemande`, `Rapport.interne`) pour reconnaître un mois déjà figé
(`moisAProposer`), compter les révisions et retrouver le mois d'un rapport dans la liste (`rapport-ecrans.js`) ;
signature des images (`verifier_signature_image`, appelée par `api_document_ecrire` avant toute écriture :
`FF D8 FF`, `89 50 4E 47 0D 0A 1A 0A`, `GIF87a`/`GIF89a`, `RIFF…WEBP`, sinon 400 « Le contenu n'est pas une image
<ext> ») ; I2 `repr` du chemin (`log_request`, 200 caractères) : aucun retour à la ligne ni caractère de contrôle
venu du client n'atteint la console ni `journal-serveur.log` ; tests : `test_audit_reseau` (un test par constat, les
constats déjà prouvés — corps, 429, délai IA — cités vers `test_acces_sessions`, `test_sauvegardes_lot7`,
`test_audit_ia`) ;
I3 `ecrireValeur` pour les colonnes inconnues ; I4 masquage `[téléphone]` et `[courriel]` dans les textes envoyés à
l'IA ; G3 plage ARCEP ; G5 `.example`.

### 22.13 En-têtes de sécurité (F1)

Sur `index.html`, `GUIDE.html`, la porte et les fichiers de l'application : `Content-Security-Policy: default-src
'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self';
frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'` (la porte ajoute à `connect-src`
l'origine https du même hôte), `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Permissions-Policy:
camera=(self), microphone=(self), geolocation=()`. Les documents gardent `Content-Security-Policy: sandbox`. Le
script en ligne d'`index.html` passe dans `js/prechargement.js`.

### 22.14 Distribution et version (D131, D137)

`construire_release.py` prend dans le cache `dist/tiers/`, ou télécharge, `python-3.14.9-embed-amd64.zip` (Python
3.14.9 du 2026-10-21 : la branche 3.12 ne reçoit plus de binaires Windows, donc plus d'OpenSSL à jour) et
`mkcert-v1.4.4-windows-amd64.exe` avec sa licence, vérifie leurs empreintes (`outils/empreintes-tiers.json`, qui entre
aussi dans le zip pour que `serveur.py` vérifie mkcert), les place dans `python/` et `outils-tiers/` du zip ; `--sans-tiers`
construit le zip sans eux (développement, tests) ; `Reinitialiser_mot_de_passe.bat` entre dans le zip ; `Lancer_GMAO.bat` cherche `python\python.exe`, puis `py -3` ou `python` ≥ 3.11 ; `lancer.sh` ≥ 3.11. Le
dépôt ignore `python/` et `outils-tiers/`. Version **2.0.0** partout (`VERSION`, `VERSION_APPLICATION`,
CHANGELOG, `version.json`) ; la démo web reste sans compte.

## 23. Aide à l'écran (décision de Nicolas du 2026-10-25, avant le lot 7)

Un encart d'explication à la première visite de chaque écran, dans la démo comme dans la version installée.

- **Modules** : `js/modules/aide-ecrans-textes.js` (objet `AideEcransTextes`, une entrée par identifiant d'écran
  d'`App.ecran` : `titre`, `ancre` de `GUIDE.html`, `texte` et `essayez`, ou `profils` { responsable, technicien,
  demandeur } ; `demo` = phrase de la version web) et `js/modules/aide-ecrans.js` (objet `AideEcrans`). Textes
  validés par Nicolas (dossier de conception du site, `AIDE-ECRANS.md` § 2), produits par
  `outils/generer_aide_ecrans.py` ; à modifier à la source. Depuis T247 (chantier multilingue), le module ne garde
  que des clés (accesseurs `get … () { return I18n.t('aide.ecran.…'); }`) : les textes sont dans le fichier d'aide de
  chaque langue, `js/i18n/aide/<langue>.js` (bloc « aide » ; le bloc « acces » porte ceux d'`AccesTextes`, produits
  par `outils/generer_acces_textes.py`) ; une langue sans fichier d'aide affiche l'aide française, sans erreur.
- **Branchement** : `App.rendre`, après un affichage réussi d'un écran nouveau (pas sur une erreur d'affichage),
  appelle `AideEcrans.apresAffichage(ecran, conteneur)` ; l'encart (`UI.bandeau('info')`, `#aide-ecran`,
  `role="status"`, titre en `h2`) se place après `.entete-page` s'il existe, sinon en tête de `#contenu` ; il ne
  bloque rien et ne s'imprime pas.
- **Choix du texte** : l'entrée de l'écran, sinon celle de son `parent` (formulaires) ; À propos n'en a pas ; variante
  du profil (`App.profil.type`) ; version web (`App.versionWeb`) : phrase `demo` en tête de l'accueil, avant le geste
  ailleurs.
- **Mémoire du poste** : `prevo.aideVue` (liste JSON d'identifiants, ajoutée à « Compris » seulement) et
  `prevo.aideActive` (`'0'` = coupée) ; `localStorage` refusé : l'encart s'affiche, rien n'est retenu. Échap ferme sans
  retenir (focus dans l'encart, ou hors d'un champ et sans fenêtre ouverte).
- **Commandes** : `#btn-explications` (menu latéral) et `#btn-explications-mobile` (en-tête du téléphone) appellent
  `AideEcrans.rouvrir()` (encart de l'écran courant, même vu ; `App.ecranCourant`). Ce poste, carte « Aide à
  l'écran » : case `#poste-aide-active`, bouton `#btn-revoir-aide`.
- **Tests** : `tests/test_aide_ecrans.py`. Les autres tests coupent l'aide (`CasNavigateur.AIDE_ECRANS = False` :
  `prevo.aideActive = '0'` posé avant le chargement de chaque contexte), comme `outils/generer_captures.py`.

## 24. Textes de l'interface (multilingue, Lot 2)

Chantier multilingue, Lot 2 (« extraction des textes », décisions D145 à D166 du cahier des charges du chantier) :
tout texte visible passe par le moteur `I18n`, et le dictionnaire français est la référence. Règle du lot : **l'écran
ne change en rien** (CS148) et **aucun texte visible ne reste en dur** (CS147). Le Lot 2 ne livre que le français ;
le Lot 3 ajoute l'anglais et le sélecteur de langue (§24.10), le Lot 4 la langue du compte. Le chargement de la langue active est décrit
au §1 (`js/i18n-chargeur.js`), l'aide longue générée au §23, les messages du serveur au §7.

### 24.1 Le moteur (`js/i18n.js`, objet global `I18n`)

Script classique, compatible `file://`. Interface :

- `I18n.t(cle, valeurs)` renvoie un texte brut. Les `{nom}` sont remplacés par `valeurs.nom`.
- `I18n.html(cle, valeurs)` renvoie un fragment sûr pour `UI.html` et `UI.remplir` : le balisage écrit dans le
  dictionnaire est gardé, chaque valeur interpolée est échappée. Il sert aux phrases qui ont du HTML au milieu
  (un lien, un mot en gras).
- **Pluriels** : si l'entrée du dictionnaire est un objet `{ one: '{n} cas', other: '{n} cas' }` (les autres
  catégories CLDR sont permises), la forme est choisie par `Intl.PluralRules` de la langue active d'après
  `valeurs.n` ; une catégorie absente se replie sur `other`. Règle de Nicolas : dès qu'un nombre précède un nom,
  on écrit une entrée de pluriel, même si le français ne change pas (« {n} cas », « {n} mois »), pour que les
  langues futures puissent accorder.
- **Repli** : langue active, puis français ; une clé absente partout renvoie la clé elle-même et fait un
  `console.warn`, une seule fois par clé. Les clés `aide.*` (aide longue) se replient sur le français **sans**
  avertissement ni erreur (décision de Nicolas : une langue peut n'avoir traduit que l'interface).
- `I18n.ajouter(code, dictionnaire)` fusionne des clés dans une langue (appels répétables) ;
  `I18n.declarer(langue)` enregistre une langue ; `I18n.choisir(code)` change la langue active et l'attribut `lang`
  de `<html>` (`'fr'` par défaut, écrit dans `index.html`) ;
  `I18n.appliquer(racine)` remplit les éléments `data-i18n="cle"` (texte) et
  `data-i18n-attr="title:cle1;placeholder:cle2"` (attributs) de `index.html` ; `I18n.langue` (code actif, `'fr'`)
  et `I18n.langues` (copie des langues déclarées) sont en lecture seule.
- **Textes écrits dans les données (D156, T292)** : ce que l'appli écrit elle-même (journal, titres et motifs
  pré-remplis, profil inscrit, raisons du wiki) passe par `I18n.donnees(cle, valeurs)`, jamais `I18n.t` : la langue de
  l'installation, pas celle de l'écran. Un texte composé ailleurs (rapport figé, raison d'une gamme, contrôle d'une
  réponse de l'IA) s'écrit dans `I18n.enLangueDesDonnees(fonction)` (synchrone : `t`, `html`, `locale` y rendent
  cette langue). Depuis le Lot 4 (T295) : la langue de l'installation (`langue_defaut`, D149, §24.11) si son
  dictionnaire est chargé dans la page, sinon le français, sans erreur.

### 24.2 Les fichiers et leur ordre de chargement

- `js/i18n/langues.js` : les langues déclarées, par exemple
  `I18n.declarer({ code: 'fr', nom: 'Français', locale: 'fr-FR', statut: 'reference' })`.
- `js/i18n/<code>.js` : le dictionnaire d'une langue, **un bloc par section**, pour que des tâches menées en parallèle
  ne touchent jamais les mêmes lignes :

  ```js
  // ==== section planning ====
  I18n.ajouter('fr', {
    'planning.liste.vide': { one: '{n} intervention', other: '{n} interventions' },
    'planning.semaine.titre': 'Semaine du {date}',
  });
  // ==== fin planning ====
  ```

  Clés triées dans chaque bloc, une par ligne, chaînes entre apostrophes simples. Les échappements JS restent tels
  que dans la source : jamais d'espace insécable écrite en clair (`test_depot` la refuse), on garde ` ` et
  ` `.
- `js/i18n/aide/<code>.js` : l'aide longue, un bloc par générateur (« aide », « acces »…). Elle est à part parce
  qu'elle est produite par des outils (`outils/generer_aide_ecrans.py`, `outils/generer_acces_textes.py`, §23) et
  repliée en silence.
- **Ordre** : `js/i18n.js`, `js/i18n/langues.js`, `js/i18n/fr.js`, `js/i18n/aide/fr.js`, `js/i18n-chargeur.js`, puis
  `js/schema.js` et la suite (ordre exact au §1). `acces/porte.html` charge aussi le moteur et `fr.js` avant son
  script. Les fichiers d'une autre langue sont ajoutés par le chargeur, de façon synchrone, juste après le français
  et avant `js/schema.js`.

### 24.3 Les clés

- Forme générale : `<section>.<composant ou écran>.<élément>`, en minuscules, avec des points et des soulignés.
  La section d'un fichier est celle de son domaine (préfixe de `js/modules/`, plus le socle). Sections actuelles :
  commun, schema, valeurs, socle, planning, causes, dictee, mise, aide, ordres, demandes, parc, preventif, controles,
  garanties (2.2, lot L4, T450), wiki, suggestions, import, magasin, indicateurs, rapport, accueil, equipe, acces,
  connexion, poste, apropos, installation, porte, parametres, sauvegardes, zip, serveur, ia.
- Une clé n'est renommée que si elle est fausse ou trompeuse (le contrôle la signale).
- `schema.tables.<table>` : nom d'une table ; `schema.<table>.<champ>` : libellé d'un champ (§4).
- `valeurs.<table>.<champ>.<valeur stockée>` : affichage d'une valeur de liste (D155, voir 24.5).
- `serveur.<code>` : message de `serveur.py` traduit par le navigateur (§7).
- **`commun.*`** : mots courants (Annuler, Enregistrer, jours, mois…) décidés une fois, uniquement pour des textes
  de **même sens et même rôle** : un bouton « Enregistrer » et un titre « Enregistrer » ne partagent pas forcément
  leur clé. En cas de doute, clé propre au domaine. Depuis T257 la section `commun` est **figée** : les extractions
  de domaines menées en parallèle ne la modifient plus. L'option `--commun-existant` de `outils/extraire_textes.py`
  reprend la clé existante pour un texte identique, sans jamais en créer, et liste chaque reprise au rapport pour que
  l'on vérifie le sens et le rôle.

### 24.4 Jamais de texte figé au chargement

Un texte traduit n'est jamais calculé une fois pour toutes quand un module se charge : il est lu au moment de
l'affichage, sinon le changement de langue (Lot 3) exigerait de recharger la page. Conséquences dans le code :

- une constante qui contenait des textes devient une **fonction** (`Indicateurs.libellesPeriodes()` à la place de
  `PERIODES`) ou un **accesseur** `get` (`get titre()`, `menu: { get libelle() }` pour `App.ecran`, `id` en premier) ;
- une phrase à choix de mot (hausse ou baisse) est coupée en phrases complètes, une par cas ;
- **piège d'`Object.assign`** : `Object.assign(cible, source)` lit chaque accesseur de `source` **une seule fois** et
  copie la valeur, qui reste figée dans la cible. Pour assembler un objet à accesseurs, on utilise
  `Object.defineProperties(cible, Object.getOwnPropertyDescriptors(source))`, qui garde les accesseurs (cas de
  `wiki-regles.js`, `wiki-calculs.js`, `wiki-ingestion.js`) ;
- les constantes recopiées d'un module à l'autre au chargement (`X: Module.CONSTANTE`) sont invisibles pour l'outil :
  on les cherche à la main.

### 24.5 Ce qui n'est jamais traduit

Chaque exception est inscrite dans `outils/exceptions_textes.json`, avec sa classe et sa raison ; le contrôle ne la
signale jamais.

- **D146** : les données (jeu de démonstration compris) ne sont pas traduites, seulement l'interface.
- **D155** : les valeurs stockées des listes (statuts, types, priorités) sont des codes français fixes ; seul leur
  affichage passe par `valeurs.*`. Même classe pour les **synonymes** de titres de colonnes reconnus à l'import
  (données d'entrée, non affichées).
- **D156** : les marqueurs écrits dans les données et relus par le code (actions du journal, « Pièce : »,
  « Réception ACH- », « Ancien n° : »…) restent fixes ; le détail qui les suit s'écrit dans la langue de
  l'installation (§24.1, `I18n.donnees`), jamais dans celle de l'écran.
- **D157** : la console et les lanceurs (messages pour qui maintient l'application).
- **D159** : les consignes envoyées à l'assistant IA restent en français (avec « réponds en <langue> »). Lot 5 (T374) :
  le wiki est rédigé par l'IA dans la langue de l'installation (`I18n.langueDesDonnees`) ; ses garde-fous valent dans
  les cinq langues — vocabulaires de la sécurité et de la nouveauté par langue (`Wiki.VOCABULAIRE_*_PAR_LANGUE`, leur
  union dans `Wiki.VOCABULAIRE_*`), mois, nombres en lettres, comptages et unités (`wiki-texte.js`), forme comparable
  qui garde le ı turc ; la consigne française est inchangée, celle d'une autre langue cite aussi ses mots refusés ;
  le masquage avant envoi reconnaît les numéros internationaux (+ ou 00, turcs, portables italiens et britanniques,
  portugais).
- **identifiants** : identifiants, noms de fichiers, en-têtes CSV, codes, sélecteurs, reconnus automatiquement par
  l'outil. **titre-initial** : le `<title>` nu de `index.html` avant le chargement des scripts, remplacé ensuite par
  `App.definirTitre`.

### 24.6 Ajouter un texte, pas à pas

1. Écrire l'appel là où le texte s'affiche : `I18n.t('planning.semaine.titre', { date: d })`, ou `I18n.html(…)` s'il
   contient du HTML ; en HTML statique, `data-i18n` ou `data-i18n-attr`. Dans une constante ou un objet, passer par
   une fonction ou un accesseur (24.4).
2. Ajouter la clé dans le bon bloc de `js/i18n/fr.js`, à sa place triée. Si un nombre précède un nom, écrire l'entrée
   de pluriel `{ one, other }` avec la variable `n`. Les variables portent un nom parlant (pas `{v1}`).
3. Pour un mot courant déjà présent dans `commun`, reprendre sa clé seulement si sens et rôle sont les mêmes.
4. Lancer `py -X utf8 outils/controler_textes.py --domaine <domaine>` : il doit répondre 0.
5. Lancer les tests du domaine et la photographie des écrans (24.7) : l'écran doit être identique.

Pour extraire en masse, on remet d'abord à la main les cas du rapport en forme saine, puis
`py -X utf8 outils/extraire_textes.py --domaine <d> --essai` (rapport sans écriture), puis la même commande sans
`--essai`, et l'on ne renomme que ce que le contrôle signale. Un nouveau message de `serveur.py` s'écrit
`traduisible(…)` (§7). Une valeur de liste du schéma reçoit sa clé `valeurs.…`.

### 24.7 Les outils et ce qu'ils vérifient

- `outils/extraire_textes.py` : classe les textes visibles d'un fichier ou d'un domaine, écrit les clés et réécrit
  les appels. Les cas douteux vont au rapport de relecture, ils ne sont pas extraits.
- `outils/controler_textes.py` (**CS147**) : aucun texte visible en dur hors exceptions ; clés manquantes ou orphelines
  (une clé calculée ne couvre plus tout le dictionnaire depuis T262) ; variables `{…}` identiques entre l'appel et la
  valeur, noms génériques refusés ; texte de `index.html` sous `data-i18n` égal à la valeur du dictionnaire. Code
  retour 0 si rien à signaler. `--domaine` limite aux fichiers d'un domaine (répétable).
- `outils/textes_serveur.py` : le même contrôle pour `serveur.py` (module `ast`), appelé par le précédent pour le
  domaine « serveur » ; `--ecrire` complète la section serveur de `fr.js`.
- `outils/photographier_ecrans.py` (**CS148**) : relève les textes visibles et les attributs de chaque écran, pour
  chaque profil, en **démo** (`index.html` en `file://`) et en **mode serveur** (serveur sur une copie du jeu de
  démo, base vide, porte des téléphones), et les compare aux relevés de référence de
  `tests/fixtures/ecrans-reference/` (`demo.json`, `serveur.json`). Options utiles : `--mode`, `--ecrans`
  (expression régulière), `--captures` et `--comparer-captures` pour les images.
- Les tests existants ne changent pas : les textes qu'ils attendent sont ceux d'avant le chantier.

### 24.8 Messages du serveur

`serveur.py` envoie les messages affichables avec leur code (`"erreur_code"`, `"erreur_valeurs"`) à côté du
français ; le navigateur affiche la clé `serveur.<code>` (`StockageServeur.texte` pour les modules qui font leur
propre `fetch`). Écriture, règles et contrôle : §7 et `outils/textes_serveur.py`.

### 24.9 Contrôle d'une langue (Lot 3, T264)

`py -X utf8 outils/controler_textes.py --langue <code>` (répétable ; module `outils/textes_langues.py`, **CS149**,
**CS151**) compare `js/i18n/<code>.js` et `js/i18n/aide/<code>.js` au français, que la langue soit déclarée ou non
(le fichier de la langue est requis) : clés manquantes ou orphelines, mêmes variables `{…}` (toutes catégories
réunies), même section, clés définies deux fois, bloc `I18n.ajouter` d'une autre langue. Une entrée plurielle en
français l'est dans la langue avec exactement les catégories requises, une entrée simple reste simple. Catégories
requises (entiers, CLDR) : `one, other` pour fr, en, tr, it et pt-PT, et pour un code absent de la table ; `many`
(fr, it, pt) n'est pas requis, il ne sert qu'aux multiples d'un million et à la notation compacte, que Prévo
n'affiche pas. Les clés de l'aide longue manquantes ne sont qu'un avertissement tant que `js/i18n/aide/<code>.js`
n'a aucune clé (repli voulu sur le français) ; une valeur identique au français n'est pas un écart. `--domaine`
limite aux sections de ces domaines (traduire groupe par groupe) ; `--langue fr` : le contrôle du français seul.
Sans option, le français et chaque langue déclarée dans `js/i18n/langues.js` sont contrôlés : une langue n'entre
dans le contrôle par défaut qu'une fois déclarée. `js/i18n/en.js` a les sections de `fr.js`, dans le même ordre.

### 24.10 Choix de la langue (Lot 3, T278)

Langues déclarées (`js/i18n/langues.js`, dans l'ordre du sélecteur) : français (référence, `fr-FR`) et anglais
britannique (`en`, locale `en-GB`, D151). Le sélecteur (`UI.selecteurLangue`, `js/interface.js`, D147) est une liste
déroulante native : chaque langue sous son nom dans sa langue (« Français », « English », tirés de `langues.js`, jamais
du dictionnaire), sans drapeau, la langue active choisie. Deux emplacements, une seule construction : l'écran
« Ce poste », carte « Affichage » (ligne « Langue de l'écran », `<label for>`, phrase « Choix gardé par ce navigateur,
pour ce poste. ») ; le pied du menu latéral, sous « Explications » (`#menu-langue`, rempli par `js/app.js` ; la liste
seule, nommée par son `aria-label`), caché quand le menu n'a que ses icônes (tablette, menu replié) et, comme tout le
menu, au téléphone. Au changement (D148, sans compte) : le choix est retenu par le navigateur du poste
(`localStorage` « prevo.langue » ; la langue qu'aurait le poste sans choix, celle de l'installation, retire la clé,
§24.11), puis la page est rechargée (`location.reload()`) :
`js/i18n-chargeur.js` charge la langue avant `js/schema.js`. Pas de changement de langue sans rechargement. Stockage
refusé : message court, la liste revient à la langue active, la page reste dans sa langue. En démo, le rechargement
ramène à l'écran de démarrage (la démo vit dans la page). Viennent au Lot 4 : la langue du compte et la bascule à la
connexion (D148), la langue du navigateur (`navigator.language`) pour la démo (D150).

### 24.11 Langue de l'installation (Lot 4, T295)

`langue_defaut` (D149) est une ligne de `parametres.csv` (code d'une langue déclarée, `fr` par défaut), réglée dans
Paramètres, section « Entreprise » (« Langue de l'installation », les langues sous leur nom dans leur langue), dans
tous les modes ; une ligne de plus, pas une colonne : le format des fichiers (`version_schema`) ne change pas, et le
serveur l'accepte comme toute clé (`parametres` est une table clé-valeur). Elle sert à deux choses :

- **Langue affichée** (D148, D150 ; T298) : 0. la langue du compte connecté (ci-dessous) ; 1. le choix de ce poste
  (« prevo.langue ») ; 2. sinon la langue de l'installation ; 3. sans réglage (ni l'un ni l'autre : démo, ou première ouverture avant toute base ; clé
  « prevo.langue.installation » absente), la langue du navigateur (`navigator.languages`, dans l'ordre : code exact, puis
  langue sans région ; toute variante `pt-*`, dont `pt-BR`, va à `pt-PT` ; `I18n.langueDuNavigateur`, T299), sinon
  l'anglais ; 4. le français n'est atteint que par `I18n.langueAAfficher` appelée sans les langues du navigateur (`js/app.js`
  une fois les paramètres lus). Aujourd'hui seuls `fr` et `en` sont déclarés : une langue non déclarée (de, tr, it, pt…) donne
  l'anglais. Dans la démo, changer de langue recharge la page et efface ce qu'on y a modifié : `UI.selecteurLangue`
  demande d'abord confirmation (`UI.confirmer`) ; Annuler remet la liste sur la langue actuelle. Hors démo, aucun
  avertissement. (`I18n.langueAAfficher`) Toute valeur est vérifiée contre les
  langues déclarées : vide, inconnue ou mal formée, elle est ignorée. Le chargeur tourne avant toute lecture des
  données : la langue de l'installation lui vient de `localStorage` « prevo.langue.installation », que `js/app.js`
  écrit chaque fois qu'il lit `parametres.csv` (ouverture des données, changement sur ce poste ou un autre ;
  `suivreLangueInstallation`). Si la page n'est alors pas dans la langue à afficher, ou n'a pas le dictionnaire de
  l'installation, elle se recharge **une fois** : la raison est notée dans `sessionStorage` (« prevo.langue.rechargement »)
  et jamais deux rechargements de suite pour la même (sans `sessionStorage`, aucun). Un changement venu d'un autre
  poste n'interrompt pas une saisie en cours. Démo et fichiers déposés : la langue est notée pour les données, rien
  n'est retenu ni rechargé (un rechargement perdrait les données, qui vivent dans la page).
- **Langue du compte** (T298) : `GET /api/session` porte la langue du compte (§22.4) ; `js/app.js`
  (`suivreLangueDuCompte`) l'écrit dans `localStorage` « prevo.langue.compte » dès qu'il connaît la session (ouverture,
  connexion) et l'efface sans session de compte (déconnexion, ouverture sans session, appareil enrôlé, sans comptes,
  modes dossier et démo ; une session perdue pendant l'usage la garde, T329, §8) ;
  `js/i18n-chargeur.js` la lit en premier (`I18n.langueAAfficher`, 4e argument,
  valeur vérifiée contre les langues déclarées). Une page qui n'est pas dans la langue que le chargeur choisirait se
  recharge une fois, avec la même garde (`rechargerPourLaLangue`) : après la connexion, la langue du compte ; après la
  déconnexion, celle du poste ou de l'installation (poste ou tablette partagés) ; jamais quand la session se perd
  pendant l'usage (T329 : la saisie serait perdue ; l'écran de connexion reste dans la langue du compte). La personne choisit sa langue sur
  « Ce poste », carte Affichage, quand une session de compte est ouverte : « Pour mon compte » (enregistrée dans le
  compte, `App.changerLangueDuCompte` → `POST /api/mot-de-passe {"langue"}` ; elle la suit sur tous les postes) ou
  « Pour ce poste seulement » (comme sans comptes ; la langue du compte est alors retirée, sinon elle passerait
  devant) ; coché d'abord : « pour mon compte » si le compte a sa langue ; changer de choix garde la langue affichée.
  La liste du menu suit la même règle (au compte s'il a sa langue, sinon au poste). Sans comptes, rien ne change.
- **Textes écrits dans les données** (D156) : `I18n.donnees` et `I18n.enLangueDesDonnees` écrivent dans la langue de
  l'installation (`I18n.noterInstallation`, `I18n.langueDesDonnees`), quelle que soit la langue de l'écran ; le
  chargeur charge aussi `js/i18n/<code>.js` de l'installation (sans son aide longue) quand elle n'est ni le français
  ni la langue affichée ; dictionnaire absent : le français.

**Base neuve** (T296 ; D149, D165) : partout où une base est créée, la liste « Langue de Prévo » (les langues
déclarées sous leur nom dans leur langue, `UI.optionsLangues`) propose la langue du navigateur ramenée à une langue
déclarée (`UI.langueDuNavigateur`, qui appelle `I18n.langueDuNavigateur` : sinon l'anglais) et la valeur va dans
`parametres.csv` (`langue_defaut`) à la création. Trois chemins : l'assistant d'installation (étape 8, carte « Par
quoi commencer ? » sur une base absente au départ ; `POST /api/installation/terminer` reçoit `langue_defaut`, §22.10 —
Solo compris : même route) ; l'écran « base vide » (`#ecran-base-vide`, liste `#base-vide-langue`, mode serveur sans
assistant et mode dossier : `remplirBaseVide` écrit `version_schema` et `langue_defaut`, ou ajoute `langue_defaut`
aux lignes du jeu de démo). Tant que la base est vide, `suivreLangueInstallation` ne retient ni ne recharge rien : la
page reste dans la langue du navigateur (sans cela, en mode dossier, un rechargement perdait le dossier choisi) ; la
base créée, la langue choisie s'applique (un rechargement s'il le faut). Une base existante n'est jamais touchée.

---

## 25. Format 4 (2.2) : réserves, garanties, contrats, catalogues (D182-D193, CS169-CS180)

Référence des règles de migration, de sauvegarde et de compatibilité : **[FORMAT.md](FORMAT.md)** (§2, §5, §6, §7).
Ici, le contrat du code. Le format 4 ne change aucun écran à lui seul : il pose les données que les lots suivants de
la 2.2 afficheront.

- `Schema.version` = **4** ; **27 tables** : les 24 du format 3 puis `reserves_controle`, `garanties` et
  `contrats_prestataires` (`depuisVersion: 4`, dans cet ordre, après `wiki_journal`). Le détail des colonnes est dans
  `js/schema.js` et [FICHE_TECHNIQUE_CSV.md](../FICHE_TECHNIQUE_CSV.md) ; `serveur.py` en est le miroir exact
  (`TABLES`, `COLONNES_PAR_TABLE`, `PREMIER_FORMAT_DES_TABLES`, `PREMIER_FORMAT_DES_COLONNES`, `DEFAUTS_DES_CHAMPS`,
  `COLONNES_DES_FORMATS_SUIVANTS`, `ETAPES_FORMAT`), comparé au navigateur par `tests/test_formats_serveur.py` et
  `tests/test_formats_js.py`.
- **Colonnes ajoutées** (en fin de table, après les colonnes inconnues) : `equipements.cout_arret_h` ;
  `ordres_travail.habilitation_requise` ; `habilitations.recyclage_mois`, `justificatif`, `catalogue_id`,
  `nature_source` ; `controles_reglementaires.source_periodicite` (défaut `saisie`), `nature_source`, `catalogue_id`,
  `catalogue_relu_le`. Attention : `habilitation_requise` existe dans `equipements` et dans `ordres_travail` ; un code
  qui fusionne les deux objets (`Object.assign`) écraserait l'une par l'autre.
- **`reserves_controle`** (`RES-` + 5 chiffres, identifiant non annuel pour que la reprise donne les mêmes identifiants
  des deux côtés) : une ligne par réserve ; `controle_id`, `date_controle`, `texte`, `gravite`, `echeance_levee`,
  `levee` (0 ou 1), `date_levee`, `commentaire_levee`, `ot_id`. **`garanties`** (`GAR-` + 4 chiffres) et
  **`contrats_prestataires`** (`CTP-` + 4 chiffres, `equipement_ids` séparés par « ; ») ont un `actif` : on désactive,
  on ne supprime pas (FORMAT.md §3).
- **Reprise des observations (D183)** : `Formats.reservesReprises` (`js/formats.js`) et `reserves_reprises`
  (`serveur.py`), mêmes réserves aux mêmes octets. Règle par contrôle (un contrôle avec observations et sans réserve
  reçoit une réserve par ligne non vide), idempotente, jamais « table vide » ; la constante de commentaire
  `COMMENTAIRE_LEVEE_REPRISE` est la même des deux côtés. Pièges de parité : le serveur travaille sur les cellules
  du fichier (apostrophe de protection relue avant la découpe), le navigateur sur les valeurs en mémoire ; découpe
  des lignes sur `\r\n`, `\r` ou `\n` seulement ; numéros lus par `RES-[0-9]+`, écrits sur au moins 5 chiffres ;
  dates et booléens lus par des copies de `Donnees.normaliser` (tests de concordance).
- **Qui l'exécute** : fonction pure de l'étape (import ZIP, tests) ; mode dossier (`migrerAuFormatCourant`) ; mode
  serveur (au démarrage, avant toute connexion) ; la démo naît déjà au format 4. Sauvegarde `avant-format-v4` d'abord,
  `version_schema` écrit en dernier (§5.6).
- **Export et import ZIP** : `ZipDonnees.CHAMPS_DOCUMENTS` est dérivé du schéma (les champs `document` des tables
  nouvelles et `habilitations.justificatif` sont donc exportés) ; l'import d'un ZIP de la 2.1 le passe au format 4
  (réserves reprises) sans annoncer la table nouvelle comme « vidée » ; un ZIP du format 5 est refusé.
- **Compatibilité** : la 2.2 ouvre un format 5 en lecture seule ; une 2.0.0-beta.2, 2.0.0 ou 2.1.0 ouvre un format 4
  en lecture seule (sauvegardes de démarrage limitées à leurs 24 tables) ; une 1.2.x ou 2.0.0-beta.1 n'a pas de
  garde (FORMAT.md §7).
- **Écarts connus** (tests `expectedFailure` de `tests/test_formats_serveur.py`) : place d'une colonne inconnue de
  `controles_reglementaires` (écart A, navigateur et serveur ne la rangent pas au même endroit) ; colonnes
  manquantes complétées en fin par l'étape (B) ; dates d'Excel normalisées par le navigateur seulement (C).
