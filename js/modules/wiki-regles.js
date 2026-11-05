'use strict';
// Wiki (1/8) — wiki de maintenance (lot 6 refondu, ARCHITECTURE.md §20) : crée l'objet Wiki. Constantes
// (§20.1), rubriques et longueurs des textes rédigés (§20.12, refonte 2), forme comparable, vocabulaire de la
// sécurité (D97) et couche calculée de la page d'un équipement (Wiki.pageEquipement, §20.3) : des fonctions
// pures, sans écriture. Les fichiers suivants (wiki-calculs.js … wiki-journal-ecrans.js) complètent l'objet.

const Wiki = (() => {

  // Rubriques des textes rédigés, par type (§20.4 ; refonte 2, D96 révisée 2, §20.12), dans l'ordre où elles
  // s'écrivent : le texte d'une machine (« En bref », « Astuces »), celui d'un article (« À quoi il sert ») et les
  // savoir-faire, communs aux machines (D116 : « Particularités par machine », une phrase par machine, avec son lien,
  // pour ce qui change d'une machine à l'autre). Le type « mode » est retiré (une panne est une page calculée).
  const RUBRIQUES = Object.freeze({
    'équipement': Object.freeze(['En bref', 'Astuces']),
    'composant': Object.freeze(['À quoi il sert']),
    'savoir-faire': Object.freeze(['Quand le faire', 'Étapes', 'Pièces et outillage', 'Pièges', 'Particularités par machine']),
  });

  // Rubriques réécrites en entier à chaque OT (D117) : le non-retrait (D106) ne s'y applique pas, toutes leurs phrases
  // sont contrôlées comme nouvelles (wiki-texte.js) et l'en-tête de leurs longueurs le dit (wiki-ingestion.js).
  const RUBRIQUES_REECRITES = Object.freeze({ 'équipement': Object.freeze(['En bref']) });

  // Longueurs des textes rédigés (D100 révisée 2, §20.12 ; réponse 2 de Nicolas du 2026-10-23 ; « En bref » : D100
  // révisée 3, D117), par type, lues par les contrôles (wiki-texte.js) et par l'en-tête des textes envoyés à l'IA. Les
  // mots se comptent comme Wiki.mesurerTexte : mots des phrases, citations exclues (liens comptés comme leur titre).
  //  - rubriques[<rubrique>] = { phrases, mots } au plus pour une rubrique d'un texte d'équipement ou de composant :
  //    ses phrases, et les mots de ses phrases sans le nom de la rubrique (Wiki.mesurerRubriques) ; mots null : pas de
  //    limite de mots ;
  //  - page = { phrases, mots } au plus pour un savoir-faire entier (Wiki.mesurerTexte : noms des rubriques compris),
  //    découpé en sous-pages au-delà (§20.4) ; null pour un texte limité rubrique par rubrique.
  const LIMITES = Object.freeze({
    'équipement': Object.freeze({ page: null, rubriques: Object.freeze({
      'En bref': Object.freeze({ phrases: 3, mots: 60 }),
      'Astuces': Object.freeze({ phrases: 10, mots: null }),
    }) }),
    'composant': Object.freeze({ page: null, rubriques: Object.freeze({
      'À quoi il sert': Object.freeze({ phrases: 3, mots: 80 }),
    }) }),
    'savoir-faire': Object.freeze({ page: Object.freeze({ phrases: 30, mots: 600 }), rubriques: Object.freeze({}) }),
  });

  // Seuils du lot (D100, §20.1), documentés dans le guide.
  const SEUILS = Object.freeze({
    pagesCreeesMax: 3,     // pages créées par un OT ingéré (des savoir-faire, §20.12)
    phrasesMax: LIMITES['savoir-faire'].page.phrases,   // phrases d'un savoir-faire (au-delà : sous-pages, §20.4) : Wiki.LIMITES
    motsMax: LIMITES['savoir-faire'].page.mots,         // mots d'un savoir-faire (rubriques comprises, citations exclues) : idem
    relancesMax: 1,        // relance avec la raison d'une réponse refusée par les contrôles (D106 révisée, §20.5)
    pagesEnvoyeesMax: 8,   // pages jointes à une requête d'ingestion
    catalogueMax: 400,     // titres du catalogue envoyé
    agentsSimultanes: 5,   // requêtes d'ingestion en même temps (D112)
    astuceMax: 500,        // caractères de l'astuce d'un OT (D110)
    otMinimum: 5,          // cas d'un symptôme à partir desquels ses causes sont montrées (D25)
    recidiveJours: 30,     // récidive : même équipement, même cause, dans les 30 jours après la clôture
    dernieres: 10,         // dernières interventions montrées
    symptomesMax: 5,       // symptômes les plus fréquents montrés
    contradictionAncienneJours: 30,   // contradiction ouverte signalée au contrôle du wiki (D108)
    demoAValiderJours: 14, // démo : propositions des 14 derniers jours d'intervention laissées « à valider »
  });

  // ===========================================================================================
  // 1. Forme comparable, vocabulaires de la sécurité (D97) et de la nouveauté (D111) ;
  //    balisage et contrôles : wiki-texte.js
  // ===========================================================================================

  // Vocabulaire de la sécurité et de la consignation (D97), en forme comparable (sans accents ni
  // majuscules, apostrophes et ponctuation devenues des espaces). Une entrée finie par « * » est un
  // début de mot (« consign* » : consigner, consignation, consigne…) ; les autres sont des mots ou des
  // expressions entiers (« epi » ne doit pas refuser « épisodique », ni « vat » « Vatican »).
  // Un mot de la liste peut refuser à tort une puce anodine : on préfère refuser (le responsable reformule).
  const VOCABULAIRE_SECURITE = Object.freeze([
    'consign*', 'deconsign*', 'cadenas*', 'habilit*', 'electrocut*', 'lockout*',
    'vat', 'epi', 'loto', 'gant', 'gants',
    'absence de tension', 'hors tension',
    'equipement de protection', 'equipements de protection', 'lunettes de protection',
    'couper l alimentation', 'coupez l alimentation', 'couper le courant', 'coupez le courant',
    'couper l energie', 'coupez l energie', 'couper l air', 'couper la pression', 'dissiper l energie',
    'mise en securite', 'mettre en securite', 'regle de securite', 'regles de securite',
    'mesure de securite', 'mesures de securite', 'pour votre securite',
  ]);

  // Vocabulaire de la nouveauté (D111), en forme comparable, mots ou expressions entiers : une phrase qui ne
  // repose que sur un OT antérieur aux faits de sa page ne peut pas présenter son information comme la plus récente.
  const VOCABULAIRE_NOUVEAUTE = Object.freeze([
    'desormais', 'dorenavant', 'maintenant', 'actuellement', 'a present', 'aujourd hui', 'recemment',
    'dernierement', 'depuis peu', 'le plus recent', 'la plus recente', 'les plus recents', 'les plus recentes',
    'dernier', 'derniere', 'derniers', 'dernieres', 'nouvelle cause', 'nouveau remede',
  ]);

  // Raison du refus d'un texte qui touche à la sécurité (IA, à la main) : lue à l'affichage, jamais figée.
  function messageSecuriteIa() {
    return I18n.t('wiki.message_securite_ia.ia_redige_jamais_consigne');
  }
  function messageSecuriteMain() {
    return I18n.t('wiki.message_securite_main.wiki_contient_pas_consigne');
  }

  // Citation d'un OT dans une phrase : « [OT-2026-0042] ».
  const MOTIF_CITATION = /\[(OT-\d{4}-\d{4,})\]/g;

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  /** Forme comparable : minuscules, sans accents, ponctuation et apostrophes devenues des espaces. */
  function comparable(valeur) {
    return texte(valeur).normalize('NFD').replace(/\p{M}/gu, '').toLowerCase()
      .replace(/œ/g, 'oe').replace(/æ/g, 'ae').replace(/[^a-z0-9]+/g, ' ').trim();
  }

  function sansDoublon(liste) {
    return Array.from(new Set(liste));
  }

  // Identifiants des OT cités dans un texte, dans l'ordre, sans doublon.
  function citations(valeur) {
    return sansDoublon(Array.from(String(valeur || '').matchAll(MOTIF_CITATION), (m) => m[1]));
  }

  // Texte d'une phrase sans ses citations, espaces réduits.
  function sansCitations(valeur) {
    return String(valeur || '').replace(MOTIF_CITATION, ' ').replace(/\s+/g, ' ').trim();
  }

  // Nombre de mots d'un texte (citations exclues) : suites de caractères qui portent une lettre ou un chiffre.
  function nombreDeMots(valeur) {
    return sansCitations(valeur).split(' ').filter((mot) => /[\p{L}\p{N}]/u.test(mot)).length;
  }

  /**
   * Termes de VOCABULAIRE_SECURITE présents dans un texte, en forme comparable, dans l'ordre de la liste :
   * le mot trouvé pour un début de mot (« consigner » pour « consign* »), l'entrée sinon.
   */
  function termesDeSecurite(valeur) {
    const cadre = ' ' + comparable(valeur) + ' ';
    const trouves = [];
    VOCABULAIRE_SECURITE.forEach((entree) => {
      if (!entree.endsWith('*')) {
        if (cadre.includes(' ' + entree + ' ')) trouves.push(entree);
        return;
      }
      const debut = ' ' + entree.slice(0, -1);
      const position = cadre.indexOf(debut);
      if (position >= 0) trouves.push(cadre.slice(position + 1, cadre.indexOf(' ', position + 1)));
    });
    return sansDoublon(trouves);
  }

  return {
    SEUILS, RUBRIQUES, RUBRIQUES_REECRITES, LIMITES, VOCABULAIRE_SECURITE, VOCABULAIRE_NOUVEAUTE,
    get MESSAGE_SECURITE_IA() { return messageSecuriteIa(); },
    get MESSAGE_SECURITE_MAIN() { return messageSecuriteMain(); },
    comparable, citations, sansCitations, nombreDeMots, termesDeSecurite,
  };
})();

