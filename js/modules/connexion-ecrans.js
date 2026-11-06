'use strict';
// Connexion : écran de connexion (#ecran-connexion de index.html ; ARCHITECTURE.md §22.4 « Écran de connexion » ;
// CDC D124, D125, D126 ; CS124), en mode serveur quand les comptes sont exigés. Trois panneaux, un seul visible :
//   - connexion : identifiant, mot de passe, « rester connecté sur cet appareil » (POST /api/connexion) ;
//   - enrôlement (page ouverte sur #/enroler/<jeton>, D125) : « Entrez votre nom » (POST /api/enroler) ; 403
//     (enrôlement désactivé) → le message et les champs de connexion classiques ;
//   - mot de passe (provisoire, a_changer) : actuel, nouveau, confirmation (POST /api/mot-de-passe), avant tout.
// App montre l'écran puis appelle Connexion.demander(options) ; la promesse rend la session (camelCase, comme
// adaptateur.session()) une fois la personne connectée ET son mot de passe choisi s'il était provisoire.
// Les appels à l'API d'accès sont faits ici par fetch avec l'en-tête X-Prevo ; le message du serveur est montré tel
// quel (401 « Identifiant ou mot de passe incorrect. », 403, 429 avec le temps restant : bouton désactivé le temps
// dit). Un mot de passe n'est jamais gardé : les champs sont vidés dès la réponse. Le nom du poste (prevo.poste)
// n'est plus demandé ici. Textes d'aide : AccesTextes (T169, une seule source).
// Dépendances : UI, AccesTextes ; aucune lecture de Donnees (les tables ne sont lues qu'après la connexion).
// Charte : css/modules/connexion.css.

