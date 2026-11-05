'use strict';
// InstallationFiche : la fiche d'accès imprimable de l'assistant d'installation (étape 8 et route #/installation/fiche ;
// ARCHITECTURE.md §22.10 ; D131 ; CS130), mise en page d'après GET /api/installation/fiche : adresses de la porte,
// QR « ouvrir Prévo » (UI.qrSvg sur l'adresse de la porte), QR « faire confiance au PC atelier » quand l'autorité
// locale existe (même adresse : la porte guide le téléphone), adresse Tailscale et du mandataire, comment arrêter et
// relancer, où sont les données, mot de passe oublié. « Imprimer » copie la fiche dans #impression (seul imprimé,
// règle de css/style.css) puis window.print() ; à l'impression : fond blanc, encre noire, aucun bouton, deux QR
// lisibles (css/modules/installation.css, @media print). Après l'installation, la fiche reste consultable dans la
// coque sur #/installation/fiche (responsable, mode serveur ; le serveur ne la sert qu'au PC serveur : message sinon).
// Dépendances : UI ; App (route dans la coque). Un seul écouteur DOMContentLoaded pour le module « installation ».

const InstallationFiche = (() => {

  const TAILLE_QR_PX = 160;
  const DELAI_NETTOYAGE_IMPRESSION_MS = 2000;   // #impression vidé après l'impression (afterprint, ou ce délai)

  /** Première adresse par laquelle les autres appareils ouvrent Prévo (la porte), sinon ce PC. */
  function adressePrincipale(fiche) {
    return (fiche.adresses && fiche.adresses[0]) || fiche.adresse_tailscale
      || (fiche.adresses_mandataire && fiche.adresses_mandataire[0]) || fiche.adresse_locale || '';
  }

  function qr(texte, libelle, id) {
    let dessin;
    try {
      dessin = UI.qrSvg(texte, TAILLE_QR_PX);
    } catch (erreur) {
      dessin = UI.html`<p class="aide">${(erreur && erreur.message) || 'QR indisponible.'}</p>`;
    }
    return UI.html`<figure class="fiche-qr" id="${id}">${dessin}<figcaption><b>${libelle}</b><span class="fiche-adresse">${texte}</span></figcaption></figure>`;
  }

  function texteDemarrage(fiche) {
    const lanceur = fiche.lanceur || 'Lancer_GMAO.bat';
    if (fiche.demarrage === 'systeme') {
      return 'Prévo démarre avec le PC, sans fenêtre, avant toute ouverture de session. Pour l\'arrêter ou le relancer : '
        + 'Paramètres › Accès et installation sur ce PC (ou le Planificateur de tâches, tâche « Prevo »). Un double-clic sur '
        + lanceur + ' lance une seconde instance seulement si la première est arrêtée.';
    }
    if (fiche.demarrage === 'session') {
      return 'Prévo démarre quand vous ouvrez votre session, dans une fenêtre à ne pas fermer. Pour l\'arrêter : fermez cette '
        + 'fenêtre ; pour le relancer : double-clic sur ' + lanceur + '.';
    }
    return 'Prévo se lance à la main : double-clic sur ' + lanceur + ' dans son dossier, et la fenêtre reste ouverte. Pour '
      + 'l\'arrêter : fermez cette fenêtre. Les téléphones ne joignent Prévo que quand il tourne.';
  }

  function texteMotDePasse(fiche) {
    if (!fiche.comptes) {
      return UI.html`<p>Aucun mot de passe : Prévo n'est joignable que sur ce PC. Dès qu'un téléphone ou un collègue doit le joindre,
        l'assistant (Paramètres › Accès et installation) crée le compte du responsable.</p>`;
    }
    const reinitialisation = fiche.reinitialisation || {};
    return UI.html`<p>Un mot de passe perdu se remplace <b>sur ce PC seulement</b>, jamais par courriel :
      ${reinitialisation.script ? UI.html`double-clic sur <b>${reinitialisation.script}</b> dans le dossier de Prévo, ou ` : ''}
      la commande <code>${reinitialisation.commande || 'serveur.py --reinitialiser <identifiant>'}</code>. Un mot de passe provisoire est
      affiché une seule fois ; il est à changer à la connexion suivante.</p>
      ${fiche.responsables && fiche.responsables.length ? UI.html`<p>Responsable${fiche.responsables.length > 1 ? 's' : ''} : <b>${fiche.responsables.join(', ')}</b>.
        Les autres comptes se créent dans Équipe › Accès.</p>` : ''}`;
  }

  /** Élément de la fiche d'accès (données de GET /api/installation/fiche). */
  function rendre(fiche) {
    const principale = adressePrincipale(fiche);
    const reseau = (fiche.adresses || []).concat(fiche.adresses_mandataire || []);
    return UI.element(UI.html`<div class="fiche-acces">
      <div class="fiche-entete">
        <div><h2>Fiche d'accès Prévo</h2><p class="aide">À imprimer et à garder près du PC serveur.</p></div>
        <button type="button" class="btn btn-secondaire sans-impression" id="fiche-imprimer">${UI.icone('imprimer')}<span>Imprimer</span></button>
      </div>
      <section class="fiche-bloc">
        <h3>Ouvrir Prévo</h3>
        <p>Sur ce PC : <b class="fiche-adresse">${fiche.adresse_locale || ''}</b></p>
        ${reseau.length ? UI.html`<p>Depuis les postes et les téléphones de l'atelier :</p>
          <ul>${reseau.map((adresse) => UI.html`<li class="fiche-adresse">${adresse}</li>`)}</ul>` : ''}
        ${fiche.adresse_tailscale ? UI.html`<p>Hors de l'atelier, par Tailscale (l'application Tailscale ouverte sur le téléphone) :
          <b class="fiche-adresse">${fiche.adresse_tailscale}</b></p>` : ''}
        ${fiche.portee === 'ce-pc' ? UI.html`<p>Prévo n'est joignable que sur ce PC : aucune autre adresse.</p>` : ''}
        <div class="fiche-qrs">
          ${qr(principale, 'Ouvrir Prévo', 'fiche-qr-ouvrir')}
          ${fiche.autorite_presente && fiche.adresse_confiance ? qr(fiche.adresse_confiance, 'Faire confiance au PC atelier', 'fiche-qr-confiance') : ''}
        </div>
        ${fiche.autorite_presente ? UI.html`<p class="aide">« Faire confiance au PC atelier » : une fois par téléphone, deux minutes. La page guide l'installation du
          certificat (Android, iPhone), puis la caméra et le micro marchent dans Prévo.</p>` : ''}
      </section>
      <section class="fiche-bloc">
        <h3>Arrêter et relancer</h3>
        <p>${texteDemarrage(fiche)}</p>
      </section>
      <section class="fiche-bloc">
        <h3>Où sont les données</h3>
        <p>Prévo : <b>${fiche.dossier || ''}</b>. Les fichiers CSV et les documents : <b>${fiche.dossier_donnees || ''}</b>
          (sauvegarde quotidienne dans son sous-dossier sauvegardes).</p>
        <p>${fiche.copie_sauvegardes ? UI.html`Copie externe chaque nuit dans <b>${fiche.copie_sauvegardes}</b> (30 copies gardées).`
          : 'Aucune copie externe : à régler dans Paramètres › Sauvegardes (clé USB, NAS, dossier synchronisé).'}</p>
      </section>
      <section class="fiche-bloc">
        <h3>Mot de passe oublié</h3>
        ${texteMotDePasse(fiche)}
      </section>
    </div>`);
  }

  // Impression : la fiche seule, copiée dans #impression (enfant direct de body, seul imprimé quand il est rempli).
  function preparerImpression(element) {
    const zone = UI.$('#impression');
    UI.remplir(zone, element.cloneNode(true));
    return zone;
  }

  function terminerImpression() {
    const zone = UI.$('#impression');
    if (zone) zone.textContent = '';
  }

  function imprimer(element) {
    preparerImpression(element);
    window.addEventListener('afterprint', terminerImpression, { once: true });
    setTimeout(terminerImpression, DELAI_NETTOYAGE_IMPRESSION_MS);
    window.print();
  }

  /** Branche « Imprimer » sur une fiche rendue (rendre), puis la rend. */
  function brancher(element) {
    const bouton = UI.$('#fiche-imprimer', element);
    if (bouton) bouton.addEventListener('click', () => imprimer(element));
    return element;
  }

  async function lire() {
    let reponse;
    try {
      reponse = await fetch('/api/installation/fiche', { cache: 'no-store', credentials: 'same-origin' });
    } catch (erreur) {
      throw new Error('Le serveur Prévo ne répond pas.');
    }
    const donnees = await reponse.json().catch(() => null);
    if (!reponse.ok) {
      throw new Error(reponse.status === 404 ? 'La fiche d\'accès ne se consulte que sur le PC serveur (ouvrez Prévo sur ce PC).'
        : (donnees && donnees.erreur) || 'Le serveur a répondu « ' + reponse.status + ' ».');
    }
    return donnees;
  }

  // Dans la coque, après l'installation : #/installation et #/installation/fiche montrent la fiche (responsable).
  async function afficherDansLaCoque(conteneur) {
    UI.remplir(conteneur, UI.html`<div class="entete-page"><h1>Fiche d'accès</h1></div>`);
    if (App.mode !== 'serveur') {
      conteneur.appendChild(UI.element(UI.vide('Pas de serveur', 'La fiche d\'accès décrit le serveur Prévo : elle n\'existe qu\'en mode serveur.')));
      return;
    }
    let fiche;
    try {
      fiche = await lire();
    } catch (erreur) {
      conteneur.appendChild(UI.bandeau('attention', (erreur && erreur.message) || String(erreur)));
      return;
    }
    conteneur.appendChild(brancher(rendre(fiche)));
    conteneur.appendChild(UI.element(UI.html`<p class="note">Les réglages d'accès se refont dans Paramètres › Accès et installation, depuis le PC serveur.</p>`));
  }

  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'installation-fiche', route: /^#\/installation(\/fiche)?$/, titre: 'Fiche d\'accès',
      profils: ['responsable'],
      afficher(conteneur) { return afficherDansLaCoque(conteneur); },
    });
  });

  return { rendre: (fiche) => brancher(rendre(fiche)), imprimer, preparerImpression, terminerImpression, adressePrincipale, lire };
})();
