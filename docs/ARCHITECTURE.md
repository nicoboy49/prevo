# Architecture de Prévo

Ce document est le **contrat interne** du code : tout fichier JavaScript ou Python le respecte.
Il est écrit pour être lu par un stagiaire comme par une IA qui code un lot suivant. En cas de
doute, `brief-gmao.md` fait foi, puis ce document.

---

## 1. Vue d'ensemble

```
index.html                 page unique de l'application
favicon.svg                logo (engrenage dans un carré dégradé)
serveur.py                 serveur local (Python 3.8+, bibliothèque standard seulement)
Lancer_GMAO.bat            lanceur Windows      lancer.sh   lanceur Mac/Linux
css/style.css              charte « Cockpit » adaptée (écran sombre + impression noir sur blanc)
css/modules/*.css          mise en page propre à chaque module (une feuille par module : app, accueil,
                           parc, demandes, ordres, preventif, magasin, parametres ; chargées par index.html)
css/polices/               police Sora (OFL)
js/lib/                    bibliothèques tierces + LICENCES.txt (jamais modifiées)
js/schema.js               Schema    : description des 22 tables (champs, types, identifiants)
js/donnees.js              Donnees   : CSV, chargement, contrôle, mutation, journal, rafraîchissement
js/stockage-serveur.js     StockageServeur : adaptateur « serveur » (API HTTP)
js/stockage-dossier.js     StockageDossier : adaptateur « dossier » (File System Access)
js/stockage-demo.js        StockageDemo    : adaptateur « démo » (mémoire)
js/demo-donnees.js         DEMO_DONNEES : jeu de démo généré (chargé à la demande)
js/interface.js            UI        : helpers d'écran (html, tableaux, fenêtres, QR, photos…)
js/modules/*.js            modules métier : un module = un préfixe de fichiers (§14.2), ex.
                           ordres-regles.js … ordres-impression.js pour l'objet Ordres ; petits
                           modules en un seul fichier (accueil.js, apropos.js, parametres.js,
                           causes-frequentes.js)
js/app.js                  App       : démarrage, choix du mode, profils, navigation
donnees/                   les CSV réels (hors dépôt git) + documents/ + sauvegardes/
donnees/demo/              le jeu de démo en CSV (versionné)
outils/generer_demo.py     génère donnees/demo/*.csv, js/demo-donnees.js et tests/fixtures/demo-scenarios.json
tests/                     tests automatisés (unittest + Playwright) ; tests/fixtures/ : pages et
                           fichiers d'essai (servis seulement avec serveur.py --servir-tests, §7)
```

