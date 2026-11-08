'use strict';
// AideEcrans : aide à l'écran, un encart d'explication à la première visite de chaque écran (décision de Nicolas
// du 2026-10-25, démo et version installée). Textes : AideEcransTextes (aide-ecrans-textes.js).
//
// Contrat (docs/ARCHITECTURE.md §23) :
//   - App.rendre appelle AideEcrans.apresAffichage(ecran, conteneur) après l'affichage réussi d'un écran NOUVEAU ;
//     l'encart (UI.bandeau('info')) est inséré en tête du contenu, après .entete-page s'il existe ; rien ne bloque.
//   - un écran sans texte prend celui de son parent (formulaires) ; À propos n'en a pas ; les textes à variantes
//     suivent App.profil.type ; dans la version web (App.versionWeb), la phrase « demo » est ajoutée.
//   - mémoire du poste : prevo.aideVue (liste JSON d'identifiants, marqués vus à « Compris » seulement) et
//     prevo.aideActive ('0' = désactivée) ; localStorage refusé : l'encart s'affiche, rien n'est retenu.
//   - « Compris » ferme et marque vu ; Échap ferme sans marquer (l'écran sera réexpliqué) ; AideEcrans.rouvrir()
//     (lien « Explications » du menu) remet l'encart de l'écran courant même s'il est vu.

const AideEcrans = (() => {

  const CLE_VUE = 'prevo.aideVue';
  const CLE_ACTIVE = 'prevo.aideActive';
  const ID_ENCART = 'aide-ecran';

  function lire(cle) {
    try { return window.localStorage.getItem(cle); } catch (erreur) { return null; }
  }

  function ecrire(cle, valeur) {
    try {
      if (valeur === null) window.localStorage.removeItem(cle); else window.localStorage.setItem(cle, valeur);
    } catch (erreur) { /* sans mémoire : l'encart reviendra, tant pis */ }
  }

  function vus() {
    try {
      const liste = JSON.parse(lire(CLE_VUE) || '[]');
      return Array.isArray(liste) ? liste.filter((id) => typeof id === 'string') : [];
    } catch (erreur) {
      return [];
    }
  }

  function estVu(id) { return vus().includes(id); }

  function marquerVu(id) {
    const liste = vus();
    if (!liste.includes(id)) { liste.push(id); ecrire(CLE_VUE, JSON.stringify(liste)); }
  }

  function active() { return lire(CLE_ACTIVE) !== '0'; }

  function activer(oui) { ecrire(CLE_ACTIVE, oui ? '1' : '0'); }

  function revoirTout() { ecrire(CLE_VUE, null); }

  /** Identifiant et entrée de texte d'un écran (le sien, sinon celui de son parent), ou null. */
  function entree(ecran) {
    if (!ecran || typeof AideEcransTextes === 'undefined') return null;
    if (AideEcransTextes[ecran.id]) return { id: ecran.id, texte: AideEcransTextes[ecran.id] };
    if (ecran.parent && AideEcransTextes[ecran.parent]) return { id: ecran.parent, texte: AideEcransTextes[ecran.parent] };
    return null;
  }

  /** Texte et geste pour le profil courant : { titre, ancre, texte, essayez, demo }. */
  function contenu(texte) {
    const profil = (App.profil && App.profil.type) || 'responsable';
    let variante = texte;
    if (texte.profils) {
      variante = texte.profils[profil] || texte.profils.responsable || texte.profils[Object.keys(texte.profils)[0]];
    }
    return { titre: texte.titre, ancre: texte.ancre, texte: variante.texte, essayez: variante.essayez,
      demo: App.versionWeb && texte.demo ? texte.demo : '' };
  }

  function fermer(marquer) {
    const encart = document.getElementById(ID_ENCART);
    if (!encart) return;
    if (marquer && encart.dataset.ecran) marquerVu(encart.dataset.ecran);
    encart.remove();
  }

  function inserer(conteneur, id, texte) {
    fermer(false);
    const c = contenu(texte);
    // Accueil : phrase de la démo en tête ; ailleurs (journal du wiki), juste avant le geste.
    const avant = c.demo && id === 'accueil' ? UI.html`<p class="aide-ecran-demo">${c.demo}</p>` : '';
    const apres = c.demo && id !== 'accueil' ? UI.html` ${c.demo}` : '';
    const encart = UI.bandeau('info', UI.html`
      ${avant}<h2 class="aide-ecran-titre">${c.titre}</h2>
      <p class="aide-ecran-texte">${c.texte}${apres}</p>
      <p class="aide-ecran-essayez">${I18n.html('aide.encart.essayez', { essayez: c.essayez })}</p>
      <div class="aide-ecran-actions">
        <button type="button" class="btn btn-secondaire aide-ecran-compris">${I18n.t('aide.encart.compris')}</button>
        <a class="aide-ecran-guide" href="${UI.adresseGuide()}#${c.ancre}" target="_blank" rel="noopener">${I18n.html('aide.encart.en_savoir_plus')}</a>
      </div>`);
    encart.id = ID_ENCART;
    encart.classList.add('aide-ecran');
    encart.dataset.ecran = id;
    encart.setAttribute('aria-labelledby', ID_ENCART + '-titre');
    encart.querySelector('.aide-ecran-titre').id = ID_ENCART + '-titre';
    encart.querySelector('.aide-ecran-compris').addEventListener('click', () => fermer(true));
    const entete = conteneur.querySelector(':scope > .entete-page');
    if (entete) entete.after(encart); else conteneur.prepend(encart);
    return encart;
  }

  /** Appelé par App.rendre après l'affichage réussi d'un écran nouveau. */
  function apresAffichage(ecran, conteneur) {
    if (!active()) return;
    const trouve = entree(ecran);
    if (!trouve || estVu(trouve.id)) return;
    inserer(conteneur, trouve.id, trouve.texte);
  }

  /** Lien « Explications » : rouvre l'encart de l'écran courant, même déjà vu. Vrai si un encart existe. */
  function rouvrir() {
    const conteneur = document.getElementById('contenu');
    const trouve = entree(App.ecranCourant);
    if (!conteneur || !trouve) return false;
    const encart = inserer(conteneur, trouve.id, trouve.texte);
    const bouton = encart.querySelector('.aide-ecran-compris');
    if (bouton) bouton.focus();
    return true;
  }

  // Échap ferme l'encart (sans le marquer vu) quand le focus est dedans ou qu'aucun champ n'est actif.
  document.addEventListener('keydown', (evenement) => {
    if (evenement.key !== 'Escape') return;
    const encart = document.getElementById(ID_ENCART);
    if (!encart) return;
    const actif = document.activeElement;
    const dansEncart = actif && encart.contains(actif);
    const dansChamp = actif && actif.matches && actif.matches('input, textarea, select, [contenteditable="true"]');
    if (!dansEncart && (dansChamp || document.querySelector('dialog[open]'))) return;
    fermer(false);
  });

  return { apresAffichage, rouvrir, active, activer, revoirTout, estVu, fermer };
})();
