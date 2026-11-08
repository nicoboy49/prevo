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

  // ===========================================================================================
  // 4. Écritures des réserves (T413, conception L2-L3 §3.3)
  // ===========================================================================================
  // Toutes par Donnees.modifier('reserves_controle') ; les contrôles sont refaits DANS la fonction de mutation, sur
  // les lignes fraîches qu'elle reçoit (elle est rejouée sur les lignes relues si un autre poste a écrit
  // entre-temps) ; un refus lève Donnees.ErreurValidation et rien n'est écrit ; jamais de suppression. Actions du
  // journal : marqueurs français fixes (D156), traduits à l'affichage (T418).

  /** Champs qu'une correction peut changer (modifierReserve) ; la levée et le contrôle d'origine sont des faits. */
  const CHAMPS_MODIFIABLES = ['texte', 'gravite', 'echeance_levee'];

  function ErreurValidation(message) {
    return new Donnees.ErreurValidation(message);
  }

  /** Lève une ErreurValidation qui réunit les messages de [{ nom, message }] ; rien si la liste est vide. */
  function refuserSiErreurs(erreurs) {
    if (erreurs.length) throw ErreurValidation(erreurs.map((erreur) => erreur.message).join(' '));
  }

  /** Erreur [{ nom, message }] d'un champ date : illisible, ou (si `pasFuture`) après `jour`. Champ vide : []. */
  function erreursDate(nom, valeur, jour, pasFuture, libelle) {
    if (!texte(valeur)) return [];
    if (!dateIso(valeur) || texte(valeur).length !== 10) return [{ nom, message: I18n.t('controles.erreurs_date.date_illisible_format_aaaa', { libelle }) }];
    if (pasFuture && texte(valeur) > jour) return [{ nom, message: I18n.t('controles.erreurs_date.peut_pas_etre_futur', { libelle }) }];
    return [];
  }

  /** Échéance de levée (facultative) : lisible, et pas avant la date du contrôle quand celle-ci est connue. */
  function erreursEcheance(echeance, dateControle) {
    const erreurs = erreursDate('echeance_levee', echeance, '', false, I18n.t('controles.verifier_reserve.echeance_levee'));
    const date = dateIso(dateControle);
    if (!erreurs.length && texte(echeance) && date && texte(echeance) < date) {
      erreurs.push({ nom: 'echeance_levee', message: I18n.t('controles.verifier_reserve.echeance_avant_controle', { date: UI.dateFr(date) }) });
    }
    return erreurs;
  }

  /** Gravité lue (casse ignorée) ; vide permis, sinon une valeur du schéma (mineure, majeure, critique ; D155). */
  function graviteLue(valeur) {
    return texte(valeur).toLowerCase();
  }

  function erreursGravite(gravite) {
    if (!gravite || Schema.champ('reserves_controle', 'gravite').valeurs.includes(gravite)) return [];
    return [{ nom: 'gravite', message: I18n.t('controles.verifier_reserve.gravite_inconnue', { gravite }) }];
  }

  /** La réserve `reserveId` parmi les lignes fraîches, sinon refus. */
  function reserveDe(lignes, reserveId) {
    const id = texte(reserveId);
    const reserve = id ? lignes.find((ligne) => texte(ligne.id) === id) : null;
    if (!reserve) throw ErreurValidation(I18n.t('controles.verifier_reserve.reserve_introuvable', { reserveId: id || I18n.t('controles.ligne_du_controle.non_choisi') }));
    return reserve;
  }

  /** Le contrôle `controleId`, sinon refus (même message que les écritures des contrôles). */
  function controleDe(controleId) {
    const id = texte(controleId);
    const controle = id ? Donnees.trouver('controles_reglementaires', id) : null;
    if (!controle) throw ErreurValidation(I18n.t('controles.ligne_du_controle.controle_introuvable', { controleId: id || I18n.t('controles.ligne_du_controle.non_choisi') }));
    return controle;
  }

  /** OT donné pour une réserve (levée, lien) : il existe et porte l'équipement du contrôle de la réserve. */
  function erreursOt(otId, reserve) {
    if (!otId) return [];
    const ot = Donnees.trouver('ordres_travail', otId);
    if (!ot) return [{ nom: 'ot_id', message: I18n.t('controles.verifier_reserve.ot_introuvable', { otId }) }];
    const controle = Donnees.trouver('controles_reglementaires', texte(reserve.controle_id));
    if (!controle || texte(ot.equipement_id) !== texte(controle.equipement_id)) {
      return [{ nom: 'ot_id', message: I18n.t('controles.verifier_reserve.ot_autre_equipement', { otId }) }];
    }
    return [];
  }

  // --- Ajout -------------------------------------------------------------------------------------

  function saisieAjout(valeurs) {
    const v = valeurs || {};
    return { date_controle: texte(v.date_controle), lignes: lignesDeReserves(v.texte), gravite: graviteLue(v.gravite),
      echeance_levee: texte(v.echeance_levee) };
  }

  /**
   * Contrôle d'un ajout de réserves ({ date_controle, texte, gravite, echeance_levee }) : [{ nom, message }]. Date du
   * contrôle obligatoire, lisible, pas dans le futur ; au moins une réserve dans le texte ; gravité connue ou vide ;
   * échéance lisible ou vide, pas avant la date du contrôle.
   */
  function verifierAjoutReserves(valeurs, aujourdhui) {
    const saisie = saisieAjout(valeurs);
    const erreurs = saisie.date_controle
      ? erreursDate('date_controle', saisie.date_controle, dateDuJour(aujourdhui), true, I18n.t('controles.verifier_realisation.date_controle'))
      : [{ nom: 'date_controle', message: I18n.t('controles.verifier_realisation.indiquez_date_controle') }];
    const dateLue = erreurs.length ? '' : saisie.date_controle;
    if (!saisie.lignes.length) erreurs.push({ nom: 'texte', message: I18n.t('controles.verifier_reserve.texte_sans_reserve') });
    return erreurs.concat(erreursGravite(saisie.gravite), erreursEcheance(saisie.echeance_levee, dateLue));
  }

  /**
   * Ajoute à un contrôle les réserves relevées à une date : une ligne par réserve du texte (lignesDeReserves), avec
   * la gravité et l'échéance de levée données (facultatives ; échéance vide : 30 jours après le contrôle à
   * l'affichage, D187), levee 0. Rejouable (essai après un conflit, double clic, même saisie envoyée deux fois) :
   * une réserve de même contrôle, même date et même texte n'est jamais recréée (un texte répété n fois dans la
   * saisie donne n réserves au plus). N'efface ni ne modifie aucune réserve existante. Refus : voir
   * verifierAjoutReserves ; contrôle introuvable. Renvoie les identifiants créés (RES-…), [] si toutes existaient.
   * Journal : « réserves relevées au contrôle du JJ/MM/AAAA : n » (n : réserves du texte).
   */
  async function ajouterReserves(controleId, valeurs) {
    const saisie = saisieAjout(valeurs);
    const controle = controleDe(controleId);
    const id = texte(controle.id);
    const action = 'réserves relevées au contrôle du ' + UI.dateFr(saisie.date_controle) + ' : ' + saisie.lignes.length;
    return Donnees.modifier('reserves_controle', (lignes, outils) => {
      refuserSiErreurs(verifierAjoutReserves(valeurs, outils.aujourdhui()));
      const dejaLa = new Map();                 // texte → réserves déjà enregistrées pour ce contrôle et cette date
      lignes.forEach((ligne) => {
        if (texte(ligne.controle_id) !== id || dateIso(ligne.date_controle) !== saisie.date_controle) return;
        dejaLa.set(texte(ligne.texte), (dejaLa.get(texte(ligne.texte)) || 0) + 1);
      });
      const creees = [];
      saisie.lignes.forEach((ligneTexte) => {
        const restantes = dejaLa.get(ligneTexte) || 0;
        if (restantes > 0) { dejaLa.set(ligneTexte, restantes - 1); return; }
        const nouvelle = outils.nouvelId(lignes);
        lignes.push({ id: nouvelle, controle_id: id, date_controle: saisie.date_controle, texte: ligneTexte,
          gravite: saisie.gravite, echeance_levee: saisie.echeance_levee, levee: '0', date_levee: '',
          commentaire_levee: '', ot_id: '' });
        creees.push(nouvelle);
      });
      return creees;
    }, { action });
  }

  // --- Levée -------------------------------------------------------------------------------------

  function saisieLevee(valeurs) {
    const v = valeurs || {};
    return { date: texte(v.date), commentaire: texte(v.commentaire), ot_id: texte(v.ot_id) };
  }

  /**
   * Contrôle d'une levée ({ date, commentaire, ot_id }) : [{ nom, message }]. Réserve ouverte ; date obligatoire,
   * ni future ni avant la date du contrôle de la réserve ; commentaire obligatoire ; OT facultatif, existant, du
   * même équipement que le contrôle.
   */
  function verifierLeveeReserve(reserve, valeurs, aujourdhui) {
    if (reserveLevee(reserve)) return [{ nom: 'date', message: I18n.t('controles.lever_reserve.reserve_deja_levee') }];
    const saisie = saisieLevee(valeurs);
    const erreurs = saisie.date
      ? erreursDate('date', saisie.date, dateDuJour(aujourdhui), true, I18n.t('controles.lever_reserve.date_levee'))
      : [{ nom: 'date', message: I18n.t('controles.lever_reserve.indiquez_date_levee') }];
    const dateControle = dateIso(reserve.date_controle);
    if (!erreurs.length && dateControle && saisie.date < dateControle) {
      erreurs.push({ nom: 'date', message: I18n.t('controles.lever_reserve.levee_avant_controle', { date: UI.dateFr(dateControle) }) });
    }
    if (!saisie.commentaire) erreurs.push({ nom: 'commentaire', message: I18n.t('controles.lever_reserve.decrivez_ce_qui_a_ete_fait') });
    return erreurs.concat(erreursOt(saisie.ot_id, reserve));
  }

  /**
   * Lève une réserve : levee 1, date_levee, commentaire_levee, et ot_id s'il est donné (sinon l'OT déjà lié reste).
   * Les autres réserves du contrôle ne changent pas. Refus : voir verifierLeveeReserve ; réserve introuvable.
   * Journal : « réserve levée le JJ/MM/AAAA : commentaire ».
   */
  async function leverReserve(reserveId, valeurs) {
    const saisie = saisieLevee(valeurs);
    return Donnees.modifier('reserves_controle', (lignes, outils) => {
      const reserve = reserveDe(lignes, reserveId);
      refuserSiErreurs(verifierLeveeReserve(reserve, saisie, outils.aujourdhui()));
      reserve.levee = '1';
      reserve.date_levee = saisie.date;
      reserve.commentaire_levee = saisie.commentaire;
      if (saisie.ot_id) reserve.ot_id = saisie.ot_id;
      return true;
    }, { action: 'réserve levée le ' + UI.dateFr(saisie.date) + ' : ' + saisie.commentaire });
  }

  // --- Correction --------------------------------------------------------------------------------

  /** Champs donnés d'une correction (absents, undefined ou null : non changés), sans espaces de bord. */
  function saisieModification(valeurs) {
    const propres = {};
    CHAMPS_MODIFIABLES.forEach((nom) => {
      if (!valeurs || valeurs[nom] === undefined || valeurs[nom] === null) return;
      propres[nom] = nom === 'gravite' ? graviteLue(valeurs[nom]) : texte(valeurs[nom]);
    });
    return propres;
  }

  /**
   * Contrôle d'une correction ({ texte, gravite, echeance_levee }, chacun facultatif) : [{ nom, message }]. Réserve
   * ouverte seulement (une levée est un fait) ; texte donné non vide ; gravité connue ou vide ; échéance lisible ou
   * vide (retour aux 30 jours, D187), pas avant la date du contrôle.
   */
  function verifierModificationReserve(reserve, valeurs) {
    if (reserveLevee(reserve)) return [{ nom: 'texte', message: I18n.t('controles.modifier_reserve.reserve_levee') }];
    const propres = saisieModification(valeurs);
    const erreurs = [];
    if (propres.texte !== undefined && !propres.texte) erreurs.push({ nom: 'texte', message: I18n.t('controles.modifier_reserve.texte_obligatoire') });
    if (propres.gravite !== undefined) erreurs.push(...erreursGravite(propres.gravite));
    if (propres.echeance_levee !== undefined) erreurs.push(...erreursEcheance(propres.echeance_levee, reserve.date_controle));
    return erreurs;
  }

  /** Corrige une réserve ouverte (texte, gravité, échéance) ; renvoie les champs réellement changés.
   *  Journal : « correction de la réserve ». */
  async function modifierReserve(reserveId, valeurs) {
    const propres = saisieModification(valeurs);
    return Donnees.modifier('reserves_controle', (lignes) => {
      const reserve = reserveDe(lignes, reserveId);
      refuserSiErreurs(verifierModificationReserve(reserve, propres));
      const changes = Object.keys(propres).filter((nom) => texte(reserve[nom]) !== propres[nom]);
      changes.forEach((nom) => { reserve[nom] = propres[nom]; });
      return changes;
    }, { action: 'correction de la réserve' });
  }

  // --- Lien avec un OT ---------------------------------------------------------------------------

  /**
   * Relie un OT à une réserve, une seule fois (« Créer un OT » depuis la réserve, T420) : réserve ouverte sans OT
   * lié (sinon refus « déjà reliée à OT-… ») ; OT existant, du même équipement. Déjà reliée à CE même OT : rien à
   * écrire, accepté (rejouable). Renvoie true. Journal : « reliée à OT-… ».
   */
  async function lierOtAReserve(reserveId, otId) {
    const ot = texte(otId);
    return Donnees.modifier('reserves_controle', (lignes) => {
      const reserve = reserveDe(lignes, reserveId);
      const lie = texte(reserve.ot_id);
      if (!ot) throw ErreurValidation(I18n.t('controles.lier_ot_a_reserve.choisissez_ot'));
      if (lie === ot) return true;
      if (reserveLevee(reserve)) throw ErreurValidation(I18n.t('controles.lier_ot_a_reserve.reserve_levee'));
      if (lie) throw ErreurValidation(I18n.t('controles.lier_ot_a_reserve.deja_reliee', { otId: lie }));
      refuserSiErreurs(erreursOt(ot, reserve));
      reserve.ot_id = ot;
      return true;
    }, { action: 'reliée à ' + ot });
  }

  // Usage interne au module (pas une API) : pour les écritures des contrôles (controles-ecritures.js) et les écrans
  // (T418-T420 : erreurs montrées sous les champs avant d'écrire).
  Object.assign(Controles.interne, { DELAI_LEVEE_PAR_DEFAUT_JOURS, ajouterJours, texteCourtReserve,
    refuserSiErreurs, erreursDate, erreursEcheance, verifierAjoutReserves, verifierLeveeReserve,
    verifierModificationReserve });

  return {
    STATUTS_RESERVE,
    // règles pures des réserves (conception L2-L3 §3.1)
    lignesDeReserves, reserveLevee, echeanceReserve, etatReserve,
    reservesDuControle, reservesOuvertes, reservesEnRetard, adresseOtReserve,
    // écritures des réserves (conception L2-L3 §3.3)
    ajouterReserves, leverReserve, modifierReserve, lierOtAReserve,
  };
})());
