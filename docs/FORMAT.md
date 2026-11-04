# Format des données de Prévo

Ce document décrit **comment les données de Prévo sont versionnées, migrées, sauvegardées, exportées et importées**.
Il s'adresse à un informaticien ou à un contributeur. Le détail de chaque colonne est dans
[FICHE_TECHNIQUE_CSV.md](../FICHE_TECHNIQUE_CSV.md) (générée depuis [js/schema.js](../js/schema.js)) ; l'architecture du
code est dans [ARCHITECTURE.md](ARCHITECTURE.md) (§3, §5.6, §8, §14.1 et §20.2).

Ce qui est écrit ici au présent existe dans le code. Ce qui est écrit au futur, ou marqué « prévu », est un **plan** :
rien n'est créé tant que la version concernée n'est pas développée.

## 1. Vocabulaire : quatre numéros qu'il ne faut pas confondre

| Notion | Forme | Exemple | À quoi elle sert |
|---|---|---|---|
| **Version de l'appli** | semver `x.y.z` | `2.0.1` | Ce que l'utilisateur télécharge ; affichée dans « À propos », comparée par le bandeau de mise à jour. |
| **Version du format** | entier | `3` | La forme des fichiers de données (tables, colonnes). C'est elle qui décide d'une migration. |
| **Empreinte d'un fichier** | SHA-256 tronqué | `3f2a…` | Contrôle de concurrence : « ce fichier a-t-il changé depuis que je l'ai lu ? ». Sans rapport avec le format. |
| **Version de l'API** | entier | `1` | Le contrat entre le navigateur et `serveur.py` (`/api/…`). |

Une nouvelle version de l'appli n'implique pas un nouveau format : 1.2.0, 2.0 bêta et 2.0.1 partagent le format 3.
Dans le code, `Schema.version` (`js/schema.js`) est le format courant ; il n'a rien à voir avec la version de l'appli.

## 2. Le format 3 (format courant)

Les données sont **24 fichiers CSV** dans le dossier de données : séparateur `;`, UTF-8 avec BOM, fins de ligne CRLF,
une apostrophe de tête protège les valeurs qu'Excel abîmerait (ARCHITECTURE.md §3). La liste des fichiers, leurs
colonnes, leurs types, leurs valeurs permises et leurs références sont dans
[FICHE_TECHNIQUE_CSV.md](../FICHE_TECHNIQUE_CSV.md) : on ne les recopie pas ici.

Le dossier d'accès (`acces/`, comptes, sessions, certificats) n'est **pas** une donnée au sens de ce document : il
n'est jamais exporté ni remplacé par un import. Les sauvegardes du serveur en copient les fichiers (comptes,
appareils, journal des connexions), jamais les sessions ni les clés, et ne le restaurent jamais.

## 3. Règles d'écriture

- Une table = un fichier CSV nommé comme dans le schéma (`equipements.csv`). Les colonnes sont écrites dans l'ordre du
  schéma ; **les colonnes ajoutées par un format sont toujours en fin de table**.
- À la lecture, Prévo est tolérant (ARCHITECTURE.md §3.3) : un fichier modifié dans Excel, avec des colonnes dans un
  autre ordre ou des colonnes en plus, reste lisible. Les colonnes inconnues sont conservées à l'écriture.
- Aucune ligne de métadonnées et aucune colonne technique n'est ajoutée dans les CSV : un tableur les casserait, et
  le serveur de la 2.0 bêta les refuserait. Le format n'est donc pas écrit dans chaque fichier (voir §4).
