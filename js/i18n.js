'use strict';
// I18n : moteur de traduction de Prévo (chantier multilingue, décisions D145 à D166 ; contrat du Lot 2).
// Contrat : docs/ARCHITECTURE.md §1 (ordre de chargement : avant js/schema.js, dans index.html et acces/porte.html).
// Les langues sont déclarées par js/i18n/langues.js (I18n.declarer) ; chaque langue enregistre ses textes par
// js/i18n/<code>.js (I18n.ajouter, un bloc par section) et son aide longue, à part, par js/i18n/aide/<code>.js (clés
// aide.*). Le français est la langue de référence et de repli. La langue active (autre que le français) est chargée
// avant js/schema.js par js/i18n-chargeur.js, qui choisit la langue à afficher (I18n.langueAAfficher : langue du compte
// connecté, T298 ; sinon choix du poste ; sinon langue de l'installation ; sinon langue du navigateur ou anglais, D150)
// et note la langue de l'installation (I18n.noterInstallation).
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
  let langueInstallation = LANGUE_DE_REFERENCE; // langue_defaut de parametres.csv (D149), vérifiée ; 'fr' sans elle

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

  // Code bien formé et déclaré (le français l'est toujours) ; toute autre valeur (vide, inconnue, mal formée) : faux.
  function estDeclaree(code) {
    return typeof code === 'string' && MOTIF_CODE.test(code) && (code === LANGUE_DE_REFERENCE || Boolean(declaration(code)));
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
  // Langue à afficher et langue de l'installation (Lot 4, T295 ; D148, D149)
  // ===========================================================================================

  /**
   * Langue à afficher (D148, D150) : 1. la langue du compte connecté (`langueDuCompte`, T298 : localStorage
   * « prevo.langue.compte », écrite par js/app.js à la connexion, effacée à la déconnexion) ; 2. sinon le choix du
   * poste ; 3. sinon la langue de l'installation ; 4. sinon, si `languesDuNavigateur` est donné (navigator.languages :
   * « sans réglage », démo ou première ouverture), la langue du navigateur (langueDuNavigateur, anglais à défaut) ;
   * 5. sinon le français. Chaque code est vérifié contre les langues déclarées : vide, inconnu ou mal formé, il est
   * ignoré. Sert à js/i18n-chargeur.js (avant js/schema.js), à js/app.js (paramètres lus : sans 3e argument) et au
   * sélecteur de langue (sans 4e argument : la langue qu'aurait le poste sans compte).
   */
  function langueAAfficher(choixDuPoste, installation, languesDuNavigateur, langueDuCompte) {
    const retenue = [langueDuCompte, choixDuPoste, installation].find(estDeclaree);
    if (retenue) return retenue;
    return Array.isArray(languesDuNavigateur) ? langueDuNavigateur(languesDuNavigateur) : LANGUE_DE_REFERENCE;
  }

  // Langues du navigateur ramenées à une langue déclarée (D150) : toute variante du portugais (pt-BR…) va au
  // portugais du Portugal. Clé : langue sans région, en minuscules.
  const VARIANTES_RAMENEES = { pt: 'pt-PT' };
  const LANGUE_SANS_REGLAGE = 'en';

  /**
   * Langue du navigateur (D150) : parcourt `langues` (navigator.languages, dans l'ordre de préférence) ; pour chacune,
   * essaie le code exact (casse ignorée) puis la langue sans région (pt-* : pt-PT), et rend la première déclarée.
   * Aucune ne l'est (ou liste vide, absente, valeurs non textuelles) : l'anglais. Fonction pure, aucune lecture du
   * navigateur.
   */
  function langueDuNavigateur(langues) {
    const declarations = declarees.map((langue) => langue.code);
    const trouver = (candidat) => declarations.find((code) => code.toLowerCase() === String(candidat).toLowerCase());
    const liste = Array.isArray(langues) ? langues : [];
    for (const etiquette of liste) {
      if (typeof etiquette !== 'string' || !etiquette.trim()) continue;
      const exacte = etiquette.trim().replace(/_/g, '-');
      const base = exacte.split('-')[0].toLowerCase();
      const code = trouver(exacte) || trouver(VARIANTES_RAMENEES[base] || base);
      if (code) return code;
    }
    return LANGUE_SANS_REGLAGE;
  }

  // Langue de l'installation posée par serveur.py dans la page qu'il sert (T297) : attribut data-langue-installation
  // de <html>, sur la porte des téléphones (toujours : langue_defaut, sinon « fr ») et sur index.html (seulement quand
  // langue_defaut est réglée). La page la connaît ainsi avant toute lecture des données (porte, écran de connexion).
  const ATTRIBUT_INSTALLATION = 'data-langue-installation';

  /** Langue de l'installation donnée par la page (attribut data-langue-installation de <html>), telle quelle, non
   *  vérifiée ; '' sans elle (page ouverte hors du serveur, base sans réglage). */
  function installationDeLaPage() {
    if (typeof document === 'undefined' || !document.documentElement) return '';
    return document.documentElement.getAttribute(ATTRIBUT_INSTALLATION) || '';
  }

  /**
   * Langue à afficher sur cette page (T297) : avec une langue de l'installation donnée par la page, langueAAfficher
   * (langue du compte, sinon choix du poste, sinon cette langue-là, sinon le français : une valeur non déclarée est
   * ignorée, sans erreur) ; elle passe avant celle retenue par ce navigateur et la langue du navigateur ne sert pas.
   * Sans elle : langueAAfficher(choixDuPoste, installationRetenue, languesDuNavigateur, langueDuCompte). Sert à
   * js/i18n-chargeur.js, à js/app.js (T298) et aux sélecteurs de langue (UI.selecteurLangue, acces/porte.js).
   */
  function langueDeLaPage(choixDuPoste, installationRetenue, languesDuNavigateur, langueDuCompte) {
    const donnee = installationDeLaPage();
    return donnee ? langueAAfficher(choixDuPoste, donnee, undefined, langueDuCompte)
      : langueAAfficher(choixDuPoste, installationRetenue, languesDuNavigateur, langueDuCompte);
  }

  /**
   * Note la langue de l'installation (langue_defaut de parametres.csv, D149), celle des textes écrits dans les
   * données (D156) ; valeur vide, inconnue ou mal formée : le français. Rend le code retenu.
   */
  function noterInstallation(code) {
    langueInstallation = estDeclaree(code) ? code : LANGUE_DE_REFERENCE;
    return langueInstallation;
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

  // D156 (Lot 4, T295) : la langue de l'installation si son dictionnaire est chargé dans la page (js/i18n-chargeur.js
  // le charge aussi quand elle n'est pas la langue affichée), sinon le français, sans erreur.
  function langueDesDonnees() {
    return dictionnaires[langueInstallation] ? langueInstallation : LANGUE_DE_REFERENCE;
  }

  /**
   * Texte brut de la clé dans la langue de l'installation, pour ce que l'appli écrit dans les données (journal,
   * titres et motifs pré-remplis, raisons du journal du wiki…), quelle que soit la langue de l'écran (D156).
   */
  function donnees(cle, valeurs) {
    if (langueDesDonnees() === LANGUE_DE_REFERENCE) return reference(cle, valeurs);
    return enLangueDesDonnees(() => t(cle, valeurs));
  }

  /**
   * Exécute `fonction` (synchrone) avec la langue de l'installation pour langue active, puis rend la langue de
   * l'écran, même sur une erreur : I18n.t, I18n.html et I18n.locale y donnent ce qui s'écrit dans les données.
   * Pour un texte composé par d'autres fonctions (rapport figé, raisons d'un contrôle, nombres mis en forme) ; un
   * texte d'une seule clé passe par I18n.donnees. Une fonction asynchrone est refusée (TypeError) : sa suite
   * s'exécuterait après le retour à la langue de l'écran.
   */
  function enLangueDesDonnees(fonction) {
    return executerEn(langueDesDonnees(), fonction, 'enLangueDesDonnees');
  }

  /**
   * Comme enLangueDesDonnees, pour la langue déclarée `code` dont le dictionnaire est chargé (T302 : rapport mensuel
   * figé dans la langue choisie ; I18n.chargerLangue la charge au besoin). Langue non déclarée ou dictionnaire absent :
   * erreur, plutôt qu'un texte écrit dans une autre langue.
   */
  function enLangue(code, fonction) {
    if (!estDeclaree(code)) throw new TypeError('I18n.enLangue : langue non déclarée (' + String(code) + ').');
    if (!dictionnaires[code]) throw new Error('I18n.enLangue : dictionnaire « ' + code + ' » non chargé (I18n.chargerLangue).');
    return executerEn(code, fonction, 'enLangue');
  }

  function executerEn(code, fonction, nom) {
    const ecran = langueActive;
    langueActive = code;
    let resultat;
    try {
      resultat = fonction();
    } finally {
      langueActive = ecran;
    }
    if (resultat && typeof resultat.then === 'function') {
      throw new TypeError('I18n.' + nom + ' : fonction synchrone attendue.');
    }
    return resultat;
  }

  // Dossier de js/i18n.js, relevé pendant l'analyse du script (document.currentScript n'existe plus ensuite) : c'est là
  // que sont js/i18n/<code>.js, comme pour js/i18n-chargeur.js.
  const dossierDesLangues = (typeof document !== 'undefined' && document.currentScript && document.currentScript.src)
    ? document.currentScript.src.replace(/[?#].*$/, '').replace(/[^/]*$/, '') + 'i18n/' : '';
  const chargements = Object.create(null);      // code → Promise du chargement en cours ou fait

  /**
   * Charge à la demande le dictionnaire de la langue déclarée `code` (balise <script src="js/i18n/<code>.js"> ajoutée à
   * la page) → Promise résolue quand il est là ; rien à faire s'il l'est déjà. Rejetée avec une erreur claire si la
   * langue n'est pas déclarée, si le fichier ne se charge pas ou ne fournit pas de dictionnaire.
   */
  function chargerLangue(code) {
    if (!estDeclaree(code)) return Promise.reject(new Error('I18n.chargerLangue : langue non déclarée (' + String(code) + ').'));
    if (dictionnaires[code]) return Promise.resolve();
    if (chargements[code]) return chargements[code];
    const promesse = new Promise((resolve, reject) => {
      if (!dossierDesLangues || typeof document === 'undefined') {
        reject(new Error('I18n.chargerLangue : dossier des langues inconnu, « ' + code + ' » ne peut pas être chargé.'));
        return;
      }
      const balise = document.createElement('script');
      balise.src = dossierDesLangues + code + '.js';
      balise.onload = () => {
        if (dictionnaires[code]) resolve();
        else reject(new Error('I18n.chargerLangue : js/i18n/' + code + '.js ne fournit pas de dictionnaire.'));
      };
      balise.onerror = () => {
        balise.remove();
        reject(new Error('I18n.chargerLangue : js/i18n/' + code + '.js ne s\'est pas chargé.'));
      };
      document.head.appendChild(balise);
    });
    chargements[code] = promesse;
    promesse.catch(() => { delete chargements[code]; });      // un nouvel essai reste possible
    return promesse;
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
    enLangue: enLangue,
    chargerLangue: chargerLangue,
    html: html,
    appliquer: appliquer,
    langueAAfficher: langueAAfficher,
    langueDeLaPage: langueDeLaPage,
    /** Vrai pour un code bien formé et déclaré par js/i18n/langues.js (le français l'est toujours), faux sinon. */
    estDeclaree: estDeclaree,
    installationDeLaPage: installationDeLaPage,
    langueDuNavigateur: langueDuNavigateur,
    noterInstallation: noterInstallation,
    /** Code de la langue de l'installation notée ('fr' tant que rien n'en note une autre). */
    get installation() { return langueInstallation; },
    /** Langue des textes écrits dans les données : celle de l'installation si son dictionnaire est chargé, sinon 'fr'. */
    get langueDesDonnees() { return langueDesDonnees(); },
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
