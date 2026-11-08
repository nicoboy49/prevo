'use strict';
// Controles — réserves des contrôles réglementaires (2.2, lot L2, CS170 ; table reserves_controle, D183, D187).
// Créé vide par T410 (socle des L2-L3) ; il reçoit :
// - T411 : les règles pures des réserves (lignesDeReserves, reserveLevee, echeanceReserve, etatReserve,
//   reservesDuControle, reservesOuvertes, reservesEnRetard, adresseOtReserve) ;
// - T413 : leurs écritures (ajouterReserves, leverReserve, modifierReserve, lierOtAReserve), toutes par
//   Donnees.modifier('reserves_controle'), contrôles refaits sur la ligne fraîche, jamais de suppression.
// Chargé juste après controles-regles.js (qui crée l'objet Controles) et avant controles-catalogue.js. Complète
// l'objet Controles ; une fonction d'un fichier chargé plus tard est cherchée au moment de l'appel.
//
// Règles pures : elles lisent Donnees, n'écrivent jamais, n'affichent aucun texte. Les dates sont des chaînes ISO
// 'AAAA-MM-JJ' calculées en UTC ; la date du jour est passée en argument (par défaut Donnees.aujourdhui()).
// Statuts d'une réserve (valeurs comparées dans le code, en français comme les statuts des contrôles, D155 ; le
// libellé affiché viendra des dictionnaires) : « levée », « en retard » (ouverte, échéance passée), « à lever ».

