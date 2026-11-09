'use strict';
// Garanties — encarts dans les écrans des autres modules (2.2, lot L4 ; CDC §3.4, D126, D182, CS173).
// Les autres modules les appellent derrière typeof Garanties !== 'undefined' (pages de test, outils/wiki_demo.py) :
//   Garanties.badgeEquipement(equipement, jour)
//       Fiche équipement, à côté de la criticité : badge « Sous garantie jusqu'au 31/03/2027 » (fragment UI.html, à
//       insérer dans un gabarit), '' si l'équipement n'est pas sous garantie le jour donné.
//   Garanties.carteEquipement(equipement, responsable, jour)
//       Fiche équipement, sous la carte des contrôles : carte « Garanties et contrats » (ÉLÉMENT DOM à placer :
//       UI.remplir, appendChild, after). Garanties en cours (fournisseur, téléphone en tel:, conditions repliées
//       au-delà de 3 lignes, document) ; garanties à venir, de fin inconnue et les 3 dernières terminées ; contrats
//       actifs qui citent l'équipement (objet, prestataire, fin ; statut et raison pour le responsable) ; vide
//       expliqué. responsable (booléen) : « Ajouter une garantie » et liens vers les fiches (écrans du responsable
//       seul). JAMAIS de montant : le technicien voit cette carte (D126). Les liens des documents se règlent seuls
//       juste après (lecture asynchrone du stockage, comme les justificatifs de la fiche d'un technicien).
//   Garanties.rappelOt(equipementId, type, jour)
//       Formulaire d'un OT (zone .ot-zone-garantie, séparée de la zone d'habilitation) et fenêtre « Accepter » d'une
//       DI : bandeau « attention » (élément DOM) si le type est un correctif (immédiat ou différé) et l'équipement
//       sous garantie le jour donné ; sinon null. Un rappel, jamais un blocage ; rien au journal (QUESTIONS L4-L6 Q7).
// equipement : la ligne de equipements.csv ou son identifiant ; jour : 'AAAA-MM-JJ', par défaut aujourd'hui.
// Profils : technicien et responsable ; le demandeur ne reçoit pas ces tables (l'appelant ne lui montre rien).
// Dernier fichier du module, chargé juste après garanties-ecrans.js (badges, fournisseur et document des fiches,
// rangés dans Garanties.interne). Complète l'objet Garanties.

