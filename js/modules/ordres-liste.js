'use strict';
// Ordres (3/7) — écran E4, liste des ordres de travail (#/ot) : filtres (dont les liens de
// l'accueil ?filtre=retard / ?filtre=p1), tableau triable, cartes sur téléphone (mention
// « anomalie constatée » des préventifs, §14.6) et export CSV de la liste filtrée
// (ARCHITECTURE.md §8, §10 et §14.2). Complète l'objet Ordres.

Object.assign(Ordres, (() => {

  // Constantes, outils et règles de ordres-regles.js.
  const { STATUTS, TYPES, PRIORITES, enRetard, filtrer, nomTechnicien } = Ordres;
  const { memoire, texte, aujourdhui, estResponsable, estTechnicien, monTechnicienId, equipementDe,
    repereEquipement, listeTechniciens } = Ordres.interne;

  // ===========================================================================================
  // 4. Liste des OT (#/ot)
  // ===========================================================================================

  // Choix du filtre « état » de la liste (valeur → libellé).
  const ETATS_LISTE = [
    { valeur: 'ouverts', libelle: 'Ouverts' },
    { valeur: 'retard', libelle: 'En retard' },
    { valeur: 'clotures', libelle: 'Clôturés' },
    { valeur: 'annules', libelle: 'Annulés' },
    { valeur: 'tous', libelle: 'Tous' },
  ];

  function filtresParDefaut() {
    return { etat: 'ouverts', priorite: '', technicien: estTechnicien() ? monTechnicienId() : '', type: '', recherche: '' };
  }

  const CLES_ADRESSE = ['filtre', 'etat', 'statut', 'priorite', 'technicien', 'type', 'recherche', 'equipement'];

  // Paramètres de l'adresse (liens de l'accueil) : ?filtre=retard (OT en retard), ?filtre=p1 (P1
  // ouverts), ?etat=ouverts|retard|clotures|annules|tous, ?priorite=P1, ?technicien=TEC-0002, ?type=…,
  // ?recherche=… (ou ?equipement=EQ-0005). Valeur inconnue ignorée. Avec des paramètres, on repart
  // des filtres par défaut ; sans paramètre, on reprend les filtres mémorisés pendant la session.
  function filtresDepuisAdresse(requete) {
    const profil = App.profil ? App.profil.type + ':' + App.profil.technicienId : '';
    if (memoire.profilFiltres !== profil) { memoire.filtres = null; memoire.profilFiltres = profil; }
    const avecParametres = Boolean(requete) && CLES_ADRESSE.some((cle) => requete.has(cle));
    const filtres = Object.assign(filtresParDefaut(), avecParametres ? {} : (memoire.filtres || {}));
    if (!avecParametres) return filtres;
    const etat = (requete.get('etat') || requete.get('filtre') || requete.get('statut') || '').toLowerCase()
      .replace('en-retard', 'retard').replace('en_retard', 'retard');
    if (ETATS_LISTE.some((e) => e.valeur === etat)) filtres.etat = etat;
    if (etat === 'p1') { filtres.etat = 'ouverts'; filtres.priorite = 'P1'; }   // « P1 ouverts » de l'accueil
    if (PRIORITES.includes((requete.get('priorite') || '').toUpperCase())) filtres.priorite = requete.get('priorite').toUpperCase();
    if (requete.has('technicien')) filtres.technicien = requete.get('technicien');
    if (TYPES.includes(requete.get('type'))) filtres.type = requete.get('type');
    const recherche = requete.get('recherche') || (requete.get('equipement') ? repereEquipement(requete.get('equipement')) : '');
    if (recherche) filtres.recherche = recherche;
    return filtres;
  }

  function optionsHtml(options, valeurChoisie) {
    return UI.html`${options.map((o) => UI.html`<option value="${o.valeur}"${o.valeur === valeurChoisie ? UI.brut(' selected') : ''}>${o.libelle}</option>`)}`;
  }

  function optionsTechnicienFiltre() {
    const options = [{ valeur: '', libelle: 'Tous les techniciens' }, { valeur: '__aucun', libelle: 'Non affectés' }];
    listeTechniciens('').forEach((t) => {
      options.push({ valeur: t.valeur, libelle: t.valeur === monTechnicienId() ? 'Mes OT (' + nomTechnicien(t.valeur) + ')' : nomTechnicien(t.valeur) });
    });
    return options;
  }

  function barreFiltresHtml(filtres) {
    return UI.html`
      <form class="filtres ot-filtres" id="ot-filtres" data-hors-saisie role="search" aria-label="Filtrer les ordres de travail">
        <label class="visuellement-cache" for="ot-filtre-recherche">Rechercher (n°, titre, équipement)</label>
        <input type="search" id="ot-filtre-recherche" name="recherche" value="${filtres.recherche}" placeholder="N°, titre ou équipement" autocomplete="off">
        <label class="visuellement-cache" for="ot-filtre-etat">État</label>
        <select id="ot-filtre-etat" name="etat">${optionsHtml(ETATS_LISTE, filtres.etat)}</select>
        <label class="visuellement-cache" for="ot-filtre-priorite">Priorité</label>
        <select id="ot-filtre-priorite" name="priorite">${optionsHtml([{ valeur: '', libelle: 'Toutes priorités' }].concat(PRIORITES.map((p) => ({ valeur: p, libelle: 'Priorité ' + p }))), filtres.priorite)}</select>
        <label class="visuellement-cache" for="ot-filtre-technicien">Technicien</label>
        <select id="ot-filtre-technicien" name="technicien">${optionsHtml(optionsTechnicienFiltre(), filtres.technicien)}</select>
        <label class="visuellement-cache" for="ot-filtre-type">Type</label>
        <select id="ot-filtre-type" name="type">${optionsHtml([{ valeur: '', libelle: 'Tous types' }].concat(TYPES.map((t) => ({ valeur: t, libelle: t }))), filtres.type)}</select>
      </form>`;
  }

  function badgeRetard(ot) {
    return enRetard(ot) ? UI.html` <span class="badge ko ot-retard">en retard</span>` : '';
  }

  /** Mention « anomalie constatée » (OT préventif pendant lequel une anomalie a été vue, §14.6). */
  function badgeAnomalie(ot) {
    return ot.anomalie_constatee === '1' ? UI.html` <span class="badge attention ot-badge-anomalie">anomalie constatée</span>` : '';
  }

  function origineHtml(ot) {
    if (ot.origine === 'DI' && ot.di_id) return UI.html`DI <a href="#/di/${encodeURIComponent(ot.di_id)}">${ot.di_id}</a>`;
    return ot.origine || '';
  }

  // Origine dans la liste : le n° de DI (lien) ou le mot (préventif, urgence, manuel).
  function origineCourte(ot) {
    if (ot.origine === 'DI' && ot.di_id) return UI.html`<a href="#/di/${encodeURIComponent(ot.di_id)}" title="Demande d'intervention">${ot.di_id}</a>`;
    return ot.origine || '';
  }

  function colonnesListe() {
    return [
      { cle: 'id', libelle: 'N°', rendu: (ot) => UI.html`<a href="#/ot/${encodeURIComponent(ot.id)}">${ot.id}</a>` },
      { cle: 'priorite', libelle: 'Priorité', rendu: (ot) => UI.badgePriorite(ot.priorite) },
      { cle: 'statut', libelle: 'Statut', valeurTri: (ot) => String(STATUTS.indexOf(ot.statut)), rendu: (ot) => UI.badgeStatut(ot.statut) },
      { cle: 'equipement', libelle: 'Équipement', valeurTri: (ot) => repereEquipement(ot.equipement_id),
        rendu: (ot) => UI.html`<b class="sans-coupure">${repereEquipement(ot.equipement_id)}</b>` },
      { cle: 'titre', libelle: 'Titre', classe: 'ot-col-titre', rendu: (ot) => UI.html`${ot.titre}${badgeAnomalie(ot)}` },
      { cle: 'type', libelle: 'Type' },
      { cle: 'technicien', libelle: 'Technicien', valeurTri: (ot) => nomTechnicien(ot.technicien_id), rendu: (ot) => nomTechnicien(ot.technicien_id) },
      { cle: 'date_prevue', libelle: 'Prévu le', classe: 'ot-col-date', rendu: (ot) => UI.html`<span class="sans-coupure">${UI.dateFr(ot.date_prevue)}</span>${badgeRetard(ot)}` },
      { cle: 'origine', libelle: 'Origine', classe: 'ot-col-origine', rendu: origineCourte },
    ];
  }

  function cartesHtml(ordres) {
    if (!ordres.length) return UI.vide('Aucun ordre de travail', 'Aucun OT ne correspond à ces filtres.', 'ordres');
    return UI.html`<ul class="liste-cartes">${ordres.map((ot) => UI.html`
      <li><a href="#/ot/${encodeURIComponent(ot.id)}" class="${ot.priorite === 'P1' || ot.priorite === 'P2' ? 'accent-' + ot.priorite.toLowerCase() : ''}">
        <div class="carte-tete"><b>${ot.id}</b>${UI.badgePriorite(ot.priorite)}${UI.badgeStatut(ot.statut)}${badgeRetard(ot)}${badgeAnomalie(ot)}</div>
        <div class="carte-titre">${ot.titre}</div>
        <div class="carte-meta"><span>${repereEquipement(ot.equipement_id)}</span>
          ${ot.date_prevue ? UI.html`<span>Prévu le ${UI.dateFr(ot.date_prevue)}</span>` : ''}
          <span>${nomTechnicien(ot.technicien_id) || 'Non affecté'}</span><span>${ot.type}</span></div>
      </a></li>`)}</ul>`;
  }

  // Ordre par défaut (cartes du téléphone, et à égalité dans le tableau) : priorité, date prévue, n°.
  function trierParDefaut(ordres) {
    return ordres.slice().sort((a, b) => texte(a.priorite || 'P9').localeCompare(texte(b.priorite || 'P9'))
      || texte(a.date_prevue || '9999').localeCompare(texte(b.date_prevue || '9999')) || a.id.localeCompare(b.id));
  }

  function afficherListe(conteneur, parametres) {
    const filtres = filtresDepuisAdresse(parametres && parametres.requete);
    memoire.filtres = filtres;
    // Les filtres pris dans l'adresse sont mémorisés : l'adresse redevient « #/ot » (un réaffichage
    // ne remettra pas ces filtres par-dessus ceux que l'utilisateur aura changés).
    if (parametres && parametres.requete && String(parametres.requete)) {
      try { history.replaceState(history.state, '', '#/ot'); } catch (erreur) { /* adresse gardée telle quelle */ }
    }
    const tous = Donnees.lignes('ordres_travail');
    UI.remplir(conteneur, UI.html`
      <div class="entete-page">
        <div><h1>Ordres de travail</h1><p>Préparer, planifier, exécuter et clôturer les interventions.</p></div>
        <div class="actions">
          ${estResponsable() ? UI.html`
            <a class="btn btn-danger" id="ot-urgence" href="#/ot/nouveau?urgence=1">${UI.icone('alerte')}OT d'urgence</a>
            <a class="btn btn-primaire" id="ot-nouveau" href="#/ot/nouveau">${UI.icone('ajouter')}Nouvel OT</a>` : ''}
        </div>
      </div>
      ${barreFiltresHtml(filtres)}
      <div class="ot-liste-tete">
        <p class="note" id="ot-compteur" role="status"></p>
        <button type="button" class="btn btn-secondaire" id="ot-export">${UI.icone('export')}Exporter en CSV</button>
      </div>
      <div class="carte ot-liste-tableau"></div>
      <div class="ot-liste-cartes"></div>`);

    let affiches = [];
    const tableau = UI.tableau({
      colonnes: colonnesListe(), lignes: [], libelle: 'Ordres de travail',
      triInitial: { cle: 'priorite', sens: 'asc' }, vide: 'Aucun ordre de travail ne correspond à ces filtres.',
      surClic: (ot) => App.naviguer('#/ot/' + encodeURIComponent(ot.id)),
    });
    UI.$('.ot-liste-tableau', conteneur).appendChild(tableau);

    function rafraichir() {
      affiches = trierParDefaut(filtrer(tous, memoire.filtres));
      tableau.mettreAJour(affiches);
      UI.remplir(UI.$('.ot-liste-cartes', conteneur), cartesHtml(affiches));
      UI.$('#ot-compteur', conteneur).textContent = affiches.length + ' ordre(s) de travail sur ' + tous.length;
    }

    const formulaire = UI.$('#ot-filtres', conteneur);
    const lireFiltres = () => { memoire.filtres = Object.assign({}, memoire.filtres, UI.lireFormulaire(formulaire)); rafraichir(); };
    formulaire.addEventListener('input', lireFiltres);
    formulaire.addEventListener('change', lireFiltres);
    formulaire.addEventListener('submit', (evenement) => evenement.preventDefault());
    UI.$('#ot-export', conteneur).addEventListener('click', () => exporterCsv(affiches));
    rafraichir();
  }

  // --- Export CSV de la liste filtrée (ARCHITECTURE.md §3 : BOM, « ; », CRLF, guillemets, apostrophe) ---

  const COLONNES_EXPORT = [
    { nom: 'id', type: 'id', valeur: (ot) => ot.id },
    { nom: 'priorite', type: 'choix', valeur: (ot) => ot.priorite },
    { nom: 'statut', type: 'choix', valeur: (ot) => ot.statut },
    { nom: 'equipement_id', type: 'ref', valeur: (ot) => ot.equipement_id },
    { nom: 'equipement_repere', type: 'texte', protege: true, valeur: (ot) => repereEquipement(ot.equipement_id) },
    { nom: 'equipement_designation', type: 'texte', valeur: (ot) => (equipementDe(ot) || {}).designation || '' },
    { nom: 'titre', type: 'texte', valeur: (ot) => ot.titre },
    { nom: 'type', type: 'choix', valeur: (ot) => ot.type },
    { nom: 'technicien_id', type: 'ref', valeur: (ot) => ot.technicien_id },
    { nom: 'technicien', type: 'texte', valeur: (ot) => nomTechnicien(ot.technicien_id) },
    { nom: 'date_creation', type: 'date_heure', valeur: (ot) => ot.date_creation },
    { nom: 'date_prevue', type: 'date', valeur: (ot) => ot.date_prevue },
    { nom: 'en_retard', type: 'booleen', valeur: (ot) => (enRetard(ot) ? '1' : '0') },
    { nom: 'origine', type: 'choix', valeur: (ot) => ot.origine },
    { nom: 'di_id', type: 'ref', valeur: (ot) => ot.di_id },
  ];

  function celluleCsv(valeur) {
    return /[;"\r\n]|^[ \t]|[ \t]$/.test(valeur) ? '"' + valeur.replace(/"/g, '""') + '"' : valeur;
  }

  /** Texte CSV (sans BOM) d'une liste d'OT : en-tête puis une ligne par OT, fins de ligne CRLF. */
  function csvListe(ordres) {
    const lignes = [COLONNES_EXPORT.map((c) => c.nom).join(';')];
    ordres.forEach((ot) => {
      lignes.push(COLONNES_EXPORT.map((colonne) => celluleCsv(Donnees.csv.ecrireValeur(colonne, texte(colonne.valeur(ot))))).join(';'));
    });
    return lignes.join('\r\n') + '\r\n';
  }

  function exporterCsv(ordres) {
    const octets = new TextEncoder().encode(csvListe(ordres));
    const contenu = new Uint8Array(octets.length + 3);
    contenu.set([0xEF, 0xBB, 0xBF], 0);
    contenu.set(octets, 3);
    UI.telecharger('ordres-de-travail-' + aujourdhui() + '.csv', new Blob([contenu], { type: 'text/csv;charset=utf-8' }));
    UI.toast(ordres.length + ' ordre(s) de travail exporté(s).', 'succes');
  }

  // Outils prêtés aux fichiers suivants du module (usage interne).
  Object.assign(Ordres.interne, { afficherListe, optionsHtml, badgeRetard, badgeAnomalie, origineHtml });

  return {
    // export (ARCHITECTURE.md §10)
    csvListe,
  };
})());
