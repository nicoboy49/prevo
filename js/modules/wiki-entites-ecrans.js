'use strict';
// Wiki (7 quater/9) — l'encyclopédie de l'atelier à l'écran (refonte 2, ARCHITECTURE.md §20.12 ; D113, D114 ; tâche
// T136) : l'accueil #/wiki et les listes #/wiki/<liste> des six types. Les routes sont dans wiki-ecrans.js, la page
// d'une entité dans wiki-page-ecrans.js et wiki-sections-ecrans.js (T137, chargés avant) ; ce fichier rend
// Wiki.afficherEncyclopedie et Wiki.afficherListeEntites, et prête aux pages ses outils d'affichage (Wiki.outilsEcrans :
// types, icônes et couleurs, liens vers les entités, fil d'Ariane, « Voir les n autres »).
//
//   Accueil (maquette validée par Nicolas, dans le style de l'accueil « bento » de Prévo : tuiles .bento-tuile,
//   pastilles d'icône, dégradé de la synthèse, css/modules/accueil.css), grille de 12 colonnes :
//     1. grande tuile « Ce que l'atelier sait » : phrase-résumé dont chaque nombre mène à sa liste (sans les
//        techniciens pour le demandeur), « Tiré de N interventions clôturées », champ de recherche ;
//     2. « Suivi du wiki » au responsable : à valider, à trancher, en échec (discrètes à zéro, liens vers
//        #/wiki-journal?vue=…), « Traiter la file » et le journal du wiki ;
//     3. résultats de la recherche (cachés sans requête) : les entités par type (Wiki.chercherEntites), puis les
//        interventions clôturées et les textes du wiki (Wiki.rechercher, blocs de Wiki.blocsRecherche) ;
//     4. briques Machines, Pannes, Articles, Techniciens (pas pour le demandeur), Savoir-faire : icône et couleur
//        discrète du type, nombre, une ligne utile ; chacune mène à sa liste ;
//     5. dernières interventions clôturées ; 6. pannes les plus fréquentes (barres).
//   Listes : machines par lieu (sous-ensembles sous leur machine), pannes par nombre de cas, articles en tableau
//   filtrable avec l'état du stock, techniciens en cartes, savoir-faire, interventions (ouvertes en tête, statut sur
//   chaque ligne) ; au téléphone, articles et interventions en cartes (Prévo : UI.tableau sur PC, cartes au
//   téléphone). Techniciens et interventions : « réservé » pour le demandeur (D114).
//
// Données : Wiki.accueilEncyclopedie, Wiki.listeEntites, Wiki.entite (wiki-entites.js), visibilité déjà appliquée
// (un lien null est un nom sans lien). Lecture seule, aucun appel réseau ; toute donnée passe par UI.html (échappée).
//
// Précisions au contrat (§20.12) :
//  - lien d'une entité : #/wiki/ + encodeURIComponent(identifiant), décodé une fois par la route (la page de la
//    panne du code « S/1 », PANNE-S%2F1, garde son identifiant) ;
//  - nombres de la phrase et des briques = Wiki.accueilEncyclopedie().nombres ; « 0 machine », « 1 panne »,
//    « 2 savoir-faire » (invariable) ; les machines qui ont le plus d'interventions sont nommées par leur repère,
//    celles sans intervention écartées ;
//  - dernières interventions : les DERNIERES_MONTREES premières de accueilEncyclopedie().dernieres ;
//  - longues listes (D101, relecture de T136 : 5 006 OT du jeu de charge) : seules les premières lignes sont créées —
//    recherche : ENTITES_MONTREES par type ; interventions : LIGNES_MONTREES lignes du tableau sur PC,
//    CARTES_MONTREES cartes au téléphone — ; « Voir les n autres » crée les autres au clic ;
//  - tableau des interventions (PC) : triable comme UI.tableau (mêmes classes et aria-sort, cellules vides en fin, tri
//    stable), mais le tri porte sur TOUTE la liste, dont seules les LIGNES_MONTREES premières lignes sont alors créées
//    (relecture de T137, m5 : avant, seules les 100 lignes déjà créées étaient triées) ; les cartes du téléphone ne se
//    trient pas ;
//  - lignes des briques : « : » et « · » collés au mot d'avant par une espace insécable (jamais seuls en tête de
//    ligne) ; textes d'exemple des champs plus courts au téléphone.

