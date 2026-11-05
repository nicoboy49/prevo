'use strict';
// Wiki (7 bis/9) — la page d'une entité de l'encyclopédie, #/wiki/<id> (refonte 2, ARCHITECTURE.md §20.12 ; D113,
// D114 ; tâche T137), pour les six types (machine, panne, article, technicien, intervention, savoir-faire), d'après
// Wiki.entite (wiki-entites.js : visibilité du profil déjà appliquée). La route est dans wiki-ecrans.js ; les sections
// calculées de chaque type dans wiki-sections-ecrans.js (chargé juste après) ; les outils d'affichage communs (types,
// icônes et couleurs, liens vers les entités, fil d'Ariane) dans wiki-entites-ecrans.js (Wiki.outilsEcrans, lu à
// l'appel). Ce fichier pose le cadre de la page (Wiki.rendreEntite), de haut en bas (maquette validée, D113) :
//   fil d'Ariane (Wiki › liste du type › nom), type (icône et couleur discrète des briques de l'accueil), titre,
//   « Sous-page de <mère> » pour une sous-page, actions (fiche de l'équipement ou de l'article, « Ouvrir la fiche OT »,
//   « Modifier » au responsable) ; EN TÊTE la consignation (machine ; savoir-faire : celle de sa machine, CS98) et
//   « À trancher » (D107 : note et boutons au responsable) ; puis, à gauche, les sections dans l'ordre de leur type
//   avec les textes rédigés et leur bandeau d'origine (§20.9) et « Pages qui renvoient ici » (wiki-sections-ecrans.js),
//   les propositions en attente (responsable) et « Références » en dernier ; à droite, la fiche des faits (au-dessus sur
//   téléphone).
//
// Aucune donnée n'est insérée comme HTML : UI.html échappe ; la consignation est posée par textContent ; une phrase est
// construite élément par élément (texte, liens [[titre]], petits numéros).
//
// Précisions au contrat (§20.12) :
//  - petits numéros : chaque citation [OT-…] d'une phrase devient, à sa place (l'espace qui la précède retirée ; répétée
//    dans la même phrase, montrée une fois), <sup class="wiki-ref"> ; les OT des articles consommés (page Machine) et
//    des articles changés (page Panne) aussi (D118, T143 : wiki-sections-ecrans.js) ; lien #/wiki/<OT>, bulle « <OT> ·
//    <date> · <titre> » (title), nom « Référence n : <bulle> » (aria-label) ; pour le demandeur, sans lien : un bouton
//    (même nom, même bulle) qui montre la bulle au clic ou au toucher, gardée dans l'écran, refermée par un autre clic
//    ou Échap (relecture de T137, m6 : un title seul est invisible au toucher) ;
//  - numérotation (une seule règle, creerReferences) : un seul jeu de numéros par page, dans l'ordre d'apparition — un
//    OT prend son numéro la première fois que la page le montre et le garde partout ; la page se construit dans son
//    ordre (« À trancher » en tête, puis les morceaux de Wiki.sectionsEntite un à un : textes et sections) ; une liste
//    longue numérote d'abord tous ses éléments, même ceux créés au clic, à leur place ;
//  - « Références » : tous les OT numérotés — numéro, OT (lien, sauf pour le demandeur), date, machine (lien), titre —,
//    dans l'ordre des numéros ;
//  - [[titre]] → une page qui s'affiche (même index que le champ liens, wiki-journal.js) : panne, machine, article,
//    savoir-faire actif, texte d'une machine ou d'un article (sa page) ; sinon le titre reste du texte ;
//  - fiche : les faits de Wiki.entite dans l'ordre, un fait vide omis ; AAAA-MM-JJ → JJ/MM/AAAA, avec l'heure →
//    JJ/MM/AAAA hh:mm, oui / non, nombre à la française, prix et taux horaire en euros (« / h ») ; un fait qui porte un
//    lien mène à sa page ; pour une machine, ses sous-ensembles (liens) avant « Interventions » ; pour une intervention,
//    à la place du fait « Technicien », tous ses techniciens (le sien, puis ceux qui ont pointé du temps :
//    sections.techniciens ; « Techniciens » s'ils sont plusieurs), chacun en lien vers sa page si le profil la voit ;
//  - « Ce que dit la page » : la phrase telle que la contradiction l'a notée (maquette) ; les OT qui l'observent en
//    petits numéros après l'observation ;
//  - « Modifier » (responsable, seul profil de #/wiki-ecrire) : texte d'une machine ou d'un article, savoir-faire ;
//    « Le nouveau remplace » mène à #/wiki-ecrire/<page>.

