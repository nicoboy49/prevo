'use strict';
// Controles — catalogue des contrôles réglementaires à l'écran (2.2, lot L2, CS171 ; window.CatalogueFR de
// js/catalogue/fr.js, gelé, en lecture seule : aucune fonction de Prévo ne l'écrit).
//   1. Règles pures du catalogue (T414, CONCEPTION-L2-L3 §4.1) : catalogue, ligneCatalogue, famillesCatalogue,
//      valeursDepuisCatalogue, lireSource, sourceApresSaisie, mentionDuControle, miseAJourProposee. Sans
//      CatalogueFR (page de test sans le fichier, catalogue retiré un jour), liste vide : l'écran retombe sur la
//      saisie libre, sans erreur. Une mise à jour du catalogue n'est JAMAIS appliquée par ces fonctions : elle est
//      seulement proposée (miseAJourProposee), reprise sur un clic par appliquerMiseAJourCatalogue (T415).
//   2. Bloc du catalogue du formulaire de création (Controles.interne.blocCatalogue) : T416.
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

  return {
    // règles pures du catalogue (CONCEPTION-L2-L3 §4.1)
    catalogue, ligneCatalogue, famillesCatalogue, valeursDepuisCatalogue, lireSource, sourceApresSaisie,
    mentionDuControle, miseAJourProposee,
  };
})());
