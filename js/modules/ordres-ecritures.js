'use strict';
// Ordres (2/7) — écritures du module « Ordres de travail » (ARCHITECTURE.md §10, §14.2 et §14.6) :
// création d'un OT, modification de ses champs, changement de statut (RG3, puis mise à jour de la
// gamme d'un préventif clôturé : RG5) et de priorité, OT lié, case « anomalie constatée »,
// avertissement d'habilitation au journal (RG8), écriture dans les tables liées à un OT (temps,
// pièces prévues, opérations). Toujours par Donnees.modifier : chaque fonction relit la ligne
// fraîche et la contrôle. Complète l'objet Ordres créé par ordres-regles.js.

Object.assign(Ordres, (() => {

  // Constantes, outils et règles de ordres-regles.js.
  const { PRIORITES, estVerrouille, verifierPassage, datePrevueParDefaut } = Ordres;
  const { texte } = Ordres.interne;

  // ===========================================================================================
  // 3. Écritures (Donnees.modifier) — chaque fonction relit la ligne fraîche et la contrôle
  // ===========================================================================================

  function ErreurValidation(message) {
    return new Donnees.ErreurValidation(message);
  }

  // Ligne d'OT dans une copie de table, ou erreur si absente ; `modifiable` refuse un OT verrouillé.
  function ligneOt(lignes, otId, modifiable) {
    const ligne = lignes.find((l) => l.id === otId);
    if (!ligne) throw ErreurValidation('L\'ordre de travail ' + otId + ' est introuvable.');
    if (modifiable && estVerrouille(ligne)) {
      throw ErreurValidation('L\'OT ' + otId + ' est « ' + ligne.statut + ' » : il ne peut plus être modifié.');
    }
    return ligne;
  }

  /**
   * Crée un OT et renvoie son identifiant (OT-AAAA-NNNN calculé dans la fonction de mutation).
   * valeurs : equipement_id, titre, type, priorite, origine (manuel, urgence…), et facultatifs.
   */
  async function creer(valeurs) {
    return Donnees.modifier('ordres_travail', (lignes, outils) => {
      const date = outils.aujourdhui();
      const id = outils.nouvelId(lignes, date);
      lignes.push(Object.assign({
        origine: 'manuel', statut: 'Créé', arret_production: '0', remise_service: '0',
      }, valeurs, { id, statut: 'Créé', date_creation: outils.maintenant() }));
      return id;
    }, { action: 'création de l\'OT (' + (valeurs.origine || 'manuel') + ')' });
  }

  /**
   * Modifie des champs d'un OT non verrouillé ; renvoie la liste des champs réellement changés.
   * Un OT « Clôturé techniquement » (sur la ligne fraîche) refuse tout changement : sa clôture
   * (RG4) a été vérifiée ; il faut que le responsable le rouvre pour modifier ses saisies.
   */
  async function modifierOt(otId, changements, action) {
    return Donnees.modifier('ordres_travail', (lignes) => {
      const ligne = ligneOt(lignes, otId, true);
      const changes = Object.keys(changements).filter((nom) => texte(ligne[nom]) !== texte(changements[nom]));
      if (changes.length && ligne.statut === 'Clôturé techniquement') {
        throw ErreurValidation('L\'OT ' + otId + ' est « Clôturé techniquement » (sans doute sur un autre poste) : '
          + 'ses saisies ne peuvent plus être modifiées. Le responsable peut le rouvrir.');
      }
      changes.forEach((nom) => { ligne[nom] = changements[nom]; });
      return changes;
    }, { action });
  }

  /**
   * Change le statut d'un OT (RG3). Dans la fonction de mutation : le statut lu doit être encore
   * `statutAttendu` (sinon l'OT a bougé sur un autre poste) et le passage est revérifié.
   * complement : { motif_attente } ou { motif_annulation }. Renvoie le statut atteint.
   * Après une clôture technique réussie d'un OT de gamme : mise à jour de la gamme (RG5).
   */
  async function changerStatut(otId, statutAttendu, cible, complement) {
    const statut = await ecrireStatut(otId, statutAttendu, cible, complement);
    if (statut === 'Clôturé techniquement') await mettreAJourGamme(otId);
    return statut;
  }

  // Le changement de statut lui-même (une seule écriture de ordres_travail).
  async function ecrireStatut(otId, statutAttendu, cible, complement) {
    const ajout = complement || {};
    const motif = ajout.motif_attente || ajout.motif_annulation || '';
    return Donnees.modifier('ordres_travail', (lignes, outils) => {
      const ligne = ligneOt(lignes, otId, false);
      if (ligne.statut !== statutAttendu) {
        throw ErreurValidation('L\'OT ' + otId + ' est passé « ' + ligne.statut + ' » sur un autre poste. Actualisez puis recommencez.');
      }
      const verification = verifierPassage(Object.assign({}, ligne, ajout), cible);
      if (!verification.ok) throw ErreurValidation(verification.erreurs.join(' '));
      const maintenant = outils.maintenant();
      if (cible === 'En attente') ligne.motif_attente = ajout.motif_attente;
      if (cible === 'Annulé') ligne.motif_annulation = ajout.motif_annulation;
      if (cible === 'En cours' && !texte(ligne.date_debut)) ligne.date_debut = maintenant;
      if (cible === 'En cours' && statutAttendu === 'Clôturé techniquement') ligne.date_cloture_tech = '';
      if (cible === 'Clôturé techniquement') ligne.date_cloture_tech = maintenant;
      if (cible === 'Clôturé administrativement') ligne.date_cloture_admin = maintenant;
      ligne.statut = cible;
      return cible;
    }, { action: 'statut ' + statutAttendu + ' → ' + cible + (motif ? ' : ' + motif : '') });
  }

  // Avertissement de la dernière clôture technique d'un OT dont la gamme n'a pas pu être mise à
  // jour : otId → message. Lu (et effacé) par la fiche, qui l'affiche à la place du succès.
  const avertissementsGamme = new Map();

  /**
   * RG5 (ARCHITECTURE.md §14.3) : après la clôture technique d'un OT qui a un gamme_id, la gamme
   * prend la date de fin de l'OT comme dernière réalisation (Preventif.apresCloture, idempotent).
   * La clôture est déjà enregistrée : un échec ne l'annule pas. Il est dit à l'utilisateur (toast
   * d'avertissement), tracé en console (console.warn) et gardé pour la fiche.
   */
  async function mettreAJourGamme(otId) {
    const ot = Donnees.trouver('ordres_travail', otId);
    if (!ot || !texte(ot.gamme_id)) return;
    try {
      if (typeof Preventif === 'undefined') throw new Error('le module Préventif n\'est pas chargé.');
      await Preventif.apresCloture(otId);
      avertissementsGamme.delete(otId);
    } catch (erreur) {
      const message = 'L\'OT ' + otId + ' est bien clôturé, mais la gamme ' + ot.gamme_id + ' n\'a pas été mise à jour ('
        + ((erreur && erreur.message) || erreur) + ') : vérifiez sa dernière réalisation sur la fiche de la gamme.';
      avertissementsGamme.set(otId, message);
      UI.toast(message, 'attention');
      console.warn('Prévo (ordres) : ' + message, erreur);
    }
  }

  /** Avertissement de mise à jour de la gamme laissé par la dernière clôture de l'OT ('' sinon), puis effacé. */
  function lireAvertissementGamme(otId) {
    const message = avertissementsGamme.get(otId) || '';
    avertissementsGamme.delete(otId);
    return message;
  }

  /**
   * Case « Anomalie constatée » d'un OT préventif (ARCHITECTURE.md §14.6). Refus si l'OT est
   * verrouillé (RG3 : Clôturé administrativement, Annulé) ou s'il n'est pas préventif, contrôlé
   * sur la ligne fraîche. Renvoie true si la valeur a changé.
   */
  async function changerAnomalie(otId, constatee) {
    const valeur = constatee ? '1' : '0';
    return Donnees.modifier('ordres_travail', (lignes) => {
      const ligne = ligneOt(lignes, otId, true);
      if (ligne.origine !== 'préventif') {
        throw ErreurValidation('« Anomalie constatée » concerne les OT préventifs : ' + otId + ' est d\'origine « ' + ligne.origine + ' ».');
      }
      if (texte(ligne.anomalie_constatee) === valeur) return false;
      ligne.anomalie_constatee = valeur;
      return true;
    }, { action: constatee ? 'anomalie constatée' : 'anomalie constatée retirée' });
  }

  /** Priorité modifiée par le responsable, motif obligatoire (journal : « priorité P2 → P1 : motif »). */
  async function changerPriorite(otId, nouvelle, motif) {
    const ancienne = texte((Donnees.trouver('ordres_travail', otId) || {}).priorite);
    return Donnees.modifier('ordres_travail', (lignes) => {
      const ligne = ligneOt(lignes, otId, true);
      if (!PRIORITES.includes(nouvelle)) throw ErreurValidation('Priorité inconnue : ' + nouvelle + '.');
      if (!texte(motif)) throw ErreurValidation('Le motif du changement de priorité est obligatoire.');
      ligne.priorite = nouvelle;
    }, { action: 'priorité ' + ancienne + ' → ' + nouvelle + ' : ' + motif });
  }

  /** Crée un OT lié (reprise d'un OT verrouillé) : ot_lie_id = OT d'origine. Renvoie son identifiant. */
  async function creerOtLie(otId) {
    const origine = Donnees.trouver('ordres_travail', otId);
    if (!origine) throw ErreurValidation('L\'ordre de travail ' + otId + ' est introuvable.');
    return creer({
      origine: 'manuel', equipement_id: origine.equipement_id, type: origine.type, priorite: origine.priorite,
      titre: 'Reprise de ' + origine.id + ' — ' + texte(origine.titre).slice(0, 120),
      travail_a_faire: origine.travail_a_faire, consignes: origine.consignes,
      date_prevue: datePrevueParDefaut(origine.priorite), ot_lie_id: origine.id,
    });
  }

  /** Enregistre l'avertissement RG8 au journal (« avertissement habilitation : … »). */
  async function journaliserHabilitation(otId, message) {
    return Donnees.journaliser('ordres_travail', otId, 'avertissement habilitation : ' + message);
  }

  // Refus d'écrire dans une table liée (temps, pièces, opérations) si l'OT est verrouillé ou
  // clôturé techniquement. Lit le cache : appeler via modifierLieeAOt, qui le relit juste avant.
  function verifierOtModifiable(otId) {
    const ot = Donnees.trouver('ordres_travail', otId);
    if (!ot) throw ErreurValidation('L\'ordre de travail ' + otId + ' est introuvable.');
    if (estVerrouille(ot) || ot.statut === 'Clôturé techniquement') {
      throw ErreurValidation('L\'OT ' + otId + ' est « ' + ot.statut + ' » (sans doute sur un autre poste) : il ne peut plus être modifié.');
    }
  }

  /**
   * Écrit dans une table liée à l'OT (ot_temps, ot_pieces, ot_operations) après avoir relu
   * ordres_travail sur le stockage : un OT clôturé ou annulé sur un autre poste est refusé.
   * Le contrôle est refait dans la fonction de mutation (rejouée en cas de conflit).
   */
  async function modifierLieeAOt(otId, table, fonction, options) {
    await Donnees.rechargerTable('ordres_travail');
    verifierOtModifiable(otId);
    return Donnees.modifier(table, (lignes, outils) => {
      verifierOtModifiable(otId);
      return fonction(lignes, outils);
    }, options);
  }

  // Outils prêtés aux fichiers suivants du module (usage interne).
  Object.assign(Ordres.interne, { modifierOt, modifierLieeAOt, journaliserHabilitation, changerAnomalie, lireAvertissementGamme });

  return {
    // écritures (ARCHITECTURE.md §10)
    creer, changerStatut, changerPriorite, creerOtLie,
  };
})());
