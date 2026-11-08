'use strict';
// Schema : description des 27 tables de Prévo (champs, types, identifiants).
// Contrat : docs/ARCHITECTURE.md §4, §14.1 et §20.2 (format 3 : tables wiki_pages et wiki_journal, colonne
// ordres_travail.astuce, lot 6) ; format 4 (version 2.2, docs/FORMAT.md) : tables reserves_controle, garanties et
// contrats_prestataires, colonnes de equipements, ordres_travail, habilitations et controles_reglementaires.
// Les champs de chaque table sont d'abord exactement
// ceux du tableau du brief §6, dans le même ordre (l'ordre des champs = l'ordre des colonnes CSV),
// puis, en fin de table, les champs ajoutés par les versions suivantes du format (attribut depuisVersion: N).
// Un fichier écrit avant la version N n'a pas ces colonnes : la lecture les complète avec la
// valeur par défaut (simple information) et l'écriture suivante les ajoute en dernière position.
// Toutes les valeurs en mémoire sont des chaînes : les valeurs par défaut le sont aussi.

const Schema = (function () {

  // ---------------------------------------------------------------------------
  // Petites fabriques de champs (pour que les tables restent lisibles)
  // ---------------------------------------------------------------------------

  // Champ générique : nom, type, puis options facultatives
  // (obligatoire, defaut, protege, synonymes, valeurs, retirees, table, champCible, filtre, depuisVersion).
  // Le libellé n'est pas écrit ici : il est lu dans js/i18n/fr.js (schema.<table>.<champ>) à chaque lecture de
  // champ.libelle (voir « Libellés » plus bas).
  function champ(nom, type, options) {
    return Object.assign({ nom: nom, type: type }, options || {});
  }

  function identifiantChamp() {
    return champ('id', 'id');
  }

  // Champ « choix » : liste fermée de valeurs canoniques. Option `retirees` : valeurs qui ne sont plus proposées ni
  // permises, mais encore lues sans erreur dans une ancienne ligne (Donnees la signale par le contrôle de sa table).
  function choix(nom, valeurs, options) {
    return champ(nom, 'choix', Object.assign({ valeurs: valeurs }, options || {}));
  }

  // Champ « ref » : référence vers la clé d'une autre table.
  function reference(nom, table, options) {
    return champ(nom, 'ref', Object.assign({ table: table }, options || {}));
  }

  // Champ « ref » vers codes_defaillance.code, filtré sur une famille (symptôme, cause, remède).
  function codeDefaillance(nom, famille) {
    return reference(nom, 'codes_defaillance', {
      champCible: 'code',
      filtre: { famille: famille },
    });
  }

  // Champ « actif » commun à plusieurs tables : une ligne n'est jamais supprimée.
  function champActif() {
    return champ('actif', 'booleen', { defaut: '1' });
  }

  // Champ booléen (0/1), faux par défaut.
  function booleen(nom) {
    return champ(nom, 'booleen', { defaut: '0' });
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
  // Format 4 : nature de la source d'un contrôle ou d'une habilitation (mêmes valeurs dans les deux tables).
  const NATURES_SOURCE = ['obligation', 'norme', 'recommandation'];

  // ---------------------------------------------------------------------------
  // Les 22 tables du brief §6, dans l'ordre de son tableau, puis wiki_pages et wiki_journal (format 3, lot 6),
  // puis reserves_controle, garanties et contrats_prestataires (format 4, version 2.2)
  // ---------------------------------------------------------------------------

  const tables = {

    localisations: {
      fichier: 'localisations.csv',
      cle: 'id',
      identifiant: { prefixe: 'LOC-', chiffres: 4, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        champ('libelle', 'texte', { obligatoire: true, synonymes: ['nom', 'lieu', 'zone'] }),
        reference('parent_id', 'localisations'),
        choix('type', ['site', 'atelier', 'ligne'], { obligatoire: true }),
      ],
    },

    equipements: {
      fichier: 'equipements.csv',
      cle: 'id',
      identifiant: { prefixe: 'EQ-', chiffres: 4, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        champ('repere', 'texte', {
          protege: true, obligatoire: true,
          synonymes: ['code machine', 'tag', 'référence machine', 'code équipement', 'n° machine', 'repère machine'],
        }),
        champ('designation', 'texte', {
          obligatoire: true,
          synonymes: ['désignation', 'nom', 'machine', 'équipement', 'libellé', 'description machine'],
        }),
        reference('localisation_id', 'localisations', {
          synonymes: ['localisation', 'atelier', 'ligne', 'emplacement', 'zone', 'site'],
        }),
        reference('parent_id', 'equipements', {
          synonymes: ['parent', 'ensemble', 'machine mère'],
        }),
        champ('marque', 'texte', { synonymes: ['fabricant', 'constructeur'] }),
        champ('modele', 'texte', { synonymes: ['modèle', 'type', 'référence constructeur'] }),
        champ('num_serie', 'texte', {
          protege: true, synonymes: ['n° de série', 'numéro de série', 'n° série', 'serial', 'série', 'sn'],
        }),
        champ('date_mes', 'date', {
          synonymes: ['mise en service', 'date de mise en service', 'mes', 'date mes', 'année de mise en service'],
        }),
        choix('criticite', CRITICITES, {
          defaut: 'B', synonymes: ['criticité', 'classe', 'priorité machine'],
        }),
        choix('statut', ['en service', 'arrêt', 'rebut'], {
          defaut: 'en service', synonymes: ['état', 'etat'],
        }),
        champ('heures_fonct_jour', 'decimal', {
          synonymes: ['heures par jour', 'h/jour', 'heures de fonctionnement'],
        }),
        champ('habilitation_requise', 'texte', {
          synonymes: ['habilitation', 'habilitations requises'],
        }),
        champ('consignation', 'texte_long', {
          synonymes: ['procédure de consignation', 'consignation énergies'],
        }),
        champ('document', 'document'),
        champActif(),
        // Version 2 du format (ARCHITECTURE.md §14.1)
        depuisVersion(2, champ('valeur_remplacement', 'decimal', {
          synonymes: ['valeur de remplacement', 'valeur à neuf', 'prix de remplacement'],
        })),
        // Version 4 du format (2.2, D188) : aucun défaut
        depuisVersion(4, champ('cout_arret_h', 'decimal')),
      ],
    },

    demandes: {
      fichier: 'demandes.csv',
      cle: 'id',
      identifiant: { prefixe: 'DI-', chiffres: 4, annuel: true },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        champ('date_heure', 'date_heure'),
        champ('demandeur', 'texte'),
        reference('equipement_id', 'equipements', { obligatoire: true }),
        champ('symptome', 'texte_long', { obligatoire: true }),
        choix('impact', ['sécurité', 'arrêt', 'dégradé', 'gêne'], { obligatoire: true }),
        champ('description', 'texte_long'),
        champ('photo', 'document'),
        choix('statut', ['Nouvelle', 'Acceptée', 'Regroupée', 'Différée', 'Refusée'], {
          defaut: 'Nouvelle',
        }),
        champ('motif_decision', 'texte_long'),
        champ('date_decision', 'date_heure'),
        reference('ot_id', 'ordres_travail'),
        // Version 2 du format (ARCHITECTURE.md §14.1)
        depuisVersion(2, codeDefaillance('symptome_code', 'symptôme')),
        depuisVersion(2, reference('ot_origine_id', 'ordres_travail')),
      ],
    },

    ordres_travail: {
      fichier: 'ordres_travail.csv',
      cle: 'id',
      identifiant: { prefixe: 'OT-', chiffres: 4, annuel: true },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        choix('origine', ['DI', 'préventif', 'urgence', 'manuel']),
        reference('di_id', 'demandes'),
        reference('gamme_id', 'gammes'),
        reference('equipement_id', 'equipements', { obligatoire: true }),
        choix('type', [
          'correctif immédiat', 'correctif différé', 'préventif systématique',
          'préventif conditionnel', 'amélioration', 'réglementaire',
        ], { obligatoire: true }),
        choix('priorite', PRIORITES, { obligatoire: true }),
        choix('statut', [
          'Créé', 'Préparé', 'Planifié', 'En cours', 'En attente',
          'Clôturé techniquement', 'Clôturé administrativement', 'Annulé',
        ], { obligatoire: true, defaut: 'Créé' }),
        champ('motif_attente', 'texte_long'),
        champ('titre', 'texte', { obligatoire: true }),
        champ('travail_a_faire', 'texte_long'),
        champ('consignes', 'texte_long'),
        champ('date_creation', 'date_heure'),
        champ('date_prevue', 'date'),
        reference('technicien_id', 'techniciens'),
        champ('temps_prevu_h', 'decimal'),
        champ('date_debut', 'date_heure'),
        champ('date_fin', 'date_heure'),
        booleen('arret_production'),
        champ('duree_arret_h', 'decimal'),
        codeDefaillance('symptome_code', 'symptôme'),
        codeDefaillance('cause_code', 'cause'),
        codeDefaillance('remede_code', 'remède'),
        champ('compte_rendu', 'texte_long'),
        booleen('remise_service'),
        champ('cout_soustraitance', 'decimal'),
        champ('date_cloture_tech', 'date_heure'),
        champ('date_cloture_admin', 'date_heure'),
        champ('motif_annulation', 'texte_long'),
        reference('ot_lie_id', 'ordres_travail'),
        // Version 2 du format (ARCHITECTURE.md §14.1)
        depuisVersion(2, booleen('anomalie_constatee')),
        // Version 3 du format (ARCHITECTURE.md §20.2, D110) : facultative, jamais exigée à la clôture
        depuisVersion(3, champ('astuce', 'texte_long')),
        // Version 4 du format (2.2, D191) : intitulés séparés par « , » ou « / », comme
        // equipements.habilitation_requise
        depuisVersion(4, champ('habilitation_requise', 'texte')),
      ],
    },

    ot_operations: {
      fichier: 'ot_operations.csv',
      cle: 'id',
      identifiant: { prefixe: 'OTO-', chiffres: 6, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        reference('ot_id', 'ordres_travail'),
        champ('ordre', 'entier'),
        champ('operation', 'texte'),
        champ('valeur_attendue', 'texte'),
        booleen('fait'),
        champ('valeur_mesuree', 'texte'),
      ],
    },

    ot_pieces: {
      fichier: 'ot_pieces.csv',
      cle: 'id',
      identifiant: { prefixe: 'OTP-', chiffres: 6, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        reference('ot_id', 'ordres_travail'),
        reference('article_id', 'articles'),
        champ('quantite_prevue', 'decimal'),
      ],
    },

    ot_temps: {
      fichier: 'ot_temps.csv',
      cle: 'id',
      identifiant: { prefixe: 'OTT-', chiffres: 6, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        reference('ot_id', 'ordres_travail'),
        reference('technicien_id', 'techniciens'),
        champ('date', 'date'),
        champ('heures', 'decimal'),
      ],
    },

    gammes: {
      fichier: 'gammes.csv',
      cle: 'id',
      identifiant: { prefixe: 'GAM-', chiffres: 4, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        reference('equipement_id', 'equipements'),
        champ('libelle', 'texte'),
        choix('declencheur', ['date', 'compteur', 'seuil'], { defaut: 'date' }),
        champ('periodicite_jours', 'entier'),
        reference('compteur_id', 'compteurs'),
        champ('periodicite_unites', 'decimal'),
        champ('seuil', 'decimal'),
        champ('avance_jours', 'entier'),
        champ('derniere_realisation', 'date'),
        champ('releve_derniere_realisation', 'decimal'),
        champ('prochaine_echeance', 'date'),
        champ('temps_prevu_h', 'decimal'),
        champ('consignes', 'texte_long'),
        champActif(),
      ],
    },

    gamme_operations: {
      fichier: 'gamme_operations.csv',
      cle: 'id',
      identifiant: { prefixe: 'GOP-', chiffres: 6, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        reference('gamme_id', 'gammes'),
        champ('ordre', 'entier'),
        champ('operation', 'texte'),
        champ('valeur_attendue', 'texte'),
      ],
    },

    articles: {
      fichier: 'articles.csv',
      cle: 'id',
      identifiant: { prefixe: 'ART-', chiffres: 4, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        champ('reference', 'texte', {
          protege: true, obligatoire: true,
          synonymes: ['référence', 'réf', 'ref', 'code article', 'code'],
        }),
        champ('designation', 'texte', {
          obligatoire: true, synonymes: ['désignation', 'libellé', 'article', 'description'],
        }),
        champ('fabricant', 'texte', { synonymes: ['marque', 'constructeur'] }),
        champ('ref_fabricant', 'texte', {
          protege: true, synonymes: ['réf fabricant', 'réf. fabricant', 'référence constructeur', 'ref constructeur'],
        }),
        champ('emplacement', 'texte', {
          synonymes: ['rayon', 'casier', 'étagère', 'localisation magasin'],
        }),
        champ('unite', 'texte', { synonymes: ['unité', 'u'] }),
        champ('stock', 'decimal', { synonymes: ['quantité en stock', 'qté stock', 'stock actuel'] }),
        champ('stock_securite', 'decimal', { synonymes: ['stock mini', 'stock minimum'] }),
        champ('point_commande', 'decimal', { synonymes: ['seuil de commande'] }),
        champ('qte_commande', 'decimal', { synonymes: ['quantité de commande', 'qté commande'] }),
        champ('delai_jours', 'entier', { synonymes: ['délai', 'délai livraison'] }),
        champ('prix_unitaire', 'decimal', { synonymes: ['prix', 'pu', 'prix achat', 'prix d\'achat'] }),
        reference('fournisseur_id', 'fournisseurs', { synonymes: ['fournisseur'] }),
        booleen('critique'),
        champActif(),
      ],
    },

    article_equipement: {
      fichier: 'article_equipement.csv',
      cle: 'id',
      identifiant: { prefixe: 'AEQ-', chiffres: 5, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        reference('article_id', 'articles'),
        reference('equipement_id', 'equipements'),
        champ('quantite', 'decimal'),
      ],
    },

    mouvements_stock: {
      fichier: 'mouvements_stock.csv',
      cle: 'id',
      identifiant: { prefixe: 'MVT-', chiffres: 6, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        champ('date', 'date_heure'),
        reference('article_id', 'articles'),
        choix('type', ['entrée', 'sortie', 'inventaire', 'retour']),
        champ('quantite', 'decimal'),
        reference('ot_id', 'ordres_travail'),
        champ('utilisateur', 'texte'),
        champ('commentaire', 'texte_long'),
      ],
    },

    techniciens: {
      fichier: 'techniciens.csv',
      cle: 'id',
      identifiant: { prefixe: 'TEC-', chiffres: 4, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        champ('nom', 'texte', { obligatoire: true, synonymes: ['nom de famille', 'technicien'] }),
        champ('prenom', 'texte', { synonymes: ['prénom'] }),
        champ('metier', 'texte', { synonymes: ['métier', 'fonction', 'spécialité', 'poste'] }),
        champ('taux_horaire', 'decimal', { synonymes: ['coût horaire', 'tarif horaire', '€/h'] }),
        champ('capacite_h_semaine', 'decimal', {
          synonymes: ['capacité', 'heures par semaine', 'h/semaine'],
        }),
        champActif(),
      ],
    },

    habilitations: {
      fichier: 'habilitations.csv',
      cle: 'id',
      identifiant: { prefixe: 'HAB-', chiffres: 4, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        reference('technicien_id', 'techniciens'),
        champ('intitule', 'texte', { synonymes: ['habilitation', 'intitulé', 'titre'] }),
        champ('date_obtention', 'date', { synonymes: ['obtenue le', 'date obtention'] }),
        champ('date_echeance', 'date', {
          synonymes: ['échéance', 'valable jusqu\'au', 'date d\'expiration', 'expiration'],
        }),
        // Version 4 du format (2.2, CS172, CS179, D185) : catalogue_id = H01 à H15 du catalogue validé
        depuisVersion(4, champ('recyclage_mois', 'entier')),
        depuisVersion(4, champ('justificatif', 'document')),
        depuisVersion(4, champ('catalogue_id', 'texte')),
        depuisVersion(4, choix('nature_source', NATURES_SOURCE)),
      ],
    },

    compteurs: {
      fichier: 'compteurs.csv',
      cle: 'id',
      identifiant: { prefixe: 'CPT-', chiffres: 4, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        reference('equipement_id', 'equipements'),
        champ('libelle', 'texte'),
        champ('unite', 'texte'),
      ],
    },

    releves: {
      fichier: 'releves.csv',
      cle: 'id',
      identifiant: { prefixe: 'REL-', chiffres: 6, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        reference('compteur_id', 'compteurs'),
        champ('date', 'date'),
        champ('valeur', 'decimal'),
        champ('utilisateur', 'texte'),
      ],
    },

    controles_reglementaires: {
      fichier: 'controles_reglementaires.csv',
      cle: 'id',
      identifiant: { prefixe: 'CTR-', chiffres: 4, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        reference('equipement_id', 'equipements'),
        champ('nature', 'texte'),
        champ('texte_reference', 'texte'),
        champ('periodicite_mois', 'entier'),
        champ('organisme', 'texte'),
        champ('derniere_date', 'date'),
        champ('prochaine_date', 'date'),
        champ('rapport', 'document'),
        champ('observations', 'texte_long'),
        booleen('observations_levees'),
        // Version 4 du format (2.2, CS171, D184) : périodicité tirée du catalogue Prévo ou saisie (défaut : avant la
        // 2.2, toute périodicité a été saisie) ; catalogue_id = C01 à C31, catalogue_relu_le = AAAA-MM-JJ
        depuisVersion(4, choix('source_periodicite', ['catalogue', 'saisie'], { defaut: 'saisie' })),
        depuisVersion(4, choix('nature_source', NATURES_SOURCE)),
        depuisVersion(4, champ('catalogue_id', 'texte')),
        depuisVersion(4, champ('catalogue_relu_le', 'date')),
      ],
    },

    codes_defaillance: {
      fichier: 'codes_defaillance.csv',
      cle: 'id',
      identifiant: { prefixe: 'CD-', chiffres: 4, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        choix('famille', ['symptôme', 'cause', 'remède'], { obligatoire: true }),
        champ('code', 'texte', { obligatoire: true }),
        champ('libelle', 'texte', { obligatoire: true }),
      ],
    },

    fournisseurs: {
      fichier: 'fournisseurs.csv',
      cle: 'id',
      identifiant: { prefixe: 'FOU-', chiffres: 4, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        champ('nom', 'texte', { synonymes: ['fournisseur', 'raison sociale', 'société'] }),
        champ('contact', 'texte', { synonymes: ['interlocuteur', 'nom du contact'] }),
        champ('telephone', 'texte', { protege: true, synonymes: ['téléphone', 'tél', 'tel', 'portable'] }),
        champ('email', 'texte', { synonymes: ['e-mail', 'mail', 'courriel', 'adresse mail'] }),
      ],
    },

    achats: {
      fichier: 'achats.csv',
      cle: 'id',
      identifiant: { prefixe: 'ACH-', chiffres: 4, annuel: false },
      ajoutSeul: false,
      champs: [
        identifiantChamp(),
        champ('date', 'date'),
        reference('article_id', 'articles'),
        reference('fournisseur_id', 'fournisseurs'),
        champ('quantite', 'decimal'),
        champ('prix_unitaire', 'decimal'),
        choix('statut', ['demandée', 'commandée', 'reçue'], { defaut: 'demandée' }),
        champ('date_reception', 'date'),
      ],
    },

    parametres: {
      fichier: 'parametres.csv',
      cle: 'cle',                      // pas d'identifiant calculé : la clé est saisie
      ajoutSeul: false,
      champs: [
        champ('cle', 'id'),
        champ('valeur', 'texte'),
      ],
    },

    journal: {
      fichier: 'journal.csv',
      cle: 'id',
      // J-AAAAMMJJHHMMSS-XXXX : « chiffres » = nombre de caractères aléatoires finaux.
      identifiant: { prefixe: 'J-', chiffres: 4, annuel: false, horodate: true },
      ajoutSeul: true,                 // écriture par ajout (ARCHITECTURE.md §5.4)
      champs: [
        identifiantChamp(),
        champ('date_heure', 'date_heure'),
        champ('poste', 'texte'),
        champ('profil', 'texte'),
        champ('table', 'texte'),
        champ('id_ligne', 'texte'),
        champ('action', 'texte'),
      ],
    },

    // Format 3 (lot 6 refondu, ARCHITECTURE.md §20.2) : le wiki de maintenance. Une base plus ancienne n'a pas
    // ces fichiers : tables vides, créées à la première écriture. Seules les pages qui ont un texte validé ont
    // une ligne ; les pages d'équipement et d'article existent toujours, calculées (§20.3). Refonte 2 (§20.12) :
    // trois types de textes ; « mode » est retiré (une panne est une page calculée) : une ancienne ligne de ce
    // type reste lue, signalée « type de page retiré ». `cause_code` reste une colonne du format 3, inutilisée.
    wiki_pages: {
      fichier: 'wiki_pages.csv',
      cle: 'id',
      identifiant: { prefixe: 'WP-', chiffres: 4, annuel: false },
      ajoutSeul: false,
      depuisVersion: 3,
      champs: [
        identifiantChamp(),
        choix('type', ['équipement', 'composant', 'savoir-faire'], { obligatoire: true, retirees: ['mode'] }),
        champ('titre', 'texte', { obligatoire: true }),
        champ('cle', 'texte'),
        reference('equipement_id', 'equipements'),
        reference('article_id', 'articles'),
        codeDefaillance('cause_code', 'cause'),
        reference('rattache_a', 'wiki_pages'),
        champ('texte', 'texte_long'),
        champ('ot_cites', 'texte'),
        champ('liens', 'texte'),
        champ('version', 'entier', { defaut: '0' }),
        choix('origine', ['IA', 'manuel', 'IA et manuel']),
        champ('modele', 'texte'),
        reference('derniere_entree', 'wiki_journal'),
        champ('valide_par', 'texte'),
        champ('valide_le', 'date_heure'),
        champ('cree_le', 'date_heure'),
        champ('modifie_le', 'date_heure'),
        choix('statut', ['active', 'archivée'], { defaut: 'active' }),
      ],
    },

    // Journal du wiki (§20.2) : une ligne par OT ingéré, par écriture à la main et par décision sur une
    // contradiction. Les changements et les contradictions sont du JSON dans un champ texte long.
    wiki_journal: {
      fichier: 'wiki_journal.csv',
      cle: 'id',
      identifiant: { prefixe: 'WJ-', chiffres: 5, annuel: false },
      ajoutSeul: false,
      depuisVersion: 3,
      champs: [
        identifiantChamp(),
        choix('nature', ['ingestion', 'manuel', 'décision'], { obligatoire: true }),
        reference('ot_id', 'ordres_travail'),
        champ('date_intervention', 'date_heure'),
        choix('statut', ['en file', 'à valider', 'validée', 'rejetée', 'à refaire', 'refusée',
          'rien à ajouter', 'appliquée'], { obligatoire: true }),
        booleen('anterieure'),
        champ('ordre', 'entier'),
        champ('pages', 'texte'),
        champ('changements', 'texte_long'),
        champ('contradictions', 'texte_long'),
        champ('raisons', 'texte_long'),
        champ('modele', 'texte'),
        champ('essais', 'entier', { defaut: '0' }),
        champ('cree_le', 'date_heure'),
        champ('traite_le', 'date_heure'),
        champ('decide_par', 'texte'),
        champ('decide_le', 'date_heure'),
        champ('motif', 'texte_long'),
      ],
    },

    // Format 4 (version 2.2) : une base plus ancienne n'a pas ces fichiers. Réserves des contrôles (D183) : une
    // ligne par réserve d'un rapport ; « levee » dit si elle est levée (une réserve reprise des observations levées
    // de la 2.1 est levée sans date de levée). Identifiants non annuels : la reprise doit donner les mêmes
    // identifiants dans le navigateur et dans serveur.py, sans date. Pas de champ actif (comme les contrôles).
    reserves_controle: {
      fichier: 'reserves_controle.csv',
      cle: 'id',
      identifiant: { prefixe: 'RES-', chiffres: 5, annuel: false },
      ajoutSeul: false,
      depuisVersion: 4,
      champs: [
        identifiantChamp(),
        reference('controle_id', 'controles_reglementaires', { obligatoire: true }),
        champ('date_controle', 'date'),
        champ('texte', 'texte_long', { obligatoire: true }),
        choix('gravite', ['mineure', 'majeure', 'critique']),
        champ('echeance_levee', 'date'),
        booleen('levee'),
        champ('date_levee', 'date'),
        champ('commentaire_levee', 'texte_long'),
        reference('ot_id', 'ordres_travail'),
      ],
    },

    // Garanties des équipements (format 4) : une garantie saisie par erreur se désactive (actif), jamais supprimée.
    garanties: {
      fichier: 'garanties.csv',
      cle: 'id',
      identifiant: { prefixe: 'GAR-', chiffres: 4, annuel: false },
      ajoutSeul: false,
      depuisVersion: 4,
      champs: [
        identifiantChamp(),
        reference('equipement_id', 'equipements', { obligatoire: true }),
        reference('fournisseur_id', 'fournisseurs'),
        champ('date_debut', 'date'),
        champ('date_fin', 'date', { obligatoire: true }),
        champ('conditions', 'texte_long'),
        champ('document', 'document'),
        champActif(),
      ],
    },

    // Contrats de prestataires (format 4, D190) : equipement_ids = identifiants séparés par « ; » (EQ-0001;EQ-0004),
    // comme wiki_pages.ot_cites ; perimetre = texte libre ; préavis et reconduction en mois ; montant annuel HT.
    contrats_prestataires: {
      fichier: 'contrats_prestataires.csv',
      cle: 'id',
      identifiant: { prefixe: 'CTP-', chiffres: 4, annuel: false },
      ajoutSeul: false,
      depuisVersion: 4,
      champs: [
        identifiantChamp(),
        reference('fournisseur_id', 'fournisseurs', { obligatoire: true }),
        champ('objet', 'texte', { obligatoire: true }),
        champ('equipement_ids', 'texte'),
        champ('perimetre', 'texte_long'),
        champ('date_debut', 'date'),
        champ('date_fin', 'date', { obligatoire: true }),
        champ('preavis_mois', 'entier'),
        booleen('reconduction_tacite'),
        champ('reconduction_mois', 'entier'),
        champ('montant_annuel', 'decimal'),
        champ('document', 'document'),
        champActif(),
      ],
    },
  };

  // ---------------------------------------------------------------------------
  // Libellés (chantier multilingue, contrat du Lot 2) : lus dans la langue active à chaque lecture, jamais figés
  // au chargement — schema.tables.<table> (table) et schema.<table>.<champ> (champ) dans js/i18n/<langue>.js.
  // Accesseurs énumérables : JSON.stringify(Schema.tables) et Object.assign({}, champ) les lisent comme une
  // propriété ordinaire. Un champ « choix » porte aussi nomTable (le nom de sa table), qui suit ses copies :
  // l'affichage de ses valeurs passe par libelleValeur (D155).
  // ---------------------------------------------------------------------------

  Object.keys(tables).forEach(function (nomTable) {
    const description = tables[nomTable];
    Object.defineProperty(description, 'libelle', {
      enumerable: true,
      configurable: true,
      get: function () { return I18n.t('schema.tables.' + nomTable); },
    });
    description.champs.forEach(function (champDefini) {
      Object.defineProperty(champDefini, 'libelle', {
        enumerable: true,
        configurable: true,
        // {devise} : symbole de la devise réglée (T304) dans les libellés de montants ; « € » si UI n'est pas chargé.
        get: function () {
          return I18n.t('schema.' + nomTable + '.' + champDefini.nom,
            { devise: typeof UI !== 'undefined' && UI.symboleDevise ? UI.symboleDevise() : '€' });
        },
      });
      if (champDefini.type === 'choix') { champDefini.nomTable = nomTable; }
    });
  });

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

  // Noms des 27 tables, dans l'ordre du brief puis celles ajoutées par les versions du format.
  function nomsTables() {
    return Object.keys(tables);
  }

  // Texte affiché d'une valeur stockée d'une liste (D155) : la valeur écrite dans les fichiers ne change jamais, seul
  // son affichage passe par valeurs.<table>.<champ>.<valeur>. Une valeur hors de la liste du champ (vide, inconnue,
  // ou champ qui n'est pas un « choix ») est rendue telle quelle ; une valeur retirée garde son libellé.
  function libelleValeur(nomTable, nomChamp, valeur) {
    const texte = valeur === null || valeur === undefined ? '' : String(valeur);
    const champTrouve = champDeTable(nomTable, nomChamp);
    if (!champTrouve || champTrouve.type !== 'choix') { return texte; }
    if (champTrouve.valeurs.concat(champTrouve.retirees || []).indexOf(texte) < 0) { return texte; }
    return I18n.t('valeurs.' + nomTable + '.' + nomChamp + '.' + texte);
  }

  return {
    version: 4,                        // version du format des fichiers (ARCHITECTURE.md §14.1, §20.2 ; 4 : 2.2)
    tables: tables,
    table: table,
    champ: champDeTable,
    nomsTables: nomsTables,
    libelleValeur: libelleValeur,
  };
})();
