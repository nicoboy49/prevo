'use strict';
// Garanties — encarts dans les écrans des autres modules (2.2, lot L4, CS173).
// Créé vide par T450 (squelette du L4) ; il recevra (T457) : la carte « Garanties et contrats » et le badge
// « Sous garantie jusqu'au … » de la fiche équipement (jamais de montant), le rappel « sous garantie » à la création
// d'un OT correctif (bandeau non bloquant, rien au journal). Les autres modules (parc-fiche.js, ordres-fiche.js,
// demandes-fiche.js) les appellent derrière typeof Garanties !== 'undefined'.
// Profils : technicien et responsable ; le demandeur ne reçoit pas ces tables.
// Dernier fichier du module, chargé juste après garanties-ecrans.js. Complète l'objet Garanties.

Object.assign(Garanties, (() => {

  return {};
})());
