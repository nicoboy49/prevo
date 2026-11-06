'use strict';
// Preventif (3/4) — écrans du préventif (ARCHITECTURE.md §14.3, brief §9 E8) :
//    9. Petits outils d'affichage (équipement, périodicité, badge d'état)
//   10. Liste des gammes (#/preventif?onglet=gammes|calendrier) : filtres statut et équipement,
//       tableau (cartes sur téléphone) ; responsable : « Nouvelle gamme », « Générer les OT échus »
//   11. Formulaire d'une gamme (#/preventif/gamme/nouvelle, et sur la fiche pour le responsable)
//   12. Fiche d'une gamme (#/preventif/gamme/<id>) : état, paramètres, check-list, OT de la gamme
//   13. Éditeur de check-list : ajout, ordre ↑/↓, modification, suppression (journalisée, D26)
//   14. Enregistrement des écrans
// Profils : le technicien consulte (lecture seule), le responsable crée et modifie, le demandeur
// n'a pas accès. L'onglet « Calendrier » est dessiné par preventif-calendrier.js (chargé après ce
// fichier : appelé par une fonction relais). Lot 3 bis (§16.6) : onglets « Suggestions » et
// « Décisions », rappel ?suggestion=, encart de la fiche et marquage « traitée » viennent de
// suggestions-ecrans.js (chargé après : appels Suggestions.* au moment de l'affichage). Complète
// l'objet Preventif.

