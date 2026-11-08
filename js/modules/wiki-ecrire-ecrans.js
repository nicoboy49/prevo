'use strict';
// Wiki (9/9) — écriture à la main et contrôle du wiki (lot 6 refondu, ARCHITECTURE.md §20.7, §20.9 ; refonte 2,
// §20.12 ; D97, D108) : écran #/wiki-ecrire/<id> (EQ-…, ART-…, WP-…) et #/wiki-ecrire/nouvelle?rattache=<id canonique>
// (responsable seulement), et Wiki.controleDuWiki(), calculé sans IA et sans rien écrire (la vue « Contrôle du wiki »
// du journal, wiki-journal-ecrans.js, et l'index #/wiki l'affichent). Dernier fichier du module.
//
// Précisions au contrat (§20.9, §20.12) :
//  - écriture : zone de texte du balisage pré-remplie avec le texte validé, aide (balisage, rubriques du texte — d'une
//    machine « En bref » et « Astuces », d'un article « À quoi il sert », d'un savoir-faire les siennes — avec leur rôle
//    et leurs limites, Wiki.LIMITES ; aucune consigne de sécurité), motif facultatif ; « Enregistrer » →
//    Wiki.ecrire(cible, texte, { version (celle affichée), motif }) ; un refus affiche ses raisons (erreur.raisons) une
//    par ligne, rien n'est écrit ; succès : retour à #/wiki/<pageId> ; « Archiver » (page qui a une ligne) demande une
//    confirmation dans la page, puis Wiki.ecrire(cible, null, { archiver: true, version }) et retour à #/wiki ;
//    nouvelle page : un savoir-faire seulement, rattaché à une machine, à un article ou à un savoir-faire (sous-page) ;
//    une ancienne page (Wiki.typeRetire : mode, sous-page d'équipement ou de composant) : « type de page retiré :
//    archivez-la », l'archivage reste possible ;
//  - Wiki.controleDuWiki() → [{ type, page (id canonique), titre, message }], types dans cet ordre : lien-casse
//    ([[titre]] inconnu du texte — ni page, ni machine, ni article, ni panne ; identifiant du champ liens inexistant
//    ou page archivée), orpheline (savoir-faire sans machine, article ni rattache_a vers lequel aucune autre page active
//    ne fait de lien, par son identifiant ou son titre ; les machines et les articles ont toujours leur page),
//    sans-ot (aucune citation dans le texte, page vide comprise), titre-proche (même Wiki.formeDuTitre entre pages
//    actives, une ligne par page), trop-longue (Wiki.LIMITES : chaque rubrique d'un texte de machine ou d'article, un
//    savoir-faire entier, comme §20.6), anciennes-rubriques (texte encore dans des rubriques hors de Wiki.RUBRIQUES de
//    son type : à réécrire dans les siennes), type-retire (Wiki.typeRetire), contradiction-ancienne (ouverte sur une
//    entrée validée depuis plus de contradictionAncienneJours, comptés depuis decide_le, sinon traite_le),
//    ancrage-disparu (equipement_id ou article_id absent ou inactif ; rattache_a vers une page absente ou archivée :
//    la mère d'une sous-page, ou la page d'un savoir-faire — une sous-page n'a pas d'ancrage propre et n'est pas
//    « disparue » pour autant) ; pages actives.

