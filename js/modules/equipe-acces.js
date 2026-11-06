'use strict';
// EquipeAcces — écran « Équipe › Accès » (#/equipe/acces ; ARCHITECTURE.md §22.3, §22.4, §22.5 ; CDC D124, D125,
// CS124) : comptes (créer, modifier, réinitialiser, désactiver, activer), appareils enrôlés (invitation par QR et
// lien, révocation), journal des connexions (consulter, exporter). Responsable seulement, en mode serveur avec les
// comptes exigés (sans comptes : un message, rien à gérer).
// Les appels à l'API d'accès du serveur (/api/session, /api/acces/…, lot 7) sont faits ici par fetch avec l'en-tête
// X-Prevo ; le serveur vérifie la session et le rôle (403 sinon). Le mot de passe provisoire d'un compte et le
// jeton d'une invitation sont montrés une seule fois, dans une fenêtre, et ne sont jamais mémorisés ni journalisés.
// Lien d'une invitation : adresse donnée par Prévo pour les QR (App.urlFicheEquipement, donc la porte d'entrée ou
// l'adresse choisie pour les étiquettes) + chemin rendu par le serveur (/#/enroler/<jeton>).
// Dépendances : App, UI, Donnees (techniciens liés, erreurs). Charte : css/modules/equipe.css (section 5).

