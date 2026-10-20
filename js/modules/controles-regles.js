'use strict';
// Controles : contrôles réglementaires (écran E10, RG9 ; ARCHITECTURE.md §15.7 ; brief §6
// « controles_reglementaires », §7 RG9, §9 E10).
//
// Le module est découpé en 3 fichiers, chargés dans cet ordre par index.html (§15.1) :
//   controles-regles.js        CE FICHIER, qui crée l'objet Controles : règles PURES (ajouterMois, prochaineDate, etat, sous30Jours) — tâche T44
//   controles-ecritures.js     création, modification, contrôle réalisé, levée des observations — tâche T47
//   controles-ecrans.js        écrans #/controles, #/controles/nouveau, #/controles/<id> — tâche T47
// Les fichiers suivants complètent l'objet : Object.assign(Controles, (() => { … return { … }; })()).
//
// FICHIER D'ATTENTE (tâche T41) : il crée l'objet, vide. La tâche T44 le remplace.

const Controles = (() => {

  // Rien pour l'instant : le contenu arrive avec la tâche T44.
  return { interne: {} };
})();
