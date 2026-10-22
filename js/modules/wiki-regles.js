'use strict';
// Wiki (1/5) — wiki de maintenance (lot 6, ARCHITECTURE.md §20) : crée l'objet Wiki. Constantes, forme
// et contrôles du texte d'une synthèse [IA] (§20.4) et couche calculée d'une page (Wiki.page, §20.3) :
// des fonctions pures, sans écriture. Les fichiers suivants (wiki-recherche.js … wiki-ecrans.js)
// complètent l'objet.

const Wiki = (() => {

  // Seuils du lot (D100), documentés dans le guide.
  const SEUILS = Object.freeze({
    otMinimum: 5,          // OT clôturés à partir desquels une synthèse peut être proposée
    otEnvoyesMax: 40,      // OT envoyés à l'IA au plus (les plus récents)
    pucesMax: 6,           // puces d'une synthèse
    motsMax: 150,          // mots d'une synthèse (citations exclues)
    recidiveJours: 30,     // récidive : même équipement, même cause, dans les 30 jours après la clôture
    dernieres: 10,         // dernières interventions montrées
    symptomesMax: 5,       // symptômes les plus fréquents montrés
  });

  // ===========================================================================================
  // 1. Forme et contrôles du texte d'une synthèse (§20.4, D97)
  // ===========================================================================================

  // Rubriques fixes, dans l'ordre où elles s'écrivent.
  const RUBRIQUES = Object.freeze(['Ce qui revient', 'Ce qui a réglé le problème', 'À surveiller']);

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

  const MESSAGE_SECURITE_IA = 'L\'IA ne rédige jamais de consigne de sécurité : voir la consignation de l\'équipement';
  const MESSAGE_SECURITE_MAIN = 'Le bloc [IA] ne contient pas de consigne de sécurité : elle se saisit dans la '
    + 'consignation de l\'équipement';

  // Citation d'un OT dans une puce : « [OT-2026-0042] ».
  const MOTIF_CITATION = /\[(OT-\d{4}-\d{4,})\]/g;
  // Début d'une puce : tiret, astérisque ou puce typographique, suivi d'un espace.
  const MOTIF_DEBUT_PUCE = /^[-*•]\s+/;

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

  // Texte d'une puce sans ses citations, espaces réduits.
  function sansCitations(valeur) {
    return String(valeur || '').replace(MOTIF_CITATION, ' ').replace(/\s+/g, ' ').trim();
  }

  // Nombre de mots d'un texte (citations exclues) : suites de caractères qui portent une lettre ou un chiffre.
  function nombreDeMots(valeur) {
    return sansCitations(valeur).split(' ').filter((mot) => /[\p{L}\p{N}]/u.test(mot)).length;
  }

  // Rubrique reconnue dans une ligne (casse, accents, « : » final et ponctuation ignorés), ou null.
  function rubriqueDe(ligne) {
    const cle = comparable(ligne);
    return RUBRIQUES.find((rubrique) => comparable(rubrique) === cle) || null;
  }

  /**
   * Puces → texte enregistré (champ `texte`) : les rubriques non vides dans l'ordre de RUBRIQUES, chacune
   * sur sa ligne, suivie de ses puces « - <texte> [OT-…] [OT-…] ». Les citations écrites dans le texte
   * d'une puce sont reportées en fin de ligne avec celles de `ot`.
   */
  function texteDeSynthese(puces) {
    const lignes = [];
    RUBRIQUES.forEach((rubrique) => {
      const siennes = (puces || []).filter((puce) => puce && puce.rubrique === rubrique);
      if (!siennes.length) return;
      lignes.push(rubrique);
      siennes.forEach((puce) => {
        const ot = sansDoublon(citations(puce.texte).concat((puce.ot || []).map(texte).filter(Boolean)));
        lignes.push(['-', sansCitations(puce.texte)].concat(ot.map((id) => '[' + id + ']')).join(' '));
      });
    });
    return lignes.join('\n');
  }

  /**
   * Texte enregistré → { puces: [{ rubrique, texte, ot }], horsForme: [numéros de ligne] } : une ligne est
   * un titre de rubrique, une puce (sous une rubrique) ou vide ; toute autre ligne est « hors forme ».
   */
  function lireSynthese(valeur) {
    const puces = [];
    const horsForme = [];
    let rubrique = null;
    String(valeur || '').replace(/\r\n?/g, '\n').split('\n').forEach((ligne, rang) => {
      const propre = ligne.trim();
      if (!propre) return;
      const titre = rubriqueDe(propre);
      if (titre) { rubrique = titre; return; }
      if (rubrique && MOTIF_DEBUT_PUCE.test(propre)) {
        const contenu = propre.replace(MOTIF_DEBUT_PUCE, '');
        puces.push({ rubrique, texte: sansCitations(contenu), ot: citations(contenu) });
        return;
      }
      horsForme.push(rang + 1);
    });
    return { puces, horsForme };
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

  /**
   * Contrôles du §20.4, pour une réponse de l'IA mise en forme (origine 'ia') comme pour un texte corrigé
   * à la main (origine 'main') : forme, 1 à pucesMax puces, motsMax mots au plus (citations exclues), au
   * moins un OT cité par puce, chaque OT cité parmi `otPermis`, aucun terme du vocabulaire de la
   * sécurité. → { ok, raisons: [texte], puces, otCites }.
   */
  function controlerSynthese(valeur, otPermis, options) {
    const origine = options && options.origine === 'main' ? 'main' : 'ia';
    const lu = lireSynthese(valeur);
    const raisons = [];
    if (lu.horsForme.length) {
      raisons.push((lu.horsForme.length > 1 ? 'Lignes ' : 'Ligne ') + lu.horsForme.join(', ')
        + ' hors de la forme : chaque ligne est un titre de rubrique (« ' + RUBRIQUES.join(' », « ')
        + ' ») ou une puce « - … » qui cite ses OT entre crochets.');
    }
    if (!lu.puces.length) raisons.push('Aucune puce : la synthèse est vide.');
    if (lu.puces.length > SEUILS.pucesMax) {
      raisons.push(lu.puces.length + ' puces : ' + SEUILS.pucesMax + ' au plus.');
    }
    const mots = lu.puces.reduce((total, puce) => total + nombreDeMots(puce.texte), 0);
    if (mots > SEUILS.motsMax) raisons.push(mots + ' mots : ' + SEUILS.motsMax + ' au plus (citations non comptées).');
    lu.puces.forEach((puce, rang) => {
      if (!puce.texte) raisons.push('Puce ' + (rang + 1) + ' : elle est vide.');
      else if (!puce.ot.length) raisons.push('Puce ' + (rang + 1) + ' : elle ne cite aucun OT (« ' + puce.texte.slice(0, 60) + ' »).');
    });
    const otCites = sansDoublon([].concat(...lu.puces.map((puce) => puce.ot)));
    const permis = new Set((otPermis || []).map(texte));
    const inconnus = otCites.filter((id) => !permis.has(id));
    if (inconnus.length) {
      raisons.push((inconnus.length > 1 ? 'OT cités absents des OT ' : 'OT cité absent des OT ')
        + (origine === 'ia' ? 'envoyés à l\'IA' : 'de cet équipement') + ' : ' + inconnus.join(', ') + '.');
    }
    const termes = termesDeSecurite(valeur);
    if (termes.length) {
      raisons.push((origine === 'ia' ? MESSAGE_SECURITE_IA : MESSAGE_SECURITE_MAIN) + ' (« ' + termes.join(' », « ') + ' »).');
    }
    return { ok: raisons.length === 0, raisons, puces: lu.puces, otCites };
  }

  return {
    SEUILS, RUBRIQUES, VOCABULAIRE_SECURITE, MESSAGE_SECURITE_IA, MESSAGE_SECURITE_MAIN,
    comparable, citations, nombreDeMots, texteDeSynthese, lireSynthese, termesDeSecurite, controlerSynthese,
  };
})();

// ===========================================================================================
// 2. Couche calculée d'une page (§20.3) : Wiki.page — tâche T96, ajoutée sous ce bloc.
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

Object.assign(Wiki, (() => {

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
      synthesesParEquipement: grouper(Donnees.lignes('wiki_syntheses'), (synthese) => texte(synthese.equipement_id)),
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
    return caracteres.slice(0, EXTRAIT_MAX - 1).join('').trimEnd() + '…';
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

  function plusRecenteDabord(a, b) {
    return comparer(texte(b.date_proposition), texte(a.date_proposition)) || comparer(texte(b.id), texte(a.id));
  }

  /**
   * Synthèse courante (la plus récente non « remplacée ») et son état : aucune, a_valider, validee ou
   * a_revoir (validée, et `depuis` > 0 : elle reste validée). depuis = OT clôturés de l'équipement après
   * date_proposition (date de clôture) et absents de ot_sources. → { synthese, etat, remplacees }.
   */
  function etatSynthese(ctx, equipementId, clotures) {
    const syntheses = ctx.synthesesParEquipement.get(equipementId) || [];
    const remplacees = syntheses.filter((s) => texte(s.statut) === 'remplacée').sort(plusRecenteDabord);
    const courante = syntheses.filter((s) => texte(s.statut) !== 'remplacée').sort(plusRecenteDabord)[0];
    const copies = remplacees.map((s) => Object.assign({}, s));
    if (!courante) return { synthese: null, etat: 'aucune', remplacees: copies };
    const sources = new Set(texte(courante.ot_sources).split(';').map(texte).filter(Boolean));
    const proposee = texte(courante.date_proposition);
    const depuis = clotures.filter((ot) => !sources.has(texte(ot.id)) && dateDeCloture(ot) > proposee).length;
    const etat = texte(courante.statut) !== 'validée' ? 'a_valider' : (depuis > 0 ? 'a_revoir' : 'validee');
    return { synthese: Object.assign({}, courante, { etat, depuis }), etat, remplacees: copies };
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
   * Page d'un équipement (§20.3), ou null s'il n'existe pas. options.maintenant : 'AAAA-MM-JJ[ HH:MM]'
   * (défaut : aujourd'hui), utilisé seulement par pannes12Mois.
   */
  function page(equipementId, options) {
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
    const synthese = etatSynthese(ctx, id, clotures);
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
      synthese: synthese.synthese,
      etat: synthese.etat,
      remplacees: synthese.remplacees,
      peutProposer: clotures.length >= SEUILS.otMinimum,
    };
  }

  /**
   * Liste des pages (écran #/wiki) : un élément par équipement qui a au moins un OT clôturé,
   * { equipementId, repere, designation, pannes12Mois, etat }, par pannes12Mois décroissant puis repère.
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
        pannes12Mois: pannesDesDouzeMois(ctx, ordres, aujourdhui), etat: etatSynthese(ctx, id, clotures).etat,
      });
    });
    return pages.sort((a, b) => b.pannes12Mois - a.pannes12Mois || comparer(a.repere, b.repere)
      || comparer(a.equipementId, b.equipementId));
  }

  return { page, listePages, MENTION_STATISTIQUE: CausesFrequentes.MENTION, MENTION_PISTE: CausesFrequentes.MENTION_PISTE };
})());
