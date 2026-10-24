'use strict';
// Wiki (7 ter/9) — les sections calculées de la page d'une entité (refonte 2, ARCHITECTURE.md §20.12 ; D113, D114 ;
// tâche T137 ; D118, T143) : Wiki.sectionsEntite(entite, contexte) rend les morceaux de la colonne de lecture, dans
// l'ordre de la page de chaque type (maquette validée), que wiki-page-ecrans.js (chargé juste avant) pose ; un morceau
// { textes, reste, toujours, titreVide } y marque la place d'un groupe de textes rédigés, posé là-bas avec ses petits
// numéros. Chaque type rend ses morceaux un à un (fonction génératrice) : une section n'est créée qu'à son tour, après
// les textes d'avant, pour que ses petits numéros suivent l'ordre de la page (registre contexte.refs, wiki-page-ecrans.js).
//   machine       « En bref », pannes fréquentes, interventions, recherche dans son historique (§20.9), articles
//                 (montés, consommés avec leurs OT en petits numéros), savoir-faire, « Astuces » (et les rubriques
//                 d'avant la refonte), préventif et contrôles ;
//   panne         machines touchées, causes, remèdes, articles changés (leurs OT en petits numéros), interventions
//                 (aucun texte) ;
//   article       « À quoi il sert », stock dans le temps (commandes, sorties, ruptures), où il est monté, consommé
//                 sur, interventions où il a servi, savoir-faire ;
//   technicien    habilitations, interventions (aucun texte ; le taux horaire est dans la fiche, au responsable) ;
//   intervention  demande d'origine, travail demandé, compte rendu, astuce, motifs d'attente et d'annulation, pièces
//                 sorties, opérations, temps passés, « Cité dans le wiki » — en lecture seule (la fiche OT pour modifier) ;
//   savoir-faire  ses rubriques, ses sous-pages ;
//   et, en dernier pour une machine, un article, une panne ou un savoir-faire (les pages qu'un lien [[…]] peut viser),
//   « Pages qui renvoient ici » (CS103, §20.9 : Wiki.entite().retours), section discrète absente quand rien n'y renvoie.
// Données : Wiki.entite (visibilité déjà appliquée : un lien null est un nom sans lien) ; outils d'affichage de
// wiki-entites-ecrans.js (Wiki.outilsEcrans, lus à l'appel). Toute donnée passe par UI.html (échappée).
//
// Précisions au contrat (§20.12) :
//  - longues listes (D101 : 500 machines et 5 000 OT au jeu de charge) : seuls les premiers éléments sont créés —
//    INTERVENTIONS_MONTREES interventions, EVENEMENTS_MONTRES lignes du stock, LIGNES_MONTREES pour les autres listes — ;
//    « Voir les n autres » crée le reste au clic ;
//  - interventions : dans l'ordre de Wiki.entite (Wiki.ordreInterventions : les ouvertes en tête), statut sur chaque
//    ligne (sous le titre) ; tableau sur PC, cartes au téléphone ; le numéro (la carte au téléphone) mène à la page de
//    l'intervention, en texte pour le demandeur ; sans panne, la colonne Panne donne le type de l'OT ;
//  - stock dans le temps : commandes, sorties et retours imputés à un OT (stock restant), ruptures (début, fin), du plus
//    récent au plus ancien (à date égale : commandes, mouvements, ruptures) ; le prix d'une commande seulement s'il est
//    rendu (technicien, responsable : D114) ;
//  - articles consommés (machine) et changés (panne), D118 : après le nombre d'interventions, les OT de l'article en
//    petits numéros — les OT_MONTRES plus récents, puis « … et n autres » —, la quantité à droite ; les lignes de toute
//    la liste sont faites d'un coup, dans son ordre (même celles créées au clic) : leurs numéros sont à leur place ;
//  - « Écrire un savoir-faire » (responsable) : #/wiki-ecrire/nouvelle?rattache=<machine ou article> ;
//  - une liste vide garde sa section, avec une phrase qui le dit ; préventif et contrôles, astuce, motifs, opérations,
//    temps passés et sous-pages n'apparaissent que s'ils ont un contenu.

