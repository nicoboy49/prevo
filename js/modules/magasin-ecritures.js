'use strict';
// Magasin (2/5) — écritures du magasin (ARCHITECTURE.md §14.4, brief §7 RG6) : sorties et retours
// imputés à un OT (refus d'un stock négatif), entrées, inventaire, achats (demandée → commandée →
// reçue), articles et fournisseurs, puis copie du stock dans la colonne `stock` des articles.
//
// Règles communes à toutes les fonctions de ce fichier :
// - toute écriture passe par Donnees.modifier ; les contrôles sont refaits DANS la fonction de
//   mutation, sur les lignes fraîches qu'elle reçoit (rejouée sur les lignes relues si un autre
//   poste a écrit entre-temps) : deux postes qui sortent la dernière pièce en même temps → une
//   seule sortie passe, l'autre reçoit « Stock insuffisant : 0 en stock, 1 demandé » ;
// - un refus lève Donnees.ErreurValidation (message pour l'utilisateur) ; jamais de suppression ;
// - après un mouvement, mettreAJourStocks(ids) recopie le stock recalculé dans articles.stock
//   (la colonne n'est qu'une copie lisible dans Excel : un échec de cette copie est seulement
//   signalé en console, il n'annule pas le mouvement déjà enregistré) ;
// - le prix d'un article n'est jamais changé par une réception (D24 : le prix payé reste dans achats).
// Complète l'objet Magasin créé par magasin-regles.js.

