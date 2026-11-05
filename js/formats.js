'use strict';
// Formats : registre des formats des fichiers de données (chantier « socle de données », décisions D167 et D168).
// Contrat : docs/ARCHITECTURE.md §1 (chargé juste après js/schema.js), §4 (schéma), §5.6 (passage au format
// courant), §14.1 (format 2) et §20.2 (format 3).
// Le format est un entier (Schema.version), distinct de la version de l'application (2.0.0) ; celui d'une base est
// parametres.version_schema (absent ou illisible : format 1). Tout est dérivé de Schema : une table ou un champ qui
// porte depuisVersion: N n'existe qu'à partir du format N ; les autres existent depuis le format 1.
//   - format 1 : les 22 tables du brief, sans les colonnes marquées depuisVersion ;
//   - format 2 : + equipements.valeur_remplacement, demandes.symptome_code, demandes.ot_origine_id,
//                ordres_travail.anomalie_constatee (§14.1) ;
//   - format 3 : + ordres_travail.astuce et les tables wiki_pages, wiki_journal (§20.2).
// Les étapes de migration (ETAPES) sont explicites, une par passage de N à N+1, pures (l'entrée n'est jamais
// modifiée) et idempotentes (rejouée, une étape ne change rien). migrer() les enchaîne et rend une ligne de journal
// par étape, exactement « passage au format N du fichier » : ce texte est relu par la suggestion S4
// (js/modules/suggestions-regles.js, MARQUE_FORMAT_2) et ne doit pas changer.
// Une base en mémoire a la forme { tables: { <nom>: { entete: [noms…], lignes: [{ <colonne>: '<valeur>' }] } } }
// (valeurs = chaînes, comme en mémoire dans Prévo). Ce fichier ne lit ni n'écrit aucun fichier : il sert de
// référence à la migration en mode dossier, à l'import et à l'export ZIP, et au miroir Python de serveur.py (mêmes
// règles).
// Dépendance : Schema (js/schema.js) seulement.

