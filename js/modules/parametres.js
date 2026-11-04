'use strict';
// Parametres : écrans « Paramètres » (#/parametres) et « Contrôle de la base » (#/controle),
// réservés au responsable (brief §4 sauvegarde, §6 contrôle de la base, §9 E12).
//
//   Paramètres : entreprise, délais par priorité, préventif et indicateurs (lot 3, §15.11),
//                rafraîchissement (écrits dans parametres.csv par Donnees.modifier), ce poste (nom,
//                profil, lien vers l'écran « Ce poste » #/poste du lot 4), sauvegardes (créer,
//                restaurer ; « Tester » en mode serveur : parametres-sauvegardes.js, §22.11, D133), lien vers
//                le contrôle de la base, lien « Importer des données » (#/import, lot 5), export ZIP ; carte
//                « Codes de défaillance » (parametres-codes.js, appelée par un relais) ; carte « Mode Solo »
//                (mode_solo, solo_technicien_id : §22.11, D132) ; carte « Accès et installation » (parametres-acces.js,
//                §22.10 : PC serveur et responsable seulement).
//   Fichiers du module : parametres.js, parametres-codes.js, parametres-solo.js, parametres-sauvegardes.js,
//                parametres-zip.js (import ZIP, T191), parametres-acces.js.
//   Contrôle   : problèmes de Donnees.problemes() groupés par gravité, attribution des identifiants
//                manquants, relecture des fichiers, liens vers les DI / OT concernés.

