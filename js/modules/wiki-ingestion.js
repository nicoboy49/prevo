'use strict';
// Wiki (5/8) — ingestion (lot 6 refondu, ARCHITECTURE.md §20.5 ; D104, D111, D112) : file des OT clôturés
// administrativement, état proposé, pages concernées, antériorité, données envoyées à l'IA (liste blanche), lecture
// de la réponse (mise en forme puis contrôles de wiki-texte.js), ordonnanceur et traitement de la file.
//
// Précisions au contrat (§20.5) :
//  - clés des pages : « EQ:<équipement> », « ART:<article> » (pages ancrées, qu'elles aient un texte ou non),
//    « WP:<page> » (pages libres validées), « TITRE:<titre comparable> » (page créée par une proposition encore à
//    valider) ; une clé « CAUSE:<code> » réserve la cause de l'OT (deux OT de même cause ne partent pas ensemble) ;
//  - une page créée par une proposition à valider entre dans l'état proposé sous sa clé TITRE ; une proposition
//    suivante qui la modifie la retrouve par son titre, avant comme après sa validation ;
//  - les écritures de wiki_journal ne sont pas recopiées au journal général (la table est elle-même un journal) ;
//  - une réponse refusée par les contrôles : entrée « refusée », raisons une par ligne ; une collision (titre créé
//    entre-temps par un autre OT) : entrée remise « en file », motif « rejoué : page créée entre-temps », au plus
//    trois fois, puis « refusée » ;
//  - toute autre erreur de l'IA (injoignable, délai, annulation, refus D67) arrête le traitement : l'OT reste en file,
//    l'erreur est rendue dans le bilan ; les envois déjà partis finissent.

