'use strict';
// Parametres : MODULE D'ATTENTE (tâche T11). Remplacé entièrement par la tâche T15
// (paramètres, sauvegardes et restauration, contrôle de la base, export ZIP).

const Parametres = (() => {

  function attente(conteneur, titre) {
    UI.remplir(conteneur, UI.html`
      <div class="entete-page"><div><h1>${titre}</h1><p>Écran livré par la tâche T15.</p></div></div>`);
  }

  // App est chargé après les modules : les écrans sont enregistrés une fois la page lue.
  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'parametres', route: /^#\/parametres$/, titre: 'Paramètres',
      menu: { libelle: 'Paramètres', icone: 'parametres', ordre: 90, groupe: 'Administration' },
      profils: ['responsable'], tables: ['parametres'],
      afficher: (conteneur) => attente(conteneur, 'Paramètres'),
    });
    App.ecran({
      id: 'controle', route: /^#\/controle$/, titre: 'Contrôle de la base', parent: 'parametres',
      profils: ['responsable'], tables: [],
      afficher: (conteneur) => attente(conteneur, 'Contrôle de la base'),
    });
  });

  return {};
})();
