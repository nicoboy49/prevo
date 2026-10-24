// Mise à jour signalée (D120, CS118 ; ARCHITECTURE.md §21). Les utilisateurs ne surveillent pas GitHub : si le
// responsable l'a autorisé dans Paramètres (maj_signalee), Prévo lit https://prevo.pro/version.json au plus une fois
// par jour et par poste (numéro, date, adresse de téléchargement, nouveautés en deux lignes) et, quand une version
// plus récente existe, le dit par un bandeau discret sur l'accueil du responsable et une ligne dans « À propos ».
// Jamais d'installation automatique ; version égale ou plus ancienne, fichier absent, injoignable ou mal formé :
// rien, sans erreur visible. Rien pour le technicien, le demandeur ni la démo en ligne (App.versionWeb).
window.MiseAJour = (function () {
  'use strict';

  const ADRESSE_PAR_DEFAUT = 'https://prevo.pro/version.json';
  const PARAMETRE = 'maj_signalee';          // parametres.csv (responsable, Paramètres) : '1' = autorisé
  const CLE_LECTURE = 'prevo.majLecture';    // poste : { date: 'AAAA-MM-JJ', fichier: {…} | null } (une lecture par jour)
  const CLE_IGNOREE = 'prevo.majIgnoree';    // poste : version que le responsable a choisi de ne plus voir
  const DELAI_MS = 5000;                     // au-delà, le fichier est tenu pour injoignable (aucune erreur montrée)
  const NOUVEAUTES_MAX = 3;
  const LONGUEUR_MAX = 200;
  const MOTIF_VERSION = /^\d{1,4}\.\d{1,4}\.\d{1,4}$/;
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

  /** « 1.2.0 » → [1, 2, 0] ; null si ce n'est pas un numéro de version. */
  function nombres(version) {
    return typeof version === 'string' && MOTIF_VERSION.test(version.trim()) ? version.trim().split('.').map(Number) : null;
  }

  /** Vrai si la version a est plus récente que la version b (tableaux de nombres(), null = jamais plus récent). */
  function plusRecente(a, b) {
    if (!a || !b) return false;
    for (let i = 0; i < 3; i += 1) {
      if (a[i] !== b[i]) return a[i] > b[i];
    }
    return false;
  }

  /** Contenu de version.json vérifié et nettoyé : { version, date, adresse, nouveautes } ; null s'il est mal formé. */
  function lireFichier(objet) {
    if (!objet || typeof objet !== 'object') return null;
    const version = typeof objet.version === 'string' ? objet.version.trim() : '';
    const adresseFichier = typeof objet.adresse === 'string' ? objet.adresse.trim() : '';
    if (!nombres(version) || !/^https:\/\//.test(adresseFichier)) return null;
    const date = typeof objet.date === 'string' && MOTIF_DATE.test(objet.date.trim()) ? objet.date.trim() : '';
    const nouveautes = (Array.isArray(objet.nouveautes) ? objet.nouveautes : [])
      .filter((n) => typeof n === 'string' && n.trim())
      .slice(0, NOUVEAUTES_MAX)
      .map((n) => n.replace(/\s+/g, ' ').trim().slice(0, LONGUEUR_MAX));
    return { version, date, adresse: adresseFichier, nouveautes };
  }

  function autorisee() {
    return typeof Donnees !== 'undefined' && String(Donnees.parametre(PARAMETRE, '0')) === '1';
  }

  function responsable() {
    const profil = typeof App !== 'undefined' ? App.profil : null;
    return Boolean(profil && profil.type === 'responsable');
  }

  /** Vrai quand Prévo a le droit de lire le fichier : poste du responsable, autorisé, jamais en version web. */
  function active() {
    return typeof App !== 'undefined' && !App.versionWeb && responsable() && autorisee();
  }

  async function telecharger() {
    try {
      const reponse = await fetch(adresse(), { cache: 'no-store', signal: AbortSignal.timeout(DELAI_MS) });
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
    if (!fichier || !plusRecente(nombres(fichier.version), nombres(App.version))) return null;
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
    const bloc = UI.bandeau('info', UI.html`<b>Prévo ${fichier.version} est disponible${fichier.date ? ' (' + UI.dateFr(fichier.date) + ')' : ''}.</b>
      ${fichier.nouveautes.length ? UI.html`<span class="maj-nouveautes">${fichier.nouveautes.join(' · ')}</span>` : ''}
      <a href="${fichier.adresse}" target="_blank" rel="noopener" class="maj-telecharger">Télécharger</a>
      <button type="button" class="btn btn-fantome maj-ignorer">Ignorer cette version</button>`);
    bloc.id = 'maj-bandeau';
    bloc.querySelector('.maj-ignorer').addEventListener('click', () => { ignorer(fichier.version); bloc.remove(); });
    return bloc;
  }

  /** Remplit la zone #maj-zone de l'accueil si elle est affichée (vide quand rien n'est à signaler). */
  function afficherSiPossible() {
    const zone = document.getElementById('maj-zone');
    if (!zone) return;
    zone.replaceChildren();
    const fichier = disponible();
    if (fichier) zone.appendChild(bandeau(fichier));
  }

  /** Ligne « Mise à jour » de la page À propos (fragment UI.html). */
  function ligneApropos() {
    if (typeof App !== 'undefined' && App.versionWeb) return UI.html`Démo en ligne : aucune vérification.`;
    if (!responsable()) return UI.html`Signalée au responsable, sur l'accueil et ici.`;
    if (!autorisee()) return UI.html`Non vérifiée : le responsable peut l'autoriser dans Paramètres (« Me signaler les nouvelles versions »).`;
    const fichier = disponible();
    if (fichier) {
      return UI.html`<b>Prévo ${fichier.version} est disponible</b>${fichier.date ? ' (' + UI.dateFr(fichier.date) + ')' : ''} —
        <a href="${fichier.adresse}" target="_blank" rel="noopener">télécharger</a>`;
    }
    const lecture = lectureDuJour();
    if (!lecture) return UI.html`Vérification en cours…`;
    if (!lecture.fichier) return UI.html`Vérification impossible aujourd'hui (prevo.pro injoignable) : rien d'autre à faire.`;
    return UI.html`Prévo est à jour (vérifié le ${UI.dateFr(lecture.date)}).`;
  }

  return { adresse, verifier, disponible, ignorer, afficherSiPossible, ligneApropos, nombres, plusRecente, lireFichier,
    PARAMETRE, CLE_LECTURE, CLE_IGNOREE };
})();
