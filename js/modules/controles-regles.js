'use strict';
// Controles : contrôles réglementaires — vérifications périodiques imposées par la réglementation
// (VGP des appareils de levage, installations électriques, équipements sous pression…), suivies à
// part du préventif (ARCHITECTURE.md §15.7 ; brief §6 « controles_reglementaires », §7 RG9, §9 E10).
//
// Le module est découpé en trois fichiers, chargés dans cet ordre par index.html (§15.1) :
//   controles-regles.js      CE FICHIER, qui crée l'objet Controles : règles PURES
//                              1. Constantes et petits outils (textes, dates ISO)
//                              2. Prochaine date d'un contrôle (ajouterMois, prochaineDate)
//                              3. Statut calculé RG9 (etat) et contrôles sous 30 jours
//   controles-ecritures.js   création, modification, contrôle réalisé, levée des observations
//   controles-ecrans.js      écrans #/controles, #/controles/nouveau, #/controles/<id>
//
// Les fichiers suivants complètent l'objet : Object.assign(Controles, (() => { … })()). Une
// fonction dont un autre fichier du module a besoin est rangée dans Controles.interne (usage
// interne au module : ce n'est pas une API).
//
// Les fonctions de ce fichier sont PURES : elles lisent Donnees, n'écrivent jamais. Les dates
// sont des chaînes ISO 'AAAA-MM-JJ', calculées en UTC ; la date du jour est passée en argument
// (par défaut Donnees.aujourdhui()).

