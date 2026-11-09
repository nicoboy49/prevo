'use strict';
// Rapport : rapport mensuel figé — une page A4 pour la direction : quatre tuiles comparées au mois
// précédent et à l'année précédente, faits marquants, décisions proposées, trois graphiques, encadré
// « Comprendre » (ARCHITECTURE.md §15.10 ; CDC du lot 3, D43 à D45). 2.2 (D188, CS174) : la 4ᵉ tuile et le
// 2ᵉ Pareto disent le coût de l'arrêt (Indicateurs.coutArret), au centime, jamais estimé.
//
// Le module est découpé en deux fichiers, chargés dans cet ordre par index.html (§15.1) :
//   rapport-contenu.js   CE FICHIER, qui crée l'objet Rapport :
//                          1. Petits outils (mois, formats, tendances)
//                          2. Données du rapport (PURES : Rapport.donnees, moisAProposer, texteCourriel)
//                          3. Page HTML autonome (Rapport.html : sans script ni ressource externe)
//   rapport-ecrans.js    figer (document daté, révisions), onglet « Rapports mensuels », bandeau de l'accueil
//
// Les chiffres viennent des mêmes règles que l'écran Indicateurs (Indicateurs.global sur le mois) :
// le rapport et l'écran disent donc la même chose. Une valeur non calculable est dite, jamais
// remplacée par un chiffre. Le texte venant des données est échappé (UI.html).
// Langue (D156) : le rapport figé est un document enregistré, écrit dans la langue de l'installation (textes, mois,
// nombres, raisons des indicateurs) quelle que soit la langue de l'écran : Rapport.donnees et Rapport.html travaillent
// dans I18n.enLangueDesDonnees. Ce qu'on en montre avant de figer (courriel, commentaire proposé par l'IA) est donc
// ce qui sera enregistré. Exception voulue (T302, D160) : le responsable peut choisir une autre langue déclarée au
// moment de figer (option `langue`, dictionnaire chargé par I18n.chargerLangue) ; la langue de l'installation est proposée.

