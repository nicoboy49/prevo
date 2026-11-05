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
      <span class="wiki-barre-cas">${I18n.t('wiki.compte.cas', { n: element.cas })}</span></li>`;
  const plusDeCas = (elements) => Math.max(1, ...elements.map((element) => element.cas));

  /**
   * Liste longue (D101) : ses `montres` premiers éléments, le reste créé au clic sur « Voir les n autres <nom> » →
   * { fragment, suite } ; `suite` est branchée par creerSection. reglages : { rendre (fragment d'un élément ; une ligne
   * par défaut), cadre (fragment de la liste avec les premiers), selecteur (la liste où ajouter), nom, montres, vide }.
   */
  function sousListe(elements, reglages) {
    const r = Object.assign({ rendre: ligne, nom: 'lignes', montres: LIGNES_MONTREES, selecteur: 'ul',
      cadre: (premiers) => UI.html`<ul class="wiki-lignes-entites wiki-lignes-page">${premiers}</ul>` }, reglages);
    if (!elements.length) return { fragment: vide(r.vide || I18n.t('wiki.sous_liste.rien_instant')), suite: null };
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
    const longue = sousListe(interventions, { montres: INTERVENTIONS_MONTREES, nom: 'interventions', vide: reglages.vide || I18n.t('wiki.bloc_interventions.aucune_intervention'),
      rendre: telephone ? carteIntervention : (ot) => ligneIntervention(ot, reglages.sansMachine),
      selecteur: telephone ? 'ul' : 'tbody',
      cadre: (premiers) => (telephone ? UI.html`<ul class="liste-cartes wiki-cartes-interventions">${premiers}</ul>`
        : UI.html`<div class="table-defile"><table class="table wiki-table-interventions">
          <caption class="visuellement-cache">${titre}</caption>
          <thead><tr><th scope="col">${I18n.t('commun.champ.date')}</th><th scope="col">${I18n.t('wiki.bloc_interventions.n')}</th><th scope="col">${I18n.t('wiki.bloc_interventions.intervention_statut')}</th><th scope="col">${I18n.t('wiki.bloc_interventions.panne')}</th>
            ${reglages.sansMachine ? '' : UI.html`<th scope="col">${I18n.t('wiki.bloc_interventions.machine')}</th>`}<th scope="col">${I18n.t('commun.champ.technicien')}</th></tr></thead>
          <tbody>${premiers}</tbody></table></div>`) });
    return creerSection(id, titre, interventions.length, longue.fragment, reglages.aide, [longue.suite]);
  }

  function blocSavoirFaire(entite, contexte, vide_) {
    const savoirs = entite.sections.savoirFaire;
    return section('wiki-savoir-faire', 'Savoir-faire', savoirs.length, UI.html`${savoirs.length
      ? liste(savoirs.map((savoir) => ({ id: savoir.id, type: 'savoir-faire', nom: o().lienEntite(savoir.lien, savoir.titre) })))
      : vide(vide_)}${contexte.responsable ? UI.html`<p class="wiki-ecrire-lien"><a class="btn btn-fantome" id="wiki-ecrire-savoir-faire"
        href="#/wiki-ecrire/nouvelle?rattache=${encodeURIComponent(entite.id)}">${UI.icone('ajouter')}${I18n.t('wiki.bloc_savoir_faire.ecrire_savoir_faire')}</a></p>` : ''}`);
  }

  /** « Pages qui renvoient ici » (CS103) : les pages du wiki dont un texte fait un lien vers celle-ci ; null sans retour. */
  function blocRetours(entite) {
    const retours = entite.retours || [];
    return retours.length ? sectionListe('wiki-retours', I18n.t('wiki.bloc_retours.pages_renvoient_ici'), retours.length, retours.map((retour) => ({
      id: retour.id, type: retour.type, nom: o().lienEntite(retour.lien, retour.titre) })),
    { nom: 'pages', aide: I18n.t('wiki.bloc_retours.pages_wiki_dont_texte') }) : null;
  }

  const calcule = (phrase) => UI.html`<p class="wiki-calcule">${UI.icone('indicateurs')}<span>${phrase}</span></p>`;

  /**
   * Lignes (voir `ligne`) des articles consommés ou changés (D118) : nom, nombre d'interventions (`compte(n)`) suivi des OT_MONTRES plus récents de `article.ot` (ordre des interventions : les plus récents d'abord) en
   * petits numéros, puis « … et n autres » ; quantité à droite. Les fragments de toute la liste sont faits ici, dans son
   * ordre, même pour les lignes créées au clic : chaque OT prend son numéro à sa place (précisions en tête).
   */
  function lignesArticles(articles, contexte, compte) {
    return articles.map((article) => {
      const numeros = article.ot.slice(0, OT_MONTRES).map((ot) => contexte.refs.fragment(ot));
      const autres = article.ot.length - OT_MONTRES;
      return { id: article.articleId, type: 'article', nom: o().lienEntite(article.lien, article.titre),
        sous: UI.html`${compte(article.ot.length)}${numeros}${autres > 0
          ? UI.html` <span class="wiki-ref-autres">${I18n.t('wiki.lignes_articles.n_autres', { n: autres })}</span>` : ''}`,
        droite: I18n.t('wiki.lignes_articles.quantite_quantite', { quantite: UI.nombreFr(article.quantite) }) };
    });
  }

  // ===========================================================================================
  // 2. Machine
  // ===========================================================================================

  function blocArticles(sections, contexte) {
    const montes = sousListe(sections.articlesMontes.map((article) => ({ id: article.articleId, type: 'article',
      nom: o().lienEntite(article.lien, article.titre), droite: article.quantite === null ? '' : '× ' + UI.nombreFr(article.quantite) })),
    { nom: 'articles', vide: I18n.t('wiki.bloc_articles.aucun_article_nomenclature_machine') });
    const consommes = sousListe(lignesArticles(sections.articlesConsommes, contexte, (n) => I18n.t('wiki.bloc_articles.interventions_cloturees', { n })),
      { nom: 'articles', vide: I18n.t('wiki.bloc_articles.aucune_piece_sortie_intervention') });
    return creerSection('wiki-articles', I18n.t('wiki.bloc_articles.articles'), null, UI.html`
      <h3 class="wiki-sous-section">${I18n.html('wiki.bloc_articles.montes_nb_articles_montes', { nbArticlesMontes: sections.articlesMontes.length })}</h3>${montes.fragment}
      <h3 class="wiki-sous-section">${I18n.html('wiki.bloc_articles.consommes_nb_articles_consommes', { nbArticlesConsommes: sections.articlesConsommes.length })}</h3>${consommes.fragment}`,
    I18n.t('wiki.bloc_articles.montes_nomenclature_machine_consommes'),
    [montes.suite, consommes.suite]);
  }

  function blocPreventif(sections) {
    if (!sections.gammes.length && !sections.controles.length) return null;
    const gammes = sections.gammes.map((gamme) => ({ id: gamme.id, nom: nom(gamme.libelle),
      sous: gamme.periodiciteJours ? I18n.t('wiki.bloc_preventif.tous_jours', { n: gamme.periodiciteJours, jours: UI.nombreFr(gamme.periodiciteJours) }) : I18n.t('wiki.bloc_preventif.selon_declencheur', { declencheur: (gamme.declencheur || I18n.t('wiki.bloc_preventif.declencheur')) }),
      droite: gamme.prochaine ? I18n.t('wiki.bloc_preventif.prochaine_prochaine', { prochaine: UI.dateFr(gamme.prochaine) }) : I18n.t('wiki.bloc_preventif.sans_echeance') }));
    const controles = sections.controles.map((controle) => ({ id: controle.id, nom: nom(controle.nature),
      sous: o().joindre([controle.organisme, controle.derniere ? I18n.t('wiki.bloc_preventif.dernier_derniere', { derniere: UI.dateFr(controle.derniere) }) : ''], ' · '),
      droite: controle.prochaine ? I18n.t('wiki.bloc_preventif.prochain_prochaine', { prochaine: UI.dateFr(controle.prochaine) }) : I18n.t('wiki.bloc_preventif.sans_echeance') }));
    return sectionListe('wiki-preventif', I18n.t('wiki.bloc_preventif.preventif_controles'), gammes.length + controles.length, gammes.concat(controles),
      { aide: I18n.t('wiki.bloc_preventif.gammes_actives_controles_reglementaires') });
  }

  function* machine(entite, contexte) {
    const sections = entite.sections;
    const total = sections.pannes.reduce((somme, panne) => somme + panne.cas, 0);
    yield { textes: [Wiki.RUBRIQUES['équipement'][0]], toujours: true };                  // « En bref » (marqueur, D156)
    yield sectionBarres('wiki-pannes', I18n.t('wiki.machine.pannes_frequentes'), total ? I18n.t('wiki.compte.cas', { n: total }) : null,
      sections.pannes.map((panne) => ({ id: panne.lien, nom: o().lienEntite(panne.lien, panne.libelle),
        detail: panne.derniere ? I18n.t('wiki.machine.derniere_derniere', { derniere: UI.dateFr(panne.derniere) }) : '', cas: panne.cas })),
      { aide: I18n.t('wiki.machine.interventions_correctives_cloturees_code'), nom: 'pannes',
        vide: I18n.t('wiki.machine.aucune_panne_elles_naissent') });
    yield blocInterventions('wiki-interventions', I18n.t('wiki.machine.interventions'), sections.interventions, contexte, { sansMachine: true,
      vide: I18n.t('wiki.machine.aucune_intervention_machine') });
    yield Wiki.champRecherche({ equipementId: entite.id, titre: I18n.t('wiki.machine.chercher_historique_machine') });
    yield blocArticles(sections, contexte);
    yield blocSavoirFaire(entite, contexte, I18n.t('wiki.machine.pas_encore_savoir_faire'));
    yield { textes: [Wiki.RUBRIQUES['équipement'][1]], reste: true };                     // « Astuces »
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
    yield calcule(I18n.t('wiki.panne.calcule_prevo_partir_interventions'));
    yield sectionBarres('wiki-panne-machines', I18n.t('wiki.panne.machines_touchees'), sections.machines.length, sections.machines.map((touchee) => ({
      id: touchee.equipementId, nom: o().lienEntite(touchee.lien, touchee.titre), cas: touchee.cas })),
    { nom: 'machines', vide: I18n.t('wiki.panne.aucune_machine_connue') });
    yield sectionBarres('wiki-causes', I18n.t('wiki.panne.causes'), sections.causes.length, codes(sections.causes), { nom: 'causes',
      vide: I18n.t('wiki.panne.aucune_cause_renseignee_cas'), apres: UI.html`<p class="note wiki-mention">${Wiki.MENTION_STATISTIQUE}</p>` });
    yield sectionBarres('wiki-remedes', I18n.t('wiki.panne.remedes'), sections.remedes.length, codes(sections.remedes), { nom: 'remedes',
      vide: I18n.t('wiki.panne.aucun_remede_renseigne_cas') });
    yield sectionListe('wiki-articles-changes', I18n.t('wiki.panne.articles_changes'), sections.articles.length,
      lignesArticles(sections.articles, contexte, (n) => I18n.t('wiki.compte.interventions', { n })),
      { nom: 'articles', vide: I18n.t('wiki.panne.aucune_piece_sortie_panne') });
    yield blocInterventions('wiki-interventions', I18n.t('wiki.machine.interventions'), sections.interventions, contexte,
      { aide: I18n.t('wiki.panne.toutes_interventions_code_ouvertes') });
    yield blocRetours(entite);
  }

  // ===========================================================================================
  // 4. Article : stock dans le temps
  // ===========================================================================================

  /** « Commandé : 4 pièces chez X à 12,00 € l'unité » : une phrase par forme (fournisseur, prix connus ou non). */
  function texteCommande(commande, quantiteCommandee) {
    const fournisseur = commande.fournisseur;
    const prix = Number.isFinite(commande.prixUnitaire) ? UI.euro(commande.prixUnitaire) : '';
    if (fournisseur && prix) return I18n.t('wiki.texte_commande.commande_chez_unite', { quantiteCommandee, fournisseur, prix });
    if (fournisseur) return I18n.t('wiki.texte_commande.commande_chez', { quantiteCommandee, fournisseur });
    return prix ? I18n.t('wiki.texte_commande.commande_unite', { quantiteCommandee, prix }) : I18n.t('wiki.texte_commande.commande_quantite_commandee', { quantiteCommandee });
  }

  /** « Sorti : 2 pièces pour OT-… sur CH-01 » (ou « Rendu : … de … ») : liens gardés, une phrase par forme. */
  function texteMouvement(mouvement, quantiteMouvement) {
    const valeurs = { quantite: quantiteMouvement, ot: o().lienEntite(mouvement.lien, mouvement.ot),
      machine: mouvement.machine ? o().lienMachine(mouvement.machine) : '' };
    if (mouvement.type === 'retour') {
      return I18n.html(mouvement.machine ? 'wiki.bloc_stock.rendu_sur_machine' : 'wiki.bloc_stock.rendu', valeurs);
    }
    return I18n.html(mouvement.machine ? 'wiki.bloc_stock.sorti_sur_machine' : 'wiki.bloc_stock.sorti', valeurs);
  }

  function blocStock(sections, unite) {
    const quantite = (valeur) => UI.nombreFr(valeur) + (unite ? ' ' + unite : '');
    const evenements = [].concat(
      sections.commandes.map((commande) => ({ date: commande.date, type: 'commande', id: commande.id,
        texte: texteCommande(commande, quantite(commande.quantite)),
        droite: commande.reception ? I18n.t('wiki.bloc_stock.recu_reception', { reception: UI.dateFr(commande.reception) }) : commande.statut })),
      sections.sorties.map((mouvement) => ({ date: mouvement.date, type: mouvement.type, id: mouvement.id,
        texte: texteMouvement(mouvement, quantite(mouvement.quantite)),
        droite: I18n.t('wiki.bloc_stock.reste_quantite', { quantite: quantite(mouvement.stock) }) })),
      sections.ruptures.map((rupture) => ({ date: rupture.debut, type: 'rupture', id: 'rupture-' + rupture.debut,
        texte: UI.html`<span class="badge ko">${I18n.t('wiki.bloc_stock.rupture')}</span>`, droite: rupture.fin ? I18n.t('wiki.bloc_stock.jusqu_au', { date: UI.dateFr(rupture.fin) }) : I18n.t('wiki.bloc_stock.toujours') })),
    ).sort((a, b) => (a.date < b.date ? 1 : (a.date > b.date ? -1 : 0)));
    const rendre = (evenement) => UI.html`<li class="wiki-evenement" data-type="${evenement.type}" data-id="${evenement.id}">
      <span class="wiki-evenement-date">${UI.dateFr(evenement.date)}</span>
      <span class="wiki-evenement-texte">${evenement.texte}</span><span class="wiki-evenement-droite">${evenement.droite}</span></li>`;
    const longue = sousListe(evenements, { rendre, montres: EVENEMENTS_MONTRES, nom: 'lignes',
      vide: I18n.t('wiki.bloc_stock.aucune_commande_ni_aucune'), cadre: (premiers) => UI.html`<ul class="wiki-chronologie">${premiers}</ul>` });
    return creerSection('wiki-stock', I18n.t('wiki.bloc_stock.stock_temps'), I18n.t('wiki.compte.ruptures', { n: sections.ruptures.length }), longue.fragment,
      I18n.t('wiki.bloc_stock.commandes_sorties_intervention_ruptures'), [longue.suite]);
  }

  function* article(entite, contexte) {
    const sections = entite.sections;
    const unite = texte(faitDe(entite, I18n.t('wiki.fait.unite')));
    yield { textes: Wiki.RUBRIQUES.composant, reste: true, toujours: true };             // « À quoi il sert »
    yield blocStock(sections, unite);
    yield sectionListe('wiki-montee', I18n.t('wiki.article.ou_monte'), sections.montee.length, sections.montee.map((monte) => ({ id: monte.equipementId,
      type: 'machine', nom: o().lienEntite(monte.lien, monte.titre), droite: monte.quantite === null ? '' : '× ' + UI.nombreFr(monte.quantite) })),
    { nom: 'machines', vide: I18n.t('wiki.article.monte_aucune_machine_nomenclature') });
    yield sectionListe('wiki-consomme-sur', I18n.t('wiki.article.consomme'), sections.consommeSur.length, sections.consommeSur.map((sur) => ({ id: sur.equipementId,
      type: 'machine', nom: o().lienEntite(sur.lien, sur.titre), sous: I18n.t('wiki.bloc_articles.interventions_cloturees', { n: sur.nombreOt }),
      droite: unite ? I18n.t('wiki.article.quantite_unite', { quantite: UI.nombreFr(sur.quantite), unite })
        : I18n.t('wiki.lignes_articles.quantite_quantite', { quantite: UI.nombreFr(sur.quantite) }) })),
    { nom: 'machines', vide: I18n.t('wiki.article.jamais_consomme_intervention_cloturee') });
    yield blocInterventions('wiki-interventions', I18n.t('wiki.article.interventions_ou_servi'), sections.interventions, contexte,
      { vide: I18n.t('wiki.article.servi_aucune_intervention') });
    yield blocSavoirFaire(entite, contexte, I18n.t('wiki.article.pas_encore_savoir_faire'));
    yield blocRetours(entite);
  }

  // ===========================================================================================
  // 5. Technicien, intervention, savoir-faire
  // ===========================================================================================

  function* technicien(entite, contexte) {
    const habilitations = entite.sections.habilitations;
    yield calcule(I18n.t('wiki.technicien.calcule_prevo_interventions_habilitations'));
    yield sectionListe('wiki-habilitations', I18n.t('wiki.technicien.habilitations'), habilitations.length, habilitations.map((habilitation) => ({
      id: habilitation.id, nom: nom(habilitation.intitule), sous: habilitation.obtention ? I18n.t('wiki.technicien.obtenue_obtention', { obtention: UI.dateFr(habilitation.obtention) }) : '',
      droite: [habilitation.echeance ? I18n.t('wiki.technicien.jusqu_au', { date: UI.dateFr(habilitation.echeance) }) : I18n.t('wiki.bloc_preventif.sans_echeance'), ' ',
        UI.badgeStatut(habilitation.etat, TONS_HABILITATION[habilitation.etat])] })),
    { nom: 'habilitations', vide: I18n.t('wiki.technicien.aucune_habilitation_enregistree') });
    yield blocInterventions('wiki-interventions', I18n.t('wiki.machine.interventions'), entite.sections.interventions, contexte,
      { aide: I18n.t('wiki.technicien.celles_dont_technicien_ou') });
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
    yield demande ? section('wiki-demande', I18n.t('wiki.intervention.demande_origine'), null, UI.html`<p class="wiki-texte-ot">${I18n.t('wiki.intervention.symptome', { symptome: demande.symptome })}</p>
      ${demande.description ? UI.html`<p class="wiki-texte-ot">${demande.description}</p>` : ''}
      <p class="wiki-meta">${lien.joindre([demande.id, UI.dateHeureFr(demande.date), demande.demandeur ? I18n.t('wiki.intervention.demandeur', { demandeur: demande.demandeur }) : '',
        demande.statut], ' · ')}</p>`) : null;
    yield ecrit('wiki-travail', I18n.t('wiki.intervention.travail_demande'), sections.travail, I18n.t('wiki.intervention.aucun_travail_decrit'));
    yield ecrit('wiki-compte-rendu', I18n.t('wiki.intervention.compte_rendu'), sections.compteRendu, I18n.t('wiki.intervention.pas_encore_compte_rendu'));
    yield sections.astuce ? section('wiki-astuce', I18n.t('wiki.intervention.astuce_prochaine_fois'), null, UI.html`<p class="wiki-texte-ot">${sections.astuce}</p>
      <p class="wiki-meta">${I18n.t('wiki.intervention.ecrite_technicien_ot')}</p>`) : null;
    yield ecrit('wiki-motif-attente', I18n.t('wiki.intervention.motif_attente'), sections.motifAttente);
    yield ecrit('wiki-motif-annulation', I18n.t('wiki.intervention.motif_annulation'), sections.motifAnnulation);
    yield sectionListe('wiki-pieces', I18n.t('wiki.intervention.pieces_sorties'), sections.pieces.length, sections.pieces.map((piece) => ({ id: piece.articleId,
      type: 'article', nom: lien.lienEntite(piece.lien, piece.titre),
      droite: '× ' + UI.nombreFr(piece.quantite) + (unite(piece.articleId) ? ' ' + unite(piece.articleId) : '') })),
    { nom: 'pieces', vide: I18n.t('wiki.intervention.aucune_piece_sortie_intervention'), aide: I18n.t('wiki.intervention.sorties_magasin_retours_deduits') });
    yield sections.operations.length ? sectionListe('wiki-operations', I18n.t('wiki.intervention.operations'), sections.operations.length,
      sections.operations.map((operation, rang) => ({ id: 'operation-' + (rang + 1),
        nom: nom((operation.ordre === null ? '' : UI.nombreFr(operation.ordre) + '. ') + operation.operation),
        sous: lien.joindre([operation.valeurAttendue ? 'attendu : ' + operation.valeurAttendue : '',
          operation.valeurMesuree ? I18n.t('wiki.intervention.mesure_valeur_mesuree', { valeurMesuree: operation.valeurMesuree }) : ''], ' · '),
        droite: UI.badgeStatut(operation.fait ? I18n.t('wiki.intervention.fait') : I18n.t('wiki.intervention.non_fait'), operation.fait ? 'ok' : 'neutre') })), { nom: 'operations' }) : null;
    yield sections.temps.length ? sectionListe('wiki-temps', I18n.t('wiki.intervention.temps_passes'), UI.heures(heures), sections.temps.map((temps) => ({
      id: temps.id, type: 'technicien', nom: lien.lienEntite(temps.lien, temps.nom || temps.technicienId),
      sous: UI.dateFr(temps.date), droite: UI.heures(temps.heures) })), { nom: 'pointages' }) : null;
    yield sectionListe('wiki-cite-dans', I18n.t('wiki.intervention.cite_wiki'), sections.citeDans.length, sections.citeDans.map((page) => ({ id: page.id,
      type: page.type, nom: lien.lienEntite(page.lien, page.titre) })),
    { nom: 'pages', vide: I18n.t('wiki.intervention.pas_encore_cite_page'), aide: I18n.t('wiki.intervention.pages_dont_texte_cite') });
  }

  function* savoirFaire(entite) {
    const sousPages = entite.sections.sousPages || [];
    yield { textes: Wiki.RUBRIQUES['savoir-faire'] || [], reste: true, toujours: true, titreVide: I18n.t('wiki.savoir_faire.savoir_faire') };
    yield sousPages.length ? sectionListe('wiki-sous-pages', 'Sous-pages', sousPages.length, sousPages.map((sousPage) => ({
      id: sousPage.id, type: 'savoir-faire', nom: o().lienEntite(sousPage.id, sousPage.titre) })),
    { nom: 'sous-pages', aide: I18n.t('wiki.savoir_faire.savoir_faire_decoupe_pages') }) : null;
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
