'use strict';
// Garanties — écritures des garanties et des contrats de prestataires (2.2, lot L4 ; CDC §3.4, D182, D190, CS173).
// Créer, modifier, retirer (actif = 0, jamais de suppression : la ligne reste, au journal), reconduire un contrat
// (nouvelle période), noter sa résiliation (reconduction tacite à 0, date de la lettre au journal) et écrire le
// document joint (nom lisible, jamais d'écrasement).
//
// Règles communes à toutes les fonctions de ce fichier :
// - profil responsable seulement (QUESTIONS-L2-L6, L4-L6 Q6) : ici côté application ; le serveur refuse aussi
//   l'écriture de ces deux tables à tout autre rôle (T453) ; le technicien les lit, le demandeur ne les reçoit pas ;
// - toute écriture passe par Donnees.modifier ; les contrôles sont refaits DANS la fonction de mutation, sur les
//   lignes fraîches qu'elle reçoit (rejouée si un autre poste a écrit entre-temps) ;
// - valeurs refusées par Garanties.verifierGarantie et Garanties.verifierContrat (garanties-regles.js, qui servent
//   aussi à l'import) : un refus lève Donnees.ErreurValidation (message pour l'utilisateur) et n'écrit rien ;
// - une ligne de journal par écriture (D156 : actions en français fixe, relues par la fiche) ;
// - le document joint (PDF, JPEG, PNG ; une photo est réduite en JPEG) est écrit APRÈS les contrôles et avant la
//   ligne, qui porte son nom : une écriture refusée n'en laisse aucun ; un échec du stockage après lui le laisse
//   orphelin (comme le rapport d'un contrôle). Le nom porte l'identifiant de la ligne et la date du jour :
//   « garantie-GAR-0001-2026-11-08.pdf », « contrat-CTP-0001-2026-11-08.pdf » (« -2 », « -3 »… si pris ; le
//   serveur y ajoute son horodatage devant). Même règle que Controles.ecrireRapport et Equipe.ecrireJustificatif
//   (le L3 n'a pas créé d'outil commun : chaque module garde le sien).
// Chargé juste après garanties-regles.js (qui crée l'objet Garanties). Complète l'objet Garanties ; une fonction d'un
// fichier chargé plus tard est cherchée au moment de l'appel.

