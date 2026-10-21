'use strict';
// Suggestions (1/2) — règles du préventif suggéré (ARCHITECTURE.md §16.2 à §16.5 ; CDC du lot 3 bis,
// D51 à D57). Fonctions pures : elles lisent les données et le journal, n'écrivent rien ; seules
// `ignorer` et `marquerTraitee` écrivent, et seulement au journal (une décision du responsable).
// Prévo ne modifie jamais une gamme tout seul.
// Crée l'objet Suggestions ; suggestions-ecrans.js le complète.

const Suggestions = (() => {

  // Type de chaque règle, en clair (badge des cartes : le texte dit le type, la couleur aide seulement).
  const TITRES = {
    S1: 'Créer une gamme',
    S2: 'Revoir le préventif',
    S3: 'Anomalies répétées',
    S4: 'Allonger une gamme',
  };

  return { TITRES };
})();
