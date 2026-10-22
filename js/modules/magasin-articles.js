'use strict';
// Magasin (3/5) — écran E9 #/magasin et ses onglets (articles, mouvements, inventaire, à commander,
// achats, fournisseurs ; l'onglet ouvert reste dans l'adresse : #/magasin?onglet=achats), onglet
// « Articles », fiche d'un article #/magasin/article/<id> et création #/magasin/article/nouveau
// (ARCHITECTURE.md §14.4). Les autres onglets sont dans magasin-mouvements.js et magasin-achats.js,
// qui enregistre les écrans du module auprès d'App.
// Profils (D27) : le technicien consulte (ses sorties et retours passent par l'OT) ; le
// responsable a tous les boutons ; le demandeur n'a pas accès au magasin.
// Complète l'objet Magasin.

Object.assign(Magasin, (() => {

  // Outils de magasin-regles.js et magasin-ecritures.js.
  const { texte, ajouterJours, dateDuJour, libelleArticle, consommationEntre, nombreTexte, normaliser,
    categorieArticle, estActif, estACommander, FENETRE_CONSOMMATION_JOURS } = Magasin.interne;

  const LIMITE_FICHE = 15;                     // lignes montrées dans les cartes de la fiche
  const memoire = { onglet: 'articles', filtresArticles: null };

  // ===========================================================================================
  // 7. Outils d'écran communs aux fichiers magasin-*.js (prêtés par Magasin.interne)
  // ===========================================================================================

  /** Tableau triable sur grand écran, cartes (liste-cartes) sur téléphone. */
  function listeAdaptative({ colonnes, lignes, vide, libelle, lien, carte, triInitial }) {
    if (UI.estTelephone()) {
      if (!lignes.length) return UI.element(UI.html`<p class="muted magasin-vide">${vide}</p>`);
      return UI.element(UI.html`<ul class="liste-cartes">${lignes.map((ligne) => UI.html`<li>${carte(ligne)}</li>`)}</ul>`);
    }
    return UI.tableau({ colonnes, lignes, vide, libelle, triInitial, surClic: lien ? (ligne) => App.naviguer(lien(ligne)) : undefined });
  }

  function lienArticle(article, texteLien) {
    if (!article) return '';
    return UI.html`<a href="#/magasin/article/${encodeURIComponent(article.id)}">${texteLien || article.reference || article.id}</a>`;
  }

  function lienOt(otId) {
    return otId ? UI.html`<a href="#/ot/${encodeURIComponent(otId)}">${otId}</a>` : '';
  }

  /** « 3 u » (quantité à la française suivie de l'unité de l'article). */
  function quantiteUnite(quantite, unite) {
    return UI.nombreFr(quantite) + (unite ? ' ' + unite : '');
  }

  function libelleFournisseur(fournisseurId) {
    const fournisseur = fournisseurId ? Donnees.trouver('fournisseurs', fournisseurId) : null;
    return fournisseur ? (fournisseur.nom || fournisseur.id) : (fournisseurId || '');
  }

  /** Badges d'un article : rupture ou « À commander », critique, inactif. */
  function badgesArticle(article, stock) {
    const valeur = stock === undefined ? Donnees.stockArticle(article.id) : stock;
    return UI.html`${estACommander(article, valeur) ? UI.html`<span class="badge attention magasin-badge-commander">À commander</span>` : ''}
      ${valeur <= 0 && estActif(article) ? UI.html`<span class="badge ko">Rupture</span>` : ''}
      ${article.critique === '1' ? UI.html`<span class="badge violet">Critique</span>` : ''}
      ${estActif(article) ? '' : UI.html`<span class="badge neutre barre">Inactif</span>`}`;
  }

  /** Achats en cours (demandée ou commandée) d'un article, les plus récents d'abord. */
  function achatsEnCours(articleId) {
    return Donnees.lignes('achats').filter((achat) => achat.article_id === articleId
      && (achat.statut === 'demandée' || achat.statut === 'commandée'))
      .sort((a, b) => texte(b.date).localeCompare(texte(a.date)) || texte(b.id).localeCompare(texte(a.id)));
  }

  function optionsHtml(options, valeurChoisie) {
    return UI.html`${options.map((o) => UI.html`<option value="${o.valeur}"${o.valeur === valeurChoisie ? UI.brut(' selected') : ''}>${o.libelle}</option>`)}`;
  }

  /** Liste des articles actifs pour une liste déroulante (« ROU-001 — Roulement… (stock 9) »). */
  function listeArticles(avecStock) {
    return Donnees.lignes('articles').filter(estActif)
      .sort((a, b) => texte(a.reference).localeCompare(texte(b.reference), 'fr', { numeric: true }))
      .map((article) => ({ valeur: article.id, libelle: libelleArticle(article)
        + (avecStock ? ' (stock ' + nombreTexte(Donnees.stockArticle(article.id)) + ')' : '') }));
  }

  function listeFournisseurs() {
    return Donnees.lignes('fournisseurs').map((f) => ({ valeur: f.id, libelle: f.nom || f.id }))
      .sort((a, b) => a.libelle.localeCompare(b.libelle, 'fr'));
  }

  /** Définition de champ pour UI.champ : celle du schéma, sinon une définition simple. */
  function definitionChamp(table, nom, remplacement) {
    return Object.assign({}, Schema.champ(table, nom) || { nom, type: 'texte' }, remplacement || {});
  }

  // Valeurs des champs nommés d'un bloc (les fenêtres de UI vivent déjà dans un <form>), au
  // format du fichier : case à cocher '1'/'0', nombres avec un point décimal.
  function lireChamps(bloc) {
    const valeurs = {};
    UI.$$('[name]', bloc).forEach((controle) => {
      if (controle.type === 'checkbox') { valeurs[controle.name] = controle.checked ? '1' : '0'; return; }
      let valeur = String(controle.value || '').trim();
      if (controle.dataset.type === 'decimal' || controle.dataset.type === 'entier') valeur = valeur.replace(/[\s\u00a0\u202f]/g, '').replace(',', '.');
      valeurs[controle.name] = valeur;
    });
    return valeurs;
  }

  /**
   * Fenêtre de saisie : champs (nœuds UI.champ), puis `action(valeurs)` (async) au clic sur le
   * bouton principal. Un refus (ErreurValidation) s'affiche DANS la fenêtre, qui reste ouverte ;
   * une autre erreur est signalée (toast). Renvoie le résultat de l'action, ou null si annulé.
   */
  async function fenetreSaisie({ titre, introduction, champs, libelleValider, action, verifier }) {
    const contenu = UI.element(UI.html`<div class="form-colonne magasin-fenetre">${introduction || ''}</div>`);
    champs.forEach((bloc) => contenu.appendChild(bloc));
    const zoneErreur = UI.element(UI.html`<p class="erreur-champ magasin-erreur-fenetre" role="alert" hidden></p>`);
    contenu.appendChild(zoneErreur);
    let fermer = null;
    let resultat = null;
    let termine = false;
    let enCours = false;

    async function valider() {
      if (enCours) return;
      zoneErreur.hidden = true;
      if (UI.verifierFormulaire(contenu).length) return;
      const valeurs = lireChamps(contenu);
      const erreurs = verifier ? verifier(valeurs) : [];
      erreurs.forEach((erreur) => UI.erreurChamp(contenu, erreur.nom, erreur.message));
      if (erreurs.length) return;
      enCours = true;
      try {
        resultat = await action(valeurs);
        termine = true;
        fermer('ok');
      } catch (erreur) {
        if (erreur instanceof Donnees.ErreurValidation) {
          zoneErreur.textContent = erreur.message;
          zoneErreur.hidden = false;
        } else {
          App.signalerErreur(erreur, titre);
        }
      } finally {
        enCours = false;
      }
    }

    const choix = await UI.fenetre({
      titre, contenu,
      boutons: [
        { libelle: 'Annuler', valeur: null, classe: 'btn-fantome' },
        { libelle: libelleValider || 'Enregistrer', valeur: 'ok', classe: 'btn-primaire', defaut: true },
      ],
      surOuverture(dialogue, fermerFenetre) { fermer = fermerFenetre; },
      avantFermeture(valeur) {
        if (valeur !== 'ok' || termine) return true;
        valider();                                   // la fenêtre se ferme toute seule si tout va bien
        return false;
      },
    });
    return choix === 'ok' ? resultat : null;
  }

  /** Après une écriture réussie : message puis réaffichage de l'écran (défilement conservé). */
  async function apresEcriture(message) {
    App.marquerSaisie(false);
    UI.toast(message, 'succes');
    await App.reafficher();
  }

  // ===========================================================================================
  // 8. Écran #/magasin : onglets (l'onglet ouvert est gardé dans l'adresse)
  // ===========================================================================================

  function ongletsDuProfil() {
    const enCours = Donnees.lignes('achats').filter((achat) => achat.statut === 'demandée' || achat.statut === 'commandée').length;
    return [
      { id: 'articles', libelle: 'Articles' },
      { id: 'mouvements', libelle: 'Mouvements' },
      App.estResponsable() && { id: 'inventaire', libelle: 'Inventaire' },
      { id: 'a-commander', libelle: 'À commander', compteur: Magasin.aCommander().length },
      { id: 'achats', libelle: 'Achats', compteur: enCours },
      { id: 'fournisseurs', libelle: 'Fournisseurs' },
    ].filter(Boolean);
  }

  // Les onglets des fichiers suivants (chargés après celui-ci) sont appelés par relais.
  const AFFICHAGES = {
    articles: (panneau, requete) => afficherOngletArticles(panneau, requete),
    mouvements: (panneau, requete) => Magasin.interne.afficherOngletMouvements(panneau, requete),
    inventaire: (panneau) => Magasin.interne.afficherOngletInventaire(panneau),
    'a-commander': (panneau) => Magasin.interne.afficherOngletACommander(panneau),
    achats: (panneau, requete) => Magasin.interne.afficherOngletAchats(panneau, requete),
    fournisseurs: (panneau) => Magasin.interne.afficherOngletFournisseurs(panneau),
  };

  function remplacerAdresse(onglet) {
    try { history.replaceState(history.state, '', '#/magasin?onglet=' + onglet); } catch (erreur) { /* adresse gardée */ }
  }

  function afficherMagasin(conteneur, parametres) {
    const requete = (parametres && parametres.requete) || new URLSearchParams();
    const onglets = ongletsDuProfil();
    const existe = (id) => onglets.some((onglet) => onglet.id === id);
    const demande = requete.get('onglet');
    const actif = existe(demande) ? demande : (existe(memoire.onglet) ? memoire.onglet : 'articles');
    memoire.onglet = actif;
    // L'adresse ne garde que l'onglet : les filtres venus d'un lien (?article=…) ne servent qu'une fois.
    remplacerAdresse(actif);
    UI.remplir(conteneur, UI.html`
      <div class="magasin">
        <div class="entete-page">
          <div><h1>Magasin</h1><p>Pièces détachées : stock, mouvements, inventaire, réapprovisionnement et fournisseurs.</p></div>
          <div class="actions">${App.estResponsable() ? UI.html`
            <a class="btn btn-primaire" id="magasin-nouvel-article" href="#/magasin/article/nouveau">${UI.icone('ajouter')}Nouvel article</a>` : ''}</div>
        </div>
        ${App.estResponsable() ? '' : UI.html`<p class="note magasin-consultation">Consultation : les sorties et retours de pièces se font depuis l'ordre de travail.</p>`}
        <div class="magasin-onglets"></div>
      </div>`);
    UI.onglets(UI.$('.magasin-onglets', conteneur), onglets.map((onglet) => Object.assign({}, onglet, {
      afficher: (panneau) => AFFICHAGES[onglet.id](panneau, onglet.id === demande ? requete : null),
    })), {
      actif, libelle: 'Rubriques du magasin',
      surChangement: (id) => { memoire.onglet = id; remplacerAdresse(id); },
    });
    // Sur téléphone la barre d'onglets défile : l'onglet ouvert doit y être visible.
    const barre = UI.$('.magasin-onglets .barre-onglets', conteneur);
    const bouton = UI.$('.onglet[aria-selected="true"]', barre);
    if (barre && bouton) barre.scrollLeft = Math.max(0, bouton.offsetLeft - barre.offsetLeft - 16);
  }

  // ===========================================================================================
  // 9. Onglet « Articles » : recherche, catégorie, état ; tableau ou cartes
  // ===========================================================================================

  const ETATS_ARTICLES = [
    { valeur: 'actifs', libelle: 'Articles actifs' },
    { valeur: 'a-commander', libelle: 'À commander' },
    { valeur: 'critiques', libelle: 'Critiques' },
    { valeur: 'inactifs', libelle: 'Inactifs' },
    { valeur: 'tous', libelle: 'Tous les articles' },
  ];

  function filtresArticles(requete) {
    const filtres = Object.assign({ recherche: '', categorie: '', etat: 'actifs' }, memoire.filtresArticles || {});
    if (requete) {
      if (requete.has('recherche')) filtres.recherche = requete.get('recherche');
      if (requete.has('categorie')) filtres.categorie = requete.get('categorie').toUpperCase();
      if (ETATS_ARTICLES.some((etat) => etat.valeur === requete.get('etat'))) filtres.etat = requete.get('etat');
    }
    memoire.filtresArticles = filtres;
    return filtres;
  }

  function garderArticle(ligne, filtres) {
    const article = ligne.article;
    const actif = estActif(article);
    if (filtres.etat === 'actifs' && !actif) return false;
    if (filtres.etat === 'inactifs' && actif) return false;
    if (filtres.etat === 'a-commander' && !ligne.aCommander) return false;
    if (filtres.etat === 'critiques' && !(actif && article.critique === '1')) return false;
    if (filtres.categorie && ligne.categorie.code !== filtres.categorie) return false;
    const recherche = normaliser(filtres.recherche);
    if (!recherche) return true;
    return normaliser([article.id, article.reference, article.designation, article.fabricant, article.ref_fabricant,
      article.emplacement, ligne.categorie.libelle].join(' ')).includes(recherche);
  }

  function ligneArticle(article) {
    const stock = Donnees.stockArticle(article.id);
    return {
      article, id: article.id, reference: article.reference, designation: article.designation,
      categorie: categorieArticle(article), emplacement: article.emplacement, stock, unite: article.unite,
      pointCommande: Donnees.nombre(article.point_commande), prix: Donnees.nombre(article.prix_unitaire),
      aCommander: estACommander(article, stock),
    };
  }

  function colonnesArticles() {
    return [
      { cle: 'reference', libelle: 'Référence', rendu: (l) => lienArticle(l.article) },
      { cle: 'designation', libelle: 'Désignation', classe: 'magasin-col-designation',
        rendu: (l) => UI.html`${l.designation} ${l.article.critique === '1' ? UI.html`<span class="badge violet">Critique</span>` : ''}
          ${estActif(l.article) ? '' : UI.html`<span class="badge neutre barre">Inactif</span>`}
          <small class="magasin-categorie">${l.categorie.libelle}</small>` },
      { cle: 'emplacement', libelle: 'Emplacement' },
      { cle: 'stock', libelle: 'Stock', type: 'nombre',
        rendu: (l) => UI.html`<span class="sans-coupure">${quantiteUnite(l.stock, l.unite)}</span>${l.aCommander
          ? UI.html` <span class="badge attention magasin-badge-commander">À commander</span>` : ''}` },
      { cle: 'pointCommande', libelle: 'Point de commande', type: 'nombre', rendu: (l) => UI.nombreFr(l.pointCommande) },
      { cle: 'prix', libelle: 'Prix unitaire', type: 'nombre', rendu: (l) => UI.euro(l.prix) },
    ];
  }

  function carteArticle(l) {
    return UI.html`<a href="#/magasin/article/${encodeURIComponent(l.id)}">
      <div class="carte-tete"><b>${l.reference || l.id}</b>${badgesArticle(l.article, l.stock)}</div>
      <div class="carte-titre">${l.designation}</div>
      <div class="carte-meta"><span>Stock : ${quantiteUnite(l.stock, l.unite)}</span>
        <span>Point de commande : ${UI.nombreFr(l.pointCommande)}</span>
        ${l.emplacement ? UI.html`<span>Emplacement : ${l.emplacement}</span>` : ''}</div></a>`;
  }

  function afficherOngletArticles(panneau, requete) {
    const filtres = filtresArticles(requete);
    const toutes = Donnees.lignes('articles').map(ligneArticle);
    const categories = new Map();
    toutes.forEach((l) => categories.set(l.categorie.code, l.categorie.libelle));
    const optionsCategories = [{ valeur: '', libelle: 'Toutes catégories' }].concat(Array.from(categories.entries())
      .map(([code, libelle]) => ({ valeur: code, libelle })).sort((a, b) => a.libelle.localeCompare(b.libelle, 'fr')));
    UI.remplir(panneau, UI.html`
      <form class="filtres magasin-filtres" id="magasin-filtres-articles" data-hors-saisie role="search" aria-label="Filtrer les articles">
        <label class="visuellement-cache" for="magasin-recherche-article">Rechercher un article</label>
        <input type="search" id="magasin-recherche-article" name="recherche" value="${filtres.recherche}"
          placeholder="Référence, désignation, fabricant, emplacement" autocomplete="off">
        <label class="visuellement-cache" for="magasin-categorie">Catégorie</label>
        <select id="magasin-categorie" name="categorie">${optionsHtml(optionsCategories, filtres.categorie)}</select>
        <label class="visuellement-cache" for="magasin-etat-article">État</label>
        <select id="magasin-etat-article" name="etat">${optionsHtml(ETATS_ARTICLES, filtres.etat)}</select>
      </form>
      <p class="note magasin-compteur" role="status"></p>
      <div class="carte magasin-liste"></div>`);
    const zone = UI.$('.magasin-liste', panneau);
    const compteur = UI.$('.magasin-compteur', panneau);
    function rafraichir() {
      const lignes = toutes.filter((l) => garderArticle(l, memoire.filtresArticles))
        .sort((a, b) => texte(a.reference).localeCompare(texte(b.reference), 'fr', { numeric: true }));
      UI.remplir(zone, listeAdaptative({
        colonnes: colonnesArticles(), lignes, libelle: 'Articles du magasin', carte: carteArticle,
        vide: 'Aucun article ne correspond à ces filtres.', lien: (l) => '#/magasin/article/' + encodeURIComponent(l.id),
      }));
      compteur.textContent = lignes.length + ' article(s) sur ' + toutes.length
        + ' — ' + toutes.filter((l) => l.aCommander).length + ' à commander';
    }
    const formulaire = UI.$('#magasin-filtres-articles', panneau);
    const lireFiltres = () => { memoire.filtresArticles = Object.assign({}, memoire.filtresArticles, UI.lireFormulaire(formulaire)); rafraichir(); };
    formulaire.addEventListener('input', lireFiltres);
    formulaire.addEventListener('change', lireFiltres);
    formulaire.addEventListener('submit', (evenement) => evenement.preventDefault());
    rafraichir();
  }

  // ===========================================================================================
  // 10. Fiche d'un article (#/magasin/article/<id>) et création (#/magasin/article/nouveau)
  // ===========================================================================================

  /** Point de commande suggéré (D23) : { valeur (nombre ou null), detail } pour l'affichage. */
  function suggestion(article) {
    const valeur = Magasin.suggestionPointCommande(article.id);
    const fin = dateDuJour();
    const { sorties, retours } = consommationEntre(article.id, ajouterJours(fin, -(FENETRE_CONSOMMATION_JOURS - 1)), fin);
    if (valeur === null) return { valeur, detail: 'aucune sortie sur les ' + FENETRE_CONSOMMATION_JOURS + ' derniers jours' };
    return {
      valeur,
      detail: 'consommation des ' + FENETRE_CONSOMMATION_JOURS + ' derniers jours : ' + quantiteUnite(Math.max(0, sorties - retours), article.unite)
        + ', délai ' + (texte(article.delai_jours) || '0') + ' j, stock de sécurité ' + (texte(article.stock_securite) || '0'),
    };
  }

  // Encadré « Point de commande suggéré » ; avec `bouton`, « Reprendre la suggestion » remplit le
  // champ point_commande du formulaire (sans enregistrer : il faut cliquer sur Enregistrer).
  function encadreSuggestion(article, bouton) {
    const calcul = suggestion(article);
    return UI.html`<div class="encadre info magasin-suggestion large" id="magasin-suggestion" data-valeur="${calcul.valeur === null ? '' : String(calcul.valeur)}">
      <p>Point de commande suggéré : <b>${calcul.valeur === null ? 'non calculable' : nombreTexte(calcul.valeur)}</b>
        <span class="magasin-detail">(${calcul.detail}).</span> Le point de commande reste celui que vous saisissez.</p>
      ${bouton && calcul.valeur !== null ? UI.html`<button type="button" class="btn btn-secondaire" id="magasin-reprendre-suggestion">${UI.icone('valider')}Reprendre la suggestion</button>` : ''}
    </div>`;
  }

  function instrumentsFiche(article, stock) {
    const prix = Donnees.nombre(article.prix_unitaire);
    const point = Donnees.nombre(article.point_commande);
    const calcul = suggestion(article);
    const ton = stock <= 0 ? 'rouge' : (estACommander(article, stock) ? 'ambre' : 'vert');
    return UI.html`<div class="instruments magasin-instruments">
      <div class="${ton}"><div class="lib">Stock</div><div class="chiffre" id="magasin-stock">${quantiteUnite(stock, article.unite)}</div>
        <div class="comp">${article.emplacement ? 'Emplacement ' + article.emplacement : 'Emplacement non renseigné'}</div></div>
      <div><div class="lib">Valeur du stock</div><div class="chiffre" id="magasin-valeur-stock">${prix === null ? '–' : UI.euro(Math.max(0, stock) * prix)}</div>
        <div class="comp">Prix unitaire ${UI.euro(prix)}</div></div>
      <div class="ambre"><div class="lib">Point de commande</div><div class="chiffre">${point === null ? '–' : UI.nombreFr(point)}</div>
        <div class="comp">Stock de sécurité ${UI.nombreFr(article.stock_securite)}</div></div>
      <div class="cyan"><div class="lib">Suggestion</div><div class="chiffre">${calcul.valeur === null ? 'non calculable' : nombreTexte(calcul.valeur)}</div>
        <div class="comp">Consommation sur ${FENETRE_CONSOMMATION_JOURS} jours</div></div>
    </div>`;
  }

  function carteDescription(article) {
    return UI.html`<article class="carte"><h2>Article</h2><dl class="valeurs">
      <dt>Référence</dt><dd>${article.reference}</dd><dt>Désignation</dt><dd>${article.designation}</dd>
      <dt>Catégorie</dt><dd>${categorieArticle(article).libelle}</dd>
      <dt>Fabricant</dt><dd>${article.fabricant}</dd><dt>Référence fabricant</dt><dd>${article.ref_fabricant}</dd>
      <dt>Emplacement</dt><dd>${article.emplacement}</dd><dt>Unité</dt><dd>${article.unite}</dd>
      <dt>Prix unitaire</dt><dd>${article.prix_unitaire === '' ? '' : UI.euro(article.prix_unitaire)}</dd>
      <dt>Fournisseur</dt><dd>${libelleFournisseur(article.fournisseur_id)}</dd>
      <dt>Délai d'approvisionnement</dt><dd>${article.delai_jours === '' ? '' : article.delai_jours + ' j'}</dd>
      <dt>Stock de sécurité</dt><dd>${article.stock_securite}</dd><dt>Point de commande</dt><dd>${article.point_commande}</dd>
      <dt>Quantité à commander</dt><dd>${article.qte_commande}</dd>
      <dt>Article critique</dt><dd>${article.critique === '1' ? 'Oui' : 'Non'}</dd>
    </dl>${encadreSuggestion(article, false)}</article>`;
  }

  /** Formulaire d'un article (création si `article` est null) ; le responsable seul l'affiche. */
  function formulaireArticle(article) {
    const formulaire = UI.element(UI.html`<form class="form-grille" id="form-article" novalidate></form>`);
    const valeur = (nom) => (article ? article[nom] : undefined);
    const ajouter = (bloc, large) => { if (large) bloc.classList.add('large'); formulaire.appendChild(bloc); return bloc; };
    const champ = (nom, options) => ajouter(UI.champ(definitionChamp('articles', nom), valeur(nom), options));
    champ('reference', { aide: 'Unique parmi les articles actifs. Le préfixe donne la catégorie (ex. ROU-012 : roulements).', attributs: { maxlength: '40' } });
    champ('designation', { attributs: { maxlength: '120' } });
    champ('fabricant');
    champ('ref_fabricant');
    champ('emplacement', { aide: 'Rayon et casier (ex. A1-03).' });
    champ('unite', { placeholder: 'u, m, L…' });
    champ('prix_unitaire', { aide: 'Prix actuel en € HT : une réception d\'achat ne le change pas.' });
    champ('fournisseur_id', { liste: listeFournisseurs() });
    champ('stock_securite');
    champ('delai_jours');
    champ('point_commande', { aide: 'Sous ce niveau (ou à ce niveau), l\'article passe « À commander ».' });
    champ('qte_commande', { aide: 'Vide : point de commande − stock + stock de sécurité.' });
    if (article) ajouter(UI.element(encadreSuggestion(article, true)), true);
    else ajouter(UI.champ({ nom: 'stock_initial', type: 'decimal', libelle: 'Stock initial' }, '', { aide: 'Facultatif : enregistré comme un inventaire.' }));
    champ('critique');
    if (article) champ('actif', { aide: 'Décoché : l\'article n\'est plus proposé (son historique est conservé).' });
    formulaire.appendChild(UI.element(UI.html`<p class="mention-requis large"><span class="requis" aria-hidden="true">*</span>champ obligatoire</p>`)).classList.add('large');
    formulaire.appendChild(UI.element(UI.html`<div class="actions">
      <button type="submit" class="btn btn-primaire">${UI.icone('valider')}Enregistrer</button>
      ${article ? '' : UI.html`<a class="btn btn-fantome" href="#/magasin?onglet=articles">Annuler</a>`}</div>`));
    const reprendre = UI.$('#magasin-reprendre-suggestion', formulaire);
    if (reprendre) {
      reprendre.addEventListener('click', () => {
        const point = UI.$('[name=point_commande]', formulaire);
        point.value = nombreTexte(Number(UI.$('#magasin-suggestion', formulaire).dataset.valeur));
        point.dispatchEvent(new Event('input', { bubbles: true }));       // saisie en cours (App)
        point.focus();
        UI.toast('Suggestion reprise : cliquez sur Enregistrer pour la garder.', 'info');
      });
    }
    formulaire.addEventListener('submit', (evenement) => { evenement.preventDefault(); enregistrerArticle(formulaire, article); });
    return formulaire;
  }

  async function enregistrerArticle(formulaire, article) {
    const bouton = UI.$('button[type=submit]', formulaire);
    if (bouton.disabled) return;
    const valeurs = lireChamps(formulaire);
    const erreurs = UI.verifierFormulaire(formulaire);
    Magasin.interne.verifierArticle(valeurs, Donnees.lignes('articles'), article ? article.id : '')
      .filter((erreur) => !erreurs.some((e) => e.nom === erreur.nom)).forEach((erreur) => erreurs.push(erreur));
    const stockInitial = article ? null : Donnees.nombre(valeurs.stock_initial);
    if (!article && texte(valeurs.stock_initial) !== '' && (stockInitial === null || stockInitial < 0)) {
      erreurs.push({ nom: 'stock_initial', message: 'Saisissez un stock positif ou laissez vide.' });
    }
    UI.$$('.champ', formulaire).forEach((bloc) => UI.erreurChamp(formulaire, bloc.dataset.champ, ''));
    erreurs.forEach((erreur) => UI.erreurChamp(formulaire, erreur.nom, erreur.message));
    if (erreurs.length) { const premier = UI.$('[aria-invalid="true"]', formulaire); if (premier) premier.focus(); return; }
    bouton.disabled = true;
    bouton.setAttribute('aria-busy', 'true');
    try {
      if (article) {
        const changes = await Magasin.modifierArticle(article.id, valeurs);
        await apresEcriture(changes.length ? 'Article enregistré.' : 'Aucune modification à enregistrer.');
        return;
      }
      const id = await Magasin.creerArticle(valeurs);
      if (stockInitial) await Magasin.inventorier([{ articleId: id, quantite: stockInitial }], 'Stock initial');
      App.marquerSaisie(false);
      UI.toast('Article créé.', 'succes');
      App.naviguer('#/magasin/article/' + encodeURIComponent(id));
    } catch (erreur) {
      App.signalerErreur(erreur, 'enregistrement de l\'article');
    } finally {
      bouton.disabled = false;
      bouton.removeAttribute('aria-busy');
    }
  }

  function carteMouvementsArticle(article) {
    const mouvements = Donnees.lignes('mouvements_stock').filter((m) => m.article_id === article.id)
      .sort((a, b) => texte(b.date).localeCompare(texte(a.date)) || texte(b.id).localeCompare(texte(a.id)));
    const lignes = mouvements.slice(0, LIMITE_FICHE);
    const liste = listeAdaptative({
      lignes, libelle: 'Derniers mouvements de l\'article', vide: 'Aucun mouvement pour cet article.',
      colonnes: [
        { cle: 'date', libelle: 'Date', classe: 'sans-coupure', rendu: (m) => UI.dateHeureFr(m.date) },
        { cle: 'type', libelle: 'Type', rendu: (m) => Magasin.interne.badgeMouvement(m.type) },
        { cle: 'quantite', libelle: 'Quantité', type: 'nombre', rendu: (m) => UI.nombreFr(m.quantite) },
        { cle: 'ot_id', libelle: 'OT', classe: 'sans-coupure', rendu: (m) => lienOt(m.ot_id) },
        { cle: 'utilisateur', libelle: 'Par' },
        { cle: 'commentaire', libelle: 'Commentaire', classe: 'magasin-col-commentaire' },
      ],
      carte: (m) => UI.html`<div class="carte-ligne"><div class="carte-tete"><b>${UI.dateHeureFr(m.date)}</b>${Magasin.interne.badgeMouvement(m.type)}</div>
        <div class="carte-meta"><span>Quantité : ${UI.nombreFr(m.quantite)}</span>${m.ot_id ? UI.html`<span>${lienOt(m.ot_id)}</span>` : ''}
          ${m.utilisateur ? UI.html`<span>${m.utilisateur}</span>` : ''}</div>${m.commentaire ? UI.html`<div class="carte-meta">${m.commentaire}</div>` : ''}</div>`,
    });
    const carte = UI.element(UI.html`<article class="carte magasin-mouvements-article">
      <div class="entete-carte"><h2>Mouvements <span class="badge">${mouvements.length}</span></h2>
        ${mouvements.length > LIMITE_FICHE ? UI.html`<a href="#/magasin?onglet=mouvements&amp;article=${encodeURIComponent(article.id)}">Voir les ${mouvements.length}</a>` : ''}</div>
      <div class="magasin-zone"></div></article>`);
    UI.$('.magasin-zone', carte).appendChild(liste);
    return carte;
  }

  function carteEquipementsLies(article) {
    const liens = Donnees.lignes('article_equipement').filter((lien) => lien.article_id === article.id).map((lien) => {
      const equipement = Donnees.trouver('equipements', lien.equipement_id);
      return { id: lien.equipement_id, repere: equipement ? equipement.repere : lien.equipement_id,
        designation: equipement ? equipement.designation : '(équipement inconnu)', quantite: lien.quantite };
    }).sort((a, b) => texte(a.repere).localeCompare(texte(b.repere), 'fr', { numeric: true }));
    return UI.html`<article class="carte"><h2>Équipements liés <span class="badge">${liens.length}</span></h2>
      ${liens.length ? UI.html`<ul class="magasin-liens">${liens.map((l) => UI.html`<li>
        <a href="#/equipement/${encodeURIComponent(l.id)}"><b>${l.repere}</b> ${l.designation}</a>
        <span class="muted">× ${UI.nombreFr(l.quantite)}</span></li>`)}</ul>`
        : UI.html`<p class="muted">Cette pièce n'est rattachée à aucun équipement.</p>`}</article>`;
  }

  function carteOtConsommateurs(article) {
    const parOt = new Map();
    Donnees.lignes('mouvements_stock').forEach((m) => {
      if (m.article_id !== article.id || !m.ot_id || (m.type !== 'sortie' && m.type !== 'retour')) return;
      const ligne = parOt.get(m.ot_id) || { otId: m.ot_id, net: 0, derniere: '' };
      ligne.net += (m.type === 'sortie' ? 1 : -1) * (Donnees.nombre(m.quantite) || 0);
      if (texte(m.date) > ligne.derniere) ligne.derniere = texte(m.date);
      parOt.set(m.ot_id, ligne);
    });
    const lignes = Array.from(parOt.values()).sort((a, b) => b.derniere.localeCompare(a.derniere));
    return UI.html`<article class="carte"><h2>OT consommateurs <span class="badge">${lignes.length}</span></h2>
      ${lignes.length ? UI.html`<ul class="magasin-liens">${lignes.slice(0, LIMITE_FICHE).map((l) => {
        const ot = Donnees.trouver('ordres_travail', l.otId);
        const equipement = ot ? Donnees.trouver('equipements', ot.equipement_id) : null;
        return UI.html`<li>${lienOt(l.otId)} <span>${equipement ? equipement.repere : ''}</span>
          ${ot ? UI.badgeStatut(ot.statut) : ''} <span class="muted">${UI.dateFr(l.derniere)} · net ${quantiteUnite(l.net, article.unite)}</span></li>`;
      })}</ul>` : UI.html`<p class="muted">Aucun ordre de travail n'a consommé cette pièce.</p>`}</article>`;
  }

  function carteAchatsArticle(article) {
    const achats = Donnees.lignes('achats').filter((achat) => achat.article_id === article.id)
      .sort((a, b) => texte(b.date).localeCompare(texte(a.date)) || texte(b.id).localeCompare(texte(a.id)));
    return UI.html`<article class="carte"><h2>Achats <span class="badge">${achats.length}</span></h2>
      ${achats.length ? UI.html`<ul class="magasin-liens">${achats.slice(0, LIMITE_FICHE).map((achat) => UI.html`<li>
        <b>${achat.id}</b> ${UI.badgeStatut(achat.statut)} <span>${UI.nombreFr(achat.quantite)} × ${UI.euro(achat.prix_unitaire)}</span>
        <span class="muted">${UI.dateFr(achat.date)}${achat.date_reception ? ' · reçu le ' + UI.dateFr(achat.date_reception) : ''} · ${libelleFournisseur(achat.fournisseur_id)}</span></li>`)}</ul>`
        : UI.html`<p class="muted">Aucun achat pour cet article.</p>`}</article>`;
  }

  function afficherArticleIntrouvable(conteneur, id) {
    App.definirTitre('Article introuvable');
    UI.remplir(conteneur, UI.html`<div class="magasin"><div class="entete-page"><div>
      <div class="fil"><a href="#/magasin?onglet=articles">Magasin</a></div><h1>Article introuvable</h1></div></div>
      ${UI.vide('Aucun article ne porte l\'identifiant « ' + id + ' »', 'Il a peut-être été saisi sur un autre poste : actualisez.', 'magasin')}</div>`);
  }

  function afficherFicheArticle(conteneur, parametres) {
    const article = Donnees.trouver('articles', parametres.id);
    if (!article) { afficherArticleIntrouvable(conteneur, parametres.id); return; }
    App.definirTitre(article.reference || article.id);
    const responsable = App.estResponsable();
    const stock = Donnees.stockArticle(article.id);
    const enCours = achatsEnCours(article.id);
    UI.remplir(conteneur, UI.html`
      <div class="magasin magasin-fiche">
        <div class="entete-page">
          <div>
            <div class="fil"><a href="#/magasin?onglet=articles">Magasin</a> <span aria-hidden="true">›</span> <span>${categorieArticle(article).libelle}</span></div>
            <h1>${libelleArticle(article)}</h1>
            <p class="magasin-badges">${badgesArticle(article, stock)}</p>
            <p><a id="lien-wiki-article" href="#/wiki/${encodeURIComponent(article.id)}">${UI.icone('wiki')}Wiki de cet article</a></p>
          </div>
          ${responsable ? UI.html`<div class="actions">
            <button type="button" class="btn btn-secondaire" id="magasin-entree">${UI.icone('ajouter')}Entrée en stock</button>
            <button type="button" class="btn btn-secondaire" id="magasin-demander-achat">${UI.icone('magasin')}Demander l'achat</button>
          </div>` : ''}
        </div>
        ${enCours.length ? UI.html`<div class="alertes"><div class="alerte" role="status">${UI.icone('apropos')}<div class="alerte-texte">
          Achat en cours : ${enCours.map((achat) => UI.html`<b>${achat.id}</b> (${achat.statut}, ${UI.nombreFr(achat.quantite)}) `)}
          — <a href="#/magasin?onglet=achats">voir les achats</a></div></div></div>` : ''}
        ${instrumentsFiche(article, stock)}
        <div class="magasin-zone-article"></div>
        <div class="grille magasin-grille">
          <div class="c4">${carteEquipementsLies(article)}</div>
          <div class="c4">${carteOtConsommateurs(article)}</div>
          <div class="c4">${carteAchatsArticle(article)}</div>
        </div>
        <div class="magasin-colonne-mouvements"></div>
      </div>`);
    const zoneArticle = UI.$('.magasin-zone-article', conteneur);
    if (responsable) {
      const carte = UI.element(UI.html`<article class="carte"><h2>Article et réapprovisionnement</h2></article>`);
      carte.appendChild(formulaireArticle(article));
      zoneArticle.appendChild(carte);
      UI.$('#magasin-entree', conteneur).addEventListener('click', () => Magasin.interne.ouvrirEntree(article));
      UI.$('#magasin-demander-achat', conteneur).addEventListener('click', () => Magasin.interne.ouvrirDemandeAchat(article));
    } else {
      UI.remplir(zoneArticle, carteDescription(article));
    }
    UI.$('.magasin-colonne-mouvements', conteneur).appendChild(carteMouvementsArticle(article));
  }

  function afficherNouvelArticle(conteneur) {
    App.definirTitre('Nouvel article');
    UI.remplir(conteneur, UI.html`<div class="magasin">
      <div class="entete-page"><div><div class="fil"><a href="#/magasin?onglet=articles">Magasin</a> <span aria-hidden="true">›</span> <span>Nouvel article</span></div>
        <h1>Nouvel article</h1><p>Le stock vient des mouvements : un stock initial est enregistré comme un inventaire.</p></div></div>
      <article class="carte magasin-zone-article"></article></div>`);
    UI.$('.magasin-zone-article', conteneur).appendChild(formulaireArticle(null));
  }

  // Outils et écrans prêtés aux fichiers suivants du module (usage interne).
  Object.assign(Magasin.interne, {
    listeAdaptative, lienArticle, lienOt, quantiteUnite, libelleFournisseur, badgesArticle, achatsEnCours,
    optionsHtml, listeArticles, listeFournisseurs, definitionChamp, lireChamps, fenetreSaisie, apresEcriture,
    afficherMagasin, afficherFicheArticle, afficherNouvelArticle,
  });

  return {};
})());
