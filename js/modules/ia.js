'use strict';
// Ia (1/3) — assistant IA optionnel (ARCHITECTURE.md §17 ; brief §10 ; CDC du lot 4, D65 à D72) :
// réglages du poste, portée du fournisseur (ce PC, PC atelier, atelier, en ligne), appel direct ou par
// le relais /api/ia du serveur, délai et annulation, validation des réponses. L'IA propose, l'humain
// valide : rien n'est appelé tant que l'IA n'est pas activée sur le poste, rien n'est écrit sans clic.
// Fichiers du module : ia.js (crée l'objet Ia), ia-prompts.js (consignes), ia-encadre.js (boutons et
// encadré Utiliser / Modifier / Ignorer).
//
// API (utilisée par « Ce poste » et par les écrans des fonctions IA) :
//   Ia.reglages() → { actif, fournisseur: 'ollama' | 'openai', url, modele, cle, delaiS }
//   Ia.enregistrerReglages(modifications) → réglages complets enregistrés (lève IaRefusee si l'on
//     active un fournisseur en ligne sans l'autorisation du responsable)
//   Ia.distantAutorise() ; Ia.portee(url[, mode]) → 'poste' | 'pc-atelier' | 'atelier' | 'distant' ;
//   Ia.mention(portee, url) → « reste sur ce PC »… ; Ia.urlValide(url) ; Ia.active() ;
//   Ia.etat() → 'inconnu' | 'ok' | 'injoignable' ; Ia.verifierAuDemarrage() (appelé par js/app.js) ;
//   Ia.tester([reglagesEssai]) → { ok, modeles, message } ;
//   Ia.demander(fonction, donnees, { signal }) → { resultat, modele, fournisseur } (consignes, schéma et
//     contrôle de chaque fonction : Ia.PROMPTS, dans ia-prompts.js) ;
//   Ia.valider.codes / impact / checkList / commentaire ; Ia.tracerUtilisation(table, id, champ, modele) ;
//   Ia.evenements : événement 'changement' (detail : { raison, etat }) quand les réglages ou l'état changent.
// Erreurs nommées (Ia.IaIndisponible, Ia.IaDelai, Ia.IaAnnulee, Ia.IaReponseInvalide, Ia.IaRefusee,
// toutes filles de Ia.ErreurIa) : message en français, jamais la clé.
// La clé du fournisseur n'est écrite que dans localStorage (prevo.ia) : ni CSV, ni journal, ni console.

