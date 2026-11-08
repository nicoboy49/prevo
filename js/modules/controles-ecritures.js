'use strict';
// Controles (2/3) — écritures des contrôles réglementaires (ARCHITECTURE.md §15.7 ; brief RG9, E10) :
// création, modification, contrôle réalisé (dates recalculées, rapport joint, réserves relevées ajoutées par
// Controles.ajouterReserves de controles-reserves.js, 2.2), levée des observations ; source de la périodicité et
// mise à jour du catalogue reprise sur un clic (2.2, CS171 ; règles de controles-catalogue.js, chargé avant).
//
// Règles communes à toutes les fonctions de ce fichier :
// - toute écriture passe par Donnees.modifier('controles_reglementaires') ; les contrôles sont
//   refaits DANS la fonction de mutation, sur les lignes fraîches qu'elle reçoit (elle est rejouée
//   sur les lignes relues si un autre poste a écrit entre-temps) ;
// - un refus lève Donnees.ErreurValidation (message pour l'utilisateur) ; jamais de suppression ;
// - ce module ne crée JAMAIS d'ordre de travail : « Créer un OT » ouvre le formulaire de l'OT
//   pré-rempli, que le responsable valide lui-même (écran, controles-ecrans.js).
// Complète l'objet Controles créé par controles-regles.js (et complété par controles-reserves.js, chargé avant).

