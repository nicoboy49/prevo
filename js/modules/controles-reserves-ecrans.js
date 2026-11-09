'use strict';
// Controles — réserves à l'écran, fiche d'un contrôle (2.2, lot L2, CS170 ; CONCEPTION-L2-L3 §3.4).
// - T418 : la carte « Réserves » de la fiche (Controles.interne.carteReserves), les champs des réserves de la
//   fenêtre « Enregistrer le contrôle réalisé » (champsReservesRealisation) et les entrées du journal des réserves
//   pour l'historique de la fiche (entreesJournalReserves, marqueurs traduits à l'affichage, D156) ;
// - T419 : les boutons de la carte (« Lever », « Modifier » par réserve ouverte, « Ajouter une réserve »), le rappel
//   « L'OT … est clôturé » et les fenêtres « Lever la réserve », « Modifier la réserve », « Ajouter une réserve »
//   (ouvrirLeveeReserve, ouvrirModificationReserve, ouvrirAjoutReserve) ;
// - T420 : « Créer un OT » depuis une réserve (#/ot/nouveau pré-rempli ; rien n'est créé sans « Créer »).
// Profils : le responsable écrit ; le technicien lit (aucun bouton d'écriture rendu) ; le demandeur n'a pas accès.
// Chargé juste après controles-ecrans.js. Complète l'objet Controles ; la fiche (controles-ecrans.js) appelle ce
// fichier par Controles.interne, au moment de l'appel.

