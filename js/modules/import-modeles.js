'use strict';
// Import (5/7) — modèles à remplir (lot 5, ARCHITECTURE.md §18.8) : un fichier .xlsx ou .csv par type
// de données, écrit d'après Import.TYPES (titres en libellés, une ligne d'exemple valable sur la démo).
// Complète l'objet Import.
//
// API :
//   Import.modele(type, format) → Promise<Blob> ; format 'xlsx' (SheetJS chargé à la demande : feuille
//     « Données » avec les titres et la ligne d'exemple, feuille « Aide » : champs obligatoires, valeurs
//     permises, formats, autres titres reconnus) ou 'csv' (format de Prévo : BOM, « ; », CRLF).
//   Import.nomModele(type, format) → nom du fichier proposé (« prevo-modele-equipements.xlsx »).
//   Import.aideModele(type) → lignes de la feuille « Aide » (texte), aussi utiles à l'écran.

Object.assign(Import, (() => {

  const FORMATS = Object.freeze({
    date: 'date JJ/MM/AAAA (ou AAAA-MM-JJ)',
    date_heure: 'date et heure JJ/MM/AAAA HH:MM',
    decimal: 'nombre (virgule ou point)',
    entier: 'nombre entier',
    booleen: 'oui ou non',
    choix: 'une des valeurs permises',
  });
  const TYPE_MIME = Object.freeze({
    xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    csv: 'text/csv;charset=utf-8',
  });

  function definition(type) {
    const trouve = Import.TYPES && Object.prototype.hasOwnProperty.call(Import.TYPES, type) ? Import.TYPES[type] : null;
    if (!trouve) throw new Import.ErreurImport('Type de données inconnu : « ' + type + ' ».');
    return trouve;
  }

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur);
  }

  function titres(type) {
    return definition(type).champs.map((champ) => champ.libelle);
  }

  function exemple(type) {
    return definition(type).champs.map((champ) => texte(champ.exemple));
  }

  /** Feuille « Aide » : présentation du type, puis une ligne par colonne du modèle. */
  function aideModele(type) {
    const description = definition(type);
    const lignes = [
      ['Modèle « ' + description.libelle + ' » — Prévo ' + texte(App.version)],
      [description.aide],
      ['Remplissez la feuille « Données » : gardez la ligne de titres, remplacez la ligne d\'exemple par vos '
        + 'données, une fiche par ligne. Les colonnes peuvent être dans un autre ordre ; Prévo les reconnaît '
        + 'par leur titre et vous montre tout avant d\'écrire.'],
      [],
      ['Colonne', 'Obligatoire', 'Format', 'Valeurs permises', 'Exemple', 'Autres titres reconnus'],
    ];
    description.champs.forEach((champ) => {
      const valeurs = champ.type === 'booleen' ? 'oui ; non' : (champ.valeurs || []).join(' ; ');
      lignes.push([champ.libelle, champ.obligatoire || champ.cleNaturelle ? 'oui' : 'non', FORMATS[champ.type] || 'texte',
        valeurs, texte(champ.exemple), (champ.synonymes || []).join(' ; ')]);
    });
    return lignes;
  }

  // Cellule CSV au format de Prévo : apostrophe de protection, guillemets si nécessaire.
  function celluleCsv(valeur) {
    const ecrite = Donnees.csv.ecrireValeur({ type: 'texte' }, valeur);
    return /[;"\r\n]|^[ \t]|[ \t]$/.test(ecrite) ? '"' + ecrite.replace(/"/g, '""') + '"' : ecrite;
  }

  function largeurs(lignes) {
    const largeur = [];
    lignes.forEach((ligne) => ligne.forEach((cellule, colonne) => {
      largeur[colonne] = Math.min(60, Math.max(largeur[colonne] || 8, texte(cellule).length + 2));
    }));
    return largeur.map((wch) => ({ wch }));
  }

  async function modele(type, format) {
    const lignes = [titres(type), exemple(type)];
    if (format === 'csv') {
      const contenu = String.fromCharCode(0xFEFF) + lignes.map((ligne) => ligne.map(celluleCsv).join(';') + '\r\n').join('');
      return new Blob([contenu], { type: TYPE_MIME.csv });
    }
    if (format !== 'xlsx') throw new Import.ErreurImport('Format de modèle inconnu : « ' + format + ' » (xlsx ou csv).');
    await App.chargerSheetJS();
    // Toutes les cellules en texte : « 007 » et les dates restent écrites comme dans l'exemple.
    const donnees = XLSX.utils.aoa_to_sheet(lignes.map((ligne) => ligne.map((cellule) => ({ t: 's', v: cellule }))));
    donnees['!cols'] = largeurs(lignes);
    const aide = aideModele(type);
    const feuilleAide = XLSX.utils.aoa_to_sheet(aide);
    feuilleAide['!cols'] = largeurs(aide.slice(4));
    const classeur = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(classeur, donnees, 'Données');
    XLSX.utils.book_append_sheet(classeur, feuilleAide, 'Aide');
    const octets = XLSX.write(classeur, { bookType: 'xlsx', type: 'array', compression: true });
    return new Blob([octets], { type: TYPE_MIME.xlsx });
  }

  function nomModele(type, format) {
    definition(type);
    return 'prevo-modele-' + type + '.' + (format === 'csv' ? 'csv' : 'xlsx');
  }

  return { modele, nomModele, aideModele };
})());
