// Porte d'entrée de Prévo (lot 7, ARCHITECTURE.md §22.6 ; D127, CS125, CS137). Script classique, sans dépendance.
//
//   1. Essai : GET https://<même hôte>:<port https>/api/ping, 2 s au plus, en mode « no-cors » : seule compte la
//      réponse du réseau (un certificat refusé par le téléphone, ou un serveur muet, rejettent la promesse ; une
//      réponse opaque suffit, le serveur n'envoie jamais d'en-tête CORS). Réponse ⇒ location.replace vers la même
//      route en https : chemin, paramètres et fragment #/… gardés (fiche d'une étiquette, lien d'invitation).
//   2. Échec ⇒ « Faites confiance au PC atelier » du système reconnu par navigator.userAgent (Android ; iPhone et
//      iPad, dont l'iPad qui se présente en Macintosh tactile ; sinon les deux au choix), puis « Réessayer ».
//
// Le port https vient de l'attribut data-port-https que serveur.py pose en servant la page : jamais une adresse
// codée en dur. Sans attribut (page ouverte hors du serveur), l'essai échoue et les étapes s'affichent.
(function () {
  'use strict';

  const DELAI_ESSAI_MS = 2000;
  const racine = document.documentElement;

  // ===========================================================================================
  // 1. Adresses et essai
  // ===========================================================================================

  function portHttps() {
    return String(racine.dataset.portHttps || '').trim();
  }

  // location.hostname garde les crochets d'une adresse IPv6 : l'origine se recompose telle quelle.
  function origineHttps() {
    return 'https://' + location.hostname + ':' + portHttps();
  }

  function adresseCible() {
    return origineHttps() + location.pathname + location.search + location.hash;
  }

  /** Vrai si l'application en https répond (le téléphone fait confiance au PC atelier). */
  async function essayer() {
    if (!portHttps() || typeof fetch !== 'function' || typeof AbortController !== 'function') return false;
    const controleur = new AbortController();
    const minuteur = setTimeout(() => controleur.abort(), DELAI_ESSAI_MS);
    try {
      await fetch(origineHttps() + '/api/ping', {
        method: 'GET', mode: 'no-cors', cache: 'no-store', credentials: 'omit', signal: controleur.signal,
      });
      return true;
    } catch (erreur) {
      return false;
    } finally {
      clearTimeout(minuteur);
    }
  }

  // ===========================================================================================
  // 2. Système du téléphone
  // ===========================================================================================

  /** 'android', 'iphone' (iPhone, iPad, iPod ; iPad récent : Macintosh tactile), ou '' (inconnu : au choix). */
  function systemeDuTelephone(agent, tactile) {
    const texte = String(agent || '');
    if (/android/i.test(texte)) return 'android';
    if (/iPhone|iPad|iPod/.test(texte)) return 'iphone';
    if (/Macintosh/.test(texte) && tactile) return 'iphone';
    return '';
  }

  // ===========================================================================================
  // 3. Écran « Faites confiance au PC atelier »
  // ===========================================================================================

  const essai = document.getElementById('essai');
  const confiance = document.getElementById('confiance');
  const choix = document.getElementById('choix-systeme');
  const message = document.getElementById('message-essai');
  const noteFirefox = document.getElementById('note-firefox');
  const listes = {
    android: document.getElementById('etapes-android'),
    iphone: document.getElementById('etapes-iphone'),
  };

  function montrerSysteme(systeme) {
    Object.keys(listes).forEach((nom) => { listes[nom].hidden = nom !== systeme; });
    noteFirefox.hidden = systeme !== 'android';
    racine.dataset.systeme = systeme;
  }

  function dire(texte, ok) {
    message.textContent = texte;
    message.classList.toggle('ok', Boolean(ok));
    message.hidden = !texte;
  }

  /** Sans autorité locale (certificat fourni par l'informaticien), /acces/ca.crt répond 404 avec l'explication :
   *  le bouton de téléchargement est remplacé par ce texte. */
  async function verifierAutorite() {
    let explication = '';
    try {
      const reponse = await fetch('/acces/ca.crt', { method: 'GET', cache: 'no-store', credentials: 'omit' });
      if (reponse.status === 404) {
        const corps = await reponse.json().catch(() => ({}));
        explication = corps.erreur || 'Aucun certificat à télécharger sur ce serveur : demandez au responsable.';
      }
    } catch (erreur) {
      return;                                   // réseau muet : on laisse le bouton, l'erreur se verra au clic
    }
    if (!explication) return;
    document.querySelectorAll('.btn-telecharger').forEach((bouton) => {
      const texte = document.createElement('p');
      texte.className = 'message';
      texte.textContent = explication;
      bouton.replaceWith(texte);
    });
  }

  function montrerConfiance() {
    essai.hidden = true;
    confiance.hidden = false;
    const systeme = systemeDuTelephone(navigator.userAgent, navigator.maxTouchPoints > 1);
    choix.hidden = Boolean(systeme);
    if (systeme) montrerSysteme(systeme);
    verifierAutorite();
  }

  async function reessayer(bouton) {
    bouton.setAttribute('aria-busy', 'true');
    dire('Vérification…', true);
    const ok = await essayer();
    bouton.removeAttribute('aria-busy');
    if (ok) {
      dire('Le téléphone fait confiance au PC atelier : ouverture de Prévo…', true);
      location.replace(adresseCible());
      return;
    }
    dire('Le téléphone ne fait pas encore confiance au PC atelier. Vérifiez les étapes ci-dessus, en particulier '
      + 'la dernière avant « Réessayer », puis réessayez.');
  }

  // ===========================================================================================
  // 4. Branchement
  // ===========================================================================================

  choix.querySelectorAll('[data-systeme]').forEach((bouton) => {
    bouton.addEventListener('click', () => montrerSysteme(bouton.dataset.systeme));
  });
  document.querySelectorAll('.btn-reessayer').forEach((bouton) => {
    bouton.addEventListener('click', () => { reessayer(bouton); });
  });

  async function demarrer() {
    if (await essayer()) {
      location.replace(adresseCible());
      return;
    }
    montrerConfiance();
  }

  window.Porte = { systemeDuTelephone, adresseCible, origineHttps, essayer };

  demarrer();
})();