Object.assign(Magasin, (() => {

  // Outils de magasin-regles.js.
  const { texte, arrondi, libelleArticle, valeurFichier, nombreTexte, normaliser, estActif,
    stockDepuisLignes, netSortiDepuisLignes } = Magasin.interne;

  const CHAMPS_ARTICLE = ['reference', 'designation', 'fabricant', 'ref_fabricant', 'emplacement', 'unite',
    'stock_securite', 'point_commande', 'qte_commande', 'delai_jours', 'prix_unitaire', 'fournisseur_id',
    'critique', 'actif'];
  const CHAMPS_NOMBRES_ARTICLE = ['stock_securite', 'point_commande', 'qte_commande', 'delai_jours', 'prix_unitaire'];
  const CHAMPS_FOURNISSEUR = ['nom', 'contact', 'telephone', 'email'];

  // ===========================================================================================
  // 3. Petits outils des écritures
  // ===========================================================================================

  function ErreurValidation(message) {
    return new Donnees.ErreurValidation(message);
  }

  /**
   * Quantité saisie ('2', '2,5', 2) → Number arrondi à 6 décimales. Refus (ErreurValidation) si
   * elle est illisible, négative, ou nulle quand `zeroPermis` est faux. `precision` : début du message.
   */
  function quantiteValide(valeur, zeroPermis, precision) {
    const quantite = Donnees.nombre(valeur);
    const debut = precision ? precision + ' : ' : '';
    if (quantite === null) throw ErreurValidation(I18n.t('magasin.quantite_valide.saisissez_quantite_ex_2', { debut }));
    if (zeroPermis ? quantite < 0 : quantite <= 0) {
      throw ErreurValidation(debut + (zeroPermis ? I18n.t('magasin.quantite_valide.quantite_peut_pas_etre') : I18n.t('magasin.quantite_valide.quantite_doit_etre_superieure')));
    }
    return arrondi(quantite, 6);
  }

  /**
   * Utilisateur inscrit dans un mouvement : le libellé du profil (App.profil) — le nom du
   * technicien (« Julien Moreau », comme dans le jeu de démo) ou « Responsable ».
   */
  function utilisateurCourant() {
    const profil = typeof App !== 'undefined' ? App.profil : null;
    if (!profil) return '';
    if (profil.type === 'responsable') return I18n.t('magasin.utilisateur_courant.responsable');
    return texte(profil.nom) || texte(profil.technicienId) || (profil.type === 'technicien' ? I18n.t('magasin.utilisateur_courant.technicien') : I18n.t('magasin.utilisateur_courant.demandeur'));
  }

  function articleExistant(articleId) {
    const article = Donnees.trouver('articles', texte(articleId));
    if (!article) throw ErreurValidation(I18n.t('magasin.article_existant.article_introuvable', { article: (texte(articleId) || I18n.t('magasin.article_existant.non_choisi')) }));
    return article;
  }

  // OT ouvert (ni clôturé ni annulé), lu dans le cache : appeler après Donnees.rechargerTable.
  // `mouvement` : 'sortie' ou 'retour' (pour le message).
  function verifierOtOuvert(otId, mouvement) {
    const ot = Donnees.trouver('ordres_travail', otId);
    if (!ot) throw ErreurValidation(I18n.t('commun.message.ot_introuvable', { otId }));
    if (!Ordres.estOuvert(ot)) {
      throw ErreurValidation(mouvement === 'sortie'
        ? I18n.t('magasin.verifier_ot_ouvert.ot_peut_etre_autre', { otId, otStatut: ot.statut })
        : I18n.t('magasin.verifier_ot_ouvert.ot_peut_etre_autre_2', { otId, otStatut: ot.statut }));
    }
    return ot;
  }

  /** Ajoute un mouvement à la copie des lignes de mouvements_stock ; renvoie son identifiant. */
  function nouveauMouvement(lignes, outils, valeurs) {
    const id = outils.nouvelId(lignes);
    lignes.push({
      id, date: outils.maintenant(), article_id: valeurs.articleId, type: valeurs.type,
      quantite: valeurFichier(valeurs.quantite), ot_id: valeurs.otId || '',
      utilisateur: utilisateurCourant(), commentaire: texte(valeurs.commentaire),
    });
    return id;
  }

  /**
   * Recopie dans articles.stock le stock recalculé depuis les mouvements pour les articles donnés.
   * Idempotent : rien n'est écrit si la colonne est déjà juste.
   * Le stock est recalculé sur mouvements_stock RELU dans la fonction de mutation (à chaque essai) :
   * si un autre poste a ajouté un mouvement entre-temps, l'écriture de articles part en conflit,
   * la table est relue et la fonction rejouée avec ses mouvements (le cache de ce poste les ignore).
   * Renvoie les identifiants des articles dont la colonne a changé.
   */
  async function mettreAJourStocks(ids) {
    const aRecalculer = new Set((ids || []).map(texte).filter(Boolean));
    if (!aRecalculer.size) return [];
    return Donnees.modifier('articles', async (lignes) => {
      const mouvements = await Donnees.rechargerTable('mouvements_stock');
      const changes = [];
      lignes.forEach((ligne) => {
        if (!aRecalculer.has(ligne.id)) return;
        const stock = stockDepuisLignes(mouvements, ligne.id);
        if (Donnees.nombre(ligne.stock) === stock && texte(ligne.stock) !== '') return;
        ligne.stock = valeurFichier(stock);
        changes.push(ligne.id);
      });
      return changes;
    }, { action: 'stock recalculé depuis les mouvements' });
  }

  // Après un mouvement enregistré : la copie du stock ne doit jamais faire croire à un échec du
  // mouvement (l'utilisateur le referait). Un échec est noté en console ; le prochain mouvement de
  // l'article corrigera la colonne.
  async function copierStocks(ids) {
    try {
      await mettreAJourStocks(ids);
    } catch (erreur) {
      console.warn('Prévo : colonne stock de articles.csv non mise à jour (' + (erreur && erreur.message) + ').', erreur);
    }
  }

  // ===========================================================================================
  // 4. Mouvements : sortie et retour (imputés à un OT), entrée, inventaire
  // ===========================================================================================

  /**
   * Sortie de stock imputée à un OT (RG6). Refus : OT absent, introuvable, clôturé ou annulé ;
   * quantité ≤ 0 ; stock qui deviendrait négatif (« Stock insuffisant : X en stock, Y demandé »).
   * Renvoie l'identifiant du mouvement créé.
   */
  async function sortir(otId, articleId, quantite, commentaire) {
    const demandee = quantiteValide(quantite, false, I18n.t('magasin.sortir.sortie_refusee'));
    if (!texte(otId)) {
      throw ErreurValidation(I18n.t('magasin.sortir.sortie_refusee_toute_sortie'));
    }
    const article = articleExistant(articleId);
    await Donnees.rechargerTable('ordres_travail');     // un OT clôturé ou annulé ailleurs est vu
    verifierOtOuvert(otId, 'sortie');
    const id = await Donnees.modifier('mouvements_stock', (lignes, outils) => {
      verifierOtOuvert(otId, 'sortie');
      const stock = stockDepuisLignes(lignes, article.id);
      if (stock - demandee < 0) {
        throw ErreurValidation(I18n.t('magasin.sortir.stock_insuffisant_stock_demande', { stock: nombreTexte(stock), demande: nombreTexte(demandee) }));
      }
      return nouveauMouvement(lignes, outils, { articleId: article.id, type: 'sortie', quantite: demandee, otId, commentaire });
    }, { action: 'sortie de ' + nombreTexte(demandee) + ' ' + texte(article.reference) + ' pour ' + otId });
    await copierStocks([article.id]);
    return id;
  }

  /**
   * Retour en stock d'une pièce sortie pour un OT : pas plus que le net sorti (sorties − retours)
   * de cet article pour cet OT, OT ni clôturé ni annulé. Renvoie l'identifiant du mouvement.
   */
  async function retourner(otId, articleId, quantite, commentaire) {
    const rendue = quantiteValide(quantite, false, I18n.t('magasin.retourner.retour_refuse'));
    if (!texte(otId)) throw ErreurValidation(I18n.t('magasin.retourner.retour_refuse_indiquez_ordre'));
    const article = articleExistant(articleId);
    await Donnees.rechargerTable('ordres_travail');
    verifierOtOuvert(otId, 'retour');
    const id = await Donnees.modifier('mouvements_stock', (lignes, outils) => {
      verifierOtOuvert(otId, 'retour');
      const net = netSortiDepuisLignes(lignes, otId, article.id);
      if (rendue > net) {
        throw ErreurValidation(I18n.t('magasin.retourner.retour_refuse_sorti_ot', { sorti: nombreTexte(Math.max(0, net)), otId, aRetourner: nombreTexte(rendue) }));
      }
      return nouveauMouvement(lignes, outils, { articleId: article.id, type: 'retour', quantite: rendue, otId, commentaire });
    }, { action: 'retour de ' + nombreTexte(rendue) + ' ' + texte(article.reference) + ' (' + otId + ')' });
    await copierStocks([article.id]);
    return id;
  }

  /** Entrée en stock hors achat (ex. pièce récupérée, don d'un autre site). Renvoie l'identifiant du mouvement. */
  async function entrer(articleId, quantite, commentaire) {
    const entree = quantiteValide(quantite, false, I18n.t('magasin.entrer.entree_refusee'));
    const article = articleExistant(articleId);
    const id = await Donnees.modifier('mouvements_stock', (lignes, outils) => nouveauMouvement(lignes, outils, {
      articleId: article.id, type: 'entrée', quantite: entree, commentaire,
    }), { action: 'entrée de ' + nombreTexte(entree) + ' ' + texte(article.reference) });
    await copierStocks([article.id]);
    return id;
  }

  /**
   * Inventaire : comptages = [{ articleId, quantite }] (stock compté, valeur absolue ≥ 0). Un
   * mouvement « inventaire » par article, en une seule écriture. Renvoie les identifiants créés.
   */
  async function inventorier(comptages, commentaire) {
    const vus = new Set();
    const liste = (comptages || []).map((comptage) => {
      const article = articleExistant(comptage && comptage.articleId);
      if (vus.has(article.id)) throw ErreurValidation(I18n.t('magasin.inventorier.inventaire_refuse_compte_deux', { libelleArticle: libelleArticle(article) }));
      vus.add(article.id);
      return { article, quantite: quantiteValide(comptage.quantite, true, I18n.t('magasin.inventorier.stock_compte', { reference: texte(article.reference) })) };
    });
    if (!liste.length) throw ErreurValidation(I18n.t('magasin.inventorier.inventaire_vide_saisissez_stock'));
    const remarque = texte(commentaire) || I18n.t('magasin.inventorier.inventaire');
    const ids = await Donnees.modifier('mouvements_stock', (lignes, outils) => liste.map((comptage) => nouveauMouvement(lignes, outils, {
      articleId: comptage.article.id, type: 'inventaire', quantite: comptage.quantite, commentaire: remarque,
    })), { action: 'inventaire de ' + liste.length + ' article(s)' });
    await copierStocks(liste.map((comptage) => comptage.article.id));
    return ids;
  }

  // ===========================================================================================
  // 5. Achats : demandée → commandée → reçue (D24 : le prix de l'article ne change pas)
  // ===========================================================================================

  function ligneAchat(lignes, achatId) {
    const achat = lignes.find((ligne) => ligne.id === achatId);
    if (!achat) throw ErreurValidation(I18n.t('magasin.ligne_achat.achat_introuvable', { achatId }));
    return achat;
  }

  /**
   * Demande d'achat (statut « demandée », prix = prix actuel de l'article, date du jour).
   * fournisseurId : facultatif (non fourni → fournisseur habituel de l'article ; '' → aucun).
   * Refus si une demande de cet article attend déjà d'être commandée. Renvoie l'identifiant.
   */
  async function demanderAchat(articleId, quantite, fournisseurId) {
    const demandee = quantiteValide(quantite, false, I18n.t('magasin.demander_achat.demande_achat_refusee'));
    const article = articleExistant(articleId);
    const fournisseur = texte(fournisseurId === undefined || fournisseurId === null ? article.fournisseur_id : fournisseurId);
    if (fournisseur && !Donnees.trouver('fournisseurs', fournisseur)) throw ErreurValidation(I18n.t('magasin.demander_achat.fournisseur_introuvable', { fournisseur }));
    return Donnees.modifier('achats', (lignes, outils) => {
      const enAttente = lignes.find((achat) => achat.article_id === article.id && achat.statut === 'demandée');
      if (enAttente) {
        throw ErreurValidation(I18n.t('magasin.demander_achat.demande_achat_attend_deja', { libelleArticle: libelleArticle(article), enAttenteId: enAttente.id }));
      }
      const id = outils.nouvelId(lignes);
      lignes.push({
        id, date: outils.aujourdhui(), article_id: article.id, fournisseur_id: fournisseur,
        quantite: valeurFichier(demandee), prix_unitaire: texte(article.prix_unitaire), statut: 'demandée', date_reception: '',
      });
      return id;
    }, { action: 'demande d\'achat de ' + nombreTexte(demandee) + ' ' + texte(article.reference) });
  }

  /** Passe un achat « demandée » à « commandée ». */
  async function commander(achatId) {
    return Donnees.modifier('achats', (lignes) => {
      const achat = ligneAchat(lignes, achatId);
      if (achat.statut !== 'demandée') {
        throw ErreurValidation(I18n.t('magasin.commander.achat_deja_sans_doute', { achatId, achatStatut: achat.statut }));
      }
      achat.statut = 'commandée';
      return achat.statut;
    }, { action: 'achat commandé' });
  }

  // Vrai si le mouvement est l'entrée en stock de la réception de cet achat (« Réception ACH-0036 »,
  // ou « Réception de la commande ACH-0033 » dans le jeu de démo).
  function estReceptionDe(mouvement, achat) {
    return mouvement.type === 'entrée' && mouvement.article_id === achat.article_id
      && /^r[ée]ception/i.test(texte(mouvement.commentaire))
      && texte(mouvement.commentaire).split(/[^A-Za-z0-9-]+/).includes(achat.id);
  }

  /**
   * Réception d'un achat « commandée » : statut « reçue », date de réception du jour, puis entrée
   * en stock « Réception ACH-… » de la quantité reçue (le prix de l'article ne change pas, D24).
   * Deux écritures enchaînées, chacune idempotente : un achat déjà reçu dont l'entrée manque (écriture
   * interrompue) reçoit son entrée ; un achat reçu avec son entrée est refusé. Renvoie l'identifiant
   * du mouvement d'entrée.
   */
  async function recevoir(achatId, quantiteRecue) {
    const recue = quantiteValide(quantiteRecue, false, I18n.t('magasin.recevoir.reception_refusee'));
    const etat = await Donnees.modifier('achats', (lignes, outils) => {
      const achat = ligneAchat(lignes, achatId);
      if (!Donnees.trouver('articles', achat.article_id)) throw ErreurValidation(I18n.t('magasin.recevoir.article_achat_introuvable', { article_id: achat.article_id, achatId }));
      if (achat.statut === 'reçue') return { achat: Object.assign({}, achat), dejaRecu: true };
      if (achat.statut !== 'commandée') {
        throw ErreurValidation(I18n.t('magasin.recevoir.achat_commandez_avant_receptionner', { achatId, achatStatut: achat.statut }));
      }
      achat.statut = 'reçue';
      achat.date_reception = outils.aujourdhui();
      return { achat: Object.assign({}, achat), dejaRecu: false };
    }, { action: 'réception de ' + nombreTexte(recue) + ' (achat ' + achatId + ')' });
    const achat = etat.achat;
    const commandee = Donnees.nombre(achat.quantite);
    // « Réception ACH-… » est un marqueur relu par le code (D156) : il reste fixe ; seul le détail est traduit.
    const detail = commandee !== null && commandee !== recue
      ? ' ' + I18n.t('magasin.recevoir.recu_commande', { recu: nombreTexte(recue), commande: nombreTexte(commandee) }) : '';
    const commentaire = 'Réception ' + achat.id + detail;
    const mouvementId = await Donnees.modifier('mouvements_stock', (lignes, outils) => {
      if (lignes.some((mouvement) => estReceptionDe(mouvement, achat))) return null;
      return nouveauMouvement(lignes, outils, { articleId: achat.article_id, type: 'entrée', quantite: recue, commentaire });
    }, { action: 'entrée en stock (réception ' + achat.id + ')' });
    if (mouvementId === null && etat.dejaRecu) {
      throw ErreurValidation(I18n.t('magasin.recevoir.achat_deja_receptionne_sans', { achatId }));
    }
    await copierStocks([achat.article_id]);
    return mouvementId;
  }

  // ===========================================================================================
  // 6. Articles et fournisseurs : création et modification (jamais de suppression : actif = 0)
  // ===========================================================================================

  /**
   * Contrôle les valeurs d'un article : [{ nom, message }] (vide si tout va bien). Référence et
   * désignation obligatoires ; référence unique parmi les articles actifs ; nombres ≥ 0 ; délai
   * entier ; fournisseur existant. idCourant : '' pour une création.
   */
  function verifierArticle(valeurs, lignesArticles, idCourant) {
    const erreurs = [];
    const courant = lignesArticles.find((ligne) => ligne.id === idCourant);
    const seraActif = valeurs.actif !== undefined ? texte(valeurs.actif) !== '0' : (!courant || estActif(courant));
    const reference = texte(valeurs.reference);
    if (!reference) erreurs.push({ nom: 'reference', message: I18n.t('magasin.verifier_article.reference_obligatoire_ex_rou') });
    else if (seraActif) {
      const double = lignesArticles.find((ligne) => ligne.id !== idCourant && estActif(ligne) && normaliser(ligne.reference) === normaliser(reference));
      if (double) erreurs.push({ nom: 'reference', message: I18n.t('magasin.verifier_article.reference_deja_celle', { reference, libelleArticle: libelleArticle(double) }) });
    }
    if (!texte(valeurs.designation)) erreurs.push({ nom: 'designation', message: I18n.t('magasin.verifier_article.designation_obligatoire') });
    CHAMPS_NOMBRES_ARTICLE.forEach((nom) => {
      if (valeurs[nom] === undefined || texte(valeurs[nom]) === '') return;
      const valeur = Donnees.nombre(valeurs[nom]);
      if (valeur === null) erreurs.push({ nom, message: I18n.t('magasin.verifier_article.saisissez_nombre_ex_4') });
      else if (valeur < 0) erreurs.push({ nom, message: I18n.t('magasin.verifier_article.valeur_peut_pas_etre') });
      else if (nom === 'delai_jours' && !Number.isInteger(valeur)) erreurs.push({ nom, message: I18n.t('magasin.verifier_article.saisissez_nombre_entier_jours') });
    });
    const fournisseur = texte(valeurs.fournisseur_id);
    if (fournisseur && !Donnees.trouver('fournisseurs', fournisseur)) erreurs.push({ nom: 'fournisseur_id', message: I18n.t('magasin.verifier_article.fournisseur_introuvable') });
    return erreurs;
  }

  // Valeurs d'article au format du fichier : seuls les champs modifiables (jamais `stock`, calculé).
  function valeursArticle(valeurs) {
    const propres = {};
    CHAMPS_ARTICLE.forEach((nom) => {
      if (valeurs[nom] === undefined) return;
      let valeur = texte(valeurs[nom]);
      if (CHAMPS_NOMBRES_ARTICLE.includes(nom) && valeur !== '') valeur = valeurFichier(Donnees.nombre(valeur));
      if (nom === 'critique' || nom === 'actif') valeur = valeur === '1' ? '1' : '0';
      propres[nom] = valeur;
    });
    return propres;
  }

  function refuserSiErreurs(erreurs) {
    if (erreurs.length) throw ErreurValidation(erreurs.map((erreur) => erreur.message).join(' '));
  }

  /** Crée un article (stock 0 : le stock vient des mouvements). Renvoie son identifiant. */
  async function creerArticle(valeurs) {
    const propres = valeursArticle(valeurs || {});
    return Donnees.modifier('articles', (lignes, outils) => {
      refuserSiErreurs(verifierArticle(propres, lignes, ''));
      const id = outils.nouvelId(lignes);
      lignes.push(Object.assign({ critique: '0', actif: '1' }, propres, { id, stock: '0' }));
      return id;
    }, { action: 'création de l\'article' });
  }

  /** Modifie un article ; renvoie la liste des champs réellement changés. */
  async function modifierArticle(articleId, valeurs) {
    const propres = valeursArticle(valeurs || {});
    return Donnees.modifier('articles', (lignes) => {
      const ligne = lignes.find((l) => l.id === articleId);
      if (!ligne) throw ErreurValidation(I18n.t('magasin.modifier_article.article_introuvable', { articleId }));
      refuserSiErreurs(verifierArticle(Object.assign({}, ligne, propres), lignes, articleId));
      const changes = Object.keys(propres).filter((nom) => texte(ligne[nom]) !== propres[nom]);
      changes.forEach((nom) => { ligne[nom] = propres[nom]; });
      return changes;
    }, { action: 'modification de l\'article' });
  }

  /** Contrôle les valeurs d'un fournisseur : nom obligatoire et unique, e-mail plausible. */
  function verifierFournisseur(valeurs, lignesFournisseurs, idCourant) {
    const erreurs = [];
    const nom = texte(valeurs.nom);
    if (!nom) erreurs.push({ nom: 'nom', message: I18n.t('magasin.verifier_fournisseur.nom_fournisseur_obligatoire') });
    else {
      const double = lignesFournisseurs.find((ligne) => ligne.id !== idCourant && normaliser(ligne.nom) === normaliser(nom));
      if (double) erreurs.push({ nom: 'nom', message: I18n.t('magasin.verifier_fournisseur.fournisseur_porte_deja_nom', { doubleId: double.id }) });
    }
    const email = texte(valeurs.email);
    if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) erreurs.push({ nom: 'email', message: I18n.t('magasin.verifier_fournisseur.adresse_e_mail_incomplete') });
    return erreurs;
  }

  function valeursFournisseur(valeurs) {
    const propres = {};
    CHAMPS_FOURNISSEUR.forEach((nom) => { if (valeurs[nom] !== undefined) propres[nom] = texte(valeurs[nom]); });
    return propres;
  }

  /** Crée un fournisseur ; renvoie son identifiant. */
  async function creerFournisseur(valeurs) {
    const propres = valeursFournisseur(valeurs || {});
    return Donnees.modifier('fournisseurs', (lignes, outils) => {
      refuserSiErreurs(verifierFournisseur(propres, lignes, ''));
      const id = outils.nouvelId(lignes);
      lignes.push(Object.assign({}, propres, { id }));
      return id;
    }, { action: 'création du fournisseur' });
  }

  /** Modifie un fournisseur ; renvoie la liste des champs réellement changés. */
  async function modifierFournisseur(fournisseurId, valeurs) {
    const propres = valeursFournisseur(valeurs || {});
    return Donnees.modifier('fournisseurs', (lignes) => {
      const ligne = lignes.find((l) => l.id === fournisseurId);
      if (!ligne) throw ErreurValidation(I18n.t('magasin.modifier_fournisseur.fournisseur_introuvable', { fournisseurId }));
      refuserSiErreurs(verifierFournisseur(Object.assign({}, ligne, propres), lignes, fournisseurId));
      const changes = Object.keys(propres).filter((nom) => texte(ligne[nom]) !== propres[nom]);
      changes.forEach((nom) => { ligne[nom] = propres[nom]; });
      return changes;
    }, { action: 'modification du fournisseur' });
  }

  // Contrôles prêtés aux écrans du module (affichage des erreurs sous les champs).
  Object.assign(Magasin.interne, { verifierArticle, verifierFournisseur, utilisateurCourant });

  return {
    // écritures (ARCHITECTURE.md §14.4)
    sortir, retourner, entrer, inventorier,
    demanderAchat, commander, recevoir,
    creerArticle, modifierArticle, creerFournisseur, modifierFournisseur,
    mettreAJourStocks,
  };
})());
