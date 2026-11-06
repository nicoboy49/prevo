'use strict';
// Parc (5/5) — fiche d'un équipement (#/equipement/<id>) : consignation, fiche technique (dont la
// valeur de remplacement), QR code, compteurs et leurs relevés, gammes préventives et leur état,
// encart des suggestions de préventif (responsable, §16.6), contrôles réglementaires et leur statut
// (§15.7), sous-équipements, pièces liées, historiques OT et DI, désactivation et réactivation ; puis
// l'enregistrement des écrans du module auprès d'App (ARCHITECTURE.md §8, §14.2 et §14.6).
// Dernier fichier du module : les écrans des fichiers précédents existent déjà.

Object.assign(Parc, (() => {

  // Règles, outils et écrans des fichiers précédents (parc-regles.js à parc-formulaires.js).
  const { cheminLocalisation, libelleEquipement, afficherListe, afficherFormulaire, afficherEtiquettes } = Parc;
  const { estActif, comparerTextes, parRepere, abreger, badgeCriticite, badgesEquipement,
    listeAdaptative, dernierReleveDe, ouvrirFenetreReleve } = Parc.interne;

  const LIMITE_HISTORIQUE = 20;                       // lignes montrées avant « Voir les autres »
  const STATUTS_OT_FERMES = ['Clôturé techniquement', 'Clôturé administrativement', 'Annulé'];
  // Couleur du badge d'état d'une gamme (mêmes tons que la liste du préventif) ; le libellé vient
  // de Preventif.STATUTS_GAMME, dont l'ordre va du plus urgent au moins urgent.
  const TONS_ETAT_GAMME = { echue: 'ko', ot_ouvert: 'cyan', bientot: 'attention', a_jour: 'ok', incomplete: 'violet', inactive: 'neutre' };

  // ===========================================================================================
  // 5. Écran #/equipement/<id> : fiche
  // ===========================================================================================

  // Adresse d'un document (async : en mode serveur c'est /api/documents/<nom>). null si introuvable.
  async function adresseDocument(nom) {
    if (!nom || !App.adaptateur) return null;
    try {
      return await App.adaptateur.urlDocument(nom);
    } catch (erreur) {
      console.warn('Prévo : document « ' + nom + ' » illisible (' + (erreur && erreur.message) + ').', erreur);
      return null;
    }
  }

  function carteConsignation(equipement) {
    const procedure = String(equipement.consignation || '').trim();
    const habilitation = String(equipement.habilitation_requise || '').trim();
    return UI.html`
      <section class="carte parc-consignation" aria-labelledby="parc-titre-consignation">
        <div class="entete-carte">
          <h2 id="parc-titre-consignation">${UI.icone('alerte')} ${I18n.t('parc.carte_consignation.consignation_avant_intervention')}</h2>
          ${habilitation ? UI.html`<span class="badge attention parc-habilitation">${I18n.t('parc.carte_consignation.habilitation_requise', { habilitation })}</span>` : ''}
        </div>
        <p class="parc-rappel"><b>${I18n.t('parc.carte_consignation.cocher_case_consigne_rien')}</b></p>
        ${procedure
          ? UI.html`<div class="parc-procedure">${procedure}</div>`
          : UI.html`<div class="encadre manque">${I18n.html('parc.carte_consignation.aucune_procedure_consignation_renseignee')}</div>`}
        ${habilitation ? '' : UI.html`<p class="note">${I18n.t('parc.carte_consignation.aucune_habilitation_particuliere_demandee')}</p>`}
      </section>`;
  }

  /** « 12 500,00 € HT » ; vide si la valeur n'est pas renseignée (ou illisible). */
  function valeurRemplacement(equipement) {
    const montant = UI.enNombre(equipement.valeur_remplacement);
    return montant === null ? '' : UI.euro(montant) + ' HT';
  }

  function carteCaracteristiques(equipement, lienDocument) {
    const parent = equipement.parent_id ? Donnees.trouver('equipements', equipement.parent_id) : null;
    const heures = UI.enNombre(equipement.heures_fonct_jour);
    let documentHtml = '';
    if (equipement.document) {
      documentHtml = lienDocument
        ? UI.html`<a href="${lienDocument}" target="_blank" rel="noopener">${UI.icone('document')} ${equipement.document}</a>`
        : UI.html`${I18n.html('parc.carte_caracteristiques.fichier_introuvable', { document: equipement.document })}`;
    }
    return UI.html`
      <article class="carte">
        <h2>${I18n.t('parc.carte_caracteristiques.fiche_technique')}</h2>
        <dl class="valeurs">
          <dt>${I18n.t('parc.carte_caracteristiques.identifiant')}</dt><dd>${equipement.id}</dd>
          <dt>${I18n.t('commun.champ.repere')}</dt><dd>${equipement.repere}</dd>
          <dt>${I18n.t('commun.champ.designation')}</dt><dd>${equipement.designation}</dd>
          <dt>${I18n.t('parc.carte_caracteristiques.localisation')}</dt><dd>${equipement.localisation_id ? cheminLocalisation(equipement.localisation_id) : ''}</dd>
          <dt>${I18n.t('parc.carte_caracteristiques.equipement_parent')}</dt><dd>${parent ? UI.html`<a href="#/equipement/${encodeURIComponent(parent.id)}">${libelleEquipement(parent.id)}</a>` : ''}</dd>
          <dt>${I18n.t('parc.carte_caracteristiques.marque')}</dt><dd>${equipement.marque}</dd>
          <dt>${I18n.t('parc.carte_caracteristiques.modele')}</dt><dd>${equipement.modele}</dd>
          <dt>${I18n.t('parc.carte_caracteristiques.numero_serie')}</dt><dd>${equipement.num_serie}</dd>
          <dt>${I18n.t('parc.carte_caracteristiques.mise_service')}</dt><dd>${UI.dateFr(equipement.date_mes)}</dd>
          <dt>${I18n.t('commun.champ.criticite')}</dt><dd>${equipement.criticite ? badgeCriticite(equipement.criticite) : ''}</dd>
          <dt>${I18n.t('commun.champ.statut')}</dt><dd>${equipement.statut ? UI.badgeValeur('equipements', 'statut', equipement.statut) : ''}</dd>
          <dt>${I18n.t('parc.carte_caracteristiques.heures_jour')}</dt><dd>${heures === null ? '' : UI.heures(heures)}</dd>
          <dt>${I18n.t('parc.carte_caracteristiques.valeur_remplacement')}</dt><dd class="parc-valeur-remplacement">${valeurRemplacement(equipement)}</dd>
          <dt>${I18n.t('parc.carte_caracteristiques.habilitation_requise')}</dt><dd>${equipement.habilitation_requise}</dd>
          <dt>${I18n.t('parc.carte_caracteristiques.document')}</dt><dd>${documentHtml}</dd>
          <dt>${I18n.t('parc.carte_caracteristiques.actif')}</dt><dd>${estActif(equipement) ? I18n.t('parc.carte_caracteristiques.oui') : I18n.t('parc.carte_caracteristiques.non_equipement_desactive')}</dd>
        </dl>
      </article>`;
  }

  function carteQr(equipement) {
    const texte = App.urlFicheEquipement(equipement.id);
    let dessin;
    try {
      dessin = UI.qrSvg(texte, 200);
    } catch (erreur) {
      console.warn('Prévo : QR code impossible (' + (erreur && erreur.message) + ').', erreur);
      dessin = UI.html`<p class="muted">${I18n.t('parc.carte_qr.qr_code_indisponible')}</p>`;
    }
    const consigne = App.mode === 'serveur'
      ? I18n.t('parc.carte_qr.scannez_appareil_photo_telephone')
      : I18n.t('parc.carte_qr.code_lisible_camera_poste', { texte });
    return UI.html`
      <article class="carte parc-qr-carte">
        <h2>${I18n.t('parc.carte_qr.qr_code_equipement')}</h2>
        <div class="qr">${dessin}<span class="repere">${equipement.repere || equipement.id}</span></div>
        <p class="note">${consigne}</p>
      </article>`;
  }

  // Carte « Compteurs » : dernier relevé de chaque compteur (valeur, unité, date, auteur) et, pour
  // le technicien et le responsable, un bouton « Saisir un relevé » (fenêtre de parc-formulaires.js).
  function carteCompteurs(equipement, peutSaisir) {
    const compteurs = Donnees.lignes('compteurs').filter((c) => c.equipement_id === equipement.id);
    const releves = Donnees.lignes('releves');
    const lignes = compteurs.map((compteur) => {
      const dernier = dernierReleveDe(releves, compteur.id);
      const libelle = compteur.libelle || compteur.id;
      return UI.html`<li data-compteur="${compteur.id}">
        <div class="parc-compteur-texte">
          <b>${libelle}</b>
          ${dernier
            ? UI.html`<span class="parc-dernier-releve">${phraseDernierReleve(dernier, compteur)}</span>`
            : UI.html`<span class="muted">${I18n.t('parc.carte_compteurs.aucun_releve')}</span>`}
        </div>
        ${peutSaisir ? UI.html`<button type="button" class="btn btn-secondaire parc-saisir-releve" data-compteur="${compteur.id}"
            aria-label="${I18n.t('parc.carte_compteurs.saisir_releve', { libelle })}">${UI.icone('ajouter')}${I18n.t('parc.carte_compteurs.saisir_releve_2')}</button>` : ''}
      </li>`;
    });
    return UI.html`
      <article class="carte parc-carte-compteurs">
        <h2>${I18n.t('parc.carte_compteurs.compteurs')}</h2>
        ${lignes.length ? UI.html`<ul class="parc-compteurs">${lignes}</ul>` : UI.html`<p class="muted">${I18n.t('parc.carte_compteurs.aucun_compteur_equipement')}</p>`}
      </article>`;
  }

  // Raison de l'état d'une gamme ; quand un OT est ouvert, son numéro (en tête de la raison)
  // devient un lien vers l'OT — sauf pour le demandeur, qui n'a pas accès aux OT.
  function raisonGamme(etat, avecLiens) {
    const id = etat.otOuvertId;
    if (!avecLiens || !id || !etat.raison.startsWith(id)) return UI.html`<span class="parc-gamme-raison">${etat.raison}</span>`;
    return UI.html`<span class="parc-gamme-raison"><a class="parc-lien-ot" href="#/ot/${encodeURIComponent(id)}">${id}</a>${etat.raison.slice(id.length)}</span>`;
  }

  // « Dernier relevé : 1 250 h le 12/10/2026 (Marie) » : une phrase complète par forme (unité ou non, utilisateur ou non).
  function phraseDernierReleve(dernier, compteur) {
    const valeur = UI.nombreFr(dernier.valeur);
    const valeurs = { valeur, unite: compteur.unite, date: UI.dateFr(dernier.date), utilisateur: dernier.utilisateur };
    if (compteur.unite) {
      return dernier.utilisateur ? I18n.html('parc.carte_compteurs.dernier_releve_unite_utilisateur', valeurs)
        : I18n.html('parc.carte_compteurs.dernier_releve_unite', valeurs);
    }
    return dernier.utilisateur ? I18n.html('parc.carte_compteurs.dernier_releve_utilisateur', valeurs)
      : I18n.html('parc.carte_compteurs.dernier_releve', valeurs);
  }

  // Carte « Préventif » : gammes de l'équipement, de la plus urgente à la moins urgente, avec leur
  // état RG5 (Preventif.etatGamme) : badge, raison, échéance, liens vers la gamme et l'OT ouvert.
  function cartePreventif(equipement, avecLiens) {
    const jour = Donnees.aujourdhui();
    const rangs = Object.keys(Preventif.STATUTS_GAMME);
    const gammes = Donnees.lignes('gammes').filter((g) => g.equipement_id === equipement.id)
      .map((gamme) => ({ gamme, etat: Preventif.etatGamme(gamme, jour) }))
      .sort((a, b) => rangs.indexOf(a.etat.statut) - rangs.indexOf(b.etat.statut)
        || comparerTextes(a.gamme.libelle, b.gamme.libelle));
    const lignes = gammes.map(({ gamme, etat }) => {
      const libelle = gamme.libelle || gamme.id;
      const estimee = gamme.declencheur === 'compteur';
      // L'échéance n'est ajoutée que si la raison ne la dit pas déjà (gamme « date » : « échéance le … »).
      const echeance = etat.echeance && !etat.raison.includes(UI.dateFr(etat.echeance)) ? etat.echeance : '';
      return UI.html`<li data-gamme="${gamme.id}" data-statut="${etat.statut}">
        <div class="parc-gamme-tete">
          ${avecLiens ? UI.html`<a class="parc-lien-gamme" href="#/preventif/gamme/${encodeURIComponent(gamme.id)}">${libelle}</a>` : UI.html`<b>${libelle}</b>`}
          ${UI.badgeStatut(Preventif.STATUTS_GAMME[etat.statut] || etat.statut, TONS_ETAT_GAMME[etat.statut])}
        </div>
        <div class="parc-gamme-detail">${raisonGamme(etat, avecLiens)}
          ${echeance ? UI.html`<span>${I18n.html('parc.carte_preventif.echeance_echeance', { echeance: UI.dateFr(echeance) })}${estimee ? ' ' + I18n.t('parc.carte_preventif.estimee') : ''}</span>` : ''}</div>
      </li>`;
    });
    return UI.html`
      <article class="carte parc-preventif">
        <h2>${I18n.html('parc.carte_preventif.preventif_nb_lignes', { nbLignes: lignes.length })}</h2>
        ${lignes.length ? UI.html`<ul class="parc-gammes">${lignes}</ul>` : UI.html`<p class="muted">${I18n.t('parc.carte_preventif.aucune_gamme_preventive_equipement')}</p>`}
      </article>`;
  }

  // Carte « Contrôles réglementaires » (ARCHITECTURE.md §15.7) : technicien et responsable. Chaque
  // contrôle de l'équipement avec son statut RG9 (Controles.etat : statut puis statuts secondaires),
  // la raison, un lien vers sa fiche ; « Ajouter un contrôle » pour le responsable.
  function carteControles(equipement, responsable) {
    const jour = Donnees.aujourdhui();
    const controles = Donnees.lignes('controles_reglementaires').filter((c) => c.equipement_id === equipement.id)
      .map((controle) => ({ controle, etat: Controles.etat(controle, jour) }))
      .sort((a, b) => Controles.STATUTS.indexOf(a.etat.statut) - Controles.STATUTS.indexOf(b.etat.statut)
        || comparerTextes(a.etat.prochaine, b.etat.prochaine));
    const lignes = controles.map(({ controle, etat }) => UI.html`<li>
        <div class="parc-gamme-tete">
          <a href="#/controles/${encodeURIComponent(controle.id)}">${controle.nature || controle.id}</a>
          <span class="controles-statuts" data-controle="${controle.id}">${UI.badgeStatut(etat.statut, '', Controles.libelleStatut(etat.statut))}${etat.secondaires.map((statut) => UI.html` ${UI.badgeStatut(statut, '', Controles.libelleStatut(statut))}`)}</span>
        </div>
        <div class="parc-gamme-detail"><span class="parc-gamme-raison">${etat.raison}</span>${controle.organisme ? UI.html`<span>${controle.organisme}</span>` : ''}</div>
      </li>`);
    return UI.html`
      <article class="carte parc-controles">
        <div class="entete-carte"><h2>${I18n.html('parc.carte_controles.controles_reglementaires', { nbLignes: lignes.length })}</h2>
          ${responsable ? UI.html`<a class="btn btn-secondaire" id="parc-ajouter-controle"
            href="#/controles/nouveau?equipement=${encodeURIComponent(equipement.id)}">${UI.icone('ajouter')}${I18n.t('parc.carte_controles.ajouter_controle')}</a>` : ''}</div>
        ${lignes.length ? UI.html`<ul class="parc-gammes">${lignes}</ul>` : UI.html`<p class="muted">${I18n.t('parc.carte_controles.aucun_controle_reglementaire_equipement')}</p>`}
      </article>`;
  }

  function carteSousEquipements(equipement) {
    const enfants = Donnees.lignes('equipements').filter((e) => e.parent_id === equipement.id).sort(parRepere);
    if (!enfants.length) return '';
    return UI.html`
      <article class="carte">
        <h2>${I18n.html('parc.carte_sous_equipements.sous_equipements', { nbEnfants: enfants.length })}</h2>
        <ul class="liste-cartes">${enfants.map((enfant) => UI.html`<li><a href="#/equipement/${encodeURIComponent(enfant.id)}">
          <div class="carte-tete"><b>${enfant.repere || enfant.id}</b>${badgesEquipement(enfant)}</div>
          <div class="carte-titre">${enfant.designation}</div></a></li>`)}</ul>
      </article>`;
  }

  function carteArticles(equipement) {
    const liens = Donnees.lignes('article_equipement').filter((l) => l.equipement_id === equipement.id);
    const lignes = liens.map((lien) => {
      const article = Donnees.trouver('articles', lien.article_id);
      return {
        id: lien.id,
        reference: article ? article.reference : lien.article_id,
        designation: article ? article.designation : I18n.t('parc.carte_articles.article_inconnu'),
        quantite: lien.quantite,
        unite: article ? article.unite : '',
        emplacement: article ? article.emplacement : '',
        stock: article ? Donnees.stockArticle(article.id) : null,
        stockSecurite: article ? UI.enNombre(article.stock_securite) : null,
      };
    }).sort((a, b) => comparerTextes(a.reference, b.reference));

    function etatStock(ligne) {
      if (ligne.stock === null) return '';
      if (ligne.stock <= 0) return UI.html` <span class="badge ko">${I18n.t('parc.carte_articles.rupture')}</span>`;
      if (ligne.stockSecurite !== null && ligne.stock <= ligne.stockSecurite) return UI.html` <span class="badge attention">${I18n.t('parc.carte_articles.stock_bas')}</span>`;
      return '';
    }
    const texteStock = (ligne) => (ligne.stock === null ? '–' : UI.nombreFr(ligne.stock) + (ligne.unite ? ' ' + ligne.unite : ''));
    const liste = listeAdaptative({
      lignes,
      vide: I18n.t('parc.carte_articles.aucune_piece_liee_equipement'),
      libelle: I18n.t('parc.carte_articles.articles_lies_equipement'),
      colonnes: [
        { cle: 'reference', libelle: I18n.t('commun.champ.reference') },
        { cle: 'designation', libelle: I18n.t('commun.champ.designation') },
        { cle: 'quantite', libelle: I18n.t('commun.champ.quantite'), type: 'nombre', rendu: (l) => UI.nombreFr(l.quantite) },
        { cle: 'stock', libelle: I18n.t('parc.carte_articles.stock'), type: 'nombre', rendu: (l) => UI.html`${texteStock(l)}${etatStock(l)}` },
        { cle: 'emplacement', libelle: I18n.t('parc.carte_articles.emplacement') },
      ],
      carte: (l) => UI.html`<div class="carte-ligne">
        <div class="carte-tete"><b>${l.reference}</b>${etatStock(l)}</div>
        <div class="carte-titre">${l.designation}</div>
        <div class="carte-meta">${I18n.html('parc.carte_articles.quantite_stock', { quantite: UI.nombreFr(l.quantite), texteStock: texteStock(l) })}
          ${l.emplacement ? UI.html`<span>${I18n.t('parc.carte_articles.emplacement_emplacement', { emplacement: l.emplacement })}</span>` : ''}</div></div>`,
    });
    const carte = UI.element(UI.html`<article class="carte"><h2>${I18n.html('parc.carte_articles.pieces_liees', { nbLignes: lignes.length })}</h2><div class="parc-liste"></div></article>`);
    UI.$('.parc-liste', carte).appendChild(liste);
    return carte;
  }

  // Carte « historique » : les plus récentes d'abord, « Voir les autres » au-delà de LIMITE_HISTORIQUE.
  function carteHistorique(titre, lignes, construire) {
    const carte = UI.element(UI.html`<article class="carte">
      <div class="entete-carte"><h2>${titre} <span class="badge">${lignes.length}</span></h2></div>
      <div class="parc-liste"></div>
      <div class="actions" hidden><button type="button" class="btn btn-secondaire parc-voir-tout"></button></div>
    </article>`);
    const zone = UI.$('.parc-liste', carte);
    const zoneBouton = UI.$('.actions', carte);
    const bouton = UI.$('.parc-voir-tout', carte);
    let toutVoir = false;
    function dessiner() {
      UI.remplir(zone, construire(toutVoir ? lignes : lignes.slice(0, LIMITE_HISTORIQUE)));
      zoneBouton.hidden = lignes.length <= LIMITE_HISTORIQUE;
      bouton.textContent = toutVoir ? I18n.t('parc.carte_historique.reduire_liste') : I18n.t('parc.carte_historique.voir_autres', { n: (lignes.length - LIMITE_HISTORIQUE) });
    }
    bouton.addEventListener('click', () => { toutVoir = !toutVoir; dessiner(); });
    dessiner();
    return carte;
  }

  function carteHistoriqueOt(equipement) {
    const ordres = Donnees.lignes('ordres_travail').filter((o) => o.equipement_id === equipement.id)
      .sort((a, b) => comparerTextes(b.date_creation, a.date_creation) || comparerTextes(b.id, a.id));
    return carteHistorique(I18n.t('parc.carte_historique_ot.historique_ordres_travail'), ordres, (lignes) => listeAdaptative({
      lignes,
      vide: I18n.t('parc.carte_historique_ot.aucun_ordre_travail_equipement'),
      libelle: I18n.t('parc.carte_historique_ot.ordres_travail_equipement'),
      lien: (o) => '#/ot/' + encodeURIComponent(o.id),
      colonnes: [
        { cle: 'id', libelle: 'N°', rendu: (o) => UI.html`<a href="#/ot/${encodeURIComponent(o.id)}">${o.id}</a>` },
        { cle: 'date_creation', libelle: I18n.t('commun.champ.date'), rendu: (o) => UI.dateFr(o.date_creation), classe: 'sans-coupure' },
        { cle: 'type', libelle: I18n.t('parc.carte_historique_ot.type'), table: 'ordres_travail' },
        { cle: 'priorite', libelle: I18n.t('commun.champ.priorite'), rendu: (o) => UI.badgePriorite(o.priorite) },
        { cle: 'statut', libelle: I18n.t('commun.champ.statut'), rendu: (o) => UI.badgeValeur('ordres_travail', 'statut', o.statut) },
        { cle: 'titre', libelle: I18n.t('parc.carte_historique_ot.titre') },
      ],
      carte: (o) => UI.html`<a href="#/ot/${encodeURIComponent(o.id)}">
        <div class="carte-tete"><b>${o.id}</b>${UI.badgePriorite(o.priorite)}${UI.badgeValeur('ordres_travail', 'statut', o.statut)}</div>
        <div class="carte-titre">${o.titre}</div>
        <div class="carte-meta"><span>${UI.dateFr(o.date_creation)}</span><span>${Schema.libelleValeur('ordres_travail', 'type', o.type)}</span></div></a>`,
    }));
  }

  function carteHistoriqueDi(equipement) {
    const demandes = Donnees.lignes('demandes').filter((d) => d.equipement_id === equipement.id)
      .sort((a, b) => comparerTextes(b.date_heure, a.date_heure) || comparerTextes(b.id, a.id));
    return carteHistorique(I18n.t('parc.carte_historique_di.historique_demandes_intervention'), demandes, (lignes) => listeAdaptative({
      lignes,
      vide: I18n.t('parc.carte_historique_di.aucune_demande_intervention_equipement'),
      libelle: I18n.t('parc.carte_historique_di.demandes_intervention_equipement'),
      lien: (d) => '#/di/' + encodeURIComponent(d.id),
      colonnes: [
        { cle: 'id', libelle: 'N°', rendu: (d) => UI.html`<a href="#/di/${encodeURIComponent(d.id)}">${d.id}</a>` },
        { cle: 'date_heure', libelle: I18n.t('commun.champ.date'), rendu: (d) => UI.dateFr(d.date_heure), classe: 'sans-coupure' },
        { cle: 'symptome', libelle: I18n.t('commun.champ.symptome'), rendu: (d) => abreger(d.symptome, 110) },
        { cle: 'statut', libelle: I18n.t('commun.champ.statut'), rendu: (d) => UI.badgeValeur('demandes', 'statut', d.statut) },
      ],
      carte: (d) => UI.html`<a href="#/di/${encodeURIComponent(d.id)}">
        <div class="carte-tete"><b>${d.id}</b>${UI.badgeValeur('demandes', 'statut', d.statut)}</div>
        <div class="carte-titre">${abreger(d.symptome, 110)}</div>
        <div class="carte-meta"><span>${UI.dateFr(d.date_heure)}</span></div></a>`,
    }));
  }

  // Désactive ou réactive un équipement (jamais de suppression : l'historique est conservé).
  async function changerActivite(equipement, activer) {
    if (!activer) {
      const ouverts = Donnees.lignes('ordres_travail').filter((o) => o.equipement_id === equipement.id && !STATUTS_OT_FERMES.includes(o.statut)).length;
      const sousEquipements = Donnees.lignes('equipements').filter((e) => e.parent_id === equipement.id && estActif(e)).length;
      let message = I18n.t('parc.changer_activite.desactiver_sera_plus_propose', { libelleEquipement: libelleEquipement(equipement.id) });
      if (ouverts) message += ' ' + I18n.t('parc.changer_activite.attention_ordres_travail_ouverts', { n: ouverts });
      if (sousEquipements) message += ' ' + I18n.t('parc.changer_activite.sous_equipement_actif_sont', { n: sousEquipements });
      if (!await UI.confirmer(message, { titre: I18n.t('parc.changer_activite.desactiver_equipement'), oui: I18n.t('commun.bouton.desactiver'), danger: true })) return;
    } else if (!await UI.confirmer(I18n.t('parc.changer_activite.reactiver_reapparaitra_parc', { libelleEquipement: libelleEquipement(equipement.id) }), { titre: I18n.t('parc.changer_activite.reactiver_equipement'), oui: I18n.t('parc.changer_activite.reactiver') })) {
      return;
    }
    try {
      await Donnees.modifier('equipements', (lignes) => {
        const ligne = lignes.find((l) => l.id === equipement.id);
        if (!ligne) throw new Donnees.ErreurValidation(I18n.t('parc.changer_activite.equipement_existe_plus'));
        if (activer) {
          const double = lignes.find((l) => l.id !== ligne.id && estActif(l) && UI.normaliserRecherche(l.repere) === UI.normaliserRecherche(ligne.repere));
          if (double) {
            throw new Donnees.ErreurValidation(I18n.t('parc.changer_activite.reactivation_impossible_repere_maintenant', { repere: ligne.repere, libelleEquipement: libelleEquipement(double.id) }));
          }
        }
        ligne.actif = activer ? '1' : '0';
      }, { action: activer ? 'réactivation' : 'désactivation' });
      UI.toast(activer ? I18n.t('parc.changer_activite.equipement_reactive') : I18n.t('parc.changer_activite.equipement_desactive'), 'succes');
      await App.reafficher();
    } catch (erreur) {
      App.signalerErreur(erreur, activer ? 'réactivation' : 'désactivation');
    }
  }

  async function afficherFiche(conteneur, parametres) {
    const equipement = Donnees.trouver('equipements', parametres.id);
    if (!equipement) {
      App.definirTitre(I18n.t('parc.fiche.equipement_introuvable'));
      UI.remplir(conteneur, UI.html`<div class="parc">
        <div class="entete-page"><div>
          <div class="fil"><a href="#/parc">${I18n.t('parc.fiche.parc')}</a></div>
          <h1>${I18n.t('parc.fiche.equipement_introuvable')}</h1>
        </div></div>
        ${UI.vide(I18n.t('parc.fiche.aucun_equipement_porte_identifiant', { parametresId: parametres.id }),
          I18n.t('parc.fiche.qr_code_peut_etre'), 'recherche')}
        <p><a class="btn btn-secondaire" href="#/parc">${I18n.t('parc.fiche.retour_parc')}</a></p></div>`);
      return;
    }
    App.definirTitre(equipement.repere || equipement.id);
    const responsable = App.estResponsable();
    // Mode Solo (D132, §22.11) : « Créer un OT » en premier, avant « Signaler un problème ».
    const solo = App.modeSolo();
    // Le demandeur consulte : pas de saisie de relevé, ni de lien vers les gammes et les OT
    // (écrans qui lui sont fermés), ni de carte Préventif (D27 : il ne voit pas le préventif).
    const intervenant = App.estTechnicien() || responsable;
    const adresse = await adresseDocument(equipement.document);
    const idUrl = encodeURIComponent(equipement.id);
    const actif = estActif(equipement);
    const sousEquipements = carteSousEquipements(equipement);

    UI.remplir(conteneur, UI.html`
      <div class="parc">
        <div class="entete-page">
          <div>
            <div class="fil"><a href="#/parc">${I18n.t('parc.fiche.parc')}</a>${equipement.localisation_id ? UI.html` <span aria-hidden="true">›</span> <span>${cheminLocalisation(equipement.localisation_id)}</span>` : ''}</div>
            <h1>${libelleEquipement(equipement.id)}</h1>
            <p class="parc-badges-fiche">${badgeCriticite(equipement.criticite)} ${equipement.statut ? UI.badgeValeur('equipements', 'statut', equipement.statut) : ''}
              ${actif ? '' : UI.html`<span class="badge neutre barre">${I18n.t('parc.fiche.inactif')}</span>`}</p>
            <p><a id="lien-wiki-equipement" href="#/wiki/${idUrl}">${UI.icone('wiki')}${I18n.t('parc.fiche.wiki_equipement')}</a></p>
          </div>
        </div>

        <div class="parc-actions">
          ${solo ? UI.html`<a class="btn btn-primaire btn-gros parc-creer-ot" id="parc-creer-ot" href="#/ot/nouveau?equipement=${idUrl}">${UI.icone('ordres')}
            <span>${I18n.html('parc.fiche.creer_ot_intervenez_meme')}</span></a>` : ''}
          <a class="btn ${solo ? 'btn-secondaire' : 'btn-primaire'} btn-gros parc-signaler" href="#/di/nouvelle?equipement=${idUrl}">${UI.icone('alerte')}
            <span>${I18n.html('parc.fiche.signaler_probleme_panne_fuite')}</span></a>
          ${responsable ? UI.html`<div class="actions">
            ${solo ? '' : UI.html`<a class="btn btn-secondaire" href="#/ot/nouveau?equipement=${idUrl}">${UI.icone('ordres')}${I18n.t('parc.fiche.creer_ot')}</a>`}
            <a class="btn btn-secondaire" href="#/equipement/${idUrl}/modifier">${UI.icone('cle')}${I18n.t('commun.bouton.modifier')}</a>
            <button type="button" class="btn ${actif ? 'btn-danger' : 'btn-secondaire'}" id="parc-activite">${actif ? I18n.t('commun.bouton.desactiver') : I18n.t('parc.changer_activite.reactiver')}</button>
          </div>` : ''}
        </div>

        ${actif ? '' : UI.html`<div class="alertes"><div class="alerte attention" role="status">${UI.icone('alerte')}
          <div class="alerte-texte">${I18n.html('parc.fiche.equipement_desactive_plus_propose')}</div></div></div>`}

        ${carteConsignation(equipement)}

        <div class="grille">
          <div class="c8">${carteCaracteristiques(equipement, adresse)}</div>
          <div class="c4">${carteQr(equipement)}</div>
        </div>
        <div class="grille">
          ${App.estDemandeur()
            ? UI.html`<div class="c12">${carteCompteurs(equipement, intervenant)}</div>`
            : UI.html`<div class="c6">${carteCompteurs(equipement, intervenant)}</div>
          <div class="c6">${cartePreventif(equipement, intervenant)}</div>`}
        </div>
        ${intervenant ? carteControles(equipement, responsable) : ''}
        ${sousEquipements}
        <div class="parc-complements"></div>
      </div>`);

    // Encart « Suggestions de préventif » (responsable, suggestions ouvertes seulement ; §16.6), sous la
    // carte Préventif. Suggestions est chargé après ce fichier : appelé au moment de l'affichage.
    const encartSuggestions = Suggestions.encartEquipement(equipement.id);
    if (encartSuggestions) UI.$('.parc-preventif', conteneur).closest('.grille').after(encartSuggestions);

    const zone = UI.$('.parc-complements', conteneur);
    zone.appendChild(carteArticles(equipement));
    zone.appendChild(carteHistoriqueOt(equipement));
    zone.appendChild(carteHistoriqueDi(equipement));

    const boutonActivite = UI.$('#parc-activite', conteneur);
    if (boutonActivite) boutonActivite.addEventListener('click', () => changerActivite(equipement, !actif));
    UI.$$('.parc-saisir-releve', conteneur).forEach((bouton) => {
      bouton.addEventListener('click', async () => {
        if (await ouvrirFenetreReleve(bouton.dataset.compteur)) await App.reafficher();
      });
    });
  }

  // ===========================================================================================
  // 7. Enregistrement des écrans (App est chargé après les modules : on attend la page)
  // ===========================================================================================

  document.addEventListener('DOMContentLoaded', () => {
    const tous = ['demandeur', 'technicien', 'responsable'];
    App.ecran({
      id: 'parc', route: /^#\/parc$/, get titre() { return I18n.t('parc.fiche.parc'); },
      menu: { get libelle() { return I18n.t('parc.fiche.parc'); }, icone: 'parc', ordre: 40 },
      profils: tous,
      tables: ['equipements', 'localisations'],
      afficher: afficherListe,
    });
    // #/parc/etiquettes : étiquettes QR par lot (parc-etiquettes.js, ARCHITECTURE.md §15.6),
    // responsable seul ; ?localisation=, ?criticite=, ?ids=EQ-…,EQ-… sont lus par l'écran.
    App.ecran({
      id: 'parc-etiquettes', route: /^#\/parc\/etiquettes$/, get titre() { return I18n.t('parc.titre.etiquettes_qr'); }, parent: 'parc',
      profils: ['responsable'],
      tables: ['equipements', 'localisations', 'parametres'],
      afficher: afficherEtiquettes,
    });
    // Les routes les plus précises d'abord : « nouveau » ne doit pas être pris pour un identifiant
    // (la route fiche l'exclut en plus, ARCHITECTURE.md §14.2).
    App.ecran({
      id: 'equipement-nouveau', route: /^#\/equipement\/nouveau$/, get titre() { return I18n.t('parc.titre.nouvel_equipement'); }, parent: 'parc',
      profils: ['responsable'],
      tables: [],
      afficher: afficherFormulaire,
    });
    App.ecran({
      id: 'equipement-modifier', route: /^#\/equipement\/(?<id>[^/?]+)\/modifier$/, get titre() { return I18n.t('parc.titre.modifier_equipement'); }, parent: 'parc',
      profils: ['responsable'],
      tables: [],
      afficher: afficherFormulaire,
    });
    App.ecran({
      id: 'equipement', route: /^#\/equipement\/(?!nouveau$)(?<id>[^/?]+)$/, get titre() { return I18n.t('commun.champ.equipement'); }, parent: 'parc',
      profils: tous,
      tables: ['equipements', 'localisations', 'ordres_travail', 'demandes', 'compteurs', 'releves',
        'gammes', 'articles', 'article_equipement', 'mouvements_stock', 'controles_reglementaires'],
      afficher: afficherFiche,
    });
  });

  return {
    afficherFiche,
  };
})());
