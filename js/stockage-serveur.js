'use strict';
// StockageServeur : adaptateur de stockage « serveur » (le PC qui fait tourner serveur.py).
// Contrat : docs/ARCHITECTURE.md §6 (adaptateurs) et §7 (API du serveur).
// Tout passe par fetch vers /api/… (même origine que la page). Ce fichier n'utilise ni crypto,
// ni presse-papiers : il doit marcher en http://192.168.x.x:8080 depuis un téléphone
// (contexte non sécurisé). Les versions (SHA-256) et les sauvegardes sont calculées par le serveur.
// Dépendance : Donnees (js/donnees.js) pour les erreurs ErreurConflit et ErreurStockage.

const StockageServeur = (() => {

  const DELAI_DETECTION_MS = 2000;
  const NOM_APPLICATION = 'Prévo';
  const MESSAGE_SERVEUR_INJOIGNABLE =
    'Le serveur Prévo ne répond pas. Vérifiez que la fenêtre du serveur est ouverte sur le PC.';

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

  // Envoie la requête et rend la réponse, quel que soit son code (l'appelant décide).
  // Échec réseau (serveur arrêté, câble débranché) → ErreurStockage au message prévu.
  // Toute requête qui écrit (PUT, POST) envoie un corps, même vide, et l'en-tête X-Prevo: 1.
  async function appeler(url, options) {
    try {
      return await fetch(url, Object.assign({ cache: 'no-store' }, options));
    } catch (erreur) {
      throw new Donnees.ErreurStockage(MESSAGE_SERVEUR_INJOIGNABLE, erreur);
    }
  }

  // Comme appeler, mais lève l'erreur correspondante pour tout code ≥ 400.
  async function appelerOuErreur(url, options) {
    const reponse = await appeler(url, options);
    if (reponse.status >= 400) { throw await erreurDepuisReponse(reponse); }
    return reponse;
  }

  // Lit le JSON d'une réponse réussie ; un échec de lecture en route = serveur injoignable.
  async function lireJson(reponse) {
    try {
      return await reponse.json();
    } catch (erreur) {
      throw new Donnees.ErreurStockage(MESSAGE_SERVEUR_INJOIGNABLE, erreur);
    }
  }

  async function lireOctets(reponse) {
    try {
      return new Uint8Array(await reponse.arrayBuffer());
    } catch (erreur) {
      throw new Donnees.ErreurStockage(MESSAGE_SERVEUR_INJOIGNABLE, erreur);
    }
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
      if (reponse.status === 404) { return { octets: null, version: null }; }
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
        throw new Donnees.ErreurStockage(MESSAGE_SERVEUR_INJOIGNABLE, erreur);
      }
    }

    // Le serveur sert le document : l'adresse suffit pour un <img src> ou un lien.
    async function adresseDocument(nom) {
      return urlDocument(nom);
    }

    async function sauvegarder() {
      const reponse = await appelerOuErreur(base + '/api/sauvegarde', {
        method: 'POST',
        headers: entetesEcriture,
        body: '',
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

    async function info() {
      const reponse = await appelerOuErreur(base + '/api/info', { method: 'GET' });
      const donnees = await lireJson(reponse);
      return { adressesReseau: donnees.adresses_reseau || [], port: donnees.port };
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
      info: info,
    };
  }

  return {
    detecter: detecter,
    creer: creer,
  };
})();