const Formats = (function () {

  const PREMIER_FORMAT = 1;
  const CLE_VERSION_SCHEMA = 'version_schema';
  const VERSION_PAR_DEFAUT = 1;              // version_schema absent ou illisible : fichiers du lot 1 (format 1)
  const NOM_APPLICATION = 'Prévo';
  const CHAMPS_CONTEXTE = ['version_appli', 'format', 'date', 'motif', 'mode'];   // ordre du manifeste
  const CODE_BOM = 0xFEFF;

  function aLaPropriete(objet, nom) {
    return Object.prototype.hasOwnProperty.call(objet, nom);
  }

  // Vrai si une table ou un champ du schéma existe dans ce format (pas de depuisVersion : depuis le format 1).
  function existeDans(element, format) {
    return element.depuisVersion === undefined || element.depuisVersion <= format;
  }

  // Premier format où la table existe (1 pour les tables du brief, 3 pour celles du wiki).
  function premierFormatDe(description) {
    return description.depuisVersion === undefined ? PREMIER_FORMAT : description.depuisVersion;
  }

  // Format demandé, ou le format courant s'il est omis.
  function formatOuCourant(format) {
    return format === undefined ? Schema.version : format;
  }

  // Champs (descriptions du schéma) de la table dans ce format, dans l'ordre du schéma ; [] si elle n'y existe pas.
  function champsDuFormat(nomTable, format) {
    const description = Schema.table(nomTable);
    if (!description || !existeDans(description, format)) { return []; }
    return description.champs.filter(function (champ) { return existeDans(champ, format); });
  }

  // ---------------------------------------------------------------------------
  // Colonnes et tables d'un format
  // ---------------------------------------------------------------------------

  // Noms des colonnes de la table dans ce format (format omis : le format courant), dans l'ordre du schéma ;
  // [] si la table n'existe pas encore dans ce format ou n'est pas dans le schéma.
  function colonnes(nomTable, format) {
    return champsDuFormat(nomTable, formatOuCourant(format)).map(function (champ) { return champ.nom; });
  }

  // Noms des tables qui existent dans ce format (format omis : le format courant), dans l'ordre du schéma.
  function tables(format) {
    const voulu = formatOuCourant(format);
    return Schema.nomsTables().filter(function (nomTable) { return existeDans(Schema.table(nomTable), voulu); });
  }

  // Nom de colonne comparable : BOM de tête retiré, espaces de bord retirés.
  function nomDeColonne(valeur) {
    let texte = valeur === null || valeur === undefined ? '' : String(valeur);
    if (texte.charCodeAt(0) === CODE_BOM) { texte = texte.slice(1); }
    return texte.trim();
  }

  // Clé de comparaison d'un nom de colonne, la même que la lecture de Prévo (Donnees, cleEntete) : BOM et espaces
  // de bord retirés, accents retirés, minuscules, espaces et soulignés ignorés. Un en-tête que Donnees sait lire
  // n'est donc jamais vu « abîmé » ici (relecture de T183).
  const MOTIF_ACCENTS = /[\u0300-\u036f]/g;
  const MOTIF_SEPARATEURS = /[\s_]+/g;
  function cleDeColonne(valeur) {
    return nomDeColonne(valeur).normalize('NFD').replace(MOTIF_ACCENTS, '').toLowerCase()
      .replace(MOTIF_SEPARATEURS, '');
  }

  // Format d'un fichier d'après son en-tête (tableau de noms, ordre indifférent) : le plus grand format N, du
  // premier format où la table existe jusqu'au format courant, dont toutes les colonnes sont dans l'en-tête.
  // Une table dont les colonnes n'ont pas changé depuis le format N donne donc le format courant (son en-tête est
  // celui de tous ces formats). 0 si même les colonnes du premier format de la table manquent (fichier abîmé ou
  // incomplet, en-tête vide) ; null pour une table inconnue du schéma. Ne lève jamais d'exception.
  function formatDuFichier(nomTable, entete) {
    try {
      const description = Schema.table(nomTable);
      if (!description) { return null; }
      const presentes = new Set((Array.isArray(entete) ? entete : []).map(cleDeColonne));
      let trouve = 0;
      for (let format = premierFormatDe(description); format <= Schema.version; format += 1) {
        const complet = colonnes(nomTable, format).every(function (nom) { return presentes.has(cleDeColonne(nom)); });
        if (!complet) { break; }            // les colonnes d'un format contiennent celles des formats précédents
        trouve = format;
      }
      return trouve;
    } catch (erreur) {
      return 0;                             // en-tête illisible (valeur qui refuse d'être convertie en texte)
    }
  }

  // ---------------------------------------------------------------------------
  // Format d'une base : parametres.version_schema
  // ---------------------------------------------------------------------------

  // Copie exacte de Donnees.nombre (js/donnees.js, normaliserDecimal) : Formats est chargé avant Donnees.
  // Valeur → Number, ou null si vide ou illisible ; virgule décimale et espaces (insécables compris) acceptés.
  function nombre(valeur) {
    if (typeof valeur === 'number') { return Number.isFinite(valeur) ? valeur : null; }
    const texte = (valeur === null || valeur === undefined ? '' : String(valeur)).trim();
    if (texte === '') { return null; }
    const compact = texte.replace(/\s+/g, '').replace(',', '.');
    const morceaux = /^([+-]?)(\d*)(?:\.(\d*))?$/.exec(compact);
    if (!morceaux || (morceaux[2] === '' && !morceaux[3])) { return null; }
    const signe = morceaux[1] === '-' ? '-' : '';
    const partieEntiere = morceaux[2] === '' ? '0' : morceaux[2];
    const partieDecimale = morceaux[3] ? '.' + morceaux[3] : '';
    const converti = Number(signe + partieEntiere + partieDecimale);
    return Number.isFinite(converti) ? converti : null;
  }

  // Format d'une base d'après les lignes de parametres ([{ cle, valeur }], valeurs en mémoire, sans l'apostrophe de
  // protection) : version_schema de la première ligne qui porte cette clé, lu comme Donnees.nombre ; absent, vide ou
  // illisible → 1. Même règle que versionSchemaDe de js/donnees.js (§5.6). Toujours un entier dans un fichier
  // écrit par Prévo ; une valeur décimale écrite à la main est rendue telle quelle, comme par versionSchemaDe.
  function versionDeBase(lignesParametres) {
    const lignes = Array.isArray(lignesParametres) ? lignesParametres : [];
    const ligne = lignes.find(function (l) { return Boolean(l) && l.cle === CLE_VERSION_SCHEMA; });
    const lue = ligne ? nombre(ligne.valeur) : null;
    return lue === null ? VERSION_PAR_DEFAUT : lue;
  }

  // ---------------------------------------------------------------------------
  // Étapes de migration (D168) : pures et idempotentes
  // ---------------------------------------------------------------------------

  // Copie d'une table de la base : en-tête et lignes copiés (les autres propriétés de la table sont gardées).
  function copierTable(table) {
    const source = table && typeof table === 'object' ? table : {};
    return Object.assign({}, source, {
      entete: Array.isArray(source.entete) ? source.entete.slice() : [],
      lignes: Array.isArray(source.lignes)
        ? source.lignes.map(function (ligne) { return Object.assign({}, ligne); })
        : [],
    });
  }

  // Ajoute en fin d'en-tête les colonnes du format absentes de la table (comparées comme dans formatDuFichier),
  // avec la valeur par défaut du schéma (sinon '') dans chaque ligne qui n'a pas déjà cette colonne. Les colonnes
  // inconnues du schéma restent à leur place, avec leurs valeurs. Modifie la COPIE reçue.
  function completerColonnes(nomTable, table, format) {
    const presentes = new Set(table.entete.map(cleDeColonne));
    for (const champ of champsDuFormat(nomTable, format)) {
      if (presentes.has(cleDeColonne(champ.nom))) { continue; }
      const valeurParDefaut = champ.defaut === undefined ? '' : champ.defaut;
      table.entete.push(champ.nom);
      presentes.add(cleDeColonne(champ.nom));
      for (const ligne of table.lignes) {
        if (!aLaPropriete(ligne, champ.nom)) { ligne[champ.nom] = valeurParDefaut; }
      }
    }
  }

  // parametres.version_schema = String(format) : la première ligne qui porte la clé, sinon une ligne ajoutée en fin
  // (les autres colonnes de l'en-tête y valent ''). Modifie la COPIE reçue.
  function poserVersion(tableParametres, format) {
    const ligne = tableParametres.lignes.find(function (l) { return l.cle === CLE_VERSION_SCHEMA; });
    if (ligne) {
      ligne.valeur = String(format);
      return;
    }
    const nouvelle = {};
    for (const colonne of tableParametres.entete) { nouvelle[colonne] = ''; }
    nouvelle.cle = CLE_VERSION_SCHEMA;
    nouvelle.valeur = String(format);
    tableParametres.lignes.push(nouvelle);
  }

  // Passage d'une base au format `format` (étape additive, §14.1 et §20.2). Rend une NOUVELLE base où :
  //   - chaque table du format absente est créée vide (entete = colonnes(table, format), lignes = []) ;
  //   - chaque colonne du format absente d'une table est ajoutée en fin d'en-tête, avec sa valeur par défaut ;
  //   - les colonnes et les tables inconnues du schéma sont gardées telles quelles ;
  //   - parametres.version_schema vaut String(format).
  // La base reçue n'est pas modifiée ; appliquée deux fois, l'étape donne le même résultat qu'une fois.
  function passerAuFormat(base, format) {
    const source = base && typeof base === 'object' ? base : {};
    const tablesSource = source.tables && typeof source.tables === 'object' ? source.tables : {};
    const nouvellesTables = {};
    for (const nomTable of Object.keys(tablesSource)) {
      nouvellesTables[nomTable] = copierTable(tablesSource[nomTable]);
    }
    for (const nomTable of tables(format)) {
      if (!aLaPropriete(nouvellesTables, nomTable)) { nouvellesTables[nomTable] = { entete: [], lignes: [] }; }
      completerColonnes(nomTable, nouvellesTables[nomTable], format);
    }
    poserVersion(nouvellesTables.parametres, format);
    return Object.assign({}, source, { tables: nouvellesTables });
  }

  // Une étape du registre : de N à N+1, une description, et sa fonction pure appliquer(base) → nouvelle base.
  function etape(de, vers, description) {
    return Object.freeze({
      de: de,
      vers: vers,
      description: description,
      appliquer: function (base) { return passerAuFormat(base, vers); },
    });
  }

  // Le registre, dans l'ordre. Un format futur ajoute son étape ici (et Schema.version) : le test
  // tests/test_formats_js.py vérifie que la chaîne va sans trou du format 1 au format courant.
  const ETAPES = Object.freeze([
    etape(1, 2, 'Format 2 (versions 1.0 et 1.1, §14.1) : colonnes equipements.valeur_remplacement, '
      + 'demandes.symptome_code, demandes.ot_origine_id et ordres_travail.anomalie_constatee (défaut 0), '
      + 'en fin de table.'),
    etape(2, 3, 'Format 3 (versions 1.2 et 2.0, §20.2) : colonne ordres_travail.astuce en fin de table, '
      + 'tables wiki_pages et wiki_journal (vides).'),
  ]);

  // Ligne de journal d'une étape : texte exact relu par la suggestion S4.
  function ligneDeJournal(format) {
    return `passage au format ${format} du fichier`;
  }

  // Enchaîne les étapes de `de` à `vers` → { base, journal, etapes } :
  //   - base    : la base au format `vers` (nouvel objet ; la base reçue n'est pas modifiée) ;
  //   - journal : une ligne « passage au format N du fichier » par étape appliquée ;
  //   - etapes  : les étapes appliquées ({ de, vers, description }).
  // `de` est le format actuel de la base (versionDeBase) ; de >= vers (base déjà au format, ou plus récente) :
  // base rendue telle quelle, journal et etapes vides. `vers` : un format entier de 1 au format courant.
  function migrer(base, de, vers) {
    if (!Number.isInteger(vers) || vers < PREMIER_FORMAT || vers > Schema.version) {
      throw new RangeError(I18n.t('socle.migrer.formats_migrer_format_cible', { vers, premier: PREMIER_FORMAT, version: Schema.version }));
    }
    if (typeof de !== 'number' || Number.isNaN(de)) {
      throw new TypeError(I18n.t('socle.migrer.formats_migrer_format_depart', { de }));
    }
    if (de >= vers) { return { base: base, journal: [], etapes: [] }; }
    let courante = base;
    const journal = [];
    const etapes = [];
    for (const etapeDuRegistre of ETAPES) {
      if (etapeDuRegistre.vers <= de || etapeDuRegistre.vers > vers) { continue; }
      courante = etapeDuRegistre.appliquer(courante);
      journal.push(ligneDeJournal(etapeDuRegistre.vers));
      etapes.push({ de: etapeDuRegistre.de, vers: etapeDuRegistre.vers, description: etapeDuRegistre.description });
    }
    return { base: courante, journal: journal, etapes: etapes };
  }

  // ---------------------------------------------------------------------------
  // Manifeste (sauvegardes, export ZIP : D167)
  // ---------------------------------------------------------------------------

  // Uint8Array, ArrayBuffer ou autre vue typée → Uint8Array (sans copie).
  function enOctets(entree) {
    if (entree instanceof Uint8Array) { return entree; }
    if (entree instanceof ArrayBuffer) { return new Uint8Array(entree); }
    if (ArrayBuffer.isView(entree)) { return new Uint8Array(entree.buffer, entree.byteOffset, entree.byteLength); }
    throw new TypeError(I18n.t('socle.en_octets.formats_manifeste_octets_attendus'));
  }

  function hexadecimal(tampon) {
    return Array.from(new Uint8Array(tampon), function (octet) {
      return octet.toString(16).padStart(2, '0');
    }).join('');
  }

  function comparerNoms(a, b) {
    if (a.nom < b.nom) { return -1; }
    return a.nom > b.nom ? 1 : 0;
  }

  // --- Repli SHA-256 en JavaScript (T189) ----------------------------------------------------
  // crypto.subtle n'existe qu'en contexte sécurisé (file://, https, 127.0.0.1) : un téléphone ou un poste qui ouvre
  // Prévo en http par le réseau n'en a pas (ARCHITECTURE.md §2). L'empreinte est alors calculée ici, selon la norme
  // FIPS 180-4 (blocs de 64 octets, 64 tours), sans bibliothèque. Testée contre hashlib.sha256 (tests/test_zip_export.py).
  const SHA256_DEPART = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];
  const SHA256_CONSTANTES = new Uint32Array([
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
  ]);

  // Rotation à droite d'un mot de 32 bits.
  function rotation(mot, rang) {
    return (mot >>> rang) | (mot << (32 - rang));
  }

  // Octets (Uint8Array) → ArrayBuffer de 32 octets, comme crypto.subtle.digest('SHA-256', …).
  function sha256(octets) {
    const longueur = octets.length;
    const message = new Uint8Array(Math.ceil((longueur + 9) / 64) * 64);
    message.set(octets);
    message[longueur] = 0x80;                                    // un bit 1, puis des 0 jusqu'à la longueur
    const vue = new DataView(message.buffer);
    vue.setUint32(message.length - 8, Math.floor(longueur / 0x20000000));   // longueur en bits, 64 bits gros-boutiste
    vue.setUint32(message.length - 4, (longueur * 8) >>> 0);
    const etat = new Uint32Array(SHA256_DEPART);
    const mots = new Uint32Array(64);
    for (let debut = 0; debut < message.length; debut += 64) {
      for (let i = 0; i < 16; i += 1) { mots[i] = vue.getUint32(debut + i * 4); }
      for (let i = 16; i < 64; i += 1) {
        const avant15 = mots[i - 15];
        const avant2 = mots[i - 2];
        const sigma0 = rotation(avant15, 7) ^ rotation(avant15, 18) ^ (avant15 >>> 3);
        const sigma1 = rotation(avant2, 17) ^ rotation(avant2, 19) ^ (avant2 >>> 10);
        mots[i] = (mots[i - 16] + sigma0 + mots[i - 7] + sigma1) | 0;
      }
      let [a, b, c, d, e, f, g, h] = etat;
      for (let i = 0; i < 64; i += 1) {
        const somme1 = rotation(e, 6) ^ rotation(e, 11) ^ rotation(e, 25);
        const choix = (e & f) ^ (~e & g);
        const t1 = (h + somme1 + choix + SHA256_CONSTANTES[i] + mots[i]) | 0;
        const somme0 = rotation(a, 2) ^ rotation(a, 13) ^ rotation(a, 22);
        const majorite = (a & b) ^ (a & c) ^ (b & c);
        const t2 = (somme0 + majorite) | 0;
        h = g; g = f; f = e; e = (d + t1) | 0;
        d = c; c = b; b = a; a = (t1 + t2) | 0;
      }
      etat[0] += a; etat[1] += b; etat[2] += c; etat[3] += d;    // Uint32Array : addition modulo 2^32
      etat[4] += e; etat[5] += f; etat[6] += g; etat[7] += h;
    }
    const resultat = new DataView(new ArrayBuffer(32));
    for (let i = 0; i < 8; i += 1) { resultat.setUint32(i * 4, etat[i]); }
    return resultat.buffer;
  }

  // Manifeste d'un ensemble de fichiers ([{ nom, octets: Uint8Array, abime }]) → Promise de
  // { application: 'Prévo', version_appli, format, date, motif, mode, fichiers: [{ nom, octets, sha256, abime }] } :
  // champs du contexte absents (undefined ou null) omis, fichiers triés par nom, octets = taille, sha256 en
  // hexadécimal ; « abime »: true seulement pour un fichier donné avec abime === true (T206 : CSV abîmé, critère de
  // l'appelant ; absent sinon). Empreinte par crypto.subtle quand il existe (contexte sécurisé : file://, https, 127.0.0.1 ;
  // ARCHITECTURE.md §2), sinon par sha256 ci-dessus (même résultat, T189) : la promesse n'est plus rejetée.
  async function manifeste(fichiers, contexte) {
    const outilsCrypto = typeof crypto !== 'undefined' && crypto ? crypto.subtle : undefined;
    const empreinteDe = outilsCrypto
      ? function (octets) { return outilsCrypto.digest('SHA-256', octets); }
      : function (octets) { return Promise.resolve(sha256(octets)); };
    const entrees = (Array.isArray(fichiers) ? fichiers : []).map(function (fichier) {
      return { nom: String(fichier.nom), octets: enOctets(fichier.octets), abime: fichier.abime === true };
    }).sort(comparerNoms);
    const decrits = await Promise.all(entrees.map(async function (entree) {
      const empreinte = await empreinteDe(entree.octets);
      const decrit = { nom: entree.nom, octets: entree.octets.byteLength, sha256: hexadecimal(empreinte) };
      if (entree.abime) { decrit.abime = true; }
      return decrit;
    }));
    const resultat = { application: NOM_APPLICATION };
    const source = contexte && typeof contexte === 'object' ? contexte : {};
    for (const cle of CHAMPS_CONTEXTE) {
      if (source[cle] !== undefined && source[cle] !== null) { resultat[cle] = source[cle]; }
    }
    resultat.fichiers = decrits;
    return resultat;
  }

  return {
    courant: Schema.version,           // format courant des fichiers (= Schema.version)
    colonnes: colonnes,
    tables: tables,
    formatDuFichier: formatDuFichier,
    versionDeBase: versionDeBase,
    ETAPES: ETAPES,
    migrer: migrer,
    manifeste: manifeste,
  };
})();
