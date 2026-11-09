'use strict';
// Garanties — écran « Garanties et contrats » (2.2, lot L4, CS173).
// Créé vide par T450 (squelette du L4) ; il recevra (T456) : la liste #/garanties (onglets Garanties et Contrats,
// filtres dans l'adresse, compteurs, total des montants, phrase D182 sous le titre, listes vides expliquées, cartes
// sur téléphone), la fiche d'une garantie (#/garanties/garantie/<id>) et celle d'un contrat
// (#/garanties/contrat/<id> : bandeau « à décider », « Noter la résiliation », « Reconduire », « Retirer »), les
// routes et l'entrée du menu.
// Profil : responsable seul.
// Chargé juste après garanties-formulaires.js et avant garanties-encarts.js. Complète l'objet Garanties ; une fonction
// d'un fichier chargé plus tard est cherchée au moment de l'appel.

Object.assign(Garanties, (() => {

  return {};
})());
