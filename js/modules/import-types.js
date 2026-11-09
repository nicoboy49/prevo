'use strict';
// Import (1b/8) — types de données de l'assistant d'import (T486, sortis de import-regles.js au plafond D28 ;
// ARCHITECTURE.md §18.2) : champs importables, clé naturelle, références, règles par type. Chargé juste
// après import-regles.js, qui lit Import.TYPES et Import.REGLES au moment de l'appel (jamais au chargement).
// Libellés et aides : fonctions lues à l'affichage. Relu sans navigateur par outils/generer_fiche_csv.py
// (section « 2. Types de données » jusqu'au repère « Fin des types »).

(() => {
  const texte = Import.interne.texte;
  const cleTexte = Import.interne.cleTexte;
  const CLE_REPERE = Import.interne.CLE_REPERE;
  const CLE_NOM = Import.interne.CLE_NOM;
  // ===== 2. Types de données (§18.2) ============================================================
  // Champs importables, clé naturelle, références. `synonymes` : ceux du schéma, complétés ici (texte
  // « a|b|c »). `exemple` : une valeur valable pour la base de démo (modèles à remplir, §18.8 ; des données, D146).
  // Libellés et aides : lus à l'affichage (accesseurs), jamais figés au chargement du module.
  const avecSynonymes = (options, liste) => Object.assign({}, options, { synonymes: (liste ? liste.split('|') : []).concat((options && options.synonymes) || []) });
  // Champs du schéma, dans l'ordre donné : { nom: exemple } ou { nom: [exemple, 'synonymes|ajoutés', options] }.
  const S = (table, exemples) => Object.keys(exemples).map((nom) => {
    const [champ, [exemple, liste, options]] = [Schema.champ(table, nom), [].concat(exemples[nom])];
    const extra = avecSynonymes(options, liste);
    return Object.assign({ cle: nom, get libelle() { return Schema.champ(table, nom).libelle; }, table, champ: nom, type: champ.type, valeurs: champ.valeurs || null,
      obligatoire: champ.obligatoire === true, protege: champ.protege === true, defaut: champ.defaut === undefined ? null : champ.defaut,
      cleNaturelle: false, exemple }, extra, { synonymes: (champ.synonymes || []).concat(extra.synonymes) });
  });
  // Champ « virtuel » propre à l'import (chemin, référence par clé naturelle, stock initial…) ; libelle : fonction.
  const V = (cle, libelle, type, exemple, liste, options) => Object.assign({ cle, get libelle() { return libelle(); }, table: null, champ: null, type, valeurs: null,
    obligatoire: false, protege: false, defaut: null, cleNaturelle: false, exemple }, avecSynonymes(options, liste));
  const [CLE, NATUREL, FACULTATIF] = [{ obligatoire: true, cleNaturelle: true }, { cleNaturelle: true }, { obligatoire: false }];
  const SITE = 'Site des Trois Vallées';
  const CHEMIN = 'chemin|chemin de localisation|localisation|emplacement|lieu|zone';
  const NIVEAU = { ref: 'localisations', ecrit: 'localisation_id', table: 'equipements' };
  const reference = (table, ref, ecrit, options) => Object.assign({ table, ref, ecrit }, options);
  const equipementDe = (table) => V('equipement', () => I18n.t('commun.champ.equipement'), 'texte', 'CP-01', 'équipement (repère)|repère|repère équipement|machine|code machine|tag',
    reference(table, 'equipements', 'equipement_id', Object.assign({ protege: true }, CLE)));
  // libelle, aide : fonctions (lues à l'affichage).
  function type(cle, libelle, aide, tables, groupes) {
    const champs = [].concat(...groupes);
    return { cle, get libelle() { return libelle(); }, get aide() { return aide(); }, tables, champs, refs: champs.filter((c) => c.ref).map((c) => ({ champ: c.cle, table: c.ref, creee: ['localisations', 'fournisseurs'].includes(c.ref) })) };
  }
  const TYPES = {
    localisations: type('localisations', () => I18n.t('import.type.localisations'), () => I18n.t('import.type_aide.localisations'), ['localisations'], [
      V('chemin', () => I18n.t('import.champ.chemin'), 'texte', SITE + ' > Atelier Usinage > Ligne de reprise', CHEMIN + '|libellé|nom', reference('localisations', 'localisations', null, CLE)),
      S('localisations', { type: ['ligne', 'niveau', FACULTATIF] })]),
    equipements: type('equipements', () => I18n.t('import.type.equipements'), () => I18n.t('import.type_aide.equipements'), ['localisations', 'equipements'], [
      S('equipements', { repere: ['MA-01', '', NATUREL], designation: "Machine d'exemple" }),
      V('chemin_localisation', () => I18n.t('import.champ.chemin_localisation'), 'texte', SITE + ' > Atelier Usinage', CHEMIN, NIVEAU),
      V('site', () => I18n.t('import.champ.site'), 'texte', SITE, 'usine', Object.assign({ niveau: 'site' }, NIVEAU)),
      V('atelier', () => I18n.t('import.champ.atelier'), 'texte', 'Atelier Usinage', 'secteur', Object.assign({ niveau: 'atelier' }, NIVEAU)),
      V('ligne', () => I18n.t('import.champ.ligne'), 'texte', "Cellule d'usinage CN", 'ligne de production|îlot', Object.assign({ niveau: 'ligne' }, NIVEAU)),
      V('parent', () => I18n.t('import.champ.parent'), 'texte', 'CU-01', 'parent|repère parent|repère du parent|ensemble|machine mère', reference('equipements', 'equipements', 'parent_id', { protege: true })),
      S('equipements', { marque: 'Aerovis', modele: 'AV 30 D', num_serie: '0012345', date_mes: '15/03/2021', criticite: ['B', 'classe de criticité'],
        statut: 'en service', heures_fonct_jour: '8', habilitation_requise: 'B1V', consignation: 'Couper le sectionneur et le cadenasser.',
        actif: ['oui', 'en activité'], valeur_remplacement: '12500',
        cout_arret_h: ['850', "coût d'arrêt|coût horaire d'arrêt|coût de l'arrêt|coût de l'arrêt (€/h)|coût d'arrêt horaire|coût de l'heure d'arrêt|perte de production horaire"] })]),
    articles: type('articles', () => I18n.t('import.type.articles'), () => I18n.t('import.type_aide.articles'), ['fournisseurs', 'articles', 'mouvements_stock'], [
      S('articles', { reference: ['ROU-099', '', NATUREL], designation: 'Roulement à billes 6308-2RS', fabricant: 'Rouloran', ref_fabricant: '6308-2RS', emplacement: 'A1-09', unite: 'u' }),
      V('stock_initial', () => I18n.t('import.champ.stock_initial'), 'decimal', '10', 'stock|quantité en stock|qté stock|stock actuel|quantité|qté', { table: 'mouvements_stock' }),
      S('articles', { stock_securite: '4', point_commande: '8', qte_commande: '20', delai_jours: '3', prix_unitaire: '9,50' }),
      V('fournisseur', () => I18n.t('import.champ.fournisseur'), 'texte', 'Mécaroule Distribution', 'nom du fournisseur|fournisseur principal', reference('articles', 'fournisseurs', 'fournisseur_id')),
      S('articles', { critique: ['non', 'critique|pièce critique'], actif: 'oui' })]),
    fournisseurs: type('fournisseurs', () => I18n.t('import.type.fournisseurs'), () => I18n.t('import.type_aide.fournisseurs'), ['fournisseurs'], [
      S('fournisseurs', { nom: ['Hydraulique Services', '', CLE], contact: 'Paul Martin', telephone: '0465710099', email: 'contact@hydraulique-demo.example' })]),
    techniciens: type('techniciens', () => I18n.t('import.type.techniciens'), () => I18n.t('import.type_aide.techniciens'), ['techniciens'], [
      S('techniciens', { nom: ['Durand', '', CLE], prenom: ['Paul', '', NATUREL], metier: 'Mécanicien', taux_horaire: '42', capacite_h_semaine: '35', actif: 'oui' })]),
    habilitations: type('habilitations', () => I18n.t('import.type.habilitations'), () => I18n.t('import.type_aide.habilitations'), ['habilitations'], [
      V('technicien', () => I18n.t('commun.champ.technicien'), 'texte', 'Julien Moreau', 'nom du technicien|intervenant|salarié|prénom nom|nom prénom|nom', reference('habilitations', 'techniciens', 'technicien_id', CLE)),
      S('habilitations', { intitule: ['H1V', '', CLE], date_obtention: '10/03/2025', date_echeance: '10/03/2028' })]),
    codes: type('codes', () => I18n.t('import.type.codes'), () => I18n.t('import.type_aide.codes'), ['codes_defaillance'], [
      S('codes_defaillance', { famille: ['cause', 'famille de code|catégorie', NATUREL], code: ['C99', 'code défaillance|n° de code', NATUREL],
        libelle: ['Usure par frottement', 'description|désignation|intitulé'] })]),
    compteurs: type('compteurs', () => I18n.t('import.type.compteurs'), () => I18n.t('import.type_aide.compteurs'), ['compteurs'], [equipementDe('compteurs'),
      S('compteurs', { libelle: ['Compteur de démarrages', 'compteur|nom du compteur', CLE], unite: ['démarrages', 'unité de mesure'] })]),
    controles: type('controles', () => I18n.t('import.type.controles'), () => I18n.t('import.type_aide.controles'), ['controles_reglementaires'], [equipementDe('controles_reglementaires'),
      S('controles_reglementaires', { nature: ['Inspection des soupapes de sécurité', 'nature|contrôle|intitulé|type de contrôle|vérification', CLE],
        texte_reference: ['Arrêté du 20 novembre 2017', 'référence réglementaire|réglementation|texte'], periodicite_mois: ['12', 'périodicité|périodicité mois|fréquence|fréquence mois'],
        organisme: ['Bureau Alpin de Contrôle (démo)', 'organisme|prestataire|bureau de contrôle'],
        derniere_date: ['15/01/2026', 'dernier contrôle|fait le|réalisé le'], prochaine_date: ['15/01/2027', 'prochain contrôle|échéance|à faire le'],
        observations: ['Aucune', 'remarques|réserves'], observations_levees: ['oui', 'réserves levées|levée'] })]),
    // Garanties et contrats (2.2, T487) : équipement par son repère (déjà dans Prévo) ; fournisseur ou prestataire par son
    // nom (créé s'il manque, D88 a) ; équipements concernés d'un contrat : repères séparés par des virgules (ou « ; »),
    // écrits en identifiants séparés par « ; » (equipement_ids, un repère inconnu refuse la ligne) ; montant annuel
    // facultatif, dans la devise réglée, hors taxes (D190). Contrôles : Garanties.verifierGarantie et verifierContrat.
    garanties: type('garanties', () => I18n.t('import.type.garanties'), () => I18n.t('import.type_aide.garanties'), ['fournisseurs', 'garanties'], [equipementDe('garanties'),
      S('garanties', { date_fin: ['31/03/2028', "fin de garantie|garantie jusqu'au|échéance|échéance de garantie|date de fin|fin|expire le|valable jusqu'au", CLE],
        date_debut: ['01/04/2026', "début de garantie|début|date de début|garantie depuis|date d'achat"] }),
      V('fournisseur', () => I18n.t('import.champ.fournisseur'), 'texte', 'Fluidalpes Services', 'nom du fournisseur|garant|vendeur', reference('garanties', 'fournisseurs', 'fournisseur_id')),
      S('garanties', { conditions: ["Pièces et main-d'œuvre, déplacement inclus.", 'conditions de garantie|couverture|ce qui est couvert'] })]),
    contrats: type('contrats', () => I18n.t('import.type.contrats'), () => I18n.t('import.type_aide.contrats'), ['fournisseurs', 'contrats_prestataires'], [
      V('prestataire', () => I18n.t('import.champ.prestataire'), 'texte', 'Fluidalpes Services', 'nom du prestataire|fournisseur|société|entreprise|sous-traitant|titulaire|titulaire du contrat',
        reference('contrats_prestataires', 'fournisseurs', 'fournisseur_id', CLE)),
      S('contrats_prestataires', { objet: ['Maintenance du groupe froid', 'objet|intitulé|intitulé du contrat|libellé|contrat|prestation|nature de la prestation', CLE] }),
      V('equipements_concernes', () => I18n.t('import.champ.equipements_concernes'), 'texte', 'GF-01, CP-01', 'équipements|repères|machines|équipements couverts|repères des équipements|parc concerné',
        { table: 'contrats_prestataires', ecrit: 'equipement_ids', liste: 'equipements', protege: true }),
      S('contrats_prestataires', { perimetre: ["Deux visites par an, pièces d'usure comprises.", 'périmètre|étendue|description|zone couverte'],
        date_debut: ['01/01/2026', "début|date de début|début du contrat|prise d'effet|date d'effet|signé le"],
        date_fin: ['31/12/2026', 'fin|date de fin|fin du contrat|échéance|échéance du contrat|expire le|terme|fin de la période'],
        preavis_mois: ['3', 'préavis|préavis (mois)|préavis de résiliation|délai de préavis|préavis en mois'],
        reconduction_tacite: ['oui', 'tacite reconduction|reconduction|renouvellement automatique|reconduction automatique'],
        reconduction_mois: ['12', 'durée de reconduction|reconduction (mois)|durée du renouvellement|renouvellement (mois)'],
        montant_annuel: ['4800', 'montant annuel ht|montant annuel|montant|montant ht|coût annuel|prix annuel|redevance annuelle'] })]),
    gammes: type('gammes', () => I18n.t('import.type.gammes'), () => I18n.t('import.type_aide.gammes'), ['gammes', 'gamme_operations'], [equipementDe('gammes'),
      S('gammes', { libelle: ['Graissage annuel du compresseur', 'gamme|nom de la gamme|intitulé', CLE], declencheur: ['date', 'type de déclenchement'],
        periodicite_jours: ['365', 'périodicité|périodicité jours|fréquence|fréquence jours'] }),
      V('compteur', () => I18n.t('import.champ.compteur'), 'texte', 'Compteur horaire de marche', 'compteur associé', reference('gammes', 'compteurs', 'compteur_id')),
      S('gammes', { periodicite_unites: ['2000', 'périodicité compteur|périodicité unités'], seuil: '0,8', avance_jours: ['7', 'avance'],
        derniere_realisation: ['15/01/2026', 'dernière visite|fait le'], releve_derniere_realisation: '14000',
        prochaine_echeance: ['15/01/2027', 'échéance|prochaine visite'], temps_prevu_h: ['1,5', 'temps prévu|durée|durée prévue'],
        consignes: ['Consigner avant intervention.', 'consignes de sécurité'], actif: 'oui' }),
      V('operations', () => I18n.t('import.champ.operations'), 'texte_long', 'Graisser les paliers ; Contrôler le moteur', 'opération|tâche|tâches|liste des opérations|travail à faire', { table: 'gamme_operations' }),
      V('valeur_attendue', () => I18n.t('import.champ.valeur_attendue'), 'texte_long', 'Graisse visible ; Pas de bruit', 'valeurs attendues|critère|attendu', { table: 'gamme_operations' })]),
    // Champs déclarés ici ; règles dans import-historique.js (Import.preparerHistorique, §18.6).
    historique: type('historique', () => I18n.t('import.type.historique'), () => I18n.t('import.type_aide.historique'), ['ordres_travail', 'ot_temps'], [
      V('ancien_numero', () => I18n.t('import.champ.ancien_numero'), 'texte', 'BT-2024-0153', "n° ot|n° d'ot|numéro d'ot|numéro ot|ancien numéro|n° intervention|numéro intervention|n° bon|bon de travail",
        { table: 'ordres_travail', cleNaturelle: true, protege: true }),
      Object.assign(equipementDe('ordres_travail'), { cleNaturelle: false }),
      S('ordres_travail', { type: ['correctif différé', "type d'intervention|nature|nature de l'intervention", FACULTATIF], priorite: ['P3', 'priorité|urgence', FACULTATIF],
        titre: ['Remplacement du filtre à air', 'objet|intitulé|libellé|désignation', FACULTATIF],
        compte_rendu: ['Filtre remplacé, essais concluants.', 'compte-rendu|commentaire|travaux réalisés|description|observations|rapport'],
        date_creation: ['12/03/2024 08:15', 'date|date de la demande|date demande|créé le'], date_debut: ['12/03/2024 09:00', "début|date intervention|date d'intervention"],
        date_fin: ['12/03/2024 11:30', 'fin|terminé le|date de clôture'], arret_production: ['oui', 'arrêt|arrêt prod|arrêt production'],
        duree_arret_h: ['2,5', "durée d'arrêt|durée arrêt|temps d'arrêt|heures d'arrêt"] }),
      V('symptome_code', () => I18n.t('import.champ.symptome_code'), 'texte', 'S01', 'symptôme', { table: 'ordres_travail', champ: 'symptome_code', ref: 'codes_defaillance', famille: 'symptôme' }),
      V('cause_code', () => I18n.t('import.champ.cause_code'), 'texte', 'C01', 'cause', { table: 'ordres_travail', champ: 'cause_code', ref: 'codes_defaillance', famille: 'cause' }),
      V('remede_code', () => I18n.t('import.champ.remede_code'), 'texte', 'R01', 'remède|action corrective', { table: 'ordres_travail', champ: 'remede_code', ref: 'codes_defaillance', famille: 'remède' }),
      V('technicien', () => I18n.t('commun.champ.technicien'), 'texte', 'Julien Moreau', 'intervenant|réalisé par|nom du technicien', reference('ordres_travail', 'techniciens', 'technicien_id')),
      V('temps_passe_h', () => I18n.t('import.champ.temps_passe_h'), 'decimal', '2,5', "temps passé|heures|durée intervention|temps|temps (h)|temps passé (h)|main d'oeuvre", { table: 'ot_temps' }),
      S('ordres_travail', { cout_soustraitance: ['0', 'sous-traitance|coût sous-traitance|coût externe'] })]),
  };
  const paire = (ref, nom) => (l) => texte(l[ref]) + '|' + cleTexte(l[nom]);
  // Prestataire d'un contrat : identifiant (base, ou fournisseur trouvé par son nom), ou fiche que l'import crée
  // (objet, distinguée par son nom : deux lignes du même prestataire nouveau ont la même clé).
  const prestataire = (valeur) => (valeur && typeof valeur === 'object' ? '+' + cleTexte(valeur.nom) : texte(valeur));
  // Table principale et clé naturelle de chaque type (même fonction pour la base et pour le fichier).
  const REGLES = {
    localisations: { table: 'localisations' }, equipements: { table: 'equipements', cle: CLE_REPERE },
    articles: { table: 'articles', cle: (l) => cleTexte(l.reference) }, fournisseurs: { table: 'fournisseurs', cle: CLE_NOM },
    techniciens: { table: 'techniciens', cle: (l) => cleTexte(l.nom) + '|' + cleTexte(l.prenom) },
    habilitations: { table: 'habilitations', cle: paire('technicien_id', 'intitule') }, codes: { table: 'codes_defaillance', cle: paire('famille', 'code') },
    compteurs: { table: 'compteurs', cle: paire('equipement_id', 'libelle') }, controles: { table: 'controles_reglementaires', cle: paire('equipement_id', 'nature') },
    garanties: { table: 'garanties', cle: paire('equipement_id', 'date_fin') },
    contrats: { table: 'contrats_prestataires', cle: (l) => prestataire(l.fournisseur_id) + '|' + cleTexte(l.objet) },
    gammes: { table: 'gammes', cle: paire('equipement_id', 'libelle') }, historique: { table: 'ordres_travail' },
  };
  // ===== Fin des types ===========================================================================

  Import.TYPES = TYPES;
  Import.REGLES = REGLES;
})();