const Parametres = (() => {

  // Réglages du formulaire (clé dans parametres.csv, type de champ, libellé, valeur par défaut,
  // bornes min/max pour un nombre, valeurs d'un choix, section : intertitre du formulaire).
  const REGLAGES = [
    { cle: 'entreprise_nom', type: 'texte', libelle: 'Nom de l\'entreprise', defaut: '', large: true, section: 'Entreprise',
      aide: 'Affiché dans le menu et sur les bons de travail.' },
    { cle: 'delai_p1_h', type: 'entier', libelle: 'Délai P1 (heures)', defaut: '0', min: 0, max: 8760, section: 'Délais par priorité',
      aide: 'Date prévue d\'une demande P1 = création + ce délai. 0 : tout de suite.' },
    { cle: 'delai_p2_h', type: 'entier', libelle: 'Délai P2 (heures)', defaut: '24', min: 0, max: 8760,
      aide: '24 heures = le lendemain.' },
    { cle: 'delai_p3_h', type: 'entier', libelle: 'Délai P3 (heures)', defaut: '168', min: 0, max: 8760,
      aide: '168 heures = une semaine.' },
    { cle: 'delai_p4', type: 'texte', libelle: 'Délai P4', defaut: 'prochain arrêt',
      aide: 'Texte libre : une P4 n\'a pas de date prévue automatique.' },
    // Lot 3 (ARCHITECTURE.md §15.11) : les deux clés du lot 2 et trois clés lues par le préventif et les indicateurs.
    { cle: 'priorite_preventif', type: 'choix', valeurs: ['P1', 'P2', 'P3', 'P4'], libelle: 'Priorité des OT préventifs', defaut: 'P3',
      section: 'Préventif et indicateurs', aide: 'Priorité donnée aux OT créés par les gammes échues.' },
    { cle: 'horizon_calendrier_semaines', type: 'entier', libelle: 'Calendrier du préventif (semaines)', defaut: '12', min: 1, max: 52,
      aide: 'Nombre de semaines affichées dans le calendrier du préventif.' },
    { cle: 'tolerance_preventif_pct', type: 'entier', libelle: 'Tolérance du respect du préventif (%)', defaut: '10', min: 0, max: 100,
      aide: 'Un préventif est « respecté » s\'il est clôturé au plus tard à sa date prévue + ce pourcentage de sa période.' },
    { cle: 'seuil_remplacement_pct', type: 'entier', libelle: 'Seuil « réparer ou remplacer » (%)', defaut: '50', min: 1, max: 1000,
      aide: 'Coût des 12 derniers mois / valeur de remplacement à partir duquel le rapport mensuel propose d\'examiner un équipement.' },
    { cle: 'heures_fonct_defaut', type: 'decimal', libelle: 'Heures de fonctionnement par jour (défaut)', defaut: '8', min: 1, max: 24,
      aide: 'Gammes « compteur » seulement : estime l\'échéance d\'un équipement sans heures par jour. Jamais utilisé par les indicateurs.' },
    // Lot 3 bis (ARCHITECTURE.md §16.1) : seuils des suggestions de préventif.
    { cle: 'suggestion_seuil_pannes', type: 'entier', libelle: 'Pannes de même cause pour suggérer', defaut: '3', min: 2, max: 20,
      section: 'Suggestions de préventif', aide: 'Créer une gamme ou revoir le préventif à partir de ce nombre de pannes de même cause sur la période.' },
    { cle: 'suggestion_visites_sans_constat', type: 'entier', libelle: 'Visites sans anomalie pour suggérer d\'allonger', defaut: '5', min: 3, max: 20,
      aide: 'Visites de suite sans anomalie ni panne (criticité B ou C seulement).' },
    { cle: 'suggestion_fenetre_mois', type: 'entier', libelle: 'Période observée (mois)', defaut: '12', min: 3, max: 24,
      aide: 'Les pannes comptées sont celles de ces derniers mois.' },
    // Lot 4 (ARCHITECTURE.md §17.1, D67) : le responsable autorise ou non les fournisseurs d'IA en ligne ; en mode
    // serveur (audit M2, §22.12), la décision est celle du PC serveur : la case la montre sans la changer.
    { cle: 'ia_distant_autorise', type: 'booleen', valeurs: ['0', '1'], defaut: '0', large: true, section: 'Assistant IA',
      decideeParLeServeur: true,
      libelle: 'Autoriser les fournisseurs d\'IA en ligne (OpenAI, Mistral, Groq…)',
      aide: 'Les textes envoyés (descriptions, comptes rendus, désignations) quittent alors l\'atelier. L\'IA locale (Ollama) reste toujours possible.' },
    // Mise à jour signalée (ARCHITECTURE.md §21, D120) : le responsable autorise la lecture de prevo.pro/version.json.
    { cle: 'maj_signalee', type: 'booleen', valeurs: ['0', '1'], defaut: '0', large: true, section: 'Mises à jour',
      libelle: 'Me signaler les nouvelles versions de Prévo',
      aide: 'Prévo lit https://prevo.pro/version.json au plus une fois par jour et par poste (numéro, date, nouveautés) ; rien d\'autre ne part, rien ne s\'installe tout seul.' },
    // Mode Solo (ARCHITECTURE.md §22.11, D132) : profil Responsable avec un réglage, pas un quatrième profil.
    // Hors du formulaire (horsFormulaire) : posés par « Passer en mode Solo » / « Quitter le mode Solo » (carte Mode Solo).
    { cle: 'mode_solo', type: 'booleen', valeurs: ['0', '1'], defaut: '0', large: true, section: 'Mode Solo', horsFormulaire: true,
      libelle: 'Mode Solo : je fais tout moi-même',
      aide: 'Menu allégé (Équipe et Planning sous « Plus »), « Nouvel OT » en premier, vous êtes le technicien de vos OT.' },
    { cle: 'solo_technicien_id', type: 'texte', defaut: '', horsFormulaire: true,
      libelle: 'Technicien « moi » du mode Solo',
      aide: 'Identifiant du technicien créé au passage en mode Solo ; il reste dans l\'équipe si vous quittez ce mode.' },
    // Clôture en une étape (§22.11, D132) : posée à 1 par « Passer en mode Solo », réglable par le responsable hors Solo.
    { cle: 'cloture_une_etape', type: 'booleen', valeurs: ['0', '1'], defaut: '0', large: true, section: 'Ordres de travail',
      libelle: 'Clôture en une étape (bouton « Clore » pour le responsable)',
      aide: 'Une seule fenêtre fait la clôture technique (mêmes champs et contrôles) puis la clôture administrative.' },
    { cle: 'rafraichissement_s', type: 'entier', libelle: 'Rafraîchissement (secondes)', defaut: '20', min: 2, max: 3600,
      section: 'Échanges entre postes', aide: 'Fréquence de lecture des changements faits sur les autres postes.' },
  ];

  // Carte « Codes de défaillance » : dans parametres-codes.js, chargé APRÈS ce fichier ; la fonction
  // est donc cherchée au moment de l'appel (relais), pas au chargement de ce fichier.
  const afficherCodes = (zone) => Parametres.interne.afficherCodes(zone);
  // Carte « Mode Solo » (§22.11, D132) : dans parametres-solo.js, chargé APRÈS ce fichier (même relais) ;
  // absente si ce fichier n'est pas chargé. Elle lit les réglages mode_solo et solo_technicien_id ci-dessus.
  const carteSolo = () => (Parametres.interne.carteSolo ? Parametres.interne.carteSolo(REGLAGES) : '');
  const brancherSolo = (conteneur) => { if (Parametres.interne.brancherSolo) Parametres.interne.brancherSolo(conteneur, pendant); };
  // Sauvegardes du PC serveur (§22.11, D133) : bouton « Tester » d'une ligne et note de la carte, dans
  // parametres-sauvegardes.js, chargé APRÈS ce fichier (même relais) ; sans lui, « Restaurer… » seul.
  const actionsSauvegarde = (sauvegarde, boutonRestaurer) => (Parametres.interne.actionsSauvegarde
    ? Parametres.interne.actionsSauvegarde(sauvegarde, boutonRestaurer, pendant) : boutonRestaurer);
  const noteSauvegardes = () => (Parametres.interne.noteSauvegardes ? Parametres.interne.noteSauvegardes() : '');
  // Import ZIP (T191, D172) : bouton « Importer un ZIP… » de la carte, dans parametres-zip.js (même relais).
  const blocImportZip = () => (Parametres.interne.blocImportZip ? Parametres.interne.blocImportZip() : '');
  const brancherImportZip = (conteneur) => { if (Parametres.interne.brancherImportZip) Parametres.interne.brancherImportZip(conteneur, pendant); };
  // Carte « Accès et installation » (§22.10, D131 dernier point) : dans parametres-acces.js, chargé APRÈS ce fichier
  // (même relais) ; la carte décide elle-même d'exister (mode serveur, PC serveur, responsable) ; absente sans lui.
  const carteAcces = () => (Parametres.interne.carteAcces ? Parametres.interne.carteAcces() : '');
  const brancherAcces = (conteneur) => { if (Parametres.interne.brancherAcces) Parametres.interne.brancherAcces(conteneur, pendant); };

  const NOTE_DECIDE_SUR_LE_SERVEUR = 'Décidé sur le PC serveur (Paramètres › Accès et installation).';

  const LIBELLES_TYPE_PROBLEME = {
    reference: 'Référence cassée', valeur: 'Valeur illisible', excel: 'Abîmé par Excel', colonne: 'Colonne',
    encodage: 'Encodage', doublon: 'Doublon', identifiant: 'Identifiant manquant', incoherence: 'Incohérence',
  };

  // Gravité → titre, ton du badge, explication courte.
  const GRAVITES = [
    { cle: 'erreur', titre: 'Erreurs', ton: 'ko', classe: 'rouge',
      explication: 'À corriger : une donnée est cassée ou introuvable, Prévo ne peut pas s\'y fier.' },
    { cle: 'attention', titre: 'À surveiller', ton: 'attention', classe: 'ambre',
      explication: 'Rien de bloquant, mais un fichier ne suit pas tout à fait le format attendu.' },
    { cle: 'info', titre: 'Informations', ton: 'info', classe: '',
      explication: 'Pour information : Prévo a corrigé ou toléré ces points à la lecture.' },
  ];

  // Route et texte du lien vers la fiche d'une ligne (demande, ordre de travail, équipement).
  const LIENS_FICHES = {
    demandes: { route: '#/di/', texte: 'Ouvrir la DI' },
    ordres_travail: { route: '#/ot/', texte: "Ouvrir l'OT" },
    equipements: { route: '#/equipement/', texte: 'Ouvrir la fiche' },
  };

  // Message à montrer en haut de l'écran après une action (le réaffichage efface l'écran).
  let messageEnAttente = null;

  // ===========================================================================================
  // 1. Petits outils
  // ===========================================================================================

  function pluriel(nombre, singulier, pluriel) {
    return nombre + ' ' + (nombre > 1 ? (pluriel || singulier + 's') : singulier);
  }

  // Désactive un bouton pendant une action ; une erreur gérée s'affiche proprement.
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

  // Après une relecture complète des fichiers (restauration, « Relire »), prévient l'application
  // (le nom de l'entreprise dans le menu peut avoir changé). Origine « local » : pas de réaffichage.
  function annoncerRechargement() {
    Donnees.evenements.dispatchEvent(new CustomEvent('changement', {
      detail: { tables: Schema.nomsTables(), origine: 'local' },
    }));
  }

  // Réaffiche l'écran courant avec un message en haut (type : succes | attention | important | info).
  function reafficherAvecMessage(type, contenu) {
    messageEnAttente = { type: type, contenu: contenu };
    return App.reafficher();
  }

  // UI.bandeau rend un élément DOM : pour l'insérer dans un gabarit UI.html, on le convertit en fragment sûr
  // (le bandeau est créé par UI.bandeau, qui échappe son contenu).
  function bandeauHtml(type, contenu) {
    return UI.brut(UI.bandeau(type, contenu).outerHTML);
  }

  function zoneMessage() {
    const message = messageEnAttente;
    messageEnAttente = null;
    if (!message) return '';
    return UI.html`<div class="alertes" id="message-action">${bandeauHtml(message.type, message.contenu)}</div>`;
  }

  function mettreSurLeBouton(racine, selecteur, action) {
    const bouton = UI.$(selecteur, racine);
    if (bouton) bouton.addEventListener('click', () => action(bouton));
  }

  // ===========================================================================================
  // 2. Sauvegardes
  // ===========================================================================================

  // Nom d'une sauvegarde → texte lisible. « 2026-10-19 » : quotidienne ; « 2026-10-19_153012 » :
  // manuelle ; « …_avant-restauration » : copie de sécurité faite avant une restauration ;
  // « …_avant-format-v2 » : sauvegarde automatique faite juste avant le passage au format 2 ; « …_avant-import-zip » et
  // « …_avant-mise-a-jour » (D170) : avant un import ZIP, avant la mise à jour de Prévo.
  function decrireSauvegarde(nom) {
    const lu = /^(\d{4}-\d{2}-\d{2})(?:_(\d{2})(\d{2})(\d{2}))?(?:(_avant-restauration)|_avant-format-v(\d+)|(_avant-import-zip)|(_avant-import)|(_avant-mise-a-jour))?$/.exec(nom);
    if (!lu) return { date: nom, type: 'Sauvegarde', ton: 'neutre' };
    const date = UI.dateFr(lu[1]) + (lu[2] ? ' à ' + lu[2] + ':' + lu[3] + ':' + lu[4] : '');
    if (lu[5]) return { date: date, type: 'Copie de sécurité', ton: 'attention' };
    if (lu[6]) return { date: date, type: 'Avant format ' + Number(lu[6]), ton: 'info' };
    if (lu[7]) return { date: date, type: 'Avant un import ZIP', ton: 'info' };
    if (lu[8]) return { date: date, type: 'Avant import', ton: 'info' };
    if (lu[9]) return { date: date, type: 'Avant la mise à jour de Prévo', ton: 'info' };
    return lu[2] ? { date: date, type: 'Manuelle', ton: 'info' } : { date: date, type: 'Quotidienne', ton: 'neutre' };
  }

  // { liste, indisponible } : la liste des sauvegardes, ou la raison pour laquelle elle n'existe pas.
  async function lireSauvegardes() {
    if (App.mode === 'demo') {
      return { liste: [], indisponible: 'Indisponible en démo : rien n\'est enregistré, il n\'y a donc rien à sauvegarder. '
        + 'Le bouton « Exporter en ZIP » permet de garder une copie des données.' };
    }
    try {
      return { liste: await App.adaptateur.listerSauvegardes(), indisponible: '' };
    } catch (erreur) {
      console.warn('Prévo : liste des sauvegardes illisible (' + (erreur && erreur.message) + ').', erreur);
      return { liste: [], indisponible: 'Les sauvegardes ne peuvent pas être lues : ' + ((erreur && erreur.message) || 'erreur inconnue') };
    }
  }

  function tableauSauvegardes(liste) {
    const lignes = liste.map((sauvegarde) => Object.assign({ decrite: decrireSauvegarde(sauvegarde.nom) }, sauvegarde));
    return UI.tableau({
      libelle: 'Sauvegardes disponibles',
      colonnes: [
        { cle: 'nom', libelle: 'Sauvegarde', valeurTri: (l) => l.nom,
          rendu: (l) => UI.html`<span class="sauvegarde-nom" title="${l.nom}">${l.decrite.date}</span>` },
        { cle: 'type', libelle: 'Type', valeurTri: (l) => l.decrite.type,
          rendu: (l) => UI.html`<span class="badge ${l.decrite.ton}">${l.decrite.type}</span>` },
        { cle: 'tables', libelle: 'Tables', type: 'nombre', valeurTri: (l) => l.tables.length, rendu: (l) => String(l.tables.length) },
        { cle: 'action', libelle: '', triable: false, rendu: (l) => {
          const bouton = UI.element(UI.html`<button type="button" class="btn btn-secondaire" data-restaurer="${l.nom}">Restaurer…</button>`);
          bouton.addEventListener('click', () => pendant(bouton, 'restauration', () => restaurer(l)));
          return actionsSauvegarde(l, bouton);
        } },
      ],
      lignes: lignes,
      vide: 'Aucune sauvegarde pour le moment.',
    });
  }

  async function sauvegarderMaintenant() {
    const nom = await App.adaptateur.sauvegarder();
    UI.toast('Sauvegarde créée : ' + nom + '.', 'succes');
    await reafficherAvecMessage('succes', UI.html`<b>Sauvegarde créée :</b> <span id="nom-sauvegarde-creee">${nom}</span>.
      Elle contient tous les fichiers dans l'état où ils sont maintenant.`);
  }

  // Fenêtre de choix (toutes les tables / une table) qui explique la copie de sécurité.
  // Renvoie null (annulé) ou { tables: undefined | [nomTable] }.
  async function demanderRestauration(sauvegarde) {
    const decrite = decrireSauvegarde(sauvegarde.nom);
    const options = sauvegarde.tables.map((nomTable) => {
      const description = Schema.table(nomTable);
      return UI.html`<option value="${nomTable}">${description ? description.libelle : nomTable} (${nomTable}.csv)</option>`;
    });
    const contenu = UI.element(UI.html`<div class="form-colonne" id="fenetre-restauration">
      <p>Sauvegarde du <b>${decrite.date}</b> (${decrite.type.charAt(0).toLowerCase() + decrite.type.slice(1)}) : ${pluriel(sauvegarde.tables.length, 'table')}.</p>
      <fieldset class="restauration-choix">
        <legend class="libelle">Que faut-il restaurer ?</legend>
        <label class="case"><input type="radio" name="portee" value="toutes" checked><span>Toutes les tables (retour complet à cette sauvegarde)</span></label>
        <label class="case"><input type="radio" name="portee" value="une"><span>Une seule table</span></label>
        <div class="champ"><select name="table" aria-label="Table à restaurer" disabled>${options}</select></div>
      </fieldset>
      <div class="encadre attention"><b>Rien n'est perdu.</b> Avant de restaurer, Prévo copie l'état actuel
        de <b>toutes</b> les tables dans une « copie de sécurité » (dans le dossier des sauvegardes, nom terminé par
        « _avant-restauration »). Si la restauration ne convient pas, restaurez cette copie pour revenir en arrière.
        Les modifications faites depuis cette sauvegarde seront remplacées dans les tables restaurées.</div>
    </div>`);
    const choixTable = UI.$('select[name=table]', contenu);
    contenu.addEventListener('change', (evenement) => {
      if (evenement.target.name === 'portee') choixTable.disabled = evenement.target.value !== 'une';
    });
    const reponse = await UI.fenetre({
      titre: 'Restaurer une sauvegarde',
      contenu: contenu,
      boutons: [
        { libelle: 'Annuler', valeur: null, classe: 'btn-fantome' },
        { libelle: 'Restaurer', valeur: 'restaurer', classe: 'btn-danger', defaut: true },
      ],
    });
    if (reponse !== 'restaurer') return null;
    const uneSeule = UI.$('input[name=portee]:checked', contenu).value === 'une';
    return { tables: uneSeule ? [choixTable.value] : undefined };
  }

  async function restaurer(sauvegarde) {
    const choix = await demanderRestauration(sauvegarde);
    if (!choix) return;
    const resultat = await App.adaptateur.restaurer(sauvegarde.nom, choix.tables);
    await Donnees.chargerTout();
    annoncerRechargement();
    UI.toast('Restauration faite. Copie de sécurité : ' + resultat.copieSecurite + '.', 'succes');
    await reafficherAvecMessage('succes', UI.html`<b>Restauration faite :</b> ${pluriel(resultat.restaurees.length, 'table restaurée', 'tables restaurées')}
      (${resultat.restaurees.join(', ')}). L'état d'avant a été copié dans la sauvegarde
      <b id="nom-copie-securite">${resultat.copieSecurite}</b> : restaurez-la si ce n'est pas ce que vous vouliez.`);
  }

  // ===========================================================================================
  // 3. Écran Paramètres
  // ===========================================================================================

  // Réglages saisis dans le formulaire « Réglages » (ceux du mode Solo ont leur propre carte).
  function reglagesDuFormulaire() {
    return REGLAGES.filter((reglage) => !reglage.horsFormulaire);
  }

  // Mode serveur (audit M2) : réglage montré tel que le PC serveur l'a décidé, jamais écrit par ce formulaire.
  function decideSurLeServeur(reglage) {
    return Boolean(reglage.decideeParLeServeur) && App.mode === 'serveur';
  }

  function reglagesEnregistres() {
    return reglagesDuFormulaire().filter((reglage) => !decideSurLeServeur(reglage));
  }

  function valeurAffichee(reglage) {
    if (!decideSurLeServeur(reglage)) return Donnees.parametre(reglage.cle, reglage.defaut);
    const serveur = typeof Ia !== 'undefined' && Ia.reglagesServeur ? Ia.reglagesServeur() : null;
    return serveur && serveur.enLigne ? '1' : '0';
  }

  // Décision du PC serveur relue à chaque affichage de l'écran (GET /api/ia/reglages), en mode serveur seulement.
  function lireDecisionsDuServeur() {
    return App.mode === 'serveur' && typeof Ia !== 'undefined' && Ia.lireReglagesServeur ? Ia.lireReglagesServeur() : null;
  }

  function formulaireReglages() {
    const formulaire = UI.element(UI.html`<form id="form-parametres" class="form-grille" novalidate></form>`);
    reglagesDuFormulaire().forEach((reglage) => {
      if (reglage.section) formulaire.appendChild(UI.element(UI.html`<h3 class="large parametres-section">${reglage.section}</h3>`));
      const surServeur = decideSurLeServeur(reglage);
      const bloc = UI.champ({ nom: reglage.cle, type: reglage.type, libelle: reglage.libelle, valeurs: reglage.valeurs },
        valeurAffichee(reglage), { aide: surServeur ? NOTE_DECIDE_SUR_LE_SERVEUR + ' ' + reglage.aide : reglage.aide,
          lectureSeule: surServeur });
      if (reglage.large) bloc.classList.add('large');
      formulaire.appendChild(bloc);
    });
    formulaire.appendChild(UI.element(UI.html`<div class="actions"><span class="espace"></span>
      <button type="submit" class="btn btn-primaire">${UI.icone('valider')}Enregistrer</button></div>`));
    formulaire.addEventListener('submit', (evenement) => {
      evenement.preventDefault();
      enregistrerReglages(formulaire);
    });
    return formulaire;
  }

  /** Message d'erreur d'un réglage (nombre hors bornes, entier attendu, choix inconnu), sinon ''. */
  function erreurReglage(reglage, valeur) {
    if (reglage.valeurs) return reglage.valeurs.includes(valeur) ? '' : 'Choisissez parmi : ' + reglage.valeurs.join(', ') + '.';
    if (reglage.min === undefined) return '';
    const nombre = Donnees.nombre(valeur);
    const entier = reglage.type === 'entier';
    if (nombre !== null && nombre >= reglage.min && nombre <= reglage.max && (!entier || Number.isInteger(nombre))) return '';
    return entier ? 'Saisissez un nombre entier entre ' + reglage.min + ' et ' + reglage.max + '.'
      : 'Saisissez un nombre entre ' + reglage.min + ' et ' + reglage.max + ' (ex. 7,5).';
  }

  // Contrôle des valeurs puis écriture dans parametres.csv (une ligne par clé, créée si elle manque).
  async function enregistrerReglages(formulaire) {
    const bouton = UI.$('button[type=submit]', formulaire);
    const syntaxe = UI.verifierFormulaire(formulaire);
    const valeurs = UI.lireFormulaire(formulaire);
    let erreurs = syntaxe.length;
    reglagesEnregistres().forEach((reglage) => {
      if (syntaxe.some((e) => e.nom === reglage.cle)) return;
      const message = erreurReglage(reglage, valeurs[reglage.cle]);
      if (message) {
        UI.erreurChamp(formulaire, reglage.cle, message);
        erreurs += 1;
      }
    });
    if (erreurs > 0) {
      const premier = UI.$('[aria-invalid="true"]', formulaire);
      if (premier) premier.focus();
      UI.toast(pluriel(erreurs, 'champ') + ' à corriger.', 'erreur');
      return;
    }
    await pendant(bouton, 'enregistrement des paramètres', async () => {
      await Donnees.modifier('parametres', (lignes) => {
        reglagesEnregistres().forEach((reglage) => {
          const nombre = reglage.type === 'entier' || reglage.type === 'decimal';
          const valeur = nombre ? String(Donnees.nombre(valeurs[reglage.cle])) : valeurs[reglage.cle];
          const ligne = lignes.find((l) => l.cle === reglage.cle);
          if (ligne) ligne.valeur = valeur; else lignes.push({ cle: reglage.cle, valeur: valeur });
        });
      }, { action: 'paramètres généraux' });
      App.marquerSaisie(false);
      UI.toast('Paramètres enregistrés.', 'succes');
    });
  }

  function carteSauvegardes(sauvegardes) {
    return UI.html`<article class="carte" id="carte-sauvegardes">
      <div class="entete-carte"><h2>Sauvegardes</h2>
        ${sauvegardes.indisponible ? '' : UI.html`<button type="button" class="btn btn-primaire" id="btn-sauvegarder">${UI.icone('sauvegarde')}Sauvegarder maintenant</button>`}
      </div>
      <p class="note sauvegardes-explication">Prévo copie tous les fichiers une fois par jour, avant la première modification de la journée.
        Vous pouvez aussi sauvegarder à la demande, par exemple avant un gros changement.
        Avant de passer les fichiers à un nouveau format, Prévo fait aussi une sauvegarde (« Avant format … »).</p>
      ${sauvegardes.indisponible ? '' : noteSauvegardes()}
      ${sauvegardes.indisponible
        ? bandeauHtml('info', sauvegardes.indisponible)
        : UI.html`<div id="zone-sauvegardes"></div>`}
      ${blocImportZip()}
    </article>`;
  }

  async function afficherParametres(conteneur) {
    const [sauvegardes] = await Promise.all([lireSauvegardes(), lireDecisionsDuServeur()]);
    // Si l'utilisateur est parti ailleurs pendant l'attente, on n'écrase pas son nouvel écran.
    if (!/^#\/parametres/.test(location.hash)) return;

    const problemes = Donnees.problemes();
    const nombreErreurs = problemes.filter((p) => p.gravite === 'erreur').length;
    const nombreAttention = problemes.filter((p) => p.gravite === 'attention').length;
    const resumeControle = nombreErreurs + nombreAttention === 0
      ? UI.html`<span class="badge ok">Aucun problème</span>`
      : UI.html`${nombreErreurs ? UI.html`<span class="badge ko">${pluriel(nombreErreurs, 'erreur')}</span> ` : ''}${nombreAttention ? UI.html`<span class="badge attention">${pluriel(nombreAttention, 'point', 'points')} à surveiller</span>` : ''}`;

    UI.remplir(conteneur, UI.html`
      <div class="entete-page"><div>
        <h1>Paramètres</h1>
        <p>Réglages de l'entreprise, sauvegardes et contrôle des données.</p>
      </div></div>
      ${zoneMessage()}
      <div class="grille parametres-grille">
        <div class="c7">
          <article class="carte">
            <div class="entete-carte"><h2>Réglages</h2></div>
            <div id="zone-formulaire"></div>
          </article>
          ${carteSauvegardes(sauvegardes)}
          ${carteAcces()}
        </div>
        <div class="c5">
          ${carteSolo()}
          <article class="carte">
            <div class="entete-carte"><h2>Ce poste</h2></div>
            <dl class="valeurs">
              <dt>Nom du poste</dt><dd id="poste-nom">${App.poste}</dd>
              <dt>Profil</dt><dd id="poste-profil">${App.libelleProfil()}</dd>
              <dt>Stockage</dt><dd>${App.adaptateur.libelle || App.mode}</dd>
            </dl>
            <p class="note">Nom, profil, assistant IA, dictée et thème de ce navigateur se règlent dans « Ce poste ».</p>
            <div class="actions"><a class="btn btn-secondaire" id="lien-ce-poste" href="#/poste">${UI.icone('utilisateur')}Ouvrir « Ce poste »</a></div>
          </article>
          <article class="carte">
            <div class="entete-carte"><h2>Contrôle de la base</h2>${resumeControle}</div>
            <p>Prévo vérifie à chaque lecture que les références (équipement, technicien…), les identifiants et les valeurs des fichiers sont cohérents.</p>
            <div class="actions"><a class="btn btn-secondaire" id="lien-controle" href="#/controle">${UI.icone('controle')}Contrôle de la base</a></div>
          </article>
          <article class="carte" id="carte-import">
            <div class="entete-carte"><h2>Importer des données</h2></div>
            <p>Reprenez vos listes existantes (équipements, articles, fournisseurs, historique des interventions…) depuis
              Excel, OpenDocument ou CSV : Prévo montre tout avant d'écrire, et l'import peut être annulé.</p>
            <div class="actions"><a class="btn btn-secondaire" id="lien-import" href="#/import">${UI.icone('document')}Importer des données</a></div>
          </article>
          <article class="carte">
            <div class="entete-carte"><h2>Exporter les données</h2></div>
            <p>Un fichier ZIP avec les ${Schema.nomsTables().length} fichiers CSV (lisibles dans Excel) et les documents joints.</p>
            <div class="actions"><button type="button" class="btn btn-secondaire" id="btn-export-zip">${UI.icone('export')}Exporter en ZIP</button></div>
          </article>
        </div>
      </div>
      <div id="zone-codes"></div>`);

    UI.remplir(UI.$('#zone-formulaire', conteneur), formulaireReglages());
    afficherCodes(UI.$('#zone-codes', conteneur));
    if (!sauvegardes.indisponible) {
      UI.$('#zone-sauvegardes', conteneur).appendChild(tableauSauvegardes(sauvegardes.liste));
      mettreSurLeBouton(conteneur, '#btn-sauvegarder', (bouton) => pendant(bouton, 'sauvegarde', sauvegarderMaintenant));
    }
    brancherSolo(conteneur);
    brancherAcces(conteneur);
    brancherImportZip(conteneur);
    mettreSurLeBouton(conteneur, '#btn-export-zip', (bouton) => pendant(bouton, 'export ZIP', () => App.exporterZip()));
  }

  // ===========================================================================================
  // 4. Écran Contrôle de la base
  // ===========================================================================================

  // Numéro de la ligne dans le fichier CSV (l'en-tête est la ligne 1), ou null s'il est inconnu.
  // Les problèmes de lecture le portent déjà ; les contrôles de cohérence le retrouvent par
  // l'identifiant (ou par le « n° » écrit dans leur message) en comptant les retours à la ligne
  // contenus dans les cellules des lignes précédentes.
  function numeroLigneFichier(probleme) {
    if (probleme.ligne !== null && probleme.ligne !== undefined) return probleme.ligne;
    const description = Schema.table(probleme.table);
    if (!description) return null;
    const lignes = Donnees.lignes(probleme.table);
    let position = -1;
    if (probleme.type === 'identifiant' || probleme.type === 'doublon') {
      const lu = /n° (\d+)/.exec(probleme.message || '');
      if (lu) position = Number(lu[1]) - 1;
    } else if (probleme.id) {
      position = lignes.findIndex((ligne) => ligne[description.cle] === probleme.id);
    }
    if (position < 0 || position >= lignes.length) return null;
    let numero = 2 + position;
    for (let i = 0; i < position; i += 1) {
      Object.keys(lignes[i]).forEach((nomChamp) => {
        const sauts = String(lignes[i][nomChamp]).match(/\n/g);
        if (sauts) numero += sauts.length;
      });
    }
    return numero;
  }

  // Liens vers les fiches concernées : la ligne en cause et, pour une incohérence, la fiche liée.
  function liensVoir(probleme) {
    const liens = [];
    if (probleme.id && LIENS_FICHES[probleme.table] && Donnees.trouver(probleme.table, probleme.id)) {
      liens.push({ href: LIENS_FICHES[probleme.table].route + encodeURIComponent(probleme.id), texte: LIENS_FICHES[probleme.table].texte });
    }
    if (probleme.type === 'incoherence' && probleme.valeur) {
      const tableLiee = probleme.table === 'demandes' ? 'ordres_travail' : 'demandes';
      if (Donnees.trouver(tableLiee, probleme.valeur)) {
        liens.push({ href: LIENS_FICHES[tableLiee].route + encodeURIComponent(probleme.valeur), texte: LIENS_FICHES[tableLiee].texte });
      }
    }
    return liens;
  }

  // Problèmes avec leur numéro de ligne, rangés par table puis par ligne.
  function problemesAvecLigne(problemes) {
    const lignes = problemes.map((probleme) => ({ probleme: probleme, numero: numeroLigneFichier(probleme) }));
    const rangTable = (nomTable) => Schema.nomsTables().indexOf(nomTable);
    return lignes.sort((a, b) => rangTable(a.probleme.table) - rangTable(b.probleme.table)
      || (a.numero === null ? 1e9 : a.numero) - (b.numero === null ? 1e9 : b.numero));
  }

  // Téléphone : une carte par problème (un tableau de 8 colonnes ne tient pas sur 375 px).
  function listeProblemes(problemes) {
    const cartes = problemesAvecLigne(problemes).map(({ probleme, numero }) => {
      const description = Schema.table(probleme.table);
      return UI.html`<li><div class="carte-ligne">
        <div class="carte-tete"><b>${probleme.id || 'Sans identifiant'}</b><span class="badge neutre">${LIBELLES_TYPE_PROBLEME[probleme.type] || probleme.type}</span></div>
        <div class="carte-titre">${probleme.message}</div>
        <div class="carte-meta"><span>${description ? description.fichier : probleme.table}</span>${numero === null ? '' : UI.html`<span>ligne ${numero}</span>`}${probleme.champ ? UI.html`<span>champ ${probleme.champ}</span>` : ''}${probleme.valeur ? UI.html`<span>valeur <code>${probleme.valeur}</code></span>` : ''}</div>
        <div class="carte-meta">${liensVoir(probleme).map((lien) => UI.html`<a class="lien-fiche" href="${lien.href}">${lien.texte}</a>`)}</div>
      </div></li>`;
    });
    return UI.element(UI.html`<ul class="liste-cartes liste-problemes">${cartes}</ul>`);
  }

  function tableauProblemes(problemes) {
    if (UI.estTelephone()) return listeProblemes(problemes);
    const lignes = problemesAvecLigne(problemes);
    return UI.tableau({
      libelle: 'Problèmes détectés',
      colonnes: [
        { cle: 'type', libelle: 'Type', valeurTri: (l) => l.probleme.type,
          rendu: (l) => UI.html`<span class="badge neutre">${LIBELLES_TYPE_PROBLEME[l.probleme.type] || l.probleme.type}</span>` },
        { cle: 'table', libelle: 'Table', valeurTri: (l) => l.probleme.table,
          rendu: (l) => { const d = Schema.table(l.probleme.table); return d ? d.fichier : l.probleme.table; } },
        { cle: 'ligne', libelle: 'Ligne', type: 'nombre', valeurTri: (l) => l.numero, rendu: (l) => (l.numero === null ? '—' : String(l.numero)) },
        { cle: 'id', libelle: 'Identifiant', valeurTri: (l) => l.probleme.id, rendu: (l) => l.probleme.id || '—', classe: 'sans-coupure' },
        { cle: 'champ', libelle: 'Champ', valeurTri: (l) => l.probleme.champ, rendu: (l) => l.probleme.champ || '—' },
        { cle: 'valeur', libelle: 'Valeur', valeurTri: (l) => l.probleme.valeur,
          rendu: (l) => (l.probleme.valeur ? UI.html`<code>${l.probleme.valeur}</code>` : '—') },
        { cle: 'message', libelle: 'Message', valeurTri: (l) => l.probleme.message, classe: 'message-probleme',
          rendu: (l) => l.probleme.message },
        { cle: 'voir', libelle: 'Voir', triable: false, classe: 'sans-coupure', rendu: (l) => {
          const liens = liensVoir(l.probleme);
          return liens.length ? UI.html`${liens.map((lien) => UI.html`<a class="lien-fiche" href="${lien.href}">${lien.texte}</a>`)}` : '—';
        } },
      ],
      lignes: lignes,
    });
  }

  // Tables ayant des lignes sans identifiant ET une façon de calculer un identifiant.
  function identifiantsAttribuables() {
    const parTable = new Map();
    Donnees.problemes().filter((p) => p.type === 'identifiant').forEach((p) => {
      const description = Schema.table(p.table);
      if (description && description.identifiant) parTable.set(p.table, (parTable.get(p.table) || 0) + 1);
    });
    return parTable;
  }

  // Année d'un identifiant annuel (DI-2026-0001) : celle de la date de la ligne, sinon d'aujourd'hui.
  function dateDeLigne(ligne) {
    const date = ligne.date_heure || ligne.date_creation || '';
    return date ? date.slice(0, 10) : undefined;
  }

  async function attribuerIdentifiants() {
    const parTable = identifiantsAttribuables();
    const total = Array.from(parTable.values()).reduce((somme, n) => somme + n, 0);
    const detail = Array.from(parTable.entries()).map(([nomTable, n]) => Schema.table(nomTable).fichier + ' (' + n + ')').join(', ');
    const accord = await UI.confirmer('Prévo va donner un identifiant à ' + pluriel(total, 'ligne') + ' qui n\'en ont pas : '
      + detail + '. Les lignes sont conservées, chaque attribution est écrite au journal. '
      + 'Les autres problèmes (références cassées, doublons…) ne sont pas modifiés.',
    { titre: 'Attribuer les identifiants manquants', oui: 'Attribuer', non: 'Annuler' });
    if (!accord) return;
    let attribues = 0;
    for (const nomTable of parTable.keys()) {
      const cle = Schema.table(nomTable).cle;
      attribues += await Donnees.modifier(nomTable, (lignes, outils) => {
        let compte = 0;
        lignes.forEach((ligne) => {
          if (ligne[cle] === '') {
            ligne[cle] = outils.nouvelId(lignes, dateDeLigne(ligne));
            compte += 1;
          }
        });
        return compte;
      }, { action: 'attribution des identifiants manquants' });
    }
    UI.toast(pluriel(attribues, 'identifiant attribué', 'identifiants attribués') + '.', 'succes');
    await reafficherAvecMessage('succes', UI.html`<b>${pluriel(attribues, 'identifiant attribué', 'identifiants attribués')}.</b>
      Ouvrez les lignes concernées pour les compléter si besoin.`);
  }

  async function relireFichiers() {
    await Donnees.chargerTout();
    annoncerRechargement();
    UI.toast('Fichiers relus.', 'succes');
    await reafficherAvecMessage('info', 'Les fichiers ont été relus depuis le stockage : le contrôle ci-dessous est à jour.');
  }

  function carteGravite(gravite, problemes) {
    const parType = new Map();
    problemes.forEach((p) => parType.set(p.type, (parType.get(p.type) || 0) + 1));
    return UI.html`<article class="carte carte-gravite" data-gravite="${gravite.cle}">
      <div class="entete-carte"><h2>${gravite.titre}</h2><span class="badge ${gravite.ton}">${problemes.length}</span></div>
      <p class="note">${gravite.explication}</p>
      <p class="controle-types">${Array.from(parType.entries()).map(([type, n]) =>
        UI.html`<span class="badge neutre">${LIBELLES_TYPE_PROBLEME[type] || type} : ${n}</span>`)}</p>
      <div data-tableau="${gravite.cle}"></div>
    </article>`;
  }

  function afficherControle(conteneur) {
    const problemes = Donnees.problemes();
    const aAttribuer = identifiantsAttribuables();
    const totalAAttribuer = Array.from(aAttribuer.values()).reduce((somme, n) => somme + n, 0);
    const groupes = GRAVITES.map((gravite) => ({ gravite: gravite, liste: problemes.filter((p) => p.gravite === gravite.cle) }));

    UI.remplir(conteneur, UI.html`
      <div class="entete-page"><div>
        <div class="fil"><a href="#/parametres">Paramètres</a> › <span>Contrôle de la base</span></div>
        <h1>Contrôle de la base</h1>
        <p>Prévo vérifie les ${Schema.nomsTables().length} fichiers à chaque lecture : jamais une donnée cassée n'est ignorée en silence.</p>
      </div>
      <div class="actions">
        <button type="button" class="btn btn-secondaire" id="btn-relire">${UI.icone('actualiser')}Relire les fichiers</button>
        ${totalAAttribuer ? UI.html`<button type="button" class="btn btn-primaire" id="btn-attribuer">${UI.icone('valider')}Attribuer les identifiants manquants (${totalAAttribuer})</button>` : ''}
      </div></div>
      ${zoneMessage()}
      <div class="instruments controle-compteurs">
        ${groupes.map((g) => UI.html`<div class="${g.gravite.classe}" data-compteur="${g.gravite.cle}">
          <div class="lib">${g.gravite.titre}</div><div class="chiffre">${g.liste.length}</div></div>`)}
      </div>
      ${problemes.length === 0
        ? bandeauHtml('succes', UI.html`<b>Aucun problème détecté.</b> Les références, les identifiants et les valeurs des 22 fichiers sont cohérents.`)
        : ''}
      <div id="zone-groupes">${groupes.filter((g) => g.liste.length > 0).map((g) => carteGravite(g.gravite, g.liste))}</div>`);

    groupes.filter((g) => g.liste.length > 0).forEach((g) => {
      UI.$('[data-tableau="' + g.gravite.cle + '"]', conteneur).appendChild(tableauProblemes(g.liste));
    });
    mettreSurLeBouton(conteneur, '#btn-relire', (bouton) => pendant(bouton, 'relecture des fichiers', relireFichiers));
    mettreSurLeBouton(conteneur, '#btn-attribuer', (bouton) => pendant(bouton, 'attribution des identifiants', attribuerIdentifiants));
  }

  // ===========================================================================================
  // 5. Enregistrement des écrans
  // ===========================================================================================

  // App est chargé après les modules : les écrans sont enregistrés une fois la page lue.
  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'parametres', route: /^#\/parametres$/, titre: 'Paramètres',
      menu: { libelle: 'Paramètres', icone: 'parametres', ordre: 90, groupe: 'Administration' },
      profils: ['responsable'], tables: ['parametres', 'codes_defaillance'],
      afficher: afficherParametres,
    });
    App.ecran({
      id: 'controle', route: /^#\/controle$/, titre: 'Contrôle de la base', parent: 'parametres',
      profils: ['responsable'],
      // Le contrôle peut changer avec n'importe quelle table (sauf le journal).
      tables: Schema.nomsTables().filter((nomTable) => nomTable !== 'journal'),
      afficher: afficherControle,
    });
  });

  // interne : complété par parametres-codes.js (afficherCodes), usage interne au module (pas une API).
  return { decrireSauvegarde, numeroLigneFichier, interne: {} };
})();
