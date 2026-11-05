'use strict';
// Wiki (2 bis) — l'encyclopédie de l'atelier (refonte 2, ARCHITECTURE.md §20.12 ; D113, D114 ; tâche T135) : profil et
// index d'un appel, références aux entités, ordre des interventions, pièces, textes rédigés et références, stock dans le
// temps d'un article, pages Panne, Technicien, Intervention et Savoir-faire, listes et accueil. Les pages Machine et
// Article, le rattachement d'un savoir-faire et les listes des machines et des savoir-faire sont dans wiki-calculs.js
// (chargé avant, lu par Wiki.interne), qui y lit à l'appel le socle de ce fichier. Tout est relu dans Donnees.lignes à
// chaque appel (index construits une fois par appel) : rien n'est écrit ni gardé, aucun appel réseau, aucune IA.
//
// API (précision au contrat : Wiki.page garde sa forme tant que les écrans actuels s'en servent) :
//  - Wiki.entite(id, { profil, maintenant }) → { id, type, titre, faits: [{ libelle, valeur, lien }], sections, textes,
//    aTrancher, enAttente, references, retours, liens } ou null (identifiant inconnu, page que le profil ne voit pas) ; type :
//    machine, panne, article, technicien, intervention, savoir-faire ; textes null pour une page sans texte rédigé ;
//  - Wiki.listeEntites(type, { profil, maintenant }) (null : type inconnu ou que le profil ne voit pas) ;
//  - Wiki.accueilEncyclopedie({ profil, maintenant }) ; Wiki.ordreInterventions(ids) ; Wiki.references(textes,
//    aTrancher) ; Wiki.idPanne(code).
//
// Définitions (précisions au contrat §20.12) :
//  - profil : options.profil, sinon celui d'App, sinon « demandeur » (le plus restreint) ; `liens` d'une entité dit
//    quels types de pages il ouvre ; une référence à une entité porte `lien` : l'identifiant de sa page si le profil
//    l'ouvre, null sinon (le demandeur voit le nom d'un technicien et le numéro d'un OT, sans lien) ; le prix d'un
//    article ou d'une commande n'est rendu qu'au technicien et au responsable, le taux horaire qu'au responsable ;
//  - OT ouvert : Créé, Préparé, Planifié, En cours, En attente ; date d'un OT : fin, sinon début, sinon date prévue,
//    sinon création ; ordre des interventions (D113) : les ouverts (« En cours » d'abord, puis date prévue croissante,
//    sans date prévue en dernier, puis identifiant), puis les autres du plus récent au plus ancien (date, puis
//    identifiant décroissant) ;
//  - cas d'une panne : OT correctif clôturé de ce code symptôme (comme les pannes d'une machine, T96) ; une panne a sa
//    page dès un cas ; ses interventions : tous les OT de ce code ; identifiant « PANNE- » + encodeURIComponent(code)
//    (« PANNE-S01 » ; sûr dans une adresse, quel que soit le code) ;
//  - pièces nettes d'un OT : par article, sorties − retours liés à l'OT, gardées si positives ; un article a servi à
//    un OT où ses pièces nettes sont positives (tout statut), il y est consommé si l'OT est clôturé (T112) ;
//  - stock dans le temps : mouvements par date puis identifiant (règle de Donnees.stockArticle : un inventaire fixe la
//    quantité, une entrée ou un retour ajoute, une sortie retire) ; une rupture commence au mouvement qui laisse le
//    stock à 0 ou moins, finit à celui qui le remonte (fin '' : elle dure encore) ; état : « rupture » (stock ≤ 0),
//    « sous le seuil » (stock ≤ point de commande renseigné), « en stock » ;
//  - habilitations : les règles du module Équipe, les mêmes que son écran et que l'alerte de l'accueil — celles qui
//    comptent (une par intitulé : la plus lointaine ; un renouvellement laisse l'ancienne ligne pour l'historique) et
//    leur état (« échue », « à renouveler » sous 60 jours (RG8), « pas encore valable », « valide ») ; l'accueil ne
//    compte que les techniciens actifs ;
//  - une référence cassée (équipement, article, technicien inconnu) n'entre dans aucune liste ; les tris départagent
//    par l'ordre des caractères (reproductible par tests/calcul_wiki.py) ;
//  - références : les OT cités dans l'ordre d'apparition sur la page (T137) — « À trancher », en tête, puis les textes —,
//    avec leurs détails, sans numéro : la page les numérote elle-même, avec ceux de ses sections (articles consommés et
//    changés, D118 : wiki-page-ecrans.js, la seule règle de numérotation) ;
//  - retours (« Pages qui renvoient ici », CS103, T137) d'une machine, d'un article, d'un savoir-faire ou d'une panne :
//    la règle de Wiki.page (retoursDe de wiki-calculs.js : pages actives dont le champ liens désigne l'identifiant de
//    l'entité ou le WP-… de son texte, la page elle-même exclue, par titre puis identifiant), réduite aux pages qui
//    s'affichent (texte d'une machine ou d'un article qui existe, savoir-faire) → [{ id, type, titre, lien }] ; une
//    proposition « à valider » n'est pas dans wiki_pages : elle n'y entre jamais ; [] pour les autres types ;
//    intervention : motifAttente et motifAnnulation de l'OT ('' sans motif).

