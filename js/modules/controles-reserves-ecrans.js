'use strict';
// Controles — réserves à l'écran, fiche d'un contrôle (2.2, lot L2, CS170).
// Créé vide par T410 (socle des L2-L3) ; il recevra :
// - T418 : la carte « Réserves » de la fiche (Controles.interne.carteReserves) ;
// - T419 : les fenêtres « Lever la réserve », « Modifier la réserve », « Ajouter une réserve » ;
// - T420 : « Créer un OT » depuis une réserve (#/ot/nouveau pré-rempli ; rien n'est créé sans « Créer »).
// Profils : le responsable écrit ; le technicien lit (aucun bouton d'écriture rendu) ; le demandeur n'a pas accès.
// Chargé juste après controles-ecrans.js. Complète l'objet Controles ; la fiche (controles-ecrans.js) appellera ce
// fichier par Controles.interne, au moment de l'appel.

Object.assign(Controles, (() => {

  return {};
})());
