'use strict';
// ZipDonnees : export ZIP complet des données, en un clic (chantier « socle de données », T189 ; décisions D167 et
// D171 ; ARCHITECTURE.md §15.1). Appelé par App.exporterZip (boutons de Paramètres, de l'accueil du responsable, du
// bandeau et de la feuille « Plus » de la démo).
//
// Contenu de prevo-export-AAAA-MM-JJ.zip :
//   - <table>.csv à la racine : les 24 tables, resérialisées depuis la mémoire (Donnees.instantane, après
//     Donnees.rafraichir : le journal, écrit par ajout, est relu d'abord) ;
//   - documents/<nom> : les documents cités dans equipements.document, demandes.photo et
//     controles_reglementaires.rapport, et les rapports mensuels figés (paramètre rapports_mensuels), lus par
//     l'adaptateur de stockage (lireDocument : donnees/documents/ en modes serveur et dossier, mémoire en démo) ;
//   - manifeste.json à la racine : Formats.manifeste de tous les autres fichiers du ZIP (application, version_appli,
//     format de la base, date « AAAA-MM-JJTHH:MM:SS » du poste (comme les sauvegardes, docs/FORMAT.md), motif « export », mode serveur | dossier | demo,
//     fichiers [{ nom, octets, sha256 }], plus « abime »: true et « abime_depuis » pour un CSV abîmé, T210 et T213) ;
//     s'il en manque, `manquants` : les documents cités introuvables.
// Jamais rien de acces/ (comptes, sessions, appareils) ni d'autre dossier : un nom cité n'est lu que s'il a la forme
// d'un nom de document (MOTIF_NOM_DOCUMENT, mêmes règles que serveur.py : ni « / », ni « \ », ni « .. ») ; sinon il
// est compté parmi les manquants, sans aucune lecture. Un document introuvable n'arrête pas l'export.
// T214 (décision de Nicolas) : export « données seules (sans les documents) », importable comme l'export complet
// (contenu({ sansDocuments: true }), bouton #btn-export-donnees-seules de Paramètres) : les CSV et manifeste.json,
// aucune entrée documents/, aucun document lu ; manifeste : « documents »: « exclus », pas de `manquants` (les
// documents cités n'y sont pas « manquants », ils sont exclus) ; prevo-export-AAAA-MM-JJ-sans-documents.zip.
// T208 (règle de Nicolas : tout ce que Prévo exporte, Prévo peut le réimporter) : avant de produire le ZIP, l'export
// contrôle les limites de l'import (ZipLecture.LIMITES, lues, jamais recopiées) ; s'il en dépasse une, rien n'est
// produit et une fenêtre dit quoi (depassements, refusDe).
// T222 (décision de Nicolas du 05/11) : avant un export complet dont les fichiers dépassent AVERTISSEMENT.contenu,
// une fenêtre (#export-zip-avertissement) propose les données seules, l'export complet quand même, ou d'annuler.
// T215 (recette du ZIP par morceaux, docs/FORMAT.md §13) : la mémoire de l'export reste proportionnelle à la taille du
// ZIP, mais dans le processus principal du navigateur, plus dans l'onglet : jusqu'à une fois et demie la taille du ZIP
// (contre 5 à 6 fois avec JSZip, T212). Seuil relevé de 150 à 500 Mo, texte corrigé.
// T228 (T215 « ZIP par morceaux », morceau 3) : le ZIP est écrit par ZipFlux (zip-flux.js), un document à la fois,
// sans JSZip. Mémoire JavaScript bornée aux CSV (les tables, déjà en mémoire) plus UN document, en deux passes :
//   1. préparation (contenu) : chaque document cité est demandé à l'adaptateur pour sa TAILLE seulement (Blob.size,
//      ou longueur d'un Uint8Array), puis oublié ; les limites de l'import sont contrôlées sur ces tailles, avant
//      toute lecture de contenu. Les CSV sont décrits pour le manifeste ; la taille exacte de manifeste.json (pour
//      l'avertissement) vient d'un manifeste où les empreintes des documents, pas encore lues, sont 64 zéros : une
//      empreinte SHA-256 en hexadécimal a toujours 64 caractères ;
//   2. écriture (exporter) : ZipFlux.ecrivain à la date du manifeste ; les CSV (compressés ; un CSV abîmé avec ses
//      octets tels quels), puis chaque document : relu, empreinte SHA-256 (Formats.manifeste), ajouté (stocké, sans
//      compression, si son extension est dans DEJA_COMPRESSES), puis oublié avant le suivant (ajouterDocument) ;
//      manifeste.json en dernier. Le ZIP grandit dans un Blob composé, tenu par le navigateur hors de la mémoire
//      JavaScript. Un document disparu ou illisible depuis la passe 1 passe parmi les manquants ; les limites sont
//      recontrôlées sur les tailles écrites, puis sur la taille du ZIP (LIMITES.zip), avant le téléchargement.
//   Coût : en mode serveur, chaque document est téléchargé deux fois (le serveur ne donne pas sa taille seule) ; en
//   mode dossier, la passe 1 ne lit que la taille du fichier ; en démo, les documents sont déjà en mémoire.
//   Navigateur sans « deflate-raw » (ZipFlux.disponible() faux) : rien n'est lu ni produit, fenêtre de refus avec
//   ZipFlux.MESSAGE_NAVIGATEUR (décision de Nicolas : pas de JSZip en secours).
// Avec les comptes (mode serveur), l'export est réservé au responsable : un technicien ou un demandeur reçoit des
// tables filtrées par le serveur (export partiel). En lecture seule (D169), l'export reste permis : il n'écrit rien.
// Dépendances : Schema, Formats, Donnees, UI ; App, ZipFlux et ZipLecture (lus à l'appel, chargés après).

