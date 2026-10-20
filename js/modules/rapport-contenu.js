'use strict';
// Rapport : rapport mensuel figé (ARCHITECTURE.md §15.10 ; CDC du lot 3, D43 à D45).
//
// Le module est découpé en 2 fichiers, chargés dans cet ordre par index.html (§15.1) :
//   rapport-contenu.js         CE FICHIER, qui crée l'objet Rapport : contenu PUR du rapport et page HTML autonome — tâche T51
//   rapport-ecrans.js          figer, onglet « Rapports mensuels », proposition de l'accueil — tâche T51
// Les fichiers suivants complètent l'objet : Object.assign(Rapport, (() => { … return { … }; })()).
//
// FICHIER D'ATTENTE (tâche T41) : il crée l'objet, vide. La tâche T51 le remplace.

const Rapport = (() => {

  // Rien pour l'instant : le contenu arrive avec la tâche T51.
  return { interne: {} };
})();
