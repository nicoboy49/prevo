'use strict';
// ZipFlux : lecture et écriture d'un ZIP PAR MORCEAUX, module bas niveau sans écran ni stockage (chantier « socle de
// données », T215 « ZIP par morceaux », morceau 1 : T226). L'import (T227) et l'export (T228) s'en servent ensuite à la
// place de JSZip, qui tient tout le ZIP en mémoire (5 à 6 fois sa taille, mesure T212). Ordre de chargement : §15.1,
// juste avant zip-lecture.js. Décisions de Nicolas : pas de JSZip en secours (un navigateur sans « deflate-raw »
// reçoit MESSAGE_NAVIGATEUR) ; jamais de ZIP64 à l'écriture (4 Go au plus).
//
// ZipFlux.disponible() → vrai si CompressionStream et DecompressionStream acceptent « deflate-raw ».
// ZipFlux.ErreurZip : erreur de ZIP, { code, message (français), nom (entrée en cause, ou null) } ; code :
//   'navigateur' (pas de « deflate-raw » : message MESSAGE_NAVIGATEUR), 'format' (ZIP illisible, en plusieurs
//   parties, chiffré, méthode inconnue, données hors du fichier), 'bombe' (taille réelle au-delà de la taille
//   déclarée), 'abime' (taille finale ou CRC-32 faux, flux deflate en erreur), 'trop-gros' (écriture au-delà de
//   4 Go ou de 65 534 entrées). Les messages 'format' reprennent ceux de zip-lecture.js. Une erreur de lecture du
//   fichier lui-même (NotReadableError, NotFoundError : fichier changé ou retiré) passe telle quelle.
// ZipFlux.crc32(octets, crcPrecedent) : CRC-32 par morceaux (crc32(b, crc32(a)) = crc32 de a puis b).
//
// Lecture, depuis un Blob ou un File, SANS JAMAIS LIRE LE FICHIER ENTIER (Blob.slice seulement) :
//   lireRepertoire(blob) → Promise de { entrees, debut, taille, nombre } (debut, taille, nombre : position, taille
//     et nombre d'entrées du répertoire central) ; entrees : [{ nom, octetsNom, dossier, drapeaux, methode, crc,
//     compresse, decompresse, local }], comme lireRepertoire de zip-lecture.js (nom décodé en UTF-8, null si les
//     octets n'en sont pas ; octetsNom : les octets bruts). Fin du répertoire cherchée dans les 65 557 derniers
//     octets, fin ZIP64 lue (localisateur, puis fin ZIP64), répertoire central lu d'une seule tranche. N'a pas
//     besoin des flux : fonctionne même si disponible() est faux. lireRepertoire(blob, controlerFin) : controlerFin
//     ({ debut, taille, nombre }) est appelée AVANT la lecture du répertoire, et peut lever (T227 : zip-lecture.js y
//     refuse un nombre d'entrées trop grand, sans lire ni analyser le répertoire).
//   positionDonnees(blob, entree, limite) → Promise de la position des données d'une entrée (en-tête local lu :
//     30 octets) ; 'format' si l'en-tête ou les données sortent de [0, limite) (limite : blob.size par défaut ; le
//     début du répertoire central pour le contrôle 2 de zip-lecture.js).
//   contenu(blob, entree) → Promise de Uint8Array décompressé : méthode 0 (stockée) ou 8 (deflate, par
//     DecompressionStream sur blob.slice(...).stream(), en tranches de 16 Ko : au plus 16,5 Mo de sortie par étape,
//     même pour une bombe) ; arrêt dès que la taille reçue dépasse entree.decompresse ('bombe') ; à la fin, taille
//     égale et CRC-32 juste, sinon 'abime'. Le tableau rendu a la taille DÉCLARÉE, allouée d'emblée : l'appelant la
//     borne avant (contrôle 3 de zip-lecture.js).
// Écriture en Blob composé, sans descripteur de données ni entrée de dossier, drapeau UTF-8 (bit 11) :
//   const ecrivain = ZipFlux.ecrivain({ date }) (date : Date, maintenant par défaut ; date et heure DOS en heure
//     locale, celle que montre l'Explorateur Windows ; limites : réservé aux tests, voir LIMITES) ;
//   await ecrivain.ajouter(nom, octets, { stocker }) : octets Uint8Array, ArrayBuffer ou Blob ; l'entrée est lue en
//     flux, CRC-32 et taille mesurés au passage, compressée (CompressionStream « deflate-raw ») ou stockée, et versée
//     dans un Blob : CRC-32 et tailles sont connus avant d'écrire l'en-tête local. Appels mis en file (ordre gardé) ;
//     au-delà des LIMITES : 'trop-gros', et l'entrée n'est pas ajoutée (le ZIP reste bon sans elle) ;
//   ecrivain.taille : octets écrits jusque-là (tout le ZIP après terminer) ;
//   ecrivain.terminer() → Blob du ZIP (répertoire central + fin), type application/zip.
//   Mêmes entrées, même date, même navigateur : mêmes octets.
// ZipFlux.verifierLimites({ entrees, total, compresse, decompresse }, limites) : contrôle des 4 Go, exposé pour les
//   tests (rien à produire) ; LIMITES : octets 0xFFFFFFFE, entrees 65 534 (0xFFFFFFFF et 0xFFFF annoncent un ZIP64).
// Si disponible() est faux : contenu et ajouter rejettent, ecrivain lève, une ErreurZip 'navigateur'.

