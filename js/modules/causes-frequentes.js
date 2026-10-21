'use strict';
// CausesFrequentes : causes fréquentes d'un symptôme, sur un équipement ou sur les équipements de
// même marque et modèle (décision D25, ARCHITECTURE.md §14.5). Statistique de l'historique des OT
// correctifs clôturés, montrée dans un encart « Causes fréquentes ici — n cas » : jamais un
// diagnostic (on écrit « fréquent ici », jamais « cause certaine »).
//
// Lot 3 bis (D59, ARCHITECTURE.md §16.7) : l'encart dit aussi la solidité de ses chiffres. Sur 12 cas,
// « 7 cas sur 12 » veut dire « entre 32 % et 81 % des cas » (fourchette de Wilson à 95 %) : quand une
// fourchette dépasse ± 20 points, la mention « Peu de cas : à prendre comme une piste. » s'affiche, et
// les fourchettes sont toujours dans un détail que l'on déplie.
//
// Utilisé par les fiches DI et OT (onglets Préparation et Compte rendu), pour tous les profils.
// Fonctions de lecture seule : rien n'est écrit. Toute donnée insérée dans l'encart passe par
// UI.html (échappement).

const CausesFrequentes = (() => {

  const MINIMUM_PAR_DEFAUT = 5;       // nombre de cas à partir duquel l'encart montre les causes
  const NOMBRE_CAUSES = 3;            // au plus 3 causes affichées
  const LIENS_PAR_CAUSE = 5;          // au plus 5 liens « voir les OT » par cause (les plus récents)
  const STATUTS_CLOTURES = ['Clôturé techniquement', 'Clôturé administrativement'];
  const MENTION = 'Statistique de l\'historique, pas un diagnostic';
  const Z_95 = 1.96;                  // fourchette à 95 % (loi normale)
  const DEMI_LARGEUR_PISTE = 0.20;    // au-delà de ± 20 points : « peu de cas »
  const MENTION_PISTE = 'Peu de cas : à prendre comme une piste.';

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  /** Marque ou modèle comparable : casse et espaces ignorés (« CR 10 » = « cr10 »). */
  function cleComparable(valeur) {
    return texte(valeur).replace(/\s+/g, '').toLowerCase();
  }

  /** Un « cas » : OT correctif clôturé (techniquement ou administrativement), de ce symptôme, avec une cause. */
  function estUnCas(ot, symptomeCode) {
    return /^correctif/.test(texte(ot.type))
      && STATUTS_CLOTURES.includes(ot.statut)
      && texte(ot.symptome_code) === symptomeCode
      && texte(ot.cause_code) !== '';
  }

  /** Date d'un cas : fin des travaux, sinon clôture technique, sinon création (AAAA-MM-JJ). */
  function dateDuCas(ot) {
    return (texte(ot.date_fin) || texte(ot.date_cloture_tech) || texte(ot.date_creation)).slice(0, 10);
  }

  /**
   * Fourchette de la part k / n (D59) : intervalle de Wilson à 95 %, { bas, haut } entre 0 et 1,
   * ou null si n = 0. Plus juste que « k / n plus ou moins … » quand il y a peu de cas ou quand la
   * part est proche de 0 ou de 1 (la fourchette ne sort jamais de 0–100 %).
   */
  function fourchette(k, n) {
    const total = Number(n);
    const cas = Number(k);
    if (!(total > 0) || !(cas >= 0) || cas > total) return null;
    const part = cas / total;
    const z2 = Z_95 * Z_95;
    const denominateur = 1 + z2 / total;
    const centre = (part + z2 / (2 * total)) / denominateur;
    const marge = (Z_95 * Math.sqrt(part * (1 - part) / total + z2 / (4 * total * total))) / denominateur;
    // Bornes exactes aux extrêmes (aucun cas : 0 % ; tous les cas : 100 %), sans erreur d'arrondi.
    return { bas: cas === 0 ? 0 : Math.max(0, centre - marge), haut: cas === total ? 1 : Math.min(1, centre + marge) };
  }

  /** 0,3195 → « 32 % » : arrondi à l'unité, demi vers le haut. */
  function pourcent(part) {
    return Math.floor(part * 100 + 0.5) + '\u00a0%';
  }

  /** « entre 32 % et 81 % des cas » (vide si n = 0). */
  function texteFourchette(k, n) {
    const resultat = fourchette(k, n);
    return resultat ? 'entre ' + pourcent(resultat.bas) + ' et ' + pourcent(resultat.haut) + ' des cas' : '';
  }

  /** Vrai si au moins une cause affichée a une fourchette de plus de ± 20 points. */
  function peuDeCas(resultat) {
    return resultat.causes.some((cause) => {
      const f = fourchette(cause.nombre, resultat.total);
      return f !== null && (f.haut - f.bas) / 2 > DEMI_LARGEUR_PISTE;
    });
  }

  /** Détail replié « Précision de ces chiffres » : la fourchette de chaque cause affichée. */
  function precisionHtml(resultat) {
    return UI.html`<details class="causes-precision">
      <summary>Précision de ces chiffres</summary>
      <dl class="causes-fourchettes">${resultat.causes.map((cause) => UI.html`<div><dt>${cause.libelle} :</dt>
        <dd>${texteFourchette(cause.nombre, resultat.total)}</dd></div>`)}</dl>
      <p class="causes-explication">Calculée ainsi (méthode de Wilson), une fourchette contient la vraie part de la cause
        95 fois sur 100 ; elle se resserre quand les cas s'accumulent.</p>
    </details>`;
  }

  /** Plus récent d'abord (date du cas, puis identifiant). */
  function comparerCasRecentsDabord(a, b) {
    const dateA = dateDuCas(a);
    const dateB = dateDuCas(b);
    if (dateA !== dateB) return dateA < dateB ? 1 : -1;
    return texte(b.id).localeCompare(texte(a.id), 'fr', { numeric: true });
  }

  /** Libellé d'un code de défaillance d'une famille (« cause », « remède »), sinon le code lui-même. */
  function libelleCode(famille, code) {
    const ligne = Donnees.lignes('codes_defaillance').find((c) => c.famille === famille && c.code === code);
    return ligne && texte(ligne.libelle) ? ligne.libelle : code;
  }

  /** Identifiants des équipements de même marque et modèle (casse et espaces ignorés), lui compris. */
  function equipementsDeMemeModele(equipement) {
    const marque = cleComparable(equipement.marque);
    const modele = cleComparable(equipement.modele);
    return new Set(Donnees.lignes('equipements')
      .filter((e) => cleComparable(e.marque) === marque && cleComparable(e.modele) === modele)
      .map((e) => e.id));
  }

  /**
   * Remède le plus utilisé parmi des cas triés du plus récent au plus ancien :
   * { code, libelle, nombre } ou null si aucun remède n'est renseigné. Égalité : le plus récent.
   */
  function remedeLePlusUtilise(casRecentsDabord) {
    const comptes = new Map();         // garde l'ordre d'apparition : le plus récent d'abord
    casRecentsDabord.forEach((ot) => {
      const code = texte(ot.remede_code);
      if (code) comptes.set(code, (comptes.get(code) || 0) + 1);
    });
    let meilleur = null;
    comptes.forEach((nombre, code) => {
      if (!meilleur || nombre > meilleur.nombre) meilleur = { code, nombre };
    });
    return meilleur ? { code: meilleur.code, libelle: libelleCode('remède', meilleur.code), nombre: meilleur.nombre } : null;
  }

  /**
   * Les 3 causes les plus fréquentes parmi des cas : par nombre décroissant, puis date du dernier
   * cas (le plus récent d'abord). [{ code, libelle, nombre, remede, dernierCas, ots }]
   */
  function causesLesPlusFrequentes(cas) {
    const parCause = new Map();
    cas.slice().sort(comparerCasRecentsDabord).forEach((ot) => {
      const code = texte(ot.cause_code);
      if (!parCause.has(code)) parCause.set(code, []);
      parCause.get(code).push(ot);
    });
    const causes = Array.from(parCause.entries()).map(([code, liste]) => ({
      code,
      libelle: libelleCode('cause', code),
      nombre: liste.length,
      remede: remedeLePlusUtilise(liste),
      dernierCas: dateDuCas(liste[0]),
      ots: liste.map((ot) => ot.id),
    }));
    causes.sort((a, b) => b.nombre - a.nombre
      || (a.dernierCas !== b.dernierCas ? (a.dernierCas < b.dernierCas ? 1 : -1) : 0)
      || a.code.localeCompare(b.code, 'fr', { numeric: true }));
    return causes.slice(0, NOMBRE_CAUSES);
  }

  function resultatSuffisant(portee, libellePortee, cas) {
    return { suffisant: true, portee, libellePortee, total: cas.length, causes: causesLesPlusFrequentes(cas) };
  }

  /**
   * Causes fréquentes d'un symptôme (D25).
   * Portée : cet équipement s'il a au moins `minimum` cas ; sinon, si sa marque et son modèle sont
   * renseignés, tous les équipements de même marque et modèle ; sinon suffisant = false.
   * → { suffisant, portee ('equipement' | 'modele' | null), libellePortee, total, causes: [{ code,
   *     libelle, nombre, remede: { code, libelle, nombre } | null, dernierCas, ots }] }
   * Quand suffisant = false, total = nombre de cas trouvés sur la portée la plus large essayée.
   */
  function calculer(equipementId, symptomeCode, options) {
    const demande = options && Number(options.minimum);
    const minimum = demande > 0 ? demande : MINIMUM_PAR_DEFAUT;
    const symptome = texte(symptomeCode);
    const insuffisant = { suffisant: false, portee: null, libellePortee: '', total: 0, causes: [] };
    if (!symptome) return insuffisant;

    const tousLesCas = Donnees.lignes('ordres_travail').filter((ot) => estUnCas(ot, symptome));
    const casEquipement = tousLesCas.filter((ot) => ot.equipement_id === equipementId);
    if (casEquipement.length >= minimum) return resultatSuffisant('equipement', 'cet équipement', casEquipement);

    const equipement = Donnees.trouver('equipements', equipementId);
    if (!equipement || !texte(equipement.marque) || !texte(equipement.modele)) {
      return Object.assign(insuffisant, { total: casEquipement.length });
    }
    const memeModele = equipementsDeMemeModele(equipement);
    const casModele = tousLesCas.filter((ot) => memeModele.has(ot.equipement_id));
    if (casModele.length >= minimum) {
      return resultatSuffisant('modele', 'équipements de même marque et modèle ('
        + texte(equipement.marque) + ' ' + texte(equipement.modele) + ')', casModele);
    }
    return Object.assign(insuffisant, { total: casModele.length });
  }

  /**
   * Le demandeur n'a pas accès aux écrans des OT (un lien #/ot le renverrait à l'accueil) : il voit
   * les mêmes identifiants, en texte simple (comme le lien de l'OT d'origine sur la fiche DI).
   */
  function sansLienVersLesOt() {
    return typeof App !== 'undefined' && App.estDemandeur();
  }

  /**
   * « et 4 autres » après les liens montrés : lien vers la liste des OT clôturés de l'équipement
   * quand la portée est cet équipement ; texte simple pour la portée « même marque et modèle »
   * (les OT sont alors sur plusieurs équipements : aucune liste ne les filtre ensemble) et pour le
   * demandeur.
   */
  function suiteDesLiens(reste, portee, equipementId) {
    if (reste <= 0) return '';
    const texteSuite = 'et ' + reste + (reste > 1 ? ' autres' : ' autre');
    if (portee !== 'equipement' || sansLienVersLesOt()) return UI.html` ${texteSuite}`;
    return UI.html` <a class="causes-autres" href="#/ot?equipement=${encodeURIComponent(equipementId)}&amp;etat=clotures">${texteSuite}</a>`;
  }

  /**
   * Une ligne de l'encart : « garniture usée — 7 cas sur 12 · remède … · dernier cas … · voir les
   * OT : … » ; au plus LIENS_PAR_CAUSE liens (les cas les plus récents), puis « et n autres ».
   * Pour le demandeur, les identifiants sont en texte simple.
   */
  function ligneCause(cause, resultat, equipementId) {
    const montres = cause.ots.slice(0, LIENS_PAR_CAUSE);         // ots : du plus récent au plus ancien
    const sansLien = sansLienVersLesOt();
    const liens = montres.map((id, position) => (sansLien
      ? UI.html`${position ? ', ' : ''}${id}`
      : UI.html`${position ? ', ' : ''}<a href="#/ot/${id}">${id}</a>`));
    const suite = suiteDesLiens(cause.ots.length - montres.length, resultat.portee, equipementId);
    const remede = cause.remede ? UI.html` · remède le plus utilisé : ${cause.remede.libelle}` : '';
    const dernier = cause.dernierCas ? UI.html` · dernier cas : ${UI.dateFr(cause.dernierCas)}` : '';
    return UI.html`<li><b>${cause.libelle}</b> — ${cause.nombre} cas sur ${resultat.total}${remede}${dernier} · voir les OT : ${liens}${suite}</li>`;
  }

  /**
   * Encart « Causes fréquentes ici » (élément DOM .encadre) pour un équipement et un code symptôme.
   * En dessous du minimum : « Pas encore assez de cas pour ce symptôme (n sur 5) ».
   * Sans code symptôme : null (rien à afficher).
   */
  function encart(equipementId, symptomeCode) {
    if (!texte(symptomeCode)) return null;
    const resultat = calculer(equipementId, symptomeCode);
    if (!resultat.suffisant) {
      return UI.element(UI.html`<div class="encadre causes-frequentes">
        <p>Pas encore assez de cas pour ce symptôme (${resultat.total} sur ${MINIMUM_PAR_DEFAUT})</p>
      </div>`);
    }
    return UI.element(UI.html`<div class="encadre causes-frequentes">
      <h3>Causes fréquentes ici — ${resultat.total} cas</h3>
      <p class="aide">Portée : ${resultat.libellePortee}</p>
      ${peuDeCas(resultat) ? UI.html`<p class="causes-piste"><b>${MENTION_PISTE}</b></p>` : ''}
      <ul>${resultat.causes.map((cause) => ligneCause(cause, resultat, equipementId))}</ul>
      <p class="note">${MENTION}</p>
      ${precisionHtml(resultat)}
    </div>`);
  }

  return { MINIMUM_PAR_DEFAUT, MENTION, MENTION_PISTE, calculer, encart, fourchette, texteFourchette };
})();
