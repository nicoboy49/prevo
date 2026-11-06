'use strict';
// Installation : assistant d'installation (#ecran-installation de index.html, route #/installation ; ARCHITECTURE.md
// §22.10 ; CDC D131, D132 ; CS130). Écran plein hors de la coque, servi par le serveur et ouvert par App sur le PC
// serveur seulement (location.hostname 127.0.0.1 ou localhost) quand /api/info rend installation_a_faire.
// Huit étapes de l'étude §4.1, une par écran (qui utilise, depuis où, compte, certificat, hors de l'atelier,
// démarrer avec le PC, sauvegardes, récapitulatif) ; chaque étape montre ses quatre textes (qui est concerné, ce que
// ça change, pourquoi, conseil selon la situation) tirés d'AccesTextes.choix (T169, jamais recopiés ici) et
// « Régler autrement », qui déplie les réglages fins avec l'aide d'AccesTextes.options. Les étapes « sans objet »
// (etat.etapes, calculé par le serveur) sont sautées avec une ligne qui le dit. Situation « informaticien » : après
// l'étape 1, toutes les étapes sur une seule page, rien d'automatique sans clic.
// Chaque étape écrit le brouillon par POST /api/installation/<etape> (fetch avec X-Prevo) ; une erreur du serveur
// s'affiche telle quelle sous le bouton et l'étape reste ouverte. Le brouillon fait foi : GET etat replace
// l'assistant à la première étape à faire. « Terminer et ouvrir Prévo » : POST terminer (base « vide » ou « demo »
// quand aucun CSV n'était là au départ, T171), puis attente de la relance (/api/info toutes les 2 s, rechargement sur
// #/accueil ; message au bout de 60 s). Dossier conseillé C:\Prevo (étape 8) : POST deplacer puis attente du serveur
// relancé depuis la copie (GET etat : dossier), ou « Rester ici » mémorisé dans le brouillon. Un mot de passe n'est
// jamais mémorisé ni réécrit dans la page. La première ligne (« Tant que l'installation n'est pas terminée… ») est
// dans index.html, seule source. La fiche d'accès (étape 8, route #/installation/fiche) est mise en page par
// InstallationFiche (installation-fiche.js) ; les formulaires des étapes sont dans InstallationEtapes
// (installation-etapes.js). Dépendances : UI, AccesTextes, InstallationEtapes, InstallationFiche. Charte :
// css/modules/installation.css.

