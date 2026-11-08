'use strict';
// Controles — catalogue des contrôles réglementaires à l'écran (2.2, lot L2, CS171 ; window.CatalogueFR de
// js/catalogue/fr.js, gelé, en lecture seule : aucune fonction de Prévo ne l'écrit).
// Créé vide par T410 (socle des L2-L3) ; il recevra :
// - T414 : les règles pures du catalogue (catalogue, ligneCatalogue, famillesCatalogue, valeursDepuisCatalogue,
//   lireSource, sourceApresSaisie, mentionDuControle, miseAJourProposee) ; sans CatalogueFR, liste vide ;
// - T416 : le bloc du catalogue du formulaire de création (Controles.interne.blocCatalogue).
// Chargé après controles-reserves.js et avant controles-ecritures.js. Complète l'objet Controles ; une fonction d'un
// fichier chargé plus tard est cherchée au moment de l'appel.

Object.assign(Controles, (() => {

  return {};
})());
