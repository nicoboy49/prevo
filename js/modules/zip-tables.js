'use strict';
// ZipTables : les tables d'un ZIP de données, lues et contrôlées SANS RIEN ÉCRIRE (étape 11 de ZipLecture, sortie de
// zip-lecture.js arrivé à 700 lignes, T213). Ordre de chargement : §15.1, juste avant zip-lecture.js, seul appelant :
// ZipTables.lire n'est appelé qu'APRÈS le contrôle du manifeste (étape 10 de ZipLecture : chaque fichier du ZIP y a
// sa taille et son empreinte SHA-256 justes, et réciproquement).
//
// ZipTables.lire(contenus, fichiersTables, deja, manifeste) — contenus : Map « <table>.csv » → octets décompressés ;
// fichiersTables : Map « <table>.csv » → nom de la table, dans l'ordre du schéma ; deja : tables déjà analysées
// ({ parametres }) ; manifeste : le manifeste vérifié, ou null → { refus: '<message clair>' }, ou
// { refus: null, tables, absentes, problemes, formatOrigine, migre, abimes } :
//   - un CSV illisible (format 0 : des colonnes du format 1 manquent à l'en-tête) ou abîmé (Donnees.csv.analyser,
//     `abime` : le réécrire en perdrait une partie) est refusé : on ne remplace pas une base par un fichier illisible.
//     SAUF s'il est marqué « abime »: true au manifeste (T213, option B de Nicolas : un fichier marqué abîmé par Prévo
//     n'est accepté à l'import que si son empreinte correspond à celle du manifeste, ce que l'étape 10 a vérifié ; sans
//     marque, refus comme avant). Il est alors dans `abimes` : [{ table, fichier, octets, depuis }] (octets du ZIP, à
//     écrire tels quels, sans aucune réparation ; depuis : « abime_depuis » du manifeste, AAAA-MM-JJTHH:MM:SS, ou
//     null). Ses lignes lues restent dans `tables` (nombres de la confirmation) ; il ne compte pas dans le format
//     d'origine, n'est pas migré, et ses problèmes de lecture ne sont pas repris (la confirmation le dit en une
//     phrase ; Paramètres › Contrôle de la base les détaillera après l'import). Un CSV marqué mais sain est lu comme
//     les autres ;
//   - tables : { <table>: { entete, lignes, colonnesInconnues } } pour chaque table du format courant ;
//   - formatOrigine : format du manifeste, sinon version_schema de parametres.csv (Formats.versionDeBase), ramené au
//     plus petit format des fichiers non vides (comme Donnees.etatDuFormat) ; migre : vrai si les tables ont été
//     passées au format courant en mémoire (Formats.migrer) ;
//   - absentes : tables absentes du ZIP (l'import les videra), dans l'ordre du schéma : une table vide chacune (sauf
//     parametres quand la migration la crée) et un problème. T393 : une table nouvelle (absente du format d'origine)
//     que la migration a remplie (reserves_controle, réserves reprises des observations des contrôles, D183) n'est
//     pas vidée par l'import : elle n'est pas dans `absentes` ; son problème (info) dit combien de lignes elle aura ;
//   - problemes : problèmes de lecture des CSV, puis tables absentes (forme des problèmes de Donnees, §5.2).
// Dépendances : Schema, Formats, Donnees (csv.analyser).

