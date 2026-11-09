'use strict';
// Controles — catalogue des contrôles réglementaires à l'écran (2.2, lot L2, CS171 ; window.CatalogueFR de
// js/catalogue/fr.js, gelé, en lecture seule : aucune fonction de Prévo ne l'écrit).
//   1. Règles pures du catalogue (T414, CONCEPTION-L2-L3 §4.1) : catalogue, ligneCatalogue, famillesCatalogue,
//      valeursDepuisCatalogue, lireSource, sourceApresSaisie, mentionDuControle, miseAJourProposee. Sans
//      CatalogueFR (page de test sans le fichier, catalogue retiré un jour), liste vide : l'écran retombe sur la
//      saisie libre, sans erreur. Une mise à jour du catalogue n'est JAMAIS appliquée par ces fonctions : elle est
//      seulement proposée (miseAJourProposee), reprise sur un clic par appliquerMiseAJourCatalogue (T415).
//   2. Le catalogue à l'écran (T416, §4.3, §4.4) : bloc du formulaire de création (Controles.interne.blocCatalogue),
//      source d'un contrôle sur sa fiche (blocSourceControle : provenance, liens, mention, mise à jour proposée).
// Chargé après controles-reserves.js et avant controles-ecritures.js. Complète l'objet Controles ; une fonction d'un
// fichier chargé plus tard est cherchée au moment de l'appel.

