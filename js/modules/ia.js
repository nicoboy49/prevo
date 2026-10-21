'use strict';
// Ia (1/3) — assistant IA optionnel (ARCHITECTURE.md §17 ; brief §10 ; CDC du lot 4, D65 à D72) :
// réglages du poste, portée du fournisseur (ce PC, PC atelier, atelier, en ligne), appel direct ou par
// le relais /api/ia du serveur, délai et annulation, validation des réponses. L'IA propose, l'humain
// valide : rien n'est appelé tant que l'IA n'est pas activée sur le poste, rien n'est écrit sans clic.
// Fichiers du module : ia.js (crée l'objet Ia), ia-prompts.js (consignes), ia-encadre.js (boutons et
// encadré Utiliser / Modifier / Ignorer).

const Ia = (() => {

  // Fournisseurs reconnus (brief §10) : Ollama local, ou toute API compatible OpenAI.
  const FOURNISSEURS = {
    ollama: 'Ollama',
    openai: 'API compatible OpenAI',
  };

  return { FOURNISSEURS };
})();
