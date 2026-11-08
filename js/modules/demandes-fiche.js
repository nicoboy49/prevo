'use strict';
// Demandes (5/5) — fiche d'une demande (#/di/<id>) : détails, photo, suivi ; pour le responsable,
// le panneau et les fenêtres de décision (accepter, regrouper, différer, refuser) ; puis
// l'enregistrement des écrans du module auprès d'App (ARCHITECTURE.md §8, §10 RG1 et §14.2).
// Dernier fichier du module : les écrans des fichiers précédents existent déjà.

Object.assign(Demandes, (() => {

  // Constantes, outils, règles, écritures et écrans des fichiers précédents (demandes-regles.js à demandes-liste.js).
  const { typePropose, datePrevue, libelleEquipement, accepter, regrouper, differer, refuser } = Demandes;
  const { STATUTS_A_TRAITER, PRIORITES, TYPE_IMMEDIAT, TYPE_DIFFERE, prioriteDeLaDemande, badgeImpact,
    otOuvertsDeLEquipement, codesSymptome, afficherNouvelle, afficherListe } = Demandes.interne;

  // ===========================================================================================
  // 7. Fiche d'une demande (#/di/<id>) et décisions du responsable
  // ===========================================================================================

  function texteSuivi(demande) {
    switch (demande.statut) {
      case 'Nouvelle': return I18n.t('demandes.texte_suivi.attente_decision_responsable_maintenance');
      case 'Acceptée': return I18n.t('demandes.texte_suivi.acceptee_ordre_travail_ete');
      case 'Regroupée': return I18n.t('demandes.texte_suivi.regroupee_ordre_travail_deja');
      case 'Différée': return I18n.t('demandes.texte_suivi.differee_sera_traitee_plus');
      case 'Refusée': return I18n.t('demandes.texte_suivi.refusee_responsable_maintenance');
      default: return '';
    }
  }

  function afficherFiche(conteneur, parametres) {
    const diId = parametres.id;
    const demande = Donnees.trouver('demandes', diId);
    App.definirTitre(demande ? demande.id : I18n.t('demandes.fiche.demande'));
    if (!demande) {
      UI.remplir(conteneur, UI.html`
        <div class="entete-page"><div><div class="fil">${I18n.html('demandes.fiche.demandes_di_id', { diId })}</div>
          <h1>${I18n.t('demandes.fiche.demande_di_id', { diId })}</h1></div></div>
        ${UI.vide(I18n.t('demandes.fiche.demande_introuvable'), I18n.t('demandes.fiche.aucune_demande_porte_numero'), 'demandes')}`);
      return;
    }
    const equipement = Donnees.trouver('equipements', demande.equipement_id);
    const priorite = prioriteDeLaDemande(demande);
    const ot = demande.ot_id ? Donnees.trouver('ordres_travail', demande.ot_id) : null;
    const decisionPossible = App.estResponsable() && STATUTS_A_TRAITER.includes(demande.statut);

    UI.remplir(conteneur, UI.html`
      <div class="entete-page di-entete-fiche">
        <div>
          <div class="fil">${I18n.html('demandes.fiche.demandes_demande_id', { demandeId: demande.id })}</div>
          <h1>${demande.symptome || demande.id}</h1>
          <p class="di-entete-badges"><b>${demande.id}</b> ${UI.badgeValeur('demandes', 'statut', demande.statut)} ${UI.badgePriorite(priorite)} ${badgeImpact(demande.impact)}</p>
        </div>
      </div>
      <div class="di-zone-securite"></div>
      <div class="grille di-fiche">
        <article class="carte c8 di-details">
          <h2>${I18n.t('demandes.fiche.demande_2')}</h2>
          <dl class="valeurs">
            <dt>${I18n.t('commun.champ.equipement')}</dt>
            <dd>${equipement ? UI.html`<a href="#/equipement/${encodeURIComponent(equipement.id)}">${libelleEquipement(equipement.id)}</a>` : demande.equipement_id}</dd>
            <dt>${I18n.t('commun.champ.symptome')}</dt><dd>${demande.symptome}</dd>
            ${demande.symptome_code ? UI.html`<dt>${I18n.t('demandes.fiche.code_symptome')}</dt><dd class="di-code-symptome">${libelleSymptome(demande.symptome_code)}</dd>` : ''}
            ${demande.ot_origine_id ? UI.html`<dt>${I18n.t('demandes.fiche.origine')}</dt><dd class="di-origine-fiche">${lienOrigine(demande.ot_origine_id)}</dd>` : ''}
            <dt>${I18n.t('demandes.fiche.impact')}</dt><dd>${badgeImpact(demande.impact)}</dd>
            <dt>${I18n.t('demandes.fiche.priorite_calculee')}</dt><dd>${UI.badgePriorite(priorite)}
              <span class="aide">${I18n.t('demandes.fiche.criticite_impact', { criticite: Schema.libelleValeur('equipements', 'criticite', (equipement && equipement.criticite) || 'B'), impact: Schema.libelleValeur('demandes', 'impact', demande.impact) || '—' })}</span></dd>
            <dt>${I18n.t('demandes.fiche.precisions')}</dt><dd class="di-texte-long">${demande.description}</dd>
            <dt>${I18n.t('demandes.fiche.demandeur')}</dt><dd>${demande.demandeur}</dd>
            <dt>${I18n.t('demandes.fiche.signalee')}</dt><dd>${UI.dateHeureFr(demande.date_heure)}</dd>
          </dl>
          <div class="di-causes"></div>
          ${demande.photo ? UI.html`<div class="di-photo"><h3>${I18n.t('demandes.fiche.photo')}</h3>
            <a class="di-lien-photo" target="_blank" rel="noopener"><img class="di-photo-image" alt="${I18n.t('demandes.fiche.photo_jointe', { demandeId: demande.id })}"></a>
            <p class="aide di-photo-etat">${I18n.t('demandes.fiche.chargement_photo')}</p></div>` : ''}
        </article>
        <aside class="c4 di-cote">
          <article class="carte di-suivi">
            <h2>${I18n.t('demandes.fiche.suivi')}</h2>
            <p>${UI.badgeValeur('demandes', 'statut', demande.statut)} ${texteSuivi(demande)}</p>
            <dl class="valeurs">
              ${demande.date_decision ? UI.html`<dt>${I18n.t('demandes.fiche.decision')}</dt><dd>${UI.dateHeureFr(demande.date_decision)}</dd>` : ''}
              ${demande.motif_decision ? UI.html`<dt>${I18n.t('demandes.fiche.motif')}</dt><dd class="di-motif-fiche">${demande.motif_decision}</dd>` : ''}
              ${demande.ot_id ? UI.html`<dt>${I18n.t('demandes.fiche.ordre_travail')}</dt><dd>${lienOt(demande.ot_id)}
                ${ot ? UI.html` ${UI.badgeValeur('ordres_travail', 'statut', ot.statut)}` : ''}</dd>` : ''}
            </dl>
          </article>
          <div class="di-decision"></div>
        </aside>
      </div>`);

    if (demande.impact === 'sécurité' && STATUTS_A_TRAITER.includes(demande.statut)) {
      UI.$('.di-zone-securite', conteneur).appendChild(UI.bandeau('securite',
        UI.html`${I18n.html('demandes.fiche.danger_signale_zone_doit')}`));
    }
    // Causes fréquentes de ce symptôme sur cet équipement (D25) : tous les profils ; rien sans code.
    const encart = CausesFrequentes.encart(demande.equipement_id, demande.symptome_code);
    if (encart) UI.$('.di-causes', conteneur).appendChild(encart);
    if (demande.photo) chargerPhoto(conteneur, demande.photo);
    if (decisionPossible) afficherPanneauDecision(UI.$('.di-decision', conteneur), demande, priorite);
  }

  /** « Fuite (S01) » : libellé du code symptôme, sinon le code seul. */
  function libelleSymptome(code) {
    const trouve = codesSymptome().find((entree) => entree.code === code);
    return trouve ? trouve.libelle + ' (' + code + ')' : code;
  }

  /** « Signalée pendant l'OT préventif OT-… » : lien, sauf pour le demandeur (pas d'accès aux OT). */
  function lienOrigine(otId) {
    const texteLien = I18n.t('demandes.lien_origine.signalee_pendant_ot_preventif', { otId });
    return App.estDemandeur() ? UI.html`${texteLien}`
      : UI.html`<a class="di-lien-origine" href="#/ot/${encodeURIComponent(otId)}">${texteLien}</a>`;
  }

  /** OT de la demande (bloc « Suivi ») : lien, sauf pour le demandeur (pas d'accès aux OT : un clic
   *  le renverrait à l'accueil) qui voit le même identifiant en texte simple. */
  function lienOt(otId) {
    return App.estDemandeur() ? UI.html`${otId}`
      : UI.html`<a href="#/ot/${encodeURIComponent(otId)}">${otId}</a>`;
  }

  // La photo est lue de façon asynchrone (URL du serveur ou URL d'objet en dossier / démo).
  async function chargerPhoto(conteneur, nom) {
    const image = UI.$('.di-photo-image', conteneur);
    const lien = UI.$('.di-lien-photo', conteneur);
    const etat = UI.$('.di-photo-etat', conteneur);
    try {
      const adresse = await App.adaptateur.urlDocument(nom);
      if (!adresse) { etat.textContent = I18n.t('demandes.charger_photo.photo_introuvable', { nom }); image.hidden = true; return; }
      image.addEventListener('load', () => { etat.textContent = ''; }, { once: true });
      image.addEventListener('error', () => { etat.textContent = I18n.t('demandes.charger_photo.photo_illisible', { nom }); image.hidden = true; }, { once: true });
      image.src = adresse;
      lien.href = adresse;
    } catch (erreur) {
      etat.textContent = I18n.t('demandes.charger_photo.photo_indisponible', { nom });
      image.hidden = true;
      console.warn('Prévo (demandes) : photo « ' + nom + ' » non affichée (' + (erreur && erreur.message) + ').', erreur);
    }
  }

  function afficherPanneauDecision(zone, demande, priorite) {
    const otOuverts = otOuvertsDeLEquipement(demande.equipement_id);
    UI.remplir(zone, UI.html`
      <article class="carte di-panneau-decision">
        <h2>${I18n.t('demandes.panneau_decision.decision')}</h2>
        <p class="di-rappel-priorite">${I18n.t('demandes.fiche.priorite_calculee')} ${UI.badgePriorite(priorite)}</p>
        <p class="aide">${I18n.t('demandes.panneau_decision.demandeur_voit_decision_motif')}</p>
        <div class="pile-gros">
          <button type="button" class="btn btn-primaire btn-gros" data-decision="accepter">${UI.icone('valider')}<span>${I18n.html('demandes.panneau_decision.accepter_cree_ordre_travail')}</span></button>
          <button type="button" class="btn btn-secondaire btn-gros" data-decision="regrouper" ${otOuverts.length ? '' : UI.brut('disabled')}>${UI.icone('ordres')}<span>${I18n.t('demandes.panneau_decision.regrouper')}<small>${otOuverts.length
            ? I18n.t('demandes.panneau_decision.ot_ouverts_equipement', { n: otOuverts.length })
            : I18n.t('demandes.panneau_decision.aucun_ot_ouvert_equipement')}</small></span></button>
          ${demande.statut === 'Nouvelle' ? UI.html`<button type="button" class="btn btn-secondaire btn-gros" data-decision="differer">${UI.icone('horloge')}<span>${I18n.html('demandes.panneau_decision.differer_traiter_plus_tard')}</span></button>` : ''}
          <button type="button" class="btn btn-danger btn-gros" data-decision="refuser">${UI.icone('fermer')}<span>${I18n.html('demandes.panneau_decision.refuser_motif_obligatoire')}</span></button>
        </div>
      </article>`);

    zone.addEventListener('click', async (evenement) => {
      const bouton = evenement.target.closest('[data-decision]');
      if (!bouton || bouton.disabled) return;
      const actions = { accepter: decisionAccepter, regrouper: decisionRegrouper, differer: decisionDifferer, refuser: decisionRefuser };
      const boutons = UI.$$('[data-decision]', zone);
      const etatsAvant = boutons.map((b) => b.disabled);
      boutons.forEach((b) => { b.disabled = true; });
      try {
        await actions[bouton.dataset.decision](demande, priorite, otOuverts);
      } catch (erreur) {
        App.signalerErreur(erreur, 'décision sur ' + demande.id);
        // Un autre poste a peut-être décidé : on montre l'état réel de la demande.
        if (erreur instanceof Donnees.ErreurValidation || erreur instanceof Donnees.ErreurConflit) {
          await App.reafficher();
          return;
        }
      }
      if (document.contains(zone)) boutons.forEach((b, rang) => { b.disabled = etatsAvant[rang]; });
    });
  }

  // --- Accepter : priorité (modifiable avec motif), type proposé, date prévue -----------------
  async function decisionAccepter(demande, priorite) {
    const idPriorite = UI.identifiantUnique('di-acc-priorite');
    const idMotif = UI.identifiantUnique('di-acc-motif');
    const idType = UI.identifiantUnique('di-acc-type');
    const contenu = UI.element(UI.html`
      <div class="form-colonne di-fenetre-accepter">
        <p>${I18n.html('demandes.decision_accepter.ordre_travail_va_etre', { libelleEquipement: libelleEquipement(demande.equipement_id), symptome: demande.symptome })}</p>
        <div class="champ">
          <label class="libelle" for="${idPriorite}">${I18n.t('commun.champ.priorite')}</label>
          <select id="${idPriorite}" name="priorite">
            ${PRIORITES.map((p) => UI.html`<option value="${p}" ${p === priorite ? UI.brut('selected') : ''}>${Schema.libelleValeur('ordres_travail', 'priorite', p)}${p === priorite ? ' ' + I18n.t('demandes.decision_accepter.calculee') : ''}</option>`)}
          </select>
        </div>
        <div class="champ di-champ-motif" hidden>
          <label class="libelle" for="${idMotif}">${I18n.t('demandes.decision_accepter.motif_changement_priorite')} <span class="requis" aria-hidden="true">*</span></label>
          <textarea id="${idMotif}" name="motif" rows="3" data-dictee aria-required="true"></textarea>
          <p class="erreur-champ" hidden></p>
        </div>
        <div class="champ">
          <label class="libelle" for="${idType}">${I18n.t('demandes.decision_accepter.type_ordre_travail')}</label>
          <select id="${idType}" name="type">
            <option value="${TYPE_IMMEDIAT}">${Schema.libelleValeur('ordres_travail', 'type', TYPE_IMMEDIAT)}</option>
            <option value="${TYPE_DIFFERE}">${Schema.libelleValeur('ordres_travail', 'type', TYPE_DIFFERE)}</option>
          </select>
        </div>
        <p class="note di-date-prevue"></p>
      </div>`);
    const choixPriorite = UI.$('select[name=priorite]', contenu);
    const choixType = UI.$('select[name=type]', contenu);
    const blocMotif = UI.$('.di-champ-motif', contenu);
    const champMotif = UI.$('textarea', contenu);
    const erreurMotif = UI.$('.erreur-champ', blocMotif);
    const zoneDate = UI.$('.di-date-prevue', contenu);
    let typeTouche = false;

    function mettreAJour() {
      const choisie = choixPriorite.value;
      blocMotif.hidden = choisie === priorite;
      if (!typeTouche) choixType.value = typePropose(choisie);
      const date = datePrevue(choisie);
      zoneDate.textContent = date ? I18n.t('demandes.decision_accepter.date_prevue_delai_priorite', { date: UI.dateFr(date), choisie: Schema.libelleValeur('ordres_travail', 'priorite', choisie) })
        : I18n.t('demandes.decision_accepter.date_prevue_prochain_arret');
    }
    choixPriorite.addEventListener('change', mettreAJour);
    choixType.addEventListener('change', () => { typeTouche = true; });
    champMotif.addEventListener('input', () => { erreurMotif.hidden = true; champMotif.removeAttribute('aria-invalid'); });
    mettreAJour();

    const choix = await UI.fenetre({
      titre: I18n.t('demandes.decision_accepter.accepter_demande_id', { demandeId: demande.id }),
      contenu,
      boutons: [
        { libelle: I18n.t('commun.bouton.annuler'), valeur: null, classe: 'btn-fantome' },
        { libelle: I18n.t('demandes.decision_accepter.creer_ordre_travail'), valeur: 'accepter', classe: 'btn-primaire', defaut: true },
      ],
      avantFermeture() {
        if (choixPriorite.value === priorite || champMotif.value.trim()) return true;
        erreurMotif.textContent = I18n.t('demandes.decision_accepter.motif_obligatoire_quand_priorite');
        erreurMotif.hidden = false;
        champMotif.setAttribute('aria-invalid', 'true');
        champMotif.focus();
        return false;
      },
    });
    if (choix !== 'accepter') return;
    const otId = await accepter(demande.id, {
      priorite: choixPriorite.value, motifPriorite: champMotif.value, type: choixType.value,
    });
    UI.toast(I18n.t('demandes.decision_accepter.demande_acceptee_cree', { demandeId: demande.id, otId }), 'succes');
    App.naviguer('#/ot/' + encodeURIComponent(otId));
  }

  // --- Regrouper : choix d'un OT ouvert du même équipement -----------------------------------
  async function decisionRegrouper(demande, priorite, otOuverts) {
    const nomGroupe = UI.identifiantUnique('di-regroupe');
    const contenu = UI.element(UI.html`
      <div class="form-colonne">
        <p>${I18n.html('demandes.decision_regrouper.rattacher_ordre_travail_deja', { demandeId: demande.id, libelleEquipement: libelleEquipement(demande.equipement_id) })}</p>
        <fieldset class="di-choix-ot"><legend class="visuellement-cache">${I18n.t('demandes.fiche.ordre_travail')}</legend>
          ${otOuverts.map((ot, rang) => UI.html`
            <label class="case di-option-ot"><input type="radio" name="${nomGroupe}" value="${ot.id}" ${rang === 0 ? UI.brut('checked') : ''}>
              <span><b>${ot.id}</b> ${UI.badgePriorite(ot.priorite)} ${UI.badgeValeur('ordres_travail', 'statut', ot.statut)}<br><span class="aide">${ot.titre}</span></span></label>`)}
        </fieldset>
      </div>`);
    const choix = await UI.fenetre({
      titre: I18n.t('demandes.decision_regrouper.regrouper_demande_id', { demandeId: demande.id }),
      contenu,
      boutons: [
        { libelle: I18n.t('commun.bouton.annuler'), valeur: null, classe: 'btn-fantome' },
        { libelle: I18n.t('demandes.panneau_decision.regrouper'), valeur: 'regrouper', classe: 'btn-primaire', defaut: true },
      ],
    });
    if (choix !== 'regrouper') return;
    const coche = UI.$('input:checked', contenu);
    if (!coche) return;
    await regrouper(demande.id, coche.value);
    UI.toast(I18n.t('demandes.decision_regrouper.demande_regroupee', { demandeId: demande.id, cocheValue: coche.value }), 'succes');
    App.marquerSaisie(false);
    await App.reafficher();
  }

  // --- Différer : motif facultatif -----------------------------------------------------------
  async function decisionDifferer(demande) {
    const idMotif = UI.identifiantUnique('di-motif-report');
    const contenu = UI.element(UI.html`
      <div class="champ">
        <label class="libelle" for="${idMotif}">${I18n.html('demandes.decision_differer.motif_report_facultatif_visible')}</label>
        <textarea id="${idMotif}" name="motif" rows="3" data-dictee placeholder="${I18n.t('demandes.decision_differer.ex_traiter_lors_arret')}"></textarea>
      </div>`);
    const choix = await UI.fenetre({
      titre: I18n.t('demandes.decision_differer.differer_demande_id', { demandeId: demande.id }),
      contenu,
      boutons: [
        { libelle: I18n.t('commun.bouton.annuler'), valeur: null, classe: 'btn-fantome' },
        { libelle: I18n.t('demandes.decision_differer.differer'), valeur: 'differer', classe: 'btn-primaire', defaut: true },
      ],
    });
    if (choix !== 'differer') return;
    await differer(demande.id, UI.$('textarea', contenu).value);
    UI.toast(I18n.t('demandes.decision_differer.demande_differee', { demandeId: demande.id }), 'succes');
    App.marquerSaisie(false);
    await App.reafficher();
  }

  // --- Refuser : motif obligatoire ----------------------------------------------------------
  async function decisionRefuser(demande) {
    const motif = await UI.demanderMotif(I18n.t('demandes.decision_refuser.refuser_demande_id', { demandeId: demande.id }), I18n.t('demandes.decision_refuser.motif_refus_visible_demandeur'), {
      libelleValider: I18n.t('demandes.decision_refuser.refuser_demande'), exemple: I18n.t('demandes.decision_refuser.ex_hors_perimetre_maintenance'),
    });
    if (motif === null) return;
    await refuser(demande.id, motif);
    UI.toast(I18n.t('demandes.decision_refuser.demande_refusee', { demandeId: demande.id }), 'succes');
    App.marquerSaisie(false);
    await App.reafficher();
  }

  // ===========================================================================================
  // 8. Enregistrement des écrans
  // ===========================================================================================

  // App est chargé après les modules : les écrans sont enregistrés une fois la page lue.
  // Ordre d'enregistrement important : « #/di/nouvelle » avant « #/di/<id> » ; la route fiche
  // exclut en plus « nouvelle » (ARCHITECTURE.md §14.2).
  document.addEventListener('DOMContentLoaded', () => {
    const tousProfils = ['demandeur', 'technicien', 'responsable'];
    App.ecran({
      id: 'nouvelle-di', route: /^#\/di\/nouvelle$/,
      get titre() { return I18n.t('demandes.ecran.nouvelle_titre'); },
      // court : barre du bas des téléphones (cinq onglets ; le libellé entier ne tient pas en anglais ni dans les
      // langues du Lot 5).
      menu: { get libelle() { return I18n.t('demandes.menu.signaler'); },
        get court() { return I18n.t('demandes.menu.signaler_court'); }, icone: 'ajouter', ordre: 15 },
      profils: tousProfils, tables: [],
      afficher: afficherNouvelle,
    });
    App.ecran({
      id: 'liste-di', route: /^#\/di$/,
      get titre() { return I18n.t('demandes.ecran.liste_titre'); },
      menu: { get libelle() { return I18n.t('demandes.menu.demandes'); }, icone: 'demandes', ordre: 20 },
      profils: tousProfils, tables: ['demandes', 'equipements'],
      afficher: afficherListe,
    });
    App.ecran({
      id: 'fiche-di', route: /^#\/di\/(?!nouvelle$)(?<id>[^/?]+)$/, parent: 'liste-di',
      get titre() { return I18n.t('demandes.ecran.fiche_titre'); },
      profils: tousProfils, tables: ['demandes', 'ordres_travail', 'equipements', 'codes_defaillance'],
      afficher: afficherFiche,
    });
  });

  return {};
})());
