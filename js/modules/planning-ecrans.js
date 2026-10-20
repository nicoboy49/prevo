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

  const { texte, nomComplet } = Planning.interne;
  const NOMS_JOURS = ['lun.', 'mar.', 'mer.', 'jeu.', 'ven.', 'sam.', 'dim.'];
  const STATUTS_DEPLACABLES = ['Préparé', 'Planifié'];
  const CLASSES_PRIORITE = { P1: 'accent-p1', P2: 'accent-p2' };
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

  /** '2026-10-19' → « lun. 19/10 » (rang 0 = lundi). */
  function libelleJour(dateIso, rang) {
    return NOMS_JOURS[rang] + ' ' + dateIso.slice(8, 10) + '/' + dateIso.slice(5, 7);
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

  function lienSemaine(lundi, decalageSemaines) {
    const numero = Planning.interne.numeroJour(lundi) + 7 * decalageSemaines;
    return '#/planning?semaine=' + Planning.interne.dateDepuisNumero(numero);
  }

  /** « 38 h / 35 h » et le badge « surcharge » (texte, pas seulement une couleur). */
  function chargeHtml(ligne) {
    const capacite = ligne.capacite === null ? 'capacité non renseignée' : UI.nombreFr(ligne.capacite) + ' h';
    return UI.html`<span class="pl-charge">${UI.nombreFr(ligne.charge)} h / ${capacite}</span>${ligne.surcharge
      ? UI.html` <span class="badge ko pl-surcharge">surcharge</span>` : ''}`;
  }

  /** Carte d'un OT : identifiant (lien), priorité, titre, repère, temps prévu, statut, retard. */
  function carteOt(ot, options) {
    const reglages = options || {};
    const deplacable = estDeplacable(ot);
    const enRetard = Accueil.otEnRetard(ot, Donnees.aujourdhui());
    const temps = texte(ot.temps_prevu_h) ? UI.heures(ot.temps_prevu_h) : 'temps non prévu';
    return UI.html`<div class="pl-ot ${CLASSES_PRIORITE[ot.priorite] || ''}${deplacable ? ' pl-deplacable' : ''}"
        data-ot="${ot.id}" data-statut="${ot.statut}" draggable="${deplacable ? 'true' : 'false'}">
      <div class="pl-ot-tete"><a href="#/ot/${encodeURIComponent(ot.id)}">${ot.id}</a>${UI.badgePriorite(ot.priorite)}</div>
      <div class="pl-ot-titre">${ot.titre || '(sans titre)'}</div>
      <div class="pl-ot-meta"><span>${repere(ot.equipement_id)}</span><span>${temps}</span>${reglages.avecTechnicien && texte(ot.technicien_id)
        ? UI.html`<span>${nomTechnicien(ot.technicien_id)}</span>` : ''}${reglages.avecDate && texte(ot.date_prevue)
        ? UI.html`<span>prévu le ${UI.dateFr(ot.date_prevue)}</span>` : ''}</div>
      <div class="pl-ot-badges">${ot.statut !== 'Planifié' ? UI.badgeStatut(ot.statut) : ''}${enRetard
        ? UI.html`<span class="badge ko">en retard</span>` : ''}</div>
      ${deplacable ? UI.html`<button type="button" class="btn btn-secondaire pl-planifier" data-action="planifier" data-ot="${ot.id}">Planifier…</button>` : ''}
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
        <th scope="row"><b>${nomComplet(ligne.technicien)}</b>${ligne.inactif ? UI.html` <span class="badge neutre">inactif</span>` : ''}
          <span class="pl-metier">${texte(ligne.technicien.metier)}</span>${chargeHtml(ligne)}</th>${cases}</tr>`;
    });
    return UI.html`<div class="pl-cadre"><table class="pl-grille">
      <caption class="visuellement-cache">Planning de la semaine du ${UI.dateFr(grille.jours[0])} au ${UI.dateFr(grille.jours[6])}, par technicien</caption>
      <thead><tr><th scope="col">Technicien</th>${entetes}</tr></thead>
      <tbody>${lignes.length ? lignes : UI.html`<tr><td colspan="8">${UI.vide('Aucun technicien actif', 'Ajoutez des techniciens dans l\'écran Équipe.', 'equipe')}</td></tr>`}</tbody>
    </table></div>`;
  }

  /** Téléphone : une liste par jour (le nom du technicien est sur chaque carte). */
  function listeParJourHtml(grille) {
    const parJour = grille.jours.map((jour) => grille.lignes.flatMap((ligne) => ligne.cases[jour]));
    return UI.html`<div class="pl-jours">${grille.jours.map((jour, rang) => UI.html`
      <section class="carte pl-jour${rang >= 5 ? ' pl-week-end' : ''}">
        <h2>${libelleJour(jour, rang)}</h2>
        ${parJour[rang].length ? UI.html`<div class="pl-liste">${parJour[rang].map((ot) => carteOt(ot, { avecTechnicien: true }))}</div>`
          : UI.html`<p class="muted">Rien de prévu.</p>`}
      </section>`)}</div>
      <section class="carte pl-charges-telephone"><h2>Charge de la semaine</h2>
        <ul>${grille.lignes.map((ligne) => UI.html`<li><b>${nomComplet(ligne.technicien)}</b> ${chargeHtml(ligne)}</li>`)}</ul>
      </section>`;
  }

  function aPlanifierHtml(grille) {
    return UI.html`<aside class="carte pl-a-planifier" aria-labelledby="pl-titre-a-planifier">
      <div class="entete-carte"><h2 id="pl-titre-a-planifier">À planifier</h2><span class="badge ${grille.aPlanifier.length ? 'info' : 'neutre'}">${grille.aPlanifier.length}</span></div>
      <p class="note">OT « Préparé » qui ne sont pas dans la grille de cette semaine, les plus prioritaires d'abord.${peutPlanifier()
        ? ' Glissez une carte sur un technicien et un jour, ou utilisez « Planifier… ».' : ''}</p>
      ${grille.aPlanifier.length ? UI.html`<div class="pl-liste">${grille.aPlanifier.map((ot) => carteOt(ot, { avecTechnicien: true, avecDate: true }))}</div>`
        : UI.vide('Rien à planifier', 'Les OT préparés apparaîtront ici.', 'planning')}
    </aside>`;
  }

  function afficher(conteneur, parametres) {
    const grille = Planning.semaine(lundiDemande(parametres));
    const telephone = UI.estTelephone();
    // Une racine propre à cet affichage : ses écouteurs disparaissent avec elle au réaffichage
    // (#contenu, lui, reste le même d'un écran à l'autre).
    UI.remplir(conteneur, UI.html`<div class="pl-ecran" data-lundi="${grille.lundi}">
      <div class="entete-page pl-entete"><div>
        <h1>Planning</h1>
        <p>Semaine du ${UI.dateFr(grille.jours[0])} au ${UI.dateFr(grille.jours[6])}.${App.estTechnicien() ? ' Consultation : le responsable planifie.' : ''}</p>
      </div>
      <nav class="actions pl-navigation" aria-label="Changer de semaine">
        <a class="btn btn-secondaire" href="${lienSemaine(grille.lundi, -1)}">‹ Semaine précédente</a>
        <a class="btn btn-fantome" href="#/planning">Cette semaine</a>
        <a class="btn btn-secondaire" href="${lienSemaine(grille.lundi, 1)}">Semaine suivante ›</a>
      </nav></div>
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
    const verbe = statutAttendu === 'Préparé' ? 'planifié' : 'replanifié';
    const succes = otId + ' ' + verbe + ' le ' + UI.dateFr(date) + ' pour ' + nomTechnicien(technicienId) + '.';
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
    const bloc = afficherMessage(conteneur, 'important', UI.html`<b>${otId} n'a pas été planifié.</b> ${erreur.message}`);
    if (!bloc || !manquantes.length) return;
    const actions = UI.element(UI.html`<div class="actions">
      <button type="button" class="btn btn-secondaire" data-action="attente-piece">Mettre en attente (motif : pièce)</button></div>`);
    actions.querySelector('button').addEventListener('click', () => mettreEnAttentePiece(otId));
    bloc.querySelector('.alerte-texte').appendChild(actions);
  }

  /** Même comportement que la fiche OT : motif « Pièce : … » prérempli, modifiable. */
  async function mettreEnAttentePiece(otId) {
    const ot = Donnees.trouver('ordres_travail', otId);
    if (!ot) return;
    const manquantes = Ordres.piecesManquantes(otId);
    const proposition = 'Pièce : ' + (manquantes.length
      ? manquantes.map((piece) => piece.libelle + ' (' + UI.nombreFr(piece.prevu) + ' prévu(s), ' + UI.nombreFr(piece.stock) + ' en stock)').join(' ; ')
      : 'stock insuffisant') + '.';
    const motif = await UI.demanderMotif('Mettre en attente ' + otId, 'Motif de mise en attente', { valeur: proposition });
    if (motif === null) return;
    try {
      await Ordres.changerStatut(otId, ot.statut, 'En attente', { motif_attente: motif });
    } catch (erreur) {
      App.signalerErreur(erreur, 'mise en attente de ' + otId);
      return;
    }
    UI.toast(otId + ' : En attente.', 'succes');
    await App.reafficher();
  }

  /** Fenêtre « Planifier… » : technicien actif et date prévue, sans glisser. */
  async function ouvrirFenetre(conteneur, otId) {
    const ot = Donnees.trouver('ordres_travail', otId);
    if (!ot) return;
    const actifs = Donnees.lignes('techniciens').filter((technicien) => texte(technicien.actif) !== '0')
      .sort((a, b) => nomComplet(a).localeCompare(nomComplet(b), 'fr'));
    // Date proposée : la date prévue de l'OT, sinon le lundi de la semaine affichée.
    const datePrevue = texte(ot.date_prevue).slice(0, 10);
    const dateProposee = /^\d{4}-\d{2}-\d{2}$/.test(datePrevue) ? datePrevue : (texte(conteneur.dataset.lundi) || Donnees.aujourdhui());
    const contenu = UI.element(UI.html`<div class="pl-fenetre">
      <p>${ot.id} — ${ot.titre || '(sans titre)'} · ${repere(ot.equipement_id)}</p>
      <div class="champ"><label class="libelle" for="pl-technicien">Technicien <span class="requis" aria-hidden="true">*</span></label>
        <select id="pl-technicien" name="technicien" required>
          <option value="">Choisir…</option>
          ${actifs.map((technicien) => UI.html`<option value="${technicien.id}"${technicien.id === texte(ot.technicien_id) ? UI.brut(' selected') : ''}>${nomComplet(technicien)} — ${texte(technicien.metier)}</option>`)}
        </select></div>
      <div class="champ"><label class="libelle" for="pl-date">Date prévue <span class="requis" aria-hidden="true">*</span></label>
        <input id="pl-date" name="date" type="date" required value="${dateProposee}"></div>
      <p class="erreur-champ" role="alert" hidden></p>
    </div>`);
    const choix = await UI.fenetre({
      titre: 'Planifier ' + ot.id, contenu,
      boutons: [{ libelle: 'Annuler', valeur: null, classe: 'btn-fantome' },
        { libelle: 'Planifier', valeur: 'planifier', classe: 'btn-primaire', defaut: true }],
      avantFermeture() {
        const manque = !contenu.querySelector('#pl-technicien').value ? 'Choisissez le technicien.'
          : (!contenu.querySelector('#pl-date').value ? 'Choisissez la date prévue.' : '');
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
      id: 'planning', route: /^#\/planning$/, titre: 'Planning',
      menu: { libelle: 'Planning', icone: 'planning', ordre: 33 },
      profils: ['technicien', 'responsable'], tables: TABLES_ECRAN,
      afficher,
    });
  });

  return {};
})());
