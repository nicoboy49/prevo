'use strict';
// Demandes : MODULE D'ATTENTE (tâche T11). Remplacé entièrement par la tâche T13
// (nouvelle DI pensée téléphone, liste des DI, fiche et décisions du responsable).

const Demandes = (() => {

  function attente(conteneur, titre) {
    UI.remplir(conteneur, UI.html`
      <div class="entete-page"><div><h1>${titre}</h1><p>Écran livré par la tâche T13.</p></div></div>`);
  }

  // App est chargé après les modules : les écrans sont enregistrés une fois la page lue.
  // Ordre d'enregistrement important : « #/di/nouvelle » avant « #/di/<id> ».
  document.addEventListener('DOMContentLoaded', () => {
    const tousProfils = ['demandeur', 'technicien', 'responsable'];
    App.ecran({
      id: 'nouvelle-di', route: /^#\/di\/nouvelle$/, titre: 'Signaler un problème',
      menu: { libelle: 'Signaler', icone: 'ajouter', ordre: 15 },
      profils: tousProfils, tables: [],
      afficher: (conteneur) => attente(conteneur, 'Signaler un problème'),
    });
    App.ecran({
      id: 'liste-di', route: /^#\/di$/, titre: 'Demandes',
      menu: { libelle: 'Demandes', icone: 'demandes', ordre: 20 },
      profils: tousProfils, tables: ['demandes'],
      afficher: (conteneur) => attente(conteneur, 'Demandes'),
    });
    App.ecran({
      id: 'fiche-di', route: /^#\/di\/(?<id>[^/?]+)$/, titre: 'Demande', parent: 'liste-di',
      profils: tousProfils, tables: ['demandes'],
      afficher: (conteneur, parametres) => attente(conteneur, 'Demande ' + parametres.id),
    });
  });

  return {};
})();