const ZipDonnees = (() => {

  const CHAMPS_DOCUMENTS = Object.freeze([
    Object.freeze(['equipements', 'document']),
    Object.freeze(['demandes', 'photo']),
    Object.freeze(['controles_reglementaires', 'rapport']),
  ]);
  const DOSSIER_DOCUMENTS = 'documents/';
  const NOM_MANIFESTE = 'manifeste.json';
  const MOTIF_EXPORT = 'export';
  // Nom d'un document enregistré : nom demandé (MOTIF_NOM_DOCUMENT de serveur.py et des adaptateurs), précédé ou non
  // de l'horodatage que le serveur impose depuis le lot 7 (« AAAAMMJJ-HHMMSS- », MOTIF_NOM_DOCUMENT_ENREGISTRE).
  const MOTIF_NOM_DOCUMENT = /^(?:[0-9]{8}-[0-9]{6}-)?[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;
  const MOTIF_DATE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/;      // « abime_depuis » (fichiers-abimes.json, T206)
  const raisonReserve = () => I18n.t('zip.raison_reserve.export_zip_reserve_responsable');

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  function deuxChiffres(nombre) {
    return String(nombre).padStart(2, '0');
  }

  // Date et heure du poste : 'AAAA-MM-JJ HH:MM:SS'.
  function dateHeure(date) {
    return date.getFullYear() + '-' + deuxChiffres(date.getMonth() + 1) + '-' + deuxChiffres(date.getDate()) + 'T'
      + deuxChiffres(date.getHours()) + ':' + deuxChiffres(date.getMinutes()) + ':' + deuxChiffres(date.getSeconds());
  }

  /** Vrai si `nom` a la forme d'un nom de document (aucun chemin : ni « / », ni « \ », ni « .. »). */
  function nomDocumentValide(nom) {
    return typeof nom === 'string' && MOTIF_NOM_DOCUMENT.test(nom) && nom.indexOf('..') === -1;
  }

  /**
   * Documents à exporter, sans doublon, dans l'ordre : ceux des trois colonnes (table par table, ligne par ligne),
   * puis les rapports figés (même règle que Rapport.rapportsFiges : rapports_mensuels, séparés par des virgules).
   * tables (facultatif, T214) : { <table>: { lignes } } (un ZIP lu par ZipLecture) au lieu des données chargées.
   */
  function nomsDocuments(tables) {
    const noms = [];
    const ajouter = (nom) => { if (nom && !noms.includes(nom)) noms.push(nom); };
    const lignesDe = (nomTable) => (tables ? (tables[nomTable] || { lignes: [] }).lignes : Donnees.lignes(nomTable));
    CHAMPS_DOCUMENTS.forEach(([nomTable, nomChamp]) => {
      lignesDe(nomTable).forEach((ligne) => ajouter(texte(ligne[nomChamp])));
    });
    const rapports = tables ? (lignesDe('parametres').find((ligne) => ligne.cle === 'rapports_mensuels') || {}).valeur
      : Donnees.parametre('rapports_mensuels', '');
    texte(rapports).split(',').map(texte).forEach(ajouter);
    return noms;
  }

  /** { permis, raison } : avec les comptes, seul le responsable exporte (raison : la phrase à montrer sinon). */
  function exportPermis() {
    const reserve = typeof App !== 'undefined' && App.comptesExiges() && !App.estResponsable();
    return { permis: !reserve, raison: reserve ? raisonReserve() : '' };
  }

  // Blob (ou File) → Uint8Array.
  async function octetsDe(blob) {
    if (blob instanceof Uint8Array) return blob;
    return new Uint8Array(await blob.arrayBuffer());
  }

  // Taille d'un document rendu par l'adaptateur (Blob, File ou Uint8Array), sans lire son contenu ; null s'il manque.
  function tailleDe(document) {
    if (!document) return null;
    return document instanceof Uint8Array ? document.length : document.size;
  }

  function avertirNonExporte(nom, erreur) {
    console.warn('Prévo : document « ' + nom + ' » non exporté (' + (erreur && erreur.message) + ').', erreur);
  }

  // Passe 1 (T208, T228) : la TAILLE de chaque document, sans garder ses octets → { trouves: [{ nom, taille }],
  // manquants: [noms], interrompu }. Un nom invalide n'est jamais lu ; une lecture en erreur (réseau, fichier
  // illisible) compte comme manquante (console.warn). Arrêt (interrompu) dès que les documents dépassent à eux seuls
  // le total décompressé ou le nombre d'entrées de l'import : l'export sera refusé, rien ne sert de tout demander.
  async function lireTailles(adaptateur, noms) {
    const limites = ZipLecture.LIMITES;
    const lus = { trouves: [], manquants: [], interrompu: false };
    let total = 0;
    for (const nom of noms) {
      if (total > limites.total || lus.trouves.length >= limites.entrees) {
        lus.interrompu = true;
        break;
      }
      if (!nomDocumentValide(nom)) {
        lus.manquants.push(nom);
        continue;
      }
      try {
        const taille = tailleDe(await adaptateur.lireDocument(nom));     // le document lui-même est oublié aussitôt
        if (taille === null) {
          lus.manquants.push(nom);
        } else {
          lus.trouves.push({ nom, taille });
          total += taille;
        }
      } catch (erreur) {
        avertirNonExporte(nom, erreur);
        lus.manquants.push(nom);
      }
    }
    return lus;
  }

  // --- Limites de l'import, contrôlées AVANT de produire le ZIP (T208) ---------------------------------------------
  // Règle de Nicolas : tout ce que Prévo exporte, Prévo peut le réimporter. Les limites sont celles de l'import,
  // ZipLecture.LIMITES (js/modules/zip-lecture.js, seul endroit où elles sont écrites), lues ici à l'appel.
  // Documents déjà compressés : le ZIP ne les réduit presque pas (moins de 10 %) ; ils bornent sa taille par en bas,
  // et l'écriture les stocke sans compression (T228).
  const DEJA_COMPRESSES = Object.freeze(['jpg', 'jpeg', 'webp', 'docx', 'xlsx', 'odt', 'ods']);
  const PART_INCOMPRESSIBLE = 0.9;

  function chiffres(nombre) {
    return String(nombre).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  }

  // « 52,3 Mo » ; « plus de <limite> » quand l'arrondi égalerait la limite (la limite et quelques octets).
  function taille(octets, limite) {
    const texte = ZipLecture.enMo(octets);
    return texte === ZipLecture.enMo(limite) ? I18n.t('zip.taille.plus_de', { texte }) : texte;
  }

  // Vrai pour une entrée documents/<nom> dont l'extension est dans DEJA_COMPRESSES.
  function dejaCompresse(nom) {
    const extension = nom.slice(nom.lastIndexOf('.') + 1).toLowerCase();
    return nom.startsWith(DOSSIER_DOCUMENTS) && DEJA_COMPRESSES.includes(extension);
  }

  /** Taille minimale du ZIP de ces entrées ([{ nom, taille }]) : la part incompressible des documents déjà compressés. */
  function tailleMinimaleZip(entrees) {
    return entrees.reduce((somme, entree) => somme
      + (dejaCompresse(entree.nom) ? Math.floor(entree.taille * PART_INCOMPRESSIBLE) : 0), 0);
  }

  /**
   * Ce qui dépasse les limites de l'import dans les entrées du ZIP à produire ([{ nom, taille }], manifeste compris) →
   * phrases (fichier, taille, limite) ; [] si l'import l'acceptera. incomplet : documents pas tous lus (au moins…).
   */
  function depassements(entrees, incomplet) {
    const limites = ZipLecture.LIMITES;
    const phrases = [];
    let total = 0;
    entrees.forEach((entree) => {
      const document = entree.nom.startsWith(DOSSIER_DOCUMENTS);
      const limite = document ? limites.document : limites.racine;
      if (entree.taille > limite) {
        phrases.push(document
          ? I18n.t('zip.depassements.fait_plus_document', { entreeNom: entree.nom, taille: taille(entree.taille, limite), enMo: ZipLecture.enMo(limite) })
          : I18n.t('zip.depassements.fait_plus_fichier_donnees', { entreeNom: entree.nom, taille: taille(entree.taille, limite), enMo: ZipLecture.enMo(limite) }));
      }
      total += entree.taille;
    });
    if (entrees.length > limites.entrees) {
      phrases.push(incomplet
        ? I18n.t('zip.depassements.zip_compterait_moins_fichiers', { n: entrees.length, nombre: chiffres(entrees.length), limite: chiffres(limites.entrees) })
        : I18n.t('zip.depassements.zip_compterait_fichiers_plus', { n: entrees.length, nombre: chiffres(entrees.length), limite: chiffres(limites.entrees) }));
    }
    if (total > limites.total) {
      phrases.push(incomplet
        ? I18n.t('zip.depassements.contenu_ferait_moins_fois', { taille: taille(total, limites.total), enMo: ZipLecture.enMo(limites.total) })
        : I18n.t('zip.depassements.contenu_ferait_fois_decompresse', { taille: taille(total, limites.total), enMo: ZipLecture.enMo(limites.total) }));
    }
    const minimum = tailleMinimaleZip(entrees);
    if (minimum > limites.zip) {
      phrases.push(I18n.t('zip.depassements.zip_ferait_moins_photos', { taille: taille(minimum, limites.zip), enMo: ZipLecture.enMo(limites.zip) }));
    }
    return phrases;
  }

  // Message du refus : ce qui dépasse (quatre phrases au plus), et rien n'est produit.
  function refusDe(phrases) {
    const montrees = phrases.slice(0, 4);
    const autres = phrases.length - montrees.length;
    const texte = montrees.join(' ; ') + (autres > 0 ? ' ' + I18n.t('zip.refus_de.n_autre', { n: autres }) : '');
    return I18n.t('zip.refus_de.export_impossible_import_prevo', { debut: texte.charAt(0).toUpperCase(), suite: texte.slice(1) });
  }

  // Fenêtre du refus (#export-zip-refus), sans attendre qu'elle soit fermée.
  function prevenir(refus) {
    const contenu = UI.element(UI.html`<div class="form-colonne" id="export-zip-refus"></div>`);
    contenu.appendChild(UI.bandeau('important', refus));
    UI.fenetre({ titre: I18n.t('zip.prevenir.export_zip_impossible'), contenu: contenu });
  }

  // --- Avertissement avant un gros export (T222 ; seuil et texte revus par T215) -------------------------------------
  // Seuil sur les octets des fichiers à mettre dans le ZIP (CSV et documents, avant compression). Mesure T215
  // (Chromium, profil sur disque) : le ZIP en cours d'écriture est un Blob composé, dont Chromium garde en mémoire, dans
  // son processus principal, chaque morceau de moins de 5 Mo et les 5 premiers Mo des autres (le reste va sur le disque
  // du profil). Pour 330 Mo de photos de 1 Mo : Chromium entier +0,5 Go, 1,5 fois le ZIP, l'onglet stable vers 0,2 Go ;
  // documents de 9,5 Mo : les deux tiers environ du ZIP. 500 Mo coûtent donc jusqu'à 750 Mo, ce que coûtaient 150 Mo
  // quand JSZip construisait le ZIP dans l'onglet (T212 : 5 à 6 fois) : la même marge sur un PC de 4 Go.
  // Écrit 500 × 1 048 576 (1 Mo) : ce fichier ne recopie aucune limite de l'import (garde-fou de test_zip_limites.py).
  const AVERTISSEMENT = Object.freeze({ contenu: 500 * 1048576 });

  /**
   * Message de l'avertissement pour un résultat de contenu(), ou null : seulement pour un export complet, sans refus,
   * dont les fichiers (somme de leurs `taille`, manifeste compris) dépassent AVERTISSEMENT.contenu.
   */
  function avertissement(resultat) {
    if (resultat.refus || resultat.sansDocuments) return null;
    const octets = resultat.fichiers.reduce((somme, fichier) => somme + fichier.taille, 0);
    if (octets <= AVERTISSEMENT.contenu) return null;
    return I18n.t('zip.avertissement.zip_contiendrait_donnees_documents', { taille: taille(octets, AVERTISSEMENT.contenu) });
  }

  // Fenêtre de l'avertissement (#export-zip-avertissement) → 'seules', 'complet', ou null (Annuler, Échap, croix).
  function demanderSiGros(texte) {
    const contenu = UI.element(UI.html`<div class="form-colonne" id="export-zip-avertissement"></div>`);
    contenu.appendChild(UI.bandeau('attention', texte));
    return UI.fenetre({
      titre: I18n.t('zip.demander_si_gros.export_zip_volumineux'),
      contenu: contenu,
      boutons: [
        { libelle: I18n.t('commun.bouton.annuler'), valeur: null, classe: 'btn-fantome' },
        { libelle: I18n.t('zip.demander_si_gros.continuer_export_complet'), valeur: 'complet', classe: 'btn-secondaire' },
        { libelle: I18n.t('zip.demander_si_gros.exporter_donnees_seules'), valeur: 'seules', classe: 'btn-primaire', defaut: true },
      ],
    });
  }

  // --- Manifeste (préparé par contenu, complété à l'écriture : T228) -------------------------------------------------

  // T213 : l'entrée du manifeste d'un CSV abîmé porte aussi « abime_depuis » (AAAA-MM-JJTHH:MM:SS, depuis quand Prévo
  // le voit abîmé : adaptateur.abimesDepuis, fichiers-abimes.json), que l'import garde telle quelle ; absente si
  // inconnue (démo, date illisible, lecture impossible : l'export n'échoue pas pour autant). decrits : les CSV décrits.
  async function noterDepuis(decrits, abimes, adaptateur) {
    if (!abimes.length || typeof adaptateur.abimesDepuis !== 'function') return;
    let depuis = {};
    try {
      depuis = (await adaptateur.abimesDepuis()) || {};
    } catch (erreur) {
      console.warn('Prévo : date des fichiers abîmés inconnue pour l\'export (' + (erreur && erreur.message) + ').', erreur);
    }
    abimes.forEach((nomTable) => {
      const decrit = decrits.find((fichier) => fichier.nom === Schema.table(nomTable).fichier);
      if (decrit && MOTIF_DATE.test(String(depuis[nomTable] || ''))) decrit.abime_depuis = depuis[nomTable];
    });
  }

  const EMPREINTE_A_VENIR = '0'.repeat(64);        // même longueur qu'une empreinte SHA-256 en hexadécimal

  function parNom(a, b) {                           // ordre de Formats.manifeste
    if (a.nom < b.nom) return -1;
    return a.nom > b.nom ? 1 : 0;
  }

  // Objet de manifeste.json : base = { entete, csv } (préparés par contenu), documents [{ nom, octets, sha256 }],
  // manquants ; mêmes clés, dans le même ordre, que depuis T189 (T210, T213, T214).
  function manifesteDe(base, documents, manquants) {
    const manifeste = Object.assign({}, base.entete, { fichiers: base.csv.concat(documents).sort(parNom) });
    if (manquants.length) manifeste.manquants = manquants.slice();
    return manifeste;
  }

  function octetsDuManifeste(manifeste) {
    return new TextEncoder().encode(JSON.stringify(manifeste, null, 2) + '\n');
  }

  // --- Passe 1 : préparation -----------------------------------------------------------------------------------------

  // Préparation de l'export (voir contenu) → { resume (le résultat de contenu), adaptateur, date, base (en-tête et
  // CSV décrits du manifeste ; null si refus) }.
  async function preparer(options) {
    const reglages = options || {};
    const adaptateur = reglages.adaptateur || App.adaptateur;
    const mode = reglages.mode || App.mode;
    const sansDocuments = reglages.sansDocuments === true;
    const date = reglages.date || new Date();
    const quand = dateHeure(date);
    const instantane = Donnees.instantane();
    // T210 : un CSV abîmé porte « abime » au manifeste, comme dans les sauvegardes (T206, Formats.manifeste), et part
    // avec les octets du fichier tel quel (adaptateur.charger) : le réécrire depuis ce que Prévo en a lu perdrait ce
    // qu'il n'a pas su lire (valeurs au-delà de l'en-tête, lignes fondues), comme une écriture (T197).
    const abimes = Donnees.tablesAbimees();
    const fichiers = await Promise.all(Schema.nomsTables().map(async (nomTable) => {
      const abime = abimes.includes(nomTable);
      const octets = abime ? (await adaptateur.charger(nomTable)).octets : instantane[nomTable];
      return { nom: Schema.table(nomTable).fichier, abime, octets, taille: octets.length };
    }));
    const csv = fichiers.length;
    const documents = sansDocuments ? { trouves: [], manquants: [], interrompu: false }
      : await lireTailles(adaptateur, nomsDocuments());
    documents.trouves.forEach((document) => fichiers.push({
      nom: DOSSIER_DOCUMENTS + document.nom, document: document.nom, taille: document.taille }));
    const tailles = fichiers.map((fichier) => ({ nom: fichier.nom, taille: fichier.taille }))
      .concat([{ nom: NOM_MANIFESTE, taille: 0 }]);       // quelques centaines de Ko au plus
    const phrases = depassements(tailles, documents.interrompu);
    const resume = {
      nomFichier: 'prevo-export-' + quand.slice(0, 10) + (sansDocuments ? '-sans-documents' : '') + '.zip',
      sansDocuments,
      fichiers,
      manifeste: null,
      csv,
      documents: documents.trouves.length,
      manquants: documents.manquants,
      refus: phrases.length ? refusDe(phrases) : null,
    };
    const prepare = { resume, adaptateur, date, base: null };
    if (resume.refus) return prepare;
    const decrit = await Formats.manifeste(fichiers.slice(0, csv), {
      version_appli: App.version,
      format: Formats.versionDeBase(Donnees.lignes('parametres')),
      date: quand,
      motif: MOTIF_EXPORT,
      mode: mode,
    });
    // T214 : « documents »: « exclus » juste avant la liste des fichiers.
    const { fichiers: decrits, ...entete } = decrit;
    if (sansDocuments) entete.documents = 'exclus';
    await noterDepuis(decrits, abimes, adaptateur);
    prepare.base = { entete, csv: decrits };
    const provisoire = manifesteDe(prepare.base, documents.trouves.map((document) => ({
      nom: DOSSIER_DOCUMENTS + document.nom, octets: document.taille, sha256: EMPREINTE_A_VENIR })), documents.manquants);
    fichiers.push({ nom: NOM_MANIFESTE, taille: octetsDuManifeste(provisoire).length });
    return prepare;
  }

  /**
   * Contenu du ZIP à produire, sans rien télécharger ni écrire, ni lire le contenu d'un document → Promise de
   * { nomFichier, sansDocuments, fichiers: [{ nom, taille, … }], manifeste, csv, documents, manquants, refus } :
   *   - fichiers : les entrées du ZIP dans l'ordre (CSV du schéma, documents/<nom>, manifeste.json en dernier), chacune
   *     avec sa taille en octets ; un CSV porte aussi ses octets (`octets`, `abime`), un document le nom à relire
   *     (`document`) : ses octets ne sont lus qu'à l'écriture (T228) ;
   *   - manifeste : null (l'objet écrit dans manifeste.json une fois le ZIP écrit par exporter) ; csv, documents :
   *     nombres de fichiers ; manquants : noms ;
   *   - refus : null, ou le message quand une limite de l'import serait dépassée (depassements, T208) : fichiers est
   *     alors sans manifeste.json (rien ne doit en être produit).
   * Lit les données en mémoire telles quelles : exporter() appelle Donnees.rafraichir() avant.
   * options.adaptateur (défaut App.adaptateur), options.mode (défaut App.mode), options.date (défaut maintenant),
   * options.sansDocuments (T214 : données seules, aucun document lu ; résultat `sansDocuments` vrai).
   */
  async function contenu(options) {
    return (await preparer(options)).resume;
  }

  // --- Passe 2 : écriture (T228) -------------------------------------------------------------------------------------

  // Un document : relu, décrit (empreinte par Formats.manifeste : crypto.subtle, sinon le repli en JavaScript), ajouté
  // au ZIP → Promise de { nom, octets, sha256 }, ou null s'il a disparu ou ne se lit plus depuis la passe 1. Ses
  // octets ne vivent que le temps de cet appel : le document suivant n'est demandé qu'après.
  async function ajouterDocument(ecrivain, adaptateur, fichier) {
    try {
      const lu = await adaptateur.lireDocument(fichier.document);
      if (!lu) return null;
      const octets = await octetsDe(lu);
      const decrit = (await Formats.manifeste([{ nom: fichier.nom, octets }])).fichiers[0];
      await ecrivain.ajouter(fichier.nom, octets, { stocker: dejaCompresse(fichier.nom) });
      return decrit;
    } catch (erreur) {
      if (erreur instanceof ZipFlux.ErreurZip) throw erreur;   // refus de l'écrivain : exporter le montre
      avertirNonExporte(fichier.document, erreur);             // lecture en erreur : aucune trace dans le ZIP
      return null;
    }
  }

  // Écrit le ZIP préparé (preparer, sans refus) → Promise du Blob du ZIP, ou null si les tailles réellement écrites
  // dépassent une limite de l'import (resume.refus est alors posé). Complète le résumé : fichiers (tels qu'écrits),
  // manifeste (les vraies empreintes), documents et manquants (un document perdu depuis la passe 1 y passe).
  async function ecrire(prepare) {
    const resume = prepare.resume;
    const ecrivain = ZipFlux.ecrivain({ date: prepare.date });
    const ecrits = [];
    const manquants = resume.manquants.slice();
    const fichiers = [];
    for (const fichier of resume.fichiers) {
      if (fichier.nom === NOM_MANIFESTE) continue;
      if (fichier.document === undefined) {
        await ecrivain.ajouter(fichier.nom, fichier.octets);
        fichiers.push(fichier);
        continue;
      }
      const decrit = await ajouterDocument(ecrivain, prepare.adaptateur, fichier);
      if (!decrit) {
        manquants.push(fichier.document);
        continue;
      }
      ecrits.push(decrit);
      fichiers.push({ nom: fichier.nom, document: fichier.document, taille: decrit.octets });
    }
    const manifeste = manifesteDe(prepare.base, ecrits, manquants);
    const octets = octetsDuManifeste(manifeste);
    await ecrivain.ajouter(NOM_MANIFESTE, octets);
    fichiers.push({ nom: NOM_MANIFESTE, taille: octets.length });
    Object.assign(resume, { fichiers, manifeste, documents: ecrits.length, manquants });
    const phrases = depassements(fichiers, false);
    if (phrases.length) {
      resume.refus = refusDe(phrases);
      return null;
    }
    return ecrivain.terminer();
  }

  // Message montré après l'export (inchangé depuis le lot 1, plus les noms des documents introuvables).
  function message(resultat) {
    let phrase = I18n.t('zip.message.export_telecharge_fichiers_csv', { n: resultat.csv });
    if (resultat.sansDocuments) return I18n.t('zip.message.sans_documents_donnees_seules', { phrase });
    if (resultat.documents) phrase += ' ' + I18n.t('zip.message.n_document', { n: resultat.documents });
    if (resultat.manquants.length) {
      const montres = resultat.manquants.slice(0, 3).join(', ') + (resultat.manquants.length > 3 ? I18n.t('zip.message.liste_tronquee') : '');
      phrase += ' ' + I18n.t('zip.message.document_introuvable_liste_manifeste', { n: resultat.manquants.length, montres });
    }
    return phrase + '.';
  }

  /**
   * Export en un clic : vérifie le droit (exportPermis), relit les tables (Donnees.rafraichir), prépare le ZIP
   * (contenu), l'écrit (ecrire, T228 : par ZipFlux, un document à la fois), propose le téléchargement (UI.telecharger)
   * et le dit (toast). Promise du résultat de contenu(), complété par l'écriture ; rejetée (ErreurValidation, avec la
   * raison) pour un rôle qui n'a pas l'export, ou si le ZIP ne s'écrit pas.
   * T208 : si l'import refuserait le ZIP (contenu().refus, puis les tailles écrites et la taille réelle du ZIP), rien
   * n'est téléchargé : fenêtre #export-zip-refus qui dit quoi (fichier, taille, limite) ; le résultat porte `refus`.
   * T228 : navigateur sans « deflate-raw » : même fenêtre, avec ZipFlux.MESSAGE_NAVIGATEUR, avant toute lecture
   * (résultat { fichiers: [], manquants: [], refus }) ; une ErreurZip de l'écriture est montrée de même.
   * options.sansDocuments (T214) : données seules, sans les documents (mêmes contrôles des limites).
   * T222 : avant un export complet de plus de AVERTISSEMENT.contenu, fenêtre #export-zip-avertissement (avertissement,
   * demanderSiGros) : « données seules » refait la préparation sans les documents ; « Annuler » ne produit rien
   * (résultat `annule` vrai, `fichiers` vidé) ; « Continuer l'export complet » écrit le ZIP complet.
   */
  async function exporter(options) {
    const droit = exportPermis();
    if (!droit.permis) throw new Donnees.ErreurValidation(droit.raison);
    if (!ZipFlux.disponible()) {
      prevenir(ZipFlux.MESSAGE_NAVIGATEUR);
      return { fichiers: [], manquants: [], refus: ZipFlux.MESSAGE_NAVIGATEUR };
    }
    try {
      await Donnees.rafraichir();                      // journal à jour (écrit par ajout)
    } catch (erreur) {
      console.warn('Prévo : rafraîchissement avant export impossible (' + (erreur && erreur.message) + ').', erreur);
    }
    let prepare = await preparer({ sansDocuments: Boolean(options) && options.sansDocuments === true });
    const texte = avertissement(prepare.resume);
    if (texte) {
      const choix = await demanderSiGros(texte);
      if (choix === null) return Object.assign(prepare.resume, { fichiers: [], annule: true });
      if (choix === 'seules') prepare = await preparer({ sansDocuments: true });
    }
    const resultat = prepare.resume;
    if (!resultat.refus) {
      let blob = null;
      try {
        blob = await ecrire(prepare);
      } catch (erreur) {
        if (!(erreur instanceof ZipFlux.ErreurZip)) throw erreur;
        resultat.refus = erreur.message;
      }
      const limite = ZipLecture.LIMITES.zip;
      if (blob && blob.size <= limite) {
        UI.telecharger(resultat.nomFichier, blob);
        UI.toast(message(resultat), resultat.manquants.length ? 'attention' : 'succes');
        return resultat;
      }
      if (blob) {
        resultat.refus = refusDe([I18n.t('zip.exporter.zip_ferait_plus', { taille: taille(blob.size, limite), enMo: ZipLecture.enMo(limite) })]);
      }
    }
    prevenir(resultat.refus);
    return resultat;
  }

  return {
    CHAMPS_DOCUMENTS,
    NOM_MANIFESTE,
    AVERTISSEMENT,
    nomDocumentValide,
    nomsDocuments,
    exportPermis,
    depassements,
    avertissement,
    contenu,
    exporter,
  };
})();
