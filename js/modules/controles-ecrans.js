'use strict';
// Controles (3/3) — écran E10 (ARCHITECTURE.md §15.7, §15.2) : liste #/controles (?statut=,
// ?filtre=30j, ?equipement=, ?recherche=, ?inactifs=1), création #/controles/nouveau (?equipement=),
// fiche #/controles/<id> (statut RG9, dernier contrôle et rapport, OT réglementaires de
// l'équipement, historique au journal) ; puis l'enregistrement des écrans auprès d'App.
// Profils : le responsable a tous les boutons ; le technicien consulte (aucun bouton d'écriture
// n'est rendu) ; le demandeur n'a pas accès (App le renvoie à l'accueil).
// Le module ne crée jamais d'OT : « Créer un OT » ouvre #/ot/nouveau pré-rempli (type
// réglementaire, titre, équipement), que le responsable relit et valide.
// Complète l'objet Controles.

Object.assign(Controles, (() => {

  // Règles et outils de controles-regles.js et controles-ecritures.js.
  const { texte, dateIso, observationsALever, equipementSuivi, verifierRealisation, verifierLevee,
    verifierFichierRapport, EXTENSIONS_RAPPORT } = Controles.interne;
  const { STATUTS, etat, sous30Jours } = Controles;

  const FILTRE_30J = '30j';
  // Instruments de la liste : statut, libellé, couleur du trait (le libellé dit toujours le statut).
  function instruments() {
    return [
      { statut: 'en retard', libelle: I18n.t('controles.instruments.retard'), ton: 'rouge' },
      { statut: 'observations à lever', libelle: I18n.t('controles.instruments.observations_lever'), ton: 'ambre' },
      { statut: 'à planifier', libelle: I18n.t('controles.instruments.planifier_30_jours'), ton: 'cyan' },
      { statut: 'à jour', libelle: I18n.t('controles.instruments.jour'), ton: 'vert' },
    ];
  }
  const LIMITE_HISTORIQUE = 30;

  // ===========================================================================================
  // 8. Petits outils d'écran
  // ===========================================================================================

  function equipementDe(controle) {
    return Donnees.trouver('equipements', controle.equipement_id) || null;
  }

  function repere(controle) {
    const equipement = equipementDe(controle);
    return equipement ? (equipement.repere || equipement.id) : (controle.equipement_id || '');
  }

  /** « PR-01 — Presse » ; l'identifiant seul si l'équipement est introuvable. */
  function libelleEquipement(controle) {
    const equipement = equipementDe(controle);
    if (!equipement) return I18n.t('controles.libelle_equipement.equipement_introuvable', { equipementId: (controle.equipement_id || '') });
    return (equipement.repere || equipement.id) + (equipement.designation ? ' — ' + equipement.designation : '');
  }

  function lienEquipement(controle) {
    if (!equipementDe(controle)) return UI.html`<span>${libelleEquipement(controle)}</span>`;
    return UI.html`<a href="#/equipement/${encodeURIComponent(controle.equipement_id)}">${libelleEquipement(controle)}</a>`;
  }

  /** Statut principal puis statuts secondaires (badges : texte toujours affiché, la couleur aide). */
  function badgesStatut(controle, etatCalcule) {
    return UI.html`<span class="controles-statuts" data-controle="${controle.id}">${UI.badgeStatut(etatCalcule.statut)}${etatCalcule.secondaires.map((statut) => UI.html` <span class="controles-secondaire" title="${I18n.t('controles.badges_statut.aussi_statut', { statut })}">${UI.badgeStatut(statut)}</span>`)}</span>`;
  }

  /** Lien « Créer un OT » : formulaire de l'OT pré-rempli (rien n'est créé sans validation). Titre
   *  (D40) : « Levée des observations — <nature> » s'il en reste à lever, sinon « Accompagnement du
   *  contrôle — <nature> » ; l'équipement est déjà dans son propre champ. */
  function adresseNouvelOt(controle) {
    const titre = (observationsALever(controle) ? I18n.t('controles.adresse_nouvel_ot.levee_observations') + ' ' : I18n.t('controles.adresse_nouvel_ot.accompagnement_controle') + ' ')
      + (texte(controle.nature) || I18n.t('controles.adresse_nouvel_ot.controle_reglementaire'));
    return '#/ot/nouveau?equipement=' + encodeURIComponent(controle.equipement_id)
      + '&type=' + encodeURIComponent('réglementaire') + '&titre=' + encodeURIComponent(titre);
  }

  function definitionChamp(nom, remplacement) {
    return Object.assign({}, Schema.champ('controles_reglementaires', nom), remplacement || {});
  }

  /** Valeurs des champs nommés d'un bloc (une fenêtre vit déjà dans un <form>) ; fichiers ignorés. */
  function lireChamps(bloc) {
    const valeurs = {};
    UI.$$('[name]', bloc).forEach((controle) => {
      if (controle.type === 'file') return;
      valeurs[controle.name] = controle.type === 'checkbox' ? (controle.checked ? '1' : '0') : String(controle.value || '').trim();
    });
    return valeurs;
  }

  function afficherErreurs(bloc, erreurs) {
    UI.$$('.champ', bloc).forEach((champ) => UI.erreurChamp(bloc, champ.dataset.champ, ''));
    erreurs.forEach((erreur) => UI.erreurChamp(bloc, erreur.nom, erreur.message));
    const premier = UI.$('[aria-invalid="true"]', bloc);
    if (premier) premier.focus();
  }

  // Fenêtre de saisie : UI.fenetreAction (interface.js), commune aux écrans Contrôles et Équipe (lot 4).

  // ===========================================================================================
  // 9. Liste #/controles : instruments, filtres, tableau (cartes sur téléphone)
  // ===========================================================================================

  /** Filtres lus dans l'adresse (le formulaire réécrit l'adresse : actualiser garde le filtre). */
  function filtresDepuis(requete) {
    const statut = requete.get('filtre') === FILTRE_30J ? FILTRE_30J
      : (STATUTS.includes(requete.get('statut')) ? requete.get('statut') : '');
    return { statut, recherche: requete.get('recherche') || '', inactifs: requete.get('inactifs') === '1',
      equipement: requete.get('equipement') || '' };
  }

  function adresseDesFiltres(filtres) {
    const parametres = new URLSearchParams();
    if (filtres.statut === FILTRE_30J) parametres.set('filtre', FILTRE_30J);
    else if (filtres.statut) parametres.set('statut', filtres.statut);
    if (filtres.recherche) parametres.set('recherche', filtres.recherche);
    if (filtres.inactifs) parametres.set('inactifs', '1');
    if (filtres.equipement) parametres.set('equipement', filtres.equipement);
    const suite = parametres.toString().replace(/\+/g, '%20');
    return '#/controles' + (suite ? '?' + suite : '');
  }

  function normaliser(valeur) {
    return UI.normaliserRecherche(valeur);
  }

  /** Lignes de la liste : { controle, etat, suivi } ; ordre : statut, prochaine date, identifiant. */
  function lignesDeLaListe(jour) {
    return Donnees.lignes('controles_reglementaires').map((controle) => ({
      controle, etat: etat(controle, jour), suivi: equipementSuivi(controle),
    })).sort((a, b) => STATUTS.indexOf(a.etat.statut) - STATUTS.indexOf(b.etat.statut)
      || (a.etat.prochaine || '').localeCompare(b.etat.prochaine || '')
      || texte(a.controle.id).localeCompare(texte(b.controle.id), 'fr', { numeric: true }));
  }

  /** Lignes de base : celles d'un équipement (?equipement=), sinon les équipements suivis (inactifs en option). */
  function dansLaBase(ligne, filtres) {
    if (filtres.equipement) return ligne.controle.equipement_id === filtres.equipement;
    return filtres.inactifs || ligne.suivi;
  }

  function aLeStatut(ligne, statut) {
    return ligne.etat.statut === statut || ligne.etat.secondaires.includes(statut);
  }

  function garder(ligne, filtres, ids30j) {
    if (!dansLaBase(ligne, filtres)) return false;
    if (filtres.statut === FILTRE_30J && !ids30j.has(ligne.controle.id)) return false;
    if (filtres.statut && filtres.statut !== FILTRE_30J && !aLeStatut(ligne, filtres.statut)) return false;
    const recherche = normaliser(filtres.recherche);
    if (!recherche) return true;
    const controle = ligne.controle;
    return normaliser([controle.id, controle.nature, controle.texte_reference, controle.organisme, libelleEquipement(controle)]
      .join(' ')).includes(recherche);
  }

  function instrumentsHtml(lignes, filtres) {
    const base = lignes.filter((ligne) => dansLaBase(ligne, filtres));
    return UI.html`<div class="instruments controles-instruments">${instruments().map((instrument) => UI.html`
      <a class="${instrument.ton}" data-statut="${instrument.statut}" href="${adresseDesFiltres(Object.assign({}, filtres, { statut: instrument.statut }))}">
        <div class="lib">${instrument.libelle}</div>
        <div class="chiffre">${base.filter((ligne) => aLeStatut(ligne, instrument.statut)).length}</div>
        <div class="comp">${filtres.statut === instrument.statut ? I18n.t('controles.instruments.filtre_applique') : I18n.t('controles.instruments.voir_liste')}</div></a>`)}</div>`;
  }

  function optionsStatut() {
    return [{ valeur: '', libelle: I18n.t('controles.options_statut.tous_statuts') }, { valeur: FILTRE_30J, libelle: I18n.t('controles.options_statut.sous_30_jours_retards') }]
      .concat(STATUTS.map((statut) => ({ valeur: statut, libelle: statut.charAt(0).toUpperCase() + statut.slice(1) })));
  }

  function colonnesListe() {
    // Le statut vient tôt dans la ligne : sur un écran étroit, le tableau défile dans son cadre.
    return [
      { cle: 'equipement', libelle: I18n.t('commun.champ.equipement'), valeurTri: (l) => repere(l.controle), classe: 'sans-coupure',
        rendu: (l) => (equipementDe(l.controle)
          ? UI.html`<a href="#/equipement/${encodeURIComponent(l.controle.equipement_id)}" title="${libelleEquipement(l.controle)}">${repere(l.controle)}</a>`
          : UI.html`<span>${libelleEquipement(l.controle)}</span>`) },
      { cle: 'nature', libelle: I18n.t('controles.colonnes_liste.controle'), valeurTri: (l) => l.controle.nature, classe: 'controles-col-nature',
        rendu: (l) => UI.html`<a class="controles-lien" href="#/controles/${encodeURIComponent(l.controle.id)}">${l.controle.nature || l.controle.id}</a>
          <small class="controles-sous-ligne">${libelleEquipement(l.controle)}${l.controle.texte_reference ? ' · ' + l.controle.texte_reference : ''}</small>` },
      { cle: 'statut', libelle: I18n.t('commun.champ.statut'), valeurTri: (l) => STATUTS.indexOf(l.etat.statut), classe: 'controles-col-statut',
        rendu: (l) => UI.html`${badgesStatut(l.controle, l.etat)}<small class="controles-sous-ligne">${l.etat.raison}</small>
          ${l.suivi ? '' : UI.html`<small class="controles-sous-ligne">${I18n.t('controles.colonnes_liste.equipement_inactif_rebut')}</small>`}` },
      { cle: 'prochaine', libelle: I18n.t('controles.colonnes_liste.prochain'), classe: 'sans-coupure', valeurTri: (l) => l.etat.prochaine,
        rendu: (l) => (l.etat.prochaine ? UI.dateFr(l.etat.prochaine) : 'inconnue') },
      { cle: 'derniere', libelle: I18n.t('controles.colonnes_liste.dernier'), classe: 'sans-coupure', valeurTri: (l) => dateIso(l.controle.derniere_date),
        rendu: (l) => UI.dateFr(l.controle.derniere_date) },
      { cle: 'organisme', libelle: I18n.t('controles.colonnes_liste.organisme'), valeurTri: (l) => l.controle.organisme, classe: 'controles-col-organisme',
        rendu: (l) => l.controle.organisme },
    ];
  }

  function carteListe(l) {
    return UI.html`<a class="controles-lien" href="#/controles/${encodeURIComponent(l.controle.id)}">
      <div class="carte-tete"><b>${repere(l.controle)}</b>${badgesStatut(l.controle, l.etat)}</div>
      <div class="carte-titre">${l.controle.nature || l.controle.id}</div>
      <div class="carte-meta"><span>${l.etat.raison}</span>${l.controle.organisme ? UI.html`<span>${l.controle.organisme}</span>` : ''}</div></a>`;
  }

  function afficherListe(conteneur, parametres) {
    const filtres = filtresDepuis((parametres && parametres.requete) || new URLSearchParams());
    const jour = Donnees.aujourdhui();
    const lignes = lignesDeLaListe(jour);
    const ids30j = new Set(sous30Jours(jour).map((controle) => controle.id));
    const equipement = filtres.equipement ? Donnees.trouver('equipements', filtres.equipement) : null;
    const responsable = App.estResponsable();
    UI.remplir(conteneur, UI.html`
      <div class="controles">
        <div class="entete-page">
          <div><h1>${I18n.t('controles.liste.controles_reglementaires')}</h1>
            <p>${I18n.t('controles.liste.verifications_imposees_reglementation_vgp')}</p></div>
          <div class="actions">${responsable ? UI.html`<a class="btn btn-primaire" id="controles-nouveau"
            href="#/controles/nouveau${filtres.equipement ? '?equipement=' + encodeURIComponent(filtres.equipement) : ''}">${UI.icone('ajouter')}${I18n.t('controles.liste.ajouter_controle')}</a>` : ''}</div>
        </div>
        ${responsable ? '' : UI.html`<p class="note controles-consultation">${I18n.t('controles.liste.consultation_seul_responsable_enregistre')}</p>`}
        ${filtres.equipement ? UI.html`<div class="alertes"><div class="alerte" role="status">${UI.icone('parc')}<div class="alerte-texte">
          ${I18n.html('controles.liste.controles_equipement_voir_tous', { equipement: equipement ? libelleEquipement({ equipement_id: filtres.equipement }) : filtres.equipement })}</div></div></div>` : ''}
        ${instrumentsHtml(lignes, filtres)}
        <form class="filtres controles-filtres" id="controles-filtres" data-hors-saisie role="search" aria-label="${I18n.t('controles.liste.filtrer_controles')}">
          <label class="visuellement-cache" for="controles-recherche">${I18n.t('controles.liste.rechercher_controle')}</label>
          <input type="search" id="controles-recherche" name="recherche" value="${filtres.recherche}" placeholder="${I18n.t('controles.liste.equipement_nature_organisme')}" autocomplete="off">
          <label class="visuellement-cache" for="controles-statut">${I18n.t('commun.champ.statut')}</label>
          <select id="controles-statut" name="statut">${optionsStatut().map((option) => UI.html`<option value="${option.valeur}"${option.valeur === filtres.statut ? UI.brut(' selected') : ''}>${option.libelle}</option>`)}</select>
          ${filtres.equipement ? '' : UI.html`<label class="case controles-case"><input type="checkbox" name="inactifs" value="1"${filtres.inactifs ? UI.brut(' checked') : ''}><span>${I18n.t('controles.liste.equipements_inactifs_rebut')}</span></label>`}
        </form>
        <p class="note controles-compteur" role="status"></p>
        <div class="carte controles-liste"></div>
      </div>`);
    const zone = UI.$('.controles-liste', conteneur);
    const compteur = UI.$('.controles-compteur', conteneur);
    const formulaire = UI.$('#controles-filtres', conteneur);

    function rafraichir() {
      const gardees = lignes.filter((ligne) => garder(ligne, filtres, ids30j));
      if (UI.estTelephone()) {
        UI.remplir(zone, gardees.length ? UI.html`<ul class="liste-cartes">${gardees.map((l) => UI.html`<li>${carteListe(l)}</li>`)}</ul>`
          : UI.html`<p class="muted">${I18n.t('controles.liste.aucun_controle_correspond_filtres')}</p>`);
      } else {
        UI.remplir(zone, UI.tableau({ colonnes: colonnesListe(), lignes: gardees, libelle: I18n.t('controles.liste.controles_reglementaires'),
          vide: I18n.t('controles.liste.aucun_controle_correspond_filtres') }));
      }
      const total = lignes.filter((ligne) => dansLaBase(ligne, Object.assign({}, filtres, { inactifs: true }))).length;
      compteur.textContent = filtres.statut === FILTRE_30J
        ? I18n.t('controles.liste.compteur_30_jours', { n: gardees.length, total })
        : I18n.t('controles.liste.compteur', { n: gardees.length, total });
    }
    function lireFiltres() {
      const valeurs = UI.lireFormulaire(formulaire);
      Object.assign(filtres, { recherche: valeurs.recherche || '', statut: valeurs.statut || '', inactifs: valeurs.inactifs === '1' });
      try { history.replaceState(history.state, '', adresseDesFiltres(filtres)); } catch (erreur) { /* adresse gardée */ }
      UI.$('.controles-instruments', conteneur).replaceWith(UI.element(instrumentsHtml(lignes, filtres)));
      rafraichir();
    }
    formulaire.addEventListener('input', lireFiltres);
    formulaire.addEventListener('change', lireFiltres);
    formulaire.addEventListener('submit', (evenement) => evenement.preventDefault());
    rafraichir();
  }

  // ===========================================================================================
  // 10. Formulaire d'un contrôle : création (#/controles/nouveau) et modification (fiche)
  // ===========================================================================================

  function formulaireControle(controle, equipementPropose) {
    const formulaire = UI.element(UI.html`<form class="form-grille" id="form-controle" novalidate>
      <div class="champ large" data-champ="equipement_id"><span class="libelle">${I18n.t('commun.champ.equipement')} <span class="requis" aria-hidden="true">*</span></span>
        <div class="controles-selecteur"></div><p class="erreur-champ" role="alert" hidden></p></div></form>`);
    const valeur = (nom) => (controle ? controle[nom] : undefined);
    const ajouter = (bloc, large) => { if (large) bloc.classList.add('large'); formulaire.appendChild(bloc); return bloc; };
    ajouter(UI.champ(definitionChamp('nature', { obligatoire: true }), valeur('nature'),
      { placeholder: I18n.t('controles.formulaire_controle.ex_verification_generale_periodique'), attributs: { maxlength: '160' } }), true);
    ajouter(UI.champ(definitionChamp('texte_reference'), valeur('texte_reference'), { placeholder: I18n.t('controles.formulaire_controle.ex_arrete_1_er') }), true);
    ajouter(UI.champ(definitionChamp('periodicite_mois', { obligatoire: true }), valeur('periodicite_mois'), { aide: I18n.t('controles.formulaire_controle.nombre_entier_mois_entre') }));
    ajouter(UI.champ(definitionChamp('organisme'), valeur('organisme')));
    ajouter(UI.champ(definitionChamp('derniere_date'), valeur('derniere_date'),
      { aide: controle ? I18n.t('controles.formulaire_controle.correction_seulement_nouveau_controle') : I18n.t('controles.formulaire_controle.facultatif_date_dernier_controle') }));
    ajouter(UI.champ(definitionChamp('prochaine_date'), valeur('prochaine_date'), { aide: I18n.t('controles.formulaire_controle.vide_calculee_dernier_controle') }));
    formulaire.appendChild(UI.element(UI.html`<p class="mention-requis large"><span class="requis" aria-hidden="true">*</span>${I18n.t('commun.message.champ_obligatoire')}</p>`)).classList.add('large');
    formulaire.appendChild(UI.element(UI.html`<div class="actions">
      <button type="submit" class="btn btn-primaire">${UI.icone('valider')}${I18n.t('commun.bouton.enregistrer')}</button>
      ${controle ? '' : UI.html`<a class="btn btn-fantome" href="#/controles">${I18n.t('commun.bouton.annuler')}</a>`}</div>`));
    const selecteur = UI.selecteurEquipement(UI.$('.controles-selecteur', formulaire), {
      equipements: Donnees.lignes('equipements'), localisations: Donnees.lignes('localisations'),
      valeur: controle ? controle.equipement_id : (equipementPropose || ''),
    });
    formulaire.addEventListener('submit', (evenement) => { evenement.preventDefault(); enregistrerControle(formulaire, controle, selecteur); });
    return formulaire;
  }

  async function enregistrerControle(formulaire, controle, selecteur) {
    const bouton = UI.$('button[type=submit]', formulaire);
    if (bouton.disabled) return;
    const valeurs = UI.lireFormulaire(formulaire);
    valeurs.equipement_id = selecteur.valeur() || (controle ? controle.equipement_id : '');
    const erreurs = UI.verifierFormulaire(formulaire);
    Controles.verifierControle(valeurs).filter((erreur) => !erreurs.some((e) => e.nom === erreur.nom)).forEach((erreur) => erreurs.push(erreur));
    afficherErreurs(formulaire, erreurs);
    if (erreurs.length) return;
    bouton.disabled = true;
    bouton.setAttribute('aria-busy', 'true');
    try {
      if (controle) {
        const changes = await Controles.modifierControle(controle.id, valeurs);
        App.marquerSaisie(false);
        UI.toast(changes.length ? I18n.t('controles.enregistrer_controle.controle_enregistre') : I18n.t('commun.message.aucune_modification'), 'succes');
        await App.reafficher();
        return;
      }
      const id = await Controles.creerControle(valeurs);
      App.marquerSaisie(false);
      UI.toast(I18n.t('controles.enregistrer_controle.controle_cree'), 'succes');
      App.naviguer('#/controles/' + encodeURIComponent(id));
    } catch (erreur) {
      App.signalerErreur(erreur, 'enregistrement du contrôle');
    } finally {
      bouton.disabled = false;
      bouton.removeAttribute('aria-busy');
    }
  }

  function afficherNouveau(conteneur, parametres) {
    const requete = (parametres && parametres.requete) || new URLSearchParams();
    App.definirTitre(I18n.t('controles.nouveau.nouveau_controle'));
    UI.remplir(conteneur, UI.html`<div class="controles">
      <div class="entete-page"><div><div class="fil">${I18n.html('controles.nouveau.controles_nouveau_controle')}</div>
        <h1>${I18n.t('controles.nouveau.nouveau_controle_reglementaire')}</h1>
        <p>${I18n.t('controles.nouveau.controle_periodique_impose_texte')}</p></div></div>
      <article class="carte controles-zone-formulaire"></article></div>`);
    UI.$('.controles-zone-formulaire', conteneur).appendChild(formulaireControle(null, requete.get('equipement')));
  }

  // ===========================================================================================
  // 11. Fiche #/controles/<id> : contrôle réalisé, levée des observations, OT, historique
  // ===========================================================================================

  function champFichierRapport() {
    const id = UI.identifiantUnique('controle-rapport-fichier');
    return UI.element(UI.html`<div class="champ" data-champ="rapport_fichier">
      <label class="libelle" for="${id}">${I18n.t('controles.champ_fichier_rapport.rapport_pdf_photo')}</label>
      <input type="file" id="${id}" name="rapport_fichier" accept=".${EXTENSIONS_RAPPORT.join(',.')}" aria-describedby="${id}-aide ${id}-erreur">
      <p class="aide" id="${id}-aide">${I18n.t('controles.champ_fichier_rapport.facultatif_mais_conseille_9')}</p>
      <p class="erreur-champ" id="${id}-erreur" role="alert" hidden></p></div>`);
  }

  async function ouvrirRealisation(controle) {
    const jour = Donnees.aujourdhui();
    const champDate = UI.champ({ nom: 'date', type: 'date', libelle: I18n.t('controles.ouvrir_realisation.date_controle') }, jour, { obligatoire: true, attributs: { max: jour } });
    const fichier = champFichierRapport();
    const fait = await UI.fenetreAction({ classe: 'controles-fenetre',
      titre: I18n.t('controles.ouvrir_realisation.enregistrer_controle_realise'),
      introduction: UI.html`<p>${I18n.t('controles.ouvrir_realisation.prochaine_date_sera_calculee', { nature: controle.nature, libelleEquipement: libelleEquipement(controle), n: controle.periodicite_mois || '?' })}</p>`,
      champs: [champDate, UI.champ(definitionChamp('organisme'), controle.organisme), fichier,
        UI.champ(definitionChamp('observations'), '', { aide: I18n.t('controles.ouvrir_realisation.vide_aucune_observation_sinon') })],
      libelleValider: I18n.t('commun.bouton.enregistrer'),
      verifier(valeurs) {
        const erreurs = verifierRealisation(Donnees.trouver('controles_reglementaires', controle.id) || controle, valeurs);
        const message = verifierFichierRapport(UI.$('input[type=file]', fichier).files[0]);
        if (message) erreurs.push({ nom: 'rapport_fichier', message });
        return erreurs;
      },
      async action(valeurs) {
        const document = UI.$('input[type=file]', fichier).files[0];
        const rapport = document ? await Controles.ecrireRapport(controle.id, valeurs.date, document) : '';
        await Controles.enregistrerRealisation(controle.id, Object.assign({}, valeurs, { rapport }));
      },
    });
    if (fait) await apresEcriture(I18n.t('controles.ouvrir_realisation.controle_realise_enregistre'));
  }

  async function ouvrirLevee(controle) {
    const jour = Donnees.aujourdhui();
    const fait = await UI.fenetreAction({ classe: 'controles-fenetre',
      titre: I18n.t('controles.ouvrir_levee.lever_observations'),
      introduction: UI.html`<div class="encadre attention">${I18n.html('controles.ouvrir_levee.observations_controle', { derniere_date: UI.dateFr(controle.derniere_date), observations: controle.observations })}</div>`,
      champs: [UI.champ({ nom: 'date', type: 'date', libelle: I18n.t('controles.ouvrir_levee.levees') }, jour, { obligatoire: true, attributs: { max: jour } }),
        UI.champ({ nom: 'commentaire', type: 'texte_long', libelle: I18n.t('controles.ouvrir_levee.ete_fait') }, '', { obligatoire: true, placeholder: I18n.t('controles.ouvrir_levee.ex_purgeur_remplace_12') })],
      libelleValider: I18n.t('controles.ouvrir_levee.lever_observations'),
      verifier: (valeurs) => verifierLevee(Donnees.trouver('controles_reglementaires', controle.id) || controle, valeurs),
      action: (valeurs) => Controles.leverObservations(controle.id, valeurs),
    });
    if (fait) await apresEcriture(I18n.t('controles.ouvrir_levee.observations_levees'));
  }

  async function apresEcriture(message) {
    App.marquerSaisie(false);
    UI.toast(message, 'succes');
    await App.reafficher();
  }

  async function adresseDocument(nom) {
    if (!nom || !App.adaptateur) return null;
    try {
      return await App.adaptateur.urlDocument(nom);
    } catch (erreur) {
      console.warn('Prévo : rapport « ' + nom + ' » illisible (' + (erreur && erreur.message) + ').', erreur);
      return null;
    }
  }

  function carteDernierControle(controle, adresseRapport) {
    let rapport = UI.html`<span class="muted">${I18n.t('controles.carte_dernier_controle.aucun_rapport_joint')}</span>`;
    if (controle.rapport) {
      rapport = adresseRapport
        ? UI.html`<a id="controle-rapport" href="${adresseRapport}" target="_blank" rel="noopener">${UI.icone('document')} ${controle.rapport}</a>`
        : UI.html`${I18n.html('controles.carte_dernier_controle.fichier_introuvable', { rapport: controle.rapport })}`;
    }
    let observations = UI.html`<span class="muted">${I18n.t('controles.carte_dernier_controle.aucune_observation')}</span>`;
    if (texte(controle.observations)) {
      observations = UI.html`<span class="controles-observations">${controle.observations}</span>
        ${observationsALever(controle) ? UI.badgeStatut(I18n.t('controles.carte_dernier_controle.lever'), 'attention') : UI.badgeStatut(I18n.t('controles.carte_dernier_controle.levees'), 'ok')}`;
    }
    return UI.html`<article class="carte"><h2>${I18n.t('controles.carte_dernier_controle.dernier_controle')}</h2><dl class="valeurs">
      <dt>${I18n.t('commun.champ.date')}</dt><dd>${controle.derniere_date ? UI.dateFr(controle.derniere_date) : I18n.t('controles.carte_dernier_controle.non_renseignee')}</dd>
      <dt>${I18n.t('controles.colonnes_liste.organisme')}</dt><dd>${controle.organisme}</dd>
      <dt>${I18n.t('controles.carte_dernier_controle.rapport')}</dt><dd>${rapport}</dd>
      <dt>${I18n.t('controles.carte_dernier_controle.observations')}</dt><dd>${observations}</dd></dl></article>`;
  }

  function carteDescription(controle, prochaine) {
    return UI.html`<article class="carte"><h2>${I18n.t('controles.colonnes_liste.controle')}</h2><dl class="valeurs">
      <dt>${I18n.t('commun.champ.equipement')}</dt><dd>${lienEquipement(controle)}</dd>
      <dt>${I18n.t('controles.carte_description.nature')}</dt><dd>${controle.nature}</dd>
      <dt>${I18n.t('controles.carte_description.texte_reference')}</dt><dd>${controle.texte_reference}</dd>
      <dt>${I18n.t('controles.carte_description.periodicite')}</dt><dd>${controle.periodicite_mois ? I18n.t('controles.carte_description.periodicite_mois_mois', { n: controle.periodicite_mois }) : ''}</dd>
      <dt>${I18n.t('controles.carte_description.organisme_controle')}</dt><dd>${controle.organisme}</dd>
      <dt>${I18n.t('controles.carte_description.prochain_controle')}</dt><dd>${prochaine ? UI.dateFr(prochaine) : I18n.t('controles.carte_description.date_inconnue')}</dd></dl></article>`;
  }

  function carteOrdres(controle) {
    const ordres = Donnees.lignes('ordres_travail')
      .filter((ot) => ot.equipement_id === controle.equipement_id && ot.type === 'réglementaire')
      .sort((a, b) => texte(b.date_creation).localeCompare(texte(a.date_creation)) || texte(b.id).localeCompare(texte(a.id)));
    return UI.html`<article class="carte controles-ot"><h2>${I18n.html('controles.carte_ordres.ot_reglementaires_equipement', { nbOrdres: ordres.length })}</h2>
      ${ordres.length ? UI.html`<ul class="controles-liens">${ordres.map((ot) => UI.html`<li>
        <a href="#/ot/${encodeURIComponent(ot.id)}">${ot.id}</a> ${UI.badgeStatut(ot.statut)}
        <span class="controles-titre-ot">${ot.titre}</span>
        <span class="muted">${ot.date_prevue ? I18n.t('controles.carte_ordres.prevu_date_prevue', { date_prevue: UI.dateFr(ot.date_prevue) }) : I18n.t('controles.carte_ordres.cree_date_creation', { date_creation: UI.dateFr(ot.date_creation) })}</span></li>`)}</ul>`
        : UI.html`<p class="muted">${I18n.t('controles.carte_ordres.aucun_ot_reglementaire_equipement')}</p>`}
    </article>`;
  }

  function carteHistorique(controle) {
    const entrees = Donnees.lignes('journal')
      .filter((entree) => entree.table === 'controles_reglementaires' && entree.id_ligne === controle.id)
      .sort((a, b) => texte(b.date_heure).localeCompare(texte(a.date_heure)) || texte(b.id).localeCompare(texte(a.id)));
    return UI.html`<article class="carte controles-historique"><h2>${I18n.html('controles.carte_historique.historique_nb_entrees', { nbEntrees: entrees.length })}</h2>
      ${entrees.length ? UI.html`<ol class="controles-journal">${entrees.slice(0, LIMITE_HISTORIQUE).map((entree) => UI.html`<li>
        <span class="controles-quand">${UI.dateHeureFr(entree.date_heure)}</span>
        <span class="controles-action">${entree.action}</span>
        <span class="muted">${[entree.profil, entree.poste].filter(Boolean).join(' · ')}</span></li>`)}</ol>
        ${entrees.length > LIMITE_HISTORIQUE ? UI.html`<p class="note">${I18n.t('controles.carte_historique.plus_recentes_reste_journal', { limite: LIMITE_HISTORIQUE, nbEntrees: entrees.length })}</p>` : ''}`
        : UI.html`<p class="muted">${I18n.t('controles.carte_historique.aucune_modification_enregistree_prevo')}</p>`}
    </article>`;
  }

  function afficherIntrouvable(conteneur, id) {
    App.definirTitre(I18n.t('controles.introuvable.controle_introuvable'));
    UI.remplir(conteneur, UI.html`<div class="controles"><div class="entete-page"><div>
      <div class="fil"><a href="#/controles">${I18n.t('controles.introuvable.controles')}</a></div><h1>${I18n.t('controles.introuvable.controle_introuvable')}</h1></div></div>
      ${UI.vide(I18n.t('controles.introuvable.aucun_controle_porte_identifiant', { id }), I18n.t('commun.message.saisi_sur_autre_poste'), 'controles')}</div>`);
  }

  async function afficherFiche(conteneur, parametres) {
    const id = parametres.id;
    if (!Donnees.trouver('controles_reglementaires', id)) { afficherIntrouvable(conteneur, id); return; }
    const adresseRapport = await adresseDocument(Donnees.trouver('controles_reglementaires', id).rapport);
    // Pendant l'attente, l'utilisateur a pu changer d'écran : on n'écrase pas le nouveau.
    if (decodeURIComponent(location.hash.split('?')[0]) !== '#/controles/' + id) return;
    const controle = Donnees.trouver('controles_reglementaires', id);
    if (!controle) { afficherIntrouvable(conteneur, id); return; }
    const etatCalcule = etat(controle);
    const responsable = App.estResponsable();
    App.definirTitre(repere(controle) ? I18n.t('controles.fiche.repere_controle', { repere: repere(controle) }) : I18n.t('controles.colonnes_liste.controle'));
    UI.remplir(conteneur, UI.html`
      <div class="controles controles-fiche">
        <div class="entete-page">
          <div>
            <div class="fil"><a href="#/controles">${I18n.t('controles.introuvable.controles')}</a> <span aria-hidden="true">›</span> ${lienEquipement(controle)}</div>
            <h1>${controle.nature || controle.id}</h1>
            <p class="controles-badges">${badgesStatut(controle, etatCalcule)} <span class="controles-raison">${etatCalcule.raison}</span></p>
          </div>
          ${responsable ? UI.html`<div class="actions">
            <button type="button" class="btn btn-primaire" id="controle-realise">${UI.icone('valider')}${I18n.t('controles.ouvrir_realisation.enregistrer_controle_realise')}</button>
            ${observationsALever(controle) ? UI.html`<button type="button" class="btn btn-secondaire" id="controle-lever">${UI.icone('controles')}${I18n.t('controles.ouvrir_levee.lever_observations')}</button>` : ''}
            <a class="btn btn-secondaire" id="controle-creer-ot" href="${adresseNouvelOt(controle)}">${UI.icone('ordres')}${I18n.t('controles.fiche.creer_ot')}</a>
          </div>` : ''}
        </div>
        ${observationsALever(controle) ? UI.html`<div class="alertes"><div class="alerte attention" role="status">${UI.icone('alerte')}
          <div class="alerte-texte">${I18n.html('controles.fiche.observations_lever', { observations: controle.observations })}</div></div></div>` : ''}
        <div class="grille controles-grille">
          <div class="c7 controles-zone-controle"></div>
          <div class="c5">${carteDernierControle(controle, adresseRapport)}${carteOrdres(controle)}</div>
        </div>
        ${carteHistorique(controle)}
      </div>`);
    const zone = UI.$('.controles-zone-controle', conteneur);
    if (responsable) {
      const carte = UI.element(UI.html`<article class="carte"><h2>${I18n.t('controles.colonnes_liste.controle')}</h2></article>`);
      carte.appendChild(formulaireControle(controle));
      zone.appendChild(carte);
      UI.$('#controle-realise', conteneur).addEventListener('click', () => ouvrirRealisation(controle));
      const lever = UI.$('#controle-lever', conteneur);
      if (lever) lever.addEventListener('click', () => ouvrirLevee(controle));
    } else {
      UI.remplir(zone, carteDescription(controle, etatCalcule.prochaine));
    }
  }

  // ===========================================================================================
  // 12. Enregistrement des écrans (App est chargé après les modules : on attend la page)
  // ===========================================================================================

  document.addEventListener('DOMContentLoaded', () => {
    const intervenants = ['technicien', 'responsable'];
    App.ecran({
      id: 'controles', route: /^#\/controles$/, get titre() { return I18n.t('controles.liste.controles_reglementaires'); },
      menu: { get libelle() { return I18n.t('controles.introuvable.controles'); }, icone: 'controles', ordre: 37 },
      profils: intervenants,
      tables: ['controles_reglementaires', 'equipements'],
      afficher: afficherListe,
    });
    // Les routes les plus précises d'abord : « nouveau » ne doit pas être pris pour un identifiant.
    App.ecran({
      id: 'controles-nouveau', route: /^#\/controles\/nouveau$/, get titre() { return I18n.t('controles.nouveau.nouveau_controle'); }, parent: 'controles',
      profils: ['responsable'],
      tables: [],
      afficher: afficherNouveau,
    });
    App.ecran({
      id: 'controles-fiche', route: /^#\/controles\/(?!nouveau$)(?<id>[^/?]+)$/, get titre() { return I18n.t('controles.titre.controle_reglementaire'); }, parent: 'controles',
      profils: intervenants,
      tables: ['controles_reglementaires', 'equipements', 'ordres_travail'],
      afficher: afficherFiche,
    });
  });

  return {};
})());
