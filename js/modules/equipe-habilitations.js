'use strict';
// Equipe — habilitations à l'écran (2.2, lot L3, CS172, CS175, CS179 ; CONCEPTION-L2-L3 §6.3 ; types d'habilitation de
// window.CatalogueFR, lus par Equipe.typesHabilitation) :
//   1. petits outils ;
//   2. type du catalogue : liste « Type (catalogue Prévo — réglementation française) », encart du type ;
//   3. fenêtres « Ajouter », « Renouveler » et « Corriger » une habilitation (déplacées d'equipe-ecrans.js) : type,
//      intitulé proposé, recyclage pré-rempli, échéance calculée en direct et modifiable, justificatif (et, pour
//      l'autorisation de conduite, « Reprendre le justificatif de : CACES … ») ;
//   4. carte « Habilitations » de la fiche d'un technicien (Equipe.interne.carteHabilitations) : recyclage et nature
//      de la source (NF C 18-510 : « recommandation »), type et provenance, justificatif, rappel du CACES sans
//      autorisation de conduite, phrase D182 ; Equipe.interne.brancherHabilitations relie boutons et liens ;
//   5. carte « Mes habilitations » de l'accueil du technicien (Equipe.carteMesHabilitations, D199, T480) : SES
//      habilitations qui comptent, type du catalogue, échéance et statut, jamais le justificatif (ni nom ni lien).
// Le contenu du catalogue (types, familles, référence, liens, durée en clair, délivré par, titres, mention) reste en
// français dans toutes les langues (CDC §3.2) : ses blocs portent lang="fr" et data-catalogue, comme aux Contrôles.
// Profils : le responsable écrit (Equipe.ajouterHabilitation… refusent tout autre profil) ; le technicien lit. Le lien
// du justificatif est montré au responsable, et au technicien sur SA fiche seulement (Q5) ; en mode serveur avec
// comptes, le serveur ne sert ces documents qu'au responsable (T445, D196) : le technicien voit alors « justificatif
// joint, visible par le responsable », jamais un lien qui échouerait (403).
// Chargé juste après equipe-ecrans.js (dont il reçoit les outils d'écran par Equipe.interne) et avant
// equipe-acces.js. Complète l'objet Equipe.

