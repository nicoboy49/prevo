'use strict';
// StockageServeur : adaptateur de stockage « serveur » (le PC qui fait tourner serveur.py).
// Contrat : docs/ARCHITECTURE.md §6 (adaptateurs) et §7 (API du serveur).
// Tout passe par fetch vers /api/… (même origine que la page). Ce fichier n'utilise ni crypto,
// ni presse-papiers : il doit marcher en http://192.168.x.x:8080 depuis un téléphone
// (contexte non sécurisé). Les versions (SHA-256) et les sauvegardes sont calculées par le serveur.
// Dépendances : Donnees (js/donnees.js) pour les erreurs ErreurConflit et ErreurStockage, Schema
// (js/schema.js) pour la liste des tables ; lues au moment des appels, pas au chargement.

const StockageServeur = (() => {

  const DELAI_DETECTION_MS = 2000;
  const NOM_APPLICATION = 'Prévo';
  const MESSAGE_SERVEUR_INJOIGNABLE =
    'Le serveur Prévo ne répond pas. Vérifiez que la fenêtre du serveur est ouverte sur le PC.';
  // Délai maximal d'une requête (réponse et lecture du corps comprises).
  const DELAI_REPONSE_MS = 15000;
  const MESSAGE_DELAI_DEPASSE = 'Le serveur Prévo met trop de temps à répondre. Vérifiez le réseau puis '
    + 'réessayez ; si vous enregistriez, rechargez la page pour voir si la modification a été faite.';
  // Réponse « réussie » mais illisible (ex. page d'un portail Wi-Fi, proxy) : l'écriture a pu se faire.
  const MESSAGE_REPONSE_INATTENDUE =
    'Réponse inattendue du serveur ; l\'opération a peut-être été faite, rechargez la page.';

  // ===========================================================================
  // Détection
  // ===========================================================================

  // Vrai si un serveur Prévo répond sur cette adresse (« » = le site qui a servi la page).
  // Abandonne au bout de 2 secondes : l'application bascule alors vers l'écran de démarrage.
  async function detecter(base = '') {
    const controleur = new AbortController();
    const minuteur = setTimeout(function () { controleur.abort(); }, DELAI_DETECTION_MS);
    try {
      const reponse = await fetch(base + '/api/ping', { signal: controleur.signal, cache: 'no-store' });
      if (!reponse.ok) { return false; }
      const donnees = await reponse.json();
      return Boolean(donnees) && donnees.application === NOM_APPLICATION;
    } catch (erreur) {
      return false;     // réseau coupé, délai dépassé, réponse qui n'est pas du JSON : pas de serveur
    } finally {
      clearTimeout(minuteur);
    }
  }

  // ===========================================================================
  // Requêtes et correspondance des erreurs
  // ===========================================================================

  // Lit le JSON d'une réponse ; null si le corps n'est pas du JSON.
  async function lireJsonOuNull(reponse) {
    try {
      return await reponse.json();
    } catch (erreur) {
      return null;
    }
  }

  // Transforme une réponse en erreur (409 → ErreurConflit, autre code ≥ 400 → ErreurStockage).
  async function erreurDepuisReponse(reponse) {
    const donnees = await lireJsonOuNull(reponse);
    const message = (donnees && donnees.erreur)
      || 'Le serveur a refusé la demande (code ' + reponse.status + ').';
    if (reponse.status === 409) {
      const versionActuelle = donnees && donnees.version_actuelle !== undefined
        ? donnees.version_actuelle : null;
      return new Donnees.ErreurConflit(message, versionActuelle);
    }
    // 423 (fichier ouvert dans Excel) et tous les autres codes : le message du serveur est lisible tel quel.
    return new Donnees.ErreurStockage(message);
  }

  // Erreur pendant l'envoi ou la lecture : délai dépassé (requête abandonnée) ou serveur injoignable.
  function erreurReseau(erreur) {
    if (erreur && erreur.name === 'AbortError') {
      return new Donnees.ErreurStockage(MESSAGE_DELAI_DEPASSE, erreur);
    }
    return new Donnees.ErreurStockage(MESSAGE_SERVEUR_INJOIGNABLE, erreur);
  }

  // Envoie la requête et rend la réponse, quel que soit son code (l'appelant décide).
  // Échec réseau (serveur arrêté, câble débranché) → ErreurStockage au message prévu.
  // Pas de réponse en 15 s → requête abandonnée, ErreurStockage « met trop de temps à répondre ».
  // Le minuteur n'est pas arrêté à la réception des en-têtes : il couvre aussi la lecture du
  // corps (abandonner une requête déjà entièrement lue n'a aucun effet).
  // Toute requête qui écrit (PUT, POST) envoie un corps, même vide, et l'en-tête X-Prevo: 1.
  async function appeler(url, options) {
    const controleur = new AbortController();
    setTimeout(function () { controleur.abort(); }, DELAI_REPONSE_MS);
    try {
      return await fetch(url, Object.assign({ cache: 'no-store' }, options, { signal: controleur.signal }));
    } catch (erreur) {
      throw erreurReseau(erreur);
    }
  }

  // Comme appeler, mais lève l'erreur correspondante pour tout code ≥ 400.
  async function appelerOuErreur(url, options) {
    const reponse = await appeler(url, options);
    if (reponse.status >= 400) { throw await erreurDepuisReponse(reponse); }
    return reponse;
  }

  // Lit l'objet JSON d'une réponse réussie. Échec de lecture en route = délai ou serveur
  // injoignable ; corps lu mais qui n'est pas un objet JSON = réponse inattendue.
  async function lireJson(reponse) {
    let texte;
    try {
      texte = await reponse.text();
    } catch (erreur) {
      throw erreurReseau(erreur);
    }
    let donnees;
    try {
      donnees = JSON.parse(texte);
    } catch (erreur) {
      throw new Donnees.ErreurStockage(MESSAGE_REPONSE_INATTENDUE, erreur);
    }
    if (donnees === null || typeof donnees !== 'object') {
      throw new Donnees.ErreurStockage(MESSAGE_REPONSE_INATTENDUE);
    }
    return donnees;
  }

  async function lireOctets(reponse) {
    try {
      return new Uint8Array(await reponse.arrayBuffer());
    } catch (erreur) {
      throw erreurReseau(erreur);
    }
  }

  // « copie_externe » de /api/info (lot 7, D133, §22.11) → { derniereReussie, joursSansCopie, erreur }, ou null quand
  // le PC serveur n'a aucun dossier de copie externe.
  function copieExterneLue(copie) {
    if (!copie || typeof copie !== 'object') return null;
    return {
      derniereReussie: typeof copie.derniere_reussie === 'string' ? copie.derniere_reussie : null,
      joursSansCopie: typeof copie.jours_sans_copie === 'number' ? copie.jours_sans_copie : null,
      erreur: typeof copie.erreur === 'string' && copie.erreur ? copie.erreur : null,
    };
  }

  // ===========================================================================
  // Fabrique de l'adaptateur
  // ===========================================================================

  // base : préfixe des adresses (« » = même origine que la page, cas normal).
  function creer(base = '') {
    const entetesEcriture = { 'X-Prevo': '1' };

    function urlTable(table) {
      return base + '/api/csv/' + encodeURIComponent(table);
    }

    function urlDocument(nom) {
      return base + '/api/documents/' + encodeURIComponent(nom);
    }

    async function charger(table) {
      const reponse = await appeler(urlTable(table), { method: 'GET' });
      // 404 = fichier absent, mais seulement pour une table du schéma (sinon : table inconnue).
      if (reponse.status === 404 && Schema.nomsTables().indexOf(table) !== -1) {
        return { octets: null, version: null };
      }
      if (reponse.status >= 400) { throw await erreurDepuisReponse(reponse); }
      return { octets: await lireOctets(reponse), version: reponse.headers.get('X-Version') };
    }

    // versionAttendue : version lue au chargement, ou null si le fichier ne doit pas exister.
    async function enregistrer(table, octets, versionAttendue) {
      const reponse = await appelerOuErreur(urlTable(table), {
        method: 'PUT',
        headers: Object.assign({
          'Content-Type': 'text/csv; charset=utf-8',
          'X-Version-Attendue': versionAttendue === null || versionAttendue === undefined
            ? 'aucune' : versionAttendue,
        }, entetesEcriture),
        body: octets,
      });
      const donnees = await lireJson(reponse);
      return { version: donnees.version };
    }

    async function ajouter(table, octets) {
      const reponse = await appelerOuErreur(urlTable(table) + '/ajout', {
        method: 'POST',
        headers: Object.assign({ 'Content-Type': 'text/csv; charset=utf-8' }, entetesEcriture),
        body: octets,
      });
      const donnees = await lireJson(reponse);
      return { version: donnees.version };
    }

    // → { nomTable: version | null, … }
    async function listerVersions() {
      const reponse = await appelerOuErreur(base + '/api/versions', { method: 'GET' });
      const donnees = await lireJson(reponse);
      if (!donnees.tables || typeof donnees.tables !== 'object' || Array.isArray(donnees.tables)) {
        throw new Donnees.ErreurStockage(MESSAGE_REPONSE_INATTENDUE);
      }
      const versions = {};
      Object.keys(donnees.tables).forEach(function (table) {
        const detail = donnees.tables[table];
        versions[table] = detail ? detail.version : null;
      });
      return versions;
    }

    // Refuse d'écraser un document : le serveur répond 409 s'il existe déjà.
    async function ecrireDocument(nom, blob) {
      const reponse = await appeler(urlDocument(nom), {
        method: 'PUT',
        headers: Object.assign({ 'Content-Type': blob.type || 'application/octet-stream' }, entetesEcriture),
        body: blob,
      });
      if (reponse.status === 409) {
        throw new Donnees.ErreurStockage('Un document porte déjà ce nom.');
      }
      if (reponse.status >= 400) { throw await erreurDepuisReponse(reponse); }
      const donnees = await lireJson(reponse);
      return donnees.nom;
    }

    async function lireDocument(nom) {
      const reponse = await appeler(urlDocument(nom), { method: 'GET' });
      if (reponse.status === 404) { return null; }
      if (reponse.status >= 400) { throw await erreurDepuisReponse(reponse); }
      try {
        return await reponse.blob();
      } catch (erreur) {
        throw erreurReseau(erreur);
      }
    }

    // Le serveur sert le document : l'adresse suffit pour un <img src> ou un lien.
    async function adresseDocument(nom) {
      return urlDocument(nom);
    }

    // motif (facultatif) : mot de la liste fermée du serveur (ex. 'avant-format-v2'), ajouté à la fin
    // du nom (« AAAA-MM-JJ_HHMMSS_avant-format-v2 ») ; motif refusé → ErreurStockage (400).
    // Sans motif : corps vide, sauvegarde manuelle « AAAA-MM-JJ_HHMMSS » comme avant.
    async function sauvegarder(motif) {
      const avecMotif = motif !== undefined && motif !== null && motif !== '';
      const reponse = await appelerOuErreur(base + '/api/sauvegarde', {
        method: 'POST',
        headers: avecMotif
          ? Object.assign({ 'Content-Type': 'application/json; charset=utf-8' }, entetesEcriture)
          : entetesEcriture,
        body: avecMotif ? JSON.stringify({ motif: motif }) : '',
      });
      const donnees = await lireJson(reponse);
      return donnees.sauvegarde;
    }

    // → [{ nom, tables: [...] }], plus récente d'abord (ordre donné par le serveur)
    async function listerSauvegardes() {
      const reponse = await appelerOuErreur(base + '/api/sauvegardes', { method: 'GET' });
      const donnees = await lireJson(reponse);
      return donnees.sauvegardes;
    }

    // tables : liste facultative ; sans elle, toutes les tables de la sauvegarde sont restaurées.
    async function restaurer(nom, tables) {
      const demande = { sauvegarde: nom };
      if (tables) { demande.tables = tables; }
      const reponse = await appelerOuErreur(base + '/api/restauration', {
        method: 'POST',
        headers: Object.assign({ 'Content-Type': 'application/json; charset=utf-8' }, entetesEcriture),
        body: JSON.stringify(demande),
      });
      const donnees = await lireJson(reponse);
      return { restaurees: donnees.restaurees, copieSecurite: donnees.copie_securite };
    }

    // « Tester une sauvegarde » (lot 7, D133) : le serveur relit chaque CSV de la sauvegarde et compte ses lignes,
    // sans rien écrire → { nom, ok, tables: [{ table, lignes, erreur }] } ; nom refusé ou sauvegarde absente →
    // ErreurStockage. Propre au mode serveur (les autres adaptateurs n'ont pas cette méthode).
    async function testerSauvegarde(nom) {
      const reponse = await appelerOuErreur(base + '/api/sauvegarde/tester', {
        method: 'POST',
        headers: Object.assign({ 'Content-Type': 'application/json; charset=utf-8' }, entetesEcriture),
        body: JSON.stringify({ nom: nom }),
      });
      return lireJson(reponse);
    }

    async function info() {
      const reponse = await appelerOuErreur(base + '/api/info', { method: 'GET' });
      const donnees = await lireJson(reponse);
      return { adressesReseau: donnees.adresses_reseau || [], port: donnees.port,
        copieExterne: copieExterneLue(donnees.copie_externe) };
    }

    return {
      mode: 'serveur',
      libelle: 'Serveur ' + location.host,
      charger: charger,
      enregistrer: enregistrer,
      ajouter: ajouter,
      listerVersions: listerVersions,
      ecrireDocument: ecrireDocument,
      lireDocument: lireDocument,
      urlDocument: adresseDocument,
      sauvegarder: sauvegarder,
      listerSauvegardes: listerSauvegardes,
      restaurer: restaurer,
      testerSauvegarde: testerSauvegarde,
      info: info,
    };
  }

  return {
    detecter: detecter,
    creer: creer,
  };
})();
