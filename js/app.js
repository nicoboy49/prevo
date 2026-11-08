'use strict';
// App : démarrage de Prévo, choix du mode de stockage, profils, navigation (ARCHITECTURE.md §8).
//
// Déroulé du démarrage :
//   1. page servie en http(s) et serveur Prévo qui répond → mode serveur ;
//      sinon écran de démarrage : dossier (File System Access), dossier précédent, démo, CSV déposés ;
//      version web (VERSION_WEB, démo en ligne) : pas de serveur cherché, la démo seule et
//      « Télécharger Prévo » ;
//   2. chargement des 23 tables ; dossier : sauvegarde « avant-mise-a-jour » si la version de Prévo notée dans le
//      dossier n'est pas celle-ci (D170, sauf lecture seule) ; base vide (serveur ou dossier) → « Partir des données de démo »
//      ou « Créer une base vide » ; puis format des fichiers, avant toute autre écriture (D168, D169) :
//      dossier et démo → passage au format courant par le navigateur (sauvegarde « avant-format-vN »
//      d'abord) ; serveur → le navigateur ne migre pas (le serveur le fait à son démarrage), bandeau au
//      responsable si la base n'est pas au format courant ; données d'une version plus récente → lecture
//      seule (rien n'est écrit : ni passage, ni verrou, ni OT préventifs ; bandeau permanent) ;
//   3. profil (mémorisé sur le poste) ; la route demandée avant (QR scanné) est gardée ;
//      mode serveur avec les comptes exigés (lot 7, D126, §22.4) : GET /api/session AVANT la lecture des tables ;
//      sans session → écran de connexion (Connexion, js/modules/connexion-ecrans.js) ; le profil est déduit de la
//      session (rôle → type, prénom et nom, technicien lié), jamais l'écran de profil, jamais mémorisé ;
//   4. technicien ou responsable : génération des OT préventifs échus (RG5) → marque prevo:preventif ;
//   5. coque (menu, barre du bas, bandeaux) et premier écran → <html data-etat="pret">.
//   Assistant d'installation (lot 7, §22.10, T168) : page ouverte sur #/installation, servie par le serveur depuis le
//   PC serveur (127.0.0.1 ou localhost) et /api/info qui rend installation_a_faire → l'écran plein #ecran-installation
//   (Installation, js/modules/installation-ecrans.js) avant toute lecture de table ; jamais imposé sur une autre
//   route (les tests des lots 1 à 6 démarrent sans configuration) ; depuis le réseau, rien. L'assistant quitté sans
//   terminer → démarrage normal sur l'accueil ; terminé → le serveur se relance et la page se recharge.
// États lus par les tests : data-etat = 'chargement' | 'demarrage' | 'profil' | 'connexion' | 'installation' | 'pret'.
//
// Contrat des écrans (les modules de js/modules/ appellent App.ecran) :
//   App.ecran({
//     id: 'liste-di', route: /^#\/di$/, titre: 'Demandes',
//     menu: { libelle: 'Demandes', court: 'Demandes', icone: 'demandes', ordre: 20, groupe: '…', lien: '#/di' },
//     profils: ['demandeur', 'technicien', 'responsable'],
//     tables: ['demandes', 'equipements'],     // réaffiché si une de ces tables change sur un autre poste
//     parent: 'parc',                          // facultatif : entrée de menu à allumer (sinon la sienne)
//     afficher(conteneur, parametres) { … },   // peut être async
//   });
//   - conteneur : <main id="contenu">, vidé avant chaque affichage ;
//   - parametres : groupes nommés de la route (ex. (?<id>[^/]+) → parametres.id), `groupes` (tous les
//     groupes, dans l'ordre), `requete` (URLSearchParams de la partie après « ? » du hash), `chemin` ;
//   - les routes sont essayées dans l'ordre d'enregistrement : la première qui correspond gagne ;
//   - js/app.js est chargé APRÈS les modules : un module enregistre ses écrans dans un écouteur
//     DOMContentLoaded (App existe alors) ; App démarre ensuite (son écouteur est ajouté en dernier) ;
//   - saisie en cours : tout événement input/change dans #contenu la signale (sauf dans un élément
//     [data-hors-saisie], ex. un champ de filtre) ; App.marquerSaisie(false) l'efface (après un
//     enregistrement) ; un réaffichage l'efface aussi ;
//   - le module lit App.adaptateur, App.profil ({ type, nom, technicienId }), App.mode, App.poste ;
//     App.modeSolo() (mode_solo = 1 et profil responsable, D132) et App.technicienSolo() (technicien « moi »).
// Règles : pas de crypto ni de presse-papiers (contexte non sécurisé), pas d'alert/confirm/prompt,
// console.warn pour une erreur gérée (jamais console.error).

