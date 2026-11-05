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
// Lecture PAR MORCEAUX (T227, morceau 2 de T215) : le ZIP n'est jamais lu en entier ni gardé ; ZipFlux (zip-flux.js) en
// lit des tranches (Blob.slice : fin et répertoire central, en-têtes locaux, données d'une entrée à la fois, en flux).
// Un File ou un Blob est lu tel quel ; un ArrayBuffer ou une vue typée, sans copie (chaque tranche lue devient un
// Blob).
// Navigateur sans « deflate-raw » (ZipFlux.disponible() faux) : refus ZipFlux.MESSAGE_NAVIGATEUR avant toute lecture,
// pas de JSZip en secours (décision de Nicolas). Fichier illisible (changé, retiré) : refus « Lecture du fichier
// impossible ».
// Deux passes (T205), mémoire bornée aux tables + UN document : lire contrôle chaque document (étapes 9, 10) puis
// l'oublie ; lireDocument(lu, nom) le relit du même fichier (taille, CRC-32, empreinte revérifiés) → Promise de
// Uint8Array, rejetée (Error au message clair) s'il a changé ou n'est plus lisible. memoire() : mesure (tests).
//
// Contrôles, dans l'ordre (le premier qui échoue donne le refus) : (1) taille du fichier avant de le lire ;
// (2) répertoire central lu par ZipFlux, noms bruts (rien d'assaini ni de fusionné) : nombre d'entrées (avant de lire
// le répertoire), noms hostiles (absolu « / » ou « C: », segment « .. » ou « . », barre inverse, segment vide,
// caractère de contrôle, UTF-8 invalide), doublons (casse ignorée), entrée chiffrée, méthode autre que « stocké » et
// « deflate », données hors du fichier (ZipFlux.positionDonnees, bornée au répertoire central) ; (3) tailles
// DÉCLARÉES, avant toute décompression : taux de compression (au-delà de 1 Mo décompressé : en dessous, aucune bombe
// possible), fichier à la racine (CSV, manifeste), document, total ; (4) retiré (T227 : il vérifiait que JSZip voyait
// les mêmes fichiers, et JSZip ne lit plus rien) ; (5) manifeste illisible ; (6) format plus récent que Formats.courant
// (manifeste, ou version_schema de parametres.csv) ; (7) noms admis : <table>.csv à la racine (table de Schema),
// documents/<nom> au nom admis par serveur.py, manifeste.json, le dossier documents/ lui-même, rien d'autre ;
// (8) au moins un CSV de table ; (9) décompression (ZipFlux.contenu) : taille RÉELLE contrôlée pendant (arrêt dès
// qu'elle dépasse la taille déclarée) et après (égale, CRC-32 juste) ; (10) manifeste : chaque fichier y figure avec
// sa taille et son empreinte SHA-256, et réciproquement ; un manifeste « documents »: « exclus » (export « données
// seules », T214) et des documents dans le ZIP : refusé ; (11) CSV illisible (format 0 : des colonnes du format 1
// manquent à l'en-tête) ou abîmé (l'écrire en perdrait une partie) : on ne remplace pas une base par un fichier
// illisible, sauf fichier marqué « abime » au manifeste, à l'empreinte juste (T213 : ZipTables, rendu dans `abimes`).
// Dépendances : ZipFlux (zip-flux.js ; plus de JSZip depuis T227, retiré du dépôt en T229 ; lu dès le chargement pour
// LIMITES.zip : zip-flux.js se charge juste avant, §15.1), Schema, Formats, Donnees (csv.analyser), ZipTables ;
// crypto.subtle pour un ZIP avec manifeste (contexte sécurisé : file://, https, 127.0.0.1).

