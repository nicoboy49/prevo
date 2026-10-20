'use strict';
// Parc (4/4) — fiche d'un équipement (#/equipement/<id>) : consignation, fiche technique, QR code,
// compteurs, sous-équipements, pièces liées, historiques OT et DI, désactivation et réactivation ;
// puis l'enregistrement des écrans du module auprès d'App (ARCHITECTURE.md §8 et §14.2).
// Dernier fichier du module : les écrans des fichiers précédents existent déjà.

Object.assign(Parc, (() => {

  // Règles, outils et écrans des fichiers précédents (parc-regles.js à parc-formulaires.js).
  const { cheminLocalisation, libelleEquipement, afficherListe, afficherFormulaire } = Parc;
  const { estActif, comparerTextes, parRepere, abreger, badgeCriticite, badgesEquipement,
    listeAdaptative } = Parc.interne;

  const LIMITE_HISTORIQUE = 20;                       // lignes montrées avant « Voir les autres »
  const STATUTS_OT_FERMES = ['Clôturé techniquement', 'Clôturé administrativement', 'Annulé'];

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
          <h2 id="parc-titre-consignation">${UI.icone('alerte')} Consignation avant intervention</h2>
          ${habilitation ? UI.html`<span class="badge attention parc-habilitation">Habilitation requise : ${habilitation}</span>` : ''}
        </div>
        <p class="parc-rappel"><b>Cocher une case ne consigne rien : appliquez la procédure.</b></p>
        ${procedure
          ? UI.html`<div class="parc-procedure">${procedure}</div>`
          : UI.html`<div class="encadre manque"><b>Aucune procédure de consignation n'est renseignée pour cet équipement.</b>
              Avant d'intervenir, demandez-la au responsable.</div>`}
        ${habilitation ? '' : UI.html`<p class="note">Aucune habilitation particulière n'est demandée pour cet équipement.</p>`}
      </section>`;
  }

  function carteCaracteristiques(equipement, lienDocument) {
    const parent = equipement.parent_id ? Donnees.trouver('equipements', equipement.parent_id) : null;
    const heures = UI.enNombre(equipement.heures_fonct_jour);
    let documentHtml = '';
    if (equipement.document) {
      documentHtml = lienDocument
        ? UI.html`<a href="${lienDocument}" target="_blank" rel="noopener">${UI.icone('document')} ${equipement.document}</a>`
        : UI.html`${equipement.document} <span class="badge attention">fichier introuvable</span>`;
    }
    return UI.html`
      <article class="carte">
        <h2>Fiche technique</h2>
        <dl class="valeurs">
          <dt>Identifiant</dt><dd>${equipement.id}</dd>
          <dt>Repère</dt><dd>${equipement.repere}</dd>
          <dt>Désignation</dt><dd>${equipement.designation}</dd>
          <dt>Localisation</dt><dd>${equipement.localisation_id ? cheminLocalisation(equipement.localisation_id) : ''}</dd>
          <dt>Équipement parent</dt><dd>${parent ? UI.html`<a href="#/equipement/${encodeURIComponent(parent.id)}">${libelleEquipement(parent.id)}</a>` : ''}</dd>
          <dt>Marque</dt><dd>${equipement.marque}</dd>
          <dt>Modèle</dt><dd>${equipement.modele}</dd>
          <dt>Numéro de série</dt><dd>${equipement.num_serie}</dd>
          <dt>Mise en service</dt><dd>${UI.dateFr(equipement.date_mes)}</dd>
          <dt>Criticité</dt><dd>${equipement.criticite ? badgeCriticite(equipement.criticite) : ''}</dd>
          <dt>Statut</dt><dd>${equipement.statut ? UI.badgeStatut(equipement.statut) : ''}</dd>
          <dt>Heures par jour</dt><dd>${heures === null ? '' : UI.heures(heures)}</dd>
          <dt>Habilitation requise</dt><dd>${equipement.habilitation_requise}</dd>
          <dt>Document</dt><dd>${documentHtml}</dd>
          <dt>Actif</dt><dd>${estActif(equipement) ? 'Oui' : 'Non — équipement désactivé'}</dd>
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
      dessin = UI.html`<p class="muted">QR code indisponible.</p>`;
    }
    const consigne = App.mode === 'serveur'
      ? 'Scannez avec l\'appareil photo du téléphone : la fiche de cet équipement s\'ouvre.'
      : 'Code ' + texte + ', lisible par la caméra du poste.';
    return UI.html`
      <article class="carte parc-qr-carte">
        <h2>QR code de l'équipement</h2>
        <div class="qr">${dessin}<span class="repere">${equipement.repere || equipement.id}</span></div>
        <p class="note">${consigne}</p>
      </article>`;
  }

  function carteCompteurs(equipement) {
    const compteurs = Donnees.lignes('compteurs').filter((c) => c.equipement_id === equipement.id);
    const lignes = compteurs.map((compteur) => {
      const releves = Donnees.lignes('releves').filter((r) => r.compteur_id === compteur.id)
        .sort((a, b) => comparerTextes(b.date, a.date) || comparerTextes(b.id, a.id));
      const dernier = releves[0];
      return UI.html`<li>
        <b>${compteur.libelle || compteur.id}</b>
        ${dernier
          ? UI.html`<span>Dernier relevé : <b class="fort">${UI.nombreFr(dernier.valeur)}${compteur.unite ? ' ' + compteur.unite : ''}</b>
              le ${UI.dateFr(dernier.date)}${dernier.utilisateur ? ' (' + dernier.utilisateur + ')' : ''}</span>`
          : UI.html`<span class="muted">Aucun relevé.</span>`}
      </li>`;
    });
    return UI.html`
      <article class="carte">
        <h2>Compteurs</h2>
        ${lignes.length ? UI.html`<ul class="parc-compteurs">${lignes}</ul>` : UI.html`<p class="muted">Aucun compteur sur cet équipement.</p>`}
      </article>`;
  }

  function carteSousEquipements(equipement) {
    const enfants = Donnees.lignes('equipements').filter((e) => e.parent_id === equipement.id).sort(parRepere);
    if (!enfants.length) return '';
    return UI.html`
      <article class="carte">
        <h2>Sous-équipements <span class="badge">${enfants.length}</span></h2>
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
        designation: article ? article.designation : '(article inconnu)',
        quantite: lien.quantite,
        unite: article ? article.unite : '',
        emplacement: article ? article.emplacement : '',
        stock: article ? Donnees.stockArticle(article.id) : null,
        stockSecurite: article ? UI.enNombre(article.stock_securite) : null,
      };
    }).sort((a, b) => comparerTextes(a.reference, b.reference));

    function etatStock(ligne) {
      if (ligne.stock === null) return '';
      if (ligne.stock <= 0) return UI.html` <span class="badge ko">Rupture</span>`;
      if (ligne.stockSecurite !== null && ligne.stock <= ligne.stockSecurite) return UI.html` <span class="badge attention">Stock bas</span>`;
      return '';
    }
    const texteStock = (ligne) => (ligne.stock === null ? '–' : UI.nombreFr(ligne.stock) + (ligne.unite ? ' ' + ligne.unite : ''));
    const liste = listeAdaptative({
      lignes,
      vide: 'Aucune pièce n\'est liée à cet équipement.',
      libelle: 'Articles liés à l\'équipement',
      colonnes: [
        { cle: 'reference', libelle: 'Référence' },
        { cle: 'designation', libelle: 'Désignation' },
        { cle: 'quantite', libelle: 'Quantité', type: 'nombre', rendu: (l) => UI.nombreFr(l.quantite) },
        { cle: 'stock', libelle: 'En stock', type: 'nombre', rendu: (l) => UI.html`${texteStock(l)}${etatStock(l)}` },
        { cle: 'emplacement', libelle: 'Emplacement' },
      ],
      carte: (l) => UI.html`<div class="carte-ligne">
        <div class="carte-tete"><b>${l.reference}</b>${etatStock(l)}</div>
        <div class="carte-titre">${l.designation}</div>
        <div class="carte-meta"><span>Quantité : ${UI.nombreFr(l.quantite)}</span><span>En stock : ${texteStock(l)}</span>
          ${l.emplacement ? UI.html`<span>Emplacement : ${l.emplacement}</span>` : ''}</div></div>`,
    });
    const carte = UI.element(UI.html`<article class="carte"><h2>Pièces liées <span class="badge">${lignes.length}</span></h2><div class="parc-liste"></div></article>`);
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
      bouton.textContent = toutVoir ? 'Réduire la liste' : 'Voir les ' + (lignes.length - LIMITE_HISTORIQUE) + ' autres';
    }
    bouton.addEventListener('click', () => { toutVoir = !toutVoir; dessiner(); });
    dessiner();
    return carte;
  }

  function carteHistoriqueOt(equipement) {
    const ordres = Donnees.lignes('ordres_travail').filter((o) => o.equipement_id === equipement.id)
      .sort((a, b) => comparerTextes(b.date_creation, a.date_creation) || comparerTextes(b.id, a.id));
    return carteHistorique('Historique des ordres de travail', ordres, (lignes) => listeAdaptative({
      lignes,
      vide: 'Aucun ordre de travail sur cet équipement.',
      libelle: 'Ordres de travail de l\'équipement',
      lien: (o) => '#/ot/' + encodeURIComponent(o.id),
      colonnes: [
        { cle: 'id', libelle: 'N°', rendu: (o) => UI.html`<a href="#/ot/${encodeURIComponent(o.id)}">${o.id}</a>` },
        { cle: 'date_creation', libelle: 'Date', rendu: (o) => UI.dateFr(o.date_creation), classe: 'sans-coupure' },
        { cle: 'type', libelle: 'Type' },
        { cle: 'priorite', libelle: 'Priorité', rendu: (o) => UI.badgePriorite(o.priorite) },
        { cle: 'statut', libelle: 'Statut', rendu: (o) => UI.badgeStatut(o.statut) },
        { cle: 'titre', libelle: 'Titre' },
      ],
      carte: (o) => UI.html`<a href="#/ot/${encodeURIComponent(o.id)}">
        <div class="carte-tete"><b>${o.id}</b>${UI.badgePriorite(o.priorite)}${UI.badgeStatut(o.statut)}</div>
        <div class="carte-titre">${o.titre}</div>
        <div class="carte-meta"><span>${UI.dateFr(o.date_creation)}</span><span>${o.type}</span></div></a>`,
    }));
  }

  function carteHistoriqueDi(equipement) {
    const demandes = Donnees.lignes('demandes').filter((d) => d.equipement_id === equipement.id)
      .sort((a, b) => comparerTextes(b.date_heure, a.date_heure) || comparerTextes(b.id, a.id));
    return carteHistorique('Historique des demandes d\'intervention', demandes, (lignes) => listeAdaptative({
      lignes,
      vide: 'Aucune demande d\'intervention sur cet équipement.',
      libelle: 'Demandes d\'intervention de l\'équipement',
      lien: (d) => '#/di/' + encodeURIComponent(d.id),
      colonnes: [
        { cle: 'id', libelle: 'N°', rendu: (d) => UI.html`<a href="#/di/${encodeURIComponent(d.id)}">${d.id}</a>` },
        { cle: 'date_heure', libelle: 'Date', rendu: (d) => UI.dateFr(d.date_heure), classe: 'sans-coupure' },
        { cle: 'symptome', libelle: 'Symptôme', rendu: (d) => abreger(d.symptome, 110) },
        { cle: 'statut', libelle: 'Statut', rendu: (d) => UI.badgeStatut(d.statut) },
      ],
      carte: (d) => UI.html`<a href="#/di/${encodeURIComponent(d.id)}">
        <div class="carte-tete"><b>${d.id}</b>${UI.badgeStatut(d.statut)}</div>
        <div class="carte-titre">${abreger(d.symptome, 110)}</div>
        <div class="carte-meta"><span>${UI.dateFr(d.date_heure)}</span></div></a>`,
    }));
  }

  // Désactive ou réactive un équipement (jamais de suppression : l'historique est conservé).
  async function changerActivite(equipement, activer) {
    if (!activer) {
      const ouverts = Donnees.lignes('ordres_travail').filter((o) => o.equipement_id === equipement.id && !STATUTS_OT_FERMES.includes(o.statut)).length;
      const sousEquipements = Donnees.lignes('equipements').filter((e) => e.parent_id === equipement.id && estActif(e)).length;
      let message = 'Désactiver ' + libelleEquipement(equipement.id) + ' ? Il ne sera plus proposé pour une demande ou un ordre de travail '
        + 'et disparaîtra de la liste du parc (sauf si « Afficher les inactifs » est coché). Son historique est conservé.';
      if (ouverts) message += ' Attention : ' + ouverts + ' ordre' + (ouverts > 1 ? 's' : '') + ' de travail ouvert' + (ouverts > 1 ? 's' : '') + ' le concerne' + (ouverts > 1 ? 'nt' : '') + ' encore.';
      if (sousEquipements) message += ' Ses ' + sousEquipements + ' sous-équipement(s) actif(s) ne sont pas désactivés.';
      if (!await UI.confirmer(message, { titre: 'Désactiver l\'équipement', oui: 'Désactiver', danger: true })) return;
    } else if (!await UI.confirmer('Réactiver ' + libelleEquipement(equipement.id) + ' ? Il réapparaîtra dans le parc.', { titre: 'Réactiver l\'équipement', oui: 'Réactiver' })) {
      return;
    }
    try {
      await Donnees.modifier('equipements', (lignes) => {
        const ligne = lignes.find((l) => l.id === equipement.id);
        if (!ligne) throw new Donnees.ErreurValidation('Cet équipement n\'existe plus.');
        if (activer) {
          const double = lignes.find((l) => l.id !== ligne.id && estActif(l) && UI.normaliserRecherche(l.repere) === UI.normaliserRecherche(ligne.repere));
          if (double) {
            throw new Donnees.ErreurValidation('Réactivation impossible : le repère « ' + ligne.repere + ' » est maintenant utilisé par '
              + libelleEquipement(double.id) + '. Changez le repère de l\'un des deux.');
          }
        }
        ligne.actif = activer ? '1' : '0';
      }, { action: activer ? 'réactivation' : 'désactivation' });
      UI.toast(activer ? 'Équipement réactivé.' : 'Équipement désactivé.', 'succes');
      await App.reafficher();
    } catch (erreur) {
      App.signalerErreur(erreur, activer ? 'réactivation' : 'désactivation');
    }
  }

  async function afficherFiche(conteneur, parametres) {
    const equipement = Donnees.trouver('equipements', parametres.id);
    if (!equipement) {
      App.definirTitre('Équipement introuvable');
      UI.remplir(conteneur, UI.html`<div class="parc">
        <div class="entete-page"><div>
          <div class="fil"><a href="#/parc">Parc</a></div>
          <h1>Équipement introuvable</h1>
        </div></div>
        ${UI.vide('Aucun équipement ne porte l\'identifiant « ' + parametres.id + ' »',
          'Le QR code est peut-être celui d\'un autre atelier, ou l\'équipement a été saisi sur un autre poste.', 'recherche')}
        <p><a class="btn btn-secondaire" href="#/parc">Retour au parc</a></p></div>`);
      return;
    }
    App.definirTitre(equipement.repere || equipement.id);
    const responsable = App.estResponsable();
    const adresse = await adresseDocument(equipement.document);
    const idUrl = encodeURIComponent(equipement.id);
    const actif = estActif(equipement);
    const sousEquipements = carteSousEquipements(equipement);

    UI.remplir(conteneur, UI.html`
      <div class="parc">
        <div class="entete-page">
          <div>
            <div class="fil"><a href="#/parc">Parc</a>${equipement.localisation_id ? UI.html` <span aria-hidden="true">›</span> <span>${cheminLocalisation(equipement.localisation_id)}</span>` : ''}</div>
            <h1>${libelleEquipement(equipement.id)}</h1>
            <p class="parc-badges-fiche">${badgeCriticite(equipement.criticite)} ${equipement.statut ? UI.badgeStatut(equipement.statut) : ''}
              ${actif ? '' : UI.html`<span class="badge neutre barre">Inactif</span>`}</p>
          </div>
        </div>

        <div class="parc-actions">
          <a class="btn btn-primaire btn-gros parc-signaler" href="#/di/nouvelle?equipement=${idUrl}">${UI.icone('alerte')}
            <span>Signaler un problème<small>Une panne, une fuite, un bruit anormal : prévenez la maintenance</small></span></a>
          ${responsable ? UI.html`<div class="actions">
            <a class="btn btn-secondaire" href="#/ot/nouveau?equipement=${idUrl}">${UI.icone('ordres')}Créer un OT</a>
            <a class="btn btn-secondaire" href="#/equipement/${idUrl}/modifier">${UI.icone('cle')}Modifier</a>
            <button type="button" class="btn ${actif ? 'btn-danger' : 'btn-secondaire'}" id="parc-activite">${actif ? 'Désactiver' : 'Réactiver'}</button>
          </div>` : ''}
        </div>

        ${actif ? '' : UI.html`<div class="alertes"><div class="alerte attention" role="status">${UI.icone('alerte')}
          <div class="alerte-texte"><b>Cet équipement est désactivé.</b> Il n'est plus proposé pour les demandes et les ordres de travail ; son historique reste consultable.</div></div></div>`}

        ${carteConsignation(equipement)}

        <div class="grille">
          <div class="c8">${carteCaracteristiques(equipement, adresse)}</div>
          <div class="c4">${carteQr(equipement)}</div>
        </div>
        <div class="grille">
          <div class="${sousEquipements ? 'c6' : 'c12'}">${carteCompteurs(equipement)}</div>
          ${sousEquipements ? UI.html`<div class="c6">${sousEquipements}</div>` : ''}
        </div>
        <div class="parc-complements"></div>
      </div>`);

    const zone = UI.$('.parc-complements', conteneur);
    zone.appendChild(carteArticles(equipement));
    zone.appendChild(carteHistoriqueOt(equipement));
    zone.appendChild(carteHistoriqueDi(equipement));

    const boutonActivite = UI.$('#parc-activite', conteneur);
    if (boutonActivite) boutonActivite.addEventListener('click', () => changerActivite(equipement, !actif));
  }

  // ===========================================================================================
  // 7. Enregistrement des écrans (App est chargé après les modules : on attend la page)
  // ===========================================================================================

  document.addEventListener('DOMContentLoaded', () => {
    const tous = ['demandeur', 'technicien', 'responsable'];
    App.ecran({
      id: 'parc', route: /^#\/parc$/, titre: 'Parc',
      menu: { libelle: 'Parc', icone: 'parc', ordre: 40 },
      profils: tous,
      tables: ['equipements', 'localisations'],
      afficher: afficherListe,
    });
    // Les routes les plus précises d'abord : « nouveau » ne doit pas être pris pour un identifiant
    // (la route fiche l'exclut en plus, ARCHITECTURE.md §14.2).
    App.ecran({
      id: 'equipement-nouveau', route: /^#\/equipement\/nouveau$/, titre: 'Nouvel équipement', parent: 'parc',
      profils: ['responsable'],
      tables: [],
      afficher: afficherFormulaire,
    });
    App.ecran({
      id: 'equipement-modifier', route: /^#\/equipement\/(?<id>[^/?]+)\/modifier$/, titre: 'Modifier l\'équipement', parent: 'parc',
      profils: ['responsable'],
      tables: [],
      afficher: afficherFormulaire,
    });
    App.ecran({
      id: 'equipement', route: /^#\/equipement\/(?!nouveau$)(?<id>[^/?]+)$/, titre: 'Équipement', parent: 'parc',
      profils: tous,
      tables: ['equipements', 'localisations', 'ordres_travail', 'demandes', 'compteurs', 'releves',
        'articles', 'article_equipement', 'mouvements_stock'],
      afficher: afficherFiche,
    });
  });

  return {
    afficherFiche,
  };
})());
