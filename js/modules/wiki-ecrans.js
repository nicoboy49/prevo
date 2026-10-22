'use strict';
// Wiki (5/5) — écrans du wiki de maintenance (lot 6, ARCHITECTURE.md §20.7) : #/wiki (liste des pages et
// recherche) et #/wiki/<équipement> (page d'un équipement), pour les trois profils ; champ de recherche
// réutilisable (OT, DI) ; enregistrement des écrans auprès d'App. Dernier fichier du module.

Object.assign(Wiki, (() => {

  // Tables lues par les écrans : réaffichés si l'une change sur un autre poste.
  const TABLES = ['equipements', 'ordres_travail', 'demandes', 'codes_defaillance', 'mouvements_stock',
    'articles', 'wiki_syntheses'];
  const PROFILS = ['demandeur', 'technicien', 'responsable'];

  function afficherListe(conteneur) {
    UI.remplir(conteneur, UI.html`
      <div class="entete-page">
        <div>
          <h1>Wiki de maintenance</h1>
          <p>Ce que l'atelier sait de chaque équipement : pannes habituelles, ce qui les a réglées, pièces changées.</p>
        </div>
      </div>
      <div class="wiki-liste"></div>`);
  }

  function afficherPage(conteneur, parametres) {
    UI.remplir(conteneur, UI.html`
      <div class="fil"><a href="#/wiki">Wiki</a> › <span>${parametres.id}</span></div>
      <div class="entete-page">
        <div>
          <h1>Wiki de l'équipement</h1>
        </div>
      </div>
      <div class="wiki-page"></div>`);
  }

  // App est chargé après les modules : les écrans sont enregistrés une fois la page lue.
  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'wiki',
      route: /^#\/wiki$/,
      titre: 'Wiki',
      menu: { libelle: 'Wiki', icone: 'wiki', ordre: 42 },
      profils: PROFILS,
      tables: TABLES,
      afficher: afficherListe,
    });
    App.ecran({
      id: 'wiki-equipement',
      route: /^#\/wiki\/(?<id>[^/?]+)$/,
      titre: 'Wiki de l\'équipement',
      parent: 'wiki',
      profils: PROFILS,
      tables: TABLES,
      afficher: afficherPage,
    });
  });

  return {};
})());