Object.assign(Wiki, (() => {

  const INTERVENTIONS_MONTREES = 10;
  const EVENEMENTS_MONTRES = 14;
  const LIGNES_MONTREES = 20;
  const OT_MONTRES = 10;                                        // OT d'un article consommé ou changé, en petits numéros
  const TONS_HABILITATION = { 'pas encore valable': 'info' };     // les autres états ont leur ton dans UI.badgeStatut

  const texte = (valeur) => (valeur === null || valeur === undefined ? '' : String(valeur).trim());
  const o = () => Wiki.outilsEcrans;
  const faitDe = (entite, libelle) => (entite.faits.find((fait) => fait.libelle === libelle) || {}).valeur;
  const vide = (message) => UI.html`<p class="wiki-vide">${message}</p>`;
  const nom = (valeur) => UI.html`<span class="wiki-nom-entite">${valeur}</span>`;

  /** Une section de la colonne de lecture : titre (et son compte), aide, contenu. */
  function section(id, titre, compte, contenu, aide) {
    return UI.html`<section class="wiki-section" id="${id}" aria-labelledby="${id}-titre">
      <h2 id="${id}-titre">${titre}${compte === null || compte === undefined ? '' : UI.html` <span class="wiki-compte">${compte}</span>`}</h2>
      ${aide ? UI.html`<p class="aide">${aide}</p>` : ''}${contenu}</section>`;
  }

  /** Une ligne d'entité (`element` : { id, type (pastille), nom, sous, droite }), comme les listes du wiki. */
  const ligne = (element) => UI.html`<li class="wiki-ligne" data-id="${element.id}">
      ${element.type ? o().pastille(element.type) : ''}<span class="wiki-ligne-corps">${element.nom}${element.sous
        ? UI.html`<span class="wiki-ligne-sous">${element.sous}</span>` : ''}</span>${element.droite
        ? UI.html`<span class="wiki-ligne-droite">${element.droite}</span>` : ''}</li>`;
  const liste = (elements) => UI.html`<ul class="wiki-lignes-entites wiki-lignes-page">${elements.map(ligne)}</ul>`;

  /** Une barre (`element` : { id, nom, detail, cas }) ; `plus` : le plus de cas de sa liste (la barre pleine). */
  const barre = (plus) => (element) => UI.html`<li data-id="${element.id}">
      <span class="wiki-barre-nom">${element.nom}${element.detail ? UI.html` <span class="wiki-barre-detail">${element.detail}</span>` : ''}</span>
      <span class="wiki-jauge" aria-hidden="true"><i style="width: ${Math.max(4, Math.round(100 * element.cas / plus))}%"></i></span>
      <span class="wiki-barre-cas">${o().pluriel(element.cas, 'cas', 'cas')}</span></li>`;
  const plusDeCas = (elements) => Math.max(1, ...elements.map((element) => element.cas));

  /**
   * Liste longue (D101) : ses `montres` premiers éléments, le reste créé au clic sur « Voir les n autres <nom> » →
   * { fragment, suite } ; `suite` est branchée par creerSection. reglages : { rendre (fragment d'un élément ; une ligne
   * par défaut), cadre (fragment de la liste avec les premiers), selecteur (la liste où ajouter), nom, montres, vide }.
   */
  function sousListe(elements, reglages) {
    const r = Object.assign({ rendre: ligne, nom: 'lignes', montres: LIGNES_MONTREES, selecteur: 'ul',
      cadre: (premiers) => UI.html`<ul class="wiki-lignes-entites wiki-lignes-page">${premiers}</ul>` }, reglages);
    if (!elements.length) return { fragment: vide(r.vide || 'Rien pour l\'instant.'), suite: null };
    const id = UI.identifiantUnique('wiki-suite');
    const reste = elements.slice(r.montres);
    return { fragment: UI.html`<div class="wiki-sous-liste" data-suite="${id}">${r.cadre(elements.slice(0, r.montres).map(r.rendre))}${o()
      .boutonAutres(reste.length, r.nom)}</div>`, suite: reste.length ? { id, reste, rendre: r.rendre, selecteur: r.selecteur } : null };
  }

  /** Section (élément), ses listes longues branchées : chacune crée son reste au clic. */
  function creerSection(id, titre, compte, contenu, aide, suites) {
    const element = UI.element(section(id, titre, compte, contenu, aide));
    (suites || []).filter(Boolean).forEach((suite) => {
      const bloc = UI.$('[data-suite="' + suite.id + '"]', element);
      o().brancherSuite(bloc, () => o().ajouterA(UI.$(suite.selecteur, bloc), suite.reste.map(suite.rendre)));
    });
    return element;
  }

  /** Section d'une seule liste longue de lignes (`elements` : voir `ligne`). */
  function sectionListe(id, titre, compte, elements, reglages) {
    const r = reglages || {};
    const longue = sousListe(elements, r);
    return creerSection(id, titre, compte, longue.fragment, r.aide, [longue.suite]);
  }

  // ===========================================================================================
  // 1. Interventions (toutes les pages sauf l'intervention et le savoir-faire)
  // ===========================================================================================

  function carteIntervention(ot) {
    const contenu = UI.html`<div class="carte-tete"><b>${ot.id}</b>${UI.badgeStatut(ot.statut)}</div>
      <div class="carte-titre">${ot.titre}</div>
      <div class="carte-meta"><span>${UI.dateFr(ot.date)}</span>${ot.machine ? UI.html`<span>${o().repere(ot.machine)}</span>` : ''}${ot.panne
        ? UI.html`<span>${ot.panne.libelle}</span>` : ''}${ot.techniciens.length ? UI.html`<span>${ot.techniciens.map((t) => t.nom).join(', ')}</span>` : ''}</div>`;
    return UI.html`<li class="wiki-intervention wiki-carte-intervention" data-id="${ot.id}">${ot.lien
      ? UI.html`<a href="${o().adresse(ot.lien)}">${contenu}</a>` : UI.html`<div class="carte-ligne">${contenu}</div>`}</li>`;
  }

  function ligneIntervention(ot, sansMachine) {
    const lien = o();
    return UI.html`<tr class="wiki-intervention" data-id="${ot.id}">
      <td class="sans-coupure">${UI.dateFr(ot.date)}</td><td class="sans-coupure">${lien.lienEntite(ot.lien, ot.id)}</td>
      <td class="wiki-cellule-titre">${ot.titre}<br>${UI.badgeStatut(ot.statut)}</td>
      <td>${ot.panne ? lien.lienEntite(ot.panne.lien, ot.panne.libelle) : UI.html`<span class="wiki-discret">${ot.type}</span>`}</td>
      ${sansMachine ? '' : UI.html`<td>${lien.lienMachine(ot.machine)}</td>`}
      <td>${lien.joindre(ot.techniciens.map((t) => lien.lienEntite(t.lien, t.nom)), ', ')}</td></tr>`;
  }

  function blocInterventions(id, titre, interventions, contexte, options) {
    const reglages = options || {};
    const telephone = contexte.telephone;
    const longue = sousListe(interventions, { montres: INTERVENTIONS_MONTREES, nom: 'interventions', vide: reglages.vide || 'Aucune intervention.',
      rendre: telephone ? carteIntervention : (ot) => ligneIntervention(ot, reglages.sansMachine),
      selecteur: telephone ? 'ul' : 'tbody',
      cadre: (premiers) => (telephone ? UI.html`<ul class="liste-cartes wiki-cartes-interventions">${premiers}</ul>`
        : UI.html`<div class="table-defile"><table class="table wiki-table-interventions">
          <caption class="visuellement-cache">${titre}</caption>
          <thead><tr><th scope="col">Date</th><th scope="col">N°</th><th scope="col">Intervention et statut</th><th scope="col">Panne</th>
            ${reglages.sansMachine ? '' : UI.html`<th scope="col">Machine</th>`}<th scope="col">Technicien</th></tr></thead>
          <tbody>${premiers}</tbody></table></div>`) });
    return creerSection(id, titre, interventions.length, longue.fragment, reglages.aide, [longue.suite]);
  }

  function blocSavoirFaire(entite, contexte, vide_) {
    const savoirs = entite.sections.savoirFaire;
    return section('wiki-savoir-faire', 'Savoir-faire', savoirs.length, UI.html`${savoirs.length
      ? liste(savoirs.map((savoir) => ({ id: savoir.id, type: 'savoir-faire', nom: o().lienEntite(savoir.lien, savoir.titre) })))
      : vide(vide_)}${contexte.responsable ? UI.html`<p class="wiki-ecrire-lien"><a class="btn btn-fantome" id="wiki-ecrire-savoir-faire"
        href="#/wiki-ecrire/nouvelle?rattache=${encodeURIComponent(entite.id)}">${UI.icone('ajouter')}Écrire un savoir-faire</a></p>` : ''}`);
  }

  /** « Pages qui renvoient ici » (CS103) : les pages du wiki dont un texte fait un lien vers celle-ci ; null sans retour. */
  function blocRetours(entite) {
    const retours = entite.retours || [];
    return retours.length ? sectionListe('wiki-retours', 'Pages qui renvoient ici', retours.length, retours.map((retour) => ({
      id: retour.id, type: retour.type, nom: o().lienEntite(retour.lien, retour.titre) })),
    { nom: 'pages', aide: 'Les pages du wiki dont un texte fait un lien vers celle-ci.' }) : null;
  }

  const calcule = (phrase) => UI.html`<p class="wiki-calcule">${UI.icone('indicateurs')}<span>${phrase}</span></p>`;

  /**
   * Lignes (voir `ligne`) des articles consommés ou changés (D118) : nom, nombre d'interventions (`noms` : singulier,
   * pluriel) suivi des OT_MONTRES plus récents de `article.ot` (ordre des interventions : les plus récents d'abord) en
   * petits numéros, puis « … et n autres » ; quantité à droite. Les fragments de toute la liste sont faits ici, dans son
   * ordre, même pour les lignes créées au clic : chaque OT prend son numéro à sa place (précisions en tête).
   */
  function lignesArticles(articles, contexte, noms) {
    return articles.map((article) => {
      const numeros = article.ot.slice(0, OT_MONTRES).map((ot) => contexte.refs.fragment(ot));
      const autres = article.ot.length - OT_MONTRES;
      return { id: article.articleId, type: 'article', nom: o().lienEntite(article.lien, article.titre),
        sous: UI.html`${o().pluriel(article.ot.length, noms[0], noms[1])}${numeros}${autres > 0
          ? UI.html` <span class="wiki-ref-autres">… et ${autres} ${autres > 1 ? 'autres' : 'autre'}</span>` : ''}`,
        droite: 'quantité ' + UI.nombreFr(article.quantite) };
    });
  }

  // ===========================================================================================
  // 2. Machine
  // ===========================================================================================

  function blocArticles(sections, contexte) {
    const montes = sousListe(sections.articlesMontes.map((article) => ({ id: article.articleId, type: 'article',
      nom: o().lienEntite(article.lien, article.titre), droite: article.quantite === null ? '' : '× ' + UI.nombreFr(article.quantite) })),
    { nom: 'articles', vide: 'Aucun article dans la nomenclature de cette machine.' });
    const consommes = sousListe(lignesArticles(sections.articlesConsommes, contexte, ['intervention clôturée', 'interventions clôturées']),
      { nom: 'articles', vide: 'Aucune pièce sortie pour une intervention clôturée.' });
    return creerSection('wiki-articles', 'Articles', null, UI.html`
      <h3 class="wiki-sous-section">Montés <span class="wiki-compte">${sections.articlesMontes.length}</span></h3>${montes.fragment}
      <h3 class="wiki-sous-section">Consommés <span class="wiki-compte">${sections.articlesConsommes.length}</span></h3>${consommes.fragment}`,
    'Montés : la nomenclature de la machine. Consommés : sortis du magasin pour ses interventions clôturées, retours déduits.',
    [montes.suite, consommes.suite]);
  }

  function blocPreventif(sections) {
    if (!sections.gammes.length && !sections.controles.length) return null;
    const gammes = sections.gammes.map((gamme) => ({ id: gamme.id, nom: nom(gamme.libelle),
      sous: gamme.periodiciteJours ? 'tous les ' + UI.nombreFr(gamme.periodiciteJours) + ' jours' : 'selon ' + (gamme.declencheur || 'son déclencheur'),
      droite: gamme.prochaine ? 'prochaine le ' + UI.dateFr(gamme.prochaine) : 'sans échéance' }));
    const controles = sections.controles.map((controle) => ({ id: controle.id, nom: nom(controle.nature),
      sous: o().joindre([controle.organisme, controle.derniere ? 'dernier le ' + UI.dateFr(controle.derniere) : ''], ' · '),
      droite: controle.prochaine ? 'prochain le ' + UI.dateFr(controle.prochaine) : 'sans échéance' }));
    return sectionListe('wiki-preventif', 'Préventif et contrôles', gammes.length + controles.length, gammes.concat(controles),
      { aide: 'Gammes actives et contrôles réglementaires, la prochaine échéance d\'abord.' });
  }

  function* machine(entite, contexte) {
    const sections = entite.sections;
    const total = sections.pannes.reduce((somme, panne) => somme + panne.cas, 0);
    yield { textes: ['En bref'], toujours: true };
    yield sectionBarres('wiki-pannes', 'Pannes fréquentes', total ? o().pluriel(total, 'cas', 'cas') : null,
      sections.pannes.map((panne) => ({ id: panne.lien, nom: o().lienEntite(panne.lien, panne.libelle),
        detail: panne.derniere ? '· dernière le ' + UI.dateFr(panne.derniere) : '', cas: panne.cas })),
      { aide: 'Interventions correctives clôturées, par code symptôme.', nom: 'pannes',
        vide: 'Aucune panne : elles naissent des interventions correctives clôturées.' });
    yield blocInterventions('wiki-interventions', 'Interventions', sections.interventions, contexte, { sansMachine: true,
      vide: 'Aucune intervention sur cette machine.' });
    yield Wiki.champRecherche({ equipementId: entite.id, titre: 'Chercher dans l\'historique de cette machine' });
    yield blocArticles(sections, contexte);
    yield blocSavoirFaire(entite, contexte, 'Pas encore de savoir-faire pour cette machine.');
    yield { textes: ['Astuces'], reste: true };
    yield blocPreventif(sections);
    yield blocRetours(entite);
  }

  // ===========================================================================================
  // 3. Panne
  // ===========================================================================================

  /** Section de barres (liste longue : les LIGNES_MONTREES premières barres, les autres au clic). */
  function sectionBarres(id, titre, compte, elements, reglages) {
    const r = reglages || {};
    const longue = sousListe(elements, { rendre: barre(plusDeCas(elements)), nom: r.nom || 'lignes', vide: r.vide,
      cadre: (premiers) => UI.html`<ul class="wiki-barres wiki-barres-page">${premiers}</ul>` });
    return creerSection(id, titre, compte, UI.html`${longue.fragment}${elements.length && r.apres ? r.apres : ''}`, r.aide, [longue.suite]);
  }

  function* panne(entite, contexte) {
    const sections = entite.sections;
    const codes = (lignes) => lignes.map((ligne) => ({ id: ligne.code, nom: nom(ligne.libelle), cas: ligne.cas }));
    yield calcule('Calculé par Prévo à partir des interventions correctives clôturées de ce code symptôme, sans IA.');
    yield sectionBarres('wiki-panne-machines', 'Machines touchées', sections.machines.length, sections.machines.map((touchee) => ({
      id: touchee.equipementId, nom: o().lienEntite(touchee.lien, touchee.titre), cas: touchee.cas })),
    { nom: 'machines', vide: 'Aucune machine connue.' });
    yield sectionBarres('wiki-causes', 'Causes', sections.causes.length, codes(sections.causes), { nom: 'causes',
      vide: 'Aucune cause renseignée sur ces cas.', apres: UI.html`<p class="note wiki-mention">${Wiki.MENTION_STATISTIQUE}</p>` });
    yield sectionBarres('wiki-remedes', 'Remèdes', sections.remedes.length, codes(sections.remedes), { nom: 'remèdes',
      vide: 'Aucun remède renseigné sur ces cas.' });
    yield sectionListe('wiki-articles-changes', 'Articles changés', sections.articles.length,
      lignesArticles(sections.articles, contexte, ['intervention', 'interventions']),
      { nom: 'articles', vide: 'Aucune pièce sortie pour cette panne.' });
    yield blocInterventions('wiki-interventions', 'Interventions', sections.interventions, contexte,
      { aide: 'Toutes les interventions de ce code, les ouvertes en tête.' });
    yield blocRetours(entite);
  }

  // ===========================================================================================
  // 4. Article : stock dans le temps
  // ===========================================================================================

  function blocStock(sections, unite) {
    const quantite = (valeur) => UI.nombreFr(valeur) + (unite ? ' ' + unite : '');
    const evenements = [].concat(
      sections.commandes.map((commande) => ({ date: commande.date, type: 'commande', id: commande.id,
        texte: 'Commandé : ' + quantite(commande.quantite) + (commande.fournisseur ? ' chez ' + commande.fournisseur : '')
          + (Number.isFinite(commande.prixUnitaire) ? ' à ' + UI.euro(commande.prixUnitaire) + ' l\'unité' : ''),
        droite: commande.reception ? 'reçu le ' + UI.dateFr(commande.reception) : commande.statut })),
      sections.sorties.map((mouvement) => ({ date: mouvement.date, type: mouvement.type, id: mouvement.id,
        texte: [mouvement.type === 'retour' ? 'Rendu : ' + quantite(mouvement.quantite) + ' de ' : 'Sorti : ' + quantite(mouvement.quantite) + ' pour ',
          o().lienEntite(mouvement.lien, mouvement.ot), mouvement.machine ? [' sur ', o().lienMachine(mouvement.machine)] : ''],
        droite: 'reste ' + quantite(mouvement.stock) })),
      sections.ruptures.map((rupture) => ({ date: rupture.debut, type: 'rupture', id: 'rupture-' + rupture.debut,
        texte: UI.html`<span class="badge ko">En rupture</span>`, droite: rupture.fin ? 'jusqu\'au ' + UI.dateFr(rupture.fin) : 'toujours' })),
    ).sort((a, b) => (a.date < b.date ? 1 : (a.date > b.date ? -1 : 0)));
    const rendre = (evenement) => UI.html`<li class="wiki-evenement" data-type="${evenement.type}" data-id="${evenement.id}">
      <span class="wiki-evenement-date">${UI.dateFr(evenement.date)}</span>
      <span class="wiki-evenement-texte">${evenement.texte}</span><span class="wiki-evenement-droite">${evenement.droite}</span></li>`;
    const longue = sousListe(evenements, { rendre, montres: EVENEMENTS_MONTRES, nom: 'lignes',
      vide: 'Aucune commande ni aucune sortie pour une intervention.', cadre: (premiers) => UI.html`<ul class="wiki-chronologie">${premiers}</ul>` });
    return creerSection('wiki-stock', 'Stock dans le temps', o().pluriel(sections.ruptures.length, 'rupture', 'ruptures'), longue.fragment,
      'Commandes, sorties pour une intervention et ruptures, de la plus récente à la plus ancienne.', [longue.suite]);
  }

  function* article(entite, contexte) {
    const sections = entite.sections;
    const unite = texte(faitDe(entite, 'Unité'));
    yield { textes: ['À quoi il sert'], reste: true, toujours: true };
    yield blocStock(sections, unite);
    yield sectionListe('wiki-montee', 'Où il est monté', sections.montee.length, sections.montee.map((monte) => ({ id: monte.equipementId,
      type: 'machine', nom: o().lienEntite(monte.lien, monte.titre), droite: monte.quantite === null ? '' : '× ' + UI.nombreFr(monte.quantite) })),
    { nom: 'machines', vide: 'Monté sur aucune machine de la nomenclature.' });
    yield sectionListe('wiki-consomme-sur', 'Consommé sur', sections.consommeSur.length, sections.consommeSur.map((sur) => ({ id: sur.equipementId,
      type: 'machine', nom: o().lienEntite(sur.lien, sur.titre), sous: o().pluriel(sur.nombreOt, 'intervention clôturée', 'interventions clôturées'),
      droite: 'quantité ' + UI.nombreFr(sur.quantite) + (unite ? ' ' + unite : '') })),
    { nom: 'machines', vide: 'Jamais consommé dans une intervention clôturée.' });
    yield blocInterventions('wiki-interventions', 'Interventions où il a servi', sections.interventions, contexte,
      { vide: 'Il n\'a servi à aucune intervention.' });
    yield blocSavoirFaire(entite, contexte, 'Pas encore de savoir-faire pour cet article.');
    yield blocRetours(entite);
  }

  // ===========================================================================================
  // 5. Technicien, intervention, savoir-faire
  // ===========================================================================================

  function* technicien(entite, contexte) {
    const habilitations = entite.sections.habilitations;
    yield calcule('Calculé par Prévo : ses interventions et ses habilitations. Le nom d\'un technicien n\'est jamais envoyé à l\'IA.');
    yield sectionListe('wiki-habilitations', 'Habilitations', habilitations.length, habilitations.map((habilitation) => ({
      id: habilitation.id, nom: nom(habilitation.intitule), sous: habilitation.obtention ? 'obtenue le ' + UI.dateFr(habilitation.obtention) : '',
      droite: [habilitation.echeance ? 'jusqu\'au ' + UI.dateFr(habilitation.echeance) : 'sans échéance', ' ',
        UI.badgeStatut(habilitation.etat, TONS_HABILITATION[habilitation.etat])] })),
    { nom: 'habilitations', vide: 'Aucune habilitation enregistrée.' });
    yield blocInterventions('wiki-interventions', 'Interventions', entite.sections.interventions, contexte,
      { aide: 'Celles dont il est le technicien ou où il a pointé du temps.' });
  }

  function* intervention(entite) {
    const sections = entite.sections;
    const lien = o();
    const ecrit = (id, titre, valeur, absent) => {
      if (valeur) return section(id, titre, null, UI.html`<p class="wiki-texte-ot">${valeur}</p>`);
      return absent ? section(id, titre, null, vide(absent)) : null;
    };
    const demande = sections.demande;
    const heures = sections.temps.reduce((somme, temps) => somme + (temps.heures || 0), 0);
    const unite = (articleId) => texte((Donnees.trouver('articles', articleId) || {}).unite);
    yield demande ? section('wiki-demande', 'Demande d\'origine', null, UI.html`<p class="wiki-texte-ot">« ${demande.symptome} »</p>
      ${demande.description ? UI.html`<p class="wiki-texte-ot">${demande.description}</p>` : ''}
      <p class="wiki-meta">${lien.joindre([demande.id, UI.dateHeureFr(demande.date), demande.demandeur ? 'par ' + demande.demandeur : '',
        demande.statut], ' · ')}</p>`) : null;
    yield ecrit('wiki-travail', 'Travail demandé', sections.travail, 'Aucun travail décrit.');
    yield ecrit('wiki-compte-rendu', 'Compte rendu', sections.compteRendu, 'Pas encore de compte rendu.');
    yield sections.astuce ? section('wiki-astuce', 'Astuce pour la prochaine fois', null, UI.html`<p class="wiki-texte-ot">${sections.astuce}</p>
      <p class="wiki-meta">Écrite par le technicien dans l'OT.</p>`) : null;
    yield ecrit('wiki-motif-attente', 'Motif d\'attente', sections.motifAttente);
    yield ecrit('wiki-motif-annulation', 'Motif d\'annulation', sections.motifAnnulation);
    yield sectionListe('wiki-pieces', 'Pièces sorties', sections.pieces.length, sections.pieces.map((piece) => ({ id: piece.articleId,
      type: 'article', nom: lien.lienEntite(piece.lien, piece.titre),
      droite: '× ' + UI.nombreFr(piece.quantite) + (unite(piece.articleId) ? ' ' + unite(piece.articleId) : '') })),
    { nom: 'pièces', vide: 'Aucune pièce sortie pour cette intervention.', aide: 'Sorties du magasin, retours déduits.' });
    yield sections.operations.length ? sectionListe('wiki-operations', 'Opérations', sections.operations.length,
      sections.operations.map((operation, rang) => ({ id: 'operation-' + (rang + 1),
        nom: nom((operation.ordre === null ? '' : UI.nombreFr(operation.ordre) + '. ') + operation.operation),
        sous: lien.joindre([operation.valeurAttendue ? 'attendu : ' + operation.valeurAttendue : '',
          operation.valeurMesuree ? 'mesuré : ' + operation.valeurMesuree : ''], ' · '),
        droite: UI.badgeStatut(operation.fait ? 'fait' : 'non fait', operation.fait ? 'ok' : 'neutre') })), { nom: 'opérations' }) : null;
    yield sections.temps.length ? sectionListe('wiki-temps', 'Temps passés', UI.heures(heures), sections.temps.map((temps) => ({
      id: temps.id, type: 'technicien', nom: lien.lienEntite(temps.lien, temps.nom || temps.technicienId),
      sous: UI.dateFr(temps.date), droite: UI.heures(temps.heures) })), { nom: 'pointages' }) : null;
    yield sectionListe('wiki-cite-dans', 'Cité dans le wiki', sections.citeDans.length, sections.citeDans.map((page) => ({ id: page.id,
      type: page.type, nom: lien.lienEntite(page.lien, page.titre) })),
    { nom: 'pages', vide: 'Pas encore cité par une page du wiki.', aide: 'Les pages dont un texte cite cette intervention.' });
  }

  function* savoirFaire(entite) {
    const sousPages = entite.sections.sousPages || [];
    yield { textes: Wiki.RUBRIQUES['savoir-faire'] || [], reste: true, toujours: true, titreVide: 'Le savoir-faire' };
    yield sousPages.length ? sectionListe('wiki-sous-pages', 'Sous-pages', sousPages.length, sousPages.map((sousPage) => ({
      id: sousPage.id, type: 'savoir-faire', nom: o().lienEntite(sousPage.id, sousPage.titre) })),
    { nom: 'sous-pages', aide: 'Le savoir-faire est découpé en pages liées : chacune reprend un sujet, avec ses OT cités.' }) : null;
    yield blocRetours(entite);
  }

  const SECTIONS = { machine, panne, article, technicien, intervention, 'savoir-faire': savoirFaire };

  /**
   * Morceaux de la colonne de lecture d'une page (voir l'en-tête), dans leur ordre, rendus un à un (chacun créé quand
   * on le demande) ; null : rien à montrer.
   */
  function sectionsEntite(entite, contexte) {
    return SECTIONS[entite.type] ? SECTIONS[entite.type](entite, contexte) : [];
  }

  return { sectionsEntite };
})());
