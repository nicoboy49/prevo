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

  const ROLES = [
    { valeur: 'responsable', libelle: 'Responsable' },
    { valeur: 'technicien', libelle: 'Technicien' },
    { valeur: 'demandeur', libelle: 'Demandeur' },
  ];
  const LIBELLES_ROLE = { responsable: 'Responsable', technicien: 'Technicien', demandeur: 'Demandeur' };
  const DUREES_INVITATION = [
    { heures: 1, libelle: '1 heure' },
    { heures: 24, libelle: '24 heures' },
    { heures: 72, libelle: '3 jours' },
    { heures: 168, libelle: '7 jours' },
  ];
  const DUREE_PAR_DEFAUT_H = 24;
  const LIGNES_JOURNAL_AFFICHEES = 300;
  const LIBELLES_RESULTAT = {
    connexion: 'Connexion', echec: 'Échec', bloque: 'Bloqué', deconnexion: 'Déconnexion', appareil: 'Appareil enrôlé',
    invitation: 'Invitation', revocation: 'Révocation', reinitialisation: 'Réinitialisation', creation: 'Compte créé',
    modification: 'Compte modifié',
  };
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
      throw new Donnees.ErreurStockage('Le serveur Prévo ne répond pas.', erreur);
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
    return 'Le serveur a répondu « ' + statut + ' ».';
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

  function badge(libelle, ton) {
    return UI.html`<span class="badge ${ton || 'neutre'}">${libelle}</span>`;
  }

  function nomDuTechnicien(id) {
    const technicien = texte(id) ? Donnees.trouver('techniciens', texte(id)) : null;
    if (!technicien) return texte(id);
    return (texte(technicien.prenom) + ' ' + texte(technicien.nom)).trim() || texte(id);
  }

  function erreurHtml(erreur) {
    return UI.bandeau('important', UI.html`<b>Lecture impossible :</b> ${(erreur && erreur.message) || 'erreur inconnue'}`);
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
    return [
      UI.champ(definition('prenom', 'texte', 'Prénom', { obligatoire: true }), valeur('prenom'), { attributs: { maxlength: '60' } }),
      UI.champ(definition('nom', 'texte', 'Nom'), valeur('nom'), { attributs: { maxlength: '60' } }),
      UI.champ(definition('role', 'choix', 'Rôle', { valeurs: ROLES.map((r) => r.valeur), obligatoire: true }),
        valeur('role') || 'demandeur',
        { aide: 'Responsable : tout, réglages compris. Technicien : les interventions, sans taux horaire ni prix. Demandeur : signaler et suivre ses demandes.' }),
      UI.champ(definition('technicien_id', 'ref', 'Technicien lié'), valeur('technicien_id'),
        { liste: listeTechniciens(), aide: 'Pour un compte technicien : sa fiche dans Équipe (temps passé, planning).' }),
    ];
  }

  function verifierCompte(valeurs) {
    const erreurs = [];
    if (!texte(valeurs.prenom)) erreurs.push({ nom: 'prenom', message: 'Le prénom est obligatoire.' });
    if (!LIBELLES_ROLE[texte(valeurs.role)]) erreurs.push({ nom: 'role', message: 'Choisissez un rôle.' });
    if (texte(valeurs.role) === 'technicien' && !texte(valeurs.technicien_id)) {
      erreurs.push({ nom: 'technicien_id', message: 'Un compte technicien est lié à une fiche de technicien.' });
    }
    if (texte(valeurs.role) !== 'technicien' && texte(valeurs.technicien_id)) {
      erreurs.push({ nom: 'technicien_id', message: 'Seul un compte technicien est lié à une fiche de technicien.' });
    }
    return erreurs;
  }

  function champsEnvoyes(valeurs) {
    return { prenom: texte(valeurs.prenom), nom: texte(valeurs.nom), role: texte(valeurs.role),
      technicien_id: texte(valeurs.technicien_id) };
  }

  /** Mot de passe provisoire montré une seule fois : à noter et à remettre en main propre. */
  function montrerMotDePasseProvisoire(compte, motDePasse, titre) {
    return UI.fenetre({
      titre: titre,
      classe: 'equipe-fenetre',
      contenu: UI.html`<div class="form-colonne acces-provisoire">
        <p>Compte <b>${texte(compte.identifiant)}</b> (${LIBELLES_ROLE[texte(compte.role)] || texte(compte.role)}).</p>
        <p>Mot de passe provisoire, montré <b>une seule fois</b> :</p>
        <div class="champ"><input type="text" class="acces-mot-de-passe" id="acces-mot-de-passe-provisoire" readonly
          value="${motDePasse}" aria-label="Mot de passe provisoire" spellcheck="false"></div>
        <p class="note">Notez-le et donnez-le en main propre : il devra être changé à la première connexion. Prévo ne
          l'écrit nulle part ; perdu, il se réinitialise d'ici (« Réinitialiser »).</p>
      </div>`,
      boutons: [{ libelle: 'J\'ai noté le mot de passe', valeur: 'ok', classe: 'btn-primaire', defaut: true }],
    });
  }

  async function creerCompte(rafraichir) {
    let resultat = null;
    const cree = await UI.fenetreAction({
      titre: 'Créer un compte',
      introduction: 'L\'identifiant (prénom.nom) est donné par Prévo. Le mot de passe provisoire s\'affiche ensuite, une seule fois.',
      champs: champsCompte(null),
      libelleValider: 'Créer le compte',
      verifier: verifierCompte,
      action: async (valeurs) => { resultat = await api.creerCompte(champsEnvoyes(valeurs)); },
    });
    if (!cree || !resultat) return;
    App.marquerSaisie(false);
    await montrerMotDePasseProvisoire(resultat.compte || {}, texte(resultat.mot_de_passe_provisoire), 'Compte créé');
    UI.toast('Compte créé.', 'succes');
    await rafraichir();
  }

  async function modifierCompte(compte, rafraichir) {
    const fait = await UI.fenetreAction({
      titre: 'Modifier le compte ' + texte(compte.identifiant),
      champs: champsCompte(compte),
      libelleValider: 'Enregistrer',
      verifier: verifierCompte,
      action: async (valeurs) => { await api.changerCompte(compte.identifiant, 'modifier', champsEnvoyes(valeurs)); },
    });
    if (!fait) return;
    UI.toast('Compte enregistré. Un rôle changé vaut dès la prochaine requête de la personne.', 'succes');
    await rafraichir();
  }

  async function reinitialiserCompte(compte, bouton, rafraichir) {
    const confirme = await UI.confirmer('Réinitialiser le mot de passe de ' + texte(compte.identifiant) + ' ? Ses sessions ouvertes '
      + 'seront fermées ; un mot de passe provisoire s\'affichera une seule fois.', { titre: 'Réinitialiser le mot de passe', oui: 'Réinitialiser' });
    if (!confirme) return;
    await pendant(bouton, 'réinitialisation du mot de passe', async () => {
      const resultat = await api.changerCompte(compte.identifiant, 'reinitialiser');
      await montrerMotDePasseProvisoire(resultat.compte || compte, texte(resultat.mot_de_passe_provisoire), 'Mot de passe réinitialisé');
      await rafraichir();
    });
  }

  async function changerActivation(compte, bouton, rafraichir) {
    const desactiver = texte(compte.actif) !== '0' && compte.actif !== false;
    if (desactiver) {
      const confirme = await UI.confirmer('Désactiver ' + texte(compte.identifiant) + ' ? La personne ne pourra plus se connecter et ses '
        + 'sessions ouvertes seront fermées ; le compte peut être réactivé plus tard.',
      { titre: 'Désactiver le compte', oui: 'Désactiver', danger: true });
      if (!confirme) return;
    }
    await pendant(bouton, desactiver ? 'désactivation du compte' : 'activation du compte', async () => {
      await api.changerCompte(compte.identifiant, desactiver ? 'desactiver' : 'activer');
      UI.toast(desactiver ? 'Compte désactivé.' : 'Compte activé.', 'succes');
      await rafraichir();
    });
  }

  function actionsCompte(compte, session, rafraichir) {
    const soiMeme = session && session.session && session.session.identifiant === compte.identifiant;
    const actif = compte.actif !== false && texte(compte.actif) !== '0';
    const groupe = UI.element(UI.html`<span class="acces-actions" data-compte="${compte.identifiant}">
      <button type="button" class="btn btn-secondaire" data-action="modifier">Modifier…</button>
      <button type="button" class="btn btn-secondaire" data-action="reinitialiser">Réinitialiser…</button>
      ${soiMeme ? '' : UI.html`<button type="button" class="btn ${actif ? 'btn-danger' : 'btn-secondaire'}" data-action="${actif ? 'desactiver' : 'activer'}">${actif ? 'Désactiver' : 'Activer'}</button>`}
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
    const morceaux = [badge(actif ? 'Actif' : 'Désactivé', actif ? 'ok' : 'neutre barre')];
    if (compte.a_changer) morceaux.push(badge('Mot de passe provisoire', 'attention'));
    return UI.html`<span class="equipe-statut">${morceaux}</span>`;
  }

  async function afficherComptes(panneau, session) {
    UI.remplir(panneau, UI.html`<p class="muted">Chargement des comptes…</p>`);
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
      <div class="entete-carte"><h2>Comptes <span class="acces-compteur">(${comptes.length})</span></h2>
        <div class="actions"><button type="button" class="btn btn-primaire" id="acces-creer-compte">${UI.icone('ajouter')}Créer un compte</button></div></div>
      <p class="note">Chaque personne a son identifiant (prénom.nom) et son rôle. Un compte créé ou réinitialisé reçoit un mot
        de passe provisoire, montré une seule fois, à changer à la première connexion. Il reste toujours au moins un
        responsable actif.</p>
    </section>`);
    carte.appendChild(UI.tableau({
      libelle: 'Comptes',
      colonnes: [
        { cle: 'identifiant', libelle: 'Identifiant', rendu: (c) => UI.html`<b>${texte(c.identifiant)}</b>` },
        { cle: 'nom', libelle: 'Personne', valeurTri: (c) => texte(c.nom) + ' ' + texte(c.prenom),
          rendu: (c) => (texte(c.prenom) + ' ' + texte(c.nom)).trim() },
        { cle: 'role', libelle: 'Rôle', rendu: (c) => LIBELLES_ROLE[texte(c.role)] || texte(c.role) },
        { cle: 'technicien_id', libelle: 'Technicien lié', rendu: (c) => nomDuTechnicien(c.technicien_id) },
        { cle: 'actif', libelle: 'État', triable: false, rendu: (c) => etatCompte(c) },
        { cle: 'actions', libelle: '', triable: false, rendu: (c) => actionsCompte(c, session, rafraichir) },
      ],
      lignes: comptes,
      triInitial: { cle: 'identifiant', sens: 'asc' },
      vide: 'Aucun compte : terminez l\'installation (l\'assistant crée le premier responsable).',
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
      <p>Le téléphone scanne ce QR (ou ouvre le lien), donne le nom de la personne et devient un appareil
        <b>Demandeur</b>, sans mot de passe. Valable jusqu'au <b>${dateHeure(invitation.expire_le)}</b>, pour autant
        d'appareils que nécessaire, révocable à tout moment.</p>
      <div class="acces-qr"><div class="acces-qr-image" id="acces-invitation-qr"></div>
        <div class="acces-lien champ"><label for="acces-invitation-lien">Lien de l'invitation</label>
          <input type="text" id="acces-invitation-lien" readonly value="${lien}" spellcheck="false"></div></div>
      <p class="note">Ce QR n'est montré qu'une fois : fermez cette fenêtre quand les téléphones sont enrôlés, ou créez
        une autre invitation plus tard.</p>
    </div>`);
    UI.remplir(UI.$('#acces-invitation-qr', contenu), UI.qrSvg(lien, 220));
    return UI.fenetre({ titre: 'Invitation ' + texte(invitation.id), classe: 'equipe-fenetre', contenu: contenu,
      boutons: [{ libelle: 'Fermer', valeur: null, classe: 'btn-primaire', defaut: true }] });
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
    if (invitation.revoquee) return badge('Révoquée', 'neutre barre');
    return invitation.valide ? badge('Valide', 'ok') : badge('Expirée', 'neutre');
  }

  function etatAppareil(appareil) {
    if (appareil.revoque) return badge('Révoqué', 'neutre barre');
    return appareil.valide ? badge('Actif', 'ok') : badge('Expiré', 'neutre');
  }

  function boutonRevoquer(genre, element, rafraichir) {
    if (!element.valide) return '';
    const bouton = UI.element(UI.html`<button type="button" class="btn btn-danger" data-revoquer="${genre}" data-id="${element.id}">Révoquer</button>`);
    bouton.addEventListener('click', async () => {
      const question = genre === 'invitation'
        ? 'Révoquer l\'invitation ' + texte(element.id) + ' ? Plus personne ne pourra s\'enrôler avec ; les appareils déjà enrôlés restent.'
        : 'Révoquer l\'appareil « ' + (texte(element.nom_demandeur) || texte(element.libelle)) + ' » ? Il perd l\'accès immédiatement et devra être enrôlé à nouveau.';
      if (!await UI.confirmer(question, { titre: 'Révoquer', oui: 'Révoquer', danger: true })) return;
      await pendant(bouton, 'révocation', async () => {
        await (genre === 'invitation' ? api.revoquerInvitation(element.id) : api.revoquerAppareil(element.id));
        UI.toast(genre === 'invitation' ? 'Invitation révoquée.' : 'Appareil révoqué.', 'succes');
        await rafraichir();
      });
    });
    return bouton;
  }

  async function revoquerTous(bouton, rafraichir) {
    const confirme = await UI.confirmer('Révoquer tous les appareils enrôlés ? Chacun perd l\'accès immédiatement ; les comptes et '
      + 'les invitations ne sont pas touchés.', { titre: 'Révoquer tous les appareils', oui: 'Tout révoquer', danger: true });
    if (!confirme) return;
    await pendant(bouton, 'révocation de tous les appareils', async () => {
      const resultat = await api.revoquerTous();
      const nombre = Array.isArray(resultat.appareils_revoques) ? resultat.appareils_revoques.length : 0;
      UI.toast(nombre ? nombre + ' appareil' + (nombre > 1 ? 's révoqués' : ' révoqué') + '.' : 'Aucun appareil à révoquer.', 'succes');
      await rafraichir();
    });
  }

  async function afficherAppareils(panneau) {
    UI.remplir(panneau, UI.html`<p class="muted">Chargement des appareils…</p>`);
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
      zone.appendChild(UI.bandeau('info', UI.html`<b>Enrôlement désactivé :</b> les demandeurs ont un compte sur ce serveur
        (réglage « demandeurs avec compte »). Les appareils déjà enrôlés ne sont plus reconnus.`));
    }
    const inviter = UI.element(UI.html`<section class="carte acces-carte" id="acces-inviter">
      <div class="entete-carte"><h2>Inviter un appareil</h2></div>
      <p>Une invitation donne un QR et un lien : le téléphone qui l'ouvre devient un appareil <b>Demandeur</b> (signaler,
        suivre ses demandes, consulter le parc), sans mot de passe, pendant un an d'activité.</p>
      <div class="acces-inviter-ligne">
        <label class="champ"><span>Valable</span>
          <select id="acces-duree-invitation">${DUREES_INVITATION.map((d) => UI.html`<option value="${String(d.heures)}" ${d.heures === DUREE_PAR_DEFAUT_H ? 'selected' : ''}>${d.libelle}</option>`)}</select></label>
        <button type="button" class="btn btn-primaire" id="acces-creer-invitation" ${actif ? '' : 'disabled'}>${UI.icone('qr')}Créer une invitation</button>
      </div>
    </section>`);
    UI.$('#acces-creer-invitation', inviter).addEventListener('click', (evenement) => {
      creerInvitation(UI.$('#acces-duree-invitation', inviter), evenement.currentTarget, rafraichir);
    });
    zone.appendChild(inviter);

    const carteInvitations = UI.element(UI.html`<section class="carte acces-carte" id="acces-invitations">
      <div class="entete-carte"><h2>Invitations <span class="acces-compteur">(${invitations.length})</span></h2></div></section>`);
    carteInvitations.appendChild(UI.tableau({
      libelle: 'Invitations',
      colonnes: [
        { cle: 'id', libelle: 'Invitation', rendu: (i) => UI.html`<b>${texte(i.id)}</b>` },
        { cle: 'cree_le', libelle: 'Créée le', rendu: (i) => dateHeure(i.cree_le) },
        { cle: 'expire_le', libelle: 'Expire le', rendu: (i) => dateHeure(i.expire_le) },
        { cle: 'valide', libelle: 'État', triable: false, rendu: (i) => etatInvitation(i) },
        { cle: 'actions', libelle: '', triable: false, rendu: (i) => boutonRevoquer('invitation', i, rafraichir) },
      ],
      lignes: invitations,
      triInitial: { cle: 'cree_le', sens: 'desc' },
      vide: 'Aucune invitation pour l\'instant.',
    }));
    zone.appendChild(carteInvitations);

    const valides = appareils.filter((a) => a.valide).length;
    const carteAppareils = UI.element(UI.html`<section class="carte acces-carte" id="acces-liste-appareils">
      <div class="entete-carte"><h2>Appareils enrôlés <span class="acces-compteur">(${appareils.length})</span></h2>
        <div class="actions">${valides ? UI.html`<button type="button" class="btn btn-danger" id="acces-revoquer-tous">Révoquer tous les appareils</button>` : ''}</div></div></section>`);
    carteAppareils.appendChild(UI.tableau({
      libelle: 'Appareils enrôlés',
      colonnes: [
        { cle: 'nom_demandeur', libelle: 'Personne', rendu: (a) => UI.html`<b>${texte(a.nom_demandeur)}</b>` },
        { cle: 'libelle', libelle: 'Appareil', rendu: (a) => UI.html`${texte(a.libelle)} <span class="note">${texte(a.id)}</span>` },
        { cle: 'cree_le', libelle: 'Enrôlé le', rendu: (a) => dateHeure(a.cree_le) },
        { cle: 'vu_le', libelle: 'Dernière activité', rendu: (a) => dateHeure(a.vu_le) },
        { cle: 'valide', libelle: 'État', triable: false, rendu: (a) => etatAppareil(a) },
        { cle: 'actions', libelle: '', triable: false, rendu: (a) => boutonRevoquer('appareil', a, rafraichir) },
      ],
      lignes: appareils,
      triInitial: { cle: 'vu_le', sens: 'desc' },
      vide: 'Aucun appareil enrôlé.',
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
    return badge(LIBELLES_RESULTAT[cle] || texte(resultat), TONS_RESULTAT[cle] || 'neutre');
  }

  async function afficherJournal(panneau) {
    UI.remplir(panneau, UI.html`<p class="muted">Chargement du journal…</p>`);
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
      <div class="entete-carte"><h2>Journal des connexions <span class="acces-compteur">(${entrees.length})</span></h2>
        <div class="actions"><button type="button" class="btn btn-secondaire" id="acces-exporter-journal">${UI.icone('export')}Exporter (CSV)</button></div></div>
      <p class="note">Connexions, échecs, blocages, comptes et appareils, avec l'adresse et le navigateur ; un an gardé
        sur le PC serveur, jamais un mot de passe. ${entrees.length > montrees.length
    ? UI.html`Les ${String(montrees.length)} lignes les plus récentes sont affichées ; l'export les contient toutes.` : ''}</p>
    </section>`);
    carte.appendChild(UI.tableau({
      libelle: 'Journal des connexions',
      colonnes: [
        { cle: 'date', libelle: 'Date', rendu: (l) => dateHeure(l.date) },
        { cle: 'qui', libelle: 'Qui' },
        { cle: 'resultat', libelle: 'Événement', rendu: (l) => badgeResultat(l.resultat) },
        { cle: 'adresse', libelle: 'Adresse', rendu: (l) => UI.html`${texte(l.adresse)}${texte(l.tailscale) ? UI.html` <span class="note">${texte(l.tailscale)}</span>` : ''}` },
        { cle: 'agent', libelle: 'Navigateur', triable: false, rendu: (l) => UI.html`<span class="acces-agent" title="${texte(l.agent)}">${texte(l.agent).slice(0, 60)}</span>` },
      ],
      lignes: montrees,
      triInitial: { cle: 'date', sens: 'desc' },
      vide: 'Aucune connexion enregistrée pour l\'instant.',
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
    App.definirTitre('Accès');
    UI.remplir(conteneur, UI.html`<div class="equipe equipe-acces">
      <div class="entete-page"><div><div class="fil"><a href="#/equipe">Équipe</a> <span aria-hidden="true">›</span> <span>Accès</span></div>
        <h1>Accès</h1><p>Comptes, appareils enrôlés et journal des connexions du PC serveur.</p></div></div>
      <div id="acces-contenu"></div></div>`);
    const zone = UI.$('#acces-contenu', conteneur);
    if (App.mode !== 'serveur') {
      zone.appendChild(UI.bandeau('info', UI.html`<b>Rien à gérer ici :</b> les comptes et les appareils n'existent qu'avec le
        serveur Prévo (mode serveur). En mode dossier ou démo, le profil se choisit à l'ouverture.`));
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
      zone.appendChild(UI.bandeau('info', UI.html`<b>Les comptes ne sont pas activés sur ce serveur</b> (portée « ce PC » : Prévo
        n'est joignable que depuis ce PC, sans mot de passe). L'assistant d'installation les active quand Prévo s'ouvre au réseau.`));
      return;
    }
    const requete = (parametres && parametres.requete) || new URLSearchParams();
    const demande = requete.get('onglet');
    // Chaque onglet relit le serveur à chaque ouverture (un autre poste, ou un téléphone qui vient de s'enrôler,
    // a pu changer les choses) ; la première ouverture est remplie par UI.onglets lui-même.
    const ouverts = new Set();
    const onglets = UI.onglets(zone, [
      { id: 'comptes', libelle: 'Comptes', afficher: (panneau) => afficherComptes(panneau, session) },
      { id: 'appareils', libelle: 'Appareils', afficher: (panneau) => afficherAppareils(panneau) },
      { id: 'journal', libelle: 'Journal des connexions', afficher: (panneau) => afficherJournal(panneau) },
    ], { actif: ['comptes', 'appareils', 'journal'].includes(demande) ? demande : 'comptes',
      surChangement: (id) => { if (ouverts.has(id)) onglets.rafraichir(id); else ouverts.add(id); } });
  }

  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'equipe-acces', route: /^#\/equipe\/acces$/, titre: 'Accès', parent: 'equipe',
      profils: ['responsable'],
      tables: ['techniciens'],
      afficher: afficher,
    });
  });

  return { lignesCsv, entreesJournal, lienInvitation, api };
})();
