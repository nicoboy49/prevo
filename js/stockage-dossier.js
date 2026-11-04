'use strict';
// StockageDossier : adaptateur de stockage « dossier » (API File System Access du navigateur).
// Contrat : docs/ARCHITECTURE.md §6 (contrat commun et paragraphe « Dossier ») et §7 (règles de
// noms de documents et de sauvegardes, identiques à celles de serveur.py).
//
// L'utilisateur choisit un dossier de son PC (ou d'un partage réseau) ; les 23 fichiers CSV y sont
// lus et écrits directement par le navigateur. Ce fichier contient, dans l'ordre :
//   1. les utilitaires (dates, empreintes, lecture et écriture de fichiers, erreurs) ;
//   2. la mémorisation du dossier choisi (IndexedDB) ;
//   3. la fabrique `creer(poignee, { poste })` qui rend l'adaptateur.
// Le mode dossier tourne toujours en contexte sécurisé (file:// ou http://127.0.0.1) : on peut
// donc utiliser crypto.subtle. Dépendances : Schema (js/schema.js), Donnees (js/donnees.js) pour
// les erreurs, Formats (js/formats.js) pour le manifeste des sauvegardes, App (version de l'appli,
// facultatif) ; elles ne sont lues qu'au moment des appels, pas au chargement du fichier.

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
  // Marqueur posé dans une sauvegarde pendant sa copie, retiré à la fin : une sauvegarde qui le
  // contient encore est incomplète (onglet fermé pendant la copie). Un marqueur plutôt qu'un
  // témoin « complet » : les sauvegardes faites par serveur.py (dossier renommé à la fin, donc
  // toujours complètes) n'ont aucun fichier en plus et restent reconnues comme complètes.
  const NOM_MARQUEUR_EN_COURS = '.en-cours';
  // Marqueur plus récent que 2 minutes : la copie est sans doute en cours sur un autre poste
  // (il est réécrit avant chaque table copiée).
  const DUREE_SAUVEGARDE_EN_COURS_MS = 2 * 60 * 1000;
  // Sauvegardes du mode dossier (D170, docs/FORMAT.md §8 et §9 ; mêmes règles que serveur.py) :
  //   - rotation, après chaque nouvelle quotidienne et chaque nouvelle manuelle : quotidiennes « AAAA-MM-JJ » de
  //     plus de 30 jours (date du jour du poste) et manuelles « AAAA-MM-JJ_HHMMSS » au-delà des 60 plus récentes
  //     supprimées ; « …_avant-… » jamais ; un nom hors de ces motifs n'est jamais touché ; T206 : les 7
  //     quotidiennes les plus récentes sans fichier abîmé sont toujours gardées, quel que soit leur âge ;
  //   - manifeste.json dans chaque sauvegarde (Formats.manifeste des fichiers copiés), écrit avant le retrait du
  //     marqueur « .en-cours » ; la restauration ne copie que les CSV des tables, donc l'ignore ; T206 : un CSV
  //     abîmé (Donnees.csv.analyser, `abime`) y porte « abime »: true. Un fichier abîmé bloque l'écriture dans la
  //     table, jamais la sauvegarde quotidienne (faite avant la garde de enregistrer et ajouter) ;
  //   - fichiers-abimes.json (racine, T206) : { "depuis": { "<table>": "AAAA-MM-JJTHH:MM:SS" } }, date à laquelle
  //     Prévo a vu la table abîmée la première fois, mis à jour à chaque sauvegarde et à l'ouverture
  //     (noterFichiersAbimes, depuis js/app.js) ; jamais copié dans une sauvegarde ni remplacé par une restauration ;
  //   - « avant-import-zip » copie aussi documents/ (dans documents/ de la sauvegarde, compté dans le manifeste) ;
  //   - « avant-mise-a-jour » : au premier démarrage d'une nouvelle version de l'appli sur ce dossier, puis
  //     derniere-version.json (racine du dossier de données) : { "version", "depuis" }.
  const MOTIF_NOM_QUOTIDIENNE = /^(\d{4})-(\d{2})-(\d{2})$/;
  const MOTIF_NOM_MANUELLE = /^\d{4}-\d{2}-\d{2}_\d{6}$/;
  const JOURS_GARDES_QUOTIDIENNES = 30;
  const MANUELLES_GARDEES = 60;
  const MS_PAR_JOUR = 24 * 60 * 60 * 1000;
  const NOM_MANIFESTE = 'manifeste.json';
  const NOM_DERNIERE_VERSION = 'derniere-version.json';
  const NOM_FICHIERS_ABIMES = 'fichiers-abimes.json';
  // T206 : quotidiennes sans fichier abîmé gardées à la rotation quel que soit leur âge (les plus récentes).
  const QUOTIDIENNES_SAINES_GARDEES = 7;
  const MOTIF_DATE_MANIFESTE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/;
  const MOTIF_AVANT_IMPORT_ZIP = 'avant-import-zip';
  const MOTIF_AVANT_MISE_A_JOUR = 'avant-mise-a-jour';
  // Motif écrit dans le manifeste d'une sauvegarde sans motif de MOTIFS_SAUVEGARDE.
  const MOTIF_QUOTIDIENNE = 'quotidienne';
  const MOTIF_MANUELLE = 'manuelle';
  const MOTIF_AVANT_RESTAURATION = 'avant-restauration';

  // Un verrou plus ancien que 3 minutes est considéré comme abandonné ; on le réécrit toutes les 60 s.
  const DUREE_VALIDITE_VERROU_MS = 3 * 60 * 1000;
  const PERIODE_VERROU_MS = 60 * 1000;

  // Mêmes règles que serveur.py (MOTIF_NOM_DOCUMENT, TYPES_DOCUMENTS, NOMS_RESERVES_WINDOWS…).
  const MOTIF_NOM_DOCUMENT = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
  // Nom de sauvegarde : AAAA-MM-JJ (quotidienne), AAAA-MM-JJ_HHMMSS (manuelle), suivi au besoin de
  // « _avant-restauration » (copie de sécurité), « _avant-format-v<N> » (juste avant le passage
  // au format N) ou « _avant-import » (juste avant un import, lot 5). En JavaScript, \d ne reconnaît
  // que 0-9, comme [0-9] côté serveur.
  const MOTIF_NOM_SAUVEGARDE = /^\d{4}-\d{2}-\d{2}(_\d{6}(_avant-restauration|_avant-format-v\d+|_avant-import-zip|_avant-import|_avant-mise-a-jour)?)?$/;
  // Motifs acceptés par sauvegarder(motif) : liste FERMÉE, la même que MOTIFS_SAUVEGARDE de serveur.py.
  const MOTIFS_SAUVEGARDE = ['avant-format-v2', 'avant-format-v3', 'avant-import', 'avant-import-zip', 'avant-mise-a-jour'];
  // 'html' : rapport mensuel figé (lot 3, ARCHITECTURE.md §15.1).
  // Les mêmes que TYPES_DOCUMENTS de serveur.py (audit F4 : « .doc » et « .xls » ne sont plus acceptés).
  const EXTENSIONS_DOCUMENTS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'pdf', 'txt', 'csv', 'docx',
    'xlsx', 'odt', 'ods', 'html'];
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

  // 'AAAA-MM-JJTHH:MM:SS' (heure locale) : date des manifestes et de derniere-version.json (docs/FORMAT.md §9).
  function dateHeureManifeste(date) {
    return dateDuJour(date) + 'T' + deuxChiffres(date.getHours()) + ':' + deuxChiffres(date.getMinutes())
      + ':' + deuxChiffres(date.getSeconds());
  }

  // Jour (Date à minuit, heure locale) d'un nom « AAAA-MM-JJ », ou null si le nom n'a pas exactement cette forme
  // ou n'est pas une vraie date (« 2026-02-30 », « 2026-13-01 ») : un tel dossier n'est jamais touché.
  function jourDuNom(nom) {
    const trouve = MOTIF_NOM_QUOTIDIENNE.exec(nom);
    if (!trouve) { return null; }
    const annee = Number(trouve[1]);
    const mois = Number(trouve[2]) - 1;
    const quantieme = Number(trouve[3]);
    const jour = new Date(annee, mois, quantieme);
    return jour.getFullYear() === annee && jour.getMonth() === mois && jour.getDate() === quantieme ? jour : null;
  }

  // Nombre de jours de `debut` à `fin` (deux Dates à minuit) ; arrondi, car un jour de changement d'heure dure 23
  // ou 25 heures.
  function joursEntre(debut, fin) {
    return Math.round((fin.getTime() - debut.getTime()) / MS_PAR_JOUR);
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

  // Garde « fichier abîmé » de la fonction d'écriture commune (T200), sur les octets du fichier en place (null s'il
  // est absent) ; rien si le fichier est absent ou vide. Réécriture (enregistrer) : refusée si le fichier est abîmé
  // (Donnees.csv.analyser, `abime`) ; ajout (ajouter) : refusé s'il finit dans un texte entre guillemets jamais fermé
  // (Donnees.csv.finitDansUnGuillemetOuvert). Donnees.ErreurFichierAbime, rien n'est écrit.
  function verifierFichierEnPlace(table, actuel, ajout) {
    if (actuel === null || estVide(actuel)) { return; }
    const abime = ajout ? Donnees.csv.finitDansUnGuillemetOuvert(actuel) : Donnees.csv.analyser(table, actuel).abime;
    if (abime) { throw new Donnees.ErreurFichierAbime(table, table + '.csv'); }
  }

  function memesOctets(a, b) {
    return a === null || b === null ? a === b : octetsEgaux(a, b);
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

  // Les erreurs de Prévo passent telles quelles (ErreurFichierAbime et ErreurLectureSeule sont des ErreurStockage) ;
  // les erreurs du navigateur sont traduites en ErreurStockage avec un message en français (la cause d'origine est
  // conservée).
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

  // Lève une ErreurStockage si le dossier ne répond plus (supprimé, déplacé, clé USB ou partage
  // réseau débranché, autorisation retirée). Un dossier vivant, même vide, se laisse parcourir.
  async function verifierDossierAccessible(dossier) {
    try {
      await dossier.values().next();
    } catch (erreur) {
      throw erreurStockage('Le dossier de données est introuvable ou inaccessible (supprimé, déplacé, '
        + 'clé USB ou partage réseau débranché ?). Rebranchez-le ou rechoisissez le dossier.', erreur);
    }
  }

  // Contenu d'un fichier (Uint8Array), ou null s'il n'existe pas. « N'existe pas » n'est répondu
  // que si le dossier lui-même répond encore : sinon ErreurStockage (jamais une base vide).
  async function lireOctets(dossier, nom) {
    const poigneeFichier = await trouverFichier(dossier, nom);
    if (!poigneeFichier) {
      await verifierDossierAccessible(dossier);
      return null;
    }
    const fichier = await poigneeFichier.getFile();
    return new Uint8Array(await fichier.arrayBuffer());
  }

  // Vrai si le fichier a toujours le contenu `attendu` (null = absent, ou vide car tout juste
  // créé par nous). La taille est comparée d'abord : le contenu n'est relu que si elle est égale.
  async function contenuInchange(dossier, nom, attendu) {
    const poigneeFichier = await trouverFichier(dossier, nom);
    const fichier = poigneeFichier ? await poigneeFichier.getFile() : null;
    if (attendu === null) { return fichier === null || fichier.size === 0; }
    if (fichier === null || fichier.size !== attendu.length) { return false; }
    return octetsEgaux(new Uint8Array(await fichier.arrayBuffer()), attendu);
  }

  // Supprime un fichier que l'on vient de créer, mais seulement s'il est encore vide : s'il a
  // un contenu, c'est qu'un autre poste l'a écrit entre-temps, et on n'y touche pas.
  async function supprimerSiToujoursVide(dossier, nom, poigneeFichier) {
    try {
      if ((await poigneeFichier.getFile()).size === 0) { await dossier.removeEntry(nom); }
    } catch (erreurSuppression) {
      // rien à nettoyer (déjà supprimé, ou dossier devenu inaccessible)
    }
  }

  // Écrit (ou remplace) un fichier : createWritable → write → close. Chrome écrit dans un fichier
  // temporaire et ne remplace l'original qu'à la fermeture : un échec ne laisse pas de fichier
  // à moitié écrit. Réglages facultatifs :
  //   - enFin : ajoute `contenu` à partir de l'octet `enFin` (le fichier temporaire part d'une copie
  //     du fichier, keepExistingData) ; le fichier doit exister ;
  //   - controle : fonction async appelée après l'écriture et juste avant la fermeture (qui rend
  //     l'écriture visible) ; si elle lève une erreur, rien n'est écrit. C'est la fenêtre la plus
  //     courte possible entre le dernier contrôle et l'écriture effective.
  // Si le fichier venait d'être créé et que l'écriture échoue, il est supprimé s'il est encore vide.
  async function ecrireFichier(dossier, nom, contenu, reglages) {
    const options = reglages || {};
    const ajout = options.enFin !== undefined;
    const existait = ajout || (await trouverFichier(dossier, nom)) !== null;
    const poigneeFichier = await dossier.getFileHandle(nom, { create: !ajout });
    let flux = null;
    try {
      flux = await poigneeFichier.createWritable({ keepExistingData: ajout });
      if (ajout) { await flux.seek(options.enFin); }
      await flux.write(contenu);
      if (options.controle) { await options.controle(); }
      await flux.close();
    } catch (erreur) {
      if (flux) { try { await flux.abort(); } catch (erreurAbandon) { /* déjà fermé */ } }
      if (!existait) { await supprimerSiToujoursVide(dossier, nom, poigneeFichier); }
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

  // Copie le fichier `nom` de « source » vers « cible » (sans changer son contenu) ; rend les octets copiés (pour
  // le manifeste : c'est exactement ce qui a été écrit).
  async function copierFichier(source, cible, nom) {
    const poigneeFichier = await source.getFileHandle(nom);
    const octets = new Uint8Array(await (await poigneeFichier.getFile()).arrayBuffer());
    await ecrireFichier(cible, nom, octets);
    return octets;
  }

  // --- Manifeste des sauvegardes (docs/FORMAT.md §9) -----------------------------------------
  // Formats (js/formats.js) et Donnees (js/donnees.js) ne sont lus qu'au moment des appels.

  // { nom, octets, sha256 } d'un fichier copié, calculé par Formats.manifeste. Fichier par fichier : les octets d'un
  // document (photo, PDF) ne restent pas en mémoire jusqu'à la fin de la sauvegarde.
  // T206 (contrat, point 2) : abime vrai → « abime »: true dans l'entrée du manifeste (absente sinon).
  async function decrireFichier(nom, octets, abime) {
    return (await Formats.manifeste([{ nom: nom, octets: octets, abime: abime === true }])).fichiers[0];
  }

  // T206 : critère « fichier abîmé » d'un CSV de table (règle numéro un, celui de la garde : Donnees.csv.analyser,
  // `abime`) ; un fichier que l'analyse ne sait pas lire du tout est compté abîmé.
  function csvAbime(table, octets) {
    try {
      return Donnees.csv.analyser(table, octets).abime === true;
    } catch (erreurLecture) {
      return true;
    }
  }

  // Format de la base sauvegardée : parametres.version_schema (Formats.versionDeBase : absent ou illisible → 1) ;
  // null (champ omis) si parametres.csv ne se lit pas : le manifeste n'empêche jamais une sauvegarde.
  function formatDeLaBase(octetsParametres) {
    try {
      const lignes = octetsParametres === null ? [] : Donnees.csv.analyser('parametres', octetsParametres).lignes;
      return Formats.versionDeBase(lignes);
    } catch (erreurLecture) {
      return null;
    }
  }

  function versionDeLAppli() {
    return typeof App !== 'undefined' && App && typeof App.version === 'string' ? App.version : undefined;
  }

  // Manifeste d'une sauvegarde : { application, version_appli, format, date, motif, mode: 'dossier', [de, vers,]
  // fichiers } (décrits par decrireFichier, triés par nom comme le fait Formats.manifeste).
  // reglages : { motif, versionAppli (défaut App.version), complements (champs ajoutés avant « fichiers ») }.
  async function manifesteDeSauvegarde(decrits, octetsParametres, reglages) {
    const manifeste = await Formats.manifeste([], {
      version_appli: reglages.versionAppli || versionDeLAppli(),
      format: formatDeLaBase(octetsParametres),
      date: dateHeureManifeste(new Date()),
      motif: reglages.motif,
      mode: 'dossier',
    });
    delete manifeste.fichiers;
    Object.assign(manifeste, reglages.complements || {});
    manifeste.fichiers = decrits.slice().sort(function (a, b) {
      if (a.nom < b.nom) { return -1; }
      return a.nom > b.nom ? 1 : 0;
    });
    return manifeste;
  }

  function enJson(valeur) {
    return encodeurUtf8.encode(JSON.stringify(valeur, null, 2) + '\n');
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

  // Motif facultatif de sauvegarder(motif) → suffixe du nom ('' sans motif). Tout motif hors de la
  // liste fermée est refusé (comme le serveur répond 400) : jamais un texte libre dans un nom de dossier.
  function suffixeDuMotif(motif) {
    if (motif === undefined || motif === null || motif === '') { return ''; }
    if (typeof motif !== 'string' || MOTIFS_SAUVEGARDE.indexOf(motif) === -1) {
      throw erreurStockage('Motif de sauvegarde refusé. Motifs acceptés : ' + MOTIFS_SAUVEGARDE.join(', ') + '.');
    }
    return '_' + motif;
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

    // documents/ du dossier de données → documents/ de la sauvegarde (« avant-import-zip »), fichier par fichier,
    // marqueur réécrit avant chacun. Rend leurs descriptions pour le manifeste, sous le nom « documents/<nom> ».
    async function copierDocuments(dossierSauvegarde, marqueur) {
      const source = await trouverDossier(racine, NOM_DOSSIER_DOCUMENTS, false);
      if (!source) { return []; }
      const noms = [];
      for await (const entree of source.values()) {
        if (entree.kind === 'file' && !entree.name.startsWith('.')) { noms.push(entree.name); }   // ni caché (serveur)
      }
      noms.sort();
      const cible = await trouverDossier(dossierSauvegarde, NOM_DOSSIER_DOCUMENTS, true);
      const decrits = [];
      for (const nom of noms) {
        await ecrireFichier(dossierSauvegarde, NOM_MARQUEUR_EN_COURS, marqueur);
        decrits.push(await decrireFichier(NOM_DOSSIER_DOCUMENTS + '/' + nom, await copierFichier(source, cible, nom)));
      }
      return decrits;
    }

    // Crée sauvegardes/<nom>/ avec une copie des tables données (et de documents/ si reglages.documents),
    // puis manifeste.json. Le marqueur « .en-cours » est posé d'abord (et réécrit avant chaque fichier
    // copié), retiré en dernier, APRÈS le manifeste. Si la copie échoue, le dossier à moitié rempli est
    // supprimé ; si l'onglet est fermé pendant la copie, le marqueur reste et la sauvegarde est vue
    // comme incomplète (ignorée par la liste, refaite si c'est celle du jour).
    // reglages : { motif (écrit dans le manifeste), documents, versionAppli, complements } (manifesteDeSauvegarde).
    // T206 : chaque CSV abîmé est marqué « abime » dans le manifeste ; `tables` étant toujours toutes celles du
    // dossier, fichiers-abimes.json est ensuite mis à jour (sans jamais faire échouer la sauvegarde).
    async function creerSauvegarde(nom, tables, reglages) {
      const options = reglages || {};
      const dossierSauvegardes = await trouverDossier(racine, NOM_DOSSIER_SAUVEGARDES, true);
      const dossierSauvegarde = await trouverDossier(dossierSauvegardes, nom, true);
      const marqueur = encodeurUtf8.encode(poste + ';' + idSession);
      const decrits = [];
      const abimees = [];
      let octetsParametres = null;
      try {
        for (const table of tables) {
          await ecrireFichier(dossierSauvegarde, NOM_MARQUEUR_EN_COURS, marqueur);
          const octets = await copierFichier(racine, dossierSauvegarde, table + '.csv');
          if (table === 'parametres') { octetsParametres = octets; }
          const abime = csvAbime(table, octets);
          if (abime) { abimees.push(table); }
          decrits.push(await decrireFichier(table + '.csv', octets, abime));
        }
        if (options.documents) {
          decrits.push.apply(decrits, await copierDocuments(dossierSauvegarde, marqueur));
        }
        await ecrireFichier(dossierSauvegarde, NOM_MARQUEUR_EN_COURS, marqueur);
        await ecrireFichier(dossierSauvegarde, NOM_MANIFESTE,
          enJson(await manifesteDeSauvegarde(decrits, octetsParametres, options)));
        await dossierSauvegarde.removeEntry(NOM_MARQUEUR_EN_COURS);
      } catch (erreur) {
        try { await dossierSauvegardes.removeEntry(nom, { recursive: true }); } catch (erreurNettoyage) { /* tant pis */ }
        throw erreur;
      }
      etatsDesQuotidiennes.set(nom, abimees.length === 0);
      try {
        await ecrireFichiersAbimes(abimees);
      } catch (erreurNote) {
        console.warn('Prévo : ' + NOM_FICHIERS_ABIMES + ' non mis à jour (' + (erreurNote && erreurNote.message) + ').',
          erreurNote);
      }
    }

    // 'complete', 'en-cours' (marqueur récent : un autre poste copie) ou 'interrompue'
    // (marqueur ancien, ou aucun CSV : l'onglet a été fermé pendant la copie).
    async function etatSauvegarde(dossierSauvegarde) {
      const marqueur = await trouverFichier(dossierSauvegarde, NOM_MARQUEUR_EN_COURS);
      if (marqueur) {
        const age = Date.now() - (await marqueur.getFile()).lastModified;
        return age < DUREE_SAUVEGARDE_EN_COURS_MS ? 'en-cours' : 'interrompue';
      }
      return (await tablesPresentes(dossierSauvegarde)).length > 0 ? 'complete' : 'interrompue';
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

    // T206 (contrat, point 3) : quotidienne « sans fichier abîmé » = complète (sans « .en-cours », au moins un CSV),
    // dont le manifeste ne marque aucun fichier « abime » et dont aucun CSV n'est abîmé (csvAbime). Un manifeste
    // sain d'après T206 ne se distingue pas d'un manifeste plus ancien (sans l'information) : les CSV sont donc
    // analysés, seulement quand la rotation en a besoin pour décider, une fois par session (etatsDesQuotidiennes ;
    // une sauvegarde n'est jamais modifiée après coup) ; rien n'est jamais écrit dans la sauvegarde.
    const etatsDesQuotidiennes = new Map();               // nom → vrai si sans fichier abîmé
    async function quotidienneSaine(dossierSauvegarde, nom) {
      if (etatsDesQuotidiennes.has(nom)) { return etatsDesQuotidiennes.get(nom); }
      if (await trouverFichier(dossierSauvegarde, NOM_MARQUEUR_EN_COURS)) { return false; }
      const octetsManifeste = await lireOctets(dossierSauvegarde, NOM_MANIFESTE);
      let saine = true;
      if (octetsManifeste !== null) {
        try {
          const manifeste = JSON.parse(decodeurUtf8Strict.decode(sansBom(octetsManifeste)));
          const fichiers = manifeste && Array.isArray(manifeste.fichiers) ? manifeste.fichiers : [];
          saine = !fichiers.some(function (fichier) { return fichier && fichier.abime === true; });
        } catch (erreurLecture) {
          // manifeste illisible : les CSV décident
        }
      }
      const tables = saine ? await tablesPresentes(dossierSauvegarde) : [];
      if (saine && tables.length === 0) { saine = false; }
      for (const table of tables) {
        if (!saine) { break; }
        saine = !csvAbime(table, await lireOctets(dossierSauvegarde, table + '.csv'));
      }
      etatsDesQuotidiennes.set(nom, saine);
      return saine;
    }

    // Quotidiennes [{ nom, dossier, ancienne }] → noms à supprimer : les anciennes (plus de 30 jours), sauf celles
    // qui sont parmi les QUOTIDIENNES_SAINES_GARDEES plus récentes sans fichier abîmé. Parcours de la plus récente à
    // la plus ancienne ; l'état d'une quotidienne n'est lu que tant que les 7 saines ne sont pas trouvées et qu'il
    // reste une ancienne à décider.
    async function quotidiennesASupprimer(quotidiennes) {
      const parDate = quotidiennes.slice().sort(function (a, b) {
        if (a.nom < b.nom) { return 1; }
        return a.nom > b.nom ? -1 : 0;
      });
      let anciennesADecider = parDate.filter(function (q) { return q.ancienne; }).length;
      let saines = 0;
      const resultat = [];
      for (const quotidienne of parDate) {
        if (anciennesADecider === 0) { break; }
        if (saines >= QUOTIDIENNES_SAINES_GARDEES) {
          if (quotidienne.ancienne) { resultat.push(quotidienne.nom); anciennesADecider -= 1; }
          continue;
        }
        const saine = await quotidienneSaine(quotidienne.dossier, quotidienne.nom);
        if (saine) { saines += 1; }
        if (quotidienne.ancienne) {
          anciennesADecider -= 1;
          if (!saine) { resultat.push(quotidienne.nom); }
        }
      }
      return resultat;
    }

    // Rotation (D170), après chaque nouvelle quotidienne et chaque nouvelle manuelle : quotidiennes
    // « AAAA-MM-JJ » (date réelle) de plus de 30 jours avant la date du jour du poste, sauf les 7 plus récentes
    // sans fichier abîmé (T206, quotidiennesASupprimer), et manuelles « AAAA-MM-JJ_HHMMSS » au-delà des 60 plus
    // récentes, supprimées. Rien d'autre n'est touché : ni les « …_avant-… », ni un nom hors de ces motifs, ni un
    // fichier. Une suppression impossible n'arrête pas l'écriture en cours (nouvel essai à la rotation suivante).
    // Rend les noms supprimés.
    async function tournerSauvegardes() {
      try {
        const dossierSauvegardes = await trouverDossier(racine, NOM_DOSSIER_SAUVEGARDES, false);
        if (!dossierSauvegardes) { return []; }
        const aujourdhui = jourDuNom(dateDuJour());
        const manuelles = [];
        const quotidiennes = [];
        for await (const entree of dossierSauvegardes.values()) {
          if (entree.kind !== 'directory') { continue; }
          if (MOTIF_NOM_MANUELLE.test(entree.name)) {
            manuelles.push(entree.name);
            continue;
          }
          const jour = jourDuNom(entree.name);
          if (jour !== null) {
            quotidiennes.push({ nom: entree.name, dossier: entree,
              ancienne: joursEntre(jour, aujourdhui) > JOURS_GARDES_QUOTIDIENNES });
          }
        }
        const aSupprimer = await quotidiennesASupprimer(quotidiennes);
        manuelles.sort();                                   // la plus ancienne d'abord
        aSupprimer.push.apply(aSupprimer, manuelles.slice(0, Math.max(0, manuelles.length - MANUELLES_GARDEES)));
        const supprimees = [];
        for (const nom of aSupprimer) {
          try {
            await dossierSauvegardes.removeEntry(nom, { recursive: true });
            supprimees.push(nom);
          } catch (erreurSuppression) {
            // retentée à la rotation suivante
          }
        }
        return supprimees;
      } catch (erreur) {
        console.warn('Prévo : rotation des sauvegardes impossible (' + (erreur && erreur.message) + ').', erreur);
        return [];
      }
    }

    // Avant la première écriture du jour : copie de tous les CSV dans sauvegardes/AAAA-MM-JJ/
    // (rien si elle existe déjà complète, si un autre poste est en train de la faire, ou s'il n'y
    // a encore aucun CSV ; refaite si elle a été interrompue), puis rotation. À appeler dans enSerie.
    async function sauvegardeQuotidienneSiBesoin() {
      const nom = dateDuJour();
      const dossierSauvegardes = await trouverDossier(racine, NOM_DOSSIER_SAUVEGARDES, false);
      const existante = dossierSauvegardes ? await trouverDossier(dossierSauvegardes, nom, false) : null;
      if (existante) {
        if ((await etatSauvegarde(existante)) !== 'interrompue') { return; }
        await dossierSauvegardes.removeEntry(nom, { recursive: true });
      }
      const tables = await tablesPresentes(racine);
      if (tables.length === 0) { return; }
      await creerSauvegarde(nom, tables, { motif: MOTIF_QUOTIDIENNE });
      await tournerSauvegardes();
    }

    // motif (facultatif) : 'avant-format-v2' → « AAAA-MM-JJ_HHMMSS_avant-format-v2 » ; sans motif,
    // sauvegarde manuelle « AAAA-MM-JJ_HHMMSS » (puis rotation). 'avant-import-zip' copie aussi
    // documents/. Motif hors liste → ErreurStockage, rien n'est écrit.
    async function sauvegarder(motif) {
      const suffixe = suffixeDuMotif(motif);
      return enSerie(async function () {
        const nom = await nouveauNomHorodate(suffixe);
        verifierNomSauvegarde(nom);                     // sécurité : le nom reste dans les règles
        await creerSauvegarde(nom, await tablesPresentes(racine),
          { motif: suffixe ? motif : MOTIF_MANUELLE, documents: motif === MOTIF_AVANT_IMPORT_ZIP });
        if (!suffixe) { await tournerSauvegardes(); }
        return nom;
      });
    }

    // Version notée dans derniere-version.json, ou null (fichier absent, illisible ou sans « version »).
    async function lireVersionNotee() {
      const octets = await lireOctets(racine, NOM_DERNIERE_VERSION);
      if (octets === null) { return null; }
      try {
        const contenu = JSON.parse(decodeurUtf8Strict.decode(sansBom(octets)));
        return contenu && typeof contenu.version === 'string' && contenu.version !== '' ? contenu.version : null;
      } catch (erreurLecture) {
        return null;
      }
    }

    // T206 (contrat, point 4) : contenu valable de fichiers-abimes.json, { table: 'AAAA-MM-JJTHH:MM:SS' } (tables du
    // schéma seulement) ; {} si le fichier est absent ou illisible.
    async function lireFichiersAbimes() {
      const octets = await lireOctets(racine, NOM_FICHIERS_ABIMES);
      const resultat = {};
      if (octets === null) { return resultat; }
      let depuis = null;
      try {
        const contenu = JSON.parse(decodeurUtf8Strict.decode(sansBom(octets)));
        depuis = contenu && typeof contenu === 'object' ? contenu.depuis : null;
      } catch (erreurLecture) {
        return resultat;
      }
      if (!depuis || typeof depuis !== 'object') { return resultat; }
      Schema.nomsTables().forEach(function (table) {
        const date = depuis[table];
        if (typeof date === 'string' && MOTIF_DATE_MANIFESTE.test(date)) { resultat[table] = date; }
      });
      return resultat;
    }

    // Met fichiers-abimes.json à jour quand l'état de toutes les tables est connu (`abimees` : les tables abîmées) :
    // table abîmée → date gardée si elle y est, sinon maintenant ; table saine → retirée. Réécrit seulement s'il
    // change ; jamais créé tant qu'aucune table n'est abîmée. Rend { table: date } des tables abîmées. À appeler dans
    // enSerie (écritures une par une).
    async function ecrireFichiersAbimes(abimees) {
      const connues = await lireFichiersAbimes();
      const maintenant = dateHeureManifeste(new Date());
      const depuis = {};
      Schema.nomsTables().forEach(function (table) {
        if (abimees.indexOf(table) !== -1) { depuis[table] = connues[table] || maintenant; }
      });
      const octets = enJson({ depuis: depuis });
      const actuel = await lireOctets(racine, NOM_FICHIERS_ABIMES);
      if (actuel === null ? Object.keys(depuis).length > 0 : !memesOctets(actuel, octets)) {
        await ecrireFichier(racine, NOM_FICHIERS_ABIMES, octets);
      }
      return depuis;
    }

    // T213 : un CSV que l'import ZIP écrit tel quel parce que son ZIP le marque abîmé (enregistrer,
    // options.abimeDepuis) : sa date « depuis » (celle du manifeste du ZIP, gardée telle quelle, jamais remise à zéro
    // par l'import) remplace celle de fichiers-abimes.json. Échec : dit sur la console, la table reste écrite. À
    // appeler dans enSerie.
    async function noterDepuisImporte(table, date) {
      try {
        const connues = await lireFichiersAbimes();
        const depuis = {};
        Schema.nomsTables().forEach(function (nom) {
          if (nom === table || connues[nom]) { depuis[nom] = nom === table ? date : connues[nom]; }
        });
        await ecrireFichier(racine, NOM_FICHIERS_ABIMES, enJson({ depuis: depuis }));
      } catch (erreur) {
        console.warn('Prévo : ' + NOM_FICHIERS_ABIMES + ' non mis à jour (' + (erreur && erreur.message) + ').', erreur);
      }
    }

    // À l'ouverture du dossier, une fois les tables chargées (js/app.js ; jamais en lecture seule) : `tables` =
    // les tables abîmées (Donnees.tablesAbimees). Rend { table: date } (abimesDepuis).
    async function noterFichiersAbimes(tables) {
      if (!Array.isArray(tables)) { throw erreurStockage('« tables » doit être une liste de noms de tables.'); }
      tables.forEach(verifierNomTable);
      return enSerie(function () { return ecrireFichiersAbimes(tables); });
    }

    // D170 : à l'ouverture du dossier, AVANT le passage au format courant et toute autre écriture
    // (js/app.js ; jamais en lecture seule, où rien ne doit être écrit). derniere-version.json absent,
    // illisible ou d'une autre version que `versionAppli` → sauvegarde « AAAA-MM-JJ_HHMMSS_avant-mise-a-jour »
    // (manifeste avec « de » : version notée ou null, et « vers »), puis, seulement si elle a réussi,
    // derniere-version.json réécrit : { version, depuis }. Base vide (aucun CSV) : rien à sauvegarder, la
    // version est seulement notée (la base sera créée par cette version). Même version : rien n'est écrit.
    // Rend { sauvegarde: nom ou null, de: version notée ou null }.
    async function sauvegarderAvantMiseAJour(versionAppli) {
      if (typeof versionAppli !== 'string' || versionAppli === '') {
        throw erreurStockage('Version de l\'application inconnue : rien n\'est sauvegardé.');
      }
      return enSerie(async function () {
        const notee = await lireVersionNotee();
        if (notee === versionAppli) { return { sauvegarde: null, de: notee }; }
        const tables = await tablesPresentes(racine);
        let nom = null;
        if (tables.length > 0) {
          nom = await nouveauNomHorodate('_' + MOTIF_AVANT_MISE_A_JOUR);
          verifierNomSauvegarde(nom);
          await creerSauvegarde(nom, tables, { motif: MOTIF_AVANT_MISE_A_JOUR, versionAppli: versionAppli,
            complements: { de: notee, vers: versionAppli } });
        }
        await ecrireFichier(racine, NOM_DERNIERE_VERSION,
          enJson({ version: versionAppli, depuis: dateHeureManifeste(new Date()) }));
        return { sauvegarde: nom, de: notee };
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
        // Sauvegarde incomplète (copie en cours ou interrompue) : pas proposée à la restauration.
        if (await trouverFichier(dossierSauvegarde, NOM_MARQUEUR_EN_COURS)) { continue; }
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
        if (await trouverFichier(dossierSauvegarde, NOM_MARQUEUR_EN_COURS)) {
          throw erreurStockage('La sauvegarde ' + nom + ' est incomplète (copie interrompue ou en cours) : '
            + 'choisissez-en une autre.');
        }
        const aRestaurer = choisirTablesARestaurer(await tablesPresentes(dossierSauvegarde), tables);

        const copieSecurite = await nouveauNomHorodate(SUFFIXE_AVANT_RESTAURATION);
        await creerSauvegarde(copieSecurite, await tablesPresentes(racine), { motif: MOTIF_AVANT_RESTAURATION });

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
        try {
          const abimees = [];
          for (const table of await tablesPresentes(racine)) {
            if (csvAbime(table, await lireOctets(racine, table + '.csv'))) { abimees.push(table); }
          }
          await ecrireFichiersAbimes(abimees);              // T206 : table redevenue saine → retirée
        } catch (erreurNote) {
          console.warn('Prévo : ' + NOM_FICHIERS_ABIMES + ' non mis à jour (' + (erreurNote && erreurNote.message) + ').',
            erreurNote);
        }
        return { restaurees: restaurees, copieSecurite: copieSecurite };
      });
    }

    // --- Écriture des CSV ------------------------------------------------------------------

    // Contrôle à faire juste avant de valider une écriture : le fichier doit être resté tel qu'on
    // l'a lu (`lu` : octets lus, ou null s'il était absent). Sinon ErreurConflit, avec sa version.
    function controleInchange(nomFichier, lu) {
      return async function () {
        if (await contenuInchange(racine, nomFichier, lu)) { return; }
        const actuel = await lireOctets(racine, nomFichier);
        const vide = actuel === null || (lu === null && actuel.length === 0);
        throw new Donnees.ErreurConflit('Le fichier ' + nomFichier + ' vient d\'être modifié par un autre poste.',
          vide ? null : await empreinte(actuel));
      };
    }

    // Remplace le CSV si sa version actuelle est celle attendue (null = le fichier ne doit pas
    // exister) ; sinon ErreurConflit.
    // Ordre (relecture vague 3) : la sauvegarde quotidienne d'abord (copie des 23 CSV, longue),
    // PUIS lecture et contrôle de version, écriture dans le fichier temporaire, dernier contrôle
    // (contenu inchangé) et fermeture. Une écriture d'un autre poste pendant la sauvegarde ou
    // pendant notre écriture donne un conflit au lieu d'être écrasée.
    // Fichier abîmé (T200, règle numéro un : Donnees.csv.analyser, `abime` : structure abîmée ou valeurs au-delà de
    // l'en-tête) : Donnees.ErreurFichierAbime, rien n'est écrit, sauf `options.remplacerFichierAbime === true` (import
    // ZIP). C'est la fonction d'écriture commune d'une table entière : tout appelant y passe (Donnees et les écritures
    // directes de l'application) ; seule la restauration d'une sauvegarde (restaurer) remplace aussi un tel fichier.
    // T206 (règle de Nicolas, contrat point 1 ; remplace l'ordre de T204) : un fichier abîmé bloque l'écriture, jamais
    // la sauvegarde quotidienne. La sauvegarde du jour (si besoin) passe donc AVANT la garde : un refus fait la
    // sauvegarde du jour si elle manque (le CSV abîmé y est marqué), puis refuse ; la table reste identique à l'octet.
    async function enregistrer(table, octets, versionAttendue, options) {
      verifierNomTable(table);
      const nouveauContenu = enOctets(octets);
      const attendue = versionAttendue === undefined ? null : versionAttendue;
      const remplacerFichierAbime = Boolean(options) && options.remplacerFichierAbime === true;
      const abimeDepuis = remplacerFichierAbime && typeof options.abimeDepuis === 'string'
        && MOTIF_DATE_MANIFESTE.test(options.abimeDepuis) ? options.abimeDepuis : null;     // T213 (import ZIP)
      return enSerie(async function () {
        await sauvegardeQuotidienneSiBesoin();
        const actuel = await lireOctets(racine, table + '.csv');
        if (!remplacerFichierAbime) { verifierFichierEnPlace(table, actuel, false); }
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
        await ecrireFichier(racine, table + '.csv', nouveauContenu,
          { controle: controleInchange(table + '.csv', actuel) });
        if (abimeDepuis) { await noterDepuisImporte(table, abimeDepuis); }
        return { version: await empreinte(nouveauContenu) };
      });
    }

    // Ajoute des lignes en fin de fichier (journal). `octets` = ligne d'en-tête + lignes (UTF-8
    // sans BOM). Mêmes règles que le serveur : fichier absent ou vide → BOM + corps ; sinon le
    // fichier doit être de l'UTF-8 valide avec le même en-tête, sinon ErreurConflit.
    // Ajout en fin : le fichier temporaire part d'une copie du fichier faite au createWritable,
    // qui a pu grandir depuis notre lecture (ligne ajoutée par un autre poste). On écrit à la
    // taille lue, puis on vérifie, juste avant la fermeture, que le fichier est toujours
    // exactement celui qu'on a lu ; sinon on abandonne (rien n'est écrit) et on lève
    // ErreurConflit : Donnees.ajouter se replie alors sur modifier, qui relit tout. Se placer à
    // la « taille réelle » ne suffirait pas : on ne sait pas si la copie a été faite avant ou
    // après l'écriture de l'autre poste, ni si celui-ci a réécrit le fichier au lieu d'ajouter.
    async function ajouter(table, octets) {
      verifierNomTable(table);
      const corps = sansBom(enOctets(octets));
      if (!estUtf8(corps)) { throw erreurStockage('Le contenu à ajouter doit être encodé en UTF-8.'); }
      const decoupe = decouperPremiereLigne(corps);
      if (decoupe.entete.length === 0) {
        throw erreurStockage('Le contenu à ajouter doit commencer par la ligne d\'en-tête.');
      }
      return enSerie(async function () {
        // T206 (comme enregistrer) : sauvegarde du jour d'abord, puis garde (fichier qui finit dans un guillemet
        // ouvert) : un refus fait la sauvegarde du jour si elle manque, rien d'autre.
        await sauvegardeQuotidienneSiBesoin();
        const actuel = await lireOctets(racine, table + '.csv');
        verifierFichierEnPlace(table, actuel, true);
        const controle = controleInchange(table + '.csv', actuel);

        if (actuel === null || estVide(actuel)) {
          const nouveau = concatener([Uint8Array.from(BOM_UTF8), corps]);
          await ecrireFichier(racine, table + '.csv', nouveau, { controle: controle });
          return { version: await empreinte(nouveau) };
        }

        // T200 : un fichier qui finit DANS une cellule entre guillemets jamais fermée (nos lignes y seraient avalées à
        // la relecture) a été refusé plus haut (verifierFichierEnPlace, après la sauvegarde du jour) ; aucune
        // dérogation pour un ajout.
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
        await ecrireFichier(racine, table + '.csv', aAjouter, { enFin: actuel.length, controle: controle });
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
      // Un document .html est isolé (aucun script ne s'y exécute) : Donnees.documentAffichable.
      const url = URL.createObjectURL(await Donnees.documentAffichable(nom, blob));
      urlsDocuments.set(nom, url);
      return url;
    }

    // --- Verrou (avertissement non bloquant : deux postes sur le même dossier) --------------

    // { autreSession: { poste, heure } } si verrou.txt a moins de 3 minutes et vient d'une autre
    // session ; sinon { autreSession: null }. L'âge se mesure avec la date de modification du
    // fichier (donnée par le système de fichiers), pas avec l'heure écrite dedans : l'horloge de
    // l'autre PC peut être décalée. L'heure écrite sert seulement à l'affichage.
    async function verifierVerrou() {
      try {
        const poigneeVerrou = await trouverFichier(racine, NOM_FICHIER_VERROU);
        if (poigneeVerrou === null) { return { autreSession: null }; }
        const fichierVerrou = await poigneeVerrou.getFile();
        const octets = new Uint8Array(await fichierVerrou.arrayBuffer());
        const morceaux = new TextDecoder().decode(octets).trim().split(';');
        if (morceaux.length < 3) { return { autreSession: null }; }
        const idAutreSession = morceaux[morceaux.length - 1].trim();
        const heure = morceaux[morceaux.length - 2].trim();
        const nomPoste = morceaux.slice(0, -2).join(';').trim();
        if (!lireDateHeureVerrou(heure) || idAutreSession === idSession) { return { autreSession: null }; }
        if (Date.now() - fichierVerrou.lastModified >= DUREE_VALIDITE_VERROU_MS) { return { autreSession: null }; }
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
      sauvegarderAvantMiseAJour: proteger('sauvegarde avant la mise à jour de Prévo', sauvegarderAvantMiseAJour),
      noterFichiersAbimes: proteger('mise à jour de ' + NOM_FICHIERS_ABIMES, noterFichiersAbimes),
      abimesDepuis: proteger('lecture de ' + NOM_FICHIERS_ABIMES, lireFichiersAbimes),
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
