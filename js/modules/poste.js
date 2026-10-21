'use strict';
// Poste — écran « Ce poste » (#/poste, tous les profils ; ARCHITECTURE.md §17.7) : identité du poste
// et profil, assistant IA, dictée, affichage (thème sombre ou clair). Les réglages propres au poste
// restent dans son navigateur ; le réglage partagé « fournisseurs d'IA en ligne autorisés » est dans
// Paramètres (responsable).

const Poste = (() => {

  const THEMES = { sombre: 'Sombre', clair: 'Clair' };

  return { THEMES };
})();
