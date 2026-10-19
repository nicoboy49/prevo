'use strict';
// StockageDossier : adaptateur de stockage « dossier » (API File System Access du navigateur).
// Contrat : docs/ARCHITECTURE.md §6 (contrat commun et paragraphe « Dossier ») et §7 (règles de
// noms de documents et de sauvegardes, identiques à celles de serveur.py).
//
// L'utilisateur choisit un dossier de son PC (ou d'un partage réseau) ; les 22 fichiers CSV y sont
// lus et écrits directement par le navigateur. Ce fichier contient, dans l'ordre :
//   1. les utilitaires (dates, empreintes, lecture et écriture de fichiers, erreurs) ;
//   2. la mémorisation du dossier choisi (IndexedDB) ;
//   3. la fabrique `creer(poignee, { poste })` qui rend l'adaptateur.
// Le mode dossier tourne toujours en contexte sécurisé (file:// ou http://127.0.0.1) : on peut
// donc utiliser crypto.subtle. Dépendances : Schema (js/schema.js) et Donnees (js/donnees.js)
// pour les erreurs ; elles ne sont lues qu'au moment des appels, pas au chargement du fichier.

const StockageDossier = (() => {

  // ===========================================================================
  // 1. Utilitaires
  // ===========================================================================

  const BOM_UTF8 = [0xEF, 0xBB, 0xBF];
  const FIN_DE_LIGNE = [0x0D, 0x0A];
  const OCTET_SAUT_DE_LIGNE = 0x0A;
  const OCTETS_BLANCS = [0x20, 0x09, 0x0D, 0x0A];            // espace, tabulation, CR, LF

  const NOM_DOSSIER_DOCUMENTS = 'documents';
  const NOM_DOSSIER_SAUVEGARDES = 'sauvegardes';
  const NOM_FICHIER_VERROU = 'verrou.txt';
  const SUFFIXE_AVANT_RESTAURATION = '_avant-restauration';

  // Un verrou plus ancien que 3 minutes est considéré comme abandonné ; on le réécrit toutes les 60 s.
  const DUREE_VALIDITE_VERROU_MS = 3 * 60 * 1000;
  const PERIODE_VERROU_MS = 60 * 1000;

  // Mêmes règles que serveur.py (MOTIF_NOM_DOCUMENT, TYPES_DOCUMENTS, NOMS_RESERVES_WINDOWS…).
  const MOTIF_NOM_DOCUMENT = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
  const MOTIF_NOM_SAUVEGARDE = /^\d{4}-\d{2}-\d{2}(_\d{6}(_avant-restauration)?)?$/;
  const EXTENSIONS_DOCUMENTS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'pdf', 'txt', 'csv', 'doc', 'docx',
    'xls', 'xlsx', 'odt', 'ods'];
  const NOMS_RESERVES_WINDOWS = ['con', 'prn', 'aux', 'nul']
    .concat([1, 2, 3, 4, 5, 6, 7, 8, 9].map(function (n) { return 'com' + n; }))
    .concat([1, 2, 3, 4, 5, 6, 7, 8, 9].map(function (n) { return 'lpt' + n; }));

  // Mémorisation de la poignée du dossier (ARCHITECTURE.md §6).
  const BASE_POIGNEES = 'prevo';
  const MAGASIN_POIGNEES = 'poignees';
  const CLE_POIGNEE_DOSSIER = 'dossier';

  const decodeurUtf8Strict = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true });
  const encodeurUtf8 = new TextEncoder();

  function deuxChiffres(nombre) {
    return (nombre < 10 ? '0' : '') + nombre;
  }

  // 'AAAA-MM-JJ' (heure locale).
  function dateDuJour(maintenant) {
    const date = maintenant || new Date();
    return date.getFullYear() + '-' + deuxChiffres(date.getMonth() + 1) + '-' + deuxChiffres(date.getDate());
  }

  // 'HHMMSS' (heure locale), pour les noms de sauvegarde.
  function heureCompacte(date) {
    return deuxChiffres(date.getHours()) + deuxChiffres(date.getMinutes()) + deuxChiffres(date.getSeconds());
  }

  // 'AAAA-MM-JJ HH:MM:SS' (heure locale), pour verrou.txt.
  function dateHeureVerrou(date) {
    return dateDuJour(date) + ' ' + deuxChiffres(date.getHours()) + ':' + deuxChiffres(date.getMinutes())
      + ':' + deuxChiffres(date.getSeconds());
  }

  // 'AAAA-MM-JJ HH:MM:SS' → Date, ou null si le texte n'a pas ce format.
  function lireDateHeureVerrou(texte) {
    const trouve = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})$/.exec(texte);
    if (!trouve) { return null; }
    return new Date(Number(trouve[1]), Number(trouve[2]) - 1, Number(trouve[3]),
      Number(trouve[4]), Number(trouve[5]), Number(trouve[6]));
  }

  function attendre(millisecondes) {
    return new Promise(function (resolu) { setTimeout(resolu, millisecondes); });
  }

  // Uint8Array, ArrayBuffer ou autre vue typée → Uint8Array.
  function enOctets(contenu) {
    if (contenu instanceof Uint8Array) { return contenu; }
    if (contenu instanceof ArrayBuffer) { return new Uint8Array(contenu); }
    if (ArrayBuffer.isView(contenu)) {
      return new Uint8Array(contenu.buffer, contenu.byteOffset, contenu.byteLength);
    }
    throw new TypeError('StockageDossier : octets attendus (Uint8Array ou ArrayBuffer).');
  }

  function concatener(morceaux) {
    let longueurTotale = 0;
    morceaux.forEach(function (morceau) { longueurTotale += morceau.length; });
    const resultat = new Uint8Array(longueurTotale);
    let position = 0;
    morceaux.forEach(function (morceau) {
      resultat.set(morceau, position);
      position += morceau.length;
    });
    return resultat;
  }

  function commencePar(octets, debut) {
    if (octets.length < debut.length) { return false; }
    for (let i = 0; i < debut.length; i++) {
      if (octets[i] !== debut[i]) { return false; }
    }
    return true;
  }

  function octetsEgaux(a, b) {
    if (a.length !== b.length) { return false; }
    for (let i = 0; i < a.length; i++) {
      if (a[i] !== b[i]) { return false; }
    }
    return true;
  }

  function sansBom(octets) {
    return commencePar(octets, BOM_UTF8) ? octets.subarray(BOM_UTF8.length) : octets;
  }

  // Vrai si le contenu est de l'UTF-8 valide.
  function estUtf8(octets) {
    try {
      decodeurUtf8Strict.decode(octets);
      return true;
    } catch (erreurDecodage) {
      return false;
    }
  }

  // Vrai si le fichier ne contient rien d'autre que le BOM et des blancs.
  function estVide(octets) {
    return sansBom(octets).every(function (octet) { return OCTETS_BLANCS.indexOf(octet) !== -1; });
  }

  // Première ligne (sans BOM ni fin de ligne) et reste du contenu (comme premiere_ligne de serveur.py).
  function decouperPremiereLigne(octets) {
    const contenu = sansBom(octets);
    const position = contenu.indexOf(OCTET_SAUT_DE_LIGNE);
    let entete = position === -1 ? contenu : contenu.subarray(0, position);
    const reste = position === -1 ? new Uint8Array(0) : contenu.subarray(position + 1);
    if (entete.length > 0 && entete[entete.length - 1] === 0x0D) {
      entete = entete.subarray(0, entete.length - 1);
    }
    return { entete: entete, reste: reste };
  }

  // Version d'un fichier = SHA-256 du contenu, 16 premiers caractères hexadécimaux (décision D7,
  // identique à serveur.py).
  async function empreinte(octets) {
    const condense = new Uint8Array(await crypto.subtle.digest('SHA-256', octets));
    let texte = '';
    for (let i = 0; i < 8; i++) {
      texte += (condense[i] < 16 ? '0' : '') + condense[i].toString(16);
    }
    return texte;
  }

  // --- Erreurs -----------------------------------------------------------------------------

  function erreurStockage(message, cause) {
    return new Donnees.ErreurStockage(message, cause);
  }

  // Les erreurs de Prévo passent telles quelles ; les erreurs du navigateur sont traduites
  // en ErreurStockage avec un message en français (la cause d'origine est conservée).
  function traduireErreur(erreur, action) {
    if (erreur instanceof Donnees.ErreurConflit || erreur instanceof Donnees.ErreurStockage) {
      return erreur;
    }
    const nom = erreur && erreur.name;
    if (nom === 'NoModificationAllowedError' || nom === 'InvalidStateError') {
      return erreurStockage('Impossible d\'écrire dans le dossier de données (' + action
        + ') : un fichier est sans doute ouvert dans Excel. Fermez-le puis réessayez.', erreur);
    }
    if (nom === 'NotAllowedError' || nom === 'SecurityError') {
      return erreurStockage('Accès refusé au dossier de données (' + action
        + '). Rechoisissez le dossier pour redonner l\'autorisation.', erreur);
    }
    if (nom === 'NotFoundError') {
      return erreurStockage('Dossier de données introuvable (' + action
        + ') : a-t-il été déplacé, renommé ou débranché ?', erreur);
    }
    return erreurStockage('Lecture ou écriture impossible dans le dossier de données (' + action + ').', erreur);
  }

  // --- Dossiers et fichiers ----------------------------------------------------------------

  // Poignée du fichier, ou null s'il n'existe pas (un dossier du même nom compte comme absent).
  async function trouverFichier(dossier, nom) {
    try {
      return await dossier.getFileHandle(nom);
    } catch (erreur) {
      if (erreur && (erreur.name === 'NotFoundError' || erreur.name === 'TypeMismatchError')) { return null; }
      throw erreur;
    }
  }

  // Poignée du sous-dossier, ou null s'il n'existe pas et qu'on ne demande pas de le créer.
  async function trouverDossier(dossier, nom, creer) {
    try {
      return await dossier.getDirectoryHandle(nom, { create: Boolean(creer) });
    } catch (erreur) {
      if (!creer && erreur && (erreur.name === 'NotFoundError' || erreur.name === 'TypeMismatchError')) {
        return null;
      }
      throw erreur;
    }
  }

  // Contenu d'un fichier (Uint8Array), ou null s'il n'existe pas.
  async function lireOctets(dossier, nom) {
    const poigneeFichier = await trouverFichier(dossier, nom);
    if (!poigneeFichier) { return null; }
    const fichier = await poigneeFichier.getFile();
    return new Uint8Array(await fichier.arrayBuffer());
  }

  // Écrit (ou remplace) un fichier : createWritable → write → close. Chrome écrit dans un fichier
  // temporaire et ne remplace l'original qu'à la fermeture : un échec ne laisse pas de fichier
  // à moitié écrit. Si le fichier venait d'être créé et que l'écriture échoue, on le supprime.
  async function ecrireFichier(dossier, nom, contenu) {
    const existait = (await trouverFichier(dossier, nom)) !== null;
    const poigneeFichier = await dossier.getFileHandle(nom, { create: true });
    let flux = null;
    try {
      flux = await poigneeFichier.createWritable();
      await flux.write(contenu);
      await flux.close();
    } catch (erreur) {
      if (flux) { try { await flux.abort(); } catch (erreurAbandon) { /* déjà fermé */ } }
      if (!existait) { try { await dossier.removeEntry(nom); } catch (erreurSuppression) { /* rien à nettoyer */ } }
      throw erreur;
    }
  }

  // Ajoute des octets à la fin d'un fichier existant (les octets déjà écrits sont conservés).
  async function ajouterEnFin(dossier, nom, octets, tailleActuelle) {
    const poigneeFichier = await dossier.getFileHandle(nom);
    const flux = await poigneeFichier.createWritable({ keepExistingData: true });
    try {
      await flux.seek(tailleActuelle);
      await flux.write(octets);
      await flux.close();
    } catch (erreur) {
      try { await flux.abort(); } catch (erreurAbandon) { /* déjà fermé */ }
      throw erreur;
    }
  }

  // Tables (dans l'ordre du schéma) dont le CSV existe dans « dossier ».
  async function tablesPresentes(dossier) {
    const noms = new Set();
    for await (const entree of dossier.values()) {
      if (entree.kind === 'file' && entree.name.endsWith('.csv')) {
        noms.add(entree.name.slice(0, -'.csv'.length));
      }
    }
    return Schema.nomsTables().filter(function (table) { return noms.has(table); });
  }

  // Copie les CSV des tables données de « source » vers « cible » (sans changer leur contenu).
  async function copierTables(source, cible, tables) {
    for (const table of tables) {
      const poigneeFichier = await source.getFileHandle(table + '.csv');
      await ecrireFichier(cible, table + '.csv', await poigneeFichier.getFile());
    }
  }

  function verifierNomTable(table) {
    if (Schema.nomsTables().indexOf(table) === -1) {
      throw erreurStockage('Table inconnue : ' + table + '.');
    }
  }

  function verifierNomDocument(nom) {
    if (typeof nom !== 'string' || !MOTIF_NOM_DOCUMENT.test(nom) || nom.indexOf('..') !== -1) {
      throw erreurStockage('Nom de document refusé : lettres, chiffres, « . », « _ » ou « - ».');
    }
    const extension = nom.indexOf('.') === -1 ? '' : nom.slice(nom.lastIndexOf('.') + 1).toLowerCase();
    if (EXTENSIONS_DOCUMENTS.indexOf(extension) === -1) {
      throw erreurStockage('Type de document refusé. Types acceptés : ' + EXTENSIONS_DOCUMENTS.join(', ') + '.');
    }
    if (NOMS_RESERVES_WINDOWS.indexOf(nom.split('.')[0].toLowerCase()) !== -1) {
      throw erreurStockage('Nom de document réservé par Windows.');
    }
  }

  function verifierNomSauvegarde(nom) {
    if (typeof nom !== 'string' || !MOTIF_NOM_SAUVEGARDE.test(nom)) {
      throw erreurStockage('Nom de sauvegarde invalide.');
    }
  }

  // ===========================================================================
  // 2. Mémorisation du dossier choisi (IndexedDB)
  // ===========================================================================
  // Les poignées de dossier sont « clonables » : IndexedDB sait les stocker telles quelles.

  function ouvrirBasePoignees() {
    return new Promise(function (resolu, rejete) {
      const demande = indexedDB.open(BASE_POIGNEES, 1);
      demande.onupgradeneeded = function () {
        if (!demande.result.objectStoreNames.contains(MAGASIN_POIGNEES)) {
          demande.result.createObjectStore(MAGASIN_POIGNEES);
        }
      };
      demande.onsuccess = function () { resolu(demande.result); };
      demande.onerror = function () { rejete(demande.error); };
    });
  }

  // Exécute une opération sur le magasin des poignées ; renvoie son résultat.
  async function surMagasinPoignees(mode, operation) {
    const base = await ouvrirBasePoignees();
    try {
      return await new Promise(function (resolu, rejete) {
        const transaction = base.transaction(MAGASIN_POIGNEES, mode);
        const demande = operation(transaction.objectStore(MAGASIN_POIGNEES));
        transaction.oncomplete = function () { resolu(demande.result); };
        transaction.onerror = function () { rejete(transaction.error); };
        transaction.onabort = function () { rejete(transaction.error); };
      });
    } finally {
      base.close();
    }
  }

  // Poignée mémorisée, ou null (IndexedDB indisponible ou vide : ce n'est pas une erreur).
  async function lirePoigneeMemorisee() {
    try {
      const poignee = await surMagasinPoignees('readonly', function (magasin) {
        return magasin.get(CLE_POIGNEE_DOSSIER);
      });
      return poignee || null;
    } catch (erreur) {
      return null;
    }
  }

  async function memoriserPoignee(poignee) {
    try {
      await surMagasinPoignees('readwrite', function (magasin) {
        return magasin.put(poignee, CLE_POIGNEE_DOSSIER);
      });
    } catch (erreur) {
      // Mémoriser est un confort (« Reprendre le dossier précédent ») : on ne bloque pas pour ça.
    }
  }

  // Le navigateur sait-il choisir un dossier ? (Chrome, Edge ; pas Firefox ni Safari.)
  function disponible() {
    return 'showDirectoryPicker' in window;
  }

  // Ouvre le sélecteur de dossier du navigateur (à appeler depuis un clic).
  // Renvoie la poignée du dossier choisi, ou null si l'utilisateur annule.
  async function choisir() {
    let poignee;
    try {
      poignee = await window.showDirectoryPicker({ mode: 'readwrite', id: 'prevo-donnees' });
    } catch (erreur) {
      if (erreur && erreur.name === 'AbortError') { return null; }
      throw traduireErreur(erreur, 'choix du dossier');
    }
    await memoriserPoignee(poignee);
    return poignee;
  }

  // Dossier mémorisé lors d'un choix précédent : { nom } ou null. Ne demande aucune autorisation.
  async function poigneeMemorisee() {
    const poignee = await lirePoigneeMemorisee();
    return poignee ? { nom: poignee.name } : null;
  }

  // « Reprendre le dossier précédent » (à appeler depuis un clic : la demande d'autorisation du
  // navigateur l'exige). Renvoie la poignée si l'accès en lecture et écriture est accordé, sinon null.
  async function reprendre() {
    const poignee = await lirePoigneeMemorisee();
    if (!poignee) { return null; }
    try {
      const reglage = { mode: 'readwrite' };
      let etat = 'granted';
      if (typeof poignee.queryPermission === 'function') {
        etat = await poignee.queryPermission(reglage);
      }
      if (etat !== 'granted' && typeof poignee.requestPermission === 'function') {
        etat = await poignee.requestPermission(reglage);
      }
      return etat === 'granted' ? poignee : null;
    } catch (erreur) {
      return null;
    }
  }

  // ===========================================================================
  // 3. L'adaptateur
  // ===========================================================================

  // poignee : FileSystemDirectoryHandle du dossier de données (rendu par choisir() ou reprendre()).
  // options.poste : nom du poste, écrit dans verrou.txt.
  async function creer(poignee, options) {
    const racine = poignee;
    const poste = String((options && options.poste) || 'Poste inconnu').replace(/[;\r\n]+/g, ' ').trim()
      || 'Poste inconnu';
    const idSession = Math.random().toString(36).slice(2, 12) + Math.random().toString(36).slice(2, 12);
    const urlsDocuments = new Map();            // nom → URL d'objet déjà fabriquée
    let minuteurVerrou = null;

    // Les écritures sont exécutées une par une : la sauvegarde quotidienne (« première écriture
    // du jour ») ne peut pas être prise par deux écritures à la fois, ni après l'une d'elles.
    let filEcritures = Promise.resolve();
    function enSerie(tache) {
      const resultat = filEcritures.then(tache);
      filEcritures = resultat.catch(function () { /* l'erreur est rendue à l'appelant */ });
      return resultat;
    }

    // Toute erreur du navigateur devient une ErreurStockage lisible.
    function proteger(action, fonction) {
      return async function () {
        try {
          return await fonction.apply(null, arguments);
        } catch (erreur) {
          throw traduireErreur(erreur, action);
        }
      };
    }

    // --- Lecture ---------------------------------------------------------------------------

    async function charger(table) {
      verifierNomTable(table);
      const octets = await lireOctets(racine, table + '.csv');
      return { octets: octets, version: octets === null ? null : await empreinte(octets) };
    }

    async function listerVersions() {
      const noms = Schema.nomsTables();
      const versions = await Promise.all(noms.map(async function (table) {
        const octets = await lireOctets(racine, table + '.csv');
        return octets === null ? null : empreinte(octets);
      }));
      const resultat = {};
      noms.forEach(function (table, i) { resultat[table] = versions[i]; });
      return resultat;
    }

    // --- Sauvegardes -----------------------------------------------------------------------

    // Crée sauvegardes/<nom>/ avec une copie des tables données. Si la copie échoue, le dossier
    // à moitié rempli est supprimé : une sauvegarde est complète ou n'existe pas.
    async function creerSauvegarde(nom, tables) {
      const dossierSauvegardes = await trouverDossier(racine, NOM_DOSSIER_SAUVEGARDES, true);
      const dossierSauvegarde = await trouverDossier(dossierSauvegardes, nom, true);
      try {
        await copierTables(racine, dossierSauvegarde, tables);
      } catch (erreur) {
        try { await dossierSauvegardes.removeEntry(nom, { recursive: true }); } catch (erreurNettoyage) { /* tant pis */ }
        throw erreur;
      }
    }

    // « AAAA-MM-JJ_HHMMSS » + suffixe, en attendant la seconde suivante si ce nom est déjà pris.
    async function nouveauNomHorodate(suffixe) {
      const dossierSauvegardes = await trouverDossier(racine, NOM_DOSSIER_SAUVEGARDES, true);
      for (;;) {
        const maintenant = new Date();
        const nom = dateDuJour(maintenant) + '_' + heureCompacte(maintenant) + suffixe;
        if (!(await trouverDossier(dossierSauvegardes, nom, false))) { return nom; }
        await attendre(200);
      }
    }

    // Avant la première écriture du jour : copie de tous les CSV dans sauvegardes/AAAA-MM-JJ/
    // (rien si elle existe déjà ou s'il n'y a encore aucun CSV). À appeler dans enSerie.
    async function sauvegardeQuotidienneSiBesoin() {
      const nom = dateDuJour();
      const dossierSauvegardes = await trouverDossier(racine, NOM_DOSSIER_SAUVEGARDES, false);
      if (dossierSauvegardes && await trouverDossier(dossierSauvegardes, nom, false)) { return; }
      const tables = await tablesPresentes(racine);
      if (tables.length === 0) { return; }
      await creerSauvegarde(nom, tables);
    }

    async function sauvegarder() {
      return enSerie(async function () {
        const nom = await nouveauNomHorodate('');
        await creerSauvegarde(nom, await tablesPresentes(racine));
        return nom;
      });
    }

    async function listerSauvegardes() {
      const dossierSauvegardes = await trouverDossier(racine, NOM_DOSSIER_SAUVEGARDES, false);
      if (!dossierSauvegardes) { return []; }
      const noms = [];
      for await (const entree of dossierSauvegardes.values()) {
        if (entree.kind === 'directory' && MOTIF_NOM_SAUVEGARDE.test(entree.name)) { noms.push(entree.name); }
      }
      noms.sort().reverse();                              // la plus récente d'abord
      const resultat = [];
      for (const nom of noms) {
        const dossierSauvegarde = await dossierSauvegardes.getDirectoryHandle(nom);
        resultat.push({ nom: nom, tables: await tablesPresentes(dossierSauvegarde) });
      }
      return resultat;
    }

    // Tables à restaurer : toutes celles de la sauvegarde, ou celles demandées (contrôlées).
    function choisirTablesARestaurer(disponibles, tablesDemandees) {
      if (tablesDemandees === undefined || tablesDemandees === null) { return disponibles; }
      if (!Array.isArray(tablesDemandees)) {
        throw erreurStockage('« tables » doit être une liste de noms de tables.');
      }
      tablesDemandees.forEach(function (table) {
        verifierNomTable(table);
        if (disponibles.indexOf(table) === -1) {
          throw erreurStockage('La table ' + table + ' est absente de cette sauvegarde.');
        }
      });
      return Schema.nomsTables().filter(function (table) { return tablesDemandees.indexOf(table) !== -1; });
    }

    // Copie de sécurité de l'état actuel (…_avant-restauration), puis copie des tables voulues.
    async function restaurer(nom, tables) {
      verifierNomSauvegarde(nom);
      return enSerie(async function () {
        const dossierSauvegardes = await trouverDossier(racine, NOM_DOSSIER_SAUVEGARDES, false);
        const dossierSauvegarde = dossierSauvegardes ? await trouverDossier(dossierSauvegardes, nom, false) : null;
        if (!dossierSauvegarde) { throw erreurStockage('Sauvegarde introuvable : ' + nom + '.'); }
        const aRestaurer = choisirTablesARestaurer(await tablesPresentes(dossierSauvegarde), tables);

        const copieSecurite = await nouveauNomHorodate(SUFFIXE_AVANT_RESTAURATION);
        await creerSauvegarde(copieSecurite, await tablesPresentes(racine));

        const restaurees = [];
        for (const table of aRestaurer) {
          try {
            const poigneeFichier = await dossierSauvegarde.getFileHandle(table + '.csv');
            await ecrireFichier(racine, table + '.csv', await poigneeFichier.getFile());
          } catch (erreur) {
            const interrompue = traduireErreur(erreur, 'restauration');
            throw erreurStockage(interrompue.message + ' Restauration interrompue à la table ' + table
              + ' ; tables déjà restaurées : ' + (restaurees.join(', ') || 'aucune')
              + '. L\'état d\'avant la restauration est dans la sauvegarde ' + copieSecurite + '.', erreur);
          }
          restaurees.push(table);
        }
        return { restaurees: restaurees, copieSecurite: copieSecurite };
      });
    }

    // --- Écriture des CSV ------------------------------------------------------------------

    // Remplace le CSV si sa version actuelle est celle attendue (null = le fichier ne doit pas
    // exister) ; sinon ErreurConflit.
    async function enregistrer(table, octets, versionAttendue) {
      verifierNomTable(table);
      const nouveauContenu = enOctets(octets);
      const attendue = versionAttendue === undefined ? null : versionAttendue;
      return enSerie(async function () {
        const actuel = await lireOctets(racine, table + '.csv');
        const versionActuelle = actuel === null ? null : await empreinte(actuel);
        if (attendue !== versionActuelle) {
          let message;
          if (versionActuelle === null) {
            message = 'Le fichier ' + table + '.csv n\'existe plus.';
          } else if (attendue === null) {
            message = 'Le fichier ' + table + '.csv existe déjà.';
          } else {
            message = 'Le fichier ' + table + '.csv a été modifié par un autre poste.';
          }
          throw new Donnees.ErreurConflit(message, versionActuelle);
        }
        await sauvegardeQuotidienneSiBesoin();
        await ecrireFichier(racine, table + '.csv', nouveauContenu);
        return { version: await empreinte(nouveauContenu) };
      });
    }

    // Ajoute des lignes en fin de fichier (journal). `octets` = ligne d'en-tête + lignes (UTF-8
    // sans BOM). Mêmes règles que le serveur : fichier absent ou vide → BOM + corps ; sinon le
    // fichier doit être de l'UTF-8 valide avec le même en-tête, sinon ErreurConflit.
    async function ajouter(table, octets) {
      verifierNomTable(table);
      const corps = sansBom(enOctets(octets));
      if (!estUtf8(corps)) { throw erreurStockage('Le contenu à ajouter doit être encodé en UTF-8.'); }
      const decoupe = decouperPremiereLigne(corps);
      if (decoupe.entete.length === 0) {
        throw erreurStockage('Le contenu à ajouter doit commencer par la ligne d\'en-tête.');
      }
      return enSerie(async function () {
        const actuel = await lireOctets(racine, table + '.csv');

        if (actuel === null || estVide(actuel)) {
          const nouveau = concatener([Uint8Array.from(BOM_UTF8), corps]);
          await sauvegardeQuotidienneSiBesoin();
          await ecrireFichier(racine, table + '.csv', nouveau);
          return { version: await empreinte(nouveau) };
        }

        const versionActuelle = await empreinte(actuel);
        if (!estUtf8(actuel)) {
          throw new Donnees.ErreurConflit('Le fichier ' + table
            + '.csv n\'est pas en UTF-8 (réenregistré par Excel ?).', versionActuelle);
        }
        if (!octetsEgaux(decouperPremiereLigne(actuel).entete, decoupe.entete)) {
          throw new Donnees.ErreurConflit('L\'en-tête de ' + table + '.csv est différent.', versionActuelle);
        }
        if (decoupe.reste.length === 0) { return { version: versionActuelle }; }

        const finissaitParSaut = actuel[actuel.length - 1] === OCTET_SAUT_DE_LIGNE;
        const aAjouter = concatener([Uint8Array.from(finissaitParSaut ? [] : FIN_DE_LIGNE), decoupe.reste]);
        await sauvegardeQuotidienneSiBesoin();
        await ajouterEnFin(racine, table + '.csv', aAjouter, actuel.length);
        return { version: await empreinte(concatener([actuel, aAjouter])) };
      });
    }

    // --- Documents -------------------------------------------------------------------------

    async function ecrireDocument(nom, blob) {
      verifierNomDocument(nom);
      return enSerie(async function () {
        const dossierDocuments = await trouverDossier(racine, NOM_DOSSIER_DOCUMENTS, true);
        if (await trouverFichier(dossierDocuments, nom)) {
          throw erreurStockage('Le document ' + nom + ' existe déjà.');
        }
        await ecrireFichier(dossierDocuments, nom, blob);
        return nom;
      });
    }

    async function lireDocument(nom) {
      verifierNomDocument(nom);
      const dossierDocuments = await trouverDossier(racine, NOM_DOSSIER_DOCUMENTS, false);
      if (!dossierDocuments) { return null; }
      const poigneeFichier = await trouverFichier(dossierDocuments, nom);
      return poigneeFichier ? poigneeFichier.getFile() : null;
    }

    // URL d'objet affichable (valable tant que la page reste ouverte) ; null si le document n'existe pas.
    async function urlDocument(nom) {
      if (urlsDocuments.has(nom)) { return urlsDocuments.get(nom); }
      const blob = await lireDocument(nom);
      if (!blob) { return null; }
      const url = URL.createObjectURL(blob);
      urlsDocuments.set(nom, url);
      return url;
    }

    // --- Verrou (avertissement non bloquant : deux postes sur le même dossier) --------------

    // { autreSession: { poste, heure } } si verrou.txt a moins de 3 minutes et vient d'une autre
    // session ; sinon { autreSession: null }.
    async function verifierVerrou() {
      try {
        const octets = await lireOctets(racine, NOM_FICHIER_VERROU);
        if (octets === null) { return { autreSession: null }; }
        const morceaux = new TextDecoder().decode(octets).trim().split(';');
        if (morceaux.length < 3) { return { autreSession: null }; }
        const idAutreSession = morceaux[morceaux.length - 1].trim();
        const heure = morceaux[morceaux.length - 2].trim();
        const nomPoste = morceaux.slice(0, -2).join(';').trim();
        const dateVerrou = lireDateHeureVerrou(heure);
        if (!dateVerrou || idAutreSession === idSession) { return { autreSession: null }; }
        if (Date.now() - dateVerrou.getTime() >= DUREE_VALIDITE_VERROU_MS) { return { autreSession: null }; }
        return { autreSession: { poste: nomPoste, heure: heure } };
      } catch (erreur) {
        return { autreSession: null };                   // verrou illisible : on ne bloque personne
      }
    }

    async function ecrireVerrou() {
      try {
        const texte = poste + ';' + dateHeureVerrou(new Date()) + ';' + idSession;
        await ecrireFichier(racine, NOM_FICHIER_VERROU, encodeurUtf8.encode(texte));
      } catch (erreur) {
        // Le verrou est un simple avertissement : on ne dérange pas l'utilisateur s'il échoue.
      }
    }

    // Écrit verrou.txt tout de suite, puis le rafraîchit toutes les 60 s.
    async function demarrerVerrou() {
      if (minuteurVerrou === null) {
        minuteurVerrou = setInterval(ecrireVerrou, PERIODE_VERROU_MS);
      }
      await ecrireVerrou();
    }

    // Arrête le rafraîchissement du verrou (le fichier reste ; il expirera au bout de 3 minutes).
    function arreterVerrou() {
      if (minuteurVerrou !== null) {
        clearInterval(minuteurVerrou);
        minuteurVerrou = null;
      }
    }

    return {
      mode: 'dossier',
      libelle: 'Dossier « ' + poignee.name + ' »',
      charger: proteger('lecture de la table', charger),
      enregistrer: proteger('enregistrement de la table', enregistrer),
      ajouter: proteger('ajout au fichier', ajouter),
      listerVersions: proteger('lecture des versions', listerVersions),
      ecrireDocument: proteger('enregistrement du document', ecrireDocument),
      lireDocument: proteger('lecture du document', lireDocument),
      urlDocument: proteger('lecture du document', urlDocument),
      sauvegarder: proteger('sauvegarde', sauvegarder),
      listerSauvegardes: proteger('liste des sauvegardes', listerSauvegardes),
      restaurer: proteger('restauration', restaurer),
      info: async function () { return {}; },
      verifierVerrou: verifierVerrou,
      demarrerVerrou: demarrerVerrou,
      arreterVerrou: arreterVerrou,
    };
  }

  return {
    disponible: disponible,
    choisir: choisir,
    poigneeMemorisee: poigneeMemorisee,
    reprendre: reprendre,
    creer: creer,
  };
})();
