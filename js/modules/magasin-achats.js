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
    return UI.html`${achats.map((achat) => UI.html`<span class="magasin-achat-en-cours">${achat.id} ${UI.badgeStatut(achat.statut)}
      <span class="muted">${UI.nombreFr(achat.quantite)}</span></span> `)}`;
  }

  // Bouton « Demander l'achat » : pas si une demande attend déjà d'être commandée (elle serait refusée).
  function boutonDemande(ligne) {
    if (!App.estResponsable() || ligne.enCours.some((achat) => achat.statut === 'demandée')) return '';
    return UI.html`<button type="button" class="btn btn-secondaire" data-action="demander-achat" data-article="${ligne.id}"
      data-quantite="${String(ligne.quantiteProposee)}">Demander l'achat</button>`;
  }

  function afficherOngletACommander(panneau) {
    const lignes = Magasin.aCommander().map((entree) => ({
      id: entree.article.id, article: entree.article, reference: entree.article.reference,
      designation: entree.article.designation, stock: entree.stock, pointCommande: entree.pointCommande,
      quantiteProposee: entree.quantiteProposee, fournisseur: libelleFournisseur(entree.article.fournisseur_id),
      enCours: achatsEnCours(entree.article.id),
    }));
    const liste = listeAdaptative({
      lignes, libelle: 'Articles à commander', vide: 'Aucun article à commander : tous les stocks sont au-dessus de leur point de commande.',
      colonnes: [
        { cle: 'reference', libelle: 'Référence', rendu: (l) => lienArticle(l.article) },
        { cle: 'designation', libelle: 'Désignation', rendu: (l) => UI.html`${l.designation}${l.article.critique === '1' ? UI.html` <span class="badge violet">Critique</span>` : ''}` },
        { cle: 'stock', libelle: 'Stock', type: 'nombre', rendu: (l) => quantiteUnite(l.stock, l.article.unite) },
        { cle: 'pointCommande', libelle: 'Point de commande', type: 'nombre', rendu: (l) => UI.nombreFr(l.pointCommande) },
        { cle: 'quantiteProposee', libelle: 'Quantité proposée', type: 'nombre', rendu: (l) => UI.html`<b>${UI.nombreFr(l.quantiteProposee)}</b>` },
        { cle: 'fournisseur', libelle: 'Fournisseur' },
        { cle: 'achat', libelle: 'Achat', triable: false, rendu: (l) => UI.html`${enCoursHtml(l.enCours)}${boutonDemande(l)}` },
      ],
      carte: (l) => UI.html`<div class="carte-ligne">
        <div class="carte-tete">${lienArticle(l.article)}${l.article.critique === '1' ? UI.html`<span class="badge violet">Critique</span>` : ''}</div>
        <div class="carte-titre">${l.designation}</div>
        <div class="carte-meta"><span>Stock : ${quantiteUnite(l.stock, l.article.unite)}</span><span>Point de commande : ${UI.nombreFr(l.pointCommande)}</span>
          <span>Proposé : <b>${UI.nombreFr(l.quantiteProposee)}</b></span>${l.fournisseur ? UI.html`<span>${l.fournisseur}</span>` : ''}</div>
        ${l.enCours.length ? UI.html`<div class="carte-meta">${enCoursHtml(l.enCours)}</div>` : ''}
        ${boutonDemande(l) ? UI.html`<div class="actions">${boutonDemande(l)}</div>` : ''}</div>`,
    });
    UI.remplir(panneau, UI.html`
      <p class="note magasin-intro">Articles actifs dont le stock est au point de commande ou en dessous (RG6). Quantité proposée :
        la quantité à commander de l'article, sinon point de commande − stock + stock de sécurité.</p>
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
      UI.champ(definitionChamp('achats', 'quantite', { libelle: 'Quantité à commander' + (article.unite ? ' (' + article.unite + ')' : '') }),
        String(proposee), { obligatoire: true }),
      UI.champ(definitionChamp('achats', 'fournisseur_id'), article.fournisseur_id, { liste: listeFournisseurs(), aide: 'Vide : fournisseur habituel de l\'article.' }),
    ];
    const id = await fenetreSaisie({
      titre: 'Demander l\'achat', champs, libelleValider: 'Demander l\'achat',
      introduction: UI.html`<p><b>${libelleArticle(article)}</b> — stock : ${quantiteUnite(Donnees.stockArticle(article.id), article.unite)},
        prix unitaire actuel : ${UI.euro(article.prix_unitaire)}.</p>`,
      action: (valeurs) => Magasin.demanderAchat(article.id, valeurs.quantite, valeurs.fournisseur_id || undefined),
    });
    if (id) await apresEcriture('Demande d\'achat ' + id + ' enregistrée.');
  }

  /** Fenêtre « Nouvelle demande d'achat » (onglet Achats) : l'article est choisi dans la liste. */
  async function ouvrirNouvelleDemande() {
    const champs = [
      UI.champ(definitionChamp('achats', 'article_id'), '', { liste: listeArticles(true), obligatoire: true }),
      UI.champ(definitionChamp('achats', 'quantite'), '', { obligatoire: true }),
      UI.champ(definitionChamp('achats', 'fournisseur_id'), '', { liste: listeFournisseurs(), aide: 'Vide : fournisseur habituel de l\'article.' }),
    ];
    const id = await fenetreSaisie({
      titre: 'Nouvelle demande d\'achat', champs, libelleValider: 'Demander l\'achat',
      action: (valeurs) => Magasin.demanderAchat(valeurs.article_id, valeurs.quantite, valeurs.fournisseur_id || undefined),
    });
    if (id) await apresEcriture('Demande d\'achat ' + id + ' enregistrée.');
  }

  // ===========================================================================================
  // 15. Onglet « Achats » : demandées, commandées, reçues
  // ===========================================================================================

  const SECTIONS_ACHATS = [
    { statut: 'demandée', titre: 'Demandées', aide: 'À passer chez le fournisseur.' },
    { statut: 'commandée', titre: 'Commandées', aide: 'En attente de livraison.' },
    { statut: 'reçue', titre: 'Reçues', aide: 'Entrées en stock à la réception.' },
  ];

  function actionAchat(achat) {
    if (!App.estResponsable()) return '';
    if (achat.statut === 'demandée') {
      return UI.html`<button type="button" class="btn btn-secondaire" data-action="commander" data-achat="${achat.id}">Commander</button>`;
    }
    if (achat.statut === 'commandée') {
      return UI.html`<button type="button" class="btn btn-primaire" data-action="receptionner" data-achat="${achat.id}">Réceptionner</button>`;
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
      { cle: 'id', libelle: 'N° et date', rendu: (a) => UI.html`<b>${a.id}</b><small class="magasin-sous-ligne">${UI.dateFr(a.date)}</small>` },
      { cle: 'article_id', libelle: 'Article', classe: 'magasin-col-designation', valeurTri: (a) => texte((article(a) || {}).reference),
        rendu: (a) => (article(a) ? UI.html`${lienArticle(article(a))}<small class="magasin-sous-ligne">${article(a).designation}</small>` : a.article_id) },
      { cle: 'fournisseur_id', libelle: 'Fournisseur', valeurTri: (a) => libelleFournisseur(a.fournisseur_id), rendu: (a) => libelleFournisseur(a.fournisseur_id) },
      { cle: 'quantite', libelle: 'Quantité', type: 'nombre', rendu: (a) => UI.nombreFr(a.quantite) },
      { cle: 'montant', libelle: 'Montant', type: 'nombre', valeurTri: montant,
        rendu: (a) => UI.html`${UI.euro(montant(a))}<small class="magasin-sous-ligne">${UI.euro(a.prix_unitaire)} l'unité</small>` },
    ];
    if (statut === 'reçue') colonnes.push({ cle: 'date_reception', libelle: 'Reçu le', classe: 'sans-coupure', rendu: (a) => UI.dateFr(a.date_reception) });
    else if (App.estResponsable()) colonnes.push({ cle: 'action', libelle: '', triable: false, rendu: actionAchat });
    return listeAdaptative({
      lignes: achats, libelle: 'Achats', vide: 'Aucun achat.', colonnes,
      carte: (a) => UI.html`<div class="carte-ligne">
        <div class="carte-tete"><b>${a.id}</b>${UI.badgeStatut(a.statut)}</div>
        <div class="carte-titre">${article(a) ? libelleArticle(article(a)) : a.article_id}</div>
        <div class="carte-meta"><span>${UI.dateFr(a.date)}</span><span>Quantité : ${UI.nombreFr(a.quantite)}</span>
          <span>${UI.euro(montant(a))}</span>${a.fournisseur_id ? UI.html`<span>${libelleFournisseur(a.fournisseur_id)}</span>` : ''}
          ${a.date_reception ? UI.html`<span>Reçu le ${UI.dateFr(a.date_reception)}</span>` : ''}</div>
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
        <form class="filtres magasin-filtres" id="magasin-filtres-achats" data-hors-saisie role="search" aria-label="Filtrer les achats">
          <label class="visuellement-cache" for="magasin-recherche-achat">Rechercher un achat</label>
          <input type="search" id="magasin-recherche-achat" name="recherche" value="${memoire.rechercheAchats}" placeholder="N°, article ou fournisseur" autocomplete="off">
        </form>
        ${App.estResponsable() ? UI.html`<button type="button" class="btn btn-primaire" id="magasin-nouvelle-demande">${UI.icone('ajouter')}Nouvelle demande d'achat</button>` : ''}
      </div>
      <div class="magasin-sections-achats"></div>`);
    const zone = UI.$('.magasin-sections-achats', panneau);
    function rafraichir() {
      const recherche = normaliser(memoire.rechercheAchats);
      const achats = Donnees.lignes('achats').filter((achat) => garderAchat(achat, recherche))
        .sort((a, b) => texte(b.date).localeCompare(texte(a.date)) || texte(b.id).localeCompare(texte(a.id), 'fr', { numeric: true }));
      zone.textContent = '';
      SECTIONS_ACHATS.forEach((section) => {
        const tous = achats.filter((achat) => achat.statut === section.statut);
        const limite = section.statut === 'reçue' && !memoire.toutesRecues;
        const carte = UI.element(UI.html`<section class="carte magasin-achats" data-statut="${section.statut}">
          <div class="entete-carte"><h2>${section.titre} <span class="badge">${tous.length}</span></h2><span class="muted">${section.aide}</span></div>
          <div class="magasin-zone"></div>
          ${limite && tous.length > LIMITE_RECUES ? UI.html`<div class="actions"><button type="button" class="btn btn-secondaire" data-action="voir-recues">Voir les ${tous.length} achats reçus</button></div>` : ''}
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
      await apresEcriture('Achat ' + achatId + ' commandé.');
    } catch (erreur) {
      App.signalerErreur(erreur, 'commande de l\'achat');
    }
  }

  /** Fenêtre « Réceptionner » : quantité reçue (la quantité commandée par défaut). */
  async function ouvrirReception(achatId) {
    const achat = Donnees.trouver('achats', achatId);
    if (!achat) { UI.toast('L\'achat ' + achatId + ' est introuvable : actualisez.', 'attention'); return; }
    const article = Donnees.trouver('articles', achat.article_id);
    const unite = article && article.unite ? ' (' + article.unite + ')' : '';
    const champs = [UI.champ({ nom: 'quantite_recue', type: 'decimal', libelle: 'Quantité reçue' + unite }, achat.quantite, { obligatoire: true })];
    const id = await fenetreSaisie({
      titre: 'Réceptionner ' + achatId, champs, libelleValider: 'Réceptionner',
      introduction: UI.html`<p><b>${article ? libelleArticle(article) : achat.article_id}</b> — commandé : ${UI.nombreFr(achat.quantite)}${unite},
        ${libelleFournisseur(achat.fournisseur_id)}.</p><p class="note">La quantité reçue entre en stock. Le prix de l'article ne change pas.</p>`,
      action: (valeurs) => Magasin.recevoir(achatId, valeurs.quantite_recue),
    });
    if (id) await apresEcriture('Achat ' + achatId + ' réceptionné : entrée en stock enregistrée.');
  }

  // ===========================================================================================
  // 16. Onglet « Fournisseurs » : liste, création, modification
  // ===========================================================================================

  async function ouvrirFournisseur(fournisseurId) {
    const existant = fournisseurId ? Donnees.trouver('fournisseurs', fournisseurId) : null;
    if (fournisseurId && !existant) { UI.toast('Ce fournisseur n\'existe plus : actualisez.', 'attention'); return; }
    const valeur = (nom) => (existant ? existant[nom] : '');
    const champs = [
      UI.champ(definitionChamp('fournisseurs', 'nom'), valeur('nom'), { obligatoire: true, attributs: { maxlength: '120' } }),
      UI.champ(definitionChamp('fournisseurs', 'contact'), valeur('contact')),
      UI.champ(definitionChamp('fournisseurs', 'telephone'), valeur('telephone'), { attributs: { inputmode: 'tel' } }),
      UI.champ(definitionChamp('fournisseurs', 'email'), valeur('email'), { attributs: { inputmode: 'email' } }),
    ];
    const resultat = await fenetreSaisie({
      titre: existant ? 'Modifier le fournisseur' : 'Nouveau fournisseur', champs,
      verifier: (valeurs) => Magasin.interne.verifierFournisseur(valeurs, Donnees.lignes('fournisseurs'), existant ? existant.id : ''),
      action: async (valeurs) => (existant ? (await Magasin.modifierFournisseur(existant.id, valeurs), existant.id) : Magasin.creerFournisseur(valeurs)),
    });
    if (resultat) await apresEcriture(existant ? 'Fournisseur enregistré.' : 'Fournisseur ' + resultat + ' créé.');
  }

  function afficherOngletFournisseurs(panneau) {
    const responsable = App.estResponsable();
    const nombreArticles = (id) => Donnees.lignes('articles').filter((article) => article.fournisseur_id === id).length;
    const lignes = Donnees.lignes('fournisseurs').map((f) => Object.assign({}, f, { articles: nombreArticles(f.id) }))
      .sort((a, b) => texte(a.nom).localeCompare(texte(b.nom), 'fr'));
    const telephone = (f) => (f.telephone ? UI.html`<a href="tel:${f.telephone.replace(/[^0-9+]/g, '')}">${f.telephone}</a>` : '');
    const email = (f) => (f.email ? UI.html`<a href="mailto:${f.email}">${f.email}</a>` : '');
    const bouton = (f) => (responsable ? UI.html`<button type="button" class="btn btn-secondaire" data-action="modifier-fournisseur" data-fournisseur="${f.id}">Modifier</button>` : '');
    const liste = listeAdaptative({
      lignes, libelle: 'Fournisseurs', vide: 'Aucun fournisseur enregistré.',
      colonnes: [
        { cle: 'nom', libelle: 'Nom', rendu: (f) => UI.html`<b>${f.nom || f.id}</b>` },
        { cle: 'contact', libelle: 'Contact' },
        { cle: 'telephone', libelle: 'Téléphone', classe: 'sans-coupure', rendu: telephone },
        { cle: 'email', libelle: 'E-mail', rendu: email },
        { cle: 'articles', libelle: 'Articles', type: 'nombre' },
        { cle: 'action', libelle: '', triable: false, rendu: bouton },
      ],
      carte: (f) => UI.html`<div class="carte-ligne"><div class="carte-tete"><b>${f.nom || f.id}</b><span class="badge neutre">${f.articles} article(s)</span></div>
        <div class="carte-meta">${f.contact ? UI.html`<span>${f.contact}</span>` : ''}${f.telephone ? UI.html`<span>${telephone(f)}</span>` : ''}
          ${f.email ? UI.html`<span class="magasin-coupable">${email(f)}</span>` : ''}</div>
        ${responsable ? UI.html`<div class="actions">${bouton(f)}</div>` : ''}</div>`,
    });
    UI.remplir(panneau, UI.html`
      ${responsable ? UI.html`<div class="magasin-barre"><span class="espace"></span>
        <button type="button" class="btn btn-primaire" id="magasin-nouveau-fournisseur">${UI.icone('ajouter')}Nouveau fournisseur</button></div>` : ''}
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
      id: 'magasin', route: /^#\/magasin$/, titre: 'Magasin',
      menu: { libelle: 'Magasin', icone: 'magasin', ordre: 45 },
      profils: ['technicien', 'responsable'], tables,
      afficher: afficherMagasin,
    });
    // « nouveau » avant la fiche : la première route qui correspond gagne ; la route fiche
    // l'exclut en plus (ARCHITECTURE.md §14.2).
    App.ecran({
      id: 'magasin-article-nouveau', route: /^#\/magasin\/article\/nouveau$/, titre: 'Nouvel article', parent: 'magasin',
      profils: ['responsable'], tables: [],
      afficher: afficherNouvelArticle,
    });
    App.ecran({
      id: 'magasin-article', route: /^#\/magasin\/article\/(?!nouveau$)(?<id>[^/?]+)$/, titre: 'Article', parent: 'magasin',
      profils: ['technicien', 'responsable'], tables: tables.concat(['equipements']),
      afficher: afficherFicheArticle,
    });
  });

  return {};
})());