const ZipTables = (function () {

  const MOTIF_DATE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/;      // « abime_depuis » (fichiers-abimes.json, T206)

  // Problème au format de Donnees (ARCHITECTURE.md §5.2).
  function probleme(gravite, type, table, message) {
    return { gravite: gravite, type: type, table: table, ligne: null, id: null, champ: null, valeur: null,
      message: message };
  }

  // Raison de refuser un CSV lu (format 0 : en-tête illisible ; abîmé : le réécrire en perdrait une partie), ou null.
  function raisonCsvIllisible(nomTable, lu) {
    if (lu.entete.length > 0 && Formats.formatDuFichier(nomTable, lu.entete) === 0) {
      return I18n.t('zip.raison_csv_illisible.ligne_tete_incomplete_illisible');
    }
    return lu.abime ? I18n.t('zip.raison_csv_illisible.structure_abimee_lignes_ont') : null;
  }

  // Fichiers marqués « abime »: true par le manifeste (T213) → Map nom → date « abime_depuis » (ou null si absente
  // ou mal formée).
  function marquesAbime(manifeste) {
    const marques = new Map();
    (manifeste ? manifeste.fichiers : []).forEach(function (fichier) {
      if (fichier.abime !== true) { return; }
      const depuis = fichier.abime_depuis;
      marques.set(fichier.nom, typeof depuis === 'string' && MOTIF_DATE.test(depuis) ? depuis : null);
    });
    return marques;
  }

  // Tables lues, leurs problèmes de lecture, les fichiers abîmés acceptés (marqués) et le plus petit format des
  // fichiers non vides et sains (Infinity s'il n'y en a pas) ; { refus } au premier CSV illisible non marqué.
  function lireTables(contenus, fichiersTables, deja, marques) {
    const tables = {};
    const problemes = [];
    const abimes = [];
    let formatFichiers = Infinity;
    for (const [fichier, nomTable] of fichiersTables) {
      if (!contenus.has(fichier)) { continue; }
      const lu = deja[nomTable] || Donnees.csv.analyser(nomTable, contenus.get(fichier));
      const raison = raisonCsvIllisible(nomTable, lu);
      if (raison && !marques.has(fichier)) {
        return { refus: I18n.t('zip.lire_tables.illisible_remplace_pas_base', { fichier, raison }) };
      }
      tables[nomTable] = { entete: lu.entete, lignes: lu.lignes, colonnesInconnues: lu.colonnesInconnues };
      if (raison) {
        abimes.push({ table: nomTable, fichier: fichier, octets: contenus.get(fichier), depuis: marques.get(fichier) });
        continue;
      }
      if (lu.entete.length > 0) { formatFichiers = Math.min(formatFichiers, Formats.formatDuFichier(nomTable, lu.entete)); }
      Array.prototype.push.apply(problemes, lu.problemes);
    }
    return { refus: null, tables: tables, problemes: problemes, abimes: abimes, formatFichiers: formatFichiers };
  }

  // Tables absentes du ZIP : un problème chacune, et une table vide (en-tête du format courant) si la migration ne
  // l'a pas déjà créée (elle crée parametres avec sa ligne version_schema). Une table nouvelle que la migration a
  // remplie (étape 3→4 : reserves_controle, D183) n'est pas vidée par l'import : hors de `absentes` (T393).
  function completerAbsentes(tables, presentes, formatOrigine) {
    const absentes = [];
    const problemes = [];
    for (const nomTable of Schema.nomsTables()) {
      if (presentes.indexOf(nomTable) >= 0) { continue; }
      const description = Schema.table(nomTable);
      if (!Object.prototype.hasOwnProperty.call(tables, nomTable)) {
        tables[nomTable] = { entete: Formats.colonnes(nomTable), lignes: [], colonnesInconnues: [] };
      } else if (!Array.isArray(tables[nomTable].colonnesInconnues)) {
        tables[nomTable].colonnesInconnues = [];
      }
      const nouvelle = Formats.tables(formatOrigine).indexOf(nomTable) < 0;
      const remplies = nouvelle ? tables[nomTable].lignes.length : 0;
      if (!remplies) { absentes.push(nomTable); }
      let suite = I18n.t('zip.completer_absentes.absent_zip_import_videra');
      if (remplies) {
        suite = I18n.t('zip.completer_absentes.existait_pas_format_remplie',
          { formatOrigine, n: remplies, format: Formats.courant });
      } else if (nouvelle) {
        suite = I18n.t('zip.completer_absentes.existait_pas_format_table', { formatOrigine });
      }
      problemes.push(probleme(nouvelle ? 'info' : 'attention', 'table', nomTable,
        description.libelle + ' : ' + description.fichier + ' ' + suite));
    }
    return { absentes: absentes, problemes: problemes };
  }

  // Lecture des tables du ZIP (voir l'en-tête).
  function lire(contenus, fichiersTables, deja, manifeste) {
    const lues = lireTables(contenus, fichiersTables, deja, marquesAbime(manifeste));
    if (lues.refus) { return { refus: lues.refus }; }
    const formatBase = manifeste && Number.isInteger(manifeste.format) ? manifeste.format
      : Formats.versionDeBase(deja.parametres ? deja.parametres.lignes : []);
    const formatOrigine = Math.max(1, Math.min(formatBase, lues.formatFichiers));
    const presentes = Object.keys(lues.tables);
    const abimees = lues.abimes.map(function (abime) { return abime.table; });
    const saines = {};
    presentes.forEach(function (nomTable) { if (abimees.indexOf(nomTable) < 0) { saines[nomTable] = lues.tables[nomTable]; } });
    const tables = formatOrigine < Formats.courant
      ? Formats.migrer({ tables: saines }, formatOrigine, Formats.courant).base.tables : saines;
    abimees.forEach(function (nomTable) { tables[nomTable] = lues.tables[nomTable]; });     // telles que lues
    const absentes = completerAbsentes(tables, presentes, formatOrigine);
    return { refus: null, tables: tables, absentes: absentes.absentes, problemes: lues.problemes.concat(absentes.problemes),
      formatOrigine: formatOrigine, migre: formatOrigine < Formats.courant, abimes: lues.abimes };
  }

  return { lire: lire };
})();
