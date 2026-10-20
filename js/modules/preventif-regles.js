'use strict';
// Preventif : module M4 « Maintenance préventive » de Prévo — gammes, déclenchement RG5 (date,
// compteur, seuil), calendrier sur 12 semaines (ARCHITECTURE.md §14.3 ; brief §7 RG5, §9 E8).
//
// Le module est découpé en quatre fichiers, chargés dans cet ordre par index.html (§14.2) :
//   preventif-regles.js       CE FICHIER, qui crée l'objet Preventif : règles PURES
//                             (dernierReleve, etatGamme, calendrier) — tâche T26
//   preventif-ecritures.js    genererOTEchus, apresCloture, gammes et check-lists — tâche T28
//   preventif-ecrans.js       écrans #/preventif et #/preventif/gamme/… — tâche T28
//   preventif-calendrier.js   onglet « Calendrier 12 semaines » — tâche T28
//
// FICHIER D'ATTENTE (tâche T24) : il crée l'objet, vide. La tâche T26 le remplace.

const Preventif = (() => {

  // Rien pour l'instant : les règles pures arrivent avec la tâche T26.
  return {};
})();
