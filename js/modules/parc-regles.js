'use strict';
// Parc : arborescence des localisations et des équipements, fiche équipement (consignation,
// historique, QR code, valeur de remplacement, relevés de compteur, gammes préventives),
// création et modification (brief §6 « equipements » et « localisations », §9 E7,
// ARCHITECTURE.md §8, §10 et §14.6).
//
// Écrans :
//   #/parc                       arborescence site › atelier › ligne, recherche, inactifs (tous les profils)
//   #/equipement/<id>            fiche complète (tous les profils)
//   #/equipement/nouveau         formulaire de création (responsable)
//   #/equipement/<id>/modifier   formulaire de modification (responsable)
//   #/parc/etiquettes            étiquettes QR par lot, planches A4 (responsable, lot 3)
//   Les localisations se créent et se modifient dans une fenêtre, depuis le parc (responsable).
//
// Fonctions offertes aux autres modules :
//   Parc.cheminLocalisation(id)   « Site des Trois Vallées › Atelier Utilités »
//   Parc.libelleEquipement(id)    « PO-02 — Pompe centrifuge eau de refroidissement »
//
// Règles de gestion : un équipement n'est jamais supprimé (champ `actif`), le repère est unique
// parmi les équipements actifs, un équipement ne peut pas être son propre ancêtre.
//
// Le module est découpé en cinq fichiers, chargés dans cet ordre par index.html (ARCHITECTURE.md
// §14.2, décision D28 : 700 lignes au plus par fichier) :
//   parc-regles.js         CE FICHIER, qui crée l'objet Parc :
//                            1. Petits outils (aussi offerts aux autres modules)   2. Contrôles de saisie (purs)
//   parc-arbre.js          3. Écran #/parc : arborescence
//   parc-formulaires.js    4. Localisation : fenêtre de création et de modification
//                          6. Écrans #/equipement/nouveau et #/equipement/<id>/modifier : formulaire
//                          8. Relevé de compteur : fenêtre de saisie et écriture
//   parc-etiquettes.js     9. Étiquettes QR par lot : sélection, planches A4 (lot 3, §15.6)
//   parc-fiche.js          5. Écran #/equipement/<id> : fiche   7. Enregistrement des écrans
// Les fichiers suivants complètent l'objet : Object.assign(Parc, (() => { … return { … }; })()).
// Une fonction dont un autre fichier du module a besoin est rangée dans Parc.interne (usage
// interne au module : ce n'est pas une API, ni les autres modules ni les tests ne s'en servent).

