'use strict';
// Wiki (3/8) — balisage d'une page (§20.4) et contrôles d'une proposition (§20.6 ; D97, D106, D111) (lot 6
// refondu). Fonctions pures : rien n'est écrit, aucun appel réseau.
//
// Balisage : « ## <Rubrique> », puis « - <phrase> [OT-AAAA-NNNN] [OT-…] » ; un lien vers une autre page s'écrit
// « [[<titre exact>]] » dans une phrase ; toute autre ligne non vide est hors de la forme. Une phrase est
// identifiée par la forme comparable de son texte sans citations ni crochets de lien : déplacée d'une rubrique à
// l'autre, elle reste la même ; reformulée, elle « reprend » les anciennes phrases dont elle cite tous les OT.
//
// Précisions au contrat (§20.6) :
//  - une proposition : { rien, pages: [{ action: 'modifier' | 'creer', titre, type, rattacheA, texte }],
//    contradictions: [{ page, phrase, observation, ot }] } (texte = balisage complet de la page après) ;
//  - un contexte : { otIngere: { id, dateIntervention, sourceTexte }, anterieure, pagesEnvoyees: [{ titre, type,
//    texte, mere, otDates: [{ id, date }] }], catalogue: [{ titre, type }] } ; écriture à la main : { manuel: true,
//    pagesEnvoyees (la page écrite), catalogue, otPermis: [identifiants], sources: { otId: texte } } ;
//  - les nombres d'une phrase identique à une phrase d'avant ne sont pas recontrôlés ; ceux d'une phrase nouvelle
//    ou reprise et du titre d'une page créée doivent figurer dans le texte de référence (l'OT ingéré et le texte
//    d'avant de la page ; à la main : les OT cités) ; « 0,4 » et « 0.4 » sont le même nombre ;
//  - dates : un nom de mois, une date en chiffres (« 12/03 », « 3/10/2026 », « 2026-06-08 ») ou une année 19xx ou
//    20xx qui n'est pas suivie d'une unité (« l'entretien des 2000 heures » n'est pas une date) ;
//  - les numéros d'OT (cités ou écrits dans le texte) ne comptent jamais comme des nombres, ni dans une phrase ni
//    dans le texte de référence ; une phrase réduite à ses citations est « vide » et refusée ;
//  - seul un savoir-faire se crée (§20.12) : le texte d'une machine ou d'un article s'écrit sur sa page, qui existe
//    toujours ; un type hors de Wiki.RUBRIQUES (« mode », retiré) est refusé, créé ou modifié ;
//  - un savoir-faire se rattache à une page envoyée d'équipement ou de composant ; une phrase gardée telle quelle
//    garde tous ses OT ;
//  - longueurs (Wiki.LIMITES, §20.12) : chaque rubrique d'un texte d'équipement ou de composant à sa limite (ses
//    phrases ; les mots de ses phrases, sans le nom de la rubrique ; une rubrique écrite deux fois compte en une) ; un
//    savoir-faire en entier (Wiki.mesurerTexte), avec le conseil de le découper sauf pour une sous-page ;
//  - comptage : un nombre en chiffres, ou de « deux » à « cent » en lettres, suivi de « fois », « OT »,
//    « intervention(s) », « panne(s) », « cas » ou « remplacement(s) » (« une fois remontée » est permis) ;
//  - sous-page (§20.4, révision du 2026-10-23 ; savoir-faire seulement, §20.12) : page créée dont « rattache_a »
//    désigne une page de même type (envoyée, au catalogue ou créée par la proposition) ; une sous-page d'équipement ou
//    de composant est refusée ; sa mère doit être une page envoyée qui n'est pas elle-même
//    une sous-page (`mere` d'une page envoyée : titre de sa mère, vide sinon), modifiée par la même proposition avec
//    un renvoi [[titre de la sous-page]] (à la main, une page s'écrit à la fois et le retrait est permis : ni l'un ni
//    l'autre n'est exigé) ; son titre commence par « <préfixe> — » suivi d'un mot (préfixe : le repère, titre avant
//    « — », d'une page d'équipement ancrée, sinon le titre entier de la mère) ; ses phrases se comparent au texte
//    d'avant de sa mère (une phrase déplacée telle quelle n'est pas recontrôlée ; les nombres d'une phrase nouvelle ou
//    reprise sont cherchés aussi dans le texte et le titre de la mère).

