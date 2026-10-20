'use strict';
// Indicateurs : module M6 « Indicateurs » — disponibilité, MTBF, MTTR, durée d'arrêt, préventif,
// délais, coûts, valeur du stock (écran E11 et rapport mensuel ; ARCHITECTURE.md §15.3 et §15.4 ;
// brief §12).
//
// Le module est découpé en quatre fichiers, chargés dans cet ordre par index.html (§15.1) :
//   indicateurs-regles.js       CE FICHIER, qui crée l'objet Indicateurs : règles PURES
//                                 1. Constantes et petits outils (nombres, dates, résultats)
//                                 2. Périodes
//                                 3. Index construits une fois par calcul
//                                 4. Pannes, attente de pièces (journal), temps requis
//                                 5. Indicateurs d'un équipement et de l'atelier
//                                 6. Préventif, délais de prise en charge, coûts, stock
//   indicateurs-series.js       7. Séries des graphiques (Pareto, heures par mois, causes…)
//   indicateurs-graphiques.js   graphiques ECharts, « Voir les valeurs », exports CSV et PNG
//   indicateurs-ecrans.js       écran #/indicateurs
//
// RÈGLE D'OR (brief §12) : jamais un chiffre faux. Chaque indicateur rend un RÉSULTAT
//   { valeur, raison, effectif, ots, exclus, note }
// valeur null ⇒ raison dit pourquoi (« non calculable : … », « aucune panne sur la période ») ;
// effectif = nombre d'éléments comptés ; ots = OT sources ; exclus = [{ id, raison }] (ce qui n'a
// pas pu être compté, et pourquoi) ; note = précision facultative. Les valeurs ne sont pas
// arrondies : l'écran arrondit.
//
// Définitions détaillées : ARCHITECTURE.md §15.3 (décisions D35 et D36 du CDC du lot 3). En bref :
// une panne est un OT correctif avec arrêt de production ; MTTR = durée d'arrêt moyenne (temps de
// rétablissement, attentes comprises) ; heures de fonctionnement non renseignées → non calculable.
// Les dates-heures du fichier (heure de l'atelier) sont comparées telles quelles : un changement
// d'heure n'est pas corrigé dans un écart compté en heures.

