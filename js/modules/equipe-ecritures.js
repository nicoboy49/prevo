'use strict';
// Equipe (2/3) — écritures des techniciens et des habilitations (ARCHITECTURE.md §15.8 ; brief §6,
// RG8) : création et modification d'un technicien (désactivation par actif = 0, jamais de
// suppression), ajout, correction et renouvellement d'une habilitation.
//
// Règles communes à toutes les fonctions de ce fichier :
// - toute écriture passe par Donnees.modifier ; les contrôles sont refaits DANS la fonction de
//   mutation, sur les lignes fraîches qu'elle reçoit (rejouée si un autre poste a écrit entre-temps :
//   deux postes qui ajoutent chacun une habilitation gardent les deux) ;
// - un refus lève Donnees.ErreurValidation (message pour l'utilisateur) ;
// - un renouvellement AJOUTE une ligne de même intitulé : l'ancienne reste telle quelle (historique),
//   et c'est la nouvelle, à l'échéance la plus lointaine, qui compte (Equipe.habilitationsQuiComptent).
// Complète l'objet Equipe créé par equipe-regles.js.

Object.assign(Equipe, (() => {

  // Outils de equipe-regles.js.
  const { texte, dateIso, cleIntitule, estActif, nomComplet } = Equipe.interne;

  const CHAMPS_TECHNICIEN = ['nom', 'prenom', 'metier', 'taux_horaire', 'capacite_h_semaine', 'actif'];
  const CHAMPS_NOMBRES = ['taux_horaire', 'capacite_h_semaine'];
  const CHAMPS_HABILITATION = ['intitule', 'date_obtention', 'date_echeance'];
  const CAPACITE_MAX_H = 80;                           // heures par semaine (au-delà : faute de frappe)

  // ===========================================================================================
  // 3. Petits outils des écritures
  // ===========================================================================================

  function ErreurValidation(message) {
    return new Donnees.ErreurValidation(message);
  }

  function refuserSiErreurs(erreurs) {
    if (erreurs.length) throw ErreurValidation(erreurs.map((erreur) => erreur.message).join(' '));
  }

  /** Nombre saisi au format du fichier (point décimal) ; texte gardé tel quel s'il est illisible. */
  function nombreFichier(valeur) {
    const lu = Donnees.nombre(valeur);
    return lu === null ? texte(valeur) : String(Math.round(lu * 1e6) / 1e6);
  }

  function libelleDate(valeur) {
    return dateIso(valeur) ? UI.dateFr(valeur) : 'sans échéance';
  }

  // ===========================================================================================
  // 4. Techniciens : création, modification, désactivation
  // ===========================================================================================

  /**
   * Contrôle les valeurs d'un technicien : [{ nom, message }] (vide si tout va bien). Nom
   * obligatoire ; taux horaire ≥ 0 ; capacité de 0 à 80 h par semaine ; pas deux techniciens
   * ACTIFS de même nom et prénom (casse et accents ignorés). idCourant : '' pour une création.
   */
  function verifierTechnicien(valeurs, lignesTechniciens, idCourant) {
    const erreurs = [];
    if (!texte(valeurs.nom)) erreurs.push({ nom: 'nom', message: 'Le nom du technicien est obligatoire.' });
    const taux = texte(valeurs.taux_horaire);
    if (taux !== '' && (Donnees.nombre(taux) === null || Donnees.nombre(taux) < 0)) {
      erreurs.push({ nom: 'taux_horaire', message: 'Le taux horaire est un nombre d\'euros par heure, jamais négatif (ex. 42).' });
    }
    const capacite = texte(valeurs.capacite_h_semaine);
    const heures = Donnees.nombre(capacite);
    if (capacite !== '' && (heures === null || heures < 0 || heures > CAPACITE_MAX_H)) {
      erreurs.push({ nom: 'capacite_h_semaine', message: 'La capacité est comprise entre 0 et ' + CAPACITE_MAX_H + ' heures par semaine (ex. 35).' });
    }
    if (texte(valeurs.nom) && texte(valeurs.actif) !== '0') {
      const cle = UI.normaliserRecherche(texte(valeurs.nom) + ' ' + texte(valeurs.prenom));
      const double = (lignesTechniciens || []).find((ligne) => ligne.id !== idCourant && estActif(ligne)
        && UI.normaliserRecherche(texte(ligne.nom) + ' ' + texte(ligne.prenom)) === cle);
      if (double) erreurs.push({ nom: 'nom', message: 'Un technicien actif porte déjà ce nom (' + double.id + ').' });
    }
    return erreurs;
  }

  // Valeurs d'un technicien au format du fichier : seuls les champs modifiables.
  function valeursTechnicien(valeurs) {
    const propres = {};
    CHAMPS_TECHNICIEN.forEach((nom) => {
      if (valeurs[nom] === undefined || valeurs[nom] === null) return;
      let valeur = texte(valeurs[nom]);
      if (CHAMPS_NOMBRES.includes(nom) && valeur !== '') valeur = nombreFichier(valeur);
      if (nom === 'actif') valeur = valeur === '0' ? '0' : '1';
      propres[nom] = valeur;
    });
    return propres;
  }

  /** Crée un technicien (actif) ; renvoie son identifiant (TEC-…). */
  async function creerTechnicien(valeurs) {
    const propres = valeursTechnicien(valeurs || {});
    return Donnees.modifier('techniciens', (lignes, outils) => {
      const ligne = Object.assign({ prenom: '', metier: '', taux_horaire: '', capacite_h_semaine: '' }, propres, { actif: '1' });
      refuserSiErreurs(verifierTechnicien(ligne, lignes, ''));
      ligne.id = outils.nouvelId(lignes);
      lignes.push(ligne);
      return ligne.id;
    }, { action: 'création du technicien' });
  }

  /** Modifie un technicien (actif = '0' : désactivation) ; renvoie la liste des champs changés. */
  async function modifierTechnicien(technicienId, valeurs) {
    const propres = valeursTechnicien(valeurs || {});
    let action = 'modification du technicien';
    return Donnees.modifier('techniciens', (lignes) => {
      const ligne = lignes.find((l) => l.id === technicienId);
      if (!ligne) throw ErreurValidation('Le technicien ' + technicienId + ' est introuvable.');
      refuserSiErreurs(verifierTechnicien(Object.assign({}, ligne, propres), lignes, technicienId));
      const changes = Object.keys(propres).filter((nom) => texte(ligne[nom]) !== propres[nom]);
      changes.forEach((nom) => { ligne[nom] = propres[nom]; });
      if (changes.includes('actif')) action = propres.actif === '0' ? 'désactivation du technicien' : 'réactivation du technicien';
      return changes;
      // Donnees.modifier lit `action` APRÈS la mutation : le « get » rend le texte décidé sur les lignes fraîches.
    }, { get action() { return action; } });
  }

  // ===========================================================================================
  // 5. Habilitations : ajout, correction, renouvellement
  // ===========================================================================================

  /** Contrôle les valeurs d'une habilitation : intitulé, obtention obligatoires ; échéance ≥ obtention. */
  function verifierHabilitation(valeurs) {
    const erreurs = [];
    if (!texte(valeurs.intitule)) erreurs.push({ nom: 'intitule', message: 'L\'intitulé est obligatoire (ex. BR, H0V, CACES R489).' });
    const obtention = texte(valeurs.date_obtention);
    const echeance = texte(valeurs.date_echeance);
    if (!obtention) erreurs.push({ nom: 'date_obtention', message: 'La date d\'obtention est obligatoire.' });
    else if (!dateIso(obtention)) erreurs.push({ nom: 'date_obtention', message: 'Date d\'obtention illisible (format AAAA-MM-JJ).' });
    if (echeance && !dateIso(echeance)) erreurs.push({ nom: 'date_echeance', message: 'Date d\'échéance illisible (format AAAA-MM-JJ).' });
    else if (echeance && dateIso(obtention) && echeance < obtention) {
      erreurs.push({ nom: 'date_echeance', message: 'L\'échéance ne peut pas précéder la date d\'obtention (' + UI.dateFr(obtention) + ').' });
    }
    return erreurs;
  }

  function valeursHabilitation(valeurs) {
    const propres = {};
    CHAMPS_HABILITATION.forEach((nom) => {
      if (valeurs[nom] !== undefined && valeurs[nom] !== null) propres[nom] = texte(valeurs[nom]);
    });
    return propres;
  }

  function technicienExistant(technicienId) {
    const technicien = Donnees.trouver('techniciens', texte(technicienId));
    if (!technicien) throw ErreurValidation('Le technicien ' + (texte(technicienId) || '(non choisi)') + ' est introuvable.');
    return technicien;
  }

  /** Lignes du même technicien et du même intitulé (casse et espaces ignorés). */
  function memeHabilitation(lignes, technicienId, intitule) {
    return lignes.filter((ligne) => ligne.technicien_id === technicienId && cleIntitule(ligne.intitule) === cleIntitule(intitule));
  }

  /**
   * Ajoute une habilitation à un technicien ; renvoie son identifiant (HAB-…). Refus si le
   * technicien a déjà cet intitulé : c'est alors un renouvellement (ou une correction).
   */
  async function ajouterHabilitation(technicienId, valeurs) {
    const technicien = technicienExistant(technicienId);
    const propres = valeursHabilitation(valeurs || {});
    return Donnees.modifier('habilitations', (lignes, outils) => {
      refuserSiErreurs(verifierHabilitation(propres));
      if (memeHabilitation(lignes, technicien.id, propres.intitule).length) {
        throw ErreurValidation(nomComplet(technicien) + ' a déjà l\'habilitation « ' + propres.intitule
          + ' » : utilisez « Renouveler » (nouvelle échéance) ou « Corriger » (erreur de saisie).');
      }
      const id = outils.nouvelId(lignes);
      lignes.push({ id, technicien_id: technicien.id, intitule: propres.intitule,
        date_obtention: propres.date_obtention, date_echeance: propres.date_echeance || '' });
      return id;
    }, { action: 'habilitation ' + propres.intitule + ' ajoutée' });
  }

  /** Corrige une habilitation (erreur de saisie) ; renvoie la liste des champs changés. */
  async function modifierHabilitation(habilitationId, valeurs) {
    const propres = valeursHabilitation(valeurs || {});
    return Donnees.modifier('habilitations', (lignes) => {
      const ligne = lignes.find((l) => l.id === habilitationId);
      if (!ligne) throw ErreurValidation('L\'habilitation ' + habilitationId + ' est introuvable.');
      const corrigee = Object.assign({}, ligne, propres);
      refuserSiErreurs(verifierHabilitation(corrigee));
      if (cleIntitule(corrigee.intitule) !== cleIntitule(ligne.intitule)
          && memeHabilitation(lignes, ligne.technicien_id, corrigee.intitule).length) {
        throw ErreurValidation('Ce technicien a déjà l\'habilitation « ' + corrigee.intitule + ' ».');
      }
      const changes = Object.keys(propres).filter((nom) => texte(ligne[nom]) !== propres[nom]);
      changes.forEach((nom) => { ligne[nom] = propres[nom]; });
      return changes;
    }, { action: 'correction de l\'habilitation' });
  }

  /**
   * Renouvelle une habilitation : NOUVELLE ligne de même technicien et même intitulé, avec les
   * dates données (l'ancienne ligne reste intacte). Refus : échéance avant l'obtention ; nouvelle
   * échéance qui ne dépasse pas l'échéance actuelle (sinon l'ancienne compterait encore) ;
   * habilitation sans échéance (rien à renouveler : la corriger). Renvoie l'identifiant créé.
   */
  async function renouvelerHabilitation(habilitationId, valeurs) {
    const dates = { date_obtention: texte(valeurs && valeurs.date_obtention), date_echeance: texte(valeurs && valeurs.date_echeance) };
    let action = 'renouvellement de ' + habilitationId;
    return Donnees.modifier('habilitations', (lignes, outils) => {
      const ancienne = lignes.find((l) => l.id === habilitationId);
      if (!ancienne) throw ErreurValidation('L\'habilitation ' + habilitationId + ' est introuvable.');
      refuserSiErreurs(verifierHabilitation(Object.assign({ intitule: ancienne.intitule }, dates)));
      const lignesMeme = memeHabilitation(lignes, ancienne.technicien_id, ancienne.intitule);
      if (lignesMeme.some((l) => !texte(l.date_echeance))) {
        throw ErreurValidation('L\'habilitation « ' + ancienne.intitule + ' » n\'a pas d\'échéance : rien à renouveler (corrigez-la si besoin).');
      }
      // Une échéance illisible ne compte pas : le renouvellement la remplace.
      const actuelle = lignesMeme.map((l) => dateIso(l.date_echeance)).filter(Boolean).sort().pop() || '';
      if (dates.date_echeance && actuelle && dates.date_echeance <= actuelle) {
        throw ErreurValidation('La nouvelle échéance doit dépasser l\'échéance actuelle (' + UI.dateFr(actuelle) + ').');
      }
      const id = outils.nouvelId(lignes);
      lignes.push({ id, technicien_id: ancienne.technicien_id, intitule: ancienne.intitule,
        date_obtention: dates.date_obtention, date_echeance: dates.date_echeance });
      action = 'renouvellement de ' + ancienne.id + ' (' + ancienne.intitule + ') : échéance '
        + (actuelle ? UI.dateFr(actuelle) : 'illisible') + ' → ' + libelleDate(dates.date_echeance);
      return id;
    }, { get action() { return action; } });          // texte lu après la mutation (voir modifierTechnicien)
  }

  // Contrôles prêtés aux écrans du module (erreurs affichées sous les champs avant d'écrire).
  Object.assign(Equipe.interne, { verifierHabilitation, CAPACITE_MAX_H });

  return {
    // écritures (ARCHITECTURE.md §15.8)
    verifierTechnicien, creerTechnicien, modifierTechnicien,
    ajouterHabilitation, modifierHabilitation, renouvelerHabilitation,
  };
})());