const EquipeAcces = (() => {

  // Rôles d'un compte : valeurs stockées par le serveur (D155), jamais traduites ; seul leur affichage passe par une clé.
  const ROLES = ['responsable', 'technicien', 'demandeur'];
  const DUREE_PAR_DEFAUT_H = 24;
  const LIGNES_JOURNAL_AFFICHEES = 300;

  /** Libellé d'un rôle (tableau des comptes, fenêtre du mot de passe provisoire) ; '' pour un rôle inconnu. */
  function libelleRole(role) {
    if (role === 'responsable') return I18n.t('equipe.role.responsable');
    if (role === 'technicien') return I18n.t('equipe.role.technicien');
    if (role === 'demandeur') return I18n.t('equipe.role.demandeur');
    return '';
  }

  /** Libellé d'un rôle dans la liste du formulaire de compte (en minuscules, comme la valeur qu'il montrait). */
  function libelleRoleListe(role) {
    if (role === 'responsable') return I18n.t('equipe.role_liste.responsable');
    if (role === 'technicien') return I18n.t('equipe.role_liste.technicien');
    return I18n.t('equipe.role_liste.demandeur');
  }

  /** Durées proposées pour une invitation ; libellés lus à l'affichage. */
  function dureesInvitation() {
    return [
      { heures: 1, libelle: I18n.t('equipe.duree_invitation.heures', { n: 1 }) },
      { heures: 24, libelle: I18n.t('equipe.duree_invitation.heures', { n: 24 }) },
      { heures: 72, libelle: I18n.t('equipe.duree_invitation.jours', { n: 3 }) },
      { heures: 168, libelle: I18n.t('equipe.duree_invitation.jours', { n: 7 }) },
    ];
  }

  /** Libellé d'un résultat du journal des connexions (code écrit par le serveur) ; '' pour un code inconnu. */
  function libelleResultat(cle) {
    switch (cle) {
      case 'connexion': return I18n.t('equipe.libelle_resultat.connexion');
      case 'echec': return I18n.t('equipe.libelle_resultat.echec');
      case 'bloque': return I18n.t('equipe.libelle_resultat.bloque');
      case 'deconnexion': return I18n.t('equipe.libelle_resultat.deconnexion');
      case 'appareil': return I18n.t('equipe.libelle_resultat.appareil_enrole');
      case 'invitation': return I18n.t('equipe.libelle_resultat.invitation');
      case 'revocation': return I18n.t('equipe.libelle_resultat.revocation');
      case 'reinitialisation': return I18n.t('equipe.libelle_resultat.reinitialisation');
      case 'creation': return I18n.t('equipe.libelle_resultat.compte_cree');
      case 'modification': return I18n.t('equipe.libelle_resultat.compte_modifie');
      default: return '';
    }
  }
  const TONS_RESULTAT = { connexion: 'ok', appareil: 'ok', creation: 'ok', echec: 'ko', bloque: 'ko', revocation: 'attention' };
  const NOM_FICHIER_JOURNAL = 'journal-acces.csv';
  const MARQUE_ORDRE_OCTETS = String.fromCharCode(0xFEFF);

  // ===========================================================================================
  // 1. Appels au serveur
  // ===========================================================================================

  /** Requête JSON vers l'API d'accès ; une erreur du serveur devient une ErreurStockage au message du serveur. */
  async function appeler(chemin, options) {
    const reglages = options || {};
    const entetes = { 'X-Prevo': '1' };
    let corps;
    if (reglages.corps !== undefined) {
      entetes['Content-Type'] = 'application/json; charset=utf-8';
      corps = JSON.stringify(reglages.corps);
    }
    let reponse;
    try {
      reponse = await fetch(chemin, { method: reglages.methode || 'GET', headers: entetes, body: corps,
        cache: 'no-store', credentials: 'same-origin' });
    } catch (erreur) {
      throw new Donnees.ErreurStockage(I18n.t('equipe.appeler.serveur_prevo_repond_pas'), erreur);
    }
    if (reglages.texte) {
      if (!reponse.ok) throw await erreurDe(reponse);
      return reponse.text();
    }
    const donnees = await reponse.json().catch(() => null);
    if (!reponse.ok) throw new Donnees.ErreurStockage(messageDe(donnees, reponse.status));
    return donnees || {};
  }

  async function erreurDe(reponse) {
    const donnees = await reponse.json().catch(() => null);
    return new Donnees.ErreurStockage(messageDe(donnees, reponse.status));
  }

  function messageDe(donnees, statut) {
    if (donnees && typeof donnees.erreur === 'string' && donnees.erreur) return donnees.erreur;
    return I18n.t('commun.message.serveur_a_repondu', { status: statut });
  }

  const api = {
    session: () => appeler('/api/session'),
    comptes: () => appeler('/api/acces/comptes'),
    creerCompte: (champs) => appeler('/api/acces/comptes', { methode: 'POST', corps: champs }),
    changerCompte: (identifiant, action, champs) => appeler('/api/acces/comptes/' + encodeURIComponent(identifiant),
      { methode: 'POST', corps: Object.assign({ action: action }, champs || {}) }),
    invitations: () => appeler('/api/acces/invitations'),
    creerInvitation: (heures) => appeler('/api/acces/invitations', { methode: 'POST', corps: { heures: heures } }),
    revoquerInvitation: (id) => appeler('/api/acces/invitations/' + encodeURIComponent(id) + '/revoquer', { methode: 'POST' }),
    revoquerAppareil: (id) => appeler('/api/acces/appareils/' + encodeURIComponent(id) + '/revoquer', { methode: 'POST' }),
    revoquerTous: () => appeler('/api/acces/appareils/revoquer-tous', { methode: 'POST' }),
    journal: () => appeler('/api/acces/journal', { texte: true }),
  };

  // ===========================================================================================
  // 2. Petits outils d'écran
  // ===========================================================================================

  const texte = (valeur) => String(valeur === undefined || valeur === null ? '' : valeur).trim();

  /** « 2026-10-26T10:05:00 » (heure locale du serveur) → « 26/10/2026 10:05 » ; le texte tel quel sinon. */
  function dateHeure(valeur) {
    const trouve = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/.exec(texte(valeur));
    if (!trouve) return texte(valeur);
    return trouve[3] + '/' + trouve[2] + '/' + trouve[1] + ' ' + trouve[4] + ':' + trouve[5];
  }

  /** Badge d'état ; barre : texte barré (révoqué, désactivé). */
  function badge(libelle, ton, barre) {
    return barre ? UI.html`<span class="badge ${ton || 'neutre'} barre">${libelle}</span>`
      : UI.html`<span class="badge ${ton || 'neutre'}">${libelle}</span>`;
  }

  function nomDuTechnicien(id) {
    const technicien = texte(id) ? Donnees.trouver('techniciens', texte(id)) : null;
    if (!technicien) return texte(id);
    return (texte(technicien.prenom) + ' ' + texte(technicien.nom)).trim() || texte(id);
  }

  function erreurHtml(erreur) {
    const message = (erreur && erreur.message) || I18n.t('commun.message.erreur_inconnue');
    return UI.bandeau('important', UI.html`${I18n.html('equipe.erreur.lecture_impossible', { message })}`);
  }

  /** Début de l'adresse mise dans les QR (« http://192.168.1.10:8080/ ») : la même que les étiquettes. */
  function adresseDeBase() {
    const exemple = App.urlFicheEquipement('X');
    const fin = '#/equipement/X';
    return (exemple.endsWith(fin) ? exemple.slice(0, -fin.length) : exemple).replace(/\/+$/, '');
  }

  function lienInvitation(chemin) {
    return adresseDeBase() + '/' + texte(chemin).replace(/^\/+/, '');
  }

  /** Bouton occupé le temps d'une action ; une erreur est signalée (App.signalerErreur). */
  async function pendant(bouton, contexte, action) {
    if (bouton && bouton.disabled) return false;
    if (bouton) { bouton.disabled = true; bouton.setAttribute('aria-busy', 'true'); }
    try {
      await action();
      return true;
    } catch (erreur) {
      App.signalerErreur(erreur, contexte);
      return false;
    } finally {
      if (bouton) { bouton.disabled = false; bouton.removeAttribute('aria-busy'); }
    }
  }

  function definition(nom, type, libelle, options) {
    return Object.assign({ nom: nom, type: type, libelle: libelle }, options || {});
  }

  function listeTechniciens() {
    return Donnees.lignes('techniciens')
      .filter((t) => texte(t.actif) !== '0')
      .map((t) => ({ valeur: t.id, libelle: (texte(t.prenom) + ' ' + texte(t.nom)).trim() || t.id }));
  }

  // ===========================================================================================
  // 3. Comptes
  // ===========================================================================================

  function champsCompte(compte) {
    const valeur = (nom) => (compte ? compte[nom] : undefined);
    const champRole = UI.champ(definition('role', 'choix', I18n.t('equipe.champs_compte.role'), { valeurs: ROLES, obligatoire: true }),
      valeur('role') || 'demandeur',
      { aide: I18n.t('equipe.champs_compte.responsable_tout_reglages_compris') });
    // Valeurs stockées (D155) : chaque option montre le libellé de son rôle, la valeur reste le code.
    UI.$$('option', champRole).forEach((option) => { if (ROLES.includes(option.value)) option.textContent = libelleRoleListe(option.value); });
    return [
      UI.champ(definition('prenom', 'texte', I18n.t('commun.champ.prenom'), { obligatoire: true }), valeur('prenom'), { attributs: { maxlength: '60' } }),
      UI.champ(definition('nom', 'texte', I18n.t('equipe.champs_compte.nom')), valeur('nom'), { attributs: { maxlength: '60' } }),
      champRole,
      UI.champ(definition('technicien_id', 'ref', I18n.t('equipe.champs_compte.technicien_lie')), valeur('technicien_id'),
        { liste: listeTechniciens(), aide: I18n.t('equipe.champs_compte.compte_technicien_fiche_equipe') }),
    ];
  }

  function verifierCompte(valeurs) {
    const erreurs = [];
    if (!texte(valeurs.prenom)) erreurs.push({ nom: 'prenom', message: I18n.t('equipe.verifier_compte.prenom_obligatoire') });
    if (!ROLES.includes(texte(valeurs.role))) erreurs.push({ nom: 'role', message: I18n.t('equipe.verifier_compte.choisissez_role') });
    if (texte(valeurs.role) === 'technicien' && !texte(valeurs.technicien_id)) {
      erreurs.push({ nom: 'technicien_id', message: I18n.t('equipe.verifier_compte.compte_technicien_lie_fiche') });
    }
    if (texte(valeurs.role) !== 'technicien' && texte(valeurs.technicien_id)) {
      erreurs.push({ nom: 'technicien_id', message: I18n.t('equipe.verifier_compte.seul_compte_technicien_lie') });
    }
    return erreurs;
  }

  function champsEnvoyes(valeurs) {
    return { prenom: texte(valeurs.prenom), nom: texte(valeurs.nom), role: texte(valeurs.role),
      technicien_id: texte(valeurs.technicien_id) };
  }

  /** Mot de passe provisoire montré une seule fois : à noter et à remettre en main propre. */
  function montrerMotDePasseProvisoire(compte, motDePasse, titre) {
    const role = libelleRole(texte(compte.role)) || texte(compte.role);
    return UI.fenetre({
      titre: titre,
      classe: 'equipe-fenetre',
      contenu: UI.html`<div class="form-colonne acces-provisoire">
        <p>${I18n.html('equipe.montrer_mot_de_passe_provisoire.compte_identifiant_role', { identifiant: texte(compte.identifiant), role })}</p>
        <p>${I18n.html('equipe.montrer_mot_de_passe_provisoire.mot_passe_provisoire_montre')}</p>
        <div class="champ"><input type="text" class="acces-mot-de-passe" id="acces-mot-de-passe-provisoire" readonly
          value="${motDePasse}" aria-label="${I18n.t('equipe.montrer_mot_de_passe_provisoire.mot_passe_provisoire')}" spellcheck="false"></div>
        <p class="note">${I18n.t('equipe.montrer_mot_de_passe_provisoire.notez_donnez_main_propre')}</p>
      </div>`,
      boutons: [{ libelle: I18n.t('equipe.montrer_mot_de_passe_provisoire.ai_note_mot_passe'), valeur: 'ok', classe: 'btn-primaire', defaut: true }],
    });
  }

  async function creerCompte(rafraichir) {
    let resultat = null;
    const cree = await UI.fenetreAction({
      titre: I18n.t('equipe.creer_compte.creer_compte'),
      introduction: I18n.t('equipe.creer_compte.identifiant_prenom_nom_donne'),
      champs: champsCompte(null),
      libelleValider: I18n.t('equipe.creer_compte.creer_le_compte'),
      verifier: verifierCompte,
      action: async (valeurs) => { resultat = await api.creerCompte(champsEnvoyes(valeurs)); },
    });
    if (!cree || !resultat) return;
    App.marquerSaisie(false);
    await montrerMotDePasseProvisoire(resultat.compte || {}, texte(resultat.mot_de_passe_provisoire), I18n.t('equipe.creer_compte.titre_compte_cree'));
    UI.toast(I18n.t('equipe.creer_compte.compte_cree'), 'succes');
    await rafraichir();
  }

  async function modifierCompte(compte, rafraichir) {
    const fait = await UI.fenetreAction({
      titre: I18n.t('equipe.modifier_compte.modifier_compte', { identifiant: texte(compte.identifiant) }),
      champs: champsCompte(compte),
      libelleValider: I18n.t('commun.bouton.enregistrer'),
      verifier: verifierCompte,
      action: async (valeurs) => { await api.changerCompte(compte.identifiant, 'modifier', champsEnvoyes(valeurs)); },
    });
    if (!fait) return;
    UI.toast(I18n.t('equipe.modifier_compte.compte_enregistre_role_change'), 'succes');
    await rafraichir();
  }

  async function reinitialiserCompte(compte, bouton, rafraichir) {
    const confirme = await UI.confirmer(I18n.t('equipe.reinitialiser_compte.reinitialiser_mot_passe_sessions', { identifiant: texte(compte.identifiant) }), { titre: I18n.t('equipe.reinitialiser_compte.reinitialiser_mot_passe'), oui: I18n.t('equipe.reinitialiser_compte.reinitialiser') });
    if (!confirme) return;
    await pendant(bouton, 'réinitialisation du mot de passe', async () => {
      const resultat = await api.changerCompte(compte.identifiant, 'reinitialiser');
      await montrerMotDePasseProvisoire(resultat.compte || compte, texte(resultat.mot_de_passe_provisoire), I18n.t('equipe.reinitialiser_compte.mot_passe_reinitialise'));
      await rafraichir();
    });
  }

  async function changerActivation(compte, bouton, rafraichir) {
    const desactiver = texte(compte.actif) !== '0' && compte.actif !== false;
    if (desactiver) {
      const confirme = await UI.confirmer(I18n.t('equipe.changer_activation.desactiver_personne_pourra_plus', { identifiant: texte(compte.identifiant) }),
      { titre: I18n.t('equipe.changer_activation.desactiver_compte'), oui: I18n.t('commun.bouton.desactiver'), danger: true });
      if (!confirme) return;
    }
    await pendant(bouton, desactiver ? 'désactivation du compte' : 'activation du compte', async () => {
      await api.changerCompte(compte.identifiant, desactiver ? 'desactiver' : 'activer');
      UI.toast(desactiver ? I18n.t('equipe.changer_activation.compte_desactive') : I18n.t('equipe.changer_activation.compte_active'), 'succes');
      await rafraichir();
    });
  }

  function actionsCompte(compte, session, rafraichir) {
    const soiMeme = session && session.session && session.session.identifiant === compte.identifiant;
    const actif = compte.actif !== false && texte(compte.actif) !== '0';
    const groupe = UI.element(UI.html`<span class="acces-actions" data-compte="${compte.identifiant}">
      <button type="button" class="btn btn-secondaire" data-action="modifier">${I18n.t('equipe.actions_compte.modifier')}</button>
      <button type="button" class="btn btn-secondaire" data-action="reinitialiser">${I18n.t('equipe.actions_compte.reinitialiser')}</button>
      ${soiMeme ? '' : UI.html`<button type="button" class="btn ${actif ? 'btn-danger' : 'btn-secondaire'}" data-action="${actif ? 'desactiver' : 'activer'}">${actif ? I18n.t('commun.bouton.desactiver') : I18n.t('equipe.actions_compte.activer')}</button>`}
    </span>`);
    UI.$$('button', groupe).forEach((bouton) => bouton.addEventListener('click', () => {
      const action = bouton.dataset.action;
      if (action === 'modifier') modifierCompte(compte, rafraichir);
      else if (action === 'reinitialiser') reinitialiserCompte(compte, bouton, rafraichir);
      else changerActivation(compte, bouton, rafraichir);
    }));
    return groupe;
  }

  function etatCompte(compte) {
    const actif = compte.actif !== false && texte(compte.actif) !== '0';
    const morceaux = [badge(actif ? I18n.t('equipe.etat_compte.actif') : I18n.t('equipe.etat_compte.desactive'), actif ? 'ok' : 'neutre', !actif)];
    if (compte.a_changer) morceaux.push(badge(I18n.t('equipe.montrer_mot_de_passe_provisoire.mot_passe_provisoire'), 'attention'));
    return UI.html`<span class="equipe-statut">${morceaux}</span>`;
  }

  async function afficherComptes(panneau, session) {
    UI.remplir(panneau, UI.html`<p class="muted">${I18n.t('equipe.comptes.chargement_comptes')}</p>`);
    let donnees;
    try {
      donnees = await api.comptes();
    } catch (erreur) {
      UI.remplir(panneau, erreurHtml(erreur));
      return;
    }
    const comptes = Array.isArray(donnees.comptes) ? donnees.comptes : [];
    const rafraichir = () => afficherComptes(panneau, session);
    const carte = UI.element(UI.html`<section class="carte acces-carte" id="acces-comptes">
      <div class="entete-carte"><h2>${I18n.html('equipe.comptes.comptes_nb_comptes', { nbComptes: comptes.length })}</h2>
        <div class="actions"><button type="button" class="btn btn-primaire" id="acces-creer-compte">${UI.icone('ajouter')}${I18n.t('equipe.creer_compte.creer_compte')}</button></div></div>
      <p class="note">${I18n.t('equipe.comptes.chaque_personne_identifiant_prenom')}</p>
    </section>`);
    carte.appendChild(UI.tableau({
      libelle: I18n.t('equipe.comptes.comptes'),
      colonnes: [
        { cle: 'identifiant', libelle: I18n.t('equipe.comptes.identifiant'), rendu: (c) => UI.html`<b>${texte(c.identifiant)}</b>` },
        { cle: 'nom', libelle: I18n.t('equipe.comptes.personne'), valeurTri: (c) => texte(c.nom) + ' ' + texte(c.prenom),
          rendu: (c) => (texte(c.prenom) + ' ' + texte(c.nom)).trim() },
        { cle: 'role', libelle: I18n.t('equipe.champs_compte.role'), rendu: (c) => libelleRole(texte(c.role)) || texte(c.role) },
        { cle: 'technicien_id', libelle: I18n.t('equipe.champs_compte.technicien_lie'), rendu: (c) => nomDuTechnicien(c.technicien_id) },
        { cle: 'actif', libelle: I18n.t('equipe.comptes.etat'), triable: false, rendu: (c) => etatCompte(c) },
        { cle: 'actions', libelle: '', triable: false, rendu: (c) => actionsCompte(c, session, rafraichir) },
      ],
      lignes: comptes,
      triInitial: { cle: 'identifiant', sens: 'asc' },
      vide: I18n.t('equipe.comptes.aucun_compte_terminez_installation'),
    }));
    UI.$('#acces-creer-compte', carte).addEventListener('click', () => creerCompte(rafraichir));
    UI.remplir(panneau, carte);
  }

  // ===========================================================================================
  // 4. Appareils enrôlés et invitations
  // ===========================================================================================

  /** Invitation créée : QR et lien, montrés une seule fois (le jeton n'est écrit nulle part). */
  function montrerInvitation(resultat) {
    const invitation = resultat.invitation || {};
    const lien = lienInvitation(resultat.chemin);
    const contenu = UI.element(UI.html`<div class="form-colonne acces-invitation">
      <p>${I18n.html('equipe.montrer_invitation.telephone_scanne_qr_ouvre', { dateHeure: dateHeure(invitation.expire_le) })}</p>
      <div class="acces-qr"><div class="acces-qr-image" id="acces-invitation-qr"></div>
        <div class="acces-lien champ"><label for="acces-invitation-lien">${I18n.t('equipe.montrer_invitation.lien_invitation')}</label>
          <input type="text" id="acces-invitation-lien" readonly value="${lien}" spellcheck="false"></div></div>
      <p class="note">${I18n.t('equipe.montrer_invitation.qr_montre_fois_fermez')}</p>
    </div>`);
    UI.remplir(UI.$('#acces-invitation-qr', contenu), UI.qrSvg(lien, 220));
    return UI.fenetre({ titre: I18n.t('equipe.montrer_invitation.invitation_invitation_id', { invitationId: texte(invitation.id) }), classe: 'equipe-fenetre', contenu: contenu,
      boutons: [{ libelle: I18n.t('commun.bouton.fermer'), valeur: null, classe: 'btn-primaire', defaut: true }] });
  }

  async function creerInvitation(selecteur, bouton, rafraichir) {
    const heures = Number(selecteur.value) || DUREE_PAR_DEFAUT_H;
    await pendant(bouton, 'création d\'une invitation', async () => {
      const resultat = await api.creerInvitation(heures);
      await montrerInvitation(resultat);
      await rafraichir();
    });
  }

  function etatInvitation(invitation) {
    if (invitation.revoquee) return badge(I18n.t('equipe.etat_invitation.revoquee'), 'neutre', true);
    return invitation.valide ? badge(I18n.t('equipe.etat_invitation.valide'), 'ok') : badge(I18n.t('equipe.etat_invitation.expiree'), 'neutre');
  }

  function etatAppareil(appareil) {
    if (appareil.revoque) return badge(I18n.t('equipe.etat_appareil.revoque'), 'neutre', true);
    return appareil.valide ? badge(I18n.t('equipe.etat_compte.actif'), 'ok') : badge(I18n.t('equipe.etat_appareil.expire'), 'neutre');
  }

  function boutonRevoquer(genre, element, rafraichir) {
    if (!element.valide) return '';
    const bouton = UI.element(UI.html`<button type="button" class="btn btn-danger" data-revoquer="${genre}" data-id="${element.id}">${I18n.t('equipe.bouton_revoquer.revoquer')}</button>`);
    bouton.addEventListener('click', async () => {
      const nomAppareil = texte(element.nom_demandeur) || texte(element.libelle);
      const question = genre === 'invitation'
        ? I18n.t('equipe.bouton_revoquer.revoquer_invitation_plus_personne', { elementId: texte(element.id) })
        : I18n.t('equipe.bouton_revoquer.revoquer_appareil_perd_acces', { nomAppareil });
      if (!await UI.confirmer(question, { titre: I18n.t('equipe.bouton_revoquer.revoquer'), oui: I18n.t('equipe.bouton_revoquer.revoquer'), danger: true })) return;
      await pendant(bouton, 'révocation', async () => {
        await (genre === 'invitation' ? api.revoquerInvitation(element.id) : api.revoquerAppareil(element.id));
        UI.toast(genre === 'invitation' ? I18n.t('equipe.bouton_revoquer.invitation_revoquee') : I18n.t('equipe.bouton_revoquer.appareil_revoque'), 'succes');
        await rafraichir();
      });
    });
    return bouton;
  }

  async function revoquerTous(bouton, rafraichir) {
    const confirme = await UI.confirmer(I18n.t('equipe.revoquer_tous.revoquer_tous_appareils_enroles'), { titre: I18n.t('equipe.revoquer_tous.revoquer_tous_appareils'), oui: I18n.t('equipe.revoquer_tous.tout_revoquer'), danger: true });
    if (!confirme) return;
    await pendant(bouton, 'révocation de tous les appareils', async () => {
      const resultat = await api.revoquerTous();
      const nombre = Array.isArray(resultat.appareils_revoques) ? resultat.appareils_revoques.length : 0;
      UI.toast(nombre ? I18n.t('equipe.revoquer_tous.appareils_revoques', { n: nombre }) : I18n.t('equipe.revoquer_tous.aucun_appareil_revoquer'), 'succes');
      await rafraichir();
    });
  }

  async function afficherAppareils(panneau) {
    UI.remplir(panneau, UI.html`<p class="muted">${I18n.t('equipe.appareils.chargement_appareils')}</p>`);
    let donnees;
    try {
      donnees = await api.invitations();
    } catch (erreur) {
      UI.remplir(panneau, erreurHtml(erreur));
      return;
    }
    const invitations = Array.isArray(donnees.invitations) ? donnees.invitations : [];
    const appareils = Array.isArray(donnees.appareils) ? donnees.appareils : [];
    const actif = donnees.enrolement_actif !== false;
    const rafraichir = () => afficherAppareils(panneau);
    const zone = UI.element(UI.html`<div class="form-colonne" id="acces-appareils"></div>`);
    if (!actif) {
      zone.appendChild(UI.bandeau('info', UI.html`${I18n.html('equipe.appareils.enrolement_desactive_demandeurs_ont')}`));
    }
    const inviter = UI.element(UI.html`<section class="carte acces-carte" id="acces-inviter">
      <div class="entete-carte"><h2>${I18n.t('equipe.appareils.inviter_appareil')}</h2></div>
      <p>${I18n.html('equipe.appareils.invitation_donne_qr_lien')}</p>
      <div class="acces-inviter-ligne">
        <label class="champ"><span>${I18n.t('equipe.appareils.valable')}</span>
          <select id="acces-duree-invitation">${dureesInvitation().map((d) => UI.html`<option value="${String(d.heures)}" ${d.heures === DUREE_PAR_DEFAUT_H ? 'selected' : ''}>${d.libelle}</option>`)}</select></label>
        <button type="button" class="btn btn-primaire" id="acces-creer-invitation" ${actif ? '' : 'disabled'}>${UI.icone('qr')}${I18n.t('equipe.appareils.creer_invitation')}</button>
      </div>
    </section>`);
    UI.$('#acces-creer-invitation', inviter).addEventListener('click', (evenement) => {
      creerInvitation(UI.$('#acces-duree-invitation', inviter), evenement.currentTarget, rafraichir);
    });
    zone.appendChild(inviter);

    const carteInvitations = UI.element(UI.html`<section class="carte acces-carte" id="acces-invitations">
      <div class="entete-carte"><h2>${I18n.html('equipe.appareils.invitations_nb_invitations', { nbInvitations: invitations.length })}</h2></div></section>`);
    carteInvitations.appendChild(UI.tableau({
      libelle: I18n.t('equipe.appareils.invitations'),
      colonnes: [
        { cle: 'id', libelle: I18n.t('equipe.appareils.invitation'), rendu: (i) => UI.html`<b>${texte(i.id)}</b>` },
        { cle: 'cree_le', libelle: I18n.t('equipe.appareils.creee'), rendu: (i) => dateHeure(i.cree_le) },
        { cle: 'expire_le', libelle: I18n.t('equipe.appareils.expire'), rendu: (i) => dateHeure(i.expire_le) },
        { cle: 'valide', libelle: I18n.t('equipe.comptes.etat'), triable: false, rendu: (i) => etatInvitation(i) },
        { cle: 'actions', libelle: '', triable: false, rendu: (i) => boutonRevoquer('invitation', i, rafraichir) },
      ],
      lignes: invitations,
      triInitial: { cle: 'cree_le', sens: 'desc' },
      vide: I18n.t('equipe.appareils.aucune_invitation_instant'),
    }));
    zone.appendChild(carteInvitations);

    const valides = appareils.filter((a) => a.valide).length;
    const carteAppareils = UI.element(UI.html`<section class="carte acces-carte" id="acces-liste-appareils">
      <div class="entete-carte"><h2>${I18n.html('equipe.appareils.appareils_enroles_nb', { nbAppareils: appareils.length })}</h2>
        <div class="actions">${valides ? UI.html`<button type="button" class="btn btn-danger" id="acces-revoquer-tous">${I18n.t('equipe.revoquer_tous.revoquer_tous_appareils')}</button>` : ''}</div></div></section>`);
    carteAppareils.appendChild(UI.tableau({
      libelle: I18n.t('equipe.appareils.appareils_enroles'),
      colonnes: [
        { cle: 'nom_demandeur', libelle: I18n.t('equipe.comptes.personne'), rendu: (a) => UI.html`<b>${texte(a.nom_demandeur)}</b>` },
        { cle: 'libelle', libelle: I18n.t('equipe.appareils.appareil'), rendu: (a) => UI.html`${texte(a.libelle)} <span class="note">${texte(a.id)}</span>` },
        { cle: 'cree_le', libelle: I18n.t('equipe.appareils.enrole'), rendu: (a) => dateHeure(a.cree_le) },
        { cle: 'vu_le', libelle: I18n.t('equipe.appareils.derniere_activite'), rendu: (a) => dateHeure(a.vu_le) },
        { cle: 'valide', libelle: I18n.t('equipe.comptes.etat'), triable: false, rendu: (a) => etatAppareil(a) },
        { cle: 'actions', libelle: '', triable: false, rendu: (a) => boutonRevoquer('appareil', a, rafraichir) },
      ],
      lignes: appareils,
      triInitial: { cle: 'vu_le', sens: 'desc' },
      vide: I18n.t('equipe.appareils.aucun_appareil_enrole'),
    }));
    const tout = UI.$('#acces-revoquer-tous', carteAppareils);
    if (tout) tout.addEventListener('click', () => revoquerTous(tout, rafraichir));
    zone.appendChild(carteAppareils);
    UI.remplir(panneau, zone);
  }

  // ===========================================================================================
  // 5. Journal des connexions
  // ===========================================================================================

  /** Lignes d'un CSV « ; » (guillemets doublés acceptés) → tableaux de cellules, sans l'apostrophe de protection. */
  function lignesCsv(contenu) {
    const lignes = [];
    let ligne = [];
    let cellule = '';
    let entreGuillemets = false;
    const source = contenu.startsWith(MARQUE_ORDRE_OCTETS) ? contenu.slice(1) : contenu;
    for (let position = 0; position < source.length; position += 1) {
      const caractere = source[position];
      if (entreGuillemets) {
        if (caractere === '"' && source[position + 1] === '"') { cellule += '"'; position += 1; }
        else if (caractere === '"') entreGuillemets = false;
        else cellule += caractere;
      } else if (caractere === '"') {
        entreGuillemets = true;
      } else if (caractere === ';') {
        ligne.push(cellule); cellule = '';
      } else if (caractere === '\n' || caractere === '\r') {
        if (caractere === '\r' && source[position + 1] === '\n') position += 1;
        ligne.push(cellule); cellule = '';
        if (ligne.some((valeur) => valeur !== '')) lignes.push(ligne);
        ligne = [];
      } else {
        cellule += caractere;
      }
    }
    if (cellule !== '' || ligne.length) { ligne.push(cellule); if (ligne.some((valeur) => valeur !== '')) lignes.push(ligne); }
    return lignes.map((cellules) => cellules.map((valeur) => (valeur.startsWith('\'') ? valeur.slice(1) : valeur)));
  }

  function entreesJournal(contenu) {
    const lignes = lignesCsv(contenu);
    if (!lignes.length) return [];
    const entete = lignes[0].map((nom) => texte(nom).toLowerCase());
    return lignes.slice(1).map((cellules) => {
      const entree = {};
      entete.forEach((nom, position) => { entree[nom] = texte(cellules[position]); });
      return entree;
    });
  }

  function badgeResultat(resultat) {
    const cle = texte(resultat).toLowerCase();
    return badge(libelleResultat(cle) || texte(resultat), TONS_RESULTAT[cle] || 'neutre');
  }

  async function afficherJournal(panneau) {
    UI.remplir(panneau, UI.html`<p class="muted">${I18n.t('equipe.journal.chargement_journal')}</p>`);
    let contenu;
    try {
      contenu = await api.journal();
    } catch (erreur) {
      UI.remplir(panneau, erreurHtml(erreur));
      return;
    }
    const entrees = entreesJournal(contenu).reverse();
    const montrees = entrees.slice(0, LIGNES_JOURNAL_AFFICHEES);
    const carte = UI.element(UI.html`<section class="carte acces-carte" id="acces-journal">
      <div class="entete-carte"><h2>${I18n.html('equipe.journal.journal_connexions_nb', { nbEntrees: entrees.length })}</h2>
        <div class="actions"><button type="button" class="btn btn-secondaire" id="acces-exporter-journal">${UI.icone('export')}${I18n.t('equipe.journal.exporter_csv')}</button></div></div>
      <p class="note">${I18n.t('equipe.journal.connexions_echecs_blocages_comptes')} ${entrees.length > montrees.length
    ? I18n.t('equipe.journal.lignes_plus_recentes', { n: montrees.length }) : ''}</p>
    </section>`);
    carte.appendChild(UI.tableau({
      libelle: I18n.t('equipe.journal.journal_connexions'),
      colonnes: [
        { cle: 'date', libelle: I18n.t('commun.champ.date'), rendu: (l) => dateHeure(l.date) },
        { cle: 'qui', libelle: I18n.t('equipe.journal.qui') },
        { cle: 'resultat', libelle: I18n.t('equipe.journal.evenement'), rendu: (l) => badgeResultat(l.resultat) },
        { cle: 'adresse', libelle: I18n.t('equipe.journal.adresse'), rendu: (l) => UI.html`${texte(l.adresse)}${texte(l.tailscale) ? UI.html` <span class="note">${texte(l.tailscale)}</span>` : ''}` },
        { cle: 'agent', libelle: I18n.t('equipe.journal.navigateur'), triable: false, rendu: (l) => UI.html`<span class="acces-agent" title="${texte(l.agent)}">${texte(l.agent).slice(0, 60)}</span>` },
      ],
      lignes: montrees,
      triInitial: { cle: 'date', sens: 'desc' },
      vide: I18n.t('equipe.journal.aucune_connexion_enregistree_instant'),
    }));
    UI.$('#acces-exporter-journal', carte).addEventListener('click', () => {
      UI.telecharger(NOM_FICHIER_JOURNAL, contenu, 'text/csv;charset=utf-8');
    });
    UI.remplir(panneau, carte);
  }

  // ===========================================================================================
  // 6. Écran
  // ===========================================================================================

  async function afficher(conteneur, parametres) {
    App.definirTitre(I18n.t('equipe.ecran.acces'));
    UI.remplir(conteneur, UI.html`<div class="equipe equipe-acces">
      <div class="entete-page"><div><div class="fil">${I18n.html('equipe.ecran.equipe_acces')}</div>
        <h1>${I18n.t('equipe.ecran.acces')}</h1><p>${I18n.t('equipe.ecran.comptes_appareils_enroles_journal')}</p></div></div>
      <div id="acces-contenu"></div></div>`);
    const zone = UI.$('#acces-contenu', conteneur);
    if (App.mode !== 'serveur') {
      zone.appendChild(UI.bandeau('info', UI.html`${I18n.html('equipe.ecran.rien_gerer_ici_comptes')}`));
      return;
    }
    let session;
    try {
      session = await api.session();
    } catch (erreur) {
      zone.appendChild(erreurHtml(erreur));
      return;
    }
    if (!session.comptes) {
      zone.appendChild(UI.bandeau('info', UI.html`${I18n.html('equipe.ecran.comptes_sont_pas_actives')}`));
      return;
    }
    const requete = (parametres && parametres.requete) || new URLSearchParams();
    const demande = requete.get('onglet');
    // Chaque onglet relit le serveur à chaque ouverture (un autre poste, ou un téléphone qui vient de s'enrôler,
    // a pu changer les choses) ; la première ouverture est remplie par UI.onglets lui-même.
    const ouverts = new Set();
    const onglets = UI.onglets(zone, [
      { id: 'comptes', libelle: I18n.t('equipe.comptes.comptes'), afficher: (panneau) => afficherComptes(panneau, session) },
      { id: 'appareils', libelle: I18n.t('equipe.ecran.appareils'), afficher: (panneau) => afficherAppareils(panneau) },
      { id: 'journal', libelle: I18n.t('equipe.journal.journal_connexions'), afficher: (panneau) => afficherJournal(panneau) },
    ], { actif: ['comptes', 'appareils', 'journal'].includes(demande) ? demande : 'comptes',
      surChangement: (id) => { if (ouverts.has(id)) onglets.rafraichir(id); else ouverts.add(id); } });
  }

  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'equipe-acces', route: /^#\/equipe\/acces$/, parent: 'equipe',
      get titre() { return I18n.t('equipe.ecran.acces'); },
      profils: ['responsable'],
      tables: ['techniciens'],
      afficher: afficher,
    });
  });

  return { lignesCsv, entreesJournal, lienInvitation, api };
})();
