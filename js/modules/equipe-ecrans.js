'use strict';
// Equipe (3/3) — écran « Équipe » (ARCHITECTURE.md §15.8, §15.2) : liste #/equipe (?etat=actifs|
// inactifs|tous, ?recherche=, ?filtre=a-renouveler : habilitations échues ou à renouveler, lien de
// l'accueil), création #/equipe/nouveau, fiche #/equipe/<id> (habilitations qui comptent avec leur
// statut, renouvellement, correction, historique) ; puis l'enregistrement des écrans auprès d'App.
// Profils : le responsable a tous les boutons ; le technicien consulte, SANS aucun taux horaire (ni
// à l'écran ni dans le DOM : la valeur n'est jamais écrite dans la page) ; le demandeur n'a pas accès.
// Lot 7 : le bouton « Accès » (comptes, appareils, journal des connexions) mène à #/equipe/acces,
// écran de equipe-acces.js, responsable en mode serveur. Complète l'objet Equipe.

Object.assign(Equipe, (() => {

  // Règles et outils de equipe-regles.js et equipe-ecritures.js.
  const { texte, dateIso, estActif, verifierHabilitation, CAPACITE_MAX_H } = Equipe.interne;
  const { STATUTS_HABILITATION, habilitationsQuiComptent, aRenouveler } = Equipe;

  const FILTRE_A_RENOUVELER = 'a-renouveler';
  const ETATS = ['actifs', 'inactifs', 'tous'];
  // Couleur de chaque statut d'une habilitation (code calculé par Equipe.etatHabilitation ; le texte dit toujours le
  // statut).
  const TONS = { 'pas encore valable': 'info', valide: 'ok', 'à renouveler': 'attention', 'échue': 'ko' };
  const CAPACITE_PAR_DEFAUT = '35';
  const STATUTS_OT_FERMES = ['Clôturé techniquement', 'Clôturé administrativement', 'Annulé'];

  // ===========================================================================================
  // 6. Petits outils d'écran
  // ===========================================================================================

  /** « Julien Moreau » : prénom puis nom (affichage). */
  function nomAffiche(technicien) {
    return [texte(technicien.prenom), texte(technicien.nom)].filter(Boolean).join(' ') || texte(technicien.id);
  }

  function lienTechnicien(technicien) {
    return UI.html`<a class="equipe-lien" href="#/equipe/${encodeURIComponent(technicien.id)}">${nomAffiche(technicien)}</a>`;
  }

  /** Libellé d'un filtre de la liste (actifs, inactifs, tous) ; lu à l'affichage. */
  function libelleEtat(valeur) {
    if (valeur === 'inactifs') return I18n.t('equipe.libelle_etat.techniciens_inactifs');
    if (valeur === 'tous') return I18n.t('equipe.libelle_etat.tous_techniciens');
    return I18n.t('equipe.libelle_etat.techniciens_actifs');
  }

  /** Statut d'une habilitation (code calculé par Equipe.etatHabilitation, jamais traduit) → libellé affiché. */
  function libelleStatut(statut) {
    if (statut === 'échue') return I18n.t('equipe.statut_habilitation.echue');
    if (statut === 'à renouveler') return I18n.t('equipe.statut_habilitation.a_renouveler');
    if (statut === 'pas encore valable') return I18n.t('equipe.statut_habilitation.pas_encore_valable');
    return I18n.t('equipe.statut_habilitation.valide');
  }

  function badgeEtat(etat) {
    return UI.badgeStatut(libelleStatut(etat.statut), TONS[etat.statut]);
  }

  /** « échéance le 02/12/2026 (dans 43 jours) », « échue depuis 142 jours », « sans échéance »… */
  function detailEtat(habilitation, etat) {
    if (etat.statut === 'pas encore valable') return I18n.t('equipe.detail_etat.valable_partir', { date_obtention: UI.dateFr(habilitation.date_obtention) });
    if (etat.sansEcheance) return I18n.t('equipe.detail_etat.sans_echeance');
    if (etat.joursRestants === null) return I18n.t('equipe.detail_etat.echeance_illisible_corrigez', { date_echeance: texte(habilitation.date_echeance) });
    const jours = Math.abs(etat.joursRestants);
    const date = UI.dateFr(habilitation.date_echeance);
    if (etat.joursRestants < 0) return I18n.t('equipe.detail_etat.echue_depuis', { date, n: jours });
    if (etat.joursRestants === 0) return I18n.t('equipe.detail_etat.echeance_aujourd_hui');
    return I18n.t('equipe.detail_etat.echeance_dans', { date, n: jours });
  }

  /** Statut d'une habilitation (badge + détail), repéré par son identifiant. */
  function statutHtml(habilitation, etat) {
    return UI.html`<span class="equipe-statut" data-habilitation="${habilitation.id}">${badgeEtat(etat)}
      <small class="equipe-detail">${detailEtat(habilitation, etat)}</small></span>`;
  }

  /** Puce « BR · échue » d'une liste : l'intitulé, et le statut en clair s'il n'est pas « valide ». */
  function puceHabilitation(habilitation, etat) {
    const ton = TONS[etat.statut] || 'neutre';
    const statut = libelleStatut(etat.statut);
    return UI.html`<span class="badge ${ton} equipe-habilitation" data-habilitation="${habilitation.id}" data-statut="${etat.statut}"
      title="${habilitation.intitule} : ${statut}">${habilitation.intitule}${etat.statut === 'valide' ? '' : ' · ' + statut}</span>`;
  }

  function habilitationsAvecEtat(technicienId, jour) {
    return habilitationsQuiComptent(technicienId).map((habilitation) => ({ habilitation, etat: Equipe.etatHabilitation(habilitation, jour) }));
  }

  function ordresOuverts(technicienId) {
    return Donnees.lignes('ordres_travail').filter((ot) => ot.technicien_id === technicienId && !STATUTS_OT_FERMES.includes(ot.statut));
  }

  function definitionChamp(table, nom, remplacement) {
    return Object.assign({}, Schema.champ(table, nom), remplacement || {});
  }

  /** Valeurs des champs nommés d'un bloc (une fenêtre vit déjà dans un <form>). */
  function lireChamps(bloc) {
    const valeurs = {};
    UI.$$('[name]', bloc).forEach((controle) => {
      valeurs[controle.name] = controle.type === 'checkbox' ? (controle.checked ? '1' : '0') : String(controle.value || '').trim();
    });
    return valeurs;
  }

  function afficherErreurs(bloc, erreurs) {
    UI.$$('.champ', bloc).forEach((champ) => UI.erreurChamp(bloc, champ.dataset.champ, ''));
    erreurs.forEach((erreur) => UI.erreurChamp(bloc, erreur.nom, erreur.message));
    const premier = UI.$('[aria-invalid="true"]', bloc);
    if (premier) premier.focus();
  }

  // Fenêtre de saisie : UI.fenetreAction (interface.js), commune aux écrans Contrôles et Équipe (lot 4).

  async function apresEcriture(message) {
    App.marquerSaisie(false);
    UI.toast(message, 'succes');
    await App.reafficher();
  }

  // ===========================================================================================
  // 7. Liste #/equipe et vue « à renouveler » (?filtre=a-renouveler)
  // ===========================================================================================

  function instrumentsHtml(jour) {
    const actifs = Donnees.lignes('techniciens').filter(estActif);
    const alertes = aRenouveler(jour);
    const echues = alertes.filter((alerte) => alerte.etat.statut === 'échue').length;
    const capacite = actifs.reduce((somme, technicien) => somme + (Donnees.nombre(technicien.capacite_h_semaine) || 0), 0);
    return UI.html`<div class="instruments equipe-instruments">
      <a href="#/equipe"><div class="lib">${I18n.t('equipe.libelle_etat.techniciens_actifs')}</div><div class="chiffre">${actifs.length}</div>
        <div class="comp">${I18n.t('equipe.instruments.inactifs', { n: Donnees.lignes('techniciens').length - actifs.length })}</div></a>
      <a class="${alertes.length ? 'ambre' : 'vert'}" href="#/equipe?filtre=${FILTRE_A_RENOUVELER}"><div class="lib">${I18n.t('equipe.instruments.habilitations_renouveler')}</div>
        <div class="chiffre">${alertes.length}</div><div class="comp">${echues ? I18n.t('equipe.instruments.dont_echues', { n: echues }) : I18n.t('equipe.instruments.echeance_60_jours')}</div></a>
      <div class="cyan"><div class="lib">${I18n.t('equipe.instruments.capacite_equipe')}</div><div class="chiffre">${I18n.t('equipe.instruments.capacite_h', { n: UI.nombreFr(capacite) })}</div>
        <div class="comp">${I18n.t('equipe.instruments.semaine_techniciens_actifs')}</div></div>
    </div>`;
  }

  function entete(responsable, sousTitre) {
    return UI.html`<div class="entete-page">
      <div><h1>${I18n.t('equipe.entete.equipe')}</h1><p>${sousTitre}</p></div>
      <div class="actions">${responsable && App.mode === 'serveur' ? UI.html`<a class="btn btn-secondaire" id="equipe-acces" href="#/equipe/acces">${UI.icone('cle')}${I18n.t('equipe.entete.acces')}</a>` : ''}
        ${responsable ? UI.html`<a class="btn btn-primaire" id="equipe-nouveau" href="#/equipe/nouveau">${UI.icone('ajouter')}${I18n.t('equipe.entete.ajouter_technicien')}</a>` : ''}</div>
    </div>`;
  }

  function colonnesListe(responsable, jour) {
    return [
      { cle: 'nom', libelle: I18n.t('commun.champ.technicien'), valeurTri: (t) => texte(t.nom) + ' ' + texte(t.prenom),
        rendu: (t) => UI.html`${lienTechnicien(t)}${estActif(t) ? '' : UI.html` <span class="badge neutre barre">${I18n.t('equipe.colonnes_liste.inactif')}</span>`}` },
      { cle: 'metier', libelle: I18n.t('equipe.colonnes_liste.metier') },
      { cle: 'capacite_h_semaine', libelle: I18n.t('equipe.colonnes_liste.capacite'), type: 'nombre', classe: 'sans-coupure',
        rendu: (t) => (texte(t.capacite_h_semaine) ? I18n.t('equipe.colonnes.capacite_h_sem', { n: UI.nombreFr(t.capacite_h_semaine) }) : '') },
      // Colonne du responsable seul : pour le technicien, la valeur n'est même pas lue.
      responsable && { cle: 'taux_horaire', libelle: I18n.t('equipe.colonnes_liste.taux_horaire'), type: 'nombre', classe: 'sans-coupure',
        rendu: (t) => (texte(t.taux_horaire) ? I18n.t('equipe.colonnes_liste.taux_par_heure', { taux: UI.euro(t.taux_horaire) }) : '') },
      { cle: 'habilitations', libelle: I18n.t('equipe.colonnes_liste.habilitations'), triable: false, classe: 'equipe-col-habilitations',
        rendu: (t) => UI.html`<span class="equipe-puces">${habilitationsAvecEtat(t.id, jour).map((h) => puceHabilitation(h.habilitation, h.etat))}</span>` },
    ].filter(Boolean);
  }

  function carteTechnicien(technicien, jour) {
    return UI.html`<a class="equipe-lien" href="#/equipe/${encodeURIComponent(technicien.id)}">
      <div class="carte-tete"><b>${nomAffiche(technicien)}</b>${estActif(technicien) ? '' : UI.html`<span class="badge neutre barre">${I18n.t('equipe.colonnes_liste.inactif')}</span>`}</div>
      <div class="carte-meta">${technicien.metier ? UI.html`<span>${technicien.metier}</span>` : ''}
        ${texte(technicien.capacite_h_semaine) ? UI.html`<span>${I18n.t('equipe.carte_technicien.capacite_h_semaine', { n: UI.nombreFr(technicien.capacite_h_semaine) })}</span>` : ''}</div>
      <div class="equipe-puces">${habilitationsAvecEtat(technicien.id, jour).map((h) => puceHabilitation(h.habilitation, h.etat))}</div></a>`;
  }

  function afficherListe(conteneur, parametres) {
    const requete = (parametres && parametres.requete) || new URLSearchParams();
    if (requete.get('filtre') === FILTRE_A_RENOUVELER) { afficherARenouveler(conteneur); return; }
    const jour = Donnees.aujourdhui();
    const responsable = App.estResponsable();
    const filtres = { recherche: requete.get('recherche') || '',
      etat: ETATS.includes(requete.get('etat')) ? requete.get('etat') : 'actifs' };
    UI.remplir(conteneur, UI.html`<div class="equipe">
      ${entete(responsable, I18n.t('equipe.liste.techniciens_capacite_habilitations_habilitation'))}
      ${responsable ? '' : UI.html`<p class="note equipe-consultation">${I18n.t('equipe.liste.consultation_seul_responsable_modifie')}</p>`}
      ${instrumentsHtml(jour)}
      <form class="filtres equipe-filtres" id="equipe-filtres" data-hors-saisie role="search" aria-label="${I18n.t('equipe.liste.filtrer_techniciens')}">
        <label class="visuellement-cache" for="equipe-recherche">${I18n.t('equipe.liste.rechercher_technicien')}</label>
        <input type="search" id="equipe-recherche" name="recherche" value="${filtres.recherche}" placeholder="${I18n.t('equipe.liste.nom_metier_habilitation')}" autocomplete="off">
        <label class="visuellement-cache" for="equipe-etat">${I18n.t('equipe.liste.techniciens_affiches')}</label>
        <select id="equipe-etat" name="etat">${ETATS.map((etat) => UI.html`<option value="${etat}"${etat === filtres.etat ? UI.brut(' selected') : ''}>${libelleEtat(etat)}</option>`)}</select>
      </form>
      <p class="note equipe-compteur" role="status"></p>
      <div class="carte equipe-liste"></div></div>`);
    const zone = UI.$('.equipe-liste', conteneur);
    const formulaire = UI.$('#equipe-filtres', conteneur);
    const techniciens = Donnees.lignes('techniciens').slice()
      .sort((a, b) => UI.comparerTextes(texte(a.nom) + ' ' + texte(a.prenom), texte(b.nom) + ' ' + texte(b.prenom)));

    function garder(technicien) {
      if (filtres.etat === 'actifs' && !estActif(technicien)) return false;
      if (filtres.etat === 'inactifs' && estActif(technicien)) return false;
      const recherche = UI.normaliserRecherche(filtres.recherche);
      if (!recherche) return true;
      const intitules = habilitationsQuiComptent(technicien.id).map((h) => h.intitule).join(' ');
      return UI.normaliserRecherche([technicien.id, technicien.nom, technicien.prenom, technicien.metier, intitules].join(' ')).includes(recherche);
    }
    function rafraichir() {
      const lignes = techniciens.filter(garder);
      if (UI.estTelephone()) {
        UI.remplir(zone, lignes.length ? UI.html`<ul class="liste-cartes">${lignes.map((t) => UI.html`<li>${carteTechnicien(t, jour)}</li>`)}</ul>`
          : UI.html`<p class="muted">${I18n.t('equipe.liste.aucun_technicien_correspond_filtres')}</p>`);
      } else {
        UI.remplir(zone, UI.tableau({ colonnes: colonnesListe(responsable, jour), lignes, libelle: I18n.t('equipe.liste.techniciens'),
          vide: I18n.t('equipe.liste.aucun_technicien_correspond_filtres') }));
      }
      UI.$('.equipe-compteur', conteneur).textContent = I18n.t('equipe.liste.compteur', { n: lignes.length, total: techniciens.length });
    }
    function lireFiltres() {
      Object.assign(filtres, UI.lireFormulaire(formulaire));
      const suite = new URLSearchParams();
      if (filtres.etat !== 'actifs') suite.set('etat', filtres.etat);
      if (filtres.recherche) suite.set('recherche', filtres.recherche);
      try { history.replaceState(history.state, '', '#/equipe' + (suite.toString() ? '?' + suite.toString() : '')); } catch (erreur) { /* adresse gardée */ }
      rafraichir();
    }
    formulaire.addEventListener('input', lireFiltres);
    formulaire.addEventListener('change', lireFiltres);
    formulaire.addEventListener('submit', (evenement) => evenement.preventDefault());
    rafraichir();
  }

  function afficherARenouveler(conteneur) {
    const jour = Donnees.aujourdhui();
    const alertes = aRenouveler(jour);
    const responsable = App.estResponsable();
    const ligne = (a) => UI.html`<li>
      <div class="equipe-tete">${lienTechnicien(a.technicien)} <b class="equipe-intitule">${a.habilitation.intitule}</b></div>
      ${statutHtml(a.habilitation, a.etat)}</li>`;
    UI.remplir(conteneur, UI.html`<div class="equipe">
      ${entete(responsable, I18n.t('equipe.arenouveler.habilitations_echues_dont_echeance'))}
      <div class="alertes"><div class="alerte" role="status">${UI.icone('equipe')}<div class="alerte-texte">
        ${I18n.html('equipe.arenouveler.alerte', { n: alertes.length })}</div></div></div>
      <article class="carte equipe-a-renouveler">
        ${alertes.length ? UI.html`<ul class="equipe-habilitations">${alertes.map(ligne)}</ul>`
          : UI.vide(I18n.t('equipe.arenouveler.aucune_habilitation_renouveler'), I18n.t('equipe.arenouveler.habilitations_techniciens_actifs_sont'), 'equipe')}
      </article></div>`);
  }

  // ===========================================================================================
  // 8. Formulaire d'un technicien : création (#/equipe/nouveau) et modification (fiche)
  // ===========================================================================================

  function formulaireTechnicien(technicien) {
    const formulaire = UI.element(UI.html`<form class="form-grille" id="form-technicien" novalidate></form>`);
    const valeur = (nom) => (technicien ? technicien[nom] : undefined);
    const ajouter = (bloc, large) => { if (large) bloc.classList.add('large'); formulaire.appendChild(bloc); return bloc; };
    ajouter(UI.champ(definitionChamp('techniciens', 'nom'), valeur('nom'), { attributs: { maxlength: '60' } }));
    ajouter(UI.champ(definitionChamp('techniciens', 'prenom'), valeur('prenom'), { attributs: { maxlength: '60' } }));
    ajouter(UI.champ(definitionChamp('techniciens', 'metier'), valeur('metier'), { placeholder: I18n.t('equipe.formulaire_technicien.ex_electricien_mecanicien') }));
    ajouter(UI.champ(definitionChamp('techniciens', 'capacite_h_semaine'), technicien ? technicien.capacite_h_semaine : CAPACITE_PAR_DEFAUT,
      { aide: I18n.t('equipe.formulaire_technicien.heures_disponibles_maintenance_chaque', { maximum: CAPACITE_MAX_H }) }));
    ajouter(UI.champ(definitionChamp('techniciens', 'taux_horaire', { libelle: I18n.t('equipe.formulaire_technicien.taux_horaire_ht_h') }), valeur('taux_horaire'),
      { aide: I18n.t('equipe.formulaire_technicien.cout_heure_technicien_sert') }));
    if (technicien) {
      ajouter(UI.champ(definitionChamp('techniciens', 'actif'), technicien.actif,
        { aide: I18n.t('equipe.formulaire_technicien.decoche_technicien_plus_propose') }), true);
    }
    formulaire.appendChild(UI.element(UI.html`<p class="mention-requis large"><span class="requis" aria-hidden="true">*</span>${I18n.t('commun.message.champ_obligatoire')}</p>`)).classList.add('large');
    formulaire.appendChild(UI.element(UI.html`<div class="actions">
      <button type="submit" class="btn btn-primaire">${UI.icone('valider')}${I18n.t('commun.bouton.enregistrer')}</button>
      ${technicien ? '' : UI.html`<a class="btn btn-fantome" href="#/equipe">${I18n.t('commun.bouton.annuler')}</a>`}</div>`));
    formulaire.addEventListener('submit', (evenement) => { evenement.preventDefault(); enregistrerTechnicien(formulaire, technicien); });
    return formulaire;
  }

  /** Désactivation : confirmation qui dit les OT encore ouverts affectés à ce technicien. */
  function confirmerDesactivation(technicien) {
    const ouverts = ordresOuverts(technicien.id).length;
    const nom = nomAffiche(technicien);
    return UI.confirmer(ouverts ? I18n.t('equipe.desactivation.question_ot_ouverts', { nom, n: ouverts })
      : I18n.t('equipe.desactivation.question', { nom }),
    { titre: I18n.t('equipe.confirmer_desactivation.desactiver_technicien'), oui: I18n.t('commun.bouton.desactiver'), danger: true });
  }

  async function enregistrerTechnicien(formulaire, technicien) {
    const bouton = UI.$('button[type=submit]', formulaire);
    if (bouton.disabled) return;
    const valeurs = UI.lireFormulaire(formulaire);
    const erreurs = UI.verifierFormulaire(formulaire);
    Equipe.verifierTechnicien(Object.assign({}, technicien || {}, valeurs), Donnees.lignes('techniciens'), technicien ? technicien.id : '')
      .filter((erreur) => !erreurs.some((e) => e.nom === erreur.nom)).forEach((erreur) => erreurs.push(erreur));
    afficherErreurs(formulaire, erreurs);
    if (erreurs.length) return;
    if (technicien && estActif(technicien) && valeurs.actif === '0' && !await confirmerDesactivation(technicien)) return;
    bouton.disabled = true;
    bouton.setAttribute('aria-busy', 'true');
    try {
      if (technicien) {
        const changes = await Equipe.modifierTechnicien(technicien.id, valeurs);
        await apresEcriture(changes.length ? I18n.t('equipe.enregistrer_technicien.technicien_enregistre') : I18n.t('commun.message.aucune_modification'));
        return;
      }
      const id = await Equipe.creerTechnicien(valeurs);
      App.marquerSaisie(false);
      UI.toast(I18n.t('equipe.enregistrer_technicien.technicien_cree'), 'succes');
      App.naviguer('#/equipe/' + encodeURIComponent(id));
    } catch (erreur) {
      App.signalerErreur(erreur, 'enregistrement du technicien');
    } finally {
      bouton.disabled = false;
      bouton.removeAttribute('aria-busy');
    }
  }

  function afficherNouveau(conteneur) {
    App.definirTitre(I18n.t('equipe.nouveau.nouveau_technicien'));
    UI.remplir(conteneur, UI.html`<div class="equipe">
      <div class="entete-page"><div><div class="fil">${I18n.html('equipe.nouveau.equipe_nouveau_technicien')}</div>
        <h1>${I18n.t('equipe.nouveau.nouveau_technicien')}</h1><p>${I18n.t('equipe.nouveau.habilitations_ajoutent_ensuite_fiche')}</p></div></div>
      <article class="carte equipe-zone-formulaire"></article></div>`);
    UI.$('.equipe-zone-formulaire', conteneur).appendChild(formulaireTechnicien(null));
  }

  // ===========================================================================================
  // 9. Fiche #/equipe/<id> : habilitations (ajout, renouvellement, correction), historique
  // ===========================================================================================

  /** Intitulés déjà connus (habilitations et équipements) proposés à la saisie. */
  function intitulesConnus() {
    const connus = new Set();
    Donnees.lignes('habilitations').forEach((h) => { if (texte(h.intitule)) connus.add(texte(h.intitule)); });
    Donnees.lignes('equipements').forEach((e) => texte(e.habilitation_requise).split(',').map(texte).filter(Boolean).forEach((i) => connus.add(i)));
    return Array.from(connus).sort((a, b) => UI.comparerTextes(a, b));
  }

  function champsHabilitation(habilitation, avecIntitule) {
    const champs = [];
    if (avecIntitule) {
      const idListe = UI.identifiantUnique('equipe-intitules');
      const bloc = UI.champ(definitionChamp('habilitations', 'intitule', { obligatoire: true }), habilitation ? habilitation.intitule : '',
        { placeholder: I18n.t('equipe.champs_habilitation.ex_br_h_0'), attributs: { list: idListe, autocomplete: 'off' } });
      bloc.appendChild(UI.element(UI.html`<datalist id="${idListe}">${intitulesConnus().map((i) => UI.html`<option value="${i}"></option>`)}</datalist>`));
      champs.push(bloc);
    }
    champs.push(UI.champ(definitionChamp('habilitations', 'date_obtention', { obligatoire: true }),
      habilitation ? habilitation.date_obtention : Donnees.aujourdhui()));
    champs.push(UI.champ(definitionChamp('habilitations', 'date_echeance'), habilitation ? habilitation.date_echeance : '',
      { aide: I18n.t('equipe.champs_habilitation.vide_habilitation_sans_echeance') }));
    return champs;
  }

  async function ouvrirAjout(technicien) {
    const fait = await UI.fenetreAction({ classe: 'equipe-fenetre',
      titre: I18n.t('equipe.ouvrir_ajout.ajouter_habilitation'), libelleValider: I18n.t('commun.bouton.ajouter'),
      introduction: UI.html`<p>${I18n.html('equipe.ouvrir_ajout.habilitation_habilitation_deja_utilisez', { nomAffiche: nomAffiche(technicien) })}</p>`,
      champs: champsHabilitation(null, true),
      verifier: verifierHabilitation,
      action: (valeurs) => Equipe.ajouterHabilitation(technicien.id, valeurs),
    });
    if (fait) await apresEcriture(I18n.t('equipe.ouvrir_ajout.habilitation_ajoutee'));
  }

  async function ouvrirRenouvellement(habilitation) {
    const echeance = dateIso(habilitation.date_echeance) ? UI.dateFr(habilitation.date_echeance) : I18n.t('equipe.ouvrir_renouvellement.aucune');
    const fait = await UI.fenetreAction({ classe: 'equipe-fenetre',
      titre: I18n.t('equipe.ouvrir_renouvellement.renouveler_habilitation'), libelleValider: I18n.t('equipe.ouvrir_renouvellement.renouveler'),
      introduction: UI.html`<p>${I18n.html('equipe.ouvrir_renouvellement.echeance_actuelle_nouvelle_ligne', { intitule: habilitation.intitule, echeance })}</p>`,
      champs: champsHabilitation(null, false),
      verifier: (valeurs) => verifierHabilitation(Object.assign({ intitule: habilitation.intitule }, valeurs)),
      action: (valeurs) => Equipe.renouvelerHabilitation(habilitation.id, valeurs),
    });
    if (fait) await apresEcriture(I18n.t('equipe.ouvrir_renouvellement.habilitation_renouvelee'));
  }

  async function ouvrirCorrection(habilitation) {
    const fait = await UI.fenetreAction({ classe: 'equipe-fenetre',
      titre: I18n.t('equipe.ouvrir_correction.corriger_habilitation'), libelleValider: I18n.t('commun.bouton.enregistrer'),
      introduction: UI.html`<p>${I18n.t('equipe.ouvrir_correction.erreur_saisie_seulement_renouvellement')}</p>`,
      champs: champsHabilitation(habilitation, true),
      verifier: verifierHabilitation,
      action: (valeurs) => Equipe.modifierHabilitation(habilitation.id, valeurs),
    });
    if (fait) await apresEcriture(I18n.t('equipe.ouvrir_correction.habilitation_corrigee'));
  }

  function carteHabilitations(technicien, responsable, jour) {
    const liste = habilitationsAvecEtat(technicien.id, jour)
      .sort((a, b) => STATUTS_HABILITATION.indexOf(a.etat.statut) - STATUTS_HABILITATION.indexOf(b.etat.statut)
        || UI.comparerTextes(texte(a.habilitation.intitule), texte(b.habilitation.intitule)));
    return UI.html`<article class="carte equipe-carte-habilitations">
      <div class="entete-carte"><h2>${I18n.html('equipe.carte_habilitations.habilitations_nb_liste', { nbListe: liste.length })}</h2>
        ${responsable ? UI.html`<button type="button" class="btn btn-secondaire" id="equipe-ajouter-habilitation">${UI.icone('ajouter')}${I18n.t('equipe.ouvrir_ajout.ajouter_habilitation')}</button>` : ''}</div>
      ${liste.length ? UI.html`<ul class="equipe-habilitations">${liste.map(({ habilitation, etat }) => UI.html`<li>
        <div class="equipe-tete"><b class="equipe-intitule">${habilitation.intitule}</b>${statutHtml(habilitation, etat)}</div>
        <div class="equipe-dates">${dateIso(habilitation.date_echeance)
    ? I18n.t('equipe.habilitations.obtenue_echeance', { obtention: UI.dateFr(habilitation.date_obtention), echeance: UI.dateFr(habilitation.date_echeance) })
    : I18n.t('equipe.habilitations.obtenue_sans_echeance', { obtention: UI.dateFr(habilitation.date_obtention) })}</div>
        ${responsable ? UI.html`<div class="actions equipe-actions">
          <button type="button" class="btn btn-secondaire" data-action="renouveler" data-habilitation="${habilitation.id}">${UI.icone('actualiser')}${I18n.t('equipe.ouvrir_renouvellement.renouveler')}</button>
          <button type="button" class="btn btn-fantome" data-action="corriger" data-habilitation="${habilitation.id}">${I18n.t('equipe.carte_habilitations.corriger')}</button></div>` : ''}
      </li>`)}</ul>` : UI.html`<p class="muted">${I18n.t('equipe.carte_habilitations.aucune_habilitation_enregistree_technicien')}</p>`}
    </article>`;
  }

  /** Toutes les lignes d'habilitation du technicien (renouvellements compris), les plus récentes d'abord. */
  function carteHistorique(technicien) {
    const comptent = new Set(habilitationsQuiComptent(technicien.id).map((h) => h.id));
    const lignes = Donnees.lignes('habilitations').filter((h) => h.technicien_id === technicien.id)
      .sort((a, b) => UI.comparerTextes(texte(a.intitule), texte(b.intitule), { sensitivity: 'base' })
        || texte(b.date_obtention).localeCompare(texte(a.date_obtention)) || texte(b.id).localeCompare(texte(a.id), 'fr', { numeric: true }));
    return UI.html`<article class="carte equipe-historique"><h2>${I18n.html('equipe.carte_historique.historique_habilitations', { nbLignes: lignes.length })}</h2>
      ${lignes.length ? UI.html`<ul class="equipe-lignes">${lignes.map((h) => UI.html`<li>
        <b>${h.intitule}</b> <span>${dateIso(h.date_echeance)
    ? I18n.t('equipe.historique.obtenue_echeance', { obtention: UI.dateFr(h.date_obtention), echeance: UI.dateFr(h.date_echeance) })
    : I18n.t('equipe.historique.obtenue_sans_echeance', { obtention: UI.dateFr(h.date_obtention) })}</span>
        ${comptent.has(h.id) ? UI.html`<span class="badge info">${I18n.t('equipe.carte_historique.cours')}</span>` : UI.html`<span class="badge neutre">${I18n.t('equipe.carte_historique.remplacee')}</span>`}
        <span class="muted">${h.id}</span></li>`)}</ul>` : UI.html`<p class="muted">${I18n.t('equipe.carte_historique.aucune_ligne_habilitation')}</p>`}
    </article>`;
  }

  function carteDescription(technicien) {
    const ouverts = ordresOuverts(technicien.id).length;
    return UI.html`<article class="carte"><h2>${I18n.t('equipe.carte_technicien.titre')}</h2><dl class="valeurs">
      <dt>${I18n.t('equipe.carte_description.nom')}</dt><dd>${technicien.nom}</dd><dt>${I18n.t('commun.champ.prenom')}</dt><dd>${technicien.prenom}</dd>
      <dt>${I18n.t('equipe.colonnes_liste.metier')}</dt><dd>${technicien.metier}</dd>
      <dt>${I18n.t('equipe.colonnes_liste.capacite')}</dt><dd>${texte(technicien.capacite_h_semaine) ? I18n.t('equipe.description.capacite_h_par_semaine', { n: UI.nombreFr(technicien.capacite_h_semaine) }) : ''}</dd>
      <dt>${I18n.t('equipe.carte_description.ot_ouverts_affectes')}</dt><dd><a href="#/ot?technicien=${encodeURIComponent(technicien.id)}">${ouverts}</a></dd>
      <dt>${I18n.t('equipe.carte_description.actif')}</dt><dd>${estActif(technicien) ? I18n.t('equipe.carte_description.oui') : I18n.t('equipe.carte_description.non_technicien_desactive')}</dd></dl></article>`;
  }

  function afficherIntrouvable(conteneur, id) {
    App.definirTitre(I18n.t('equipe.introuvable.technicien_introuvable'));
    UI.remplir(conteneur, UI.html`<div class="equipe"><div class="entete-page"><div>
      <div class="fil"><a href="#/equipe">${I18n.t('equipe.entete.equipe')}</a></div><h1>${I18n.t('equipe.introuvable.technicien_introuvable')}</h1></div></div>
      ${UI.vide(I18n.t('equipe.introuvable.aucun_technicien_porte_identifiant', { id }), I18n.t('commun.message.saisi_sur_autre_poste'), 'equipe')}</div>`);
  }

  function afficherFiche(conteneur, parametres) {
    const technicien = Donnees.trouver('techniciens', parametres.id);
    if (!technicien) { afficherIntrouvable(conteneur, parametres.id); return; }
    const responsable = App.estResponsable();
    const jour = Donnees.aujourdhui();
    App.definirTitre(nomAffiche(technicien));
    UI.remplir(conteneur, UI.html`
      <div class="equipe equipe-fiche" data-technicien="${technicien.id}">
        <div class="entete-page"><div>
          <div class="fil">${I18n.html('equipe.fiche.equipe_technicien_id', { technicienId: technicien.id })}</div>
          <h1>${nomAffiche(technicien)}</h1>
          <p class="equipe-badges">${technicien.metier ? UI.html`<span>${technicien.metier}</span>` : ''}
            ${estActif(technicien) ? '' : UI.html`<span class="badge neutre barre">${I18n.t('equipe.colonnes_liste.inactif')}</span>`}</p>
        </div></div>
        ${estActif(technicien) ? '' : UI.html`<div class="alertes"><div class="alerte attention" role="status">${UI.icone('alerte')}
          <div class="alerte-texte">${I18n.html('equipe.fiche.technicien_desactive_plus_propose')}</div></div></div>`}
        <div class="grille equipe-grille">
          <div class="c7">${carteHabilitations(technicien, responsable, jour)}</div>
          <div class="c5 equipe-zone-technicien"></div>
        </div>
        ${carteHistorique(technicien)}
      </div>`);
    const zone = UI.$('.equipe-zone-technicien', conteneur);
    if (!responsable) { UI.remplir(zone, carteDescription(technicien)); return; }
    const carte = UI.element(UI.html`<article class="carte"><h2>${I18n.t('equipe.carte_technicien.titre')}</h2></article>`);
    carte.appendChild(formulaireTechnicien(technicien));
    zone.appendChild(carte);
    UI.$('#equipe-ajouter-habilitation', conteneur).addEventListener('click', () => ouvrirAjout(technicien));
    UI.$$('button[data-action]', conteneur).forEach((bouton) => bouton.addEventListener('click', () => {
      const habilitation = Donnees.trouver('habilitations', bouton.dataset.habilitation);
      if (!habilitation) { UI.toast(I18n.t('equipe.fiche.habilitation_existe_plus_actualisez'), 'attention'); return; }
      if (bouton.dataset.action === 'renouveler') ouvrirRenouvellement(habilitation); else ouvrirCorrection(habilitation);
    }));
  }

  // ===========================================================================================
  // 10. Enregistrement des écrans (App est chargé après les modules : on attend la page)
  // ===========================================================================================

  document.addEventListener('DOMContentLoaded', () => {
    const intervenants = ['technicien', 'responsable'];
    App.ecran({
      id: 'equipe', route: /^#\/equipe$/,
      get titre() { return I18n.t('equipe.entete.equipe'); },
      menu: { get libelle() { return I18n.t('equipe.menu.libelle'); }, icone: 'equipe', ordre: 85, get groupe() { return I18n.t('equipe.groupe.administration'); } },
      profils: intervenants,
      tables: ['techniciens', 'habilitations'],
      afficher: afficherListe,
    });
    // Les routes les plus précises d'abord : « nouveau » et « acces » (equipe-acces.js, enregistré après ce
    // fichier) ne doivent pas être pris pour un identifiant.
    App.ecran({
      id: 'equipe-nouveau', route: /^#\/equipe\/nouveau$/, parent: 'equipe',
      get titre() { return I18n.t('equipe.nouveau.nouveau_technicien'); },
      profils: ['responsable'],
      tables: [],
      afficher: afficherNouveau,
    });
    App.ecran({
      id: 'equipe-fiche', route: /^#\/equipe\/(?!nouveau$|acces$)(?<id>[^/?]+)$/, parent: 'equipe',
      get titre() { return I18n.t('equipe.ecran_fiche.titre'); },
      profils: intervenants,
      tables: ['techniciens', 'habilitations', 'ordres_travail'],
      afficher: afficherFiche,
    });
  });

  // libelleStatut : libellé d'un état calculé d'habilitation, aussi pour le wiki (fiche d'un technicien).
  return { libelleStatut };
})());
