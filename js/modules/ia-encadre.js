'use strict';
// Ia (3/4) — boutons « avec l'IA » et encadré de proposition (ARCHITECTURE.md §17.4) : progression et
// « Annuler » pendant que l'IA travaille, puis la proposition, la mention « Proposition de l'IA —
// <fournisseur>, <modèle> » et les boutons Utiliser / Modifier / Ignorer. L'encadré n'écrit rien : c'est
// l'écran qui enregistre, sur le bouton habituel. Mention permanente de la portée dans la coque.
// Complète l'objet Ia.
//
// API :
//   Ia.bouton(libelle, surClic) → <button class="ia-bouton"> ou null si l'IA n'est pas utilisable
//     (Ia.active() et Ia.etat() === 'ok') ; surClic(evenement, bouton). Version web (démo en ligne) :
//     toujours posé, l'encadré affiche alors le message Ia.MESSAGE_VERSION_WEB (rien n'est appelé).
//   Ia.emplacement(libelle, surClic) → <div class="ia-emplacement"> qui porte ce bouton quand l'IA est
//     utilisable et le retire sinon, au fil des changements de l'IA (test d'ouverture fini, fournisseur
//     injoignable, réglages du poste, autorisation du responsable), sans réafficher l'écran ; masqué
//     (hidden) sans bouton.
//   Ia.ouvrirEncadre({ apres, fonction, donnees, langue, rendu, utiliser, modifier, boutons }) → Promise de
//     l'issue { choix, resultat, modele, fournisseur, erreur } ; choix : 'utiliser' | 'modifier' |
//     'ignorer' | 'annuler' | 'erreur' | 'ferme' | la `valeur` d'un bouton propre.
//       apres     : élément après lequel l'encadré est placé (un seul encadré à la fois par élément) ;
//       rendu(resultat, reponse) → texte, UI.html ou nœud : la proposition (par défaut : son texte) ;
//       utiliser / modifier(resultat, reponse) : appelés au clic (peuvent être async) ;
//       boutons : [{ libelle, valeur, classe, action(resultat, reponse) }] remplacent Utiliser et
//                 Modifier (« Ajouter les opérations cochées », « Copier ») ; « Ignorer » reste.
//     Une action qui renvoie false (ou lève une erreur, alors affichée) garde l'encadré ouvert.
//     Erreur de l'IA : message dans l'encadré, aucune proposition ; l'issue 'erreur' est rendue tout
//     de suite, le message reste jusqu'à « Fermer ».
//   Ia.fermerEncadre(apres) : ferme l'encadré placé après `apres` (requête en cours abandonnée).
//   Ia.afficherMention() : met à jour la mention de la coque (appelé tout seul sur les changements).

