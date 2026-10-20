'use strict';
// Magasin (4/5) — onglets « Mouvements » (filtres type, article, OT ; liens vers les OT) et
// « Inventaire » (responsable : stock compté par article, écart affiché, validation groupée) de
// l'écran #/magasin, et fenêtre « Entrée en stock » de la fiche article (ARCHITECTURE.md §14.4).
// Complète l'objet Magasin.

Object.assign(Magasin, (() => {

  // Constantes et outils de magasin-regles.js et magasin-articles.js.
  const { TYPES_MOUVEMENT } = Magasin;
  const { texte, nombreTexte, normaliser, libelleArticle, categorieArticle, estActif, listeAdaptative, lienArticle,
    lienOt, quantiteUnite, optionsHtml, fenetreSaisie, apresEcriture } = Magasin.interne;

  const LIMITE_MOUVEMENTS = 300;              // lignes affichées au plus (les plus récentes)
  const TONS_MOUVEMENT = { 'entrée': 'ok', 'sortie': 'attention', 'retour': 'cyan', 'inventaire': 'violet' };
  // Mémoire de la session : filtres, et stocks comptés pas encore validés (une tournée
  // d'inventaire survit à un passage sur un autre écran).
  const memoire = { filtresMouvements: null, filtresInventaire: null, saisiesInventaire: new Map() };

  /** Badge du type de mouvement (texte toujours affiché ; la couleur aide seulement). */
  function badgeMouvement(type) {
    return UI.badgeStatut(type, TONS_MOUVEMENT[type] || 'neutre');
  }

  function articleDe(mouvement) {
    return Donnees.trouver('articles', mouvement.article_id);
  }

  // ===========================================================================================
  // 11. Onglet « Mouvements »
  // ===========================================================================================

  // Filtres : ceux de la session, ou ceux d'un lien (#/magasin?onglet=mouvements&article=ART-0016).
  function filtresMouvements(requete) {
    let filtres = Object.assign({ type: '', article: '', ot: '' }, memoire.filtresMouvements || {});
    if (requete && ['type', 'article', 'ot'].some((cle) => requete.has(cle))) {
      filtres = {
        type: TYPES_MOUVEMENT.includes(requete.get('type')) ? requete.get('type') : '',
        article: requete.get('article') || '', ot: requete.get('ot') || '',
      };
    }
    memoire.filtresMouvements = filtres;
    return filtres;
  }

  function garderMouvement(mouvement, filtres) {
    if (filtres.type && mouvement.type !== filtres.type) return false;
    if (filtres.article && mouvement.article_id !== filtres.article) return false;
    if (filtres.ot && !normaliser(mouvement.ot_id).includes(normaliser(filtres.ot))) return false;
    return true;
  }

  function colonnesMouvements() {
    return [
      { cle: 'date', libelle: 'Date', classe: 'sans-coupure', rendu: (m) => UI.dateHeureFr(m.date) },
      { cle: 'article_id', libelle: 'Article', valeurTri: (m) => texte((articleDe(m) || {}).reference),
        rendu: (m) => (articleDe(m) ? UI.html`${lienArticle(articleDe(m))} <span class="muted">${articleDe(m).designation}</span>` : m.article_id) },
      { cle: 'type', libelle: 'Type', rendu: (m) => badgeMouvement(m.type) },
      { cle: 'quantite', libelle: 'Quantité', type: 'nombre', rendu: (m) => UI.nombreFr(m.quantite) },
      { cle: 'ot_id', libelle: 'OT', classe: 'sans-coupure', rendu: (m) => lienOt(m.ot_id) },
      { cle: 'utilisateur', libelle: 'Par' },
      { cle: 'commentaire', libelle: 'Commentaire', classe: 'magasin-col-commentaire' },
    ];
  }

  function carteMouvement(m) {
    const article = articleDe(m);
    return UI.html`<div class="carte-ligne">
      <div class="carte-tete"><b>${article ? article.reference : m.article_id}</b>${badgeMouvement(m.type)}</div>
      <div class="carte-titre">${article ? article.designation : ''}</div>
      <div class="carte-meta"><span>${UI.dateHeureFr(m.date)}</span><span>Quantité : ${UI.nombreFr(m.quantite)}</span>
        ${m.ot_id ? UI.html`<span>${lienOt(m.ot_id)}</span>` : ''}${m.utilisateur ? UI.html`<span>${m.utilisateur}</span>` : ''}</div>
      ${m.commentaire ? UI.html`<div class="carte-meta">${m.commentaire}</div>` : ''}</div>`;
  }

  function afficherOngletMouvements(panneau, requete) {
    const filtres = filtresMouvements(requete);
    const tous = Donnees.lignes('mouvements_stock');
    const optionsArticles = [{ valeur: '', libelle: 'Tous les articles' }].concat(Donnees.lignes('articles').slice()
      .sort((a, b) => texte(a.reference).localeCompare(texte(b.reference), 'fr', { numeric: true }))
      .map((article) => ({ valeur: article.id, libelle: libelleArticle(article) })));
    UI.remplir(panneau, UI.html`
      <form class="filtres magasin-filtres" id="magasin-filtres-mouvements" data-hors-saisie role="search" aria-label="Filtrer les mouvements">
        <label class="visuellement-cache" for="magasin-filtre-type">Type de mouvement</label>
        <select id="magasin-filtre-type" name="type">${optionsHtml([{ valeur: '', libelle: 'Tous les types' }]
          .concat(TYPES_MOUVEMENT.map((type) => ({ valeur: type, libelle: type }))), filtres.type)}</select>
        <label class="visuellement-cache" for="magasin-filtre-article">Article</label>
        <select id="magasin-filtre-article" name="article">${optionsHtml(optionsArticles, filtres.article)}</select>
        <label class="visuellement-cache" for="magasin-filtre-ot">N° d'ordre de travail</label>
        <input type="search" id="magasin-filtre-ot" name="ot" value="${filtres.ot}" placeholder="N° d'OT (ex. OT-2026-0175)" autocomplete="off">
      </form>
      <p class="note magasin-compteur" role="status"></p>
      <div class="carte magasin-liste"></div>`);
    const zone = UI.$('.magasin-liste', panneau);
    const compteur = UI.$('.magasin-compteur', panneau);
    function rafraichir() {
      const retenus = tous.filter((m) => garderMouvement(m, memoire.filtresMouvements))
        .sort((a, b) => texte(b.date).localeCompare(texte(a.date)) || texte(b.id).localeCompare(texte(a.id)));
      const lignes = retenus.slice(0, LIMITE_MOUVEMENTS);
      UI.remplir(zone, listeAdaptative({
        colonnes: colonnesMouvements(), lignes, carte: carteMouvement, libelle: 'Mouvements de stock',
        vide: 'Aucun mouvement ne correspond à ces filtres.',
      }));
      compteur.textContent = retenus.length + ' mouvement(s) sur ' + tous.length
        + (retenus.length > LIMITE_MOUVEMENTS ? ' — les ' + LIMITE_MOUVEMENTS + ' plus récents sont affichés : affinez les filtres' : '');
    }
    const formulaire = UI.$('#magasin-filtres-mouvements', panneau);
    const lireFiltres = () => { memoire.filtresMouvements = UI.lireFormulaire(formulaire); rafraichir(); };
    formulaire.addEventListener('input', lireFiltres);
    formulaire.addEventListener('change', lireFiltres);
    formulaire.addEventListener('submit', (evenement) => evenement.preventDefault());
    rafraichir();
  }

  // ===========================================================================================
  // 12. Onglet « Inventaire » (responsable) : stock compté, écart, validation groupée
  // ===========================================================================================

  /** Écart affiché : vide (rien saisi), « illisible », « 0 », « +2 » ou « −3 ». */
  function ecartHtml(stock, saisie) {
    if (texte(saisie) === '') return '';
    const compte = Donnees.nombre(saisie);
    if (compte === null || compte < 0) return UI.html`<span class="badge ko">illisible</span>`;
    const ecart = Math.round((compte - stock) * 1e6) / 1e6;
    if (ecart === 0) return UI.html`<span class="badge ok magasin-ecart">0</span>`;
    return UI.html`<span class="badge ${ecart > 0 ? 'info' : 'attention'} magasin-ecart">${ecart > 0 ? '+' : '−'}${nombreTexte(Math.abs(ecart))}</span>`;
  }

  function ligneInventaire(article) {
    const stock = Donnees.stockArticle(article.id);
    const saisie = memoire.saisiesInventaire.get(article.id) || '';
    const idChamp = 'magasin-inventaire-' + article.id;
    return UI.html`<tr>
      <td data-libelle="Référence">${lienArticle(article)}</td>
      <td data-libelle="Désignation">${article.designation}</td>
      <td data-libelle="Emplacement">${article.emplacement}</td>
      <td data-libelle="Stock calculé" class="num">${quantiteUnite(stock, article.unite)}</td>
      <td data-libelle="Stock compté" class="num"><label class="visuellement-cache" for="${idChamp}">Stock compté de ${article.reference}</label>
        <input type="text" inputmode="decimal" autocomplete="off" id="${idChamp}" data-inventaire="${article.id}" data-stock="${String(stock)}" value="${saisie}"></td>
      <td data-libelle="Écart" class="num" data-ecart="${article.id}">${ecartHtml(stock, saisie)}</td>
    </tr>`;
  }

  function resumeInventaire() {
    const saisies = Array.from(memoire.saisiesInventaire.values()).filter((valeur) => texte(valeur) !== '');
    return saisies.length ? saisies.length + ' article(s) compté(s), à valider.' : 'Aucun stock compté pour l\'instant.';
  }

  async function validerInventaire(panneau) {
    const comptages = [];
    const illisibles = [];
    memoire.saisiesInventaire.forEach((valeur, articleId) => {
      if (texte(valeur) === '') return;
      const quantite = Donnees.nombre(valeur);
      const article = Donnees.trouver('articles', articleId);
      if (quantite === null || quantite < 0) illisibles.push(article ? article.reference : articleId);
      else comptages.push({ articleId, quantite });
    });
    if (illisibles.length) { UI.toast('Stock compté illisible pour : ' + illisibles.join(', ') + '.', 'erreur'); return; }
    if (!comptages.length) { UI.toast('Saisissez le stock compté d\'au moins un article.', 'attention'); return; }
    const ecarts = comptages.filter((c) => c.quantite !== Donnees.stockArticle(c.articleId)).length;
    const accord = await UI.confirmer('Enregistrer le stock compté de ' + comptages.length + ' article(s), dont ' + ecarts
      + ' avec un écart ? Le stock compté remplace le stock calculé.', { titre: 'Valider l\'inventaire', oui: 'Enregistrer' });
    if (!accord) return;
    try {
      await Magasin.inventorier(comptages, UI.$('#magasin-inventaire-commentaire', panneau).value);
      memoire.saisiesInventaire.clear();
      await apresEcriture('Inventaire enregistré : ' + comptages.length + ' article(s).');
    } catch (erreur) {
      App.signalerErreur(erreur, 'inventaire');
    }
  }

  function afficherOngletInventaire(panneau) {
    if (!App.estResponsable()) {
      UI.remplir(panneau, UI.vide('Inventaire réservé au responsable', 'Le technicien consulte le stock dans l\'onglet Articles.', 'magasin'));
      return;
    }
    const filtres = Object.assign({ recherche: '', categorie: '' }, memoire.filtresInventaire || {});
    memoire.filtresInventaire = filtres;
    const articles = Donnees.lignes('articles').filter(estActif).sort((a, b) => texte(a.emplacement).localeCompare(texte(b.emplacement), 'fr', { numeric: true })
      || texte(a.reference).localeCompare(texte(b.reference), 'fr', { numeric: true }));
    const categories = new Map(articles.map((article) => [categorieArticle(article).code, categorieArticle(article).libelle]));
    UI.remplir(panneau, UI.html`
      <div class="encadre info">Comptez les pièces et saisissez le <b>stock compté</b> : l'écart avec le stock calculé s'affiche.
        Les lignes laissées vides ne changent rien. À la validation, le stock compté remplace le stock calculé (mouvement « inventaire »).</div>
      <form class="filtres magasin-filtres" id="magasin-filtres-inventaire" data-hors-saisie role="search" aria-label="Filtrer les articles à compter">
        <label class="visuellement-cache" for="magasin-inventaire-recherche">Rechercher un article</label>
        <input type="search" id="magasin-inventaire-recherche" name="recherche" value="${filtres.recherche}" placeholder="Référence, désignation, emplacement" autocomplete="off">
        <label class="visuellement-cache" for="magasin-inventaire-categorie">Catégorie</label>
        <select id="magasin-inventaire-categorie" name="categorie">${optionsHtml([{ valeur: '', libelle: 'Toutes catégories' }]
          .concat(Array.from(categories.entries()).map(([valeur, libelle]) => ({ valeur, libelle }))
            .sort((a, b) => a.libelle.localeCompare(b.libelle, 'fr'))), filtres.categorie)}</select>
      </form>
      <div class="carte magasin-inventaire"><div class="table-defile"><table class="table magasin-table-inventaire">
        <caption class="visuellement-cache">Inventaire : stock compté par article</caption>
        <thead><tr><th scope="col">Référence</th><th scope="col">Désignation</th><th scope="col">Emplacement</th>
          <th scope="col" class="num">Stock calculé</th><th scope="col" class="num">Stock compté</th><th scope="col" class="num">Écart</th></tr></thead>
        <tbody></tbody></table></div></div>
      <div class="carte magasin-inventaire-validation">
        <div class="form-ligne">
          <div class="champ"><label class="libelle" for="magasin-inventaire-commentaire">Commentaire (facultatif)</label>
            <input type="text" id="magasin-inventaire-commentaire" maxlength="200" placeholder="Ex. inventaire tournant, rayon A"></div>
          <button type="button" class="btn btn-primaire" id="magasin-valider-inventaire">${UI.icone('valider')}Valider l'inventaire</button>
        </div>
        <p class="note" id="magasin-inventaire-resume" role="status"></p>
      </div>`);
    const corps = UI.$('.magasin-table-inventaire tbody', panneau);
    const resume = UI.$('#magasin-inventaire-resume', panneau);
    function rafraichir() {
      const recherche = normaliser(memoire.filtresInventaire.recherche);
      const retenus = articles.filter((article) => (!memoire.filtresInventaire.categorie || categorieArticle(article).code === memoire.filtresInventaire.categorie)
        && (!recherche || normaliser([article.reference, article.designation, article.emplacement].join(' ')).includes(recherche)));
      UI.remplir(corps, retenus.length ? UI.html`${retenus.map(ligneInventaire)}`
        : UI.html`<tr><td colspan="6" class="vide-table">Aucun article ne correspond à ces filtres.</td></tr>`);
      resume.textContent = resumeInventaire();
    }
    corps.addEventListener('input', (evenement) => {
      const champ = evenement.target.closest('input[data-inventaire]');
      if (!champ) return;
      memoire.saisiesInventaire.set(champ.dataset.inventaire, champ.value);
      UI.remplir(UI.$('[data-ecart="' + champ.dataset.inventaire + '"]', corps), ecartHtml(Number(champ.dataset.stock), champ.value));
      resume.textContent = resumeInventaire();
    });
    const formulaire = UI.$('#magasin-filtres-inventaire', panneau);
    const lireFiltres = () => { memoire.filtresInventaire = UI.lireFormulaire(formulaire); rafraichir(); };
    formulaire.addEventListener('input', lireFiltres);
    formulaire.addEventListener('change', lireFiltres);
    formulaire.addEventListener('submit', (evenement) => evenement.preventDefault());
    UI.$('#magasin-valider-inventaire', panneau).addEventListener('click', () => validerInventaire(panneau));
    rafraichir();
  }

  // ===========================================================================================
  // 13. Fenêtre « Entrée en stock » (fiche article, responsable)
  // ===========================================================================================

  async function ouvrirEntree(article) {
    const champs = [
      UI.champ({ nom: 'quantite', type: 'decimal', libelle: 'Quantité entrée' + (article.unite ? ' (' + article.unite + ')' : '') }, '', { obligatoire: true }),
      UI.champ({ nom: 'commentaire', type: 'texte', libelle: 'Commentaire' }, '', { placeholder: 'Ex. pièce récupérée sur un équipement réformé' }),
    ];
    const id = await fenetreSaisie({
      titre: 'Entrée en stock', champs, libelleValider: 'Enregistrer l\'entrée',
      introduction: UI.html`<p><b>${libelleArticle(article)}</b> — stock actuel : ${quantiteUnite(Donnees.stockArticle(article.id), article.unite)}.</p>
        <p class="note">Pour une livraison de fournisseur, réceptionnez plutôt l'achat (onglet Achats).</p>`,
      action: (valeurs) => Magasin.entrer(article.id, valeurs.quantite, valeurs.commentaire),
    });
    if (id) await apresEcriture('Entrée en stock enregistrée.');
  }

  // Outils prêtés aux autres fichiers du module (usage interne).
  Object.assign(Magasin.interne, { badgeMouvement, afficherOngletMouvements, afficherOngletInventaire, ouvrirEntree });

  return {};
})());
