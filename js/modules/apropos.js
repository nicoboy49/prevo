'use strict';
// Apropos : écran « À propos » (#/apropos, tous profils ; brief §9 E13 et « Signature »).
// Version, mode de stockage, aide (guide), limites de sécurité, bibliothèques et licences, crédit.

const Apropos = (() => {

  /** Adresses de Prévo, à ce seul endroit (T306 ; réutilisées par la mention « traduction automatique » du Lot 5).
   *  Les formulaires d'issue GitHub (.github/ISSUE_TEMPLATE/) se pré-remplissent par paramètre portant l'id du champ. */
  const ADRESSES = Object.freeze({
    depot: 'https://github.com/prevo-pro/prevo',
    suggestion: Object.freeze({ fr: '2-proposer-une-amelioration.yml', en: '3-suggest-an-improvement.yml' }),
    traduction: '4-corriger-une-traduction.yml',          // Lot 5 (T343, CS161) : formulaire bilingue
    courriel: 'contact@prevo.pro',
  });

  /** Navigateur réduit à « nom version, système » (« Chrome 130, Windows ») : rien d'autre de l'en-tête du
   *  navigateur ne part. `ua` = navigator.userAgent, `donneesUa` = navigator.userAgentData (facultatif). */
  function navigateurReduit(ua, donneesUa) {
    ua = String(ua || '');
    let nom = '';
    let version = '';
    const marques = donneesUa && Array.isArray(donneesUa.brands) ? donneesUa.brands : [];
    for (const [marque, libelle] of [['Microsoft Edge', 'Edge'], ['Google Chrome', 'Chrome']]) {
      const trouvee = marques.find((m) => m && m.brand === marque);
      if (trouvee && /^\d+/.test(String(trouvee.version))) { nom = libelle; version = String(trouvee.version).match(/^\d+/)[0]; break; }
    }
    if (!nom) {
      for (const [motif, libelle] of [[/(?:Edg|EdgA|EdgiOS)\/(\d+)/, 'Edge'], [/(?:Firefox|FxiOS)\/(\d+)/, 'Firefox'],
        [/(?:Chrome|CriOS)\/(\d+)/, 'Chrome'], [/Version\/(\d+)[^]*Safari\//, 'Safari']]) {
        const trouve = ua.match(motif);
        if (trouve) { nom = libelle; version = trouve[1]; break; }
      }
    }
    if (!nom) return I18n.t('apropos.suggestion.navigateur_inconnu');
    let systeme = '';
    const plateforme = donneesUa && typeof donneesUa.platform === 'string' ? donneesUa.platform : '';
    if (['Windows', 'macOS', 'Linux', 'Android'].includes(plateforme)) systeme = plateforme;
    else if (/iPhone|iPad|iPod/.test(ua)) systeme = 'iOS';
    else if (/Android/.test(ua)) systeme = 'Android';
    else if (/Windows/.test(ua)) systeme = 'Windows';
    else if (/Macintosh|Mac OS X/.test(ua)) systeme = 'macOS';
    else if (/Linux|X11/.test(ua)) systeme = 'Linux';
    return nom + ' ' + version + (systeme ? ', ' + systeme : '');
  }

  /** Contenu pré-rempli d'une suggestion : version de Prévo, langue active, navigateur réduit. Aucune donnée de la base. */
  function contexteSuggestion() {
    return I18n.t('apropos.suggestion.contexte', { version: App.version, langue: I18n.langue,
      navigateur: navigateurReduit(navigator.userAgent, navigator.userAgentData) });
  }

  /** Paramètres d'adresse « nom=valeur&… », valeurs encodées. */
  function requete(parametres) {
    return Object.keys(parametres).map((nom) => nom + '=' + encodeURIComponent(parametres[nom])).join('&');
  }

  /** Adresse du formulaire de suggestion sur GitHub (modèle anglais si Prévo est en anglais, sinon français). */
  function adresseSuggestion() {
    const modele = I18n.langue === 'en' ? ADRESSES.suggestion.en : ADRESSES.suggestion.fr;
    return ADRESSES.depot + '/issues/new?' + requete({ template: modele,
      title: I18n.t('apropos.suggestion.titre_formulaire'), contexte: contexteSuggestion() });
  }

  /** Repli par e-mail : même contenu. */
  function adresseCourriel() {
    return 'mailto:' + ADRESSES.courriel + '?' + requete({ subject: I18n.t('apropos.suggestion.courriel_objet'),
      body: contexteSuggestion() });
  }

  /** Lien « Suggérer une amélioration » (nouvel onglet) ; rien ne part tant qu'on ne clique pas. */
  function lienSuggestion(id) {
    return UI.html`<a id="${id}" href="${adresseSuggestion()}" target="_blank" rel="noopener noreferrer">${I18n.t('apropos.suggestion.lien')}</a>`;
  }

  /** Mention d'une langue traduite automatiquement (Lot 5, T343, CS161 ; statut « automatique » dans js/i18n/langues.js) :
   *  « Traduction automatique — corrections bienvenues », le lien ouvrant (nouvel onglet) le formulaire d'issue
   *  « Corriger une traduction » pré-rempli avec la langue et le même contexte que la suggestion. '' pour une autre
   *  langue (français, anglais). Rien ne part tant qu'on ne clique pas. */
  function mentionTraduction(id) {
    const langue = I18n.langues.find((declaree) => declaree.code === I18n.langue);
    if (!langue || langue.statut !== 'automatique') return '';
    const adresse = ADRESSES.depot + '/issues/new?' + requete({ template: ADRESSES.traduction,
      title: I18n.t('apropos.traduction.titre_formulaire'), langue: langue.code, contexte: contexteSuggestion() });
    return UI.html`<span class="mention-traduction">${I18n.t('apropos.traduction.automatique')} — <a id="${id}" href="${adresse}" target="_blank" rel="noopener noreferrer">${I18n.t('apropos.traduction.corrections')}</a></span>`;
  }

  /** Crédit (signature) ; lu à l'affichage. */
  function credit() {
    return I18n.t('apropos.credit.developpe_claude_anthropic_demande');
  }

  /** Bibliothèques embarquées dans js/lib/ (textes complets des licences dans js/lib/LICENCES.txt) ; lues à
   *  l'affichage. */
  function bibliotheques() {
    return [
      { nom: 'PapaParse', version: '5.7.0', licence: 'MIT', role: I18n.t('apropos.bibliotheques.lecture_fichiers_csv') },
      { nom: 'qrcode-generator', version: '2.0.4', licence: 'MIT', role: I18n.t('apropos.bibliotheques.dessin_qr_codes') },
      { nom: 'jsQR', version: '1.4.0', licence: 'Apache-2.0', role: I18n.t('apropos.bibliotheques.lecture_qr_codes_camera') },
      { nom: 'ECharts', version: '5.5.1', licence: 'Apache-2.0', role: I18n.t('apropos.bibliotheques.graphiques_indicateurs') },
      { nom: I18n.t('apropos.bibliotheques.sheet_js'), version: '0.20.3', licence: 'Apache-2.0', role: I18n.t('apropos.bibliotheques.lecture_fichiers_excel_open_document') },
      { nom: I18n.t('apropos.bibliotheques.police_sora'), version: '', licence: I18n.t('apropos.bibliotheques.ofl_1_1'), role: I18n.t('apropos.bibliotheques.police_caracteres') },
    ];
  }

  /** Libellé d'un mode de stockage (serveur, dossier, demo) ; lu à l'affichage. */
  function libelleMode(mode) {
    if (mode === 'serveur') return I18n.t('apropos.libelle_mode.serveur');
    if (mode === 'dossier') return I18n.t('apropos.libelle_mode.dossier');
    if (mode === 'demo') return I18n.t('apropos.libelle_mode.demo');
    return '';
  }

  // Modèle qui a construit le wiki de la démo (lot 6, §20.10) : lu dans son journal, en mode démo seulement.
  function modeleWikiDemo(mode) {
    if (mode !== 'demo') return '';
    const entree = Donnees.lignes('wiki_journal').find((ligne) => ligne.nature === 'ingestion' && ligne.modele);
    return entree ? entree.modele : '';
  }

  function afficher(conteneur) {
    const mode = App.mode;
    const libelleStockage = App.adaptateur ? App.adaptateur.libelle : '';
    // Lot 7 (D126) : avec les comptes exigés, le profil vient du compte et le serveur vérifie les droits ; la limite
    // « ce n'est pas une sécurité » ne vaut que sans comptes (portée « ce PC », modes dossier et démo).
    const comptesExiges = typeof App.comptesExiges === 'function' && App.comptesExiges();
    const modeleWiki = modeleWikiDemo(mode);
    UI.remplir(conteneur, UI.html`
      <div class="entete-page">
        <div>
          <h1>${I18n.t('apropos.ecran.propos_prevo')}</h1>
          <p>${I18n.t('apropos.ecran.gmao_libre_atelier_parc')}</p>
        </div>
      </div>
      <div class="grille">
        <article class="carte c6">
          <h2>${I18n.t('apropos.ecran.version')}</h2>
          <dl class="valeurs">
            <dt>${I18n.t('apropos.ecran.application')}</dt><dd>${I18n.t('apropos.ecran.prevo_gmao')}</dd>
            <dt>${I18n.t('apropos.ecran.version')}</dt><dd>${App.version}</dd>
            <dt>${I18n.t('commun.champ.date')}</dt><dd>${UI.dateFr(App.dateVersion)}</dd>
            <dt>${I18n.t('apropos.ecran.mise_jour')}</dt><dd id="apropos-maj">${typeof MiseAJour !== 'undefined' ? MiseAJour.ligneApropos() : ''}</dd>
            <dt>${I18n.t('apropos.ecran.contenu')}</dt><dd>${I18n.t('apropos.ecran.lots_1_4_parc')}</dd>
            <dt>${I18n.t('apropos.ecran.stockage_actuel')}</dt><dd>${libelleStockage || libelleMode(mode) || '—'}</dd>
          </dl>
        </article>
        <article class="carte c6">
          <h2>${I18n.t('apropos.ecran.trois_modes_stockage')}</h2>
          <ul class="apropos-liste">
            <li>${I18n.html('apropos.ecran.serveur_lancer_gmao_bat')}</li>
            <li>${I18n.html('apropos.ecran.dossier_index_html_ouvert')}</li>
            <li>${modeleWiki ? I18n.html('apropos.modes.demo_modele', { modele: modeleWiki }) : I18n.html('apropos.modes.demo')}</li>
          </ul>
          <p class="note">${I18n.t('apropos.ecran.tous_modes_donnees_sont')}</p>
        </article>
        <article class="carte c6">
          <h2>${I18n.t('apropos.ecran.limites_connaitre')}</h2>
          <ul class="apropos-liste">
            ${comptesExiges ? UI.html`
            <li>${I18n.t('apropos.ecran.chaque_personne_compte_role')}</li>
            <li>${I18n.t('apropos.ecran.usage_reseau_local_reseau')}</li>` : UI.html`
            <li>${I18n.t('apropos.ecran.profils_adaptent_ecrans_pas')}</li>
            <li>${I18n.t('apropos.ecran.usage_reseau_local_uniquement')}</li>`}
            <li>${I18n.t('apropos.ecran.assistant_ia_facultatif_regle')}</li>
            <li>${I18n.t('apropos.ecran.dictee_chrome_edge_voix')}</li>
          </ul>
        </article>
        <article class="carte c6">
          <h2>${I18n.t('apropos.ecran.aide')}</h2>
          <p>${I18n.html('apropos.ecran.ouvrir_guide_utilisation_demarrer', { guide: UI.adresseGuide() })}</p>
          <p id="apropos-suggestion">${lienSuggestion('apropos-suggestion-lien')} (<a id="apropos-suggestion-courriel" href="${adresseCourriel()}">${I18n.t('apropos.suggestion.lien_courriel')}</a>)</p>
          <p class="note">${I18n.t('apropos.suggestion.explication')}</p>
          ${mentionTraduction('apropos-traduction-lien') ? UI.html`<p class="note" id="apropos-traduction">${mentionTraduction('apropos-traduction-lien')}</p>` : ''}
        </article>
        <article class="carte c6">
          <h2>${I18n.t('apropos.ecran.bibliotheques_licences')}</h2>
          <p>${I18n.t('apropos.ecran.code_prevo_sous_licence')}</p>
          <ul class="apropos-liste">
            ${bibliotheques().map((b) => UI.html`<li><b>${b.nom}${b.version ? ' ' + b.version : ''}</b> — ${b.licence} (${b.role})</li>`)}
          </ul>
          <p><a href="js/lib/LICENCES.txt" target="_blank" rel="noopener">${I18n.t('apropos.ecran.lire_texte_complet_licences')}</a></p>
        </article>
      </div>
      <article class="carte apropos-credit">
        ${UI.logo()}
        <p>${credit()}</p>
      </article>`);
  }

  // App est chargé après les modules : l'écran est enregistré une fois la page lue.
  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'apropos',
      route: /^#\/apropos$/,
      get titre() { return I18n.t('apropos.ecran.titre'); },
      menu: { get libelle() { return I18n.t('apropos.menu.libelle'); }, icone: 'apropos', ordre: 100 },
      profils: ['demandeur', 'technicien', 'responsable'],
      tables: [],
      afficher,
    });
  });

  return { get CREDIT() { return credit(); }, ADRESSES, navigateurReduit, adresseSuggestion, adresseCourriel, lienSuggestion,
    mentionTraduction, afficher };
})();
