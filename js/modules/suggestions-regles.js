'use strict';
// Suggestions (1/2) — règles du préventif suggéré (ARCHITECTURE.md §16.2 à §16.5 ; CDC du lot 3 bis,
// D51 à D57). Fonctions de lecture : elles lisent les données et le journal, n'écrivent rien ; seules
// `ignorer` et `marquerTraitee` écrivent, et seulement au journal (une décision du responsable).
// Prévo ne modifie jamais une gamme tout seul.
//    1. Constantes et petits outils (texte, dates, réglages)
//    2. Index d'un calcul (équipements, gammes, visites, pannes, DI, décisions, passage au format 2)
//    3. Les quatre règles (S1 créer une gamme, S2 revoir le préventif, S3 anomalies répétées,
//       S4 allonger une gamme)
//    4. Textes des suggestions
//    5. API : calculer, ouvertes, pourEquipement, pourGamme, trouver
//    6. Décisions du responsable (journal) : ignorer, marquerTraitee
// Crée l'objet Suggestions ; suggestions-ecrans.js le complète.

const Suggestions = (() => {

  // ===========================================================================================
  // 1. Constantes et petits outils
  // ===========================================================================================

  // Type de chaque règle, en clair (badge des cartes : le texte dit le type, la couleur aide seulement).
  const TITRES = {
    S1: 'Créer une gamme',
    S2: 'Revoir le préventif',
    S3: 'Anomalies répétées',
    S4: 'Allonger une gamme',
  };
  const TYPES_CORRECTIFS = ['correctif immédiat', 'correctif différé'];
  const STATUTS_CLOTURES = ['Clôturé techniquement', 'Clôturé administrativement'];
  const DECLENCHEURS_SUIVIS = ['date', 'compteur'];     // une gamme « seuil » n'a pas de périodicité
  const VISITES_REGARDEES_S3 = 4;                       // S3 : 2 anomalies sur les 4 dernières visites
  const ANOMALIES_S3 = 2;
  const CRITICITES_S4 = ['B', 'C'];                     // jamais A (ni criticité vide)
  const ORDRE_REGLES = { S2: 0, S3: 1, S1: 2, S4: 3 };  // des pannes ou anomalies en cours d'abord
  const ORDRE_CRITICITES = { A: 0, B: 1, C: 2 };
  const MOTIF_MAX = 300;
  // [\s\S]* : le motif peut contenir n'importe quel caractère (un saut de ligne venu d'Excel compris).
  const MOTIF_DECISION = /^suggestion (S[1-4]-\S+) (ignorée|traitée) : ([\s\S]*)$/;
  const MARQUE_FORMAT_2 = 'passage au format 2 du fichier';

  // Réglages de parametres.csv (§16.1) : absents, illisibles ou hors bornes → valeur par défaut.
  const REGLAGES = {
    seuilPannes: { cle: 'suggestion_seuil_pannes', defaut: 3, min: 2, max: 20 },
    visitesSansConstat: { cle: 'suggestion_visites_sans_constat', defaut: 5, min: 3, max: 20 },
    fenetreMois: { cle: 'suggestion_fenetre_mois', defaut: 12, min: 3, max: 24 },
  };

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  /** Vrai pour une date 'AAAA-MM-JJ' qui existe (le 31/02 n'existe pas). */
  function estJourValide(jour) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(jour)) return false;
    const [annee, mois, quantieme] = jour.split('-').map(Number);
    const date = new Date(Date.UTC(annee, mois - 1, quantieme));
    return date.getUTCFullYear() === annee && date.getUTCMonth() === mois - 1 && date.getUTCDate() === quantieme;
  }

  /**
   * Moment d'un OT (§16.2) : fin des travaux, sinon clôture technique, sinon création, au format
   * 'AAAA-MM-JJ HH:MM' (ou 'AAAA-MM-JJ' pour une date seule) ; '' si la date est illisible.
   * Deux moments se comparent comme des textes.
   */
  function momentDe(ot) {
    const brut = texte(ot.date_fin) || texte(ot.date_cloture_tech) || texte(ot.date_creation);
    const moment = brut.replace('T', ' ').slice(0, 16);
    return estJourValide(moment.slice(0, 10)) ? moment : '';
  }

  function momentDuJournal(valeur) {
    const moment = texte(valeur).replace('T', ' ').slice(0, 16);
    return estJourValide(moment.slice(0, 10)) ? moment : '';
  }

  function versUtc(jour) {
    const [annee, mois, quantieme] = jour.split('-').map(Number);
    return Date.UTC(annee, mois - 1, quantieme);
  }

  function versJour(millisecondes) {
    return new Date(millisecondes).toISOString().slice(0, 10);
  }

  function ajouterJours(jour, nombre) {
    return versJour(versUtc(jour) + nombre * 86400000);
  }

  /** Même jour, n mois plus tard (ou plus tôt), ramené au dernier jour du mois s'il n'existe pas. */
  function ajouterMois(jour, nombre) {
    const [annee, mois, quantieme] = jour.split('-').map(Number);
    const total = annee * 12 + (mois - 1) + nombre;
    const nouvelleAnnee = Math.floor(total / 12);
    const nouveauMois = total - nouvelleAnnee * 12;
    const dernier = new Date(Date.UTC(nouvelleAnnee, nouveauMois + 1, 0)).getUTCDate();
    return versJour(Date.UTC(nouvelleAnnee, nouveauMois, Math.min(quantieme, dernier)));
  }

  function joursEntre(debut, fin) {
    return Math.round((versUtc(fin) - versUtc(debut)) / 86400000);
  }

  /** Arrondi à l'unité, demi vers le haut (58,5 → 59). */
  function arrondi(valeur) {
    return Math.floor(valeur + 0.5);
  }

  function reglage(nom, remplacements) {
    const definition = REGLAGES[nom];
    const demande = remplacements && remplacements[nom] !== undefined
      ? remplacements[nom] : Donnees.parametre(definition.cle, '');
    const valeur = Number(texte(demande).replace(',', '.'));
    const valide = texte(demande) !== '' && Number.isInteger(valeur) && valeur >= definition.min && valeur <= definition.max;
    return valide ? valeur : definition.defaut;
  }

  // ===========================================================================================
  // 2. Index d'un calcul (construits une fois : le calcul reste linéaire sur 5 000 OT)
  // ===========================================================================================

  /** Décisions du journal, de la plus récente à la plus ancienne (date_heure, puis identifiant). */
  function lireDecisions() {
    const decisions = [];
    Donnees.lignes('journal').forEach((ligne) => {
      const trouve = MOTIF_DECISION.exec(texte(ligne.action));
      const dateHeure = momentDuJournal(ligne.date_heure);
      if (!trouve || !dateHeure) return;
      decisions.push({
        cle: trouve[1], regle: trouve[1].slice(0, 2), decision: trouve[2], texte: trouve[3],
        dateHeure, profil: texte(ligne.profil), table: texte(ligne.table), idLigne: texte(ligne.id_ligne),
        id: texte(ligne.id), revenue: false,
      });
    });
    return decisions.sort((a, b) => (a.dateHeure !== b.dateHeure ? (a.dateHeure < b.dateHeure ? 1 : -1)
      : b.id.localeCompare(a.id)));
  }

  /** Moment du passage au format 2 (§16.2) : la plus récente ligne du journal qui le dit, sinon ''. */
  function passageAuFormat2() {
    let passage = '';
    Donnees.lignes('journal').forEach((ligne) => {
      if (texte(ligne.table) !== 'parametres' || texte(ligne.id_ligne) !== 'version_schema') return;
      if (!texte(ligne.action).includes(MARQUE_FORMAT_2)) return;
      const moment = momentDuJournal(ligne.date_heure);
      if (moment > passage) passage = moment;
    });
    return passage;
  }

  function ajouterA(index, cle, valeur) {
    if (!index.has(cle)) index.set(cle, []);
    index.get(cle).push(valeur);
  }

  function comparerFaits(a, b) {
    return a.moment !== b.moment ? (a.moment < b.moment ? -1 : 1) : texte(a.ot.id).localeCompare(texte(b.ot.id));
  }

  function construireContexte(jour, remplacements) {
    const fenetreMois = reglage('fenetreMois', remplacements);
    const debutFenetre = ajouterJours(ajouterMois(jour, -fenetreMois), 1);
    const contexte = {
      jour,
      reglages: {
        seuilPannes: reglage('seuilPannes', remplacements),
        visitesSansConstat: reglage('visitesSansConstat', remplacements),
        fenetreMois, debutFenetre, passageFormat2: passageAuFormat2(),
      },
      equipements: new Map(),
      gammesParEquipement: new Map(),       // gammes actives (tout déclencheur)
      visitesParGamme: new Map(),           // [{ ot, moment, jour, anomalie }] triées
      pannesParEquipement: new Map(),       // correctifs de même cause dans la fenêtre : [{ ot, moment, jour }]
      creationsCorrectifs: new Map(),       // S4 : jours de création des correctifs non annulés
      disParOt: new Map(),
      libellesCauses: new Map(),
      derniereDecision: new Map(),
      decisions: lireDecisions(),
    };
    Donnees.lignes('equipements').forEach((e) => contexte.equipements.set(e.id, e));
    Donnees.lignes('gammes').forEach((g) => {
      if (texte(g.actif) !== '0') ajouterA(contexte.gammesParEquipement, texte(g.equipement_id), g);
    });
    Donnees.lignes('demandes').forEach((di) => {
      if (texte(di.ot_origine_id)) ajouterA(contexte.disParOt, texte(di.ot_origine_id), di.id);
    });
    Donnees.lignes('codes_defaillance').forEach((c) => {
      if (c.famille === 'cause' && texte(c.libelle)) contexte.libellesCauses.set(texte(c.code), texte(c.libelle));
    });
    Donnees.lignes('ordres_travail').forEach((ot) => indexerOt(contexte, ot));
    contexte.visitesParGamme.forEach((visites) => visites.sort(comparerFaits));
    contexte.pannesParEquipement.forEach((pannes) => pannes.sort(comparerFaits));
    contexte.decisions.forEach((d) => { if (!contexte.derniereDecision.has(d.cle)) contexte.derniereDecision.set(d.cle, d); });
    return contexte;
  }

  function indexerOt(contexte, ot) {
    const type = texte(ot.type);
    const statut = texte(ot.statut);
    const equipementId = texte(ot.equipement_id);
    if (TYPES_CORRECTIFS.includes(type) && statut !== 'Annulé') {
      const creation = texte(ot.date_creation).slice(0, 10);
      if (estJourValide(creation)) ajouterA(contexte.creationsCorrectifs, equipementId, creation);
    }
    if (!STATUTS_CLOTURES.includes(statut)) return;
    const moment = momentDe(ot);
    const jour = moment.slice(0, 10);
    if (!moment || jour > contexte.jour) return;
    if (texte(ot.gamme_id)) {
      ajouterA(contexte.visitesParGamme, texte(ot.gamme_id), {
        ot, moment, jour, anomalie: texte(ot.anomalie_constatee) === '1' || contexte.disParOt.has(ot.id),
      });
    }
    if (TYPES_CORRECTIFS.includes(type) && texte(ot.cause_code) && jour >= contexte.reglages.debutFenetre) {
      ajouterA(contexte.pannesParEquipement, equipementId, { ot, moment, jour });
    }
  }

  /** Équipement suivi (§16.2) : actif et pas au rebut. */
  function equipementSuivi(contexte, equipementId) {
    const equipement = contexte.equipements.get(equipementId);
    return Boolean(equipement) && texte(equipement.actif) !== '0' && texte(equipement.statut) !== 'rebut';
  }

  function gammesSuivies(contexte, equipementId) {
    return (contexte.gammesParEquipement.get(equipementId) || [])
      .filter((g) => DECLENCHEURS_SUIVIS.includes(texte(g.declencheur) || 'date'));
  }

  // ===========================================================================================
  // 3. Les quatre règles
  // ===========================================================================================

  /** Pannes de l'équipement regroupées par cause, postérieures à `apres` (moment, '' = toutes). */
  function pannesParCause(contexte, equipementId, apres) {
    const parCause = new Map();
    (contexte.pannesParEquipement.get(equipementId) || []).forEach((fait) => {
      if (fait.moment > apres) ajouterA(parCause, texte(fait.ot.cause_code), fait);
    });
    return parCause;
  }

  /** Intervalle médian en jours entre des faits triés (arrondi demi vers le haut), null s'il n'y en a qu'un. */
  function intervalleMedian(faits) {
    const ecarts = [];
    for (let rang = 1; rang < faits.length; rang += 1) ecarts.push(joursEntre(faits[rang - 1].jour, faits[rang].jour));
    if (!ecarts.length) return null;
    ecarts.sort((a, b) => a - b);
    const milieu = Math.floor(ecarts.length / 2);
    return arrondi(ecarts.length % 2 ? ecarts[milieu] : (ecarts[milieu - 1] + ecarts[milieu]) / 2);
  }

  function decisionDe(contexte, cle) {
    return contexte.derniereDecision.get(cle) || null;
  }

  /** Suggestion de base, complétée par chaque règle ; faits triés du plus ancien au plus récent. */
  function suggestion(contexte, regle, cle, equipementId, faits, complements) {
    const equipement = contexte.equipements.get(equipementId) || {};
    const decision = decisionDe(contexte, cle);
    return Object.assign({
      cle, regle, titre: TITRES[regle], equipementId, repere: texte(equipement.repere) || equipementId,
      criticite: texte(equipement.criticite), gammeIds: [], causeCode: '', causeLibelle: '',
      nombre: faits.length, sur: null, intervalleMedianJours: null,
      ots: faits.map((f) => f.ot.id).reverse(), dis: [], dates: faits.map((f) => f.jour),
      depuis: decision ? decision.dateHeure : null,
      decisionPrecedente: decision ? { decision: decision.decision, dateHeure: decision.dateHeure,
        texte: decision.texte, profil: decision.profil } : null,
    }, complements);
  }

  /** S1 « Créer une gamme » : équipement suivi sans gamme active, au moins `seuil` pannes de même cause. */
  function regleS1(contexte, equipementId, resultats) {
    if ((contexte.gammesParEquipement.get(equipementId) || []).length) return;
    const parCause = new Map();
    (contexte.pannesParEquipement.get(equipementId) || []).forEach((fait) => ajouterA(parCause, texte(fait.ot.cause_code), fait));
    parCause.forEach((tous, cause) => {
      const cle = 'S1-' + equipementId + '-' + cause;
      const decision = decisionDe(contexte, cle);
      const faits = decision ? tous.filter((f) => f.moment > decision.dateHeure) : tous;
      if (faits.length < contexte.reglages.seuilPannes) return;
      resultats.push(suggestion(contexte, 'S1', cle, equipementId, faits, {
        causeCode: cause, causeLibelle: contexte.libellesCauses.get(cause) || cause, intervalleMedianJours: intervalleMedian(faits),
      }));
    });
  }

  /** S2 « Revoir le préventif » : pannes de même cause postérieures à la première visite des gammes suivies. */
  function regleS2(contexte, equipementId, resultats) {
    const gammes = gammesSuivies(contexte, equipementId).filter((g) => (contexte.visitesParGamme.get(g.id) || []).length);
    if (!gammes.length) return;
    const premiereVisite = gammes.map((g) => contexte.visitesParGamme.get(g.id)[0].moment).sort()[0];
    pannesParCause(contexte, equipementId, premiereVisite).forEach((tous, cause) => {
      const cle = 'S2-' + equipementId + '-' + cause;
      const decision = decisionDe(contexte, cle);
      const faits = decision ? tous.filter((f) => f.moment > decision.dateHeure) : tous;
      if (faits.length < contexte.reglages.seuilPannes) return;
      resultats.push(suggestion(contexte, 'S2', cle, equipementId, faits, {
        gammeIds: gammes.map((g) => g.id).sort(), causeCode: cause,
        causeLibelle: contexte.libellesCauses.get(cause) || cause, intervalleMedianJours: intervalleMedian(faits),
      }));
    });
  }

  /** S3 « Anomalies répétées » : au moins 2 anomalies parmi les 4 dernières visites de la gamme. */
  function regleS3(contexte, gamme, resultats) {
    const cle = 'S3-' + gamme.id;
    const decision = decisionDe(contexte, cle);
    const visites = (contexte.visitesParGamme.get(gamme.id) || []).filter((v) => !decision || v.moment > decision.dateHeure);
    const regardees = visites.slice(-VISITES_REGARDEES_S3);
    const avecAnomalie = regardees.filter((v) => v.anomalie);
    if (avecAnomalie.length < ANOMALIES_S3) return;
    const dis = [];
    avecAnomalie.forEach((v) => (contexte.disParOt.get(v.ot.id) || []).forEach((id) => dis.push(id)));
    resultats.push(suggestion(contexte, 'S3', cle, texte(gamme.equipement_id), avecAnomalie, {
      gammeIds: [gamme.id], sur: regardees.length, dis: dis.sort(),
    }));
  }

  /** S4 « Allonger une gamme » : série de visites sans anomalie ni panne, criticité B ou C seulement. */
  function regleS4(contexte, gamme, resultats) {
    const equipementId = texte(gamme.equipement_id);
    const equipement = contexte.equipements.get(equipementId);
    if (!CRITICITES_S4.includes(texte(equipement && equipement.criticite))) return;
    const cle = 'S4-' + gamme.id;
    const decision = decisionDe(contexte, cle);
    const passage = contexte.reglages.passageFormat2;
    const comptees = (contexte.visitesParGamme.get(gamme.id) || [])
      .filter((v) => v.moment > passage && (!decision || v.moment > decision.dateHeure));
    const serie = [];
    for (let rang = comptees.length - 1; rang >= 0 && !comptees[rang].anomalie; rang -= 1) serie.unshift(comptees[rang]);
    if (serie.length < contexte.reglages.visitesSansConstat) return;
    const premierJour = serie[0].jour;
    if ((contexte.creationsCorrectifs.get(equipementId) || []).some((jour) => jour >= premierJour)) return;
    resultats.push(suggestion(contexte, 'S4', cle, equipementId, serie, { gammeIds: [gamme.id] }));
  }

  function comparerSuggestions(a, b) {
    const criticite = (s) => (s.criticite in ORDRE_CRITICITES ? ORDRE_CRITICITES[s.criticite] : 3);
    return ORDRE_REGLES[a.regle] - ORDRE_REGLES[b.regle] || criticite(a) - criticite(b)
      || b.nombre - a.nombre || (a.cle < b.cle ? -1 : a.cle > b.cle ? 1 : 0);   // clé : ordre des caractères, stable
  }

  // ===========================================================================================
  // 4. Textes des suggestions (D56 a : les faits, jamais une périodicité proposée)
  // ===========================================================================================

  function periodicite(gamme) {
    if (texte(gamme.declencheur) === 'compteur') {
      const compteur = Donnees.trouver('compteurs', gamme.compteur_id);
      const unite = compteur ? texte(compteur.unite) : '';
      return texte(gamme.periodicite_unites)
        ? 'toutes les ' + UI.nombreFr(gamme.periodicite_unites) + (unite ? '\u00a0' + unite : '') : 'périodicité non renseignée';
    }
    return texte(gamme.periodicite_jours) ? 'tous les ' + UI.nombreFr(gamme.periodicite_jours) + '\u00a0j' : 'périodicité non renseignée';
  }

  function gammeEnClair(gammeId) {
    const gamme = Donnees.trouver('gammes', gammeId);
    return gamme ? gammeId + ' (' + periodicite(gamme) + ')' : gammeId;
  }

  function enumeration(elements) {
    return elements.length < 2 ? elements.join('') : elements.slice(0, -1).join(', ') + ' et ' + elements[elements.length - 1];
  }

  /** « en 12 mois », ou « depuis le 12/03/2026 » quand une décision précédente borne les faits. */
  function periode(s, contexte) {
    return s.depuis ? 'depuis le ' + UI.dateFr(s.depuis.slice(0, 10)) : 'en ' + contexte.reglages.fenetreMois + ' mois';
  }

  /**
   * Fréquence en clair d'après l'intervalle médian : « environ une toutes les 4 semaines » (14 jours et
   * plus), « environ une tous les 5 jours », « environ une par jour » (1 jour). Médiane de 0 jour
   * (pannes groupées le même jour) ou inconnue : rien, plutôt qu'une fréquence fausse.
   */
  function frequence(intervalle) {
    if (intervalle === null || intervalle < 1) return '';
    if (intervalle >= 14) return ' (environ une toutes les ' + arrondi(intervalle / 7) + ' semaines)';
    return intervalle === 1 ? ' (environ une par jour)' : ' (environ une tous les ' + intervalle + ' jours)';
  }

  function rediger(s, contexte) {
    const pannes = s.nombre + ' pannes « ' + s.causeLibelle + ' » ' + periode(s, contexte);
    if (s.regle === 'S1') {
      s.texte = s.repere + ' : ' + pannes + frequence(s.intervalleMedianJours) + ', aucune gamme active.';
      s.question = 'Créer une gamme pour prévenir cette panne ?';
    } else if (s.regle === 'S2') {
      const gammes = s.gammeIds.map(gammeEnClair);
      s.texte = s.repere + ' : ' + pannes + ' malgré ' + (gammes.length > 1 ? 'les gammes ' : 'la gamme ') + enumeration(gammes)
        + (s.intervalleMedianJours === null ? '.' : ' ; intervalle médian entre ces pannes : ' + s.intervalleMedianJours + ' jours.');
      s.question = 'Raccourcir la périodicité, ajouter une opération à la check-list ou créer une gamme dédiée ? '
        + 'À examiner : la gamme ne dit pas quelles pannes elle prévient.';
    } else if (s.regle === 'S3') {
      const visites = s.sur === VISITES_REGARDEES_S3 ? 'des ' + s.sur + ' dernières visites' : 'de ses ' + s.sur + ' visites';
      s.texte = s.gammeIds[0] + ' (' + s.repere + ') : anomalie constatée à ' + s.nombre + ' ' + visites
        + ' (' + s.dates.map((jour) => UI.dateFr(jour)).join(', ') + ').';
      s.question = 'Raccourcir la périodicité ou compléter la check-list ?';
    } else {
      const gamme = Donnees.trouver('gammes', s.gammeIds[0]);
      s.texte = s.repere + ' : ' + s.nombre + ' visites de suite sans anomalie (gamme ' + s.gammeIds[0]
        + (gamme ? ', ' + periodicite(gamme) : '') + '), aucune panne depuis la première (' + UI.dateFr(s.dates[0]) + ').';
      s.question = 'Allonger la périodicité ? Vérifiez d\'abord qu\'aucune obligation (réglementaire, constructeur, '
        + 'garantie) ne l\'impose.';
    }
    return s;
  }

  // ===========================================================================================
  // 5. API
  // ===========================================================================================

  /**
   * Suggestions ouvertes au `jour` donné (aujourd'hui s'il est omis) et décisions du journal (§16.5).
   * Lecture seule.
   * `remplacements` (facultatif) : { seuilPannes, visitesSansConstat, fenetreMois } à la place des
   * paramètres (tests).
   */
  function calculer(jour, remplacements) {
    const contexte = construireContexte(jour || Donnees.aujourdhui(), remplacements);
    const resultats = [];
    contexte.equipements.forEach((equipement, equipementId) => {
      if (!equipementSuivi(contexte, equipementId)) return;
      regleS1(contexte, equipementId, resultats);
      regleS2(contexte, equipementId, resultats);
      gammesSuivies(contexte, equipementId).forEach((gamme) => {
        regleS3(contexte, gamme, resultats);
        regleS4(contexte, gamme, resultats);
      });
    });
    const ouvertes = resultats.map((s) => rediger(s, contexte)).sort(comparerSuggestions);
    const clesOuvertes = new Set(ouvertes.map((s) => s.cle));
    const decisions = contexte.decisions.map((d) => Object.assign({}, d, {
      revenue: contexte.derniereDecision.get(d.cle) === d && clesOuvertes.has(d.cle),
    }));
    return { ouvertes, decisions, reglages: contexte.reglages };
  }

  function ouvertes(jour) {
    return calculer(jour || Donnees.aujourdhui()).ouvertes;
  }

  /** S1, S2 de l'équipement et S3, S4 de ses gammes. */
  function pourEquipement(equipementId, jour) {
    return ouvertes(jour).filter((s) => s.equipementId === equipementId);
  }

  /** S2 qui citent la gamme, S3 et S4 de la gamme. */
  function pourGamme(gammeId, jour) {
    return ouvertes(jour).filter((s) => s.gammeIds.includes(gammeId));
  }

  /** La suggestion ouverte de cette clé, sinon null. */
  function trouver(cle, jour) {
    return ouvertes(jour).find((s) => s.cle === cle) || null;
  }

  // ===========================================================================================
  // 6. Décisions du responsable (journal, §16.4)
  // ===========================================================================================

  /**
   * Ligne du journal qui porte la décision : l'équipement pour S1 et S2, la gamme pour S3 et S4.
   * La clé suit §16.2 ; l'équipement est retrouvé parmi les identifiants existants (le plus long qui
   * convient), car un code cause peut contenir un tiret.
   */
  function cibleDecision(cle) {
    const regle = texte(cle).slice(0, 2);
    if (regle === 'S3' || regle === 'S4') {
      const gamme = Donnees.trouver('gammes', cle.slice(3));
      if (gamme) return { table: 'gammes', id: gamme.id };
    } else if (regle === 'S1' || regle === 'S2') {
      const candidats = Donnees.lignes('equipements').filter((e) => e.id && cle.startsWith(regle + '-' + e.id + '-'))
        .sort((a, b) => b.id.length - a.id.length);
      if (candidats.length) return { table: 'equipements', id: candidats[0].id };
    }
    throw new Donnees.ErreurValidation('Suggestion inconnue : « ' + texte(cle) + ' ».');
  }

  function texteDecision(valeur) {
    return texte(valeur).replace(/\s+/g, ' ');      // tout blanc (saut de ligne, U+2028, U+2029…) → une espace
  }

  async function ecrireDecision(cle, decision, motif) {
    const cible = cibleDecision(cle);
    const identifiant = await Donnees.journaliser(cible.table, cible.id, 'suggestion ' + cle + ' ' + decision + ' : ' + motif);
    if (!identifiant) {
      throw new Donnees.ErreurStockage('La décision n\'a pas pu être inscrite au journal : la suggestion reste ouverte. Réessayez.');
    }
    return identifiant;
  }

  /** « Ignorer » : motif obligatoire, suggestion ouverte seulement ; renvoie l'identifiant de la ligne du journal. */
  async function ignorer(cle, motif) {
    const propre = texteDecision(motif);
    if (!propre) throw new Donnees.ErreurValidation('Indiquez pourquoi vous ignorez cette suggestion : le motif est inscrit au journal.');
    if (propre.length > MOTIF_MAX) throw new Donnees.ErreurValidation('Le motif ne doit pas dépasser ' + MOTIF_MAX + ' caractères.');
    if (!trouver(cle, Donnees.aujourdhui())) {
      throw new Donnees.ErreurValidation('Cette suggestion n\'est plus ouverte (déjà décidée, ou les faits ont changé).');
    }
    return ecrireDecision(cle, 'ignorée', propre);
  }

  /**
   * « Traitée » : après la création ou la modification d'une gamme depuis la suggestion. La
   * suggestion peut déjà ne plus s'appliquer (S1 : l'équipement a maintenant une gamme) : seule la
   * clé est exigée.
   */
  async function marquerTraitee(cle, ceQuiAEteFait) {
    const propre = texteDecision(ceQuiAEteFait).slice(0, MOTIF_MAX) || 'traitée';
    return ecrireDecision(cle, 'traitée', propre);
  }

  return {
    TITRES, REGLAGES,
    calculer, ouvertes, pourEquipement, pourGamme, trouver, ignorer, marquerTraitee,
  };
})();
