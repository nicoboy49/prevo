'use strict';
// Donnees : accès aux données de Prévo (les 22 fichiers CSV décrits par js/schema.js).
// Contrat : docs/ARCHITECTURE.md §3 (format des CSV) et §5 (Donnees).
// Ce fichier contient, dans l'ordre :
//   1. les erreurs propres à Prévo ;
//   2. les dates, nombres et la normalisation des valeurs saisies à la main ;
//   3. la lecture et l'écriture des CSV (protection par apostrophe, lecture tolérante) ;
//   4. le chargement, les mutations, le journal et le rafraîchissement (tâche T08).
// Toute valeur en mémoire est une CHAÎNE au format du fichier : dates ISO, booléens 0/1,
// point décimal. Dépendances : Schema (js/schema.js) et Papa (js/lib/papaparse.min.js).

const Donnees = (() => {

  // ===========================================================================
  // 1. Erreurs
  // ===========================================================================

  // Le fichier a été modifié ailleurs depuis notre lecture (version périmée).
  // versionActuelle : la version que le stockage a trouvée (null si inconnue).
  class ErreurConflit extends Error {
    constructor(message, versionActuelle) {
      super(message || 'Le fichier a été modifié en même temps sur un autre poste.');
      this.name = 'ErreurConflit';
      this.versionActuelle = versionActuelle === undefined ? null : versionActuelle;
    }
  }

  // Action refusée par une règle métier : le message est montré tel quel à l'utilisateur.
  // Une ErreurValidation n'est jamais réessayée.
  class ErreurValidation extends Error {
    constructor(message) {
      super(message || 'Action refusée.');
      this.name = 'ErreurValidation';
    }
  }

  // Lecture ou écriture impossible (ex. fichier ouvert dans Excel). Message en français.
  // cause : l'erreur d'origine, gardée pour le diagnostic (facultative).
  class ErreurStockage extends Error {
    constructor(message, cause) {
      super(message || 'Lecture ou écriture du fichier impossible.');
      this.name = 'ErreurStockage';
      this.cause = cause === undefined ? null : cause;
    }
  }

  // ===========================================================================
  // 2. Dates, nombres, normalisation
  // ===========================================================================
  // Chaque fonction de « normaliser » reçoit une valeur lue dans un fichier (éventuellement
  // retouchée dans Excel) et renvoie { valeur, ok } :
  //   - ok = true  : valeur est la forme canonique (ou '' si la cellule est vide) ;
  //   - ok = false : valeur illisible, renvoyée brute (sans les espaces des bords).

  // Expressions régulières compilées une seule fois (performance de la lecture).
  const MOTIF_DATE_ISO = /^(\d{4})-(\d{1,2})-(\d{1,2})$/;
  const MOTIF_DATE_FRANCAISE = /^(\d{1,2})([/.-])(\d{1,2})\2(\d{4})$/;   // JJ/MM/AAAA, J/M/AAAA, JJ-MM-AAAA, JJ.MM.AAAA
  const MOTIF_DATE_ET_HEURE = /^([0-9/.-]+)(?:(?:\s+|T)(\d{1,2}):(\d{2})(?::(\d{2}))?)?$/;
  const MOTIF_ESPACES = /[\s\u00A0\u202F]+/g;                            // y compris insécables
  const MOTIF_DECIMAL = /^([+-]?)(\d*)(?:\.(\d*))?$/;
  const MOTIF_ENTIER = /^([+-]?)(\d+)(?:\.0*)?$/;                         // « 12.0 » accepté → « 12 »
  const MOTIF_ACCENTS = /[\u0300-\u036f]/g;

  const VALEURS_BOOLEENNES = {
    '1': '1', '0': '0',
    'vrai': '1', 'faux': '0',
    'oui': '1', 'non': '0',
    'true': '1', 'false': '0',
    'x': '1',
  };

  function deuxChiffres(nombreEntier) {
    return String(nombreEntier).padStart(2, '0');
  }

  // Date JavaScript (heure locale) → 'AAAA-MM-JJ'.
  function formaterDate(date) {
    return date.getFullYear() + '-' + deuxChiffres(date.getMonth() + 1) + '-' + deuxChiffres(date.getDate());
  }

  // Date du jour, heure locale : 'AAAA-MM-JJ'.
  function aujourdhui() {
    return formaterDate(new Date());
  }

  // Date et heure actuelles, heure locale : 'AAAA-MM-JJ HH:MM'.
  function maintenant() {
    const date = new Date();
    return formaterDate(date) + ' ' + deuxChiffres(date.getHours()) + ':' + deuxChiffres(date.getMinutes());
  }

  // Texte sans accents, en minuscules (pour comparer « Arrêt » et « arret »).
  function sansAccentsMinuscules(texte) {
    return texte.normalize('NFD').replace(MOTIF_ACCENTS, '').toLowerCase();
  }

  function enTexte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur);
  }

  // Vérifie qu'un jour existe vraiment (pas de 31/02) et renvoie 'AAAA-MM-JJ', sinon null.
  function dateIsoSiValide(annee, mois, jour) {
    const a = Number(annee);
    const m = Number(mois);
    const j = Number(jour);
    if (m < 1 || m > 12 || j < 1) { return null; }
    const joursDuMois = new Date(Date.UTC(a, m, 0)).getUTCDate();   // jour 0 du mois suivant
    if (j > joursDuMois) { return null; }
    return String(a).padStart(4, '0') + '-' + deuxChiffres(m) + '-' + deuxChiffres(j);
  }

  // Partie « date » seule : renvoie 'AAAA-MM-JJ' ou null.
  function lireDate(texte) {
    let morceaux = MOTIF_DATE_ISO.exec(texte);
    if (morceaux) { return dateIsoSiValide(morceaux[1], morceaux[2], morceaux[3]); }
    morceaux = MOTIF_DATE_FRANCAISE.exec(texte);
    if (morceaux) { return dateIsoSiValide(morceaux[4], morceaux[3], morceaux[1]); }
    return null;
  }

  // Date : AAAA-MM-JJ, JJ/MM/AAAA, J/M/AAAA, JJ-MM-AAAA, JJ.MM.AAAA → 'AAAA-MM-JJ'.
  function normaliserDate(brut) {
    const texte = enTexte(brut).trim();
    if (texte === '') { return { valeur: '', ok: true }; }
    const iso = lireDate(texte);
    return iso ? { valeur: iso, ok: true } : { valeur: texte, ok: false };
  }

  // Date et heure : une date (formats ci-dessus) suivie de HH:MM ou HH:MM:SS, séparées par une
  // espace ou par « T » → 'AAAA-MM-JJ HH:MM' (secondes ignorées ; date seule → 00:00).
  function normaliserDateHeure(brut) {
    const texte = enTexte(brut).trim();
    if (texte === '') { return { valeur: '', ok: true }; }
    const morceaux = MOTIF_DATE_ET_HEURE.exec(texte);
    const iso = morceaux ? lireDate(morceaux[1]) : null;
    if (!iso) { return { valeur: texte, ok: false }; }
    if (morceaux[2] === undefined) { return { valeur: iso + ' 00:00', ok: true }; }
    const heures = Number(morceaux[2]);
    const minutes = Number(morceaux[3]);
    const secondes = morceaux[4] === undefined ? 0 : Number(morceaux[4]);
    if (heures > 23 || minutes > 59 || secondes > 59) { return { valeur: texte, ok: false }; }
    return { valeur: iso + ' ' + deuxChiffres(heures) + ':' + deuxChiffres(minutes), ok: true };
  }

  // Nombre décimal : virgule → point, espaces (y compris insécables) retirés, « + » retiré.
  // « 7,5 » → « 7.5 » ; « 1 234,50 » → « 1234.50 » ; « ,5 » → « 0.5 ».
  function normaliserDecimal(brut) {
    const texte = enTexte(brut).trim();
    if (texte === '') { return { valeur: '', ok: true }; }
    const compact = texte.replace(MOTIF_ESPACES, '').replace(',', '.');
    const morceaux = MOTIF_DECIMAL.exec(compact);
    if (!morceaux || (morceaux[2] === '' && !morceaux[3])) { return { valeur: texte, ok: false }; }
    const signe = morceaux[1] === '-' ? '-' : '';
    const partieEntiere = morceaux[2] === '' ? '0' : morceaux[2];
    const partieDecimale = morceaux[3] ? '.' + morceaux[3] : '';
    return { valeur: signe + partieEntiere + partieDecimale, ok: true };
  }

  // Nombre entier : mêmes nettoyages que normaliserDecimal ; « 12,0 » accepté → « 12 ».
  function normaliserEntier(brut) {
    const texte = enTexte(brut).trim();
    if (texte === '') { return { valeur: '', ok: true }; }
    const compact = texte.replace(MOTIF_ESPACES, '').replace(',', '.');
    const morceaux = MOTIF_ENTIER.exec(compact);
    if (!morceaux) { return { valeur: texte, ok: false }; }
    return { valeur: (morceaux[1] === '-' ? '-' : '') + morceaux[2], ok: true };
  }

  // Booléen : 1, 0, vrai, faux, oui, non, true, false, x (casse ignorée) → '1' / '0'.
  function normaliserBooleen(brut) {
    const texte = enTexte(brut).trim();
    if (texte === '') { return { valeur: '', ok: true }; }
    const canonique = VALEURS_BOOLEENNES[texte.toLowerCase()];
    return canonique ? { valeur: canonique, ok: true } : { valeur: texte, ok: false };
  }

  // Pour chaque liste de valeurs du schéma : Map « valeur sans casse ni accents » → canonique.
  const correspondancesChoix = new WeakMap();

  function correspondanceChoix(valeursPossibles) {
    let correspondance = correspondancesChoix.get(valeursPossibles);
    if (!correspondance) {
      correspondance = new Map();
      for (const valeurCanonique of valeursPossibles) {
        correspondance.set(sansAccentsMinuscules(valeurCanonique), valeurCanonique);
      }
      correspondancesChoix.set(valeursPossibles, correspondance);
    }
    return correspondance;
  }

  // Choix : comparaison sans casse ni accents (espaces multiples réduits) → valeur canonique.
  // valeursPossibles : le tableau `valeurs` du champ dans le schéma.
  function normaliserChoix(brut, valeursPossibles) {
    const texte = enTexte(brut).trim();
    if (texte === '') { return { valeur: '', ok: true }; }
    const liste = valeursPossibles || [];
    if (liste.indexOf(texte) >= 0) { return { valeur: texte, ok: true }; }   // cas courant, rapide
    const cle = sansAccentsMinuscules(texte.replace(MOTIF_ESPACES, ' '));
    const canonique = correspondanceChoix(liste).get(cle);
    return canonique !== undefined ? { valeur: canonique, ok: true } : { valeur: texte, ok: false };
  }

  const normaliser = {
    date: normaliserDate,
    dateHeure: normaliserDateHeure,
    decimal: normaliserDecimal,
    entier: normaliserEntier,
    booleen: normaliserBooleen,
    choix: normaliserChoix,
  };

  // Valeur en mémoire (ou nombre) → Number, ou null si vide ou illisible.
  // Accepte aussi la virgule décimale (« 7,5 » → 7.5).
  function nombre(valeur) {
    if (typeof valeur === 'number') { return Number.isFinite(valeur) ? valeur : null; }
    const resultat = normaliserDecimal(valeur);
    if (!resultat.ok || resultat.valeur === '') { return null; }
    const converti = Number(resultat.valeur);
    return Number.isFinite(converti) ? converti : null;
  }

  // ===========================================================================
  // 3. CSV
  // ===========================================================================

  // --- 3.1 Protection par apostrophe (ARCHITECTURE.md §3.2, appliqué tel quel) ---------------

  const MOTIF_DEBUT_DANGEREUX = /^[=+\-@\t\r]/;                         // formule ou tiret en tête
  const MOTIFS_NOMBRE_DATE_FRACTION = [
    /^[0-9]+([.,][0-9]+)?$/,                                            // nombre (zéros en tête, plus de 11 chiffres)
    /^[0-9]+([.,][0-9]+)?[eE][+-]?[0-9]+$/,                             // exposant
    /^[0-9]{1,4}[/.-][0-9]{1,2}([/.-][0-9]{1,4})?$/,                    // date ou fraction (1/2, 01-12, 2026-10)
    /^[0-9]{1,2}:[0-9]{2}(:[0-9]{2})?$/,                                // heure
    /^[0-9]+([.,][0-9]+)?\s?%$/,                                        // pourcentage
  ];

  function ressembleNombreDateFraction(valeur) {
    const sansEspacesAuxBords = valeur.trim();
    for (const motif of MOTIFS_NOMBRE_DATE_FRACTION) {
      if (motif.test(sansEspacesAuxBords)) { return true; }
    }
    return false;
  }

  function estChampTexte(champ) {
    return Boolean(champ) && (champ.type === 'texte' || champ.type === 'texte_long');
  }

  // Vrai si Excel risque d'abîmer cette valeur : on l'écrira précédée d'une apostrophe.
  // Seuls les champs de type texte et texte_long sont protégés.
  function aProteger(champ, valeur) {
    if (!estChampTexte(champ)) { return false; }
    const texte = enTexte(valeur);
    return texte !== '' && (
      champ.protege === true
      || MOTIF_DEBUT_DANGEREUX.test(texte)
      || texte.startsWith("'")
      || ressembleNombreDateFraction(texte));
  }

  // Valeur en mémoire → valeur écrite dans le fichier (apostrophe ajoutée si besoin).
  function ecrireValeur(champ, valeur) {
    const texte = enTexte(valeur);
    return aProteger(champ, texte) ? "'" + texte : texte;
  }

  // Valeur lue dans le fichier → valeur en mémoire (apostrophe de protection retirée).
  // Garantie (testée) : relireValeur(champ, ecrireValeur(champ, v)) === v pour tout v.
  function relireValeur(champ, valeurLue) {
    const texte = enTexte(valeurLue);
    return (texte.startsWith("'") && aProteger(champ, texte.slice(1))) ? texte.slice(1) : texte;
  }

  // --- 3.2 Décodage des octets --------------------------------------------------------------

  const decodeurUtf8Strict = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true });
  const decodeurWindows1252 = new TextDecoder('windows-1252');

  // Uint8Array, ArrayBuffer, autre vue typée ou tableau de nombres → Uint8Array.
  function enOctets(entree) {
    if (entree instanceof Uint8Array) { return entree; }
    if (entree instanceof ArrayBuffer) { return new Uint8Array(entree); }
    if (ArrayBuffer.isView(entree)) { return new Uint8Array(entree.buffer, entree.byteOffset, entree.byteLength); }
    if (Array.isArray(entree)) { return Uint8Array.from(entree); }
    throw new TypeError('Donnees.csv : octets attendus (Uint8Array ou ArrayBuffer).');
  }

  // Octets d'un fichier → { texte, encodage } (encodage : 'utf-8' ou 'windows-1252').
  // Le BOM est retiré. Si les octets ne sont pas de l'UTF-8 valide (fichier enregistré par Excel
  // au format « CSV » simple), on les lit en Windows-1252. Une chaîne est acceptée telle quelle.
  function decoder(entree) {
    if (typeof entree === 'string') {
      return { texte: entree.charCodeAt(0) === 0xFEFF ? entree.slice(1) : entree, encodage: 'utf-8' };
    }
    let octets = enOctets(entree);
    if (octets.length >= 3 && octets[0] === 0xEF && octets[1] === 0xBB && octets[2] === 0xBF) {
      octets = octets.subarray(3);
    }
    try {
      return { texte: decodeurUtf8Strict.decode(octets), encodage: 'utf-8' };
    } catch (erreurDecodage) {
      return { texte: decodeurWindows1252.decode(octets), encodage: 'windows-1252' };
    }
  }

  // --- 3.3 Écriture (ARCHITECTURE.md §3.1) --------------------------------------------------

  const MOTIF_A_GUILLEMETER = /[;"\r\n]|^[ \t]|[ \t]$/;
  const MOTIF_GUILLEMET = /"/g;
  const BOM_UTF8 = [0xEF, 0xBB, 0xBF];
  const encodeurUtf8 = new TextEncoder();

  // Une cellule CSV : entre guillemets si elle contient « ; », « " », CR, LF ou une espace au
  // début ou à la fin ; les guillemets intérieurs sont doublés (RFC 4180).
  function celluleCsv(texte) {
    return MOTIF_A_GUILLEMETER.test(texte) ? '"' + texte.replace(MOTIF_GUILLEMET, '""') + '"' : texte;
  }

  function descriptionTable(nomTable) {
    const description = Schema.table(nomTable);
    if (!description) { throw new Error('Donnees.csv : table inconnue « ' + nomTable + ' ».'); }
    return description;
  }

  // Lignes (objets) → octets du fichier : BOM UTF-8, « ; », CRLF, en-têtes dans l'ordre du schéma
  // puis les colonnes inconnues conservées (dans leur ordre d'origine).
  // options.bom = false : sans BOM (écriture par ajout au journal, ARCHITECTURE.md §5.4).
  function serialiser(nomTable, lignes, colonnesInconnues, options) {
    const champs = descriptionTable(nomTable).champs;
    const inconnues = colonnesInconnues || [];
    const avecBom = !(options && options.bom === false);
    const morceaux = [];

    const entetes = [];
    for (const champ of champs) { entetes.push(celluleCsv(champ.nom)); }
    for (const nomColonne of inconnues) { entetes.push(celluleCsv(nomColonne)); }
    morceaux.push(entetes.join(';'));

    for (const ligne of lignes || []) {
      const cellules = [];
      for (const champ of champs) { cellules.push(celluleCsv(ecrireValeur(champ, ligne[champ.nom]))); }
      for (const nomColonne of inconnues) { cellules.push(celluleCsv(enTexte(ligne[nomColonne]))); }
      morceaux.push(cellules.join(';'));
    }

    const corps = encodeurUtf8.encode(morceaux.join('\r\n') + '\r\n');
    if (!avecBom) { return corps; }
    const octets = new Uint8Array(BOM_UTF8.length + corps.length);
    octets.set(BOM_UTF8, 0);
    octets.set(corps, BOM_UTF8.length);
    return octets;
  }

  // --- 3.4 Lecture tolérante (ARCHITECTURE.md §3.3) -----------------------------------------

  const MOTIF_FIN_PARASITE = /[ \t\r]+$/;                                // espaces de fin et \r parasites
  const MOTIF_PREMIERE_LIGNE_NON_VIDE = /^[^\r\n]*\S[^\r\n]*/m;
  const MOTIF_NOTATION_SCIENTIFIQUE_EXCEL = /^[0-9]+,[0-9]+E\+[0-9]+$/i;
  const MOTIF_ERREUR_FORMULE_EXCEL = /^#(NOM|NAME)\?$/;
  const MOTIF_SEPARATEURS_ENTETE = /[\s_]+/g;

  // Nom de colonne → clé de comparaison (casse, accents, espaces et « _ » ignorés).
  function cleEntete(nomColonne) {
    return sansAccentsMinuscules(nomColonne).replace(MOTIF_SEPARATEURS_ENTETE, '');
  }

  // Séparateur : « ; » ; si l'en-tête n'a aucun « ; » mais des « , », on lit avec « , ».
  function choisirSeparateur(texte) {
    const trouvee = MOTIF_PREMIERE_LIGNE_NON_VIDE.exec(texte);
    const entete = trouvee ? trouvee[0] : '';
    return (entete.indexOf(';') < 0 && entete.indexOf(',') >= 0) ? ',' : ';';
  }

  function compterOccurrences(texte, caractere, debut, fin) {
    let compte = 0;
    let position = texte.indexOf(caractere, debut);
    while (position >= 0 && position < fin) {
      compte += 1;
      position = texte.indexOf(caractere, position + 1);
    }
    return compte;
  }

  // Découpe le texte avec Papa.parse et numérote chaque enregistrement par la ligne du fichier où
  // il commence (en-tête = 1), malgré les lignes vides sautées et les valeurs sur plusieurs lignes.
  // Renvoie { enregistrements: [{ cellules, numero }], erreurs: [{ numero, message }] }.
  function decouper(texte, separateur) {
    const finDeLigne = texte.indexOf('\n') >= 0 ? '\n' : '\r';
    const enregistrements = [];
    const erreurs = [];
    let positionComptee = 0;     // jusqu'où les sauts de ligne ont été comptés
    let sautsDeLigne = 0;        // sauts de ligne avant positionComptee

    Papa.parse(texte, {
      delimiter: separateur,
      quoteChar: '"',
      skipEmptyLines: 'greedy',
      step: (resultat) => {
        const curseur = resultat.meta.cursor;          // position juste après l'enregistrement
        sautsDeLigne += compterOccurrences(texte, finDeLigne, positionComptee, curseur);
        positionComptee = curseur;
        const termineParUnSaut = texte[curseur - 1] === finDeLigne ? 1 : 0;
        const cellules = resultat.data;
        let sautsInterieurs = 0;
        for (const cellule of cellules) {
          if (cellule.indexOf(finDeLigne) >= 0) {
            sautsInterieurs += compterOccurrences(cellule, finDeLigne, 0, cellule.length);
          }
        }
        const numero = 1 + sautsDeLigne - termineParUnSaut - sautsInterieurs;
        enregistrements.push({ cellules: cellules, numero: numero });
        for (const erreur of resultat.errors) {
          erreurs.push({ numero: numero, message: erreur.message, code: erreur.code });
        }
      },
    });
    return { enregistrements: enregistrements, erreurs: erreurs };
  }

  // Messages d'aide pour une valeur illisible, selon le type du champ.
  function explicationValeurIllisible(champ) {
    switch (champ.type) {
      case 'date': return "n'est pas une date valide (formats acceptés : 2024-03-15 ou 15/03/2024)";
      case 'date_heure': return "n'est pas une date et heure valide (formats acceptés : 2024-03-15 08:30 ou 15/03/2024 08:30)";
      case 'decimal': return "n'est pas un nombre (exemples acceptés : 7,5 ou 7.5)";
      case 'entier': return "n'est pas un nombre entier";
      case 'booleen': return "n'est pas reconnu comme oui ou non (valeurs acceptées : 1, 0, oui, non, vrai, faux, x)";
      case 'choix': return "ne fait pas partie des valeurs possibles (" + (champ.valeurs || []).join(', ') + ')';
      default: return 'est illisible';
    }
  }

  // Normalise une cellule selon le type de son champ. Renvoie { valeur, probleme } où probleme
  // est null ou { gravite, type, explication }.
  function lireCellule(champ, brut) {
    const nettoye = brut.replace(MOTIF_FIN_PARASITE, '');
    let resultat;
    switch (champ.type) {
      case 'texte':
      case 'texte_long': {
        const valeur = relireValeur(champ, nettoye);
        if (MOTIF_NOTATION_SCIENTIFIQUE_EXCEL.test(valeur)) {
          return { valeur: valeur, probleme: { gravite: 'attention', type: 'excel',
            explication: "valeur probablement abîmée par Excel (nombre long transformé en notation scientifique). "
              + "Retrouvez la valeur d'origine et saisissez-la précédée d'une apostrophe, par exemple '123456789012345" } };
        }
        if (MOTIF_ERREUR_FORMULE_EXCEL.test(valeur)) {
          return { valeur: valeur, probleme: { gravite: 'attention', type: 'excel',
            explication: "valeur probablement abîmée par Excel (texte commençant par « = », « + » ou « - » pris pour une formule). "
              + "Retrouvez le texte d'origine et saisissez-le précédé d'une apostrophe" } };
        }
        return { valeur: valeur, probleme: null };
      }
      case 'date': resultat = normaliserDate(nettoye); break;
      case 'date_heure': resultat = normaliserDateHeure(nettoye); break;
      case 'decimal': resultat = normaliserDecimal(nettoye); break;
      case 'entier': resultat = normaliserEntier(nettoye); break;
      case 'booleen': resultat = normaliserBooleen(nettoye); break;
      case 'choix': resultat = normaliserChoix(nettoye, champ.valeurs); break;
      default:   // id, ref, document : simple nettoyage des espaces
        return { valeur: nettoye.trim(), probleme: null };
    }
    if (resultat.ok) { return { valeur: resultat.valeur, probleme: null }; }
    return { valeur: resultat.valeur, probleme: { gravite: 'erreur', type: 'valeur',
      explication: explicationValeurIllisible(champ) + '. Valeur conservée telle quelle : à corriger' } };
  }

  // Fabrique d'un problème (forme commune à tout Donnees, ARCHITECTURE.md §5.2).
  function probleme(gravite, type, table, ligne, id, champ, valeur, message) {
    return {
      gravite: gravite, type: type, table: table,
      ligne: ligne === undefined ? null : ligne,
      id: id === undefined || id === '' ? null : id,
      champ: champ === undefined ? null : champ,
      valeur: valeur === undefined ? null : valeur,
      message: message,
    };
  }

  // Associe chaque colonne du fichier à un champ du schéma ou à une colonne inconnue conservée.
  // Renvoie { colonnes: [{ champ } | { inconnue: nom } | { ignoree: true }], inconnues, absents }.
  function associerColonnes(description, nomTable, entete, enregistrements, problemes) {
    const champParCle = new Map();
    for (const champ of description.champs) { champParCle.set(cleEntete(champ.nom), champ); }
    const champsVus = new Set();
    const nomsInconnus = new Set();
    const colonnes = [];
    const inconnues = [];

    function nomInconnuLibre(nomVoulu) {
      let nom = nomVoulu;
      let numero = 2;
      while (nomsInconnus.has(nom) || champParCle.has(cleEntete(nom))) {
        nom = nomVoulu + ' (' + numero + ')';
        numero += 1;
      }
      nomsInconnus.add(nom);
      return nom;
    }

    entete.forEach((celluleEntete, index) => {
      const nomColonne = celluleEntete.trim();
      const champ = champParCle.get(cleEntete(nomColonne));
      if (champ && !champsVus.has(champ.nom)) {
        champsVus.add(champ.nom);
        colonnes.push({ champ: champ });
        return;
      }
      if (nomColonne === '') {
        // Colonne sans nom : ignorée si elle est vide partout, sinon conservée sous « colonne N ».
        const contientDesValeurs = enregistrements.some((e) => (e.cellules[index] || '').trim() !== '');
        if (!contientDesValeurs) { colonnes.push({ ignoree: true }); return; }
      }
      const nomConserve = nomInconnuLibre(nomColonne === '' ? 'colonne ' + (index + 1) : nomColonne);
      colonnes.push({ inconnue: nomConserve });
      inconnues.push(nomConserve);
      const message = champ
        ? description.libelle + ' : la colonne « ' + nomColonne + ' » apparaît deux fois dans ' + description.fichier
          + ' ; la seconde est conservée à part sous le nom « ' + nomConserve + ' » et n\'est pas utilisée par Prévo.'
        : description.libelle + ' : la colonne « ' + nomConserve + ' » de ' + description.fichier
          + ' ne fait pas partie de Prévo ; elle est conservée telle quelle (réécrite en fin de fichier).';
      problemes.push(probleme(champ ? 'attention' : 'info', 'colonne', nomTable, 1, null, nomConserve, null, message));
    });

    const absents = description.champs.filter((champ) => !champsVus.has(champ.nom));
    for (const champ of absents) {
      const valeurParDefaut = champ.defaut === undefined ? '' : champ.defaut;
      const suite = valeurParDefaut === ''
        ? 'la valeur est laissée vide'
        : 'la valeur par défaut « ' + valeurParDefaut + ' » est utilisée';
      problemes.push(probleme('attention', 'colonne', nomTable, 1, null, champ.nom, null,
        description.libelle + ' : la colonne « ' + champ.nom + ' » (' + champ.libelle + ') est absente de '
        + description.fichier + ' ; ' + suite + '. Elle sera ajoutée à la prochaine modification de la table.'));
    }
    return { colonnes: colonnes, inconnues: inconnues, absents: absents };
  }

  // Octets (ou texte) d'un fichier CSV → { lignes, colonnesInconnues, problemes, encodage, separateur }.
  // Chaque ligne est un objet avec TOUS les champs du schéma (valeur par défaut du schéma si la
  // colonne est absente du fichier, sinon chaîne vide), plus les colonnes inconnues.
  function analyser(nomTable, entree) {
    const description = descriptionTable(nomTable);
    const decode = decoder(entree);
    const texte = decode.texte;
    const separateur = choisirSeparateur(texte);
    const problemes = [];
    const resultat = { lignes: [], colonnesInconnues: [], problemes: problemes,
      encodage: decode.encodage, separateur: separateur };

    if (decode.encodage === 'windows-1252') {
      problemes.push(probleme('info', 'encodage', nomTable, null, null, null, null,
        description.libelle + ' : ' + description.fichier + " n'est pas en UTF-8 (sans doute enregistré par Excel au format "
        + '« CSV (séparateur : point-virgule) ») ; il a été lu en Windows-1252. '
        + 'Il sera réécrit en UTF-8 à la prochaine modification de la table.'));
    }
    if (texte.trim() === '') { return resultat; }      // fichier vide : table vide, rien à signaler

    const decoupage = decouper(texte, separateur);
    const enregistrements = decoupage.enregistrements;
    const entete = enregistrements.length > 0 ? enregistrements[0].cellules : [];
    const donnees = enregistrements.slice(1);
    const association = associerColonnes(description, nomTable, entete, donnees, problemes);
    const colonnes = association.colonnes;
    resultat.colonnesInconnues = association.inconnues;

    // Ligne modèle : champs absents du fichier = valeur par défaut, présents = '' (remplis ensuite).
    const modele = {};
    for (const champ of description.champs) { modele[champ.nom] = ''; }
    for (const champ of association.absents) { modele[champ.nom] = champ.defaut === undefined ? '' : champ.defaut; }
    const indexCle = colonnes.findIndex((colonne) => colonne.champ && colonne.champ.nom === description.cle);

    for (const erreur of decoupage.erreurs) {
      problemes.push(probleme('erreur', 'valeur', nomTable, erreur.numero, null, null, null,
        description.libelle + ', ligne ' + erreur.numero + ' de ' + description.fichier
        + ' : structure du fichier abîmée (' + erreur.message + '), par exemple un guillemet non fermé. '
        + 'Les valeurs de cette ligne et des suivantes peuvent être décalées.'));
    }

    for (const enregistrement of donnees) {
      const cellules = enregistrement.cellules;
      const numero = enregistrement.numero;
      const ligne = Object.assign({}, modele);
      const identifiant = indexCle >= 0 ? (cellules[indexCle] || '').trim() : '';
      const reperage = description.libelle + ', ligne ' + numero + (identifiant ? ' (' + identifiant + ')' : '');

      for (let index = 0; index < colonnes.length; index += 1) {
        const colonne = colonnes[index];
        const brut = index < cellules.length ? cellules[index] : '';
        if (colonne.champ) {
          const lu = lireCellule(colonne.champ, brut);
          ligne[colonne.champ.nom] = lu.valeur;
          if (lu.probleme) {
            problemes.push(probleme(lu.probleme.gravite, lu.probleme.type, nomTable, numero, identifiant,
              colonne.champ.nom, lu.valeur,
              reperage + ' : « ' + colonne.champ.libelle + ' » contient « ' + lu.valeur + ' », '
              + lu.probleme.explication + '.'));
          }
        } else if (colonne.inconnue !== undefined) {
          ligne[colonne.inconnue] = brut.replace(MOTIF_FIN_PARASITE, '');
        }
      }

      // Cellules au-delà de l'en-tête : signalées si elles ne sont pas vides, puis ignorées.
      for (let index = colonnes.length; index < cellules.length; index += 1) {
        if (cellules[index].trim() !== '') {
          problemes.push(probleme('attention', 'colonne', nomTable, numero, identifiant, null, cellules[index],
            reperage + ' : cette ligne contient plus de valeurs que l\'en-tête n\'a de colonnes ; '
            + 'la valeur « ' + cellules[index] + ' » (colonne ' + (index + 1) + ') est ignorée.'));
        }
      }
      resultat.lignes.push(ligne);
    }
    return resultat;
  }

  const csv = {
    decoder: decoder,
    aProteger: aProteger,
    ecrireValeur: ecrireValeur,
    relireValeur: relireValeur,
    analyser: analyser,
    serialiser: serialiser,
  };

  // ===========================================================================
  // 4. Chargement, mutation, journal, rafraîchissement
  // ===========================================================================
  // Section complétée par la tâche T08 (ARCHITECTURE.md §5.2 à §5.5) : initialiser, chargerTout,
  // lignes, trouver, version, parametre, problemes, stockArticle, modifier, ajouter,
  // demarrerSurveillance, evenements, statistiques.

  return {
    // 1. Erreurs
    ErreurConflit: ErreurConflit,
    ErreurValidation: ErreurValidation,
    ErreurStockage: ErreurStockage,
    // 2. Dates, nombres, normalisation
    nombre: nombre,
    aujourdhui: aujourdhui,
    maintenant: maintenant,
    normaliser: normaliser,
    // 3. CSV
    csv: csv,
  };
})();
