# Fichiers d'essai de l'import (lot 5)

Écrits par `py outils/generer_fixtures_import.py` (docs/ARCHITECTURE.md §18.10, tâche T79). **Ne pas les modifier
à la main** : relancer le générateur, qui réécrit les mêmes octets (dates des archives fixées, aucun horodatage) ;
`tests/test_fixtures_import.py` vérifie la régénération à l'octet et la présence de chaque piège annoncé ici.
`.gitattributes` les protège (`tests/fixtures/import/** -text`). Aucune donnée personnelle réelle : noms de
personnes et d'entreprises inventés, adresses en `.example`, comme le jeu de démo.

## Conventions des attentes

- **Base de référence** : le jeu de démo du dépôt (`donnees/demo/`), tel quel. Chaque fichier est importé **seul**
  sur cette base, avec le type de données indiqué, la correspondance de colonnes attendue, la case « Compléter et
  mettre à jour les fiches existantes » **cochée** (défaut, D84 a) et aucune case « Importer quand même » cochée.
- **Ligne** : numéro de ligne du fichier tel que l'affiche un tableur (1 = première ligne du fichier, titre et
  en-tête compris ; une cellule entre guillemets sur plusieurs lignes compte pour une seule ligne).
- **Actions** (§18.5, §18.6) : `créer` ; `mettre à jour` (seules les colonnes importées **non vides** qui changent,
  avant → après) ; `identique` ; `refusée` (avec sa raison ; le texte exact du message est libre, la nature de la
  raison ne l'est pas) ; pour l'historique, `doublon sûr` (ignorée) et `doublon supposé` (montrée avec « Importer
  quand même », non importée par défaut).
- **Identifiants** : ceux que donne `Donnees.nouvelId` sur la démo (plus grand numéro existant + 1), attribués dans
  l'ordre du fichier, table par table.
- Valeurs converties par `Donnees.normaliser` (dates `AAAA-MM-JJ`, décimales à point, booléens `0`/`1`) ; les
  champs protégés (repère, n° de série, référence, réf. fabricant, téléphone) gardent leur texte exact.

## Vue d'ensemble

| Fichier | Format | Type | Données | Créer | Mettre à jour | Identique | Refusées | Autres |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| equipements.xlsx / .ods / .xls | classeur (3 formats) | `equipements` | 23 | 5 | 1 | 14 | 3 | — |
| articles.csv | CSV Windows-1252 « ; » | `articles` | 12 | 7 | 1 | 1 | 3 | — |
| fournisseurs.tsv | collage tabulé UTF-8 | `fournisseurs` | 6 | 3 | 1 | 1 | 1 | — |
| techniciens.tsv | collage tabulé UTF-8 | `techniciens` | 7 | 2 | 1 | 3 | 1 | — |
| habilitations.csv | CSV UTF-8 BOM « ; » | `habilitations` | 8 | 2 | 2 | 1 | 3 | — |
| codes.csv | CSV UTF-8 « ; », fins LF | `codes` | 43 | 4 | 0 | 36 | 3 | — |
| compteurs.csv | CSV Windows-1252 « ; » | `compteurs` | 7 | 3 | 1 | 1 | 2 | — |
| controles.csv | CSV UTF-8 BOM « ; » | `controles` | 6 | 2 | 1 | 1 | 2 | — |
| gammes.xlsx | classeur .xlsx | `gammes` | 9 | 6 | 0 | 0 | 3 | — |
| historique.csv | CSV UTF-8 « , » | `historique` | 18 | 13 | 0 | 0 | 2 | 1 doublon sûr, 2 doublon supposé |
| garanties.csv | CSV UTF-8 BOM « ; » | `garanties` | 10 | 3 | 1 | 1 | 5 | — |
| contrats.csv | CSV UTF-8 BOM « ; » | `contrats` | 10 | 2 | 1 | 1 | 6 | — |
| reserves.csv | CSV UTF-8 BOM « ; » | `reserves` | 15 | 3 | 1 | 1 | 10 | — |

## equipements.xlsx, equipements.ods, equipements.xls — liste du parc d'un atelier

- **Type de données** : `equipements` (tables écrites : `localisations`, `equipements`).
- **Formats** : `.xlsx` écrit en Python (sans SheetJS) ; `.ods` (mêmes données) ; `.xls` ancien format BIFF8
  écrit par SheetJS 0.20.3 dans Chromium (mêmes données). Deux feuilles : **« Parc »** (les données) puis
  « Notes » (deux lignes de texte, à ne pas importer : la feuille « Parc » est la première, proposée par défaut).
- **Ligne 1** : titre « Liste du parc — atelier » (une seule cellule, A1 ; dans le .xlsx, chaîne « en ligne » `inlineStr`).
  **Ligne 2** : l'en-tête (`Import.ligneEntete` doit rendre le rang 1, soit la 2ᵉ ligne). Données : lignes 3 à 25.
- **Colonnes, dans le désordre** (A à I) : « Désignation », « Code machine », « Fabricant », « Mise en service », « Emplacement », « N° de série », « Criticité », « Machine mère », « Commentaire ».

| Colonne | Champ attendu | Statut attendu |
| --- | --- | --- |
| Désignation | `designation` | sûre (libellé) |
| Code machine | `repere` (clé naturelle) | sûre (synonyme) |
| Fabricant | `marque` | sûre (synonyme) |
| Mise en service | `date_mes` | sûre (synonyme) |
| Emplacement | `chemin_localisation` (localisation par chemin) | sûre (synonyme de la localisation) |
| N° de série | `num_serie` | sûre (synonyme) |
| Criticité | `criticite` | sûre (libellé) |
| Machine mère | `parent` (équipement parent par repère) | sûre (synonyme) |
| Commentaire | — | **non utilisée** (colonne inconnue) |

**Pièges** :
- repère « 007 » (ligne 11) : texte à zéros en tête, à garder tel quel ; n° de série « 00481723 » (RA-01,
  ligne 6) et « 0042-117 » : texte ; n° de série « 1E5 » (ligne 4) : texte, jamais 100000 ;
- dates de mise en service en **numéros de série Excel (système 1900)** avec un style de date `dd/mm/yyyy`
  (.xlsx : `<c s="1"><v>44333</v>` pour le 2021-05-17 ; .xls : même nombre et même format ; .ods :
  `office:date-value`) → la lecture les rend en `AAAA-MM-JJ` ; une date écrite **en texte** « 15/03/2024 »
  (ligne 4), convertie par l'aperçu en 2024-03-15 ; une cellule de date vide (ligne 25) ;
- localisation **nouvelle** « Site des Trois Vallées > Atelier Usinage > Ligne de rectification » (lignes 11 et 12) : un seul niveau manque (la ligne) → une
  seule localisation créée (D88), réutilisée à la ligne suivante ; chemin écrit avec « / » (ligne 8) ;
- équipement parent **cité plus bas** : « 007 » est créé ligne 11 puis cité comme machine mère ligne
  12 ; « CP-01 » (base) cité ligne 4 ; parent inconnu « XX-99 » (ligne 17) ;
- un repère existant mis à jour (PO-02, ligne 8) et quatorze repères existants identiques (les machines de la
  démo que citent les autres fichiers d'essai, pour qu'ils s'enchaînent aussi sur une base vide) ;
- lignes en erreur : criticité « Z » (ligne 16), désignation vide (ligne 24), machine mère introuvable
  (ligne 17) ;
- .ods : cellules vides répétées au milieu des lignes (`table:number-columns-repeated`, par exemple les six cellules
  vides de la ligne 25 avant « Commentaire ») et en fin de ligne jusqu'à la 1 024ᵉ colonne ; lignes vides
  répétées jusqu'à la 1 048 576ᵉ (`table:number-rows-repeated`) : la lecture doit rendre 25 lignes sur 9
  colonnes, sans décaler les colonnes ni lire un million de lignes.

**Attendu** (base de démo, « Compléter et mettre à jour » coché) : 23 lignes de données : 5 créer, 1 mettre à jour, 14 identique, 3 refusée. Équipements créés dans l'ordre du
fichier ; références créées : localisation LOC-0008 « Ligne de rectification » (type `ligne`, parent « Atelier Usinage »).

| Ligne | Clé | Action attendue | Détail |
| --- | --- | --- | --- |
| 3 | CP-01 | identique | EQ-0001 : aucune colonne importée ne change |
| 4 | CP-01.PUR | créer | EQ-0032 ; machine mère CP-01 = EQ-0001 (base) ; mise en service écrite en texte « 15/03/2024 » → 2024-03-15 ; n° de série « 1E5 » gardé tel quel (champ protégé, jamais un nombre) |
| 5 | CP-02 | créer | EQ-0033 ; criticité « b » → B (correspondance tolérante, D86) ; mise en service 2023-11-06 (n° de série Excel) |
| 6 | RA-01 | identique | EQ-0003 : identique — le n° de série « 00481723 » doit être lu en texte (zéros en tête) |
| 7 | PO-01 | identique | EQ-0004 : aucune colonne importée ne change |
| 8 | PO-02 | mettre à jour | EQ-0005 : criticité B → A (seul changement) ; chemin écrit avec « / » au lieu de « > » (même localisation LOC-0004) |
| 9 | GF-01 | identique | EQ-0007 : aucune colonne importée ne change |
| 10 | VE-01 | identique | EQ-0008 : aucune colonne importée ne change |
| 11 | 007 | créer | EQ-0034 ; repère « 007 » gardé avec ses zéros ; localisation **créée** LOC-0008 « Ligne de rectification » (type ligne, parent LOC-0002 « Atelier Usinage ») |
| 12 | 007.TA | créer | EQ-0035 ; machine mère « 007 » = EQ-0034, créé plus haut dans le même fichier ; localisation LOC-0008 (déjà créée plus haut : pas de second exemplaire) |
| 13 | CU-01 | identique | EQ-0016 : aucune colonne importée ne change |
| 14 | PT-01 | identique | EQ-0018 : aucune colonne importée ne change |
| 15 | SC-01 | identique | EQ-0019 : aucune colonne importée ne change |
| 16 | SC-02 | refusée | criticité « Z » hors liste (valeurs permises : A, B, C) |
| 17 | PE-02 | refusée | machine mère « XX-99 » introuvable (ni dans la base ni plus haut dans le fichier ; un équipement parent n'est jamais créé, D88) |
| 18 | PR-01 | identique | EQ-0020 : aucune colonne importée ne change |
| 19 | CV-02 | identique | EQ-0023 : aucune colonne importée ne change |
| 20 | CV-03 | identique | EQ-0025 : aucune colonne importée ne change |
| 21 | EM-01 | identique | EQ-0026 : aucune colonne importée ne change |
| 22 | ET-01 | identique | EQ-0027 : aucune colonne importée ne change |
| 23 | CH-01 | identique | EQ-0030 : aucune colonne importée ne change |
| 24 | TR-01 | refusée | désignation vide (champ obligatoire) |
| 25 | MT-01 | créer | EQ-0036 ; sans localisation ni date ; criticité vide → B (défaut du schéma), statut « en service », actif 1 |

## articles.csv — export d'une autre GMAO

- **Type de données** : `articles`.
- **Format** : CSV **Windows-1252** (pas UTF-8 : la lecture doit retomber sur Windows-1252), séparateur « ; », fins de ligne CRLF, décimales à virgule.
- **En-tête** : ligne 1 ; colonnes « Code article », « Libellé », « Famille », « Marque », « Réf. fabricant », « Casier », « Unité », « Qté stock », « Stock mini », « Prix achat », « Fournisseur », « Délai livraison ».

| Colonne | Champ attendu | Statut attendu |
| --- | --- | --- |
| Code article | `reference` (clé naturelle) | sûre (synonyme) |
| Libellé | `designation` | sûre (synonyme) |
| Famille | — | **non utilisée** (colonne inconnue) |
| Marque | `fabricant` | sûre (synonyme) |
| Réf. fabricant | `ref_fabricant` | sûre (synonyme) |
| Casier | `emplacement` | sûre (synonyme) |
| Unité | `unite` | sûre (libellé) |
| Qté stock | `stock_initial` (→ mouvement « inventaire ») | sûre (synonyme du stock) |
| Stock mini | `stock_securite` | sûre (synonyme) |
| Prix achat | `prix_unitaire` | sûre (synonyme) |
| Fournisseur | `fournisseur` (par nom, créé s'il manque) | sûre (synonyme) |
| Délai livraison | `delai_jours` | sûre (synonyme) |

**Pièges** :
- caractères propres à Windows-1252 : « Œ » (0x8C, ligne 6), apostrophe typographique « ’ » (0x92) et « Ø » (ligne 5), espace insécable 0xA0 dans « 1 250,00 » (ligne 11) ; lus faux en ISO-8859-1 ou en UTF-8 ;
- prix et stocks à virgule (« 5,15 », « 120,5 ») ; « 0 » en stock (inventaire de 0) et stock vide (aucun mouvement) ;
- fournisseur inconnu « Boulonnerie des Cimes » cité deux fois : créé une seule fois (D88) ;
- référence « ROU-101 » en double dans le fichier ; référence existante mise à jour (ROU-001) et identique (FIL-001) ;
- désignation vide ; délai « 2 semaines » illisible.

**Attendu** (base de démo) : 12 lignes de données : 7 créer, 1 mettre à jour, 1 identique, 3 refusée. Références créées : fournisseur FOU-0006 « Boulonnerie des Cimes » ; 6 mouvements « inventaire » (MVT-000303 à MVT-000308).

| Ligne | Clé | Action attendue | Détail |
| --- | --- | --- | --- |
| 2 | ROU-001 | mettre à jour | ART-0001 : prix unitaire 4.8 → 5.15 (seul changement) ; qté stock vide → aucun mouvement (une cellule vide n'efface rien) |
| 3 | FIL-001 | identique | ART-0020 : aucune colonne importée ne change ; qté stock vide → aucun mouvement |
| 4 | ROU-101 | créer | ART-0053 ; stock initial « 6 » → MVT-000303 « inventaire » de 6 (motif « import ») ; prix 18.40 |
| 5 | JNT-201 | créer | ART-0054 ; stock initial « 25 » → MVT-000304 « inventaire » de 25 (motif « import ») ; réf. fabricant « 004512 » gardée avec ses zéros ; apostrophe typographique et « Ø » (Windows-1252) |
| 6 | FIX-010 | créer | ART-0055 ; stock initial « 4 » → MVT-000305 « inventaire » de 4 (motif « import ») ; fournisseur « Boulonnerie des Cimes » inconnu → **créé** FOU-0006 (D88) |
| 7 | ELE-150 | créer | ART-0056 ; stock initial « 120,5 » → MVT-000306 « inventaire » de 120.5 (motif « import ») ; virgule dans la désignation |
| 8 | ROU-101 | refusée | doublon dans le fichier (même référence que la ligne 4) |
| 9 | LUB-010 | créer | ART-0057 ; stock initial « 0 » → MVT-000307 « inventaire » de 0 (motif « import ») ; « 0 » n'est pas vide : inventaire de 0 |
| 10 | FIX-011 | créer | ART-0058 ; qté stock vide → aucun mouvement ; fournisseur FOU-0006 (créé plus haut : une seule création) |
| 11 | VAR-001 | créer | ART-0059 ; stock initial « 1 » → MVT-000308 « inventaire » de 1 (motif « import ») ; prix « 1 250,00 » avec espace insécable (U+00A0) → 1250.00 |
| 12 | OUT-020 | refusée | désignation vide (champ obligatoire) |
| 13 | PNE-020 | refusée | délai « 2 semaines » illisible (nombre entier attendu) |

## fournisseurs.tsv — collage depuis Excel

- **Type de données** : `fournisseurs`.
- **Format** : texte tabulé (collage : tabulation entre les cellules, CRLF à chaque fin de ligne, y compris la dernière), UTF-8 sans BOM. Peut aussi être collé dans la zone de collage.
- **En-tête** : ligne 1 ; colonnes « Raison sociale », « Interlocuteur », « Tél », « Courriel ».

| Colonne | Champ attendu | Statut attendu |
| --- | --- | --- |
| Raison sociale | `nom` (clé naturelle) | sûre (synonyme) |
| Interlocuteur | `contact` | sûre (synonyme) |
| Tél | `telephone` | sûre (synonyme) |
| Courriel | `email` | sûre (synonyme) |

**Pièges** :
- téléphones à zéro en tête et avec espaces (champ protégé, texte exact) ;
- ligne aux cellules finales vides (tabulations en fin de ligne) ;
- raison sociale vide.

**Attendu** (base de démo) : 6 lignes de données : 3 créer, 1 mettre à jour, 1 identique, 1 refusée.

| Ligne | Clé | Action attendue | Détail |
| --- | --- | --- | --- |
| 2 | Fluidalpes Services | mettre à jour | FOU-0002 : e-mail ventes@fluidalpes-demo.example → commandes@fluidalpes-demo.example |
| 3 | Lubrifix Industrie | identique | FOU-0004 : aucune colonne ne change (téléphone « 0465710004 » lu en texte) |
| 4 | Roulements du Vercors | créer | FOU-0006 ; téléphone « 0465710023 » gardé avec son zéro |
| 5 | Pneumatique Savoie Services | créer | FOU-0007 ; téléphone « 04 65 71 00 30 » gardé tel quel (champ protégé) |
| 6 | Soudure et Métallerie du Guiers | créer | FOU-0008 ; cellules vides en fin de ligne (tabulations finales) |
| 7 |  | refusée | raison sociale vide (nom = clé naturelle du fournisseur) |

## techniciens.tsv — collage depuis Excel

- **Type de données** : `techniciens`.
- **Format** : texte tabulé (collage), UTF-8 sans BOM, CRLF.
- **En-tête** : ligne 1 ; colonnes « Nom », « Prénom », « Fonction », « Coût horaire », « h/semaine ».

| Colonne | Champ attendu | Statut attendu |
| --- | --- | --- |
| Nom | `nom` (clé naturelle avec le prénom) | sûre (libellé) |
| Prénom | `prenom` | sûre (libellé) |
| Fonction | `metier` | sûre (synonyme) |
| Coût horaire | `taux_horaire` | sûre (synonyme) |
| h/semaine | `capacite_h_semaine` | sûre (synonyme) |

**Pièges** :
- les quatre techniciens de la démo (un mis à jour, trois identiques) : ils existent ainsi aussi sur une base vide ;
- taux à virgule « 41,50 » ;
- nom vide.

**Attendu** (base de démo) : 7 lignes de données : 2 créer, 1 mettre à jour, 3 identique, 1 refusée.

| Ligne | Clé | Action attendue | Détail |
| --- | --- | --- | --- |
| 2 | Moreau Julien | mettre à jour | TEC-0001 : taux horaire 44 → 46 |
| 3 | Benali Karim | identique | TEC-0002 : aucune colonne ne change |
| 4 | Lambert Sophie | identique | TEC-0003 : aucune colonne ne change |
| 5 | Garnier Thomas | identique | TEC-0004 : aucune colonne ne change |
| 6 | Chabert Inès | créer | TEC-0005 ; taux « 41,50 » → 41.50 |
| 7 | Vidal Mathis | créer | TEC-0006 |
| 8 | Lucas | refusée | nom vide (champ obligatoire) |

## habilitations.csv

- **Type de données** : `habilitations`.
- **Format** : CSV UTF-8 **avec BOM**, séparateur « ; », CRLF, dates JJ/MM/AAAA.
- **En-tête** : ligne 1 ; colonnes « Technicien », « Habilitation », « Obtenue le », « Valable jusqu'au ».

| Colonne | Champ attendu | Statut attendu |
| --- | --- | --- |
| Technicien | `technicien` (par « Prénom Nom » ou « Nom Prénom », doit exister) | sûre (libellé) |
| Habilitation | `intitule` | sûre (synonyme) |
| Obtenue le | `date_obtention` | sûre (synonyme) |
| Valable jusqu'au | `date_echeance` | sûre (synonyme) |

**Pièges** :
- technicien écrit « Prénom Nom » et « Nom Prénom » (ligne 4) ;
- technicien inconnu de la base (jamais créé : la ligne est refusée) ;
- date impossible « 31/02/2026 ».

**Attendu** (base de démo) : 8 lignes de données : 2 créer, 2 mettre à jour, 1 identique, 3 refusée.

| Ligne | Clé | Action attendue | Détail |
| --- | --- | --- | --- |
| 2 | Julien Moreau / BR | identique | HAB-0001 (TEC-0001) : aucune date ne change |
| 3 | Karim Benali / CACES R489 | mettre à jour | HAB-0004 (TEC-0002) : date d'obtention 2021-12-02 → 2026-10-15 ; échéance 2026-12-02 → 2031-10-15 (renouvellement) |
| 4 | Garnier Thomas / BR | mettre à jour | HAB-0009 (TEC-0004, écrit « Nom Prénom ») : obtention 2023-06-01 → 2026-06-01 ; échéance 2026-05-31 → 2029-06-01 |
| 5 | Sophie Lambert / B2V | créer | HAB-0012 (TEC-0003) |
| 6 | Thomas Garnier / H1V | créer | HAB-0013 (TEC-0004) |
| 7 | Inès Chabert / H0V | refusée | technicien « Inès Chabert » introuvable (elle n'existe qu'après l'import de techniciens.tsv) |
| 8 | Paul Dumas / BR | refusée | technicien « Paul Dumas » introuvable (un technicien n'est jamais créé par cet import) |
| 9 | Julien Moreau / ATEX niveau 1 | refusée | date « 31/02/2026 » illisible (jour inexistant) |

## codes.csv — codes de défaillance

- **Type de données** : `codes`.
- **Format** : CSV UTF-8 **sans BOM**, séparateur « ; », fins de ligne **LF** (pas CRLF).
- **En-tête** : ligne 1 ; colonnes « Famille », « Code », « Libellé ».

| Colonne | Champ attendu | Statut attendu |
| --- | --- | --- |
| Famille | `famille` (correspondance tolérante) | sûre (libellé) |
| Code | `code` | sûre (libellé) |
| Libellé | `libelle` | sûre (libellé) |

**Pièges** :
- familles écrites librement : « Symptome », « CAUSE », « Remede », « symptôme », « Cause », « remède », « REMÈDE » → symptôme, cause, remède ; famille hors liste « Défaut » ;
- les 36 codes de la démo (identiques ; ils existent ainsi aussi sur une base vide) et quatre nouveaux ;
- code vide ; même famille + code deux fois (C15).

**Attendu** (base de démo) : 43 lignes de données : 4 créer, 36 identique, 3 refusée.

| Ligne | Clé | Action attendue | Détail |
| --- | --- | --- | --- |
| 2 à 12 | 11 fiches de la démo | identique | aucune colonne importée ne change (CD-0001 à CD-0011) |
| 13 | symptôme S11 | créer | CD-0037 ; famille « symptôme » → symptôme |
| 14 à 28 | 15 fiches de la démo | identique | aucune colonne importée ne change (CD-0012 à CD-0026) |
| 29 | cause C15 | créer | CD-0038 ; famille « Cause » → cause |
| 30 à 39 | 10 fiches de la démo | identique | aucune colonne importée ne change (CD-0027 à CD-0036) |
| 40 | remède R11 | créer | CD-0039 ; famille « remède » → remède |
| 41 | remède R12 | créer | CD-0040 ; famille « REMÈDE » → remède |
| 42 | D01 | refusée | famille « Défaut » hors liste (valeurs permises : symptôme, cause, remède) |
| 43 |  | refusée | code vide (champ obligatoire) |
| 44 | cause C15 | refusée | doublon dans le fichier (même famille et même code que la ligne 29) |

## compteurs.csv

- **Type de données** : `compteurs`.
- **Format** : CSV **Windows-1252**, séparateur « ; », CRLF.
- **En-tête** : ligne 1 ; colonnes « Repère », « Libellé », « Unité ».

| Colonne | Champ attendu | Statut attendu |
| --- | --- | --- |
| Repère | `equipement` (par repère, doit exister) | sûre (synonyme attendu de l'équipement) |
| Libellé | `libelle` | sûre (libellé) |
| Unité | `unite` | sûre (libellé) |

**Pièges** :
- équipement par repère ; repère « 007 » inconnu de la démo ; repère vide ;
- compteur existant identique et compteur existant dont l'unité change.

**Attendu** (base de démo) : 7 lignes de données : 3 créer, 1 mettre à jour, 1 identique, 2 refusée.

| Ligne | Clé | Action attendue | Détail |
| --- | --- | --- | --- |
| 2 | CP-01 | identique | CPT-0001 : aucune colonne ne change |
| 3 | CH-01 | mettre à jour | CPT-0003 : unité h → heures |
| 4 | PO-02 | créer | CPT-0005 (équipement EQ-0005) |
| 5 | CU-01 | créer | CPT-0006 (équipement EQ-0016) |
| 6 | GF-01 | créer | CPT-0007 (équipement EQ-0007) |
| 7 | 007 | refusée | équipement « 007 » introuvable (il n'existe qu'après l'import de la liste du parc) |
| 8 |  | refusée | équipement vide (repère obligatoire : clé naturelle équipement + libellé) |

## controles.csv — contrôles réglementaires

- **Type de données** : `controles`.
- **Format** : CSV UTF-8 **avec BOM**, séparateur « ; », CRLF, dates JJ/MM/AAAA.
- **En-tête** : ligne 1 ; colonnes « Équipement », « Nature du contrôle », « Texte de référence », « Périodicité (mois) », « Organisme de contrôle », « Date du dernier contrôle », « Date du prochain contrôle », « Observations ».

| Colonne | Champ attendu | Statut attendu |
| --- | --- | --- |
| Équipement | `equipement` (par repère, doit exister) | sûre (synonyme attendu) |
| Nature du contrôle | `nature` (clé naturelle avec l'équipement) | sûre (libellé) |
| Texte de référence | `texte_reference` | sûre (libellé) |
| Périodicité (mois) | `periodicite_mois` | sûre (libellé) |
| Organisme de contrôle | `organisme` | sûre (libellé) |
| Date du dernier contrôle | `derniere_date` | sûre (libellé) |
| Date du prochain contrôle | `prochaine_date` | sûre (libellé) |
| Observations | `observations` → réserves des contrôles (une par ligne non vide, D183 ; colonne `observations` du contrôle jamais écrite) | sûre (nom du champ) |

**Pièges** :
- « ; » dans un champ entre guillemets (ligne 4) ;
- observations sur deux lignes (ligne 3, champ entre guillemets) : deux réserves (2.2, T489) ;
- périodicité « 12 mois » illisible sur une fiche existante (refusée, la fiche ne change pas) ;
- équipement inconnu « XX-99 ».

**Attendu** (base de démo) : 6 lignes de données : 2 créer, 1 mettre à jour, 1 identique, 2 refusée.

| Ligne | Clé | Action attendue | Détail |
| --- | --- | --- | --- |
| 2 | PT-01 | identique | CTR-0001 : aucune colonne ne change |
| 3 | CH-01 | mettre à jour | CTR-0002 : dernier contrôle 2026-03-18 → 2026-09-18 ; prochain 2026-09-18 → 2027-03-18 ; observations sur deux lignes (champ entre guillemets) → deux réserves RES-00004 et RES-00005 créées, datées du 2026-09-18 (D183) ; la colonne observations du contrôle n'est pas écrite |
| 4 | PR-01 | créer | CTR-0008 (équipement EQ-0020) ; « ; » dans le texte de référence (champ entre guillemets) ; réserve RES-00006 « Carter de protection arrière à refixer. » créée, datée du 2026-07-05 |
| 5 | CU-01 | créer | CTR-0009 (équipement EQ-0016) |
| 6 | XX-99 | refusée | équipement « XX-99 » introuvable |
| 7 | GF-01 | refusée | périodicité « 12 mois » illisible (nombre entier attendu) : la fiche CTR-0005 n'est pas touchée |

## gammes.xlsx — gammes de préventif, une ligne par opération

- **Type de données** : `gammes`.
- **Format** : .xlsx écrit en Python (sans SheetJS), une feuille « Gammes » ; périodicités et temps en nombres, dernière réalisation en numéro de série Excel avec style de date.
- **En-tête** : ligne 1 ; colonnes « Équipement », « Libellé », « Périodicité (jours) », « Temps prévu (heures) », « Dernière réalisation », « Opération », « Valeur attendue ».

| Colonne | Champ attendu | Statut attendu |
| --- | --- | --- |
| Équipement | `equipement` (par repère, doit exister) | sûre (synonyme attendu) |
| Libellé | `libelle` (clé naturelle avec l'équipement) | sûre (libellé) |
| Périodicité (jours) | `periodicite_jours` | sûre (libellé) |
| Temps prévu (heures) | `temps_prevu_h` | sûre (libellé) |
| Dernière réalisation | `derniere_realisation` | sûre (libellé) |
| Opération | `operations` (une ligne par opération) | sûre (libellé) |
| Valeur attendue | `valeur_attendue` de l'opération | sûre (libellé) |

**Pièges** :
- une ligne par opération : la même gamme (équipement + libellé) répétée sur trois lignes n'est **pas** un doublon ; l'ordre des opérations est celui du fichier (1, 2, 3) ;
- nombre décimal 0.75 ; « ≤ » dans une valeur attendue ;
- gamme d'un équipement inconnu (« 007 ») sur deux lignes ; libellé de gamme vide.

**Attendu** (base de démo) : 9 lignes de données : 6 créer, 3 refusée.

| Ligne | Clé | Action attendue | Détail |
| --- | --- | --- | --- |
| 2 | SC-01 / Graissage et contrôle mensuel de la scie SC-01 | créer | **GAM-0013 créée** (équipement EQ-0019, déclencheur « date » par défaut, périodicité 30 j, temps prévu 1 h, dernière réalisation 2026-10-01) ; GOP-000067, opération 1 (ordre 1) |
| 3 | SC-01 / Graissage et contrôle mensuel de la scie SC-01 | créer | même gamme GAM-0013 répétée (pas un doublon) ; GOP-000068, opération 2 (ordre 2) |
| 4 | SC-01 / Graissage et contrôle mensuel de la scie SC-01 | créer | même gamme GAM-0013 répétée (pas un doublon) ; GOP-000069, opération 3 (ordre 3) |
| 5 | CV-03 / Contrôle trimestriel du convoyeur de sortie CV-03 | créer | **GAM-0014 créée** (équipement EQ-0025, déclencheur « date » par défaut, périodicité 90 j, temps prévu 0.75 h, dernière réalisation 2026-09-15) ; GOP-000070, opération 1 (ordre 1) |
| 6 | CV-03 / Contrôle trimestriel du convoyeur de sortie CV-03 | créer | même gamme GAM-0014 répétée (pas un doublon) ; GOP-000071, opération 2 (ordre 2) |
| 7 | CV-03 / Contrôle trimestriel du convoyeur de sortie CV-03 | créer | même gamme GAM-0014 répétée (pas un doublon) ; GOP-000072, opération 3 (ordre 3) |
| 8 | 007 / Contrôle annuel de la rectifieuse 007 | refusée | équipement « 007 » introuvable (toutes les lignes de cette gamme) |
| 9 | 007 / Contrôle annuel de la rectifieuse 007 | refusée | équipement « 007 » introuvable (toutes les lignes de cette gamme) |
| 10 | PO-01 / (vide) | refusée | libellé de gamme vide (clé naturelle équipement + libellé) |

## historique.csv — historique d'une autre GMAO (D92)

- **Type de données** : `historique` (tables écrites : `ordres_travail`, `ot_temps`).
- **Format** : CSV **UTF-8 sans BOM**, séparateur « , », fins de ligne CRLF, décimales à point (et une à virgule,
  « 1,75 », entre guillemets), champs entre guillemets quand ils contiennent « , », « " » ou un saut de ligne
  (ligne 7 : compte rendu sur deux lignes avec des guillemets doublés). Dates **JJ/MM/AAAA HH:MM**.
- **En-tête** : ligne 1 ; 18 lignes de données (lignes 2 à 19).

| Colonne | Champ attendu |
| --- | --- |
| N° OT | `ancien_numero` (écrit en tête du compte rendu : `Ancien n° : <numéro>`, ajustement 1) |
| Machine | `equipement` (par repère, obligatoire) |
| Date demande | `date_creation` |
| Début | `date_debut` |
| Fin | `date_fin` |
| Type | `type` (libellés libres, correspondance tolérante) |
| Libellé | `titre` |
| Compte rendu | `compte_rendu` |
| Durée arrêt (h) | `duree_arret_h` |
| Arrêt | `arret_production` (oui / non) |
| Symptôme, Cause, Remède | `symptome_code`, `cause_code`, `remede_code` (par code ou par libellé, dans la bonne famille) |
| Intervenant | `technicien` (par nom) |
| Temps (h) | `temps_passe_h` (→ une ligne `ot_temps`) |

Aucune colonne « Priorité » : chaque OT créé reçoit **P3**, signalée. Chaque OT créé est « Clôturé
administrativement », `date_cloture_tech` = `date_cloture_admin` = date de fin, `remise_service` 1 ; son compte
rendu vaut `Ancien n° : <N° OT>` + saut de ligne + le compte rendu du fichier. Aucun OT existant n'est modifié.

**Pièges** : libellés de type libres (« Dépannage », « Curatif », « Préventif »…) et type absent ; codes par code
(« R01 »), par libellé (« Fuite »), par libellé en minuscules (« défaut qualité ») ; un code d'une autre famille
(« C04 » en symptôme) et un libellé inconnu (« Usure générale ») ; intervenant inconnu (« Pierre Martel ») et
écrit « NOM Prénom » ; durées d'arrêt vides (avec « Arrêt » à non, et une avec « Arrêt » à oui, ligne 7) ;
colonne « Arrêt » vide avec une durée (ligne 16) ; dates de 2024 et de 2025 (numéros `OT-2024-…` et
`OT-2025-…`) ; **doublon supposé** dans le fichier (ligne 12 : même machine, même date, même libellé que la
ligne 4, numéro différent) et contre un OT existant (ligne 18, OT-2025-0002) ; **doublon sûr** : même
N° OT deux fois dans le fichier (lignes 6 et 19) ; ligne sans date de demande ni de début (refusée,
ligne 13) ; date de demande vide mais début renseigné (ligne 14) ; machine inconnue (ligne 15).

**Attendu** (base de démo, aucune case « Importer quand même » cochée) : 18 lignes de données : 13 créer, 2 refusée, 1 doublon sûr, 2 doublon supposé.
13 OT créés (OT-2024-0001 à OT-2025-0067, numéros de l'année de création, dans l'ordre du fichier) et
12 lignes `ot_temps`. Les identifiants supposent les doublons supposés non importés.
**Réimport** du même fichier après cet import : 0 OT créé (les 13 lignes créées et la ligne 19 →
doublons sûrs par l'ancien numéro ; ligne 12 → doublon supposé de l'OT créé pour la ligne 4 ;
ligne 18 → doublon supposé d'OT-2025-0002 ; lignes 13 et 15 → refusées).

Équivalences de type attendues : « Dépannage », « Curatif » → correctif immédiat ; « Préventif » → préventif
systématique (origine « préventif », sans gamme) ; « Correctif différé », « Amélioration », « Réglementaire » →
même valeur ; absent → correctif différé (signalé). Origine « manuel » pour les autres types.

| Ligne | N° OT | Machine | Action | OT attendu | Type (origine) | Création → début → fin | Arrêt / durée (h) | Codes S / C / R | Technicien | Ligne ot_temps | Remarques |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 3987 | PO-01 | créer | OT-2024-0001 | correctif immédiat (manuel) | 2024-11-18 15:45 → 16:00 → 17:30 | 1 / 1.5 | S06 / C09 / R07 | TEC-0004 | OTT-000279 : 1.5 h (TEC-0004, 2024-11-18) | type « Dépannage » → « correctif immédiat » (équivalence affichée) ; intervenant écrit « NOM Prénom » |
| 3 | 3990 | SC-01 | créer | OT-2024-0002 | préventif systématique (préventif) | 2024-12-09 08:00 → 08:30 → 09:30 | 0 / vide | — / — / — | TEC-0002 | OTT-000280 : 1 h (TEC-0002, 2024-12-09) | type « Préventif » → « préventif systématique » (équivalence affichée) |
| 4 | 4512 | CP-01 | créer | OT-2025-0057 | correctif immédiat (manuel) | 2025-01-14 07:40 → 08:05 → 10:30 | 1 / 2.5 | S01 / C01 / R01 | TEC-0002 | OTT-000281 : 2.5 h (TEC-0002, 2025-01-14) | type « Dépannage » → « correctif immédiat » (équivalence affichée) |
| 5 | 4513 | PO-02 | créer | OT-2025-0058 | correctif immédiat (manuel) | 2025-02-03 10:15 → 10:40 → 12:10 | 1 / 1.5 | S02 / C02 / R01 | TEC-0002 | OTT-000282 : 1.75 h (TEC-0002, 2025-02-03) | type « Curatif » → « correctif immédiat » (équivalence affichée) |
| 6 | 4514 | CV-02 | créer | OT-2025-0059 | correctif immédiat (manuel) | 2025-02-11 06:50 → 07:05 → 07:50 | 1 / 0.75 | S05 / C04 / R03 | TEC-0001 | OTT-000283 : 0.75 h (TEC-0001, 2025-02-11) | type « Dépannage » → « correctif immédiat » (équivalence affichée) |
| 7 | 4515 | PR-01 | créer | OT-2025-0060 | correctif immédiat (manuel) | 2025-02-24 13:20 → 13:30 → 16:00 | 1 / vide | S01 / C10 / R01 | TEC-0004 | OTT-000284 : 2.5 h (TEC-0004, 2025-02-24) | type « Dépannage » → « correctif immédiat » (équivalence affichée) ; arrêt sans durée : durée d'arrêt **vide** (jamais 0), panne exclue du MTTR et de la disponibilité (ajustement 3) |
| 8 | 4516 | GF-01 | créer | OT-2025-0061 | préventif systématique (préventif) | 2025-03-10 09:00 → 09:15 → 12:15 | 0 / vide | — / — / — | TEC-0001 | OTT-000285 : 3 h (TEC-0001, 2025-03-10) | type « Préventif » → « préventif systématique » (équivalence affichée) |
| 9 | 4517 | CU-01 | créer | OT-2025-0062 | correctif différé (manuel) | 2025-03-19 14:10 → 2025-03-20 08:00 → 11:30 | 1 / 1.5 | S05 / C06 / R04 | TEC-0003 | OTT-000286 : 3.5 h (TEC-0003, 2025-03-20) | — |
| 10 | 4518 | EM-01 | créer | OT-2025-0063 | amélioration (manuel) | 2025-04-02 10:00 → 2025-04-07 13:00 → 17:00 | 0 / vide | — / — / R09 | TEC-0003 | OTT-000287 : 4 h (TEC-0003, 2025-04-07) | — |
| 11 | 4519 | PT-01 | créer | OT-2025-0064 | réglementaire (manuel) | 2025-04-15 08:00 → 2025-04-16 08:00 → 10:00 | 0 / vide | — / — / — | vide | aucune (temps vide) | intervenant « Pierre Martel » introuvable → technicien vide (signalé) |
| 12 | 4520 | CP-01 | doublon supposé | — | — | — | — | — | — | — | même machine, même date de création à la minute et même titre que la ligne 4 (n° 4512), numéro différent : montrée avec « Importer quand même » (non cochée) |
| 13 | 4521 | CV-03 | refusée | — | — | — | — | — | — | — | ni date de demande ni date de début (la date de fin seule ne suffit pas) : ligne refusée |
| 14 | 4522 | ET-01 | créer | OT-2025-0065 | correctif immédiat (manuel) | 2025-05-12 09:30 → 09:30 → 10:15 | 1 / 0.5 | S07 / C11 / R02 | TEC-0004 | OTT-000288 : 0.75 h (TEC-0004, 2025-05-12) | type « Dépannage » → « correctif immédiat » (équivalence affichée) ; date de demande absente → date de création = date de début ; symptôme « défaut qualité » → S07 (libellé « Défaut qualité », casse ignorée) |
| 15 | 4523 | XX-99 | refusée | — | — | — | — | — | — | — | équipement « XX-99 » introuvable (obligatoire) |
| 16 | 4524 | CH-01 | créer | OT-2025-0066 | correctif immédiat (manuel) | 2025-05-20 14:00 → 14:20 → 16:20 | 1 / 2 | vide / vide / R06 | TEC-0002 | OTT-000289 : 2 h (TEC-0002, 2025-05-20) | type « Dépannage » → « correctif immédiat » (équivalence affichée) ; symptôme « C04 » introuvable dans la famille symptôme → vide (signalé, aucun code créé) ; cause « Usure générale » introuvable dans la famille cause → vide (signalé, aucun code créé) ; colonne Arrêt vide mais durée > 0 → arrêt de production 1 |
| 17 | 4525 | VE-01 | créer | OT-2025-0067 | correctif différé (manuel) | 2025-06-03 07:30 → 08:00 → 09:10 | 0 / vide | S03 / C03 / R02 | TEC-0001 | OTT-000290 : 1 h (TEC-0001, 2025-06-03) | type absent → « correctif différé » (signalé) ; titre absent → 80 premiers caractères du compte rendu : « Courroie du ventilateur détendue : retendue et alignée, puis vibrations mesurées » |
| 18 | 4601 | CV-02 | doublon supposé | — | — | — | — | — | — | — | même équipement CV-02 (EQ-0023), même date de création 2025-09-25 12:54 et même titre que l'OT existant OT-2025-0002 : montrée avec « Importer quand même » (non cochée) |
| 19 | 4514 | CV-02 | doublon sûr | — | — | — | — | — | — | — | même ancien numéro « 4514 » que la ligne 6, plus haut dans le même fichier : doublon sûr, ignorée |

## garanties.csv — garanties des équipements (2.2)

- **Type de données** : `garanties`.
- **Format** : CSV UTF-8 **avec BOM**, séparateur « ; », CRLF, dates JJ/MM/AAAA.
- **En-tête** : ligne 1 ; colonnes « Repère », « Fournisseur », « Date de début », « Échéance », « Ce qui est couvert ».

| Colonne | Champ attendu | Statut attendu |
| --- | --- | --- |
| Repère | `equipement` (par repère, doit exister ; clé naturelle avec la fin) | sûre (synonyme) |
| Fournisseur | `fournisseur` (par nom, créé s'il manque) | sûre (libellé) |
| Date de début | `date_debut` | sûre (synonyme) |
| Échéance | `date_fin` (clé naturelle avec l'équipement) | sûre (synonyme) |
| Ce qui est couvert | `conditions` | sûre (synonyme) |

**Pièges** :
- clé naturelle équipement + date de fin : une deuxième garantie du même équipement (PO-01, autre fin) est une création, pas une mise à jour ;
- « ; » dans les conditions (ligne 2, champ entre guillemets) ;
- fournisseur inconnu créé une fois (D88 a), mais pas celui d'une ligne refusée (lignes 8 et 9) ;
- fournisseur et date de début vides (facultatifs) ; fin avant le début (formulaire) ; échéance vide ; date impossible ; équipement inconnu ; doublon dans le fichier.

**Attendu** (base de démo) : 10 lignes de données : 3 créer, 1 mettre à jour, 1 identique, 5 refusée. Référence créée : fournisseur FOU-0006 « Froid Industriel du Dauphiné » (les fournisseurs des lignes refusées ne sont pas créés).

| Ligne | Clé | Action attendue | Détail |
| --- | --- | --- | --- |
| 2 | CP-01 / 2027-03-28 | identique | GAR-0001 : aucune colonne ne change ; « ; » dans les conditions (champ entre guillemets) |
| 3 | PO-02 / 2026-11-18 | mettre à jour | GAR-0002 : conditions « Garniture mécanique et roulements : pièces seules, main-d'œuvre à notre charge. » → « Garniture mécanique, roulements et main-d'œuvre. » |
| 4 | GF-01 / 2028-08-31 | créer | GAR-0004 (équipement EQ-0007) ; fournisseur FOU-0006 « Froid Industriel du Dauphiné » créé |
| 5 | CU-01 / 2027-06-30 | créer | GAR-0005 (équipement EQ-0016) ; sans fournisseur ni date de début (facultatifs) |
| 6 | PO-01 / 2028-07-01 | créer | GAR-0006 (équipement EQ-0004) : une autre date de fin que GAR-0003 (fin 2026-07-01), donc une autre garantie |
| 7 | XX-99 / 2027-12-31 | refusée | équipement « XX-99 » introuvable |
| 8 | PR-01 / (vide) | refusée | échéance vide (fin de garantie : obligatoire, clé naturelle avec l'équipement) ; « Hydraulique du Guiers » n'est pas créé |
| 9 | SC-01 / 2026-03-01 | refusée | fin avant le début (contrôle du formulaire, Garanties.verifierGarantie) ; « Scies et Lames du Grésivaudan » n'est pas créé |
| 10 | PT-01 / 31/02/2027 | refusée | échéance « 31/02/2027 » illisible (jour inexistant) |
| 11 | GF-01 / 2028-08-31 | refusée | doublon dans le fichier (même équipement et même date de fin que la ligne 4) |

## contrats.csv — contrats de prestataires (2.2)

- **Type de données** : `contrats`.
- **Format** : CSV UTF-8 **avec BOM**, séparateur « ; », CRLF, dates JJ/MM/AAAA, décimales à virgule.
- **En-tête** : ligne 1 ; colonnes « Prestataire », « Objet », « Équipements », « Début », « Fin », « Préavis », « Tacite reconduction », « Montant annuel HT », « Périmètre ».

| Colonne | Champ attendu | Statut attendu |
| --- | --- | --- |
| Prestataire | `prestataire` (par nom, créé s'il manque ; clé naturelle avec l'objet) | sûre (libellé) |
| Objet | `objet` | sûre (libellé) |
| Équipements | `equipements_concernes` → `equipement_ids` (repères → identifiants séparés par « ; ») | sûre (synonyme) |
| Début | `date_debut` | sûre (libellé) |
| Fin | `date_fin` | sûre (libellé) |
| Préavis | `preavis_mois` | sûre (synonyme) |
| Tacite reconduction | `reconduction_tacite` | sûre (synonyme) |
| Montant annuel HT | `montant_annuel` (devise réglée, hors taxes, D190) | sûre (libellé) |
| Périmètre | `perimetre` | sûre (libellé) |

**Pièges** :
- équipements concernés en repères séparés par des virgules (« CP-01, CP-01.SEC ») ou par « ; » (ligne 5, champ entre guillemets) ; un repère inconnu (« CV-09 », ligne 6) refuse sa ligne, les autres s'importent ;
- prestataire inconnu créé une fois, écrit aussi en majuscules (doublon ligne 4) ; celui d'une ligne refusée n'est pas créé ;
- montant « 2 350,50 » (espace, virgule) ; montant vide (facultatif) ; montant négatif sur une fiche existante (refusée, la fiche ne change pas) ; préavis « trois » ; prestataire vide ;
- contrat existant identique et contrat existant mis à jour (fin et montant ; cellules vides : rien d'effacé).

**Attendu** (base de démo) : 10 lignes de données : 2 créer, 1 mettre à jour, 1 identique, 6 refusée. Référence créée : fournisseur FOU-0006 « Froid Industriel du Dauphiné » (prestataire).

| Ligne | Clé | Action attendue | Détail |
| --- | --- | --- | --- |
| 2 | Fluidalpes Services / compresseurs | identique | CTP-0001 : aucune colonne ne change ; équipements « CP-01, CP-01.SEC » = EQ-0001;EQ-0002 |
| 3 | Électro-Alpes Distribution / électricité | mettre à jour | CTP-0002 : fin 2026-06-30 → 2027-06-30 ; montant 1250 → 1300 (cellules vides : rien d'effacé) |
| 4 | Froid Industriel du Dauphiné / groupe froid | créer | CTP-0005 (équipement EQ-0007) ; prestataire FOU-0006 « Froid Industriel du Dauphiné » créé ; montant « 2 350,50 » → 2350.5 ; préavis de 3 mois : date limite de résiliation 2026-09-30 (CS173) |
| 5 | Garnitech Pompes / pompes | créer | CTP-0006 ; repères séparés par « ; » (champ entre guillemets) → EQ-0004;EQ-0005;EQ-0006 ; sans montant (facultatif) |
| 6 | Lubrifix Industrie / convoyeurs | refusée | équipement « CV-09 » introuvable (un repère inconnu refuse la ligne, les autres s'importent) |
| 7 | (vide) / filtres | refusée | prestataire vide (obligatoire, clé naturelle avec l'objet) |
| 8 | Mécaroule Distribution / roulements | refusée | préavis « trois » illisible (nombre entier attendu) |
| 9 | Lubrifix Industrie / chaînes | refusée | montant « -200 » négatif (contrôle du formulaire, Garanties.verifierContrat) : la fiche CTP-0004 n'est pas touchée |
| 10 | Froid Industriel du Dauphiné / groupe froid | refusée | doublon dans le fichier (même prestataire, écrit en majuscules, et même objet que la ligne 4) |
| 11 | Hydraulique du Guiers / hydraulique | refusée | fin avant le début (contrôle du formulaire) ; prestataire « Hydraulique du Guiers » pas créé |

## reserves.csv — réserves des contrôles (2.2)

- **Type de données** : `reserves`.
- **Format** : CSV UTF-8 **avec BOM**, séparateur « ; », CRLF, dates JJ/MM/AAAA.
- **En-tête** : ligne 1 ; colonnes « Repère », « Nature du contrôle », « Date du contrôle », « Réserve », « Gravité », « Échéance », « Levée », « Levée le », « Commentaire ».

| Colonne | Champ attendu | Statut attendu |
| --- | --- | --- |
| Repère | `equipement` (par repère, doit exister ; désigne le contrôle avec la nature) | sûre (synonyme) |
| Nature du contrôle | `nature` → `controle_id` (contrôle de cet équipement, doit exister) | sûre (libellé) |
| Date du contrôle | `date_controle` (clé naturelle avec le contrôle et le texte) | sûre (libellé) |
| Réserve | `texte` (clé naturelle) | sûre (libellé) |
| Gravité | `gravite` (mineure, majeure, critique) | sûre (libellé) |
| Échéance | `echeance_levee` | sûre (synonyme) |
| Levée | `levee` | sûre (libellé) |
| Levée le | `date_levee` | sûre (synonyme) |
| Commentaire | `commentaire_levee` | sûre (synonyme) |

**Pièges** :
- trois réserves créées et rattachées à leur contrôle, désigné par le repère et la nature (lignes 4 à 6) ; contrôle inconnu (ligne 7) : refusée ;
- levée sans date : date de levée vide, commentaire « levée avant la 2.2, date inconnue » s'il manque (D183), sur une réserve existante (ligne 3) et sur une nouvelle (ligne 6) ;
- règles des réserves (L2) : date du contrôle vide ou future, échéance avant le contrôle, levée datée sans commentaire, réserve déjà levée modifiée ; « non » dans Levée avec une date ; gravité hors liste ; doublon écrit en majuscules.

**Attendu** (base de démo) : 15 lignes de données : 3 créer, 1 mettre à jour, 1 identique, 10 refusée.

| Ligne | Clé | Action attendue | Détail |
| --- | --- | --- | --- |
| 2 | AE-01 / schéma unifilaire | identique | RES-00003 : aucune colonne ne change |
| 3 | RA-01 / purgeur | mettre à jour | RES-00001 : gravité (vide) → majeure ; levée 0 → 1, sans date (date de levée vide) ; commentaire de levée (vide) → « levée avant la 2.2, date inconnue » (D183) |
| 4 | GF-01 / raccord | créer | RES-00004 (contrôle CTR-0005), ouverte, échéance 2026-04-24 |
| 5 | GF-01 / étiquetage | créer | RES-00005 (contrôle CTR-0005), levée le 2026-04-10 avec son commentaire |
| 6 | PT-01 / fin de course | créer | RES-00006 (contrôle CTR-0001), levée sans date : date de levée vide, commentaire « levée avant la 2.2, date inconnue » (D183) |
| 7 | CH-01 / freins | refusée | contrôle « Vérification des freins » introuvable pour CH-01 (un contrôle inconnu refuse la ligne) |
| 8 | XX-99 | refusée | équipement « XX-99 » introuvable |
| 9 | VE-02 / débit | refusée | levée datée sans commentaire (règle de la levée : commentaire obligatoire) |
| 10 | GF-01 / futur | refusée | date du contrôle 2026-12-15 dans le futur (règle de l'ajout ; démo au 2026-10-19) |
| 11 | AE-04 / extincteur | refusée | échéance de levée avant la date du contrôle (règle de l'ajout) |
| 12 | AE-01 / différentiel | refusée | RES-00002 déjà levée : elle ne se modifie plus (la levée est un fait) ; la fiche n'est pas touchée |
| 13 | CH-01 / avertisseur | refusée | « non » dans Levée avec une date de levée : contradiction |
| 14 | GF-01 / raccord | refusée | doublon dans le fichier (même contrôle, même date et même texte, écrit en majuscules, que la ligne 4) |
| 15 | VE-02 / gaine | refusée | gravité « grave » hors de la liste (mineure, majeure, critique) |
| 16 | PT-01 / câble | refusée | date du contrôle vide (règle de l'ajout : date du contrôle obligatoire) |

## Fichiers piégés (CS89 : message clair, rien de lu ni d'écrit, l'onglet ne se bloque pas)

| Fichier | Contenu | Attendu |
| --- | --- | --- |
| `trop_de_lignes.csv` | UTF-8 BOM « ; » : 1 ligne d'en-tête + **20 001** lignes de données = 20 002 lignes non vides | `Import.ErreurImport` « fichier trop grand » (plafond : 20 000 lignes de données + 1 ligne d'en-tête, soit 20 001 lignes non vides au plus) ; rien n'est lu |
| `limite_de_lignes.csv` | même forme : 1 ligne d'en-tête + **20 000** lignes de données = 20 001 lignes | **accepté** (pile au plafond) : 20 000 lignes de données lues (type `articles` : référence, désignation, qté stock) |
| `chiffre.xlsx` | conteneur OLE/CFB (signature `D0 CF 11 E0 A1 B1 1A E1`) avec les flux `EncryptionInfo` (chiffrement agile 4.4, descripteur XML aux valeurs factices, dans le mini-flux) et `EncryptedPackage` (6 024 octets pseudo-aléatoires) : la forme d'un classeur Excel protégé par mot de passe. Contenu factice : rien n'est vraiment chiffré ; pas de stockage `\x06DataSpaces` | `Import.ErreurImport` « fichier protégé par un mot de passe » (SheetJS 0.20.3 lève « File is password-protected ») |
| `vide.csv` | 0 octet | `Import.ErreurImport` « fichier vide » |
| `lignes_vides.csv` | BOM UTF-8 puis seulement des séparateurs et des lignes vides | `Import.ErreurImport` « aucune ligne non vide » |
| `sans_entete.csv` | 5 lignes de nombres seulement (« ; », virgules décimales) | aucune ligne d'en-tête reconnue (`Import.ligneEntete` ne trouve aucune ligne de textes) → message clair, rien d'importé |
| `cellules_repetees.ods` | « bombe » : une ligne d'en-tête, puis une ligne dont **une cellule non vide est répétée 1 000 000 de fois** (`table:number-columns-repeated="1000000"`) ; archive de moins de 2 Ko | `Import.ErreurImport` « fichier trop grand » (plus de 200 colonnes), sans développer le million de cellules |

À ne pas confondre : `equipements.ods` contient aussi des cellules et des lignes répétées, mais **vides** (comme
LibreOffice les écrit) ; il doit se lire normalement (25 lignes).

## Choix retenus là où le contrat (§18) se tait — à respecter par T80 à T86

1. Une **clé naturelle vide** refuse la ligne, même quand le champ n'est pas obligatoire dans le schéma
   (fournisseur sans nom, compteur sans équipement, gamme sans libellé).
2. **Stock initial** : « 0 » crée un mouvement « inventaire » de 0 ; une cellule vide n'en crée aucun (ni pour un
   article nouveau, ni pour un article existant).
3. **Gammes** : les lignes d'une même gamme (même équipement + même libellé) sont ses opérations, dans l'ordre du
   fichier ; ce n'est pas un doublon. Si l'équipement est introuvable, toutes les lignes de la gamme sont refusées.
4. **Localisation par chemin** : libellés comparés tels quels, niveau par niveau ; séparateurs « > », « / » ou
   « \ » ; seuls les niveaux manquants sont créés (type déduit du niveau : site, atelier, ligne), une seule fois.
5. **Technicien** (habilitations, historique) : « Prénom Nom » ou « Nom Prénom », casse ignorée
   (« GARNIER Thomas »).
6. **Historique** : équivalences de type ci-dessus ; codes par code ou par libellé, casse et accents ignorés
   (`Import.comparable`), seulement dans la famille de la colonne ; titre absent = les 80 premiers caractères du
   compte rendu du fichier (sans la ligne « Ancien n° » ; ici la coupe tombe en fin de mot, une coupe au dernier
   mot entier donnerait le même titre) ; un doublon supposé se cherche aussi parmi les lignes précédentes du même
   fichier ; la ligne `ot_temps` prend le technicien de l'OT et la date de fin (jour), et n'existe pas sans temps.
7. Les fichiers évitent exprès les cas que le contrat laisse ouverts (décimal « 38,00 » face à « 38 » en base,
   opérations d'une gamme existante, stock d'un article existant, temps passé sans technicien, équipement parent
   défini **plus bas** que son enfant) : ils ne fixent rien à leur sujet.

## Ce que SheetJS 0.20.3 fait de ces fichiers (relevé à la génération, utile à la lecture T81)

- `equipements.xlsx` et `equipements.xls` : dates rendues en nombres (numéros de série, format `dd/mm/yyyy`
  sur la cellule) ; feuilles « Parc » (`!ref` A1:I25) et « Notes » (A1:A2).
- `equipements.ods` : les dates arrivent en objets `Date` **même sans `cellDates`**, à minuit **heure locale**
  (en France : 22 h ou 23 h UTC la veille) ; la lecture doit les rendre en `AAAA-MM-JJ` avec la date locale,
  jamais par `toISOString()`. Les cellules et lignes vides répétées ne gonflent pas `!ref` (A1:I25).
- `cellules_repetees.ods` : SheetJS **développe** la ligne répétée (environ 1 000 000 de cellules créées, environ
  2 s dans Chromium) et rend pourtant `!ref` = A1:B2 : le plafond de 200 colonnes ne se voit ni dans `!ref` ni
  par `sheetRows`. La lecture doit repérer les `table:number-columns-repeated` non vides dans `content.xml`
  **avant** d'appeler SheetJS (ou refuser autrement), pour que l'onglet ne se bloque pas.
- `chiffre.xlsx` : `XLSX.read` lève « File is password-protected » ; `XLSX.CFB.read` y voit `EncryptionInfo`
  et `EncryptedPackage`.

## Enchaînement sur une base vide (recette T86)

Les attentes chiffrées ci-dessus valent pour la **démo**. Pour reprendre un atelier sur une base **vide**, importer
dans cet ordre : `codes.csv`, `techniciens.tsv`, `fournisseurs.tsv`, `equipements.xlsx`, `articles.csv`,
`habilitations.csv`, `compteurs.csv`, `controles.csv`, `gammes.xlsx`, `historique.csv`. La liste du parc contient
toutes les machines de la démo citées par les autres fichiers (avec leurs chemins de localisation complets), les
techniciens et les codes de la démo sont dans leurs fichiers : sur une base vide, les références se résolvent alors
par les fiches créées plus tôt, sauf les pièges voulus (« XX-99 », « Pierre Martel », « Paul Dumas », lignes en
erreur). `garanties.csv`, `contrats.csv` et `reserves.csv` (2.2) ne font pas partie de cette reprise : leurs attentes
valent pour la démo seulement (ils citent des équipements que la liste du parc ne contient pas). Différences attendues avec la démo : tout ce qui était « identique » ou « mis à jour » est **créé** ;
« 007 » existe après la liste du parc (son compteur, sa gamme et l'habilitation d'Inès Chabert après
`techniciens.tsv` deviennent des créations) ; la ligne 18 de l'historique n'a plus d'OT existant en face
(elle est créée) ; « CP-01.PUR » trouve sa machine mère CP-01 plus haut dans le fichier. Le calcul Python
indépendant de T86 refait les comptes.
