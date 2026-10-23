'use strict';
// Wiki (7/8) — écrans de lecture du wiki de maintenance (lot 6 refondu, ARCHITECTURE.md §20.9 ; tâche T119), pour
// les trois profils : #/wiki (compteurs du responsable, recherche sur tout le parc, pages par type) et la route
// #/wiki/<id> (Wiki.page, puis le rendu de wiki-page-ecrans.js, chargé juste après ce fichier : en-tête, pour un
// savoir-faire l'en-tête posé par Prévo — consignation et « Ce savoir-faire ne remplace pas la consignation de
// l'équipement » —, couche calculée, texte et origine, « À trancher », « Pages qui renvoient ici », propositions en
// attente) ; champ de recherche réutilisable (Wiki.champRecherche, posé dans l'onglet Préparation de l'OT ;
// Wiki.poserRechercheDemande, dans la saisie d'une DI) ; enregistrement des écrans auprès d'App.
//
// Lecture seule, sauf le rattrapage du journal (Wiki.rattraper, §20.7) au responsable avant d'afficher ; aucun
// appel réseau. Toute donnée insérée passe par UI.html (échappement). Le demandeur n'a accès ni aux écrans des OT
// ni au magasin : il voit les numéros d'OT en texte, sans lien.
//
// Précisions au contrat (§20.9) :
//  - index : une page par équipement et par article (pages calculées, toujours présentes), plus les pages actives
//    de wiki_pages (composants libres, modes, savoir-faire, et les sous-pages dans la section de leur type, comptées
//    comme une page de plus) ; dans chaque section, les pages qui ont un texte
//    validé d'abord, puis par titre (ordre alphabétique français) et identifiant ; nombre d'OT cités = citations
//    distinctes du texte validé ; PAGES_MONTREES premières, le reste derrière « Tout afficher » ;
//  - compteurs du responsable (Wiki.compteurs) : « À valider » = entrées « à valider » ; « Contradictions
//    ouvertes » = contradictions « ouverte » des entrées « validée » ; « En file » = Wiki.file() ; « En échec » =
//    OT distincts dont une entrée d'ingestion « refusée » n'est suivie d'aucune entrée plus récente (numéro WJ
//    plus grand) en file, à refaire, à valider, validée ou rien à ajouter ; « Hors du wiki » = Wiki.horsDuWiki() ;
//    « Contrôle du wiki » = Wiki.controleDuWiki().length quand la fonction existe (sinon pas de nombre) ; chacun
//    mène à #/wiki-journal?vue=<a-valider | contradictions | file | echecs | hors | controle> ;
//  - « Déjà vu sur cette machine ? » (saisie d'une DI) : les liens des résultats s'ouvrent dans un nouvel onglet,
//    pour ne jamais faire perdre la demande en cours.