Object.assign(Wiki, (() => {

  const STATUTS_CLOTURES = ['Clôturé techniquement', 'Clôturé administrativement'];
  const STATUTS_OUVERTS = ['Créé', 'Préparé', 'Planifié', 'En cours', 'En attente'];
  const PROFILS = ['demandeur', 'technicien', 'responsable'];
  const PREFIXE_PANNE = 'PANNE-';
  const MACHINES_ACCUEIL = 3;              // machines qui ont le plus d'interventions, dans leur brique de l'accueil
  const PANNES_ACCUEIL = 6;                // pannes les plus fréquentes de l'accueil (maquette validée ; relecture de T136)

  const texte = (valeur) => (valeur === null || valeur === undefined ? '' : String(valeur).trim());
  const comparer = (a, b) => (a < b ? -1 : (a > b ? 1 : 0));          // ordre des caractères, comme le calcul Python
  const parTitre = (cle) => (a, b) => comparer(a.titre, b.titre) || comparer(a[cle], b[cle]);
  const jour = (valeur) => texte(valeur).slice(0, 10);                 // 'AAAA-MM-JJ…' → 'AAAA-MM-JJ'
  const arrondi = (valeur) => Math.round(valeur * 1e6) / 1e6;          // comme Donnees.stockArticle
  const fait = (libelle, valeur, lien) => ({ libelle, valeur, lien: lien || null });
  const estCloture = (ot) => STATUTS_CLOTURES.includes(texte(ot.statut));
  const estOuvert = (ot) => STATUTS_OUVERTS.includes(texte(ot.statut));
  const estUnCas = (ot) => /^correctif/.test(texte(ot.type)) && estCloture(ot) && texte(ot.symptome_code) !== '';
  const dateDeLOt = (ot) => texte(ot.date_fin) || texte(ot.date_debut) || texte(ot.date_prevue) || texte(ot.date_creation);

  function ajouter(carte, cle, valeur) {
    if (!carte.has(cle)) carte.set(cle, []);
    carte.get(cle).push(valeur);
  }

  function grouper(lignes, cleDe) {
    const groupes = new Map();
    lignes.forEach((ligne) => ajouter(groupes, cleDe(ligne), ligne));
    return groupes;
  }

  // ===========================================================================================
  // 1. Profil, index d'un appel, références aux entités
  // ===========================================================================================

  function profilDe(options) {
    const demande = texte(options && options.profil);
    if (PROFILS.includes(demande)) return demande;
    const deLApp = typeof App !== 'undefined' && App && App.profil ? texte(App.profil.type) : '';
    return PROFILS.includes(deLApp) ? deLApp : 'demandeur';
  }

  /** Index lus une fois par appel (aucune recherche linéaire dans une boucle). */
  function contexte(options) {
    const profil = profilDe(options);
    const ordres = Donnees.lignes('ordres_travail');
    const mouvements = Donnees.lignes('mouvements_stock').slice()
      .sort((a, b) => comparer(texte(a.date), texte(b.date)) || comparer(texte(a.id), texte(b.id)));
    const pieces = new Map();                     // OT → Map(article → quantité nette), dans l'ordre des mouvements
    mouvements.forEach((mouvement) => {
      const type = texte(mouvement.type);
      const otId = texte(mouvement.ot_id);
      if (!otId || (type !== 'sortie' && type !== 'retour')) return;
      if (!pieces.has(otId)) pieces.set(otId, new Map());
      const parArticle = pieces.get(otId);
      const articleId = texte(mouvement.article_id);
      const quantite = Donnees.nombre(mouvement.quantite) || 0;
      parArticle.set(articleId, (parArticle.get(articleId) || 0) + (type === 'sortie' ? quantite : -quantite));
    });
    const servi = new Map();                      // article → OT où ses pièces nettes sont positives
    pieces.forEach((parArticle, otId) => parArticle.forEach((net, articleId) => { if (net > 0) ajouter(servi, articleId, otId); }));
    const temps = Donnees.lignes('ot_temps');
    const parTechnicien = new Map();              // technicien → OT (technicien de l'OT ou temps pointé)
    ordres.forEach((ot) => { if (texte(ot.technicien_id)) ajouter(parTechnicien, texte(ot.technicien_id), texte(ot.id)); });
    temps.forEach((ligne) => ajouter(parTechnicien, texte(ligne.technicien_id), texte(ligne.ot_id)));
    const libelles = new Map();
    Donnees.lignes('codes_defaillance').forEach((code) => {
      const cle = texte(code.famille) + '|' + texte(code.code);
      if (!libelles.has(cle)) libelles.set(cle, texte(code.libelle));     // la première ligne fait foi
    });
    const ouvre = profil !== 'demandeur';
    return {
      profil, aujourdhui: jour(options && options.maintenant) || Donnees.aujourdhui(),
      liens: { machine: true, panne: true, article: true, 'savoir-faire': true, technicien: ouvre, intervention: ouvre },
      ordres, libelles, pieces, servi, parTechnicien,
      ordresParEquipement: grouper(ordres, (ot) => texte(ot.equipement_id)),
      ordresParSymptome: grouper(ordres, (ot) => texte(ot.symptome_code)),
      codesAvecCas: new Set(ordres.filter(estUnCas).map((ot) => texte(ot.symptome_code))),
      mouvementsParArticle: grouper(mouvements, (mouvement) => texte(mouvement.article_id)),
      tempsParOt: grouper(temps, (ligne) => texte(ligne.ot_id)),
      pagesActives: Donnees.lignes('wiki_pages').filter((ligne) => texte(ligne.statut) !== 'archivée'),
      lieux: new Map(),
    };
  }

  /** Libellé d'un code de la famille ; le code s'il est inconnu ; '' sans code. */
  function libelleCode(ctx, famille, code) {
    const propre = texte(code);
    return propre ? (ctx.libelles.get(famille + '|' + propre) || propre) : '';
  }

  const titreMachine = (fiche) => [texte(fiche.repere), texte(fiche.designation)].filter(Boolean).join(' — ');
  const titreArticle = (article) => texte(article.designation) || texte(article.reference) || texte(article.id);
  const nomTechnicien = (technicien) => [texte(technicien.prenom), texte(technicien.nom)].filter(Boolean).join(' ')
    || texte(technicien.id);                                          // « Prénom Nom » (D78)

  function refMachine(id) {
    const fiche = id ? Donnees.trouver('equipements', id) : null;
    return fiche ? { equipementId: id, titre: titreMachine(fiche), lien: id } : null;
  }

  function refArticle(id) {
    const article = id ? Donnees.trouver('articles', id) : null;
    return article ? { articleId: id, titre: titreArticle(article), lien: id } : null;
  }

  function refTechnicien(ctx, id) {
    const technicien = id ? Donnees.trouver('techniciens', id) : null;
    return technicien ? { technicienId: id, nom: nomTechnicien(technicien), lien: ctx.liens.technicien ? id : null } : null;
  }

  const idPanne = (code) => PREFIXE_PANNE + encodeURIComponent(texte(code));

  /** Panne d'un code symptôme : { code, libelle, lien } (lien : sa page, si le code a un cas) ; null sans code. */
  function refPanne(ctx, code) {
    const propre = texte(code);
    return propre ? { code: propre, libelle: libelleCode(ctx, 'symptôme', propre),
      lien: ctx.codesAvecCas.has(propre) ? idPanne(propre) : null } : null;
  }

  /** Chemin du lieu d'une localisation (de la racine à elle), libellés joints par « › » ; '' sans localisation. */
  function lieuDe(ctx, localisationId) {
    const id = texte(localisationId);
    if (!ctx.lieux.has(id)) {
      const noms = [];
      const vus = new Set();
      for (let lieu = id ? Donnees.trouver('localisations', id) : null; lieu && !vus.has(texte(lieu.id));
        lieu = texte(lieu.parent_id) ? Donnees.trouver('localisations', texte(lieu.parent_id)) : null) {
        vus.add(texte(lieu.id));
        noms.unshift(texte(lieu.libelle));
      }
      ctx.lieux.set(id, noms.filter(Boolean).join(' › '));
    }
    return ctx.lieux.get(id);
  }

  // ===========================================================================================
  // 2. Interventions : ordre (D113), lignes de liste, pièces, pannes
  // ===========================================================================================

  /** Ordre des interventions (définition en tête) : les ouverts d'abord, puis les autres du plus récent au plus ancien. */
  function comparerInterventions(a, b) {
    const ouvert = estOuvert(a);
    if (ouvert !== estOuvert(b)) return ouvert ? -1 : 1;
    if (!ouvert) return comparer(dateDeLOt(b), dateDeLOt(a)) || comparer(texte(b.id), texte(a.id));
    const prevueA = jour(a.date_prevue);
    const prevueB = jour(b.date_prevue);
    return Number(texte(a.statut) !== 'En cours') - Number(texte(b.statut) !== 'En cours')
      || Number(!prevueA) - Number(!prevueB) || comparer(prevueA, prevueB) || comparer(texte(a.id), texte(b.id));
  }

  /** OT connus de ces identifiants, sans doublon, dans l'ordre des interventions. */
  function ordresDe(ids) {
    const parId = new Map();
    (ids || []).forEach((id) => {
      const ot = Donnees.trouver('ordres_travail', texte(id));
      if (ot) parId.set(texte(ot.id), ot);
    });
    return Array.from(parId.values()).sort(comparerInterventions);
  }

  /** Techniciens d'un OT : le sien, puis ceux qui y ont pointé du temps (dans l'ordre de ot_temps). */
  function techniciensDe(ctx, ot) {
    const ids = [texte(ot.technicien_id)].concat((ctx.tempsParOt.get(texte(ot.id)) || []).map((ligne) => texte(ligne.technicien_id)));
    return Array.from(new Set(ids.filter(Boolean)), (id) => refTechnicien(ctx, id)).filter(Boolean);
  }

  /** Une ligne d'une liste d'interventions (lien : null pour le demandeur). */
  function elementOt(ctx, ot) {
    const id = texte(ot.id);
    return {
      id, titre: texte(ot.titre), statut: texte(ot.statut), type: texte(ot.type), date: jour(dateDeLOt(ot)),
      datePrevue: jour(ot.date_prevue), machine: refMachine(texte(ot.equipement_id)), panne: refPanne(ctx, ot.symptome_code),
      techniciens: techniciensDe(ctx, ot), lien: ctx.liens.intervention ? id : null,
    };
  }

  const interventions = (ctx, ordres) => ordres.slice().sort(comparerInterventions).map((ot) => elementOt(ctx, ot));

  /**
   * Pièces nettes d'une liste d'OT (les clôturés seulement si `clotures`), par article connu : [{ articleId, titre,
   * quantite, ot, lien }], ot dans l'ordre des interventions ; quantité décroissante, puis article.
   */
  function piecesDesOrdres(ctx, ordres, clotures) {
    const parArticle = new Map();                 // article → { quantite, ordres }
    ordres.forEach((ot) => {
      if (clotures && !estCloture(ot)) return;
      (ctx.pieces.get(texte(ot.id)) || new Map()).forEach((net, articleId) => {
        if (!(net > 0) || !refArticle(articleId)) return;
        const entree = parArticle.get(articleId) || { quantite: 0, ordres: [] };
        entree.quantite += net;
        entree.ordres.push(ot);
        parArticle.set(articleId, entree);
      });
    });
    return Array.from(parArticle, ([articleId, entree]) => Object.assign(refArticle(articleId), {
      quantite: arrondi(entree.quantite), ot: entree.ordres.sort(comparerInterventions).map((ot) => texte(ot.id)) }))
      .sort((a, b) => b.quantite - a.quantite || comparer(a.articleId, b.articleId));
  }

  /** Pannes des cas d'une liste d'OT : [{ code, libelle, cas, derniere, lien }], cas décroissants, la plus récente, code. */
  function pannesDe(ctx, ordres) {
    const parCode = new Map();
    ordres.filter(estUnCas).forEach((ot) => {
      const entree = parCode.get(texte(ot.symptome_code)) || { cas: 0, derniere: '' };
      entree.cas += 1;
      if (jour(dateDeLOt(ot)) > entree.derniere) entree.derniere = jour(dateDeLOt(ot));
      parCode.set(texte(ot.symptome_code), entree);
    });
    return Array.from(parCode, ([code, entree]) => ({ code, libelle: libelleCode(ctx, 'symptôme', code), cas: entree.cas,
      derniere: entree.derniere, lien: idPanne(code) }))
      .sort((a, b) => b.cas - a.cas || comparer(b.derniere, a.derniere) || comparer(a.code, b.code));
  }

  /** Codes d'un champ (cause_code, remede_code) dans des cas : [{ code, libelle, cas }], cas décroissants puis code. */
  function compterCodes(ctx, cas, champ, famille) {
    const parCode = new Map();
    cas.forEach((ot) => { if (texte(ot[champ])) parCode.set(texte(ot[champ]), (parCode.get(texte(ot[champ])) || 0) + 1); });
    return Array.from(parCode, ([code, nombre]) => ({ code, libelle: libelleCode(ctx, famille, code), cas: nombre }))
      .sort((a, b) => b.cas - a.cas || comparer(a.code, b.code));
  }

  // ===========================================================================================
  // 3. Textes rédigés, références (D113), assemblage d'une entité
  // ===========================================================================================

  /**
   * Rubriques d'un texte stocké (§20.4) : [{ nom, phrases: [phrase avec ses citations et ses liens] }], dans l'ordre de
   * Wiki.RUBRIQUES[type] (une rubrique d'un autre type vient après, dans l'ordre du texte).
   */
  function rubriquesDe(valeur, type) {
    const rubriques = [];
    String(valeur || '').replace(/\r\n?/g, '\n').split('\n').forEach((ligne) => {
      const titre = /^##\s+(.+?)\s*$/.exec(ligne.trim());
      const phrase = /^-\s+(.*)$/.exec(ligne.trim());
      if (titre) rubriques.push({ nom: titre[1], phrases: [] });
      else if (phrase && rubriques.length) rubriques[rubriques.length - 1].phrases.push(phrase[1].trim());
    });
    const ordre = Wiki.RUBRIQUES[type] || [];
    const rang = (nom) => (ordre.includes(nom) ? ordre.indexOf(nom) : ordre.length);
    return rubriques.map((rubrique, position) => ({ rubrique, position }))
      .sort((a, b) => rang(a.rubrique.nom) - rang(b.rubrique.nom) || a.position - b.position).map((element) => element.rubrique);
  }

  /** Texte rédigé d'une page (ligne de wiki_pages, ou rien) : { pageId, origine, modele, validePar, valideLe, rubriques }. */
  function textesDe(ligne, type) {
    const champ = (nom) => (ligne ? texte(ligne[nom]) : '');
    return { pageId: champ('id'), origine: champ('origine'), modele: champ('modele'), validePar: champ('valide_par'),
      valideLe: champ('valide_le'), rubriques: ligne ? rubriquesDe(ligne.texte, type) : [] };
  }

  /** Ligne active du texte d'une machine ou d'un article (la première de la table, comme Wiki.page). */
  function ligneAncree(ctx, type, champ, id) {
    return ctx.pagesActives.find((ligne) => texte(ligne.type) === type && texte(ligne[champ]) === id) || null;
  }

  /**
   * OT cités, sans doublon, dans l'ordre de première apparition sur la page (D113 : « À trancher » en tête, T137) :
   * « À trancher » (pour chaque contradiction : sa phrase, puis les OT qui l'observent, sinon l'OT de l'entrée), puis
   * les phrases des textes (rubriques dans leur ordre).
   */
  function references(textes, aTrancher) {
    const ids = [];
    (aTrancher || []).forEach((contradiction) => {
      ids.push(...Wiki.citations(contradiction && contradiction.phrase));
      const ot = ((contradiction && contradiction.ot) || []).map(texte).filter(Boolean);
      ids.push(...(ot.length ? ot : [texte(contradiction && contradiction.otSource)].filter(Boolean)));
    });
    ((textes && textes.rubriques) || []).forEach((rubrique) => (rubrique.phrases || []).forEach((phrase) => {
      ids.push(...Wiki.citations(phrase));
    }));
    return Array.from(new Set(ids));
  }

  /** Détails d'un OT cité : { id, date, titre, machine, lien } (OT inconnu : date, titre, machine vides). */
  function referenceDetaillee(ctx, id) {
    const ot = Donnees.trouver('ordres_travail', id);
    return { id, date: ot ? jour(dateDeLOt(ot)) : '', titre: ot ? texte(ot.titre) : '',
      machine: ot ? refMachine(texte(ot.equipement_id)) : null, lien: ot && ctx.liens.intervention ? id : null };
  }

  /**
   * Termine une entité : textes, « À trancher » et propositions en attente (crochets de wiki-journal.js, chargé plus
   * loin, pour `reperes` = { id, pageId, type, titre } ; `suivi` : déjà calculés ; rien sans texte), références, liens.
   */
  function assembler(ctx, base, textes, reperes, suivi) {
    const options = { profil: ctx.profil, responsable: ctx.profil === 'responsable' };
    const crochet = (nom) => (reperes && typeof Wiki[nom] === 'function' ? Wiki[nom](reperes, options) || [] : []);
    const etat = suivi || { aTrancher: crochet('contradictionsDe'), enAttente: crochet('enAttenteDe') };
    return Object.assign(base, {
      textes, aTrancher: etat.aTrancher, enAttente: etat.enAttente,
      references: references(textes, etat.aTrancher).map((id) => referenceDetaillee(ctx, id)),
      retours: [], liens: Object.assign({}, ctx.liens),
    });
  }

  const TYPES_RETOURS = { 'équipement': 'machine', composant: 'article', 'savoir-faire': 'savoir-faire' };
  const CIBLES_DE_LIENS = ['machine', 'article', 'savoir-faire', 'panne'];

  /** « Pages qui renvoient ici » d'une entité (définition en tête) : la règle de Wiki.page, sur les pages qui s'affichent. */
  function retoursVers(ctx, resultat) {
    return Wiki.interne.retoursDe(ctx.pagesActives, resultat.id, resultat.textes ? resultat.textes.pageId : '')
      .filter((retour) => retour.type === 'savoir-faire' || (retour.type === 'équipement' && refMachine(retour.id))
        || (retour.type === 'composant' && refArticle(retour.id)))
      .map((retour) => ({ id: retour.id, type: TYPES_RETOURS[retour.type], titre: retour.titre, lien: retour.id }));
  }

  // ===========================================================================================
  // 4. Stock dans le temps d'un article (D113)
  // ===========================================================================================

  /**
   * { stock, sorties: [{ id, date, type, quantite, ot, machine, stock, lien }] (mouvements imputés à un OT, stock
   * restant après chacun), ruptures: [{ debut, fin }] }, dans l'ordre des mouvements (définitions en tête).
   */
  function stockDansLeTemps(ctx, articleId) {
    let stock = 0;
    let debut = null;
    const sorties = [];
    const ruptures = [];
    (ctx.mouvementsParArticle.get(articleId) || []).forEach((mouvement) => {
      const type = texte(mouvement.type);
      const quantite = Donnees.nombre(mouvement.quantite) || 0;
      if (type === 'inventaire') stock = quantite;
      else if (type === 'entrée' || type === 'retour') stock += quantite;
      else if (type === 'sortie') stock -= quantite;
      const reste = arrondi(stock);
      const date = jour(mouvement.date);
      const otId = texte(mouvement.ot_id);
      if (otId && (type === 'sortie' || type === 'retour')) {
        const ot = Donnees.trouver('ordres_travail', otId);
        sorties.push({ id: texte(mouvement.id), date, type, quantite, ot: otId, machine: ot ? refMachine(texte(ot.equipement_id)) : null,
          stock: reste, lien: ot && ctx.liens.intervention ? otId : null });
      }
      if (reste <= 0 && debut === null) debut = date;
      else if (reste > 0 && debut !== null) {
        ruptures.push({ debut, fin: date });
        debut = null;
      }
    });
    if (debut !== null) ruptures.push({ debut, fin: '' });
    return { stock: arrondi(stock), sorties, ruptures };
  }

  function etatDuStock(article, stock) {
    const pointCommande = Donnees.nombre(article.point_commande);
    if (stock <= 0) return 'rupture';
    return pointCommande !== null && stock <= pointCommande ? 'sous le seuil' : 'en stock';   // codes (D155), libellés : wiki.etat_stock.*
  }

  // ===========================================================================================
  // 5. Panne, technicien, intervention, savoir-faire ; Wiki.entite
  // ===========================================================================================

  function entitePanne(ctx, identifiant) {
    let code = '';
    try { code = decodeURIComponent(identifiant.slice(PREFIXE_PANNE.length)); } catch (erreur) { return null; }
    const ordres = ctx.ordresParSymptome.get(code) || [];
    const cas = ordres.filter(estUnCas);
    if (!code || idPanne(code) !== identifiant || !cas.length) return null;
    const jours = cas.map((ot) => jour(dateDeLOt(ot))).filter(Boolean).sort();
    const machines = new Map();
    cas.forEach((ot) => {
      const machine = refMachine(texte(ot.equipement_id));                // inconnue : comptée dans les cas seulement
      if (!machine) return;
      if (!machines.has(machine.equipementId)) machines.set(machine.equipementId, Object.assign(machine, { cas: 0 }));
      machines.get(machine.equipementId).cas += 1;
    });
    return assembler(ctx, {
      id: identifiant, type: 'panne', titre: libelleCode(ctx, 'symptôme', code),
      faits: [fait(I18n.t('wiki.fait.code'), code), fait(I18n.t('wiki.fait.cas'), cas.length), fait(I18n.t('wiki.fait.machines_touchees'), machines.size),
        fait(I18n.t('wiki.fait.premier_cas'), jours.length ? jours[0] : ''), fait(I18n.t('wiki.fait.dernier_cas'), jours.length ? jours[jours.length - 1] : '')],
      sections: {
        machines: Array.from(machines.values()).sort((a, b) => b.cas - a.cas || parTitre('equipementId')(a, b)),
        causes: compterCodes(ctx, cas, 'cause_code', 'cause'), remedes: compterCodes(ctx, cas, 'remede_code', 'remède'),
        articles: piecesDesOrdres(ctx, cas, true), interventions: interventions(ctx, ordres),
      },
    }, null, null);
  }

  /** Habilitations d'un technicien : [{ id, intitule, obtention, echeance, etat }], par intitulé, échéance décroissante. */
  // Habilitations qui comptent et leur état : celles du module Équipe (Equipe.habilitationsQuiComptent, triées par
  // intitulé, et Equipe.etatHabilitation), pour que le wiki, l'écran Équipe et l'accueil disent la même chose.
  function habilitationsDe(ctx, technicienId) {
    return Equipe.habilitationsQuiComptent(technicienId).map((ligne) => ({ id: texte(ligne.id), intitule: texte(ligne.intitule),
      obtention: jour(ligne.date_obtention), echeance: jour(ligne.date_echeance),
      etat: Equipe.etatHabilitation(ligne, ctx.aujourdhui).statut }));
  }

  const heuresDe = (technicienId) => arrondi(Donnees.lignes('ot_temps').filter((ligne) => texte(ligne.technicien_id) === technicienId)
    .reduce((somme, ligne) => somme + (Donnees.nombre(ligne.heures) || 0), 0));

  function entiteTechnicien(ctx, technicien) {
    const id = texte(technicien.id);
    const ordres = ordresDe(ctx.parTechnicien.get(id));
    return assembler(ctx, {
      id, type: 'technicien', titre: nomTechnicien(technicien),
      faits: [fait(I18n.t('wiki.fait.metier'), texte(technicien.metier)), fait(I18n.t('wiki.fait.capacite_semaine'), Donnees.nombre(technicien.capacite_h_semaine)),
        fait(I18n.t('wiki.fait.heures_pointees'), heuresDe(id)), fait(I18n.t('wiki.fait.interventions'), ordres.length), fait(I18n.t('wiki.fait.actif'), texte(technicien.actif) !== '0')]
        .concat(ctx.profil === 'responsable' ? [fait(I18n.t('wiki.fait.taux_horaire'), Donnees.nombre(technicien.taux_horaire))] : []),
      sections: { habilitations: habilitationsDe(ctx, id), interventions: ordres.map((ot) => elementOt(ctx, ot)) },
    }, null, null);
  }

  /** Demande d'origine : celle que l'OT désigne, sinon la plus ancienne demande acceptée qui pointe vers lui. */
  function demandeDe(ot) {
    const demande = (texte(ot.di_id) && Donnees.trouver('demandes', texte(ot.di_id))) || Donnees.lignes('demandes')
      .filter((di) => texte(di.ot_id) === texte(ot.id) && texte(di.statut) === 'Acceptée')
      .sort((a, b) => comparer(texte(a.date_heure), texte(b.date_heure)))[0];
    return demande ? { id: texte(demande.id), date: texte(demande.date_heure), demandeur: texte(demande.demandeur),
      symptome: texte(demande.symptome), description: texte(demande.description), statut: texte(demande.statut) } : null;
  }

  /** Pages dont un texte cite l'OT (« Cité dans le wiki ») : textes de machines et d'articles, savoir-faire ; par titre. */
  function citeDans(ctx, otId) {
    const pages = new Map();
    ctx.pagesActives.filter((ligne) => Wiki.citations(ligne.texte).includes(otId)).forEach((ligne) => {
      const type = texte(ligne.type);
      const machine = type === 'équipement' ? refMachine(texte(ligne.equipement_id)) : null;
      const article = type === 'composant' ? refArticle(texte(ligne.article_id)) : null;
      let entree = type === 'savoir-faire' ? { id: texte(ligne.id), type, titre: texte(ligne.titre), lien: texte(ligne.id) } : null;
      if (machine) entree = { id: machine.equipementId, type: 'machine', titre: machine.titre, lien: machine.lien };
      if (article) entree = { id: article.articleId, type: 'article', titre: article.titre, lien: article.lien };
      if (entree && !pages.has(entree.id)) pages.set(entree.id, entree);
    });
    return Array.from(pages.values()).sort(parTitre('id'));
  }

  function entiteIntervention(ctx, ot) {
    const id = texte(ot.id);
    const machine = refMachine(texte(ot.equipement_id));
    const technicien = refTechnicien(ctx, texte(ot.technicien_id));
    const panne = refPanne(ctx, ot.symptome_code);
    const demande = demandeDe(ot);
    const valeurs = [[I18n.t('wiki.fait.type'), 'type'], [I18n.t('commun.champ.priorite'), 'priorite'], [I18n.t('commun.champ.statut'), 'statut']].map(([libelle, champ]) => fait(libelle, texte(ot[champ])));
    const dates = [[I18n.t('wiki.fait.cree_le'), 'date_creation'], [I18n.t('wiki.fait.prevu_le'), 'date_prevue'], [I18n.t('wiki.fait.debut'), 'date_debut'], [I18n.t('wiki.fait.fin'), 'date_fin']]
      .map(([libelle, champ]) => fait(libelle, texte(ot[champ])));
    return assembler(ctx, {
      id, type: 'intervention', titre: texte(ot.titre) || id,
      faits: [fait(I18n.t('wiki.fait.machine'), machine ? machine.titre : texte(ot.equipement_id), machine && machine.lien)].concat(valeurs,
        [fait(I18n.t('commun.champ.technicien'), technicien ? technicien.nom : '', technicien && technicien.lien)], dates, [
          fait(I18n.t('wiki.fait.arret_production'), texte(ot.arret_production) === '1'), fait(I18n.t('wiki.fait.duree_arret'), Donnees.nombre(ot.duree_arret_h)),
          fait(I18n.t('wiki.fait.panne'), panne ? panne.libelle : '', panne && panne.lien), fait(I18n.t('wiki.fait.cause'), libelleCode(ctx, 'cause', ot.cause_code)),
          fait(I18n.t('wiki.fait.remede'), libelleCode(ctx, 'remède', ot.remede_code)), fait(I18n.t('wiki.fait.demande_origine'), demande ? demande.id : ''),
          fait(I18n.t('wiki.fait.cloture_technique'), texte(ot.date_cloture_tech)), fait(I18n.t('wiki.fait.cloture_administrative'), texte(ot.date_cloture_admin))]),
      sections: {
        demande, travail: texte(ot.travail_a_faire), compteRendu: texte(ot.compte_rendu), astuce: texte(ot.astuce),
        motifAttente: texte(ot.motif_attente), motifAnnulation: texte(ot.motif_annulation),
        techniciens: techniciensDe(ctx, ot),
        pieces: Array.from(ctx.pieces.get(id) || new Map()).filter(([articleId, net]) => net > 0 && refArticle(articleId))
          .map(([articleId, net]) => Object.assign(refArticle(articleId), { quantite: arrondi(net) })),
        operations: Donnees.lignes('ot_operations').filter((operation) => texte(operation.ot_id) === id)
          .sort((a, b) => (Donnees.nombre(a.ordre) || 0) - (Donnees.nombre(b.ordre) || 0) || comparer(texte(a.id), texte(b.id)))
          .map((operation) => ({ ordre: Donnees.nombre(operation.ordre), operation: texte(operation.operation),
            valeurAttendue: texte(operation.valeur_attendue), fait: texte(operation.fait) === '1', valeurMesuree: texte(operation.valeur_mesuree) })),
        temps: (ctx.tempsParOt.get(id) || []).slice()
          .sort((a, b) => comparer(texte(a.date), texte(b.date)) || comparer(texte(a.id), texte(b.id)))
          .map((ligne) => Object.assign({ id: texte(ligne.id), date: jour(ligne.date), technicienId: texte(ligne.technicien_id), nom: '',
            lien: null }, refTechnicien(ctx, texte(ligne.technicien_id)) || {}, { heures: Donnees.nombre(ligne.heures) })),
        citeDans: citeDans(ctx, id), ficheOT: '#/ot/' + encodeURIComponent(id),
      },
    }, null, null);
  }

  function entiteSavoirFaire(ctx, ligne, options) {
    const page = Wiki.page(texte(ligne.id), { profil: ctx.profil, responsable: ctx.profil === 'responsable',
      maintenant: options && options.maintenant });
    if (!page || page.type !== 'savoir-faire') return null;
    const rattachement = Wiki.interne.rattachementDe(ligne);
    return assembler(ctx, {
      id: page.id, type: 'savoir-faire', titre: page.titre,
      faits: [fait(I18n.t('wiki.fait.rattache_a'), rattachement ? rattachement.titre : '', rattachement && rattachement.lien)]
        .concat(page.mere ? [fait(I18n.t('wiki.fait.sous_page_de'), page.mere.titre, page.mere.id)] : []),
      sections: { entete: page.entete, rattachement, mere: page.mere, sousPages: page.sousPages },
    }, textesDe(ligne, 'savoir-faire'), null, { aTrancher: page.contradictions, enAttente: page.enAttente });
  }

  /** Page d'une entité (§20.12, D113, D114) — voir l'API en tête. */
  function entite(id, options) {
    const ctx = contexte(options);
    const resultat = entiteSansRetours(ctx, texte(id), options);
    if (resultat && CIBLES_DE_LIENS.includes(resultat.type)) resultat.retours = retoursVers(ctx, resultat);
    return resultat;
  }

  function entiteSansRetours(ctx, identifiant, options) {
    if (!identifiant) return null;
    const trouver = (table, cle) => (texte(cle) ? Donnees.trouver(table, texte(cle)) : null);
    if (identifiant.startsWith(PREFIXE_PANNE)) return entitePanne(ctx, identifiant);
    if (trouver('equipements', identifiant)) return Wiki.interne.entiteMachine(ctx, trouver('equipements', identifiant));
    if (trouver('articles', identifiant)) return Wiki.interne.entiteArticle(ctx, trouver('articles', identifiant));
    const technicien = trouver('techniciens', identifiant);
    if (technicien) return ctx.liens.technicien ? entiteTechnicien(ctx, technicien) : null;
    const ot = trouver('ordres_travail', identifiant);
    if (ot) return ctx.liens.intervention ? entiteIntervention(ctx, ot) : null;
    const ligne = trouver('wiki_pages', identifiant);
    if (!ligne || texte(ligne.statut) === 'archivée') return null;
    const machine = texte(ligne.type) === 'équipement' ? trouver('equipements', ligne.equipement_id) : null;
    const article = texte(ligne.type) === 'composant' ? trouver('articles', ligne.article_id) : null;
    if (machine) return Wiki.interne.entiteMachine(ctx, machine);
    if (article) return Wiki.interne.entiteArticle(ctx, article);
    return texte(ligne.type) === 'savoir-faire' ? entiteSavoirFaire(ctx, ligne, options) : null;
  }

  // ===========================================================================================
  // 6. Listes et accueil
  // ===========================================================================================

  /** Pannes (codes qui ont un cas) : [{ id, code, titre, cas, machines, cause, derniere, lien }], cas décroissants, code. */
  function listePannes(ctx) {
    const pannes = [];
    ctx.ordresParSymptome.forEach((ordres, code) => {
      if (!code || !ctx.codesAvecCas.has(code)) return;
      const cas = ordres.filter(estUnCas);
      const causes = compterCodes(ctx, cas, 'cause_code', 'cause');
      pannes.push({
        id: idPanne(code), code, titre: libelleCode(ctx, 'symptôme', code), cas: cas.length,
        machines: new Set(cas.map((ot) => texte(ot.equipement_id)).filter((machine) => refMachine(machine))).size,
        cause: causes.length ? { code: causes[0].code, libelle: causes[0].libelle } : null,
        derniere: cas.map((ot) => jour(dateDeLOt(ot))).reduce((plusRecente, date) => (date > plusRecente ? date : plusRecente), ''),
        lien: idPanne(code),
      });
    });
    return pannes.sort((a, b) => b.cas - a.cas || comparer(a.code, b.code));
  }

  /** Articles : [{ articleId, titre, reference, emplacement, stock, unite, etat, critique, interventions, lien }], par titre. */
  function listeArticles(ctx) {
    return Donnees.lignes('articles').map((article) => {
      const id = texte(article.id);
      const stock = stockDansLeTemps(ctx, id).stock;
      return Object.assign(refArticle(id), { reference: texte(article.reference), emplacement: texte(article.emplacement),
        stock, unite: texte(article.unite), etat: etatDuStock(article, stock), critique: texte(article.critique) === '1',
        interventions: ordresDe(ctx.servi.get(id)).length });
    }).sort(parTitre('articleId'));
  }

  /** Techniciens : [{ technicienId, nom, metier, actif, interventions, habilitations, heures, lien }], par nom. */
  function listeTechniciens(ctx) {
    return Donnees.lignes('techniciens').map((technicien) => {
      const id = texte(technicien.id);
      return Object.assign(refTechnicien(ctx, id), { metier: texte(technicien.metier), actif: texte(technicien.actif) !== '0',
        interventions: ordresDe(ctx.parTechnicien.get(id)).length, habilitations: habilitationsDe(ctx, id).length, heures: heuresDe(id) });
    }).sort((a, b) => comparer(a.nom, b.nom) || comparer(a.technicienId, b.technicienId));
  }

  const LISTES = {
    machine: (ctx) => Wiki.interne.listeMachines(ctx), panne: listePannes, article: listeArticles,
    'savoir-faire': (ctx) => Wiki.interne.listeSavoirFaire(ctx),
    technicien: (ctx) => (ctx.liens.technicien ? listeTechniciens(ctx) : null),
    intervention: (ctx) => (ctx.liens.intervention ? interventions(ctx, ctx.ordres) : null),
  };

  /** Données d'une liste (§20.12, routes #/wiki/<liste>) ; null pour un type inconnu ou que le profil ne voit pas. */
  function listeEntites(type, options) {
    return Object.prototype.hasOwnProperty.call(LISTES, texte(type)) ? LISTES[texte(type)](contexte(options)) : null;
  }

  /**
   * Suivi du wiki (responsable), mêmes définitions que les vues du journal où il mène (wiki-journal-ecrans.js) : à
   * valider ; à trancher (contradictions ouvertes des entrées validées) ; en échec (OT dont la dernière entrée
   * d'ingestion est refusée et qui n'a aucune autre entrée que rejetée ou refusée).
   */
  function suiviDuWiki() {
    const journal = Donnees.lignes('wiki_journal');
    const lire = (valeur) => {
      try { const lu = JSON.parse(valeur); return Array.isArray(lu) ? lu : []; } catch (erreur) { return []; }
    };
    const rang = (entree) => Number(texte(entree.id).replace(/\D/g, '')) || 0;
    const echoue = (entree) => ['rejetée', 'refusée'].includes(texte(entree.statut));
    const ingestions = journal.filter((entree) => texte(entree.nature) === 'ingestion' && texte(entree.ot_id));
    const vivants = new Set(ingestions.filter((entree) => !echoue(entree)).map((entree) => texte(entree.ot_id)));
    const dernieres = new Map();
    ingestions.filter((entree) => echoue(entree) && !vivants.has(texte(entree.ot_id))).forEach((entree) => {
      const avant = dernieres.get(texte(entree.ot_id));
      if (!avant || rang(avant) < rang(entree)) dernieres.set(texte(entree.ot_id), entree);
    });
    return {
      aValider: journal.filter((entree) => texte(entree.statut) === 'à valider').length,
      aTrancher: journal.filter((entree) => texte(entree.statut) === 'validée').reduce((total, entree) => total
        + lire(entree.contradictions).filter((contradiction) => contradiction && texte(contradiction.statut) === 'ouverte').length, 0),
      enEchec: Array.from(dernieres.values()).filter((entree) => texte(entree.statut) === 'refusée').length,
    };
  }

  /**
   * Accueil de l'encyclopédie (D113) : { nombres, machinesPlusDInterventions, pannePlusFrequente, articles: { sousLeSeuil,
   * enRupture }, habilitations: { suivies, aRenouveler, echues } (null pour le demandeur), dernieres (OT clôturés, du plus
   * récent), pannesFrequentes, suivi (responsable seulement, sinon null) }.
   */
  function accueilEncyclopedie(options) {
    const ctx = contexte(options);
    const pannes = listePannes(ctx);
    const articles = listeArticles(ctx);
    const habilitations = ctx.liens.technicien ? Donnees.lignes('techniciens').filter((technicien) => texte(technicien.actif) !== '0')
      .flatMap((technicien) => habilitationsDe(ctx, texte(technicien.id))) : null;
    const clotures = ctx.ordres.filter(estCloture).sort(comparerInterventions);
    const compter = (liste, champ, valeur) => liste.filter((element) => element[champ] === valeur).length;
    return {
      nombres: {
        machines: Donnees.lignes('equipements').length, pannes: pannes.length, articles: articles.length,
        techniciens: ctx.liens.technicien ? Donnees.lignes('techniciens').length : null,
        savoirFaire: Wiki.interne.listeSavoirFaire(ctx).length, interventions: ctx.liens.intervention ? ctx.ordres.length : null,
        cloturees: clotures.length,
      },
      machinesPlusDInterventions: Donnees.lignes('equipements').map((fiche) => Object.assign(refMachine(texte(fiche.id)),
        { interventions: (ctx.ordresParEquipement.get(texte(fiche.id)) || []).length }))
        .sort((a, b) => b.interventions - a.interventions || parTitre('equipementId')(a, b)).slice(0, MACHINES_ACCUEIL),
      pannePlusFrequente: pannes.length ? pannes[0] : null,
      articles: { sousLeSeuil: compter(articles, 'etat', 'sous le seuil'), enRupture: compter(articles, 'etat', 'rupture') },
      habilitations: habilitations ? { suivies: habilitations.length, aRenouveler: compter(habilitations, 'etat', 'à renouveler'),
        echues: compter(habilitations, 'etat', 'échue') } : null,
      dernieres: clotures.slice(0, Wiki.SEUILS.dernieres).map((ot) => elementOt(ctx, ot)),
      pannesFrequentes: pannes.slice(0, PANNES_ACCUEIL),
      suivi: ctx.profil === 'responsable' ? suiviDuWiki() : null,
    };
  }

  // Socle lu à l'appel par les pages Machine et Article et les listes de wiki-calculs.js (Wiki.interne, pas une API).
  Object.assign(Wiki.interne, {
    fait, parTitre, arrondi, refMachine, refArticle, lieuDe, ordresDe, interventions, piecesDesOrdres, pannesDe, textesDe,
    ligneAncree, assembler, stockDansLeTemps, etatDuStock,
  });

  return { entite, listeEntites, accueilEncyclopedie, ordreInterventions: (ids) => ordresDe(ids).map((ot) => texte(ot.id)),
    references, idPanne };
})());
