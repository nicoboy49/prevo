'use strict';
// Ordres : MODULE D'ATTENTE (tâche T11). Remplacé entièrement par la tâche T14
// (liste des OT, fiche OT et ses onglets, règles RG3, RG4, RG7, RG8, bon de travail).

const Ordres = (() => {

  function attente(conteneur, titre) {
    UI.remplir(conteneur, UI.html`
      <div class="entete-page"><div><h1>${titre}</h1><p>Écran livré par la tâche T14.</p></div></div>`);
  }

  // App est chargé après les modules : les écrans sont enregistrés une fois la page lue.
  document.addEventListener('DOMContentLoaded', () => {
    const profils = ['technicien', 'responsable'];
    App.ecran({
      id: 'liste-ot', route: /^#\/ot$/, titre: 'Ordres de travail',
      menu: { libelle: 'Ordres de travail', court: 'Ordres', icone: 'ordres', ordre: 30 },
      profils, tables: ['ordres_travail'],
      afficher: (conteneur) => attente(conteneur, 'Ordres de travail'),
    });
    App.ecran({
      id: 'fiche-ot', route: /^#\/ot\/(?<id>[^/?]+)$/, titre: 'Ordre de travail', parent: 'liste-ot',
      profils, tables: ['ordres_travail'],
      afficher: (conteneur, parametres) => attente(conteneur, 'Ordre de travail ' + parametres.id),
    });
  });

  return {};
})();