Object.assign(Controles, (() => {

  // Outils de controles-regles.js.
  const { texte, dateIso, dateDuJour, periodicite, observationsALever } = Controles.interne;
  // Outils de controles-reserves.js (chargé avant ce fichier).
  const { refuserSiErreurs, erreursDate, erreursEcheance } = Controles.interne;
  const { ajouterMois } = Controles;

  // Champs du formulaire d'un contrôle (création et modification). Le rapport, les observations
  // et leur levée viennent des actions « contrôle réalisé » et « lever les observations ».
  // 2.2 (CS171) : nature_source est saisie (ou copiée du catalogue) ; source_periodicite, catalogue_id et
  // catalogue_relu_le (CHAMPS_PROVENANCE) sont tenus par l'écriture elle-même (sourceAvantEcriture).
  const CHAMPS_CONTROLE = ['equipement_id', 'nature', 'texte_reference', 'periodicite_mois', 'organisme',
    'derniere_date', 'prochaine_date', 'nature_source', 'source_periodicite', 'catalogue_id', 'catalogue_relu_le'];
  const CHAMPS_PROVENANCE = ['source_periodicite', 'catalogue_id', 'catalogue_relu_le'];
  // Valeurs qui font la source (comparées comme dans Controles.sourceApresSaisie) ; la nature n'en est pas.
  const CHAMPS_SOURCE = ['periodicite_mois', 'texte_reference', 'nature_source'];
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

  function ligneDuControle(lignes, controleId) {
    const ligne = lignes.find((l) => l.id === controleId);
    if (!ligne) throw ErreurValidation(I18n.t('controles.ligne_du_controle.controle_introuvable', { controleId: (controleId || I18n.t('controles.ligne_du_controle.non_choisi')) }));
    return ligne;
  }

  function naturesSource() {
    const champ = Schema.champ('controles_reglementaires', 'nature_source');
    return (champ && champ.valeurs) || [];
  }

  /**
   * Valeurs d'un contrôle au format du fichier : seuls les champs du formulaire, sans espaces de bord.
   * Nature de la source hors de la liste et ligne du catalogue inconnue (ou catalogue absent) ramenées à vide,
   * sans message (2.2) ; « c14 » s'écrit « C14 ».
   */
  function valeursControle(valeurs) {
    const propres = {};
    CHAMPS_CONTROLE.forEach((nom) => {
      if (valeurs[nom] === undefined || valeurs[nom] === null) return;
      propres[nom] = texte(valeurs[nom]);
    });
    if (propres.periodicite_mois && /^\d+$/.test(propres.periodicite_mois)) {
      propres.periodicite_mois = String(Number(propres.periodicite_mois));     // « 012 » → « 12 »
    }
    if (propres.nature_source !== undefined) {
      const nature = propres.nature_source.toLowerCase();
      propres.nature_source = naturesSource().includes(nature) ? nature : '';
    }
    if (propres.catalogue_id !== undefined) {
      const ligne = Controles.ligneCatalogue(propres.catalogue_id);
      propres.catalogue_id = ligne ? texte(ligne.id) : '';
    }
    return propres;
  }

  /** Les valeurs sans les champs de provenance (jamais pris tels quels de l'appelant). */
  function sansProvenance(valeurs) {
    const copie = Object.assign({}, valeurs);
    CHAMPS_PROVENANCE.forEach((nom) => { delete copie[nom]; });
    return copie;
  }

  function memesValeursSource(a, b) {
    const valeur = (ligne, champ) => {
      const brute = texte(ligne[champ]);
      return champ === 'periodicite_mois' && /^\d+$/.test(brute) ? String(Number(brute)) : brute;
    };
    return CHAMPS_SOURCE.every((champ) => valeur(a, champ) === valeur(b, champ));
  }

  /**
   * Provenance d'un contrôle avant son écriture : { source_periodicite, catalogue_id, catalogue_relu_le }, par
   * Controles.sourceApresSaisie (CS171 : une valeur de la source changée → « saisie », la ligne gardée).
   * - création (avant absent) : ligne = catalogue_id choisi ; catalogue_relu_le = relecture de cette ligne ;
   * - modification : ligne = celle du contrôle (catalogue_id et catalogue_relu_le ne changent pas ici) et le
   *   contrôle d'avant en 3e argument : changer l'organisme d'un contrôle « catalogue » dont la ligne a été relue
   *   depuis le laisse « catalogue » (sa mise à jour reste proposée, jamais appliquée par une autre écriture) ;
   *   ligne absente du catalogue de la page (fichier retouché, ligne retirée par une version plus récente) :
   *   provenance gardée telle quelle tant que périodicité, référence et nature de la source ne changent pas,
   *   « saisie » sinon ; jamais effacée par l'absence du catalogue.
   */
  function sourceAvantEcriture(apres, choisie, avant) {
    if (!avant) return Controles.sourceApresSaisie(sansProvenance(apres), choisie);
    const catalogueId = texte(avant.catalogue_id);
    if (catalogueId && !Controles.ligneCatalogue(catalogueId)) {
      return { source_periodicite: memesValeursSource(apres, avant) ? texte(avant.source_periodicite) : 'saisie',
        catalogue_id: catalogueId, catalogue_relu_le: texte(avant.catalogue_relu_le) };
    }
    return Controles.sourceApresSaisie(apres, catalogueId, avant);
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

  /**
   * Crée un contrôle ; renvoie son identifiant (CTR-…). catalogue_id : la ligne du catalogue choisie (facultatif) ;
   * source_periodicite et catalogue_relu_le sont calculés (« catalogue » si périodicité, référence et nature de la
   * source sont celles de la ligne, « saisie » sinon), jamais pris des valeurs reçues.
   */
  async function creerControle(valeurs) {
    const propres = valeursControle(valeurs || {});
    const choisie = propres.catalogue_id || '';
    const nouveau = Object.assign({ nature_source: '' }, sansProvenance(propres));
    Object.assign(nouveau, sourceAvantEcriture(nouveau, choisie, null));
    return Donnees.modifier('controles_reglementaires', (lignes, outils) => {
      refuserSiErreurs(verifierControle(nouveau, outils.aujourdhui()));
      const id = outils.nouvelId(lignes);
      lignes.push(Object.assign({}, nouveau, { id, rapport: '', observations: '', observations_levees: '1' }));
      return id;
    }, { action: 'création du contrôle réglementaire' });
  }

  /**
   * Modifie un contrôle (champs du formulaire) ; renvoie la liste des champs réellement changés. La source est
   * recalculée sur la ligne fraîche (sourceAvantEcriture) : une périodicité, une référence ou une nature de la
   * source changée rend « saisie » (catalogue_id gardé) ; catalogue_id, catalogue_relu_le et source_periodicite
   * reçus sont ignorés (seule appliquerMiseAJourCatalogue reprend des valeurs du catalogue).
   */
  async function modifierControle(controleId, valeurs) {
    const propres = sansProvenance(valeursControle(valeurs || {}));
    return Donnees.modifier('controles_reglementaires', (lignes, outils) => {
      const ligne = ligneDuControle(lignes, controleId);
      const apres = Object.assign({}, ligne, propres);
      refuserSiErreurs(verifierControle(apres, outils.aujourdhui()));
      const nouvelles = Object.assign({}, propres, sourceAvantEcriture(apres, null, ligne));
      const changes = Object.keys(nouvelles).filter((nom) => texte(ligne[nom]) !== nouvelles[nom]);
      changes.forEach((nom) => { ligne[nom] = nouvelles[nom]; });
      return changes;
    }, { action: 'modification du contrôle réglementaire' });
  }

  /**
   * Reprend sur un contrôle les valeurs que propose une relecture plus récente de sa ligne du catalogue
   * (Controles.miseAJourProposee : périodicité, référence, nature de la source) ; catalogue_relu_le prend la date
   * de cette relecture. Seule écriture qui reprend des valeurs du catalogue sur un contrôle existant, sur un clic
   * (CS171 : une mise à jour du catalogue ne change aucun contrôle sans lui). La prochaine date enregistrée n'est
   * pas recalculée (comme à la modification de la périodicité : le fichier fait foi). Rien de proposé (déjà
   * repris, ici ou sur un autre poste ; contrôle « saisie ») : rien n'est écrit, renvoie []. Journal : « valeurs
   * du catalogue C14 relu le 01/03/2027 reprises ». Renvoie la liste des champs changés.
   */
  async function appliquerMiseAJourCatalogue(controleId) {
    const annoncee = Controles.miseAJourProposee(Donnees.trouver('controles_reglementaires', texte(controleId)));
    const choisie = annoncee ? annoncee.ligne : null;
    const reluLe = choisie ? dateIso(choisie.relu_le) : '';
    const action = choisie ? 'valeurs du catalogue ' + texte(choisie.id) + (reluLe ? ' relu le ' + UI.dateFr(reluLe) : '')
      + ' reprises' : '';
    return Donnees.modifier('controles_reglementaires', (lignes) => {
      const ligne = ligneDuControle(lignes, texte(controleId));
      const proposee = Controles.miseAJourProposee(ligne);
      // Sur la ligne fraîche : seulement la proposition annoncée au journal (même ligne, même relecture).
      if (!proposee || !choisie || texte(proposee.ligne.id) !== texte(choisie.id)
        || dateIso(proposee.ligne.relu_le) !== reluLe) return [];
      const nouvelles = { source_periodicite: 'catalogue' };
      proposee.ecarts.forEach((ecart) => { nouvelles[ecart.champ] = ecart.propose; });
      if (reluLe) nouvelles.catalogue_relu_le = reluLe;
      const changes = Object.keys(nouvelles).filter((nom) => texte(ligne[nom]) !== nouvelles[nom]);
      changes.forEach((nom) => { ligne[nom] = nouvelles[nom]; });
      return changes;
    }, { action });
  }

  // ===========================================================================================
  // 6. Contrôle réalisé et levée des observations
  // ===========================================================================================

  /**
   * Contrôle d'un « contrôle réalisé » : [{ nom, message }]. Date obligatoire, ni future ni
   * antérieure au dernier contrôle enregistré ; périodicité connue (pour calculer la suivante) ;
   * échéance de levée des réserves (facultative) lisible et pas avant la date du contrôle.
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
    return erreurs.concat(erreursEcheance(valeurs.echeance_levee, erreurs.length ? '' : date));
  }

  /**
   * Enregistre un contrôle réalisé ({ date, organisme, rapport, reserves, echeance_levee }) en deux
   * écritures, dans un ordre sûr (D18) :
   * 1. le contrôle : derniere_date = date, prochaine_date = date + périodicité (même jour, ramené à
   *    la fin du mois), organisme (s'il est donné), rapport (nom d'un document déjà écrit par
   *    ecrireRapport ; vide si aucun) ; transition jusqu'à T418 : observations = texte des réserves,
   *    observations_levees = '0' s'il y en a, sinon '1' (le statut d'avant T412 reste juste) ;
   * 2. les réserves relevées (une par ligne du texte), AJOUTÉES par Controles.ajouterReserves avec
   *    cette date et l'échéance donnée : aucune réserve existante n'est effacée ni modifiée (CS170 ;
   *    celles des contrôles précédents restent ouvertes). Rejouable : renvoyer la même saisie après
   *    un échec de la 2e écriture ne recrée pas les réserves déjà écrites.
   * `observations` est lu comme synonyme de `reserves` (ancienne fenêtre, jusqu'à T418). Renvoie
   * { derniere_date, prochaine_date, reserves: identifiants créés }.
   */
  async function enregistrerRealisation(controleId, valeurs) {
    const v = valeurs || {};
    const saisie = {
      date: texte(v.date), organisme: texte(v.organisme), rapport: texte(v.rapport),
      observations: texte(v.reserves !== undefined && v.reserves !== null ? v.reserves : v.observations),
      echeance_levee: texte(v.echeance_levee),
    };
    const action = 'contrôle réalisé le ' + UI.dateFr(saisie.date)
      + (saisie.organisme ? ' par ' + saisie.organisme : '')
      + (saisie.rapport ? ' ; rapport : ' + saisie.rapport : ' ; sans rapport joint')
      + (saisie.observations ? ' ; observations : ' + saisie.observations : ' ; sans observation');
    const dates = await Donnees.modifier('controles_reglementaires', (lignes, outils) => {
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
    const reserves = Controles.lignesDeReserves(saisie.observations).length
      ? await Controles.ajouterReserves(controleId, { date_controle: saisie.date, texte: saisie.observations,
        echeance_levee: saisie.echeance_levee })
      : [];
    return Object.assign(dates, { reserves });
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

  // Le stockage refuse d'écraser un document : « Le document … existe déjà. » (dossier, démo) ou « Un document
  // porte déjà ce nom. » (serveur, 409). Il n'a pas de code d'erreur pour ce cas : ses messages sont comparés
  // dans la langue de l'écran, celle où il les écrit (comme Equipe.ecrireJustificatif) ; avant T413, seul le
  // français était reconnu et un 2e rapport du même jour échouait dans une autre langue au lieu de prendre « -2 ».
  function documentExisteDeja(erreur, nom) {
    return erreur instanceof Donnees.ErreurStockage
      && [I18n.t('socle.creer.document_existe_deja', { nom }), I18n.t('socle.creer.document_porte_deja_nom')].includes(erreur.message);
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
        if (!documentExisteDeja(erreur, nom)) throw erreur;
      }
    }
    return App.adaptateur.ecrireDocument(UI.nomFichierUnique(base, extension), contenu);
  }

  // Contrôles prêtés aux écrans du module (erreurs affichées sous les champs avant d'écrire).
  Object.assign(Controles.interne, { verifierRealisation, verifierLevee, verifierFichierRapport, EXTENSIONS_RAPPORT });

  return {
    // écritures (ARCHITECTURE.md §15.7)
    verifierControle, creerControle, modifierControle, enregistrerRealisation, leverObservations, ecrireRapport,
    // catalogue des contrôles (CONCEPTION-L2-L3 §4.2)
    appliquerMiseAJourCatalogue,
  };
})());
