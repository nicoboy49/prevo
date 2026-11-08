'use strict';
// Donnees : accès aux données de Prévo (les 23 fichiers CSV décrits par js/schema.js).
// Contrat : docs/ARCHITECTURE.md §3 (format des CSV) et §5 (Donnees).
// Ce fichier contient, dans l'ordre :
//   1. les erreurs propres à Prévo ;
//   2. les dates, nombres et la normalisation des valeurs saisies à la main ;
//   3. la lecture et l'écriture des CSV (protection par apostrophe, lecture tolérante) ;
//   4. le chargement, les mutations, le journal et le rafraîchissement (tâche T08).
// Toute valeur en mémoire est une CHAÎNE au format du fichier : dates ISO, booléens 0/1,
// point décimal. Dépendances : Schema (js/schema.js) et Papa (js/lib/papaparse.min.js) ; Formats
// (js/formats.js) pour le seul passage au format courant (§4.11 : etatDuFormat, migrerAuFormatCourant).

const Donnees = (() => {

  // ===========================================================================
  // 1. Erreurs
  // ===========================================================================

  // Le fichier a été modifié ailleurs depuis notre lecture (version périmée).
  // versionActuelle : la version que le stockage a trouvée (null si inconnue).
  class ErreurConflit extends Error {
    constructor(message, versionActuelle) {
      super(message || I18n.t('socle.constructor.fichier_ete_modifie_meme'));
      this.name = 'ErreurConflit';
      this.versionActuelle = versionActuelle === undefined ? null : versionActuelle;
    }
  }

  // Action refusée par une règle métier : le message est montré tel quel à l'utilisateur.
  // Une ErreurValidation n'est jamais réessayée.
  class ErreurValidation extends Error {
    constructor(message) {
      super(message || I18n.t('socle.constructor.action_refusee'));
      this.name = 'ErreurValidation';
    }
  }

  // Lecture ou écriture impossible (ex. fichier ouvert dans Excel). Message en français.
  // cause : l'erreur d'origine, gardée pour le diagnostic (facultative).
  class ErreurStockage extends Error {
    constructor(message, cause) {
      super(message || I18n.t('socle.constructor.lecture_ecriture_fichier_impossible'));
      this.name = 'ErreurStockage';
      this.cause = cause === undefined ? null : cause;
    }
  }

  // Écriture refusée : les données viennent d'une version plus récente de Prévo (parametres.version_schema plus
  // grand que Schema.version, décision D169) et sont ouvertes en lecture seule. format : le format de la base.
  // Sous-classe d'ErreurStockage : partout où une erreur de stockage est montrée telle quelle, ce message l'est aussi.
  class ErreurLectureSeule extends ErreurStockage {
    constructor(format) {
      super(I18n.t('socle.constructor.donnees_viennent_version_plus', { format, version: Schema.version }));
      this.name = 'ErreurLectureSeule';
      this.format = format;
    }
  }

  // Écriture refusée : le fichier de la table est abîmé (structure, ou valeurs au-delà de l'en-tête : csv.analyser,
  // entree.abime) ; le réécrire en perdrait une partie sans le dire (règle numéro un, CS140 ; défaut trouvé par la
  // recette T193). Seuls l'import ZIP (option remplacerFichierAbime) et la restauration d'une sauvegarde (adaptateur)
  // remplacent un tel fichier. T200 : la garde est aussi dans la fonction d'écriture commune de chaque adaptateur
  // (enregistrer : fichier abîmé ; ajouter : fichier qui finit par un guillemet ouvert, csv.finitDansUnGuillemetOuvert),
  // par laquelle passent toutes les écritures. Sous-classe d'ErreurStockage : le message est montré tel quel.
  class ErreurFichierAbime extends ErreurStockage {
    constructor(nomTable, fichier) {
      super(I18n.t('socle.constructor.fichier_abime_tete_coupe', { fichier: (fichier || nomTable + '.csv') }));
      this.name = 'ErreurFichierAbime';
      this.table = nomTable;
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
    'yes': '1', 'no': '0',                 // anglais aussi : même lecture quelle que soit la langue (T287)
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
    const contenu = await blob.text();
    const page = `<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>${echapper(nom)}</title><style>html,body{margin:0;height:100%;background:#fff}iframe{border:0;display:block;width:100%;height:100%}</style></head><body><iframe sandbox="allow-modals" title="${echapper(nom)}" srcdoc="${echapper(contenu)}"></iframe></body></html>`;
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

  // Colonnes inconnues (hors schéma, conservées) : traitées comme un champ texte, avec la même
  // protection par apostrophe à l'écriture et la même relecture (audit I3).
  const CHAMP_INCONNU = Object.freeze({ type: 'texte' });

  // --- 3.2 Décodage des octets --------------------------------------------------------------

  const decodeurUtf8Strict = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true });
  const decodeurWindows1252 = new TextDecoder('windows-1252');

  // Uint8Array, ArrayBuffer, autre vue typée ou tableau de nombres → Uint8Array.
  function enOctets(entree) {
    if (entree instanceof Uint8Array) { return entree; }
    if (entree instanceof ArrayBuffer) { return new Uint8Array(entree); }
    if (ArrayBuffer.isView(entree)) { return new Uint8Array(entree.buffer, entree.byteOffset, entree.byteLength); }
    if (Array.isArray(entree)) { return Uint8Array.from(entree); }
    throw new TypeError(I18n.t('socle.en_octets.donnees_csv_octets_attendus'));
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
    if (!description) { throw new Error(I18n.t('socle.description_table.donnees_csv_table_inconnue', { nomTable })); }
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
      for (const nomColonne of inconnues) { cellules.push(celluleCsv(ecrireValeur(CHAMP_INCONNU, ligne[nomColonne]))); }
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
      case 'date': return I18n.t('socle.explication_valeur_illisible.pas_date_valide_formats');
      case 'date_heure': return I18n.t('socle.explication_valeur_illisible.pas_date_heure_valide');
      case 'decimal': return I18n.t('socle.explication_valeur_illisible.pas_nombre_exemples_acceptes');
      case 'entier': return I18n.t('socle.explication_valeur_illisible.pas_nombre_entier');
      case 'booleen': return I18n.t('socle.explication_valeur_illisible.pas_reconnu_comme_oui');
      case 'choix': {
        // Valeurs stockées (D155), telles qu'elles doivent être écrites dans le fichier.
        const valeurs = (champ.valeurs || []).join(', ');
        return I18n.t('socle.explication_valeur_illisible.fait_pas_partie_valeurs', { valeurs });
      }
      default: return I18n.t('socle.explication_valeur_illisible.illisible');
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
            explication: I18n.t('socle.lire_cellule.valeur_probablement_abimee_excel') } };
        }
        if (MOTIF_ERREUR_FORMULE_EXCEL.test(valeur)) {
          return { valeur: valeur, probleme: { gravite: 'attention', type: 'excel',
            explication: I18n.t('socle.lire_cellule.valeur_probablement_abimee_excel_formule') } };
        }
        return { valeur: valeur, probleme: null };
      }
      case 'date': resultat = normaliserDate(nettoye); break;
      case 'date_heure': resultat = normaliserDateHeure(nettoye); break;
      case 'decimal': resultat = normaliserDecimal(nettoye); break;
      case 'entier': resultat = normaliserEntier(nettoye); break;
      case 'booleen': resultat = normaliserBooleen(nettoye); break;
      case 'choix': {
        resultat = normaliserChoix(nettoye, champ.valeurs);
        // Valeur retirée du schéma (champ.retirees : le type « mode » des pages du wiki, §20.12) : une ancienne ligne
        // reste lue sans erreur ; le contrôle de sa table la signale.
        const retiree = !resultat.ok && champ.retirees ? normaliserChoix(nettoye, champ.retirees) : null;
        if (retiree && retiree.ok) { resultat = retiree; }
        break;
      }
      default:   // id, ref, document : simple nettoyage des espaces
        return { valeur: nettoye.trim(), probleme: null };
    }
    if (resultat.ok) { return { valeur: resultat.valeur, probleme: null }; }
    return { valeur: resultat.valeur, probleme: { gravite: 'erreur', type: 'valeur',
      explication: I18n.t('socle.lire_cellule.valeur_conservee_telle_quelle', { explicationValeurIllisible: explicationValeurIllisible(champ) }) } };
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
      const numero = index + 1;
      const nomConserve = nomInconnuLibre(nomColonne === '' ? I18n.t('socle.associer_colonnes.colonne_numero', { numero }) : nomColonne);
      colonnes.push({ inconnue: nomConserve });
      inconnues.push(nomConserve);
      const message = champ
        ? I18n.t('socle.associer_colonnes.colonne_apparait_deux_fois', { descriptionLibelle: description.libelle, nomColonne, fichier: description.fichier, nomConserve })
        : I18n.t('socle.associer_colonnes.colonne_fait_pas_partie', { descriptionLibelle: description.libelle, nomConserve, fichier: description.fichier });
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
        I18n.t('socle.probleme_colonne_absente.colonne_ajoutee_version_format', { descriptionLibelle: description.libelle, champNom: champ.nom, depuisVersion: champ.depuisVersion }));
    }
    const valeurParDefaut = champ.defaut === undefined ? '' : champ.defaut;
    const suite = valeurParDefaut === ''
      ? I18n.t('socle.probleme_colonne_absente.valeur_laissee_vide')
      : I18n.t('socle.probleme_colonne_absente.valeur_defaut_utilisee', { valeurParDefaut });
    return probleme('attention', 'colonne', nomTable, 1, null, champ.nom, null,
      I18n.t('socle.probleme_colonne_absente.colonne_absente_sera_ajoutee', { descriptionLibelle: description.libelle, champNom: champ.nom, champLibelle: champ.libelle, fichier: description.fichier, suite }));
  }

  // Octets (ou texte) d'un fichier CSV → { lignes, colonnesInconnues, problemes, encodage, separateur, entete }.
  // Chaque ligne est un objet avec TOUS les champs du schéma (valeur par défaut du schéma si la
  // colonne est absente du fichier, sinon chaîne vide), plus les colonnes inconnues.
  // entete : les noms de la ligne d'en-tête du fichier, tels qu'écrits (espaces des bords retirés) ; [] pour un
  // fichier vide. Il sert à reconnaître le format du fichier (Formats.formatDuFichier, décision D167).
  // abime : vrai si le fichier ne se relit pas sans perte (structure abîmée, ou valeurs au-delà de l'en-tête) :
  // le réécrire perdrait ces valeurs, le passage au format courant ne le réécrit donc pas (§4.11).
  function analyser(nomTable, entree) {
    const description = descriptionTable(nomTable);
    const decode = decoder(entree);
    const texte = decode.texte;
    const separateur = choisirSeparateur(texte);
    const problemes = [];
    const resultat = { lignes: [], colonnesInconnues: [], problemes: problemes,
      encodage: decode.encodage, separateur: separateur, entete: [], abime: false };

    if (decode.encodage === 'windows-1252') {
      problemes.push(probleme('info', 'encodage', nomTable, null, null, null, null,
        I18n.t('socle.analyser.pas_utf_8_sans', { descriptionLibelle: description.libelle, fichier: description.fichier })));
    }
    if (texte.trim() === '') { return resultat; }      // fichier vide : table vide, rien à signaler

    const decoupage = decouper(texte, separateur);
    const enregistrements = decoupage.enregistrements;
    const entete = enregistrements.length > 0 ? enregistrements[0].cellules : [];
    resultat.entete = entete.map((cellule) => cellule.trim());
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
      resultat.abime = true;
      problemes.push(probleme('erreur', 'valeur', nomTable, erreur.numero, null, null, null,
        I18n.t('socle.analyser.ligne_structure_fichier_abimee', { descriptionLibelle: description.libelle, numero: erreur.numero, fichier: description.fichier, erreurMessage: erreur.message })));
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
              I18n.t('socle.analyser.reperage_champ_libelle_contient_lu_valeur', { reperage, champLibelle: colonne.champ.libelle, luValeur: lu.valeur, explication: lu.probleme.explication })));
          }
        } else if (colonne.inconnue !== undefined) {
          ligne[colonne.inconnue] = relireValeur(CHAMP_INCONNU, brut).replace(MOTIF_FIN_PARASITE, '');
        }
      }

      // Cellules au-delà de l'en-tête : signalées si elles ne sont pas vides, puis ignorées.
      for (let index = colonnes.length; index < cellules.length; index += 1) {
        if (cellules[index].trim() !== '') {
          resultat.abime = true;
          const [valeurIgnoree, colonneIgnoree] = [cellules[index], index + 1];
          problemes.push(probleme('attention', 'colonne', nomTable, numero, identifiant, null, cellules[index],
            I18n.t('socle.analyser.ligne_contient_plus_valeurs', { reperage, valeurIgnoree, colonneIgnoree })));
        }
      }
      resultat.lignes.push(ligne);
    }
    return resultat;
  }

  // --- 3.5 Fin dans une cellule entre guillemets jamais fermée (T200) -------------------------

  // Vrai si les octets d'un CSV finissent DANS une cellule entre guillemets jamais fermée : une ligne ajoutée à la fin
  // (journal, ajouter) serait avalée par cette cellule à la relecture, donc perdue. Sur les octets bruts, sans
  // décodage ; même automate que finit_dans_un_guillemet_ouvert de serveur.py (mêmes exemples, mêmes réponses) :
  // BOM UTF-8 de tête ignoré ; séparateur « ; », sauf si la première ligne non vide n'a aucun « ; » et a une « , » ;
  // un guillemet n'ouvre une cellule qu'en tout début de cellule (aucun blanc sauté) ; « "" » est un guillemet doublé.
  const OCTET_GUILLEMET = 0x22;
  const OCTET_CR = 0x0D;
  const OCTET_LF = 0x0A;
  const OCTET_POINT_VIRGULE = 0x3B;
  const OCTET_VIRGULE = 0x2C;
  const OCTETS_BLANCS_LIGNE = [0x20, 0x09, 0x0B, 0x0C];      // espace, tabulations, saut de page
  const DEBUT_DE_CELLULE = 0;
  const DANS_LA_CELLULE = 1;
  const ENTRE_GUILLEMETS = 2;
  const GUILLEMET_VU = 3;

  // Séparateur des octets (comme choisirSeparateur sur le texte) : « , » si la première ligne non vide n'a aucun « ; »
  // et a une « , », sinon « ; ».
  function separateurDesOctets(octets, debut) {
    let ligneNonVide = false;
    let pointVirgule = false;
    let virgule = false;
    for (let position = debut; position < octets.length; position += 1) {
      const octet = octets[position];
      if (octet === OCTET_CR || octet === OCTET_LF) {
        if (ligneNonVide) { break; }
        pointVirgule = false;
        virgule = false;
        continue;
      }
      if (OCTETS_BLANCS_LIGNE.indexOf(octet) === -1) { ligneNonVide = true; }
      if (octet === OCTET_POINT_VIRGULE) { pointVirgule = true; } else if (octet === OCTET_VIRGULE) { virgule = true; }
    }
    return ligneNonVide && !pointVirgule && virgule ? OCTET_VIRGULE : OCTET_POINT_VIRGULE;
  }

  function finitDansUnGuillemetOuvert(entree) {
    const octets = enOctets(entree);
    const debut = octets.length >= 3 && octets[0] === 0xEF && octets[1] === 0xBB && octets[2] === 0xBF ? 3 : 0;
    const separateur = separateurDesOctets(octets, debut);
    let etat = DEBUT_DE_CELLULE;
    for (let position = debut; position < octets.length; position += 1) {
      const octet = octets[position];
      const finDeCellule = octet === separateur || octet === OCTET_CR || octet === OCTET_LF;
      if (etat === ENTRE_GUILLEMETS) {
        if (octet === OCTET_GUILLEMET) { etat = GUILLEMET_VU; }
      } else if (etat === GUILLEMET_VU && octet === OCTET_GUILLEMET) {
        etat = ENTRE_GUILLEMETS;                                  // guillemet doublé
      } else if (finDeCellule) {
        etat = DEBUT_DE_CELLULE;
      } else if (etat === DEBUT_DE_CELLULE && octet === OCTET_GUILLEMET) {
        etat = ENTRE_GUILLEMETS;
      } else {
        etat = DANS_LA_CELLULE;
      }
    }
    return etat === ENTRE_GUILLEMETS;
  }

  const csv = {
    decoder: decoder,
    aProteger: aProteger,
    ecrireValeur: ecrireValeur,
    relireValeur: relireValeur,
    analyser: analyser,
    serialiser: serialiser,
    finitDansUnGuillemetOuvert: finitDansUnGuillemetOuvert,
  };

  // ===========================================================================
  // 4. Chargement, mutation, journal, rafraîchissement (ARCHITECTURE.md §5.2 à §5.5)
  // ===========================================================================
  // Le cache garde, pour chaque table, une « entrée » :
  //   { lignes, colonnesInconnues, entete, version, index, problemesLecture, perime, absente }
  //   - lignes            : tableau d'objets (toutes les valeurs sont des chaînes) ;
  //   - colonnesInconnues : colonnes du fichier qui ne sont pas dans le schéma (conservées) ;
  //   - entete            : noms de la ligne d'en-tête du fichier (lue, ou écrite par nous) ; [] si le fichier
  //                         est absent ou vide. Le format du fichier s'en déduit (Formats.formatDuFichier) ;
  //   - abime             : vrai si le fichier lu ne se réécrirait pas sans perte (csv.analyser) ;
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
  const tablesDitesAbimees = new Set();      // tables dont l'événement « fichierAbime » est déjà émis (T200)
  const statistiques = { conflits: 0, essais: 0 };

  // Résultats calculés à la demande, oubliés à chaque changement de données (« à recalculer »).
  let problemesCalcules = null;
  let mouvementsParArticle = null;

  let minuteurSurveillance = null;
  let surRetourOnglet = null;
  let rafraichissementEnCours = null;

  // Format des fichiers (§4.11) : format de la base quand il dépasse Schema.version (lecture seule, D169), sinon
  // null ; une fois vu pendant une session, il le reste jusqu'au prochain initialiser(). problemesFormat : tables à
  // l'en-tête illisible laissées telles quelles par le dernier passage au format courant.
  let formatPlusRecent = null;
  let problemesFormat = [];

  // --- 4.1 Outils internes ------------------------------------------------------------------

  function verifierInitialise() {
    if (!adaptateurActif) {
      throw new Error(I18n.t('socle.verifier_initialise.donnees_appelez_donnees_initialiser'));
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
    return { lignes: [], colonnesInconnues: [], entete: [], abime: false, version: null, index: new Map(),
      problemesLecture: [], perime: false, absente: true };
  }

  // En-tête que serialiser écrit pour une table : les champs du schéma, puis les colonnes inconnues conservées.
  function enteteEcrit(description, colonnesInconnues) {
    return description.champs.map((champ) => champ.nom).concat(colonnesInconnues);
  }

  // Résultat de adaptateur.charger → entrée de cache.
  function entreeDepuisFichier(nomTable, octets, version) {
    if (octets === null || octets === undefined) { return entreeAbsente(); }
    const lu = analyser(nomTable, octets);
    return {
      lignes: lu.lignes,
      colonnesInconnues: lu.colonnesInconnues,
      entete: lu.entete,
      abime: lu.abime,
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
    if (nomTable === 'parametres') { noterFormatDeLaBase(); }
    return entree;
  }

  function signaler(nomsTables, origine) {
    evenements.dispatchEvent(new CustomEvent('changement', {
      detail: { tables: nomsTables, origine: origine },
    }));
  }

  // --- 4.2 Lecture --------------------------------------------------------------------------

  // adaptateur : objet du contrat ARCHITECTURE.md §6 ; options : { poste, profil } (pour le journal).
  // Vide le cache : appeler ensuite chargerTout(). Les écritures passent par protegerEcritures(adaptateur)
  // (refusées en lecture seule, §4.11) : passer le même adaptateur protégé à l'application (App.adaptateur).
  function initialiser(adaptateur, options) {
    arreterSurveillance();
    adaptateurActif = protegerEcritures(adaptateur);
    definirIdentite(options);
    cache.clear();
    filesAttente.clear();
    statistiques.conflits = 0;
    statistiques.essais = 0;
    rafraichissementEnCours = null;
    formatPlusRecent = null;
    problemesFormat = [];
    tablesDitesAbimees.clear();
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
    noterFormatDeLaBase();
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
    const numero = position + 1;
    return cle ? cle : I18n.t('socle.reperage_ligne.ligne_donnees_sans_identifiant', { numero });
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
          I18n.t('socle.controler_identifiants.pas_identifiant_colonne_vide', { descriptionLibelle: description.libelle, reperageLigne: reperageLigne(description, ligne, position), fichier: description.fichier, cle: description.cle })));
        return;
      }
      if (vus.has(cle)) {
        resultat.push(probleme('erreur', 'doublon', nomTable, null, cle, description.cle, cle,
          I18n.t('socle.controler_identifiants.identifiant_apparait_plusieurs_fois', { descriptionLibelle: description.libelle, cle, fichier: description.fichier, numero: (position + 1) })));
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
          explication = I18n.t('socle.controler_references.existe_mais_lieu', { descriptionCibleLibelle: descriptionCible.libelle, familleTrouvee, filtre: decrireFiltre(cibles.filtre) });
        } else {
          explication = cibles.filtre
            ? I18n.t('socle.controler_references.existe_pas', { descriptionCibleLibelle: descriptionCible.libelle, filtre: decrireFiltre(cibles.filtre) })
            : I18n.t('socle.controler_references.existe_pas_sans_filtre', { descriptionCibleLibelle: descriptionCible.libelle });
        }
        resultat.push(probleme('erreur', 'reference', nomTable, null, ligne[description.cle], champ.nom, valeur,
          I18n.t('socle.controler_references.reperage_champ_libelle_vaut_valeur', { reperage, champLibelle: champ.libelle, valeur, explication })));
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
          I18n.t('socle.controler_coherence.demande_acceptee_mais_aucun', { id: (demande.id || I18n.t('socle.controler_coherence.sans_identifiant')) })));
      } else if (!indexOrdres.has(demande.ot_id)) {
        resultat.push(probleme('erreur', 'incoherence', 'demandes', null, demande.id, 'ot_id', demande.ot_id,
          I18n.t('socle.controler_coherence.demande_acceptee_mais_ordre', { id: (demande.id || I18n.t('socle.controler_coherence.sans_identifiant')), ot_id: demande.ot_id })));
      }
    }
    for (const ordre of entreeDe('ordres_travail').lignes) {
      if (ordre.di_id === '') { continue; }
      const demande = indexDemandes.get(ordre.di_id);
      if (demande && demande.statut !== 'Acceptée' && demande.statut !== 'Regroupée') {
        // Cas d'une acceptation interrompue (l'OT est créé avant la DI, §5.3) : accepter de nouveau
        // la demande réutilise cet OT. Pas bloquant, d'où « attention ».
        resultat.push(probleme('attention', 'incoherence', 'ordres_travail', null, ordre.id, 'di_id', ordre.di_id,
          I18n.t('socle.controler_coherence.ordre_travail_vient_demande', { id: (ordre.id || I18n.t('socle.controler_coherence.sans_identifiant')), di_id: ordre.di_id, statut: Schema.libelleValeur('demandes', 'statut', demande.statut) })));
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
    // Une panne (PANNE-<code symptôme encodé>, page calculée du wiki, §20.12) : son code doit exister ; qu'elle ait un cas,
    // c'est le contrôle du wiki qui le dit (Wiki.controleDuWiki, même définition que sa page).
    const symptomes = new Map(entreeDe('codes_defaillance').lignes.filter((c) => enTexte(c.famille).trim() === 'symptôme')
      .map((c) => ['PANNE-' + encodeURIComponent(enTexte(c.code).trim()), c]));
    const cibles = { 'EQ-': entreeDe('equipements').index, 'ART-': entreeDe('articles').index, 'WP-': pages.index, 'PANNE-': symptomes };
    const ordres = entreeDe('ordres_travail').index;
    const typesRetires = (descriptionTable('wiki_pages').champs.find((champ) => champ.nom === 'type') || {}).retirees || [];
    const parCle = new Map();
    const signaler = (gravite, page, champ, valeur, message) => resultat.push(probleme(gravite, 'wiki', 'wiki_pages', null,
      page.id, champ, valeur, I18n.t('socle.controler_wiki.page_wiki', { id: (page.id || I18n.t('socle.controler_coherence.sans_identifiant')), pageTitre: page.titre, message })));
    for (const page of pages.lignes.filter((ligne) => ligne.statut !== 'archivée')) {
      for (const lien of listeDe(page.liens)) {
        const prefixe = Object.keys(cibles).find((debut) => lien.startsWith(debut));
        const cible = prefixe ? cibles[prefixe].get(lien) : null;
        if (!cible || (prefixe === 'WP-' && cible.statut === 'archivée')) {
          signaler('attention', page, 'liens', lien, I18n.t('socle.controler_wiki.lien_vers_page_inexistante', { lien }));
        }
      }
      for (const ot of listeDe(page.ot_cites)) {
        if (!ordres.has(ot)) { signaler('attention', page, 'ot_cites', ot, I18n.t('socle.controler_wiki.cite_ot_existe_pas', { ot })); }
      }
      if (enTexte(page.texte).trim() && !listeDe(page.ot_cites).length) {
        signaler('info', page, 'ot_cites', '', I18n.t('socle.controler_wiki.cite_aucun_ot'));
      }
      // Type retiré par la refonte 2 (§20.12 : « mode », une panne est une page calculée) : la ligne reste lue, à archiver.
      if (typesRetires.includes(page.type)) {
        signaler('attention', page, 'type', page.type, I18n.t('socle.controler_wiki.type_page_retire_panne', { pageType: Schema.libelleValeur('wiki_pages', 'type', page.type) }));
      }
      // Rattachement (sous-page, §20.4 : sa mère, de même type ; savoir-faire) vers une page archivée. Une page absente
      // est déjà une référence cassée ; une sous-page n'a pas d'ancrage propre (ni equipement_id ni article_id).
      const mere = enTexte(page.rattache_a).trim() ? pages.index.get(enTexte(page.rattache_a).trim()) : null;
      if (mere && mere.statut === 'archivée') {
        signaler('attention', page, 'rattache_a', mere.id, mere.type === page.type
          ? I18n.t('socle.controler_wiki.sous_page_page_archivee', { mereTitre: mere.titre, mereId: mere.id })
          : I18n.t('socle.controler_wiki.rattachee_page_archivee', { mereTitre: mere.titre, mereId: mere.id }));
      }
      const cle = enTexte(page.cle).trim();
      if (cle) { parCle.set(cle, (parCle.get(cle) || []).concat([page])); }
    }
    parCle.forEach((memes) => {
      if (memes.length > 1) {
        signaler('attention', memes[1], 'cle', memes[1].cle, I18n.t('socle.controler_wiki.meme_titre_page_deux', { page: memes[0].id }));
      }
    });
    const ancienne = typeof Wiki !== 'undefined' && Wiki.SEUILS ? Wiki.SEUILS.contradictionAncienneJours : 30;
    for (const entree of journal.filter((ligne) => ligne.statut === 'validée')) {
      let changements = [];
      let contradictions = [];
      try { changements = JSON.parse(entree.changements || '[]') || []; } catch (erreur) { changements = null; }
      try { contradictions = JSON.parse(entree.contradictions || '[]') || []; } catch (erreur) { contradictions = []; }
      const absents = changements === null ? [I18n.t('socle.controler_wiki.changements_illisibles')] : changements.filter((c) => {
        const page = c && c.page ? pages.index.get(c.page) : null;
        return !page || (Number(page.version) || 0) < (Number(c.version_avant) || 0) + 1;
      }).map((c) => (c && (c.page || c.titre)) || '?');
      if (absents.length) {
        resultat.push(probleme('attention', 'wiki', 'wiki_journal', null, entree.id, 'changements', absents.join(', '),
          I18n.t('socle.controler_wiki.entree_journal_wiki_validee', { entreeId: entree.id, pages: absents.join(', ') })));
      }
      contradictions.filter((c) => c && c.statut === 'ouverte'
        && joursDepuis(entree.decide_le || entree.traite_le) > ancienne).forEach((c) => {
        resultat.push(probleme('info', 'wiki', 'wiki_journal', null, entree.id, 'contradictions', enTexte(c.page),
          I18n.t('socle.controler_wiki.entree_journal_wiki_contradiction', { entreeId: entree.id, n: ancienne, page: enTexte(c.page) })));
      });
    }
  }

  function calculerProblemes() {
    const resultat = [];
    const memoireCibles = new Map();
    for (const nomTable of Schema.nomsTables()) {
      for (const lu of entreeDe(nomTable).problemesLecture) { resultat.push(lu); }
    }
    for (const laissee of problemesFormatActuels()) { resultat.push(laissee); }
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
      throw new Error(I18n.t('socle.nouvel_id.donnees_nouvel_id_table_pas', { nomTable }));
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
    // Horodatage + 4 caractères aléatoires : unicité vérifiée dans le lot en cours ET dans le journal déjà lu ou
    // écrit par ce poste (index du cache : aucun coût). Avant T261, seul le lot comptait : deux lots écrits dans la
    // même seconde pouvaient tirer les mêmes caractères, et le contrôle de la base signalait à jamais le doublon.
    // Reste possible : un autre poste qui écrit dans la même seconde, avant de relire nos lignes (une chance sur
    // 1,7 million pour deux entrées de la même seconde).
    const journalLu = cache.get('journal');
    const dejaEcrit = (id) => Boolean(journalLu && journalLu.index && journalLu.index.has(id));
    let identifiant = nouvelId('journal', []);
    while (identifiantsPris.has(identifiant) || dejaEcrit(identifiant)) { identifiant = nouvelId('journal', []); }
    identifiantsPris.add(identifiant);
    const ligne = {};
    for (const champ of descriptionJournal.champs) { ligne[champ.nom] = ''; }
    return Object.assign(ligne, {
      id: identifiant, date_heure: maintenant(), poste: identite.poste, profil: identite.profil,
      table: nomTable, id_ligne: enTexte(idLigne), action: enTexte(action),
    });
  }

  // Écrit des entrées au journal. Un échec ne fait jamais échouer l'action de l'utilisateur :
  // il est signalé en console (console.warn) et la fonction renvoie false. Fichier du journal abîmé
  // (ErreurFichierAbime, T200) : en plus, événement « fichierAbime » (detail : { table }), une seule fois par
  // table jusqu'au prochain initialiser() ; l'application en fait un bandeau.
  async function ecrireJournal(entrees) {
    if (entrees.length === 0) { return true; }
    try {
      await ajouter('journal', entrees);
      return true;
    } catch (erreur) {
      console.warn('Prévo : le journal n\'a pas pu être écrit (' + (erreur && erreur.message) + ').', erreur);
      if (erreur instanceof ErreurFichierAbime) { signalerFichierAbime(erreur.table || 'journal'); }
      return false;
    }
  }

  function signalerFichierAbime(nomTable) {
    if (tablesDitesAbimees.has(nomTable)) { return; }
    tablesDitesAbimees.add(nomTable);
    evenements.dispatchEvent(new CustomEvent('fichierAbime', { detail: { table: nomTable } }));
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
    return I18n.t('socle.message_conflit_persistant.fichier_modifie_meme_temps', { nomTable });
  }

  // Chemin d'écriture d'une table entière (modifier et passage au format courant) : en lecture seule,
  // ErreurLectureSeule ; sinon les lignes sont sérialisées (§3.1) et enregistrées si le stockage a encore la
  // version lue (`entree.version`), puis le cache est mis à jour. Version périmée : ErreurConflit, rien n'est écrit.
  async function enregistrerLignes(nomTable, description, entree, nouvelles, reglagesEcriture) {
    verifierEcriturePermise();
    if (entree.abime && !(reglagesEcriture && reglagesEcriture.remplacerFichierAbime)) {
      throw new ErreurFichierAbime(nomTable, description.fichier);
    }
    const octets = serialiser(nomTable, nouvelles, entree.colonnesInconnues);
    // T200 : l'adaptateur refuse aussi de remplacer un fichier abîmé (ErreurFichierAbime), sauf dérogation demandée.
    const reponse = reglagesEcriture && reglagesEcriture.remplacerFichierAbime
      ? await adaptateurActif.enregistrer(nomTable, octets, entree.version, { remplacerFichierAbime: true })
      : await adaptateurActif.enregistrer(nomTable, octets, entree.version);
    const nouvelIndex = indexer(description, nouvelles);
    cache.set(nomTable, {
      lignes: nouvelles,
      colonnesInconnues: entree.colonnesInconnues,
      entete: enteteEcrit(description, entree.colonnesInconnues),
      abime: false,
      version: reponse && reponse.version !== undefined ? reponse.version : null,
      index: nouvelIndex,
      problemesLecture: problemesApresReecriture(entree.problemesLecture, nouvelIndex, entree.colonnesInconnues),
      perime: false,
      absente: false,
    });
    aRecalculer();
  }

  // Modifie une table : fonction(lignes, outils) reçoit une COPIE des lignes, ajoute ou modifie
  // des objets et renvoie une valeur (renvoyée par modifier). outils : { nouvelId(lignes?, dateIso?),
  // maintenant(), aujourdhui() }. ErreurValidation levée par la fonction : jamais réessayée.
  // Conflit d'écriture : la table est relue et la fonction réappliquée (3 essais au total).
  // options : { action: texte ajouté au journal, journal: false pour ne pas journaliser, remplacerFichierAbime: vrai
  // pour remplacer un fichier abîmé (import ZIP seulement ; sinon ErreurFichierAbime, rien n'est écrit) }.
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
        try {
          await enregistrerLignes(nomTable, description, entree, nouvelles,
            { remplacerFichierAbime: reglages.remplacerFichierAbime === true });
        } catch (erreur) {
          if (!(erreur instanceof ErreurConflit)) { throw erreur; }
          statistiques.conflits += 1;
          if (essai === NOMBRE_ESSAIS) {
            throw new ErreurConflit(messageConflitPersistant(nomTable), erreur.versionActuelle);
          }
          entree = await rechargerSansAttente(nomTable);
          continue;
        }
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
    verifierEcriturePermise();
    const colonnesInconnues = entreeDe(nomTable).colonnesInconnues;
    const propres = lignesAAjouter.map((ligne) => ligneNormalisee(description, colonnesInconnues, ligne));
    const octets = serialiser(nomTable, propres, colonnesInconnues, { bom: false });
    let reponse;
    try {
      reponse = await adaptateurActif.ajouter(nomTable, octets);
    } catch (erreur) {
      // Fichier abîmé (T200 : il finit par un guillemet ouvert, nos lignes seraient avalées) : l'erreur remonte telle
      // quelle, jamais de repli sur modifier (il réécrirait le fichier). Seul un conflit se replie.
      if (erreur instanceof ErreurFichierAbime || !(erreur instanceof ErreurConflit)) { throw erreur; }
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
    // Fichier absent ou vide : le stockage l'a créé avec notre en-tête (sinon l'en-tête est resté le même).
    const description = descriptionTable(nomTable);
    const entete = entree.entete.length ? entree.entete : enteteEcrit(description, entree.colonnesInconnues);
    cache.set(nomTable, Object.assign({}, entree, {
      entete: entete,
      lignes: lignesCompletees,
      index: indexer(description, lignesCompletees),
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

  // --- 4.11 Format des fichiers : passage au format courant, lecture seule ----------------------
  // ARCHITECTURE.md §5.6, §14.1 et §20.2 ; chantier « socle de données » (T186, décisions D167 à D169).
  // Le format d'une base est parametres.version_schema (absent ou illisible : 1) ; celui de chaque fichier se
  // reconnaît à son en-tête (Formats.formatDuFichier, js/formats.js ; 0 si l'en-tête est illisible). Le POINT DE
  // DÉPART d'un passage est le plus petit format trouvé (version_schema et chaque fichier présent et lisible) :
  // une base dont un fichier est resté à un format plus ancien (copie partielle de fichiers) est ainsi complétée.
  //   - mode dossier et démo : le navigateur fait le passage (migrerAuFormatCourant), au démarrage, après
  //     chargerTout() et avant toute autre écriture (passerAuFormatCourant dans js/app.js) ;
  //   - mode serveur : le navigateur ne fait plus de passage (D168), le serveur le fait à son démarrage ;
  //   - version_schema plus grand que Schema.version (données d'une version plus récente de Prévo, D169) :
  //     lecture seule, toute écriture lève ErreurLectureSeule, l'application reste consultable.
  // Décision de Nicolas (2026-10-20), inchangée : JUSTE AVANT le passage, Prévo fait une sauvegarde automatique
  // « AAAA-MM-JJ_HHMMSS_avant-format-vN » (N = format courant), restaurable depuis Paramètres ; sans elle, rien.

  const CLE_VERSION_SCHEMA = 'version_schema';
  const VERSION_SCHEMA_PAR_DEFAUT = 1;       // clé absente ou illisible : fichiers du lot 1 (format 1)
  const ECRITURES_ADAPTATEUR = ['enregistrer', 'ajouter', 'ecrireDocument', 'sauvegarder', 'restaurer',
    'sauvegarderAvantMiseAJour'];
  const adaptateursProteges = new WeakSet();

  // Version du format lue dans une valeur de parametres.csv (absente ou illisible → 1).
  function versionSchemaDe(valeur) {
    const lue = nombre(valeur);
    return lue === null ? VERSION_SCHEMA_PAR_DEFAUT : lue;
  }

  // Note le format de la base (parametres en cache) : plus récent que Schema.version → lecture seule jusqu'au
  // prochain initialiser() ; la première fois, événement « lectureSeule » (detail : { format }).
  function noterFormatDeLaBase() {
    if (formatPlusRecent !== null) { return; }
    const format = versionSchemaDe(parametre(CLE_VERSION_SCHEMA, ''));
    if (!(format > Schema.version)) { return; }
    formatPlusRecent = format;
    evenements.dispatchEvent(new CustomEvent('lectureSeule', { detail: { format: format } }));
  }

  // Vrai si les données sont ouvertes en lecture seule (format plus récent que celui de cette version de Prévo).
  function lectureSeule() {
    return formatPlusRecent !== null;
  }

  function verifierEcriturePermise() {
    if (formatPlusRecent !== null) { throw new ErreurLectureSeule(formatPlusRecent); }
  }

  // Adaptateur dont les écritures (enregistrer, ajouter, ecrireDocument, sauvegarder, restaurer) sont refusées en
  // lecture seule (promesse rejetée : ErreurLectureSeule). C'est une vue (Proxy) de l'adaptateur : tout le reste
  // (lectures, info, verrou…) est le sien, et une méthode remplacée sur l'un se voit sur l'autre. Un adaptateur
  // déjà protégé est rendu tel quel.
  function protegerEcritures(adaptateur) {
    if (!adaptateur || adaptateursProteges.has(adaptateur)) { return adaptateur; }
    const protege = new Proxy(adaptateur, {
      get(cible, nom) {
        const valeur = cible[nom];
        if (typeof valeur !== 'function' || !ECRITURES_ADAPTATEUR.includes(nom)) { return valeur; }
        return function () {
          if (formatPlusRecent !== null) { return Promise.reject(new ErreurLectureSeule(formatPlusRecent)); }
          return valeur.apply(cible, arguments);
        };
      },
    });
    adaptateursProteges.add(protege);
    return protege;
  }

  function exigerFormats() {
    if (typeof Formats === 'undefined') {
      throw new Error(I18n.t('socle.exiger_formats.donnees_registre_formats_js'));
    }
  }

  // Pourquoi un passage au format courant ne réécrirait pas une table présente, ou null (fichier à réécrire, ou rien
  // à faire) : 'entete' → fichier non vide dont l'en-tête est illisible (format 0 : des colonnes du format 1 y
  // manquent) ; 'contenu' → fichier d'un format plus ancien qui ne se relit pas sans perte (entree.abime : structure
  // abîmée, ou valeurs au-delà de l'en-tête), que la réécriture ferait perdre (CS140 : aucune perte silencieuse).
  function raisonDeLaisser(nomTable, entree) {
    if (!entree || entree.absente) { return null; }
    const format = Formats.formatDuFichier(nomTable, entree.entete);
    if (format === 0) { return entree.entete.length > 0 ? 'entete' : null; }      // fichier vide : rien à perdre
    return entree.abime && format < Schema.version ? 'contenu' : null;
  }

  // Tables chargées dont le fichier est abîmé (entree.abime), dans l'ordre du schéma : jamais réécrites par
  // modifier (ErreurFichierAbime), quel que soit leur format (T197).
  function tablesAbimees() {
    return Schema.nomsTables().filter((nomTable) => { const entree = cache.get(nomTable); return !!(entree && entree.abime); });
  }

  // État du format de la base chargée, sans rien écrire : { base, courant, depart, plusRecent, aCompleter, abimees }
  //   - base       : format de la base (version_schema ; absent ou illisible : 1) ; courant : Schema.version ;
  //   - depart     : le plus petit format trouvé (base et fichiers présents, lisibles et non abîmés) ;
  //                  depart < courant : un passage est à faire ;
  //   - plusRecent : base > courant (lecture seule) ;
  //   - aCompleter : tables présentes dont le fichier est à un format plus ancien que le courant ;
  //   - abimees    : tables qu'un passage laisse telles quelles (raisonDeLaisser) : jamais réécrites, elles ne
  //                  comptent pas pour le point de départ (un fichier vide non plus).
  function etatDuFormat() {
    verifierInitialise();
    exigerFormats();
    const courant = Schema.version;
    const base = versionSchemaDe(parametre(CLE_VERSION_SCHEMA, ''));
    const etat = { base: base, courant: courant, depart: base, plusRecent: base > courant, aCompleter: [], abimees: [] };
    for (const nomTable of Schema.nomsTables()) {
      const entree = cache.get(nomTable);
      if (!entree || entree.absente) { continue; }
      if (raisonDeLaisser(nomTable, entree)) { etat.abimees.push(nomTable); continue; }
      const format = Formats.formatDuFichier(nomTable, entree.entete);
      if (format === 0) { continue; }                                       // fichier vide
      if (format < courant) { etat.aCompleter.push(nomTable); }
      etat.depart = Math.min(etat.depart, format);
    }
    return etat;
  }

  // Problème signalé pour une table laissée telle quelle par le passage au format courant (montré par problemes()
  // tant que la raison demeure ; le détail de ce qui est abîmé est dans les problèmes de lecture de la table).
  function problemeTableLaissee(nomTable) {
    const description = descriptionTable(nomTable);
    const raison = raisonDeLaisser(nomTable, entreeDe(nomTable)) === 'entete'
      ? I18n.t('socle.probleme_table_laissee.ligne_tete_incomplete_illisible', { fichier: description.fichier })
      : I18n.t('socle.probleme_table_laissee.abime_structure_fichier_valeurs', { fichier: description.fichier });
    return probleme('erreur', 'colonne', nomTable, 1, null, null, null,
      I18n.t('socle.probleme_table_laissee.prevo_reecrit_pas_fichier', { descriptionLibelle: description.libelle, raison, version: Schema.version }));
  }

  function problemesFormatActuels() {
    return problemesFormat.filter((laissee) => raisonDeLaisser(laissee.table, entreeDe(laissee.table)) !== null);
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
      throw new Error(I18n.t('socle.sauvegarder_avant_format.mode_stockage_sait_pas'));
    }
    const nom = await adaptateurActif.sauvegarder('avant-format-v' + versionCible);
    if (!nom) { throw new Error(I18n.t('socle.sauvegarder_avant_format.stockage_pas_confirme_sauvegarde')); }
    return nom;
  }

  // Message d'une erreur sans point final (pour l'insérer au milieu d'une phrase).
  function messageSansPointFinal(erreur) {
    return String((erreur && erreur.message) || I18n.t('commun.message.erreur_inconnue')).replace(/[\s.]+$/, '');
  }

  // Étapes du passage depuis `depart`, calculées en mémoire par Formats.migrer sur les en-têtes des tables données
  // (aucune ligne n'est copiée) : [{ vers, passage, tables }] dans l'ordre, où passage est la ligne de journal de
  // Formats (« passage au format N du fichier ») et tables les tables données que l'étape complète. Une table
  // absente que l'étape crée n'est pas comptée : elle reste absente (lue vide) jusqu'à sa première écriture
  // (reserves_controle : écrite par la reprise s'il y a des réserves à reprendre, phase 3 bis de migrerAuFormatCourant).
  function etapesDuPassage(depart, nomsTables) {
    let base = { tables: {} };
    for (const nomTable of nomsTables) { base.tables[nomTable] = { entete: entreeDe(nomTable).entete.slice(), lignes: [] }; }
    const etapes = [];
    for (const etape of Formats.ETAPES) {
      if (etape.vers <= depart || etape.vers > Schema.version) { continue; }
      const pas = Formats.migrer(base, etape.de, etape.vers);
      etapes.push({
        vers: etape.vers,
        passage: pas.journal[0],
        tables: nomsTables.filter((nomTable) => pas.base.tables[nomTable].entete.length !== base.tables[nomTable].entete.length),
      });
      base = pas.base;
    }
    return etapes;
  }

  // Réécrit une table présente au format courant par le chemin d'écriture habituel (enregistrerLignes : contrôle
  // de version ; conflit → table relue et nouvel essai, 3 essais au total). Décidé sur la table FRAÎCHE : déjà au
  // format courant (un autre poste l'a fait), absente, illisible ou abîmée → rien. Les lignes écrites sont celles que
  // rend Formats.migrer (colonnes ajoutées avec leur valeur par défaut, toutes les autres valeurs gardées).
  // Rend vrai si la table a été écrite.
  async function ecrireAuFormatCourant(nomTable) {
    const description = descriptionTable(nomTable);
    return enSerie(nomTable, async () => {
      let entree = entreeDe(nomTable);
      if (entree.perime) { entree = await rechargerSansAttente(nomTable); }
      for (let essai = 1; essai <= NOMBRE_ESSAIS; essai += 1) {
        const format = entree.absente ? 0 : Formats.formatDuFichier(nomTable, entree.entete);
        if (format === 0 || format >= Schema.version || entree.abime) { return false; }
        const seule = { tables: {} };
        seule.tables[nomTable] = { entete: entree.entete, lignes: entree.lignes };
        const migree = Formats.migrer(seule, format, Schema.version).base.tables[nomTable];
        const nouvelles = migree.lignes.map((ligne) => ligneNormalisee(description, entree.colonnesInconnues, ligne));
        try {
          await enregistrerLignes(nomTable, description, entree, nouvelles);
          return true;
        } catch (erreur) {
          if (!(erreur instanceof ErreurConflit)) { throw erreur; }
          statistiques.conflits += 1;
          if (essai === NOMBRE_ESSAIS) {
            throw new ErreurConflit(messageConflitPersistant(nomTable), erreur.versionActuelle);
          }
          entree = await rechargerSansAttente(nomTable);
        }
      }
      return false;
    });
  }

  // Reprise des observations des contrôles en réserves (D183 ; note de conception du format 4, §3.3 à §3.5) : la
  // table que l'étape qui crée reserves_controle remplit, au lieu de la laisser absente jusqu'à sa première écriture.
  const TABLE_DES_RESERVES = 'reserves_controle';
  const TABLE_DES_CONTROLES = 'controles_reglementaires';

  // Vrai si le fichier d'une table se relit sans perte pour la reprise : présent, non abîmé, en-tête lisible
  // (format reconnu ; un fichier vide se lit sans ligne).
  function relisiblePourReprise(nomTable, entree) {
    return !entree.absente && !entree.abime
      && (entree.entete.length === 0 || Formats.formatDuFichier(nomTable, entree.entete) > 0);
  }

  // Phase « 3 bis » du passage : réserves tirées des observations (Formats.reservesReprises), écrites dans
  // reserves_controle par le chemin habituel (enregistrerLignes : contrôle de version ; conflit → table relue et
  // réserves recalculées, 3 essais au total ; un autre poste les a peut-être déjà reprises). Décidée sur les tables
  // FRAÎCHES : controles_reglementaires absente, abîmée ou à l'en-tête illisible, ou reserves_controle abîmée ou à
  // l'en-tête illisible → rien ; absente → créée s'il y a au moins une réserve à reprendre. Les lignes existantes de
  // reserves_controle sont gardées, les reprises ajoutées après elles. Idempotente : un contrôle qui a déjà une
  // réserve ne reçoit rien. Rend vrai si reserves_controle a été écrite.
  async function reprendreObservationsEnReserves() {
    const description = descriptionTable(TABLE_DES_RESERVES);
    return enSerie(TABLE_DES_RESERVES, async () => {
      let controles = entreeDe(TABLE_DES_CONTROLES);
      if (controles.perime) { controles = await rechargerSansAttente(TABLE_DES_CONTROLES); }
      if (!relisiblePourReprise(TABLE_DES_CONTROLES, controles)) { return false; }
      let entree = entreeDe(TABLE_DES_RESERVES);
      if (entree.perime) { entree = await rechargerSansAttente(TABLE_DES_RESERVES); }
      for (let essai = 1; essai <= NOMBRE_ESSAIS; essai += 1) {
        if (!entree.absente && !relisiblePourReprise(TABLE_DES_RESERVES, entree)) { return false; }
        const reprises = Formats.reservesReprises(controles.lignes, entree.lignes);
        if (reprises.length === 0) { return false; }
        const nouvelles = entree.lignes.concat(reprises)
          .map((ligne) => ligneNormalisee(description, entree.colonnesInconnues, ligne));
        try {
          await enregistrerLignes(TABLE_DES_RESERVES, description, entree, nouvelles);
          return true;
        } catch (erreur) {
          if (!(erreur instanceof ErreurConflit)) { throw erreur; }
          statistiques.conflits += 1;
          if (essai === NOMBRE_ESSAIS) {
            throw new ErreurConflit(messageConflitPersistant(TABLE_DES_RESERVES), erreur.versionActuelle);
          }
          entree = await rechargerSansAttente(TABLE_DES_RESERVES);
        }
      }
      return false;
    });
  }

  // Passage au format courant (mode dossier et démo, D168). Sans effet (rien n'est écrit) en mode serveur, en
  // lecture seule, sur une base vide ou déjà au format courant ; idempotent : un second appel n'écrit rien.
  //   0. parametres.csv abîmé (sauf démo) : ErreurFichierAbime et RIEN n'est écrit, pas même la sauvegarde (T204) ;
  //   1. la sauvegarde « avant-format-vN » (sauf démo) : impossible → ErreurStockage et RIEN n'est écrit (nouvel
  //      essai à la prochaine ouverture) ;
  //   2. Formats.migrer, étape par étape, sur les tables présentes et lisibles ;
  //   3. chaque table que le passage change (sauf parametres) est réécrite par le chemin habituel ; une table à
  //      l'en-tête illisible (format 0), ou abîmée au point qu'une réécriture en perdrait une partie, n'est JAMAIS
  //      réécrite : signalée (problemes()) et laissée telle quelle ;
  //   3 bis. si le passage comprend l'étape qui crée reserves_controle (3→4) : les observations des contrôles sans
  //      réserve y sont reprises (reprendreObservationsEnReserves) ; la table, créée ou complétée, compte parmi les
  //      tables de cette étape (journal, résultat). Avant 4 : version_schema au format 4 ⇒ reprise faite ;
  //   4. parametres.version_schema, décidé sur les lignes FRAÎCHES (rien si un autre poste l'a déjà mis) ;
  //   5. une ligne de journal par étape (table parametres, ligne version_schema) : « passage au format N du
  //      fichier ; sauvegarde … faite juste avant » (texte relu par la suggestion S4) ; pour une étape qui ne fait
  //      que compléter des fichiers d'une base déjà à ce format, « fichiers complétés au format N : <tables> ;
  //      sauvegarde … faite juste avant ». En démo : « … ; sans sauvegarde (démo) ».
  // Renvoie { misAJour, sauvegarde, depart, tables, abimees } : misAJour vrai si CET appel a écrit (une table ou
  // version_schema) ; sauvegarde : nom de la sauvegarde faite juste avant, ou null (aucune, ou démo) ; depart : le
  // point de départ ; tables : tables réécrites (hors parametres) ; abimees : tables laissées telles quelles.
  // Deux postes ouverts en même temps sur une base ancienne peuvent faire chacun leur sauvegarde (sans gravité) ;
  // le second, en conflit, relit chaque table et ne réécrit rien de ce que le premier a déjà fait.
  async function migrerAuFormatCourant() {
    verifierInitialise();
    exigerFormats();
    const courant = Schema.version;
    if (!cache.has('parametres')) { await rechargerTable('parametres'); }
    const etat = etatDuFormat();
    const resultat = { misAJour: false, sauvegarde: null, depart: etat.depart, tables: [], abimees: [] };
    if (lectureSeule() || adaptateurActif.mode === 'serveur' || baseVide() || etat.depart >= courant) {
      return resultat;
    }
    resultat.abimees = etat.abimees;
    problemesFormat = etat.abimees.map(problemeTableLaissee);
    aRecalculer();

    // T204 (comme le correctif 1.2.1 et le serveur) : parametres.csv abîmé, version_schema ne pourra pas être écrite ;
    // le passage est refusé AVANT la sauvegarde : rien n'est écrit, aucune sauvegarde refaite à chaque ouverture.
    // L'application s'ouvre quand même, avec le bandeau « Fichier abîmé » (js/app.js). Démo : tout reste en mémoire.
    if (entreeDe('parametres').abime && sauvegardeExigee()) {
      throw new ErreurFichierAbime('parametres', descriptionTable('parametres').fichier);
    }

    // 1. La sauvegarde d'abord : sans elle, on ne touche à rien.
    if (sauvegardeExigee()) {
      try {
        resultat.sauvegarde = await sauvegarderAvantFormat(courant);
      } catch (erreur) {
        throw new ErreurStockage(I18n.t('socle.migrer_au_format_courant.sauvegarde_avant_passage_format', { courant, messageSansPointFinal: messageSansPointFinal(erreur) }), erreur);
      }
    }

    // 2 et 3. Les étapes, puis les tables qu'elles changent, dans l'ordre du schéma.
    const lisibles = Schema.nomsTables().filter((nomTable) => !entreeDe(nomTable).absente
      && !etat.abimees.includes(nomTable));
    const etapes = etapesDuPassage(etat.depart, lisibles);
    for (const nomTable of lisibles) {
      if (nomTable === 'parametres' || !etapes.some((etape) => etape.tables.includes(nomTable))) { continue; }
      if (await ecrireAuFormatCourant(nomTable)) { resultat.tables.push(nomTable); }
    }

    // 3 bis. La reprise des observations en réserves (D183), après les tables complétées et avant version_schema.
    const etapeDesReserves = etapes.find((etape) => etape.vers === descriptionTable(TABLE_DES_RESERVES).depuisVersion);
    if (etapeDesReserves && await reprendreObservationsEnReserves()) {
      if (!etapeDesReserves.tables.includes(TABLE_DES_RESERVES)) { etapeDesReserves.tables.push(TABLE_DES_RESERVES); }
      resultat.tables.push(TABLE_DES_RESERVES);
    }

    // 4. Puis version_schema, décidée sur les lignes FRAÎCHES (modifier relit la table en cas de conflit et
    // réapplique la fonction) : rien n'est écrit si un autre poste l'a déjà fait.
    let versionTrouvee = etat.base;
    const versionEcrite = await modifier('parametres', (lignesParametres) => {
      const ligne = lignesParametres.find((l) => l.cle === CLE_VERSION_SCHEMA);
      versionTrouvee = versionSchemaDe(ligne ? ligne.valeur : '');
      if (versionTrouvee >= courant) { return false; }
      if (ligne) {
        ligne.valeur = String(courant);
      } else {
        lignesParametres.push({ cle: CLE_VERSION_SCHEMA, valeur: String(courant) });
      }
      return true;
    }, { journal: false });

    // 5. Le journal : une ligne par étape (texte dans la langue de l'installation, D156).
    const suite = resultat.sauvegarde ? I18n.donnees('socle.migrer_au_format_courant.sauvegarde_faite_juste_avant', { sauvegarde: resultat.sauvegarde }) : I18n.donnees('socle.migrer_au_format_courant.sans_sauvegarde_demo');
    const identifiantsPris = new Set();
    const entrees = [];
    for (const etape of etapes) {
      let action = null;
      if (versionEcrite && etape.vers > versionTrouvee) {
        action = etape.passage;
      } else {
        const completees = etape.tables.filter((nomTable) => resultat.tables.includes(nomTable));
        if (completees.length) { action = 'fichiers complétés au format ' + etape.vers + ' : ' + completees.join(', '); }
      }
      if (action) { entrees.push(entreeJournal(identifiantsPris, 'parametres', CLE_VERSION_SCHEMA, action + ' ; ' + suite)); }
    }
    await ecrireJournal(entrees);
    resultat.misAJour = versionEcrite === true || resultat.tables.length > 0;
    if (resultat.tables.length) { signaler(resultat.tables.slice(), 'local'); }
    return resultat;
  }

  return {
    // 1. Erreurs
    ErreurConflit: ErreurConflit,
    ErreurValidation: ErreurValidation,
    ErreurStockage: ErreurStockage,
    ErreurLectureSeule: ErreurLectureSeule,
    ErreurFichierAbime: ErreurFichierAbime,
    tablesAbimees: tablesAbimees,
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
    // 4.11 Format des fichiers : passage au format courant, lecture seule
    etatDuFormat: etatDuFormat,
    migrerAuFormatCourant: migrerAuFormatCourant,
    mettreAJourVersionSchema: migrerAuFormatCourant,      // ancien nom (lot 2), même fonction
    lectureSeule: lectureSeule,
    protegerEcritures: protegerEcritures,
    evenements: evenements,
    statistiques: statistiques,
  };
})();
