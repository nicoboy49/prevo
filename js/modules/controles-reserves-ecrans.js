'use strict';
// Controles — réserves à l'écran, fiche d'un contrôle (2.2, lot L2, CS170 ; CONCEPTION-L2-L3 §3.4).
// - T418 : la carte « Réserves » de la fiche (Controles.interne.carteReserves), les champs des réserves de la
//   fenêtre « Enregistrer le contrôle réalisé » (champsReservesRealisation) et les entrées du journal des réserves
//   pour l'historique de la fiche (entreesJournalReserves, marqueurs traduits à l'affichage, D156) ;
// - T419 : les fenêtres « Lever la réserve », « Modifier la réserve », « Ajouter une réserve » ;
// - T420 : « Créer un OT » depuis une réserve (#/ot/nouveau pré-rempli ; rien n'est créé sans « Créer »).
// Profils : le responsable écrit ; le technicien lit (aucun bouton d'écriture rendu) ; le demandeur n'a pas accès.
// Chargé juste après controles-ecrans.js. Complète l'objet Controles ; la fiche (controles-ecrans.js) appelle ce
// fichier par Controles.interne, au moment de l'appel.

Object.assign(Controles, (() => {

  // Règles de controles-regles.js et controles-reserves.js (chargés avant).
  const { texte, dateIso, DELAI_LEVEE_PAR_DEFAUT_JOURS, texteCourtReserve } = Controles.interne;
  const { reservesDuControle, reservesOuvertes, reserveLevee, etatReserve, lignesDeReserves } = Controles;
  const [EN_RETARD, A_LEVER, LEVEE] = Controles.STATUTS_RESERVE;

  // ===========================================================================================
  // 1. Carte « Réserves » de la fiche (technicien et responsable)
  // ===========================================================================================

  /** Badge de l'état d'une réserve (le texte dit toujours l'état, la couleur aide) : « à lever » (ambre), « en
   *  retard » (rouge), « levée le 10/12/2025 » ou, réserve reprise levée sans date (D183), « levée, date inconnue ». */
  function badgeReserve(reserve, etatCalcule) {
    if (etatCalcule.statut === LEVEE) {
      const date = dateIso(reserve.date_levee);
      return UI.badgeStatut(LEVEE, 'ok', date ? I18n.t('controles.carte_reserves.levee_le', { date: UI.dateFr(date) })
        : I18n.t('controles.carte_reserves.levee_date_inconnue'));
    }
    if (etatCalcule.statut === EN_RETARD) return UI.badgeStatut(EN_RETARD, 'ko', I18n.t('controles.carte_reserves.en_retard'));
    return UI.badgeStatut(A_LEVER, 'attention', I18n.t('controles.carte_reserves.a_lever'));
  }

  /** Échéance d'une réserve ouverte : « échéance le 12/12/2025 », suivie de « (30 jours après le contrôle) » quand
   *  elle est calculée (D187) ; date du contrôle inconnue : « échéance inconnue (date du contrôle inconnue) ». */
  function texteEcheance(etatCalcule) {
    if (!etatCalcule.echeance) return I18n.t('controles.carte_reserves.echeance_inconnue');
    const date = UI.dateFr(etatCalcule.echeance);
    return etatCalcule.parDefaut
      ? I18n.t('controles.carte_reserves.echeance_le_par_defaut', { date, jours: DELAI_LEVEE_PAR_DEFAUT_JOURS })
      : I18n.t('controles.carte_reserves.echeance_le', { date });
  }

  /** OT lié : lien et statut ; identifiant seul s'il est introuvable. */
  function otLie(reserve) {
    const otId = texte(reserve.ot_id);
    if (!otId) return '';
    const ot = Donnees.trouver('ordres_travail', otId);
    return UI.html`<span class="controles-reserve-ot">${I18n.t('controles.carte_reserves.ot_lie')} ${ot
      ? UI.html`<a href="#/ot/${encodeURIComponent(otId)}">${otId}</a> ${UI.badgeValeur('ordres_travail', 'statut', ot.statut)}`
      : I18n.t('controles.carte_reserves.ot_introuvable', { otId })}</span>`;
  }

  /** Commentaire de levée ; celui des réserves reprises levées (D183, écrit en français dans les données) est
   *  affiché traduit. */
  function commentaireLevee(reserve) {
    const commentaire = texte(reserve.commentaire_levee);
    if (!commentaire) return '';
    const affiche = commentaire === Formats.COMMENTAIRE_LEVEE_REPRISE
      ? I18n.t('controles.carte_reserves.commentaire_reprise') : commentaire;
    return UI.html`<p class="controles-reserve-commentaire">${I18n.t('controles.carte_reserves.ce_qui_a_ete_fait', { commentaire: affiche })}</p>`;
  }

  /** Une réserve : texte ; badge ; gravité s'il y en a une ; échéance (ouverte) ; OT lié ; commentaire de levée. */
  function elementReserve(reserve, jour) {
    const etatCalcule = etatReserve(reserve, jour);
    const levee = etatCalcule.statut === LEVEE;
    const gravite = texte(reserve.gravite);
    return UI.html`<li class="controles-reserve" data-reserve="${reserve.id}" data-statut="${etatCalcule.statut}">
      <p class="controles-reserve-texte">${reserve.texte}</p>
      <p class="controles-reserve-meta">${badgeReserve(reserve, etatCalcule)}
        ${gravite ? UI.html`<span class="controles-reserve-gravite">${I18n.t('controles.carte_reserves.gravite', { gravite: Schema.libelleValeur('reserves_controle', 'gravite', gravite) })}</span>` : ''}
        ${levee ? '' : UI.html`<span class="controles-reserve-echeance">${texteEcheance(etatCalcule)}</span>`}
        ${otLie(reserve)}</p>
      ${levee ? commentaireLevee(reserve) : ''}</li>`;
  }

  /** Un groupe par réalisation : « Contrôle du 12/11/2025 — 2 réserves », les ouvertes, puis les levées repliées
   *  sous « Voir les réserves levées (1) ». */
  function groupeReserves(groupe, jour) {
    const n = groupe.reserves.length;
    const ouvertes = groupe.reserves.filter((reserve) => !reserveLevee(reserve));
    const levees = groupe.reserves.filter(reserveLevee);
    const titre = groupe.date_controle
      ? I18n.t('controles.carte_reserves.groupe', { date: UI.dateFr(groupe.date_controle), n })
      : I18n.t('controles.carte_reserves.groupe_sans_date', { n });
    return UI.html`<section class="controles-reserves-groupe" data-date-controle="${groupe.date_controle}">
      <h3>${titre}</h3>
      ${ouvertes.length ? UI.html`<ul class="controles-reserves-liste">${ouvertes.map((reserve) => elementReserve(reserve, jour))}</ul>` : ''}
      ${levees.length ? UI.html`<details class="controles-reserves-levees"><summary>${I18n.t('controles.carte_reserves.voir_levees', { n: levees.length })}</summary>
        <ul class="controles-reserves-liste">${levees.map((reserve) => elementReserve(reserve, jour))}</ul></details>` : ''}
    </section>`;
  }

  /**
   * Carte « Réserves » d'un contrôle (élément DOM) : titre « Réserves (5, dont 2 à lever) » (« Réserves (3, toutes
   * levées) »), un groupe par réalisation, la plus récente d'abord (Controles.reservesDuControle) ; carte vide :
   * « Aucune réserve relevée. ». Lecture seule (technicien et responsable) : les boutons viendront avec les
   * fenêtres de levée et de correction (T419, T420).
   */
  function carteReserves(controle) {
    const jour = Donnees.aujourdhui();
    const groupes = reservesDuControle(controle.id);
    const total = groupes.reduce((somme, groupe) => somme + groupe.reserves.length, 0);
    const ouvertes = reservesOuvertes(controle.id).length;
    let titre = I18n.t('controles.carte_reserves.titre_vide');
    if (total && ouvertes) titre = I18n.t('controles.carte_reserves.titre', { n: total, ouvertes });
    else if (total) titre = I18n.t('controles.carte_reserves.titre_toutes_levees', { n: total });
    return UI.element(UI.html`<article class="carte controles-reserves" data-controle="${controle.id}">
      <h2>${titre}</h2>
      ${total ? groupes.map((groupe) => groupeReserves(groupe, jour))
    : UI.html`<p class="muted controles-reserves-vide">${I18n.t('controles.carte_reserves.aucune')}</p>`}
    </article>`);
  }

  /** Nombre de réserves relevées à la dernière réalisation (carte « Dernier contrôle ») : celles dont la date du
   *  contrôle est la dernière date du contrôle. */
  function reservesDuDernierControle(controle) {
    const derniere = dateIso(controle.derniere_date);
    const groupe = reservesDuControle(controle.id).find((g) => g.date_controle === derniere);
    return groupe ? groupe.reserves.length : 0;
  }

  // ===========================================================================================
  // 2. Fenêtre « Enregistrer le contrôle réalisé » : réserves relevées, échéance commune, aperçu
  // ===========================================================================================

  /**
   * Champs des réserves de la fenêtre « Enregistrer le contrôle réalisé » (blocs DOM, dans l'ordre) : « Réserves
   * relevées » (reserves : une ligne par réserve), « Échéance de levée (facultatif) » (echeance_levee : commune aux
   * réserves de ce contrôle), aperçu en direct « 3 réserves seront enregistrées. » (Controles.lignesDeReserves, la
   * règle de l'écriture) et, s'il en reste, « 2 réserves des contrôles précédents restent à lever. ».
   */
  function champsReservesRealisation(controle) {
    const reserves = UI.champ({ nom: 'reserves', type: 'texte_long', libelle: I18n.t('controles.ouvrir_realisation.reserves_relevees') }, '',
      { aide: I18n.t('controles.ouvrir_realisation.reserves_aide') });
    const echeance = UI.champ({ nom: 'echeance_levee', type: 'date', libelle: I18n.t('controles.ouvrir_realisation.echeance_levee') }, '',
      { aide: I18n.t('controles.ouvrir_realisation.echeance_aide', { jours: DELAI_LEVEE_PAR_DEFAUT_JOURS }) });
    const apercu = UI.element(UI.html`<p class="note controles-apercu-reserves" role="status" aria-live="polite"></p>`);
    const saisie = UI.$('textarea', reserves);
    const montrer = () => {
      const n = lignesDeReserves(saisie.value).length;
      apercu.textContent = n ? I18n.t('controles.ouvrir_realisation.apercu', { n }) : '';
    };
    saisie.addEventListener('input', montrer);
    const blocs = [reserves, echeance, apercu];
    const restantes = reservesOuvertes(controle.id).length;
    if (restantes) {
      blocs.push(UI.element(UI.html`<p class="note controles-reserves-precedentes">${I18n.t('controles.ouvrir_realisation.ouvertes_precedentes', { n: restantes })}</p>`));
    }
    return blocs;
  }

  /** Message de fin de la fenêtre : « Contrôle réalisé enregistré, 3 réserves relevées. » (sans réserve : « Contrôle
   *  réalisé enregistré. »). */
  function messageRealisation(saisieReserves) {
    const n = lignesDeReserves(saisieReserves).length;
    return n ? I18n.t('controles.ouvrir_realisation.enregistre_avec_reserves', { n })
      : I18n.t('controles.ouvrir_realisation.controle_realise_enregistre');
  }

  // ===========================================================================================
  // 3. Historique : entrées du journal des réserves du contrôle
  // ===========================================================================================

  // Marqueurs écrits au journal par controles-reserves.js (D156 : texte français fixe), après « création — » ou
  // « modification : champs — » (Donnees.modifier) ; reconnus par des expressions régulières littérales, traduits
  // à l'affichage.
  const MOTIF_RELEVEES = /^réserves relevées au contrôle du (.+?) : (\d+)$/;
  const MOTIF_RESERVE_LEVEE = /^réserve levée le (.+?) : ([\s\S]*)$/;
  const MOTIF_CORRECTION = /^correction de la réserve$/;
  const MOTIF_RELIEE = /^reliée à (\S+)$/;

  /** Action traduite d'une entrée du journal des réserves (« Réserve levée le 10/12/2025 : … »), ou null si le
   *  marqueur n'est pas un de ceux des réserves. */
  function actionReserve(action) {
    const brute = texte(action);
    const coupure = brute.indexOf(' — ');
    if (coupure < 0) return null;
    const complement = brute.slice(coupure + 3);
    let trouve = MOTIF_RELEVEES.exec(complement);
    if (trouve) return I18n.t('controles.journal.reserves_relevees', { date: trouve[1], n: trouve[2] });
    trouve = MOTIF_RESERVE_LEVEE.exec(complement);
    if (trouve) return I18n.t('controles.journal.reserve_levee', { date: trouve[1], commentaire: trouve[2] });
    if (MOTIF_CORRECTION.test(complement)) return I18n.t('controles.journal.reserve_corrigee');
    trouve = MOTIF_RELIEE.exec(complement);
    return trouve ? I18n.t('controles.journal.reserve_reliee', { otId: trouve[1] }) : null;
  }

  /**
   * Entrées du journal des réserves d'un contrôle (table reserves_controle, id_ligne = une de ses réserves), pour
   * l'historique de la fiche : [{ id, date_heure, profil, poste, action, detail }]. action : marqueur des réserves
   * traduit (actionReserve), sinon `lireAction(action)` (la lecture de la fiche : création, import, ou telle
   * quelle). Les entrées d'une même écriture (même heure, même action, même poste : « réserves relevées … : 3 » est
   * écrit une fois par réserve) n'en font qu'une ; detail : texte court de la réserve quand l'entrée n'en concerne
   * qu'une, sinon ''.
   */
  function entreesJournalReserves(controle, lireAction) {
    const reserves = new Map(Donnees.lignes('reserves_controle')
      .filter((reserve) => texte(reserve.controle_id) === texte(controle.id))
      .map((reserve) => [texte(reserve.id), reserve]));
    if (!reserves.size) return [];
    const fusionnees = new Map();
    Donnees.lignes('journal').forEach((entree) => {
      const id = texte(entree.id_ligne);
      if (entree.table !== 'reserves_controle' || !reserves.has(id)) return;
      const cle = JSON.stringify([entree.date_heure, entree.action, entree.profil, entree.poste].map(texte));
      if (!fusionnees.has(cle)) fusionnees.set(cle, { entree, ids: new Set() });
      fusionnees.get(cle).ids.add(id);
    });
    return Array.from(fusionnees.values(), ({ entree, ids }) => ({
      id: entree.id, date_heure: entree.date_heure, profil: entree.profil, poste: entree.poste,
      action: actionReserve(entree.action) || lireAction(entree.action),
      detail: ids.size === 1 ? texteCourtReserve(reserves.get(Array.from(ids)[0])) : '',
    }));
  }

  // Outils prêtés à la fiche (controles-ecrans.js), cherchés au moment de l'appel.
  Object.assign(Controles.interne, { carteReserves, reservesDuDernierControle, champsReservesRealisation,
    messageRealisation, entreesJournalReserves });

  return {};
})());
