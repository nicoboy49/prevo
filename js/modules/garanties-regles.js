'use strict';
// Garanties : garanties des équipements et contrats de prestataires (2.2, lot L4 ; CDC §3.4, D187, D190, CS173).
// Prévo rappelle la fin d'une garantie et la date limite de résiliation d'un contrat, et garde leurs documents ; il
// est une aide au suivi, la responsabilité reste celle de l'employeur (D182).
//
// Données (format 4 ; les noms font foi dans js/schema.js) :
//   garanties              GAR-0001 : equipement_id, fournisseur_id, date_debut, date_fin, conditions, document, actif
//   contrats_prestataires  CTP-0001 : fournisseur_id, objet, equipement_ids (identifiants séparés par « ; »),
//                          perimetre, date_debut, date_fin, preavis_mois, reconduction_tacite, reconduction_mois,
//                          montant_annuel (hors taxes), document, actif
//   parametres             réglage alerte_echeances_jours (un seul pour les deux tables, D187)
// Une ligne n'est jamais supprimée : « Retirer » met actif à 0.
//
// Le module est découpé en fichiers chargés dans cet ordre par index.html (§15.1), juste après le module Controles :
//   garanties-regles.js       CE FICHIER, qui crée l'objet Garanties : règles PURES (T451)
//                               1. Constantes et petits outils (textes, dates ISO, délai d'alerte, montants)
//                               2. Garanties : état, sous garantie, garanties d'un équipement
//                               3. Contrats : date limite de résiliation, état, équipements, reconduction proposée,
//                                  total des montants
//                               4. Échéances (accueil, compteurs de l'écran)
//                               5. Vérification des valeurs saisies ou importées, avertissements
//   garanties-ecritures.js    créer, modifier, retirer, reconduire, noter la résiliation, document joint (T452)
//   garanties-formulaires.js  formulaires d'une garantie et d'un contrat (T455)
//   garanties-ecrans.js       écran #/garanties (onglets, compteurs, filtres), fiches, routes et menu (T456)
//   garanties-encarts.js      encarts des autres écrans : carte et badge de la fiche équipement, rappel à la création
//                               d'un OT correctif (T457)
// Feuille : css/modules/garanties.css. Domaine des textes : section « garanties » de js/i18n/<langue>.js.
//
// Les fichiers suivants complètent l'objet : Object.assign(Garanties, (() => { … })()). Une fonction dont un autre
// fichier du module a besoin est rangée dans Garanties.interne (usage interne au module : ce n'est pas une API) ; une
// fonction d'un fichier chargé plus tard est cherchée au moment de l'appel. Un autre module n'appelle Garanties que
// derrière typeof Garanties !== 'undefined' (les pages de test et outils/wiki_demo.py ne chargent pas tout).
//
// Les fonctions de ce fichier sont PURES : elles lisent Donnees, n'écrivent jamais. Les dates sont des chaînes ISO
// 'AAAA-MM-JJ', calculées en UTC ; la date du jour est passée en argument (par défaut Donnees.aujourdhui()). L'ajout
// de mois est celui des contrôles (Controles.ajouterMois, chargé avant ce module : une seule règle des fins de mois).

