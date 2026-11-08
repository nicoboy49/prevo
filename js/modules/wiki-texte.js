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
//    d'avant de la page — rien pour une page créée, le texte et le titre de sa mère pour une sous-page créée ; à la main :
//    les OT cités) ; « 0,4 » et « 0.4 » sont le même nombre ; le refus dit ce texte de référence (« absent de l'OT
//    intégré et du texte d'avant de cette page », « … de l'OT intégré, seule source des nombres d'une page créée »,
//    « … de l'OT intégré, du texte et du titre de sa page mère » ; à la main : « absent des OT cités ») ;
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
//    reprise sont cherchés aussi dans le texte et le titre de la mère) ;
//  - rubrique réécrite en entier (D117, Wiki.RUBRIQUES_REECRITES : « En bref ») d'une page modifiée par l'IA : ni « phrase
//    retirée », ni « OT retiré », ni reprise — ses phrases d'avant ne comptent pas, ni ses phrases d'après pour garder
//    celles d'une autre rubrique du type (une astuce reste dans « Astuces ») ; une phrase d'une ancienne rubrique (hors
//    du type) peut s'y réécrire ; toutes ses phrases sont contrôlées comme nouvelles (citations, nombres, comptage, dates,
//    nouveauté, sécurité, liens, longueurs) ; à la main, rien ne change ;
//  - même geste (D116, Wiki.memeGeste) : un savoir-faire dont au moins MEME_GESTE.motsMin mots du titre, et au moins
//    MEME_GESTE.partMin de ses mots (forme de la recherche, Wiki.motsRecherche), sont dans le texte de l'OT.

