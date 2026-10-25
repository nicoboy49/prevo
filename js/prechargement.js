'use strict';
// Préchargement de la police Sora (ex-script en ligne d'index.html, déplacé ici pour la politique de sécurité
// du contenu, lot 7 §22.13 : script-src 'self', aucun script en ligne). Seulement en http(s) : en file://, Chrome
// refuse un préchargement de police (règle CORS) et l'inscrit en erreur dans la console.
(function () {
  if (location.protocol !== 'http:' && location.protocol !== 'https:') return;
  const prechargement = document.createElement('link');
  prechargement.rel = 'preload';
  prechargement.href = 'css/polices/sora-latin-wght-normal.woff2';
  prechargement.as = 'font';
  prechargement.type = 'font/woff2';
  prechargement.crossOrigin = 'anonymous';
  document.head.appendChild(prechargement);
})();