const Rapport = (() => {

  // ===========================================================================================
  // 1. Petits outils
  // ===========================================================================================

  // Noms des mois dans la langue active, par Intl (I18n.locale : « septembre » en fr-FR, « September » en en-GB) : celle
  // de l'installation dans le rapport (D156), celle de l'écran dans la liste des rapports figés ; lus au moment de
  // l'écriture, jamais figés au chargement (T289 : neuf mois étaient restés en dur).
  function nomsMois() {
    const format = new Intl.DateTimeFormat(I18n.locale, { month: 'long', timeZone: 'UTC' });
    return Array.from({ length: 12 }, (_, index) => format.format(new Date(Date.UTC(2026, index, 1))));
  }
  const COULEURS_SERIES = ['#2F5BD3', '#A86A12', '#6B7280'];     // impression sur blanc : bleu, ocre, gris
  const PREFIXE_FICHIER = 'rapport-mensuel-';
  // Nom enregistré d'un rapport : en mode serveur, le nom demandé précédé de l'horodatage du serveur (audit F4,
  // « AAAAMMJJ-HHMMSS- ») ; en mode dossier ou démo, le nom demandé tel quel. nomDemande() retire ce préfixe.
  const PREFIXE_SERVEUR = /^\d{8}-\d{6}-/;

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  function nomDemande(nom) {
    return texte(nom).replace(PREFIXE_SERVEUR, '');
  }

  /** 'AAAA-MM' + n mois (n négatif possible). */
  function decalerMois(mois, n) {
    const total = Number(mois.slice(0, 4)) * 12 + Number(mois.slice(5, 7)) - 1 + n;
    const annee = Math.floor(total / 12);
    return annee + '-' + String(total - annee * 12 + 1).padStart(2, '0');
  }

  /** '2026-09' → « septembre 2026 ». */
  function libelleMois(mois) {
    return nomsMois()[Number(mois.slice(5, 7)) - 1] + ' ' + mois.slice(0, 4);
  }

  function repere(equipementId) {
    const equipement = Donnees.trouver('equipements', equipementId);
    return equipement ? texte(equipement.repere) || equipement.id : texte(equipementId);
  }

  /** Plus ancienne date de l'historique : la première création d'OT ('' si aucun OT). */
  function debutHistorique() {
    return Donnees.lignes('ordres_travail').reduce((plusAncienne, ot) => {
      const jour = texte(ot.date_creation).slice(0, 10);
      return /^\d{4}-\d{2}-\d{2}$/.test(jour) && (!plusAncienne || jour < plusAncienne) ? jour : plusAncienne;
    }, '');
  }

  /** Le mois est-il couvert par l'historique (il commence au plus tôt le jour du premier OT) ? */
  function estCouvert(mois) {
    const debut = debutHistorique();
    return Boolean(debut) && Indicateurs.periodeDuMois(mois).debut >= debut;
  }

  function pourcentage(valeur) {
    return UI.nombreFr(valeur * 100, 1) + ' %';
  }

  /** Format d'une tuile selon sa nature. */
  function formater(cle, valeur) {
    if (valeur === null || valeur === undefined) return I18n.t('rapport.formater.non_calculable');
    if (cle === 'coutArret') return UI.euro(valeur, 2);                  // au centime (CS174)
    return cle === 'cout' ? UI.euro(valeur, 0) : pourcentage(valeur);
  }

  /**
   * Comparaison d'une valeur à une valeur de référence : { sens, texte } ; sens ∈ 'hausse',
   * 'baisse', 'stable', null (non comparable ou non calculable). Taux : écart en points ; coûts :
   * écart relatif en %.
   */
  function comparer(cle, valeur, reference, comparable, libelleReference) {
    if (!comparable) return { sens: null, texte: I18n.t('rapport.comparer.non_comparable_historique_trop', { libelleReference }) };
    if (valeur === null || reference === null) return { sens: null, texte: I18n.t('rapport.comparer.non_calculable', { libelleReference }) };
    if (cle === 'cout' || cle === 'coutArret') {
      if (reference === 0) {
        return valeur === 0 ? { sens: 'stable', texte: I18n.t('rapport.comparer.stable_rapport', { libelleReference }) }
          : { sens: 'hausse', texte: I18n.t('rapport.comparer.hausse_0', { libelleReference, devise: UI.symboleDevise() }) };
      }
      const ecart = (valeur - reference) / reference * 100;
      if (Math.abs(ecart) < 0.5) return { sens: 'stable', texte: I18n.t('rapport.comparer.stable_rapport', { libelleReference }) };
      return { sens: ecart > 0 ? 'hausse' : 'baisse',
        texte: ecart > 0 ? I18n.t('rapport.comparer.hausse_rapport', { pourcent: UI.nombreFr(Math.abs(ecart), 0), libelleReference })
          : I18n.t('rapport.comparer.baisse_rapport', { pourcent: UI.nombreFr(Math.abs(ecart), 0), libelleReference }) };
    }
    const points = (valeur - reference) * 100;
    if (Math.abs(points) < 0.05) return { sens: 'stable', texte: I18n.t('rapport.comparer.stable_rapport', { libelleReference }) };
    return { sens: points > 0 ? 'hausse' : 'baisse',
      texte: points > 0 ? I18n.t('rapport.comparer.hausse_point_rapport', { n: Math.abs(points), points: UI.nombreFr(Math.abs(points), 1), libelleReference })
        : I18n.t('rapport.comparer.baisse_point_rapport', { n: Math.abs(points), points: UI.nombreFr(Math.abs(points), 1), libelleReference }) };
  }

  // ===========================================================================================
  // 2. Données du rapport (pures)
  // ===========================================================================================

  // Fonction (et non constante) : les libellés sont lus au moment de l'écriture du rapport.
  function tuilesDefinies() {
    return [
      { cle: 'disponibilite', libelle: I18n.t('rapport.tuiles_definies.disponibilite'), hausseFavorable: true, lire: (g) => g.disponibilite },
      { cle: 'cout', libelle: I18n.t('rapport.tuiles_definies.cout_maintenance_mois'), hausseFavorable: false, lire: (g) => g.cout },
      { cle: 'partPreventif', libelle: I18n.t('rapport.tuiles_definies.part_preventif_heures'), hausseFavorable: true, lire: (g) => g.partPreventif },
    ];
  }

  /** Nombre de faits marquants et de décisions du rapport (une page A4). */
  const NOMBRE_FAITS = 3;
  // Rang d'un fait marquant : au-delà de NOMBRE_FAITS, les rangs les plus grands sortent ; ceux qui restent gardent
  // l'ordre d'écriture. Les retards réglementaires (contrôles, réserves) passent avant la répétition des pannes :
  // sans réserve en retard, il n'y a jamais plus de trois faits et le rapport est celui d'avant la 2.2 (T421).
  const RANG_FAIT = { arret: 1, retard: 2, reserves: 3, pannes: 4 };
  /** Longueur du texte d'une réserve citée par une décision (coupé à un blanc, puis « … »). */
  const LONGUEUR_TEXTE_RESERVE = 60;

  /** Contrôles en retard (équipement suivi) à la date `aujourdhui`. */
  function controlesEnRetard(aujourdhui) {
    return Donnees.lignes('controles_reglementaires').filter((controle) => Controles.interne.equipementSuivi(controle) && Controles.etat(controle, aujourdhui).statut === 'en retard');
  }

  /**
   * Fait marquant des réserves en retard (Controles.reservesEnRetard, CS170) : « 3 réserves de contrôle en retard au
   * 31/10/2026 (échéance de levée passée). » ; quand certaines n'ont pas d'échéance saisie (réserves reprises de la
   * 2.1, D183, ou saisies sans échéance), la phrase dit que leur échéance est celle par défaut (30 jours après le
   * contrôle, D187) : elle explique pourquoi elles sont presque toutes en retard au premier lancement de la 2.2.
   */
  function faitReservesEnRetard(reserves, aujourdhui) {
    const parDefaut = reserves.filter((element) => element.etat.parDefaut).length;
    const valeurs = { n: reserves.length, aujourdhui: UI.dateFr(aujourdhui), parDefaut, jours: Controles.interne.DELAI_LEVEE_PAR_DEFAUT_JOURS };
    if (!parDefaut) return I18n.t('rapport.faits_marquants.reserves_retard', valeurs);
    if (parDefaut === reserves.length) return I18n.t('rapport.faits_marquants.reserves_retard_par_defaut', valeurs);
    return I18n.t('rapport.faits_marquants.reserves_retard_dont_par_defaut', valeurs);
  }

  function faitsMarquants(periode, global, aujourdhui) {
    const faits = [];                         // { rang, texte }, dans l'ordre d'écriture
    const pannes = Indicateurs.pannes(periode).filter((panne) => panne.duree !== null);
    if (pannes.length) {
      const longue = pannes.reduce((a, b) => (b.duree > a.duree ? b : a));
      faits.push({ rang: RANG_FAIT.arret, texte: I18n.t('rapport.faits_marquants.plus_long_arret', { repere: repere(longue.ot.equipement_id), duree: UI.heures(longue.duree), otId: longue.ot.id }) });
    }
    const plusSouvent = Indicateurs.paretoPannes(periode, 1)[0];
    if (plusSouvent && plusSouvent.valeur >= 2) {
      faits.push({ rang: RANG_FAIT.pannes, texte: I18n.t('rapport.faits_marquants.pannes_mois', { repere: repere(plusSouvent.equipementId), n: plusSouvent.valeur }) });
    }
    const enRetard = controlesEnRetard(aujourdhui);
    if (enRetard.length) faits.push({ rang: RANG_FAIT.retard, texte: I18n.t('rapport.faits_marquants.controle_reglementaire_retard', { n: enRetard.length, aujourdhui: UI.dateFr(aujourdhui) }) });
    else if (global.otEnRetard.valeur) faits.push({ rang: RANG_FAIT.retard, texte: I18n.t('rapport.faits_marquants.ot_retard', { otEnRetardValeur: global.otEnRetard.valeur, aujourdhui: UI.dateFr(aujourdhui) }) });
    const reserves = Controles.reservesEnRetard(aujourdhui);
    if (reserves.length) faits.push({ rang: RANG_FAIT.reserves, texte: faitReservesEnRetard(reserves, aujourdhui) });
    if (!faits.length) return [I18n.t('rapport.faits_marquants.aucune_panne_arret_production')];
    const gardes = faits.slice().sort((a, b) => a.rang - b.rang).slice(0, NOMBRE_FAITS);
    return faits.filter((fait) => gardes.includes(fait)).map((fait) => fait.texte);
  }

  /** Décision « réparer ou remplacer ? » (D44) : équipement au plus fort ratio coût 12 mois /
   *  valeur de remplacement, s'il dépasse le seuil. Renvoie aussi le nombre d'équipements sans valeur. */
  function reparerOuRemplacer(mois) {
    const seuilLu = Donnees.nombre(Donnees.parametre('seuil_remplacement_pct', '50'));
    const seuil = seuilLu !== null && seuilLu > 0 ? seuilLu : 50;
    const fin = Indicateurs.periodeDuMois(mois).fin;
    const periode12 = { code: 'du-au', debut: Indicateurs.periodeDuMois(decalerMois(mois, -11)).debut, fin, libelle: '' };
    let meilleur = null;
    const sansValeur = [];
    Indicateurs.coutParEquipement(periode12).forEach((element) => {
      const equipement = Donnees.trouver('equipements', element.equipementId);
      // Un équipement déjà au rebut ou désactivé n'est pas à « réparer ou remplacer ».
      if (!equipement || texte(equipement.actif) === '0' || texte(equipement.statut) === 'rebut') return;
      const valeur = Donnees.nombre(equipement.valeur_remplacement);
      if (valeur === null || valeur <= 0) { if (element.valeur > 0) sansValeur.push(element.equipementId); return; }
      const ratio = element.valeur / valeur * 100;
      if (ratio >= seuil && (!meilleur || ratio > meilleur.ratio)) meilleur = { equipementId: element.equipementId, cout: element.valeur, valeur, ratio };
    });
    return { decision: meilleur && (I18n.t('rapport.reparer_ou_remplacer.maintenance_12_mois_soit', { repere: repere(meilleur.equipementId), euro: UI.euro(meilleur.cout, 0), ratio: UI.nombreFr(meilleur.ratio, 0), valeurRemplacement: UI.euro(meilleur.valeur, 0) })),
    sansValeur, seuil };
  }

  /** Texte d'une réserve sur une ligne, coupé à LONGUEUR_TEXTE_RESERVE caractères (au dernier blanc s'il y en a un
   *  dans la seconde moitié), suivi de « … » quand il est coupé. */
  function texteCourtReserve(reserve) {
    const caracteres = Array.from(texte(reserve.texte).replace(/\s+/g, ' '));
    if (caracteres.length <= LONGUEUR_TEXTE_RESERVE) return caracteres.join('');
    let coupe = caracteres.slice(0, LONGUEUR_TEXTE_RESERVE).join('');
    const blanc = coupe.lastIndexOf(' ');
    if (blanc >= LONGUEUR_TEXTE_RESERVE / 2) coupe = coupe.slice(0, blanc);
    return coupe.replace(/[\s,;:.]+$/, '') + I18n.t('rapport.donnees.texte');
  }

  function decisions(mois, aujourdhui, remplacement) {
    const liste = [];
    if (remplacement.decision) liste.push(remplacement.decision);
    const enRetard = controlesEnRetard(aujourdhui);
    if (enRetard.length) {
      const controles = enRetard.slice(0, 3).map((controle) => texte(controle.nature) + ' (' + repere(controle.equipement_id) + ')').join(' ; ');
      liste.push(I18n.t('rapport.decisions.planifier_controles', { n: enRetard.length, liste: controles }));
    }
    // 2.2 (CS170) : « Lever les 3 réserves en retard : <texte court> (<repère>) ; … », les plus anciennes d'abord.
    const reserves = Controles.reservesEnRetard(aujourdhui);
    if (reserves.length) {
      const reservesCitees = reserves.slice(0, 3).map((element) => texteCourtReserve(element.reserve) + ' (' + repere(element.controle.equipement_id) + ')').join(' ; ');
      liste.push(I18n.t('rapport.decisions.lever_reserves', { n: reserves.length, liste: reservesCitees }));
    }
    const aCommander = Magasin.aCommander();
    if (aCommander.length) {
      const critiques = aCommander.filter((element) => texte(element.article.critique) === '1').length;
      liste.push(critiques ? I18n.t('rapport.decisions.commander_articles_dont_critiques', { n: aCommander.length, critiques })
        : I18n.t('rapport.decisions.commander_articles', { n: aCommander.length }));
    }
    return liste.slice(0, NOMBRE_FAITS);
  }

  // Coût de l'arrêt (2.2, D188, CS174) : Indicateurs.coutArret du mois, en centimes entiers. Rien n'est estimé : ce
  // qui manque (équipements sans coût horaire, OT sans durée) est dit sous la valeur et listé dans « Non calculable ».
  /** Repères cités dans « Non calculable » au plus (une page A4) ; la liste complète est à l'écran Indicateurs. */
  const REPERES_NON_CHIFFRES = 8;

  /** Valeur de la tuile en euros ; null (« non chiffré ») quand le mois a des pannes et qu'aucune n'est chiffrée. */
  function valeurCoutArret(calcul) {
    return calcul.parEquipement.length || calcul.complet ? calcul.totalCentimes / 100 : null;
  }

  /** Ce qui manque au calcul : « 1 équipement non chiffré, 1 OT sans durée » ('' quand il est complet). */
  function manqueCoutArret(calcul) {
    const morceaux = [];
    if (calcul.nonChiffres.length) morceaux.push(I18n.t('rapport.cout_arret.equipements_non_chiffres', { n: calcul.nonChiffres.length }));
    if (calcul.sansDuree.length) morceaux.push(I18n.t('rapport.cout_arret.ot_sans_duree', { n: calcul.sansDuree.length }));
    return morceaux.join(', ');
  }

  /** Comparaison de deux coûts de l'arrêt, seulement entre deux mois complets (`reference` null : historique trop court). */
  function comparerCoutArret(calcul, reference, libelleReference) {
    if (!reference) return comparer('coutArret', null, null, false, libelleReference);
    if (!calcul.complet || !reference.complet) {
      return { sens: null, texte: I18n.t('rapport.comparer.non_comparable_cout_incomplet', { libelleReference }) };
    }
    return comparer('coutArret', calcul.totalCentimes / 100, reference.totalCentimes / 100, true, libelleReference);
  }

  /** 4ᵉ tuile : même forme que les trois autres ; `precision` (sous la valeur) dit « Partiel : … » ou « aucun arrêt ». */
  function tuileCoutArret(calcul, precedent, annee, libellePrecedent, libelleAnnee) {
    const valeur = valeurCoutArret(calcul);
    const manque = manqueCoutArret(calcul);
    let precision = manque;                       // « non chiffré » : ce qui manque ; complet sans panne : aucun arrêt
    if (valeur !== null) {
      precision = calcul.parEquipement.length ? (manque && I18n.t('rapport.cout_arret.partiel', { manque })) : I18n.t('rapport.cout_arret.aucun_arret');
    }
    return {
      cle: 'coutArret', libelle: I18n.t('rapport.tuiles_definies.cout_arret'), hausseFavorable: false,
      valeur, raison: valeur === null ? manque : '', precision,
      texteValeur: valeur === null ? I18n.t('rapport.cout_arret.non_chiffre') : formater('coutArret', valeur),
      precedent: precedent ? valeurCoutArret(precedent) : null, anneePrecedente: annee ? valeurCoutArret(annee) : null,
      tendance: { precedent: comparerCoutArret(calcul, precedent, libellePrecedent), annee: comparerCoutArret(calcul, annee, libelleAnnee) },
    };
  }

  /** Entrée « Non calculable » du coût de l'arrêt (null s'il est complet) : « Coût de l'arrêt — non chiffré : PR-02 (6,5 h
   *  d'arrêt), CU-01 (2 h) ; OT sans durée : OT-2026-0042 (CP-01, non clôturé) », REPERES_NON_CHIFFRES repères au plus. */
  function nonCalculableCoutArret(calcul) {
    if (calcul.complet) return null;
    const equipements = calcul.nonChiffres.slice(0, REPERES_NON_CHIFFRES).map((ligne, rang) => I18n.t(rang
      ? 'rapport.cout_arret.repere_heures' : 'rapport.cout_arret.repere_heures_arret', { repere: repere(ligne.equipementId), duree: UI.heures(ligne.heures) }));
    const ots = calcul.sansDuree.slice(0, REPERES_NON_CHIFFRES - equipements.length)
      .map((ligne) => I18n.t('rapport.cout_arret.ot_repere_raison', { otId: ligne.otId, repere: repere(ligne.equipementId), raison: ligne.raison }));
    let raison = equipements.length && ots.length
      ? I18n.t('rapport.cout_arret.non_chiffres_et_sans_duree', { nonChiffres: equipements.join(', '), sansDuree: ots.join(', ') })
      : equipements.concat(ots).join(', ');
    const autres = calcul.nonChiffres.length + calcul.sansDuree.length - equipements.length - ots.length;
    if (autres > 0) raison = I18n.t('rapport.cout_arret.liste_et_autres', { liste: raison, n: autres });
    return { libelle: I18n.t(calcul.nonChiffres.length ? 'rapport.cout_arret.titre_non_chiffre' : 'rapport.cout_arret.titre_sans_duree'), raison };
  }

  /**
   * Données du rapport d'un mois 'AAAA-MM', calculées à la date `aujourdhui` (date de génération,
   * qui sert aux retards) : { mois, libelleMois, genereLe, entreprise, tuiles, faits, decisions,
   * pareto, paretoCout, heures12Mois, coutArret, nonCalculables, comprendre, courriel } ; coutArret :
   * Indicateurs.coutArret du mois, plus `tendance` (celle de la 4ᵉ tuile). Dans la langue de l'installation (D156), ou dans
   * `langue` (code déclaré dont le dictionnaire est chargé : celle choisie pour le rapport, T302).
   */
  function donnees(mois, aujourdhui, maintenant, langue) {
    return enLangueDuRapport(langue, () => donneesDuMois(mois, aujourdhui, maintenant));
  }

  /** `fonction` dans la langue choisie du rapport, à défaut dans celle de l'installation. */
  function enLangueDuRapport(langue, fonction) {
    return langue ? I18n.enLangue(langue, fonction) : I18n.enLangueDesDonnees(fonction);
  }

  function donneesDuMois(mois, aujourdhui, maintenant) {
    const jour = /^\d{4}-\d{2}-\d{2}$/.test(texte(aujourdhui).slice(0, 10)) ? texte(aujourdhui).slice(0, 10) : Donnees.aujourdhui();
    const periode = Indicateurs.periodeDuMois(mois);
    const global = Indicateurs.global(periode, {}, jour);
    const precedent = decalerMois(mois, -1);
    const anneePrecedente = decalerMois(mois, -12);
    const globalPrecedent = estCouvert(precedent) ? Indicateurs.global(Indicateurs.periodeDuMois(precedent), {}, jour) : null;
    const globalAnnee = estCouvert(anneePrecedente) ? Indicateurs.global(Indicateurs.periodeDuMois(anneePrecedente), {}, jour) : null;
    const tuiles = tuilesDefinies().map((tuile) => {
      const resultat = tuile.lire(global);
      const valeurPrecedente = globalPrecedent ? tuile.lire(globalPrecedent).valeur : null;
      const valeurAnnee = globalAnnee ? tuile.lire(globalAnnee).valeur : null;
      return {
        cle: tuile.cle, libelle: tuile.libelle, hausseFavorable: tuile.hausseFavorable,
        valeur: resultat.valeur, raison: resultat.raison, precision: resultat.valeur === null ? resultat.raison : '',
        texteValeur: formater(tuile.cle, resultat.valeur),
        precedent: valeurPrecedente, anneePrecedente: valeurAnnee,
        tendance: {
          precedent: comparer(tuile.cle, resultat.valeur, valeurPrecedente, Boolean(globalPrecedent), libelleMois(precedent)),
          annee: comparer(tuile.cle, resultat.valeur, valeurAnnee, Boolean(globalAnnee), libelleMois(anneePrecedente)),
        },
      };
    });
    const nonCalculables = tuiles.filter((tuile) => tuile.valeur === null).map((tuile) => ({ libelle: tuile.libelle, raison: tuile.raison }));
    // Coût de l'arrêt du mois, comparé aux mois couverts par l'historique (mêmes règles que les trois autres tuiles).
    const coutArret = Indicateurs.coutArret(periode);
    const tuileArret = tuileCoutArret(coutArret,
      globalPrecedent ? Indicateurs.coutArret(Indicateurs.periodeDuMois(precedent)) : null,
      globalAnnee ? Indicateurs.coutArret(Indicateurs.periodeDuMois(anneePrecedente)) : null,
      libelleMois(precedent), libelleMois(anneePrecedente));
    tuiles.push(tuileArret);
    const remplacement = reparerOuRemplacer(mois);
    if (global.tempsRequis.exclus.length) {
      nonCalculables.push({ libelle: I18n.t('rapport.donnees.equipements_hors_disponibilite'), raison: I18n.t('rapport.donnees.equipement_sans_heures_fonctionnement', { n: global.tempsRequis.exclus.length, reperes: global.tempsRequis.exclus.slice(0, 6).map((element) => repere(element.id)).join(', ') }) + (global.tempsRequis.exclus.length > 6 ? I18n.t('rapport.donnees.texte') : '') });
    }
    if (remplacement.sansValeur.length) {
      nonCalculables.push({ libelle: I18n.t('rapport.donnees.reparer_remplacer'), raison: I18n.t('rapport.donnees.valeur_remplacement_non_renseignee', { n: remplacement.sansValeur.length, reperes: remplacement.sansValeur.slice(0, 6).map(repere).join(', ') }) });
    }
    const manqueArret = nonCalculableCoutArret(coutArret);
    if (manqueArret) nonCalculables.push(manqueArret);
    const resultat = {
      mois, libelleMois: libelleMois(mois), genereLe: texte(maintenant) || Donnees.maintenant(),
      entreprise: texte(Donnees.parametre('entreprise_nom', '')),
      tuiles, faits: faitsMarquants(periode, global, jour), decisions: decisions(mois, jour, remplacement),
      pareto: Indicateurs.paretoArrets(periode, 5).map((ligne) => ({ repere: repere(ligne.equipementId), heures: ligne.valeur })),
      paretoCout: Indicateurs.paretoCoutArret(periode, 5).map((ligne) => ({ repere: repere(ligne.equipementId), centimes: ligne.centimes, valeur: ligne.valeur })),
      heures12Mois: Indicateurs.heuresParMois(mois, 12),
      coutArret: Object.assign({}, coutArret, { tendance: tuileArret.tendance }),
      mttr: global.mttr, attentePieces: global.attentePieces, seuilRemplacement: remplacement.seuil,
      nonCalculables,
      comprendre: [
        [I18n.t('rapport.tuiles_definies.disponibilite'), I18n.t('rapport.donnees.mtbf_mtbf_mttr_part')],
        [I18n.t('rapport.donnees.panne'), I18n.t('rapport.donnees.ot_correctif_arret_production')],
        ['MTTR', I18n.t('rapport.donnees.duree_arret_moyenne_panne')],
        [I18n.t('rapport.donnees.cout'), I18n.t('rapport.donnees.heures_taux_horaire_pieces')],
        [I18n.t('rapport.tuiles_definies.cout_arret'), I18n.t('rapport.donnees.cout_arret_formule')],
        [I18n.t('rapport.donnees.part_preventif'), I18n.t('rapport.donnees.heures_passees_ot_preventifs')],
        [I18n.t('rapport.donnees.reparer_remplacer'), I18n.t('rapport.donnees.cout_maintenance_12_derniers', { seuil: UI.nombreFr(remplacement.seuil, 0) })],
      ],
    };
    resultat.courriel = texteCourriel(resultat);
    return resultat;
  }

  /** Mois à proposer de figer : le mois précédent, s'il n'est pas déjà figé et que l'historique le couvre. */
  function moisAProposer(aujourdhui) {
    const jour = /^\d{4}-\d{2}-\d{2}$/.test(texte(aujourdhui).slice(0, 10)) ? texte(aujourdhui).slice(0, 10) : Donnees.aujourdhui();
    const mois = decalerMois(jour.slice(0, 7), -1);
    if (rapportsFiges().some((nom) => nomDemande(nom).startsWith(PREFIXE_FICHIER + mois))) return null;
    return estCouvert(mois) ? mois : null;
  }

  /** Noms des rapports figés (paramètre rapports_mensuels), du plus ancien au plus récent. */
  function rapportsFiges() {
    return texte(Donnees.parametre('rapports_mensuels', '')).split(',').map(texte).filter(Boolean);
  }

  /** Objet et corps d'un courriel de résumé (texte simple, moins de 1 800 caractères). */
  function texteCourriel(rapport) {
    const lignes = [rapport.entreprise ? I18n.t('rapport.texte_courriel.rapport_mensuel_maintenance', { libelleMois: rapport.libelleMois, entreprise: rapport.entreprise })
      : I18n.t('rapport.texte_courriel.rapport_mensuel_maintenance_2', { libelleMois: rapport.libelleMois }), ''];
    // Le coût de l'arrêt dit ce qui lui manque (« Partiel : … », D188) ; les trois autres tuiles, comme avant la 2.2.
    rapport.tuiles.forEach((tuile) => lignes.push('• ' + tuile.libelle + ' : ' + (tuile.cle === 'coutArret' && tuile.precision
      ? I18n.t('rapport.texte_courriel.valeur_precision', { valeur: tuile.texteValeur, precision: tuile.precision }) : tuile.texteValeur)
      + ' (' + tuile.tendance.precedent.texte + ')'));
    lignes.push('', I18n.t('rapport.texte_courriel.faits_marquants'));
    rapport.faits.forEach((fait) => lignes.push('• ' + fait));
    if (rapport.decisions.length) {
      lignes.push('', I18n.t('rapport.texte_courriel.decisions_proposees'));
      rapport.decisions.forEach((decision) => lignes.push('• ' + decision));
    }
    lignes.push('', I18n.t('rapport.texte_courriel.rapport_complet_page_prevo'));
    let corps = lignes.join('\r\n');      // RFC 6068 : fins de ligne CRLF (%0D%0A)
    if (corps.length > 1800) corps = I18n.t('rapport.texte_courriel.slice', { slice: corps.slice(0, 1790) });
    return { objet: I18n.t('rapport.texte_courriel.rapport_maintenance', { libelleMois: rapport.libelleMois }), corps };
  }

  /** Lien mailto: (RFC 6068) : rien n'est envoyé par Prévo, la messagerie du poste s'ouvre. */
  function lienCourriel(rapport) {
    return 'mailto:?subject=' + encodeURIComponent(rapport.courriel.objet) + '&body=' + encodeURIComponent(rapport.courriel.corps);
  }

  // ===========================================================================================
  // 3. Page HTML autonome (une page A4, sans script ni ressource externe)
  // ===========================================================================================

  /** Étiquette sûre pour un graphique (le SVG est inséré tel quel) : sans < > & ". */
  function etiquette(valeur) {
    return texte(valeur).replace(/[<>&"]/g, ' ');
  }

  /** Graphique ECharts rendu en SVG hors écran (rien n'est ajouté à la page). */
  function svg(lib, largeur, hauteur, option) {
    const graphique = lib.init(null, null, { renderer: 'svg', ssr: true, width: largeur, height: hauteur });
    graphique.setOption(Object.assign({ animation: false, textStyle: { fontFamily: I18n.t('rapport.svg.arial_helvetica_sans_serif'), fontSize: 11, color: '#222' } }, option));
    const dessin = graphique.renderToSVGString();
    graphique.dispose();
    return dessin;
  }

  // Trois graphiques côte à côte (2.2) : dessinés à la largeur d'une colonne de la page A4 (186 mm, deux intervalles de
  // 10 px), donc imprimés à leur taille, sans réduction du texte.
  const LARGEUR_GRAPHIQUE = 226;
  const HAUTEUR_GRAPHIQUE = 150;

  function graphiques(lib, rapport) {
    const pareto = rapport.pareto.length ? svg(lib, LARGEUR_GRAPHIQUE, HAUTEUR_GRAPHIQUE, {
      grid: { left: 62, right: 34, top: 10, bottom: 30 },
      xAxis: { type: 'value', name: 'h', axisLabel: { color: '#333', formatter: (valeur) => UI.nombreFr(valeur) } },
      yAxis: { type: 'category', inverse: true, data: rapport.pareto.map((ligne) => etiquette(ligne.repere)), axisLabel: { color: '#333' } },
      series: [{ type: 'bar', barMaxWidth: 24, data: rapport.pareto.map((ligne) => Math.round(ligne.heures * 10) / 10), itemStyle: { color: COULEURS_SERIES[0] },
        label: { show: true, position: 'right', color: '#222', formatter: (point) => UI.nombreFr(point.value, 1) } }],
    }) : '';
    // Coût de l'arrêt : montants au centime sur les barres (leur somme est la tuile quand il y a cinq équipements au plus).
    const cout = rapport.paretoCout.length ? svg(lib, LARGEUR_GRAPHIQUE, HAUTEUR_GRAPHIQUE, {
      grid: { left: 62, right: 76, top: 10, bottom: 10 },
      xAxis: { type: 'value', axisLabel: { show: false }, splitLine: { show: false } },
      yAxis: { type: 'category', inverse: true, data: rapport.paretoCout.map((ligne) => etiquette(ligne.repere)), axisLabel: { color: '#333' } },
      series: [{ type: 'bar', barMaxWidth: 24, data: rapport.paretoCout.map((ligne) => ligne.valeur), itemStyle: { color: COULEURS_SERIES[0] },
        label: { show: true, position: 'right', color: '#222', formatter: (point) => etiquette(UI.euro(point.value, 2)) } }],
    }) : '';
    const heures = svg(lib, LARGEUR_GRAPHIQUE, HAUTEUR_GRAPHIQUE, {
      grid: { left: 40, right: 10, top: 30, bottom: 30 },
      legend: { top: 0, textStyle: { color: '#222' } },
      xAxis: { type: 'category', data: rapport.heures12Mois.map((element) => element.mois.slice(5, 7) + '/' + element.mois.slice(2, 4)), axisLabel: { color: '#333' } },
      yAxis: { type: 'value', name: 'h', axisLabel: { color: '#333', formatter: (valeur) => UI.nombreFr(valeur) } },
      series: [
        // Mêmes couleurs que l'écran Indicateurs : correctif bleu, préventif ocre.
        { name: 'Correctif', type: 'bar', data: rapport.heures12Mois.map((element) => element.correctif), itemStyle: { color: COULEURS_SERIES[0] } },
        { name: I18n.t('rapport.graphiques.preventif'), type: 'bar', data: rapport.heures12Mois.map((element) => element.preventif), itemStyle: { color: COULEURS_SERIES[1] } },
      ],
    });
    return { pareto, cout, heures };
  }

  /** Feu d'une tendance : forme ET texte (jamais la couleur seule). */
  function feu(tuile, tendance) {
    if (!tendance.sens) return UI.html`<span class="feu neutre">○ ${tendance.texte}</span>`;
    if (tendance.sens === 'stable') return UI.html`<span class="feu neutre">■ ${tendance.texte}</span>`;
    const favorable = (tendance.sens === 'hausse') === tuile.hausseFavorable;
    return UI.html`<span class="feu ${favorable ? 'bon' : 'mauvais'}">${tendance.sens === 'hausse' ? '▲' : '▼'} ${tendance.texte}${favorable ? '' : ' ' + I18n.t('rapport.feu.surveiller')}</span>`;
  }

  const STYLE = `@page { size: A4; margin: 11mm 12mm; }
* { box-sizing: border-box; }
body { margin: 0; color: #111; background: #fff; font: 9.5pt/1.35 "Segoe UI", Arial, Helvetica, sans-serif; }
.page { max-width: 186mm; margin: 0 auto; }
header { border-bottom: 2px solid #111; padding-bottom: 4px; margin-bottom: 8px; }
h1 { font-size: 15pt; margin: 0; } h2 { font-size: 10.5pt; margin: 0 0 4px; }
.sous { margin: 2px 0 0; color: #333; }
.tuiles { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-bottom: 8px; }
.tuile { border: 1px solid #888; border-radius: 6px; padding: 5px 7px; min-width: 0; line-height: 1.25; }
.tuile .lib { font-weight: 600; } .tuile .val { font-size: 15pt; font-weight: 700; margin: 2px 0; overflow-wrap: anywhere; }
.tuile .raison { font-size: 8pt; color: #333; }
.feu { display: block; font-size: 8pt; } .feu.bon { color: #14532d; } .feu.mauvais { color: #7f1d1d; font-weight: 600; } .feu.neutre { color: #333; }
.colonnes { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 8px; }
ul, ol { margin: 0; padding-left: 16px; } li { margin: 0 0 2px; }
figure { margin: 0; } figcaption { font-weight: 600; margin-bottom: 2px; }
.graphiques { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 8px; }
.graphiques figure { min-width: 0; }
.graphiques svg { width: 100%; height: auto; }
.comprendre { border: 1px solid #888; border-radius: 6px; padding: 6px 8px; margin-bottom: 6px; font-size: 8.5pt; line-height: 1.25; }
.comprendre dt { font-weight: 600; display: inline; } .comprendre dd { display: inline; margin: 0; } .comprendre div { margin-bottom: 1px; }
.non-calculable { font-size: 8.5pt; color: #333; line-height: 1.25; }
.commentaire { border-left: 3px solid #555; padding: 2px 0 2px 8px; margin-bottom: 8px; }
.commentaire p { margin: 0 0 2px; white-space: pre-line; } .commentaire .mention-ia { font-size: 8pt; font-style: italic; color: #444; }
.pied { font-size: 8pt; color: #444; margin-top: 4px; }
@media print { .sans-impression { display: none; } }`;

  /**
   * Page HTML autonome du rapport d'un mois (texte). Charge ECharts à la demande pour dessiner les
   * graphiques en SVG intégré ; aucune balise <script>, aucune ressource externe (seul le lien
   * mailto: de la préparation du courriel est un lien).
   */
  async function html(mois, options) {
    const reglages = options || {};
    const rapport = reglages.donnees || donnees(mois, reglages.aujourdhui, reglages.maintenant, reglages.langue);
    const lib = await App.chargerEcharts();
    return enLangueDuRapport(reglages.langue, () => pageDuRapport(rapport, reglages, lib));        // document enregistré (D156)
  }

  function pageDuRapport(rapport, reglages, lib) {
    // Lot 4 (§17.5) : commentaire du responsable, éventuellement proposé par l'IA (mention alors imprimée).
    const commentaire = reglages.commentaire && texte(reglages.commentaire.texte) ? reglages.commentaire : null;
    const dessins = graphiques(lib, rapport);
    const titre = I18n.t('rapport.texte_courriel.rapport_mensuel_maintenance_2', { libelleMois: rapport.libelleMois });
    const mttr = rapport.mttr.valeur === null ? '' : UI.html`<p class="pied">${I18n.html('rapport.html.mttr_v1', { duree: UI.heures(Math.round(rapport.mttr.valeur * 10) / 10) })}${rapport.attentePieces.valeur === null ? ''
      : UI.html`${I18n.html('rapport.html.dont_attente_pieces_panne', { n: rapport.attentePieces.effectif, duree: UI.heures(Math.round(rapport.attentePieces.valeur * 10) / 10) })}`}.</p>`;
    const page = UI.html`<!doctype html>
<html lang="${I18n.langue}"><head><meta charset="utf-8"><title>${rapport.entreprise ? titre + ' — ' + rapport.entreprise : titre}</title>
<style>${UI.brut(STYLE)}</style></head>
<body><main class="page">
<header><h1>${titre}</h1>
<p class="sous">${rapport.entreprise ? UI.html`${I18n.html('rapport.html.donnees_rapport_fige_prevo', { entreprise: rapport.entreprise, genereLe: UI.dateHeureFr(rapport.genereLe) })}`
  : UI.html`${I18n.html('rapport.html.donnees_rapport_fige_prevo_2', { genereLe: UI.dateHeureFr(rapport.genereLe) })}`}</p></header>
<section class="tuiles">${rapport.tuiles.map((tuile) => UI.html`<div class="tuile" data-cle="${tuile.cle}">
  <div class="lib">${tuile.libelle}</div><div class="val">${tuile.texteValeur}</div>
  ${tuile.precision ? UI.html`<div class="raison">${tuile.precision}</div>` : ''}
  ${feu(tuile, tuile.tendance.precedent)}${feu(tuile, tuile.tendance.annee)}</div>`)}</section>
<section class="colonnes"><div><h2>${I18n.html('rapport.html.faits_marquants')}</h2><ul>${rapport.faits.map((fait) => UI.html`<li>${fait}</li>`)}</ul></div>
<div><h2>${I18n.html('rapport.html.decisions_prendre')}</h2>${rapport.decisions.length ? UI.html`<ol>${rapport.decisions.map((decision) => UI.html`<li>${decision}</li>`)}</ol>`
    : UI.html`<p>${I18n.html('rapport.html.aucune_decision_urgente_mois')}</p>`}</div></section>
${commentaire ? UI.html`<section class="commentaire"><h2>${I18n.html('rapport.html.commentaire')}</h2><p>${texte(commentaire.texte)}</p>${commentaire.aideIa
    ? UI.html`<p class="mention-ia">${I18n.html('rapport.html.commentaire_redige_aide_ia')}</p>` : ''}</section>` : ''}
<section class="graphiques">
<figure><figcaption>${I18n.html('rapport.html.duree_arret_mois_equipement')}</figcaption>${dessins.pareto ? UI.brut(dessins.pareto) : UI.html`<p>${I18n.html('rapport.html.aucun_arret_mois_ci')}</p>`}</figure>
<figure><figcaption>${I18n.html('rapport.html.cout_arret_mois_equipement', { devise: UI.symboleDevise() })}</figcaption>${dessins.cout ? UI.brut(dessins.cout)
    : UI.html`<p>${rapport.coutArret.complet && !rapport.coutArret.parEquipement.length ? I18n.html('rapport.html.aucun_arret_mois_ci')
      : I18n.html('rapport.html.aucun_cout_arret_chiffre')}</p>`}</figure>
<figure><figcaption>${I18n.html('rapport.html.heures_correctif_preventif_12')}</figcaption>${UI.brut(dessins.heures)}</figure>
</section>
${mttr}
<section class="comprendre"><h2>${I18n.html('rapport.html.comprendre')}</h2><dl>${rapport.comprendre.map(([terme, definition]) => UI.html`<div><dt>${terme} :</dt> <dd>${definition}</dd></div>`)}</dl></section>
${rapport.nonCalculables.length ? UI.html`<section class="non-calculable"><h2>${I18n.html('rapport.html.non_calculable')}</h2><ul>${rapport.nonCalculables.map((element) => UI.html`<li><b>${element.libelle}</b> : ${element.raison}</li>`)}</ul></section>` : ''}
<p class="pied sans-impression">${I18n.html('rapport.html.lien_courriel', { adresse: lienCourriel(rapport) })}</p>
</main></body></html>`;
    return String(page);
  }

  /**
   * Lot 4 (§17.3, D71) : jetons du commentaire proposé par l'IA — les chiffres du rapport, sous un
   * nom ; l'IA écrit {disponibilite}, Prévo remplace par la valeur affichée (« 92,4 % »).
   */
  function jetonsCommentaire(rapport) {
    const noms = { disponibilite: 'disponibilite', cout: 'cout_du_mois', partPreventif: 'part_preventif' };
    const jetons = {};
    rapport.tuiles.forEach((tuile) => {
      if (tuile.valeur === null || !noms[tuile.cle]) return;
      jetons[noms[tuile.cle]] = tuile.texteValeur;
      jetons[noms[tuile.cle] + '_evolution'] = tuile.tendance.precedent.texte;
    });
    return jetons;
  }

  return {
    PREFIXE_FICHIER,
    // pures (ARCHITECTURE.md §15.10)
    donnees, moisAProposer, texteCourriel, rapportsFiges, jetonsCommentaire,
    html,
    // Usage interne au module (pas une API).
    interne: { enLangueDuRapport, texte, nomDemande, decalerMois, libelleMois, lienCourriel, estCouvert, debutHistorique },
  };
})();
