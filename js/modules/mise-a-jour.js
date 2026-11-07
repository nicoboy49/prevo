// Mise à jour signalée (D120, CS118 ; ARCHITECTURE.md §21). Les utilisateurs ne surveillent pas GitHub : Prévo lit
// https://prevo.pro/version.json au plus une fois par jour et par poste (numéro, date, adresse de téléchargement,
// nouveautés) et, quand une version plus récente existe, le dit par un bandeau discret sur l'accueil du responsable et
// une ligne dans « À propos ». Jamais d'installation automatique ; version égale ou plus ancienne, fichier absent,
// injoignable ou mal formé : rien, sans erreur visible. Rien pour le technicien, le demandeur ni la démo en ligne
// (App.versionWeb). Numéros SemVer (T216) : une bêta (2.0.0-beta.2) est prévenue de la finale (2.0.0) ; une
// installation stable n'est jamais prévenue d'une bêta.
// T305 (D174-D176, décisions de Nicolas des 06 et 07/11) : active par défaut (maj_signalee absente = '1'), coupée par
// maj_signalee = '0' (Paramètres › Mises à jour, texte à côté de la case) ; tant que le responsable n'a rien réglé,
// un bandeau d'information unique par poste le dit (« Compris ») ; la lecture n'envoie rien que la requête elle-même
// (credentials omit, aucun Referer, aucune redirection suivie, aucun paramètre) ; l'adresse de téléchargement n'est
// gardée que vers https://prevo.pro ou https://github.com/nicoboy49/prevo (sinon aucun bandeau) ; nouveautes_en
// (facultatif) est montré en anglais, sinon nouveautes. C'est la seule connexion que Prévo ouvre de lui-même.
window.MiseAJour = (function () {
  'use strict';

  const ADRESSE_PAR_DEFAUT = 'https://prevo.pro/version.json';
  const PARAMETRE = 'maj_signalee';          // parametres.csv (responsable, Paramètres) : '1' = autorisé
  const CLE_LECTURE = 'prevo.majLecture';    // poste : { date: 'AAAA-MM-JJ', fichier: {…} | null } (une lecture par jour)
  const CLE_IGNOREE = 'prevo.majIgnoree';    // poste : version que le responsable a choisi de ne plus voir
  const CLE_INFORMEE = 'prevo.majInformee';  // poste : le bandeau d'information unique a été lu (« Compris », T305)
  const SITE_PREVO = 'prevo.pro';            // D176 : seules adresses de téléchargement gardées (https, hôte exact)
  const DEPOT_GITHUB = '/nicoboy49/prevo';
  const DELAI_MS = 5000;                     // au-delà, le fichier est tenu pour injoignable (aucune erreur montrée)
  const NOUVEAUTES_MAX = 3;
  const LONGUEUR_MAX = 200;
  const MOTIF_VERSION = /^(\d{1,4})\.(\d{1,4})\.(\d{1,4})(?:-([0-9A-Za-z]{1,20}(?:\.[0-9A-Za-z]{1,20}){0,3}))?$/;
  const MOTIF_DATE = /^\d{4}-\d{2}-\d{2}$/;

  /** Adresse lue : window.PREVO_ADRESSE_VERSION (tests, faux serveur local) sinon prevo.pro. */
  function adresse() {
    const forcee = window.PREVO_ADRESSE_VERSION;
    return typeof forcee === 'string' && forcee ? forcee : ADRESSE_PAR_DEFAUT;
  }

  // localStorage peut être refusé (navigation privée, réglage) : on continue sans mémoire.
  function lireMemoire(cle) {
    try { return window.localStorage.getItem(cle); } catch (erreur) { return null; }
  }

  function ecrireMemoire(cle, valeur) {
    try { window.localStorage.setItem(cle, valeur); } catch (erreur) { /* sans mémoire : tant pis */ }
  }

  function lireJson(cle) {
    try { return JSON.parse(lireMemoire(cle) || 'null'); } catch (erreur) { return null; }
  }

  function aujourdhui() {
    const d = new Date();
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }

  /** « 1.2.0 » → [1, 2, 0] ; « 2.0.0-beta.2 » → [2, 0, 0, 'beta', 2] (identifiants de pré-version : nombre ou
   *  texte) ; null si ce n'est pas un numéro de version. */
  function nombres(version) {
    const trouve = typeof version === 'string' ? MOTIF_VERSION.exec(version.trim()) : null;
    if (!trouve) return null;
    const pre = trouve[4] ? trouve[4].split('.').map((id) => (/^\d+$/.test(id) ? Number(id) : id)) : [];
    return [Number(trouve[1]), Number(trouve[2]), Number(trouve[3])].concat(pre);
  }

  // Ordre de deux identifiants de pré-version (SemVer §11) : deux nombres entre eux, deux textes dans l'ordre ASCII,
  // un nombre avant un texte.
  function comparerIdentifiants(x, y) {
    if (typeof x === 'number' && typeof y === 'number') return x - y;
    if (typeof x === 'number') return -1;
    if (typeof y === 'number') return 1;
    return x < y ? -1 : (x > y ? 1 : 0);
  }

  /** Vrai si la version a est plus récente que la version b (tableaux de nombres(), null = jamais plus récent).
   *  SemVer (T216) : une pré-version passe avant sa finale (2.0.0-beta.2 < 2.0.0) ; deux pré-versions se comparent
   *  identifiant par identifiant (beta.2 < beta.10 < rc.1), la plus courte d'abord à égalité (beta < beta.1). */
  function plusRecente(a, b) {
    if (!a || !b) return false;
    for (let i = 0; i < 3; i += 1) {
      if (a[i] !== b[i]) return a[i] > b[i];
    }
    if (a.length === 3 || b.length === 3) return a.length === 3 && b.length > 3;
    for (let i = 3; i < Math.min(a.length, b.length); i += 1) {
      const ordre = comparerIdentifiants(a[i], b[i]);
      if (ordre !== 0) return ordre > 0;
    }
    return a.length > b.length;
  }

  /** Vrai si la version lue est à signaler à l'installation : plus récente, et jamais une pré-version (bêta) à une
   *  installation stable (T216 ; un canal bêta à part viendra au Lot 4). Une bêta est prévenue de la finale. */
  function aSignaler(lue, installee) {
    return plusRecente(lue, installee) && (lue.length === 3 || installee.length > 3);
  }

  /** D176 : vrai pour une adresse https de prevo.pro ou du dépôt GitHub de Prévo (hôte exact, sans nom ni mot de
   *  passe, port par défaut) ; toute autre adresse (http, autre site, sous-domaine, autre dépôt) est refusée. */
  function adresseDeTelechargementPermise(texte) {
    let url;
    try { url = new URL(texte); } catch (erreur) { return false; }
    if (url.protocol !== 'https:' || url.username || url.password || url.port) return false;
    if (url.hostname === SITE_PREVO) return true;
    return url.hostname === 'github.com' && (url.pathname === DEPOT_GITHUB || url.pathname.startsWith(DEPOT_GITHUB + '/'));
  }

  function nettoyerNouveautes(liste) {
    return (Array.isArray(liste) ? liste : [])
      .filter((n) => typeof n === 'string' && n.trim())
      .slice(0, NOUVEAUTES_MAX)
      .map((n) => n.replace(/\s+/g, ' ').trim().slice(0, LONGUEUR_MAX));
  }

  /** Contenu de version.json vérifié et nettoyé : { version, date, adresse, nouveautes, nouveautesEn } ; null s'il est
   *  mal formé ou si son adresse de téléchargement n'est pas permise (D176). */
  function lireFichier(objet) {
    if (!objet || typeof objet !== 'object') return null;
    const version = typeof objet.version === 'string' ? objet.version.trim() : '';
    const adresseFichier = typeof objet.adresse === 'string' ? objet.adresse.trim() : '';
    if (!nombres(version) || !adresseDeTelechargementPermise(adresseFichier)) return null;
    const date = typeof objet.date === 'string' && MOTIF_DATE.test(objet.date.trim()) ? objet.date.trim() : '';
    // nouveautesEn (lu dans nouveautes_en, ou déjà nettoyé dans la mémoire du poste)
    const nouveautesEn = nettoyerNouveautes(objet.nouveautes_en !== undefined ? objet.nouveautes_en : objet.nouveautesEn);
    return { version, date, adresse: adresseFichier, nouveautes: nettoyerNouveautes(objet.nouveautes), nouveautesEn };
  }

  /** Nouveautés à montrer : en anglais (nouveautes_en) dans un Prévo affiché en anglais s'il y en a, sinon en
   *  français (nouveautes), comme Nicolas l'a décidé le 06/11. */
  function nouveautesAffichees(fichier) {
    return I18n.langue === 'en' && fichier.nouveautesEn.length ? fichier.nouveautesEn : fichier.nouveautes;
  }

  // T305 : active sauf maj_signalee = '0' (absente : active, D175).
  function autorisee() {
    return typeof Donnees !== 'undefined' && String(Donnees.parametre(PARAMETRE, '1')).trim() !== '0';
  }

  // Le responsable n'a encore rien réglé (clé absente ou vide) : le bandeau d'information unique est à montrer.
  function jamaisReglee() {
    return typeof Donnees !== 'undefined' && Donnees.parametre(PARAMETRE, '') === '';
  }

  function responsable() {
    const profil = typeof App !== 'undefined' ? App.profil : null;
    return Boolean(profil && profil.type === 'responsable');
  }

  /** Vrai quand Prévo a le droit de lire le fichier : poste du responsable, autorisé, jamais en version web ni dans la
   *  démo (atelier fictif en mémoire, index.html ouvert directement : T305, comme avant la vérification par défaut). */
  function active() {
    return typeof App !== 'undefined' && !App.versionWeb && App.mode !== 'demo' && responsable() && autorisee();
  }

  async function telecharger() {
    try {
      // Rien que la requête : ni cookie ni identifiant (credentials omit), ni adresse de la page (no-referrer), aucune
      // redirection suivie, aucun paramètre. L'origine (Origin) est ajoutée par le navigateur lui-même (dit dans la doc).
      const reponse = await fetch(adresse(), { cache: 'no-store', credentials: 'omit', referrerPolicy: 'no-referrer',
        redirect: 'error', signal: AbortSignal.timeout(DELAI_MS) });
      if (!reponse.ok) return null;
      return lireFichier(await reponse.json());
    } catch (erreur) {
      return null;                           // injoignable, refusé, mal formé : rien à montrer
    }
  }

  /** Lecture du jour sur ce poste ({ date, fichier }), ou null si aucune lecture n'a eu lieu aujourd'hui. */
  function lectureDuJour() {
    const lecture = lireJson(CLE_LECTURE);
    return lecture && lecture.date === aujourdhui() ? lecture : null;
  }

  /** La version plus récente à signaler ({ version, date, adresse, nouveautes }), ou null. */
  function disponible() {
    if (!active()) return null;
    const lecture = lectureDuJour();
    const fichier = lecture && lecture.fichier ? lireFichier(lecture.fichier) : null;
    if (!fichier || !aSignaler(nombres(fichier.version), nombres(App.version))) return null;
    if (lireMemoire(CLE_IGNOREE) === fichier.version) return null;
    return fichier;
  }

  /**
   * Vérifie une fois par jour et par poste (D120) : lit le fichier si aucune lecture n'a eu lieu aujourd'hui, garde
   * le résultat (même nul : un échec compte pour la lecture du jour), puis met l'accueil à jour s'il est affiché.
   */
  async function verifier() {
    if (!active()) return null;
    if (!lectureDuJour()) {
      const fichier = await telecharger();
      ecrireMemoire(CLE_LECTURE, JSON.stringify({ date: aujourdhui(), fichier }));
    }
    afficherSiPossible();
    return disponible();
  }

  function ignorer(version) {
    ecrireMemoire(CLE_IGNOREE, String(version));
  }

  /** Bandeau de l'accueil du responsable : version, date, nouveautés, lien de téléchargement, « Ignorer ». */
  function bandeau(fichier) {
    const bloc = UI.bandeau('info', UI.html`<b>${fichier.date ? I18n.t('mise.bandeau.disponible_date', { version: fichier.version, date: UI.dateFr(fichier.date) })
      : I18n.t('mise.bandeau.disponible', { version: fichier.version })}</b>
      ${nouveautesAffichees(fichier).length ? UI.html`<span class="maj-nouveautes">${nouveautesAffichees(fichier).join(' · ')}</span>` : ''}
      <a href="${fichier.adresse}" target="_blank" rel="noopener" class="maj-telecharger">${I18n.t('mise.bandeau.telecharger')}</a>
      <button type="button" class="btn btn-fantome maj-ignorer">${I18n.t('mise.bandeau.ignorer_version')}</button>`);
    bloc.id = 'maj-bandeau';
    bloc.querySelector('.maj-ignorer').addEventListener('click', () => { ignorer(fichier.version); bloc.remove(); });
    return bloc;
  }

  /** T305 : bandeau d'information unique (vérification active sans que le responsable l'ait réglée) ; « Compris » le
   *  retire pour ce poste ; régler la case dans Paramètres le retire partout. */
  function bandeauInformation() {
    const bloc = UI.bandeau('info', UI.html`<span>${I18n.t('mise.information.verification_jour')}</span>
      <button type="button" class="btn btn-fantome maj-compris">${I18n.t('mise.information.compris')}</button>`);
    bloc.id = 'maj-information';
    bloc.querySelector('.maj-compris').addEventListener('click', () => { ecrireMemoire(CLE_INFORMEE, '1'); bloc.remove(); });
    return bloc;
  }

  /** Remplit la zone #maj-zone de l'accueil si elle est affichée (vide quand rien n'est à signaler). */
  function afficherSiPossible() {
    const zone = document.getElementById('maj-zone');
    if (!zone) return;
    zone.replaceChildren();
    if (active() && jamaisReglee() && lireMemoire(CLE_INFORMEE) !== '1') zone.appendChild(bandeauInformation());
    const fichier = disponible();
    if (fichier) zone.appendChild(bandeau(fichier));
  }

  /** Ligne « Mise à jour » de la page À propos (fragment UI.html). */
  function ligneApropos() {
    if (typeof App !== 'undefined' && App.versionWeb) return UI.html`${I18n.t('mise.ligne_apropos.demo_ligne_aucune_verification')}`;
    if (typeof App !== 'undefined' && App.mode === 'demo') return UI.html`${I18n.t('mise.ligne_apropos.demo_aucune_verification')}`;
    if (!responsable()) return UI.html`${I18n.t('mise.ligne_apropos.signalee_responsable_accueil_ici')}`;
    if (!autorisee()) return UI.html`${I18n.t('mise.ligne_apropos.non_verifiee_responsable_peut')}`;
    const fichier = disponible();
    if (fichier) {
      // Phrase balisée (lien au milieu) : I18n.html, balisage écrit dans le dictionnaire, valeurs échappées.
      return fichier.date
        ? I18n.html('mise.ligne_apropos.disponible_date', { version: fichier.version, date: UI.dateFr(fichier.date),
          adresse: fichier.adresse })
        : I18n.html('mise.ligne_apropos.disponible', { version: fichier.version, adresse: fichier.adresse });
    }
    const lecture = lectureDuJour();
    if (!lecture) return UI.html`${I18n.t('mise.ligne_apropos.verification_cours')}`;
    if (!lecture.fichier) return UI.html`${I18n.t('mise.ligne_apropos.verification_impossible_aujourd_hui')}`;
    return UI.html`${I18n.t('mise.ligne_apropos.prevo_jour_verifie', { date: UI.dateFr(lecture.date) })}`;
  }

  return { adresse, verifier, disponible, ignorer, afficherSiPossible, ligneApropos, nombres, plusRecente, aSignaler,
    lireFichier, adresseDeTelechargementPermise,
    PARAMETRE, CLE_LECTURE, CLE_IGNOREE, CLE_INFORMEE };
})();
