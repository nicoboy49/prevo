'use strict';
// Preventif (4/4) — onglet « Calendrier 12 semaines » de l'écran #/preventif (ARCHITECTURE.md
// §14.3) : échéances des gammes (estimées pour un compteur) et OT préventifs ouverts, semaine par semaine.
//
// FICHIER D'ATTENTE (tâche T24) : il n'ajoute rien à l'objet Preventif. La tâche T28 le remplace.

Object.assign(Preventif, (() => ({}))());
