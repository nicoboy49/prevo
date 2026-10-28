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
  const ETATS = [
    { valeur: 'actifs', libelle: 'Techniciens actifs' },
    { valeur: 'inactifs', libelle: 'Techniciens inactifs' },
    { valeur: 'tous', libelle: 'Tous les techniciens' },
  ];
  // Couleur d'un statut sans ton prévu par UI.badgeStatut (le texte dit toujours le statut).
  const TONS = { 'pas encore valable': 'info' };
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

  function badgeEtat(etat) {
    return UI.badgeStatut(etat.statut, TONS[etat.statut]);
  }

  /** « échéance le 02/12/2026 (dans 43 jours) », « échue depuis 142 jours », « sans échéance »… */
  function detailEtat(habilitation, etat) {
    if (etat.statut === 'pas encore valable') return 'valable à partir du ' + UI.dateFr(habilitation.date_obtention);
    if (etat.sansEcheance) return 'sans échéance';
    if (etat.joursRestants === null) return 'échéance illisible (« ' + texte(habilitation.date_echeance) + ' ») : corrigez-la';
    const jours = Math.abs(etat.joursRestants);
    const duree = jours + ' jour' + (jours > 1 ? 's' : '');
    if (etat.joursRestants < 0) return 'échue le ' + UI.dateFr(habilitation.date_echeance) + ' (depuis ' + duree + ')';
    if (etat.joursRestants === 0) return 'échéance aujourd\'hui';
    return 'échéance le ' + UI.dateFr(habilitation.date_echeance) + ' (dans ' + duree + ')';
  }

  /** Statut d'une habilitation (badge + détail), repéré par son identifiant. */
  function statutHtml(habilitation, etat) {
    return UI.html`<span class="equipe-statut" data-habilitation="${habilitation.id}">${badgeEtat(etat)}
      <small class="equipe-detail">${detailEtat(habilitation, etat)}</small></span>`;
  }

  /** Puce « BR · échue » d'une liste : l'intitulé, et le statut en clair s'il n'est pas « valide ». */
  function puceHabilitation(habilitation, etat) {
    const ton = TONS[etat.statut] || { valide: 'ok', 'à renouveler': 'attention', 'échue': 'ko' }[etat.statut] || 'neutre';
    return UI.html`<span class="badge ${ton} equipe-habilitation" data-habilitation="${habilitation.id}" data-statut="${etat.statut}"
      title="${habilitation.intitule} : ${etat.statut}">${habilitation.intitule}${etat.statut === 'valide' ? '' : ' · ' + etat.statut}</span>`;
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
      <a href="#/equipe"><div class="lib">Techniciens actifs</div><div class="chiffre">${actifs.length}</div>
        <div class="comp">${Donnees.lignes('techniciens').length - actifs.length} inactif(s)</div></a>
      <a class="${alertes.length ? 'ambre' : 'vert'}" href="#/equipe?filtre=${FILTRE_A_RENOUVELER}"><div class="lib">Habilitations à renouveler</div>
        <div class="chiffre">${alertes.length}</div><div class="comp">${echues ? 'dont ' + echues + ' échue(s)' : 'échéance dans les 60 jours'}</div></a>
      <div class="cyan"><div class="lib">Capacité de l'équipe</div><div class="chiffre">${UI.nombreFr(capacite)} h</div>
        <div class="comp">par semaine (techniciens actifs)</div></div>
    </div>`;
  }

  function entete(responsable, sousTitre) {
    return UI.html`<div class="entete-page">
      <div><h1>Équipe</h1><p>${sousTitre}</p></div>
      <div class="actions">${responsable && App.mode === 'serveur' ? UI.html`<a class="btn btn-secondaire" id="equipe-acces" href="#/equipe/acces">${UI.icone('cle')}Accès</a>` : ''}
        ${responsable ? UI.html`<a class="btn btn-primaire" id="equipe-nouveau" href="#/equipe/nouveau">${UI.icone('ajouter')}Ajouter un technicien</a>` : ''}</div>
    </div>`;
  }

  function colonnesListe(responsable, jour) {
    return [
      { cle: 'nom', libelle: 'Technicien', valeurTri: (t) => texte(t.nom) + ' ' + texte(t.prenom),
        rendu: (t) => UI.html`${lienTechnicien(t)}${estActif(t) ? '' : UI.html` <span class="badge neutre barre">Inactif</span>`}` },
      { cle: 'metier', libelle: 'Métier' },
      { cle: 'capacite_h_semaine', libelle: 'Capacité', type: 'nombre', classe: 'sans-coupure',
        rendu: (t) => (texte(t.capacite_h_semaine) ? UI.nombreFr(t.capacite_h_semaine) + ' h / sem.' : '') },
      // Colonne du responsable seul : pour le technicien, la valeur n'est même pas lue.
      responsable && { cle: 'taux_horaire', libelle: 'Taux horaire', type: 'nombre', classe: 'sans-coupure',
        rendu: (t) => (texte(t.taux_horaire) ? UI.euro(t.taux_horaire) + ' / h' : '') },
      { cle: 'habilitations', libelle: 'Habilitations', triable: false, classe: 'equipe-col-habilitations',
        rendu: (t) => UI.html`<span class="equipe-puces">${habilitationsAvecEtat(t.id, jour).map((h) => puceHabilitation(h.habilitation, h.etat))}</span>` },
    ].filter(Boolean);
  }

  function carteTechnicien(technicien, jour) {
    return UI.html`<a class="equipe-lien" href="#/equipe/${encodeURIComponent(technicien.id)}">
      <div class="carte-tete"><b>${nomAffiche(technicien)}</b>${estActif(technicien) ? '' : UI.html`<span class="badge neutre barre">Inactif</span>`}</div>
      <div class="carte-meta">${technicien.metier ? UI.html`<span>${technicien.metier}</span>` : ''}
        ${texte(technicien.capacite_h_semaine) ? UI.html`<span>${UI.nombreFr(technicien.capacite_h_semaine)} h / semaine</span>` : ''}</div>
      <div class="equipe-puces">${habilitationsAvecEtat(technicien.id, jour).map((h) => puceHabilitation(h.habilitation, h.etat))}</div></a>`;
  }

  function afficherListe(conteneur, parametres) {
    const requete = (parametres && parametres.requete) || new URLSearchParams();
    if (requete.get('filtre') === FILTRE_A_RENOUVELER) { afficherARenouveler(conteneur); return; }
    const jour = Donnees.aujourdhui();
    const responsable = App.estResponsable();
    const filtres = { recherche: requete.get('recherche') || '',
      etat: ETATS.some((etat) => etat.valeur === requete.get('etat')) ? requete.get('etat') : 'actifs' };
    UI.remplir(conteneur, UI.html`<div class="equipe">
      ${entete(responsable, 'Techniciens, capacité et habilitations : une habilitation échue ou à moins de 60 jours de son échéance est signalée.')}
      ${responsable ? '' : UI.html`<p class="note equipe-consultation">Consultation : seul le responsable modifie l'équipe.</p>`}
      ${instrumentsHtml(jour)}
      <form class="filtres equipe-filtres" id="equipe-filtres" data-hors-saisie role="search" aria-label="Filtrer les techniciens">
        <label class="visuellement-cache" for="equipe-recherche">Rechercher un technicien</label>
        <input type="search" id="equipe-recherche" name="recherche" value="${filtres.recherche}" placeholder="Nom, métier, habilitation" autocomplete="off">
        <label class="visuellement-cache" for="equipe-etat">Techniciens affichés</label>
        <select id="equipe-etat" name="etat">${ETATS.map((etat) => UI.html`<option value="${etat.valeur}"${etat.valeur === filtres.etat ? UI.brut(' selected') : ''}>${etat.libelle}</option>`)}</select>
      </form>
      <p class="note equipe-compteur" role="status"></p>
      <div class="carte equipe-liste"></div></div>`);
    const zone = UI.$('.equipe-liste', conteneur);
    const formulaire = UI.$('#equipe-filtres', conteneur);
    const techniciens = Donnees.lignes('techniciens').slice()
      .sort((a, b) => (texte(a.nom) + ' ' + texte(a.prenom)).localeCompare(texte(b.nom) + ' ' + texte(b.prenom), 'fr'));

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
          : UI.html`<p class="muted">Aucun technicien ne correspond à ces filtres.</p>`);
      } else {
        UI.remplir(zone, UI.tableau({ colonnes: colonnesListe(responsable, jour), lignes, libelle: 'Techniciens',
          vide: 'Aucun technicien ne correspond à ces filtres.' }));
      }
      UI.$('.equipe-compteur', conteneur).textContent = lignes.length + ' technicien(s) sur ' + techniciens.length;
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
      ${entete(responsable, 'Habilitations échues ou dont l\'échéance tombe dans les 60 jours, techniciens actifs (les plus urgentes d\'abord).')}
      <div class="alertes"><div class="alerte" role="status">${UI.icone('equipe')}<div class="alerte-texte">
        <b>${alertes.length} habilitation(s) à renouveler.</b> Une habilitation renouvelée garde son historique : ouvrez la fiche du technicien,
        puis « Renouveler ». — <a href="#/equipe">voir toute l'équipe</a></div></div></div>
      <article class="carte equipe-a-renouveler">
        ${alertes.length ? UI.html`<ul class="equipe-habilitations">${alertes.map(ligne)}</ul>`
          : UI.vide('Aucune habilitation à renouveler', 'Les habilitations des techniciens actifs sont valables au-delà de 60 jours.', 'equipe')}
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
    ajouter(UI.champ(definitionChamp('techniciens', 'metier'), valeur('metier'), { placeholder: 'Ex. Électricien, mécanicien' }));
    ajouter(UI.champ(definitionChamp('techniciens', 'capacite_h_semaine'), technicien ? technicien.capacite_h_semaine : CAPACITE_PAR_DEFAUT,
      { aide: 'Heures disponibles pour la maintenance chaque semaine (0 à ' + CAPACITE_MAX_H + ') : sert au planning.' }));
    ajouter(UI.champ(definitionChamp('techniciens', 'taux_horaire', { libelle: 'Taux horaire (€ HT / h)' }), valeur('taux_horaire'),
      { aide: 'Coût d\'une heure de ce technicien : sert au coût des OT (RG7). Jamais montré aux techniciens.' }));
    if (technicien) {
      ajouter(UI.champ(definitionChamp('techniciens', 'actif'), technicien.actif,
        { aide: 'Décoché : le technicien n\'est plus proposé (OT, planning, profil) ; son historique est conservé.' }), true);
    }
    formulaire.appendChild(UI.element(UI.html`<p class="mention-requis large"><span class="requis" aria-hidden="true">*</span>champ obligatoire</p>`)).classList.add('large');
    formulaire.appendChild(UI.element(UI.html`<div class="actions">
      <button type="submit" class="btn btn-primaire">${UI.icone('valider')}Enregistrer</button>
      ${technicien ? '' : UI.html`<a class="btn btn-fantome" href="#/equipe">Annuler</a>`}</div>`));
    formulaire.addEventListener('submit', (evenement) => { evenement.preventDefault(); enregistrerTechnicien(formulaire, technicien); });
    return formulaire;
  }

  /** Désactivation : confirmation qui dit les OT encore ouverts affectés à ce technicien. */
  function confirmerDesactivation(technicien) {
    const ouverts = ordresOuverts(technicien.id).length;
    return UI.confirmer('Désactiver ' + nomAffiche(technicien) + ' ? Il ne sera plus proposé pour les OT, le planning ni le choix du profil ; '
      + 'son historique et ses habilitations sont conservés.'
      + (ouverts ? ' Attention : ' + ouverts + ' OT ouvert(s) lui sont encore affectés : réaffectez-les.' : ''),
    { titre: 'Désactiver le technicien', oui: 'Désactiver', danger: true });
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
        await apresEcriture(changes.length ? 'Technicien enregistré.' : 'Aucune modification à enregistrer.');
        return;
      }
      const id = await Equipe.creerTechnicien(valeurs);
      App.marquerSaisie(false);
      UI.toast('Technicien créé.', 'succes');
      App.naviguer('#/equipe/' + encodeURIComponent(id));
    } catch (erreur) {
      App.signalerErreur(erreur, 'enregistrement du technicien');
    } finally {
      bouton.disabled = false;
      bouton.removeAttribute('aria-busy');
    }
  }

  function afficherNouveau(conteneur) {
    App.definirTitre('Nouveau technicien');
    UI.remplir(conteneur, UI.html`<div class="equipe">
      <div class="entete-page"><div><div class="fil"><a href="#/equipe">Équipe</a> <span aria-hidden="true">›</span> <span>Nouveau technicien</span></div>
        <h1>Nouveau technicien</h1><p>Ses habilitations s'ajoutent ensuite sur sa fiche.</p></div></div>
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
    return Array.from(connus).sort((a, b) => a.localeCompare(b, 'fr'));
  }

  function champsHabilitation(habilitation, avecIntitule) {
    const champs = [];
    if (avecIntitule) {
      const idListe = UI.identifiantUnique('equipe-intitules');
      const bloc = UI.champ(definitionChamp('habilitations', 'intitule', { obligatoire: true }), habilitation ? habilitation.intitule : '',
        { placeholder: 'Ex. BR, H0V, CACES R489', attributs: { list: idListe, autocomplete: 'off' } });
      bloc.appendChild(UI.element(UI.html`<datalist id="${idListe}">${intitulesConnus().map((i) => UI.html`<option value="${i}"></option>`)}</datalist>`));
      champs.push(bloc);
    }
    champs.push(UI.champ(definitionChamp('habilitations', 'date_obtention', { obligatoire: true }),
      habilitation ? habilitation.date_obtention : Donnees.aujourdhui()));
    champs.push(UI.champ(definitionChamp('habilitations', 'date_echeance'), habilitation ? habilitation.date_echeance : '',
      { aide: 'Vide : habilitation sans échéance.' }));
    return champs;
  }

  async function ouvrirAjout(technicien) {
    const fait = await UI.fenetreAction({ classe: 'equipe-fenetre',
      titre: 'Ajouter une habilitation', libelleValider: 'Ajouter',
      introduction: UI.html`<p>Habilitation de <b>${nomAffiche(technicien)}</b>. Pour une habilitation qu'il a déjà, utilisez « Renouveler ».</p>`,
      champs: champsHabilitation(null, true),
      verifier: verifierHabilitation,
      action: (valeurs) => Equipe.ajouterHabilitation(technicien.id, valeurs),
    });
    if (fait) await apresEcriture('Habilitation ajoutée.');
  }

  async function ouvrirRenouvellement(habilitation) {
    const fait = await UI.fenetreAction({ classe: 'equipe-fenetre',
      titre: 'Renouveler l\'habilitation', libelleValider: 'Renouveler',
      introduction: UI.html`<p><b>${habilitation.intitule}</b> — échéance actuelle : ${dateIso(habilitation.date_echeance) ? UI.dateFr(habilitation.date_echeance) : 'aucune'}.
        Une nouvelle ligne est ajoutée ; l'ancienne reste dans l'historique.</p>`,
      champs: champsHabilitation(null, false),
      verifier: (valeurs) => verifierHabilitation(Object.assign({ intitule: habilitation.intitule }, valeurs)),
      action: (valeurs) => Equipe.renouvelerHabilitation(habilitation.id, valeurs),
    });
    if (fait) await apresEcriture('Habilitation renouvelée.');
  }

  async function ouvrirCorrection(habilitation) {
    const fait = await UI.fenetreAction({ classe: 'equipe-fenetre',
      titre: 'Corriger l\'habilitation', libelleValider: 'Enregistrer',
      introduction: UI.html`<p>Pour une erreur de saisie seulement : un renouvellement garde l'ancienne ligne (« Renouveler »).</p>`,
      champs: champsHabilitation(habilitation, true),
      verifier: verifierHabilitation,
      action: (valeurs) => Equipe.modifierHabilitation(habilitation.id, valeurs),
    });
    if (fait) await apresEcriture('Habilitation corrigée.');
  }

  function carteHabilitations(technicien, responsable, jour) {
    const liste = habilitationsAvecEtat(technicien.id, jour)
      .sort((a, b) => STATUTS_HABILITATION.indexOf(a.etat.statut) - STATUTS_HABILITATION.indexOf(b.etat.statut)
        || texte(a.habilitation.intitule).localeCompare(texte(b.habilitation.intitule), 'fr'));
    return UI.html`<article class="carte equipe-carte-habilitations">
      <div class="entete-carte"><h2>Habilitations <span class="badge">${liste.length}</span></h2>
        ${responsable ? UI.html`<button type="button" class="btn btn-secondaire" id="equipe-ajouter-habilitation">${UI.icone('ajouter')}Ajouter une habilitation</button>` : ''}</div>
      ${liste.length ? UI.html`<ul class="equipe-habilitations">${liste.map(({ habilitation, etat }) => UI.html`<li>
        <div class="equipe-tete"><b class="equipe-intitule">${habilitation.intitule}</b>${statutHtml(habilitation, etat)}</div>
        <div class="equipe-dates">Obtenue le ${UI.dateFr(habilitation.date_obtention)}${dateIso(habilitation.date_echeance) ? ' · échéance le ' + UI.dateFr(habilitation.date_echeance) : ' · sans échéance'}</div>
        ${responsable ? UI.html`<div class="actions equipe-actions">
          <button type="button" class="btn btn-secondaire" data-action="renouveler" data-habilitation="${habilitation.id}">${UI.icone('actualiser')}Renouveler</button>
          <button type="button" class="btn btn-fantome" data-action="corriger" data-habilitation="${habilitation.id}">Corriger</button></div>` : ''}
      </li>`)}</ul>` : UI.html`<p class="muted">Aucune habilitation enregistrée pour ce technicien.</p>`}
    </article>`;
  }

  /** Toutes les lignes d'habilitation du technicien (renouvellements compris), les plus récentes d'abord. */
  function carteHistorique(technicien) {
    const comptent = new Set(habilitationsQuiComptent(technicien.id).map((h) => h.id));
    const lignes = Donnees.lignes('habilitations').filter((h) => h.technicien_id === technicien.id)
      .sort((a, b) => texte(a.intitule).localeCompare(texte(b.intitule), 'fr', { sensitivity: 'base' })
        || texte(b.date_obtention).localeCompare(texte(a.date_obtention)) || texte(b.id).localeCompare(texte(a.id), 'fr', { numeric: true }));
    return UI.html`<article class="carte equipe-historique"><h2>Historique des habilitations <span class="badge">${lignes.length}</span></h2>
      ${lignes.length ? UI.html`<ul class="equipe-lignes">${lignes.map((h) => UI.html`<li>
        <b>${h.intitule}</b> <span>obtenue le ${UI.dateFr(h.date_obtention)} — ${dateIso(h.date_echeance) ? 'échéance le ' + UI.dateFr(h.date_echeance) : 'sans échéance'}</span>
        ${comptent.has(h.id) ? UI.html`<span class="badge info">en cours</span>` : UI.html`<span class="badge neutre">remplacée</span>`}
        <span class="muted">${h.id}</span></li>`)}</ul>` : UI.html`<p class="muted">Aucune ligne d'habilitation.</p>`}
    </article>`;
  }

  function carteDescription(technicien) {
    const ouverts = ordresOuverts(technicien.id).length;
    return UI.html`<article class="carte"><h2>Technicien</h2><dl class="valeurs">
      <dt>Nom</dt><dd>${technicien.nom}</dd><dt>Prénom</dt><dd>${technicien.prenom}</dd>
      <dt>Métier</dt><dd>${technicien.metier}</dd>
      <dt>Capacité</dt><dd>${texte(technicien.capacite_h_semaine) ? UI.nombreFr(technicien.capacite_h_semaine) + ' h par semaine' : ''}</dd>
      <dt>OT ouverts affectés</dt><dd><a href="#/ot?technicien=${encodeURIComponent(technicien.id)}">${ouverts}</a></dd>
      <dt>Actif</dt><dd>${estActif(technicien) ? 'Oui' : 'Non — technicien désactivé'}</dd></dl></article>`;
  }

  function afficherIntrouvable(conteneur, id) {
    App.definirTitre('Technicien introuvable');
    UI.remplir(conteneur, UI.html`<div class="equipe"><div class="entete-page"><div>
      <div class="fil"><a href="#/equipe">Équipe</a></div><h1>Technicien introuvable</h1></div></div>
      ${UI.vide('Aucun technicien ne porte l\'identifiant « ' + id + ' »', 'Il a peut-être été saisi sur un autre poste : actualisez.', 'equipe')}</div>`);
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
          <div class="fil"><a href="#/equipe">Équipe</a> <span aria-hidden="true">›</span> <span>${technicien.id}</span></div>
          <h1>${nomAffiche(technicien)}</h1>
          <p class="equipe-badges">${technicien.metier ? UI.html`<span>${technicien.metier}</span>` : ''}
            ${estActif(technicien) ? '' : UI.html`<span class="badge neutre barre">Inactif</span>`}</p>
        </div></div>
        ${estActif(technicien) ? '' : UI.html`<div class="alertes"><div class="alerte attention" role="status">${UI.icone('alerte')}
          <div class="alerte-texte"><b>Ce technicien est désactivé.</b> Il n'est plus proposé ; son historique reste consultable.</div></div></div>`}
        <div class="grille equipe-grille">
          <div class="c7">${carteHabilitations(technicien, responsable, jour)}</div>
          <div class="c5 equipe-zone-technicien"></div>
        </div>
        ${carteHistorique(technicien)}
      </div>`);
    const zone = UI.$('.equipe-zone-technicien', conteneur);
    if (!responsable) { UI.remplir(zone, carteDescription(technicien)); return; }
    const carte = UI.element(UI.html`<article class="carte"><h2>Technicien</h2></article>`);
    carte.appendChild(formulaireTechnicien(technicien));
    zone.appendChild(carte);
    UI.$('#equipe-ajouter-habilitation', conteneur).addEventListener('click', () => ouvrirAjout(technicien));
    UI.$$('button[data-action]', conteneur).forEach((bouton) => bouton.addEventListener('click', () => {
      const habilitation = Donnees.trouver('habilitations', bouton.dataset.habilitation);
      if (!habilitation) { UI.toast('Cette habilitation n\'existe plus : actualisez.', 'attention'); return; }
      if (bouton.dataset.action === 'renouveler') ouvrirRenouvellement(habilitation); else ouvrirCorrection(habilitation);
    }));
  }

  // ===========================================================================================
  // 10. Enregistrement des écrans (App est chargé après les modules : on attend la page)
  // ===========================================================================================

  document.addEventListener('DOMContentLoaded', () => {
    const intervenants = ['technicien', 'responsable'];
    App.ecran({
      id: 'equipe', route: /^#\/equipe$/, titre: 'Équipe',
      menu: { libelle: 'Équipe', icone: 'equipe', ordre: 85, groupe: 'Administration' },
      profils: intervenants,
      tables: ['techniciens', 'habilitations'],
      afficher: afficherListe,
    });
    // Les routes les plus précises d'abord : « nouveau » et « acces » (equipe-acces.js, enregistré après ce
    // fichier) ne doivent pas être pris pour un identifiant.
    App.ecran({
      id: 'equipe-nouveau', route: /^#\/equipe\/nouveau$/, titre: 'Nouveau technicien', parent: 'equipe',
      profils: ['responsable'],
      tables: [],
      afficher: afficherNouveau,
    });
    App.ecran({
      id: 'equipe-fiche', route: /^#\/equipe\/(?!nouveau$|acces$)(?<id>[^/?]+)$/, titre: 'Technicien', parent: 'equipe',
      profils: intervenants,
      tables: ['techniciens', 'habilitations', 'ordres_travail'],
      afficher: afficherFiche,
    });
  });

  return {};
})());
