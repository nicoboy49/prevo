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
      { valeur: 'Nouvelle', libelle: 'À traiter (nouvelles)' },
      { valeur: 'Différée', libelle: 'Différées' },
      { valeur: 'Acceptée', libelle: 'Acceptées' },
      { valeur: 'Regroupée', libelle: 'Regroupées' },
      { valeur: 'Refusée', libelle: 'Refusées' },
      { valeur: 'tous', libelle: 'Tous les statuts' },
    ];

    UI.remplir(conteneur, UI.html`
      <div class="entete-page">
        <div><h1>Demandes d'intervention</h1>
          <p>${App.estResponsable() ? 'Les demandes à traiter, et tout l\'historique.' : 'Suivez vos demandes et la décision du responsable maintenance.'}</p></div>
        <div class="actions"><a class="btn btn-primaire" href="#/di/nouvelle">${UI.icone('ajouter')}Signaler un problème</a></div>
      </div>
      <article class="carte di-liste">
        <div class="filtres" data-hors-saisie>
          <input type="search" name="recherche" aria-label="Rechercher une demande"
            placeholder="N°, équipement, symptôme, demandeur…" value="${filtre.recherche}">
          <select name="statut" aria-label="Statut">
            ${optionsStatut.map((o) => UI.html`<option value="${o.valeur}" ${o.valeur === filtre.statut ? UI.brut('selected') : ''}>${o.libelle}</option>`)}
          </select>
          ${aUnNom ? UI.html`<select name="portee" aria-label="Demandes affichées">
            <option value="mes" ${filtre.portee === 'mes' ? UI.brut('selected') : ''}>Mes demandes</option>
            <option value="toutes" ${filtre.portee === 'toutes' ? UI.brut('selected') : ''}>Toutes les demandes</option>
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
      const puce = UI.element(UI.html`<p class="di-puce-filtre">Équipement : <b>${libelleEquipement(filtre.equipement)}</b>
        <button type="button" class="btn btn-fantome">${UI.icone('fermer')}Tous les équipements</button></p>`);
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
          demande.description, demande.impact, demande.statut, demande.motif_decision,
          libelleEquipement(demande.equipement_id)].join(' '));
        return mots.every((mot) => texteRecherche.includes(mot));
      });
    }

    const tableau = UI.tableau({
      libelle: 'Demandes d\'intervention',
      colonnes: [
        { cle: 'id', libelle: 'N°', rendu: (l) => UI.html`<a href="#/di/${encodeURIComponent(l.id)}">${l.id}</a>` },
        { cle: 'date_heure', libelle: 'Date', rendu: celluleDate },
        { cle: 'equipement_id', libelle: 'Équipement', valeurTri: (l) => libelleEquipement(l.equipement_id), rendu: celluleEquipement },
        { cle: 'symptome', libelle: 'Symptôme', classe: 'di-col-symptome', rendu: (l) => celluleTexte(l.symptome) },
        { cle: 'impact', libelle: 'Impact', rendu: (l) => badgeImpact(l.impact) },
        { cle: 'priorite', libelle: 'Priorité calculée', valeurTri: (l) => prioriteDeLaDemande(l), rendu: (l) => UI.badgePriorite(prioriteDeLaDemande(l)) },
        { cle: 'statut', libelle: 'Statut', rendu: (l) => UI.badgeStatut(l.statut) },
        { cle: 'motif_decision', libelle: 'Motif (refus, report)', classe: 'di-col-motif',
          rendu: (l) => (['Refusée', 'Différée'].includes(l.statut) ? celluleTexte(l.motif_decision) : '') },
      ],
      lignes: [],
      triInitial: { cle: 'date_heure', sens: 'desc' },
      surClic: (l) => App.naviguer('#/di/' + encodeURIComponent(l.id)),
      vide: 'Aucune demande ne correspond à ces filtres.',
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

    function carte(demande) {
      const priorite = prioriteDeLaDemande(demande);
      const motifVisible = ['Refusée', 'Différée'].includes(demande.statut) && demande.motif_decision;
      return UI.html`<li><a href="#/di/${encodeURIComponent(demande.id)}" class="${priorite === 'P1' || priorite === 'P2' ? 'accent-' + priorite.toLowerCase() : ''}">
        <div class="carte-tete"><b>${demande.id}</b>${UI.badgePriorite(priorite)}${UI.badgeStatut(demande.statut)}</div>
        <div class="carte-titre">${demande.symptome}</div>
        <div class="carte-meta"><span>${libelleEquipement(demande.equipement_id)}</span><span>${UI.dateHeureFr(demande.date_heure)}</span><span>${demande.impact}</span></div>
        ${motifVisible ? UI.html`<div class="di-motif"><b>Motif :</b> ${demande.motif_decision}</div>` : ''}
      </a></li>`;
    }

    function rafraichir() {
      const lignes = lignesFiltrees();
      tableau.mettreAJour(lignes);
      const triees = lignes.slice().sort((a, b) => String(b.date_heure).localeCompare(String(a.date_heure)));
      UI.remplir(listeCartes, triees.length ? UI.html`${triees.map(carte)}`
        : UI.html`<li>${UI.vide('Aucune demande', 'Aucune demande ne correspond à ces filtres.', 'demandes')}</li>`);
      compte.textContent = lignes.length + (lignes.length > 1 ? ' demandes' : ' demande');
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
