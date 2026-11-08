'use strict';
// Ordres — RG8 à l'écran (2.2, lot L3, D186, D191 ; CS178, CS180) : l'habilitation exigée bloque l'affectation.
// Créé vide par T410 (socle des L2-L3) ; il recevra :
// - T438 : le bandeau d'habilitation (déplacé d'ordres-fiche.js), la fenêtre « passer outre » du responsable
//   (Ordres.demanderDerogation) et Ordres.avecDerogation ;
// - T440 : le champ « Habilitation exigée pour cet OT » (nouvel OT et préparation ; ordres-onglets.js, à 700 lignes,
//   ne grandit pas : la logique d'habilitation de la préparation vient ici).
// Le technicien voit les bandeaux, jamais la case ni le bouton « passer outre ».
// Chargé juste après ordres-impression.js (qui enregistre les écrans du module). Complète l'objet Ordres ; les écrans
// d'ordres-fiche.js et d'ordres-onglets.js appelleront ce fichier par Ordres.interne, au moment de l'appel.

Object.assign(Ordres, (() => {

  return {};
})());
