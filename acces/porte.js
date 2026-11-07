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
// Langue (T297 ; D148) : js/i18n-chargeur.js, chargé avant ce script, a choisi la langue de la page (choix de ce
// téléphone, sinon langue de l'installation posée par serveur.py dans data-langue-installation, sinon le français) et
// chargé ses textes ; le sélecteur en haut de la page retient le choix du téléphone et recharge la page.
(function () {
  'use strict';

  const DELAI_ESSAI_MS = 2000;
  const NOM_CERTIFICAT = 'prevo-ca.crt';
  const racine = document.documentElement;

  // ===========================================================================================
  // 0. Textes (js/i18n.js, js/i18n/fr.js et la langue choisie par js/i18n-chargeur.js, chargés avant ce script) :
  //    data-i18n de la page, et les deux phrases balisées (nom de fichier, début en gras), écrites par I18n.html
  //    (balisage du dictionnaire, valeurs échappées)
  // ===========================================================================================

  function poserLesTextes() {
    I18n.appliquer(document);
    document.getElementById('titre-fichier-android').innerHTML = String(
      I18n.html('porte.etapes_android.choisissez_fichier', { fichier: NOM_CERTIFICAT }));
    document.getElementById('texte-firefox').innerHTML = String(I18n.html('porte.note_firefox.magasin_certificats'));
  }

  poserLesTextes();

  // ===========================================================================================
  // 0 bis. Sélecteur de langue (T297) : chaque langue déclarée sous son nom dans sa langue (I18n.langues, jamais
  //    traduit) ; le choix est retenu par ce téléphone (localStorage « prevo.langue », la clé de js/i18n-chargeur.js),
  //    puis la page est rechargée. Choisir la langue qu'aurait la page sans choix retire la clé (le téléphone suit alors
  //    l'installation). Stockage refusé : une ligne le dit, la page reste dans sa langue.
  // ===========================================================================================

  const CLE_LANGUE = 'prevo.langue';
  // T324 (Nicolas, 07/11) : la porte (http) et l'application (https) n'ont pas le même stockage ; la langue de la porte
  // passe à l'application dans l'adresse qu'elle ouvre déjà (adresseCible : ?langue=<code>, et langue_neuve=1 si elle
  // vient d'être choisie ici, pendant cette visite : CLE_CHOISIE_ICI, sessionStorage). Aucune adresse nouvelle.
  const CLE_CHOISIE_ICI = 'prevo.langue.choisieSurLaPorte';
  const PARAMETRE_LANGUE = 'langue';
  const PARAMETRE_LANGUE_NEUVE = 'langue_neuve';

  function brancherLangue() {
    const zone = document.getElementById('choix-langue');
    const liste = document.getElementById('langue-liste');
    const refus = document.getElementById('langue-refus');
    I18n.langues.forEach((langue) => {
      const option = new Option(langue.nom, langue.code);
      option.lang = langue.code;                // lu dans sa langue par un lecteur d'écran
      liste.appendChild(option);
    });
    liste.value = I18n.langue;
    zone.hidden = false;
    liste.addEventListener('change', () => {
      const code = liste.value;
      if (code === I18n.langue) return;
      try {
        if (code === I18n.langueDeLaPage('', '')) localStorage.removeItem(CLE_LANGUE);
        else localStorage.setItem(CLE_LANGUE, code);
        try { sessionStorage.setItem(CLE_CHOISIE_ICI, code); } catch (erreur) { /* sans mémoire d'onglet : non transmise neuve */ }
      } catch (erreur) {                        // navigation privée stricte, réglage du navigateur
        liste.value = I18n.langue;
        refus.hidden = false;
        return;
      }
      location.reload();
    });
  }

  brancherLangue();

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

  function lireStockage(stockage, cle) {
    try { return stockage.getItem(cle) || ''; } catch (erreur) { return ''; }
  }

  /** La langue à passer à l'application ({ code, neuve }) : celle choisie sur la porte pendant cette visite (neuve),
   *  sinon celle que ce téléphone a retenue sur la porte ; seulement une langue déclarée ; null sinon (T324). */
  function langueATransmettre() {
    const declaree = (code) => I18n.langues.some((langue) => langue.code === code);
    const choisieIci = lireStockage(window.sessionStorage, CLE_CHOISIE_ICI);
    if (declaree(choisieIci)) return { code: choisieIci, neuve: true };
    const retenue = lireStockage(window.localStorage, CLE_LANGUE);
    return declaree(retenue) ? { code: retenue, neuve: false } : null;
  }

  /** L'application en https, même route ; avec la langue de la porte dans la requête (T324). */
  function adresseCible() {
    const parametres = new URLSearchParams(location.search);
    const langue = langueATransmettre();
    if (langue) {
      parametres.set(PARAMETRE_LANGUE, langue.code);
      if (langue.neuve) parametres.set(PARAMETRE_LANGUE_NEUVE, '1');
    }
    const requete = parametres.toString();
    return origineHttps() + location.pathname + (requete ? '?' + requete : '') + location.hash;
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

  /** Message d'une réponse du serveur (D157, T297) : la clé serveur.<code> dans la langue de la page (valeurs simples
   *  seulement), le français reçu quand la page ne connaît pas le code ; '' sans message. */
  function messageDuServeur(corps) {
    if (!corps || typeof corps.erreur !== 'string') return '';
    const code = typeof corps.erreur_code === 'string' ? corps.erreur_code : '';
    if (!code) return corps.erreur;
    const valeurs = {};
    Object.entries(corps.erreur_valeurs && typeof corps.erreur_valeurs === 'object' ? corps.erreur_valeurs : {})
      .forEach(([nom, valeur]) => { if (typeof valeur === 'string' || typeof valeur === 'number') valeurs[nom] = valeur; });
    const traduit = I18n.t('serveur.' + code, valeurs);
    return traduit === 'serveur.' + code ? corps.erreur : traduit;
  }

  /** Sans autorité locale (certificat fourni par l'informaticien), /acces/ca.crt répond 404 avec l'explication :
   *  le bouton de téléchargement est remplacé par ce texte, dans la langue de la page. */
  async function verifierAutorite() {
    let explication = '';
    try {
      const reponse = await fetch('/acces/ca.crt', { method: 'GET', cache: 'no-store', credentials: 'omit' });
      if (reponse.status === 404) {
        const corps = await reponse.json().catch(() => ({}));
        explication = messageDuServeur(corps) || I18n.t('porte.verifier_autorite.aucun_certificat_telecharger_serveur');
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
    dire(I18n.t('porte.reessayer.verification'), true);
    const ok = await essayer();
    bouton.removeAttribute('aria-busy');
    if (ok) {
      dire(I18n.t('porte.reessayer.telephone_fait_confiance_pc'), true);
      location.replace(adresseCible());
      return;
    }
    dire(I18n.t('porte.reessayer.telephone_fait_pas_encore'));
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

  window.Porte = { systemeDuTelephone, adresseCible, origineHttps, essayer, messageDuServeur };

  demarrer();
})();
