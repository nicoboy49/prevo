'use strict';
// Chargeur de la langue active (chantier multilingue, contrat du Lot 2 ; docs/ARCHITECTURE.md §1 et §24.11).
// Placé dans index.html juste après js/i18n/fr.js et js/i18n/aide/fr.js, avant js/schema.js, et dans acces/porte.html
// après js/i18n/fr.js, avant acces/porte.js (T297 : la porte le sert sans session). Il choisit la langue à
// afficher (D148, Lot 4, T295, T298 ; I18n.langueDeLaPage) : 1. la langue du compte connecté ; 2. sinon le choix de ce
// poste ; 3. sinon la langue de l'installation ; 4. sinon (installation inconnue) la langue du navigateur ; 5. sinon le
// français. Chaque valeur est vérifiée contre les langues déclarées par js/i18n/langues.js : absente,
// non déclarée ou mal formée, stockage refusé, elle est ignorée, sans erreur. Si la langue à afficher n'est pas le
// français, elle devient la langue active et ses deux fichiers (js/i18n/<code>.js puis js/i18n/aide/<code>.js : toute
// langue déclarée fournit les deux, sauf « aide: false ») sont écrits dans la page par document.write pendant son
// analyse : le navigateur les charge et les exécute aussitôt, de façon synchrone, AVANT js/schema.js, en file:// comme
// en http (un <script src> du même dossier : permis par la politique de sécurité du contenu, script-src 'self').
// La langue de l'installation est notée (I18n.noterInstallation) : c'est celle des textes écrits dans les données
// (D156) ; si elle n'est ni le français ni la langue affichée, son dictionnaire (js/i18n/<code>.js, sans l'aide
// longue) est écrit aussi, pour que I18n.donnees la trouve.
// La langue du compte vient de localStorage « prevo.langue.compte », écrite par js/app.js quand il apprend la session
// (T298 : GET /api/session, connexion) et effacée sans session de compte (déconnexion, session expirée, appareil
// enrôlé, sans comptes). Le choix du poste vient de localStorage « prevo.langue », écrit par le sélecteur de langue
// (UI.selecteurLangue, écran « Ce poste » et pied du menu). La langue de l'installation vient de
// localStorage « prevo.langue.installation », écrit par js/app.js chaque fois qu'il lit parametres.csv (langue_defaut,
// D149) : le chargeur tourne avant toute lecture des données ; si la page n'est pas dans la bonne langue une fois les
// paramètres lus, js/app.js la recharge une fois. Une page servie par serveur.py avec l'attribut
// data-langue-installation (T297 : la porte des téléphones, toujours ; index.html quand langue_defaut est réglée, pour
// l'écran de connexion d'un appareil neuf) donne elle-même la langue de l'installation : elle passe avant celle retenue
// par ce navigateur, et la langue du navigateur ne sert pas (I18n.langueDeLaPage). La langue choisie donne aussi
// l'attribut lang de <html> (I18n.choisir).
// Ajouté à une page déjà analysée (document.write l'effacerait) : rien n'est fait, la page reste en français.
// Aucun objet global : seulement I18n (js/i18n.js).
(function () {
  const CLE_LANGUE = 'prevo.langue';
  const CLE_INSTALLATION = 'prevo.langue.installation';
  const CLE_COMPTE = 'prevo.langue.compte';
  const LANGUE_DE_REFERENCE = 'fr';
  const REMPLACEMENTS = { '&': '&amp;', '"': '&quot;', '<': '&lt;', '>': '&gt;' };

  function lire(cle) {
    try {
      return localStorage.getItem(cle) || '';
    } catch (erreur) {               // stockage refusé (navigation privée stricte, file:// verrouillé) : ignorée
      return '';
    }
  }

  function ecrire(cle, valeur) {
    try {
      localStorage.setItem(cle, valeur);
    } catch (erreur) { /* stockage refusé : la langue vaut pour cette page seulement */ }
  }

  // T324 (Nicolas, 07/11) : langue choisie sur la porte des téléphones (acces/porte.js, en http : un autre stockage),
  // passée dans l'adresse ouverte par la porte (?langue=<code>, langue_neuve=1 si elle vient d'y être choisie). Une
  // langue déclarée devient le choix de ce poste quand il n'en a pas, ou quand elle vient d'être choisie ; un choix
  // fait plus tard dans l'application n'est donc pas écrasé. Les deux paramètres sont retirés de l'adresse. La langue
  // du compte reste devant (ordre : compte, porte ou poste, installation). Valeur hors liste : ignorée.
  function reprendreLaLangueDeLaPorte() {
    let parametres;
    try { parametres = new URLSearchParams(location.search); } catch (erreur) { return; }
    if (!parametres.has('langue') && !parametres.has('langue_neuve')) return;
    const code = parametres.get('langue') || '';
    const neuve = parametres.get('langue_neuve') === '1';
    if (I18n.langues.some((langue) => langue.code === code) && (neuve || !lire(CLE_LANGUE))) ecrire(CLE_LANGUE, code);
    parametres.delete('langue');
    parametres.delete('langue_neuve');
    const reste = parametres.toString();
    try {
      history.replaceState(history.state, '', location.pathname + (reste ? '?' + reste : '') + location.hash);
    } catch (erreur) { /* adresse laissée telle quelle : sans effet sur la langue */ }
  }

  function balise(adresse) {
    return '<script src="' + adresse.replace(/[&"<>]/g, (caractere) => REMPLACEMENTS[caractere]) + '"><\/script>';
  }

  const script = document.currentScript;
  if (document.readyState !== 'loading' || !script || !script.src) return;
  reprendreLaLangueDeLaPorte();
  // Valeurs vérifiées par I18n : une langue non déclarée ou mal formée donne le français.
  const retenue = lire(CLE_INSTALLATION);
  const installation = I18n.noterInstallation(I18n.installationDeLaPage() || retenue);
  let languesDuNavigateur = [];
  try {
    languesDuNavigateur = Array.from(navigator.languages && navigator.languages.length ? navigator.languages : [navigator.language]);
  } catch (erreur) { /* navigateur sans langue lisible : anglais */ }
  const code = I18n.langueDeLaPage(lire(CLE_LANGUE), retenue, languesDuNavigateur, lire(CLE_COMPTE));
  // Dossier de ce fichier (js/), quelle que soit l'adresse de la page : index.html à la racine, ou une autre page.
  const dossier = script.src.replace(/[?#].*$/, '').replace(/[^/]*$/, '') + 'i18n/';
  let balises = '';
  let avecAide = true;
  if (code !== LANGUE_DE_REFERENCE) {
    avecAide = I18n.langues.find((langue) => langue.code === code).aide !== false;
    I18n.choisir(code);
    balises += balise(dossier + code + '.js') + (avecAide ? balise(dossier + 'aide/' + code + '.js') : '');
  }
  if (installation !== LANGUE_DE_REFERENCE && installation !== code) balises += balise(dossier + installation + '.js');
  if (balises) document.write(balises);
  // Langue sans aide longue traduite (« aide: false » dans langues.js) : une seule ligne, une fois (T308, Nicolas).
  if (!avecAide) console.info('Prévo : pas d\'aide longue en « ' + code + ' » ; elle s\'affiche en français.');
})();
