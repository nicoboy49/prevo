'use strict';
// Equipe : techniciens et habilitations (écran « Équipe », alertes d'accueil ; ARCHITECTURE.md
// §15.8 ; brief §6 « techniciens » et « habilitations », §7 RG8, §9 E1).
//
// Le module est découpé en trois fichiers, chargés dans cet ordre par index.html (§15.1) :
//   equipe-regles.js      CE FICHIER, qui crée l'objet Equipe : règles PURES
//                           1. Constantes et petits outils
//                           2. État d'une habilitation, habilitations qui comptent, à renouveler
//   equipe-ecritures.js   techniciens et habilitations : création, modification, renouvellement
//   equipe-ecrans.js      écrans #/equipe, #/equipe/nouveau, #/equipe/<id>
//
// Les fichiers suivants complètent l'objet : Object.assign(Equipe, (() => { … })()). Une fonction
// dont un autre fichier du module a besoin est rangée dans Equipe.interne (pas une API).
//
// Rappel RG8 (lot 1, Ordres.verifierHabilitation) : une habilitation est valable du jour de son
// obtention au jour de son échéance inclus. Ce fichier ne change pas RG8 : il calcule l'état
// affiché à l'écran et les alertes de l'accueil (échue, ou à renouveler dans les 60 jours).

