'use strict';
// Garanties — écran « Garanties et contrats » (2.2, lot L4 ; CDC §3.4, D182, D187, D190, CS173, CS175).
// Routes (profil responsable seul : l'entrée de menu est cachée au technicien et au demandeur, App les renvoie à
// l'accueil s'ils ouvrent l'adresse) :
//   #/garanties                 compteurs, puis onglets Garanties et Contrats ; l'adresse garde l'onglet et ses
//                               filtres : ?onglet=garanties|contrats, ?filtre=, ?fournisseur=, ?recherche=.
//                               ?filtre= : garanties → sous-garantie (en cours ou se termine bientôt), bientot,
//                               a-venir, terminee, fin-inconnue ; contrats → a-decider (en alerte : à décider avec
//                               reconduction tacite, se termine bientôt sans, T463), a-mettre-a-jour, preavis-depasse,
//                               en-cours, termine, fin-inconnue. Pied des contrats : total des montants annuels des
//                               contrats en cours, ceux sans montant comptés à part, jamais estimés (D190).
//   #/garanties/garantie/<id>   fiche : statut et raison, équipement, fournisseur (tel:, mailto:), conditions,
//                               document, historique du journal ; « Modifier », « Retirer la garantie » (confirmée).
//   #/garanties/contrat/<id>    fiche : bandeau de l'échéance avec « Écrire au prestataire » (mailto: : Prévo n'envoie
//                               rien), « Modifier », « Noter la résiliation » et « Reconduire » (reconduction tacite),
//                               « Retirer le contrat » (confirmé), historique du journal ; « Résiliation notée le … »
//                               sous le statut quand le journal la porte (Garanties.resiliationNotee, T463).
// Phrase D182 sous le titre des trois écrans (garanties.principe.texte) ; aucun texte ne dit « conforme » (CS175).
// Montant annuel : écrans du responsable seulement (le technicien n'y entre pas ; le serveur lui cache la colonne,
// T453, D126). Ligne retirée (actif = 0) : absente de la liste et des compteurs ; sa fiche reste lisible, sans bouton.
// Les routes des formulaires (garanties-formulaires.js, chargé avant) sont enregistrées avant celles-ci.
// Chargé juste après garanties-formulaires.js et avant garanties-encarts.js. Complète l'objet Garanties.

