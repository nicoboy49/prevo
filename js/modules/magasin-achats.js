'use strict';
// Magasin (5/5) — onglets « À commander » (Magasin.aCommander(), « Demander l'achat »), « Achats »
// (demandées, commandées, reçues ; « Commander », « Réceptionner ») et « Fournisseurs » (liste,
// création, modification) de l'écran #/magasin ; puis l'enregistrement des écrans du module
// auprès d'App (ARCHITECTURE.md §8, §14.2 et §14.4). Dernier fichier du module : les écrans des
// fichiers précédents existent déjà. Complète l'objet Magasin.

Object.assign(Magasin, (() => {

  // Outils et écrans de magasin-regles.js, magasin-ecritures.js et magasin-articles.js.
  const { texte, normaliser, libelleArticle, listeAdaptative, lienArticle, quantiteUnite, libelleFournisseur,
    achatsEnCours, listeArticles, listeFournisseurs, definitionChamp, fenetreSaisie, apresEcriture,
    afficherMagasin, afficherFicheArticle, afficherNouvelArticle } = Magasin.interne;

  const LIMITE_RECUES = 20;                    // achats reçus montrés avant « Voir tout »
  const memoire = { rechercheAchats: '', toutesRecues: false };

  // Clic sur un bouton [data-action] d'un panneau (tableau sur grand écran ou cartes sur
  // téléphone) : un seul écouteur par panneau.
  function surAction(panneau, actions) {
    panneau.addEventListener('click', (evenement) => {
      const bouton = evenement.target.closest('button[data-action]');
      if (!bouton || !panneau.contains(bouton) || !actions[bouton.dataset.action]) return;
      actions[bouton.dataset.action](bouton.dataset);
    });
  }

  // ===========================================================================================
  // 14. Onglet « À commander » et fenêtre « Demander l'achat »
  // ===========================================================================================

  function enCoursHtml(achats) {
    return UI.html`${achats.map((achat) => UI.html`<span class="magasin-achat-en-cours">${achat.id} ${UI.badgeValeur('achats', 'statut', achat.statut)}
      <span class="muted">${UI.nombreFr(achat.quantite)}</span></span> `)}`;
  }

  // Bouton « Demander l'achat » : pas si une demande attend déjà d'être commandée (elle serait refusée).
  function boutonDemande(ligne) {
    if (!App.estResponsable() || ligne.enCours.some((achat) => achat.statut === 'demandée')) return '';
    return UI.html`<button type="button" class="btn btn-secondaire" data-action="demander-achat" data-article="${ligne.id}"
      data-quantite="${String(ligne.quantiteProposee)}">${I18n.t('magasin.bouton_demande.demander_achat')}</button>`;
  }

  function afficherOngletACommander(panneau) {
    const lignes = Magasin.aCommander().map((entree) => ({
      id: entree.article.id, article: entree.article, reference: entree.article.reference,
      designation: entree.article.designation, stock: entree.stock, pointCommande: entree.pointCommande,
      quantiteProposee: entree.quantiteProposee, fournisseur: libelleFournisseur(entree.article.fournisseur_id),
      enCours: achatsEnCours(entree.article.id),
    }));
    const liste = listeAdaptative({
      lignes, libelle: I18n.t('magasin.onglet_acommander.articles_commander'), vide: I18n.t('magasin.onglet_acommander.aucun_article_commander_tous'),
      colonnes: [
        { cle: 'reference', libelle: I18n.t('commun.champ.reference'), rendu: (l) => lienArticle(l.article) },
        { cle: 'designation', libelle: I18n.t('commun.champ.designation'), rendu: (l) => UI.html`${l.designation}${l.article.critique === '1' ? UI.html` <span class="badge violet">${I18n.t('magasin.onglet_acommander.critique')}</span>` : ''}` },
        { cle: 'stock', libelle: I18n.t('magasin.onglet_acommander.stock'), type: 'nombre', rendu: (l) => quantiteUnite(l.stock, l.article.unite) },
        { cle: 'pointCommande', libelle: I18n.t('magasin.onglet_acommander.point_commande'), type: 'nombre', rendu: (l) => UI.nombreFr(l.pointCommande) },
        { cle: 'quantiteProposee', libelle: I18n.t('magasin.onglet_acommander.quantite_proposee'), type: 'nombre', rendu: (l) => UI.html`<b>${UI.nombreFr(l.quantiteProposee)}</b>` },
        { cle: 'fournisseur', libelle: I18n.t('magasin.onglet_acommander.fournisseur') },
        { cle: 'achat', libelle: I18n.t('magasin.onglet_acommander.achat'), triable: false, rendu: (l) => UI.html`${enCoursHtml(l.enCours)}${boutonDemande(l)}` },
      ],
      carte: (l) => UI.html`<div class="carte-ligne">
        <div class="carte-tete">${lienArticle(l.article)}${l.article.critique === '1' ? UI.html`<span class="badge violet">${I18n.t('magasin.onglet_acommander.critique')}</span>` : ''}</div>
        <div class="carte-titre">${l.designation}</div>
        <div class="carte-meta">${I18n.html('magasin.onglet_acommander.stock_point_commande_propose', { quantiteUnite: quantiteUnite(l.stock, l.article.unite), pointCommande: UI.nombreFr(l.pointCommande), quantiteProposee: UI.nombreFr(l.quantiteProposee) })}${l.fournisseur ? UI.html`<span>${l.fournisseur}</span>` : ''}</div>
        ${l.enCours.length ? UI.html`<div class="carte-meta">${enCoursHtml(l.enCours)}</div>` : ''}
        ${boutonDemande(l) ? UI.html`<div class="actions">${boutonDemande(l)}</div>` : ''}</div>`,
    });
    UI.remplir(panneau, UI.html`
      <p class="note magasin-intro">${I18n.t('magasin.onglet_acommander.articles_actifs_dont_stock')}</p>
      <div class="carte magasin-liste magasin-a-commander"></div>`);
    UI.$('.magasin-liste', panneau).appendChild(liste);
    surAction(panneau, {
      'demander-achat': (donnees) => {
        const article = Donnees.trouver('articles', donnees.article);
        if (article) ouvrirDemandeAchat(article, Number(donnees.quantite));
      },
    });
  }

  /** Fenêtre « Demander l'achat » : quantité (proposée par défaut) et fournisseur. */
  async function ouvrirDemandeAchat(article, quantiteProposee) {
    const proposee = quantiteProposee > 0 ? quantiteProposee
      : ((Magasin.aCommander().find((entree) => entree.article.id === article.id) || {}).quantiteProposee
        || Donnees.nombre(article.qte_commande) || 1);
    const champs = [
      UI.champ(definitionChamp('achats', 'quantite', { libelle: article.unite ? I18n.t('magasin.ouvrir_demande_achat.quantite_commander', { unite: article.unite }) : I18n.t('magasin.ouvrir_demande_achat.quantite_commander_2') }),
        String(proposee), { obligatoire: true }),
      UI.champ(definitionChamp('achats', 'fournisseur_id'), article.fournisseur_id, { liste: listeFournisseurs(), aide: I18n.t('magasin.ouvrir_demande_achat.vide_fournisseur_habituel_article') }),
    ];
    const id = await fenetreSaisie({
      titre: I18n.t('magasin.bouton_demande.demander_achat'), champs, libelleValider: I18n.t('magasin.bouton_demande.demander_achat'),
      introduction: UI.html`<p>${I18n.html('magasin.ouvrir_demande_achat.stock_prix_unitaire_actuel', { libelleArticle: libelleArticle(article), quantiteUnite: quantiteUnite(Donnees.stockArticle(article.id), article.unite), euro: UI.euro(article.prix_unitaire) })}</p>`,
      action: (valeurs) => Magasin.demanderAchat(article.id, valeurs.quantite, valeurs.fournisseur_id || undefined),
    });
    if (id) await apresEcriture(I18n.t('magasin.ouvrir_demande_achat.demande_achat_enregistree', { id }));
  }

  /** Fenêtre « Nouvelle demande d'achat » (onglet Achats) : l'article est choisi dans la liste. */
  async function ouvrirNouvelleDemande() {
    const champs = [
      UI.champ(definitionChamp('achats', 'article_id'), '', { liste: listeArticles(true), obligatoire: true }),
      UI.champ(definitionChamp('achats', 'quantite'), '', { obligatoire: true }),
      UI.champ(definitionChamp('achats', 'fournisseur_id'), '', { liste: listeFournisseurs(), aide: I18n.t('magasin.ouvrir_demande_achat.vide_fournisseur_habituel_article') }),
    ];
    const id = await fenetreSaisie({
      titre: I18n.t('magasin.ouvrir_nouvelle_demande.nouvelle_demande_achat'), champs, libelleValider: I18n.t('magasin.bouton_demande.demander_achat'),
      action: (valeurs) => Magasin.demanderAchat(valeurs.article_id, valeurs.quantite, valeurs.fournisseur_id || undefined),
    });
    if (id) await apresEcriture(I18n.t('magasin.ouvrir_demande_achat.demande_achat_enregistree', { id }));
  }

  // ===========================================================================================
  // 15. Onglet « Achats » : demandées, commandées, reçues
  // ===========================================================================================

  function sectionsAchats() {
    return [
      { statut: 'demandée', titre: I18n.t('magasin.sections_achats.demandees'), aide: I18n.t('magasin.sections_achats.passer_chez_fournisseur') },
      { statut: 'commandée', titre: I18n.t('magasin.sections_achats.commandees'), aide: I18n.t('magasin.sections_achats.attente_livraison') },
      { statut: 'reçue', titre: I18n.t('magasin.sections_achats.recues'), aide: I18n.t('magasin.sections_achats.entrees_stock_reception') },
    ];
  }

  function actionAchat(achat) {
    if (!App.estResponsable()) return '';
    if (achat.statut === 'demandée') {
      return UI.html`<button type="button" class="btn btn-secondaire" data-action="commander" data-achat="${achat.id}">${I18n.t('magasin.action_achat.commander')}</button>`;
    }
    if (achat.statut === 'commandée') {
      return UI.html`<button type="button" class="btn btn-primaire" data-action="receptionner" data-achat="${achat.id}">${I18n.t('magasin.action_achat.receptionner')}</button>`;
    }
    return '';
  }

  function montant(achat) {
    const quantite = Donnees.nombre(achat.quantite);
    const prix = Donnees.nombre(achat.prix_unitaire);
    return quantite === null || prix === null ? null : quantite * prix;
  }

  // Colonnes d'une section : la date de réception pour les reçus, le bouton d'action pour les
  // autres (responsable) — peu de colonnes, pour que le bouton reste visible sans défiler.
  function listeAchats(achats, statut) {
    const article = (achat) => Donnees.trouver('articles', achat.article_id);
    const colonnes = [
      { cle: 'id', libelle: I18n.t('magasin.liste_achats.date'), rendu: (a) => UI.html`<b>${a.id}</b><small class="magasin-sous-ligne">${UI.dateFr(a.date)}</small>` },
      { cle: 'article_id', libelle: I18n.t('commun.champ.article'), classe: 'magasin-col-designation', valeurTri: (a) => texte((article(a) || {}).reference),
        rendu: (a) => (article(a) ? UI.html`${lienArticle(article(a))}<small class="magasin-sous-ligne">${article(a).designation}</small>` : a.article_id) },
      { cle: 'fournisseur_id', libelle: I18n.t('magasin.onglet_acommander.fournisseur'), valeurTri: (a) => libelleFournisseur(a.fournisseur_id), rendu: (a) => libelleFournisseur(a.fournisseur_id) },
      { cle: 'quantite', libelle: I18n.t('commun.champ.quantite'), type: 'nombre', rendu: (a) => UI.nombreFr(a.quantite) },
      { cle: 'montant', libelle: I18n.t('magasin.liste_achats.montant'), type: 'nombre', valeurTri: montant,
        rendu: (a) => UI.html`${I18n.html('magasin.liste_achats.euro_euro2_unite', { euro: UI.euro(montant(a)), prixUnitaire: UI.euro(a.prix_unitaire) })}` },
    ];
    if (statut === 'reçue') colonnes.push({ cle: 'date_reception', libelle: I18n.t('magasin.liste_achats.recu'), classe: 'sans-coupure', rendu: (a) => UI.dateFr(a.date_reception) });
    else if (App.estResponsable()) colonnes.push({ cle: 'action', libelle: '', triable: false, rendu: actionAchat });
    return listeAdaptative({
      lignes: achats, libelle: I18n.t('magasin.liste_achats.achats'), vide: I18n.t('magasin.liste_achats.aucun_achat'), colonnes,
      carte: (a) => UI.html`<div class="carte-ligne">
        <div class="carte-tete"><b>${a.id}</b>${UI.badgeValeur('achats', 'statut', a.statut)}</div>
        <div class="carte-titre">${article(a) ? libelleArticle(article(a)) : a.article_id}</div>
        <div class="carte-meta">${I18n.html('magasin.liste_achats.date_quantite_quantite_euro', { date: UI.dateFr(a.date), quantite: UI.nombreFr(a.quantite), euro: UI.euro(montant(a)) })}${a.fournisseur_id ? UI.html`<span>${libelleFournisseur(a.fournisseur_id)}</span>` : ''}
          ${a.date_reception ? UI.html`<span>${I18n.t('magasin.liste_achats.recu_date_reception', { date_reception: UI.dateFr(a.date_reception) })}</span>` : ''}</div>
        ${actionAchat(a) ? UI.html`<div class="actions">${actionAchat(a)}</div>` : ''}</div>`,
    });
  }

  function garderAchat(achat, recherche) {
    if (!recherche) return true;
    const article = Donnees.trouver('articles', achat.article_id) || {};
    return normaliser([achat.id, article.reference, article.designation, libelleFournisseur(achat.fournisseur_id)].join(' ')).includes(recherche);
  }

  function afficherOngletAchats(panneau, requete) {
    if (requete && requete.has('recherche')) memoire.rechercheAchats = requete.get('recherche');
    UI.remplir(panneau, UI.html`
      <div class="magasin-barre">
        <form class="filtres magasin-filtres" id="magasin-filtres-achats" data-hors-saisie role="search" aria-label="${I18n.t('magasin.onglet_achats.filtrer_achats')}">
          <label class="visuellement-cache" for="magasin-recherche-achat">${I18n.t('magasin.onglet_achats.rechercher_achat')}</label>
          <input type="search" id="magasin-recherche-achat" name="recherche" value="${memoire.rechercheAchats}" placeholder="${I18n.t('magasin.onglet_achats.article_fournisseur')}" autocomplete="off">
        </form>
        ${App.estResponsable() ? UI.html`<button type="button" class="btn btn-primaire" id="magasin-nouvelle-demande">${UI.icone('ajouter')}${I18n.t('magasin.ouvrir_nouvelle_demande.nouvelle_demande_achat')}</button>` : ''}
      </div>
      <div class="magasin-sections-achats"></div>`);
    const zone = UI.$('.magasin-sections-achats', panneau);
    function rafraichir() {
      const recherche = normaliser(memoire.rechercheAchats);
      const achats = Donnees.lignes('achats').filter((achat) => garderAchat(achat, recherche))
        .sort((a, b) => texte(b.date).localeCompare(texte(a.date)) || texte(b.id).localeCompare(texte(a.id), 'fr', { numeric: true }));
      zone.textContent = '';
      sectionsAchats().forEach((section) => {
        const tous = achats.filter((achat) => achat.statut === section.statut);
        const limite = section.statut === 'reçue' && !memoire.toutesRecues;
        const carte = UI.element(UI.html`<section class="carte magasin-achats" data-statut="${section.statut}">
          <div class="entete-carte"><h2>${section.titre} <span class="badge">${tous.length}</span></h2><span class="muted">${section.aide}</span></div>
          <div class="magasin-zone"></div>
          ${limite && tous.length > LIMITE_RECUES ? UI.html`<div class="actions"><button type="button" class="btn btn-secondaire" data-action="voir-recues">${I18n.t('magasin.onglet_achats.voir_achats_recus', { n: tous.length })}</button></div>` : ''}
        </section>`);
        UI.$('.magasin-zone', carte).appendChild(listeAchats(limite ? tous.slice(0, LIMITE_RECUES) : tous, section.statut));
        zone.appendChild(carte);
      });
    }
    const formulaire = UI.$('#magasin-filtres-achats', panneau);
    formulaire.addEventListener('input', () => { memoire.rechercheAchats = UI.lireFormulaire(formulaire).recherche; rafraichir(); });
    formulaire.addEventListener('submit', (evenement) => evenement.preventDefault());
    const nouvelle = UI.$('#magasin-nouvelle-demande', panneau);
    if (nouvelle) nouvelle.addEventListener('click', ouvrirNouvelleDemande);
    surAction(panneau, {
      commander: (donnees) => commanderAchat(donnees.achat),
      receptionner: (donnees) => ouvrirReception(donnees.achat),
      'voir-recues': () => { memoire.toutesRecues = true; rafraichir(); },
    });
    rafraichir();
  }

  async function commanderAchat(achatId) {
    try {
      await Magasin.commander(achatId);
      await apresEcriture(I18n.t('magasin.commander_achat.achat_commande', { achatId }));
    } catch (erreur) {
      App.signalerErreur(erreur, 'commande de l\'achat');
    }
  }

  /** Fenêtre « Réceptionner » : quantité reçue (la quantité commandée par défaut). */
  async function ouvrirReception(achatId) {
    const achat = Donnees.trouver('achats', achatId);
    if (!achat) { UI.toast(I18n.t('magasin.ouvrir_reception.achat_introuvable_actualisez', { achatId }), 'attention'); return; }
    const article = Donnees.trouver('articles', achat.article_id);
    const unite = article && article.unite ? ' (' + article.unite + ')' : '';
    const champs = [UI.champ({ nom: 'quantite_recue', type: 'decimal', libelle: I18n.t('magasin.ouvrir_reception.quantite_recue', { unite }) }, achat.quantite, { obligatoire: true })];
    const id = await fenetreSaisie({
      titre: I18n.t('magasin.ouvrir_reception.receptionner_achat_id', { achatId }), champs, libelleValider: I18n.t('magasin.action_achat.receptionner'),
      introduction: UI.html`<p>${I18n.html('magasin.ouvrir_reception.v1_commande_quantite_unite', { article: article ? libelleArticle(article) : achat.article_id, quantite: UI.nombreFr(achat.quantite), unite, libelleFournisseur: libelleFournisseur(achat.fournisseur_id) })}</p><p class="note">${I18n.t('magasin.ouvrir_reception.quantite_recue_entre_stock')}</p>`,
      action: (valeurs) => Magasin.recevoir(achatId, valeurs.quantite_recue),
    });
    if (id) await apresEcriture(I18n.t('magasin.ouvrir_reception.achat_receptionne_entree_stock', { achatId }));
  }

  // ===========================================================================================
  // 16. Onglet « Fournisseurs » : liste, création, modification
  // ===========================================================================================

  async function ouvrirFournisseur(fournisseurId) {
    const existant = fournisseurId ? Donnees.trouver('fournisseurs', fournisseurId) : null;
    if (fournisseurId && !existant) { UI.toast(I18n.t('magasin.ouvrir_fournisseur.fournisseur_existe_plus_actualisez'), 'attention'); return; }
    const valeur = (nom) => (existant ? existant[nom] : '');
    const champs = [
      UI.champ(definitionChamp('fournisseurs', 'nom'), valeur('nom'), { obligatoire: true, attributs: { maxlength: '120' } }),
      UI.champ(definitionChamp('fournisseurs', 'contact'), valeur('contact')),
      UI.champ(definitionChamp('fournisseurs', 'telephone'), valeur('telephone'), { attributs: { inputmode: 'tel' } }),
      UI.champ(definitionChamp('fournisseurs', 'email'), valeur('email'), { attributs: { inputmode: 'email' } }),
    ];
    const resultat = await fenetreSaisie({
      titre: existant ? I18n.t('magasin.ouvrir_fournisseur.modifier_fournisseur') : I18n.t('magasin.ouvrir_fournisseur.nouveau_fournisseur'), champs,
      verifier: (valeurs) => Magasin.interne.verifierFournisseur(valeurs, Donnees.lignes('fournisseurs'), existant ? existant.id : ''),
      action: async (valeurs) => (existant ? (await Magasin.modifierFournisseur(existant.id, valeurs), existant.id) : Magasin.creerFournisseur(valeurs)),
    });
    if (resultat) await apresEcriture(existant ? I18n.t('magasin.ouvrir_fournisseur.fournisseur_enregistre') : I18n.t('magasin.ouvrir_fournisseur.fournisseur_cree', { resultat }));
  }

  function afficherOngletFournisseurs(panneau) {
    const responsable = App.estResponsable();
    const nombreArticles = (id) => Donnees.lignes('articles').filter((article) => article.fournisseur_id === id).length;
    const lignes = Donnees.lignes('fournisseurs').map((f) => Object.assign({}, f, { articles: nombreArticles(f.id) }))
      .sort((a, b) => texte(a.nom).localeCompare(texte(b.nom), 'fr'));
    const telephone = (f) => (f.telephone ? UI.html`<a href="tel:${f.telephone.replace(/[^0-9+]/g, '')}">${f.telephone}</a>` : '');
    const email = (f) => (f.email ? UI.html`<a href="mailto:${f.email}">${f.email}</a>` : '');
    const bouton = (f) => (responsable ? UI.html`<button type="button" class="btn btn-secondaire" data-action="modifier-fournisseur" data-fournisseur="${f.id}">${I18n.t('commun.bouton.modifier')}</button>` : '');
    const liste = listeAdaptative({
      lignes, libelle: I18n.t('magasin.onglet_fournisseurs.fournisseurs'), vide: I18n.t('magasin.onglet_fournisseurs.aucun_fournisseur_enregistre'),
      colonnes: [
        { cle: 'nom', libelle: I18n.t('magasin.onglet_fournisseurs.nom'), rendu: (f) => UI.html`<b>${f.nom || f.id}</b>` },
        { cle: 'contact', libelle: I18n.t('magasin.onglet_fournisseurs.contact') },
        { cle: 'telephone', libelle: I18n.t('magasin.onglet_fournisseurs.telephone'), classe: 'sans-coupure', rendu: telephone },
        { cle: 'email', libelle: 'E-mail', rendu: email },
        { cle: 'articles', libelle: I18n.t('magasin.onglet_fournisseurs.articles'), type: 'nombre' },
        { cle: 'action', libelle: '', triable: false, rendu: bouton },
      ],
      carte: (f) => UI.html`<div class="carte-ligne"><div class="carte-tete">${I18n.html('magasin.onglet_fournisseurs.v1_n_article', { n: f.articles, nom: f.nom || f.id })}</div>
        <div class="carte-meta">${f.contact ? UI.html`<span>${f.contact}</span>` : ''}${f.telephone ? UI.html`<span>${telephone(f)}</span>` : ''}
          ${f.email ? UI.html`<span class="magasin-coupable">${email(f)}</span>` : ''}</div>
        ${responsable ? UI.html`<div class="actions">${bouton(f)}</div>` : ''}</div>`,
    });
    UI.remplir(panneau, UI.html`
      ${responsable ? UI.html`<div class="magasin-barre"><span class="espace"></span>
        <button type="button" class="btn btn-primaire" id="magasin-nouveau-fournisseur">${UI.icone('ajouter')}${I18n.t('magasin.ouvrir_fournisseur.nouveau_fournisseur')}</button></div>` : ''}
      <div class="carte magasin-liste"></div>`);
    UI.$('.magasin-liste', panneau).appendChild(liste);
    const nouveau = UI.$('#magasin-nouveau-fournisseur', panneau);
    if (nouveau) nouveau.addEventListener('click', () => ouvrirFournisseur(''));
    surAction(panneau, { 'modifier-fournisseur': (donnees) => ouvrirFournisseur(donnees.fournisseur) });
  }

  // Écrans et fenêtres prêtés aux fichiers précédents (appelés par relais) : usage interne.
  Object.assign(Magasin.interne, { afficherOngletACommander, afficherOngletAchats, afficherOngletFournisseurs, ouvrirDemandeAchat });

  // ===========================================================================================
  // 17. Enregistrement des écrans (App est chargé après les modules : on attend la page)
  // ===========================================================================================

  document.addEventListener('DOMContentLoaded', () => {
    const tables = ['articles', 'mouvements_stock', 'achats', 'fournisseurs', 'article_equipement', 'ordres_travail'];
    App.ecran({
      id: 'magasin', route: /^#\/magasin$/, get titre() { return I18n.t('magasin.titre.magasin'); },
      menu: { get libelle() { return I18n.t('magasin.titre.magasin'); }, icone: 'magasin', ordre: 45 },
      profils: ['technicien', 'responsable'], tables,
      afficher: afficherMagasin,
    });
    // « nouveau » avant la fiche : la première route qui correspond gagne ; la route fiche
    // l'exclut en plus (ARCHITECTURE.md §14.2).
    App.ecran({
      id: 'magasin-article-nouveau', route: /^#\/magasin\/article\/nouveau$/, get titre() { return I18n.t('magasin.titre.nouvel_article'); }, parent: 'magasin',
      profils: ['responsable'], tables: [],
      afficher: afficherNouvelArticle,
    });
    App.ecran({
      id: 'magasin-article', route: /^#\/magasin\/article\/(?!nouveau$)(?<id>[^/?]+)$/, get titre() { return I18n.t('magasin.ecran_article.titre'); }, parent: 'magasin',
      profils: ['technicien', 'responsable'], tables: tables.concat(['equipements']),
      afficher: afficherFicheArticle,
    });
  });

  return {};
})());
