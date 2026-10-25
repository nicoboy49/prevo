'use strict';
// Poste — écran « Ce poste » (#/poste, tous les profils ; ARCHITECTURE.md §17.7) : identité du poste
// et profil, assistant IA, dictée, affichage (thème sombre ou clair). Les réglages propres au poste
// restent dans son navigateur (localStorage : prevo.ia, prevo.dictee, prevo.theme) ; le réglage
// partagé « fournisseurs d'IA en ligne autorisés » est dans Paramètres (responsable).
//
// API :
//   Poste.THEMES                → { sombre: 'Sombre', clair: 'Clair' }
//   Poste.themeMemorise()       → 'sombre' | 'clair' (lecture protégée : stockage refusé → 'sombre')
//   Poste.appliquerTheme(theme) → pose <html data-theme="clair">, ou l'enlève (thème sombre, défaut) ;
//                                 appelé par js/app.js dès sa lecture, donc avant le premier écran
//   Poste.choisirTheme(theme)   → mémorise le choix sur ce poste et l'applique tout de suite
//
// Règles de l'assistant IA (§17.3) : l'IA propose, l'humain valide. La clé du fournisseur n'est écrite
// que dans localStorage (Ia.enregistrerReglages) : jamais dans un fichier, le journal ou la console,
// et jamais réaffichée (le champ reste vide ; laissé vide, il garde la clé enregistrée).
//
// Sommaire : 1 thème · 2 petits outils · 3 carte Identité · 4 carte Assistant IA · 5 carte Dictée ·
// 6 carte Affichage · 7 écran et enregistrement.

