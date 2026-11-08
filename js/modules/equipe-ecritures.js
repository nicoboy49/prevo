'use strict';
// Equipe (2/3) — écritures des techniciens et des habilitations (ARCHITECTURE.md §15.8 ; brief §6,
// RG8) : création et modification d'un technicien (désactivation par actif = 0, jamais de
// suppression), ajout, correction et renouvellement d'une habilitation, justificatif joint (2.2).
//
// Règles communes à toutes les fonctions de ce fichier :
// - toute écriture passe par Donnees.modifier ; les contrôles sont refaits DANS la fonction de
//   mutation, sur les lignes fraîches qu'elle reçoit (rejouée si un autre poste a écrit entre-temps :
//   deux postes qui ajoutent chacun une habilitation gardent les deux) ;
// - un refus lève Donnees.ErreurValidation (message pour l'utilisateur) ;
// - un renouvellement AJOUTE une ligne de même intitulé : l'ancienne reste telle quelle (historique),
//   et c'est la nouvelle, à l'échéance la plus lointaine, qui compte (Equipe.habilitationsQuiComptent) ;
// - les habilitations (et leurs justificatifs) ne sont écrites que sous le profil responsable (2.2,
//   réponse provisoire n° 2 de QUESTIONS-L2-L6, à confirmer) : ici côté application ; le refus côté
//   serveur est une tâche séparée.
// Complète l'objet Equipe créé par equipe-regles.js.