Object.assign(Ia, (() => {

  const ID_MENTION = 'ia-mention';
  // Étincelle au trait (même style que les icônes de UI.icone).
  const DESSIN_ETINCELLE = '<path d="M12 3.5l1.9 5 5 1.9-5 1.9-1.9 5-1.9-5-5-1.9 5-1.9z"/><path d="M18.5 15.5l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z"/>';
  const encadresOuverts = new WeakMap();      // élément « apres » → { encadre, retirer(issue) }

  function iconeIa() {
    return UI.brut('<svg class="icone" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' + DESSIN_ETINCELLE + '</svg>');
  }

  // Boutons IA posés : IA utilisable sur ce poste, ou version web (boutons et emplacements à leur
  // place ; le clic rend le message de la démo en ligne, sans requête).
  function utilisable() {
    return Ia.versionWeb() || (Ia.active() && Ia.etat() === 'ok');
  }

  /** Bouton « avec l'IA » ; null si l'IA n'est pas utilisable sur ce poste (inactive ou injoignable). */
  function bouton(libelle, surClic) {
    if (!utilisable()) return null;
    const element = UI.element(UI.html`<button type="button" class="btn btn-secondaire ia-bouton">${iconeIa()}<span>${libelle}</span></button>`);
    if (typeof surClic === 'function') element.addEventListener('click', (evenement) => surClic(evenement, element));
    return element;
  }

  // ===========================================================================================
  // Encadré de proposition
  // ===========================================================================================

  /** Ferme l'encadré placé après `apres` (s'il y en a un) ; son issue est « ferme ». */
  function fermerEncadre(apres) {
    const ouvert = apres ? encadresOuverts.get(apres) : null;
    if (ouvert) ouvert.retirer({ choix: 'ferme' });
  }

  // Rendu par défaut : le texte proposé, ou les opérations, ou les valeurs simples.
  function renduParDefaut(resultat) {
    if (resultat && typeof resultat.texte === 'string') return UI.html`<p class="ia-texte">${resultat.texte}</p>`;
    if (resultat && Array.isArray(resultat.operations)) {
      return UI.html`<ul class="ia-liste">${resultat.operations.map((o) => UI.html`<li>${o.operation}${o.valeur_attendue ? UI.html` — <i>${o.valeur_attendue}</i>` : ''}</li>`)}</ul>`;
    }
    const valeurs = Object.keys(resultat || {}).filter((cle) => typeof resultat[cle] === 'string' && resultat[cle]);
    return UI.html`<ul class="ia-liste">${valeurs.map((cle) => UI.html`<li>${cle} : <b>${resultat[cle]}</b></li>`)}</ul>`;
  }

  function messageErreur(erreur) {
    if (erreur instanceof Ia.ErreurIa) return erreur.message;
    console.warn('Prévo : erreur de l\'encadré IA (' + (erreur && erreur.message) + ').', erreur);
    return I18n.t('ia.message_erreur.assistant_ia_rencontre_erreur');
  }

  // Boutons de la proposition : ceux de l'écran (ou Utiliser / Modifier), puis toujours Ignorer.
  function definitionsBoutons(options) {
    const propres = Array.isArray(options.boutons) && options.boutons.length ? options.boutons : [
      { libelle: I18n.t('ia.definitions_boutons.utiliser'), valeur: 'utiliser', classe: 'btn-primaire', action: options.utiliser },
      { libelle: I18n.t('commun.bouton.modifier'), valeur: 'modifier', classe: 'btn-secondaire', action: options.modifier },
    ];
    return propres.concat([{ libelle: I18n.t('ia.definitions_boutons.ignorer'), valeur: 'ignorer', classe: 'btn-fantome' }]);
  }

  /** Ouvre l'encadré, demande la proposition et attend le choix (voir l'API en tête de fichier). */
  function ouvrirEncadre(options) {
    const reglages = options || {};
    const apres = reglages.apres;
    if (!apres || !apres.parentNode) throw new Error(I18n.t('ia.ouvrir_encadre.ia_ouvrir_encadre_apres_doit'));
    fermerEncadre(apres);                                   // un seul encadré à la fois par élément

    const encadre = UI.element(UI.html`<section class="encadre ia-encadre" aria-live="polite" aria-label="${I18n.t('ia.ouvrir_encadre.proposition_ia')}"></section>`);
    apres.insertAdjacentElement('afterend', encadre);
    const controleur = new AbortController();
    let resoudre = null;
    const issuePromise = new Promise((fonction) => { resoudre = fonction; });
    let issueDonnee = false;
    let minuteur = null;

    // L'issue n'est donnée qu'une fois ; la requête éventuellement en cours est abandonnée.
    function repondre(issue) {
      if (issueDonnee) return;
      issueDonnee = true;
      clearInterval(minuteur);
      controleur.abort();
      resoudre(issue);
    }

    function retirer(issue) {
      encadre.remove();
      const ouvert = encadresOuverts.get(apres);
      if (ouvert && ouvert.encadre === encadre) encadresOuverts.delete(apres);
      repondre(issue);
    }
    encadresOuverts.set(apres, { encadre, retirer });

    afficherProgression(encadre, () => retirer({ choix: 'annuler' }));
    const debut = Date.now();
    minuteur = setInterval(() => {
      if (!encadre.isConnected) { retirer({ choix: 'ferme' }); return; }   // écran réaffiché entre-temps
      const zone = UI.$('.ia-duree', encadre);
      if (zone) zone.textContent = Math.round((Date.now() - debut) / 1000) + '\u00a0s';
    }, 1000);

    // Erreur (de l'IA ou du rendu) : message dans l'encadré, issue « erreur » rendue tout de suite.
    function echec(erreur) {
      afficherErreur(encadre, messageErreur(erreur), () => retirer({ choix: 'erreur', erreur }));
      repondre({ choix: 'erreur', erreur });
    }

    Ia.demander(reglages.fonction, reglages.donnees, { signal: controleur.signal, langue: reglages.langue }).then((reponse) => {
      if (issueDonnee) return;
      clearInterval(minuteur);
      if (!encadre.isConnected) { retirer({ choix: 'ferme' }); return; }
      try {
        afficherProposition(encadre, reponse, reglages, retirer);
      } catch (erreur) {
        echec(erreur);
      }
    }, (erreur) => {
      if (issueDonnee) return;
      clearInterval(minuteur);
      if (!encadre.isConnected) { retirer({ choix: 'ferme', erreur }); return; }
      echec(erreur);
    });
    return issuePromise;
  }

  function afficherProgression(encadre, annuler) {
    UI.remplir(encadre, UI.html`<div class="chargement ia-progression" role="status">
      <span>${I18n.t('ia.progression.ia_redige')} <span class="ia-duree" aria-hidden="true"></span></span>
      <button type="button" class="btn btn-fantome ia-annuler">${I18n.t('commun.bouton.annuler')}</button>
    </div>`);
    UI.$('.ia-annuler', encadre).addEventListener('click', annuler);
  }

  function afficherErreur(encadre, message, fermer) {
    encadre.classList.add('ia-en-erreur');
    UI.remplir(encadre, UI.html`<p class="ia-erreur" role="alert">${iconeIa()}<span>${message}</span></p>
      <div class="actions ia-actions"><button type="button" class="btn btn-fantome ia-fermer">${I18n.t('commun.bouton.fermer')}</button></div>`);
    UI.$('.ia-fermer', encadre).addEventListener('click', fermer);
  }

  // La proposition, sa mention et ses boutons (une erreur du rendu de l'écran remonte à l'appelant).
  function afficherProposition(encadre, reponse, reglages, retirer) {
    const contenu = typeof reglages.rendu === 'function' ? reglages.rendu(reponse.resultat, reponse) : renduParDefaut(reponse.resultat);
    UI.remplir(encadre, UI.html`<p class="ia-mention-proposition">${iconeIa()}<span>${I18n.t('ia.proposition.proposition_ia', { fournisseur: reponse.fournisseur, modele: reponse.modele })}</span></p>
      <div class="ia-proposition"></div>
      <p class="ia-erreur-action" role="alert" hidden></p>
      <div class="actions ia-actions"></div>`);
    UI.remplir(UI.$('.ia-proposition', encadre), contenu);
    const zoneBoutons = UI.$('.ia-actions', encadre);
    const definitions = definitionsBoutons(reglages);
    const boutons = definitions.map((definition) => {
      const element = UI.element(UI.html`<button type="button" class="btn ${definition.classe || 'btn-secondaire'}">${definition.libelle}</button>`);
      element.addEventListener('click', () => choisir(definition));
      zoneBoutons.appendChild(element);
      return element;
    });

    // Clic : l'action de l'écran d'abord (remplir le champ…), puis l'encadré se ferme avec l'issue.
    async function choisir(definition) {
      const zoneErreur = UI.$('.ia-erreur-action', encadre);
      zoneErreur.hidden = true;
      boutons.forEach((element) => { element.disabled = true; });
      try {
        if (typeof definition.action === 'function') {
          const retour = await definition.action(reponse.resultat, reponse);
          if (retour === false) { boutons.forEach((element) => { element.disabled = false; }); return; }
        }
      } catch (erreur) {
        zoneErreur.textContent = (erreur && erreur.message) || I18n.t('ia.proposition.action_impossible');
        zoneErreur.hidden = false;
        boutons.forEach((element) => { element.disabled = false; });
        console.warn('Prévo : action « ' + definition.libelle + ' » de l\'encadré IA impossible (' + (erreur && erreur.message) + ').', erreur);
        return;
      }
      retirer({ choix: definition.valeur, resultat: reponse.resultat, modele: reponse.modele, fournisseur: reponse.fournisseur });
    }
  }

  // ===========================================================================================
  // Mention permanente de la portée dans la coque (« IA : reste sur ce PC »…)
  // ===========================================================================================

  function texteMention() {
    if (!Ia.active() || Ia.versionWeb()) return '';         // version web : aucun texte ne part
    const reglages = Ia.reglages();
    const mention = Ia.mention(Ia.portee(reglages.url), reglages.url);
    return Ia.etat() === 'injoignable' ? I18n.t('ia.texte_mention.ia_repond_pas', { mention }) : I18n.t('ia.texte_mention.ia', { mention });
  }

  /**
   * Met à jour la mention de la coque : visible quand l'IA est active, au-dessus du contenu de chaque
   * écran (ordinateur et téléphone), en ambre quand les données partent en ligne. Créée à la demande
   * juste avant la zone des alertes de la coque. Renvoie l'élément (ou null sans coque).
   */
  function afficherMention() {
    let zone = document.getElementById(ID_MENTION);
    const contenu = texteMention();
    if (!zone) {
      const ancre = document.getElementById('alertes-app');
      if (!contenu || !ancre) return null;
      zone = UI.element(UI.html`<p class="ia-mention-coque" id="ia-mention">${iconeIa()}<span class="ia-mention-texte"></span></p>`);
      ancre.parentNode.insertBefore(zone, ancre);
    }
    zone.hidden = !contenu;
    UI.$('.ia-mention-texte', zone).textContent = contenu;
    zone.classList.toggle('distant', Boolean(contenu) && Ia.portee(Ia.reglages().url) === 'distant');
    return zone;
  }

  // Réglages ou état de l'IA changés, ou paramètres partagés changés (autorisation du responsable).
  Ia.evenements.addEventListener('changement', () => afficherMention());
  if (typeof Donnees !== 'undefined' && Donnees.evenements) {
    Donnees.evenements.addEventListener('changement', (evenement) => {
      const tables = (evenement.detail && evenement.detail.tables) || [];
      if (tables.includes('parametres')) afficherMention();
    });
  }

  /** Emplacement d'un bouton IA qui suit l'état de l'IA tant qu'il est dans la page (voir l'en-tête). */
  function emplacement(libelle, surClic) {
    const zone = UI.element(UI.html`<div class="ia-emplacement" hidden></div>`);
    let insere = false;
    const poser = () => {
      const disponible = utilisable();
      if (Boolean(zone.firstElementChild) === disponible) return;     // inchangé : l'encadré ouvert reste
      zone.textContent = '';
      const element = disponible ? bouton(libelle, surClic) : null;
      if (element) zone.appendChild(element);
      zone.hidden = !element;
    };
    const suivre = () => {
      if (!zone.isConnected) { if (insere) Ia.evenements.removeEventListener('changement', suivre); return; }
      insere = true;
      poser();
    };
    Ia.evenements.addEventListener('changement', suivre);
    poser();
    return zone;
  }

  return { bouton, emplacement, ouvrirEncadre, fermerEncadre, afficherMention };
})());
