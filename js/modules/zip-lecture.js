'use strict';
// ZipLecture : lecture et contrôle d'un ZIP de données, SANS RIEN ÉCRIRE (ni stockage, ni réseau). Chantier « socle
// de données », tâche T190 ; décision D172 : import par remplacement complet seulement, contrôles stricts, aucune
// nouvelle route serveur. L'écran d'import et l'écriture viennent ensuite (T191). Ordre de chargement : §15.1.
// ZIP lus : ceux de l'export de Prévo (<table>.csv à la racine, documents/<nom>, et manifeste.json depuis le chantier
// « socle de données »), y compris les exports des versions 1.2 et 2.0 bêta, qui n'ont pas de manifeste.
//
// ZipLecture.lire(source) — source : File, Blob ou ArrayBuffer (ou vue typée) → Promise de :
//   - refusé  : { ok: false, refus: '<message clair en français>' } et rien d'autre ;
//   - accepté : { ok: true, refus: null, format, formatOrigine, migre, manifeste, tables, absentes, abimes,
//                 documents, problemes } (formatOrigine, migre, tables, absentes, abimes : ZipTables, zip-tables.js) :
//       format        : format des tables rendues (Formats.courant) ;
//       formatOrigine : format du ZIP : celui du manifeste, sinon version_schema de parametres.csv
//                       (Formats.versionDeBase), ramené au plus petit format des fichiers (comme Donnees.etatDuFormat) ;
//       migre         : vrai si les tables ont été passées au format courant en mémoire (Formats.migrer) ;
//       manifeste     : le manifeste lu (objet), ou null (export sans manifeste) ;
//       tables        : { <table>: { entete, lignes, colonnesInconnues } } pour CHAQUE table du format courant
//                       (Donnees.csv.analyser, puis migration) ; une table absente du ZIP y est vide (sauf
//                       parametres quand la migration la crée : sa seule ligne est alors version_schema) ;
//       absentes      : tables absentes du ZIP (l'import les videra), dans l'ordre du schéma ;
//       documents     : [{ nom, taille, empreinte }] (nom sans « documents/ », taille décompressée, SHA-256 en
//                       hexadécimal, ou null sans crypto.subtle) : AUCUN octet, le contenu se relit par lireDocument ;
//       problemes     : problèmes de lecture des CSV, tables absentes, documents manquants à l'export (forme des
//                       problèmes de Donnees, ARCHITECTURE.md §5.2).
// La promesse n'est rejetée que sur un défaut du code (dépendance absente) : tout ZIP refusé donne { ok: false }.
// Deux passes (T205), mémoire bornée au ZIP (gardé par le résultat) + les tables + UN document : lire contrôle chaque
// document (étapes 9, 10) puis l'oublie ; lireDocument(lu, nom) le relit du même ZIP (taille, CRC-32, empreinte
// revérifiés) → Promise de Uint8Array, rejetée (Error au message clair) s'il a changé. memoire() : mesure (tests).
//
// Contrôles, dans l'ordre (le premier qui échoue donne le refus) : (1) taille du fichier avant de le lire ;
// (2) répertoire central lu ICI, pas par JSZip (qui assainit les noms et fusionne les doublons) : nombre d'entrées,
// noms hostiles (absolu « / » ou « C: », segment « .. » ou « . », barre inverse, segment vide, caractère de contrôle,
// UTF-8 invalide), doublons (casse ignorée), entrée chiffrée, méthode autre que « stocké » et « deflate », données
// hors du fichier ; (3) tailles DÉCLARÉES, avant toute décompression : taux de compression (au-delà de 1 Mo
// décompressé : en dessous, aucune bombe possible), fichier à la racine (CSV, manifeste), document, total ; (4) JSZip voit les
// mêmes fichiers sous les mêmes noms ; (5) manifeste illisible ; (6) format plus récent que Formats.courant
// (manifeste, ou version_schema de parametres.csv) ; (7) noms admis : <table>.csv à la racine (table de Schema),
// documents/<nom> au nom admis par serveur.py, manifeste.json, le dossier documents/ lui-même, rien d'autre ;
// (8) au moins un CSV de table ; (9) décompression : taille RÉELLE contrôlée pendant (arrêt dès qu'elle dépasse la
// taille déclarée) et après (égale, CRC-32 juste) ; (10) manifeste : chaque fichier y figure avec sa taille et son
// empreinte SHA-256, et réciproquement ; un manifeste « documents »: « exclus » (export « données seules », T214)
// et des documents dans le ZIP : refusé ; (11) CSV illisible (format 0 : des colonnes du format 1 manquent à
// l'en-tête) ou abîmé (l'écrire en perdrait une partie) : on ne remplace pas une base par un fichier illisible, sauf
// fichier marqué « abime » au manifeste, à l'empreinte juste (T213 : ZipTables, rendu dans `abimes`).
// Dépendances : JSZip (js/lib/jszip.min.js), Schema, Formats, Donnees (csv.analyser), ZipTables ; crypto.subtle
// pour un ZIP avec manifeste (contexte sécurisé : file://, https, 127.0.0.1).