const Parc = (() => {

  const SEPARATEUR_CHEMIN = ' › ';

  // ===========================================================================================
  // 1. Petits outils (aussi offerts aux autres modules)
  // ===========================================================================================

  function estActif(ligne) {
    return ligne.actif !== '0';
  }

  /** Codes, repères, références, dates ISO : ordre fixe, le même dans toutes les langues (D154). */
  function comparerCodes(a, b) {
    return String(a || '').localeCompare(String(b || ''), 'fr', { numeric: true, sensitivity: 'base' });
  }

  /** Libellés affichés (localisations, gammes…) : ordre de la langue active (UI.comparerTextes, D154). */
  function comparerLibelles(a, b) {
    return UI.comparerTextes(a || '', b || '', { numeric: true, sensitivity: 'base' });
  }

  function parRepere(a, b) {
    return comparerCodes(a.repere, b.repere);
  }

  /** « Site › Atelier › Ligne » d'une localisation. Identifiant inconnu : l'identifiant lui-même. */
  function cheminLocalisation(id) {
    if (!id) return '';
    let courante = Donnees.trouver('localisations', id);
    if (!courante) return id;
    const libelles = [];
    const dejaVues = new Set();
    while (courante && !dejaVues.has(courante.id)) {      // dejaVues : protège d'une boucle dans les données
      dejaVues.add(courante.id);
      libelles.unshift(courante.libelle || courante.id);
      courante = courante.parent_id ? Donnees.trouver('localisations', courante.parent_id) : null;
    }
    return libelles.join(SEPARATEUR_CHEMIN);
  }

  /** « PO-02 — Pompe centrifuge eau de refroidissement ». Identifiant inconnu : l'identifiant lui-même. */
  function libelleEquipement(id) {
    if (!id) return '';
    const equipement = Donnees.trouver('equipements', id);
    if (!equipement) return id;
    const repere = equipement.repere || equipement.id;
    return equipement.designation ? repere + ' — ' + equipement.designation : repere;
  }

  /** Identifiants de tous les descendants d'une ligne (table à `parent_id`), elle-même exclue. */
  function identifiantsDescendants(nomTable, id) {
    const resultat = new Set();
    const lignes = Donnees.lignes(nomTable);
    const aTraiter = [id];
    while (aTraiter.length) {
      const courant = aTraiter.pop();
      lignes.forEach((ligne) => {
        if (ligne.parent_id === courant && ligne.id !== id && !resultat.has(ligne.id)) {
          resultat.add(ligne.id);
          aTraiter.push(ligne.id);
        }
      });
    }
    return resultat;
  }

  // Vrai si, en remontant les `parent_id` depuis `id`, on retombe sur `id` (boucle dans les données).
  function remonteSurSoi(id, lignesParId) {
    const dejaVus = new Set([id]);
    let courant = lignesParId.get(id);
    while (courant && courant.parent_id) {
      if (dejaVus.has(courant.parent_id)) return courant.parent_id === id;
      dejaVus.add(courant.parent_id);
      courant = lignesParId.get(courant.parent_id);
    }
    return false;
  }

  function abreger(texte, longueurMax) {
    const propre = String(texte || '').replace(/\s+/g, ' ').trim();
    return propre.length > longueurMax ? I18n.t('parc.abreger.v1', { texte: propre.slice(0, longueurMax - 1).trimEnd() }) : propre;
  }

  function badgeCriticite(criticite) {
    const tons = { A: 'ko', B: 'attention', C: 'neutre' };
    const libelles = { A: I18n.t('parc.badge_criticite.tres_critique'), B: I18n.t('parc.badge_criticite.critique'), C: I18n.t('parc.badge_criticite.peu_critique') };
    if (!tons[criticite]) return UI.html`<span class="badge neutre" title="${I18n.t('parc.badge_criticite.criticite_non_renseignee')}">${I18n.t('parc.badge_criticite.crit')}</span>`;
    return UI.html`<span class="badge ${tons[criticite]}" title="${I18n.t('parc.badge_criticite.criticite_criticite_v1', { criticite: Schema.libelleValeur('equipements', 'criticite', criticite), libelle: libelles[criticite] })}">${I18n.t('parc.badge_criticite.crit_criticite', { criticite: Schema.libelleValeur('equipements', 'criticite', criticite) })}</span>`;
  }

  // Badges d'une ligne de l'arbre : criticité, statut s'il n'est pas « en service », mention inactif.
  function badgesEquipement(equipement) {
    return UI.html`${badgeCriticite(equipement.criticite)}
      ${equipement.statut && equipement.statut !== 'en service' ? UI.badgeValeur('equipements', 'statut', equipement.statut) : ''}
      ${estActif(equipement) ? '' : UI.html`<span class="badge neutre barre" title="${I18n.t('parc.badges_equipement.equipement_desactive')}">${I18n.t('parc.badges_equipement.inactif')}</span>`}`;
  }

  // Liste « tableau sur ordinateur, cartes sur téléphone » : le tableau déborderait de l'écran.
  // `carte(ligne)` rend le lien (<a>) d'une carte ; `lien(ligne)` donne la route d'une ligne cliquable.
  function listeAdaptative({ colonnes, lignes, vide, libelle, lien, carte }) {
    if (UI.estTelephone()) {
      if (!lignes.length) return UI.element(UI.html`<p class="muted">${vide}</p>`);
      return UI.element(UI.html`<ul class="liste-cartes">${lignes.map((ligne) => UI.html`<li>${carte(ligne)}</li>`)}</ul>`);
    }
    return UI.tableau({
      colonnes, lignes, vide, libelle,
      surClic: lien ? (ligne) => App.naviguer(lien(ligne)) : undefined,
    });
  }

  // ===========================================================================================
  // 2. Contrôles de saisie (purs : testés sans écran)
  // ===========================================================================================

  // Forme normalisée de Donnees (« 1250.50 ») d'un montant positif ou nul, deux décimales au plus.
  const MONTANT_AU_CENTIME = /^\d+(?:\.\d{0,2})?$/;

  /**
   * Contrôle les valeurs d'un équipement. Renvoie [{ nom, message }] (vide si tout va bien).
   *   valeurs : champs du formulaire ; lignesEquipements / lignesLocalisations : données à jour ;
   *   idCourant : identifiant de l'équipement modifié ('' pour une création).
   */
  function verifierEquipement(valeurs, lignesEquipements, lignesLocalisations, idCourant) {
    const erreurs = [];
    const courant = lignesEquipements.find((e) => e.id === idCourant);
    const seraActif = !courant || estActif(courant);
    const repere = String(valeurs.repere || '').trim();

    if (!repere) {
      erreurs.push({ nom: 'repere', message: I18n.t('parc.verifier_equipement.repere_obligatoire_ex_po') });
    } else if (seraActif) {
      const motif = UI.normaliserRecherche(repere);
      const double = lignesEquipements.find((e) => e.id !== idCourant && estActif(e) && UI.normaliserRecherche(e.repere) === motif);
      if (double) {
        erreurs.push({ nom: 'repere', message: I18n.t('parc.verifier_equipement.repere_deja_utilise_equipement', { repere, libelleEquipement: libelleEquipement(double.id) }) });
      }
    }

    if (!String(valeurs.designation || '').trim()) {
      erreurs.push({ nom: 'designation', message: I18n.t('parc.verifier_equipement.designation_obligatoire_ex_pompe') });
    }

    if (valeurs.localisation_id && !lignesLocalisations.some((l) => l.id === valeurs.localisation_id)) {
      erreurs.push({ nom: 'localisation_id', message: I18n.t('parc.verifier_equipement.localisation_existe_pas') });
    }

    if (valeurs.parent_id) {
      const parents = new Map(lignesEquipements.map((e) => [e.id, e]));
      if (idCourant && valeurs.parent_id === idCourant) {
        erreurs.push({ nom: 'parent_id', message: I18n.t('parc.verifier_equipement.equipement_peut_pas_etre') });
      } else if (!parents.has(valeurs.parent_id)) {
        erreurs.push({ nom: 'parent_id', message: I18n.t('parc.verifier_equipement.equipement_parent_existe_pas') });
      } else if (idCourant && remonteParentJusqua(valeurs.parent_id, idCourant, parents)) {
        erreurs.push({ nom: 'parent_id', message: I18n.t('parc.verifier_equipement.boucle_interdite_deja_sous', { libelleEquipement: libelleEquipement(valeurs.parent_id) }) });
      }
    }

    const criticites = ['A', 'B', 'C'];
    if (valeurs.criticite && !criticites.includes(valeurs.criticite)) {
      erreurs.push({ nom: 'criticite', message: I18n.t('parc.verifier_equipement.criticite_doit_etre_b') });
    }
    if (valeurs.statut && !['en service', 'arrêt', 'rebut'].includes(valeurs.statut)) {
      erreurs.push({ nom: 'statut', message: I18n.t('parc.verifier_equipement.statut_doit_etre_service') });
    }
    if (valeurs.heures_fonct_jour) {
      const heures = UI.enNombre(valeurs.heures_fonct_jour);
      if (heures === null || heures < 0 || heures > 24) {
        erreurs.push({ nom: 'heures_fonct_jour', message: I18n.t('parc.verifier_equipement.saisissez_nombre_heures_entre') });
      }
    }
    if (valeurs.valeur_remplacement) {
      const montant = UI.enNombre(valeurs.valeur_remplacement);
      if (montant === null || montant < 0) {
        erreurs.push({ nom: 'valeur_remplacement', message: I18n.t('parc.verifier_equipement.saisissez_montant_euros_positif') });
      }
    }
    // Coût d'une heure d'arrêt (D188, CS174) : vide permis (« non chiffré ») ; sinon positif ou nul, au centime.
    const coutArret = String(valeurs.cout_arret_h || '').trim();
    if (coutArret) {
      const lu = Donnees.normaliser.decimal(coutArret);
      if (!lu.ok || !MONTANT_AU_CENTIME.test(lu.valeur)) {
        erreurs.push({ nom: 'cout_arret_h', message: I18n.t('parc.verifier_equipement.saisissez_montant_positif_nul') });
      }
    }
    return erreurs;
  }

  /**
   * Coût d'une heure d'arrêt d'une fiche (equipements.cout_arret_h, D188) : nombre positif ou nul, ou null si la
   * valeur est vide, illisible ou négative (« non chiffré », jamais estimé : même règle qu'Indicateurs.coutArret).
   */
  function coutArretHoraire(valeur) {
    const montant = Donnees.nombre(valeur);
    return montant === null || montant < 0 ? null : montant || 0;
  }

  // Vrai si `ancetre` figure parmi les parents (de parent en parent) de `depart`, lui compris.
  function remonteParentJusqua(depart, ancetre, lignesParId) {
    const dejaVus = new Set();
    let courant = lignesParId.get(depart);
    while (courant && !dejaVus.has(courant.id)) {
      if (courant.id === ancetre) return true;
      dejaVus.add(courant.id);
      courant = courant.parent_id ? lignesParId.get(courant.parent_id) : null;
    }
    return false;
  }

  /** Contrôle les valeurs d'une localisation. Renvoie [{ nom, message }]. */
  function verifierLocalisation(valeurs, lignesLocalisations, idCourant) {
    const erreurs = [];
    const libelle = String(valeurs.libelle || '').trim();
    if (!libelle) {
      erreurs.push({ nom: 'libelle', message: I18n.t('parc.verifier_localisation.libelle_obligatoire_ex_atelier') });
    }
    if (!['site', 'atelier', 'ligne'].includes(valeurs.type)) {
      erreurs.push({ nom: 'type', message: I18n.t('parc.verifier_localisation.choisissez_type_site_atelier') });
    }
    if (valeurs.parent_id) {
      const parents = new Map(lignesLocalisations.map((l) => [l.id, l]));
      if (idCourant && valeurs.parent_id === idCourant) {
        erreurs.push({ nom: 'parent_id', message: I18n.t('parc.verifier_localisation.localisation_peut_pas_etre') });
      } else if (!parents.has(valeurs.parent_id)) {
        erreurs.push({ nom: 'parent_id', message: I18n.t('parc.verifier_localisation.localisation_parente_existe_pas') });
      } else if (idCourant && remonteParentJusqua(valeurs.parent_id, idCourant, parents)) {
        erreurs.push({ nom: 'parent_id', message: I18n.t('parc.verifier_localisation.boucle_interdite_localisation_parente') });
      }
    }
    if (libelle) {
      const motif = UI.normaliserRecherche(libelle);
      const jumelle = lignesLocalisations.find((l) => l.id !== idCourant && (l.parent_id || '') === (valeurs.parent_id || '')
        && UI.normaliserRecherche(l.libelle) === motif);
      if (jumelle) {
        erreurs.push({ nom: 'libelle', message: I18n.t('parc.verifier_localisation.existe_deja_localisation_endroit', { jumelleLibelle: jumelle.libelle }) });
      }
    }
    return erreurs;
  }

  // --- Relevés de compteur (lot 2, ARCHITECTURE.md §14.6) -------------------------------------

  /**
   * Dernier relevé d'un compteur parmi `lignesReleves` (le cache, ou les lignes fraîches d'une
   * fonction de mutation) : la ligne du relevé, ou null. Même ordre que Preventif.dernierReleve :
   * la date, puis l'identifiant ; un relevé dont la valeur est illisible est ignoré.
   */
  function dernierReleveDe(lignesReleves, compteurId) {
    let dernier = null;
    lignesReleves.forEach((releve) => {
      if (releve.compteur_id !== compteurId || Donnees.nombre(releve.valeur) === null) return;
      const date = String(releve.date || '').slice(0, 10);
      const dateDernier = dernier ? String(dernier.date || '').slice(0, 10) : '';
      if (!dernier || date > dateDernier || (date === dateDernier && String(releve.id) > String(dernier.id))) {
        dernier = releve;
      }
    });
    return dernier;
  }

  /**
   * Contrôle un relevé saisi : { date: 'AAAA-MM-JJ', valeur: '1234.5' }. Renvoie [{ nom, message }].
   * La date est obligatoire et ne peut pas être après `aujourdhui` ; la valeur est un nombre.
   */
  function verifierReleve(valeurs, aujourdhui) {
    const erreurs = [];
    const date = String(valeurs.date || '').trim();
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
      erreurs.push({ nom: 'date', message: I18n.t('parc.verifier_releve.indiquez_date_releve') });
    } else if (date > aujourdhui) {
      erreurs.push({ nom: 'date', message: I18n.t('parc.verifier_releve.date_releve_peut_pas') });
    }
    if (String(valeurs.valeur || '').trim() === '') {
      erreurs.push({ nom: 'valeur', message: I18n.t('parc.verifier_releve.indiquez_valeur_lue_compteur') });
    } else if (Donnees.nombre(valeurs.valeur) === null) {
      erreurs.push({ nom: 'valeur', message: I18n.t('parc.verifier_releve.saisissez_nombre_ex_1') });
    }
    return erreurs;
  }

  /** Vrai si la valeur saisie est plus basse que le dernier relevé (ligne de releves, ou null). */
  function estEnBaisse(valeur, dernier) {
    const nouvelle = Donnees.nombre(valeur);
    const precedente = dernier ? Donnees.nombre(dernier.valeur) : null;
    return nouvelle !== null && precedente !== null && nouvelle < precedente;
  }

  return {
    cheminLocalisation,
    libelleEquipement,
    verifierEquipement,
    verifierLocalisation,
    // (les écrans afficherListe, afficherFormulaire, afficherFiche : fichiers parc-*.js suivants)
    // Usage interne au module : outils prêtés aux fichiers parc-*.js, qui y ajoutent les leurs par
    // Object.assign(Parc.interne, …). Pas une API : son contenu peut changer à tout moment.
    interne: {
      estActif, comparerCodes, comparerLibelles, parRepere, identifiantsDescendants, remonteSurSoi, abreger,
      badgeCriticite, badgesEquipement, listeAdaptative, coutArretHoraire,
      dernierReleveDe, verifierReleve, estEnBaisse,
    },
  };
})();
