'use strict';
// Schema : description des 24 tables de Prévo (champs, types, identifiants).
// Contrat : docs/ARCHITECTURE.md §4, §14.1 et §20.2 (format 3 : tables wiki_pages et wiki_journal, colonne
// ordres_travail.astuce, lot 6). Les champs de chaque table sont d'abord exactement
// ceux du tableau du brief §6, dans le même ordre (l'ordre des champs = l'ordre des colonnes CSV),
// puis, en fin de table, les champs ajoutés par la version 2 du format (attribut depuisVersion: 2).
// Un fichier écrit avant la version 2 n'a pas ces colonnes : la lecture les complète avec la
// valeur par défaut (simple information) et l'écriture suivante les ajoute en dernière position.
// Toutes les valeurs en mémoire sont des chaînes : les valeurs par défaut le sont aussi.

const Schema = (function () {

  // ---------------------------------------------------------------------------
  // Petites fabriques de champs (pour que les tables restent lisibles)
  // ---------------------------------------------------------------------------

  // Champ générique : nom, type, libellé, puis options facultatives
  // (obligatoire, defaut, protege, synonymes, valeurs, table, champCible, filtre, depuisVersion).
  function champ(nom, type, libelle, options) {
    return Object.assign({ nom: nom, type: type, libelle: libelle }, options || {});
  }

  function identifiantChamp() {
    return champ('id', 'id', 'Identifiant');
  }

  // Champ « choix » : liste fermée de valeurs canoniques.
  function choix(nom, libelle, valeurs, options) {
    return champ(nom, 'choix', libelle, Object.assign({ valeurs: valeurs }, options || {}));
  }

  // Champ « ref » : référence vers la clé d'une autre table.
  function reference(nom, libelle, table, options) {
    return champ(nom, 'ref', libelle, Object.assign({ table: table }, options || {}));
  }

  // Champ « ref » vers codes_defaillance.code, filtré sur une famille (symptôme, cause, remède).
  function codeDefaillance(nom, libelle, famille) {
    return reference(nom, libelle, 'codes_defaillance', {
      champCible: 'code',
      filtre: { famille: famille },
    });
  }

  // Champ « actif » commun à plusieurs tables : une ligne n'est jamais supprimée.
  function champActif() {
    return champ('actif', 'booleen', 'Actif', { defaut: '1' });
  }

  // Champ booléen (0/1), faux par défaut.
  function booleen(nom, libelle) {
    return champ(nom, 'booleen', libelle, { defaut: '0' });
  }

  // Marque un champ ajouté par une version du format après la première (ARCHITECTURE.md §14.1).
  // Ces champs sont toujours placés en fin de table, après les champs du brief.
  function depuisVersion(version, champDefini) {
    champDefini.depuisVersion = version;
    return champDefini;
  }

  // ---------------------------------------------------------------------------
  // Valeurs canoniques des listes (accents compris, ARCHITECTURE.md §4)
  // ---------------------------------------------------------------------------

  const CRITICITES = ['A', 'B', 'C'];
  const PRIORITES = ['P1', 'P2', 'P3', 'P4'];

  // ---------------------------------------------------------------------------
  // Les 22 tables du brief §6, dans l'ordre de son tableau, puis wiki_pages et wiki_journal (format 3, lot 6)
  // ---------------------------------------------------------------------------

  const tables = {

    localisations: {
      fichier: 'localisations.csv', libelle: 'Localisations',
      cle: 'id',
      identifiant: { prefixe: 'LOC-', chiffres: 4, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        champ('libelle', 'texte', 'Libellé', { obligatoire: true, synonymes: ['nom', 'lieu', 'zone'] }),
        reference('parent_id', 'Localisation parente', 'localisations'),
        choix('type', 'Type', ['site', 'atelier', 'ligne'], { obligatoire: true }),
      ],
    },

    equipements: {
      fichier: 'equipements.csv', libelle: 'Équipements',
      cle: 'id',
      identifiant: { prefixe: 'EQ-', chiffres: 4, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        champ('repere', 'texte', 'Repère', {
          protege: true, obligatoire: true,
          synonymes: ['code machine', 'tag', 'référence machine', 'code équipement', 'n° machine', 'repère machine'],
        }),
        champ('designation', 'texte', 'Désignation', {
          obligatoire: true,
          synonymes: ['désignation', 'nom', 'machine', 'équipement', 'libellé', 'description machine'],
        }),
        reference('localisation_id', 'Localisation', 'localisations', {
          synonymes: ['localisation', 'atelier', 'ligne', 'emplacement', 'zone', 'site'],
        }),
        reference('parent_id', 'Équipement parent', 'equipements', {
          synonymes: ['parent', 'ensemble', 'machine mère'],
        }),
        champ('marque', 'texte', 'Marque', { synonymes: ['fabricant', 'constructeur'] }),
        champ('modele', 'texte', 'Modèle', { synonymes: ['modèle', 'type', 'référence constructeur'] }),
        champ('num_serie', 'texte', 'Numéro de série', {
          protege: true, synonymes: ['n° de série', 'numéro de série', 'n° série', 'serial', 'série', 'sn'],
        }),
        champ('date_mes', 'date', 'Date de mise en service', {
          synonymes: ['mise en service', 'date de mise en service', 'mes', 'date mes', 'année de mise en service'],
        }),
        choix('criticite', 'Criticité', CRITICITES, {
          defaut: 'B', synonymes: ['criticité', 'classe', 'priorité machine'],
        }),
        choix('statut', 'Statut', ['en service', 'arrêt', 'rebut'], {
          defaut: 'en service', synonymes: ['état', 'etat'],
        }),
        champ('heures_fonct_jour', 'decimal', 'Heures de fonctionnement par jour', {
          synonymes: ['heures par jour', 'h/jour', 'heures de fonctionnement'],
        }),
        champ('habilitation_requise', 'texte', 'Habilitation requise', {
          synonymes: ['habilitation', 'habilitations requises'],
        }),
        champ('consignation', 'texte_long', 'Consignation', {
          synonymes: ['procédure de consignation', 'consignation énergies'],
        }),
        champ('document', 'document', 'Document'),
        champActif(),
        // Version 2 du format (ARCHITECTURE.md §14.1)
        depuisVersion(2, champ('valeur_remplacement', 'decimal', 'Valeur de remplacement (€ HT)', {
          synonymes: ['valeur de remplacement', 'valeur à neuf', 'prix de remplacement'],
        })),
      ],
    },

    demandes: {
      fichier: 'demandes.csv', libelle: 'Demandes d\'intervention',
      cle: 'id',
      identifiant: { prefixe: 'DI-', chiffres: 4, annuel: true },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        champ('date_heure', 'date_heure', 'Date et heure de la demande'),
        champ('demandeur', 'texte', 'Demandeur'),
        reference('equipement_id', 'Équipement', 'equipements', { obligatoire: true }),
        champ('symptome', 'texte_long', 'Symptôme observé', { obligatoire: true }),
        choix('impact', 'Impact', ['sécurité', 'arrêt', 'dégradé', 'gêne'], { obligatoire: true }),
        champ('description', 'texte_long', 'Description'),
        champ('photo', 'document', 'Photo'),
        choix('statut', 'Statut', ['Nouvelle', 'Acceptée', 'Regroupée', 'Différée', 'Refusée'], {
          defaut: 'Nouvelle',
        }),
        champ('motif_decision', 'texte_long', 'Motif de la décision'),
        champ('date_decision', 'date_heure', 'Date de la décision'),
        reference('ot_id', 'Ordre de travail lié', 'ordres_travail'),
        // Version 2 du format (ARCHITECTURE.md §14.1)
        depuisVersion(2, codeDefaillance('symptome_code', 'Code symptôme', 'symptôme')),
        depuisVersion(2, reference('ot_origine_id', 'OT d\'origine (préventif)', 'ordres_travail')),
      ],
    },

    ordres_travail: {
      fichier: 'ordres_travail.csv', libelle: 'Ordres de travail',
      cle: 'id',
      identifiant: { prefixe: 'OT-', chiffres: 4, annuel: true },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        choix('origine', 'Origine', ['DI', 'préventif', 'urgence', 'manuel']),
        reference('di_id', 'Demande d\'intervention', 'demandes'),
        reference('gamme_id', 'Gamme de préventif', 'gammes'),
        reference('equipement_id', 'Équipement', 'equipements', { obligatoire: true }),
        choix('type', 'Type', [
          'correctif immédiat', 'correctif différé', 'préventif systématique',
          'préventif conditionnel', 'amélioration', 'réglementaire',
        ], { obligatoire: true }),
        choix('priorite', 'Priorité', PRIORITES, { obligatoire: true }),
        choix('statut', 'Statut', [
          'Créé', 'Préparé', 'Planifié', 'En cours', 'En attente',
          'Clôturé techniquement', 'Clôturé administrativement', 'Annulé',
        ], { obligatoire: true, defaut: 'Créé' }),
        champ('motif_attente', 'texte_long', 'Motif de mise en attente'),
        champ('titre', 'texte', 'Titre', { obligatoire: true }),
        champ('travail_a_faire', 'texte_long', 'Travail à faire'),
        champ('consignes', 'texte_long', 'Consignes'),
        champ('date_creation', 'date_heure', 'Date de création'),
        champ('date_prevue', 'date', 'Date prévue'),
        reference('technicien_id', 'Technicien', 'techniciens'),
        champ('temps_prevu_h', 'decimal', 'Temps prévu (heures)'),
        champ('date_debut', 'date_heure', 'Date de début'),
        champ('date_fin', 'date_heure', 'Date de fin'),
        booleen('arret_production', 'Arrêt de production'),
        champ('duree_arret_h', 'decimal', 'Durée d\'arrêt (heures)'),
        codeDefaillance('symptome_code', 'Code symptôme', 'symptôme'),
        codeDefaillance('cause_code', 'Code cause', 'cause'),
        codeDefaillance('remede_code', 'Code remède', 'remède'),
        champ('compte_rendu', 'texte_long', 'Compte rendu'),
        booleen('remise_service', 'Remis en service en sécurité'),
        champ('cout_soustraitance', 'decimal', 'Coût de sous-traitance'),
        champ('date_cloture_tech', 'date_heure', 'Date de clôture technique'),
        champ('date_cloture_admin', 'date_heure', 'Date de clôture administrative'),
        champ('motif_annulation', 'texte_long', 'Motif d\'annulation'),
        reference('ot_lie_id', 'Ordre de travail lié', 'ordres_travail'),
        // Version 2 du format (ARCHITECTURE.md §14.1)
        depuisVersion(2, booleen('anomalie_constatee', 'Anomalie constatée')),
        // Version 3 du format (ARCHITECTURE.md §20.2, D110) : facultative, jamais exigée à la clôture
        depuisVersion(3, champ('astuce', 'texte_long', 'Astuce pour la prochaine fois')),
      ],
    },

    ot_operations: {
      fichier: 'ot_operations.csv', libelle: 'Opérations d\'ordre de travail',
      cle: 'id',
      identifiant: { prefixe: 'OTO-', chiffres: 6, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        reference('ot_id', 'Ordre de travail', 'ordres_travail'),
        champ('ordre', 'entier', 'Ordre'),
        champ('operation', 'texte', 'Opération'),
        champ('valeur_attendue', 'texte', 'Valeur attendue'),
        booleen('fait', 'Fait'),
        champ('valeur_mesuree', 'texte', 'Valeur mesurée'),
      ],
    },

    ot_pieces: {
      fichier: 'ot_pieces.csv', libelle: 'Pièces prévues d\'ordre de travail',
      cle: 'id',
      identifiant: { prefixe: 'OTP-', chiffres: 6, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        reference('ot_id', 'Ordre de travail', 'ordres_travail'),
        reference('article_id', 'Article', 'articles'),
        champ('quantite_prevue', 'decimal', 'Quantité prévue'),
      ],
    },

    ot_temps: {
      fichier: 'ot_temps.csv', libelle: 'Temps passés sur ordre de travail',
      cle: 'id',
      identifiant: { prefixe: 'OTT-', chiffres: 6, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        reference('ot_id', 'Ordre de travail', 'ordres_travail'),
        reference('technicien_id', 'Technicien', 'techniciens'),
        champ('date', 'date', 'Date'),
        champ('heures', 'decimal', 'Heures'),
      ],
    },

    gammes: {
      fichier: 'gammes.csv', libelle: 'Gammes de préventif',
      cle: 'id',
      identifiant: { prefixe: 'GAM-', chiffres: 4, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        reference('equipement_id', 'Équipement', 'equipements'),
        champ('libelle', 'texte', 'Libellé'),
        choix('declencheur', 'Déclencheur', ['date', 'compteur', 'seuil'], { defaut: 'date' }),
        champ('periodicite_jours', 'entier', 'Périodicité (jours)'),
        reference('compteur_id', 'Compteur', 'compteurs'),
        champ('periodicite_unites', 'decimal', 'Périodicité (unités du compteur)'),
        champ('seuil', 'decimal', 'Seuil'),
        champ('avance_jours', 'entier', 'Avance (jours)'),
        champ('derniere_realisation', 'date', 'Dernière réalisation'),
        champ('releve_derniere_realisation', 'decimal', 'Relevé à la dernière réalisation'),
        champ('prochaine_echeance', 'date', 'Prochaine échéance'),
        champ('temps_prevu_h', 'decimal', 'Temps prévu (heures)'),
        champ('consignes', 'texte_long', 'Consignes'),
        champActif(),
      ],
    },

    gamme_operations: {
      fichier: 'gamme_operations.csv', libelle: 'Opérations de gamme',
      cle: 'id',
      identifiant: { prefixe: 'GOP-', chiffres: 6, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        reference('gamme_id', 'Gamme', 'gammes'),
        champ('ordre', 'entier', 'Ordre'),
        champ('operation', 'texte', 'Opération'),
        champ('valeur_attendue', 'texte', 'Valeur attendue'),
      ],
    },

    articles: {
      fichier: 'articles.csv', libelle: 'Articles (pièces détachées)',
      cle: 'id',
      identifiant: { prefixe: 'ART-', chiffres: 4, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        champ('reference', 'texte', 'Référence', {
          protege: true, obligatoire: true,
          synonymes: ['référence', 'réf', 'ref', 'code article', 'code'],
        }),
        champ('designation', 'texte', 'Désignation', {
          obligatoire: true, synonymes: ['désignation', 'libellé', 'article', 'description'],
        }),
        champ('fabricant', 'texte', 'Fabricant', { synonymes: ['marque', 'constructeur'] }),
        champ('ref_fabricant', 'texte', 'Référence fabricant', {
          protege: true, synonymes: ['réf fabricant', 'réf. fabricant', 'référence constructeur', 'ref constructeur'],
        }),
        champ('emplacement', 'texte', 'Emplacement', {
          synonymes: ['rayon', 'casier', 'étagère', 'localisation magasin'],
        }),
        champ('unite', 'texte', 'Unité', { synonymes: ['unité', 'u'] }),
        champ('stock', 'decimal', 'Stock', { synonymes: ['quantité en stock', 'qté stock', 'stock actuel'] }),
        champ('stock_securite', 'decimal', 'Stock de sécurité', { synonymes: ['stock mini', 'stock minimum'] }),
        champ('point_commande', 'decimal', 'Point de commande', { synonymes: ['seuil de commande'] }),
        champ('qte_commande', 'decimal', 'Quantité à commander', { synonymes: ['quantité de commande', 'qté commande'] }),
        champ('delai_jours', 'entier', 'Délai d\'approvisionnement (jours)', { synonymes: ['délai', 'délai livraison'] }),
        champ('prix_unitaire', 'decimal', 'Prix unitaire', { synonymes: ['prix', 'pu', 'prix achat', 'prix d\'achat'] }),
        reference('fournisseur_id', 'Fournisseur', 'fournisseurs', { synonymes: ['fournisseur'] }),
        booleen('critique', 'Article critique'),
        champActif(),
      ],
    },

    article_equipement: {
      fichier: 'article_equipement.csv', libelle: 'Articles par équipement',
      cle: 'id',
      identifiant: { prefixe: 'AEQ-', chiffres: 5, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        reference('article_id', 'Article', 'articles'),
        reference('equipement_id', 'Équipement', 'equipements'),
        champ('quantite', 'decimal', 'Quantité'),
      ],
    },

    mouvements_stock: {
      fichier: 'mouvements_stock.csv', libelle: 'Mouvements de stock',
      cle: 'id',
      identifiant: { prefixe: 'MVT-', chiffres: 6, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        champ('date', 'date_heure', 'Date et heure'),
        reference('article_id', 'Article', 'articles'),
        choix('type', 'Type', ['entrée', 'sortie', 'inventaire', 'retour']),
        champ('quantite', 'decimal', 'Quantité'),
        reference('ot_id', 'Ordre de travail', 'ordres_travail'),
        champ('utilisateur', 'texte', 'Utilisateur'),
        champ('commentaire', 'texte_long', 'Commentaire'),
      ],
    },

    techniciens: {
      fichier: 'techniciens.csv', libelle: 'Techniciens',
      cle: 'id',
      identifiant: { prefixe: 'TEC-', chiffres: 4, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        champ('nom', 'texte', 'Nom', { obligatoire: true, synonymes: ['nom de famille', 'technicien'] }),
        champ('prenom', 'texte', 'Prénom', { synonymes: ['prénom'] }),
        champ('metier', 'texte', 'Métier', { synonymes: ['métier', 'fonction', 'spécialité', 'poste'] }),
        champ('taux_horaire', 'decimal', 'Taux horaire', { synonymes: ['coût horaire', 'tarif horaire', '€/h'] }),
        champ('capacite_h_semaine', 'decimal', 'Capacité (heures par semaine)', {
          synonymes: ['capacité', 'heures par semaine', 'h/semaine'],
        }),
        champActif(),
      ],
    },

    habilitations: {
      fichier: 'habilitations.csv', libelle: 'Habilitations',
      cle: 'id',
      identifiant: { prefixe: 'HAB-', chiffres: 4, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        reference('technicien_id', 'Technicien', 'techniciens'),
        champ('intitule', 'texte', 'Intitulé', { synonymes: ['habilitation', 'intitulé', 'titre'] }),
        champ('date_obtention', 'date', 'Date d\'obtention', { synonymes: ['obtenue le', 'date obtention'] }),
        champ('date_echeance', 'date', 'Date d\'échéance', {
          synonymes: ['échéance', 'valable jusqu\'au', 'date d\'expiration', 'expiration'],
        }),
      ],
    },

    compteurs: {
      fichier: 'compteurs.csv', libelle: 'Compteurs',
      cle: 'id',
      identifiant: { prefixe: 'CPT-', chiffres: 4, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        reference('equipement_id', 'Équipement', 'equipements'),
        champ('libelle', 'texte', 'Libellé'),
        champ('unite', 'texte', 'Unité'),
      ],
    },

    releves: {
      fichier: 'releves.csv', libelle: 'Relevés de compteur',
      cle: 'id',
      identifiant: { prefixe: 'REL-', chiffres: 6, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        reference('compteur_id', 'Compteur', 'compteurs'),
        champ('date', 'date', 'Date'),
        champ('valeur', 'decimal', 'Valeur'),
        champ('utilisateur', 'texte', 'Utilisateur'),
      ],
    },

    controles_reglementaires: {
      fichier: 'controles_reglementaires.csv', libelle: 'Contrôles réglementaires',
      cle: 'id',
      identifiant: { prefixe: 'CTR-', chiffres: 4, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        reference('equipement_id', 'Équipement', 'equipements'),
        champ('nature', 'texte', 'Nature du contrôle'),
        champ('texte_reference', 'texte', 'Texte de référence'),
        champ('periodicite_mois', 'entier', 'Périodicité (mois)'),
        champ('organisme', 'texte', 'Organisme de contrôle'),
        champ('derniere_date', 'date', 'Date du dernier contrôle'),
        champ('prochaine_date', 'date', 'Date du prochain contrôle'),
        champ('rapport', 'document', 'Rapport'),
        champ('observations', 'texte_long', 'Observations'),
        booleen('observations_levees', 'Observations levées'),
      ],
    },

    codes_defaillance: {
      fichier: 'codes_defaillance.csv', libelle: 'Codes de défaillance',
      cle: 'id',
      identifiant: { prefixe: 'CD-', chiffres: 4, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        choix('famille', 'Famille', ['symptôme', 'cause', 'remède'], { obligatoire: true }),
        champ('code', 'texte', 'Code', { obligatoire: true }),
        champ('libelle', 'texte', 'Libellé', { obligatoire: true }),
      ],
    },

    fournisseurs: {
      fichier: 'fournisseurs.csv', libelle: 'Fournisseurs',
      cle: 'id',
      identifiant: { prefixe: 'FOU-', chiffres: 4, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        champ('nom', 'texte', 'Nom', { synonymes: ['fournisseur', 'raison sociale', 'société'] }),
        champ('contact', 'texte', 'Contact', { synonymes: ['interlocuteur', 'nom du contact'] }),
        champ('telephone', 'texte', 'Téléphone', { protege: true, synonymes: ['téléphone', 'tél', 'tel', 'portable'] }),
        champ('email', 'texte', 'E-mail', { synonymes: ['e-mail', 'mail', 'courriel', 'adresse mail'] }),
      ],
    },

    achats: {
      fichier: 'achats.csv', libelle: 'Achats',
      cle: 'id',
      identifiant: { prefixe: 'ACH-', chiffres: 4, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        champ('date', 'date', 'Date'),
        reference('article_id', 'Article', 'articles'),
        reference('fournisseur_id', 'Fournisseur', 'fournisseurs'),
        champ('quantite', 'decimal', 'Quantité'),
        champ('prix_unitaire', 'decimal', 'Prix unitaire'),
        choix('statut', 'Statut', ['demandée', 'commandée', 'reçue'], { defaut: 'demandée' }),
        champ('date_reception', 'date', 'Date de réception'),
      ],
    },

    parametres: {
      fichier: 'parametres.csv', libelle: 'Paramètres',
      cle: 'cle',                      // pas d'identifiant calculé : la clé est saisie
      ajoutSeul: false,
      champs: [
        champ('cle', 'id', 'Clé'),
        champ('valeur', 'texte', 'Valeur'),
      ],
    },

    journal: {
      fichier: 'journal.csv', libelle: 'Journal des modifications',
      cle: 'id',
      // J-AAAAMMJJHHMMSS-XXXX : « chiffres » = nombre de caractères aléatoires finaux.
      identifiant: { prefixe: 'J-', chiffres: 4, annuel: false, horodate: true },
      ajoutSeul: true,                 // écriture par ajout (ARCHITECTURE.md §5.4)
      champs: [
        identifiantChamp(),
        champ('date_heure', 'date_heure', 'Date et heure'),
        champ('poste', 'texte', 'Poste'),
        champ('profil', 'texte', 'Profil'),
        champ('table', 'texte', 'Table'),
        champ('id_ligne', 'texte', 'Identifiant de la ligne'),
        champ('action', 'texte', 'Action'),
      ],
    },

    // Format 3 (lot 6 refondu, ARCHITECTURE.md §20.2) : le wiki de maintenance. Une base plus ancienne n'a pas
    // ces fichiers : tables vides, créées à la première écriture. Seules les pages qui ont un texte validé ont
    // une ligne ; les pages d'équipement et d'article existent toujours, calculées (§20.3).
    wiki_pages: {
      fichier: 'wiki_pages.csv', libelle: 'Pages du wiki',
      cle: 'id',
      identifiant: { prefixe: 'WP-', chiffres: 4, annuel: false },
      ajoutSeul: false,
      depuisVersion: 3,
      champs: [
        identifiantChamp(),
        choix('type', 'Type', ['équipement', 'composant', 'mode', 'savoir-faire'], { obligatoire: true }),
        champ('titre', 'texte', 'Titre', { obligatoire: true }),
        champ('cle', 'texte', 'Clé (titre comparable)'),
        reference('equipement_id', 'Équipement', 'equipements'),
        reference('article_id', 'Article', 'articles'),
        codeDefaillance('cause_code', 'Code cause', 'cause'),
        reference('rattache_a', 'Rattaché à la page', 'wiki_pages'),
        champ('texte', 'texte_long', 'Texte'),
        champ('ot_cites', 'texte', 'OT cités'),
        champ('liens', 'texte', 'Pages liées'),
        champ('version', 'entier', 'Version', { defaut: '0' }),
        choix('origine', 'Origine', ['IA', 'manuel', 'IA et manuel']),
        champ('modele', 'texte', 'Modèle'),
        reference('derniere_entree', 'Dernière entrée appliquée', 'wiki_journal'),
        champ('valide_par', 'texte', 'Validé par'),
        champ('valide_le', 'date_heure', 'Validé le'),
        champ('cree_le', 'date_heure', 'Créée le'),
        champ('modifie_le', 'date_heure', 'Modifiée le'),
        choix('statut', 'Statut', ['active', 'archivée'], { defaut: 'active' }),
      ],
    },

    // Journal du wiki (§20.2) : une ligne par OT ingéré, par écriture à la main et par décision sur une
    // contradiction. Les changements et les contradictions sont du JSON dans un champ texte long.
    wiki_journal: {
      fichier: 'wiki_journal.csv', libelle: 'Journal du wiki',
      cle: 'id',
      identifiant: { prefixe: 'WJ-', chiffres: 5, annuel: false },
      ajoutSeul: false,
      depuisVersion: 3,
      champs: [
        identifiantChamp(),
        choix('nature', 'Nature', ['ingestion', 'manuel', 'décision'], { obligatoire: true }),
        reference('ot_id', 'Ordre de travail', 'ordres_travail'),
        champ('date_intervention', 'date_heure', 'Date d\'intervention'),
        choix('statut', 'Statut', ['en file', 'à valider', 'validée', 'rejetée', 'à refaire', 'refusée',
          'rien à ajouter', 'appliquée'], { obligatoire: true }),
        booleen('anterieure', 'Intervention antérieure'),
        champ('ordre', 'entier', 'Rang de traitement'),
        champ('pages', 'texte', 'Pages concernées'),
        champ('changements', 'texte_long', 'Changements'),
        champ('contradictions', 'texte_long', 'Contradictions'),
        champ('raisons', 'texte_long', 'Raisons du refus'),
        champ('modele', 'texte', 'Modèle'),
        champ('essais', 'entier', 'Essais', { defaut: '0' }),
        champ('cree_le', 'date_heure', 'Créée le'),
        champ('traite_le', 'date_heure', 'Traitée le'),
        champ('decide_par', 'texte', 'Décidé par'),
        champ('decide_le', 'date_heure', 'Décidé le'),
        champ('motif', 'texte_long', 'Motif'),
      ],
    },
  };

  // ---------------------------------------------------------------------------
  // Fonctions pures d'accès
  // ---------------------------------------------------------------------------

  // Description d'une table, ou undefined si elle n'existe pas.
  function table(nomTable) {
    return Object.prototype.hasOwnProperty.call(tables, nomTable) ? tables[nomTable] : undefined;
  }

  // Description d'un champ d'une table, ou undefined si la table ou le champ n'existe pas.
  function champDeTable(nomTable, nomChamp) {
    const tableTrouvee = table(nomTable);
    if (!tableTrouvee) { return undefined; }
    return tableTrouvee.champs.find(function (c) { return c.nom === nomChamp; });
  }

  // Noms des 24 tables, dans l'ordre du brief puis celles ajoutées par les versions du format.
  function nomsTables() {
    return Object.keys(tables);
  }

  return {
    version: 3,                        // version du format des fichiers (ARCHITECTURE.md §14.1, §20.2)
    tables: tables,
    table: table,
    champ: champDeTable,
    nomsTables: nomsTables,
  };
})();
