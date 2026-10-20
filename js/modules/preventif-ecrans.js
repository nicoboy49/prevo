'use strict';
// Preventif (3/4) — écrans du préventif (ARCHITECTURE.md §14.3, brief §9 E8) :
//    9. Petits outils d'affichage (équipement, périodicité, badge d'état)
//   10. Liste des gammes (#/preventif?onglet=gammes|calendrier) : filtres statut et équipement,
//       tableau (cartes sur téléphone) ; responsable : « Nouvelle gamme », « Générer les OT échus »
//   11. Formulaire d'une gamme (#/preventif/gamme/nouvelle, et sur la fiche pour le responsable)
//   12. Fiche d'une gamme (#/preventif/gamme/<id>) : état, paramètres, check-list, OT de la gamme
//   13. Éditeur de check-list : ajout, ordre ↑/↓, modification, suppression (journalisée, D26)
//   14. Enregistrement des écrans
// Profils : le technicien consulte (lecture seule), le responsable crée et modifie, le demandeur
// n'a pas accès. L'onglet « Calendrier » est dessiné par preventif-calendrier.js (chargé après ce
// fichier : appelé par une fonction relais). Complète l'objet Preventif.

Object.assign(Preventif, (() => {

  // Constantes, règles et outils de preventif-regles.js et preventif-ecritures.js.
  const { DECLENCHEURS, STATUTS_GAMME } = Preventif;
  const { texte, contexteCalcul, evaluerGamme, nombreDeSemaines, operationsDeGamme } = Preventif.interne;

  const ONGLETS = ['gammes', 'calendrier'];
  const TONS_ETAT = { echue: 'ko', ot_ouvert: 'cyan', bientot: 'attention', a_jour: 'ok', incomplete: 'violet', inactive: 'neutre' };
  const RANGS_ETAT = Object.keys(STATUTS_GAMME);            // du plus urgent au moins urgent
  const LIBELLES_COURTS = { date: 'Date', compteur: 'Compteur', seuil: 'Seuil' };
  const TABLES_ECRANS = ['gammes', 'gamme_operations', 'ordres_travail', 'releves', 'compteurs', 'equipements'];

  // Filtres de la liste, gardés pendant la session (comme ceux de la liste des OT).
  const memoire = { statut: '', equipement: '' };

  // ===========================================================================================
  // 9. Petits outils d'affichage
  // ===========================================================================================

  function comparerTextes(a, b) {
    return String(a).localeCompare(String(b), 'fr', { numeric: true, sensitivity: 'base' });
  }

  function repere(equipementId) {
    const equipement = Donnees.trouver('equipements', equipementId);
    return equipement ? (equipement.repere || equipement.id) : texte(equipementId);
  }

  function libelleEquipement(equipementId) {
    const equipement = Donnees.trouver('equipements', equipementId);
    return equipement ? repere(equipementId) + ' — ' + texte(equipement.designation) : texte(equipementId);
  }

  function uniteCompteur(gamme) {
    const compteur = Donnees.trouver('compteurs', gamme.compteur_id);
    return compteur ? texte(compteur.unite) : '';
  }

  /** « 2 000 h » : nombre à la française et unité, jamais coupés l'un de l'autre (espace insécable). */
  function avecUnite(valeur, unite) {
    return UI.nombreFr(valeur) + (unite ? ' ' + unite : '');
  }

  /** « tous les 30 j », « toutes les 2 000 h », « seuil 0,8 bar » (vide si non renseignée). */
  function periodicite(gamme) {
    const declencheur = texte(gamme.declencheur) || 'date';
    if (declencheur === 'date') return gamme.periodicite_jours ? 'tous les ' + UI.nombreFr(gamme.periodicite_jours) + ' j' : '';
    if (declencheur === 'compteur') return gamme.periodicite_unites ? 'toutes les ' + avecUnite(gamme.periodicite_unites, uniteCompteur(gamme)) : '';
    return texte(gamme.seuil) ? 'seuil ' + avecUnite(gamme.seuil, uniteCompteur(gamme)) : '';
  }

  /** Badge du statut calculé (texte toujours affiché ; la couleur aide seulement). */
  function badgeEtat(etat) {
    return UI.badgeStatut(STATUTS_GAMME[etat.statut] || etat.statut, TONS_ETAT[etat.statut]);
  }

  function lienOt(otId) {
    return otId ? UI.html`<a href="#/ot/${encodeURIComponent(otId)}">${otId}</a>` : '';
  }

  /** Raison de l'état ; pour une gamme qui a un OT ouvert, son numéro devient un lien vers l'OT. */
  function raisonHtml(etat) {
    const id = etat.otOuvertId;
    if (!id || !etat.raison.startsWith(id)) return UI.html`<span class="pv-raison">${etat.raison}</span>`;
    return UI.html`<span class="pv-raison">${lienOt(id)}${etat.raison.slice(id.length)}</span>`;
  }

  function lienGamme(gamme) {
    return UI.html`<a href="#/preventif/gamme/${encodeURIComponent(gamme.id)}">${texte(gamme.libelle) || gamme.id}</a>`;
  }

  /** Échéance affichée ; celle d'une gamme au compteur est une estimation. */
  function echeanceHtml(gamme, etat) {
    if (!etat.echeance) return '';
    const estimee = texte(gamme.declencheur) === 'compteur';
    return UI.html`<span class="sans-coupure">${UI.dateFr(etat.echeance)}</span>${estimee ? UI.html` <span class="pv-estimee">(estimée)</span>` : ''}`;
  }

  /** Gammes et leur état (RG5), de la plus urgente à la moins urgente : [{ gamme, etat }]. */
  function gammesAvecEtat() {
    const jour = Donnees.aujourdhui();
    const contexte = contexteCalcul();
    const rang = (entree) => RANGS_ETAT.indexOf(entree.etat.statut);
    return Donnees.lignes('gammes').map((gamme) => ({ gamme, etat: evaluerGamme(gamme, jour, contexte) }))
      .sort((a, b) => rang(a) - rang(b) || comparerTextes(a.etat.echeance || '9999', b.etat.echeance || '9999')
        || comparerTextes(a.gamme.id, b.gamme.id));
  }

  function optionsHtml(liste, valeurChoisie) {
    return UI.html`${liste.map((o) => UI.html`<option value="${o.valeur}"${o.valeur === valeurChoisie ? UI.brut(' selected') : ''}>${o.libelle}</option>`)}`;
  }

  /** Exécute une action d'un bouton : boutons de la zone désactivés pendant l'action, erreur signalée. Vrai si réussie. */
  async function agir(zone, action, contexte) {
    const boutons = UI.$$('button', zone).filter((bouton) => !bouton.disabled);
    boutons.forEach((bouton) => { bouton.disabled = true; });
    try {
      await action();
      return true;
    } catch (erreur) {
      App.signalerErreur(erreur, contexte);
      return false;
    } finally {
      boutons.forEach((bouton) => { bouton.disabled = false; });
    }
  }

  // ===========================================================================================
  // 10. Liste des gammes (#/preventif)
  // ===========================================================================================

  // Paramètres d'adresse : ?onglet=gammes|calendrier, ?statut=echue…, ?equipement=EQ-0001.
  function lireFiltresAdresse(requete) {
    if (requete.has('statut')) memoire.statut = RANGS_ETAT.includes(requete.get('statut')) ? requete.get('statut') : '';
    if (requete.has('equipement')) memoire.equipement = requete.get('equipement');
  }

  /** L'onglet ouvert est gardé dans l'adresse (#/preventif?onglet=calendrier), sans réafficher l'écran. */
  function memoriserOnglet(onglet) {
    const adresse = '#/preventif?onglet=' + onglet;
    if (location.hash === adresse) return;
    try { history.replaceState(history.state, '', adresse); } catch (erreur) { /* adresse gardée telle quelle */ }
  }

  function afficherListe(conteneur, parametres) {
    const requete = parametres.requete;
    lireFiltresAdresse(requete);
    const onglet = ONGLETS.includes(requete.get('onglet')) ? requete.get('onglet') : 'gammes';
    const toutes = gammesAvecEtat();
    const semaines = nombreDeSemaines();
    UI.remplir(conteneur, UI.html`
      <div class="preventif">
        <div class="entete-page">
          <div><h1>Préventif</h1><p>Gammes de maintenance préventive, échéances et calendrier des ${semaines} prochaines semaines.</p></div>
          ${App.estResponsable() ? UI.html`<div class="actions">
            <button type="button" class="btn btn-secondaire" id="pv-generer">${UI.icone('actualiser')}Générer les OT échus</button>
            <a class="btn btn-primaire" id="pv-nouvelle" href="#/preventif/gamme/nouvelle">${UI.icone('ajouter')}Nouvelle gamme</a>
          </div>` : ''}
        </div>
        <div class="pv-onglets"></div>
      </div>`);
    const bouton = UI.$('#pv-generer', conteneur);
    if (bouton) bouton.addEventListener('click', () => genererDepuisBouton(bouton));
    UI.onglets(UI.$('.pv-onglets', conteneur), [
      { id: 'gammes', libelle: 'Gammes', compteur: toutes.length, afficher: (panneau) => afficherGammes(panneau, toutes) },
      { id: 'calendrier', libelle: 'Calendrier ' + semaines + ' semaines', afficher: (panneau) => afficherCalendrier(panneau) },
    ], { actif: onglet, libelle: 'Vues du préventif', surChangement: memoriserOnglet });
  }

  // Relais vers preventif-calendrier.js (chargé après ce fichier).
  function afficherCalendrier(panneau) {
    Preventif.interne.afficherCalendrier(panneau);
  }

  /** Bouton « Générer les OT échus » (responsable) : RG5 à la demande, puis réaffichage. */
  async function genererDepuisBouton(bouton) {
    bouton.disabled = true;
    bouton.setAttribute('aria-busy', 'true');
    try {
      const crees = await Preventif.genererOTEchus();
      UI.toast(Preventif.texteGeneration(crees.length) + '.', crees.length ? 'succes' : 'info');
      await App.reafficher();
    } catch (erreur) {
      App.signalerErreur(erreur, 'génération des OT préventifs');
    } finally {
      bouton.disabled = false;
      bouton.removeAttribute('aria-busy');
    }
  }

  function barreFiltresHtml(toutes) {
    const statuts = RANGS_ETAT.map((statut) => ({
      valeur: statut, libelle: STATUTS_GAMME[statut] + ' (' + toutes.filter((e) => e.etat.statut === statut).length + ')',
    }));
    const identifiants = new Set(toutes.map((e) => e.gamme.equipement_id));
    if (memoire.equipement) identifiants.add(memoire.equipement);
    const equipements = Array.from(identifiants).map((id) => ({ valeur: id, libelle: libelleEquipement(id) }))
      .sort((a, b) => comparerTextes(a.libelle, b.libelle));
    return UI.html`
      <form class="filtres pv-filtres" id="pv-filtres" data-hors-saisie role="search" aria-label="Filtrer les gammes">
        <label class="visuellement-cache" for="pv-filtre-statut">Statut</label>
        <select id="pv-filtre-statut" name="statut">${optionsHtml([{ valeur: '', libelle: 'Tous les statuts' }].concat(statuts), memoire.statut)}</select>
        <label class="visuellement-cache" for="pv-filtre-equipement">Équipement</label>
        <select id="pv-filtre-equipement" name="equipement">${optionsHtml([{ valeur: '', libelle: 'Tous les équipements' }].concat(equipements), memoire.equipement)}</select>
      </form>`;
  }

  function colonnesListe() {
    return [
      { cle: 'equipement', libelle: 'Équipement', valeurTri: (l) => repere(l.gamme.equipement_id),
        rendu: (l) => UI.html`<b class="sans-coupure">${repere(l.gamme.equipement_id)}</b>` },
      { cle: 'libelle', libelle: 'Gamme', classe: 'pv-col-gamme', valeurTri: (l) => l.gamme.libelle,
        rendu: (l) => UI.html`${lienGamme(l.gamme)} <span class="pv-id">${l.gamme.id}</span>` },
      { cle: 'declencheur', libelle: 'Déclencheur · périodicité', valeurTri: (l) => l.gamme.declencheur,
        rendu: (l) => UI.html`${LIBELLES_COURTS[l.gamme.declencheur] || l.gamme.declencheur}<span class="pv-sous">${periodicite(l.gamme)}</span>` },
      { cle: 'derniere', libelle: 'Dernière réalisation', valeurTri: (l) => l.gamme.derniere_realisation,
        rendu: (l) => UI.dateFr(l.gamme.derniere_realisation) },
      { cle: 'echeance', libelle: 'Échéance', valeurTri: (l) => l.etat.echeance, rendu: (l) => echeanceHtml(l.gamme, l.etat) },
      // Statut : badge, raison et, pour une gamme qui a un OT ouvert, le lien vers cet OT.
      { cle: 'statut', libelle: 'Statut', classe: 'pv-col-statut',
        valeurTri: (l) => String(RANGS_ETAT.indexOf(l.etat.statut)) + (l.etat.echeance || '9999'),
        rendu: (l) => UI.html`${badgeEtat(l.etat)}${raisonHtml(l.etat)}` },
    ];
  }

  function cartesHtml(liste) {
    if (!liste.length) return UI.html`<li>${UI.vide('Aucune gamme', 'Aucune gamme ne correspond à ces filtres.', 'preventif')}</li>`;
    return UI.html`${liste.map(({ gamme, etat }) => UI.html`<li><div class="carte-ligne">
      <div class="carte-tete"><b>${repere(gamme.equipement_id)}</b>${badgeEtat(etat)}</div>
      <div class="carte-titre">${lienGamme(gamme)}</div>
      <div class="carte-meta"><span>${periodicite(gamme)}</span>
        ${etat.echeance ? UI.html`<span>Échéance ${echeanceHtml(gamme, etat)}</span>` : ''}
        ${raisonHtml(etat)}</div>
    </div></li>`)}`;
  }

  function afficherGammes(panneau, toutes) {
    UI.remplir(panneau, UI.html`
      ${barreFiltresHtml(toutes)}
      <p class="note pv-compteur" id="pv-compteur" role="status"></p>
      <div class="carte pv-liste-tableau"></div>
      <ul class="liste-cartes pv-liste-cartes"></ul>`);
    const tableau = UI.tableau({ colonnes: colonnesListe(), lignes: [], libelle: 'Gammes de préventif',
      vide: 'Aucune gamme ne correspond à ces filtres.' });
    UI.$('.pv-liste-tableau', panneau).appendChild(tableau);

    function rafraichir() {
      const affichees = toutes.filter(({ gamme, etat }) => (!memoire.statut || etat.statut === memoire.statut)
        && (!memoire.equipement || gamme.equipement_id === memoire.equipement));
      tableau.mettreAJour(affichees);
      UI.remplir(UI.$('.pv-liste-cartes', panneau), cartesHtml(affichees));
      UI.$('#pv-compteur', panneau).textContent = affichees.length + ' gamme(s) sur ' + toutes.length;
    }

    const formulaire = UI.$('#pv-filtres', panneau);
    formulaire.addEventListener('change', () => { Object.assign(memoire, UI.lireFormulaire(formulaire)); rafraichir(); });
    formulaire.addEventListener('submit', (evenement) => evenement.preventDefault());
    rafraichir();
  }

  // ===========================================================================================
  // 11. Formulaire d'une gamme (création, modification par le responsable)
  // ===========================================================================================

  // Champs propres à un déclencheur : masqués pour les autres (ils restent dans le formulaire et
  // gardent leur valeur ; les règles n'utilisent que ceux du déclencheur choisi).
  const DECLENCHEURS_DU_CHAMP = {
    periodicite_jours: ['date'], avance_jours: ['date'], prochaine_echeance: ['date'],
    compteur_id: ['compteur', 'seuil'], periodicite_unites: ['compteur'], seuil: ['seuil'],
    releve_derniere_realisation: ['compteur', 'seuil'],
  };

  const AIDES = {
    periodicite_jours: 'Obligatoire pour une gamme par date (ex. 30 pour une gamme mensuelle).',
    avance_jours: 'L\'OT est généré ce nombre de jours avant l\'échéance.',
    compteur_id: 'Compteur (heures, cycles) ou point de mesure (pression, température…).',
    periodicite_unites: 'Obligatoire pour une gamme au compteur (ex. 2000 pour 2 000 heures).',
    seuil: 'La gamme est échue quand un relevé atteint ce seuil.',
    derniere_realisation: 'Mise à jour automatiquement à la clôture technique d\'un OT de la gamme.',
    releve_derniere_realisation: 'Valeur du compteur à la dernière réalisation : base du prochain déclenchement.',
    prochaine_echeance: 'Laissez vide pour la calculer : dernière réalisation + périodicité.',
    temps_prevu_h: 'Recopié dans chaque OT généré.',
  };

  const CHAMPS_DU_FORMULAIRE = ['periodicite_jours', 'compteur_id', 'periodicite_unites', 'seuil', 'avance_jours',
    'derniere_realisation', 'releve_derniere_realisation', 'prochaine_echeance', 'temps_prevu_h'];

  function definitionChamp(nom) {
    return Schema.table('gammes').champs.find((champ) => champ.nom === nom);
  }

  function listeEquipements(valeur) {
    return Donnees.lignes('equipements').filter((e) => e.actif !== '0' || e.id === valeur)
      .map((e) => ({ valeur: e.id, libelle: libelleEquipement(e.id) }))
      .sort((a, b) => comparerTextes(a.libelle, b.libelle));
  }

  function listeCompteurs() {
    return Donnees.lignes('compteurs')
      .map((c) => ({ valeur: c.id, libelle: repere(c.equipement_id) + ' — ' + texte(c.libelle) + (c.unite ? ' (' + c.unite + ')' : '') + ' · ' + c.id }))
      .sort((a, b) => comparerTextes(a.libelle, b.libelle));
  }

  function formulaireGamme(gamme, valeursInitiales) {
    const valeur = (nom) => (gamme ? gamme[nom] : (valeursInitiales || {})[nom]);
    const formulaire = UI.element(UI.html`<form class="form-grille pv-formulaire" id="pv-formulaire-gamme" novalidate></form>`);
    const ajouter = (nom, bloc, large) => {
      if (large) bloc.classList.add('large');
      if (DECLENCHEURS_DU_CHAMP[nom]) bloc.dataset.declencheurs = DECLENCHEURS_DU_CHAMP[nom].join(' ');
      formulaire.appendChild(bloc);
    };
    ajouter('equipement_id', UI.champ(definitionChamp('equipement_id'), valeur('equipement_id'),
      { liste: listeEquipements(valeur('equipement_id')), obligatoire: true }));
    ajouter('libelle', UI.champ(definitionChamp('libelle'), valeur('libelle'), { obligatoire: true, attributs: { maxlength: '160' } }));
    ajouter('declencheur', UI.champ(Object.assign({}, definitionChamp('declencheur'), { type: 'ref' }), valeur('declencheur') || 'date', {
      obligatoire: true, liste: Object.keys(DECLENCHEURS).map((cle) => ({ valeur: cle, libelle: DECLENCHEURS[cle] })),
    }));
    CHAMPS_DU_FORMULAIRE.forEach((nom) => ajouter(nom, UI.champ(definitionChamp(nom), valeur(nom), {
      aide: AIDES[nom], liste: nom === 'compteur_id' ? listeCompteurs() : undefined,
    })));
    ajouter('consignes', UI.champ(definitionChamp('consignes'), valeur('consignes'),
      { aide: 'Recopiées dans chaque OT généré (sécurité, consignation…).' }), true);
    ajouter('actif', UI.champ(definitionChamp('actif'), gamme ? gamme.actif : '1', { libelle: 'Gamme active (elle génère des OT)' }), true);
    formulaire.appendChild(UI.element(UI.html`<p class="mention-requis large"><span class="requis" aria-hidden="true">*</span>champ obligatoire</p>`));
    formulaire.appendChild(UI.element(UI.html`<div class="actions">
      <button type="submit" class="btn btn-primaire">${UI.icone('valider')}${gamme ? 'Enregistrer la gamme' : 'Créer la gamme'}</button>
      <a class="btn btn-fantome" href="${gamme ? '#/preventif/gamme/' + encodeURIComponent(gamme.id) : '#/preventif'}">Annuler</a>
    </div>`));

    const choixDeclencheur = formulaire.querySelector('[name="declencheur"]');
    const montrerChampsDuDeclencheur = () => UI.$$('[data-declencheurs]', formulaire).forEach((bloc) => {
      bloc.hidden = !bloc.dataset.declencheurs.split(' ').includes(choixDeclencheur.value);
    });
    choixDeclencheur.addEventListener('change', montrerChampsDuDeclencheur);
    montrerChampsDuDeclencheur();
    brancherEnregistrement(formulaire, gamme);
    return formulaire;
  }

  function afficherErreurs(formulaire, erreurs) {
    UI.$$('.champ', formulaire).forEach((bloc) => UI.erreurChamp(formulaire, bloc.dataset.champ, ''));
    erreurs.forEach((erreur) => UI.erreurChamp(formulaire, erreur.nom, erreur.message));
    const premier = UI.$('[aria-invalid="true"]', formulaire);
    if (premier) premier.focus();
  }

  function brancherEnregistrement(formulaire, gamme) {
    let enCours = false;
    formulaire.addEventListener('submit', async (evenement) => {
      evenement.preventDefault();
      if (enCours) return;
      const valeurs = UI.lireFormulaire(formulaire);
      const erreurs = UI.verifierFormulaire(formulaire);
      Preventif.verifierGamme(valeurs).forEach((erreur) => { if (!erreurs.some((e) => e.nom === erreur.nom)) erreurs.push(erreur); });
      afficherErreurs(formulaire, erreurs);
      if (erreurs.length) return;
      const bouton = UI.$('button[type=submit]', formulaire);
      enCours = true;
      bouton.disabled = true;
      bouton.setAttribute('aria-busy', 'true');
      try {
        if (gamme) {
          const changes = await Preventif.modifierGamme(gamme.id, valeurs);
          App.marquerSaisie(false);
          UI.toast(changes.length ? 'Gamme enregistrée.' : 'Aucune modification à enregistrer.', changes.length ? 'succes' : 'info');
          await App.reafficher();
        } else {
          const id = await Preventif.creerGamme(valeurs);
          App.marquerSaisie(false);
          UI.toast('Gamme ' + id + ' créée : ajoutez maintenant sa check-list.', 'succes');
          App.naviguer('#/preventif/gamme/' + encodeURIComponent(id));
        }
      } catch (erreur) {
        App.signalerErreur(erreur, 'enregistrement de la gamme');
      } finally {
        enCours = false;
        bouton.disabled = false;
        bouton.removeAttribute('aria-busy');
      }
    });
  }

  function afficherNouvelle(conteneur, parametres) {
    UI.remplir(conteneur, UI.html`
      <div class="preventif">
        <div class="entete-page"><div>
          <div class="fil"><a href="#/preventif">Préventif</a> <span aria-hidden="true">›</span> <span>Nouvelle gamme</span></div>
          <h1>Nouvelle gamme</h1>
          <p>La check-list (les opérations à réaliser) se remplit ensuite, sur la fiche de la gamme.</p>
        </div></div>
        <article class="carte pv-carte-formulaire"></article>
      </div>`);
    const equipement = parametres.requete.get('equipement') || '';
    UI.$('.pv-carte-formulaire', conteneur).appendChild(formulaireGamme(null, { equipement_id: equipement, declencheur: 'date' }));
  }

  // ===========================================================================================
  // 12. Fiche d'une gamme (#/preventif/gamme/<id>)
  // ===========================================================================================

  function descriptionHtml(gamme, etat) {
    const declencheur = texte(gamme.declencheur) || 'date';
    const compteur = Donnees.trouver('compteurs', gamme.compteur_id);
    const releve = compteur ? Preventif.dernierReleve(compteur.id) : null;
    return UI.html`<dl class="valeurs">
      <dt>Équipement</dt><dd><a href="#/equipement/${encodeURIComponent(gamme.equipement_id)}">${libelleEquipement(gamme.equipement_id)}</a></dd>
      <dt>Déclencheur</dt><dd>${DECLENCHEURS[declencheur] || declencheur}</dd>
      <dt>Périodicité</dt><dd>${periodicite(gamme)}</dd>
      ${compteur ? UI.html`<dt>Compteur</dt><dd>${texte(compteur.libelle)} (${compteur.id})${releve
        ? UI.html` — dernier relevé ${avecUnite(releve.valeur, compteur.unite)} le ${UI.dateFr(releve.date)}` : ''}</dd>` : ''}
      ${declencheur === 'date' ? UI.html`<dt>Avance</dt><dd>${gamme.avance_jours ? gamme.avance_jours + ' j' : ''}</dd>` : ''}
      <dt>Dernière réalisation</dt><dd>${UI.dateFr(gamme.derniere_realisation)}${compteur && texte(gamme.releve_derniere_realisation)
        ? ' (' + avecUnite(gamme.releve_derniere_realisation, compteur.unite) + ')' : ''}</dd>
      <dt>Échéance</dt><dd>${echeanceHtml(gamme, etat)}</dd>
      <dt>Temps prévu</dt><dd>${gamme.temps_prevu_h ? UI.heures(gamme.temps_prevu_h) : ''}</dd>
      <dt>Consignes</dt><dd class="pv-texte">${gamme.consignes}</dd>
      <dt>Active</dt><dd>${gamme.actif === '0' ? 'non' : 'oui'}</dd>
    </dl>`;
  }

  function afficherOtsDeLaGamme(section, gammeId) {
    const ots = Donnees.lignes('ordres_travail').filter((ot) => ot.gamme_id === gammeId)
      .sort((a, b) => comparerTextes(b.date_creation, a.date_creation) || comparerTextes(b.id, a.id));
    UI.remplir(section, UI.html`<div class="entete-carte"><h2 id="pv-titre-ots">OT de la gamme</h2><span class="badge neutre">${ots.length}</span></div>`);
    section.appendChild(UI.tableau({
      colonnes: [
        { cle: 'id', libelle: 'N°', rendu: (ot) => lienOt(ot.id) },
        { cle: 'statut', libelle: 'Statut', rendu: (ot) => UI.badgeStatut(ot.statut) },
        { cle: 'date_prevue', libelle: 'Prévu le', rendu: (ot) => UI.dateFr(ot.date_prevue) },
        { cle: 'date_fin', libelle: 'Réalisé le', rendu: (ot) => UI.dateFr(ot.date_fin) },
      ],
      lignes: ots, libelle: 'OT de la gamme', classe: 'pv-table-ots', vide: 'Aucun OT pour cette gamme pour le moment.',
    }));
  }

  function afficherFiche(conteneur, parametres) {
    const gamme = Donnees.trouver('gammes', parametres.id);
    if (!gamme) {
      UI.remplir(conteneur, UI.html`<div class="preventif"><div class="entete-page"><div>
        <div class="fil"><a href="#/preventif">Préventif</a></div><h1>Gamme introuvable</h1></div></div>
        ${UI.vide('Gamme introuvable', 'Aucune gamme ne porte l\'identifiant « ' + parametres.id + ' ».', 'recherche')}</div>`);
      return;
    }
    App.definirTitre(gamme.id);
    const etat = Preventif.etatGamme(gamme);
    const responsable = App.estResponsable();
    UI.remplir(conteneur, UI.html`
      <div class="preventif pv-fiche" data-gamme="${gamme.id}">
        <div class="entete-page"><div>
          <div class="fil"><a href="#/preventif">Préventif</a> <span aria-hidden="true">›</span> <span>${gamme.id}</span></div>
          <h1><span class="pv-numero">${gamme.id}</span> ${texte(gamme.libelle)}</h1>
          <div class="pv-badges">${badgeEtat(etat)}${raisonHtml(etat)}</div>
        </div></div>
        <div class="pv-fiche-grille">
          <section class="carte pv-parametres" aria-labelledby="pv-titre-parametres">
            <div class="entete-carte"><h2 id="pv-titre-parametres">${responsable ? 'Paramètres de la gamme' : 'Gamme'}</h2></div>
            ${responsable ? '' : descriptionHtml(gamme, etat)}
          </section>
          <section class="carte pv-check-liste" aria-labelledby="pv-titre-check-liste"></section>
          <section class="carte pv-ots" aria-labelledby="pv-titre-ots"></section>
        </div>
      </div>`);
    if (responsable) UI.$('.pv-parametres', conteneur).appendChild(formulaireGamme(gamme));
    const checkListe = UI.$('.pv-check-liste', conteneur);
    afficherCheckListe(checkListe, gamme.id);
    if (responsable) brancherCheckListe(checkListe, gamme.id);
    afficherOtsDeLaGamme(UI.$('.pv-ots', conteneur), gamme.id);
  }

  // ===========================================================================================
  // 13. Éditeur de check-list (responsable) ; lecture seule pour le technicien
  // ===========================================================================================

  function operationHtml(operation, rang, total, responsable) {
    return UI.html`<li class="pv-operation" data-operation="${operation.id}">
      <span class="pv-rang" aria-hidden="true">${rang + 1}</span>
      <div class="pv-operation-texte"><span class="operation">${operation.operation}</span>
        ${operation.valeur_attendue ? UI.html`<span class="attendu">Attendu : ${operation.valeur_attendue}</span>` : ''}</div>
      ${responsable ? UI.html`<div class="pv-operation-actions">
        <button type="button" class="btn btn-fantome btn-icone" data-action="monter" title="Monter"
          aria-label="Monter l'opération ${rang + 1}"${rang === 0 ? UI.brut(' disabled') : ''}>↑</button>
        <button type="button" class="btn btn-fantome btn-icone" data-action="descendre" title="Descendre"
          aria-label="Descendre l'opération ${rang + 1}"${rang === total - 1 ? UI.brut(' disabled') : ''}>↓</button>
        <button type="button" class="btn btn-fantome" data-action="modifier">Modifier</button>
        <button type="button" class="btn btn-danger" data-action="supprimer">Supprimer</button>
      </div>` : ''}
    </li>`;
  }

  function formulaireAjoutHtml() {
    return UI.html`<form class="form-ligne pv-ajout-operation" id="pv-ajout-operation" novalidate>
      <div class="champ"><label class="libelle" for="pv-nouvelle-operation">Nouvelle opération <span class="requis" aria-hidden="true">*</span></label>
        <input type="text" id="pv-nouvelle-operation" name="operation" maxlength="200" autocomplete="off"
          placeholder="Ex. Contrôler la tension de la courroie" aria-describedby="pv-erreur-operation"></div>
      <div class="champ"><label class="libelle" for="pv-nouvelle-attendue">Valeur attendue</label>
        <input type="text" id="pv-nouvelle-attendue" name="valeur_attendue" maxlength="120" autocomplete="off" placeholder="Ex. Flèche de 10 à 15 mm"></div>
      <button type="submit" class="btn btn-secondaire">${UI.icone('ajouter')}Ajouter</button>
      <p class="erreur-champ" id="pv-erreur-operation" role="alert" hidden></p>
    </form>`;
  }

  function afficherCheckListe(section, gammeId) {
    const operations = operationsDeGamme(gammeId);
    const responsable = App.estResponsable();
    UI.remplir(section, UI.html`
      <div class="entete-carte"><h2 id="pv-titre-check-liste">Check-list</h2><span class="badge neutre">${operations.length}</span></div>
      ${operations.length
        ? UI.html`<ol class="pv-operations">${operations.map((op, rang) => operationHtml(op, rang, operations.length, responsable))}</ol>`
        : UI.html`<p class="muted">Aucune opération${responsable ? ' : ajoutez ci-dessous les opérations à réaliser, dans l\'ordre.' : '.'}</p>`}
      ${responsable ? formulaireAjoutHtml() : ''}
      <p class="note">Chaque OT généré reçoit une copie de cette check-list : la modifier ne change pas les OT déjà créés.</p>`);
  }

  /** Fenêtre de modification d'une opération ; vrai si elle a été enregistrée. */
  async function modifierDansFenetre(section, operationId) {
    const operation = Donnees.trouver('gamme_operations', operationId);
    if (!operation) return true;                                   // déjà supprimée : on réaffiche
    const contenu = UI.element(UI.html`<div class="form-colonne">
      <div class="champ"><label class="libelle" for="pv-modif-operation">Opération <span class="requis" aria-hidden="true">*</span></label>
        <input type="text" id="pv-modif-operation" maxlength="200" aria-describedby="pv-modif-erreur"></div>
      <div class="champ"><label class="libelle" for="pv-modif-attendue">Valeur attendue</label>
        <input type="text" id="pv-modif-attendue" maxlength="120"></div>
      <p class="erreur-champ" id="pv-modif-erreur" role="alert" hidden></p>
    </div>`);
    const champOperation = UI.$('#pv-modif-operation', contenu);
    const champAttendue = UI.$('#pv-modif-attendue', contenu);
    champOperation.value = operation.operation;
    champAttendue.value = operation.valeur_attendue;
    const choix = await UI.fenetre({
      titre: 'Modifier l\'opération', contenu,
      boutons: [{ libelle: 'Annuler', valeur: null, classe: 'btn-fantome' },
        { libelle: 'Enregistrer', valeur: 'ok', classe: 'btn-primaire', defaut: true }],
      avantFermeture(valeur) {
        if (valeur !== 'ok' || champOperation.value.trim()) return true;
        const erreur = UI.$('#pv-modif-erreur', contenu);
        erreur.textContent = 'Décrivez l\'opération à réaliser.';
        erreur.hidden = false;
        champOperation.focus();
        return false;
      },
    });
    if (choix !== 'ok') return false;
    return agir(section, () => Preventif.modifierOperation(operationId,
      { operation: champOperation.value, valeur_attendue: champAttendue.value }), 'modification de l\'opération');
  }

  /** Suppression après confirmation (D26 : seule suppression permise, inscrite au journal). */
  async function supprimerAvecConfirmation(section, operationId) {
    const operation = Donnees.trouver('gamme_operations', operationId);
    if (!operation) return true;
    const confirme = await UI.confirmer('Supprimer l\'opération « ' + operation.operation + ' » de la check-list ? '
      + 'La suppression est inscrite au journal ; les OT déjà créés gardent leur copie.',
    { titre: 'Supprimer une opération', oui: 'Supprimer', danger: true });
    if (!confirme) return false;
    const fait = await agir(section, () => Preventif.supprimerOperation(operationId), 'suppression de l\'opération');
    if (fait) UI.toast('Opération supprimée (inscrite au journal).', 'succes');
    return true;
  }

  /** Écouteurs de l'éditeur, posés UNE fois sur la carte (délégation) : la carte est redessinée après chaque action. */
  function brancherCheckListe(section, gammeId) {
    const redessiner = (operationId, action) => {
      afficherCheckListe(section, gammeId);
      const bouton = operationId ? UI.$('[data-operation="' + operationId + '"] [data-action="' + action + '"]', section) : null;
      if (bouton && !bouton.disabled) bouton.focus();
    };
    section.addEventListener('submit', async (evenement) => {
      evenement.preventDefault();
      const formulaire = evenement.target;
      const valeurs = UI.lireFormulaire(formulaire);
      const erreur = UI.$('#pv-erreur-operation', formulaire);
      if (!valeurs.operation) {
        erreur.textContent = 'Décrivez l\'opération à réaliser.';
        erreur.hidden = false;
        UI.$('#pv-nouvelle-operation', formulaire).focus();
        return;
      }
      if (!await agir(section, () => Preventif.ajouterOperation(gammeId, valeurs), 'ajout d\'une opération')) return;
      redessiner();
      UI.$('#pv-nouvelle-operation', section).focus();
    });
    section.addEventListener('click', async (evenement) => {
      const bouton = evenement.target.closest('button[data-action]');
      if (!bouton || !section.contains(bouton)) return;
      const operationId = bouton.closest('[data-operation]').dataset.operation;
      const action = bouton.dataset.action;
      let fait = false;
      if (action === 'monter' || action === 'descendre') {
        fait = await agir(section, () => Preventif.deplacerOperation(operationId, action === 'monter' ? -1 : 1), 'ordre de la check-list');
      } else if (action === 'modifier') {
        fait = await modifierDansFenetre(section, operationId);
      } else if (action === 'supprimer') {
        fait = await supprimerAvecConfirmation(section, operationId);
      }
      if (fait) redessiner(operationId, action);
    });
  }

  // ===========================================================================================
  // 14. Enregistrement des écrans (App est chargé après les modules, §8)
  // ===========================================================================================

  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'preventif', route: /^#\/preventif$/, titre: 'Préventif',
      menu: { libelle: 'Préventif', icone: 'preventif', ordre: 35 },
      profils: ['technicien', 'responsable'], tables: TABLES_ECRANS,
      afficher: afficherListe,
    });
    App.ecran({
      id: 'preventif-gamme-nouvelle', route: /^#\/preventif\/gamme\/nouvelle$/, titre: 'Nouvelle gamme',
      parent: 'preventif', profils: ['responsable'], tables: ['equipements', 'compteurs'],
      afficher: afficherNouvelle,
    });
    App.ecran({
      id: 'preventif-gamme', route: /^#\/preventif\/gamme\/(?<id>(?!nouvelle$)[^/?]+)$/, titre: 'Gamme de préventif',
      parent: 'preventif', profils: ['technicien', 'responsable'], tables: TABLES_ECRANS,
      afficher: afficherFiche,
    });
  });

  return {};
})());
