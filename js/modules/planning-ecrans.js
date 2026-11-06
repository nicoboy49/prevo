'use strict';
// Planning (3/3) — écran #/planning (ARCHITECTURE.md §15.5 ; brief §9 E6) :
//   1. Petits outils d'affichage (repère, jours, carte d'un OT)
//   2. Grille de la semaine (grand écran) et liste par jour (téléphone), colonne « À planifier »
//   3. Actions : glisser-déposer, bouton « Planifier… » (même résultat sans glisser : WCAG 2.2,
//      critère 2.5.7), refus RG3 avec « Mettre en attente (motif : pièce) », avertissement RG8
//   4. Enregistrement de l'écran
// Profils : le responsable planifie ; le technicien consulte (sa ligne en tête, aucune carte
// déplaçable, aucun bouton) ; le demandeur n'a pas accès. Complète l'objet Planning.

Object.assign(Planning, (() => {

  const { texte, nomComplet, ordreDesNoms } = Planning.interne;
  const STATUTS_DEPLACABLES = ['Préparé', 'Planifié'];
  const CLASSES_PRIORITE = { P1: 'accent-p1', P2: 'accent-p2' };
  // Début du motif de mise en attente pour pièce (D156) : écrit dans les données et relu par le code (RG3,
  // indicateurs) ; jamais traduit, seul le détail qui suit l'est.
  const MARQUEUR_PIECE = 'Pièce : ';
  const TABLES_ECRAN = ['ordres_travail', 'techniciens', 'equipements', 'habilitations', 'ot_pieces', 'mouvements_stock', 'articles'];

  // Message à montrer après le réaffichage qui suit une écriture (avertissement d'habilitation).
  let messageApresReaffichage = null;

  // ===========================================================================================
  // 1. Petits outils d'affichage
  // ===========================================================================================

  function repere(equipementId) {
    const equipement = Donnees.trouver('equipements', equipementId);
    return equipement ? texte(equipement.repere) || equipement.id : texte(equipementId);
  }

  /** Abréviations des jours, lundi d'abord (lues à l'affichage, jamais figées au chargement du module). */
  function nomsJours() {
    return [I18n.t('planning.noms_jours.lun'), I18n.t('planning.noms_jours.mar'), I18n.t('planning.noms_jours.mer'),
      I18n.t('planning.noms_jours.jeu'), I18n.t('planning.noms_jours.ven'), I18n.t('planning.noms_jours.sam'),
      I18n.t('planning.noms_jours.dim')];
  }

  /** '2026-10-19' → « lun. 19/10 » (rang 0 = lundi). */
  function libelleJour(dateIso, rang) {
    return nomsJours()[rang] + ' ' + dateIso.slice(8, 10) + '/' + dateIso.slice(5, 7);
  }

  function peutPlanifier() {
    return App.estResponsable();
  }

  function estDeplacable(ot) {
    return peutPlanifier() && STATUTS_DEPLACABLES.includes(texte(ot.statut));
  }

  /** Lundi demandé par ?semaine= (ramené au lundi), sinon celui de la semaine en cours. */
  function lundiDemande(parametres) {
    const demande = texte(parametres && parametres.requete && parametres.requete.get('semaine'));
    return Planning.lundiDe(/^\d{4}-\d{2}-\d{2}$/.test(demande) ? demande : Donnees.aujourdhui());
  }

  /** Lien vers une autre semaine ; le filtre ?technicien= suit (correction de relecture). */
  function lienSemaine(lundi, decalageSemaines, technicienId) {
    const numero = Planning.interne.numeroJour(lundi) + 7 * decalageSemaines;
    return '#/planning?semaine=' + Planning.interne.dateDepuisNumero(numero)
      + (technicienId ? '&technicien=' + encodeURIComponent(technicienId) : '');
  }

  /** Filtre ?technicien= annoncé, avec le lien qui le retire (la grille ne montre qu'une ligne). */
  function filtreHtml(grille, technicienId) {
    if (!technicienId) return '';
    return UI.html`<p class="note pl-filtre">${I18n.t('planning.filtre.planning_seulement', { nomTechnicien: nomTechnicien(technicienId) })}
      <a href="${'#/planning?semaine=' + grille.lundi}">${I18n.t('planning.filtre.voir_toute_equipe')}</a></p>`;
  }

  /** « 38 h / 35 h » et le badge « surcharge » (texte, pas seulement une couleur). */
  function chargeHtml(ligne) {
    const capacite = ligne.capacite === null ? I18n.t('planning.charge.capacite_non_renseignee') : I18n.t('planning.charge.capacite_h', { capacite: UI.nombreFr(ligne.capacite) });
    return UI.html`<span class="pl-charge">${I18n.t('planning.charge.charge_h_capacite', { charge: UI.nombreFr(ligne.charge), capacite })}</span>${ligne.surcharge
      ? UI.html` <span class="badge ko pl-surcharge">${I18n.t('planning.charge.surcharge')}</span>` : ''}`;
  }

  /** Carte d'un OT : identifiant (lien), priorité, titre, repère, temps prévu, statut, retard. */
  function carteOt(ot, options) {
    const reglages = options || {};
    const deplacable = estDeplacable(ot);
    const enRetard = Accueil.otEnRetard(ot, Donnees.aujourdhui());
    const temps = texte(ot.temps_prevu_h) ? UI.heures(ot.temps_prevu_h) : I18n.t('planning.carte_ot.temps_non_prevu');
    return UI.html`<div class="pl-ot ${CLASSES_PRIORITE[ot.priorite] || ''}${deplacable ? ' pl-deplacable' : ''}"
        data-ot="${ot.id}" data-statut="${ot.statut}" draggable="${deplacable ? 'true' : 'false'}">
      <div class="pl-ot-tete"><a href="#/ot/${encodeURIComponent(ot.id)}">${ot.id}</a>${UI.badgePriorite(ot.priorite)}</div>
      <div class="pl-ot-titre" title="${ot.titre || ''}">${ot.titre || I18n.t('planning.carte_ot.sans_titre')}</div>
      <div class="pl-ot-meta"><span>${repere(ot.equipement_id)}</span><span>${temps}</span>${reglages.avecTechnicien && texte(ot.technicien_id)
        ? UI.html`<span>${nomTechnicien(ot.technicien_id)}</span>` : ''}${reglages.avecDate && texte(ot.date_prevue)
        ? UI.html`<span>${I18n.t('planning.carte_ot.prevu_date_prevue', { date_prevue: UI.dateFr(ot.date_prevue) })}</span>` : ''}</div>
      <div class="pl-ot-badges">${ot.statut !== 'Planifié' ? UI.badgeValeur('ordres_travail', 'statut', ot.statut) : ''}${enRetard
        ? UI.html`<span class="badge ko">${I18n.t('planning.carte_ot.retard')}</span>` : ''}</div>
      ${deplacable ? UI.html`<button type="button" class="btn btn-secondaire pl-planifier" data-action="planifier" data-ot="${ot.id}">${I18n.t('planning.carte_ot.planifier')}</button>` : ''}
    </div>`;
  }

  function nomTechnicien(technicienId) {
    const technicien = Donnees.trouver('techniciens', technicienId);
    return technicien ? nomComplet(technicien) : texte(technicienId);
  }

  // ===========================================================================================
  // 2. Grille de la semaine, liste par jour, colonne « À planifier »
  // ===========================================================================================

  /** Lignes de la grille ; pour le technicien, la sienne en premier. */
  function lignesOrdonnees(grille) {
    if (!App.estTechnicien()) return grille.lignes;
    const moi = texte(App.profil.technicienId);
    return grille.lignes.filter((ligne) => ligne.technicien.id === moi)
      .concat(grille.lignes.filter((ligne) => ligne.technicien.id !== moi));
  }

  function grilleHtml(grille) {
    const aujourdhui = Donnees.aujourdhui();
    const entetes = grille.jours.map((jour, rang) => UI.html`<th scope="col" class="${rang >= 5 ? 'pl-week-end' : ''}${jour === aujourdhui ? ' pl-aujourdhui' : ''}">${libelleJour(jour, rang)}</th>`);
    const lignes = lignesOrdonnees(grille).map((ligne) => {
      const depot = peutPlanifier() && !ligne.inactif;
      const cases = grille.jours.map((jour, rang) => UI.html`<td class="pl-case${rang >= 5 ? ' pl-week-end' : ''}"
          data-technicien="${ligne.technicien.id}" data-date="${jour}"${depot ? UI.brut(' data-depot="1"') : ''}>
        ${ligne.cases[jour].map((ot) => carteOt(ot))}</td>`);
      const moi = App.estTechnicien() && ligne.technicien.id === texte(App.profil.technicienId);
      return UI.html`<tr class="${ligne.inactif ? 'pl-inactif' : ''}${moi ? ' pl-moi' : ''}" data-technicien="${ligne.technicien.id}">
        <th scope="row"><b>${nomComplet(ligne.technicien)}</b>${ligne.inactif ? UI.html` <span class="badge neutre">${I18n.t('planning.grille.inactif')}</span>` : ''}
          <span class="pl-metier">${texte(ligne.technicien.metier)}</span>${chargeHtml(ligne)}</th>${cases}</tr>`;
    });
    return UI.html`<div class="pl-cadre"><table class="pl-grille">
      <caption class="visuellement-cache">${I18n.t('planning.grille.planning_semaine_technicien', { debut: UI.dateFr(grille.jours[0]), fin: UI.dateFr(grille.jours[6]) })}</caption>
      <thead><tr><th scope="col">${I18n.t('planning.grille.technicien')}</th>${entetes}</tr></thead>
      <tbody>${lignes.length ? lignes : UI.html`<tr><td colspan="8">${UI.vide(I18n.t('planning.grille.aucun_technicien_actif'), I18n.t('planning.grille.ajoutez_techniciens_ecran_equipe'), 'equipe')}</td></tr>`}</tbody>
    </table></div>`;
  }

  /** Téléphone : une liste par jour (le nom du technicien est sur chaque carte). */
  function listeParJourHtml(grille) {
    const parJour = grille.jours.map((jour) => grille.lignes.flatMap((ligne) => ligne.cases[jour]));
    return UI.html`<div class="pl-jours">${grille.jours.map((jour, rang) => UI.html`
      <section class="carte pl-jour${rang >= 5 ? ' pl-week-end' : ''}">
        <h2>${libelleJour(jour, rang)}</h2>
        ${parJour[rang].length ? UI.html`<div class="pl-liste">${parJour[rang].map((ot) => carteOt(ot, { avecTechnicien: true }))}</div>`
          : UI.html`<p class="muted">${I18n.t('planning.liste_par_jour.rien_prevu')}</p>`}
      </section>`)}</div>
      <section class="carte pl-charges-telephone"><h2>${I18n.t('planning.liste_par_jour.charge_semaine')}</h2>
        <ul>${grille.lignes.map((ligne) => UI.html`<li><b>${nomComplet(ligne.technicien)}</b> ${chargeHtml(ligne)}</li>`)}</ul>
      </section>`;
  }

  function aPlanifierHtml(grille) {
    return UI.html`<aside class="carte pl-a-planifier" aria-labelledby="pl-titre-a-planifier">
      <div class="entete-carte"><h2 id="pl-titre-a-planifier">${I18n.t('planning.a_planifier.planifier')}</h2><span class="badge ${grille.aPlanifier.length ? 'info' : 'neutre'}">${grille.aPlanifier.length}</span></div>
      <p class="note">${I18n.t('planning.a_planifier.ot_prepare_sont_pas')}${peutPlanifier()
        ? ' ' + I18n.t('planning.a_planifier.glissez_carte_technicien_jour') : ''}</p>
      ${grille.aPlanifier.length ? UI.html`<div class="pl-liste">${grille.aPlanifier.map((ot) => carteOt(ot, { avecTechnicien: true, avecDate: true }))}</div>`
        : UI.vide(I18n.t('planning.a_planifier.rien_planifier'), I18n.t('planning.a_planifier.ot_prepares_apparaitront_ici'), 'planning')}
    </aside>`;
  }

  function afficher(conteneur, parametres) {
    const grille = Planning.semaine(lundiDemande(parametres));
    // ?technicien=TEC-… (§15.5) : la grille ne montre que ce technicien.
    const technicienDemande = texte(parametres && parametres.requete && parametres.requete.get('technicien'));
    if (technicienDemande) grille.lignes = grille.lignes.filter((ligne) => ligne.technicien.id === technicienDemande);
    const telephone = UI.estTelephone();
    // Une racine propre à cet affichage : ses écouteurs disparaissent avec elle au réaffichage
    // (#contenu, lui, reste le même d'un écran à l'autre).
    UI.remplir(conteneur, UI.html`<div class="pl-ecran" data-lundi="${grille.lundi}">
      <div class="entete-page pl-entete"><div>
        <h1>${I18n.t('planning.ecran.titre')}</h1>
        <p>${I18n.t('planning.ecran.semaine_du_au', { debut: UI.dateFr(grille.jours[0]), fin: UI.dateFr(grille.jours[6]) })}${App.estTechnicien() ? ' ' + I18n.t('planning.ecran.consultation_responsable_planifie') : ''}</p>
      </div>
      <nav class="actions pl-navigation" aria-label="${I18n.t('planning.ecran.changer_semaine')}">
        <a class="btn btn-secondaire" href="${lienSemaine(grille.lundi, -1, technicienDemande)}">${I18n.t('planning.ecran.semaine_precedente')}</a>
        <a class="btn btn-fantome" href="${'#/planning' + (technicienDemande ? '?technicien=' + encodeURIComponent(technicienDemande) : '')}">${I18n.t('planning.ecran.semaine')}</a>
        <a class="btn btn-secondaire" href="${lienSemaine(grille.lundi, 1, technicienDemande)}">${I18n.t('planning.ecran.semaine_suivante')}</a>
      </nav></div>
      ${filtreHtml(grille, technicienDemande)}
      <div id="pl-message"></div>
      <div class="pl-disposition">
        <div class="pl-principal">${telephone ? listeParJourHtml(grille) : grilleHtml(grille)}</div>
        ${aPlanifierHtml(grille)}
      </div></div>`);
    const racine = conteneur.querySelector('.pl-ecran');
    if (messageApresReaffichage) {
      afficherMessage(racine, messageApresReaffichage.type, messageApresReaffichage.contenu);
      messageApresReaffichage = null;
    }
    if (peutPlanifier()) brancherActions(racine);
  }

  // ===========================================================================================
  // 3. Actions
  // ===========================================================================================

  function afficherMessage(conteneur, type, contenu) {
    const zone = conteneur.querySelector('#pl-message');
    if (!zone) return null;
    const bloc = UI.bandeau(type, contenu);
    UI.remplir(zone, bloc);
    zone.scrollIntoView({ block: 'nearest' });
    return bloc;
  }

  /** Écrit la planification puis réaffiche ; un refus est expliqué dans le bandeau de l'écran. */
  async function placer(conteneur, otId, statutAttendu, technicienId, date) {
    let resultat;
    try {
      resultat = await Planning.planifier(otId, statutAttendu, technicienId, date);
    } catch (erreur) {
      if (erreur instanceof Donnees.ErreurValidation) afficherRefus(conteneur, otId, erreur);
      else App.signalerErreur(erreur, 'planification de ' + otId);
      return;
    }
    const succes = statutAttendu === 'Préparé'
      ? I18n.t('planning.placer.succes_planifie', { otId, date: UI.dateFr(date), nomTechnicien: nomTechnicien(technicienId) })
      : I18n.t('planning.placer.succes_replanifie', { otId, date: UI.dateFr(date), nomTechnicien: nomTechnicien(technicienId) });
    if (resultat.avertissements.length) {
      messageApresReaffichage = { type: 'attention', contenu: UI.html`<b>${succes}</b> ${resultat.avertissements.join(' ')}` };
      UI.toast(resultat.avertissements.join(' '), 'attention');
    } else {
      UI.toast(succes, 'succes');
    }
    App.marquerSaisie(false);
    await App.reafficher();
  }

  /** Refus (RG3, statut changé, technicien inactif…) ; pièce manquante → « Mettre en attente ». */
  function afficherRefus(conteneur, otId, erreur) {
    const manquantes = erreur.piecesManquantes || [];
    const bloc = afficherMessage(conteneur, 'important', UI.html`${I18n.html('planning.refus.pas_ete_planifie', { otId, erreurMessage: erreur.message })}`);
    if (!bloc || !manquantes.length) return;
    const actions = UI.element(UI.html`<div class="actions">
      <button type="button" class="btn btn-secondaire" data-action="attente-piece">${I18n.t('planning.refus.mettre_attente_motif_piece')}</button></div>`);
    actions.querySelector('button').addEventListener('click', () => mettreEnAttentePiece(otId));
    bloc.querySelector('.alerte-texte').appendChild(actions);
  }

  /** Détail d'une pièce manquante dans le motif proposé : « Joint (2 prévu(s), 0 en stock) ». */
  function detailPiece(piece) {
    return piece.sorti > 0
      ? I18n.t('planning.detail_piece.prevu_deja_sorti_ot', { pieceLibelle: piece.libelle, prevu: UI.nombreFr(piece.prevu), sorti: UI.nombreFr(piece.sorti), stock: UI.nombreFr(piece.stock) })
      : I18n.t('planning.detail_piece.prevu_stock', { n: piece.prevu, pieceLibelle: piece.libelle, prevu: UI.nombreFr(piece.prevu), stock: UI.nombreFr(piece.stock) });
  }

  /** Même comportement que la fiche OT : motif « Pièce : … » prérempli, modifiable. */
  async function mettreEnAttentePiece(otId) {
    const ot = Donnees.trouver('ordres_travail', otId);
    if (!ot) return;
    const manquantes = Ordres.piecesManquantes(otId);
    const proposition = MARQUEUR_PIECE + I18n.enLangueDesDonnees(() => (manquantes.length ? manquantes.map(detailPiece).join(' ; ')
      : I18n.donnees('planning.mettre_en_attente_piece.stock_insuffisant'))) + '.';      // motif pré-rempli (D156)
    const motif = await UI.demanderMotif(I18n.t('planning.mettre_en_attente_piece.mettre_attente', { otId }), I18n.t('planning.mettre_en_attente_piece.motif_mise_attente'), { valeur: proposition });
    if (motif === null) return;
    try {
      await Ordres.changerStatut(otId, ot.statut, 'En attente', { motif_attente: motif });
    } catch (erreur) {
      App.signalerErreur(erreur, 'mise en attente de ' + otId);
      return;
    }
    UI.toast(I18n.t('planning.mettre_en_attente_piece.ot_id_attente', { otId }), 'succes');
    await App.reafficher();
  }

  /** Fenêtre « Planifier… » : technicien actif et date prévue, sans glisser. */
  async function ouvrirFenetre(conteneur, otId) {
    const ot = Donnees.trouver('ordres_travail', otId);
    if (!ot) return;
    const actifs = Donnees.lignes('techniciens').filter((technicien) => texte(technicien.actif) !== '0')
      .sort(ordreDesNoms);
    // Date proposée : la date prévue de l'OT, sinon le lundi de la semaine affichée.
    const datePrevue = texte(ot.date_prevue).slice(0, 10);
    const dateProposee = /^\d{4}-\d{2}-\d{2}$/.test(datePrevue) ? datePrevue : (texte(conteneur.dataset.lundi) || Donnees.aujourdhui());
    const contenu = UI.element(UI.html`<div class="pl-fenetre">
      <p>${ot.id} — ${ot.titre || I18n.t('planning.carte_ot.sans_titre')} · ${repere(ot.equipement_id)}</p>
      <div class="champ"><label class="libelle" for="pl-technicien">${I18n.t('planning.grille.technicien')} <span class="requis" aria-hidden="true">*</span></label>
        <select id="pl-technicien" name="technicien" required>
          <option value="">${I18n.t('planning.ouvrir_fenetre.choisir')}</option>
          ${actifs.map((technicien) => UI.html`<option value="${technicien.id}"${technicien.id === texte(ot.technicien_id) ? UI.brut(' selected') : ''}>${nomComplet(technicien)} — ${texte(technicien.metier)}</option>`)}
        </select></div>
      <div class="champ"><label class="libelle" for="pl-date">${I18n.t('planning.ouvrir_fenetre.date_prevue')} <span class="requis" aria-hidden="true">*</span></label>
        <input id="pl-date" name="date" type="date" required value="${dateProposee}"></div>
      <p class="erreur-champ" role="alert" hidden></p>
    </div>`);
    const choix = await UI.fenetre({
      titre: I18n.t('planning.ouvrir_fenetre.planifier_ot_id', { otId: ot.id }), contenu,
      boutons: [{ libelle: I18n.t('planning.ouvrir_fenetre.annuler'), valeur: null, classe: 'btn-fantome' },
        { libelle: I18n.t('planning.ouvrir_fenetre.planifier'), valeur: 'planifier', classe: 'btn-primaire', defaut: true }],
      avantFermeture() {
        const manque = !contenu.querySelector('#pl-technicien').value ? I18n.t('planning.ouvrir_fenetre.choisissez_technicien')
          : (!contenu.querySelector('#pl-date').value ? I18n.t('planning.ouvrir_fenetre.choisissez_date_prevue') : '');
        const zone = contenu.querySelector('.erreur-champ');
        zone.textContent = manque;
        zone.hidden = !manque;
        return !manque;
      },
    });
    if (choix !== 'planifier') return;
    await placer(conteneur, ot.id, ot.statut, contenu.querySelector('#pl-technicien').value, contenu.querySelector('#pl-date').value);
  }

  /** Glisser-déposer (HTML5) et boutons « Planifier… » — responsable seulement. */
  function brancherActions(conteneur) {
    conteneur.addEventListener('dragstart', (evenement) => {
      const carte = evenement.target.closest && evenement.target.closest('.pl-ot[draggable="true"]');
      if (!carte) return;
      evenement.dataTransfer.setData('text/plain', carte.dataset.ot);
      evenement.dataTransfer.effectAllowed = 'move';
      carte.classList.add('pl-en-cours');
    });
    conteneur.addEventListener('dragend', (evenement) => {
      const carte = evenement.target.closest && evenement.target.closest('.pl-ot');
      if (carte) carte.classList.remove('pl-en-cours');
    });
    conteneur.addEventListener('dragover', (evenement) => {
      const cible = evenement.target.closest && evenement.target.closest('.pl-case[data-depot]');
      if (!cible) return;
      evenement.preventDefault();
      evenement.dataTransfer.dropEffect = 'move';
      cible.classList.add('pl-survol');
    });
    conteneur.addEventListener('dragleave', (evenement) => {
      const cible = evenement.target.closest && evenement.target.closest('.pl-case');
      if (cible && !cible.contains(evenement.relatedTarget)) cible.classList.remove('pl-survol');
    });
    conteneur.addEventListener('drop', (evenement) => {
      const cible = evenement.target.closest && evenement.target.closest('.pl-case[data-depot]');
      if (!cible) return;
      evenement.preventDefault();
      cible.classList.remove('pl-survol');
      const otId = evenement.dataTransfer.getData('text/plain');
      const carte = otId && conteneur.querySelector('.pl-ot[data-ot="' + CSS.escape(otId) + '"]');
      if (!carte) return;
      placer(conteneur, otId, carte.dataset.statut, cible.dataset.technicien, cible.dataset.date);
    });
    conteneur.addEventListener('click', (evenement) => {
      const bouton = evenement.target.closest && evenement.target.closest('[data-action="planifier"]');
      if (bouton) ouvrirFenetre(conteneur, bouton.dataset.ot);
    });
  }

  // ===========================================================================================
  // 4. Enregistrement de l'écran
  // ===========================================================================================

  // App est chargé après les modules : l'écran est enregistré une fois la page lue (§8).
  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'planning', route: /^#\/planning$/,
      get titre() { return I18n.t('planning.ecran.titre'); },
      menu: { get libelle() { return I18n.t('planning.menu.libelle'); }, icone: 'planning', ordre: 33 },
      profils: ['technicien', 'responsable'], tables: TABLES_ECRAN,
      afficher,
    });
  });

  return {};
})());
