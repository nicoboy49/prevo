'use strict';
// Wiki (2/5) — recherche dans l'historique, sans IA (lot 6, ARCHITECTURE.md §20.6, décision D99 a) :
// index des OT clôturés (avec la DI d'origine et les libellés de leurs codes) et des synthèses
// validées, mots comparables, lexique du dépannage, classement BM25, portées équipement → même marque
// et modèle → parc. Complète l'objet Wiki (créé par wiki-regles.js).
//
// Tout se passe dans la page : aucune requête réseau, aucune écriture. L'index est construit à la
// première recherche et oublié dès qu'une table qu'il lit change (Donnees.evenements) ; il est aussi
// refait quand Donnees a relu ces tables sans événement (Donnees.initialiser puis chargerTout).
//
// Précisions au contrat (§20.6) :
//  - `extrait` est du TEXTE BRUT ; chaque résultat porte aussi `mots` (les formes trouvées dans le
//    document) : Wiki.surligner(extrait, mots) en fait un fragment UI.html, <mark> autour des mots et
//    tout le reste échappé (jamais de HTML venu des données) ;
//  - chaque résultat porte aussi `repere` (repère de l'équipement) ; une synthèse porte `syntheseId`
//    et le titre « [IA] Synthèse validée — <repère> <désignation> » ; `cause` et `remede` sont les
//    libellés des codes (vides pour une synthèse) ; `date` = AAAA-MM-JJ (fin des travaux, sinon
//    clôture technique, sinon création ; pour une synthèse : validation, sinon proposition) ;
//  - avec un équipement, les trois portées sont toujours rendues dans l'ordre, même vides ;
//  - « même marque et modèle » : comparaison sans casse ni espaces, comme CausesFrequentes (§14.5),
//    équipements actifs ou non, l'équipement lui-même exclu ; marque ou modèle vide → portée vide ;
//  - une expression du lexique (« ne demarre pas », « manque de pression ») est reconnue mot à mot,
//    avant le retrait des mots vides, et compte comme un mot de plus dans le document.

