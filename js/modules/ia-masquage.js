'use strict';
// Ia (masquage) — textes d'atelier masqués avant tout envoi à l'IA (audit I4, ARCHITECTURE.md §22.12 ; Lot 5,
// T374 : formats internationaux). Complète l'objet Ia (Ia.masquer) ; chargé après ia.js, avant ia-prompts.js,
// qui s'en sert pour tout texte envoyé (uneLigne, bloc).

Object.assign(Ia, (() => {

  // Masquage avant l'envoi (audit I4, ARCHITECTURE.md §22.12) : les textes libres d'un atelier (descriptions, comptes
  // rendus, notes, astuces, pages du wiki) peuvent contenir un numéro de téléphone ou une adresse de courriel ; ils
  // partent remplacés par « [téléphone] » et « [courriel] ». Numéros français : 0X XX XX XX XX ou +33 X XX XX XX XX
  // (aussi 0033), groupes collés ou séparés par un même caractère (espace, point ou tiret), « (0) » toléré après +33.
  // Un même séparateur partout : une date « 05.10.2026 08:30 » ou un OT « OT-2026-0107 » ne ressemble pas à un numéro ;
  // ni « 15 855 h » ni « 0,58 bar » (pas de 0 suivi de neuf chiffres).
  const MOTIF_COURRIEL = /[\p{L}\p{N}._%+-]+@[\p{L}\p{N}-]+(?:\.[\p{L}\p{N}-]+)+/gu;
  const MOTIF_TELEPHONE = new RegExp('(?<![\\p{L}\\p{N}])(?:(?:\\+|00)33[ .-]?(?:\\(0\\)[ .-]?)?|0)[1-9]([ .-]?)\\d{2}'
    + '(?:\\1\\d{2}){3}(?![\\p{L}\\p{N}])', 'gu');
  // Lot 5 (T374, D159) : formats internationaux. Indicatif « + » ou « 00 » (tous pays) suivi d'au moins 7 chiffres en
  // groupes (« (0) » toléré) ; numéros nationaux sans indicatif : turcs 0XXX XXX XX XX, portables italiens
  // 3XX XXX XXXX, portugais 9XX XXX XXX ou 2XX XXX XXX, portables britanniques 07XXX XXXXXX.
  const MOTIF_TELEPHONE_INTERNATIONAL = new RegExp('(?<![\\p{L}\\p{N}])(?:(?:\\+|00)[1-9]\\d{0,2}(?:[ .-]?\\(0\\))?'
    + '[ .-]?\\d{1,4}(?:[ .-]?\\d{2,4}){2,4}|0[2-5]\\d{2}([ .-]?)\\d{3}\\1\\d{2}\\1\\d{2}'
    + '|3\\d{2}([ .-]?)\\d{3}\\2\\d{4}|[29]\\d{2}([ .-]?)\\d{3}\\3\\d{3}|07\\d{3}[ .-]?\\d{6})(?![\\p{L}\\p{N}])', 'gu');

  /** Texte → le même texte, numéros de téléphone et adresses de courriel remplacés (« [téléphone] », « [courriel] »). */
  function masquer(valeur) {
    return (valeur === null || valeur === undefined ? '' : String(valeur))
      .replace(MOTIF_COURRIEL, '[courriel]').replace(MOTIF_TELEPHONE, '[téléphone]')
      .replace(MOTIF_TELEPHONE_INTERNATIONAL, '[téléphone]');
  }

  return { masquer };
})());