Object.assign(Wiki, (() => {

  const SEUILS = Wiki.SEUILS;
  const STATUT_CLOTURE_ADMIN = 'Clôturé administrativement';
  const STATUTS_FILE = ['en file', 'à refaire'];
  const STATUTS_DEJA = ['en file', 'à refaire', 'à valider', 'validée', 'rien à ajouter', 'refusée'];
  const ESSAIS_COLLISION_MAX = 3;
  const MOTIF_COLLISION = 'rejoué : page créée entre-temps';

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  function comparer(a, b) {
    return a < b ? -1 : (a > b ? 1 : 0);
  }

  function json(valeur, defaut) {
    try { return JSON.parse(valeur); } catch (erreur) { return defaut; }
  }

  function annoncer(message, ton) {
    if (typeof UI !== 'undefined' && typeof UI.toast === 'function') UI.toast(message, ton);
  }

  // ===========================================================================================
  // 1. File (D104, D111)
  // ===========================================================================================

  function entreesIngestion() {
    return Donnees.lignes('wiki_journal').filter((entree) => texte(entree.nature) === 'ingestion');
  }

  /** Ordre de la file : date d'intervention (date de fin réelle de l'OT), puis numéro d'OT (D111). */
  function comparerFile(a, b) {
    return comparer(texte(a.date_intervention), texte(b.date_intervention)) || comparer(texte(a.ot_id), texte(b.ot_id))
      || comparer(texte(a.id), texte(b.id));
  }

  /** Entrées « en file » et « à refaire », dans l'ordre où elles seront traitées. */
  function file() {
    return entreesIngestion().filter((entree) => STATUTS_FILE.includes(texte(entree.statut))).sort(comparerFile);
  }

  /**
   * Met des OT clôturés administrativement dans la file (une entrée « en file » chacun) ; un OT qui a déjà une entrée
   * en file, à valider, validée, sans rien à ajouter ou refusée n'est pas remis. Rend le nombre d'OT ajoutés.
   * options.annoncer : message à l'écran (clôture administrative) ; une erreur n'est alors jamais levée.
   */
  async function mettreEnFile(otIds, options) {
    const ids = Array.from(new Set((otIds || []).map(texte).filter(Boolean)));
    const avecMessage = Boolean(options && options.annoncer);
    try {
      const ajoutes = await Donnees.modifier('wiki_journal', (lignes, outils) => {
        const deja = new Set(lignes.filter((ligne) => texte(ligne.nature) === 'ingestion'
          && STATUTS_DEJA.includes(texte(ligne.statut))).map((ligne) => texte(ligne.ot_id)));
        let nombre = 0;
        ids.forEach((id) => {
          const ot = Donnees.trouver('ordres_travail', id);
          if (!ot || texte(ot.statut) !== STATUT_CLOTURE_ADMIN || deja.has(id)) return;
          lignes.push({ id: outils.nouvelId(lignes), nature: 'ingestion', ot_id: id, date_intervention: texte(ot.date_fin),
            statut: 'en file', anterieure: '0', essais: '0', cree_le: outils.maintenant() });
          deja.add(id);
          nombre += 1;
        });
        return nombre;
      }, { journal: false });
      if (avecMessage && ajoutes) annoncer('OT ajouté à la file du wiki.', 'info');
      return ajoutes || 0;
    } catch (erreur) {
      if (!avecMessage) throw erreur;
      annoncer('OT non ajouté à la file du wiki (' + (erreur && erreur.message ? erreur.message : String(erreur))
        + ') : il reste « hors du wiki », à ajouter depuis l\'écran Wiki.', 'attention');
      return 0;
    }
  }

  /** OT clôturés administrativement sans aucune entrée d'ingestion (historique, import) ; options.equipementId. */
  function horsDuWiki(options) {
    const equipementId = texte(options && options.equipementId);
    const vus = new Set(entreesIngestion().map((entree) => texte(entree.ot_id)));
    return Donnees.lignes('ordres_travail').filter((ot) => texte(ot.statut) === STATUT_CLOTURE_ADMIN && !vus.has(texte(ot.id))
      && (!equipementId || texte(ot.equipement_id) === equipementId))
      .sort((a, b) => comparer(texte(a.date_fin), texte(b.date_fin)) || comparer(texte(a.id), texte(b.id)));
  }

  // ===========================================================================================
  // 2. État proposé (D105) : pages validées, puis les propositions « à valider » dans l'ordre
  // ===========================================================================================

  function titreEquipement(equipement) {
    return [texte(equipement.repere), texte(equipement.designation)].filter(Boolean).join(' — ');
  }

  function cleDeLigne(ligne) {
    if (texte(ligne.type) === 'équipement' && texte(ligne.equipement_id)) return 'EQ:' + texte(ligne.equipement_id);
    if (texte(ligne.type) === 'composant' && texte(ligne.article_id)) return 'ART:' + texte(ligne.article_id);
    return 'WP:' + texte(ligne.id);
  }

  /** Titre comparable → clé, pour toutes les pages de l'état et toutes les pages calculées (équipements, articles). */
  function indexDesTitres(pages) {
    const index = new Map();
    Donnees.lignes('equipements').forEach((e) => index.set(Wiki.comparable(titreEquipement(e)), 'EQ:' + texte(e.id)));
    Donnees.lignes('articles').forEach((a) => index.set(Wiki.comparable(a.designation), 'ART:' + texte(a.id)));
    pages.forEach((page) => index.set(Wiki.comparable(page.titre), page.cle));
    return index;
  }

  function rattacher(page, rattacheA, index) {
    const cle = index.get(Wiki.comparable(rattacheA)) || '';
    if (cle.startsWith('EQ:')) page.equipementId = cle.slice(3);
    if (cle.startsWith('ART:')) page.articleId = cle.slice(4);
    page.rattacheA = cle;
  }

  /** État proposé → Map clé → { cle, pageId, titre, type, texte, equipementId, articleId, causeCode, rattacheA, version }. */
  function etatPropose() {
    const pages = new Map();
    const lignes = Donnees.lignes('wiki_pages').filter((ligne) => texte(ligne.statut) !== 'archivée');
    // Rattachement d'un savoir-faire : la clé de la page visée (« ART:… » pour une page de composant ancrée).
    const cleDe = new Map(lignes.map((ligne) => [texte(ligne.id), cleDeLigne(ligne)]));
    lignes.forEach((ligne) => {
      const cle = cleDeLigne(ligne);
      const rattache = texte(ligne.rattache_a);
      pages.set(cle, { cle, pageId: texte(ligne.id), titre: texte(ligne.titre), type: texte(ligne.type), texte: ligne.texte || '',
        equipementId: texte(ligne.equipement_id), articleId: texte(ligne.article_id), causeCode: texte(ligne.cause_code),
        rattacheA: rattache ? cleDe.get(rattache) || 'WP:' + rattache : '', version: Number(ligne.version) || 0 });
    });
    const enAttente = Donnees.lignes('wiki_journal').filter((entree) => texte(entree.statut) === 'à valider')
      .sort((a, b) => (Number(a.ordre) || 0) - (Number(b.ordre) || 0) || comparer(texte(a.id), texte(b.id)));
    enAttente.forEach((entree) => json(entree.changements, []).forEach((changement) => {
      const index = indexDesTitres(Array.from(pages.values()));
      let cle = texte(changement.cle);
      if (cle.startsWith('TITRE:') && index.has(cle.slice(6))) cle = index.get(cle.slice(6));
      const page = pages.get(cle);
      if (page) { page.texte = changement.apres || ''; return; }
      const nouvelle = { cle, pageId: '', titre: texte(changement.titre), type: texte(changement.type), texte: changement.apres || '',
        equipementId: '', articleId: '', causeCode: '', rattacheA: '', version: 0 };
      if (cle.startsWith('EQ:')) nouvelle.equipementId = cle.slice(3);
      if (cle.startsWith('ART:')) nouvelle.articleId = cle.slice(4);
      if (texte(changement.rattacheA)) rattacher(nouvelle, changement.rattacheA, index);
      pages.set(cle, nouvelle);
    }));
    return pages;
  }

  // ===========================================================================================
  // 3. Pages concernées (D112) et antériorité (D111)
  // ===========================================================================================

  /** Articles consommés par un OT : sorties − retours > 0, { articleId, designation, reference, quantite }. */
  function articlesConsommes(otId) {
    const net = new Map();
    Donnees.lignes('mouvements_stock').filter((m) => texte(m.ot_id) === otId).forEach((m) => {
      const signe = texte(m.type) === 'sortie' ? 1 : (texte(m.type) === 'retour' ? -1 : 0);
      if (signe) net.set(texte(m.article_id), (net.get(texte(m.article_id)) || 0) + signe * (Number(m.quantite) || 0));
    });
    return Array.from(net.entries()).filter(([, quantite]) => quantite > 0).sort((a, b) => comparer(a[0], b[0]))
      .map(([articleId, quantite]) => {
        const article = Donnees.trouver('articles', articleId) || {};
        return { articleId, designation: texte(article.designation), reference: texte(article.reference).replace(/^'/, ''), quantite };
      });
  }

  function pageCalculee(cle) {
    if (cle.startsWith('EQ:')) {
      const equipement = Donnees.trouver('equipements', cle.slice(3));
      return equipement ? { cle, pageId: '', titre: titreEquipement(equipement), type: 'équipement', texte: '',
        equipementId: cle.slice(3), articleId: '', causeCode: '', rattacheA: '', version: 0 } : null;
    }
    if (cle.startsWith('ART:')) {
      const article = Donnees.trouver('articles', cle.slice(4));
      return article ? { cle, pageId: '', titre: texte(article.designation), type: 'composant', texte: '',
        equipementId: '', articleId: cle.slice(4), causeCode: '', rattacheA: '', version: 0 } : null;
    }
    return null;
  }

  /**
   * Pages concernées par un OT, calculées avant l'envoi → { cles, envoyees } : clés de son équipement, de chaque
   * article consommé et de sa cause, puis des pages envoyées ; envoyées dans l'ordre de priorité — équipement,
   * savoir-faire de l'équipement, articles, savoir-faire des articles, modes ancrés sur la cause, pages liées depuis
   * la page de l'équipement —, pagesEnvoyeesMax au plus.
   */
  function pagesConcernees(otId, etatDonne) {
    const etat = etatDonne || etatPropose();
    const ot = Donnees.trouver('ordres_travail', otId);
    if (!ot) return { cles: [], envoyees: [] };
    const equipementId = texte(ot.equipement_id);
    const articles = articlesConsommes(texte(ot.id)).map((article) => article.articleId);
    const cles = [];
    const envoyees = [];
    const ajouter = (cle) => {
      if (!cle || cles.includes(cle)) return;
      cles.push(cle);
      const page = etat.get(cle) || pageCalculee(cle);
      if (page && envoyees.length < SEUILS.pagesEnvoyeesMax) envoyees.push(page);
    };
    const toutes = Array.from(etat.values()).sort((a, b) => comparer(a.titre, b.titre) || comparer(a.cle, b.cle));
    ajouter('EQ:' + equipementId);
    toutes.filter((page) => page.type === 'savoir-faire'
      && (page.equipementId === equipementId || page.rattacheA === 'EQ:' + equipementId)).forEach((page) => ajouter(page.cle));
    articles.forEach((articleId) => ajouter('ART:' + articleId));
    toutes.filter((page) => page.type === 'savoir-faire' && !page.equipementId
      && (articles.includes(page.articleId) || articles.some((articleId) => page.rattacheA === 'ART:' + articleId)))
      .forEach((page) => ajouter(page.cle));
    const cause = texte(ot.cause_code);
    if (cause) {
      cles.push('CAUSE:' + cause);
      toutes.filter((page) => page.type === 'mode' && page.causeCode === cause).forEach((page) => ajouter(page.cle));
    }
    const pageEquipement = etat.get('EQ:' + equipementId);
    if (pageEquipement) {
      const index = indexDesTitres(toutes);
      Wiki.liensDe(pageEquipement.texte).forEach((titre) => ajouter(index.get(Wiki.comparable(titre))));
    }
    return { cles, envoyees };
  }

  function dateIntervention(otId) {
    const ot = Donnees.trouver('ordres_travail', otId);
    return ot ? texte(ot.date_fin) : '';
  }

  // ===========================================================================================
  // 4. Données envoyées (liste blanche, CS99) et lecture de la réponse
  // ===========================================================================================

  function libelleCode(famille, code) {
    const propre = texte(code);
    if (!propre) return '';
    const ligne = Donnees.lignes('codes_defaillance').find((c) => texte(c.famille) === famille && texte(c.code) === propre);
    return ligne ? texte(ligne.libelle) : propre;
  }

  function symptomeDI(ot) {
    const di = (texte(ot.di_id) && Donnees.trouver('demandes', texte(ot.di_id)))
      || Donnees.lignes('demandes').find((demande) => texte(demande.ot_id) === texte(ot.id) && texte(demande.statut) !== 'Regroupée');
    return di ? texte(di.symptome) : '';
  }

  function catalogueIngestion(etat) {
    const vus = new Set();
    const catalogue = [];
    const ajouter = (titre, type) => {
      const cle = Wiki.comparable(titre);
      if (!cle || vus.has(cle)) return;
      vus.add(cle);
      catalogue.push({ titre: texte(titre), type });
    };
    Wiki.catalogue().forEach((page) => ajouter(page.titre, page.type));
    Array.from(etat.values()).filter((page) => !page.pageId && page.cle.startsWith('TITRE:'))
      .sort((a, b) => comparer(a.titre, b.titre)).forEach((page) => ajouter(page.titre, page.type));
    return catalogue.slice(0, SEUILS.catalogueMax);
  }

  /**
   * Données d'une requête d'ingestion (§20.5) : l'OT (liste blanche : jamais les noms des techniciens ou des demandeurs,
   * les coûts, les documents, les photos), l'antériorité, les pages envoyées (clé, titre, type, texte, dates
   * d'intervention des OT qu'elles citent) et le catalogue.
   */
  function donneesIngestion(otId, etatDonne) {
    const etat = etatDonne || etatPropose();
    const ot = Donnees.trouver('ordres_travail', otId);
    if (!ot) throw new Error('Wiki.donneesIngestion : OT inconnu « ' + otId + ' ».');
    const equipement = Donnees.trouver('equipements', texte(ot.equipement_id)) || {};
    const concernees = pagesConcernees(texte(ot.id), etat);
    const pages = concernees.envoyees.map((page) => ({ cle: page.cle, titre: page.titre, type: page.type, texte: page.texte,
      otDates: Wiki.citationsDe(page.texte).map((id) => ({ id, date: dateIntervention(id) })) }));
    const plusRecente = pages.flatMap((page) => page.otDates.map((entree) => entree.date)).filter(Boolean).sort().pop() || '';
    return {
      ot: {
        id: texte(ot.id), dateIntervention: texte(ot.date_fin), type: texte(ot.type),
        equipement: { repere: texte(equipement.repere), designation: texte(equipement.designation),
          marque: texte(equipement.marque), modele: texte(equipement.modele) },
        titre: texte(ot.titre), travail: texte(ot.travail_a_faire), symptome: libelleCode('symptôme', ot.symptome_code),
        cause: libelleCode('cause', ot.cause_code), remede: libelleCode('remède', ot.remede_code),
        compteRendu: ot.compte_rendu || '', astuce: ot.astuce || '',
        pieces: articlesConsommes(texte(ot.id)).map((article) => ({ designation: article.designation,
          reference: article.reference, quantite: String(article.quantite) })),
        dureeArret: texte(ot.duree_arret_h), symptomeDI: symptomeDI(ot),
      },
      anterieure: Boolean(plusRecente && texte(ot.date_fin) && texte(ot.date_fin) < plusRecente),
      pages,
      catalogue: catalogueIngestion(etat),
      cles: concernees.cles,
    };
  }

  // Texte de référence des contrôles (nombres) : tout ce qui a été envoyé de l'OT, sauf sa date.
  function sourceDe(ot) {
    const eq = ot.equipement || {};
    return [ot.id, ot.type, eq.repere, eq.designation, eq.marque, eq.modele, ot.titre, ot.travail, ot.symptome, ot.cause,
      ot.remede, ot.compteRendu, ot.astuce, ot.dureeArret, ot.symptomeDI]
      .concat(...(ot.pieces || []).map((piece) => [piece.designation, piece.reference, piece.quantite])).map(texte).join('\n');
  }

  function liste(valeur) {
    return Array.isArray(valeur) ? valeur : [];
  }

  /**
   * Réponse de l'IA (objet JSON) → { rien, changements: [{ cle, titre, type, creation, rattacheA, avant, apres }],
   * contradictions: [{ page, pageCle, phrase, observation, ot }] } après les contrôles du §20.6 ; sinon
   * Ia.IaReponseInvalide (raisons dans erreur.raisons). Sert de `verifier` à la consigne ingestionWiki.
   */
  function lireIngestion(objet, donnees) {
    if (!objet || typeof objet !== 'object' || !Array.isArray(objet.pages) || !Array.isArray(objet.contradictions)
      || typeof objet.rien_a_ajouter !== 'boolean') {
      throw new Ia.IaReponseInvalide('Réponse de l\'IA hors de la forme attendue : aucune proposition.');
    }
    const envoyeeDe = new Map(liste(donnees.pages).map((page) => [Wiki.comparable(page.titre), page]));
    const pages = objet.pages.map((item) => {
      const action = texte(item && item.action);
      const envoyee = action === 'modifier' ? envoyeeDe.get(Wiki.comparable(item.titre)) : null;
      const type = envoyee ? envoyee.type : texte(item && item.type);
      const rubriques = liste(item && item.rubriques).map((rubrique) => ({ rubrique: rubrique && rubrique.rubrique,
        phrases: liste(rubrique && rubrique.phrases).map((phrase) => ({ texte: phrase && phrase.texte, ot: liste(phrase && phrase.ot) })) }));
      return { action, titre: envoyee ? envoyee.titre : texte(item && item.titre), type, rattacheA: texte(item && item.rattache_a),
        texte: Wiki.ecrireTexte(rubriques, type), cle: envoyee ? envoyee.cle : 'TITRE:' + Wiki.comparable(item && item.titre),
        avant: envoyee ? envoyee.texte : '' };
    });
    const contradictions = objet.contradictions.map((c) => ({ page: texte(c && c.page), phrase: texte(c && c.phrase),
      observation: texte(c && c.observation), ot: liste(c && c.ot).map(texte).filter(Boolean) }));
    const controle = Wiki.controlerProposition({ rien: objet.rien_a_ajouter, pages, contradictions }, {
      otIngere: { id: donnees.ot.id, dateIntervention: donnees.ot.dateIntervention, sourceTexte: sourceDe(donnees.ot) },
      anterieure: Boolean(donnees.anterieure), pagesEnvoyees: liste(donnees.pages), catalogue: liste(donnees.catalogue),
    });
    if (!controle.ok) {
      const erreur = new Ia.IaReponseInvalide('Proposition refusée : ' + controle.raisons.join(' '));
      erreur.raisons = controle.raisons;
      throw erreur;
    }
    return {
      rien: objet.rien_a_ajouter,
      changements: pages.map((page) => ({ cle: page.cle, titre: page.titre, type: page.type, creation: page.action === 'creer',
        rattacheA: page.rattacheA, avant: page.avant, apres: page.texte })),
      contradictions: contradictions.map((c) => Object.assign({ pageCle: envoyeeDe.get(Wiki.comparable(c.page)).cle }, c)),
    };
  }

  // ===========================================================================================
  // 5. Ordonnanceur (D112) et traitement de la file
  // ===========================================================================================

  /**
   * Entrées de la file qui peuvent partir maintenant → [{ entree, cles }] : dans l'ordre de la file, tant que moins de
   * `agents` envois sont en cours ; une entrée part si aucune de ses clés n'est prise par un envoi en cours NI par une
   * entrée plus ancienne de la file restée en attente (pour chaque page, l'ordre des dates d'intervention).
   */
  function prochainsEnvois(entrees, enCours, options) {
    const agents = (options && options.agents) || SEUILS.agentsSimultanes;
    const etat = (options && options.etat) || etatPropose();
    const prises = new Set();
    (enCours || []).forEach((envoi) => (envoi.cles || []).forEach((cle) => prises.add(cle)));
    const choisis = [];
    for (const entree of entrees || []) {
      if ((enCours || []).length + choisis.length >= agents) break;
      const cles = pagesConcernees(texte(entree.ot_id), etat).cles;
      if (cles.every((cle) => !prises.has(cle))) choisis.push({ entree, cles });
      cles.forEach((cle) => prises.add(cle));
    }
    return choisis;
  }

  async function ecrireEntree(id, champs, avecOrdre) {
    return Donnees.modifier('wiki_journal', (lignes, outils) => {
      const ligne = lignes.find((entree) => entree.id === id);
      if (!ligne || !STATUTS_FILE.includes(texte(ligne.statut))) return false;    // traitée ailleurs entre-temps
      if (avecOrdre) ligne.ordre = String(lignes.reduce((max, entree) => Math.max(max, Number(entree.ordre) || 0), 0) + 1);
      Object.assign(ligne, champs, { traite_le: outils.maintenant() });
      return true;
    }, { journal: false });
  }

  async function traiterUne(entree, appeler, signal) {
    const etat = etatPropose();
    const donnees = donneesIngestion(texte(entree.ot_id), etat);
    const requete = Ia.requete('ingestionWiki', donnees);
    const reponse = await appeler(requete, donnees, signal);
    const modele = texte(reponse && reponse.modele);
    const essais = String((Number(entree.essais) || 0) + 1);
    let lu;
    try {
      lu = Ia.lireReponse('ingestionWiki', reponse && reponse.contenu, donnees);
    } catch (erreur) {
      if (!erreur || erreur.name !== 'IaReponseInvalide') throw erreur;
      await ecrireEntree(entree.id, { statut: 'refusée', raisons: (erreur.raisons || [erreur.message]).join('\n'), modele, essais });
      return 'refusée';
    }
    const titres = new Set(Array.from(etatPropose().values()).map((page) => Wiki.comparable(page.titre)));
    if (lu.changements.some((changement) => changement.creation && titres.has(Wiki.comparable(changement.titre)))) {
      if (Number(essais) > ESSAIS_COLLISION_MAX) {
        await ecrireEntree(entree.id, { statut: 'refusée', raisons: 'Page créée en même temps par un autre OT, ' + essais
          + ' essais.', modele, essais });
        return 'refusée';
      }
      await ecrireEntree(entree.id, { statut: 'en file', motif: MOTIF_COLLISION, modele, essais });
      return 'rejouée';
    }
    const versions = new Map(Donnees.lignes('wiki_pages').map((ligne) => [cleDeLigne(ligne), Number(ligne.version) || 0]));
    await ecrireEntree(entree.id, {
      statut: lu.rien ? 'rien à ajouter' : 'à valider', modele, essais, raisons: '', motif: '',
      anterieure: donnees.anterieure ? '1' : '0', pages: donnees.cles.join(';'),
      changements: JSON.stringify(lu.changements.map((changement) => Object.assign({ version_avant: versions.get(changement.cle) || 0 },
        changement))),
      contradictions: JSON.stringify(lu.contradictions.map((c) => Object.assign({ statut: 'ouverte' }, c))),
    }, true);
    return lu.rien ? 'rien' : 'acceptée';
  }

  /**
   * Traite la file (§20.5) : options { appeler(requete, donnees, signal) → { contenu, modele } (défaut :
   * Ia.envoyerRequete), agents (défaut SEUILS.agentsSimultanes), signal (arrêt : rien d'autre ne part, les envois en
   * cours finissent), surProgres(etat) }. → bilan { acceptees, rien, refusees, rejouees, erreur, envois: [{ ot, cles,
   * debut, fin }] } (debut et fin : rangs d'événements, pour vérifier qu'aucune page n'a deux envois en même temps).
   */
  async function traiterFile(options) {
    const opts = options || {};
    const appeler = opts.appeler || ((requete, donnees, signal) => Ia.envoyerRequete(requete, signal));
    const agents = opts.agents || SEUILS.agentsSimultanes;
    const enCours = new Map();
    const bilan = { acceptees: 0, rien: 0, refusees: 0, rejouees: 0, erreur: null, envois: [] };
    let rang = 0;
    let arret = false;
    const progres = () => {
      if (typeof opts.surProgres === 'function') {
        opts.surProgres({ enCours: enCours.size, restants: file().length - enCours.size, acceptees: bilan.acceptees,
          rien: bilan.rien, refusees: bilan.refusees, rejouees: bilan.rejouees });
      }
    };
    for (;;) {
      if (!arret && !(opts.signal && opts.signal.aborted)) {
        const enAttente = file().filter((entree) => !enCours.has(entree.id));
        prochainsEnvois(enAttente, Array.from(enCours.values()), { agents, etat: etatPropose() }).forEach(({ entree, cles }) => {
          const envoi = { ot: texte(entree.ot_id), cles, debut: ++rang, fin: null };
          bilan.envois.push(envoi);
          const suivi = { entree, cles };
          suivi.promesse = traiterUne(entree, appeler, opts.signal).then((issue) => {
            if (issue === 'acceptée') bilan.acceptees += 1;
            else if (issue === 'rien') bilan.rien += 1;
            else if (issue === 'refusée') bilan.refusees += 1;
            else bilan.rejouees += 1;
          }, (erreur) => {
            arret = true;
            if (!bilan.erreur) bilan.erreur = erreur;
          }).then(() => {
            envoi.fin = ++rang;
            enCours.delete(entree.id);
          });
          enCours.set(entree.id, suivi);
        });
      }
      progres();
      if (!enCours.size) break;
      await Promise.race(Array.from(enCours.values()).map((suivi) => suivi.promesse));
    }
    return bilan;
  }

  return {
    file, mettreEnFile, horsDuWiki, etatPropose, pagesConcernees, donneesIngestion, lireIngestion, prochainsEnvois,
    traiterFile, articlesConsommes, MOTIF_COLLISION,
  };
})());