Object.assign(Wiki, (() => {

  // Les six types : libellés et compte (« 3 machines »), lus à l'affichage ; icône et couleur discrète (classe
  // wiki-t-<type>), route de leur liste (aussi le nom de la liste pour « Voir les n autres »), nombre de l'accueil.
  const TYPES = {
    machine: { get libelle() { return I18n.t('wiki.libelle.machine'); }, get pluriel() { return I18n.t('wiki.pluriel.machines'); },
      compte(n) { return I18n.t('wiki.compte.machines', { n }); }, icone: 'parc', liste: 'machines', nombre: 'machines' },
    panne: { get libelle() { return I18n.t('wiki.libelle.panne'); }, get pluriel() { return I18n.t('wiki.pluriel.pannes'); },
      compte(n) { return I18n.t('wiki.compte.pannes', { n }); }, icone: 'alerte', liste: 'pannes', nombre: 'pannes' },
    article: { get libelle() { return I18n.t('wiki.libelle.article'); }, get pluriel() { return I18n.t('wiki.pluriel.articles'); },
      compte(n) { return I18n.t('wiki.compte.articles', { n }); }, icone: 'magasin', liste: 'articles', nombre: 'articles' },
    technicien: { get libelle() { return I18n.t('wiki.libelle.technicien'); }, get pluriel() { return I18n.t('wiki.pluriel.techniciens'); },
      compte(n) { return I18n.t('wiki.compte.techniciens', { n }); }, icone: 'utilisateur', liste: 'techniciens', nombre: 'techniciens' },
    'savoir-faire': { get libelle() { return I18n.t('wiki.libelle.savoir_faire'); }, get pluriel() { return I18n.t('wiki.pluriel.savoir_faire'); },
      compte(n) { return I18n.t('wiki.compte.savoir_faire', { n }); }, icone: 'cle', liste: 'savoir-faire', nombre: 'savoirFaire' },
    intervention: { get libelle() { return I18n.t('wiki.libelle.intervention'); }, get pluriel() { return I18n.t('wiki.pluriel.interventions'); },
      compte(n) { return I18n.t('wiki.compte.interventions', { n }); }, icone: 'ordres', liste: 'interventions', nombre: 'interventions' },
  };
  const TYPE_DE_LISTE = Object.fromEntries(Object.keys(TYPES).map((type) => [TYPES[type].liste, type]));
  const BRIQUES = ['machine', 'panne', 'article', 'technicien', 'savoir-faire'];
  const SUIVI = [
    { vue: 'a-valider', champ: 'aValider', libelle: 'à valider', ton: 'attente' },
    { vue: 'contradictions', champ: 'aTrancher', get libelle() { return I18n.t('wiki.libelle.trancher'); }, ton: 'urgent' },
    { vue: 'echecs', champ: 'enEchec', get libelle() { return I18n.t('wiki.libelle.echec'); }, ton: 'urgent' },
  ];
  /** Phrase d'introduction de la liste d'un type (lue à l'affichage). */
  function description(type) {
    switch (type) {
      case 'machine': return I18n.t('wiki.description.parc_lieu_sous_ensembles');
      case 'panne': return I18n.t('wiki.description.page_code_symptome_tiree');
      case 'article': return I18n.t('wiki.description.pieces_magasin_ou_elles');
      case 'technicien': return I18n.t('wiki.description.interventions_habilitations_nom_jamais');
      case 'savoir-faire': return I18n.t('wiki.description.gestes_font_gagner_temps');
      default: return I18n.t('wiki.description.toutes_interventions_celles_cours');
    }
  }
  const ETATS_STOCK = { 'en stock': 'ok', 'sous le seuil': 'attention', rupture: 'ko' };
  const optionsEtat = () => [['', I18n.t('wiki.options_etat.tous_etats')], ['en stock', I18n.t('wiki.options_etat.en_stock')],
    ['sous le seuil', I18n.t('wiki.options_etat.sous_le_seuil')], ['rupture', I18n.t('wiki.options_etat.rupture')]];   // [code, libellé]
  // État du stock calculé par Wiki (code : « en stock », « sous le seuil », « rupture ») → libellé affiché.
  const libelleEtatStock = (etat) => (etat === 'en stock' ? I18n.t('wiki.etat_stock.en_stock') : etat === 'sous le seuil'
    ? I18n.t('wiki.etat_stock.sous_le_seuil') : etat === 'rupture' ? I18n.t('wiki.etat_stock.rupture') : etat);

  const DERNIERES_MONTREES = 6;          // dernières interventions de l'accueil
  const ENTITES_MONTREES = 6;            // par type, dans les résultats de la recherche
  const LIGNES_MONTREES = 100;           // interventions sur PC (tableau), avant « Voir les n autres »
  const CARTES_MONTREES = 40;            // interventions au téléphone, avant « Voir les n autres »
  const SEPARATEUR = '\u00a0·';            // « 1 habilitation suivie · 2 échues » : le point reste collé au mot d'avant
  const DELAI_RECHERCHE_MS = 300;        // comme Wiki.champRecherche : la recherche part après 300 ms sans frappe

  // ===========================================================================================
  // 1. Petits outils
  // ===========================================================================================

  const texte = (valeur) => (valeur === null || valeur === undefined ? '' : String(valeur).trim());
  const profilCourant = () => (App.profil ? texte(App.profil.type) : '');
  const adresse = (id) => '#/wiki/' + encodeURIComponent(id);
  const compte = (nombre, type) => TYPES[type].compte(nombre);

  // Ordre alphabétique français (« Électrovanne » avec les E) des articles, techniciens et savoir-faire, comme Prévo.
  const ORDRE_FRANCAIS = new Intl.Collator('fr', { numeric: true, sensitivity: 'base' });
  const enFrancais = (liste, nom) => liste.slice().sort((a, b) => ORDRE_FRANCAIS.compare(nom(a), nom(b)));

  /** Morceaux non vides séparés par `separateur` (tableau pour UI.html : chaque chaîne y est échappée). */
  const joindre = (parties, separateur) => parties.filter(Boolean).map((partie, rang) => (rang ? [separateur, partie] : [partie]));

  /**
   * Morceaux non vides qu'une ligne ne coupe jamais en leur milieu (« CH-01 », « 1 à renouveler ») : chacun garde
   * son séparateur à la fin (`marque` : ',' ou SEPARATEUR), la ligne ne se coupe qu'entre deux morceaux.
   */
  function insecables(parties, marque) {
    const gardees = parties.filter(Boolean);
    return gardees.map((partie, rang) => [rang ? ' ' : '',
      UI.html`<span class="wiki-insecable">${partie}${rang < gardees.length - 1 ? marque : ''}</span>`]);
  }

  /** Nom d'une entité en lien vers sa page (`lien` : identifiant de la page), en texte si le profil ne l'ouvre pas. */
  function lienEntite(lien, titre) {
    return lien ? UI.html`<a class="wiki-lien-entite" href="${adresse(lien)}">${titre}</a>`
      : UI.html`<span class="wiki-nom-entite">${titre}</span>`;
  }

  /** Repère d'une machine (référence d'une liste), sinon son titre. */
  function repere(machine) {
    const fiche = machine ? Donnees.trouver('equipements', machine.equipementId) : null;
    return texte(fiche && fiche.repere) || (machine ? machine.titre : '');
  }

  /** Machine par son repère, en lien (titre complet en bulle). */
  function lienMachine(machine) {
    if (!machine) return '';
    return machine.lien ? UI.html`<a class="wiki-lien-entite" href="${adresse(machine.lien)}" title="${machine.titre}">${repere(machine)}</a>`
      : UI.html`<span class="wiki-nom-entite">${repere(machine)}</span>`;
  }

  const pastille = (type) => UI.html`<span class="wiki-pastille wiki-t-${type}" aria-hidden="true">${UI.icone(TYPES[type].icone)}</span>`;
  const puce = (type) => UI.html`<span class="badge wiki-puce wiki-t-${type}">${UI.icone(TYPES[type].icone)}${TYPES[type].libelle}</span>`;
  const etatStock = (article) => UI.html`<span class="badge ${ETATS_STOCK[article.etat] || 'neutre'} wiki-etat-stock">${UI.nombreFr(article.stock)}${article.unite ? ' ' + article.unite : ''} · ${libelleEtatStock(article.etat)}</span>`;
  const fil = (morceaux) => UI.html`<nav class="fil" aria-label="${I18n.t('wiki.fil.etes_ici')}"><a href="#/wiki">${I18n.t('wiki.fil.wiki')}</a>${morceaux.map((morceau) => UI.html` <span aria-hidden="true">›</span> ${morceau}`)}</nav>`;

  /** Bouton « Voir les n autres <nom> » (fragment ; '' s'il ne reste rien). */
  // « Voir l'autre » / « Voir les n autres <liste> » : une entrée de pluriel par liste (nom : code de la liste).
  const boutonAutres = (reste, nom) => (reste > 0 ? UI.html`<button type="button" class="btn btn-fantome wiki-voir-autres">${
    I18n.t('wiki.voir_autres.' + nom.replace('-', '_'), { n: reste })}</button>` : '');

  /**
   * Longue liste (D101) : au clic sur « Voir les n autres » du bloc, `ajouter()` crée le reste (rien n'est créé avant),
   * puis le bouton disparaît et le premier lien ajouté prend le focus. `ajouter` rend les éléments ajoutés.
   */
  function brancherSuite(bloc, ajouter) {
    const bouton = UI.$('.wiki-voir-autres', bloc);
    if (!bouton) return;
    bouton.addEventListener('click', () => {
      const ajoutes = ajouter() || [];
      bouton.remove();
      const lien = ajoutes.length ? ajoutes[0].querySelector('a[href]') || (ajoutes[0].matches('a[href]') ? ajoutes[0] : null) : null;
      if (lien) lien.focus();
    });
  }

  /** Ajoute à `liste` (ul, tbody) les fragments `morceaux` (UI.html), créés d'un seul coup ; rend les éléments ajoutés. */
  function ajouterA(liste, morceaux) {
    const tampon = document.createElement(liste.tagName);
    UI.remplir(tampon, UI.html`${morceaux}`);
    const ajoutes = Array.from(tampon.children);
    liste.append(...ajoutes);
    return ajoutes;
  }

  // ===========================================================================================
  // 2. Accueil #/wiki
  // ===========================================================================================

  /** « 31 machines, 11 pannes, 52 articles, 4 techniciens et 23 savoir-faire » : chaque nombre mène à sa liste. */
  function phraseResume(nombres) {
    const morceaux = BRIQUES.filter((type) => Number.isInteger(nombres[TYPES[type].nombre]))
      .map((type) => UI.html`<a href="#/wiki/${TYPES[type].liste}" data-liste="${TYPES[type].liste}">${compte(nombres[TYPES[type].nombre], type)}</a>`);
    return morceaux.map((morceau, rang) => [rang === 0 ? '' : (rang === morceaux.length - 1 ? ' ' + I18n.t('wiki.phrase_resume.et') + ' ' : ', '), morceau]);
  }

  function tuileSynthese(accueil, profil) {
    const telephone = UI.estTelephone();         // au téléphone, un exemple qui tient dans le champ
    const exemple = profil === 'demandeur'
      ? (telephone ? I18n.t('wiki.tuile_synthese.machine_panne_article') : I18n.t('wiki.tuile_synthese.chercher_machine_panne_article'))
      : (telephone ? I18n.t('wiki.tuile_synthese.machine_panne_ot') : I18n.t('wiki.tuile_synthese.chercher_avec_interventions'));
    return UI.html`<section class="bento-tuile bento-synthese wiki-synthese" id="wiki-synthese" aria-labelledby="wiki-phrase-resume">
      <span class="bento-lueur" aria-hidden="true"><span class="bento-halo bento-halo-blanc"></span><span class="bento-halo bento-halo-cyan"></span></span>
      <p class="wiki-synthese-pastille">${UI.icone('wiki')}${I18n.t('wiki.tuile_synthese.atelier_sait')}</p>
      <h1 class="wiki-phrase-resume" id="wiki-phrase-resume">${phraseResume(accueil.nombres)}</h1>
      <p class="wiki-synthese-ligne" id="wiki-tire-de">${I18n.t('wiki.tuile_synthese.tire_de', { n: accueil.nombres.cloturees })}</p>
      <div class="wiki-recherche-accueil" role="search">
        <label class="visuellement-cache" for="wiki-champ-accueil">${I18n.t('wiki.tuile_synthese.chercher_wiki')}</label>
        ${UI.icone('recherche')}
        <input type="search" id="wiki-champ-accueil" class="wiki-recherche-champ" data-hors-saisie maxlength="200" autocomplete="off"
          enterkeyhint="search" placeholder="${exemple}" aria-describedby="wiki-aide-recherche">
        <p class="visuellement-cache" id="wiki-aide-recherche">${I18n.t('wiki.tuile_synthese.entites_wiki_nom_puis')}</p>
      </div>
    </section>`;
  }

  /** « Suivi du wiki » (responsable) : mêmes définitions que les vues du journal où mènent les petites tuiles. */
  function tuileSuivi(suivi) {
    const file = typeof Wiki.file === 'function' ? Wiki.file().length : 0;
    return UI.html`<section class="bento-tuile wiki-suivi" id="wiki-suivi" aria-labelledby="wiki-suivi-titre">
      <h2 id="wiki-suivi-titre">${I18n.t('wiki.tuile_suivi.suivi_wiki')}</h2>
      <div class="wiki-suivi-tuiles">${SUIVI.map((entree) => {
        const nombre = suivi[entree.champ];
        return UI.html`<a class="wiki-mini${nombre ? ' ' + entree.ton : ''}" data-suivi="${entree.vue}" href="#/wiki-journal?vue=${entree.vue}">
          <b class="wiki-mini-nombre">${nombre}</b><span>${entree.libelle}</span></a>`;
      })}</div>
      <div class="wiki-suivi-actions">
        <a class="btn btn-secondaire" id="wiki-traiter-file" href="#/wiki-journal?vue=file">${I18n.t('wiki.tuile_suivi.traiter_file', { file })}</a>
        <a class="wiki-lien-journal" id="wiki-lien-journal" href="#/wiki-journal">${I18n.t('wiki.tuile_suivi.journal_wiki')}</a>
      </div>
    </section>`;
  }

  /** Ligne utile d'une brique (données de Wiki.accueilEncyclopedie). */
  function ligneBrique(type, accueil) {
    if (type === 'machine') {
      const suivies = accueil.machinesPlusDInterventions.filter((machine) => machine.interventions > 0);
      return suivies.length ? [I18n.t('wiki.ligne_brique.plus_interventions') + ' ', insecables(suivies.map(repere), ',')] : I18n.t('wiki.ligne_brique.aucune_intervention_enregistree');
    }
    if (type === 'panne') {
      const panne = accueil.pannePlusFrequente;
      return panne ? [I18n.t('wiki.ligne_brique.plus_frequente', { panneTitre: panne.titre }) + ' ', insecables(['(' + I18n.t('wiki.compte.cas', { n: panne.cas }) + ')'], '')]
        : I18n.t('wiki.ligne_brique.elles_naissent_interventions_correctives');
    }
    if (type === 'article') {
      const parties = [accueil.articles.sousLeSeuil ? I18n.t('wiki.ligne_brique.sous_seuil', { sousLeSeuil: accueil.articles.sousLeSeuil }) : '',
        accueil.articles.enRupture ? I18n.t('wiki.ligne_brique.en_rupture_rupture', { enRupture: accueil.articles.enRupture }) : ''].filter(Boolean);
      return parties.length ? insecables(parties, SEPARATEUR) : I18n.t('wiki.ligne_brique.tous_stock_dessus_seuil');
    }
    if (type === 'technicien') {
      const habilitations = accueil.habilitations;
      return insecables([I18n.t('wiki.ligne_brique.habilitations_suivies', { n: habilitations.suivies }),
        habilitations.aRenouveler ? I18n.t('wiki.ligne_brique.a_renouveler_renouveler', { aRenouveler: habilitations.aRenouveler }) : '',
        habilitations.echues ? I18n.t('wiki.ligne_brique.n_echues', { n: habilitations.echues }) : ''], SEPARATEUR);
    }
    return accueil.nombres.savoirFaire ? I18n.t('wiki.ligne_brique.ecrits_partir_astuces_techniciens') : I18n.t('wiki.ligne_brique.ils_naissent_astuces_interventions');
  }

  function brique(type, accueil) {
    return UI.html`<a class="bento-tuile wiki-brique" data-type="${type}" href="#/wiki/${TYPES[type].liste}">
      <span class="bento-pastille-icone wiki-t-${type}" aria-hidden="true">${UI.icone(TYPES[type].icone)}</span>
      <h2>${TYPES[type].pluriel}</h2>
      <span class="wiki-brique-nombre">${accueil.nombres[TYPES[type].nombre]}</span>
      <span class="wiki-brique-ligne">${ligneBrique(type, accueil)}</span>
    </a>`;
  }

  /** Une intervention de l'accueil : son titre (lien vers sa page, en texte pour le demandeur), date, machine, panne. */
  function ligneDerniere(ot) {
    return UI.html`<li class="wiki-ligne" data-id="${ot.id}">${pastille('intervention')}
      <span class="wiki-ligne-corps">${lienEntite(ot.lien, ot.titre || ot.id)}
        <span class="wiki-ligne-sous">${joindre([UI.dateFr(ot.date), lienMachine(ot.machine), ot.panne ? lienEntite(ot.panne.lien, ot.panne.libelle) : ''], ' · ')}</span>
      </span></li>`;
  }

  function tuileDernieres(accueil) {
    const lignes = accueil.dernieres.slice(0, DERNIERES_MONTREES);
    return UI.html`<section class="bento-tuile wiki-tuile-liste" id="wiki-dernieres" aria-labelledby="wiki-dernieres-titre">
      <div class="bento-liste-tete"><h2 id="wiki-dernieres-titre">${I18n.t('wiki.tuile_dernieres.dernieres_interventions')}</h2>
        ${accueil.nombres.interventions === null ? '' : UI.html`<a class="bento-tout-voir" href="#/wiki/interventions">${I18n.t('wiki.tuile_dernieres.toutes')}</a>`}</div>
      ${lignes.length ? UI.html`<ul class="wiki-lignes-entites">${lignes.map(ligneDerniere)}</ul>`
        : UI.html`<p class="bento-vide">${I18n.t('wiki.tuile_dernieres.aucune_intervention_cloturee_instant')}</p>`}
    </section>`;
  }

  function tuilePannes(accueil) {
    const pannes = accueil.pannesFrequentes;
    const plus = pannes.length ? Math.max(1, pannes[0].cas) : 1;
    return UI.html`<section class="bento-tuile wiki-tuile-liste" id="wiki-pannes-frequentes" aria-labelledby="wiki-pannes-titre">
      <div class="bento-liste-tete"><h2 id="wiki-pannes-titre">${I18n.t('wiki.tuile_pannes.pannes_plus_frequentes')}</h2>
        <a class="bento-tout-voir" href="#/wiki/pannes">${I18n.t('wiki.tuile_dernieres.toutes')}</a></div>
      ${pannes.length ? UI.html`<ul class="wiki-barres">${pannes.map((panne) => UI.html`<li data-id="${panne.id}">
          ${lienEntite(panne.lien, panne.titre)}
          <span class="wiki-jauge" aria-hidden="true"><i style="width: ${Math.max(4, Math.round(100 * panne.cas / plus))}%"></i></span>
          <span class="wiki-barre-cas">${I18n.t('wiki.compte.cas', { n: panne.cas })}</span></li>`)}</ul>`
        : UI.html`<p class="bento-vide">${I18n.t('wiki.tuile_pannes.aucune_panne_instant_elles')}</p>`}
    </section>`;
  }

  // --- recherche de l'accueil ---

  const TITRES_TROUVES = { intervention: (entite) => entite.element.id + ' · ' + entite.titre };
  const SOUS_TROUVES = {
    machine: (e) => [e.lieu, e.marqueModele],
    panne: (e) => [I18n.t('wiki.compte.cas', { n: e.cas }), I18n.t('wiki.compte.machines', { n: e.machines })],
    article: (e) => [e.reference, e.emplacement ? I18n.t('wiki.article.range_emplacement', { emplacement: e.emplacement }) : ''],
    technicien: (e) => [e.metier],
    'savoir-faire': (e) => [e.rattachement ? e.rattachement.titre : ''],
    intervention: (e) => [UI.dateFr(e.date), Schema.libelleValeur('ordres_travail', 'statut', e.statut)],
  };

  function entiteTrouvee(type, entite) {
    const sous = SOUS_TROUVES[type](entite.element).filter(Boolean).join(' · ');
    return UI.html`<li class="wiki-ligne wiki-entite-trouvee" data-id="${entite.lien || ''}">
      ${pastille(type)}<span class="wiki-ligne-corps">${lienEntite(entite.lien, (TITRES_TROUVES[type] || ((e) => e.titre))(entite))}
      ${sous ? UI.html`<span class="wiki-ligne-sous">${sous}</span>` : ''}</span></li>`;
  }

  /** Un groupe de la recherche (« Machines · 3 ») : ses ENTITES_MONTREES premières entités, les autres créées au clic. */
  function groupeTrouve(groupe) {
    const type = groupe.type;
    const bloc = UI.element(UI.html`<div class="wiki-groupe" data-type="${type}">
      <h3 class="wiki-groupe-titre">${TYPES[type].pluriel} · ${groupe.entites.length}</h3>
      <ul class="wiki-lignes-entites">${groupe.entites.slice(0, ENTITES_MONTREES).map((entite) => entiteTrouvee(type, entite))}</ul>
      ${boutonAutres(groupe.entites.length - ENTITES_MONTREES, TYPES[type].liste)}
    </div>`);
    brancherSuite(bloc, () => ajouterA(UI.$('ul', bloc), groupe.entites.slice(ENTITES_MONTREES).map((entite) => entiteTrouvee(type, entite))));
    return bloc;
  }

  /** Résultats d'une requête : les entités par type, puis les interventions et les textes du wiki (Wiki.rechercher). */
  function afficherTrouves(zone, requete, profil) {
    const entites = Wiki.chercherEntites(requete, { profil });
    const blocs = Wiki.blocsRecherche(Wiki.rechercher(requete, {}), {});
    if (!entites.groupes.length && !blocs.length) {             // un seul titre : rien trouvé
      UI.remplir(zone, UI.html`<h2 class="wiki-trouves-titre wiki-rien">${I18n.t('wiki.trouves.rien_trouve', { requete })}</h2>
        <p class="aide">${I18n.t('wiki.trouves.essayez_repere_cp_01')}</p>`);
      return;
    }
    UI.remplir(zone, UI.html`<h2 class="wiki-trouves-titre">${I18n.t('wiki.trouves.resultats_requete', { requete })}</h2>`);
    entites.groupes.forEach((groupe) => zone.appendChild(groupeTrouve(groupe)));
    if (!blocs.length) return;
    const plein = UI.element(UI.html`<div class="wiki-groupe wiki-plein-texte" data-type="texte">
      <h3 class="wiki-groupe-titre">${I18n.t('wiki.trouves.interventions_textes_wiki')}</h3><div class="wiki-resultats"></div></div>`);
    UI.remplir(UI.$('.wiki-resultats', plein), blocs);
    zone.appendChild(plein);
  }

  function brancherRecherche(conteneur, profil) {
    const champ = UI.$('#wiki-champ-accueil', conteneur);
    const zone = UI.$('#wiki-trouves', conteneur);
    let minuterie = null;
    function chercher() {
      clearTimeout(minuterie);
      minuterie = null;
      const requete = texte(champ.value);
      zone.hidden = !requete;
      if (!requete) {
        zone.textContent = '';
        return;
      }
      try {
        afficherTrouves(zone, requete, profil);
      } catch (erreur) {
        UI.remplir(zone, UI.html`<p class="erreur">${I18n.t('wiki.brancher_recherche.recherche_impossible', { message: (erreur && erreur.message) || '' })}</p>`);
        console.warn('Prévo (wiki) : recherche impossible (' + (erreur && erreur.message) + ').', erreur);
      }
    }
    champ.addEventListener('input', () => {
      clearTimeout(minuterie);
      minuterie = setTimeout(() => { if (champ.isConnected) chercher(); }, DELAI_RECHERCHE_MS);
    });
    champ.addEventListener('keydown', (evenement) => {
      if (evenement.key !== 'Enter') return;
      evenement.preventDefault();
      chercher();
    });
  }

  /** Écran #/wiki : l'accueil de l'encyclopédie (voir l'en-tête du fichier). */
  function afficherEncyclopedie(conteneur) {
    const profil = profilCourant();
    const accueil = Wiki.accueilEncyclopedie({ profil });
    const briques = BRIQUES.filter((type) => Number.isInteger(accueil.nombres[TYPES[type].nombre]));
    App.definirTitre(I18n.t('wiki.fil.wiki'));
    UI.remplir(conteneur, UI.html`<div class="wiki wiki-accueil" data-profil="${profil}">
      <div class="wiki-bento${accueil.suivi ? '' : ' sans-suivi'}" id="wiki-accueil">
        ${tuileSynthese(accueil, profil)}
        ${accueil.suivi ? tuileSuivi(accueil.suivi) : ''}
        <section class="bento-tuile wiki-trouves" id="wiki-trouves" aria-live="polite" aria-label="${I18n.t('wiki.encyclopedie.resultats_recherche')}" hidden></section>
        <div class="wiki-briques" data-nombre="${briques.length}">${briques.map((type) => brique(type, accueil))}</div>
        ${tuileDernieres(accueil)}${tuilePannes(accueil)}
      </div>
    </div>`);
    brancherRecherche(conteneur, profil);
  }

  // ===========================================================================================
  // 3. Listes #/wiki/<liste>
  // ===========================================================================================

  function enteteListe(type, nombre, description) {
    return UI.html`<div class="entete-page wiki-entete-liste"><div>
      ${fil([UI.html`<span>${TYPES[type].pluriel}</span>`])}
      <p class="wiki-puce-ligne">${puce(type)}</p>
      <h1>${TYPES[type].pluriel}${nombre === null ? '' : UI.html` <span class="badge wiki-nombre">${nombre}</span>`}</h1>
      ${description ? UI.html`<p>${description}</p>` : ''}
    </div></div>`;
  }

  /** Cadre d'une liste : en-tête, puis `contenu` (fragment), dans .wiki-liste-entites[data-liste]. */
  function cadreListe(conteneur, type, nombre, contenu) {
    UI.remplir(conteneur, UI.html`<div class="wiki wiki-liste-entites" data-liste="${TYPES[type].liste}">
      ${enteteListe(type, nombre, description(type))}${contenu}</div>`);
    return UI.$('.wiki-liste-entites', conteneur);
  }

  function afficherReserve(conteneur, type) {
    UI.remplir(conteneur, UI.html`<div class="wiki wiki-liste-entites wiki-reserve" data-liste="${TYPES[type].liste}">
      ${enteteListe(type, null, '')}
      ${UI.vide(I18n.t('wiki.reserve.reserve_techniciens_responsable'), type === 'technicien'
        ? I18n.t('wiki.reserve.demandeur_voit_nom_techniciens') : I18n.t('wiki.reserve.demandeur_voit_numero_interventions'), 'utilisateur')}
      <p><a class="btn btn-secondaire" href="#/wiki">${I18n.t('wiki.reserve.retour_wiki')}</a></p>
    </div>`);
  }

  /** Lignes d'une machine puis de ses sous-ensembles (décalés selon leur profondeur). */
  function lignesMachine(machine, profondeur) {
    const pannes = machine.pannes.slice(0, 2).map((panne) => panne.libelle).join(', ');
    return [UI.html`<li class="${profondeur ? 'wiki-ligne enfant' : 'wiki-ligne'}" data-id="${machine.equipementId}" style="--profondeur: ${profondeur}">
      <span class="wiki-ligne-corps">${lienEntite(machine.lien, machine.titre)}
        ${machine.marqueModele || pannes ? UI.html`<span class="wiki-ligne-sous">${joindre([machine.marqueModele, pannes], ' · ')}</span>` : ''}</span>
      <span class="wiki-ligne-droite">${I18n.t('wiki.compte.interventions', { n: machine.interventions })}</span></li>`]
      .concat(machine.sousEnsembles.flatMap((enfant) => lignesMachine(enfant, profondeur + 1)));
  }

  /**
   * Titre d'un groupe de lieu : le chemin du lieu, sans sa racine quand tous les lieux partagent la même (le site,
   * « Site des Trois Vallées › Atelier Usinage » → « Atelier Usinage ») ; « Lieu non renseigné » sans lieu.
   */
  function titresDesLieux(groupes) {
    const chemins = groupes.map((groupe) => (groupe.lieu ? groupe.lieu.split(' › ') : []));
    const racine = chemins.length && chemins.every((chemin) => chemin.length > 1 && chemin[0] === chemins[0][0]) ? 1 : 0;
    return chemins.map((chemin) => (chemin.length ? chemin.slice(racine).join(' › ') : I18n.t('wiki.titres_des_lieux.lieu_non_renseigne')));
  }

  function rendreMachines(conteneur, groupes) {
    const compter = (machines) => machines.reduce((total, machine) => total + 1 + compter(machine.sousEnsembles), 0);
    const titres = titresDesLieux(groupes);
    cadreListe(conteneur, 'machine', groupes.reduce((total, groupe) => total + compter(groupe.machines), 0),
      groupes.length ? groupes.map((groupe, rang) => UI.html`<section class="wiki-groupe-lieu" data-lieu="${groupe.lieu}" aria-labelledby="wiki-lieu-${rang}">
        <h2 class="wiki-groupe-titre" id="wiki-lieu-${rang}" title="${groupe.lieu}">${titres[rang]}</h2>
        <ul class="bento-tuile wiki-lignes-entites wiki-tuile-lignes">${groupe.machines.map((machine) => lignesMachine(machine, 0))}</ul></section>`)
        : UI.vide(I18n.t('wiki.rendre_machines.aucune_machine_parc'), I18n.t('wiki.rendre_machines.chaque_equipement_cree_parc'), 'parc'));
  }

  function rendrePannes(conteneur, pannes) {
    cadreListe(conteneur, 'panne', pannes.length, pannes.length ? UI.html`<ul class="bento-tuile wiki-lignes-entites wiki-tuile-lignes">${pannes.map((panne) => UI.html`
      <li class="wiki-ligne" data-id="${panne.id}">${pastille('panne')}
        <span class="wiki-ligne-corps">${lienEntite(panne.lien, panne.titre)}
          <span class="wiki-ligne-sous">${joindre([I18n.t('wiki.rendre_pannes.machines_touchees', { n: panne.machines }),
            panne.cause ? I18n.t('wiki.rendre_pannes.cause_plus_frequente', { causeLibelle: panne.cause.libelle }) : '', panne.derniere ? I18n.t('wiki.rendre_pannes.dernier_cas', { derniere: UI.dateFr(panne.derniere) }) : ''], ' · ')}</span></span>
        <span class="wiki-ligne-droite">${I18n.t('wiki.compte.cas', { n: panne.cas })}</span></li>`)}</ul>`
      : UI.vide(I18n.t('wiki.rendre_pannes.aucune_panne_instant'), I18n.t('wiki.rendre_pannes.panne_page_des_intervention'), 'alerte'));
  }

  function carteArticle(article) {
    return UI.html`<li data-id="${article.articleId}"><a href="${adresse(article.lien)}">
      <div class="carte-tete"><b>${article.reference || article.articleId}</b>${etatStock(article)}</div>
      <div class="carte-titre">${article.titre}</div>
      <div class="carte-meta">${article.emplacement ? UI.html`<span>${I18n.t('wiki.carte_article.range_emplacement', { emplacement: article.emplacement })}</span>` : ''}
        <span>${I18n.t('wiki.compte.interventions', { n: article.interventions })}</span>${article.critique ? UI.html`<span>${I18n.t('wiki.carte_article.piece_critique')}</span>` : ''}</div>
    </a></li>`;
  }

  function rendreArticles(conteneur, articles) {
    const cadre = cadreListe(conteneur, 'article', articles.length, UI.html`
      <form class="filtres wiki-filtres" id="wiki-filtres-articles" data-hors-saisie role="search" aria-label="${I18n.t('wiki.rendre_articles.filtrer_articles')}">
        <label class="visuellement-cache" for="wiki-filtre-texte">${I18n.t('wiki.rendre_articles.filtrer_articles')}</label>
        <input type="search" id="wiki-filtre-texte" name="texte" placeholder="${UI.estTelephone() ? I18n.t('wiki.rendre_articles.designation_reference')
          : I18n.t('wiki.rendre_articles.designation_reference_emplacement')}" autocomplete="off">
        <label class="visuellement-cache" for="wiki-filtre-etat">${I18n.t('wiki.rendre_articles.etat_stock')}</label>
        <select id="wiki-filtre-etat" name="etat">${optionsEtat().map(([valeur, libelle]) => UI.html`<option value="${valeur}">${libelle}</option>`)}</select>
      </form>
      <p class="aide wiki-filtre-compte" role="status"></p>
      <div class="bento-tuile wiki-tuile-tableau" id="wiki-articles"></div>`);
    const formulaire = UI.$('#wiki-filtres-articles', cadre);
    const zone = UI.$('#wiki-articles', cadre);
    const compteur = UI.$('.wiki-filtre-compte', cadre);
    const cleDe = (article) => UI.normaliserRecherche([article.titre, article.reference, article.emplacement].join(' '));
    const tableau = UI.estTelephone() ? null : UI.tableau({
      libelle: I18n.t('wiki.rendre_articles.articles_magasin'), vide: I18n.t('wiki.rendre_articles.aucun_article_correspond_filtre'), lignes: articles,
      colonnes: [
        { cle: 'titre', libelle: I18n.t('commun.champ.article'), classe: 'wiki-cellule-titre',
          rendu: (article) => UI.html`${lienEntite(article.lien, article.titre)}${article.critique ? UI.html` <span class="badge attention">${I18n.t('wiki.rendre_articles.critique')}</span>` : ''}` },
        { cle: 'reference', libelle: I18n.t('commun.champ.reference') },
        { cle: 'emplacement', libelle: I18n.t('wiki.rendre_articles.emplacement') },
        { cle: 'stock', libelle: I18n.t('wiki.rendre_articles.stock'), type: 'nombre', rendu: etatStock },
        { cle: 'interventions', libelle: I18n.t('wiki.pluriel.interventions'), type: 'nombre' },
      ],
    });
    function rafraichir() {
      const valeurs = UI.lireFormulaire(formulaire);
      const mots = UI.normaliserRecherche(valeurs.texte).split(' ').filter(Boolean);
      const gardes = articles.filter((article) => (!valeurs.etat || article.etat === valeurs.etat)
        && mots.every((mot) => cleDe(article).includes(mot)));
      if (tableau) tableau.mettreAJour(gardes);
      else {
        UI.remplir(zone, gardes.length ? UI.html`<ul class="liste-cartes">${gardes.map(carteArticle)}</ul>`
          : UI.html`<p class="muted">${I18n.t('wiki.rendre_articles.aucun_article_correspond_filtre')}</p>`);
      }
      compteur.textContent = I18n.t('wiki.rendre_articles.n_articles_nb_articles', { n: gardes.length, nbArticles: articles.length });
    }
    if (tableau) zone.appendChild(tableau);
    formulaire.addEventListener('input', rafraichir);
    formulaire.addEventListener('change', rafraichir);
    formulaire.addEventListener('submit', (evenement) => evenement.preventDefault());
    rafraichir();
  }

  function rendreTechniciens(conteneur, techniciens) {
    cadreListe(conteneur, 'technicien', techniciens.length, techniciens.length ? UI.html`<ul class="wiki-cartes-techniciens">${techniciens.map((technicien) => UI.html`
      <li data-id="${technicien.technicienId}"><a class="bento-tuile wiki-carte-technicien" href="${adresse(technicien.lien)}">
        <span class="bento-pastille-icone wiki-t-technicien" aria-hidden="true">${UI.icone('utilisateur')}</span>
        <h2>${technicien.nom}</h2>
        <span class="wiki-ligne-sous">${joindre([technicien.metier, technicien.actif ? '' : I18n.t('wiki.rendre_techniciens.inactif')], ' · ')}</span>
        <span class="wiki-carte-chiffres">${joindre([I18n.t('wiki.compte.interventions', { n: technicien.interventions }),
          I18n.t('wiki.compte.habilitations', { n: technicien.habilitations }), I18n.t('wiki.rendre_techniciens.heures_pointees', { heures: UI.heures(technicien.heures) })], ' · ')}</span>
      </a></li>`)}</ul>`
      : UI.vide(I18n.t('wiki.rendre_techniciens.aucun_technicien'), I18n.t('wiki.rendre_techniciens.techniciens_equipe_ont_page'), 'utilisateur'));
  }

  function rendreSavoirFaire(conteneur, savoirFaire) {
    cadreListe(conteneur, 'savoir-faire', savoirFaire.length, savoirFaire.length ? UI.html`<ul class="bento-tuile wiki-lignes-entites wiki-tuile-lignes">${savoirFaire.map((page) => UI.html`
      <li class="wiki-ligne" data-id="${page.id}">${pastille('savoir-faire')}
        <span class="wiki-ligne-corps">${lienEntite(page.lien, page.titre)}
          <span class="wiki-ligne-sous">${joindre([page.rattachement ? UI.html`${page.rattachement.type === 'machine' ? I18n.t('wiki.libelle.machine') : I18n.t('wiki.libelle.article')} ${lienEntite(page.rattachement.lien, page.rattachement.titre)}` : I18n.t('wiki.rendre_savoir_faire.sans_rattachement'),
            page.mere ? I18n.html('wiki.rendre_savoir_faire.sous_page_de', { mere: lienEntite(page.mere.id, page.mere.titre) }) : ''], ' · ')}</span></span></li>`)}</ul>`
      : UI.vide(I18n.t('wiki.rendre_savoir_faire.aucun_savoir_faire_instant'), I18n.t('wiki.rendre_savoir_faire.ils_naissent_astuces_interventions'), 'cle'));
  }

  function carteIntervention(ot) {
    return UI.html`<li class="wiki-carte-intervention" data-id="${ot.id}"><a href="${adresse(ot.lien)}">
      <div class="carte-tete"><b>${ot.id}</b>${UI.badgeValeur('ordres_travail', 'statut', ot.statut)}</div>
      <div class="carte-titre">${ot.titre}</div>
      <div class="carte-meta"><span>${UI.dateFr(ot.date)}</span>${ot.machine ? UI.html`<span>${repere(ot.machine)}</span>` : ''}${ot.panne ? UI.html`<span>${ot.panne.libelle}</span>` : ''}</div>
    </a></li>`;
  }

  /**
   * Tableau triable d'une longue liste, posé dans `zone` (précisions en tête) : le tri ordonne toutes les `lignes`, puis
   * seules les `montres` premières sont créées, les autres au clic sur « Voir les n autres <nom> » (les tris suivants
   * les gardent). reglages : { libelle, vide, nom, montres, lignes, colonnes : [{ cle, libelle, classe, type ('nombre'),
   * valeurTri (ligne → valeur ; sinon ligne[cle]), rendu (ligne → texte ou fragment UI.html ; sinon ligne[cle]) }] }.
   */
  function tableauParMorceaux(zone, reglages) {
    const colonnes = reglages.colonnes;
    let lignes = reglages.lignes.slice();
    let tri = null;                                    // { cle, sens: 'asc' | 'desc' }, comme UI.tableau
    let toutes = lignes.length <= reglages.montres;
    const cadre = UI.element(UI.html`<div class="table-defile"><table class="table">
      <caption class="visuellement-cache">${reglages.libelle}</caption>
      <thead><tr>${colonnes.map((colonne) => UI.html`<th scope="col" class="${colonne.type === 'nombre' ? 'num' : ''}"><button type="button"
        class="tri" data-cle="${colonne.cle}">${colonne.libelle}<span class="sens" aria-hidden="true"></span></button></th>`)}</tr></thead>
      <tbody></tbody></table></div>`);
    const corps = UI.$('tbody', cadre);
    const rangee = (ligne) => UI.html`<tr>${colonnes.map((colonne) => UI.html`<td class="${[colonne.type === 'nombre' ? 'num' : '',
      colonne.classe || ''].filter(Boolean).join(' ')}">${typeof colonne.rendu === 'function' ? colonne.rendu(ligne) : ligne[colonne.cle]}</td>`)}</tr>`;
    const estVide = (valeur) => valeur === null || valeur === undefined || valeur === '';

    /** Tri stable de toute la liste sur la colonne de `tri` ; les cellules vides en fin, dans les deux sens. */
    function trier() {
      const colonne = colonnes.find((c) => c.cle === tri.cle);
      const valeurDe = (ligne) => (typeof colonne.valeurTri === 'function' ? colonne.valeurTri(ligne) : ligne[colonne.cle]);
      const sens = tri.sens === 'desc' ? -1 : 1;
      lignes = lignes.map((ligne, rang) => ({ ligne, rang, valeur: valeurDe(ligne) })).sort((a, b) => {
        if (estVide(a.valeur) || estVide(b.valeur)) return (estVide(a.valeur) === estVide(b.valeur) ? 0 : (estVide(a.valeur) ? 1 : -1)) || a.rang - b.rang;
        const ecart = colonne.type === 'nombre' ? Number(a.valeur) - Number(b.valeur) : ORDRE_FRANCAIS.compare(String(a.valeur), String(b.valeur));
        return sens * ecart || a.rang - b.rang;
      }).map((entree) => entree.ligne);
    }

    function afficher() {
      corps.textContent = '';
      if (!lignes.length) {
        UI.remplir(corps, UI.html`<tr><td class="vide-table" colspan="${colonnes.length}">${reglages.vide}</td></tr>`);
      } else {
        ajouterA(corps, (toutes ? lignes : lignes.slice(0, reglages.montres)).map(rangee));
      }
      UI.$$('thead th', cadre).forEach((cellule) => {
        if (tri && UI.$('.tri', cellule).dataset.cle === tri.cle) cellule.setAttribute('aria-sort', tri.sens === 'desc' ? 'descending' : 'ascending');
        else cellule.removeAttribute('aria-sort');
      });
    }

    UI.$$('thead .tri', cadre).forEach((bouton) => bouton.addEventListener('click', () => {
      const cle = bouton.dataset.cle;
      tri = tri && tri.cle === cle ? { cle, sens: tri.sens === 'asc' ? 'desc' : 'asc' } : { cle, sens: 'asc' };
      trier();
      afficher();
    }));
    afficher();
    zone.appendChild(cadre);
    if (!toutes) zone.appendChild(UI.element(boutonAutres(lignes.length - reglages.montres, reglages.nom)));
    brancherSuite(zone, () => {
      toutes = true;
      return ajouterA(corps, lignes.slice(reglages.montres).map(rangee));
    });
  }

  /** Liste des interventions : LIGNES_MONTREES lignes (PC) ou CARTES_MONTREES cartes (téléphone), les autres au clic (D101). */
  function rendreInterventions(conteneur, interventions) {
    const cadre = cadreListe(conteneur, 'intervention', interventions.length, UI.html`<div class="bento-tuile wiki-tuile-tableau" id="wiki-interventions"></div>`);
    const zone = UI.$('#wiki-interventions', cadre);
    if (!UI.estTelephone()) {
      tableauParMorceaux(zone, {
        libelle: I18n.t('wiki.pluriel.interventions'), vide: I18n.t('wiki.rendre_interventions.aucune_intervention'), nom: 'interventions', montres: LIGNES_MONTREES, lignes: interventions,
        colonnes: [
          { cle: 'date', libelle: I18n.t('commun.champ.date'), rendu: (ot) => UI.dateFr(ot.date) },
          { cle: 'id', libelle: 'N°', classe: 'sans-coupure', rendu: (ot) => lienEntite(ot.lien, ot.id) },
          { cle: 'titre', libelle: I18n.t('wiki.libelle.intervention'), classe: 'wiki-cellule-titre' },
          { cle: 'statut', libelle: I18n.t('commun.champ.statut'), rendu: (ot) => UI.badgeValeur('ordres_travail', 'statut', ot.statut) },
          { cle: 'machine', libelle: I18n.t('wiki.libelle.machine'), valeurTri: (ot) => repere(ot.machine), rendu: (ot) => lienMachine(ot.machine) },
          { cle: 'panne', libelle: I18n.t('wiki.libelle.panne'), valeurTri: (ot) => (ot.panne ? ot.panne.libelle : ''),
            rendu: (ot) => (ot.panne ? lienEntite(ot.panne.lien, ot.panne.libelle) : '') },
          { cle: 'techniciens', libelle: I18n.t('commun.champ.technicien'), valeurTri: (ot) => ot.techniciens.map((t) => t.nom).join(', '),
            rendu: (ot) => UI.html`${joindre(ot.techniciens.map((t) => lienEntite(t.lien, t.nom)), ', ')}` },
        ],
      });
      return;
    }
    UI.remplir(zone, interventions.length ? UI.html`<ul class="liste-cartes">${interventions.slice(0, CARTES_MONTREES).map(carteIntervention)}</ul>
      ${boutonAutres(interventions.length - CARTES_MONTREES, 'interventions')}` : UI.html`<p class="muted">${I18n.t('wiki.rendre_interventions.aucune_intervention')}</p>`);
    brancherSuite(zone, () => ajouterA(UI.$('.liste-cartes', zone), interventions.slice(CARTES_MONTREES).map(carteIntervention)));
  }

  const RENDUS = { machine: rendreMachines, panne: rendrePannes, article: rendreArticles, technicien: rendreTechniciens,
    'savoir-faire': rendreSavoirFaire, intervention: rendreInterventions };
  // Listes montrées dans l'ordre alphabétique français (les autres gardent l'ordre de Wiki.listeEntites).
  const NOMS_TRIES = { article: (article) => article.titre, technicien: (technicien) => technicien.nom, 'savoir-faire': (page) => page.titre };

  /** Écran #/wiki/<liste> : la liste d'un type, ou « réservé » quand le profil ne la voit pas (D114). */
  function afficherListeEntites(conteneur, liste) {
    const type = TYPE_DE_LISTE[liste];
    App.definirTitre(I18n.t('wiki.liste_entites.titre', { liste: TYPES[type].pluriel }));
    const donnees = Wiki.listeEntites(type, { profil: profilCourant() });
    if (!donnees) afficherReserve(conteneur, type);
    else RENDUS[type](conteneur, NOMS_TRIES[type] ? enFrancais(donnees, NOMS_TRIES[type]) : donnees);
  }

  // Outils prêtés aux pages d'une entité (wiki-page-ecrans.js, wiki-sections-ecrans.js), lus à l'appel.
  const outilsEcrans = { TYPES, adresse, joindre, libelleEtatStock, lienEntite, lienMachine, repere, pastille, puce, fil,
    boutonAutres, brancherSuite, ajouterA };

  return { afficherEncyclopedie, afficherListeEntites, outilsEcrans };
})());
