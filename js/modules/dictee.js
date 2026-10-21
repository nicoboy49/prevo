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
  const AVERTISSEMENT_NUAGE = 'Dans Chrome et Edge, la voix est envoyée aux serveurs de Google ou Microsoft pour être transcrite.';
  const AVERTISSEMENT_LOCAL = 'La voix est transcrite sur ce PC : elle n\'est envoyée nulle part.';
  const AIDE_CLAVIER = 'Dictée : utilisez le micro du clavier de votre téléphone.';
  const MESSAGES_ERREUR = {
    'not-allowed': 'Micro refusé : autorisez le micro pour cette page, puis réessayez.',
    'service-not-allowed': 'Micro refusé : autorisez le micro pour cette page, puis réessayez.',
    'audio-capture': 'Aucun micro trouvé sur cet appareil.',
    network: 'Dictée impossible : pas de connexion au service de reconnaissance.',
    'no-speech': 'Aucune parole entendue : la dictée s\'est arrêtée.',
    'language-not-supported': 'Le français n\'est pas proposé par la reconnaissance de ce navigateur.',
  };

  let ecoute = null;       // { reconnaissance, champ, bouton } : une seule dictée à la fois

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
      aria-pressed="false" title="Dicter" aria-label="Dicter dans ce champ">${UI.icone('micro')}<span class="dictee-libelle">Dicter</span></button>`);
    bouton.addEventListener('click', () => basculer(champ, bouton));
    return bouton;
  }

  /**
   * Pose un bouton micro après chaque champ [data-dictee] de `racine` qui n'en a pas encore (après
   * chaque affichage d'écran et à l'ouverture d'une fenêtre). Sans dictée possible : sur un appareil
   * tactile dont la page n'est pas sécurisée (téléphone en http://192.168…), une aide discrète sous le
   * premier champ dicté rappelle la dictée du clavier.
   */
  function equiper(racine) {
    const zone = racine || document;
    if (ecoute && !document.contains(ecoute.champ)) arreter();     // l'écran a changé pendant une dictée
    const champs = Array.from(zone.querySelectorAll('[data-dictee]'));
    if (!champs.length) return;
    if (!disponible()) {
      const aideUtile = reglages().active && appareilTactile() && window.isSecureContext !== true;
      if (aideUtile && !zone.querySelector('.dictee-aide')) {
        champs[0].insertAdjacentElement('afterend', UI.element(UI.html`<p class="aide dictee-aide">${AIDE_CLAVIER}</p>`));
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
      titre: 'Dictée vocale',
      contenu: UI.element(UI.html`<div class="form-colonne dictee-avertissement">
        <p><b>${locale ? AVERTISSEMENT_LOCAL : AVERTISSEMENT_NUAGE}</b></p>
        <p>Vous pouvez désactiver la dictée sur ce poste maintenant, ou plus tard dans « Ce poste ».</p>
      </div>`),
      boutons: [{ libelle: 'Désactiver la dictée', valeur: 'desactiver', classe: 'btn-fantome' },
        { libelle: 'Continuer', valeur: 'continuer', classe: 'btn-primaire', defaut: true }],
    });
    if (choix === 'desactiver') {
      enregistrerReglages({ active: false });
      retirerBoutons();
      UI.toast('Dictée désactivée sur ce poste (réactivable dans « Ce poste »).', 'info');
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
    if (libelle) libelle.textContent = actif ? 'Arrêter' : 'Dicter';
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
      UI.toast(MESSAGES_ERREUR[evenement.error] || 'Dictée interrompue (' + evenement.error + ').', 'attention');
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
      UI.toast('Dictée impossible : ' + ((erreur && erreur.message) || 'erreur inconnue') + '.', 'attention');
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
    LANGUE, AVERTISSEMENT_NUAGE, AVERTISSEMENT_LOCAL, AIDE_CLAVIER,
    reglages, enregistrerReglages, prisEnCharge, disponible, transcriptionLocale, equiper, surveiller, retirerBoutons,
    arreter, arreterDans,
  };
})();
