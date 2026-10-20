'use strict';
// Magasin (3/5) — écran #/magasin (onglets articles, mouvements, inventaire, à commander, achats,
// fournisseurs) et fiche d'un article #/magasin/article/<id> (ARCHITECTURE.md §14.4).
//
// FICHIER D'ATTENTE (tâche T24) : il enregistre seulement l'écran #/magasin et son entrée de menu
// (« Magasin », ordre 45, technicien et responsable), qui annonce l'écran à venir. La tâche T27
// le remplace.

Object.assign(Magasin, (() => {

  function afficherAttente(conteneur) {
    UI.remplir(conteneur, UI.html`
      <div class="entete-page"><div>
        <h1>Magasin</h1>
        <p>Écran livré par la tâche T27.</p>
      </div></div>`);
  }

  // App est chargé après les modules : l'écran est enregistré une fois la page lue (§8).
  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'magasin', route: /^#\/magasin$/, titre: 'Magasin',
      menu: { libelle: 'Magasin', icone: 'magasin', ordre: 45 },
      profils: ['technicien', 'responsable'], tables: [],
      afficher: afficherAttente,
    });
  });

  return {};
})());
