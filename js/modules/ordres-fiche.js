'use strict';
// Ordres (4/7) — écran E5, fiche d'un OT (#/ot/<id>) : en-tête, étapes, consignation, anomalie
// d'un OT préventif et ses demandes liées (§14.6), barre d'actions (transitions RG3 avec leurs
// contrôles), messages et structure des onglets ; et l'écran de création #/ot/nouveau (manuel, ou
// d'urgence avec ?urgence=1 ; ?type= et ?titre= pré-remplissent le formulaire, §15.7). Le contenu
// des onglets est dans ordres-onglets.js et ordres-pieces.js (ARCHITECTURE.md §14.2). Complète
// l'objet Ordres.

Object.assign(Ordres, (() => {

  // Constantes, outils, règles et écritures des fichiers précédents (ordres-regles.js à ordres-liste.js).
  const { PRIORITES, transitionsPossibles, verifierPassage, verifierHabilitation,
    piecesManquantes, estVerrouille, datePrevueParDefaut, libelleEquipement, nomTechnicien,
    creer, changerStatut, changerPriorite, creerOtLie } = Ordres;
  const { ETAPES, STATUTS_CLOTURES, memoire, texte, aujourdhui, estResponsable, estTechnicien,
    equipementDe, repereEquipement, cheminLocalisation, listeTechniciens, placerChamp, champOt,
    statutDeReprise, habilitationsManquantes, journaliserHabilitation, optionsHtml, badgeRetard,
    badgeAnomalie, origineHtml, changerAnomalie, lireAvertissementGamme, detailManque } = Ordres.interne;

  // Fonctions des fichiers chargés APRÈS celui-ci (ordres-onglets.js, ordres-impression.js) :
  // elles sont cherchées au moment de l'appel, pas au chargement de ce fichier.
  const afficherPreparation = (panneau, ot) => Ordres.interne.afficherPreparation(panneau, ot);
  const afficherExecution = (panneau, ot) => Ordres.interne.afficherExecution(panneau, ot);
  const afficherCompteRendu = (panneau, ot) => Ordres.interne.afficherCompteRendu(panneau, ot);
  const afficherHistorique = (panneau, ot) => Ordres.interne.afficherHistorique(panneau, ot);
  const imprimerBon = (otId) => Ordres.imprimerBon(otId);

  // Formulaires de la fiche affichée : { formulaire, enregistrer } (vidé à chaque affichage).
  let formulairesFiche = [];

  // ===========================================================================================
  // 5. Nouvel OT (#/ot/nouveau, ?equipement=EQ-0005, ?urgence=1, ?type=, ?titre=)
  // ===========================================================================================

  /**
   * Type proposé par l'adresse (?type=réglementaire, lien « Créer un OT » d'un contrôle
   * réglementaire, §15.7) s'il fait partie de la liste des types d'OT, sinon « correctif différé ».
   */
  function typeDemande(requete) {
    const demande = (requete.get('type') || '').trim();
    return Schema.champ('ordres_travail', 'type').valeurs.includes(demande) ? demande : 'correctif différé';
  }

  function afficherNouveau(conteneur, parametres) {
    const requete = parametres.requete || new URLSearchParams('');
    const urgence = requete.get('urgence') === '1';
    const priorite = urgence ? 'P1' : 'P3';
    // Titre pré-rempli par l'adresse (?titre=…), toujours modifiable avant la création.
    const titre = (requete.get('titre') || '').trim();
    App.definirTitre(urgence ? I18n.t('ordres.nouveau.ot_urgence') : I18n.t('ordres.nouveau.nouvel_ot'));
    UI.remplir(conteneur, UI.html`
      <div class="entete-page"><div>
        <div class="fil">${I18n.html('ordres.nouveau.ordres_travail')} <span>${urgence ? I18n.t('ordres.nouveau.ot_urgence') : I18n.t('ordres.nouveau.nouvel_ot')}</span></div>
        <h1>${urgence ? I18n.t('ordres.nouveau.ot_urgence') : I18n.t('ordres.nouveau.nouvel_ordre_travail')}</h1>
        <p>${urgence ? I18n.t('ordres.nouveau.correctif_immediat_priorite_p') : I18n.t('ordres.nouveau.ot_cree_main_origine')}</p>
      </div></div>
      <form class="carte form-grille" id="form-nouvel-ot" novalidate>
        <div class="champ large"><span class="libelle">${I18n.t('commun.champ.equipement')} <span class="requis" aria-hidden="true">*</span></span>
          <div id="ot-nouveau-equipement"></div><p class="erreur-champ" id="ot-nouveau-equipement-erreur" hidden></p></div>
        <div class="large" data-place="titre"></div>
        <div data-place="type"></div><div data-place="priorite"></div>
        <div class="large" data-place="travail_a_faire"></div>
        <div data-place="technicien_id"></div><div data-place="date_prevue"></div>
        <div class="large ot-zone-habilitation"></div>
        <div class="actions">
          <a class="btn btn-fantome" href="#/ot">${I18n.t('commun.bouton.annuler')}</a><span class="espace"></span>
          <button type="submit" class="btn ${urgence ? 'btn-danger' : 'btn-primaire'}">${UI.icone('valider')}${urgence ? I18n.t('ordres.nouveau.creer_ot_urgence') : I18n.t('ordres.nouveau.creer_ot')}</button>
        </div>
      </form>`);
    if (urgence) {
      conteneur.insertBefore(UI.bandeau('securite', UI.html`${I18n.html('ordres.nouveau.intervention_urgence_mettez_zone')}`), UI.$('#form-nouvel-ot', conteneur));
    }
    const formulaire = UI.$('#form-nouvel-ot', conteneur);
    const placer = (nom, element) => placerChamp(formulaire, nom, element);
    placer('titre', champOt('titre', titre, { placeholder: I18n.t('ordres.nouveau.ex_po_02_fuite') }));
    placer('type', champOt('type', urgence ? 'correctif immédiat' : typeDemande(requete), { lectureSeule: urgence }));
    placer('priorite', champOt('priorite', priorite, { lectureSeule: urgence }));
    placer('travail_a_faire', champOt('travail_a_faire', ''));
    // Mode Solo (D132) : le technicien « moi » est pré-rempli (toujours modifiable) ; '' sinon.
    const technicienParDefaut = App.technicienSolo();
    placer('technicien_id', champOt('technicien_id', technicienParDefaut, { liste: listeTechniciens(technicienParDefaut) }));
    placer('date_prevue', champOt('date_prevue', datePrevueParDefaut(priorite), { aide: I18n.t('ordres.nouveau.defaut_creation_delai_priorite') }));

    const selecteur = UI.selecteurEquipement(UI.$('#ot-nouveau-equipement', formulaire), {
      equipements: Donnees.lignes('equipements'), localisations: Donnees.lignes('localisations'),
      valeur: requete.get('equipement') || '', surChoix: () => montrerHabilitationNouvelOt(formulaire, selecteur),
    });
    montrerHabilitationNouvelOt(formulaire, selecteur);
    formulaire.addEventListener('change', (evenement) => {
      if (evenement.target.name === 'priorite') {
        const champDate = UI.$('[name="date_prevue"]', formulaire);
        champDate.value = datePrevueParDefaut(evenement.target.value);
      }
      montrerHabilitationNouvelOt(formulaire, selecteur);
    });
    formulaire.addEventListener('submit', (evenement) => {
      evenement.preventDefault();
      validerNouvelOt(formulaire, selecteur, urgence);
    });
  }

  function montrerHabilitationNouvelOt(formulaire, selecteur) {
    const valeurs = UI.lireFormulaire(formulaire);
    const zone = UI.$('.ot-zone-habilitation', formulaire);
    zone.textContent = '';
    const message = verifierHabilitation(selecteur.valeur(), valeurs.technicien_id, valeurs.date_prevue);
    if (message) zone.appendChild(bandeauHabilitation(selecteur.valeur(), valeurs.technicien_id, valeurs.date_prevue));
  }

  async function validerNouvelOt(formulaire, selecteur, urgence) {
    const erreurs = UI.verifierFormulaire(formulaire);
    const erreurEquipement = UI.$('#ot-nouveau-equipement-erreur', formulaire);
    erreurEquipement.hidden = Boolean(selecteur.valeur());
    erreurEquipement.textContent = selecteur.valeur() ? '' : I18n.t('ordres.valider_nouvel_ot.choisissez_equipement_concerne');
    if (erreurs.length || !selecteur.valeur()) return;
    const valeurs = UI.lireFormulaire(formulaire);
    const bouton = UI.$('button[type=submit]', formulaire);
    bouton.disabled = true;
    try {
      const id = await creer({
        origine: urgence ? 'urgence' : 'manuel', equipement_id: selecteur.valeur(), titre: valeurs.titre,
        type: urgence ? 'correctif immédiat' : valeurs.type, priorite: urgence ? 'P1' : valeurs.priorite,
        travail_a_faire: valeurs.travail_a_faire, technicien_id: valeurs.technicien_id, date_prevue: valeurs.date_prevue,
      });
      const habilitation = verifierHabilitation(selecteur.valeur(), valeurs.technicien_id, valeurs.date_prevue, true);   // journal (D156)
      if (habilitation) await journaliserHabilitation(id, habilitation);
      App.marquerSaisie(false);
      UI.toast(I18n.t('ordres.valider_nouvel_ot.ordre_travail_cree', { id }), 'succes');
      App.naviguer('#/ot/' + encodeURIComponent(id));
    } catch (erreur) {
      App.signalerErreur(erreur, 'création d\'un OT');
      bouton.disabled = false;
    }
  }

  // ===========================================================================================
  // 6. Fiche OT (#/ot/<id>) : en-tête, étapes, consignation, actions, messages
  // ===========================================================================================

  const LIBELLES_ACTION = {
    'Préparé': (ot) => (ot.statut === 'Planifié' ? I18n.t('ordres.prepare.deplanifier') : ot.statut === 'En attente' ? I18n.t('ordres.prepare.reprendre_prepare') : I18n.t('ordres.prepare.marquer_prepare')),
    'Planifié': () => I18n.t('ordres.planifie.planifier'),
    'En cours': (ot) => (ot.statut === 'Clôturé techniquement' ? I18n.t('ordres.en_cours.rouvrir') : ot.statut === 'En attente' ? I18n.t('ordres.en_cours.reprendre_cours') : I18n.t('ordres.en_cours.demarrer')),
    'En attente': () => I18n.t('ordres.en_attente.mettre_attente'),
    'Annulé': () => I18n.t('ordres.annule.annuler_ot'),
    'Clôturé techniquement': () => I18n.t('ordres.cloture_techniquement.cloturer_techniquement'),
    'Clôturé administrativement': () => I18n.t('ordres.cloture_administrativement.cloturer_administrativement'),
  };

  /** Le profil courant peut-il demander ce passage ? (technicien : démarrer, attente, clôture technique) */
  function actionAutorisee(ot, cible) {
    if (estResponsable()) return true;
    if (!estTechnicien()) return false;
    if (cible === 'En cours') return ot.statut !== 'Clôturé techniquement';   // rouvrir : responsable
    return cible === 'En attente' || cible === 'Clôturé techniquement';
  }

  function classeAction(cible) {
    if (cible === 'Annulé') return 'btn-danger';
    if (cible === 'En attente' || cible === 'Préparé') return 'btn-secondaire';
    return 'btn-primaire';
  }

  function boutonTransition(ot, cible) {
    return UI.html`<button type="button" class="btn ${classeAction(cible)}" data-action="transition" data-cible="${cible}">${LIBELLES_ACTION[cible](ot)}</button>`;
  }

  function boutonsTransitions(ot, cibles) {
    return cibles.filter((cible) => transitionsPossibles(ot).includes(cible) && actionAutorisee(ot, cible))
      .map((cible) => boutonTransition(ot, cible));
  }

  function etapesHtml(ot) {
    const reference = ot.statut === 'En attente' ? statutDeReprise(ot) : ot.statut;
    let rangCourant = ETAPES.indexOf(reference);
    if (ot.statut === 'Annulé') rangCourant = -1;
    const horsEtape = ot.statut === 'En attente' || ot.statut === 'Annulé';
    return UI.html`<ol class="etapes ot-etapes" aria-label="${I18n.t('ordres.etapes.avancement_ot')}">
      ${ETAPES.map((etape, rang) => {
        let classe = '';
        if (rang < rangCourant || (rang === rangCourant && horsEtape)) classe = 'fait';
        if (rang === rangCourant && !horsEtape) classe = 'courant';
        return UI.html`<li class="${classe}"${classe === 'courant' ? UI.brut(' aria-current="step"') : ''}>${Schema.libelleValeur('ordres_travail', 'statut', etape)}</li>`;
      })}
      ${horsEtape ? UI.html`<li class="hors" aria-current="step">${Schema.libelleValeur('ordres_travail', 'statut', ot.statut)}</li>` : ''}
    </ol>`;
  }

  function enteteFicheHtml(ot) {
    const equipement = equipementDe(ot);
    return UI.html`
      <div class="entete-page ot-entete">
        <div>
          <div class="fil">${I18n.html('ordres.entete_fiche.ordres_travail', { otId: ot.id })}</div>
          <h1><span class="ot-numero">${ot.id}</span> ${ot.titre}</h1>
          <div class="ot-badges">${UI.badgePriorite(ot.priorite)} ${UI.badgeValeur('ordres_travail', 'statut', ot.statut)}${badgeRetard(ot)}${badgeAnomalie(ot)}
            <span class="badge neutre">${Schema.libelleValeur('ordres_travail', 'type', ot.type)}</span>
            ${equipement ? UI.html`<a class="ot-lien-equipement" href="#/equipement/${encodeURIComponent(equipement.id)}">${libelleEquipement(equipement.id)}</a>` : ''}
          </div>
        </div>
        <div class="actions">
          ${estResponsable() && !estVerrouille(ot) ? UI.html`<button type="button" class="btn btn-fantome" id="ot-priorite">${UI.icone('alerte')}${I18n.t('ordres.fiche.bouton_priorite')}</button>` : ''}
          <button type="button" class="btn btn-secondaire" id="ot-imprimer">${UI.icone('imprimer')}${I18n.t('ordres.entete_fiche.imprimer_bon_travail')}</button>
        </div>
      </div>`;
  }

  function lienOt(id) {
    return UI.html`<a href="#/ot/${encodeURIComponent(id)}">${id}</a>`;
  }

  function reperesHtml(ot) {
    const lies = Donnees.lignes('ordres_travail').filter((autre) => autre.ot_lie_id === ot.id);
    return UI.html`<dl class="valeurs">
      <dt>${I18n.t('ordres.reperes.origine')}</dt><dd>${origineHtml(ot)}${ot.gamme_id ? UI.html` ${I18n.t('ordres.reperes.gamme_gamme_id', { gamme_id: ot.gamme_id })}` : ''}</dd>
      <dt>${I18n.t('commun.champ.technicien')}</dt><dd>${nomTechnicien(ot.technicien_id)}</dd>
      <dt>${I18n.t('ordres.reperes.cree')}</dt><dd>${UI.dateHeureFr(ot.date_creation)}</dd>
      <dt>${I18n.t('ordres.reperes.prevu')}</dt><dd>${UI.dateFr(ot.date_prevue)}${badgeRetard(ot)}</dd>
      <dt>${I18n.t('ordres.reperes.temps_prevu')}</dt><dd>${ot.temps_prevu_h ? UI.heures(ot.temps_prevu_h) : ''}</dd>
      <dt>${I18n.t('ordres.reperes.debut_fin')}</dt><dd>${UI.dateHeureFr(ot.date_debut)}${ot.date_fin ? ' → ' + UI.dateHeureFr(ot.date_fin) : ''}</dd>
      ${ot.date_cloture_tech ? UI.html`<dt>${I18n.t('ordres.reperes.cloture_technique')}</dt><dd>${UI.dateHeureFr(ot.date_cloture_tech)}</dd>` : ''}
      ${ot.date_cloture_admin ? UI.html`<dt>${I18n.t('ordres.reperes.cloture_administrative')}</dt><dd>${UI.dateHeureFr(ot.date_cloture_admin)}</dd>` : ''}
      ${ot.ot_lie_id ? UI.html`<dt>${I18n.t('ordres.reperes.reprend_ot')}</dt><dd>${lienOt(ot.ot_lie_id)}</dd>` : ''}
      ${lies.length ? UI.html`<dt>${I18n.t('ordres.reperes.repris')}</dt><dd>${lies.map((l, rang) => UI.html`${rang ? ', ' : ''}${lienOt(l.id)}`)}</dd>` : ''}
    </dl>`;
  }

  function equipementHtml(equipement) {
    if (!equipement) return UI.html`<p class="muted">${I18n.t('ordres.equipement.equipement_introuvable')}</p>`;
    return UI.html`<dl class="valeurs">
      <dt>${I18n.t('commun.champ.repere')}</dt><dd><a href="#/equipement/${encodeURIComponent(equipement.id)}">${equipement.repere || equipement.id}</a></dd>
      <dt>${I18n.t('commun.champ.designation')}</dt><dd>${equipement.designation}</dd>
      <dt>${I18n.t('ordres.equipement.localisation')}</dt><dd>${cheminLocalisation(equipement.localisation_id)}</dd>
      <dt>${I18n.t('commun.champ.criticite')}</dt><dd>${Schema.libelleValeur('equipements', 'criticite', equipement.criticite)}</dd>
      <dt>${I18n.t('ordres.equipement.etat')}</dt><dd>${equipement.statut ? UI.badgeValeur('equipements', 'statut', equipement.statut) : ''}</dd>
      <dt>${I18n.t('ordres.equipement.habilitation_requise')}</dt><dd>${equipement.habilitation_requise || I18n.t('ordres.equipement.aucune_habilitation')}</dd>
    </dl>`;
  }

  /** Bloc consignation (RG4) : procédure de l'équipement + rappel « Cocher une case ne consigne rien ». */
  function consignationHtml(equipement) {
    const procedure = texte(equipement && equipement.consignation);
    return UI.html`<section class="carte ot-consignation" aria-labelledby="ot-titre-consignation">
      <div class="entete-carte"><h2 id="ot-titre-consignation">${UI.icone('cle')} ${I18n.t('ordres.consignation.consignation_equipement')}</h2></div>
      ${procedure ? UI.html`<div class="ot-procedure">${procedure}</div>`
        : UI.html`<p class="muted">${I18n.t('ordres.consignation.aucune_procedure_consignation_renseignee')}</p>`}
      <p class="ot-rappel"><b>${Ordres.rappelConsignation()}</b></p>
    </section>`;
  }

  // --- OT préventif : anomalie constatée et demandes liées (ARCHITECTURE.md §14.6) ----------

  /** Demandes signalées pendant cet OT (demandes.ot_origine_id), les plus récentes d'abord. */
  function demandesLiees(ot) {
    return Donnees.lignes('demandes').filter((di) => di.ot_origine_id === ot.id)
      .sort((a, b) => texte(b.date_heure).localeCompare(texte(a.date_heure)) || b.id.localeCompare(a.id));
  }

  /**
   * Carte d'un OT préventif : case « Anomalie constatée » (désactivée si l'OT est verrouillé),
   * bouton « Signaler une anomalie (DI liée) » (absent si verrouillé) et demandes liées.
   * data-hors-saisie : la case s'enregistre aussitôt, ce n'est pas une saisie en cours.
   */
  function anomalieHtml(ot) {
    if (ot.origine !== 'préventif') return '';
    const verrouille = estVerrouille(ot);
    const liees = demandesLiees(ot);
    const adresse = '#/di/nouvelle?equipement=' + encodeURIComponent(ot.equipement_id) + '&ot=' + encodeURIComponent(ot.id);
    return UI.html`<section class="carte ot-anomalie sans-impression" data-hors-saisie aria-labelledby="ot-titre-anomalie">
      <div class="entete-carte"><h2 id="ot-titre-anomalie">${I18n.t('ordres.anomalie.anomalie_pendant_preventif')}</h2>
        ${verrouille ? UI.html`<span class="aide">${I18n.t('ordres.anomalie.ot_verrouille_lecture_seule')}</span>` : ''}</div>
      <label class="case"><input type="checkbox" id="ot-anomalie-constatee"${ot.anomalie_constatee === '1' ? UI.brut(' checked') : ''}${verrouille ? UI.brut(' disabled') : ''}>
        <span>${I18n.t('ordres.anomalie.anomalie_constatee')}</span></label>
      ${verrouille ? '' : UI.html`<p class="aide">${I18n.t('ordres.anomalie.anomalie_traiter_signale_demande')}</p>
        <div class="actions"><a class="btn btn-secondaire" id="ot-signaler-anomalie" href="${adresse}">${UI.icone('alerte')}${I18n.t('ordres.anomalie.signaler_anomalie_di_liee')}</a></div>`}
      <h3 class="ot-sous-titre">${I18n.t('ordres.anomalie.demandes_liees', { nbLiees: liees.length })}</h3>
      ${liees.length ? UI.html`<ul class="ot-di-liees">${liees.map((di) => UI.html`<li>
          <a href="#/di/${encodeURIComponent(di.id)}">${di.id}</a> ${UI.badgeValeur('demandes', 'statut', di.statut)} <span>${di.symptome}</span></li>`)}</ul>`
        : UI.html`<p class="muted">${I18n.t('ordres.anomalie.aucune_demande_liee_ot')}</p>`}
    </section>`;
  }

  /** Case « Anomalie constatée » : enregistrée aussitôt ; remise comme avant si l'écriture est refusée. */
  async function basculerAnomalie(ot, caseAnomalie) {
    const coche = caseAnomalie.checked;
    const reussi = await pendant(caseAnomalie, () => changerAnomalie(ot.id, coche), I18n.t('ordres.basculer_anomalie.anomalie_constatee'));
    if (reussi === undefined) { caseAnomalie.checked = !coche; return; }
    await apresEnregistrement();
    UI.toast(ot.id + (coche ? ' ' + I18n.t('ordres.basculer_anomalie.phrase_anomalie_constatee') : ' ' + I18n.t('ordres.basculer_anomalie.mention_anomalie_constatee_retiree')), 'succes');
  }

  function bandeauEtat(ot) {
    if (ot.statut === 'En attente') return UI.bandeau('attention', UI.html`${I18n.html('ordres.bandeau_etat.attente', { motif: ot.motif_attente || I18n.t('ordres.bandeau_etat.motif_non_renseigne') })}`);
    if (ot.statut === 'Annulé') return UI.bandeau('important', UI.html`${I18n.html('ordres.bandeau_etat.ot_annule_reste_consultable', { motif: ot.motif_annulation || I18n.t('ordres.bandeau_etat.motif_non_renseigne') })}`);
    if (ot.statut === 'Clôturé administrativement') {
      return UI.bandeau('info', UI.html`${I18n.html('ordres.bandeau_etat.ot_verrouille_cloture_administrativement', { date_cloture_admin: UI.dateHeureFr(ot.date_cloture_admin) })}`);
    }
    return null;
  }

  function actionsHtml(ot) {
    const boutons = boutonsTransitions(ot, ['Préparé', 'Planifié', 'En cours', 'Clôturé techniquement', 'Clôturé administrativement', 'En attente', 'Annulé']);
    const lie = estVerrouille(ot) && estResponsable()
      ? UI.html`<button type="button" class="btn btn-primaire" id="ot-lie">${UI.icone('ajouter')}${I18n.t('ordres.actions.creer_ot_lie')}</button>` : '';
    const clore = boutonClore(ot);                                  // §22.11, D132 : réglage cloture_une_etape
    if (!boutons.length && !lie && !clore) return '';
    return UI.html`<div class="carte ot-actions sans-impression"><div class="entete-carte"><h2>${I18n.t('ordres.actions.actions')}</h2></div>
      <div class="actions">${clore}${boutons}${lie}</div></div>`;
  }

  /** Affiche un message (refus, manques…) au-dessus des onglets et le fait voir. */
  function afficherMessage(type, contenu) {
    const zone = UI.$('#ot-message');
    if (!zone) { UI.toast(String(contenu), type === 'important' ? 'erreur' : 'attention'); return null; }
    zone.textContent = '';
    const bandeau = UI.bandeau(type, contenu);
    zone.appendChild(bandeau);
    if (typeof zone.scrollIntoView === 'function') zone.scrollIntoView({ block: 'nearest' });
    return bandeau;
  }

  function viderMessage() {
    const zone = UI.$('#ot-message');
    if (zone) zone.textContent = '';
  }

  function ongletParDefaut(ot) {
    if (['En cours', 'En attente'].includes(ot.statut)) return 'execution';
    if (STATUTS_CLOTURES.includes(ot.statut) || ot.statut === 'Annulé') return 'compte-rendu';
    return 'preparation';
  }

  function afficherFiche(conteneur, parametres) {
    formulairesFiche = [];
    const ot = Donnees.trouver('ordres_travail', parametres.id);
    if (!ot) {
      UI.remplir(conteneur, UI.html`<div class="entete-page"><div><div class="fil">${I18n.html('ordres.fiche.ordres_travail', { parametresId: parametres.id })}</div><h1>${I18n.t('ordres.fiche.ordre_travail', { parametresId: parametres.id })}</h1></div></div>
        ${UI.vide(I18n.t('ordres.fiche.ordre_travail_introuvable'), I18n.t('ordres.fiche.aucun_ot_porte_identifiant'), 'ordres')}`);
      return;
    }
    App.definirTitre(ot.id);
    const equipement = equipementDe(ot);
    // Racine neuve à chaque affichage : #contenu est réutilisé, ses écouteurs s'accumuleraient.
    const racine = document.createElement('div');
    racine.className = 'ot-fiche';
    UI.remplir(conteneur, racine);
    UI.remplir(racine, UI.html`
      ${enteteFicheHtml(ot)}
      ${etapesHtml(ot)}
      <div class="ot-bandeau-etat"></div>
      <div class="grille">
        <section class="carte c6"><h2>${I18n.t('ordres.fiche.equipement')}</h2>${equipementHtml(equipement)}</section>
        <section class="carte c6"><h2>${I18n.t('ordres.fiche.reperes')}</h2>${reperesHtml(ot)}</section>
      </div>
      ${consignationHtml(equipement)}
      ${anomalieHtml(ot)}
      ${actionsHtml(ot)}
      <div id="ot-message" class="ot-message" aria-live="polite"></div>
      <div class="ot-onglets"></div>`);
    const etat = bandeauEtat(ot);
    if (etat) UI.$('.ot-bandeau-etat', racine).appendChild(etat);

    UI.onglets(UI.$('.ot-onglets', racine), [
      { id: 'preparation', libelle: I18n.t('ordres.fiche.preparation'), afficher: (panneau) => afficherPreparation(panneau, ot) },
      { id: 'execution', libelle: I18n.t('ordres.fiche.execution'), afficher: (panneau) => afficherExecution(panneau, ot) },
      { id: 'compte-rendu', libelle: I18n.t('ordres.fiche.compte_rendu'), afficher: (panneau) => afficherCompteRendu(panneau, ot) },
      { id: 'historique', libelle: I18n.t('ordres.fiche.historique_equipement'), afficher: (panneau) => afficherHistorique(panneau, ot) },
    ], { actif: memoire.ongletParOt[ot.id] || ongletParDefaut(ot), libelle: I18n.t('ordres.fiche.parties_ordre_travail'),
      surChangement: (id) => { memoire.ongletParOt[ot.id] = id; } });

    brancherActionsFiche(racine, ot);
  }

  function brancherActionsFiche(racine, ot) {
    racine.addEventListener('click', (evenement) => {
      const bouton = evenement.target.closest('button[data-action="transition"]');
      if (bouton) { demanderTransition(ot, bouton.dataset.cible, bouton); return; }
      if (evenement.target.closest('#ot-imprimer')) imprimerBon(ot.id);
      if (evenement.target.closest('#ot-priorite')) demanderPriorite(ot);
      if (evenement.target.closest('#ot-lie')) lancerOtLie(ot);
      if (evenement.target.closest('#ot-clore')) demanderClore(ot);
      const attentePiece = evenement.target.closest('button[data-action="attente-piece"]');
      if (attentePiece) mettreEnAttentePiece(ot);
    });
    const caseAnomalie = UI.$('#ot-anomalie-constatee', racine);
    if (caseAnomalie) caseAnomalie.addEventListener('change', () => basculerAnomalie(ot, caseAnomalie));
  }

  // --- Formulaires de la fiche : enregistrés avant une transition s'ils ont été modifiés ------

  /** Déclare un formulaire de la fiche : `enregistrer()` renvoie true si l'enregistrement a réussi. */
  function declarerFormulaire(formulaire, enregistrer) {
    const marquer = () => { formulaire.dataset.modifie = '1'; };
    formulaire.addEventListener('input', marquer);
    formulaire.addEventListener('change', marquer);
    formulairesFiche.push({ formulaire, enregistrer });
  }

  /** Enregistre les formulaires modifiés (sans réafficher). Renvoie { ok, enregistres }. */
  async function enregistrerFormulairesModifies() {
    let enregistres = 0;
    for (const entree of formulairesFiche) {
      if (entree.formulaire.dataset.modifie !== '1' || !document.contains(entree.formulaire)) continue;
      const reussi = await entree.enregistrer();
      if (!reussi) return { ok: false, enregistres };
      entree.formulaire.dataset.modifie = '0';
      enregistres += 1;
    }
    return { ok: true, enregistres };
  }

  /**
   * Réaffiche la fiche après un enregistrement (saisie terminée, défilement conservé). Les autres
   * blocs modifiés mais pas encore enregistrés le sont d'abord : le réaffichage ne doit perdre
   * aucune saisie (ex. « Travail à faire » tapé avant « Enregistrer les pièces »). Si l'un d'eux est
   * refusé, la fiche n'est pas réaffichée : la saisie reste à l'écran avec son message.
   */
  async function apresEnregistrement() {
    const autres = await enregistrerFormulairesModifies();
    if (!autres.ok) return;
    App.marquerSaisie(false);
    await App.reafficher();
  }

  // Exécute une écriture : bouton désactivé pendant l'action, erreur affichée proprement.
  async function pendant(bouton, action, contexte) {
    if (bouton) bouton.disabled = true;
    try {
      return await action();
    } catch (erreur) {
      App.signalerErreur(erreur, contexte);
      return undefined;
    } finally {
      if (bouton && document.contains(bouton)) bouton.disabled = false;
    }
  }

  function listeErreursHtml(titre, erreurs) {
    return UI.html`<b>${titre}</b><ul class="ot-manques">${erreurs.map((e) => UI.html`<li>${e}</li>`)}</ul>`;
  }

  /** Clic sur un bouton de transition : motifs, enregistrement des saisies, contrôles, écriture. */
  async function demanderTransition(ot, cible, bouton) {
    viderMessage();
    const sauvegarde = await enregistrerFormulairesModifies();
    if (!sauvegarde.ok) return;
    const actuel = Donnees.trouver('ordres_travail', ot.id) || ot;
    const complement = await demanderComplement(actuel, cible);
    if (complement === null) { if (sauvegarde.enregistres) await apresEnregistrement(); return; }
    const verification = verifierPassage(Object.assign({}, actuel, complement), cible);
    if (!verification.ok) {
      if (sauvegarde.enregistres) await apresEnregistrement();
      afficherRefus(actuel, cible, verification);
      return;
    }
    if (cible === 'Clôturé administrativement' && !(await UI.confirmer(
      I18n.t('ordres.demander_transition.ot_sera_verrouille_plus', { actuelId: actuel.id }),
      { titre: I18n.t('ordres.cloture_administrativement.cloturer_administrativement'), oui: I18n.t('ordres.demander_transition.cloturer_verrouiller') }))) return;
    const reussi = await pendant(bouton, () => changerStatut(actuel.id, actuel.statut, cible, complement), I18n.t('ordres.demander_transition.changement_statut'));
    if (reussi === undefined) return;
    await apresEnregistrement();
    // Clôture d'un préventif dont la gamme n'a pas pu être mise à jour (RG5) : l'avertissement
    // reste affiché au-dessus des onglets, et le toast le redit au lieu du succès.
    const avertissementGamme = lireAvertissementGamme(actuel.id);
    UI.toast(avertissementGamme || actuel.id + ' : ' + Schema.libelleValeur('ordres_travail', 'statut', cible) + '.', avertissementGamme ? 'attention' : 'succes');
    const avertissements = verification.avertissements.concat(avertissementGamme ? [avertissementGamme] : []);
    if (avertissements.length) afficherMessage('attention', avertissements.join(' '));
  }

  // Motif demandé pour En attente et Annulé : { motif_… } ; null si l'utilisateur renonce.
  async function demanderComplement(ot, cible) {
    if (cible === 'En attente') {
      const motif = await UI.demanderMotif(I18n.t('ordres.demander_complement.mettre_attente', { otId: ot.id }), I18n.t('ordres.demander_complement.motif_mise_attente'), { exemple: I18n.t('ordres.demander_complement.ex_piece_commande_attente') });
      return motif === null ? null : { motif_attente: motif };
    }
    if (cible === 'Annulé') {
      const motif = await UI.demanderMotif(I18n.t('ordres.demander_complement.annuler_ot_id', { otId: ot.id }), I18n.t('ordres.demander_complement.motif_annulation'), { libelleValider: I18n.t('ordres.annule.annuler_ot') });
      return motif === null ? null : { motif_annulation: motif };
    }
    return {};
  }

  function afficherRefus(ot, cible, verification) {
    const titre = cible === 'Clôturé techniquement'
      ? I18n.t('ordres.refus.cloture_technique_impossible_statut', { otStatut: Schema.libelleValeur('ordres_travail', 'statut', ot.statut) })
      : I18n.t('ordres.refus.passage_refuse_statut_reste', { cible: Schema.libelleValeur('ordres_travail', 'statut', cible), otStatut: Schema.libelleValeur('ordres_travail', 'statut', ot.statut) });
    const bandeau = afficherMessage('important', listeErreursHtml(titre, verification.erreurs));
    if (bandeau && verification.piecesManquantes.length && transitionsPossibles(ot).includes('En attente') && actionAutorisee(ot, 'En attente')) {
      bandeau.querySelector('.alerte-texte').appendChild(UI.element(UI.html`<div class="actions">
        <button type="button" class="btn btn-secondaire" data-action="attente-piece">${I18n.t('ordres.refus.mettre_attente_motif_piece')}</button></div>`));
    }
  }

  // Début du motif de mise en attente pour pièce (D156) : écrit dans les données et relu par le code (RG3,
  // indicateurs) ; jamais traduit, seul le détail qui suit l'est.
  const MARQUEUR_PIECE = 'Pièce : ';

  /** RG3 : stock insuffisant → mise en attente avec un motif « Pièce : … » prérempli (modifiable). */
  async function mettreEnAttentePiece(ot) {
    const actuel = Donnees.trouver('ordres_travail', ot.id) || ot;
    const manquantes = piecesManquantes(actuel.id);
    const proposition = MARQUEUR_PIECE + I18n.enLangueDesDonnees(() => (manquantes.length      // motif pré-rempli (D156)
      ? manquantes.map((p) => p.libelle + ' (' + detailManque(p) + ')').join(' ; ')
      : I18n.donnees('ordres.mettre_en_attente_piece.stock_insuffisant'))) + '.';
    const motif = await UI.demanderMotif(I18n.t('ordres.mettre_en_attente_piece.mettre_attente', { actuelId: actuel.id }), I18n.t('ordres.demander_complement.motif_mise_attente'), { valeur: proposition });
    if (motif === null) return;
    const reussi = await pendant(null, () => changerStatut(actuel.id, actuel.statut, 'En attente', { motif_attente: motif }), I18n.t('ordres.mettre_en_attente_piece.mise_attente'));
    if (reussi === undefined) return;
    await apresEnregistrement();
    UI.toast(I18n.t('ordres.mettre_en_attente_piece.actuel_id_attente', { actuelId: actuel.id }), 'succes');
  }

  async function demanderPriorite(ot) {
    const contenu = UI.element(UI.html`<div class="form-colonne">
      <p>${I18n.t('ordres.demander_priorite.priorite_actuelle')} ${UI.badgePriorite(ot.priorite)}${I18n.t('ordres.demander_priorite.changement_trace_journal_motif')}</p>
      <div class="champ"><label class="libelle" for="ot-nouvelle-priorite">${I18n.t('ordres.demander_priorite.nouvelle_priorite')}</label>
        <select id="ot-nouvelle-priorite">${optionsHtml(PRIORITES.map((p) => ({ valeur: p, libelle: Schema.libelleValeur('ordres_travail', 'priorite', p) })), ot.priorite)}</select></div>
      <div class="champ"><label class="libelle" for="ot-motif-priorite">${I18n.t('ordres.demander_priorite.motif')} <span class="requis" aria-hidden="true">*</span></label>
        <textarea id="ot-motif-priorite" rows="3" data-dictee required aria-required="true"></textarea>
        <p class="erreur-champ" hidden></p></div></div>`);
    const choix = await UI.fenetre({
      titre: I18n.t('ordres.demander_priorite.modifier_priorite', { otId: ot.id }), contenu,
      boutons: [{ libelle: I18n.t('commun.bouton.annuler'), valeur: null, classe: 'btn-fantome' }, { libelle: I18n.t('commun.bouton.enregistrer'), valeur: 'ok', classe: 'btn-primaire', defaut: true }],
      avantFermeture() {
        const erreur = UI.$('.erreur-champ', contenu);
        let message = '';
        if (UI.$('#ot-nouvelle-priorite', contenu).value === ot.priorite) message = I18n.t('ordres.demander_priorite.choisissez_priorite_differente_actuelle');
        else if (!UI.$('#ot-motif-priorite', contenu).value.trim()) message = I18n.t('ordres.demander_priorite.motif_obligatoire');
        erreur.textContent = message;
        erreur.hidden = !message;
        return !message;
      },
    });
    if (choix !== 'ok') return;
    const nouvelle = UI.$('#ot-nouvelle-priorite', contenu).value;
    const motif = UI.$('#ot-motif-priorite', contenu).value.trim();
    const reussi = await pendant(null, () => changerPriorite(ot.id, nouvelle, motif), I18n.t('ordres.demander_priorite.changement_priorite'));
    if (reussi === undefined) return;
    await apresEnregistrement();
    UI.toast(I18n.t('ordres.demander_priorite.priorite_enregistree', { priorite: Schema.libelleValeur('ordres_travail', 'priorite', ot.priorite), nouvelle: Schema.libelleValeur('ordres_travail', 'priorite', nouvelle) }), 'succes');
  }

  async function lancerOtLie(ot) {
    const id = await pendant(UI.$('#ot-lie'), () => creerOtLie(ot.id), I18n.t('ordres.lancer_ot_lie.creation_ot_lie'));
    if (!id) return;
    UI.toast(I18n.t('ordres.lancer_ot_lie.ot_lie_cree_reprise', { id, otId: ot.id }), 'succes');
    App.naviguer('#/ot/' + encodeURIComponent(id));
  }

  // --- Clôture en une étape (ARCHITECTURE.md §22.11, D132) : « Clore », réglage cloture_une_etape ---

  /** Bouton « Clore » : réglage actif, profil responsable, OT qui peut recevoir la clôture technique. */
  function boutonClore(ot) {
    return Ordres.clotureUneEtape() && transitionsPossibles(ot).includes('Clôturé techniquement')
      ? UI.html`<button type="button" class="btn btn-primaire" id="ot-clore">${UI.icone('valider')}${I18n.t('ordres.bouton_clore.clore')}</button>` : '';
  }

  // Champs de la fenêtre « Clore » : ceux des onglets Exécution et Compte rendu (mêmes libellés et
  // aides), le temps passé et une pièce sortie du magasin (facultative, Magasin.sortir).
  function champsClore(ot) {
    const { lignesDeLOt, listeCodes, libelleArticle, nombre, aideAstuce } = Ordres.interne;
    const total = lignesDeLOt('ot_temps', ot.id).reduce((somme, ligne) => somme + nombre(ligne.heures), 0);
    const technicien = App.technicienSolo() || ot.technicien_id || '';
    const articles = Donnees.lignes('articles').filter((a) => texte(a.actif) !== '0')
      .map((a) => ({ valeur: a.id, libelle: I18n.t('ordres.options_articles.libelle_article_stock_stock_article', { libelleArticle: libelleArticle(a), stockArticle: UI.nombreFr(Donnees.stockArticle(a.id)) }) }));
    const fin = champOt('date_fin', texte(ot.date_fin) || Donnees.maintenant().slice(0, 16));
    UI.$('input', fin).max = Donnees.maintenant().replace(' ', 'T');     // pas de date de fin dans le futur
    const remise = champOt('remise_service', ot.remise_service, {
      libelle: I18n.t('ordres.champs_clore.equipement_remis_service_securite'),
    });
    if (texte((equipementDe(ot) || {}).habilitation_requise)) remise.appendChild(UI.element(UI.html`<p class="aide">${Ordres.rappelConsignation()}</p>`));
    return [
      fin,
      champOt('arret_production', ot.arret_production, { libelle: I18n.t('ordres.champs_clore.arret_production_pendant_intervention') }),
      champOt('duree_arret_h', ot.duree_arret_h),
      UI.champ({ nom: 'heures', type: 'decimal', libelle: I18n.t('ordres.champs_clore.temps_passe_ajouter_heures') }, '',
        { aide: total > 0 ? I18n.t('ordres.champs_clore.deja_saisi', { total: UI.heures(total) }) : I18n.t('ordres.champs_clore.moins_temps_passe_exige') }),
      champOt('technicien_id', technicien, { liste: listeTechniciens(technicien), libelle: I18n.t('ordres.champs_clore.technicien_temps_passe') }),
      UI.champ({ nom: 'article_id', type: 'ref', libelle: I18n.t('ordres.champs_clore.piece_sortie_magasin_facultatif') }, '', { liste: articles }),
      UI.champ({ nom: 'quantite', type: 'decimal', libelle: I18n.t('ordres.champs_clore.quantite_sortie') }, '1'),
      champOt('symptome_code', ot.symptome_code, { liste: listeCodes('symptôme') }),
      champOt('cause_code', ot.cause_code, { liste: listeCodes('cause') }),
      champOt('remede_code', ot.remede_code, { liste: listeCodes('remède') }),
      champOt('compte_rendu', ot.compte_rendu, {
        aide: I18n.t('ordres.champs_clore.ete_constate_cause_ete'),
      }),
      champOt('astuce', ot.astuce, { aide: aideAstuce() }),
      remise,
    ];
  }

  /** « Clore » : saisies de la fiche enregistrées, puis une seule fenêtre → Ordres.clore (technique + administrative). */
  async function demanderClore(ot) {
    viderMessage();
    const sauvegarde = await enregistrerFormulairesModifies();
    if (!sauvegarde.ok) return;
    const actuel = Donnees.trouver('ordres_travail', ot.id) || ot;
    const fait = await UI.fenetreAction({
      titre: I18n.t('ordres.demander_clore.clore_actuel_id', { actuelId: actuel.id }), libelleValider: I18n.t('ordres.demander_clore.clore_verrouiller'), classe: 'ot-fenetre-clore',
      introduction: UI.html`<p>${I18n.t('ordres.demander_clore.cloture_technique_puis_administrative')}</p>`,
      champs: champsClore(actuel),
      verifier: () => [],
      action: (valeurs, contenu) => Ordres.clore(actuel, UI.lireFormulaire(contenu.closest('form'))),
    });
    if (!fait) { if (sauvegarde.enregistres) await apresEnregistrement(); return; }
    await apresEnregistrement();
    const avertissementGamme = lireAvertissementGamme(actuel.id);
    UI.toast(avertissementGamme || I18n.t('ordres.demander_clore.cloture_techniquement_administrativement', { actuelId: actuel.id }), avertissementGamme ? 'attention' : 'succes');
  }

  /** Avertissement RG8 affichable (texte complet, avec le nom du technicien et l'équipement). */
  function bandeauHabilitation(equipementId, technicienId, date) {
    const equipement = Donnees.trouver('equipements', equipementId);
    const jour = texte(date).slice(0, 10) || aujourdhui();
    const manquantes = habilitationsManquantes(equipement, technicienId, jour);
    return UI.bandeau('attention', UI.html`${I18n.html('ordres.bandeau_habilitation.avertissement_habilitation_pas_habilitation', { nomTechnicien: nomTechnicien(technicienId), technicienId, join: manquantes.join(', '), jour: UI.dateFr(jour), repereEquipement: repereEquipement(equipementId) })}`);
  }

  // Panneau d'onglet : zone de titre + contenu en lecture seule ou modifiable.
  function enteteOnglet(titre, explication) {
    return UI.html`<div class="entete-carte"><h2>${titre}</h2>${explication ? UI.html`<span class="aide">${explication}</span>` : ''}</div>`;
  }

  // Outils prêtés aux fichiers suivants du module (usage interne).
  Object.assign(Ordres.interne, {
    afficherNouveau, afficherFiche, boutonsTransitions, declarerFormulaire, apresEnregistrement, pendant,
    listeErreursHtml, bandeauHabilitation, enteteOnglet, lienOt,
  });

  return {};
})());
