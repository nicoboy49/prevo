'use strict';
// Magasin : module M5 « Magasin » de Prévo — articles, mouvements de stock, inventaire, articles à
// commander, achats et fournisseurs ; règle RG6 « stock jamais négatif » (ARCHITECTURE.md §14.4 ;
// brief §7 RG6, §9 E9).
//
// Le module est découpé en cinq fichiers, chargés dans cet ordre par index.html (§14.2) :
//   magasin-regles.js       CE FICHIER, qui crée l'objet Magasin : règles PURES
//                             1. Constantes et petits outils
//                             2. Point de commande suggéré (D23), articles à commander, sorties d'un OT
//   magasin-ecritures.js    sortir, retourner, entrer, inventorier, achats, fournisseurs
//   magasin-articles.js     écran #/magasin, liste et fiche des articles
//   magasin-mouvements.js   mouvements de stock et inventaire
//   magasin-achats.js       articles à commander, achats et fournisseurs
//
// Les fichiers suivants complètent l'objet : Object.assign(Magasin, (() => { … })()). Une
// fonction dont un autre fichier du module a besoin est rangée dans Magasin.interne (usage
// interne au module : ce n'est pas une API, ni les autres modules ni les tests ne s'en servent).
//
// Les fonctions de ce fichier sont PURES : elles lisent Donnees, n'écrivent jamais. Le stock d'un
// article est toujours Donnees.stockArticle(id), recalculé depuis les mouvements (un inventaire
// fixe la valeur) ; la colonne articles.stock n'est qu'une copie lisible dans Excel.

