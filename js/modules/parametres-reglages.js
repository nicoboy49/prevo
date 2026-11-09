'use strict';
// ParametresReglages : réglages de l'écran Paramètres (une ligne de parametres.csv chacun, lue par
// Donnees.parametre(cle, defaut)), sortis de parametres.js (T454 : plafond D28 de 700 lignes). Chargé juste AVANT
// parametres.js, qui les affiche (formulaire « Réglages »), les passe à la carte Mode Solo (parametres-solo.js) et
// les donne à l'import ZIP (Parametres.reglagesConnus, T319 : un réglage absent du ZIP garde la valeur de la base).
// outils/generer_fiche_csv.py relit ce tableau (libellé, valeurs, défaut) : garder « { cle: '…' » en tête de ligne.
//
// Un réglage : clé dans parametres.csv, type de champ, libellé, valeur par défaut, bornes min/max pour un nombre,
// valeurs d'un choix, section (intertitre du formulaire), aide ; horsFormulaire : posé par une carte (mode Solo) ;
// decideeParLeServeur : montré tel que le PC serveur l'a décidé (mode serveur). Textes lus à l'affichage
// (accesseurs), jamais figés au chargement du module.

const ParametresReglages = (() => {

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
    // 2.2, lot L4 (T454, D187) : délai d'alerte des garanties et des contrats de prestataires, un seul pour les deux ;
    // lu par Garanties.delaiAlerte (garanties-regles.js : vide, illisible ou hors de 1 à 365 → 60).
    { cle: 'alerte_echeances_jours', type: 'entier', get libelle() { return I18n.t('parametres.libelle.alerte_avant_echeance_jours'); }, defaut: '60', min: 1, max: 365,
      get section() { return I18n.t('parametres.section.garanties_contrats'); }, get aide() { return I18n.t('parametres.aide.garanties_avant_date_fin'); } },
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

  return { REGLAGES: Object.freeze(REGLAGES) };
})();