const Connexion = (() => {

  const LONGUEUR_MIN_MOT_DE_PASSE = 12;        // règles du serveur (§22.3), affichées à l'écran
  const LONGUEUR_MAX_MOT_DE_PASSE = 256;
  const LONGUEUR_SOLIDE = 20;                   // au-delà : « solide » (phrase de passe)
  const ATTENTE_PAR_DEFAUT_S = 60;              // 429 sans temps lisible
  const MOTIF_ROUTE_ENROLER = /^#\/enroler\/([A-Za-z0-9_-]+)$/;
  const PANNEAUX = {
    connexion: 'connexion-formulaire',
    enrolement: 'connexion-enrolement',
    motDePasse: 'connexion-mot-de-passe-panneau',
  };
  /** Titre et sous-titre d'un panneau (connexion, enrolement, motDePasse) ; lus à l'affichage. */
  function titres(nom) {
    if (nom === 'enrolement') {
      return [I18n.t('connexion.titres.bienvenue'), I18n.t('connexion.titres.appareil_va_etre_reconnu')];
    }
    if (nom === 'motDePasse') {
      return [I18n.t('connexion.titres.choisissez_mot_passe'), I18n.t('connexion.titres.mot_passe_provisoire_faut')];
    }
    return [I18n.t('connexion.titres.connexion'), I18n.t('connexion.titres.chaque_personne_compte_serveur')];
  }
  // Messages de l'écran, lus à l'affichage.
  const messageServeurInjoignable = () => I18n.t('connexion.message_serveur_injoignable.serveur_prevo_repond_pas');
  const messageChampsConnexion = () => I18n.t('connexion.message_champs_connexion.indiquez_identifiant_mot_passe');
  const messageNom = () => I18n.t('connexion.message_nom.indiquez_nom_inscrit_demandes');
  const messageActuel = () => I18n.t('connexion.message_actuel.indiquez_mot_passe_actuel');
  const messageConfirmation = () => I18n.t('connexion.message_confirmation.confirmation_correspond_pas_nouveau');
  const messageIdentique = () => I18n.t('connexion.message_identique.choisissez_mot_passe_different');

  // --- État -------------------------------------------------------------------------------
  let resoudre = null;             // termine le Connexion.demander en cours (la session)
  let jetonInvitation = '';        // jeton de la route #/enroler/<jeton> pendant l'enrôlement
  let minuteurBlocage = null;      // compte à rebours d'un 429
  let ecouteursPoses = false;

  // ===========================================================================================
  // 1. Appels au serveur
  // ===========================================================================================

  /** POST JSON vers l'API d'accès → { statut, donnees, message } ; statut 0 et le message prévu si le serveur ne répond pas. */
  async function appeler(chemin, corps) {
    let reponse;
    try {
      reponse = await fetch(chemin, {
        method: 'POST', cache: 'no-store', credentials: 'same-origin',
        headers: { 'X-Prevo': '1', 'Content-Type': 'application/json; charset=utf-8' },
        body: JSON.stringify(corps || {}),
      });
    } catch (erreur) {
      return { statut: 0, donnees: null, message: messageServeurInjoignable(), attente: 0 };
    }
    const donnees = await reponse.json().catch(() => null);
    const message = donnees && typeof donnees.erreur === 'string' && donnees.erreur
      ? StockageServeur.texte(donnees, 'erreur') : I18n.t('commun.message.serveur_a_repondu', { status: reponse.status });
    // 429 : temps restant dans le corps (attente_secondes), sinon l'en-tête Retry-After, sinon une minute.
    let attente = donnees && typeof donnees.attente_secondes === 'number' ? donnees.attente_secondes : 0;
    if (!attente) attente = Number(reponse.headers.get('Retry-After')) || ATTENTE_PAR_DEFAUT_S;
    return { statut: reponse.status, donnees: donnees, message: reponse.ok ? '' : message, attente: attente };
  }

  /** Session de l'API (§22.4) en camelCase, comme adaptateur.session() de js/stockage-serveur.js. */
  function sessionLue(identite) {
    return {
      identifiant: String(identite.identifiant || ''), role: String(identite.role || ''),
      prenom: String(identite.prenom || ''), nom: String(identite.nom || ''),
      technicienId: String(identite.technicien_id || ''), aChanger: Boolean(identite.a_changer),
      appareil: Boolean(identite.appareil),
    };
  }

  // ===========================================================================================
  // 2. Panneaux, messages, blocage
  // ===========================================================================================

  function $(id) {
    return UI.$('#' + id);
  }

  function montrerPanneau(nom) {
    Object.keys(PANNEAUX).forEach((cle) => { $(PANNEAUX[cle]).hidden = cle !== nom; });
    const [titre, sousTitre] = titres(nom);
    $('connexion-titre').textContent = titre;
    $('connexion-sous-titre').textContent = sousTitre;
    const premier = UI.$('input', $(PANNEAUX[nom]));
    if (premier) premier.focus();
  }

  function montrerErreur(idZone, message) {
    const zone = $(idZone);
    zone.textContent = message || '';
    zone.hidden = !message;
  }

  function viderErreurs() {
    ['connexion-erreur', 'connexion-enrolement-erreur', 'connexion-mdp-erreur'].forEach((id) => montrerErreur(id, ''));
  }

  // Les mots de passe ne restent jamais dans la page : vidés à chaque réponse et à chaque ouverture de l'écran.
  function viderMotsDePasse() {
    ['connexion-mot-de-passe', 'connexion-actuel', 'connexion-nouveau', 'connexion-confirmation'].forEach((id) => { $(id).value = ''; });
    $('connexion-force').textContent = '';
  }

  // Bandeaux au-dessus des panneaux : appareil refusé (D125, 401 appareil_refuse), ou le motif du retour à l'écran
  // (session expirée pendant l'usage, message du serveur).
  function montrerAlertes(reglages) {
    const zone = $('connexion-alertes');
    zone.textContent = '';
    if (reglages.appareilRefuse) {
      const bandeau = UI.bandeau('important', UI.html`${I18n.html('connexion.montrer_alertes.appareil_plus_autorise_demandez')}`);
      bandeau.id = 'connexion-appareil-refuse';
      zone.appendChild(bandeau);
    } else if (reglages.message) {
      const bandeau = UI.bandeau('attention', reglages.message);
      bandeau.id = 'connexion-motif';
      zone.appendChild(bandeau);
    }
    zone.hidden = zone.children.length === 0;
  }

  // 429 : le bouton reste désactivé le temps dit par le serveur, avec un compte à rebours à la suite du message.
  function bloquer(bouton, idZone, message, secondes) {
    arreterBlocage();
    let reste = Math.max(1, Math.round(secondes));
    const zone = $(idZone);
    const afficher = () => {
      zone.textContent = message + ' ' + I18n.t('connexion.bloquer.nouvel_essai_possible', { n: reste });
      zone.hidden = false;
    };
    bouton.disabled = true;
    bouton.dataset.bloque = '1';
    afficher();
    minuteurBlocage = setInterval(() => {
      reste -= 1;
      if (reste > 0) { afficher(); return; }
      arreterBlocage();
      zone.textContent = message;
    }, 1000);
  }

  function arreterBlocage() {
    if (minuteurBlocage === null) return;
    clearInterval(minuteurBlocage);
    minuteurBlocage = null;
    UI.$$('#ecran-connexion [data-bloque]').forEach((bouton) => { delete bouton.dataset.bloque; bouton.disabled = false; });
  }

  /** Bouton occupé le temps d'une action (un seul envoi à la fois) ; un blocage posé par l'action le laisse désactivé. */
  async function pendant(bouton, action) {
    if (bouton.disabled) return;
    bouton.disabled = true;
    bouton.setAttribute('aria-busy', 'true');
    try {
      await action();
    } finally {
      bouton.removeAttribute('aria-busy');
      if (!bouton.dataset.bloque) bouton.disabled = false;
    }
  }

  // ===========================================================================================
  // 3. Les trois actions
  // ===========================================================================================

  async function seConnecter() {
    const champIdentifiant = $('connexion-identifiant');
    const champMotDePasse = $('connexion-mot-de-passe');
    const identifiant = champIdentifiant.value.trim();
    const motDePasse = champMotDePasse.value;
    if (!identifiant || !motDePasse) {
      montrerErreur('connexion-erreur', messageChampsConnexion());
      (identifiant ? champMotDePasse : champIdentifiant).focus();
      return;
    }
    montrerErreur('connexion-erreur', '');
    const reponse = await appeler('/api/connexion', { identifiant: identifiant, mot_de_passe: motDePasse,
      rester: $('connexion-rester').checked });
    champMotDePasse.value = '';
    if (reponse.statut === 200 && reponse.donnees && reponse.donnees.session) {
      poursuivre(sessionLue(reponse.donnees.session));
      return;
    }
    if (reponse.statut === 429) {
      bloquer($('connexion-valider'), 'connexion-erreur', reponse.message, reponse.attente);
      return;
    }
    montrerErreur('connexion-erreur', reponse.message);
    champMotDePasse.focus();
  }

  async function enroler() {
    const champNom = $('connexion-nom');
    const nom = champNom.value.trim().replace(/\s+/g, ' ');
    if (!nom) {
      montrerErreur('connexion-enrolement-erreur', messageNom());
      champNom.focus();
      return;
    }
    montrerErreur('connexion-enrolement-erreur', '');
    const reponse = await appeler('/api/enroler', { invitation: jetonInvitation, nom: nom });
    if (reponse.statut === 200 && reponse.donnees && reponse.donnees.session) {
      terminer(sessionLue(reponse.donnees.session));
      return;
    }
    if (reponse.statut === 403) {
      // Enrôlement désactivé (demandeurs_avec_compte) : chaque demandeur a un compte, les champs classiques.
      montrerPanneau('connexion');
      montrerErreur('connexion-erreur', reponse.message);
      return;
    }
    montrerErreur('connexion-enrolement-erreur', reponse.message);
    champNom.focus();
  }

  function problemeDuNouveau(actuel, nouveau, confirmation) {
    if (!actuel) return messageActuel();
    if (nouveau.length < LONGUEUR_MIN_MOT_DE_PASSE) {
      return I18n.t('connexion.nouveau_mot_de_passe.trop_court', { n: LONGUEUR_MIN_MOT_DE_PASSE, longueur: nouveau.length });
    }
    if (nouveau.length > LONGUEUR_MAX_MOT_DE_PASSE) return I18n.t('connexion.nouveau_mot_de_passe.trop_long', { n: LONGUEUR_MAX_MOT_DE_PASSE });
    if (nouveau === actuel) return messageIdentique();
    if (nouveau !== confirmation) return messageConfirmation();
    return '';
  }

  async function changerMotDePasse() {
    const actuel = $('connexion-actuel').value;
    const nouveau = $('connexion-nouveau').value;
    const confirmation = $('connexion-confirmation').value;
    const probleme = problemeDuNouveau(actuel, nouveau, confirmation);
    if (probleme) {
      montrerErreur('connexion-mdp-erreur', probleme);
      $(actuel ? (nouveau.length < LONGUEUR_MIN_MOT_DE_PASSE || nouveau === actuel ? 'connexion-nouveau' : 'connexion-confirmation') : 'connexion-actuel').focus();
      return;
    }
    montrerErreur('connexion-mdp-erreur', '');
    const reponse = await appeler('/api/mot-de-passe', { actuel: actuel, nouveau: nouveau });
    viderMotsDePasse();
    if (reponse.statut === 200 && reponse.donnees && reponse.donnees.session) {
      terminer(sessionLue(reponse.donnees.session));
      return;
    }
    if (reponse.statut === 429) {
      bloquer($('connexion-changer'), 'connexion-mdp-erreur', reponse.message, reponse.attente);
      return;
    }
    montrerErreur('connexion-mdp-erreur', reponse.message);
    $('connexion-actuel').focus();
  }

  // Indication de force, par la longueur seule (D124 : aucune règle de composition, phrase de passe conseillée).
  function indicationForce(valeur) {
    const longueur = valeur.length;
    if (!longueur) return '';
    if (longueur < LONGUEUR_MIN_MOT_DE_PASSE) return I18n.t('connexion.indication_force.trop_court', { n: longueur, minimum: LONGUEUR_MIN_MOT_DE_PASSE });
    if (longueur < LONGUEUR_SOLIDE) return I18n.t('connexion.indication_force.correct', { n: longueur });
    return I18n.t('connexion.indication_force.solide', { n: longueur });
  }

  // Session reçue : mot de passe provisoire → le choix du mot de passe d'abord ; sinon l'écran se termine.
  function poursuivre(session) {
    if (session.aChanger) {
      montrerAlertes({});
      montrerPanneau('motDePasse');
      return;
    }
    terminer(session);
  }

  function terminer(session) {
    arreterBlocage();
    viderMotsDePasse();
    viderErreurs();
    jetonInvitation = '';
    const fin = resoudre;
    resoudre = null;
    if (fin) fin(session);
  }

  // Mot de passe provisoire mais pas la bonne personne : la session est fermée, retour aux champs de connexion.
  async function abandonnerProvisoire() {
    try {
      await deconnecter();
    } catch (erreur) {
      montrerErreur('connexion-mdp-erreur', (erreur && erreur.message) || String(erreur));
      return;
    }
    viderMotsDePasse();
    viderErreurs();
    montrerPanneau('connexion');
  }

  // ===========================================================================================
  // 4. Écouteurs (posés une seule fois) et entrée du module
  // ===========================================================================================

  function poserEcouteurs() {
    if (ecouteursPoses) return;
    ecouteursPoses = true;
    const aide = typeof AccesTextes !== 'undefined' && AccesTextes.options && AccesTextes.options.session_longue_jours;
    if (aide && aide.aide) $('connexion-rester-aide').textContent = aide.aide;
    $('connexion-formulaire').addEventListener('submit', (evenement) => {
      evenement.preventDefault();
      pendant($('connexion-valider'), seConnecter);
    });
    $('connexion-enrolement').addEventListener('submit', (evenement) => {
      evenement.preventDefault();
      pendant($('connexion-enroler'), enroler);
    });
    $('connexion-mot-de-passe-panneau').addEventListener('submit', (evenement) => {
      evenement.preventDefault();
      pendant($('connexion-changer'), changerMotDePasse);
    });
    $('connexion-avec-compte').addEventListener('click', () => { viderErreurs(); montrerPanneau('connexion'); });
    $('connexion-mdp-deconnexion').addEventListener('click', () => pendant($('connexion-mdp-deconnexion'), abandonnerProvisoire));
    $('connexion-nouveau').addEventListener('input', () => { $('connexion-force').textContent = indicationForce($('connexion-nouveau').value); });
    // Une saisie efface le message d'erreur du panneau (pas un blocage en cours : son compte à rebours reste).
    [['connexion-formulaire', 'connexion-erreur'], ['connexion-enrolement', 'connexion-enrolement-erreur'],
      ['connexion-mot-de-passe-panneau', 'connexion-mdp-erreur']].forEach(([idPanneau, idZone]) => {
      $(idPanneau).addEventListener('input', () => { if (minuteurBlocage === null) montrerErreur(idZone, ''); });
    });
  }

  /** Jeton d'une route #/enroler/<jeton> ('' sinon). */
  function jetonDeLaRoute(hash) {
    const trouve = MOTIF_ROUTE_ENROLER.exec(hash || '');
    return trouve ? trouve[1] : '';
  }

  function estRouteEnrolement(hash) {
    return jetonDeLaRoute(hash) !== '';
  }

  /**
   * Conduit l'écran (déjà montré par App) jusqu'à une session utilisable. Promesse : la session (camelCase).
   * options : { sessionProvisoire } (session ouverte mais mot de passe à changer : le panneau du mot de passe
   * d'abord), { appareilRefuse } (bandeau D125), { message } (motif du retour à l'écran, ex. session expirée).
   * Sans session, la page ouverte sur #/enroler/<jeton> montre le panneau d'enrôlement, sinon la connexion.
   */
  function demander(options) {
    const reglages = options || {};
    poserEcouteurs();
    arreterBlocage();
    viderMotsDePasse();
    viderErreurs();
    montrerAlertes(reglages);
    if (reglages.sessionProvisoire) {
      montrerPanneau('motDePasse');
    } else {
      jetonInvitation = jetonDeLaRoute(location.hash);
      montrerPanneau(jetonInvitation ? 'enrolement' : 'connexion');
    }
    return new Promise((fin) => { resoudre = fin; });
  }

  /** POST /api/deconnexion : la session du navigateur est fermée (une session déjà absente, 401, ne gêne pas). */
  async function deconnecter() {
    const reponse = await appeler('/api/deconnexion', {});
    if (reponse.statut !== 200 && reponse.statut !== 401) throw new Error(reponse.message);
  }

  return {
    demander,
    deconnecter,
    jetonDeLaRoute,
    estRouteEnrolement,
    sessionLue,
    LONGUEUR_MIN_MOT_DE_PASSE,
    LONGUEUR_MAX_MOT_DE_PASSE,
  };
})();
