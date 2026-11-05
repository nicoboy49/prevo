'use strict';
// Preventif (2/4) — écritures du préventif (ARCHITECTURE.md §14.3, brief §7 RG5) :
//   5. Génération des OT des gammes échues (genererOTEchus) et copie de leur check-list
//   6. Mise à jour d'une gamme après la clôture technique de son OT (apresCloture)
//   7. Gammes : vérification, création, modification
//   8. Check-list d'une gamme (gamme_operations) : ajout, modification, ordre, suppression (D26)
//
// Toujours par Donnees.modifier : chaque décision est prise DANS la fonction de mutation, sur les
// lignes fraîches (en cas de conflit avec un autre poste, la table est relue et la fonction rejouée).
// Un refus lève Donnees.ErreurValidation (message pour l'utilisateur). Aucune ligne n'est jamais
// supprimée, sauf une opération de check-list de gamme (décision D26), et cette suppression est
// inscrite au journal. Complète l'objet Preventif créé par preventif-regles.js.

Object.assign(Preventif, (() => {

  // Constantes et outils de preventif-regles.js.
  const { DECLENCHEURS } = Preventif;
  const { texte, nombre, estDateIso, ajouterJours, dateDuJour, contexteCalcul, evaluerGamme,
    echeanceEstimee, otsOuvertsParGamme } = Preventif.interne;

  const PRIORITES = ['P1', 'P2', 'P3', 'P4'];
  const PRIORITE_PAR_DEFAUT = 'P3';
  const STATUTS_CLOTURES = ['Clôturé techniquement', 'Clôturé administrativement'];
  const CHAMPS_GAMME = ['equipement_id', 'libelle', 'declencheur', 'periodicite_jours', 'compteur_id',
    'periodicite_unites', 'seuil', 'avance_jours', 'derniere_realisation', 'releve_derniere_realisation',
    'prochaine_echeance', 'temps_prevu_h', 'consignes', 'actif'];

  function ErreurValidation(message) {
    return new Donnees.ErreurValidation(message);
  }

  /** Rang d'une opération dans sa check-list : ordre (nombre), puis identifiant. */
  function comparerOperations(a, b) {
    const rangA = nombre(a.ordre);
    const rangB = nombre(b.ordre);
    if (rangA !== rangB) {
      if (rangA === null) return 1;
      if (rangB === null) return -1;
      return rangA - rangB;
    }
    return texte(a.id).localeCompare(texte(b.id), 'fr', { numeric: true });
  }

  /** Opérations d'une gamme, dans l'ordre de la check-list. lignes : par défaut le cache. */
  function operationsDeGamme(gammeId, lignes) {
    return (lignes || Donnees.lignes('gamme_operations')).filter((op) => op.gamme_id === gammeId)
      .sort(comparerOperations);
  }

  // ===========================================================================================
  // 5. Génération des OT des gammes échues (RG5)
  // ===========================================================================================

  /** Priorité des OT préventifs : paramètre priorite_preventif (P1 à P4), sinon P3. */
  function prioritePreventif() {
    const valeur = texte(Donnees.parametre('priorite_preventif', PRIORITE_PAR_DEFAUT)).toUpperCase();
    return PRIORITES.includes(valeur) ? valeur : PRIORITE_PAR_DEFAUT;
  }

  /**
   * Gammes actives échues ET sans OT ouvert, d'après les lignes d'OT données (dans la fonction de
   * mutation : les lignes fraîches, qui comptent les OT créés par un autre poste) : [{ gamme, etat }].
   */
  function gammesEchuesSansOt(lignesOt, jour) {
    const contexte = { releves: contexteCalcul().releves, otsOuverts: otsOuvertsParGamme(lignesOt) };
    return Donnees.lignes('gammes').filter((gamme) => texte(gamme.actif) !== '0')
      .map((gamme) => ({ gamme, etat: evaluerGamme(gamme, jour, contexte) }))
      .filter((candidat) => candidat.etat.statut === 'echue');
  }

  /** Ligne d'OT préventif d'une gamme échue (§14.3). Date prévue : l'échéance si elle est future, sinon le jour. */
  function nouvelOtPreventif(gamme, etat, jour, id, maintenant) {
    const nombreOperations = operationsDeGamme(gamme.id).length;
    return {
      id, origine: 'préventif', gamme_id: gamme.id, equipement_id: gamme.equipement_id,
      type: texte(gamme.declencheur) === 'seuil' ? 'préventif conditionnel' : 'préventif systématique',
      priorite: prioritePreventif(), statut: 'Créé',
      titre: texte(gamme.libelle) || I18n.t('preventif.nouvel_ot_preventif.gamme_gamme_id', { gammeId: gamme.id }),
      travail_a_faire: (nombreOperations ? I18n.t('preventif.nouvel_ot_preventif.realiser_operations_check_list', { n: nombreOperations }) + ' '
        : I18n.t('preventif.nouvel_ot_preventif.realiser_gamme') + ' ') + I18n.t('preventif.nouvel_ot_preventif.gamme_id_declenchement_raison', { gammeId: gamme.id, raison: etat.raison }),
      consignes: gamme.consignes, temps_prevu_h: gamme.temps_prevu_h,
      date_creation: maintenant, date_prevue: etat.echeance > jour ? etat.echeance : jour,
      arret_production: '0', remise_service: '0', anomalie_constatee: '0',
    };
  }

  /**
   * OT dont la check-list est à copier : ceux qui viennent d'être créés, et les OT préventifs encore
   * « Créé » d'une gamme restés sans aucune opération (copie interrompue lors d'une génération
   * précédente). Seulement si la gamme a des opérations. lignesOperations : ot_operations à lire.
   */
  function otsACompleter(idsCrees, lignesOperations) {
    const avecOperations = new Set(lignesOperations.map((op) => op.ot_id));
    const candidats = new Set(idsCrees);
    Donnees.lignes('ordres_travail').forEach((ot) => {
      if (ot.origine === 'préventif' && texte(ot.gamme_id) && ot.statut === 'Créé') candidats.add(ot.id);
    });
    return Array.from(candidats).filter((otId) => {
      const ot = Donnees.trouver('ordres_travail', otId);
      return ot && !avecOperations.has(otId) && operationsDeGamme(ot.gamme_id).length > 0;
    });
  }

  /** Copie la check-list de la gamme dans ot_operations (fait = 0) pour chaque OT qui n'en a pas encore. */
  async function copierOperations(idsCrees) {
    if (!otsACompleter(idsCrees, Donnees.lignes('ot_operations')).length) return 0;
    return Donnees.modifier('ot_operations', (lignes, outils) => {
      let copiees = 0;
      let dernier = '';      // identifiant suivant tiré du dernier créé : un seul parcours de la table (T86)
      otsACompleter(idsCrees, lignes).forEach((otId) => {
        operationsDeGamme(Donnees.trouver('ordres_travail', otId).gamme_id).forEach((operation) => {
          dernier = outils.nouvelId(dernier ? [{ id: dernier }] : lignes);
          lignes.push({ id: dernier, ot_id: otId, ordre: operation.ordre, operation: operation.operation,
            valeur_attendue: operation.valeur_attendue, fait: '0', valeur_mesuree: '' });
          copiees += 1;
        });
      });
      return copiees;
    }, { action: 'copie de la check-list de la gamme (RG5)' });
  }

  /**
   * RG5 : crée un OT pour chaque gamme active échue qui n'a pas d'OT ouvert, puis copie sa
   * check-list. Renvoie les identifiants des OT créés (tableau vide : rien à générer).
   * options : { aujourdhui: 'AAAA-MM-JJ' } (par défaut la date du jour).
   * Une seule écriture de ordres_travail, décidée sur les lignes fraîches : deux postes qui
   * génèrent en même temps ne créent qu'un OT par gamme (le second, en conflit, relit la table et
   * y trouve l'OT du premier). Rien d'échu dans le cache : aucune écriture (cas le plus courant).
   */
  async function genererOTEchus(options) {
    const jour = dateDuJour(options && options.aujourdhui);
    let crees = [];
    if (gammesEchuesSansOt(Donnees.lignes('ordres_travail'), jour).length) {
      crees = await Donnees.modifier('ordres_travail', (lignes, outils) => {
        const identifiants = [];
        gammesEchuesSansOt(lignes, jour).forEach(({ gamme, etat }) => {
          // Un seul parcours des OT existants : les suivants partent du dernier créé (même année).
          const dernier = identifiants[identifiants.length - 1];
          const id = outils.nouvelId(dernier ? [{ id: dernier }] : lignes, outils.aujourdhui());
          lignes.push(nouvelOtPreventif(gamme, etat, jour, id, outils.maintenant()));
          identifiants.push(id);
        });
        return identifiants;
      }, { action: 'génération du préventif (RG5)' });
    }
    await copierOperations(crees);
    return crees;
  }

  /** Message du résultat d'une génération : « Aucune gamme échue », « 1 OT préventif généré », « 3 OT préventifs générés ». */
  function texteGeneration(nombreCrees) {
    if (!nombreCrees) return I18n.t('preventif.texte_generation.aucune_gamme_echue');
    return nombreCrees === 1 ? I18n.t('preventif.texte_generation.1_ot_preventif_genere') : I18n.t('preventif.texte_generation.ot_preventifs_generes', { nombreCrees });
  }

  // ===========================================================================================
  // 6. Après la clôture technique d'un OT de gamme (RG5)
  // ===========================================================================================

  function estPlusRecent(a, b) {
    return a.date !== b.date ? a.date > b.date : a.id > b.id;
  }

  /**
   * Relevé d'un compteur au jour d'une réalisation : le dernier daté au plus tard de ce jour, sinon
   * le dernier relevé tout court ; { valeur, date, id } ou null. Un relevé saisi après la réalisation
   * ne change donc pas la base (apresCloture reste idempotent).
   */
  function releveALaDate(compteurId, date) {
    let dernier = null;
    let avantLaDate = null;
    Donnees.lignes('releves').forEach((releve) => {
      const valeur = nombre(releve.valeur);
      if (releve.compteur_id !== compteurId || valeur === null) return;
      const candidat = { valeur, date: texte(releve.date).slice(0, 10), id: texte(releve.id) };
      if (!dernier || estPlusRecent(candidat, dernier)) dernier = candidat;
      if (candidat.date <= date && (!avantLaDate || estPlusRecent(candidat, avantLaDate))) avantLaDate = candidat;
    });
    return avantLaDate || dernier;
  }

  /**
   * Champs d'une gamme réalisée le `date` : derniere_realisation ; date : prochaine_echeance =
   * date + periodicite_jours ; compteur et seuil : releve_derniere_realisation = relevé du compteur
   * à cette date ; compteur : prochaine_echeance estimée (compteur en heures) ou vide ; seuil : vide.
   */
  function valeursApresRealisation(gamme, date) {
    const valeurs = { derniere_realisation: date };
    const declencheur = texte(gamme.declencheur) || 'date';
    if (declencheur === 'date') {
      const periodicite = nombre(gamme.periodicite_jours);
      valeurs.prochaine_echeance = periodicite > 0 ? ajouterJours(date, Math.round(periodicite)) : '';
      return valeurs;
    }
    const compteur = Donnees.trouver('compteurs', texte(gamme.compteur_id));
    const releve = compteur ? releveALaDate(compteur.id, date) : null;
    if (releve) valeurs.releve_derniere_realisation = String(releve.valeur);
    const periodicite = nombre(gamme.periodicite_unites);
    valeurs.prochaine_echeance = declencheur === 'compteur' && releve && periodicite > 0
      ? echeanceEstimee(gamme, compteur, releve, periodicite) : '';
    return valeurs;
  }

  /** Date de réalisation d'un OT clôturé (« AAAA-MM-JJ HH:MM ») : sa date de fin, sinon celle de sa clôture. */
  function dateRealisation(ot) {
    return (texte(ot.date_fin) || texte(ot.date_cloture_tech) || texte(ot.date_cloture_admin)).slice(0, 16);
  }

  /**
   * À appeler après la clôture technique d'un OT qui a un gamme_id : la gamme prend la date de fin
   * de l'OT comme dernière réalisation, et son échéance est recalculée depuis cette date (RG5, D22).
   * La décision se prend sur les OT relus (ordres_travail frais) : si l'OT est celui dont la date
   * de fin est la plus récente parmi les OT clôturés (techniquement ou administrativement) de la
   * gamme, sa date fait foi, même si la gamme porte une date plus récente (date de fin erronée,
   * corrigée après réouverture puis nouvelle clôture). Sinon (OT plus ancien clôturé après coup),
   * la gamme ne change pas. Idempotent : un second appel ne change rien. Renvoie vrai si la gamme
   * a changé.
   */
  async function apresCloture(otId) {
    const ordres = await Donnees.rechargerTable('ordres_travail');
    const ot = ordres.find((ligne) => ligne.id === otId);
    if (!ot) throw ErreurValidation(I18n.t('commun.message.ot_introuvable', { otId }));
    const gammeId = texte(ot.gamme_id);
    if (!gammeId) return false;
    if (!STATUTS_CLOTURES.includes(ot.statut)) {
      throw ErreurValidation(I18n.t('preventif.apres_cloture.ot_pas_cloture_gamme', { otId, gammeId }));
    }
    const fin = dateRealisation(ot) || Donnees.aujourdhui();
    // Un autre OT clôturé de la gamme, réalisé plus tard : c'est sa date qui fait foi.
    const plusRecent = ordres.some((autre) => autre.id !== otId && texte(autre.gamme_id) === gammeId
      && STATUTS_CLOTURES.includes(autre.statut) && dateRealisation(autre) > fin);
    if (plusRecent) return false;
    const date = fin.slice(0, 10);
    return Donnees.modifier('gammes', (lignes) => {
      const gamme = lignes.find((ligne) => ligne.id === gammeId);
      if (!gamme) throw ErreurValidation(I18n.t('preventif.apres_cloture.gamme_ot_introuvable', { gammeId, otId }));
      const valeurs = valeursApresRealisation(gamme, date);
      const changes = Object.keys(valeurs).filter((nom) => texte(gamme[nom]) !== texte(valeurs[nom]));
      changes.forEach((nom) => { gamme[nom] = valeurs[nom]; });
      return changes.length > 0;
    }, { action: 'réalisation de la gamme par l\'OT ' + otId + ' (RG5)' });
  }

  // ===========================================================================================
  // 7. Gammes : vérification, création, modification
  // ===========================================================================================

  /** Valeurs d'une gamme ramenées aux champs du fichier (chaînes, sans espaces de bord). */
  function valeursGamme(valeurs) {
    const propres = {};
    CHAMPS_GAMME.forEach((nom) => { propres[nom] = texte(valeurs[nom]); });
    propres.declencheur = propres.declencheur || 'date';
    propres.actif = propres.actif === '0' ? '0' : '1';
    return propres;
  }

  function estEntierPositif(valeur, minimum) {
    return /^\d+$/.test(valeur) && Number(valeur) >= minimum;
  }

  /** Règles propres au déclencheur (périodicité, compteur, seuil) : [{ nom, message }]. */
  function erreursDuDeclencheur(gamme) {
    const erreurs = [];
    if (gamme.declencheur === 'date' && !estEntierPositif(gamme.periodicite_jours, 1)) {
      erreurs.push({ nom: 'periodicite_jours', message: I18n.t('preventif.erreurs_du_declencheur.indiquez_periodicite_jours_nombre') });
    }
    if (gamme.declencheur === 'compteur' || gamme.declencheur === 'seuil') {
      if (!gamme.compteur_id) erreurs.push({ nom: 'compteur_id', message: I18n.t('preventif.erreurs_du_declencheur.choisissez_compteur_point_mesure') });
      else if (!Donnees.trouver('compteurs', gamme.compteur_id)) erreurs.push({ nom: 'compteur_id', message: I18n.t('preventif.erreurs_du_declencheur.compteur_existe_pas') });
    }
    if (gamme.declencheur === 'compteur' && !(nombre(gamme.periodicite_unites) > 0)) {
      erreurs.push({ nom: 'periodicite_unites', message: I18n.t('preventif.erreurs_du_declencheur.indiquez_periodicite_unites_compteur') });
    }
    if (gamme.declencheur === 'seuil' && nombre(gamme.seuil) === null) {
      erreurs.push({ nom: 'seuil', message: I18n.t('preventif.erreurs_du_declencheur.indiquez_seuil_declenche_gamme') });
    }
    return erreurs;
  }

  /** Vérifie une gamme (règle pure) : [{ nom, message }], vide si tout va bien. */
  function verifierGamme(valeurs) {
    const gamme = valeursGamme(valeurs);
    const erreurs = [];
    if (!gamme.equipement_id) erreurs.push({ nom: 'equipement_id', message: I18n.t('preventif.verifier_gamme.choisissez_equipement') });
    else if (!Donnees.trouver('equipements', gamme.equipement_id)) erreurs.push({ nom: 'equipement_id', message: I18n.t('preventif.verifier_gamme.equipement_existe_pas') });
    if (!gamme.libelle) erreurs.push({ nom: 'libelle', message: I18n.t('preventif.verifier_gamme.donnez_libelle_gamme') });
    if (!Object.keys(DECLENCHEURS).includes(gamme.declencheur)) {
      erreurs.push({ nom: 'declencheur', message: I18n.t('preventif.verifier_gamme.declencheur_inconnu_choisissez_date') });
    } else {
      erreurs.push(...erreursDuDeclencheur(gamme));
    }
    if (gamme.avance_jours && !estEntierPositif(gamme.avance_jours, 0)) {
      erreurs.push({ nom: 'avance_jours', message: I18n.t('preventif.verifier_gamme.avance_nombre_entier_jours') });
    }
    ['periodicite_unites', 'seuil', 'releve_derniere_realisation', 'temps_prevu_h'].forEach((nom) => {
      if (gamme[nom] && nombre(gamme[nom]) === null && !erreurs.some((e) => e.nom === nom)) {
        erreurs.push({ nom, message: I18n.t('preventif.verifier_gamme.saisissez_nombre_ex_12') });
      }
    });
    if (gamme.temps_prevu_h && nombre(gamme.temps_prevu_h) < 0) erreurs.push({ nom: 'temps_prevu_h', message: I18n.t('preventif.verifier_gamme.temps_prevu_peut_pas') });
    ['derniere_realisation', 'prochaine_echeance'].forEach((nom) => {
      if (gamme[nom] && !estDateIso(gamme[nom])) erreurs.push({ nom, message: I18n.t('preventif.verifier_gamme.date_illisible_format_attendu') });
    });
    return erreurs;
  }

  function refuserSiInvalide(erreurs) {
    if (erreurs.length) throw ErreurValidation(erreurs.map((erreur) => erreur.message).join(' '));
  }

  /** Crée une gamme (active par défaut) et renvoie son identifiant (GAM-NNNN). */
  async function creerGamme(valeurs) {
    const gamme = valeursGamme(valeurs);
    return Donnees.modifier('gammes', (lignes, outils) => {
      refuserSiInvalide(verifierGamme(gamme));
      const id = outils.nouvelId(lignes);
      lignes.push(Object.assign({}, gamme, { id }));
      return id;
    }, { action: 'création de la gamme' });
  }

  /** Modifie une gamme (lue fraîche) ; renvoie la liste des champs réellement changés. */
  async function modifierGamme(gammeId, valeurs) {
    return Donnees.modifier('gammes', (lignes) => {
      const ligne = lignes.find((l) => l.id === gammeId);
      if (!ligne) throw ErreurValidation(I18n.t('preventif.modifier_gamme.gamme_existe_plus', { gammeId }));
      const gamme = valeursGamme(Object.assign({}, ligne, valeurs));
      refuserSiInvalide(verifierGamme(gamme));
      const changes = CHAMPS_GAMME.filter((nom) => texte(ligne[nom]) !== gamme[nom]);
      changes.forEach((nom) => { ligne[nom] = gamme[nom]; });
      return changes;
    }, { action: 'modification de la gamme' });
  }

  // ===========================================================================================
  // 8. Check-list d'une gamme (gamme_operations)
  // ===========================================================================================

  function operationSaisie(valeurs) {
    const operation = texte(valeurs && valeurs.operation);
    if (!operation) throw ErreurValidation(I18n.t('preventif.operation_saisie.decrivez_operation_realiser'));
    return { operation, valeur_attendue: texte(valeurs.valeur_attendue) };
  }

  function ligneOperation(lignes, operationId) {
    const ligne = lignes.find((l) => l.id === operationId);
    if (!ligne) throw ErreurValidation(I18n.t('preventif.ligne_operation.operation_existe_plus_supprimee'));
    return ligne;
  }

  /** Ajoute une opération en fin de check-list ; renvoie son identifiant (GOP-NNNNNN). */
  async function ajouterOperation(gammeId, valeurs) {
    const saisie = operationSaisie(valeurs);
    return Donnees.modifier('gamme_operations', (lignes, outils) => {
      if (!Donnees.trouver('gammes', gammeId)) throw ErreurValidation(I18n.t('preventif.ajouter_operation.gamme_introuvable', { gammeId }));
      const dernierRang = operationsDeGamme(gammeId, lignes).reduce((plusGrand, op) => Math.max(plusGrand, nombre(op.ordre) || 0), 0);
      const id = outils.nouvelId(lignes);
      lignes.push(Object.assign({ id, gamme_id: gammeId, ordre: String(dernierRang + 1) }, saisie));
      return id;
    }, { action: 'check-list de la gamme ' + gammeId + ' : ajout' });
  }

  /** Modifie le texte et la valeur attendue d'une opération ; renvoie vrai si quelque chose a changé. */
  async function modifierOperation(operationId, valeurs) {
    const saisie = operationSaisie(valeurs);
    return Donnees.modifier('gamme_operations', (lignes) => {
      const ligne = ligneOperation(lignes, operationId);
      const change = texte(ligne.operation) !== saisie.operation || texte(ligne.valeur_attendue) !== saisie.valeur_attendue;
      Object.assign(ligne, saisie);
      return change;
    }, { action: 'check-list : modification de l\'opération' });
  }

  /** Renumérote 1, 2, 3… les opérations d'une gamme dans l'ordre donné. */
  function renumeroter(operations) {
    operations.forEach((operation, rang) => { operation.ordre = String(rang + 1); });
  }

  /**
   * Monte (sens = -1) ou descend (sens = +1) une opération dans sa check-list, puis renumérote.
   * Renvoie faux si elle est déjà en tête (ou en fin).
   */
  async function deplacerOperation(operationId, sens) {
    return Donnees.modifier('gamme_operations', (lignes) => {
      const ligne = ligneOperation(lignes, operationId);
      const liste = operationsDeGamme(ligne.gamme_id, lignes);
      const position = liste.indexOf(ligne);
      const cible = position + (sens < 0 ? -1 : 1);
      if (cible < 0 || cible >= liste.length) return false;
      liste.splice(position, 1);
      liste.splice(cible, 0, ligne);
      renumeroter(liste);
      return true;
    }, { action: 'check-list : ordre des opérations' });
  }

  /**
   * Supprime une opération de la check-list (décision D26 : la SEULE suppression de ligne permise
   * dans Prévo), renumérote les suivantes et inscrit la suppression au journal.
   * Les OT déjà créés gardent leur copie (ot_operations) : elle n'est pas touchée.
   */
  async function supprimerOperation(operationId) {
    const connue = Donnees.trouver('gamme_operations', operationId);
    if (!connue) throw ErreurValidation(I18n.t('preventif.ligne_operation.operation_existe_plus_supprimee'));
    const supprimee = await Donnees.modifier('gamme_operations', (lignes) => {
      const ligne = ligneOperation(lignes, operationId);
      lignes.splice(lignes.indexOf(ligne), 1);
      renumeroter(operationsDeGamme(ligne.gamme_id, lignes));
      return Object.assign({}, ligne);
    }, { action: 'check-list de la gamme ' + connue.gamme_id + ' : renumérotation après une suppression' });
    await Donnees.journaliser('gamme_operations', operationId, 'suppression (D26) de l\'opération « '
      + texte(supprimee.operation) + ' » de la check-list de la gamme ' + supprimee.gamme_id);
    return true;
  }

  // Outils prêtés aux fichiers suivants du module (usage interne).
  Object.assign(Preventif.interne, { operationsDeGamme, CHAMPS_GAMME });

  return {
    // écritures (ARCHITECTURE.md §14.3)
    genererOTEchus, texteGeneration, apresCloture,
    verifierGamme, creerGamme, modifierGamme,
    ajouterOperation, modifierOperation, deplacerOperation, supprimerOperation,
  };
})());