Object.assign(Garanties, (() => {

  // Outils de garanties-regles.js.
  const { texte, dateIso, estActif, estTacite } = Garanties.interne;

  // Champs écrits par le formulaire (création et modification) ; actif n'est changé que par « Retirer ».
  const CHAMPS_GARANTIE = ['equipement_id', 'fournisseur_id', 'date_debut', 'date_fin', 'conditions', 'document'];
  const CHAMPS_CONTRAT = ['fournisseur_id', 'objet', 'equipement_ids', 'perimetre', 'date_debut', 'date_fin',
    'preavis_mois', 'reconduction_tacite', 'reconduction_mois', 'montant_annuel', 'document'];
  const CHAMPS_DATES = ['date_debut', 'date_fin'];
  const CHAMPS_ENTIERS = ['preavis_mois', 'reconduction_mois'];

  // Document joint : PDF, JPEG ou PNG (conception L4 §2.3) ; une photo est réduite en JPEG lisible avant l'envoi.
  const EXTENSIONS_DOCUMENT = ['pdf', 'jpg', 'jpeg', 'png'];
  const EXTENSIONS_PHOTO = ['jpg', 'jpeg', 'png'];
  const TAILLE_MAX_DOCUMENT = 9 * 1024 * 1024;           // le serveur refuse plus de 10 Mo
  const COTE_MAX_PHOTO = 2400;                           // pixels : un certificat photographié reste lisible
  const ESSAIS_NOM_DOCUMENT = 9;

  // Les deux tables : nom, champs, ligne vide, vérification, début du nom des documents, messages.
  const GARANTIES = {
    table: 'garanties', champs: CHAMPS_GARANTIE, prefixeId: 'GAR-', debutDocument: 'garantie-',
    vide: { equipement_id: '', fournisseur_id: '', date_debut: '', date_fin: '', conditions: '', document: '' },
    verifier: (valeurs) => Garanties.verifierGarantie(valeurs),
    introuvable: (garantieId) => I18n.t('garanties.ligne.garantie_introuvable', { garantieId }),
    retiree: (garantieId) => I18n.t('garanties.ligne.garantie_retiree', { garantieId }),
  };
  const CONTRATS = {
    table: 'contrats_prestataires', champs: CHAMPS_CONTRAT, prefixeId: 'CTP-', debutDocument: 'contrat-',
    vide: { fournisseur_id: '', objet: '', equipement_ids: '', perimetre: '', date_debut: '', date_fin: '',
      preavis_mois: '', reconduction_tacite: '0', reconduction_mois: '', montant_annuel: '', document: '' },
    verifier: (valeurs) => Garanties.verifierContrat(valeurs),
    introuvable: (contratId) => I18n.t('garanties.ligne.contrat_introuvable', { contratId }),
    retiree: (contratId) => I18n.t('garanties.ligne.contrat_retire', { contratId }),
  };

  // ===========================================================================================
  // 6. Petits outils des écritures
  // ===========================================================================================

  function ErreurValidation(message) {
    return new Donnees.ErreurValidation(message);
  }

  function refuserSiErreurs(erreurs) {
    if (erreurs.length) throw ErreurValidation(erreurs.map((erreur) => erreur.message).join(' '));
  }

  // Garanties et contrats : profil responsable seulement (le serveur le refuse aussi, T453).
  function exigerResponsable() {
    const responsable = typeof App !== 'undefined' && Boolean(App) && typeof App.estResponsable === 'function'
      && App.estResponsable();
    if (!responsable) throw ErreurValidation(I18n.t('garanties.exiger_responsable.seul_responsable'));
  }

  /**
   * Valeurs d'une garantie ou d'un contrat au format du fichier : seuls les champs du formulaire, sans espaces de
   * bord. Dates « 31/12/2026 » → « 2026-12-31 » ; équipements concernés (liste ou texte séparé par « ; », « , » ou
   * des espaces) → « EQ-0001;EQ-0004 », doublons retirés ; préavis et durée d'une reconduction entiers sans zéros
   * (« 03 », « 3,0 » → « 3 ») ; reconduction tacite → « 1 » ou « 0 » ; montant au point décimal (« 4 800,50 » →
   * « 4800.50 »). Une valeur illisible est gardée telle quelle : la vérification la refuse ensuite.
   */
  function valeursDe(sorte, valeurs) {
    const propres = {};
    sorte.champs.forEach((nom) => {
      const brute = valeurs[nom];
      if (brute === undefined || brute === null) return;
      propres[nom] = Array.isArray(brute) ? brute.map(texte).join(';') : texte(brute);
    });
    CHAMPS_DATES.forEach((nom) => {
      const lue = propres[nom] === undefined ? null : Donnees.normaliser.date(propres[nom]);
      if (lue && lue.ok) propres[nom] = lue.valeur;
    });
    if (propres.equipement_ids !== undefined) propres.equipement_ids = Garanties.equipementsDuContrat(propres).join(';');
    CHAMPS_ENTIERS.forEach((nom) => {
      const lu = propres[nom] === undefined ? null : Donnees.normaliser.entier(propres[nom]);
      if (lu && lu.ok && lu.valeur !== '') propres[nom] = String(Number(lu.valeur));
    });
    if (propres.reconduction_tacite !== undefined) {
      propres.reconduction_tacite = Donnees.normaliser.booleen(propres.reconduction_tacite).valeur === '1' ? '1' : '0';
    }
    if (propres.montant_annuel !== undefined) {
      const lu = Donnees.normaliser.decimal(propres.montant_annuel);
      if (lu.ok) propres.montant_annuel = lu.valeur;
    }
    return propres;
  }

  /** La ligne de cet identifiant parmi les lignes fraîches ; refus si elle est introuvable ou retirée. */
  function ligneSuivie(sorte, lignes, id) {
    const ligne = lignes.find((l) => l.id === texte(id));
    if (!ligne) throw ErreurValidation(sorte.introuvable(texte(id)));
    if (!estActif(ligne)) throw ErreurValidation(sorte.retiree(ligne.id));
    return ligne;
  }

  // ===========================================================================================
  // 7. Document joint : vérification, préparation, écriture (nom lisible et unique)
  // ===========================================================================================

  function extensionDe(nomFichier) {
    const point = String(nomFichier || '').lastIndexOf('.');
    return point === -1 ? '' : String(nomFichier).slice(point + 1).toLowerCase();
  }

  /** Message d'erreur si le fichier ne peut pas servir de document (type, taille), sinon ''. */
  function verifierFichierDocument(fichier) {
    if (!fichier) return '';
    if (!EXTENSIONS_DOCUMENT.includes(extensionDe(fichier.name))) return I18n.t('garanties.document.type_refuse');
    if (fichier.size > TAILLE_MAX_DOCUMENT && !EXTENSIONS_PHOTO.includes(extensionDe(fichier.name))) {
      return I18n.t('commun.message.fichier_trop_volumineux');
    }
    return '';
  }

  /** Document prêt à écrire : { contenu, extension } (photo réduite en JPEG), ou null sans fichier. Refus : type,
   *  taille (après réduction pour une photo). */
  async function preparerDocument(fichier) {
    if (!fichier) return null;
    const message = verifierFichierDocument(fichier);
    if (message) throw ErreurValidation(message);
    const photo = EXTENSIONS_PHOTO.includes(extensionDe(fichier.name));
    const contenu = photo ? await UI.redimensionnerPhoto(fichier, COTE_MAX_PHOTO) : fichier;
    if (contenu.size > TAILLE_MAX_DOCUMENT) throw ErreurValidation(I18n.t('commun.message.fichier_trop_volumineux'));
    return { contenu, extension: photo ? 'jpg' : extensionDe(fichier.name) };
  }

  // Le stockage refuse d'écraser un document : « Le document … existe déjà. » (dossier, démo) ou « Un document
  // porte déjà ce nom. » (serveur, 409) ; messages comparés dans la langue de l'écran (comme Controles.ecrireRapport).
  function documentExisteDeja(erreur, nom) {
    return erreur instanceof Donnees.ErreurStockage
      && [I18n.t('socle.creer.document_existe_deja', { nom }), I18n.t('socle.creer.document_porte_deja_nom')].includes(erreur.message);
  }

  /** Écrit un document préparé sous « <garantie-|contrat-><id>-<AAAA-MM-JJ>.<ext> » (« -2 »… si pris) ; renvoie le
   *  nom enregistré par le stockage (à mettre dans la colonne document). */
  async function ecrireDocumentPrepare(sorte, id, date, prepare) {
    const base = (sorte.debutDocument + texte(id) + '-' + (dateIso(date) || Donnees.aujourdhui()))
      .replace(/[^A-Za-z0-9._-]+/g, '-');
    for (let rang = 1; rang <= ESSAIS_NOM_DOCUMENT; rang += 1) {
      const nom = base + (rang === 1 ? '' : '-' + rang) + '.' + prepare.extension;
      try {
        return await App.adaptateur.ecrireDocument(nom, prepare.contenu);
      } catch (erreur) {
        if (!documentExisteDeja(erreur, nom)) throw erreur;
      }
    }
    return App.adaptateur.ecrireDocument(UI.nomFichierUnique(base, prepare.extension), prepare.contenu);
  }

  /**
   * Écrit le document d'une garantie (GAR-…) ou d'un contrat (CTP-…) existant et renvoie son nom
   * (« garantie-GAR-0001-2026-11-08.pdf », « -2 », « -3 »… si ce nom existe déjà : jamais d'écrasement). date :
   * celle du nom (par défaut le jour). N'écrit pas la ligne : creerGarantie, modifierGarantie, creerContrat et
   * modifierContrat reçoivent le fichier eux-mêmes et nomment le document sur la ligne. Refus (ErreurValidation) :
   * profil, ligne introuvable, type ou taille.
   */
  async function ecrireDocument(id, fichier, date) {
    exigerResponsable();
    const sorte = texte(id).startsWith(CONTRATS.prefixeId) ? CONTRATS : GARANTIES;
    if (!Donnees.trouver(sorte.table, texte(id))) throw ErreurValidation(sorte.introuvable(texte(id)));
    if (!fichier) throw ErreurValidation(I18n.t('garanties.document.type_refuse'));
    return ecrireDocumentPrepare(sorte, id, date, await preparerDocument(fichier));
  }

  // ===========================================================================================
  // 8. Création, modification, retrait (communs aux deux tables)
  // ===========================================================================================

  /**
   * Crée une ligne (actif = 1) ; renvoie son identifiant. Fichier facultatif : écrit après les contrôles, nommé
   * avec l'identifiant de la ligne ; rejouée après un conflit, la mutation reprend le document déjà écrit pour le
   * même identifiant. Journal : « création — <actionDeBase> ; document : <nom> ».
   */
  async function creerLigne(sorte, valeurs, fichier, actionDeBase) {
    exigerResponsable();
    const nouvelle = Object.assign({}, sorte.vide, valeursDe(sorte, valeurs || {}), { actif: '1' });
    refuserSiErreurs(sorte.verifier(nouvelle));        // avant de préparer le document : rien d'écrit
    const prepare = await preparerDocument(fichier);
    let ecrit = null;
    let action = actionDeBase;
    return Donnees.modifier(sorte.table, async (lignes, outils) => {
      refuserSiErreurs(sorte.verifier(nouvelle));
      const id = outils.nouvelId(lignes);
      const ligne = Object.assign({ id }, nouvelle);
      if (prepare) {
        if (!ecrit || ecrit.id !== id) ecrit = { id, nom: await ecrireDocumentPrepare(sorte, id, outils.aujourdhui(), prepare) };
        ligne.document = ecrit.nom;
      }
      action = actionDeBase + (prepare ? ' ; document : ' + ligne.document : '');
      lignes.push(ligne);
      return id;
      // Donnees.modifier lit `action` APRÈS la mutation : le « get » rend le texte décidé sur les lignes fraîches.
    }, { get action() { return action; } });
  }

  /**
   * Modifie une ligne active (champs du formulaire, valeurs partielles) ; renvoie la liste des champs réellement
   * changés ([] : rien d'écrit). Fichier facultatif : nouveau document (l'ancien reste dans les documents et au
   * journal). Journal : « modification : <champs> — <actionDeBase> ; document : <nom> ».
   */
  async function modifierLigne(sorte, id, valeurs, fichier, actionDeBase) {
    exigerResponsable();
    const propres = valeursDe(sorte, valeurs || {});
    const prepare = await preparerDocument(fichier);
    let ecrit = '';
    let action = actionDeBase;
    return Donnees.modifier(sorte.table, async (lignes, outils) => {
      const ligne = ligneSuivie(sorte, lignes, id);
      const apres = Object.assign({}, ligne, propres);
      refuserSiErreurs(sorte.verifier(apres));
      if (prepare) {
        if (!ecrit) ecrit = await ecrireDocumentPrepare(sorte, ligne.id, outils.aujourdhui(), prepare);
        apres.document = ecrit;
      }
      const changes = sorte.champs.filter((nom) => texte(ligne[nom]) !== texte(apres[nom]));
      changes.forEach((nom) => { ligne[nom] = texte(apres[nom]); });
      action = actionDeBase + (prepare ? ' ; document : ' + ecrit : '');
      return changes;
    }, { get action() { return action; } });
  }

  /**
   * « Retirer » : actif = 0, rien n'est effacé (la ligne reste, au journal ; elle n'est plus affichée ni rappelée).
   * Déjà retirée (double clic, autre poste) : rien d'écrit. Renvoie ['actif'] ou [].
   */
  async function retirerLigne(sorte, id, action) {
    exigerResponsable();
    return Donnees.modifier(sorte.table, (lignes) => {
      const ligne = lignes.find((l) => l.id === texte(id));
      if (!ligne) throw ErreurValidation(sorte.introuvable(texte(id)));
      if (!estActif(ligne)) return [];
      ligne.actif = '0';
      return ['actif'];
    }, { action });
  }

  // ===========================================================================================
  // 9. Garanties
  // ===========================================================================================

  /** Crée une garantie ; renvoie son identifiant (GAR-…). fichier : certificat ou facture (facultatif). Refus :
   *  Garanties.verifierGarantie (équipement, fournisseur, dates), document (type, taille), profil. */
  async function creerGarantie(valeurs, fichier) {
    const action = 'garantie enregistrée';
    return creerLigne(GARANTIES, valeurs, fichier, action);
  }

  /** Modifie une garantie active ; renvoie la liste des champs changés. fichier : nouveau document (facultatif). */
  async function modifierGarantie(garantieId, valeurs, fichier) {
    const action = 'modification de la garantie';
    return modifierLigne(GARANTIES, garantieId, valeurs, fichier, action);
  }

  /** Retire une garantie (actif = 0, jamais supprimée) ; renvoie ['actif'] ou [] si elle l'était déjà. */
  async function retirerGarantie(garantieId) {
    const action = 'garantie retirée';
    return retirerLigne(GARANTIES, garantieId, action);
  }

  // ===========================================================================================
  // 10. Contrats de prestataires
  // ===========================================================================================

  /** Crée un contrat ; renvoie son identifiant (CTP-…). fichier : contrat signé (facultatif). Montant annuel
   *  facultatif, dans la devise réglée, hors taxes (D190). Refus : Garanties.verifierContrat, document, profil. */
  async function creerContrat(valeurs, fichier) {
    const action = 'contrat enregistré';
    return creerLigne(CONTRATS, valeurs, fichier, action);
  }

  /** Modifie un contrat actif ; renvoie la liste des champs changés. fichier : nouveau document (facultatif). */
  async function modifierContrat(contratId, valeurs, fichier) {
    const action = 'modification du contrat';
    return modifierLigne(CONTRATS, contratId, valeurs, fichier, action);
  }

  /** Retire un contrat (actif = 0, jamais supprimé) ; renvoie ['actif'] ou [] s'il l'était déjà. */
  async function retirerContrat(contratId) {
    const action = 'contrat retiré';
    return retirerLigne(CONTRATS, contratId, action);
  }

  /**
   * « Reconduire » un contrat à reconduction tacite : nouvelle période { date_debut, date_fin }, par défaut celle
   * de Garanties.propositionReconduction (ancienne fin + 1 jour ; durée reconduction_mois, sinon celle de la
   * période, sinon 12 mois), toujours modifiable. Refus : contrat sans reconduction tacite (ses dates se
   * modifient), dates (verifierContrat), nouvelle fin pas après la fin actuelle. Journal : « reconduction : du
   * 01/01/2026 au 31/12/2026 → du 01/01/2027 au 31/12/2027 » (« jusqu'au … » sans début). Renvoie la période écrite.
   */
  async function reconduireContrat(contratId, valeurs) {
    exigerResponsable();
    const saisie = valeursDe(CONTRATS, valeurs || {});
    let action = '';
    return Donnees.modifier(CONTRATS.table, (lignes) => {
      const ligne = ligneSuivie(CONTRATS, lignes, contratId);
      if (!estTacite(ligne)) throw ErreurValidation(I18n.t('garanties.reconduire.pas_tacite'));
      const proposee = Garanties.propositionReconduction(ligne) || { date_debut: '', date_fin: '' };
      const nouvelle = {
        date_debut: saisie.date_debut !== undefined ? saisie.date_debut : proposee.date_debut,
        date_fin: saisie.date_fin !== undefined ? saisie.date_fin : proposee.date_fin,
      };
      // Seules les dates sont contrôlées : la fenêtre « Reconduire » ne montre qu'elles.
      refuserSiErreurs(Garanties.verifierContrat(Object.assign({}, ligne, nouvelle))
        .filter((erreur) => CHAMPS_DATES.includes(erreur.nom)));
      const ancienDebut = UI.dateFr(dateIso(ligne.date_debut));
      const ancienneFin = dateIso(ligne.date_fin);
      if (ancienneFin && nouvelle.date_fin <= ancienneFin) {
        throw ErreurValidation(I18n.t('garanties.reconduire.fin_apres_actuelle', { fin: UI.dateFr(ancienneFin) }));
      }
      const nouveauDebut = UI.dateFr(nouvelle.date_debut);
      action = 'reconduction : ' + (ancienDebut ? 'du ' + ancienDebut + ' au ' : 'jusqu\'au ')
        + (UI.dateFr(ancienneFin) || '?') + ' → ' + (nouveauDebut ? 'du ' + nouveauDebut + ' au ' : 'jusqu\'au ')
        + UI.dateFr(nouvelle.date_fin);
      ligne.date_debut = nouvelle.date_debut;
      ligne.date_fin = nouvelle.date_fin;
      return nouvelle;
    }, { get action() { return action; } });
  }

  /** Erreurs de la date d'envoi de la lettre : obligatoire, lisible, pas dans le futur. */
  function erreursDateLettre(date, jour) {
    if (!date) return [{ nom: 'date', message: I18n.t('garanties.noter_resiliation.date_obligatoire') }];
    if (!dateIso(date)) return [{ nom: 'date', message: I18n.t('garanties.noter_resiliation.date_illisible') }];
    if (date > jour) return [{ nom: 'date', message: I18n.t('garanties.noter_resiliation.date_future') }];
    return [];
  }

  /**
   * « Noter la résiliation » ({ date, commentaire }) : la lettre est partie (Prévo n'envoie rien). Effet :
   * reconduction tacite → 0 (le contrat se termine à sa fin). Journal : « résiliation notée : lettre du
   * JJ/MM/AAAA ; <commentaire> » ; contrat déjà sans reconduction tacite : la ligne ne change pas, l'entrée du
   * journal est écrite quand même (la trace de la lettre). Refus : date de la lettre absente, illisible ou future,
   * contrat introuvable ou retiré, profil, contrat tacite dont la fin enregistrée est passée (« dates à mettre à
   * jour » ou « à décider » sur une période calculée : reconduire d'abord, rien n'est écrit). Renvoie ['reconduction_tacite'] ou [].
   */
  async function noterResiliation(contratId, valeurs) {
    exigerResponsable();
    const v = valeurs || {};
    const lue = Donnees.normaliser.date(v.date);
    const date = lue.ok ? lue.valeur : texte(v.date);
    const commentaire = texte(v.commentaire);
    const action = 'résiliation notée : lettre du ' + UI.dateFr(date) + (commentaire ? ' ; ' + commentaire : '');
    let id = texte(contratId);
    const changes = await Donnees.modifier(CONTRATS.table, (lignes, outils) => {
      const ligne = ligneSuivie(CONTRATS, lignes, contratId);
      refuserSiErreurs(erreursDateLettre(date, outils.aujourdhui()));
      id = ligne.id;
      // Fin enregistrée passée : la lettre ferait « terminer » le contrat à son ancienne fin ; reconduire d'abord (T464),
      // quel que soit le statut : « à décider » sur une période calculée comme « dates à mettre à jour » (D198, T503).
      const etat = Garanties.etatContrat(ligne, outils.aujourdhui());
      if (estTacite(ligne) && (etat.periodeCalculee || etat.statut === 'a_mettre_a_jour')) {
        throw ErreurValidation(I18n.t('garanties.noter_resiliation.reconduire_d_abord', { fin: UI.dateFr(dateIso(ligne.date_fin)) }));
      }
      if (!estTacite(ligne)) return [];
      ligne.reconduction_tacite = '0';
      return ['reconduction_tacite'];
    }, { action });
    if (!changes.length) await Donnees.journaliser(CONTRATS.table, id, action);
    return changes;
  }

  // Contrôles prêtés aux formulaires du module (erreurs affichées sous les champs avant d'écrire).
  Object.assign(Garanties.interne, { verifierFichierDocument, EXTENSIONS_DOCUMENT });

  return {
    // écritures (conception L4 §2.3 et §2.4)
    creerGarantie, modifierGarantie, retirerGarantie,
    creerContrat, modifierContrat, retirerContrat, reconduireContrat, noterResiliation,
    ecrireDocument,
  };
})());
