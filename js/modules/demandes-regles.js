'use strict';
// Demandes : module M2 « Demandes d'intervention » (DI) — tâche T13.
// Trois écrans (ARCHITECTURE.md §8, §10 RG1 et RG2 ; brief §9 E2 et E3) :
//   #/di/nouvelle   « Signaler un problème » : tous profils, pensé téléphone d'abord
//                   (une colonne, gros boutons utilisables avec des gants) ;
//   #/di            liste des demandes (filtres, tableau triable, cartes sur téléphone) ;
//   #/di/<id>       fiche d'une demande et, pour le responsable, les décisions
//                   (accepter, regrouper, différer, refuser).
//
// Fonctions exposées (utilisées par les tests et les autres modules) :
//   Demandes.prioriteCalculee(criticite, impact)   règle RG2, fonction pure
//   Demandes.creer(valeurs)                        → identifiant de la DI créée
//   Demandes.accepter(diId, { priorite, motifPriorite, type })  → identifiant de l'OT
//   Demandes.regrouper(diId, otId), Demandes.differer(diId, motif), Demandes.refuser(diId, motif)
//
// Le module est découpé en cinq fichiers, chargés dans cet ordre par index.html (ARCHITECTURE.md
// §14.2, décision D28 : 700 lignes au plus par fichier) :
//   demandes-regles.js      CE FICHIER, qui crée l'objet Demandes :
//                             1. Constantes et règles pures (matrice RG2)   2. Libellés partagés
//   demandes-ecritures.js   3. Écritures (Donnees.modifier)   4. Photo : nom du fichier
//   demandes-signaler.js    5. Écran « Signaler un problème » (#/di/nouvelle) et confirmation
//   demandes-liste.js       6. Liste des demandes (#/di)
//   demandes-fiche.js       7. Fiche (#/di/<id>) et décisions du responsable   8. Enregistrement des écrans
// Les fichiers suivants complètent l'objet : Object.assign(Demandes, (() => { … return { … }; })()).
// Une fonction ou une constante dont un autre fichier du module a besoin est rangée dans
// Demandes.interne (usage interne au module : ce n'est pas une API, ni les autres modules ni les
// tests ne s'en servent).
//
// Règles de ce module :
// - toute écriture passe par Donnees.modifier (identifiants calculés DANS la fonction) ;
// - une action sur deux tables (accepter) enchaîne deux modifier() idempotents (décision D18) ;
// - contexte non sécurisé (téléphone en http://192.168…) : pas de crypto, la photo passe par
//   <input type="file" accept="image/*" capture="environment"> ;
// - pas d'alert/confirm/prompt ; console.warn (via App.signalerErreur) pour une erreur gérée.

