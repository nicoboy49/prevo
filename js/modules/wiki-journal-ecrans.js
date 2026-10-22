'use strict';
// Wiki (8/8) — écrans du responsable (§20.9) : journal #/wiki-journal, traitement de la file, écriture à
// la main, contrôle du wiki (lot 6 refondu). Socle (T110) : la route est enregistrée, réservée au
// responsable, avec un texte d'attente ; les écrans arrivent avec T120. Dernier fichier du module.

Object.assign(Wiki, (() => {

  const TABLES = ['wiki_journal', 'wiki_pages', 'ordres_travail'];

  function afficherJournal(conteneur) {
    App.definirTitre('Journal du wiki');
    UI.remplir(conteneur, UI.html`<div class="wiki wiki-journal">
      <div class="entete-page"><div>
        <div class="fil"><a href="#/wiki">Wiki</a></div>
        <h1>Journal du wiki</h1>
        <p>Les propositions de l'IA à valider, la file des OT à intégrer et les écritures à la main.</p>
      </div></div>
      ${UI.vide('Rien pour l\'instant', 'Le journal du wiki arrive avec la suite du lot 6.', 'wiki')}
    </div>`);
  }

  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'wiki-journal',
      route: /^#\/wiki-journal$/,
      titre: 'Journal du wiki',
      parent: 'wiki',
      profils: ['responsable'],
      tables: TABLES,
      afficher: afficherJournal,
    });
  });

  return {};
})());
