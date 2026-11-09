'use strict';
// Garanties — formulaires d'une garantie et d'un contrat de prestataire (2.2, lot L4 ; CDC §3.4, D190, CS173).
// Routes (profil responsable seul ; App renvoie le technicien et le demandeur à l'accueil) :
//   #/garanties/garantie/nouvelle (?equipement=EQ-… : équipement pré-rempli)   #/garanties/garantie/<id>/modifier
//   #/garanties/contrat/nouveau                                                #/garanties/contrat/<id>/modifier
// Champs, aides, boutons et messages : conception L4 §2.3 ; préavis en mois (QUESTIONS L4-L6 Q2) ; durée d'une
// reconduction (Q3, avec la reconduction tacite seulement) ; montant annuel facultatif, hors taxes, libellé avec la
// devise réglée (D190, Q9 ; jamais montré au technicien, D126 : il n'ouvre pas ces écrans et le serveur lui cache la
// colonne, T453).
// - équipement d'une garantie : sélecteur d'équipement (UI.selecteurEquipement) ;
// - équipements concernés d'un contrat : sélecteur + « Ajouter », puces retirables ; equipement_ids séparés par « ; » ;
// - fournisseur (prestataire d'un contrat) : liste des fournisseurs, ou « Nouveau fournisseur… », qui ouvre la fenêtre
//   du Magasin (Magasin.interne.ouvrirFournisseur, telle quelle). Cette fenêtre réaffiche l'écran après
//   l'enregistrement : la saisie est gardée dans un brouillon le temps de la fenêtre, puis remise (document joint
//   compris), le nouveau fournisseur choisi ;
// - date limite de résiliation recalculée à la saisie (Garanties.dateLimiteResiliation) et avertissement non bloquant
//   (Garanties.avertissementsContrat) sous le préavis ;
// - erreurs sous les champs AVANT toute écriture (Garanties.verifierGarantie, verifierContrat ; document : type,
//   taille) ; enregistrement par garanties-ecritures.js (le document est écrit avec la ligne), puis la fiche.
// Profil : responsable seul.
// Chargé juste après garanties-ecritures.js et avant garanties-ecrans.js. Complète l'objet Garanties ; une fonction
// d'un fichier chargé plus tard est cherchée au moment de l'appel.

