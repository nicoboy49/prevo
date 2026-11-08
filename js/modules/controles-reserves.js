'use strict';
// Controles — réserves des contrôles réglementaires (2.2, lot L2, CS170 ; table reserves_controle, D183, D187).
// Créé vide par T410 (socle des L2-L3) ; il recevra :
// - T411 : les règles pures des réserves (lignesDeReserves, reserveLevee, echeanceReserve, etatReserve,
//   reservesDuControle, reservesOuvertes, reservesEnRetard, adresseOtReserve) ;
// - T413 : leurs écritures (ajouterReserves, leverReserve, modifierReserve, lierOtAReserve), toutes par
//   Donnees.modifier('reserves_controle'), contrôles refaits sur la ligne fraîche, jamais de suppression.
// Chargé juste après controles-regles.js (qui crée l'objet Controles) et avant controles-catalogue.js. Complète
// l'objet Controles ; une fonction d'un fichier chargé plus tard est cherchée au moment de l'appel.

Object.assign(Controles, (() => {

  return {};
})());
