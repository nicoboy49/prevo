'use strict';
// Planning (2/3) — écriture du planning : placer un OT sur un technicien et un jour (ARCHITECTURE.md
// §15.5 ; brief §7 RG3 et RG8). Une seule écriture de ordres_travail, contrôlée sur la ligne
// fraîche ; RG8 y est bloquante (D186, D191) : refus, ou dérogation du responsable notée à la fin de
// l'action du journal de cette écriture (Ordres.controlerAffectation, conception L2-L3 §7.3 à §7.5).

Object.assign(Planning, (() => {

  const { texte } = Planning.interne;
  const MOTIF_DATE = /^\d{4}-\d{2}-\d{2}$/;

  function ErreurValidation(message) {
    return new Donnees.ErreurValidation(message);
  }

  /** Contrôles faits avant d'écrire (sur les tables en mémoire) : date lisible, technicien actif. */
  function verifierDemande(technicienId, date) {
    if (!MOTIF_DATE.test(date)) throw ErreurValidation(I18n.t('planning.verifier_demande.choisissez_date_prevue_valide'));
    const technicien = Donnees.trouver('techniciens', technicienId);
    if (!technicien) throw ErreurValidation(I18n.t('planning.verifier_demande.choisissez_technicien'));
    if (texte(technicien.actif) === '0') {
      throw ErreurValidation(I18n.t('planning.verifier_demande.technicien_desactive_choisissez_technicien', { technicienId }));
    }
  }

  /**
   * Place l'OT `otId` sur le technicien et le jour donnés → { statut, avertissements } (avertissements :
   * toujours vide depuis que RG8 bloque, gardé pour l'écran).
   *   - « Préparé » → « Planifié » : contrôles RG3 refaits sur la ligne fraîche (technicien, date,
   *     pièces prévues en stock, RG8). Pièce manquante → ErreurValidation dont `piecesManquantes` donne
   *     le détail (l'écran propose alors « Mettre en attente (motif : pièce) ») ;
   *   - « Planifié » : nouvelle date ou nouveau technicien, statut inchangé (replanification ; RG8 revue) ;
   *   - tout autre statut est refusé (« Créé » : il faut d'abord préparer l'OT).
   * RG8 : technicien sans l'habilitation exigée valide à ce jour → ErreurValidation dont `habilitation` =
   * { otId, technicienId, date, manquantes }, rien n'est écrit ; options : { passerOutreHabilitation,
   * motifDerogation }, pris en compte pour le responsable seul et avec un motif.
   * statutAttendu : le statut que l'écran affichait ; s'il a changé (autre poste), refus.
   */
  async function planifier(otId, statutAttendu, technicienId, dateIso, options) {
    const date = texte(dateIso).slice(0, 10);
    verifierDemande(technicienId, date);
    const action = (statutAttendu === 'Préparé' ? 'planification : ' : 'replanification : ')
      + technicienId + ' le ' + date + (statutAttendu === 'Préparé' ? ' (Préparé → Planifié)' : '');
    // Relu par Donnees.modifier APRÈS la mutation : le marqueur de dérogation y est ajouté (atomique).
    const journal = { action };
    // T504 : Ordres.ecrireAvecTrace refuse d'annoncer une dérogation (journal.derogation) que le journal n'a pas notée.
    const statut = await Ordres.ecrireAvecTrace((lignes) => {
      journal.action = action;                       // fonction rejouée en cas de conflit : action de départ
      journal.derogation = '';
      const ligne = lignes.find((candidate) => candidate.id === otId);
      if (!ligne) throw ErreurValidation(I18n.t('planning.planifier.ordre_travail_introuvable', { otId }));
      if (ligne.statut !== statutAttendu) {
        throw ErreurValidation(I18n.t('planning.planifier.ot_passe_autre_poste', { otId, ligneStatut: Schema.libelleValeur('ordres_travail', 'statut', ligne.statut) }));
      }
      if (ligne.statut === 'Créé') {
        throw ErreurValidation(I18n.t('planning.planifier.ot_cree_preparez_abord', { otId }));
      }
      if (ligne.statut !== 'Préparé' && ligne.statut !== 'Planifié') {
        throw ErreurValidation(I18n.t('planning.planifier.seul_ot_prepare_planifie', { otId, ligneStatut: Schema.libelleValeur('ordres_travail', 'statut', ligne.statut) }));
      }
      const prochaine = Object.assign({}, ligne, { technicien_id: technicienId, date_prevue: date });
      const deplace = texte(ligne.technicien_id) !== technicienId || texte(ligne.date_prevue).slice(0, 10) !== date;
      if (ligne.statut === 'Préparé' || deplace) {
        const verification = ligne.statut === 'Préparé' ? Ordres.verifierPassage(prochaine, 'Planifié') : null;
        const marqueur = Ordres.controlerAffectation(prochaine, options, verification);
        if (marqueur) Object.assign(journal, { action: action + ' ; ' + marqueur, derogation: marqueur });
      }
      if (ligne.statut === 'Préparé') ligne.statut = 'Planifié';
      ligne.technicien_id = technicienId;
      ligne.date_prevue = date;
      return ligne.statut;
    }, journal, otId);
    return { statut, avertissements: [] };
  }

  return { planifier };
})());
