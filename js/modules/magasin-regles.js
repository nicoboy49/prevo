'use strict';
// Magasin : module M5 « Magasin » de Prévo — articles, mouvements de stock, inventaire, articles à
// commander, achats et fournisseurs ; règle RG6 « stock jamais négatif » (ARCHITECTURE.md §14.4 ;
// brief §7 RG6, §9 E9).
//
// Le module est découpé en cinq fichiers, chargés dans cet ordre par index.html (§14.2) :
//   magasin-regles.js       CE FICHIER, qui crée l'objet Magasin : règles PURES
//                           (suggestionPointCommande, aCommander, sortiesDeLOt) — tâche T26
//   magasin-ecritures.js    sortir, retourner, entrer, inventorier, achats, fournisseurs — tâche T27
//   magasin-articles.js     écran #/magasin, liste et fiche des articles — tâche T27
//   magasin-mouvements.js   mouvements de stock et inventaire — tâche T27
//   magasin-achats.js       articles à commander, achats et fournisseurs — tâche T27
//
// FICHIER D'ATTENTE (tâche T24) : il crée l'objet, vide. La tâche T26 le remplace.

const Magasin = (() => {

  // Rien pour l'instant : les règles pures arrivent avec la tâche T26.
  return {};
})();