const App = (() => {

  const VERSION = '2.0.0';
  const DATE_VERSION = '2026-11-08';
  // Version web (démo en ligne, docs/DEPLOIEMENT_DEMO.md) : faux dans le dépôt et dans la release ;
  // outils/construire_demo_web.py le passe à vrai dans sa copie (dist/demo-web/). Vrai : l'écran de
  // démarrage ne propose que la démo et « Télécharger Prévo » (ni dossier, ni serveur), et l'assistant
  // IA reste visible mais n'appelle rien (js/modules/ia.js). Jamais déduit de l'adresse de la page.
  const VERSION_WEB = false;
  const CLE_PROFIL = 'prevo.profil';
  const CLE_POSTE = 'prevo.poste';
  const CLE_MENU_REPLIE = 'prevo.menuReplie';
  const CLE_VERROU_ONGLET = 'prevo.verrouOnglet';   // sessionStorage : poste du verrou posé par cet onglet
  // Langue (Lot 4 du chantier multilingue, T295, T298 ; D148, D149) : langue du compte connecté et langue de
  // l'installation (écrites ici), choix du poste (écrit par UI.selecteurLangue), lus par js/i18n-chargeur.js avant
  // js/schema.js ; raison du dernier rechargement pour la langue (sessionStorage, cet onglet : jamais deux de suite
  // pour la même).
  const CLE_LANGUE_POSTE = 'prevo.langue';
  const CLE_LANGUE_COMPTE = 'prevo.langue.compte';
  const CLE_LANGUE_INSTALLATION = 'prevo.langue.installation';
  const CLE_RECHARGEMENT_LANGUE = 'prevo.langue.rechargement';
  const PARAMETRE_LANGUE = 'langue_defaut';
  const ROUTE_ACCUEIL = '#/accueil';
  const TYPES_PROFIL = ['demandeur', 'technicien', 'responsable'];
  const ENTREES_BARRE_BAS = 4;
  // Mode Solo (D132, §22.11) : réglage mode_solo de parametres.csv, profil responsable seulement. Ces écrans
  // passent sous « Plus » (repliable dans le menu latéral, feuille « Plus » au téléphone) ; leurs routes restent.
  const ECRANS_SOUS_PLUS_SOLO = ['equipe', 'planning'];
  const ECRANS_PLEINS = ['ecran-chargement', 'ecran-demarrage', 'ecran-base-vide', 'ecran-profil', 'ecran-connexion', 'ecran-installation', 'app'];
  const ROUTE_INSTALLATION = '#/installation';
  const HOTES_DU_PC_SERVEUR = ['127.0.0.1', 'localhost', '[::1]', '::1'];

  // --- État de l'application ----------------------------------------------------------------
  let mode = null;                 // 'serveur' | 'dossier' | 'demo'
  let adaptateur = null;           // adaptateur de stockage (contrat ARCHITECTURE.md §6)
  let profil = null;               // { type, nom, technicienId }
  let comptesExiges = false;       // mode serveur : les comptes sont exigés (lot 7, D124) ; le profil vient de la session
  let session = null;              // mode comptes : session du serveur (camelCase, adaptateur.session()), sinon null
  let raisonDejaDite = '';         // langue : rechargement déjà refusé (et dit) pour cette raison sur cette page
  let promesseConnexion = null;    // écran de connexion en cours (une seule fois à la fois)
  let poste = '';                  // nom du poste (journal, verrou)
  let adressesReseau = [];         // mode serveur : ['http://192.168.1.10:8080/', …]
  let cePcSeulement = false;       // mode serveur : portée « ce PC », aucun téléphone ne joint Prévo (recette du lot 7)
  let installationAFaire = false;  // mode serveur : /api/info rend installation_a_faire (pas de prevo.config.json, §22.10)
  const ecrans = [];               // écrans enregistrés par les modules
  let ecranCourant = null;
  let saisieEnCours = false;
  let numeroAffichage = 0;         // pour ignorer un affichage dépassé par un autre
  let pretDejaMarque = false;
  let preventifDejaMarque = false; // performance.mark('prevo:preventif') posée une seule fois
  let promesseScriptDemo = null;
  let promesseEcharts = null;        // chargement à la demande d'ECharts (lot 3)
  let resoudreProfil = null;       // fonction qui termine l'écran de profil en cours
  let resoudreBaseVide = null;     // fonction qui termine l'écran « base vide » en cours
  let menuPlusOuvert = false;      // mode Solo : groupe « Plus » du menu latéral déplié
  const alertesCoque = [];         // bandeaux à montrer dans la coque (ex. verrou du dossier)
  let tablesLaissees = [];          // tables laissées par le passage au format (déjà dites par leur bandeau, T197)
  const tablesDitesAbimees = new Set();   // tables dont le bandeau « Fichier abîmé » est déjà posé (T197, T200)
  let depuisAbimes = {};            // T206 : { table: 'AAAA-MM-JJTHH:MM:SS' }, depuis quand chaque table est abîmée
  let formatEnAttente = null;      // mode serveur : état du format (Donnees.etatDuFormat) d'une base pas au format courant

  // Thème du poste (lot 4, §17.7) : <html data-theme="clair"> posé dès la lecture de ce fichier, donc
  // avant DOMContentLoaded et avant le premier écran (pas d'écran sombre qui passe au clair).
  appliquerThemeDuPoste();

  // ===========================================================================================
  // 1. Petits outils
  // ===========================================================================================

  // Thème mémorisé sur le poste (prevo.theme, lu par Poste avec une lecture protégée) ; une erreur
  // n'empêche jamais Prévo de démarrer : le thème sombre par défaut reste alors en place.
  function appliquerThemeDuPoste() {
    try {
      if (typeof Poste !== 'undefined') Poste.appliquerTheme(Poste.themeMemorise());
    } catch (erreur) {
      console.warn('Prévo : thème du poste non appliqué (' + (erreur && erreur.message) + ').', erreur);
    }
  }

  // localStorage peut être refusé (navigation privée, réglage) : on continue sans mémoire.
  function lireMemoire(cle) {
    try { return window.localStorage.getItem(cle); } catch (erreur) { return null; }
  }

  function ecrireMemoire(cle, valeur) {
    try { window.localStorage.setItem(cle, valeur); } catch (erreur) { /* sans mémoire : tant pis */ }
  }

  function effacerMemoire(cle) {
    try { window.localStorage.removeItem(cle); } catch (erreur) { /* sans mémoire : rien à effacer */ }
  }

  // Nom de poste proposé la première fois : « Poste-7KQ2 » (Math.random suffit, pas de crypto).
  function posteAleatoire() {
    const caracteres = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    let suffixe = '';
    for (let i = 0; i < 4; i += 1) suffixe += caracteres[Math.floor(Math.random() * caracteres.length)];
    return I18n.donnees('socle.poste_aleatoire.poste_suffixe', { suffixe });     // écrit au journal et dans verrou.txt (D156)
  }

  // (Donnees.ErreurLectureSeule est une ErreurStockage : son message est montré tel quel.)
  function estErreurDonnees(erreur) {
    return erreur instanceof Donnees.ErreurValidation || erreur instanceof Donnees.ErreurConflit
      || erreur instanceof Donnees.ErreurStockage;
  }

  // Fichier abîmé (T201) : jamais réécrit (T197, T200, Donnees.ErreurFichierAbime) ; le message dit quoi faire, sans
  // jargon et selon le rôle. Qui n'est pas responsable (technicien, demandeur, appareil enrôlé, autre profil en mode
  // dossier) n'a rien à réparer : il prévient le responsable. Les écrans ne vident ni ne quittent rien sur une erreur :
  // la saisie reste dans le formulaire. Le message technique de l'erreur ne va qu'en console.
  function fichierAbimeDe(erreur) {
    const nomTable = erreur.table || '';
    return nomTable ? (Schema.table(nomTable) || {}).fichier || nomTable + '.csv' : '';
  }

  /** Texte d'une erreur pour l'utilisateur : son message, sauf fichier abîmé (texte selon le rôle, T201). */
  function messageErreur(erreur) {
    if (!(erreur instanceof Donnees.ErreurFichierAbime)) return (erreur && erreur.message) || String(erreur);
    if (!estResponsable()) {
      return I18n.t('socle.message_erreur.fichier_abime_prevenez_responsable');
    }
    const fichier = fichierAbimeDe(erreur);
    if (!fichier) {
      return I18n.t('socle.message_erreur.fichier_abime_rien_ete');
    }
    return I18n.t('socle.message_erreur.fichier_abime_rien_ete_avec_fichier', { fichier });
  }

  /**
   * Raison d'un échec, à glisser dans une phrase (« …, mais la gamme n'a pas été mise à jour (raison) ») : le message
   * de l'erreur (« erreur inconnue » sans erreur), sauf fichier abîmé (texte court selon le rôle, T201).
   */
  function raisonErreur(erreur) {
    if (erreur === undefined || erreur === null) return I18n.t('commun.message.erreur_inconnue');
    if (!(erreur instanceof Donnees.ErreurFichierAbime)) return erreur.message || String(erreur);
    if (!estResponsable()) return I18n.t('socle.raison_erreur.fichier_abime_prevenez_responsable');
    const fichier = fichierAbimeDe(erreur);
    if (!fichier) {
      return I18n.t('socle.raison_erreur.fichier_abime_rien_ete');
    }
    return I18n.t('socle.raison_erreur.fichier_abime_rien_ete_avec_fichier', { fichier });
  }

  /** Erreur gérée : message à l'utilisateur (toast, messageErreur) et trace console.warn (jamais console.error). */
  function signalerErreur(erreur, contexte) {
    // T329 : session perdue, l'écran de connexion est là et dit quoi faire (la saisie reste) : pas de toast en plus.
    if (!(erreur && erreur.sessionAbsente && promesseConnexion)) UI.toast(messageErreur(erreur), 'erreur');
    console.warn('Prévo' + (contexte ? ' (' + contexte + ')' : '') + ' : ' + ((erreur && erreur.message) || String(erreur)),
      erreur);
  }

  // Phrases de index.html qui ont du balisage au milieu (data-i18n n'y pose que du texte) : remplies ici, au démarrage.
  function remplirPhrasesBalisees() {
    UI.remplir(UI.$('#note-mode-serveur'), UI.html`${I18n.html('socle.remplir_phrases_balisees.plusieurs_postes_telephones_lancez')}`);
    UI.$$('.lien-installation').forEach((lien) => UI.remplir(lien, UI.html`${I18n.html('socle.remplir_phrases_balisees.installer_prevo_assistant_comptes')}`));
    UI.remplir(UI.$('.signature .libelle'), UI.html`${I18n.html('socle.remplir_phrases_balisees.developpe_claude_anthropic_demande')}`);
  }

  // Remplace <span data-icone="nom"> et <span data-ui="logo"> par les dessins de UI.
  function remplacerIcones(racine) {
    UI.$$('[data-icone]', racine).forEach((place) => { place.outerHTML = String(UI.icone(place.dataset.icone)); });
    UI.$$('[data-ui="logo"]', racine).forEach((place) => { place.outerHTML = String(UI.logo(place.dataset.classe)); });
  }

  // Montre un seul des écrans pleins (ou la coque #app) ; `etat` va dans <html data-etat>.
  function montrer(idEcran, etat) {
    ECRANS_PLEINS.forEach((id) => { UI.$('#' + id).hidden = id !== idEcran; });
    if (etat) document.documentElement.dataset.etat = etat;
    window.scrollTo(0, 0);
  }

  function coqueVisible() {
    return !UI.$('#app').hidden;
  }

  // Exécute une action déclenchée par un bouton : boutons de l'écran désactivés pendant l'action,
  // erreur affichée proprement. Renvoie le résultat de l'action (ou undefined en cas d'erreur).
  async function pendantAction(ecran, action) {
    const boutons = UI.$$('button, input', ecran);
    boutons.forEach((bouton) => { bouton.disabled = true; });
    try {
      return await action();
    } catch (erreur) {
      signalerErreur(erreur);
      return undefined;
    } finally {
      boutons.forEach((bouton) => { bouton.disabled = false; });
    }
  }

  // ===========================================================================================
  // 2. Démarrage : mode serveur ou écran de démarrage
  // ===========================================================================================

  async function demarrer() {
    I18n.appliquer(document);          // textes statiques de index.html (data-i18n, data-i18n-attr)
    // Titre de l'onglet dans la langue active dès le démarrage (avant le premier écran) : la balise <title>
    // d'index.html reste nue (relue telle quelle par test_acces_mandataire et test_version_web, T260, T294).
    document.title = I18n.t('socle.definir_titre.prevo_gmao');
    remplirPhrasesBalisees();
    remplacerIcones(document);
    installerEcouteurs();
    poste = lireMemoire(CLE_POSTE) || posteAleatoire();
    montrer('ecran-chargement', 'chargement');

    // Version web : pas de serveur Prévo à chercher (le site est statique : /api/ping n'existe pas).
    const pageEnHttp = location.protocol === 'http:' || location.protocol === 'https:';
    if (!VERSION_WEB && pageEnHttp && await StockageServeur.detecter()) {
      const serveur = StockageServeur.creer();
      // Lot 7 (§22.10) : #/installation sur le PC serveur, sans configuration → l'assistant d'abord ; quitté sans
      // terminer, Prévo s'ouvre normalement sur l'accueil (terminé, la page se recharge d'elle-même).
      if (await ouvrirAssistantSiDemande(serveur)) remplacerRoute(ROUTE_ACCUEIL);
      try {
        await ouvrirAvec(serveur);
      } catch (erreur) {
        signalerErreur(erreur, 'lecture des données du serveur');
        await afficherDemarrage();
      }
      return;
    }
    await afficherDemarrage();
  }

  // Le PC serveur lui-même : la page est ouverte par 127.0.0.1 ou localhost (les routes de l'assistant n'existent que là).
  function pcServeur() {
    return HOTES_DU_PC_SERVEUR.includes(location.hostname);
  }

  // Vrai si l'assistant a été montré (route #/installation, PC serveur, installation à faire) puis quitté sans terminer.
  async function ouvrirAssistantSiDemande(serveur) {
    if (typeof Installation === 'undefined' || !Installation.estRoute(location.hash) || !pcServeur()) return false;
    let informations;
    try {
      informations = await serveur.info();
    } catch (erreur) {
      console.warn('Prévo : état de l\'installation inconnu (' + (erreur && erreur.message) + ').', erreur);
      return false;
    }
    if (!informations.installationAFaire) return false;
    montrer('ecran-installation', 'installation');
    await Installation.ouvrir();
    return true;
  }

  // Lien discret « Installer Prévo (assistant) » des écrans de démarrage en mode serveur : sur le PC serveur seulement,
  // tant que l'installation n'est pas faite ; depuis le réseau, rien.
  function montrerLienInstallation() {
    const visible = mode === 'serveur' && installationAFaire && pcServeur() && typeof Installation !== 'undefined';
    UI.$$('.lien-installation').forEach((zone) => { zone.hidden = !visible; });
  }

  async function afficherDemarrage() {
    const dossierPossible = !VERSION_WEB && StockageDossier.disponible();
    UI.$('#btn-dossier').hidden = !dossierPossible;
    let memorise = null;
    if (dossierPossible) {
      try {
        memorise = await StockageDossier.poigneeMemorisee();
      } catch (erreur) {
        console.warn('Prévo : dossier précédent illisible (' + (erreur && erreur.message) + ').', erreur);
      }
    }
    UI.$('#btn-reprendre').hidden = !memorise;
    UI.$('#nom-dossier-precedent').textContent = memorise ? '« ' + memorise.nom + ' »' : '';
    const zoneAlerte = UI.$('#alerte-navigateur');
    zoneAlerte.textContent = '';
    zoneAlerte.hidden = dossierPossible || VERSION_WEB;
    if (!dossierPossible && !VERSION_WEB) {
      zoneAlerte.appendChild(UI.bandeau('attention', UI.html`${I18n.html('socle.demarrage.navigateur_sait_pas_ouvrir')}`));
    }
    preparerVersionWeb();
    montrer('ecran-demarrage', 'demarrage');
  }

  // Version web : seule la démo est proposée ; « Télécharger Prévo » (dernière release, lien écrit
  // dans index.html) remplace le mode dossier, le dépôt de CSV et le rappel du mode serveur, et le titre
  // « Où sont les données de cette démo ? » (avec sa réponse) remplace « Où sont vos données ? ».
  function preparerVersionWeb() {
    UI.$('#zone-depot').hidden = VERSION_WEB;
    UI.$('#note-mode-serveur').hidden = VERSION_WEB;
    UI.$('#btn-telecharger').hidden = !VERSION_WEB;
    UI.$('#titre-donnees').hidden = VERSION_WEB;
    UI.$('#titre-donnees-demo').hidden = !VERSION_WEB;
    UI.$('#note-donnees-demo').hidden = !VERSION_WEB;
    // T377 : hors français, une phrase dit que les données de la démo décrivent un atelier français (elles ne se
    // traduisent pas : ce sont des données) ; proposition 1 de T339.
    UI.$('#note-demo-atelier-francais').hidden = !(VERSION_WEB && I18n.langue !== 'fr');
    const demo = UI.$('#btn-demo');
    demo.classList.toggle('btn-primaire', VERSION_WEB);
    demo.classList.toggle('btn-secondaire', !VERSION_WEB);
  }

  async function choisirDossier() {
    const poignee = await StockageDossier.choisir();
    if (!poignee) return;                                  // l'utilisateur a annulé
    await ouvrirAvecGarde(await StockageDossier.creer(poignee, { poste }));
  }

  async function reprendreDossier() {
    const poignee = await StockageDossier.reprendre();
    if (!poignee) {
      UI.toast(I18n.t('socle.reprendre_dossier.acces_dossier_precedent_pas'), 'attention');
      return;
    }
    await ouvrirAvecGarde(await StockageDossier.creer(poignee, { poste }));
  }

  async function essayerDemo() {
    await chargerScriptDemo();
    await ouvrirAvecGarde(StockageDemo.creer(DEMO_DONNEES.tables, { dateReference: DEMO_DONNEES.dateReference }));
  }

  async function ouvrirFichiersDeposes(fichiers) {
    const liste = Array.from(fichiers || []);
    if (!liste.length) return;
    const resultat = await StockageDemo.depuisFichiers(liste);
    const ignores = resultat.fichiersIgnores;
    if (ignores.length === liste.length) {
      UI.toast(I18n.t('socle.ouvrir_fichiers_deposes.aucun_fichier_reconnu_fichiers'), 'attention');
      return;
    }
    await ouvrirAvecGarde(resultat.adaptateur);
    if (ignores.length) UI.toast(I18n.t('socle.ouvrir_fichiers_deposes.fichiers_ignores_nom_inconnu', { fichiers: ignores.join(', ') }), 'attention');
  }

  // Ouvre un adaptateur choisi sur l'écran de démarrage ; en cas d'échec, on y revient.
  async function ouvrirAvecGarde(nouvelAdaptateur) {
    try {
      await ouvrirAvec(nouvelAdaptateur);
    } catch (erreur) {
      if (nouvelAdaptateur && typeof nouvelAdaptateur.arreterVerrou === 'function') nouvelAdaptateur.arreterVerrou();
      adaptateur = null;
      mode = null;
      await afficherDemarrage();
      throw erreur;
    }
  }

  /** Charge js/demo-donnees.js à la demande (balise <script>, compatible file://). Promesse. */
  function chargerScriptDemo() {
    if (typeof DEMO_DONNEES !== 'undefined') return Promise.resolve();
    if (!promesseScriptDemo) {
      promesseScriptDemo = new Promise((resoudre, rejeter) => {
        const script = document.createElement('script');
        script.src = 'js/demo-donnees.js';
        script.onload = () => resoudre();
        script.onerror = () => {
          promesseScriptDemo = null;
          rejeter(new Error(I18n.t('socle.charger_script_demo.jeu_demo_js_demo')));
        };
        document.head.appendChild(script);
      });
    }
    return promesseScriptDemo;
  }

  // ECharts (js/lib/echarts.min.js, ≈ 1 Mo) n'est jamais chargé au démarrage : il est injecté à la
  // première ouverture des Indicateurs ou d'un rapport (lot 3, ARCHITECTURE.md §15.1). Même mécanisme
  // que le jeu de démo : une balise <script>, compatible file://. Un échec permet un nouvel essai.
  // SheetJS (js/lib/xlsx.full.min.js, ≈ 0,9 Mo) : même principe, injecté à l'ouverture de l'assistant
  // d'import (lot 5, ARCHITECTURE.md §18.1), jamais au démarrage.
  let promesseSheetJS = null;
  function chargerSheetJS() {
    if (typeof XLSX !== 'undefined') return Promise.resolve(XLSX);
    if (!promesseSheetJS) {
      promesseSheetJS = new Promise((resoudre, rejeter) => {
        const script = document.createElement('script');
        script.src = 'js/lib/xlsx.full.min.js';
        script.onload = () => resoudre(XLSX);
        script.onerror = () => {
          promesseSheetJS = null;
          script.remove();
          rejeter(new Error(I18n.t('socle.charger_sheet_js.bibliotheque_lecture_fichiers_excel')));
        };
        document.head.appendChild(script);
      });
    }
    return promesseSheetJS;
  }

  function chargerEcharts() {
    if (typeof echarts !== 'undefined') return Promise.resolve(echarts);
    if (!promesseEcharts) {
      promesseEcharts = new Promise((resoudre, rejeter) => {
        const script = document.createElement('script');
        script.src = 'js/lib/echarts.min.js';
        script.onload = () => resoudre(echarts);
        script.onerror = () => {
          promesseEcharts = null;
          script.remove();
          rejeter(new Error(I18n.t('socle.charger_echarts.bibliotheque_graphiques_js_lib')));
        };
        document.head.appendChild(script);
      });
    }
    return promesseEcharts;
  }

  // ===========================================================================================
  // 3. Ouverture des données : chargement, base vide, verrou, profil, coque
  // ===========================================================================================

  async function ouvrirAvec(nouvelAdaptateur) {
    montrer('ecran-chargement', 'chargement');
    // Le même adaptateur, protégé, pour Donnees et pour les modules : en lecture seule (D169), ses écritures
    // (tables, documents, sauvegardes, restauration) sont refusées.
    adaptateur = Donnees.protegerEcritures(nouvelAdaptateur);
    mode = nouvelAdaptateur.mode;
    formatEnAttente = null;
    tablesDitesAbimees.clear();
    Donnees.initialiser(adaptateur, { poste, profil: '' });
    // Lot 7 (§22.4) : comptes exigés → connexion (ou mot de passe à choisir) AVANT toute lecture de table, sinon
    // chaque table répondrait 401 (ou 403 avec un mot de passe provisoire : la base paraîtrait vide). T298 : la page
    // qui n'est pas dans la langue du compte (ou qui l'est encore sans session) se recharge, une fois.
    if (mode === 'serveur') {
      if (await ouvrirSession()) return;
    } else {
      effacerMemoire(CLE_LANGUE_COMPTE);                  // T298 : sans comptes hors du mode serveur
    }
    montrer('ecran-chargement', 'chargement');
    // /api/info avant les tables (après la session : la route n'est pas publique) : adresses réseau, et l'installation
    // à faire, pour le lien de l'assistant sur les écrans « base vide » et « profil » (§22.10).
    if (mode === 'serveur') {
      try {
        const informations = await adaptateur.info();
        adressesReseau = (informations && informations.adressesReseau) || [];
        installationAFaire = Boolean(informations && informations.installationAFaire);
        cePcSeulement = Boolean(informations && informations.cePcSeulement);
      } catch (erreur) {
        console.warn('Prévo : adresses réseau du serveur inconnues (' + (erreur && erreur.message) + ').', erreur);
      }
    }
    montrerLienInstallation();
    await Donnees.chargerTout();
    if (suivreLangueInstallation()) return;              // T295 : page dans une autre langue, rechargée une fois
    await sauvegarderAvantMiseAJour();                   // D170 : avant toute écriture (base vide, format courant)

    if (mode !== 'demo' && Donnees.baseVide()) {
      const choix = await demanderBaseVide();
      montrer('ecran-chargement', 'chargement');
      await remplirBaseVide(choix);
      await Donnees.chargerTout();
      if (suivreLangueInstallation()) return;
    }
    const formatAJour = await passerAuFormatCourant();   // avant TOUTE autre écriture, pour tous les profils
    const lectureSeule = Donnees.lectureSeule();

    // Lecture seule : pas de verrou (verrou.txt est une écriture dans le dossier ; rien n'y est écrit).
    if (mode === 'dossier' && !lectureSeule) await verifierVerrouDossier();

    // Comptes exigés : le profil est déduit de la session (D126), l'écran de profil de 1.2 ne s'affiche jamais.
    let profilChoisi = session ? profilDepuisSession(session) : lireProfilMemorise();
    if (!session && !profilValable(profilChoisi)) profilChoisi = await demanderProfil(false);
    appliquerProfil(profilChoisi);
    if (formatEnAttente && estResponsable()) alertesCoque.push(bandeauFormatEnAttente(formatEnAttente));
    // Fichiers abîmés (T197) : jamais réécrits ; on le dit tout de suite, avant qu'une écriture soit refusée.
    const abimes = lectureSeule ? [] : Donnees.tablesAbimees()
      .filter((t) => !tablesLaissees.includes(t) && !tablesDitesAbimees.has(t));
    depuisAbimes = await lireDepuisAbimes(lectureSeule, abimes.length > 0);
    abimes.forEach((t) => tablesDitesAbimees.add(t));
    if (abimes.length) alertesCoque.push(bandeauFichiersAbimes(abimes));
    const otPreventifs = await genererPreventifAOuverture(formatAJour && !lectureSeule);
    Donnees.demarrerSurveillance();
    // Assistant IA (lot 4, §17.3) : un seul test du fournisseur s'il est activé sur le poste, aucun
    // appel sinon ; sans attendre la réponse (l'état « prêt » n'en dépend pas).
    if (typeof Ia !== 'undefined') Ia.verifierAuDemarrage();
    // Dictée (lot 4, §17.6) : bouton micro sur chaque champ dicté, où qu'il apparaisse ensuite.
    if (typeof Dictee !== 'undefined') Dictee.surveiller(document.body);
    await ouvrirCoque();
    // En démo, les données repartent du jeu d'origine à chaque ouverture : la génération a lieu à chaque
    // fois, et sa notification n'apprendrait rien (T89, brief : pas de toast à chaque ouverture de la démo).
    if (otPreventifs.length && mode !== 'demo') UI.toast(Preventif.texteGeneration(otPreventifs.length) + '.', 'succes');
  }

  // Langue de l'installation (Lot 4 du chantier multilingue, T295 ; D148, D149, D156), à chaque lecture de
  // parametres.csv (ouverture des données, changement de parametres sur ce poste ou un autre) : langue_defaut est notée
  // (I18n.noterInstallation : langue des textes écrits dans les données) et, en mode serveur ou dossier, retenue par ce
  // navigateur pour js/i18n-chargeur.js. Si la page n'est pas dans la langue à afficher (choix du poste, sinon
  // installation, sinon français) ou n'a pas le dictionnaire de l'installation, elle se recharge, une fois : la raison
  // est notée pour cet onglet et jamais deux rechargements de suite pour la même ; sans sessionStorage, aucun. Démo et
  // fichiers déposés : langue notée, rien de retenu ni de rechargé (les données vivent dans la page). Une saisie en
  // cours (rechargementPermis faux) attend le prochain changement ou la prochaine ouverture. Vrai si la page se recharge.
  // T298 : la langue du compte connecté passe avant le choix du poste (suivreLangueDuCompte).
  function suivreLangueInstallation(rechargementPermis) {
    const installation = I18n.noterInstallation(Donnees.parametre(PARAMETRE_LANGUE, ''));
    // Pendant l'usage, le profil inscrit au journal suit (D156) ; à l'ouverture, appliquerProfil le pose ensuite.
    if (profil && coqueVisible()) Donnees.definirIdentite({ poste, profil: libelleJournal(profil) });
    if (mode !== 'serveur' && mode !== 'dossier') return false;
    // Base vide (T296) : pas encore de langue de l'installation ; la page garde la sienne (celle du navigateur, D150)
    // pour l'écran « base vide », qui la demande ; elle est retenue une fois la base créée.
    if (Donnees.baseVide()) return false;
    ecrireMemoire(CLE_LANGUE_INSTALLATION, installation);
    const attendue = I18n.langueAAfficher(lireMemoire(CLE_LANGUE_POSTE), installation, undefined,
      langueDuCompte(session));
    try {
      if (attendue === I18n.langue && I18n.langueDesDonnees === installation) {
        if (window.sessionStorage.getItem(CLE_RECHARGEMENT_LANGUE) !== null) {
          window.sessionStorage.removeItem(CLE_RECHARGEMENT_LANGUE);
        }
        return false;
      }
    } catch (erreur) {               // sans mémoire d'onglet, pas de garde-fou : pas de rechargement
      return false;
    }
    if (rechargementPermis === false) return false;
    return rechargerPourLaLangue(attendue + '/' + installation);
  }

  /** Recharge la page pour la langue, une fois : la raison est notée pour cet onglet et jamais deux rechargements de
   *  suite pour la même (un avertissement à la place, une fois par page) ; sans sessionStorage, aucun. Vrai si la page
   *  se recharge. */
  function rechargerPourLaLangue(raison) {
    try {
      if (window.sessionStorage.getItem(CLE_RECHARGEMENT_LANGUE) === raison) {
        if (raisonDejaDite !== raison) {
          console.warn('Prévo : page déjà rechargée pour la langue « ' + raison + ' » ; elle reste en « ' + I18n.langue + ' ».');
        }
        raisonDejaDite = raison;
        return false;
      }
      window.sessionStorage.setItem(CLE_RECHARGEMENT_LANGUE, raison);
    } catch (erreur) {               // sans mémoire d'onglet, pas de garde-fou : pas de rechargement
      return false;
    }
    window.location.reload();
    return true;
  }

  // Mode dossier, nouvelle version de Prévo (D170) : une fois les tables chargées, AVANT toute écriture (base vide,
  // passage au format courant), sauvegarde « avant-mise-a-jour » puis derniere-version.json si la version notée dans
  // le dossier n'est pas celle-ci (StockageDossier, sauvegarderAvantMiseAJour). Lecture seule : rien (aucune
  // écriture). Échec : erreur signalée et bandeau, l'application continue ; nouvel essai à la prochaine ouverture.
  // Le serveur fait la même chose à son démarrage (serveur.py).
  async function sauvegarderAvantMiseAJour() {
    if (mode !== 'dossier' || Donnees.lectureSeule() || typeof adaptateur.sauvegarderAvantMiseAJour !== 'function') return;
    try {
      await adaptateur.sauvegarderAvantMiseAJour(VERSION);
    } catch (erreur) {
      signalerErreur(erreur, 'sauvegarde avant la mise à jour de Prévo');
      const message = (erreur && erreur.message) || '';
      alertesCoque.push(UI.bandeau('attention', UI.html`${I18n.html('socle.sauvegarder_avant_mise_ajour.sauvegarde_avant_mise_jour', { message })}`));
    }
  }

  // Format des fichiers (ARCHITECTURE.md §5.6 et §14.1 ; décisions D168 et D169) : une fois les tables chargées,
  // pour tous les profils et AVANT toute autre écriture.
  //   - données d'une version plus récente (Donnees.lectureSeule()) : rien n'est fait ni écrit ; le bandeau
  //     permanent de la coque le dit (afficherLectureSeule) ;
  //   - mode serveur : le navigateur ne migre plus, c'est le serveur à son démarrage ; base pas au format courant
  //     → bandeau au responsable (posé après le choix du profil, bandeauFormatEnAttente) ;
  //   - dossier et démo : Donnees.migrerAuFormatCourant (sauvegarde « avant-format-vN » d'abord, sans effet si
  //     c'est déjà fait). Sauvegarde impossible : erreur signalée et bandeau dans la coque, rien n'est écrit,
  //     l'application reste utilisable et le passage sera retenté à la prochaine ouverture. Tables abîmées,
  //     laissées telles quelles : bandeau.
  // Renvoie true si les fichiers sont au format courant (passage fait, ou rien à faire), false sinon.
  async function passerAuFormatCourant() {
    if (Donnees.lectureSeule()) return false;
    try {
      if (mode === 'serveur') {
        const etat = Donnees.etatDuFormat();
        formatEnAttente = etat.depart < etat.courant ? etat : null;
        return formatEnAttente === null;
      }
      const resultat = await Donnees.migrerAuFormatCourant();
      if (resultat.abimees.length) alertesCoque.push(bandeauFichiersLaisses(resultat.abimees));
      tablesLaissees = resultat.abimees.slice();
      return true;
    } catch (erreur) {
      // T204 : parametres.csv abîmé, passage refusé sans rien écrire (Donnees.migrerAuFormatCourant) ; le bandeau
      // « Fichier abîmé » posé après le choix du profil le dit : ni toast, ni bandeau en plus, ni génération du préventif.
      if (erreur instanceof Donnees.ErreurFichierAbime) {
        tablesLaissees = [];
        console.warn('Prévo (passage au format ' + Schema.version + ' des fichiers) : ' + erreur.message, erreur);
        return false;
      }
      signalerErreur(erreur, 'passage au format ' + Schema.version + ' des fichiers');
      const message = (erreur && erreur.message) || '';
      alertesCoque.push(UI.bandeau('attention', UI.html`${I18n.html('socle.passer_au_format_courant.fichiers_ont_pas_pu', { version: Schema.version, message })}`));
      return false;
    }
  }

  // Mode serveur, base pas au format courant (le serveur n'a pas pu la mettre à jour à son démarrage).
  function bandeauFormatEnAttente(etat) {
    return UI.bandeau('attention', UI.html`${I18n.html('socle.bandeau_format_en_attente.fichiers_donnees_sont_pas', { courant: etat.courant, depart: etat.depart })}`);
  }

  // Tables laissées telles quelles par le passage au format courant (en-tête illisible, ou fichier abîmé qu'une
  // réécriture ferait perdre en partie) : jamais réécrites.
  function bandeauFichiersLaisses(tables) {
    const fichiers = tables.map((nomTable) => (Schema.table(nomTable) || {}).fichier || nomTable + '.csv').join(', ');
    const titre = tables.length > 1 ? I18n.t('socle.bandeau_fichiers_laisses.fichiers_abimes_laisses_tels') : I18n.t('socle.bandeau_fichiers_laisses.fichier_abime_laisse_tel');
    return UI.bandeau('attention', UI.html`${I18n.html('socle.bandeau_fichiers_laisses.tete_illisible_lignes_reecriture', { titre, fichiers, version: Schema.version })}`);
  }

  // Fichiers abîmés (T197, défaut trouvé par la recette T193) : Prévo ne les enregistre plus (ErreurFichierAbime).
  // T201 : sans jargon pour qui n'est pas responsable (il prévient le responsable, comme messageErreur).
  // T206 : pour le responsable, depuis quand chaque fichier est abîmé (fichierAbimeDepuis).
  function bandeauFichiersAbimes(tables) {
    const plusieurs = tables.length > 1;
    const titre = plusieurs ? I18n.t('socle.bandeau_fichiers_abimes.fichiers_abimes') : I18n.t('socle.bandeau_fichiers_abimes.fichier_abime');
    if (!estResponsable()) {
      const suite = plusieurs
        ? I18n.t('socle.bandeau_fichiers_abimes.tant_ils_sont_pas')
        : I18n.t('socle.bandeau_fichiers_abimes.tant_pas_repare_prevo');
      return UI.bandeau('attention', UI.html`${I18n.html('socle.bandeau_fichiers_abimes.prevenez_responsable', { titre, suite })}`);
    }
    const fichiers = tables.map(fichierAbimeDepuis).join(' ; ');
    return UI.bandeau('attention', UI.html`${I18n.html('socle.bandeau_fichiers_abimes.tete_coupe_guillemet_non', { titre, fichiers })}`);
  }

  // T206 (contrat, point 4) : depuis quand chaque table est abîmée ({ table: 'AAAA-MM-JJTHH:MM:SS' }). Mode dossier
  // (jamais en lecture seule) : fichiers-abimes.json est d'abord mis à jour avec les tables abîmées chargées, à chaque
  // ouverture (StockageDossier, noterFichiersAbimes) ; serveur : /api/info (abimesDepuis), seulement si le bandeau du
  // responsable en a besoin. Échec : {} (le bandeau dit « repéré aujourd'hui »), l'application continue.
  async function lireDepuisAbimes(lectureSeule, besoin) {
    if (lectureSeule) return {};
    try {
      if (mode === 'dossier' && typeof adaptateur.noterFichiersAbimes === 'function') {
        return await adaptateur.noterFichiersAbimes(Donnees.tablesAbimees());
      }
      if (besoin && estResponsable() && typeof adaptateur.abimesDepuis === 'function') return await adaptateur.abimesDepuis();
    } catch (erreur) {
      console.warn('Prévo : date des fichiers abîmés inconnue (' + (erreur && erreur.message) + ').', erreur);
    }
    return {};
  }

  // T206 (contrat, point 5) : « <fichier>, depuis le JJ/MM/AAAA (N jours) » d'après depuisAbimes ; date inconnue, ou
  // date du jour → « <fichier>, repéré aujourd'hui ».
  function fichierAbimeDepuis(nomTable) {
    const fichier = (Schema.table(nomTable) || {}).fichier || nomTable + '.csv';
    const lu = /^(\d{4})-(\d{2})-(\d{2})T/.exec(String(depuisAbimes[nomTable] || ''));
    const jour = new Date();
    const jours = lu ? Math.round((Date.UTC(jour.getFullYear(), jour.getMonth(), jour.getDate())
      - Date.UTC(+lu[1], lu[2] - 1, +lu[3])) / 86400000) : 0;
    if (jours <= 0) return I18n.t('socle.fichier_abime_depuis.repere_aujourd_hui', { fichier });
    return I18n.t('socle.fichier_abime_depuis.depuis_le', { fichier, date: UI.dateFr(lu[0].slice(0, 10)), n: jours });
  }

  // Bandeau « Fichier abîmé » pour une table pas encore signalée (ni à l'ouverture, ni par le passage au format) :
  // tout de suite si la coque est affichée, sinon à son ouverture (afficherAlertesCoque). T200 (écriture refusée
  // découverte pendant l'usage), T201 (génération des OT préventifs refusée à l'ouverture).
  function direFichierAbime(nomTable) {
    if (!nomTable || tablesLaissees.includes(nomTable) || tablesDitesAbimees.has(nomTable)) return;
    tablesDitesAbimees.add(nomTable);
    alertesCoque.push(bandeauFichiersAbimes([nomTable]));
    if (coqueVisible()) afficherAlertesCoque();
  }

  // Lecture seule (D169) : bandeau permanent (sans bouton « Fermer ») en tête de la coque, donc sur tous les
  // écrans ; retiré si les données ouvertes ne sont plus en lecture seule (autre dossier).
  function afficherLectureSeule() {
    const zone = UI.$('#alertes-app');
    const present = UI.$('#bandeau-lecture-seule');
    if (!Donnees.lectureSeule()) {
      if (present) present.remove();
      zone.hidden = zone.children.length === 0;
      return;
    }
    if (present) return;
    const format = Donnees.etatDuFormat().base;
    const bandeau = UI.bandeau('important', UI.html`${I18n.html('socle.lecture_seule.lecture_seule_donnees_viennent', { format, version: Schema.version })}`);
    bandeau.id = 'bandeau-lecture-seule';
    zone.prepend(bandeau);
    zone.hidden = false;
  }

  // RG5 (ARCHITECTURE.md §14.3) : à l'ouverture, un technicien ou un responsable (jamais un demandeur)
  // génère les OT des gammes échues. Renvoie les identifiants des OT créés ; une erreur est signalée et
  // l'application reste utilisable (le bouton « Générer les OT échus » et la prochaine ouverture
  // réessaieront). La marque performance « prevo:preventif » est posée quand l'étape est finie
  // (aussi pour un demandeur, pour qui il n'y a rien à faire : la mesure a toujours son repère).
  //
  // Choix : la génération se fait AVANT le premier écran et l'état « pret » (la marque
  // prevo:preventif précède donc prevo:pret). Ainsi le premier écran (accueil : préventifs de la
  // semaine) montre déjà les OT du jour, aucune écriture ne court sous les doigts de l'utilisateur
  // (pas de réaffichage surprise, pas de conflit avec sa première action), et un autre poste ouvert
  // juste après lit des fichiers déjà à jour. Le coût est faible : sans gamme échue (presque toutes
  // les ouvertures), le contrôle se fait en mémoire, sans aucune écriture ; sinon deux écritures
  // (ordres_travail puis ot_operations) et le journal, une fois par jour et par gamme.
  //
  // formatAJour faux (passage au format courant impossible, faute de sauvegarde confirmée) : pas de
  // génération automatique à cette ouverture, car elle écrirait ordres_travail et ot_operations au
  // nouveau format (décision : pas de format 2 sans sauvegarde confirmée). L'erreur est déjà
  // signalée ; la prochaine ouverture retentera tout (sauvegarde, format, génération).
  async function genererPreventifAOuverture(formatAJour) {
    let crees = [];
    if (formatAJour && (estTechnicien() || estResponsable()) && typeof Preventif !== 'undefined') {
      try {
        crees = await Preventif.genererOTEchus();
      } catch (erreur) {
        // Fichier abîmé (T201) : aucune saisie à garder ici ; le bandeau « Fichier abîmé » de l'ouverture le dit.
        if (erreur instanceof Donnees.ErreurFichierAbime) {
          direFichierAbime(erreur.table);
          console.warn('Prévo (génération des OT préventifs à l\'ouverture) : ' + erreur.message, erreur);
        } else {
          signalerErreur(erreur, 'génération des OT préventifs à l\'ouverture');
        }
      }
    }
    if (!preventifDejaMarque && window.performance && typeof performance.mark === 'function') {
      preventifDejaMarque = true;
      performance.mark('prevo:preventif');
    }
    return crees;
  }

  // « Langue de Prévo » (T296, D149) : les langues déclarées, celle du navigateur proposée (UI.langueDuNavigateur).
  function demanderBaseVide() {
    UI.$('#texte-base-vide').textContent = I18n.t('socle.demander_base_vide.aucun_fichier_trouve',
      { n: Schema.nomsTables().length, stockage: adaptateur.libelle || mode });
    UI.remplir(UI.$('#base-vide-langue'), UI.optionsLangues(UI.langueDuNavigateur()));
    montrer('ecran-base-vide', 'demarrage');
    return new Promise((resoudre) => { resoudreBaseVide = resoudre; });
  }

  // Écrit les 23 fichiers (versionAttendue null : aucun ne doit exister, sinon ErreurConflit), avec langue_defaut
  // dans parametres.csv : la langue choisie sur l'écran (T296), lue ensuite par suivreLangueInstallation.
  async function remplirBaseVide(choix) {
    const contenus = {};
    const choisie = UI.$('#base-vide-langue').value;
    const langue = I18n.langues.some((declaree) => declaree.code === choisie) ? choisie : 'fr';
    if (choix === 'demo') {
      await chargerScriptDemo();
      // La ligne de la langue ajoutée au texte du jeu de démo (un code déclaré : rien à protéger), le reste tel quel.
      const tables = Object.assign({}, DEMO_DONNEES.tables, { parametres:
        DEMO_DONNEES.tables.parametres.replace(/(\r?\n)?$/, '\r\n') + PARAMETRE_LANGUE + ';' + langue + '\r\n' });
      Object.assign(contenus, StockageDemo.decalerDates(tables, DEMO_DONNEES.dateReference));
    } else {
      Schema.nomsTables().forEach((nomTable) => { contenus[nomTable] = Donnees.csv.serialiser(nomTable, []); });
      // Une base neuve est écrite au format courant : pas de sauvegarde « avant-format-v2 » inutile
      // au premier démarrage (ARCHITECTURE.md §14.1).
      contenus.parametres = Donnees.csv.serialiser('parametres', [{ cle: 'version_schema', valeur: String(Schema.version) },
        { cle: PARAMETRE_LANGUE, valeur: langue }]);
    }
    for (const nomTable of Schema.nomsTables()) {
      if (contenus[nomTable]) await adaptateur.enregistrer(nomTable, contenus[nomTable], null);
    }
  }

  // Mode dossier : avertit (sans bloquer) si une autre session semble ouverte, puis pose le verrou.
  // Un rechargement de l'onglet crée une nouvelle session : le verrou laissé par CET onglet (même
  // poste, marque dans sessionStorage, propre à l'onglet) ne déclenche pas l'avertissement.
  async function verifierVerrouDossier() {
    const resultat = await adaptateur.verifierVerrou();
    const autre = resultat && resultat.autreSession;
    let verrouDeCetOnglet = false;
    try { verrouDeCetOnglet = window.sessionStorage.getItem(CLE_VERROU_ONGLET) === poste; } catch (erreur) { /* sans mémoire */ }
    if (autre && !(verrouDeCetOnglet && autre.poste === poste)) {
      alertesCoque.push(UI.bandeau('attention', UI.html`${I18n.html('socle.verifier_verrou_dossier.dossier_semble_deja_ouvert', { poste: autre.poste, heure: autre.heure })}`));
    }
    await adaptateur.demarrerVerrou();
    try { window.sessionStorage.setItem(CLE_VERROU_ONGLET, poste); } catch (erreur) { /* sans mémoire */ }
  }

  // ===========================================================================================
  // 3 bis. Comptes et sessions (lot 7, §22.4 : connexion, profil déduit, déconnexion)
  // ===========================================================================================

  // GET /api/session au démarrage : sans comptes (portée « ce PC »), rien ne change ; avec, il faut une session
  // utilisable (connexion, enrôlement d'un appareil, mot de passe provisoire changé) avant de lire les tables.
  // T298 : vrai si la page se recharge pour la langue (suivreLangueDuCompte), avant la connexion (session absente
  // ou expirée : la langue du poste ou de l'installation) ou après (la langue du compte).
  async function ouvrirSession() {
    const etat = await adaptateur.session();
    comptesExiges = etat.comptes;
    session = null;
    if (!comptesExiges) return suivreLangueDuCompte(null);
    // Comptes exigés sans aucun compte responsable (configuration écrite à la main, §22.10) : personne ne peut se
    // connecter ; sur le PC serveur, l'assistant s'ouvre pour créer le premier compte (terminé, la page se recharge).
    if (!etat.session && etat.installationInachevee && pcServeur() && typeof Installation !== 'undefined') {
      montrer('ecran-installation', 'installation');
      await Installation.ouvrir();
    }
    if (etat.session && !etat.session.aChanger) {
      session = etat.session;
      return suivreLangueDuCompte(session);
    }
    if (suivreLangueDuCompte(null)) return true;
    const options = etat.session ? { sessionProvisoire: etat.session } : await motifSansSession();
    await demanderConnexion(options);
    return suivreLangueDuCompte(session);
  }

  // Langue du compte (T298 ; D148) : la session porte la langue du compte connecté ('' : la langue de l'installation) ;
  // retenue pour js/i18n-chargeur.js (localStorage « prevo.langue.compte »), elle passe avant le choix du poste. Sans
  // session de compte (sans comptes, appareil enrôlé, déconnexion, session expirée), la clé est effacée : la page
  // revient à la langue du poste ou de l'installation (poste ou tablette partagés). Valeur toujours vérifiée.
  function langueDuCompte(laSession) {
    const code = laSession && !laSession.appareil ? laSession.langue : '';
    return I18n.estDeclaree(code) ? code : '';
  }

  function noterLangueDuCompte(laSession) {
    const code = langueDuCompte(laSession);
    if (code) ecrireMemoire(CLE_LANGUE_COMPTE, code);
    else effacerMemoire(CLE_LANGUE_COMPTE);
    return code;
  }

  /** Note la langue du compte de `laSession` (ou l'efface) ; si la page n'est pas dans la langue que le chargeur
   *  choisirait alors (I18n.langueDeLaPage, mêmes clés), elle se recharge, une fois. Vrai si la page se recharge. */
  function suivreLangueDuCompte(laSession) {
    const compte = noterLangueDuCompte(laSession);
    let navigateur = [];
    try {
      navigateur = Array.from(navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language]);
    } catch (erreur) { /* navigateur sans langue lisible : anglais */ }
    const attendue = I18n.langueDeLaPage(lireMemoire(CLE_LANGUE_POSTE), lireMemoire(CLE_LANGUE_INSTALLATION),
      navigateur, compte);
    return attendue !== I18n.langue && rechargerPourLaLangue(attendue + '/' + I18n.installation);
  }

  /** T298 : langue du compte connecté changée sur le serveur (Connexion.changerLangue : POST /api/mot-de-passe
   *  {langue}) ; la session et la clé du chargeur suivent, la page ne se recharge pas. Refus du serveur : levé. */
  async function changerLangueDuCompte(code) {
    const nouvelle = await Connexion.changerLangue(code);
    session = Object.assign({}, session, { langue: nouvelle.langue });
    noterLangueDuCompte(session);
  }

  // Liste de langue du menu (T298) : un compte qui a sa langue la change pour le compte ; sinon le choix de ce poste.
  async function retenirLangueDuMenu(code) {
    if (!langueDuCompte(session)) return UI.retenirLangueDuPoste(code);
    try {
      await changerLangueDuCompte(code);
      return true;
    } catch (erreur) {
      signalerErreur(erreur, 'langue du compte');
      return false;
    }
  }

  // Sans session, GET /api/session (route publique) ne dit pas si un cookie d'appareil a été refusé : une lecture
  // protégée le dit (401 appareil_refuse, D125 ; le serveur efface alors le cookie), pour le bandeau de l'écran.
  async function motifSansSession() {
    try {
      await adaptateur.listerVersions();
    } catch (erreur) {
      if (erreur && erreur.sessionAbsente) return { appareilRefuse: Boolean(erreur.appareilRefuse) };
    }
    return {};
  }

  // Profil de l'interface tiré de la session : rôle → type, « Prénom Nom » (un appareil enrôlé : le nom saisi),
  // technicien lié → technicienId. Un rôle inconnu (comptes.json abîmé) donne le profil le plus restreint.
  function profilDepuisSession(laSession) {
    const type = TYPES_PROFIL.includes(laSession.role) ? laSession.role : 'demandeur';
    const nom = ((laSession.prenom || '') + ' ' + (laSession.nom || '')).trim();
    return { type, nom, technicienId: String(laSession.technicienId || '') };
  }

  /**
   * Écran de connexion (mode comptes) : promesse de la session ouverte, mot de passe choisi s'il était provisoire.
   * options : { sessionProvisoire } | { appareilRefuse, message } (voir Connexion.demander). Un seul écran à la fois :
   * un second appel pendant l'écran rend la même promesse. La route de la page est gardée (après la connexion, la
   * coque se rouvre dessus) ; une page ouverte sur #/enroler/<jeton> va à l'accueil une fois l'appareil enrôlé.
   */
  function demanderConnexion(options) {
    if (!promesseConnexion) {
      montrer('ecran-connexion', 'connexion');
      promesseConnexion = Connexion.demander(options || {}).then((nouvelle) => {
        promesseConnexion = null;
        session = nouvelle;
        if (Connexion.estRouteEnrolement(location.hash)) remplacerRoute(ROUTE_ACCUEIL);
        return nouvelle;
      });
    }
    return promesseConnexion;
  }

  // Session absente pendant l'usage (401 relu par stockage-serveur.js : expirée, fermée par le responsable, mot de
  // passe changé ailleurs, appareil révoqué) : l'écran de connexion par-dessus l'écran courant.
  // T329 (décisions de Nicolas du 07/11) : la page ne se recharge plus pour la langue (avant, quand la langue du compte
  // n'était pas celle du poste, la saisie était perdue sans message) : l'écran de connexion reste dans la langue où la
  // personne travaillait, avec un message qui dit quoi faire. L'écran courant reste tel quel, saisie comprise ; une
  // fenêtre ouverte est mise de côté (fermée, gardée dans la page) le temps de la connexion, sinon elle bloquerait
  // l'écran de connexion. Le même compte, avec les mêmes droits, retrouve l'écran et ses fenêtres tels qu'il les a
  // laissés, puis enregistre ; un autre compte, ou des droits changés : les fenêtres sont abandonnées (comme
  // « Annuler ») et l'écran reconstruit (tables relues) : la saisie n'est ni montrée ni enregistrée sous un autre nom.
  function surSessionAbsente(evenement) {
    if (!comptesExiges || !coqueVisible() || promesseConnexion) return;
    const detail = evenement.detail || {};
    reprendreApresSessionPerdue(session, Boolean(detail.appareilRefuse));
  }

  async function reprendreApresSessionPerdue(avant, appareilRefuse) {
    const defilement = window.scrollY;
    const actif = document.activeElement;
    const fenetres = mettreFenetresDeCote();
    await demanderConnexion(appareilRefuse ? { appareilRefuse }
      : { message: I18n.t('socle.session_perdue.reconnectez_vous_meme_compte') });
    if (!memesDroits(avant, session)) {
      abandonnerFenetres(fenetres);
      await rouvrirApresConnexion();
      return;
    }
    noterLangueDuCompte(session);
    montrer('app', 'pret');
    window.scrollTo(0, defilement);
    rouvrirFenetres(fenetres);
    if (!fenetres.length && actif && actif !== document.body && UI.$('#contenu').contains(actif)) {
      actif.focus({ preventScroll: true });
    }
    UI.toast(I18n.t('socle.session_perdue.reconnecte_saisie_gardee'), 'succes');
  }

  /** Même compte, même rôle, même technicien lié (T329) : la saisie lui est rendue. */
  function memesDroits(avant, apres) {
    return Boolean(avant && apres) && avant.identifiant === apres.identifiant && avant.role === apres.role
      && avant.technicienId === apres.technicienId && Boolean(avant.appareil) === Boolean(apres.appareil);
  }

  // Fenêtres ouvertes (<dialog>, UI.fenetre) : fermées sans être retirées (aucune réponse donnée), dictée arrêtée.
  function mettreFenetresDeCote() {
    const fenetres = UI.$$('dialog[open]');
    fenetres.forEach((dialogue) => {
      if (typeof Dictee !== 'undefined') Dictee.arreterDans(dialogue);
      dialogue.close();
    });
    return fenetres;
  }

  function rouvrirFenetres(fenetres) {
    fenetres.forEach((dialogue) => { if (dialogue.isConnected && !dialogue.open) dialogue.showModal(); });
  }

  // Comme Échap : UI.fenetre rend null (« Annuler ») et retire la fenêtre ; une autre fenêtre est retirée.
  function abandonnerFenetres(fenetres) {
    fenetres.forEach((dialogue) => {
      if (!dialogue.isConnected) return;
      dialogue.dispatchEvent(new Event('cancel', { cancelable: true }));
      if (dialogue.isConnected) dialogue.remove();
    });
  }

  // T329 : portée des brouillons gardés sur l'appareil (js/modules/brouillons.js) : la base et l'auteur, le compte
  // connecté (un appareil enrôlé : « appareil:<id> ») ou, sans comptes, le profil du poste. '' : aucun brouillon (démo,
  // lecture seule, personne de connu). Le nom d'un profil sans comptes est déclaratif : qui prend le même profil sur
  // ce poste voit ses brouillons, comme le reste de ce que fait ce profil.
  function porteeDesBrouillons() {
    if ((mode !== 'serveur' && mode !== 'dossier') || !adaptateur || Donnees.lectureSeule()) return '';
    const base = mode === 'dossier' ? 'dossier:' + String(adaptateur.nomDossier || '') : 'serveur';
    if (comptesExiges) return session && session.identifiant ? base + '|compte:' + session.identifiant : '';
    if (!profil) return '';
    return base + '|profil:' + profil.type + ':' + (profil.technicienId || profil.nom || '');
  }

  async function reconnecter(options) {
    await demanderConnexion(options);
    await rouvrirApresConnexion();
  }

  // Après une connexion (déconnexion puis connexion, ou autre compte après une session perdue) : la langue du compte,
  // son profil, les tables relues, la coque rouverte sur la même route.
  async function rouvrirApresConnexion() {
    if (suivreLangueDuCompte(session)) return;           // T298 : la langue du compte qui vient de se connecter
    appliquerProfil(profilDepuisSession(session));
    montrer('ecran-chargement', 'chargement');
    try {
      await Donnees.chargerTout();
    } catch (erreur) {
      signalerErreur(erreur, 'lecture des données après la connexion');
    }
    if (suivreLangueInstallation()) return;
    await ouvrirCoque();
  }

  /** Mode comptes : ferme la session sur le serveur (POST /api/deconnexion), puis l'écran de connexion. */
  async function deconnecter() {
    if (!comptesExiges || !session || promesseConnexion) return;
    if (session.appareil) {
      UI.toast(I18n.t('socle.deconnecter.appareil_enrole_sans_mot'), 'attention');
      return;
    }
    try {
      await Connexion.deconnecter();
    } catch (erreur) {
      signalerErreur(erreur, 'déconnexion');
      return;
    }
    session = null;
    if (suivreLangueDuCompte(null)) return;              // T298 : la langue du poste ou de l'installation
    await reconnecter({});
  }

  // Bouton de profil du menu latéral, bouton de l'en-tête mobile : « changer » de profil sans comptes, « se
  // déconnecter » avec ; rien pour un appareil enrôlé (seul le responsable le révoque).
  function mettreAJourBoutonsProfil() {
    const appareil = comptesExiges && Boolean(session) && session.appareil;
    const bouton = UI.$('#etat-poste');
    const changer = UI.$('#etat-poste .changer');
    changer.textContent = comptesExiges ? I18n.t('socle.mettre_ajour_boutons_profil.deconnecter') : I18n.t('socle.etat_poste.changer');
    changer.hidden = appareil;
    bouton.disabled = appareil;
    bouton.title = appareil ? I18n.t('socle.mettre_ajour_boutons_profil.appareil_enrole', { libelleAffiche: libelleAffiche(profil) })
      : comptesExiges ? I18n.t('socle.mettre_ajour_boutons_profil.connecte_cliquer_deconnecter', { libelleCompte: libelleCompte(profil) })
        : I18n.t('socle.mettre_ajour_boutons_profil.profil_poste_cliquer_changer', { libelleAffiche: libelleAffiche(profil), poste });
    const mobile = UI.$('#btn-profil-mobile');
    mobile.hidden = appareil;
    mobile.setAttribute('aria-label', comptesExiges ? I18n.t('socle.mettre_ajour_boutons_profil.deconnecter_bouton') : I18n.t('socle.mettre_ajour_boutons_profil.changer_profil'));
  }

  // ===========================================================================================
  // 4. Profils
  // ===========================================================================================

  function lireProfilMemorise() {
    const texte = lireMemoire(CLE_PROFIL);
    if (!texte) return null;
    try {
      const lu = JSON.parse(texte);
      if (!lu || !TYPES_PROFIL.includes(lu.type)) return null;
      return { type: lu.type, nom: String(lu.nom || ''), technicienId: String(lu.technicienId || '') };
    } catch (erreur) {
      return null;
    }
  }

  // Un profil mémorisé reste valable si son nom est connu (demandeur) et son technicien actif.
  function profilValable(candidat) {
    if (!candidat) return false;
    if (candidat.type === 'demandeur') return candidat.nom.trim() !== '';
    if (candidat.type === 'technicien') {
      const technicien = Donnees.trouver('techniciens', candidat.technicienId);
      return Boolean(technicien) && technicien.actif !== '0';
    }
    return true;
  }

  function nomTechnicien(technicien) {
    return ((technicien.prenom || '') + ' ' + (technicien.nom || '')).trim() || technicien.id;
  }

  // Libellé d'un type de profil (lu à chaque affichage, jamais figé au chargement) ; type inconnu : undefined.
  function libelleType(type) {
    switch (type) {
      case 'demandeur': return I18n.t('socle.libelle_type.demandeur');
      case 'technicien': return I18n.t('socle.libelle_type.technicien');
      case 'responsable': return I18n.t('socle.libelle_type.responsable');
      default: return undefined;
    }
  }

  // Texte inscrit au journal : « Responsable », « Demandeur Lucie Martin », « Technicien TEC-0002 » ; dans la langue de
  // l'installation, jamais celle de l'écran (D156).
  function libelleJournal(p) {
    if (p.type === 'demandeur') return I18n.donnees('socle.libelle_journal.demandeur_p_nom', { nom: p.nom });
    if (p.type === 'technicien') return I18n.donnees('socle.libelle_journal.technicien_technicien_id', { technicienId: p.technicienId });
    return I18n.enLangueDesDonnees(() => libelleType(p.type));
  }

  // Texte affiché dans le menu : « Technicien · Julien Moreau ».
  function libelleAffiche(p) {
    if (!p) return '';
    return p.type === 'responsable' ? libelleType('responsable') : libelleType(p.type) + ' · ' + p.nom;
  }

  // Texte du menu en mode comptes : « Nicolas Briand · Responsable » (le compte fait foi, pas le poste).
  function libelleCompte(p) {
    if (!p) return '';
    return (p.nom ? p.nom + ' · ' : '') + libelleType(p.type);
  }

  function appliquerProfil(nouveau) {
    profil = nouveau;
    if (profil.type === 'technicien') {
      const technicien = Donnees.trouver('techniciens', profil.technicienId);
      if (technicien) profil.nom = nomTechnicien(technicien);
    }
    // Mode comptes : le profil n'est plus mémorisé sur le poste (la session fait foi) ; le nom du poste, si.
    if (!comptesExiges) ecrireMemoire(CLE_PROFIL, JSON.stringify(profil));
    ecrireMemoire(CLE_POSTE, poste);
    Donnees.definirIdentite({ poste, profil: libelleJournal(profil) });
    UI.$('#libelle-profil').textContent = comptesExiges ? libelleCompte(profil) : libelleAffiche(profil) + ' · ' + poste;
    mettreAJourBoutonsProfil();
  }

  // Affiche l'écran de profil. Renvoie une promesse : le profil choisi, ou null si « Annuler ».
  function demanderProfil(annulable) {
    UI.$('#profil-poste').value = poste;
    UI.$('#profil-annuler').hidden = !annulable;
    const precedent = lireProfilMemorise();
    UI.$('#profil-nom').value = precedent && precedent.type === 'demandeur' ? precedent.nom : '';
    remplirListeTechniciens();
    montrerPanneauProfil('profil-choix');
    montrer('ecran-profil', 'profil');
    return new Promise((resoudre) => { resoudreProfil = resoudre; });
  }

  function remplirListeTechniciens() {
    const actifs = Donnees.lignes('techniciens').filter((t) => t.actif !== '0')
      .sort((a, b) => UI.comparerTextes(nomTechnicien(a), nomTechnicien(b)));
    const zone = UI.$('#profil-techniciens');
    if (!actifs.length) {
      UI.remplir(zone, UI.html`<p class="note">${I18n.t('socle.remplir_liste_techniciens.aucun_technicien_actif_techniciens')}</p>`);
      return;
    }
    UI.remplir(zone, UI.html`${actifs.map((t) => UI.html`
      <button type="button" class="btn btn-secondaire btn-gros" data-technicien="${t.id}">
        ${UI.icone('utilisateur')}<span>${nomTechnicien(t)}<small>${t.metier || t.id}</small></span>
      </button>`)}`);
  }

  // Un seul des trois panneaux de l'écran de profil est visible : choix, demandeur, technicien.
  function montrerPanneauProfil(idPanneau) {
    ['profil-choix', 'profil-panneau-demandeur', 'profil-panneau-technicien'].forEach((id) => {
      UI.$('#' + id).hidden = id !== idPanneau;
    });
    const erreur = UI.$('#profil-nom-erreur');
    erreur.hidden = true;
    UI.$('#profil-nom').removeAttribute('aria-invalid');
  }

  function terminerProfil(choix) {
    if (!resoudreProfil) return;
    if (choix) poste = UI.$('#profil-poste').value.trim().replace(/[;\r\n]+/g, ' ') || poste;
    const resoudre = resoudreProfil;
    resoudreProfil = null;
    resoudre(choix);
  }

  function validerDemandeur(evenement) {
    evenement.preventDefault();
    const champNom = UI.$('#profil-nom');
    const nom = champNom.value.trim().replace(/[;\r\n]+/g, ' ');
    if (!nom) {
      const erreur = UI.$('#profil-nom-erreur');
      erreur.textContent = I18n.t('socle.valider_demandeur.indiquez_nom_permet_retrouver');
      erreur.hidden = false;
      champNom.setAttribute('aria-invalid', 'true');
      champNom.focus();
      return;
    }
    terminerProfil({ type: 'demandeur', nom, technicienId: '' });
  }

  /** Change de profil sans recharger la page (en démo, recharger ferait tout perdre). Mode comptes : se déconnecter. */
  async function changerProfil() {
    if (!adaptateur || !profil || resoudreProfil) return;
    if (comptesExiges) {
      await deconnecter();
      return;
    }
    const nouveau = await demanderProfil(true);
    if (nouveau) {
      appliquerProfil(nouveau);
      UI.toast(I18n.t('socle.changer_profil.profil_libelle_affiche', { libelleAffiche: libelleAffiche(profil) }), 'succes');
    }
    await ouvrirCoque();
  }

  function estResponsable() { return Boolean(profil) && profil.type === 'responsable'; }
  function estTechnicien() { return Boolean(profil) && profil.type === 'technicien'; }
  function estDemandeur() { return Boolean(profil) && profil.type === 'demandeur'; }

  /** Mode Solo (D132) : mode_solo = 1 dans parametres.csv ET profil responsable (pas un quatrième profil). */
  function modeSolo() {
    return estResponsable() && Boolean(adaptateur) && String(Donnees.parametre('mode_solo', '0')).trim() === '1';
  }

  /** Identifiant du technicien « moi » du mode Solo (solo_technicien_id), '' hors mode Solo ou s'il est introuvable. */
  function technicienSolo() {
    if (!modeSolo()) return '';
    const id = String(Donnees.parametre('solo_technicien_id', '')).trim();
    return id && Donnees.trouver('techniciens', id) ? id : '';
  }

  // ===========================================================================================
  // 5. Coque : menu latéral, barre du bas, bandeaux
  // ===========================================================================================

  async function ouvrirCoque() {
    montrer('app');
    UI.$('#bandeau-demo').hidden = mode !== 'demo';
    afficherAlertesCoque();
    afficherLectureSeule();
    appliquerRepli(lireMemoire(CLE_MENU_REPLIE) === '1');
    mettreAJourEntreprise();
    placerSelecteurLangue();
    if (!location.hash || location.hash === '#' || location.hash === '#/'
        || (typeof Connexion !== 'undefined' && Connexion.estRouteEnrolement(location.hash))) remplacerRoute(ROUTE_ACCUEIL);
    construireMenus();
    await afficherRoute(false);
    document.documentElement.dataset.etat = 'pret';
    if (!pretDejaMarque) {
      pretDejaMarque = true;
      if (window.performance && typeof performance.mark === 'function') performance.mark('prevo:pret');
      // Mise à jour signalée (D120) : une lecture par jour et par poste, seulement si le responsable l'a autorisée.
      if (typeof MiseAJour !== 'undefined') MiseAJour.verifier();
      // T329 : brouillons de plus de 7 jours effacés de cet appareil (tous les auteurs).
      if (typeof Brouillons !== 'undefined') Brouillons.purger();
      // T323 : mode Solo sans technicien « moi » reconnu (import ZIP, fiche supprimée) : la question, sans deviner.
      if (modeSolo() && !technicienSolo() && typeof Parametres !== 'undefined' && Parametres.interne.demanderMoiSolo
          && !Donnees.lectureSeule()) Parametres.interne.demanderMoiSolo();
    }
  }

  function afficherAlertesCoque() {
    const zone = UI.$('#alertes-app');
    alertesCoque.splice(0).forEach((bandeau) => {
      const fermer = UI.element(UI.html`<button type="button" class="btn btn-fantome">${I18n.t('commun.bouton.fermer')}</button>`);
      fermer.addEventListener('click', () => {
        bandeau.remove();
        zone.hidden = zone.children.length === 0;
      });
      bandeau.appendChild(fermer);
      zone.appendChild(bandeau);
    });
    zone.hidden = zone.children.length === 0;
  }

  // En-tête du menu latéral (D32, T89) : « Prévo », « GMAO », puis le nom de l'entreprise sur sa propre
  // ligne, en entier (app.css) ; il reste aussi en infobulle.
  function mettreAJourEntreprise() {
    const nom = adaptateur ? String(Donnees.parametre('entreprise_nom', '')).trim() : '';
    const zone = UI.$('#nom-entreprise');
    zone.textContent = nom;
    zone.title = nom;
    zone.hidden = !nom;
  }

  // Pied du menu latéral (D147, T278) : la liste des langues seule, nommée par son aria-label ; même liste que l'écran
  // « Ce poste » (UI.selecteurLangue). Refaite à chaque ouverture de la coque. Cachée quand le menu n'a que ses icônes.
  function placerSelecteurLangue() {
    const zone = UI.$('#menu-langue');
    if (!zone) return;
    UI.remplir(zone, UI.selecteurLangue({ id: 'menu-langue-liste',
      libelle: I18n.t('socle.selecteur_langue.langue_ecran'), retenir: retenirLangueDuMenu }));
    // T306 : « Suggérer une amélioration », sous la langue (l'adresse suit la langue active) ; cachée avec elle.
    const suggestion = UI.$('#menu-suggestion');
    if (suggestion) UI.remplir(suggestion, Apropos.lienSuggestion('menu-suggestion-lien'));
  }

  function appliquerRepli(replie) {
    UI.$('#app').classList.toggle('replie', replie);
    const bouton = UI.$('#btn-replier');
    bouton.setAttribute('aria-expanded', String(!replie));
    bouton.setAttribute('aria-label', replie ? I18n.t('socle.appliquer_repli.deplier_menu') : I18n.t('socle.appliquer_repli.replier_menu'));
  }

  function basculerRepli() {
    const replie = !UI.$('#app').classList.contains('replie');
    appliquerRepli(replie);
    ecrireMemoire(CLE_MENU_REPLIE, replie ? '1' : '0');
  }

  function ecranAutorise(ecran) {
    return Boolean(profil) && (!ecran.profils || ecran.profils.includes(profil.type));
  }

  // '#/di' depuis /^#\/di$/ (routes simples) ; sinon menu.lien est obligatoire.
  function lienDepuisRoute(route) {
    return route.source.replace(/^\^/, '').replace(/\$$/, '').replace(/\\\//g, '/');
  }

  function entreesMenu() {
    return ecrans.filter((ecran) => ecran.menu && ecranAutorise(ecran))
      .sort((a, b) => (a.menu.ordre || 0) - (b.menu.ordre || 0));
  }

  function lienEntree(ecran) {
    return ecran.menu.lien || lienDepuisRoute(ecran.route);
  }

  // Entrées du menu partagées en deux : principales, et celles rangées sous « Plus » en mode Solo (vide sinon).
  function partagerEntrees() {
    const entrees = entreesMenu();
    if (!modeSolo()) return { principales: entrees, sousPlus: [] };
    return {
      principales: entrees.filter((ecran) => !ECRANS_SOUS_PLUS_SOLO.includes(ecran.id)),
      sousPlus: entrees.filter((ecran) => ECRANS_SOUS_PLUS_SOLO.includes(ecran.id)),
    };
  }

  function lienMenu(ecran) {
    return UI.html`<a href="${lienEntree(ecran)}" data-ecran="${ecran.id}" title="${ecran.menu.libelle}">${UI.icone(ecran.menu.icone || 'chevron')}<span class="libelle">${ecran.menu.libelle}</span></a>`;
  }

  function construireMenus() {
    const { principales, sousPlus } = partagerEntrees();
    const morceaux = [];
    let groupeCourant = '';
    principales.forEach((ecran) => {
      const groupe = ecran.menu.groupe || '';
      if (groupe && groupe !== groupeCourant) morceaux.push(UI.html`<div class="menu-groupe">${groupe}</div>`);
      groupeCourant = groupe;
      morceaux.push(lienMenu(ecran));
    });
    // Mode Solo : groupe « Plus » repliable (bouton réel, aria-expanded) ; replié par défaut.
    if (sousPlus.length) {
      morceaux.push(UI.html`<div class="menu-plus">
        <button type="button" class="menu-plus-bouton" id="btn-menu-plus" aria-expanded="false" aria-controls="menu-plus-liste" title="${I18n.t('socle.construire_menus.plus')}">${UI.icone('plus')}<span class="libelle">${I18n.t('socle.construire_menus.plus')}</span></button>
        <div class="menu-plus-liste" id="menu-plus-liste" hidden>${sousPlus.map(lienMenu)}</div>
      </div>`);
    }
    UI.remplir(UI.$('#menu'), morceaux);
    const boutonPlus = UI.$('#btn-menu-plus');
    if (boutonPlus) boutonPlus.addEventListener('click', () => deplierMenuPlus(!menuPlusOuvert));

    const enBas = principales.slice(0, ENTREES_BARRE_BAS);
    UI.remplir(UI.$('#barre-bas'), UI.html`${enBas.map((ecran) => UI.html`<a href="${lienEntree(ecran)}" data-ecran="${ecran.id}">${UI.icone(ecran.menu.icone || 'chevron')}<span class="libelle">${ecran.menu.court || ecran.menu.libelle}</span></a>`)}
      <button type="button" id="btn-plus" aria-haspopup="dialog">${UI.icone('plus')}<span class="libelle">${I18n.t('socle.construire_menus.plus')}</span></button>`);
    UI.$('#btn-plus').addEventListener('click', ouvrirPlus);
    allumerMenus();
  }

  // Mode Solo : déplie (vrai) ou replie le groupe « Plus » du menu latéral.
  function deplierMenuPlus(ouvert) {
    const bouton = UI.$('#btn-menu-plus');
    const liste = UI.$('#menu-plus-liste');
    if (!bouton || !liste) return;
    menuPlusOuvert = ouvert;
    bouton.setAttribute('aria-expanded', String(ouvert));
    liste.hidden = !ouvert;
  }

  // Entrée active (et aria-current) dans le menu latéral et la barre du bas.
  function allumerMenus() {
    const idActif = ecranCourant ? (ecranCourant.parent || ecranCourant.id) : '';
    UI.$$('#menu a, #barre-bas a').forEach((lien) => {
      const actif = lien.dataset.ecran === idActif;
      lien.classList.toggle('actif', actif);
      if (actif) lien.setAttribute('aria-current', 'page'); else lien.removeAttribute('aria-current');
    });
    // Mode Solo : l'écran ouvert est sous « Plus » → le groupe est déplié (sinon il garde son état).
    const boutonPlus = UI.$('#btn-menu-plus');
    if (boutonPlus) {
      const dansPlus = UI.$$('#menu-plus-liste a').some((lien) => lien.dataset.ecran === idActif);
      boutonPlus.classList.toggle('actif', dansPlus);
      deplierMenuPlus(menuPlusOuvert || dansPlus);
    }
    const plus = UI.$('#btn-plus');
    if (plus) {
      const dansLaBarre = UI.$$('#barre-bas a').some((lien) => lien.dataset.ecran === idActif);
      plus.classList.toggle('actif', Boolean(idActif) && !dansLaBarre);
    }
  }

  // « Plus » (téléphone) : les entrées qui n'ont pas de place dans la barre du bas + actions du poste.
  function ouvrirPlus() {
    const idActif = ecranCourant ? (ecranCourant.parent || ecranCourant.id) : '';
    const { principales, sousPlus } = partagerEntrees();
    const reste = principales.slice(ENTREES_BARRE_BAS).concat(sousPlus);
    // Mode comptes : « Se déconnecter » à la place de « Changer de profil » ; rien pour un appareil enrôlé.
    const appareil = comptesExiges && Boolean(session) && session.appareil;
    const contenu = UI.element(UI.html`<ul class="liste-plus">
      ${reste.map((ecran) => UI.html`<li><a href="${lienEntree(ecran)}" class="${ecran.id === idActif ? 'actif' : ''}">${UI.icone(ecran.menu.icone || 'chevron')}${ecran.menu.libelle}</a></li>`)}
      ${appareil ? '' : UI.html`<li><a href="#" data-action="profil">${UI.icone('utilisateur')}${comptesExiges ? I18n.t('socle.ouvrir_plus.deconnecter_libelle_compte', { libelleCompte: libelleCompte(profil) }) : I18n.t('socle.ouvrir_plus.changer_profil', { libelleAffiche: libelleAffiche(profil) })}</a></li>`}
      ${mode === 'demo' ? UI.html`<li><a href="#" data-action="zip">${UI.icone('export')}${I18n.t('socle.ouvrir_plus.exporter_zip')}</a></li>` : ''}
    </ul>`);
    UI.fenetre({
      titre: I18n.t('socle.construire_menus.plus'), classe: 'feuille', contenu,
      boutons: [{ libelle: I18n.t('commun.bouton.fermer'), valeur: null, classe: 'btn-secondaire', defaut: true }],
      surOuverture(dialogue, fermer) {
        contenu.addEventListener('click', (evenement) => {
          const lien = evenement.target.closest('a');
          if (!lien) return;
          const action = lien.dataset.action;
          if (action) evenement.preventDefault();
          fermer(null);
          if (action === 'profil') changerProfil();
          if (action === 'zip') exporterZip();
        });
      },
    });
  }

  // ===========================================================================================
  // 6. Navigation (routes en #/…)
  // ===========================================================================================

  /** Enregistre un écran (voir le contrat en tête de fichier). */
  function ecran(definition) {
    if (!definition || !definition.id || !(definition.route instanceof RegExp) || typeof definition.afficher !== 'function') {
      throw new Error(I18n.t('socle.ecran.app_ecran_id_route'));
    }
    if (ecrans.some((e) => e.id === definition.id)) {
      throw new Error(I18n.t('socle.ecran.app_ecran_ecran_deja', { definitionId: definition.id }));
    }
    ecrans.push(definition);
    if (coqueVisible()) construireMenus();
  }

  function analyserHash(hash) {
    const texte = hash || '';
    const position = texte.indexOf('?');
    return {
      chemin: position === -1 ? texte : texte.slice(0, position),
      requete: new URLSearchParams(position === -1 ? '' : texte.slice(position + 1)),
    };
  }

  function decoder(valeur) {
    if (valeur === undefined) return undefined;
    try { return decodeURIComponent(valeur); } catch (erreur) { return valeur; }
  }

  function trouverEcran(chemin) {
    for (const candidat of ecrans) {
      const correspondance = candidat.route.exec(chemin);
      if (correspondance) return { ecran: candidat, correspondance };
    }
    return null;
  }

  // Change le hash sans déclencher hashchange (pas de double affichage).
  function remplacerRoute(hash) {
    try {
      history.replaceState(history.state, '', hash);
    } catch (erreur) {
      location.replace(hash);
    }
  }

  /** Va vers une route : App.naviguer('#/di/DI-2026-0042'). Même route : l'écran est réaffiché. */
  function naviguer(hash) {
    if (location.hash === hash) afficherRoute(false);
    else location.hash = hash;
  }

  async function afficherRoute(garderDefilement) {
    if (!coqueVisible() || !profil) return;
    const { chemin, requete } = analyserHash(location.hash);
    const trouve = trouverEcran(chemin);
    if (!trouve || !ecranAutorise(trouve.ecran)) {
      if (trouve) UI.toast(I18n.t('socle.route.ecran_pas_disponible_profil', { ecranTitre: trouve.ecran.titre, profil: libelleType(profil.type) }), 'attention');
      const accueil = trouverEcran(ROUTE_ACCUEIL);
      if (chemin !== ROUTE_ACCUEIL && accueil && ecranAutorise(accueil.ecran)) {
        remplacerRoute(ROUTE_ACCUEIL);
        await afficherRoute(false);
      } else {
        ecranCourant = null;
        UI.remplir(UI.$('#contenu'), UI.vide(I18n.t('socle.route.ecran_introuvable'), I18n.t('socle.route.aucun_ecran_correspond_adresse')));
      }
      return;
    }
    const correspondance = trouve.correspondance;
    const parametres = { groupes: correspondance.slice(1).map(decoder), requete, chemin };
    Object.keys(correspondance.groups || {}).forEach((nom) => { parametres[nom] = decoder(correspondance.groups[nom]); });
    await rendre(trouve.ecran, parametres, garderDefilement);
  }

  async function rendre(ecranAAfficher, parametres, garderDefilement) {
    const conteneur = UI.$('#contenu');
    const defilement = window.scrollY;
    const nouvelEcran = ecranCourant !== ecranAAfficher;
    numeroAffichage += 1;
    const numero = numeroAffichage;
    ecranCourant = ecranAAfficher;
    saisieEnCours = false;
    UI.$('#bandeau-changement').hidden = true;
    definirTitre(ecranAAfficher.titre);
    allumerMenus();
    conteneur.textContent = '';
    try {
      await ecranAAfficher.afficher(conteneur, parametres);
    } catch (erreur) {
      if (numero === numeroAffichage) {
        UI.remplir(conteneur, UI.html`<div class="entete-page"><h1>${ecranAAfficher.titre}</h1></div>`);
        const message = (erreur && erreur.message) || '';
        conteneur.appendChild(UI.bandeau('important', UI.html`${I18n.html('socle.rendre.ecran_pas_pu_afficher', { message })}`));
      }
      if (!estErreurDonnees(erreur)) throw erreur;     // défaut du code : il doit se voir
      signalerErreur(erreur, 'affichage de « ' + ecranAAfficher.titre + ' »');
    }
    if (numero !== numeroAffichage) return;
    // Aide à l'écran (§23) : encart de la première visite, après un affichage réussi d'un écran nouveau.
    if (nouvelEcran && typeof AideEcrans !== 'undefined' && conteneur.childElementCount
        && !conteneur.querySelector(':scope > .entete-page + .alerte.important')) {
      try { AideEcrans.apresAffichage(ecranAAfficher, conteneur); } catch (erreur) { console.warn('Prévo : aide à l\'écran non affichée.', erreur); }
    }
    if (garderDefilement) window.scrollTo(0, defilement);
    else window.scrollTo(0, 0);
    if (nouvelEcran && !garderDefilement && document.activeElement !== conteneur
        && !conteneur.contains(document.activeElement)) {
      conteneur.focus({ preventScroll: true });          // lecteurs d'écran : on est sur le nouvel écran
    }
  }

  /** Titre de l'onglet et de l'en-tête mobile (un écran peut le préciser : « OT-2026-0107 »). */
  function definirTitre(texte) {
    document.title = texte ? I18n.t('socle.definir_titre.texte_prevo', { texte }) : I18n.t('socle.definir_titre.prevo_gmao');
    UI.$('#titre-mobile').textContent = texte || I18n.t('socle.definir_titre.prevo');
  }

  /**
   * En-tête mobile seul, sur deux lignes (T90 : « Bonjour » et la date sur l'accueil du responsable) ;
   * le titre de l'onglet ne change pas, et l'écran suivant remet son titre (definirTitre).
   */
  function definirTitreMobile(titre, detail) {
    UI.remplir(UI.$('#titre-mobile'), UI.html`<span>${titre}</span>${detail ? UI.html`<small>${detail}</small>` : ''}`);
  }

  /** Réaffiche l'écran courant (défilement conservé). */
  function reafficher() {
    return afficherRoute(true);
  }

  /** Signale (true, défaut) ou efface (false) une saisie en cours dans l'écran courant. */
  function marquerSaisie(enCours) {
    saisieEnCours = enCours !== false;
  }

  function surSaisie(evenement) {
    if (evenement.target && evenement.target.closest && evenement.target.closest('[data-hors-saisie]')) return;
    saisieEnCours = true;
  }

  // Données changées : sur un autre poste → réaffichage (ou bandeau si une saisie est en cours).
  function surChangement(evenement) {
    const detail = evenement.detail || {};
    const tables = detail.tables || [];
    if (tables.includes('parametres')) {
      // langue_defaut a pu changer : un changement d'un autre poste n'interrompt pas une saisie en cours.
      if (suivreLangueInstallation(detail.origine !== 'distant' || !saisieEnCours)) return;
      mettreAJourEntreprise();
      // mode_solo a pu changer (ce poste ou un autre) : le menu suit.
      if (coqueVisible() && profil) construireMenus();
    }
    if (detail.origine !== 'distant' || !ecranCourant || !coqueVisible()) return;
    const tablesEcran = ecranCourant.tables || [];
    if (!tables.some((nomTable) => tablesEcran.includes(nomTable))) return;
    if (saisieEnCours) {
      UI.$('#bandeau-changement').hidden = false;
      return;
    }
    reafficher();
  }

  // ===========================================================================================
  // 7. Export ZIP (tous modes) et adresse des fiches équipement
  // ===========================================================================================

  /**
   * Télécharge prevo-export-AAAA-MM-JJ.zip (D171, T189) : ZipDonnees.exporter (js/modules/zip-donnees.js) y met les
   * 24 CSV, les documents cités, les rapports mensuels figés et manifeste.json, jamais acces/. Avec les comptes,
   * réservé au responsable (sinon la raison est montrée) ; permis en lecture seule. Promise du résultat de
   * ZipDonnees.contenu, ou undefined (rien d'ouvert, ou erreur déjà signalée). options.sansDocuments (T214) : données
   * seules, sans les documents (prevo-export-AAAA-MM-JJ-sans-documents.zip).
   */
  async function exporterZip(options) {
    if (!adaptateur) return undefined;
    try {
      return await ZipDonnees.exporter(options);
    } catch (erreur) {
      signalerErreur(erreur, 'export ZIP');
      return undefined;
    }
  }

  /** Texte du QR d'une fiche équipement : URL réseau en mode serveur, sinon « GMAO:<id> ». */
  // Lot 3 (§15.1) : l'adresse choisie pour les étiquettes (paramètre adresse_qr) passe avant la
  // première adresse détectée ; une valeur qui n'est pas une adresse http(s) est ignorée.
  function urlFicheEquipement(id) {
    if (mode !== 'serveur') return 'GMAO:' + id;
    const choisie = String(Donnees.parametre('adresse_qr', '') || '').trim();
    const base = (/^https?:\/\/\S+$/i.test(choisie) ? choisie : '')
      || adressesReseau[0] || (location.protocol + '//' + location.host + '/');
    return base.replace(/\/+$/, '') + '/#/equipement/' + encodeURIComponent(id);
  }

  /** Adresses réseau du PC (mode serveur ; liste vide sinon) : une copie, pour le choix de l'adresse des QR. */
  function adressesDuReseau() {
    return mode === 'serveur' ? adressesReseau.slice() : [];
  }

  // ===========================================================================================
  // 8. Écouteurs (installés une seule fois)
  // ===========================================================================================

  function installerEcouteurs() {
    // Écran de démarrage
    const ecranDemarrage = UI.$('#ecran-demarrage');
    UI.$('#btn-dossier').addEventListener('click', () => pendantAction(ecranDemarrage, choisirDossier));
    UI.$('#btn-reprendre').addEventListener('click', () => pendantAction(ecranDemarrage, reprendreDossier));
    UI.$('#btn-demo').addEventListener('click', () => pendantAction(ecranDemarrage, essayerDemo));
    const champFichiers = UI.$('#fichiers-csv');
    champFichiers.addEventListener('change', () => {
      const fichiers = Array.from(champFichiers.files || []);
      champFichiers.value = '';
      pendantAction(ecranDemarrage, () => ouvrirFichiersDeposes(fichiers));
    });
    const zoneDepot = UI.$('#zone-depot');
    zoneDepot.addEventListener('dragover', (evenement) => { evenement.preventDefault(); zoneDepot.classList.add('survol'); });
    zoneDepot.addEventListener('dragleave', () => zoneDepot.classList.remove('survol'));
    zoneDepot.addEventListener('drop', (evenement) => {
      evenement.preventDefault();
      zoneDepot.classList.remove('survol');
      const fichiers = Array.from((evenement.dataTransfer && evenement.dataTransfer.files) || []);
      pendantAction(ecranDemarrage, () => ouvrirFichiersDeposes(fichiers));
    });
    // Un fichier lâché à côté de la zone ne doit pas remplacer la page.
    window.addEventListener('dragover', (evenement) => evenement.preventDefault());
    window.addEventListener('drop', (evenement) => evenement.preventDefault());

    // Assistant d'installation (§22.10) : le lien des écrans de démarrage recharge la page sur #/installation
    // (l'assistant s'ouvre avant toute lecture de table : rien à perdre au démarrage).
    UI.$$('.lien-installation a').forEach((lien) => lien.addEventListener('click', (evenement) => {
      evenement.preventDefault();
      location.hash = ROUTE_INSTALLATION;
      location.reload();
    }));

    // Base vide
    UI.$('#btn-base-demo').addEventListener('click', () => { if (resoudreBaseVide) resoudreBaseVide('demo'); resoudreBaseVide = null; });
    UI.$('#btn-base-vide').addEventListener('click', () => { if (resoudreBaseVide) resoudreBaseVide('vide'); resoudreBaseVide = null; });

    // Profil
    UI.$('#profil-responsable').addEventListener('click', () => terminerProfil({ type: 'responsable', nom: '', technicienId: '' }));
    UI.$('#profil-demandeur').addEventListener('click', () => { montrerPanneauProfil('profil-panneau-demandeur'); UI.$('#profil-nom').focus(); });
    UI.$('#profil-technicien').addEventListener('click', () => {
      montrerPanneauProfil('profil-panneau-technicien');
      const premier = UI.$('#profil-techniciens button');
      if (premier) premier.focus();
    });
    UI.$('#profil-panneau-demandeur').addEventListener('submit', validerDemandeur);
    UI.$('#profil-nom').addEventListener('input', () => {
      UI.$('#profil-nom-erreur').hidden = true;
      UI.$('#profil-nom').removeAttribute('aria-invalid');
    });
    UI.$('#profil-techniciens').addEventListener('click', (evenement) => {
      const bouton = evenement.target.closest('[data-technicien]');
      if (!bouton) return;
      const technicien = Donnees.trouver('techniciens', bouton.dataset.technicien);
      if (technicien) terminerProfil({ type: 'technicien', nom: nomTechnicien(technicien), technicienId: technicien.id });
    });
    UI.$$('#ecran-profil [data-retour]').forEach((bouton) => bouton.addEventListener('click', () => montrerPanneauProfil('profil-choix')));
    UI.$('#profil-annuler').addEventListener('click', () => terminerProfil(null));

    // Coque
    UI.$('#btn-replier').addEventListener('click', basculerRepli);
    UI.$('#etat-poste').addEventListener('click', () => changerProfil());
    UI.$('#btn-profil-mobile').addEventListener('click', () => changerProfil());
    ['#btn-explications', '#btn-explications-mobile'].forEach((selecteur) => {
      UI.$(selecteur).addEventListener('click', () => { if (typeof AideEcrans !== 'undefined') AideEcrans.rouvrir(); });
    });
    UI.$('#btn-export-demo').addEventListener('click', () => exporterZip());
    UI.$('#btn-actualiser').addEventListener('click', () => reafficher());
    UI.$('#contenu').addEventListener('input', surSaisie);
    UI.$('#contenu').addEventListener('change', surSaisie);
    window.addEventListener('hashchange', () => { afficherRoute(false); });
    Donnees.evenements.addEventListener('changement', surChangement);
    // Lecture seule découverte pendant l'usage (parametres relu : un autre poste a ouvert la base avec une version
    // plus récente de Prévo) : le bandeau permanent apparaît sur l'écran en cours.
    Donnees.evenements.addEventListener('lectureSeule', () => { if (coqueVisible()) afficherLectureSeule(); });
    // Fichier abîmé découvert par une écriture refusée (T200 : journal qui finit par un guillemet ouvert, abîmé après
    // l'ouverture) : bandeau « Fichier abîmé », seulement pour une table pas encore signalée (ni à l'ouverture, ni par
    // le passage au format) ; tout de suite si la coque est affichée, sinon à son ouverture (afficherAlertesCoque).
    Donnees.evenements.addEventListener('fichierAbime', (evenement) => {
      direFichierAbime(evenement.detail && evenement.detail.table);
    });
    // Lot 7 (§22.4) : session absente ou appareil refusé pendant l'usage (401) → écran de connexion.
    if (typeof StockageServeur !== 'undefined') {
      document.addEventListener(StockageServeur.EVENEMENT_SESSION_ABSENTE, surSessionAbsente);
    }

    // Erreurs de Donnees non attrapées par un module : message clair plutôt qu'une erreur console.
    window.addEventListener('unhandledrejection', (evenement) => {
      if (estErreurDonnees(evenement.reason)) {
        evenement.preventDefault();
        signalerErreur(evenement.reason);
      }
    });
  }

  // js/app.js est le dernier script : les modules ont déjà ajouté leurs écouteurs DOMContentLoaded
  // (qui enregistrent leurs écrans) ; celui-ci passe après eux.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => { demarrer(); });
  } else {
    setTimeout(demarrer, 0);
  }

  return {
    version: VERSION,
    dateVersion: DATE_VERSION,
    versionWeb: VERSION_WEB,
    get mode() { return mode; },
    get adaptateur() { return adaptateur; },
    get profil() { return profil ? Object.assign({}, profil) : null; },
    get session() { return session ? Object.assign({}, session) : null; },
    get poste() { return poste; },
    get ecranCourant() { return ecranCourant; },
    ecran,
    naviguer,
    reafficher,
    definirTitre,
    definirTitreMobile,
    marquerSaisie,
    estResponsable,
    estTechnicien,
    estDemandeur,
    modeSolo,
    technicienSolo,
    libelleProfil: () => libelleAffiche(profil),
    urlFicheEquipement,
    adressesReseau: adressesDuReseau,
    chargerScriptDemo,
    chargerEcharts,
    chargerSheetJS,
    changerProfil,
    comptesExiges: () => comptesExiges,
    installationAFaire: () => installationAFaire,
    cePcSeulement: () => cePcSeulement,
    pcServeur,
    demanderConnexion,
    deconnecter,
    changerLangueDuCompte,
    porteeDesBrouillons,
    exporterZip,
    signalerErreur,
    messageErreur,
    raisonErreur,
  };
})();
