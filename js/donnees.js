'use strict';
// Donnees : accès aux données de Prévo (les 23 fichiers CSV décrits par js/schema.js).
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

  // Document à afficher (lot 3, correction de relecture). Un document « .html » (rapport mensuel figé)
  // n'est jamais ouvert tel quel hors du serveur (qui le sert avec « Content-Security-Policy:
  // sandbox ») : il est placé dans une page enveloppe, à l'intérieur d'un cadre isolé SANS scripts
  // (iframe sandbox), pour qu'aucun script qu'il contiendrait ne s'exécute. Les autres types sont
  // rendus tels quels.
  async function documentAffichable(nom, blob) {
    if (!blob || !/\.html$/i.test(enTexte(nom))) return blob;
    const echapper = (texte) => texte.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const page = '<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>' + echapper(nom) + '</title>'
      + '<style>html,body{margin:0;height:100%;background:#fff}iframe{border:0;display:block;width:100%;height:100%}</style>'
      + '</head><body><iframe sandbox="allow-modals" title="' + echapper(nom) + '" srcdoc="' + echapper(await blob.text()) + '"></iframe></body></html>';
    return new Blob([page], { type: 'text/html;charset=utf-8' });
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
    // Retrait explicite de [ \t\r\n] aux deux bords (et non trim()) : règle identique à celle de
    // ressemble_nombre_date_fraction dans outils/generer_demo.py.
    const sansEspacesAuxBords = valeur.replace(/^[ \t\r\n]+|[ \t\r\n]+$/g, '');
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
  // puis les colonnes inconnues conservées (dans leur ordre d'origine). Toutes les colonnes du
  // schéma sont toujours écrites : un fichier de la version 1 du format reçoit ainsi les colonnes
  // de la version 2 (en fin de champs du schéma) à son prochain enregistrement (§14.1).
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
        // On lit d'abord la cellule brute (sinon « '<tab> » perdrait son contenu), puis on retire la fin parasite.
        const valeur = relireValeur(champ, brut).replace(MOTIF_FIN_PARASITE, '');
        // Une valeur protégée par apostrophe (« '1,5E+3 ») est voulue : seule une cellule brute sans apostrophe est suspecte.
        if (!brut.startsWith("'") && MOTIF_NOTATION_SCIENTIFIQUE_EXCEL.test(valeur)) {
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
      problemes.push(problemeColonneAbsente(description, nomTable, champ));
    }
    return { colonnes: colonnes, inconnues: inconnues, absents: absents };
  }

  // Problème signalé pour une colonne du schéma absente du fichier (sa valeur par défaut est
  // appliquée aux lignes lues, voir analyser) :
  //   - champ ajouté par une version du format (depuisVersion) : simple information, le fichier a
  //     été écrit avant cette version et recevra la colonne au prochain enregistrement (§14.1) ;
  //   - champ du brief : « attention », la colonne a sans doute été supprimée à la main (§3.3).
  function problemeColonneAbsente(description, nomTable, champ) {
    if (champ.depuisVersion !== undefined) {
      return probleme('info', 'colonne', nomTable, 1, null, champ.nom, null,
        description.libelle + ' : colonne « ' + champ.nom + ' » ajoutée par la version ' + champ.depuisVersion
        + ' du format, écrite au prochain enregistrement.');
    }
    const valeurParDefaut = champ.defaut === undefined ? '' : champ.defaut;
    const suite = valeurParDefaut === ''
      ? 'la valeur est laissée vide'
      : 'la valeur par défaut « ' + valeurParDefaut + ' » est utilisée';
    return probleme('attention', 'colonne', nomTable, 1, null, champ.nom, null,
      description.libelle + ' : la colonne « ' + champ.nom + ' » (' + champ.libelle + ') est absente de '
      + description.fichier + ' ; ' + suite + '. Elle sera ajoutée à la prochaine modification de la table.');
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
  // 4. Chargement, mutation, journal, rafraîchissement (ARCHITECTURE.md §5.2 à §5.5)
  // ===========================================================================
  // Le cache garde, pour chaque table, une « entrée » :
  //   { lignes, colonnesInconnues, version, index, problemesLecture, perime, absente }
  //   - lignes            : tableau d'objets (toutes les valeurs sont des chaînes) ;
  //   - colonnesInconnues : colonnes du fichier qui ne sont pas dans le schéma (conservées) ;
  //   - version           : version donnée par l'adaptateur (null si le fichier n'existe pas) ;
  //   - index             : Map clé → ligne (première ligne si la clé est en double) ;
  //   - problemesLecture  : problèmes trouvés par csv.analyser ;
  //   - perime            : vrai si le fichier a changé sans que le cache soit à jour (ajout au
  //                         journal) : la table sera relue avant toute réécriture (modifier) et
  //                         au rafraîchissement (voir versionApresAjout) ;
  //   - absente           : vrai si le fichier n'existe pas ;
  //   - versionApresAjout : (facultatif) version rendue par notre dernier ajout direct ; nos
  //                         lignes ajoutées sont déjà dans `lignes`. Tant que le stockage a cette
  //                         version, la surveillance ne relit pas la table (elle reste périmée).

  const NOMBRE_ESSAIS = 3;
  const RAFRAICHISSEMENT_PAR_DEFAUT_S = 20;
  const CARACTERES_ALEATOIRES = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  const MOTIF_CHIFFRES = /^[0-9]+$/;
  const MOTIF_ANNEE = /^([0-9]{4})/;

  let adaptateurActif = null;
  let identite = { poste: '', profil: '' };
  const cache = new Map();                    // nom de table → entrée (voir ci-dessus)
  const filesAttente = new Map();             // nom de table → promesse de la dernière tâche
  const evenements = new EventTarget();
  const statistiques = { conflits: 0, essais: 0 };

  // Résultats calculés à la demande, oubliés à chaque changement de données (« à recalculer »).
  let problemesCalcules = null;
  let mouvementsParArticle = null;

  let minuteurSurveillance = null;
  let surRetourOnglet = null;
  let rafraichissementEnCours = null;

  // --- 4.1 Outils internes ------------------------------------------------------------------

  function verifierInitialise() {
    if (!adaptateurActif) {
      throw new Error('Donnees : appelez Donnees.initialiser(adaptateur, …) avant de lire ou d\'écrire.');
    }
  }

  // Oublie les résultats calculés : ils seront recalculés au prochain appel.
  function aRecalculer() {
    problemesCalcules = null;
    mouvementsParArticle = null;
  }

  // Exécute les tâches d'une même table l'une après l'autre (jamais deux écritures en même
  // temps sur un fichier depuis ce poste). Une tâche en échec ne bloque pas les suivantes.
  function enSerie(nomTable, tache) {
    const precedente = filesAttente.get(nomTable) || Promise.resolve();
    const resultat = precedente.then(tache, tache);
    filesAttente.set(nomTable, resultat.catch(() => undefined));
    return resultat;
  }

  // Map clé → ligne. En cas de doublon, la première ligne est gardée ; une clé vide est ignorée.
  function indexer(description, lignes) {
    const index = new Map();
    for (const ligne of lignes) {
      const cle = ligne[description.cle];
      if (cle !== '' && cle !== undefined && !index.has(cle)) { index.set(cle, ligne); }
    }
    return index;
  }

  function entreeAbsente() {
    return { lignes: [], colonnesInconnues: [], version: null, index: new Map(),
      problemesLecture: [], perime: false, absente: true };
  }

  // Résultat de adaptateur.charger → entrée de cache.
  function entreeDepuisFichier(nomTable, octets, version) {
    if (octets === null || octets === undefined) { return entreeAbsente(); }
    const lu = analyser(nomTable, octets);
    return {
      lignes: lu.lignes,
      colonnesInconnues: lu.colonnesInconnues,
      version: version === undefined ? null : version,
      index: indexer(descriptionTable(nomTable), lu.lignes),
      problemesLecture: lu.problemes,
      perime: false,
      absente: false,
    };
  }

  // Entrée du cache ; une table pas encore chargée est vue comme vide (et périmée).
  function entreeDe(nomTable) {
    descriptionTable(nomTable);                       // lève une erreur si la table n'existe pas
    const entree = cache.get(nomTable);
    if (entree) { return entree; }
    const vide = entreeAbsente();
    vide.perime = true;
    return vide;
  }

  // Relit une table depuis l'adaptateur (sans passer par la file d'attente).
  async function rechargerSansAttente(nomTable) {
    verifierInitialise();
    const resultat = await adaptateurActif.charger(nomTable);
    const entree = entreeDepuisFichier(nomTable, resultat.octets, resultat.version);
    cache.set(nomTable, entree);
    aRecalculer();
    return entree;
  }

  function signaler(nomsTables, origine) {
    evenements.dispatchEvent(new CustomEvent('changement', {
      detail: { tables: nomsTables, origine: origine },
    }));
  }

  // --- 4.2 Lecture --------------------------------------------------------------------------

  // adaptateur : objet du contrat ARCHITECTURE.md §6 ; options : { poste, profil } (pour le journal).
  // Vide le cache : appeler ensuite chargerTout().
  function initialiser(adaptateur, options) {
    arreterSurveillance();
    adaptateurActif = adaptateur;
    definirIdentite(options);
    cache.clear();
    filesAttente.clear();
    statistiques.conflits = 0;
    statistiques.essais = 0;
    rafraichissementEnCours = null;
    aRecalculer();
  }

  // Change le poste et le profil inscrits au journal (ex. après le choix du profil).
  function definirIdentite(options) {
    const valeurs = options || {};
    identite = { poste: enTexte(valeurs.poste), profil: enTexte(valeurs.profil) };
  }

  // Charge les 23 tables en parallèle. Renvoie { tablesAbsentes: [noms des fichiers absents] }.
  async function chargerTout() {
    verifierInitialise();
    const noms = Schema.nomsTables();
    const resultats = await Promise.all(noms.map((nomTable) => adaptateurActif.charger(nomTable)));
    const tablesAbsentes = [];
    noms.forEach((nomTable, position) => {
      const resultat = resultats[position];
      const entree = entreeDepuisFichier(nomTable, resultat.octets, resultat.version);
      if (entree.absente) { tablesAbsentes.push(nomTable); }
      cache.set(nomTable, entree);
    });
    aRecalculer();
    return { tablesAbsentes: tablesAbsentes };
  }

  // Vrai si aucun des 23 fichiers n'existe (proposer « base vide » ou « données de démo »).
  function baseVide() {
    const noms = Schema.nomsTables();
    return noms.every((nomTable) => cache.has(nomTable) && cache.get(nomTable).absente);
  }

  // Lignes d'une table. NE PAS MODIFIER ces objets : passer par Donnees.modifier.
  function lignes(nomTable) {
    return entreeDe(nomTable).lignes;
  }

  // Ligne dont la clé vaut `cle` (index Map), ou undefined.
  function trouver(nomTable, cle) {
    return entreeDe(nomTable).index.get(cle);
  }

  function version(nomTable) {
    return entreeDe(nomTable).version;
  }

  // Valeur d'un paramètre de parametres.csv ; `defaut` si la clé est absente ou la valeur vide.
  function parametre(cle, defaut) {
    const ligne = trouver('parametres', cle);
    if (!ligne || ligne.valeur === '') { return defaut; }
    return ligne.valeur;
  }

  // Relit une table depuis le stockage (sans émettre d'événement). Renvoie ses lignes.
  async function rechargerTable(nomTable) {
    descriptionTable(nomTable);
    const entree = await enSerie(nomTable, () => rechargerSansAttente(nomTable));
    return entree.lignes;
  }

  // --- 4.3 Contrôle de la base : problemes() ------------------------------------------------

  // Repère d'une ligne pour les messages : son identifiant, sinon sa position.
  function reperageLigne(description, ligne, position) {
    const cle = ligne[description.cle];
    return cle ? cle : 'ligne de données n° ' + (position + 1) + ' (sans identifiant)';
  }

  function decrireFiltre(filtre) {
    return Object.keys(filtre).map((nomChamp) => nomChamp + ' « ' + filtre[nomChamp] + ' »').join(', ');
  }

  // Valeurs existantes d'une cible de référence, calculées une seule fois par contrôle.
  // Renvoie { valides: Set, toutes: Map valeur → ligne } (toutes = sans filtre, pour expliquer).
  function ciblesReference(memoire, champ) {
    const descriptionCible = descriptionTable(champ.table);
    const champCible = champ.champCible || descriptionCible.cle;
    const filtre = champ.filtre || null;
    const cleMemoire = champ.table + '|' + champCible + '|' + (filtre ? JSON.stringify(filtre) : '');
    let cibles = memoire.get(cleMemoire);
    if (cibles) { return cibles; }
    cibles = { valides: new Set(), toutes: new Map(), champCible: champCible, filtre: filtre };
    const nomsFiltre = filtre ? Object.keys(filtre) : [];
    for (const ligne of entreeDe(champ.table).lignes) {
      const valeur = ligne[champCible];
      if (valeur === '' || valeur === undefined) { continue; }
      if (!cibles.toutes.has(valeur)) { cibles.toutes.set(valeur, ligne); }
      if (nomsFiltre.every((nomChamp) => ligne[nomChamp] === filtre[nomChamp])) { cibles.valides.add(valeur); }
    }
    memoire.set(cleMemoire, cibles);
    return cibles;
  }

  // Identifiants manquants et en double d'une table.
  function controlerIdentifiants(nomTable, description, lignesTable, resultat) {
    const vus = new Set();
    lignesTable.forEach((ligne, position) => {
      const cle = ligne[description.cle];
      if (cle === '' || cle === undefined) {
        resultat.push(probleme('erreur', 'identifiant', nomTable, null, null, description.cle, null,
          description.libelle + ' : la ' + reperageLigne(description, ligne, position) + ' de '
          + description.fichier + ' n\'a pas d\'identifiant (colonne « ' + description.cle + ' » vide). '
          + 'Complétez-le ou supprimez la ligne dans le fichier.'));
        return;
      }
      if (vus.has(cle)) {
        resultat.push(probleme('erreur', 'doublon', nomTable, null, cle, description.cle, cle,
          description.libelle + ' : l\'identifiant « ' + cle + ' » apparaît plusieurs fois dans '
          + description.fichier + ' (ligne de données n° ' + (position + 1) + '). Seule la première ligne est '
          + 'retrouvée par Prévo : donnez un identifiant unique aux autres.'));
      }
      vus.add(cle);
    });
  }

  // Clés étrangères cassées d'une table (et codes de défaillance de la mauvaise famille).
  function controlerReferences(nomTable, description, lignesTable, memoire, resultat) {
    const champsReference = description.champs.filter((champ) => champ.type === 'ref');
    for (const champ of champsReference) {
      const cibles = ciblesReference(memoire, champ);
      const descriptionCible = descriptionTable(champ.table);
      lignesTable.forEach((ligne, position) => {
        const valeur = ligne[champ.nom];
        if (valeur === '' || valeur === undefined || cibles.valides.has(valeur)) { return; }
        const reperage = description.libelle + ', ' + reperageLigne(description, ligne, position);
        const ligneSansFiltre = cibles.toutes.get(valeur);
        let explication;
        if (ligneSansFiltre && cibles.filtre) {
          const familleTrouvee = Object.keys(cibles.filtre)
            .map((nomChamp) => nomChamp + ' « ' + ligneSansFiltre[nomChamp] + ' »').join(', ');
          explication = 'existe dans ' + descriptionCible.libelle + ' mais avec ' + familleTrouvee
            + ' au lieu de ' + decrireFiltre(cibles.filtre);
        } else {
          explication = 'n\'existe pas dans ' + descriptionCible.libelle
            + (cibles.filtre ? ' (' + decrireFiltre(cibles.filtre) + ')' : '');
        }
        resultat.push(probleme('erreur', 'reference', nomTable, null, ligne[description.cle], champ.nom, valeur,
          reperage + ' : « ' + champ.libelle + ' » vaut « ' + valeur + ' », qui ' + explication + '.'));
      });
    }
  }

  // Incohérences entre demandes et ordres de travail (décision D18).
  function controlerCoherence(resultat) {
    const indexOrdres = entreeDe('ordres_travail').index;
    const indexDemandes = entreeDe('demandes').index;
    for (const demande of entreeDe('demandes').lignes) {
      if (demande.statut !== 'Acceptée') { continue; }
      if (demande.ot_id === '') {
        resultat.push(probleme('erreur', 'incoherence', 'demandes', null, demande.id, 'ot_id', '',
          'Demande ' + (demande.id || '(sans identifiant)') + ' : elle est « Acceptée » mais aucun ordre de travail '
          + 'ne lui est lié. Rouvrez-la ou liez-la à son ordre de travail.'));
      } else if (!indexOrdres.has(demande.ot_id)) {
        resultat.push(probleme('erreur', 'incoherence', 'demandes', null, demande.id, 'ot_id', demande.ot_id,
          'Demande ' + (demande.id || '(sans identifiant)') + ' : elle est « Acceptée » mais son ordre de travail « '
          + demande.ot_id + ' » n\'existe pas.'));
      }
    }
    for (const ordre of entreeDe('ordres_travail').lignes) {
      if (ordre.di_id === '') { continue; }
      const demande = indexDemandes.get(ordre.di_id);
      if (demande && demande.statut !== 'Acceptée' && demande.statut !== 'Regroupée') {
        // Cas d'une acceptation interrompue (l'OT est créé avant la DI, §5.3) : accepter de nouveau
        // la demande réutilise cet OT. Pas bloquant, d'où « attention ».
        resultat.push(probleme('attention', 'incoherence', 'ordres_travail', null, ordre.id, 'di_id', ordre.di_id,
          'Ordre de travail ' + (ordre.id || '(sans identifiant)') + ' : il vient de la demande « ' + ordre.di_id
          + ' », qui est « ' + demande.statut + ' » (ni acceptée ni regroupée). Acceptez ou regroupez la demande, '
          + 'ou annulez l\'ordre de travail.'));
      }
    }
  }

  // --- Lot 6 (ARCHITECTURE.md §20.2) : problèmes du wiki --------------------------------------
  // Liens et OT cités lus dans les champs `liens` et `ot_cites` des pages actives (tirés du texte à l'écriture) ;
  // une entrée « validée » doit avoir laissé chaque page de ses changements au moins à version_avant + 1.

  function listeDe(valeur) {
    return enTexte(valeur).split(';').map((morceau) => morceau.trim()).filter(Boolean);
  }

  function joursDepuis(dateTexte) {
    const lu = /^(\d{4})-(\d{2})-(\d{2})/.exec(enTexte(dateTexte));
    const jour = /^(\d{4})-(\d{2})-(\d{2})/.exec(aujourdhui());
    if (!lu || !jour) { return 0; }
    return Math.round((Date.UTC(+jour[1], jour[2] - 1, +jour[3]) - Date.UTC(+lu[1], lu[2] - 1, +lu[3])) / 86400000);
  }

  function controlerWiki(resultat) {
    const pages = entreeDe('wiki_pages');
    const journal = entreeDe('wiki_journal').lignes;
    if (!pages.lignes.length && !journal.length) { return; }
    const cibles = { 'EQ-': entreeDe('equipements').index, 'ART-': entreeDe('articles').index, 'WP-': pages.index };
    const ordres = entreeDe('ordres_travail').index;
    const parCle = new Map();
    const signaler = (gravite, page, champ, valeur, message) => resultat.push(probleme(gravite, 'wiki', 'wiki_pages', null,
      page.id, champ, valeur, 'Page du wiki ' + (page.id || '(sans identifiant)') + ' (« ' + page.titre + ' ») : ' + message));
    for (const page of pages.lignes.filter((ligne) => ligne.statut !== 'archivée')) {
      for (const lien of listeDe(page.liens)) {
        const prefixe = Object.keys(cibles).find((debut) => lien.startsWith(debut));
        const cible = prefixe ? cibles[prefixe].get(lien) : null;
        if (!cible || (prefixe === 'WP-' && cible.statut === 'archivée')) {
          signaler('attention', page, 'liens', lien, 'lien vers une page inexistante ou archivée (« ' + lien + ' »).');
        }
      }
      for (const ot of listeDe(page.ot_cites)) {
        if (!ordres.has(ot)) { signaler('attention', page, 'ot_cites', ot, 'elle cite l\'OT « ' + ot + ' », qui n\'existe pas.'); }
      }
      if (enTexte(page.texte).trim() && !listeDe(page.ot_cites).length) {
        signaler('info', page, 'ot_cites', '', 'elle ne cite aucun OT.');
      }
      const cle = enTexte(page.cle).trim();
      if (cle) { parCle.set(cle, (parCle.get(cle) || []).concat([page])); }
    }
    parCle.forEach((memes) => {
      if (memes.length > 1) {
        signaler('attention', memes[1], 'cle', memes[1].cle, 'même titre que la page ' + memes[0].id + ' (deux pages actives de même clé).');
      }
    });
    const ancienne = typeof Wiki !== 'undefined' && Wiki.SEUILS ? Wiki.SEUILS.contradictionAncienneJours : 30;
    for (const entree of journal.filter((ligne) => ligne.statut === 'validée')) {
      let changements = [];
      let contradictions = [];
      try { changements = JSON.parse(entree.changements || '[]') || []; } catch (erreur) { changements = null; }
      try { contradictions = JSON.parse(entree.contradictions || '[]') || []; } catch (erreur) { contradictions = []; }
      const absents = changements === null ? ['(changements illisibles)'] : changements.filter((c) => {
        const page = c && c.page ? pages.index.get(c.page) : null;
        return !page || (Number(page.version) || 0) < (Number(c.version_avant) || 0) + 1;
      }).map((c) => (c && (c.page || c.titre)) || '?');
      if (absents.length) {
        resultat.push(probleme('attention', 'wiki', 'wiki_journal', null, entree.id, 'changements', absents.join(', '),
          'Entrée ' + entree.id + ' du journal du wiki : elle est « validée » mais ses changements ne sont pas dans les pages ('
          + absents.join(', ') + ').'));
      }
      contradictions.filter((c) => c && c.statut === 'ouverte'
        && joursDepuis(entree.decide_le || entree.traite_le) > ancienne).forEach((c) => {
        resultat.push(probleme('info', 'wiki', 'wiki_journal', null, entree.id, 'contradictions', enTexte(c.page),
          'Entrée ' + entree.id + ' du journal du wiki : contradiction ouverte depuis plus de ' + ancienne + ' jours sur la page « '
          + enTexte(c.page) + ' ».'));
      });
    }
  }

  function calculerProblemes() {
    const resultat = [];
    const memoireCibles = new Map();
    for (const nomTable of Schema.nomsTables()) {
      for (const lu of entreeDe(nomTable).problemesLecture) { resultat.push(lu); }
    }
    for (const nomTable of Schema.nomsTables()) {
      const description = descriptionTable(nomTable);
      const lignesTable = entreeDe(nomTable).lignes;
      controlerIdentifiants(nomTable, description, lignesTable, resultat);
      controlerReferences(nomTable, description, lignesTable, memoireCibles, resultat);
    }
    controlerCoherence(resultat);
    controlerWiki(resultat);
    return resultat;
  }

  // Tous les problèmes de la base (lecture + contrôles). Recalculé seulement après un changement.
  // [{ gravite: 'erreur'|'attention'|'info', type, table, ligne, id, champ, valeur, message }]
  function problemes() {
    if (problemesCalcules === null) { problemesCalcules = calculerProblemes(); }
    return problemesCalcules;
  }

  // --- 4.4 Stock d'un article ---------------------------------------------------------------

  function comparerMouvements(a, b) {
    if (a.date !== b.date) { return a.date < b.date ? -1 : 1; }
    if (a.id !== b.id) { return a.id < b.id ? -1 : 1; }
    return 0;
  }

  // Map article_id → mouvements triés par date puis identifiant (calculée une fois par changement).
  function indexMouvements() {
    if (mouvementsParArticle !== null) { return mouvementsParArticle; }
    mouvementsParArticle = new Map();
    for (const mouvement of entreeDe('mouvements_stock').lignes) {
      let liste = mouvementsParArticle.get(mouvement.article_id);
      if (!liste) {
        liste = [];
        mouvementsParArticle.set(mouvement.article_id, liste);
      }
      liste.push(mouvement);
    }
    for (const liste of mouvementsParArticle.values()) { liste.sort(comparerMouvements); }
    return mouvementsParArticle;
  }

  // Stock recalculé depuis mouvements_stock : un inventaire fixe la valeur, une entrée ou un
  // retour ajoute, une sortie retire. Quantité illisible = 0. Renvoie un Number (0 sans mouvement).
  function stockArticle(articleId) {
    const mouvements = indexMouvements().get(articleId) || [];
    let stock = 0;
    for (const mouvement of mouvements) {
      const quantite = nombre(mouvement.quantite) || 0;
      if (mouvement.type === 'inventaire') { stock = quantite; }
      else if (mouvement.type === 'entrée' || mouvement.type === 'retour') { stock += quantite; }
      else if (mouvement.type === 'sortie') { stock -= quantite; }
    }
    return Math.round(stock * 1e6) / 1e6;          // évite 0.30000000000000004
  }

  // --- 4.5 Identifiants (ARCHITECTURE.md §4) ------------------------------------------------

  function horodatageCompact(date) {
    return date.getFullYear() + deuxChiffres(date.getMonth() + 1) + deuxChiffres(date.getDate())
      + deuxChiffres(date.getHours()) + deuxChiffres(date.getMinutes()) + deuxChiffres(date.getSeconds());
  }

  function caracteresAleatoires(nombreCaracteres) {
    let texte = '';
    for (let i = 0; i < nombreCaracteres; i += 1) {
      texte += CARACTERES_ALEATOIRES[Math.floor(Math.random() * CARACTERES_ALEATOIRES.length)];
    }
    return texte;
  }

  // Plus grand numéro des identifiants « prefixe + chiffres » présents dans les lignes (0 si aucun).
  function plusGrandNumero(lignesExistantes, nomCle, prefixe) {
    let plusGrand = 0;
    for (const ligne of lignesExistantes) {
      const identifiant = ligne[nomCle];
      if (typeof identifiant !== 'string' || !identifiant.startsWith(prefixe)) { continue; }
      const suite = identifiant.slice(prefixe.length);
      if (MOTIF_CHIFFRES.test(suite)) { plusGrand = Math.max(plusGrand, Number(suite)); }
    }
    return plusGrand;
  }

  // Identifiant suivant d'une table :
  //   - séquentiel : EQ-0001 (plus grand numéro existant + 1, zéros à gauche) ;
  //   - annuel     : DI-AAAA-0001, numérotation propre à chaque année ; l'année vient de dateIso
  //                  ('AAAA-…') ou, à défaut, de la date du jour ;
  //   - horodaté   : J-AAAAMMJJHHMMSS-XXXX (journal ; 4 caractères A-Z/0-9 tirés au hasard).
  // lignesExistantes : par défaut les lignes en cache de la table.
  function nouvelId(nomTable, lignesExistantes, dateIso) {
    const description = descriptionTable(nomTable);
    const format = description.identifiant;
    if (!format) {
      throw new Error('Donnees.nouvelId : la table « ' + nomTable + ' » n\'a pas d\'identifiant calculé.');
    }
    const existantes = lignesExistantes || lignes(nomTable);
    if (format.horodate) {
      const debut = format.prefixe + horodatageCompact(new Date()) + '-';
      const dejaPris = new Set(existantes.map((ligne) => ligne[description.cle]));
      let identifiant = debut + caracteresAleatoires(format.chiffres);
      while (dejaPris.has(identifiant)) { identifiant = debut + caracteresAleatoires(format.chiffres); }
      return identifiant;
    }
    let prefixe = format.prefixe;
    if (format.annuel) {
      const annee = MOTIF_ANNEE.exec(enTexte(dateIso));
      prefixe += (annee ? annee[1] : aujourdhui().slice(0, 4)) + '-';
    }
    const suivant = plusGrandNumero(existantes, description.cle, prefixe) + 1;
    return prefixe + String(suivant).padStart(format.chiffres, '0');
  }

  // --- 4.6 Journal --------------------------------------------------------------------------

  function entreeJournal(identifiantsPris, nomTable, idLigne, action) {
    const descriptionJournal = descriptionTable('journal');
    // Horodatage + 4 caractères aléatoires : on ne vérifie l'unicité que dans le lot en cours
    // (relire tout le journal à chaque entrée coûterait trop cher ; une collision est improbable).
    let identifiant = nouvelId('journal', []);
    while (identifiantsPris.has(identifiant)) { identifiant = nouvelId('journal', []); }
    identifiantsPris.add(identifiant);
    const ligne = {};
    for (const champ of descriptionJournal.champs) { ligne[champ.nom] = ''; }
    return Object.assign(ligne, {
      id: identifiant, date_heure: maintenant(), poste: identite.poste, profil: identite.profil,
      table: nomTable, id_ligne: enTexte(idLigne), action: enTexte(action),
    });
  }

  // Écrit des entrées au journal. Un échec ne fait jamais échouer l'action de l'utilisateur :
  // il est signalé en console (console.warn) et la fonction renvoie false.
  async function ecrireJournal(entrees) {
    if (entrees.length === 0) { return true; }
    try {
      await ajouter('journal', entrees);
      return true;
    } catch (erreur) {
      console.warn('Prévo : le journal n\'a pas pu être écrit (' + (erreur && erreur.message) + ').', erreur);
      return false;
    }
  }

  // Entrée de journal sans modification de donnée (ex. avertissement d'habilitation RG8).
  // Renvoie une promesse : l'identifiant de l'entrée, ou null si l'écriture a échoué.
  async function journaliser(nomTable, idLigne, action) {
    verifierInitialise();
    const entree = entreeJournal(new Set(), nomTable, idLigne, action);
    return (await ecrireJournal([entree])) ? entree.id : null;
  }

  // --- 4.7 Écriture : modifier (ARCHITECTURE.md §5.3) ---------------------------------------

  // Ligne écrite par une fonction de mutation → ligne propre : tous les champs du schéma et les
  // colonnes inconnues, en chaînes (valeur absente → valeur par défaut du schéma ou '').
  function ligneNormalisee(description, colonnesInconnues, ligne) {
    const propre = {};
    for (const champ of description.champs) {
      const valeur = ligne[champ.nom];
      if (valeur === undefined || valeur === null) {
        propre[champ.nom] = champ.defaut === undefined ? '' : champ.defaut;
      } else {
        propre[champ.nom] = typeof valeur === 'string' ? valeur : String(valeur);
      }
    }
    for (const nomColonne of colonnesInconnues) { propre[nomColonne] = enTexte(ligne[nomColonne]); }
    return propre;
  }

  // Compare les nouvelles lignes aux anciennes : [{ ligne, champs: null (création) | [noms] }].
  // Une ligne est d'abord comparée à celle de même position (cas courant), sinon à celle de même clé.
  function changementsEntre(description, colonnesInconnues, anciennes, ancienIndex, nouvelles) {
    const nomsChamps = description.champs.map((champ) => champ.nom).concat(colonnesInconnues);
    const changements = [];
    nouvelles.forEach((ligne, position) => {
      const cle = ligne[description.cle];
      let ancienne = anciennes[position];
      if (!ancienne || ancienne[description.cle] !== cle) { ancienne = cle === '' ? undefined : ancienIndex.get(cle); }
      if (!ancienne) {
        changements.push({ ligne: ligne, champs: null });
        return;
      }
      const champsModifies = nomsChamps.filter((nom) => enTexte(ancienne[nom]) !== ligne[nom]);
      if (champsModifies.length > 0) { changements.push({ ligne: ligne, champs: champsModifies }); }
    });
    return changements;
  }

  // Problèmes de lecture encore vrais après réécriture du fichier au format §3.1 : la structure,
  // l'encodage et les colonnes absentes sont réparés ; une valeur illisible (ou abîmée par Excel)
  // reste signalée tant qu'elle n'a pas été corrigée ; une colonne inconnue reste conservée.
  function problemesApresReecriture(anciens, nouvelIndex, colonnesInconnues) {
    const inconnues = new Set(colonnesInconnues);
    return anciens.filter((p) => {
      if (p.type === 'colonne') { return p.ligne === 1 && inconnues.has(p.champ); }
      if ((p.type === 'valeur' || p.type === 'excel') && p.id !== null && p.champ !== null) {
        const ligne = nouvelIndex.get(p.id);
        return Boolean(ligne) && ligne[p.champ] === p.valeur;
      }
      return false;
    });
  }

  function messageConflitPersistant(nomTable) {
    return 'Le fichier ' + nomTable + ' est modifié en même temps sur un autre poste. Réessayez dans un instant.';
  }

  // Modifie une table : fonction(lignes, outils) reçoit une COPIE des lignes, ajoute ou modifie
  // des objets et renvoie une valeur (renvoyée par modifier). outils : { nouvelId(lignes?, dateIso?),
  // maintenant(), aujourdhui() }. ErreurValidation levée par la fonction : jamais réessayée.
  // Conflit d'écriture : la table est relue et la fonction réappliquée (3 essais au total).
  // options : { action: texte ajouté au journal, journal: false pour ne pas journaliser }.
  async function modifier(nomTable, fonction, options) {
    verifierInitialise();
    const description = descriptionTable(nomTable);
    const reglages = options || {};
    const resultat = await enSerie(nomTable, async () => {
      let entree = entreeDe(nomTable);
      if (entree.perime) { entree = await rechargerSansAttente(nomTable); }
      for (let essai = 1; essai <= NOMBRE_ESSAIS; essai += 1) {
        statistiques.essais += 1;
        const copie = entree.lignes.map((ligne) => Object.assign({}, ligne));
        const outils = {
          nouvelId: (lignesExistantes, dateIso) => nouvelId(nomTable, lignesExistantes || copie, dateIso),
          maintenant: maintenant,
          aujourdhui: aujourdhui,
        };
        const valeurRendue = await fonction(copie, outils);      // ErreurValidation : sort tout de suite
        const nouvelles = copie.map((ligne) => ligneNormalisee(description, entree.colonnesInconnues, ligne));
        const changements = changementsEntre(description, entree.colonnesInconnues,
          entree.lignes, entree.index, nouvelles);
        if (changements.length === 0 && nouvelles.length === entree.lignes.length) {
          return { valeur: valeurRendue, changements: [] };      // rien à écrire
        }
        const octets = serialiser(nomTable, nouvelles, entree.colonnesInconnues);
        let reponse;
        try {
          reponse = await adaptateurActif.enregistrer(nomTable, octets, entree.version);
        } catch (erreur) {
          if (!(erreur instanceof ErreurConflit)) { throw erreur; }
          statistiques.conflits += 1;
          if (essai === NOMBRE_ESSAIS) {
            throw new ErreurConflit(messageConflitPersistant(nomTable), erreur.versionActuelle);
          }
          entree = await rechargerSansAttente(nomTable);
          continue;
        }
        const nouvelIndex = indexer(description, nouvelles);
        cache.set(nomTable, {
          lignes: nouvelles,
          colonnesInconnues: entree.colonnesInconnues,
          version: reponse && reponse.version !== undefined ? reponse.version : null,
          index: nouvelIndex,
          problemesLecture: problemesApresReecriture(entree.problemesLecture, nouvelIndex, entree.colonnesInconnues),
          perime: false,
          absente: false,
        });
        aRecalculer();
        return { valeur: valeurRendue, changements: changements };
      }
      throw new ErreurConflit(messageConflitPersistant(nomTable));   // jamais atteint (sécurité)
    });

    if (resultat.changements.length > 0) {
      signaler([nomTable], 'local');
      if (reglages.journal !== false && nomTable !== 'journal') {
        const complement = reglages.action ? ' — ' + reglages.action : '';
        const identifiantsPris = new Set();
        const entrees = resultat.changements.map((changement) => entreeJournal(identifiantsPris, nomTable,
          changement.ligne[description.cle],
          (changement.champs === null ? 'création' : 'modification : ' + changement.champs.join(', ')) + complement));
        await ecrireJournal(entrees);
      }
    }
    return resultat.valeur;
  }

  // --- 4.8 Écriture par ajout : ajouter (ARCHITECTURE.md §5.4) ------------------------------

  // Ajoute des lignes en fin de fichier (journal) : en-tête + lignes, sans BOM. Si le stockage
  // refuse (fichier réenregistré par Excel : en-tête ou encodage différent), repli sur modifier.
  // Le cache n'est pas complété ligne à ligne : la table est marquée périmée et sera relue
  // (jamais de version « devinée », qui ferait perdre des lignes au prochain modifier).
  // Renvoie { repli: vrai si le repli sur modifier a servi }.
  async function ajouter(nomTable, nouvellesLignes) {
    verifierInitialise();
    const description = descriptionTable(nomTable);
    const lignesAAjouter = nouvellesLignes || [];
    if (lignesAAjouter.length === 0) { return { repli: false }; }
    const colonnesInconnues = entreeDe(nomTable).colonnesInconnues;
    const propres = lignesAAjouter.map((ligne) => ligneNormalisee(description, colonnesInconnues, ligne));
    const octets = serialiser(nomTable, propres, colonnesInconnues, { bom: false });
    let reponse;
    try {
      reponse = await adaptateurActif.ajouter(nomTable, octets);
    } catch (erreur) {
      if (!(erreur instanceof ErreurConflit)) { throw erreur; }
      await modifier(nomTable, (lignesActuelles) => {
        for (const ligne of lignesAAjouter) { lignesActuelles.push(Object.assign({}, ligne)); }
      }, { journal: false });
      return { repli: true };              // modifier a relu puis réécrit la table : cache exact
    }
    marquerApresAjout(nomTable, propres, reponse);
    return { repli: false };
  }

  // Après un ajout direct : nos lignes sont ajoutées au cache (pour l'affichage et l'export),
  // la table reste PÉRIMÉE (modifier la relira avant toute réécriture : un autre poste a pu
  // ajouter des lignes avant les nôtres, absentes du cache) et la version rendue par
  // l'adaptateur est mémorisée dans `versionApresAjout` : tant que le stockage a exactement
  // cette version, la surveillance n'a pas besoin de relire la table (seul notre ajout l'a
  // changée depuis). La version du cache (`version`) n'est jamais « devinée ».
  function marquerApresAjout(nomTable, propres, reponse) {
    const entree = cache.get(nomTable);
    if (!entree) {
      cache.set(nomTable, Object.assign(entreeAbsente(), { perime: true }));
      return;
    }
    const lignesCompletees = entree.lignes.concat(propres);
    const versionRendue = reponse && typeof reponse.version === 'string' ? reponse.version : null;
    cache.set(nomTable, Object.assign({}, entree, {
      lignes: lignesCompletees,
      index: indexer(descriptionTable(nomTable), lignesCompletees),
      perime: true,
      absente: false,
      versionApresAjout: versionRendue,
    }));
    aRecalculer();
  }

  // Vrai si la table, périmée, n'a été changée que par nos propres ajouts : le stockage a encore
  // exactement la version rendue par notre dernier ajout.
  function changeeSeulementParNosAjouts(entree, versionStockage) {
    return Boolean(entree) && entree.perime && typeof entree.versionApresAjout === 'string'
      && entree.versionApresAjout === versionStockage;
  }

  // --- 4.9 Rafraîchissement (ARCHITECTURE.md §5.5) ------------------------------------------

  // complet : vrai → toute table périmée est relue ; faux (surveillance) → une table périmée
  // seulement par nos propres ajouts (même version qu'après notre dernier ajout) n'est pas
  // relue et reste périmée (modifier la relira avant toute réécriture).
  async function rafraichirMaintenant(complet) {
    verifierInitialise();
    const versions = await adaptateurActif.listerVersions();
    const aRelireMaintenant = (nomTable) => {
      const entree = cache.get(nomTable);
      const connue = Object.prototype.hasOwnProperty.call(versions, nomTable);
      const versionStockage = versions[nomTable] === undefined ? null : versions[nomTable];
      if (!entree) { return true; }
      if (entree.perime) { return complet || !connue || !changeeSeulementParNosAjouts(entree, versionStockage); }
      return connue && versionStockage !== entree.version;
    };
    // Journal relu parce qu'un autre poste y a écrit (et non seulement à cause de nos ajouts).
    let journalChangeAilleurs = false;
    const aRelire = Schema.nomsTables().filter(aRelireMaintenant);
    const relues = await Promise.all(aRelire.map((nomTable) => enSerie(nomTable, async () => {
      // Une écriture de ce poste (modifier) a pu relire la table entre-temps : rien à faire alors.
      if (!aRelireMaintenant(nomTable)) { return null; }
      if (nomTable === 'journal') {
        const versionStockage = versions.journal === undefined ? null : versions.journal;
        journalChangeAilleurs = !changeeSeulementParNosAjouts(cache.get('journal'), versionStockage);
      }
      await rechargerSansAttente(nomTable);
      return nomTable;
    })));
    const changees = relues.filter((nomTable) => nomTable !== null);
    // Le journal changé par un autre poste est signalé (onglets Suggestions et Décisions, lot 4) ;
    // le journal changé seulement par nos propres ajouts ne l'est pas.
    const signalees = changees.filter((nomTable) => nomTable !== 'journal' || journalChangeAilleurs);
    if (signalees.length) { signaler(signalees, 'distant'); }
    return changees;
  }

  // Un seul rafraîchissement à la fois. Une demande complète arrivant pendant un rafraîchissement
  // léger (surveillance) est enchaînée après lui ; toute autre demande partage celui en cours.
  function lancerRafraichissement(complet) {
    const enCours = rafraichissementEnCours;
    if (enCours && (enCours.complet || !complet)) { return enCours.promesse; }
    const avant = enCours ? enCours.promesse.catch(() => undefined) : Promise.resolve();
    const etat = { complet: complet, promesse: null };
    etat.promesse = avant.then(() => rafraichirMaintenant(complet)).finally(() => {
      if (rafraichissementEnCours === etat) { rafraichissementEnCours = null; }
    });
    rafraichissementEnCours = etat;
    return etat.promesse;
  }

  // Relit les tables modifiées ailleurs (version différente) ou périmées (toutes, y compris le
  // journal après nos propres ajouts : à appeler avant instantane(), ex. pour l'export).
  // Événement « changement » (origine « distant ») si au moins une table a changé ailleurs (le
  // journal changé seulement par nos propres ajouts n'est pas signalé). Renvoie leurs noms.
  function rafraichir() {
    return lancerRafraichissement(true);
  }

  // Rafraîchissement de la surveillance : léger (voir rafraichirMaintenant).
  async function rafraichirSansErreur() {
    try {
      await lancerRafraichissement(false);
    } catch (erreur) {
      console.warn('Prévo : rafraîchissement impossible (' + (erreur && erreur.message) + ').', erreur);
    }
  }

  function ongletVisible() {
    return typeof document === 'undefined' || document.visibilityState !== 'hidden';
  }

  // Rafraîchit toutes les periodeMs (défaut : paramètre rafraichissement_s, 20 s) tant que
  // l'onglet est visible, et à chaque retour sur l'onglet.
  function demarrerSurveillance(periodeMs) {
    verifierInitialise();
    arreterSurveillance();
    let periode = Number(periodeMs);
    if (!(periode > 0)) {
      const secondes = nombre(parametre('rafraichissement_s', String(RAFRAICHISSEMENT_PAR_DEFAUT_S)));
      periode = (secondes && secondes > 0 ? secondes : RAFRAICHISSEMENT_PAR_DEFAUT_S) * 1000;
    }
    minuteurSurveillance = setInterval(() => {
      if (ongletVisible()) { rafraichirSansErreur(); }
    }, periode);
    if (typeof document !== 'undefined') {
      surRetourOnglet = () => { if (ongletVisible()) { rafraichirSansErreur(); } };
      document.addEventListener('visibilitychange', surRetourOnglet);
    }
  }

  function arreterSurveillance() {
    if (minuteurSurveillance !== null) {
      clearInterval(minuteurSurveillance);
      minuteurSurveillance = null;
    }
    if (surRetourOnglet !== null && typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', surRetourOnglet);
    }
    surRetourOnglet = null;
  }

  // --- 4.10 Instantané ----------------------------------------------------------------------

  // { nomTable: Uint8Array } des 23 tables sérialisées depuis le cache (export ZIP, copie de la
  // démo). Le journal, écrit par ajout, peut être en retard : faire `await rafraichir()` avant.
  function instantane() {
    const fichiers = {};
    for (const nomTable of Schema.nomsTables()) {
      const entree = entreeDe(nomTable);
      fichiers[nomTable] = serialiser(nomTable, entree.lignes, entree.colonnesInconnues);
    }
    return fichiers;
  }

  // --- 4.11 Passage au format courant : version_schema (ARCHITECTURE.md §5.6 et §14.1) --------
  // Décision de Nicolas (2026-10-20) : JUSTE AVANT que parametres.version_schema passe de 1 à 2
  // sur une base existante, Prévo fait une sauvegarde automatique (« AAAA-MM-JJ_HHMMSS_avant-format-v2 »),
  // restaurable depuis Paramètres comme les autres. À appeler au démarrage, après chargerTout()
  // et avant toute autre écriture (appelée par passerAuFormatCourant dans js/app.js).

  const CLE_VERSION_SCHEMA = 'version_schema';
  const VERSION_SCHEMA_PAR_DEFAUT = 1;       // clé absente ou illisible : fichiers du lot 1 (format 1)

  // Version du format lue dans une valeur de parametres.csv (absente ou illisible → 1).
  function versionSchemaDe(valeur) {
    const lue = nombre(valeur);
    return lue === null ? VERSION_SCHEMA_PAR_DEFAUT : lue;
  }

  // Vrai si une sauvegarde est exigée avant le passage : tous les modes sauf la démo, où rien
  // n'est enregistré (son sauvegarder() lève toujours « indisponible »). Un stockage qui ne sait
  // pas sauvegarder n'est donc PAS dispensé : le passage est refusé (décision de Nicolas).
  function sauvegardeExigee() {
    return adaptateurActif.mode !== 'demo';
  }

  // Fait la sauvegarde « avant-format-vN » et renvoie son nom ; lève une erreur si le stockage
  // ne sait pas sauvegarder ou ne confirme pas la sauvegarde (aucun nom renvoyé).
  async function sauvegarderAvantFormat(versionCible) {
    if (typeof adaptateurActif.sauvegarder !== 'function') {
      throw new Error('ce mode de stockage ne sait pas faire de sauvegarde');
    }
    const nom = await adaptateurActif.sauvegarder('avant-format-v' + versionCible);
    if (!nom) { throw new Error("le stockage n'a pas confirmé la sauvegarde (aucun nom renvoyé)"); }
    return nom;
  }

  // Message d'une erreur sans point final (pour l'insérer au milieu d'une phrase).
  function messageSansPointFinal(erreur) {
    return String((erreur && erreur.message) || 'erreur inconnue').replace(/[\s.]+$/, '');
  }

  // Met parametres.version_schema à Schema.version, après une sauvegarde automatique.
  // Idempotente : si la version est déjà à jour (ou plus récente), rien n'est fait.
  // Renvoie { misAJour, sauvegarde } :
  //   - misAJour   : vrai si CET appel a écrit la nouvelle version dans parametres.csv ;
  //   - sauvegarde : nom de la sauvegarde faite juste avant, ou null (aucune, ou démo).
  // Sauvegarde impossible → ErreurStockage, et la version n'est PAS changée : la mise à jour
  // (sauvegarde comprise) sera retentée à la prochaine ouverture.
  // Deux postes ouverts en même temps sur une base en format 1 peuvent faire chacun leur
  // sauvegarde : sans gravité (deux copies identiques). Un seul écrit la version : l'autre, en
  // conflit, relit parametres.csv (lignes fraîches) et n'écrit rien car la version y est déjà.
  async function mettreAJourVersionSchema() {
    verifierInitialise();
    const versionCible = Schema.version;
    if (!cache.has('parametres')) { await rechargerTable('parametres'); }
    if (baseVide() || versionSchemaDe(parametre(CLE_VERSION_SCHEMA, '')) >= versionCible) {
      return { misAJour: false, sauvegarde: null };      // base pas encore créée, ou déjà à jour
    }

    // 1. La sauvegarde d'abord : sans elle, on ne touche à rien.
    let sauvegarde = null;
    if (sauvegardeExigee()) {
      try {
        sauvegarde = await sauvegarderAvantFormat(versionCible);
      } catch (erreur) {
        throw new ErreurStockage('Sauvegarde avant le passage au format ' + versionCible + ' impossible : '
          + messageSansPointFinal(erreur) + ' ; la mise à jour sera retentée à la prochaine ouverture.', erreur);
      }
    }

    // 2. Puis la version, décidée sur les lignes FRAÎCHES (modifier relit la table en cas de
    // conflit et réapplique la fonction) : rien n'est écrit si un autre poste l'a déjà fait.
    const action = 'passage au format ' + versionCible + ' du fichier ; '
      + (sauvegarde ? 'sauvegarde ' + sauvegarde + ' faite juste avant' : 'sans sauvegarde (démo)');
    const misAJour = await modifier('parametres', (lignesParametres) => {
      const ligne = lignesParametres.find((l) => l.cle === CLE_VERSION_SCHEMA);
      if (ligne && versionSchemaDe(ligne.valeur) >= versionCible) { return false; }
      if (ligne) {
        ligne.valeur = String(versionCible);
      } else {
        lignesParametres.push({ cle: CLE_VERSION_SCHEMA, valeur: String(versionCible) });
      }
      return true;
    }, { action: action });
    return { misAJour: misAJour, sauvegarde: sauvegarde };
  }

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
    documentAffichable: documentAffichable,
    // 3. CSV
    csv: csv,
    // 4. Chargement, mutation, journal, rafraîchissement
    initialiser: initialiser,
    definirIdentite: definirIdentite,
    chargerTout: chargerTout,
    baseVide: baseVide,
    lignes: lignes,
    trouver: trouver,
    version: version,
    parametre: parametre,
    rechargerTable: rechargerTable,
    problemes: problemes,
    stockArticle: stockArticle,
    nouvelId: nouvelId,
    modifier: modifier,
    ajouter: ajouter,
    journaliser: journaliser,
    rafraichir: rafraichir,
    demarrerSurveillance: demarrerSurveillance,
    arreterSurveillance: arreterSurveillance,
    instantane: instantane,
    mettreAJourVersionSchema: mettreAJourVersionSchema,
    evenements: evenements,
    statistiques: statistiques,
  };
})();
