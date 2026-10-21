'use strict';
// Import (6/7) — écran « Importer des données » (#/import, responsable seulement ; lot 5, ARCHITECTURE.md
// §18.9) : étapes « Quoi », « D'où » et « Colonnes » de l'assistant. Complète l'objet Import.

Object.assign(Import, (() => {

  function afficher(conteneur) {
    UI.remplir(conteneur, UI.html`
      <div class="entete-page">
        <div>
          <h1>Importer des données</h1>
          <p>Reprenez vos listes existantes (Excel, OpenDocument, CSV) : rien n'est écrit avant votre validation.</p>
        </div>
      </div>
      <div class="import-etapes"></div>`);
  }

  // App est chargé après les modules : l'écran est enregistré une fois la page lue.
  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'import',
      route: /^#\/import$/,
      titre: 'Importer des données',
      parent: 'parametres',
      profils: ['responsable'],
      tables: [],
      afficher,
    });
  });

  return {};
})());
