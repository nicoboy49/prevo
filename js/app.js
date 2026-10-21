'use strict';
// App : démarrage de Prévo, choix du mode de stockage, profils, navigation (ARCHITECTURE.md §8).
//
// Déroulé du démarrage :
//   1. page servie en http(s) et serveur Prévo qui répond → mode serveur ;
//      sinon écran de démarrage : dossier (File System Access), dossier précédent, démo, CSV déposés ;
//      version web (VERSION_WEB, démo en ligne) : pas de serveur cherché, la démo seule et
//      « Télécharger Prévo » ;
//   2. chargement des 22 tables ; base vide (serveur ou dossier) → « Partir des données de démo »
//      ou « Créer une base vide » ; puis passage des fichiers au format courant (version_schema,
//      sauvegarde « avant-format-v2 » d'abord), avant toute autre écriture ;
//   3. profil (mémorisé sur le poste) ; la route demandée avant (QR scanné) est gardée ;
//   4. technicien ou responsable : génération des OT préventifs échus (RG5) → marque prevo:preventif ;
//   5. coque (menu, barre du bas, bandeaux) et premier écran → <html data-etat="pret">.
// États lus par les tests : data-etat = 'chargement' | 'demarrage' | 'profil' | 'pret'.
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
//   - le module lit App.adaptateur, App.profil ({ type, nom, technicienId }), App.mode, App.poste.
// Règles : pas de crypto ni de presse-papiers (contexte non sécurisé), pas d'alert/confirm/prompt,
// console.warn pour une erreur gérée (jamais console.error).