const Equipe = (() => {

  // ===========================================================================================
  // 1. Constantes et petits outils
  // ===========================================================================================

  /** Statuts d'une habilitation, du plus urgent au moins urgent. */
  const STATUTS_HABILITATION = Object.freeze(['échue', 'à renouveler', 'pas encore valable', 'valide']);

  // Une habilitation est « à renouveler » quand son échéance tombe dans les 60 jours (brief RG8).
  const HORIZON_A_RENOUVELER_JOURS = 60;
  const MILLISECONDES_PAR_JOUR = 86400000;
  const MOTIF_DATE_ISO = /^(\d{4})-(\d{2})-(\d{2})/;

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  function numeroJour(dateIso) {
    const morceaux = MOTIF_DATE_ISO.exec(texte(dateIso));
    if (!morceaux) return null;
    return Date.UTC(Number(morceaux[1]), Number(morceaux[2]) - 1, Number(morceaux[3])) / MILLISECONDES_PAR_JOUR;
  }

  /** La date ISO (10 premiers caractères) si elle existe vraiment, sinon '' (« 2026-13-05 » ou
   *  « 2026-02-30 » ne sont pas des dates : le contrôle passe alors en « date inconnue »). */
  function dateIso(valeur) {
    const date = texte(valeur).slice(0, 10);
    const numero = numeroJour(date);
    if (numero === null) return '';
    const relue = new Date(numero * MILLISECONDES_PAR_JOUR);
    const attendue = relue.getUTCFullYear() + '-' + String(relue.getUTCMonth() + 1).padStart(2, '0')
      + '-' + String(relue.getUTCDate()).padStart(2, '0');
    return attendue === date ? date : '';
  }

  function dateDuJour(aujourdhui) {
    return dateIso(aujourdhui) || Donnees.aujourdhui();
  }

  /** Intitulé comparable : « CACES  r489 » et « caces R489 » sont la même habilitation. */
  function cleIntitule(intitule) {
    return texte(intitule).toLowerCase().replace(/\s+/g, '');
  }

  function estActif(technicien) {
    return texte(technicien.actif) !== '0';
  }

  /** « Moreau Julien » : nom puis prénom (ordre des listes). */
  /** Nom affiché d'un technicien : « Prénom Nom » (lot 4, D78). */
  function nomComplet(technicien) {
    return [texte(technicien.prenom), texte(technicien.nom)].filter(Boolean).join(' ') || texte(technicien.id);
  }

  /** Ordre des techniciens : par nom, puis prénom (l'affichage reste « Prénom Nom »). */
  function ordreDesNoms(a, b) {
    return UI.comparerTextes(texte(a.nom) + ' ' + texte(a.prenom), texte(b.nom) + ' ' + texte(b.prenom))
      || texte(a.id).localeCompare(texte(b.id), 'fr', { numeric: true });
  }

  // ===========================================================================================
  // 2. État d'une habilitation, habilitations qui comptent, à renouveler
  // ===========================================================================================

  /**
   * État d'une habilitation à une date : { statut, joursRestants, sansEcheance }.
   * « pas encore valable » (obtention future), « échue » (échéance passée), « à renouveler »
   * (échéance dans les 60 jours, le jour même compris), « valide » (échéance plus lointaine, ou
   * aucune échéance : sansEcheance vrai). joursRestants : jours avant l'échéance (négatif si
   * échue), null sans échéance.
   */
  function etatHabilitation(habilitation, aujourdhui) {
    const jour = numeroJour(dateDuJour(aujourdhui));
    const obtention = numeroJour(dateIso(habilitation.date_obtention));
    const echeance = numeroJour(dateIso(habilitation.date_echeance));
    // Échéance saisie mais illisible (« 2026-02-30 ») : par prudence, l'habilitation est tenue pour
    // échue (elle apparaît dans « à renouveler »), jamais pour valide sans échéance.
    if (texte(habilitation.date_echeance) && echeance === null) return { statut: 'échue', joursRestants: null, sansEcheance: false, illisible: true };
    const joursRestants = echeance === null ? null : echeance - jour;
    const sansEcheance = echeance === null;
    let statut = 'valide';
    if (obtention !== null && obtention > jour) statut = 'pas encore valable';
    else if (joursRestants !== null && joursRestants < 0) statut = 'échue';
    else if (joursRestants !== null && joursRestants <= HORIZON_A_RENOUVELER_JOURS) statut = 'à renouveler';
    return { statut, joursRestants, sansEcheance };
  }

  /** Vrai si l'habilitation `a` doit compter plutôt que `b` (même intitulé) : échéance la plus
   *  lointaine (vide = sans limite), puis obtention la plus récente, puis identifiant le plus grand. */
  function compteAvant(a, b) {
    // Vide = sans limite (la plus lointaine) ; illisible = la plus faible : une ligne mal saisie ne
    // l'emporte jamais sur un renouvellement lisible.
    const rang = (valeur) => (texte(valeur) ? dateIso(valeur) || '0000-00-00' : '9999-12-31');
    const echeanceA = rang(a.date_echeance);
    const echeanceB = rang(b.date_echeance);
    if (echeanceA !== echeanceB) return echeanceA > echeanceB;
    const obtentionA = dateIso(a.date_obtention);
    const obtentionB = dateIso(b.date_obtention);
    if (obtentionA !== obtentionB) return obtentionA > obtentionB;
    return texte(a.id).localeCompare(texte(b.id), 'fr', { numeric: true }) > 0;
  }

  /**
   * Habilitations qui comptent pour un technicien : pour chaque intitulé (casse et espaces
   * ignorés), la ligne dont l'échéance est la plus lointaine. Un renouvellement ajoute une ligne
   * (l'ancienne reste pour l'historique) : c'est donc la nouvelle qui compte. Triées par intitulé.
   */
  function habilitationsQuiComptent(technicienId) {
    const parIntitule = new Map();
    Donnees.lignes('habilitations')
      .filter((habilitation) => texte(habilitation.technicien_id) === texte(technicienId) && cleIntitule(habilitation.intitule))
      .forEach((habilitation) => {
        const cle = cleIntitule(habilitation.intitule);
        const actuelle = parIntitule.get(cle);
        if (!actuelle || compteAvant(habilitation, actuelle)) parIntitule.set(cle, habilitation);
      });
    return Array.from(parIntitule.values())
      .sort((a, b) => UI.comparerTextes(texte(a.intitule), texte(b.intitule), { sensitivity: 'base' }));
  }

  /**
   * Habilitations à renouveler (compteur de l'accueil) : pour chaque technicien ACTIF, ses
   * habilitations qui comptent dont l'état est « échue » ou « à renouveler ».
   * → [{ technicien, habilitation, etat }], les plus urgentes d'abord (jours restants croissants),
   * puis par nom du technicien et intitulé.
   */
  function aRenouveler(aujourdhui) {
    const jour = dateDuJour(aujourdhui);
    const resultat = [];
    Donnees.lignes('techniciens').filter(estActif).forEach((technicien) => {
      habilitationsQuiComptent(technicien.id).forEach((habilitation) => {
        const etat = etatHabilitation(habilitation, jour);
        if (etat.statut === 'échue' || etat.statut === 'à renouveler') resultat.push({ technicien, habilitation, etat });
      });
    });
    return resultat.sort((a, b) => (a.etat.joursRestants - b.etat.joursRestants)
      || ordreDesNoms(a.technicien, b.technicien)
      || UI.comparerTextes(texte(a.habilitation.intitule), texte(b.habilitation.intitule)));
  }

  // ===========================================================================================
  // 3. Types d'habilitation du catalogue (CS172, CS179) : règles pures, aucun texte affiché
  // ===========================================================================================

  /** Types du catalogue (CatalogueFR.habilitations) ; [] si le catalogue n'est pas chargé. */
  function typesHabilitation() {
    return (typeof CatalogueFR !== 'undefined' && CatalogueFR && Array.isArray(CatalogueFR.habilitations))
      ? CatalogueFR.habilitations : [];
  }

  /** Ligne du catalogue d'identifiant H01 à H15 (casse et espaces ignorés), ou null. */
  function typeHabilitation(id) {
    const cle = texte(id).toUpperCase();
    return (cle && typesHabilitation().find((type) => type.id === cle)) || null;
  }

  // Un type peut être passé comme ligne du catalogue ou comme identifiant.
  function versType(type) {
    return (type && typeof type === 'object') ? type : typeHabilitation(type);
  }

  /** Type d'une habilitation (par son catalogue_id), ou null. */
  function typeDe(habilitation) {
    return habilitation ? typeHabilitation(habilitation.catalogue_id) : null;
  }

  /**
   * Intitulé proposé : la partie du type avant « – » (« CACES R489 »). Vide pour l'électricité :
   * l'intitulé y est le symbole du titre (BR, B2V…), que le catalogue ne peut pas deviner.
   */
  function intitulePropose(type) {
    const ligne = versType(type);
    if (!ligne || ligne.famille === 'Électricité') return '';
    return texte(ligne.type).split('–')[0].trim();
  }

  /** Valeurs proposées à la création d'après un type ; recyclage_mois vide si le type n'en a pas (H14). */
  function valeursDepuisType(type) {
    const ligne = versType(type);
    if (!ligne) return { intitule: '', recyclage_mois: '', catalogue_id: '', nature_source: '' };
    const mois = Number.isInteger(ligne.duree_mois) && ligne.duree_mois > 0 ? ligne.duree_mois : '';
    return { intitule: intitulePropose(ligne), recyclage_mois: mois, catalogue_id: ligne.id, nature_source: texte(ligne.nature_source) };
  }

  /** Échéance proposée = obtention + recyclage (Controles.ajouterMois, cherché à l'appel) ; '' si inconnue. */
  function echeanceProposee(obtention, recyclageMois) {
    const mois = Number(recyclageMois);
    const jour = dateIso(obtention);
    if (!jour || !Number.isInteger(mois) || mois <= 0 || typeof Controles === 'undefined') return '';
    return Controles.ajouterMois(jour, mois);
  }

  /** { propose, egal } : durée du type de l'habilitation et si son recyclage la suit (sans durée de type : rien à comparer). */
  function recyclageDuType(habilitation) {
    const type = typeDe(habilitation);
    const propose = type && Number.isInteger(type.duree_mois) ? type.duree_mois : null;
    if (propose === null) return { propose: null, egal: true };
    return { propose, egal: Number(habilitation.recyclage_mois) === propose };
  }

  /** H14 : l'autorisation de conduite de l'employeur, distincte des CACES. */
  function estAutorisationDeConduite(type) {
    const ligne = versType(type);
    return !!ligne && ligne.id === 'H14';
  }

  /** H06 à H13 : famille CACES. */
  function estCaces(type) {
    const ligne = versType(type);
    return !!ligne && ligne.famille === 'CACES';
  }

  function compteVraiment(habilitation, jour) {
    const statut = etatHabilitation(habilitation, jour).statut;
    return statut === 'valide' || statut === 'à renouveler';
  }

  /**
   * CACES valables d'un technicien (ceux qui comptent) quand aucune autorisation de conduite
   * valable ne les accompagne : rappel CS179. → lignes d'habilitation ([] si une autorisation compte).
   */
  function cacesSansAutorisation(technicienId, aujourdhui) {
    const jour = dateDuJour(aujourdhui);
    const quiComptent = habilitationsQuiComptent(technicienId).filter((h) => compteVraiment(h, jour));
    if (quiComptent.some((h) => estAutorisationDeConduite(typeDe(h)))) return [];
    return quiComptent.filter((h) => estCaces(typeDe(h)));
  }

  /** CACES du technicien qui ont un justificatif (à reprendre pour l'autorisation), le plus récent d'abord. */
  function justificatifsReprenables(technicienId) {
    return Donnees.lignes('habilitations')
      .filter((h) => texte(h.technicien_id) === texte(technicienId) && texte(h.justificatif) && estCaces(typeDe(h)))
      .sort((a, b) => texte(b.date_obtention).localeCompare(texte(a.date_obtention)));
  }

  return {
    STATUTS_HABILITATION,
    // règles pures (ARCHITECTURE.md §15.8)
    etatHabilitation, habilitationsQuiComptent, aRenouveler,
    // types d'habilitation du catalogue (2.2)
    typesHabilitation, typeHabilitation, typeDe, valeursDepuisType, intitulePropose, echeanceProposee,
    recyclageDuType, estAutorisationDeConduite, estCaces, cacesSansAutorisation, justificatifsReprenables,
    // Usage interne au module (pas une API).
    interne: { texte, dateIso, dateDuJour, cleIntitule, estActif, nomComplet },
  };
})();
