'use strict';
// Parc : MODULE D'ATTENTE (tâche T11). Remplacé entièrement par la tâche T12
// (arborescence, fiche équipement complète, QR, création et modification).
// En attendant, il liste les équipements actifs : cela sert aussi à vérifier le réaffichage
// automatique quand equipements.csv change sur un autre poste.

const Parc = (() => {

  function afficherListe(conteneur) {
    const equipements = Donnees.lignes('equipements').filter((e) => e.actif !== '0')
      .slice().sort((a, b) => String(a.repere).localeCompare(String(b.repere), 'fr'));
    UI.remplir(conteneur, UI.html`
      <div class="entete-page"><div><h1>Parc</h1><p>Écran livré par la tâche T12.</p></div></div>
      <article class="carte">
        <h2>${equipements.length} équipement(s) actif(s)</h2>
        <ul class="liste-cartes">
          ${equipements.map((e) => UI.html`<li><a href="#/equipement/${encodeURIComponent(e.id)}">
            <div class="carte-tete"><b>${e.repere || e.id}</b></div>
            <div class="carte-titre">${e.designation}</div></a></li>`)}
        </ul>
      </article>`);
  }

  function afficherFiche(conteneur, parametres) {
    const equipement = Donnees.trouver('equipements', parametres.id);
    App.definirTitre(equipement ? equipement.repere || equipement.id : 'Équipement');
    UI.remplir(conteneur, UI.html`
      <div class="entete-page"><div>
        <div class="fil"><a href="#/parc">Parc</a> › <span>${parametres.id}</span></div>
        <h1>${equipement ? (equipement.repere || equipement.id) + ' — ' + equipement.designation : 'Équipement ' + parametres.id}</h1>
        <p>Fiche équipement livrée par la tâche T12.</p>
      </div></div>
      ${equipement ? '' : UI.vide('Équipement introuvable', 'Aucun équipement ne porte cet identifiant.', 'parc')}`);
  }

  // App est chargé après les modules : les écrans sont enregistrés une fois la page lue.
  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'parc', route: /^#\/parc$/, titre: 'Parc',
      menu: { libelle: 'Parc', icone: 'parc', ordre: 40 },
      profils: ['demandeur', 'technicien', 'responsable'],
      tables: ['equipements', 'localisations'],
      afficher: afficherListe,
    });
    App.ecran({
      id: 'equipement', route: /^#\/equipement\/(?<id>[^/?]+)$/, titre: 'Équipement', parent: 'parc',
      profils: ['demandeur', 'technicien', 'responsable'],
      tables: ['equipements', 'localisations'],
      afficher: afficherFiche,
    });
  });

  return { afficherListe, afficherFiche };
})();