Object.assign(Wiki, (() => {

  // Tables lues par les écrans : réaffichés si l'une change sur un autre poste.
  const TABLES = ['equipements', 'ordres_travail', 'demandes', 'codes_defaillance', 'mouvements_stock',
    'articles', 'article_equipement', 'wiki_pages', 'wiki_journal'];
  const PROFILS = ['demandeur', 'technicien', 'responsable'];

  const DELAI_RECHERCHE_MS = 300;                       // la recherche part après 300 ms sans frappe
  const RESULTATS_MONTRES = 5;                          // par portée, avant « Voir les n autres résultats »
  const RESULTATS_MONTRES_DEMANDE = 3;                  // saisie d'une DI (téléphone) : formulaire plus court
  const PAGES_MONTREES = 24;                            // par section de l'index, avant « Tout afficher »
  const TITRE_RECHERCHE_DEMANDE = 'Déjà vu sur cette machine ?';
  const NOUVEL_ONGLET = 's\'ouvre dans un nouvel onglet';

  const SECTIONS = [
    { type: 'équipement', cle: 'equipement', libelle: 'Équipements', vide: 'Aucun équipement dans le parc.' },
    { type: 'composant', cle: 'composant', libelle: 'Composants', vide: 'Aucun article au magasin ni page de composant.' },
    { type: 'mode', cle: 'mode', libelle: 'Modes de défaillance',
      vide: 'Aucune page pour l\'instant : elles naissent des OT intégrés au wiki ou d\'une écriture à la main.' },
    { type: 'savoir-faire', cle: 'savoir-faire', libelle: 'Savoir-faire',
      vide: 'Aucune page pour l\'instant : elles naissent surtout des astuces des OT intégrés au wiki.' },
  ];

  const COMPTEURS = [
    { vue: 'a-valider', champ: 'aValider', libelle: 'À valider', comp: 'propositions de l\'IA' },
    { vue: 'contradictions', champ: 'contradictions', libelle: 'Contradictions ouvertes', comp: 'à trancher' },
    { vue: 'file', champ: 'file', libelle: 'En file', comp: 'OT à intégrer', bouton: 'Traiter la file' },
    { vue: 'echecs', champ: 'echecs', libelle: 'En échec', comp: 'OT refusés au contrôle' },
    { vue: 'hors', champ: 'hors', libelle: 'Hors du wiki', comp: 'OT clôturés jamais mis en file', bouton: 'Ajouter à la file' },
    { vue: 'controle', champ: 'controle', libelle: 'Contrôle du wiki', comp: 'liens, pages, titres' },
  ];

  // ===========================================================================================
  // 1. Petits outils
  // ===========================================================================================

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  function json(valeur) {
    try { return JSON.parse(valeur) || []; } catch (erreur) { return []; }
  }

  function comparer(a, b) {
    return a < b ? -1 : (a > b ? 1 : 0);
  }

  // Ordre alphabétique français des titres de l'index (« Électrovanne » avec les E), comme les listes de Prévo.
  const ORDRE_FRANCAIS = new Intl.Collator('fr', { numeric: true, sensitivity: 'base' });

  /** Le demandeur n'a accès ni aux OT ni au magasin (profils de leurs routes) : pas de lien pour lui. */
  function avecLiens() {
    return App.estTechnicien() || App.estResponsable();
  }

  /** Attributs d'un lien qui s'ouvre dans un nouvel onglet (titre : `libelle` et la mention). */
  function attributsOnglet(nouvelOnglet, libelle) {
    return nouvelOnglet ? UI.html` target="_blank" rel="noopener" title="${libelle} (${NOUVEL_ONGLET})"` : '';
  }

  function lienOt(otId, liens, nouvelOnglet) {
    return liens ? UI.html`<a class="wiki-lien-ot" href="#/ot/${encodeURIComponent(otId)}"${attributsOnglet(nouvelOnglet, otId)}>${otId}</a>`
      : UI.html`<b class="wiki-numero-ot">${otId}</b>`;
  }

  function nombreOt(nombre) {
    if (!nombre) return 'Aucun OT cité';
    return nombre + (nombre > 1 ? ' OT cités' : ' OT cité');
  }

  /** Rattrapage du journal (§20.7) au responsable avant d'afficher ; une erreur n'empêche pas l'affichage. */
  async function rattraper() {
    if (!App.estResponsable() || typeof Wiki.rattraper !== 'function') return;
    try {
      await Wiki.rattraper();
    } catch (erreur) {
      console.warn('Prévo (wiki) : rattrapage du journal impossible (' + (erreur && erreur.message) + ').', erreur);
    }
  }

  // ===========================================================================================
  // 2. Champ de recherche réutilisable (§20.8)
  // ===========================================================================================

  const recherchesPosees = new WeakMap();      // élément du champ → { champ, chercherPlusTard, repris }
  const symptomesSuivis = new WeakSet();       // champs « symptôme » des DI déjà écoutés

  /**
   * Un résultat : OT (numéro en lien ou en texte selon le profil, puis son titre) ou page du wiki (son titre en
   * lien vers #/wiki/<lien>, pour tous les profils : le wiki est ouvert au demandeur). `nouvelOnglet` : liens
   * ouverts dans un nouvel onglet (saisie d'une DI).
   */
  function resultatHtml(resultat, portee, reglages, cache) {
    const estOt = resultat.type === 'ot';
    const tete = estOt ? lienOt(resultat.otId, reglages.liens, reglages.nouvelOnglet)
      : UI.html`<a class="wiki-lien-page" href="#/wiki/${encodeURIComponent(resultat.lien)}"${attributsOnglet(reglages.nouvelOnglet, resultat.titre)}>${resultat.titre}</a><span class="badge info">Page du wiki</span>`;
    const repere = portee !== 'equipement' && resultat.repere ? UI.html`<span class="badge neutre">${resultat.repere}</span>` : '';
    const codes = [resultat.cause ? UI.html`<span>Cause : ${resultat.cause}</span>` : '',
      resultat.remede ? UI.html`<span>Remède : ${resultat.remede}</span>` : ''];
    return UI.html`<li class="wiki-trouve" data-type="${resultat.type}" data-id="${estOt ? resultat.otId : resultat.pageId}"${cache ? UI.brut(' hidden') : ''}>
      <div class="wiki-ligne-tete">${tete}${repere}${resultat.date ? UI.html`<span class="wiki-date">${UI.dateFr(resultat.date)}</span>` : ''}</div>
      ${estOt ? UI.html`<div class="carte-titre">${resultat.titre}</div>` : ''}
      ${resultat.cause || resultat.remede ? UI.html`<div class="carte-meta">${codes}</div>` : ''}
      ${resultat.extrait ? UI.html`<p class="wiki-extrait">${Wiki.surligner(resultat.extrait, resultat.mots)}</p>` : ''}
    </li>`;
  }

  /** Une portée (« Sur cet équipement »…) : ses `montres` premiers résultats, le reste derrière un bouton. */
  function blocPortee(portee, reglages) {
    const montres = reglages.montres;
    const reste = portee.resultats.length - montres;
    const texteBouton = reste > 1 ? 'Voir les ' + reste + ' autres résultats' : 'Voir l\'autre résultat';
    const bloc = UI.element(UI.html`<div class="wiki-portee" data-portee="${portee.portee}">
      <h3>${portee.libelle} <span class="badge">${portee.resultats.length}</span></h3>
      <ul class="wiki-lignes">${portee.resultats.map((resultat, rang) => resultatHtml(resultat, portee.portee, reglages, rang >= montres))}</ul>
      ${reste > 0 ? UI.html`<button type="button" class="btn btn-fantome wiki-voir-plus" aria-expanded="false">${texteBouton}</button>` : ''}
    </div>`);
    const bouton = UI.$('.wiki-voir-plus', bloc);
    if (bouton) {
      bouton.addEventListener('click', () => {
        const ouvrir = bouton.getAttribute('aria-expanded') !== 'true';
        UI.$$('.wiki-trouve', bloc).forEach((ligne, rang) => { ligne.hidden = !ouvrir && rang >= montres; });
        bouton.setAttribute('aria-expanded', String(ouvrir));
        bouton.textContent = ouvrir ? 'Montrer moins de résultats' : texteBouton;
      });
    }
    return bloc;
  }

  function afficherResultats(zone, resultat, reglages) {
    if (!resultat.requete) {
      zone.textContent = '';
      return;
    }
    const portees = resultat.portees.filter((portee) => portee.resultats.length);
    if (!portees.length) {
      UI.remplir(zone, UI.html`<p class="wiki-rien"><b>Rien trouvé pour « ${resultat.requete} ».</b></p>
        <p class="aide">Essayez un autre mot : fuite, bruit, chauffe, ne démarre pas…</p>`);
      return;
    }
    const complet = Object.assign({ liens: avecLiens() }, reglages);
    UI.remplir(zone, portees.map((portee) => blocPortee(portee, complet)));
  }

  /**
   * Texte de départ d'une recherche limitée à un équipement : son repère (souvent en tête d'un titre d'OT,
   * « PO-02 — Fuite… ») est retiré, avec les tirets et deux-points qui le suivent ; sinon « po » et « 02 »
   * seraient cherchés partout.
   */
  function sansRepere(valeur, equipementId) {
    const equipement = equipementId ? Donnees.trouver('equipements', equipementId) : null;
    const repere = texte(equipement && equipement.repere);
    if (!repere) return texte(valeur);
    return texte(valeur).split(repere).join(' ').replace(/^[\s—–:-]+/, '').replace(/\s+/g, ' ').trim();
  }

  /** Construit le champ et sa zone de résultats → { element, champ, chercherPlusTard }. */
  function creerChamp(options) {
    const reglages = options || {};
    const equipementId = texte(reglages.equipementId);
    const titre = texte(reglages.titre) || 'Chercher dans l\'historique';
    const montres = Number.isInteger(reglages.montres) && reglages.montres > 0 ? reglages.montres : RESULTATS_MONTRES;
    const affichage = { montres, nouvelOnglet: Boolean(reglages.nouvelOnglet) };
    const id = UI.identifiantUnique('wiki-recherche');
    const aide = equipementId
      ? 'Dans les interventions clôturées et les pages du wiki : cet équipement d\'abord, puis ceux de même marque et modèle, puis le reste du parc.'
      : 'Dans les interventions clôturées et les pages du wiki, sur tout le parc.';
    const element = UI.element(UI.html`
      <section class="carte wiki-recherche" data-hors-saisie role="search" aria-label="${titre}" data-equipement="${equipementId}">
        <label class="wiki-recherche-titre" for="${id}">${UI.icone('recherche')}<span>${titre}</span></label>
        <input type="search" id="${id}" class="wiki-recherche-champ" data-hors-saisie maxlength="200" autocomplete="off"
          enterkeyhint="search" placeholder="Ex. fuite, bruit, ne démarre pas" value="${sansRepere(reglages.texteInitial, equipementId)}">
        <p class="aide wiki-recherche-aide">${aide}</p>
        <div class="wiki-resultats" aria-live="polite"></div>
      </section>`);
    const champ = UI.$('.wiki-recherche-champ', element);
    const zone = UI.$('.wiki-resultats', element);
    let minuterie = null;

    function chercher() {
      clearTimeout(minuterie);
      minuterie = null;
      try {
        afficherResultats(zone, Wiki.rechercher(champ.value, { equipementId }), affichage);
      } catch (erreur) {
        UI.remplir(zone, UI.html`<p class="erreur">Recherche impossible : ${(erreur && erreur.message) || ''}</p>`);
        console.warn('Prévo (wiki) : recherche impossible (' + (erreur && erreur.message) + ').', erreur);
      }
    }
    // Après DELAI_RECHERCHE_MS sans frappe ; rien si le champ n'est plus affiché (écran quitté).
    function chercherPlusTard() {
      clearTimeout(minuterie);
      minuterie = setTimeout(() => { if (element.isConnected) chercher(); }, DELAI_RECHERCHE_MS);
    }
    champ.addEventListener('input', chercherPlusTard);
    champ.addEventListener('keydown', (evenement) => {
      if (evenement.key !== 'Enter') return;
      evenement.preventDefault();            // jamais l'envoi du formulaire qui contient le champ (DI)
      chercher();
    });
    if (champ.value) chercherPlusTard();      // pré-rempli (titre de l'OT, symptôme) : résultats tout de suite
    return { element, champ, chercherPlusTard };
  }

  /**
   * Champ de recherche réutilisable : Wiki.champRecherche({ equipementId, texteInitial, titre, montres }) →
   * élément <section> (carte) à poser dans l'écran. Sans équipement : tout le parc ; avec : portées équipement,
   * même marque et modèle, parc. Champ type="search" [data-hors-saisie] (ce n'est pas une saisie en cours) ;
   * `montres` : résultats montrés par portée avant « Voir les n autres résultats » (5 par défaut).
   */
  function champRecherche(options) {
    return creerChamp(options).element;
  }

  // Le champ « Déjà vu sur cette machine ? » reprend le symptôme tant qu'on n'y a pas tapé autre chose.
  function suivreSymptome(champSymptome) {
    const etape = champSymptome.closest('section');
    const bloc = etape ? UI.$('.wiki-recherche-demande', etape) : null;
    const recherche = bloc ? recherchesPosees.get(bloc) : null;
    if (!recherche || recherche.champ.value !== recherche.repris) return;
    recherche.repris = texte(champSymptome.value);
    recherche.champ.value = recherche.repris;
    recherche.chercherPlusTard();
  }

  /**
   * Saisie d'une DI : une fois l'équipement choisi, le champ « Déjà vu sur cette machine ? », pré-rempli avec
   * le symptôme saisi, sous le symptôme (dans sa <section>). À rappeler à chaque choix d'équipement : sans
   * équipement, le champ est retiré ; avec un autre, il est refait. Ses liens s'ouvrent dans un nouvel onglet
   * (la demande en cours n'est jamais perdue).
   */
  function poserRechercheDemande(champSymptome, equipementId) {
    const etape = champSymptome ? champSymptome.closest('section') : null;
    if (!etape) return null;
    const id = texte(equipementId);
    const actuel = UI.$('.wiki-recherche-demande', etape);
    if (actuel && actuel.dataset.equipement === id) return actuel;
    if (actuel) actuel.remove();
    if (!id) return null;
    const recherche = creerChamp({ equipementId: id, texteInitial: champSymptome.value, titre: TITRE_RECHERCHE_DEMANDE,
      montres: RESULTATS_MONTRES_DEMANDE, nouvelOnglet: true });
    recherche.element.classList.replace('carte', 'wiki-recherche-demande');
    recherche.repris = recherche.champ.value;
    recherchesPosees.set(recherche.element, recherche);
    etape.appendChild(recherche.element);
    if (!symptomesSuivis.has(champSymptome)) {
      symptomesSuivis.add(champSymptome);
      champSymptome.addEventListener('input', () => suivreSymptome(champSymptome));
    }
    return recherche.element;
  }

  // ===========================================================================================
  // 3. Pages par type et compteurs (index)
  // ===========================================================================================

  function titreEquipement(ligne) {
    return [texte(ligne.repere), texte(ligne.designation)].filter(Boolean).join(' — ');
  }

  // Même règle que Wiki.catalogue (wiki-calculs.js) : désignation, sinon référence, sinon identifiant.
  function titreArticle(ligne) {
    return texte(ligne.designation) || texte(ligne.reference) || texte(ligne.id);
  }

  /**
   * Entrée canonique d'une ligne active de wiki_pages, même règle que Wiki.page : une page d'équipement ou de
   * composant dont l'ancrage existe a l'identifiant et le titre de son équipement ou de son article.
   */
  function entreeDeLigne(ligne) {
    const type = texte(ligne.type);
    const equipement = type === 'équipement' && texte(ligne.equipement_id) ? Donnees.trouver('equipements', texte(ligne.equipement_id)) : null;
    if (equipement) return { id: texte(equipement.id), type, titre: titreEquipement(equipement) };
    const article = type === 'composant' && texte(ligne.article_id) ? Donnees.trouver('articles', texte(ligne.article_id)) : null;
    if (article) return { id: texte(article.id), type, titre: titreArticle(article) };
    return { id: texte(ligne.id), type, titre: texte(ligne.titre) };
  }

  /**
   * Pages du wiki par type (§20.9) → [{ type, cle, libelle, vide, pages: [{ id, titre, type, ot, avecTexte }] }] :
   * chaque équipement, chaque article, puis les pages actives de wiki_pages ; avec un texte d'abord, puis par titre.
   */
  function indexDesPages() {
    const parType = new Map(SECTIONS.map((section) => [section.type, new Map()]));
    Donnees.lignes('equipements').forEach((ligne) => parType.get('équipement').set(texte(ligne.id),
      { id: texte(ligne.id), titre: titreEquipement(ligne), type: 'équipement', ot: 0, avecTexte: false }));
    Donnees.lignes('articles').forEach((ligne) => parType.get('composant').set(texte(ligne.id),
      { id: texte(ligne.id), titre: titreArticle(ligne), type: 'composant', ot: 0, avecTexte: false }));
    Donnees.lignes('wiki_pages').filter((ligne) => texte(ligne.statut) !== 'archivée').forEach((ligne) => {
      const entree = entreeDeLigne(ligne);
      const pages = parType.get(entree.type);
      if (!pages || !entree.id) return;                         // type inconnu : signalé par Donnees.problemes()
      const page = pages.get(entree.id) || { id: entree.id, titre: entree.titre, type: entree.type, ot: 0, avecTexte: false };
      if (texte(ligne.texte)) Object.assign(page, { avecTexte: true, ot: Wiki.citations(ligne.texte).length });
      pages.set(entree.id, page);
    });
    return SECTIONS.map((section) => Object.assign({}, section, {
      pages: Array.from(parType.get(section.type).values()).sort((a, b) => Number(b.avecTexte) - Number(a.avecTexte)
        || ORDRE_FRANCAIS.compare(a.titre, b.titre) || comparer(a.id, b.id)),
    }));
  }

  /** Numéro d'une entrée du journal (WJ-00012 → 12), pour dire laquelle est la plus récente. */
  function rangJournal(entree) {
    return Number(texte(entree.id).replace(/\D/g, '')) || 0;
  }

  /** Compteurs du responsable (voir les précisions en tête) → { aValider, contradictions, file, echecs, hors, controle }. */
  function compteurs() {
    const journal = Donnees.lignes('wiki_journal');
    const contradictions = journal.filter((entree) => texte(entree.statut) === 'validée')
      .reduce((total, entree) => total + json(entree.contradictions)
        .filter((contradiction) => contradiction && texte(contradiction.statut) === 'ouverte').length, 0);
    const ingestions = journal.filter((entree) => texte(entree.nature) === 'ingestion' && texte(entree.ot_id));
    // « En échec » = la vue où mène le compteur (wiki-journal-ecrans.js) : OT sans autre entrée que rejetée ou refusée,
    // dont la dernière entrée est « refusée ».
    const echoue = (entree) => ['rejetée', 'refusée'].includes(texte(entree.statut));
    const vivants = new Set(ingestions.filter((entree) => !echoue(entree)).map((entree) => texte(entree.ot_id)));
    const dernieres = new Map();
    ingestions.filter((entree) => echoue(entree) && !vivants.has(texte(entree.ot_id))).forEach((entree) => {
      const avant = dernieres.get(texte(entree.ot_id));
      if (!avant || rangJournal(avant) < rangJournal(entree)) dernieres.set(texte(entree.ot_id), entree);
    });
    const echecs = Array.from(dernieres.values()).filter((entree) => texte(entree.statut) === 'refusée');
    let controle = null;
    if (typeof Wiki.controleDuWiki === 'function') {
      const resultat = Wiki.controleDuWiki();
      controle = resultat && Number.isInteger(resultat.length) ? resultat.length : null;
    }
    return {
      aValider: journal.filter((entree) => texte(entree.statut) === 'à valider').length,
      contradictions, file: Wiki.file().length, echecs: echecs.length, hors: Wiki.horsDuWiki().length, controle,
    };
  }

  // ===========================================================================================
  // 4. Écran #/wiki : compteurs du responsable, recherche, pages par type
  // ===========================================================================================

  function blocCompteurs(valeurs) {
    return UI.html`<section class="carte wiki-suivi" id="wiki-suivi" aria-labelledby="wiki-titre-suivi">
      <h2 id="wiki-titre-suivi">Suivi du wiki</h2>
      <div class="instruments wiki-compteurs">${COMPTEURS.map((compteur) => {
        const adresse = '#/wiki-journal?vue=' + compteur.vue;
        const nombre = valeurs[compteur.champ];
        return UI.html`<div class="wiki-compteur" data-compteur="${compteur.vue}">
          <a class="wiki-compteur-lien" href="${adresse}"><span class="lib">${compteur.libelle}</span>
            ${nombre === null ? '' : UI.html`<span class="chiffre">${nombre}</span>`}<span class="comp">${compteur.comp}</span></a>
          ${compteur.bouton ? UI.html`<a class="btn btn-secondaire wiki-compteur-action" href="${adresse}">${compteur.bouton}</a>` : ''}
        </div>`;
      })}</div>
    </section>`;
  }

  function ligneIndexHtml(page) {
    return UI.html`<li data-id="${page.id}" data-texte="${page.avecTexte ? 'oui' : 'non'}">
      <a href="#/wiki/${encodeURIComponent(page.id)}"><span class="wiki-index-titre">${page.titre || page.id}</span>
        <span class="wiki-index-ot">${nombreOt(page.ot)}</span></a></li>`;
  }

  function sectionIndex(section) {
    const element = UI.element(UI.html`<section class="carte wiki-index-section" id="wiki-section-${section.cle}"
        data-type="${section.type}" aria-labelledby="wiki-titre-${section.cle}">
      <h2 id="wiki-titre-${section.cle}">${section.libelle} <span class="badge wiki-nombre">${section.pages.length}</span></h2>
      ${section.pages.length ? UI.html`<ul class="wiki-index-liste"></ul>` : UI.html`<p class="muted wiki-index-vide">${section.vide}</p>`}
    </section>`);
    const liste = UI.$('.wiki-index-liste', element);
    if (!liste) return element;
    UI.remplir(liste, section.pages.slice(0, PAGES_MONTREES).map(ligneIndexHtml));
    if (section.pages.length > PAGES_MONTREES) {
      const bouton = UI.element(UI.html`<button type="button" class="btn btn-secondaire wiki-tout-afficher">Tout afficher (${section.pages.length})</button>`);
      bouton.addEventListener('click', () => {
        UI.remplir(liste, section.pages.map(ligneIndexHtml));
        bouton.remove();
        const suivant = liste.children[PAGES_MONTREES] && UI.$('a', liste.children[PAGES_MONTREES]);
        if (suivant) suivant.focus();
      });
      element.appendChild(bouton);
    }
    return element;
  }

  async function afficherIndex(conteneur) {
    const responsable = App.estResponsable();
    const route = location.hash;
    await rattraper();
    if (location.hash !== route) return;          // parti ailleurs pendant le rattrapage : on n'écrase pas l'écran suivant
    App.definirTitre('Wiki');
    UI.remplir(conteneur, UI.html`
      <div class="wiki wiki-liste">
        <div class="entete-page"><div>
          <h1>Wiki de maintenance</h1>
          <p>Ce que l'atelier sait de ses équipements, composants, modes de défaillance et savoir-faire : ce que Prévo
            calcule à partir des OT, et ce que l'atelier en a retenu.</p>
        </div></div>
        ${responsable ? blocCompteurs(compteurs()) : ''}
        <div class="wiki-zone-recherche"></div>
        <div class="wiki-zone-sections"></div>
      </div>`);
    UI.$('.wiki-zone-recherche', conteneur).replaceWith(champRecherche({ titre: 'Chercher dans le wiki et l\'historique du parc' }));
    UI.$('.wiki-zone-sections', conteneur).replaceWith(...indexDesPages().map(sectionIndex));
  }

  // ===========================================================================================
  // 5. Écran #/wiki/<id> : Wiki.page, puis le rendu de wiki-page-ecrans.js
  // ===========================================================================================

  function afficherIntrouvable(conteneur, id) {
    App.definirTitre('Page introuvable');
    UI.remplir(conteneur, UI.html`<div class="wiki wiki-page wiki-introuvable">
      <div class="entete-page"><div>
        <div class="fil"><a href="#/wiki">Wiki</a></div>
        <h1>Page introuvable</h1>
      </div></div>
      ${UI.vide('Aucune page du wiki ne porte l\'identifiant « ' + id + ' »',
        'Elle a peut-être été archivée ou saisie sur un autre poste. L\'index du wiki montre les pages connues.', 'wiki')}
      <p><a class="btn btn-secondaire" href="#/wiki">Retour au wiki</a></p>
    </div>`);
  }

  async function afficherPage(conteneur, parametres) {
    const id = texte(parametres.id);
    const responsable = App.estResponsable();
    const route = location.hash;
    await rattraper();
    if (location.hash !== route) return;
    const page = Wiki.page(id, { profil: App.profil ? App.profil.type : '', responsable });
    if (!page) {
      afficherIntrouvable(conteneur, id);
      return;
    }
    Wiki.rendrePage(conteneur, page, { liens: avecLiens(), responsable, index: indexDesPages() });
  }

  // ===========================================================================================
  // 6. Enregistrement des écrans (App est chargé après les modules : on attend la page)
  // ===========================================================================================

  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'wiki',
      route: /^#\/wiki$/,
      titre: 'Wiki',
      menu: { libelle: 'Wiki', icone: 'wiki', ordre: 42 },
      profils: PROFILS,
      tables: TABLES,
      afficher: afficherIndex,
    });
    App.ecran({
      id: 'wiki-page',
      route: /^#\/wiki\/(?<id>[^/?]+)$/,
      titre: 'Page du wiki',
      parent: 'wiki',
      profils: PROFILS,
      tables: TABLES,
      afficher: afficherPage,
    });
  });

  return { champRecherche, poserRechercheDemande, indexDesPages, compteurs };
})());