Object.assign(Equipe, (() => {

  // Outils de equipe-regles.js, equipe-ecritures.js et equipe-ecrans.js.
  const { texte, dateIso, verifierHabilitation, verifierFichierJustificatif, EXTENSIONS_JUSTIFICATIF,
    nomAffiche, statutHtml, habilitationsAvecEtat, definitionChamp, apresEcriture } = Equipe.interne;
  const { STATUTS_HABILITATION } = Equipe;

  const ADRESSE_LIEN = /^https:\/\/[^\s"'<>]+$/;

  // ===========================================================================================
  // 1. Petits outils
  // ===========================================================================================

  const catalogueHtml = (valeur) => UI.html`<span lang="fr" data-catalogue>${valeur}</span>`;
  const libelleMois = (valeur) => I18n.t('equipe.type_habilitation.mois', { n: Number(valeur) });
  const libelleNature = (nature) => Schema.libelleValeur('habilitations', 'nature_source', texte(nature));
  const principeHtml = () => UI.html`<p class="note equipe-principe">${I18n.t('equipe.principe.texte')}</p>`;

  /** « 36 mois » pour un recyclage entier, le texte tel quel sinon (valeur illisible d'un fichier ancien). */
  function dureeRecyclage(valeur) {
    const mois = Number(texte(valeur));
    return Number.isInteger(mois) && mois > 0 ? libelleMois(mois) : texte(valeur);
  }

  /** Intitulés déjà connus (habilitations et équipements) et intitulés proposés par le catalogue (« CACES R489 »). */
  function intitulesConnus() {
    const connus = new Set();
    Donnees.lignes('habilitations').forEach((h) => { if (texte(h.intitule)) connus.add(texte(h.intitule)); });
    Donnees.lignes('equipements').forEach((e) => texte(e.habilitation_requise).split(',').map(texte).filter(Boolean).forEach((i) => connus.add(i)));
    Equipe.typesHabilitation().forEach((type) => { if (Equipe.intitulePropose(type)) connus.add(Equipe.intitulePropose(type)); });
    return Array.from(connus).sort((a, b) => UI.comparerTextes(a, b));
  }

  // ===========================================================================================
  // 2. Type du catalogue : liste et encart (CONCEPTION-L2-L3 §6.3)
  // ===========================================================================================

  /** Types du catalogue groupés par famille, dans l'ordre du catalogue : [{ famille, types }]. */
  function famillesDeTypes() {
    const familles = [];
    Equipe.typesHabilitation().forEach((type) => {
      let groupe = familles.find((g) => g.famille === type.famille);
      if (!groupe) { groupe = { famille: type.famille, types: [] }; familles.push(groupe); }
      groupe.types.push(type);
    });
    return familles;
  }

  /** « H02 · Habilitation électrique – électricien — recyclage 36 mois (recommandation) ». */
  function libelleType(type) {
    const valeurs = Equipe.valeursDepuisType(type);
    return I18n.t('equipe.type_habilitation.option', { ligne: texte(type.id), type: texte(type.type),
      recyclage: valeurs.recyclage_mois ? I18n.t('equipe.type_habilitation.option_recyclage', { duree: libelleMois(valeurs.recyclage_mois) })
        : I18n.t('equipe.type_habilitation.option_sans_recyclage'),
      nature: libelleNature(valeurs.nature_source) });
  }

  /** Liste du type (« Autre (saisie libre) » d'abord et par défaut, puis un groupe par famille) ; null sans catalogue. */
  function blocType(typeInitial) {
    const familles = famillesDeTypes();
    if (!familles.length) return null;
    const id = UI.identifiantUnique('equipe-type');
    const choisi = typeInitial ? typeInitial.id : '';
    return UI.element(UI.html`<div class="champ" data-champ="catalogue_id">
      <label class="libelle" for="${id}">${I18n.t('equipe.type_habilitation.choisir')}</label>
      <select id="${id}" name="catalogue_id" aria-describedby="${id}-aide ${id}-erreur">
        <option value="">${I18n.t('equipe.type_habilitation.saisie_libre')}</option>${familles.map((groupe) => UI.html`
        <optgroup label="${groupe.famille}" data-catalogue>${groupe.types.map((type) => UI.html`
          <option value="${type.id}" data-catalogue="${texte(type.type)}"${type.id === choisi ? UI.brut(' selected') : ''}>${libelleType(type)}</option>`)}</optgroup>`)}
      </select><p class="aide" id="${id}-aide">${I18n.t('equipe.type_habilitation.aide_type')}</p>
      <p class="erreur-champ" id="${id}-erreur" role="alert" hidden></p></div>`);
  }

  /** Liens d'un type (Légifrance, INRS…) : nouvel onglet, sans transmettre la page d'origine (CS177). */
  function liensHtml(type) {
    const liens = (Array.isArray(type.liens) ? type.liens : []).filter((lien) => lien && texte(lien.libelle || lien.url));
    if (!liens.length) return '';
    return UI.html`<ul class="equipe-type-liens">${liens.map((lien) => {
      const libelle = texte(lien.libelle) || texte(lien.url);
      if (!ADRESSE_LIEN.test(texte(lien.url))) return UI.html`<li>${catalogueHtml(libelle)}</li>`;
      return UI.html`<li><a href="${texte(lien.url)}" target="_blank" rel="noopener noreferrer">${catalogueHtml(libelle)}<span
        class="visuellement-cache"> ${I18n.t('equipe.type_habilitation.nouvel_onglet')}</span></a></li>`;
    })}</ul>`;
  }

  /** Texte de Prévo sur l'autorisation de conduite (H14) ou sur un CACES (CS179) ; '' pour un autre type. */
  function texteConduite(type) {
    if (Equipe.estAutorisationDeConduite(type)) return I18n.t('equipe.type_habilitation.autorisation_conduite');
    if (Equipe.estCaces(type)) return I18n.t('equipe.type_habilitation.rappel_caces');
    return '';
  }

  /** Encart du type : source (nature · relu le · réglementation française), référence, liens, durée en clair, délivré
   *  par, mention à confirmer (H03), texte sur l'autorisation de conduite ou le CACES. */
  function encartTypeHtml(type) {
    const valeurs = Equipe.valeursDepuisType(type);
    const relu = dateIso(type.relu_le);
    const source = [libelleNature(valeurs.nature_source),
      relu ? I18n.t('equipe.type_habilitation.relu_le', { date: UI.dateFr(relu) }) : '',
      I18n.t('equipe.type_habilitation.reglementation_francaise')].filter(Boolean).join(' · ');
    const liens = liensHtml(type);
    const conduite = texteConduite(type);
    return UI.html`<dl class="valeurs equipe-type-valeurs">
      <dt>${I18n.t('equipe.type_habilitation.source')}</dt><dd class="equipe-type-source">${source}</dd>
      <dt>${I18n.t('equipe.type_habilitation.reference')}</dt><dd lang="fr" data-catalogue>${texte(type.reference)}</dd>
      ${liens ? UI.html`<dt>${I18n.t('equipe.type_habilitation.liens')}</dt><dd>${liens}</dd>` : ''}
      <dt>${I18n.t('equipe.type_habilitation.duree')}</dt><dd lang="fr" data-catalogue>${texte(type.duree_texte)}</dd>
      <dt>${I18n.t('equipe.type_habilitation.delivre_par')}</dt><dd lang="fr" data-catalogue>${texte(type.delivre_par)}</dd></dl>
      ${texte(type.mention) ? UI.html`<div class="alerte attention equipe-type-mention" role="note">${UI.icone('alerte')}
        <div class="alerte-texte" lang="fr" data-catalogue>${texte(type.mention)}</div></div>` : ''}
      ${conduite ? UI.html`<p class="equipe-conduite"><b>${conduite}</b></p>` : ''}`;
  }

  function afficherEncart(encart, type) {
    encart.hidden = !type;
    UI.remplir(encart, type ? encartTypeHtml(type) : '');
  }

  // ===========================================================================================
  // 3. Fenêtres « Ajouter », « Renouveler », « Corriger » une habilitation
  // ===========================================================================================

  /** Intitulé (obligatoire, intitulés connus proposés) ; aide « Le symbole du titre : … » pour un type d'électricité. */
  function blocIntitule(valeur) {
    const idListe = UI.identifiantUnique('equipe-intitules');
    const bloc = UI.champ(definitionChamp('habilitations', 'intitule', { obligatoire: true }), valeur,
      { placeholder: I18n.t('equipe.champs_habilitation.ex_br_h_0'), attributs: { list: idListe, autocomplete: 'off' } });
    bloc.appendChild(UI.element(UI.html`<datalist id="${idListe}">${intitulesConnus().map((i) => UI.html`<option value="${i}"></option>`)}</datalist>`));
    const saisie = UI.$('[name]', bloc);
    const aide = UI.element(UI.html`<p class="aide equipe-aide-symbole" id="${saisie.id}-symbole" hidden></p>`);
    bloc.insertBefore(aide, UI.$('.erreur-champ', bloc));
    saisie.setAttribute('aria-describedby', aide.id + ' ' + saisie.getAttribute('aria-describedby'));
    return bloc;
  }

  /** « Justificatif (PDF ou photo) » : un fichier, facultatif ; en correction, le nom du justificatif actuel. */
  function blocJustificatif(actuel) {
    const id = UI.identifiantUnique('equipe-justificatif');
    return UI.element(UI.html`<div class="champ" data-champ="justificatif">
      <label class="libelle" for="${id}">${I18n.t('equipe.type_habilitation.justificatif')}</label>
      <input type="file" id="${id}" name="justificatif_fichier" accept=".${EXTENSIONS_JUSTIFICATIF.join(',.')}" aria-describedby="${id}-aide ${id}-erreur">
      <p class="aide" id="${id}-aide">${texte(actuel) ? I18n.t('equipe.type_habilitation.justificatif_actuel', { nom: texte(actuel) })
    : I18n.t('equipe.type_habilitation.justificatif_aide')}</p>
      <p class="erreur-champ" id="${id}-erreur" role="alert" hidden></p></div>`);
  }

  /** « Reprendre le justificatif de : CACES R489 (obtenu le 20/02/2024) » (autorisation de conduite, CS179) : les
   *  CACES du technicien qui ont un justificatif (Equipe.justificatifsReprenables) ; null s'il n'y en a aucun. */
  function blocReprise(technicienId) {
    const reprenables = Equipe.justificatifsReprenables(technicienId);
    if (!reprenables.length) return null;
    const id = UI.identifiantUnique('equipe-reprise');
    return UI.element(UI.html`<div class="champ" data-champ="justificatif_repris" hidden>
      <label class="libelle" for="${id}">${I18n.t('equipe.type_habilitation.reprendre')}</label>
      <select id="${id}" name="justificatif_repris" aria-describedby="${id}-aide ${id}-erreur">
        <option value="">${I18n.t('equipe.type_habilitation.reprendre_aucun')}</option>${reprenables.map((h) => UI.html`
        <option value="${texte(h.justificatif)}">${I18n.t('equipe.type_habilitation.reprendre_option', { intitule: texte(h.intitule), date: UI.dateFr(h.date_obtention) })}</option>`)}
      </select><p class="aide" id="${id}-aide">${I18n.t('equipe.type_habilitation.reprendre_aide')}</p>
      <p class="erreur-champ" id="${id}-erreur" role="alert" hidden></p></div>`);
  }

  /**
   * Champs d'une fenêtre d'habilitation et leur comportement. mode : 'ajout', 'correction' ou 'renouvellement' (le
   * renouvellement reprend intitulé, type et nature de l'ancienne ligne : ni liste du type ni intitulé, l'encart de
   * son type seulement). Choisir un type pré-remplit le recyclage (et l'intitulé, s'il est vide ou encore celui que
   * proposait le type d'avant) ; l'échéance suit obtention + recyclage tant qu'elle n'a pas été tapée à la main (une
   * échéance existante égale au calcul le suit aussi). Rend { champs, valeurs(valeurs), fichier(), reprise(valeurs) }.
   */
  function formulaireHabilitation(mode, technicienId, habilitation) {
    const correction = mode === 'correction';
    const typeInitial = habilitation ? Equipe.typeDe(habilitation) : null;
    const liste = mode === 'renouvellement' ? null : blocType(typeInitial);
    const encart = UI.element(UI.html`<div class="encadre equipe-type-encart" hidden></div>`);
    const intitule = mode === 'renouvellement' ? null : blocIntitule(correction ? habilitation.intitule : '');
    const obtention = UI.champ(definitionChamp('habilitations', 'date_obtention', { obligatoire: true }),
      correction ? habilitation.date_obtention : Donnees.aujourdhui());
    const recyclage = UI.champ(definitionChamp('habilitations', 'recyclage_mois'), habilitation ? texte(habilitation.recyclage_mois) : '');
    const echeance = UI.champ(definitionChamp('habilitations', 'date_echeance'), correction ? habilitation.date_echeance : '',
      { aide: I18n.t('equipe.type_habilitation.aide_echeance') });
    const justificatif = blocJustificatif(correction ? habilitation.justificatif : '');
    const reprise = blocReprise(technicienId);
    const champs = [liste, encart, UI.element(principeHtml()), intitule, obtention, recyclage, echeance, justificatif, reprise]
      .filter(Boolean);

    const saisie = (bloc) => (bloc ? UI.$('[name]', bloc) : null);
    const [champType, champIntitule, champObtention, champRecyclage, champEcheance] =
      [liste, intitule, obtention, recyclage, echeance].map(saisie);
    const aideSymbole = intitule ? UI.$('.equipe-aide-symbole', intitule) : null;
    const proposee = () => Equipe.echeanceProposee(champObtention.value, texte(champRecyclage.value).replace(',', '.'));
    let echeanceAuto = !champEcheance.value || champEcheance.value === proposee();
    let intitulePrecedent = Equipe.intitulePropose(typeInitial);

    const typeChoisi = () => (champType ? Equipe.typeHabilitation(champType.value) : typeInitial);
    function recalculer() {
      if (echeanceAuto) champEcheance.value = proposee();
    }
    function montrerType() {
      const type = typeChoisi();
      afficherEncart(encart, type);
      if (reprise) reprise.hidden = !Equipe.estAutorisationDeConduite(type);
      if (aideSymbole) {
        const titres = type && !Equipe.intitulePropose(type) ? texte(type.titres) : '';
        aideSymbole.hidden = !titres;
        UI.remplir(aideSymbole, titres ? I18n.html('equipe.type_habilitation.aide_symbole', { titres: catalogueHtml(titres) }) : '');
      }
    }
    function choisirType() {
      montrerType();
      const type = typeChoisi();
      if (!type) return;                                 // « Autre » : rien n'est effacé
      const valeurs = Equipe.valeursDepuisType(type);
      champRecyclage.value = valeurs.recyclage_mois === '' ? '' : String(valeurs.recyclage_mois);
      if (champIntitule && (!texte(champIntitule.value) || texte(champIntitule.value) === intitulePrecedent)) champIntitule.value = valeurs.intitule;
      intitulePrecedent = valeurs.intitule;
      recalculer();
    }

    if (champType) champType.addEventListener('change', choisirType);
    [champObtention, champRecyclage].forEach((champ) => ['input', 'change'].forEach((evenement) => champ.addEventListener(evenement, recalculer)));
    ['input', 'change'].forEach((evenement) => champEcheance.addEventListener(evenement, () => { echeanceAuto = !champEcheance.value; }));
    montrerType();
    recalculer();

    /** Valeurs à écrire : dates, recyclage ; intitulé, type et nature de sa source hors renouvellement. */
    function valeursEcrites(valeurs) {
      const ecrites = { date_obtention: valeurs.date_obtention, date_echeance: valeurs.date_echeance, recyclage_mois: valeurs.recyclage_mois };
      if (mode === 'renouvellement') return ecrites;
      ecrites.intitule = valeurs.intitule;
      if (valeurs.catalogue_id === undefined) return ecrites;      // catalogue absent : type laissé tel quel
      const type = Equipe.typeHabilitation(valeurs.catalogue_id);
      ecrites.catalogue_id = type ? type.id : '';
      // Nature de la source : celle du type choisi (gardée en correction si le type ne change pas).
      if (!correction || ecrites.catalogue_id !== texte(habilitation.catalogue_id).toUpperCase()) {
        ecrites.nature_source = type ? texte(type.nature_source) : '';
      }
      return ecrites;
    }
    return {
      champs,
      valeurs: valeursEcrites,
      fichier: () => UI.$('input[type=file]', justificatif).files[0] || null,
      reprise: (valeurs) => (reprise && !reprise.hidden ? texte(valeurs.justificatif_repris) : ''),
    };
  }

  /** Ouvre une fenêtre d'habilitation ; le justificatif (fichier, ou CACES repris) est écrit avant la ligne. */
  async function ouvrirFenetre(mode, technicienId, habilitation, reglages) {
    const formulaire = formulaireHabilitation(mode, technicienId, habilitation);
    const intituleFixe = mode === 'renouvellement' ? { intitule: habilitation.intitule } : {};
    const fait = await UI.fenetreAction({ classe: 'equipe-fenetre equipe-fenetre-habilitation',
      titre: reglages.titre, libelleValider: reglages.libelleValider, introduction: reglages.introduction,
      champs: formulaire.champs,
      verifier(valeurs) {
        const erreurs = verifierHabilitation(Object.assign({}, valeurs, intituleFixe));
        const message = verifierFichierJustificatif(formulaire.fichier());
        if (message) erreurs.push({ nom: 'justificatif', message });
        return erreurs;
      },
      async action(valeurs) {
        const ecrites = formulaire.valeurs(valeurs);
        const fichier = formulaire.fichier();
        if (fichier) {
          ecrites.justificatif = await Equipe.ecrireJustificatif(technicienId, ecrites.intitule || habilitation.intitule,
            ecrites.date_obtention, fichier);
        } else if (formulaire.reprise(valeurs)) {
          ecrites.justificatif = formulaire.reprise(valeurs);
        }
        await reglages.ecrire(ecrites);
      },
    });
    if (fait) await apresEcriture(reglages.message);
  }

  function ouvrirAjout(technicien) {
    return ouvrirFenetre('ajout', technicien.id, null, {
      titre: I18n.t('equipe.ouvrir_ajout.ajouter_habilitation'), libelleValider: I18n.t('commun.bouton.ajouter'),
      introduction: UI.html`<p>${I18n.html('equipe.ouvrir_ajout.habilitation_habilitation_deja_utilisez', { nomAffiche: nomAffiche(technicien) })}</p>`,
      ecrire: (valeurs) => Equipe.ajouterHabilitation(technicien.id, valeurs),
      message: I18n.t('equipe.ouvrir_ajout.habilitation_ajoutee'),
    });
  }

  function ouvrirRenouvellement(habilitation) {
    const echeance = dateIso(habilitation.date_echeance) ? UI.dateFr(habilitation.date_echeance) : I18n.t('equipe.ouvrir_renouvellement.aucune');
    return ouvrirFenetre('renouvellement', habilitation.technicien_id, habilitation, {
      titre: I18n.t('equipe.ouvrir_renouvellement.renouveler_habilitation'), libelleValider: I18n.t('equipe.ouvrir_renouvellement.renouveler'),
      introduction: UI.html`<p>${I18n.html('equipe.ouvrir_renouvellement.echeance_actuelle_nouvelle_ligne', { intitule: habilitation.intitule, echeance })}</p>`,
      ecrire: (valeurs) => Equipe.renouvelerHabilitation(habilitation.id, valeurs),
      message: I18n.t('equipe.ouvrir_renouvellement.habilitation_renouvelee'),
    });
  }

  function ouvrirCorrection(habilitation) {
    return ouvrirFenetre('correction', habilitation.technicien_id, habilitation, {
      titre: I18n.t('equipe.ouvrir_correction.corriger_habilitation'), libelleValider: I18n.t('commun.bouton.enregistrer'),
      introduction: UI.html`<p>${I18n.t('equipe.ouvrir_correction.erreur_saisie_seulement_renouvellement')}</p>`,
      ecrire: (valeurs) => Equipe.modifierHabilitation(habilitation.id, valeurs),
      message: I18n.t('equipe.ouvrir_correction.habilitation_corrigee'),
    });
  }

  // ===========================================================================================
  // 4. Carte « Habilitations » de la fiche d'un technicien
  // ===========================================================================================

  /** 'lien' : le justificatif s'ouvre (responsable ; technicien sur sa propre fiche, hors comptes) ; 'ferme' sinon. */
  function accesJustificatif(technicien) {
    if (App.estResponsable()) return 'lien';
    const profil = App.profil;
    const sienne = Boolean(profil) && profil.type === 'technicien' && texte(profil.technicienId) === texte(technicien.id);
    // Mode serveur avec comptes : document servi au responsable seul (T445) ; un lien échouerait (403).
    return sienne && !(App.mode === 'serveur' && App.comptesExiges()) ? 'lien' : 'ferme';
  }

  /** « Recyclage : 36 mois [recommandation] » (badge de la nature de la source, CS172) ; '' si rien n'est connu. */
  function recyclageHtml(habilitation) {
    const recyclage = texte(habilitation.recyclage_mois);
    const nature = texte(habilitation.nature_source);
    if (!recyclage && !nature) return '';
    return UI.html`<div class="equipe-recyclage">${recyclage ? I18n.t('equipe.carte_habilitations.recyclage', { duree: dureeRecyclage(recyclage) })
      : I18n.t('equipe.carte_habilitations.sans_recyclage')}
      ${nature ? UI.badgeValeur('habilitations', 'nature_source', nature) : ''}</div>`;
  }

  /** « Type : <type> (catalogue Prévo) », et l'écart du recyclage à la durée du type ; rien en saisie libre. */
  function typeHtml(habilitation) {
    const type = Equipe.typeDe(habilitation);
    if (!type) return '';
    const duree = Equipe.recyclageDuType(habilitation);
    let ecart = '';
    if (!duree.egal) {
      ecart = I18n.t(texte(habilitation.recyclage_mois) ? 'equipe.carte_habilitations.recyclage_catalogue'
        : 'equipe.carte_habilitations.recyclage_vide_catalogue', { duree: libelleMois(duree.propose) });
    }
    return UI.html`<div class="equipe-type">${I18n.html('equipe.carte_habilitations.type', { type: catalogueHtml(texte(type.type)) })}
      ${ecart ? UI.html`<small class="equipe-ecart">${ecart}</small>` : ''}</div>`;
  }

  /** « Justificatif : <lien> » (relié par brancherHabilitations), « aucun justificatif » ou « joint, visible par le
   *  responsable ». */
  function justificatifHtml(habilitation, acces) {
    const nom = texte(habilitation.justificatif);
    let valeur = UI.html`<span class="muted">${I18n.t('equipe.carte_habilitations.aucun_justificatif')}</span>`;
    if (nom && acces === 'lien') valeur = UI.html`<span class="equipe-justificatif" data-justificatif="${nom}">${nom}</span>`;
    else if (nom) valeur = UI.html`<span class="equipe-justificatif-ferme">${I18n.t('equipe.carte_habilitations.justificatif_ferme')}</span>`;
    return UI.html`<div class="equipe-justificatif-ligne">${I18n.html('equipe.carte_habilitations.justificatif', { justificatif: valeur })}</div>`;
  }

  function rappelCacesHtml() {
    return UI.html`<div class="alerte attention equipe-rappel-caces" role="note">${UI.icone('alerte')}
      <div class="alerte-texte">${I18n.t('equipe.type_habilitation.rappel_caces')}</div></div>`;
  }

  /** Habilitations qui comptent d'un technicien, avec leur état : les plus urgentes d'abord, puis par intitulé. */
  function parUrgence(technicienId, jour) {
    return habilitationsAvecEtat(technicienId, jour)
      .sort((a, b) => STATUTS_HABILITATION.indexOf(a.etat.statut) - STATUTS_HABILITATION.indexOf(b.etat.statut)
        || UI.comparerTextes(texte(a.habilitation.intitule), texte(b.habilitation.intitule)));
  }

  /** « Obtenue le … · échéance le … » (ou « sans échéance »). */
  function datesHtml(habilitation) {
    return UI.html`<div class="equipe-dates">${dateIso(habilitation.date_echeance)
      ? I18n.t('equipe.habilitations.obtenue_echeance', { obtention: UI.dateFr(habilitation.date_obtention), echeance: UI.dateFr(habilitation.date_echeance) })
      : I18n.t('equipe.habilitations.obtenue_sans_echeance', { obtention: UI.dateFr(habilitation.date_obtention) })}</div>`;
  }

  /** Carte « Habilitations » : les habilitations qui comptent, des plus urgentes aux autres ; phrase D182 en note. */
  function carteHabilitations(technicien, responsable, jour) {
    const liste = parUrgence(technicien.id, jour);
    const sansAutorisation = new Set(Equipe.cacesSansAutorisation(technicien.id, jour).map((h) => h.id));
    const acces = accesJustificatif(technicien);
    return UI.html`<article class="carte equipe-carte-habilitations">
      <div class="entete-carte"><h2>${I18n.html('equipe.carte_habilitations.habilitations_nb_liste', { nbListe: liste.length })}</h2>
        ${responsable ? UI.html`<button type="button" class="btn btn-secondaire" id="equipe-ajouter-habilitation">${UI.icone('ajouter')}${I18n.t('equipe.ouvrir_ajout.ajouter_habilitation')}</button>` : ''}</div>
      ${liste.length ? UI.html`<ul class="equipe-habilitations">${liste.map(({ habilitation, etat }) => UI.html`<li data-habilitation="${habilitation.id}">
        <div class="equipe-tete"><b class="equipe-intitule">${habilitation.intitule}</b>${statutHtml(habilitation, etat)}</div>
        ${datesHtml(habilitation)}
        <div class="equipe-details">${recyclageHtml(habilitation)}${typeHtml(habilitation)}${justificatifHtml(habilitation, acces)}</div>
        ${sansAutorisation.has(habilitation.id) ? rappelCacesHtml() : ''}
        ${responsable ? UI.html`<div class="actions equipe-actions">
          <button type="button" class="btn btn-secondaire" data-action="renouveler" data-habilitation="${habilitation.id}">${UI.icone('actualiser')}${I18n.t('equipe.ouvrir_renouvellement.renouveler')}</button>
          <button type="button" class="btn btn-fantome" data-action="corriger" data-habilitation="${habilitation.id}">${I18n.t('equipe.carte_habilitations.corriger')}</button></div>` : ''}
      </li>`)}</ul>` : UI.html`<p class="muted">${I18n.t('equipe.carte_habilitations.aucune_habilitation_enregistree_technicien')}</p>`}
      ${principeHtml()}
    </article>`;
  }

  /** Liens des justificatifs de la carte (adresse du stockage, nouvel onglet) ; « fichier introuvable » sinon. */
  async function relierJustificatifs(carte) {
    for (const zone of UI.$$('.equipe-justificatif[data-justificatif]', carte)) {
      const nom = zone.dataset.justificatif;
      let adresse = null;
      try {
        adresse = App.adaptateur ? await App.adaptateur.urlDocument(nom) : null;
      } catch (erreur) {
        console.warn('Prévo : justificatif « ' + nom + ' » illisible (' + (erreur && erreur.message) + ').', erreur);
      }
      if (!zone.isConnected) return;                     // l'utilisateur a changé d'écran entre-temps
      UI.remplir(zone, adresse
        ? UI.html`<a class="equipe-justificatif-lien" href="${adresse}" target="_blank" rel="noopener">${UI.icone('document')} ${nom}</a>`
        : I18n.html('equipe.carte_habilitations.fichier_introuvable', { nom }));
      zone.removeAttribute('data-justificatif');
    }
  }

  /** Après l'affichage de la fiche : liens des justificatifs ; boutons Ajouter, Renouveler, Corriger (responsable). */
  function brancherHabilitations(conteneur, technicien, responsable) {
    const carte = UI.$('.equipe-carte-habilitations', conteneur);
    if (!carte) return;
    relierJustificatifs(carte);
    if (!responsable) return;
    UI.$('#equipe-ajouter-habilitation', carte).addEventListener('click', () => ouvrirAjout(technicien));
    UI.$$('button[data-action]', carte).forEach((bouton) => bouton.addEventListener('click', () => {
      const habilitation = Donnees.trouver('habilitations', bouton.dataset.habilitation);
      if (!habilitation) { UI.toast(I18n.t('equipe.fiche.habilitation_existe_plus_actualisez'), 'attention'); return; }
      if (bouton.dataset.action === 'renouveler') ouvrirRenouvellement(habilitation); else ouvrirCorrection(habilitation);
    }));
  }

  // ===========================================================================================
  // 5. Carte « Mes habilitations » de l'accueil du technicien (D199, T480)
  // ===========================================================================================

  /**
   * Carte « Mes habilitations » de l'accueil (Accueil la cherche à l'affichage) : les habilitations qui comptent du
   * technicien donné (celui du profil ou du compte connecté), les plus urgentes d'abord : intitulé, statut (valide,
   * à renouveler, échue, pas encore valable) et son détail, dates, type du catalogue. Jamais le justificatif, ni nom ni
   * lien (D196, D199), ni bouton ; aucune habilitation d'un autre technicien. '' sans technicien lié au profil.
   */
  function carteMesHabilitations(technicienId, jour) {
    const id = texte(technicienId);
    if (!id) return '';
    const liste = parUrgence(id, jour);
    return UI.html`<article class="carte accueil-mes-habilitations" id="accueil-mes-habilitations">
      <div class="entete-carte"><h2>${I18n.t('equipe.mes_habilitations.titre')}</h2><span class="badge ${liste.length ? 'info' : 'neutre'}">${liste.length}</span></div>
      <p class="muted accueil-habilitations-aide">${I18n.t('equipe.mes_habilitations.tenues_par_responsable')}</p>
      ${liste.length ? UI.html`<ul class="equipe-habilitations">${liste.map(({ habilitation, etat }) => {
    const type = Equipe.typeDe(habilitation);
    return UI.html`<li data-habilitation="${habilitation.id}" data-statut="${etat.statut}">
        <div class="equipe-tete"><b class="equipe-intitule">${habilitation.intitule}</b>${statutHtml(habilitation, etat)}</div>
        ${datesHtml(habilitation)}
        ${type ? UI.html`<div class="equipe-details"><div class="equipe-type">${I18n.html('equipe.carte_habilitations.type', { type: catalogueHtml(texte(type.type)) })}</div></div>` : ''}
      </li>`;
  })}</ul>` : UI.html`<p class="muted">${I18n.t('equipe.mes_habilitations.aucune')}</p>`}
      ${principeHtml()}
    </article>`;
  }

  Object.assign(Equipe.interne, { carteHabilitations, brancherHabilitations });

  // carteMesHabilitations : pour l'accueil du technicien (accueil.js).
  return { carteMesHabilitations };
})());