Object.assign(Wiki, (() => {

  const TYPE_TEXTE = { machine: 'équipement', article: 'composant', 'savoir-faire': 'savoir-faire' };   // Wiki.RUBRIQUES
  // Rubriques lues comme un paragraphe (« En bref », « À quoi il sert » : marqueurs, D156) ; les autres en liste.
  const PROSE = [Wiki.RUBRIQUES['équipement'][0], Wiki.RUBRIQUES.composant[0]];
  const ETATS_STOCK = { 'en stock': 'ok', 'sous le seuil': 'attention', rupture: 'ko' };
  const MOTIF_JETON = /\[\[([^[\]]+)\]\]|\s*\[(OT-\d{4}-\d{4,})\]/g;

  // ===========================================================================================
  // 1. Petits outils
  // ===========================================================================================

  const texte = (valeur) => (valeur === null || valeur === undefined ? '' : String(valeur).trim());
  const outils = () => Wiki.outilsEcrans;
  const faitDe = (entite, libelle) => (entite.faits.find((fait) => fait.libelle === libelle) || {}).valeur;
  const titreMachine = (ligne) => [texte(ligne.repere), texte(ligne.designation)].filter(Boolean).join(' — ');
  const titreArticle = (ligne) => texte(ligne.designation) || texte(ligne.reference) || texte(ligne.id);

  /** Boutons pour trancher une contradiction : [décision (code stocké), libellé], lus à l'affichage. */
  const decisions = () => [['ancien', I18n.t('wiki.decisions.bouton_ancien')], ['nouveau', I18n.t('wiki.decisions.bouton_nouveau')], ['les deux', I18n.t('wiki.decisions.bouton_deux')]];

  /** Titre (caché) de la fiche des faits d'un type de page. */
  function titreFiche(type) {
    switch (type) {
      case 'machine': return I18n.t('wiki.titre_fiche.fiche_machine');
      case 'panne': return I18n.t('wiki.titre_fiche.fiche_panne');
      case 'article': return I18n.t('wiki.titre_fiche.fiche_article');
      case 'technicien': return I18n.t('wiki.titre_fiche.fiche_technicien');
      case 'intervention': return I18n.t('wiki.titre_fiche.fiche_intervention');
      default: return I18n.t('wiki.titre_fiche.fiche_savoir_faire');
    }
  }

  /** Montant d'un fait en euros (prix unitaire ; taux horaire, suivi de « / h ») ; null pour un autre nombre. */
  function enEuros(fait, valeur) {
    if (fait.libelle === I18n.t('commun.champ.prix_unitaire')) return UI.euro(valeur);
    return fait.libelle === I18n.t('wiki.fait.taux_horaire') ? I18n.t('wiki.fiche.montant_par_heure', { montant: UI.euro(valeur) }) : null;
  }

  /** Valeur d'un fait à l'écran (précisions en tête) ; null si le fait est vide. */
  function valeurFait(fait) {
    const valeur = fait.valeur;
    if (valeur === null || valeur === undefined || valeur === '') return null;
    if (typeof valeur === 'boolean') return valeur ? I18n.t('wiki.fiche.oui') : I18n.t('wiki.fiche.non');
    if (typeof valeur === 'number') {
      const montant = enEuros(fait, valeur);
      return montant === null ? UI.nombreFr(valeur) : montant;
    }
    const chaine = String(valeur);
    if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}/.test(chaine)) return UI.dateHeureFr(chaine);
    return /^\d{4}-\d{2}-\d{2}$/.test(chaine) ? UI.dateFr(chaine) : chaine;
  }

  // Adresse d'un document (async : en mode serveur c'est /api/documents/<nom>) ; null si introuvable.
  async function adresseDocument(nom) {
    if (!nom || !App.adaptateur) return null;
    try {
      return await App.adaptateur.urlDocument(nom);
    } catch (erreur) {
      console.warn('Prévo (wiki) : document « ' + nom + ' » illisible (' + (erreur && erreur.message) + ').', erreur);
      return null;
    }
  }

  /**
   * [[titre]] → identifiant d'une page qui s'affiche (précisions en tête), index construit au premier lien demandé.
   * Même ordre que l'index du champ liens (wiki-journal.js) : pannes, machines, articles, puis pages actives.
   */
  function resolveur(profil) {
    let index = null;
    function construire() {
      index = new Map();
      const poser = (titre, id) => { if (texte(titre) && texte(id)) index.set(Wiki.comparable(titre), texte(id)); };
      (Wiki.listeEntites('panne', { profil }) || []).forEach((panne) => poser(panne.titre, panne.id));
      Donnees.lignes('equipements').forEach((ligne) => poser(titreMachine(ligne), ligne.id));
      Donnees.lignes('articles').forEach((ligne) => poser(titreArticle(ligne), ligne.id));
      Donnees.lignes('wiki_pages').filter((ligne) => texte(ligne.statut) !== 'archivée').forEach((ligne) => {
        const type = texte(ligne.type);
        if (type === 'savoir-faire') poser(ligne.titre, ligne.id);
        else if (type === 'équipement' && Donnees.trouver('equipements', texte(ligne.equipement_id))) poser(ligne.titre, ligne.equipement_id);
        else if (type === 'composant' && Donnees.trouver('articles', texte(ligne.article_id))) poser(ligne.titre, ligne.article_id);
      });
    }
    return (titre) => {
      if (!index) construire();
      return index.get(Wiki.comparable(titre)) || '';
    };
  }

  // ===========================================================================================
  // 2. Petits numéros et « Références » (D113)
  // ===========================================================================================

  /**
   * Registre des références d'une page, la seule règle de numérotation (précisions en tête) : un OT prend son numéro
   * la première fois que la page le montre (numero), dans l'ordre où elle se construit, et le garde partout. Détails
   * d'un OT (bulle, « Références ») : Wiki.entite().references (textes, « À trancher »), sinon sa ligne parmi les
   * interventions de la page (les OT des articles consommés ou changés en sont tous).
   */
  function creerReferences(entite) {
    const details = new Map(((entite.sections && entite.sections.interventions) || []).map((ot) => [ot.id, ot]));
    (entite.references || []).forEach((reference) => details.set(reference.id, reference));
    const numeros = new Map();
    const detail = (ot) => details.get(ot) || { id: ot, date: '', titre: '', machine: null, lien: null };
    const bulle = (ot) => [ot, UI.dateFr(detail(ot).date), detail(ot).titre].filter(Boolean).join(' · ');

    function numero(ot) {
      if (!numeros.has(ot)) numeros.set(ot, numeros.size + 1);
      return numeros.get(ot);
    }

    /**
     * Petit numéro d'un OT (fragment UI.html) : <sup class="wiki-ref">, lien vers sa page ; pour le demandeur, un bouton
     * qui montre la bulle (basculerBulle). Même nom accessible dans les deux cas.
     */
    function fragment(ot) {
      const n = numero(ot);
      const lien = detail(ot).lien;
      const nom = I18n.t('wiki.creer_references.reference_n_bulle', { n, bulle: bulle(ot) });
      return lien
        ? UI.html`<sup class="wiki-ref" data-ot="${ot}"><a href="${outils().adresse(lien)}" title="${bulle(ot)}" aria-label="${nom}">${n}</a></sup>`
        : UI.html`<sup class="wiki-ref" data-ot="${ot}"><button type="button" class="wiki-ref-numero" title="${bulle(ot)}"
            aria-label="${nom}">${n}</button></sup>`;
    }

    const element = (ot) => UI.element(fragment(ot));

    /** Section « Références » : numéro, OT, date, machine, titre. */
    function section() {
      const o = outils();
      return UI.element(UI.html`<section class="wiki-section wiki-references" id="wiki-references" aria-labelledby="wiki-titre-references">
        <h2 id="wiki-titre-references">${I18n.html('wiki.creer_references.references_numeros_size', { numerosSize: numeros.size })}</h2>
        <ol class="wiki-refs">${Array.from(numeros, ([ot, numero]) => {
          const reference = detail(ot);
          return UI.html`<li id="wiki-ref-${numero}" data-ot="${ot}">${o.joindre([o.lienEntite(reference.lien, ot),
            UI.dateFr(reference.date), o.lienMachine(reference.machine), reference.titre], ' · ')}</li>`;
        })}</ol></section>`);
    }

    return { fragment, element, section, nombre: () => numeros.size };
  }

  const MARGE_BULLE = 8;                         // px gardés entre la bulle et le bord de l'écran

  function fermerBulles(racine) {
    UI.$$('.wiki-ref-bulle', racine).forEach((bulle) => bulle.remove());
  }

  /**
   * Bulle d'un petit numéro sans lien (demandeur) : ouverte sous le numéro au clic ou au toucher, une seule à la fois,
   * décalée pour rester dans l'écran (jamais de défilement horizontal) ; un second clic la referme. Son texte est celui
   * du nom du bouton : elle est cachée aux lecteurs d'écran, qui l'ont déjà.
   */
  function basculerBulle(bouton) {
    const sup = bouton.closest('.wiki-ref');
    const ouverte = UI.$('.wiki-ref-bulle', sup);
    fermerBulles(bouton.closest('.wiki-page') || document);
    if (ouverte) return;
    const bulle = document.createElement('span');
    bulle.className = 'wiki-ref-bulle';
    bulle.setAttribute('aria-hidden', 'true');
    bulle.textContent = bouton.title;
    sup.appendChild(bulle);
    const cadre = bulle.getBoundingClientRect();
    const largeur = document.documentElement.clientWidth;
    const decalage = Math.max(MARGE_BULLE - cadre.left, Math.min(0, largeur - MARGE_BULLE - cadre.right));
    if (decalage) bulle.style.left = Math.round(decalage) + 'px';
  }

  // ===========================================================================================
  // 3. Phrases et textes rédigés (§20.4, §20.9)
  // ===========================================================================================

  function ajouterTexte(conteneur, valeur) {
    if (valeur) conteneur.appendChild(document.createTextNode(valeur));
  }

  /** Pose une phrase dans `conteneur`, élément par élément : texte, liens [[titre]], petits numéros. */
  function poserPhrase(conteneur, source, contexte) {
    const valeur = String(source || '').replace(/\s+/g, ' ').trim();
    const cites = new Set();
    let position = 0;
    for (const jeton of valeur.matchAll(MOTIF_JETON)) {
      ajouterTexte(conteneur, valeur.slice(position, jeton.index));
      position = jeton.index + jeton[0].length;
      if (jeton[2]) {
        if (!cites.has(jeton[2])) conteneur.appendChild(contexte.refs.element(jeton[2]));
        cites.add(jeton[2]);
        continue;
      }
      const titre = jeton[1].trim();
      const id = contexte.resoudre(titre);
      conteneur.appendChild(UI.element(id ? UI.html`<a class="wiki-lien-page" href="${outils().adresse(id)}">${titre}</a>`
        : UI.html`<span class="wiki-lien-absent" title="${I18n.t('wiki.poser_phrase.page_introuvable_wiki')}">${titre}</span>`));
    }
    ajouterTexte(conteneur, valeur.slice(position));
    return conteneur;
  }

  /** Bandeau d'origine (§20.9, CS103). */
  function texteOrigine(textes) {
    const modele = texte(textes.modele);
    const ia = modele ? I18n.t('wiki.texte_origine.redige_ia_modele', { modele }) : I18n.t('wiki.texte_origine.redige_ia');
    const date = UI.dateFr(texte(textes.valideLe));
    const qui = texte(textes.validePar) || I18n.t('wiki.texte_origine.responsable');
    const par = date ? I18n.t('wiki.texte_origine.qui_date', { qui, date }) : qui;
    if (textes.origine === 'IA') return I18n.t('wiki.texte_origine.ia_valide_par', { ia, par });
    if (textes.origine === 'manuel') return I18n.t('wiki.texte_origine.ecrit_par', { par });
    if (textes.origine === 'IA et manuel') return I18n.t('wiki.texte_origine.puis_modifie_main_valide', { ia, par });
    return texte(textes.validePar) ? I18n.t('wiki.texte_origine.origine_non_renseignee_validee', { par }) : I18n.t('wiki.texte_origine.origine_non_renseignee');
  }

  /**
   * Un groupe de textes rédigés (`groupe` : { textes: [noms de rubriques], reste (aussi les rubriques hors du type),
   * toujours (montré vide, sous le titre titreVide, sinon le nom de sa première rubrique) }) : une section par rubrique qui a des phrases, dans l'ordre de Wiki.entite, le bandeau
   * d'origine sous le premier titre ; null si rien à montrer.
   */
  function blocTextes(entite, groupe, contexte) {
    const connues = Wiki.RUBRIQUES[TYPE_TEXTE[entite.type]] || [];
    const textes = entite.textes || { rubriques: [] };
    const rubriques = textes.rubriques.filter((rubrique) => rubrique.phrases.length
      && (groupe.textes.includes(rubrique.nom) || (groupe.reste && !connues.includes(rubrique.nom))));
    if (!rubriques.length && !groupe.toujours) return null;
    const bloc = UI.element(UI.html`<div class="wiki-textes"></div>`);
    contexte.groupes = (contexte.groupes || 0) + 1;
    if (contexte.groupes === 1) bloc.id = 'wiki-texte';                // le premier groupe de textes de la page
    if (!rubriques.length) {
      const titre = groupe.titreVide || groupe.textes[0];
      bloc.appendChild(UI.element(UI.html`<section class="wiki-section wiki-texte" data-rubrique="${titre}">
        <h2>${titre}</h2><p class="wiki-sans-texte"><b>${I18n.t('wiki.bloc_textes.aucun_texte_valide_instant')}</b></p>
        <p class="aide">${I18n.t('wiki.bloc_textes.ecrit_partir_interventions_cloturees')}</p></section>`));
      return bloc;
    }
    rubriques.forEach((rubrique, rang) => {
      const id = UI.identifiantUnique('wiki-rubrique');
      const section = UI.element(UI.html`<section class="wiki-section wiki-texte" data-rubrique="${rubrique.nom}" aria-labelledby="${id}">
        <h2 id="${id}">${rubrique.nom}</h2>
        ${rang ? '' : UI.html`<p class="wiki-origine" data-origine="${textes.origine}">${textes.origine.includes('IA')
          ? UI.html`<span class="wiki-origine-ia">IA</span> ` : ''}<span>${texteOrigine(textes)}</span></p>`}
        ${PROSE.includes(rubrique.nom) ? UI.html`<p class="wiki-prose"></p>` : UI.html`<ul class="wiki-phrases"></ul>`}</section>`);
      const zone = UI.$('.wiki-prose, .wiki-phrases', section);
      rubrique.phrases.forEach((phrase, n) => {
        const element = document.createElement(zone.tagName === 'P' ? 'span' : 'li');
        element.className = 'wiki-phrase';
        if (zone.tagName === 'P' && n) zone.appendChild(document.createTextNode(' '));
        zone.appendChild(poserPhrase(element, phrase, contexte));
      });
      bloc.appendChild(section);
    });
    return bloc;
  }

  // ===========================================================================================
  // 4. « À trancher » (D107)
  // ===========================================================================================

  // Une décision à la fois ; après le réaffichage, les clics de tranchage sont ignorés un court instant : un double
  // clic ne doit jamais trancher la contradiction arrivée sous le pointeur (relecture de T119, comme le journal).
  const REPOS_APRES_DECISION_MS = 600;
  let decisionEnCours = false;
  let reposJusqua = 0;
  let pageEnRepos = null;                       // la page réaffichée après la décision (une autre page n'est pas bloquée)

  function decisionPermise(evenement, bouton) {
    return !decisionEnCours && evenement.detail <= 1
      && !(bouton.closest('.wiki-page') === pageEnRepos && performance.now() < reposJusqua);
  }

  async function trancher(element, contradiction, bouton) {
    decisionEnCours = true;
    try {
      await enregistrerDecision(element, contradiction, bouton);
    } finally {
      decisionEnCours = false;
      reposJusqua = performance.now() + REPOS_APRES_DECISION_MS;
      const page = document.querySelector('.wiki-page');
      pageEnRepos = page;
      if (page) {
        page.dataset.occupe = '1';
        setTimeout(() => { delete page.dataset.occupe; }, REPOS_APRES_DECISION_MS);
      }
    }
  }

  async function enregistrerDecision(element, contradiction, bouton) {
    const boutons = UI.$$('button[data-decision]', element);
    boutons.forEach((autre) => { autre.disabled = true; });
    bouton.setAttribute('aria-busy', 'true');
    const decision = bouton.dataset.decision;
    try {
      const resultat = await Wiki.trancher(contradiction.entreeId, contradiction.rang, decision, UI.$('.wiki-note', element).value);
      App.marquerSaisie(false);
      UI.toast(I18n.t('wiki.enregistrer_decision.decision_enregistree_journal_wiki'), 'succes');
      if (decision === 'nouveau' && resultat && resultat.pageId) {
        App.naviguer('#/wiki-ecrire/' + encodeURIComponent(resultat.pageId));
        return;
      }
      await App.reafficher();
    } catch (erreur) {
      console.warn('Prévo (wiki) : décision non enregistrée (' + (erreur && erreur.message) + ').', erreur);
      UI.toast(I18n.t('wiki.enregistrer_decision.decision_non_enregistree', { raisonErreur: App.raisonErreur(erreur) }), 'erreur');
      boutons.forEach((autre) => { autre.disabled = false; });
      bouton.removeAttribute('aria-busy');
    }
  }

  function contradictionElement(contradiction, contexte) {
    const anterieure = Boolean(contradiction.anterieure);
    const ots = (contradiction.ot && contradiction.ot.length ? contradiction.ot : [contradiction.otSource]).filter(Boolean);
    const idNote = UI.identifiantUnique('wiki-note');
    const element = UI.element(UI.html`<li class="wiki-contradiction" data-entree="${contradiction.entreeId}"
        data-rang="${contradiction.rang}" data-anterieure="${anterieure ? 'oui' : 'non'}">
      <div class="wiki-cotes">
        <div class="wiki-cote wiki-cote-page"><h3>${I18n.t('wiki.contradiction_element.dit_page')}</h3><p class="wiki-phrase"></p></div>
        <div class="wiki-cote wiki-cote-ot"><h3>${anterieure ? I18n.t('wiki.contradiction_element.observation_anterieure_faits_page') : I18n.t('wiki.contradiction_element.dit_nouvel_ot')}</h3>
          <p class="wiki-observation"><span class="wiki-observation-texte">${contradiction.observation}</span></p></div>
      </div>
      ${contradiction.depuis ? UI.html`<p class="aide wiki-depuis">${I18n.t('wiki.contradiction_element.signalee_depuis', { depuis: UI.dateFr(contradiction.depuis) })}</p>` : ''}
      ${contexte.responsable ? UI.html`<div class="wiki-trancher" role="group" aria-label="${I18n.t('wiki.contradiction_element.trancher_contradiction')}">
        <div class="champ"><label class="libelle" for="${idNote}">${I18n.t('wiki.contradiction_element.note_facultative')}</label>
          <textarea id="${idNote}" class="wiki-note" rows="2" maxlength="500"></textarea></div>
        <div class="actions">${decisions().map(([decision, libelle]) => UI.html`<button type="button"
          class="btn ${decision === 'nouveau' ? 'btn-primaire' : 'btn-secondaire'}" data-decision="${decision}">${libelle}</button>`)}</div>
      </div>` : ''}
    </li>`);
    poserPhrase(UI.$('.wiki-cote-page .wiki-phrase', element), contradiction.phrase, contexte);    // numéros dans l'ordre affiché
    const observation = UI.$('.wiki-observation', element);
    ots.forEach((ot) => observation.appendChild(contexte.refs.element(ot)));
    UI.$$('button[data-decision]', element).forEach((bouton) => bouton.addEventListener('click', (evenement) => {
      if (decisionPermise(evenement, bouton)) trancher(element, contradiction, bouton);
    }));
    return element;
  }

  function blocContradictions(entite, contexte) {
    const section = UI.element(UI.html`<section class="wiki-encadre wiki-a-trancher" id="wiki-a-trancher" aria-labelledby="wiki-titre-trancher">
      <h2 id="wiki-titre-trancher">${UI.icone('alerte')}${I18n.html('wiki.bloc_contradictions.trancher_nb_atrancher', { nbATrancher: entite.aTrancher.length })}</h2>
      <p class="aide">${I18n.t('wiki.bloc_contradictions.ot_dit_autre_chose')}</p>
      <ul class="wiki-contradictions"></ul>
    </section>`);
    entite.aTrancher.forEach((contradiction) => UI.$('.wiki-contradictions', section).appendChild(contradictionElement(contradiction, contexte)));
    return section;
  }

  // ===========================================================================================
  // 5. Consignation (machine ; en-tête d'un savoir-faire, CS98)
  // ===========================================================================================

  /**
   * Consignation : texte de la fiche tel quel (textContent), document ; jamais de texte d'IA. `reglages` : { id, titre,
   * phrase (en-tête d'un savoir-faire), equipementId, responsable }.
   */
  function blocConsignation(consignation, reglages) {
    const valeur = consignation || { texte: '', document: '' };
    const nomDocument = texte(valeur.document);
    const section = UI.element(UI.html`
      <section class="wiki-encadre wiki-consignation${reglages.phrase ? ' wiki-entete-sf' : ''}" id="${reglages.id}" aria-labelledby="${reglages.id}-titre">
        <h2 id="${reglages.id}-titre">${UI.icone('alerte')} ${reglages.titre}</h2>
        ${reglages.phrase ? UI.html`<p class="wiki-entete-phrase"><b>${reglages.phrase}</b></p>` : ''}
        ${texte(valeur.texte)
          ? UI.html`<div class="wiki-consignation-texte"></div>
            <p class="aide">${I18n.t('wiki.bloc_consignation.procedure_fiche_equipement_telle')}</p>`
          : UI.html`<p class="wiki-sans-consignation"><b>${I18n.t('wiki.bloc_consignation.aucune_consignation_saisie_equipement')}</b></p>
            ${reglages.responsable && !reglages.phrase ? UI.html`<p><a class="btn btn-secondaire" id="wiki-modifier-consignation"
              href="#/equipement/${encodeURIComponent(reglages.equipementId)}/modifier">${UI.icone('cle')}${I18n.t('wiki.bloc_consignation.saisir_consignation_fiche')}</a></p>` : ''}`}
        ${nomDocument ? UI.html`<p class="wiki-consignation-document">${I18n.html('wiki.bloc_consignation.document_nom_document', { nomDocument })}</p>` : ''}
      </section>`);
    const zoneTexte = UI.$('.wiki-consignation-texte', section);
    if (zoneTexte) zoneTexte.textContent = valeur.texte;      // tel quel : jamais interprété
    const zoneDocument = UI.$('.wiki-document', section);
    if (zoneDocument) {
      adresseDocument(nomDocument).then((adresse) => {
        UI.remplir(zoneDocument, adresse
          ? UI.html`<a class="wiki-lien-document" href="${adresse}" target="_blank" rel="noopener">${UI.icone('document')} ${nomDocument}</a>`
          : UI.html`${I18n.html('wiki.bloc_consignation.fichier_introuvable', { nomDocument })}`);
      });
    }
    return section;
  }

  /** En tête de page : la consignation d'une machine, l'en-tête d'un savoir-faire (null pour les autres types). */
  function consignationDe(entite, contexte) {
    if (entite.type === 'machine') {
      return blocConsignation(entite.sections.consignation, { id: 'wiki-consignation', titre: I18n.t('wiki.consignation_de.consignation_repere', { repere: (faitDe(entite, I18n.t('commun.champ.repere')) || entite.titre) }), equipementId: entite.id, responsable: contexte.responsable });
    }
    if (entite.type !== 'savoir-faire') return null;
    const entete = entite.sections.entete || { consignation: null, equipements: [], phrase: Wiki.PHRASE_SAVOIR_FAIRE };
    const rattachement = entite.sections.rattachement;
    // Savoir-faire commun à plusieurs machines (D116) : la liste de ces machines, comme pour un article.
    const commun = !(rattachement && rattachement.type === 'article') && entete.equipements.length > 1;
    if (rattachement && rattachement.type === 'machine' && !commun) {
      const fiche = Donnees.trouver('equipements', rattachement.id);
      const repere = (entete.equipements[0] && entete.equipements[0].repere) || texte(fiche && fiche.repere) || rattachement.titre;
      return blocConsignation(entete.consignation, { id: 'wiki-entete', titre: I18n.t('wiki.consignation_de.consignation_repere', { repere }),
        phrase: entete.phrase || Wiki.PHRASE_SAVOIR_FAIRE, equipementId: rattachement.id, responsable: contexte.responsable });
    }
    return UI.element(UI.html`<section class="wiki-encadre wiki-consignation wiki-entete-sf" id="wiki-entete" aria-labelledby="wiki-entete-titre">
      <h2 id="wiki-entete-titre">${UI.icone('alerte')} ${I18n.t('wiki.consignation_de.consignation_equipements')}</h2>
      <p class="wiki-entete-phrase"><b>${entete.phrase || Wiki.PHRASE_SAVOIR_FAIRE}</b></p>
      ${entete.equipements.length ? UI.html`<p>${commun ? I18n.t('wiki.consignation_de.savoir_faire_sert_machines') : I18n.t('wiki.consignation_de.article_monte_machines')}</p>
        <ul class="wiki-jumeaux wiki-entete-equipements">${entete.equipements.map((monte) => UI.html`<li><a class="wiki-lien-page"
          href="${outils().adresse(monte.equipementId)}">${monte.repere || monte.equipementId}</a></li>`)}</ul>`
        : UI.html`<p class="aide">${I18n.t('wiki.consignation_de.aucune_machine_connue_savoir')}</p>`}
    </section>`);
  }

  // ===========================================================================================
  // 6. En-tête, fiche des faits, propositions en attente
  // ===========================================================================================

  /** Nom court dans le fil d'Ariane : repère d'une machine, référence d'un article, numéro d'un OT, sinon le titre. */
  function nomCourt(entite) {
    if (entite.type === 'machine') return texte(faitDe(entite, I18n.t('commun.champ.repere'))) || entite.titre;
    if (entite.type === 'article') return texte(faitDe(entite, I18n.t('commun.champ.reference'))) || entite.titre;
    return entite.type === 'intervention' ? entite.id : entite.titre;
  }

  function sousTitre(entite) {
    const o = outils();
    const fait = (libelle) => entite.faits.find((element) => element.libelle === libelle) || { valeur: '', lien: null };
    if (entite.type === 'machine') return texte(faitDe(entite, I18n.t('wiki.fait.lieu')));
    if (entite.type === 'panne') {
      const cas = I18n.t('wiki.compte.cas', { n: faitDe(entite, I18n.t('wiki.fait.cas')) });
      const machines = I18n.t('wiki.compte.machines', { n: faitDe(entite, I18n.t('wiki.fait.machines_touchees')) });
      return I18n.t('wiki.sous_titre.cas_machines', { cas, machines });
    }
    if (entite.type === 'article') {
      return o.joindre([texte(faitDe(entite, I18n.t('commun.champ.reference'))), texte(faitDe(entite, I18n.t('wiki.fait.emplacement'))) ? I18n.t('wiki.article.range_emplacement', { emplacement: faitDe(entite, I18n.t('wiki.fait.emplacement')) }) : ''], ' · ');
    }
    if (entite.type === 'technicien') return o.joindre([texte(faitDe(entite, I18n.t('wiki.fait.metier'))), faitDe(entite, I18n.t('wiki.fait.actif')) === false ? I18n.t('wiki.sous_titre.inactif') : ''], ' · ');
    if (entite.type === 'intervention') {
      const date = ['wiki.fait.fin', 'wiki.fait.debut', 'wiki.fait.prevu_le', 'wiki.fait.cree_le'].map((cle) => texte(faitDe(entite, I18n.t(cle))))
        .find(Boolean);
      const machine = fait(I18n.t('wiki.fait.machine'));
      return o.joindre([UI.dateFr(date), texte(machine.valeur) ? o.lienEntite(machine.lien, machine.valeur) : ''], ' · ');
    }
    const rattachement = entite.sections.rattachement;
    return rattachement ? I18n.html('wiki.sous_titre.rattache_a', { lien: o.lienEntite(rattachement.lien, rattachement.titre) })
      : I18n.t('wiki.sous_titre.sans_rattachement');
  }

  /** « Sous-page de <mère> » : lien vers la mère ; sans lien si elle est archivée (elle reste nommée). */
  function mereHtml(mere) {
    const ligne = Donnees.trouver('wiki_pages', mere.id);
    const archivee = Boolean(ligne) && texte(ligne.statut) === 'archivée';
    return UI.html`<p class="wiki-mere" id="wiki-mere">${I18n.html('wiki.mere.sous_page_de', { mere: archivee
      ? I18n.html('wiki.mere.page_archivee', { mereTitre: mere.titre })
      : UI.html`<a class="wiki-lien-mere" href="${outils().adresse(mere.id)}">${mere.titre}</a>` })}</p>`;
  }

  function actionsHtml(entite, contexte) {
    const actions = [];
    const bouton = (id, adresse, icone, libelle) => UI.html`<a class="btn btn-secondaire" id="${id}" href="${adresse}">${UI.icone(icone)}${libelle}</a>`;
    if (entite.type === 'machine') actions.push(bouton('wiki-lien-fiche', '#/equipement/' + encodeURIComponent(entite.id), 'parc', I18n.t('wiki.actions.fiche_equipement')));
    if (entite.type === 'article' && contexte.profil !== 'demandeur') {
      actions.push(bouton('wiki-lien-fiche', '#/magasin/article/' + encodeURIComponent(entite.id), 'magasin', I18n.t('wiki.titre_fiche.fiche_article')));
    }
    if (entite.type === 'intervention' && entite.sections.ficheOT) actions.push(bouton('wiki-fiche-ot', entite.sections.ficheOT, 'ordres', I18n.t('wiki.actions.ouvrir_fiche_ot')));
    if (contexte.responsable && TYPE_TEXTE[entite.type]) {
      actions.push(bouton('wiki-modifier', '#/wiki-ecrire/' + encodeURIComponent(entite.id), 'cle', I18n.t('commun.bouton.modifier')));
    }
    return actions.length ? UI.html`<div class="actions wiki-actions">${actions}</div>` : '';
  }

  function enteteHtml(entite, contexte) {
    const o = outils();
    const type = o.TYPES[entite.type];
    const titre = entite.type === 'intervention' && entite.titre !== entite.id ? entite.id + ' — ' + entite.titre : entite.titre;
    const mere = entite.type === 'savoir-faire' ? entite.sections.mere : null;
    return UI.html`<div class="entete-page wiki-entete-entite"><div class="wiki-entete-texte">
        ${o.fil([UI.html`<a href="#/wiki/${type.liste}">${type.pluriel}</a>`, UI.html`<span class="wiki-fil-nom">${nomCourt(entite)}</span>`])}
        <p class="wiki-puce-ligne">${o.puce(entite.type)}</p>
        <h1>${titre}</h1>
        ${mere ? mereHtml(mere) : ''}
        <p class="wiki-sous-titre">${sousTitre(entite)}</p>
      </div>${actionsHtml(entite, contexte)}</div>`;
  }

  /** Ligne des techniciens d'une intervention (précisions en tête) : un lien par technicien, en texte sans lien. */
  function ligneTechniciens(techniciens) {
    const o = outils();
    return UI.html`<dt data-fait="Technicien" data-section="techniciens">${I18n.t('wiki.ligne_techniciens.techniciens', { n: techniciens.length })}</dt>
      <dd>${o.joindre(techniciens.map((technicien) => o.lienEntite(technicien.lien, technicien.nom)), ', ')}</dd>`;
  }

  /** Fiche des faits (précisions en tête), à droite de la page (au-dessus sur téléphone). */
  function ficheHtml(entite) {
    const o = outils();
    const techniciens = entite.type === 'intervention' ? entite.sections.techniciens || [] : [];
    const deTechniciens = (fait) => techniciens.length > 0 && fait.libelle === I18n.t('commun.champ.technicien');
    const lignes = entite.faits.map((fait) => ({ fait, valeur: valeurFait(fait) })).filter((ligne) => ligne.valeur !== null || deTechniciens(ligne.fait))
      .map(({ fait, valeur }) => (deTechniciens(fait) ? ligneTechniciens(techniciens)
        : UI.html`<dt data-fait="${fait.libelle}">${fait.libelle}</dt><dd>${fait.lien ? o.lienEntite(fait.lien, valeur)
          : (fait.libelle === I18n.t('wiki.fait.etat_stock') ? UI.html`<span class="badge ${ETATS_STOCK[valeur] || 'neutre'}">${o.libelleEtatStock(valeur)}</span>` : valeur)}</dd>`));
    const sousEnsembles = entite.type === 'machine' ? entite.sections.sousEnsembles || [] : [];
    if (sousEnsembles.length) {
      const rang = entite.faits.filter((fait) => valeurFait(fait) !== null).findIndex((fait) => fait.libelle === I18n.t('wiki.fait.interventions'));
      lignes.splice(rang < 0 ? lignes.length : rang, 0, UI.html`<dt data-fait="Sous-ensembles" data-section="sousEnsembles">${I18n.t('wiki.fiche.sous_ensembles')}</dt>
        <dd>${o.joindre(sousEnsembles.map((machine) => o.lienMachine(machine)), ', ')}</dd>`);
    }
    return UI.html`<aside class="bento-tuile wiki-fiche" id="wiki-faits" aria-labelledby="wiki-faits-titre">
      <h2 id="wiki-faits-titre" class="wiki-fiche-titre">${o.puce(entite.type)}<span class="visuellement-cache">${titreFiche(entite.type)}</span></h2>
      <dl class="valeurs wiki-fiche-faits">${lignes}</dl>
    </aside>`;
  }

  function blocEnAttente(entite) {
    const o = outils();
    const vues = new Set();
    const propositions = entite.enAttente.filter((proposition) => !vues.has(proposition.entreeId) && vues.add(proposition.entreeId));
    return UI.element(UI.html`<section class="wiki-section" id="wiki-en-attente" aria-labelledby="wiki-titre-attente">
      <h2 id="wiki-titre-attente">${I18n.html('wiki.bloc_en_attente.propositions_attente_page', { nbPropositions: propositions.length })}</h2>
      <p class="aide">${I18n.t('wiki.bloc_en_attente.propositions_ia_pas_encore')}</p>
      <ul class="wiki-lignes wiki-attente">${propositions.map((proposition) => UI.html`<li data-entree="${proposition.entreeId}">
        <div class="wiki-ligne-tete"><a class="wiki-lien-proposition" href="#/wiki-journal?entree=${encodeURIComponent(proposition.entreeId)}">${I18n.t('wiki.bloc_en_attente.proposition_entree_id', { entreeId: proposition.entreeId })}</a>
          ${proposition.ot ? o.lienEntite(proposition.ot, proposition.ot) : ''}</div></li>`)}</ul>
    </section>`);
  }

  // ===========================================================================================
  // 7. La page
  // ===========================================================================================

  /**
   * Pose la page de `entite` (Wiki.entite) dans `conteneur` (précisions en tête). reglages : { profil, responsable }.
   */
  function rendreEntite(conteneur, entite, reglages) {
    const contexte = { profil: reglages.profil, responsable: Boolean(reglages.responsable), liens: entite.liens,
      telephone: UI.estTelephone(), refs: creerReferences(entite), resoudre: resolveur(reglages.profil) };
    const machine = entite.type === 'machine' ? entite.id : '';
    const mere = entite.type === 'savoir-faire' && entite.sections.mere ? entite.sections.mere.id : '';
    App.definirTitre(I18n.t('wiki.rendre_entite.wiki_nom_court', { nomCourt: nomCourt(entite) }));
    UI.remplir(conteneur, UI.html`<div class="wiki wiki-page wiki-entite" data-page="${entite.id}" data-type="${entite.type}"
        data-equipement="${machine}" data-mere="${mere}">
      ${enteteHtml(entite, contexte)}
      <div class="wiki-alertes"></div>
      <div class="wiki-page-grille"><div class="wiki-lecture"></div>${ficheHtml(entite)}</div>
    </div>`);
    // Bulles des petits numéros sans lien (demandeur) : un clic sur un numéro l'ouvre ou la ferme, ailleurs les ferme.
    const page = UI.$('.wiki-page', conteneur);
    page.addEventListener('click', (evenement) => {
      const bouton = evenement.target.closest('.wiki-ref-numero');
      if (bouton) basculerBulle(bouton);
      else fermerBulles(page);
    });
    page.addEventListener('keydown', (evenement) => { if (evenement.key === 'Escape') fermerBulles(page); });
    // En tête, dans l'ordre de la page : consignation, puis « À trancher » (les petits numéros commencent là).
    const alertes = UI.$('.wiki-alertes', conteneur);
    const consignation = consignationDe(entite, contexte);
    if (consignation) alertes.appendChild(consignation);
    if (entite.aTrancher.length) alertes.appendChild(blocContradictions(entite, contexte));
    if (!alertes.children.length) alertes.remove();
    const lecture = UI.$('.wiki-lecture', conteneur);
    // Les morceaux un à un, dans l'ordre de la page : chacun est créé à son tour (Wiki.sectionsEntite les rend un à un),
    // donc ses petits numéros suivent ceux des morceaux d'avant.
    for (const morceau of Wiki.sectionsEntite(entite, contexte)) {
      if (!morceau) continue;
      const element = morceau.textes ? blocTextes(entite, morceau, contexte) : (morceau instanceof Node ? morceau : UI.element(morceau));
      if (element) lecture.appendChild(element);
    }
    if (contexte.responsable && entite.enAttente.length) lecture.appendChild(blocEnAttente(entite));
    if (contexte.refs.nombre()) lecture.appendChild(contexte.refs.section());
  }

  return { rendreEntite };
})());