Object.assign(Garanties, (() => {

  // Outils de garanties-regles.js.
  const { texte, dateIso, estActif, estTacite, preavisMois, reconductionMois, equipementSuivi } = Garanties.interne;
  const { libelleStatut } = Garanties;

  const ADRESSE_LISTE = '#/garanties';
  const ONGLETS = ['garanties', 'contrats'];
  const LIMITE_HISTORIQUE = 30;
  const EQUIPEMENTS_AFFICHES = 2;          // au-delà, la liste dit « 3 équipements »
  // Couleur du badge de chaque statut (le texte dit toujours le statut, la couleur aide).
  const TONS = { en_cours: 'ok', bientot: 'attention', a_venir: 'info', terminee: 'neutre', termine: 'neutre',
    fin_inconnue: 'attention', a_decider: 'ko', a_mettre_a_jour: 'violet', preavis_depasse: 'cyan' };
  // Ordre des listes : ce qui demande une décision d'abord.
  const ORDRE = {
    garanties: ['bientot', 'fin_inconnue', 'en_cours', 'a_venir', 'terminee'],
    contrats: ['a_decider', 'bientot', 'a_mettre_a_jour', 'fin_inconnue', 'preavis_depasse', 'en_cours', 'termine'],
  };

  // ===========================================================================================
  // 15. Petits outils d'écran
  // ===========================================================================================

  function majuscule(valeur) {
    const brut = texte(valeur);
    return brut.charAt(0).toUpperCase() + brut.slice(1);
  }

  function libelleChamp(table, nom) {
    const champ = Schema.champ(table, nom);
    return champ ? champ.libelle : nom;
  }

  function comparerIds(a, b) {
    return texte(a.id).localeCompare(texte(b.id), 'fr', { numeric: true });
  }

  function fournisseurDe(id) {
    return texte(id) ? Donnees.trouver('fournisseurs', texte(id)) || null : null;
  }

  function nomFournisseur(id) {
    const fournisseur = fournisseurDe(id);
    return fournisseur ? (fournisseur.nom || fournisseur.id) : texte(id);
  }

  /** « CP-01 Compresseur à vis » ; « équipement introuvable (EQ-0099) » si l'identifiant n'existe plus. */
  function nomEquipement(id) {
    const equipement = Donnees.trouver('equipements', texte(id));
    if (!equipement) return I18n.t('garanties.formulaire_contrat.equipement_introuvable', { equipementId: texte(id) });
    return [equipement.repere || equipement.id, equipement.designation].filter(Boolean).join(' ');
  }

  function lienEquipement(id) {
    if (!Donnees.trouver('equipements', texte(id))) return UI.html`<span>${nomEquipement(id)}</span>`;
    return UI.html`<a href="#/equipement/${encodeURIComponent(texte(id))}">${nomEquipement(id)}</a>`;
  }

  function badge(statut) {
    return UI.html`<span class="garanties-statut" data-statut="${statut}">${UI.badgeStatut(statut, TONS[statut] || 'neutre', libelleStatut(statut))}</span>`;
  }

  /** « dans 45 jours », « aujourd'hui » (jours ≥ 0). */
  function quand(jours) {
    return jours === 0 ? I18n.t('garanties.quand.aujourd_hui') : I18n.t('garanties.quand.dans_n_jours', { n: jours });
  }

  function adresseFiche(id) {
    return '#/garanties/' + (texte(id).startsWith('CTP-') ? 'contrat/' : 'garantie/') + encodeURIComponent(texte(id));
  }

  /** Nom, contact, téléphone (tel:) et e-mail (mailto:) du fournisseur ; « non renseigné » ; introuvable. */
  function blocFournisseur(id) {
    if (!texte(id)) return UI.html`<span class="muted">${I18n.t('garanties.fiche.non_renseigne')}</span>`;
    const f = fournisseurDe(id);
    if (!f) return UI.html`<span>${I18n.t('garanties.fiche.fournisseur_introuvable', { fournisseurId: texte(id) })}</span>`;
    const telephone = texte(f.telephone);
    return UI.html`<span class="garanties-fournisseur"><b>${f.nom || f.id}</b>${f.contact ? UI.html`<span>${f.contact}</span>` : ''}
      ${telephone ? UI.html`<a href="tel:${telephone.replace(/[^0-9+]/g, '')}">${telephone}</a>` : ''}
      ${texte(f.email) ? UI.html`<a href="mailto:${texte(f.email)}">${texte(f.email)}</a>` : ''}</span>`;
  }

  async function adresseDocument(nom) {
    if (!nom || !App.adaptateur) return null;
    try {
      return await App.adaptateur.urlDocument(nom);
    } catch (erreur) {
      console.warn('Prévo : document « ' + nom + ' » illisible (' + (erreur && erreur.message) + ').', erreur);
      return null;
    }
  }

  function blocDocument(nom, adresse) {
    if (!texte(nom)) return UI.html`<span class="muted">${I18n.t('garanties.fiche.aucun_document')}</span>`;
    if (!adresse) return UI.html`<span>${I18n.t('garanties.fiche.document_introuvable', { nom: texte(nom) })}</span>`;
    return UI.html`<a class="garanties-document" href="${adresse}" target="_blank" rel="noopener">${UI.icone('document')}${I18n.t('garanties.fiche.ouvrir')}</a>
      <span class="muted garanties-nom-document">${texte(nom)}</span>`;
  }

  // ===========================================================================================
  // 16. Lignes des deux listes, filtres et adresse
  // ===========================================================================================

  function lignesDe(onglet, jour, delai) {
    const table = onglet === 'contrats' ? 'contrats_prestataires' : 'garanties';
    const ordre = ORDRE[onglet];
    return Donnees.lignes(table).filter(estActif).map((ligne) => {
      const etat = onglet === 'contrats' ? Garanties.etatContrat(ligne, jour, delai) : Garanties.etatGarantie(ligne, jour, delai);
      const echeance = (onglet === 'contrats' && etat.statut === 'a_decider' ? etat.dateLimite : etat.finPeriode || etat.fin) || '9';
      return { ligne, etat, echeance };
    }).sort((a, b) => ordre.indexOf(a.etat.statut) - ordre.indexOf(b.etat.statut)
      || a.echeance.localeCompare(b.echeance) || comparerIds(a.ligne, b.ligne));
  }

  function filtreDuStatut(statut) {
    return { valeur: statut.replace(/_/g, '-'), libelle: majuscule(libelleStatut(statut)), garder: (l) => l.etat.statut === statut };
  }

  /** Choix du filtre de chaque onglet (les compteurs en emploient quatre). */
  function filtresDe(onglet) {
    if (onglet === 'contrats') {
      return [{ valeur: 'a-decider', libelle: I18n.t('garanties.filtres.a_decider'), garder: (l) => l.etat.alerte }]
        .concat(['a_mettre_a_jour', 'preavis_depasse', 'en_cours', 'termine', 'fin_inconnue'].map(filtreDuStatut));
    }
    // « Bientôt » (filtre et compteur) : la règle de l'accueil, équipements actifs hors rebut (Garanties.aEcheance, T503).
    const bientot = Object.assign(filtreDuStatut('bientot'), { garder: (l) => l.etat.statut === 'bientot' && equipementSuivi(l.ligne) });
    return [{ valeur: 'sous-garantie', libelle: I18n.t('garanties.filtres.sous_garantie'),
      garder: (l) => l.etat.statut === 'en_cours' || l.etat.statut === 'bientot' }]
      .concat([bientot], ['a_venir', 'terminee', 'fin_inconnue'].map(filtreDuStatut));
  }

  function filtresDepuis(onglet, requete) {
    const filtre = requete.get('filtre') || '';
    return { filtre: filtresDe(onglet).some((f) => f.valeur === filtre) ? filtre : '',
      fournisseur: requete.get('fournisseur') || '', recherche: requete.get('recherche') || '' };
  }

  function adresseDe(onglet, filtres) {
    const parametres = new URLSearchParams();
    parametres.set('onglet', onglet);
    ['filtre', 'fournisseur', 'recherche'].forEach((nom) => { if (filtres && filtres[nom]) parametres.set(nom, filtres[nom]); });
    return ADRESSE_LISTE + '?' + parametres.toString().replace(/\+/g, '%20');
  }

  /** Texte où la recherche cherche : équipement, fournisseur, conditions ; objet, prestataire, périmètre, équipements. */
  function texteCherche(onglet, ligne) {
    if (onglet === 'contrats') {
      return [ligne.id, ligne.objet, nomFournisseur(ligne.fournisseur_id), ligne.perimetre]
        .concat(Garanties.equipementsDuContrat(ligne).map(nomEquipement)).join(' ');
    }
    return [ligne.id, nomEquipement(ligne.equipement_id), nomFournisseur(ligne.fournisseur_id), ligne.conditions].join(' ');
  }

  function garder(onglet, l, filtres) {
    const filtre = filtresDe(onglet).find((f) => f.valeur === filtres.filtre);
    if (filtre && !filtre.garder(l)) return false;
    if (filtres.fournisseur && texte(l.ligne.fournisseur_id) !== filtres.fournisseur) return false;
    const recherche = UI.normaliserRecherche(filtres.recherche);
    return !recherche || UI.normaliserRecherche(texteCherche(onglet, l.ligne)).includes(recherche);
  }

  // ===========================================================================================
  // 17. Liste #/garanties : compteurs, onglets, filtres, tableau (cartes sur téléphone), total
  // ===========================================================================================

  function compteursHtml(lignes, delai, courant) {
    const compteur = (onglet, filtre, ton, libelle) => {
      const nombre = lignes[onglet].filter(filtresDe(onglet).find((f) => f.valeur === filtre).garder).length;
      const applique = courant.onglet === onglet && courant.filtres[onglet].filtre === filtre;
      return UI.html`<a class="${ton}" data-compteur="${filtre}" href="${adresseDe(onglet, { filtre })}">
        <div class="lib">${libelle}</div><div class="chiffre">${nombre}</div>
        <div class="comp">${applique ? I18n.t('garanties.compteurs.filtre_applique') : I18n.t('garanties.compteurs.voir_liste')}</div></a>`;
    };
    return UI.html`<div class="instruments garanties-compteurs">
      ${compteur('garanties', 'sous-garantie', 'vert', I18n.t('garanties.compteurs.garanties_en_cours'))}
      ${compteur('garanties', 'bientot', 'ambre', I18n.t('garanties.compteurs.finissent_sous', { n: delai }))}
      ${compteur('contrats', 'a-decider', 'rouge', I18n.t('garanties.compteurs.contrats_a_decider'))}
      ${compteur('contrats', 'a-mettre-a-jour', 'cyan', I18n.t('garanties.compteurs.a_mettre_a_jour'))}</div>`;
  }

  // Le statut vient juste après la ligne : sur un écran étroit, le tableau défile dans son cadre (comme Contrôles).
  function colonneStatut(onglet) {
    return { cle: 'statut', libelle: I18n.t('commun.champ.statut'), classe: 'garanties-col-statut',
      valeurTri: (l) => ORDRE[onglet].indexOf(l.etat.statut),
      rendu: (l) => UI.html`${badge(l.etat.statut)}<small class="garanties-sous-ligne">${l.etat.raison}</small>` };
  }

  function colonneDate(cle, libelle, valeur) {
    return { cle, libelle, type: 'date', classe: 'sans-coupure', valeurTri: valeur, rendu: (l) => UI.dateFr(valeur(l)) };
  }

  function colonnesGaranties() {
    const equipement = (l) => Donnees.trouver('equipements', texte(l.ligne.equipement_id));
    const repere = (l) => (equipement(l) || {}).repere || texte(l.ligne.equipement_id);
    return [
      { cle: 'equipement', libelle: I18n.t('commun.champ.equipement'), valeurTri: repere, classe: 'garanties-col-equipement',
        rendu: (l) => UI.html`<a class="garanties-lien" href="${adresseFiche(l.ligne.id)}">${repere(l)}</a>
          <small class="garanties-sous-ligne">${equipement(l) ? equipement(l).designation : nomEquipement(l.ligne.equipement_id)}</small>` },
      colonneStatut('garanties'),
      { cle: 'fournisseur', libelle: libelleChamp('garanties', 'fournisseur_id'), valeurTri: (l) => nomFournisseur(l.ligne.fournisseur_id),
        rendu: (l) => nomFournisseur(l.ligne.fournisseur_id) },
      colonneDate('debut', I18n.t('garanties.colonnes.debut'), (l) => l.etat.debut),
      colonneDate('fin', I18n.t('garanties.colonnes.fin'), (l) => l.etat.fin),
      { cle: 'document', libelle: libelleChamp('garanties', 'document'), valeurTri: (l) => texte(l.ligne.document),
        rendu: (l) => (texte(l.ligne.document) ? I18n.t('garanties.colonnes.document_joint') : '') },
    ];
  }

  /** Repères des équipements cités (« CP-01, CP-02 »), ou « 3 équipements » au-delà de deux. */
  function equipementsCourts(contrat) {
    const ids = Garanties.equipementsDuContrat(contrat);
    if (ids.length > EQUIPEMENTS_AFFICHES) {
      return UI.html`<span title="${ids.map(nomEquipement).join(', ')}">${I18n.t('garanties.colonnes.n_equipements', { n: ids.length })}</span>`;
    }
    return UI.html`${ids.map((id, rang) => UI.html`${rang ? ', ' : ''}<span class="sans-coupure" title="${nomEquipement(id)}">${(Donnees.trouver('equipements', id) || {}).repere || id}</span>`)}`;
  }

  function colonnesContrats() {
    return [
      { cle: 'objet', libelle: I18n.t('garanties.colonnes.objet'), valeurTri: (l) => l.ligne.objet, classe: 'garanties-col-objet',
        rendu: (l) => UI.html`<a class="garanties-lien" href="${adresseFiche(l.ligne.id)}">${texte(l.ligne.objet) || l.ligne.id}</a>` },
      colonneStatut('contrats'),
      colonneDate('limite', I18n.t('garanties.colonnes.date_limite'), (l) => l.etat.dateLimite),
      colonneDate('fin', I18n.t('garanties.colonnes.fin'), (l) => l.etat.fin),
      { cle: 'prestataire', libelle: libelleChamp('contrats_prestataires', 'fournisseur_id'),
        valeurTri: (l) => nomFournisseur(l.ligne.fournisseur_id), rendu: (l) => nomFournisseur(l.ligne.fournisseur_id) },
      { cle: 'montant', libelle: libelleChamp('contrats_prestataires', 'montant_annuel'), type: 'nombre', classe: 'sans-coupure',
        valeurTri: (l) => texte(l.ligne.montant_annuel), rendu: (l) => (texte(l.ligne.montant_annuel) ? UI.euro(l.ligne.montant_annuel) : '') },
      { cle: 'tacite', libelle: libelleChamp('contrats_prestataires', 'reconduction_tacite'), valeurTri: (l) => (estTacite(l.ligne) ? 1 : 0),
        rendu: (l) => (estTacite(l.ligne) ? I18n.t('garanties.valeur.oui') : I18n.t('garanties.valeur.non')) },
      { cle: 'equipements', libelle: I18n.t('garanties.colonnes.equipements'), triable: false, rendu: (l) => equipementsCourts(l.ligne) },
    ];
  }

  function carteListe(onglet, l) {
    const contrat = onglet === 'contrats';
    const tete = contrat ? texte(l.ligne.objet) || l.ligne.id : nomEquipement(l.ligne.equipement_id);
    const fournisseur = nomFournisseur(l.ligne.fournisseur_id);
    return UI.html`<a class="garanties-lien" href="${adresseFiche(l.ligne.id)}" data-ligne="${l.ligne.id}">
      <div class="carte-tete"><b>${tete}</b>${badge(l.etat.statut)}</div>
      ${fournisseur ? UI.html`<div class="carte-titre">${fournisseur}</div>` : ''}
      <div class="carte-meta"><span>${l.etat.raison}</span>${contrat && texte(l.ligne.montant_annuel)
    ? UI.html`<span>${UI.euro(l.ligne.montant_annuel)}</span>` : ''}</div></a>`;
  }

  /** Pied des contrats : « Total des contrats en cours : 18 400,00 € par an — 2 contrats sans montant. » */
  function texteTotal(jour) {
    const total = Garanties.totalMontants(Donnees.lignes('contrats_prestataires'), jour);
    const montant = UI.euro(total.centimes / 100);
    return total.sansMontant ? I18n.t('garanties.liste.total_sans_montant', { montant, n: total.sansMontant })
      : I18n.t('garanties.liste.total', { montant });
  }

  function optionsFournisseurs(onglet, lignes, choisi) {
    const ids = [...new Set(lignes.map((l) => texte(l.ligne.fournisseur_id)).filter(Boolean))]
      .sort((a, b) => UI.comparerTextes(nomFournisseur(a), nomFournisseur(b)));
    const tous = onglet === 'contrats' ? I18n.t('garanties.filtres.tous_prestataires') : I18n.t('garanties.filtres.tous_fournisseurs');
    return UI.html`<option value="">${tous}</option>${ids.map((id) => UI.html`<option value="${id}"${id === choisi ? UI.brut(' selected') : ''}>${nomFournisseur(id)}</option>`)}`;
  }

  /** Un onglet : vide expliqué, ou filtres, compteur, tableau ou cartes (et le total des contrats). */
  function afficherOnglet(panneau, onglet, liste) {
    const contrat = onglet === 'contrats';
    const lignes = liste.lignes[onglet];
    const filtres = liste.filtres[onglet];
    if (!lignes.length) {
      UI.remplir(panneau, contrat ? UI.vide(I18n.t('garanties.liste.aucun_contrat'), I18n.t('garanties.formulaire_contrat.introduction'), 'document')
        : UI.vide(I18n.t('garanties.liste.aucune_garantie'), I18n.t('garanties.liste.aucune_garantie_texte'), 'document'));
      return;
    }
    const id = UI.identifiantUnique('garanties-' + onglet);
    UI.remplir(panneau, UI.html`
      <form class="filtres garanties-filtres" data-hors-saisie role="search" aria-label="${contrat ? I18n.t('garanties.filtres.filtrer_contrats') : I18n.t('garanties.filtres.filtrer_garanties')}">
        <label class="visuellement-cache" for="${id}-recherche">${I18n.t('garanties.filtres.rechercher')}</label>
        <input type="search" id="${id}-recherche" name="recherche" value="${filtres.recherche}" autocomplete="off"
          placeholder="${contrat ? I18n.t('garanties.filtres.exemple_contrats') : I18n.t('garanties.filtres.exemple_garanties')}">
        <label class="visuellement-cache" for="${id}-filtre">${I18n.t('commun.champ.statut')}</label>
        <select id="${id}-filtre" name="filtre"><option value="">${I18n.t('garanties.filtres.tous_statuts')}</option>${filtresDe(onglet).map((f) => UI.html`<option value="${f.valeur}"${f.valeur === filtres.filtre ? UI.brut(' selected') : ''}>${f.libelle}</option>`)}</select>
        <label class="visuellement-cache" for="${id}-fournisseur">${libelleChamp(contrat ? 'contrats_prestataires' : 'garanties', 'fournisseur_id')}</label>
        <select id="${id}-fournisseur" name="fournisseur">${optionsFournisseurs(onglet, lignes, filtres.fournisseur)}</select>
      </form>
      <p class="note garanties-nombre" role="status"></p>
      <div class="carte garanties-liste" data-onglet="${onglet}"></div>
      ${contrat ? UI.html`<p class="garanties-total">${texteTotal(liste.jour)}</p>` : ''}`);
    const zone = UI.$('.garanties-liste', panneau);
    const nombre = UI.$('.garanties-nombre', panneau);
    const formulaire = UI.$('form', panneau);

    function rafraichir() {
      const gardees = lignes.filter((l) => garder(onglet, l, filtres));
      const sansResultat = contrat ? I18n.t('garanties.liste.aucun_contrat_filtres') : I18n.t('garanties.liste.aucune_garantie_filtres');
      if (UI.estTelephone()) {
        UI.remplir(zone, gardees.length ? UI.html`<ul class="liste-cartes">${gardees.map((l) => UI.html`<li>${carteListe(onglet, l)}</li>`)}</ul>`
          : UI.html`<p class="muted">${sansResultat}</p>`);
      } else {
        UI.remplir(zone, UI.tableau({ colonnes: contrat ? colonnesContrats() : colonnesGaranties(), lignes: gardees, vide: sansResultat,
          libelle: contrat ? I18n.t('garanties.onglets.contrats') : I18n.t('garanties.onglets.garanties') }));
      }
      nombre.textContent = contrat ? I18n.t('garanties.liste.nombre_contrats', { n: gardees.length, total: lignes.length })
        : I18n.t('garanties.liste.nombre_garanties', { n: gardees.length, total: lignes.length });
    }
    function lireFiltres() {
      const valeurs = UI.lireFormulaire(formulaire);
      Object.assign(filtres, { recherche: valeurs.recherche || '', filtre: valeurs.filtre || '', fournisseur: valeurs.fournisseur || '' });
      liste.changer(onglet);
      rafraichir();
    }
    formulaire.addEventListener('input', lireFiltres);
    formulaire.addEventListener('change', lireFiltres);
    formulaire.addEventListener('submit', (evenement) => evenement.preventDefault());
    rafraichir();
  }

  function afficherListe(conteneur, parametres) {
    // En-tête du téléphone : le libellé court, comme la barre du bas (le titre long est coupé sur un iPhone en anglais et
    // en turc, planche T497) ; le titre de l'onglet et le grand titre de la page restent complets.
    App.definirTitreMobile(I18n.t('garanties.menu.court'));
    const requete = (parametres && parametres.requete) || new URLSearchParams();
    const actif = ONGLETS.includes(requete.get('onglet')) ? requete.get('onglet') : 'garanties';
    const jour = Donnees.aujourdhui();
    const delai = Garanties.delaiAlerte();
    const vides = { filtre: '', fournisseur: '', recherche: '' };
    const liste = {
      jour, onglet: actif,
      lignes: { garanties: lignesDe('garanties', jour, delai), contrats: lignesDe('contrats', jour, delai) },
      filtres: { garanties: Object.assign({}, vides), contrats: Object.assign({}, vides) },
      // L'onglet ou un filtre change : l'adresse le garde (actualiser le garde), les compteurs disent le filtre.
      changer(onglet) {
        liste.onglet = onglet;
        try { history.replaceState(history.state, '', adresseDe(onglet, liste.filtres[onglet])); } catch (erreur) { /* adresse gardée */ }
        const compteurs = UI.$('.garanties-compteurs', conteneur);
        if (compteurs) compteurs.replaceWith(UI.element(compteursHtml(liste.lignes, delai, liste)));
      },
    };
    liste.filtres[actif] = filtresDepuis(actif, requete);
    UI.remplir(conteneur, UI.html`
      <div class="garanties garanties-ecran">
        <div class="entete-page">
          <div><h1>${I18n.t('garanties.liste.titre')}</h1>
            <p>${I18n.t('garanties.liste.introduction')}</p>
            <p class="note garanties-principe">${I18n.t('garanties.principe.texte')}</p></div>
          <div class="actions">
            <a class="btn btn-primaire" id="garanties-nouvelle" href="${Garanties.adresseNouvelleGarantie()}">${UI.icone('ajouter')}${I18n.t('garanties.formulaire_garantie.titre_nouvelle')}</a>
            <a class="btn btn-secondaire" id="garanties-nouveau-contrat" href="#/garanties/contrat/nouveau">${UI.icone('ajouter')}${I18n.t('garanties.formulaire_contrat.titre_nouveau')}</a></div>
        </div>
        ${compteursHtml(liste.lignes, delai, liste)}
        <div class="garanties-onglets"></div>
      </div>`);
    UI.onglets(UI.$('.garanties-onglets', conteneur), ONGLETS.map((onglet) => ({
      id: onglet, libelle: I18n.t('garanties.onglets.' + onglet), compteur: liste.lignes[onglet].length,
      afficher: (panneau) => afficherOnglet(panneau, onglet, liste),
    })), { actif, libelle: I18n.t('garanties.onglets.libelle'), surChangement: (onglet) => liste.changer(onglet) });
  }

  // ===========================================================================================
  // 18. Historique : entrées du journal de la ligne (D156 : actions écrites en français, traduites ici)
  // ===========================================================================================

  // Compléments écrits par garanties-ecritures.js après « création — » ou « modification : champs — ».
  const COMPLEMENTS = [
    [/^garantie enregistrée$/, 'garanties.journal.garantie_enregistree'],
    [/^modification de la garantie$/, 'garanties.journal.modification_garantie'],
    [/^garantie retirée$/, 'garanties.journal.garantie_retiree'],
    [/^contrat enregistré$/, 'garanties.journal.contrat_enregistre'],
    [/^modification du contrat$/, 'garanties.journal.modification_contrat'],
    [/^contrat retiré$/, 'garanties.journal.contrat_retire'],
  ];
  const MOTIF_DOCUMENT = /^([\s\S]*) ; document : (.+)$/;
  const MOTIF_RECONDUCTION = /^reconduction : (.+) → (.+)$/;
  const MOTIF_PERIODE = /^du (.+) au (.+)$/;
  const MOTIF_JUSQU_AU = /^jusqu'au (.+)$/;
  const MOTIF_RESILIATION = /^résiliation notée : lettre du ([^;]*?)(?: ; ([\s\S]*))?$/;
  const MOTIF_CREATION = /^création$/;
  const MOTIF_MODIFICATION = /^modification : (.+)$/;

  function periodeJournal(periode) {
    let trouve = MOTIF_PERIODE.exec(periode);
    if (trouve) return I18n.t('garanties.journal.periode', { debut: trouve[1], fin: trouve[2] });
    trouve = MOTIF_JUSQU_AU.exec(periode);
    return trouve ? I18n.t('garanties.journal.periode_sans_debut', { fin: trouve[1] }) : periode;
  }

  /** Complément traduit, ou null s'il est inconnu (l'action est alors affichée telle quelle). */
  function complementJournal(complement) {
    let trouve = MOTIF_DOCUMENT.exec(complement);
    if (trouve) {
      const debut = complementJournal(trouve[1]);
      return debut === null ? null : I18n.t('garanties.journal.document', { complement: debut, nom: trouve[2] });
    }
    const connu = COMPLEMENTS.find(([motif]) => motif.test(complement));
    if (connu) return I18n.t(connu[1]);
    trouve = MOTIF_RECONDUCTION.exec(complement);
    if (trouve) return I18n.t('garanties.journal.reconduction', { avant: periodeJournal(trouve[1]), apres: periodeJournal(trouve[2]) });
    trouve = MOTIF_RESILIATION.exec(complement);
    if (trouve) {
      return trouve[2] ? I18n.t('garanties.journal.resiliation_commentaire', { date: trouve[1], commentaire: trouve[2] })
        : I18n.t('garanties.journal.resiliation', { date: trouve[1] });
    }
    return null;
  }

  function actionJournal(table, action) {
    const brute = texte(action);
    const coupure = brute.indexOf(' — ');
    const debut = coupure < 0 ? brute : brute.slice(0, coupure);
    const modification = MOTIF_MODIFICATION.exec(debut);
    let base = null;
    if (MOTIF_CREATION.test(debut)) base = I18n.t('garanties.journal.creation');
    else if (modification) {
      base = I18n.t('garanties.journal.modification', { champs: modification[1].split(', ').map((nom) => libelleChamp(table, nom)).join(', ') });
    }
    if (base === null) return majuscule(complementJournal(brute) || brute);     // « résiliation notée » seule
    if (coupure < 0) return base;
    const complement = complementJournal(brute.slice(coupure + 3));
    return complement === null ? brute : I18n.t('garanties.journal.action_complement', { action: base, complement });
  }

  function carteHistorique(table, id) {
    const entrees = Donnees.lignes('journal').filter((e) => e.table === table && e.id_ligne === id)
      .sort((a, b) => texte(b.date_heure).localeCompare(texte(a.date_heure)) || texte(b.id).localeCompare(texte(a.id)));
    return UI.html`<article class="carte garanties-historique"><h2>${I18n.t('garanties.historique.titre', { n: entrees.length })}</h2>
      ${entrees.length ? UI.html`<ol class="garanties-journal">${entrees.slice(0, LIMITE_HISTORIQUE).map((e) => UI.html`<li>
        <span class="garanties-quand">${UI.dateHeureFr(e.date_heure)}</span><span class="garanties-action">${actionJournal(table, e.action)}</span>
        <span class="muted">${[e.profil, e.poste].filter(Boolean).join(' · ')}</span></li>`)}</ol>
        ${entrees.length > LIMITE_HISTORIQUE ? UI.html`<p class="note">${I18n.t('garanties.historique.plus_recentes', { limite: LIMITE_HISTORIQUE, n: entrees.length })}</p>` : ''}`
    : UI.html`<p class="muted">${I18n.t('garanties.historique.vide')}</p>`}</article>`;
  }

  // ===========================================================================================
  // 19. Fiches d'une garantie et d'un contrat
  // ===========================================================================================

  function fil(onglet) {
    return UI.html`<a href="${ADRESSE_LISTE}">${I18n.t('garanties.liste.titre')}</a> <span aria-hidden="true">›</span>
      <a href="${adresseDe(onglet)}">${I18n.t('garanties.onglets.' + onglet)}</a>`;
  }

  function afficherIntrouvable(conteneur, onglet, titre, message) {
    App.definirTitre(titre);
    UI.remplir(conteneur, UI.html`<div class="garanties garanties-fiche"><div class="entete-page"><div>
      <div class="fil">${fil(onglet)}</div><h1>${titre}</h1></div></div>
      ${UI.vide(message, I18n.t('commun.message.saisi_sur_autre_poste'), 'document')}</div>`);
  }

  /** Entête commune : fil, titre, statut et raison (puis le complément, s'il y en a un), phrase D182, boutons (ligne
   *  active seulement). */
  function enteteFiche(onglet, titre, etat, boutons, complement) {
    return UI.html`<div class="entete-page"><div>
        <div class="fil">${fil(onglet)}</div><h1>${titre}</h1>
        <p class="garanties-badges">${badge(etat.statut)} <span class="garanties-raison">${etat.raison}</span></p>${complement || ''}
        <p class="note garanties-principe">${I18n.t('garanties.principe.texte')}</p></div>
      ${boutons ? UI.html`<div class="actions">${boutons}</div>` : ''}</div>`;
  }

  /** Lecture asynchrone du document, puis l'écran si l'utilisateur n'a pas changé d'adresse entre-temps. */
  async function chargerFiche(table, id, chemin) {
    const ligne = Donnees.trouver(table, id);
    const adresse = ligne ? await adresseDocument(ligne.document) : null;
    if (decodeURIComponent(location.hash.split('?')[0]) !== chemin) return null;
    return { ligne: Donnees.trouver(table, id), adresse };
  }

  async function retirer(message, titre, retrait, toast, onglet) {
    if (!await UI.confirmer(message, { titre, oui: I18n.t('garanties.fiche.retirer'), danger: true })) return;
    try {
      await retrait();
      UI.toast(toast, 'succes');
      App.naviguer(adresseDe(onglet));
    } catch (erreur) {
      App.signalerErreur(erreur, 'retrait : ' + onglet);
    }
  }

  async function afficherFicheGarantie(conteneur, parametres) {
    const id = parametres.id;
    const lu = await chargerFiche('garanties', id, '#/garanties/garantie/' + id);
    if (!lu) return;
    const garantie = lu.ligne;
    if (!garantie) {
      afficherIntrouvable(conteneur, 'garanties', I18n.t('garanties.formulaire_garantie.introuvable'),
        I18n.t('garanties.ligne.garantie_introuvable', { garantieId: id }));
      return;
    }
    const actif = estActif(garantie);
    const etat = Garanties.etatGarantie(garantie);
    const titre = I18n.t('garanties.fiche_garantie.titre', { equipement: nomEquipement(garantie.equipement_id) });
    App.definirTitre(titre);
    UI.remplir(conteneur, UI.html`<div class="garanties garanties-fiche" data-garantie="${garantie.id}">
      ${enteteFiche('garanties', titre, etat, actif ? UI.html`
        <a class="btn btn-primaire" id="garantie-modifier" href="${Garanties.adresseModification(garantie.id)}">${I18n.t('commun.bouton.modifier')}</a>
        <button type="button" class="btn btn-secondaire" id="garantie-retirer">${I18n.t('garanties.fiche_garantie.retirer')}</button>` : '')}
      ${actif ? '' : UI.html`<div class="alertes"><div class="alerte attention" role="status">${UI.icone('alerte')}<div class="alerte-texte">${I18n.t('garanties.fiche_garantie.retiree')}</div></div></div>`}
      <article class="carte"><h2>${I18n.t('garanties.fiche_garantie.carte')}</h2><dl class="valeurs">
        <dt>${I18n.t('commun.champ.equipement')}</dt><dd>${lienEquipement(garantie.equipement_id)}</dd>
        <dt>${libelleChamp('garanties', 'fournisseur_id')}</dt><dd>${blocFournisseur(garantie.fournisseur_id)}</dd>
        <dt>${libelleChamp('garanties', 'date_debut')}</dt><dd>${UI.dateFr(dateIso(garantie.date_debut) || texte(garantie.date_debut))}</dd>
        <dt>${libelleChamp('garanties', 'date_fin')}</dt><dd>${UI.dateFr(dateIso(garantie.date_fin) || texte(garantie.date_fin))}</dd>
        <dt>${libelleChamp('garanties', 'conditions')}</dt><dd class="garanties-texte-long">${texte(garantie.conditions)}</dd>
        <dt>${libelleChamp('garanties', 'document')}</dt><dd>${blocDocument(garantie.document, lu.adresse)}</dd></dl></article>
      ${carteHistorique('garanties', garantie.id)}</div>`);
    const bouton = UI.$('#garantie-retirer', conteneur);
    if (bouton) {
      bouton.addEventListener('click', () => retirer(I18n.t('garanties.fiche_garantie.retirer_question'), I18n.t('garanties.fiche_garantie.retirer'),
        () => Garanties.retirerGarantie(garantie.id), I18n.t('garanties.fiche_garantie.retiree_toast'), 'garanties'));
    }
  }

  /** « Écrire au prestataire » : la messagerie du poste s'ouvre (mailto:), Prévo n'envoie rien. */
  function adresseCourriel(contrat) {
    const fournisseur = fournisseurDe(contrat.fournisseur_id);
    const destinataire = fournisseur ? texte(fournisseur.email) : '';
    return 'mailto:' + encodeURIComponent(destinataire).replace(/%40/g, '@') + '?subject='
      + encodeURIComponent(I18n.t('garanties.fiche_contrat.objet_courriel', { objet: texte(contrat.objet) }));
  }

  /** Bandeau de l'échéance (à décider, se termine bientôt, dates à mettre à jour), ou ''. */
  function bandeauContrat(contrat, etat) {
    const valeurs = { fin: UI.dateFr(etat.finPeriode), limite: UI.dateFr(etat.dateLimite) };
    let message = '';
    let ecrire = false;
    if (etat.statut === 'a_decider') {                 // reconduction tacite seulement (T463)
      message = I18n.t('garanties.fiche_contrat.bandeau_a_decider_tacite', Object.assign(valeurs, { quand: quand(etat.joursAvantLimite) }));
      ecrire = true;
    } else if (etat.statut === 'bientot') {
      message = I18n.t('garanties.fiche_contrat.bandeau_bientot', { fin: valeurs.fin, quand: quand(etat.joursAvantFin) });
    } else if (etat.statut === 'a_mettre_a_jour') {
      message = I18n.t('garanties.fiche_contrat.bandeau_a_mettre_a_jour', { fin: UI.dateFr(etat.fin) });
    }
    if (!message) return '';
    return UI.html`<div class="alertes"><div class="alerte attention garanties-bandeau" role="status">${UI.icone('alerte')}<div class="alerte-texte">
      <p>${message}</p>${ecrire ? UI.html`<a class="btn btn-primaire" id="contrat-ecrire" href="${adresseCourriel(contrat)}">${UI.icone('demandes')}${I18n.t('garanties.fiche_contrat.ecrire')}</a>` : ''}</div></div></div>`;
  }

  function valeursContrat(contrat, etat, adresse) {
    const ids = Garanties.equipementsDuContrat(contrat);
    const preavis = preavisMois(contrat);
    const reconduction = reconductionMois(contrat);
    const limite = !etat.dateLimite ? '' : (etat.joursAvantLimite >= 0
      ? I18n.t('garanties.fiche_contrat.date_limite_quand', { date: UI.dateFr(etat.dateLimite), quand: quand(etat.joursAvantLimite) })
      : I18n.t('garanties.fiche_contrat.date_limite_passee', { date: UI.dateFr(etat.dateLimite) }));
    const tacite = estTacite(contrat) ? (reconduction ? I18n.t('garanties.fiche_contrat.tacite_par_periodes', { n: reconduction })
      : I18n.t('garanties.valeur.oui')) : I18n.t('garanties.valeur.non');
    const libelle = (nom) => libelleChamp('contrats_prestataires', nom);
    return UI.html`<dl class="valeurs">
      <dt>${libelle('fournisseur_id')}</dt><dd>${blocFournisseur(contrat.fournisseur_id)}</dd>
      <dt>${libelle('objet')}</dt><dd>${texte(contrat.objet)}</dd>
      <dt>${libelle('equipement_ids')}</dt><dd>${ids.length ? UI.html`<ul class="garanties-equipements-liste">${ids.map((e) => UI.html`<li>${lienEquipement(e)}</li>`)}</ul>` : ''}</dd>
      <dt>${libelle('perimetre')}</dt><dd class="garanties-texte-long">${texte(contrat.perimetre)}</dd>
      <dt>${libelle('date_debut')}</dt><dd>${UI.dateFr(dateIso(contrat.date_debut) || texte(contrat.date_debut))}</dd>
      <dt>${I18n.t('garanties.formulaire_contrat.fin')}</dt><dd>${UI.dateFr(etat.fin || texte(contrat.date_fin))}</dd>
      <dt>${I18n.t('garanties.fiche_contrat.preavis')}</dt><dd>${preavis ? I18n.t('garanties.fiche_contrat.preavis_mois', { n: preavis }) : I18n.t('garanties.fiche_contrat.sans_preavis')}</dd>
      <dt>${I18n.t('garanties.colonnes.date_limite')}</dt><dd>${limite}</dd>
      <dt>${libelle('reconduction_tacite')}</dt><dd>${tacite}</dd>
      <dt>${libelle('montant_annuel')}</dt><dd>${texte(contrat.montant_annuel) ? UI.euro(contrat.montant_annuel) : ''}</dd>
      <dt>${libelle('document')}</dt><dd>${blocDocument(contrat.document, adresse)}</dd></dl>`;
  }

  function champDate(nom, libelle, valeur, reglages) {
    return UI.champ({ nom, type: 'date', libelle }, valeur, Object.assign({ obligatoire: true }, reglages || {}));
  }

  /** « Noter la résiliation » : date d'envoi de la lettre (obligatoire, pas dans le futur), commentaire. */
  async function ouvrirResiliation(contrat, etat) {
    const jour = Donnees.aujourdhui();
    const fait = await UI.fenetreAction({ classe: 'garanties-fenetre', titre: I18n.t('garanties.fiche_contrat.noter_resiliation'),
      introduction: UI.html`<p>${I18n.t('garanties.resiliation.introduction', { fin: UI.dateFr(etat.fin) })}</p>`,
      champs: [champDate('date', I18n.t('garanties.resiliation.date'), jour, { attributs: { max: jour } }),
        UI.champ({ nom: 'commentaire', type: 'texte_long', libelle: I18n.t('commun.champ.commentaire') }, '')],
      libelleValider: I18n.t('commun.bouton.enregistrer'),
      verifier: (valeurs) => (valeurs.date > jour ? [{ nom: 'date', message: I18n.t('garanties.noter_resiliation.date_future') }] : []),
      action: (valeurs) => Garanties.noterResiliation(contrat.id, valeurs),
    });
    if (fait) await apresEcriture(I18n.t('garanties.resiliation.notee', { fin: UI.dateFr(etat.fin) }));
  }

  /** « Reconduire » : nouvelle période proposée (Garanties.propositionReconduction), modifiable. */
  async function ouvrirReconduction(contrat) {
    const proposee = Garanties.propositionReconduction(contrat) || { date_debut: '', date_fin: '', mois: 12 };
    let fin = '';
    const fait = await UI.fenetreAction({ classe: 'garanties-fenetre', titre: I18n.t('garanties.reconduction.titre'),
      introduction: UI.html`<p>${I18n.t('garanties.reconduction.introduction', { n: proposee.mois, fin: UI.dateFr(dateIso(contrat.date_fin)) })}</p>`,
      champs: [champDate('date_debut', I18n.t('garanties.reconduction.debut'), proposee.date_debut, { obligatoire: false }),
        champDate('date_fin', I18n.t('garanties.reconduction.fin'), proposee.date_fin)],
      libelleValider: I18n.t('garanties.fiche_contrat.reconduire'),
      verifier: () => [],
      action: async (valeurs) => { fin = (await Garanties.reconduireContrat(contrat.id, valeurs)).date_fin; },
    });
    if (fait) await apresEcriture(I18n.t('garanties.reconduction.faite', { fin: UI.dateFr(fin) }));
  }

  async function apresEcriture(message) {
    App.marquerSaisie(false);
    UI.toast(message, 'succes');
    await App.reafficher();
  }

  async function afficherFicheContrat(conteneur, parametres) {
    const id = parametres.id;
    const lu = await chargerFiche('contrats_prestataires', id, '#/garanties/contrat/' + id);
    if (!lu) return;
    const contrat = lu.ligne;
    if (!contrat) {
      afficherIntrouvable(conteneur, 'contrats', I18n.t('garanties.formulaire_contrat.introuvable'),
        I18n.t('garanties.ligne.contrat_introuvable', { contratId: id }));
      return;
    }
    const actif = estActif(contrat);
    const tacite = estTacite(contrat);
    const etat = Garanties.etatContrat(contrat);
    const titre = I18n.t('garanties.fiche_contrat.titre', { objet: texte(contrat.objet) || contrat.id });
    // Sans reconduction tacite, la décision est prise : « Résiliation notée le … » si le journal la porte (T463).
    const resiliation = Garanties.resiliationNotee(contrat);
    const complement = resiliation && UI.html`<p class="garanties-resiliation">${I18n.t('garanties.fiche_contrat.resiliation_notee',
      { notee: UI.dateFr(resiliation.notee), lettre: UI.dateFr(resiliation.lettre), fin: UI.dateFr(etat.finPeriode) })}</p>`;
    // Fin enregistrée passée, quel que soit le statut : « Noter la résiliation » est refusé, l'écran guide vers « Reconduire » (T464, T503).
    const finPassee = etat.periodeCalculee || etat.statut === 'a_mettre_a_jour';
    const aReconduire = actif && tacite && finPassee
      && UI.html`<p class="garanties-resiliation">${I18n.t('garanties.noter_resiliation.reconduire_d_abord', { fin: UI.dateFr(etat.fin) })}</p>`;
    App.definirTitre(titre);
    UI.remplir(conteneur, UI.html`<div class="garanties garanties-fiche" data-contrat="${contrat.id}">
      ${enteteFiche('contrats', titre, etat, actif ? UI.html`
        <a class="btn btn-primaire" id="contrat-modifier" href="${Garanties.adresseModification(contrat.id)}">${I18n.t('commun.bouton.modifier')}</a>
        ${tacite ? UI.html`${finPassee ? '' : UI.html`<button type="button" class="btn btn-secondaire" id="contrat-resiliation">${I18n.t('garanties.fiche_contrat.noter_resiliation')}</button>`}
        <button type="button" class="btn btn-secondaire" id="contrat-reconduire">${I18n.t('garanties.fiche_contrat.reconduire')}</button>` : ''}
        <button type="button" class="btn btn-secondaire" id="contrat-retirer">${I18n.t('garanties.fiche_contrat.retirer')}</button>` : '', complement || aReconduire)}
      ${actif ? bandeauContrat(contrat, etat) : UI.html`<div class="alertes"><div class="alerte attention" role="status">${UI.icone('alerte')}<div class="alerte-texte">${I18n.t('garanties.fiche_contrat.retire')}</div></div></div>`}
      <article class="carte"><h2>${I18n.t('garanties.fiche_contrat.carte')}</h2>${valeursContrat(contrat, etat, lu.adresse)}</article>
      ${carteHistorique('contrats_prestataires', contrat.id)}</div>`);
    if (!actif) return;
    const brancher = (selecteur, action) => { const bouton = UI.$(selecteur, conteneur); if (bouton) bouton.addEventListener('click', action); };
    brancher('#contrat-resiliation', () => ouvrirResiliation(contrat, etat));
    brancher('#contrat-reconduire', () => ouvrirReconduction(contrat));
    brancher('#contrat-retirer', () => retirer(I18n.t('garanties.fiche_contrat.retirer_question'), I18n.t('garanties.fiche_contrat.retirer'),
      () => Garanties.retirerContrat(contrat.id), I18n.t('garanties.fiche_contrat.retire_toast'), 'contrats'));
  }

  // ===========================================================================================
  // 20. Enregistrement des écrans (App est chargé après les modules : on attend la page)
  // ===========================================================================================

  document.addEventListener('DOMContentLoaded', () => {
    const responsable = ['responsable'];
    App.ecran({
      id: 'garanties', route: /^#\/garanties$/, get titre() { return I18n.t('garanties.liste.titre'); },
      menu: { get libelle() { return I18n.t('garanties.liste.titre'); }, get court() { return I18n.t('garanties.menu.court'); },
        icone: 'document', ordre: 38 },
      profils: responsable,
      tables: ['garanties', 'contrats_prestataires', 'equipements', 'fournisseurs', 'parametres'],
      afficher: afficherListe,
    });
    // « nouvelle », « nouveau » et « …/modifier » sont les formulaires (routes enregistrées avant celles-ci).
    App.ecran({
      id: 'garanties-garantie', route: /^#\/garanties\/garantie\/(?!nouvelle$)(?<id>[^/?]+)$/, parent: 'garanties',
      get titre() { return I18n.t('garanties.fiche_garantie.carte'); }, profils: responsable,
      tables: ['garanties', 'equipements', 'fournisseurs'], afficher: afficherFicheGarantie,
    });
    App.ecran({
      id: 'garanties-contrat', route: /^#\/garanties\/contrat\/(?!nouveau$)(?<id>[^/?]+)$/, parent: 'garanties',
      get titre() { return I18n.t('garanties.fiche_contrat.carte'); }, profils: responsable,
      tables: ['contrats_prestataires', 'equipements', 'fournisseurs'], afficher: afficherFicheContrat,
    });
  });

  // Pour garanties-encarts.js (carte de la fiche équipement) : mêmes badges, même fournisseur, même document.
  Object.assign(Garanties.interne, { badge, blocFournisseur, adresseDocument, blocDocument, lignesDe, filtresDe });
  return { adresseFiche };
})());