Object.assign(Equipe, (() => {

  // Outils de equipe-regles.js.
  const { texte, dateIso, cleIntitule, estActif, nomComplet } = Equipe.interne;

  const CHAMPS_TECHNICIEN = ['nom', 'prenom', 'metier', 'taux_horaire', 'capacite_h_semaine', 'actif'];
  const CHAMPS_NOMBRES = ['taux_horaire', 'capacite_h_semaine'];
  // Format 4 (2.2, CS172, CS179) : recyclage, justificatif (nom d'un document déjà écrit par
  // ecrireJustificatif), type du catalogue (H01 à H15) et nature de sa source.
  const CHAMPS_HABILITATION = ['intitule', 'date_obtention', 'date_echeance', 'recyclage_mois', 'justificatif',
    'catalogue_id', 'nature_source'];
  const CAPACITE_MAX_H = 80;                           // heures par semaine (au-delà : faute de frappe)
  const RECYCLAGE_MAX_MOIS = 240;                      // 20 ans : au-delà, c'est une faute de frappe

  // Justificatif joint : PDF ou photo (une photo est réduite en JPEG lisible avant l'envoi), comme le
  // rapport d'un contrôle (Controles.ecrireRapport).
  const EXTENSIONS_JUSTIFICATIF = ['pdf', 'jpg', 'jpeg', 'png', 'webp'];
  const EXTENSIONS_PHOTO = ['jpg', 'jpeg', 'png', 'webp'];
  const TAILLE_MAX_JUSTIFICATIF = 9 * 1024 * 1024;     // le serveur refuse plus de 10 Mo
  const COTE_MAX_PHOTO = 2400;                         // pixels : un titre photographié reste lisible
  const ESSAIS_NOM_JUSTIFICATIF = 9;
  const LONGUEUR_MAX_NOM = 128;                        // règle des noms de documents du serveur

  // ===========================================================================================
  // 3. Petits outils des écritures
  // ===========================================================================================

  function ErreurValidation(message) {
    return new Donnees.ErreurValidation(message);
  }

  function refuserSiErreurs(erreurs) {
    if (erreurs.length) throw ErreurValidation(erreurs.map((erreur) => erreur.message).join(' '));
  }

  /** Nombre saisi au format du fichier (point décimal) ; texte gardé tel quel s'il est illisible. */
  function nombreFichier(valeur) {
    const lu = Donnees.nombre(valeur);
    return lu === null ? texte(valeur) : String(Math.round(lu * 1e6) / 1e6);
  }

  // Habilitations et justificatifs : profil responsable seulement (réponse provisoire n° 2, à confirmer).
  function exigerResponsable() {
    const responsable = typeof App !== 'undefined' && Boolean(App) && typeof App.estResponsable === 'function'
      && App.estResponsable();
    if (!responsable) throw ErreurValidation(I18n.t('equipe.exiger_responsable.seul_responsable_habilitations'));
  }

  // ===========================================================================================
  // 4. Techniciens : création, modification, désactivation
  // ===========================================================================================

  /**
   * Contrôle les valeurs d'un technicien : [{ nom, message }] (vide si tout va bien). Nom
   * obligatoire ; taux horaire ≥ 0 ; capacité de 0 à 80 h par semaine ; pas deux techniciens
   * ACTIFS de même nom et prénom (casse et accents ignorés). idCourant : '' pour une création.
   */
  function verifierTechnicien(valeurs, lignesTechniciens, idCourant) {
    const erreurs = [];
    if (!texte(valeurs.nom)) erreurs.push({ nom: 'nom', message: I18n.t('equipe.verifier_technicien.nom_technicien_obligatoire') });
    const taux = texte(valeurs.taux_horaire);
    if (taux !== '' && (Donnees.nombre(taux) === null || Donnees.nombre(taux) < 0)) {
      erreurs.push({ nom: 'taux_horaire', message: I18n.t('equipe.verifier_technicien.taux_horaire_nombre_euros') });
    }
    const capacite = texte(valeurs.capacite_h_semaine);
    const heures = Donnees.nombre(capacite);
    if (capacite !== '' && (heures === null || heures < 0 || heures > CAPACITE_MAX_H)) {
      erreurs.push({ nom: 'capacite_h_semaine', message: I18n.t('equipe.verifier_technicien.capacite_entre', { n: CAPACITE_MAX_H }) });
    }
    if (texte(valeurs.nom) && texte(valeurs.actif) !== '0') {
      const cle = UI.normaliserRecherche(texte(valeurs.nom) + ' ' + texte(valeurs.prenom));
      const double = (lignesTechniciens || []).find((ligne) => ligne.id !== idCourant && estActif(ligne)
        && UI.normaliserRecherche(texte(ligne.nom) + ' ' + texte(ligne.prenom)) === cle);
      if (double) erreurs.push({ nom: 'nom', message: I18n.t('equipe.verifier_technicien.technicien_actif_porte_deja', { doubleId: double.id }) });
    }
    return erreurs;
  }

  // Valeurs d'un technicien au format du fichier : seuls les champs modifiables.
  function valeursTechnicien(valeurs) {
    const propres = {};
    CHAMPS_TECHNICIEN.forEach((nom) => {
      if (valeurs[nom] === undefined || valeurs[nom] === null) return;
      let valeur = texte(valeurs[nom]);
      if (CHAMPS_NOMBRES.includes(nom) && valeur !== '') valeur = nombreFichier(valeur);
      if (nom === 'actif') valeur = valeur === '0' ? '0' : '1';
      propres[nom] = valeur;
    });
    return propres;
  }

  /** Crée un technicien (actif) ; renvoie son identifiant (TEC-…). */
  async function creerTechnicien(valeurs) {
    const propres = valeursTechnicien(valeurs || {});
    return Donnees.modifier('techniciens', (lignes, outils) => {
      const ligne = Object.assign({ prenom: '', metier: '', taux_horaire: '', capacite_h_semaine: '' }, propres, { actif: '1' });
      refuserSiErreurs(verifierTechnicien(ligne, lignes, ''));
      ligne.id = outils.nouvelId(lignes);
      lignes.push(ligne);
      return ligne.id;
    }, { action: 'création du technicien' });
  }

  /** Modifie un technicien (actif = '0' : désactivation) ; renvoie la liste des champs changés. */
  async function modifierTechnicien(technicienId, valeurs) {
    const propres = valeursTechnicien(valeurs || {});
    let action = 'modification du technicien';
    return Donnees.modifier('techniciens', (lignes) => {
      const ligne = lignes.find((l) => l.id === technicienId);
      if (!ligne) throw ErreurValidation(I18n.t('equipe.modifier_technicien.technicien_introuvable', { technicienId }));
      refuserSiErreurs(verifierTechnicien(Object.assign({}, ligne, propres), lignes, technicienId));
      const changes = Object.keys(propres).filter((nom) => texte(ligne[nom]) !== propres[nom]);
      changes.forEach((nom) => { ligne[nom] = propres[nom]; });
      if (changes.includes('actif')) action = propres.actif === '0' ? 'désactivation du technicien' : 'réactivation du technicien';
      return changes;
      // Donnees.modifier lit `action` APRÈS la mutation : le « get » rend le texte décidé sur les lignes fraîches.
    }, { get action() { return action; } });
  }

  // ===========================================================================================
  // 5. Habilitations : ajout, correction, renouvellement
  // ===========================================================================================

  /** Vrai si le recyclage est vide ou un nombre entier de mois de 1 à 240. */
  function recyclageAdmis(valeur) {
    const brute = texte(valeur);
    if (!brute) return true;
    const mois = Donnees.nombre(brute);
    return mois !== null && Number.isInteger(mois) && mois >= 1 && mois <= RECYCLAGE_MAX_MOIS;
  }

  /**
   * Contrôle les valeurs d'une habilitation : intitulé, obtention obligatoires ; échéance ≥ obtention ;
   * recyclage (facultatif) entier de 1 à 240 mois.
   */
  function verifierHabilitation(valeurs) {
    const erreurs = [];
    if (!texte(valeurs.intitule)) erreurs.push({ nom: 'intitule', message: I18n.t('equipe.verifier_habilitation.intitule_obligatoire_ex_br') });
    const obtention = texte(valeurs.date_obtention);
    const echeance = texte(valeurs.date_echeance);
    if (!obtention) erreurs.push({ nom: 'date_obtention', message: I18n.t('equipe.verifier_habilitation.date_obtention_obligatoire') });
    else if (!dateIso(obtention)) erreurs.push({ nom: 'date_obtention', message: I18n.t('equipe.verifier_habilitation.date_obtention_illisible_format') });
    if (echeance && !dateIso(echeance)) erreurs.push({ nom: 'date_echeance', message: I18n.t('equipe.verifier_habilitation.date_echeance_illisible_format') });
    else if (echeance && dateIso(obtention) && echeance < obtention) {
      erreurs.push({ nom: 'date_echeance', message: I18n.t('equipe.verifier_habilitation.echeance_peut_pas_preceder', { obtention: UI.dateFr(obtention) }) });
    }
    if (!recyclageAdmis(valeurs.recyclage_mois)) {
      erreurs.push({ nom: 'recyclage_mois', message: I18n.t('equipe.verifier_habilitation.recyclage_nombre_entier_mois', { maximum: RECYCLAGE_MAX_MOIS }) });
    }
    return erreurs;
  }

  function naturesSource() {
    const champ = Schema.champ('habilitations', 'nature_source');
    return (champ && champ.valeurs) || [];
  }

  /**
   * Valeurs d'une habilitation au format du fichier : seuls les champs connus, sans espaces de bord.
   * Recyclage entier écrit sans zéros ni décimales (« 036 », « 36,0 » → « 36 » ; un autre texte est
   * gardé, puis refusé par verifierHabilitation) ; type du catalogue inconnu (ou catalogue absent) et
   * nature de la source hors de la liste ramenés à vide.
   */
  function valeursHabilitation(valeurs) {
    const propres = {};
    CHAMPS_HABILITATION.forEach((nom) => {
      if (valeurs[nom] !== undefined && valeurs[nom] !== null) propres[nom] = texte(valeurs[nom]);
    });
    if (propres.recyclage_mois !== undefined) {
      const mois = Donnees.nombre(propres.recyclage_mois);
      if (mois !== null && Number.isInteger(mois)) propres.recyclage_mois = String(mois);
    }
    if (propres.catalogue_id !== undefined) {
      const type = Equipe.typeHabilitation(propres.catalogue_id);
      propres.catalogue_id = type ? type.id : '';
    }
    if (propres.nature_source !== undefined) {
      const nature = propres.nature_source.toLowerCase();
      propres.nature_source = naturesSource().includes(nature) ? nature : '';
    }
    return propres;
  }

  /** Échéance vide et recyclage connu : échéance = obtention + recyclage ; une échéance saisie est gardée. */
  function completerEcheance(ligne) {
    if (!texte(ligne.date_echeance) && texte(ligne.recyclage_mois)) {
      const proposee = Equipe.echeanceProposee(ligne.date_obtention, ligne.recyclage_mois);
      if (proposee) ligne.date_echeance = proposee;
    }
    return ligne;
  }

  function technicienExistant(technicienId) {
    const technicien = Donnees.trouver('techniciens', texte(technicienId));
    const nom = texte(technicienId) || I18n.t('equipe.technicien_existant.non_choisi');
    if (!technicien) throw ErreurValidation(I18n.t('equipe.technicien_existant.technicien_introuvable', { nom }));
    return technicien;
  }

  /** Lignes du même technicien et du même intitulé (casse et espaces ignorés). */
  function memeHabilitation(lignes, technicienId, intitule) {
    return lignes.filter((ligne) => ligne.technicien_id === technicienId && cleIntitule(ligne.intitule) === cleIntitule(intitule));
  }

  /**
   * Ajoute une habilitation à un technicien ; renvoie son identifiant (HAB-…). Échéance vide et
   * recyclage connu : échéance = obtention + recyclage. Refus si le technicien a déjà cet
   * intitulé : c'est alors un renouvellement (ou une correction).
   */
  async function ajouterHabilitation(technicienId, valeurs) {
    exigerResponsable();
    const technicien = technicienExistant(technicienId);
    const propres = valeursHabilitation(valeurs || {});
    return Donnees.modifier('habilitations', (lignes, outils) => {
      const nouvelle = completerEcheance(Object.assign({ intitule: '', date_obtention: '', date_echeance: '',
        recyclage_mois: '', justificatif: '', catalogue_id: '', nature_source: '' }, propres));
      refuserSiErreurs(verifierHabilitation(nouvelle));
      if (memeHabilitation(lignes, technicien.id, nouvelle.intitule).length) {
        throw ErreurValidation(I18n.t('equipe.ajouter_habilitation.deja_habilitation_utilisez_renouveler', { nomComplet: nomComplet(technicien), intitule: nouvelle.intitule }));
      }
      const id = outils.nouvelId(lignes);
      lignes.push(Object.assign({ id, technicien_id: technicien.id }, nouvelle));
      return id;
    }, { action: 'habilitation ' + propres.intitule + ' ajoutée' });
  }

  /**
   * Corrige une habilitation (erreur de saisie) ; renvoie la liste des champs changés. Échéance vide
   * et recyclage connu : échéance recalculée (obtention + recyclage) ; une échéance saisie est gardée.
   */
  async function modifierHabilitation(habilitationId, valeurs) {
    exigerResponsable();
    const propres = valeursHabilitation(valeurs || {});
    return Donnees.modifier('habilitations', (lignes) => {
      const ligne = lignes.find((l) => l.id === habilitationId);
      if (!ligne) throw ErreurValidation(I18n.t('equipe.modifier_habilitation.habilitation_introuvable', { habilitationId }));
      const corrigee = completerEcheance(Object.assign({}, ligne, propres));
      refuserSiErreurs(verifierHabilitation(corrigee));
      if (cleIntitule(corrigee.intitule) !== cleIntitule(ligne.intitule)
          && memeHabilitation(lignes, ligne.technicien_id, corrigee.intitule).length) {
        throw ErreurValidation(I18n.t('equipe.modifier_habilitation.technicien_deja_habilitation', { intitule: corrigee.intitule }));
      }
      const changes = CHAMPS_HABILITATION.filter((nom) => corrigee[nom] !== undefined && texte(ligne[nom]) !== texte(corrigee[nom]));
      changes.forEach((nom) => { ligne[nom] = texte(corrigee[nom]); });
      return changes;
    }, { action: 'correction de l\'habilitation' });
  }

  /**
   * Renouvelle une habilitation : NOUVELLE ligne de même technicien, avec les dates données (l'ancienne
   * ligne reste intacte). Reprend de l'ancienne l'intitulé, le recyclage (sauf s'il est redonné), le
   * type et la nature de la source ; échéance vide et recyclage connu : obtention + recyclage ;
   * justificatif : le nouveau s'il est donné (facultatif), l'ancien reste sur l'ancienne ligne.
   * Refus : échéance avant l'obtention ; nouvelle échéance qui ne dépasse pas l'échéance actuelle
   * (sinon l'ancienne compterait encore) ; habilitation sans échéance (rien à renouveler : la
   * corriger). Renvoie l'identifiant créé.
   */
  async function renouvelerHabilitation(habilitationId, valeurs) {
    exigerResponsable();
    const saisie = valeursHabilitation(valeurs || {});
    let action = 'renouvellement de ' + habilitationId;
    return Donnees.modifier('habilitations', (lignes, outils) => {
      const ancienne = lignes.find((l) => l.id === habilitationId);
      if (!ancienne) throw ErreurValidation(I18n.t('equipe.modifier_habilitation.habilitation_introuvable', { habilitationId }));
      const reprise = valeursHabilitation({ recyclage_mois: ancienne.recyclage_mois || '',
        catalogue_id: ancienne.catalogue_id || '', nature_source: ancienne.nature_source || '' });
      if (!recyclageAdmis(reprise.recyclage_mois)) reprise.recyclage_mois = '';   // illisible : rien à reprendre
      const nouvelle = completerEcheance({
        intitule: texte(ancienne.intitule),
        date_obtention: saisie.date_obtention || '', date_echeance: saisie.date_echeance || '',
        recyclage_mois: saisie.recyclage_mois !== undefined ? saisie.recyclage_mois : reprise.recyclage_mois,
        justificatif: saisie.justificatif || '',
        catalogue_id: reprise.catalogue_id, nature_source: reprise.nature_source,
      });
      refuserSiErreurs(verifierHabilitation(nouvelle));
      const lignesMeme = memeHabilitation(lignes, ancienne.technicien_id, ancienne.intitule);
      if (lignesMeme.some((l) => !texte(l.date_echeance))) {
        throw ErreurValidation(I18n.t('equipe.renouveler_habilitation.habilitation_pas_echeance_rien', { intitule: ancienne.intitule }));
      }
      // Une échéance illisible ne compte pas : le renouvellement la remplace.
      const actuelle = lignesMeme.map((l) => dateIso(l.date_echeance)).filter(Boolean).sort().pop() || '';
      if (nouvelle.date_echeance && actuelle && nouvelle.date_echeance <= actuelle) {
        throw ErreurValidation(I18n.t('equipe.renouveler_habilitation.nouvelle_echeance_doit_depasser', { actuelle: UI.dateFr(actuelle) }));
      }
      const id = outils.nouvelId(lignes);
      lignes.push(Object.assign({ id, technicien_id: ancienne.technicien_id }, nouvelle));
      // Action du journal (D156 : écrite dans les données, jamais traduite).
      action = 'renouvellement de ' + ancienne.id + ' (' + ancienne.intitule + ') : échéance '
        + (actuelle ? UI.dateFr(actuelle) : 'illisible') + ' → ' + (dateIso(nouvelle.date_echeance) ? UI.dateFr(nouvelle.date_echeance) : 'sans échéance');
      return id;
    }, { get action() { return action; } });          // texte lu après la mutation (voir modifierTechnicien)
  }

  // ===========================================================================================
  // 6. Justificatif joint : écriture du document (nom lisible et unique)
  // ===========================================================================================

  function extensionDe(nomFichier) {
    const point = String(nomFichier || '').lastIndexOf('.');
    return point === -1 ? '' : String(nomFichier).slice(point + 1).toLowerCase();
  }

  /** Message d'erreur si le fichier ne peut pas servir de justificatif, sinon ''. */
  function verifierFichierJustificatif(fichier) {
    if (!fichier) return '';
    if (!EXTENSIONS_JUSTIFICATIF.includes(extensionDe(fichier.name))) return I18n.t('equipe.verifier_fichier_justificatif.justificatif_doit_etre_pdf');
    if (fichier.size > TAILLE_MAX_JUSTIFICATIF && !EXTENSIONS_PHOTO.includes(extensionDe(fichier.name))) {
      return I18n.t('commun.message.fichier_trop_volumineux');
    }
    return '';
  }

  /** Morceau d'un nom de document : lettres sans accents, chiffres et « - » (« Autorisation de conduite (employeur) » → « Autorisation-de-conduite-employeur »). */
  function morceauDeNom(valeur) {
    return texte(valeur).normalize('NFD')
      .replace(/[^ -~]+/g, '')                         // hors ASCII imprimable : accents décomposés, etc.
      .replace(/[^A-Za-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  }

  // Le stockage refuse d'écraser un document : « Le document … existe déjà. » (dossier, démo) ou « Un
  // document porte déjà ce nom. » (serveur, 409) ; messages comparés dans la langue de l'écran.
  function documentExisteDeja(erreur, nom) {
    return erreur instanceof Donnees.ErreurStockage
      && [I18n.t('socle.creer.document_existe_deja', { nom }), I18n.t('socle.creer.document_porte_deja_nom')].includes(erreur.message);
  }

  /**
   * Écrit le justificatif d'une habilitation dans les documents et renvoie le nom enregistré (à mettre
   * dans la colonne justificatif) : « habilitation-TEC-0002-CACES-R489-2021-12-02.pdf » (« -2 »,
   * « -3 »… si ce nom existe déjà ; le serveur y ajoute son horodatage devant). Une photo est réduite
   * (JPEG, 2 400 px). Refus (ErreurValidation) : profil, type ou taille. Comme le rapport d'un
   * contrôle, le document est écrit avant la ligne : une ligne refusée ensuite le laisse orphelin.
   */
  async function ecrireJustificatif(technicienId, intitule, date, fichier) {
    exigerResponsable();
    if (!fichier) throw ErreurValidation(I18n.t('equipe.verifier_fichier_justificatif.justificatif_doit_etre_pdf'));
    const message = verifierFichierJustificatif(fichier);
    if (message) throw ErreurValidation(message);
    const photo = EXTENSIONS_PHOTO.includes(extensionDe(fichier.name));
    const contenu = photo ? await UI.redimensionnerPhoto(fichier, COTE_MAX_PHOTO) : fichier;
    const extension = photo ? 'jpg' : extensionDe(fichier.name);
    if (contenu.size > TAILLE_MAX_JUSTIFICATIF) throw ErreurValidation(I18n.t('commun.message.fichier_trop_volumineux'));
    const technicien = morceauDeNom(technicienId) || 'TEC';
    const jour = dateIso(date) || morceauDeNom(date);
    // Place gardée pour « -9 » et l'extension : l'intitulé est raccourci si le nom dépasserait 128 caractères.
    const fixe = ('habilitation-' + technicien + '--' + jour + '-9.' + extension).length;
    const morceau = morceauDeNom(intitule).slice(0, Math.max(0, LONGUEUR_MAX_NOM - fixe)).replace(/-+$/, '');
    const base = ['habilitation', technicien, morceau, jour].filter(Boolean).join('-');
    for (let rang = 1; rang <= ESSAIS_NOM_JUSTIFICATIF; rang += 1) {
      const nom = base + (rang === 1 ? '' : '-' + rang) + '.' + extension;
      try {
        return await App.adaptateur.ecrireDocument(nom, contenu);
      } catch (erreur) {
        if (!documentExisteDeja(erreur, nom)) throw erreur;
      }
    }
    return App.adaptateur.ecrireDocument(UI.nomFichierUnique(base, extension), contenu);
  }

  // Contrôles prêtés aux écrans du module (erreurs affichées sous les champs avant d'écrire).
  Object.assign(Equipe.interne, { verifierHabilitation, verifierFichierJustificatif, CAPACITE_MAX_H, RECYCLAGE_MAX_MOIS,
    EXTENSIONS_JUSTIFICATIF });

  return {
    // écritures (ARCHITECTURE.md §15.8)
    verifierTechnicien, creerTechnicien, modifierTechnicien,
    ajouterHabilitation, modifierHabilitation, renouvelerHabilitation, ecrireJustificatif,
  };
})());
