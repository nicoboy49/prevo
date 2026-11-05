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
- **Fichier abîmé importé tel quel** (T213) : l'import ZIP écrit avec les octets du ZIP un CSV que le manifeste marque
  `"abime": true` (option `abimeDepuis` de l'adaptateur ; en mode serveur, en-tête `X-Prevo-Abime-Depuis:
  AAAA-MM-JJTHH:MM:SS` avec `X-Prevo-Remplacer-Abime: 1`, 400 sinon). Le serveur ne compare alors pas son en-tête au
  schéma, seulement s'il voit lui-même le fichier abîmé (UTF-8 et cellules dangereuses toujours contrôlés). La date
  va dans `fichiers-abimes.json` ; après une écriture de l'import, ce fichier suit la table (saine : retirée).

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
Un CSV abîmé (§3) porte aussi `"abime": true` (sauvegardes, T206 ; export, T210) et, dans un export, `"abime_depuis":
"AAAA-MM-JJTHH:MM:SS"` : depuis quand Prévo le voit abîmé (`fichiers-abimes.json` ; absente si inconnue, T213).
Un export « données seules » porte `"documents": "exclus"` (juste avant `fichiers`, T214).
`date` est toujours de la forme `AAAA-MM-JJTHH:MM:SS` (heure locale, sans fuseau horaire) : celle du serveur pour ses
sauvegardes, celle du poste pour le mode dossier et l'export.
Le manifeste sert à contrôler qu'une sauvegarde ou un ZIP est complet et intact, et à savoir de quel format il vient.

## 10. Export et import ZIP

**Export** (en un clic) : tous les CSV, les documents cités, les rapports figés et `manifeste.json`. **Jamais**
`acces/`. Le ZIP est écrit **par morceaux** (T228) : un document à la fois, jamais tout le ZIP en mémoire JavaScript ;
photos et documents déjà compressés y sont stockés tels quels. Un navigateur trop ancien pour compresser par morceaux
(sans « deflate-raw ») refuse l'export avec un message clair, qui propose de copier le dossier de données.
Variante « données seules (sans les documents) » (T214) : les CSV et `manifeste.json` seulement
(`"documents": "exclus"`, aucun document listé manquant), `prevo-export-AAAA-MM-JJ-sans-documents.zip`, importable
comme l'export complet : les tables sont remplacées, les documents déjà présents gardés tels quels (jamais supprimés),
et la confirmation dit combien de documents cités par les données importées manquent.

**Règle (T208) : tout ce que Prévo exporte, Prévo peut le réimporter.** Limites de l'import, écrites à un seul endroit
(`LIMITES` de `js/modules/zip-lecture.js`) : ZIP de 4 Go au plus, sans ZIP64 (T229 : la plus grande taille que
l'écriture par morceaux produit, 4 Go moins 2 octets), 10 000 entrées (T212), 50 Mo par CSV, 10 Mo par document, 4 Go
décompressés (T229) ; `serveur.py` suit les deux qui le concernent (envoi d'une table 50 Mo, d'un document 10 Mo).
L'export les contrôle avant de produire le ZIP : s'il en dépasse une, il dit quoi (fichier, taille, limite) et ne
produit rien.

**Import** : remplacement complet seulement (pas de fusion).

- Réservé au **responsable** (ou à toute personne si l'installation n'a pas de comptes).
- Contrôles avant d'écrire quoi que ce soit : taille totale, nombre d'entrées, taux de compression (bombe de
  décompression), chemins (aucun `..`, aucun chemin absolu), noms de fichiers admis, empreintes du manifeste, format.
- Lecture en **deux passes** : chaque document est décompressé pour le contrôle puis oublié, puis relu depuis le
  fichier ZIP (empreinte revérifiée) juste avant d'être écrit. Le ZIP est lu **par morceaux**, jamais en entier (T227) :
  pic de mémoire, les tables + UN document. Un navigateur trop ancien pour décompresser par morceaux (sans
  « deflate-raw ») refuse l'import avec un message clair.
- Une **sauvegarde `avant-import-zip`** est faite d'abord (documents compris) ; une confirmation liste ce qui sera
  remplacé.
- `acces/` n'est jamais remplacé.
- Un ZIP d'un format plus ancien est migré ; un ZIP d'un format **plus récent** est refusé.
- Un CSV illisible ou abîmé est refusé, **sauf** s'il est marqué `"abime": true` au manifeste et que son empreinte
  correspond (T213, décision de Nicolas) : il est alors écrit tel quel, sans réparation ni migration ; la confirmation
  le dit ; la date « abîmé depuis » du manifeste est gardée (sinon : la date de l'import) ; la base retrouve le même
  état, bandeau « Fichier abîmé » compris.
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

**Mémoire de l'export et de l'import ZIP (T212).** Mesuré le 2026-11-04 (PC de développement, Chromium sans tête :
processus du navigateur de test seulement, relevés toutes les 100 ms) sur la grosse base de `tests/test_zip_limites.py`
(20 000 OT, journal de 45 Mo, 37 documents) complétée de photos fictives incompressibles :

| Cas | ZIP | Chromium (avant → pic) | Onglet seul (pic) | Durée |
| --- | --- | --- | --- | --- |
| Export, mode serveur, 367 documents | 385 Mo, 392 entrées | 0,7 → 2,6 Go | 2,1 Go | 78 s |
| Import du même ZIP, mode dossier | 385 Mo | 0,2 → 2,3 Go | 1,6 Go | 29 s |
| Export, mode dossier (cette base, après rechargement) | 385 Mo | 1,3 → 3,1 Go | 2,2 Go | 51 s |
| Export, mode serveur, 9 925 documents | 390 Mo, 9 950 entrées | 0,7 → 2,8 Go | 2,4 Go | 170 s |

Ces mesures datent d'avant la lecture et l'écriture par morceaux (T227, T228) : l'import lisait tout le ZIP avec
JSZip, l'export gardait tous les documents en mémoire puis JSZip produisait le ZIP, et l'onglet montait à 5 ou 6 fois
la taille du ZIP. Elles valent pour la bêta 2 : **sur un PC de 4 Go, ce n'était pas raisonnable près de la limite
d'alors (400 Mo)** ; Windows et le navigateur y laissent souvent moins de 1,5 Go libres, l'onglet pouvait se fermer
(rien n'est perdu, rien n'est exporté ni importé).

**Mémoire du ZIP par morceaux (T215).** Depuis T227 et T228, le ZIP est lu et écrit par morceaux
(`js/modules/zip-flux.js`, sans JSZip, retiré en T229) : mémoire JavaScript bornée aux tables plus UN document. Mesuré
le 2026-11-05 par la recette `tests/test_zip_morceaux.py` (même PC, même méthode que T212), mais avec un profil de
navigateur **sur le disque**, comme celui d'un utilisateur (T212 : contexte incognito, où Chromium garde tout en
mémoire) ; documents fictifs incompressibles, sur le jeu de charge `generer_demo.py --volume 300,2000` (300,20000 pour
les 9 888 photos) : avec la grosse base de T212, la recette n'aurait pas tenu au-dessus de 1,5 Go libres sur ce PC.

| Cas | ZIP | Chromium (avant → pic) | Onglet seul (pic) | Durée |
| --- | --- | --- | --- | --- |
| Export, mode serveur, 330 photos de 1 Mo | 330 Mo, 355 entrées | 0,2 → 0,7 Go | 0,2 Go | 14 s |
| Le même export, en incognito (le contexte de T212) | 330 Mo | 0,2 → 0,75 Go | 0,2 Go | 12 s |
| Import du même ZIP, mode dossier | 330 Mo | 0,2 → 0,3 Go | 0,2 Go | 14 s |
| Export, mode dossier (cette base, navigateur relancé) | 330 Mo | 0,2 → 0,7 Go | 0,2 Go | 7 s |
| Export, mode serveur, 9 888 photos de 34 Kio | 337 Mo, 9 913 entrées | 0,4 → 1,4 à 1,7 Go | 0,9 à 1,0 Go | 183 à 186 s |
| Export « données seules » de la grosse base de T212 | 6 Mo, 25 entrées | 0,7 → 1,3 Go | 1,2 Go | 6 s |
| Export, mode serveur, 220 documents de 9,5 Mo | 2 091 Mo, 245 entrées | 0,2 → 1,6 Go | 0,2 Go | 87 à 93 s |
| Import du même ZIP, mode dossier | 2 091 Mo | 0,2 → 0,4 à 0,45 Go | 0,3 Go | 100 à 117 s |
| Export, mode dossier (cette base, navigateur relancé) | 2 091 Mo | 0,2 → 1,5 Go | 0,2 Go | 71 s |
| Import du ZIP du serveur, mode serveur (quota des documents relevé) | 2 091 Mo | 0,2 → 0,5 Go | 0,3 Go | 100 à 119 s |
| ZIP écrit dans la page (`ZipFlux.ecrivain`), 40 entrées de 97,5 Mo | 3 900 Mo, 40 entrées | 0,1 → 0,4 Go | 0,2 Go | 73 à 96 s |

Toutes ces mesures ont été faites sous Chrome (Chromium) seulement : Edge et Firefox n'ont pas été mesurés.

- **L'onglet ne dépend plus de la taille du ZIP** : 0,2 à 0,3 Go de 330 Mo à 3,9 Go (contre 2,1 à 2,4 Go pour 385 Mo).
  Sauf pour des milliers de petites entrées : 0,9 à 1 Go pour 9 913 entrées (objets de chaque entrée en attente du
  ramasse-miettes).
- **L'import est borné** : 0,5 Go de Chromium au plus pour un ZIP de 2 Go, en mode dossier comme en mode serveur.
  En mode serveur, le dossier des documents est plafonné à 4 Go par défaut (`quota_documents_mo`, 4 096 depuis T250 ;
  2 048 lors de cette mesure, d'où « quota relevé ») : autant que l'import ZIP, pour qu'un export du mode dossier, qui
  n'a pas de plafond, se réimporte en mode serveur. Au-delà, l'import est refusé proprement (« Dossier des documents
  plein… », tables intactes, sauvegarde faite) ; le message dit où agrandir la place des documents (Paramètres ›
  Accès et installation, sur le PC serveur).
- **L'export reste proportionnel à la taille du ZIP, mais dans le processus principal du navigateur** : le ZIP en
  cours d'écriture est un Blob composé dont Chromium garde en mémoire chaque morceau de moins de 5 Mo et les 5 premiers
  Mo des autres (le reste va dans le dossier du profil : 1 Go sur le disque pour le ZIP de 2 Go). Chromium entier
  prend ainsi environ 1,5 fois la taille du ZIP pour des photos de 1 Mo, les deux tiers pour des documents de 9,5 Mo,
  un dixième pour des morceaux de 100 Mo ; tout est rendu après le téléchargement. En incognito, tout reste en mémoire.
- **La grosse base de T212** (20 000 OT, journal de 45 Mo) : l'onglet est à 0,6 Go avant tout export et monte à 1,2 Go
  pendant un export « données seules », sans aucun document (la garde de la recette, 1,5 Go libres sur le PC, l'a
  arrêté deux fois avant qu'il passe). Ce coût vient des tables (relecture du journal, 24 CSV sérialisés et empreints),
  pas du ZIP.

**Pour un PC de 4 Go** : l'import est désormais raisonnable jusqu'aux limites (4 Go). L'export l'est tant que le
navigateur peut prendre environ une fois et demie la taille du ZIP : 500 Mo en demandent jusqu'à 0,75 Go, ce que
demandaient 150 Mo avec JSZip ; un export de 2 Go (1,4 Go de plus dans le navigateur) ne l'est pas (la recette elle-même
n'a tenu qu'en attendant 3,3 Go libres). D'où l'avertissement de l'export complet (T222, `ZipDonnees.AVERTISSEMENT`),
gardé mais relevé de 150 à 500 Mo avant compression, avec le texte « jusqu'à une fois et demie cette taille en
mémoire » ; l'export « données seules » (sans les documents, T214) reste la parade. Une très grosse base (des dizaines
de milliers d'OT, un journal de plusieurs années) reste lourde à exporter, documents ou non.

**Ouverture par d'autres outils (T215).** Un vrai export de 2 091 Mo (5 entrées au-delà de 2 Go), un ZIP de 3 900 Mo
écrit dans la page par `ZipFlux.ecrivain` (40 entrées de 97,5 Mo, 18 au-delà de 2 Go) et un ZIP de 3 900 Mo de 400
entrées de 9,75 Mo (copie Python de l'écrivain, vérifiée à l'octet contre lui ; 189 entrées au-delà de 2 Go) : Python
`zipfile` (`testzip()`), `tar` de Windows (liste ; extraction de la première entrée et de la plus lointaine) et
« Extraire tout » de l'Explorateur (moteur ZIP du Shell de Windows) les ouvrent sans erreur : tous les fichiers, à
l'octet (SHA-256), en 31 à 40 s pour 2 Go et en 43 à 68 s pour 3,9 Go.