Object.assign(Garanties, (() => {

  // Outils de garanties-regles.js et garanties-ecritures.js.
  const { texte, dateIso, verifierFichierDocument, EXTENSIONS_DOCUMENT } = Garanties.interne;

  // Champ caché du sélecteur d'équipement d'un contrat (l'équipement à ajouter) : jamais enregistré.
  const CHAMP_A_AJOUTER = 'equipement_a_ajouter';
  const ADRESSE_LISTE = '#/garanties';

  // Saisie gardée le temps de la fenêtre « Nouveau fournisseur… » : { adresse, valeurs, fichier, fournisseurs }.
  let brouillon = null;

  // ===========================================================================================
  // 11. Outils communs aux deux formulaires
  // ===========================================================================================

  function definitionChamp(table, nom, remplacement) {
    return Object.assign({}, Schema.champ(table, nom) || { nom, type: 'texte' }, remplacement || {});
  }

  function listeFournisseurs() {
    return Donnees.lignes('fournisseurs').map((f) => ({ valeur: f.id, libelle: f.nom || f.id }))
      .sort((a, b) => UI.comparerTextes(a.libelle, b.libelle));
  }

  /** « CP-01 — Compresseur à vis » ; « équipement introuvable (EQ-0099) » si l'identifiant n'existe plus. */
  function libelleEquipement(equipementId) {
    const equipement = Donnees.trouver('equipements', equipementId);
    if (!equipement) return I18n.t('garanties.formulaire_contrat.equipement_introuvable', { equipementId });
    return (equipement.repere || equipement.id) + (equipement.designation ? ' — ' + equipement.designation : '');
  }

  function magasinDisponible() {
    return typeof Magasin !== 'undefined' && Boolean(Magasin.interne)
      && typeof Magasin.interne.ouvrirFournisseur === 'function';
  }

  /** Liste des fournisseurs (UI.champ) suivie de « Nouveau fournisseur… » (fenêtre du Magasin). */
  function champFournisseur(table, valeur, reglages) {
    const bloc = UI.champ(definitionChamp(table, 'fournisseur_id'), valeur, Object.assign({ liste: listeFournisseurs() }, reglages));
    bloc.classList.add('large');
    if (magasinDisponible()) {
      const liste = UI.$('select', bloc);
      const ligne = UI.element(UI.html`<div class="garanties-ligne-fournisseur"></div>`);
      liste.replaceWith(ligne);
      ligne.appendChild(liste);
      ligne.appendChild(UI.element(UI.html`<button type="button" class="btn btn-secondaire garanties-nouveau-fournisseur">${UI.icone('ajouter')}${I18n.t('garanties.formulaire.nouveau_fournisseur')}</button>`));
    }
    return bloc;
  }

  /** Document joint (PDF, JPEG, PNG) : un fichier, facultatif ; en modification, le nom du document actuel. */
  function champDocument(libelle, actuel) {
    const id = UI.identifiantUnique('garanties-document');
    return UI.element(UI.html`<div class="champ large" data-champ="document">
      <label class="libelle" for="${id}">${libelle}</label>
      <input type="file" id="${id}" name="document_fichier" accept=".${EXTENSIONS_DOCUMENT.join(',.')}" aria-describedby="${id}-aide ${id}-erreur">
      <p class="aide" id="${id}-aide">${texte(actuel) ? I18n.t('garanties.formulaire.document_actuel', { nom: texte(actuel) })
    : I18n.t('garanties.formulaire.document_aide')}</p>
      <p class="erreur-champ" id="${id}-erreur" role="alert" hidden></p></div>`);
  }

  function fichierChoisi(formulaire) {
    const champ = UI.$('input[type=file]', formulaire);
    return (champ && champ.files && champ.files[0]) || null;
  }

  /** Remet le fichier du brouillon dans le champ (navigateurs qui le permettent ; sinon il est à rechoisir). */
  function remettreFichier(formulaire, fichier) {
    const champ = UI.$('input[type=file]', formulaire);
    if (!fichier || !champ || typeof DataTransfer === 'undefined') return;
    try {
      const transfert = new DataTransfer();
      transfert.items.add(fichier);
      champ.files = transfert.files;
    } catch (erreur) {
      console.warn('Prévo : document joint à rechoisir après la fenêtre du fournisseur.', erreur);
    }
  }

  /** Valeurs lues telles quelles (format du fichier ; fichiers et équipement à ajouter ignorés). */
  function lireChamps(formulaire) {
    const valeurs = UI.lireFormulaire(formulaire);
    delete valeurs[CHAMP_A_AJOUTER];
    return valeurs;
  }

  /** Dates saisies à moitié (le navigateur rend une valeur vide) : « illisible » plutôt que « saisissez ». */
  function erreursDatesIllisibles(formulaire) {
    const illisible = (nom) => {
      const champ = formulaire.elements[nom];
      return Boolean(champ && champ.validity && champ.validity.badInput);
    };
    const erreurs = [];
    if (illisible('date_debut')) erreurs.push({ nom: 'date_debut', message: I18n.t('garanties.verifier.debut_illisible') });
    if (illisible('date_fin')) erreurs.push({ nom: 'date_fin', message: I18n.t('garanties.verifier.fin_illisible') });
    return erreurs;
  }

  /**
   * Erreurs à afficher, une par champ, dans cet ordre de priorité : date à moitié saisie ; règles du module
   * (messages de la conception) ; document (type, taille) ; contrôles généraux de UI (nombres lisibles) pour les
   * champs enregistrés.
   */
  function erreursDuFormulaire(formulaire, sorte, valeurs, fichier) {
    const generales = UI.verifierFormulaire(formulaire);
    const erreurs = erreursDatesIllisibles(formulaire);
    const ajouter = (liste) => liste.forEach((erreur) => {
      if (!erreurs.some((e) => e.nom === erreur.nom)) erreurs.push(erreur);
    });
    ajouter(sorte.verifier(valeurs));
    const message = verifierFichierDocument(fichier);
    if (message) ajouter([{ nom: 'document', message }]);
    ajouter(generales.filter((erreur) => erreur.nom in valeurs));
    return erreurs;
  }

  /** Erreurs sous les champs (les anciennes effacées) ; le curseur va au premier champ en erreur. */
  function afficherErreurs(formulaire, erreurs) {
    UI.$$('.champ', formulaire).forEach((bloc) => UI.erreurChamp(formulaire, bloc.dataset.champ, ''));
    erreurs.forEach((erreur) => UI.erreurChamp(formulaire, erreur.nom, erreur.message));
    const premier = UI.$('.champ.en-erreur', formulaire);
    const controle = premier && UI.$$('input:not([type=hidden]), select, textarea', premier)
      .find((element) => !element.closest('[hidden]'));
    if (controle) controle.focus();
  }

  function zoneErreur(formulaire, message) {
    const zone = UI.$('.garanties-erreur-formulaire', formulaire);
    zone.textContent = message || '';
    zone.hidden = !message;
  }

  /** Bas du formulaire : mention des champs obligatoires, refus d'une écriture, boutons. */
  function piedFormulaire(libelleEnregistrer, adresseAnnuler) {
    return UI.element(UI.html`<div class="large garanties-pied">
      <p class="mention-requis"><span class="requis" aria-hidden="true">*</span>${I18n.t('commun.message.champ_obligatoire')}</p>
      <p class="erreur-champ garanties-erreur-formulaire" role="alert" hidden></p>
      <div class="actions">
        <a class="btn btn-fantome" href="${adresseAnnuler}">${I18n.t('commun.bouton.annuler')}</a>
        <button type="submit" class="btn btn-primaire">${UI.icone('valider')}${libelleEnregistrer}</button></div></div>`);
  }

  /** Valeurs de départ : le brouillon (retour de la fenêtre du fournisseur, sur la même adresse) avec le
   *  fournisseur qu'elle vient de créer, sinon null. */
  function repriseDuBrouillon() {
    if (!brouillon || brouillon.adresse !== location.hash) return null;
    const crees = Donnees.lignes('fournisseurs').map((f) => f.id).filter((id) => !brouillon.fournisseurs.includes(id));
    return Object.assign({}, brouillon.valeurs, crees.length ? { fournisseur_id: crees[crees.length - 1] } : {});
  }

  /** « Nouveau fournisseur… » : fenêtre du Magasin ; l'écran réaffiché après l'enregistrement reprend la saisie. */
  async function nouveauFournisseur(formulaire) {
    brouillon = { adresse: location.hash, valeurs: lireChamps(formulaire), fichier: fichierChoisi(formulaire),
      fournisseurs: Donnees.lignes('fournisseurs').map((f) => f.id) };
    try {
      await Magasin.interne.ouvrirFournisseur('');
    } catch (erreur) {
      App.signalerErreur(erreur, 'nouveau fournisseur');
    } finally {
      brouillon = null;
    }
  }

  /** Enregistre (création ou modification) puis ouvre la fiche ; un refus s'affiche dans le formulaire. */
  async function enregistrer(formulaire, sorte, ligne) {
    const bouton = UI.$('button[type=submit]', formulaire);
    if (bouton.disabled) return;
    zoneErreur(formulaire, '');
    const valeurs = sorte.valeurs(formulaire);
    const fichier = fichierChoisi(formulaire);
    const erreurs = erreursDuFormulaire(formulaire, sorte, valeurs, fichier);
    afficherErreurs(formulaire, erreurs);
    if (erreurs.length) return;
    bouton.disabled = true;
    bouton.setAttribute('aria-busy', 'true');
    try {
      let id = ligne ? ligne.id : '';
      let message = sorte.enregistree();
      if (ligne) {
        const changes = await sorte.modifier(ligne.id, valeurs, fichier);
        if (!changes.length) message = I18n.t('commun.message.aucune_modification');
      } else {
        id = await sorte.creer(valeurs, fichier);
      }
      App.marquerSaisie(false);
      UI.toast(message, 'succes');
      App.naviguer(sorte.fiche(id));
    } catch (erreur) {
      if (erreur instanceof Donnees.ErreurValidation) zoneErreur(formulaire, erreur.message);
      else App.signalerErreur(erreur, 'enregistrement : ' + sorte.table);
    } finally {
      bouton.disabled = false;
      bouton.removeAttribute('aria-busy');
    }
  }

  /** Branche l'envoi et « Nouveau fournisseur… » ; remet le document du brouillon. */
  function brancher(formulaire, sorte, ligne, reprise) {
    formulaire.addEventListener('submit', (evenement) => { evenement.preventDefault(); enregistrer(formulaire, sorte, ligne); });
    const bouton = UI.$('.garanties-nouveau-fournisseur', formulaire);
    if (bouton) bouton.addEventListener('click', () => nouveauFournisseur(formulaire));
    if (reprise) {
      remettreFichier(formulaire, brouillon && brouillon.fichier);
      App.marquerSaisie(true);
    }
  }

  /**
   * Page d'un formulaire : en-tête (fil, titre, introduction), puis le formulaire, ou « introuvable » / « retirée ».
   * construire(ligne, reprise) rend le <form>.
   */
  function afficherPage(conteneur, sorte, ligneId, construire) {
    const ligne = ligneId ? Donnees.trouver(sorte.table, ligneId) : null;
    const titre = ligneId ? sorte.titreModifier() : sorte.titreNouveau();
    App.definirTitre(titre);
    const sousTitre = ligne ? I18n.t('garanties.formulaire.ligne_concernee', { libelle: sorte.libelle(ligne), id: ligne.id })
      : sorte.introduction();
    UI.remplir(conteneur, UI.html`<div class="garanties garanties-page-formulaire">
      <div class="entete-page"><div><div class="fil">${I18n.html('garanties.formulaire.fil', { titre })}</div>
        <h1>${titre}</h1>${ligneId && !ligne ? '' : UI.html`<p>${sousTitre}</p>`}</div></div>
      <div class="garanties-zone-formulaire"></div></div>`);
    const zone = UI.$('.garanties-zone-formulaire', conteneur);
    if (ligneId && !ligne) {
      UI.remplir(zone, UI.vide(sorte.titreIntrouvable(), sorte.introuvable(ligneId)));
      return;
    }
    if (ligne && !Garanties.interne.estActif(ligne)) {
      zone.appendChild(UI.bandeau('attention', sorte.retiree(ligne.id)));
      return;
    }
    const carte = UI.element(UI.html`<article class="carte"></article>`);
    const reprise = repriseDuBrouillon();
    const formulaire = construire(ligne, reprise);
    carte.appendChild(formulaire);
    zone.appendChild(carte);
    brancher(formulaire, sorte, ligne, reprise);
  }

  // ===========================================================================================
  // 12. Formulaire d'une garantie
  // ===========================================================================================

  const GARANTIE = {
    table: 'garanties',
    fiche: (id) => '#/garanties/garantie/' + encodeURIComponent(id),
    valeurs: (formulaire) => lireChamps(formulaire),
    verifier: (valeurs) => Garanties.verifierGarantie(valeurs),
    creer: (valeurs, fichier) => Garanties.creerGarantie(valeurs, fichier),
    modifier: (id, valeurs, fichier) => Garanties.modifierGarantie(id, valeurs, fichier),
    libelle: (garantie) => libelleEquipement(garantie.equipement_id),
    titreNouveau: () => I18n.t('garanties.formulaire_garantie.titre_nouvelle'),
    titreModifier: () => I18n.t('garanties.formulaire_garantie.titre_modifier'),
    introduction: () => I18n.t('garanties.formulaire_garantie.introduction'),
    enregistree: () => I18n.t('garanties.formulaire_garantie.enregistree'),
    titreIntrouvable: () => I18n.t('garanties.formulaire_garantie.introuvable'),
    introuvable: (garantieId) => I18n.t('garanties.ligne.garantie_introuvable', { garantieId }),
    retiree: (garantieId) => I18n.t('garanties.ligne.garantie_retiree', { garantieId }),
  };

  /** Annuler : la fiche (modification), l'équipement d'où l'on vient (?equipement=), sinon la liste. */
  function annulerGarantie(garantie, equipementPropose) {
    if (garantie) return GARANTIE.fiche(garantie.id);
    if (equipementPropose && Donnees.trouver('equipements', equipementPropose)) {
      return '#/equipement/' + encodeURIComponent(equipementPropose);
    }
    return ADRESSE_LISTE + '?onglet=garanties';
  }

  function formulaireGarantie(garantie, reprise, equipementPropose) {
    const depart = reprise || garantie || {};
    const valeur = (nom) => (reprise || garantie ? texte(depart[nom]) : undefined);
    const formulaire = UI.element(UI.html`<form class="form-grille garanties-formulaire" id="form-garantie" novalidate>
      <div class="champ large" data-champ="equipement_id"><span class="libelle">${I18n.t('commun.champ.equipement')} <span class="requis" aria-hidden="true">*</span></span>
        <div class="garanties-selecteur"></div><p class="erreur-champ" role="alert" hidden></p></div></form>`);
    const ajouter = (bloc, large) => { if (large) bloc.classList.add('large'); formulaire.appendChild(bloc); return bloc; };
    ajouter(champFournisseur('garanties', valeur('fournisseur_id'), { aide: I18n.t('garanties.formulaire_garantie.fournisseur_aide') }));
    ajouter(UI.champ(definitionChamp('garanties', 'date_debut'), valeur('date_debut')));
    ajouter(UI.champ(definitionChamp('garanties', 'date_fin'), valeur('date_fin'), { obligatoire: true }));
    ajouter(UI.champ(definitionChamp('garanties', 'conditions'), valeur('conditions'),
      { aide: I18n.t('garanties.formulaire_garantie.conditions_aide') }), true);
    ajouter(champDocument(I18n.t('garanties.formulaire_garantie.document'), garantie && garantie.document));
    formulaire.appendChild(piedFormulaire(I18n.t('garanties.formulaire_garantie.enregistrer'), annulerGarantie(garantie, equipementPropose)));
    UI.selecteurEquipement(UI.$('.garanties-selecteur', formulaire), {
      equipements: Donnees.lignes('equipements'), localisations: Donnees.lignes('localisations'),
      valeur: reprise || garantie ? texte(depart.equipement_id) : texte(equipementPropose),
      surChoix: () => App.marquerSaisie(),
    });
    return formulaire;
  }

  function afficherFormulaireGarantie(conteneur, parametres) {
    const reglages = parametres || {};
    const equipementPropose = reglages.requete ? reglages.requete.get('equipement') : '';
    afficherPage(conteneur, GARANTIE, reglages.id || '',
      (garantie, reprise) => formulaireGarantie(garantie, reprise, equipementPropose));
  }

  // ===========================================================================================
  // 13. Formulaire d'un contrat de prestataire
  // ===========================================================================================

  const CONTRAT = {
    table: 'contrats_prestataires',
    fiche: (id) => '#/garanties/contrat/' + encodeURIComponent(id),
    // Sans reconduction tacite, la durée d'une reconduction (champ caché) n'est pas enregistrée : elle garde sa valeur.
    valeurs: (formulaire) => {
      const valeurs = lireChamps(formulaire);
      if (valeurs.reconduction_tacite !== '1') delete valeurs.reconduction_mois;
      return valeurs;
    },
    verifier: (valeurs) => Garanties.verifierContrat(valeurs),
    creer: (valeurs, fichier) => Garanties.creerContrat(valeurs, fichier),
    modifier: (id, valeurs, fichier) => Garanties.modifierContrat(id, valeurs, fichier),
    libelle: (contrat) => texte(contrat.objet),
    titreNouveau: () => I18n.t('garanties.formulaire_contrat.titre_nouveau'),
    titreModifier: () => I18n.t('garanties.formulaire_contrat.titre_modifier'),
    introduction: () => I18n.t('garanties.formulaire_contrat.introduction'),
    enregistree: () => I18n.t('garanties.formulaire_contrat.enregistre'),
    titreIntrouvable: () => I18n.t('garanties.formulaire_contrat.introuvable'),
    introuvable: (contratId) => I18n.t('garanties.ligne.contrat_introuvable', { contratId }),
    retiree: (contratId) => I18n.t('garanties.ligne.contrat_retire', { contratId }),
  };

  /** « Équipements concernés » : puces retirables (champ caché equipement_ids, « ; ») et sélecteur + « Ajouter ». */
  function champEquipements(valeurInitiale) {
    const idLibelle = UI.identifiantUnique('garanties-equipements');
    const bloc = UI.element(UI.html`<div class="champ large garanties-equipements" data-champ="equipement_ids">
      <input type="hidden" name="equipement_ids">
      <span class="libelle" id="${idLibelle}">${definitionChamp('contrats_prestataires', 'equipement_ids').libelle}</span>
      <ul class="garanties-puces" aria-labelledby="${idLibelle}"></ul>
      <div class="garanties-ajout-equipement"><div class="garanties-selecteur"></div>
        <button type="button" class="btn btn-secondaire garanties-ajouter-equipement" disabled>${UI.icone('ajouter')}${I18n.t('commun.bouton.ajouter')}</button></div>
      <p class="aide">${I18n.t('garanties.formulaire_contrat.equipements_aide')}</p>
      <p class="erreur-champ" role="alert" hidden></p></div>`);
    const champ = UI.$('input[name=equipement_ids]', bloc);
    const puces = UI.$('.garanties-puces', bloc);
    const bouton = UI.$('.garanties-ajouter-equipement', bloc);
    let ids = Garanties.equipementsDuContrat({ equipement_ids: valeurInitiale });

    function rendre() {
      champ.value = ids.join(';');
      UI.remplir(puces, UI.html`${ids.map((id) => UI.html`<li class="garanties-puce" data-equipement="${id}"><span>${libelleEquipement(id)}</span>
        <button type="button" class="btn btn-fantome btn-icone" data-retirer="${id}" aria-label="${I18n.t('garanties.formulaire_contrat.retirer_equipement', { equipement: libelleEquipement(id) })}">${UI.icone('fermer')}</button></li>`)}`);
    }
    const selecteur = UI.selecteurEquipement(UI.$('.garanties-selecteur', bloc), {
      equipements: Donnees.lignes('equipements'), localisations: Donnees.lignes('localisations'), nom: CHAMP_A_AJOUTER,
      surChoix: (equipement) => { bouton.disabled = !equipement; },
    });
    bouton.addEventListener('click', () => {
      const id = selecteur.valeur();
      if (!id) return;
      if (!ids.includes(id)) ids.push(id);
      rendre();
      selecteur.vider();
      App.marquerSaisie();
      const recherche = UI.$('input[type=search]', bloc);
      if (recherche) recherche.focus();
    });
    puces.addEventListener('click', (evenement) => {
      const retirer = evenement.target.closest('button[data-retirer]');
      if (!retirer) return;
      ids = ids.filter((id) => id !== retirer.dataset.retirer);
      rendre();
      App.marquerSaisie();
      const recherche = UI.$('input[type=search]', bloc);
      if (recherche && !recherche.closest('[hidden]')) recherche.focus();
    });
    rendre();
    return bloc;
  }

  /** Préavis valable pour le calcul : vide, ou entier ≥ 0 (« 3 », « 03 », « 3.0 »). */
  function preavisLisible(preavis) {
    if (!preavis) return true;
    const lu = Donnees.nombre(preavis);
    return lu !== null && Number.isInteger(lu) && lu >= 0;
  }

  /** Sous le préavis, à chaque saisie : « Date limite de résiliation : 30/09/2026 » et l'avertissement non bloquant. */
  function majDateLimite(formulaire) {
    const zone = UI.$('.garanties-date-limite', formulaire);
    const avertissement = UI.$('.garanties-avertissement', formulaire);
    const valeurs = lireChamps(formulaire);
    const fin = dateIso(valeurs.date_fin);
    const preavis = texte(valeurs.preavis_mois);
    let message = '';
    if (!fin) message = I18n.t('garanties.formulaire_contrat.date_limite_attente');
    else if (preavisLisible(preavis)) {
      const date = UI.dateFr(Garanties.dateLimiteResiliation({ date_fin: fin, preavis_mois: preavis }));
      message = Donnees.nombre(preavis) ? I18n.t('garanties.formulaire_contrat.date_limite', { date })
        : I18n.t('garanties.formulaire_contrat.date_limite_sans_preavis', { date });
    }
    zone.textContent = message;
    zone.hidden = !message;
    const avertissements = preavisLisible(preavis) ? Garanties.avertissementsContrat(valeurs) : [];
    avertissement.textContent = '';
    if (avertissements.length) avertissement.appendChild(UI.bandeau('attention', avertissements.map((a) => a.message).join(' ')));
  }

  /** La durée d'une reconduction ne se montre qu'avec la reconduction tacite. */
  function majReconduction(formulaire) {
    const tacite = UI.$('[name=reconduction_tacite]', formulaire);
    const bloc = UI.$('.champ[data-champ="reconduction_mois"]', formulaire);
    if (tacite && bloc) bloc.hidden = !tacite.checked;
  }

  function formulaireContrat(contrat, reprise) {
    const depart = reprise || contrat || {};
    const valeur = (nom) => (reprise || contrat ? texte(depart[nom]) : undefined);
    const formulaire = UI.element(UI.html`<form class="form-grille garanties-formulaire" id="form-contrat" novalidate></form>`);
    const ajouter = (bloc, large) => { if (large) bloc.classList.add('large'); formulaire.appendChild(bloc); return bloc; };
    const champ = (nom, reglages, remplacement) => UI.champ(definitionChamp('contrats_prestataires', nom, remplacement), valeur(nom), reglages);
    ajouter(champFournisseur('contrats_prestataires', valeur('fournisseur_id'),
      { obligatoire: true, aide: I18n.t('garanties.formulaire_contrat.prestataire_aide') }));
    ajouter(champ('objet', { obligatoire: true, placeholder: I18n.t('garanties.formulaire_contrat.objet_exemple'),
      attributs: { maxlength: '160' } }), true);
    ajouter(champEquipements(valeur('equipement_ids')));
    ajouter(champ('perimetre', { aide: I18n.t('garanties.formulaire_contrat.perimetre_aide') }), true);
    ajouter(champ('date_debut'));
    ajouter(champ('date_fin', { obligatoire: true }, { libelle: I18n.t('garanties.formulaire_contrat.fin') }));
    const preavis = ajouter(champ('preavis_mois', { aide: I18n.t('garanties.formulaire_contrat.preavis_aide') }));
    preavis.appendChild(UI.element(UI.html`<p class="garanties-date-limite" aria-live="polite"></p>`));
    preavis.appendChild(UI.element(UI.html`<div class="garanties-avertissement" aria-live="polite"></div>`));
    ajouter(champ('montant_annuel', { aide: I18n.t('garanties.formulaire_contrat.montant_aide') }));
    ajouter(champ('reconduction_tacite', {}, { libelle: I18n.t('garanties.formulaire_contrat.reconduction_tacite') }), true);
    ajouter(champ('reconduction_mois', { aide: I18n.t('garanties.formulaire_contrat.reconduction_mois_aide') }));
    ajouter(champDocument(I18n.t('garanties.formulaire_contrat.document'), contrat && contrat.document));
    formulaire.appendChild(piedFormulaire(I18n.t('garanties.formulaire_contrat.enregistrer'),
      contrat ? CONTRAT.fiche(contrat.id) : ADRESSE_LISTE + '?onglet=contrats'));
    formulaire.addEventListener('input', () => majDateLimite(formulaire));
    formulaire.addEventListener('change', () => { majDateLimite(formulaire); majReconduction(formulaire); });
    majDateLimite(formulaire);
    majReconduction(formulaire);
    return formulaire;
  }

  function afficherFormulaireContrat(conteneur, parametres) {
    afficherPage(conteneur, CONTRAT, (parametres && parametres.id) || '', formulaireContrat);
  }

  // ===========================================================================================
  // 14. Adresses des formulaires et enregistrement des écrans
  // ===========================================================================================

  /** « Nouvelle garantie », équipement pré-rempli s'il est donné (fiche équipement, T457). */
  function adresseNouvelleGarantie(equipementId) {
    return '#/garanties/garantie/nouvelle' + (texte(equipementId) ? '?equipement=' + encodeURIComponent(texte(equipementId)) : '');
  }

  /** Formulaire de modification d'une garantie (GAR-…) ou d'un contrat (CTP-…). */
  function adresseModification(id) {
    return (texte(id).startsWith('CTP-') ? CONTRAT : GARANTIE).fiche(texte(id)) + '/modifier';
  }

  // App est chargé après les modules : on attend la page. Ces routes passent avant celles des fiches
  // (garanties-ecrans.js, chargé après) : la première qui correspond gagne (ARCHITECTURE.md §14.2).
  document.addEventListener('DOMContentLoaded', () => {
    const tablesGarantie = ['garanties', 'equipements', 'localisations', 'fournisseurs'];
    const tablesContrat = ['contrats_prestataires', 'equipements', 'localisations', 'fournisseurs'];
    App.ecran({
      id: 'garanties-garantie-nouvelle', route: /^#\/garanties\/garantie\/nouvelle$/, parent: 'garanties',
      get titre() { return I18n.t('garanties.formulaire_garantie.titre_nouvelle'); },
      profils: ['responsable'], tables: tablesGarantie, afficher: afficherFormulaireGarantie,
    });
    App.ecran({
      id: 'garanties-garantie-modifier', route: /^#\/garanties\/garantie\/(?<id>[^/?]+)\/modifier$/, parent: 'garanties',
      get titre() { return I18n.t('garanties.formulaire_garantie.titre_modifier'); },
      profils: ['responsable'], tables: tablesGarantie, afficher: afficherFormulaireGarantie,
    });
    App.ecran({
      id: 'garanties-contrat-nouveau', route: /^#\/garanties\/contrat\/nouveau$/, parent: 'garanties',
      get titre() { return I18n.t('garanties.formulaire_contrat.titre_nouveau'); },
      profils: ['responsable'], tables: tablesContrat, afficher: afficherFormulaireContrat,
    });
    App.ecran({
      id: 'garanties-contrat-modifier', route: /^#\/garanties\/contrat\/(?<id>[^/?]+)\/modifier$/, parent: 'garanties',
      get titre() { return I18n.t('garanties.formulaire_contrat.titre_modifier'); },
      profils: ['responsable'], tables: tablesContrat, afficher: afficherFormulaireContrat,
    });
  });

  return { adresseNouvelleGarantie, adresseModification };
})());
