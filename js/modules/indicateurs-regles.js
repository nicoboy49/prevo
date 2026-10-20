'use strict';
// Indicateurs : module M6 « Indicateurs » (écran E11 ; ARCHITECTURE.md §15.3 et §15.4 ;
// brief §12).
//
// Le module est découpé en 3 fichiers, chargés dans cet ordre par index.html (§15.1) :
//   indicateurs-regles.js      CE FICHIER, qui crée l'objet Indicateurs : règles PURES (pannes, MTBF, MTTR, disponibilité, préventif, coûts…) — tâche T43
//   indicateurs-graphiques.js  graphiques ECharts, « Voir les valeurs », exports CSV et PNG — tâche T49
//   indicateurs-ecrans.js      écran #/indicateurs — tâche T49
// Les fichiers suivants complètent l'objet : Object.assign(Indicateurs, (() => { … return { … }; })()).
//
// FICHIER D'ATTENTE (tâche T41) : il crée l'objet, vide. La tâche T43 le remplace.

const Indicateurs = (() => {

  // Rien pour l'instant : le contenu arrive avec la tâche T43.
  return { interne: {} };
})();