Object.assign(Wiki, (() => {

  const SEUILS = Wiki.SEUILS;
  const TYPES = Object.keys(Wiki.RUBRIQUES);
  const MOTIF_RUBRIQUE = /^##\s+(.+?)\s*$/;
  const MOTIF_PHRASE = /^-\s+(.*)$/;
  const MOTIF_CITATION = /\[(OT-\d{4}-\d{4,})\]/g;
  const MOTIF_LIEN = /\[\[([^[\]]+)\]\]/g;
  const MOTIF_NOMBRE = /\d+(?:[.,]\d+)*/g;
  const MOTS_NOMBRES = ['deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit', 'neuf', 'dix', 'onze', 'douze',
    'treize', 'quatorze', 'quinze', 'seize', 'vingt', 'trente', 'quarante', 'cinquante', 'soixante', 'cent'];
  const MOTIF_COMPTAGE = new RegExp('(?:^| )(?:\\d+|' + MOTS_NOMBRES.join('|')
    + ') (?:fois|ot|interventions?|pannes?|cas|remplacements?)(?= |$)');
  const MOIS = ['janvier', 'fevrier', 'mars', 'avril', 'mai', 'juin', 'juillet', 'aout', 'septembre', 'octobre',
    'novembre', 'decembre'];
  const MOTIF_MOIS = new RegExp('(?:^| )(?:' + MOIS.join('|') + ')(?= |$)');
  // Unités qui font d'un 19xx ou 20xx une quantité ; pas d'unité d'une lettre ambiguë (« en 2026 a été… »).
  const UNITES = 'h|heures?|bars?|mm|cm|km|kg|tr|tours?|litres?|kw|kva|mn|min|minutes?|secondes?|pieces?|cycles?';
  const MOTIF_ANNEE = new RegExp('(?:^| )(?:19|20)\\d{2}(?= |$)(?! (?:' + UNITES + ')(?: |$))');
  const MOTIF_DATE_CHIFFRES = /(?:^|[^\d/.-])(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/.]\d{1,2}[/.]\d{2,4}|\d{2}[/.]\d{2})(?![\d/.])/;
  const MOTIF_NUMERO_OT = /\bOT-\d{4}-\d{4,}\b/g;
  const MESSAGE_SECURITE = { ia: Wiki.MESSAGE_SECURITE_IA, manuel: Wiki.MESSAGE_SECURITE_MAIN };
  // Refus de la création d'un texte ancré (§20.12) : il existe toujours, sur la page de sa machine ou de son article.
  const TEXTE_DE_SA_PAGE = {
    'équipement': 'une page d\'équipement ne se crée pas : le texte d\'une machine s\'écrit sur sa page, qui existe toujours '
      + '(seul un savoir-faire se crée).',
    'composant': 'une page de composant ne se crée pas : le texte d\'un article s\'écrit sur sa page, qui existe toujours '
      + '(seul un savoir-faire se crée).',
  };

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  function sansDoublon(liste) {
    return Array.from(new Set(liste));
  }

  function court(valeur) {
    const propre = texte(valeur).replace(/\s+/g, ' ');
    return propre.length > 70 ? propre.slice(0, 69) + '…' : propre;
  }

  /** Refus d'un type hors de Wiki.RUBRIQUES (« mode », retiré par la refonte 2 : une panne est une page calculée). */
  function typeInconnu(type) {
    return 'type « ' + type + ' » inconnu (' + TYPES.join(', ') + ').';
  }

  // ===========================================================================================
  // 1. Balisage d'une page
  // ===========================================================================================

  function citationsDe(contenu) {
    return sansDoublon(Array.from(String(contenu || '').matchAll(MOTIF_CITATION), (m) => m[1]));
  }

  function liensDe(contenu) {
    return sansDoublon(Array.from(String(contenu || '').matchAll(MOTIF_LIEN), (m) => m[1].trim()));
  }

  /** Texte d'une phrase sans citations, liens gardés comme texte (« [[Titre]] » → « Titre »), espaces réduits. */
  function propre(contenu) {
    return String(contenu || '').replace(MOTIF_CITATION, ' ').replace(MOTIF_LIEN, (_, titre) => titre)
      .replace(/\s+/g, ' ').trim();
  }

  /**
   * Texte d'une phrase sans citations, sans liens NI numéros d'OT (pour les nombres et les dates : le titre d'une
   * page n'est pas une affirmation, un numéro d'OT n'est pas un nombre).
   */
  function sansReferences(contenu) {
    return String(contenu || '').replace(MOTIF_CITATION, ' ').replace(MOTIF_LIEN, ' ').replace(MOTIF_NUMERO_OT, ' ')
      .replace(/\s+/g, ' ').trim();
  }

  /** Identité d'une phrase : forme comparable de son texte sans citations ni crochets de lien. */
  function identitePhrase(contenu) {
    return Wiki.comparable(propre(contenu));
  }

  /**
   * Balisage → { rubriques: [{ nom, phrases: [{ texte, propre, ot, liens }] }], erreurs: [{ ligne, message }] }.
   * Lignes vides ignorées ; une phrase avant toute rubrique, ou une ligne qui n'est ni l'une ni l'autre, est une erreur.
   */
  function lireTexte(valeur) {
    const rubriques = [];
    const erreurs = [];
    let courante = null;
    String(valeur || '').replace(/\r\n?/g, '\n').split('\n').forEach((ligne, rang) => {
      const nette = ligne.trim();
      if (!nette) return;
      const titre = MOTIF_RUBRIQUE.exec(nette);
      if (titre) {
        courante = { nom: titre[1], phrases: [] };
        rubriques.push(courante);
        return;
      }
      const phrase = MOTIF_PHRASE.exec(nette);
      if (phrase && courante) {
        const contenu = phrase[1].trim();
        courante.phrases.push({ texte: contenu, propre: propre(contenu), ot: citationsDe(contenu), liens: liensDe(contenu) });
        return;
      }
      erreurs.push({ ligne: rang + 1, message: phrase ? 'phrase écrite avant toute rubrique'
        : 'ligne hors de la forme (« ## Rubrique » ou « - phrase [OT-…] »)' });
    });
    return { rubriques, erreurs };
  }

  /**
   * Rubriques → balisage : [{ rubrique | nom, phrases: [{ texte, ot }] }] ; rubriques vides omises, dans l'ordre de
   * Wiki.RUBRIQUES[type] (une rubrique inconnue du type vient après, telle quelle : le contrôle la refusera). Les
   * citations écrites dans le texte d'une phrase sont reportées en fin de ligne avec celles de `ot`.
   */
  function ecrireTexte(rubriques, type) {
    const ordre = Wiki.RUBRIQUES[type] || [];
    const rang = (nom) => {
      const trouve = ordre.findIndex((connue) => Wiki.comparable(connue) === Wiki.comparable(nom));
      return trouve < 0 ? ordre.length : trouve;
    };
    const lues = (rubriques || []).map((rubrique, position) => ({
      nom: texte(rubrique && (rubrique.rubrique || rubrique.nom)), position,
      phrases: ((rubrique && rubrique.phrases) || []).map((phrase) => ({
        texte: sansDoublon(citationsDe(phrase && phrase.texte).concat(((phrase && phrase.ot) || []).map(texte).filter(Boolean))),
        corps: String((phrase && phrase.texte) || '').replace(MOTIF_CITATION, ' ').replace(/\s+/g, ' ').trim(),
      })).filter((phrase) => phrase.corps || phrase.texte.length),
    })).filter((rubrique) => rubrique.nom && rubrique.phrases.length);
    lues.sort((a, b) => rang(a.nom) - rang(b.nom) || a.position - b.position);
    const lignes = [];
    lues.forEach((rubrique) => {
      const connue = ordre.find((nom) => Wiki.comparable(nom) === Wiki.comparable(rubrique.nom));
      lignes.push('## ' + (connue || rubrique.nom));
      rubrique.phrases.forEach((phrase) => {
        lignes.push(['-', phrase.corps].concat(phrase.texte.map((id) => '[' + id + ']')).join(' '));
      });
    });
    return lignes.join('\n');
  }

  function phrasesDe(lu) {
    return [].concat(...lu.rubriques.map((rubrique) => rubrique.phrases.map((phrase) =>
      Object.assign({ rubrique: rubrique.nom }, phrase))));
  }

  /** Taille d'une page comme la comptent les contrôles (§20.6) → { phrases, mots } (rubriques comprises, citations non). */
  function mesureDe(lu) {
    const phrases = phrasesDe(lu);
    return { phrases: phrases.length, mots: phrases.reduce((total, phrase) => total + Wiki.nombreDeMots(phrase.propre), 0)
      + lu.rubriques.reduce((total, rubrique) => total + Wiki.nombreDeMots(rubrique.nom), 0) };
  }

  /**
   * Taille de chaque rubrique (limites des textes rédigés, §20.12) → Map(rubrique comparable → { nom, phrases, mots }) :
   * mots de ses phrases sans citations, sans le nom de la rubrique ; une rubrique écrite deux fois compte en une (nom :
   * celui de sa première ligne).
   */
  function mesureDesRubriques(lu) {
    const mesures = new Map();
    lu.rubriques.forEach((rubrique) => {
      const cle = Wiki.comparable(rubrique.nom);
      if (!mesures.has(cle)) mesures.set(cle, { nom: rubrique.nom, phrases: 0, mots: 0 });
      const mesure = mesures.get(cle);
      mesure.phrases += rubrique.phrases.length;
      mesure.mots += rubrique.phrases.reduce((total, phrase) => total + Wiki.nombreDeMots(phrase.propre), 0);
    });
    return mesures;
  }

  /**
   * Changements d'une page (§20.6, §20.9) → { identiques, nouvelles, reprises: [{ phrase, anciennes }], retirees } :
   * une phrase d'après identique à une phrase d'avant est « identique » ; sinon, elle « reprend » les phrases d'avant
   * (non gardées telles quelles) dont elle cite tous les OT, ou elle est « nouvelle » ; une phrase d'avant ni gardée
   * ni reprise est « retirée ».
   */
  function comparerTextes(avant, apres) {
    const anciennes = phrasesDe(lireTexte(avant));
    const nouvelles = phrasesDe(lireTexte(apres));
    const identitesApres = new Set(nouvelles.map((phrase) => identitePhrase(phrase.texte)));
    const identitesAvant = new Set(anciennes.map((phrase) => identitePhrase(phrase.texte)));
    const gardees = anciennes.filter((phrase) => identitesApres.has(identitePhrase(phrase.texte)));
    const aReprendre = anciennes.filter((phrase) => !gardees.includes(phrase));
    const resultat = { identiques: [], nouvelles: [], reprises: [], retirees: [] };
    const reprisesAnciennes = new Set();
    nouvelles.forEach((phrase) => {
      if (identitesAvant.has(identitePhrase(phrase.texte))) { resultat.identiques.push(phrase); return; }
      const reprises = phrase.propre ? aReprendre.filter((ancienne) => ancienne.ot.length
        && ancienne.ot.every((id) => phrase.ot.includes(id))) : [];
      reprises.forEach((ancienne) => reprisesAnciennes.add(ancienne));
      if (reprises.length) resultat.reprises.push({ phrase, anciennes: reprises });
      else resultat.nouvelles.push(phrase);
    });
    resultat.retirees = aReprendre.filter((ancienne) => !reprisesAnciennes.has(ancienne));
    return resultat;
  }

  // ===========================================================================================
  // 2. Contrôles d'une proposition (§20.6)
  // ===========================================================================================

  /** Nombres d'un texte, normalisés (« 0,4 » → « 0.4 »). */
  function nombresDe(valeur) {
    return Array.from(String(valeur || '').matchAll(MOTIF_NOMBRE), (m) => m[0].replace(/,/g, '.'));
  }

  /** Forme de recherche d'un titre (mots vides retirés, pluriel simple, ordre indifférent). */
  function formeDuTitre(titre) {
    const mots = typeof Wiki.motsRecherche === 'function' ? Wiki.motsRecherche(titre) : Wiki.comparable(titre).split(' ');
    return sansDoublon(mots.filter(Boolean)).sort().join(' ');
  }

  function contientUnMot(valeur, liste) {
    const cadre = ' ' + Wiki.comparable(valeur) + ' ';
    return liste.filter((entree) => cadre.includes(' ' + entree + ' '));
  }

  function controlerDates(phrase, nom, raisons) {
    const forme = Wiki.comparable(sansReferences(phrase.texte));
    if (MOTIF_MOIS.test(forme) || MOTIF_ANNEE.test(forme) || MOTIF_DATE_CHIFFRES.test(sansReferences(phrase.texte))) {
      raisons.push(nom + ' : aucune date dans le wiki (les OT cités portent les leurs) — « ' + court(phrase.propre) + ' ».');
    }
  }

  /**
   * Préfixe du titre d'une sous-page (§20.4) : le repère d'une page d'équipement ancrée (son titre avant « — »),
   * sinon le titre entier de la mère. mere = { titre, type, mere } (mere.mere : titre de sa propre mère, vide sinon).
   */
  function prefixeSousPage(mere) {
    const titre = texte(mere && mere.titre);
    return mere && texte(mere.type) === 'équipement' && !texte(mere.mere) ? titre.split(' — ')[0].trim() : titre;
  }

  /** Le titre commence par « <préfixe> — » suivi d'au moins un mot (en forme comparable). */
  function suitLePrefixe(titre, prefixe) {
    const attendu = Wiki.comparable(prefixe);
    return Boolean(attendu) && Array.from(titre.matchAll(/—/g)).some((m) => Wiki.comparable(titre.slice(0, m.index)) === attendu
      && Wiki.comparable(titre.slice(m.index + 1)) !== '');
  }

  /**
   * Contrôles propres à une sous-page créée (§20.6) : mère envoyée, qui n'est pas elle-même une sous-page, modifiée par
   * la même proposition et qui renvoie à elle (sauf à la main), titre « <préfixe> — <sujet> ».
   */
  function controlerSousPage(page, nom, mere, ctx, raisons) {
    const titre = texte(page.titre);
    const nomMere = '« ' + texte(mere.titre) + ' »';
    if (!ctx.envoyeeDe.has(Wiki.comparable(mere.titre))) {
      raisons.push(nom + ' : sa page mère ' + nomMere + ' n\'a pas été envoyée (une sous-page se crée sous une page reçue).');
      return;
    }
    if (texte(mere.mere)) {
      raisons.push(nom + ' : sa page mère ' + nomMere + ' est elle-même une sous-page (de « ' + texte(mere.mere)
        + ' ») : un seul niveau, une sous-page ne se découpe pas.');
    }
    if (!ctx.manuel) {
      const modifiee = ctx.modifiees.get(Wiki.comparable(mere.titre));
      const renvoi = '[[' + titre + ']] qui cite les OT des phrases déplacées';
      if (!modifiee) {
        raisons.push(nom + ' : sa page mère ' + nomMere + ' n\'est pas modifiée par la proposition (elle garde une phrase de '
          + 'renvoi ' + renvoi + ').');
      } else if (!liensDe(modifiee.texte).some((lien) => Wiki.comparable(lien) === Wiki.comparable(titre))) {
        raisons.push(nom + ' : sa page mère ' + nomMere + ' ne renvoie pas à elle (phrase de renvoi ' + renvoi + ' attendue).');
      }
    }
    const prefixe = prefixeSousPage(mere);
    if (!suitLePrefixe(titre, prefixe)) {
      raisons.push(nom + ' : le titre d\'une sous-page commence par « ' + prefixe + ' — » suivi de son sujet.');
    }
  }

  /**
   * Longueurs d'un texte (§20.12, Wiki.LIMITES) : chaque rubrique d'un texte d'équipement ou de composant à sa limite ;
   * un savoir-faire en entier (Wiki.mesurerTexte), qui se découpe en sous-pages au-delà, sauf s'il en est une (§20.4).
   */
  function controlerLongueurs(lu, type, nom, sousPage, raisons) {
    const limites = Wiki.LIMITES[type] || { page: null, rubriques: {} };
    const mesures = mesureDesRubriques(lu);
    Object.keys(limites.rubriques).forEach((rubrique) => {
      const limite = limites.rubriques[rubrique];
      const mesure = mesures.get(Wiki.comparable(rubrique)) || { phrases: 0, mots: 0 };
      if (mesure.phrases > limite.phrases) {
        raisons.push(nom + ' : « ' + rubrique + ' » : ' + mesure.phrases + ' phrases, ' + limite.phrases + ' au plus.');
      }
      if (limite.mots !== null && mesure.mots > limite.mots) {
        raisons.push(nom + ' : « ' + rubrique + ' » : ' + mesure.mots + ' mots, ' + limite.mots + ' au plus (citations non comptées).');
      }
    });
    if (!limites.page) return;
    const decoupe = sousPage ? '' : 'au-delà, la page se découpe en sous-pages';
    const mesure = mesureDe(lu);
    if (mesure.phrases > limites.page.phrases) {
      raisons.push(nom + ' : ' + mesure.phrases + ' phrases, ' + limites.page.phrases + ' au plus'
        + (decoupe ? ' (' + decoupe + ')' : '') + '.');
    }
    if (mesure.mots > limites.page.mots) {
      raisons.push(nom + ' : ' + mesure.mots + ' mots, ' + limites.page.mots + ' au plus (rubriques comprises, citations non comptées'
        + (decoupe ? ' ; ' + decoupe : '') + ').');
    }
  }

  /** L'OT cité le plus récent d'une phrase, par date d'intervention (puis identifiant). */
  function plusRecent(ot, dates) {
    return ot.slice().sort((a, b) => String(dates.get(b) || '').localeCompare(String(dates.get(a) || ''))
      || b.localeCompare(a))[0];
  }

  /**
   * Contrôles d'une proposition de l'IA (ou d'une écriture à la main, contexte.manuel) → { ok, raisons } ; chaque
   * raison nomme la page. Rien n'est écrit.
   */
  function controlerProposition(proposition, contexte) {
    const ctx = contexte || {};
    const manuel = Boolean(ctx.manuel);
    const raisons = [];
    const envoyees = ctx.pagesEnvoyees || [];
    const envoyeeDe = new Map(envoyees.map((page) => [Wiki.comparable(page.titre), page]));
    const otIngere = ctx.otIngere || null;
    const dates = new Map();
    envoyees.forEach((page) => (page.otDates || []).forEach((entree) => dates.set(entree.id, texte(entree.date))));
    if (otIngere) dates.set(otIngere.id, texte(otIngere.dateIntervention));
    const permis = new Set(manuel ? (ctx.otPermis || []).map(texte)
      : [otIngere && otIngere.id].concat(...envoyees.map((page) => citationsDe(page.texte))).filter(Boolean));
    const pages = (proposition && proposition.pages) || [];
    const contradictions = (proposition && proposition.contradictions) || [];
    if (proposition && proposition.rien && (pages.length || contradictions.length)) {
      raisons.push('« Rien à ajouter » avec des pages ou des contradictions : la réponse se contredit.');
    }
    const creees = pages.filter((page) => page.action === 'creer');
    if (creees.length > SEUILS.pagesCreeesMax) {
      raisons.push('Proposition : ' + creees.length + ' pages créées, ' + SEUILS.pagesCreeesMax + ' au plus par OT.');
    }
    const connus = (ctx.catalogue || []).concat(envoyees).map((page) => texte(page.titre));
    const titresExistants = new Set(connus.map(Wiki.comparable));
    const titresConnus = new Set(connus.concat(creees.map((page) => texte(page.titre))).map(Wiki.comparable));
    const formes = new Map(connus.map((titre) => [formeDuTitre(titre), titre]));
    // Pages qu'un rattachement peut viser (type d'une sous-page) et pages modifiées (renvoi de la mère).
    const connuesDe = new Map(creees.concat(ctx.catalogue || [], envoyees).map((page) => [Wiki.comparable(page.titre), page]));
    const modifiees = new Map(pages.filter((page) => page.action === 'modifier').map((page) => [Wiki.comparable(page.titre), page]));
    pages.forEach((page) => controlerPage(page, {
      manuel, envoyeeDe, connuesDe, modifiees, otIngere, dates, permis, titresExistants, titresConnus, formes,
      sources: ctx.sources || {}, anterieure: Boolean(ctx.anterieure),
    }, raisons));
    contradictions.forEach((contradiction) => {
      const nom = 'Contradiction sur la page « ' + texte(contradiction.page) + ' »';
      const envoyee = envoyeeDe.get(Wiki.comparable(contradiction.page));
      if (!envoyee) { raisons.push(nom + ' : cette page n\'a pas été envoyée.'); return; }
      const existantes = new Set(phrasesDe(lireTexte(envoyee.texte)).map((phrase) => identitePhrase(phrase.texte)));
      if (!existantes.has(identitePhrase(contradiction.phrase))) {
        raisons.push(nom + ' : la phrase contredite n\'existe pas sur la page — « ' + court(contradiction.phrase) + ' ».');
      }
      const ot = ((contradiction.ot) || []).map(texte).filter(Boolean);
      if (!otIngere || !ot.length || ot.some((id) => id !== otIngere.id)) {
        raisons.push(nom + ' : elle doit citer l\'OT ingéré' + (otIngere ? ' (' + otIngere.id + ')' : '') + ', et lui seul.');
      }
      if (!texte(contradiction.observation)) raisons.push(nom + ' : l\'observation est vide.');
      const termes = Wiki.termesDeSecurite(contradiction.observation);
      if (termes.length) raisons.push(nom + ' : ' + MESSAGE_SECURITE[manuel ? 'manuel' : 'ia'] + ' (« ' + termes.join(' », « ') + ' »).');
    });
    return { ok: raisons.length === 0, raisons };
  }

  function controlerPage(page, ctx, raisons) {
    const titre = texte(page.titre);
    const nom = 'Page « ' + (titre || '(sans titre)') + ' »';
    const envoyee = ctx.envoyeeDe.get(Wiki.comparable(titre));
    let type = texte(page.type);
    let avant = '';
    let origine = '';               // texte d'où viennent ses phrases : son texte d'avant ; sous-page créée : celui de sa mère
    let titreMere = '';
    let sousPage = false;
    if (page.action === 'modifier') {
      if (!envoyee) {
        raisons.push(nom + ' : cette page n\'a pas été envoyée, elle ne peut pas être modifiée.');
        return;
      }
      type = texte(envoyee.type);
      if (!TYPES.includes(type)) { raisons.push(nom + ' : ' + typeInconnu(type)); return; }
      avant = envoyee.texte || '';
      origine = avant;
      sousPage = Boolean(texte(envoyee.mere));
    } else if (page.action === 'creer') {
      if (!TYPES.includes(type)) { raisons.push(nom + ' : ' + typeInconnu(type)); return; }
      const rattachement = ctx.envoyeeDe.get(Wiki.comparable(page.rattacheA));
      const visee = texte(page.rattacheA) ? ctx.connuesDe.get(Wiki.comparable(page.rattacheA)) : null;
      // Sous-page (§20.4) : rattachée à une page de même type. Seul un savoir-faire se crée, et lui seul a des
      // sous-pages (§20.12) : le texte d'une machine ou d'un article est celui de sa page, qui existe toujours.
      sousPage = Boolean(visee && texte(visee.type) === type);
      if (type !== 'savoir-faire') {
        raisons.push(nom + ' : ' + (sousPage ? 'une sous-page n\'existe que pour un savoir-faire (seul un savoir-faire se crée).'
          : TEXTE_DE_SA_PAGE[type]));
        return;
      }
      if (sousPage) {
        controlerSousPage(page, nom, visee, ctx, raisons);
        if (rattachement) { origine = rattachement.texte || ''; titreMere = texte(rattachement.titre); }
      }
      if (!sousPage && !(rattachement && ['équipement', 'composant'].includes(rattachement.type))) {
        raisons.push(nom + ' : un savoir-faire se rattache à une page envoyée (équipement ou composant).');
      } else if (!sousPage && texte(rattachement.mere)) {
        // Rattaché à une sous-page, il perdrait l'ancrage de l'équipement : ni envoyé avec ses OT, ni consignation.
        raisons.push(nom + ' : un savoir-faire se rattache à la page mère « ' + texte(rattachement.mere)
          + ' », jamais à une sous-page.');
      }
      if (ctx.titresExistants.has(Wiki.comparable(titre))) {
        raisons.push(nom + ' : une page de ce titre existe déjà.');
      } else if (ctx.formes.has(formeDuTitre(titre))) {
        raisons.push(nom + ' : titre trop proche de « ' + ctx.formes.get(formeDuTitre(titre)) + ' ».');
      }
      ctx.formes.set(formeDuTitre(titre), titre);
    } else {
      raisons.push(nom + ' : action « ' + texte(page.action) + ' » inconnue.');
      return;
    }
    const lu = lireTexte(page.texte);
    lu.erreurs.forEach((erreur) => raisons.push(nom + ' : ligne ' + erreur.ligne + ', ' + erreur.message + '.'));
    const rubriquesDuType = (Wiki.RUBRIQUES[type] || []).map(Wiki.comparable);
    lu.rubriques.forEach((rubrique) => {
      if (!rubriquesDuType.includes(Wiki.comparable(rubrique.nom))) {
        raisons.push(nom + ' : rubrique « ' + rubrique.nom + ' » inconnue pour une page ' + type + '.');
      }
    });
    const phrases = phrasesDe(lu);
    if (!phrases.length) raisons.push(nom + ' : aucune phrase.');
    controlerLongueurs(lu, type, nom, sousPage, raisons);
    phrases.forEach((phrase) => {
      if (!phrase.propre) raisons.push(nom + ' : phrase vide (réduite à ses citations).');
      if (!phrase.ot.length) raisons.push(nom + ' : phrase sans OT cité — « ' + court(phrase.propre) + ' ».');
      const horsListe = phrase.ot.filter((id) => !ctx.permis.has(id));
      if (horsListe.length) raisons.push(nom + ' : OT cité hors des OT permis : ' + horsListe.join(', ') + '.');
      phrase.liens.filter((lien) => !ctx.titresConnus.has(Wiki.comparable(lien)))
        .forEach((lien) => raisons.push(nom + ' : lien vers une page inconnue « ' + lien + ' ».'));
    });
    // Non-retrait (D106) : seulement pour l'IA ; le responsable peut retirer. Sous-page créée : ses phrases se comparent
    // au texte d'avant de sa mère (une phrase déplacée telle quelle y est « identique »).
    const changements = comparerTextes(origine, page.texte);
    if (!ctx.manuel && page.action === 'modifier') {
      const apres = new Set(citationsDe(page.texte));
      const perdus = citationsDe(avant).filter((id) => !apres.has(id));
      if (perdus.length) raisons.push(nom + ' : OT cité retiré de la page : ' + perdus.join(', ') + '.');
      changements.retirees.forEach((phrase) => raisons.push(nom + ' : phrase retirée — « ' + court(phrase.propre) + ' ».'));
      phrasesDe(lireTexte(avant)).forEach((ancienne) => {
        const memes = phrases.filter((phrase) => identitePhrase(phrase.texte) === identitePhrase(ancienne.texte));
        const manquants = memes.length ? ancienne.ot.filter((id) => !memes.some((phrase) => phrase.ot.includes(id))) : [];
        if (manquants.length) {
          raisons.push(nom + ' : OT retiré de la phrase « ' + court(ancienne.propre) + ' » : ' + manquants.join(', ') + '.');
        }
      });
    }
    // Phrases à contrôler en entier : nouvelles et reprises (une phrase identique à avant a déjà été contrôlée).
    const aControler = changements.nouvelles.concat(changements.reprises.map((reprise) => reprise.phrase));
    const reference = (ctx.manuel
      ? Array.from(new Set(phrases.flatMap((phrase) => phrase.ot))).map((id) => ctx.sources[id] || '').join('\n')
      : (ctx.otIngere && ctx.otIngere.sourceTexte) || '') + '\n' + origine + '\n' + titreMere;
    const nombresConnus = new Set(nombresDe(sansReferences(reference)));
    const nombresTitre = page.action === 'creer' ? nombresDe(sansReferences(titre)) : [];
    nombresTitre.filter((nombre) => !nombresConnus.has(nombre))
      .forEach((nombre) => raisons.push(nom + ' : nombre « ' + nombre + ' » du titre absent des OT.'));
    aControler.forEach((phrase) => {
      nombresDe(sansReferences(phrase.texte)).filter((nombre) => !nombresConnus.has(nombre)).forEach((nombre) =>
        raisons.push(nom + ' : nombre « ' + nombre + ' » absent des OT cités — « ' + court(phrase.propre) + ' ».'));
      if (MOTIF_COMPTAGE.test(Wiki.comparable(sansReferences(phrase.texte)))) {
        raisons.push(nom + ' : comptage interdit (les nombres de cas sont calculés par Prévo) — « ' + court(phrase.propre) + ' ».');
      }
      controlerDates(phrase, nom, raisons);
      if (ctx.anterieure && ctx.otIngere && phrase.ot.includes(ctx.otIngere.id)
        && plusRecent(phrase.ot, ctx.dates) === ctx.otIngere.id) {
        const mots = contientUnMot(sansReferences(phrase.texte), Wiki.VOCABULAIRE_NOUVEAUTE);
        if (mots.length) {
          raisons.push(nom + ' : intervention antérieure à des faits déjà intégrés, elle ne peut pas être présentée comme '
            + 'la plus récente (« ' + mots.join(' », « ') + ' ») — « ' + court(phrase.propre) + ' ».');
        }
      }
    });
    const termes = Wiki.termesDeSecurite(titre + '\n' + (page.texte || ''));
    if (termes.length) raisons.push(nom + ' : ' + MESSAGE_SECURITE[ctx.manuel ? 'manuel' : 'ia'] + ' (« ' + termes.join(' », « ') + ' »).');
  }

  return {
    lireTexte, ecrireTexte, comparerTextes, controlerProposition, formeDuTitre, prefixeSousPage,
    identitePhrase, citationsDe, liensDe, phrasesDe: (valeur) => phrasesDe(lireTexte(valeur)),
    mesurerTexte: (valeur) => mesureDe(lireTexte(valeur)),
    // { <rubrique>: { phrases, mots } } (mots sans le nom de la rubrique), pour les limites de Wiki.LIMITES (§20.12).
    mesurerRubriques: (valeur) => Object.fromEntries(Array.from(mesureDesRubriques(lireTexte(valeur)).values(),
      (mesure) => [mesure.nom, { phrases: mesure.phrases, mots: mesure.mots }])),
  };
})());