Object.assign(Garanties, (() => {

  const { texte, dateDuJour, badge, blocFournisseur, adresseDocument, blocDocument } = Garanties.interne;

  // Types d'OT qui déclenchent le rappel (valeurs stockées, en français : D155).
  const TYPES_CORRECTIFS = Object.freeze(['correctif immédiat', 'correctif différé']);
  const TERMINEES_AFFICHEES = 3;
  // Conditions repliées au-delà de 3 lignes : plus de 3 lignes écrites, ou assez de texte pour en remplir plus de 3 à
  // l'écran ; la feuille n'en montre alors que 3 (line-clamp) et un bouton déplie le reste.
  const LIGNES_CONDITIONS = 3;
  const LONGUEUR_CONDITIONS = 180;
  // Texte du rappel selon ce qu'on sait du fournisseur.
  const CLES_RAPPEL = Object.freeze({
    complet: 'garanties.rappel_ot.texte',
    sans_telephone: 'garanties.rappel_ot.texte_sans_telephone',
    sans_fournisseur: 'garanties.rappel_ot.texte_sans_fournisseur',
  });

  function idDe(equipement) {
    return texte(equipement && typeof equipement === 'object' ? equipement.id : equipement);
  }

  function libelleChamp(table, nom) {
    const champ = Schema.champ(table, nom);
    return champ ? champ.libelle : nom;
  }

  function fournisseurDe(id) {
    return texte(id) ? Donnees.trouver('fournisseurs', texte(id)) || null : null;
  }

  function nomFournisseur(fournisseur) {
    return fournisseur ? texte(fournisseur.nom) || fournisseur.id : '';
  }

  function lienTelephone(telephone) {
    return UI.html`<a href="tel:${telephone.replace(/[^0-9+]/g, '')}">${telephone}</a>`;
  }

  // ===========================================================================================
  // 21. Badge de la fiche équipement
  // ===========================================================================================

  /** « Sous garantie jusqu'au 31/03/2027 » (ambre si la garantie se termine sous le délai d'alerte), ou ''. */
  function badgeEquipement(equipement, jour) {
    const date = dateDuJour(jour);
    const sous = Garanties.sousGarantie(idDe(equipement), date);
    if (!sous) return '';
    const ton = Garanties.etatGarantie(sous.garantie, date).alerte ? 'attention' : 'ok';
    return UI.html`<span class="garanties-badge-equipement" data-garantie="${sous.garantie.id}">${UI.badgeStatut('', ton,
      I18n.t('garanties.encart.sous_garantie', { fin: UI.dateFr(sous.fin) }))}</span>`;
  }

  // ===========================================================================================
  // 22. Carte « Garanties et contrats » de la fiche équipement
  // ===========================================================================================

  function blocConditions(conditions) {
    const longues = conditions.split(/\r?\n/).length > LIGNES_CONDITIONS || conditions.length > LONGUEUR_CONDITIONS;
    if (!longues) return UI.html`<div class="garanties-encart-conditions">${conditions}</div>`;
    const id = UI.identifiantUnique('garanties-conditions');
    return UI.html`<div class="garanties-encart-conditions replie" id="${id}">${conditions}</div>
      <button type="button" class="lien-bouton garanties-encart-deplier" aria-expanded="false" aria-controls="${id}">${I18n.t('garanties.encart.conditions_deplier')}</button>`;
  }

  /** Garantie en cours : fin, statut, fournisseur, conditions, document (rendu des fiches). */
  function itemEnCours({ ligne, etat }, responsable) {
    const titre = I18n.t('garanties.encart.sous_garantie', { fin: UI.dateFr(etat.fin) });
    const valeurs = [];
    const nomDocument = texte(ligne.document);
    const libelle = (nom) => UI.html`<dt>${libelleChamp('garanties', nom)}</dt> `;
    if (texte(ligne.fournisseur_id)) valeurs.push(UI.html`${libelle('fournisseur_id')}<dd>${blocFournisseur(ligne.fournisseur_id)}</dd>`);
    if (texte(ligne.conditions)) valeurs.push(UI.html`${libelle('conditions')}<dd>${blocConditions(texte(ligne.conditions))}</dd>`);
    // le lien « Ouvrir » est posé par relierDocuments, une fois l'adresse lue dans le stockage
    if (nomDocument) {
      valeurs.push(UI.html`${libelle('document')}<dd class="garanties-encart-document" data-document="${nomDocument}"><span class="muted">${nomDocument}</span></dd>`);
    }
    return UI.html`<li class="garanties-encart-en-cours" data-garantie="${ligne.id}">
      <div class="garanties-encart-tete">${responsable ? UI.html`<a href="${Garanties.adresseFiche(ligne.id)}">${titre}</a>` : UI.html`<b>${titre}</b>`} ${badge(etat.statut)}</div>
      ${etat.alerte ? UI.html`<div class="garanties-encart-detail">${etat.raison}</div>` : ''}
      ${valeurs.length ? UI.html`<dl class="valeurs">${valeurs.map((v) => UI.html`${v} `)}</dl>` : ''}</li>`;
  }

  /** Garantie à venir, de fin inconnue ou terminée : statut, raison, fournisseur. */
  function itemAutre({ ligne, etat }, responsable) {
    const raison = etat.statut === 'fin_inconnue' ? I18n.t('garanties.encart.fin_non_renseignee') : etat.raison;
    const fournisseur = nomFournisseur(fournisseurDe(ligne.fournisseur_id));
    return UI.html`<li data-garantie="${ligne.id}">
      <div class="garanties-encart-tete">${badge(etat.statut)} ${responsable ? UI.html`<a href="${Garanties.adresseFiche(ligne.id)}">${raison}</a>` : UI.html`<span>${raison}</span>`}</div>
      ${fournisseur ? UI.html`<div class="garanties-encart-detail">${fournisseur}</div>` : ''}</li>`;
  }

  /** Période d'un contrat pour le technicien : « jusqu'au … », « reconduit tacitement le … », « terminé le … ». */
  function periodeContrat(etat) {
    if (etat.statut === 'fin_inconnue') return I18n.t('garanties.encart.fin_non_renseignee');
    if (etat.statut === 'termine') return I18n.t('garanties.raison_contrat.termine', { fin: UI.dateFr(etat.fin) });
    // reconduit tacitement après sa fin enregistrée : période calculée (reconduction_mois) ou pas encore saisie
    if (etat.periodeCalculee) {
      return I18n.t('garanties.encart.contrat_reconduit', { fin: UI.dateFr(etat.fin), finPeriode: UI.dateFr(etat.finPeriode) });
    }
    if (etat.statut === 'a_mettre_a_jour') return I18n.t('garanties.encart.contrat_reconduit_sans_fin', { fin: UI.dateFr(etat.fin) });
    return I18n.t('garanties.raison_contrat.en_cours', { fin: UI.dateFr(etat.finPeriode) });
  }

  /** Contrat qui cite l'équipement : objet, prestataire (téléphone), fin ; statut et raison pour le responsable.
   *  Ni montant ni document (le contrat signé porte le prix : servi au responsable seul). */
  function itemContrat({ ligne, etat }, responsable) {
    const objet = texte(ligne.objet) || ligne.id;
    const prestataire = fournisseurDe(ligne.fournisseur_id);
    const telephone = prestataire ? texte(prestataire.telephone) : '';
    return UI.html`<li data-contrat="${ligne.id}">
      <div class="garanties-encart-tete">${responsable ? UI.html`<a href="${Garanties.adresseFiche(ligne.id)}">${objet}</a> ${badge(etat.statut)}` : UI.html`<b>${objet}</b>`}</div>
      <div class="garanties-encart-detail">${prestataire ? UI.html`<span>${nomFournisseur(prestataire)}${telephone ? UI.html` · ${lienTelephone(telephone)}` : ''}</span>` : ''}
        <span>${responsable ? etat.raison : periodeContrat(etat)}</span></div></li>`;
  }

  /** Après la création : liens « Ouvrir » des documents (adresse du stockage), « Fichier introuvable » sinon. */
  async function relierDocuments(carte) {
    if (typeof App === 'undefined') return;              // page sans application : le nom du fichier reste affiché
    for (const zone of UI.$$('[data-document]', carte)) {
      const nom = zone.dataset.document;
      UI.remplir(zone, blocDocument(nom, await adresseDocument(nom)));
      zone.removeAttribute('data-document');
    }
  }

  function brancherConditions(carte) {
    UI.$$('.garanties-encart-deplier', carte).forEach((bouton) => bouton.addEventListener('click', () => {
      const ouvert = bouton.getAttribute('aria-expanded') !== 'true';
      UI.$('#' + bouton.getAttribute('aria-controls'), carte).classList.toggle('replie', !ouvert);
      bouton.setAttribute('aria-expanded', String(ouvert));
      bouton.textContent = I18n.t(ouvert ? 'garanties.encart.conditions_replier' : 'garanties.encart.conditions_deplier');
    }));
  }

  /** Carte « Garanties et contrats » de la fiche équipement (élément DOM) : voir l'entête du fichier. */
  function carteEquipement(equipement, responsable, jour) {
    const id = idDe(equipement);
    const date = dateDuJour(jour);
    const delai = Garanties.delaiAlerte();
    // Fin la plus lointaine d'abord (garantiesDeLEquipement) : les terminées les plus récentes en tête.
    const garanties = Garanties.garantiesDeLEquipement(id).map((ligne) => ({ ligne, etat: Garanties.etatGarantie(ligne, date, delai) }));
    const avec = (...statuts) => garanties.filter((g) => statuts.includes(g.etat.statut));
    const enCours = avec('en_cours', 'bientot');
    const terminees = avec('terminee');
    const autres = avec('a_venir').reverse().concat(avec('fin_inconnue'), terminees.slice(0, TERMINEES_AFFICHEES));
    // Contrats par date de fin (contratsDeLEquipement), les terminés en dernier.
    const contrats = Garanties.contratsDeLEquipement(id).map((ligne) => ({ ligne, etat: Garanties.etatContrat(ligne, date, delai) }));
    const ordonnes = contrats.filter((c) => c.etat.statut !== 'termine').concat(contrats.filter((c) => c.etat.statut === 'termine'));
    const masquees = terminees.length - TERMINEES_AFFICHEES;
    const carte = UI.element(UI.html`
      <article class="carte garanties-carte-equipement" data-equipement="${id}">
        <div class="entete-carte"><h2>${I18n.t('garanties.liste.titre')}</h2>
          ${responsable ? UI.html`<a class="btn btn-secondaire" id="garanties-ajouter-garantie"
            href="${Garanties.adresseNouvelleGarantie(id)}">${UI.icone('ajouter')}${I18n.t('garanties.encart.ajouter_garantie')}</a>` : ''}</div>
        ${!garanties.length && !contrats.length ? UI.html`<p class="muted">${I18n.t('garanties.encart.vide')}</p>` : ''}
        ${garanties.length && !enCours.length ? UI.html`<p class="garanties-encart-pas-sous-garantie">${I18n.t('garanties.encart.pas_sous_garantie')}</p>` : ''}
        ${enCours.length ? UI.html`<ul class="garanties-encart-liste">${enCours.map((g) => itemEnCours(g, responsable))}</ul>` : ''}
        ${autres.length ? UI.html`<h3>${I18n.t('garanties.encart.autres_garanties')}</h3>
          <ul class="garanties-encart-liste garanties-encart-autres">${autres.map((g) => itemAutre(g, responsable))}</ul>
          ${masquees > 0 ? UI.html`<p class="note">${I18n.t('garanties.encart.terminees_masquees', { n: masquees })}</p>` : ''}` : ''}
        ${ordonnes.length ? UI.html`<h3>${I18n.t('garanties.encart.contrats')}</h3>
          <ul class="garanties-encart-liste garanties-encart-contrats">${ordonnes.map((c) => itemContrat(c, responsable))}</ul>` : ''}
      </article>`);
    brancherConditions(carte);
    relierDocuments(carte);
    return carte;
  }

  // ===========================================================================================
  // 23. Rappel à la création d'un OT correctif
  // ===========================================================================================

  /**
   * « Équipement sous garantie jusqu'au 31/03/2027 (Hydraulique Services, tél. 04 65 71 00 99). Appeler le fournisseur
   * avant d'intervenir ? » et « Conditions : … » si elles sont saisies : bandeau « attention » (élément DOM) quand le
   * type est un correctif et l'équipement sous garantie le jour donné ; null sinon (préventif, amélioration, sans
   * équipement, pas de garantie en cours).
   */
  function rappelOt(equipementId, type, jour) {
    if (!TYPES_CORRECTIFS.includes(texte(type))) return null;
    const sous = Garanties.sousGarantie(idDe(equipementId), dateDuJour(jour));
    if (!sous) return null;
    const nom = nomFournisseur(sous.fournisseur);
    const telephone = sous.fournisseur ? texte(sous.fournisseur.telephone) : '';
    const cle = !nom ? CLES_RAPPEL.sans_fournisseur : telephone ? CLES_RAPPEL.complet : CLES_RAPPEL.sans_telephone;
    const conditions = texte(sous.garantie.conditions);
    const bandeau = UI.bandeau('attention', UI.html`<p>${I18n.html(cle, { fin: UI.dateFr(sous.fin), fournisseur: nom,
      telephone: telephone ? lienTelephone(telephone) : '' })}</p>
      ${conditions ? UI.html`<p class="garanties-rappel-conditions">${I18n.t('garanties.rappel_ot.conditions', { conditions })}</p>` : ''}`);
    bandeau.classList.add('garanties-rappel');
    bandeau.dataset.garantie = sous.garantie.id;
    return bandeau;
  }

  return { badgeEquipement, carteEquipement, rappelOt, TYPES_CORRECTIFS };
})());
