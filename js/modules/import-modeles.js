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

  /** Format attendu d'une colonne selon le type du champ (lu à l'affichage) ; « texte » par défaut. */
  function formatDe(type) {
    switch (type) {
      case 'date': return I18n.t('import.format.date');
      case 'date_heure': return I18n.t('import.format.date_heure');
      case 'decimal': return I18n.t('import.format.decimal');
      case 'entier': return I18n.t('import.format.entier');
      case 'booleen': return I18n.t('import.format.booleen');
      case 'choix': return I18n.t('import.format.choix');
      default: return I18n.t('import.format.texte');
    }
  }
  const TYPE_MIME = Object.freeze({
    xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    csv: 'text/csv;charset=utf-8',
  });

  function definition(type) {
    const trouve = Import.TYPES && Object.prototype.hasOwnProperty.call(Import.TYPES, type) ? Import.TYPES[type] : null;
    if (!trouve) throw new Import.ErreurImport(I18n.t('import.erreur.type_inconnu', { type }));
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
      [I18n.t('import.aide_modele.titre', { type: description.libelle, version: texte(App.version) })],
      [description.aide],
      [I18n.t('import.aide_modele.remplissez_feuille_donnees_gardez')],
      [],
      [I18n.t('import.aide_modele.colonne'), I18n.t('import.aide_modele.obligatoire'), I18n.t('import.aide_modele.format'), I18n.t('import.aide_modele.valeurs_permises'), I18n.t('import.aide_modele.exemple'), I18n.t('import.aide_modele.autres_titres_reconnus')],
    ];
    description.champs.forEach((champ) => {
      const valeurs = champ.type === 'booleen' ? I18n.t('import.aide_modele.oui_non') : (champ.valeurs || []).join(' ; ');
      lignes.push([champ.libelle, champ.obligatoire || champ.cleNaturelle ? I18n.t('import.aide_modele.oui') : I18n.t('import.aide_modele.non'), formatDe(champ.type),
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
    if (format !== 'xlsx') throw new Import.ErreurImport(I18n.t('import.modele.format_modele_inconnu_xlsx', { format }));
    await App.chargerSheetJS();
    // Toutes les cellules en texte : « 007 » et les dates restent écrites comme dans l'exemple.
    const donnees = XLSX.utils.aoa_to_sheet(lignes.map((ligne) => ligne.map((cellule) => ({ t: 's', v: cellule }))));
    donnees['!cols'] = largeurs(lignes);
    const aide = aideModele(type);
    const feuilleAide = XLSX.utils.aoa_to_sheet(aide);
    feuilleAide['!cols'] = largeurs(aide.slice(4));
    const classeur = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(classeur, donnees, I18n.t('import.modele.donnees'));
    XLSX.utils.book_append_sheet(classeur, feuilleAide, I18n.t('import.modele.aide'));
    const octets = XLSX.write(classeur, { bookType: 'xlsx', type: 'array', compression: true });
    return new Blob([octets], { type: TYPE_MIME.xlsx });
  }

  function nomModele(type, format) {
    definition(type);
    return 'prevo-modele-' + type + '.' + (format === 'csv' ? 'csv' : 'xlsx');
  }

  return { modele, nomModele, aideModele };
})());
