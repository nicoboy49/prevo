'use strict';
// Wiki (8/9) — écrans du responsable (lot 6 refondu, ARCHITECTURE.md §20.9 ; D104, D105, D107, D108, D112) : journal
// #/wiki-journal et ses vues (journal, à valider, contradictions, file, en échec, hors du wiki, contrôle du wiki),
// « Traiter la file » avec sa progression et « Arrêter ». L'écriture à la main (#/wiki-ecrire/…) et le calcul du
// contrôle du wiki (Wiki.controleDuWiki) sont dans wiki-ecrire-ecrans.js (9/9), chargé juste après.
//
// Précisions au contrat (§20.9) :
//  - adresses : #/wiki-journal (journal : à valider, puis refusées, puis toutes les entrées), ?vue=a-valider |
//    contradictions | file | echecs | hors | controle, ?entree=<WJ-…> (une entrée, avec ses changements) ;
//  - Wiki.rattraper({ relire: true }) est appelé à chaque affichage du journal (§20.7 ; une page du wiki, elle, ne relit rien) ;
//  - une proposition : OT (lien), date d'intervention, « Intervention antérieure », modèle, rang, « Acceptée à la
//    relance, après le refus : » et les raisons du premier refus (D106 : entrée d'ingestion acceptée — à valider, rien à
//    ajouter, validée, rejetée, à refaire — qui garde des raisons ; une refusée garde « Raisons du refus ») ; contradictions
//    en tête (jamais de case à cocher : elle se valide seule) ; par page, d'après Wiki.comparerTextes : phrases
//    nouvelles surlignées (<mark>, étiquette « Nouvelle »), reprises (<ins>, ancienne forme en <del>), retirées (<del>),
//    identiques repliées (<details>) ; page créée en entier ; « Valider », « Rejeter » (motif exigé dans la page) ;
//  - « en échec » : la dernière entrée refusée (puis rejetée) d'un OT qui n'en a pas d'autre en cours, « Relancer » ;
//  - « Traiter la file » : Wiki.traiterFile({ signal, surProgres }) ; « Arrêter » coupe le signal seulement (les
//    envois partis finissent) ; le traitement continue si l'on quitte l'écran, le bilan s'affiche au retour ;
//    version web ou IA non utilisable : pas de bouton, le message d'ia.js (Ia.MESSAGE_VERSION_WEB, ou celui que
//    rend Ia.envoyerRequete sans rien envoyer : son signal est déjà coupé) ;
//  - aucun HTML venu des données : tout passe par UI.html ; les citations d'une phrase sont du texte.

