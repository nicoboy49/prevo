'use strict';
// Accueil : MODULE D'ATTENTE (tâche T11). Remplacé entièrement par la tâche T15
// (indicateurs du responsable, OT du technicien, demandes du demandeur, QR de connexion).

const Accueil = (() => {

  function afficher(conteneur) {
    UI.remplir(conteneur, UI.html`
      <div class="entete-page"><div><h1>Accueil</h1><p>Écran livré par la tâche T15.</p></div></div>
      <article class="carte">
        <p>Profil : ${App.libelleProfil()}. En attendant cet écran, le menu donne accès aux autres modules.</p>
      </article>`);
  }

  // App est chargé après les modules : l'écran est enregistré une fois la page lue.
  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'accueil', route: /^#\/accueil$/, titre: 'Accueil',
      menu: { libelle: 'Accueil', icone: 'accueil', ordre: 10 },
      profils: ['demandeur', 'technicien', 'responsable'],
      tables: [],
      afficher,
    });
  });

  return { afficher };
})();
