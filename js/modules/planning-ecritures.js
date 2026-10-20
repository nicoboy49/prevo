'use strict';
// Planning (2/3) — écriture du planning : placer un OT sur un technicien et un jour (ARCHITECTURE.md
// §15.5 ; brief §7 RG3 et RG8). Une seule écriture de ordres_travail, contrôlée sur la ligne
// fraîche ; puis l'avertissement d'habilitation (RG8), affiché et inscrit au journal comme au lot 1.

Object.assign(Planning, (() => {

  const { texte } = Planning.interne;
  const MOTIF_DATE = /^\d{4}-\d{2}-\d{2}$/;

  function ErreurValidation(message) {
    return new Donnees.ErreurValidation(message);
  }

  /** Contrôles faits avant d'écrire (sur les tables en mémoire) : date lisible, technicien actif. */
  function verifierDemande(technicienId, date) {
    if (!MOTIF_DATE.test(date)) throw ErreurValidation('Choisissez une date prévue valide.');
    const technicien = Donnees.trouver('techniciens', technicienId);
    if (!technicien) throw ErreurValidation('Choisissez un technicien.');
    if (texte(technicien.actif) === '0') {
      throw ErreurValidation('Le technicien ' + technicienId + ' est désactivé : choisissez un technicien actif.');
    }
  }

  /**
   * Place l'OT `otId` sur le technicien et le jour donnés → { statut, avertissements }.
   *   - « Préparé » → « Planifié » : contrôles RG3 refaits sur la ligne fraîche (technicien, date,
   *     pièces prévues en stock). Pièce manquante → ErreurValidation dont `piecesManquantes` donne
   *     le détail (l'écran propose alors « Mettre en attente (motif : pièce) ») ;
   *   - « Planifié » : nouvelle date ou nouveau technicien, statut inchangé (replanification) ;
   *   - tout autre statut est refusé (« Créé » : il faut d'abord préparer l'OT).
   * statutAttendu : le statut que l'écran affichait ; s'il a changé (autre poste), refus.
   */
  async function planifier(otId, statutAttendu, technicienId, dateIso) {
    const date = texte(dateIso).slice(0, 10);
    verifierDemande(technicienId, date);
    const action = (statutAttendu === 'Préparé' ? 'planification : ' : 'replanification : ')
      + technicienId + ' le ' + date + (statutAttendu === 'Préparé' ? ' (Préparé → Planifié)' : '');
    const statut = await Donnees.modifier('ordres_travail', (lignes) => {
      const ligne = lignes.find((candidate) => candidate.id === otId);
      if (!ligne) throw ErreurValidation('L\'ordre de travail ' + otId + ' est introuvable.');
      if (ligne.statut !== statutAttendu) {
        throw ErreurValidation('L\'OT ' + otId + ' est passé « ' + ligne.statut + ' » sur un autre poste. Actualisez puis recommencez.');
      }
      if (ligne.statut === 'Créé') {
        throw ErreurValidation('L\'OT ' + otId + ' est « Créé » : préparez-le d\'abord (fiche OT, onglet Préparation), puis planifiez-le.');
      }
      if (ligne.statut !== 'Préparé' && ligne.statut !== 'Planifié') {
        throw ErreurValidation('Seul un OT « Préparé » ou « Planifié » se place sur le planning : ' + otId + ' est « ' + ligne.statut + ' ».');
      }
      if (ligne.statut === 'Préparé') {
        const verification = Ordres.verifierPassage(Object.assign({}, ligne, { technicien_id: technicienId, date_prevue: date }), 'Planifié');
        if (!verification.ok) {
          const erreur = ErreurValidation(verification.erreurs.join(' '));
          erreur.piecesManquantes = verification.piecesManquantes || [];
          throw erreur;
        }
        ligne.statut = 'Planifié';
      }
      ligne.technicien_id = technicienId;
      ligne.date_prevue = date;
      return ligne.statut;
    }, { action });

    // RG8 : avertissement (jamais un blocage), affiché par l'écran et tracé au journal.
    const ot = Donnees.trouver('ordres_travail', otId);
    const message = Ordres.verifierHabilitation(ot && ot.equipement_id, technicienId, date);
    const avertissements = [];
    if (message) {
      avertissements.push('Avertissement habilitation : ' + message + '.');
      await Donnees.journaliser('ordres_travail', otId, 'avertissement habilitation : ' + message);
    }
    return { statut, avertissements };
  }

  return { planifier };
})());