Object.assign(Controles, (() => {

  // Règles de controles-regles.js et controles-reserves.js (chargés avant).
  const { texte, dateIso, DELAI_LEVEE_PAR_DEFAUT_JOURS, texteCourtReserve, verifierLeveeReserve,
    verifierModificationReserve, verifierAjoutReserves } = Controles.interne;
  const { reservesDuControle, reservesOuvertes, reserveLevee, etatReserve, lignesDeReserves } = Controles;
  const [EN_RETARD, A_LEVER, LEVEE] = Controles.STATUTS_RESERVE;
  // Statuts d'un OT clôturé (valeurs stockées, D155) : son OT clôturé rappelle de lever la réserve (§3.4).
  const STATUTS_OT_CLOTURES = ['Clôturé techniquement', 'Clôturé administrativement'];

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

  /** OT lié à une réserve OUVERTE et clôturé (techniquement ou administrativement), sinon null. */
  function otLieCloture(reserve) {
    const otId = texte(reserve.ot_id);
    if (!otId || reserveLevee(reserve)) return null;
    const ot = Donnees.trouver('ordres_travail', otId);
    return ot && STATUTS_OT_CLOTURES.includes(texte(ot.statut)) ? ot : null;
  }

  /** Responsable, réserve ouverte : rappel « L'OT … est clôturé : levez la réserve si le travail l'a corrigée. »
   *  (OT lié clôturé), puis « Lever » et « Modifier ». */
  function actionsReserve(reserve) {
    const ot = otLieCloture(reserve);
    return UI.html`${ot ? UI.html`<p class="controles-reserve-rappel" role="note">${UI.icone('alerte')}<span>${I18n.t('controles.carte_reserves.rappel_ot_cloture', { otId: ot.id })}</span></p>` : ''}
      <div class="actions controles-reserve-actions">
        <button type="button" class="btn btn-secondaire" data-action="lever">${UI.icone('valider')}${I18n.t('controles.carte_reserves.lever')}</button>
        <button type="button" class="btn btn-fantome" data-action="modifier">${I18n.t('commun.bouton.modifier')}</button></div>`;
  }

  /** Une réserve : texte ; badge ; gravité s'il y en a une ; échéance (ouverte) ; OT lié ; commentaire de levée ;
   *  responsable et réserve ouverte : rappel de l'OT clôturé et boutons (actionsReserve). */
  function elementReserve(reserve, jour, responsable) {
    const etatCalcule = etatReserve(reserve, jour);
    const levee = etatCalcule.statut === LEVEE;
    const gravite = texte(reserve.gravite);
    return UI.html`<li class="controles-reserve" data-reserve="${reserve.id}" data-statut="${etatCalcule.statut}">
      <p class="controles-reserve-texte">${reserve.texte}</p>
      <p class="controles-reserve-meta">${badgeReserve(reserve, etatCalcule)}
        ${gravite ? UI.html`<span class="controles-reserve-gravite">${I18n.t('controles.carte_reserves.gravite', { gravite: Schema.libelleValeur('reserves_controle', 'gravite', gravite) })}</span>` : ''}
        ${levee ? '' : UI.html`<span class="controles-reserve-echeance">${texteEcheance(etatCalcule)}</span>`}
        ${otLie(reserve)}</p>
      ${levee ? commentaireLevee(reserve) : ''}
      ${!levee && responsable ? actionsReserve(reserve) : ''}</li>`;
  }

  /** Un groupe par réalisation : « Contrôle du 12/11/2025 — 2 réserves », les ouvertes, puis les levées repliées
   *  sous « Voir les réserves levées (1) ». */
  function groupeReserves(groupe, jour, responsable) {
    const n = groupe.reserves.length;
    const ouvertes = groupe.reserves.filter((reserve) => !reserveLevee(reserve));
    const levees = groupe.reserves.filter(reserveLevee);
    const titre = groupe.date_controle
      ? I18n.t('controles.carte_reserves.groupe', { date: UI.dateFr(groupe.date_controle), n })
      : I18n.t('controles.carte_reserves.groupe_sans_date', { n });
    return UI.html`<section class="controles-reserves-groupe" data-date-controle="${groupe.date_controle}">
      <h3>${titre}</h3>
      ${ouvertes.length ? UI.html`<ul class="controles-reserves-liste">${ouvertes.map((reserve) => elementReserve(reserve, jour, responsable))}</ul>` : ''}
      ${levees.length ? UI.html`<details class="controles-reserves-levees"><summary>${I18n.t('controles.carte_reserves.voir_levees', { n: levees.length })}</summary>
        <ul class="controles-reserves-liste">${levees.map((reserve) => elementReserve(reserve, jour, responsable))}</ul></details>` : ''}
    </section>`;
  }

  /**
   * Carte « Réserves » d'un contrôle (élément DOM) : titre « Réserves (5, dont 2 à lever) » (« Réserves (3, toutes
   * levées) »), un groupe par réalisation, la plus récente d'abord (Controles.reservesDuControle) ; carte vide :
   * « Aucune réserve relevée. ». Le technicien la lit seulement ; le responsable a en plus « Ajouter une réserve »
   * (en-tête) et, par réserve ouverte, « Lever » et « Modifier » (fenêtres du §4 ; T420 y ajoutera « Créer un OT »).
   */
  function carteReserves(controle) {
    const jour = Donnees.aujourdhui();
    const responsable = App.estResponsable();
    const groupes = reservesDuControle(controle.id);
    const total = groupes.reduce((somme, groupe) => somme + groupe.reserves.length, 0);
    const ouvertes = reservesOuvertes(controle.id).length;
    let titre = I18n.t('controles.carte_reserves.titre_vide');
    if (total && ouvertes) titre = I18n.t('controles.carte_reserves.titre', { n: total, ouvertes });
    else if (total) titre = I18n.t('controles.carte_reserves.titre_toutes_levees', { n: total });
    const carte = UI.element(UI.html`<article class="carte controles-reserves" data-controle="${controle.id}">
      <div class="entete-carte"><h2>${titre}</h2>
        ${responsable ? UI.html`<button type="button" class="btn btn-secondaire" data-action="ajouter">${UI.icone('ajouter')}${I18n.t('controles.carte_reserves.ajouter_reserve')}</button>` : ''}</div>
      ${total ? groupes.map((groupe) => groupeReserves(groupe, jour, responsable))
    : UI.html`<p class="muted controles-reserves-vide">${I18n.t('controles.carte_reserves.aucune')}</p>`}
    </article>`);
    if (responsable) carte.addEventListener('click', (evenement) => brancherBouton(evenement, controle.id));
    return carte;
  }

  /** Clic dans la carte (responsable) : « Ajouter une réserve », « Lever », « Modifier » ouvrent leur fenêtre. */
  function brancherBouton(evenement, controleId) {
    const bouton = evenement.target.closest('button[data-action]');
    if (!bouton) return;
    const element = bouton.closest('.controles-reserve');
    const reserveId = element ? element.dataset.reserve : '';
    if (bouton.dataset.action === 'ajouter') ouvrirAjoutReserve(controleId);
    else if (bouton.dataset.action === 'lever') ouvrirLeveeReserve(reserveId);
    else if (bouton.dataset.action === 'modifier') ouvrirModificationReserve(reserveId);
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

  // ===========================================================================================
  // 4. Fenêtres « Lever la réserve », « Modifier la réserve », « Ajouter une réserve » (responsable)
  // ===========================================================================================
  // Chaque fenêtre part de la ligne fraîche (un autre poste a pu écrire), montre les erreurs sous les champs avant
  // d'écrire (Controles.interne.verifier… : les règles mêmes de l'écriture, rien n'est écrit sur un refus), écrit par
  // Controles.leverReserve, modifierReserve ou ajouterReserves (refus refaits sur la ligne fraîche), puis toast et
  // fiche redessinée (carte, statut, historique). Rend true si l'écriture est faite.

  /** La réserve d'identifiant `reserveId` telle qu'en mémoire, ou null. */
  function reserveFraiche(reserveId) {
    const id = texte(reserveId);
    return (id && Donnees.trouver('reserves_controle', id)) || null;
  }

  async function apresEcriture(message) {
    App.marquerSaisie(false);
    UI.toast(message, 'succes');
    await App.reafficher();
  }

  /** En tête de fenêtre : « Relevée au contrôle du 12/11/2025 » et, si `avecTexte`, le texte de la réserve. */
  function rappelReserve(reserve, avecTexte) {
    const date = dateIso(reserve.date_controle);
    return UI.html`<div class="controles-rappel-reserve">
      <p class="muted">${date ? I18n.t('controles.rappel_reserve.relevee_le', { date: UI.dateFr(date) }) : I18n.t('controles.rappel_reserve.date_inconnue')}</p>
      ${avecTexte ? UI.html`<blockquote class="controles-rappel-texte">${reserve.texte}</blockquote>` : ''}</div>`;
  }

  /** OT proposés à la levée : ceux de l'équipement du contrôle, les plus récents d'abord (« OT-2026-0042 — titre
   *  (Clôturé techniquement) »). */
  function optionsOt(reserve) {
    const controle = Donnees.trouver('controles_reglementaires', texte(reserve.controle_id));
    const equipementId = controle ? texte(controle.equipement_id) : '';
    if (!equipementId) return [];
    return Donnees.lignes('ordres_travail')
      .filter((ot) => texte(ot.equipement_id) === equipementId)
      .sort((a, b) => texte(b.date_creation).localeCompare(texte(a.date_creation))
        || texte(b.id).localeCompare(texte(a.id), 'fr', { numeric: true }))
      .map((ot) => ({ valeur: texte(ot.id), libelle: I18n.t('controles.ouvrir_levee_reserve.option_ot',
        { otId: texte(ot.id), titre: texte(ot.titre), statut: Schema.libelleValeur('ordres_travail', 'statut', texte(ot.statut)) }) }));
  }

  /**
   * Levée proposée : { date, commentaire, ot_id } — aujourd'hui, rien, l'OT lié. OT lié clôturé (§3.4) : la date de
   * fin de l'OT (ou de sa clôture technique) quand elle est acceptable (ni future, ni avant le contrôle ; sinon
   * aujourd'hui) et « Levée par l'OT OT-… », écrit dans la langue de l'installation (texte des données, D156).
   */
  function leveeProposee(reserve, jour) {
    const proposee = { date: jour, commentaire: '', ot_id: texte(reserve.ot_id) };
    const ot = otLieCloture(reserve);
    if (!ot) return proposee;
    const fin = dateIso(ot.date_fin) || dateIso(ot.date_cloture_tech);
    const dateControle = dateIso(reserve.date_controle);
    if (fin && fin <= jour && (!dateControle || fin >= dateControle)) proposee.date = fin;
    proposee.commentaire = I18n.donnees('controles.ouvrir_levee_reserve.commentaire_par_ot', { otId: texte(ot.id) });
    return proposee;
  }

  /**
   * Fenêtre « Lever la réserve » : rappel du texte et de la date du contrôle ; « Levée le » (obligatoire, défaut
   * aujourd'hui, ni future ni avant le contrôle) ; « Ce qui a été fait » (obligatoire) ; « OT lié (facultatif) »
   * parmi les OT de l'équipement (défaut : l'OT lié). OT lié clôturé : pré-remplie (leveeProposee). Toast « Réserve
   * levée. » ; les autres réserves du contrôle ne changent pas.
   */
  async function ouvrirLeveeReserve(reserveId) {
    const reserve = reserveFraiche(reserveId);
    if (!reserve) return false;
    const jour = Donnees.aujourdhui();
    const proposee = leveeProposee(reserve, jour);
    const dateControle = dateIso(reserve.date_controle);
    const fait = await UI.fenetreAction({ classe: 'controles-fenetre controles-fenetre-reserve',
      titre: I18n.t('controles.ouvrir_levee_reserve.lever_reserve'),
      introduction: rappelReserve(reserve, true),
      champs: [
        UI.champ({ nom: 'date', type: 'date', libelle: I18n.t('controles.ouvrir_levee_reserve.levee_le') }, proposee.date,
          { obligatoire: true, attributs: dateControle ? { min: dateControle, max: jour } : { max: jour } }),
        UI.champ({ nom: 'commentaire', type: 'texte_long', libelle: I18n.t('controles.ouvrir_levee_reserve.ce_qui_a_ete_fait') },
          proposee.commentaire, { obligatoire: true }),
        UI.champ({ nom: 'ot_id', type: 'ref', libelle: I18n.t('controles.ouvrir_levee_reserve.ot_lie') }, proposee.ot_id,
          { liste: optionsOt(reserve) }),
      ],
      libelleValider: I18n.t('controles.ouvrir_levee_reserve.lever_reserve'),
      verifier: (valeurs) => verifierLeveeReserve(reserveFraiche(reserve.id) || reserve, valeurs),
      action: (valeurs) => Controles.leverReserve(reserve.id, valeurs),
    });
    if (fait) await apresEcriture(I18n.t('controles.ouvrir_levee_reserve.reserve_levee'));
    return fait;
  }

  /** Fenêtre « Modifier la réserve » (réserve ouverte : une levée est un fait) : texte, gravité, échéance (vide :
   *  30 jours après le contrôle). Toast « Réserve modifiée. » (rien de changé : « Aucune modification… »). */
  async function ouvrirModificationReserve(reserveId) {
    const reserve = reserveFraiche(reserveId);
    if (!reserve) return false;
    const dateControle = dateIso(reserve.date_controle);
    let changes = [];
    const fait = await UI.fenetreAction({ classe: 'controles-fenetre controles-fenetre-reserve',
      titre: I18n.t('controles.ouvrir_modification_reserve.modifier_reserve'),
      introduction: rappelReserve(reserve, false),
      champs: [
        UI.champ(Schema.champ('reserves_controle', 'texte'), texte(reserve.texte)),
        UI.champ(Schema.champ('reserves_controle', 'gravite'), texte(reserve.gravite)),
        UI.champ(Schema.champ('reserves_controle', 'echeance_levee'), dateIso(reserve.echeance_levee), {
          aide: I18n.t('controles.ouvrir_modification_reserve.echeance_aide', { jours: DELAI_LEVEE_PAR_DEFAUT_JOURS }),
          attributs: dateControle ? { min: dateControle } : {} }),
      ],
      libelleValider: I18n.t('commun.bouton.enregistrer'),
      verifier: (valeurs) => verifierModificationReserve(reserveFraiche(reserve.id) || reserve, valeurs),
      async action(valeurs) { changes = await Controles.modifierReserve(reserve.id, valeurs); },
    });
    if (fait) {
      await apresEcriture(changes.length ? I18n.t('controles.ouvrir_modification_reserve.reserve_modifiee')
        : I18n.t('commun.message.aucune_modification'));
    }
    return fait;
  }

  /** Fenêtre « Ajouter une réserve » (une réserve oubliée à la saisie) : date du contrôle (défaut : le dernier),
   *  texte (une ligne par réserve), gravité, échéance. Les réserves déjà enregistrées ne changent pas. Toast
   *  « Réserve ajoutée. » / « 2 réserves ajoutées. ». */
  async function ouvrirAjoutReserve(controleId) {
    const controle = Donnees.trouver('controles_reglementaires', texte(controleId));
    if (!controle) return false;
    const jour = Donnees.aujourdhui();
    let creees = [];
    const fait = await UI.fenetreAction({ classe: 'controles-fenetre controles-fenetre-reserve',
      titre: I18n.t('controles.carte_reserves.ajouter_reserve'),
      introduction: UI.html`<p>${I18n.t('controles.ouvrir_ajout_reserve.introduction')}</p>`,
      champs: [
        UI.champ(Schema.champ('reserves_controle', 'date_controle'), dateIso(controle.derniere_date),
          { obligatoire: true, attributs: { max: jour }, aide: I18n.t('controles.ouvrir_ajout_reserve.date_aide') }),
        UI.champ(Schema.champ('reserves_controle', 'texte'), '', { libelle: I18n.t('controles.ouvrir_ajout_reserve.reserves'),
          aide: I18n.t('controles.ouvrir_ajout_reserve.reserves_aide') }),
        UI.champ(Schema.champ('reserves_controle', 'gravite'), ''),
        UI.champ(Schema.champ('reserves_controle', 'echeance_levee'), '',
          { aide: I18n.t('controles.ouvrir_ajout_reserve.echeance_aide', { jours: DELAI_LEVEE_PAR_DEFAUT_JOURS }) }),
      ],
      libelleValider: I18n.t('commun.bouton.ajouter'),
      verifier: (valeurs) => verifierAjoutReserves(valeurs),
      async action(valeurs) { creees = await Controles.ajouterReserves(controle.id, valeurs); },
    });
    if (fait) {
      await apresEcriture(creees.length ? I18n.t('controles.ouvrir_ajout_reserve.ajoutees', { n: creees.length })
        : I18n.t('commun.message.aucune_modification'));
    }
    return fait;
  }

  // Outils prêtés à la fiche (controles-ecrans.js), cherchés au moment de l'appel ; fenêtres des réserves (T420 et
  // les tests les ouvrent aussi par là).
  Object.assign(Controles.interne, { carteReserves, reservesDuDernierControle, champsReservesRealisation,
    messageRealisation, entreesJournalReserves, ouvrirLeveeReserve, ouvrirModificationReserve, ouvrirAjoutReserve });

  return {};
})());
