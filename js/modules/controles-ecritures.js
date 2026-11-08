'use strict';
// Controles (2/3) — écritures des contrôles réglementaires (ARCHITECTURE.md §15.7 ; brief RG9, E10) :
// création, modification, contrôle réalisé (dates recalculées, rapport joint), levée des observations.
//
// Règles communes à toutes les fonctions de ce fichier :
// - toute écriture passe par Donnees.modifier('controles_reglementaires') ; les contrôles sont
//   refaits DANS la fonction de mutation, sur les lignes fraîches qu'elle reçoit (elle est rejouée
//   sur les lignes relues si un autre poste a écrit entre-temps) ;
// - un refus lève Donnees.ErreurValidation (message pour l'utilisateur) ; jamais de suppression ;
// - ce module ne crée JAMAIS d'ordre de travail : « Créer un OT » ouvre le formulaire de l'OT
//   pré-rempli, que le responsable valide lui-même (écran, controles-ecrans.js).
// Complète l'objet Controles créé par controles-regles.js.

Object.assign(Controles, (() => {

  // Outils de controles-regles.js.
  const { texte, dateIso, dateDuJour, periodicite, observationsALever } = Controles.interne;
  const { ajouterMois } = Controles;

  // Champs du formulaire d'un contrôle (création et modification). Le rapport, les observations
  // et leur levée viennent des actions « contrôle réalisé » et « lever les observations ».
  const CHAMPS_CONTROLE = ['equipement_id', 'nature', 'texte_reference', 'periodicite_mois', 'organisme',
    'derniere_date', 'prochaine_date'];
  const PERIODICITE_MAX_MOIS = 240;                       // 20 ans : au-delà, c'est une faute de frappe

  // Rapport joint : PDF ou photo (une photo est réduite en JPEG lisible avant l'envoi).
  const EXTENSIONS_RAPPORT = ['pdf', 'jpg', 'jpeg', 'png', 'webp'];
  const EXTENSIONS_PHOTO = ['jpg', 'jpeg', 'png', 'webp'];
  const TAILLE_MAX_RAPPORT = 9 * 1024 * 1024;             // le serveur refuse plus de 10 Mo
  const COTE_MAX_PHOTO = 2400;                            // pixels : un rapport photographié reste lisible
  const ESSAIS_NOM_RAPPORT = 9;

  // ===========================================================================================
  // 4. Petits outils des écritures
  // ===========================================================================================

  function ErreurValidation(message) {
    return new Donnees.ErreurValidation(message);
  }

  function refuserSiErreurs(erreurs) {
    if (erreurs.length) throw ErreurValidation(erreurs.map((erreur) => erreur.message).join(' '));
  }

  function ligneDuControle(lignes, controleId) {
    const ligne = lignes.find((l) => l.id === controleId);
    if (!ligne) throw ErreurValidation(I18n.t('controles.ligne_du_controle.controle_introuvable', { controleId: (controleId || I18n.t('controles.ligne_du_controle.non_choisi')) }));
    return ligne;
  }

  /** Valeurs d'un contrôle au format du fichier : seuls les champs du formulaire, sans espaces de bord. */
  function valeursControle(valeurs) {
    const propres = {};
    CHAMPS_CONTROLE.forEach((nom) => {
      if (valeurs[nom] === undefined || valeurs[nom] === null) return;
      propres[nom] = texte(valeurs[nom]);
    });
    if (propres.periodicite_mois && /^\d+$/.test(propres.periodicite_mois)) {
      propres.periodicite_mois = String(Number(propres.periodicite_mois));     // « 012 » → « 12 »
    }
    return propres;
  }

  /** Erreur [{ nom, message }] d'un champ date : illisible, ou (si `pasFuture`) après aujourd'hui. */
  function erreursDate(nom, valeur, jour, pasFuture, libelle) {
    if (!texte(valeur)) return [];
    if (!dateIso(valeur) || texte(valeur).length !== 10) return [{ nom, message: I18n.t('controles.erreurs_date.date_illisible_format_aaaa', { libelle }) }];
    if (pasFuture && texte(valeur) > jour) return [{ nom, message: I18n.t('controles.erreurs_date.peut_pas_etre_futur', { libelle }) }];
    return [];
  }

  // ===========================================================================================
  // 5. Création et modification d'un contrôle
  // ===========================================================================================

  /**
   * Contrôle les valeurs d'un contrôle : [{ nom, message }] (vide si tout va bien). Équipement
   * obligatoire et existant ; nature obligatoire ; périodicité entière de 1 à 240 mois ; dernière
   * date ni illisible ni future ; prochaine date (facultative : vide = dernière date + périodicité)
   * après la dernière date. `aujourdhui` : date du jour (par défaut Donnees.aujourdhui()).
   */
  function verifierControle(valeurs, aujourdhui) {
    const erreurs = [];
    const jour = dateDuJour(aujourdhui);
    const equipementId = texte(valeurs.equipement_id);
    if (!equipementId) erreurs.push({ nom: 'equipement_id', message: I18n.t('controles.verifier_controle.choisissez_equipement_controle') });
    else if (!Donnees.trouver('equipements', equipementId)) {
      erreurs.push({ nom: 'equipement_id', message: I18n.t('controles.verifier_controle.equipement_introuvable', { equipementId }) });
    }
    if (!texte(valeurs.nature)) {
      erreurs.push({ nom: 'nature', message: I18n.t('controles.verifier_controle.nature_controle_obligatoire_ex') });
    }
    const brute = texte(valeurs.periodicite_mois);
    const mois = Donnees.nombre(brute);
    if (!brute) erreurs.push({ nom: 'periodicite_mois', message: I18n.t('controles.verifier_controle.periodicite_obligatoire_mois_ex') });
    else if (mois === null || !Number.isInteger(mois) || mois <= 0 || mois > PERIODICITE_MAX_MOIS) {
      erreurs.push({ nom: 'periodicite_mois', message: I18n.t('controles.verifier_controle.periodicite_doit_etre_nombre', { maximum: PERIODICITE_MAX_MOIS }) });
    }
    erreurs.push(...erreursDate('derniere_date', valeurs.derniere_date, jour, true, I18n.t('controles.verifier_controle.date_dernier_controle')));
    erreurs.push(...erreursDate('prochaine_date', valeurs.prochaine_date, jour, false, I18n.t('controles.verifier_controle.date_prochain_controle')));
    const derniere = dateIso(valeurs.derniere_date);
    const prochaine = dateIso(valeurs.prochaine_date);
    if (derniere && prochaine && prochaine <= derniere && !erreurs.some((e) => e.nom === 'prochaine_date')) {
      erreurs.push({ nom: 'prochaine_date', message: I18n.t('controles.verifier_controle.date_prochain_controle_doit', { derniere: UI.dateFr(derniere) }) });
    }
    return erreurs;
  }

  /** Crée un contrôle ; renvoie son identifiant (CTR-…). */
  async function creerControle(valeurs) {
    const propres = valeursControle(valeurs || {});
    return Donnees.modifier('controles_reglementaires', (lignes, outils) => {
      refuserSiErreurs(verifierControle(propres, outils.aujourdhui()));
      const id = outils.nouvelId(lignes);
      lignes.push(Object.assign({}, propres, { id, rapport: '', observations: '', observations_levees: '1' }));
      return id;
    }, { action: 'création du contrôle réglementaire' });
  }

  /** Modifie un contrôle (champs du formulaire) ; renvoie la liste des champs réellement changés. */
  async function modifierControle(controleId, valeurs) {
    const propres = valeursControle(valeurs || {});
    return Donnees.modifier('controles_reglementaires', (lignes, outils) => {
      const ligne = ligneDuControle(lignes, controleId);
      refuserSiErreurs(verifierControle(Object.assign({}, ligne, propres), outils.aujourdhui()));
      const changes = Object.keys(propres).filter((nom) => texte(ligne[nom]) !== propres[nom]);
      changes.forEach((nom) => { ligne[nom] = propres[nom]; });
      return changes;
    }, { action: 'modification du contrôle réglementaire' });
  }

  // ===========================================================================================
  // 6. Contrôle réalisé et levée des observations
  // ===========================================================================================

  /**
   * Contrôle d'un « contrôle réalisé » : [{ nom, message }]. Date obligatoire, ni future ni
   * antérieure au dernier contrôle enregistré ; périodicité connue (pour calculer la suivante).
   */
  function verifierRealisation(controle, valeurs, aujourdhui) {
    const jour = dateDuJour(aujourdhui);
    const date = texte(valeurs.date);
    if (!date) return [{ nom: 'date', message: I18n.t('controles.verifier_realisation.indiquez_date_controle') }];
    const erreurs = erreursDate('date', date, jour, true, I18n.t('controles.verifier_realisation.date_controle'));
    const derniere = dateIso(controle.derniere_date);
    if (!erreurs.length && derniere && date < derniere) {
      erreurs.push({ nom: 'date', message: I18n.t('controles.verifier_realisation.dernier_controle_enregistre_date', { derniere: UI.dateFr(derniere) }) });
    }
    if (periodicite(controle) === null) {
      erreurs.push({ nom: 'date', message: I18n.t('controles.verifier_realisation.periodicite_controle_pas_renseignee') });
    }
    return erreurs;
  }

  /**
   * Enregistre un contrôle réalisé : derniere_date = date, prochaine_date = date + périodicité
   * (même jour, ramené à la fin du mois), organisme (s'il est donné), rapport (nom d'un document
   * déjà écrit par ecrireRapport ; vide si aucun), observations ; observations_levees = '0' s'il y
   * a des observations, sinon '1'. Renvoie { derniere_date, prochaine_date }.
   */
  async function enregistrerRealisation(controleId, valeurs) {
    const saisie = {
      date: texte(valeurs && valeurs.date), organisme: texte(valeurs && valeurs.organisme),
      rapport: texte(valeurs && valeurs.rapport), observations: texte(valeurs && valeurs.observations),
    };
    const action = 'contrôle réalisé le ' + UI.dateFr(saisie.date)
      + (saisie.organisme ? ' par ' + saisie.organisme : '')
      + (saisie.rapport ? ' ; rapport : ' + saisie.rapport : ' ; sans rapport joint')
      + (saisie.observations ? ' ; observations : ' + saisie.observations : ' ; sans observation');
    return Donnees.modifier('controles_reglementaires', (lignes, outils) => {
      const ligne = ligneDuControle(lignes, controleId);
      refuserSiErreurs(verifierRealisation(ligne, saisie, outils.aujourdhui()));
      ligne.derniere_date = saisie.date;
      ligne.prochaine_date = ajouterMois(saisie.date, periodicite(ligne));
      if (saisie.organisme) ligne.organisme = saisie.organisme;
      ligne.rapport = saisie.rapport;                     // le rapport précédent reste nommé au journal
      ligne.observations = saisie.observations;
      ligne.observations_levees = saisie.observations ? '0' : '1';
      return { derniere_date: ligne.derniere_date, prochaine_date: ligne.prochaine_date };
    }, { action });
  }

  /** Contrôle d'une levée d'observations : [{ nom, message }]. */
  function verifierLevee(controle, valeurs, aujourdhui) {
    if (!observationsALever(controle)) return [{ nom: 'commentaire', message: I18n.t('controles.verifier_levee.controle_pas_observation_lever') }];
    const jour = dateDuJour(aujourdhui);
    const date = texte(valeurs.date);
    const erreurs = date ? erreursDate('date', date, jour, true, I18n.t('controles.verifier_levee.date_levee'))
      : [{ nom: 'date', message: I18n.t('controles.verifier_levee.indiquez_date_laquelle_observations') }];
    const derniere = dateIso(controle.derniere_date);
    if (!erreurs.length && derniere && date < derniere) {
      erreurs.push({ nom: 'date', message: I18n.t('controles.verifier_levee.observations_datent_controle_levee', { derniere: UI.dateFr(derniere) }) });
    }
    if (!texte(valeurs.commentaire)) {
      erreurs.push({ nom: 'commentaire', message: I18n.t('controles.verifier_levee.decrivez_ete_fait_ex') });
    }
    return erreurs;
  }

  /**
   * Lève les observations du dernier contrôle (observations_levees = '1', le texte est gardé) ;
   * journal « observations levées le JJ/MM/AAAA : commentaire ».
   */
  async function leverObservations(controleId, valeurs) {
    const saisie = { date: texte(valeurs && valeurs.date), commentaire: texte(valeurs && valeurs.commentaire) };
    return Donnees.modifier('controles_reglementaires', (lignes, outils) => {
      const ligne = ligneDuControle(lignes, controleId);
      refuserSiErreurs(verifierLevee(ligne, saisie, outils.aujourdhui()));
      ligne.observations_levees = '1';
      return true;
    }, { action: 'observations levées le ' + UI.dateFr(saisie.date) + ' : ' + saisie.commentaire });
  }

  // ===========================================================================================
  // 7. Rapport joint : écriture du document (nom lisible et unique)
  // ===========================================================================================

  function extensionDe(nomFichier) {
    const point = String(nomFichier || '').lastIndexOf('.');
    return point === -1 ? '' : String(nomFichier).slice(point + 1).toLowerCase();
  }

  /** Message d'erreur si le fichier ne peut pas servir de rapport, sinon ''. */
  function verifierFichierRapport(fichier) {
    if (!fichier) return '';
    if (!EXTENSIONS_RAPPORT.includes(extensionDe(fichier.name))) return I18n.t('controles.verifier_fichier_rapport.rapport_doit_etre_pdf');
    if (fichier.size > TAILLE_MAX_RAPPORT && !EXTENSIONS_PHOTO.includes(extensionDe(fichier.name))) {
      return I18n.t('commun.message.fichier_trop_volumineux');
    }
    return '';
  }

  // Le stockage refuse d'écraser un document : « … existe déjà » (dossier, démo) ou « … porte déjà ce nom » (serveur).
  function documentExisteDeja(erreur) {
    return erreur instanceof Donnees.ErreurStockage && /existe déjà|porte déjà ce nom/.test(erreur.message || '');
  }

  /**
   * Écrit le rapport d'un contrôle dans les documents et renvoie son nom :
   * « controle-CTR-0002-2026-10-20.pdf » (« -2 », « -3 »… si ce nom existe déjà). Une photo est
   * réduite (JPEG). Refus (ErreurValidation) : type ou taille.
   */
  async function ecrireRapport(controleId, date, fichier) {
    const message = verifierFichierRapport(fichier);
    if (message) throw ErreurValidation(message);
    const photo = EXTENSIONS_PHOTO.includes(extensionDe(fichier.name));
    const contenu = photo ? await UI.redimensionnerPhoto(fichier, COTE_MAX_PHOTO) : fichier;
    const extension = photo ? 'jpg' : extensionDe(fichier.name);
    if (contenu.size > TAILLE_MAX_RAPPORT) throw ErreurValidation(I18n.t('commun.message.fichier_trop_volumineux'));
    const base = ('controle-' + texte(controleId) + '-' + texte(date)).replace(/[^A-Za-z0-9._-]+/g, '-');
    for (let rang = 1; rang <= ESSAIS_NOM_RAPPORT; rang += 1) {
      const nom = base + (rang === 1 ? '' : '-' + rang) + '.' + extension;
      try {
        return await App.adaptateur.ecrireDocument(nom, contenu);
      } catch (erreur) {
        if (!documentExisteDeja(erreur)) throw erreur;
      }
    }
    return App.adaptateur.ecrireDocument(UI.nomFichierUnique(base, extension), contenu);
  }

  // Contrôles prêtés aux écrans du module (erreurs affichées sous les champs avant d'écrire).
  Object.assign(Controles.interne, { verifierRealisation, verifierLevee, verifierFichierRapport, EXTENSIONS_RAPPORT });

  return {
    // écritures (ARCHITECTURE.md §15.7)
    verifierControle, creerControle, modifierControle, enregistrerRealisation, leverObservations, ecrireRapport,
  };
})());
