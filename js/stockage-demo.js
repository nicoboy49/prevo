'use strict';
// StockageDemo : adaptateur de stockage « démo » (tout en mémoire, rien n'est enregistré).
// Contrat : docs/ARCHITECTURE.md §6 (adaptateurs) et §11 (données de démo).
// Les fichiers CSV vivent dans une Map ; leur version est un compteur (« v1 », « v2 »…).
// Pas de crypto, pas de réseau : marche en file:// comme en http://192.168.x.x.
// Dépendances : Schema (js/schema.js) et Donnees (js/donnees.js).

const StockageDemo = (() => {

  const MESSAGE_INDISPONIBLE = 'Indisponible en mode démo : rien n\'est enregistré.';
  const LIBELLE = 'Démo — rien n\'est enregistré';
  const MOTIF_NOM_DOCUMENT = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
  const MOTIF_NOM_CSV = /^(.+)\.csv$/i;
  const MOTIF_DATE = /^(\d{4})-(\d{2})-(\d{2})/;
  const MILLISECONDES_PAR_JOUR = 86400000;
  const BOM_UTF8 = [0xEF, 0xBB, 0xBF];
  const encodeurUtf8 = new TextEncoder();

  // ===========================================================================
  // Outils
  // ===========================================================================

  function estTableConnue(nomTable) {
    return Boolean(Schema.table(nomTable));
  }

  function verifierNomTable(nomTable) {
    if (!estTableConnue(nomTable)) {
      throw new Donnees.ErreurStockage('Table inconnue : « ' + nomTable + ' ».');
    }
  }

  // Texte CSV ou octets → Uint8Array (copie). Un texte reçoit le BOM, comme un vrai fichier.
  function enOctets(contenu) {
    if (typeof contenu === 'string') {
      const texte = contenu.charCodeAt(0) === 0xFEFF ? contenu.slice(1) : contenu;
      const corps = encodeurUtf8.encode(texte);
      const octets = new Uint8Array(BOM_UTF8.length + corps.length);
      octets.set(BOM_UTF8, 0);
      octets.set(corps, BOM_UTF8.length);
      return octets;
    }
    if (contenu instanceof Uint8Array) { return contenu.slice(); }
    if (contenu instanceof ArrayBuffer) { return new Uint8Array(contenu.slice(0)); }
    if (ArrayBuffer.isView(contenu)) {
      return new Uint8Array(contenu.buffer.slice(contenu.byteOffset, contenu.byteOffset + contenu.byteLength));
    }
    throw new Donnees.ErreurStockage('Contenu de fichier illisible (texte ou octets attendus).');
  }

  // 'AAAA-MM-JJ' → nombre de jours depuis le 1er janvier 1970 (UTC), ou null.
  function jourDepuisDate(dateIso) {
    const morceaux = MOTIF_DATE.exec(String(dateIso || ''));
    if (!morceaux) { return null; }
    return Date.UTC(Number(morceaux[1]), Number(morceaux[2]) - 1, Number(morceaux[3])) / MILLISECONDES_PAR_JOUR;
  }

  function dateDepuisJour(jour) {
    const date = new Date(jour * MILLISECONDES_PAR_JOUR);
    return date.getUTCFullYear() + '-' + String(date.getUTCMonth() + 1).padStart(2, '0')
      + '-' + String(date.getUTCDate()).padStart(2, '0');
  }

  // Décale de `jours` une valeur 'AAAA-MM-JJ' ou 'AAAA-MM-JJ HH:MM' (l'heure est gardée).
  // Une valeur vide ou illisible est rendue telle quelle.
  function decalerValeur(valeur, jours) {
    const jour = jourDepuisDate(valeur);
    if (jour === null) { return valeur; }
    return dateDepuisJour(jour + jours) + valeur.slice(10);
  }

  // ===========================================================================
  // Décalage des dates (ARCHITECTURE.md §11)
  // ===========================================================================

  // Décale tous les champs date et date_heure du nombre de SEMAINES ENTIÈRES écoulées entre
  // dateReference et aujourdhui (les jours de la semaine restent les mêmes ; les identifiants
  // gardent leur année d'origine). tables : { nomTable: texte CSV ou octets }.
  // Renvoie { nomTable: Uint8Array } (format §3.1). Une table inconnue du schéma est recopiée.
  function decalerDates(tables, dateReference, aujourdhui = Donnees.aujourdhui()) {
    const jourReference = jourDepuisDate(dateReference);
    const jourActuel = jourDepuisDate(aujourdhui);
    if (jourReference === null || jourActuel === null) {
      throw new Error('StockageDemo.decalerDates : dates attendues au format AAAA-MM-JJ.');
    }
    const semaines = Math.trunc((jourActuel - jourReference) / 7);
    const jours = semaines * 7;
    const resultat = {};
    Object.keys(tables).forEach((nomTable) => {
      const description = Schema.table(nomTable);
      if (!description || jours === 0) {
        resultat[nomTable] = enOctets(tables[nomTable]);
        return;
      }
      const champsDates = description.champs
        .filter((champ) => champ.type === 'date' || champ.type === 'date_heure')
        .map((champ) => champ.nom);
      const lu = Donnees.csv.analyser(nomTable, tables[nomTable]);
      for (const ligne of lu.lignes) {
        for (const nomChamp of champsDates) { ligne[nomChamp] = decalerValeur(ligne[nomChamp], jours); }
      }
      resultat[nomTable] = Donnees.csv.serialiser(nomTable, lu.lignes, lu.colonnesInconnues);
    });
    return resultat;
  }

  // ===========================================================================
  // Fabrique de l'adaptateur
  // ===========================================================================

  // tables : { nomTable: texte CSV ou Uint8Array } (table non fournie = fichier absent).
  // options : { dateReference, aujourdhui } ; avec dateReference, les dates sont décalées.
  function creer(tables, options) {
    const reglages = options || {};
    let contenus = tables || {};
    if (reglages.dateReference) {
      contenus = decalerDates(contenus, reglages.dateReference, reglages.aujourdhui || Donnees.aujourdhui());
    }

    const fichiers = new Map();         // nomTable → { octets, numero }
    const documents = new Map();        // nom → Blob
    const urlsDocuments = new Map();    // nom → URL d'objet déjà créée

    Object.keys(contenus).forEach((nomTable) => {
      if (!estTableConnue(nomTable)) {
        console.warn('StockageDemo : table inconnue « ' + nomTable + ' » ignorée.');
        return;
      }
      fichiers.set(nomTable, { octets: enOctets(contenus[nomTable]), numero: 1 });
    });

    function versionDe(nomTable) {
      const fichier = fichiers.get(nomTable);
      return fichier ? 'v' + fichier.numero : null;
    }

    function ecrireFichier(nomTable, octets) {
      const ancien = fichiers.get(nomTable);
      fichiers.set(nomTable, { octets: octets, numero: ancien ? ancien.numero + 1 : 1 });
      return { version: versionDe(nomTable) };
    }

    async function charger(nomTable) {
      verifierNomTable(nomTable);
      const fichier = fichiers.get(nomTable);
      if (!fichier) { return { octets: null, version: null }; }
      return { octets: fichier.octets.slice(), version: versionDe(nomTable) };
    }

    // versionAttendue null = le fichier ne doit pas exister ; sinon il doit avoir cette version.
    async function enregistrer(nomTable, octets, versionAttendue) {
      verifierNomTable(nomTable);
      const attendue = versionAttendue === undefined ? null : versionAttendue;
      const actuelle = versionDe(nomTable);
      if (attendue !== actuelle) {
        let message = 'Le fichier ' + nomTable + '.csv a été modifié par un autre poste.';
        if (actuelle === null) { message = 'Le fichier ' + nomTable + '.csv n\'existe plus.'; }
        else if (attendue === null) { message = 'Le fichier ' + nomTable + '.csv existe déjà.'; }
        throw new Donnees.ErreurConflit(message, actuelle);
      }
      return ecrireFichier(nomTable, enOctets(octets));
    }

    // Ajoute en fin de fichier : octets = ligne d'en-tête + lignes (UTF-8 sans BOM).
    // Fichier absent ou vide → BOM + contenu. Sinon le fichier doit être en UTF-8 avec le même
    // en-tête, sinon ErreurConflit (le fichier a été réenregistré par Excel).
    async function ajouter(nomTable, octets) {
      verifierNomTable(nomTable);
      const ajout = Donnees.csv.decoder(enOctets(octets));
      if (ajout.encodage !== 'utf-8') {
        throw new Donnees.ErreurStockage('Le contenu à ajouter doit être encodé en UTF-8.');
      }
      const finEntete = ajout.texte.indexOf('\n');
      const enteteAjout = (finEntete < 0 ? ajout.texte : ajout.texte.slice(0, finEntete)).replace(/\r$/, '');
      const resteAjout = finEntete < 0 ? '' : ajout.texte.slice(finEntete + 1);
      if (enteteAjout === '') {
        throw new Donnees.ErreurStockage('Le contenu à ajouter doit commencer par la ligne d\'en-tête.');
      }

      const fichier = fichiers.get(nomTable);
      const actuel = fichier ? Donnees.csv.decoder(fichier.octets) : null;
      if (!actuel || actuel.texte.trim() === '') { return ecrireFichier(nomTable, enOctets(ajout.texte)); }

      if (actuel.encodage !== 'utf-8') {
        throw new Donnees.ErreurConflit('Le fichier ' + nomTable + '.csv n\'est pas en UTF-8 (réenregistré par Excel ?).',
          versionDe(nomTable));
      }
      const finEnteteActuel = actuel.texte.indexOf('\n');
      const enteteActuel = (finEnteteActuel < 0 ? actuel.texte : actuel.texte.slice(0, finEnteteActuel)).replace(/\r$/, '');
      if (enteteActuel !== enteteAjout) {
        throw new Donnees.ErreurConflit('L\'en-tête de ' + nomTable + '.csv est différent.', versionDe(nomTable));
      }
      if (resteAjout === '') { return { version: versionDe(nomTable) }; }
      const separation = actuel.texte.endsWith('\n') ? '' : '\r\n';
      return ecrireFichier(nomTable, enOctets(actuel.texte + separation + resteAjout));
    }

    async function listerVersions() {
      const versions = {};
      for (const nomTable of Schema.nomsTables()) { versions[nomTable] = versionDe(nomTable); }
      return versions;
    }

    // --- Documents (photos, rapports) : gardés en mémoire ------------------------------------

    function verifierNomDocument(nom) {
      if (typeof nom !== 'string' || !MOTIF_NOM_DOCUMENT.test(nom) || nom.indexOf('..') >= 0) {
        throw new Donnees.ErreurStockage('Nom de document invalide : « ' + nom + ' ».');
      }
    }

    async function ecrireDocument(nom, blob) {
      verifierNomDocument(nom);
      if (documents.has(nom)) { throw new Donnees.ErreurStockage('Le document ' + nom + ' existe déjà.'); }
      documents.set(nom, blob);
      return nom;
    }

    async function lireDocument(nom) {
      verifierNomDocument(nom);
      return documents.has(nom) ? documents.get(nom) : null;
    }

    // URL d'objet affichable (valable tant que la page reste ouverte) ; null si le document n'existe pas.
    async function urlDocument(nom) {
      verifierNomDocument(nom);
      if (urlsDocuments.has(nom)) { return urlsDocuments.get(nom); }
      if (!documents.has(nom)) { return null; }
      // Un document .html est isolé (aucun script ne s'y exécute) : Donnees.documentAffichable.
      const url = URL.createObjectURL(await Donnees.documentAffichable(nom, documents.get(nom)));
      urlsDocuments.set(nom, url);
      return url;
    }

    // Documents ajoutés pendant la démo, pour l'export ZIP : [{ nom, blob }].
    function documentsEnMemoire() {
      return Array.from(documents, ([nom, blob]) => ({ nom: nom, blob: blob }));
    }

    // --- Sauvegardes : sans objet en démo ----------------------------------------------------

    async function indisponible() {
      throw new Donnees.ErreurStockage(MESSAGE_INDISPONIBLE);
    }

    return {
      mode: 'demo',
      libelle: LIBELLE,
      charger: charger,
      enregistrer: enregistrer,
      ajouter: ajouter,
      listerVersions: listerVersions,
      ecrireDocument: ecrireDocument,
      lireDocument: lireDocument,
      urlDocument: urlDocument,
      sauvegarder: indisponible,
      listerSauvegardes: indisponible,
      restaurer: indisponible,
      info: async function () { return {}; },
      documentsEnMemoire: documentsEnMemoire,
    };
  }

  // ===========================================================================
  // Démo à partir de fichiers déposés
  // ===========================================================================

  function lireFichier(fichier) {
    if (typeof fichier.arrayBuffer === 'function') {
      return fichier.arrayBuffer().then((tampon) => new Uint8Array(tampon));
    }
    return new Promise((resoudre, rejeter) => {
      const lecteur = new FileReader();
      lecteur.onload = () => resoudre(new Uint8Array(lecteur.result));
      lecteur.onerror = () => rejeter(lecteur.error);
      lecteur.readAsArrayBuffer(fichier);
    });
  }

  // fichiers : FileList ou tableau de File (nom « <table>.csv », casse ignorée), sans décalage
  // des dates. Renvoie { adaptateur, fichiersIgnores: [noms] } (autre nom, ou table en double).
  async function depuisFichiers(fichiers) {
    const tables = {};
    const fichiersIgnores = [];
    for (const fichier of Array.from(fichiers || [])) {
      const morceaux = MOTIF_NOM_CSV.exec(fichier.name || '');
      const nomTable = morceaux ? morceaux[1].toLowerCase() : '';
      if (!estTableConnue(nomTable) || Object.prototype.hasOwnProperty.call(tables, nomTable)) {
        fichiersIgnores.push(fichier.name);
        continue;
      }
      try {
        tables[nomTable] = await lireFichier(fichier);
      } catch (erreur) {
        throw new Donnees.ErreurStockage('Impossible de lire le fichier ' + fichier.name + '.', erreur);
      }
    }
    return { adaptateur: creer(tables), fichiersIgnores: fichiersIgnores };
  }

  return {
    creer: creer,
    decalerDates: decalerDates,
    depuisFichiers: depuisFichiers,
  };
})();
