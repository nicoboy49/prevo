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
    { cle: 'entreprise_nom', type: 'texte', get libelle() { return I18n.t('parametres.libelle.nom_entreprise'); }, defaut: '', large: true, get section() { return I18n.t('parametres.section.entreprise'); },
      get aide() { return I18n.t('parametres.aide.affiche_menu_bons_travail'); } },
    // Chantier multilingue, Lot 4 (T295, D149) : langue des postes sans choix et des textes écrits dans les données
    // (D156). Valeurs : les langues déclarées (js/i18n/langues.js), affichées sous leur nom dans leur langue.
    { cle: 'langue_defaut', type: 'choix', get valeurs() { return I18n.langues.map((langue) => langue.code); }, defaut: 'fr', langues: true,
      get libelle() { return I18n.t('parametres.libelle.langue_installation'); },
      get aide() { return I18n.t('parametres.aide.langue_proposee_postes_textes'); } },
    // Devise (T304, D152) : code ISO 4217 ; la liste courte, ou « autre » avec un champ (devise_autre) ; n'affecte que l'affichage.
    { cle: 'devise', type: 'choix', valeurs: ['EUR', 'CHF', 'GBP', 'USD', 'TRY'], defaut: 'EUR', devises: true,
      get libelle() { return I18n.t('parametres.libelle.devise'); },
      get aide() { return I18n.t('parametres.aide.devise_affichage_seulement'); } },
    { cle: 'delai_p1_h', type: 'entier', get libelle() { return I18n.t('parametres.libelle.delai_p_1_heures'); }, defaut: '0', min: 0, max: 8760, get section() { return I18n.t('parametres.section.delais_priorite'); },
      get aide() { return I18n.t('parametres.aide.date_prevue_demande_p'); } },
    { cle: 'delai_p2_h', type: 'entier', get libelle() { return I18n.t('parametres.libelle.delai_p_2_heures'); }, defaut: '24', min: 0, max: 8760,
      get aide() { return I18n.t('parametres.aide.24_heures_lendemain'); } },
    { cle: 'delai_p3_h', type: 'entier', get libelle() { return I18n.t('parametres.libelle.delai_p_3_heures'); }, defaut: '168', min: 0, max: 8760,
      get aide() { return I18n.t('parametres.aide.168_heures_semaine'); } },
    { cle: 'delai_p4', type: 'texte', get libelle() { return I18n.t('parametres.libelle.delai_p_4'); }, get defaut() { return I18n.t('parametres.defaut.prochain_arret'); },
      get aide() { return I18n.t('parametres.aide.texte_libre_p_4'); } },
    // Lot 3 (ARCHITECTURE.md §15.11) : les deux clés du lot 2 et trois clés lues par le préventif et les indicateurs.
    { cle: 'priorite_preventif', type: 'choix', valeurs: ['P1', 'P2', 'P3', 'P4'], get libelle() { return I18n.t('parametres.libelle.priorite_ot_preventifs'); }, defaut: 'P3',
      get section() { return I18n.t('parametres.section.preventif_indicateurs'); }, get aide() { return I18n.t('parametres.aide.priorite_donnee_ot_crees'); } },
    { cle: 'horizon_calendrier_semaines', type: 'entier', get libelle() { return I18n.t('parametres.libelle.calendrier_preventif_semaines'); }, defaut: '12', min: 1, max: 52,
      get aide() { return I18n.t('parametres.aide.nombre_semaines_affichees_calendrier'); } },
    { cle: 'tolerance_preventif_pct', type: 'entier', get libelle() { return I18n.t('parametres.libelle.tolerance_respect_preventif'); }, defaut: '10', min: 0, max: 100,
      get aide() { return I18n.t('parametres.aide.preventif_respecte_cloture_plus'); } },
    { cle: 'seuil_remplacement_pct', type: 'entier', get libelle() { return I18n.t('parametres.libelle.seuil_reparer_remplacer'); }, defaut: '50', min: 1, max: 1000,
      get aide() { return I18n.t('parametres.aide.cout_12_derniers_mois'); } },
    { cle: 'heures_fonct_defaut', type: 'decimal', get libelle() { return I18n.t('parametres.libelle.heures_fonctionnement_jour_defaut'); }, defaut: '8', min: 1, max: 24,
      get aide() { return I18n.t('parametres.aide.gammes_compteur_seulement_estime'); } },
    // Lot 3 bis (ARCHITECTURE.md §16.1) : seuils des suggestions de préventif.
    { cle: 'suggestion_seuil_pannes', type: 'entier', get libelle() { return I18n.t('parametres.libelle.pannes_meme_cause_suggerer'); }, defaut: '3', min: 2, max: 20,
      get section() { return I18n.t('parametres.section.suggestions_preventif'); }, get aide() { return I18n.t('parametres.aide.creer_gamme_revoir_preventif'); } },
    { cle: 'suggestion_visites_sans_constat', type: 'entier', get libelle() { return I18n.t('parametres.libelle.visites_sans_anomalie_suggerer'); }, defaut: '5', min: 3, max: 20,
      get aide() { return I18n.t('parametres.aide.visites_suite_sans_anomalie'); } },
    { cle: 'suggestion_fenetre_mois', type: 'entier', get libelle() { return I18n.t('parametres.libelle.periode_observee_mois'); }, defaut: '12', min: 3, max: 24,
      get aide() { return I18n.t('parametres.aide.pannes_comptees_sont_celles'); } },
    // Lot 4 (ARCHITECTURE.md §17.1, D67) : le responsable autorise ou non les fournisseurs d'IA en ligne ; en mode
    // serveur (audit M2, §22.12), la décision est celle du PC serveur : la case la montre sans la changer.
    { cle: 'ia_distant_autorise', type: 'booleen', valeurs: ['0', '1'], defaut: '0', large: true, get section() { return I18n.t('parametres.section.assistant_ia'); },
      decideeParLeServeur: true,
      get libelle() { return I18n.t('parametres.libelle.autoriser_fournisseurs_ia_ligne'); },
      get aide() { return I18n.t('parametres.aide.textes_envoyes_descriptions_comptes'); } },
    // Mise à jour signalée (ARCHITECTURE.md §21, D120 ; T305, D175 : active par défaut) : lecture de prevo.pro/version.json.
    { cle: 'maj_signalee', type: 'booleen', valeurs: ['0', '1'], defaut: '1', large: true, get section() { return I18n.t('parametres.section.mises_jour'); },
      get libelle() { return I18n.t('parametres.libelle.me_signaler_nouvelles_versions'); },
      get aide() { return I18n.t('parametres.aide.prevo_lit_https_prevo'); } },
    // Mode Solo (ARCHITECTURE.md §22.11, D132) : profil Responsable avec un réglage, pas un quatrième profil.
    // Hors du formulaire (horsFormulaire) : posés par « Passer en mode Solo » / « Quitter le mode Solo » (carte Mode Solo).
    { cle: 'mode_solo', type: 'booleen', valeurs: ['0', '1'], defaut: '0', large: true, get section() { return I18n.t('parametres.section.mode_solo'); }, horsFormulaire: true,
      get libelle() { return I18n.t('parametres.libelle.mode_solo_je_fais'); },
      get aide() { return I18n.t('parametres.aide.menu_allege_equipe_planning'); } },
    { cle: 'solo_technicien_id', type: 'texte', defaut: '', horsFormulaire: true,
      get libelle() { return I18n.t('parametres.libelle.technicien_moi_mode_solo'); },
      get aide() { return I18n.t('parametres.aide.identifiant_technicien_cree_passage'); } },
    // Clôture en une étape (§22.11, D132) : posée à 1 par « Passer en mode Solo », réglable par le responsable hors Solo.
    { cle: 'cloture_une_etape', type: 'booleen', valeurs: ['0', '1'], defaut: '0', large: true, get section() { return I18n.t('parametres.section.ordres_travail'); },
      get libelle() { return I18n.t('parametres.libelle.cloture_etape_bouton_clore'); },
      get aide() { return I18n.t('parametres.aide.seule_fenetre_fait_cloture'); } },
    { cle: 'rafraichissement_s', type: 'entier', get libelle() { return I18n.t('parametres.libelle.rafraichissement_secondes'); }, defaut: '20', min: 2, max: 3600,
      get section() { return I18n.t('parametres.section.echanges_entre_postes'); }, get aide() { return I18n.t('parametres.aide.frequence_lecture_changements_faits'); } },
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

  // Textes lus à l'affichage (fonctions, accesseurs), jamais figés au chargement du module.
  const noteDecideSurLeServeur = () => I18n.t('parametres.note_decide_sur_le_serveur.decide_pc_serveur_parametres');

  const libelleTypeProbleme = (type) => ({
    reference: I18n.t('parametres.libelle_type_probleme.reference_cassee'), valeur: I18n.t('parametres.libelle_type_probleme.valeur_illisible'), excel: I18n.t('parametres.libelle_type_probleme.abime_excel'), colonne: I18n.t('parametres.libelle_type_probleme.colonne'),
    encodage: I18n.t('parametres.libelle_type_probleme.encodage'), doublon: I18n.t('parametres.libelle_type_probleme.doublon'), identifiant: I18n.t('parametres.libelle_type_probleme.identifiant_manquant'), incoherence: I18n.t('parametres.libelle_type_probleme.incoherence'),
  })[type] || type;

  // Gravité → titre, ton du badge, explication courte.
  const GRAVITES = [
    { cle: 'erreur', get titre() { return I18n.t('parametres.titre.erreurs'); }, ton: 'ko', classe: 'rouge',
      get explication() { return I18n.t('parametres.explication.corriger_donnee_cassee_introuvable'); } },
    { cle: 'attention', get titre() { return I18n.t('parametres.titre.surveiller'); }, ton: 'attention', classe: 'ambre',
      get explication() { return I18n.t('parametres.explication.rien_bloquant_mais_fichier'); } },
    { cle: 'info', get titre() { return I18n.t('parametres.titre.informations'); }, ton: 'info', classe: '',
      get explication() { return I18n.t('parametres.explication.information_prevo_corrige_tolere'); } },
  ];

  // Route et texte du lien vers la fiche d'une ligne (demande, ordre de travail, équipement).
  const LIENS_FICHES = {
    demandes: { route: '#/di/', get texte() { return I18n.t('parametres.texte.ouvrir_di'); } },
    ordres_travail: { route: '#/ot/', get texte() { return I18n.t('parametres.texte.ouvrir_ot'); } },
    equipements: { route: '#/equipement/', get texte() { return I18n.t('parametres.texte.ouvrir_fiche'); } },
  };

  // Message à montrer en haut de l'écran après une action (le réaffichage efface l'écran).
  let messageEnAttente = null;

  // ===========================================================================================
  // 1. Petits outils
  // ===========================================================================================

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
    if (!lu) return { date: nom, type: I18n.t('parametres.decrire_sauvegarde.sauvegarde'), ton: 'neutre' };
    const date = lu[2] ? I18n.t('parametres.decrire_sauvegarde.date_heure', { date: UI.dateFr(lu[1]), heures: lu[2], minutes: lu[3], secondes: lu[4] }) : UI.dateFr(lu[1]);
    if (lu[5]) return { date: date, type: I18n.t('parametres.decrire_sauvegarde.copie_securite'), ton: 'attention' };
    if (lu[6]) return { date: date, type: I18n.t('parametres.decrire_sauvegarde.avant_format', { version: Number(lu[6]) }), ton: 'info' };
    if (lu[7]) return { date: date, type: I18n.t('parametres.decrire_sauvegarde.avant_import_zip'), ton: 'info' };
    if (lu[8]) return { date: date, type: I18n.t('parametres.decrire_sauvegarde.avant_import'), ton: 'info' };
    if (lu[9]) return { date: date, type: I18n.t('parametres.decrire_sauvegarde.avant_mise_jour_prevo'), ton: 'info' };
    return lu[2] ? { date: date, type: I18n.t('parametres.decrire_sauvegarde.manuelle'), ton: 'info' }
      : { date: date, type: I18n.t('parametres.decrire_sauvegarde.quotidienne'), ton: 'neutre' };
  }

  // { liste, indisponible } : la liste des sauvegardes, ou la raison pour laquelle elle n'existe pas.
  async function lireSauvegardes() {
    if (App.mode === 'demo') {
      return { liste: [], indisponible: I18n.t('parametres.lire_sauvegardes.indisponible_demo_rien_enregistre') };
    }
    try {
      return { liste: await App.adaptateur.listerSauvegardes(), indisponible: '' };
    } catch (erreur) {
      console.warn('Prévo : liste des sauvegardes illisible (' + (erreur && erreur.message) + ').', erreur);
      return { liste: [], indisponible: I18n.t('parametres.lire_sauvegardes.sauvegardes_peuvent_pas_etre', { motif: ((erreur && erreur.message) || I18n.t('commun.message.erreur_inconnue')) }) };
    }
  }

  function tableauSauvegardes(liste) {
    const lignes = liste.map((sauvegarde) => Object.assign({ decrite: decrireSauvegarde(sauvegarde.nom) }, sauvegarde));
    return UI.tableau({
      libelle: I18n.t('parametres.tableau_sauvegardes.sauvegardes_disponibles'),
      colonnes: [
        { cle: 'nom', libelle: I18n.t('parametres.tableau_sauvegardes.sauvegarde'), valeurTri: (l) => l.nom,
          rendu: (l) => UI.html`<span class="sauvegarde-nom" title="${l.nom}">${l.decrite.date}</span>` },
        { cle: 'type', libelle: I18n.t('parametres.tableau_sauvegardes.type'), valeurTri: (l) => l.decrite.type,
          rendu: (l) => UI.html`<span class="badge ${l.decrite.ton}">${l.decrite.type}</span>` },
        { cle: 'tables', libelle: I18n.t('parametres.tableau_sauvegardes.tables'), type: 'nombre', valeurTri: (l) => l.tables.length, rendu: (l) => String(l.tables.length) },
        { cle: 'action', libelle: '', triable: false, rendu: (l) => {
          const bouton = UI.element(UI.html`<button type="button" class="btn btn-secondaire" data-restaurer="${l.nom}">${I18n.t('parametres.tableau_sauvegardes.restaurer')}</button>`);
          bouton.addEventListener('click', () => pendant(bouton, 'restauration', () => restaurer(l)));
          return actionsSauvegarde(l, bouton);
        } },
      ],
      lignes: lignes,
      vide: I18n.t('parametres.tableau_sauvegardes.aucune_sauvegarde_moment'),
    });
  }

  async function sauvegarderMaintenant() {
    const nom = await App.adaptateur.sauvegarder();
    UI.toast(I18n.t('parametres.sauvegarder_maintenant.sauvegarde_creee', { nom }), 'succes');
    await reafficherAvecMessage('succes', UI.html`${I18n.html('parametres.sauvegarder_maintenant.sauvegarde_creee_contient_tous', { nom })}`);
  }

  // Fenêtre de choix (toutes les tables / une table) qui explique la copie de sécurité.
  // Renvoie null (annulé) ou { tables: undefined | [nomTable] }.
  async function demanderRestauration(sauvegarde) {
    const decrite = decrireSauvegarde(sauvegarde.nom);
    const typeEnMinuscule = decrite.type.charAt(0).toLowerCase() + decrite.type.slice(1);
    const options = sauvegarde.tables.map((nomTable) => {
      const description = Schema.table(nomTable);
      return UI.html`<option value="${nomTable}">${I18n.t('parametres.demander_restauration.option_table', { libelle: description ? description.libelle : nomTable, nomTable })}</option>`;
    });
    const contenu = UI.element(UI.html`<div class="form-colonne" id="fenetre-restauration">
      <p>${I18n.html('parametres.demander_restauration.sauvegarde_du', { n: sauvegarde.tables.length, date: decrite.date, typeEnMinuscule })}</p>
      <fieldset class="restauration-choix">
        <legend class="libelle">${I18n.t('parametres.demander_restauration.faut_restaurer')}</legend>
        <label class="case"><input type="radio" name="portee" value="toutes" checked><span>${I18n.t('parametres.demander_restauration.toutes_tables_retour_complet')}</span></label>
        <label class="case"><input type="radio" name="portee" value="une"><span>${I18n.t('parametres.demander_restauration.seule_table')}</span></label>
        <div class="champ"><select name="table" aria-label="${I18n.t('parametres.demander_restauration.table_restaurer')}" disabled>${options}</select></div>
      </fieldset>
      <div class="encadre attention">${I18n.html('parametres.demander_restauration.rien_perdu_avant_restaurer')}</div>
    </div>`);
    const choixTable = UI.$('select[name=table]', contenu);
    contenu.addEventListener('change', (evenement) => {
      if (evenement.target.name === 'portee') choixTable.disabled = evenement.target.value !== 'une';
    });
    const reponse = await UI.fenetre({
      titre: I18n.t('parametres.demander_restauration.restaurer_sauvegarde'),
      contenu: contenu,
      boutons: [
        { libelle: I18n.t('commun.bouton.annuler'), valeur: null, classe: 'btn-fantome' },
        { libelle: I18n.t('parametres.demander_restauration.restaurer'), valeur: 'restaurer', classe: 'btn-danger', defaut: true },
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
    UI.toast(I18n.t('parametres.restaurer.restauration_faite_copie_securite', { copieSecurite: resultat.copieSecurite }), 'succes');
    await reafficherAvecMessage('succes', UI.html`${I18n.html('parametres.restaurer.restauration_faite_etat_avant', { n: resultat.restaurees.length, join: resultat.restaurees.join(', '), copieSecurite: resultat.copieSecurite })}`);
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
      // Langues : liste de UI.champ (type ref) sous le nom de chaque langue dans sa langue, lu dans sa langue.
      const langues = reglage.langues ? I18n.langues : null;
      // Devise : « code — nom » dans la langue active, puis « autre » (champ devise_autre sous la liste).
      const actuelle = valeurAffichee(reglage);
      const devises = reglage.devises ? reglage.valeurs.map((code) => ({ valeur: code, libelle: code + ' — ' + UI.nomDevise(code) }))
        .concat([{ valeur: 'autre', libelle: I18n.t('parametres.devise.autre') }]) : null;
      const bloc = UI.champ({ nom: reglage.cle, type: langues || devises ? 'ref' : reglage.type, libelle: reglage.libelle, valeurs: reglage.valeurs },
        devises && !reglage.valeurs.includes(actuelle) ? 'autre' : actuelle, { aide: surServeur ? noteDecideSurLeServeur() + ' ' + reglage.aide : reglage.aide,
          lectureSeule: surServeur, liste: devises || (langues && langues.map((langue) => ({ valeur: langue.code, libelle: langue.nom }))) });
      if (langues) UI.$$('option', bloc).forEach((option) => { if (reglage.valeurs.includes(option.value)) option.lang = option.value; });
      if (devises) { const vide = UI.$('option[value=""]', bloc); if (vide) vide.remove(); }
      if (reglage.large) bloc.classList.add('large');
      formulaire.appendChild(bloc);
      if (devises) formulaire.appendChild(UI.champ({ nom: 'devise_autre', type: 'texte', libelle: I18n.t('parametres.libelle.devise_autre') },
        reglage.valeurs.includes(actuelle) ? '' : actuelle, { placeholder: 'SEK', attributs: { maxlength: '3', autocapitalize: 'characters' } }));
    });
    formulaire.appendChild(UI.element(UI.html`<div class="actions"><span class="espace"></span>
      <button type="submit" class="btn btn-primaire">${UI.icone('valider')}${I18n.t('commun.bouton.enregistrer')}</button></div>`));
    formulaire.addEventListener('submit', (evenement) => {
      evenement.preventDefault();
      enregistrerReglages(formulaire);
    });
    return formulaire;
  }

  /** Message d'erreur d'un réglage (nombre hors bornes, entier attendu, choix inconnu), sinon ''. */
  function erreurReglage(reglage, valeur) {
    if (reglage.devises) return UI.deviseConnue(valeur) ? '' : I18n.t('parametres.erreur_reglage.devise_inconnue');
    if (reglage.valeurs) return reglage.valeurs.includes(valeur) ? '' : I18n.t('parametres.erreur_reglage.choisissez_parmi', { join: reglage.valeurs.join(', ') });
    if (reglage.min === undefined) return '';
    const nombre = Donnees.nombre(valeur);
    const entier = reglage.type === 'entier';
    if (nombre !== null && nombre >= reglage.min && nombre <= reglage.max && (!entier || Number.isInteger(nombre))) return '';
    return entier ? I18n.t('parametres.erreur_reglage.saisissez_nombre_entier_entre', { min: reglage.min, max: reglage.max })
      : I18n.t('parametres.erreur_reglage.saisissez_nombre_entre_ex', { min: reglage.min, max: reglage.max });
  }

  // Contrôle des valeurs puis écriture dans parametres.csv (une ligne par clé, créée si elle manque).
  async function enregistrerReglages(formulaire) {
    const bouton = UI.$('button[type=submit]', formulaire);
    const syntaxe = UI.verifierFormulaire(formulaire);
    const valeurs = UI.lireFormulaire(formulaire);
    let erreurs = syntaxe.length;
    // Devise : « autre » prend le code saisi (majuscules) ; devise_autre n'est pas un réglage.
    const autreDevise = valeurs.devise === 'autre';
    if (autreDevise) valeurs.devise = String(valeurs.devise_autre || '').toUpperCase();
    reglagesEnregistres().forEach((reglage) => {
      if (syntaxe.some((e) => e.nom === reglage.cle)) return;
      const message = erreurReglage(reglage, valeurs[reglage.cle]);
      if (message) {
        UI.erreurChamp(formulaire, reglage.devises && autreDevise ? 'devise_autre' : reglage.cle, message);
        erreurs += 1;
      }
    });
    if (erreurs > 0) {
      const premier = UI.$('[aria-invalid="true"]', formulaire);
      if (premier) premier.focus();
      UI.toast(I18n.t('parametres.enregistrer_reglages.champs_corriger', { n: erreurs }), 'erreur');
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
      UI.toast(I18n.t('parametres.enregistrer_reglages.parametres_enregistres'), 'succes');
    });
  }

  function carteSauvegardes(sauvegardes) {
    return UI.html`<article class="carte" id="carte-sauvegardes">
      <div class="entete-carte"><h2>${I18n.t('parametres.carte_sauvegardes.sauvegardes')}</h2>
        ${sauvegardes.indisponible ? '' : UI.html`<button type="button" class="btn btn-primaire" id="btn-sauvegarder">${UI.icone('sauvegarde')}${I18n.t('parametres.carte_sauvegardes.sauvegarder_maintenant')}</button>`}
      </div>
      <p class="note sauvegardes-explication">${I18n.t('parametres.carte_sauvegardes.prevo_copie_tous_fichiers')}</p>
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
      ? UI.html`<span class="badge ok">${I18n.t('parametres.parametres.aucun_probleme')}</span>`
      : UI.html`${nombreErreurs ? UI.html`<span class="badge ko">${I18n.t('parametres.parametres.erreurs', { n: nombreErreurs })}</span> ` : ''}${nombreAttention ? UI.html`<span class="badge attention">${I18n.t('parametres.parametres.points_a_surveiller', { n: nombreAttention })}</span>` : ''}`;

    UI.remplir(conteneur, UI.html`
      <div class="entete-page"><div>
        <h1>${I18n.t('parametres.parametres.parametres')}</h1>
        <p>${I18n.t('parametres.parametres.reglages_entreprise_sauvegardes_controle')}</p>
      </div></div>
      ${zoneMessage()}
      <div class="grille parametres-grille">
        <div class="c7">
          <article class="carte">
            <div class="entete-carte"><h2>${I18n.t('parametres.parametres.reglages')}</h2></div>
            <div id="zone-formulaire"></div>
          </article>
          ${carteSauvegardes(sauvegardes)}
          ${carteAcces()}
        </div>
        <div class="c5">
          ${carteSolo()}
          <article class="carte">
            <div class="entete-carte"><h2>${I18n.t('parametres.parametres.poste')}</h2></div>
            <dl class="valeurs">
              <dt>${I18n.t('parametres.parametres.nom_poste')}</dt><dd id="poste-nom">${App.poste}</dd>
              <dt>${I18n.t('parametres.parametres.profil')}</dt><dd id="poste-profil">${App.libelleProfil()}</dd>
              <dt>${I18n.t('parametres.parametres.stockage')}</dt><dd>${App.adaptateur.libelle || App.mode}</dd>
            </dl>
            <p class="note">${I18n.t('parametres.parametres.nom_profil_assistant_ia')}</p>
            <div class="actions"><a class="btn btn-secondaire" id="lien-ce-poste" href="#/poste">${UI.icone('utilisateur')}${I18n.t('parametres.parametres.ouvrir_poste')}</a></div>
          </article>
          <article class="carte">
            <div class="entete-carte"><h2>${I18n.t('parametres.parametres.controle_base')}</h2>${resumeControle}</div>
            <p>${I18n.t('parametres.parametres.prevo_verifie_chaque_lecture')}</p>
            <div class="actions"><a class="btn btn-secondaire" id="lien-controle" href="#/controle">${UI.icone('controle')}${I18n.t('parametres.parametres.controle_base')}</a></div>
          </article>
          <article class="carte" id="carte-import">
            <div class="entete-carte"><h2>${I18n.t('parametres.parametres.importer_donnees')}</h2></div>
            <p>${I18n.t('parametres.parametres.reprenez_listes_existantes_equipements')}</p>
            <div class="actions"><a class="btn btn-secondaire" id="lien-import" href="#/import">${UI.icone('document')}${I18n.t('parametres.parametres.importer_donnees')}</a></div>
          </article>
          <article class="carte">
            <div class="entete-carte"><h2>${I18n.t('parametres.parametres.exporter_donnees')}</h2></div>
            <p>${I18n.t('parametres.parametres.fichier_zip_fichiers_csv', { n: Schema.nomsTables().length })}</p>
            <div class="actions"><button type="button" class="btn btn-secondaire" id="btn-export-zip">${UI.icone('export')}${I18n.t('parametres.parametres.exporter_zip')}</button>
              <button type="button" class="btn btn-secondaire" id="btn-export-donnees-seules">${UI.icone('export')}${I18n.t('parametres.parametres.exporter_donnees_seules_sans')}</button></div>
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
    mettreSurLeBouton(conteneur, '#btn-export-donnees-seules', (bouton) => pendant(bouton, 'export des données seules',
      () => App.exporterZip({ sansDocuments: true })));
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
        <div class="carte-tete"><b>${probleme.id || I18n.t('parametres.liste_problemes.sans_identifiant')}</b><span class="badge neutre">${libelleTypeProbleme(probleme.type)}</span></div>
        <div class="carte-titre">${probleme.message}</div>
        <div class="carte-meta"><span>${description ? description.fichier : probleme.table}</span>${numero === null ? '' : UI.html`<span>${I18n.t('parametres.liste_problemes.ligne_numero', { numero })}</span>`}${probleme.champ ? UI.html`<span>${I18n.t('parametres.liste_problemes.champ_champ', { champ: probleme.champ })}</span>` : ''}${probleme.valeur ? UI.html`<span>${I18n.html('parametres.liste_problemes.valeur_probleme_valeur', { problemeValeur: probleme.valeur })}</span>` : ''}</div>
        <div class="carte-meta">${liensVoir(probleme).map((lien) => UI.html`<a class="lien-fiche" href="${lien.href}">${lien.texte}</a>`)}</div>
      </div></li>`;
    });
    return UI.element(UI.html`<ul class="liste-cartes liste-problemes">${cartes}</ul>`);
  }

  function tableauProblemes(problemes) {
    if (UI.estTelephone()) return listeProblemes(problemes);
    const lignes = problemesAvecLigne(problemes);
    return UI.tableau({
      libelle: I18n.t('parametres.tableau_problemes.problemes_detectes'),
      colonnes: [
        { cle: 'type', libelle: I18n.t('parametres.tableau_sauvegardes.type'), valeurTri: (l) => l.probleme.type,
          rendu: (l) => UI.html`<span class="badge neutre">${libelleTypeProbleme(l.probleme.type)}</span>` },
        { cle: 'table', libelle: I18n.t('parametres.tableau_problemes.table'), valeurTri: (l) => l.probleme.table,
          rendu: (l) => { const d = Schema.table(l.probleme.table); return d ? d.fichier : l.probleme.table; } },
        { cle: 'ligne', libelle: I18n.t('parametres.tableau_problemes.ligne'), type: 'nombre', valeurTri: (l) => l.numero, rendu: (l) => (l.numero === null ? '—' : String(l.numero)) },
        { cle: 'id', libelle: I18n.t('parametres.tableau_problemes.identifiant'), valeurTri: (l) => l.probleme.id, rendu: (l) => l.probleme.id || '—', classe: 'sans-coupure' },
        { cle: 'champ', libelle: I18n.t('parametres.tableau_problemes.champ'), valeurTri: (l) => l.probleme.champ, rendu: (l) => l.probleme.champ || '—' },
        { cle: 'valeur', libelle: I18n.t('parametres.tableau_problemes.valeur'), valeurTri: (l) => l.probleme.valeur,
          rendu: (l) => (l.probleme.valeur ? UI.html`<code>${l.probleme.valeur}</code>` : '—') },
        { cle: 'message', libelle: I18n.t('parametres.tableau_problemes.message'), valeurTri: (l) => l.probleme.message, classe: 'message-probleme',
          rendu: (l) => l.probleme.message },
        { cle: 'voir', libelle: I18n.t('parametres.tableau_problemes.voir'), triable: false, classe: 'sans-coupure', rendu: (l) => {
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
    const accord = await UI.confirmer(I18n.t('parametres.attribuer_identifiants.prevo_va_donner_identifiant', { n: total, detail }),
    { titre: I18n.t('parametres.attribuer_identifiants.attribuer_identifiants_manquants'), oui: I18n.t('parametres.attribuer_identifiants.attribuer'), non: I18n.t('commun.bouton.annuler') });
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
    UI.toast(I18n.t('parametres.attribuer_identifiants.identifiants_attribues', { n: attribues }), 'succes');
    await reafficherAvecMessage('succes', UI.html`${I18n.html('parametres.attribuer_identifiants.succes_ouvrez_lignes', { n: attribues })}`);
  }

  async function relireFichiers() {
    await Donnees.chargerTout();
    annoncerRechargement();
    UI.toast(I18n.t('parametres.relire_fichiers.fichiers_relus'), 'succes');
    await reafficherAvecMessage('info', I18n.t('parametres.relire_fichiers.fichiers_ont_ete_relus'));
  }

  function carteGravite(gravite, problemes) {
    const parType = new Map();
    problemes.forEach((p) => parType.set(p.type, (parType.get(p.type) || 0) + 1));
    return UI.html`<article class="carte carte-gravite" data-gravite="${gravite.cle}">
      <div class="entete-carte"><h2>${gravite.titre}</h2><span class="badge ${gravite.ton}">${problemes.length}</span></div>
      <p class="note">${gravite.explication}</p>
      <p class="controle-types">${Array.from(parType.entries()).map(([type, n]) =>
        UI.html`<span class="badge neutre">${libelleTypeProbleme(type)} : ${n}</span>`)}</p>
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
        <div class="fil">${I18n.html('parametres.controle.parametres_controle_base')}</div>
        <h1>${I18n.t('parametres.parametres.controle_base')}</h1>
        <p>${I18n.t('parametres.controle.prevo_verifie_fichiers_chaque', { n: Schema.nomsTables().length })}</p>
      </div>
      <div class="actions">
        <button type="button" class="btn btn-secondaire" id="btn-relire">${UI.icone('actualiser')}${I18n.t('parametres.controle.relire_fichiers')}</button>
        ${totalAAttribuer ? UI.html`<button type="button" class="btn btn-primaire" id="btn-attribuer">${UI.icone('valider')}${I18n.t('parametres.controle.attribuer_identifiants_manquants', { totalAAttribuer })}</button>` : ''}
      </div></div>
      ${zoneMessage()}
      <div class="instruments controle-compteurs">
        ${groupes.map((g) => UI.html`<div class="${g.gravite.classe}" data-compteur="${g.gravite.cle}">
          <div class="lib">${g.gravite.titre}</div><div class="chiffre">${g.liste.length}</div></div>`)}
      </div>
      ${problemes.length === 0
        ? bandeauHtml('succes', UI.html`${I18n.html('parametres.controle.aucun_probleme_detecte_references')}`)
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
      id: 'parametres', route: /^#\/parametres$/, get titre() { return I18n.t('parametres.parametres.parametres'); },
      menu: { get libelle() { return I18n.t('parametres.parametres.parametres'); }, icone: 'parametres', ordre: 90, get groupe() { return I18n.t('parametres.groupe.administration'); } },
      profils: ['responsable'], tables: ['parametres', 'codes_defaillance'],
      afficher: afficherParametres,
    });
    App.ecran({
      id: 'controle', route: /^#\/controle$/, get titre() { return I18n.t('parametres.parametres.controle_base'); }, parent: 'parametres',
      profils: ['responsable'],
      // Le contrôle peut changer avec n'importe quelle table (sauf le journal).
      tables: Schema.nomsTables().filter((nomTable) => nomTable !== 'journal'),
      afficher: afficherControle,
    });
  });

  // interne : complété par parametres-codes.js (afficherCodes), usage interne au module (pas une API).
  // reglagesConnus : les réglages ci-dessus (formulaire et mode Solo), pour l'import ZIP (T319 : gardés s'ils manquent).
  return { decrireSauvegarde, numeroLigneFichier, reglagesConnus: () => REGLAGES.slice(), interne: {} };
})();