Object.assign(Controles, (() => {
  const { texte, dateIso } = Controles.interne;

  // ===========================================================================================
  // 1. Règles pures du catalogue
  // ===========================================================================================

  // Champs qui font la source d'un contrôle (source_periodicite) : égaux à ceux de la ligne choisie → « catalogue ».
  // La nature (intitulé du contrôle) n'en est pas : on peut la renommer et rester « catalogue ».
  const CHAMPS_SOURCE = Object.freeze(['periodicite_mois', 'texte_reference', 'nature_source']);

  // Remplacements à l'affichage, en ce seul endroit : réponse provisoire n° 1 de QUESTIONS-L2-L6 (C18, CS175, D182),
  // à confirmer par Nicolas. L'écran n'affiche jamais « conforme » ; le catalogue validé (docs/catalogue/*.json,
  // window.CatalogueFR) n'est pas modifié. Si la ligne est reformulée dans le catalogue, l'entrée ne joue plus :
  // la retirer.
  const REMPLACEMENTS_AFFICHES = Object.freeze([
    Object.freeze({ id: 'C18', champ: 'periodicite_texte', avant: 'équipement fixe conforme',
      apres: 'équipement fixe répondant aux exigences du règlement' }),
  ]);

  /** La ligne telle qu'affichée : elle-même, ou une copie gelée où les remplacements ci-dessus sont faits. */
  function ligneAffichee(ligne) {
    const remplacements = REMPLACEMENTS_AFFICHES.filter((remplacement) => remplacement.id === ligne.id
      && typeof ligne[remplacement.champ] === 'string' && ligne[remplacement.champ].includes(remplacement.avant));
    if (!remplacements.length) return ligne;
    const copie = Object.assign({}, ligne);
    remplacements.forEach((remplacement) => {
      copie[remplacement.champ] = copie[remplacement.champ].split(remplacement.avant).join(remplacement.apres);
    });
    return Object.freeze(copie);
  }

  // Lignes affichées, recalculées seulement quand window.CatalogueFR change (page de test, version modifiée).
  let memo = { source: null, lignes: Object.freeze([]) };

  /** Lignes du catalogue des contrôles (CatalogueFR.controles, dans l'ordre du fichier), gelées ; [] sans catalogue. */
  function catalogue() {
    const source = window.CatalogueFR && Array.isArray(window.CatalogueFR.controles)
      ? window.CatalogueFR.controles : null;
    if (!source) return [];
    if (memo.source !== source) {
      const lignes = source.filter((ligne) => ligne && typeof ligne === 'object' && texte(ligne.id) !== '');
      memo = { source, lignes: Object.freeze(lignes.map(ligneAffichee)) };
    }
    return memo.lignes;
  }

  /** Une ligne du catalogue par son identifiant (« C14 », casse et espaces ignorés), ou null. */
  function ligneCatalogue(id) {
    const cherche = texte(id).toUpperCase();
    if (!cherche) return null;
    return catalogue().find((ligne) => texte(ligne.id).toUpperCase() === cherche) || null;
  }

  /** [{ famille, lignes }] dans l'ordre du fichier (un <optgroup> par famille) ; [] sans catalogue. */
  function famillesCatalogue() {
    const familles = [];
    catalogue().forEach((ligne) => {
      const nom = texte(ligne.famille);
      let groupe = familles.find((element) => element.famille === nom);
      if (!groupe) {
        groupe = { famille: nom, lignes: [] };
        familles.push(groupe);
      }
      groupe.lignes.push(ligne);
    });
    return familles;
  }

  /** Une ligne donnée par elle-même ou par son identifiant. */
  function ligneDonnee(ligne) {
    return ligne && typeof ligne === 'object' ? ligne : ligneCatalogue(ligne);
  }

  /**
   * Valeurs d'un contrôle copiées d'une ligne du catalogue (ou de son identifiant), en texte comme dans les CSV :
   * { nature, periodicite_mois, texte_reference, nature_source, source_periodicite: 'catalogue', catalogue_id,
   *   catalogue_relu_le } ; periodicite_mois '' quand le catalogue n'en donne pas (C13, C24). null sans ligne.
   */
  function valeursDepuisCatalogue(ligne) {
    const choisie = ligneDonnee(ligne);
    if (!choisie) return null;
    const mois = texte(choisie.periodicite_mois);
    return {
      nature: texte(choisie.nature),
      periodicite_mois: /^[1-9]\d*$/.test(mois) ? mois : '',
      texte_reference: texte(choisie.reference),
      nature_source: texte(choisie.nature_source),
      source_periodicite: 'catalogue',
      catalogue_id: texte(choisie.id),
      catalogue_relu_le: dateIso(choisie.relu_le),
    };
  }

  /** Valeur d'un champ de source telle qu'on la compare (périodicité « 048 » = « 48 »). */
  function valeurComparee(champ, valeur) {
    const brute = texte(valeur);
    return champ === 'periodicite_mois' && /^\d+$/.test(brute) ? String(Number(brute)) : brute;
  }

  function memeSource(valeurs, reference) {
    return CHAMPS_SOURCE.every((champ) => valeurComparee(champ, valeurs[champ]) === valeurComparee(champ, reference[champ]));
  }

  /**
   * Provenance d'un contrôle : { origine: 'catalogue' | 'saisie', catalogueId, reluLe }. « catalogue » demande
   * source_periodicite = catalogue ET un catalogue_id (fichier retouché à la main sans lui : lu « saisie ») ; tout
   * le reste, contrôles d'avant la 2.2 compris (défaut du format 4), est « saisie ». catalogueId est rendu même
   * en saisie (la nature a pu être choisie au catalogue) ; reluLe : date ISO lisible, sinon ''.
   */
  function lireSource(controle) {
    const valeurs = controle || {};
    const catalogueId = texte(valeurs.catalogue_id);
    const origine = texte(valeurs.source_periodicite) === 'catalogue' && catalogueId ? 'catalogue' : 'saisie';
    return { origine, catalogueId, reluLe: dateIso(valeurs.catalogue_relu_le) };
  }

  /**
   * Source d'un contrôle après une saisie : { source_periodicite, catalogue_id, catalogue_relu_le }.
   * valeurs : le contrôle tel qu'il sera écrit (champs complets) ; ligne : la ligne du catalogue choisie (ou son
   * identifiant) ; avant (facultatif) : le contrôle avant la modification.
   * - « catalogue » si périodicité, référence et nature de la source sont celles de la ligne ;
   * - « catalogue » aussi si le contrôle l'était avant et que ces trois valeurs n'ont pas changé (la ligne a été
   *   relue depuis : sa mise à jour reste proposée, jamais appliquée par une autre modification) ;
   * - sinon « saisie », catalogue_id et catalogue_relu_le gardés (la nature a été choisie au catalogue) ;
   * - sans ligne (aucune, ou identifiant inconnu) : « saisie », catalogue_id et catalogue_relu_le vides.
   * catalogue_relu_le : celui des valeurs s'il est lisible, sinon la date de relecture de la ligne.
   */
  function sourceApresSaisie(valeurs, ligne, avant) {
    const choisie = ligneDonnee(ligne);
    if (!choisie) return { source_periodicite: 'saisie', catalogue_id: '', catalogue_relu_le: '' };
    const saisies = valeurs || {};
    const copiees = valeursDepuisCatalogue(choisie);
    const precedent = avant ? lireSource(avant) : null;
    const inchangee = Boolean(precedent) && precedent.origine === 'catalogue'
      && precedent.catalogueId.toUpperCase() === copiees.catalogue_id.toUpperCase() && memeSource(saisies, avant);
    return {
      source_periodicite: memeSource(saisies, copiees) || inchangee ? 'catalogue' : 'saisie',
      catalogue_id: copiees.catalogue_id,
      catalogue_relu_le: dateIso(saisies.catalogue_relu_le) || copiees.catalogue_relu_le,
    };
  }

  /** La mention de la ligne catalogue_id du contrôle (« à confirmer avec votre organisme de contrôle », C04, C13),
   *  ou ''. */
  function mentionDuControle(controle) {
    const ligne = ligneCatalogue(controle && controle.catalogue_id);
    return ligne ? texte(ligne.mention) : '';
  }

  /**
   * Mise à jour du catalogue proposée pour un contrôle, jamais appliquée (rien n'est écrit, le contrôle n'est pas
   * touché) : null, ou { ligne, ecarts: [{ champ, actuel, propose }] } quand le contrôle est « catalogue », que sa
   * ligne a été relue après catalogue_relu_le (date inconnue : toute relecture compte) et que périodicité,
   * référence ou nature de la source y diffèrent.
   */
  function miseAJourProposee(controle) {
    const source = lireSource(controle);
    if (source.origine !== 'catalogue') return null;
    const ligne = ligneCatalogue(source.catalogueId);
    if (!ligne) return null;
    const reluLe = dateIso(ligne.relu_le);
    if (source.reluLe && !(reluLe > source.reluLe)) return null;
    const proposees = valeursDepuisCatalogue(ligne);
    const ecarts = CHAMPS_SOURCE
      .filter((champ) => valeurComparee(champ, controle[champ]) !== valeurComparee(champ, proposees[champ]))
      .map((champ) => ({ champ, actuel: texte(controle[champ]), propose: proposees[champ] }));
    return ecarts.length ? { ligne, ecarts } : null;
  }

  // ===========================================================================================
  // 2. Le catalogue à l'écran (T416, CONCEPTION-L2-L3 §4.3, §4.4) : bloc du formulaire de création (blocCatalogue),
  //    source d'un contrôle sur sa fiche (blocSourceControle), provenance (texteProvenance). Le contenu du catalogue
  //    (nature, référence, liens, équipements visés, qui vérifie, periodicite_texte, mention) reste en français dans
  //    toutes les langues (CDC §3.2 : textes juridiques français) : ses blocs portent lang="fr" et data-catalogue,
  //    que tests/test_ecrans_anglais.py range parmi les données ; une option de la liste, où le texte du catalogue
  //    voisine avec un texte traduit (« — 12 months »), porte la part du catalogue dans data-catalogue. Libellés,
  //    provenance, mention « réglementation française » et phrase D182 sont traduits. Aucune écriture ici, sauf le
  //    bouton « Reprendre ces valeurs » : Controles.appliquerMiseAJourCatalogue (T415), sur un clic du responsable.
  // ===========================================================================================

  // Champs que le choix d'une ligne pré-remplit (valeursDepuisCatalogue) ; tout reste modifiable.
  const CHAMPS_PRE_REMPLIS = Object.freeze(['nature', 'periodicite_mois', 'texte_reference', 'nature_source']);
  const ADRESSE_LIEN = /^https:\/\/[^\s"'<>]+$/;

  const libelleMois = (valeur) => I18n.t('controles.carte_description.periodicite_mois_mois', { n: Number(valeur) });
  const catalogueHtml = (valeur) => UI.html`<span lang="fr" data-catalogue>${valeur}</span>`;

  /** Provenance d'un contrôle (§2) : « Catalogue Prévo (C14), relu le 08/11/2026 — réglementation française »,
   *  « Saisie (nature choisie au catalogue : C14) » ou « Saisie ». source : un contrôle, ou ses champs de source. */
  function texteProvenance(source) {
    const lue = lireSource(source);
    if (lue.origine === 'catalogue') {
      return lue.reluLe
        ? I18n.t('controles.catalogue.provenance_catalogue', { ligne: lue.catalogueId, date: UI.dateFr(lue.reluLe) })
        : I18n.t('controles.catalogue.provenance_catalogue_sans_date', { ligne: lue.catalogueId });
    }
    return lue.catalogueId ? I18n.t('controles.catalogue.provenance_saisie_ligne', { ligne: lue.catalogueId })
      : I18n.t('controles.catalogue.provenance_saisie');
  }

  /** Liens d'une ligne (Légifrance, EUR-Lex…) : nouvel onglet, sans transmettre la page d'origine ; un simple lien
   *  ouvert par l'utilisateur, aucune requête de l'appli (CS177). Une adresse autre que https:// n'est pas un lien. */
  function liensHtml(ligne) {
    const liens = (Array.isArray(ligne.liens) ? ligne.liens : []).filter((lien) => lien && texte(lien.libelle || lien.url));
    if (!liens.length) return '';
    return UI.html`<ul class="controles-catalogue-liens">${liens.map((lien) => {
      const libelle = texte(lien.libelle) || texte(lien.url);
      if (!ADRESSE_LIEN.test(texte(lien.url))) return UI.html`<li>${catalogueHtml(libelle)}</li>`;
      return UI.html`<li><a href="${texte(lien.url)}" target="_blank" rel="noopener noreferrer">${catalogueHtml(libelle)}<span
        class="visuellement-cache"> ${I18n.t('controles.catalogue.nouvel_onglet')}</span></a></li>`;
    })}</ul>`;
  }

  /** Mention de la ligne (« à confirmer avec votre organisme de contrôle », C04, C13) en encadré d'attention. */
  function mentionHtml(mention) {
    if (!mention) return '';
    return UI.html`<div class="alerte attention controles-catalogue-mention" role="note">${UI.icone('alerte')}
      <div class="alerte-texte" lang="fr" data-catalogue>${mention}</div></div>`;
  }

  /** Libellé d'une option : « C01 · VGP pont roulant… — 12 mois » (« sans périodicité par défaut » : C13, C24). */
  function libelleOption(ligne) {
    const periodicite = valeursDepuisCatalogue(ligne).periodicite_mois;
    return I18n.t('controles.catalogue.option', { ligne: texte(ligne.id), nature: texte(ligne.nature),
      periodicite: periodicite ? libelleMois(periodicite) : I18n.t('controles.catalogue.option_sans_periodicite') });
  }

  /** Encart de la ligne choisie au formulaire : provenance (badge « saisie » si une valeur de la source a changé),
   *  source, référence, liens, équipements visés, qui vérifie, periodicite_texte, mention, « Tout reste modifiable ». */
  function encartHtml(ligne) {
    const valeurs = valeursDepuisCatalogue(ligne);
    const source = [Schema.libelleValeur('controles_reglementaires', 'nature_source', valeurs.nature_source),
      valeurs.catalogue_relu_le ? I18n.t('controles.catalogue.relu_le', { date: UI.dateFr(valeurs.catalogue_relu_le) }) : '',
      I18n.t('controles.catalogue.reglementation_francaise')].filter(Boolean).join(' · ');
    const liens = liensHtml(ligne);
    return UI.html`<dl class="valeurs controles-catalogue-valeurs">
      <dt>${I18n.t('controles.catalogue.provenance')}</dt><dd><span class="controles-provenance"></span>
        <span class="controles-badge-saisie"></span></dd>
      <dt>${I18n.t('controles.catalogue.source')}</dt><dd class="controles-catalogue-source">${source}</dd>
      <dt>${I18n.t('controles.carte_description.texte_reference')}</dt><dd lang="fr" data-catalogue>${valeurs.texte_reference}</dd>
      ${liens ? UI.html`<dt>${I18n.t('controles.catalogue.liens')}</dt><dd>${liens}</dd>` : ''}
      <dt>${I18n.t('controles.catalogue.equipements_vises')}</dt><dd lang="fr" data-catalogue>${texte(ligne.equipements)}</dd>
      <dt>${I18n.t('controles.catalogue.qui_verifie')}</dt><dd lang="fr" data-catalogue>${texte(ligne.qui_verifie)}</dd>
      <dt>${I18n.t('controles.carte_description.periodicite')}</dt><dd lang="fr" data-catalogue>${texte(ligne.periodicite_texte)}</dd>
      </dl>
      <p class="aide controles-valeur-modifiee" hidden>${I18n.t('controles.catalogue.valeur_modifiee')}</p>
      ${mentionHtml(texte(ligne.mention))}
      <p class="note">${I18n.t('controles.catalogue.tout_modifiable')}</p>`;
  }

  /**
   * Bloc du catalogue, inséré en tête du formulaire « Nouveau contrôle » (rendu) : liste « Choisir dans le catalogue
   * Prévo — réglementation française » (« Saisie libre (hors catalogue) » en premier et par défaut, Q6 ; un
   * <optgroup> par famille), encart de la ligne choisie, phrase D182. Choisir une ligne remplit nature, périodicité,
   * référence et nature de la source ; changer ensuite l'une des valeurs de la source montre « saisie », par la
   * règle même de l'écriture (sourceApresSaisie). La liste s'appelle catalogue_id : creerControle (T415) en déduit la
   * provenance. Sans catalogue (CatalogueFR absent) : la phrase seule, saisie libre.
   */
  function blocCatalogue(formulaire) {
    const familles = famillesCatalogue();
    const id = UI.identifiantUnique('controle-catalogue');
    const bloc = UI.element(UI.html`<div class="large controles-catalogue">${familles.length ? UI.html`
      <div class="champ" data-champ="catalogue_id"><label class="libelle" for="${id}">${I18n.t('controles.catalogue.choisir')}</label>
        <select id="${id}" name="catalogue_id" aria-describedby="${id}-aide">
          <option value="">${I18n.t('controles.catalogue.saisie_libre')}</option>${familles.map((groupe) => UI.html`
          <optgroup label="${groupe.famille}" data-catalogue>${groupe.lignes.map((ligne) => UI.html`
            <option value="${ligne.id}" data-catalogue="${texte(ligne.nature)}">${libelleOption(ligne)}</option>`)}</optgroup>`)}
        </select><p class="aide" id="${id}-aide">${I18n.t('controles.catalogue.aide_choix')}</p></div>
      <div class="encadre controles-catalogue-encart" hidden></div>` : ''}
      <p class="note controles-principe">${I18n.t('controles.principe.texte')}</p></div>`);
    formulaire.insertBefore(bloc, formulaire.firstChild);
    const liste = UI.$('select', bloc);
    if (!liste) return bloc;
    const encart = UI.$('.controles-catalogue-encart', bloc);
    const aidePeriodicite = UI.$('.champ[data-champ="periodicite_mois"] .aide', formulaire);
    const aideInitiale = aidePeriodicite ? aidePeriodicite.textContent : '';

    function actualiserProvenance() {
      const ligne = ligneCatalogue(liste.value);
      const provenance = UI.$('.controles-provenance', encart);
      if (!ligne || !provenance) return;
      const source = sourceApresSaisie(UI.lireFormulaire(formulaire), ligne);
      const saisie = source.source_periodicite === 'saisie';
      provenance.textContent = texteProvenance(source);
      UI.remplir(UI.$('.controles-badge-saisie', encart),
        saisie ? UI.badgeValeur('controles_reglementaires', 'source_periodicite', 'saisie') : '');
      UI.$('.controles-valeur-modifiee', encart).hidden = !saisie;
    }

    function choisir() {
      const ligne = ligneCatalogue(liste.value);
      encart.hidden = !ligne;
      UI.remplir(encart, ligne ? encartHtml(ligne) : '');
      if (!ligne) {
        if (aidePeriodicite) aidePeriodicite.textContent = aideInitiale;
        return;
      }
      const valeurs = valeursDepuisCatalogue(ligne);
      CHAMPS_PRE_REMPLIS.forEach((nom) => {
        const champ = formulaire.querySelector('[name="' + nom + '"]');
        if (champ) champ.value = valeurs[nom];
      });
      if (aidePeriodicite) {
        aidePeriodicite.textContent = valeurs.periodicite_mois ? aideInitiale : I18n.t('controles.catalogue.sans_periodicite_aide');
      }
      actualiserProvenance();
    }

    liste.addEventListener('change', choisir);
    ['input', 'change'].forEach((evenement) => formulaire.addEventListener(evenement, (e) => {
      if (e.target !== liste) actualiserProvenance();
    }));
    return bloc;
  }

  /** « Le catalogue Prévo a été relu le 01/03/2027 : il propose 60 mois (vous avez 48 mois). Rien n'est changé sans
   *  vous. » : un fragment sûr (les textes du catalogue y restent en français). */
  function texteMiseAJour(proposee) {
    const nature = (valeur) => Schema.libelleValeur('controles_reglementaires', 'nature_source', valeur) || '—';
    const propositions = proposee.ecarts.map((ecart) => {
      if (ecart.champ === 'periodicite_mois') {
        return I18n.html('controles.catalogue.propose_periodicite', { propose: ecart.propose ? libelleMois(ecart.propose) : '—',
          actuel: ecart.actuel ? libelleMois(ecart.actuel) : '—' });
      }
      if (ecart.champ === 'texte_reference') {
        return I18n.html('controles.catalogue.propose_reference', { propose: catalogueHtml(ecart.propose || '—'),
          actuel: ecart.actuel || '—' });
      }
      return I18n.html('controles.catalogue.propose_nature_source', { propose: nature(ecart.propose), actuel: nature(ecart.actuel) });
    });
    const valeurs = { propositions: UI.brut(propositions.map(String).join(' ; ')) };
    const reluLe = dateIso(proposee.ligne.relu_le);
    return reluLe ? I18n.html('controles.catalogue.mise_a_jour', Object.assign(valeurs, { date: UI.dateFr(reluLe) }))
      : I18n.html('controles.catalogue.mise_a_jour_sans_date', valeurs);
  }

  async function reprendreCatalogue(controleId, bouton) {
    if (bouton.disabled) return;
    bouton.disabled = true;
    bouton.setAttribute('aria-busy', 'true');
    try {
      const changes = await Controles.appliquerMiseAJourCatalogue(controleId);
      UI.toast(I18n.t(changes.length ? 'controles.catalogue.valeurs_reprises' : 'controles.catalogue.rien_a_reprendre'), 'succes');
      await App.reafficher();
    } catch (erreur) {
      App.signalerErreur(erreur, 'reprise des valeurs du catalogue');
    } finally {
      bouton.disabled = false;
      bouton.removeAttribute('aria-busy');
    }
  }

  /**
   * Source d'un contrôle sur sa fiche (carte de description, carte du formulaire du responsable) : provenance, liens
   * et mention de sa ligne du catalogue, mise à jour proposée (§4.4 : encart et, pour le responsable, « Reprendre ces
   * valeurs », seul moyen de reprendre des valeurs du catalogue), phrase D182 en note. Rend un élément.
   */
  function blocSourceControle(controle, responsable) {
    const ligne = ligneCatalogue(controle.catalogue_id);
    const liens = ligne ? liensHtml(ligne) : '';
    const proposee = miseAJourProposee(controle);
    const bloc = UI.element(UI.html`<div class="controles-source"><dl class="valeurs">
      <dt>${I18n.t('controles.catalogue.provenance')}</dt><dd class="controles-provenance">${texteProvenance(controle)}</dd>
      ${liens ? UI.html`<dt>${I18n.t('controles.catalogue.liens')}</dt><dd>${liens}</dd>` : ''}</dl>
      ${mentionHtml(mentionDuControle(controle))}
      ${proposee ? UI.html`<div class="encadre info controles-mise-a-jour" role="status"><p>${texteMiseAJour(proposee)}</p>
        ${responsable ? UI.html`<button type="button" class="btn btn-secondaire" id="controle-reprendre-catalogue">${UI.icone('valider')}${I18n.t('controles.catalogue.reprendre')}</button>` : ''}</div>` : ''}
      <p class="note controles-principe">${I18n.t('controles.principe.texte')}</p></div>`);
    const bouton = UI.$('#controle-reprendre-catalogue', bloc);
    if (bouton) bouton.addEventListener('click', () => reprendreCatalogue(controle.id, bouton));
    return bloc;
  }

  Object.assign(Controles.interne, { blocCatalogue, blocSourceControle, texteProvenance });

  return {
    // règles pures du catalogue (CONCEPTION-L2-L3 §4.1)
    catalogue, ligneCatalogue, famillesCatalogue, valeursDepuisCatalogue, lireSource, sourceApresSaisie,
    mentionDuControle, miseAJourProposee,
  };
})());
