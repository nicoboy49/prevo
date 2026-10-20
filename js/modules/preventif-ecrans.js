'use strict';
// Preventif (3/4) — écrans du préventif (ARCHITECTURE.md §14.3) : liste des gammes (#/preventif),
// création et fiche d'une gamme (#/preventif/gamme/nouvelle, #/preventif/gamme/<id>).
//
// FICHIER D'ATTENTE (tâche T24) : il enregistre seulement l'écran #/preventif et son entrée de menu
// (« Préventif », ordre 35, technicien et responsable), qui annonce l'écran à venir. La tâche T28
// le remplace.

Object.assign(Preventif, (() => {

  function afficherAttente(conteneur) {
    UI.remplir(conteneur, UI.html`
      <div class="entete-page"><div>
        <h1>Préventif</h1>
        <p>Écran livré par la tâche T28.</p>
      </div></div>`);
  }

  // App est chargé après les modules : l'écran est enregistré une fois la page lue (§8).
  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'preventif', route: /^#\/preventif$/, titre: 'Préventif',
      menu: { libelle: 'Préventif', icone: 'preventif', ordre: 35 },
      profils: ['technicien', 'responsable'], tables: [],
      afficher: afficherAttente,
    });
  });

  return {};
})());
