'use strict';
// Wiki (2/8) — couches calculées du composant et du mode, pages et catalogue (lot 6 refondu,
// ARCHITECTURE.md §20.3 ; tâche T112). Tout est relu dans Donnees.lignes à chaque appel : rien n'est
// écrit, rien n'est gardé entre deux appels, aucun appel réseau, aucune IA.
//
// Définitions (§20.3 et précisions de T112, rapport .chantier/rapports/T112.md) :
// - page active : ligne de wiki_pages dont le statut n'est pas « archivée » ;
// - page ancrée : ligne active de type « équipement » dont l'equipement_id existe, ou de type
//   « composant » dont l'article_id existe ; son identifiant canonique est l'EQ-… ou l'ART-… (son titre est
//   celui que Prévo impose) ; toute autre page active garde son WP-… ;
// - OT clôturé : statut « Clôturé techniquement » ou « Clôturé administrativement » ;
// - consommation d'un article : OT clôturé dont la quantité nette sortie de l'article (sorties − retours
//   liés à cet OT) est positive ; sa date est le jour de la date de fin de l'OT ;
// - cas d'une cause : OT correctif (type commençant par « correctif ») clôturé, de cette cause (le code
//   symptôme n'est pas exigé) ;
// - un équipement inconnu (référence cassée) n'entre dans aucune liste d'équipements ;
// - les tris départagent par l'ordre des caractères (reproductible par tests/calcul_wiki.py).

