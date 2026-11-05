'use strict';
// Import (3/7) — lecture des fichiers et du collage (lot 5, ARCHITECTURE.md §18.3) : CSV/TSV par
// PapaParse, xlsx/xls/ods par SheetJS (App.chargerSheetJS, à la demande), cellules en texte, plafonds.
// Complète l'objet Import.
//
// API :
//   Import.lire(source) → Promise<{ nom, format, encodage, feuilles: [{ nom, lignes: [[texte]] }] }> ;
//     source = File (ou Blob avec .name) ou { texte, nom } (collage). Toutes les cellules sont du texte :
//     dates des tableurs en « AAAA-MM-JJ » ou « AAAA-MM-JJ HH:MM » (systèmes 1900 et 1904), nombres sans
//     arrondi d'affichage (format « 000 » gardé : repère « 007 »), cases VRAI/FAUX en « 1 »/« 0 ».
//     Erreurs : Import.ErreurImport (trop grand, trop de lignes ou de colonnes, chiffré, vide, illisible).
//   Import.ligneEntete(lignes, type) → rang (0…) de la ligne d'en-tête probable.
//   Import.entetes(lignes, rang, surDeuxLignes) → textes d'en-tête (deux lignes jointes si demandé).
//   Import.PLAFONDS = { octets, lignes, colonnes }.