const Demandes = (() => {

  // ===========================================================================================
  // 1. Constantes et règles pures
  // ===========================================================================================

  const STATUTS = ['Nouvelle', 'Acceptée', 'Regroupée', 'Différée', 'Refusée'];
  const STATUTS_A_TRAITER = ['Nouvelle', 'Différée'];          // décision encore possible (RG1)
  const STATUTS_OT_FERMES = ['Clôturé techniquement', 'Clôturé administrativement', 'Annulé'];
  const PRIORITES = ['P1', 'P2', 'P3', 'P4'];
  const TYPE_IMMEDIAT = 'correctif immédiat';
  const TYPE_DIFFERE = 'correctif différé';
  const MESSAGE_DEJA_TRAITEE = 'Cette demande a déjà été traitée sur un autre poste';

  // Les 4 impacts, dans l'ordre d'affichage, avec l'explication montrée sur les gros boutons.
  const IMPACTS = [
    { valeur: 'sécurité', libelle: 'Sécurité', explication: 'Danger pour une personne' },
    { valeur: 'arrêt', libelle: 'Arrêt', explication: 'La machine ne tourne plus' },
    { valeur: 'dégradé', libelle: 'Dégradé', explication: 'Elle tourne, mais mal' },
    { valeur: 'gêne', libelle: 'Gêne', explication: 'Peut attendre' },
  ];

  // RG2 : priorité = criticité de l'équipement × impact (« sécurité » donne toujours P1).
  const MATRICE_PRIORITE = {
    A: { 'gêne': 'P2', 'dégradé': 'P1', 'arrêt': 'P1' },
    B: { 'gêne': 'P3', 'dégradé': 'P2', 'arrêt': 'P1' },
    C: { 'gêne': 'P4', 'dégradé': 'P3', 'arrêt': 'P2' },
  };

  // Texte comparable : minuscules, sans accents ni espaces de bord (« Sécurité » → « securite »).
  function sansAccents(texte) {
    return String(texte === null || texte === undefined ? '' : texte)
      .normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
  }

  /** Impact écrit de façon approximative (« Securite », « ARRET ») → valeur canonique, ou ''. */
  function normaliserImpact(impact) {
    const cherche = sansAccents(impact);
    const trouve = IMPACTS.find((entree) => sansAccents(entree.valeur) === cherche);
    return trouve ? trouve.valeur : '';
  }

  /**
   * Priorité calculée (RG2), fonction pure :
   *   prioriteCalculee('B', 'dégradé') → 'P2' ; prioriteCalculee('C', 'sécurité') → 'P1'.
   * Criticité absente ou inconnue → B. Impact absent ou inconnu → '' (pas de priorité).
   */
  function prioriteCalculee(criticite, impact) {
    const impactConnu = normaliserImpact(impact);
    if (!impactConnu) return '';
    if (impactConnu === 'sécurité') return 'P1';
    const lettre = String(criticite === null || criticite === undefined ? '' : criticite).trim().toUpperCase();
    const ligne = MATRICE_PRIORITE[lettre] || MATRICE_PRIORITE.B;
    return ligne[impactConnu];
  }

  /** Type d'OT proposé à l'acceptation : P1 → correctif immédiat, sinon correctif différé. */
  function typePropose(priorite) {
    return priorite === 'P1' ? TYPE_IMMEDIAT : TYPE_DIFFERE;
  }

  /** Priorité calculée d'une DI (criticité lue sur son équipement). */
  function prioriteDeLaDemande(demande) {
    const equipement = Donnees.trouver('equipements', demande.equipement_id);
    return prioriteCalculee(equipement ? equipement.criticite : '', demande.impact);
  }

  function estOuvert(ot) {
    return Boolean(ot) && !STATUTS_OT_FERMES.includes(ot.statut);
  }

  /** OT ouverts (ni clôturés ni annulés) d'un équipement, les plus récents d'abord. */
  function otOuvertsDeLEquipement(equipementId) {
    return Donnees.lignes('ordres_travail')
      .filter((ot) => ot.equipement_id === equipementId && estOuvert(ot))
      .sort((a, b) => String(b.id).localeCompare(String(a.id), 'fr', { numeric: true }));
  }

  // Date prévue d'un OT : aujourd'hui + délai de la priorité (parametres.csv : delai_pN_h).
  // P4 (« prochain arrêt ») : pas de date.
  function datePrevue(priorite, aujourdhuiIso) {
    if (priorite === 'P4' || !PRIORITES.includes(priorite)) return '';
    const parDefaut = { P1: 0, P2: 24, P3: 168 };
    const lu = Donnees.nombre(Donnees.parametre('delai_' + priorite.toLowerCase() + '_h', ''));
    const heures = lu === null || lu < 0 ? parDefaut[priorite] : lu;
    const morceaux = /^(\d{4})-(\d{2})-(\d{2})/.exec(aujourdhuiIso || Donnees.aujourdhui());
    const date = new Date(Number(morceaux[1]), Number(morceaux[2]) - 1, Number(morceaux[3]), 0, 0, 0);
    date.setHours(date.getHours() + heures);
    return date.getFullYear() + '-' + deuxChiffres(date.getMonth() + 1) + '-' + deuxChiffres(date.getDate());
  }

  function deuxChiffres(nombre) {
    return String(nombre).padStart(2, '0');
  }

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  // ===========================================================================================
  // 2. Libellés partagés
  // ===========================================================================================

  /** « PO-02 — Pompe centrifuge… » : Parc.libelleEquipement s'il existe, sinon calculé ici. */
  function libelleEquipement(equipementId) {
    if (typeof Parc !== 'undefined' && Parc && typeof Parc.libelleEquipement === 'function') {
      try {
        const libelle = Parc.libelleEquipement(equipementId);
        if (libelle) return String(libelle);
      } catch (erreur) {
        console.warn('Prévo (demandes) : Parc.libelleEquipement a échoué, libellé calculé ici.', erreur);
      }
    }
    const equipement = Donnees.trouver('equipements', equipementId);
    if (!equipement) return equipementId || '—';
    return (equipement.repere || equipement.id) + (equipement.designation ? ' — ' + equipement.designation : '');
  }

  /** Nom inscrit dans « demandeur » : nom du profil (le responsable n'a pas de nom : « Responsable »). */
  function nomDuProfil() {
    const profil = App.profil;
    if (profil && profil.nom) return profil.nom;
    return App.libelleProfil() || 'Responsable';
  }

  /** Badge d'impact (le texte est toujours affiché, la couleur aide seulement). */
  function badgeImpact(impact) {
    const tons = { 'sécurité': 'ko', 'arrêt': 'attention', 'dégradé': 'cyan', 'gêne': 'neutre' };
    return UI.html`<span class="badge ${tons[impact] || 'neutre'}">${impact || '—'}</span>`;
  }

  return {
    STATUTS, IMPACTS, MATRICE_PRIORITE,
    prioriteCalculee, normaliserImpact, typePropose, datePrevue, libelleEquipement,
    // (les écritures creer, accepter, regrouper, differer, refuser : demandes-ecritures.js)
    // Usage interne au module : outils prêtés aux fichiers demandes-*.js, qui y ajoutent les leurs
    // par Object.assign(Demandes.interne, …). Pas une API : son contenu peut changer à tout moment.
    interne: {
      STATUTS_A_TRAITER, PRIORITES, TYPE_IMMEDIAT, TYPE_DIFFERE, MESSAGE_DEJA_TRAITEE,
      sansAccents, texte, deuxChiffres, prioriteDeLaDemande, estOuvert, otOuvertsDeLEquipement,
      nomDuProfil, badgeImpact,
    },
  };
})();
