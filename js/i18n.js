'use strict';
// I18n : moteur de traduction de Prévo (chantier multilingue, décisions D145 à D166 ; contrat du Lot 2).
// Contrat : docs/ARCHITECTURE.md §1 (ordre de chargement : avant js/schema.js, dans index.html et acces/porte.html).
// Les langues sont déclarées par js/i18n/langues.js (I18n.declarer) ; chaque langue enregistre ses textes par
// js/i18n/<code>.js (I18n.ajouter, un bloc par section) et son aide longue, à part, par js/i18n/aide/<code>.js (clés
// aide.*). Le français est la langue de référence et de repli. La langue active (autre que le français) est chargée
// avant js/schema.js par js/i18n-chargeur.js.
//
// Règles :
// - script classique, sans dépendance, compatible file:// ;
// - I18n.t(cle, valeurs) rend du TEXTE brut : « {nom} » est remplacé par valeurs.nom ; une entrée de pluriel
//   ({ one: '{n} ordre', other: '{n} ordres' }, catégories CLDR) est choisie par Intl.PluralRules de la langue du
//   texte sur valeurs.n (catégorie absente : other) ;
// - I18n.html(cle, valeurs) rend un fragment sûr pour UI.html et UI.remplir : le balisage écrit dans le dictionnaire
//   est gardé, chaque valeur insérée est échappée (sauf un fragment déjà sûr, UI.html ou I18n.html, gardé tel quel) ;
// - repli : langue active, puis français, puis la clé elle-même ; console.warn une fois par clé (texte pris en
//   français faute de traduction, ou clé absente partout). Les clés aide.* se replient sur le français sans
//   avertissement (l'aide longue n'existe pas dans toutes les langues : décision de Nicolas) ;
// - un texte se lit au moment de l'afficher, jamais dans une constante calculée au chargement d'un module (sinon le
//   changement de langue demanderait de recharger la page).

