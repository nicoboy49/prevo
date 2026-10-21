# Fiche technique des fichiers CSV de Prévo

Document généré par `outils/generer_fiche_csv.py` d'après `js/schema.js` : ne pas le modifier à la main.

Prévo range ses données dans **22 fichiers CSV** (format **version 2**), dans le dossier de données (`donnees/` à côté de `serveur.py`, ou le dossier choisi en mode dossier). Ils s'ouvrent et se modifient dans Excel. Le paramètre `version_schema` de `parametres.csv` indique la version du format.

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
| `document` | nom d'un fichier du dossier `documents/` (photo, PDF…) |

## 3. Les 22 fichiers

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
