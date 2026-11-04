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
//     format de la base, date « AAAA-MM-JJ HH:MM:SS » du poste, motif « export », mode serveur | dossier | demo,
//     fichiers [{ nom, octets, sha256 }]) ; s'il en manque, `manquants` : les documents cités introuvables.
// Jamais rien de acces/ (comptes, sessions, appareils) ni d'autre dossier : un nom cité n'est lu que s'il a la forme
// d'un nom de document (MOTIF_NOM_DOCUMENT, mêmes règles que serveur.py : ni « / », ni « \ », ni « .. ») ; sinon il
// est compté parmi les manquants, sans aucune lecture. Un document introuvable n'arrête pas l'export.
// Avec les comptes (mode serveur), l'export est réservé au responsable : un technicien ou un demandeur reçoit des
// tables filtrées par le serveur (export partiel). En lecture seule (D169), l'export reste permis : il n'écrit rien.
// Dépendances : JSZip (js/lib/jszip.min.js), Schema, Formats, Donnees, UI ; App (lu à l'appel, chargé après).

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
  const RAISON_RESERVE = 'L\'export ZIP est réservé au responsable : avec les comptes, les autres rôles ne voient '
    + 'qu\'une partie des données, et l\'export serait incomplet.';

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  function deuxChiffres(nombre) {
    return String(nombre).padStart(2, '0');
  }

  // Date et heure du poste : 'AAAA-MM-JJ HH:MM:SS'.
  function dateHeure(date) {
    return date.getFullYear() + '-' + deuxChiffres(date.getMonth() + 1) + '-' + deuxChiffres(date.getDate()) + ' '
      + deuxChiffres(date.getHours()) + ':' + deuxChiffres(date.getMinutes()) + ':' + deuxChiffres(date.getSeconds());
  }

  /** Vrai si `nom` a la forme d'un nom de document (aucun chemin : ni « / », ni « \ », ni « .. »). */
  function nomDocumentValide(nom) {
    return typeof nom === 'string' && MOTIF_NOM_DOCUMENT.test(nom) && nom.indexOf('..') === -1;
  }

  /**
   * Documents à exporter, sans doublon, dans l'ordre : ceux des trois colonnes (table par table, ligne par ligne),
   * puis les rapports figés (même règle que Rapport.rapportsFiges : rapports_mensuels, séparés par des virgules).
   */
  function nomsDocuments() {
    const noms = [];
    const ajouter = (nom) => { if (nom && !noms.includes(nom)) noms.push(nom); };
    CHAMPS_DOCUMENTS.forEach(([nomTable, nomChamp]) => {
      Donnees.lignes(nomTable).forEach((ligne) => ajouter(texte(ligne[nomChamp])));
    });
    texte(Donnees.parametre('rapports_mensuels', '')).split(',').map(texte).forEach(ajouter);
    return noms;
  }

  /** { permis, raison } : avec les comptes, seul le responsable exporte (raison : la phrase à montrer sinon). */
  function exportPermis() {
    const reserve = typeof App !== 'undefined' && App.comptesExiges() && !App.estResponsable();
    return { permis: !reserve, raison: reserve ? RAISON_RESERVE : '' };
  }

  // Blob (ou File) → Uint8Array.
  async function octetsDe(blob) {
    if (blob instanceof Uint8Array) return blob;
    return new Uint8Array(await blob.arrayBuffer());
  }

  // Lit chaque document par l'adaptateur → { trouves: [{ nom, octets }], manquants: [noms] }. Un nom invalide n'est
  // jamais lu ; une lecture en erreur (réseau, fichier illisible) compte comme manquante (console.warn).
  async function lireDocuments(adaptateur, noms) {
    const trouves = [];
    const manquants = [];
    for (const nom of noms) {
      if (!nomDocumentValide(nom)) {
        manquants.push(nom);
        continue;
      }
      try {
        const blob = await adaptateur.lireDocument(nom);
        if (blob) trouves.push({ nom, octets: await octetsDe(blob) });
        else manquants.push(nom);
      } catch (erreur) {
        console.warn('Prévo : document « ' + nom + ' » non exporté (' + (erreur && erreur.message) + ').', erreur);
        manquants.push(nom);
      }
    }
    return { trouves, manquants };
  }

  /**
   * Contenu du ZIP, sans rien télécharger ni écrire → Promise de
   * { nomFichier, fichiers: [{ nom, octets }], manifeste, csv, documents, manquants } :
   *   - fichiers : les entrées du ZIP dans l'ordre (CSV du schéma, documents/<nom>, manifeste.json en dernier) ;
   *   - manifeste : l'objet écrit dans manifeste.json ; csv, documents : nombres de fichiers ; manquants : noms.
   * Lit les données en mémoire telles quelles : exporter() appelle Donnees.rafraichir() avant.
   * options.adaptateur (défaut App.adaptateur), options.mode (défaut App.mode), options.date (défaut maintenant).
   */
  async function contenu(options) {
    const reglages = options || {};
    const adaptateur = reglages.adaptateur || App.adaptateur;
    const mode = reglages.mode || App.mode;
    const quand = dateHeure(reglages.date || new Date());
    const instantane = Donnees.instantane();
    const fichiers = Schema.nomsTables().map((nomTable) => ({
      nom: Schema.table(nomTable).fichier, octets: instantane[nomTable],
    }));
    const documents = await lireDocuments(adaptateur, nomsDocuments());
    documents.trouves.forEach((document) => fichiers.push({ nom: DOSSIER_DOCUMENTS + document.nom, octets: document.octets }));
    const manifeste = await Formats.manifeste(fichiers, {
      version_appli: App.version,
      format: Formats.versionDeBase(Donnees.lignes('parametres')),
      date: quand,
      motif: MOTIF_EXPORT,
      mode: mode,
    });
    if (documents.manquants.length) manifeste.manquants = documents.manquants.slice();
    const nombreCsv = fichiers.length - documents.trouves.length;
    fichiers.push({ nom: NOM_MANIFESTE, octets: new TextEncoder().encode(JSON.stringify(manifeste, null, 2) + '\n') });
    return {
      nomFichier: 'prevo-export-' + quand.slice(0, 10) + '.zip',
      fichiers,
      manifeste,
      csv: nombreCsv,
      documents: documents.trouves.length,
      manquants: documents.manquants,
    };
  }

  // Message montré après l'export (inchangé depuis le lot 1, plus les noms des documents introuvables).
  function message(resultat) {
    let phrase = 'Export téléchargé : ' + resultat.csv + ' fichiers CSV';
    if (resultat.documents) phrase += ' et ' + resultat.documents + ' document(s)';
    if (resultat.manquants.length) {
      const montres = resultat.manquants.slice(0, 3).join(', ') + (resultat.manquants.length > 3 ? '…' : '');
      phrase += ' (' + resultat.manquants.length + ' document(s) introuvable(s) : ' + montres
        + ' ; liste dans manifeste.json)';
    }
    return phrase + '.';
  }

  /**
   * Export en un clic : vérifie le droit (exportPermis), relit les tables (Donnees.rafraichir), construit le ZIP
   * (contenu), propose le téléchargement (UI.telecharger) et le dit (toast). Promise du résultat de contenu() ;
   * rejetée (ErreurValidation, avec la raison) pour un rôle qui n'a pas l'export, ou si le ZIP ne se construit pas.
   */
  async function exporter() {
    const droit = exportPermis();
    if (!droit.permis) throw new Donnees.ErreurValidation(droit.raison);
    try {
      await Donnees.rafraichir();                      // journal à jour (écrit par ajout)
    } catch (erreur) {
      console.warn('Prévo : rafraîchissement avant export impossible (' + (erreur && erreur.message) + ').', erreur);
    }
    const resultat = await contenu();
    const archive = new JSZip();
    // createFolders : false → aucune entrée « documents/ » de dossier, seulement les fichiers (lus par ZipLecture).
    resultat.fichiers.forEach((fichier) => archive.file(fichier.nom, fichier.octets, { createFolders: false }));
    const blob = await archive.generateAsync({ type: 'blob', compression: 'DEFLATE', mimeType: 'application/zip' });
    UI.telecharger(resultat.nomFichier, blob);
    UI.toast(message(resultat), resultat.manquants.length ? 'attention' : 'succes');
    return resultat;
  }

  return {
    CHAMPS_DOCUMENTS,
    NOM_MANIFESTE,
    nomDocumentValide,
    nomsDocuments,
    exportPermis,
    contenu,
    exporter,
  };
})();