const Garanties = (() => {

  // ===========================================================================================
  // 1. Constantes et petits outils
  // ===========================================================================================

  /** Statuts calculés d'une garantie, dans l'ordre de priorité : le premier vrai est le statut (conception §2.2).
   *  Des codes, jamais affichés tels quels : le libellé est garanties.statut.<code> (libelleStatut). */
  const STATUTS_GARANTIE = Object.freeze(['fin_inconnue', 'a_venir', 'terminee', 'bientot', 'en_cours']);
  /** Statuts calculés d'un contrat, dans l'ordre de priorité (conception §2.2, QUESTIONS L4-L6 Q1 et Q3). */
  const STATUTS_CONTRAT = Object.freeze(['fin_inconnue', 'a_decider', 'a_mettre_a_jour', 'bientot',
    'preavis_depasse', 'termine', 'en_cours']);
  const [FIN_INCONNUE, A_VENIR, TERMINEE, BIENTOT, EN_COURS] = STATUTS_GARANTIE;
  const [, A_DECIDER, A_METTRE_A_JOUR, , PREAVIS_DEPASSE, TERMINE] = STATUTS_CONTRAT;
  // Contrats comptés au total des montants : ceux dont la prestation continue. « Dates à mettre à jour » en est : le
  // contrat reconduit tacitement continue (conception §2.2, statut 3), et il passe « à décider » quand la date limite
  // de sa période calculée approche (Q3) : l'exclure ferait entrer et sortir le même contrat du total.
  const STATUTS_AU_TOTAL = Object.freeze([EN_COURS, A_DECIDER, A_METTRE_A_JOUR, BIENTOT, PREAVIS_DEPASSE]);

  /** Réglage du délai d'alerte (parametres.csv), en jours, pour les garanties et les contrats (D187). */
  const PARAMETRE_DELAI = 'alerte_echeances_jours';
  const DELAI_PAR_DEFAUT_JOURS = 60;
  const DELAI_MIN_JOURS = 1;
  const DELAI_MAX_JOURS = 365;
  // Reconduction proposée quand ni la durée d'une reconduction ni celle de la période ne sont connues.
  const RECONDUCTION_PAR_DEFAUT_MOIS = 12;
  const MILLISECONDES_PAR_JOUR = 86400000;
  const MOTIF_DATE_ISO = /^(\d{4})-(\d{2})-(\d{2})$/;
  const MOTIF_MONTANT = /^(\d+)(?:\.(\d*))?$/;
  const SEPARATEURS_EQUIPEMENTS = /[\s,;]+/;

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  function deuxChiffres(nombre) {
    return String(nombre).padStart(2, '0');
  }

  /** 'AAAA-MM-JJ' → numéro du jour depuis le 01/01/1970 (UTC), ou null. */
  function numeroJour(date) {
    const morceaux = MOTIF_DATE_ISO.exec(date);
    if (!morceaux) return null;
    return Date.UTC(Number(morceaux[1]), Number(morceaux[2]) - 1, Number(morceaux[3])) / MILLISECONDES_PAR_JOUR;
  }

  function dateDepuisNumero(numero) {
    const date = new Date(numero * MILLISECONDES_PAR_JOUR);
    return date.getUTCFullYear() + '-' + deuxChiffres(date.getUTCMonth() + 1) + '-' + deuxChiffres(date.getUTCDate());
  }

  /** La date ISO (10 premiers caractères) si elle existe vraiment, sinon '' (« 2026-02-30 », « 31/12/2026 » ou un
   *  texte ne sont pas lisibles : une fin illisible donne le statut « fin inconnue »). */
  function dateIso(valeur) {
    const date = texte(valeur).slice(0, 10);
    const numero = numeroJour(date);
    return numero !== null && dateDepuisNumero(numero) === date ? date : '';
  }

  /** Date ISO + n jours (n négatif possible). */
  function ajouterJours(date, n) {
    return dateDepuisNumero(numeroJour(date) + n);
  }

  /** Nombre de jours de `debut` à `fin` (négatif si fin est avant). */
  function joursEntre(debut, fin) {
    return numeroJour(fin) - numeroJour(debut);
  }

  /** Date du jour à utiliser : celle passée en argument, sinon aujourd'hui. */
  function dateDuJour(aujourdhui) {
    return dateIso(aujourdhui) || Donnees.aujourdhui();
  }

  /** Date ISO + n mois, jour ramené au dernier jour du mois s'il n'existe pas (règle des contrôles). */
  function ajouterMois(date, n) {
    return Controles.ajouterMois(date, n);
  }

  /** Nombre entier lu dans une valeur (« 3 », « 3,0 »), ou null si vide, illisible ou non entier. */
  function entier(valeur) {
    const lu = Donnees.nombre(valeur);
    return lu !== null && Number.isInteger(lu) ? lu : null;
  }

  /** Vrai si la ligne n'est pas retirée (actif vide ou différent de 0). */
  function estActif(ligne) {
    return texte(ligne && ligne.actif) !== '0';
  }

  function lignesActives(nomTable) {
    return Donnees.lignes(nomTable).filter(estActif);
  }

  function comparerIdentifiants(a, b) {
    return texte(a.id).localeCompare(texte(b.id), 'fr', { numeric: true });
  }

  /** « dans 45 jours », « aujourd'hui » : morceau des raisons affichées. */
  function quand(jours) {
    return jours === 0 ? I18n.t('garanties.quand.aujourd_hui') : I18n.t('garanties.quand.dans_n_jours', { n: jours });
  }

  /** Libellé affiché d'un statut calculé (garantie ou contrat) ; statut inconnu : tel quel. */
  function libelleStatut(statut) {
    return STATUTS_GARANTIE.includes(statut) || STATUTS_CONTRAT.includes(statut)
      ? I18n.t('garanties.statut.' + statut) : statut;
  }

  /**
   * Délai d'alerte en jours (D187) : la valeur passée, sinon le réglage alerte_echeances_jours de parametres.csv ;
   * vide, illisible, non entier ou hors de 1 à 365 → 60.
   */
  function delaiAlerte(valeur) {
    const brute = valeur === undefined || valeur === null ? Donnees.parametre(PARAMETRE_DELAI, '') : valeur;
    const jours = entier(brute);
    return jours !== null && jours >= DELAI_MIN_JOURS && jours <= DELAI_MAX_JOURS ? jours : DELAI_PAR_DEFAUT_JOURS;
  }

  /** Montant en centimes (entier, arrondi au centime : « 4 800,505 » → 480051), ou null si vide, illisible ou
   *  négatif. Calcul sur le texte, sans flottant. */
  function centimes(valeur) {
    const lu = Donnees.normaliser.decimal(valeur);
    const morceaux = lu.ok ? MOTIF_MONTANT.exec(lu.valeur) : null;
    if (!morceaux) return null;
    const decimales = ((morceaux[2] || '') + '000').slice(0, 3);
    return Number(morceaux[1]) * 100 + Number(decimales.slice(0, 2)) + (Number(decimales[2]) >= 5 ? 1 : 0);
  }

  // ===========================================================================================
  // 2. Garanties
  // ===========================================================================================

  function raisonGarantie(statut, debut, fin, joursRestants) {
    if (statut === FIN_INCONNUE) return I18n.t('garanties.raison_garantie.fin_inconnue');
    if (statut === A_VENIR) return I18n.t('garanties.raison_garantie.a_venir', { debut: UI.dateFr(debut) });
    if (statut === TERMINEE) return I18n.t('garanties.raison_garantie.terminee', { fin: UI.dateFr(fin) });
    if (statut === BIENTOT) {
      return I18n.t('garanties.raison_garantie.bientot', { quand: quand(joursRestants), fin: UI.dateFr(fin) });
    }
    return I18n.t('garanties.raison_garantie.en_cours', { fin: UI.dateFr(fin) });
  }

  /**
   * État d'une garantie à une date : { statut, debut, fin, joursRestants, alerte, raison }. statut = le premier vrai
   * de STATUTS_GARANTIE : « fin inconnue » (fin vide ou illisible), « à venir » (début après le jour), « terminée »
   * (fin avant le jour), « se termine bientôt » (0 ≤ fin − jour ≤ délai : alerte), « en cours ». Bornes incluses :
   * le jour du début et le jour de la fin, la garantie court. Un début illisible compte comme vide (déjà commencée).
   * delai : jours (par défaut delaiAlerte()).
   */
  function etatGarantie(garantie, aujourdhui, delai) {
    const jour = dateDuJour(aujourdhui);
    const jours = delaiAlerte(delai);
    const debut = dateIso(garantie && garantie.date_debut);
    const fin = dateIso(garantie && garantie.date_fin);
    const joursRestants = fin ? joursEntre(jour, fin) : null;
    let statut = EN_COURS;
    if (!fin) statut = FIN_INCONNUE;
    else if (debut && debut > jour) statut = A_VENIR;
    else if (joursRestants < 0) statut = TERMINEE;
    else if (joursRestants <= jours) statut = BIENTOT;
    return { statut, debut, fin, joursRestants, alerte: statut === BIENTOT,
      raison: raisonGarantie(statut, debut, fin, joursRestants) };
  }

  /** Garanties actives d'un équipement, la fin la plus lointaine d'abord (fins inconnues en dernier). */
  function garantiesDeLEquipement(equipementId) {
    const id = texte(equipementId);
    if (!id) return [];
    return lignesActives('garanties')
      .filter((garantie) => texte(garantie.equipement_id) === id)
      .sort((a, b) => {
        const finA = dateIso(a.date_fin);
        const finB = dateIso(b.date_fin);
        if (finA !== finB) return !finA ? 1 : !finB ? -1 : finB.localeCompare(finA);
        return comparerIdentifiants(a, b);
      });
  }

  /**
   * L'équipement est-il sous garantie le jour donné ? { garantie, fournisseur, fin } ou null. Sous garantie : garantie
   * active, début vide (ou illisible) ou au plus tard le jour, jour au plus tard la fin (bornes incluses). Plusieurs
   * garanties : celle dont la fin est la plus lointaine (« sous garantie jusqu'au … »). fournisseur : la ligne de
   * fournisseurs.csv, ou null (le rappel dit alors « appeler le fournisseur » sans nom).
   */
  function sousGarantie(equipementId, aujourdhui) {
    const jour = dateDuJour(aujourdhui);
    const garantie = garantiesDeLEquipement(equipementId).find((ligne) => {
      const debut = dateIso(ligne.date_debut);
      const fin = dateIso(ligne.date_fin);
      return Boolean(fin) && fin >= jour && (!debut || debut <= jour);
    });
    if (!garantie) return null;
    const fournisseurId = texte(garantie.fournisseur_id);
    const fournisseur = fournisseurId ? Donnees.trouver('fournisseurs', fournisseurId) || null : null;
    return { garantie, fournisseur, fin: dateIso(garantie.date_fin) };
  }

  // ===========================================================================================
  // 3. Contrats
  // ===========================================================================================

  /** Vrai si le contrat se reconduit tacitement (« 1 », « oui », « vrai »…). */
  function estTacite(contrat) {
    return Donnees.normaliser.booleen(contrat && contrat.reconduction_tacite).valeur === '1';
  }

  /** Préavis en mois : entier ≥ 0 ; vide, illisible ou négatif → 0 (date limite = fin, l'alerte vient avant la fin). */
  function preavisMois(contrat) {
    const mois = entier(contrat && contrat.preavis_mois);
    return mois !== null && mois > 0 ? mois : 0;
  }

  /** Durée d'une reconduction en mois (entier ≥ 1), ou null si vide ou illisible. */
  function reconductionMois(contrat) {
    const mois = entier(contrat && contrat.reconduction_mois);
    return mois !== null && mois > 0 ? mois : null;
  }

  /** Fin de la période qui suit `fin` de n mois : le lendemain + n mois, moins un jour. Une période finie le
   *  31/12 finit le 31/12, une finie le 30/09 reconduite de 3 mois finit le 31/12 (et non le 30/12). */
  function finApres(fin, mois) {
    return ajouterJours(ajouterMois(ajouterJours(fin, 1), mois), -1);
  }

  /** Date limite de résiliation d'une fin : fin − préavis en mois (fin de mois ramenée au dernier jour). */
  function limiteDeLaFin(fin, preavis) {
    return preavis ? ajouterMois(fin, -preavis) : fin;
  }

  /**
   * Date limite de résiliation d'un contrat ('AAAA-MM-JJ', ou '' si sa fin est vide ou illisible) : date_fin −
   * preavis_mois mois, jour ramené au dernier jour du mois s'il n'existe pas (31/12/2026 − 3 mois = 30/09/2026 ;
   * 31/05/2028 − 3 mois = 29/02/2028). Préavis vide, 0 ou illisible : la date de fin.
   */
  function dateLimiteResiliation(contrat) {
    const fin = dateIso(contrat && contrat.date_fin);
    return fin ? limiteDeLaFin(fin, preavisMois(contrat)) : '';
  }

  /**
   * Fin de la période en cours d'un contrat reconduit tacitement dont la fin enregistrée est passée, calculée avec
   * reconduction_mois (QUESTIONS L4-L6 Q3 : rien n'est écrit) : la première fin fin + k × reconduction_mois (k ≥ 1)
   * qui n'est pas avant le jour. '' si la durée d'une reconduction est inconnue.
   */
  function finDeLaPeriodeReconduite(fin, mois, jour) {
    if (!mois) return '';
    const ecart = (Number(jour.slice(0, 4)) - Number(fin.slice(0, 4))) * 12
      + Number(jour.slice(5, 7)) - Number(fin.slice(5, 7));
    let k = Math.max(1, Math.ceil(ecart / mois));
    while (k > 1 && finApres(fin, (k - 1) * mois) >= jour) k -= 1;
    while (finApres(fin, k * mois) < jour) k += 1;
    return finApres(fin, k * mois);
  }

  function raisonContrat(statut, etatCalcule) {
    const fin = UI.dateFr(etatCalcule.fin);
    const finPeriode = UI.dateFr(etatCalcule.finPeriode);
    const limite = UI.dateFr(etatCalcule.dateLimite);
    const avecPreavis = etatCalcule.dateLimite !== etatCalcule.finPeriode;
    switch (statut) {
      case FIN_INCONNUE: return I18n.t('garanties.raison_contrat.fin_inconnue');
      case A_DECIDER:
        if (etatCalcule.periodeCalculee) {
          return I18n.t('garanties.raison_contrat.a_decider_periode_calculee',
            { limite, quand: quand(etatCalcule.joursAvantLimite), fin });
        }
        if (etatCalcule.tacite) {
          return I18n.t('garanties.raison_contrat.a_decider_tacite',
            { limite, quand: quand(etatCalcule.joursAvantLimite), fin: finPeriode });
        }
        // sans reconduction tacite ni préavis, la date limite est la fin : la raison dit la fin
        return avecPreavis ? I18n.t('garanties.raison_contrat.a_decider',
          { limite, quand: quand(etatCalcule.joursAvantLimite), fin: finPeriode })
          : I18n.t('garanties.raison_contrat.bientot', { quand: quand(etatCalcule.joursAvantFin), fin: finPeriode });
      case A_METTRE_A_JOUR: return I18n.t('garanties.raison_contrat.a_mettre_a_jour', { fin });
      case BIENTOT:
        return I18n.t('garanties.raison_contrat.bientot', { quand: quand(etatCalcule.joursAvantFin), fin: finPeriode });
      case PREAVIS_DEPASSE:
        return I18n.t(etatCalcule.tacite ? 'garanties.raison_contrat.preavis_depasse_tacite'
          : 'garanties.raison_contrat.preavis_depasse', { limite, fin: finPeriode });
      case TERMINE: return I18n.t('garanties.raison_contrat.termine', { fin });
      default:
        return avecPreavis ? I18n.t('garanties.raison_contrat.en_cours_preavis', { fin: finPeriode, limite })
          : I18n.t('garanties.raison_contrat.en_cours', { fin: finPeriode });
    }
  }

  /**
   * État d'un contrat à une date : { statut, fin, finPeriode, periodeCalculee, tacite, dateLimite, joursAvantLimite,
   * joursAvantFin, alerte, raison }. fin : date_fin enregistrée ; finPeriode : fin de la période qui sert au calcul,
   * la même, sauf pour un contrat reconduit tacitement dont la fin est passée et dont reconduction_mois est connu :
   * la fin de la période reconduite, calculée (periodeCalculee, rien n'est écrit) ; dateLimite, joursAvantLimite et
   * joursAvantFin portent sur cette période. statut = le premier vrai de STATUTS_CONTRAT :
   *   « fin inconnue » (fin vide ou illisible) ;
   *   « à décider » (0 ≤ date limite − jour ≤ délai : alerte) ;
   *   « dates à mettre à jour » (fin enregistrée passée et reconduction tacite : le contrat continue) ;
   *   « se termine bientôt » (sans reconduction tacite, 0 ≤ fin − jour ≤ délai : alerte, la prestation s'arrête) ;
   *   « préavis dépassé » (date limite < jour ≤ fin) ; « terminé » (fin passée, sans reconduction) ; « en cours ».
   * CS173 (délai 60) : fin 31/12/2026, préavis 3 mois → à décider du 01/08/2026 au 30/09/2026.
   */
  function etatContrat(contrat, aujourdhui, delai) {
    const jour = dateDuJour(aujourdhui);
    const jours = delaiAlerte(delai);
    const fin = dateIso(contrat && contrat.date_fin);
    const tacite = estTacite(contrat);
    const resultat = { statut: FIN_INCONNUE, fin, finPeriode: fin, periodeCalculee: false, tacite, dateLimite: '',
      joursAvantLimite: null, joursAvantFin: null, alerte: false };
    if (fin) {
      const reconduite = tacite && fin < jour ? finDeLaPeriodeReconduite(fin, reconductionMois(contrat), jour) : '';
      const finPeriode = reconduite || fin;
      const dateLimite = limiteDeLaFin(finPeriode, preavisMois(contrat));
      const joursAvantLimite = joursEntre(jour, dateLimite);
      const joursAvantFin = joursEntre(jour, finPeriode);
      let statut = EN_COURS;
      if (joursAvantLimite >= 0 && joursAvantLimite <= jours) statut = A_DECIDER;
      else if (tacite && fin < jour) statut = A_METTRE_A_JOUR;
      else if (!tacite && joursAvantFin >= 0 && joursAvantFin <= jours) statut = BIENTOT;
      else if (joursAvantLimite < 0 && joursAvantFin >= 0) statut = PREAVIS_DEPASSE;
      else if (joursAvantFin < 0) statut = TERMINE;
      Object.assign(resultat, { statut, finPeriode, periodeCalculee: Boolean(reconduite), dateLimite,
        joursAvantLimite, joursAvantFin, alerte: statut === A_DECIDER || statut === BIENTOT });
    }
    resultat.raison = raisonContrat(resultat.statut, resultat);
    return resultat;
  }

  /** Identifiants des équipements cités par un contrat (equipement_ids : séparés par « ; », « , » ou des espaces),
   *  dans l'ordre, doublons retirés. */
  function equipementsDuContrat(contrat) {
    const vus = [];
    texte(contrat && contrat.equipement_ids).split(SEPARATEURS_EQUIPEMENTS).forEach((id) => {
      if (id && !vus.includes(id)) vus.push(id);
    });
    return vus;
  }

  /** Contrats actifs qui citent l'équipement, par date de fin (fins inconnues en dernier), puis par identifiant. */
  function contratsDeLEquipement(equipementId) {
    const id = texte(equipementId);
    if (!id) return [];
    return lignesActives('contrats_prestataires')
      .filter((contrat) => equipementsDuContrat(contrat).includes(id))
      .sort((a, b) => {
        const finA = dateIso(a.date_fin);
        const finB = dateIso(b.date_fin);
        if (finA !== finB) return !finA ? 1 : !finB ? -1 : finA.localeCompare(finB);
        return comparerIdentifiants(a, b);
      });
  }

  /** Durée de la période d'un contrat en mois entiers (le plus grand n tel que début + n mois ≤ lendemain de la fin),
   *  ou null si le début est vide ou illisible, ou si la période fait moins d'un mois. */
  function dureePeriodeMois(contrat) {
    const debut = dateIso(contrat && contrat.date_debut);
    const fin = dateIso(contrat && contrat.date_fin);
    if (!debut || !fin || fin < debut) return null;
    const lendemain = ajouterJours(fin, 1);
    let mois = (Number(lendemain.slice(0, 4)) - Number(debut.slice(0, 4))) * 12
      + Number(lendemain.slice(5, 7)) - Number(debut.slice(5, 7));
    if (ajouterMois(debut, mois) > lendemain) mois -= 1;
    return mois > 0 ? mois : null;
  }

  /**
   * Nouvelle période proposée par « Reconduire » (toujours modifiable) : { date_debut, date_fin, mois }, ou null si la
   * fin est vide ou illisible. Début = ancienne fin + 1 jour ; durée = reconduction_mois, sinon la durée de la
   * période en mois entiers, sinon 12 ; fin = début + durée − 1 jour (31/12/2026, 12 mois → 01/01/2027-31/12/2027).
   */
  function propositionReconduction(contrat) {
    const fin = dateIso(contrat && contrat.date_fin);
    if (!fin) return null;
    const mois = reconductionMois(contrat) || dureePeriodeMois(contrat) || RECONDUCTION_PAR_DEFAUT_MOIS;
    return { date_debut: ajouterJours(fin, 1), date_fin: finApres(fin, mois), mois };
  }

  /**
   * Total des montants annuels (liste des contrats) : { centimes, sansMontant }. Contrats actifs dont la prestation
   * continue (STATUTS_AU_TOTAL : ni « fin inconnue » ni « terminé ») ; montant vide ou illisible : compté dans
   * sansMontant, jamais estimé (D190). contrats : lignes (par défaut tous les contrats).
   */
  function totalMontants(contrats, aujourdhui) {
    const jour = dateDuJour(aujourdhui);
    const jours = delaiAlerte();
    const lignes = Array.isArray(contrats) ? contrats : Donnees.lignes('contrats_prestataires');
    let total = 0;
    let sansMontant = 0;
    lignes.filter(estActif).forEach((contrat) => {
      if (!STATUTS_AU_TOTAL.includes(etatContrat(contrat, jour, jours).statut)) return;
      const montant = centimes(contrat.montant_annuel);
      if (montant === null) sansMontant += 1;
      else total += montant;
    });
    return { centimes: total, sansMontant };
  }

  // ===========================================================================================
  // 4. Échéances
  // ===========================================================================================

  /** L'équipement de la garantie existe, est actif et n'est pas au rebut. */
  function equipementSuivi(garantie) {
    const equipement = Donnees.trouver('equipements', texte(garantie.equipement_id));
    return Boolean(equipement) && texte(equipement.actif) !== '0' && texte(equipement.statut) !== 'rebut';
  }

  function trierParDate(elements, date) {
    return elements
      .sort((a, b) => date(a).localeCompare(date(b)) || comparerIdentifiants(a.ligne, b.ligne))
      .map((element) => element.ligne);
  }

  /**
   * Échéances à une date (accueil, compteurs de l'écran) : { garanties, contrats, aMettreAJour } — lignes actives.
   * garanties : « se termine bientôt », d'équipements actifs hors rebut, par date de fin ; contrats : en alerte
   * (« à décider » ou « se termine bientôt »), par date de l'alerte (date limite, ou fin pour « se termine
   * bientôt ») ; aMettreAJour : « dates à mettre à jour », par date de fin. delai : jours (par défaut delaiAlerte()).
   */
  function aEcheance(aujourdhui, delai) {
    const jour = dateDuJour(aujourdhui);
    const jours = delaiAlerte(delai);
    const garanties = lignesActives('garanties').filter(equipementSuivi)
      .map((ligne) => ({ ligne, etat: etatGarantie(ligne, jour, jours) }))
      .filter((element) => element.etat.alerte);
    const contrats = lignesActives('contrats_prestataires')
      .map((ligne) => ({ ligne, etat: etatContrat(ligne, jour, jours) }));
    return {
      garanties: trierParDate(garanties, (element) => element.etat.fin),
      contrats: trierParDate(contrats.filter((element) => element.etat.alerte), (element) =>
        (element.etat.statut === A_DECIDER ? element.etat.dateLimite : element.etat.finPeriode)),
      aMettreAJour: trierParDate(contrats.filter((element) => element.etat.statut === A_METTRE_A_JOUR),
        (element) => element.etat.fin),
    };
  }

  // ===========================================================================================
  // 5. Vérification des valeurs saisies ou importées
  // ===========================================================================================

  /** Erreurs des dates de début (facultative) et de fin (obligatoire) : illisibles, fin absente, fin avant début. */
  function erreursPeriode(valeurs, messageFinAbsente) {
    const erreurs = [];
    const debutBrut = texte(valeurs.date_debut);
    const finBrute = texte(valeurs.date_fin);
    const debut = dateIso(debutBrut);
    const fin = dateIso(finBrute);
    if (debutBrut && !debut) erreurs.push({ nom: 'date_debut', message: I18n.t('garanties.verifier.debut_illisible') });
    if (!finBrute) erreurs.push({ nom: 'date_fin', message: messageFinAbsente });
    else if (!fin) erreurs.push({ nom: 'date_fin', message: I18n.t('garanties.verifier.fin_illisible') });
    else if (debut && fin < debut) erreurs.push({ nom: 'date_fin', message: I18n.t('garanties.verifier.fin_avant_debut') });
    return erreurs;
  }

  function erreurEquipement(equipementId) {
    return Donnees.trouver('equipements', equipementId) ? null
      : { nom: 'equipement_id', message: I18n.t('garanties.verifier.equipement_introuvable', { equipementId }) };
  }

  /**
   * Contrôle les valeurs d'une garantie : [{ nom, message }] (vide si tout va bien). Équipement obligatoire et
   * existant ; fournisseur facultatif, existant s'il est donné ; début facultatif, fin obligatoire, lisibles
   * (AAAA-MM-JJ) ; fin pas avant le début. Sert au formulaire et à l'import.
   */
  function verifierGarantie(valeurs) {
    const propres = valeurs || {};
    const erreurs = [];
    const equipementId = texte(propres.equipement_id);
    if (!equipementId) {
      erreurs.push({ nom: 'equipement_id', message: I18n.t('garanties.verifier_garantie.choisissez_equipement') });
    } else {
      const erreur = erreurEquipement(equipementId);
      if (erreur) erreurs.push(erreur);
    }
    const fournisseurId = texte(propres.fournisseur_id);
    if (fournisseurId && !Donnees.trouver('fournisseurs', fournisseurId)) {
      erreurs.push({ nom: 'fournisseur_id', message: I18n.t('garanties.verifier.fournisseur_introuvable', { fournisseurId }) });
    }
    erreurs.push(...erreursPeriode(propres, I18n.t('garanties.verifier_garantie.fin_obligatoire')));
    return erreurs;
  }

  /**
   * Contrôle les valeurs d'un contrat : [{ nom, message }]. Prestataire obligatoire et existant (fournisseurs) ;
   * objet obligatoire ; équipements cités existants ; début facultatif, fin obligatoire, lisibles, fin pas avant le
   * début ; préavis vide ou entier ≥ 0 ; durée d'une reconduction vide ou entier ≥ 1 ; montant vide ou nombre ≥ 0.
   * Sert au formulaire et à l'import.
   */
  function verifierContrat(valeurs) {
    const propres = valeurs || {};
    const erreurs = [];
    const fournisseurId = texte(propres.fournisseur_id);
    if (!fournisseurId) {
      erreurs.push({ nom: 'fournisseur_id', message: I18n.t('garanties.verifier_contrat.choisissez_prestataire') });
    } else if (!Donnees.trouver('fournisseurs', fournisseurId)) {
      erreurs.push({ nom: 'fournisseur_id', message: I18n.t('garanties.verifier_contrat.prestataire_introuvable', { fournisseurId }) });
    }
    if (!texte(propres.objet)) erreurs.push({ nom: 'objet', message: I18n.t('garanties.verifier_contrat.objet_obligatoire') });
    equipementsDuContrat(propres).forEach((id) => {
      const erreur = erreurEquipement(id);
      if (erreur) erreurs.push(Object.assign(erreur, { nom: 'equipement_ids' }));
    });
    erreurs.push(...erreursPeriode(propres, I18n.t('garanties.verifier_contrat.fin_obligatoire')));
    const preavis = texte(propres.preavis_mois);
    const preavisLu = entier(preavis);
    if (preavis && (preavisLu === null || preavisLu < 0)) {
      erreurs.push({ nom: 'preavis_mois', message: I18n.t('garanties.verifier_contrat.preavis_entier') });
    }
    const reconduction = texte(propres.reconduction_mois);
    const reconductionLue = entier(reconduction);
    if (reconduction && (reconductionLue === null || reconductionLue < 1)) {
      erreurs.push({ nom: 'reconduction_mois', message: I18n.t('garanties.verifier_contrat.reconduction_entier') });
    }
    if (texte(propres.montant_annuel) && centimes(propres.montant_annuel) === null) {
      erreurs.push({ nom: 'montant_annuel', message: I18n.t('garanties.verifier_contrat.montant_positif') });
    }
    return erreurs;
  }

  /**
   * Avertissements non bloquants d'un contrat : [{ nom, message }]. Le préavis dépasse la durée du contrat (la date
   * limite de résiliation tombe avant son début).
   */
  function avertissementsContrat(valeurs) {
    const propres = valeurs || {};
    const debut = dateIso(propres.date_debut);
    const limite = dateLimiteResiliation(propres);
    if (debut && limite && limite < debut) {
      return [{ nom: 'preavis_mois', message: I18n.t('garanties.avertissement_contrat.preavis_depasse_duree') }];
    }
    return [];
  }

  return {
    STATUTS_GARANTIE, STATUTS_CONTRAT, PARAMETRE_DELAI, libelleStatut, delaiAlerte,
    // règles pures (conception L4 §2.6)
    etatGarantie, garantiesDeLEquipement, sousGarantie,
    dateLimiteResiliation, etatContrat, equipementsDuContrat, contratsDeLEquipement, propositionReconduction,
    totalMontants, aEcheance, verifierGarantie, verifierContrat, avertissementsContrat,
    // Usage interne au module (pas une API) : complété par les fichiers suivants.
    interne: { texte, dateIso, dateDuJour, ajouterJours, joursEntre, centimes, estActif, estTacite, preavisMois,
      reconductionMois },
  };
})();
