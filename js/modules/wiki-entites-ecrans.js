'use strict';
// Wiki (7 ter/8) — l'encyclopédie de l'atelier à l'écran (refonte 2, ARCHITECTURE.md §20.12 ; D113, D114 ; tâche
// T136) : l'accueil #/wiki, les listes #/wiki/<liste> des six types et, en attendant les pages de la tâche T137, un
// rendu minimal des pages Panne, Technicien et Intervention (titre, fiche des faits, « Ouvrir la fiche OT »). Les
// routes sont dans wiki-ecrans.js (chargé avant) ; ce fichier rend Wiki.afficherEncyclopedie,
// Wiki.afficherListeEntites et Wiki.rendreEntite.
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
//  - dernières interventions : les DERNIERES_MONTREES premières de accueilEncyclopedie().dernieres ; recherche :
//    ENTITES_MONTREES premières entités par type, le reste derrière « Voir les n autres » ; interventions au
//    téléphone : CARTES_MONTREES premières cartes, le reste derrière un bouton ;
//  - page minimale : les faits de Wiki.entite dans l'ordre (date AAAA-MM-JJ → JJ/MM/AAAA, oui / non, nombre à la
//    française ; un fait vide est omis ; un fait qui porte un lien mène à sa page).

Object.assign(Wiki, (() => {

  // Les six types : libellés, icône et couleur discrète (classe wiki-t-<type>), route de leur liste, nombre de l'accueil.
  const TYPES = {
    machine: { libelle: 'Machine', pluriel: 'Machines', un: 'machine', plusieurs: 'machines', icone: 'parc',
      liste: 'machines', nombre: 'machines' },
    panne: { libelle: 'Panne', pluriel: 'Pannes', un: 'panne', plusieurs: 'pannes', icone: 'alerte',
      liste: 'pannes', nombre: 'pannes' },
    article: { libelle: 'Article', pluriel: 'Articles', un: 'article', plusieurs: 'articles', icone: 'magasin',
      liste: 'articles', nombre: 'articles' },
    technicien: { libelle: 'Technicien', pluriel: 'Techniciens', un: 'technicien', plusieurs: 'techniciens',
      icone: 'utilisateur', liste: 'techniciens', nombre: 'techniciens' },
    'savoir-faire': { libelle: 'Savoir-faire', pluriel: 'Savoir-faire', un: 'savoir-faire', plusieurs: 'savoir-faire',
      icone: 'cle', liste: 'savoir-faire', nombre: 'savoirFaire' },
    intervention: { libelle: 'Intervention', pluriel: 'Interventions', un: 'intervention', plusieurs: 'interventions',
      icone: 'ordres', liste: 'interventions', nombre: 'interventions' },
  };
  const TYPE_DE_LISTE = Object.fromEntries(Object.keys(TYPES).map((type) => [TYPES[type].liste, type]));
  const BRIQUES = ['machine', 'panne', 'article', 'technicien', 'savoir-faire'];
  const SUIVI = [
    { vue: 'a-valider', champ: 'aValider', libelle: 'à valider', ton: 'attente' },
    { vue: 'contradictions', champ: 'aTrancher', libelle: 'à trancher', ton: 'urgent' },
    { vue: 'echecs', champ: 'enEchec', libelle: 'en échec', ton: 'urgent' },
  ];
  const DESCRIPTIONS = {
    machine: 'Le parc, par lieu ; les sous-ensembles sous leur machine.',
    panne: 'Une page par code symptôme, tirée des interventions correctives clôturées ; les plus fréquentes d\'abord.',
    article: 'Les pièces du magasin : où elles sont rangées, leur stock, où elles servent.',
    technicien: 'Leurs interventions et leurs habilitations ; leur nom n\'est jamais envoyé à l\'IA.',
    'savoir-faire': 'Les gestes qui font gagner du temps, écrits à partir des astuces des techniciens.',
    intervention: 'Toutes les interventions : celles en cours ou à venir en tête, puis de la plus récente à la plus ancienne.',
  };
  const FICHES = { panne: 'Fiche de la panne', technicien: 'Fiche du technicien', intervention: 'Fiche de l\'intervention' };
  const ETATS_STOCK = { 'en stock': 'ok', 'sous le seuil': 'attention', rupture: 'ko' };
  const OPTIONS_ETAT = [['', 'Tous les états'], ['en stock', 'En stock'], ['sous le seuil', 'Sous le seuil'], ['rupture', 'En rupture']];

  const DERNIERES_MONTREES = 6;          // dernières interventions de l'accueil
  const ENTITES_MONTREES = 6;            // par type, dans les résultats de la recherche
  const CARTES_MONTREES = 40;            // interventions au téléphone, avant « Voir les n autres »
  const DELAI_RECHERCHE_MS = 300;        // comme Wiki.champRecherche : la recherche part après 300 ms sans frappe

  // ===========================================================================================
  // 1. Petits outils
  // ===========================================================================================

  const texte = (valeur) => (valeur === null || valeur === undefined ? '' : String(valeur).trim());
  const profilCourant = () => (App.profil ? texte(App.profil.type) : '');
  const adresse = (id) => '#/wiki/' + encodeURIComponent(id);
  const pluriel = (nombre, un, plusieurs) => nombre + ' ' + (nombre > 1 ? plusieurs : un);
  const compte = (nombre, type) => pluriel(nombre, TYPES[type].un, TYPES[type].plusieurs);

  // Ordre alphabétique français (« Électrovanne » avec les E) des articles, techniciens et savoir-faire, comme Prévo.
  const ORDRE_FRANCAIS = new Intl.Collator('fr', { numeric: true, sensitivity: 'base' });
  const enFrancais = (liste, nom) => liste.slice().sort((a, b) => ORDRE_FRANCAIS.compare(nom(a), nom(b)));

  /** Morceaux non vides séparés par `separateur` (tableau pour UI.html : chaque chaîne y est échappée). */
  const joindre = (parties, separateur) => parties.filter(Boolean).map((partie, rang) => (rang ? [separateur, partie] : [partie]));

  /**
   * Morceaux non vides qu'une ligne ne coupe jamais en leur milieu (« CH-01 », « 1 à renouveler ») : chacun garde
   * son séparateur à la fin (`marque` : ',' ou ' ·'), la ligne ne se coupe qu'entre deux morceaux.
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
  const etatStock = (article) => UI.html`<span class="badge ${ETATS_STOCK[article.etat] || 'neutre'} wiki-etat-stock">${UI.nombreFr(article.stock)}${article.unite ? ' ' + article.unite : ''} · ${article.etat}</span>`;
  const fil = (morceaux) => UI.html`<nav class="fil" aria-label="Vous êtes ici"><a href="#/wiki">Wiki</a>${morceaux.map((morceau) => UI.html` <span aria-hidden="true">›</span> ${morceau}`)}</nav>`;

  /** Bouton « Voir les n autres » qui montre ou cache les éléments [hidden] d'un bloc, au-delà des `montres` premiers. */
  function brancherVoirPlus(bloc, selecteur, montres) {
    const bouton = UI.$('.wiki-voir-autres', bloc);
    if (!bouton) return;
    const texteBouton = bouton.textContent;
    bouton.addEventListener('click', () => {
      const ouvrir = bouton.getAttribute('aria-expanded') !== 'true';
      UI.$$(selecteur, bloc).forEach((element, rang) => { element.hidden = !ouvrir && rang >= montres; });
      bouton.setAttribute('aria-expanded', String(ouvrir));
      bouton.textContent = ouvrir ? 'Montrer moins' : texteBouton;
    });
  }

  const boutonAutres = (reste, nom) => (reste > 0 ? UI.html`<button type="button" class="btn btn-fantome wiki-voir-autres"
    aria-expanded="false">${reste > 1 ? 'Voir les ' + reste + ' autres ' + nom : 'Voir l\'autre'}</button>` : '');

  // ===========================================================================================
  // 2. Accueil #/wiki
  // ===========================================================================================

  /** « 31 machines, 11 pannes, 52 articles, 4 techniciens et 23 savoir-faire » : chaque nombre mène à sa liste. */
  function phraseResume(nombres) {
    const morceaux = BRIQUES.filter((type) => Number.isInteger(nombres[TYPES[type].nombre]))
      .map((type) => UI.html`<a href="#/wiki/${TYPES[type].liste}" data-liste="${TYPES[type].liste}">${compte(nombres[TYPES[type].nombre], type)}</a>`);
    return morceaux.map((morceau, rang) => [rang === 0 ? '' : (rang === morceaux.length - 1 ? ' et ' : ', '), morceau]);
  }

  function tuileSynthese(accueil, profil) {
    const exemple = profil === 'demandeur' ? 'Chercher une machine, une panne, un article, un savoir-faire…'
      : 'Chercher une machine, une panne, un article, une intervention…';
    return UI.html`<section class="bento-tuile bento-synthese wiki-synthese" id="wiki-synthese" aria-labelledby="wiki-phrase-resume">
      <span class="bento-lueur" aria-hidden="true"><span class="bento-halo bento-halo-blanc"></span><span class="bento-halo bento-halo-cyan"></span></span>
      <p class="wiki-synthese-pastille">${UI.icone('wiki')}Ce que l'atelier sait</p>
      <h1 class="wiki-phrase-resume" id="wiki-phrase-resume">${phraseResume(accueil.nombres)}</h1>
      <p class="wiki-synthese-ligne" id="wiki-tire-de">Tiré de ${pluriel(accueil.nombres.cloturees, 'intervention clôturée', 'interventions clôturées')}.
        Tout est relié : chaque nom mène à sa page.</p>
      <div class="wiki-recherche-accueil" role="search">
        <label class="visuellement-cache" for="wiki-champ-accueil">Chercher dans le wiki</label>
        ${UI.icone('recherche')}
        <input type="search" id="wiki-champ-accueil" class="wiki-recherche-champ" data-hors-saisie maxlength="200" autocomplete="off"
          enterkeyhint="search" placeholder="${exemple}" aria-describedby="wiki-aide-recherche">
        <p class="visuellement-cache" id="wiki-aide-recherche">Les entités du wiki par leur nom, puis les interventions clôturées et les textes du wiki.</p>
      </div>
    </section>`;
  }

  /** « Suivi du wiki » (responsable) : mêmes définitions que les vues du journal où mènent les petites tuiles. */
  function tuileSuivi(suivi) {
    const file = typeof Wiki.file === 'function' ? Wiki.file().length : 0;
    return UI.html`<section class="bento-tuile wiki-suivi" id="wiki-suivi" aria-labelledby="wiki-suivi-titre">
      <h2 id="wiki-suivi-titre">Suivi du wiki</h2>
      <div class="wiki-suivi-tuiles">${SUIVI.map((entree) => {
        const nombre = suivi[entree.champ];
        return UI.html`<a class="wiki-mini${nombre ? ' ' + entree.ton : ''}" data-suivi="${entree.vue}" href="#/wiki-journal?vue=${entree.vue}">
          <b class="wiki-mini-nombre">${nombre}</b><span>${entree.libelle}</span></a>`;
      })}</div>
      <div class="wiki-suivi-actions">
        <a class="btn btn-secondaire" id="wiki-traiter-file" href="#/wiki-journal?vue=file">Traiter la file (${file})</a>
        <a class="wiki-lien-journal" id="wiki-lien-journal" href="#/wiki-journal">Journal du wiki</a>
      </div>
    </section>`;
  }

  /** Ligne utile d'une brique (données de Wiki.accueilEncyclopedie). */
  function ligneBrique(type, accueil) {
    if (type === 'machine') {
      const suivies = accueil.machinesPlusDInterventions.filter((machine) => machine.interventions > 0);
      return suivies.length ? ['Le plus d\'interventions : ', insecables(suivies.map(repere), ',')] : 'Aucune intervention enregistrée';
    }
    if (type === 'panne') {
      const panne = accueil.pannePlusFrequente;
      return panne ? ['La plus fréquente : ' + panne.titre + ' ', insecables(['(' + pluriel(panne.cas, 'cas', 'cas') + ')'], '')]
        : 'Elles naissent des interventions correctives clôturées';
    }
    if (type === 'article') {
      const parties = [accueil.articles.sousLeSeuil ? accueil.articles.sousLeSeuil + ' sous le seuil' : '',
        accueil.articles.enRupture ? accueil.articles.enRupture + ' en rupture' : ''].filter(Boolean);
      return parties.length ? insecables(parties, ' ·') : 'Tous en stock, au-dessus du seuil';
    }
    if (type === 'technicien') {
      const habilitations = accueil.habilitations;
      return insecables([pluriel(habilitations.suivies, 'habilitation suivie', 'habilitations suivies'),
        habilitations.aRenouveler ? habilitations.aRenouveler + ' à renouveler' : '',
        habilitations.echues ? pluriel(habilitations.echues, 'échue', 'échues') : ''], ' ·');
    }
    return accueil.nombres.savoirFaire ? 'Écrits à partir des astuces des techniciens' : 'Ils naissent des astuces des interventions';
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
      <div class="bento-liste-tete"><h2 id="wiki-dernieres-titre">Dernières interventions</h2>
        ${accueil.nombres.interventions === null ? '' : UI.html`<a class="bento-tout-voir" href="#/wiki/interventions">Toutes</a>`}</div>
      ${lignes.length ? UI.html`<ul class="wiki-lignes-entites">${lignes.map(ligneDerniere)}</ul>`
        : UI.html`<p class="bento-vide">Aucune intervention clôturée pour l'instant.</p>`}
    </section>`;
  }

  function tuilePannes(accueil) {
    const pannes = accueil.pannesFrequentes;
    const plus = pannes.length ? Math.max(1, pannes[0].cas) : 1;
    return UI.html`<section class="bento-tuile wiki-tuile-liste" id="wiki-pannes-frequentes" aria-labelledby="wiki-pannes-titre">
      <div class="bento-liste-tete"><h2 id="wiki-pannes-titre">Pannes les plus fréquentes</h2>
        <a class="bento-tout-voir" href="#/wiki/pannes">Toutes</a></div>
      ${pannes.length ? UI.html`<ul class="wiki-barres">${pannes.map((panne) => UI.html`<li data-id="${panne.id}">
          ${lienEntite(panne.lien, panne.titre)}
          <span class="wiki-jauge" aria-hidden="true"><i style="width: ${Math.max(4, Math.round(100 * panne.cas / plus))}%"></i></span>
          <span class="wiki-barre-cas">${pluriel(panne.cas, 'cas', 'cas')}</span></li>`)}</ul>`
        : UI.html`<p class="bento-vide">Aucune panne pour l'instant : elles naissent des interventions correctives clôturées.</p>`}
    </section>`;
  }

  // --- recherche de l'accueil ---

  const TITRES_TROUVES = { intervention: (entite) => entite.element.id + ' · ' + entite.titre };
  const SOUS_TROUVES = {
    machine: (e) => [e.lieu, e.marqueModele],
    panne: (e) => [pluriel(e.cas, 'cas', 'cas'), pluriel(e.machines, 'machine', 'machines')],
    article: (e) => [e.reference, e.emplacement ? 'rangé ' + e.emplacement : ''],
    technicien: (e) => [e.metier],
    'savoir-faire': (e) => [e.rattachement ? e.rattachement.titre : ''],
    intervention: (e) => [UI.dateFr(e.date), e.statut],
  };

  /** Un groupe de la recherche (« Machines · 3 ») : ses ENTITES_MONTREES premières entités, le reste derrière un bouton. */
  function groupeTrouve(groupe) {
    const type = groupe.type;
    const bloc = UI.element(UI.html`<div class="wiki-groupe" data-type="${type}">
      <h3 class="wiki-groupe-titre">${TYPES[type].pluriel} · ${groupe.entites.length}</h3>
      <ul class="wiki-lignes-entites">${groupe.entites.map((entite, rang) => {
        const sous = SOUS_TROUVES[type](entite.element).filter(Boolean).join(' · ');
        return UI.html`<li class="wiki-ligne wiki-entite-trouvee" data-id="${entite.lien || ''}"${rang >= ENTITES_MONTREES ? UI.brut(' hidden') : ''}>
          ${pastille(type)}<span class="wiki-ligne-corps">${lienEntite(entite.lien, (TITRES_TROUVES[type] || ((e) => e.titre))(entite))}
          ${sous ? UI.html`<span class="wiki-ligne-sous">${sous}</span>` : ''}</span></li>`;
      })}</ul>
      ${boutonAutres(groupe.entites.length - ENTITES_MONTREES, TYPES[type].plusieurs)}
    </div>`);
    brancherVoirPlus(bloc, '.wiki-entite-trouvee', ENTITES_MONTREES);
    return bloc;
  }

  /** Résultats d'une requête : les entités par type, puis les interventions et les textes du wiki (Wiki.rechercher). */
  function afficherTrouves(zone, requete, profil) {
    const entites = Wiki.chercherEntites(requete, { profil });
    const blocs = Wiki.blocsRecherche(Wiki.rechercher(requete, {}), {});
    UI.remplir(zone, UI.html`<h2 class="wiki-trouves-titre">Résultats pour « ${requete} »</h2>`);
    if (!entites.groupes.length && !blocs.length) {
      zone.insertAdjacentHTML('beforeend', String(UI.html`<p class="wiki-rien"><b>Rien trouvé pour « ${requete} ».</b></p>
        <p class="aide">Essayez un repère (CP-01), une panne (fuite), une référence d'article ou un autre mot.</p>`));
      return;
    }
    entites.groupes.forEach((groupe) => zone.appendChild(groupeTrouve(groupe)));
    if (!blocs.length) return;
    const plein = UI.element(UI.html`<div class="wiki-groupe wiki-plein-texte" data-type="texte">
      <h3 class="wiki-groupe-titre">Dans les interventions et les textes du wiki</h3><div class="wiki-resultats"></div></div>`);
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
        UI.remplir(zone, UI.html`<p class="erreur">Recherche impossible : ${(erreur && erreur.message) || ''}</p>`);
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
    App.definirTitre('Wiki');
    UI.remplir(conteneur, UI.html`<div class="wiki wiki-accueil" data-profil="${profil}">
      <div class="wiki-bento${accueil.suivi ? '' : ' sans-suivi'}" id="wiki-accueil">
        ${tuileSynthese(accueil, profil)}
        ${accueil.suivi ? tuileSuivi(accueil.suivi) : ''}
        <section class="bento-tuile wiki-trouves" id="wiki-trouves" aria-live="polite" aria-label="Résultats de la recherche" hidden></section>
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
      ${enteteListe(type, nombre, DESCRIPTIONS[type])}${contenu}</div>`);
    return UI.$('.wiki-liste-entites', conteneur);
  }

  function afficherReserve(conteneur, type) {
    UI.remplir(conteneur, UI.html`<div class="wiki wiki-liste-entites wiki-reserve" data-liste="${TYPES[type].liste}">
      ${enteteListe(type, null, '')}
      ${UI.vide('Réservé aux techniciens et au responsable', type === 'technicien'
        ? 'Le demandeur voit le nom des techniciens, sans leur page.' : 'Le demandeur voit le numéro des interventions, sans leur détail.', 'utilisateur')}
      <p><a class="btn btn-secondaire" href="#/wiki">Retour au wiki</a></p>
    </div>`);
  }

  /** Lignes d'une machine puis de ses sous-ensembles (décalés selon leur profondeur). */
  function lignesMachine(machine, profondeur) {
    const pannes = machine.pannes.slice(0, 2).map((panne) => panne.libelle).join(', ');
    return [UI.html`<li class="wiki-ligne${profondeur ? ' enfant' : ''}" data-id="${machine.equipementId}" style="--profondeur: ${profondeur}">
      <span class="wiki-ligne-corps">${lienEntite(machine.lien, machine.titre)}
        ${machine.marqueModele || pannes ? UI.html`<span class="wiki-ligne-sous">${joindre([machine.marqueModele, pannes], ' · ')}</span>` : ''}</span>
      <span class="wiki-ligne-droite">${pluriel(machine.interventions, 'intervention', 'interventions')}</span></li>`]
      .concat(machine.sousEnsembles.flatMap((enfant) => lignesMachine(enfant, profondeur + 1)));
  }

  /**
   * Titre d'un groupe de lieu : le chemin du lieu, sans sa racine quand tous les lieux partagent la même (le site,
   * « Site des Trois Vallées › Atelier Usinage » → « Atelier Usinage ») ; « Lieu non renseigné » sans lieu.
   */
  function titresDesLieux(groupes) {
    const chemins = groupes.map((groupe) => (groupe.lieu ? groupe.lieu.split(' › ') : []));
    const racine = chemins.length && chemins.every((chemin) => chemin.length > 1 && chemin[0] === chemins[0][0]) ? 1 : 0;
    return chemins.map((chemin) => (chemin.length ? chemin.slice(racine).join(' › ') : 'Lieu non renseigné'));
  }

  function rendreMachines(conteneur, groupes) {
    const compter = (machines) => machines.reduce((total, machine) => total + 1 + compter(machine.sousEnsembles), 0);
    const titres = titresDesLieux(groupes);
    cadreListe(conteneur, 'machine', groupes.reduce((total, groupe) => total + compter(groupe.machines), 0),
      groupes.length ? groupes.map((groupe, rang) => UI.html`<section class="wiki-groupe-lieu" data-lieu="${groupe.lieu}" aria-labelledby="wiki-lieu-${rang}">
        <h2 class="wiki-groupe-titre" id="wiki-lieu-${rang}" title="${groupe.lieu}">${titres[rang]}</h2>
        <ul class="bento-tuile wiki-lignes-entites wiki-tuile-lignes">${groupe.machines.map((machine) => lignesMachine(machine, 0))}</ul></section>`)
        : UI.vide('Aucune machine dans le parc', 'Chaque équipement créé dans le Parc a sa page ici.', 'parc'));
  }

  function rendrePannes(conteneur, pannes) {
    cadreListe(conteneur, 'panne', pannes.length, pannes.length ? UI.html`<ul class="bento-tuile wiki-lignes-entites wiki-tuile-lignes">${pannes.map((panne) => UI.html`
      <li class="wiki-ligne" data-id="${panne.id}">${pastille('panne')}
        <span class="wiki-ligne-corps">${lienEntite(panne.lien, panne.titre)}
          <span class="wiki-ligne-sous">${joindre([pluriel(panne.machines, 'machine touchée', 'machines touchées'),
            panne.cause ? 'cause la plus fréquente : ' + panne.cause.libelle : '', panne.derniere ? 'dernier cas le ' + UI.dateFr(panne.derniere) : ''], ' · ')}</span></span>
        <span class="wiki-ligne-droite">${pluriel(panne.cas, 'cas', 'cas')}</span></li>`)}</ul>`
      : UI.vide('Aucune panne pour l\'instant', 'Une panne a sa page dès qu\'une intervention corrective de son code symptôme est clôturée.', 'alerte'));
  }

  function carteArticle(article) {
    return UI.html`<li data-id="${article.articleId}"><a href="${adresse(article.lien)}">
      <div class="carte-tete"><b>${article.reference || article.articleId}</b>${etatStock(article)}</div>
      <div class="carte-titre">${article.titre}</div>
      <div class="carte-meta">${article.emplacement ? UI.html`<span>Rangé ${article.emplacement}</span>` : ''}
        <span>${pluriel(article.interventions, 'intervention', 'interventions')}</span>${article.critique ? UI.html`<span>Pièce critique</span>` : ''}</div>
    </a></li>`;
  }

  function rendreArticles(conteneur, articles) {
    const cadre = cadreListe(conteneur, 'article', articles.length, UI.html`
      <form class="filtres wiki-filtres" id="wiki-filtres-articles" data-hors-saisie role="search" aria-label="Filtrer les articles">
        <label class="visuellement-cache" for="wiki-filtre-texte">Filtrer les articles</label>
        <input type="search" id="wiki-filtre-texte" name="texte" placeholder="Désignation, référence, emplacement" autocomplete="off">
        <label class="visuellement-cache" for="wiki-filtre-etat">État du stock</label>
        <select id="wiki-filtre-etat" name="etat">${OPTIONS_ETAT.map(([valeur, libelle]) => UI.html`<option value="${valeur}">${libelle}</option>`)}</select>
      </form>
      <p class="aide wiki-filtre-compte" role="status"></p>
      <div class="bento-tuile wiki-tuile-tableau" id="wiki-articles"></div>`);
    const formulaire = UI.$('#wiki-filtres-articles', cadre);
    const zone = UI.$('#wiki-articles', cadre);
    const compteur = UI.$('.wiki-filtre-compte', cadre);
    const cleDe = (article) => UI.normaliserRecherche([article.titre, article.reference, article.emplacement].join(' '));
    const tableau = UI.estTelephone() ? null : UI.tableau({
      libelle: 'Articles du magasin', vide: 'Aucun article ne correspond à ce filtre.', lignes: articles,
      colonnes: [
        { cle: 'titre', libelle: 'Article', classe: 'wiki-cellule-titre',
          rendu: (article) => UI.html`${lienEntite(article.lien, article.titre)}${article.critique ? UI.html` <span class="badge attention">Critique</span>` : ''}` },
        { cle: 'reference', libelle: 'Référence' },
        { cle: 'emplacement', libelle: 'Emplacement' },
        { cle: 'stock', libelle: 'Stock', type: 'nombre', rendu: etatStock },
        { cle: 'interventions', libelle: 'Interventions', type: 'nombre' },
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
          : UI.html`<p class="muted">Aucun article ne correspond à ce filtre.</p>`);
      }
      compteur.textContent = pluriel(gardes.length, 'article', 'articles') + ' sur ' + articles.length;
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
        <span class="wiki-ligne-sous">${joindre([technicien.metier, technicien.actif ? '' : 'inactif'], ' · ')}</span>
        <span class="wiki-carte-chiffres">${joindre([pluriel(technicien.interventions, 'intervention', 'interventions'),
          pluriel(technicien.habilitations, 'habilitation', 'habilitations'), UI.heures(technicien.heures) + ' pointées'], ' · ')}</span>
      </a></li>`)}</ul>`
      : UI.vide('Aucun technicien', 'Les techniciens de l\'Équipe ont leur page ici.', 'utilisateur'));
  }

  function rendreSavoirFaire(conteneur, savoirFaire) {
    cadreListe(conteneur, 'savoir-faire', savoirFaire.length, savoirFaire.length ? UI.html`<ul class="bento-tuile wiki-lignes-entites wiki-tuile-lignes">${savoirFaire.map((page) => UI.html`
      <li class="wiki-ligne" data-id="${page.id}">${pastille('savoir-faire')}
        <span class="wiki-ligne-corps">${lienEntite(page.lien, page.titre)}
          <span class="wiki-ligne-sous">${joindre([page.rattachement ? UI.html`${page.rattachement.type === 'machine' ? 'Machine' : 'Article'} ${lienEntite(page.rattachement.lien, page.rattachement.titre)}` : 'Sans rattachement',
            page.mere ? UI.html`sous-page de ${lienEntite(page.mere.id, page.mere.titre)}` : ''], ' · ')}</span></span></li>`)}</ul>`
      : UI.vide('Aucun savoir-faire pour l\'instant', 'Ils naissent des astuces des interventions intégrées au wiki, ou d\'une écriture à la main.', 'cle'));
  }

  function carteIntervention(ot, cache) {
    return UI.html`<li class="wiki-carte-intervention" data-id="${ot.id}"${cache ? UI.brut(' hidden') : ''}><a href="${adresse(ot.lien)}">
      <div class="carte-tete"><b>${ot.id}</b>${UI.badgeStatut(ot.statut)}</div>
      <div class="carte-titre">${ot.titre}</div>
      <div class="carte-meta"><span>${UI.dateFr(ot.date)}</span>${ot.machine ? UI.html`<span>${repere(ot.machine)}</span>` : ''}${ot.panne ? UI.html`<span>${ot.panne.libelle}</span>` : ''}</div>
    </a></li>`;
  }

  function rendreInterventions(conteneur, interventions) {
    const cadre = cadreListe(conteneur, 'intervention', interventions.length, UI.html`<div class="bento-tuile wiki-tuile-tableau" id="wiki-interventions"></div>`);
    const zone = UI.$('#wiki-interventions', cadre);
    if (!UI.estTelephone()) {
      zone.appendChild(UI.tableau({
        libelle: 'Interventions', vide: 'Aucune intervention.', lignes: interventions,
        colonnes: [
          { cle: 'date', libelle: 'Date', rendu: (ot) => UI.dateFr(ot.date) },
          { cle: 'id', libelle: 'N°', classe: 'sans-coupure', rendu: (ot) => lienEntite(ot.lien, ot.id) },
          { cle: 'titre', libelle: 'Intervention', classe: 'wiki-cellule-titre' },
          { cle: 'statut', libelle: 'Statut', rendu: (ot) => UI.badgeStatut(ot.statut) },
          { cle: 'machine', libelle: 'Machine', valeurTri: (ot) => repere(ot.machine), rendu: (ot) => lienMachine(ot.machine) },
          { cle: 'panne', libelle: 'Panne', valeurTri: (ot) => (ot.panne ? ot.panne.libelle : ''),
            rendu: (ot) => (ot.panne ? lienEntite(ot.panne.lien, ot.panne.libelle) : '') },
          { cle: 'techniciens', libelle: 'Technicien', valeurTri: (ot) => ot.techniciens.map((t) => t.nom).join(', '),
            rendu: (ot) => UI.html`${joindre(ot.techniciens.map((t) => lienEntite(t.lien, t.nom)), ', ')}` },
        ],
      }));
      return;
    }
    UI.remplir(zone, interventions.length ? UI.html`<ul class="liste-cartes">${interventions.map((ot, rang) => carteIntervention(ot, rang >= CARTES_MONTREES))}</ul>
      ${boutonAutres(interventions.length - CARTES_MONTREES, 'interventions')}` : UI.html`<p class="muted">Aucune intervention.</p>`);
    brancherVoirPlus(zone, '.wiki-carte-intervention', CARTES_MONTREES);
  }

  const RENDUS = { machine: rendreMachines, panne: rendrePannes, article: rendreArticles, technicien: rendreTechniciens,
    'savoir-faire': rendreSavoirFaire, intervention: rendreInterventions };
  // Listes montrées dans l'ordre alphabétique français (les autres gardent l'ordre de Wiki.listeEntites).
  const NOMS_TRIES = { article: (article) => article.titre, technicien: (technicien) => technicien.nom, 'savoir-faire': (page) => page.titre };

  /** Écran #/wiki/<liste> : la liste d'un type, ou « réservé » quand le profil ne la voit pas (D114). */
  function afficherListeEntites(conteneur, liste) {
    const type = TYPE_DE_LISTE[liste];
    App.definirTitre('Wiki · ' + TYPES[type].pluriel);
    const donnees = Wiki.listeEntites(type, { profil: profilCourant() });
    if (!donnees) afficherReserve(conteneur, type);
    else RENDUS[type](conteneur, NOMS_TRIES[type] ? enFrancais(donnees, NOMS_TRIES[type]) : donnees);
  }

  // ===========================================================================================
  // 4. Pages Panne, Technicien et Intervention : rendu minimal (titre et faits), en attendant la tâche T137
  // ===========================================================================================

  /** Valeur d'un fait à l'écran (précisions en tête) ; null si le fait est vide. */
  function valeurFait(fait) {
    const valeur = fait.valeur;
    if (valeur === null || valeur === undefined || valeur === '') return null;
    if (typeof valeur === 'boolean') return valeur ? 'oui' : 'non';
    if (typeof valeur === 'number') return UI.nombreFr(valeur);
    const chaine = String(valeur);
    if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}/.test(chaine)) return UI.dateHeureFr(chaine);
    return /^\d{4}-\d{2}-\d{2}$/.test(chaine) ? UI.dateFr(chaine) : chaine;
  }

  /** Rend la page d'une panne, d'un technicien ou d'une intervention (Wiki.entite) ; false pour un autre type. */
  function rendreEntite(conteneur, entite) {
    const type = entite && entite.type;
    if (!FICHES[type]) return false;
    const titre = type === 'intervention' && entite.titre !== entite.id ? entite.id + ' — ' + entite.titre : entite.titre;
    const faits = entite.faits.map((fait) => [fait, valeurFait(fait)]).filter(([, valeur]) => valeur !== null);
    const fiche = entite.sections && entite.sections.ficheOT;
    App.definirTitre(titre);
    UI.remplir(conteneur, UI.html`<div class="wiki wiki-page wiki-entite" data-page="${entite.id}" data-type="${type}">
      <div class="entete-page"><div>
        ${fil([UI.html`<a href="#/wiki/${TYPES[type].liste}">${TYPES[type].pluriel}</a>`])}
        <p class="wiki-puce-ligne">${puce(type)}</p>
        <h1>${titre}</h1>
      </div>${fiche ? UI.html`<a class="btn btn-secondaire" id="wiki-fiche-ot" href="${fiche}">${UI.icone('ordres')}Ouvrir la fiche OT</a>` : ''}</div>
      <section class="carte wiki-faits" id="wiki-faits" aria-labelledby="wiki-faits-titre">
        <h2 id="wiki-faits-titre">${FICHES[type]}</h2>
        <dl class="valeurs">${faits.map(([fait, valeur]) => UI.html`<dt>${fait.libelle}</dt>
          <dd>${fait.lien ? UI.html`<a href="${adresse(fait.lien)}">${valeur}</a>` : valeur}</dd>`)}</dl>
      </section>
    </div>`);
    return true;
  }

  return { afficherEncyclopedie, afficherListeEntites, rendreEntite };
})());