**Ordre de chargement dans `index.html`** (scripts classiques, jamais `type="module"`) :
`js/lib/papaparse.min.js`, `js/lib/qrcode.js`, `js/lib/jsQR.js`, `js/lib/jszip.min.js`,
`js/schema.js`, `js/donnees.js`, `js/stockage-serveur.js`, `js/stockage-dossier.js`,
`js/stockage-demo.js`, `js/interface.js`, les fichiers de `js/modules/` dans l'ordre exact du
§14.2, `js/app.js` (en dernier).
`js/demo-donnees.js` n'est **pas** chargé au démarrage : `App` l'injecte (balise `<script>`
créée dynamiquement, compatible `file://`) quand on choisit la démo ou la copie du jeu de démo.
ECharts (présent dans `js/lib/`) n'est chargé qu'à partir du lot 3.

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
  version: 2,                          // version du format des fichiers (§14.1) ; 1 au lot 1
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
    // … 22 tables : d'abord exactement les champs du §6 du brief, dans le même ordre,
    // puis, en fin de table, les champs ajoutés par le format v2 (depuisVersion: 2, §14.1)
  },
};
```
Types : `id`, `texte`, `texte_long`, `entier`, `decimal`, `date`, `date_heure`, `booleen`,
`choix` (avec `valeurs`), `ref` (avec `table`, et `champCible` si ce n'est pas la clé — ex. les
`*_code` des OT visent `codes_defaillance.code` filtré par `famille`, attribut `filtre`), `document`
(nom de fichier dans `donnees/documents/`). Champs facultatifs : `libelle` (toujours renseigné, en
français), `obligatoire`, `defaut`, `protege`, `synonymes` (pour l'assistant d'import futur),
`depuisVersion` (version du format qui a ajouté le champ : `2` pour les quatre champs du §14.1 ;
absent pour les champs du brief).

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
await Donnees.mettreAJourVersionSchema()   // passage au format courant, sauvegarde d'abord (§5.6)
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

### 5.5 Rafraîchissement
`Donnees.demarrerSurveillance()` : toutes les `rafraichissement_s` secondes (20 par défaut) et à
chaque retour sur l'onglet (`visibilitychange`), `adaptateur.listerVersions()` ; chaque table
dont la version diffère est relue ; événement `changement` (`origine: 'distant'`).

### 5.6 Passage au format courant : `mettreAJourVersionSchema` (lot 2)
`await Donnees.mettreAJourVersionSchema()` → `{ misAJour, sauvegarde }`. Appelée par `App` au
démarrage, après `chargerTout()`, **pour tous les profils et avant toute autre écriture** (§8).
- Rien à faire (renvoie `{ misAJour: false, sauvegarde: null }`) si la base est vide ou si
  `parametres.version_schema` vaut déjà `Schema.version` (ou plus).
- Sinon, **décision de Nicolas** : d'abord une sauvegarde automatique complète
  `adaptateur.sauvegarder('avant-format-v2')`, nommée `AAAA-MM-JJ_HHMMSS_avant-format-v2`
  (restaurable depuis Paramètres, où elle apparaît avec le type « Avant format 2 ») ; **puis
  seulement** `version_schema` passe à 2, par un `modifier('parametres')` décidé sur les lignes
  fraîches (si un autre poste l'a déjà fait, rien n'est écrit). Journal : « passage au format 2 du
  fichier ; sauvegarde … faite juste avant ».
- Si la sauvegarde échoue, ou si le stockage ne sait pas sauvegarder (pas de méthode `sauvegarder`,
  ou aucun nom renvoyé) : `ErreurStockage` (« Sauvegarde avant le passage au format 2 impossible :
  … ; la mise à jour sera retentée à la prochaine ouverture. »), et `version_schema` **n'est pas
  changé**. Seule exception : la démo (rien n'y est enregistré, aucune sauvegarde n'est exigée).
- Deux postes ouverts ensemble sur une base au format 1 peuvent faire chacun leur sauvegarde (deux
  copies identiques, sans gravité) ; un seul écrit la version.
- « Créer une base vide » écrit directement `version_schema` = 2 dans `parametres.csv` : pas de
  sauvegarde inutile au premier démarrage. Le jeu de démo porte déjà `version_schema` = 2.

## 6. Adaptateurs de stockage (contrat commun)

Chaque fichier `js/stockage-*.js` expose une fabrique : `await StockageServeur.creer()`,
`await StockageDossier.creer(poigneeDossier)`, `StockageDemo.creer(tablesCsv)`. L'objet rendu :

```
mode                                  'serveur' | 'dossier' | 'demo'
libelle                               texte affiché (ex. « Serveur 192.168.1.10:8080 »)
await charger(table)                  → { octets: Uint8Array|null, version: string|null }  (null = fichier absent)
await enregistrer(table, octets, versionAttendue)   → { version }
                                      versionAttendue null = le fichier ne doit pas exister ; sinon ErreurConflit
