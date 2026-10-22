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