const Ia = (() => {

  // Fournisseurs reconnus (brief §10) : Ollama local, ou toute API compatible OpenAI.
  const FOURNISSEURS = {
    ollama: 'Ollama',
    openai: 'API compatible OpenAI',
  };

  const CLE_REGLAGES = 'prevo.ia';
  const DEFAUTS = Object.freeze({
    actif: false, fournisseur: 'ollama', url: 'http://localhost:11434', modele: 'qwen2.5:7b', cle: '', delaiS: 120,
  });
  const DELAI_MIN_S = 1;
  const DELAI_MAX_S = 300;            // plafond du relais du serveur (§17.2)
  const DELAI_TEST_S = 10;            // test de connexion (ouverture, « Tester la connexion »)
  const MARGE_RELAIS_S = 5;           // mode serveur : le serveur coupe d'abord (504), le navigateur ensuite
  const ADRESSE_RELAIS = '/api/ia';
  const TEMPERATURE = 0.2;
  const TEXTE_MAX = 4000;             // tout texte proposé par l'IA
  const OPERATIONS_MAX = 20;
  const OPERATION_MAX = 200;
  const VALEUR_ATTENDUE_MAX = 120;
  const IMPACTS = Object.freeze(['gêne', 'dégradé', 'arrêt', 'sécurité']);
  const FAMILLES_CODES = Object.freeze({ symptome: 'symptôme', cause: 'cause', remede: 'remède' });
  // Chemins du fournisseur (liste fermée du relais) : liste des modèles et conversation.
  const CHEMINS = {
    ollama: { modeles: 'api/tags', chat: 'api/chat' },
    openai: { modeles: 'models', chat: 'chat/completions' },
  };
  const MESSAGE_DISTANT_REFUSE = 'Le responsable n\'a pas autorisé les fournisseurs en ligne (Paramètres, '
    + '« Assistant IA »). L\'IA locale reste possible.';
  const MENTIONS = { poste: 'reste sur ce PC', 'pc-atelier': 'reste sur le PC atelier', atelier: 'reste dans l\'atelier' };
  const MOTIF_JETON = /\{([^{}]*)\}/g;

  const evenements = new EventTarget();
  let etatCourant = 'inconnu';
  let verificationOuverture = null;   // promesse du seul test fait à l'ouverture

  // ===========================================================================================
  // 1. Erreurs nommées
  // ===========================================================================================

  // Mère de toutes les erreurs de l'IA : l'écran les reconnaît par instanceof (Ia.IaDelai…).
  class ErreurIa extends Error {
    constructor(message, cause) {
      super(message);
      this.name = 'ErreurIa';
      if (cause) this.cause = cause;
    }
  }

  // Fabrique une erreur nommée (name = son nom) avec son message par défaut, en français.
  function erreurNommee(nom, messageParDefaut) {
    const Classe = class extends ErreurIa {
      constructor(message, cause) {
        super(message || messageParDefaut, cause);
        this.name = nom;
      }
    };
    Object.defineProperty(Classe, 'name', { value: nom });
    return Classe;
  }

  // Fournisseur injoignable, IA non activée, adresse invalide, accès refusé par le fournisseur.
  const IaIndisponible = erreurNommee('IaIndisponible', 'L\'assistant IA ne répond pas : aucune proposition.');
  // Pas de réponse dans le délai réglé sur le poste.
  const IaDelai = erreurNommee('IaDelai', 'L\'IA n\'a pas répondu dans le délai prévu.');
  // « Annuler » cliqué pendant que l'IA travaillait.
  const IaAnnulee = erreurNommee('IaAnnulee', 'Demande à l\'IA annulée.');
  // Réponse illisible (pas du JSON) ou hors du schéma attendu : aucune proposition.
  const IaReponseInvalide = erreurNommee('IaReponseInvalide', 'Réponse de l\'IA illisible : aucune proposition.');
  // Portée non autorisée : fournisseur en ligne sans l'accord du responsable (D67).
  const IaRefusee = erreurNommee('IaRefusee', MESSAGE_DISTANT_REFUSE);

  // Fournisseur qu'on n'atteint pas (réseau, serveur arrêté) : l'état passe à « injoignable ».
  function erreurReseau(message, cause) {
    const erreur = new IaIndisponible(message, cause);
    erreur.reseau = true;
    return erreur;
  }

  // ===========================================================================================
  // 2. Petits outils
  // ===========================================================================================

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  // Minuscules sans accents : « Dégradé » et « degrade » se comparent pareil.
  function motComparable(valeur) {
    return texte(valeur).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  }

  function modeCourant() {
    return typeof App !== 'undefined' && App ? App.mode : null;
  }

  function signaler(raison) {
    evenements.dispatchEvent(new CustomEvent('changement', { detail: { raison, etat: etat() } }));
  }

  function definirEtat(nouvelEtat) {
    if (etatCourant === nouvelEtat) return;
    etatCourant = nouvelEtat;
    signaler('etat');
  }

  // ===========================================================================================
  // 3. Réglages du poste (localStorage prevo.ia, lecture protégée comme dans js/app.js)
  // ===========================================================================================

  function lireMemoire() {
    try { return window.localStorage.getItem(CLE_REGLAGES); } catch (erreur) { return null; }
  }

  function ecrireMemoire(valeur) {
    try {
      window.localStorage.setItem(CLE_REGLAGES, valeur);
      return true;
    } catch (erreur) {
      return false;
    }
  }

  // Délai en secondes : entier de 1 à 300 ; valeur absente ou illisible → 120.
  function delaiValide(valeur) {
    const nombre = Number(valeur);
    if (valeur === '' || valeur === null || !Number.isFinite(nombre) || nombre <= 0) return DEFAUTS.delaiS;
    return Math.min(Math.max(Math.round(nombre), DELAI_MIN_S), DELAI_MAX_S);
  }

  // Réglages complets et propres, quels que soient ceux lus (champ manquant → valeur par défaut).
  function normaliser(source) {
    const lus = source && typeof source === 'object' ? source : {};
    return {
      actif: lus.actif === true,
      fournisseur: Object.prototype.hasOwnProperty.call(FOURNISSEURS, lus.fournisseur) ? lus.fournisseur : DEFAUTS.fournisseur,
      url: texte(lus.url) || DEFAUTS.url,
      modele: texte(lus.modele) || DEFAUTS.modele,
      cle: texte(lus.cle),
      delaiS: delaiValide(lus.delaiS),
    };
  }

  /** Réglages IA de ce poste (valeurs par défaut si rien n'est mémorisé ou si c'est illisible). */
  function reglages() {
    let lus = null;
    try { lus = JSON.parse(lireMemoire() || 'null'); } catch (erreur) { lus = null; }
    return normaliser(lus);
  }

  /**
   * Enregistre les réglages du poste (les champs absents gardent leur valeur). Renvoie les réglages
   * complets. Activer un fournisseur en ligne sans l'accord du responsable → IaRefusee, rien n'est écrit.
   * Changer de fournisseur, d'adresse ou de clé remet l'état à « inconnu » : « Ce poste » appelle
   * ensuite Ia.tester() (les boutons IA n'apparaissent qu'avec l'état « ok »).
   */
  function enregistrerReglages(modifications) {
    const anciens = reglages();
    const nouveaux = normaliser(Object.assign({}, anciens, modifications || {}));
    if (nouveaux.actif && !porteeAutorisee(nouveaux.url)) throw new IaRefusee();
    if (!ecrireMemoire(JSON.stringify(nouveaux))) {
      console.warn('Prévo : réglages de l\'assistant IA non mémorisés (stockage du navigateur refusé).');
    }
    if (anciens.fournisseur !== nouveaux.fournisseur || anciens.url !== nouveaux.url || anciens.cle !== nouveaux.cle) {
      etatCourant = 'inconnu';
    }
    signaler('reglages');
    return nouveaux;
  }

  /** Réglage partagé du responsable (parametres.csv) : fournisseurs en ligne autorisés ? (D67) */
  function distantAutorise() {
    try {
      return typeof Donnees !== 'undefined' && String(Donnees.parametre('ia_distant_autorise', '0')) === '1';
    } catch (erreur) {
      return false;                     // tables pas encore chargées : non
    }
  }

  // ===========================================================================================
  // 4. Portée du fournisseur et mention
  // ===========================================================================================

  // Adresse utilisable : http(s), un hôte, ni identifiant, ni paramètres, ni fragment (comme le relais).
  function urlValide(url) {
    try {
      const adresse = new URL(texte(url));
      return (adresse.protocol === 'http:' || adresse.protocol === 'https:') && Boolean(adresse.hostname)
        && !adresse.username && !adresse.password && !adresse.search && !adresse.hash;
    } catch (erreur) {
      return false;
    }
  }

  // Nom d'hôte tel qu'affiché (« api.mistral.ai », « [::1] ») ; '' si l'adresse est illisible.
  function hoteAffiche(url) {
    try {
      const adresse = new URL(texte(url));
      return adresse.protocol === 'http:' || adresse.protocol === 'https:' ? adresse.hostname : '';
    } catch (erreur) {
      return '';
    }
  }

  // Les quatre nombres d'une adresse IPv4 (« 192.168.1.20 »), ou null.
  function octetsIPv4(hote) {
    const morceaux = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(hote);
    if (!morceaux) return null;
    const octets = morceaux.slice(1).map(Number);
    return octets.every((octet) => octet <= 255) ? octets : null;
  }

  // Hôte comparable : minuscules, sans crochets ; une IPv4 écrite en IPv6 (::ffff:c0a8:114) redevient IPv4.
  function hoteNormalise(url) {
    const hote = hoteAffiche(url).replace(/^\[|\]$/g, '').toLowerCase();
    const associee = /^::ffff:([0-9a-f]{1,4}):([0-9a-f]{1,4})$/.exec(hote);
    if (!associee) return hote;
    const haut = parseInt(associee[1], 16);
    const bas = parseInt(associee[2], 16);
    return [haut >> 8, haut & 255, bas >> 8, bas & 255].join('.');
  }

  function estBoucleLocale(hote) {
    if (hote === 'localhost' || hote.endsWith('.localhost') || hote === '::1') return true;
    const octets = octetsIPv4(hote);
    return Boolean(octets) && octets[0] === 127;
  }

  // Adresse privée : 10/8, 172.16/12, 192.168/16, liens locaux 169.254/16 ; IPv6 fc00::/7 et fe80::/10 ;
  // noms en .local (mDNS). Ces adresses ne sortent pas du réseau de l'atelier.
  function estAdressePrivee(hote) {
    const octets = octetsIPv4(hote);
    if (octets) {
      const [a, b] = octets;
      return a === 10 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168) || (a === 169 && b === 254);
    }
    if (hote.includes(':')) return /^f[cd][0-9a-f]{2}:/.test(hote) || /^fe[89ab][0-9a-f]:/.test(hote);
    return hote.endsWith('.local');
  }

  /**
   * Où vont les données : 'poste' (boucle locale appelée directement : modes dossier et démo),
   * 'pc-atelier' (boucle locale par le relais : mode serveur), 'atelier' (adresse privée), 'distant'
   * (toute autre adresse, ou adresse illisible). `mode` : celui de l'application par défaut.
   */
  function portee(url, mode) {
    const hote = hoteNormalise(url);
    if (!hote) return 'distant';
    if (estBoucleLocale(hote)) return (mode === undefined ? modeCourant() : mode) === 'serveur' ? 'pc-atelier' : 'poste';
    if (estAdressePrivee(hote)) return 'atelier';
    return 'distant';
  }

  /** Texte de la mention : « reste sur ce PC »… « données envoyées à api.mistral.ai ». Sans argument : ce poste. */
  function mention(porteeConnue, url) {
    const adresse = url === undefined ? reglages().url : url;
    const laPortee = porteeConnue || portee(adresse);
    if (MENTIONS[laPortee]) return MENTIONS[laPortee];
    return 'données envoyées à ' + (hoteAffiche(adresse) || 'un service en ligne');
  }

  function porteeAutorisee(url) {
    return portee(url) !== 'distant' || distantAutorise();
  }

  /** IA utilisable sur ce poste : activée, réglages valides, portée autorisée par le responsable. */
  function active() {
    const r = reglages();
    return r.actif && urlValide(r.url) && r.modele !== '' && porteeAutorisee(r.url);
  }

  /** 'ok' (le fournisseur a répondu), 'injoignable', ou 'inconnu' (pas testé, ou IA inactive). */
  function etat() {
    return active() ? etatCourant : 'inconnu';
  }

  // ===========================================================================================
  // 5. Transport : appel direct ou relais /api/ia, délai et annulation
  // ===========================================================================================

  // Lance travail(signal) ; coupe au bout de delaiS secondes (IaDelai) ou sur « Annuler » (IaAnnulee).
  async function avecDelai(delaiS, delaiAffiche, signalAppelant, travail) {
    if (signalAppelant && signalAppelant.aborted) throw new IaAnnulee();
    const controleur = new AbortController();
    let raison = '';
    const minuteur = setTimeout(() => { raison = 'delai'; controleur.abort(); }, delaiS * 1000);
    const surAnnulation = () => {
      if (!raison) raison = 'annulee';
      controleur.abort();
    };
    if (signalAppelant) signalAppelant.addEventListener('abort', surAnnulation);
    try {
      return await travail(controleur.signal);
    } catch (erreur) {
      if (raison === 'annulee') throw new IaAnnulee();
      if (raison === 'delai') throw messageDelai(delaiAffiche);
      throw erreur;
    } finally {
      clearTimeout(minuteur);
      if (signalAppelant) signalAppelant.removeEventListener('abort', surAnnulation);
    }
  }

  function messageDelai(delaiS) {
    return new IaDelai('L\'IA n\'a pas répondu en ' + delaiS + '\u00a0s (délai du poste). Un PC sans carte '
      + 'graphique peut être lent : réessayez, ou allongez le délai dans « Ce poste ».');
  }

  // Corps d'une réponse : objet JSON si possible, sinon texte.
  async function lireCorps(reponse, signal) {
    let brut;
    try {
      brut = await reponse.text();
    } catch (erreur) {
      if (signal.aborted) throw erreur;
      throw erreurReseau('La réponse du fournisseur d\'IA a été coupée.', erreur);
    }
    try { return JSON.parse(brut); } catch (erreur) { return brut; }
  }

  function messageInjoignable(r) {
    const hote = hoteAffiche(r.url) || 'adresse inconnue';
    if (r.fournisseur === 'ollama' && portee(r.url) === 'poste') {
      return 'Ollama ne répond pas (' + hote + ') : vérifiez qu\'il est lancé et, pour une page ouverte sans '
        + 'serveur, que OLLAMA_ORIGINS l\'autorise (voir le guide).';
    }
    return 'Le fournisseur d\'IA ne répond pas (' + hote + ').';
  }

  // Appel direct (modes dossier et démo) : fetch vers le fournisseur, sans cookie, sans redirection.
  async function appelDirect(r, chemin, methode, corps, signal) {
    const entetes = { Accept: 'application/json' };
    if (methode === 'POST') entetes['Content-Type'] = 'application/json';
    if (r.cle) entetes.Authorization = 'Bearer ' + r.cle;
    let reponse;
    try {
      reponse = await fetch(r.url.replace(/\/+$/, '') + '/' + chemin, {
        method: methode, headers: entetes, body: methode === 'POST' ? JSON.stringify(corps) : undefined,
        signal, cache: 'no-store', credentials: 'omit', redirect: 'manual',
      });
    } catch (erreur) {
      if (signal.aborted) throw erreur;
      throw erreurReseau(messageInjoignable(r), erreur);
    }
    return { statut: reponse.status, corps: await lireCorps(reponse, signal) };
  }

  // Mode serveur : toujours par le relais du serveur (§17.2), téléphones compris.
  async function appelRelais(r, chemin, methode, corps, signal) {
    const demande = { url: r.url.replace(/\/+$/, ''), chemin, methode, delai: r.delaiS };
    if (methode === 'POST') demande.corps = corps;
    if (r.cle) demande.cle = r.cle;
    let reponse;
    try {
      reponse = await fetch(ADRESSE_RELAIS, {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Prevo': '1' },
        body: JSON.stringify(demande), signal, cache: 'no-store',
      });
    } catch (erreur) {
      if (signal.aborted) throw erreur;
      throw erreurReseau('Le serveur Prévo ne répond pas : l\'IA est injoignable pour l\'instant.', erreur);
    }
    const donnees = await lireCorps(reponse, signal);
    if (reponse.status === 504) throw messageDelai(r.delaiS);
    if (reponse.status === 502) {
      throw erreurReseau('Le PC atelier ne joint pas le fournisseur d\'IA (' + (hoteAffiche(r.url) || 'adresse inconnue') + ').');
    }
    if (reponse.status !== 200 || !donnees || typeof donnees !== 'object') {
      const detail = donnees && typeof donnees === 'object' && donnees.erreur ? ' : ' + donnees.erreur : ' (code ' + reponse.status + ').';
      throw new IaIndisponible('Le serveur Prévo a refusé la demande à l\'IA' + detail);
    }
    return { statut: Number(donnees.statut) || 0, corps: donnees.corps };
  }

  function envoyer(r, chemin, methode, corps, signal) {
    return modeCourant() === 'serveur' ? appelRelais(r, chemin, methode, corps, signal)
      : appelDirect(r, chemin, methode, corps, signal);
  }

  // Délai du navigateur : en mode serveur, un peu plus que celui du relais (qui rend 504 le premier).
  function delaiNavigateur(delaiS) {
    return delaiS + (modeCourant() === 'serveur' ? MARGE_RELAIS_S : 0);
  }

  // Message d'un code HTTP du fournisseur (jamais le texte du fournisseur : il pourrait citer la clé).
  function messageStatut(statut, r) {
    if (statut === 403 && r.fournisseur === 'ollama' && modeCourant() !== 'serveur') {
      return 'Ollama refuse cette page (403) : autorisez-la avec OLLAMA_ORIGINS (voir le guide).';
    }
    if (statut === 401 || statut === 403) return 'Le fournisseur d\'IA refuse l\'accès (' + statut + ') : vérifiez la clé.';
    if (statut === 404) return 'Adresse ou modèle « ' + r.modele + ' » introuvable chez le fournisseur d\'IA (404).';
    if (statut === 429) return 'Le fournisseur d\'IA limite les demandes (429) : réessayez plus tard.';
    if (statut === 0 || (statut >= 300 && statut < 400)) return 'Le fournisseur d\'IA répond par une redirection : vérifiez l\'adresse.';
    if (statut >= 500) return 'Le fournisseur d\'IA est en difficulté (' + statut + ') : réessayez plus tard.';
    return 'Le fournisseur d\'IA a refusé la demande (' + statut + ').';
  }

  function verifierStatut(statut, r) {
    if (statut !== 200) throw new IaIndisponible(messageStatut(statut, r));
  }

  // ===========================================================================================
  // 6. Test de connexion (un seul à l'ouverture ; « Tester la connexion » dans « Ce poste »)
  // ===========================================================================================

  function listeModeles(fournisseur, corps) {
    if (fournisseur === 'ollama') {
      return corps && Array.isArray(corps.models) ? corps.models.map((m) => texte(m && (m.name || m.model))).filter(Boolean) : [];
    }
    return corps && Array.isArray(corps.data) ? corps.data.map((m) => texte(m && m.id)).filter(Boolean) : [];
  }

  function modeleDansListe(modele, modeles) {
    return modeles.includes(modele) || modeles.includes(modele + ':latest');
  }

  function messageConnexion(modeles, modele) {
    const nombre = modeles.length + ' modèle' + (modeles.length > 1 ? 's' : '') + ' disponible' + (modeles.length > 1 ? 's' : '');
    if (modeles.length && !modeleDansListe(modele, modeles)) {
      return 'Connexion réussie (' + nombre + '), mais le modèle « ' + modele + ' » n\'est pas dans la liste.';
    }
    return 'Connexion réussie : ' + nombre + '.';
  }

  async function testerAvec(r) {
    if (!urlValide(r.url)) {
      return { ok: false, modeles: [], message: 'Adresse du fournisseur invalide : http://… ou https://… attendu.' };
    }
    if (!porteeAutorisee(r.url)) return { ok: false, modeles: [], message: MESSAGE_DISTANT_REFUSE };
    const delaiS = Math.min(r.delaiS, DELAI_TEST_S);
    const essai = Object.assign({}, r, { delaiS });
    try {
      const reponse = await avecDelai(delaiNavigateur(delaiS), delaiS, null,
        (signal) => envoyer(essai, CHEMINS[r.fournisseur].modeles, 'GET', null, signal));
      if (reponse.statut !== 200) return { ok: false, modeles: [], message: messageStatut(reponse.statut, r) };
      const modeles = listeModeles(r.fournisseur, reponse.corps);
      return { ok: true, modeles, message: messageConnexion(modeles, r.modele) };
    } catch (erreur) {
      return { ok: false, modeles: [], message: erreur instanceof ErreurIa ? erreur.message : messageInjoignable(r) };
    }
  }

  /**
   * Teste le fournisseur (liste des modèles). Sans argument : les réglages du poste, et l'état
   * (ok / injoignable) est mis à jour. Avec `reglagesEssai` : des réglages pas encore enregistrés
   * (« Ce poste »), sans toucher à l'état. Ne lève jamais : { ok, modeles, message }.
   */
  async function tester(reglagesEssai) {
    const pourLePoste = !reglagesEssai;
    const r = pourLePoste ? reglages() : normaliser(Object.assign(reglages(), reglagesEssai));
    const resultat = await testerAvec(r);
    // Adresse invalide ou portée refusée : rien n'a été appelé, l'état reste ce qu'il était.
    if (pourLePoste && urlValide(r.url) && porteeAutorisee(r.url)) definirEtat(resultat.ok ? 'ok' : 'injoignable');
    return resultat;
  }

  /**
   * À l'ouverture de Prévo (js/app.js, après le chargement des tables, sans attendre) : si l'IA est
   * active, un seul test du fournisseur ; sinon AUCUN appel réseau. Promesse de l'état ; ne lève jamais.
   */
  function verifierAuDemarrage() {
    try {
      signaler('ouverture');                      // mention de la coque, avant même le test
      if (!active()) return Promise.resolve(etat());
      if (!verificationOuverture) verificationOuverture = tester().then(() => etat(), () => etat());
      return verificationOuverture;
    } catch (erreur) {
      console.warn('Prévo : vérification de l\'assistant IA impossible (' + (erreur && erreur.message) + ').', erreur);
      return Promise.resolve('inconnu');
    }
  }

  // ===========================================================================================
  // 7. Demander une proposition
  // ===========================================================================================

  function contenuRecu(fournisseur, corps) {
    if (fournisseur === 'ollama') {
      if (corps && corps.message && typeof corps.message.content === 'string') return corps.message.content;
      throw new IaReponseInvalide();
    }
    const message = corps && Array.isArray(corps.choices) && corps.choices[0] && corps.choices[0].message;
    if (message && typeof message.content === 'string') return message.content;
    if (message && message.refusal) throw new IaReponseInvalide('L\'IA a refusé de répondre : aucune proposition.');
    throw new IaReponseInvalide();
  }

  // Conversation : sortie JSON contrainte par le schéma ; repli si le fournisseur refuse le schéma (400).
  async function discuter(r, fonction, messages, schema, signal) {
    if (r.fournisseur === 'ollama') {
      const corps = { model: r.modele, messages, stream: false, format: schema, options: { temperature: TEMPERATURE } };
      let reponse = await envoyer(r, CHEMINS.ollama.chat, 'POST', corps, signal);
      // Ollama antérieur à la version 0.5 : pas de schéma, seulement format « json » (le schéma est aussi dans la consigne).
      if (reponse.statut === 400) reponse = await envoyer(r, CHEMINS.ollama.chat, 'POST', Object.assign({}, corps, { format: 'json' }), signal);
      verifierStatut(reponse.statut, r);
      return contenuRecu('ollama', reponse.corps);
    }
    const base = { model: r.modele, messages, temperature: TEMPERATURE };
    const avecSchema = { type: 'json_schema', json_schema: { name: fonction, schema, strict: true } };
    let reponse = await envoyer(r, CHEMINS.openai.chat, 'POST', Object.assign({}, base, { response_format: avecSchema }), signal);
    if (reponse.statut === 400) {
      reponse = await envoyer(r, CHEMINS.openai.chat, 'POST', Object.assign({}, base, { response_format: { type: 'json_object' } }), signal);
    }
    verifierStatut(reponse.statut, r);
    return contenuRecu('openai', reponse.corps);
  }

  // Objet JSON écrit par l'IA (accepte un bloc ```json … ``` ou un texte autour de l'objet).
  function objetJson(contenu) {
    const brut = texte(contenu).replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
    const essais = [brut];
    const debut = brut.indexOf('{');
    const fin = brut.lastIndexOf('}');
    if (debut !== -1 && fin > debut) essais.push(brut.slice(debut, fin + 1));
    for (const essai of essais) {
      try {
        const objet = JSON.parse(essai);
        if (objet && typeof objet === 'object' && !Array.isArray(objet)) return objet;
      } catch (erreur) { /* essai suivant */ }
    }
    throw new IaReponseInvalide();
  }

  function libelleFournisseur(r) {
    return r.fournisseur === 'ollama' ? FOURNISSEURS.ollama : (hoteAffiche(r.url) || FOURNISSEURS.openai);
  }

  /**
   * Demande une proposition à l'IA pour une fonction de Ia.PROMPTS. Renvoie
   * { resultat, modele, fournisseur } (resultat contrôlé par Ia.PROMPTS[fonction].verifier) ; sinon une
   * erreur nommée. options.signal : AbortSignal du bouton « Annuler ». Rien n'est écrit.
   */
  async function demander(fonction, donnees, options) {
    const consigne = Ia.PROMPTS && Object.prototype.hasOwnProperty.call(Ia.PROMPTS, fonction) ? Ia.PROMPTS[fonction] : null;
    if (!consigne) throw new Error('Ia.demander : fonction inconnue « ' + fonction + ' ».');
    const r = reglages();
    if (!r.actif) throw new IaIndisponible('L\'assistant IA n\'est pas activé sur ce poste (« Ce poste »).');
    if (!urlValide(r.url)) throw new IaIndisponible('Adresse du fournisseur d\'IA invalide (« Ce poste »).');
    if (!porteeAutorisee(r.url)) throw new IaRefusee();
    const valeurs = donnees && typeof donnees === 'object' ? donnees : {};
    const messages = [{ role: 'system', content: consigne.systeme }, { role: 'user', content: consigne.utilisateur(valeurs) }];
    const schema = consigne.schema(valeurs);
    try {
      const contenu = await avecDelai(delaiNavigateur(r.delaiS), r.delaiS, options && options.signal,
        (signal) => discuter(r, fonction, messages, schema, signal));
      const resultat = consigne.verifier(objetJson(contenu), valeurs);
      definirEtat('ok');
      return { resultat, modele: r.modele, fournisseur: libelleFournisseur(r) };
    } catch (erreur) {
      if (erreur && erreur.reseau) definirEtat('injoignable');     // les boutons IA se masquent
      throw erreur;
    }
  }

  // ===========================================================================================
  // 8. Validations pures (Ia.valider)
  // ===========================================================================================

  /**
   * Codes proposés → { symptome, cause, remede, rejetes: [{ champ, code }] } : un code n'est gardé que
   * s'il existe dans codes_defaillance ET dans la bonne famille (D70) ; sinon il est rejeté et listé.
   */
  function codes(objet, lignesCodes) {
    const resultat = { symptome: '', cause: '', remede: '', rejetes: [] };
    const source = objet && typeof objet === 'object' ? objet : {};
    const lignes = Array.isArray(lignesCodes) ? lignesCodes : [];
    Object.keys(FAMILLES_CODES).forEach((champ) => {
      const code = texte(source[champ]);
      if (!code) return;
      const connu = lignes.some((ligne) => ligne && ligne.code === code && ligne.famille === FAMILLES_CODES[champ]);
      if (connu) resultat[champ] = code; else resultat.rejetes.push({ champ, code });
    });
    return resultat;
  }

  /** Impact proposé → 'gêne' | 'dégradé' | 'arrêt' | 'sécurité', ou null s'il n'est pas dans la liste. */
  function impact(valeur) {
    if (typeof valeur !== 'string') return null;
    const cherche = motComparable(valeur);
    return IMPACTS.find((possible) => motComparable(possible) === cherche) || null;
  }

  function refusCheckList(raison) {
    return { ok: false, operations: [], raison: 'Check-list refusée : ' + raison + '.' };
  }

  /** Check-list proposée → { ok, operations: [{ operation, valeur_attendue }], raison } (1 à 20 opérations). */
  function checkList(objet) {
    const liste = objet && typeof objet === 'object' && Array.isArray(objet.operations) ? objet.operations : null;
    if (!liste) return refusCheckList('la réponse ne contient pas de liste d\'opérations');
    if (!liste.length) return refusCheckList('aucune opération proposée');
    if (liste.length > OPERATIONS_MAX) return refusCheckList('plus de ' + OPERATIONS_MAX + ' opérations proposées');
    const operations = [];
    for (const element of liste) {
      const operation = texte(element && element.operation);
      const valeurAttendue = texte(element && element.valeur_attendue);
      if (!operation) return refusCheckList('une opération est vide');
      if (operation.length > OPERATION_MAX) return refusCheckList('une opération dépasse ' + OPERATION_MAX + ' caractères');
      if (valeurAttendue.length > VALEUR_ATTENDUE_MAX) {
        return refusCheckList('une valeur attendue dépasse ' + VALEUR_ATTENDUE_MAX + ' caractères');
      }
      operations.push({ operation, valeur_attendue: valeurAttendue });
    }
    return { ok: true, operations, raison: '' };
  }

  function refusCommentaire(raison) {
    return { ok: false, texte: '', raison: 'Commentaire refusé : ' + raison + '.' };
  }

  /**
   * Commentaire à jetons (D71) → { ok, texte, raison } : refusé si un chiffre apparaît hors d'un jeton
   * {nom} connu, ou si un jeton est inconnu ; sinon le texte avec chaque jeton remplacé par sa valeur.
   */
  function commentaire(texteIa, jetons) {
    const source = typeof texteIa === 'string' ? texteIa.trim() : '';
    const valeurs = jetons && typeof jetons === 'object' ? jetons : {};
    if (!source) return refusCommentaire('le commentaire est vide');
    if (source.length > TEXTE_MAX) return refusCommentaire('le commentaire dépasse 4\u00a0000 caractères');
    const inconnus = [];
    const sansJetons = source.replace(MOTIF_JETON, (jeton, nom) => {
      if (!Object.prototype.hasOwnProperty.call(valeurs, nom.trim())) inconnus.push(jeton);
      return ' ';
    });
    if (inconnus.length) return refusCommentaire('jeton inconnu ' + inconnus[0]);
    if (/[{}]/.test(sansJetons)) return refusCommentaire('accolade sans jeton complet');
    const chiffre = /\p{Nd}[\p{Nd}\s.,%]*/u.exec(sansJetons);
    if (chiffre) {
      return refusCommentaire('chiffre écrit en clair (« ' + chiffre[0].trim() + ' ») : seuls les jetons {…} portent les chiffres');
    }
    const final = source.replace(MOTIF_JETON, (jeton, nom) => texte(valeurs[nom.trim()]));
    if (final.length > TEXTE_MAX) return refusCommentaire('le commentaire dépasse 4\u00a0000 caractères');
    return { ok: true, texte: final, raison: '' };
  }

  // ===========================================================================================
  // 9. Trace d'utilisation (D65)
  // ===========================================================================================

  /**
   * Journal « proposition IA utilisée (<modèle>) : <champ> » : appelé par l'écran APRÈS l'enregistrement
   * réussi d'un champ rempli par « Utiliser » ou « Modifier ». Promesse (identifiant de l'entrée ou null).
   */
  function tracerUtilisation(table, id, champ, modele) {
    return Donnees.journaliser(table, id, 'proposition IA utilisée (' + texte(modele) + ') : ' + texte(champ));
  }

  // Autorisation du responsable changée (parametres.csv, sur ce poste ou un autre) : « changement »
  // (raison 'autorisation'), pour que les écrans posent ou retirent leurs boutons sans réafficher (D67).
  let autorisationConnue = null;
  if (typeof Donnees !== 'undefined' && Donnees.evenements) {
    Donnees.evenements.addEventListener('changement', (evenement) => {
      if (!((evenement.detail && evenement.detail.tables) || []).includes('parametres')) return;
      const autorise = distantAutorise();
      if (autorise !== autorisationConnue) { autorisationConnue = autorise; signaler('autorisation'); }
    });
  }

  return {
    FOURNISSEURS, DEFAUTS, IMPACTS, FAMILLES_CODES, TEXTE_MAX,
    ErreurIa, IaIndisponible, IaDelai, IaAnnulee, IaReponseInvalide, IaRefusee,
    evenements,
    reglages, enregistrerReglages, distantAutorise, urlValide, portee, mention, active, etat,
    verifierAuDemarrage, tester, demander,
    valider: Object.freeze({ codes, impact, checkList, commentaire }),
    tracerUtilisation,
  };
})();
