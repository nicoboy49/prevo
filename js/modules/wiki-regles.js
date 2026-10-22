'use strict';
// Wiki (1/5) — wiki de maintenance (lot 6, ARCHITECTURE.md §20) : crée l'objet Wiki. Ce fichier portera
// les constantes, la couche calculée d'une page (Wiki.page, §20.3), l'état d'une synthèse et les
// contrôles du texte [IA] (§20.4) — des fonctions pures, sans écriture. Les fichiers suivants
// (wiki-recherche.js … wiki-ecrans.js) complètent l'objet.

const Wiki = (() => {

  // Seuils du lot (D100), documentés dans le guide.
  const SEUILS = Object.freeze({
    otMinimum: 5,          // OT clôturés à partir desquels une synthèse peut être proposée
    otEnvoyesMax: 40,      // OT envoyés à l'IA au plus (les plus récents)
    pucesMax: 6,           // puces d'une synthèse
    motsMax: 150,          // mots d'une synthèse (citations exclues)
    recidiveJours: 30,     // récidive : même équipement, même cause, dans les 30 jours après la clôture
    dernieres: 10,         // dernières interventions montrées
    symptomesMax: 5,       // symptômes les plus fréquents montrés
  });

  return { SEUILS };
})();
