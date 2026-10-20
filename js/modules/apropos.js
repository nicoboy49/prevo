'use strict';
// Apropos : écran « À propos » (#/apropos, tous profils ; brief §9 E13 et « Signature »).
// Version, mode de stockage, limites de sécurité, bibliothèques et licences, crédit.

const Apropos = (() => {

  const CREDIT = 'Développé par Claude (Anthropic) à la demande de Nicolas Briand — SELECTIS';

  // Bibliothèques embarquées dans js/lib/ (textes complets des licences dans js/lib/LICENCES.txt).
  const BIBLIOTHEQUES = [
    { nom: 'PapaParse', version: '5.7.0', licence: 'MIT', role: 'lecture des fichiers CSV' },
    { nom: 'qrcode-generator', version: '2.0.4', licence: 'MIT', role: 'dessin des QR codes' },
    { nom: 'jsQR', version: '1.4.0', licence: 'Apache-2.0', role: 'lecture des QR codes par la caméra' },
    { nom: 'JSZip', version: '3.10.2', licence: 'MIT', role: 'export ZIP' },
    { nom: 'ECharts', version: '5.5.1', licence: 'Apache-2.0', role: 'graphiques (à partir du lot 3)' },
    { nom: 'Police Sora', version: '', licence: 'OFL 1.1', role: 'police de caractères' },
  ];

  const MODES = {
    serveur: 'Serveur',
    dossier: 'Dossier',
    demo: 'Démo',
  };

  function afficher(conteneur) {
    const mode = App.mode;
    const libelleStockage = App.adaptateur ? App.adaptateur.libelle : '';
    UI.remplir(conteneur, UI.html`
      <div class="entete-page">
        <div>
          <h1>À propos de Prévo</h1>
          <p>GMAO libre pour l'atelier : demandes d'intervention, ordres de travail, parc d'équipements.</p>
        </div>
      </div>
      <div class="grille">
        <article class="carte c6">
          <h2>Version</h2>
          <dl class="valeurs">
            <dt>Application</dt><dd>Prévo — GMAO</dd>
            <dt>Version</dt><dd>${App.version}</dd>
            <dt>Date</dt><dd>${UI.dateFr(App.dateVersion)}</dd>
            <dt>Contenu</dt><dd>Lot 1 : socle, parc, demandes, ordres de travail</dd>
            <dt>Stockage actuel</dt><dd>${libelleStockage || MODES[mode] || '—'}</dd>
          </dl>
        </article>
        <article class="carte c6">
          <h2>Les trois modes de stockage</h2>
          <ul class="apropos-liste">
            <li><b>Serveur</b> : <code>Lancer_GMAO.bat</code> (ou <code>lancer.sh</code>) démarre un petit serveur sur ce PC.
              Plusieurs postes et des téléphones travaillent ensemble sur le réseau local ; les QR codes ouvrent la fiche de l'équipement.</li>
            <li><b>Dossier</b> : <code>index.html</code> ouvert dans Chrome ou Edge, avec un dossier de fichiers CSV choisi sur le PC.
              Un seul poste, aucune installation.</li>
            <li><b>Démo</b> : un atelier fictif en mémoire, pour découvrir l'outil. Rien n'est enregistré ;
              l'export ZIP permet de garder une copie.</li>
          </ul>
          <p class="note">Dans tous les modes, les données sont des fichiers CSV (séparateur « ; », UTF-8) lisibles dans Excel.</p>
        </article>
        <article class="carte c6">
          <h2>Limites à connaître</h2>
          <ul class="apropos-liste">
            <li>Les profils adaptent les écrans, ce n'est pas une sécurité : n'importe qui peut choisir le profil Responsable.</li>
            <li>Usage sur réseau local uniquement, sans authentification : ne jamais exposer le serveur sur Internet.</li>
            <li>Assistant IA et dictée vocale : pas encore disponibles (prévus au lot 4).</li>
          </ul>
        </article>
        <article class="carte c6">
          <h2>Bibliothèques et licences</h2>
          <p>Le code de Prévo est sous licence MIT. Il embarque ces composants libres, chacun sous sa licence :</p>
          <ul class="apropos-liste">
            ${BIBLIOTHEQUES.map((b) => UI.html`<li><b>${b.nom}${b.version ? ' ' + b.version : ''}</b> — ${b.licence} (${b.role})</li>`)}
          </ul>
          <p><a href="js/lib/LICENCES.txt" target="_blank" rel="noopener">Lire le texte complet des licences</a></p>
        </article>
      </div>
      <article class="carte apropos-credit">
        ${UI.logo()}
        <p>${CREDIT}</p>
      </article>`);
  }

  // App est chargé après les modules : l'écran est enregistré une fois la page lue.
  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'apropos',
      route: /^#\/apropos$/,
      titre: 'À propos',
      menu: { libelle: 'À propos', icone: 'apropos', ordre: 100 },
      profils: ['demandeur', 'technicien', 'responsable'],
      tables: [],
      afficher,
    });
  });

  return { CREDIT, afficher };
})();