const ZipLecture = (function () {

  // Limites de l'import, écrites ICI seulement (T208 ; T212 : ZIP 400 Mo, 10 000 entrées, en attendant T215) : l'export (ZipDonnees) les contrôle ; serveur.py en suit deux.
  const MO = 1024 * 1024;
  const LIMITES = Object.freeze({
    zip: 400 * MO,          // taille du fichier ZIP
    entrees: 10000,         // entrées du ZIP (fichiers et dossiers)
    racine: 50 * MO,        // un fichier à la racine (CSV, manifeste), décompressé ; = envoi d'un CSV au serveur
    document: 10 * MO,      // un document (documents/<nom>), décompressé ; = envoi d'un document au serveur
    total: 1024 * MO,       // tout le contenu décompressé
    taux: 100,              // taux de compression d'une entrée : taille décompressée / taille compressée
    seuilTaux: MO,          // le taux n'est contrôlé qu'au-delà de 1 Mo décompressé
  });
  const NOM_MANIFESTE = 'manifeste.json';
  const DOSSIER_DOCUMENTS = 'documents/';

  // Règle des noms de documents : COPIE de serveur.py, verifier_nom_document pour un nom enregistré
  // (MOTIF_NOM_DOCUMENT_ENREGISTRE, « .. » interdit, extension de TYPES_DOCUMENTS, NOMS_RESERVES_WINDOWS).
  // tests/test_zip_lecture.py compare cette copie aux listes de serveur.py.
  const MOTIF_NOM_DOCUMENT = /^([0-9]{8}-[0-9]{6}-)?[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
  const EXTENSIONS_DOCUMENTS = Object.freeze(['jpg', 'jpeg', 'png', 'gif', 'webp', 'pdf', 'txt', 'csv', 'html',
    'docx', 'xlsx', 'odt', 'ods']);
  const NOMS_RESERVES_WINDOWS = Object.freeze(['con', 'prn', 'aux', 'nul']
    .concat([1, 2, 3, 4, 5, 6, 7, 8, 9].map(function (n) { return 'com' + n; }))
    .concat([1, 2, 3, 4, 5, 6, 7, 8, 9].map(function (n) { return 'lpt' + n; })));

  function nomDocumentAdmis(nom) {           // vrai si le nom (sans « documents/ ») est admis par la règle du serveur
    if (typeof nom !== 'string' || !MOTIF_NOM_DOCUMENT.test(nom) || nom.indexOf('..') >= 0) { return false; }
    const extension = nom.indexOf('.') < 0 ? '' : nom.slice(nom.lastIndexOf('.') + 1).toLowerCase();
    if (EXTENSIONS_DOCUMENTS.indexOf(extension) < 0) { return false; }
    return NOMS_RESERVES_WINDOWS.indexOf(nom.split('.')[0].toLowerCase()) < 0;
  }

  // --- Refus et messages -------------------------------------------------------------------------------------------

  class Refus extends Error {}          // refus d'un ZIP : converti en { ok: false, refus } par lire()

  function refuser(message) { throw new Refus(message); }

  const PAS_UN_ZIP = 'Ce fichier n\'est pas un ZIP lisible. Choisissez le fichier ZIP exporté par Prévo '
    + '(« prevo-export-AAAA-MM-JJ.zip »).';
  const ZIP_ABIME = 'Ce ZIP est abîmé (structure illisible ou incohérente) : il est refusé. Refaites l\'export, '
    + 'ou choisissez un autre fichier.';
  const MANIFESTE_ILLISIBLE = 'Le manifeste du ZIP (manifeste.json) est illisible : le ZIP a été abîmé ou modifié '
    + 'après l\'export. Il est refusé ; refaites l\'export.';

  // Nombre écrit à la française : 2 001. Taille, une décimale au plus : « 60 Mo », « 10,5 Mo », « 1 Go », « 1,1 Go ».
  function enChiffres(nombre) { return String(nombre).replace(/\B(?=(\d{3})+(?!\d))/g, ' '); }
  function enMo(octets) {
    const go = octets >= 1024 * MO;
    return String(Math.round(octets / (go ? 1024 * MO : MO) * 10) / 10).replace('.', ',') + (go ? ' Go' : ' Mo');
  }

  function estControle(code) { return code < 0x20 || (code >= 0x7f && code <= 0x9f); }

  // Nom d'entrée affichable dans un message : caractères de contrôle remplacés par « ? », 100 caractères au plus.
  function afficher(nom) {
    let texte = '';
    for (let i = 0; i < nom.length && i < 100; i += 1) { texte += estControle(nom.charCodeAt(i)) ? '?' : nom[i]; }
    return nom.length > 100 ? texte + '…' : texte;
  }

  // Problème au format de Donnees (ARCHITECTURE.md §5.2).
  function probleme(gravite, type, table, message) {
    return { gravite: gravite, type: type, table: table, ligne: null, id: null, champ: null, valeur: null,
      message: message };
  }

  // --- 1. Octets du fichier (taille contrôlée avant de lire) -------------------------------------------------------

  function tailleDe(source) {
    if (source instanceof ArrayBuffer || ArrayBuffer.isView(source)) { return source.byteLength; }
    if (typeof Blob !== 'undefined' && source instanceof Blob) { return source.size; }
    return null;
  }

  async function lireOctets(source) {
    const taille = tailleDe(source);
    if (taille === null) { refuser('Aucun fichier à lire : choisissez le fichier ZIP exporté par Prévo.'); }
    if (taille > LIMITES.zip) {
      refuser('Ce fichier fait ' + enMo(taille) + ' : un ZIP de données ne peut pas dépasser ' + enMo(LIMITES.zip)
        + '. Il est refusé.');
    }
    if (source instanceof ArrayBuffer) { return new Uint8Array(source); }
    if (ArrayBuffer.isView(source)) { return new Uint8Array(source.buffer, source.byteOffset, source.byteLength); }
    try {
      return new Uint8Array(await source.arrayBuffer());
    } catch (erreur) {
      return refuser('Lecture du fichier impossible (' + ((erreur && erreur.message) || 'erreur inconnue') + ').');
    }
  }

  // --- 2. Répertoire central (APPNOTE de PKWARE), lu avant toute décompression -------------------------------------

  const SIGNATURES = Object.freeze({ fin: 0x06054b50, localisateur64: 0x07064b50, fin64: 0x06064b50,
    centrale: 0x02014b50, locale: 0x04034b50 });
  const MAX_16 = 0xFFFF;
  const MAX_32 = 0xFFFFFFFF;
  const CHAMP_ZIP64 = 0x0001;
  const ATTRIBUT_DOSSIER = 0x10;
  const decodeurNoms = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true });

  function lecteur(octets) {
    const vue = new DataView(octets.buffer, octets.byteOffset, octets.byteLength);
    return {
      u16: function (position) { return vue.getUint16(position, true); },
      u32: function (position) { return vue.getUint32(position, true); },
      u64: function (position) { return vue.getUint32(position, true) + vue.getUint32(position + 4, true) * 0x100000000; },
    };
  }

  // Nom d'une entrée : UTF-8 (comme JSZip) ; null si les octets n'en sont pas.
  function decoderNom(octetsNom) {
    try { return decodeurNoms.decode(octetsNom); } catch (erreur) { return null; }
  }

  // Dernière signature de fin du répertoire central (comme JSZip), ou -1.
  function trouverFin(octets, lire) {
    const premier = Math.max(0, octets.length - 22 - MAX_16);
    for (let position = octets.length - 22; position >= premier; position -= 1) {
      if (lire.u32(position) === SIGNATURES.fin) { return position; }
    }
    return -1;
  }

  // Tailles et position sur 64 bits (champ « ZIP64 » des données en plus) quand le champ sur 32 bits est saturé.
  function lireZip64(lire, debut, longueur, entree) {
    if (entree.decompresse !== MAX_32 && entree.compresse !== MAX_32 && entree.local !== MAX_32) { return; }
    const finExtra = debut + longueur;
    for (let position = debut; position + 4 <= finExtra; position += 4 + lire.u16(position + 2)) {
      if (lire.u16(position) !== CHAMP_ZIP64) { continue; }
      const finChamp = Math.min(finExtra, position + 4 + lire.u16(position + 2));
      let curseur = position + 4;
      for (const cle of ['decompresse', 'compresse', 'local']) {
        if (entree[cle] === MAX_32 && curseur + 8 <= finChamp) { entree[cle] = lire.u64(curseur); curseur += 8; }
      }
      return;
    }
  }

  // Position, taille et nombre d'entrées du répertoire central (fin « ZIP64 » comprise).
  function lireFin(octets, lire) {
    const fin = trouverFin(octets, lire);
    if (fin < 0) { refuser(PAS_UN_ZIP); }
    if (lire.u16(fin + 4) !== 0 || lire.u16(fin + 6) !== 0) {
      refuser('Ce ZIP est en plusieurs parties : il est refusé. Choisissez le ZIP exporté par Prévo, en un seul fichier.');
    }
    const resultat = { nombre: lire.u16(fin + 10), taille: lire.u32(fin + 12), debut: lire.u32(fin + 16) };
    if (resultat.nombre === MAX_16 || resultat.taille === MAX_32 || resultat.debut === MAX_32) {
      const localisateur = fin - 20;
      if (localisateur < 0 || lire.u32(localisateur) !== SIGNATURES.localisateur64) { refuser(ZIP_ABIME); }
      const fin64 = lire.u64(localisateur + 8);
      if (fin64 + 56 > octets.length || lire.u32(fin64) !== SIGNATURES.fin64) { refuser(ZIP_ABIME); }
      resultat.nombre = lire.u64(fin64 + 32);
      resultat.taille = lire.u64(fin64 + 40);
      resultat.debut = lire.u64(fin64 + 48);
    }
    return resultat;
  }

  // Entrées du répertoire central : { entrees: [{ nom, dossier, drapeaux, methode, crc, compresse, decompresse,
  // local }], debut, lire }.
  function lireRepertoire(octets) {
    if (octets.length < 22) { refuser(PAS_UN_ZIP); }
    const lire = lecteur(octets);
    const fin = lireFin(octets, lire);
    if (fin.nombre > LIMITES.entrees) {
      refuser('Ce ZIP contient ' + enChiffres(fin.nombre) + ' entrées : ' + enChiffres(LIMITES.entrees)
        + ' au plus. Il est refusé.');
    }
    const finRepertoire = fin.debut + fin.taille;
    if (finRepertoire > octets.length) { refuser(ZIP_ABIME); }
    const entrees = [];
    let position = fin.debut;
    for (let numero = 0; numero < fin.nombre; numero += 1) {
      if (position + 46 > finRepertoire || lire.u32(position) !== SIGNATURES.centrale) { refuser(ZIP_ABIME); }
      const longueurNom = lire.u16(position + 28);
      const longueurExtra = lire.u16(position + 30);
      const suivante = position + 46 + longueurNom + longueurExtra + lire.u16(position + 32);
      if (suivante > finRepertoire) { refuser(ZIP_ABIME); }
      const nom = decoderNom(octets.subarray(position + 46, position + 46 + longueurNom));
      const entree = {
        nom: nom,
        // Dossier : nom en « / » ou attribut « dossier » (même règle que JSZip).
        dossier: nom !== null && (nom.endsWith('/') || (lire.u32(position + 38) & ATTRIBUT_DOSSIER) !== 0),
        drapeaux: lire.u16(position + 8), methode: lire.u16(position + 10), crc: lire.u32(position + 16),
        compresse: lire.u32(position + 20), decompresse: lire.u32(position + 24), local: lire.u32(position + 42),
      };
      lireZip64(lire, position + 46 + longueurNom, longueurExtra, entree);
      entrees.push(entree);
      position = suivante;
    }
    return { entrees: entrees, debut: fin.debut, lire: lire };
  }

  // Raison pour laquelle un nom d'entrée est hostile, ou null.
  function raisonHostile(nom) {
    if (nom === null) { return 'nom illisible : ce n\'est pas de l\'UTF-8'; }
    if (nom === '') { return 'nom vide'; }
    for (let i = 0; i < nom.length; i += 1) {
      if (estControle(nom.charCodeAt(i))) { return 'caractère de contrôle'; }
    }
    if (nom.indexOf('\\') >= 0) { return 'barre oblique inverse'; }
    if (nom[0] === '/' || /^[A-Za-z]:/.test(nom)) { return 'chemin absolu'; }
    const segments = (nom.endsWith('/') ? nom.slice(0, -1) : nom).split('/');
    if (segments.indexOf('..') >= 0) { return 'remontée de dossier « .. »'; }
    if (segments.indexOf('.') >= 0) { return 'segment « . »'; }
    return segments.indexOf('') >= 0 ? 'segment vide' : null;
  }

  // Noms hostiles, doublons, chiffrement, méthode, données hors du fichier, puis tailles déclarées.
  function controlerEntrees(repertoire) {
    const lire = repertoire.lire;
    const vus = new Set();
    for (const entree of repertoire.entrees) {
      const raison = raisonHostile(entree.nom);
      if (raison) {
        refuser('Ce ZIP contient un chemin dangereux : « ' + afficher(entree.nom === null ? '?' : entree.nom) + ' » ('
          + raison + '). Il est refusé.');
      }
      const cle = entree.nom.toLowerCase();
      if (vus.has(cle)) {
        refuser('Ce ZIP contient deux fois « ' + afficher(entree.nom) + ' » : il est refusé (on ne saurait pas '
          + 'lequel importer).');
      }
      vus.add(cle);
    }
    for (const entree of repertoire.entrees) {
      if (entree.drapeaux & 1) {
        refuser('« ' + afficher(entree.nom) + ' » est chiffré dans ce ZIP : un export de Prévo ne l\'est jamais. '
          + 'Il est refusé.');
      }
      if (entree.methode !== 0 && entree.methode !== 8) {
        refuser('« ' + afficher(entree.nom) + ' » est compressé par une méthode que Prévo ne lit pas (méthode '
          + entree.methode + ') : ZIP refusé. Refaites l\'export.');
      }
      const local = entree.local;
      if (local + 30 > repertoire.debut || lire.u32(local) !== SIGNATURES.locale) { refuser(ZIP_ABIME); }
      const donnees = local + 30 + lire.u16(local + 26) + lire.u16(local + 28);
      if (donnees + entree.compresse > repertoire.debut) { refuser(ZIP_ABIME); }
    }
    controlerTaillesDeclarees(repertoire.entrees);
  }

  function controlerTaillesDeclarees(entrees) {
    let total = 0;
    for (const entree of entrees) {
      if (entree.dossier) { continue; }
      if (entree.decompresse > LIMITES.seuilTaux
        && (entree.compresse === 0 || entree.decompresse / entree.compresse > LIMITES.taux)) {
        const taux = entree.compresse === 0 ? 'infiniment'
          : enChiffres(Math.round(entree.decompresse / entree.compresse)) + ' fois';
        refuser('« ' + afficher(entree.nom) + ' » se décompresse ' + taux + ' plus gros qu\'il n\'est compressé '
          + '(100 fois au plus) : bombe de décompression probable. Le ZIP est refusé.');
      }
      const [limite, quoi] = entree.nom.indexOf('/') < 0 ? [LIMITES.racine, 'fichier de données']
        : [LIMITES.document, 'document'];
      if (entree.decompresse > limite) {
        refuser('« ' + afficher(entree.nom) + ' » fait ' + enMo(entree.decompresse) + ' une fois décompressé : '
          + enMo(limite) + ' au plus par ' + quoi + '. Le ZIP est refusé.');
      }
      total += entree.decompresse;
    }
    if (total > LIMITES.total) {
      refuser('Ce ZIP fait ' + enMo(total) + ' une fois décompressé : ' + enMo(LIMITES.total)
        + ' au plus. Il est refusé.');
    }
  }

  // --- 4 et 9. JSZip : mêmes fichiers, puis décompression sous contrôle --------------------------------------------

  async function ouvrirAvecJszip(octets, fichiers) {
    let archive = null;
    try {
      archive = await JSZip.loadAsync(octets, { checkCRC32: false, createFolders: false });
    } catch (erreur) {
      refuser(ZIP_ABIME);
    }
    const vusParJszip = Object.keys(archive.files).filter(function (nom) { return !archive.files[nom].dir; });
    if (vusParJszip.length !== fichiers.length) { refuser(ZIP_ABIME); }
    for (const entree of fichiers) {
      const objet = archive.files[entree.nom];
      if (!objet || objet.dir || (objet.unsafeOriginalName !== undefined && objet.unsafeOriginalName !== entree.nom)) {
        refuser(ZIP_ABIME);
      }
      entree.objet = objet;
    }
  }

  const TABLE_CRC = (function () {
    const table = new Int32Array(256);
    for (let n = 0; n < 256; n += 1) {
      let valeur = n;
      for (let bit = 0; bit < 8; bit += 1) { valeur = (valeur & 1) ? (0xEDB88320 ^ (valeur >>> 1)) : (valeur >>> 1); }
      table[n] = valeur;
    }
    return table;
  })();

  function crc32(octets) {
    let crc = -1;
    for (let i = 0; i < octets.length; i += 1) { crc = (crc >>> 8) ^ TABLE_CRC[(crc ^ octets[i]) & 0xFF]; }
    return (crc ^ -1) >>> 0;
  }

  function abime(entree) {
    return '« ' + afficher(entree.nom) + ' » est abîmé dans ce ZIP (contenu illisible, ou différent de ce que le ZIP '
      + 'annonce) : il est refusé. Refaites l\'export.';
  }

  // Contenu décompressé d'une entrée (copie neuve, de la taille déclarée : bornée à l'étape 3, et sans seconde copie
  // à la fin). Taille RÉELLE contrôlée pendant la décompression : dès qu'elle dépasse la taille déclarée (bombe qui
  // ment sur sa taille), la lecture s'arrête et le ZIP est refusé ; à la fin, taille et CRC-32 doivent être ceux du
  // répertoire central.
  function decompresser(entree) {
    return new Promise(function (resoudre, rejeter) {
      const contenu = new Uint8Array(entree.decompresse);
      let recu = 0;
      let fini = false;
      let flux = null;
      function arreter(message) {
        if (fini) { return; }
        fini = true;
        try { if (flux) { flux.pause(); } } catch (erreur) { /* flux déjà arrêté */ }
        rejeter(new Refus(message));
      }
      try {
        flux = entree.objet.internalStream('uint8array');
      } catch (erreur) {
        arreter(abime(entree));
        return;
      }
      flux.on('data', function (morceau) {
        if (fini) { return; }
        if (recu + morceau.length > entree.decompresse) {
          arreter('« ' + afficher(entree.nom) + ' » se décompresse plus gros que ce que le ZIP annonce : bombe de '
            + 'décompression probable. Le ZIP est refusé.');
          return;
        }
        contenu.set(morceau, recu);
        recu += morceau.length;
      });
      flux.on('error', function () { arreter(abime(entree)); });
      flux.on('end', function () {
        if (fini) { return; }
        if (recu !== entree.decompresse || crc32(contenu) !== entree.crc) { arreter(abime(entree)); return; }
        fini = true;
        resoudre(contenu);
      });
      flux.resume();
    });
  }

  // --- 5, 6 et 10. Manifeste et format ------------------------------------------------------------------------------

  const MOTIF_SHA256 = /^[0-9a-fA-F]{64}$/;

  function fichierDecritValide(fichier) {
    return Boolean(fichier) && typeof fichier === 'object' && typeof fichier.nom === 'string'
      && Number.isInteger(fichier.octets) && fichier.octets >= 0
      && typeof fichier.sha256 === 'string' && MOTIF_SHA256.test(fichier.sha256);
  }

  // Manifeste lu et vérifié dans sa forme : objet JSON, fichiers [{ nom, octets, sha256 }] sans doublon, format
  // entier (ou absent).
  function lireManifeste(contenu) {
    let manifeste = null;
    try {
      manifeste = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(contenu));
    } catch (erreur) {
      refuser(MANIFESTE_ILLISIBLE);
    }
    const forme = Boolean(manifeste) && typeof manifeste === 'object' && !Array.isArray(manifeste)
      && Array.isArray(manifeste.fichiers) && manifeste.fichiers.every(fichierDecritValide)
      && (manifeste.format === undefined || manifeste.format === null
        || (Number.isInteger(manifeste.format) && manifeste.format >= 1));
    const noms = forme ? manifeste.fichiers.map(function (fichier) { return fichier.nom; }) : [];
    if (!forme || new Set(noms).size !== noms.length) { refuser(MANIFESTE_ILLISIBLE); }
    return manifeste;
  }

  function formatDuManifeste(manifeste) {
    return manifeste && Number.isInteger(manifeste.format) ? manifeste.format : null;
  }

  function refuserSiPlusRecent(manifeste, parametres) {
    const formats = [formatDuManifeste(manifeste), parametres ? Formats.versionDeBase(parametres.lignes) : null];
    const plusRecent = formats.find(function (format) { return format !== null && format > Formats.courant; });
    if (plusRecent !== undefined) {
      refuser('Ce ZIP vient d\'une version plus récente de Prévo (format ' + plusRecent + ' des fichiers ; cette '
        + 'version lit jusqu\'au format ' + Formats.courant + ') : il est refusé. Mettez Prévo à jour, puis '
        + 'recommencez.');
    }
  }

  function hexadecimal(tampon) {
    return Array.from(new Uint8Array(tampon), function (octet) { return octet.toString(16).padStart(2, '0'); }).join('');
  }

  function outilsCrypto() { return typeof crypto !== 'undefined' && crypto ? crypto.subtle : undefined; }

  // Résumé d'un contenu décompressé : { taille, empreinte } (SHA-256 en hexadécimal ; null sans crypto.subtle).
  async function resumer(contenu) {
    const outils = outilsCrypto();
    return { taille: contenu.byteLength, empreinte: outils ? hexadecimal(await outils.digest('SHA-256', contenu)) : null };
  }

  // Chaque fichier du ZIP (hors manifeste et dossiers ; resumes : nom → résumé) est décrit par le manifeste, avec sa
  // taille et son empreinte SHA-256 exactes ; chaque fichier décrit est dans le ZIP.
  function verifierManifeste(manifeste, resumes) {
    if (!outilsCrypto()) {
      refuser('Les empreintes du manifeste ne peuvent pas être vérifiées sur cette page (il faut un contexte '
        + 'sécurisé : https, ou Prévo ouvert sur ce PC) : le ZIP est refusé.');
    }
    const decrits = new Set(manifeste.fichiers.map(function (fichier) { return fichier.nom; }));
    for (const nom of resumes.keys()) {
      if (!decrits.has(nom)) {
        refuser('« ' + afficher(nom) + ' » n\'est pas décrit par le manifeste : le ZIP a été modifié après l\'export. '
          + 'Il est refusé ; refaites l\'export.');
      }
    }
    for (const fichier of manifeste.fichiers) {
      const resume = resumes.get(fichier.nom);
      if (!resume) {
        refuser('« ' + afficher(fichier.nom) + ' », décrit par le manifeste, manque dans le ZIP : il a été modifié '
          + 'après l\'export. Il est refusé ; refaites l\'export.');
      }
      if (resume.taille !== fichier.octets || resume.empreinte !== fichier.sha256.toLowerCase()) {
        refuser('« ' + afficher(fichier.nom) + ' » ne correspond pas à son empreinte dans le manifeste : le fichier '
          + 'a été modifié ou abîmé après l\'export. Le ZIP est refusé ; refaites l\'export.');
      }
    }
  }

  // --- 7 et 8. Noms admis (11, les tables : ZipTables) ------------------------------------------------------------

  // Fichier d'une table (« equipements.csv ») → nom de la table, dans l'ordre du schéma.
  function tablesParFichier() {
    const resultat = new Map();
    for (const nomTable of Schema.nomsTables()) { resultat.set(Schema.table(nomTable).fichier, nomTable); }
    return resultat;
  }

  // Genre d'une entrée admise ('table', 'document', 'manifeste', 'dossier'), ou null.
  function genreDe(entree, fichiersTables) {
    if (entree.dossier) { return entree.nom === DOSSIER_DOCUMENTS ? 'dossier' : null; }
    if (entree.nom === NOM_MANIFESTE) { return 'manifeste'; }
    if (fichiersTables.has(entree.nom)) { return 'table'; }
    const document = entree.nom.startsWith(DOSSIER_DOCUMENTS)
      && nomDocumentAdmis(entree.nom.slice(DOSSIER_DOCUMENTS.length));
    return document ? 'document' : null;
  }

  function controlerNomsAdmis(entrees, fichiersTables) {
    const refusees = entrees.filter(function (entree) { return genreDe(entree, fichiersTables) === null; });
    if (refusees.length) {
      const autres = refusees.length > 1 ? ' (et ' + enChiffres(refusees.length - 1) + ' autre(s))' : '';
      refuser('Ce ZIP contient un fichier qui ne vient pas d\'un export de Prévo : « ' + afficher(refusees[0].nom)
        + ' »' + autres + '. Seuls sont admis les fichiers CSV des tables (à la racine du ZIP), le dossier '
        + 'documents/ (documents aux noms autorisés) et manifeste.json. Le ZIP est refusé.');
    }
    if (!entrees.some(function (entree) { return genreDe(entree, fichiersTables) === 'table'; })) {
      refuser('Ce ZIP ne contient aucun fichier CSV de table (equipements.csv, ordres_travail.csv…) : ce n\'est pas '
        + 'un export de données de Prévo. Il est refusé.');
    }
  }

  // Documents cités par la base mais absents de l'export (manifeste.manquants, facultatif).
  function problemesManquants(manifeste) {
    const manquants = manifeste && Array.isArray(manifeste.manquants) ? manifeste.manquants : [];
    return manquants.filter(function (nom) { return typeof nom === 'string'; }).map(function (nom) {
      return probleme('attention', 'document', null, 'Le document « ' + afficher(nom) + ' » était introuvable lors '
        + 'de l\'export : il n\'est pas dans le ZIP.');
    });
  }

  // --- Lecture complète --------------------------------------------------------------------------------------------

  function exigerDependances() {
    const manquantes = [['JSZip', typeof JSZip], ['Schema', typeof Schema], ['Formats', typeof Formats],
      ['Donnees', typeof Donnees], ['ZipTables', typeof ZipTables]]
      .filter(function (paire) { return paire[1] === 'undefined'; });
    if (manquantes.length) {
      throw new Error('ZipLecture : à charger après ' + manquantes.map(function (paire) { return paire[0]; }).join(', ')
        + ' (ordre de index.html).');
    }
  }

  // Répertoire central lu et contrôlé (étapes 2 et 3) ; une lecture hors du fichier (positions fausses) : ZIP abîmé.
  function repertoireControle(octets) {
    try {
      const repertoire = lireRepertoire(octets);
      controlerEntrees(repertoire);
      return repertoire;
    } catch (erreur) {
      if (erreur instanceof RangeError) { refuser(ZIP_ABIME); }
      throw erreur;
    }
  }

  const DOCUMENTS_DES_RESULTATS = new WeakMap();   // résultat accepté → documents (leurs entrées gardent le ZIP)
  // Mesure de la dernière lecture (tests) : ZIP, racine (tables, manifeste), documents gardés à la fois, plus gros.
  let memoire = { zip: 0, racine: 0, documentsGardesMax: 0, documentMax: 0 };

  // Document décompressé et résumé dans sa propre trame (une fois finie, plus rien ne le garde) → résumé.
  async function resumerDocument(entree) {
    const contenu = await decompresser(entree);
    memoire.documentMax = Math.max(memoire.documentMax, contenu.byteLength);
    return resumer(contenu);
  }

  async function lireEtControler(source) {
    const octets = await lireOctets(source);
    memoire = { zip: octets.length, racine: 0, documentsGardesMax: 0, documentMax: 0 };
    const repertoire = repertoireControle(octets);
    const fichiers = repertoire.entrees.filter(function (entree) { return !entree.dossier; });
    await ouvrirAvecJszip(octets, fichiers);
    const parNom = new Map(fichiers.map(function (entree) { return [entree.nom, entree]; }));
    const contenus = new Map();               // fichiers de la racine (LIMITES.racine au plus chacun), gardés
    async function contenuDe(nom) {
      if (!contenus.has(nom)) { contenus.set(nom, await decompresser(parNom.get(nom))); }
      return contenus.get(nom);
    }
    const manifeste = parNom.has(NOM_MANIFESTE) ? lireManifeste(await contenuDe(NOM_MANIFESTE)) : null;
    const fichierParametres = Schema.table('parametres').fichier;
    const parametres = parNom.has(fichierParametres)
      ? Donnees.csv.analyser('parametres', await contenuDe(fichierParametres)) : null;
    refuserSiPlusRecent(manifeste, parametres);
    const fichiersTables = tablesParFichier();
    controlerNomsAdmis(repertoire.entrees, fichiersTables);
    // Fichiers résumés dans l'ordre d'avant (parametres.csv, puis le ZIP) ; un document à la fois, oublié aussitôt.
    const resumes = new Map();
    const documents = new Map();              // seconde passe : nom sans « documents/ » → { entree, resume }
    let gardes = 0;                           // documents décompressés gardés
    for (const nom of [fichierParametres].concat(Array.from(parNom.keys()))) {
      if (nom === NOM_MANIFESTE || resumes.has(nom) || !parNom.has(nom)) { continue; }
      const document = genreDe(parNom.get(nom), fichiersTables) === 'document';
      memoire.documentsGardesMax = Math.max(memoire.documentsGardesMax, gardes += document ? 1 : 0);
      resumes.set(nom, document ? await resumerDocument(parNom.get(nom)) : await resumer(await contenuDe(nom)));
      gardes -= document ? 1 : 0;             // document oublié : relu par lireDocument
      if (document) {
        documents.set(nom.slice(DOSSIER_DOCUMENTS.length), { entree: parNom.get(nom), resume: resumes.get(nom) });
      }
    }
    for (const contenu of contenus.values()) { memoire.racine += contenu.byteLength; }
    if (manifeste) { verifierManifeste(manifeste, resumes); }
    if (manifeste && manifeste.documents === 'exclus' && documents.size) {
      refuser('Le manifeste dit que ce ZIP ne contient pas les documents (données seules), mais il en contient : il a '
        + 'été modifié après l\'export. Il est refusé ; refaites l\'export.');
    }

    // 11 (après le manifeste : un CSV abîmé n'est accepté que marqué, à l'empreinte vérifiée, T213).
    const lues = ZipTables.lire(contenus, fichiersTables, parametres ? { parametres: parametres } : {}, manifeste);
    if (lues.refus) { refuser(lues.refus); }
    const resultat = {
      ok: true, refus: null, format: Formats.courant, formatOrigine: lues.formatOrigine, migre: lues.migre,
      manifeste: manifeste, tables: lues.tables, absentes: lues.absentes, abimes: lues.abimes,
      documents: Array.from(documents, function (paire) { return Object.assign({ nom: paire[0] }, paire[1].resume); }),
      problemes: lues.problemes.concat(problemesManquants(manifeste)),
    };
    DOCUMENTS_DES_RESULTATS.set(resultat, documents);
    return resultat;
  }

  // Seconde passe (voir l'en-tête) : document `nom` (sans « documents/ ») d'un résultat accepté, relu et revérifié ;
  // taille et CRC-32 le sont pendant la décompression. Le contenu rendu (copie neuve) est à oublier après usage.
  async function lireDocument(lu, nom) {
    const document = (DOCUMENTS_DES_RESULTATS.get(lu) || new Map()).get(nom);
    if (!document) {
      throw new Error('ZipLecture.lireDocument : « ' + afficher(String(nom)) + ' » n\'est pas un document d\'un ZIP '
        + 'accepté par ZipLecture.lire.');
    }
    const contenu = await decompresser(document.entree);
    if (document.resume.empreinte !== null && (await resumer(contenu)).empreinte !== document.resume.empreinte) {
      refuser('« ' + afficher(document.entree.nom) + ' » a changé depuis le contrôle du ZIP (son empreinte ne '
        + 'correspond plus) : il n\'est pas importé.');
    }
    return contenu;
  }

  // Lit et contrôle un ZIP de données (voir l'en-tête) ; rien n'est écrit nulle part.
  async function lire(source) {
    exigerDependances();
    try {
      return await lireEtControler(source);
    } catch (erreur) {
      if (erreur instanceof Refus) { return { ok: false, refus: erreur.message }; }
      throw erreur;
    }
  }

  return {
    lire: lire,
    lireDocument: lireDocument,
    memoire: function () { return Object.assign({}, memoire); },
    nomDocumentAdmis: nomDocumentAdmis,
    LIMITES: LIMITES,
    enMo: enMo,                       // « 50 Mo », « 1 Go » : messages de l'export (ZipDonnees) comme de l'import
    // Copie de la règle de serveur.py, exposée pour le test de cohérence.
    REGLE_DOCUMENTS: Object.freeze({ motif: MOTIF_NOM_DOCUMENT.source, extensions: EXTENSIONS_DOCUMENTS,
      reserves: NOMS_RESERVES_WINDOWS }),
  };
})();
