'use strict';
// Ordres (2/7) — écritures du module « Ordres de travail » (ARCHITECTURE.md §10, §14.2 et §14.6) :
// création d'un OT, modification de ses champs, changement de statut (RG3, puis mise à jour de la
// gamme d'un préventif clôturé : RG5) et de priorité, OT lié, case « anomalie constatée »,
// RG8 bloquante à l'affectation (refus, ou dérogation du responsable notée au journal : D186, D191),
// écriture dans les tables liées à un OT (temps, pièces prévues, opérations). Toujours par
// Donnees.modifier : chaque fonction relit la ligne fraîche et la contrôle. Complète l'objet Ordres
// créé par ordres-regles.js.

Object.assign(Ordres, (() => {

  // Constantes, outils et règles de ordres-regles.js.
  const { PRIORITES, estVerrouille, verifierPassage, datePrevueParDefaut, marqueurDerogation } = Ordres;
  const { texte, refusHabilitation, messageRefusHabilitation } = Ordres.interne;

  // ===========================================================================================
  // 3. Écritures (Donnees.modifier) — chaque fonction relit la ligne fraîche et la contrôle
  // ===========================================================================================

  function ErreurValidation(message) {
    return new Donnees.ErreurValidation(message);
  }

  // --- RG8 bloquante (D186, D191 ; CS178, CS180 ; conception L2-L3 §7.3 à §7.5) -------------
  // L'action du journal d'une écriture qui affecte un technicien finit, en cas de dérogation, par le marqueur
  // fixe d'Ordres.marqueurDerogation (D156). Donnees.modifier lit options.action APRÈS la fonction de mutation :
  // celle-ci complète l'action (objet `journal`) une fois RG8 tranchée sur la ligne fraîche, d'où l'atomicité.
  const CHAMPS_AFFECTATION = ['technicien_id', 'date_prevue', 'habilitation_requise'];

  // Le responsable seul peut passer outre : vérifié ici, un technicien qui appelle l'écriture n'y gagne rien (CS178).
  function profilResponsable() {
    return typeof App !== 'undefined' && Boolean(App) && typeof App.estResponsable === 'function' && App.estResponsable();
  }

  // D186 « qui » (T448) : le journal n'a que poste et profil ; en mode serveur avec comptes, l'identifiant du compte
  // connecté (App.session) va dans le marqueur de dérogation. Hors comptes (démo, dossier, serveur sans comptes) : ''.
  function compteConnecte() {
    if (typeof App === 'undefined' || !App || typeof App.comptesExiges !== 'function' || !App.comptesExiges()) return '';
    const session = App.session;
    return session ? texte(session.identifiant) : '';
  }

  /**
   * RG8 dans une écriture, sur l'OT tel qu'il sera écrit (technicien_id et date_prevue à jour). verification :
   * celle de verifierPassage(ot, 'Planifié'), dont les autres erreurs comptent aussi ; sans elle, RG8 seule.
   * options : { passerOutreHabilitation, motifDerogation }, pris en compte pour le responsable seul, motif
   * obligatoire (QUESTIONS-L2-L6 Q7). → marqueur de dérogation à ajouter à l'action du journal ('' : rien à
   * déroger). Sinon lève Donnees.ErreurValidation : erreur.habilitation = { otId, technicienId, date,
   * manquantes } quand RG8 refuse ; erreur.piecesManquantes = celles de verification (ou []).
   */
  function controlerAffectation(ot, options, verification) {
    const passage = verification
      || { erreurs: [], piecesManquantes: [], habilitation: refusHabilitation(ot, ot.technicien_id, ot.date_prevue) };
    const refus = passage.habilitation || null;
    const reglages = options || {};
    const passerOutre = Boolean(refus) && reglages.passerOutreHabilitation === true && profilResponsable();
    const marqueur = passerOutre
      ? marqueurDerogation(refus.technicienId, refus.date, refus.manquantes, reglages.motifDerogation, compteConnecte()) : '';
    const erreurs = passage.erreurs.filter((message) => !refus || message !== refus.message);
    if (refus && !marqueur) erreurs.push(passerOutre ? messageRefusHabilitation(refus, true) : refus.message);
    if (!erreurs.length) return marqueur;
    const erreur = ErreurValidation(erreurs.join(' '));
    erreur.piecesManquantes = passage.piecesManquantes || [];
    if (refus && !marqueur) {
      erreur.habilitation = { otId: refus.otId, technicienId: refus.technicienId, date: refus.date, manquantes: refus.manquantes };
    }
    throw erreur;
  }

  // Action du journal suivie du marqueur de dérogation (« … ; dérogation habilitation : … »), s'il y en a un ;
  // journal.derogation le garde pour ecrireAvecTrace ('' : aucune dérogation ; remis à chaque essai de l'écriture).
  function noterDerogation(journal, action, marqueur) {
    journal.derogation = marqueur;
    journal.action = !marqueur ? action : texte(action) ? action + ' ; ' + marqueur : marqueur;
  }

  /**
   * Donnees.modifier('ordres_travail', mutation, journal) pour une écriture qui peut porter une dérogation (T504,
   * D186 : le journal est la preuve). Si la dérogation (journal.derogation) est accordée mais que la ligne de journal
   * n'a pas pu être écrite, lève Donnees.ErreurStockage au lieu d'annoncer un succès. L'OT reste écrit (pas de
   * retour arrière) : sans ligne au journal, le contrôle suivant redemandera la dérogation. otId : celui de
   * l'OT, sinon ce que rend la mutation (création). Sans dérogation, un journal non écrit ne fait rien échouer.
   * T510 : cette erreur porte otEcrit (l'identifiant de l'OT écrit) et rendu (ce que l'écriture aurait rendu), pour
   * que l'écran suive l'état écrit (Ordres.avecDerogation).
   */
  async function ecrireAvecTrace(mutation, journal, otId) {
    let journalEcrit = true;
    journal.siJournalNonEcrit = () => { journalEcrit = false; };
    const rendu = await Donnees.modifier('ordres_travail', mutation, journal);
    if (!journalEcrit && journal.derogation) {
      const erreur = new Donnees.ErreurStockage(I18n.t('ordres.derogation.non_tracee', { otId: otId || rendu }));
      throw Object.assign(erreur, { otEcrit: otId || rendu, rendu });
    }
    return rendu;
  }

  // Ligne d'OT dans une copie de table, ou erreur si absente ; `modifiable` refuse un OT verrouillé.
  function ligneOt(lignes, otId, modifiable) {
    const ligne = lignes.find((l) => l.id === otId);
    if (!ligne) throw ErreurValidation(I18n.t('commun.message.ot_introuvable', { otId }));
    if (modifiable && estVerrouille(ligne)) {
      throw ErreurValidation(I18n.t('ordres.ligne_ot.ot_peut_plus_etre', { otId, ligneStatut: Schema.libelleValeur('ordres_travail', 'statut', ligne.statut) }));
    }
    return ligne;
  }

  /**
   * Crée un OT et renvoie son identifiant (OT-AAAA-NNNN calculé dans la fonction de mutation).
   * valeurs : equipement_id, titre, type, priorite, origine (manuel, urgence…), et facultatifs.
   * Avec un technicien : RG8 sur la ligne créée (controlerAffectation) ; options : { passerOutreHabilitation,
   * motifDerogation } (responsable seul), la dérogation est notée à la fin de l'action du journal.
   */
  async function creer(valeurs, options) {
    const action = 'création de l\'OT (' + (valeurs.origine || 'manuel') + ')';
    const journal = { action };
    return ecrireAvecTrace((lignes, outils) => {
      const date = outils.aujourdhui();
      const id = outils.nouvelId(lignes, date);
      const ligne = Object.assign({
        origine: 'manuel', statut: 'Créé', arret_production: '0', remise_service: '0',
      }, valeurs, { id, statut: 'Créé', date_creation: outils.maintenant() });
      noterDerogation(journal, action, controlerAffectation(ligne, options));
      lignes.push(ligne);
      return id;
    }, journal);
  }

  /**
   * Modifie des champs d'un OT non verrouillé ; renvoie la liste des champs réellement changés.
   * Un OT « Clôturé techniquement » (sur la ligne fraîche) refuse tout changement : sa clôture
   * (RG4) a été vérifiée ; il faut que le responsable le rouvre pour modifier ses saisies.
   * RG8 quand technicien_id, date_prevue ou habilitation_requise change (préparation) : controlerAffectation
   * sur la ligne fraîche modifiée ; options : { passerOutreHabilitation, motifDerogation } (responsable seul).
   */
  async function modifierOt(otId, changements, action, options) {
    const journal = { action };
    return ecrireAvecTrace((lignes) => {
      const ligne = ligneOt(lignes, otId, true);
      const changes = Object.keys(changements).filter((nom) => texte(ligne[nom]) !== texte(changements[nom]));
      if (changes.length && ligne.statut === 'Clôturé techniquement') {
        throw ErreurValidation(I18n.t('ordres.modifier_ot.ot_cloture_techniquement_sans', { otId }));
      }
      changes.forEach((nom) => { ligne[nom] = changements[nom]; });
      const affectation = changes.some((nom) => CHAMPS_AFFECTATION.includes(nom));
      noterDerogation(journal, action, affectation ? controlerAffectation(ligne, options) : '');
      return changes;
    }, journal, otId);
  }

  /**
   * Change le statut d'un OT (RG3). Dans la fonction de mutation : le statut lu doit être encore
   * `statutAttendu` (sinon l'OT a bougé sur un autre poste) et le passage est revérifié.
   * complement : { motif_attente } ou { motif_annulation }. Renvoie le statut atteint.
   * Vers « Planifié », RG8 refuse sauf dérogation : options { passerOutreHabilitation, motifDerogation }.
   * Après une clôture technique réussie d'un OT de gamme : mise à jour de la gamme (RG5).
   */
  async function changerStatut(otId, statutAttendu, cible, complement, options) {
    const statut = await ecrireStatut(otId, statutAttendu, cible, complement, options);
    if (statut === 'Clôturé techniquement') await mettreAJourGamme(otId);
    // Lot 6 (§20.5, D104) : l'OT verrouillé entre dans la file du wiki ; un échec n'annule pas la clôture (message).
    if (statut === 'Clôturé administrativement' && typeof Wiki !== 'undefined') await Wiki.mettreEnFile([otId], { annoncer: true });
    return statut;
  }

  // Le changement de statut lui-même (une seule écriture de ordres_travail).
  async function ecrireStatut(otId, statutAttendu, cible, complement, options) {
    const ajout = complement || {};
    const motif = ajout.motif_attente || ajout.motif_annulation || '';
    const action = 'statut ' + statutAttendu + ' → ' + cible + (motif ? ' : ' + motif : '');
    const journal = { action };
    return ecrireAvecTrace((lignes, outils) => {
      const ligne = ligneOt(lignes, otId, false);
      if (ligne.statut !== statutAttendu) {
        throw ErreurValidation(I18n.t('ordres.ecrire_statut.ot_passe_autre_poste', { otId, ligneStatut: Schema.libelleValeur('ordres_travail', 'statut', ligne.statut) }));
      }
      const verification = verifierPassage(Object.assign({}, ligne, ajout), cible);
      if (cible === 'Planifié') noterDerogation(journal, action, controlerAffectation(ligne, options, verification));
      else if (!verification.ok) throw ErreurValidation(verification.erreurs.join(' '));
      const maintenant = outils.maintenant();
      if (cible === 'En attente') ligne.motif_attente = ajout.motif_attente;
      if (cible === 'Annulé') ligne.motif_annulation = ajout.motif_annulation;
      if (cible === 'En cours' && !texte(ligne.date_debut)) ligne.date_debut = maintenant;
      if (cible === 'En cours' && statutAttendu === 'Clôturé techniquement') ligne.date_cloture_tech = '';
      if (cible === 'Clôturé techniquement') ligne.date_cloture_tech = maintenant;
      if (cible === 'Clôturé administrativement') ligne.date_cloture_admin = maintenant;
      ligne.statut = cible;
      return cible;
    }, journal, otId);
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
      if (typeof Preventif === 'undefined') throw new Error(I18n.t('ordres.mettre_ajour_gamme.module_preventif_pas_charge'));
      await Preventif.apresCloture(otId);
      avertissementsGamme.delete(otId);
    } catch (erreur) {
      const message = I18n.t('ordres.mettre_ajour_gamme.ot_bien_cloture_mais', { otId, gamme_id: ot.gamme_id, raisonErreur: App.raisonErreur(erreur) });
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
        throw ErreurValidation(I18n.t('ordres.changer_anomalie.anomalie_constatee_concerne_ot', { otId, origine: Schema.libelleValeur('ordres_travail', 'origine', ligne.origine) }));
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
      if (!PRIORITES.includes(nouvelle)) throw ErreurValidation(I18n.t('ordres.changer_priorite.priorite_inconnue', { nouvelle }));
      if (!texte(motif)) throw ErreurValidation(I18n.t('ordres.changer_priorite.motif_changement_priorite_obligatoire'));
      ligne.priorite = nouvelle;
    }, { action: 'priorité ' + ancienne + ' → ' + nouvelle + ' : ' + motif });
  }

  /** Crée un OT lié (reprise d'un OT verrouillé) : ot_lie_id = OT d'origine. Renvoie son identifiant. */
  async function creerOtLie(otId) {
    const origine = Donnees.trouver('ordres_travail', otId);
    if (!origine) throw ErreurValidation(I18n.t('commun.message.ot_introuvable', { otId }));
    return creer({
      origine: 'manuel', equipement_id: origine.equipement_id, type: origine.type, priorite: origine.priorite,
      titre: I18n.donnees('ordres.creer_ot_lie.reprise_origine_id', { origineId: origine.id, titre: texte(origine.titre).slice(0, 120) }),
      travail_a_faire: origine.travail_a_faire, consignes: origine.consignes,
      date_prevue: datePrevueParDefaut(origine.priorite), ot_lie_id: origine.id,
    });
  }

  // Refus d'écrire dans une table liée (temps, pièces, opérations) si l'OT est verrouillé ou
  // clôturé techniquement. Lit le cache : appeler via modifierLieeAOt, qui le relit juste avant.
  function verifierOtModifiable(otId) {
    const ot = Donnees.trouver('ordres_travail', otId);
    if (!ot) throw ErreurValidation(I18n.t('commun.message.ot_introuvable', { otId }));
    if (estVerrouille(ot) || ot.statut === 'Clôturé techniquement') {
      throw ErreurValidation(I18n.t('ordres.verifier_ot_modifiable.ot_sans_doute_autre', { otId, otStatut: Schema.libelleValeur('ordres_travail', 'statut', ot.statut) }));
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

  // ===========================================================================================
  // 3 bis. Clôture en une étape (ARCHITECTURE.md §22.11, D132) : réglage cloture_une_etape
  // ===========================================================================================

  // Champs de la clôture technique saisis dans la fenêtre « Clore » (mêmes champs que les onglets
  // Exécution et Compte rendu ; temps passé et pièce sortie sont écrits dans leurs tables).
  const CHAMPS_CLOTURE = ['date_fin', 'arret_production', 'duree_arret_h', 'symptome_code', 'cause_code',
    'remede_code', 'compte_rendu', 'astuce', 'remise_service'];
  const ASTUCE_MAX = 500;                     // comme l'onglet Compte rendu (Wiki.SEUILS.astuceMax)

  /** Vrai si « Clore » est proposé : réglage cloture_une_etape = 1 et profil responsable. */
  function clotureUneEtape() {
    return Ordres.interne.estResponsable() && texte(Donnees.parametre('cloture_une_etape', '0')) === '1';
  }

  // Contrôles faits AVANT toute écriture : réglage, passage possible, astuce, RG4 sur l'OT tel qu'il
  // sera (champs saisis + temps passé ajouté). Lève une ErreurValidation listant tous les manques.
  function verifierClore(ot, champs, heures) {
    if (!clotureUneEtape()) throw ErreurValidation(I18n.t('ordres.verifier_clore.cloture_etape_pas_activee'));
    if (!Ordres.transitionsPossibles(ot).includes('Clôturé techniquement')) {
      throw ErreurValidation(I18n.t('ordres.verifier_clore.ot_peut_pas_etre', { otId: ot.id, otStatut: Schema.libelleValeur('ordres_travail', 'statut', ot.statut) }));
    }
    const longueur = Array.from(champs.astuce || '').length;
    if (longueur > ASTUCE_MAX) throw ErreurValidation(I18n.t('ordres.verifier_clore.astuce_trop_longue_caracteres', { n: longueur, max: ASTUCE_MAX }));
    const temps = Ordres.interne.lignesDeLOt('ot_temps', ot.id).concat(heures > 0 ? [{ heures: String(heures) }] : []);
    const manques = Ordres.verifierCloture(Object.assign({}, ot, champs), { temps });
    if (manques.length) throw ErreurValidation(I18n.t('ordres.verifier_clore.cloture_impossible_manque', { join: manques.join(' ; ') }));
  }

  /**
   * « Clore » (D132) : clôture technique puis administrative dans une seule écriture de
   * ordres_travail, deux dates égales, deux lignes de journal, OT mis dans la file du wiki.
   * valeurs : CHAMPS_CLOTURE, et facultatifs heures + technicien_id + date_temps (temps passé),
   * article_id + quantite (pièce sortie par Magasin.sortir). Les règles de la clôture technique
   * (RG4, stock RG6) s'appliquent : tout est contrôlé avant la première écriture, puis revérifié.
   */
  async function clore(ot, valeurs) {
    await Donnees.rechargerTable('ordres_travail');
    const actuel = ligneOt(Donnees.lignes('ordres_travail'), ot.id, true);
    const champs = {};
    CHAMPS_CLOTURE.forEach((nom) => { if (valeurs[nom] !== undefined) champs[nom] = texte(valeurs[nom]); });
    const heures = Donnees.nombre(valeurs.heures) || 0;
    const quantite = Donnees.nombre(valeurs.quantite) || 0;
    if (texte(valeurs.heures) && !(heures > 0 && heures <= 24)) throw ErreurValidation(I18n.t('ordres.clore.temps_passe_nombre_heures'));
    if (heures > 0 && !texte(valeurs.technicien_id)) throw ErreurValidation(I18n.t('ordres.clore.temps_passe_choisissez_technicien'));
    if (texte(valeurs.article_id) && !(quantite > 0)) throw ErreurValidation(I18n.t('ordres.clore.piece_sortie_quantite_superieure'));
    verifierClore(actuel, champs, heures);
    const statutAttendu = actuel.statut;
    if (texte(valeurs.article_id)) await Magasin.sortir(actuel.id, valeurs.article_id, quantite, texte(valeurs.commentaire_piece));
    if (heures > 0) {
      await modifierLieeAOt(actuel.id, 'ot_temps', (lignes, outils) => {
        lignes.push({ id: outils.nouvelId(lignes), ot_id: actuel.id, technicien_id: valeurs.technicien_id,
          date: texte(valeurs.date_temps) || texte(champs.date_fin).slice(0, 10) || outils.aujourdhui(), heures: String(heures) });
      }, { action: I18n.donnees('ordres.clore.temps_passe', { actuelId: actuel.id }) });     // journal : D156
    }
    const saisis = await Donnees.modifier('ordres_travail', (lignes, outils) => {
      const ligne = ligneOt(lignes, actuel.id, true);
      if (ligne.statut !== statutAttendu) {
        throw ErreurValidation(I18n.t('ordres.clore.ot_passe_autre_poste', { actuelId: actuel.id, ligneStatut: Schema.libelleValeur('ordres_travail', 'statut', ligne.statut) }));
      }
      const changes = Object.keys(champs).filter((nom) => texte(ligne[nom]) !== champs[nom]);
      changes.forEach((nom) => { ligne[nom] = champs[nom]; });
      const technique = verifierPassage(ligne, 'Clôturé techniquement');
      if (!technique.ok) throw ErreurValidation(technique.erreurs.join(' '));
      const maintenant = outils.maintenant();          // une seule heure : les deux dates sont égales
      ligne.date_cloture_tech = maintenant;
      ligne.statut = 'Clôturé techniquement';
      const administrative = verifierPassage(ligne, 'Clôturé administrativement');
      if (!administrative.ok) throw ErreurValidation(administrative.erreurs.join(' '));
      ligne.date_cloture_admin = maintenant;
      ligne.statut = 'Clôturé administrativement';
      return changes;
    }, { journal: false });
    // Les deux lignes habituelles (celles de deux changerStatut successifs), dans l'ordre, au même format :
    // Indicateurs lit « statut A → B » après « — » (MOTIF_TRANSITION) ; aucun ajout au texte de l'action.
    await Donnees.journaliser('ordres_travail', actuel.id, 'modification : ' + saisis.concat(['statut', 'date_cloture_tech']).join(', ')
      + ' — statut ' + statutAttendu + ' → Clôturé techniquement');
    await Donnees.journaliser('ordres_travail', actuel.id, 'modification : statut, date_cloture_admin'
      + ' — statut Clôturé techniquement → Clôturé administrativement');
    await mettreAJourGamme(actuel.id);                                       // RG5, comme changerStatut
    if (typeof Wiki !== 'undefined') await Wiki.mettreEnFile([actuel.id], { annoncer: true });   // §20.5, D104
    return 'Clôturé administrativement';
  }

  // Outils prêtés aux fichiers suivants du module (usage interne).
  Object.assign(Ordres.interne, { modifierOt, modifierLieeAOt, changerAnomalie, lireAvertissementGamme });

  return {
    // écritures (ARCHITECTURE.md §10)
    creer, changerStatut, changerPriorite, creerOtLie,
    // RG8 bloquante à l'affectation (D186, D191) : aussi pour Planning.planifier
    controlerAffectation, ecrireAvecTrace,
    // clôture en une étape (§22.11, D132)
    clore, clotureUneEtape,
  };
})());
