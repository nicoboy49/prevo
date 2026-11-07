'use strict';
// UI : helpers d'écran communs à tous les modules de Prévo (ARCHITECTURE.md §9).
// Échappement HTML, formats français, badges, notifications, fenêtres, tableaux triables,
// champs de formulaire, sélecteur d'équipement, QR codes, photos, onglets, bandeaux, icônes, sélecteur de langue.
//
// Règles :
// - aucune dépendance à Donnees ni aux modules : tout ce qu'il faut est passé en paramètre ;
// - compatible file:// et contexte non sécurisé (http://192.168.x.x) : pas de crypto, pas de
//   presse-papiers ; la caméra n'est proposée que si window.isSecureContext && navigator.mediaDevices ;
// - jamais d'alert / confirm / prompt : UI.toast, UI.confirmer, UI.demanderMotif.
// Bibliothèques utilisées si elles sont chargées : qrcode (js/lib/qrcode.js), jsQR (js/lib/jsQR.js).

const UI = (function () {

  // ===========================================================================================
  // Sélecteurs
  // ===========================================================================================

  /** Premier élément qui correspond au sélecteur (dans `racine`, ou tout le document). */
  function $(selecteur, racine) {
    return (racine || document).querySelector(selecteur);
  }

  /** Tous les éléments qui correspondent, sous forme de vrai tableau. */
  function $$(selecteur, racine) {
    return Array.from((racine || document).querySelectorAll(selecteur));
  }

  let compteurIdentifiants = 0;
  /** Identifiant d'élément HTML unique dans la page (pour relier un libellé à son champ). */
  function identifiantUnique(prefixe) {
    compteurIdentifiants += 1;
    const base = String(prefixe || 'ui').replace(/[^A-Za-z0-9_-]/g, '-');
    return base + '-' + compteurIdentifiants;
  }

  // ===========================================================================================
  // Échappement et fragments HTML sûrs
  // ===========================================================================================

  const REMPLACEMENTS_HTML = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

  /** Rend un texte inoffensif dans du HTML (balises et guillemets échappés). null/undefined → ''. */
  function echapper(valeur) {
    if (valeur === null || valeur === undefined) return '';
    return String(valeur).replace(/[&<>"']/g, (caractere) => REMPLACEMENTS_HTML[caractere]);
  }

  // Un fragment HTML déjà sûr (produit par UI.html ou déclaré par UI.brut).
  // Il se convertit en chaîne tout seul : element.innerHTML = UI.html`…` fonctionne.
  class HtmlSur {
    constructor(texte) { this.texte = texte; }
    toString() { return this.texte; }
  }

  /** Déclare un fragment HTML comme sûr (à n'utiliser que sur du HTML écrit dans le code). */
  function brut(texte) {
    if (texte instanceof HtmlSur) return texte;
    return new HtmlSur(texte === null || texte === undefined ? '' : String(texte));
  }

  /** Vrai si la valeur est un fragment sûr (UI.html ou UI.brut). */
  function estSur(valeur) {
    return valeur instanceof HtmlSur;
  }

  // Conversion d'une valeur insérée dans UI.html : fragment sûr gardé tel quel, tableau joint,
  // null / undefined / false ignorés (pratique pour `${condition && UI.html`…`}`), le reste échappé.
  function valeurVersHtml(valeur) {
    if (valeur instanceof HtmlSur) return valeur.texte;
    if (Array.isArray(valeur)) return valeur.map(valeurVersHtml).join('');
    if (valeur === null || valeur === undefined || valeur === false) return '';
    return echapper(valeur);
  }

  /**
   * Gabarit HTML qui échappe chaque valeur insérée :
   *   conteneur.innerHTML = UI.html`<b>${equipement.repere}</b> ${UI.badgePriorite(ot.priorite)}`;
   * Un tableau est joint sans séparateur ; UI.brut(s) insère un fragment déjà sûr.
   * Renvoie un fragment sûr (String(fragment) donne le texte HTML).
   */
  function html(morceaux, ...valeurs) {
    // Appelé comme une fonction ordinaire (UI.html(chaine)), il laisserait passer du HTML non échappé.
    if (!morceaux || !Array.isArray(morceaux.raw)) {
      throw new Error(I18n.t('socle.html.ui_html_utilise_comme'));
    }
    let resultat = morceaux[0];
    for (let i = 0; i < valeurs.length; i += 1) {
      resultat += valeurVersHtml(valeurs[i]) + morceaux[i + 1];
    }
    return new HtmlSur(resultat);
  }

  /**
   * Remplit un élément : un nœud DOM est ajouté, un fragment sûr est inséré comme HTML,
   * tout autre valeur est insérée comme TEXTE (donc jamais interprétée).
   */
  function remplir(element, contenu) {
    element.textContent = '';
    ajouterContenu(element, contenu);
    return element;
  }

  function ajouterContenu(element, contenu) {
    if (contenu === null || contenu === undefined || contenu === false) return;
    if (Array.isArray(contenu)) { contenu.forEach((morceau) => ajouterContenu(element, morceau)); return; }
    if (contenu instanceof Node) { element.appendChild(contenu); return; }
    if (contenu instanceof HtmlSur) { element.insertAdjacentHTML('beforeend', contenu.texte); return; }
    element.appendChild(document.createTextNode(String(contenu)));
  }

  /** Crée un élément DOM à partir d'un fragment sûr : UI.element(UI.html`<li>${nom}</li>`). */
  function element(fragment) {
    const modele = document.createElement('template');
    modele.innerHTML = valeurVersHtml(fragment).trim();
    return modele.content.firstElementChild;
  }

  /**
   * Texte comparable pour une recherche, un seul pliage quelle que soit la langue (D154) : ı et İ ramenés à i (I l'est
   * par les minuscules), ß à ss, accents retirés, minuscules, espaces simplifiés (« İSTANBUL » → « istanbul »,
   * « ırmak » et « IRMAK » → « irmak »). Toute recherche de l'application passe par ici (le wiki aussi).
   */
  function normaliserRecherche(texte) {
    return String(texte === null || texte === undefined ? '' : texte)
      .replace(/[ıİ]/g, 'i').replace(/[ßẞ]/g, 'ss')
      .normalize('NFD').replace(/\p{M}+/gu, '')
      .toLowerCase().replace(/\s+/g, ' ').trim();
  }

  // Tri des listes affichées (D154) : ordre de la langue active, Intl.Collator de I18n.locale (en turc : « Çelik » entre
  // « Cem » et « Dede », « Işık » avant « İnce »), un par locale et par réglages, gardé. Codes, identifiants, dates ISO,
  // noms de fichiers et en-têtes CSV n'y passent pas : leur ordre reste le même dans toutes les langues.
  const collateurs = new Map();

  function collateur(numeric, sensitivity) {
    const locale = I18n.locale;
    const cle = locale + ' ' + numeric + ' ' + sensitivity;
    if (!collateurs.has(cle)) {
      const reglages = { numeric, sensitivity };
      let nouveau;
      try {
        nouveau = new Intl.Collator(locale, reglages);
      } catch (erreur) {                         // locale refusée par Intl : ordre du français
        nouveau = new Intl.Collator('fr-FR', reglages);
      }
      collateurs.set(cle, nouveau);
    }
    return collateurs.get(cle);
  }

  function enChaine(valeur) {
    return String(valeur === null || valeur === undefined ? '' : valeur);
  }

  /** Compare deux libellés dans l'ordre de la langue active ; options d'Intl.Collator : { numeric, sensitivity }. */
  function comparerTextes(a, b, options) {
    const reglages = options || {};
    return collateur(Boolean(reglages.numeric), reglages.sensitivity || 'variant').compare(enChaine(a), enChaine(b));
  }

  // ===========================================================================================
  // Formats français (les valeurs en mémoire sont des chaînes au format du fichier)
  // ===========================================================================================

  const TIRET_VALEUR_ABSENTE = '–';
  const formateursNombre = {};

  // Intl sépare les milliers par l'espace fine insécable U+202F, presque invisible avec la police
  // Sora (« 15855 h ») : l'affichage la remplace par l'espace insécable U+00A0, bien visible
  // (demande de Nicolas). Les CSV ne sont pas concernés : ils n'ont jamais de séparateur (§3).
  const ESPACE_FINE = /\u202F/g;
  const ESPACE_INSECABLE = '\u00A0';

  // Devise de l'installation (T304, D152) : clé `devise` de parametres.csv (code ISO 4217), lue à chaque formatage ;
  // EUR si elle manque, est illisible ou inconnue d'Intl, ou si la page n'a pas Donnees. Elle ne convertit aucun montant.
  const DEVISE_PAR_DEFAUT = 'EUR';
  const devisesConnues = {};
  const symbolesDevise = {};

  /** Vrai si `code` est un code ISO 4217 (3 lettres majuscules) connu d'Intl. */
  function deviseConnue(code) {
    if (typeof code !== 'string' || !/^[A-Z]{3}$/.test(code)) return false;
    if (!(code in devisesConnues)) {
      let connue = false;
      try {
        if (typeof Intl.supportedValuesOf === 'function') connue = Intl.supportedValuesOf('currency').includes(code);
        else connue = new Intl.DisplayNames(['en'], { type: 'currency' }).of(code) !== code;
      } catch (erreur) { connue = false; }
      devisesConnues[code] = connue;
    }
    return devisesConnues[code];
  }

  /** Code de la devise réglée (« EUR » par défaut). */
  function devise() {
    let code = DEVISE_PAR_DEFAUT;
    try {
      if (typeof Donnees !== 'undefined' && Donnees && typeof Donnees.parametre === 'function') {
        code = String(Donnees.parametre('devise', DEVISE_PAR_DEFAUT)).trim().toUpperCase();
      }
    } catch (erreur) { code = DEVISE_PAR_DEFAUT; }
    return deviseConnue(code) ? code : DEVISE_PAR_DEFAUT;
  }

  /** Nom de la devise dans la langue active (« euro », « Swiss Franc ») ; le code lui-même si Intl l'ignore. */
  function nomDevise(code) {
    try { return new Intl.DisplayNames([I18n.locale], { type: 'currency' }).of(code) || code; } catch (erreur) { return code; }
  }

  /** Symbole court de la devise réglée, pour les libellés (« € », « CHF », « £ »). */
  function symboleDevise() {
    const code = devise();
    const cle = I18n.locale + '/' + code;
    if (!symbolesDevise[cle]) {
      let symbole = code;
      try {
        const parties = new Intl.NumberFormat(I18n.locale, { style: 'currency', currency: code, currencyDisplay: 'narrowSymbol' }).formatToParts(0);
        const partie = parties.find((p) => p.type === 'currency');
        if (partie) symbole = partie.value;
      } catch (erreur) { symbole = code; }
      symbolesDevise[cle] = symbole;
    }
    return symbolesDevise[cle];
  }

  function formateurNombre(decimalesMin, decimalesMax, style) {
    const locale = I18n.locale;
    const monnaie = style === 'euro' ? devise() : '';
    const cle = locale + '/' + decimalesMin + '/' + decimalesMax + '/' + (style || '') + '/' + monnaie;
    if (!formateursNombre[cle]) {
      const options = { minimumFractionDigits: decimalesMin, maximumFractionDigits: decimalesMax };
      if (style === 'euro') { options.style = 'currency'; options.currency = monnaie; }
      const intl = new Intl.NumberFormat(locale, options);
      formateursNombre[cle] = { format: (nombre) => intl.format(nombre).replace(ESPACE_FINE, ESPACE_INSECABLE) };
    }
    return formateursNombre[cle];
  }

  /** Nombre JavaScript à partir d'une valeur du fichier ('12.5', '12,5', ' 1 200 ', 12.5) ou null. */
  function enNombre(valeur) {
    if (typeof valeur === 'number') return Number.isFinite(valeur) ? valeur : null;
    if (valeur === null || valeur === undefined) return null;
    const texte = String(valeur).replace(/[\s\u00a0\u202f]/g, '').replace(',', '.');
    if (!/^[-+]?(\d+\.?\d*|\.\d+)(e[-+]?\d+)?$/i.test(texte)) return null;
    return Number(texte);
  }

  /** '2026-03-15' (ou '2026-03-15 08:05') → '15/03/2026'. Valeur vide → ''. Autre format : rendu tel quel. */
  function dateFr(valeur) {
    if (valeur === null || valeur === undefined || valeur === '') return '';
    if (valeur instanceof Date) {
      return deuxChiffres(valeur.getDate()) + '/' + deuxChiffres(valeur.getMonth() + 1) + '/' + valeur.getFullYear();
    }
    const morceaux = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(valeur).trim());
    if (!morceaux) return String(valeur);
    return morceaux[3] + '/' + morceaux[2] + '/' + morceaux[1];
  }

  /** '2026-03-15 08:05' → '15/03/2026 08:05' ; une date seule → '15/03/2026'. Valeur vide → ''. */
  function dateHeureFr(valeur) {
    if (valeur === null || valeur === undefined || valeur === '') return '';
    if (valeur instanceof Date) {
      return dateFr(valeur) + ' ' + deuxChiffres(valeur.getHours()) + ':' + deuxChiffres(valeur.getMinutes());
    }
    const morceaux = /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?/.exec(String(valeur).trim());
    if (!morceaux) return String(valeur);
    const date = morceaux[3] + '/' + morceaux[2] + '/' + morceaux[1];
    return morceaux[4] ? date + ' ' + morceaux[4] + ':' + morceaux[5] : date;
  }

  function deuxChiffres(nombre) {
    return String(nombre).padStart(2, '0');
  }

  /**
   * Nombre à la française : '1234.5' → '1 234,5'. `decimales` fixe le nombre de décimales ;
   * sans lui, jusqu'à 2 décimales. Valeur absente ou illisible → '–'.
   */
  function nombreFr(valeur, decimales) {
    const nombre = enNombre(valeur);
    if (nombre === null) return TIRET_VALEUR_ABSENTE;
    if (decimales === undefined || decimales === null) return formateurNombre(0, 2).format(nombre);
    return formateurNombre(decimales, decimales).format(nombre);
  }

  /** Montant dans la devise réglée (EUR par défaut) : '1234.5' → '1 234,50 €' (2 décimales par défaut). Absent → '–'. */
  function euro(valeur, decimales) {
    const nombre = enNombre(valeur);
    if (nombre === null) return TIRET_VALEUR_ABSENTE;
    const nb = decimales === undefined || decimales === null ? 2 : decimales;
    return formateurNombre(nb, nb, 'euro').format(nombre);
  }

  /** Durée en heures : '1.5' → '1,5 h'. Absent → '–'. */
  function heures(valeur) {
    const nombre = enNombre(valeur);
    if (nombre === null) return TIRET_VALEUR_ABSENTE;
    return formateurNombre(0, 2).format(nombre) + '\u00a0h';
  }

  // ===========================================================================================
  // Badges
  // ===========================================================================================

  /** Badge de priorité : couleur de la charte ET libellé (P1 rouge, P2 ambre, P3 cyan, P4 gris). */
  function badgePriorite(priorite) {
    const texte = String(priorite === null || priorite === undefined ? '' : priorite).trim();
    const code = texte.toUpperCase();
    if (/^P[1-4]$/.test(code)) {
      return html`<span class="badge prio-${code.toLowerCase()}" title="${I18n.t('socle.badge_priorite.priorite_code', { code })}">${code}</span>`;
    }
    return html`<span class="badge neutre" title="${I18n.t('socle.badge_priorite.priorite_inconnue')}">${texte || '—'}</span>`;
  }

  // Ton (couleur) de chaque statut connu (DI, OT, équipements, achats, contrôles) ; inconnu → neutre.
  const TONS_STATUT = {
    // demandes d'intervention
    'nouvelle': 'info', 'acceptée': 'ok', 'regroupée': 'violet', 'différée': 'attention', 'refusée': 'ko',
    // ordres de travail
    'créé': 'neutre', 'préparé': 'info', 'planifié': 'violet', 'en cours': 'cyan', 'en attente': 'attention',
    'clôturé techniquement': 'ok', 'clôturé administrativement': 'ok', 'annulé': 'neutre barre',
    // équipements
    'en service': 'ok', 'arrêt': 'ko', 'rebut': 'neutre',
    // achats
    'demandée': 'info', 'commandée': 'violet', 'reçue': 'ok',
    // contrôles réglementaires, habilitations
    'à jour': 'ok', 'à planifier': 'attention', 'en retard': 'ko', 'observations à lever': 'attention',
    'valide': 'ok', 'à renouveler': 'attention', 'échue': 'ko',
  };

  /**
   * Badge de statut (texte toujours affiché ; la couleur aide seulement). `ton` force la couleur. `libelle` : texte
   * affiché à la place du statut (état calculé traduit), la couleur restant choisie sur le statut.
   */
  function badgeStatut(statut, ton, libelle) {
    const texte = String(statut === null || statut === undefined ? '' : statut).trim();
    const tonChoisi = ton || TONS_STATUT[texte.toLowerCase()] || 'neutre';
    return html`<span class="badge statut ${tonChoisi}">${(libelle === undefined ? texte : libelle) || '—'}</span>`;
  }

  /**
   * Badge d'une valeur stockée d'une liste du schéma (D155) : la couleur se choisit sur la valeur brute (TONS_STATUT,
   * comme badgeStatut), le texte est son libellé dans la langue de l'écran (Schema.libelleValeur). `ton` force la
   * couleur. UI.badgeValeur('ordres_travail', 'statut', ot.statut).
   */
  function badgeValeur(nomTable, nomChamp, valeur, ton) {
    const texte = String(valeur === null || valeur === undefined ? '' : valeur).trim();
    const tonChoisi = ton || TONS_STATUT[texte.toLowerCase()] || 'neutre';
    return html`<span class="badge statut ${tonChoisi}">${Schema.libelleValeur(nomTable, nomChamp, texte) || '—'}</span>`;
  }

  // ===========================================================================================
  // Icônes (SVG au trait, 24 × 24, comme la référence Cockpit)
  // ===========================================================================================

  const ICONES = {
    accueil: '<path d="M4 13h6V4H4zm0 7h6v-5H4zm10 0h6v-9h-6zm0-16v5h6V4z"/>',
    demandes: '<path d="M4 5h16v11H10l-6 4z"/><path d="M12 8v3.5M12 13.6v.01"/>',
    ordres: '<path d="M9 3.5h6v3H9z"/><path d="M9 5H6v16h12V5h-3"/><path d="m9 12 2 2 4-4M9 17h6"/>',
    parc: '<path d="M3 20V11l5 3v-3l5 3v-3l5 3V4h3v16z"/><path d="M7 17h2M12 17h2"/>',
    parametres: '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
    apropos: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.6v.01"/>',
    plus: '<circle cx="5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="19" cy="12" r="1.3"/>',
    ajouter: '<path d="M12 5v14M5 12h14"/>',
    recherche: '<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/>',
    qr: '<path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4z"/><path d="M14 14h2.5v2.5H14zM19 14h1M14 19.5h1M17.5 17.5H20V20h-2.5z"/>',
    photo: '<path d="M4 8h3.2l1.8-3h6l1.8 3H20v11H4z"/><circle cx="12" cy="13" r="3.5"/>',
    retour: '<path d="M19 12H5M11 6l-6 6 6 6"/>',
    imprimer: '<path d="M7 9V3.5h10V9"/><path d="M7 17H4V9h16v8h-3"/><path d="M7 14h10v6.5H7z"/>',
    sauvegarde: '<path d="M5 4h11l3 3v13H5z"/><path d="M8 4v5h7V4M8 20v-6h8v6"/>',
    alerte: '<path d="M12 3.5 2.5 20h19z"/><path d="M12 10v4.5M12 17.4v.01"/>',
    telephone: '<rect x="7" y="2.5" width="10" height="19" rx="2.2"/><path d="M11 18.5h2"/>',
    controle: '<path d="M12 3 19 6v5c0 4.6-3 8.4-7 10-4-1.6-7-5.4-7-10V6z"/><path d="m9 12 2 2 4-4"/>',
    menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
    fermer: '<path d="M6 6l12 12M18 6 6 18"/>',
    export: '<path d="M12 3.5v11M7.5 10l4.5 4.5 4.5-4.5"/><path d="M4.5 15v5h15v-5"/>',
    utilisateur: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1-4.4 4.4-6.5 8-6.5s7 2.1 8 6.5"/>',
    micro: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M8.5 21h7"/>',
    engrenage: '<circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1.2l2-1.5-2-3.4-2.3.9a7 7 0 0 0-2-1.2L14.2 3h-4.4l-.4 2.6a7 7 0 0 0-2 1.2l-2.3-.9-2 3.4 2 1.5a7 7 0 0 0 0 2.4l-2 1.5 2 3.4 2.3-.9a7 7 0 0 0 2 1.2l.4 2.6h4.4l.4-2.6a7 7 0 0 0 2-1.2l2.3.9 2-3.4-2-1.5c.1-.4.1-.8.1-1.2z"/>',
    cle: '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.8-3.8a6 6 0 0 1-7.9 7.9l-6.9 6.9a2.1 2.1 0 0 1-3-3l6.9-6.9a6 6 0 0 1 7.9-7.9z"/>',
    horloge: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.2 2"/>',
    valider: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    actualiser: '<path d="M20 11a8 8 0 0 0-14.6-4.5L4 8M4 4v4h4"/><path d="M4 13a8 8 0 0 0 14.6 4.5L20 16m0 4v-4h-4"/>',
    document: '<path d="M6 2.5h9l5 5V21.5H6z"/><path d="M14 3v5h5M9 12.5h8M9 16.5h8"/>',
    calendrier: '<path d="M4 6h16v14H4zM4 10h16M8 3v5M16 3v5"/>',
    // Lot 2 (ARCHITECTURE.md §14.2) : calendrier coché (Préventif) et carton fermé (Magasin)
    preventif: '<path d="M4 6h16v14H4zM4 10h16M8 3v5M16 3v5"/><path d="m8.5 15 2.5 2.5 4.5-4.5"/>',
    magasin: '<path d="M3.5 8 12 4l8.5 4v9L12 21l-8.5-4z"/><path d="M3.5 8 12 12l8.5-4M12 12v9"/><path d="m7.75 6 8.5 4v3"/>',
    // Lot 3 (ARCHITECTURE.md §15.1) : planning (calendrier à créneaux), contrôles réglementaires
    // (rosette cochée), indicateurs (histogramme), équipe (deux personnes)
    planning: '<path d="M4 6h16v14H4zM4 10h16M8 3v5M16 3v5"/><path d="M7.5 13.5h4M13 13.5h3.5M7.5 16.5h3"/>',
    controles: '<circle cx="12" cy="9" r="5.5"/><path d="m9.6 9 1.7 1.7 3.1-3.1"/><path d="M8.4 13.4 7 21l5-2.6 5 2.6-1.4-7.6"/>',
    indicateurs: '<path d="M4 20h16"/><path d="M6 20v-6h3v6M10.5 20V9h3v11M15 20v-9h3v9"/>',
    equipe: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.8 3.4-5.7 6.5-5.7s5.7 1.9 6.5 5.7"/><path d="M15 4.7a3.5 3.5 0 0 1 0 6.6M17.5 14.6c2 .6 3.4 2.4 4 5.4"/>',
    replier: '<path d="m14 6-6 6 6 6M19 6v12"/>',
    chevron: '<path d="m9 6 6 6-6 6"/>',
    // Lot 6 (ARCHITECTURE.md §20.1) : wiki de maintenance (livre ouvert)
    wiki: '<path d="M12 6.5C10 5 7 4.5 3.5 5v13.5c3.5-.5 6.5 0 8.5 1.5 2-1.5 5-2 8.5-1.5V5c-3.5-.5-6.5 0-8.5 1.5z"/><path d="M12 6.5V20"/>',
    // Lot 4 du chantier multilingue (T297) : langue de l'écran (globe neutre, sans drapeau ni mot), écran de connexion
    langue: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.4 2.5 3.6 5.5 3.6 9s-1.2 6.5-3.6 9c-2.4-2.5-3.6-5.5-3.6-9s1.2-6.5 3.6-9z"/>',
  };

  /** Icône SVG au trait par son nom (voir ICONES) ; `classe` ajoute des classes CSS. Inconnue → ''. */
  function icone(nom, classe) {
    const dessin = ICONES[nom];
    if (!dessin) return brut('');
    const classes = 'icone' + (classe ? ' ' + classe : '');
    return html`<svg class="${classes}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${brut(dessin)}</svg>`;
  }

  /** Noms des icônes disponibles (pour le guide de style). */
  function nomsIcones() {
    return Object.keys(ICONES);
  }

  // Engrenage du favicon (même dessin, en blanc sur le carré dégradé).
  const CHEMIN_ENGRENAGE_LOGO = 'M24.22 13.46 L27.37 13.70 L27.37 18.30 L24.22 18.54 L23.61 20.01 L25.67 22.41 '
    + 'L22.41 25.67 L20.01 23.61 L18.54 24.22 L18.30 27.37 L13.70 27.37 L13.46 24.22 L11.99 23.61 L9.59 25.67 '
    + 'L6.33 22.41 L8.39 20.01 L7.78 18.54 L4.63 18.30 L4.63 13.70 L7.78 13.46 L8.39 11.99 L6.33 9.59 L9.59 6.33 '
    + 'L11.99 8.39 L13.46 7.78 L13.70 4.63 L18.30 4.63 L18.54 7.78 L20.01 8.39 L22.41 6.33 L25.67 9.59 L23.61 11.99 Z '
    + 'M19.60 16.00 A3.6 3.6 0 1 0 12.40 16.00 A3.6 3.6 0 1 0 19.60 16.00 Z';

  /** Logo de l'application : carré dégradé avec l'engrenage. `classe` : 'grand' pour l'écran de démarrage. */
  function logo(classe) {
    const classes = 'logo' + (classe ? ' ' + classe : '');
    return html`<span class="${classes}" aria-hidden="true"><svg viewBox="0 0 32 32" focusable="false"><path fill-rule="evenodd" d="${CHEMIN_ENGRENAGE_LOGO}"/></svg></span>`;
  }

  // ===========================================================================================
  // Notifications : toast et bandeaux
  // ===========================================================================================

  let minuteurToast = null;

  // Durée d'affichage d'un toast (T89 : courte ; une erreur reste plus longtemps, le temps de la lire).
  const DUREES_TOAST = { erreur: 7000, attention: 4500 };
  const DUREE_TOAST = 3000;

  /**
   * Petit message temporaire en bas de l'écran (élément role="status", lu par les lecteurs d'écran) :
   * bulle en bas à droite, au-dessus de la barre du bas sur téléphone (css/style.css §10).
   * type : 'succes' | 'erreur' | 'attention' | 'info' (défaut). Un clic le ferme.
   */
  function toast(message, type) {
    // Réutilise la zone fournie vide par la page (les lecteurs d'écran annoncent alors le premier
    // message) ; sinon la crée vide, l'insère, puis la remplit au tour suivant.
    let zone = document.getElementById('toast') || document.querySelector('.toast[role="status"]');
    let tourSuivant = false;
    if (!zone) {
      zone = document.createElement('div');
      zone.id = 'toast';
      zone.setAttribute('role', 'status');
      zone.setAttribute('aria-live', 'polite');
      zone.className = 'toast';
      document.body.appendChild(zone);
      tourSuivant = true;
    }
    if (!zone.dataset.fermeture) {
      zone.dataset.fermeture = '1';
      zone.addEventListener('click', () => zone.classList.remove('visible'));
    }
    const afficher = () => {
      zone.className = 'toast' + (type && type !== 'info' ? ' ' + type : '');
      remplir(zone, message);
      void zone.offsetWidth; // relance la transition si un toast était déjà affiché
      zone.classList.add('visible');
    };
    if (tourSuivant) setTimeout(afficher, 0); else afficher();
    clearTimeout(minuteurToast);
    minuteurToast = setTimeout(() => zone.classList.remove('visible'), DUREES_TOAST[type] || DUREE_TOAST);
    return zone;
  }

  const ICONES_BANDEAU = { info: 'apropos', attention: 'alerte', important: 'alerte', succes: 'valider', securite: 'alerte' };

  /**
   * Crée un bandeau (non inséré : à placer par l'appelant).
   * type : 'info' | 'attention' | 'important' | 'succes' | 'securite' (bandeau rouge plein).
   * contenu : texte (échappé), fragment UI.html ou nœud DOM.
   */
  function bandeau(type, contenu) {
    const typeConnu = ICONES_BANDEAU[type] ? type : 'info';
    const bloc = document.createElement('div');
    bloc.className = typeConnu === 'securite' ? 'bandeau-securite'
      : 'alerte' + (typeConnu === 'info' ? '' : ' ' + typeConnu);
    bloc.setAttribute('role', typeConnu === 'important' || typeConnu === 'securite' ? 'alert' : 'status');
    bloc.innerHTML = String(icone(ICONES_BANDEAU[typeConnu])) + '<div class="alerte-texte"></div>';
    remplir(bloc.querySelector('.alerte-texte'), contenu);
    return bloc;
  }

  /** État vide qui explique quoi faire : UI.vide('Aucune demande', 'Les demandes créées apparaîtront ici.', 'demandes'). */
  function vide(titre, texte, nomIcone) {
    return html`<div class="vide">${icone(nomIcone || 'apropos')}<b>${titre}</b>${texte ? html`<p>${texte}</p>` : ''}</div>`;
  }

  /** Indicateur de chargement (texte toujours présent). */
  function chargement(texte) {
    return html`<div class="chargement" role="status">${texte || I18n.t('socle.chargement.chargement')}</div>`;
  }

  // ===========================================================================================
  // Fenêtres (<dialog>) : fenetre, confirmer, demanderMotif
  // ===========================================================================================

  /**
   * Ouvre une fenêtre modale et attend le choix de l'utilisateur.
   *   const choix = await UI.fenetre({
   *     titre: 'Titre', contenu: texte | UI.html`…` | nœud DOM,
   *     boutons: [{ libelle: 'Annuler', valeur: null, classe: 'btn-fantome' },
   *               { libelle: 'Enregistrer', valeur: 'ok', classe: 'btn-primaire', defaut: true }],
   *     classe: 'large' | 'feuille' (facultatif),
   *     avantFermeture(valeur, dialogue) { return false pour garder la fenêtre ouverte },
   *     surOuverture(dialogue, fermer) { … }   // fermer(valeur) ferme la fenêtre par programme
   *   });
   * Renvoie la `valeur` du bouton cliqué ; Échap ou la croix renvoient null.
   * La touche Entrée dans un champ d'une ligne déclenche le bouton `defaut`.
   */
  function fenetre(options) {
    const reglages = options || {};
    return new Promise((resoudre) => {
      const elementAvant = document.activeElement;
      const dialogue = document.createElement('dialog');
      dialogue.className = 'dialogue' + (reglages.classe ? ' ' + reglages.classe : '');
      const idTitre = identifiantUnique('titre-fenetre');
      dialogue.setAttribute('aria-labelledby', idTitre);

      const formulaire = document.createElement('form');
      formulaire.method = 'dialog';
      formulaire.noValidate = true;
      formulaire.innerHTML = String(html`
        <div class="fenetre-tete">
          <h2 id="${idTitre}"></h2>
          <button type="button" class="btn btn-fantome btn-icone fenetre-fermer" aria-label="${I18n.t('commun.bouton.fermer')}">${icone('fermer')}</button>
        </div>
        <div class="fenetre-corps"></div>
        <div class="actions fenetre-actions"></div>`);
      formulaire.querySelector('h2').textContent = reglages.titre || '';
      remplir(formulaire.querySelector('.fenetre-corps'), reglages.contenu);

      const boutons = reglages.boutons && reglages.boutons.length
        ? reglages.boutons
        : [{ libelle: I18n.t('commun.bouton.fermer'), valeur: null, classe: 'btn-primaire', defaut: true }];
      const zoneBoutons = formulaire.querySelector('.fenetre-actions');
      let boutonParDefaut = null;
      boutons.forEach((definition) => {
        const bouton = document.createElement('button');
        bouton.type = 'button';
        bouton.className = 'btn ' + (definition.classe || 'btn-secondaire');
        if (definition.icone) bouton.innerHTML = String(icone(definition.icone));
        bouton.appendChild(document.createTextNode(definition.libelle));
        bouton.addEventListener('click', () => terminer(definition.valeur === undefined ? null : definition.valeur));
        zoneBoutons.appendChild(bouton);
        if (definition.defaut) boutonParDefaut = bouton;
      });
      dialogue.appendChild(formulaire);

      let termine = false;
      function terminer(valeur) {
        if (termine) return;
        if (valeur !== null && typeof reglages.avantFermeture === 'function'
            && reglages.avantFermeture(valeur, dialogue) === false) {
          return; // la fenêtre reste ouverte (ex. motif vide)
        }
        termine = true;
        // Lot 4 (§17.6) : une dictée en cours dans la fenêtre s'arrête avec elle.
        if (typeof Dictee !== 'undefined') Dictee.arreterDans(dialogue);
        if (dialogue.open) dialogue.close();
        dialogue.remove();
        if (elementAvant && typeof elementAvant.focus === 'function' && document.contains(elementAvant)) {
          elementAvant.focus();
        }
        resoudre(valeur);
      }

      formulaire.querySelector('.fenetre-fermer').addEventListener('click', () => terminer(null));
      formulaire.addEventListener('submit', (evenement) => {
        evenement.preventDefault();
        if (boutonParDefaut) boutonParDefaut.click();
      });
      dialogue.addEventListener('cancel', (evenement) => { // touche Échap
        evenement.preventDefault();
        terminer(null);
      });

      document.body.appendChild(dialogue);
      dialogue.showModal();
      // Lot 4 (§17.6) : bouton micro sur les champs dictés de la fenêtre (Dictee est chargé après ce fichier).
      if (typeof Dictee !== 'undefined') Dictee.equiper(dialogue);
      const premierChamp = formulaire.querySelector('.fenetre-corps input:not([type=hidden]), .fenetre-corps textarea, .fenetre-corps select');
      (premierChamp || boutonParDefaut || zoneBoutons.lastElementChild || dialogue).focus();
      if (typeof reglages.surOuverture === 'function') reglages.surOuverture(dialogue, terminer);
    });
  }

  /**
   * Fenêtre de saisie commune (lot 4, mise en commun des écrans Contrôles et Équipe) :
   *   UI.fenetreAction({ titre, introduction, champs, libelleValider, verifier, action, classe })
   * `champs` : blocs .champ (UI.champ) ; `verifier(valeurs, contenu)` → erreurs [{ nom, message }]
   * affichées sous les champs (la fenêtre reste ouverte) ; puis `action(valeurs, contenu)` (async). Un
   * refus (Donnees.ErreurValidation) s'affiche dans la fenêtre ; une autre erreur est signalée. Les
   * champs « fichier » ne sont pas lus dans `valeurs` (l'écran les lit dans `contenu`). Renvoie true si
   * l'action a réussi (fenêtre fermée), false si l'utilisateur a annulé.
   */
  async function fenetreAction({ titre, introduction, champs, libelleValider, verifier, action, classe }) {
    const contenu = element(html`<div class="form-colonne ${classe || ''}">${introduction || ''}</div>`);
    champs.forEach((bloc) => contenu.appendChild(bloc));
    const zoneErreur = element(html`<p class="erreur-champ" role="alert" hidden></p>`);
    contenu.appendChild(zoneErreur);
    let fermer = null;
    let fait = false;
    let enCours = false;

    function lireChamps() {
      const valeurs = {};
      $$('[name]', contenu).forEach((controle) => {
        if (controle.type === 'file') return;
        valeurs[controle.name] = controle.type === 'checkbox' ? (controle.checked ? '1' : '0') : String(controle.value || '').trim();
      });
      return valeurs;
    }

    function afficherErreurs(erreurs) {
      $$('.champ', contenu).forEach((champ) => erreurChamp(contenu, champ.dataset.champ, ''));
      erreurs.forEach((erreur) => erreurChamp(contenu, erreur.nom, erreur.message));
      const premier = $('[aria-invalid="true"]', contenu);
      if (premier) premier.focus();
    }

    async function valider() {
      if (enCours) return;
      zoneErreur.hidden = true;
      const erreurs = verifierFormulaire(contenu);
      const valeurs = lireChamps();
      if (!erreurs.length) erreurs.push(...verifier(valeurs, contenu));
      afficherErreurs(erreurs);
      if (erreurs.length) return;
      enCours = true;
      try {
        await action(valeurs, contenu);
        fait = true;
        fermer('ok');
      } catch (erreur) {
        if (erreur instanceof Donnees.ErreurValidation) {
          zoneErreur.textContent = erreur.message;
          zoneErreur.hidden = false;
        } else {
          App.signalerErreur(erreur, titre);
        }
      } finally {
        enCours = false;
      }
    }

    const choix = await fenetre({
      titre, contenu,
      boutons: [
        { libelle: I18n.t('commun.bouton.annuler'), valeur: null, classe: 'btn-fantome' },
        { libelle: libelleValider, valeur: 'ok', classe: 'btn-primaire', defaut: true },
      ],
      surOuverture(dialogue, fermerFenetre) { fermer = fermerFenetre; },
      avantFermeture(valeur) {
        if (valeur !== 'ok' || fait) return true;
        valider();                                     // la fenêtre se ferme toute seule si tout va bien
        return false;
      },
    });
    return choix === 'ok';
  }

  /**
   * Demande une confirmation. Renvoie true (bouton « Confirmer ») ou false.
   * options : { titre, oui: 'Supprimer', non: 'Annuler', danger: true }.
   */
  async function confirmer(message, options) {
    const reglages = options || {};
    const choix = await fenetre({
      titre: reglages.titre || I18n.t('socle.confirmer.confirmation'),
      contenu: html`<p>${message}</p>`,
      boutons: [
        { libelle: reglages.non || I18n.t('commun.bouton.annuler'), valeur: false, classe: 'btn-fantome' },
        { libelle: reglages.oui || I18n.t('socle.confirmer.confirmer'), valeur: true, classe: reglages.danger ? 'btn-danger' : 'btn-primaire', defaut: true },
      ],
    });
    return choix === true;
  }

  /**
   * Demande un motif obligatoire (refus de DI, mise en attente, annulation…).
   * Renvoie le texte saisi (espaces de bord retirés, jamais vide) ou null si l'utilisateur annule.
   * Un motif vide est refusé : message d'erreur et la fenêtre reste ouverte.
   */
  async function demanderMotif(titre, libelle, options) {
    const reglages = options || {};
    const idChamp = identifiantUnique('motif');
    const contenu = element(html`
      <div class="champ">
        <label class="libelle" for="${idChamp}">${libelle || I18n.t('socle.demander_motif.motif')} <span class="requis" aria-hidden="true">*</span></label>
        <textarea id="${idChamp}" name="motif" rows="4" required aria-required="true" data-dictee
          aria-describedby="${idChamp}-erreur" placeholder="${reglages.exemple || ''}"></textarea>
        <p class="erreur-champ" id="${idChamp}-erreur" role="alert" hidden></p>
      </div>`);
    const zoneTexte = contenu.querySelector('textarea');
    zoneTexte.value = reglages.valeur || '';
    const zoneErreur = contenu.querySelector('.erreur-champ');
    zoneTexte.addEventListener('input', () => {
      if (zoneTexte.value.trim()) { zoneErreur.hidden = true; zoneTexte.removeAttribute('aria-invalid'); }
    });
    const choix = await fenetre({
      titre: titre || I18n.t('socle.demander_motif.motif'),
      contenu: contenu,
      boutons: [
        { libelle: I18n.t('commun.bouton.annuler'), valeur: null, classe: 'btn-fantome' },
        { libelle: reglages.libelleValider || I18n.t('socle.demander_motif.valider'), valeur: 'valider', classe: 'btn-primaire', defaut: true },
      ],
      avantFermeture() {
        if (zoneTexte.value.trim() !== '') return true;
        zoneErreur.textContent = I18n.t('socle.demander_motif.motif_obligatoire');
        zoneErreur.hidden = false;
        zoneTexte.setAttribute('aria-invalid', 'true');
        zoneTexte.focus();
        return false;
      },
    });
    return choix === 'valider' ? zoneTexte.value.trim() : null;
  }

  // ===========================================================================================
  // Tableau triable
  // ===========================================================================================

  // Ordre des codes (repères, identifiants, dates ISO) : fixe, le même dans toutes les langues (D154).
  const ordreDesCodes = new Intl.Collator('fr', { numeric: true, sensitivity: 'base' });

  /**
   * Tableau HTML triable par clic sur l'en-tête. Renvoie un élément <div class="table-defile">.
   *   UI.tableau({
   *     colonnes: [
   *       { cle: 'id', libelle: 'N°' },
   *       { cle: 'priorite', libelle: 'Priorité', rendu: (l) => UI.badgePriorite(l.priorite) },
   *       { cle: 'date_prevue', libelle: 'Prévu le', type: 'date', rendu: (l) => UI.dateFr(l.date_prevue) },
   *       { cle: 'cout', libelle: 'Coût', type: 'nombre', valeurTri: (l) => Ordres.cout(l) },
   *       { cle: 'actions', libelle: '', triable: false, rendu: … },
   *     ],
   *     lignes: [...], surClic: (ligne) => …, triInitial: { cle: 'date_prevue', sens: 'desc' },
   *     vide: 'Aucun ordre de travail.', libelle: 'Ordres de travail' (légende pour les lecteurs d'écran)
   *   });
   * rendu(ligne) peut rendre un texte (échappé), un fragment UI.html ou un nœud DOM. Sans rendu, `table` (nom de
   * table du schéma) affiche une valeur de liste par son libellé (Schema.libelleValeur, D155) : { cle: 'statut',
   * libelle: 'Statut', table: 'demandes' }.
   * type 'nombre' : tri numérique et alignement à droite ; type 'date' : ordre des codes ; sinon ordre de la langue
   * active (UI.comparerTextes). Les cellules vides vont toujours à la fin.
   * element.mettreAJour(nouvellesLignes) réaffiche le tableau en gardant le tri.
   */
  function tableau(options) {
    const colonnes = options.colonnes || [];
    let lignes = (options.lignes || []).slice();
    let tri = lireTriInitial(options.triInitial);
    const conteneur = document.createElement('div');
    conteneur.className = 'table-defile';

    function valeurDeTri(colonne, ligne) {
      if (typeof colonne.valeurTri === 'function') return colonne.valeurTri(ligne);
      return ligne[colonne.cle];
    }

    function comparer(ligneA, ligneB, colonne, sens) {
      const valeurA = valeurDeTri(colonne, ligneA);
      const valeurB = valeurDeTri(colonne, ligneB);
      const aVide = valeurA === null || valeurA === undefined || valeurA === '';
      const bVide = valeurB === null || valeurB === undefined || valeurB === '';
      if (aVide || bVide) return aVide === bVide ? 0 : (aVide ? 1 : -1);
      let ecart;
      if (colonne.type === 'nombre') {
        const nombreA = enNombre(valeurA);
        const nombreB = enNombre(valeurB);
        ecart = (nombreA === null ? 0 : nombreA) - (nombreB === null ? 0 : nombreB);
      } else {
        ecart = colonne.type === 'date' ? ordreDesCodes.compare(String(valeurA), String(valeurB))
          : comparerTextes(valeurA, valeurB, { numeric: true, sensitivity: 'base' });
      }
      return sens === 'desc' ? -ecart : ecart;
    }

    function trier() {
      if (!tri) return;
      const colonne = colonnes.find((c) => c.cle === tri.cle);
      if (!colonne) return;
      // tri stable : à égalité, l'ordre d'origine est gardé
      lignes = lignes.map((ligne, rang) => ({ ligne, rang }))
        .sort((a, b) => comparer(a.ligne, b.ligne, colonne, tri.sens) || a.rang - b.rang)
        .map((entree) => entree.ligne);
    }

    function afficher(cleAFocaliser) {
      const table = document.createElement('table');
      table.className = 'table' + (options.classe ? ' ' + options.classe : '');
      if (options.libelle) {
        const legende = document.createElement('caption');
        legende.className = 'visuellement-cache';
        legende.textContent = options.libelle;
        table.appendChild(legende);
      }
      const entete = table.createTHead().insertRow();
      colonnes.forEach((colonne) => {
        const cellule = document.createElement('th');
        cellule.scope = 'col';
        if (colonne.type === 'nombre') cellule.classList.add('num');
        if (colonne.triable === false || !colonne.libelle) {
          cellule.textContent = colonne.libelle || '';
        } else {
          const bouton = document.createElement('button');
          bouton.type = 'button';
          bouton.className = 'tri';
          bouton.dataset.cle = colonne.cle;
          bouton.textContent = colonne.libelle;
          const sens = document.createElement('span');
          sens.className = 'sens';
          sens.setAttribute('aria-hidden', 'true');
          bouton.appendChild(sens);
          bouton.addEventListener('click', () => {
            tri = tri && tri.cle === colonne.cle
              ? { cle: colonne.cle, sens: tri.sens === 'asc' ? 'desc' : 'asc' }
              : { cle: colonne.cle, sens: 'asc' };
            trier();
            afficher(colonne.cle);
          });
          if (tri && tri.cle === colonne.cle) {
            cellule.setAttribute('aria-sort', tri.sens === 'desc' ? 'descending' : 'ascending');
          }
          cellule.appendChild(bouton);
        }
        entete.appendChild(cellule);
      });

      const corps = table.createTBody();
      if (lignes.length === 0) {
        const cellule = corps.insertRow().insertCell();
        cellule.colSpan = Math.max(1, colonnes.length);
        cellule.className = 'vide-table';
        remplir(cellule, options.vide === undefined ? I18n.t('socle.tableau.aucune_ligne_afficher') : options.vide);
      }
      lignes.forEach((ligne) => {
        const rangee = corps.insertRow();
        colonnes.forEach((colonne) => {
          const cellule = rangee.insertCell();
          if (colonne.type === 'nombre') cellule.classList.add('num');
          if (colonne.classe) cellule.className += ' ' + colonne.classe;
          // colonne.table : la cellule est une valeur stockée d'une liste du schéma (D155), affichée par son libellé.
          const contenu = typeof colonne.rendu === 'function' ? colonne.rendu(ligne)
            : colonne.table ? Schema.libelleValeur(colonne.table, colonne.cle, ligne[colonne.cle]) : ligne[colonne.cle];
          remplir(cellule, contenu);
        });
        if (typeof options.surClic === 'function') {
          rangee.classList.add('cliquable');
          rangee.tabIndex = 0;
          rangee.addEventListener('click', (evenement) => {
            // un lien ou un bouton dans la ligne garde son propre comportement
            if (evenement.target.closest('a, button, input, select, textarea, label')) return;
            options.surClic(ligne, evenement);
          });
          rangee.addEventListener('keydown', (evenement) => {
            if ((evenement.key === 'Enter' || evenement.key === ' ') && evenement.target === rangee) {
              evenement.preventDefault();
              options.surClic(ligne, evenement);
            }
          });
        }
      });

      conteneur.textContent = '';
      conteneur.appendChild(table);
      if (cleAFocaliser) {
        const bouton = conteneur.querySelector('th .tri[data-cle="' + cleAFocaliser.replace(/"/g, '') + '"]');
        if (bouton) bouton.focus();
      }
    }

    conteneur.mettreAJour = function (nouvellesLignes) {
      lignes = (nouvellesLignes || []).slice();
      trier();
      afficher();
    };

    trier();
    afficher();
    return conteneur;
  }

  function lireTriInitial(triInitial) {
    if (!triInitial) return null;
    if (typeof triInitial === 'string') return { cle: triInitial, sens: 'asc' };
    return { cle: triInitial.cle, sens: triInitial.sens === 'desc' ? 'desc' : 'asc' };
  }

  // ===========================================================================================
  // Formulaires
  // ===========================================================================================

  /**
   * Champ de formulaire construit d'après le schéma (js/schema.js) : libellé, contrôle, aide, erreur.
   *   UI.champ(Schema.tables.demandes.champs[…], valeurActuelle, {
   *     liste: [{ valeur: 'EQ-0001', libelle: 'CMP-01 — Compresseur' }],   // pour un type 'ref'
   *     aide: 'Texte d'aide', obligatoire: true, lectureSeule: false, libelle: 'Autre libellé',
   *     nom: 'autre_nom', id: 'id-html', placeholder: '…', attributs: { min: '0' }
   *   });
   * Types : texte, texte_long (textarea data-dictee), entier, decimal (virgule acceptée), date,
   * date_heure, booleen (case à cocher), choix (liste des `valeurs`), ref (liste `options.liste`),
   * id et document (texte). Valeur undefined → `defaut` du schéma.
   * Renvoie un <div class="champ" data-champ="nom">. Lire les valeurs avec UI.lireFormulaire(form).
   */
  function champ(definitionChamp, valeur, options) {
    const definition = definitionChamp || {};
    const reglages = options || {};
    const type = definition.type || 'texte';
    const nom = reglages.nom || definition.nom || '';
    const id = reglages.id || identifiantUnique('champ-' + nom);
    const libelle = reglages.libelle || definition.libelle || nom;
    const obligatoire = reglages.obligatoire !== undefined ? Boolean(reglages.obligatoire) : Boolean(definition.obligatoire);
    let valeurTexte;
    if (valeur === undefined) valeurTexte = definition.defaut === undefined ? '' : String(definition.defaut);
    else valeurTexte = valeur === null ? '' : String(valeur);

    const bloc = document.createElement('div');
    bloc.className = 'champ';
    bloc.dataset.champ = nom;
    bloc.dataset.type = type;

    let controle;
    if (type === 'booleen') {
      const etiquette = element(html`<label class="case"><input type="checkbox" id="${id}" value="1"><span></span></label>`);
      controle = etiquette.querySelector('input');
      controle.checked = valeurTexte === '1';
      remplir(etiquette.querySelector('span'), obligatoire
        ? html`${libelle} <span class="requis" aria-hidden="true">*</span>` : libelle);
      bloc.appendChild(etiquette);
    } else {
      const etiquette = document.createElement('label');
      etiquette.className = 'libelle';
      etiquette.htmlFor = id;
      remplir(etiquette, obligatoire ? html`${libelle} <span class="requis" aria-hidden="true">*</span>` : libelle);
      bloc.appendChild(etiquette);
      controle = creerControle(type, definition, valeurTexte, reglages, obligatoire);
      controle.id = id;
      bloc.appendChild(controle);
    }

    controle.name = nom;
    controle.dataset.type = type;
    if (obligatoire) { controle.required = true; controle.setAttribute('aria-required', 'true'); }
    if (reglages.placeholder && 'placeholder' in controle) controle.placeholder = reglages.placeholder;
    if (reglages.lectureSeule) {
      if (controle.tagName === 'SELECT' || controle.type === 'checkbox') controle.disabled = true;
      else controle.readOnly = true;
    }
    Object.keys(reglages.attributs || {}).forEach((attribut) => controle.setAttribute(attribut, reglages.attributs[attribut]));

    const decrit = [];
    if (reglages.aide) {
      const aide = document.createElement('p');
      aide.className = 'aide';
      aide.id = id + '-aide';
      remplir(aide, reglages.aide);
      bloc.appendChild(aide);
      decrit.push(aide.id);
    }
    const erreur = document.createElement('p');
    erreur.className = 'erreur-champ';
    erreur.id = id + '-erreur';
    erreur.hidden = true;
    bloc.appendChild(erreur);
    decrit.push(erreur.id);
    controle.setAttribute('aria-describedby', decrit.join(' '));
    if (reglages.erreur) marquerErreur(bloc, reglages.erreur);
    return bloc;
  }

  function creerControle(type, definition, valeurTexte, reglages, obligatoire) {
    let controle;
    switch (type) {
      case 'texte_long':
        controle = document.createElement('textarea');
        controle.rows = 4;
        controle.setAttribute('data-dictee', ''); // crochet du bouton micro (lot 4)
        controle.value = valeurTexte;
        break;
      case 'entier':
        controle = champSaisie('text', valeurTexte);
        controle.inputMode = 'numeric';
        controle.autocomplete = 'off';
        break;
      case 'decimal':
        controle = champSaisie('text', valeurTexte.replace('.', ','));
        controle.inputMode = 'decimal';
        controle.autocomplete = 'off';
        break;
      case 'date':
        controle = champSaisie('date', valeurTexte.slice(0, 10));
        break;
      case 'date_heure':
        controle = champSaisie('datetime-local', valeurTexte.replace(' ', 'T').slice(0, 16));
        break;
      case 'choix':
        // Valeurs stockées (D155) : libellé affiché par Schema.libelleValeur si le champ vient du schéma (nomTable).
        controle = listeDeroulante((definition.valeurs || []).map((v) => ({ valeur: v,
          libelle: definition.nomTable ? Schema.libelleValeur(definition.nomTable, definition.nom, v) : v })), valeurTexte, obligatoire);
        break;
      case 'ref':
        controle = listeDeroulante((reglages.liste || []).map((entree) => (typeof entree === 'object'
          ? { valeur: String(entree.valeur), libelle: entree.libelle === undefined ? String(entree.valeur) : String(entree.libelle) }
          : { valeur: String(entree), libelle: String(entree) })), valeurTexte, obligatoire);
        break;
      case 'id':
        controle = champSaisie('text', valeurTexte);
        controle.readOnly = true;
        break;
      default: // texte, document et types inconnus
        controle = champSaisie('text', valeurTexte);
        if (definition.protege) { controle.spellcheck = false; controle.autocomplete = 'off'; }
    }
    return controle;
  }

  function champSaisie(typeHtml, valeurTexte) {
    const saisie = document.createElement('input');
    saisie.type = typeHtml;
    saisie.value = valeurTexte;
    return saisie;
  }

  // Liste déroulante ; une valeur actuelle absente de la liste est conservée (signalée « inconnue »).
  function listeDeroulante(entrees, valeurTexte, obligatoire) {
    const liste = document.createElement('select');
    if (!obligatoire || valeurTexte === '') {
      liste.appendChild(new Option(obligatoire ? I18n.t('socle.liste_deroulante.choisir') : '—', ''));
    }
    entrees.forEach((entree) => liste.appendChild(new Option(entree.libelle, entree.valeur)));
    if (valeurTexte !== '' && !entrees.some((entree) => entree.valeur === valeurTexte)) {
      liste.appendChild(new Option(I18n.t('socle.liste_deroulante.valeur_inconnue', { valeurTexte }), valeurTexte));
    }
    liste.value = valeurTexte;
    return liste;
  }

  /**
   * Lit un formulaire : { nom: valeur } avec des CHAÎNES au format du fichier (§3.1) :
   * case à cocher → '1' / '0', decimal et entier → point décimal sans espaces,
   * date_heure → 'AAAA-MM-JJ HH:MM', textes sans espaces de bord. Les champs sans nom sont ignorés.
   */
  function lireFormulaire(formulaire) {
    const valeurs = {};
    Array.from(formulaire.elements).forEach((controle) => {
      const nom = controle.name;
      if (!nom) return;
      if (['button', 'submit', 'reset', 'file'].includes(controle.type) || controle.tagName === 'FIELDSET') return;
      if (controle.type === 'checkbox') {
        valeurs[nom] = controle.checked ? (controle.value && controle.value !== 'on' ? controle.value : '1') : '0';
        return;
      }
      if (controle.type === 'radio') {
        if (controle.checked) valeurs[nom] = controle.value;
        else if (!(nom in valeurs)) valeurs[nom] = '';
        return;
      }
      let valeur = String(controle.value || '').replace(/\r\n/g, '\n').trim();
      const type = controle.dataset.type || '';
      if (type === 'decimal' || type === 'entier') valeur = valeur.replace(/[\s\u00a0\u202f]/g, '').replace(',', '.');
      if (type === 'date_heure' || controle.type === 'datetime-local') valeur = valeur.replace('T', ' ').slice(0, 16);
      valeurs[nom] = valeur;
    });
    return valeurs;
  }

  // Affiche (ou efface, message vide) l'erreur d'un bloc .champ.
  function marquerErreur(bloc, message) {
    const zone = bloc.querySelector('.erreur-champ');
    const controle = bloc.querySelector('input, select, textarea');
    bloc.classList.toggle('en-erreur', Boolean(message));
    if (zone) { zone.textContent = message || ''; zone.hidden = !message; }
    if (controle) {
      if (message) controle.setAttribute('aria-invalid', 'true');
      else controle.removeAttribute('aria-invalid');
    }
  }

  /** Affiche une erreur sous le champ `nom` d'un formulaire (message vide : efface l'erreur). */
  function erreurChamp(formulaire, nom, message) {
    const bloc = Array.from(formulaire.querySelectorAll('.champ')).find((b) => b.dataset.champ === nom);
    if (bloc) marquerErreur(bloc, message);
  }

  /**
   * Vérifie les champs construits par UI.champ : obligatoires remplis, nombres lisibles.
   * Affiche les erreurs sous les champs, place le curseur sur le premier champ en erreur et
   * renvoie la liste [{ nom, message }] (vide si tout va bien).
   */
  function verifierFormulaire(formulaire) {
    const erreurs = [];
    formulaire.querySelectorAll('.champ').forEach((bloc) => {
      const controle = bloc.querySelector('[name]');
      if (!controle) return;
      const type = bloc.dataset.type;
      const valeur = controle.type === 'checkbox' ? (controle.checked ? '1' : '') : String(controle.value || '').trim();
      let message = '';
      if (controle.required && valeur === '') {
        message = controle.type === 'checkbox' ? I18n.t('socle.verifier_formulaire.case_doit_etre_cochee') : I18n.t('socle.verifier_formulaire.champ_obligatoire');
      } else if (valeur !== '' && type === 'entier' && !/^[-+]?\d+$/.test(valeur.replace(/[\s\u00a0\u202f]/g, ''))) {
        message = I18n.t('socle.verifier_formulaire.saisissez_nombre_entier_ex');
      } else if (valeur !== '' && type === 'decimal' && enNombre(valeur) === null) {
        message = I18n.t('socle.verifier_formulaire.saisissez_nombre_ex_12');
      }
      marquerErreur(bloc, message);
      if (message) erreurs.push({ nom: controle.name, message });
    });
    if (erreurs.length) {
      const premier = formulaire.querySelector('[aria-invalid="true"]');
      if (premier) premier.focus();
    }
    return erreurs;
  }

  // ===========================================================================================
  // Sélecteur d'équipement (recherche par repère / désignation, scan QR si caméra)
  // ===========================================================================================

  /**
   * Installe dans `conteneur` un sélecteur d'équipement.
   *   const selecteur = UI.selecteurEquipement(conteneur, {
   *     equipements: Donnees.lignes('equipements'), localisations: Donnees.lignes('localisations'),
   *     valeur: 'EQ-0007', surChoix: (equipement) => …,   // equipement null si on efface le choix
   *     nom: 'equipement_id' (champ caché lu par UI.lireFormulaire), maxResultats: 8
   *   });
   *   selecteur.valeur() → 'EQ-0007' ou '' ; selecteur.choisir(id) ; selecteur.vider()
   * Les équipements inactifs (actif = '0') ne sont pas proposés.
   */
  function selecteurEquipement(conteneur, options) {
    const reglages = options || {};
    const equipements = reglages.equipements || [];
    const libellesLocalisations = new Map((reglages.localisations || []).map((l) => [l.id, l.libelle]));
    const maxResultats = reglages.maxResultats || 8;
    const idRecherche = identifiantUnique('recherche-equipement');
    let valeurCourante = '';

    const bloc = element(html`
      <div class="selecteur-equipement">
        <input type="hidden" name="${reglages.nom || 'equipement_id'}" data-type="ref">
        <div class="selecteur-choisi" hidden>
          <div class="selecteur-resume"></div>
          <button type="button" class="btn btn-secondaire selecteur-changer">${I18n.t('socle.selecteur_equipement.changer')}</button>
        </div>
        <div class="selecteur-recherche">
          <div class="selecteur-ligne">
            <label class="visuellement-cache" for="${idRecherche}">${I18n.t('socle.selecteur_equipement.rechercher_equipement')}</label>
            <input type="search" id="${idRecherche}" autocomplete="off" enterkeyhint="search"
              placeholder="${I18n.t('socle.selecteur_equipement.repere_nom')}">
            ${cameraDisponible() ? html`<button type="button" class="btn btn-secondaire selecteur-scanner">${icone('qr')}${I18n.t('socle.selecteur_equipement.scanner')}</button>` : ''}
          </div>
          <ul class="selecteur-resultats" aria-label="${I18n.t('socle.selecteur_equipement.equipements_trouves')}"></ul>
          <p class="aide selecteur-aide"></p>
        </div>
      </div>`);
    conteneur.textContent = '';
    conteneur.appendChild(bloc);

    const champCache = bloc.querySelector('input[type=hidden]');
    const zoneChoisi = bloc.querySelector('.selecteur-choisi');
    const zoneRecherche = bloc.querySelector('.selecteur-recherche');
    const saisie = bloc.querySelector('input[type=search]');
    const listeResultats = bloc.querySelector('.selecteur-resultats');
    const aide = bloc.querySelector('.selecteur-aide');

    function libelleLocalisation(equipement) {
      return libellesLocalisations.get(equipement.localisation_id) || '';
    }

    function textePourRecherche(equipement) {
      return normaliserRecherche([equipement.repere, equipement.designation, libelleLocalisation(equipement), equipement.id].join(' '));
    }

    function afficherResultats() {
      const mots = normaliserRecherche(saisie.value).split(' ').filter(Boolean);
      const trouves = equipements
        .filter((e) => e.actif !== '0')
        .filter((e) => mots.every((mot) => textePourRecherche(e).includes(mot)))
        .sort((a, b) => ordreDesCodes.compare(a.repere || '', b.repere || ''));
      listeResultats.innerHTML = String(html`${trouves.slice(0, maxResultats).map((e) => html`
        <li><button type="button" class="selecteur-option" data-id="${e.id}">
          <b>${e.repere || e.id}</b><span>${e.designation}</span>${libelleLocalisation(e) ? html`<small>${libelleLocalisation(e)}</small>` : ''}
        </button></li>`)}`);
      const recherche = saisie.value.trim();
      if (trouves.length === 0) aide.textContent = I18n.t('socle.selecteur_equipement.aucun_equipement_correspond', { recherche });
      else if (trouves.length > maxResultats) aide.textContent = I18n.t('socle.selecteur_equipement.equipements_trouves_affiner', { n: trouves.length });
      else aide.textContent = '';
    }

    function choisir(id, sansNotification) {
      const equipement = equipements.find((e) => e.id === id);
      if (!equipement) return false;
      valeurCourante = equipement.id;
      champCache.value = equipement.id;
      remplir(bloc.querySelector('.selecteur-resume'), html`<b>${equipement.repere || equipement.id}</b>${equipement.designation}
        ${libelleLocalisation(equipement) ? html`<small>${libelleLocalisation(equipement)}</small>` : ''}`);
      zoneChoisi.hidden = false;
      zoneRecherche.hidden = true;
      if (!sansNotification && typeof reglages.surChoix === 'function') reglages.surChoix(equipement);
      return true;
    }

    function vider() {
      valeurCourante = '';
      champCache.value = '';
      zoneChoisi.hidden = true;
      zoneRecherche.hidden = false;
      saisie.value = '';
      afficherResultats();
      if (typeof reglages.surChoix === 'function') reglages.surChoix(null);
    }

    saisie.addEventListener('input', afficherResultats);
    saisie.addEventListener('keydown', (evenement) => {
      if (evenement.key === 'Enter') { // Entrée choisit le premier résultat, sans envoyer le formulaire
        evenement.preventDefault();
        const premier = listeResultats.querySelector('.selecteur-option');
        if (premier) choisir(premier.dataset.id);
      }
    });
    listeResultats.addEventListener('click', (evenement) => {
      const option = evenement.target.closest('.selecteur-option');
      if (option) choisir(option.dataset.id);
    });
    bloc.querySelector('.selecteur-changer').addEventListener('click', () => { vider(); saisie.focus(); });
    const boutonScanner = bloc.querySelector('.selecteur-scanner');
    if (boutonScanner) {
      boutonScanner.addEventListener('click', async () => {
        const texte = await scannerQR();
        if (texte === null) return;
        const id = identifiantDepuisQR(texte);
        if (!id || !choisir(id)) toast(I18n.t('socle.selecteur_equipement.qr_code_correspond_aucun'), 'attention');
      });
    }

    if (!(reglages.valeur && choisir(reglages.valeur, true))) afficherResultats();

    return {
      element: bloc,
      valeur: () => valeurCourante,
      choisir: (id) => choisir(id),
      vider,
    };
  }

  /** Identifiant d'équipement lu dans un QR : 'GMAO:EQ-0007' ou 'http://…/#/equipement/EQ-0007'. Sinon null. */
  function identifiantDepuisQR(texte) {
    const correspondance = /(?:^GMAO:|#\/equipement\/)([A-Za-z0-9_-]+)/.exec(String(texte || '').trim());
    return correspondance ? decodeURIComponent(correspondance[1]) : null;
  }

  // ===========================================================================================
  // QR codes : lecture (caméra + jsQR) et dessin (qrcode-generator)
  // ===========================================================================================

  /** Vrai si le scan caméra est possible : page sécurisée (https, localhost, file) + caméra + jsQR. */
  function cameraDisponible() {
    return Boolean(window.isSecureContext && navigator.mediaDevices
      && typeof navigator.mediaDevices.getUserMedia === 'function' && typeof window.jsQR === 'function');
  }

  /**
   * Ouvre la caméra arrière, lit un QR code avec jsQR et renvoie son texte, ou null (Annuler,
   * caméra refusée ou indisponible). En contexte non sécurisé (téléphone en http://192.168…),
   * la caméra n'est pas proposée : le téléphone scanne avec son appareil photo habituel.
   */
  async function scannerQR() {
    if (!cameraDisponible()) {
      toast(I18n.t('socle.scanner_qr.scan_camera_pas_disponible'), 'attention');
      return null;
    }
    let flux = null;
    let actif = true;
    const contenu = element(html`
      <div>
        <div class="scanner"><video playsinline muted></video><div class="scanner-viseur"></div></div>
        <p class="note">${I18n.t('socle.scanner_qr.placez_qr_code_equipement')}</p>
      </div>`);
    const video = contenu.querySelector('video');
    const toile = document.createElement('canvas');
    const contexte = toile.getContext('2d', { willReadFrequently: true });

    function arreterCamera() {
      actif = false;
      if (flux) flux.getTracks().forEach((piste) => piste.stop());
      flux = null;
    }

    const resultat = await fenetre({
      titre: I18n.t('socle.scanner_qr.scanner_qr_code'),
      contenu,
      classe: 'large',
      boutons: [{ libelle: I18n.t('commun.bouton.annuler'), valeur: null, classe: 'btn-secondaire', defaut: true }],
      surOuverture: async (dialogue, fermer) => {
        try {
          flux = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
        } catch (erreur) {
          fermer(null);
          toast(I18n.t('socle.scanner_qr.impossible_ouvrir_camera_autorisation'), 'erreur');
          return;
        }
        if (!actif) { arreterCamera(); return; }
        video.srcObject = flux;
        try { await video.play(); } catch (erreur) { /* la lecture démarre au premier rendu */ }
        const analyser = () => {
          if (!actif) return;
          if (video.readyState >= 2 && video.videoWidth) {
            const echelle = Math.min(1, 640 / video.videoWidth); // image réduite : lecture plus rapide
            toile.width = Math.round(video.videoWidth * echelle);
            toile.height = Math.round(video.videoHeight * echelle);
            contexte.drawImage(video, 0, 0, toile.width, toile.height);
            const image = contexte.getImageData(0, 0, toile.width, toile.height);
            const code = window.jsQR(image.data, image.width, image.height, { inversionAttempts: 'dontInvert' });
            if (code && code.data) { fermer(code.data); return; }
          }
          requestAnimationFrame(analyser);
        };
        requestAnimationFrame(analyser);
      },
    });
    arreterCamera();
    return resultat;
  }

  /**
   * QR code en SVG (noir sur blanc, marge de 4 modules) : UI.qrSvg(texte, 160).
   * Les couleurs sont écrites en dur dans le SVG : un QR doit rester noir sur blanc partout
   * (écran sombre, impression, image exportée).
   */
  function qrSvg(texte, taille) {
    if (typeof window.qrcode !== 'function') throw new Error(I18n.t('socle.qr_svg.bibliotheque_qrcode_absente_js'));
    const generateur = window.qrcode;
    if (generateur.stringToBytesFuncs && generateur.stringToBytesFuncs['UTF-8']) {
      generateur.stringToBytes = generateur.stringToBytesFuncs['UTF-8']; // accents corrects
    }
    const code = generateur(0, 'M'); // version automatique, correction d'erreur moyenne (15 %)
    code.addData(String(texte));
    code.make();
    const modules = code.getModuleCount();
    const marge = 4;
    const cote = modules + marge * 2;
    let chemin = '';
    for (let ligne = 0; ligne < modules; ligne += 1) {
      let colonne = 0;
      while (colonne < modules) {
        if (!code.isDark(ligne, colonne)) { colonne += 1; continue; }
        const debut = colonne;
        while (colonne < modules && code.isDark(ligne, colonne)) colonne += 1;
        const largeur = colonne - debut;
        chemin += 'M' + [debut + marge, ligne + marge].join(' ') + 'h' + largeur + 'v1h-' + largeur + 'z';
      }
    }
    const pixels = Math.round(taille || 160);
    return html`<svg xmlns="http://www.w3.org/2000/svg" class="qr-svg" viewBox="0 0 ${cote} ${cote}" width="${pixels}" height="${pixels}" shape-rendering="crispEdges" role="img" aria-label="${I18n.t('socle.qr_svg.qr_code', { texte })}"><rect width="${cote}" height="${cote}" fill="#fff"/><path fill="#000" d="${chemin}"/></svg>`;
  }

  // ===========================================================================================
  // Photos et fichiers
  // ===========================================================================================

  /**
   * Réduit une photo (File ou Blob) : plus grand côté ≤ tailleMax (1280 par défaut), JPEG qualité 0,85.
   * Renvoie un Blob 'image/jpeg'. L'orientation des photos de téléphone est respectée.
   */
  async function redimensionnerPhoto(fichier, tailleMax) {
    const limite = tailleMax || 1280;
    const image = await chargerImage(fichier);
    const echelle = Math.min(1, limite / Math.max(image.largeur, image.hauteur));
    const largeur = Math.max(1, Math.round(image.largeur * echelle));
    const hauteur = Math.max(1, Math.round(image.hauteur * echelle));
    const toile = document.createElement('canvas');
    toile.width = largeur;
    toile.height = hauteur;
    const contexte = toile.getContext('2d');
    contexte.fillStyle = '#fff'; // le JPEG n'a pas de transparence : fond blanc plutôt que noir
    contexte.fillRect(0, 0, largeur, hauteur);
    contexte.imageSmoothingQuality = 'high';
    contexte.drawImage(image.source, 0, 0, largeur, hauteur);
    image.liberer();
    return new Promise((resoudre, rejeter) => {
      toile.toBlob((blob) => (blob ? resoudre(blob) : rejeter(new Error(I18n.t('socle.redimensionner_photo.photo_pas_pu_etre')))), 'image/jpeg', 0.85);
    });
  }

  async function chargerImage(fichier) {
    if (typeof createImageBitmap === 'function') {
      try {
        const bitmap = await createImageBitmap(fichier, { imageOrientation: 'from-image' });
        return { source: bitmap, largeur: bitmap.width, hauteur: bitmap.height, liberer: () => bitmap.close() };
      } catch (erreur) { /* format non pris en charge par createImageBitmap : on essaie avec <img> */ }
    }
    return new Promise((resoudre, rejeter) => {
      const adresse = URL.createObjectURL(fichier);
      const image = new Image();
      image.onload = () => resoudre({
        source: image, largeur: image.naturalWidth, hauteur: image.naturalHeight, liberer: () => URL.revokeObjectURL(adresse),
      });
      image.onerror = () => {
        URL.revokeObjectURL(adresse);
        rejeter(new Error(I18n.t('socle.charger_image.image_peut_pas_etre')));
      };
      image.src = adresse;
    });
  }

  /**
   * Nom de fichier unique et sûr pour donnees/documents/ : 'DI-2026-0042_20261019-153012_k3f9.jpg'.
   * (Math.random suffit ici : pas de crypto en contexte non sécurisé ; le serveur refuse d'écraser.)
   */
  function nomFichierUnique(prefixe, extension) {
    const maintenant = new Date();
    const horodatage = maintenant.getFullYear() + deuxChiffres(maintenant.getMonth() + 1) + deuxChiffres(maintenant.getDate())
      + '-' + deuxChiffres(maintenant.getHours()) + deuxChiffres(maintenant.getMinutes()) + deuxChiffres(maintenant.getSeconds());
    const hasard = Math.random().toString(36).slice(2, 6).padEnd(4, '0');
    const debut = String(prefixe || 'document').normalize('NFD').replace(/[̀-ͯ]/g, '')
      .replace(/[^A-Za-z0-9._-]+/g, '-').replace(/\.{2,}/g, '.').replace(/^[^A-Za-z0-9]+/, '').slice(0, 60) || 'document';
    const fin = String(extension || 'bin').replace(/[^A-Za-z0-9]/g, '').toLowerCase() || 'bin';
    return debut + '_' + horodatage + '_' + hasard + '.' + fin;
  }

  /** Fait télécharger un fichier au navigateur : UI.telecharger('ot.csv', blob ou texte). */
  function telecharger(nom, contenu, typeMime) {
    const blob = contenu instanceof Blob ? contenu : new Blob([contenu], { type: typeMime || 'text/plain;charset=utf-8' });
    const adresse = URL.createObjectURL(blob);
    const lien = document.createElement('a');
    lien.href = adresse;
    lien.download = nom;
    lien.hidden = true;
    document.body.appendChild(lien);
    lien.click();
    lien.remove();
    setTimeout(() => URL.revokeObjectURL(adresse), 10000);
  }

  // ===========================================================================================
  // Onglets
  // ===========================================================================================

  /**
   * Installe des onglets accessibles (flèches gauche/droite, Début, Fin) dans `conteneur`.
   *   const onglets = UI.onglets(conteneur, [
   *     { id: 'preparation', libelle: 'Préparation', afficher: (panneau) => { … } },
   *     { id: 'execution', libelle: 'Exécution', contenu: UI.html`…`, compteur: 3 },
   *   ], { actif: 'execution', surChangement: (id) => … });
   *   onglets.activer('preparation') ; onglets.actif() ; onglets.panneau('execution') ; onglets.rafraichir(id)
   * Un panneau est rempli à sa première ouverture (afficher ou contenu).
   */
  function onglets(conteneur, listeOnglets, options) {
    const reglages = options || {};
    const prefixe = identifiantUnique('onglet');
    const barre = document.createElement('div');
    barre.className = 'barre-onglets';
    barre.setAttribute('role', 'tablist');
    if (reglages.libelle) barre.setAttribute('aria-label', reglages.libelle);
    const panneaux = {};
    const boutons = {};
    let ongletActif = null;

    conteneur.textContent = '';
    conteneur.classList.add('onglets');
    conteneur.appendChild(barre);

    listeOnglets.forEach((onglet) => {
      const bouton = document.createElement('button');
      bouton.type = 'button';
      bouton.className = 'onglet';
      bouton.id = prefixe + '-' + onglet.id;
      bouton.dataset.onglet = onglet.id;
      bouton.setAttribute('role', 'tab');
      bouton.setAttribute('aria-controls', bouton.id + '-panneau');
      bouton.setAttribute('aria-selected', 'false');
      bouton.tabIndex = -1;
      remplir(bouton, onglet.compteur !== undefined && onglet.compteur !== null
        ? html`${onglet.libelle} <span class="badge">${onglet.compteur}</span>` : onglet.libelle);
      bouton.addEventListener('click', () => activer(onglet.id));
      barre.appendChild(bouton);
      boutons[onglet.id] = bouton;

      const panneau = document.createElement('div');
      panneau.className = 'panneau-onglet';
      panneau.id = bouton.id + '-panneau';
      panneau.dataset.onglet = onglet.id;
      panneau.setAttribute('role', 'tabpanel');
      panneau.setAttribute('aria-labelledby', bouton.id);
      panneau.tabIndex = 0;
      panneau.hidden = true;
      conteneur.appendChild(panneau);
      panneaux[onglet.id] = panneau;
    });

    function remplirPanneau(onglet) {
      const panneau = panneaux[onglet.id];
      if (typeof onglet.afficher === 'function') { panneau.textContent = ''; onglet.afficher(panneau); }
      else remplir(panneau, onglet.contenu);
      panneau.dataset.affiche = '1';
    }

    // Sur téléphone, la barre d'onglets défile : l'onglet choisi est ramené dans sa partie visible
    // (la barre seule défile, jamais la page), après la mise en page.
    function montrerDansLaBarre(bouton) {
      requestAnimationFrame(() => {
        if (barre.scrollWidth <= barre.clientWidth) return;
        const cadre = barre.getBoundingClientRect();
        const place = bouton.getBoundingClientRect();
        if (place.left < cadre.left || place.right > cadre.right) barre.scrollLeft += place.left - cadre.left - 16;
      });
    }

    function activer(id, donnerLeFocus) {
      const onglet = listeOnglets.find((o) => o.id === id);
      if (!onglet) return;
      listeOnglets.forEach((o) => {
        const choisi = o.id === id;
        boutons[o.id].setAttribute('aria-selected', String(choisi));
        boutons[o.id].tabIndex = choisi ? 0 : -1;
        panneaux[o.id].hidden = !choisi;
      });
      if (!panneaux[id].dataset.affiche) remplirPanneau(onglet);
      if (donnerLeFocus) boutons[id].focus();
      montrerDansLaBarre(boutons[id]);
      const change = ongletActif !== id;
      ongletActif = id;
      if (change && typeof reglages.surChangement === 'function') reglages.surChangement(id);
    }

    barre.addEventListener('keydown', (evenement) => {
      const rang = listeOnglets.findIndex((o) => o.id === ongletActif);
      let cible = null;
      if (evenement.key === 'ArrowRight') cible = (rang + 1) % listeOnglets.length;
      else if (evenement.key === 'ArrowLeft') cible = (rang - 1 + listeOnglets.length) % listeOnglets.length;
      else if (evenement.key === 'Home') cible = 0;
      else if (evenement.key === 'End') cible = listeOnglets.length - 1;
      if (cible === null) return;
      evenement.preventDefault();
      activer(listeOnglets[cible].id, true);
    });

    if (listeOnglets.length) activer(reglages.actif && boutons[reglages.actif] ? reglages.actif : listeOnglets[0].id);

    return {
      activer: (id) => activer(id),
      actif: () => ongletActif,
      panneau: (id) => panneaux[id],
      rafraichir(id) {
        const onglet = listeOnglets.find((o) => o.id === (id || ongletActif));
        if (onglet) remplirPanneau(onglet);
      },
    };
  }

  // ===========================================================================================
  // Divers
  // ===========================================================================================

  /** Vrai sur un écran de téléphone (même seuil que le CSS : 640 px). */
  function estTelephone() {
    return window.matchMedia('(max-width: 640px)').matches;
  }

  const CLE_LANGUE = 'prevo.langue';          // lue par js/i18n-chargeur.js avant js/schema.js
  const CLE_LANGUE_INSTALLATION = 'prevo.langue.installation';   // écrite par js/app.js (langue_defaut, T295)

  /** Langue de ce navigateur ramenée à une langue déclarée (I18n.langueDuNavigateur, D150 : sinon l'anglais). */
  function langueDuNavigateur() {
    let langues = [];
    try {
      langues = Array.from(navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language]);
    } catch (erreur) { /* navigateur sans langue lisible : anglais */ }
    return I18n.langueDuNavigateur(langues);
  }

  /**
   * Options (fragment sûr) des langues déclarées, chacune sous son nom dans sa langue (lang posé, jamais traduit, sans
   * drapeau), « choisie » sélectionnée : liste « Langue de Prévo » d'une base neuve (T296 ; assistant d'installation,
   * écran « base vide »), proposée d'après le navigateur (langueDuNavigateur).
   */
  function optionsLangues(choisie) {
    return html`${I18n.langues.map((langue) => html`<option value="${langue.code}" lang="${langue.code}" ${brut(langue.code === choisie ? 'selected' : '')}>${langue.nom}</option>`)}`;
  }

  /**
   * Sélecteur de langue (D147, D148) : <select> des langues déclarées (I18n.langues, ordre de js/i18n/langues.js),
   * chacune sous son nom dans sa langue (jamais traduit, sans drapeau), la langue active choisie. Au changement, le
   * choix est retenu par ce navigateur (localStorage « prevo.langue »), puis la page est rechargée : js/i18n-chargeur.js
   * y charge la langue avant js/schema.js. La langue qu'aurait le poste sans choix (celle de l'installation donnée par
   * la page ou retenue par ce navigateur, sinon, sans réglage, la langue du navigateur : I18n.langueDeLaPage, T295,
   * T297 et T299) retire la clé : le poste suit alors
   * l'installation. Stockage refusé : message court, la liste revient à la langue active, la page reste dans sa langue.
   * Dans la démo (App.mode « demo »), le rechargement efface ce qu'on y a modifié : une confirmation d'abord
   * (UI.confirmer) ; Annuler remet la liste sur la langue active, rien n'est retenu.
   * reglages : { id, classe, libelle (aria-label, quand aucun <label> visible ne nomme la liste) }.
   */
  function selecteurLangue(reglages) {
    const options = reglages || {};
    const liste = document.createElement('select');
    if (options.id) liste.id = options.id;
    if (options.classe) liste.className = options.classe;
    if (options.libelle) liste.setAttribute('aria-label', options.libelle);
    I18n.langues.forEach((langue) => {
      const option = new Option(langue.nom, langue.code);
      option.lang = langue.code;                // lu dans sa langue par un lecteur d'écran
      liste.appendChild(option);
    });
    liste.value = I18n.langue;
    liste.addEventListener('change', async () => {
      const code = liste.value;
      if (code === I18n.langue) return;
      if (typeof App !== 'undefined' && App.mode === 'demo') {
        const accord = await confirmer(I18n.t('socle.selecteur_langue.recharge_demo'), {
          titre: I18n.t('socle.selecteur_langue.changer_langue'), oui: I18n.t('socle.selecteur_langue.changer'), danger: true });
        if (!accord) { liste.value = I18n.langue; return; }
      }
      try {
        const sansChoix = I18n.langueDeLaPage('', window.localStorage.getItem(CLE_LANGUE_INSTALLATION),
          Array.from(navigator.languages || [navigator.language]));
        if (code === sansChoix) window.localStorage.removeItem(CLE_LANGUE);
        else window.localStorage.setItem(CLE_LANGUE, code);
      } catch (erreur) {                        // navigation privée stricte, réglage du navigateur
        liste.value = I18n.langue;
        toast(I18n.t('socle.selecteur_langue.choix_non_retenu'), 'erreur');
        return;
      }
      window.location.reload();
    });
    return liste;
  }

  return Object.freeze({
    // sélecteurs et HTML sûr
    $, $$, echapper, html, brut, estSur, remplir, element, identifiantUnique, normaliserRecherche, comparerTextes,
    // formats français
    dateFr, dateHeureFr, nombreFr, euro, montant: euro, devise, deviseConnue, nomDevise, symboleDevise, heures, enNombre,
    // badges, icônes, logo
    badgePriorite, badgeStatut, badgeValeur, icone, nomsIcones, logo,
    // notifications
    toast, bandeau, vide, chargement,
    // fenêtres
    fenetre, fenetreAction, confirmer, demanderMotif,
    // tableaux et formulaires
    tableau, champ, lireFormulaire, erreurChamp, verifierFormulaire,
    // équipements et QR
    selecteurEquipement, identifiantDepuisQR, cameraDisponible, scannerQR, qrSvg,
    // fichiers
    redimensionnerPhoto, nomFichierUnique, telecharger,
    // mise en page, langue de l'écran
    onglets, estTelephone, selecteurLangue, langueDuNavigateur, optionsLangues,
  });
})();