Object.assign(Wiki, (() => {

  const TABLES = ['wiki_pages', 'wiki_journal', 'equipements', 'articles', 'codes_defaillance'];
  const TYPE_NOUVELLE = 'savoir-faire';         // seule page qui se crée (§20.12), sous-page comprise
  /** Nom affiché du type d'un texte rédigé (lu à l'affichage), ou '' pour un type inconnu. */
  function libelleType(type) {
    if (type === 'équipement') return I18n.t('wiki.ecrire.type_machine');
    if (type === 'composant') return I18n.t('wiki.ecrire.type_article');
    return type === 'savoir-faire' ? I18n.t('wiki.ecrire.type_savoir_faire') : '';
  }
  /** Ce qu'on écrit dans chaque texte rédigé (§20.12 ; mêmes mots que la consigne de l'IA), lu à l'affichage. */
  function role(type) {
    if (type === 'équipement') {
      return I18n.t('wiki.role.bref_faut_savoir_abord');
    }
    if (type === 'composant') return I18n.t('wiki.role.quoi_sert_role_machines');
    if (type !== 'savoir-faire') return '';
    return I18n.t('wiki.role.geste_methode_commun_machines');
  }
  const S = Wiki.SEUILS;

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  function estActive(ligne) {
    return texte(ligne.statut) !== 'archivée';
  }

  function titreEquipement(equipement) {
    return [texte(equipement.repere), texte(equipement.designation)].filter(Boolean).join(' — ');
  }

  function titreArticle(article) {
    return texte(article.designation) || texte(article.reference).replace(/^'/, '') || texte(article.id);
  }

  /** { id (canonique), titre } d'une ligne de wiki_pages : EQ-… ou ART-… quand son ancrage existe, sinon WP-…. */
  function repereDe(ligne) {
    const equipement = texte(ligne.type) === 'équipement' && Donnees.trouver('equipements', texte(ligne.equipement_id));
    if (equipement) return { id: texte(equipement.id), titre: titreEquipement(equipement) };
    const article = texte(ligne.type) === 'composant' && texte(ligne.article_id) && Donnees.trouver('articles', texte(ligne.article_id));
    if (article) return { id: texte(article.id), titre: titreArticle(article) };
    return { id: texte(ligne.id), titre: texte(ligne.titre) };
  }

  function jours(depuis) {
    const lu = /^(\d{4})-(\d{2})-(\d{2})/.exec(texte(depuis));
    const jour = /^(\d{4})-(\d{2})-(\d{2})/.exec(Donnees.aujourdhui());
    if (!lu || !jour) return 0;
    return Math.round((Date.UTC(+jour[1], jour[2] - 1, +jour[3]) - Date.UTC(+lu[1], lu[2] - 1, +lu[3])) / 86400000);
  }

  /** « 6 phrases et 130 mots » : une mesure, ou une limite de Wiki.LIMITES (sans les mots quand elle ne les compte pas). */
  function longueur(mesure, limite) {
    return limite.mots === null ? I18n.t('wiki.longueur.phrases', { n: mesure.phrases })
      : I18n.t('wiki.longueur.phrases_mots', { phrases: mesure.phrases, mots: mesure.mots });
  }

  // ===========================================================================================
  // 1. Contrôle du wiki (D108) : calculé, rien n'est corrigé
  // ===========================================================================================

  function controleDuWiki() {
    const lignes = Donnees.lignes('wiki_pages');
    const actives = lignes.filter(estActive);
    const problemes = { 'lien-casse': [], orpheline: [], 'sans-ot': [], 'titre-proche': [], 'trop-longue': [],
      'anciennes-rubriques': [], 'type-retire': [], 'contradiction-ancienne': [], 'ancrage-disparu': [] };
    const noter = (type, ligne, message) => { const r = repereDe(ligne); problemes[type].push({ type, page: r.id, titre: r.titre, message }); };
    const titres = new Set(actives.map((l) => Wiki.comparable(repereDe(l).titre)).concat(actives.map((l) => Wiki.comparable(l.titre))));
    const calcules = Donnees.lignes('equipements').map((e) => ({ id: texte(e.id), titre: titreEquipement(e) }))
      .concat(Donnees.lignes('articles').map((a) => ({ id: texte(a.id), titre: titreArticle(a) })));
    calcules.forEach((p) => titres.add(Wiki.comparable(p.titre)));
    // Pannes (pages calculées, même définition que leur page : Wiki.pannesDuWiki, wiki-journal.js) : liens valides.
    const pannes = typeof Wiki.pannesDuWiki === 'function' ? Wiki.pannesDuWiki() : [];
    pannes.forEach((p) => titres.add(Wiki.comparable(p.titre)));
    const idsPannes = new Set(pannes.map((p) => p.id));
    // Lien vers une page archivée : signalé une fois, par le champ `liens` (« page archivée »), pas comme inconnu.
    const archives = new Set(lignes.filter((l) => !estActive(l)).map((l) => Wiki.comparable(l.titre)));
    const sources = new Map();                    // cible (identifiant ou TITRE:forme) → pages actives qui y renvoient
    const relier = (cible, source) => { if (!sources.has(cible)) sources.set(cible, new Set()); sources.get(cible).add(source); };
    actives.forEach((ligne) => {
      Wiki.liensDe(ligne.texte).forEach((titre) => {
        relier('TITRE:' + Wiki.comparable(titre), ligne.id);
        if (!titres.has(Wiki.comparable(titre)) && !archives.has(Wiki.comparable(titre))) {
          noter('lien-casse', ligne, I18n.t('wiki.controle_du_wiki.lien_vers_page_inconnue', { titre }));
        }
      });
      texte(ligne.liens).split(';').map(texte).filter(Boolean).forEach((id) => {
        relier(id, ligne.id);
        const table = id.startsWith('EQ-') ? 'equipements' : (id.startsWith('ART-') ? 'articles' : 'wiki_pages');
        const cible = id.startsWith('PANNE-') ? idsPannes.has(id) : Donnees.trouver(table, id);
        if (!cible) noter('lien-casse', ligne, I18n.t('wiki.controle_du_wiki.lien_vers_page_inexistante', { id }));
        else if (table === 'wiki_pages' && !estActive(cible)) noter('lien-casse', ligne, I18n.t('wiki.controle_du_wiki.lien_vers_page_archivee', { cibleTitre: texte(cible.titre), id }));
      });
    });
    // Seul un savoir-faire peut être orphelin : une machine ou un article a toujours sa page (§20.12).
    const libre = (l) => texte(l.type) === 'savoir-faire' && !texte(l.rattache_a) && !texte(l.equipement_id) && !texte(l.article_id);
    const liee = (l) => [l.id, repereDe(l).id, 'TITRE:' + Wiki.comparable(l.titre)]
      .some((cible) => Array.from(sources.get(cible) || []).some((source) => source !== l.id));
    actives.filter((l) => libre(l) && !liee(l)).forEach((l) => noter('orpheline', l, I18n.t('wiki.controle_du_wiki.aucune_page_renvoie_ici')));
    actives.filter((l) => !Wiki.citationsDe(l.texte).length)
      .forEach((l) => noter('sans-ot', l, texte(l.texte) ? I18n.t('wiki.controle_du_wiki.texte_cite_aucun_ot') : I18n.t('wiki.controle_du_wiki.page_vide_aucun_ot')));
    const parForme = new Map();
    actives.forEach((l) => { const forme = Wiki.formeDuTitre(repereDe(l).titre); if (forme) parForme.set(forme, (parForme.get(forme) || []).concat([l])); });
    // Titres calculés (équipements, articles) : une page libre de même forme qu'eux est trop proche, sauf sa propre page.
    calcules.forEach((p) => {
      const forme = Wiki.formeDuTitre(p.titre);
      if (forme && parForme.has(forme)) parForme.set(forme, parForme.get(forme).concat([{ calcule: p }]));
    });
    const titreDe = (m) => (m.calcule ? m.calcule.titre : repereDe(m).titre);
    parForme.forEach((memes) => {
      const distincts = memes.filter((m, n) => !m.calcule || !memes.some((autre, k) => k !== n && !autre.calcule
        && repereDe(autre).id === m.calcule.id));
      if (distincts.length < 2) return;
      distincts.filter((l) => !l.calcule).forEach((l) => noter('titre-proche', l, I18n.t('wiki.controle_du_wiki.titre_trop_proche', { titres: distincts.filter((m) => m !== l).map((m) => '« ' + titreDe(m) + ' »').join(', ') })));
    });
    actives.forEach((l) => {
      const retire = Wiki.typeRetire(l);
      if (retire) { noter('type-retire', l, I18n.t('wiki.controle_du_wiki.type_page_retire_archivez', { retire })); return; }
      const type = texte(l.type);
      const limites = Wiki.LIMITES[type];
      const mesures = Object.entries(Wiki.mesurerRubriques(l.texte));
      Object.keys(limites.rubriques).forEach((rubrique) => {
        const trouvee = mesures.find(([nom]) => Wiki.comparable(nom) === Wiki.comparable(rubrique));
        const mesure = trouvee ? trouvee[1] : { phrases: 0, mots: 0 };
        const limite = limites.rubriques[rubrique];
        if (mesure.phrases > limite.phrases || (limite.mots !== null && mesure.mots > limite.mots)) {
          noter('trop-longue', l, I18n.t('wiki.controle_du_wiki.rubrique_longueur_au_plus', { rubrique, longueur: longueur(mesure, limite), limite: longueur(limite, limite) }));
        }
      });
      const page = Wiki.mesurerTexte(l.texte);
      if (limites.page && (page.phrases > limites.page.phrases || page.mots > limites.page.mots)) {
        noter('trop-longue', l, I18n.t('wiki.controle_du_wiki.longueur_au_plus', { longueur: longueur(page, limites.page), limite: longueur(limites.page, limites.page) }));
      }
      const permises = Wiki.RUBRIQUES[type].map(Wiki.comparable);
      const anciennes = mesures.map(([nom]) => nom).filter((nom) => !permises.includes(Wiki.comparable(nom)));
      if (anciennes.length) {
        noter('anciennes-rubriques', l, I18n.t('wiki.controle_du_wiki.reecrire_rubriques', { anciennes: anciennes.map((nom) => '« ' + nom + ' »').join(', '), rubriques: Wiki.RUBRIQUES[type].map((nom) => '« ' + nom + ' »').join(', ') }));
      }
    });
    Donnees.lignes('wiki_journal').filter((e) => texte(e.statut) === 'validée').forEach((entree) => {
      const depuis = texte(entree.decide_le) || texte(entree.traite_le);
      if (jours(depuis) <= S.contradictionAncienneJours) return;
      let liste = [];
      try { liste = JSON.parse(entree.contradictions || '[]') || []; } catch (erreur) { liste = []; }
      liste.filter((c) => c && texte(c.statut) === 'ouverte').forEach((c) => {
        const cle = texte(c.pageCle);
        const ligne = cle.startsWith('WP:') ? lignes.find((l) => l.id === cle.slice(3))
          : actives.find((l) => Wiki.comparable(l.titre) === (cle.startsWith('TITRE:') ? cle.slice(6) : Wiki.comparable(c.page)));
        const id = ligne ? repereDe(ligne).id : cle.slice(cle.indexOf(':') + 1);
        problemes['contradiction-ancienne'].push({ type: 'contradiction-ancienne', page: id, titre: texte(c.page) || id,
          message: I18n.t('wiki.controle_du_wiki.ouverte_depuis', { depuis: UI.dateFr(depuis), references: [texte(entree.ot_id), entree.id].filter(Boolean).join(', ') }) });
      });
    });
    actives.forEach((l) => [['equipement_id', 'equipements'], ['article_id', 'articles']].forEach(([champ, table]) => {
      const id = texte(l[champ]);
      const cible = id ? Donnees.trouver(table, id) : null;
      const machine = table === 'equipements';
      if (id && !cible) noter('ancrage-disparu', l, machine ? I18n.t('wiki.controle_du_wiki.equipement_absent', { id }) : I18n.t('wiki.controle_du_wiki.article_absent', { id }));
      else if (cible && texte(cible.actif) === '0') noter('ancrage-disparu', l, machine ? I18n.t('wiki.controle_du_wiki.equipement_inactif', { id }) : I18n.t('wiki.controle_du_wiki.article_inactif', { id }));
      else if (cible && machine && texte(cible.statut) === 'rebut') noter('ancrage-disparu', l, I18n.t('wiki.controle_du_wiki.equipement_rebut', { id }));
    }));
    // Rattachement (§20.4) : la mère d'une sous-page (même type ; tout rattachement d'une page qui n'est pas un
    // savoir-faire), ou la page d'un savoir-faire, absente ou archivée.
    actives.filter((l) => texte(l.rattache_a)).forEach((l) => {
      const id = texte(l.rattache_a);
      const cible = lignes.find((autre) => autre.id === id);
      const mere = cible ? texte(cible.type) === texte(l.type) : texte(l.type) !== 'savoir-faire';
      if (!cible) noter('ancrage-disparu', l, mere ? I18n.t('wiki.controle_du_wiki.page_mere_absente', { id }) : I18n.t('wiki.controle_du_wiki.page_rattachement_absente', { id }));
      else if (!estActive(cible)) {
        noter('ancrage-disparu', l, mere ? I18n.t('wiki.controle_du_wiki.page_mere_archivee', { cibleTitre: texte(cible.titre), id })
          : I18n.t('wiki.controle_du_wiki.page_rattachement_archivee', { cibleTitre: texte(cible.titre), id }));
      }
    });
    return Object.keys(problemes).flatMap((type) => problemes[type]);
  }

  // ===========================================================================================
  // 2. Écran #/wiki-ecrire/<id> et #/wiki-ecrire/nouvelle
  // ===========================================================================================

  /** Les limites d'un texte (Wiki.LIMITES) en clair : par rubrique, ou le savoir-faire entier et ses sous-pages au-delà. */
  function limitesEnClair(type) {
    const limites = Wiki.LIMITES[type];
    if (!limites) return '';
    if (limites.page) {
      return I18n.t('wiki.limites_en_clair.longueur_savoir_faire', { longueur: longueur(limites.page, limites.page) });
    }
    const liste = Object.keys(limites.rubriques).map((rubrique) => I18n.t('wiki.limites_en_clair.rubrique_longueur_plus', { rubrique, longueur: longueur(limites.rubriques[rubrique], limites.rubriques[rubrique]) })).join(', ');
    return I18n.t('wiki.limites_en_clair.longueurs_citations_non_comptees', { liste });
  }

  /** « ## Rubrique commence une rubrique. Pour <ce texte> : « … », « … », dans cet ordre. » (une phrase par type). */
  function aideRubriques(type) {
    const noms = (Wiki.RUBRIQUES[type] || []).map((r) => String(UI.html`<span class="wj-rubrique-nom">${I18n.t('wiki.aide_rubriques.nom_rubrique', { rubrique: r })}</span>`));
    const rubriques = UI.html`<span class="wj-rubriques">${UI.brut(noms.join(', '))}</span>`;
    if (type === 'équipement') return I18n.html('wiki.aide.rubriques_machine', { rubriques });
    if (type === 'composant') return I18n.html('wiki.aide.rubriques_article', { rubriques });
    if (type === 'savoir-faire') return I18n.html('wiki.aide.rubriques_savoir_faire', { rubriques });
    return I18n.html('wiki.aide.rubriques_page', { rubriques });
  }

  function aideHtml(type) {
    const limites = limitesEnClair(type);
    return UI.html`<h2 id="wj-titre-aide">${I18n.t('wiki.aide.comment_ecrire')}</h2>
      <ul class="wj-aide-liste">
        <li>${aideRubriques(type)}</li>
        ${role(type) ? UI.html`<li class="wj-aide-roles">${role(type)}</li>` : ''}
        ${limites ? UI.html`<li class="wj-aide-limites">${limites}</li>` : ''}
        <li>${I18n.html('wiki.aide.phrase_ot_aaaa_nnnn')}</li>
        <li>${I18n.html('wiki.aide.lien_titre_page')}</li>
        <li>${I18n.t('wiki.aide.aucun_comptage_ni_aucune')}</li>
        <li class="wj-aide-securite">${I18n.html('wiki.aide.aucune_consigne_securite_saisit')}</li>
      </ul>
      <p class="aide">${I18n.t('wiki.aide.memes_controles_ia_sauf')}</p>`;
  }

  /** Rattachements d'un savoir-faire : une machine, un article, ou un savoir-faire (il en est alors une sous-page). */
  function optionsRattachement(choisi) {
    const option = (id, titre) => UI.html`<option value="${id}"${id === choisi ? UI.brut(' selected') : ''}>${titre}</option>`;
    const savoirs = Donnees.lignes('wiki_pages').filter((l) => estActive(l) && texte(l.type) === TYPE_NOUVELLE && !Wiki.typeRetire(l)
      && !(texte(l.rattache_a) && texte((Donnees.trouver('wiki_pages', texte(l.rattache_a)) || {}).type) === TYPE_NOUVELLE));
    return UI.html`<option value="">${I18n.t('wiki.options_rattachement.choisir')}</option>
      <optgroup label="${I18n.t('wiki.options_rattachement.machines')}">${Donnees.lignes('equipements').map((e) => option(texte(e.id), titreEquipement(e) || e.id))}</optgroup>
      <optgroup label="${I18n.t('wiki.options_rattachement.articles')}">${Donnees.lignes('articles').map((a) => option(texte(a.id), titreArticle(a)))}</optgroup>
      <optgroup label="${I18n.t('wiki.options_rattachement.savoir_faire_sous_page')}">${savoirs.map((l) => option(texte(l.id), texte(l.titre)))}</optgroup>`;
  }

  function champsNouvelle(rattache) {
    return UI.html`<div class="form-grille wj-nouvelle-champs">
      <div class="champ"><label class="libelle" for="wj-titre">${I18n.t('wiki.champs_nouvelle.titre_savoir_faire')} <span class="requis" aria-hidden="true">*</span></label>
        <input id="wj-titre" name="titre" maxlength="120" aria-required="true" aria-describedby="wj-titre-erreur" autocomplete="off">
        <p class="erreur-champ" id="wj-titre-erreur" role="alert" hidden></p></div>
      <div class="champ large wj-champ-rattache"><label class="libelle" for="wj-rattache">${I18n.t('wiki.champs_nouvelle.rattache')}</label>
        <select id="wj-rattache" name="rattache">${optionsRattachement(rattache)}</select>
        <p class="aide">${I18n.t('wiki.champs_nouvelle.aide_rattache')}</p></div>
    </div>`;
  }

  function archiverHtml(titre) {
    return UI.html`<section class="carte wj-archiver" aria-labelledby="wj-titre-archiver">
      <h2 id="wj-titre-archiver">${I18n.t('wiki.archiver.archiver_page')}</h2>
      <p class="aide">${I18n.t('wiki.archiver.page_sort_wiki_texte')}</p>
      <div class="actions"><button type="button" class="btn btn-danger wj-archiver-demande">${I18n.t('wiki.archiver.archiver')}</button></div>
      <div class="wj-confirmation" role="alert" hidden>
        <p>${I18n.html('wiki.archiver.archiver_page_apparaitra_plus', { titre })}</p>
        <div class="actions"><button type="button" class="btn btn-danger wj-archiver-confirmer">${I18n.t('wiki.archiver.confirmer_archivage')}</button>
          <button type="button" class="btn btn-fantome wj-archiver-annuler">${I18n.t('commun.bouton.annuler')}</button></div>
      </div>
    </section>`;
  }

  /** Refus d'une écriture : les raisons une par ligne (contrôles), sinon le message ; rien n'a été écrit. */
  function montrerRefus(zone, erreur) {
    const raisons = erreur && Array.isArray(erreur.raisons) ? erreur.raisons : [];
    if (!(erreur instanceof Donnees.ErreurValidation)) App.signalerErreur(erreur, 'écriture dans le wiki');
    UI.remplir(zone, UI.bandeau('important', raisons.length
      ? UI.html`<p><b>${I18n.t('wiki.montrer_refus.texte_refuse_rien_ete')}</b></p><ul class="wj-raisons">${raisons.map((r) => UI.html`<li>${r}</li>`)}</ul>`
      : UI.html`<p>${I18n.html('wiki.montrer_refus.rien_ete_ecrit', { raisonErreur: App.raisonErreur(erreur) })}</p>`));
    zone.scrollIntoView({ block: 'nearest' });
  }

  function afficherIntrouvable(conteneur, id) {
    UI.remplir(conteneur, UI.html`<div class="wiki wj wj-ecrire">
      <div class="entete-page"><div><div class="fil"><a href="#/wiki">${I18n.t('wiki.introuvable.wiki')}</a></div><h1>${I18n.t('wiki.introuvable.page_introuvable')}</h1></div></div>
      ${UI.vide(I18n.t('wiki.introuvable.aucune_page_active_porte', { id }), I18n.t('wiki.introuvable.peut_etre_archivee_autre_poste'), 'wiki')}
      <p><a class="btn btn-secondaire" href="#/wiki">${I18n.t('wiki.introuvable.retour_wiki')}</a></p></div>`);
  }

  async function afficherEcriture(conteneur, parametres) {
    const id = texte(parametres && parametres.id);
    const requete = (parametres && parametres.requete) || new URLSearchParams();
    const nouvelle = id === 'nouvelle';
    const page = nouvelle ? null : Wiki.page(id);
    if (!nouvelle && !page) {
      App.definirTitre(I18n.t('wiki.introuvable.page_introuvable'));
      afficherIntrouvable(conteneur, id);
      return;
    }
    const ligne = page && page.pageId ? Donnees.trouver('wiki_pages', page.pageId) : null;
    const version = ligne ? Number(ligne.version) || 0 : 0;
    const type = nouvelle ? TYPE_NOUVELLE : page.type;
    const retire = ligne ? Wiki.typeRetire(ligne) : '';
    const retour = nouvelle ? '#/wiki' : '#/wiki/' + encodeURIComponent(id);
    const attente = page ? new Set((page.enAttente || []).map((e) => e.entreeId)).size : 0;
    App.definirTitre(nouvelle ? I18n.t('wiki.ecriture.nouveau_savoir_faire') : I18n.t('wiki.ecriture.modifier_page_titre', { pageTitre: page.titre }));
    UI.remplir(conteneur, UI.html`<div class="wiki wj wj-ecrire" data-page="${nouvelle ? '' : id}" data-version="${version}">
      <div class="entete-page"><div>
        <div class="fil"><a href="#/wiki">${I18n.t('wiki.introuvable.wiki')}</a>${page ? UI.html` <span aria-hidden="true">›</span> <a href="${retour}">${page.titre}</a>` : ''}</div>
        <h1>${nouvelle ? I18n.t('wiki.ecriture.nouveau_savoir_faire') : I18n.t('wiki.ecriture.modifier_page')}</h1>
        <p>${page ? page.titre + ' · ' + (libelleType(type) || type) + ' · version ' + version
          : I18n.t('wiki.ecriture.savoir_faire_ecrit_main')}</p>
      </div></div>
      <div class="wj-annonce" aria-live="polite"></div>
      ${retire ? UI.html`<div class="alerte attention wj-type-retire" role="status">${UI.icone('alerte')}<div class="alerte-texte"><p>${I18n.html('wiki.ecriture.page_avant_refonte_wiki', { retire })}</p></div></div>` : ''}
      ${attente ? UI.html`<div class="alerte attention" role="status">${UI.icone('alerte')}<div class="alerte-texte"><p>${I18n.t('wiki.ecriture.propositions_valider_portent_page', { n: attente })}</p></div></div>` : ''}
      <div class="wj-ecrire-grille">
        <form class="carte wj-formulaire" novalidate>
          ${nouvelle ? champsNouvelle(texte(requete.get('rattache'))) : ''}
          <div class="champ"><label class="libelle" for="wj-texte">${I18n.t('wiki.ecriture.texte_page')}</label>
            <textarea id="wj-texte" name="texte" rows="16" spellcheck="true" placeholder="${I18n.t('wiki.ecrire.exemple_texte', { rubrique: (Wiki.RUBRIQUES[type] || [])[0]
              || I18n.t('wiki.ecrire.exemple_rubrique') })}"></textarea></div>
          <div class="champ"><label class="libelle" for="wj-motif-ecriture">${I18n.t('wiki.ecriture.motif_facultatif')}</label>
            <input id="wj-motif-ecriture" name="motif" maxlength="300" autocomplete="off" placeholder="${I18n.t('wiki.ecriture.ex_remise_ordre_apres')}"></div>
          <div class="actions"><button type="submit" class="btn btn-primaire wj-enregistrer">${UI.icone('sauvegarde')}${I18n.t('commun.bouton.enregistrer')}</button>
            <a class="btn btn-fantome" href="${retour}">${I18n.t('commun.bouton.annuler')}</a></div>
        </form>
        <aside class="carte wj-aide-balisage" aria-labelledby="wj-titre-aide">${aideHtml(type)}</aside>
      </div>
      ${ligne ? archiverHtml(page.titre) : ''}
    </div>`);
    const racine = UI.$('.wj-ecrire', conteneur);
    const zone = UI.$('.wj-annonce', racine);
    const formulaire = UI.$('.wj-formulaire', racine);
    UI.$('#wj-texte', racine).value = page ? page.texte || '' : '';
    let enCours = false;
    formulaire.addEventListener('submit', async (evenement) => {
      evenement.preventDefault();
      if (enCours) return;
      const cible = nouvelle ? lireNouvelle(racine) : { pageId: id };
      if (!cible) return;
      enCours = true;
      UI.$('.wj-enregistrer', racine).disabled = true;
      try {
        const resultat = await Wiki.ecrire(cible, UI.$('#wj-texte', racine).value,
          { version: nouvelle ? undefined : version, motif: UI.$('#wj-motif-ecriture', racine).value });
        App.marquerSaisie(false);
        UI.toast(I18n.t('wiki.ecriture.page_wiki_enregistree'), 'succes');
        App.naviguer('#/wiki/' + encodeURIComponent(resultat.pageId));
      } catch (erreur) {
        montrerRefus(zone, erreur);
      } finally {
        enCours = false;
        UI.$('.wj-enregistrer', racine).disabled = false;
      }
    });
    if (ligne) brancherArchivage(racine, zone, id, version);
  }

  /** Cible d'un nouveau savoir-faire, ou null (titre manquant : message sous le champ). */
  function lireNouvelle(racine) {
    const champ = UI.$('#wj-titre', racine);
    const erreur = UI.$('#wj-titre-erreur', racine);
    const titre = texte(champ.value);
    erreur.hidden = Boolean(titre);
    if (!titre) {
      erreur.textContent = I18n.t('wiki.lire_nouvelle.titre_obligatoire');
      champ.setAttribute('aria-invalid', 'true');
      champ.focus();
      return null;
    }
    champ.removeAttribute('aria-invalid');
    return { nouvelle: { type: TYPE_NOUVELLE, titre, rattacheA: UI.$('#wj-rattache', racine).value } };
  }

  function brancherArchivage(racine, zone, id, version) {
    const bloc = UI.$('.wj-archiver', racine);
    const demande = UI.$('.wj-archiver-demande', bloc);
    const confirmation = UI.$('.wj-confirmation', bloc);
    const basculer = (ouvrir) => {
      confirmation.hidden = !ouvrir;
      demande.closest('.actions').hidden = ouvrir;
      (ouvrir ? UI.$('.wj-archiver-confirmer', bloc) : demande).focus();
    };
    demande.addEventListener('click', () => basculer(true));
    UI.$('.wj-archiver-annuler', bloc).addEventListener('click', () => basculer(false));
    UI.$('.wj-archiver-confirmer', bloc).addEventListener('click', async (evenement) => {
      const bouton = evenement.currentTarget;
      bouton.disabled = true;
      try {
        await Wiki.ecrire({ pageId: id }, null, { archiver: true, version });
        App.marquerSaisie(false);
        UI.toast(I18n.t('wiki.brancher_archivage.page_archivee_sort_wiki'), 'succes');
        App.naviguer('#/wiki');
      } catch (erreur) {
        bouton.disabled = false;
        montrerRefus(zone, erreur);
      }
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'wiki-ecrire',
      route: /^#\/wiki-ecrire\/(?<id>[^/?]+)$/,
      get titre() { return I18n.t('wiki.ecran.titre_ecrire'); },
      parent: 'wiki',
      profils: ['responsable'],
      tables: TABLES,
      afficher: afficherEcriture,
    });
  });

  return { controleDuWiki };
})());