// ===========================================================================================
// 2. Couche calculée de la page d'un équipement (§20.3) : Wiki.pageEquipement — tâche T96.
// ===========================================================================================

// Tout est relu dans Donnees.lignes à chaque appel : rien n'est écrit, rien n'est gardé entre deux
// appels, aucun appel réseau. Définitions (§20.3 et précisions de T96) :
// - « cas » : OT correctif (type commençant par « correctif ») clôturé techniquement ou
//   administrativement, avec un code symptôme (règle de CausesFrequentes, §14.5, sans exiger la cause) ;
// - date d'un cas : date de la panne (Indicateurs.datePanne : DI d'origine, sinon création de l'OT) ;
// - clôture d'un OT : date de clôture technique, sinon date de fin ;
// - récidive d'un cas de cause C clôturé à l'instant J : un autre OT correctif non annulé du même
//   équipement, de cause C, dont la panne est strictement après J et au plus tard le jour J + 30 ;
// - jumeaux : autres équipements actifs (actif ≠ 0) de même marque et même modèle, comparés sans
//   espaces ni casse (règle de CausesFrequentes, reprise ici : elle y est interne).
// Les tris départagent les égalités par l'ordre des caractères (reproductible par tests/calcul_wiki.py).

Object.defineProperties(Wiki, Object.getOwnPropertyDescriptors((() => {   // garde les accesseurs get (Object.assign les figerait)

  const SEUILS = Wiki.SEUILS;
  const STATUTS_CLOTURES = ['Clôturé techniquement', 'Clôturé administrativement'];
  const NOMBRE_CAUSES = 3;            // causes montrées par symptôme, comme l'encart (D25)
  const DEMI_LARGEUR_PISTE = 0.20;    // D59 : fourchette de plus de ± 20 points → « peu de cas »
  const EXTRAIT_MAX = 160;            // caractères de l'extrait du compte rendu
  const JOURS_DE_LA_FENETRE = 365;    // pannes des 12 derniers mois : 365 jours, aujourd'hui compris
  const MILLISECONDES_PAR_JOUR = 86400000;

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  /** Ordre des caractères (pas celui de la langue) : le calcul Python de contrôle trie de même. */
  function comparer(a, b) {
    return a < b ? -1 : (a > b ? 1 : 0);
  }

  function grouper(lignes, cleDe) {
    const groupes = new Map();
    lignes.forEach((ligne) => {
      const cle = cleDe(ligne);
      if (!groupes.has(cle)) groupes.set(cle, []);
      groupes.get(cle).push(ligne);
    });
    return groupes;
  }

  /** 'AAAA-MM-JJ…' → 'AAAA-MM-JJ'. */
  function jour(valeur) {
    return texte(valeur).slice(0, 10);
  }

  /** 'AAAA-MM-JJ' + n jours (calendrier, sans heure d'été) ; '' si la date est illisible. */
  function jourPlus(jourIso, jours) {
    const morceaux = /^(\d{4})-(\d{2})-(\d{2})$/.exec(jourIso);
    if (!morceaux) return '';
    const instant = Date.UTC(Number(morceaux[1]), Number(morceaux[2]) - 1, Number(morceaux[3])) + jours * MILLISECONDES_PAR_JOUR;
    return new Date(instant).toISOString().slice(0, 10);
  }

  /** Marque ou modèle comparable : espaces et casse ignorés (« CR 10 » = « cr10 »), comme CausesFrequentes. */
  function cleComparable(valeur) {
    return texte(valeur).replace(/\s+/g, '').toLowerCase();
  }

  function estCloture(ot) {
    return STATUTS_CLOTURES.includes(texte(ot.statut));
  }

  function estCorrectif(ot) {
    return /^correctif/.test(texte(ot.type));
  }

  function estUnCas(ot) {
    return estCorrectif(ot) && estCloture(ot) && texte(ot.symptome_code) !== '';
  }

  function dateDeCloture(ot) {
    return texte(ot.date_cloture_tech) || texte(ot.date_fin);
  }

  /** Index lus une fois par appel (aucune recherche linéaire dans une boucle). */
  function contexteWiki() {
    const libelles = new Map();
    Donnees.lignes('codes_defaillance').forEach((code) => {
      const cle = texte(code.famille) + '|' + texte(code.code);
      if (!libelles.has(cle)) libelles.set(cle, texte(code.libelle));     // la première ligne fait foi
    });
    return {
      indicateurs: Indicateurs.contexte(),
      equipements: Donnees.lignes('equipements'),
      ordresParEquipement: grouper(Donnees.lignes('ordres_travail'), (ot) => texte(ot.equipement_id)),
      mouvementsParOt: grouper(Donnees.lignes('mouvements_stock'), (mouvement) => texte(mouvement.ot_id)),
      articles: new Map(Donnees.lignes('articles').map((article) => [texte(article.id), article])),
      libelles,
    };
  }

  /** Libellé d'un code de la famille (« symptôme », « cause », « remède ») ; le code s'il est inconnu ; '' sans code. */
  function libelleCode(ctx, famille, code) {
    const propre = texte(code);
    return propre ? (ctx.libelles.get(famille + '|' + propre) || propre) : '';
  }

  function dateDePanne(ctx, ot) {
    return texte(Indicateurs.datePanne(ot, ctx.indicateurs));
  }

  /** Vrai si le cas est suivi d'une récidive (définition en tête de section). */
  function estSuiviDUneRecidive(ctx, cas) {
    const cloture = dateDeCloture(cas);
    const limite = jourPlus(jour(cloture), SEUILS.recidiveJours);
    const cause = texte(cas.cause_code);
    if (!limite || !cause) return false;
    return (ctx.ordresParEquipement.get(texte(cas.equipement_id)) || []).some((autre) => {
      if (autre.id === cas.id || !estCorrectif(autre) || texte(autre.statut) === 'Annulé') return false;
      if (texte(autre.cause_code) !== cause) return false;
      const panne = dateDePanne(ctx, autre);
      return panne > cloture && jour(panne) <= limite;
    });
  }

  /** Remèdes des cas d'une cause : [{ code, libelle, fois, recidives }], les plus employés d'abord. */
  function remedesDe(ctx, casDeLaCause) {
    const avecRemede = casDeLaCause.filter((ot) => texte(ot.remede_code));
    const remedes = Array.from(grouper(avecRemede, (ot) => texte(ot.remede_code)), ([code, liste]) => ({
      code,
      libelle: libelleCode(ctx, 'remède', code),
      fois: liste.length,
      recidives: liste.filter((ot) => estSuiviDUneRecidive(ctx, ot)).length,
    }));
    return remedes.sort((a, b) => b.fois - a.fois || a.recidives - b.recidives || comparer(a.code, b.code));
  }

  /** Jours de panne d'une liste de cas, triés (les dates illisibles sont laissées de côté). */
  function joursDePanne(ctx, liste) {
    return liste.map((ot) => jour(dateDePanne(ctx, ot))).filter(Boolean).sort();
  }

  /**
   * Un symptôme : { code, libelle, cas, debut, fin, casAvecCause, suffisant, peuDeCas, causes }. Si cas ≥
   * otMinimum, les 3 causes les plus fréquentes parmi les cas qui ont une cause : { code, libelle, nombre,
   * dernierCas, fourchette (Wilson, sur casAvecCause), remedes } ; peuDeCas selon D59. Sinon causes vide.
   */
  function symptomeDetaille(ctx, symptome) {
    const avecCause = symptome.liste.filter((ot) => texte(ot.cause_code));
    const resultat = {
      code: symptome.code, libelle: symptome.libelle, cas: symptome.cas, debut: symptome.debut, fin: symptome.fin,
      casAvecCause: avecCause.length, suffisant: symptome.cas >= SEUILS.otMinimum, peuDeCas: false, causes: [],
    };
    if (!resultat.suffisant) return resultat;
    const causes = Array.from(grouper(avecCause, (ot) => texte(ot.cause_code)), ([code, liste]) => {
      const jours = joursDePanne(ctx, liste);
      return {
        code,
        libelle: libelleCode(ctx, 'cause', code),
        nombre: liste.length,
        dernierCas: jours.length ? jours[jours.length - 1] : '',
        fourchette: CausesFrequentes.fourchette(liste.length, avecCause.length),
        remedes: remedesDe(ctx, liste),
      };
    });
    causes.sort((a, b) => b.nombre - a.nombre || comparer(b.dernierCas, a.dernierCas) || comparer(a.code, b.code));
    resultat.causes = causes.slice(0, NOMBRE_CAUSES);
    resultat.peuDeCas = resultat.causes.some((cause) => cause.fourchette !== null
      && (cause.fourchette.haut - cause.fourchette.bas) / 2 > DEMI_LARGEUR_PISTE);
    return resultat;
  }

  /** Pannes habituelles d'un ou plusieurs équipements : les symptomesMax symptômes les plus fréquents. */
  function pannesDe(ctx, equipementIds) {
    const cas = [];
    equipementIds.forEach((id) => (ctx.ordresParEquipement.get(id) || []).forEach((ot) => {
      if (estUnCas(ot)) cas.push(ot);
    }));
    const symptomes = Array.from(grouper(cas, (ot) => texte(ot.symptome_code)), ([code, liste]) => {
      const jours = joursDePanne(ctx, liste);
      return {
        code, liste, libelle: libelleCode(ctx, 'symptôme', code), cas: liste.length,
        debut: jours.length ? jours[0] : '', fin: jours.length ? jours[jours.length - 1] : '',
      };
    });
    symptomes.sort((a, b) => b.cas - a.cas || comparer(b.fin, a.fin) || comparer(a.code, b.code));
    return symptomes.slice(0, SEUILS.symptomesMax).map((symptome) => symptomeDetaille(ctx, symptome));
  }

  /**
   * Pièces consommées par les OT donnés : par article, sorties moins retours. Un OT compte pour un
   * article si sa quantité nette y est positive ; derniereDate = jour de la dernière sortie de ces OT.
   * Seuls les articles de quantité nette positive sont gardés.
   */
  function piecesDe(ctx, ordres) {
    const parArticle = new Map();       // article → Map(OT → { quantite, derniereSortie })
    ordres.forEach((ot) => (ctx.mouvementsParOt.get(texte(ot.id)) || []).forEach((mouvement) => {
      const type = texte(mouvement.type);
      if (type !== 'sortie' && type !== 'retour') return;
      const articleId = texte(mouvement.article_id);
      if (!parArticle.has(articleId)) parArticle.set(articleId, new Map());
      const parOt = parArticle.get(articleId);
      if (!parOt.has(ot.id)) parOt.set(ot.id, { quantite: 0, derniereSortie: '' });
      const net = parOt.get(ot.id);
      const quantite = Donnees.nombre(mouvement.quantite) || 0;
      net.quantite += type === 'sortie' ? quantite : -quantite;
      if (type === 'sortie' && jour(mouvement.date) > net.derniereSortie) net.derniereSortie = jour(mouvement.date);
    }));
    const pieces = [];
    parArticle.forEach((parOt, articleId) => {
      const nets = Array.from(parOt.values());
      const quantite = nets.reduce((somme, net) => somme + net.quantite, 0);
      if (!(quantite > 0)) return;
      const positifs = nets.filter((net) => net.quantite > 0);
      const article = ctx.articles.get(articleId) || {};
      pieces.push({
        articleId, reference: texte(article.reference) || articleId, designation: texte(article.designation),
        quantite, nombreOt: positifs.length,
        derniereDate: positifs.reduce((plusRecente, net) => (net.derniereSortie > plusRecente ? net.derniereSortie : plusRecente), ''),
      });
    });
    return pieces.sort((a, b) => b.nombreOt - a.nombreOt || b.quantite - a.quantite || comparer(a.articleId, b.articleId));
  }

  /** Compte rendu ramené à une ligne, EXTRAIT_MAX caractères au plus (« … » final s'il est coupé). */
  function extrait(valeur) {
    const caracteres = Array.from(texte(valeur).replace(/\s+/g, ' '));
    if (caracteres.length <= EXTRAIT_MAX) return caracteres.join('');
    return I18n.t('wiki.extrait.coupe', { debut: caracteres.slice(0, EXTRAIT_MAX - 1).join('').trimEnd() });
  }

  /** Les `dernieres` OT clôturés les plus récents (date de fin, puis identifiant ; sans date de fin : en dernier). */
  function dernieresDe(ctx, clotures) {
    return clotures.slice()
      .sort((a, b) => comparer(texte(b.date_fin), texte(a.date_fin)) || comparer(texte(b.id), texte(a.id)))
      .slice(0, SEUILS.dernieres)
      .map((ot) => ({
        id: ot.id, date: texte(ot.date_fin), type: texte(ot.type), titre: texte(ot.titre),
        codes: {
          symptome: libelleCode(ctx, 'symptôme', ot.symptome_code),
          cause: libelleCode(ctx, 'cause', ot.cause_code),
          remede: libelleCode(ctx, 'remède', ot.remede_code),
        },
        extrait: extrait(ot.compte_rendu),
        dureeArret: Donnees.nombre(ot.duree_arret_h),
      }));
  }

  /** Cas dont la panne tombe dans les 365 jours qui finissent le jour de `maintenant`. */
  function pannesDesDouzeMois(ctx, ordres, aujourdhui) {
    const debut = jourPlus(aujourdhui, 1 - JOURS_DE_LA_FENETRE);
    return ordres.filter((ot) => {
      if (!estUnCas(ot)) return false;
      const jourDeLaPanne = jour(dateDePanne(ctx, ot));
      return jourDeLaPanne >= debut && jourDeLaPanne <= aujourdhui;
    }).length;
  }

  function jourDe(options) {
    return jour(options && options.maintenant) || Donnees.aujourdhui();
  }

  /**
   * Couche calculée de la page d'un équipement (§20.3), ou null s'il n'existe pas. options.maintenant : 'AAAA-MM-JJ[ HH:MM]'
   * (défaut : aujourd'hui), utilisé seulement par pannes12Mois.
   */
  function pageEquipement(equipementId, options) {
    const id = texte(equipementId);
    const equipement = Donnees.trouver('equipements', id);
    if (!equipement) return null;
    const ctx = contexteWiki();
    const ordres = ctx.ordresParEquipement.get(id) || [];
    const clotures = ordres.filter(estCloture);
    const marque = cleComparable(equipement.marque);
    const modele = cleComparable(equipement.modele);
    const jumeaux = marque && modele ? ctx.equipements.filter((autre) => texte(autre.id) !== id
      && texte(autre.actif) !== '0' && cleComparable(autre.marque) === marque && cleComparable(autre.modele) === modele)
      .sort((a, b) => comparer(texte(a.repere), texte(b.repere)) || comparer(texte(a.id), texte(b.id))) : [];
    // Consignation telle quelle (texte et document de la fiche) ; null seulement si les deux sont vides.
    const consignation = equipement.consignation === undefined ? '' : String(equipement.consignation);
    const documentConsignation = equipement.document === undefined ? '' : String(equipement.document);
    return {
      equipement: {
        id, repere: texte(equipement.repere), designation: texte(equipement.designation),
        marque: texte(equipement.marque), modele: texte(equipement.modele),
      },
      consignation: texte(consignation) || texte(documentConsignation)
        ? { texte: consignation, document: documentConsignation } : null,
      pannes: pannesDe(ctx, [id]),
      pannes12Mois: pannesDesDouzeMois(ctx, ordres, jourDe(options)),
      pieces: piecesDe(ctx, ordres),
      dernieres: dernieresDe(ctx, clotures),
      total: clotures.length,
      memeModele: jumeaux.length ? {
        equipements: jumeaux.map((autre) => ({ id: texte(autre.id), repere: texte(autre.repere) })),
        pannes: pannesDe(ctx, [id].concat(jumeaux.map((autre) => texte(autre.id)))),
      } : null,
    };
  }

  /**
   * Liste des pages (écran #/wiki) : un élément par équipement qui a au moins un OT clôturé,
   * { equipementId, repere, designation, pannes12Mois }, par pannes12Mois décroissant puis repère.
   */
  function listePages(options) {
    const ctx = contexteWiki();
    const aujourdhui = jourDe(options);
    const pages = [];
    ctx.equipements.forEach((equipement) => {
      const id = texte(equipement.id);
      const ordres = ctx.ordresParEquipement.get(id) || [];
      const clotures = ordres.filter(estCloture);
      if (!clotures.length) return;
      pages.push({
        equipementId: id, repere: texte(equipement.repere), designation: texte(equipement.designation),
        pannes12Mois: pannesDesDouzeMois(ctx, ordres, aujourdhui),
      });
    });
    return pages.sort((a, b) => b.pannes12Mois - a.pannes12Mois || comparer(a.repere, b.repere)
      || comparer(a.equipementId, b.equipementId));
  }

  return {
    pageEquipement, listePages,
    // Mentions des causes fréquentes, lues dans la langue du moment (accesseurs : jamais recopiées au chargement).
    get MENTION_STATISTIQUE() { return CausesFrequentes.MENTION; },
    get MENTION_PISTE() { return CausesFrequentes.MENTION_PISTE; },
  };
})()));
