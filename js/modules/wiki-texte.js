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
//    texte, otDates: [{ id, date }] }], catalogue: [{ titre, type }] } ; écriture à la main : { manuel: true,
//    pagesEnvoyees (la page écrite), catalogue, otPermis: [identifiants], sources: { otId: texte } } ;
//  - les nombres d'une phrase identique à une phrase d'avant ne sont pas recontrôlés ; ceux d'une phrase nouvelle
//    ou reprise et du titre d'une page créée doivent figurer dans le texte de référence (l'OT ingéré et le texte
//    d'avant de la page ; à la main : les OT cités) ; « 0,4 » et « 0.4 » sont le même nombre ;
//  - dates : un nom de mois, une date en chiffres (« 12/03 », « 3/10/2026 », « 2026-06-08 ») ou une année 19xx ou
//    20xx qui n'est pas suivie d'une unité (« l'entretien des 2000 heures » n'est pas une date) ;
//  - les numéros d'OT (cités ou écrits dans le texte) ne comptent jamais comme des nombres, ni dans une phrase ni
//    dans le texte de référence ; une phrase réduite à ses citations est « vide » et refusée ;
//  - un savoir-faire se rattache à une page envoyée d'équipement ou de composant ; une phrase gardée telle quelle
//    garde tous ses OT ;
//  - comptage : un nombre en chiffres, ou de « deux » à « cent » en lettres, suivi de « fois », « OT »,
//    « intervention(s) », « panne(s) », « cas » ou « remplacement(s) » (« une fois remontée » est permis).

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
    pages.forEach((page) => controlerPage(page, {
      manuel, envoyeeDe, otIngere, dates, permis, titresExistants, titresConnus, formes, sources: ctx.sources || {},
      anterieure: Boolean(ctx.anterieure),
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
    if (page.action === 'modifier') {
      if (!envoyee) {
        raisons.push(nom + ' : cette page n\'a pas été envoyée, elle ne peut pas être modifiée.');
        return;
      }
      type = envoyee.type;
      avant = envoyee.texte || '';
    } else if (page.action === 'creer') {
      if (!TYPES.includes(type)) { raisons.push(nom + ' : type « ' + type + ' » inconnu.'); return; }
      if (type === 'équipement') raisons.push(nom + ' : une page d\'équipement ne se crée pas, elle existe déjà.');
      const rattachement = ctx.envoyeeDe.get(Wiki.comparable(page.rattacheA));
      if (type === 'savoir-faire' && !(rattachement && ['équipement', 'composant'].includes(rattachement.type))) {
        raisons.push(nom + ' : un savoir-faire se rattache à une page envoyée (équipement ou composant).');
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
    if (phrases.length > SEUILS.phrasesMax) raisons.push(nom + ' : ' + phrases.length + ' phrases, ' + SEUILS.phrasesMax + ' au plus.');
    const mots = mesureDe(lu).mots;
    if (mots > SEUILS.motsMax) raisons.push(nom + ' : ' + mots + ' mots, ' + SEUILS.motsMax + ' au plus (rubriques comprises, citations non comptées).');
    phrases.forEach((phrase) => {
      if (!phrase.propre) raisons.push(nom + ' : phrase vide (réduite à ses citations).');
      if (!phrase.ot.length) raisons.push(nom + ' : phrase sans OT cité — « ' + court(phrase.propre) + ' ».');
      const horsListe = phrase.ot.filter((id) => !ctx.permis.has(id));
      if (horsListe.length) raisons.push(nom + ' : OT cité hors des OT permis : ' + horsListe.join(', ') + '.');
      phrase.liens.filter((lien) => !ctx.titresConnus.has(Wiki.comparable(lien)))
        .forEach((lien) => raisons.push(nom + ' : lien vers une page inconnue « ' + lien + ' ».'));
    });
    // Non-retrait (D106) : seulement pour l'IA ; le responsable peut retirer.
    const changements = comparerTextes(avant, page.texte);
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
      : (ctx.otIngere && ctx.otIngere.sourceTexte) || '') + '\n' + avant;
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
    lireTexte, ecrireTexte, comparerTextes, controlerProposition, formeDuTitre,
    identitePhrase, citationsDe, liensDe, phrasesDe: (valeur) => phrasesDe(lireTexte(valeur)),
    mesurerTexte: (valeur) => mesureDe(lireTexte(valeur)),
  };
})());