const Magasin = (() => {

  // ===========================================================================================
  // 1. Constantes et petits outils
  // ===========================================================================================

  // Valeurs du schéma (js/schema.js) : une seule source, la liste suit le schéma.
  const TYPES_MOUVEMENT = Object.freeze(Schema.champ('mouvements_stock', 'type').valeurs.slice());
  const STATUTS_ACHAT = Object.freeze(Schema.champ('achats', 'statut').valeurs.slice());

  // D23 : la consommation est mesurée sur les 365 derniers jours (aujourd'hui compris).
  const FENETRE_CONSOMMATION_JOURS = 365;
  const MILLISECONDES_PAR_JOUR = 86400000;
  const MOTIF_DATE_ISO = /^(\d{4})-(\d{2})-(\d{2})/;

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  /** Nombre lu dans une valeur du fichier ; vide ou illisible → 0. */
  function nombre(valeur) {
    return Donnees.nombre(valeur) || 0;
  }

  function arrondi(valeur, decimales) {
    const facteur = Math.pow(10, decimales === undefined ? 2 : decimales);
    return Math.round(valeur * facteur) / facteur;
  }

  /** Date ISO + n jours (calcul en UTC : un changement d'heure ne décale jamais un jour). */
  function ajouterJours(dateIso, jours) {
    const morceaux = MOTIF_DATE_ISO.exec(texte(dateIso));
    if (!morceaux) return '';
    const date = new Date(Date.UTC(Number(morceaux[1]), Number(morceaux[2]) - 1, Number(morceaux[3]))
      + jours * MILLISECONDES_PAR_JOUR);
    return date.getUTCFullYear() + '-' + String(date.getUTCMonth() + 1).padStart(2, '0')
      + '-' + String(date.getUTCDate()).padStart(2, '0');
  }

  /** Date du jour à utiliser : celle passée en argument (10 premiers caractères), sinon aujourd'hui. */
  function dateDuJour(aujourdhui) {
    const date = texte(aujourdhui).slice(0, 10);
    return MOTIF_DATE_ISO.test(date) ? date : Donnees.aujourdhui();
  }

  /** « REF-12 — Garniture mécanique » (référence puis désignation). */
  function libelleArticle(article) {
    if (!article) return '';
    return (article.reference ? article.reference + ' — ' : '') + (article.designation || article.id);
  }

  function comparerMouvements(a, b) {
    if (a.date !== b.date) return a.date < b.date ? -1 : 1;
    return texte(a.id).localeCompare(texte(b.id), 'fr', { numeric: true });
  }

  /** Nombre écrit dans un fichier : '2.5' (6 décimales au plus, jamais 0.30000000000000004). */
  function valeurFichier(valeur) {
    return String(arrondi(valeur, 6));
  }

  /** Nombre dans un message : '2,5' (virgule décimale, sans espace de milliers). */
  function nombreTexte(valeur) {
    return valeurFichier(valeur).replace('.', ',');
  }

  /** Texte comparable : le pliage de toute recherche (UI.normaliserRecherche, D154 ; « Écrou  M8 » → « ecrou m8 »). */
  function normaliser(valeur) {
    return UI.normaliserRecherche(valeur);
  }

  // Catégorie d'un article = préfixe de sa référence (« ROU-001 » → ROU). Les préfixes connus ont
  // un libellé ; un autre préfixe est affiché tel quel ; sans préfixe : « Sans catégorie ».
  // Fonctions (et non texte figé) : le libellé est lu au moment de l'affichage.
  const LIBELLES_CATEGORIES = {
    ROU: () => I18n.t('magasin.rou.roulements'), TRA: () => I18n.t('magasin.tra.transmission'), ETA: () => I18n.t('magasin.eta.etancheite'), FIL: () => I18n.t('magasin.fil.filtration'), LUB: () => I18n.t('magasin.lub.lubrification'),
    ELE: () => I18n.t('magasin.ele.electricite'), HYD: () => I18n.t('magasin.hyd.hydraulique'), PNE: () => I18n.t('magasin.pne.pneumatique'), OUT: () => I18n.t('magasin.out.outillage'), DIV: () => I18n.t('magasin.div.divers'),
  };

  /** { code, libelle } de la catégorie d'un article (code '' : sans catégorie). */
  function categorieArticle(article) {
    const morceaux = /^([A-Za-z]{2,6})[-_ .]/.exec(texte(article && article.reference));
    if (!morceaux) return { code: '', libelle: I18n.t('magasin.categorie_article.sans_categorie') };
    const code = morceaux[1].toUpperCase();
    return { code, libelle: LIBELLES_CATEGORIES[code] ? LIBELLES_CATEGORIES[code]() : code };
  }

  /** Vrai si l'article est actif (champ actif différent de '0'). */
  function estActif(article) {
    return Boolean(article) && texte(article.actif) !== '0';
  }

  /** Vrai si l'article est « à commander » (RG6) : actif, point de commande renseigné, stock ≤ point. */
  function estACommander(article, stock) {
    const pointCommande = Donnees.nombre(article && article.point_commande);
    if (!estActif(article) || pointCommande === null) return false;
    return (stock === undefined ? Donnees.stockArticle(article.id) : stock) <= pointCommande;
  }

  // Ordre chronologique d'un mouvement : date puis identifiant (même règle que Donnees.stockArticle).
  function ordreChronologique(a, b) {
    if (a.date !== b.date) return a.date < b.date ? -1 : 1;
    if (a.id !== b.id) return a.id < b.id ? -1 : 1;
    return 0;
  }

  /**
   * Stock d'un article calculé sur une liste de mouvements DONNÉE (même règle que
   * Donnees.stockArticle : un inventaire fixe la valeur, une entrée ou un retour ajoute, une sortie
   * retire). Sert dans les fonctions de mutation, sur les lignes fraîches de mouvements_stock.
   */
  function stockDepuisLignes(lignesMouvements, articleId) {
    let stock = 0;
    lignesMouvements.filter((mouvement) => mouvement.article_id === articleId).sort(ordreChronologique)
      .forEach((mouvement) => {
        const quantite = nombre(mouvement.quantite);
        if (mouvement.type === 'inventaire') stock = quantite;
        else if (mouvement.type === 'entrée' || mouvement.type === 'retour') stock += quantite;
        else if (mouvement.type === 'sortie') stock -= quantite;
      });
    return arrondi(stock, 6);
  }

  /** Quantité nette sortie (sorties − retours) d'un article pour un OT, sur une liste de mouvements donnée. */
  function netSortiDepuisLignes(lignesMouvements, otId, articleId) {
    let net = 0;
    lignesMouvements.forEach((mouvement) => {
      if (mouvement.ot_id !== otId || mouvement.article_id !== articleId) return;
      if (mouvement.type === 'sortie') net += nombre(mouvement.quantite);
      else if (mouvement.type === 'retour') net -= nombre(mouvement.quantite);
    });
    return arrondi(net, 6);
  }

  // ===========================================================================================
  // 2. Règles PURES (ARCHITECTURE.md §14.4)
  // ===========================================================================================

  /**
   * Sorties et retours d'un article entre deux dates ISO comprises : { sorties, retours }.
   * La date d'un mouvement est 'AAAA-MM-JJ HH:MM' : seul le jour compte.
   */
  function consommationEntre(articleId, debut, fin) {
    const cumul = { sorties: 0, retours: 0 };
    Donnees.lignes('mouvements_stock').forEach((mouvement) => {
      if (mouvement.article_id !== articleId) return;
      const jour = texte(mouvement.date).slice(0, 10);
      if (!MOTIF_DATE_ISO.test(jour) || jour < debut || jour > fin) return;
      if (mouvement.type === 'sortie') cumul.sorties += nombre(mouvement.quantite);
      else if (mouvement.type === 'retour') cumul.retours += nombre(mouvement.quantite);
    });
    return cumul;
  }

  /**
   * Point de commande SUGGÉRÉ (D23 ; le point de commande, lui, reste saisi) :
   *   (sorties − retours des 365 derniers jours) / 365 × delai_jours + stock_securite,
   *   arrondi à l'unité supérieure. null s'il n'y a aucune sortie sur la période (« non calculable »)
   *   ou si l'article n'existe pas. Délai ou stock de sécurité vide : compté 0.
   */
  function suggestionPointCommande(articleId, aujourdhui) {
    const article = Donnees.trouver('articles', articleId);
    if (!article) return null;
    const fin = dateDuJour(aujourdhui);
    const debut = ajouterJours(fin, -(FENETRE_CONSOMMATION_JOURS - 1));
    const { sorties, retours } = consommationEntre(articleId, debut, fin);
    if (sorties <= 0) return null;
    const consommation = Math.max(0, sorties - retours);
    const delai = Math.max(0, nombre(article.delai_jours));
    const securite = Math.max(0, nombre(article.stock_securite));
    // Multiplier avant de diviser, puis arrondir à 6 décimales : 73 × 10 / 365 donne bien 2.
    return Math.ceil(arrondi((consommation * delai) / FENETRE_CONSOMMATION_JOURS + securite, 6));
  }

  /** Quantité proposée à la commande : qte_commande si renseignée, sinon point − stock + sécurité (au moins 1). */
  function quantiteProposee(article, stock, pointCommande) {
    const quantiteFixe = Donnees.nombre(article.qte_commande);
    const quantite = quantiteFixe !== null && quantiteFixe > 0
      ? quantiteFixe
      : pointCommande - stock + nombre(article.stock_securite);
    return Math.max(1, arrondi(quantite, 6));
  }

  /**
   * Articles à commander (RG6) : articles actifs dont le point de commande est renseigné et dont
   * le stock est inférieur ou égal à ce point. Les articles critiques d'abord, puis par référence.
   * → [{ article (ligne), stock, pointCommande, quantiteProposee }]
   */
  function aCommander() {
    const liste = [];
    Donnees.lignes('articles').forEach((article) => {
      if (texte(article.actif) === '0') return;
      const pointCommande = Donnees.nombre(article.point_commande);
      if (pointCommande === null) return;
      const stock = Donnees.stockArticle(article.id);
      if (stock > pointCommande) return;
      liste.push({ article, stock, pointCommande, quantiteProposee: quantiteProposee(article, stock, pointCommande) });
    });
    return liste.sort((a, b) => (b.article.critique === '1') - (a.article.critique === '1')
      || texte(a.article.reference || a.article.id).localeCompare(texte(b.article.reference || b.article.id), 'fr', { numeric: true }));
  }

  /**
   * Pièces sorties pour un OT, article par article (dans l'ordre de la première sortie) :
   * [{ articleId, sorti, retourne, net }] où net = sorti − retourné.
   */
  function sortiesDeLOt(otId) {
    const parArticle = new Map();
    Donnees.lignes('mouvements_stock')
      .filter((mouvement) => mouvement.ot_id === otId && (mouvement.type === 'sortie' || mouvement.type === 'retour'))
      .sort(comparerMouvements)
      .forEach((mouvement) => {
        const ligne = parArticle.get(mouvement.article_id) || { articleId: mouvement.article_id, sorti: 0, retourne: 0, net: 0 };
        if (mouvement.type === 'sortie') ligne.sorti += nombre(mouvement.quantite);
        else ligne.retourne += nombre(mouvement.quantite);
        parArticle.set(mouvement.article_id, ligne);
      });
    return Array.from(parArticle.values()).map((ligne) => ({
      articleId: ligne.articleId,
      sorti: arrondi(ligne.sorti, 6),
      retourne: arrondi(ligne.retourne, 6),
      net: arrondi(ligne.sorti - ligne.retourne, 6),
    }));
  }

  return {
    TYPES_MOUVEMENT, STATUTS_ACHAT,
    // règles pures (ARCHITECTURE.md §14.4) ; le stock d'un article est Donnees.stockArticle(id)
    suggestionPointCommande, aCommander, sortiesDeLOt,
    // Usage interne au module : outils prêtés aux fichiers magasin-*.js, qui y ajoutent les leurs
    // par Object.assign(Magasin.interne, …). Pas une API : son contenu peut changer à tout moment.
    interne: {
      FENETRE_CONSOMMATION_JOURS,
      texte, nombre, arrondi, ajouterJours, dateDuJour, libelleArticle, consommationEntre,
      valeurFichier, nombreTexte, normaliser, categorieArticle, estActif, estACommander,
      stockDepuisLignes, netSortiDepuisLignes,
    },
  };
})();
