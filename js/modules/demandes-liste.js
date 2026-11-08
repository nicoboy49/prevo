'use strict';
// Demandes (4/5) — liste des demandes d'intervention (#/di, ?statut=, ?portee=, ?q=, ?equipement=) :
// filtres, tableau triable, cartes sur téléphone (ARCHITECTURE.md §8 et §14.2 ; brief §9 E3).
// Complète l'objet Demandes.

Object.assign(Demandes, (() => {

  // Constantes, outils et règles de demandes-regles.js.
  const { STATUTS, libelleEquipement } = Demandes;
  const { prioriteDeLaDemande, badgeImpact } = Demandes.interne;

  // ===========================================================================================
  // 6. Liste des demandes (#/di)
  // ===========================================================================================

  function afficherListe(conteneur, parametres) {
    const requete = parametres.requete || new URLSearchParams();
    const profil = App.profil || {};
    const aUnNom = Boolean(profil.nom);
    const filtre = {
      statut: requete.get('statut') || (App.estResponsable() ? 'Nouvelle' : 'tous'),
      portee: requete.get('portee') || (App.estDemandeur() ? 'mes' : 'toutes'),
      recherche: requete.get('q') || '',
      equipement: requete.get('equipement') || '',
    };
    if (filtre.statut !== 'tous' && !STATUTS.includes(filtre.statut)) filtre.statut = 'tous';
    if (!aUnNom) filtre.portee = 'toutes';

    const optionsStatut = [
      { valeur: 'Nouvelle', libelle: I18n.t('demandes.liste.traiter_nouvelles') },
      { valeur: 'Différée', libelle: I18n.t('demandes.liste.differees') },
      { valeur: 'Acceptée', libelle: I18n.t('demandes.liste.acceptees') },
      { valeur: 'Regroupée', libelle: I18n.t('demandes.liste.regroupees') },
      { valeur: 'Refusée', libelle: I18n.t('demandes.liste.refusees') },
      { valeur: 'tous', libelle: I18n.t('demandes.liste.tous_statuts') },
    ];

    UI.remplir(conteneur, UI.html`
      <div class="entete-page">
        <div><h1>${I18n.t('demandes.liste.demandes_intervention')}</h1>
          <p>${App.estResponsable() ? I18n.t('demandes.liste.demandes_traiter_tout_historique') : I18n.t('demandes.liste.suivez_demandes_decision_responsable')}</p></div>
        <div class="actions"><a class="btn btn-primaire" href="#/di/nouvelle">${UI.icone('ajouter')}${I18n.t('demandes.liste.signaler_probleme')}</a></div>
      </div>
      <article class="carte di-liste">
        <div class="filtres" data-hors-saisie>
          <input type="search" name="recherche" aria-label="${I18n.t('demandes.liste.rechercher_demande')}"
            placeholder="${I18n.t('demandes.liste.equipement_symptome_demandeur')}" value="${filtre.recherche}">
          <select name="statut" aria-label="${I18n.t('commun.champ.statut')}">
            ${optionsStatut.map((o) => UI.html`<option value="${o.valeur}" ${o.valeur === filtre.statut ? UI.brut('selected') : ''}>${o.libelle}</option>`)}
          </select>
          ${aUnNom ? UI.html`<select name="portee" aria-label="${I18n.t('demandes.liste.demandes_affichees')}">
            <option value="mes" ${filtre.portee === 'mes' ? UI.brut('selected') : ''}>${I18n.t('demandes.liste.mes_demandes')}</option>
            <option value="toutes" ${filtre.portee === 'toutes' ? UI.brut('selected') : ''}>${I18n.t('demandes.liste.toutes_demandes')}</option>
          </select>` : ''}
        </div>
        <div class="di-filtre-equipement"></div>
        <p class="di-compte" aria-live="polite"></p>
        <div class="di-zone-tableau"></div>
        <ul class="liste-cartes di-cartes"></ul>
      </article>`);

    const zoneFiltres = UI.$('.filtres', conteneur);
    const compte = UI.$('.di-compte', conteneur);
    const listeCartes = UI.$('.di-cartes', conteneur);

    if (filtre.equipement) {
      const puce = UI.element(UI.html`<p class="di-puce-filtre">${I18n.html('demandes.liste.equipement_libelle_equipement', { libelleEquipement: libelleEquipement(filtre.equipement) })}
        <button type="button" class="btn btn-fantome">${UI.icone('fermer')}${I18n.t('demandes.liste.tous_equipements')}</button></p>`);
      UI.$('button', puce).addEventListener('click', () => {
        filtre.equipement = '';
        puce.remove();
        rafraichir();
      });
      UI.$('.di-filtre-equipement', conteneur).appendChild(puce);
    }

    function lignesFiltrees() {
      const mots = UI.normaliserRecherche(filtre.recherche).split(' ').filter(Boolean);
      return Donnees.lignes('demandes').filter((demande) => {
        if (filtre.statut !== 'tous' && demande.statut !== filtre.statut) return false;
        if (filtre.portee === 'mes' && demande.demandeur !== profil.nom) return false;
        if (filtre.equipement && demande.equipement_id !== filtre.equipement) return false;
        if (!mots.length) return true;
        const texteRecherche = UI.normaliserRecherche([demande.id, demande.demandeur, demande.symptome,
          demande.description, demande.impact, demande.statut, demande.motif_decision, demande.ot_origine_id,
          libelleEquipement(demande.equipement_id)].join(' '));
        return mots.every((mot) => texteRecherche.includes(mot));
      });
    }

    const tableau = UI.tableau({
      libelle: I18n.t('demandes.liste.demandes_intervention'),
      colonnes: [
        { cle: 'id', libelle: I18n.t('demandes.colonnes_liste.numero'), rendu: (l) => UI.html`<a href="#/di/${encodeURIComponent(l.id)}">${l.id}</a>` },
        { cle: 'date_heure', libelle: I18n.t('commun.champ.date'), rendu: celluleDate },
        { cle: 'equipement_id', libelle: I18n.t('commun.champ.equipement'), valeurTri: (l) => libelleEquipement(l.equipement_id), rendu: celluleEquipement },
        { cle: 'symptome', libelle: I18n.t('commun.champ.symptome'), classe: 'di-col-symptome', rendu: celluleSymptome },
        { cle: 'impact', libelle: I18n.t('demandes.liste.impact'), rendu: (l) => badgeImpact(l.impact) },
        { cle: 'priorite', libelle: I18n.t('demandes.liste.priorite_calculee'), valeurTri: (l) => prioriteDeLaDemande(l), rendu: (l) => UI.badgePriorite(prioriteDeLaDemande(l)) },
        { cle: 'statut', libelle: I18n.t('commun.champ.statut'), rendu: (l) => UI.badgeValeur('demandes', 'statut', l.statut) },
        { cle: 'motif_decision', libelle: I18n.t('demandes.liste.motif_refus_report'), classe: 'di-col-motif',
          rendu: (l) => (['Refusée', 'Différée'].includes(l.statut) ? celluleTexte(l.motif_decision) : '') },
      ],
      lignes: [],
      triInitial: { cle: 'date_heure', sens: 'desc' },
      surClic: (l) => App.naviguer('#/di/' + encodeURIComponent(l.id)),
      vide: I18n.t('demandes.liste.aucune_demande_correspond_filtres'),
    });
    UI.$('.di-zone-tableau', conteneur).appendChild(tableau);

    // Cellules compactes : le texte complet reste lisible au survol (title) et dans la fiche.
    function celluleDate(l) {
      const morceaux = /^(\S+)\s+(\S+)$/.exec(UI.dateHeureFr(l.date_heure));
      return morceaux ? UI.html`<span class="di-date">${morceaux[1]}<small>${morceaux[2]}</small></span>` : UI.dateHeureFr(l.date_heure);
    }
    function celluleEquipement(l) {
      const equipement = Donnees.trouver('equipements', l.equipement_id);
      if (!equipement) return l.equipement_id;
      return UI.html`<span class="di-eq" title="${libelleEquipement(l.equipement_id)}"><b>${equipement.repere || equipement.id}</b><small>${equipement.designation}</small></span>`;
    }
    function celluleTexte(valeur) {
      return UI.html`<span class="di-coupe" title="${valeur}">${valeur}</span>`;
    }
    // Symptôme, et en petit l'OT préventif pendant lequel l'anomalie a été constatée (lot 2).
    function celluleSymptome(l) {
      return UI.html`${celluleTexte(l.symptome)}${mentionOrigine(l)}`;
    }
    function mentionOrigine(demande) {
      return demande.ot_origine_id
        ? UI.html`<small class="di-origine-liste">${I18n.t('demandes.liste.pendant_ot_preventif', { ot_origine_id: demande.ot_origine_id })}</small>` : '';
    }

    function carte(demande) {
      const priorite = prioriteDeLaDemande(demande);
      const motifVisible = ['Refusée', 'Différée'].includes(demande.statut) && demande.motif_decision;
      return UI.html`<li><a href="#/di/${encodeURIComponent(demande.id)}" class="${priorite === 'P1' || priorite === 'P2' ? 'accent-' + priorite.toLowerCase() : ''}">
        <div class="carte-tete"><b>${demande.id}</b>${UI.badgePriorite(priorite)}${UI.badgeValeur('demandes', 'statut', demande.statut)}</div>
        <div class="carte-titre">${demande.symptome}${mentionOrigine(demande)}</div>
        <div class="carte-meta"><span>${libelleEquipement(demande.equipement_id)}</span><span>${UI.dateHeureFr(demande.date_heure)}</span><span>${Schema.libelleValeur('demandes', 'impact', demande.impact)}</span></div>
        ${motifVisible ? UI.html`<div class="di-motif">${I18n.html('demandes.liste.motif_motif_decision', { motif_decision: demande.motif_decision })}</div>` : ''}
      </a></li>`;
    }

    function rafraichir() {
      const lignes = lignesFiltrees();
      tableau.mettreAJour(lignes);
      const triees = lignes.slice().sort((a, b) => String(b.date_heure).localeCompare(String(a.date_heure)));
      UI.remplir(listeCartes, triees.length ? UI.html`${triees.map(carte)}`
        : UI.html`<li>${UI.vide(I18n.t('demandes.liste.aucune_demande'), I18n.t('demandes.liste.aucune_demande_correspond_filtres'), 'demandes')}</li>`);
      compte.textContent = lignes.length + (lignes.length > 1 ? ' ' + I18n.t('demandes.liste.demandes') : ' ' + I18n.t('demandes.liste.demande'));
    }

    zoneFiltres.addEventListener('input', (evenement) => {
      const champ = evenement.target;
      if (champ.name === 'recherche') filtre.recherche = champ.value;
      else if (champ.name === 'statut') filtre.statut = champ.value;
      else if (champ.name === 'portee') filtre.portee = champ.value;
      rafraichir();
    });
    rafraichir();
  }

  // Écran enregistré par demandes-fiche.js (usage interne au module).
  Object.assign(Demandes.interne, { afficherListe });

  return {};
})());
