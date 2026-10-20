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
      case 'Nouvelle': return 'En attente de la décision du responsable maintenance.';
      case 'Acceptée': return 'Acceptée : un ordre de travail a été créé.';
      case 'Regroupée': return 'Regroupée avec un ordre de travail déjà ouvert pour cet équipement.';
      case 'Différée': return 'Différée : elle sera traitée plus tard (par exemple au prochain arrêt).';
      case 'Refusée': return 'Refusée par le responsable maintenance.';
      default: return '';
    }
  }

  function afficherFiche(conteneur, parametres) {
    const diId = parametres.id;
    const demande = Donnees.trouver('demandes', diId);
    App.definirTitre(demande ? demande.id : 'Demande');
    if (!demande) {
      UI.remplir(conteneur, UI.html`
        <div class="entete-page"><div><div class="fil"><a href="#/di">Demandes</a> › <span>${diId}</span></div>
          <h1>Demande ${diId}</h1></div></div>
        ${UI.vide('Demande introuvable', 'Aucune demande ne porte ce numéro.', 'demandes')}`);
      return;
    }
    const equipement = Donnees.trouver('equipements', demande.equipement_id);
    const priorite = prioriteDeLaDemande(demande);
    const ot = demande.ot_id ? Donnees.trouver('ordres_travail', demande.ot_id) : null;
    const decisionPossible = App.estResponsable() && STATUTS_A_TRAITER.includes(demande.statut);

    UI.remplir(conteneur, UI.html`
      <div class="entete-page di-entete-fiche">
        <div>
          <div class="fil"><a href="#/di">Demandes</a> › <span>${demande.id}</span></div>
          <h1>${demande.symptome || demande.id}</h1>
          <p class="di-entete-badges"><b>${demande.id}</b> ${UI.badgeStatut(demande.statut)} ${UI.badgePriorite(priorite)} ${badgeImpact(demande.impact)}</p>
        </div>
      </div>
      <div class="di-zone-securite"></div>
      <div class="grille di-fiche">
        <article class="carte c8 di-details">
          <h2>La demande</h2>
          <dl class="valeurs">
            <dt>Équipement</dt>
            <dd>${equipement ? UI.html`<a href="#/equipement/${encodeURIComponent(equipement.id)}">${libelleEquipement(equipement.id)}</a>` : demande.equipement_id}</dd>
            <dt>Symptôme</dt><dd>${demande.symptome}</dd>
            ${demande.symptome_code ? UI.html`<dt>Code symptôme</dt><dd class="di-code-symptome">${libelleSymptome(demande.symptome_code)}</dd>` : ''}
            ${demande.ot_origine_id ? UI.html`<dt>Origine</dt><dd class="di-origine-fiche">${lienOrigine(demande.ot_origine_id)}</dd>` : ''}
            <dt>Impact</dt><dd>${badgeImpact(demande.impact)}</dd>
            <dt>Priorité calculée</dt><dd>${UI.badgePriorite(priorite)}
              <span class="aide">criticité ${(equipement && equipement.criticite) || 'B'} × impact ${demande.impact || '—'}</span></dd>
            <dt>Précisions</dt><dd class="di-texte-long">${demande.description}</dd>
            <dt>Demandeur</dt><dd>${demande.demandeur}</dd>
            <dt>Signalée le</dt><dd>${UI.dateHeureFr(demande.date_heure)}</dd>
          </dl>
          <div class="di-causes"></div>
          ${demande.photo ? UI.html`<div class="di-photo"><h3>Photo</h3>
            <a class="di-lien-photo" target="_blank" rel="noopener"><img class="di-photo-image" alt="Photo jointe à ${demande.id}"></a>
            <p class="aide di-photo-etat">Chargement de la photo…</p></div>` : ''}
        </article>
        <aside class="c4 di-cote">
          <article class="carte di-suivi">
            <h2>Suivi</h2>
            <p>${UI.badgeStatut(demande.statut)} ${texteSuivi(demande)}</p>
            <dl class="valeurs">
              ${demande.date_decision ? UI.html`<dt>Décision le</dt><dd>${UI.dateHeureFr(demande.date_decision)}</dd>` : ''}
              ${demande.motif_decision ? UI.html`<dt>Motif</dt><dd class="di-motif-fiche">${demande.motif_decision}</dd>` : ''}
              ${demande.ot_id ? UI.html`<dt>Ordre de travail</dt><dd><a href="#/ot/${encodeURIComponent(demande.ot_id)}">${demande.ot_id}</a>
                ${ot ? UI.html` ${UI.badgeStatut(ot.statut)}` : ''}</dd>` : ''}
            </dl>
          </article>
          <div class="di-decision"></div>
        </aside>
      </div>`);

    if (demande.impact === 'sécurité' && STATUTS_A_TRAITER.includes(demande.statut)) {
      UI.$('.di-zone-securite', conteneur).appendChild(UI.bandeau('securite',
        UI.html`<b>Danger signalé :</b> la zone doit être mise en sécurité. Priorité P1 : à traiter immédiatement.`));
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
    const texteLien = 'Signalée pendant l\'OT préventif ' + otId;
    return App.estDemandeur() ? UI.html`${texteLien}`
      : UI.html`<a class="di-lien-origine" href="#/ot/${encodeURIComponent(otId)}">${texteLien}</a>`;
  }

  // La photo est lue de façon asynchrone (URL du serveur ou URL d'objet en dossier / démo).
  async function chargerPhoto(conteneur, nom) {
    const image = UI.$('.di-photo-image', conteneur);
    const lien = UI.$('.di-lien-photo', conteneur);
    const etat = UI.$('.di-photo-etat', conteneur);
    try {
      const adresse = await App.adaptateur.urlDocument(nom);
      if (!adresse) { etat.textContent = 'Photo introuvable : ' + nom + '.'; image.hidden = true; return; }
      image.addEventListener('load', () => { etat.textContent = ''; }, { once: true });
      image.addEventListener('error', () => { etat.textContent = 'Photo illisible : ' + nom + '.'; image.hidden = true; }, { once: true });
      image.src = adresse;
      lien.href = adresse;
    } catch (erreur) {
      etat.textContent = 'Photo indisponible : ' + nom + '.';
      image.hidden = true;
      console.warn('Prévo (demandes) : photo « ' + nom + ' » non affichée (' + (erreur && erreur.message) + ').', erreur);
    }
  }

  function afficherPanneauDecision(zone, demande, priorite) {
    const otOuverts = otOuvertsDeLEquipement(demande.equipement_id);
    UI.remplir(zone, UI.html`
      <article class="carte di-panneau-decision">
        <h2>Décision</h2>
        <p class="di-rappel-priorite">Priorité calculée ${UI.badgePriorite(priorite)}</p>
        <p class="aide">Le demandeur voit la décision et son motif.</p>
        <div class="pile-gros">
          <button type="button" class="btn btn-primaire btn-gros" data-decision="accepter">${UI.icone('valider')}<span>Accepter<small>crée un ordre de travail</small></span></button>
          <button type="button" class="btn btn-secondaire btn-gros" data-decision="regrouper" ${otOuverts.length ? '' : UI.brut('disabled')}>${UI.icone('ordres')}<span>Regrouper<small>${otOuverts.length
            ? otOuverts.length + ' OT ouvert' + (otOuverts.length > 1 ? 's' : '') + ' sur cet équipement'
            : 'aucun OT ouvert sur cet équipement'}</small></span></button>
          ${demande.statut === 'Nouvelle' ? UI.html`<button type="button" class="btn btn-secondaire btn-gros" data-decision="differer">${UI.icone('horloge')}<span>Différer<small>à traiter plus tard</small></span></button>` : ''}
          <button type="button" class="btn btn-danger btn-gros" data-decision="refuser">${UI.icone('fermer')}<span>Refuser<small>motif obligatoire</small></span></button>
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
        <p>Un ordre de travail va être créé pour <b>${libelleEquipement(demande.equipement_id)}</b> :
          « ${demande.symptome} ».</p>
        <div class="champ">
          <label class="libelle" for="${idPriorite}">Priorité</label>
          <select id="${idPriorite}" name="priorite">
            ${PRIORITES.map((p) => UI.html`<option value="${p}" ${p === priorite ? UI.brut('selected') : ''}>${p}${p === priorite ? ' (calculée)' : ''}</option>`)}
          </select>
        </div>
        <div class="champ di-champ-motif" hidden>
          <label class="libelle" for="${idMotif}">Motif du changement de priorité <span class="requis" aria-hidden="true">*</span></label>
          <textarea id="${idMotif}" name="motif" rows="3" data-dictee aria-required="true"></textarea>
          <p class="erreur-champ" hidden></p>
        </div>
        <div class="champ">
          <label class="libelle" for="${idType}">Type d'ordre de travail</label>
          <select id="${idType}" name="type">
            <option value="${TYPE_IMMEDIAT}">${TYPE_IMMEDIAT}</option>
            <option value="${TYPE_DIFFERE}">${TYPE_DIFFERE}</option>
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
      zoneDate.textContent = date ? 'Date prévue : ' + UI.dateFr(date) + ' (délai de la priorité ' + choisie + ').'
        : 'Date prévue : au prochain arrêt (priorité P4, pas de date).';
    }
    choixPriorite.addEventListener('change', mettreAJour);
    choixType.addEventListener('change', () => { typeTouche = true; });
    champMotif.addEventListener('input', () => { erreurMotif.hidden = true; champMotif.removeAttribute('aria-invalid'); });
    mettreAJour();

    const choix = await UI.fenetre({
      titre: 'Accepter ' + demande.id,
      contenu,
      boutons: [
        { libelle: 'Annuler', valeur: null, classe: 'btn-fantome' },
        { libelle: 'Créer l\'ordre de travail', valeur: 'accepter', classe: 'btn-primaire', defaut: true },
      ],
      avantFermeture() {
        if (choixPriorite.value === priorite || champMotif.value.trim()) return true;
        erreurMotif.textContent = 'Le motif est obligatoire quand la priorité change.';
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
    UI.toast('Demande ' + demande.id + ' acceptée : ' + otId + ' créé.', 'succes');
    App.naviguer('#/ot/' + encodeURIComponent(otId));
  }

  // --- Regrouper : choix d'un OT ouvert du même équipement -----------------------------------
  async function decisionRegrouper(demande, priorite, otOuverts) {
    const nomGroupe = UI.identifiantUnique('di-regroupe');
    const contenu = UI.element(UI.html`
      <div class="form-colonne">
        <p>Rattacher ${demande.id} à un ordre de travail déjà ouvert sur <b>${libelleEquipement(demande.equipement_id)}</b> :</p>
        <fieldset class="di-choix-ot"><legend class="visuellement-cache">Ordre de travail</legend>
          ${otOuverts.map((ot, rang) => UI.html`
            <label class="case di-option-ot"><input type="radio" name="${nomGroupe}" value="${ot.id}" ${rang === 0 ? UI.brut('checked') : ''}>
              <span><b>${ot.id}</b> ${UI.badgePriorite(ot.priorite)} ${UI.badgeStatut(ot.statut)}<br><span class="aide">${ot.titre}</span></span></label>`)}
        </fieldset>
      </div>`);
    const choix = await UI.fenetre({
      titre: 'Regrouper ' + demande.id,
      contenu,
      boutons: [
        { libelle: 'Annuler', valeur: null, classe: 'btn-fantome' },
        { libelle: 'Regrouper', valeur: 'regrouper', classe: 'btn-primaire', defaut: true },
      ],
    });
    if (choix !== 'regrouper') return;
    const coche = UI.$('input:checked', contenu);
    if (!coche) return;
    await regrouper(demande.id, coche.value);
    UI.toast('Demande ' + demande.id + ' regroupée avec ' + coche.value + '.', 'succes');
    App.marquerSaisie(false);
    await App.reafficher();
  }

  // --- Différer : motif facultatif -----------------------------------------------------------
  async function decisionDifferer(demande) {
    const idMotif = UI.identifiantUnique('di-motif-report');
    const contenu = UI.element(UI.html`
      <div class="champ">
        <label class="libelle" for="${idMotif}">Motif du report <span class="aide">(facultatif, visible du demandeur)</span></label>
        <textarea id="${idMotif}" name="motif" rows="3" data-dictee placeholder="Ex. à traiter lors de l'arrêt programmé de fin de mois"></textarea>
      </div>`);
    const choix = await UI.fenetre({
      titre: 'Différer ' + demande.id,
      contenu,
      boutons: [
        { libelle: 'Annuler', valeur: null, classe: 'btn-fantome' },
        { libelle: 'Différer', valeur: 'differer', classe: 'btn-primaire', defaut: true },
      ],
    });
    if (choix !== 'differer') return;
    await differer(demande.id, UI.$('textarea', contenu).value);
    UI.toast('Demande ' + demande.id + ' différée.', 'succes');
    App.marquerSaisie(false);
    await App.reafficher();
  }

  // --- Refuser : motif obligatoire ----------------------------------------------------------
  async function decisionRefuser(demande) {
    const motif = await UI.demanderMotif('Refuser ' + demande.id, 'Motif du refus (visible du demandeur)', {
      libelleValider: 'Refuser la demande', exemple: 'Ex. hors périmètre de la maintenance, à adresser au service méthodes',
    });
    if (motif === null) return;
    await refuser(demande.id, motif);
    UI.toast('Demande ' + demande.id + ' refusée.', 'succes');
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
      id: 'nouvelle-di', route: /^#\/di\/nouvelle$/, titre: 'Signaler un problème',
      menu: { libelle: 'Signaler', icone: 'ajouter', ordre: 15 },
      profils: tousProfils, tables: [],
      afficher: afficherNouvelle,
    });
    App.ecran({
      id: 'liste-di', route: /^#\/di$/, titre: 'Demandes',
      menu: { libelle: 'Demandes', icone: 'demandes', ordre: 20 },
      profils: tousProfils, tables: ['demandes', 'equipements'],
      afficher: afficherListe,
    });
    App.ecran({
      id: 'fiche-di', route: /^#\/di\/(?!nouvelle$)(?<id>[^/?]+)$/, titre: 'Demande', parent: 'liste-di',
      profils: tousProfils, tables: ['demandes', 'ordres_travail', 'equipements', 'codes_defaillance'],
      afficher: afficherFiche,
    });
  });

  return {};
})());
