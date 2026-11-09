'use strict';
// Ordres — RG8 à l'écran (2.2, lot L3, D186, D191 ; CS178, CS180 ; conception L2-L3 §7.4 et §7.6) : l'habilitation
// exigée bloque l'affectation, le responsable seul passe outre, avec un motif (QUESTIONS-L2-L6 Q7).
// - T438 : le bandeau du refus, en direct au nouvel OT et à la préparation (déplacé d'ordres-fiche.js et
//   d'ordres-onglets.js), l'information « dérogation du responsable le … » sur la fiche, la fenêtre « Habilitation
//   exigée non valide » (Ordres.demanderDerogation) et Ordres.avecDerogation (nouvel OT, préparation, bouton
//   « Planifier » ; le planning, T439) ;
// - T440 : le champ « Habilitation exigée pour cet OT » (nouvel OT et préparation ; ordres-onglets.js, à 700 lignes,
//   ne grandit pas : la logique d'habilitation de la préparation est ici).
// Le technicien voit les bandeaux, jamais la case ni le bouton « passer outre » : aucune fenêtre ne lui est ouverte.
// Chargé juste après ordres-impression.js (qui enregistre les écrans du module). Complète l'objet Ordres ; les écrans
// d'ordres-fiche.js et d'ordres-onglets.js appellent ce fichier par Ordres et Ordres.interne, au moment de l'appel.

