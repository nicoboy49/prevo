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
css/modules/*.css          mise en page propre à chaque module (un fichier par module, chargé par index.html)
css/polices/               police Sora (OFL)
js/lib/                    bibliothèques tierces + LICENCES.txt (jamais modifiées)
js/schema.js               Schema    : description des 22 tables (champs, types, identifiants)
js/donnees.js              Donnees   : CSV, chargement, contrôle, mutation, journal, rafraîchissement
js/stockage-serveur.js     StockageServeur : adaptateur « serveur » (API HTTP)
js/stockage-dossier.js     StockageDossier : adaptateur « dossier » (File System Access)
js/stockage-demo.js        StockageDemo    : adaptateur « démo » (mémoire)
js/demo-donnees.js         DEMO_DONNEES : jeu de démo généré (chargé à la demande)
js/interface.js            UI        : helpers d'écran (html, tableaux, fenêtres, QR, photos…)
js/modules/*.js            un fichier par module métier (parc, demandes, ordres, accueil…)
js/app.js                  App       : démarrage, choix du mode, profils, navigation
donnees/                   les CSV réels (hors dépôt git) + documents/ + sauvegardes/
donnees/demo/              le jeu de démo en CSV (versionné)
outils/generer_demo.py     génère donnees/demo/*.csv et js/demo-donnees.js
tests/                     tests automatisés (unittest + Playwright)
```

**Ordre de chargement dans `index.html`** (scripts classiques, jamais `type="module"`) :
`js/lib/papaparse.min.js`, `js/lib/qrcode.js`, `js/lib/jsQR.js`, `js/lib/jszip.min.js`,
`js/schema.js`, `js/donnees.js`, `js/stockage-serveur.js`, `js/stockage-dossier.js`,
`js/stockage-demo.js`, `js/interface.js`, `js/modules/*.js`, `js/app.js` (en dernier).
`js/demo-donnees.js` n'est **pas** chargé au démarrage : `App` l'injecte (balise `<script>`
créée dynamiquement, compatible `file://`) quand on choisit la démo ou la copie du jeu de démo.
ECharts n'est chargé qu'à partir du lot 3.

**Un fichier = un objet global** (`const Schema = …`, `const Donnees = …`). Rien d'autre n'est
global. Chaque fichier commence par `'use strict';` et un commentaire qui dit son rôle.

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
  version: 1,
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
    // … 22 tables, champs exactement ceux du §6 du brief, dans le même ordre
  },
};
```
Types : `id`, `texte`, `texte_long`, `entier`, `decimal`, `date`, `date_heure`, `booleen`,
`choix` (avec `valeurs`), `ref` (avec `table`, et `champCible` si ce n'est pas la clé — ex. les
`*_code` des OT visent `codes_defaillance.code` filtré par `famille`), `document` (nom de
fichier dans `donnees/documents/`). Champs facultatifs : `libelle` (toujours renseigné, en
français), `obligatoire`, `defaut`, `protege`, `synonymes` (pour l'assistant d'import futur).

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
`tolerance_preventif_pct`, `rafraichissement_s` (20), `version_schema` (1).

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
Donnees.demarrerSurveillance() / Donnees.arreterSurveillance()   // §5.5
Donnees.csv.analyser(table, entree)  // → { lignes, colonnesInconnues, problemes, encodage }
Donnees.csv.serialiser(table, lignes, colonnesInconnues) // → Uint8Array
Donnees.csv.ecrireValeur(champ, v) / Donnees.csv.relireValeur(champ, s)   // §3.2
Donnees.evenements                   // EventTarget : 'changement' { detail: { tables: [...] , origine: 'local'|'distant' } }
Donnees.statistiques                 // { conflits, essais } — lu par les tests
```
Types de problèmes : `reference` (clé étrangère cassée), `valeur` (illisible), `excel`
(abîmée par Excel), `colonne`, `encodage`, `doublon` (identifiant en double), `identifiant`
(ligne sans identifiant), `incoherence` (ex. DI acceptée sans OT, voir D18).

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
await sauvegarder()                   → nom de la sauvegarde manuelle (AAAA-MM-JJ_HHMMSS)
await listerSauvegardes()             → [{ nom, tables: [...] }]  (plus récente d'abord)
await restaurer(nom, tables?)         → { restaurees: [...], copieSecurite: nom }
await info()                          → { adressesReseau: [...] } (serveur) ou {}
```
Version d'un fichier = empreinte SHA-256 du contenu, 16 premiers caractères hexadécimaux
(décision D7). Sauvegarde quotidienne : avant la **première écriture de la journée**, copie de
tous les CSV dans `sauvegardes/AAAA-MM-JJ/` (si ce dossier n'existe pas). Une restauration copie
d'abord l'état courant dans `sauvegardes/AAAA-MM-JJ_HHMMSS_avant-restauration/`. Le mode dossier
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
| `POST /api/sauvegarde` | `{"sauvegarde": "AAAA-MM-JJ_HHMMSS"}` |
| `GET /api/sauvegardes` | `{"sauvegardes": [{"nom", "tables": [...]}]}` |
| `POST /api/restauration` | corps `{"sauvegarde": "…", "tables": [...] (facultatif)}` → `{"restaurees", "copie_securite"}` |

Règles : noms de tables limités aux 22 du schéma (liste recopiée dans `serveur.py`, avec un
commentaire de renvoi vers `js/schema.js`, cohérence vérifiée par un test) ; nom de document
`^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$` sans `..` ; nom de sauvegarde
`^\d{4}-\d{2}-\d{2}(_\d{6}(_avant-restauration)?)?$` ; tout chemin résolu doit rester sous
`donnees/` (vérification sur le chemin brut **et** décodé, `\` compris) ; écriture atomique
(fichier temporaire dans le même dossier, `fsync`, `os.replace`) ; un verrou global sérialise
les écritures ; sauvegarde quotidienne faite par le serveur avant la première écriture du jour.
Fichiers statiques : le dossier de l'application, **sauf** `donnees/` et tout chemin dont un
segment commence par `.` ; `/` → `index.html`. Pas d'en-têtes CORS.
Le serveur parle HTTP/1.1 avec connexions persistantes (`protocol_version = 'HTTP/1.1'` : un
navigateur réutilise ses connexions au lieu d'en ouvrir une par requête), avec une file d'attente
d'écoute de 128 connexions (`request_queue_size = 128`) et un fil par connexion.
Lancement : `py serveur.py [--port 8080] [--donnees CHEMIN] [--sans-navigateur] [--hote NOM]` ; port suivant
si occupé (jusqu'à +20) ; affiche l'adresse locale et les adresses réseau ; ouvre le navigateur.
Adresses réseau : interface de sortie trouvée par un `connect()` UDP vers une adresse privée
(aucun paquet envoyé) + `gethostbyname_ex`, adresses de bouclage exclues.

## 8. Application (`js/app.js`, `index.html`)

**Démarrage** : si la page est en `http(s)` et que `GET /api/ping` répond (délai 2 s) → mode
serveur. Sinon écran de démarrage : « Choisir le dossier de données » (si
`showDirectoryPicker` existe), « Reprendre le dossier précédent » (si une poignée est mémorisée),
« Essayer avec les données de démo », zone de dépôt de CSV (démo à partir de fichiers déposés).
Base vide (aucun CSV) → choix « Créer une base vide » ou « Partir des données de démo ».
Navigateur sans File System Access → message « utilisez Chrome ou Edge » + démo.

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
Profils : l'accueil, les DI, le parc et À propos sont ouverts aux trois profils ; les OT
(`#/ot`, `#/ot/<id>`) au technicien et au responsable ; `#/ot/nouveau`, la création et la
modification d'équipement, `#/parametres` et `#/controle` au responsable seul.
Paramètres d'adresse lus :
- `#/di` : `?statut=` (ex. `Nouvelle`), `?portee=` (`mes` ou `toutes`), `?q=` (recherche), `?equipement=` ;
- `#/ot` : `?filtre=retard` (OT en retard) ou `?filtre=p1` (P1 ouverts), liens de l'accueil ; aussi
  `?etat=`, `?statut=`, `?priorite=`, `?technicien=`, `?type=`, `?recherche=`, `?equipement=` ;
- `#/di/nouvelle` : `?equipement=` ; `#/ot/nouveau` : `?equipement=`, `?urgence=1`.

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
4 entrées + « Plus »). Badge de signature en bas du menu : « Développé par Claude (Anthropic) à
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
sa mise en page propre va dans `css/modules/<module>.css` (déjà référencé par `index.html`), en
réutilisant les variables de la charte (jamais de couleur codée en dur).
Les champs `texte_long` des formulaires portent l'attribut `data-dictee` (crochet pour le bouton
micro du lot 4 ; en attendant, la dictée du clavier du téléphone fonctionne sans code).

## 10. Règles métier du lot 1

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
  technicien et une date prévue, et est **refusé si une pièce prévue manque en stock**
  (`Donnees.stockArticle` < quantité prévue cumulée) : message + bouton « Mettre en attente
  (motif : pièce) ».
- **RG4** clôture technique bloquée sans : `date_fin`, au moins un temps passé (`ot_temps`),
  `cause_code`, `remede_code`, `compte_rendu` d'au moins 10 caractères (et sur un correctif,
  « RAS » / « rien à signaler » refusé), `remise_service` = 1. Le message liste **tous** les
  manques. La procédure de consignation de l'équipement s'affiche sur l'OT avec le rappel :
  « Cocher une case ne consigne rien : appliquez la procédure. » Clôture administrative
  (responsable) : `date_cloture_admin`, OT en lecture seule.
- **RG7** coût = Σ (heures × `taux_horaire` du technicien) + Σ (sorties de stock imputées à
  l'OT − retours) × `prix_unitaire` + `cout_soustraitance`.
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

### API effective des modules du lot 1 (`js/modules/`)

Un module = un objet global ; ses écrans s'enregistrent dans `DOMContentLoaded` (§8). Les fonctions
d'écriture sont `async`, passent par `Donnees.modifier` et lèvent `Donnees.ErreurValidation` pour un refus.

- **`Parc`** : `cheminLocalisation(id)`, `libelleEquipement(id)`, `verifierEquipement`,
  `verifierLocalisation` (règles : repère unique parmi les équipements actifs, aucun équipement
  ancêtre de lui-même), `afficherListe`, `afficherFiche`, `afficherFormulaire`.
- **`Demandes`** : constantes `STATUTS`, `IMPACTS`, `MATRICE_PRIORITE` ; règles pures
  `prioriteCalculee(criticite, impact)`, `normaliserImpact`, `typePropose(priorite)`,
  `datePrevue(priorite, aujourdhuiIso)`, `libelleEquipement` ; écritures `creer(valeurs)`,
  `accepter(diId, options)`, `regrouper(diId, otId)`, `differer(diId, motif)`, `refuser(diId, motif)`.
- **`Ordres`** : constantes `STATUTS`, `TYPES`, `PRIORITES`, `RAPPEL_CONSIGNATION` ; règles pures
  `transitionsPossibles`, `verifierPassage`, `verifierCloture`, `cout`, `verifierHabilitation`,
  `estOuvert`, `enRetard`, `estVerrouille`, `estCorrectif`, `estRienASignaler`, `piecesManquantes(otId)`,
  `filtrer(ordres, filtres)`, `datePrevueParDefaut` ; écritures `creer(valeurs)`,
  `changerStatut(otId, statutAttendu, cible, complement)`, `changerPriorite(otId, nouvelle, motif)`,
  `creerOtLie(otId)` ; affichage et export `libelleEquipement`, `nomTechnicien`, `csvListe`,
  `bonDeTravailHtml(ot)`, `imprimerBon(otId)`.
- **`Accueil`** : `afficher`, `calculerCompteurs()` → `{ diATraiter, otEnRetard, p1Ouverts }`
  (trois listes de lignes), `otEnRetard(ot, aujourdhui)`, `p1Ouvert(ot)`.
- **`Parametres`** : écrans `#/parametres` et `#/controle` ; n'expose que `decrireSauvegarde(nom)`
  et `numeroLigneFichier(probleme)` (utilitaires testés).
- **`Apropos`** : `CREDIT`, `afficher`.

## 11. Données de démo

`outils/generer_demo.py` (graine fixe, date de référence fixe `DATE_REFERENCE`) écrit
`donnees/demo/*.csv` (22 fichiers, format §3.1) et `js/demo-donnees.js` :
```js
const DEMO_DONNEES = { dateReference: 'AAAA-MM-JJ', tables: { equipements: '<texte CSV>', … } };
```
`StockageDemo` (et la copie du jeu de démo vers un vrai dossier) décale toutes les dates du
nombre de **semaines entières** écoulées depuis `dateReference`, pour que l'historique de 6 mois
se termine toujours aujourd'hui (les identifiants gardent leur année d'origine).
Option `--volume EQUIPEMENTS,OT --sortie DOSSIER` : jeu de charge (test de performance CS20).

## 12. Tests

`py -m unittest discover -s tests -v` lance tout. Outils communs dans `tests/commun.py` :
serveur de test (copie du jeu de démo dans un dossier temporaire, `--sans-navigateur`, port
libre), serveur statique (pour le dossier simulé), lancement de Chromium headless, collecte des
erreurs console (**toute erreur JavaScript fait échouer le test**), dossier simulé (OPFS
substitué à `showDirectoryPicker`), profil préréglé (`prevo.profil` dans localStorage),
attente de `dataset.etat === 'pret'`. Les tests ne touchent jamais `donnees/` réel.

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

- Lot 2 : `js/modules/preventif.js`, `js/modules/magasin.js` ; sorties de pièces depuis l'OT
  (mouvement `sortie` imputé à l'OT, stock négatif refusé) ; réécriture de la colonne `stock`.
- Lot 3 : `js/modules/indicateurs.js` (ECharts), `planning.js`, `controles.js`, étiquettes QR.
- Compteurs de l'accueil (brief E1) : le lot 1 n'affiche que DI à traiter, OT en retard et P1
  ouverts. Les autres compteurs prévus par le brief viendront avec les lots suivants : préventifs
  de la semaine et articles à commander (lot 2), contrôles réglementaires sous 30 jours et
  habilitations échues ou à moins de 60 jours (lot 3). `Accueil.calculerCompteurs()` est le point
  d'extension.
- Lot 4 : `js/modules/ia.js`, `js/modules/ia-prompts.js`, `js/modules/dictee.js` ; les champs
  `texte_long` des formulaires portent `data-dictee` pour recevoir un bouton micro ; les
  `synonymes` du schéma servent à l'assistant d'import.