Object.assign(Wiki, (() => {

  const TABLES = ['wiki_journal', 'wiki_pages', 'ordres_travail', 'equipements', 'articles'];
  const VUES = [   // libellés lus à l'affichage
    { id: '', get libelle() { return I18n.t('wiki.libelle.journal'); } }, { id: 'a-valider', get libelle() { return I18n.t('wiki.libelle.valider'); } },
    { id: 'contradictions', get libelle() { return I18n.t('wiki.libelle.contradictions'); } }, { id: 'file', get libelle() { return I18n.t('wiki.libelle.file'); } },
    { id: 'echecs', get libelle() { return I18n.t('wiki.libelle.vue_echecs'); } }, { id: 'hors', get libelle() { return I18n.t('wiki.libelle.hors_wiki'); } },
    { id: 'controle', get libelle() { return I18n.t('wiki.libelle.controle_wiki'); } },
  ];
  const TONS = { 'en file': 'neutre', 'à valider': 'info', 'validée': 'ok', 'rejetée': 'ko', 'à refaire': 'attention',
    'refusée': 'ko', 'rien à ajouter': 'neutre', 'appliquée': 'ok' };
  const natures = () => ({ ingestion: I18n.t('wiki.natures.ot_ingere'), manuel: I18n.t('wiki.natures.ecriture_main'), 'décision': I18n.t('wiki.natures.decision') });
  const decisions = () => ({ ancien: I18n.t('wiki.decisions.ancien_reste'), nouveau: I18n.t('wiki.decisions.nouveau_remplace'), 'les deux': I18n.t('wiki.decisions.deux_sont_vrais') });
  const libellesCompteurs = () => [['enCours', I18n.t('wiki.compteurs.en_cours')], ['restants', I18n.t('wiki.compteurs.restants')], ['acceptees', I18n.t('wiki.compteurs.acceptees')],
    ['rien', I18n.t('wiki.compteurs.rien_ajouter')], ['refusees', I18n.t('wiki.compteurs.refusees')], ['rejouees', I18n.t('wiki.compteurs.rejouees')]];
  const S = Wiki.SEUILS;
  // Limites des textes rédigés en clair (Wiki.LIMITES, §20.12) : « « En bref » 5 phrases et 120 mots, …, un savoir-faire … ».
  const limites = () => Object.entries(Wiki.LIMITES).flatMap(([type, l]) => (l.page ? [[type === 'savoir-faire' ? I18n.t('wiki.limites.un_savoir_faire') : type, l.page]]
    : Object.entries(l.rubriques).map(([rubrique, x]) => ['« ' + rubrique + ' »', x]))).map(([nom, x]) => nom + ' ' + (x.mots === null
      ? I18n.t('wiki.longueur.phrases', { n: x.phrases }) : I18n.t('wiki.longueur.phrases_mots', { phrases: x.phrases, mots: x.mots }))).join(', ');
  const TYPES_CONTROLE = [
    { type: 'lien-casse', get libelle() { return I18n.t('wiki.libelle.liens_casses'); },
      get aide() { return I18n.t('wiki.aide.lien_titre_vers_page'); } },
    { type: 'orpheline', get libelle() { return I18n.t('wiki.libelle.pages_orphelines'); }, get aide() { return I18n.t('wiki.aide.savoir_faire_sans_machine'); } },
    { type: 'sans-ot', get libelle() { return I18n.t('wiki.libelle.pages_sans_ot_cite'); }, get aide() { return I18n.t('wiki.aide.chaque_phrase_wiki_cite'); } },
    { type: 'titre-proche', get libelle() { return I18n.t('wiki.libelle.titres_trop_proches'); }, get aide() { return I18n.t('wiki.aide.meme_titre_fois_mots'); } },
    { type: 'trop-longue', get libelle() { return I18n.t('wiki.libelle.textes_trop_longs'); }, get aide() { return I18n.t('wiki.aide.plus_dela_sous_pages', { limites: limites() }); } },
    { type: 'anciennes-rubriques', get libelle() { return I18n.t('wiki.libelle.anciennes_rubriques'); }, get aide() { return I18n.t('wiki.aide.texte_ecrit_avant_refonte'); } },
    { type: 'type-retire', get libelle() { return I18n.t('wiki.libelle.types_page_retires'); }, get aide() { return I18n.t('wiki.aide.page_mode_sous_page'); } },
    { type: 'contradiction-ancienne', get libelle() { return I18n.t('wiki.libelle.contradictions_anciennes'); },
      get aide() { return I18n.t('wiki.aide.ouvertes_depuis_plus_jours', { n: S.contradictionAncienneJours }); } },
    { type: 'ancrage-disparu', get libelle() { return I18n.t('wiki.libelle.ancrages_disparus'); },
      get aide() { return I18n.t('wiki.aide.page_ancree_equipement_article'); } },
  ];
  const ACCEPTEES = ['à valider', 'rien à ajouter', 'validée', 'rejetée', 'à refaire'];   // ses raisons : le refus d'avant la relance

  let annonce = null;        // message posé avant un réaffichage : { type, contenu }
  let traitement = null;     // « Traiter la file » en cours : { controleur, etat, arret }

  // ===========================================================================================
  // 1. Petits outils
  // ===========================================================================================

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  function json(valeur) {
    try { const lu = JSON.parse(valeur); return Array.isArray(lu) ? lu.filter((x) => x && typeof x === 'object') : []; }
    catch (erreur) { return []; }
  }

  function rang(entree) {
    return Number(entree.ordre) || 0;
  }

  function parRang(a, b) {
    return rang(a) - rang(b) || (texte(a.id) < texte(b.id) ? -1 : 1);
  }

  function journal() {
    return Donnees.lignes('wiki_journal');
  }

  const changementsDe = (entree) => json(entree.changements);
  const contradictionsDe = (entree) => json(entree.contradictions);

  function annoncer(type, contenu) {
    annonce = { type, contenu };
  }

  function badge(statut) {
    return UI.badgeValeur('wiki_journal', 'statut', statut, TONS[texte(statut)] || 'neutre');
  }

  function lienOt(id) {
    return texte(id) ? UI.html`<a class="wj-lien-ot" href="#/ot/${encodeURIComponent(id)}">${id}</a>` : '';
  }

  function titreOt(id) {
    const ot = texte(id) ? Donnees.trouver('ordres_travail', texte(id)) : null;
    return ot ? texte(ot.titre) : '';
  }

  /** Identifiant canonique (#/wiki/<id>) d'une ligne de wiki_pages : EQ-… ou ART-… s'il existe, sinon WP-…. */
  function idCanonique(ligne) {
    const type = texte(ligne.type);
    if (type === 'équipement' && Donnees.trouver('equipements', texte(ligne.equipement_id))) return texte(ligne.equipement_id);
    if (type === 'composant' && texte(ligne.article_id) && Donnees.trouver('articles', texte(ligne.article_id))) return texte(ligne.article_id);
    return texte(ligne.id);
  }

  /** Identifiant canonique d'une clé de page (EQ:, ART:, WP:, TITRE:) ou, à défaut, d'un titre ; '' si aucune. */
  function idDePage(cle, titre) {
    const valeur = texte(cle);
    if (valeur.startsWith('EQ:') || valeur.startsWith('ART:')) return valeur.slice(valeur.indexOf(':') + 1);
    const lignes = Donnees.lignes('wiki_pages');
    let ligne = valeur.startsWith('WP:') ? lignes.find((l) => l.id === valeur.slice(3)) : null;
    const forme = valeur.startsWith('TITRE:') ? valeur.slice(6) : Wiki.comparable(titre);
    if (!ligne && forme) ligne = lignes.find((l) => texte(l.statut) !== 'archivée' && Wiki.comparable(l.titre) === forme);
    return ligne ? idCanonique(ligne) : '';
  }

  // ===========================================================================================
  // 2. Sélections du journal
  // ===========================================================================================

  function aValider() {
    return journal().filter((e) => texte(e.nature) === 'ingestion' && texte(e.statut) === 'à valider').sort(parRang);
  }

  function contradictionsOuvertes() {
    return journal().filter((e) => texte(e.statut) === 'validée').sort(parRang)
      .flatMap((entree) => contradictionsDe(entree).filter((c) => texte(c.statut) === 'ouverte').map((c) => ({ entree, c })));
  }

  /** Dernière entrée rejetée ou refusée de chaque OT qui n'a pas d'autre entrée en cours (Wiki.remettreEnFile). */
  function relancables() {
    const lignes = journal().filter((e) => texte(e.nature) === 'ingestion');
    const echec = (e) => ['rejetée', 'refusée'].includes(texte(e.statut));
    const vivants = new Set(lignes.filter((e) => !echec(e)).map((e) => texte(e.ot_id)));
    const dernieres = new Map();
    lignes.filter((e) => echec(e) && !vivants.has(texte(e.ot_id))).forEach((e) => {
      const avant = dernieres.get(texte(e.ot_id));
      if (!avant || texte(avant.id) < texte(e.id)) dernieres.set(texte(e.ot_id), e);
    });
    return Array.from(dernieres.values()).sort((a, b) => (texte(a.id) < texte(b.id) ? 1 : -1));
  }

  function compteurs() {
    return {
      'a-valider': aValider().length, contradictions: contradictionsOuvertes().length, file: Wiki.file().length,
      echecs: relancables().filter((e) => texte(e.statut) === 'refusée').length, hors: Wiki.horsDuWiki().length,
      controle: Wiki.controleDuWiki().length,
    };
  }

  // ===========================================================================================
  // 3. Une entrée : en-tête, contradictions, changements par page
  // ===========================================================================================

  function phraseHtml(phrase) {
    return UI.html`<span class="wj-phrase">${phrase.propre || phrase.texte}</span>${phrase.ot.length
      ? UI.html` <span class="wj-citations">${phrase.ot.map((id, n) => UI.html`${n ? ' ' : ''}<span class="wj-citation">[${id}]</span>`)}</span>` : ''}`;
  }

  /** Changements d'une page modifiée : nouvelles surlignées, reprises avec l'ancienne forme barrée, identiques repliées. */
  function diffHtml(avant, apres) {
    const c = Wiki.comparerTextes(avant, apres);
    const genres = new Map();
    c.nouvelles.forEach((phrase) => genres.set(phrase.texte, null));
    c.reprises.forEach((reprise) => genres.set(reprise.phrase.texte, reprise.anciennes));
    const groupes = Wiki.lireTexte(apres).rubriques.map((r) => ({ nom: r.nom, phrases: r.phrases.filter((p) => genres.has(p.texte)) }))
      .filter((groupe) => groupe.phrases.length);
    const ligne = (phrase) => {
      const anciennes = genres.get(phrase.texte);
      return anciennes
        ? UI.html`<li class="wj-reprise"><span class="wj-etiquette">${I18n.t('wiki.diff.reprise')}</span> <ins>${phraseHtml(phrase)}</ins>
            <span class="wj-avant">${I18n.t('wiki.diff.avant')} ${anciennes.map((a) => UI.html`<del>${phraseHtml(a)}</del>`)}</span></li>`
        : UI.html`<li class="wj-nouvelle"><span class="wj-etiquette">Nouvelle</span> <mark>${phraseHtml(phrase)}</mark></li>`;
    };
    return UI.html`${groupes.map((g) => UI.html`<h5 class="wj-rubrique">${g.nom}</h5><ul class="wj-phrases">${g.phrases.map(ligne)}</ul>`)}
      ${c.retirees.length ? UI.html`<ul class="wj-phrases">${c.retirees.map((p) => UI.html`<li class="wj-retiree">
        <span class="wj-etiquette">${I18n.t('wiki.diff.retiree')}</span> <del>${phraseHtml(p)}</del></li>`)}</ul>` : ''}
      ${!groupes.length && !c.retirees.length ? UI.html`<p class="aide">${I18n.t('wiki.diff.aucune_phrase_nouvelle_ni')}</p>` : ''}
      ${c.identiques.length ? UI.html`<details class="wj-identiques"><summary>${I18n.t('wiki.diff.phrases_inchangees', { n: c.identiques.length })}</summary><ul class="wj-phrases">${c.identiques.map((p) => UI.html`<li>${phraseHtml(p)}</li>`)}</ul></details>` : ''}`;
  }

  function texteEntierHtml(valeur) {
    return Wiki.lireTexte(valeur).rubriques.map((r) => UI.html`<h5 class="wj-rubrique">${r.nom}</h5>
      <ul class="wj-phrases">${r.phrases.map((p) => UI.html`<li class="wj-creee">${phraseHtml(p)}</li>`)}</ul>`);
  }

  function changementHtml(c) {
    const genre = c.archivage ? I18n.t('wiki.changement.page_archivee') : (c.creation ? I18n.t('wiki.changement.page_creee') : I18n.t('wiki.changement.page_modifiee'));
    return UI.html`<section class="wj-changement" data-cle="${texte(c.cle)}" data-creation="${c.creation ? 'oui' : 'non'}">
      <h4><span class="wj-page-titre">${texte(c.titre) || texte(c.cle)}</span>
        <span class="badge ${c.creation ? 'violet' : 'neutre'}">${genre}</span>${texte(c.type) ? UI.html` <span class="wj-type">${Schema.libelleValeur('wiki_pages', 'type', c.type)}</span>` : ''}</h4>
      ${c.archivage ? UI.html`<p class="aide">${I18n.t('wiki.changement.page_sort_wiki_texte')}</p>`
        : (c.creation ? texteEntierHtml(c.apres) : diffHtml(c.avant || '', c.apres || ''))}
    </section>`;
  }

  function contradictionsHtml(entree, liste) {
    const libelle = texte(entree.anterieure) === '1' ? I18n.t('wiki.contradictions.observation_anterieure_faits_page') : I18n.t('wiki.contradictions.dit_nouvel_ot');
    return UI.html`<section class="wj-contradictions" aria-label="${I18n.t('wiki.libelle.contradictions')}">
      <h4>${UI.icone('alerte')}<span>${I18n.t('wiki.contradictions.jamais_ecrasee_lire', { n: liste.length })}</span></h4>
      <ul>${liste.map((c) => UI.html`<li data-statut="${texte(c.statut) || 'ouverte'}">
        <p class="wj-contradiction-page">${I18n.t('wiki.contradictions.page_page', { page: c.page })}</p>
        <p>${I18n.html('wiki.contradictions.dit_page', { phrase: c.phrase })}</p>
        <p><b>${libelle}</b> : ${c.observation}${(c.ot || []).map((id) => UI.html` <span class="wj-citation">[${id}]</span>`)}</p>
        ${texte(c.statut) === 'fermée' ? UI.html`<p class="aide">${tranchee(c)}${texte(c.note) ? ' — ' + c.note : ''}</p>` : ''}
      </li>`)}</ul></section>`;
  }

  /** « Tranchée : <décision> — <par>, le <date> » (qui et quand, s'ils sont connus) : une phrase par forme. */
  function tranchee(c) {
    const decision = decisions()[c.decision] || c.decision;
    const par = texte(c.decide_par);
    const date = texte(c.decide_le) ? UI.dateFr(c.decide_le) : '';
    if (par) return date ? I18n.t('wiki.tranchee.tranchee_decision_par_date', { decision, par, date }) : I18n.t('wiki.tranchee.tranchee_decision_par', { decision, par });
    return date ? I18n.t('wiki.tranchee.tranchee_decision_date', { decision, date }) : I18n.t('wiki.tranchee.tranchee_decision', { decision });
  }

  function quoiDe(entree) {
    if (texte(entree.nature) === 'ingestion') return titreOt(entree.ot_id);
    const decision = texte(entree.nature) === 'décision' ? contradictionsDe(entree)[0] : null;
    if (decision) return I18n.t('wiki.quoi_de.decision_page', { page: texte(decision.page), decision: (decisions()[decision.decision] || texte(decision.decision)) });
    return changementsDe(entree).map((c) => texte(c.titre)).filter(Boolean).join(', ');
  }

  function teteHtml(entree) {
    const date = texte(entree.date_intervention);
    if (texte(entree.nature) === 'ingestion') {
      return UI.html`<h3 class="wj-entree-titre">${lienOt(entree.ot_id)} <span>${titreOt(entree.ot_id)}</span></h3>
        <p class="wj-meta">${badge(entree.statut)}${date ? UI.html`<span>${I18n.t('wiki.tete.intervention_date', { date: UI.dateFr(date) })}</span>` : ''}
          ${texte(entree.anterieure) === '1' ? UI.html`<span class="badge attention wj-anterieure">${I18n.t('wiki.tete.intervention_anterieure')}</span>` : ''}
          ${texte(entree.modele) ? UI.html`<span>${I18n.t('wiki.tete.modele_modele', { modele: entree.modele })}</span>` : ''}${rang(entree) ? UI.html`<span>${I18n.t('wiki.tete.rang_rang', { rang: rang(entree) })}</span>` : ''}
          <span class="wj-id">${entree.id}</span></p>`;
    }
    return UI.html`<h3 class="wj-entree-titre">${natures()[texte(entree.nature)] || texte(entree.nature)}${quoiDe(entree) ? ' — ' + quoiDe(entree) : ''}</h3>
      <p class="wj-meta">${badge(entree.statut)}${texte(entree.decide_par) ? UI.html`<span>${I18n.t('wiki.tete.decide_par', { decide_par: entree.decide_par })}</span>` : ''}
        ${texte(entree.decide_le) ? UI.html`<span>${I18n.t('wiki.tete.decide_le', { decide_le: UI.dateHeureFr(entree.decide_le) })}</span>` : ''}<span class="wj-id">${entree.id}</span></p>`;
  }

  /** Raisons, une par ligne ; titrées « Acceptée à la relance, après le refus : » (D106), ou « Raisons du refus : » (carte). */
  function raisonsHtml(entree, carte) {
    const raisons = texte(entree.raisons).split('\n').map(texte).filter(Boolean);
    const relance = texte(entree.nature) === 'ingestion' && ACCEPTEES.includes(texte(entree.statut));
    const titre = relance ? I18n.t('wiki.raisons.acceptee_relance_apres_refus') : (carte ? I18n.t('wiki.raisons.raisons_refus') : '');
    return raisons.length ? UI.html`${titre ? UI.html`<p class="wj-raisons-titre${relance ? ' wj-relance' : ''}"><b>${titre}</b></p>` : ''}
      <ul class="wj-raisons">${raisons.map((r) => UI.html`<li>${r}</li>`)}</ul>` : '';
  }

  function actionsHtml(entree) {
    const id = UI.identifiantUnique('wj-motif');
    return UI.html`<div class="actions wj-actions">
        <button type="button" class="btn btn-primaire wj-valider" data-entree="${entree.id}">${UI.icone('valider')}${I18n.t('wiki.actions.valider')}</button>
        <button type="button" class="btn btn-danger wj-rejeter" data-entree="${entree.id}">${I18n.t('wiki.actions.rejeter')}</button></div>
      <div class="wj-rejet" hidden>
        <div class="champ"><label class="libelle" for="${id}">${I18n.t('wiki.actions.motif_rejet')} <span class="requis" aria-hidden="true">*</span></label>
          <textarea id="${id}" class="wj-motif" rows="3" aria-required="true" aria-describedby="${id}-erreur"
            placeholder="${I18n.t('wiki.actions.ex_phrase_mal_tournee')}"></textarea>
          <p class="erreur-champ" id="${id}-erreur" role="alert" hidden></p></div>
        <div class="actions"><button type="button" class="btn btn-danger wj-confirmer-rejet" data-entree="${entree.id}">${I18n.t('wiki.actions.confirmer_rejet')}</button>
          <button type="button" class="btn btn-fantome wj-annuler-rejet">${I18n.t('commun.bouton.annuler')}</button></div>
      </div>`;
  }

  /** Carte d'une entrée ; options.actions : boutons (Valider et Rejeter, ou Relancer) ; options.selection : case à cocher. */
  function carteHtml(entree, options) {
    const statut = texte(entree.statut);
    const contradictions = contradictionsDe(entree);
    const actions = options.actions && statut === 'à valider';
    const choix = actions && options.selection && !contradictions.length;
    const relance = options.actions && ['rejetée', 'refusée'].includes(statut) && relancables().some((e) => e.id === entree.id);
    return UI.html`<article class="carte wj-entree" data-entree="${entree.id}" data-statut="${statut}">
      <div class="wj-entree-tete">${choix ? UI.html`<label class="case wj-choisir"><input type="checkbox" class="wj-choix"
        value="${entree.id}" data-hors-saisie><span>${I18n.t('wiki.carte.selectionner')}</span></label>` : ''}<div class="wj-entree-titres">${teteHtml(entree)}</div></div>
      ${contradictions.length ? contradictionsHtml(entree, contradictions) : ''}
      ${changementsDe(entree).map(changementHtml)}
      ${texte(entree.motif) ? UI.html`<p class="wj-motif-lu">${I18n.html('wiki.carte.motif_motif', { motif: entree.motif })}</p>` : ''}
      ${raisonsHtml(entree, true)}
      ${actions ? actionsHtml(entree) : ''}
      ${relance ? UI.html`<div class="actions"><button type="button" class="btn btn-secondaire wj-relancer" data-entree="${entree.id}">${UI.icone('actualiser')}${I18n.t('wiki.carte.relancer')}</button></div>` : ''}
    </article>`;
  }

  function ligneHtml(entree) {
    const date = texte(entree.decide_le) || texte(entree.traite_le) || texte(entree.cree_le);
    return UI.html`<li class="wj-ligne" data-entree="${entree.id}" data-statut="${texte(entree.statut)}">
      <div class="wj-ligne-tete"><a class="wj-lien-entree" href="#/wiki-journal?entree=${encodeURIComponent(entree.id)}">${entree.id}</a>${badge(entree.statut)}
        <span class="wj-nature">${natures()[texte(entree.nature)] || texte(entree.nature)}</span>${texte(entree.nature) === 'ingestion' ? lienOt(entree.ot_id) : ''}
        ${date ? UI.html`<span class="wj-date">${UI.dateFr(date)}</span>` : ''}</div>
      ${quoiDe(entree) ? UI.html`<p class="wj-ligne-quoi">${quoiDe(entree)}</p>` : ''}
      ${texte(entree.motif) ? UI.html`<p class="wj-ligne-motif">${I18n.t('wiki.ligne.motif_motif', { motif: entree.motif })}</p>` : ''}${raisonsHtml(entree)}
    </li>`;
  }

  // ===========================================================================================
  // 4. Vues
  // ===========================================================================================

  function enteteSection(id, titre, nombre, bouton) {
    return UI.html`<div class="entete-carte"><h2 id="${id}">${titre} <span class="badge">${nombre}</span></h2>${bouton || ''}</div>`;
  }

  function sectionAValider(liste) {
    const avec = liste.filter((e) => contradictionsDe(e).length);
    return UI.html`<section class="wj-section" id="wj-a-valider" aria-labelledby="wj-titre-a-valider">
      ${enteteSection('wj-titre-a-valider', I18n.t('wiki.libelle.valider'), liste.length)}
      ${liste.length ? UI.html`<p class="aide">${I18n.t('wiki.section_avalider.ordre_ou_elles_ont')}</p>
        ${avec.length ? UI.html`<div class="alerte attention wj-alerte-contradictions" role="status">${UI.icone('alerte')}<div class="alerte-texte">
          <p>${I18n.html('wiki.section_avalider.propositions_portent_contradiction', { n: avec.length, liste: avec.map((e) => e.id + ', ' + e.ot_id).join(' ; ') })}</p></div></div>` : ''}
        <div class="actions wj-selection"><button type="button" class="btn btn-secondaire wj-valider-selection" disabled>${I18n.t('wiki.section_avalider.valider_propositions_selectionnees')}</button>
          <span class="aide">${I18n.t('wiki.section_avalider.proposition_contradiction_pas_case')}</span></div>
        <div class="wj-liste">${liste.map((e) => carteHtml(e, { actions: true, selection: true }))}</div>`
        : UI.vide(I18n.t('wiki.section_avalider.aucune_proposition_valider'), I18n.t('wiki.section_avalider.propositions_ia_arrivent_ici'), 'wiki')}
    </section>`;
  }

  function sectionEchecs(liste, titre, id) {
    return UI.html`<section class="wj-section" id="${id}" aria-labelledby="${id}-titre">${enteteSection(id + '-titre', titre, liste.length)}
      ${liste.length ? UI.html`<div class="wj-liste">${liste.map((e) => carteHtml(e, { actions: true }))}</div>`
        : UI.html`<p class="muted">${I18n.t('wiki.section_echecs.aucune')}</p>`}</section>`;
  }

  function vueJournal() {
    const toutes = journal().slice().sort((a, b) => (texte(a.id) < texte(b.id) ? 1 : -1));
    return UI.html`${sectionAValider(aValider())}
      ${sectionEchecs(relancables().filter((e) => texte(e.statut) === 'refusée'), I18n.t('wiki.vue_journal.refusees_controles'), 'wj-refusees')}
      <section class="wj-section" id="wj-toutes" aria-labelledby="wj-titre-toutes">${enteteSection('wj-titre-toutes', I18n.t('wiki.vue_journal.toutes_entrees'), toutes.length)}
        ${toutes.length ? UI.html`<ul class="wj-lignes">${toutes.map(ligneHtml)}</ul>` : UI.html`<p class="muted">${I18n.t('wiki.vue_journal.journal_vide')}</p>`}
      </section>`;
  }

  function vueContradictions() {
    const ouvertes = contradictionsOuvertes();
    const propositions = aValider().filter((e) => contradictionsDe(e).length);
    return UI.html`<section class="wj-section" id="wj-contradictions" aria-labelledby="wj-titre-contradictions">
      ${enteteSection('wj-titre-contradictions', I18n.t('wiki.vue_contradictions.contradictions_ouvertes'), ouvertes.length)}
      <p class="aide">${I18n.t('wiki.vue_contradictions.signalees_jamais_ecrasees_page')}</p>
      ${ouvertes.length ? UI.html`<ul class="wj-lignes">${ouvertes.map(({ entree, c }) => {
        const id = idDePage(c.pageCle, c.page);
        return UI.html`<li class="wj-ligne wj-contradiction" data-entree="${entree.id}">
          <div class="wj-ligne-tete">${id ? UI.html`<a class="wj-lien-page" href="#/wiki/${encodeURIComponent(id)}">${c.page}</a>` : UI.html`<b>${c.page}</b>`}
            ${lienOt(entree.ot_id)}<span class="wj-date">${I18n.t('wiki.vue_contradictions.depuis', { date: UI.dateFr(entree.decide_le || entree.traite_le) })}</span></div>
          <p>${I18n.html('wiki.contradictions.dit_page', { phrase: c.phrase })}</p>
          <p><b>${texte(entree.anterieure) === '1' ? I18n.t('wiki.contradictions.observation_anterieure_faits_page') : I18n.t('wiki.contradictions.dit_nouvel_ot')}</b> : ${c.observation}</p>
        </li>`; })}</ul>` : UI.html`<p class="muted">${I18n.t('wiki.vue_contradictions.aucune_contradiction_ouverte')}</p>`}
    </section>
    ${propositions.length ? UI.html`<section class="wj-section" aria-labelledby="wj-titre-propositions-contradiction">
      ${enteteSection('wj-titre-propositions-contradiction', I18n.t('wiki.vue_contradictions.propositions_contradiction'), propositions.length)}
      <div class="wj-liste">${propositions.map((e) => carteHtml(e, { actions: true }))}</div></section>` : ''}`;
  }

  function ligneFileHtml(entree) {
    const essais = Number(entree.essais) || 0;
    return UI.html`<li class="wj-ligne" data-entree="${entree.id}" data-ot="${texte(entree.ot_id)}">
      <div class="wj-ligne-tete">${lienOt(entree.ot_id)}${badge(entree.statut)}<span class="wj-date">${I18n.t('wiki.ligne_file.intervention_date_intervention', { date_intervention: UI.dateFr(entree.date_intervention) })}</span>
        ${essais ? UI.html`<span class="wj-essais">${I18n.t('wiki.compte.essais', { n: essais })}</span>` : ''}</div>
      ${titreOt(entree.ot_id) ? UI.html`<p class="wj-ligne-quoi">${titreOt(entree.ot_id)}</p>` : ''}
      ${texte(entree.motif) ? UI.html`<p class="wj-ligne-motif">${entree.motif}</p>` : ''}
    </li>`;
  }

  /** '' si l'IA est utilisable sur ce poste ; sinon le message du lot 4 (ia.js), sans aucun envoi. */
  async function raisonSansIa() {
    if (Ia.versionWeb()) return Ia.MESSAGE_VERSION_WEB;
    if (Ia.active()) return '';
    const coupe = new AbortController();
    coupe.abort();
    try { await Ia.envoyerRequete(null, coupe.signal); } catch (erreur) {
      if (!(erreur instanceof Ia.IaAnnulee)) return (erreur && erreur.message) || String(erreur);
    }
    return '';
  }

  async function vueFile() {
    const file = Wiki.file();
    const sansIa = await raisonSansIa();
    const bouton = !sansIa && file.length && !traitement
      ? UI.html`<button type="button" class="btn btn-primaire wj-traiter">${UI.icone('wiki')}${I18n.t('wiki.vue_file.traiter_file')}</button>` : '';
    return UI.html`<section class="wj-section" id="wj-file" aria-labelledby="wj-titre-file">
      ${enteteSection('wj-titre-file', I18n.t('wiki.vue_file.file_wiki'), file.length, bouton)}
      <p class="aide">${I18n.t('wiki.vue_file.requete_neuve_ot_plus', { agentsSimultanes: S.agentsSimultanes })}</p>
      ${sansIa ? UI.html`<div class="alerte attention wj-sans-ia" role="status">${UI.icone('alerte')}<div class="alerte-texte"><p>${sansIa}</p></div></div>` : ''}
      <div class="carte wj-progression" id="wj-progression" role="status" hidden></div>
      ${file.length ? UI.html`<ol class="wj-lignes wj-file">${file.map(ligneFileHtml)}</ol>`
        : UI.vide(I18n.t('wiki.vue_file.file_vide'), I18n.t('wiki.vue_file.ot_entre_cloture_administrative'), 'wiki')}
    </section>`;
  }

  function vueHors() {
    const hors = Wiki.horsDuWiki();
    const parEquipement = new Map();
    hors.forEach((ot) => parEquipement.set(texte(ot.equipement_id), (parEquipement.get(texte(ot.equipement_id)) || 0) + 1));
    const groupes = Array.from(parEquipement, ([id, nombre]) => ({ id, nombre, equipement: Donnees.trouver('equipements', id) || {} }))
      .sort((a, b) => b.nombre - a.nombre || (texte(a.equipement.repere) < texte(b.equipement.repere) ? -1 : 1));
    return UI.html`<section class="wj-section" id="wj-hors" aria-labelledby="wj-titre-hors">
      ${enteteSection('wj-titre-hors', I18n.t('wiki.libelle.hors_wiki'), hors.length)}
      ${hors.length ? UI.html`<p class="wj-hors-total" data-nombre="${hors.length}">${I18n.html('wiki.vue_hors.ot_clotures_administrativement_sont', { n: hors.length })}</p>
        <div class="actions"><button type="button" class="btn btn-primaire wj-ajouter" data-tout="1" data-equipement="" data-nombre="${hors.length}">
          ${UI.icone('ajouter')}${I18n.t('wiki.vue_hors.ajouter_ot_file', { n: hors.length })}</button></div>
        <ul class="wj-lignes wj-hors">${groupes.map((g) => UI.html`<li class="wj-ligne wj-hors-equipement" data-equipement="${g.id}" data-nombre="${g.nombre}">
          <div class="wj-hors-ligne"><span class="wj-hors-nom"><b>${texte(g.equipement.repere) || g.id || I18n.t('wiki.vue_hors.sans_equipement')}</b>
            ${texte(g.equipement.designation)}</span><span class="badge info">${I18n.t('wiki.compte.ot', { n: g.nombre })}</span>
            <button type="button" class="btn btn-secondaire wj-ajouter" data-equipement="${g.id}" data-nombre="${g.nombre}">${I18n.t('wiki.vue_hors.ajouter_ot', { n: g.nombre })}</button></div>
        </li>`)}</ul>`
        : UI.vide(I18n.t('wiki.vue_hors.tous_ot_clotures_administrativement'), I18n.t('wiki.vue_hors.ils_entrent_cloture_administrative'), 'wiki')}
    </section>`;
  }

  function vueEchecs() {
    const liste = relancables();
    return UI.html`${sectionEchecs(liste.filter((e) => texte(e.statut) === 'refusée'), I18n.t('wiki.vue_echecs.echec_refusees_controles'), 'wj-echecs')}
      ${sectionEchecs(liste.filter((e) => texte(e.statut) === 'rejetée'), I18n.t('wiki.vue_echecs.rejetees'), 'wj-rejetees')}`;
  }

  function vueControle() {
    const problemes = Wiki.controleDuWiki();
    return UI.html`<section class="wj-section" id="wj-controle" aria-labelledby="wj-titre-controle">
      ${enteteSection('wj-titre-controle', I18n.t('wiki.libelle.controle_wiki'), problemes.length)}
      <p class="aide">${I18n.t('wiki.vue_controle.calcule_ouverture_ecran_sans')}</p>
      ${TYPES_CONTROLE.map((t) => {
        const liste = problemes.filter((p) => p.type === t.type);
        return UI.html`<section class="carte wj-controle-type" data-type="${t.type}" aria-labelledby="wj-controle-${t.type}">
          <h3 id="wj-controle-${t.type}">${t.libelle} <span class="badge ${liste.length ? 'attention' : 'ok'}">${liste.length}</span></h3>
          <p class="aide">${t.aide}</p>
          ${liste.length ? UI.html`<ul class="wj-lignes wj-problemes">${liste.map((p) => UI.html`<li class="wj-ligne" data-page="${p.page}">
            <div class="wj-ligne-tete"><a class="wj-lien-page" href="#/wiki/${encodeURIComponent(p.page)}">${p.titre || p.page}</a>
              <a class="wj-modifier" href="#/wiki-ecrire/${encodeURIComponent(p.page)}">${I18n.t('commun.bouton.modifier')}</a></div>
            <p class="wj-probleme">${p.message}</p></li>`)}</ul>` : UI.html`<p class="muted">${I18n.t('wiki.vue_controle.aucun')}</p>`}
        </section>`; })}
    </section>`;
  }

  function vueEntree(id) {
    const entree = Donnees.trouver('wiki_journal', id);
    const retour = UI.html`<p><a class="btn btn-fantome" href="#/wiki-journal">${UI.icone('retour')}${I18n.t('wiki.vue_entree.tout_journal')}</a></p>`;
    return entree ? UI.html`${retour}${carteHtml(entree, { actions: true })}`
      : UI.html`${retour}${UI.vide(I18n.t('wiki.vue_entree.entree_introuvable'), I18n.t('wiki.vue_entree.aucune_entree_journal_porte', { id }), 'wiki')}`;
  }

  const RENDUS = { '': vueJournal, 'a-valider': () => sectionAValider(aValider()), contradictions: vueContradictions,
    file: vueFile, echecs: vueEchecs, hors: vueHors, controle: vueControle };

  // ===========================================================================================
  // 5. Actions : valider, rejeter, relancer, ajouter à la file
  // ===========================================================================================

  // Une action à la fois ; après le réaffichage, les clics sont ignorés un court instant : un double clic ne doit
  // jamais agir sur la carte arrivée sous le pointeur (une proposition que le responsable n'a pas choisie).
  const REPOS_APRES_ACTION_MS = 600;
  let actionEnCours = false;
  let reposJusqua = 0;
  let racineEnRepos = null;                     // l'écran réaffiché après l'action (une autre vue n'est pas bloquée)

  function clicPermis(evenement, racine) {
    return !actionEnCours && evenement.detail <= 1 && !(racine === racineEnRepos && performance.now() < reposJusqua);
  }

  /** Lance une action, puis réaffiche l'écran avec son bilan ; un refus s'affiche avec son message. */
  async function agir(bouton, action) {
    const racine = bouton.closest('.wj');
    actionEnCours = true;
    racine.dataset.occupe = '1';
    UI.$$('.wj-corps button', racine).forEach((b) => { b.disabled = true; });
    bouton.setAttribute('aria-busy', 'true');
    try {
      await action();
    } catch (erreur) {
      if (erreur instanceof Donnees.ErreurValidation) annoncer('important', UI.html`${I18n.html('wiki.agir.refuse_erreur_message', { erreurMessage: erreur.message })}`);
      else {
        annoncer('important', UI.html`${I18n.html('wiki.agir.action_pas_abouti', { raisonErreur: App.raisonErreur(erreur) })}`);
        App.signalerErreur(erreur, 'journal du wiki');
      }
    }
    try {
      await App.reafficher();
    } finally {
      actionEnCours = false;
      reposJusqua = performance.now() + REPOS_APRES_ACTION_MS;
      // Repos visible (data-occupe) : les tests et les lecteurs attendent qu'il soit levé.
      const nouvelle = document.querySelector('.wj');
      racineEnRepos = nouvelle;
      if (nouvelle) {
        nouvelle.dataset.occupe = '1';
        setTimeout(() => { delete nouvelle.dataset.occupe; }, REPOS_APRES_ACTION_MS);
      }
    }
  }

  async function validerIds(ids) {
    if (!ids.length) return;
    const bilan = await Wiki.valider(ids);
    const nombre = bilan.validees.length;
    annoncer(bilan.aRefaire.length ? 'attention' : 'succes', UI.html`${nombre
      ? UI.html`<b>${I18n.t('wiki.valider_ids.propositions_validees', { n: nombre })}</b> : ${bilan.validees.join(', ')}.`
      : UI.html`<b>${I18n.t('wiki.valider_ids.aucune_proposition_validee')}</b>`}${bilan.aRefaire.length ? UI.html` <span class="wj-bilan-a-refaire">${I18n.t('wiki.valider_ids.passees_refaire_page_avait', { propositions: bilan.aRefaire.join(', ') })}</span>` : ''}`);
  }

  function ouvrirRejet(bouton, ouvrir) {
    const carte = bouton.closest('.wj-entree');
    UI.$('.wj-rejet', carte).hidden = !ouvrir;
    UI.$('.wj-actions', carte).hidden = ouvrir;
    (ouvrir ? UI.$('.wj-motif', carte) : UI.$('.wj-rejeter', carte)).focus();
  }

  function confirmerRejet(bouton) {
    const carte = bouton.closest('.wj-entree');
    const champ = UI.$('.wj-motif', carte);
    const erreur = UI.$('.wj-rejet .erreur-champ', carte);
    const motif = texte(champ.value);
    if (!motif) {
      erreur.textContent = I18n.t('wiki.confirmer_rejet.motif_rejet_obligatoire');
      erreur.hidden = false;
      champ.setAttribute('aria-invalid', 'true');
      champ.focus();
      return;
    }
    agir(bouton, async () => {
      const resultat = await Wiki.rejeter(bouton.dataset.entree, motif);
      annoncer('succes', UI.html`${I18n.html('wiki.confirmer_rejet.proposition_rejetee_motif', { rejetee: resultat.rejetee, motif })}${resultat.aRefaire.length
        ? UI.html` <span class="wj-bilan-a-refaire">${I18n.t('wiki.confirmer_rejet.passees_refaire_ot_reviennent', { propositions: resultat.aRefaire.join(', ') })}</span>` : ''}`);
    });
  }

  async function relancer(id) {
    const nouvelle = await Wiki.remettreEnFile(id);
    const entree = Donnees.trouver('wiki_journal', nouvelle) || {};
    annoncer('succes', UI.html`${I18n.html('wiki.relancer.ot_remis_file_sera', { ot_id: entree.ot_id, nouvelle })}`);
  }

  // tout : tous les OT hors du wiki ; sinon ceux de cet équipement (« Sans équipement » : equipementId vide).
  async function ajouterALaFile(tout, equipementId) {
    const ids = Wiki.horsDuWiki().filter((ot) => tout || texte(ot.equipement_id) === texte(equipementId)).map((ot) => ot.id);
    const nombre = await Wiki.mettreEnFile(ids);
    annoncer('succes', UI.html`${I18n.html('wiki.ajouter_ala_file.ot_ajoutes', { n: nombre })}`);
  }

  function majSelection(racine) {
    const bouton = UI.$('.wj-valider-selection', racine);
    if (!bouton) return;
    const nombre = UI.$$('.wj-choix:checked', racine).length;
    bouton.disabled = !nombre;
    bouton.textContent = nombre ? I18n.t('wiki.maj_selection.valider_propositions_selectionnees', { nombre }) : I18n.t('wiki.section_avalider.valider_propositions_selectionnees');
  }

  // ===========================================================================================
  // 6. « Traiter la file » : progression et « Arrêter »
  // ===========================================================================================

  function progressionHtml() {
    return UI.html`<div class="wj-progression-tete"><b>${I18n.t('wiki.progression.traitement_file_cours')}</b>
        <button type="button" class="btn btn-danger wj-arreter">${I18n.t('wiki.progression.arreter')}</button></div>
      <progress class="wj-barre" max="1" value="0" aria-label="${I18n.t('wiki.progression.ot_traites')}"></progress>
      <dl class="wj-compteurs">${libellesCompteurs().map(([cle, libelle]) => UI.html`<div data-compteur="${cle}"><dt>${libelle}</dt>
        <dd><b class="wj-nombre">0</b>${cle === 'enCours' ? UI.html` <small>${I18n.t('wiki.progression.plus_agents_simultanes', { agentsSimultanes: S.agentsSimultanes })}</small>` : ''}</dd></div>`)}</dl>
      <p class="aide wj-arret" hidden>${I18n.t('wiki.progression.arret_demande_envois_deja')}</p>`;
  }

  function majProgression() {
    const zone = document.getElementById('wj-progression');
    if (!zone) return;
    zone.hidden = !traitement;
    if (!traitement) return;
    if (!UI.$('.wj-compteurs', zone)) UI.remplir(zone, progressionHtml());
    const etat = traitement.etat;
    libellesCompteurs().forEach(([cle]) => { UI.$('[data-compteur="' + cle + '"] .wj-nombre', zone).textContent = String(etat[cle] || 0); });
    const faits = (etat.acceptees || 0) + (etat.rien || 0) + (etat.refusees || 0);
    const barre = UI.$('.wj-barre', zone);
    barre.max = Math.max(1, faits + (etat.restants || 0) + (etat.enCours || 0));
    barre.value = faits;
    UI.$('.wj-arreter', zone).disabled = traitement.arret;
    UI.$('.wj-arret', zone).hidden = !traitement.arret;
  }

  function bilanHtml(bilan, arret) {
    const reste = Wiki.file().length;
    const titre = bilan.erreur ? I18n.t('wiki.bilan.traitement_interrompu') : (arret ? I18n.t('wiki.bilan.traitement_arrete_demande') : I18n.t('wiki.bilan.traitement_file_termine'));
    const acceptees = I18n.t('wiki.bilan.propositions_valider', { n: bilan.acceptees || 0 });
    const refusees = I18n.t('wiki.bilan.n_refusees', { n: bilan.refusees || 0 });
    const rejouees = I18n.t('wiki.bilan.n_rejouees', { n: bilan.rejouees || 0 });
    const restent = I18n.t('wiki.bilan.ot_restent', { n: reste });
    const rien = bilan.rien || 0;
    const message = (bilan.erreur && bilan.erreur.message) || String(bilan.erreur);
    return UI.html`${I18n.html('wiki.bilan.sans_rien_ajouter_file', { titre, acceptees, rien, refusees, rejouees, restent })}${bilan.erreur ? UI.html`
      <span class="wj-erreur-ia">${I18n.t('wiki.bilan.ot_non_traites_restent', { message })}</span>` : ''}`;
  }

  async function lancerTraitement() {
    if (traitement) return;
    const bouton = UI.$('.wj-traiter');
    if (bouton) bouton.hidden = true;
    const controleur = new AbortController();
    traitement = { controleur, arret: false, etat: { enCours: 0, restants: Wiki.file().length, acceptees: 0, rien: 0, refusees: 0, rejouees: 0 } };
    majProgression();
    let bilan;
    try {
      bilan = await Wiki.traiterFile({ signal: controleur.signal,
        surProgres: (etat) => { if (traitement) { traitement.etat = etat; majProgression(); } } });
    } catch (erreur) {
      bilan = Object.assign({}, traitement.etat, { erreur });
    }
    const arret = traitement.arret;
    traitement = null;
    annoncer(bilan.erreur ? 'important' : (bilan.refusees ? 'attention' : 'succes'), bilanHtml(bilan, arret));
    UI.toast(bilan.erreur ? I18n.t('wiki.lancer_traitement.traitement_file_interrompu') : I18n.t('wiki.lancer_traitement.traitement_file_termine'), bilan.erreur ? 'attention' : 'succes');
    if (UI.$('.wj[data-vue="file"]')) await App.reafficher();
  }

  function arreterTraitement() {
    if (!traitement || traitement.arret) return;
    traitement.arret = true;
    traitement.controleur.abort();
    majProgression();
  }

  // ===========================================================================================
  // 7. Écran #/wiki-journal
  // ===========================================================================================

  function navigation(vue, nombres) {
    return UI.html`<nav class="wj-vues" aria-label="${I18n.t('wiki.navigation.vues_journal_wiki')}">${VUES.map((v) => UI.html`<a class="wj-vue"
      href="#/wiki-journal${v.id ? '?vue=' + v.id : ''}" data-vue="${v.id || 'journal'}"${v.id === vue ? UI.brut(' aria-current="page"') : ''}>${v.libelle}${v.id
      ? UI.html` <span class="badge">${nombres[v.id]}</span>` : ''}</a>`)}</nav>`;
  }

  function brancher(racine) {
    racine.addEventListener('click', (evenement) => {
      const bouton = evenement.target.closest('button');
      if (!bouton || !racine.contains(bouton) || bouton.disabled) return;
      if (!clicPermis(evenement, bouton.closest('.wj'))) { evenement.preventDefault(); return; }
      const id = bouton.dataset.entree;
      const classe = (nom) => bouton.classList.contains(nom);
      if (classe('wj-valider')) agir(bouton, () => validerIds([id]));
      else if (classe('wj-valider-selection')) agir(bouton, () => validerIds(UI.$$('.wj-choix:checked', racine).map((c) => c.value)));
      else if (classe('wj-rejeter')) ouvrirRejet(bouton, true);
      else if (classe('wj-annuler-rejet')) ouvrirRejet(bouton, false);
      else if (classe('wj-confirmer-rejet')) confirmerRejet(bouton);
      else if (classe('wj-relancer')) agir(bouton, () => relancer(id));
      else if (classe('wj-ajouter')) agir(bouton, () => ajouterALaFile(bouton.dataset.tout === '1', bouton.dataset.equipement));
      else if (classe('wj-traiter')) lancerTraitement();
      else if (classe('wj-arreter')) arreterTraitement();
    });
    racine.addEventListener('change', (evenement) => {
      if (evenement.target.classList.contains('wj-choix')) majSelection(racine);
    });
  }

  async function afficherJournal(conteneur, parametres) {
    App.definirTitre(I18n.t('wiki.journal.journal_wiki'));
    try {
      await Wiki.rattraper({ relire: true });     // à l'ouverture du journal seulement : pages relues (§20.7)
    } catch (erreur) {
      console.warn('Prévo (wiki) : rattrapage du journal impossible (' + (erreur && erreur.message) + ').', erreur);
    }
    const requete = (parametres && parametres.requete) || new URLSearchParams();
    const demandee = texte(requete.get('vue'));
    const vue = VUES.some((v) => v.id === demandee) ? demandee : '';
    const entreeId = texte(requete.get('entree'));
    const corps = entreeId ? vueEntree(entreeId) : await RENDUS[vue]();
    UI.remplir(conteneur, UI.html`<div class="wiki wiki-journal wj" data-vue="${entreeId ? 'entree' : (vue || 'journal')}">
      <div class="entete-page"><div>
        <div class="fil"><a href="#/wiki">${I18n.t('wiki.journal.wiki')}</a></div>
        <h1>${I18n.t('wiki.journal.journal_wiki')}</h1>
        <p>${I18n.t('wiki.journal.propositions_ia_valider_file')}</p>
      </div></div>
      ${navigation(entreeId ? null : vue, compteurs())}
      <div class="wj-annonce"></div>
      <div class="wj-corps">${corps}</div>
    </div>`);
    const racine = UI.$('.wj', conteneur);
    if (annonce) {
      UI.$('.wj-annonce', racine).appendChild(UI.bandeau(annonce.type, annonce.contenu));
      annonce = null;
    }
    brancher(racine);
    majProgression();
  }

  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'wiki-journal', route: /^#\/wiki-journal$/, get titre() { return I18n.t('wiki.ecran.titre_journal'); },
      parent: 'wiki', profils: ['responsable'], tables: TABLES, afficher: afficherJournal,
    });
  });

  return {};
})());
