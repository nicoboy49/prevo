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
  const LIBELLES = { 'équipement': 'machine', composant: 'article', 'savoir-faire': 'savoir-faire' };
  const POUR = { 'équipement': 'le texte d\'une machine', composant: 'le texte d\'un article', 'savoir-faire': 'un savoir-faire' };
  // Ce qu'on écrit dans chaque texte rédigé (§20.12 ; mêmes mots que la consigne de l'IA).
  const ROLES = {
    'équipement': '« En bref » : ce qu\'il faut savoir d\'abord de cette machine, ses pannes et ce qui les a réglées (une '
      + 'synthèse, réécrite en entier à chaque intervention, pas un historique) ; « Astuces » : les astuces tirées des OT.',
    composant: '« À quoi il sert » : son rôle sur les machines où il sert, ses signes d\'usure.',
    'savoir-faire': 'Un geste ou une méthode, commun aux machines (titre sans repère), écrit d\'abord à partir des astuces '
      + 'des OT ; « Particularités par machine » : une phrase par machine, avec son lien, pour ce qui change pour elle.',
  };
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
    return mesure.phrases + ' phrases' + (limite.mots === null ? '' : ' et ' + mesure.mots + ' mots');
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
          noter('lien-casse', ligne, 'lien [[' + titre + ']] vers une page inconnue');
        }
      });
      texte(ligne.liens).split(';').map(texte).filter(Boolean).forEach((id) => {
        relier(id, ligne.id);
        const table = id.startsWith('EQ-') ? 'equipements' : (id.startsWith('ART-') ? 'articles' : 'wiki_pages');
        const cible = id.startsWith('PANNE-') ? idsPannes.has(id) : Donnees.trouver(table, id);
        if (!cible) noter('lien-casse', ligne, 'lien vers ' + id + ', page inexistante');
        else if (table === 'wiki_pages' && !estActive(cible)) noter('lien-casse', ligne, 'lien vers « ' + texte(cible.titre) + ' » (' + id + '), page archivée');
      });
    });
    // Seul un savoir-faire peut être orphelin : une machine ou un article a toujours sa page (§20.12).
    const libre = (l) => texte(l.type) === 'savoir-faire' && !texte(l.rattache_a) && !texte(l.equipement_id) && !texte(l.article_id);
    const liee = (l) => [l.id, repereDe(l).id, 'TITRE:' + Wiki.comparable(l.titre)]
      .some((cible) => Array.from(sources.get(cible) || []).some((source) => source !== l.id));
    actives.filter((l) => libre(l) && !liee(l)).forEach((l) => noter('orpheline', l, 'aucune page ne renvoie ici et elle n\'est rattachée à rien'));
    actives.filter((l) => !Wiki.citationsDe(l.texte).length)
      .forEach((l) => noter('sans-ot', l, texte(l.texte) ? 'son texte ne cite aucun OT' : 'page vide : aucun OT cité'));
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
      distincts.filter((l) => !l.calcule).forEach((l) => noter('titre-proche', l, 'titre trop proche de '
        + distincts.filter((m) => m !== l).map((m) => '« ' + titreDe(m) + ' »').join(', ')));
    });
    actives.forEach((l) => {
      const retire = Wiki.typeRetire(l);
      if (retire) { noter('type-retire', l, 'type de page retiré (' + retire + ') : archivez-la'); return; }
      const type = texte(l.type);
      const limites = Wiki.LIMITES[type];
      const mesures = Object.entries(Wiki.mesurerRubriques(l.texte));
      Object.keys(limites.rubriques).forEach((rubrique) => {
        const trouvee = mesures.find(([nom]) => Wiki.comparable(nom) === Wiki.comparable(rubrique));
        const mesure = trouvee ? trouvee[1] : { phrases: 0, mots: 0 };
        const limite = limites.rubriques[rubrique];
        if (mesure.phrases > limite.phrases || (limite.mots !== null && mesure.mots > limite.mots)) {
          noter('trop-longue', l, '« ' + rubrique + ' » : ' + longueur(mesure, limite) + ' (au plus ' + longueur(limite, limite) + ')');
        }
      });
      const page = Wiki.mesurerTexte(l.texte);
      if (limites.page && (page.phrases > limites.page.phrases || page.mots > limites.page.mots)) {
        noter('trop-longue', l, longueur(page, limites.page) + ' (au plus ' + longueur(limites.page, limites.page) + ')');
      }
      const permises = Wiki.RUBRIQUES[type].map(Wiki.comparable);
      const anciennes = mesures.map(([nom]) => nom).filter((nom) => !permises.includes(Wiki.comparable(nom)));
      if (anciennes.length) {
        noter('anciennes-rubriques', l, anciennes.map((nom) => '« ' + nom + ' »').join(', ') + ' : à réécrire dans ses rubriques ('
          + Wiki.RUBRIQUES[type].map((nom) => '« ' + nom + ' »').join(', ') + ')');
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
          message: 'ouverte depuis le ' + UI.dateFr(depuis) + ' (' + [texte(entree.ot_id), entree.id].filter(Boolean).join(', ') + ')' });
      });
    });
    actives.forEach((l) => [['equipement_id', 'equipements', 'équipement'], ['article_id', 'articles', 'article']].forEach(([champ, table, nom]) => {
      const id = texte(l[champ]);
      const cible = id ? Donnees.trouver(table, id) : null;
      if (id && !cible) noter('ancrage-disparu', l, nom + ' ' + id + ' absent');
      else if (cible && texte(cible.actif) === '0') noter('ancrage-disparu', l, nom + ' ' + id + ' inactif');
      else if (cible && table === 'equipements' && texte(cible.statut) === 'rebut') noter('ancrage-disparu', l, nom + ' ' + id + ' au rebut');
    }));
    // Rattachement (§20.4) : la mère d'une sous-page (même type ; tout rattachement d'une page qui n'est pas un
    // savoir-faire), ou la page d'un savoir-faire, absente ou archivée.
    actives.filter((l) => texte(l.rattache_a)).forEach((l) => {
      const id = texte(l.rattache_a);
      const cible = lignes.find((autre) => autre.id === id);
      const nom = (cible ? texte(cible.type) === texte(l.type) : texte(l.type) !== 'savoir-faire') ? 'page mère' : 'page de rattachement';
      if (!cible) noter('ancrage-disparu', l, nom + ' ' + id + ' absente');
      else if (!estActive(cible)) noter('ancrage-disparu', l, nom + ' « ' + texte(cible.titre) + ' » (' + id + ') archivée');
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
      return 'Longueur : ' + longueur(limites.page, limites.page) + ' au plus, noms des rubriques compris (citations non '
        + 'comptées, un lien compte les mots de son titre) ; au-delà, découpez-le en sous-pages « <titre> — <sujet> ».';
    }
    return 'Longueurs : ' + Object.keys(limites.rubriques).map((rubrique) => '« ' + rubrique + ' » '
      + longueur(limites.rubriques[rubrique], limites.rubriques[rubrique]) + ' au plus').join(', ')
      + ' (citations non comptées, un lien compte les mots de son titre).';
  }

  function aideHtml(type) {
    const limites = limitesEnClair(type);
    return UI.html`<h2 id="wj-titre-aide">Comment écrire</h2>
      <ul class="wj-aide-liste">
        <li><code>## Rubrique</code> commence une rubrique. Pour ${POUR[type] || 'cette page'} :
          <span class="wj-rubriques">${(Wiki.RUBRIQUES[type] || []).map((r, n) => UI.html`${n ? ', ' : ''}<span class="wj-rubrique-nom">« ${r} »</span>`)}</span>, dans cet ordre.</li>
        ${ROLES[type] ? UI.html`<li class="wj-aide-roles">${ROLES[type]}</li>` : ''}
        ${limites ? UI.html`<li class="wj-aide-limites">${limites}</li>` : ''}
        <li><code>- phrase [OT-AAAA-NNNN]</code> : une phrase par ligne, qui cite au moins un OT clôturé administrativement.</li>
        <li><code>[[Titre d'une page]]</code> dans une phrase : lien vers une autre page du wiki (machine, article, panne,
          savoir-faire).</li>
        <li>Aucun comptage ni aucune date : les nombres de cas viennent de Prévo ; un nombre écrit doit figurer dans un OT cité.</li>
        <li class="wj-aide-securite"><b>Aucune consigne de sécurité</b> : elle se saisit dans la consignation de l'équipement.</li>
      </ul>
      <p class="aide">Mêmes contrôles que pour l'IA, sauf que vous pouvez retirer une phrase ou un OT cité. Chaque écriture entre au journal du wiki.</p>`;
  }

  /** Rattachements d'un savoir-faire : une machine, un article, ou un savoir-faire (il en est alors une sous-page). */
  function optionsRattachement(choisi) {
    const option = (id, titre) => UI.html`<option value="${id}"${id === choisi ? UI.brut(' selected') : ''}>${titre}</option>`;
    const savoirs = Donnees.lignes('wiki_pages').filter((l) => estActive(l) && texte(l.type) === TYPE_NOUVELLE && !Wiki.typeRetire(l)
      && !(texte(l.rattache_a) && texte((Donnees.trouver('wiki_pages', texte(l.rattache_a)) || {}).type) === TYPE_NOUVELLE));
    return UI.html`<option value="">Choisir…</option>
      <optgroup label="Machines">${Donnees.lignes('equipements').map((e) => option(texte(e.id), titreEquipement(e) || e.id))}</optgroup>
      <optgroup label="Articles">${Donnees.lignes('articles').map((a) => option(texte(a.id), titreArticle(a)))}</optgroup>
      <optgroup label="Savoir-faire (pour une sous-page)">${savoirs.map((l) => option(texte(l.id), texte(l.titre)))}</optgroup>`;
  }

  function champsNouvelle(rattache) {
    return UI.html`<div class="form-grille wj-nouvelle-champs">
      <div class="champ"><label class="libelle" for="wj-titre">Titre du savoir-faire <span class="requis" aria-hidden="true">*</span></label>
        <input id="wj-titre" name="titre" maxlength="120" aria-required="true" aria-describedby="wj-titre-erreur" autocomplete="off">
        <p class="erreur-champ" id="wj-titre-erreur" role="alert" hidden></p></div>
      <div class="champ large wj-champ-rattache"><label class="libelle" for="wj-rattache">Rattaché à</label>
        <select id="wj-rattache" name="rattache">${optionsRattachement(rattache)}</select>
        <p class="aide">Une machine ou un article : sa page reprend la consignation de la machine. Un savoir-faire : c'en est une
          sous-page, dont le titre commence par « ${'<titre du savoir-faire>'} — ».</p></div>
    </div>`;
  }

  function archiverHtml(titre) {
    return UI.html`<section class="carte wj-archiver" aria-labelledby="wj-titre-archiver">
      <h2 id="wj-titre-archiver">Archiver la page</h2>
      <p class="aide">La page sort du wiki ; son texte reste au journal. Rien n'est effacé.</p>
      <div class="actions"><button type="button" class="btn btn-danger wj-archiver-demande">Archiver</button></div>
      <div class="wj-confirmation" role="alert" hidden>
        <p><b>Archiver la page « ${titre} » ?</b> Elle n'apparaîtra plus dans le wiki ni dans la recherche.</p>
        <div class="actions"><button type="button" class="btn btn-danger wj-archiver-confirmer">Confirmer l'archivage</button>
          <button type="button" class="btn btn-fantome wj-archiver-annuler">Annuler</button></div>
      </div>
    </section>`;
  }

  /** Refus d'une écriture : les raisons une par ligne (contrôles), sinon le message ; rien n'a été écrit. */
  function montrerRefus(zone, erreur) {
    const raisons = erreur && Array.isArray(erreur.raisons) ? erreur.raisons : [];
    if (!(erreur instanceof Donnees.ErreurValidation)) App.signalerErreur(erreur, 'écriture dans le wiki');
    UI.remplir(zone, UI.bandeau('important', raisons.length
      ? UI.html`<p><b>Texte refusé, rien n'a été écrit :</b></p><ul class="wj-raisons">${raisons.map((r) => UI.html`<li>${r}</li>`)}</ul>`
      : UI.html`<p><b>Rien n'a été écrit :</b> ${App.raisonErreur(erreur)}</p>`));
    zone.scrollIntoView({ block: 'nearest' });
  }

  function afficherIntrouvable(conteneur, id) {
    UI.remplir(conteneur, UI.html`<div class="wiki wj wj-ecrire">
      <div class="entete-page"><div><div class="fil"><a href="#/wiki">Wiki</a></div><h1>Page introuvable</h1></div></div>
      ${UI.vide('Aucune page active ne porte l\'identifiant « ' + id + ' »', 'Elle a peut-être été archivée sur un autre poste.', 'wiki')}
      <p><a class="btn btn-secondaire" href="#/wiki">Retour au wiki</a></p></div>`);
  }

  async function afficherEcriture(conteneur, parametres) {
    const id = texte(parametres && parametres.id);
    const requete = (parametres && parametres.requete) || new URLSearchParams();
    const nouvelle = id === 'nouvelle';
    const page = nouvelle ? null : Wiki.page(id);
    if (!nouvelle && !page) {
      App.definirTitre('Page introuvable');
      afficherIntrouvable(conteneur, id);
      return;
    }
    const ligne = page && page.pageId ? Donnees.trouver('wiki_pages', page.pageId) : null;
    const version = ligne ? Number(ligne.version) || 0 : 0;
    const type = nouvelle ? TYPE_NOUVELLE : page.type;
    const retire = ligne ? Wiki.typeRetire(ligne) : '';
    const retour = nouvelle ? '#/wiki' : '#/wiki/' + encodeURIComponent(id);
    const attente = page ? new Set((page.enAttente || []).map((e) => e.entreeId)).size : 0;
    App.definirTitre(nouvelle ? 'Nouveau savoir-faire' : 'Modifier ' + page.titre);
    UI.remplir(conteneur, UI.html`<div class="wiki wj wj-ecrire" data-page="${nouvelle ? '' : id}" data-version="${version}">
      <div class="entete-page"><div>
        <div class="fil"><a href="#/wiki">Wiki</a>${page ? UI.html` <span aria-hidden="true">›</span> <a href="${retour}">${page.titre}</a>` : ''}</div>
        <h1>${nouvelle ? 'Nouveau savoir-faire' : 'Modifier la page'}</h1>
        <p>${page ? page.titre + ' · ' + (LIBELLES[type] || type) + ' · version ' + version
          : 'Un savoir-faire écrit à la main : un geste ou une méthode, rattaché à une machine, à un article ou à un savoir-faire.'}</p>
      </div></div>
      <div class="wj-annonce" aria-live="polite"></div>
      ${retire ? UI.html`<div class="alerte attention wj-type-retire" role="status">${UI.icone('alerte')}<div class="alerte-texte"><p><b>Page
        d'avant la refonte du wiki (${retire}) : type de page retiré : archivez-la.</b> Son texte reste au journal ; ce qu'il
        dit va dans les textes de la machine, de l'article ou d'un savoir-faire.</p></div></div>` : ''}
      ${attente ? UI.html`<div class="alerte attention" role="status">${UI.icone('alerte')}<div class="alerte-texte"><p>${attente > 1
        ? attente + ' propositions à valider portent sur cette page : enregistrer les fera passer « à refaire » (leurs OT reviennent dans la file).'
        : 'Une proposition à valider porte sur cette page : enregistrer la fera passer « à refaire » (son OT revient dans la file).'}</p></div></div>` : ''}
      <div class="wj-ecrire-grille">
        <form class="carte wj-formulaire" novalidate>
          ${nouvelle ? champsNouvelle(texte(requete.get('rattache'))) : ''}
          <div class="champ"><label class="libelle" for="wj-texte">Texte de la page</label>
            <textarea id="wj-texte" name="texte" rows="16" spellcheck="true" placeholder="${'## ' + ((Wiki.RUBRIQUES[type] || [])[0]
              || 'Rubrique') + String.fromCharCode(10) + '- Phrase qui cite son OT [OT-2026-0042]'}"></textarea></div>
          <div class="champ"><label class="libelle" for="wj-motif-ecriture">Motif (facultatif)</label>
            <input id="wj-motif-ecriture" name="motif" maxlength="300" autocomplete="off" placeholder="Ex. remise en ordre après relecture"></div>
          <div class="actions"><button type="submit" class="btn btn-primaire wj-enregistrer">${UI.icone('sauvegarde')}Enregistrer</button>
            <a class="btn btn-fantome" href="${retour}">Annuler</a></div>
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
        UI.toast('Page du wiki enregistrée.', 'succes');
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
      erreur.textContent = 'Le titre est obligatoire.';
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
        UI.toast('Page archivée : elle sort du wiki, son texte reste au journal.', 'succes');
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
      titre: 'Écrire dans le wiki',
      parent: 'wiki',
      profils: ['responsable'],
      tables: TABLES,
      afficher: afficherEcriture,
    });
  });

  return { controleDuWiki };
})());