await ajouter(table, octets)          → { version }  (ErreurConflit si en-tête/encodage différent)
await listerVersions()                → { nomTable: version|null, … }
await ecrireDocument(nom, blob)       → nom   (refuse d'écraser un document existant)
await lireDocument(nom)               → Blob|null
await urlDocument(nom)                → URL affichable (serveur : /api/documents/nom ; sinon URL d'objet)
await sauvegarder(motif?)             → nom de la sauvegarde : manuelle sans motif (AAAA-MM-JJ_HHMMSS) ;
                                      avec motif 'avant-format-v2' (liste fermée, le seul motif accepté)
                                      → AAAA-MM-JJ_HHMMSS_avant-format-v2 ; autre motif → ErreurStockage
await listerSauvegardes()             → [{ nom, tables: [...] }]  (plus récente d'abord)
await restaurer(nom, tables?)         → { restaurees: [...], copieSecurite: nom }
await info()                          → { adressesReseau: [...] } (serveur) ou {}
```
Version d'un fichier = empreinte SHA-256 du contenu, 16 premiers caractères hexadécimaux
(décision D7). Sauvegarde quotidienne : avant la **première écriture de la journée**, copie de
tous les CSV dans `sauvegardes/AAAA-MM-JJ/` (si ce dossier n'existe pas). Une restauration copie
d'abord l'état courant dans `sauvegardes/AAAA-MM-JJ_HHMMSS_avant-restauration/`. Le passage au
format 2 (§5.6) copie tous les CSV dans `sauvegardes/AAAA-MM-JJ_HHMMSS_avant-format-v2/`. Noms de
sauvegarde acceptés (serveur et dossier, mêmes règles) :
`AAAA-MM-JJ`, `AAAA-MM-JJ_HHMMSS`, `AAAA-MM-JJ_HHMMSS_avant-restauration`,
`AAAA-MM-JJ_HHMMSS_avant-format-vN`. Le mode dossier
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

Réponses JSON `{"erreur": "message en français"}` en cas d'erreur. Toute requête qui écrit
(`PUT`, `POST`) exige l'en-tête **`X-Prevo: 1`** (sinon 403). Corps limité à **10 Mo**
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
| `PUT /api/csv/<table>` | en-tête `X-Version-Attendue: <version>` ou `aucune` ; 200 `{"version"}` · 409 `{"erreur", "version_actuelle"}` · 423 si le fichier est verrouillé (Excel ouvert) |
| `POST /api/csv/<table>/ajout` | corps = en-tête + lignes (UTF-8 sans BOM) ; ajoute en fin de fichier (crée le fichier avec BOM s'il n'existe pas) ; 409 si l'en-tête ou l'encodage du fichier existant diffère |
| `GET /api/documents/<nom>` | octets, type MIME deviné ; 404 |
| `PUT /api/documents/<nom>` | 201 `{"nom"}` · 409 si le document existe déjà |
| `POST /api/sauvegarde` | corps vide → sauvegarde manuelle `{"sauvegarde": "AAAA-MM-JJ_HHMMSS"}` ; corps JSON facultatif `{"motif": "avant-format-v2"}` → `{"sauvegarde": "AAAA-MM-JJ_HHMMSS_avant-format-v2"}` ; motif hors de la liste fermée `MOTIFS_SAUVEGARDE`, corps qui n'est pas un objet JSON, JSON invalide ou trop imbriqué → 400 (contrôlé avant toute écriture) |
| `GET /api/sauvegardes` | `{"sauvegardes": [{"nom", "tables": [...]}]}` |
| `POST /api/restauration` | corps `{"sauvegarde": "…", "tables": [...] (facultatif)}` → `{"restaurees", "copie_securite"}` |

Règles : noms de tables limités aux 22 du schéma (liste recopiée dans `serveur.py`, avec un
commentaire de renvoi vers `js/schema.js`, cohérence vérifiée par un test) ; nom de document
`^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$` sans `..` ; nom de sauvegarde
`^\d{4}-\d{2}-\d{2}(_\d{6}(_avant-restauration|_avant-format-v\d+)?)?$` ; tout chemin résolu doit
rester sous `donnees/` (vérification sur le chemin brut **et** décodé, `\` compris) ; écriture
atomique (fichier temporaire dans le même dossier, `fsync`, `os.replace`) ; un verrou global
sérialise les écritures ; sauvegarde quotidienne faite par le serveur avant la première écriture
du jour. Les corps JSON (`/api/sauvegarde`, `/api/restauration`) sont lus par `lire_objet_json` :
UTF-8 invalide, JSON invalide, JSON qui n'est pas un objet ou trop imbriqué (`[[[[…`) → 400, jamais
500.

**Fichiers statiques : liste blanche (lot 2, D29).** Seuls sont servis `/` (→ `index.html`),
`index.html`, `favicon.svg`, `GUIDE.html` s'il existe, et tout ce qui est sous `css/` et `js/`
(constantes `FICHIERS_PUBLICS`, `DOSSIERS_PUBLICS` de `serveur.py` ; comparaison sans casse, car
Windows ne distingue pas `Index.html` de `index.html`). **Tout le reste répond 404**, comme un
fichier absent : `brief-gmao.md`, `README.md`, `docs/`, `tests/`, `outils/`, `reference-design/`,
`serveur.py`, les lanceurs… La liste blanche est contrôlée sur le chemin demandé **et** sur le chemin
résolu (un lien ou une jonction rangé dans `js/` ne permet pas de lire un fichier situé ailleurs).
Les contrôles du lot 1 restent en place avant elle : chemin dont un segment commence par `.`
(fichier caché, `..`), contient `:` ou finit par `.` ou une espace, `\` ou `%5C`, double encodage →
400 ; `donnees/` → 403. L'option `--servir-tests` (passée par `tests/commun.py`) sert en plus
`tests/fixtures/` (pages et fichiers d'essai des tests). Pas d'en-têtes CORS.
Le serveur parle HTTP/1.1 avec connexions persistantes (`protocol_version = 'HTTP/1.1'` : un
navigateur réutilise ses connexions au lieu d'en ouvrir une par requête), avec une file d'attente
d'écoute de 128 connexions (`request_queue_size = 128`) et un fil par connexion.
Lancement : `py serveur.py [--port 8080] [--donnees CHEMIN] [--sans-navigateur] [--hote NOM]
[--servir-tests]` ; port suivant si occupé (jusqu'à +20) ; affiche l'adresse locale et les adresses
réseau ; ouvre le navigateur. `--servir-tests` n'est utile qu'aux tests automatiques.
Adresses réseau : interface de sortie trouvée par un `connect()` UDP vers une adresse privée
(aucun paquet envoyé) + `gethostbyname_ex`, adresses de bouclage exclues.

## 8. Application (`js/app.js`, `index.html`)

**Démarrage** : si la page est en `http(s)` et que `GET /api/ping` répond (délai 2 s) → mode
serveur. Sinon écran de démarrage : « Choisir le dossier de données » (si
`showDirectoryPicker` existe), « Reprendre le dossier précédent » (si une poignée est mémorisée),
« Essayer avec les données de démo », zone de dépôt de CSV (démo à partir de fichiers déposés).
Base vide (aucun CSV) → choix « Créer une base vide » ou « Partir des données de démo ».
Navigateur sans File System Access → message « utilisez Chrome ou Edge » + démo.

Suite du démarrage (lot 2), dans cet ordre, **avant le premier écran** :
1. tables chargées → `Donnees.mettreAJourVersionSchema()` (§5.6), pour tous les profils et avant
   toute autre écriture ; en cas d'échec (sauvegarde impossible), l'erreur est signalée, un bandeau
   « Les fichiers n'ont pas pu passer au format 2 » s'affiche dans la coque, et l'application reste
   utilisable ;
2. profil (mémorisé ou demandé) ;
3. technicien ou responsable : `Preventif.genererOTEchus()` (RG5, §14.3) ; toast « n OT préventifs
   générés » si n > 0 ; erreur → `App.signalerErreur`, l'application reste utilisable. **Pas de
   génération automatique si l'étape 1 a échoué** (elle écrirait des fichiers au format 2 sans
   sauvegarde confirmée) : la prochaine ouverture retente tout. Puis
   `performance.mark('prevo:preventif')`, posée une seule fois, aussi pour le demandeur (rien à
   générer) ;
4. surveillance, coque, premier écran, état « prêt » (`prevo:preventif` précède donc `prevo:pret`).

**Profils** (localStorage `prevo.profil` = JSON `{type: 'demandeur'|'technicien'|'responsable',
nom, technicienId}` ; `prevo.poste` = nom du poste). Si aucun profil n'est mémorisé, l'écran de
profil s'affiche, puis l'application revient à la route demandée (cas du QR scanné).

**État prêt** : quand les tables sont chargées et le premier écran affiché,
`document.documentElement.dataset.etat = 'pret'` et `performance.mark('prevo:pret')` (lus par
les tests). Pendant le chargement : `'chargement'` ; écran de démarrage : `'demarrage'` ; écran
de profil : `'profil'`.

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
Profils : l'accueil, les DI, le parc et À propos sont ouverts aux trois profils ; les OT
(`#/ot`, `#/ot/<id>`), le préventif (`#/preventif`, `#/preventif/gamme/<id>`) et le magasin
(`#/magasin`, `#/magasin/article/<id>`) au technicien et au responsable (le technicien y est en
consultation, D27) ; `#/ot/nouveau`, la création et la modification d'équipement,
`#/preventif/gamme/nouvelle`, `#/magasin/article/nouveau`, `#/parametres` et `#/controle` au
responsable seul. Le demandeur ne voit ni Préventif ni Magasin.
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
  `?recherche=`.

Un écran dont un formulaire a été modifié et non enregistré n'est pas
réaffiché par un changement distant : un bandeau « Des données ont changé sur un autre poste —
Actualiser » s'affiche à la place.
`App` expose : `App.version`, `App.dateVersion`, `App.mode`, `App.profil`, `App.poste`,
`App.adaptateur`, `App.ecran(définition)`, `App.naviguer(hash)`, `App.reafficher()`,
`App.definirTitre(texte)`, `App.marquerSaisie(booléen)`, `App.estResponsable()`,
`App.estTechnicien()`, `App.estDemandeur()`, `App.libelleProfil()`, `App.changerProfil()`,
`App.urlFicheEquipement(id)` (URL réseau en mode serveur, sinon `GMAO:<id>`),
`App.chargerScriptDemo()`, `App.exporterZip()`, `App.signalerErreur(erreur)`.

**Menu** : latéral sur grand écran (≥ 1100 px), repliable en icônes (mémorisé
`prevo.menuReplie`), icônes seules de 641 à 1099 px, barre du bas sur téléphone (≤ 640 px :
4 entrées + « Plus »). En tête du menu latéral : « Prévo », « GMAO », puis le nom de l'entreprise
(`entreprise_nom`) sur deux lignes au plus, nom complet en infobulle (D32). Entrées ajoutées au
lot 2 : « Préventif » (ordre 35, icône `preventif`) et « Magasin » (ordre 45, icône `magasin`).
Badge de signature en bas du menu : « Développé par Claude (Anthropic) à
la demande de Nicolas Briand — SELECTIS » → `#/apropos`.
`#impression` doit être un enfant direct de `<body>` (la feuille d'impression masque tous les autres
enfants de `body`) ; `#toast` (vide, `role="status"`) est présent dans `index.html` dès le chargement.

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
pour masquer un élément à l'impression (réutilisée par le futur rapport mensuel).

`css/style.css` porte la charte et **tous les composants communs** ; un module n'y touche pas :
sa mise en page propre va dans `css/modules/<module>.css` (une feuille par module, même découpé en
plusieurs fichiers JS ; toutes référencées par `index.html`, dont `preventif.css` et `magasin.css`
au lot 2), en réutilisant les variables de la charte (jamais de couleur codée en dur).
`UI.icone(nom)` connaît depuis le lot 2 les icônes `preventif` (calendrier coché) et `magasin`
(carton) ; `UI.estTelephone()` sert à masquer la carte « Connecter un téléphone » de l'accueil (D31).
Les champs `texte_long` des formulaires portent l'attribut `data-dictee` (crochet pour le bouton
micro du lot 4 ; en attendant, la dictée du clavier du téléphone fonctionne sans code).

## 10. Règles métier (lots 1 et 2)

RG1 à RG4, RG7 et RG8 viennent du lot 1 (RG3 révisée au lot 2, voir ci-dessous) ; RG5 (préventif)
et RG6 (magasin) sont détaillées aux §14.3 et §14.4.

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
- « OT en retard » : statut ni clôturé ni annulé et `date_prevue` < aujourd'hui. « P1 ouvert » :
  priorité P1, statut ni clôturé ni annulé. « DI à traiter » : statut `Nouvelle`.

Les fonctions de règles sont **pures** et exposées pour les tests :
`Demandes.prioriteCalculee(criticite, impact)`, `Ordres.transitionsPossibles(ot)`,
`Ordres.verifierPassage(ot, statutCible)` → `{ ok, erreurs, avertissements }`,
`Ordres.verifierCloture(ot)` → liste des manques, `Ordres.cout(ot)`,
`Ordres.verifierHabilitation(equipement, technicienId, dateIso)` → message ou `null`.

### API effective des modules (`js/modules/`, état du lot 2)

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
  (§14.6).
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
  { minimum })`, `encart(equipementId, symptomeCode)`.
- **`Accueil`** : `afficher`, `calculerCompteurs()` → `{ diATraiter, otEnRetard, p1Ouverts,
  preventifsSemaine, articlesACommander }` (les quatre premières : listes de lignes de demandes ou
  d'OT ; `articlesACommander` : éléments de `Magasin.aCommander()`), `otEnRetard(ot, aujourdhui)`,
  `p1Ouvert(ot)`, et depuis le lot 2 `dimancheDe(dateIso)` (dimanche de la semaine du lundi au
  dimanche, calculé en UTC) et `preventifDeLaSemaine(ot, dimanche)` (OT d'origine `préventif`,
  ouvert, date prévue ≤ ce dimanche, retards compris).
- **`Parametres`** : écrans `#/parametres` et `#/controle` ; n'expose que `decrireSauvegarde(nom)`
  (lot 2 : type « Avant format 2 » pour `…_avant-format-v2`) et `numeroLigneFichier(probleme)`
  (utilitaires testés).
- **`Apropos`** : `CREDIT`, `afficher`.

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
lundi), premières lignes en septembre 2025. Le jeu par défaut contient notamment 31 équipements,
150 DI, 232 OT, 10 gammes, 56 relevés, 52 articles, 302 mouvements de stock et 36 achats, avec les
champs du format v2 renseignés (valeur de remplacement de chaque équipement, code symptôme sur 127
DI, deux OT préventifs avec anomalie et leur DI liée) et au moins deux équipements qui ont 5 OT
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
anomalie…), l'identifiant de la ligne qui le joue. Les rôles sont décrits dans la docstring de
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
vérifie le découpage (700 lignes au plus par fichier de `js/modules/`, ordre exact du §14.2).

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

Le lot 2 est réalisé (§14) ; le contrat du lot 3 est au §15. Restent, dans l'ordre prévu :
- **Lot 3** (contrat au §15) : indicateurs (E11, ECharts déjà présent dans `js/lib/`), planning (E6), étiquettes QR
  par lot, contrôles réglementaires (E10, RG9), écran des habilitations, rapport mensuel (réutilise
  `.sans-impression`). Nouveaux modules en préfixes de fichiers (`indicateurs-*.js`…), 700 lignes au
  plus par fichier, ajoutés à l'ordre du §14.2 **et** à `ORDRE_MODULES` de `tests/test_depot.py`.
  Compteurs de l'accueil (brief E1) restant à ajouter : contrôles réglementaires sous 30 jours,
  habilitations échues ou à moins de 60 jours ; `Accueil.calculerCompteurs()` est le point
  d'extension (il renvoie déjà `preventifsSemaine` et `articlesACommander`).
- **Lot 3 bis** : préventif **suggéré**. Le champ `ordres_travail.anomalie_constatee` et le lien
  `demandes.ot_origine_id` (DI signalée pendant un préventif) sont posés et remplis depuis le lot 2
  pour être exploités là (ex. raccourcir une périodicité quand les anomalies se répètent) ;
  l'encart des causes fréquentes pourra recevoir un indicateur de fiabilité statistique (D25).
- **Lot 4** : `js/modules/ia.js`, `js/modules/ia-prompts.js`, `js/modules/dictee.js` ; les champs
  `texte_long` des formulaires portent `data-dictee` pour recevoir un bouton micro ; `GUIDE.html`
  (déjà dans la liste blanche du serveur, §7), `FICHE_TECHNIQUE_CSV.md`, https local en option.
- **Lot « Import »** : assistant d'import (les `synonymes` du schéma servent à reconnaître les
  colonnes), lecture des fichiers `.xls` (SheetJS).
- Piste notée par Nicolas : stocker le prix unitaire dans `mouvements_stock` au moment de la sortie
  pour figer le coût des OT passés (changement de format, lève la limite de D24 ; à décider).
- Nouveau format : ajouter les champs en fin de table avec `depuisVersion: N`, porter
  `Schema.version` à N, ajouter `avant-format-vN` aux listes fermées de motifs de sauvegarde
  (`MOTIFS_SAUVEGARDE` de `serveur.py` et de `js/stockage-dossier.js`) : `mettreAJourVersionSchema`
  fera la sauvegarde puis le passage.

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
apropos.js  accueil.js  causes-frequentes.js
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
`css/**`, `js/**` ; **tout le reste répond 404** (dont `brief-gmao.md`, `README.md`, `docs/`,
`tests/`, `outils/`, `reference-design/`, `serveur.py`). L'option `--servir-tests` (passée par
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

Écrit avant le code du lot 3 ; il sera relu et aligné sur le code à la fin du lot (mentions « écart
retenu : … », comme au §14). Les définitions métier du CDC sont recopiées ici : ce contrat se suffit.

### 15.1 Socle
- **Format CSV inchangé** : `Schema.version` reste 2, aucun champ ajouté. Nouvelles clés de
  `parametres.csv` (lues par `Donnees.parametre(cle, defaut)`, absentes → défaut) :
  `seuil_remplacement_pct` (`50`), `adresse_qr` (`''` : première adresse réseau détectée),
  `rapports_mensuels` (`''` : noms des rapports figés, séparés par des virgules, du plus ancien au
  plus récent).
- **Documents** : l'extension `html` s'ajoute aux types acceptés (`TYPES_DOCUMENTS` de `serveur.py`,
  `text/html; charset=utf-8` ; `EXTENSIONS_DOCUMENTS` de `js/stockage-dossier.js`). Comme tout
  document, il est servi avec `Content-Security-Policy: sandbox` (aucun script ne s'y exécute).
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
  avec lui) :
  ```
  apropos.js  accueil.js  causes-frequentes.js
  parc-regles.js  parc-arbre.js  parc-formulaires.js  parc-etiquettes.js  parc-fiche.js
  demandes-regles.js  demandes-ecritures.js  demandes-signaler.js  demandes-liste.js  demandes-fiche.js
  ordres-regles.js  ordres-ecritures.js  ordres-liste.js  ordres-fiche.js  ordres-onglets.js  ordres-pieces.js  ordres-impression.js
  preventif-regles.js  preventif-ecritures.js  preventif-ecrans.js  preventif-calendrier.js
  magasin-regles.js  magasin-ecritures.js  magasin-articles.js  magasin-mouvements.js  magasin-achats.js
  equipe-regles.js  equipe-ecritures.js  equipe-ecrans.js
  controles-regles.js  controles-ecritures.js  controles-ecrans.js
  planning-regles.js  planning-ecritures.js  planning-ecrans.js
  indicateurs-regles.js  indicateurs-graphiques.js  indicateurs-ecrans.js
  rapport-contenu.js  rapport-ecrans.js
  parametres.js  parametres-codes.js  (puis js/app.js)
  ```
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
  Date de panne = `date_heure` de la DI dont `ot_id` est cet OT (ou `di_id` de l'OT), sinon
  `date_creation` de l'OT ; la panne compte dans la période qui contient cette date.
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
- **Disponibilité** = MTBF / (MTBF + MTTR) ; `null` si l'un des deux l'est.
- **Attente de pièces** (`attentePieces(otId)` → `{ heures, complet }`) : lecture de `journal.csv`
  (table `ordres_travail`, `id_ligne` = l'OT, triées par `date_heure` puis `id`). Historique complet
  ⇔ une entrée de création de l'OT existe (action commençant par « création de l'OT » ou
  « acceptation de DI- »). Attente = Σ des intervalles entre une action « statut X → En attente : m »
  où `m` commence par « pièce » (casse et accents ignorés) et l'action « statut En attente → Y »
  suivante (sans sortie : jusqu'à `date_fin`, sinon jusqu'à maintenant) ; plafonnée à `duree_arret_h`.
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
  période ; délai (h) = `date_debut` − (`date_heure` de la DI, sinon `date_creation`) ; par priorité :
  `{ mediane, partDansLeDelai, effectif }` (délai cible `delai_pN_h` ; P4 : médiane seule).
- **Coût** : `Ordres.cout(ot)` (RG7, prix actuel des pièces) des OT clôturés, rangé au mois de
  `date_fin` ; `coutParEquipement(periode)`, `coutsParMois(debutMois, nbMois)`.
- **Valeur du stock** = Σ `Donnees.stockArticle(id)` × `prix_unitaire` des articles actifs.
- Agrégats : `parEquipement(equipementId, periode)` → `{ tempsRequis, pannes, dureeArret, mtbf, mttr,
  disponibilite, attentePieces, cout }` (chacun un résultat) ; `global(periode, { criticite,
  atelier })` → mêmes clés sur les équipements dont le temps requis est connu (les autres listés dans
  `exclus`), plus `partPreventif`, `respectPreventif`, `otEnRetard`, `valeurStock`, `delais`.
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

### 15.5 Planning (`planning-*.js`, objet `Planning`)
- Règles : `Planning.lundiDe(dateIso)`, `Planning.joursDeLaSemaine(lundi)` (7 dates ISO, UTC) ;
  `Planning.ordresDeLaSemaine(lundi)` → OT ni clôturés ni annulés, avec `technicien_id` et
  `date_prevue` dans la semaine ; `Planning.chargeSemaine(technicienId, lundi)` = Σ `temps_prevu_h`
  de ces OT pour ce technicien (vide = 0) ; `Planning.semaine(lundi)` → `{ lundi, jours, lignes:
  [{ technicien, cases: { date: [ot] }, charge, capacite, surcharge }], aPlanifier: [ot] }` (lignes :
  techniciens actifs par nom ; `aPlanifier` : OT `Préparé` absents de la grille de cette semaine, triés
  par priorité puis date prévue) ; `surcharge` = charge > `capacite_h_semaine`.
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

### 15.7 Contrôles réglementaires (`controles-*.js`, objet `Controles`)
- Règles : `Controles.STATUTS` = `['en retard', 'observations à lever', 'à planifier', 'à jour']` ;
  `Controles.ajouterMois(dateIso, n)` (même jour, ramené au dernier jour du mois : 31/01 + 1 →
  28 ou 29/02) ; `Controles.prochaineDate(controle)` = `prochaine_date`, sinon `derniere_date` +
  `periodicite_mois`, sinon `''` ; `Controles.etat(controle, aujourdhui)` → `{ statut, secondaires,
  prochaine, joursRestants, raison }` : statut = le premier vrai parmi `en retard` (prochaine <
  aujourd'hui), `observations à lever` (`observations` non vide et `observations_levees` ≠ 1),
  `à planifier` (prochaine ≤ aujourd'hui + 30 j, ou prochaine inconnue : raison « date inconnue »),
  `à jour` ; `secondaires` = les autres états vrais. `Controles.sous30Jours(aujourdhui)` → contrôles
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
  type=réglementaire&titre=…` pré-rempli : `#/ot/nouveau` lit désormais `?type=` et `?titre=`).
  Carte « Contrôles réglementaires » sur la fiche équipement (technicien et responsable).

### 15.8 Équipe et habilitations (`equipe-*.js`, objet `Equipe`)
- Règles : `Equipe.etatHabilitation(hab, aujourdhui)` → `{ statut, joursRestants }`, statut ∈
  `pas encore valable` (obtention future), `échue` (échéance < aujourd'hui), `à renouveler`
  (échéance ≤ aujourd'hui + 60 j), `valide` (échéance plus lointaine, ou vide : « sans échéance ») ;
  `Equipe.habilitationsQuiComptent(technicienId)` → pour chaque intitulé (casse et espaces ignorés),
  la ligne à l'échéance la plus lointaine (vide = la plus lointaine) ; `Equipe.aRenouveler(aujourdhui)`
  → `[{ technicien, habilitation, etat }]` des techniciens actifs dont une habilitation qui compte est
  `échue` ou `à renouveler`.
- Écritures : `verifierTechnicien`, `creerTechnicien`, `modifierTechnicien` (désactivation par
  `actif` = 0 ; nom obligatoire, taux ≥ 0, capacité 0–80 h), `ajouterHabilitation(technicienId,
  valeurs)`, `modifierHabilitation(id, valeurs)` (correction), `renouvelerHabilitation(id, {
  date_obtention, date_echeance })` = **nouvelle ligne** de même intitulé (l'ancienne reste) ;
  échéance ≥ obtention.
- Écrans : `#/equipe` (`?filtre=a-renouveler`), `#/equipe/nouveau`, `#/equipe/<id>` (habilitations
  avec statut, historique). Pour le technicien : lecture, **sans `taux_horaire`** (absent du DOM).

### 15.9 Accueil (lot 3)
`Accueil.calculerCompteurs()` renvoie en plus `controlesSous30j` (`Controles.sous30Jours`) et
`habilitationsARenouveler` (`Equipe.aRenouveler`) ; cartes « Contrôles sous 30 j » →
`#/controles?filtre=30j`, « Habilitations à renouveler » → `#/equipe?filtre=a-renouveler`
(technicien et responsable). Pour le responsable, bandeau « Figer le rapport de <mois> ? » quand
`Rapport.moisAProposer(aujourdhui)` renvoie un mois (§15.10), boutons « Figer » et « Plus tard »
(masqué jusqu'à la prochaine ouverture : sessionStorage).

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

### 15.11 Paramètres (`parametres.js`, `parametres-codes.js`)
- Réglages ajoutés au formulaire : `tolerance_preventif_pct` (0–100), `seuil_remplacement_pct`
  (1–1000), `priorite_preventif` (P1–P4), `horizon_calendrier_semaines` (1–52),
  `heures_fonct_defaut` (0–24, gammes compteur seulement). Les deux clés du lot 2 deviennent donc
  modifiables à l'écran.
- Carte « Codes de défaillance » : liste par famille ; `Parametres.ajouterCode({ famille, libelle,
  code })` (code proposé = lettre de la famille S / C / R + numéro suivant sur 2 chiffres,
  modifiable ; code unique, libellé non vide et unique dans la famille) ;
  `Parametres.modifierLibelleCode(id, libelle)`. Ni désactivation ni suppression (la table n'a pas
  de champ `actif`).

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
(3 équipements dont un A, avec pannes, heures connues).

### 15.13 Tests du lot 3
Un fichier par sujet : `test_socle_lot3.py`, `test_regles_lot3.py` (règles pures, dont les
indicateurs de 3 équipements comparés à un calcul Python indépendant sur les CSV),
`test_equipe.py`, `test_controles.py`, `test_planning.py`, `test_etiquettes.py`,
`test_indicateurs.py`, `test_rapport.py`, `test_accueil_lot3.py`, `test_recette_lot3.py` (recette de
bout en bout en modes serveur et démo, profils, design 1440 et 375 px) ; `test_performance.py`
complété (CS49) ; `test_depot.py` (ordre §15.1, 700 lignes).