Object.assign(Wiki, (() => {

  const STATUTS_CLOTURES = ['Clôturé techniquement', 'Clôturé administrativement'];
  const PHRASE_SAVOIR_FAIRE = 'Ce savoir-faire ne remplace pas la consignation de l\'équipement';
  const MILLISECONDES_PAR_JOUR = 86400000;

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  /** Valeur telle quelle (sans rien retirer) ; '' si absente. */
  function brut(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur);
  }

  /** Ordre des caractères (pas celui de la langue) : le calcul Python de contrôle trie de même. */
  function comparer(a, b) {
    return a < b ? -1 : (a > b ? 1 : 0);
  }

  /** 'AAAA-MM-JJ…' → 'AAAA-MM-JJ'. */
  function jour(valeur) {
    return texte(valeur).slice(0, 10);
  }

  /** Instant UTC d'un jour 'AAAA-MM-JJ', ou null si ce n'est pas une date du calendrier. */
  function instantDuJour(jourIso) {
    const morceaux = /^(\d{4})-(\d{2})-(\d{2})$/.exec(jourIso);
    if (!morceaux) return null;
    const instant = Date.UTC(Number(morceaux[1]), Number(morceaux[2]) - 1, Number(morceaux[3]));
    return new Date(instant).toISOString().slice(0, 10) === jourIso ? instant : null;
  }

  /** Médiane d'une liste de nombres (moyenne des deux du milieu pour un nombre pair) ; null si vide. */
  function mediane(valeurs) {
    const triees = valeurs.slice().sort((a, b) => a - b);
    if (!triees.length) return null;
    const milieu = Math.floor(triees.length / 2);
    return triees.length % 2 ? triees[milieu] : (triees[milieu - 1] + triees[milieu]) / 2;
  }

  function estCloture(ot) {
    return STATUTS_CLOTURES.includes(texte(ot.statut));
  }

  function estCorrectif(ot) {
    return /^correctif/.test(texte(ot.type));
  }

  function estActive(ligne) {
    return texte(ligne.statut) !== 'archivée';
  }

  function equipement(id) {
    return id ? Donnees.trouver('equipements', id) : undefined;
  }

  function titreEquipement(ligne) {
    return [texte(ligne.repere), texte(ligne.designation)].filter(Boolean).join(' — ');
  }

  function titreArticle(ligne) {
    return texte(ligne.designation) || texte(ligne.reference) || texte(ligne.id);
  }

  /** Libellé d'un code de la famille (la première ligne fait foi) ; le code s'il est inconnu ou sans libellé. */
  function libelleCode(famille, code) {
    const ligne = Donnees.lignes('codes_defaillance')
      .find((candidat) => texte(candidat.famille) === famille && texte(candidat.code) === code);
    return (ligne && texte(ligne.libelle)) || code;
  }

  /** Trie une liste d'éléments { equipementId, repere } par repère puis identifiant. */
  function parRepere(a, b) {
    return comparer(a.repere, b.repere) || comparer(a.equipementId, b.equipementId);
  }

  // ===========================================================================================
  // 1. Composant ancré (article) : article, montage, consommations, remplacements
  // ===========================================================================================

  /**
   * Consommations d'un article : [{ otId, date, equipementId, quantite }], une par OT clôturé dont la
   * quantité nette sortie (sorties − retours de cet article liés à l'OT) est positive ; du plus récent
   * au plus ancien (jour de la date de fin), puis par identifiant d'OT.
   */
  function consommationsDe(articleId) {
    const nets = new Map();                      // OT → quantité nette, dans l'ordre de la table
    Donnees.lignes('mouvements_stock').forEach((mouvement) => {
      const type = texte(mouvement.type);
      const otId = texte(mouvement.ot_id);
      if (texte(mouvement.article_id) !== articleId || !otId || (type !== 'sortie' && type !== 'retour')) return;
      const quantite = Donnees.nombre(mouvement.quantite) || 0;
      nets.set(otId, (nets.get(otId) || 0) + (type === 'sortie' ? quantite : -quantite));
    });
    const consommations = [];
    nets.forEach((quantite, otId) => {
      const ot = Donnees.trouver('ordres_travail', otId);
      if (!(quantite > 0) || !ot || !estCloture(ot)) return;
      consommations.push({ otId, date: jour(ot.date_fin), equipementId: texte(ot.equipement_id), quantite });
    });
    return consommations.sort((a, b) => comparer(b.date, a.date) || comparer(a.otId, b.otId));
  }

  /**
   * Montage d'un article : équipements de article_equipement (quantité de la première ligne, en texte) et
   * équipements où il a été consommé (quantité vide s'il ne l'est que là) ; source « liste »,
   * « consommation » ou « les deux » ; par repère.
   */
  function montageDe(articleId, consommations) {
    const parEquipement = new Map();             // équipement → { quantite, liste, consomme }
    Donnees.lignes('article_equipement').forEach((ligne) => {
      const equipementId = texte(ligne.equipement_id);
      if (texte(ligne.article_id) !== articleId || !equipementId || parEquipement.has(equipementId)) return;
      parEquipement.set(equipementId, { quantite: texte(ligne.quantite), liste: true, consomme: false });
    });
    consommations.forEach((consommation) => {
      const entree = parEquipement.get(consommation.equipementId) || { quantite: '', liste: false };
      entree.consomme = true;
      parEquipement.set(consommation.equipementId, entree);
    });
    const montage = [];
    parEquipement.forEach((entree, equipementId) => {
      const ligne = equipement(equipementId);
      if (!ligne) return;
      const source = entree.liste && entree.consomme ? 'les deux' : (entree.liste ? 'liste' : 'consommation');
      montage.push({ equipementId, repere: texte(ligne.repere), quantite: entree.quantite, source });
    });
    return montage.sort(parRepere);
  }

  /**
   * Remplacements par équipement : [{ equipementId, repere, nombre, intervalleMedianJours }] — nombre d'OT
   * qui l'ont consommé ; médiane des écarts en jours entre leurs dates d'intervention successives (jours
   * lisibles seulement), null sous 2 dates ; par repère.
   */
  function remplacementsDe(consommations) {
    const parEquipement = new Map();             // équipement → { nombre, instants }
    consommations.forEach((consommation) => {
      if (!parEquipement.has(consommation.equipementId)) parEquipement.set(consommation.equipementId, { nombre: 0, instants: [] });
      const entree = parEquipement.get(consommation.equipementId);
      entree.nombre += 1;
      const instant = instantDuJour(consommation.date);
      if (instant !== null) entree.instants.push(instant);
    });
    const remplacements = [];
    parEquipement.forEach((entree, equipementId) => {
      const ligne = equipement(equipementId);
      if (!ligne) return;
      const instants = entree.instants.slice().sort((a, b) => a - b);
      const ecarts = instants.slice(1).map((instant, rang) => Math.round((instant - instants[rang]) / MILLISECONDES_PAR_JOUR));
      remplacements.push({
        equipementId, repere: texte(ligne.repere), nombre: entree.nombre,
        intervalleMedianJours: instants.length < 2 ? null : mediane(ecarts),
      });
    });
    return remplacements.sort(parRepere);
  }

  function stockDe(article) {
    return typeof Donnees.stockArticle === 'function' ? Donnees.stockArticle(texte(article.id)) : Donnees.nombre(article.stock);
  }

  /**
   * Couche calculée d'un composant ancré (§20.3) : { article, montage, consommations, remplacements },
   * ou null si l'article n'existe pas.
   */
  function pageComposant(articleId) {
    const id = texte(articleId);
    const article = id ? Donnees.trouver('articles', id) : undefined;
    if (!article) return null;
    const consommations = consommationsDe(id);
    return {
      article: {
        id, reference: texte(article.reference), designation: texte(article.designation),
        fabricant: texte(article.fabricant), refFabricant: texte(article.ref_fabricant),
        emplacement: texte(article.emplacement), stock: stockDe(article),
      },
      montage: montageDe(id, consommations),
      consommations,
      remplacements: remplacementsDe(consommations),
    };
  }

  // ===========================================================================================
  // 2. Mode ancré (cause) : cas, équipements, remèdes
  // ===========================================================================================

  /**
   * Couche calculée d'un mode ancré sur une cause (§20.3) : { cause: { code, libelle }, cas, equipements:
   * [{ equipementId, repere, cas }] (cas décroissant puis repère), remedes: [{ code, libelle, fois }]
   * (fois décroissant puis code ; un OT sans remède n'est pas compté) } ; null sans code.
   */
  function pageMode(causeCode) {
    const code = texte(causeCode);
    if (!code) return null;
    const cas = Donnees.lignes('ordres_travail')
      .filter((ot) => estCorrectif(ot) && estCloture(ot) && texte(ot.cause_code) === code);
    const parEquipement = new Map();
    const parRemede = new Map();
    cas.forEach((ot) => {
      const equipementId = texte(ot.equipement_id);
      parEquipement.set(equipementId, (parEquipement.get(equipementId) || 0) + 1);
      const remede = texte(ot.remede_code);
      if (remede) parRemede.set(remede, (parRemede.get(remede) || 0) + 1);
    });
    const equipements = [];
    parEquipement.forEach((nombre, equipementId) => {
      const ligne = equipement(equipementId);
      if (ligne) equipements.push({ equipementId, repere: texte(ligne.repere), cas: nombre });
    });
    const remedes = Array.from(parRemede, ([remede, fois]) => ({ code: remede, libelle: libelleCode('remède', remede), fois }));
    return {
      cause: { code, libelle: libelleCode('cause', code) },
      cas: cas.length,
      equipements: equipements.sort((a, b) => b.cas - a.cas || parRepere(a, b)),
      remedes: remedes.sort((a, b) => b.fois - a.fois || comparer(a.code, b.code)),
    };
  }

  // ===========================================================================================
  // 3. Savoir-faire : en-tête posé par Prévo (jamais de texte d'IA)
  // ===========================================================================================

  /** Consignation de la fiche, texte et document tels quels ; null seulement si les deux sont vides. */
  function consignationDe(ligne) {
    const consignation = brut(ligne.consignation);
    const document = brut(ligne.document);
    return texte(consignation) || texte(document) ? { texte: consignation, document } : null;
  }

  /**
   * En-tête d'un savoir-faire : { consignation, equipements: [{ equipementId, repere }], phrase }.
   * Rattaché à un équipement (equipement_id, ou page rattachée qui en a un) : sa consignation telle quelle
   * et cet équipement ; à un article (article_id, ou page de composant rattachée qui en a un) : pas de
   * consignation, les équipements où l'article est monté ; sinon : ni l'une ni les autres.
   */
  function enteteSavoirFaire(ligne) {
    let cible = ligne;
    if (!texte(ligne.equipement_id) && !texte(ligne.article_id) && texte(ligne.rattache_a)) {
      cible = Donnees.trouver('wiki_pages', texte(ligne.rattache_a)) || {};
    }
    const equipementId = texte(cible.equipement_id);
    const fiche = equipement(equipementId);
    if (fiche) {
      return {
        consignation: consignationDe(fiche),
        equipements: [{ equipementId, repere: texte(fiche.repere) }],
        phrase: PHRASE_SAVOIR_FAIRE,
      };
    }
    const articleId = texte(cible.article_id);
    const equipements = articleId && Donnees.trouver('articles', articleId)
      ? montageDe(articleId, consommationsDe(articleId)).map((monte) => ({ equipementId: monte.equipementId, repere: monte.repere }))
      : [];
    return { consignation: null, equipements, phrase: PHRASE_SAVOIR_FAIRE };
  }

  // ===========================================================================================
  // 4. Pages, retours, catalogue
  // ===========================================================================================

  /** Identifiants d'un champ « liens » (« ; »), sans vide ni doublon, dans l'ordre. */
  function liensDe(ligne) {
    return Array.from(new Set(brut(ligne.liens).split(';').map(texte).filter(Boolean)));
  }

  /** Entrée canonique d'une ligne active : { id, type, titre, ancree }. */
  function entreeDe(ligne) {
    const type = texte(ligne.type);
    if (type === 'équipement') {
      const fiche = equipement(texte(ligne.equipement_id));
      if (fiche) return { id: texte(fiche.id), type, titre: titreEquipement(fiche), ancree: true };
    }
    if (type === 'composant' && texte(ligne.article_id)) {
      const article = Donnees.trouver('articles', texte(ligne.article_id));
      if (article) return { id: texte(article.id), type, titre: titreArticle(article), ancree: true };
    }
    return { id: texte(ligne.id), type, titre: texte(ligne.titre), ancree: false };
  }

  function pagesActives() {
    return Donnees.lignes('wiki_pages').filter(estActive);
  }

  /** Pages actives (autres qu'elle-même) dont les liens désignent la page, par son id canonique ou son WP-… ; par titre. */
  function retoursDe(actives, id, pageId) {
    const cibles = new Set([id, pageId].filter(Boolean));
    const retours = new Map();
    actives.forEach((ligne) => {
      if (!liensDe(ligne).some((lien) => cibles.has(lien))) return;
      const entree = entreeDe(ligne);
      if (entree.id === id || retours.has(entree.id)) return;
      retours.set(entree.id, { id: entree.id, titre: entree.titre, type: entree.type });
    });
    return Array.from(retours.values()).sort((a, b) => comparer(a.titre, b.titre) || comparer(a.id, b.id));
  }

  /**
   * Assemble une page : la base { id, type, titre, calcul, entete } et le texte validé de sa ligne de
   * wiki_pages (vide sans ligne).
   */
  function assembler(base, ligne, actives, options) {
    const pageId = ligne ? texte(ligne.id) : '';
    const page = Object.assign(base, {
      texte: ligne ? brut(ligne.texte) : '',
      origine: ligne ? texte(ligne.origine) : '',
      modele: ligne ? texte(ligne.modele) : '',
      validePar: ligne ? texte(ligne.valide_par) : '',
      valideLe: ligne ? texte(ligne.valide_le) : '',
      liens: ligne ? liensDe(ligne) : [],
      retours: retoursDe(actives, base.id, pageId),
      contradictions: [],
      enAttente: [],
      pageId,                                  // WP-… de la ligne du texte ('' sans texte validé)
    });
    // Crochets : wiki-journal.js (§20.7, chargé après ce fichier) fournit les contradictions ouvertes et
    // les propositions « à valider » qui touchent la page (responsable seulement) par
    // Wiki.contradictionsDe(page, options) et Wiki.enAttenteDe(page, options), page = { id, pageId, type,
    // titre }. Tant qu'ils n'existent pas, les deux listes restent vides.
    const reperes = { id: page.id, pageId, type: page.type, titre: page.titre };
    if (typeof Wiki.contradictionsDe === 'function') page.contradictions = Wiki.contradictionsDe(reperes, options) || [];
    if (typeof Wiki.enAttenteDe === 'function') page.enAttente = Wiki.enAttenteDe(reperes, options) || [];
    return page;
  }

  /** Page d'un équipement ou d'un article (identifiant canonique) avec le texte de sa ligne ancrée active. */
  function pageAncree(type, id, actives, options) {
    const ligne = actives.find((candidate) => {
      const entree = entreeDe(candidate);
      return entree.ancree && entree.type === type && entree.id === id;
    });
    if (type === 'équipement') {
      const calcul = Wiki.pageEquipement(id, options);
      if (!calcul) return null;
      const titre = [calcul.equipement.repere, calcul.equipement.designation].filter(Boolean).join(' — ');
      return assembler({ id, type, titre, calcul, entete: null }, ligne, actives, options);
    }
    const calcul = pageComposant(id);
    if (!calcul) return null;
    return assembler({ id, type, titre: titreArticle(Donnees.trouver('articles', id)), calcul, entete: null },
      ligne, actives, options);
  }

  /**
   * Page d'un identifiant (§20.3) : EQ-… (équipement), ART-… (article) ou WP-… (ligne active de
   * wiki_pages ; une page ancrée rend la page de son équipement ou de son article). → { id, type, titre,
   * calcul, entete, texte, origine, modele, validePar, valideLe, liens, retours, contradictions, enAttente,
   * pageId } ou null (identifiant inconnu, page archivée). options : { maintenant, profil }.
   */
  function page(id, options) {
    const identifiant = texte(id);
    if (!identifiant) return null;
    const actives = pagesActives();
    if (equipement(identifiant)) return pageAncree('équipement', identifiant, actives, options);
    if (Donnees.trouver('articles', identifiant)) return pageAncree('composant', identifiant, actives, options);
    const ligne = Donnees.trouver('wiki_pages', identifiant);
    if (!ligne || !estActive(ligne)) return null;
    const entree = entreeDe(ligne);
    if (entree.ancree) return pageAncree(entree.type, entree.id, actives, options);
    const causeCode = texte(ligne.cause_code);
    const calcul = entree.type === 'mode' && causeCode ? pageMode(causeCode) : null;
    const entete = entree.type === 'savoir-faire' ? enteteSavoirFaire(ligne) : null;
    return assembler({ id: entree.id, type: entree.type, titre: entree.titre, calcul, entete }, ligne, actives, options);
  }

  /**
   * Catalogue (§20.3) : [{ id, titre, type }] — un équipement par EQ-…, un article par ART-…, puis les
   * pages actives non ancrées (modes, savoir-faire, composants libres) ; celles qui ont un texte d'abord,
   * puis par titre et identifiant ; catalogueMax au plus.
   */
  function catalogue() {
    const entrees = new Map();
    const avecTexte = new Set();
    Donnees.lignes('equipements').forEach((ligne) => {
      entrees.set(texte(ligne.id), { id: texte(ligne.id), titre: titreEquipement(ligne), type: 'équipement' });
    });
    Donnees.lignes('articles').forEach((ligne) => {
      entrees.set(texte(ligne.id), { id: texte(ligne.id), titre: titreArticle(ligne), type: 'composant' });
    });
    pagesActives().forEach((ligne) => {
      const entree = entreeDe(ligne);
      if (!entree.ancree) entrees.set(entree.id, { id: entree.id, titre: entree.titre, type: entree.type });
      if (texte(ligne.texte)) avecTexte.add(entree.id);
    });
    return Array.from(entrees.values())
      .sort((a, b) => Number(avecTexte.has(b.id)) - Number(avecTexte.has(a.id))
        || comparer(a.titre, b.titre) || comparer(a.id, b.id))
      .slice(0, Wiki.SEUILS.catalogueMax);
  }

  return { page, pageComposant, pageMode, catalogue, PHRASE_SAVOIR_FAIRE };
})());
