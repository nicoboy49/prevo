'use strict';
// Garanties — écritures des garanties et des contrats de prestataires (2.2, lot L4, CS173).
// Créé vide par T450 (squelette du L4) ; il recevra (T452) : creerGarantie, modifierGarantie, retirerGarantie,
// creerContrat, modifierContrat, retirerContrat (actif = 0, jamais de suppression), reconduireContrat (nouvelle
// période), noterResiliation (reconduction tacite à 0, date de la lettre au journal) et ecrireDocument (document joint
// sans écrasement) ; valeurs refusées par verifierGarantie et verifierContrat (garanties-regles.js) ; une ligne de
// journal par écriture.
// Profils : le responsable écrit ; le technicien lit ; le demandeur ne reçoit pas ces tables.
// Chargé juste après garanties-regles.js (qui crée l'objet Garanties). Complète l'objet Garanties ; une fonction d'un
// fichier chargé plus tard est cherchée au moment de l'appel.

Object.assign(Garanties, (() => {

  return {};
})());
