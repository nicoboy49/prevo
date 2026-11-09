'use strict';
// Garanties : garanties des équipements et contrats de prestataires (2.2, lot L4 ; CDC §3.4, D187, D190, CS173).
// Prévo rappelle la fin d'une garantie et la date limite de résiliation d'un contrat, et garde leurs documents ; il
// est une aide au suivi, la responsabilité reste celle de l'employeur (D182).
//
// Données (format 4 ; les noms font foi dans js/schema.js) :
//   garanties              GAR-0001 : equipement_id, fournisseur_id, date_debut, date_fin, conditions, document, actif
//   contrats_prestataires  CTP-0001 : fournisseur_id, objet, equipement_ids (identifiants séparés par « ; »),
//                          perimetre, date_debut, date_fin, preavis_mois, reconduction_tacite, reconduction_mois,
//                          montant_annuel (hors taxes), document, actif
//   parametres             réglage alerte_echeances_jours (un seul pour les deux tables, D187)
// Une ligne n'est jamais supprimée : « Retirer » met actif à 0.
//
// Le module est découpé en fichiers chargés dans cet ordre par index.html (§15.1), juste après le module Controles :
//   garanties-regles.js       CE FICHIER, qui crée l'objet Garanties : règles PURES (T451 : délai d'alerte, date
//                               limite de résiliation, état d'une garantie et d'un contrat, échéances, reconduction
//                               proposée, total des montants, vérification des valeurs saisies ou importées)
//   garanties-ecritures.js    créer, modifier, retirer, reconduire, noter la résiliation, document joint (T452)
//   garanties-formulaires.js  formulaires d'une garantie et d'un contrat (T455)
//   garanties-ecrans.js       écran #/garanties (onglets, compteurs, filtres), fiches, routes et menu (T456)
//   garanties-encarts.js      encarts des autres écrans : carte et badge de la fiche équipement, rappel à la création
//                               d'un OT correctif (T457)
// Feuille : css/modules/garanties.css. Domaine des textes : section « garanties » de js/i18n/<langue>.js.
//
// Les fichiers suivants complètent l'objet : Object.assign(Garanties, (() => { … })()). Une fonction dont un autre
// fichier du module a besoin est rangée dans Garanties.interne (usage interne au module : ce n'est pas une API) ; une
// fonction d'un fichier chargé plus tard est cherchée au moment de l'appel. Un autre module n'appelle Garanties que
// derrière typeof Garanties !== 'undefined' (les pages de test et outils/wiki_demo.py ne chargent pas tout).
//
// Les fonctions de ce fichier seront PURES : elles lisent Donnees, n'écrivent jamais. Les dates sont des chaînes ISO
// 'AAAA-MM-JJ' ; la date du jour est passée en argument (par défaut Donnees.aujourdhui()).
// Créé vide par T450 (squelette du L4).

const Garanties = (() => {

  return {
    // Usage interne au module (pas une API) : complété par les fichiers suivants.
    interne: {},
  };
})();