const I18n = (function () {

  const LANGUE_DE_REFERENCE = 'fr';
  const PREFIXE_AIDE = 'aide.';
  const CATEGORIE_PAR_DEFAUT = 'other';
  const MOTIF_CODE = /^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$/;     // fr, en, pt-PT…
  const MOTIF_VARIABLE = /\{([A-Za-z_][A-Za-z0-9_]*)\}/g;

  const dictionnaires = Object.create(null);   // code → { cle: texte | { one: …, other: … } }
  const declarees = [];                         // déclarations de js/i18n/langues.js, dans l'ordre
  const reglesPluriel = Object.create(null);    // locale → Intl.PluralRules
  const averties = new Set();                   // clés déjà signalées par console.warn
  let langueActive = LANGUE_DE_REFERENCE;

  // ===========================================================================================
  // Langues et dictionnaires
  // ===========================================================================================

  function verifierCode(code, fonction) {
    if (typeof code !== 'string' || !MOTIF_CODE.test(code)) {
      throw new TypeError('I18n.' + fonction + ' : code de langue invalide (' + String(code) + ').');
    }
  }

  /** Déclare une langue : { code: 'fr', nom: 'Français', locale: 'fr-FR', statut: 'reference' } (redite : remplace). */
  function declarer(langue) {
    if (!langue || typeof langue !== 'object') throw new TypeError('I18n.declarer : déclaration attendue.');
    verifierCode(langue.code, 'declarer');
    const copie = Object.assign({}, langue);
    const position = declarees.findIndex((existante) => existante.code === copie.code);
    if (position >= 0) declarees[position] = copie; else declarees.push(copie);
  }

  /** Fusionne des clés dans le dictionnaire de la langue `code` (plusieurs appels permis, la dernière valeur gagne). */
  function ajouter(code, dictionnaire) {
    verifierCode(code, 'ajouter');
    if (!dictionnaire || typeof dictionnaire !== 'object' || Array.isArray(dictionnaire)) {
      throw new TypeError('I18n.ajouter : dictionnaire attendu pour « ' + code + ' ».');
    }
    const cible = dictionnaires[code] || (dictionnaires[code] = Object.create(null));
    Object.keys(dictionnaire).forEach((cle) => { cible[cle] = dictionnaire[cle]; });
  }

  function declaration(code) {
    return declarees.find((langue) => langue.code === code) || null;
  }

  /**
   * Rend `code` langue active s'il est déclaré (le français l'est toujours) ; vrai si c'est fait, faux sinon (la
   * langue active ne change pas). L'attribut lang de <html> prend ce code (D147 ; 'fr' par défaut, écrit dans la
   * page). Sert à js/i18n-chargeur.js : le sélecteur de langue (UI.selecteurLangue) retient le choix puis recharge
   * la page, il ne change pas de langue en cours de route.
   */
  function choisir(code) {
    if (code !== LANGUE_DE_REFERENCE && !declaration(code)) return false;
    langueActive = code;
    if (typeof document !== 'undefined' && document.documentElement) document.documentElement.lang = code;
    return true;
  }

  // ===========================================================================================
  // Recherche d'une clé (repli) et pluriels
  // ===========================================================================================

  function avertir(cle, raison) {
    if (averties.has(cle)) return;
    averties.add(cle);
    console.warn('Prévo (traduction) : clé « ' + cle + ' » ' + raison + '.');
  }

  // { valeur, langue } du texte à utiliser, ou null si la clé n'existe nulle part (la clé est alors affichée).
  function trouver(cle, enReference) {
    if (enReference) {
      const base = dictionnaires[LANGUE_DE_REFERENCE];
      return base && cle in base ? { valeur: base[cle], langue: LANGUE_DE_REFERENCE } : null;
    }
    const active = dictionnaires[langueActive];
    if (active && cle in active) return { valeur: active[cle], langue: langueActive };
    const reference = dictionnaires[LANGUE_DE_REFERENCE];
    if (reference && cle in reference) {
      if (langueActive !== LANGUE_DE_REFERENCE && cle.indexOf(PREFIXE_AIDE) !== 0) {
        avertir(cle, 'absente en « ' + langueActive + ' » : texte français affiché');
      }
      return { valeur: reference[cle], langue: LANGUE_DE_REFERENCE };
    }
    avertir(cle, 'absente de tous les dictionnaires : la clé est affichée');
    return null;
  }

  function regles(code) {
    const langue = declaration(code);
    const locale = (langue && langue.locale) || code;
    if (!reglesPluriel[locale]) {
      try {
        reglesPluriel[locale] = new Intl.PluralRules(locale);
      } catch (erreur) {                         // locale inconnue d'Intl : règles du français
        reglesPluriel[locale] = new Intl.PluralRules(LANGUE_DE_REFERENCE);
      }
    }
    return reglesPluriel[locale];
  }

  // Forme d'une entrée de pluriel pour le nombre n (catégorie absente, ou n absent : other).
  function formePlurielle(entree, n, code) {
    let categorie = CATEGORIE_PAR_DEFAUT;
    const nombre = typeof n === 'number' ? n : (n === undefined || n === null || n === '' ? NaN : Number(n));
    if (Number.isFinite(nombre)) categorie = regles(code).select(nombre);
    if (typeof entree[categorie] === 'string') return entree[categorie];
    if (typeof entree[CATEGORIE_PAR_DEFAUT] === 'string') return entree[CATEGORIE_PAR_DEFAUT];
    const premiere = Object.keys(entree).find((nom) => typeof entree[nom] === 'string');
    return premiere ? entree[premiere] : '';
  }

  // Texte du dictionnaire (balisage compris, variables pas encore remplacées) ; null si la clé n'existe nulle part.
  function gabarit(cle, valeurs, enReference) {
    const trouve = trouver(String(cle), enReference);
    if (!trouve) return null;
    const entree = trouve.valeur;
    if (entree && typeof entree === 'object') return formePlurielle(entree, valeurs && valeurs.n, trouve.langue);
    return entree === null || entree === undefined ? '' : String(entree);
  }

  // Remplace chaque {nom} connu de `valeurs` par convertir(valeur) ; une variable sans valeur reste écrite.
  function interpoler(texte, valeurs, convertir) {
    if (!valeurs || typeof valeurs !== 'object') return texte;
    return texte.replace(MOTIF_VARIABLE, (tout, nom) => {
      const connue = Object.prototype.hasOwnProperty.call(valeurs, nom) && valeurs[nom] !== undefined;
      return connue ? convertir(valeurs[nom]) : tout;
    });
  }

  // ===========================================================================================
  // Textes : t (brut) et html (fragment sûr)
  // ===========================================================================================

  function enTexte(valeur) {
    return valeur === null ? '' : String(valeur);
  }

  /** Texte brut de la clé dans la langue active (repli : français, puis la clé). */
  function t(cle, valeurs) {
    const texte = gabarit(cle, valeurs);
    return texte === null ? String(cle) : interpoler(texte, valeurs, enTexte);
  }

  /** Texte de la clé dans la langue de référence (français), quelle que soit la langue active, sans avertissement. */
  function reference(cle, valeurs) {
    const texte = gabarit(cle, valeurs, true);
    return texte === null ? String(cle) : interpoler(texte, valeurs, enTexte);
  }

  // ===========================================================================================
  // Textes écrits dans les données (D156) : langue de l'installation, jamais celle de l'écran
  // ===========================================================================================

  // D156 ; au Lot 4, langue de l'installation (langue_defaut) : d'ici là, la langue de référence.
  function langueDesDonnees() {
    return LANGUE_DE_REFERENCE;
  }

  /**
   * Texte brut de la clé dans la langue de l'installation, pour ce que l'appli écrit dans les données (journal,
   * titres et motifs pré-remplis, raisons du journal du wiki…), quelle que soit la langue de l'écran (D156).
   */
  function donnees(cle, valeurs) {
    return reference(cle, valeurs);       // D156 ; au Lot 4, langue de l'installation (langue_defaut)
  }

  /**
   * Exécute `fonction` (synchrone) avec la langue de l'installation pour langue active, puis rend la langue de
   * l'écran, même sur une erreur : I18n.t, I18n.html et I18n.locale y donnent ce qui s'écrit dans les données.
   * Pour un texte composé par d'autres fonctions (rapport figé, raisons d'un contrôle, nombres mis en forme) ; un
   * texte d'une seule clé passe par I18n.donnees. Une fonction asynchrone est refusée (TypeError) : sa suite
   * s'exécuterait après le retour à la langue de l'écran.
   */
  function enLangueDesDonnees(fonction) {
    const ecran = langueActive;
    langueActive = langueDesDonnees();
    let resultat;
    try {
      resultat = fonction();
    } finally {
      langueActive = ecran;
    }
    if (resultat && typeof resultat.then === 'function') {
      throw new TypeError('I18n.enLangueDesDonnees : fonction synchrone attendue.');
    }
    return resultat;
  }

  const REMPLACEMENTS_HTML = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

  function echapper(valeur) {
    return String(valeur).replace(/[&<>"']/g, (caractere) => REMPLACEMENTS_HTML[caractere]);
  }

  // Page sans UI (js/interface.js n'y est pas chargé : acces/porte.html) : fragment qui se convertit en chaîne tout
  // seul (element.innerHTML = I18n.html(…) fonctionne).
  class FragmentHtml {
    constructor(texte) { this.texte = texte; }
    toString() { return this.texte; }
  }

  function uiPresent() {
    return typeof UI !== 'undefined' && UI && typeof UI.brut === 'function' && typeof UI.estSur === 'function';
  }

  // Même conversion que UI.html : fragment sûr gardé tel quel, tableau joint, null / undefined / false ignorés, le
  // reste échappé.
  function enHtml(valeur) {
    if (valeur instanceof FragmentHtml || (uiPresent() && UI.estSur(valeur))) return String(valeur);
    if (Array.isArray(valeur)) return valeur.map(enHtml).join('');
    if (valeur === null || valeur === undefined || valeur === false) return '';
    return echapper(valeur);
  }

  /**
   * Fragment sûr de la clé : balisage du dictionnaire gardé, valeurs échappées. Avec UI chargé, c'est un fragment de
   * UI.brut (accepté par UI.html et UI.remplir sans double échappement) ; sinon un objet qui se convertit en chaîne.
   * Une clé absente partout donne la clé, échappée.
   */
  function html(cle, valeurs) {
    const texte = gabarit(cle, valeurs);
    const resultat = texte === null ? echapper(String(cle)) : interpoler(texte, valeurs, enHtml);
    return uiPresent() ? UI.brut(resultat) : new FragmentHtml(resultat);
  }

  // ===========================================================================================
  // Textes statiques de index.html : data-i18n="cle", data-i18n-attr="title:cle1;placeholder:cle2"
  // ===========================================================================================

  /** Applique les clés des attributs data-i18n (texte) et data-i18n-attr (attributs) de `racine` et de ses enfants. */
  function appliquer(racine) {
    const base = racine || document;
    const selecteur = '[data-i18n], [data-i18n-attr]';
    const elements = Array.from(base.querySelectorAll(selecteur));
    if (base.nodeType === 1 && base.matches(selecteur)) elements.unshift(base);
    elements.forEach((element) => {
      const cle = element.getAttribute('data-i18n');
      if (cle) element.textContent = t(cle.trim());
      const attributs = element.getAttribute('data-i18n-attr');
      if (!attributs) return;
      attributs.split(';').forEach((paire) => {
        const position = paire.indexOf(':');
        const nom = paire.slice(0, position).trim();
        const cleAttribut = paire.slice(position + 1).trim();
        if (position > 0 && nom && cleAttribut) element.setAttribute(nom, t(cleAttribut));
      });
    });
    return elements.length;
  }

  return {
    ajouter: ajouter,
    declarer: declarer,
    choisir: choisir,
    t: t,
    reference: reference,
    donnees: donnees,
    enLangueDesDonnees: enLangueDesDonnees,
    html: html,
    appliquer: appliquer,
    /** Code de la langue active ('fr' tant que rien n'en choisit une autre). */
    get langue() { return langueActive; },
    /** Locale Intl de la langue active (nombres, montants, dates), 'fr-FR' si la langue n'en déclare pas. */
    get locale() {
      const langue = declarees.find((l) => l.code === langueActive);
      return (langue && langue.locale) || 'fr-FR';
    },
    /** Copie des langues déclarées par js/i18n/langues.js, dans l'ordre. */
    get langues() { return declarees.map((langue) => Object.assign({}, langue)); },
  };
})();