const ZipLecture = (function () {

  // Limites de l'import, écrites ICI seulement (T208) : l'export (ZipDonnees) les contrôle ; serveur.py en suit deux
  // (racine et document). T229 (décisions de Nicolas du 05/11, ZIP lu et écrit par morceaux depuis T227 et T228) :
  // ZIP limité à 4 Go, sans ZIP64 ; 4 Go décompressés ; 10 000 entrées (T212).
  const MO = 1024 * 1024;
  const LIMITES = Object.freeze({
    zip: ZipFlux.LIMITES.octets,  // taille du fichier ZIP : 4 Go moins 2 octets, le plus grand ZIP que l'écrivain de
                                  // zip-flux.js produit (0xFFFFFFFF annoncerait un ZIP64) ; affichée « 4 Go »
    entrees: 10000,         // entrées du ZIP (fichiers et dossiers)
    racine: 50 * MO,        // un fichier à la racine (CSV, manifeste), décompressé ; = envoi d'un CSV au serveur
    document: 10 * MO,      // un document (documents/<nom>), décompressé ; = envoi d'un document au serveur
    total: 4096 * MO,       // tout le contenu décompressé : 4 Go
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
  // Taille refusée, face à sa limite : « plus de 4 Go » quand l'arrondi égalerait la limite (T229, comme ZipDonnees).
  function enMoFace(octets, limite) {
    const texte = enMo(octets);
    return texte === enMo(limite) ? 'plus de ' + texte : texte;
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

  // --- 1. Source lue par tranches (taille contrôlée avant toute lecture) -------------------------------------------

  function tailleDe(source) {
    if (source instanceof ArrayBuffer || ArrayBuffer.isView(source)) { return source.byteLength; }
    if (typeof Blob !== 'undefined' && source instanceof Blob) { return source.size; }
    return null;
  }

  // Source à lire par ZipFlux (size, slice) : un File ou un Blob tel quel ; un ArrayBuffer ou une vue typée, enveloppé
  // SANS COPIE : chaque tranche demandée devient un Blob de ses seuls octets, lus à ce moment-là (comme d'un fichier).
  function sourceParTranches(source) {
    const taille = tailleDe(source);
    if (taille === null) { refuser('Aucun fichier à lire : choisissez le fichier ZIP exporté par Prévo.'); }
    if (taille > LIMITES.zip) {
      refuser('Ce fichier fait ' + enMoFace(taille, LIMITES.zip) + ' : un ZIP de données ne peut pas dépasser '
        + enMo(LIMITES.zip) + '. Il est refusé.');
    }
    if (typeof Blob !== 'undefined' && source instanceof Blob) { return source; }
    const octets = source instanceof ArrayBuffer ? new Uint8Array(source)
      : new Uint8Array(source.buffer, source.byteOffset, source.byteLength);
    return { size: octets.byteLength,
      slice: function (debut, fin) { return new Blob([octets.subarray(debut, fin)]); } };
  }

  // Chaque lecture d'une tranche de fichier coûte un aller-retour (près d'une milliseconde) : un ZIP de 10 000 petites
  // entrées en demanderait 30 000 (en-têtes locaux, puis données). Pendant lire, les tranches de FENETRE octets au plus
  // sont donc servies depuis une fenêtre de FENETRE octets lue d'un coup (une seule gardée) ; les autres sont lues
  // directement (ZipFlux.contenu les lit en flux). lireDocument prend une fenêtre neuve à chaque appel : il relit
  // bien le fichier (en-tête local et petit document en une seule lecture).
  const FENETRE = 64 * 1024;

  function lecteurAFenetre(blob) {
    let fenetre = { debut: 0, octets: new Uint8Array(0) };
    async function octets(debut, fin) {
      let lue = fenetre;
      if (debut < lue.debut || fin > lue.debut + lue.octets.length) {
        const finLue = Math.min(blob.size, Math.max(fin, debut + FENETRE));
        lue = fenetre = { debut: debut, octets: new Uint8Array(await blob.slice(debut, finLue).arrayBuffer()) };
      }
      return lue.octets.slice(debut - lue.debut, fin - lue.debut);       // copie : la fenêtre peut changer
    }
    return {
      size: blob.size,
      slice: function (debutDemande, finDemandee) {
        const debut = Math.max(0, Math.min(blob.size, debutDemande));
        const fin = Math.max(debut, Math.min(blob.size, finDemandee));
        if (fin - debut > FENETRE) { return blob.slice(debut, fin); }
        return {
          size: fin - debut,
          arrayBuffer: async function () { return (await octets(debut, fin)).buffer; },
          stream: function () {
            return new ReadableStream({ pull: async function (controleur) {
              const morceau = await octets(debut, fin);
              if (morceau.length) { controleur.enqueue(morceau); }
              controleur.close();
            } });
          },
        };
      },
    };
  }

  // Erreur de lecture du fichier lui-même (changé, déplacé ou retiré depuis son choix), et non du ZIP : ZipFlux la
  // laisse passer telle quelle.
  function estErreurDeFichier(erreur) {
    return Boolean(erreur) && (erreur.name === 'NotReadableError' || erreur.name === 'NotFoundError');
  }

  // --- 2. Répertoire central (ZipFlux : fin et répertoire lus par tranches), avant toute décompression -------------

  // { entrees: [{ nom, dossier, drapeaux, methode, crc, compresse, decompresse, local, octetsNom }], debut, taille,
  // nombre } ; le nombre d'entrées est contrôlé AVANT la lecture du répertoire (rien n'en est lu ni analysé au-delà).
  function lireRepertoire(blob) {
    return ZipFlux.lireRepertoire(blob, function (fin) {
      if (fin.nombre > LIMITES.entrees) {
        refuser('Ce ZIP contient ' + enChiffres(fin.nombre) + ' entrées : ' + enChiffres(LIMITES.entrees)
          + ' au plus. Il est refusé.');
      }
    });
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
  async function controlerEntrees(lecteur, repertoire) {
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
      // En-tête local (30 octets lus) et données avant le répertoire central, sinon 'format' (ZIP abîmé).
      await ZipFlux.positionDonnees(lecteur, entree, repertoire.debut);
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
        refuser('« ' + afficher(entree.nom) + ' » fait ' + enMoFace(entree.decompresse, limite)
          + ' une fois décompressé : ' + enMo(limite) + ' au plus par ' + quoi + '. Le ZIP est refusé.');
      }
      total += entree.decompresse;
    }
    if (total > LIMITES.total) {
      refuser('Ce ZIP fait ' + enMoFace(total, LIMITES.total) + ' une fois décompressé : ' + enMo(LIMITES.total)
        + ' au plus. Il est refusé.');
    }
  }

  // --- 9. Décompression sous contrôle : ZipFlux.contenu -------------------------------------------------------------
  // Tableau neuf de la taille DÉCLARÉE (bornée à l'étape 3), taille RÉELLE contrôlée pendant la décompression : dès
  // qu'elle dépasse la taille déclarée (bombe qui ment sur sa taille), la lecture s'arrête et le ZIP est refusé ; à la
  // fin, taille et CRC-32 doivent être ceux du répertoire central.

  function abime(entree) {
    return '« ' + afficher(entree.nom) + ' » est abîmé dans ce ZIP (contenu illisible, ou différent de ce que le ZIP '
      + 'annonce) : il est refusé. Refaites l\'export.';
  }

  function bombe(entree) {
    return '« ' + afficher(entree.nom) + ' » se décompresse plus gros que ce que le ZIP annonce : bombe de '
      + 'décompression probable. Le ZIP est refusé.';
  }

  // Erreur venue de ZipFlux → refus au message de ce module : 'bombe' et 'abime' (entrée en cause : erreur.nom),
  // 'format' (messages repris d'ici) et 'navigateur' tels quels ; fichier illisible → « Lecture du fichier
  // impossible ». Toute autre erreur (défaut du code) passe telle quelle.
  function traduire(erreur) {
    if (erreur instanceof Refus) { return erreur; }
    if (erreur instanceof ZipFlux.ErreurZip) {
      const entree = { nom: typeof erreur.nom === 'string' ? erreur.nom : '?' };
      if (erreur.code === 'bombe') { return new Refus(bombe(entree)); }
      return new Refus(erreur.code === 'abime' ? abime(entree) : erreur.message);
    }
    if (estErreurDeFichier(erreur)) {
      return new Refus('Lecture du fichier impossible (' + (erreur.message || 'erreur inconnue') + ').');
    }
    return erreur;
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
    const manquantes = [['ZipFlux', typeof ZipFlux], ['Schema', typeof Schema], ['Formats', typeof Formats],
      ['Donnees', typeof Donnees], ['ZipTables', typeof ZipTables]]
      .filter(function (paire) { return paire[1] === 'undefined'; });
    if (manquantes.length) {
      throw new Error('ZipLecture : à charger après ' + manquantes.map(function (paire) { return paire[0]; }).join(', ')
        + ' (ordre de index.html).');
    }
  }

  // Répertoire central lu et contrôlé (étapes 2 et 3 ; en-têtes locaux lus par `lecteur`, à fenêtre) ; une lecture
  // hors des octets lus (positions fausses) : ZIP abîmé.
  async function repertoireControle(blob, lecteur) {
    try {
      const repertoire = await lireRepertoire(blob);
      await controlerEntrees(lecteur, repertoire);
      return repertoire;
    } catch (erreur) {
      if (erreur instanceof RangeError) { refuser(ZIP_ABIME); }
      throw erreur;
    }
  }

  // Résultat accepté → { blob, documents } : la source (un File n'est qu'une poignée, ses octets restent sur le disque)
  // et ses documents (nom sans « documents/ » → { entree, resume }), pour la seconde passe.
  const LECTURES = new WeakMap();
  // Mesure de la dernière lecture (tests) : zip (octets du ZIP gardés en mémoire : 0 depuis T227, il est lu par
  // tranches), racine (tables, manifeste), documents gardés à la fois, plus gros document.
  let memoire = { zip: 0, racine: 0, documentsGardesMax: 0, documentMax: 0 };

  // Document décompressé et résumé dans sa propre trame (une fois finie, plus rien ne le garde) → résumé.
  async function resumerDocument(lecteur, entree) {
    const contenu = await ZipFlux.contenu(lecteur, entree);
    memoire.documentMax = Math.max(memoire.documentMax, contenu.byteLength);
    return resumer(contenu);
  }

  async function lireEtControler(source) {
    const blob = sourceParTranches(source);
    const lecteur = lecteurAFenetre(blob);
    memoire = { zip: 0, racine: 0, documentsGardesMax: 0, documentMax: 0 };
    const repertoire = await repertoireControle(blob, lecteur);
    const fichiers = repertoire.entrees.filter(function (entree) { return !entree.dossier; });
    const parNom = new Map(fichiers.map(function (entree) { return [entree.nom, entree]; }));
    const contenus = new Map();               // fichiers de la racine (LIMITES.racine au plus chacun), gardés
    async function contenuDe(nom) {
      if (!contenus.has(nom)) { contenus.set(nom, await ZipFlux.contenu(lecteur, parNom.get(nom))); }
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
      resumes.set(nom, document ? await resumerDocument(lecteur, parNom.get(nom))
        : await resumer(await contenuDe(nom)));
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
    LECTURES.set(resultat, { blob: blob, documents: documents });
    return resultat;
  }

  // Seconde passe (voir l'en-tête) : document `nom` (sans « documents/ ») d'un résultat accepté, relu du même fichier
  // et revérifié ; taille et CRC-32 le sont pendant la décompression. Le contenu rendu (copie neuve) est à oublier
  // après usage. Fichier devenu illisible (modifié, déplacé, supprimé) : refus clair, le document n'est pas importé.
  async function lireDocument(lu, nom) {
    const lecture = LECTURES.get(lu);
    const document = lecture ? lecture.documents.get(nom) : undefined;
    if (!document) {
      throw new Error('ZipLecture.lireDocument : « ' + afficher(String(nom)) + ' » n\'est pas un document d\'un ZIP '
        + 'accepté par ZipLecture.lire.');
    }
    let contenu = null;
    try {
      contenu = await ZipFlux.contenu(lecteurAFenetre(lecture.blob), document.entree);   // fenêtre neuve : relu
    } catch (erreur) {
      if (!estErreurDeFichier(erreur)) { throw traduire(erreur); }
      refuser('« ' + afficher(document.entree.nom) + ' » ne peut plus être relu : le fichier ZIP a été modifié, '
        + 'déplacé ou supprimé depuis son contrôle. Il n\'est pas importé.');
    }
    if (document.resume.empreinte !== null && (await resumer(contenu)).empreinte !== document.resume.empreinte) {
      refuser('« ' + afficher(document.entree.nom) + ' » a changé depuis le contrôle du ZIP (son empreinte ne '
        + 'correspond plus) : il n\'est pas importé.');
    }
    return contenu;
  }

  // Lit et contrôle un ZIP de données (voir l'en-tête) ; rien n'est écrit nulle part.
  async function lire(source) {
    exigerDependances();
    if (!ZipFlux.disponible()) { return { ok: false, refus: ZipFlux.MESSAGE_NAVIGATEUR }; }
    try {
      return await lireEtControler(source);
    } catch (erreur) {
      const refus = traduire(erreur);
      if (refus instanceof Refus) { return { ok: false, refus: refus.message }; }
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