Object.assign(Import, (() => {

  const PLAFONDS = Object.freeze({ octets: 10 * 1024 * 1024, lignes: 20000, colonnes: 200 });
  const TABLEURS = ['xlsx', 'xlsm', 'xls', 'ods'];
  const TEXTES = ['csv', 'txt', 'tsv'];
  const LIGNES_EXAMINEES_EN_TETE = 20;

  function erreur(message) {
    return new Import.ErreurImport(message);
  }

  function extension(nom) {
    const position = String(nom || '').lastIndexOf('.');
    return position >= 0 ? String(nom).slice(position + 1).toLowerCase() : '';
  }

  // Signatures : ZIP (xlsx, ods), conteneur OLE (xls, ou xlsx chiffré par Excel).
  function estZip(octets) {
    return octets.length >= 4 && octets[0] === 0x50 && octets[1] === 0x4B && octets[2] === 0x03 && octets[3] === 0x04;
  }
  function estOle(octets) {
    const signature = [0xD0, 0xCF, 0x11, 0xE0, 0xA1, 0xB1, 0x1A, 0xE1];
    return octets.length >= 8 && signature.every((octet, rang) => octets[rang] === octet);
  }

  // Un conteneur OLE qui porte le flux « EncryptionInfo » est un classeur chiffré par mot de passe.
  function estChiffre(octets) {
    if (!estOle(octets)) return false;
    const nom = 'EncryptionInfo';
    const limite = Math.min(octets.length, 1024 * 1024);
    for (let position = 0; position + nom.length * 2 <= limite; position += 1) {
      let egal = true;
      for (let rang = 0; rang < nom.length; rang += 1) {
        if (octets[position + rang * 2] !== nom.charCodeAt(rang) || octets[position + rang * 2 + 1] !== 0) { egal = false; break; }
      }
      if (egal) return true;
    }
    return false;
  }

  // Message d'un classeur chiffré (lu à l'affichage).
  const messageChiffre = () => I18n.t('import.lecture.chiffre');

  /** Contrôle commun des plafonds et du contenu ; supprime les lignes et colonnes vides en fin de feuille. */
  function nettoyer(feuilles) {
    const gardees = feuilles.map((feuille) => {
      const lignes = Array.from(feuille.lignes, (ligne) => Array.from(ligne || [], (cellule) => (cellule === null || cellule === undefined ? '' : String(cellule))));
      while (lignes.length && lignes[lignes.length - 1].every((cellule) => cellule.trim() === '')) lignes.pop();
      let largeur = 0;
      lignes.forEach((ligne) => {
        for (let colonne = ligne.length - 1; colonne >= 0; colonne -= 1) {
          if (ligne[colonne].trim() !== '') { largeur = Math.max(largeur, colonne + 1); break; }
        }
      });
      if (lignes.length > PLAFONDS.lignes + 1) {
        throw erreur(I18n.t('import.lecture.trop_long_feuille', { feuille: feuille.nom, n: PLAFONDS.lignes, lignes: UI.nombreFr(PLAFONDS.lignes) }));
      }
      if (largeur > PLAFONDS.colonnes) {
        throw erreur(I18n.t('import.lecture.trop_colonnes', { feuille: feuille.nom, colonnes: PLAFONDS.colonnes }));
      }
      return { nom: feuille.nom, lignes: lignes.map((ligne) => {
        const complete = ligne.slice(0, largeur);
        while (complete.length < largeur) complete.push('');
        return complete;
      }) };
    }).filter((feuille) => feuille.lignes.some((ligne) => ligne.some((cellule) => cellule.trim() !== '')));
    if (!gardees.length) throw erreur(I18n.t('import.lecture.aucune_donnee'));
    return gardees;
  }

  // --- Texte : CSV, TSV, collage ---------------------------------------------------------------

  function compterHorsGuillemets(ligne, separateur) {
    let compte = 0;
    let dansGuillemets = false;
    for (const caractere of ligne) {
      if (caractere === '"') dansGuillemets = !dansGuillemets;
      else if (caractere === separateur && !dansGuillemets) compte += 1;
    }
    return compte;
  }

  /**
   * Séparateur le plus régulier sur les 30 premières lignes non vides : pour chacun (tabulation, « ; »,
   * « , »), le nombre d'occurrences le plus fréquent (hors guillemets, hors zéro) et le nombre de lignes
   * qui l'ont ; la régularité l'emporte, puis le nombre de colonnes. « ; » par défaut (format de Prévo).
   */
  function separateurProbable(texte) {
    const lignes = texte.split(/\r\n|\n|\r/).filter((ligne) => ligne.trim() !== '').slice(0, 30);
    let meilleur = ';';
    let meilleurScore = [0, 0];
    ['\t', ';', ','].forEach((separateur) => {
      const frequences = new Map();
      lignes.forEach((ligne) => {
        const compte = compterHorsGuillemets(ligne, separateur);
        if (compte) frequences.set(compte, (frequences.get(compte) || 0) + 1);
      });
      frequences.forEach((lignesConcernees, compte) => {
        if (lignesConcernees > meilleurScore[0] || (lignesConcernees === meilleurScore[0] && compte > meilleurScore[1])) {
          meilleurScore = [lignesConcernees, compte];
          meilleur = separateur;
        }
      });
    });
    return meilleur;
  }

  function lireTexte(texte, nom, format, encodage) {
    const resultat = Papa.parse(texte, {
      delimiter: separateurProbable(texte), quoteChar: '"', skipEmptyLines: false,
    });
    const lignes = resultat.data.filter((ligne, rang, toutes) => !(rang === toutes.length - 1 && ligne.length === 1 && ligne[0] === ''));
    if (lignes.length > PLAFONDS.lignes + 50) {
      throw erreur(I18n.t('import.lecture.trop_long', { n: PLAFONDS.lignes, lignes: UI.nombreFr(PLAFONDS.lignes) }));
    }
    return { nom, format, encodage, feuilles: nettoyer([{ nom: nom, lignes }]) };
  }

  // --- Tableurs : xlsx, xls, ods par SheetJS ------------------------------------------------------

  function deuxChiffres(nombre) {
    return (nombre < 10 ? '0' : '') + nombre;
  }

  /** Texte d'une cellule SheetJS : dates par le numéro de série (aucun fuseau horaire), nombres bruts. */
  function texteCellule(cellule, date1904, bibliotheque) {
    if (!cellule || cellule.v === undefined || cellule.v === null) return '';
    if (cellule.t === 'b') return cellule.v ? '1' : '0';
    if (cellule.t === 'e') return '';
    if (cellule.t === 'n') {
      const format = cellule.z ? String(cellule.z) : '';
      if (format && bibliotheque.SSF.is_date(format)) {
        const partie = bibliotheque.SSF.parse_date_code(cellule.v, { date1904 });
        if (partie) {
          const jour = partie.y + '-' + deuxChiffres(partie.m) + '-' + deuxChiffres(partie.d);
          return partie.H || partie.M ? jour + ' ' + deuxChiffres(partie.H) + ':' + deuxChiffres(partie.M) : jour;
        }
      }
      if (/^0+$/.test(format) && cellule.w) return String(cellule.w);         // « 007 » : zéros en tête voulus
      return String(cellule.v);
    }
    if (cellule.t === 'd' && cellule.v instanceof Date) {
      const d = cellule.v;
      return d.getFullYear() + '-' + deuxChiffres(d.getMonth() + 1) + '-' + deuxChiffres(d.getDate());
    }
    return String(cellule.v);
  }

  // Un .ods décrit ses cellules et lignes répétées par un compte (« number-columns-repeated ») : quelques
  // octets peuvent valoir un million de cellules, que SheetJS déplierait (et dont il ne dirait rien dans la
  // plage de la feuille). Les plafonds sont donc contrôlés sur content.xml, AVANT la lecture par SheetJS.
  const MOTIF_ODS = /<table:table-row\b([^>]*?)(\/?)>|<\/table:table-row>|<table:(?:covered-)?table-cell\b([^>]*?)\/?>|<table:table((?:\s[^>]*)?)>/g;

  function attribut(attributs, nom) {
    const trouve = new RegExp('\\s' + nom + '="([^"]*)"').exec(attributs || '');
    return trouve ? trouve[1] : null;
  }

  function controlerOds(octets, bibliotheque) {
    let entree = null;
    try {
      const archive = bibliotheque.CFB.read(octets, { type: 'array' });
      const type = bibliotheque.CFB.find(archive, 'mimetype');
      if (!type || !/opendocument\.spreadsheet/.test(new TextDecoder('utf-8').decode(type.content))) return;
      entree = bibliotheque.CFB.find(archive, 'content.xml');
    } catch (cause) {
      return;                                              // pas un .ods lisible : SheetJS dira pourquoi
    }
    if (!entree || !entree.content) return;
    const xml = new TextDecoder('utf-8').decode(entree.content);
    let feuille = '';
    let colonne = 0;
    let ligneRemplie = false;
    let repetitionLigne = 1;
    let lignes = 0;
    MOTIF_ODS.lastIndex = 0;
    for (let trouve = MOTIF_ODS.exec(xml); trouve; trouve = MOTIF_ODS.exec(xml)) {
      if (trouve[4] !== undefined) {                       // nouvelle feuille
        feuille = attribut(trouve[4], 'table:name') || '';
        lignes = 0;
      } else if (trouve[1] !== undefined) {                // début de ligne
        colonne = 0;
        ligneRemplie = false;
        repetitionLigne = Number(attribut(trouve[1], 'table:number-rows-repeated')) || 1;
      } else if (trouve[3] !== undefined) {                // cellule
        const fois = Number(attribut(trouve[3], 'table:number-columns-repeated')) || 1;
        if (attribut(trouve[3], 'office:value-type') !== null) {
          ligneRemplie = true;
          if (colonne + fois > PLAFONDS.colonnes) {
            throw erreur(I18n.t('import.lecture.trop_colonnes', { feuille: feuille, colonnes: PLAFONDS.colonnes }));
          }
        }
        colonne += fois;
      }
      if (trouve[0] === '</table:table-row>' || (trouve[1] !== undefined && trouve[2] === '/')) {
        if (ligneRemplie) lignes += repetitionLigne;
        if (lignes > PLAFONDS.lignes + 1) {
          throw erreur(I18n.t('import.lecture.trop_long_feuille', { feuille: feuille, n: PLAFONDS.lignes, lignes: UI.nombreFr(PLAFONDS.lignes) }));
        }
      }
    }
  }

  async function lireTableur(octets, nom, format) {
    if (estChiffre(octets)) throw erreur(messageChiffre());
    const bibliotheque = await App.chargerSheetJS();
    if (estZip(octets)) controlerOds(octets, bibliotheque);
    let classeur;
    try {
      classeur = bibliotheque.read(octets, {
        type: 'array', dense: true, cellNF: true, cellDates: false, cellText: true, sheetRows: PLAFONDS.lignes + 2,
      });
    } catch (cause) {
      if (/password|encrypt|protect/i.test(String(cause && cause.message))) throw erreur(messageChiffre());
      throw erreur(I18n.t('import.lecture.illisible', { raison: cause && cause.message ? cause.message : I18n.t('import.lecture.format_inconnu') }));
    }
    const date1904 = Boolean(classeur.Workbook && classeur.Workbook.WBProps && classeur.Workbook.WBProps.date1904);
    const feuilles = classeur.SheetNames.map((nomFeuille) => {
      const feuille = classeur.Sheets[nomFeuille];
      const donnees = feuille['!data'] || [];
      if (donnees.length > PLAFONDS.lignes + 1) {
        throw erreur(I18n.t('import.lecture.trop_long_feuille', { feuille: nomFeuille, n: PLAFONDS.lignes, lignes: UI.nombreFr(PLAFONDS.lignes) }));
      }
      // Array.from et non map : une ligne de SheetJS peut avoir des trous (cellules absentes), que map garderait.
      const lignes = Array.from(donnees, (ligne) => Array.from(ligne || [], (cellule) => texteCellule(cellule, date1904, bibliotheque)));
      return { nom: nomFeuille, lignes };
    });
    return { nom, format, encodage: null, feuilles: nettoyer(feuilles) };
  }

  /** Lit un fichier ou un collage : voir l'en-tête du fichier. */
  async function lire(source) {
    if (!source) throw erreur(I18n.t('import.lecture.aucun_fichier'));
    if (typeof source.texte === 'string') {
      if (!source.texte.trim()) throw erreur(I18n.t('import.lecture.collage_vide'));
      return lireTexte(source.texte, source.nom || I18n.t('import.lecture.collage'), 'collage', null);
    }
    const nom = source.name || source.nom || I18n.t('import.lire.fichier');
    const format = extension(nom);
    if (typeof source.size === 'number' && source.size > PLAFONDS.octets) {
      throw erreur(I18n.t('import.lecture.trop_grand', { n: PLAFONDS.octets / 1024 / 1024 }));
    }
    const octets = new Uint8Array(await source.arrayBuffer());
    if (octets.length > PLAFONDS.octets) {
      throw erreur(I18n.t('import.lecture.trop_grand', { n: PLAFONDS.octets / 1024 / 1024 }));
    }
    if (!octets.length) throw erreur(I18n.t('import.lecture.fichier_vide'));
    if (TABLEURS.includes(format) || estZip(octets) || estOle(octets)) return lireTableur(octets, nom, format || 'tableur');
    if (TEXTES.includes(format) || format === '') {
      const decode = Donnees.csv.decoder(octets);
      return lireTexte(decode.texte, nom, format || 'csv', decode.encodage);
    }
    throw erreur(I18n.t('import.lecture.format_non_reconnu', { format }));
  }

  // --- Ligne d'en-tête ------------------------------------------------------------------------

  function estNumerique(texte) {
    return /^[-+]?[\d\s.,]+$/.test(texte) || /^\d{4}-\d{2}-\d{2}/.test(texte) || /^\d{1,2}\/\d{1,2}\/\d{2,4}/.test(texte);
  }

  /** Noms reconnus d'un type (clé, libellé, synonymes de ses champs), en forme comparable. */
  function nomsDuType(type) {
    const definition = type && Import.TYPES ? Import.TYPES[type] : null;
    const noms = new Set();
    if (!definition || typeof Import.comparable !== 'function') return noms;
    (definition.champs || []).forEach((champ) => {
      [champ.cle, champ.libelle].concat(champ.synonymes || []).forEach((nom) => { if (nom) noms.add(Import.comparable(nom)); });
    });
    return noms;
  }

  /**
   * Ligne d'en-tête probable parmi les 20 premières : celle qui reconnaît le plus de noms du type, puis
   * celle qui a le plus de cellules de texte non numériques (au moins deux) ; les lignes de titre au-dessus
   * (une seule cellule remplie) ne gagnent jamais. 0 par défaut.
   */
  function ligneEntete(lignes, type) {
    const noms = nomsDuType(type);
    let meilleure = 0;
    let meilleurScore = [-1, -1];
    (lignes || []).slice(0, LIGNES_EXAMINEES_EN_TETE).forEach((ligne, rang) => {
      const remplies = ligne.map((cellule) => String(cellule).trim()).filter(Boolean);
      const textes = remplies.filter((cellule) => !estNumerique(cellule));
      if (textes.length < 2 || textes.length < remplies.length / 2) return;
      const reconnus = noms.size ? textes.filter((cellule) => noms.has(Import.comparable(cellule))).length : 0;
      const score = [reconnus, textes.length];
      if (score[0] > meilleurScore[0] || (score[0] === meilleurScore[0] && score[1] > meilleurScore[1])) {
        meilleurScore = score;
        meilleure = rang;
      }
    });
    return meilleure;
  }

  /** En-têtes à partir de la ligne `rang` ; avec surDeuxLignes, chaque titre est joint à celui de la ligne suivante. */
  function entetes(lignes, rang, surDeuxLignes) {
    const premiere = (lignes && lignes[rang]) || [];
    const seconde = surDeuxLignes ? (lignes[rang + 1] || []) : [];
    const largeur = Math.max(premiere.length, seconde.length);
    const resultat = [];
    let precedent = '';
    for (let colonne = 0; colonne < largeur; colonne += 1) {
      let haut = String(premiere[colonne] || '').trim();
      // Cellule fusionnée sur plusieurs colonnes : le titre du haut vaut pour les colonnes suivantes.
      if (surDeuxLignes && !haut) haut = precedent; else precedent = haut;
      const bas = String(seconde[colonne] || '').trim();
      resultat.push([haut, bas].filter(Boolean).join(' '));
    }
    return resultat;
  }

  return { PLAFONDS, lire, ligneEntete, entetes };
})());
