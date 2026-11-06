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
    return UI.badgeValeur('mouvements_stock', 'type', type, TONS_MOUVEMENT[type] || 'neutre');
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
      { cle: 'date', libelle: I18n.t('commun.champ.date'), classe: 'sans-coupure', rendu: (m) => UI.dateHeureFr(m.date) },
      { cle: 'article_id', libelle: I18n.t('commun.champ.article'), valeurTri: (m) => texte((articleDe(m) || {}).reference),
        rendu: (m) => (articleDe(m) ? UI.html`${lienArticle(articleDe(m))} <span class="muted">${articleDe(m).designation}</span>` : m.article_id) },
      { cle: 'type', libelle: I18n.t('magasin.colonnes_mouvements.type'), rendu: (m) => badgeMouvement(m.type) },
      { cle: 'quantite', libelle: I18n.t('commun.champ.quantite'), type: 'nombre', rendu: (m) => UI.nombreFr(m.quantite) },
      { cle: 'ot_id', libelle: I18n.t('magasin.colonnes_mouvements.ot'), classe: 'sans-coupure', rendu: (m) => lienOt(m.ot_id) },
      { cle: 'utilisateur', libelle: I18n.t('magasin.colonnes_mouvements.par') },
      { cle: 'commentaire', libelle: I18n.t('commun.champ.commentaire'), classe: 'magasin-col-commentaire' },
    ];
  }

  function carteMouvement(m) {
    const article = articleDe(m);
    return UI.html`<div class="carte-ligne">
      <div class="carte-tete"><b>${article ? article.reference : m.article_id}</b>${badgeMouvement(m.type)}</div>
      <div class="carte-titre">${article ? article.designation : ''}</div>
      <div class="carte-meta">${I18n.html('magasin.carte_mouvement.date_quantite_quantite', { date: UI.dateHeureFr(m.date), quantite: UI.nombreFr(m.quantite) })}
        ${m.ot_id ? UI.html`<span>${lienOt(m.ot_id)}</span>` : ''}${m.utilisateur ? UI.html`<span>${m.utilisateur}</span>` : ''}</div>
      ${m.commentaire ? UI.html`<div class="carte-meta">${m.commentaire}</div>` : ''}</div>`;
  }

  function afficherOngletMouvements(panneau, requete) {
    const filtres = filtresMouvements(requete);
    const tous = Donnees.lignes('mouvements_stock');
    const optionsArticles = [{ valeur: '', libelle: I18n.t('magasin.onglet_mouvements.tous_articles') }].concat(Donnees.lignes('articles').slice()
      .sort((a, b) => texte(a.reference).localeCompare(texte(b.reference), 'fr', { numeric: true }))
      .map((article) => ({ valeur: article.id, libelle: libelleArticle(article) })));
    UI.remplir(panneau, UI.html`
      <form class="filtres magasin-filtres" id="magasin-filtres-mouvements" data-hors-saisie role="search" aria-label="${I18n.t('magasin.onglet_mouvements.filtrer_mouvements')}">
        <label class="visuellement-cache" for="magasin-filtre-type">${I18n.t('magasin.onglet_mouvements.type_mouvement')}</label>
        <select id="magasin-filtre-type" name="type">${optionsHtml([{ valeur: '', libelle: I18n.t('magasin.onglet_mouvements.tous_types') }]
          .concat(TYPES_MOUVEMENT.map((type) => ({ valeur: type, libelle: Schema.libelleValeur('mouvements_stock', 'type', type) }))), filtres.type)}</select>
        <label class="visuellement-cache" for="magasin-filtre-article">${I18n.t('commun.champ.article')}</label>
        <select id="magasin-filtre-article" name="article">${optionsHtml(optionsArticles, filtres.article)}</select>
        <label class="visuellement-cache" for="magasin-filtre-ot">${I18n.t('magasin.onglet_mouvements.ordre_travail')}</label>
        <input type="search" id="magasin-filtre-ot" name="ot" value="${filtres.ot}" placeholder="${I18n.t('magasin.onglet_mouvements.ot_ex_ot_2026')}" autocomplete="off">
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
        colonnes: colonnesMouvements(), lignes, carte: carteMouvement, libelle: I18n.t('magasin.onglet_mouvements.mouvements_stock'),
        vide: I18n.t('magasin.onglet_mouvements.aucun_mouvement_correspond_filtres'),
      }));
      compteur.textContent = I18n.t('magasin.onglet_mouvements.n_mouvement_nb_tous', { n: retenus.length, nbTous: tous.length }) + (retenus.length > LIMITE_MOUVEMENTS ? ' ' + I18n.t('magasin.onglet_mouvements.plus_recents_sont_affiches', { limite: LIMITE_MOUVEMENTS }) : '');
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
    if (compte === null || compte < 0) return UI.html`<span class="badge ko">${I18n.t('magasin.ecart.illisible')}</span>`;
    const ecart = Math.round((compte - stock) * 1e6) / 1e6;
    if (ecart === 0) return UI.html`<span class="badge ok magasin-ecart">0</span>`;
    return UI.html`<span class="badge ${ecart > 0 ? 'info' : 'attention'} magasin-ecart">${ecart > 0 ? '+' : '−'}${nombreTexte(Math.abs(ecart))}</span>`;
  }

  function ligneInventaire(article) {
    const stock = Donnees.stockArticle(article.id);
    const saisie = memoire.saisiesInventaire.get(article.id) || '';
    const idChamp = 'magasin-inventaire-' + article.id;
    return UI.html`<tr>
      <td data-libelle="${I18n.t('commun.champ.reference')}">${lienArticle(article)}</td>
      <td data-libelle="${I18n.t('commun.champ.designation')}">${article.designation}</td>
      <td data-libelle="${I18n.t('magasin.inventaire.emplacement')}">${article.emplacement}</td>
      <td data-libelle="${I18n.t('magasin.inventaire.stock_calcule')}" class="num">${quantiteUnite(stock, article.unite)}</td>
      <td data-libelle="${I18n.t('magasin.inventaire.stock_compte')}" class="num"><label class="visuellement-cache" for="${idChamp}">${I18n.t('magasin.ligne_inventaire.stock_compte', { reference: article.reference })}</label>
        <input type="text" inputmode="decimal" autocomplete="off" id="${idChamp}" data-inventaire="${article.id}" data-stock="${String(stock)}" value="${saisie}"></td>
      <td data-libelle="${I18n.t('magasin.inventaire.ecart')}" class="num" data-ecart="${article.id}">${ecartHtml(stock, saisie)}</td>
    </tr>`;
  }

  function resumeInventaire() {
    const saisies = Array.from(memoire.saisiesInventaire.values()).filter((valeur) => texte(valeur) !== '');
    return saisies.length ? I18n.t('magasin.resume_inventaire.article_compte_valider', { n: saisies.length }) : I18n.t('magasin.resume_inventaire.aucun_stock_compte_instant');
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
    if (illisibles.length) { UI.toast(I18n.t('magasin.valider_inventaire.stock_compte_illisible', { join: illisibles.join(', ') }), 'erreur'); return; }
    if (!comptages.length) { UI.toast(I18n.t('magasin.valider_inventaire.saisissez_stock_compte_moins'), 'attention'); return; }
    const ecarts = comptages.filter((c) => c.quantite !== Donnees.stockArticle(c.articleId)).length;
    const accord = await UI.confirmer(I18n.t('magasin.valider_inventaire.enregistrer_stock_compte_article', { n: comptages.length, ecarts }), { titre: I18n.t('magasin.valider_inventaire.valider_inventaire'), oui: I18n.t('commun.bouton.enregistrer') });
    if (!accord) return;
    try {
      await Magasin.inventorier(comptages, UI.$('#magasin-inventaire-commentaire', panneau).value);
      memoire.saisiesInventaire.clear();
      await apresEcriture(I18n.t('magasin.valider_inventaire.inventaire_enregistre_article', { n: comptages.length }));
    } catch (erreur) {
      App.signalerErreur(erreur, 'inventaire');
    }
  }

  function afficherOngletInventaire(panneau) {
    if (!App.estResponsable()) {
      UI.remplir(panneau, UI.vide(I18n.t('magasin.onglet_inventaire.inventaire_reserve_responsable'), I18n.t('magasin.onglet_inventaire.technicien_consulte_stock_onglet'), 'magasin'));
      return;
    }
    const filtres = Object.assign({ recherche: '', categorie: '' }, memoire.filtresInventaire || {});
    memoire.filtresInventaire = filtres;
    const articles = Donnees.lignes('articles').filter(estActif).sort((a, b) => texte(a.emplacement).localeCompare(texte(b.emplacement), 'fr', { numeric: true })
      || texte(a.reference).localeCompare(texte(b.reference), 'fr', { numeric: true }));
    const categories = new Map(articles.map((article) => [categorieArticle(article).code, categorieArticle(article).libelle]));
    UI.remplir(panneau, UI.html`
      <div class="encadre info">${I18n.html('magasin.onglet_inventaire.comptez_pieces_saisissez_stock')}</div>
      <form class="filtres magasin-filtres" id="magasin-filtres-inventaire" data-hors-saisie role="search" aria-label="${I18n.t('magasin.onglet_inventaire.filtrer_articles_compter')}">
        <label class="visuellement-cache" for="magasin-inventaire-recherche">${I18n.t('magasin.onglet_inventaire.rechercher_article')}</label>
        <input type="search" id="magasin-inventaire-recherche" name="recherche" value="${filtres.recherche}" placeholder="${I18n.t('magasin.onglet_inventaire.reference_designation_emplacement')}" autocomplete="off">
        <label class="visuellement-cache" for="magasin-inventaire-categorie">${I18n.t('magasin.onglet_inventaire.categorie')}</label>
        <select id="magasin-inventaire-categorie" name="categorie">${optionsHtml([{ valeur: '', libelle: I18n.t('magasin.onglet_inventaire.toutes_categories') }]
          .concat(Array.from(categories.entries()).map(([valeur, libelle]) => ({ valeur, libelle }))
            .sort((a, b) => a.libelle.localeCompare(b.libelle, 'fr'))), filtres.categorie)}</select>
      </form>
      <div class="carte magasin-inventaire"><div class="table-defile"><table class="table magasin-table-inventaire">
        <caption class="visuellement-cache">${I18n.t('magasin.onglet_inventaire.inventaire_stock_compte_article')}</caption>
        <thead><tr><th scope="col">${I18n.t('commun.champ.reference')}</th><th scope="col">${I18n.t('commun.champ.designation')}</th><th scope="col">${I18n.t('magasin.onglet_inventaire.emplacement')}</th>
          <th scope="col" class="num">${I18n.t('magasin.onglet_inventaire.stock_calcule')}</th><th scope="col" class="num">${I18n.t('magasin.onglet_inventaire.stock_compte')}</th><th scope="col" class="num">${I18n.t('magasin.onglet_inventaire.ecart')}</th></tr></thead>
        <tbody></tbody></table></div></div>
      <div class="carte magasin-inventaire-validation">
        <div class="form-ligne">
          <div class="champ"><label class="libelle" for="magasin-inventaire-commentaire">${I18n.t('magasin.onglet_inventaire.commentaire_facultatif')}</label>
            <input type="text" id="magasin-inventaire-commentaire" maxlength="200" placeholder="${I18n.t('magasin.onglet_inventaire.ex_inventaire_tournant_rayon')}"></div>
          <button type="button" class="btn btn-primaire" id="magasin-valider-inventaire">${UI.icone('valider')}${I18n.t('magasin.valider_inventaire.valider_inventaire')}</button>
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
        : UI.html`<tr><td colspan="6" class="vide-table">${I18n.t('magasin.onglet_inventaire.aucun_article_correspond_filtres')}</td></tr>`);
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
      UI.champ({ nom: 'quantite', type: 'decimal', libelle: article.unite ? I18n.t('magasin.ouvrir_entree.quantite_entree', { unite: article.unite }) : I18n.t('magasin.ouvrir_entree.quantite_entree_2') }, '', { obligatoire: true }),
      UI.champ({ nom: 'commentaire', type: 'texte', libelle: I18n.t('commun.champ.commentaire') }, '', { placeholder: I18n.t('magasin.ouvrir_entree.ex_piece_recuperee_equipement') }),
    ];
    const id = await fenetreSaisie({
      titre: I18n.t('magasin.ouvrir_entree.entree_stock'), champs, libelleValider: I18n.t('magasin.ouvrir_entree.enregistrer_entree'),
      introduction: UI.html`<p>${I18n.html('magasin.ouvrir_entree.stock_actuel', { libelleArticle: libelleArticle(article), quantiteUnite: quantiteUnite(Donnees.stockArticle(article.id), article.unite) })}</p>
        <p class="note">${I18n.t('magasin.ouvrir_entree.livraison_fournisseur_receptionnez_plutot')}</p>`,
      action: (valeurs) => Magasin.entrer(article.id, valeurs.quantite, valeurs.commentaire),
    });
    if (id) await apresEcriture(I18n.t('magasin.ouvrir_entree.entree_stock_enregistree'));
  }

  // Outils prêtés aux autres fichiers du module (usage interne).
  Object.assign(Magasin.interne, { badgeMouvement, afficherOngletMouvements, afficherOngletInventaire, ouvrirEntree });

  return {};
})());