Object.assign(Ordres, (() => {

  // Règles et outils de ordres-regles.js (RG8 pure : T436, T437).
  const { controleHabilitation, derogationAccordee, lireDerogation, nomTechnicien } = Ordres;
  const { texte, estResponsable, repereEquipement, refusHabilitation, messageRefusHabilitation,
    libelleManquante } = Ordres.interne;

  // ===========================================================================================
  // Bandeaux : refus en direct (nouvel OT, préparation) et dérogation de l'affectation actuelle (fiche)
  // ===========================================================================================

  /** Bandeau du refus RG8 (refus de refusHabilitation) : le responsable lit qu'il pourra passer outre, les autres non. */
  function bandeauRefus(refus) {
    const valeurs = {
      nomTechnicien: nomTechnicien(refus.technicienId), technicienId: refus.technicienId, date: UI.dateFr(refus.date),
      liste: refus.manquantes.map(libelleManquante).join(', '),
    };
    return UI.bandeau('important', I18n.html(estResponsable() ? 'ordres.bandeau_habilitation.refus_responsable'
      : 'ordres.bandeau_habilitation.refus', valeurs));
  }

  /**
   * Bandeau RG8 en direct dans la zone .ot-zone-habilitation d'un formulaire (nouvel OT, préparation), revu à chaque
   * changement : otDuFormulaire(valeurs) rend l'OT tel qu'il serait écrit (equipement_id, technicien_id, date_prevue,
   * habilitation_requise). Rien quand l'OT n'exige rien, que le technicien est habilité ou qu'une dérogation est déjà
   * notée pour ce même OT, technicien, date et habilitations. Rend la fonction qui revoit la zone.
   */
  function brancherZoneHabilitation(formulaire, otDuFormulaire) {
    const zone = UI.$('.ot-zone-habilitation', formulaire);
    const montrer = () => {
      const valeurs = UI.lireFormulaire(formulaire);
      const refus = refusHabilitation(otDuFormulaire(valeurs), valeurs.technicien_id, valeurs.date_prevue);
      zone.textContent = '';
      if (refus) zone.appendChild(bandeauRefus(refus));
    };
    montrer();
    formulaire.addEventListener('change', montrer);
    return montrer;
  }

  /**
   * Fiche de l'OT : l'affectation actuelle manque d'une habilitation exigée et une dérogation du responsable est
   * notée au journal → « Affecté sans habilitation BR valide : dérogation du responsable le 08/11/2026 à 10:42 »
   * (et son motif) ; sinon null. Vu de tous les profils.
   */
  function bandeauDerogation(ot) {
    const controle = controleHabilitation(ot, ot.technicien_id, ot.date_prevue);
    if (!controle.bloque) return null;
    const entree = derogationAccordee(ot.id, controle.technicienId, controle.date, controle.manquantes);
    if (!entree) return null;
    const derogation = lireDerogation(entree.action);
    return UI.bandeau('attention', I18n.html('ordres.bandeau_habilitation.derogation', {
      n: controle.manquantes.length, liste: controle.manquantes.map((m) => m.intitule).join(', '),
      date: UI.dateFr(entree.date_heure), heure: texte(entree.date_heure).slice(11, 16),
      motif: derogation ? derogation.motif : '',
    }));
  }

  // ===========================================================================================
  // Fenêtre « Habilitation exigée non valide » et écriture avec dérogation (responsable seul)
  // ===========================================================================================

  /** « équipement AE-03 », « OT » ou « équipement AE-03 ; OT » : d'où viennent les exigences manquantes. */
  function originesDe(manquantes, equipementId) {
    const vient = (origine) => manquantes.some((m) => (m.origines || []).includes(origine));
    const valeurs = { repereEquipement: repereEquipement(equipementId) };
    if (vient('equipement') && vient('ot')) return I18n.t('ordres.derogation.origine_equipement_ot', valeurs);
    return vient('ot') ? I18n.t('ordres.derogation.origine_ot') : I18n.t('ordres.derogation.origine_equipement', valeurs);
  }

  /**
   * Fenêtre « Habilitation exigée non valide » (§7.4). infos : le refus d'une écriture (erreur.habilitation = { otId,
   * technicienId, date, manquantes }), plus equipementId quand l'OT n'existe pas encore (nouvel OT). Case « Je passe
   * outre, sous ma responsabilité… » et motif obligatoires : « Passer outre et enregistrer » reste inactif sans eux
   * (Q7). Rend { motif }, ou null (Annuler, Échap). Hors responsable : null, sans rien ouvrir (rien que le refus).
   */
  async function demanderDerogation(infos) {
    const manquantes = (infos && infos.manquantes) || [];
    if (!estResponsable() || !manquantes.length) return null;
    const ot = infos.otId ? Donnees.trouver('ordres_travail', infos.otId) : null;
    const equipementId = texte(infos.equipementId) || texte(ot && ot.equipement_id);
    const contenu = UI.element(UI.html`<div class="form-colonne ot-derogation">
      <p>${I18n.t('ordres.derogation.constat', { nomTechnicien: nomTechnicien(infos.technicienId), technicienId: infos.technicienId,
        date: UI.dateFr(infos.date), liste: manquantes.map(libelleManquante).join(', ') })}</p>
      <p><b>${I18n.t('ordres.derogation.exigence', { n: manquantes.length, origines: originesDe(manquantes, equipementId) })}</b></p>
      <label class="case ot-derogation-case"><input type="checkbox" name="passer_outre" required aria-required="true">
        <span>${I18n.t('ordres.derogation.case')}</span></label>
      <div class="champ"><label class="libelle" for="ot-derogation-motif">${I18n.t('ordres.derogation.motif')} <span class="requis" aria-hidden="true">*</span></label>
        <textarea id="ot-derogation-motif" name="motif" rows="3" data-dictee required aria-required="true"
          placeholder="${I18n.t('ordres.derogation.exemple_motif')}"></textarea></div>
      <p class="aide" id="ot-derogation-aide">${I18n.t('ordres.derogation.aide')}</p>
    </div>`);
    const caseOutre = UI.$('[name="passer_outre"]', contenu);
    const motif = UI.$('[name="motif"]', contenu);
    const pret = () => caseOutre.checked && motif.value.trim() !== '';
    const choix = await UI.fenetre({
      titre: I18n.t('ordres.derogation.titre'), contenu, classe: 'ot-fenetre-derogation',
      boutons: [
        { libelle: I18n.t('commun.bouton.annuler'), valeur: null, classe: 'btn-fantome' },
        { libelle: I18n.t('ordres.derogation.passer_outre'), valeur: 'passer', classe: 'btn-danger ot-passer-outre' },
      ],
      surOuverture(dialogue) {
        const bouton = UI.$('.ot-passer-outre', dialogue);
        bouton.setAttribute('aria-describedby', 'ot-derogation-aide');
        const suivre = () => { bouton.disabled = !pret(); };
        contenu.addEventListener('input', suivre);
        contenu.addEventListener('change', suivre);
        suivre();
      },
      avantFermeture: (valeur) => valeur !== 'passer' || pret(),
    });
    return choix === 'passer' && pret() ? { motif: motif.value.trim() } : null;
  }

  /** Le refus ne porte que sur RG8 (aucune autre erreur, pièce ou date, que la dérogation ne lèverait pas). */
  function seulRefusHabilitation(erreur) {
    return erreur instanceof Donnees.ErreurValidation && Boolean(erreur.habilitation)
      && erreur.message === messageRefusHabilitation(erreur.habilitation, false);
  }

  /**
   * Écriture qui affecte un technicien (Ordres.creer, modifierOt, changerStatut vers « Planifié », Planning.planifier) :
   * ecrire(options) est essayée sans option ; sur un refus d'habilitation (seul), le responsable voit la fenêtre, puis
   * l'écriture est refaite avec { passerOutreHabilitation: true, motifDerogation } (la dérogation est notée au journal
   * par l'écriture elle-même). contexte : { equipementId } pour un OT pas encore créé. Rend le résultat de l'écriture.
   * Hors responsable, fenêtre annulée ou autre erreur : l'erreur est relancée, rien n'est écrit (l'appelant la dit).
   */
  async function avecDerogation(ecrire, contexte) {
    try {
      return await ecrire(undefined);
    } catch (erreur) {
      if (!seulRefusHabilitation(erreur) || !estResponsable()) throw erreur;
      const choix = await demanderDerogation(Object.assign({}, erreur.habilitation, contexte || {}));
      if (!choix) throw erreur;
      return ecrire({ passerOutreHabilitation: true, motifDerogation: choix.motif });
    }
  }

  // Outils prêtés aux écrans du module (ordres-fiche.js, ordres-onglets.js), cherchés au moment de l'appel.
  Object.assign(Ordres.interne, { brancherZoneHabilitation, bandeauDerogation });

  return { demanderDerogation, avecDerogation };
})());
