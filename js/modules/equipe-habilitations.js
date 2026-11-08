'use strict';
// Equipe — habilitations à l'écran (2.2, lot L3, CS172, CS179 ; types d'habilitation de window.CatalogueFR).
// Créé vide par T410 (socle des L2-L3) ; il recevra (T432) les fenêtres « Ajouter », « Renouveler » et « Corriger »
// une habilitation, déplacées d'equipe-ecrans.js et étendues (type du catalogue, recyclage, échéance calculée,
// justificatif), et la carte « Habilitations » de la fiche d'un technicien (Equipe.interne.carteHabilitations).
// Profils : le responsable écrit ; le technicien lit (lien du justificatif sur sa propre fiche seulement).
// Chargé juste après equipe-ecrans.js et avant equipe-acces.js. Complète l'objet Equipe ; la fiche
// (equipe-ecrans.js) appellera ce fichier par Equipe.interne, au moment de l'appel.

Object.assign(Equipe, (() => {

  return {};
})());
