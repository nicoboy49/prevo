'use strict';
// Planning : planning de la semaine par technicien (écran E6 ; ARCHITECTURE.md §15.5 ;
// brief §9 E6, §7 RG3 et RG8).
//
// Le module est découpé en 3 fichiers, chargés dans cet ordre par index.html (§15.1) :
//   planning-regles.js         CE FICHIER, qui crée l'objet Planning : règles PURES (lundiDe, joursDeLaSemaine, ordresDeLaSemaine, chargeSemaine, semaine) — tâche T44
//   planning-ecritures.js      planifier (RG3, RG8, journal) — tâche T48
//   planning-ecrans.js         écran #/planning : grille, glisser-déposer, bouton « Planifier… » — tâche T48
// Les fichiers suivants complètent l'objet : Object.assign(Planning, (() => { … return { … }; })()).
//
// FICHIER D'ATTENTE (tâche T41) : il crée l'objet, vide. La tâche T44 le remplace.

const Planning = (() => {

  // Rien pour l'instant : le contenu arrive avec la tâche T44.
  return { interne: {} };
})();
