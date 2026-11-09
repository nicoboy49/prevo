'use strict';
// Garanties — formulaires d'une garantie et d'un contrat de prestataire (2.2, lot L4, CS173).
// Créé vide par T450 (squelette du L4) ; il recevra (T455) : les routes #/garanties/garantie/nouvelle,
// #/garanties/garantie/<id>/modifier, #/garanties/contrat/nouveau et #/garanties/contrat/<id>/modifier (équipement
// pré-rempli par ?equipement=, équipements concernés en puces, date limite de résiliation recalculée à la saisie,
// document joint) ; enregistrement par les écritures de garanties-ecritures.js.
// Profil : responsable seul.
// Chargé juste après garanties-ecritures.js et avant garanties-ecrans.js. Complète l'objet Garanties ; une fonction
// d'un fichier chargé plus tard est cherchée au moment de l'appel.

Object.assign(Garanties, (() => {

  return {};
})());
