'use strict';
// Import (1/7) — assistant d'import des données existantes (lot 5, ARCHITECTURE.md §18) : types de
// données, correspondance des colonnes, conversion, clés naturelles, aperçu à blanc. Fonctions pures :
// rien n'est écrit ici. Fichiers du préfixe : import-regles.js (crée Import), import-historique.js,
// import-lecture.js, import-ecritures.js, import-modeles.js, import-ecrans.js, import-apercu.js.

const Import = (() => {

  /** Erreur de l'import (fichier illisible, trop grand, chiffré…) : message en français pour l'écran. */
  class ErreurImport extends Error {
    constructor(message) {
      super(message);
      this.name = 'ErreurImport';
    }
  }

  return { ErreurImport };
})();
