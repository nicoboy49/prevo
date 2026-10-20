'use strict';
// Équipe : techniciens et habilitations (écran « Équipe », RG8 ; ARCHITECTURE.md §15.8 ;
// brief §6 « techniciens » et « habilitations », §7 RG8, §9 E1).
//
// Le module est découpé en 3 fichiers, chargés dans cet ordre par index.html (§15.1) :
//   equipe-regles.js           CE FICHIER, qui crée l'objet Equipe : règles PURES (etatHabilitation, habilitationsQuiComptent, aRenouveler) — tâche T44
//   equipe-ecritures.js        techniciens et habilitations : création, modification, renouvellement — tâche T46
//   equipe-ecrans.js           écrans #/equipe, #/equipe/nouveau, #/equipe/<id> — tâche T46
// Les fichiers suivants complètent l'objet : Object.assign(Equipe, (() => { … return { … }; })()).
//
// FICHIER D'ATTENTE (tâche T41) : il crée l'objet, vide. La tâche T44 le remplace.

const Equipe = (() => {

  // Rien pour l'instant : le contenu arrive avec la tâche T44.
  return { interne: {} };
})();