Object.assign(Wiki, (() => {

  const SEUILS = Wiki.SEUILS;
  const TYPES = Object.keys(Wiki.RUBRIQUES);
  const PARTICULARITES = Wiki.comparable(Wiki.RUBRIQUES['savoir-faire'][4]);   // « Particularités par machine » (D116)
  const MOTIF_RUBRIQUE = /^##\s+(.+?)\s*$/;
  const MOTIF_PHRASE = /^-\s+(.*)$/;
  const MOTIF_CITATION = /\[(OT-\d{4}-\d{4,})\]/g;
  const MOTIF_LIEN = /\[\[([^[\]]+)\]\]/g;
  const MOTIF_NOMBRE = /\d+(?:[.,]\d+)*/g;
  const MOTS_NOMBRES = ['deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit', 'neuf', 'dix', 'onze', 'douze',
    'treize', 'quatorze', 'quinze', 'seize', 'vingt', 'trente', 'quarante', 'cinquante', 'soixante', 'cent',
    // Lot 5 (T374) : anglais, turc, italien, portugais (forme comparable)
    'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve', 'twenty', 'thirty',
    'hundred', 'iki', 'uc', 'dort', 'bes', 'alti', 'yedi', 'sekiz', 'dokuz', 'yirmi', 'otuz', 'yuz',
    'due', 'tre', 'quattro', 'cinque', 'sei', 'sette', 'otto', 'nove', 'dieci', 'venti', 'trenta', 'cento',
    'dois', 'duas', 'tres', 'quatro', 'cinco', 'seis', 'sete', 'oito', 'nove', 'dez', 'vinte', 'trinta', 'cem'];
  const COMPTES = ['fois', 'ot', 'interventions?', 'pannes?', 'cas', 'remplacements?',
    'times', 'work orders?', 'wos?', 'failures?', 'breakdowns?', 'cases', 'replacements?',
    'kez', 'kere', 'defa', 'is emri', 'ariza', 'vaka', 'degisim', 'mudahale',
    'volte', 'odl', 'interventi', 'guasti', 'casi', 'sostituzioni',
    'vezes', 'intervencoes', 'avarias', 'casos', 'substituicoes'];
  const MOTIF_COMPTAGE = new RegExp('(?:^| )(?:\\d+|' + MOTS_NOMBRES.join('|')
    + ') (?:' + COMPTES.join('|') + ')(?= |$)');
  const MOIS = ['janvier', 'fevrier', 'mars', 'avril', 'mai', 'juin', 'juillet', 'aout', 'septembre', 'octobre',
    'novembre', 'decembre',
    // Lot 5 (T374). Mois qui sont aussi des mots courants, écartés (refus à tort) : « may » (anglais), « ocak »
    // (fourneau), « ekim » (semis), « aralik » (intervalle, fréquent en maintenance) en turc.
    'january', 'february', 'march', 'april', 'june', 'july', 'august', 'september', 'october', 'november', 'december',
    'subat', 'mart', 'nisan', 'mayis', 'haziran', 'temmuz', 'agustos', 'eylul', 'kasim',
    'gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio', 'agosto', 'settembre', 'ottobre',
    'dicembre', 'janeiro', 'fevereiro', 'abril', 'maio', 'junho', 'julho', 'setembro', 'outubro', 'novembro',
    'dezembro'];
  const MOTIF_MOIS = new RegExp('(?:^| )(?:' + MOIS.join('|') + ')(?= |$)');
  // Unités qui font d'un 19xx ou 20xx une quantité ; pas d'unité d'une lettre ambiguë (« en 2026 a été… »).
  const UNITES = 'h|heures?|bars?|mm|cm|km|kg|tr|tours?|litres?|kw|kva|mn|min|minutes?|secondes?|pieces?|cycles?'
    + '|hours?|hrs?|liters?|rpm|turns?|parts?|saat|dakika|devir|parca|ore|litri|giri|pezzi|horas?|litros?|voltas?|pecas';
  const MOTIF_ANNEE = new RegExp('(?:^| )(?:19|20)\\d{2}(?= |$)(?! (?:' + UNITES + ')(?: |$))');
  const MOTIF_DATE_CHIFFRES = /(?:^|[^\d/.-])(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/.]\d{1,2}[/.]\d{2,4}|\d{2}[/.]\d{2})(?![\d/.])/;
  const MOTIF_NUMERO_OT = /\bOT-\d{4}-\d{4,}\b/g;
  const messageSecurite = (manuel) => (manuel ? Wiki.MESSAGE_SECURITE_MAIN : Wiki.MESSAGE_SECURITE_IA);   // lu à l'appel
  // Même geste (D116) : savoir-faire envoyés avec un OT parce que leur titre (le geste et l'organe) est dans son texte.
  const MEME_GESTE = Object.freeze({ motsMin: 2, partMin: 0.6, pagesMax: 2 });
  // Où un nombre d'une proposition de l'IA a été cherché, dit dans son refus (texte de référence, précisions en tête).
  function sourceDesNombres(page, titreMere) {
    if (page.action === 'modifier') return I18n.t('wiki.source_des_nombres.ot_integre_texte_avant');
    return titreMere ? I18n.t('wiki.source_des_nombres.ot_integre_texte_titre') : I18n.t('wiki.source_des_nombres.ot_integre_seule_source');
  }
  // Refus de la création d'un texte ancré (§20.12) : il existe toujours, sur la page de sa machine ou de son article.
  function texteDeSaPage(type, nom) {
    if (type === 'équipement') {
      return I18n.t('wiki.texte_de_sa_page.page_equipement_cree_pas', { nom });
    }
    return I18n.t('wiki.texte_de_sa_page.page_composant_cree_pas', { nom });
  }

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  function sansDoublon(liste) {
    return Array.from(new Set(liste));
  }

  function court(valeur) {
    const propre = texte(valeur).replace(/\s+/g, ' ');
    return propre.length > 70 ? I18n.t('wiki.court.coupe', { debut: propre.slice(0, 69) }) : propre;
  }

  /** Refus d'un type hors de Wiki.RUBRIQUES (« mode », retiré par la refonte 2 : une panne est une page calculée). */
  function typeInconnu(type) {
    return I18n.t('wiki.type_inconnu.type_inconnu', { type, types: TYPES.join(', ') });
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
      erreurs.push({ ligne: rang + 1, message: phrase ? I18n.t('wiki.lire_texte.phrase_ecrite_avant_toute')
        : I18n.t('wiki.lire_texte.ligne_hors_forme_rubrique') });
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

  /** Mots de recherche d'un texte (mots vides retirés, pluriel simple : Wiki.motsRecherche), sans doublon. */
  function motsDe(valeur) {
    const mots = typeof Wiki.motsRecherche === 'function' ? Wiki.motsRecherche(valeur) : Wiki.comparable(valeur).split(' ');
    return sansDoublon(mots.filter(Boolean));
  }

  /** Forme de recherche d'un titre (mots vides retirés, pluriel simple, ordre indifférent). */
  function formeDuTitre(titre) {
    return motsDe(titre).sort().join(' ');
  }

  /**
   * Savoir-faire du même geste qu'un texte (D116, §20.5) : parmi `pages` ([{ titre, cle }]), au plus MEME_GESTE.pagesMax
   * dont au moins motsMin mots du titre, et au moins partMin de ses mots, sont dans le texte ; la plus grande part
   * d'abord, puis le plus de mots trouvés, puis le titre et la clé (ordre des caractères : déterministe).
   */
  function memeGeste(valeur, pages) {
    const mots = new Set(motsDe(valeur));
    const ordre = (a, b) => (a < b ? -1 : (a > b ? 1 : 0));
    return (pages || []).map((page) => {
      const titre = motsDe(page.titre);
      const trouves = titre.filter((mot) => mots.has(mot)).length;
      return { page, trouves, part: titre.length ? trouves / titre.length : 0 };
    }).filter((x) => x.trouves >= MEME_GESTE.motsMin && x.part >= MEME_GESTE.partMin)
      .sort((a, b) => b.part - a.part || b.trouves - a.trouves || ordre(texte(a.page.titre), texte(b.page.titre))
        || ordre(texte(a.page.cle), texte(b.page.cle)))
      .slice(0, MEME_GESTE.pagesMax).map((x) => x.page);
  }

  /** Le texte réduit aux rubriques que `garder(nom en forme comparable)` retient (leur ligne « ## » et leurs phrases). */
  function filtrerRubriques(valeur, garder) {
    let gardee = true;
    return String(valeur || '').replace(/\r\n?/g, '\n').split('\n').filter((ligne) => {
      const titre = MOTIF_RUBRIQUE.exec(ligne.trim());
      if (titre) gardee = garder(Wiki.comparable(titre[1]));
      return gardee;
    }).join('\n');
  }

  /**
   * Non-retrait (D106) des phrases d'`avant` dans `apres`, pour une page modifiée par l'IA → { perdus (OT d'avant absents
   * d'après), retirees (phrases ni gardées ni reprises), manquants: [{ ancienne, ot }] (OT d'une phrase gardée telle quelle
   * qu'elle ne cite plus) }.
   */
  function nonRetrait(avant, apres) {
    const restants = new Set(citationsDe(apres));
    const phrases = phrasesDe(lireTexte(apres));
    const manquants = [];
    phrasesDe(lireTexte(avant)).forEach((ancienne) => {
      const memes = phrases.filter((phrase) => identitePhrase(phrase.texte) === identitePhrase(ancienne.texte));
      const ot = memes.length ? ancienne.ot.filter((id) => !memes.some((phrase) => phrase.ot.includes(id))) : [];
      if (ot.length) manquants.push({ ancienne, ot });
    });
    return { perdus: citationsDe(avant).filter((id) => !restants.has(id)), retirees: comparerTextes(avant, apres).retirees, manquants };
  }

  function contientUnMot(valeur, liste) {
    const cadre = ' ' + Wiki.comparable(valeur) + ' ';
    return liste.filter((entree) => cadre.includes(' ' + entree + ' '));
  }

  function controlerDates(phrase, nom, raisons) {
    const forme = Wiki.comparable(sansReferences(phrase.texte));
    if (MOTIF_MOIS.test(forme) || MOTIF_ANNEE.test(forme) || MOTIF_DATE_CHIFFRES.test(sansReferences(phrase.texte))) {
      raisons.push(I18n.t('wiki.controler_dates.aucune_date_wiki_ot', { nom, court: court(phrase.propre) }));
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
      raisons.push(I18n.t('wiki.controler_sous_page.page_mere_pas_ete', { nom, nomMere }));
      return;
    }
    if (texte(mere.mere)) {
      raisons.push(I18n.t('wiki.controler_sous_page.page_mere_meme_sous', { nom, nomMere, mere: texte(mere.mere) }));
    }
    if (!ctx.manuel) {
      const modifiee = ctx.modifiees.get(Wiki.comparable(mere.titre));
      const renvoi = I18n.t('wiki.controler_sous_page.cite_ot_phrases_deplacees', { titre });
      if (!modifiee) {
        raisons.push(I18n.t('wiki.controler_sous_page.page_mere_pas_modifiee', { nom, nomMere, renvoi }));
      } else if (!liensDe(modifiee.texte).some((lien) => Wiki.comparable(lien) === Wiki.comparable(titre))) {
        raisons.push(I18n.t('wiki.controler_sous_page.page_mere_renvoie_pas', { nom, nomMere, renvoi }));
      }
    }
    const prefixe = prefixeSousPage(mere);
    if (!suitLePrefixe(titre, prefixe)) {
      raisons.push(I18n.t('wiki.controler_sous_page.titre_sous_page_commence', { nom, prefixe }));
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
        raisons.push(I18n.t('wiki.controler_longueurs.phrases_plus', { nom, rubrique, n: mesure.phrases, limite: limite.phrases }));
      }
      if (limite.mots !== null && mesure.mots > limite.mots) {
        raisons.push(I18n.t('wiki.controler_longueurs.mots_plus_citations_non', { nom, rubrique, n: mesure.mots, limite: limite.mots }));
      }
    });
    if (!limites.page) return;
    const mesure = mesureDe(lu);
    const phrases = mesure.phrases;
    const mots = mesure.mots;
    const plafond = limites.page;
    if (phrases > plafond.phrases) {
      raisons.push(sousPage ? I18n.t('wiki.controler_longueurs.phrases_plus_sous_page', { nom, n: phrases, limite: plafond.phrases })
        : I18n.t('wiki.controler_longueurs.phrases_plus_dela_page', { nom, n: phrases, limite: plafond.phrases }));
    }
    if (mots > plafond.mots) {
      raisons.push(sousPage ? I18n.t('wiki.controler_longueurs.mots_plus_rubriques_comprises', { nom, n: mots, limite: plafond.mots })
        : I18n.t('wiki.controler_longueurs.mots_plus_dela_page', { nom, n: mots, limite: plafond.mots }));
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
      raisons.push(I18n.t('wiki.controler_proposition.rien_ajouter_pages_contradictions'));
    }
    const creees = pages.filter((page) => page.action === 'creer');
    if (creees.length > SEUILS.pagesCreeesMax) {
      raisons.push(I18n.t('wiki.controler_proposition.proposition_pages_creees_plus', { n: creees.length, maximum: SEUILS.pagesCreeesMax }));
    }
    const connus = (ctx.catalogue || []).concat(envoyees).map((page) => texte(page.titre));
    const titresExistants = new Set(connus.map(Wiki.comparable));
    const titresConnus = new Set(connus.concat(creees.map((page) => texte(page.titre))).map(Wiki.comparable));
    const formes = new Map(connus.map((titre) => [formeDuTitre(titre), titre]));
    // Pages qu'un rattachement peut viser (type d'une sous-page) et pages modifiées (renvoi de la mère).
    const connuesDe = new Map(creees.concat(ctx.catalogue || [], envoyees).map((page) => [Wiki.comparable(page.titre), page]));
    const modifiees = new Map(pages.filter((page) => page.action === 'modifier').map((page) => [Wiki.comparable(page.titre), page]));
    // Savoir-faire connus (hors sous-pages) : un seul par geste (D116, relecture de T141).
    const savoirFaire = (ctx.catalogue || []).concat(envoyees)
      .filter((page) => texte(page.type) === 'savoir-faire' && !texte(page.mere)).map((page) => texte(page.titre));
    pages.forEach((page) => controlerPage(page, {
      manuel, envoyeeDe, connuesDe, modifiees, otIngere, dates, permis, titresExistants, titresConnus, formes, savoirFaire,
      sources: ctx.sources || {}, anterieure: Boolean(ctx.anterieure),
    }, raisons));
    contradictions.forEach((contradiction) => {
      const nom = I18n.t('wiki.controler_proposition.contradiction_page', { page: texte(contradiction.page) });
      const envoyee = envoyeeDe.get(Wiki.comparable(contradiction.page));
      if (!envoyee) { raisons.push(I18n.t('wiki.controler_proposition.page_pas_ete_envoyee', { nom })); return; }
      const existantes = new Set(phrasesDe(lireTexte(envoyee.texte)).map((phrase) => identitePhrase(phrase.texte)));
      if (!existantes.has(identitePhrase(contradiction.phrase))) {
        raisons.push(I18n.t('wiki.controler_proposition.phrase_contredite_existe_pas', { nom, court: court(contradiction.phrase) }));
      }
      const ot = ((contradiction.ot) || []).map(texte).filter(Boolean);
      if (!otIngere || !ot.length || ot.some((id) => id !== otIngere.id)) {
        raisons.push(otIngere ? I18n.t('wiki.controler_proposition.doit_citer_ot_ingere', { nom, otIngereId: otIngere.id })
          : I18n.t('wiki.controler_proposition.doit_citer_ot_ingere_sans_numero', { nom }));
      }
      if (!texte(contradiction.observation)) raisons.push(I18n.t('wiki.controler_proposition.observation_vide', { nom }));
      const termes = Wiki.termesDeSecurite(contradiction.observation);
      if (termes.length) raisons.push(I18n.t('wiki.controler_page.securite', { nom, message: messageSecurite(manuel), termes: termes.join(' », « ') }));
    });
    return { ok: raisons.length === 0, raisons };
  }

  function controlerPage(page, ctx, raisons) {
    const titre = texte(page.titre);
    const nom = I18n.t('wiki.controler_page.nom_page', { titre: (titre || I18n.t('wiki.controler_page.sans_titre')) });
    const envoyee = ctx.envoyeeDe.get(Wiki.comparable(titre));
    let type = texte(page.type);
    let avant = '';
    let origine = '';               // texte d'où viennent ses phrases : son texte d'avant ; sous-page créée : celui de sa mère
    let titreMere = '';
    let sousPage = false;
    if (page.action === 'modifier') {
      if (!envoyee) {
        raisons.push(I18n.t('wiki.controler_page.page_pas_ete_envoyee', { nom }));
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
        raisons.push(sousPage ? I18n.t('wiki.controler_page.sous_page_existe_savoir', { nom }) : texteDeSaPage(type, nom));
        return;
      }
      if (sousPage) {
        controlerSousPage(page, nom, visee, ctx, raisons);
        if (rattachement) { origine = rattachement.texte || ''; titreMere = texte(rattachement.titre); }
      }
      if (!sousPage && !(rattachement && ['équipement', 'composant'].includes(rattachement.type))) {
        raisons.push(I18n.t('wiki.controler_page.savoir_faire_rattache_page', { nom }));
      } else if (!sousPage && texte(rattachement.mere)) {
        // Rattaché à une sous-page, il perdrait l'ancrage de l'équipement : ni envoyé avec ses OT, ni consignation.
        raisons.push(I18n.t('wiki.controler_page.savoir_faire_rattache_mere', { nom, mere: texte(rattachement.mere) }));
      }
      if (ctx.titresExistants.has(Wiki.comparable(titre))) {
        raisons.push(I18n.t('wiki.controler_page.page_titre_existe_deja', { nom }));
      } else if (ctx.formes.has(formeDuTitre(titre))) {
        raisons.push(I18n.t('wiki.controler_page.titre_trop_proche', { nom, titre: ctx.formes.get(formeDuTitre(titre)) }));
      } else if (!sousPage) {
        // Même geste (D116) : l'organe d'un savoir-faire connu (son titre sans son premier mot, 2 mots au moins) est
        // tout entier dans le titre créé (« Changer une garniture mécanique » face à « Remplacer une garniture mécanique »).
        const mots = new Set(motsDe(titre));
        const meme = (ctx.savoirFaire || []).find((connu) => {
          const organe = motsDe(connu).slice(1);
          return organe.length >= 2 && organe.every((mot) => mots.has(mot));
        });
        if (meme) {
          raisons.push(ctx.envoyeeDe.has(Wiki.comparable(meme)) ? I18n.t('wiki.controler_page.meme_geste_completer', { nom, meme })
            : I18n.t('wiki.controler_page.meme_geste_lien', { nom, meme }));
        }
      }
      ctx.formes.set(formeDuTitre(titre), titre);
    } else {
      raisons.push(I18n.t('wiki.controler_page.action_inconnue', { nom, action: texte(page.action) }));
      return;
    }
    const lu = lireTexte(page.texte);
    lu.erreurs.forEach((erreur) => raisons.push(nom + ' : ligne ' + erreur.ligne + ', ' + erreur.message + '.'));
    const rubriquesDuType = (Wiki.RUBRIQUES[type] || []).map(Wiki.comparable);
    lu.rubriques.forEach((rubrique) => {
      if (!rubriquesDuType.includes(Wiki.comparable(rubrique.nom))) {
        raisons.push(I18n.t('wiki.controler_page.rubrique_inconnue_page', { nom, rubriqueNom: rubrique.nom, type }));
      }
    });
    const phrases = phrasesDe(lu);
    if (!phrases.length) raisons.push(I18n.t('wiki.controler_page.aucune_phrase', { nom }));
    controlerLongueurs(lu, type, nom, sousPage, raisons);
    phrases.forEach((phrase) => {
      if (!phrase.propre) raisons.push(I18n.t('wiki.controler_page.phrase_vide_reduite_citations', { nom }));
      if (!phrase.ot.length) raisons.push(I18n.t('wiki.controler_page.phrase_sans_ot_cite', { nom, court: court(phrase.propre) }));
      const horsListe = phrase.ot.filter((id) => !ctx.permis.has(id));
      if (horsListe.length) raisons.push(I18n.t('wiki.controler_page.ot_cite_hors_ot', { nom, ot: horsListe.join(', ') }));
      phrase.liens.filter((lien) => !ctx.titresConnus.has(Wiki.comparable(lien)))
        .forEach((lien) => raisons.push(I18n.t('wiki.controler_page.lien_vers_page_inconnue', { nom, lien })));
    });
    // « Particularités par machine » (D116) : chaque phrase relie sa machine ([[repère — nom]]), sans quoi le savoir-faire
    // n'est ni envoyé avec les OT de cette machine ni listé sur sa page. Pour l'IA seulement.
    if (type === 'savoir-faire' && !ctx.manuel) {
      lu.rubriques.filter((rubrique) => Wiki.comparable(rubrique.nom) === PARTICULARITES).forEach((rubrique) => {
        rubrique.phrases.filter((phrase) => !phrase.liens.some((lien) => {
          const cible = ctx.connuesDe.get(Wiki.comparable(lien));
          return cible && texte(cible.type) === 'équipement';
        })).forEach((phrase) => raisons.push(I18n.t('wiki.controler_page.particularites_machine_phrase_sans', { nom, court: court(phrase.propre) })));
      });
    }
    // Non-retrait (D106) : seulement pour l'IA ; le responsable peut retirer. Sous-page créée : ses phrases se comparent
    // au texte d'avant de sa mère (une phrase déplacée telle quelle y est « identique »). Rubrique réécrite en entier
    // (D117, Wiki.RUBRIQUES_REECRITES) : hors du non-retrait, des deux côtés (précisions en tête) ; une ancienne rubrique
    // (hors du type) se compare à tout le texte d'après, où elle se réécrit.
    const reecrites = ctx.manuel ? [] : (Wiki.RUBRIQUES_REECRITES[type] || []).map(Wiki.comparable);
    const changements = comparerTextes(origine, page.texte);
    if (!ctx.manuel && page.action === 'modifier') {
      const horsReecrites = (rubrique) => !reecrites.includes(rubrique);
      const gardees = nonRetrait(filtrerRubriques(avant, (rubrique) => rubriquesDuType.includes(rubrique) && horsReecrites(rubrique)),
        filtrerRubriques(page.texte, horsReecrites));
      const anciennes = nonRetrait(filtrerRubriques(avant, (rubrique) => !rubriquesDuType.includes(rubrique)), page.texte);
      const perdus = sansDoublon(gardees.perdus.concat(anciennes.perdus));
      if (perdus.length) raisons.push(I18n.t('wiki.controler_page.ot_cite_retire_page', { nom, ot: perdus.join(', ') }));
      gardees.retirees.concat(anciennes.retirees)
        .forEach((phrase) => raisons.push(I18n.t('wiki.controler_page.phrase_retiree', { nom, court: court(phrase.propre) })));
      gardees.manquants.concat(anciennes.manquants).forEach(({ ancienne, ot }) =>
        raisons.push(I18n.t('wiki.controler_page.ot_retire_phrase', { nom, court: court(ancienne.propre), ot: ot.join(', ') })));
    }
    // Phrases à contrôler en entier : nouvelles et reprises (une phrase identique à avant a déjà été contrôlée), et toutes
    // celles d'une rubrique réécrite (D117).
    const aControler = changements.nouvelles.concat(changements.reprises.map((reprise) => reprise.phrase),
      changements.identiques.filter((phrase) => reecrites.includes(Wiki.comparable(phrase.rubrique))));
    const reference = (ctx.manuel
      ? Array.from(new Set(phrases.flatMap((phrase) => phrase.ot))).map((id) => ctx.sources[id] || '').join('\n')
      : (ctx.otIngere && ctx.otIngere.sourceTexte) || '') + '\n' + origine + '\n' + titreMere;
    const nombresConnus = new Set(nombresDe(sansReferences(reference)));
    // Le refus dit où le nombre a été cherché : la raison d'une relance doit permettre de corriger (T140).
    const source = ctx.manuel ? null : sourceDesNombres(page, titreMere);
    const nombresTitre = page.action === 'creer' ? nombresDe(sansReferences(titre)) : [];
    nombresTitre.filter((nombre) => !nombresConnus.has(nombre))
      .forEach((nombre) => raisons.push(I18n.t('wiki.controler_page.nombre_titre_absent', { nom, nombre, source: (source || I18n.t('wiki.controler_page.ot')) })));
    aControler.forEach((phrase) => {
      nombresDe(sansReferences(phrase.texte)).filter((nombre) => !nombresConnus.has(nombre)).forEach((nombre) =>
        raisons.push(I18n.t('wiki.controler_page.nombre_absent', { nom, nombre, source: (source || I18n.t('wiki.controler_page.ot_cites')), court: court(phrase.propre) })));
      if (MOTIF_COMPTAGE.test(Wiki.comparable(sansReferences(phrase.texte)))) {
        raisons.push(I18n.t('wiki.controler_page.comptage_interdit_nombres_cas', { nom, court: court(phrase.propre) }));
      }
      controlerDates(phrase, nom, raisons);
      if (ctx.anterieure && ctx.otIngere && phrase.ot.includes(ctx.otIngere.id)
        && plusRecent(phrase.ot, ctx.dates) === ctx.otIngere.id) {
        const mots = contientUnMot(sansReferences(phrase.texte), Wiki.VOCABULAIRE_NOUVEAUTE);
        if (mots.length) {
          raisons.push(I18n.t('wiki.controler_page.intervention_anterieure_faits_deja', { nom, mots: mots.join(' », « '), court: court(phrase.propre) }));
        }
      }
    });
    const termes = Wiki.termesDeSecurite(titre + '\n' + (page.texte || ''));
    if (termes.length) raisons.push(I18n.t('wiki.controler_page.securite', { nom, message: messageSecurite(ctx.manuel), termes: termes.join(' », « ') }));
  }

  return {
    lireTexte, ecrireTexte, comparerTextes, controlerProposition, formeDuTitre, prefixeSousPage, memeGeste, MEME_GESTE,
    identitePhrase, citationsDe, liensDe, phrasesDe: (valeur) => phrasesDe(lireTexte(valeur)),
    mesurerTexte: (valeur) => mesureDe(lireTexte(valeur)),
    // { <rubrique>: { phrases, mots } } (mots sans le nom de la rubrique), pour les limites de Wiki.LIMITES (§20.12).
    mesurerRubriques: (valeur) => Object.fromEntries(Array.from(mesureDesRubriques(lireTexte(valeur)).values(),
      (mesure) => [mesure.nom, { phrases: mesure.phrases, mots: mesure.mots }])),
  };
})());
