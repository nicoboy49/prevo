'use strict';
// Ordres — RG8 à l'écran (2.2, lot L3, D186, D191 ; CS178, CS180 ; conception L2-L3 §7.4 et §7.6) : l'habilitation
// exigée bloque l'affectation, le responsable seul passe outre, avec un motif (QUESTIONS-L2-L6 Q7).
// - T438 : le bandeau du refus, en direct au nouvel OT et à la préparation (déplacé d'ordres-fiche.js et
//   d'ordres-onglets.js), l'information « dérogation du responsable le … » sur la fiche, la fenêtre « Habilitation
//   exigée non valide » (Ordres.demanderDerogation) et Ordres.avecDerogation (nouvel OT, préparation, bouton
//   « Planifier » ; le planning, T439) ;
// - T440 : le champ « Habilitation exigée par l'OT » (ot.habilitation_requise, D191 : nouvel OT et préparation ;
//   ordres-onglets.js, près de 700 lignes, ne grandit pas : la logique d'habilitation de la préparation est ici), sa liste
//   (intitulés connus et proposés par le catalogue), son aide « En plus de celle de l'équipement (BR)… », et
//   « Habilitation exigée : BR (équipement), H0V (OT) » dans l'en-tête de la fiche et sur le bon de travail.
// Le technicien voit les bandeaux, jamais la case ni le bouton « passer outre » : aucune fenêtre ne lui est ouverte.
// Chargé juste après ordres-impression.js (qui enregistre les écrans du module). Complète l'objet Ordres ; les écrans
// d'ordres-fiche.js, d'ordres-onglets.js et le bon (ordres-impression.js) appellent ce fichier par Ordres et
// Ordres.interne, au moment de l'appel.

