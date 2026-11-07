# Fiche technique des fichiers CSV de Prévo

Document généré par `outils/generer_fiche_csv.py` d'après `js/schema.js` (et, pour la section 4, `js/modules/import-regles.js` ; pour la section 5, `serveur.py` et `js/modules/parametres.js`) : ne pas le modifier à la main.

Prévo range ses données dans **24 fichiers CSV** (format **version 3**), dans le dossier de données (`donnees/` à côté de `serveur.py`, ou le dossier choisi en mode dossier). Ils s'ouvrent et se modifient dans Excel. Le paramètre `version_schema` de `parametres.csv` indique la version du format.

## 1. Règles communes à tous les fichiers

- **Encodage** : UTF-8 avec BOM ; à la lecture, un fichier en Windows-1252 est aussi accepté (signalé).
- **Séparateur** : point-virgule `;` (une virgule est acceptée à la lecture si l'en-tête n'a aucun `;`).
- **Fins de ligne** : CRLF. **Première ligne** : les noms des colonnes, dans l'ordre ci-dessous ; les colonnes ajoutées à la main sont conservées et réécrites à la fin ; une colonne manquante prend sa valeur par défaut.
- **Guillemets** : une valeur est entre guillemets si elle contient `;`, `"`, un retour à la ligne ; un `"` s'écrit `""`.
- **Valeurs** : dates `AAAA-MM-JJ`, date-heure `AAAA-MM-JJ HH:MM`, nombres avec un point, booléens `1`/`0`. À la lecture, Prévo accepte aussi `JJ/MM/AAAA`, la virgule décimale, `oui`/`non`, `vrai`/`faux`.
- **Apostrophe de protection** : Excel abîme certaines valeurs de texte (`00123` devient `123`, `1/2` devient une date, `- joint` devient une formule). Prévo écrit ces valeurs précédées d'une apostrophe (`'00123`) et la retire à la lecture. Les colonnes marquées « toujours protégé » l'ont systématiquement.
- **Jamais de suppression** : une ligne n'est jamais effacée ; elle est désactivée (`actif` = `0`) ou annulée (statut `Annulé`). Toute modification faite par Prévo est inscrite dans `journal.csv`.
- **Excel et Prévo en même temps** : ne modifiez pas un fichier dans Excel pendant que quelqu'un enregistre dans Prévo ; fermez Excel avant.

## 2. Les types de colonnes

| Type | Contenu |
| --- | --- |
| `id` | identifiant de la ligne (voir le format de chaque fichier) |
| `texte` | texte sur une ligne |
| `texte_long` | texte sur plusieurs lignes (entre guillemets dans le fichier) |
| `entier` | nombre entier (`12`) |
| `decimal` | nombre à virgule, écrit avec un point (`7.5`) ; la virgule est acceptée à la lecture |
| `date` | date `AAAA-MM-JJ` |
| `date_heure` | date et heure `AAAA-MM-JJ HH:MM` |
| `booleen` | `1` (oui) ou `0` (non) |
| `choix` | une des valeurs de la liste fermée |
| `ref` | identifiant d'une ligne d'un autre fichier |
| `document` | nom d'un fichier du dossier `documents/` (photo, PDF…) ; en mode serveur, préfixé `AAAAMMJJ-HHMMSS-` (§5) |

## 3. Les 24 fichiers

| Fichier | Contenu | Identifiant |
| --- | --- | --- |
| `localisations.csv` | Arborescence des lieux : site, ateliers, lignes. | `LOC-NNNN` (ex. `LOC-0001`) |
| `equipements.csv` | Le parc : chaque machine ou sous-ensemble, sa criticité, sa consignation. | `EQ-NNNN` (ex. `EQ-0001`) |
| `demandes.csv` | Demandes d'intervention (DI) signalées par les demandeurs. | `DI-AAAA-NNNN` (numéro remis à 1 chaque année ; ex. `DI-2026-0042`) |
| `ordres_travail.csv` | Ordres de travail (OT) : correctifs, préventifs, réglementaires, améliorations. | `OT-AAAA-NNNN` (numéro remis à 1 chaque année ; ex. `OT-2026-0042`) |
| `ot_operations.csv` | Check-list d'un OT (copie de la gamme, cochée pendant l'intervention). | `OTO-NNNNNN` (ex. `OTO-000001`) |
| `ot_pieces.csv` | Pièces prévues pour un OT. | `OTP-NNNNNN` (ex. `OTP-000001`) |
| `ot_temps.csv` | Temps passés par technicien sur un OT. | `OTT-NNNNNN` (ex. `OTT-000001`) |
| `gammes.csv` | Gammes de maintenance préventive (par date, compteur ou seuil). | `GAM-NNNN` (ex. `GAM-0001`) |
| `gamme_operations.csv` | Opérations (check-list) de chaque gamme. | `GOP-NNNNNN` (ex. `GOP-000001`) |
| `articles.csv` | Articles du magasin (pièces de rechange, consommables). | `ART-NNNN` (ex. `ART-0001`) |
| `article_equipement.csv` | Lien entre articles et équipements (pièces d'une machine). | `AEQ-NNNNN` (ex. `AEQ-00001`) |
| `mouvements_stock.csv` | Mouvements du magasin : entrées, sorties, retours, inventaires. | `MVT-NNNNNN` (ex. `MVT-000001`) |
| `techniciens.csv` | Techniciens : capacité hebdomadaire, taux horaire. | `TEC-NNNN` (ex. `TEC-0001`) |
| `habilitations.csv` | Habilitations des techniciens et leurs échéances. | `HAB-NNNN` (ex. `HAB-0001`) |
| `compteurs.csv` | Compteurs (heures, cycles) et points de mesure des équipements. | `CPT-NNNN` (ex. `CPT-0001`) |
| `releves.csv` | Relevés des compteurs et des mesures. | `REL-NNNNNN` (ex. `REL-000001`) |
| `controles_reglementaires.csv` | Contrôles réglementaires périodiques (VGP, électricité…). | `CTR-NNNN` (ex. `CTR-0001`) |
| `codes_defaillance.csv` | Codes de défaillance : symptômes, causes, remèdes. | `CD-NNNN` (ex. `CD-0001`) |
| `fournisseurs.csv` | Fournisseurs du magasin. | `FOU-NNNN` (ex. `FOU-0001`) |
| `achats.csv` | Demandes d'achat et commandes. | `ACH-NNNN` (ex. `ACH-0001`) |
| `parametres.csv` | Réglages partagés de l'atelier (une ligne par clé). | saisi (la clé elle-même) |
| `journal.csv` | Journal des modifications (qui, quand, quoi) ; on n'y fait qu'ajouter. | `J-AAAAMMJJHHMMSS-XXXX` (horodatage puis 4 caractères tirés au hasard) |
| `wiki_pages.csv` | Pages du wiki de maintenance (format 3) : équipements, composants, modes de défaillance et savoir-faire ; seul le texte validé y est enregistré. | `WP-NNNN` (ex. `WP-0001`) |
| `wiki_journal.csv` | Journal du wiki (format 3) : OT en file, propositions de l'IA et leur décision, écritures à la main, contradictions tranchées. | `WJ-NNNNN` (ex. `WJ-00001`) |

### 3.1 `localisations.csv` — Localisations

Arborescence des lieux : site, ateliers, lignes.

- Identifiant : `LOC-NNNN` (ex. `LOC-0001`).

| Colonne | Libellé | Type | Obligatoire | Valeurs ou référence | Défaut | Remarques |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | Identifiant | `id` |  |  |  |  |
| `libelle` | Libellé | `texte` | oui |  |  | autres noms reconnus : nom, lieu, zone |
| `parent_id` | Localisation parente | `ref` |  | réf. `localisations.csv` |  |  |
| `type` | Type | `choix` | oui | `site`, `atelier`, `ligne` |  |  |

### 3.2 `equipements.csv` — Équipements

Le parc : chaque machine ou sous-ensemble, sa criticité, sa consignation.

- Identifiant : `EQ-NNNN` (ex. `EQ-0001`).

| Colonne | Libellé | Type | Obligatoire | Valeurs ou référence | Défaut | Remarques |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | Identifiant | `id` |  |  |  |  |
| `repere` | Repère | `texte` | oui |  |  | toujours protégé par une apostrophe ; autres noms reconnus : code machine, tag, référence machine, code équipement, n° machine, repère machine |
| `designation` | Désignation | `texte` | oui |  |  | autres noms reconnus : désignation, nom, machine, équipement, libellé, description machine |
| `localisation_id` | Localisation | `ref` |  | réf. `localisations.csv` |  | autres noms reconnus : localisation, atelier, ligne, emplacement, zone, site |
| `parent_id` | Équipement parent | `ref` |  | réf. `equipements.csv` |  | autres noms reconnus : parent, ensemble, machine mère |
| `marque` | Marque | `texte` |  |  |  | autres noms reconnus : fabricant, constructeur |
| `modele` | Modèle | `texte` |  |  |  | autres noms reconnus : modèle, type, référence constructeur |
| `num_serie` | Numéro de série | `texte` |  |  |  | toujours protégé par une apostrophe ; autres noms reconnus : n° de série, numéro de série, n° série, serial, série, sn |
| `date_mes` | Date de mise en service | `date` |  |  |  | autres noms reconnus : mise en service, date de mise en service, mes, date mes, année de mise en service |
| `criticite` | Criticité | `choix` |  | `A`, `B`, `C` | `B` | autres noms reconnus : criticité, classe, priorité machine |
| `statut` | Statut | `choix` |  | `en service`, `arrêt`, `rebut` | `en service` | autres noms reconnus : état, etat |
| `heures_fonct_jour` | Heures de fonctionnement par jour | `decimal` |  |  |  | autres noms reconnus : heures par jour, h/jour, heures de fonctionnement |
| `habilitation_requise` | Habilitation requise | `texte` |  |  |  | autres noms reconnus : habilitation, habilitations requises |
| `consignation` | Consignation | `texte_long` |  |  |  | autres noms reconnus : procédure de consignation, consignation énergies |
| `document` | Document | `document` |  |  |  |  |
| `actif` | Actif | `booleen` |  |  | `1` |  |
| `valeur_remplacement` | Valeur de remplacement (€ HT) | `decimal` |  |  |  | depuis le format 2 ; autres noms reconnus : valeur de remplacement, valeur à neuf, prix de remplacement |

### 3.3 `demandes.csv` — Demandes d'intervention

Demandes d'intervention (DI) signalées par les demandeurs.

- Identifiant : `DI-AAAA-NNNN` (numéro remis à 1 chaque année ; ex. `DI-2026-0042`).

| Colonne | Libellé | Type | Obligatoire | Valeurs ou référence | Défaut | Remarques |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | Identifiant | `id` |  |  |  |  |
| `date_heure` | Date et heure de la demande | `date_heure` |  |  |  |  |
| `demandeur` | Demandeur | `texte` |  |  |  |  |
| `equipement_id` | Équipement | `ref` | oui | réf. `equipements.csv` |  |  |
| `symptome` | Symptôme observé | `texte_long` | oui |  |  |  |
| `impact` | Impact | `choix` | oui | `sécurité`, `arrêt`, `dégradé`, `gêne` |  |  |
| `description` | Description | `texte_long` |  |  |  |  |
| `photo` | Photo | `document` |  |  |  |  |
| `statut` | Statut | `choix` |  | `Nouvelle`, `Acceptée`, `Regroupée`, `Différée`, `Refusée` | `Nouvelle` |  |
| `motif_decision` | Motif de la décision | `texte_long` |  |  |  |  |
| `date_decision` | Date de la décision | `date_heure` |  |  |  |  |
| `ot_id` | Ordre de travail lié | `ref` |  | réf. `ordres_travail.csv` |  |  |
| `symptome_code` | Code symptôme | `ref` |  | réf. `codes_defaillance.csv` (colonne `code`), famille = symptôme |  | depuis le format 2 |
| `ot_origine_id` | OT d'origine (préventif) | `ref` |  | réf. `ordres_travail.csv` |  | depuis le format 2 |

### 3.4 `ordres_travail.csv` — Ordres de travail

Ordres de travail (OT) : correctifs, préventifs, réglementaires, améliorations.

- Identifiant : `OT-AAAA-NNNN` (numéro remis à 1 chaque année ; ex. `OT-2026-0042`).

| Colonne | Libellé | Type | Obligatoire | Valeurs ou référence | Défaut | Remarques |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | Identifiant | `id` |  |  |  |  |
| `origine` | Origine | `choix` |  | `DI`, `préventif`, `urgence`, `manuel` |  |  |
| `di_id` | Demande d'intervention | `ref` |  | réf. `demandes.csv` |  |  |
| `gamme_id` | Gamme de préventif | `ref` |  | réf. `gammes.csv` |  |  |
| `equipement_id` | Équipement | `ref` | oui | réf. `equipements.csv` |  |  |
| `type` | Type | `choix` | oui | `correctif immédiat`, `correctif différé`, `préventif systématique`, `préventif conditionnel`, `amélioration`, `réglementaire` |  |  |
| `priorite` | Priorité | `choix` | oui | `P1`, `P2`, `P3`, `P4` |  |  |
| `statut` | Statut | `choix` | oui | `Créé`, `Préparé`, `Planifié`, `En cours`, `En attente`, `Clôturé techniquement`, `Clôturé administrativement`, `Annulé` | `Créé` |  |
| `motif_attente` | Motif de mise en attente | `texte_long` |  |  |  |  |
| `titre` | Titre | `texte` | oui |  |  |  |
| `travail_a_faire` | Travail à faire | `texte_long` |  |  |  |  |
| `consignes` | Consignes | `texte_long` |  |  |  |  |
| `date_creation` | Date de création | `date_heure` |  |  |  |  |
| `date_prevue` | Date prévue | `date` |  |  |  |  |
| `technicien_id` | Technicien | `ref` |  | réf. `techniciens.csv` |  |  |
| `temps_prevu_h` | Temps prévu (heures) | `decimal` |  |  |  |  |
| `date_debut` | Date de début | `date_heure` |  |  |  |  |
| `date_fin` | Date de fin | `date_heure` |  |  |  |  |
| `arret_production` | Arrêt de production | `booleen` |  |  | `0` |  |
| `duree_arret_h` | Durée d'arrêt (heures) | `decimal` |  |  |  |  |
| `symptome_code` | Code symptôme | `ref` |  | réf. `codes_defaillance.csv` (colonne `code`), famille = symptôme |  |  |
| `cause_code` | Code cause | `ref` |  | réf. `codes_defaillance.csv` (colonne `code`), famille = cause |  |  |
| `remede_code` | Code remède | `ref` |  | réf. `codes_defaillance.csv` (colonne `code`), famille = remède |  |  |
| `compte_rendu` | Compte rendu | `texte_long` |  |  |  |  |
| `remise_service` | Remis en service en sécurité | `booleen` |  |  | `0` |  |
| `cout_soustraitance` | Coût de sous-traitance | `decimal` |  |  |  |  |
| `date_cloture_tech` | Date de clôture technique | `date_heure` |  |  |  |  |
| `date_cloture_admin` | Date de clôture administrative | `date_heure` |  |  |  |  |
| `motif_annulation` | Motif d'annulation | `texte_long` |  |  |  |  |
| `ot_lie_id` | Ordre de travail lié | `ref` |  | réf. `ordres_travail.csv` |  |  |
| `anomalie_constatee` | Anomalie constatée | `booleen` |  |  | `0` | depuis le format 2 |
| `astuce` | Astuce pour la prochaine fois | `texte_long` |  |  |  | depuis le format 3 |

### 3.5 `ot_operations.csv` — Opérations d'ordre de travail

Check-list d'un OT (copie de la gamme, cochée pendant l'intervention).

- Identifiant : `OTO-NNNNNN` (ex. `OTO-000001`).

| Colonne | Libellé | Type | Obligatoire | Valeurs ou référence | Défaut | Remarques |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | Identifiant | `id` |  |  |  |  |
| `ot_id` | Ordre de travail | `ref` |  | réf. `ordres_travail.csv` |  |  |
| `ordre` | Ordre | `entier` |  |  |  |  |
| `operation` | Opération | `texte` |  |  |  |  |
| `valeur_attendue` | Valeur attendue | `texte` |  |  |  |  |
| `fait` | Fait | `booleen` |  |  | `0` |  |
| `valeur_mesuree` | Valeur mesurée | `texte` |  |  |  |  |

### 3.6 `ot_pieces.csv` — Pièces prévues d'ordre de travail

Pièces prévues pour un OT.

- Identifiant : `OTP-NNNNNN` (ex. `OTP-000001`).

| Colonne | Libellé | Type | Obligatoire | Valeurs ou référence | Défaut | Remarques |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | Identifiant | `id` |  |  |  |  |
| `ot_id` | Ordre de travail | `ref` |  | réf. `ordres_travail.csv` |  |  |
| `article_id` | Article | `ref` |  | réf. `articles.csv` |  |  |
| `quantite_prevue` | Quantité prévue | `decimal` |  |  |  |  |

### 3.7 `ot_temps.csv` — Temps passés sur ordre de travail

Temps passés par technicien sur un OT.

- Identifiant : `OTT-NNNNNN` (ex. `OTT-000001`).

| Colonne | Libellé | Type | Obligatoire | Valeurs ou référence | Défaut | Remarques |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | Identifiant | `id` |  |  |  |  |
| `ot_id` | Ordre de travail | `ref` |  | réf. `ordres_travail.csv` |  |  |
| `technicien_id` | Technicien | `ref` |  | réf. `techniciens.csv` |  |  |
| `date` | Date | `date` |  |  |  |  |
| `heures` | Heures | `decimal` |  |  |  |  |

### 3.8 `gammes.csv` — Gammes de préventif

Gammes de maintenance préventive (par date, compteur ou seuil).

- Identifiant : `GAM-NNNN` (ex. `GAM-0001`).

| Colonne | Libellé | Type | Obligatoire | Valeurs ou référence | Défaut | Remarques |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | Identifiant | `id` |  |  |  |  |
| `equipement_id` | Équipement | `ref` |  | réf. `equipements.csv` |  |  |
| `libelle` | Libellé | `texte` |  |  |  |  |
| `declencheur` | Déclencheur | `choix` |  | `date`, `compteur`, `seuil` | `date` |  |
| `periodicite_jours` | Périodicité (jours) | `entier` |  |  |  |  |
| `compteur_id` | Compteur | `ref` |  | réf. `compteurs.csv` |  |  |
| `periodicite_unites` | Périodicité (unités du compteur) | `decimal` |  |  |  |  |
| `seuil` | Seuil | `decimal` |  |  |  |  |
| `avance_jours` | Avance (jours) | `entier` |  |  |  |  |
| `derniere_realisation` | Dernière réalisation | `date` |  |  |  |  |
| `releve_derniere_realisation` | Relevé à la dernière réalisation | `decimal` |  |  |  |  |
| `prochaine_echeance` | Prochaine échéance | `date` |  |  |  |  |
| `temps_prevu_h` | Temps prévu (heures) | `decimal` |  |  |  |  |
| `consignes` | Consignes | `texte_long` |  |  |  |  |
| `actif` | Actif | `booleen` |  |  | `1` |  |

### 3.9 `gamme_operations.csv` — Opérations de gamme

Opérations (check-list) de chaque gamme.

- Identifiant : `GOP-NNNNNN` (ex. `GOP-000001`).

| Colonne | Libellé | Type | Obligatoire | Valeurs ou référence | Défaut | Remarques |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | Identifiant | `id` |  |  |  |  |
| `gamme_id` | Gamme | `ref` |  | réf. `gammes.csv` |  |  |
| `ordre` | Ordre | `entier` |  |  |  |  |
| `operation` | Opération | `texte` |  |  |  |  |
| `valeur_attendue` | Valeur attendue | `texte` |  |  |  |  |

### 3.10 `articles.csv` — Articles (pièces détachées)

Articles du magasin (pièces de rechange, consommables).

- Identifiant : `ART-NNNN` (ex. `ART-0001`).

| Colonne | Libellé | Type | Obligatoire | Valeurs ou référence | Défaut | Remarques |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | Identifiant | `id` |  |  |  |  |
| `reference` | Référence | `texte` | oui |  |  | toujours protégé par une apostrophe ; autres noms reconnus : référence, réf, ref, code article, code |
| `designation` | Désignation | `texte` | oui |  |  | autres noms reconnus : désignation, libellé, article, description |
| `fabricant` | Fabricant | `texte` |  |  |  | autres noms reconnus : marque, constructeur |
| `ref_fabricant` | Référence fabricant | `texte` |  |  |  | toujours protégé par une apostrophe ; autres noms reconnus : réf fabricant, réf. fabricant, référence constructeur, ref constructeur |
| `emplacement` | Emplacement | `texte` |  |  |  | autres noms reconnus : rayon, casier, étagère, localisation magasin |
| `unite` | Unité | `texte` |  |  |  | autres noms reconnus : unité, u |
| `stock` | Stock | `decimal` |  |  |  | autres noms reconnus : quantité en stock, qté stock, stock actuel |
| `stock_securite` | Stock de sécurité | `decimal` |  |  |  | autres noms reconnus : stock mini, stock minimum |
| `point_commande` | Point de commande | `decimal` |  |  |  | autres noms reconnus : seuil de commande |
| `qte_commande` | Quantité à commander | `decimal` |  |  |  | autres noms reconnus : quantité de commande, qté commande |
| `delai_jours` | Délai d'approvisionnement (jours) | `entier` |  |  |  | autres noms reconnus : délai, délai livraison |
| `prix_unitaire` | Prix unitaire | `decimal` |  |  |  | autres noms reconnus : prix, pu, prix achat, prix d'achat |
| `fournisseur_id` | Fournisseur | `ref` |  | réf. `fournisseurs.csv` |  | autres noms reconnus : fournisseur |
| `critique` | Article critique | `booleen` |  |  | `0` |  |
| `actif` | Actif | `booleen` |  |  | `1` |  |

### 3.11 `article_equipement.csv` — Articles par équipement

Lien entre articles et équipements (pièces d'une machine).

- Identifiant : `AEQ-NNNNN` (ex. `AEQ-00001`).

| Colonne | Libellé | Type | Obligatoire | Valeurs ou référence | Défaut | Remarques |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | Identifiant | `id` |  |  |  |  |
| `article_id` | Article | `ref` |  | réf. `articles.csv` |  |  |
| `equipement_id` | Équipement | `ref` |  | réf. `equipements.csv` |  |  |
| `quantite` | Quantité | `decimal` |  |  |  |  |

### 3.12 `mouvements_stock.csv` — Mouvements de stock

Mouvements du magasin : entrées, sorties, retours, inventaires.

- Identifiant : `MVT-NNNNNN` (ex. `MVT-000001`).

| Colonne | Libellé | Type | Obligatoire | Valeurs ou référence | Défaut | Remarques |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | Identifiant | `id` |  |  |  |  |
| `date` | Date et heure | `date_heure` |  |  |  |  |
| `article_id` | Article | `ref` |  | réf. `articles.csv` |  |  |
| `type` | Type | `choix` |  | `entrée`, `sortie`, `inventaire`, `retour` |  |  |
| `quantite` | Quantité | `decimal` |  |  |  |  |
| `ot_id` | Ordre de travail | `ref` |  | réf. `ordres_travail.csv` |  |  |
| `utilisateur` | Utilisateur | `texte` |  |  |  |  |
| `commentaire` | Commentaire | `texte_long` |  |  |  |  |

### 3.13 `techniciens.csv` — Techniciens

Techniciens : capacité hebdomadaire, taux horaire.

- Identifiant : `TEC-NNNN` (ex. `TEC-0001`).

| Colonne | Libellé | Type | Obligatoire | Valeurs ou référence | Défaut | Remarques |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | Identifiant | `id` |  |  |  |  |
| `nom` | Nom | `texte` | oui |  |  | autres noms reconnus : nom de famille, technicien |
| `prenom` | Prénom | `texte` |  |  |  | autres noms reconnus : prénom |
| `metier` | Métier | `texte` |  |  |  | autres noms reconnus : métier, fonction, spécialité, poste |
| `taux_horaire` | Taux horaire | `decimal` |  |  |  | autres noms reconnus : coût horaire, tarif horaire, €/h |
| `capacite_h_semaine` | Capacité (heures par semaine) | `decimal` |  |  |  | autres noms reconnus : capacité, heures par semaine, h/semaine |
| `actif` | Actif | `booleen` |  |  | `1` |  |

### 3.14 `habilitations.csv` — Habilitations

Habilitations des techniciens et leurs échéances.

- Identifiant : `HAB-NNNN` (ex. `HAB-0001`).

| Colonne | Libellé | Type | Obligatoire | Valeurs ou référence | Défaut | Remarques |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | Identifiant | `id` |  |  |  |  |
| `technicien_id` | Technicien | `ref` |  | réf. `techniciens.csv` |  |  |
| `intitule` | Intitulé | `texte` |  |  |  | autres noms reconnus : habilitation, intitulé, titre |
| `date_obtention` | Date d'obtention | `date` |  |  |  | autres noms reconnus : obtenue le, date obtention |
| `date_echeance` | Date d'échéance | `date` |  |  |  | autres noms reconnus : échéance, valable jusqu'au, date d'expiration, expiration |

### 3.15 `compteurs.csv` — Compteurs

Compteurs (heures, cycles) et points de mesure des équipements.

- Identifiant : `CPT-NNNN` (ex. `CPT-0001`).

| Colonne | Libellé | Type | Obligatoire | Valeurs ou référence | Défaut | Remarques |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | Identifiant | `id` |  |  |  |  |
| `equipement_id` | Équipement | `ref` |  | réf. `equipements.csv` |  |  |
| `libelle` | Libellé | `texte` |  |  |  |  |
| `unite` | Unité | `texte` |  |  |  |  |

### 3.16 `releves.csv` — Relevés de compteur

Relevés des compteurs et des mesures.

- Identifiant : `REL-NNNNNN` (ex. `REL-000001`).

| Colonne | Libellé | Type | Obligatoire | Valeurs ou référence | Défaut | Remarques |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | Identifiant | `id` |  |  |  |  |
| `compteur_id` | Compteur | `ref` |  | réf. `compteurs.csv` |  |  |
| `date` | Date | `date` |  |  |  |  |
| `valeur` | Valeur | `decimal` |  |  |  |  |
| `utilisateur` | Utilisateur | `texte` |  |  |  |  |

### 3.17 `controles_reglementaires.csv` — Contrôles réglementaires

Contrôles réglementaires périodiques (VGP, électricité…).

- Identifiant : `CTR-NNNN` (ex. `CTR-0001`).

| Colonne | Libellé | Type | Obligatoire | Valeurs ou référence | Défaut | Remarques |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | Identifiant | `id` |  |  |  |  |
| `equipement_id` | Équipement | `ref` |  | réf. `equipements.csv` |  |  |
| `nature` | Nature du contrôle | `texte` |  |  |  |  |
| `texte_reference` | Texte de référence | `texte` |  |  |  |  |
| `periodicite_mois` | Périodicité (mois) | `entier` |  |  |  |  |
| `organisme` | Organisme de contrôle | `texte` |  |  |  |  |
| `derniere_date` | Date du dernier contrôle | `date` |  |  |  |  |
| `prochaine_date` | Date du prochain contrôle | `date` |  |  |  |  |
| `rapport` | Rapport | `document` |  |  |  |  |
| `observations` | Observations | `texte_long` |  |  |  |  |
| `observations_levees` | Observations levées | `booleen` |  |  | `0` |  |

### 3.18 `codes_defaillance.csv` — Codes de défaillance

Codes de défaillance : symptômes, causes, remèdes.

- Identifiant : `CD-NNNN` (ex. `CD-0001`).

| Colonne | Libellé | Type | Obligatoire | Valeurs ou référence | Défaut | Remarques |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | Identifiant | `id` |  |  |  |  |
| `famille` | Famille | `choix` | oui | `symptôme`, `cause`, `remède` |  |  |
| `code` | Code | `texte` | oui |  |  |  |
| `libelle` | Libellé | `texte` | oui |  |  |  |

### 3.19 `fournisseurs.csv` — Fournisseurs

Fournisseurs du magasin.

- Identifiant : `FOU-NNNN` (ex. `FOU-0001`).

| Colonne | Libellé | Type | Obligatoire | Valeurs ou référence | Défaut | Remarques |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | Identifiant | `id` |  |  |  |  |
| `nom` | Nom | `texte` |  |  |  | autres noms reconnus : fournisseur, raison sociale, société |
| `contact` | Contact | `texte` |  |  |  | autres noms reconnus : interlocuteur, nom du contact |
| `telephone` | Téléphone | `texte` |  |  |  | toujours protégé par une apostrophe ; autres noms reconnus : téléphone, tél, tel, portable |
| `email` | E-mail | `texte` |  |  |  | autres noms reconnus : e-mail, mail, courriel, adresse mail |

### 3.20 `achats.csv` — Achats

Demandes d'achat et commandes.

- Identifiant : `ACH-NNNN` (ex. `ACH-0001`).

| Colonne | Libellé | Type | Obligatoire | Valeurs ou référence | Défaut | Remarques |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | Identifiant | `id` |  |  |  |  |
| `date` | Date | `date` |  |  |  |  |
| `article_id` | Article | `ref` |  | réf. `articles.csv` |  |  |
| `fournisseur_id` | Fournisseur | `ref` |  | réf. `fournisseurs.csv` |  |  |
| `quantite` | Quantité | `decimal` |  |  |  |  |
| `prix_unitaire` | Prix unitaire | `decimal` |  |  |  |  |
| `statut` | Statut | `choix` |  | `demandée`, `commandée`, `reçue` | `demandée` |  |
| `date_reception` | Date de réception | `date` |  |  |  |  |

### 3.21 `parametres.csv` — Paramètres

Réglages partagés de l'atelier (une ligne par clé).

- Identifiant : saisi (la clé elle-même).

| Colonne | Libellé | Type | Obligatoire | Valeurs ou référence | Défaut | Remarques |
| --- | --- | --- | --- | --- | --- | --- |
| `cle` | Clé | `id` |  |  |  |  |
| `valeur` | Valeur | `texte` |  |  |  |  |

### 3.22 `journal.csv` — Journal des modifications

Journal des modifications (qui, quand, quoi) ; on n'y fait qu'ajouter.

- Identifiant : `J-AAAAMMJJHHMMSS-XXXX` (horodatage puis 4 caractères tirés au hasard).
- Fichier écrit par ajout seulement : les lignes existantes ne sont jamais réécrites.

| Colonne | Libellé | Type | Obligatoire | Valeurs ou référence | Défaut | Remarques |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | Identifiant | `id` |  |  |  |  |
| `date_heure` | Date et heure | `date_heure` |  |  |  |  |
| `poste` | Poste | `texte` |  |  |  |  |
| `profil` | Profil | `texte` |  |  |  |  |
| `table` | Table | `texte` |  |  |  |  |
| `id_ligne` | Identifiant de la ligne | `texte` |  |  |  |  |
| `action` | Action | `texte` |  |  |  |  |

### 3.23 `wiki_pages.csv` — Pages du wiki

Pages du wiki de maintenance (format 3) : équipements, composants, modes de défaillance et savoir-faire ; seul le texte validé y est enregistré.

- Identifiant : `WP-NNNN` (ex. `WP-0001`).

| Colonne | Libellé | Type | Obligatoire | Valeurs ou référence | Défaut | Remarques |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | Identifiant | `id` |  |  |  |  |
| `type` | Type | `choix` | oui | `équipement`, `composant`, `savoir-faire` |  |  |
| `titre` | Titre | `texte` | oui |  |  |  |
| `cle` | Clé (titre comparable) | `texte` |  |  |  |  |
| `equipement_id` | Équipement | `ref` |  | réf. `equipements.csv` |  |  |
| `article_id` | Article | `ref` |  | réf. `articles.csv` |  |  |
| `cause_code` | Code cause | `ref` |  | réf. `codes_defaillance.csv` (colonne `code`), famille = cause |  |  |
| `rattache_a` | Rattaché à la page | `ref` |  | réf. `wiki_pages.csv` |  |  |
| `texte` | Texte | `texte_long` |  |  |  |  |
| `ot_cites` | OT cités | `texte` |  |  |  |  |
| `liens` | Pages liées | `texte` |  |  |  |  |
| `version` | Version | `entier` |  |  | `0` |  |
| `origine` | Origine | `choix` |  | `IA`, `manuel`, `IA et manuel` |  |  |
| `modele` | Modèle | `texte` |  |  |  |  |
| `derniere_entree` | Dernière entrée appliquée | `ref` |  | réf. `wiki_journal.csv` |  |  |
| `valide_par` | Validé par | `texte` |  |  |  |  |
| `valide_le` | Validé le | `date_heure` |  |  |  |  |
| `cree_le` | Créée le | `date_heure` |  |  |  |  |
| `modifie_le` | Modifiée le | `date_heure` |  |  |  |  |
| `statut` | Statut | `choix` |  | `active`, `archivée` | `active` |  |

### 3.24 `wiki_journal.csv` — Journal du wiki

Journal du wiki (format 3) : OT en file, propositions de l'IA et leur décision, écritures à la main, contradictions tranchées.

- Identifiant : `WJ-NNNNN` (ex. `WJ-00001`).

| Colonne | Libellé | Type | Obligatoire | Valeurs ou référence | Défaut | Remarques |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | Identifiant | `id` |  |  |  |  |
| `nature` | Nature | `choix` | oui | `ingestion`, `manuel`, `décision` |  |  |
| `ot_id` | Ordre de travail | `ref` |  | réf. `ordres_travail.csv` |  |  |
| `date_intervention` | Date d'intervention | `date_heure` |  |  |  |  |
| `statut` | Statut | `choix` | oui | `en file`, `à valider`, `validée`, `rejetée`, `à refaire`, `refusée`, `rien à ajouter`, `appliquée` |  |  |
| `anterieure` | Intervention antérieure | `booleen` |  |  | `0` |  |
| `ordre` | Rang de traitement | `entier` |  |  |  |  |
| `pages` | Pages concernées | `texte` |  |  |  |  |
| `changements` | Changements | `texte_long` |  |  |  |  |
| `contradictions` | Contradictions | `texte_long` |  |  |  |  |
| `raisons` | Raisons du refus | `texte_long` |  |  |  |  |
| `modele` | Modèle | `texte` |  |  |  |  |
| `essais` | Essais | `entier` |  |  | `0` |  |
| `cree_le` | Créée le | `date_heure` |  |  |  |  |
| `traite_le` | Traitée le | `date_heure` |  |  |  |  |
| `decide_par` | Décidé par | `texte` |  |  |  |  |
| `decide_le` | Décidé le | `date_heure` |  |  |  |  |
| `motif` | Motif | `texte_long` |  |  |  |  |

## 4. Import depuis un tableur

L'écran « Importer des données » (responsable, depuis Paramètres) reprend des données existantes depuis un fichier `.csv`, `.tsv`, `.txt`, `.xlsx`, `.xlsm`, `.xls` ou `.ods`, ou depuis des cellules collées : 10 Mo, 20 000 lignes et 200 colonnes au plus. Rien n'est écrit avant le bouton « Importer » ; une sauvegarde `AAAA-MM-JJ_HHMMSS_avant-import` est faite juste avant (modes serveur et dossier), et l'import peut être annulé.

- **Titres reconnus** : un titre de colonne est reconnu, sans tenir compte des majuscules, des accents ni de la ponctuation, s'il est égal au titre du modèle, au nom de la colonne CSV ou à l'un des autres titres listés ci-dessous ; un titre seulement proche est proposé « à confirmer ».
- **Clé naturelle** : les identifiants de Prévo ne sont jamais pris dans le fichier ; une fiche est reconnue par sa clé (tableau ci-dessous). Une fiche déjà présente est complétée et mise à jour, pour les seules colonnes importées et non vides (au choix, à chaque import) : une cellule vide n'efface rien. L'historique ne modifie jamais un OT existant.
- **Valeurs** : lues comme dans un CSV de Prévo (§1) ; une valeur illisible ou hors de la liste fermée refuse la ligne, avec sa raison. Une valeur n'est jamais inventée.
- **Obligatoire** : sans cette colonne, une ligne qui crée une fiche est refusée. **Clé** : partie de la clé naturelle ; vide, elle refuse la ligne.
- **Modèles** : pour chaque type, l'assistant propose un modèle `.xlsx` (avec une feuille « Aide ») et `.csv`, avec ces titres et une ligne d'exemple.

| Type | Fichiers écrits | Reconnu par (clé naturelle) |
| --- | --- | --- |
| Localisations | `localisations.csv` | Chemin |
| Équipements | `localisations.csv`, `equipements.csv` | Repère |
| Articles (pièces détachées) | `fournisseurs.csv`, `articles.csv`, `mouvements_stock.csv` | Référence |
| Fournisseurs | `fournisseurs.csv` | Nom |
| Techniciens | `techniciens.csv` | Nom + Prénom |
| Habilitations | `habilitations.csv` | Technicien + Intitulé |
| Codes de défaillance | `codes_defaillance.csv` | Famille + Code |
| Compteurs | `compteurs.csv` | Équipement + Libellé |
| Contrôles réglementaires | `controles_reglementaires.csv` | Équipement + Nature du contrôle |
| Gammes de préventif | `gammes.csv`, `gamme_operations.csv` | Équipement + Libellé |
| Historique des interventions | `ordres_travail.csv`, `ot_temps.csv` | Ancien n° d'OT ; sans lui, même équipement, même date de création (à la minute) et même titre : doublon supposé, montré dans l'aperçu |

### 4.1 Localisations

Sites, ateliers et lignes : un chemin « Site > Atelier > Ligne » par ligne (séparateur >, / ou \\) ; le type se déduit du niveau.

| Titre de la colonne | Écrit dans | Obligatoire | Autres titres reconnus | Remarques |
| --- | --- | --- | --- | --- |
| Chemin | `localisations.csv` | oui, clé | chemin, chemin de localisation, localisation, emplacement, lieu, zone, libellé, nom | « Site > Atelier > Ligne » (séparateur `>`, `/` ou `\`) ; type déduit du niveau ; niveaux manquants créés |
| Type | `localisations.csv` : `type` |  | niveau |  |

### 4.2 Équipements

Le parc : un équipement par ligne, reconnu par son repère ; localisation par son chemin (« Site > Atelier > Ligne ») ou une colonne par niveau ; équipement parent par son repère.

| Titre de la colonne | Écrit dans | Obligatoire | Autres titres reconnus | Remarques |
| --- | --- | --- | --- | --- |
| Repère | `equipements.csv` : `repere` | oui, clé | code machine, tag, référence machine, code équipement, n° machine, repère machine |  |
| Désignation | `equipements.csv` : `designation` | oui | désignation, nom, machine, équipement, libellé, description machine |  |
| Localisation | `equipements.csv` : `localisation_id` |  | chemin, chemin de localisation, localisation, emplacement, lieu, zone | chemin « Site > Atelier > Ligne » ; localisation créée si elle manque |
| Site | `equipements.csv` : `localisation_id` |  | usine | une colonne par niveau, au lieu du chemin ; créé s'il manque |
| Atelier | `equipements.csv` : `localisation_id` |  | secteur | une colonne par niveau, au lieu du chemin ; créé s'il manque |
| Ligne | `equipements.csv` : `localisation_id` |  | ligne de production, îlot | une colonne par niveau, au lieu du chemin ; créée si elle manque |
| Équipement parent | `equipements.csv` : `parent_id` |  | parent, repère parent, repère du parent, ensemble, machine mère | repère d'un équipement de Prévo ou du même fichier |
| Marque | `equipements.csv` : `marque` |  | fabricant, constructeur |  |
| Modèle | `equipements.csv` : `modele` |  | modèle, type, référence constructeur |  |
| Numéro de série | `equipements.csv` : `num_serie` |  | n° de série, numéro de série, n° série, serial, série, sn |  |
| Date de mise en service | `equipements.csv` : `date_mes` |  | mise en service, date de mise en service, mes, date mes, année de mise en service |  |
| Criticité | `equipements.csv` : `criticite` |  | criticité, classe, priorité machine, classe de criticité |  |
| Statut | `equipements.csv` : `statut` |  | état, etat |  |
| Heures de fonctionnement par jour | `equipements.csv` : `heures_fonct_jour` |  | heures par jour, h/jour, heures de fonctionnement |  |
| Habilitation requise | `equipements.csv` : `habilitation_requise` |  | habilitation, habilitations requises |  |
| Consignation | `equipements.csv` : `consignation` |  | procédure de consignation, consignation énergies |  |
| Actif | `equipements.csv` : `actif` |  | en activité |  |
| Valeur de remplacement (€ HT) | `equipements.csv` : `valeur_remplacement` |  | valeur de remplacement, valeur à neuf, prix de remplacement |  |

### 4.3 Articles (pièces détachées)

Le magasin : un article par ligne, reconnu par sa référence ; fournisseur par son nom (créé s'il manque) ; le stock initial devient un inventaire.

| Titre de la colonne | Écrit dans | Obligatoire | Autres titres reconnus | Remarques |
| --- | --- | --- | --- | --- |
| Référence | `articles.csv` : `reference` | oui, clé | référence, réf, ref, code article, code |  |
| Désignation | `articles.csv` : `designation` | oui | désignation, libellé, article, description |  |
| Fabricant | `articles.csv` : `fabricant` |  | marque, constructeur |  |
| Référence fabricant | `articles.csv` : `ref_fabricant` |  | réf fabricant, réf. fabricant, référence constructeur, ref constructeur |  |
| Emplacement | `articles.csv` : `emplacement` |  | rayon, casier, étagère, localisation magasin |  |
| Unité | `articles.csv` : `unite` |  | unité, u |  |
| Stock initial | `mouvements_stock.csv` |  | stock, quantité en stock, qté stock, stock actuel, quantité, qté | devient un mouvement « inventaire » ; le stock affiché est celui du fichier |
| Stock de sécurité | `articles.csv` : `stock_securite` |  | stock mini, stock minimum |  |
| Point de commande | `articles.csv` : `point_commande` |  | seuil de commande |  |
| Quantité à commander | `articles.csv` : `qte_commande` |  | quantité de commande, qté commande |  |
| Délai d'approvisionnement (jours) | `articles.csv` : `delai_jours` |  | délai, délai livraison |  |
| Prix unitaire | `articles.csv` : `prix_unitaire` |  | prix, pu, prix achat, prix d'achat |  |
| Fournisseur | `articles.csv` : `fournisseur_id` |  | nom du fournisseur, fournisseur principal | nom du fournisseur ; créé s'il manque |
| Article critique | `articles.csv` : `critique` |  | critique, pièce critique |  |
| Actif | `articles.csv` : `actif` |  |  |  |

### 4.4 Fournisseurs

Un fournisseur par ligne, reconnu par son nom.

| Titre de la colonne | Écrit dans | Obligatoire | Autres titres reconnus | Remarques |
| --- | --- | --- | --- | --- |
| Nom | `fournisseurs.csv` : `nom` | oui, clé | fournisseur, raison sociale, société |  |
| Contact | `fournisseurs.csv` : `contact` |  | interlocuteur, nom du contact |  |
| Téléphone | `fournisseurs.csv` : `telephone` |  | téléphone, tél, tel, portable |  |
| E-mail | `fournisseurs.csv` : `email` |  | e-mail, mail, courriel, adresse mail |  |

### 4.5 Techniciens

Un technicien par ligne, reconnu par son nom et son prénom.

| Titre de la colonne | Écrit dans | Obligatoire | Autres titres reconnus | Remarques |
| --- | --- | --- | --- | --- |
| Nom | `techniciens.csv` : `nom` | oui, clé | nom de famille, technicien |  |
| Prénom | `techniciens.csv` : `prenom` | clé | prénom |  |
| Métier | `techniciens.csv` : `metier` |  | métier, fonction, spécialité, poste |  |
| Taux horaire | `techniciens.csv` : `taux_horaire` |  | coût horaire, tarif horaire, €/h |  |
| Capacité (heures par semaine) | `techniciens.csv` : `capacite_h_semaine` |  | capacité, heures par semaine, h/semaine |  |
| Actif | `techniciens.csv` : `actif` |  |  |  |

### 4.6 Habilitations

Une habilitation par ligne : technicien (« Prénom Nom » ou « Nom Prénom », déjà dans Prévo) et intitulé.

| Titre de la colonne | Écrit dans | Obligatoire | Autres titres reconnus | Remarques |
| --- | --- | --- | --- | --- |
| Technicien | `habilitations.csv` : `technicien_id` | oui, clé | nom du technicien, intervenant, salarié, prénom nom, nom prénom, nom | « Prénom Nom », « Nom Prénom » ou nom seul s'il est unique ; doit exister |
| Intitulé | `habilitations.csv` : `intitule` | oui, clé | habilitation, intitulé, titre |  |
| Date d'obtention | `habilitations.csv` : `date_obtention` |  | obtenue le, date obtention |  |
| Date d'échéance | `habilitations.csv` : `date_echeance` |  | échéance, valable jusqu'au, date d'expiration, expiration |  |

### 4.7 Codes de défaillance

Symptômes, causes et remèdes : un code par ligne, reconnu par sa famille et son code.

| Titre de la colonne | Écrit dans | Obligatoire | Autres titres reconnus | Remarques |
| --- | --- | --- | --- | --- |
| Famille | `codes_defaillance.csv` : `famille` | oui, clé | famille de code, catégorie |  |
| Code | `codes_defaillance.csv` : `code` | oui, clé | code défaillance, n° de code |  |
| Libellé | `codes_defaillance.csv` : `libelle` | oui | description, désignation, intitulé |  |

### 4.8 Compteurs

Un compteur par ligne : équipement (repère, déjà dans Prévo) et libellé.

| Titre de la colonne | Écrit dans | Obligatoire | Autres titres reconnus | Remarques |
| --- | --- | --- | --- | --- |
| Équipement | `compteurs.csv` : `equipement_id` | oui, clé | équipement (repère), repère, repère équipement, machine, code machine, tag | repère d'un équipement de Prévo |
| Libellé | `compteurs.csv` : `libelle` | oui, clé | compteur, nom du compteur |  |
| Unité | `compteurs.csv` : `unite` |  | unité de mesure |  |

### 4.9 Contrôles réglementaires

Un contrôle par ligne : équipement (repère, déjà dans Prévo) et nature du contrôle.

| Titre de la colonne | Écrit dans | Obligatoire | Autres titres reconnus | Remarques |
| --- | --- | --- | --- | --- |
| Équipement | `controles_reglementaires.csv` : `equipement_id` | oui, clé | équipement (repère), repère, repère équipement, machine, code machine, tag | repère d'un équipement de Prévo |
| Nature du contrôle | `controles_reglementaires.csv` : `nature` | oui, clé | nature, contrôle, intitulé, type de contrôle, vérification |  |
| Texte de référence | `controles_reglementaires.csv` : `texte_reference` |  | référence réglementaire, réglementation, texte |  |
| Périodicité (mois) | `controles_reglementaires.csv` : `periodicite_mois` |  | périodicité, périodicité mois, fréquence, fréquence mois |  |
| Organisme de contrôle | `controles_reglementaires.csv` : `organisme` |  | organisme, prestataire, bureau de contrôle |  |
| Date du dernier contrôle | `controles_reglementaires.csv` : `derniere_date` |  | dernier contrôle, fait le, réalisé le |  |
| Date du prochain contrôle | `controles_reglementaires.csv` : `prochaine_date` |  | prochain contrôle, échéance, à faire le |  |
| Observations | `controles_reglementaires.csv` : `observations` |  | remarques, réserves |  |
| Observations levées | `controles_reglementaires.csv` : `observations_levees` |  | réserves levées, levée |  |

### 4.10 Gammes de préventif

Une gamme par équipement et libellé ; opérations : une ligne par opération (gamme répétée) ou une colonne d'opérations séparées par « ; ».

| Titre de la colonne | Écrit dans | Obligatoire | Autres titres reconnus | Remarques |
| --- | --- | --- | --- | --- |
| Équipement | `gammes.csv` : `equipement_id` | oui, clé | équipement (repère), repère, repère équipement, machine, code machine, tag | repère d'un équipement de Prévo |
| Libellé | `gammes.csv` : `libelle` | oui, clé | gamme, nom de la gamme, intitulé |  |
| Déclencheur | `gammes.csv` : `declencheur` |  | type de déclenchement |  |
| Périodicité (jours) | `gammes.csv` : `periodicite_jours` |  | périodicité, périodicité jours, fréquence, fréquence jours |  |
| Compteur | `gammes.csv` : `compteur_id` |  | compteur associé | libellé d'un compteur du même équipement |
| Périodicité (unités du compteur) | `gammes.csv` : `periodicite_unites` |  | périodicité compteur, périodicité unités |  |
| Seuil | `gammes.csv` : `seuil` |  |  |  |
| Avance (jours) | `gammes.csv` : `avance_jours` |  | avance |  |
| Dernière réalisation | `gammes.csv` : `derniere_realisation` |  | dernière visite, fait le |  |
| Relevé à la dernière réalisation | `gammes.csv` : `releve_derniere_realisation` |  |  |  |
| Prochaine échéance | `gammes.csv` : `prochaine_echeance` |  | échéance, prochaine visite |  |
| Temps prévu (heures) | `gammes.csv` : `temps_prevu_h` |  | temps prévu, durée, durée prévue |  |
| Consignes | `gammes.csv` : `consignes` |  | consignes de sécurité |  |
| Actif | `gammes.csv` : `actif` |  |  |  |
| Opérations | `gamme_operations.csv` |  | opération, tâche, tâches, liste des opérations, travail à faire | une ligne par opération (gamme répétée) ou opérations séparées par « ; » |
| Valeur attendue | `gamme_operations.csv` |  | valeurs attendues, critère, attendu | dans l'ordre des opérations, séparées par « ; » |

### 4.11 Historique des interventions

Les interventions passées d'une autre GMAO : chacune devient un OT clôturé ; l'ancien numéro est gardé dans le compte rendu.

| Titre de la colonne | Écrit dans | Obligatoire | Autres titres reconnus | Remarques |
| --- | --- | --- | --- | --- |
| Ancien n° d'OT | `ordres_travail.csv` | clé | n° ot, n° d'ot, numéro d'ot, numéro ot, ancien numéro, n° intervention, numéro intervention, n° bon, bon de travail | écrit en tête du compte rendu (« Ancien n° : … ») ; sert à repérer les doublons |
| Équipement | `ordres_travail.csv` : `equipement_id` | oui | équipement (repère), repère, repère équipement, machine, code machine, tag | repère d'un équipement de Prévo |
| Type | `ordres_travail.csv` : `type` |  | type d'intervention, nature, nature de l'intervention | absent : « correctif différé », signalé ; inconnu : ligne refusée |
| Priorité | `ordres_travail.csv` : `priorite` |  | priorité, urgence | absente : « P3 », signalée |
| Titre | `ordres_travail.csv` : `titre` |  | objet, intitulé, libellé, désignation | absent : début du compte rendu |
| Compte rendu | `ordres_travail.csv` : `compte_rendu` |  | compte-rendu, commentaire, travaux réalisés, description, observations, rapport |  |
| Date de création | `ordres_travail.csv` : `date_creation` |  | date, date de la demande, date demande, créé le | absente : date de début ; ni l'une ni l'autre : ligne refusée |
| Date de début | `ordres_travail.csv` : `date_debut` |  | début, date intervention, date d'intervention |  |
| Date de fin | `ordres_travail.csv` : `date_fin` |  | fin, terminé le, date de clôture | absente : date de début |
| Arrêt de production | `ordres_travail.csv` : `arret_production` |  | arrêt, arrêt prod, arrêt production | absent : « oui » si une durée d'arrêt non nulle est donnée |
| Durée d'arrêt (heures) | `ordres_travail.csv` : `duree_arret_h` |  | durée d'arrêt, durée arrêt, temps d'arrêt, heures d'arrêt | absente : laissée vide, jamais 0 |
| Code symptôme | `ordres_travail.csv` : `symptome_code` |  | symptôme | code ou libellé de la famille ; jamais créé (vide et signalé s'il est inconnu) |
| Code cause | `ordres_travail.csv` : `cause_code` |  | cause | code ou libellé de la famille ; jamais créé (vide et signalé s'il est inconnu) |
| Code remède | `ordres_travail.csv` : `remede_code` |  | remède, action corrective | code ou libellé de la famille ; jamais créé (vide et signalé s'il est inconnu) |
| Technicien | `ordres_travail.csv` : `technicien_id` |  | intervenant, réalisé par, nom du technicien | par son nom ; vide et signalé s'il est introuvable |
| Temps passé (heures) | `ot_temps.csv` |  | temps passé, heures, durée intervention, temps, temps (h), temps passé (h), main d'oeuvre | une ligne de `ot_temps.csv` (technicien de l'OT) |
| Coût de sous-traitance | `ordres_travail.csv` : `cout_soustraitance` |  | sous-traitance, coût sous-traitance, coût externe |  |

## 5. Prévo 2 : accès et installation

Ce que la version 2 (lot 7) change pour qui ouvre le dossier des données. Le format des fichiers CSV ne change pas. Le détail pour l'informaticien est dans `docs/INSTALLATION.md` (dépôt).

### 5.1 Le dossier `acces/` (mode serveur)

`acces/` range les fichiers du serveur pour les comptes et les appareils : `comptes.json` (empreintes des mots de passe, jamais les mots de passe), `sessions.json`, `appareils.json`, `journal-acces.csv`, et le certificat de l'atelier (`certificat.pem`, `cle.pem`, dossier `autorite/`).

- **Jamais à modifier à la main** (Excel compris) : le serveur seul les lit et les écrit. Ne les joignez jamais à un signalement.
- **Jamais servis** : ni par l'API des tables, ni dans l'export ZIP. Seul le journal des connexions sort, quand le responsable l'exporte (Équipe › Accès).
- **Sauvegardes** : les sauvegardes du serveur copient les fichiers de `acces/` (pas le dossier `autorite/`), sauf `sessions.json` (une session ne se restaure jamais) et `cle.pem` (la clé privée du certificat de l'atelier ne quitte pas le PC ; Prévo la refabrique au démarrage si elle manque) ; une restauration ne les remet jamais en place.
- **`journal-acces.csv`**, le journal des connexions, suit les règles de la section 1 (UTF-8 avec BOM, `;`, CRLF, apostrophe de protection). Colonnes : `date`, `qui`, `adresse`, `agent`, `resultat`, `tailscale`. `date` est écrite `AAAA-MM-JJTHH:MM:SS` ; `resultat` vaut `connexion`, `echec`, `bloque`, `deconnexion`, `appareil`, `invitation`, `revocation`, `reinitialisation`, `creation`, `modification`, `langue` ; `tailscale` porte le compte Tailscale d'une session venue par `tailscale serve`. Les lignes de plus de 366 jours sont effacées. Le responsable l'exporte depuis Équipe › Accès.

À côté, dans le dossier des données : `installation.json` (brouillon de l'assistant d'installation, supprimé à la fin), `journal-serveur.log` (journal du serveur), `copie-externe.json` (état de la copie externe des sauvegardes) et `derniere-version.json` (version de Prévo qui a ouvert ces données en dernier ; une autre version fait d'abord une sauvegarde `…_avant-mise-a-jour`). Chaque sauvegarde contient un `manifeste.json` (ses fichiers, avec leur taille et leur empreinte SHA-256). La configuration, `prevo.config.json`, est à côté de `serveur.py`, jamais dans le dossier des données.

### 5.2 Les documents joints (`documents/`)

- **Nom imposé par le serveur** : en mode serveur, chaque document envoyé est enregistré sous `AAAAMMJJ-HHMMSS-<nom demandé>` (horodatage du serveur, extension en minuscules), et c'est ce nom qui est écrit dans la colonne (type `document`). Les documents déjà présents gardent leur nom ; en mode dossier, le nom n'a pas de préfixe.
- **Extensions acceptées** : `.csv`, `.docx`, `.gif`, `.html`, `.jpeg`, `.jpg`, `.ods`, `.odt`, `.pdf`, `.png`, `.txt`, `.webp`, `.xlsx`. Toute autre est refusée, dont `.doc` et `.xls` depuis Prévo 2 : enregistrez en `.docx` ou `.xlsx`.
- **Place** : 4096 Mo au plus pour tout le dossier, par défaut (`quota_documents_mo` de `prevo.config.json`).

### 5.3 Nouveaux réglages de `parametres.csv`

| Clé | Libellé dans Paramètres | Valeurs | Défaut | Rôle |
| --- | --- | --- | --- | --- |
| `mode_solo` | Mode Solo : je fais tout moi-même | `0`, `1` | `0` | `1` : mode Solo (menu allégé, « Nouvel OT » en premier). Posé par l'assistant en Solo ou par « Passer en mode Solo » (Paramètres), remis à `0` par « Quitter le mode Solo ». |
| `cloture_une_etape` | Clôture en une étape (bouton « Clore » pour le responsable) | `0`, `1` | `0` | `1` : bouton « Clore » du responsable (clôtures technique et administrative d'un coup). Posé à `1` avec le mode Solo ; réglable dans Paramètres, section Ordres de travail. |
| `solo_technicien_id` | Technicien « moi » du mode Solo | texte | vide | Identifiant (`TEC-…`) du technicien « moi » du mode Solo, pré-rempli sur les OT ; il reste dans l'équipe si l'on quitte ce mode. |
| `langue_defaut` | Langue de l'installation | `fr`, `en` | `fr` | Langue de l'installation (chantier multilingue, D149) : langue des postes qui n'ont pas choisi la leur, et des textes que Prévo écrit dans les données (journal, motifs, rapport figé). Code d'une langue déclarée ; réglable dans Paramètres, section Entreprise. |
| `devise` | Devise | `EUR`, `CHF`, `GBP`, `USD`, `TRY` | `EUR` | Devise d'affichage des montants (chantier multilingue, D152) : code ISO 4217, `EUR` par défaut. La liste de Paramètres propose ces codes et « Autre code ISO 4217 » : tout code ISO connu s'écrit ici. Change seulement l'affichage : aucun montant des fichiers n'est converti (les montants des CSV restent des nombres sans symbole). Réglable dans Paramètres, section Entreprise. |

`ia_distant_autorise` (« Autoriser les fournisseurs d'IA en ligne (OpenAI, Mistral, Groq…) ») ne décide plus rien en mode serveur : un fournisseur d'IA en ligne n'y est permis que par `ia_en_ligne` dans `prevo.config.json` du PC serveur, et la case de Paramètres montre cette décision. En mode dossier, la case décide comme avant.
