'use strict';
// Import (1/7) — assistant d'import des données existantes (lot 5, ARCHITECTURE.md §18) : types de
// données, correspondance des colonnes, conversion, clés naturelles, aperçu à blanc. Fonctions pures : rien
// n'est écrit dans la base (seule la mémoire du poste, localStorage « prevo.import », est écrite par
// memoriserCorrespondance). Fichiers du préfixe : import-regles.js (crée Import), import-historique.js,
// import-controles.js (T92), import-lecture.js, import-ecritures.js, import-modeles.js, import-ecrans.js,
// import-apercu.js.
// Aperçu (Import.preparer, §18.5) : 1re passe dans l'ordre du fichier (conversion, références qui doivent
// exister, clé naturelle, doublon dans le fichier, fiche existante ou à créer) ; 2e passe (parent,
// localisations et fournisseurs créés s'ils manquent — D88 a —, stock initial, opérations, action D84 a) ;
// contrôles des formulaires (T92) ; fin (parent refusé → enfant refusé, seules les références utilisées
// sont créées, identifiants).

const Import = (() => {
  /** Erreur de l'import (fichier illisible, trop grand, chiffré…) : message en français pour l'écran. */
  class ErreurImport extends Error {
    constructor(message) { super(message); this.name = 'ErreurImport'; }
  }

  // ===== 1. Petits outils =====================================================================
  const [CLE_MEMOIRE, MEMOIRE_MAX, PLAFOND_LIGNES] = ['prevo.import', 40, 20000];   // mémoire du poste ; plafond §18.3
  const ACTIONS = ['creer', 'mettre_a_jour', 'identique', 'refusee'];
  const GARDEES = new Set(['creer', 'mettre_a_jour']);
  const texte = (valeur) => (valeur === null || valeur === undefined ? '' : String(valeur).trim());
  const propre = (objet, cle) => (Object.prototype.hasOwnProperty.call(objet, cle) ? objet[cle] : undefined);
  const sansAccents = (valeur) => texte(valeur).normalize('NFD').replace(/\p{M}+/gu, '').toLowerCase();
  const estActif = (ligne) => texte(ligne && ligne.actif) !== '0';
  /** Texte comparable (§18.4) : minuscules, sans accents, ponctuation et espaces réduits (« N° de série » ≈ « n de serie »). */
  const comparable = (valeur) => sansAccents(valeur).replace(/œ/g, 'oe').replace(/æ/g, 'ae').replace(/[^a-z0-9]+/g, ' ').trim();
  /** Clé naturelle : casse, accents et espaces ignorés, ponctuation gardée (« CP-01 » ≠ « CP 01 »). */
  const cleTexte = (valeur) => sansAccents(valeur).replace(/\s+/g, ' ');
  /** « 0012.50 » → « 12.5 » : forme canonique d'un nombre déjà normalisé (point décimal). */
  function nombreCanonique(valeur) {
    const morceaux = /^(-?)(\d+)(?:\.(\d*))?$/.exec(valeur);
    if (!morceaux) return valeur;
    const decimales = (morceaux[3] || '').replace(/0+$/, '');
    const nombre = morceaux[2].replace(/^0+(?=\d)/, '') + (decimales ? '.' + decimales : '');
    return morceaux[1] && nombre !== '0' ? '-' + nombre : nombre;
  }

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
        actif: ['oui', 'en activité'], valeur_remplacement: '12500' })]),
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
  const [CLE_REPERE, CLE_NOM] = [(ligne) => cleTexte(ligne.repere), (ligne) => cleTexte(ligne.nom)];
  const paire = (ref, nom) => (l) => texte(l[ref]) + '|' + cleTexte(l[nom]);
  // Table principale et clé naturelle de chaque type (même fonction pour la base et pour le fichier).
  const REGLES = {
    localisations: { table: 'localisations' }, equipements: { table: 'equipements', cle: CLE_REPERE },
    articles: { table: 'articles', cle: (l) => cleTexte(l.reference) }, fournisseurs: { table: 'fournisseurs', cle: CLE_NOM },
    techniciens: { table: 'techniciens', cle: (l) => cleTexte(l.nom) + '|' + cleTexte(l.prenom) },
    habilitations: { table: 'habilitations', cle: paire('technicien_id', 'intitule') }, codes: { table: 'codes_defaillance', cle: paire('famille', 'code') },
    compteurs: { table: 'compteurs', cle: paire('equipement_id', 'libelle') }, controles: { table: 'controles_reglementaires', cle: paire('equipement_id', 'nature') },
    gammes: { table: 'gammes', cle: paire('equipement_id', 'libelle') }, historique: { table: 'ordres_travail' },
  };
  function typeDonnees(cle) {
    if (!propre(TYPES, cle)) throw new ErreurImport(I18n.t('import.erreur.type_inconnu', { type: texte(cle) }));
    return TYPES[cle];
  }
  const champDe = (description, cle) => description.champs.find((champ) => champ.cle === cle);

  // ===== 3. Conversion d'une cellule (§18.5, D85, D86) : jamais de valeur inventée ====================
  // Équivalences sûres des listes fermées (D86), montrées dans l'aperçu : texte comparable → valeur.
  const EQUIVALENCES = {
    'equipements.statut': { 'service': 'en service', 'en fonctionnement': 'en service', 'en marche': 'en service', 'a l arret': 'arrêt', 'arrete': 'arrêt', 'au rebut': 'rebut', 'reforme': 'rebut' },
    'equipements.criticite': { 'classe a': 'A', 'classe b': 'B', 'classe c': 'C' }, 'localisations.type': { 'usine': 'site', 'ligne de production': 'ligne' },
    'gammes.declencheur': { 'calendaire': 'date', 'calendrier': 'date' },
  };
  // Explication d'une valeur illisible, par type de champ (fonctions : textes lus à l'affichage).
  const EXPLICATIONS = { date: () => I18n.t('import.explication.date'), date_heure: () => I18n.t('import.explication.date_heure'),
    decimal: () => I18n.t('import.explication.decimal'), entier: () => I18n.t('import.explication.entier'), booleen: () => I18n.t('import.explication.booleen') };
  const MOTIF_ABIME_PAR_EXCEL = /^[0-9]+,[0-9]+E\+[0-9]+$|^#(NOM|NAME)\?$/i;
  function convertirChoix(champ, valeur) {
    const [lu, cherche] = [Donnees.normaliser.choix(valeur, champ.valeurs), comparable(valeur)];
    let trouvee = lu.ok ? lu.valeur : propre(EQUIVALENCES[champ.table + '.' + champ.champ] || {}, cherche);
    if (trouvee === undefined) trouvee = (champ.valeurs || []).find((v) => comparable(v) === cherche || comparable(v) + 's' === cherche);
    if (trouvee === undefined) return { valeur, erreur: I18n.t('import.convertir_choix.hors_valeurs', { valeurs: champ.valeurs.join(', ') }) };
    return comparable(trouvee) === cherche ? { valeur: trouvee } : { valeur: trouvee, note: I18n.t('import.convertir_choix.lu_comme', { valeur, trouvee }) };
  }
  /** Cellule → { valeur, erreur?, note? } selon le type du champ (texte gardé tel quel, D85). */
  function convertir(champ, brut) {
    let valeur = texte(brut);
    if (valeur === '') return { valeur: '' };
    if (champ.type === 'texte' || champ.type === 'texte_long') {
      const lue = Donnees.csv.relireValeur({ type: 'texte', protege: champ.protege === true }, valeur);
      return MOTIF_ABIME_PAR_EXCEL.test(lue) ? { valeur: lue, note: I18n.t('import.convertir.valeur_probablement_abimee_excel') } : { valeur: lue };
    }
    if (valeur.startsWith("'")) valeur = valeur.slice(1).trim();       // apostrophe de protection (§3.2)
    if (champ.type === 'choix') return convertirChoix(champ, valeur);
    let lu;
    if (champ.type === 'date') {
      lu = Donnees.normaliser.date(valeur);
      const avecHeure = lu.ok ? null : Donnees.normaliser.dateHeure(valeur);
      if (avecHeure && avecHeure.ok) lu = { ok: true, valeur: avecHeure.valeur.slice(0, 10) };
    } else if (champ.type === 'date_heure') lu = Donnees.normaliser.dateHeure(valeur);
    else if (champ.type === 'booleen') lu = Donnees.normaliser.booleen(valeur);
    else if (champ.type === 'decimal' || champ.type === 'entier') {
      lu = Donnees.normaliser[champ.type](valeur);
      if (lu.ok) lu.valeur = nombreCanonique(lu.valeur);
    } else return { valeur };
    return lu.ok ? { valeur: lu.valeur } : { valeur, erreur: EXPLICATIONS[champ.type]() };
  }
  /** Cellules d'une ligne → { valeurs, enErreur, erreurs, notes, vides, manquants } (champs dans l'ordre du type). */
  function lireCellules(description, colonnes, cellules) {
    const lu = { valeurs: {}, enErreur: new Set(), erreurs: [], notes: [], vides: [], manquants: [] };
    for (const champ of description.champs) {
      const colonne = colonnes.get(champ.cle);
      const brut = colonne === undefined ? '' : (cellules || [])[colonne];
      const resultat = colonne === undefined ? { valeur: '' } : convertir(champ, brut);
      if (resultat.note) lu.notes.push(I18n.t('import.lire_cellules.note', { champ: champ.libelle, note: resultat.note }));
      if (resultat.erreur) {
        lu.valeurs[champ.cle] = resultat.valeur;
        lu.enErreur.add(champ.cle);
        lu.erreurs.push(I18n.t('import.lire_cellules.erreur', { champ: champ.libelle, valeur: texte(brut), erreur: resultat.erreur }));
      } else if (resultat.valeur !== '') lu.valeurs[champ.cle] = resultat.valeur;
      else if (champ.obligatoire) (champ.cleNaturelle ? lu.erreurs : lu.manquants).push(colonne === undefined
        ? I18n.t('import.lire_cellules.obligatoire_sans_colonne', { champ: champ.libelle }) : I18n.t('import.lire_cellules.obligatoire_cellule_vide', { champ: champ.libelle }));
      else if (colonne !== undefined) lu.vides.push(champ);
    }
    return lu;
  }

  // ===== 4. Correspondance des colonnes (§18.4) et mémoire du poste =================================
  function nomsDuChamp(champ) {
    // Libellé de la langue active et libellé français (D155) ; champs virtuels : libellé actif seul.
    const enFrancais = champ.table ? I18n.reference(['schema', champ.table, champ.champ].join('.')) : '';
    const premiers = [champ.cle, champ.libelle, enFrancais, champ.champ].filter(Boolean).map(comparable);
    return { champ, premiers, seconds: champ.synonymes.map(comparable).filter((nom) => nom && !premiers.includes(nom)) };
  }
  const MOTS_VIDES = new Set(['date', 'dans', 'pour', 'avec', 'code', 'type', 'numero', 'nombre']);
  const motsDe = (nom) => nom.split(' ').filter((mot) => mot.length >= 4 && !MOTS_VIDES.has(mot));
  // Proximité d'un en-tête avec les noms d'un champ : 2 = l'un commence par l'autre, 1 = mot commun, 0 = rien.
  function proximite(entete, noms) {
    let score = 0;
    for (const nom of noms) {
      if (entete.length >= 3 && (entete.startsWith(nom + ' ') || nom.startsWith(entete + ' '))) return 2;
      if (motsDe(nom).some((mot) => motsDe(entete).includes(mot))) score = 1;
    }
    return score;
  }
  const TYPES_VERIFIES = new Set(['date', 'date_heure', 'decimal', 'entier', 'booleen']);
  // Vrai si au moins la moitié des valeurs d'exemple non vides se lisent dans le type du champ.
  function echantillonConforme(champ, valeurs) {
    const remplies = valeurs.filter((valeur) => texte(valeur) !== '');
    return !TYPES_VERIFIES.has(champ.type) || remplies.filter((valeur) => !convertir(champ, valeur).erreur).length * 2 >= remplies.length;
  }
  /**
   * En-têtes → [{ colonne, entete, champ, statut, raison }] ; statut : sure, a_confirmer, non_utilisee.
   * memoire : tableau retenu (correspondanceRetenue), undefined ou 'auto' = mémoire du poste, null = aucune.
   */
  function correspondance(type, entetes, echantillon, memoire) {
    const description = typeDonnees(type);
    const liste = (entetes || []).map((entete, colonne) => ({ colonne, entete: texte(entete), champ: '', statut: 'non_utilisee', raison: '' }));
    const retenue = memoire === undefined || memoire === 'auto' ? correspondanceRetenue(type, entetes) : memoire;
    if (Array.isArray(retenue) && retenue.length === liste.length) {
      return liste.map((ligne, colonne) => Object.assign(ligne, champDe(description, retenue[colonne])
        ? { champ: retenue[colonne], statut: 'sure', raison: I18n.t('import.correspondance.retenue_lors_import_precedent') } : { raison: I18n.t('import.correspondance.non_utilisee_lors_import') }));
    }
    const exemples = (colonne) => (echantillon || []).slice(0, 50).map((cellules) => (cellules || [])[colonne]);
    const noms = description.champs.map(nomsDuChamp);
    const propositions = [];
    for (const ligne of liste) {
      const cherche = comparable(ligne.entete);
      if (!cherche) { ligne.raison = I18n.t('import.correspondance.colonne_sans_titre'); continue; }
      for (const niveau of [1, 2]) {
        const champs = noms.filter((n) => (niveau === 1 ? n.premiers : n.seconds).includes(cherche)).map((n) => n.champ);
        if (champs.length) { propositions.push({ ligne, niveau, champs }); break; }
      }
    }
    // Un champ = une colonne : titre exact d'abord, puis synonyme ; à niveau égal, la première colonne.
    propositions.sort((a, b) => a.niveau - b.niveau || a.ligne.colonne - b.ligne.colonne);
    const pris = new Map();
    for (const { ligne, niveau, champs } of propositions) {
      const champ = champs.find((c) => !pris.has(c.cle));
      if (!champ) {
        const autre = pris.get(champs[0].cle);
        if (autre.niveau === niveau) Object.assign(autre.ligne, { statut: 'a_confirmer', raison: I18n.t('import.correspondance.deux_colonnes', { champ: champs[0].libelle, premiere: autre.ligne.entete, seconde: ligne.entete }) });
        Object.assign(ligne, { statut: 'a_confirmer', raison: I18n.t('import.correspondance.meme_champ', { entete: autre.ligne.entete, champ: champs[0].libelle }) });
        continue;
      }
      pris.set(champ.cle, { ligne, niveau });
      ligne.champ = champ.cle;
      if (champs.length > 1) Object.assign(ligne, { statut: 'a_confirmer', raison: I18n.t('import.correspondance.plusieurs_champs', { champs: champs.map((c) => c.libelle).join(', ') }) });
      else if (!echantillonConforme(champ, exemples(ligne.colonne))) Object.assign(ligne, { statut: 'a_confirmer', raison: I18n.t('import.correspondance.titre_reconnu_mais_valeurs', { champLibelle: champ.libelle }) });
      else Object.assign(ligne, { statut: 'sure', raison: niveau === 1 ? I18n.t('import.correspondance.titre_reconnu') : I18n.t('import.correspondance.synonyme_champ_libelle', { champLibelle: champ.libelle }) });
    }
    for (const ligne of liste.filter((l) => l.statut === 'non_utilisee' && !l.raison)) {
      let [meilleur, score] = [null, 0];
      for (const n of noms) {
        const s = pris.has(n.champ.cle) ? 0 : proximite(comparable(ligne.entete), n.premiers.concat(n.seconds));
        if (s > score) [score, meilleur] = [s, n.champ];
      }
      if (!meilleur) { ligne.raison = I18n.t('import.correspondance.aucun_champ_reconnu'); continue; }
      pris.set(meilleur.cle, { ligne, niveau: 3 });
      Object.assign(ligne, { champ: meilleur.cle, statut: 'a_confirmer', raison: I18n.t('import.correspondance.titre_proche', { meilleurLibelle: meilleur.libelle }) });
    }
    return liste;
  }
  // localStorage peut être refusé (navigation privée, réglage) ou abîmé : on continue sans mémoire.
  function lireMemoire() {
    try {
      const objet = JSON.parse(window.localStorage.getItem(CLE_MEMOIRE) || '{}');
      return objet && typeof objet === 'object' && !Array.isArray(objet) ? objet : {};
    } catch (erreur) { return {}; }
  }
  const cleMemoire = (type, entetes) => type + '|' + (entetes || []).map(comparable).join('|');
  /** Retient sur le poste la correspondance validée (champ par colonne) ; renvoie ce qui est retenu. */
  function memoriserCorrespondance(type, entetes, liste) {
    typeDonnees(type);
    const champs = (entetes || []).map((_, colonne) => {
      const entree = (liste || []).find((e) => Number(e.colonne) === colonne);
      return entree && entree.statut !== 'non_utilisee' ? texte(entree.champ) : '';
    });
    const [memoire, cle] = [lireMemoire(), cleMemoire(type, entetes)];
    delete memoire[cle];
    memoire[cle] = champs;
    Object.keys(memoire).slice(0, Math.max(0, Object.keys(memoire).length - MEMOIRE_MAX)).forEach((ancienne) => { delete memoire[ancienne]; });
    try { window.localStorage.setItem(CLE_MEMOIRE, JSON.stringify(memoire)); } catch (erreur) { /* sans mémoire : tant pis */ }
    return champs;
  }
  /** Champ retenu par colonne pour ce type et ce jeu d'en-têtes (comparables), ou null. */
  function correspondanceRetenue(type, entetes) {
    const champs = propre(lireMemoire(), cleMemoire(type, entetes));
    return Array.isArray(champs) && champs.length === (entetes || []).length ? champs.map(texte) : null;
  }

  // ===== 5. Références : localisations (arbre), équipements, techniciens, fournisseurs ===============
  const TYPE_SUIVANT = new Map([['', 'site'], ['site', 'atelier'], ['atelier', 'ligne']]);
  function ajouterNoeud(arbre, noeud, parent) {
    arbre.parents.set(noeud, parent);
    for (const [index, cle] of [[arbre.enfants, parent], [arbre.parLibelle, cleTexte(noeud.libelle)]]) index.set(cle, (index.get(cle) || []).concat([noeud]));
  }
  // Arbre des localisations : lignes de la base (jamais modifiées) et localisations prévues.
  function arbreDe(contexte) {
    if (!contexte.arbre) {
      contexte.arbre = { parents: new Map(), enfants: new Map(), parLibelle: new Map() };
      Donnees.lignes('localisations').forEach((l) => ajouterNoeud(contexte.arbre, l, (l.parent_id && Donnees.trouver('localisations', l.parent_id)) || null));
    }
    return contexte.arbre;
  }
  const enfantNomme = (arbre, parent, libelle) => (arbre.enfants.get(parent) || []).find((n) => cleTexte(n.libelle) === cleTexte(libelle)) || null;
  function cheminDe(arbre, noeud) {
    const morceaux = [];
    for (let n = noeud, garde = 0; n && garde < 50; n = arbre.parents.get(n) || null, garde += 1) morceaux.unshift(n.libelle);
    return morceaux.join(' > ');
  }
  /** « Site > Atelier > Ligne » (séparateur >, sinon / ou \) → { morceaux } ou { erreur }. */
  function decouperChemin(valeur) {
    const morceaux = texte(valeur).split(valeur.includes('>') ? '>' : /[\\/]/).map(texte);
    if (morceaux.includes('')) return { erreur: I18n.t('import.decouper_chemin.chemin_localisation_incomplet_niveau') };
    return morceaux.length > 3 ? { erreur: I18n.t('import.decouper_chemin.plus_trois_niveaux_site') } : { morceaux };
  }
  // Chemin [{ libelle, type }] → { noeud } (existant ou prévu) ou { erreur }. Premier niveau cherché parmi les sites,
  // sinon parmi toutes les localisations de ce nom (une seule) ; niveaux manquants prévus (D88 a), type déduit du niveau.
  function resoudreChemin(contexte, elements) {
    const arbre = arbreDe(contexte);
    let [parent, debut] = [enfantNomme(arbre, null, elements[0].libelle), 1];
    if (!parent) {
      const ancres = arbre.parLibelle.get(cleTexte(elements[0].libelle)) || [];
      if (ancres.length > 1) return { erreur: I18n.t('import.resoudre_chemin.plusieurs_localisations', { nom: elements[0].libelle }) };
      [parent, debut] = [ancres[0] || null, ancres.length];
    }
    for (const element of elements.slice(debut)) {
      let noeud = enfantNomme(arbre, parent, element.libelle);
      if (!noeud) {
        const typeNoeud = element.type || TYPE_SUIVANT.get(parent ? parent.type : '');
        if (!typeNoeud) return { erreur: I18n.t('import.resoudre_chemin.plus_trois_niveaux_sous', { cheminDe: cheminDe(arbre, parent) }) };
        noeud = nouvelleLigne('localisations', { libelle: element.libelle, type: typeNoeud });
        ajouterNoeud(arbre, noeud, parent);
        prevoir(contexte, 'localisations', noeud, null);
      }
      parent = noeud;
    }
    return { noeud: parent };
  }
  // Index « clé naturelle → ligne » d'une table de la base, la ligne active d'abord (une fois par aperçu).
  function indexDe(contexte, table, fonction) {
    if (!contexte.index.has(fonction)) {
      const index = new Map();
      Donnees.lignes(table).forEach((ligne) => { const deja = index.get(fonction(ligne)); if (!deja || (!estActif(deja) && estActif(ligne))) index.set(fonction(ligne), ligne); });
      contexte.index.set(fonction, index);
    }
    return contexte.index.get(fonction);
  }
  /** Équipement de la base par son repère (l'actif d'abord), ou null. */
  const trouverEquipement = (repere, contexte) => indexDe(contexte || nouveauContexte(), 'equipements', CLE_REPERE).get(cleTexte(repere)) || null;
  /** Technicien par « Prénom Nom », « Nom Prénom » ou, à défaut, par son seul nom → { id, ligne } ou { erreur }. */
  function trouverTechnicien(nom) {
    const [cherche, tous] = [cleTexte(nom), Donnees.lignes('techniciens')];
    let trouves = tous.filter((t) => [texte(t.prenom) + ' ' + texte(t.nom), texte(t.nom) + ' ' + texte(t.prenom)].map(cleTexte).includes(cherche));
    if (!trouves.length) trouves = tous.filter((t) => cleTexte(t.nom) === cherche);
    if (trouves.length > 1 && trouves.filter(estActif).length === 1) trouves = trouves.filter(estActif);
    if (trouves.length === 1) return { id: trouves[0].id, ligne: trouves[0] };
    return { erreur: trouves.length ? I18n.t('import.trouver_technicien.plusieurs_techniciens_appellent', { nom: texte(nom) }) : I18n.t('import.trouver_technicien.technicien_introuvable_prevo', { nom: texte(nom) }) };
  }
  function fournisseurNomme(contexte, nom) {
    const existant = indexDe(contexte, 'fournisseurs', CLE_NOM).get(cleTexte(nom));
    if (existant) return existant.id;
    if (!contexte.fournisseurs.has(cleTexte(nom))) contexte.fournisseurs.set(cleTexte(nom), prevoir(contexte, 'fournisseurs', nouvelleLigne('fournisseurs', { nom: texte(nom) }), null));
    return contexte.fournisseurs.get(cleTexte(nom));
  }
  // Texte montré pour une valeur (référence : chemin, repère, nom ou libellé de la fiche visée).
  function afficher(contexte, champ, valeur) {
    if (champ && champ.type === 'choix' && champ.table) return Schema.libelleValeur(champ.table, champ.champ, valeur);   // D155
    if (!champ || !champ.ref || champ.ref === 'codes_defaillance') return valeur;
    const ligne = valeur && (typeof valeur === 'object' ? valeur : Donnees.trouver(champ.ref, valeur));
    if (!ligne) return valeur ? String(valeur) : '';
    return champ.ref === 'localisations' ? cheminDe(arbreDe(contexte), ligne) : texte(ligne.repere || ligne.nom || ligne.libelle);
  }

  // ===== 6. Aperçu à blanc (§18.5) ===============================================================
  function nouveauContexte(type, options) {
    const reglages = options || {};
    return { type, description: type ? typeDonnees(type) : null, table: type ? REGLES[type].table : null, mettreAJour: reglages.mettreAJour !== false,
      premierNumero: Number.isInteger(reglages.numeroPremiereLigne) ? reglages.numeroPremiereLigne : 2,
      maintenant: texte(reglages.maintenant) || Donnees.maintenant(), utilisateur: reglages.utilisateur === undefined ? I18n.donnees('import.nouveau_contexte.responsable') : texte(reglages.utilisateur),
      colonnes: new Map(), lignes: [], crees: [], entrees: new Map(), cles: new Map(), vus: new Map(), index: new Map(), fournisseurs: new Map(), etats: new Map(), arbre: null };
  }
  /** Ligne complète d'une table : valeurs données, sinon `defaut` du schéma, sinon vide. */
  function nouvelleLigne(table, valeurs) {
    const ligne = {};
    Schema.table(table).champs.forEach((c) => { ligne[c.nom] = valeurs[c.nom] !== undefined ? valeurs[c.nom] : (c.defaut === undefined ? '' : c.defaut); });
    return ligne;
  }
  /** Note une ligne à créer (ligne de l'aperçu qui la crée, ou null pour une référence créée). */
  function prevoir(contexte, table, objet, ligne) {
    const entree = { table, objet, ligne };
    contexte.crees.push(entree);
    contexte.entrees.set(objet, entree);
    return objet;
  }
  function refuser(ligne, raisons) {
    Object.assign(ligne, { action: 'refusee', changements: [], cible: '' }).raisons.push(...[].concat(raisons));
  }
  /** Correspondance → Map « clé du champ → colonne » (ErreurImport si un champ est choisi deux fois). */
  function colonnesParChamp(description, liste) {
    const colonnes = new Map();
    for (const entree of liste || []) {
      const cle = texte(entree && entree.champ);
      if (!cle || entree.statut === 'non_utilisee') continue;
      const champ = champDe(description, cle);
      if (!champ) throw new ErreurImport(I18n.t('import.colonnes_par_champ.champ_inconnu', { cle, descriptionLibelle: description.libelle }));
      if (colonnes.has(cle)) throw new ErreurImport(I18n.t('import.colonnes_par_champ.champ_choisi_deux_colonnes', { champLibelle: champ.libelle }));
      colonnes.set(cle, Number(entree.colonne));
    }
    return colonnes;
  }
  function premierePasse(contexte, cellules, rang) {
    if (!(cellules || []).some((cellule) => texte(cellule) !== '')) return;          // ligne vide : ignorée
    const ligne = { numero: contexte.premierNumero + rang, rang, action: 'creer', raisons: [], valeurs: {}, changements: [], cible: '', _cibles: [] };
    contexte.lignes.push(ligne);
    if (rang >= PLAFOND_LIGNES) return refuser(ligne, I18n.t('import.lire_ligne.plafond', { n: PLAFOND_LIGNES }));
    const { description, table, type: typeLigne } = contexte;
    const lu = lireCellules(description, contexte.colonnes, cellules);
    const [v, brouillon, erreurs] = [ligne.valeurs = lu.valeurs, {}, lu.erreurs];
    ligne.raisons.push(...lu.notes);
    for (const champ of description.champs) {
      if (v[champ.cle] === undefined || lu.enErreur.has(champ.cle) || !champ.champ || champ.table !== table) continue;
      brouillon[champ.champ] = v[champ.cle];
      if (!champ.cleNaturelle) ligne._cibles.push({ champ, colonne: champ.champ, valeur: v[champ.cle] });
    }
    // Références qui doivent exister dans la base : équipement (repère), technicien (nom), compteur de l'équipement.
    const equipement = !erreurs.length && v.equipement !== undefined ? trouverEquipement(v.equipement, contexte) : undefined;
    if (equipement) brouillon.equipement_id = equipement.id;
    else if (equipement === null) erreurs.push(I18n.t('import.premiere_passe.equipement_introuvable_prevo', { equipement: v.equipement }));
    const technicien = !erreurs.length && v.technicien !== undefined ? trouverTechnicien(v.technicien) : {};
    if (technicien.id) brouillon.technicien_id = technicien.id;
    else if (technicien.erreur) erreurs.push(technicien.erreur);
    if (!erreurs.length && v.compteur !== undefined) {
      const compteur = Donnees.lignes('compteurs').find((c) => c.equipement_id === brouillon.equipement_id && cleTexte(c.libelle) === cleTexte(v.compteur));
      if (compteur) ligne._cibles.push({ champ: champDe(description, 'compteur'), colonne: 'compteur_id', valeur: brouillon.compteur_id = compteur.id });
      else erreurs.push(I18n.t('import.premiere_passe.compteur_introuvable_equipement', { compteur: v.compteur }));
    }
    ['chemin', 'chemin_localisation'].forEach((cle) => { const d = !erreurs.length && v[cle] !== undefined ? decouperChemin(v[cle]) : {}; if (d.erreur) erreurs.push(d.erreur); });
    if (erreurs.length) return refuser(ligne, erreurs);
    if (typeLigne === 'localisations') return;                                       // clé : chemin résolu ensuite
    const cle = REGLES[typeLigne].cle(brouillon);
    const premiere = contexte.cles.get(cle);
    if (premiere && typeLigne === 'gammes' && v.operations) { ligne._tete = premiere; return; }
    if (premiere) return refuser(ligne, I18n.t('import.premiere_passe.doublon_fichier_ligne', { numero: premiere.numero }));
    const existante = indexDe(contexte, table, REGLES[typeLigne].cle).get(cle) || null;
    if (!existante && lu.manquants.length) return refuser(ligne, lu.manquants);
    contexte.cles.set(cle, ligne);
    if (existante) { ligne._existante = existante; return; }
    ligne._objet = prevoir(contexte, table, nouvelleLigne(table, Object.assign(typeLigne === 'articles' ? { stock: '0' } : {}, brouillon)), ligne);
    for (const champ of lu.vides.filter((c) => c.defaut !== null && c.champ && c.table === table)) {
      const oui = champ.defaut === '1';
      const defaut = champ.type !== 'booleen' ? champ.defaut : (oui ? I18n.t('import.premiere_passe.oui') : I18n.t('import.premiere_passe.non'));
      ligne.raisons.push(I18n.t('import.premiere_passe.vide_defaut', { champ: champ.libelle, defaut }));
    }
  }
  function memeValeur(champ, avant, apres) {
    if (typeof apres === 'object') return false;
    const lu = champ && (champ.type === 'decimal' || champ.type === 'entier') ? Donnees.normaliser.decimal(avant) : null;
    return lu && lu.ok && lu.valeur !== '' ? nombreCanonique(lu.valeur) === apres : texte(avant) === apres;
  }
  // Action d'une ligne : créer (pas de fiche), sinon les colonnes importées non vides qui changent (D84 a).
  function decider(contexte, ligne, ajouts) {
    const existante = ligne._existante;
    if (!existante) { ligne.action = 'creer'; return; }
    ligne.cible = existante.id;
    const changes = {};
    for (const cible of ligne._cibles) {
      const avant = cible.avant !== undefined ? cible.avant : texte(existante[cible.colonne]);
      if (memeValeur(cible.champ, avant, cible.valeur)) continue;
      changes[cible.colonne] = cible.valeur;
      ligne.changements.push({ champ: cible.colonne, libelle: cible.champ.libelle, avant: afficher(contexte, cible.champ, avant), apres: afficher(contexte, cible.champ, cible.valeur) });
    }
    const nombre = Object.keys(changes).length;
    if (!nombre && !ajouts) ligne.action = 'identique';
    else if (!contexte.mettreAJour) Object.assign(ligne, { action: 'identique', changements: [] }).raisons.push(I18n.t('import.decider.deja_prevo_mise_jour'));
    else Object.assign(ligne, { action: 'mettre_a_jour', _modifier: nombre ? [{ table: contexte.table, id: existante.id, changes }] : [] });
  }
  const poserReference = (ligne, champ, colonne, valeur) => (ligne._objet ? (ligne._objet[colonne] = valeur) : ligne._cibles.push({ champ, colonne, valeur }));
  function secondeLocalisation(contexte, ligne) {
    const v = ligne.valeurs;
    const elements = decouperChemin(v.chemin).morceaux.map((libelle) => ({ libelle, type: '' }));
    elements[elements.length - 1].type = v.type || '';
    const resultat = resoudreChemin(contexte, elements);
    if (resultat.erreur) return refuser(ligne, resultat.erreur);
    const [noeud, entree] = [resultat.noeud, contexte.entrees.get(resultat.noeud)];
    const deja = entree ? entree.ligne : contexte.vus.get(noeud);
    if (deja) return refuser(ligne, I18n.t('import.premiere_passe.doublon_fichier_ligne', { numero: deja.numero }));
    if (entree) {                                     // prévue (par cette ligne ou comme parent d'une autre)
      entree.ligne = ligne;
      if (v.type) noeud.type = v.type;
      return Object.assign(ligne, { _objet: noeud, action: 'creer' });
    }
    contexte.vus.set(noeud, ligne);
    ligne._existante = noeud;
    decider(contexte, ligne);
  }
  function secondeEquipement(contexte, ligne) {
    const v = ligne.valeurs;
    if (v.parent !== undefined) {
      if (cleTexte(v.parent) === cleTexte(v.repere)) return refuser(ligne, I18n.t('import.seconde_equipement.equipement_peut_pas_etre'));
      const existant = trouverEquipement(v.parent, contexte);
      const duFichier = existant ? null : contexte.cles.get(cleTexte(v.parent));     // parent ailleurs dans le fichier
      if (!existant && !(duFichier && duFichier._objet)) return refuser(ligne, I18n.t('import.seconde_equipement.equipement_parent_introuvable_ni', { parent: v.parent }));
      ligne._parent = { valeur: existant ? existant.id : duFichier._objet, ligne: duFichier };
      poserReference(ligne, champDe(contexte.description, 'parent'), 'parent_id', ligne._parent.valeur);
    }
    const elements = v.chemin_localisation !== undefined ? decouperChemin(v.chemin_localisation).morceaux.map((libelle) => ({ libelle, type: '' }))
      : ['site', 'atelier', 'ligne'].filter((niveau) => v[niveau] !== undefined).map((niveau) => ({ libelle: v[niveau], type: niveau }));
    if (elements.length) {
      const resultat = resoudreChemin(contexte, elements);
      if (resultat.erreur) return refuser(ligne, I18n.t('import.seconde_equipement.localisation_erreur', { erreur: resultat.erreur }));
      poserReference(ligne, champDe(contexte.description, 'chemin_localisation'), 'localisation_id', contexte.entrees.has(resultat.noeud) ? resultat.noeud : resultat.noeud.id);
    }
    decider(contexte, ligne);
  }
  // Après la seconde passe : parent refusé → enfant refusé ; boucle de parents refusée (jusqu'à stabilité).
  function cascadeEquipements(contexte) {
    for (let change = true; change;) {
      change = false;
      const acceptees = contexte.lignes.filter((l) => GARDEES.has(l.action) && l._parent);
      const parents = new Map(acceptees.map((l) => [l._objet || l._existante.id, l._parent.valeur]));
      for (const ligne of acceptees) {
        const [parente, soi] = [ligne._parent.ligne, ligne._objet || ligne._existante.id];
        let raison = parente && parente.action === 'refusee' ? I18n.t('import.cascade_equipements.equipement_parent_refuse_ligne', { numero: parente.numero }) : '';
        for (let courant = ligne._parent.valeur, pas = 0; !raison && courant && pas < 1000; pas += 1) {
          if (courant === soi) raison = I18n.t('import.cascade_equipements.boucle_equipement_deviendrait_propre');
          courant = parents.has(courant) ? parents.get(courant) : (typeof courant === 'string' ? texte((Donnees.trouver('equipements', courant) || {}).parent_id) : '');
        }
        if (raison) { refuser(ligne, raison); change = true; }
      }
    }
  }
  function secondeArticle(contexte, ligne) {
    const [v, quantite] = [ligne.valeurs, ligne.valeurs.stock_initial];
    if (v.fournisseur !== undefined) poserReference(ligne, champDe(contexte.description, 'fournisseur'), 'fournisseur_id', fournisseurNomme(contexte, v.fournisseur));
    if (quantite !== undefined && ligne._objet) ligne._objet.stock = quantite;
    else if (quantite !== undefined) {
      ligne._cibles.push({ champ: champDe(contexte.description, 'stock_initial'), colonne: 'stock', valeur: quantite, avant: nombreCanonique(String(Donnees.stockArticle(ligne._existante.id))) });
    }
    decider(contexte, ligne);
    if (quantite === undefined || !(ligne.action === 'creer' || (ligne.action === 'mettre_a_jour' && ligne._modifier.some((m) => m.changes.stock !== undefined)))) return;
    prevoir(contexte, 'mouvements_stock', nouvelleLigne('mouvements_stock', { date: contexte.maintenant, article_id: ligne._objet || ligne._existante.id,
      type: 'inventaire', quantite, utilisateur: contexte.utilisateur, commentaire: 'import' }), ligne);
  }
  function operationsDe(valeurs) {
    const liste = valeurs.operations ? valeurs.operations.split(';').map(texte) : [];
    const attendues = liste.length > 1 ? texte(valeurs.valeur_attendue).split(';').map(texte) : [texte(valeurs.valeur_attendue)];
    return liste.map((operation, i) => ({ operation, attendue: attendues[i] || '' })).filter((o) => o.operation);
  }
  // Gamme : la première ligne porte la fiche ; les lignes suivantes de la même gamme ajoutent des opérations.
  function secondeGamme(contexte, ligne) {
    const tete = ligne._tete || ligne;
    if (!contexte.etats.has(tete)) {
      const existantes = tete._existante ? Donnees.lignes('gamme_operations').filter((o) => o.gamme_id === tete._existante.id) : [];
      contexte.etats.set(tete, { ordre: existantes.reduce((max, o) => Math.max(max, Number(o.ordre) || 0), 0), connues: new Map(existantes.map((o) => [cleTexte(o.operation), o])) });
    }
    const [etat, ajouts, modifications] = [contexte.etats.get(tete), [], []];
    for (const { operation, attendue } of operationsDe(ligne.valeurs)) {
      const connue = etat.connues.get(cleTexte(operation));
      if (!connue) {
        etat.ordre += 1;
        etat.connues.set(cleTexte(operation), prevoir(contexte, 'gamme_operations', nouvelleLigne('gamme_operations', {
          gamme_id: tete._objet || tete._existante.id, ordre: String(etat.ordre), operation, valeur_attendue: attendue }), ligne));
        ajouts.push(operation);
      } else if (!contexte.entrees.has(connue) && attendue && attendue !== texte(connue.valeur_attendue)) modifications.push({ connue, attendue });
    }
    if (ligne._tete) {
      ligne._cibles = [];
      ligne.raisons.push(ajouts.length ? I18n.t('import.seconde_gamme.operation_ajoutee', { numero: tete.numero }) : I18n.t('import.seconde_gamme.operation_deja_gamme_rien'));
      if (tete._objet) return Object.assign(ligne, { action: ajouts.length ? 'creer' : 'identique', _objetCible: tete._objet });
      ligne._existante = tete._existante;
    }
    if (ligne._existante) {
      ajouts.forEach((operation) => ligne.changements.push({ champ: 'operation', libelle: I18n.t('import.seconde_gamme.operation'), avant: '', apres: operation }));
      modifications.forEach(({ connue, attendue }) => ligne.changements.push({ champ: 'valeur_attendue', libelle: I18n.t('import.seconde_gamme.valeur_attendue', { operation: connue.operation }), avant: texte(connue.valeur_attendue), apres: attendue }));
    }
    decider(contexte, ligne, ajouts.length + modifications.length > 0);
    if (ligne.action === 'mettre_a_jour') modifications.forEach(({ connue, attendue }) => ligne._modifier.push({ table: 'gamme_operations', id: connue.id, changes: { valeur_attendue: attendue } }));
  }
  const SECONDES_PASSES = { localisations: secondeLocalisation, equipements: secondeEquipement, articles: secondeArticle, gammes: secondeGamme };
  /** Fabrique d'identifiants suivants (Donnees.nouvelId), qui tient compte des créations déjà prévues (année de dateIso si annuels). */
  function fabriqueIdentifiants() {
    const derniers = new Map();
    return (table, dateIso) => {
      const description = Schema.table(table);
      const cle = table + '|' + (description.identifiant.annuel ? (/^\d{4}/.exec(texte(dateIso)) || [Donnees.aujourdhui().slice(0, 4)])[0] : '');
      const id = Donnees.nouvelId(table, derniers.has(cle) ? [{ [description.cle]: derniers.get(cle) }] : Donnees.lignes(table), dateIso);
      derniers.set(cle, id);
      return id;
    };
  }
  /** Fin de l'aperçu : références utilisées, identifiants dans l'ordre du fichier, écritures, totaux. */
  function terminer(contexte) {
    const gardee = (ligne) => Boolean(ligne) && GARDEES.has(ligne.action);
    const [arbre, utilises, idDe] = [contexte.arbre, new Set(), (valeur) => (valeur && typeof valeur === 'object' ? valeur.id : valeur)];
    const marquer = (valeur) => { for (let v = valeur; v && typeof v === 'object' && !utilises.has(v); v = arbre ? arbre.parents.get(v) : null) utilises.add(v); };
    contexte.crees.filter((e) => gardee(e.ligne)).forEach((e) => (e.table === 'localisations' ? marquer(arbre.parents.get(e.objet)) : Object.values(e.objet).forEach(marquer)));
    contexte.lignes.filter(gardee).forEach((l) => (l._modifier || []).forEach((m) => Object.values(m.changes).forEach(marquer)));
    const gardes = contexte.crees.filter((e) => gardee(e.ligne) || (!e.ligne && utilises.has(e.objet)));
    const identifiant = fabriqueIdentifiants();
    gardes.forEach((e) => { e.objet.id = identifiant(e.table, e.objet.date_creation || e.objet.date); });
    const [ecritures, referencesCreees] = [{}, []];
    contexte.description.tables.forEach((table) => { ecritures[table] = { creer: [], modifier: [] }; });
    for (const { table, objet, ligne } of gardes) {
      if (table === 'localisations' && arbre) objet.parent_id = idDe(arbre.parents.get(objet)) || '';
      const creee = {};
      Schema.table(table).champs.forEach((champ) => { creee[champ.nom] = idDe(objet[champ.nom]); });
      ecritures[table].creer.push(creee);
      if (!ligne) referencesCreees.push({ table, libelle: table === 'localisations' ? cheminDe(arbre, objet) : objet.nom, id: objet.id });
    }
    for (const ligne of contexte.lignes) {
      for (const m of gardee(ligne) ? ligne._modifier || [] : []) {
        const changes = {};
        Object.keys(m.changes).forEach((nom) => { changes[nom] = idDe(m.changes[nom]); });
        ecritures[m.table].modifier.push({ id: m.id, changes });
      }
      const creee = ligne._objet || ligne._objetCible;
      if (ligne.action !== 'refusee' && creee && !ligne._existante) ligne.cible = creee.id;
    }
    const totaux = { lignes: contexte.lignes.length, references: referencesCreees.length };
    ACTIONS.concat(contexte.lignes.map((l) => l.action)).forEach((action) => { totaux[action] = contexte.lignes.filter((l) => l.action === action).length; });
    const lignes = contexte.lignes.map((l) => ({ numero: l.numero, rang: l.rang, action: l.action, raisons: l.raisons, valeurs: l.valeurs, changements: l.changements, cible: l.cible }));
    return { type: contexte.type, lignes, ecritures, referencesCreees, totaux };
  }
  /**
   * Aperçu à blanc (§18.5) : { type, lignes: [{ numero, rang, action, raisons, valeurs, changements, cible }], ecritures:
   * { table: { creer, modifier: [{ id, changes }] } }, referencesCreees, totaux } ; ne fait que lire Donnees.
   * options : mettreAJour (vrai par défaut, D84 a), numeroPremiereLigne (2), maintenant, utilisateur.
   */
  function preparer(type, lignes, correspondanceChoisie, options) {
    const description = typeDonnees(type);
    if (type === 'historique') {
      if (typeof Import.preparerHistorique !== 'function') throw new ErreurImport(I18n.t('import.preparer.import_historique_interventions_pas'));
      return Import.preparerHistorique(lignes || [], correspondanceChoisie || [], options || {}, Import.interne);
    }
    const contexte = nouveauContexte(type, options);
    contexte.colonnes = colonnesParChamp(description, correspondanceChoisie);
    (lignes || []).forEach((cellules, rang) => premierePasse(contexte, cellules, rang));
    contexte.lignes.filter((l) => l.action !== 'refusee').forEach((ligne) => (SECONDES_PASSES[type] || decider)(contexte, ligne));
    if (type === 'equipements') cascadeEquipements(contexte);
    if (typeof Import.controlerFormulaires === 'function') Import.controlerFormulaires(contexte);   // T92 : import-controles.js
    return terminer(contexte);
  }

  // ===== 7. Rapport des lignes refusées (CSV au format de Prévo, §3.1) ===============================
  function celluleCsv(valeur) {
    const ecrite = Donnees.csv.ecrireValeur({ type: 'texte' }, valeur);
    return /[;"\r\n]|^[ \t]|[ \t]$/.test(ecrite) ? '"' + ecrite.replace(/"/g, '""') + '"' : ecrite;
  }
  /** Lignes refusées → texte CSV (BOM, « ; », CRLF, apostrophe de protection), colonne « Raison » en tête. */
  function rapportRefus(apercu, lignes, entetes) {
    const enTexte = (valeur) => (valeur === null || valeur === undefined ? '' : String(valeur));
    const enTetes = (entetes || []).map(enTexte);
    const sortie = [[I18n.t('import.rapport_refus.raison')].concat(enTetes)].concat(((apercu && apercu.lignes) || []).filter((l) => l.action === 'refusee')
      .map((ligne) => [ligne.raisons.join(' ; ')].concat(enTetes.map((_, i) => enTexte(((lignes || [])[ligne.rang] || [])[i])))));
    return String.fromCharCode(0xFEFF) + sortie.map((cellules) => cellules.map(celluleCsv).join(';') + '\r\n').join('');
  }

  // Outils partagés avec import-historique.js (T82) et les écrans.
  const interne = {
    texte, comparable, cleTexte, nombreCanonique, convertir, lireCellules, colonnesParChamp, typeDonnees, champDe,
    nouveauContexte, nouvelleLigne, prevoir, refuser, decider, memeValeur, afficher, terminer, fabriqueIdentifiants,
    trouverEquipement, trouverTechnicien, decouperChemin, resoudreChemin, cheminDe, operationsDe, EQUIVALENCES, PLAFOND_LIGNES, GARDEES,
  };

  return { ErreurImport, TYPES, comparable, correspondance, memoriserCorrespondance, correspondanceRetenue, preparer, rapportRefus, interne };
})();
