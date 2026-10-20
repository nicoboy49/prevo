'use strict';
// Magasin (2/5) — écritures du magasin (ARCHITECTURE.md §14.4) : sorties et retours imputés à un OT
// (refus d'un stock négatif, RG6), entrées, inventaire, achats et fournisseurs, colonne `stock` des articles.
//
// FICHIER D'ATTENTE (tâche T24) : il n'ajoute rien à l'objet Magasin. La tâche T27 le remplace.

Object.assign(Magasin, (() => ({}))());