const Installation = (() => {

  const MOTIF_ROUTE = /^#\/installation(\/fiche)?(\?.*)?$/;
  const MOTIF_ROUTE_FICHE = /^#\/installation\/fiche(\?.*)?$/;
  const INTERVALLE_RELANCE_MS = 2000;           // ping du serveur relancé
  const DELAI_RELANCE_MS = 60000;               // au-delà : message, le serveur ne revient pas
  const messageServeurInjoignable = () => I18n.t('installation.message_serveur_injoignable.serveur_prevo_repond_pas');

  /** Pourquoi une étape est sans objet (compte, certificat, tailscale) ; '' pour une autre étape. Lu à l'affichage. */
  function raisonSansObjet(cle) {
    if (cle === 'compte') return I18n.t('installation.raison_sans_objet.prevo_reste_pc_aucun');
    if (cle === 'certificat') return I18n.t('installation.raison_sans_objet.prevo_reste_pc_http');
    if (cle === 'tailscale') return I18n.t('installation.raison_sans_objet.prevo_pas_joignable_hors');
    return '';
  }

  // Les huit étapes de l'étude §4.1 : clé de l'API (etat.etapes), question, choix d'AccesTextes (le premier porte
  // les quatre textes de l'étape ; un second complète, ex. la veille sous « Démarrer avec le PC »). Libellé court et
  // titre : accesseurs, lus à l'affichage.
  const ETAPES = [
    { cle: 'situation', get court() { return I18n.t('installation.court.utilise'); }, get titre() { return I18n.t('installation.titre.va_utiliser_prevo'); }, choix: ['installation'] },
    { cle: 'portee', get court() { return I18n.t('installation.court.depuis_ou'); }, get titre() { return I18n.t('installation.titre.ou_faut_pouvoir_ouvrir'); }, choix: ['exterieur', 'mot_de_passe'] },
    { cle: 'compte', get court() { return I18n.t('installation.court.compte'); }, get titre() { return I18n.t('installation.titre.nom_mot_passe'); }, choix: ['mot_de_passe'] },
    { cle: 'certificat', get court() { return I18n.t('installation.court.certificat'); }, get titre() { return I18n.t('installation.titre.telephones_fassent_confiance_https'); }, choix: ['certificat'] },
    { cle: 'tailscale', get court() { return I18n.t('installation.court.hors_atelier'); }, get titre() { return I18n.t('installation.titre.comment_joindre_pc_dehors'); }, choix: ['exterieur'] },
    { cle: 'demarrage', get court() { return I18n.t('installation.court.demarrage'); }, get titre() { return I18n.t('installation.titre.prevo_doit_demarrer_tout'); }, choix: ['demarrage', 'veille'] },
    { cle: 'sauvegardes', get court() { return I18n.t('installation.court.sauvegardes'); }, get titre() { return I18n.t('installation.titre.ou_garder_copie_donnees'); }, choix: ['sauvegardes'] },
    { cle: 'recapitulatif', get court() { return I18n.t('installation.court.recapitulatif'); }, get titre() { return I18n.t('installation.titre.voila_comment_connecte'); }, choix: ['etiquettes'] },
  ];

  // --- État -------------------------------------------------------------------------------
  let etat = null;                 // GET etat (étapes, brouillon, Tailscale, mkcert, système…)
  let index = 0;                   // étape courante (pas à pas)
  let sautees = [];                // étapes sans objet passées depuis la dernière étape montrée
  let resoudre = null;             // termine Installation.ouvrir (l'assistant quitté sans terminer)
  let fiche = null;                // GET fiche, lue à l'étape 8

  // ===========================================================================================
  // 1. Appels au serveur
  // ===========================================================================================

  /** GET (sans corps) ou POST JSON vers /api/installation/<etape> → { statut, donnees, message }. */
  async function appeler(etape, corps) {
    const options = { cache: 'no-store', credentials: 'same-origin', headers: {} };
    if (corps !== undefined) {
      options.method = 'POST';
      options.headers = { 'X-Prevo': '1', 'Content-Type': 'application/json; charset=utf-8' };
      options.body = JSON.stringify(corps);
    }
    let reponse;
    try {
      reponse = await fetch('/api/installation/' + etape, options);
    } catch (erreur) {
      return { statut: 0, donnees: null, message: messageServeurInjoignable() };
    }
    const donnees = await reponse.json().catch(() => null);
    const message = donnees && typeof donnees.erreur === 'string' && donnees.erreur
      ? StockageServeur.texte(donnees, 'erreur') : I18n.t('commun.message.serveur_a_repondu', { status: reponse.status });
    return { statut: reponse.status, donnees: donnees, message: reponse.ok ? '' : message };
  }

  function brouillon() {
    return (etat && etat.brouillon) || {};
  }

  function situation() {
    return (etat && etat.situation) || '';
  }

  function etatEtape(cle) {
    return (etat && etat.etapes && etat.etapes[cle]) || 'a_faire';
  }

  // Réponse d'une étape qui écrit le brouillon : {brouillon, etapes} repris dans l'état.
  function reprendre(donnees) {
    if (!donnees) return;
    if (donnees.brouillon) etat.brouillon = donnees.brouillon;
    if (donnees.etapes) etat.etapes = donnees.etapes;
    if (etat.brouillon && etat.brouillon.situation) etat.situation = etat.brouillon.situation;
    if (donnees.compte || donnees.technicien_id) etat.responsable_existe = etat.responsable_existe || Boolean(donnees.compte);
  }

  // ===========================================================================================
  // 2. Textes : les quatre textes d'un choix, l'aide d'un réglage, « Régler autrement »
  // ===========================================================================================

  function texteChoix(cleChoix) {
    return (typeof AccesTextes !== 'undefined' && AccesTextes.choix && AccesTextes.choix[cleChoix]) || null;
  }

  function aideOption(cle) {
    const option = typeof AccesTextes !== 'undefined' && AccesTextes.options && AccesTextes.options[cle];
    return option && option.aide ? option.aide : '';
  }

  /** Bloc des quatre textes d'un choix : qui est concerné, ce que ça change, pourquoi, conseil selon la situation. */
  function blocTextes(cleChoix) {
    const choix = texteChoix(cleChoix);
    if (!choix) return '';
    const laSituation = situation();
    const conseil = laSituation && choix.conseil[laSituation]
      ? choix.conseil[laSituation]
      : UI.html`<ul class="installation-conseils">${Object.keys(choix.conseil).map((cle) => UI.html`<li><b>${AccesTextes.situations[cle] || cle}</b> : ${choix.conseil[cle]}</li>`)}</ul>`;
    return UI.html`<div class="installation-textes" data-choix="${cleChoix}">
      <h3>${choix.titre}</h3>
      <dl>
        <div><dt>${I18n.t('installation.bloc_textes.concerne')}</dt><dd data-texte="qui">${choix.qui}</dd></div>
        <div><dt>${I18n.t('installation.bloc_textes.ca_change')}</dt><dd data-texte="change">${choix.change}</dd></div>
        <div><dt>${I18n.t('installation.bloc_textes.pourquoi')}</dt><dd data-texte="pourquoi">${choix.pourquoi}</dd></div>
        <div><dt>${I18n.t('installation.bloc_textes.prevo_conseille')}</dt><dd data-texte="conseil">${conseil}</dd></div>
      </dl>
    </div>`;
  }

  function blocAutrement(contenu) {
    return UI.html`<details class="installation-autrement">
      <summary>${I18n.t('installation.bloc_autrement.regler_autrement')}</summary>
      <div class="installation-autrement-corps">${contenu}</div>
    </details>`;
  }

  // Contexte donné aux formulaires d'InstallationEtapes : l'état et les textes de cet écran.
  function formulaireDe(etape) {
    return InstallationEtapes.formulaire(etape.cle, { etat, brouillon, situation, etatEtape, blocTextes, aideOption });
  }

  // ===========================================================================================
  // 3. Rendu : progression, une étape, la page unique de l'informaticien
  // ===========================================================================================

  function progression() {
    return UI.html`<ol class="installation-progression" aria-label="${I18n.t('installation.progression.etapes')}">${ETAPES.map((etape, i) => {
      const e = etape.cle === 'recapitulatif' ? 'a_faire' : etatEtape(etape.cle);
      const classe = i === index ? 'courante' : e === 'sans_objet' ? 'sans-objet' : e === 'fait' ? 'faite' : '';
      return UI.html`<li class="${classe}" ${UI.brut(i === index ? 'aria-current="step"' : '')}><span class="numero">${i + 1}</span><span class="libelle">${etape.court}</span></li>`;
    })}</ol>`;
  }

  function sectionEtape(etape, formulaire, unePage) {
    const i = ETAPES.indexOf(etape);
    const sansObjet = etatEtape(etape.cle) === 'sans_objet';
    // Bouton principal : « Enregistrer cette étape » sur la page unique, « Continuer » pas à pas ; aucun pour une
    // étape qui a ses propres boutons (Tailscale) tant qu'elle n'est pas faite, ni pour le récapitulatif.
    const recap = etape.cle === 'recapitulatif';
    let principal = '';
    if (!recap && unePage && !formulaire.propresBoutons && !formulaire.passer) {
      principal = UI.html`<button type="button" class="btn btn-primaire" data-enregistrer="${etape.cle}">${I18n.t('installation.section_etape.enregistrer_etape')}</button>`;
    } else if (!recap && !unePage && (!formulaire.propresBoutons || formulaire.passer)) {
      principal = UI.html`<button type="button" class="btn btn-primaire" id="inst-continuer">${etape.cle === 'situation' ? I18n.t('installation.section_etape.commencer') : I18n.t('commun.bouton.continuer')}</button>`;
    }
    const corps = sansObjet
      ? UI.html`<p class="installation-sautee">${I18n.t('installation.section_etape.sans_objet', { raison: raisonSansObjet(etape.cle) })}</p>`
      : UI.html`${formulaire.champs}
        <p class="erreur-champ installation-erreur" id="inst-erreur-${etape.cle}" role="alert" hidden></p>
        <div class="actions installation-actions">
          ${!unePage && i > 0 ? UI.html`<button type="button" class="btn btn-fantome" id="inst-precedent">${I18n.t('installation.section_etape.precedent')}</button>` : ''}
          <span class="espace"></span>
          ${principal}
          ${recap ? UI.html`<button type="button" class="btn btn-primaire" id="inst-terminer">${I18n.t('installation.section_etape.terminer_ouvrir_prevo')}</button>` : ''}
        </div>
        <div class="installation-attente" id="inst-attente" hidden></div>`;
    const faite = !recap && etatEtape(etape.cle) === 'fait';
    return UI.html`<section class="carte installation-etape" data-etape="${etape.cle}" data-numero="${i + 1}">
      <h2><span class="installation-numero">${I18n.t('installation.section_etape.etape_sur', { numero: i + 1, total: ETAPES.length })}${faite ? UI.html` <span class="installation-fait">${I18n.t('installation.section_etape.fait')}</span>` : ''}</span>${etape.titre}</h2>
      ${corps}
      ${etape.choix.map(blocTextes)}
      ${blocAutrement(formulaire.autrement)}
    </section>`;
  }

  /** « Étape « Certificat » sautée : … » (étape sans objet passée depuis la dernière étape montrée). */
  function ligneSautee(cle) {
    const etape = ETAPES.find((e) => e.cle === cle).court;
    const raison = raisonSansObjet(cle) || I18n.t('installation.ligne_sautee.sans_objet');
    return UI.html`<p class="installation-sautee">${I18n.t('installation.ligne_sautee.etape_sautee', { etape, raison })}</p>`;
  }

  function rendreEtape() {
    const etape = ETAPES[index];
    const formulaire = formulaireDe(etape);
    const zone = UI.$('#installation-contenu');
    UI.remplir(zone, UI.html`${progression()}
      ${sautees.map(ligneSautee)}
      ${sectionEtape(etape, formulaire, false)}`);
    zone.dataset.formulaire = etape.cle;
    poserEcouteursEtape(etape, formulaire, zone);
    if (etape.cle === 'recapitulatif') chargerFiche();
    window.scrollTo(0, 0);
  }

  // Informaticien : toutes les étapes sur une page, chacune avec ses appels ; rien d'automatique sans clic.
  function rendreUnePage() {
    const zone = UI.$('#installation-contenu');
    UI.remplir(zone, UI.html`<p class="note installation-une-page">${I18n.t('installation.rendre_une_page.situation_informaticien_toutes_etapes')}</p>
      ${ETAPES.slice(1).map((etape) => sectionEtape(etape, formulaireDe(etape), true))}`);
    zone.dataset.formulaire = 'une-page';
    ETAPES.slice(1).forEach((etape) => poserEcouteursEtape(etape, () => formulaireDe(etape), zone, true));
    chargerFiche();
  }

  function rendre() {
    sautees = sautees.filter((cle) => etatEtape(cle) === 'sans_objet');
    if (situation() === 'informaticien' && index > 0) rendreUnePage(); else rendreEtape();
  }

  function montrerErreur(cle, message) {
    const zone = UI.$('#inst-erreur-' + cle);
    if (!zone) return;
    zone.textContent = message || '';
    zone.hidden = !message;
  }

  async function pendant(bouton, action) {
    if (!bouton || bouton.disabled) return;
    bouton.disabled = true;
    bouton.setAttribute('aria-busy', 'true');
    try {
      await action();
    } finally {
      bouton.removeAttribute('aria-busy');
      bouton.disabled = false;
    }
  }

  // ===========================================================================================
  // 4. Écouteurs d'une étape : envoi, navigation, Tailscale, déplacement, fin
  // ===========================================================================================

  function poserEcouteursEtape(etape, formulaire, zone, unePage) {
    const lire = () => (typeof formulaire === 'function' ? formulaire() : formulaire);
    const section = UI.$('[data-etape="' + etape.cle + '"]', zone);
    if (!section) return;
    const force = UI.$('#inst-mot-de-passe', section);
    if (force) force.addEventListener('input', () => { UI.$('#inst-force', section).textContent = InstallationEtapes.indicationForce(force.value); });
    section.addEventListener('input', () => montrerErreur(etape.cle, ''));
    const continuer = UI.$('#inst-continuer', section) || UI.$('[data-enregistrer]', section);
    if (continuer) continuer.addEventListener('click', () => pendant(continuer, () => envoyer(etape, lire(), section, unePage)));
    const precedent = UI.$('#inst-precedent', section);
    if (precedent) precedent.addEventListener('click', () => { index = indicePrecedent(index); sautees = []; rendre(); });
    const plusTardTailscale = UI.$('#inst-tailscale-plus-tard', section);
    if (plusTardTailscale) plusTardTailscale.addEventListener('click', () => pendant(plusTardTailscale, () => poster(etape, 'tailscale', { action: 'plus_tard' }, unePage)));
    const appliquer = UI.$('#inst-tailscale-appliquer', section);
    if (appliquer) appliquer.addEventListener('click', () => pendant(appliquer, () => appliquerTailscale(etape, section, unePage)));
    const plusTardSauvegardes = UI.$('#inst-sauvegardes-plus-tard', section);
    if (plusTardSauvegardes) plusTardSauvegardes.addEventListener('click', () => pendant(plusTardSauvegardes, () => poster(etape, 'sauvegardes', { dossier: '' }, unePage)));
    const deplacer = UI.$('#inst-deplacer', section);
    if (deplacer) deplacer.addEventListener('click', () => pendant(deplacer, () => deplacerPrevo(section)));
    const garder = UI.$('#inst-dossier-garder', section);
    if (garder) garder.addEventListener('click', () => pendant(garder, () => resterIci(section)));
    const terminer = UI.$('#inst-terminer', section);
    if (terminer) terminer.addEventListener('click', () => pendant(terminer, () => terminerInstallation(section, lire())));
  }

  // Lecture du formulaire puis POST de l'étape ; « passer » (compte déjà fait) avance sans appel.
  async function envoyer(etape, formulaire, section, unePage) {
    if (etape.cle === 'recapitulatif') return;
    if (formulaire.passer) { avancer(unePage); return; }
    const corps = formulaire.lire ? formulaire.lire(section) : {};
    if (!corps) { montrerErreur(etape.cle, formulaire.message || I18n.t('installation.envoyer.completez_etape')); return; }
    if (corps.probleme) { montrerErreur(etape.cle, corps.probleme); return; }
    await poster(etape, etape.cle, corps, unePage, formulaire, section);
  }

  async function poster(etape, route, corps, unePage, formulaire, section) {
    const reponse = await appeler(route, corps);
    if (formulaire && formulaire.apres) formulaire.apres(section);
    if (reponse.statut === 409 && etape.cle === 'compte') {
      // Un responsable existe déjà (jamais de remplacement) : le message du serveur, et l'étape se passe.
      etat.responsable_existe = true;
      rendreApres(unePage, etape, reponse.message);
      return;
    }
    if (!reponse.statut || reponse.statut >= 400) { montrerErreur(etape.cle, reponse.message); return; }
    reprendre(reponse.donnees);
    const echec = formulaire && formulaire.echec ? formulaire.echec(reponse.donnees) : '';
    if (echec) { montrerErreur(etape.cle, echec); rendreApres(unePage, etape, echec); return; }
    const texte = formulaire && formulaire.reussite ? formulaire.reussite(reponse.donnees) : '';
    if (texte) UI.toast(texte, 'succes');
    if (unePage) rendreApres(true, etape); else avancer(false);
  }

  // Page unique : la section rejouée (les étapes suivantes peuvent changer d'objet) ; pas à pas : la même étape.
  function rendreApres(unePage, etape, message) {
    rendre();
    if (message) montrerErreur(etape.cle, message);
    if (unePage) {
      const section = UI.$('#installation-contenu [data-etape="' + etape.cle + '"]');
      if (section) section.scrollIntoView({ block: 'start' });
    }
  }

  function indiceSuivant(depuis) {
    let i = depuis + 1;
    sautees = [];
    while (i < ETAPES.length - 1 && etatEtape(ETAPES[i].cle) === 'sans_objet') { sautees.push(ETAPES[i].cle); i += 1; }
    return i;
  }

  function indicePrecedent(depuis) {
    let i = depuis - 1;
    while (i > 0 && etatEtape(ETAPES[i].cle) === 'sans_objet') i -= 1;
    return Math.max(0, i);
  }

  function avancer(unePage) {
    if (unePage) { rendre(); return; }
    index = indiceSuivant(index);
    rendre();
  }

  async function appliquerTailscale(etape, section, unePage) {
    const detection = await appeler('tailscale', { action: 'detecter' });
    if (!detection.statut || detection.statut >= 400) { montrerErreur(etape.cle, detection.message); return; }
    const d = detection.donnees.detection || {};
    const proposition = detection.donnees.proposition || {};
    if (!d.present || !d.connecte) {
      let probleme = I18n.t('installation.appliquer_tailscale.tailscale_installe_mais_pas');
      if (!d.present) {
        probleme = d.raison ? I18n.t('installation.appliquer_tailscale.tailscale_toujours_pas_detecte_raison', { raison: StockageServeur.texte(d, 'raison') })
          : I18n.t('installation.appliquer_tailscale.tailscale_toujours_pas_detecte');
      }
      montrerErreur(etape.cle, probleme);
      return;
    }
    const application = await appeler('tailscale', { action: 'appliquer' });
    if (!application.statut || application.statut >= 400) { montrerErreur(etape.cle, application.message); return; }
    reprendre(application.donnees);
    const resultat = UI.$('#inst-tailscale-resultat', section);
    const publie = StockageServeur.texte(application.donnees, 'message') || I18n.t('installation.appliquer_tailscale.tailscale_publie_prevo');
    const adresse = application.donnees.adresse || '';
    UI.remplir(resultat, UI.html`<p>${I18n.html('installation.appliquer_tailscale.publie_adresse_adresse', { publie, adresse })}</p>
      <ul>${(proposition.rappels || []).map((rappel) => UI.html`<li>${rappel}</li>`)}</ul>
      ${proposition.unattended ? UI.html`<div class="actions"><button type="button" class="btn btn-secondaire" id="inst-tailscale-unattended">${I18n.t('installation.appliquer_tailscale.rester_connecte_meme_sans')}</button></div>` : ''}
      <div class="actions">${unePage ? '' : UI.html`<button type="button" class="btn btn-primaire" id="inst-tailscale-continuer">${I18n.t('commun.bouton.continuer')}</button>`}</div>`);
    resultat.hidden = false;
    const unattended = UI.$('#inst-tailscale-unattended', resultat);
    if (unattended) {
      unattended.addEventListener('click', () => pendant(unattended, async () => {
        const reponse = await appeler('tailscale', { action: 'unattended' });
        if (!reponse.statut || reponse.statut >= 400) { montrerErreur(etape.cle, reponse.message); return; }
        UI.toast(StockageServeur.texte(reponse.donnees, 'message') || I18n.t('installation.appliquer_tailscale.fait'), 'succes');
        unattended.hidden = true;
      }));
    }
    const continuer = UI.$('#inst-tailscale-continuer', resultat);
    if (continuer) continuer.addEventListener('click', () => avancer(false));
  }

  async function chargerFiche() {
    const zone = UI.$('#inst-fiche');
    if (!zone) return;
    const reponse = await appeler('fiche');
    if (!reponse.statut || reponse.statut >= 400) { UI.remplir(zone, UI.html`<p class="erreur-champ">${reponse.message}</p>`); return; }
    fiche = reponse.donnees;
    UI.remplir(zone, InstallationFiche.rendre(fiche));
  }

  // Étape « Dossier » (D131, T171) : copie dans C:\Prevo, chaque fichier vérifié, puis Prévo se relance depuis là ;
  // l'assistant reprend à la même étape (le brouillon est dans la copie). L'ancien dossier n'est pas supprimé.
  async function deplacerPrevo(section) {
    const erreur = UI.$('#inst-deplacer-erreur', section);
    erreur.hidden = true;
    const reponse = await appeler('deplacer', { vers: etat.dossier_conseille });
    if (!reponse.statut || reponse.statut >= 400) { erreur.textContent = reponse.message; erreur.hidden = false; return; }
    const vers = reponse.donnees.vers;
    await attendreRelance(section, reponse.donnees.relance,
      I18n.t('installation.deplacer_prevo.prevo_ete_copie_fichiers', { copie: reponse.donnees.copie, vers, dossier: etat.dossier }),
      location.hash, serveurRelanceDepuis(vers));
  }

  // « Rester ici » : refus mémorisé dans le brouillon (deplacement_refuse) ; la proposition n'est plus montrée.
  async function resterIci(section) {
    const erreur = UI.$('#inst-deplacer-erreur', section);
    erreur.hidden = true;
    const reponse = await appeler('deplacer', { rester: true });
    if (!reponse.statut || reponse.statut >= 400) { erreur.textContent = reponse.message; erreur.hidden = false; return; }
    reprendre(reponse.donnees);
    UI.$('#inst-dossier', section).hidden = true;
  }

  async function terminerInstallation(section, formulaire) {
    const corps = formulaire && formulaire.lire ? formulaire.lire(section) : {};
    const reponse = await appeler('terminer', corps);
    if (!reponse.statut || reponse.statut >= 400) { montrerErreur('recapitulatif', reponse.message); return; }
    await attendreRelance(section, reponse.donnees.relance, I18n.t('installation.terminer_installation.configuration_ecrite', { fichier: reponse.donnees.fichier }), '#/accueil', serveurConfigure);
  }

  // Après « terminer » : le serveur relancé répond à /api/info avec l'installation faite (ou 401 : comptes exigés,
  // donc configuré).
  async function serveurConfigure() {
    const reponse = await fetch('/api/info', { cache: 'no-store', credentials: 'same-origin' });
    const donnees = reponse.ok ? await reponse.json().catch(() => null) : null;
    return reponse.status === 401 || Boolean(donnees && donnees.installation_a_faire === false);
  }

  // Après « deplacer » : le serveur relancé dit tourner depuis le nouveau dossier (GET etat, casse ignorée : Windows).
  function serveurRelanceDepuis(vers) {
    return async () => {
      const reponse = await appeler('etat');
      return Boolean(reponse.statut === 200 && reponse.donnees && String(reponse.donnees.dossier || '').toLowerCase() === String(vers).toLowerCase());
    };
  }

  // Le serveur se relance : « pret » (une fonction async) interrogé toutes les 2 s jusqu'à ce qu'il dise vrai, puis la
  // page se recharge sur « route » ; message après 60 s.
  async function attendreRelance(section, relance, message, route, pret) {
    const zone = UI.$('#inst-attente', section) || UI.$('#inst-attente');
    UI.$$('.btn', section).forEach((bouton) => { bouton.disabled = true; });
    zone.hidden = false;
    const lanceur = (fiche && fiche.lanceur) || 'Lancer_GMAO.bat';
    UI.remplir(zone, UI.html`<p class="chargement" role="status">${message} ${relance ? I18n.t('installation.attendre_relance.prevo_relance_patientez') : I18n.t('installation.attendre_relance.relancez_prevo_main_page', { lanceur })}</p>`);
    const debut = Date.now();
    while (Date.now() - debut < DELAI_RELANCE_MS) {
      await new Promise((suite) => { setTimeout(suite, INTERVALLE_RELANCE_MS); });
      try {
        if (await pret()) {
          location.replace(location.pathname + route);
          location.reload();
          return;
        }
      } catch (erreur) { /* le serveur redémarre : on réessaie */ }
    }
    const adresseLocale = (fiche && fiche.adresse_locale) || location.origin + '/';
    UI.remplir(zone, UI.html`<p class="erreur-champ" role="alert">${I18n.html('installation.attendre_relance.serveur_revient_pas_relancez', { lanceur, adresseLocale })}</p>`);
    UI.$$('.btn', section).forEach((bouton) => { bouton.disabled = false; });
  }

  // ===========================================================================================
  // 5. Entrée : l'écran est montré par App ; GET etat replace l'assistant à la première étape à faire
  // ===========================================================================================

  function estRoute(hash) {
    return MOTIF_ROUTE.test(hash || '');
  }

  function premiereEtapeAFaire() {
    for (let i = 1; i < ETAPES.length - 1; i += 1) {
      if (etatEtape(ETAPES[i].cle) === 'a_faire') return i;
    }
    return ETAPES.length - 1;
  }

  async function ficheSeule() {
    const zone = UI.$('#installation-contenu');
    const reponse = await appeler('fiche');
    const contenu = reponse.statut >= 400 || !reponse.statut ? UI.html`<p class="erreur-champ">${reponse.message}</p>` : InstallationFiche.rendre(reponse.donnees);
    UI.remplir(zone, [contenu, UI.html`<div class="actions"><a class="btn btn-secondaire" href="#/installation" id="inst-retour-assistant">${I18n.t('installation.fiche_seule.retour_assistant')}</a></div>`]);
    UI.$('#inst-retour-assistant').addEventListener('click', (evenement) => { evenement.preventDefault(); location.hash = '#/installation'; location.reload(); });
  }

  /** Conduit l'assistant (écran déjà montré par App). Promesse : résolue si l'assistant est quitté sans terminer. */
  async function ouvrir() {
    const quitter = UI.$('#installation-quitter');
    quitter.onclick = (evenement) => { evenement.preventDefault(); const fin = resoudre; resoudre = null; if (fin) fin('quitter'); };
    const promesse = new Promise((fin) => { resoudre = fin; });
    if (MOTIF_ROUTE_FICHE.test(location.hash)) { await ficheSeule(); return promesse; }
    const reponse = await appeler('etat');
    if (!reponse.statut || reponse.statut >= 400) {
      UI.remplir(UI.$('#installation-contenu'), UI.html`<p class="erreur-champ" role="alert">${reponse.message}</p>`);
      return promesse;
    }
    etat = reponse.donnees;
    index = etat.brouillon ? premiereEtapeAFaire() : 0;
    sautees = [];
    rendre();
    return promesse;
  }

  return { ouvrir, estRoute, ETAPES };
})();