const Controles = (() => {

  // ===========================================================================================
  // 1. Constantes et petits outils
  // ===========================================================================================

  /** Statuts calculés (RG9), dans l'ordre de priorité : le premier vrai est le statut affiché. */
  const STATUTS = Object.freeze(['en retard', 'observations à lever', 'à planifier', 'à jour']);
  // Libellé affiché d'un statut calculé (controles.statut_calcule.*) : le statut reste la valeur des filtres et adresses.
  const CLES_STATUT = Object.freeze({ 'en retard': 'en_retard', 'observations à lever': 'observations_a_lever',
    'à planifier': 'a_planifier', 'à jour': 'a_jour' });
  function libelleStatut(statut) {
    return CLES_STATUT[statut] ? I18n.t('controles.statut_calcule.' + CLES_STATUT[statut]) : statut;
  }

  // Un contrôle est « à planifier » quand sa prochaine date tombe dans les 30 jours (RG9).
  const HORIZON_A_PLANIFIER_JOURS = 30;
  const MILLISECONDES_PAR_JOUR = 86400000;
  const MOTIF_DATE_ISO = /^(\d{4})-(\d{2})-(\d{2})/;

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  function deuxChiffres(nombre) {
    return String(nombre).padStart(2, '0');
  }

  /** 'AAAA-MM-JJ' (ou 'AAAA-MM-JJ HH:MM') → numéro du jour depuis le 01/01/1970, ou null. */
  function numeroJour(dateIso) {
    const morceaux = MOTIF_DATE_ISO.exec(texte(dateIso));
    if (!morceaux) return null;
    return Date.UTC(Number(morceaux[1]), Number(morceaux[2]) - 1, Number(morceaux[3])) / MILLISECONDES_PAR_JOUR;
  }

  function dateDepuisNumero(numero) {
    const date = new Date(numero * MILLISECONDES_PAR_JOUR);
    return date.getUTCFullYear() + '-' + deuxChiffres(date.getUTCMonth() + 1) + '-' + deuxChiffres(date.getUTCDate());
  }

  /** La date ISO (10 premiers caractères) si elle existe vraiment, sinon '' (« 2026-13-05 » ou
   *  « 2026-02-30 » ne sont pas des dates : le contrôle passe alors en « date inconnue »). */
  function dateIso(valeur) {
    const date = texte(valeur).slice(0, 10);
    const numero = numeroJour(date);
    if (numero === null) return '';
    const relue = new Date(numero * MILLISECONDES_PAR_JOUR);
    const attendue = relue.getUTCFullYear() + '-' + String(relue.getUTCMonth() + 1).padStart(2, '0')
      + '-' + String(relue.getUTCDate()).padStart(2, '0');
    return attendue === date ? date : '';
  }

  /** Nombre de jours de `debut` à `fin` (négatif si fin est avant). */
  function joursEntre(debut, fin) {
    return numeroJour(fin) - numeroJour(debut);
  }

  /** Date du jour à utiliser : celle passée en argument, sinon aujourd'hui. */
  function dateDuJour(aujourdhui) {
    return dateIso(aujourdhui) || Donnees.aujourdhui();
  }

  // ===========================================================================================
  // 2. Prochaine date d'un contrôle
  // ===========================================================================================

  /** Nombre de jours du mois (mois0 : 0 = janvier), années bissextiles comprises. */
  function joursDansLeMois(annee, mois0) {
    return new Date(Date.UTC(annee, mois0 + 1, 0)).getUTCDate();
  }

  /**
   * Date ISO + n mois, même jour du mois, ramené au dernier jour du mois s'il n'existe pas :
   * ajouterMois('2026-01-31', 1) → '2026-02-28' ; ajouterMois('2028-01-31', 1) → '2028-02-29'.
   * n entier (négatif possible) ; date illisible ou n non entier → ''.
   */
  function ajouterMois(dateDepart, n) {
    const morceaux = MOTIF_DATE_ISO.exec(texte(dateDepart));
    const mois = Number(texte(n));
    if (!morceaux || texte(n) === '' || !Number.isInteger(mois)) return '';
    const total = Number(morceaux[1]) * 12 + (Number(morceaux[2]) - 1) + mois;
    const annee = Math.floor(total / 12);
    const mois0 = total - annee * 12;
    const jour = Math.min(Number(morceaux[3]), joursDansLeMois(annee, mois0));
    return annee + '-' + deuxChiffres(mois0 + 1) + '-' + deuxChiffres(jour);
  }

  /** Périodicité en mois (entier > 0), ou null si vide ou illisible. */
  function periodicite(controle) {
    const valeur = Donnees.nombre(controle.periodicite_mois);
    return valeur !== null && valeur > 0 && Number.isInteger(valeur) ? valeur : null;
  }

  /**
   * Prochaine date d'un contrôle : `prochaine_date` si elle est renseignée (le fichier fait foi,
   * même modifié dans Excel), sinon `derniere_date` + `periodicite_mois`, sinon ''.
   */
  function prochaineDate(controle) {
    const enregistree = dateIso(controle.prochaine_date);
    if (enregistree) return enregistree;
    const derniere = dateIso(controle.derniere_date);
    const mois = periodicite(controle);
    return derniere && mois ? ajouterMois(derniere, mois) : '';
  }

  // ===========================================================================================
  // 3. Statut calculé (RG9) et contrôles sous 30 jours
  // ===========================================================================================

  /** Des observations ont été notées et ne sont pas encore levées. */
  function observationsALever(controle) {
    return texte(controle.observations) !== '' && texte(controle.observations_levees) !== '1';
  }

  function raisonDuStatut(statut, prochaine, joursRestants) {
    if (statut === 'en retard') {
      return I18n.t('controles.raison_du_statut.retard_jours_prevu', { n: -joursRestants, prochaine: UI.dateFr(prochaine) });
    }
    if (statut === 'observations à lever') return I18n.t('controles.raison_du_statut.observations_dernier_controle_non');
    if (statut === 'à planifier') {
      if (!prochaine) return I18n.t('controles.raison_du_statut.date_inconnue_renseignez_derniere');
      return joursRestants === 0 ? I18n.t('controles.raison_du_statut.prevu_aujourd_hui')
        : I18n.t('controles.raison_du_statut.n_jours_prochaine', { n: joursRestants, prochaine: UI.dateFr(prochaine) });
    }
    return I18n.t('controles.raison_du_statut.prochain_controle', { prochaine: UI.dateFr(prochaine) });
  }

  /**
   * État d'un contrôle à une date : { statut, secondaires, prochaine, joursRestants, raison }.
   * statut = le premier vrai de STATUTS : « en retard » (prochaine date dépassée), « observations
   * à lever », « à planifier » (prochaine date dans les 30 jours, ou inconnue), « à jour » ;
   * secondaires = les autres états vrais (ex. « en retard » avec des observations à lever).
   */
  function etat(controle, aujourdhui) {
    const jour = dateDuJour(aujourdhui);
    const prochaine = prochaineDate(controle);
    const joursRestants = prochaine ? joursEntre(jour, prochaine) : null;
    const vrais = [];
    if (prochaine && joursRestants < 0) vrais.push('en retard');
    if (observationsALever(controle)) vrais.push('observations à lever');
    if (!prochaine || (joursRestants >= 0 && joursRestants <= HORIZON_A_PLANIFIER_JOURS)) vrais.push('à planifier');
    if (!vrais.length) vrais.push('à jour');
    const statut = vrais[0];
    return { statut, secondaires: vrais.slice(1), prochaine, joursRestants, raison: raisonDuStatut(statut, prochaine, joursRestants) };
  }

  /** L'équipement du contrôle existe, est actif et n'est pas au rebut. */
  function equipementSuivi(controle) {
    const equipement = Donnees.trouver('equipements', controle.equipement_id);
    return Boolean(equipement) && texte(equipement.actif) !== '0' && texte(equipement.statut) !== 'rebut';
  }

  /**
   * Contrôles « sous 30 jours » (compteur de l'accueil) : équipement actif hors rebut, prochaine
   * date inconnue ou au plus tard dans 30 jours (retards compris). Triés : dates inconnues
   * d'abord, puis par date, puis par identifiant.
   */
  function sous30Jours(aujourdhui) {
    const jour = dateDuJour(aujourdhui);
    const limite = dateDepuisNumero(numeroJour(jour) + HORIZON_A_PLANIFIER_JOURS);
    return Donnees.lignes('controles_reglementaires')
      .filter(equipementSuivi)
      .map((controle) => ({ controle, prochaine: prochaineDate(controle) }))
      .filter((element) => !element.prochaine || element.prochaine <= limite)
      .sort((a, b) => (a.prochaine || '').localeCompare(b.prochaine || '')
        || texte(a.controle.id).localeCompare(texte(b.controle.id), 'fr', { numeric: true }))
      .map((element) => element.controle);
  }

  return {
    STATUTS, libelleStatut,
    // règles pures (ARCHITECTURE.md §15.7)
    ajouterMois, prochaineDate, etat, sous30Jours,
    // Usage interne au module (pas une API).
    interne: { texte, dateIso, dateDuJour, joursEntre, periodicite, observationsALever, equipementSuivi },
  };
})();
