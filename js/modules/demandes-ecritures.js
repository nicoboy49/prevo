'use strict';
// Demandes (2/5) — écritures du module « Demandes d'intervention » (ARCHITECTURE.md §10 RG1 et
// §14.2, §14.6) : créer une DI (avec son code symptôme et, si elle est signalée pendant un OT
// préventif, l'OT d'origine marqué « anomalie constatée »), l'accepter (OT créé avec le code
// symptôme, puis annulé s'il devient orphelin), la regrouper, la différer, la refuser ; et le nom
// de fichier d'une photo. Toujours par Donnees.modifier, le contrôle étant refait DANS la fonction
// de mutation. Complète l'objet Demandes.

Object.assign(Demandes, (() => {

  // Constantes, outils et règles de demandes-regles.js.
  const { normaliserImpact, typePropose, datePrevue } = Demandes;
  const { STATUTS_A_TRAITER, PRIORITES, TYPE_IMMEDIAT, TYPE_DIFFERE, MESSAGE_DEJA_TRAITEE, texte,
    deuxChiffres, prioriteDeLaDemande, estOuvert, nomDuProfil, codesSymptome, estOtPreventif } = Demandes.interne;

  // ===========================================================================================
  // 3. Écritures (toutes par Donnees.modifier)
  // ===========================================================================================

  // Vérifie qu'une décision est encore possible sur la DI (statut Nouvelle ou Différée).
  function verifierATraiter(demande, diId) {
    if (!demande) throw new Donnees.ErreurValidation('La demande ' + diId + ' est introuvable.');
    if (!STATUTS_A_TRAITER.includes(demande.statut)) {
      throw new Donnees.ErreurValidation(MESSAGE_DEJA_TRAITEE + ' (statut actuel : ' + demande.statut + ').');
    }
  }

  // Relit demandes.csv avant une décision : un autre poste a peut-être déjà décidé.
  // (Le contrôle est refait DANS la fonction de mutation : c'est lui qui fait foi.)
  async function verifierEncoreATraiter(diId) {
    const lignes = await Donnees.rechargerTable('demandes');
    verifierATraiter(lignes.find((ligne) => ligne.id === diId), diId);
  }

  /** Vérifie un code symptôme saisi : vide, ou un code connu de la famille « symptôme ». */
  function verifierCodeSymptome(code) {
    if (code && !codesSymptome().some((entree) => entree.code === code)) {
      throw new Donnees.ErreurValidation('Le code symptôme ' + code + ' est inconnu.');
    }
  }

  /**
   * Vérifie l'OT d'origine d'une DI signalée pendant un préventif : il doit exister (relu sur le
   * disque s'il n'est pas encore connu de ce poste, un OT n'est jamais supprimé) et être préventif.
   */
  async function verifierOtOrigine(otId) {
    let ot = Donnees.trouver('ordres_travail', otId);
    if (!ot) ot = (await Donnees.rechargerTable('ordres_travail')).find((ligne) => ligne.id === otId);
    if (!ot) throw new Donnees.ErreurValidation('L\'ordre de travail ' + otId + ' est introuvable.');
    if (!estOtPreventif(ot)) {
      throw new Donnees.ErreurValidation('L\'ordre de travail ' + otId + ' n\'est pas un OT préventif : la demande ne peut pas lui être liée.');
    }
  }

  /**
   * Crée une demande. valeurs : { equipement_id, symptome, impact, description, photo, demandeur,
   * symptome_code (facultatif : code connu de la famille « symptôme »), ot_origine_id (facultatif :
   * OT préventif pendant lequel l'anomalie a été constatée) }.
   * Renvoie l'identifiant (DI-AAAA-NNNN, calculé dans la fonction de mutation).
   * Avec ot_origine_id, l'OT d'origine passe ensuite « anomalie constatée » (seconde écriture,
   * idempotente) ; si elle échoue, la DI reste créée et un toast d'avertissement le dit. Un OT
   * d'origine verrouillé (Clôturé administrativement, Annulé : RG3) garde le lien depuis la DI,
   * mais n'est jamais modifié (voir marquerAnomalie).
   */
  async function creer(valeurs) {
    const v = valeurs || {};
    const equipementId = texte(v.equipement_id);
    const symptome = texte(v.symptome).replace(/[\r\n]+/g, ' ');
    const impact = normaliserImpact(v.impact);
    const symptomeCode = texte(v.symptome_code);
    const otOrigineId = texte(v.ot_origine_id);
    if (!equipementId) throw new Donnees.ErreurValidation('Choisissez l\'équipement concerné.');
    if (!Donnees.trouver('equipements', equipementId)) {
      throw new Donnees.ErreurValidation('L\'équipement ' + equipementId + ' est inconnu.');
    }
    if (!symptome) throw new Donnees.ErreurValidation('Décrivez en quelques mots ce que vous constatez.');
    if (!impact) throw new Donnees.ErreurValidation('Choisissez l\'impact : sécurité, arrêt, dégradé ou gêne.');
    verifierCodeSymptome(symptomeCode);
    if (otOrigineId) await verifierOtOrigine(otOrigineId);
    const demandeur = texte(v.demandeur) || nomDuProfil();
    const description = texte(v.description);
    const photo = texte(v.photo);

    // (1) La DI.
    const id = await Donnees.modifier('demandes', (lignes, outils) => {
      const maintenant = outils.maintenant();
      const nouvelId = outils.nouvelId(lignes, maintenant);     // DI-AAAA-NNNN, recalculé à chaque essai
      lignes.push({
        id: nouvelId, date_heure: maintenant, demandeur, equipement_id: equipementId, symptome, impact,
        description, photo, statut: 'Nouvelle', motif_decision: '', date_decision: '', ot_id: '',
        symptome_code: symptomeCode, ot_origine_id: otOrigineId,
      });
      return nouvelId;
    }, { action: otOrigineId ? 'demande signalée pendant ' + otOrigineId : 'demande signalée' });

    // (2) L'OT d'origine : « anomalie constatée ». La DI existe déjà : un échec ne l'annule pas.
    if (otOrigineId) {
      try {
        await marquerAnomalie(otOrigineId, id);
      } catch (erreur) {
        UI.toast('La demande ' + id + ' est bien créée, mais l\'OT ' + otOrigineId
          + ' n\'a pas pu être marqué « anomalie constatée » : ' + App.raisonErreur(erreur), 'attention');
        console.warn('Prévo (demandes) : anomalie non marquée sur ' + otOrigineId + ' après ' + id + '.', erreur);
      }
    }
    return id;
  }

  /**
   * Coche « anomalie constatée » sur un OT (D18 : idempotent ; une ligne déjà cochée n'est pas
   * réécrite, Donnees.modifier n'écrit rien quand rien ne change).
   * RG3 : un OT verrouillé (Clôturé administrativement, Annulé) n'est jamais modifié, même par une
   * DI liée. Le verrou est contrôlé sur la ligne FRAÎCHE reçue par la fonction de mutation : un OT
   * clôturé ou annulé sur un autre poste après l'ouverture du formulaire n'est pas marqué (conflit
   * d'écriture → table relue → fonction rejouée → rien à écrire).
   * Renvoie true si l'OT porte la marque, false s'il est verrouillé (laissé tel quel).
   */
  async function marquerAnomalie(otId, diId) {
    return Donnees.modifier('ordres_travail', (lignes) => {
      const ot = lignes.find((ligne) => ligne.id === otId);
      if (!ot) throw new Donnees.ErreurValidation('L\'ordre de travail ' + otId + ' est introuvable.');
      if (Ordres.estVerrouille(ot)) return false;
      ot.anomalie_constatee = '1';
      return true;
    }, { action: 'anomalie constatée (' + diId + ')' });
  }

  /**
   * Accepte une DI (RG1) : crée l'OT (ou réutilise celui qui porte déjà ce di_id) puis passe la DI
   * « Acceptée ». options : { priorite (défaut : calculée), motifPriorite (obligatoire si la
   * priorité change), type (défaut : P1 → correctif immédiat, sinon correctif différé) }.
   * Renvoie l'identifiant de l'OT.
   */
  async function accepter(diId, options) {
    const reglages = options || {};
    await verifierEncoreATraiter(diId);
    const demande = Donnees.trouver('demandes', diId);
    const calculee = prioriteDeLaDemande(demande) || 'P3';
    const priorite = texte(reglages.priorite) || calculee;
    if (!PRIORITES.includes(priorite)) throw new Donnees.ErreurValidation('Priorité inconnue : ' + priorite + '.');
    const motifPriorite = texte(reglages.motifPriorite);
    if (priorite !== calculee && !motifPriorite) {
      throw new Donnees.ErreurValidation('Indiquez le motif du changement de priorité (' + calculee + ' → ' + priorite + ').');
    }
    const type = texte(reglages.type) || typePropose(priorite);
    if (![TYPE_IMMEDIAT, TYPE_DIFFERE].includes(type)) {
      throw new Donnees.ErreurValidation('Type d\'ordre de travail inconnu : ' + type + '.');
    }
    const changementPriorite = priorite !== calculee
      ? 'priorité ' + calculee + ' → ' + priorite + ' : ' + motifPriorite : '';

    // (1) L'OT : réutilisé s'il existe déjà pour cette DI (essai précédent interrompu, autre poste),
    //     sinon créé. Idempotent : rejoué sans risque sur conflit. Le code symptôme de la DI est
    //     recopié dans l'OT (lot 2) ; sur un OT réutilisé, seulement si le sien est vide.
    const symptomeCode = texte(demande.symptome_code);
    const otId = await Donnees.modifier('ordres_travail', (lignes, outils) => {
      const existant = lignes.find((ot) => ot.di_id === diId);
      if (existant) {
        if (symptomeCode && !texte(existant.symptome_code)) existant.symptome_code = symptomeCode;
        return existant.id;
      }
      const maintenant = outils.maintenant();
      const id = outils.nouvelId(lignes, maintenant);
      lignes.push({
        id, origine: 'DI', di_id: diId, equipement_id: demande.equipement_id, type, priorite,
        statut: 'Créé', titre: texte(demande.symptome).replace(/[\r\n]+/g, ' '),
        travail_a_faire: demande.description || '', date_creation: maintenant,
        date_prevue: datePrevue(priorite, outils.aujourdhui()), symptome_code: symptomeCode,
      });
      return id;
    }, { action: 'acceptation de ' + diId + (changementPriorite ? ' ; ' + changementPriorite : '') });

    // (2) La DI : encore à traiter ? (sinon un autre poste a décidé entre-temps)
    let vue = null;          // la DI telle que lue (fraîche) par la fonction de mutation
    try {
      await Donnees.modifier('demandes', (lignes, outils) => {
        const ligne = lignes.find((l) => l.id === diId);
        vue = ligne ? { statut: ligne.statut, ot_id: ligne.ot_id } : null;
        verifierATraiter(ligne, diId);
        ligne.statut = 'Acceptée';
        ligne.ot_id = otId;
        ligne.date_decision = outils.maintenant();
        ligne.motif_decision = changementPriorite ? changementPriorite.charAt(0).toUpperCase() + changementPriorite.slice(1) : '';
      }, { action: 'acceptée → ' + otId + (changementPriorite ? ' ; ' + changementPriorite : '') });
    } catch (erreur) {
      // La DI a été refusée, différée ou regroupée ailleurs entre les deux étapes : l'OT créé à
      // l'étape 1 n'a plus de raison d'être. (Acceptée ailleurs avec CET OT : il est conservé.)
      if (erreur instanceof Donnees.ErreurValidation && !(vue && vue.ot_id === otId)) {
        await annulerOtOrphelin(diId, otId);
      }
      throw erreur;
    }
    return otId;
  }

  /** Annule l'OT créé pour une DI finalement traitée sur un autre poste (s'il est encore « Créé »). */
  async function annulerOtOrphelin(diId, otId) {
    const motif = 'DI traitée sur un autre poste';
    try {
      await Donnees.modifier('ordres_travail', (lignes) => {
        const ot = lignes.find((l) => l.id === otId);
        if (!ot || ot.di_id !== diId || ot.statut !== 'Créé') return;
        ot.statut = 'Annulé';
        ot.motif_annulation = motif;
      }, { action: 'statut Créé → Annulé : ' + motif });
    } catch (erreur) {
      App.signalerErreur(erreur, 'annulation de l\'OT ' + otId);
    }
  }

  /** Rattache la DI à un OT ouvert du même équipement (statut « Regroupée »). */
  async function regrouper(diId, otId) {
    await verifierEncoreATraiter(diId);
    const demande = Donnees.trouver('demandes', diId);
    const ordres = await Donnees.rechargerTable('ordres_travail');
    const ot = ordres.find((ligne) => ligne.id === otId);
    if (!ot) throw new Donnees.ErreurValidation('L\'ordre de travail ' + otId + ' est introuvable.');
    if (!estOuvert(ot)) throw new Donnees.ErreurValidation('L\'ordre de travail ' + otId + ' n\'est plus ouvert (' + ot.statut + ').');
    if (ot.equipement_id !== demande.equipement_id) {
      throw new Donnees.ErreurValidation('L\'ordre de travail ' + otId + ' concerne un autre équipement.');
    }
    await Donnees.modifier('demandes', (lignes, outils) => {
      const ligne = lignes.find((l) => l.id === diId);
      verifierATraiter(ligne, diId);
      ligne.statut = 'Regroupée';
      ligne.ot_id = otId;
      ligne.date_decision = outils.maintenant();
      ligne.motif_decision = 'Regroupée avec ' + otId + ', déjà ouvert pour cet équipement.';
    }, { action: 'regroupée avec ' + otId });
    return otId;
  }

  /** Diffère une DI nouvelle (motif facultatif, visible du demandeur). */
  async function differer(diId, motif) {
    await verifierEncoreATraiter(diId);
    await Donnees.modifier('demandes', (lignes, outils) => {
      const ligne = lignes.find((l) => l.id === diId);
      verifierATraiter(ligne, diId);
      if (ligne.statut === 'Différée') throw new Donnees.ErreurValidation('Cette demande est déjà différée.');
      ligne.statut = 'Différée';
      ligne.date_decision = outils.maintenant();
      ligne.motif_decision = texte(motif);
    }, { action: 'différée' });
  }

  /** Refuse une DI : motif obligatoire, visible du demandeur. */
  async function refuser(diId, motif) {
    const motifPropre = texte(motif);
    if (!motifPropre) throw new Donnees.ErreurValidation('Le motif du refus est obligatoire : il sera montré au demandeur.');
    await verifierEncoreATraiter(diId);
    await Donnees.modifier('demandes', (lignes, outils) => {
      const ligne = lignes.find((l) => l.id === diId);
      verifierATraiter(ligne, diId);
      ligne.statut = 'Refusée';
      ligne.date_decision = outils.maintenant();
      ligne.motif_decision = motifPropre;
    }, { action: 'refusée' });
  }

  // ===========================================================================================
  // 4. Photo : réduite à 1280 px (JPEG) dès le choix, envoyée à la validation
  // ===========================================================================================

  // photo-AAAAMMJJ-HHMMSS-XXXX.jpg (Math.random suffit : pas de crypto en contexte non sécurisé ;
  // le stockage refuse d'écraser un document existant).
  function nomPhoto() {
    const d = new Date();
    const caracteres = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    let hasard = '';
    for (let i = 0; i < 4; i += 1) hasard += caracteres[Math.floor(Math.random() * caracteres.length)];
    return 'photo-' + d.getFullYear() + deuxChiffres(d.getMonth() + 1) + deuxChiffres(d.getDate())
      + '-' + deuxChiffres(d.getHours()) + deuxChiffres(d.getMinutes()) + deuxChiffres(d.getSeconds())
      + '-' + hasard + '.jpg';
  }

  // Outil prêté aux fichiers suivants du module (usage interne).
  Object.assign(Demandes.interne, { nomPhoto });

  return {
    creer, accepter, regrouper, differer, refuser,
  };
})());
