'use strict';
// Apropos : écran « À propos » (#/apropos, tous profils ; brief §9 E13 et « Signature »).
// Version, mode de stockage, aide (guide), limites de sécurité, bibliothèques et licences, crédit.

const Apropos = (() => {

  const CREDIT = 'Développé par Claude (Anthropic) à la demande de Nicolas Briand — SELECTIS';

  // Bibliothèques embarquées dans js/lib/ (textes complets des licences dans js/lib/LICENCES.txt).
  const BIBLIOTHEQUES = [
    { nom: 'PapaParse', version: '5.7.0', licence: 'MIT', role: 'lecture des fichiers CSV' },
    { nom: 'qrcode-generator', version: '2.0.4', licence: 'MIT', role: 'dessin des QR codes' },
    { nom: 'jsQR', version: '1.4.0', licence: 'Apache-2.0', role: 'lecture des QR codes par la caméra' },
    { nom: 'JSZip', version: '3.10.2', licence: 'MIT', role: 'export ZIP' },
    { nom: 'ECharts', version: '5.5.1', licence: 'Apache-2.0', role: 'graphiques des indicateurs' },
    { nom: 'SheetJS CE', version: '0.20.3', licence: 'Apache-2.0', role: 'lecture des fichiers Excel et OpenDocument (import)' },
    { nom: 'Police Sora', version: '', licence: 'OFL 1.1', role: 'police de caractères' },
  ];

  const MODES = {
    serveur: 'Serveur',
    dossier: 'Dossier',
    demo: 'Démo',
  };

  // Modèle qui a construit le wiki de la démo (lot 6, §20.10) : lu dans son journal, en mode démo seulement.
  function modeleWikiDemo(mode) {
    if (mode !== 'demo') return '';
    const entree = Donnees.lignes('wiki_journal').find((ligne) => ligne.nature === 'ingestion' && ligne.modele);
    return entree ? entree.modele : '';
  }

  function afficher(conteneur) {
    const mode = App.mode;
    const libelleStockage = App.adaptateur ? App.adaptateur.libelle : '';
    // Lot 7 (D126) : avec les comptes exigés, le profil vient du compte et le serveur vérifie les droits ; la limite
    // « ce n'est pas une sécurité » ne vaut que sans comptes (portée « ce PC », modes dossier et démo).
    const comptesExiges = typeof App.comptesExiges === 'function' && App.comptesExiges();
    UI.remplir(conteneur, UI.html`
      <div class="entete-page">
        <div>
          <h1>À propos de Prévo</h1>
          <p>GMAO libre pour l'atelier : parc, demandes d'intervention, ordres de travail, préventif, magasin, planning, contrôles, indicateurs.</p>
        </div>
      </div>
      <div class="grille">
        <article class="carte c6">
          <h2>Version</h2>
          <dl class="valeurs">
            <dt>Application</dt><dd>Prévo — GMAO</dd>
            <dt>Version</dt><dd>${App.version}</dd>
            <dt>Date</dt><dd>${UI.dateFr(App.dateVersion)}</dd>
            <dt>Mise à jour</dt><dd id="apropos-maj">${typeof MiseAJour !== 'undefined' ? MiseAJour.ligneApropos() : ''}</dd>
            <dt>Contenu</dt><dd>Lots 1 à 4 : parc, demandes, ordres de travail, préventif et préventif suggéré, magasin, planning, contrôles réglementaires, équipe, indicateurs et rapport mensuel, assistant IA, dictée</dd>
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
              l'export ZIP permet de garder une copie. Son wiki de maintenance a été construit par
              Claude${modeleWikiDemo(mode) ? ' (' + modeleWikiDemo(mode) + ')' : ''} avec la consigne de Prévo, un agent par OT,
              dans l'ordre des interventions ; la démo n'appelle aucune IA.</li>
          </ul>
          <p class="note">Dans tous les modes, les données sont des fichiers CSV (séparateur « ; », UTF-8) lisibles dans Excel.</p>
        </article>
        <article class="carte c6">
          <h2>Limites à connaître</h2>
          <ul class="apropos-liste">
            ${comptesExiges ? UI.html`
            <li>Chaque personne a son compte et son rôle ; le serveur vérifie les droits : un écran ou une donnée réservés à un autre rôle lui sont refusés.</li>
            <li>Usage sur le réseau local ou par un réseau privé (Tailscale, VPN de l'entreprise) : ne jamais exposer le serveur directement sur Internet.</li>` : UI.html`
            <li>Les profils adaptent les écrans, ce n'est pas une sécurité : n'importe qui peut choisir le profil Responsable.</li>
            <li>Usage sur réseau local uniquement, sans authentification : ne jamais exposer le serveur sur Internet.</li>`}
            <li>Assistant IA (facultatif, réglé dans « Ce poste ») : l'IA propose, vous validez ; rien n'est enregistré sans vous. Un fournisseur en ligne reçoit les textes envoyés : il faut l'autorisation du responsable.</li>
            <li>Dictée : dans Chrome et Edge, la voix est en général transcrite par les serveurs de Google ou de Microsoft.</li>
          </ul>
        </article>
        <article class="carte c6">
          <h2>Aide</h2>
          <p><a href="GUIDE.html" target="_blank" rel="noopener">Ouvrir le guide d'utilisation</a> : démarrer, chaque module, assistant IA, dictée, https, sauvegardes. Il s'imprime.</p>
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
