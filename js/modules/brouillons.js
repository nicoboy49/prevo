'use strict';
// Brouillons — saisie gardée sur l'appareil (T329, décisions de Nicolas du 07/11) : la déclaration de panne
// (#/di/nouvelle) et le compte rendu d'un OT survivent à un onglet déchargé par le navigateur (téléphone resté en
// veille), à un rechargement de la page ou à une session expirée. Règles :
//   - un brouillon est lié au compte qui l'a tapé (sans comptes : au profil du poste) et n'est jamais montré à un
//     autre : sa clé porte la base et l'auteur (App.porteeDesBrouillons) ; aucun brouillon dans la démo ni en lecture
//     seule ;
//   - il est effacé dès que la saisie est enregistrée, ou au bout de 7 jours (purgés à l'ouverture de Prévo) ;
//   - rien ne part au serveur : localStorage de ce navigateur seulement, clé « prevo.brouillon|<base>|<auteur>|<nom> »,
//     valeur { le (ms), valeurs, depart, … }.
// Un brouillon n'est écrit que s'il diffère de la saisie de départ (les valeurs enregistrées) ; revenu à elle, il est
// effacé. Il est écrit 400 ms après la dernière frappe, et aussitôt quand la page passe en arrière-plan (veille,
// autre onglet, fermeture). Une photo n'y est jamais gardée (seulement le fait qu'il y en avait une).
//    1. Stockage (lire, effacer, purger)
//    2. Champs d'un formulaire (valeurs, poser, egales)
//    3. Suivi d'un formulaire (suivre)
//    4. Bandeaux (repris, non repris)

