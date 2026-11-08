'use strict';
// Wiki (2/8) — couches calculées du composant et du mode, pages et catalogue (lot 6 refondu,
// ARCHITECTURE.md §20.3 ; tâche T112) ; pages Machine et Article de l'encyclopédie, rattachement d'un savoir-faire,
// listes des machines et des savoir-faire (refonte 2, §20.12 ; tâche T135, section 5, sur le socle de
// wiki-entites.js). Tout est relu dans Donnees.lignes à chaque appel : rien n'est écrit, rien n'est gardé entre deux
// appels, aucun appel réseau, aucune IA.
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
// - les tris départagent par l'ordre des caractères (reproductible par tests/calcul_wiki.py) ;
// - sous-page (§20.4, T131) : ligne active dont rattache_a désigne une ligne de même type (sa mère, même archivée) ;
//   pas de couche calculée ; ses sous-pages, la mère les liste par titre dans l'ordre alphabétique français, comme
//   l'index du wiki (ce n'est pas un calcul de tests/calcul_wiki.py).

Object.defineProperties(Wiki, Object.getOwnPropertyDescriptors((() => {   // garde les accesseurs get (Object.assign les figerait)

  const STATUTS_CLOTURES = ['Clôturé techniquement', 'Clôturé administrativement'];
  const phraseSavoirFaire = () => I18n.t('wiki.phrase_savoir_faire.savoir_faire_remplace_pas');
  const phraseSousPage = () => I18n.t('wiki.phrase_sous_page.page_remplace_pas_consignation');
  const MILLISECONDES_PAR_JOUR = 86400000;
  const ORDRE_FRANCAIS = new Intl.Collator('fr', { numeric: true, sensitivity: 'base' });

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
   * Machines liées par le texte d'une ligne (champ `liens` : un EQ-…, ou la ligne du texte d'une machine), dans l'ordre
   * des liens, sans doublon → [{ equipementId, repere }] (machines existantes seulement).
   */
  function machinesLiees(ligne) {
    const ids = liensDe(ligne).map((lien) => {
      const page = equipement(lien) ? null : Donnees.trouver('wiki_pages', lien);
      return page && texte(page.type) === 'équipement' ? texte(page.equipement_id) : lien;
    }).filter((id) => equipement(id));
    return Array.from(new Set(ids), (id) => ({ equipementId: id, repere: texte(equipement(id).repere) }));
  }

  /**
   * En-tête d'un savoir-faire : { consignation, equipements: [{ equipementId, repere }], phrase }.
   * Rattaché à un équipement (equipement_id, ou page rattachée qui en a un) et sans autre machine liée dans son texte :
   * sa consignation telle quelle et cet équipement ; commun à plusieurs machines (D116 : rattachement et machines liées)
   * : pas de consignation, ces machines (celle du rattachement d'abord) ; rattaché à un article (article_id, ou page de
   * composant rattachée qui en a un) : pas de consignation, les équipements où l'article est monté puis les machines
   * liées ; sinon : les machines liées.
   */
  function enteteSavoirFaire(ligne) {
    let cible = ligne;
    if (!texte(ligne.equipement_id) && !texte(ligne.article_id) && texte(ligne.rattache_a)) {
      cible = Donnees.trouver('wiki_pages', texte(ligne.rattache_a)) || {};
    }
    const equipementId = texte(cible.equipement_id);
    const fiche = equipement(equipementId);
    const articleId = texte(cible.article_id);
    const premieres = fiche ? [{ equipementId, repere: texte(fiche.repere) }] : (articleId && Donnees.trouver('articles', articleId)
      ? montageDe(articleId, consommationsDe(articleId)).map((monte) => ({ equipementId: monte.equipementId, repere: monte.repere }))
      : []);
    const equipements = premieres.concat(machinesLiees(ligne)
      .filter((liee) => !premieres.some((machine) => machine.equipementId === liee.equipementId)));
    if (fiche && equipements.length === 1) {
      return { consignation: consignationDe(fiche), equipements, phrase: phraseSavoirFaire() };
    }
    return { consignation: null, equipements, phrase: phraseSavoirFaire() };
  }

  // ===========================================================================================
  // 3 bis. Sous-pages (§20.4) : mère, en-tête repris de la mère, liste des sous-pages
  // ===========================================================================================

  /** Ligne de la mère d'une ligne de wiki_pages si c'en est une sous-page (rattache_a de même type), sinon null. */
  function ligneMere(ligne) {
    const mere = texte(ligne.rattache_a) ? Donnees.trouver('wiki_pages', texte(ligne.rattache_a)) : null;
    return mere && texte(mere.type) === texte(ligne.type) ? mere : null;
  }

  /**
   * En-tête d'une sous-page, posé par Prévo comme celui d'un savoir-faire (CS98, jamais de texte d'IA) : sous-page
   * d'équipement → la consignation de l'équipement de sa mère, telle quelle, et « Cette page ne remplace pas la
   * consignation de l'équipement » ; sous-page de savoir-faire → l'en-tête de sa mère ; sinon null.
   */
  function enteteSousPage(ligne, mere) {
    if (texte(ligne.type) === 'savoir-faire') return enteteSavoirFaire(mere);
    if (texte(ligne.type) !== 'équipement') return null;
    const equipementId = texte(mere.equipement_id);
    const fiche = equipement(equipementId);
    return { consignation: fiche ? consignationDe(fiche) : null,
      equipements: fiche ? [{ equipementId, repere: texte(fiche.repere) }] : [], phrase: phraseSousPage() };
  }

  /** Sous-pages actives d'une ligne : [{ id, titre }], par titre (ordre alphabétique français) puis identifiant. */
  function sousPagesDe(actives, ligne) {
    const id = texte(ligne.id);
    return actives.filter((autre) => texte(autre.id) !== id && texte(autre.rattache_a) === id && texte(autre.type) === texte(ligne.type))
      .map((autre) => ({ id: texte(autre.id), titre: texte(autre.titre) }))
      .sort((a, b) => ORDRE_FRANCAIS.compare(a.titre, b.titre) || comparer(a.id, b.id));
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
   * wiki_pages (vide sans ligne) ; `mere` (sous-page : { id, titre } canoniques de sa mère, sinon null) et
   * `sousPages` (page mère : ses sous-pages actives, sinon []).
   */
  function assembler(base, ligne, actives, options, mere) {
    const pageId = ligne ? texte(ligne.id) : '';
    const entreeMere = mere ? entreeDe(mere) : null;
    const page = Object.assign(base, {
      mere: entreeMere ? { id: entreeMere.id, titre: entreeMere.titre } : null,
      sousPages: ligne ? sousPagesDe(actives, ligne) : [],
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
   * wiki_pages ; une page ancrée rend la page de son équipement ou de son article ; une sous-page n'a pas de
   * couche calculée). → { id, type, titre, calcul, entete, mere, sousPages, texte, origine, modele, validePar,
   * valideLe, liens, retours, contradictions, enAttente, pageId } ou null (identifiant inconnu, page archivée).
   * options : { maintenant, profil }.
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
    const mere = ligneMere(ligne);
    if (mere) {
      return assembler({ id: entree.id, type: entree.type, titre: entree.titre, calcul: null, entete: enteteSousPage(ligne, mere) },
        ligne, actives, options, mere);
    }
    const causeCode = texte(ligne.cause_code);
    const calcul = entree.type === 'mode' && causeCode ? pageMode(causeCode) : null;
    const entete = entree.type === 'savoir-faire' ? enteteSavoirFaire(ligne) : null;
    return assembler({ id: entree.id, type: entree.type, titre: entree.titre, calcul, entete }, ligne, actives, options);
  }

  /**
   * Catalogue (§20.3) : [{ id, titre, type }] — un équipement par EQ-…, un article par ART-…, puis les
   * pages actives non ancrées (modes, savoir-faire, composants libres, sous-pages) ; celles qui ont un texte d'abord,
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

  // ===========================================================================================
  // 5. Encyclopédie (refonte 2, §20.12 ; T135) : pages Machine et Article, rattachement d'un savoir-faire, listes des
  //    machines et des savoir-faire. Le socle (index `ctx` d'un appel, références aux entités, interventions, pièces,
  //    textes, stock dans le temps, assemblage) est dans wiki-entites.js, chargé après ce fichier, qui l'ajoute à
  //    Wiki.interne : ces fonctions l'y lisent à l'appel ; Wiki.entite et Wiki.listeEntites les appellent par là.
  // ===========================================================================================

  /**
   * Rattachement d'un savoir-faire, règle de son en-tête (enteteSavoirFaire ; une sous-page : celui de sa mère) : sa
   * machine (equipement_id de sa ligne ou de la page à laquelle il est rattaché), sinon son article → { type : 'machine'
   * ou 'article', id, titre, lien } ; null sinon.
   */
  function rattachementDe(ligne) {
    const socle = Wiki.interne;
    const source = ligneMere(ligne) || ligne;
    let cible = source;
    if (!texte(source.equipement_id) && !texte(source.article_id) && texte(source.rattache_a)) {
      cible = Donnees.trouver('wiki_pages', texte(source.rattache_a)) || {};
    }
    const machine = socle.refMachine(texte(cible.equipement_id));
    if (machine) return { type: 'machine', id: machine.equipementId, titre: machine.titre, lien: machine.lien };
    const article = socle.refArticle(texte(cible.article_id));
    return article ? { type: 'article', id: article.articleId, titre: article.titre, lien: article.lien } : null;
  }

  /**
   * Savoir-faire actifs d'une machine ou d'un article, sans les sous-pages (que leur mère liste) ; par titre : ceux qui y
   * sont rattachés et ceux dont le champ `liens` (le leur, ou celui de l'une de leurs sous-pages) désigne l'entité ou la
   * ligne de son texte (D116), une fois chacun.
   */
  function savoirFaireDe(ctx, type, id) {
    const texteAncre = type === 'machine' ? Wiki.interne.ligneAncree(ctx, 'équipement', 'equipement_id', id)
      : Wiki.interne.ligneAncree(ctx, 'composant', 'article_id', id);
    const cibles = [id, texteAncre ? texte(texteAncre.id) : ''].filter(Boolean);
    const lies = new Set(ctx.pagesActives.filter((ligne) => texte(ligne.type) === 'savoir-faire'
      && liensDe(ligne).some((lien) => cibles.includes(lien))).map((ligne) => texte((ligneMere(ligne) || ligne).id)));
    return ctx.pagesActives.filter((ligne) => texte(ligne.type) === 'savoir-faire' && !ligneMere(ligne))
      .filter((ligne) => {
        const rattachement = rattachementDe(ligne);
        return (rattachement !== null && rattachement.type === type && rattachement.id === id) || lies.has(texte(ligne.id));
      })
      .map((ligne) => ({ id: texte(ligne.id), titre: texte(ligne.titre), lien: texte(ligne.id) }))
      .sort(Wiki.interne.parTitre('id'));
  }

  /** Lignes de article_equipement du côté `champ` = id (la première d'un couple fait foi) : Map(autre id → quantité). */
  function nomenclature(champ, id, autre, existe) {
    const montes = new Map();
    Donnees.lignes('article_equipement').forEach((ligne) => {
      const cle = texte(ligne[autre]);
      if (texte(ligne[champ]) === id && cle && !montes.has(cle) && existe(cle)) montes.set(cle, Donnees.nombre(ligne.quantite));
    });
    return montes;
  }

  /** Gammes et contrôles : prochaine échéance croissante (sans date en dernier), puis identifiant. */
  function parProchaine(a, b) {
    return Number(!a.prochaine) - Number(!b.prochaine) || comparer(a.prochaine, b.prochaine) || comparer(a.id, b.id);
  }

  function nomFournisseur(id) {
    const fournisseur = texte(id) ? Donnees.trouver('fournisseurs', texte(id)) : null;
    return fournisseur ? texte(fournisseur.nom) || texte(fournisseur.id) : texte(id);
  }

  /** Page Machine (§20.12) : fiche, consignation, sous-ensembles, pannes, interventions, articles, savoir-faire, préventif. */
  function entiteMachine(ctx, fiche) {
    const socle = Wiki.interne;
    const { fait, parTitre } = socle;
    const id = texte(fiche.id);
    const ordres = ctx.ordresParEquipement.get(id) || [];
    const parent = texte(fiche.parent_id);
    const mere = socle.refMachine(parent);
    const titre = titreEquipement(fiche);
    const ligne = socle.ligneAncree(ctx, 'équipement', 'equipement_id', id);
    return socle.assembler(ctx, {
      id, type: 'machine', titre,
      faits: [
        fait(I18n.t('commun.champ.repere'), texte(fiche.repere)), fait(I18n.t('wiki.fait.lieu'), socle.lieuDe(ctx, fiche.localisation_id)),
        fait(I18n.t('wiki.fait.marque_modele'), [texte(fiche.marque), texte(fiche.modele)].filter(Boolean).join(' ')),
        fait(I18n.t('wiki.fait.numero_serie'), texte(fiche.num_serie)), fait(I18n.t('wiki.fait.mise_en_service'), jour(fiche.date_mes)),
        fait(I18n.t('commun.champ.criticite'), Schema.libelleValeur('equipements', 'criticite', texte(fiche.criticite))),
        fait(I18n.t('wiki.fait.etat'), Schema.libelleValeur('equipements', 'statut', texte(fiche.statut))),
        fait(I18n.t('wiki.fait.habilitation_requise'), texte(fiche.habilitation_requise)),
      ].concat(parent ? [fait(I18n.t('wiki.fait.fait_partie_de'), mere ? mere.titre : parent, mere && mere.lien)] : [],
        [fait(I18n.t('wiki.fait.interventions'), ordres.length)]),
      sections: {
        consignation: consignationDe(fiche),
        sousEnsembles: Donnees.lignes('equipements').filter((autre) => texte(autre.parent_id) === id && texte(autre.id) !== id)
          .map((autre) => socle.refMachine(texte(autre.id))).sort(parTitre('equipementId')),
        pannes: socle.pannesDe(ctx, ordres),
        interventions: socle.interventions(ctx, ordres),
        articlesMontes: Array.from(nomenclature('equipement_id', id, 'article_id', socle.refArticle),
          ([articleId, quantite]) => Object.assign(socle.refArticle(articleId), { quantite })).sort(parTitre('articleId')),
        articlesConsommes: socle.piecesDesOrdres(ctx, ordres, true),
        savoirFaire: savoirFaireDe(ctx, 'machine', id),
        gammes: Donnees.lignes('gammes').filter((gamme) => texte(gamme.equipement_id) === id && texte(gamme.actif) !== '0')
          .map((gamme) => ({ id: texte(gamme.id), libelle: texte(gamme.libelle), declencheur: texte(gamme.declencheur),
            periodiciteJours: Donnees.nombre(gamme.periodicite_jours), prochaine: jour(gamme.prochaine_echeance) }))
          .sort(parProchaine),
        controles: Donnees.lignes('controles_reglementaires').filter((controle) => texte(controle.equipement_id) === id)
          .map((controle) => ({ id: texte(controle.id), nature: texte(controle.nature), organisme: texte(controle.organisme),
            derniere: jour(controle.derniere_date), prochaine: jour(controle.prochaine_date) }))
          .sort(parProchaine),
      },
    }, socle.textesDe(ligne, 'équipement'), { id, pageId: ligne ? texte(ligne.id) : '', type: 'équipement', titre });
  }

  /** Page Article (§20.12) : fiche (prix au technicien et au responsable, D114), stock dans le temps, montage, usages. */
  function entiteArticle(ctx, article) {
    const socle = Wiki.interne;
    const { fait, parTitre } = socle;
    const id = texte(article.id);
    const prix = ctx.profil !== 'demandeur';
    const temps = socle.stockDansLeTemps(ctx, id);
    const titre = titreArticle(article);
    const ligne = socle.ligneAncree(ctx, 'composant', 'article_id', id);
    const consommeSur = new Map();                       // machine → { nombreOt, quantite } (OT clôturés, T112)
    (ctx.servi.get(id) || []).forEach((otId) => {
      const ot = Donnees.trouver('ordres_travail', otId);
      const machine = ot && estCloture(ot) ? socle.refMachine(texte(ot.equipement_id)) : null;
      if (!machine) return;
      const entree = consommeSur.get(machine.equipementId) || Object.assign(machine, { nombreOt: 0, quantite: 0 });
      entree.nombreOt += 1;
      entree.quantite = socle.arrondi(entree.quantite + ctx.pieces.get(otId).get(id));
      consommeSur.set(machine.equipementId, entree);
    });
    const nombre = (champ) => Donnees.nombre(article[champ]);
    return socle.assembler(ctx, {
      id, type: 'article', titre,
      faits: [
        fait(I18n.t('commun.champ.reference'), texte(article.reference)), fait(I18n.t('wiki.fait.fabricant'), texte(article.fabricant)),
        fait(I18n.t('wiki.fait.reference_fabricant'), texte(article.ref_fabricant)), fait(I18n.t('wiki.fait.emplacement'), texte(article.emplacement)),
        fait(I18n.t('wiki.fait.stock'), temps.stock), fait(I18n.t('wiki.fait.unite'), texte(article.unite)), fait(I18n.t('wiki.fait.etat_stock'), socle.etatDuStock(article, temps.stock)),
        fait(I18n.t('wiki.fait.stock_securite'), nombre('stock_securite')), fait(I18n.t('wiki.fait.point_commande'), nombre('point_commande')),
        fait(I18n.t('wiki.fait.quantite_commande'), nombre('qte_commande')), fait(I18n.t('wiki.fait.delai_jours'), nombre('delai_jours')),
        fait(I18n.t('wiki.fait.fournisseur'), nomFournisseur(article.fournisseur_id)),
      ].concat(prix ? [fait(I18n.t('commun.champ.prix_unitaire'), nombre('prix_unitaire'))] : [], [fait(I18n.t('wiki.fait.critique'), texte(article.critique) === '1')]),
      sections: {
        commandes: Donnees.lignes('achats').filter((achat) => texte(achat.article_id) === id)
          .sort((a, b) => comparer(texte(a.date), texte(b.date)) || comparer(texte(a.id), texte(b.id)))
          .map((achat) => Object.assign({ id: texte(achat.id), date: jour(achat.date), quantite: Donnees.nombre(achat.quantite),
            fournisseur: nomFournisseur(achat.fournisseur_id), statut: texte(achat.statut), reception: jour(achat.date_reception) },
          prix ? { prixUnitaire: Donnees.nombre(achat.prix_unitaire) } : {})),
        sorties: temps.sorties,
        ruptures: temps.ruptures,
        montee: Array.from(nomenclature('article_id', id, 'equipement_id', socle.refMachine),
          ([equipementId, quantite]) => Object.assign(socle.refMachine(equipementId), { quantite })).sort(parTitre('equipementId')),
        consommeSur: Array.from(consommeSur.values()).sort((a, b) => b.nombreOt - a.nombreOt || parTitre('equipementId')(a, b)),
        interventions: socle.interventions(ctx, socle.ordresDe(ctx.servi.get(id))),
        savoirFaire: savoirFaireDe(ctx, 'article', id),
      },
    }, socle.textesDe(ligne, 'composant'), { id, pageId: ligne ? texte(ligne.id) : '', type: 'composant', titre });
  }

  /** Vrai si la chaîne des parents d'une machine revient à elle (elle reste alors en tête de la liste des machines). */
  function dansUnCycle(fiche) {
    const vues = new Set();
    for (let courante = fiche; courante && texte(courante.parent_id) && !vues.has(texte(courante.id));
      courante = equipement(texte(courante.parent_id))) {
      vues.add(texte(courante.id));
      if (texte(courante.parent_id) === texte(fiche.id)) return true;
    }
    return false;
  }

  /**
   * Liste des machines : [{ lieu, machines: [{ equipementId, titre, lien, lieu, marqueModele, interventions, pannes,
   * sousEnsembles }] }], par lieu (vide en dernier) puis titre ; un sous-ensemble sous sa machine (parent connu, sans cycle).
   */
  function listeMachines(ctx) {
    const socle = Wiki.interne;
    const enfants = new Map();
    const racines = [];
    Donnees.lignes('equipements').forEach((fiche) => {
      const parent = texte(fiche.parent_id);
      if (!parent || !equipement(parent) || dansUnCycle(fiche)) racines.push(fiche);
      else enfants.set(parent, (enfants.get(parent) || []).concat([fiche]));
    });
    const noeud = (fiche) => {
      const id = texte(fiche.id);
      const ordres = ctx.ordresParEquipement.get(id) || [];
      return Object.assign(socle.refMachine(id), { lieu: socle.lieuDe(ctx, fiche.localisation_id),
        marqueModele: [texte(fiche.marque), texte(fiche.modele)].filter(Boolean).join(' '), interventions: ordres.length,
        pannes: socle.pannesDe(ctx, ordres), sousEnsembles: (enfants.get(id) || []).map(noeud).sort(socle.parTitre('equipementId')) });
    };
    const groupes = new Map();
    racines.map(noeud).sort(socle.parTitre('equipementId'))
      .forEach((machine) => groupes.set(machine.lieu, (groupes.get(machine.lieu) || []).concat([machine])));
    return Array.from(groupes, ([lieu, machines]) => ({ lieu, machines }))
      .sort((a, b) => Number(!a.lieu) - Number(!b.lieu) || comparer(a.lieu, b.lieu));
  }

  /** Savoir-faire actifs, sous-pages comprises : [{ id, titre, rattachement, mere, lien }], par titre. */
  function listeSavoirFaire(ctx) {
    return ctx.pagesActives.filter((ligne) => texte(ligne.type) === 'savoir-faire').map((ligne) => {
      const mere = ligneMere(ligne);
      return { id: texte(ligne.id), titre: texte(ligne.titre), rattachement: rattachementDe(ligne),
        mere: mere ? { id: texte(mere.id), titre: texte(mere.titre) } : null, lien: texte(ligne.id) };
    }).sort(Wiki.interne.parTitre('id'));
  }

  return {
    page, pageComposant, pageMode, catalogue,
    get PHRASE_SAVOIR_FAIRE() { return phraseSavoirFaire(); },
    get PHRASE_SOUS_PAGE() { return phraseSousPage(); },
    // Usage interne du wiki (pas une API) : complété par wiki-entites.js (socle de l'encyclopédie).
    interne: { entiteMachine, entiteArticle, rattachementDe, listeMachines, listeSavoirFaire, retoursDe },
  };
})()));