const ZipFlux = (() => {

  const MESSAGE_NAVIGATEUR = 'Ce navigateur est trop ancien pour lire ou écrire un ZIP de Prévo. Mettez-le à jour '
    + '(Chrome, Edge, Firefox ou Safari récents), ou copiez simplement votre dossier de données pour le sauvegarder ou '
    + 'le transporter.';
  const PAS_UN_ZIP = 'Ce fichier n\'est pas un ZIP lisible. Choisissez le fichier ZIP exporté par Prévo '
    + '(« prevo-export-AAAA-MM-JJ.zip »).';
  const ZIP_ABIME = 'Ce ZIP est abîmé (structure illisible ou incohérente) : il est refusé. Refaites l\'export, '
    + 'ou choisissez un autre fichier.';
  const PLUSIEURS_PARTIES = 'Ce ZIP est en plusieurs parties : il est refusé. Choisissez le ZIP exporté par Prévo, '
    + 'en un seul fichier.';
  const TROP_GROS = 'Le ZIP dépasserait 4 Go, la plus grande taille que Prévo écrit. Exportez les données seules, ou '
    + 'copiez simplement votre dossier de données pour le sauvegarder ou le transporter.';
  const TROP_D_ENTREES = 'Le ZIP aurait plus de 65 534 fichiers, le plus grand nombre que Prévo écrit. Copiez '
    + 'simplement votre dossier de données pour le sauvegarder ou le transporter.';

  const SIGNATURES = Object.freeze({ fin: 0x06054b50, localisateur64: 0x07064b50, fin64: 0x06064b50,
    centrale: 0x02014b50, locale: 0x04034b50 });
  const MAX_16 = 0xFFFF;
  const MAX_32 = 0xFFFFFFFF;
  const CHAMP_ZIP64 = 0x0001;
  const ATTRIBUT_DOSSIER = 0x10;
  const DRAPEAU_CHIFFRE = 0x0001;
  const DRAPEAU_UTF8 = 0x0800;
  const VERSION = 20;                       // 2.0 : deflate (version requise et version de l'auteur, hôte MS-DOS)
  const TRANCHE_DEFLATE = 16 * 1024;        // entrée du décompresseur, par étape (deflate : 1 032 fois au plus)
  // Sans ZIP64 : 0xFFFFFFFF dans une taille ou une position, 0xFFFF dans le nombre d'entrées, renvoient à une fin
  // ZIP64 (zip-lecture.js l'exigerait). Le plus grand ZIP écrit : 4 Go moins 2 octets, 65 534 entrées.
  const LIMITES = Object.freeze({ octets: MAX_32 - 1, entrees: MAX_16 - 1 });

  const decodeurNoms = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true });
  const encodeurNoms = new TextEncoder();

  // --- Erreurs -------------------------------------------------------------------------------------------------------

  class ErreurZip extends Error {
    constructor(code, message, nom) {
      super(message);
      this.name = 'ErreurZip';
      this.code = code;
      this.nom = nom === undefined ? null : nom;
    }
  }

  function estControle(code) { return code < 0x20 || (code >= 0x7f && code <= 0x9f); }

  // Nom d'entrée affichable dans un message : caractères de contrôle remplacés par « ? », 100 caractères au plus.
  function afficher(nom) {
    if (typeof nom !== 'string') { return '?'; }
    let texte = '';
    for (let i = 0; i < nom.length && i < 100; i += 1) { texte += estControle(nom.charCodeAt(i)) ? '?' : nom[i]; }
    return nom.length > 100 ? texte + '…' : texte;
  }

  function erreurFormat(message, nom) { return new ErreurZip('format', message || ZIP_ABIME, nom); }

  function erreurAbime(entree) {
    return new ErreurZip('abime', '« ' + afficher(entree.nom) + ' » est abîmé dans ce ZIP (contenu illisible, ou '
      + 'différent de ce que le ZIP annonce) : il est refusé. Refaites l\'export.', entree.nom);
  }

  function erreurBombe(entree) {
    return new ErreurZip('bombe', '« ' + afficher(entree.nom) + ' » se décompresse plus gros que ce que le ZIP '
      + 'annonce : bombe de décompression probable. Le ZIP est refusé.', entree.nom);
  }

  // --- Navigateur ----------------------------------------------------------------------------------------------------

  // Vrai si le constructeur existe et accepte « deflate-raw » (il lève sur un format inconnu).
  function accepteDeflateBrut(Constructeur) {
    if (typeof Constructeur !== 'function') { return false; }
    try {
      new Constructeur('deflate-raw');
      return true;
    } catch (erreur) {
      return false;
    }
  }

  // Évalué à chaque appel (un test remplace les flux avant ou après le chargement).
  function disponible() {
    return accepteDeflateBrut(typeof CompressionStream === 'undefined' ? undefined : CompressionStream)
      && accepteDeflateBrut(typeof DecompressionStream === 'undefined' ? undefined : DecompressionStream);
  }

  function exigerFlux() {
    if (!disponible()) { throw new ErreurZip('navigateur', MESSAGE_NAVIGATEUR); }
  }

  // --- CRC-32 (polynôme 0xEDB88320, celui du ZIP) --------------------------------------------------------------------

  const TABLE_CRC = (() => {
    const table = new Int32Array(256);
    for (let n = 0; n < 256; n += 1) {
      let valeur = n;
      for (let bit = 0; bit < 8; bit += 1) { valeur = (valeur & 1) ? (0xEDB88320 ^ (valeur >>> 1)) : (valeur >>> 1); }
      table[n] = valeur;
    }
    return table;
  })();

  // CRC-32 de `octets` à la suite de `crcPrecedent` (0, ou rien, pour un premier morceau).
  function crc32(octets, crcPrecedent) {
    let crc = ((crcPrecedent || 0) ^ -1);
    for (let i = 0; i < octets.length; i += 1) { crc = (crc >>> 8) ^ TABLE_CRC[(crc ^ octets[i]) & 0xFF]; }
    return (crc ^ -1) >>> 0;
  }

  // --- Lecture : tranches du fichier ---------------------------------------------------------------------------------

  function lecteur(octets) {
    const vue = new DataView(octets.buffer, octets.byteOffset, octets.byteLength);
    return {
      u16: (position) => vue.getUint16(position, true),
      u32: (position) => vue.getUint32(position, true),
      u64: (position) => vue.getUint32(position, true) + vue.getUint32(position + 4, true) * 0x100000000,
    };
  }

  // Octets [debut, debut + longueur) du fichier, et eux seuls (Blob.slice) ; 'format' s'ils sortent du fichier.
  async function lireTranche(blob, debut, longueur) {
    if (!(debut >= 0 && longueur >= 0 && debut + longueur <= blob.size)) { throw erreurFormat(); }
    const octets = new Uint8Array(await blob.slice(debut, debut + longueur).arrayBuffer());
    if (octets.length !== longueur) { throw erreurFormat(); }
    return octets;
  }

  // Nom d'une entrée : UTF-8 (comme JSZip et zip-lecture.js) ; null si les octets n'en sont pas.
  function decoderNom(octetsNom) {
    try { return decodeurNoms.decode(octetsNom); } catch (erreur) { return null; }
  }

  // Position, taille et nombre d'entrées du répertoire central (fin ZIP64 comprise), d'après la DERNIÈRE signature
  // de fin trouvée dans les 65 557 derniers octets (22 octets de fin + 65 535 de commentaire au plus).
  async function lireFin(blob) {
    if (blob.size < 22) { throw erreurFormat(PAS_UN_ZIP); }
    const debutQueue = Math.max(0, blob.size - 22 - MAX_16);
    const queue = await lireTranche(blob, debutQueue, blob.size - debutQueue);
    const lire = lecteur(queue);
    let fin = queue.length - 22;
    while (fin >= 0 && lire.u32(fin) !== SIGNATURES.fin) { fin -= 1; }
    if (fin < 0) { throw erreurFormat(PAS_UN_ZIP); }
    if (lire.u16(fin + 4) !== 0 || lire.u16(fin + 6) !== 0) { throw erreurFormat(PLUSIEURS_PARTIES); }
    const resultat = { nombre: lire.u16(fin + 10), taille: lire.u32(fin + 12), debut: lire.u32(fin + 16) };
    if (resultat.nombre === MAX_16 || resultat.taille === MAX_32 || resultat.debut === MAX_32) {
      const positionFin = debutQueue + fin;
      if (positionFin < 20) { throw erreurFormat(); }
      const localisateur = lecteur(await lireTranche(blob, positionFin - 20, 20));
      if (localisateur.u32(0) !== SIGNATURES.localisateur64) { throw erreurFormat(); }
      const fin64 = lecteur(await lireTranche(blob, localisateur.u64(8), 56));
      if (fin64.u32(0) !== SIGNATURES.fin64) { throw erreurFormat(); }
      resultat.nombre = fin64.u64(32);
      resultat.taille = fin64.u64(40);
      resultat.debut = fin64.u64(48);
    }
    return resultat;
  }

  // Tailles et position sur 64 bits (champ extra « ZIP64 ») quand le champ sur 32 bits est saturé.
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

  // Répertoire central (voir l'en-tête), lu d'une seule tranche, avant toute décompression.
  async function lireRepertoire(blob, controlerFin) {
    const fin = await lireFin(blob);
    if (controlerFin) { controlerFin({ debut: fin.debut, taille: fin.taille, nombre: fin.nombre }); }
    const octets = await lireTranche(blob, fin.debut, fin.taille);
    const lire = lecteur(octets);
    const entrees = [];
    let position = 0;
    for (let numero = 0; numero < fin.nombre; numero += 1) {
      if (position + 46 > octets.length || lire.u32(position) !== SIGNATURES.centrale) { throw erreurFormat(); }
      const longueurNom = lire.u16(position + 28);
      const longueurExtra = lire.u16(position + 30);
      const suivante = position + 46 + longueurNom + longueurExtra + lire.u16(position + 32);
      if (suivante > octets.length) { throw erreurFormat(); }
      const octetsNom = octets.slice(position + 46, position + 46 + longueurNom);
      const nom = decoderNom(octetsNom);
      const entree = {
        nom: nom,
        octetsNom: octetsNom,
        // Dossier : nom en « / » ou attribut « dossier » (même règle que JSZip et zip-lecture.js).
        dossier: nom !== null && (nom.endsWith('/') || (lire.u32(position + 38) & ATTRIBUT_DOSSIER) !== 0),
        drapeaux: lire.u16(position + 8), methode: lire.u16(position + 10), crc: lire.u32(position + 16),
        compresse: lire.u32(position + 20), decompresse: lire.u32(position + 24), local: lire.u32(position + 42),
      };
      lireZip64(lire, position + 46 + longueurNom, longueurExtra, entree);
      entrees.push(entree);
      position = suivante;
    }
    return { entrees: entrees, debut: fin.debut, taille: fin.taille, nombre: fin.nombre };
  }

  // Position des données d'une entrée, d'après son en-tête local (30 octets + nom + extra).
  async function positionDonnees(blob, entree, limite) {
    const borne = limite === undefined ? blob.size : Math.min(limite, blob.size);
    if (!(entree.local >= 0 && entree.local + 30 <= borne)) { throw erreurFormat(ZIP_ABIME, entree.nom); }
    const lire = lecteur(await lireTranche(blob, entree.local, 30));
    if (lire.u32(0) !== SIGNATURES.locale) { throw erreurFormat(ZIP_ABIME, entree.nom); }
    const donnees = entree.local + 30 + lire.u16(26) + lire.u16(28);
    if (!(entree.compresse >= 0 && donnees + entree.compresse <= borne)) { throw erreurFormat(ZIP_ABIME, entree.nom); }
    return donnees;
  }

  // Coupe chaque morceau en tranches de TRANCHE_DEFLATE : le décompresseur, qui respecte la contre-pression entre deux
  // morceaux, produit alors au plus 1 032 fois une tranche avant que contenu() ne relise la taille reçue.
  function decoupeur() {
    return new TransformStream({
      transform(morceau, controleur) {
        for (let i = 0; i < morceau.length; i += TRANCHE_DEFLATE) {
          controleur.enqueue(morceau.subarray(i, i + TRANCHE_DEFLATE));
        }
      },
    });
  }

  // Erreur de lecture du fichier lui-même (il a changé ou disparu) : elle passe telle quelle, ce n'est pas le ZIP.
  function estErreurDeFichier(erreur) {
    return Boolean(erreur) && (erreur.name === 'NotReadableError' || erreur.name === 'NotFoundError');
  }

  // Contenu décompressé d'une entrée (voir l'en-tête).
  async function contenu(blob, entree) {
    exigerFlux();
    if (entree.drapeaux & DRAPEAU_CHIFFRE) {
      throw erreurFormat('« ' + afficher(entree.nom) + ' » est chiffré dans ce ZIP : un export de Prévo ne l\'est '
        + 'jamais. Il est refusé.', entree.nom);
    }
    if (entree.methode !== 0 && entree.methode !== 8) {
      throw erreurFormat('« ' + afficher(entree.nom) + ' » est compressé par une méthode que Prévo ne lit pas '
        + '(méthode ' + entree.methode + ') : ZIP refusé. Refaites l\'export.', entree.nom);
    }
    const debut = await positionDonnees(blob, entree);
    let flux = blob.slice(debut, debut + entree.compresse).stream();
    if (entree.methode === 8) { flux = flux.pipeThrough(decoupeur()).pipeThrough(new DecompressionStream('deflate-raw')); }
    const lecture = flux.getReader();
    const sortie = new Uint8Array(entree.decompresse);
    let recu = 0;
    let crc = 0;
    try {
      for (;;) {
        const morceau = await lecture.read();
        if (morceau.done) { break; }
        if (recu + morceau.value.length > entree.decompresse) {
          lecture.cancel().catch(() => {});     // arrête la lecture du fichier et la décompression
          throw erreurBombe(entree);
        }
        sortie.set(morceau.value, recu);
        crc = crc32(morceau.value, crc);
        recu += morceau.value.length;
      }
    } catch (erreur) {
      if (erreur instanceof ErreurZip || estErreurDeFichier(erreur)) { throw erreur; }
      throw erreurAbime(entree);                 // flux deflate illisible, tronqué, ou suivi d'autres octets
    }
    if (recu !== entree.decompresse || crc !== entree.crc) { throw erreurAbime(entree); }
    return sortie;
  }

  // --- Écriture ------------------------------------------------------------------------------------------------------

  // Contrôle des limites d'un ZIP sans ZIP64 (voir l'en-tête) : mesures { entrees, total, compresse, decompresse },
  // chacune facultative ; limites : LIMITES par défaut ({ octets, entrees }).
  function verifierLimites(mesures, limites) {
    const bornes = Object.assign({}, LIMITES, limites || {});
    if (mesures.entrees !== undefined && !(mesures.entrees <= bornes.entrees)) {
      throw new ErreurZip('trop-gros', TROP_D_ENTREES);
    }
    for (const cle of ['total', 'compresse', 'decompresse']) {
      if (mesures[cle] !== undefined && !(mesures[cle] <= bornes.octets)) { throw new ErreurZip('trop-gros', TROP_GROS); }
    }
  }

  // Date et heure DOS (heure locale, secondes paires), bornées à 1980-2107.
  function dateDos(date) {
    const annee = date.getFullYear();
    if (annee < 1980) { return { heure: 0, jour: (1 << 5) | 1 }; }
    if (annee > 2107) { return { heure: (23 << 11) | (59 << 5) | 29, jour: (127 << 9) | (12 << 5) | 31 }; }
    return {
      heure: (date.getHours() << 11) | (date.getMinutes() << 5) | (date.getSeconds() >> 1),
      jour: ((annee - 1980) << 9) | ((date.getMonth() + 1) << 5) | date.getDate(),
    };
  }

  function blobDe(octets) {
    if (typeof Blob !== 'undefined' && octets instanceof Blob) { return octets; }
    if (octets instanceof ArrayBuffer || ArrayBuffer.isView(octets)) { return new Blob([octets]); }
    throw new TypeError('ZipFlux : contenu attendu en Uint8Array, ArrayBuffer ou Blob.');
  }

  // Lit la source en flux : CRC-32 et taille mesurés au passage, puis compression (ou rien) ; résultat versé dans un
  // Blob, géré par le navigateur, hors de la mémoire JavaScript.
  async function preparer(source, stocker) {
    const mesure = { crc: 0, taille: 0 };
    let flux = source.stream().pipeThrough(new TransformStream({
      transform(morceau, controleur) {
        mesure.crc = crc32(morceau, mesure.crc);
        mesure.taille += morceau.length;
        controleur.enqueue(morceau);
      },
    }));
    if (!stocker) { flux = flux.pipeThrough(new CompressionStream('deflate-raw')); }
    const donnees = await new Response(flux).blob();
    return { donnees: donnees, crc: mesure.crc, taille: mesure.taille };
  }

  // En-tête local (30 octets + nom) ou entrée du répertoire central (46 octets + nom), sans extra ni commentaire.
  function entete(central, champs) {
    const octets = new Uint8Array((central ? 46 : 30) + champs.nom.length);
    const vue = new DataView(octets.buffer);
    const d = central ? 2 : 0;                   // décalage des champs communs dans l'entrée centrale
    vue.setUint32(0, central ? SIGNATURES.centrale : SIGNATURES.locale, true);
    if (central) { vue.setUint16(4, VERSION, true); }
    vue.setUint16(4 + d, VERSION, true);
    vue.setUint16(6 + d, DRAPEAU_UTF8, true);
    vue.setUint16(8 + d, champs.methode, true);
    vue.setUint16(10 + d, champs.heure, true);
    vue.setUint16(12 + d, champs.jour, true);
    vue.setUint32(14 + d, champs.crc, true);
    vue.setUint32(18 + d, champs.compresse, true);
    vue.setUint32(22 + d, champs.decompresse, true);
    vue.setUint16(26 + d, champs.nom.length, true);
    // Extra (28 + d), puis pour l'entrée centrale : commentaire, disque, attributs internes et externes, à zéro.
    if (central) { vue.setUint32(42, champs.local, true); }
    octets.set(champs.nom, central ? 46 : 30);
    return octets;
  }

  // Écrivain de ZIP (voir l'en-tête).
  function ecrivain(options) {
    exigerFlux();
    const reglages = options || {};
    const date = reglages.date === undefined ? new Date() : reglages.date;
    if (!(date instanceof Date) || isNaN(date.getTime())) { throw new TypeError('ZipFlux.ecrivain : date invalide.'); }
    const limites = Object.assign({}, LIMITES, reglages.limites || {});
    const dos = dateDos(date);
    const parties = [];                          // en-têtes locaux et données, dans l'ordre du fichier
    const centrales = [];                        // entrées du répertoire central
    let taille = 0;                              // octets des parties
    let tailleCentrale = 0;
    let enCours = 0;
    let file = Promise.resolve();
    let zip = null;

    async function ajouterMaintenant(nom, octets, choix) {
      if (zip) { throw new Error('ZipFlux : ajouter() après terminer().'); }
      exigerFlux();
      if (typeof nom !== 'string' || nom === '') { throw new TypeError('ZipFlux : nom d\'entrée attendu.'); }
      const octetsNom = encodeurNoms.encode(nom);
      if (octetsNom.length > MAX_16) { throw new ErreurZip('trop-gros', TROP_GROS, nom); }
      const source = blobDe(octets);
      verifierLimites({ entrees: centrales.length + 1, decompresse: source.size }, limites);
      const stocker = Boolean(choix) && choix.stocker === true;
      const prepare = await preparer(source, stocker);
      const champs = { nom: octetsNom, methode: stocker ? 0 : 8, heure: dos.heure, jour: dos.jour, crc: prepare.crc,
        compresse: prepare.donnees.size, decompresse: prepare.taille, local: taille };
      const local = entete(false, champs);
      const centrale = entete(true, champs);
      // Tout le ZIP une fois terminé (répertoire central et fin de 22 octets compris) : ainsi terminer() ne lève pas.
      verifierLimites({ entrees: centrales.length + 1, compresse: champs.compresse, decompresse: champs.decompresse,
        total: taille + local.length + champs.compresse + tailleCentrale + centrale.length + 22 }, limites);
      parties.push(local, prepare.donnees);
      centrales.push(centrale);
      taille += local.length + champs.compresse;
      tailleCentrale += centrale.length;
    }

    return {
      ajouter(nom, octets, choix) {
        enCours += 1;
        const resultat = file.then(() => ajouterMaintenant(nom, octets, choix));
        file = resultat.then(() => {}, () => {});
        return resultat.finally(() => { enCours -= 1; });
      },
      get taille() { return zip ? zip.size : taille; },
      terminer() {
        if (zip) { return zip; }
        if (enCours > 0) { throw new Error('ZipFlux : terminer() avant la fin d\'un ajouter().'); }
        const fin = new Uint8Array(22);
        const vue = new DataView(fin.buffer);
        vue.setUint32(0, SIGNATURES.fin, true);
        vue.setUint16(8, centrales.length, true);
        vue.setUint16(10, centrales.length, true);
        vue.setUint32(12, tailleCentrale, true);
        vue.setUint32(16, taille, true);
        zip = new Blob(parties.concat(centrales, [fin]), { type: 'application/zip' });
        return zip;
      },
    };
  }

  return {
    disponible,
    MESSAGE_NAVIGATEUR,
    ErreurZip,
    LIMITES,
    crc32,
    lireRepertoire,
    positionDonnees,
    contenu,
    ecrivain,
    verifierLimites,
  };
})();