const App = (() => {

  const VERSION = '1.0.0';
  const DATE_VERSION = '2026-10-21';
  // Version web (démo en ligne, docs/DEPLOIEMENT_DEMO.md) : faux dans le dépôt et dans la release ;
  // outils/construire_demo_web.py le passe à vrai dans sa copie (dist/demo-web/). Vrai : l'écran de
  // démarrage ne propose que la démo et « Télécharger Prévo » (ni dossier, ni serveur), et l'assistant
  // IA reste visible mais n'appelle rien (js/modules/ia.js). Jamais déduit de l'adresse de la page.
  const VERSION_WEB = false;
  const CLE_PROFIL = 'prevo.profil';
  const CLE_POSTE = 'prevo.poste';
  const CLE_MENU_REPLIE = 'prevo.menuReplie';
  const CLE_VERROU_ONGLET = 'prevo.verrouOnglet';   // sessionStorage : poste du verrou posé par cet onglet
  const ROUTE_ACCUEIL = '#/accueil';
  const TYPES_PROFIL = ['demandeur', 'technicien', 'responsable'];
  const LIBELLES_TYPE = { demandeur: 'Demandeur', technicien: 'Technicien', responsable: 'Responsable' };
  const ENTREES_BARRE_BAS = 4;
  const ECRANS_PLEINS = ['ecran-chargement', 'ecran-demarrage', 'ecran-base-vide', 'ecran-profil', 'app'];
  const CHAMPS_DOCUMENTS = [['equipements', 'document'], ['demandes', 'photo'], ['controles_reglementaires', 'rapport']];

  // --- État de l'application ----------------------------------------------------------------
  let mode = null;                 // 'serveur' | 'dossier' | 'demo'
  let adaptateur = null;           // adaptateur de stockage (contrat ARCHITECTURE.md §6)
  let profil = null;               // { type, nom, technicienId }
  let poste = '';                  // nom du poste (journal, verrou)
  let adressesReseau = [];         // mode serveur : ['http://192.168.1.10:8080/', …]
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
  const alertesCoque = [];         // bandeaux à montrer dans la coque (ex. verrou du dossier)

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

  // Nom de poste proposé la première fois : « Poste-7KQ2 » (Math.random suffit, pas de crypto).
  function posteAleatoire() {
    const caracteres = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    let suffixe = '';
    for (let i = 0; i < 4; i += 1) suffixe += caracteres[Math.floor(Math.random() * caracteres.length)];
    return 'Poste-' + suffixe;
  }

  function estErreurDonnees(erreur) {
    return erreur instanceof Donnees.ErreurValidation || erreur instanceof Donnees.ErreurConflit
      || erreur instanceof Donnees.ErreurStockage;
  }

  /** Erreur gérée : message à l'utilisateur (toast) et trace console.warn (jamais console.error). */
  function signalerErreur(erreur, contexte) {
    const message = (erreur && erreur.message) || String(erreur);
    UI.toast(message, 'erreur');
    console.warn('Prévo' + (contexte ? ' (' + contexte + ')' : '') + ' : ' + message, erreur);
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
    remplacerIcones(document);
    installerEcouteurs();
    poste = lireMemoire(CLE_POSTE) || posteAleatoire();
    montrer('ecran-chargement', 'chargement');

    // Version web : pas de serveur Prévo à chercher (le site est statique : /api/ping n'existe pas).
    const pageEnHttp = location.protocol === 'http:' || location.protocol === 'https:';
    if (!VERSION_WEB && pageEnHttp && await StockageServeur.detecter()) {
      try {
        await ouvrirAvec(StockageServeur.creer());
      } catch (erreur) {
        signalerErreur(erreur, 'lecture des données du serveur');
        await afficherDemarrage();
      }
      return;
    }
    await afficherDemarrage();
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
      zoneAlerte.appendChild(UI.bandeau('attention', UI.html`<b>Ce navigateur ne sait pas ouvrir un dossier.</b>
        Pour travailler sur vos fichiers, utilisez Chrome ou Edge sur un ordinateur. En attendant,
        la démo fonctionne ici.`));
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
      UI.toast('L\'accès au dossier précédent n\'a pas été accordé. Choisissez le dossier à nouveau.', 'attention');
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
      UI.toast('Aucun fichier reconnu : les fichiers doivent s\'appeler equipements.csv, demandes.csv, ordres_travail.csv…', 'attention');
      return;
    }
    await ouvrirAvecGarde(resultat.adaptateur);
    if (ignores.length) UI.toast('Fichiers ignorés (nom inconnu ou en double) : ' + ignores.join(', '), 'attention');
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
          rejeter(new Error('Le jeu de démo (js/demo-donnees.js) n\'a pas pu être chargé.'));
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
          rejeter(new Error('La bibliothèque de lecture des fichiers Excel (js/lib/xlsx.full.min.js) n\'a pas pu être chargée.'));
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
          rejeter(new Error('La bibliothèque des graphiques (js/lib/echarts.min.js) n\'a pas pu être chargée.'));
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
    adaptateur = nouvelAdaptateur;
    mode = nouvelAdaptateur.mode;
    Donnees.initialiser(adaptateur, { poste, profil: '' });
    await Donnees.chargerTout();

    if (mode !== 'demo' && Donnees.baseVide()) {
      const choix = await demanderBaseVide();
      montrer('ecran-chargement', 'chargement');
      await remplirBaseVide(choix);
      await Donnees.chargerTout();
    }
    const formatAJour = await passerAuFormatCourant();   // avant TOUTE autre écriture, pour tous les profils

    if (mode === 'serveur') {
      try {
        const informations = await adaptateur.info();
        adressesReseau = (informations && informations.adressesReseau) || [];
      } catch (erreur) {
        console.warn('Prévo : adresses réseau du serveur inconnues (' + (erreur && erreur.message) + ').', erreur);
      }
    }
    if (mode === 'dossier') await verifierVerrouDossier();

    let profilChoisi = lireProfilMemorise();
    if (!profilValable(profilChoisi)) profilChoisi = await demanderProfil(false);
    appliquerProfil(profilChoisi);
    const otPreventifs = await genererPreventifAOuverture(formatAJour);
    Donnees.demarrerSurveillance();
    // Assistant IA (lot 4, §17.3) : un seul test du fournisseur s'il est activé sur le poste, aucun
    // appel sinon ; sans attendre la réponse (l'état « prêt » n'en dépend pas).
    if (typeof Ia !== 'undefined') Ia.verifierAuDemarrage();
    // Dictée (lot 4, §17.6) : bouton micro sur chaque champ dicté, où qu'il apparaisse ensuite.
    if (typeof Dictee !== 'undefined') Dictee.surveiller(document.body);
    await ouvrirCoque();
    if (otPreventifs.length) UI.toast(Preventif.texteGeneration(otPreventifs.length) + '.', 'succes');
  }

  // Format des fichiers (ARCHITECTURE.md §14.1) : une fois les tables chargées, pour tous les profils
  // et AVANT toute autre écriture, parametres.version_schema passe au format courant, juste après une
  // sauvegarde « avant-format-v2 » (Donnees.mettreAJourVersionSchema, sans effet si c'est déjà fait).
  // Sauvegarde impossible : erreur signalée et bandeau dans la coque, la version reste inchangée,
  // l'application reste utilisable et le passage sera retenté à la prochaine ouverture.
  // Renvoie true si les fichiers sont au format courant (passage fait, ou rien à faire), false sinon.
  async function passerAuFormatCourant() {
    try {
      await Donnees.mettreAJourVersionSchema();
      return true;
    } catch (erreur) {
      signalerErreur(erreur, 'passage au format ' + Schema.version + ' des fichiers');
      alertesCoque.push(UI.bandeau('attention', UI.html`<b>Les fichiers n'ont pas pu passer au format ${Schema.version}.</b>
        ${(erreur && erreur.message) || ''} D'ici là, les OT préventifs échus ne sont pas générés automatiquement.`));
      return false;
    }
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
        signalerErreur(erreur, 'génération des OT préventifs à l\'ouverture');
      }
    }
    if (!preventifDejaMarque && window.performance && typeof performance.mark === 'function') {
      preventifDejaMarque = true;
      performance.mark('prevo:preventif');
    }
    return crees;
  }

  function demanderBaseVide() {
    UI.$('#texte-base-vide').textContent = 'Aucun des 22 fichiers de Prévo n\'a été trouvé ('
      + (adaptateur.libelle || mode) + '). Par quoi voulez-vous commencer ?';
    montrer('ecran-base-vide', 'demarrage');
    return new Promise((resoudre) => { resoudreBaseVide = resoudre; });
  }

  // Écrit les 22 fichiers (versionAttendue null : aucun ne doit exister, sinon ErreurConflit).
  async function remplirBaseVide(choix) {
    const contenus = {};
    if (choix === 'demo') {
      await chargerScriptDemo();
      Object.assign(contenus, StockageDemo.decalerDates(DEMO_DONNEES.tables, DEMO_DONNEES.dateReference));
    } else {
      Schema.nomsTables().forEach((nomTable) => { contenus[nomTable] = Donnees.csv.serialiser(nomTable, []); });
      // Une base neuve est écrite au format courant : pas de sauvegarde « avant-format-v2 » inutile
      // au premier démarrage (ARCHITECTURE.md §14.1).
      contenus.parametres = Donnees.csv.serialiser('parametres', [{ cle: 'version_schema', valeur: String(Schema.version) }]);
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
      alertesCoque.push(UI.bandeau('attention', UI.html`<b>Ce dossier semble déjà ouvert sur « ${autre.poste} »</b>
        (dernier signe de vie : ${autre.heure}). Deux postes qui écrivent dans le même dossier peuvent se gêner :
        fermez l'autre session si possible.`));
    }
    await adaptateur.demarrerVerrou();
    try { window.sessionStorage.setItem(CLE_VERROU_ONGLET, poste); } catch (erreur) { /* sans mémoire */ }
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

  // Texte inscrit au journal : « Responsable », « Demandeur Lucie Martin », « Technicien TEC-0002 ».
  function libelleJournal(p) {
    if (p.type === 'demandeur') return 'Demandeur ' + p.nom;
    if (p.type === 'technicien') return 'Technicien ' + p.technicienId;
    return LIBELLES_TYPE[p.type];
  }

  // Texte affiché dans le menu : « Technicien · Julien Moreau ».
  function libelleAffiche(p) {
    if (!p) return '';
    return p.type === 'responsable' ? LIBELLES_TYPE.responsable : LIBELLES_TYPE[p.type] + ' · ' + p.nom;
  }

  function appliquerProfil(nouveau) {
    profil = nouveau;
    if (profil.type === 'technicien') {
      const technicien = Donnees.trouver('techniciens', profil.technicienId);
      if (technicien) profil.nom = nomTechnicien(technicien);
    }
    ecrireMemoire(CLE_PROFIL, JSON.stringify(profil));
    ecrireMemoire(CLE_POSTE, poste);
    Donnees.definirIdentite({ poste, profil: libelleJournal(profil) });
    UI.$('#libelle-profil').textContent = libelleAffiche(profil) + ' · ' + poste;
    UI.$('#etat-poste').title = 'Profil : ' + libelleAffiche(profil) + ' — poste « ' + poste + ' ». Cliquer pour changer.';
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
      .sort((a, b) => nomTechnicien(a).localeCompare(nomTechnicien(b), 'fr'));
    const zone = UI.$('#profil-techniciens');
    if (!actifs.length) {
      UI.remplir(zone, UI.html`<p class="note">Aucun technicien actif dans techniciens.csv : choisissez un autre profil.</p>`);
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
      erreur.textContent = 'Indiquez votre nom : il permet de retrouver vos demandes.';
      erreur.hidden = false;
      champNom.setAttribute('aria-invalid', 'true');
      champNom.focus();
      return;
    }
    terminerProfil({ type: 'demandeur', nom, technicienId: '' });
  }

  /** Change de profil sans recharger la page (en démo, recharger ferait tout perdre). */
  async function changerProfil() {
    if (!adaptateur || !profil || resoudreProfil) return;
    const nouveau = await demanderProfil(true);
    if (nouveau) {
      appliquerProfil(nouveau);
      UI.toast('Profil : ' + libelleAffiche(profil) + '.', 'succes');
    }
    await ouvrirCoque();
  }

  function estResponsable() { return Boolean(profil) && profil.type === 'responsable'; }
  function estTechnicien() { return Boolean(profil) && profil.type === 'technicien'; }
  function estDemandeur() { return Boolean(profil) && profil.type === 'demandeur'; }

  // ===========================================================================================
  // 5. Coque : menu latéral, barre du bas, bandeaux
  // ===========================================================================================

  async function ouvrirCoque() {
    montrer('app');
    UI.$('#bandeau-demo').hidden = mode !== 'demo';
    afficherAlertesCoque();
    appliquerRepli(lireMemoire(CLE_MENU_REPLIE) === '1');
    mettreAJourEntreprise();
    if (!location.hash || location.hash === '#' || location.hash === '#/') remplacerRoute(ROUTE_ACCUEIL);
    construireMenus();
    await afficherRoute(false);
    document.documentElement.dataset.etat = 'pret';
    if (!pretDejaMarque) {
      pretDejaMarque = true;
      if (window.performance && typeof performance.mark === 'function') performance.mark('prevo:pret');
    }
  }

  function afficherAlertesCoque() {
    const zone = UI.$('#alertes-app');
    alertesCoque.splice(0).forEach((bandeau) => {
      const fermer = UI.element(UI.html`<button type="button" class="btn btn-fantome">Fermer</button>`);
      fermer.addEventListener('click', () => {
        bandeau.remove();
        zone.hidden = zone.children.length === 0;
      });
      bandeau.appendChild(fermer);
      zone.appendChild(bandeau);
    });
    zone.hidden = zone.children.length === 0;
  }

  // En-tête du menu latéral (D32) : « Prévo », « GMAO », puis le nom de l'entreprise sur deux lignes
  // au plus (au-delà, la feuille app.css le coupe) ; le nom complet reste lisible en infobulle.
  function mettreAJourEntreprise() {
    const nom = adaptateur ? String(Donnees.parametre('entreprise_nom', '')).trim() : '';
    const zone = UI.$('#nom-entreprise');
    zone.textContent = nom;
    zone.title = nom;
    zone.hidden = !nom;
  }

  function appliquerRepli(replie) {
    UI.$('#app').classList.toggle('replie', replie);
    const bouton = UI.$('#btn-replier');
    bouton.setAttribute('aria-expanded', String(!replie));
    bouton.setAttribute('aria-label', replie ? 'Déplier le menu' : 'Replier le menu');
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

  function construireMenus() {
    const entrees = entreesMenu();
    const morceaux = [];
    let groupeCourant = '';
    entrees.forEach((ecran) => {
      const groupe = ecran.menu.groupe || '';
      if (groupe && groupe !== groupeCourant) morceaux.push(UI.html`<div class="menu-groupe">${groupe}</div>`);
      groupeCourant = groupe;
      morceaux.push(UI.html`<a href="${lienEntree(ecran)}" data-ecran="${ecran.id}" title="${ecran.menu.libelle}">${UI.icone(ecran.menu.icone || 'chevron')}<span class="libelle">${ecran.menu.libelle}</span></a>`);
    });
    UI.remplir(UI.$('#menu'), morceaux);

    const enBas = entrees.slice(0, ENTREES_BARRE_BAS);
    UI.remplir(UI.$('#barre-bas'), UI.html`${enBas.map((ecran) => UI.html`<a href="${lienEntree(ecran)}" data-ecran="${ecran.id}">${UI.icone(ecran.menu.icone || 'chevron')}<span class="libelle">${ecran.menu.court || ecran.menu.libelle}</span></a>`)}
      <button type="button" id="btn-plus" aria-haspopup="dialog">${UI.icone('plus')}<span class="libelle">Plus</span></button>`);
    UI.$('#btn-plus').addEventListener('click', ouvrirPlus);
    allumerMenus();
  }

  // Entrée active (et aria-current) dans le menu latéral et la barre du bas.
  function allumerMenus() {
    const idActif = ecranCourant ? (ecranCourant.parent || ecranCourant.id) : '';
    UI.$$('#menu a, #barre-bas a').forEach((lien) => {
      const actif = lien.dataset.ecran === idActif;
      lien.classList.toggle('actif', actif);
      if (actif) lien.setAttribute('aria-current', 'page'); else lien.removeAttribute('aria-current');
    });
    const plus = UI.$('#btn-plus');
    if (plus) {
      const dansLaBarre = UI.$$('#barre-bas a').some((lien) => lien.dataset.ecran === idActif);
      plus.classList.toggle('actif', Boolean(idActif) && !dansLaBarre);
    }
  }

  // « Plus » (téléphone) : les entrées qui n'ont pas de place dans la barre du bas + actions du poste.
  function ouvrirPlus() {
    const idActif = ecranCourant ? (ecranCourant.parent || ecranCourant.id) : '';
    const reste = entreesMenu().slice(ENTREES_BARRE_BAS);
    const contenu = UI.element(UI.html`<ul class="liste-plus">
      ${reste.map((ecran) => UI.html`<li><a href="${lienEntree(ecran)}" class="${ecran.id === idActif ? 'actif' : ''}">${UI.icone(ecran.menu.icone || 'chevron')}${ecran.menu.libelle}</a></li>`)}
      <li><a href="#" data-action="profil">${UI.icone('utilisateur')}Changer de profil (${libelleAffiche(profil)})</a></li>
      ${mode === 'demo' ? UI.html`<li><a href="#" data-action="zip">${UI.icone('export')}Exporter en ZIP</a></li>` : ''}
    </ul>`);
    UI.fenetre({
      titre: 'Plus', classe: 'feuille', contenu,
      boutons: [{ libelle: 'Fermer', valeur: null, classe: 'btn-secondaire', defaut: true }],
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
      throw new Error('App.ecran : id, route (RegExp) et afficher(conteneur, parametres) sont obligatoires.');
    }
    if (ecrans.some((e) => e.id === definition.id)) {
      throw new Error('App.ecran : l\'écran « ' + definition.id + ' » est déjà enregistré.');
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
      if (trouve) UI.toast('L\'écran « ' + trouve.ecran.titre + ' » n\'est pas disponible pour le profil ' + LIBELLES_TYPE[profil.type] + '.', 'attention');
      const accueil = trouverEcran(ROUTE_ACCUEIL);
      if (chemin !== ROUTE_ACCUEIL && accueil && ecranAutorise(accueil.ecran)) {
        remplacerRoute(ROUTE_ACCUEIL);
        await afficherRoute(false);
      } else {
        ecranCourant = null;
        UI.remplir(UI.$('#contenu'), UI.vide('Écran introuvable', 'Aucun écran ne correspond à cette adresse.'));
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
        conteneur.appendChild(UI.bandeau('important', UI.html`<b>Cet écran n'a pas pu s'afficher.</b> ${(erreur && erreur.message) || ''}`));
      }
      if (!estErreurDonnees(erreur)) throw erreur;     // défaut du code : il doit se voir
      signalerErreur(erreur, 'affichage de « ' + ecranAAfficher.titre + ' »');
    }
    if (numero !== numeroAffichage) return;
    if (garderDefilement) window.scrollTo(0, defilement);
    else window.scrollTo(0, 0);
    if (nouvelEcran && !garderDefilement && document.activeElement !== conteneur
        && !conteneur.contains(document.activeElement)) {
      conteneur.focus({ preventScroll: true });          // lecteurs d'écran : on est sur le nouvel écran
    }
  }

  /** Titre de l'onglet et de l'en-tête mobile (un écran peut le préciser : « OT-2026-0107 »). */
  function definirTitre(texte) {
    const titre = texte || 'Prévo';
    document.title = titre === 'Prévo' ? 'Prévo — GMAO' : titre + ' — Prévo';
    UI.$('#titre-mobile').textContent = titre;
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
    if (tables.includes('parametres')) mettreAJourEntreprise();
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

  /** Télécharge prevo-export-AAAA-MM-JJ.zip : les 22 CSV et les documents référencés. */
  async function exporterZip() {
    if (!adaptateur) return;
    try {
      try {
        await Donnees.rafraichir();                      // journal à jour (écrit par ajout)
      } catch (erreur) {
        console.warn('Prévo : rafraîchissement avant export impossible (' + (erreur && erreur.message) + ').', erreur);
      }
      const archive = new JSZip();
      const fichiers = Donnees.instantane();
      Schema.nomsTables().forEach((nomTable) => {
        archive.file(Schema.table(nomTable).fichier, fichiers[nomTable]);
      });
      const documents = await documentsAExporter();
      documents.trouves.forEach((document) => archive.file('documents/' + document.nom, document.blob));
      const blob = await archive.generateAsync({ type: 'blob', compression: 'DEFLATE' });
      UI.telecharger('prevo-export-' + Donnees.aujourdhui() + '.zip', blob);
      let message = 'Export téléchargé : 22 fichiers CSV';
      if (documents.trouves.length) message += ' et ' + documents.trouves.length + ' document(s)';
      if (documents.manquants.length) message += ' (' + documents.manquants.length + ' document(s) introuvable(s))';
      UI.toast(message + '.', documents.manquants.length ? 'attention' : 'succes');
    } catch (erreur) {
      signalerErreur(erreur, 'export ZIP');
    }
  }

  // Démo : documents ajoutés en mémoire. Ailleurs : documents cités dans les CSV (photo, document, rapport).
  async function documentsAExporter() {
    if (typeof adaptateur.documentsEnMemoire === 'function') {
      return { trouves: adaptateur.documentsEnMemoire(), manquants: [] };
    }
    const noms = new Set();
    CHAMPS_DOCUMENTS.forEach(([nomTable, nomChamp]) => {
      Donnees.lignes(nomTable).forEach((ligne) => { if (ligne[nomChamp]) noms.add(ligne[nomChamp]); });
    });
    const trouves = [];
    const manquants = [];
    for (const nom of noms) {
      try {
        const blob = await adaptateur.lireDocument(nom);
        if (blob) trouves.push({ nom, blob }); else manquants.push(nom);
      } catch (erreur) {
        console.warn('Prévo : document « ' + nom + ' » non exporté (' + (erreur && erreur.message) + ').', erreur);
        manquants.push(nom);
      }
    }
    return { trouves, manquants };
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
    UI.$('#btn-export-demo').addEventListener('click', () => exporterZip());
    UI.$('#btn-actualiser').addEventListener('click', () => reafficher());
    UI.$('#contenu').addEventListener('input', surSaisie);
    UI.$('#contenu').addEventListener('change', surSaisie);
    window.addEventListener('hashchange', () => { afficherRoute(false); });
    Donnees.evenements.addEventListener('changement', surChangement);

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
    get poste() { return poste; },
    ecran,
    naviguer,
    reafficher,
    definirTitre,
    marquerSaisie,
    estResponsable,
    estTechnicien,
    estDemandeur,
    libelleProfil: () => libelleAffiche(profil),
    urlFicheEquipement,
    adressesReseau: adressesDuReseau,
    chargerScriptDemo,
    chargerEcharts,
    chargerSheetJS,
    changerProfil,
    exporterZip,
    signalerErreur,
  };
})();
