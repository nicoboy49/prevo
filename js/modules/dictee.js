'use strict';
// Dictee — dictée vocale sur les champs de texte long marqués data-dictee (ARCHITECTURE.md §17.6 ;
// brief §11) : bouton micro, avertissement à la première utilisation sur le poste (la voix part chez
// Google ou Microsoft, sauf reconnaissance sur l'appareil), texte ajouté à la fin du champ sans rien
// effacer, désactivable dans « Ce poste ». Sur un téléphone sans page sécurisée : une aide rappelle la
// dictée du clavier.

const Dictee = (() => {

  const LANGUE = 'fr-FR';

  return { LANGUE };
})();