const Brouillons = (() => {

  const PREFIXE = 'prevo.brouillon|';
  const DUREE_MS = 7 * 24 * 60 * 60 * 1000;
  const DELAI_MS = 400;
  const suivis = new Set();                    // suivis en cours (écrits quand la page passe en arrière-plan)

  // ===========================================================================================
  // 1. Stockage
  // ===========================================================================================

  function memoire() {
    try { return window.localStorage; } catch (erreur) { return null; }  // navigation privée stricte, réglage
  }

  // Clé du brouillon `nom` pour l'auteur connecté ; '' quand les brouillons ne valent pas (démo, lecture seule…).
  function cle(nom) {
    const portee = typeof App !== 'undefined' && typeof App.porteeDesBrouillons === 'function'
      ? App.porteeDesBrouillons() : '';
    return portee && nom ? PREFIXE + portee + '|' + nom : '';
  }

  function valable(contenu, maintenant) {
    return Boolean(contenu) && typeof contenu === 'object' && typeof contenu.le === 'number'
      && Boolean(contenu.valeurs) && typeof contenu.valeurs === 'object' && maintenant - contenu.le <= DUREE_MS;
  }

  function relire(stock, cleBrouillon) {
    try { return JSON.parse(stock.getItem(cleBrouillon) || 'null'); } catch (erreur) { return undefined; }
  }

  function retirer(stock, cleBrouillon) {
    try { stock.removeItem(cleBrouillon); } catch (erreur) { /* rien à effacer */ }
  }

  /** Le brouillon `nom` de l'auteur connecté ({ le, valeurs, depart, … }), ou null ; périmé ou illisible : effacé. */
  function lire(nom) {
    const stock = memoire();
    const cleBrouillon = cle(nom);
    if (!stock || !cleBrouillon) return null;
    const contenu = relire(stock, cleBrouillon);
    if (contenu === null) return null;
    if (!valable(contenu, Date.now())) {
      retirer(stock, cleBrouillon);
      return null;
    }
    return contenu;
  }

  function ecrire(nom, valeurs, complement) {
    const stock = memoire();
    const cleBrouillon = cle(nom);
    if (!stock || !cleBrouillon) return false;
    try {
      stock.setItem(cleBrouillon, JSON.stringify(Object.assign({}, complement || {}, { le: Date.now(), valeurs })));
      return true;
    } catch (erreur) {                           // stockage plein ou refusé : la saisie reste à l'écran
      console.warn('Prévo : brouillon non gardé sur cet appareil (' + (erreur && erreur.message) + ').');
      return false;
    }
  }

  /** Efface le brouillon `nom` de l'auteur connecté. */
  function effacer(nom) {
    const stock = memoire();
    const cleBrouillon = cle(nom);
    if (stock && cleBrouillon) retirer(stock, cleBrouillon);
  }

  /** Efface tous les brouillons de cet appareil de plus de 7 jours (ou illisibles), de tous les auteurs. Rend leur nombre. */
  function purger() {
    const stock = memoire();
    if (!stock) return 0;
    const cles = [];
    try {
      for (let i = 0; i < stock.length; i += 1) {
        const cleLue = stock.key(i);
        if (cleLue && cleLue.startsWith(PREFIXE)) cles.push(cleLue);
      }
    } catch (erreur) {
      return 0;
    }
    const maintenant = Date.now();
    const perimees = cles.filter((cleLue) => !valable(relire(stock, cleLue), maintenant));
    perimees.forEach((cleLue) => retirer(stock, cleLue));
    return perimees.length;
  }

  // ===========================================================================================
  // 2. Champs d'un formulaire (par leur attribut name ; boutons radio : la valeur cochée ; case : '1' ou '0')
  // ===========================================================================================

  function controles(formulaire, nom) {
    return Array.from(formulaire.querySelectorAll('[name]')).filter((controle) => controle.name === nom);
  }

  /** { nom: valeur } des champs `noms` de `formulaire`, tels qu'à l'écran (texte non retouché). */
  function valeurs(formulaire, noms) {
    const resultat = {};
    noms.forEach((nom) => {
      const trouves = controles(formulaire, nom);
      if (!trouves.length) return;
      const premier = trouves[0];
      if (premier.type === 'radio') {
        const coche = trouves.find((controle) => controle.checked);
        resultat[nom] = coche ? coche.value : '';
      } else if (premier.type === 'checkbox') {
        resultat[nom] = premier.checked ? '1' : '0';
      } else {
        resultat[nom] = String(premier.value || '');
      }
    });
    return resultat;
  }

  /** Remet les valeurs dans les champs (sauf champs cachés et fichiers), avec les événements habituels (input, change). */
  function poser(formulaire, aPoser) {
    Object.keys(aPoser || {}).forEach((nom) => {
      const valeur = String(aPoser[nom] === null || aPoser[nom] === undefined ? '' : aPoser[nom]);
      controles(formulaire, nom).forEach((controle) => {
        if (controle.type === 'hidden' || controle.type === 'file') return;
        if (controle.type === 'radio' || controle.type === 'checkbox') {
          const coche = controle.type === 'radio' ? controle.value === valeur : valeur === '1';
          if (controle.checked === coche) return;
          controle.checked = coche;
          if (coche || controle.type === 'checkbox') controle.dispatchEvent(new Event('change', { bubbles: true }));
          return;
        }
        if (controle.value === valeur) return;
        controle.value = valeur;
        controle.dispatchEvent(new Event('input', { bubbles: true }));
        controle.dispatchEvent(new Event('change', { bubbles: true }));
      });
    });
  }

  /** Vrai si `a` et `b` ont les mêmes valeurs pour `noms` (absent = vide). */
  function egales(a, b, noms) {
    return noms.every((nom) => String((a || {})[nom] || '') === String((b || {})[nom] || ''));
  }

  // ===========================================================================================
  // 3. Suivi d'un formulaire
  // ===========================================================================================

  /**
   * Garde la saisie des champs `noms` de `formulaire` dans le brouillon `nom`. options :
   *   depart     : valeurs de départ (celles qui sont enregistrées) ; un brouillon égal à elles est effacé ;
   *   complement : objet, ou fonction qui le rend, gardé avec le brouillon (contexte : OT d'origine, photo…).
   * Renvoie { ecrireMaintenant(), terminer() } : terminer() (saisie enregistrée) arrête le suivi et efface le brouillon.
   */
  function suivre(formulaire, nom, noms, options) {
    const reglages = options || {};
    const depart = reglages.depart || {};
    let minuteur = null;
    let fini = false;

    function complement() {
      const extra = typeof reglages.complement === 'function' ? reglages.complement() : reglages.complement;
      return Object.assign({}, extra || {}, { depart });
    }

    // Écrit (ou efface) le brouillon. Un formulaire retiré de la page (écran quitté sans enregistrer) garde ses
    // valeurs : elles sont écrites une dernière fois, puis le suivi s'arrête.
    function ecrireMaintenant() {
      clearTimeout(minuteur);
      minuteur = null;
      if (fini) return;
      const actuelles = valeurs(formulaire, noms);
      if (egales(actuelles, depart, noms)) effacer(nom);
      else ecrire(nom, actuelles, complement());
      if (!formulaire.isConnected) arreter();
    }

    function planifier() {
      if (fini) return;
      clearTimeout(minuteur);
      minuteur = setTimeout(ecrireMaintenant, DELAI_MS);
    }

    function arreter() {
      fini = true;
      clearTimeout(minuteur);
      minuteur = null;
      formulaire.removeEventListener('input', planifier);
      formulaire.removeEventListener('change', planifier);
      suivis.delete(suivi);
    }

    const suivi = {
      ecrireMaintenant,
      terminer() { arreter(); effacer(nom); },
    };
    formulaire.addEventListener('input', planifier);
    formulaire.addEventListener('change', planifier);
    suivis.add(suivi);
    return suivi;
  }

  function toutEcrire() {
    Array.from(suivis).forEach((suivi) => suivi.ecrireMaintenant());
  }

  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') toutEcrire(); });
    window.addEventListener('pagehide', toutEcrire);
  }

  // ===========================================================================================
  // 4. Bandeaux
  // ===========================================================================================

  function quand(brouillon) {
    return UI.dateHeureFr(new Date(brouillon.le));
  }

  /**
   * Bandeau « brouillon repris » : quand il a été tapé, un avertissement facultatif (texte), et « Abandonner le
   * brouillon » (surAbandon). Rend l'élément à placer.
   */
  function bandeauRepris(brouillon, options) {
    const reglages = options || {};
    const bandeau = UI.bandeau(reglages.avertissement ? 'attention' : 'info', UI.html`
      ${I18n.t('commun.brouillon.repris', { quand: quand(brouillon) })}
      ${reglages.avertissement ? UI.html`<br>${reglages.avertissement}` : ''}
      <br><button type="button" class="btn btn-fantome brouillon-abandonner">${I18n.t('commun.brouillon.abandonner')}</button>`);
    bandeau.classList.add('brouillon-repris');
    UI.$('.brouillon-abandonner', bandeau).addEventListener('click', () => {
      if (typeof reglages.surAbandon === 'function') reglages.surAbandon();
      bandeau.remove();
    });
    return bandeau;
  }

  return { lire, effacer, purger, valeurs, poser, egales, suivre, bandeauRepris, quand, DUREE_MS };
})();
