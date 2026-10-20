'use strict';
// Ordres (4/6) — écran E5, fiche d'un OT (#/ot/<id>) : en-tête, étapes, consignation, barre
// d'actions (transitions RG3 avec leurs contrôles), messages et structure des onglets ; et l'écran
// de création #/ot/nouveau (manuel, ou d'urgence avec ?urgence=1). Le contenu des onglets est dans
// ordres-onglets.js (ARCHITECTURE.md §14.2). Complète l'objet Ordres.

Object.assign(Ordres, (() => {

  // Constantes, outils, règles et écritures des fichiers précédents (ordres-regles.js à ordres-liste.js).
  const { PRIORITES, RAPPEL_CONSIGNATION, transitionsPossibles, verifierPassage, verifierHabilitation,
    piecesManquantes, estVerrouille, datePrevueParDefaut, libelleEquipement, nomTechnicien,
    creer, changerStatut, changerPriorite, creerOtLie } = Ordres;
  const { ETAPES, STATUTS_CLOTURES, memoire, texte, aujourdhui, estResponsable, estTechnicien,
    equipementDe, repereEquipement, cheminLocalisation, listeTechniciens, placerChamp, champOt,
    statutDeReprise, habilitationsManquantes, journaliserHabilitation, optionsHtml, badgeRetard,
    origineHtml } = Ordres.interne;

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
  // 5. Nouvel OT (#/ot/nouveau, ?equipement=EQ-0005, ?urgence=1)
  // ===========================================================================================

  function afficherNouveau(conteneur, parametres) {
    const requete = parametres.requete || new URLSearchParams('');
    const urgence = requete.get('urgence') === '1';
    const priorite = urgence ? 'P1' : 'P3';
    App.definirTitre(urgence ? 'OT d\'urgence' : 'Nouvel OT');
    UI.remplir(conteneur, UI.html`
      <div class="entete-page"><div>
        <div class="fil"><a href="#/ot">Ordres de travail</a> › <span>${urgence ? 'OT d\'urgence' : 'Nouvel OT'}</span></div>
        <h1>${urgence ? 'OT d\'urgence' : 'Nouvel ordre de travail'}</h1>
        <p>${urgence ? 'Correctif immédiat, priorité P1 : l\'OT pourra être démarré tout de suite.' : 'OT créé à la main (origine « manuel »). Il pourra ensuite être préparé, planifié et exécuté.'}</p>
      </div></div>
      <form class="carte form-grille" id="form-nouvel-ot" novalidate>
        <div class="champ large"><span class="libelle">Équipement <span class="requis" aria-hidden="true">*</span></span>
          <div id="ot-nouveau-equipement"></div><p class="erreur-champ" id="ot-nouveau-equipement-erreur" hidden></p></div>
        <div class="large" data-place="titre"></div>
        <div data-place="type"></div><div data-place="priorite"></div>
        <div class="large" data-place="travail_a_faire"></div>
        <div data-place="technicien_id"></div><div data-place="date_prevue"></div>
        <div class="large ot-zone-habilitation"></div>
        <div class="actions">
          <a class="btn btn-fantome" href="#/ot">Annuler</a><span class="espace"></span>
          <button type="submit" class="btn ${urgence ? 'btn-danger' : 'btn-primaire'}">${UI.icone('valider')}${urgence ? 'Créer l\'OT d\'urgence' : 'Créer l\'OT'}</button>
        </div>
      </form>`);
    if (urgence) {
      conteneur.insertBefore(UI.bandeau('securite', UI.html`<b>Intervention d'urgence.</b> Mettez la zone en sécurité et appliquez la procédure de consignation de l'équipement avant d'intervenir.`), UI.$('#form-nouvel-ot', conteneur));
    }
    const formulaire = UI.$('#form-nouvel-ot', conteneur);
    const placer = (nom, element) => placerChamp(formulaire, nom, element);
    placer('titre', champOt('titre', '', { placeholder: 'Ex. PO-02 — fuite à la garniture' }));
    placer('type', champOt('type', urgence ? 'correctif immédiat' : 'correctif différé', { lectureSeule: urgence }));
    placer('priorite', champOt('priorite', priorite, { lectureSeule: urgence }));
    placer('travail_a_faire', champOt('travail_a_faire', ''));
    placer('technicien_id', champOt('technicien_id', '', { liste: listeTechniciens('') }));
    placer('date_prevue', champOt('date_prevue', datePrevueParDefaut(priorite), { aide: 'Par défaut : création + délai de la priorité (Paramètres).' }));

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
    erreurEquipement.textContent = selecteur.valeur() ? '' : 'Choisissez l\'équipement concerné.';
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
      const habilitation = verifierHabilitation(selecteur.valeur(), valeurs.technicien_id, valeurs.date_prevue);
      if (habilitation) await journaliserHabilitation(id, habilitation);
      App.marquerSaisie(false);
      UI.toast('Ordre de travail ' + id + ' créé.', 'succes');
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
    'Préparé': (ot) => (ot.statut === 'Planifié' ? 'Déplanifier' : ot.statut === 'En attente' ? 'Reprendre (Préparé)' : 'Marquer préparé'),
    'Planifié': () => 'Planifier',
    'En cours': (ot) => (ot.statut === 'Clôturé techniquement' ? 'Rouvrir' : ot.statut === 'En attente' ? 'Reprendre (En cours)' : 'Démarrer'),
    'En attente': () => 'Mettre en attente',
    'Annulé': () => 'Annuler l\'OT',
    'Clôturé techniquement': () => 'Clôturer techniquement',
    'Clôturé administrativement': () => 'Clôturer administrativement',
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
    return UI.html`<ol class="etapes ot-etapes" aria-label="Avancement de l'OT">
      ${ETAPES.map((etape, rang) => {
        let classe = '';
        if (rang < rangCourant || (rang === rangCourant && horsEtape)) classe = 'fait';
        if (rang === rangCourant && !horsEtape) classe = 'courant';
        return UI.html`<li class="${classe}"${classe === 'courant' ? UI.brut(' aria-current="step"') : ''}>${etape}</li>`;
      })}
      ${horsEtape ? UI.html`<li class="hors" aria-current="step">${ot.statut}</li>` : ''}
    </ol>`;
  }

  function enteteFicheHtml(ot) {
    const equipement = equipementDe(ot);
    return UI.html`
      <div class="entete-page ot-entete">
        <div>
          <div class="fil"><a href="#/ot">Ordres de travail</a> › <span>${ot.id}</span></div>
          <h1><span class="ot-numero">${ot.id}</span> ${ot.titre}</h1>
          <div class="ot-badges">${UI.badgePriorite(ot.priorite)} ${UI.badgeStatut(ot.statut)}${badgeRetard(ot)}
            <span class="badge neutre">${ot.type}</span>
            ${equipement ? UI.html`<a class="ot-lien-equipement" href="#/equipement/${encodeURIComponent(equipement.id)}">${libelleEquipement(equipement.id)}</a>` : ''}
          </div>
        </div>
        <div class="actions">
          ${estResponsable() && !estVerrouille(ot) ? UI.html`<button type="button" class="btn btn-fantome" id="ot-priorite">${UI.icone('alerte')}Priorité</button>` : ''}
          <button type="button" class="btn btn-secondaire" id="ot-imprimer">${UI.icone('imprimer')}Imprimer le bon de travail</button>
        </div>
      </div>`;
  }

  function lienOt(id) {
    return UI.html`<a href="#/ot/${encodeURIComponent(id)}">${id}</a>`;
  }

  function reperesHtml(ot) {
    const lies = Donnees.lignes('ordres_travail').filter((autre) => autre.ot_lie_id === ot.id);
    return UI.html`<dl class="valeurs">
      <dt>Origine</dt><dd>${origineHtml(ot)}${ot.gamme_id ? UI.html` (gamme ${ot.gamme_id})` : ''}</dd>
      <dt>Technicien</dt><dd>${nomTechnicien(ot.technicien_id)}</dd>
      <dt>Créé le</dt><dd>${UI.dateHeureFr(ot.date_creation)}</dd>
      <dt>Prévu le</dt><dd>${UI.dateFr(ot.date_prevue)}${badgeRetard(ot)}</dd>
      <dt>Temps prévu</dt><dd>${ot.temps_prevu_h ? UI.heures(ot.temps_prevu_h) : ''}</dd>
      <dt>Début · fin</dt><dd>${UI.dateHeureFr(ot.date_debut)}${ot.date_fin ? ' → ' + UI.dateHeureFr(ot.date_fin) : ''}</dd>
      ${ot.date_cloture_tech ? UI.html`<dt>Clôture technique</dt><dd>${UI.dateHeureFr(ot.date_cloture_tech)}</dd>` : ''}
      ${ot.date_cloture_admin ? UI.html`<dt>Clôture administrative</dt><dd>${UI.dateHeureFr(ot.date_cloture_admin)}</dd>` : ''}
      ${ot.ot_lie_id ? UI.html`<dt>Reprend l'OT</dt><dd>${lienOt(ot.ot_lie_id)}</dd>` : ''}
      ${lies.length ? UI.html`<dt>Repris par</dt><dd>${lies.map((l, rang) => UI.html`${rang ? ', ' : ''}${lienOt(l.id)}`)}</dd>` : ''}
    </dl>`;
  }

  function equipementHtml(equipement) {
    if (!equipement) return UI.html`<p class="muted">Équipement introuvable.</p>`;
    return UI.html`<dl class="valeurs">
      <dt>Repère</dt><dd><a href="#/equipement/${encodeURIComponent(equipement.id)}">${equipement.repere || equipement.id}</a></dd>
      <dt>Désignation</dt><dd>${equipement.designation}</dd>
      <dt>Localisation</dt><dd>${cheminLocalisation(equipement.localisation_id)}</dd>
      <dt>Criticité</dt><dd>${equipement.criticite}</dd>
      <dt>État</dt><dd>${equipement.statut ? UI.badgeStatut(equipement.statut) : ''}</dd>
      <dt>Habilitation requise</dt><dd>${equipement.habilitation_requise || 'aucune'}</dd>
    </dl>`;
  }

  /** Bloc consignation (RG4) : procédure de l'équipement + rappel « Cocher une case ne consigne rien ». */
  function consignationHtml(equipement) {
    const procedure = texte(equipement && equipement.consignation);
    return UI.html`<section class="carte ot-consignation" aria-labelledby="ot-titre-consignation">
      <div class="entete-carte"><h2 id="ot-titre-consignation">${UI.icone('cle')} Consignation de l'équipement</h2></div>
      ${procedure ? UI.html`<div class="ot-procedure">${procedure}</div>`
        : UI.html`<p class="muted">Aucune procédure de consignation n'est renseignée pour cet équipement : voyez votre responsable avant d'intervenir.</p>`}
      <p class="ot-rappel"><b>${RAPPEL_CONSIGNATION}</b></p>
    </section>`;
  }

  function bandeauEtat(ot) {
    if (ot.statut === 'En attente') return UI.bandeau('attention', UI.html`<b>En attente</b> — ${ot.motif_attente || 'motif non renseigné'}`);
    if (ot.statut === 'Annulé') return UI.bandeau('important', UI.html`<b>OT annulé</b> — ${ot.motif_annulation || 'motif non renseigné'}. Il reste consultable mais n'est plus modifiable.`);
    if (ot.statut === 'Clôturé administrativement') {
      return UI.bandeau('info', UI.html`<b>OT verrouillé</b> (clôturé administrativement le ${UI.dateHeureFr(ot.date_cloture_admin)}) : lecture seule. Une reprise se fait par un nouvel OT lié.`);
    }
    return null;
  }

  function actionsHtml(ot) {
    const boutons = boutonsTransitions(ot, ['Préparé', 'Planifié', 'En cours', 'Clôturé techniquement', 'Clôturé administrativement', 'En attente', 'Annulé']);
    const lie = estVerrouille(ot) && estResponsable()
      ? UI.html`<button type="button" class="btn btn-primaire" id="ot-lie">${UI.icone('ajouter')}Créer un OT lié</button>` : '';
    if (!boutons.length && !lie) return '';
    return UI.html`<div class="carte ot-actions sans-impression"><div class="entete-carte"><h2>Actions</h2></div>
      <div class="actions">${boutons}${lie}</div></div>`;
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
      UI.remplir(conteneur, UI.html`<div class="entete-page"><div><div class="fil"><a href="#/ot">Ordres de travail</a> › <span>${parametres.id}</span></div><h1>Ordre de travail ${parametres.id}</h1></div></div>
        ${UI.vide('Ordre de travail introuvable', 'Aucun OT ne porte cet identifiant.', 'ordres')}`);
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
        <section class="carte c6"><h2>Équipement</h2>${equipementHtml(equipement)}</section>
        <section class="carte c6"><h2>Repères</h2>${reperesHtml(ot)}</section>
      </div>
      ${consignationHtml(equipement)}
      ${actionsHtml(ot)}
      <div id="ot-message" class="ot-message" aria-live="polite"></div>
      <div class="ot-onglets"></div>`);
    const etat = bandeauEtat(ot);
    if (etat) UI.$('.ot-bandeau-etat', racine).appendChild(etat);

    UI.onglets(UI.$('.ot-onglets', racine), [
      { id: 'preparation', libelle: 'Préparation', afficher: (panneau) => afficherPreparation(panneau, ot) },
      { id: 'execution', libelle: 'Exécution', afficher: (panneau) => afficherExecution(panneau, ot) },
      { id: 'compte-rendu', libelle: 'Compte rendu', afficher: (panneau) => afficherCompteRendu(panneau, ot) },
      { id: 'historique', libelle: 'Historique équipement', afficher: (panneau) => afficherHistorique(panneau, ot) },
    ], { actif: memoire.ongletParOt[ot.id] || ongletParDefaut(ot), libelle: 'Parties de l\'ordre de travail',
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
      const attentePiece = evenement.target.closest('button[data-action="attente-piece"]');
      if (attentePiece) mettreEnAttentePiece(ot);
    });
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
      'L\'OT ' + actuel.id + ' sera verrouillé : plus aucune modification possible. Une reprise se fera par un nouvel OT lié.',
      { titre: 'Clôturer administrativement', oui: 'Clôturer et verrouiller' }))) return;
    const reussi = await pendant(bouton, () => changerStatut(actuel.id, actuel.statut, cible, complement), 'changement de statut');
    if (reussi === undefined) return;
    await apresEnregistrement();
    UI.toast(actuel.id + ' : ' + cible + '.', 'succes');
    if (verification.avertissements.length) afficherMessage('attention', verification.avertissements.join(' '));
  }

  // Motif demandé pour En attente et Annulé : { motif_… } ; null si l'utilisateur renonce.
  async function demanderComplement(ot, cible) {
    if (cible === 'En attente') {
      const motif = await UI.demanderMotif('Mettre en attente ' + ot.id, 'Motif de mise en attente', { exemple: 'Ex. pièce en commande, attente de l\'arrêt de la ligne…' });
      return motif === null ? null : { motif_attente: motif };
    }
    if (cible === 'Annulé') {
      const motif = await UI.demanderMotif('Annuler ' + ot.id, 'Motif d\'annulation', { libelleValider: 'Annuler l\'OT' });
      return motif === null ? null : { motif_annulation: motif };
    }
    return {};
  }

  function afficherRefus(ot, cible, verification) {
    const titre = cible === 'Clôturé techniquement'
      ? 'Clôture technique impossible : le statut reste « ' + ot.statut + ' ».'
      : 'Passage à « ' + cible + ' » refusé : le statut reste « ' + ot.statut + ' ».';
    const bandeau = afficherMessage('important', listeErreursHtml(titre, verification.erreurs));
    if (bandeau && verification.piecesManquantes.length && transitionsPossibles(ot).includes('En attente') && actionAutorisee(ot, 'En attente')) {
      bandeau.querySelector('.alerte-texte').appendChild(UI.element(UI.html`<div class="actions">
        <button type="button" class="btn btn-secondaire" data-action="attente-piece">Mettre en attente (motif : pièce)</button></div>`));
    }
  }

  /** RG3 : stock insuffisant → mise en attente avec un motif « Pièce : … » prérempli (modifiable). */
  async function mettreEnAttentePiece(ot) {
    const actuel = Donnees.trouver('ordres_travail', ot.id) || ot;
    const manquantes = piecesManquantes(actuel.id);
    const proposition = 'Pièce : ' + (manquantes.length
      ? manquantes.map((p) => p.libelle + ' (' + UI.nombreFr(p.prevu) + ' prévu(s), ' + UI.nombreFr(p.stock) + ' en stock)').join(' ; ')
      : 'stock insuffisant') + '.';
    const motif = await UI.demanderMotif('Mettre en attente ' + actuel.id, 'Motif de mise en attente', { valeur: proposition });
    if (motif === null) return;
    const reussi = await pendant(null, () => changerStatut(actuel.id, actuel.statut, 'En attente', { motif_attente: motif }), 'mise en attente');
    if (reussi === undefined) return;
    await apresEnregistrement();
    UI.toast(actuel.id + ' : En attente.', 'succes');
  }

  async function demanderPriorite(ot) {
    const contenu = UI.element(UI.html`<div class="form-colonne">
      <p>Priorité actuelle : ${UI.badgePriorite(ot.priorite)}. Le changement est tracé au journal avec son motif.</p>
      <div class="champ"><label class="libelle" for="ot-nouvelle-priorite">Nouvelle priorité</label>
        <select id="ot-nouvelle-priorite">${optionsHtml(PRIORITES.map((p) => ({ valeur: p, libelle: p })), ot.priorite)}</select></div>
      <div class="champ"><label class="libelle" for="ot-motif-priorite">Motif <span class="requis" aria-hidden="true">*</span></label>
        <textarea id="ot-motif-priorite" rows="3" data-dictee required aria-required="true"></textarea>
        <p class="erreur-champ" hidden></p></div></div>`);
    const choix = await UI.fenetre({
      titre: 'Modifier la priorité de ' + ot.id, contenu,
      boutons: [{ libelle: 'Annuler', valeur: null, classe: 'btn-fantome' }, { libelle: 'Enregistrer', valeur: 'ok', classe: 'btn-primaire', defaut: true }],
      avantFermeture() {
        const erreur = UI.$('.erreur-champ', contenu);
        let message = '';
        if (UI.$('#ot-nouvelle-priorite', contenu).value === ot.priorite) message = 'Choisissez une priorité différente de l\'actuelle.';
        else if (!UI.$('#ot-motif-priorite', contenu).value.trim()) message = 'Le motif est obligatoire.';
        erreur.textContent = message;
        erreur.hidden = !message;
        return !message;
      },
    });
    if (choix !== 'ok') return;
    const nouvelle = UI.$('#ot-nouvelle-priorite', contenu).value;
    const motif = UI.$('#ot-motif-priorite', contenu).value.trim();
    const reussi = await pendant(null, () => changerPriorite(ot.id, nouvelle, motif), 'changement de priorité');
    if (reussi === undefined) return;
    await apresEnregistrement();
    UI.toast('Priorité ' + ot.priorite + ' → ' + nouvelle + ' enregistrée.', 'succes');
  }

  async function lancerOtLie(ot) {
    const id = await pendant(UI.$('#ot-lie'), () => creerOtLie(ot.id), 'création d\'un OT lié');
    if (!id) return;
    UI.toast('OT lié ' + id + ' créé (reprise de ' + ot.id + ').', 'succes');
    App.naviguer('#/ot/' + encodeURIComponent(id));
  }

  /** Avertissement RG8 affichable (texte complet, avec le nom du technicien et l'équipement). */
  function bandeauHabilitation(equipementId, technicienId, date) {
    const equipement = Donnees.trouver('equipements', equipementId);
    const jour = texte(date).slice(0, 10) || aujourdhui();
    const manquantes = habilitationsManquantes(equipement, technicienId, jour);
    return UI.bandeau('attention', UI.html`<b>Avertissement habilitation :</b> ${nomTechnicien(technicienId)} (${technicienId})
      n'a pas d'habilitation ${manquantes.join(', ')} valide au ${UI.dateFr(jour)}, exigée pour ${repereEquipement(equipementId)}.
      L'affectation reste possible ; l'avertissement est tracé au journal.`);
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