- Une ligne n'est jamais supprimée : on désactive (`actif`) ou on annule. Le journal (`journal.csv`) est écrit par ajout.
- **Un fichier abîmé n'est jamais réécrit.** Abîmé = une réécriture en perdrait une partie : structure abîmée
  (guillemet non fermé, texte collé à un guillemet fermant) ou valeurs au-delà de l'en-tête (en-tête coupé). La garde
  est dans la fonction d'écriture commune du stockage, par laquelle passent toutes les écritures : l'adaptateur du
  navigateur en mode dossier (`enregistrer`, `ajouter`) et, en mode serveur, le serveur lui-même (toutes les écritures
  d'un CSV de données, y compris celles de l'assistant, de la démo et du passage de format) ; `Donnees` refuse aussi
  plus tôt, avec le même message. Refus : `ErreurFichierAbime` dans le navigateur, **409** au code `fichier_abime`
  (avec `table`) pour le serveur ; rien n'est écrit, et un bandeau « Fichier abîmé » le dit à l'ouverture.
  Le message dit quoi faire, sans jargon (T201) : pour qui n'est pas responsable, « Fichier abîmé : prévenez le
  responsable » ; pour le responsable, le fichier et le remède (sauvegarde du jour, import ZIP). La saisie reste
  dans le formulaire (rien n'est vidé), et rien n'est écrit, pas même la photo d'une demande.
- **Ajout en fin de fichier** (journal) : refusé si le fichier en place se termine au milieu d'un texte entre
  guillemets (guillemet ouvert jamais fermé), sinon les lignes ajoutées y seraient avalées. Une ligne de journal
  refusée ne fait pas échouer l'action de l'utilisateur.
- **Deux dérogations seulement**, qui sont les remèdes : la **restauration** d'une sauvegarde et l'**import ZIP**
  (option `remplacerFichierAbime` de l'adaptateur ; en mode serveur, en-tête `X-Prevo-Remplacer-Abime: 1` sur
  `PUT /api/csv/<table>` ; avec les comptes, réservé au responsable comme l'import ZIP, 403 sinon).

## 4. Numéro de format et signature

- **Numéro de format de la base** : la valeur de `version_schema` dans `parametres.csv`. Absente, vide ou illisible :
  format 1 (les fichiers d'avant les versions publiées n'avaient pas ce paramètre).
- **Signature d'un fichier** : le format d'un fichier se reconnaît à son en-tête. Pour une table, c'est le plus grand
  format dont toutes les colonnes sont présentes. Les noms de colonnes sont comparés sans casse, sans accents, sans
  espaces ni soulignés (comme la lecture de Prévo). Si même les colonnes du premier format manquent, le fichier est
  dit abîmé ou incomplet.
- Le **format de départ d'une migration** est le plus petit format trouvé entre `version_schema` et les signatures des
  fichiers : un fichier resté en arrière est donc toujours rattrapé.
- Implémentations : `Formats.formatDuFichier` et `Formats.versionDeBase` dans [js/formats.js](../js/formats.js),
  `format_du_fichier` et `version_de_base` dans [serveur.py](../serveur.py). Les deux suivent les mêmes règles et un test
  les compare.

## 5. Historique des formats

| Format | Versions de l'appli | Ajouts (par rapport au précédent) |
|---|---|---|
| **1** | avant les versions publiées | Les 22 tables du brief (§6), sans les colonnes ci-dessous. `version_schema` absent. |
| **2** | 1.0, 1.1 | Colonnes `equipements.valeur_remplacement`, `demandes.symptome_code`, `demandes.ot_origine_id`, `ordres_travail.anomalie_constatee` (défaut `0`), en fin de table. |
| **3** | 1.2.0, 2.0 bêta, 2.0.1 | Colonne `ordres_travail.astuce` en fin de table ; tables `wiki_pages` et `wiki_journal` (créées vides). 24 tables en tout. |

La source de vérité est l'attribut `depuisVersion` dans [js/schema.js](../js/schema.js).

## 6. Migrations

- **Registre d'étapes** : une étape par passage de N à N+1 (1→2, 2→3), dans `Formats.ETAPES` (navigateur) et
  `ETAPES_FORMAT` (serveur, miroir exact). Chaque étape est **pure** (l'entrée n'est pas modifiée), **idempotente**
  (rejouée, elle ne change rien) et **additive** : elle ajoute des colonnes en fin de table ou des tables vides, et
  pose `version_schema`. Les colonnes et tables inconnues sont gardées telles quelles.
- **Journal** : chaque étape ajoute au journal la ligne « passage au format N du fichier ; sauvegarde … faite juste
  avant ». Ce texte est relu par une suggestion de l'appli : il ne doit pas changer.
- **Qui l'exécute** :
  - en **mode serveur**, le **serveur, au démarrage**, avant toute connexion ;
  - en **mode dossier** (fichiers ouverts directement par le navigateur), le **navigateur**, au chargement ;
  - en **démo**, rien n'est écrit.
- **Sauvegarde d'abord** : une sauvegarde `avant-format-vN` est faite avant la première étape ; si elle échoue, rien
  n'est migré et la migration est retentée au démarrage suivant.
- **Fichier illisible** : un fichier que Prévo ne sait pas lire n'est jamais réécrit.
- **Règle pour l'avenir** : un nouveau format reste **additif** tant que possible. Les versions 1.2 et 2.0 bêta
  rouvrent des fichiers d'un format plus récent sans garde : toute modification non additive (renommer ou retirer une
  colonne, changer le sens d'une valeur) les ferait écrire des données fausses.

## 7. Données d'un format plus récent que l'appli : lecture seule

Si la base (ou un fichier) porte un format supérieur au format courant de l'appli, Prévo n'y écrit rien :

- le **navigateur** passe en lecture seule (`Donnees.lectureSeule`, erreur `ErreurLectureSeule`) avec un message clair ;
- le **serveur** refuse toute écriture : réponse **409** avec le code `format_plus_recent`.

Rien n'est migré « vers le bas » : on met l'appli à jour, ou on restaure une sauvegarde.

## 8. Sauvegardes

| Déclencheur | Nom (motif) | Purgée automatiquement ? |
|---|---|---|
| Avant la première écriture du jour, et au démarrage du serveur | `AAAA-MM-JJ` (quotidienne) | Oui, après **30 jours** |
| Avant une migration | `avant-format-vN` | Non |
| Avant un import ZIP (avec `documents/`) | `avant-import-zip` | Non |
| Au premier démarrage d'une nouvelle version de l'appli (comparée à la version notée) | `avant-mise-a-jour` | Non |
| À la demande (Paramètres) | `AAAA-MM-JJ_HHMMSS` (manuelle) | Oui, les 60 dernières gardées |

- **Jamais à la fermeture** : un navigateur ne garantit pas une écriture à la fermeture.
- Les sauvegardes « avant-… » ne sont jamais purgées automatiquement : c'est la trace de ce qui a précédé un
  changement important. On les supprime à la main quand on n'en a plus besoin.
- Les documents (photos, PDF) sont dans les sauvegardes faites avant un import et dans l'export ZIP, pas dans les
  quotidiennes.
- **Restaurer** une sauvegarde (Paramètres › Sauvegardes) remet ses tables (les CSV) et rien d'autre : restaurer une
  sauvegarde `avant-import-zip` ne recopie **pas** les documents de son dossier `documents/`. Pour les retrouver, on
  les copie à la main de `sauvegardes/<nom>/documents/` vers `documents/`.
- La version notée est dans `derniere-version.json`, à la racine du dossier de données : `{"version", "depuis"}`
  (version de l'appli, date `AAAA-MM-JJTHH:MM:SS`). Elle est écrite après la sauvegarde `avant-mise-a-jour`, et
  seulement si celle-ci a réussi (base vide : voir plus bas).
- La **copie externe nocturne** (lot 7, ARCHITECTURE.md §22.11) est inchangée.
- Piège : un dossier nommé comme la version de l'appli (`prevo-<version>/`) peut être remplacé par une mise à jour
  manuelle ; gardez les données hors de ce dossier (voir [INSTALLATION.md](INSTALLATION.md)).
- Mêmes règles en mode dossier, sauf pour une **base vide** (aucun CSV) : le mode dossier note la version dès
  l'ouverture, sans sauvegarde (il n'y a rien à garder) ; le serveur, lui, n'écrit rien au démarrage. La base créée
  ensuite par le navigateur (« Créer une base vide », démo) reçoit donc, en mode serveur, une sauvegarde
  `avant-mise-a-jour` au démarrage suivant du serveur, puis la version est notée.

## 9. Manifeste (`manifeste.json`)

Chaque sauvegarde et chaque export ZIP contient un `manifeste.json` :

```json
{
  "application": "Prévo",
  "version_appli": "2.0.1",
  "format": 3,
  "date": "2026-11-04T09:30:00",
  "motif": "avant-format-v3",
  "mode": "serveur",
  "fichiers": [ { "nom": "equipements.csv", "octets": 1234, "sha256": "…" } ]
}
```

`fichiers` liste chaque fichier avec sa taille et son empreinte SHA-256 complète (hexadécimal), triés par nom.
`date` est toujours de la forme `AAAA-MM-JJTHH:MM:SS` (heure locale, sans fuseau horaire) : celle du serveur pour ses
sauvegardes, celle du poste pour le mode dossier et l'export.
Le manifeste sert à contrôler qu'une sauvegarde ou un ZIP est complet et intact, et à savoir de quel format il vient.

## 10. Export et import ZIP

**Export** (en un clic) : tous les CSV, les documents cités, les rapports figés et `manifeste.json`. **Jamais**
`acces/`.

**Import** : remplacement complet seulement (pas de fusion).

- Réservé au **responsable** (ou à toute personne si l'installation n'a pas de comptes).
- Contrôles avant d'écrire quoi que ce soit : taille totale, nombre d'entrées, taux de compression (bombe de
  décompression), chemins (aucun `..`, aucun chemin absolu), noms de fichiers admis, empreintes du manifeste, format.
- Lecture en **deux passes** : chaque document est décompressé pour le contrôle puis oublié, puis relu depuis le ZIP
  (empreinte revérifiée) juste avant d'être écrit. Pic de mémoire : le ZIP (200 Mo au plus) + les tables + UN document.
- Une **sauvegarde `avant-import-zip`** est faite d'abord (documents compris) ; une confirmation liste ce qui sera
  remplacé.
- `acces/` n'est jamais remplacé.
- Un ZIP d'un format plus ancien est migré ; un ZIP d'un format **plus récent** est refusé.
- Le navigateur lit le ZIP et écrit par le chemin habituel : aucune route serveur nouvelle.

## 11. Ajouter un format 4 (liste de contrôle)

1. **Schéma** : dans [js/schema.js](../js/schema.js), marquer les nouveaux champs `depuisVersion(4, …)` (toujours en fin
   de table) et les nouvelles tables `depuisVersion: 4` ; passer `Schema.version` à 4. Rester additif (§6).
2. **Étape de migration** : ajouter `etape(3, 4, '…')` dans `ETAPES` de [js/formats.js](../js/formats.js) **et** son
   miroir `EtapeDeFormat(3, 4, '…')` dans `ETAPES_FORMAT` de [serveur.py](../serveur.py), avec `VERSION_SCHEMA_CSV`,
   `PREMIER_FORMAT_DES_TABLES`, `PREMIER_FORMAT_DES_COLONNES`, `DEFAUTS_DES_CHAMPS`, `COLONNES_PAR_TABLE` et
   `COLONNES_DES_FORMATS_SUIVANTS`. Les deux descriptions doivent être identiques.
3. **Jeu d'essai** : ajouter un jeu au format 3 dans `tests/jeux_formats.py` et sa notice dans
   `tests/fixtures/formats/LISEZMOI.md`.
4. **Motif de sauvegarde** : déclarer `avant-format-v4` (liste des motifs de `serveur.py` et du navigateur).
5. **Fiche technique** : régénérer [FICHE_TECHNIQUE_CSV.md](../FICHE_TECHNIQUE_CSV.md) depuis le schéma.
6. **Tests** : étape 3→4 (pure, idempotente), chaîne 1→4 sans trou, parité navigateur/serveur
   (`tests/test_formats_js.py`, `tests/test_formats_serveur.py`), lecture seule d'un format 5 simulé.
7. **Documentation** : mettre à jour les tableaux des §5 et §12 de ce document, et ARCHITECTURE.md §20.2.

## 12. Plan des versions à venir (2.1 à 2.4)

Cette section est un **plan** : ce qui est listé est **prévu, non créé**. Chaque ajout arrivera dans la version
indiquée, par une étape de migration additive (§6), et seulement si cette version s'en sert. Les noms et les rôles
peuvent encore changer. Ces fonctions aident au suivi ; la responsabilité reste celle de l'employeur, et les
périodicités réglementaires seront sourcées et modifiables.

**Ce qui existe déjà (format 3) et ne sera donc pas recréé :**

- Compteurs d'heures et relevés : tables `compteurs` et `releves`, `gammes.declencheur` (`compteur`, `seuil`),
  `gammes.compteur_id`, `gammes.periodicite_unites`, `gammes.releve_derniere_realisation`. La 2.3 s'appuie dessus.
- Habilitations : table `habilitations` (`date_obtention`, `date_echeance`) et `equipements.habilitation_requise`.
- Contrôles réglementaires : table `controles_reglementaires` (périodicité, organisme, rapport, `observations`,
  `observations_levees`).
- Pièces de rechange : `articles` (`stock`, `stock_securite`, `point_commande`, `qte_commande`), `article_equipement`
  (lien aux machines), `mouvements_stock`, `achats`.
- Consignation : texte libre `equipements.consignation`.
- Coût de l'arrêt : `ordres_travail.arret_production`, `ordres_travail.duree_arret_h` et
  `equipements.valeur_remplacement`.
- Fiche machine : `equipements.marque`, `modele`, `num_serie`, `date_mes`, `document`.

**Ce qui est prévu :**

- 2.1, mode formateur : aucune table nouvelle. Un pack de scénarios est un ZIP au format ci-dessus (§10), importé
  par l'import existant ; la remise à zéro est un import de ce pack.
- 2.4, mode hébergé : aucune colonne de données. Le PWA est du code ; les réglages de notification (adresse e-mail ou
  sujet ntfy) seront des clés de `parametres` (des lignes, pas des colonnes).

<!-- plan:debut -->
- `reserves_controle` (2.2) : une ligne par réserve d'un rapport de contrôle (contrôle, texte, échéance de levée, date de levée, OT lié), pour suivre les réserves une à une.
- `controles_reglementaires.source_periodicite` (2.2) : d'où vient la périodicité proposée (texte de référence ou saisie).
- `habilitations.recyclage_mois` (2.2) : durée de validité avant recyclage, pour calculer l'échéance.
- `habilitations.justificatif` (2.2) : document (attestation, CACES) rattaché à l'habilitation.
- `garanties` (2.2) : garantie d'un équipement (équipement, fournisseur, début, fin, conditions).
- `contrats_prestataires` (2.2) : contrat de maintenance ou de contrôle (prestataire, périmètre, début, fin, préavis).
- `equipements.cout_arret_h` (2.2) : coût d'une heure d'arrêt de la machine, pour le coût de l'arrêt du rapport mensuel.
- `equipements.plaque_photo` (2.3) : photo de la plaque signalétique, d'où l'IA propose la fiche.
- `equipements.annee_fabrication` (2.3) : année de fabrication lue sur la plaque.
- `consignations` (2.3) : fiche de consignation structurée par machine (énergie, point d'isolement, dispositif, vérification, validation), affichée par QR code ; aide, ne remplace pas la procédure.
<!-- plan:fin -->

## 13. Performances connues

Contrôle « fichier abîmé » (§3) : avant chaque réécriture d'une table, le fichier en place est relu en entier. Mesuré
le 2026-11-04 (PC de développement, Chromium, médiane de 7 mesures) sur les jeux de charge de
`outils/generer_demo.py --volume 500,N` :

| Fichier | 5 000 OT | 20 000 OT |
| --- | --- | --- |
| `ordres_travail.csv` (2,7 Mo / 11 Mo), mode dossier (navigateur) | 156 ms | **700 ms** |
| `ordres_travail.csv`, mode serveur (serveur.py) | 70 ms | 358 ms |
| `ot_operations.csv` (1 Mo), mode dossier / serveur | 60 / 40 ms | 45 / 35 ms |
| `equipements.csv` (0,3 Mo), mode dossier / serveur | 7 / 7 ms | 6 / 6 ms |

Ce temps s'ajoute à chaque enregistrement qui touche la table (par exemple chaque OT enregistré). L'ajout en fin de
journal ne fait qu'un contrôle léger (guillemet ouvert en fin de fichier) : 80 ms dans le navigateur et 160 ms sur le
serveur pour un journal de 14,6 Mo.

**À surveiller** : au-delà d'environ 15 000 OT en mode dossier, le contrôle dépasse 500 ms par enregistrement d'un OT.
Une optimisation est possible plus tard (ne pas recontrôler un fichier que Prévo vient lui-même d'écrire), sans
changer la règle.