const Indicateurs = (() => {

  // ===========================================================================================
  // 1. Constantes et petits outils
  // ===========================================================================================

  const TYPES_CORRECTIFS = ['correctif immédiat', 'correctif différé'];
  const TYPES_PREVENTIFS = ['préventif systématique', 'préventif conditionnel'];
  const STATUTS_CLOTURES = ['Clôturé techniquement', 'Clôturé administrativement'];
  const PRIORITES = ['P1', 'P2', 'P3', 'P4'];
  const PERIODES = Object.freeze({
    mois: 'Mois en cours', 'mois-precedent': 'Mois précédent', '3-mois': '3 derniers mois',
    '12-mois': '12 derniers mois', 'du-au': 'Période choisie',
  });
  const MILLISECONDES_PAR_JOUR = 86400000;
  const MILLISECONDES_PAR_HEURE = 3600000;
  const MOTIF_DATE_ISO = /^(\d{4})-(\d{2})-(\d{2})/;
  const MOTIF_DATE_HEURE = /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?/;
  // Le journal écrit « <description> — <action> » (Donnees.modifier), ex. « modification : statut,
  // motif_attente — statut En cours → En attente : Pièce : en attente de livraison. » ; on lit l'action.
  const MOTIF_TRANSITION = /^statut (.+?) → (.+?)(?: : (.*))?$/;
  const SEPARATEUR_ACTION = ' — ';

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  /** Nombre lu dans une valeur du fichier, ou null si vide ou illisible. */
  function nombre(valeur) {
    return Donnees.nombre(valeur);
  }

  /** Comme Ordres.cout : une valeur vide compte zéro. */
  function nombreOuZero(valeur) {
    const resultat = nombre(valeur);
    return resultat === null ? 0 : resultat;
  }

  function arrondi(valeur, decimales) {
    const facteur = Math.pow(10, decimales === undefined ? 2 : decimales);
    return Math.round(valeur * facteur) / facteur;
  }

  /** Texte sans accents ni majuscules : « Pièce » → « piece ». */
  function simplifier(valeur) {
    return texte(valeur).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  }

  function numeroJour(dateIso) {
    const morceaux = MOTIF_DATE_ISO.exec(texte(dateIso));
    if (!morceaux) return null;
    return Date.UTC(Number(morceaux[1]), Number(morceaux[2]) - 1, Number(morceaux[3])) / MILLISECONDES_PAR_JOUR;
  }

  function dateDepuisNumero(numero) {
    const date = new Date(numero * MILLISECONDES_PAR_JOUR);
    return date.getUTCFullYear() + '-' + String(date.getUTCMonth() + 1).padStart(2, '0')
      + '-' + String(date.getUTCDate()).padStart(2, '0');
  }

  /** La date ISO (10 premiers caractères) si elle est lisible, sinon ''. */
  function jourDe(valeur) {
    const date = texte(valeur).slice(0, 10);
    return numeroJour(date) === null ? '' : date;
  }

  function ajouterJours(dateIso, jours) {
    return dateDepuisNumero(numeroJour(dateIso) + jours);
  }

  /** Date ISO + n mois, ramenée au dernier jour du mois si besoin (31/03 − 1 mois → 28/02). */
  function ajouterMois(dateIso, mois) {
    const morceaux = MOTIF_DATE_ISO.exec(dateIso);
    const total = Number(morceaux[1]) * 12 + Number(morceaux[2]) - 1 + mois;
    const annee = Math.floor(total / 12);
    const mois0 = total - annee * 12;
    const dernierJour = new Date(Date.UTC(annee, mois0 + 1, 0)).getUTCDate();
    return annee + '-' + String(mois0 + 1).padStart(2, '0') + '-' + String(Math.min(Number(morceaux[3]), dernierJour)).padStart(2, '0');
  }

  function dateDuJour(aujourdhui) {
    return jourDe(aujourdhui) || Donnees.aujourdhui();
  }

  /** « AAAA-MM-JJ HH:MM » → millisecondes (heure d'horloge lue comme UTC), ou null. */
  function instant(dateHeure) {
    const morceaux = MOTIF_DATE_HEURE.exec(texte(dateHeure));
    if (!morceaux) return null;
    return Date.UTC(Number(morceaux[1]), Number(morceaux[2]) - 1, Number(morceaux[3]),
      Number(morceaux[4] || 0), Number(morceaux[5] || 0));
  }

  function heuresEntre(debut, fin) {
    const a = instant(debut);
    const b = instant(fin);
    return a === null || b === null ? null : (b - a) / MILLISECONDES_PAR_HEURE;
  }

  function dansPeriode(dateIso, periode) {
    const jour = jourDe(dateIso);
    return jour !== '' && jour >= periode.debut && jour <= periode.fin;
  }

  /** Un résultat d'indicateur (voir l'en-tête). */
  function resultat(valeur, raison, details) {
    const autres = details || {};
    const propre = valeur === null || valeur === undefined || !Number.isFinite(valeur) ? null : valeur;
    return {
      valeur: propre,
      raison: propre === null ? (raison || 'non calculable') : null,
      effectif: autres.effectif || 0,
      ots: autres.ots || [],
      exclus: autres.exclus || [],
      note: autres.note || null,
    };
  }

  function mediane(valeurs) {
    if (!valeurs.length) return null;
    const triees = valeurs.slice().sort((a, b) => a - b);
    const milieu = Math.floor(triees.length / 2);
    return triees.length % 2 ? triees[milieu] : (triees[milieu - 1] + triees[milieu]) / 2;
  }

  function estCloture(ot) {
    return STATUTS_CLOTURES.includes(texte(ot.statut));
  }

  function estSuivi(equipement) {
    return Boolean(equipement) && texte(equipement.actif) !== '0' && texte(equipement.statut) !== 'rebut';
  }

  // ===========================================================================================
  // 2. Périodes
  // ===========================================================================================

  /**
   * Période d'un code : 'mois' (du 1er à aujourd'hui), 'mois-precedent', '3-mois' et '12-mois'
   * (glissants : du lendemain du même jour 3 ou 12 mois plus tôt à aujourd'hui ; '12-mois' est le
   * défaut), 'du-au' (dates `du` et `au`, remises dans l'ordre). → { code, debut, fin, libelle }.
   */
  function periode(code, aujourdhui, du, au) {
    const jour = dateDuJour(aujourdhui);
    let debut;
    let fin = jour;
    let choisi = PERIODES[code] ? code : '12-mois';
    if (choisi === 'mois') debut = jour.slice(0, 8) + '01';
    else if (choisi === 'mois-precedent') {
      debut = ajouterMois(jour.slice(0, 8) + '01', -1);
      fin = ajouterJours(jour.slice(0, 8) + '01', -1);
    } else if (choisi === '3-mois') debut = ajouterJours(ajouterMois(jour, -3), 1);
    else if (choisi === 'du-au' && jourDe(du) && jourDe(au)) {
      debut = jourDe(du) <= jourDe(au) ? jourDe(du) : jourDe(au);
      fin = jourDe(du) <= jourDe(au) ? jourDe(au) : jourDe(du);
    } else {
      choisi = '12-mois';
      debut = ajouterJours(ajouterMois(jour, -12), 1);
    }
    return { code: choisi, debut, fin, libelle: PERIODES[choisi] + ' (du ' + UI.dateFr(debut) + ' au ' + UI.dateFr(fin) + ')' };
  }

  /** Période d'un mois 'AAAA-MM' (du 1er au dernier jour). */
  function periodeDuMois(mois) {
    const debut = mois + '-01';
    return { code: 'du-au', debut, fin: ajouterJours(ajouterMois(debut, 1), -1), libelle: mois };
  }

  function joursDansPeriode(debut, fin) {
    return numeroJour(fin) - numeroJour(debut) + 1;
  }

  // ===========================================================================================
  // 3. Index construits une fois par calcul (jamais de recherche linéaire dans une boucle)
  // ===========================================================================================

  function grouper(lignes, cle) {
    const groupes = new Map();
    lignes.forEach((ligne) => {
      const valeur = texte(ligne[cle]);
      if (!groupes.has(valeur)) groupes.set(valeur, []);
      groupes.get(valeur).push(ligne);
    });
    return groupes;
  }

  function contexte() {
    const ordres = Donnees.lignes('ordres_travail');
    const demandes = Donnees.lignes('demandes');
    const diParOt = new Map();
    demandes.forEach((di) => { if (texte(di.ot_id)) diParOt.set(texte(di.ot_id), di); });
    const demandesParId = new Map(demandes.map((di) => [di.id, di]));
    ordres.forEach((ot) => {
      if (!diParOt.has(ot.id) && demandesParId.has(texte(ot.di_id))) diParOt.set(ot.id, demandesParId.get(texte(ot.di_id)));
    });
    const journal = Donnees.lignes('journal').filter((entree) => texte(entree.table) === 'ordres_travail');
    return {
      ordres,
      ordresParId: new Map(ordres.map((ot) => [ot.id, ot])),
      ordresParEquipement: grouper(ordres, 'equipement_id'),
      equipements: new Map(Donnees.lignes('equipements').map((equipement) => [equipement.id, equipement])),
      diParOt,
      journalParOt: grouper(journal, 'id_ligne'),
      tempsParOt: grouper(Donnees.lignes('ot_temps'), 'ot_id'),
      mouvementsParOt: grouper(Donnees.lignes('mouvements_stock'), 'ot_id'),
      techniciens: new Map(Donnees.lignes('techniciens').map((technicien) => [technicien.id, technicien])),
      articles: new Map(Donnees.lignes('articles').map((article) => [article.id, article])),
      gammes: new Map(Donnees.lignes('gammes').map((gamme) => [gamme.id, gamme])),
      compteurs: new Map(Donnees.lignes('compteurs').map((compteur) => [compteur.id, compteur])),
      localisations: new Map(Donnees.lignes('localisations').map((localisation) => [localisation.id, localisation])),
    };
  }

  /** Vrai si l'équipement passe les filtres { criticite, atelier } (atelier : une localisation
   *  ancêtre de celle de l'équipement, elle comprise). */
  function passeFiltres(equipement, filtres, ctx) {
    const reglages = filtres || {};
    if (reglages.criticite && texte(equipement.criticite) !== reglages.criticite) return false;
    if (!reglages.atelier) return true;
    let courant = texte(equipement.localisation_id);
    const vus = new Set();
    while (courant && !vus.has(courant)) {
      if (courant === reglages.atelier) return true;
      vus.add(courant);
      courant = texte((ctx.localisations.get(courant) || {}).parent_id);
    }
    return false;
  }

  /** Coût RG7 d'un OT : même calcul et mêmes arrondis qu'Ordres.cout(ot).total, sur les index. */
  function coutDeLOt(ot, ctx) {
    const montantHeures = (ctx.tempsParOt.get(ot.id) || []).reduce((somme, ligne) =>
      somme + nombreOuZero(ligne.heures) * nombreOuZero((ctx.techniciens.get(ligne.technicien_id) || {}).taux_horaire), 0);
    const quantites = new Map();
    (ctx.mouvementsParOt.get(ot.id) || []).forEach((mouvement) => {
      if (mouvement.type !== 'sortie' && mouvement.type !== 'retour') return;
      const signe = mouvement.type === 'sortie' ? 1 : -1;
      quantites.set(mouvement.article_id, (quantites.get(mouvement.article_id) || 0) + signe * nombreOuZero(mouvement.quantite));
    });
    let montantPieces = 0;
    quantites.forEach((quantite, articleId) => {
      montantPieces += quantite * nombreOuZero((ctx.articles.get(articleId) || {}).prix_unitaire);
    });
    return arrondi(montantHeures + montantPieces + nombreOuZero(ot.cout_soustraitance));
  }

  // ===========================================================================================
  // 4. Pannes, attente de pièces (journal), temps requis
  // ===========================================================================================

  function estPanne(ot) {
    return TYPES_CORRECTIFS.includes(texte(ot.type)) && texte(ot.arret_production) === '1' && texte(ot.statut) !== 'Annulé';
  }

  /** Date-heure de la panne : celle de la DI d'origine, sinon la création de l'OT. */
  function datePanne(ot, ctx) {
    const di = ctx.diParOt.get(ot.id);
    return texte(di && di.date_heure) || texte(ot.date_creation);
  }

  /** Action d'une entrée du journal : la partie après « — » (sinon tout le texte). */
  function actionDe(entree) {
    const action = texte(entree.action);
    const position = action.indexOf(SEPARATEUR_ACTION);
    return position >= 0 ? action.slice(position + SEPARATEUR_ACTION.length) : action;
  }

  /**
   * Attente de pièces d'un OT, lue dans le journal : { heures, complet }.
   * complet : la création de la ligne de l'OT figure au journal (« création — … » ; sinon on ne
   * sait pas tout de son histoire).
   * heures : Σ des séjours « En attente » dont le motif commence par « pièce » (casse et accents
   * ignorés), jusqu'à la sortie d'« En attente » (ou la date de fin de l'OT), plafonnée à la durée
   * d'arrêt quand elle est connue ; null si un séjour ne peut pas être mesuré.
   */
  function attentePieces(otId, ctxDonne) {
    const ctx = ctxDonne || contexte();
    const ot = ctx.ordresParId.get(otId) || {};
    const entrees = (ctx.journalParOt.get(texte(otId)) || []).slice()
      .sort((a, b) => texte(a.date_heure).localeCompare(texte(b.date_heure)) || texte(a.id).localeCompare(texte(b.id)));
    const complet = entrees.some((entree) => /^création\b/.test(texte(entree.action))
      || /^(création de l'OT|acceptation de DI-)/.test(actionDe(entree)));
    let total = 0;
    let debutAttente = null;
    let mesurable = true;
    entrees.forEach((entree) => {
      const transition = MOTIF_TRANSITION.exec(actionDe(entree));
      if (!transition) return;
      const moment = instant(entree.date_heure);
      if (debutAttente !== null && transition[1] === 'En attente') {
        if (moment === null) mesurable = false; else total += (moment - debutAttente) / MILLISECONDES_PAR_HEURE;
        debutAttente = null;
      }
      if (transition[2] === 'En attente' && simplifier(transition[3]).startsWith('piece')) {
        if (moment === null) mesurable = false; else debutAttente = moment;
      }
    });
    if (debutAttente !== null) {
      const fin = instant(ot.date_fin);
      if (fin === null) mesurable = false; else total += Math.max(0, (fin - debutAttente) / MILLISECONDES_PAR_HEURE);
    }
    const duree = nombre(ot.duree_arret_h);
    const heures = mesurable ? (duree !== null && duree >= 0 ? Math.min(total, duree) : total) : null;
    return { heures, complet };
  }

  /** Pannes d'une période : [{ ot, date, duree, attente }], par date. */
  function pannes(periodeChoisie, options, ctxDonne) {
    const ctx = ctxDonne || contexte();
    const reglages = options || {};
    const source = reglages.equipementId ? (ctx.ordresParEquipement.get(reglages.equipementId) || []) : ctx.ordres;
    return source.filter((ot) => estPanne(ot) && dansPeriode(datePanne(ot, ctx), periodeChoisie))
      .map((ot) => {
        const duree = nombre(ot.duree_arret_h);
        return { ot, date: datePanne(ot, ctx), duree: duree !== null && duree >= 0 ? duree : null, attente: attentePieces(ot.id, ctx) };
      })
      .sort((a, b) => a.date.localeCompare(b.date) || a.ot.id.localeCompare(b.ot.id));
  }

  /** Temps requis d'un équipement sur la période (heures), voir l'en-tête. */
  function tempsRequis(equipement, periodeChoisie) {
    if (!equipement) return resultat(null, 'non calculable : équipement introuvable');
    if (!estSuivi(equipement)) return resultat(null, 'non calculable : équipement désactivé ou au rebut');
    const heures = nombre(equipement.heures_fonct_jour);
    if (heures === null || heures <= 0) return resultat(null, 'non calculable : heures de fonctionnement par jour non renseignées');
    const miseEnService = jourDe(equipement.date_mes);
    const debut = miseEnService && miseEnService > periodeChoisie.debut ? miseEnService : periodeChoisie.debut;
    if (debut > periodeChoisie.fin) return resultat(null, 'non calculable : mis en service après la période');
    const jours = joursDansPeriode(debut, periodeChoisie.fin);
    return resultat(heures * jours, null, { effectif: jours, note: heures + ' h par jour × ' + jours + ' jours' });
  }

  // ===========================================================================================
  // 5. Indicateurs d'un équipement et de l'atelier
  // ===========================================================================================

  /** MTBF, MTTR, disponibilité, durée d'arrêt, attente de pièces d'un ensemble de pannes,
   *  pour un temps requis connu (ou un résultat « non calculable »). */
  function fiabilite(liste, requis) {
    const ots = liste.map((panne) => panne.ot.id);
    const sansDuree = liste.filter((panne) => panne.duree === null)
      .map((panne) => ({ id: panne.ot.id, raison: estCloture(panne.ot) ? 'sans durée d\'arrêt' : 'non clôturée' }));
    const avecDuree = liste.filter((panne) => panne.duree !== null);
    const sommeArret = avecDuree.reduce((somme, panne) => somme + panne.duree, 0);
    const dureeArret = resultat(sommeArret, null, { effectif: avecDuree.length, ots, exclus: sansDuree });

    const mesurables = avecDuree.filter((panne) => estCloture(panne.ot));
    const exclusMttr = liste.filter((panne) => !mesurables.includes(panne))
      .map((panne) => ({ id: panne.ot.id, raison: estCloture(panne.ot) ? 'sans durée d\'arrêt' : 'non clôturée' }));
    const mttr = liste.length === 0 ? resultat(null, 'aucune panne sur la période')
      : resultat(mesurables.length ? mesurables.reduce((somme, panne) => somme + panne.duree, 0) / mesurables.length : null,
        'non calculable : aucune panne clôturée avec une durée d\'arrêt',
        { effectif: mesurables.length, ots: mesurables.map((panne) => panne.ot.id), exclus: exclusMttr });

    let mtbf;
    if (requis.valeur === null) mtbf = resultat(null, requis.raison, { ots });
    else if (liste.length === 0) mtbf = resultat(null, 'aucune panne sur la période');
    else mtbf = resultat((requis.valeur - sommeArret) / liste.length, null, { effectif: liste.length, ots, exclus: sansDuree });

    let disponibilite;
    if (requis.valeur === null) disponibilite = resultat(null, requis.raison);
    else if (liste.length === 0) disponibilite = resultat(1, null, { note: 'aucune panne sur la période' });
    else if (mtbf.valeur === null || mttr.valeur === null) disponibilite = resultat(null, mttr.raison || mtbf.raison);
    else disponibilite = resultat(mtbf.valeur / (mtbf.valeur + mttr.valeur), null, { effectif: liste.length, ots });

    const completes = mesurables.filter((panne) => panne.attente.complet && panne.attente.heures !== null);
    const attente = resultat(completes.length ? completes.reduce((somme, panne) => somme + panne.attente.heures, 0) / completes.length : null,
      liste.length === 0 ? 'aucune panne sur la période' : 'historique des statuts absent du journal',
      { effectif: completes.length, ots: completes.map((panne) => panne.ot.id) });
    return { pannes: resultat(liste.length, null, { effectif: liste.length, ots }), dureeArret, mtbf, mttr, disponibilite, attentePieces: attente };
  }

  /** Coût (RG7) des OT clôturés dont la date de fin tombe dans la période. */
  function coutDesOrdres(ordres, periodeChoisie, ctx) {
    const comptes = ordres.filter((ot) => estCloture(ot) && dansPeriode(ot.date_fin, periodeChoisie));
    return resultat(arrondi(comptes.reduce((somme, ot) => somme + coutDeLOt(ot, ctx), 0)), null,
      { effectif: comptes.length, ots: comptes.map((ot) => ot.id), note: 'prix actuel des pièces (limite D24)' });
  }

  /** Indicateurs d'un équipement : { tempsRequis, pannes, dureeArret, mtbf, mttr, disponibilite,
   *  attentePieces, cout } (chacun un résultat). */
  function parEquipement(equipementId, periodeChoisie, ctxDonne) {
    const ctx = ctxDonne || contexte();
    const equipement = ctx.equipements.get(equipementId);
    const requis = tempsRequis(equipement, periodeChoisie);
    const indicateurs = fiabilite(pannes(periodeChoisie, { equipementId }, ctx), requis);
    return Object.assign({ tempsRequis: requis }, indicateurs,
      { cout: coutDesOrdres(ctx.ordresParEquipement.get(equipementId) || [], periodeChoisie, ctx) });
  }

  /**
   * Indicateurs de l'atelier (filtres { criticite, atelier }) : fiabilité calculée sur les
   * équipements suivis dont le temps requis est connu (les autres dans tempsRequis.exclus) ; coût,
   * préventif, délais et OT en retard sur tous les équipements filtrés ; valeur du stock globale.
   */
  function global(periodeChoisie, filtres, aujourdhui) {
    const ctx = contexte();
    const retenus = [];
    const exclus = [];
    let sommeRequis = 0;
    const equipementsFiltres = Array.from(ctx.equipements.values()).filter((equipement) => estSuivi(equipement) && passeFiltres(equipement, filtres, ctx));
    equipementsFiltres.forEach((equipement) => {
      const requis = tempsRequis(equipement, periodeChoisie);
      if (requis.valeur === null) exclus.push({ id: equipement.id, raison: requis.raison });
      else { retenus.push(equipement.id); sommeRequis += requis.valeur; }
    });
    const ids = new Set(retenus);
    const liste = pannes(periodeChoisie, {}, ctx).filter((panne) => ids.has(texte(panne.ot.equipement_id)));
    const requisGlobal = retenus.length ? resultat(sommeRequis, null, { effectif: retenus.length, exclus })
      : resultat(null, 'non calculable : aucun équipement n\'a ses heures de fonctionnement par jour', { exclus });
    const idsFiltres = new Set(equipementsFiltres.map((equipement) => equipement.id));
    const ordresFiltres = ctx.ordres.filter((ot) => idsFiltres.has(texte(ot.equipement_id)));
    return Object.assign({ tempsRequis: requisGlobal }, fiabilite(liste, requisGlobal), {
      cout: coutDesOrdres(ordresFiltres, periodeChoisie, ctx),
      partPreventif: partPreventif(periodeChoisie, filtres, ctx),
      respectPreventif: respectPreventif(periodeChoisie, filtres, ctx),
      otEnRetard: otEnRetard(aujourdhui, filtres, ctx),
      valeurStock: valeurStock(),
      delais: delaisPriseEnCharge(periodeChoisie, filtres, ctx),
    });
  }

  // ===========================================================================================
  // 6. Préventif, délais de prise en charge, coûts, stock
  // ===========================================================================================

  function ordresFiltres(filtres, ctx) {
    if (!filtres || (!filtres.criticite && !filtres.atelier)) return ctx.ordres;
    return ctx.ordres.filter((ot) => {
      const equipement = ctx.equipements.get(texte(ot.equipement_id));
      return Boolean(equipement) && passeFiltres(equipement, filtres, ctx);
    });
  }

  /** Part du préventif = heures passées (ot_temps datés dans la période) sur des OT préventifs /
   *  heures passées sur tous les OT non annulés. */
  function partPreventif(periodeChoisie, filtres, ctxDonne) {
    const ctx = ctxDonne || contexte();
    let total = 0;
    let preventif = 0;
    ordresFiltres(filtres, ctx).filter((ot) => texte(ot.statut) !== 'Annulé').forEach((ot) => {
      const heures = (ctx.tempsParOt.get(ot.id) || []).filter((ligne) => dansPeriode(ligne.date, periodeChoisie))
        .reduce((somme, ligne) => somme + nombreOuZero(ligne.heures), 0);
      total += heures;
      if (TYPES_PREVENTIFS.includes(texte(ot.type))) preventif += heures;
    });
    return resultat(total > 0 ? preventif / total : null, 'non calculable : aucune heure passée sur la période',
      { effectif: arrondi(total, 2), note: arrondi(preventif, 2) + ' h de préventif sur ' + arrondi(total, 2) + ' h' });
  }

  function estUniteHeure(unite) {
    return /^(h|heures?)$/.test(texte(unite).toLowerCase().replace(/\.$/, ''));
  }

  /** Période d'une gamme en jours (date : periodicite_jours ; compteur en heures :
   *  periodicite_unites / heures par jour de l'équipement), ou null. */
  function periodeGammeJours(gamme, ctx) {
    if (texte(gamme.declencheur) === 'date') {
      const jours = nombre(gamme.periodicite_jours);
      return jours !== null && jours > 0 ? jours : null;
    }
    if (texte(gamme.declencheur) === 'compteur') {
      const compteur = ctx.compteurs.get(texte(gamme.compteur_id));
      const unites = nombre(gamme.periodicite_unites);
      const heures = nombre((ctx.equipements.get(texte(gamme.equipement_id)) || {}).heures_fonct_jour);
      if (!compteur || !estUniteHeure(compteur.unite) || unites === null || unites <= 0 || heures === null || heures <= 0) return null;
      return unites / heures;
    }
    return null;
  }

  /** Respect du préventif : part des OT préventifs systématiques à échéance (date prévue +
   *  tolérance) dans la période qui ont été clôturés au plus tard à cette échéance. */
  function respectPreventif(periodeChoisie, filtres, ctxDonne) {
    const ctx = ctxDonne || contexte();
    const pourcentage = nombre(Donnees.parametre('tolerance_preventif_pct', '10'));
    const tolerancePct = pourcentage !== null && pourcentage >= 0 ? pourcentage : 10;
    const comptes = [];
    const respectes = [];
    const exclus = [];
    ordresFiltres(filtres, ctx).forEach((ot) => {
      if (texte(ot.type) !== 'préventif systématique' || texte(ot.statut) === 'Annulé' || !texte(ot.gamme_id)) return;
      const gamme = ctx.gammes.get(texte(ot.gamme_id));
      const jours = gamme ? periodeGammeJours(gamme, ctx) : null;
      if (jours === null || !jourDe(ot.date_prevue)) {
        exclus.push({ id: ot.id, raison: !jourDe(ot.date_prevue) ? 'sans date prévue' : 'période de la gamme inconnue' });
        return;
      }
      const limite = ajouterJours(jourDe(ot.date_prevue), Math.max(1, Math.ceil(tolerancePct * jours / 100)));
      if (limite < periodeChoisie.debut || limite > periodeChoisie.fin) return;
      comptes.push(ot.id);
      if (estCloture(ot) && jourDe(ot.date_fin) && jourDe(ot.date_fin) <= limite) respectes.push(ot.id);
    });
    return resultat(comptes.length ? respectes.length / comptes.length : null,
      'non calculable : aucun préventif à échéance sur la période',
      { effectif: comptes.length, ots: comptes, exclus, note: respectes.length + ' respecté(s) sur ' + comptes.length });
  }

  /** OT en retard (définition du lot 1) à une date, sur les équipements filtrés. */
  function otEnRetard(aujourdhui, filtres, ctxDonne) {
    const ctx = ctxDonne || contexte();
    const jour = dateDuJour(aujourdhui);
    const liste = ordresFiltres(filtres, ctx).filter((ot) => Accueil.otEnRetard(ot, jour));
    return resultat(liste.length, null, { effectif: liste.length, ots: liste.map((ot) => ot.id) });
  }

  /** Délai de prise en charge par priorité : { P1: { mediane, partDansLeDelai, effectif, cible,
   *  ots }, … } pour les OT démarrés dans la période. */
  function delaisPriseEnCharge(periodeChoisie, filtres, ctxDonne) {
    const ctx = ctxDonne || contexte();
    const parPriorite = {};
    PRIORITES.forEach((priorite) => { parPriorite[priorite] = []; });
    ordresFiltres(filtres, ctx).forEach((ot) => {
      if (texte(ot.statut) === 'Annulé' || !dansPeriode(ot.date_debut, periodeChoisie) || !parPriorite[texte(ot.priorite)]) return;
      const di = ctx.diParOt.get(ot.id);
      const delai = heuresEntre(texte(di && di.date_heure) || ot.date_creation, ot.date_debut);
      if (delai !== null && delai >= 0) parPriorite[texte(ot.priorite)].push({ id: ot.id, delai });
    });
    const resultatParPriorite = {};
    PRIORITES.forEach((priorite) => {
      const liste = parPriorite[priorite];
      const cible = priorite === 'P4' ? null : nombre(Donnees.parametre('delai_' + priorite.toLowerCase() + '_h', ''));
      resultatParPriorite[priorite] = {
        mediane: mediane(liste.map((element) => element.delai)),
        partDansLeDelai: cible === null || !liste.length ? null : liste.filter((element) => element.delai <= cible).length / liste.length,
        effectif: liste.length, cible, ots: liste.map((element) => element.id),
      };
    });
    return resultatParPriorite;
  }

  /** Coût par équipement (OT clôturés dans la période) : [{ equipementId, valeur, ots }], décroissant. */
  function coutParEquipement(periodeChoisie, filtres) {
    const ctx = contexte();
    const parEquipementId = new Map();
    ordresFiltres(filtres, ctx).forEach((ot) => {
      if (!estCloture(ot) || !dansPeriode(ot.date_fin, periodeChoisie)) return;
      const element = parEquipementId.get(texte(ot.equipement_id)) || { equipementId: texte(ot.equipement_id), valeur: 0, ots: [] };
      element.valeur += coutDeLOt(ot, ctx);
      element.ots.push(ot.id);
      parEquipementId.set(element.equipementId, element);
    });
    return Array.from(parEquipementId.values()).map((element) => Object.assign(element, { valeur: arrondi(element.valeur) }))
      .sort((a, b) => b.valeur - a.valeur || a.equipementId.localeCompare(b.equipementId));
  }

  /** Coût des OT clôturés par mois de date de fin : [{ mois: 'AAAA-MM', valeur }] sur nbMois mois. */
  function coutsParMois(debutMois, nbMois, filtres) {
    const ctx = contexte();
    const mois = [];
    for (let rang = 0; rang < nbMois; rang += 1) mois.push(ajouterMois(debutMois + '-01', rang).slice(0, 7));
    const valeurs = new Map(mois.map((cle) => [cle, 0]));
    ordresFiltres(filtres, ctx).forEach((ot) => {
      const cle = jourDe(ot.date_fin).slice(0, 7);
      if (estCloture(ot) && valeurs.has(cle)) valeurs.set(cle, valeurs.get(cle) + coutDeLOt(ot, ctx));
    });
    return mois.map((cle) => ({ mois: cle, valeur: arrondi(valeurs.get(cle)) }));
  }

  /** Valeur du stock : Σ stock × prix unitaire des articles actifs (sans prix : exclus). */
  function valeurStock() {
    const exclus = [];
    let total = 0;
    let effectif = 0;
    Donnees.lignes('articles').filter((article) => texte(article.actif) !== '0').forEach((article) => {
      const prix = nombre(article.prix_unitaire);
      if (prix === null) { exclus.push({ id: article.id, raison: 'sans prix unitaire' }); return; }
      total += Donnees.stockArticle(article.id) * prix;
      effectif += 1;
    });
    return resultat(arrondi(total), null, { effectif, exclus });
  }

  return {
    PERIODES,
    // règles pures (ARCHITECTURE.md §15.3) ; les séries des graphiques sont dans indicateurs-series.js
    periode, periodeDuMois, pannes, tempsRequis, attentePieces, parEquipement, global,
    partPreventif, respectPreventif, otEnRetard, delaisPriseEnCharge, coutParEquipement, coutsParMois, valeurStock,
    // Usage interne au module (pas une API).
    interne: {
      TYPES_CORRECTIFS, TYPES_PREVENTIFS, texte, nombre, nombreOuZero, arrondi, jourDe, ajouterJours, ajouterMois,
      dateDuJour, heuresEntre, contexte, grouper, ordresFiltres, coutDeLOt, estPanne, datePanne, estSuivi, passeFiltres,
    },
  };
})();
