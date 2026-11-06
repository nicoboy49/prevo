'use strict';
// Chargeur de la langue active (chantier multilingue, contrat du Lot 2 ; docs/ARCHITECTURE.md §1).
// Placé dans index.html juste après js/i18n/fr.js et js/i18n/aide/fr.js, avant js/schema.js. Si la langue demandée
// n'est pas le français et qu'elle est déclarée par js/i18n/langues.js, elle devient la langue active et ses deux
// fichiers (js/i18n/<code>.js puis js/i18n/aide/<code>.js : toute langue déclarée fournit les deux) sont écrits dans la
// page par document.write pendant son analyse : le navigateur les charge et les exécute aussitôt, de façon synchrone,
// AVANT js/schema.js, en file:// comme en http (un <script src> du même dossier : permis par la politique de sécurité
// du contenu, script-src 'self').
// La langue demandée vient de localStorage « prevo.langue », écrit par le sélecteur de langue (UI.selecteurLangue,
// Lot 3 : écran « Ce poste » et pied du menu ; la langue du compte viendra au Lot 4). Valeur absente, non déclarée ou
// mal formée, stockage refusé : français, sans erreur. La langue choisie donne aussi l'attribut lang de <html>
// (I18n.choisir).
// Ajouté à une page déjà analysée (document.write l'effacerait) : rien n'est fait, la page reste en français.
// Aucun objet global : seulement I18n (js/i18n.js).
(function () {
  const CLE_LANGUE = 'prevo.langue';
  const MOTIF_CODE = /^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$/;
  const REMPLACEMENTS = { '&': '&amp;', '"': '&quot;', '<': '&lt;', '>': '&gt;' };

  function langueDemandee() {
    try {
      return localStorage.getItem(CLE_LANGUE) || '';
    } catch (erreur) {               // stockage refusé (navigation privée stricte, file:// verrouillé) : français
      return '';
    }
  }

  function balise(adresse) {
    return '<script src="' + adresse.replace(/[&"<>]/g, (caractere) => REMPLACEMENTS[caractere]) + '"><\/script>';
  }

  const code = langueDemandee();
  if (!code || code === 'fr' || !MOTIF_CODE.test(code)) return;
  if (!I18n.langues.some((langue) => langue.code === code)) return;
  const script = document.currentScript;
  if (document.readyState !== 'loading' || !script || !script.src) return;
  // Dossier de ce fichier (js/), quelle que soit l'adresse de la page : index.html à la racine, ou une autre page.
  const dossier = script.src.replace(/[?#].*$/, '').replace(/[^/]*$/, '') + 'i18n/';
  const avecAide = I18n.langues.find((langue) => langue.code === code).aide !== false;
  I18n.choisir(code);
  document.write(balise(dossier + code + '.js') + (avecAide ? balise(dossier + 'aide/' + code + '.js') : ''));
  // Langue sans aide longue traduite (« aide: false » dans langues.js) : une seule ligne, une fois (T308, Nicolas).
  if (!avecAide) console.info('Prévo : pas d\'aide longue en « ' + code + ' » ; elle s\'affiche en français.');
})();