const Poste = (() => {

  const THEMES = Object.freeze({ sombre: 'Sombre', clair: 'Clair' });
  const THEME_DEFAUT = 'sombre';
  const CLE_THEME = 'prevo.theme';
  const DELAI_MIN_S = 1;
  const DELAI_MAX_S = 300;            // plafond du relais du serveur (§17.2), comme dans ia.js
  // Explication affichée sous la mention de portée (Ia.portee → Ia.mention).
  const EXPLICATIONS_PORTEE = {
    poste: 'Le fournisseur tourne sur ce PC : les textes ne quittent pas l\'ordinateur.',
    'pc-atelier': 'Le serveur Prévo transmet la demande au fournisseur installé sur le PC atelier : '
      + 'les textes ne quittent pas ce PC.',
    atelier: 'Le fournisseur est sur un autre PC du réseau de l\'atelier : les textes ne sortent pas de l\'atelier.',
  };

  // ===========================================================================================
  // 1. Thème (sombre par défaut, clair au choix du poste)
  // ===========================================================================================

  /** Thème mémorisé sur ce poste ; stockage refusé ou valeur inconnue → thème sombre. */
  function themeMemorise() {
    let lu = null;
    try { lu = window.localStorage.getItem(CLE_THEME); } catch (erreur) { lu = null; }
    return Object.prototype.hasOwnProperty.call(THEMES, lu) ? lu : THEME_DEFAUT;
  }

  // Barre du navigateur sur téléphone (<meta name="theme-color">) : couleur de fond du thème choisi.
  function accorderBarreNavigateur() {
    const meta = document.querySelector('meta[name="theme-color"]');
    if (!meta || !document.documentElement) return;
    const fond = getComputedStyle(document.documentElement).getPropertyValue('--fond').trim();
    if (fond) meta.setAttribute('content', fond);
  }

  /** Pose <html data-theme="clair"> (variables du thème clair de css/style.css) ou l'enlève. */
  function appliquerTheme(theme) {
    const racine = document.documentElement;
    if (!racine) return;
    if (theme === 'clair') racine.setAttribute('data-theme', 'clair');
    else racine.removeAttribute('data-theme');
    accorderBarreNavigateur();
  }

  /** Mémorise le thème sur ce poste et l'applique tout de suite. Renvoie le thème retenu. */
  function choisirTheme(theme) {
    const retenu = Object.prototype.hasOwnProperty.call(THEMES, theme) ? theme : THEME_DEFAUT;
    try { window.localStorage.setItem(CLE_THEME, retenu); } catch (erreur) { /* sans mémoire : vaut pour cette page */ }
    appliquerTheme(retenu);
    return retenu;
  }

  // ===========================================================================================
  // 2. Petits outils
  // ===========================================================================================

  // Nom d'hôte (« api.mistral.ai ») et origine (« https://api.mistral.ai ») d'une adresse ; '' si illisible.
  function hote(url) {
    try { return new URL(String(url || '').trim()).hostname; } catch (erreur) { return ''; }
  }

  function origine(url) {
    try { return new URL(String(url || '').trim()).origin; } catch (erreur) { return ''; }
  }

  // Désactive un bouton pendant une action ; une erreur imprévue s'affiche proprement.
  async function pendant(bouton, contexte, action) {
    bouton.disabled = true;
    bouton.setAttribute('aria-busy', 'true');
    try {
      return await action();
    } catch (erreur) {
      App.signalerErreur(erreur, contexte);
      return undefined;
    } finally {
      bouton.disabled = false;
      bouton.removeAttribute('aria-busy');
    }
  }

  // ===========================================================================================
  // 3. Carte « Identité » : nom du poste, profil, stockage, changement de profil
  // ===========================================================================================

  function carteIdentite() {
    const stockage = (App.adaptateur && App.adaptateur.libelle) || App.mode || '';
    return UI.html`<article class="carte" id="carte-identite" data-hors-saisie>
      <div class="entete-carte"><h2>Identité</h2></div>
      <dl class="valeurs">
        <dt>Nom du poste</dt><dd id="poste-nom">${App.poste}</dd>
        <dt>Profil</dt><dd id="poste-profil">${App.libelleProfil()}</dd>
        <dt>Stockage</dt><dd id="poste-stockage">${stockage}</dd>
      </dl>
      <p class="note">Le nom du poste est inscrit au journal avec chaque modification. Le profil adapte les écrans :
        ce n'est pas une sécurité.</p>
      <div class="actions"><button type="button" class="btn btn-secondaire" id="btn-changer-profil">${UI.icone('utilisateur')}Changer de profil ou de nom de poste…</button></div>
    </article>`;
  }

  // ===========================================================================================
  // 4. Carte « Assistant IA » : réglages du poste, portée, test de connexion, enregistrement
  // ===========================================================================================

  // État de l'IA sur ce poste (badge en tête de la carte).
  function etatIa() {
    if (!Ia.reglages().actif) return { ton: 'neutre', texte: 'Désactivé sur ce poste' };
    if (!Ia.active()) return { ton: 'attention', texte: 'Activé, mais inutilisable (adresse ou autorisation)' };
    const etat = Ia.etat();
    if (etat === 'ok') return { ton: 'ok', texte: 'Activé — le fournisseur répond' };
    if (etat === 'injoignable') return { ton: 'ko', texte: 'Activé — le fournisseur ne répond pas' };
    return { ton: 'info', texte: 'Activé — connexion pas encore vérifiée' };
  }

  function remplirEtat(zone) {
    const etat = etatIa();
    zone.className = 'badge ' + etat.ton;
    zone.textContent = etat.texte;
  }

  // Valeurs saisies dans la carte (chaînes, sauf les deux cases à cocher).
  function lireIa(formulaire) {
    const lu = UI.lireFormulaire(formulaire);
    return {
      actif: lu.actif === '1', fournisseur: lu.fournisseur, url: lu.url, modele: lu.modele,
      cleSaisie: lu.cle || '', effacerCle: lu.effacer_cle === '1', delaiS: lu.delaiS,
    };
  }

  // Clé à envoyer : celle saisie ; sinon celle déjà enregistrée, gardée seulement pour l'API compatible
  // OpenAI à la même adresse (une clé n'est jamais envoyée à un autre fournisseur) ; aucune pour Ollama.
  function cleRetenue(valeurs, enregistres) {
    if (valeurs.fournisseur !== 'openai') return '';
    if (valeurs.cleSaisie) return valeurs.cleSaisie;
    if (valeurs.effacerCle) return '';
    const memeAdresse = enregistres.fournisseur === 'openai' && origine(enregistres.url) !== ''
      && origine(enregistres.url) === origine(valeurs.url);
    return memeAdresse ? enregistres.cle : '';
  }

  // Réglages complets décrits par le formulaire (ceux que l'on teste ou que l'on enregistre).
  function reglagesDuFormulaire(valeurs) {
    return {
      actif: valeurs.actif, fournisseur: valeurs.fournisseur, url: valeurs.url, modele: valeurs.modele,
      cle: cleRetenue(valeurs, Ia.reglages()), delaiS: Number(valeurs.delaiS),
    };
  }

  // Vrai si le formulaire décrit exactement les réglages enregistrés (le test met alors l'état à jour).
  function memesQueLePoste(r) {
    const enregistres = Ia.reglages();
    return enregistres.fournisseur === r.fournisseur && enregistres.url === String(r.url).trim()
      && enregistres.modele === String(r.modele).trim() && enregistres.cle === r.cle && enregistres.delaiS === r.delaiS;
  }

  /** Portée et mention d'après l'adresse saisie (mise à jour à chaque frappe). */
  function afficherPortee(formulaire) {
    const zone = formulaire && UI.$('#poste-ia-portee', formulaire);
    if (!zone) return;
    const valeurs = lireIa(formulaire);
    zone.classList.remove('distant', 'invalide');
    if (!Ia.urlValide(valeurs.url)) {
      zone.classList.add('invalide');
      UI.remplir(zone, UI.html`<p class="poste-ia-ou">Où vont les textes : <b id="poste-ia-mention">adresse invalide</b></p>
        <p class="aide">Adresse attendue : http://… ou https://… (sans identifiant, paramètres ni #).</p>`);
      return;
    }
    const portee = Ia.portee(valeurs.url);
    let explication = EXPLICATIONS_PORTEE[portee];
    if (portee === 'distant') {
      zone.classList.add('distant');
      explication = Ia.distantAutorise()
        ? UI.html`Fournisseur en ligne, <b>autorisé par le responsable</b> : les textes envoyés quittent l'atelier.`
        : UI.html`${new Ia.IaRefusee().message}${App.estResponsable() ? UI.html` <a href="#/parametres">Ouvrir les Paramètres</a>` : ''}`;
    }
    UI.remplir(zone, UI.html`<p class="poste-ia-ou">Où vont les textes : <b id="poste-ia-mention">${Ia.mention(portee, valeurs.url)}</b></p>
      <p class="aide">${explication}</p>`);
  }

  // Liste « Modèles trouvés » remplie après un test de connexion réussi.
  function afficherModeles(formulaire, modeles) {
    const zone = UI.$('#poste-ia-zone-modeles', formulaire);
    const liste = UI.$('#poste-ia-liste-modeles', formulaire);
    const actuel = UI.$('#poste-ia-modele', formulaire).value.trim();
    liste.textContent = '';
    liste.appendChild(new Option('— Choisir un modèle trouvé —', ''));
    modeles.forEach((modele) => liste.appendChild(new Option(modele, modele)));
    liste.value = modeles.includes(actuel) ? actuel : '';
    zone.hidden = modeles.length === 0;
  }

  function afficherResultat(formulaire, type, contenu) {
    const zone = UI.$('#poste-ia-resultat', formulaire);
    UI.remplir(zone, contenu ? UI.bandeau(type, contenu) : null);
  }

  /** « Tester la connexion » : réglages saisis (rien n'est enregistré), liste des modèles trouvés. */
  async function testerConnexion(formulaire) {
    const essai = reglagesDuFormulaire(lireIa(formulaire));
    UI.remplir(UI.$('#poste-ia-resultat', formulaire), UI.chargement('Test de la connexion…'));
    // Réglages du poste inchangés : le test met aussi l'état à jour (« le fournisseur répond »).
    const resultat = memesQueLePoste(essai) ? await Ia.tester() : await Ia.tester(essai);
    if (!formulaire.isConnected) return;
    afficherModeles(formulaire, resultat.modeles);
    afficherResultat(formulaire, resultat.ok ? 'succes' : 'attention', resultat.message);
  }

  // Contrôle des champs avant d'activer l'IA ; erreurs affichées sous les champs.
  function verifierIa(formulaire, valeurs) {
    const erreurs = [];
    if (!Ia.urlValide(valeurs.url)) erreurs.push(['url', 'Adresse invalide : http://… ou https://… attendu (ex. ' + Ia.DEFAUTS.url + ').']);
    if (!valeurs.modele) erreurs.push(['modele', 'Indiquez le modèle (ex. ' + Ia.DEFAUTS.modele + ').']);
    const delai = Number(valeurs.delaiS);
    if (!/^\d+$/.test(valeurs.delaiS) || delai < DELAI_MIN_S || delai > DELAI_MAX_S) {
      erreurs.push(['delaiS', 'Saisissez un nombre entier de ' + DELAI_MIN_S + ' à ' + DELAI_MAX_S + '.']);
    }
    ['url', 'modele', 'delaiS'].forEach((nom) => UI.erreurChamp(formulaire, nom, ''));
    erreurs.forEach(([nom, message]) => UI.erreurChamp(formulaire, nom, message));
    if (!erreurs.length) return true;
    const premier = UI.$('[aria-invalid="true"]', formulaire);
    if (premier) premier.focus();
    UI.toast(erreurs.length + (erreurs.length > 1 ? ' champs' : ' champ') + ' à corriger.', 'erreur');
    return false;
  }

  // Avertissement à l'activation d'un fournisseur en ligne : sauf s'il était déjà actif chez le même hôte.
  function avertissementUtile(anciens, nouveaux) {
    const dejaActif = anciens.actif && Ia.portee(anciens.url) === 'distant' && hote(anciens.url) === hote(nouveaux.url);
    return !dejaActif;
  }

  /** Fenêtre d'avertissement (§17.7) ; vrai si l'utilisateur confirme l'activation. */
  async function confirmerEnLigne(url) {
    const choix = await UI.fenetre({
      titre: 'Fournisseur d\'IA en ligne',
      contenu: UI.element(UI.html`<div class="form-colonne poste-avertissement-distant">
        <p><b>Les textes envoyés — descriptions, comptes rendus, désignations — partent chez ${hote(url)} ; ils peuvent contenir des noms.</b></p>
        <p>Prévo n'envoie jamais les noms des techniciens ni des demandeurs, ni les coûts ; mais un texte saisi peut en contenir.
          Relisez ce que vous demandez à l'IA.</p>
      </div>`),
      boutons: [
        { libelle: 'Annuler', valeur: false, classe: 'btn-fantome' },
        { libelle: 'Activer quand même', valeur: true, classe: 'btn-primaire', defaut: true },
      ],
    });
    return choix === true;
  }

  function refuser(formulaire, erreur) {
    afficherResultat(formulaire, 'important', erreur.message);
    UI.toast(erreur.message, 'erreur');
  }

  /** « Enregistrer » : contrôles, refus ou avertissement d'un fournisseur en ligne, puis test. */
  async function enregistrerIa(formulaire) {
    afficherResultat(formulaire, '', null);
    const valeurs = lireIa(formulaire);
    if (valeurs.actif && !verifierIa(formulaire, valeurs)) return;
    const anciens = Ia.reglages();
    const nouveaux = reglagesDuFormulaire(valeurs);
    if (nouveaux.actif && Ia.portee(nouveaux.url) === 'distant') {
      // D67 : refus d'abord (sans avertissement) si le responsable n'a pas autorisé les fournisseurs en ligne.
      if (!Ia.distantAutorise()) { refuser(formulaire, new Ia.IaRefusee()); return; }
      if (avertissementUtile(anciens, nouveaux) && !await confirmerEnLigne(nouveaux.url)) {
        afficherResultat(formulaire, 'info', 'Activation annulée : rien n\'a été enregistré.');
        return;
      }
    }
    let enregistres;
    try {
      enregistres = Ia.enregistrerReglages(nouveaux);
    } catch (erreur) {
      if (erreur instanceof Ia.IaRefusee) { refuser(formulaire, erreur); return; }
      throw erreur;
    }
    App.marquerSaisie(false);
    const cleNonReprise = Boolean(anciens.cle) && !enregistres.cle && enregistres.fournisseur === 'openai' && !valeurs.effacerCle;
    if (cleNonReprise) {
      UI.toast('Réglages enregistrés. La clé enregistrée n\'est pas envoyée à une autre adresse : saisissez la clé de ce fournisseur.', 'attention');
    } else {
      UI.toast('Réglages de l\'assistant IA enregistrés sur ce poste.', 'succes');
    }
    const carte = remplacerCarteIa();
    const nouveauFormulaire = UI.$('#form-ia', carte);
    if (!enregistres.actif) {
      afficherResultat(nouveauFormulaire, 'info', 'Réglages enregistrés : l\'assistant IA est désactivé sur ce poste.');
      return;
    }
    UI.remplir(UI.$('#poste-ia-resultat', carte), UI.chargement('Réglages enregistrés. Test de la connexion…'));
    const resultat = await Ia.tester();
    if (!carte.isConnected) return;
    afficherModeles(nouveauFormulaire, resultat.modeles);
    afficherResultat(nouveauFormulaire, resultat.ok ? 'succes' : 'attention', 'Réglages enregistrés. ' + resultat.message);
  }

  function aideAdresse() {
    const reseau = App.mode === 'serveur'
      ? ' En réseau, « localhost » désigne le PC qui fait tourner le serveur Prévo (le PC atelier).' : '';
    return 'Ollama : ' + Ia.DEFAUTS.url + '. API compatible OpenAI : adresse de base, souvent terminée par /v1 '
      + '(LM Studio : http://localhost:1234/v1).' + reseau;
  }

  // Champs de la carte, construits par UI.champ (libellé, aide, erreur sous le champ).
  function champsIa(r) {
    const sansCorrection = { autocomplete: 'off', autocapitalize: 'off', spellcheck: 'false' };
    const actif = UI.champ({ nom: 'actif', type: 'booleen', libelle: 'Activer l\'assistant IA sur ce poste' },
      r.actif ? '1' : '0', { id: 'poste-ia-actif' });
    const fournisseur = UI.champ({ nom: 'fournisseur', type: 'ref', libelle: 'Fournisseur' }, r.fournisseur, {
      id: 'poste-ia-fournisseur', aide: 'Ollama : modèle installé sur un PC. API compatible OpenAI : LM Studio, Mistral, Groq…',
      liste: Object.keys(Ia.FOURNISSEURS).map((cle) => ({ valeur: cle, libelle: Ia.FOURNISSEURS[cle] })) });
    UI.$('option[value=""]', fournisseur).remove();          // toujours un fournisseur choisi
    const delai = UI.champ({ nom: 'delaiS', type: 'entier', libelle: 'Délai de réponse (secondes)' }, String(r.delaiS), {
      id: 'poste-ia-delai', aide: 'De ' + DELAI_MIN_S + ' à ' + DELAI_MAX_S + ' s. Sans carte graphique, une réponse peut prendre plus d\'une minute.' });
    const adresse = UI.champ({ nom: 'url', type: 'texte', libelle: 'Adresse du fournisseur' }, r.url, {
      id: 'poste-ia-url', placeholder: Ia.DEFAUTS.url, aide: aideAdresse(),
      attributs: Object.assign({ inputmode: 'url' }, sansCorrection) });
    const modele = UI.champ({ nom: 'modele', type: 'texte', libelle: 'Modèle' }, r.modele, {
      id: 'poste-ia-modele', placeholder: Ia.DEFAUTS.modele, attributs: sansCorrection,
      aide: 'Conseillé avec Ollama : ' + Ia.DEFAUTS.modele + '. « Tester la connexion » liste les modèles disponibles.' });
    const trouves = UI.element(UI.html`<div class="champ" id="poste-ia-zone-modeles" hidden>
      <label class="libelle" for="poste-ia-liste-modeles">Modèles trouvés chez le fournisseur</label>
      <select id="poste-ia-liste-modeles"></select>
      <p class="aide">Choisir un modèle le recopie dans le champ « Modèle ».</p>
    </div>`);
    return { actif, fournisseur, delai, adresse, modele, trouves, zoneCle: zoneCle(r) };
  }

  // Clé de l'API compatible OpenAI : champ mot de passe toujours vide (jamais réaffichée).
  function zoneCle(r) {
    const zone = UI.element(UI.html`<div class="poste-ia-zone-cle large" id="poste-ia-zone-cle"></div>`);
    const cle = UI.champ({ nom: 'cle', type: 'texte', libelle: 'Clé d\'accès (API compatible OpenAI)' }, '', {
      id: 'poste-ia-cle', placeholder: r.cle ? 'Clé enregistrée : laisser vide pour la garder' : 'Clé fournie par le service',
      aide: 'Gardée dans ce navigateur seulement (jamais dans les fichiers ni le journal) et jamais réaffichée.',
      attributs: { autocomplete: 'new-password', autocapitalize: 'off', spellcheck: 'false' } });
    UI.$('input', cle).type = 'password';
    zone.appendChild(cle);
    if (r.cle) {
      zone.appendChild(UI.champ({ nom: 'effacer_cle', type: 'booleen', libelle: 'Effacer la clé enregistrée' }, '0',
        { id: 'poste-ia-effacer-cle' }));
    }
    zone.hidden = r.fournisseur !== 'openai';
    return zone;
  }

  function brancherIa(formulaire) {
    const champModele = UI.$('#poste-ia-modele', formulaire);
    formulaire.addEventListener('input', () => afficherPortee(formulaire));
    formulaire.addEventListener('change', (evenement) => {
      if (evenement.target.name === 'fournisseur') UI.$('#poste-ia-zone-cle', formulaire).hidden = evenement.target.value !== 'openai';
      afficherPortee(formulaire);
    });
    UI.$('#poste-ia-liste-modeles', formulaire).addEventListener('change', (evenement) => {
      if (evenement.target.value) champModele.value = evenement.target.value;
    });
    const tester = UI.$('#btn-tester-ia', formulaire);
    tester.addEventListener('click', () => pendant(tester, 'test de connexion à l\'IA', () => testerConnexion(formulaire)));
    const enregistrer = UI.$('#btn-enregistrer-ia', formulaire);
    formulaire.addEventListener('submit', (evenement) => {
      evenement.preventDefault();
      pendant(enregistrer, 'réglages de l\'assistant IA', () => enregistrerIa(formulaire));
    });
  }

  /** Carte « Assistant IA » (élément DOM), d'après les réglages enregistrés sur le poste. */
  function carteIa() {
    const r = Ia.reglages();
    const carte = UI.element(UI.html`<article class="carte poste-carte-ia" id="carte-ia">
      <div class="entete-carte"><h2>Assistant IA</h2><span class="badge" id="poste-ia-etat"></span></div>
      <p class="note poste-intro">L'IA propose, vous validez : rien n'est écrit sans votre clic. Sans IA, Prévo
        fonctionne pareil et n'appelle aucun service.</p>
      <form id="form-ia" class="form-grille poste-ia" novalidate></form>
    </article>`);
    const formulaire = UI.$('#form-ia', carte);
    const champs = champsIa(r);
    [champs.actif, champs.adresse, champs.zoneCle].forEach((bloc) => bloc.classList.add('large'));
    [champs.actif, champs.fournisseur, champs.delai, champs.adresse, champs.modele, champs.trouves, champs.zoneCle]
      .forEach((bloc) => formulaire.appendChild(bloc));
    formulaire.appendChild(UI.element(UI.html`<div class="poste-ia-portee large" id="poste-ia-portee" aria-live="polite"></div>`));
    formulaire.appendChild(UI.element(UI.html`<div class="actions">
      <button type="button" class="btn btn-secondaire" id="btn-tester-ia">${UI.icone('actualiser')}Tester la connexion</button>
      <span class="espace"></span>
      <button type="submit" class="btn btn-primaire" id="btn-enregistrer-ia">${UI.icone('valider')}Enregistrer</button>
    </div>`));
    formulaire.appendChild(UI.element(UI.html`<div class="poste-ia-resultat large" id="poste-ia-resultat" aria-live="polite"></div>`));
    remplirEtat(UI.$('#poste-ia-etat', carte));
    afficherPortee(formulaire);
    brancherIa(formulaire);
    return carte;
  }

  // Après un enregistrement : la carte est reconstruite d'après les réglages du poste (clé vidée).
  function remplacerCarteIa() {
    const ancienne = document.getElementById('carte-ia');
    const nouvelle = carteIa();
    if (ancienne) ancienne.replaceWith(nouvelle);
    return nouvelle;
  }

  // ===========================================================================================
  // 5. Carte « Dictée » : activer ou non sur ce poste, état détecté
  // ===========================================================================================

  function carteDictee() {
    return UI.html`<article class="carte" id="carte-dictee" data-hors-saisie>
      <div class="entete-carte"><h2>Dictée vocale</h2></div>
      <p class="note poste-intro">Un bouton micro à côté des champs de description et de compte rendu ; le texte
        dicté s'ajoute à la fin du champ.</p>
      <label class="case"><input type="checkbox" id="poste-dictee-active"><span>Proposer la dictée sur ce poste</span></label>
      <p class="poste-etat-detecte">État détecté : <b id="poste-dictee-etat">…</b></p>
      <div class="actions" id="poste-dictee-actions" hidden>
        <button type="button" class="btn btn-fantome" id="btn-verifier-dictee">${UI.icone('micro')}Où la voix est-elle transcrite ?</button>
      </div>
    </article>`;
  }

  // Raison pour laquelle le navigateur ne propose pas la dictée ici.
  function raisonSansDictee() {
    if (!(window.SpeechRecognition || window.webkitSpeechRecognition)) {
      return 'non proposée : ce navigateur ne reconnaît pas la voix (Chrome ou Edge sur ordinateur le font).';
    }
    return 'non proposée : la page n\'est pas sécurisée (adresse en http:// sur le réseau) ; '
      + 'sur un téléphone, utilisez le micro du clavier.';
  }

  // État détecté à l'affichage : la reconnaissance est-elle proposée ici ? Le lieu de la transcription
  // (sur ce PC ou chez Google / Microsoft) n'est demandé que sur clic : SpeechRecognition.available()
  // est récent et fait planter l'onglet de certaines versions de Chromium (constaté : Chromium 148 sans
  // fenêtre ; Chrome et Edge 155 répondent normalement).
  function afficherEtatDictee(conteneur) {
    const zone = UI.$('#poste-dictee-etat', conteneur);
    const proposee = Dictee.prisEnCharge();
    zone.textContent = proposee ? 'proposée par ce navigateur' : raisonSansDictee();
    UI.$('#poste-dictee-actions', conteneur).hidden = !proposee;
  }

  async function verifierTranscription(conteneur) {
    const zone = UI.$('#poste-dictee-etat', conteneur);
    const locale = await Dictee.transcriptionLocale();
    if (!zone.isConnected) return;
    zone.textContent = locale ? 'proposée par ce navigateur — transcription sur ce PC'
      : 'proposée par ce navigateur — la voix est envoyée à Google ou Microsoft pour être transcrite';
  }

  function brancherDictee(conteneur) {
    const caseActive = UI.$('#poste-dictee-active', conteneur);
    caseActive.checked = Dictee.reglages().active;
    caseActive.addEventListener('change', () => {
      const active = caseActive.checked;
      Dictee.enregistrerReglages({ active });
      if (active) Dictee.equiper(document.body); else Dictee.retirerBoutons();
      UI.toast(active ? 'Dictée activée sur ce poste.' : 'Dictée désactivée sur ce poste.', 'succes');
    });
    afficherEtatDictee(conteneur);
    const verifier = UI.$('#btn-verifier-dictee', conteneur);
    verifier.addEventListener('click', () => pendant(verifier, 'lieu de la transcription', () => verifierTranscription(conteneur)));
  }

  // ===========================================================================================
  // 6. Carte « Affichage » : thème sombre ou clair, appliqué tout de suite
  // ===========================================================================================

  function carteAffichage() {
    return UI.html`<article class="carte" id="carte-affichage" data-hors-saisie>
      <div class="entete-carte"><h2>Affichage</h2></div>
      <fieldset class="poste-themes">
        <legend class="libelle">Thème de l'écran</legend>
        <label class="case"><input type="radio" name="theme" value="sombre" id="poste-theme-sombre"><span>${THEMES.sombre} (par défaut)</span></label>
        <label class="case"><input type="radio" name="theme" value="clair" id="poste-theme-clair"><span>${THEMES.clair} : pièce lumineuse, plein jour</span></label>
      </fieldset>
      <p class="note">Réglage de ce navigateur seulement. L'impression reste en noir sur blanc.</p>
    </article>`;
  }

  function brancherAffichage(conteneur) {
    const actuel = themeMemorise();
    UI.$$('input[name=theme]', conteneur).forEach((bouton) => {
      bouton.checked = bouton.value === actuel;
      bouton.addEventListener('change', () => { if (bouton.checked) choisirTheme(bouton.value); });
    });
  }

  // Carte « Aide à l'écran » (AideEcrans, §23) : explication à la première visite de chaque écran.
  function carteAide() {
    if (typeof AideEcrans === 'undefined') return '';
    return UI.html`<article class="carte" id="carte-aide" data-hors-saisie>
      <div class="entete-carte"><h2>Aide à l'écran</h2></div>
      <label class="case"><input type="checkbox" id="poste-aide-active"><span>Afficher l'explication à la première visite de chaque écran</span></label>
      <div class="actions"><button type="button" class="btn btn-secondaire" id="btn-revoir-aide">Revoir toutes les explications</button></div>
      <p class="note" id="poste-aide-note">Le lien « Explications » du menu rouvre celle de l'écran affiché.</p>
    </article>`;
  }

  function brancherAide(conteneur) {
    const caseActive = UI.$('#poste-aide-active', conteneur);
    if (!caseActive) return;
    caseActive.checked = AideEcrans.active();
    caseActive.addEventListener('change', () => AideEcrans.activer(caseActive.checked));
    UI.$('#btn-revoir-aide', conteneur).addEventListener('click', () => {
      AideEcrans.revoirTout();
      AideEcrans.activer(true);
      caseActive.checked = true;
      UI.remplir(UI.$('#poste-aide-note', conteneur), 'Les explications reviendront à la prochaine visite de chaque écran.');
    });
  }

  // ===========================================================================================
  // 7. Écran et enregistrement
  // ===========================================================================================

  function afficher(conteneur) {
    UI.remplir(conteneur, UI.html`
      <div class="entete-page"><div>
        <h1>Ce poste</h1>
        <p>Réglages de ce navigateur : ils ne changent rien sur les autres postes.</p>
      </div></div>
      <div class="grille poste">
        <div class="c7 poste-colonne" id="poste-colonne-principale">${carteIdentite()}</div>
        <div class="c5 poste-colonne">${carteDictee()}${carteAffichage()}${carteAide()}</div>
      </div>`);
    UI.$('#poste-colonne-principale', conteneur).appendChild(carteIa());
    UI.$('#btn-changer-profil', conteneur).addEventListener('click', () => { App.changerProfil(); });
    brancherDictee(conteneur);
    brancherAffichage(conteneur);
    brancherAide(conteneur);
  }

  // L'état de l'IA change (test, réglages) : badge de la carte à jour. L'autorisation du responsable
  // change (parametres.csv) : portée à jour, sans toucher à la saisie en cours.
  if (typeof Ia !== 'undefined') {
    Ia.evenements.addEventListener('changement', () => {
      const zone = document.getElementById('poste-ia-etat');
      if (zone) remplirEtat(zone);
    });
  }
  if (typeof Donnees !== 'undefined' && Donnees.evenements) {
    Donnees.evenements.addEventListener('changement', (evenement) => {
      const tables = (evenement.detail && evenement.detail.tables) || [];
      if (tables.includes('parametres')) afficherPortee(document.getElementById('form-ia'));
    });
  }

  // App est chargé après les modules : l'écran est enregistré une fois la page lue.
  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'poste', route: /^#\/poste$/, titre: 'Ce poste',
      menu: { libelle: 'Ce poste', icone: 'utilisateur', ordre: 92, groupe: 'Administration' },
      profils: ['demandeur', 'technicien', 'responsable'], tables: ['parametres'],
      afficher,
    });
  });

  return { THEMES, themeMemorise, appliquerTheme, choisirTheme };
})();