Object.assign(Ordres, (() => {

  // Règles et outils de ordres-regles.js (RG8 pure : T436, T437).
  const { controleHabilitation, derogationAccordee, lireDerogation, nomTechnicien, habilitationsExigees } = Ordres;
  const { texte, estResponsable, repereEquipement, refusHabilitation, messageRefusHabilitation,
    libelleManquante, placerChamp, champOt } = Ordres.interne;
  // Intitulé comparable (casse et espaces ignorés) : la fonction d'Equipe (equipe-regles.js, chargé après).
  const cleIntitule = (intitule) => Equipe.interne.cleIntitule(intitule);

  // ===========================================================================================
  // Champ « Habilitation exigée par l'OT » (T440 ; D191, conception L2-L3 §7.6) : nouvel OT et préparation
  // ===========================================================================================

  /** Intitulés d'une colonne habilitation_requise lus par la règle de RG8 (« , » ou « / », doublons réunis). */
  function intitulesSaisis(valeur) {
    return habilitationsExigees({ habilitation_requise: valeur }).map((exigence) => exigence.intitule);
  }

  /** Valeur écrite : la saisie sans séparateur ni espace en tête ou en fin (« BR, » laissé par la liste → « BR »). */
  function exigenceSaisie(valeur) {
    return texte(valeur).replace(/^[\s,/]+|[\s,/]+$/g, '');
  }

  /** Intitulés connus (habilitations des techniciens, exigences des équipements et des OT) et proposés par le
   *  catalogue (« CACES R489 ») : un par intitulé (casse et espaces ignorés, première écriture gardée), triés. */
  function intitulesConnus() {
    const parCle = new Map();
    const garder = (intitule) => { const cle = cleIntitule(intitule); if (cle && !parCle.has(cle)) parCle.set(cle, texte(intitule)); };
    Donnees.lignes('habilitations').forEach((h) => garder(h.intitule));
    ['equipements', 'ordres_travail'].forEach((table) => Donnees.lignes(table)
      .forEach((ligne) => intitulesSaisis(ligne.habilitation_requise).forEach(garder)));
    Equipe.typesHabilitation().forEach((type) => garder(Equipe.intitulePropose(type)));
    return Array.from(parCle.values()).sort((a, b) => UI.comparerTextes(a, b));
  }

  /** Propositions de la liste d'après la saisie : « H0V », ou, après « BR, », « BR, H0V » (intitulés déjà saisis ôtés). */
  function proposer(saisie, liste, connus) {
    const debut = saisie.value.replace(/[^,/]*$/, '');
    const prefixe = debut ? debut.replace(/\s*$/, ' ') : '';
    const saisis = new Set(intitulesSaisis(debut).map(cleIntitule));
    UI.remplir(liste, connus.filter((intitule) => !saisis.has(cleIntitule(intitule)))
      .map((intitule) => UI.html`<option value="${prefixe + intitule}"></option>`));
  }

  /** Aide : « En plus de celle de l'équipement (BR). Plusieurs : séparez par des virgules. » (ou : il n'en exige aucune). */
  function aideExigence(equipementId) {
    const equipement = Donnees.trouver('equipements', texte(equipementId));
    if (!equipement) return I18n.t('ordres.habilitation_exigee.aide_sans_equipement');
    const siennes = intitulesSaisis(equipement.habilitation_requise);
    return siennes.length ? I18n.t('ordres.habilitation_exigee.aide_equipement', { n: siennes.length, liste: siennes.join(', ') })
      : I18n.t('ordres.habilitation_exigee.aide_sans_exigence');
  }

  /**
   * Place le champ dans data-place="habilitation_requise" du formulaire (s'il y est) : valeur ot.habilitation_requise
   * (ot null au nouvel OT : vide), liste revue à chaque frappe, aide selon l'équipement. Rend revoir(equipementId).
   */
  function placerChampExigence(formulaire, ot) {
    if (!UI.$('[data-place="habilitation_requise"]', formulaire)) return () => {};
    const idListe = UI.identifiantUnique('ot-intitules');
    const bloc = champOt('habilitation_requise', texte(ot && ot.habilitation_requise), {
      aide: aideExigence(ot && ot.equipement_id), placeholder: I18n.t('ordres.habilitation_exigee.exemple'),
      attributs: { list: idListe, autocomplete: 'off' },
    });
    const liste = UI.element(UI.html`<datalist id="${idListe}"></datalist>`);
    bloc.appendChild(liste);
    placerChamp(formulaire, 'habilitation_requise', bloc);
    const saisie = UI.$('[name="habilitation_requise"]', bloc);
    const connus = intitulesConnus();
    saisie.addEventListener('input', () => proposer(saisie, liste, connus));
    proposer(saisie, liste, connus);
    const aide = UI.$('.aide', bloc);
    return (equipementId) => { aide.textContent = aideExigence(equipementId); };
  }

  // ===========================================================================================
  // « Habilitation exigée : BR (équipement), H0V (OT) » : en-tête de la fiche et bon de travail
  // ===========================================================================================

  /** « BR (équipement), H0V (OT) » : habilitations exigées par l'OT (celle de son équipement, puis
   *  ot.habilitation_requise), chacune avec son origine ; '' quand l'OT n'exige rien. */
  function libelleExigences(ot) {
    const origines = {
      equipement: I18n.t('ordres.habilitation_exigee.origine_equipement'), ot: I18n.t('ordres.habilitation_exigee.origine_ot'),
    };
    return habilitationsExigees(ot).map((exigence) => I18n.t('ordres.habilitation_exigee.intitule_origines', {
      intitule: exigence.intitule, origines: exigence.origines.map((origine) => origines[origine]).join(', '),
    })).join(', ');
  }

  /** Badge de l'en-tête de la fiche : « Habilitation exigée : BR (équipement), H0V (OT) » ; '' sans exigence. */
  function badgeExigences(ot) {
    const liste = libelleExigences(ot);
    return liste ? UI.html`<span class="badge attention ot-habilitation-exigee">${I18n.t('ordres.habilitation_exigee.entete', { liste })}</span>` : '';
  }

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
   * habilitation_requise saisie). Rien quand l'OT n'exige rien, que le technicien est habilité ou qu'une dérogation est
   * déjà notée pour ce même OT, technicien, date et habilitations. Place d'abord le champ « Habilitation exigée par
   * l'OT » (valeur de ot, l'OT préparé ; null au nouvel OT), dont l'aide suit l'équipement. Rend la fonction qui revoit.
   */
  function brancherZoneHabilitation(formulaire, otDuFormulaire, ot) {
    const zone = UI.$('.ot-zone-habilitation', formulaire);
    const revoirChamp = placerChampExigence(formulaire, ot || null);
    const montrer = () => {
      const valeurs = UI.lireFormulaire(formulaire);
      const ligne = otDuFormulaire(valeurs);
      revoirChamp(ligne.equipement_id);
      const refus = refusHabilitation(ligne, valeurs.technicien_id, valeurs.date_prevue);
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

  // Outils prêtés aux écrans du module (ordres-fiche.js, ordres-onglets.js, ordres-impression.js), cherchés au moment
  // de l'appel.
  Object.assign(Ordres.interne, { brancherZoneHabilitation, bandeauDerogation, exigenceSaisie, libelleExigences, badgeExigences });

  return { demanderDerogation, avecDerogation };
})());