Object.assign(Wiki, (() => {

  // ===========================================================================================
  // Réglages, mots vides et lexique (§20.6)
  // ===========================================================================================

  const RECHERCHE = Object.freeze({
    k1: 1.2,                 // BM25 : saturation de la fréquence d'un mot dans un document
    b: 0.75,                 // BM25 : poids de la longueur du document
    poidsEquivalent: 0.7,    // un équivalent du lexique compte pour 0,7 d'un mot de la requête
    limite: 10,              // résultats par portée, par défaut
    longueurExtrait: 160,    // caractères de l'extrait au plus (points de suspension compris)
    lettresMinimum: 2,       // un mot plus court est ignoré
  });

  const STATUTS_CLOTURES = ['Clôturé techniquement', 'Clôturé administrativement'];
  const STATUT_VALIDEE = 'validée';
  // Tables lues par l'index : il est refait quand l'une d'elles change.
  const TABLES_INDEXEES = ['ordres_travail', 'demandes', 'codes_defaillance', 'wiki_syntheses'];
  const AVANT_LE_MOT = 50;   // caractères gardés, dans l'extrait, avant le premier mot trouvé

  // Mots vides, en forme comparable (minuscules, sans accents) : retirés des textes et des requêtes.
  // « avant », « arriere », « haut », « bas » ne le sont pas : ils situent une pièce (roulement avant).
  const MOTS_VIDES = Object.freeze([
    'au', 'aux', 'avec', 'ce', 'ces', 'cet', 'cette', 'ca', 'cela', 'ceci', 'celui', 'celle', 'ceux',
    'dans', 'de', 'des', 'du', 'en', 'et', 'ou', 'il', 'ils', 'elle', 'elles', 'je', 'tu', 'nous', 'vous',
    'on', 'la', 'le', 'les', 'leur', 'leurs', 'lui', 'ma', 'mon', 'mes', 'ta', 'ton', 'tes', 'sa', 'son',
    'ses', 'notre', 'nos', 'votre', 'vos', 'me', 'te', 'se', 'ne', 'pas', 'plus', 'par', 'pour', 'sur',
    'sous', 'sans', 'qui', 'que', 'qu', 'quoi', 'dont', 'quand', 'comme', 'mais', 'donc', 'car', 'ni',
    'si', 'un', 'une', 'est', 'sont', 'etait', 'ete', 'etre', 'ai', 'as', 'avait', 'avoir', 'eu', 'fait',
    'faire', 'fais', 'font', 'tres', 'tout', 'tous', 'toute', 'toutes', 'aussi', 'encore', 'deja', 'bien',
    'peu', 'chez', 'vers', 'lors', 'depuis', 'jusqu', 'puis', 'alors', 'quel', 'quelle', 'quels',
    'quelles', 'ici', 'meme', 'autre', 'autres', 'entre',
  ]);

  // Lexique du dépannage (§20.6, listé dans le guide) : dans un groupe, les mots sont équivalents
  // pour la recherche ; un mot du lexique cherche aussi ses équivalents (poids 0,7).
  const LEXIQUE = Object.freeze([
    ['bruit', 'grincement', 'grince', 'claquement', 'claque', 'cognement', 'cogne', 'sifflement', 'siffle'],
    ['fuite', 'fuit', 'suintement', 'suinte', 'goutte'],
    ['chauffe', 'surchauffe', 'chaud', 'temperature'],
    ['vibration', 'vibre', 'balourd'],
    ['bloque', 'blocage', 'coince', 'grippe'],
    ['casse', 'rupture', 'fissure'],
    ['arret', 'stoppe', 'ne demarre pas'],
    ['pression', 'manque de pression'],
    ['usure', 'use'],
  ].map((groupe) => Object.freeze(groupe)));

  const motsVides = new Set(MOTS_VIDES);

  // ===========================================================================================
  // Mots comparables
  // ===========================================================================================

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  /** Forme comparable : minuscules, sans accents, tout ce qui n'est ni lettre ni chiffre → espace. */
  function comparable(valeur) {
    return texte(valeur).normalize('NFD').replace(/\p{M}+/gu, '').toLowerCase()
      .replace(/œ/g, 'oe').replace(/æ/g, 'ae')
      .replace(/[^a-z0-9]+/g, ' ').trim();
  }

  /**
   * Forme d'un mot comparable pour l'index : null s'il a moins de 2 lettres ou s'il est vide de sens ;
   * pluriel simple retiré (« s » ou « x » final, au-delà de 3 lettres : « fuites » → « fuite »).
   */
  function formeDuMot(mot) {
    if (mot.length < RECHERCHE.lettresMinimum || motsVides.has(mot)) return null;
    return mot.length > 3 && (mot.endsWith('s') || mot.endsWith('x')) ? mot.slice(0, -1) : mot;
  }

  /** Clé d'une entrée du lexique : la forme du mot, ou l'expression comparable (plusieurs mots). */
  function cleDuLexique(entree) {
    const forme = comparable(entree);
    return forme.includes(' ') ? forme : formeDuMot(forme);
  }

  const GROUPES = LEXIQUE.map((groupe) => groupe.map(cleDuLexique));   // clés de chaque groupe
  const GROUPE_DE = new Map();                                         // clé → numéro du groupe
  const EXPRESSIONS = [];                                              // [{ cle, mots }]
  GROUPES.forEach((cles, numero) => cles.forEach((cle) => {
    GROUPE_DE.set(cle, numero);
    if (cle.includes(' ')) EXPRESSIONS.push({ cle, mots: cle.split(' ') });
  }));

  /** Vrai si l'expression commence au mot `position` de la liste de mots comparables. */
  function expressionA(expression, mots, position) {
    if (position + expression.mots.length > mots.length) return false;
    return expression.mots.every((mot, decalage) => mots[position + decalage] === mot);
  }

  /**
   * Mots d'un texte pour l'index et les requêtes : formes des mots (dans l'ordre), puis une entrée
   * par expression du lexique trouvée (« ne demarre pas »).
   */
  function termes(valeur) {
    const forme = comparable(valeur);
    if (!forme) return [];
    const bruts = forme.split(' ');
    const resultat = [];
    bruts.forEach((mot) => {
      const motIndexe = formeDuMot(mot);
      if (motIndexe) resultat.push(motIndexe);
    });
    EXPRESSIONS.forEach((expression) => {
      bruts.forEach((mot, position) => {
        if (mot === expression.mots[0] && expressionA(expression, bruts, position)) resultat.push(expression.cle);
      });
    });
    return resultat;
  }

  /**
   * Mots d'une requête, sans doublon, et leurs équivalents du lexique :
   * { mots, equivalents, poids: Map(mot → 1 ou poidsEquivalent) }. Un mot tapé garde le poids 1 même
   * s'il est aussi l'équivalent d'un autre mot tapé.
   */
  function termesDeLaRequete(requete) {
    const mots = Array.from(new Set(termes(requete)));
    const poids = new Map(mots.map((mot) => [mot, 1]));
    const equivalents = [];
    mots.forEach((mot) => {
      if (!GROUPE_DE.has(mot)) return;
      GROUPES[GROUPE_DE.get(mot)].forEach((cle) => {
        if (poids.has(cle)) return;
        poids.set(cle, RECHERCHE.poidsEquivalent);
        equivalents.push(cle);
      });
    });
    return { mots, equivalents, poids };
  }

  // ===========================================================================================
  // Documents et index
  // ===========================================================================================

  let index = null;          // { sources, documents, postings, longueurMoyenne } ou null (à construire)
  let constructions = 0;     // nombre d'index construits depuis l'ouverture (suivi, tests)

  /** Date d'un OT (AAAA-MM-JJ) : fin des travaux, sinon clôture technique, sinon création. */
  function dateOt(ot) {
    return (texte(ot.date_fin) || texte(ot.date_cloture_tech) || texte(ot.date_creation)).slice(0, 10);
  }

  /**
   * DI d'origine de chaque OT, même règle que Indicateurs.contexte (D35) : celle que l'OT désigne
   * (di_id) ; à défaut, parmi les DI qui pointent vers lui (ot_id), la plus ancienne acceptée.
   * → Map identifiant d'OT → DI.
   */
  function demandesDOrigine(ordres, demandes) {
    const parId = new Map(demandes.map((di) => [di.id, di]));
    const accepteeParOt = new Map();
    demandes.forEach((di) => {
      const otId = texte(di.ot_id);
      if (!otId || texte(di.statut) !== 'Acceptée') return;
      const premiere = accepteeParOt.get(otId);
      if (!premiere || texte(di.date_heure) < texte(premiere.date_heure)) accepteeParOt.set(otId, di);
    });
    const origines = new Map();
    ordres.forEach((ot) => {
      const origine = parId.get(texte(ot.di_id)) || accepteeParOt.get(ot.id);
      if (origine) origines.set(ot.id, origine);
    });
    return origines;
  }

  /** Libellé d'un code de défaillance d'une famille (le premier trouvé), sinon le code ; '' sans code. */
  function lecteurDeLibelles(codes) {
    const libelles = new Map();
    codes.forEach((ligne) => {
      const cle = texte(ligne.famille) + '|' + texte(ligne.code);
      if (!libelles.has(cle)) libelles.set(cle, texte(ligne.libelle));
    });
    return (famille, code) => {
      const valeur = texte(code);
      return valeur ? libelles.get(famille + '|' + valeur) || valeur : '';
    };
  }

  /**
   * Un document par OT clôturé. `champs` : textes indexés ; `corps` : textes d'où l'extrait est
   * tiré, dans cet ordre (compte rendu, travail à faire, symptôme et description de la DI).
   */
  function documentsDesOt(ordres, demandes, libelle) {
    const origines = demandesDOrigine(ordres, demandes);
    const documents = [];
    ordres.forEach((ot) => {
      if (!STATUTS_CLOTURES.includes(texte(ot.statut))) return;
      const di = origines.get(ot.id) || {};
      const cause = libelle('cause', ot.cause_code);
      const remede = libelle('remède', ot.remede_code);
      const corps = [ot.compte_rendu, ot.travail_a_faire, di.symptome, di.description];
      documents.push({
        type: 'ot', id: ot.id, equipementId: texte(ot.equipement_id), date: dateOt(ot), titre: texte(ot.titre),
        cause, remede, corps,
        champs: [ot.titre, libelle('symptôme', ot.symptome_code), cause, remede].concat(corps),
      });
    });
    return documents;
  }

  /** Un document par synthèse « validée » (ni « à valider » ni « remplacée ») : il mène à la page. */
  function documentsDesSyntheses(syntheses) {
    return syntheses.filter((synthese) => texte(synthese.statut) === STATUT_VALIDEE).map((synthese) => ({
      type: 'synthese', id: synthese.id, equipementId: texte(synthese.equipement_id),
      date: (texte(synthese.date_validation) || texte(synthese.date_proposition)).slice(0, 10),
      titre: '', cause: '', remede: '', corps: [synthese.texte], champs: [synthese.texte],
    }));
  }

  /**
   * Index inversé : pour chaque mot, la liste à plat [numéro de document, fréquence, …] ; longueur de
   * chaque document (nombre de mots indexés) et longueur moyenne (BM25).
   */
  function construireIndex() {
    const sources = {};
    TABLES_INDEXEES.forEach((nom) => { sources[nom] = Donnees.lignes(nom); });
    const libelle = lecteurDeLibelles(sources.codes_defaillance);
    const documents = documentsDesOt(sources.ordres_travail, sources.demandes, libelle)
      .concat(documentsDesSyntheses(sources.wiki_syntheses));
    const postings = new Map();
    let longueurTotale = 0;
    documents.forEach((documentIndexe, numero) => {
      const frequences = new Map();
      let longueur = 0;
      documentIndexe.champs.forEach((champ) => termes(champ).forEach((mot) => {
        frequences.set(mot, (frequences.get(mot) || 0) + 1);
        longueur += 1;
      }));
      frequences.forEach((frequence, mot) => {
        if (!postings.has(mot)) postings.set(mot, []);
        postings.get(mot).push(numero, frequence);
      });
      documentIndexe.longueur = longueur;
      documentIndexe.champs = null;                 // inutile après l'indexation
      longueurTotale += longueur;
    });
    constructions += 1;
    return { sources, documents, postings, longueurMoyenne: documents.length ? longueurTotale / documents.length : 0 };
  }

  /** Même table qu'à la construction (Donnees rend un nouveau tableau à chaque relecture ou écriture). */
  function memeTable(avant, maintenant) {
    return avant === maintenant || (avant.length === 0 && maintenant.length === 0);
  }

  /** L'index, construit à la première recherche et refait si une table indexée a été relue. */
  function indexAJour() {
    const aJour = index !== null
      && TABLES_INDEXEES.every((nom) => memeTable(index.sources[nom], Donnees.lignes(nom)));
    if (!aJour) index = construireIndex();
    return index;
  }

  // Une table indexée change (ici ou sur un autre poste) : l'index sera refait à la prochaine recherche.
  Donnees.evenements.addEventListener('changement', (evenement) => {
    const tables = evenement.detail && evenement.detail.tables;
    if (!Array.isArray(tables) || tables.some((nom) => TABLES_INDEXEES.includes(nom))) index = null;
  });

  // ===========================================================================================
  // Classement (BM25) et portées
  // ===========================================================================================

  /**
   * Documents qui contiennent au moins un mot cherché : [{ documentIndexe, score, mots }], score BM25
   * (k1, b) où chaque mot compte selon son poids (1, ou 0,7 pour un équivalent du lexique).
   */
  function classer(indexCourant, poids) {
    const { k1, b } = RECHERCHE;
    const nombreDocuments = indexCourant.documents.length;
    const trouves = new Map();
    poids.forEach((poidsDuMot, mot) => {
      const liste = indexCourant.postings.get(mot);
      if (!liste) return;
      const documentsAvecLeMot = liste.length / 2;
      const idf = Math.log(1 + (nombreDocuments - documentsAvecLeMot + 0.5) / (documentsAvecLeMot + 0.5));
      for (let rang = 0; rang < liste.length; rang += 2) {
        const documentIndexe = indexCourant.documents[liste[rang]];
        const frequence = liste[rang + 1];
        const normalisation = k1 * (1 - b + b * documentIndexe.longueur / indexCourant.longueurMoyenne);
        if (!trouves.has(liste[rang])) trouves.set(liste[rang], { documentIndexe, score: 0, mots: [] });
        const trouve = trouves.get(liste[rang]);
        trouve.score += poidsDuMot * idf * (frequence * (k1 + 1)) / (frequence + normalisation);
        trouve.mots.push(mot);
      }
    });
    return Array.from(trouves.values());
  }

  /** Marque ou modèle comparable : casse et espaces ignorés (« CR 10 » = « cr10 »), comme §14.5. */
  function cleMarqueModele(valeur) {
    return texte(valeur).replace(/\s+/g, '').toLowerCase();
  }

  /** Autres équipements de même marque et modèle (actifs ou non) ; vide si l'un des deux manque. */
  function equipementsDeMemeModele(equipement) {
    if (!equipement) return new Set();
    const marque = cleMarqueModele(equipement.marque);
    const modele = cleMarqueModele(equipement.modele);
    if (!marque || !modele) return new Set();
    return new Set(Donnees.lignes('equipements')
      .filter((autre) => autre.id !== equipement.id
        && cleMarqueModele(autre.marque) === marque && cleMarqueModele(autre.modele) === modele)
      .map((autre) => autre.id));
  }

  /** Portées, dans l'ordre : sans équipement, le parc seul ; sinon équipement, même modèle, reste du parc. */
  function porteesDe(equipementId) {
    if (!equipementId) return [{ portee: 'parc', libelle: 'Dans tout le parc', contient: () => true }];
    const equipement = Donnees.trouver('equipements', equipementId);
    const jumeaux = equipementsDeMemeModele(equipement);
    const precision = jumeaux.size ? ' (' + texte(equipement.marque) + ' ' + texte(equipement.modele) + ')' : '';
    return [
      { portee: 'equipement', libelle: 'Sur cet équipement', contient: (id) => id === equipementId },
      { portee: 'modele', libelle: 'Même marque et modèle' + precision, contient: (id) => jumeaux.has(id) },
      { portee: 'parc', libelle: 'Ailleurs dans le parc', contient: () => true },
    ];
  }

  /** Meilleur score d'abord, puis le plus récent, puis l'identifiant. */
  function comparerTrouves(a, b) {
    if (b.score !== a.score) return b.score - a.score;
    if (a.documentIndexe.date !== b.documentIndexe.date) return a.documentIndexe.date < b.documentIndexe.date ? 1 : -1;
    return a.documentIndexe.id.localeCompare(b.documentIndexe.id, 'fr', { numeric: true });
  }

  // ===========================================================================================
  // Extrait et surlignage
  // ===========================================================================================

  /**
   * Mots d'un texte d'origine avec leur place : [{ debut, fin, brut (comparable), forme (ou null) }].
   * Un mot d'origine qui donne plusieurs mots comparables (lettre hors de a-z) les garde à sa place.
   */
  function motsAvecPlaces(valeur) {
    const mots = [];
    const motif = /[\p{L}\p{M}\p{N}]+/gu;
    let trouve = motif.exec(valeur);
    while (trouve !== null) {
      const debut = trouve.index;
      const fin = debut + trouve[0].length;
      comparable(trouve[0]).split(' ').filter(Boolean)
        .forEach((brut) => mots.push({ debut, fin, brut, forme: formeDuMot(brut) }));
      trouve = motif.exec(valeur);
    }
    return mots;
  }

  /** Passages [debut, fin] d'un texte où paraît un mot cherché (forme ou expression), triés, fusionnés. */
  function passagesTrouves(valeur, cherches) {
    const mots = motsAvecPlaces(valeur);
    const bruts = mots.map((mot) => mot.brut);
    const passages = [];
    mots.forEach((mot, position) => {
      if (mot.forme && cherches.has(mot.forme)) passages.push([mot.debut, mot.fin]);
      EXPRESSIONS.forEach((expression) => {
        if (cherches.has(expression.cle) && expressionA(expression, bruts, position)) {
          passages.push([mot.debut, mots[position + expression.mots.length - 1].fin]);
        }
      });
    });
    passages.sort((a, b) => a[0] - b[0] || b[1] - a[1]);
    const fusionnes = [];
    passages.forEach(([debut, fin]) => {
      const dernier = fusionnes[fusionnes.length - 1];
      if (dernier && debut <= dernier[1]) dernier[1] = Math.max(dernier[1], fin);
      else fusionnes.push([debut, fin]);
    });
    return fusionnes;
  }

  /**
   * Au plus `longueurExtrait` caractères d'un texte (espaces simplifiés), autour du mot trouvé entre
   * debutMot et finMot : AVANT_LE_MOT caractères avant lui, coupé aux espaces, « … » aux coupures.
   */
  function couper(valeur, debutMot, finMot) {
    const longueur = RECHERCHE.longueurExtrait;
    if (valeur.length <= longueur) return valeur;
    let debut = Math.max(0, debutMot - AVANT_LE_MOT);
    let fin = Math.min(valeur.length, debut + longueur - 2);           // place des deux « … »
    if (fin === valeur.length) debut = Math.max(0, fin - (longueur - 1));
    if (debut > 0) {
      const espace = valeur.indexOf(' ', debut);
      if (espace !== -1 && espace < debutMot) debut = espace + 1;
    }
    if (fin < valeur.length) {
      const espace = valeur.lastIndexOf(' ', fin);
      if (espace > Math.max(debut, finMot)) fin = espace;
    }
    return (debut > 0 ? '…' : '') + valeur.slice(debut, fin).trim() + (fin < valeur.length ? '…' : '');
  }

  /**
   * Extrait (texte brut) : dans le premier texte du corps qui contient un mot trouvé, autour de sa
   * première apparition ; sinon (mot trouvé dans le titre ou un code seulement) le début du corps.
   */
  function extraitDe(corps, mots) {
    const cherches = new Set(mots);
    const textes = corps.map((champ) => texte(champ).replace(/\s+/g, ' ')).filter(Boolean);
    for (const valeur of textes) {
      const passages = passagesTrouves(valeur, cherches);
      if (passages.length) return couper(valeur, passages[0][0], passages[0][1]);
    }
    return textes.length ? couper(textes[0], 0, 0) : '';
  }

  /**
   * Fragment UI.html d'un extrait : <mark> autour des mots cherchés (formes rendues par la recherche,
   * ou mots tels que tapés), tout le reste échappé. Jamais de HTML venu des données.
   */
  function surligner(extrait, mots) {
    const valeur = extrait === null || extrait === undefined ? '' : String(extrait);
    const cherches = new Set();
    (Array.isArray(mots) ? mots : [mots]).forEach((mot) => {
      const forme = comparable(mot);
      if (!forme) return;
      cherches.add(forme);                                // forme déjà rendue, ou expression
      if (!forme.includes(' ')) {
        const motIndexe = formeDuMot(forme);              // mot tel que tapé (« Fuites »)
        if (motIndexe) cherches.add(motIndexe);
      }
    });
    const morceaux = [];
    let curseur = 0;
    passagesTrouves(valeur, cherches).forEach(([debut, fin]) => {
      morceaux.push(valeur.slice(curseur, debut), UI.html`<mark>${valeur.slice(debut, fin)}</mark>`);
      curseur = fin;
    });
    morceaux.push(valeur.slice(curseur));
    return UI.html`${morceaux}`;
  }

  // ===========================================================================================
  // Recherche
  // ===========================================================================================

  /** Un résultat rendu (§20.6, avec les précisions en tête de fichier). */
  function enResultat(trouve) {
    const source = trouve.documentIndexe;
    const equipement = Donnees.trouver('equipements', source.equipementId);
    const repere = equipement ? texte(equipement.repere) : '';
    const commun = {
      equipementId: source.equipementId, repere, date: source.date, cause: source.cause, remede: source.remede,
      extrait: extraitDe(source.corps, trouve.mots), mots: trouve.mots.slice(), score: trouve.score,
    };
    if (source.type === 'ot') return Object.assign({ type: 'ot', otId: source.id, titre: source.titre }, commun);
    const nom = [repere, equipement ? texte(equipement.designation) : ''].filter(Boolean).join(' ');
    return Object.assign({ type: 'synthese', syntheseId: source.id,
      titre: '[IA] Synthèse validée' + (nom ? ' — ' + nom : '') }, commun);
  }

  /**
   * Recherche dans l'historique (§20.6) : texte libre ; options { equipementId, limite (10 par
   * portée) }. → { requete, mots, equivalents, portees: [{ portee, libelle, resultats }] } ; un
   * résultat n'est que dans la première portée qui le contient. Rien n'est cherché sans mot utile.
   */
  function rechercher(texteRecherche, options) {
    const reglages = options || {};
    const limiteDemandee = Number(reglages.limite);
    const limite = Number.isInteger(limiteDemandee) && limiteDemandee > 0 ? limiteDemandee : RECHERCHE.limite;
    const equipementId = texte(reglages.equipementId);
    const requete = texte(texteRecherche);
    const { mots, equivalents, poids } = termesDeLaRequete(requete);
    const portees = porteesDe(equipementId);
    const rangees = portees.map(() => []);
    if (mots.length) {
      classer(indexAJour(), poids).forEach((trouve) => {
        rangees[portees.findIndex((portee) => portee.contient(trouve.documentIndexe.equipementId))].push(trouve);
      });
    }
    return {
      requete, mots, equivalents,
      portees: portees.map((portee, rang) => ({
        portee: portee.portee, libelle: portee.libelle,
        resultats: rangees[rang].sort(comparerTrouves).slice(0, limite).map(enResultat),
      })),
    };
  }

  /** État de l'index (suivi et tests) : { construit, documents, constructions }. */
  function etatRecherche() {
    return { construit: index !== null, documents: index ? index.documents.length : 0, constructions };
  }

  return {
    RECHERCHE, MOTS_VIDES, LEXIQUE,
    rechercher, surligner, etatRecherche,
    motsRecherche: (valeur) => termes(valeur),
  };
})());