Object.assign(Controles, (() => {

  // Outils de controles-regles.js.
  const { texte, dateIso, dateDuJour, joursEntre, equipementSuivi } = Controles.interne;

  // ===========================================================================================
  // 1. Constantes et petits outils
  // ===========================================================================================

  /** Statuts d'une réserve (etatReserve) : valeurs comparées dans le code, jamais affichées telles quelles (D155). */
  const STATUTS_RESERVE = Object.freeze(['en retard', 'à lever', 'levée']);
  const [EN_RETARD, A_LEVER, LEVEE] = STATUTS_RESERVE;
  /** D187 : sans échéance saisie, une réserve est à lever 30 jours après le contrôle qui l'a relevée. */
  const DELAI_LEVEE_PAR_DEFAUT_JOURS = 30;
  /** Longueur du texte de la réserve repris dans le titre d'un OT (conception L2-L3 §3.4). */
  const LONGUEUR_TITRE_OT = 80;
  // Puce de début d'une ligne de rapport : « - », « – », « • », « * », ou un numéro « 1. », « 1) » suivi d'un blanc
  // (ou seul). Un tiret suivi d'un chiffre est un signe (« -20 °C mesurés ») : il reste ; « 1.5 bar » aussi.
  const MOTIF_PUCE = /^(?:[•*]|[-–](?!\d)|\d{1,3}[.)](?=\s|$))\s*/;
  const MOTIF_FIN_DE_LIGNE = /\r\n|\r|\n/;

  /** Date ISO valide + n jours (n entier), ou ''. */
  function ajouterJours(date, n) {
    const depart = dateIso(date);
    if (!depart) return '';
    const jour = new Date(Date.UTC(Number(depart.slice(0, 4)), Number(depart.slice(5, 7)) - 1,
      Number(depart.slice(8, 10)) + n));
    return jour.toISOString().slice(0, 10);
  }

  /** Identifiants comparés dans l'ordre naturel (RES-00009 avant RES-00010). */
  function parIdentifiant(a, b) {
    return texte(a.id).localeCompare(texte(b.id), 'fr', { numeric: true });
  }

  /** Dates ISO comparées comme des textes (sens 1 : croissant, -1 : décroissant) ; une date vide (inconnue) passe
   *  après toutes les autres dans les deux sens. */
  function parDate(a, b, sens) {
    if (a === b) return 0;
    if (!a) return 1;
    if (!b) return -1;
    return (a < b ? -1 : 1) * sens;
  }

  /** Texte d'une réserve sur une ligne (blancs intérieurs réduits à une espace), coupé à LONGUEUR_TITRE_OT
   *  caractères (bord blanc de la coupe retiré). */
  function texteCourtReserve(reserve) {
    const caracteres = Array.from(texte(reserve && reserve.texte).replace(/\s+/g, ' '));
    return caracteres.slice(0, LONGUEUR_TITRE_OT).join('').trimEnd();
  }

  // ===========================================================================================
  // 2. Une réserve : texte saisi, levée, échéance, état
  // ===========================================================================================

  /**
   * Les réserves d'un texte saisi (« réserves relevées », une par ligne, comme le rapport les liste) : une par
   * ligne non vide, bords nettoyés, puce de début retirée (« - », « • », « * », « 1. », « 1) ») ; doublons exacts
   * gardés (le rapport peut les répéter). Rien → [].
   */
  function lignesDeReserves(saisie) {
    return texte(saisie).split(MOTIF_FIN_DE_LIGNE)
      .map((ligne) => ligne.trim().replace(MOTIF_PUCE, '').trim())
      .filter((ligne) => ligne !== '');
  }

  /** Une réserve est levée quand sa colonne levee vaut 1 (Donnees relit oui, x, vrai… en 1) : une réserve reprise
   *  levée (D183, date de levée vide, « levée avant la 2.2, date inconnue ») l'est donc aussi. */
  function reserveLevee(reserve) {
    return Boolean(reserve) && texte(reserve.levee) === '1';
  }

  /**
   * Échéance de levée (D187) : { date, parDefaut }. L'échéance saisie (echeance_levee) ; sinon date_controle +
   * 30 jours (parDefaut vrai : l'écran dit « 30 jours après le contrôle ») ; sinon { date: '', parDefaut: false }
   * (date du contrôle inconnue : la réserve n'est jamais en retard). Une date illisible compte comme vide.
   */
  function echeanceReserve(reserve) {
    const saisie = dateIso(reserve && reserve.echeance_levee);
    if (saisie) return { date: saisie, parDefaut: false };
    const calculee = ajouterJours(reserve && reserve.date_controle, DELAI_LEVEE_PAR_DEFAUT_JOURS);
    return calculee ? { date: calculee, parDefaut: true } : { date: '', parDefaut: false };
  }

  /**
   * État d'une réserve à une date : { statut, echeance, parDefaut, joursRestants }. statut : « levée » (quelle que
   * soit l'échéance), « en retard » (ouverte, échéance passée : la veille au plus tard), sinon « à lever » (échéance
   * aujourd'hui, à venir ou inconnue). joursRestants : jours jusqu'à l'échéance (négatif en retard), null pour une
   * réserve levée ou sans échéance.
   */
  function etatReserve(reserve, aujourdhui) {
    const { date, parDefaut } = echeanceReserve(reserve);
    if (reserveLevee(reserve)) return { statut: LEVEE, echeance: date, parDefaut, joursRestants: null };
    const joursRestants = date ? joursEntre(dateDuJour(aujourdhui), date) : null;
    const statut = joursRestants !== null && joursRestants < 0 ? EN_RETARD : A_LEVER;
    return { statut, echeance: date, parDefaut, joursRestants };
  }

  // ===========================================================================================
  // 3. Réserves d'un contrôle, réserves en retard
  // ===========================================================================================

  /** Ouvertes avant levées, puis dans l'ordre des identifiants (l'ordre de saisie). */
  function ouvertesAvantLevees(a, b) {
    return Number(reserveLevee(a)) - Number(reserveLevee(b)) || parIdentifiant(a, b);
  }

  /**
   * Réserves d'un contrôle groupées par réalisation : [{ date_controle, reserves }], la réalisation la plus récente
   * d'abord (date du contrôle inconnue ou illisible : un groupe date_controle '' en dernier) ; dans un groupe, les
   * ouvertes avant les levées, puis dans l'ordre des identifiants. Contrôle sans réserve → [].
   */
  function reservesDuControle(controleId) {
    const id = texte(controleId);
    const groupes = new Map();
    if (!id) return [];
    Donnees.lignes('reserves_controle').forEach((reserve) => {
      if (texte(reserve.controle_id) !== id) return;
      const date = dateIso(reserve.date_controle);
      if (!groupes.has(date)) groupes.set(date, []);
      groupes.get(date).push(reserve);
    });
    return Array.from(groupes, ([date, reserves]) => ({ date_controle: date, reserves: reserves.sort(ouvertesAvantLevees) }))
      .sort((a, b) => parDate(a.date_controle, b.date_controle, -1));
  }

  /** Réserves non levées d'un contrôle, dans l'ordre de reservesDuControle. */
  function reservesOuvertes(controleId) {
    return reservesDuControle(controleId)
      .flatMap((groupe) => groupe.reserves)
      .filter((reserve) => !reserveLevee(reserve));
  }

  /**
   * Réserves en retard à une date (accueil, rapport, filtre de la liste) : [{ reserve, controle, etat }] des
   * contrôles dont l'équipement est suivi (equipementSuivi : existe, actif, hors rebut ; réserve d'un contrôle
   * introuvable : ignorée), l'échéance la plus ancienne d'abord, puis par identifiant.
   */
  function reservesEnRetard(aujourdhui) {
    const jour = dateDuJour(aujourdhui);
    return Donnees.lignes('reserves_controle')
      .filter((reserve) => !reserveLevee(reserve))
      .map((reserve) => ({ reserve, controle: Donnees.trouver('controles_reglementaires', texte(reserve.controle_id)) }))
      .filter((element) => element.controle && equipementSuivi(element.controle))
      .map((element) => Object.assign(element, { etat: etatReserve(element.reserve, jour) }))
      .filter((element) => element.etat.statut === EN_RETARD)
      .sort((a, b) => parDate(a.etat.echeance, b.etat.echeance, 1) || parIdentifiant(a.reserve, b.reserve));
  }

  /**
   * Adresse « Créer un OT » d'une réserve : #/ot/nouveau?equipement=…&type=réglementaire&titre=…&travail=…
   * &reserve=RES-… (rien n'est créé : l'adresse ouvre le formulaire pré-rempli, que le responsable valide).
   * equipement : celui du contrôle de la réserve (vide si le contrôle est introuvable). titre et travail : ceux de
   * `textes` ({ titre, travail }, facultatif), que l'écran compose dans la langue de l'installation (D156) ; sans
   * eux, le texte de la réserve (titre : coupé à 80 caractères ; travail : entier) — aucun texte de l'interface ici.
   * Réserve sans identifiant → ''.
   */
  function adresseOtReserve(reserve, textes) {
    const id = texte(reserve && reserve.id);
    if (!id) return '';
    const controle = Donnees.trouver('controles_reglementaires', texte(reserve.controle_id));
    const fournis = textes || {};
    const titre = fournis.titre !== undefined && fournis.titre !== null ? texte(fournis.titre) : texteCourtReserve(reserve);
    const travail = fournis.travail !== undefined && fournis.travail !== null ? texte(fournis.travail) : texte(reserve.texte);
    return '#/ot/nouveau?equipement=' + encodeURIComponent(controle ? texte(controle.equipement_id) : '')
      + '&type=' + encodeURIComponent('réglementaire') + '&titre=' + encodeURIComponent(titre)
      + '&travail=' + encodeURIComponent(travail) + '&reserve=' + encodeURIComponent(id);
  }

  // Usage interne au module (pas une API) : pour les écritures (T413) et les écrans (T418-T420).
  Object.assign(Controles.interne, { DELAI_LEVEE_PAR_DEFAUT_JOURS, ajouterJours, texteCourtReserve });

  return {
    STATUTS_RESERVE,
    // règles pures des réserves (conception L2-L3 §3.1)
    lignesDeReserves, reserveLevee, echeanceReserve, etatReserve,
    reservesDuControle, reservesOuvertes, reservesEnRetard, adresseOtReserve,
  };
})());