Object.assign(Preventif, (() => {

  // Constantes, règles et outils de preventif-regles.js et preventif-ecritures.js.
  const { DECLENCHEURS, STATUTS_GAMME } = Preventif;
  const { texte, contexteCalcul, evaluerGamme, nombreDeSemaines, operationsDeGamme } = Preventif.interne;

  const ONGLETS = ['gammes', 'calendrier'];
  const TONS_ETAT = { echue: 'ko', ot_ouvert: 'cyan', bientot: 'attention', a_jour: 'ok', incomplete: 'violet', inactive: 'neutre' };
  const RANGS_ETAT = Object.keys(STATUTS_GAMME);            // du plus urgent au moins urgent
  const LIBELLES_COURTS = { get date() { return I18n.t('preventif.libelles_courts.date'); }, get compteur() { return I18n.t('preventif.compteur.compteur'); }, get seuil() { return I18n.t('preventif.seuil.seuil'); } };
  const TABLES_ECRANS = ['gammes', 'gamme_operations', 'ordres_travail', 'releves', 'compteurs', 'equipements'];
  // Onglets « Suggestions » et « Décisions » du responsable : ils dépendent en plus du journal (décisions
  // prises sur un autre poste), des DI et des codes de défaillance (lot 4, §17.9).
  const TABLES_SUGGESTIONS = ['journal', 'demandes', 'codes_defaillance'];

  // Filtres de la liste, gardés pendant la session (comme ceux de la liste des OT).
  const memoire = { statut: '', equipement: '' };

  // ===========================================================================================
  // 9. Petits outils d'affichage
  // ===========================================================================================

  function comparerTextes(a, b) {
    return String(a).localeCompare(String(b), 'fr', { numeric: true, sensitivity: 'base' });
  }

  function repere(equipementId) {
    const equipement = Donnees.trouver('equipements', equipementId);
    return equipement ? (equipement.repere || equipement.id) : texte(equipementId);
  }

  function libelleEquipement(equipementId) {
    const equipement = Donnees.trouver('equipements', equipementId);
    return equipement ? repere(equipementId) + ' — ' + texte(equipement.designation) : texte(equipementId);
  }

  function uniteCompteur(gamme) {
    const compteur = Donnees.trouver('compteurs', gamme.compteur_id);
    return compteur ? texte(compteur.unite) : '';
  }

  /** « 2 000 h » : nombre à la française et unité, jamais coupés l'un de l'autre (espace insécable). */
  function avecUnite(valeur, unite) {
    return UI.nombreFr(valeur) + (unite ? '\u00a0' + unite : '');
  }

  /** « tous les 30 j », « toutes les 2 000 h », « seuil 0,8 bar » (vide si non renseignée). */
  function periodicite(gamme) {
    const declencheur = texte(gamme.declencheur) || 'date';
    if (declencheur === 'date') return gamme.periodicite_jours ? I18n.t('preventif.periodicite.tous_periodicite_jours', { n: UI.nombreFr(gamme.periodicite_jours) }) : '';
    if (declencheur === 'compteur') return gamme.periodicite_unites ? I18n.t('preventif.periodicite.toutes_avec_unite', { avecUnite: avecUnite(gamme.periodicite_unites, uniteCompteur(gamme)) }) : '';
    return texte(gamme.seuil) ? I18n.t('preventif.periodicite.seuil_avec_unite', { avecUnite: avecUnite(gamme.seuil, uniteCompteur(gamme)) }) : '';
  }

  /** Badge du statut calculé (texte toujours affiché ; la couleur aide seulement). */
  function badgeEtat(etat) {
    return UI.badgeStatut(STATUTS_GAMME[etat.statut] || etat.statut, TONS_ETAT[etat.statut]);
  }

  function lienOt(otId) {
    return otId ? UI.html`<a href="#/ot/${encodeURIComponent(otId)}">${otId}</a>` : '';
  }

  /** Raison de l'état ; pour une gamme qui a un OT ouvert, son numéro devient un lien vers l'OT. */
  function raisonHtml(etat) {
    const id = etat.otOuvertId;
    if (!id || !etat.raison.startsWith(id)) return UI.html`<span class="pv-raison">${etat.raison}</span>`;
    return UI.html`<span class="pv-raison">${lienOt(id)}${etat.raison.slice(id.length)}</span>`;
  }

  function lienGamme(gamme) {
    return UI.html`<a href="#/preventif/gamme/${encodeURIComponent(gamme.id)}">${texte(gamme.libelle) || gamme.id}</a>`;
  }

  /** Échéance affichée ; celle d'une gamme au compteur est une estimation. */
  function echeanceHtml(gamme, etat) {
    if (!etat.echeance) return '';
    const estimee = texte(gamme.declencheur) === 'compteur';
    return UI.html`<span class="sans-coupure">${UI.dateFr(etat.echeance)}</span>${estimee ? UI.html` <span class="pv-estimee">${I18n.t('preventif.echeance.estimee')}</span>` : ''}`;
  }

  /** Gammes et leur état (RG5), de la plus urgente à la moins urgente : [{ gamme, etat }]. */
  function gammesAvecEtat() {
    const jour = Donnees.aujourdhui();
    const contexte = contexteCalcul();
    const rang = (entree) => RANGS_ETAT.indexOf(entree.etat.statut);
    return Donnees.lignes('gammes').map((gamme) => ({ gamme, etat: evaluerGamme(gamme, jour, contexte) }))
      .sort((a, b) => rang(a) - rang(b) || comparerTextes(a.etat.echeance || '9999', b.etat.echeance || '9999')
        || comparerTextes(a.gamme.id, b.gamme.id));
  }

  function optionsHtml(liste, valeurChoisie) {
    return UI.html`${liste.map((o) => UI.html`<option value="${o.valeur}"${o.valeur === valeurChoisie ? UI.brut(' selected') : ''}>${o.libelle}</option>`)}`;
  }

  /** Exécute une action d'un bouton : boutons de la zone désactivés pendant l'action, erreur signalée. Vrai si réussie. */
  async function agir(zone, action, contexte) {
    const boutons = UI.$$('button', zone).filter((bouton) => !bouton.disabled);
    boutons.forEach((bouton) => { bouton.disabled = true; });
    try {
      await action();
      return true;
    } catch (erreur) {
      App.signalerErreur(erreur, contexte);
      return false;
    } finally {
      boutons.forEach((bouton) => { bouton.disabled = false; });
    }
  }

  // ===========================================================================================
  // 10. Liste des gammes (#/preventif)
  // ===========================================================================================

  // Paramètres d'adresse : ?onglet=gammes|calendrier (responsable : aussi suggestions|decisions,
  // lot 3 bis), ?statut=echue…, ?equipement=EQ-0001.
  function lireFiltresAdresse(requete) {
    if (requete.has('statut')) memoire.statut = RANGS_ETAT.includes(requete.get('statut')) ? requete.get('statut') : '';
    if (requete.has('equipement')) memoire.equipement = requete.get('equipement');
  }

  /** L'onglet ouvert est gardé dans l'adresse (#/preventif?onglet=calendrier), sans réafficher l'écran. */
  function memoriserOnglet(onglet) {
    const adresse = '#/preventif?onglet=' + onglet;
    if (location.hash === adresse) return;
    try { history.replaceState(history.state, '', adresse); } catch (erreur) { /* adresse gardée telle quelle */ }
  }

  function afficherListe(conteneur, parametres) {
    const requete = parametres.requete;
    if (Suggestions.ongletRefuse(requete)) return;          // suggestions demandées par un autre profil : accueil
    lireFiltresAdresse(requete);
    // Onglets « Suggestions » et « Décisions » du responsable (suggestions-ecrans.js, §16.6) ; [] sinon.
    const ongletsSuggestions = Suggestions.ongletsPreventif();
    const ids = ONGLETS.concat(ongletsSuggestions.map((o) => o.id));
    const onglet = ids.includes(requete.get('onglet')) ? requete.get('onglet') : 'gammes';
    const toutes = gammesAvecEtat();
    const semaines = nombreDeSemaines();
    UI.remplir(conteneur, UI.html`
      <div class="preventif">
        <div class="entete-page">
          <div><h1>${I18n.t('preventif.liste.preventif')}</h1><p>${I18n.t('preventif.liste.gammes_maintenance_preventive_echeances', { n: semaines })}</p></div>
          ${App.estResponsable() ? UI.html`<div class="actions">
            <button type="button" class="btn btn-secondaire" id="pv-generer">${UI.icone('actualiser')}${I18n.t('preventif.liste.generer_ot_echus')}</button>
            <a class="btn btn-primaire" id="pv-nouvelle" href="#/preventif/gamme/nouvelle">${UI.icone('ajouter')}${I18n.t('preventif.liste.nouvelle_gamme')}</a>
          </div>` : ''}
        </div>
        <div class="pv-onglets"></div>
      </div>`);
    const bouton = UI.$('#pv-generer', conteneur);
    if (bouton) bouton.addEventListener('click', () => genererDepuisBouton(bouton));
    UI.onglets(UI.$('.pv-onglets', conteneur), [
      { id: 'gammes', libelle: I18n.t('preventif.liste.gammes'), compteur: toutes.length, afficher: (panneau) => afficherGammes(panneau, toutes) },
      { id: 'calendrier', libelle: I18n.t('preventif.liste.calendrier_semaines', { n: semaines }), afficher: (panneau) => afficherCalendrier(panneau) },
    ].concat(ongletsSuggestions), { actif: onglet, libelle: I18n.t('preventif.liste.vues_preventif'), surChangement: memoriserOnglet });
  }

  // Relais vers preventif-calendrier.js (chargé après ce fichier).
  function afficherCalendrier(panneau) {
    Preventif.interne.afficherCalendrier(panneau);
  }

  /** Bouton « Générer les OT échus » (responsable) : RG5 à la demande, puis réaffichage. */
  async function genererDepuisBouton(bouton) {
    bouton.disabled = true;
    bouton.setAttribute('aria-busy', 'true');
    try {
      const crees = await Preventif.genererOTEchus();
      UI.toast(Preventif.texteGeneration(crees.length) + '.', crees.length ? 'succes' : 'info');
      await App.reafficher();
    } catch (erreur) {
      App.signalerErreur(erreur, 'génération des OT préventifs');
    } finally {
      bouton.disabled = false;
      bouton.removeAttribute('aria-busy');
    }
  }

  function barreFiltresHtml(toutes) {
    const statuts = RANGS_ETAT.map((statut) => ({
      valeur: statut, libelle: STATUTS_GAMME[statut] + ' (' + toutes.filter((e) => e.etat.statut === statut).length + ')',
    }));
    const identifiants = new Set(toutes.map((e) => e.gamme.equipement_id));
    if (memoire.equipement) identifiants.add(memoire.equipement);
    const equipements = Array.from(identifiants).map((id) => ({ valeur: id, libelle: libelleEquipement(id) }))
      .sort((a, b) => comparerTextes(a.libelle, b.libelle));
    return UI.html`
      <form class="filtres pv-filtres" id="pv-filtres" data-hors-saisie role="search" aria-label="${I18n.t('preventif.barre_filtres.filtrer_gammes')}">
        <label class="visuellement-cache" for="pv-filtre-statut">${I18n.t('commun.champ.statut')}</label>
        <select id="pv-filtre-statut" name="statut">${optionsHtml([{ valeur: '', libelle: I18n.t('preventif.barre_filtres.tous_statuts') }].concat(statuts), memoire.statut)}</select>
        <label class="visuellement-cache" for="pv-filtre-equipement">${I18n.t('commun.champ.equipement')}</label>
        <select id="pv-filtre-equipement" name="equipement">${optionsHtml([{ valeur: '', libelle: I18n.t('preventif.barre_filtres.tous_equipements') }].concat(equipements), memoire.equipement)}</select>
      </form>`;
  }

  function colonnesListe() {
    return [
      { cle: 'equipement', libelle: I18n.t('commun.champ.equipement'), valeurTri: (l) => repere(l.gamme.equipement_id),
        rendu: (l) => UI.html`<b class="sans-coupure">${repere(l.gamme.equipement_id)}</b>` },
      { cle: 'libelle', libelle: I18n.t('preventif.colonnes_liste.gamme'), classe: 'pv-col-gamme', valeurTri: (l) => l.gamme.libelle,
        rendu: (l) => UI.html`${lienGamme(l.gamme)} <span class="pv-id">${l.gamme.id}</span>` },
      { cle: 'declencheur', libelle: I18n.t('preventif.colonnes_liste.declencheur_periodicite'), valeurTri: (l) => l.gamme.declencheur,
        rendu: (l) => UI.html`${LIBELLES_COURTS[l.gamme.declencheur] || l.gamme.declencheur}<span class="pv-sous">${periodicite(l.gamme)}</span>` },
      { cle: 'derniere', libelle: I18n.t('preventif.colonnes_liste.derniere_realisation'), valeurTri: (l) => l.gamme.derniere_realisation,
        rendu: (l) => UI.dateFr(l.gamme.derniere_realisation) },
      { cle: 'echeance', libelle: I18n.t('preventif.colonnes_liste.echeance'), valeurTri: (l) => l.etat.echeance, rendu: (l) => echeanceHtml(l.gamme, l.etat) },
      // Statut : badge, raison et, pour une gamme qui a un OT ouvert, le lien vers cet OT.
      { cle: 'statut', libelle: I18n.t('commun.champ.statut'), classe: 'pv-col-statut',
        valeurTri: (l) => String(RANGS_ETAT.indexOf(l.etat.statut)) + (l.etat.echeance || '9999'),
        rendu: (l) => UI.html`${badgeEtat(l.etat)}${raisonHtml(l.etat)}` },
    ];
  }

  function cartesHtml(liste) {
    if (!liste.length) return UI.html`<li>${UI.vide(I18n.t('preventif.cartes.aucune_gamme'), I18n.t('preventif.cartes.aucune_gamme_correspond_filtres'), 'preventif')}</li>`;
    return UI.html`${liste.map(({ gamme, etat }) => UI.html`<li><div class="carte-ligne">
      <div class="carte-tete"><b>${repere(gamme.equipement_id)}</b>${badgeEtat(etat)}</div>
      <div class="carte-titre">${lienGamme(gamme)}</div>
      <div class="carte-meta"><span>${periodicite(gamme)}</span>
        ${etat.echeance ? UI.html`<span>${I18n.t('preventif.colonnes_liste.echeance')} ${echeanceHtml(gamme, etat)}</span>` : ''}
        ${raisonHtml(etat)}</div>
    </div></li>`)}`;
  }

  function afficherGammes(panneau, toutes) {
    UI.remplir(panneau, UI.html`
      ${barreFiltresHtml(toutes)}
      <p class="note pv-compteur" id="pv-compteur" role="status"></p>
      <div class="carte pv-liste-tableau"></div>
      <ul class="liste-cartes pv-liste-cartes"></ul>`);
    const tableau = UI.tableau({ colonnes: colonnesListe(), lignes: [], libelle: I18n.t('preventif.gammes.gammes_preventif'),
      vide: I18n.t('preventif.cartes.aucune_gamme_correspond_filtres') });
    UI.$('.pv-liste-tableau', panneau).appendChild(tableau);

    function rafraichir() {
      const affichees = toutes.filter(({ gamme, etat }) => (!memoire.statut || etat.statut === memoire.statut)
        && (!memoire.equipement || gamme.equipement_id === memoire.equipement));
      tableau.mettreAJour(affichees);
      UI.remplir(UI.$('.pv-liste-cartes', panneau), cartesHtml(affichees));
      UI.$('#pv-compteur', panneau).textContent = I18n.t('preventif.gammes.n_gamme_nb_toutes', { n: affichees.length, nbToutes: toutes.length });
    }

    const formulaire = UI.$('#pv-filtres', panneau);
    formulaire.addEventListener('change', () => { Object.assign(memoire, UI.lireFormulaire(formulaire)); rafraichir(); });
    formulaire.addEventListener('submit', (evenement) => evenement.preventDefault());
    rafraichir();
  }

  // ===========================================================================================
  // 11. Formulaire d'une gamme (création, modification par le responsable)
  // ===========================================================================================

  // Champs propres à un déclencheur : masqués pour les autres (ils restent dans le formulaire et
  // gardent leur valeur ; les règles n'utilisent que ceux du déclencheur choisi).
  const DECLENCHEURS_DU_CHAMP = {
    periodicite_jours: ['date'], avance_jours: ['date'], prochaine_echeance: ['date'],
    compteur_id: ['compteur', 'seuil'], periodicite_unites: ['compteur'], seuil: ['seuil'],
    releve_derniere_realisation: ['compteur', 'seuil'],
  };

  const AIDES = {
    get periodicite_jours() { return I18n.t('preventif.periodicite_jours.obligatoire_gamme_date_ex'); },
    get avance_jours() { return I18n.t('preventif.avance_jours.ot_genere_nombre_jours'); },
    get compteur_id() { return I18n.t('preventif.compteur_id.compteur_heures_cycles_point'); },
    get periodicite_unites() { return I18n.t('preventif.periodicite_unites.obligatoire_gamme_compteur_ex'); },
    get seuil() { return I18n.t('preventif.seuil.gamme_echue_quand_releve'); },
    get derniere_realisation() { return I18n.t('preventif.derniere_realisation.mise_jour_automatiquement_cloture'); },
    get releve_derniere_realisation() { return I18n.t('preventif.releve_derniere_realisation.valeur_compteur_derniere_realisation'); },
    get prochaine_echeance() { return I18n.t('preventif.prochaine_echeance.laissez_vide_calculer_derniere'); },
    get temps_prevu_h() { return I18n.t('preventif.temps_prevu_h.recopie_chaque_ot_genere'); },
  };

  const CHAMPS_DU_FORMULAIRE = ['periodicite_jours', 'compteur_id', 'periodicite_unites', 'seuil', 'avance_jours',
    'derniere_realisation', 'releve_derniere_realisation', 'prochaine_echeance', 'temps_prevu_h'];

  function definitionChamp(nom) {
    return Schema.table('gammes').champs.find((champ) => champ.nom === nom);
  }

  function listeEquipements(valeur) {
    return Donnees.lignes('equipements').filter((e) => e.actif !== '0' || e.id === valeur)
      .map((e) => ({ valeur: e.id, libelle: libelleEquipement(e.id) }))
      .sort((a, b) => comparerTextes(a.libelle, b.libelle));
  }

  function listeCompteurs() {
    return Donnees.lignes('compteurs')
      .map((c) => ({ valeur: c.id, libelle: repere(c.equipement_id) + ' — ' + texte(c.libelle) + (c.unite ? ' (' + c.unite + ')' : '') + ' · ' + c.id }))
      .sort((a, b) => comparerTextes(a.libelle, b.libelle));
  }

  function formulaireGamme(gamme, valeursInitiales) {
    const valeur = (nom) => (gamme ? gamme[nom] : (valeursInitiales || {})[nom]);
    const formulaire = UI.element(UI.html`<form class="form-grille pv-formulaire" id="pv-formulaire-gamme" novalidate></form>`);
    const ajouter = (nom, bloc, large) => {
      if (large) bloc.classList.add('large');
      if (DECLENCHEURS_DU_CHAMP[nom]) bloc.dataset.declencheurs = DECLENCHEURS_DU_CHAMP[nom].join(' ');
      formulaire.appendChild(bloc);
    };
    ajouter('equipement_id', UI.champ(definitionChamp('equipement_id'), valeur('equipement_id'),
      { liste: listeEquipements(valeur('equipement_id')), obligatoire: true }));
    ajouter('libelle', UI.champ(definitionChamp('libelle'), valeur('libelle'), { obligatoire: true, attributs: { maxlength: '160' } }));
    ajouter('declencheur', UI.champ(Object.assign({}, definitionChamp('declencheur'), { type: 'ref' }), valeur('declencheur') || 'date', {
      obligatoire: true, liste: Object.keys(DECLENCHEURS).map((cle) => ({ valeur: cle, libelle: DECLENCHEURS[cle] })),
    }));
    CHAMPS_DU_FORMULAIRE.forEach((nom) => ajouter(nom, UI.champ(definitionChamp(nom), valeur(nom), {
      aide: AIDES[nom], liste: nom === 'compteur_id' ? listeCompteurs() : undefined,
    })));
    ajouter('consignes', UI.champ(definitionChamp('consignes'), valeur('consignes'),
      { aide: I18n.t('preventif.formulaire_gamme.recopiees_chaque_ot_genere') }), true);
    ajouter('actif', UI.champ(definitionChamp('actif'), gamme ? gamme.actif : '1', { libelle: I18n.t('preventif.formulaire_gamme.gamme_active_genere_ot') }), true);
    formulaire.appendChild(UI.element(UI.html`<p class="mention-requis large"><span class="requis" aria-hidden="true">*</span>${I18n.t('commun.message.champ_obligatoire')}</p>`));
    formulaire.appendChild(UI.element(UI.html`<div class="actions">
      <button type="submit" class="btn btn-primaire">${UI.icone('valider')}${gamme ? I18n.t('preventif.formulaire_gamme.enregistrer_gamme') : I18n.t('preventif.formulaire_gamme.creer_gamme')}</button>
      <a class="btn btn-fantome" href="${gamme ? '#/preventif/gamme/' + encodeURIComponent(gamme.id) : '#/preventif'}">${I18n.t('commun.bouton.annuler')}</a>
    </div>`));

    const choixDeclencheur = formulaire.querySelector('[name="declencheur"]');
    const montrerChampsDuDeclencheur = () => UI.$$('[data-declencheurs]', formulaire).forEach((bloc) => {
      bloc.hidden = !bloc.dataset.declencheurs.split(' ').includes(choixDeclencheur.value);
    });
    choixDeclencheur.addEventListener('change', montrerChampsDuDeclencheur);
    montrerChampsDuDeclencheur();
    brancherEnregistrement(formulaire, gamme);
    return formulaire;
  }

  function afficherErreurs(formulaire, erreurs) {
    UI.$$('.champ', formulaire).forEach((bloc) => UI.erreurChamp(formulaire, bloc.dataset.champ, ''));
    erreurs.forEach((erreur) => UI.erreurChamp(formulaire, erreur.nom, erreur.message));
    const premier = UI.$('[aria-invalid="true"]', formulaire);
    if (premier) premier.focus();
  }

  function brancherEnregistrement(formulaire, gamme) {
    let enCours = false;
    formulaire.addEventListener('submit', async (evenement) => {
      evenement.preventDefault();
      if (enCours) return;
      const valeurs = UI.lireFormulaire(formulaire);
      const erreurs = UI.verifierFormulaire(formulaire);
      Preventif.verifierGamme(valeurs).forEach((erreur) => { if (!erreurs.some((e) => e.nom === erreur.nom)) erreurs.push(erreur); });
      afficherErreurs(formulaire, erreurs);
      if (erreurs.length) return;
      const bouton = UI.$('button[type=submit]', formulaire);
      enCours = true;
      bouton.disabled = true;
      bouton.setAttribute('aria-busy', 'true');
      try {
        if (gamme) {
          const changes = await Preventif.modifierGamme(gamme.id, valeurs);
          App.marquerSaisie(false);
          UI.toast(changes.length ? I18n.t('preventif.brancher_enregistrement.gamme_enregistree') : I18n.t('commun.message.aucune_modification'), changes.length ? 'succes' : 'info');
          await Suggestions.apresModificationGamme(gamme.id, changes);     // suggestion suivie : traitée (§16.6)
          await App.reafficher();
        } else {
          const id = await Preventif.creerGamme(valeurs);
          App.marquerSaisie(false);
          UI.toast(I18n.t('preventif.brancher_enregistrement.gamme_creee_ajoutez_maintenant', { id }), 'succes');
          await Suggestions.apresCreationGamme(id);                         // S1 suivie : traitée (§16.6)
          App.naviguer('#/preventif/gamme/' + encodeURIComponent(id));
        }
      } catch (erreur) {
        App.signalerErreur(erreur, 'enregistrement de la gamme');
      } finally {
        enCours = false;
        bouton.disabled = false;
        bouton.removeAttribute('aria-busy');
      }
    });
  }

  function afficherNouvelle(conteneur, parametres) {
    UI.remplir(conteneur, UI.html`
      <div class="preventif">
        <div class="entete-page"><div>
          <div class="fil">${I18n.html('preventif.nouvelle.preventif_nouvelle_gamme')}</div>
          <h1>${I18n.t('preventif.liste.nouvelle_gamme')}</h1>
          <p>${I18n.t('preventif.nouvelle.check_list_operations_realiser')}</p>
        </div></div>
        <article class="carte pv-carte-formulaire"></article>
      </div>`);
    // ?equipement= ; ?suggestion=<clé S1> pré-remplit le libellé et rappelle la suggestion (§16.6).
    const creation = Suggestions.preparerCreation(parametres.requete);
    const carte = UI.$('.pv-carte-formulaire', conteneur);
    if (creation.rappel) carte.before(creation.rappel);
    carte.appendChild(formulaireGamme(null, creation.valeurs));
  }

  // ===========================================================================================
  // 12. Fiche d'une gamme (#/preventif/gamme/<id>)
  // ===========================================================================================

  function descriptionHtml(gamme, etat) {
    const declencheur = texte(gamme.declencheur) || 'date';
    const compteur = Donnees.trouver('compteurs', gamme.compteur_id);
    const releve = compteur ? Preventif.dernierReleve(compteur.id) : null;
    return UI.html`<dl class="valeurs">
      <dt>${I18n.t('commun.champ.equipement')}</dt><dd><a href="#/equipement/${encodeURIComponent(gamme.equipement_id)}">${libelleEquipement(gamme.equipement_id)}</a></dd>
      <dt>${I18n.t('preventif.description.declencheur')}</dt><dd>${DECLENCHEURS[declencheur] || declencheur}</dd>
      <dt>${I18n.t('preventif.description.periodicite')}</dt><dd>${periodicite(gamme)}</dd>
      ${compteur ? UI.html`<dt>${I18n.t('preventif.compteur.compteur')}</dt><dd>${texte(compteur.libelle)} (${compteur.id})${releve
        ? UI.html` ${I18n.t('preventif.description.dernier_releve', { avecUnite: avecUnite(releve.valeur, compteur.unite), date: UI.dateFr(releve.date) })}` : ''}</dd>` : ''}
      ${declencheur === 'date' ? UI.html`<dt>${I18n.t('preventif.description.avance')}</dt><dd>${gamme.avance_jours ? I18n.t('preventif.description.avance_jours', { n: gamme.avance_jours }) : ''}</dd>` : ''}
      <dt>${I18n.t('preventif.colonnes_liste.derniere_realisation')}</dt><dd>${UI.dateFr(gamme.derniere_realisation)}${compteur && texte(gamme.releve_derniere_realisation)
        ? ' (' + avecUnite(gamme.releve_derniere_realisation, compteur.unite) + ')' : ''}</dd>
      <dt>${I18n.t('preventif.colonnes_liste.echeance')}</dt><dd>${echeanceHtml(gamme, etat)}</dd>
      <dt>${I18n.t('preventif.description.temps_prevu')}</dt><dd>${gamme.temps_prevu_h ? UI.heures(gamme.temps_prevu_h) : ''}</dd>
      <dt>${I18n.t('preventif.description.consignes')}</dt><dd class="pv-texte">${gamme.consignes}</dd>
      <dt>${I18n.t('preventif.description.active')}</dt><dd>${gamme.actif === '0' ? I18n.t('preventif.description.non') : I18n.t('preventif.description.oui')}</dd>
    </dl>`;
  }

  function afficherOtsDeLaGamme(section, gammeId) {
    const ots = Donnees.lignes('ordres_travail').filter((ot) => ot.gamme_id === gammeId)
      .sort((a, b) => comparerTextes(b.date_creation, a.date_creation) || comparerTextes(b.id, a.id));
    UI.remplir(section, UI.html`<div class="entete-carte"><h2 id="pv-titre-ots">${I18n.t('preventif.ots_de_la_gamme.ot_gamme')}</h2><span class="badge neutre">${ots.length}</span></div>`);
    section.appendChild(UI.tableau({
      colonnes: [
        { cle: 'id', libelle: I18n.t('commun.champ.numero'), rendu: (ot) => lienOt(ot.id) },
        { cle: 'statut', libelle: I18n.t('commun.champ.statut'), rendu: (ot) => UI.badgeValeur('ordres_travail', 'statut', ot.statut) },
        { cle: 'date_prevue', libelle: I18n.t('preventif.ots_de_la_gamme.prevu'), rendu: (ot) => UI.dateFr(ot.date_prevue) },
        { cle: 'date_fin', libelle: I18n.t('preventif.ots_de_la_gamme.realise'), rendu: (ot) => UI.dateFr(ot.date_fin) },
      ],
      lignes: ots, libelle: I18n.t('preventif.ots_de_la_gamme.ot_gamme'), classe: 'pv-table-ots', vide: I18n.t('preventif.ots_de_la_gamme.aucun_ot_gamme_moment'),
    }));
  }

  function afficherFiche(conteneur, parametres) {
    const gamme = Donnees.trouver('gammes', parametres.id);
    if (!gamme) {
      UI.remplir(conteneur, UI.html`<div class="preventif"><div class="entete-page"><div>
        <div class="fil"><a href="#/preventif">${I18n.t('preventif.liste.preventif')}</a></div><h1>${I18n.t('preventif.fiche.gamme_introuvable')}</h1></div></div>
        ${UI.vide(I18n.t('preventif.fiche.gamme_introuvable'), I18n.t('preventif.fiche.aucune_gamme_porte_identifiant', { parametresId: parametres.id }), 'recherche')}</div>`);
      return;
    }
    App.definirTitre(gamme.id);
    const etat = Preventif.etatGamme(gamme);
    const responsable = App.estResponsable();
    UI.remplir(conteneur, UI.html`
      <div class="preventif pv-fiche" data-gamme="${gamme.id}">
        <div class="entete-page"><div>
          <div class="fil">${I18n.html('preventif.fiche.preventif_gamme_id', { gammeId: gamme.id })}</div>
          <h1><span class="pv-numero">${gamme.id}</span> ${texte(gamme.libelle)}</h1>
          <div class="pv-badges">${badgeEtat(etat)}${raisonHtml(etat)}</div>
        </div></div>
        <div class="pv-fiche-grille">
          <section class="carte pv-parametres" aria-labelledby="pv-titre-parametres">
            <div class="entete-carte"><h2 id="pv-titre-parametres">${responsable ? I18n.t('preventif.fiche.parametres_gamme') : I18n.t('preventif.colonnes_liste.gamme')}</h2></div>
            ${responsable ? '' : descriptionHtml(gamme, etat)}
          </section>
          <section class="carte pv-check-liste" aria-labelledby="pv-titre-check-liste"></section>
          <section class="carte pv-ots" aria-labelledby="pv-titre-ots"></section>
        </div>
      </div>`);
    // Responsable (§16.6) : rappel de ?suggestion=<clé> (suivie jusqu'à son marquage), puis encart des
    // autres suggestions ouvertes de la gamme. suiviFiche d'abord : il dit à encartGamme ce qui est rappelé.
    [Suggestions.suiviFiche(gamme.id, parametres.requete), Suggestions.encartGamme(gamme.id)]
      .forEach((bloc) => { if (bloc) UI.$('.pv-fiche-grille', conteneur).before(bloc); });
    if (responsable) UI.$('.pv-parametres', conteneur).appendChild(formulaireGamme(gamme));
    const checkListe = UI.$('.pv-check-liste', conteneur);
    afficherCheckListe(checkListe, gamme.id);
    if (responsable) brancherCheckListe(checkListe, gamme.id);
    afficherOtsDeLaGamme(UI.$('.pv-ots', conteneur), gamme.id);
  }

  // ===========================================================================================
  // 13. Éditeur de check-list (responsable) ; lecture seule pour le technicien
  // ===========================================================================================

  function operationHtml(operation, rang, total, responsable) {
    return UI.html`<li class="pv-operation" data-operation="${operation.id}">
      <span class="pv-rang" aria-hidden="true">${rang + 1}</span>
      <div class="pv-operation-texte"><span class="operation">${operation.operation}</span>
        ${operation.valeur_attendue ? UI.html`<span class="attendu">${I18n.t('preventif.operation.attendu_valeur_attendue', { valeur_attendue: operation.valeur_attendue })}</span>` : ''}</div>
      ${responsable ? UI.html`<div class="pv-operation-actions">
        <button type="button" class="btn btn-fantome btn-icone" data-action="monter" title="${I18n.t('preventif.operation.monter')}"
          aria-label="${I18n.t('preventif.operation.monter_operation', { numero: rang + 1 })}"${rang === 0 ? UI.brut(' disabled') : ''}>↑</button>
        <button type="button" class="btn btn-fantome btn-icone" data-action="descendre" title="${I18n.t('preventif.operation.descendre')}"
          aria-label="${I18n.t('preventif.operation.descendre_operation', { numero: rang + 1 })}"${rang === total - 1 ? UI.brut(' disabled') : ''}>↓</button>
        <button type="button" class="btn btn-fantome" data-action="modifier">${I18n.t('commun.bouton.modifier')}</button>
        <button type="button" class="btn btn-danger" data-action="supprimer">${I18n.t('preventif.operation.supprimer')}</button>
      </div>` : ''}
    </li>`;
  }

  function formulaireAjoutHtml() {
    return UI.html`<form class="form-ligne pv-ajout-operation" id="pv-ajout-operation" novalidate>
      <div class="champ"><label class="libelle" for="pv-nouvelle-operation">${I18n.t('preventif.formulaire_ajout.nouvelle_operation')} <span class="requis" aria-hidden="true">*</span></label>
        <input type="text" id="pv-nouvelle-operation" name="operation" maxlength="200" autocomplete="off"
          placeholder="${I18n.t('preventif.formulaire_ajout.ex_controler_tension_courroie')}" aria-describedby="pv-erreur-operation"></div>
      <div class="champ"><label class="libelle" for="pv-nouvelle-attendue">${I18n.t('preventif.formulaire_ajout.valeur_attendue')}</label>
        <input type="text" id="pv-nouvelle-attendue" name="valeur_attendue" maxlength="120" autocomplete="off" placeholder="${I18n.t('preventif.formulaire_ajout.ex_fleche_10_15')}"></div>
      <button type="submit" class="btn btn-secondaire">${UI.icone('ajouter')}${I18n.t('commun.bouton.ajouter')}</button>
      <p class="erreur-champ" id="pv-erreur-operation" role="alert" hidden></p>
    </form>`;
  }

  function afficherCheckListe(section, gammeId) {
    const operations = operationsDeGamme(gammeId);
    const responsable = App.estResponsable();
    UI.remplir(section, UI.html`
      <div class="entete-carte"><h2 id="pv-titre-check-liste">${I18n.t('preventif.check_liste.check_list')}</h2><span class="badge neutre">${operations.length}</span></div>
      ${operations.length
        ? UI.html`<ol class="pv-operations">${operations.map((op, rang) => operationHtml(op, rang, operations.length, responsable))}</ol>`
        : UI.html`<p class="muted">${I18n.t('preventif.check_liste.aucune_operation')}${responsable ? ' ' + I18n.t('preventif.check_liste.ajoutez_ci_dessous_operations') : '.'}</p>`}
      ${responsable ? formulaireAjoutHtml() : ''}
      <p class="note">${I18n.t('preventif.check_liste.chaque_ot_genere_recoit')}</p>`);
    // Lot 4 (§17.5) : check-list de départ proposée par l'IA (responsable ; bouton absent sans IA, posé
    // ou retiré au fil de l'état de l'IA).
    if (responsable) {
      // Encadré placé après l'emplacement (pas dedans) : un message d'erreur reste visible quand le bouton s'en va.
      const zoneIa = Ia.emplacement(I18n.t('preventif.check_liste.proposer_check_list'), () => proposerCheckListe(section, gammeId, zoneIa));
      UI.$('.pv-ajout-operation', section).insertAdjacentElement('afterend', zoneIa);
    }
  }

  /** Cause visée par la gamme : celle d'une suggestion ouverte qui la cite, ou « Prévenir : <cause> ». */
  function causeVisee(gamme) {
    const suggestion = Suggestions.pourGamme(gamme.id, Donnees.aujourdhui()).find((s) => s.causeLibelle);
    return suggestion ? suggestion.causeLibelle : (/^Prévenir : (.+)$/.exec(texte(gamme.libelle)) || [])[1] || '';
  }

  /** Proposition de l'IA : opérations cochables ; seules les cochées sont ajoutées, sur le clic (journal habituel). */
  async function proposerCheckListe(section, gammeId, zoneIa) {
    const gamme = Donnees.trouver('gammes', gammeId) || { id: gammeId };
    const equipement = Donnees.trouver('equipements', gamme.equipement_id) || {};
    const issue = await Ia.ouvrirEncadre({
      apres: zoneIa, fonction: 'checkList',
      donnees: { designation: equipement.designation, marque: equipement.marque, modele: equipement.modele, libelle: gamme.libelle,
        declencheur: DECLENCHEURS[gamme.declencheur] || gamme.declencheur, periodicite: periodicite(gamme), causeVisee: causeVisee(gamme) },
      rendu: (resultat) => UI.html`<ul class="pv-ia-operations">${resultat.operations.map((op, rang) => UI.html`<li><label class="case">
        <input type="checkbox" checked data-rang="${rang}"><span>${op.operation}${op.valeur_attendue ? UI.html` — <i>${op.valeur_attendue}</i>` : ''}</span></label></li>`)}</ul>`,
      boutons: [{ libelle: I18n.t('preventif.proposer_check_liste.ajouter_operations_cochees'), valeur: 'ajouter', classe: 'btn-primaire', action: async (resultat, reponse) => {
        const cochees = UI.$$('.pv-ia-operations input:checked', section);
        if (!cochees.length) { UI.toast(I18n.t('preventif.proposer_check_liste.cochez_moins_operation'), 'attention'); return false; }
        for (const caseACocher of cochees) {
          await Preventif.ajouterOperation(gammeId, resultat.operations[Number(caseACocher.dataset.rang)]);
          caseACocher.checked = false;                     // ajoutée : après un échec, un nouvel essai ne la rajoute pas
          caseACocher.disabled = true;
        }
        try {
          await Ia.tracerUtilisation('gammes', gammeId, 'check-list', reponse.modele);
        } catch (erreur) {
          console.warn('Prévo (préventif) : trace de la proposition IA non écrite (' + (erreur && erreur.message) + ').', erreur);
        }
        UI.toast(I18n.t('preventif.proposer_check_liste.operation_ajoutee_check_list', { n: cochees.length }), 'succes');
        return true;
      } }],
    });
    if (issue.choix !== 'ajouter') return;
    afficherCheckListe(section, gammeId);
    Suggestions.apresCheckListe(gammeId);                     // check-list changée : suggestion suivie traitée (§16.6)
  }

  /** Fenêtre de modification d'une opération ; vrai si elle a été enregistrée. */
  async function modifierDansFenetre(section, operationId) {
    const operation = Donnees.trouver('gamme_operations', operationId);
    if (!operation) return true;                                   // déjà supprimée : on réaffiche
    const contenu = UI.element(UI.html`<div class="form-colonne">
      <div class="champ"><label class="libelle" for="pv-modif-operation">${I18n.t('preventif.modifier_dans_fenetre.operation')} <span class="requis" aria-hidden="true">*</span></label>
        <input type="text" id="pv-modif-operation" maxlength="200" aria-describedby="pv-modif-erreur"></div>
      <div class="champ"><label class="libelle" for="pv-modif-attendue">${I18n.t('preventif.formulaire_ajout.valeur_attendue')}</label>
        <input type="text" id="pv-modif-attendue" maxlength="120"></div>
      <p class="erreur-champ" id="pv-modif-erreur" role="alert" hidden></p>
    </div>`);
    const champOperation = UI.$('#pv-modif-operation', contenu);
    const champAttendue = UI.$('#pv-modif-attendue', contenu);
    champOperation.value = operation.operation;
    champAttendue.value = operation.valeur_attendue;
    const choix = await UI.fenetre({
      titre: I18n.t('preventif.modifier_dans_fenetre.modifier_operation'), contenu,
      boutons: [{ libelle: I18n.t('commun.bouton.annuler'), valeur: null, classe: 'btn-fantome' },
        { libelle: I18n.t('commun.bouton.enregistrer'), valeur: 'ok', classe: 'btn-primaire', defaut: true }],
      avantFermeture(valeur) {
        if (valeur !== 'ok' || champOperation.value.trim()) return true;
        const erreur = UI.$('#pv-modif-erreur', contenu);
        erreur.textContent = I18n.t('preventif.modifier_dans_fenetre.decrivez_operation_realiser');
        erreur.hidden = false;
        champOperation.focus();
        return false;
      },
    });
    if (choix !== 'ok') return false;
    return agir(section, () => Preventif.modifierOperation(operationId,
      { operation: champOperation.value, valeur_attendue: champAttendue.value }), I18n.t('preventif.modifier_dans_fenetre.modification_operation'));
  }

  /** Suppression après confirmation (D26 : seule suppression permise, inscrite au journal). */
  async function supprimerAvecConfirmation(section, operationId) {
    const operation = Donnees.trouver('gamme_operations', operationId);
    if (!operation) return true;
    const confirme = await UI.confirmer(I18n.t('preventif.supprimer_avec_confirmation.supprimer_operation_check_list', { operation: operation.operation }),
    { titre: I18n.t('preventif.supprimer_avec_confirmation.supprimer_operation'), oui: I18n.t('preventif.operation.supprimer'), danger: true });
    if (!confirme) return false;
    const fait = await agir(section, () => Preventif.supprimerOperation(operationId), I18n.t('preventif.supprimer_avec_confirmation.suppression_operation'));
    if (fait) UI.toast(I18n.t('preventif.supprimer_avec_confirmation.operation_supprimee_inscrite_journal'), 'succes');
    return true;
  }

  /** Écouteurs de l'éditeur, posés UNE fois sur la carte (délégation) : la carte est redessinée après chaque action. */
  function brancherCheckListe(section, gammeId) {
    const redessiner = (operationId, action) => {
      afficherCheckListe(section, gammeId);
      const bouton = operationId ? UI.$('[data-operation="' + operationId + '"] [data-action="' + action + '"]', section) : null;
      if (bouton && !bouton.disabled) bouton.focus();
      Suggestions.apresCheckListe(gammeId);                  // check-list changée : suggestion suivie traitée (§16.6)
    };
    section.addEventListener('submit', async (evenement) => {
      evenement.preventDefault();
      const formulaire = evenement.target;
      const valeurs = UI.lireFormulaire(formulaire);
      const erreur = UI.$('#pv-erreur-operation', formulaire);
      if (!valeurs.operation) {
        erreur.textContent = I18n.t('preventif.modifier_dans_fenetre.decrivez_operation_realiser');
        erreur.hidden = false;
        UI.$('#pv-nouvelle-operation', formulaire).focus();
        return;
      }
      if (!await agir(section, () => Preventif.ajouterOperation(gammeId, valeurs), I18n.t('preventif.brancher_check_liste.ajout_operation'))) return;
      redessiner();
      UI.$('#pv-nouvelle-operation', section).focus();
    });
    section.addEventListener('click', async (evenement) => {
      const bouton = evenement.target.closest('button[data-action]');
      if (!bouton || !section.contains(bouton)) return;
      const operationId = bouton.closest('[data-operation]').dataset.operation;
      const action = bouton.dataset.action;
      let fait = false;
      if (action === 'monter' || action === 'descendre') {
        fait = await agir(section, () => Preventif.deplacerOperation(operationId, action === 'monter' ? -1 : 1), 'ordre de la check-list');
      } else if (action === 'modifier') {
        fait = await modifierDansFenetre(section, operationId);
      } else if (action === 'supprimer') {
        fait = await supprimerAvecConfirmation(section, operationId);
      }
      if (fait) redessiner(operationId, action);
    });
  }

  // ===========================================================================================
  // 14. Enregistrement des écrans (App est chargé après les modules, §8)
  // ===========================================================================================

  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'preventif', route: /^#\/preventif$/, get titre() { return I18n.t('preventif.liste.preventif'); },
      menu: { get libelle() { return I18n.t('preventif.liste.preventif'); }, icone: 'preventif', ordre: 35 },
      profils: ['technicien', 'responsable'],
      get tables() { return App.estResponsable() ? TABLES_ECRANS.concat(TABLES_SUGGESTIONS) : TABLES_ECRANS; },
      afficher: afficherListe,
    });
    App.ecran({
      id: 'preventif-gamme-nouvelle', route: /^#\/preventif\/gamme\/nouvelle$/, get titre() { return I18n.t('preventif.liste.nouvelle_gamme'); },
      parent: 'preventif', profils: ['responsable'], tables: ['equipements', 'compteurs'],
      afficher: afficherNouvelle,
    });
    App.ecran({
      id: 'preventif-gamme', route: /^#\/preventif\/gamme\/(?<id>(?!nouvelle$)[^/?]+)$/, get titre() { return I18n.t('preventif.titre.gamme_preventif'); },
      parent: 'preventif', profils: ['technicien', 'responsable'], tables: TABLES_ECRANS,
      afficher: afficherFiche,
    });
  });

  return {};
})());
