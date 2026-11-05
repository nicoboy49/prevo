'use strict';
// Dictee — dictée vocale sur les champs de texte long marqués data-dictee (ARCHITECTURE.md §17.6 ;
// brief §11) : bouton micro, avertissement à la première utilisation sur le poste (la voix part chez
// Google ou Microsoft, sauf reconnaissance sur l'appareil), texte ajouté à la fin du champ sans rien
// effacer, désactivable dans « Ce poste ». Sur un téléphone sans page sécurisée : une aide rappelle la
// dictée du clavier.
//    1. Réglages du poste (localStorage « prevo.dictee »)
//    2. Disponibilité (reconnaissance du navigateur, page sécurisée, reconnaissance sur l'appareil)
//    3. Boutons micro et aide « micro du clavier » (equiper)
//    4. Écoute : avertissement, démarrage, résultats, erreurs, arrêt

const Dictee = (() => {

  const LANGUE = 'fr-FR';
  const CLE_REGLAGES = 'prevo.dictee';

  let ecoute = null;       // { reconnaissance, champ, bouton } : une seule dictée à la fois

  // Textes lus au moment de les montrer (jamais figés au chargement du module).
  function avertissementNuage() {
    return I18n.t('dictee.avertissement_nuage.chrome_edge_voix_envoyee');
  }

  function avertissementLocal() {
    return I18n.t('dictee.avertissement_local.voix_transcrite_pc_envoyee');
  }

  function aideClavier() {
    return I18n.t('dictee.aide_clavier.dictee_utilisez_micro_clavier');
  }

  /** Message d'une erreur de la reconnaissance (evenement.error), ou null si le code n'a pas de message à lui. */
  function messageErreur(code) {
    switch (code) {
      case 'not-allowed':
      case 'service-not-allowed':
        return I18n.t('dictee.message_erreur.micro_refuse_autorisez_micro');
      case 'audio-capture':
        return I18n.t('dictee.message_erreur.aucun_micro_trouve_appareil');
      case 'network':
        return I18n.t('dictee.message_erreur.dictee_impossible_pas_connexion');
      case 'no-speech':
        return I18n.t('dictee.message_erreur.aucune_parole_entendue_dictee');
      case 'language-not-supported':
        return I18n.t('dictee.message_erreur.francais_pas_propose_reconnaissance');
      default:
        return null;
    }
  }

  // ===========================================================================================
  // 1. Réglages du poste
  // ===========================================================================================

  /** { active, avertie } ; avertie : '' (jamais), 'local' (transcription sur ce PC annoncée) ou 'nuage'
   *  (Google ou Microsoft annoncés ; true des premières versions = 'nuage'). Lecture protégée : défauts. */
  function reglages() {
    let lus = {};
    try { lus = JSON.parse(window.localStorage.getItem(CLE_REGLAGES) || '{}') || {}; } catch (erreur) { lus = {}; }
    const avertie = lus.avertie === true || lus.avertie === 'nuage' ? 'nuage' : (lus.avertie === 'local' ? 'local' : '');
    return { active: lus.active !== false, avertie };
  }

  /** Vrai si l'avertissement du lieu de transcription a déjà été donné : « nuage » vaut aussi pour « local ». */
  function dejaAverti(locale) {
    const avertie = reglages().avertie;
    return avertie === 'nuage' || (locale && avertie === 'local');
  }

  function enregistrerReglages(modifications) {
    const nouveaux = Object.assign(reglages(), modifications || {});
    try { window.localStorage.setItem(CLE_REGLAGES, JSON.stringify(nouveaux)); } catch (erreur) { /* sans mémoire */ }
    return nouveaux;
  }

  // ===========================================================================================
  // 2. Disponibilité
  // ===========================================================================================

  function classeReconnaissance() {
    return window.SpeechRecognition || window.webkitSpeechRecognition || null;
  }

  /** Vrai si le navigateur propose la dictée ici : reconnaissance présente et page sécurisée. */
  function prisEnCharge() {
    return Boolean(classeReconnaissance()) && window.isSecureContext === true;
  }

  /** Vrai si un bouton micro doit être proposé : pris en charge et active sur le poste. */
  function disponible() {
    return prisEnCharge() && reglages().active;
  }

  function appareilTactile() {
    return typeof window.matchMedia === 'function' && window.matchMedia('(pointer: coarse)').matches;
  }

  /**
   * Vrai si le navigateur transcrit le français sur l'appareil même (rien n'est envoyé) : demandé à
   * SpeechRecognition.available() (expérimental) ; toute erreur ou absence → faux (prudence).
   */
  async function transcriptionLocale() {
    const Classe = classeReconnaissance();
    if (!Classe || typeof Classe.available !== 'function') return false;
    try {
      return (await Classe.available({ langs: [LANGUE], processLocally: true })) === 'available';
    } catch (erreur) {
      return false;
    }
  }

  // ===========================================================================================
  // 3. Boutons micro et aide « micro du clavier »
  // ===========================================================================================

  function boutonPour(champ) {
    const bouton = UI.element(UI.html`<button type="button" class="btn btn-fantome btn-icone dictee-bouton"
      aria-pressed="false" title="${I18n.t('dictee.bouton_pour.dicter')}" aria-label="${I18n.t('dictee.bouton_pour.dicter_champ')}">${UI.icone('micro')}<span class="dictee-libelle">${I18n.t('dictee.bouton_pour.dicter')}</span></button>`);
    bouton.addEventListener('click', () => basculer(champ, bouton));
    return bouton;
  }

  /**
   * Pose un bouton micro après chaque champ [data-dictee] de `racine` qui n'en a pas encore (après
   * chaque affichage d'écran et à l'ouverture d'une fenêtre). Sans dictée possible sur un appareil
   * tactile (navigateur sans reconnaissance vocale, comme Firefox sur Android ; ou page non sécurisée,
   * ce qu'un téléphone ne voit plus depuis la porte d'entrée du lot 7, §22.6), une aide discrète sous le
   * premier champ dicté rappelle la dictée du clavier.
   */
  function equiper(racine) {
    const zone = racine || document;
    if (ecoute && !document.contains(ecoute.champ)) arreter();     // l'écran a changé pendant une dictée
    const champs = Array.from(zone.querySelectorAll('[data-dictee]'));
    if (!champs.length) return;
    if (!disponible()) {
      const aideUtile = reglages().active && appareilTactile() && !prisEnCharge();
      if (aideUtile && !zone.querySelector('.dictee-aide')) {
        champs[0].insertAdjacentElement('afterend', UI.element(UI.html`<p class="aide dictee-aide">${aideClavier()}</p>`));
      }
      return;
    }
    champs.forEach((champ) => {
      if (champ.dataset.dicteeEquipe) return;
      champ.dataset.dicteeEquipe = '1';
      champ.insertAdjacentElement('afterend', boutonPour(champ));
    });
  }

  let observateur = null;

  /**
   * Équipe la page entière puis chaque partie ajoutée ensuite (écrans, onglets, encarts, fenêtres) :
   * un champ dicté reçoit son micro où qu'il apparaisse. Une dictée dont le champ disparaît s'arrête.
   * Appelé une fois au démarrage par App.
   */
  function surveiller(racine) {
    const zone = racine || document.body;
    equiper(zone);
    if (observateur || typeof MutationObserver === 'undefined') return;
    observateur = new MutationObserver((changements) => {
      changements.forEach((changement) => changement.addedNodes.forEach((noeud) => {
        if (noeud.nodeType !== 1) return;
        if (noeud.matches('[data-dictee]') && noeud.parentElement) equiper(noeud.parentElement);
        else if (noeud.querySelector('[data-dictee]')) equiper(noeud);
      }));
      if (ecoute && !ecoute.champ.isConnected) arreter();
    });
    observateur.observe(zone, { childList: true, subtree: true });
  }

  /** Retire les boutons micro (dictée désactivée sur le poste). */
  function retirerBoutons() {
    document.querySelectorAll('.dictee-bouton').forEach((bouton) => bouton.remove());
    document.querySelectorAll('[data-dictee-equipe]').forEach((champ) => { delete champ.dataset.dicteeEquipe; });
  }

  // ===========================================================================================
  // 4. Écoute
  // ===========================================================================================

  /** Première utilisation sur le poste : « Continuer » (vrai), « Désactiver la dictée » ou fermeture (faux). */
  async function avertir(locale) {
    const choix = await UI.fenetre({
      titre: I18n.t('dictee.avertir.dictee_vocale'),
      contenu: UI.element(UI.html`<div class="form-colonne dictee-avertissement">
        <p><b>${locale ? avertissementLocal() : avertissementNuage()}</b></p>
        <p>${I18n.t('dictee.avertir.pouvez_desactiver_dictee_poste')}</p>
      </div>`),
      boutons: [{ libelle: I18n.t('dictee.avertir.desactiver_dictee'), valeur: 'desactiver', classe: 'btn-fantome' },
        { libelle: I18n.t('dictee.avertir.continuer'), valeur: 'continuer', classe: 'btn-primaire', defaut: true }],
    });
    if (choix === 'desactiver') {
      enregistrerReglages({ active: false });
      retirerBoutons();
      UI.toast(I18n.t('dictee.avertir.dictee_desactivee_poste_reactivable'), 'info');
      return false;
    }
    if (choix !== 'continuer') return false;
    enregistrerReglages({ avertie: locale ? 'local' : 'nuage' });
    return true;
  }

  /** « texte saisi » + « texte dicté » : une espace entre les deux, rien d'effacé. */
  function joindre(debut, ajout) {
    const dicte = String(ajout || '').trim();
    if (!dicte) return debut;
    return debut && !/\s$/.test(debut) ? debut + ' ' + dicte : debut + dicte;
  }

  function signalerSaisie(champ) {
    champ.dispatchEvent(new Event('input', { bubbles: true }));
  }

  function marquer(bouton, actif) {
    bouton.setAttribute('aria-pressed', actif ? 'true' : 'false');
    bouton.classList.toggle('dictee-active', actif);
    const libelle = bouton.querySelector('.dictee-libelle');
    if (libelle) libelle.textContent = actif ? I18n.t('dictee.marquer.arreter') : I18n.t('dictee.bouton_pour.dicter');
  }

  function demarrer(champ, bouton, locale) {
    const Classe = classeReconnaissance();
    const reconnaissance = new Classe();
    reconnaissance.lang = LANGUE;
    reconnaissance.interimResults = true;
    reconnaissance.continuous = true;
    if (locale) reconnaissance.processLocally = true;
    let debut = champ.value;
    let definitif = '';
    let ecrit = champ.value;                            // dernière valeur posée par la dictée
    // Champ changé sans la dictée (frappe, « Utiliser » de l'IA) : on repart de son contenu, jamais effacé.
    const rebaser = () => { if (champ.value !== ecrit) { debut = champ.value; definitif = ''; } };
    const ecrire = (valeur) => { champ.value = valeur; ecrit = valeur; signalerSaisie(champ); };
    reconnaissance.onresult = (evenement) => {
      rebaser();
      let provisoire = '';
      for (let rang = evenement.resultIndex; rang < evenement.results.length; rang += 1) {
        const morceau = evenement.results[rang][0].transcript;
        if (evenement.results[rang].isFinal) definitif += morceau;
        else provisoire += morceau;
      }
      ecrire(joindre(debut, definitif + provisoire));
    };
    reconnaissance.onerror = (evenement) => {
      UI.toast(messageErreur(evenement.error) || I18n.t('dictee.demarrer.dictee_interrompue', { error: evenement.error }), 'attention');
    };
    reconnaissance.onend = () => {
      rebaser();
      ecrire(joindre(debut, definitif));                // les mots encore provisoires sont abandonnés
      marquer(bouton, false);
      if (ecoute && ecoute.reconnaissance === reconnaissance) ecoute = null;
    };
    ecoute = { reconnaissance, champ, bouton };
    marquer(bouton, true);
    try {
      reconnaissance.start();
    } catch (erreur) {
      ecoute = null;
      marquer(bouton, false);
      UI.toast(I18n.t('dictee.demarrer.dictee_impossible', { raison: (erreur && erreur.message) || I18n.t('dictee.demarrer.erreur_inconnue') }), 'attention');
    }
  }

  /** Clic sur un micro : arrête la dictée de ce champ, ou en démarre une (après l'avertissement). */
  async function basculer(champ, bouton) {
    if (ecoute && ecoute.champ === champ) {
      ecoute.reconnaissance.stop();
      return;
    }
    arreter();
    const locale = await transcriptionLocale();
    if (!dejaAverti(locale) && !await avertir(locale)) return;
    demarrer(champ, bouton, locale);
  }

  /** Arrête la dictée en cours (changement d'écran). */
  function arreter() {
    if (!ecoute) return;
    try { ecoute.reconnaissance.stop(); } catch (erreur) { /* déjà arrêtée */ }
    ecoute = null;
  }

  /** Arrête la dictée seulement si son champ est dans `racine` (fermeture d'une fenêtre). */
  function arreterDans(racine) {
    if (ecoute && racine && racine.contains(ecoute.champ)) arreter();
  }

  return {
    LANGUE,
    /** Textes de l'avertissement et de l'aide, lus dans la langue du moment (accesseurs). */
    get AVERTISSEMENT_NUAGE() { return avertissementNuage(); },
    get AVERTISSEMENT_LOCAL() { return avertissementLocal(); },
    get AIDE_CLAVIER() { return aideClavier(); },
    reglages, enregistrerReglages, prisEnCharge, disponible, transcriptionLocale, equiper, surveiller, retirerBoutons,
    arreter, arreterDans,
  };
})();
