'use strict';
// Preventif : module M4 « Maintenance préventive » de Prévo — gammes, déclenchement RG5 (date,
// compteur, seuil), calendrier sur 12 semaines (ARCHITECTURE.md §14.3 ; brief §7 RG5, §9 E8).
//
// Le module est découpé en quatre fichiers, chargés dans cet ordre par index.html (§14.2) :
//   preventif-regles.js       CE FICHIER, qui crée l'objet Preventif : règles PURES
//                               1. Constantes et petits outils (textes, nombres, dates ISO)
//                               2. Relevés de compteur, OT ouverts d'une gamme
//                               3. État d'une gamme (etatGamme) : date, compteur, seuil
//                               4. Calendrier des prochaines semaines
//   preventif-ecritures.js    genererOTEchus, apresCloture, gammes et check-lists
//   preventif-ecrans.js       écrans #/preventif et #/preventif/gamme/…
//   preventif-calendrier.js   onglet « Calendrier 12 semaines »
//
// Les fichiers suivants complètent l'objet : Object.assign(Preventif, (() => { … })()). Une
// fonction dont un autre fichier du module a besoin est rangée dans Preventif.interne (usage
// interne au module : ce n'est pas une API, ni les autres modules ni les tests ne s'en servent).
//
// Les fonctions de ce fichier sont PURES : elles lisent Donnees, n'écrivent jamais. Toutes les
// dates sont des chaînes ISO 'AAAA-MM-JJ' ; la date du jour est passée en argument (par défaut
// Donnees.aujourdhui()), pour que le résultat ne dépende pas de l'heure réelle.

const Preventif = (() => {

  // ===========================================================================================
  // 1. Constantes et petits outils
  // ===========================================================================================

  /** Déclencheurs d'une gamme (valeurs du schéma) et leur libellé. */
  const DECLENCHEURS = Object.freeze({
    get date() { return I18n.t('preventif.date.date_tous_jours'); },
    get compteur() { return I18n.t('preventif.compteur.compteur_toutes_unites'); },
    get seuil() { return I18n.t('preventif.seuil.seuil_mesure_atteint_limite'); },
  });

  /** Statuts calculés d'une gamme (etatGamme), du plus urgent au moins urgent, et leur libellé. */
  const STATUTS_GAMME = Object.freeze({
    get echue() { return I18n.t('preventif.echue.echue'); },
    get ot_ouvert() { return I18n.t('preventif.ot_ouvert.ot_ouvert'); },
    get bientot() { return I18n.t('preventif.bientot.bientot'); },
    get a_jour() { return I18n.t('preventif.a_jour.jour'); },
    get incomplete() { return I18n.t('preventif.incomplete.incomplete'); },
    get inactive() { return I18n.t('preventif.inactive.inactive'); },
  });

  // Une gamme est « bientôt » échue si son déclenchement tombe dans les 14 jours qui viennent.
  const HORIZON_BIENTOT_JOURS = 14;
  const SEMAINES_PAR_DEFAUT = 12;
  const HEURES_PAR_JOUR_PAR_DEFAUT = 8;
  const STATUTS_FERMES = ['Clôturé techniquement', 'Clôturé administrativement', 'Annulé'];
  const MILLISECONDES_PAR_JOUR = 86400000;
  const MOTIF_DATE_ISO = /^(\d{4})-(\d{2})-(\d{2})/;

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  /** Nombre lu dans une valeur du fichier, ou null si vide ou illisible. */
  function nombre(valeur) {
    return Donnees.nombre(valeur);
  }

  function arrondi(valeur, decimales) {
    const facteur = Math.pow(10, decimales === undefined ? 2 : decimales);
    return Math.round(valeur * facteur) / facteur;
  }

  // --- Dates ISO, calculées en UTC (un changement d'heure ne décale jamais un jour) ----------

  /** 'AAAA-MM-JJ' (ou 'AAAA-MM-JJ HH:MM') → numéro du jour depuis le 01/01/1970, ou null. */
  function numeroJour(dateIso) {
    const morceaux = MOTIF_DATE_ISO.exec(texte(dateIso));
    if (!morceaux) return null;
    return Date.UTC(Number(morceaux[1]), Number(morceaux[2]) - 1, Number(morceaux[3])) / MILLISECONDES_PAR_JOUR;
  }

  function dateDepuisNumero(numero) {
    const date = new Date(numero * MILLISECONDES_PAR_JOUR);
    return date.getUTCFullYear() + '-' + String(date.getUTCMonth() + 1).padStart(2, '0')
      + '-' + String(date.getUTCDate()).padStart(2, '0');
  }

  function estDateIso(valeur) {
    return numeroJour(valeur) !== null;
  }

  /** Date ISO + n jours (n peut être négatif). Date illisible → ''. */
  function ajouterJours(dateIso, jours) {
    const numero = numeroJour(dateIso);
    return numero === null ? '' : dateDepuisNumero(numero + jours);
  }

  /** Nombre de jours de `debut` à `fin` (négatif si fin est avant), ou null si une date est illisible. */
  function joursEntre(debut, fin) {
    const a = numeroJour(debut);
    const b = numeroJour(fin);
    return a === null || b === null ? null : b - a;
  }

  /** Lundi de la semaine d'une date (semaine du lundi au dimanche). */
  function lundiDe(dateIso) {
    const numero = numeroJour(dateIso);
    const jourSemaine = new Date(numero * MILLISECONDES_PAR_JOUR).getUTCDay();   // 0 = dimanche
    return dateDepuisNumero(numero - ((jourSemaine + 6) % 7));
  }

  /** Date du jour à utiliser : celle passée en argument (10 premiers caractères), sinon aujourd'hui. */
  function dateDuJour(aujourdhui) {
    const date = texte(aujourdhui).slice(0, 10);
    return estDateIso(date) ? date : Donnees.aujourdhui();
  }

  /** « 1 860 h », « 74 °C », « 52 000 » : nombre à la française suivi de l'unité éventuelle. */
  function valeurAvecUnite(valeur, unite) {
    return UI.nombreFr(valeur) + (texte(unite) ? ' ' + texte(unite) : '');
  }

  // ===========================================================================================
  // 2. Relevés de compteur, OT ouverts d'une gamme
  // ===========================================================================================

  /** Vrai si le relevé `a` est plus récent que `b` (date, puis identifiant). */
  function estPlusRecent(a, b) {
    if (a.date !== b.date) return a.date > b.date;
    return a.id > b.id;
  }

  /**
   * Dernier relevé de chaque compteur, en une seule lecture de releves :
   * Map compteur_id → { valeur (Number), date, id }. Un relevé de valeur illisible est ignoré.
   */
  function derniersReleves() {
    const derniers = new Map();
    Donnees.lignes('releves').forEach((releve) => {
      const valeur = nombre(releve.valeur);
      if (valeur === null) return;
      const candidat = { valeur, date: texte(releve.date).slice(0, 10), id: texte(releve.id) };
      const actuel = derniers.get(releve.compteur_id);
      if (!actuel || estPlusRecent(candidat, actuel)) derniers.set(releve.compteur_id, candidat);
    });
    return derniers;
  }

  /** Dernier relevé d'un compteur (relevés triés par date puis identifiant) : { valeur, date } ou null. */
  function dernierReleve(compteurId) {
    const releve = derniersReleves().get(compteurId);
    return releve ? { valeur: releve.valeur, date: releve.date } : null;
  }

  /** Vrai si l'OT n'est ni clôturé (techniquement ou administrativement) ni annulé. */
  function estOuvert(ot) {
    return Boolean(ot) && !STATUTS_FERMES.includes(ot.statut);
  }

  /** OT préventif : origine « préventif », lié à une gamme, ou de type « préventif … ». */
  function estOtPreventif(ot) {
    return ot.origine === 'préventif' || texte(ot.gamme_id) !== '' || /^préventif/.test(texte(ot.type));
  }

  /**
   * Premier OT ouvert (plus petit identifiant) de chaque gamme : Map gamme_id → OT.
   * lignesOt : lignes d'OT à lire (ex. les lignes fraîches d'une fonction de mutation), sinon le cache.
   */
  function otsOuvertsParGamme(lignesOt) {
    const parGamme = new Map();
    (lignesOt || Donnees.lignes('ordres_travail')).forEach((ot) => {
      if (!texte(ot.gamme_id) || !estOuvert(ot)) return;
      const actuel = parGamme.get(ot.gamme_id);
      if (!actuel || ot.id < actuel.id) parGamme.set(ot.gamme_id, ot);
    });
    return parGamme;
  }

  /**
   * Ce dont le calcul d'état a besoin, lu une seule fois (le calendrier évalue toutes les gammes
   * avec le même contexte) : { releves: Map compteur → dernier relevé, otsOuverts: Map gamme → OT }.
   */
  function contexteCalcul() {
    return { releves: derniersReleves(), otsOuverts: otsOuvertsParGamme() };
  }

  // --- Compteurs en heures : estimation d'une échéance -----------------------------------------

  /** Vrai si l'unité est l'heure : « h », « heure », « heures » (casse et espaces ignorés). */
  function estUniteHeure(unite) {
    return /^(h|heures?)$/.test(texte(unite).toLowerCase().replace(/\.$/, ''));
  }

  /**
   * Heures de fonctionnement par jour : celles de l'équipement de la gamme (sinon de celui du
   * compteur), à défaut le paramètre heures_fonct_defaut, à défaut 8.
   */
  function heuresParJour(gamme, compteur) {
    const equipement = Donnees.trouver('equipements', gamme.equipement_id)
      || (compteur && Donnees.trouver('equipements', compteur.equipement_id));
    const propres = equipement ? nombre(equipement.heures_fonct_jour) : null;
    if (propres !== null && propres > 0) return propres;
    const parDefaut = nombre(Donnees.parametre('heures_fonct_defaut', ''));
    return parDefaut !== null && parDefaut > 0 ? parDefaut : HEURES_PAR_JOUR_PAR_DEFAUT;
  }

  /**
   * Échéance estimée d'une gamme « compteur » : date du relevé + reste / heures par jour (arrondi
   * au jour supérieur : c'est le jour où le compteur atteint la périodicité). Seulement si l'unité
   * du compteur est l'heure et que le relevé est daté ; sinon ''. Reste négatif → date passée.
   */
  function echeanceEstimee(gamme, compteur, releve, reste) {
    if (!compteur || !estUniteHeure(compteur.unite) || !releve || !estDateIso(releve.date)) return '';
    const jours = Math.ceil(arrondi(reste / heuresParJour(gamme, compteur), 6));
    return ajouterJours(releve.date, jours);
  }

  // ===========================================================================================
  // 3. État d'une gamme (RG5) — etatGamme
  // ===========================================================================================

  /** Résultat vide d'etatGamme, complété par chaque déclencheur. */
  function etatDeBase(statut, raison) {
    return { statut, echeance: '', declenchement: '', raison, otOuvertId: '', releveActuel: null, reste: null };
  }

  /** Statut d'après la date de déclenchement : échue, bientôt (≤ 14 jours) ou à jour. */
  function statutSelonDeclenchement(declenchement, jour) {
    const joursAvant = joursEntre(jour, declenchement);
    if (joursAvant <= 0) return 'echue';
    return joursAvant <= HORIZON_BIENTOT_JOURS ? 'bientot' : 'a_jour';
  }

  /**
   * Déclencheur « date » : échéance = prochaine_echeance, sinon derniere_realisation +
   * periodicite_jours, sinon aujourd'hui (jamais réalisée → à faire) ; déclenchement = échéance −
   * avance_jours ; échue si aujourd'hui ≥ déclenchement. periodicite_jours est obligatoire (sans
   * elle, l'échéance suivante ne peut pas être calculée) : sinon « incomplete ».
   */
  function etatDate(gamme, jour) {
    const periodicite = nombre(gamme.periodicite_jours);
    if (periodicite === null || periodicite <= 0) return etatDeBase('incomplete', I18n.t('preventif.etat_date.periodicite_jours_renseigner'));
    const avance = Math.max(0, Math.round(nombre(gamme.avance_jours) || 0));
    let echeance = texte(gamme.prochaine_echeance).slice(0, 10);
    const derniere = texte(gamme.derniere_realisation).slice(0, 10);
    const jamaisRealisee = !echeance && !derniere;
    if (!echeance && derniere) echeance = ajouterJours(derniere, Math.round(periodicite));
    if (jamaisRealisee) echeance = jour;
    if (!estDateIso(echeance)) return etatDeBase('incomplete', I18n.t('preventif.etat_date.date_echeance_illisible'));

    const declenchement = ajouterJours(echeance, -avance);
    const etat = etatDeBase(statutSelonDeclenchement(declenchement, jour), '');
    etat.echeance = echeance;
    etat.declenchement = declenchement;
    etat.reste = joursEntre(jour, echeance);           // jours avant l'échéance (négatif : dépassée)
    etat.raison = raisonDate(etat, jour, avance, jamaisRealisee);
    return etat;
  }

  function raisonDate(etat, jour, avance, jamaisRealisee) {
    if (jamaisRealisee) return I18n.t('preventif.raison_date.jamais_realisee');
    if (etat.statut === 'echue' && etat.echeance < jour) return I18n.t('preventif.raison_date.echue_depuis', { echeance: UI.dateFr(etat.echeance) });
    if (etat.echeance === jour) return I18n.t('preventif.raison_date.echeance_aujourd_hui', { echeance: UI.dateFr(etat.echeance) });
    return I18n.t('preventif.raison_date.echeance_echeance', { echeance: UI.dateFr(etat.echeance) }) + (avance > 0 ? ' ' + I18n.t('preventif.raison_date.declenchement_avance', { declenchement: UI.dateFr(etat.declenchement), n: avance }) : '');
  }

  /**
   * Compteur et dernier relevé d'une gamme « compteur » ou « seuil », ou un état « incomplete »
   * qui dit ce qui manque : { compteur, releve } | { incomplet: etat }.
   */
  function compteurEtReleve(gamme, contexte) {
    const compteurId = texte(gamme.compteur_id);
    if (!compteurId) return { incomplet: etatDeBase('incomplete', I18n.t('preventif.compteur_et_releve.compteur_choisir')) };
    const compteur = Donnees.trouver('compteurs', compteurId);
    if (!compteur) return { incomplet: etatDeBase('incomplete', I18n.t('preventif.compteur_et_releve.compteur_introuvable', { compteurId })) };
    const releve = contexte.releves.get(compteurId);
    if (!releve) return { incomplet: etatDeBase('incomplete', I18n.t('preventif.compteur_et_releve.aucun_releve_compteur', { compteurId })) };
    return { compteur, releve };
  }

  /**
   * Déclencheur « compteur » : base = releve_derniere_realisation (0 si vide) ; échue si dernier
   * relevé − base ≥ periodicite_unites. Échéance estimée si le compteur compte des heures (sinon
   * vide) ; « bientôt » si cette estimation tombe dans les 14 jours.
   */
  function etatCompteur(gamme, jour, contexte) {
    const periodicite = nombre(gamme.periodicite_unites);
    if (periodicite === null || periodicite <= 0) return etatDeBase('incomplete', I18n.t('preventif.etat_compteur.periodicite_unites_renseigner'));
    const lu = compteurEtReleve(gamme, contexte);
    if (lu.incomplet) return lu.incomplet;
    const base = nombre(gamme.releve_derniere_realisation) || 0;
    const usage = arrondi(lu.releve.valeur - base, 6);
    const reste = arrondi(periodicite - usage, 6);
    const echeance = echeanceEstimee(gamme, lu.compteur, lu.releve, reste);

    let statut = 'a_jour';
    if (usage >= periodicite) statut = 'echue';
    else if (echeance && joursEntre(jour, echeance) <= HORIZON_BIENTOT_JOURS) statut = 'bientot';
    const etat = etatDeBase(statut, I18n.t('preventif.etat_compteur.valeur_avec_unite_periodicite', { valeurAvecUnite: valeurAvecUnite(usage, lu.compteur.unite), periodicite: UI.nombreFr(periodicite) }));
    etat.echeance = echeance;
    etat.declenchement = echeance;                     // pas d'avance : c'est le compteur qui déclenche
    etat.releveActuel = lu.releve.valeur;
    etat.reste = reste;                                // unités avant l'échéance (négatif : dépassée)
    return etat;
  }

  /**
   * Déclencheur « seuil » : échue si le dernier relevé ≥ seuil ET si ce relevé est postérieur à
   * derniere_realisation (sinon une gamme juste réalisée se redéclencherait aussitôt). Pas
   * d'échéance datée : jamais « bientôt ».
   */
  function etatSeuil(gamme, contexte) {
    const seuil = nombre(gamme.seuil);
    if (seuil === null) return etatDeBase('incomplete', I18n.t('preventif.etat_seuil.seuil_renseigner'));
    const lu = compteurEtReleve(gamme, contexte);
    if (lu.incomplet) return lu.incomplet;
    const unite = lu.compteur.unite;
    const derniere = texte(gamme.derniere_realisation).slice(0, 10);
    const atteint = lu.releve.valeur >= seuil;
    const posterieur = !derniere || lu.releve.date > derniere;
    const comparaison = I18n.t(atteint ? 'preventif.etat_seuil.releve_atteint_seuil' : 'preventif.etat_seuil.releve_sous_seuil',
      { releve: valeurAvecUnite(lu.releve.valeur, unite), seuil: valeurAvecUnite(seuil, unite) });

    const etat = etatDeBase(atteint && posterieur ? 'echue' : 'a_jour', comparaison);
    if (atteint && !posterieur) etat.raison += I18n.t('preventif.etat_seuil.releve_anterieur_derniere_realisation', { derniere: UI.dateFr(derniere) });
    etat.releveActuel = lu.releve.valeur;
    etat.reste = arrondi(seuil - lu.releve.valeur, 6);  // écart au seuil (négatif ou nul : atteint)
    return etat;
  }

  /** etatGamme avec un contexte déjà lu (voir contexteCalcul). */
  function evaluerGamme(gamme, aujourdhui, contexte) {
    const ligne = typeof gamme === 'string' ? Donnees.trouver('gammes', gamme) : gamme;
    if (!ligne) return etatDeBase('incomplete', I18n.t('preventif.evaluer_gamme.gamme_introuvable'));
    if (texte(ligne.actif) === '0') return etatDeBase('inactive', I18n.t('preventif.evaluer_gamme.gamme_inactive'));
    const jour = dateDuJour(aujourdhui);
    const declencheur = texte(ligne.declencheur) || 'date';

    let etat;
    if (declencheur === 'date') etat = etatDate(ligne, jour);
    else if (declencheur === 'compteur') etat = etatCompteur(ligne, jour, contexte);
    else if (declencheur === 'seuil') etat = etatSeuil(ligne, contexte);
    else etat = etatDeBase('incomplete', I18n.t('preventif.evaluer_gamme.declencheur_inconnu', { declencheur }));

    // Un OT ouvert pour cette gamme passe avant tout le reste : on n'en génère pas un second.
    const otOuvert = contexte.otsOuverts.get(ligne.id);
    if (otOuvert) {
      etat.statut = 'ot_ouvert';
      etat.otOuvertId = otOuvert.id;
      etat.raison = I18n.t('preventif.evaluer_gamme.ot_ouvert_statut', { otId: otOuvert.id, statut: Schema.libelleValeur('ordres_travail', 'statut', otOuvert.statut) });
    }
    return etat;
  }

  /**
   * État d'une gamme à une date (RG5). gamme : ligne de gammes (ou son identifiant).
   * → { statut, echeance, declenchement, raison, otOuvertId, releveActuel, reste }
   *   statut : inactive | ot_ouvert | echue | bientot | a_jour | incomplete (voir STATUTS_GAMME) ;
   *   echeance, declenchement : dates ISO ou '' ; raison : phrase courte en français ;
   *   releveActuel : dernier relevé (compteur, seuil) ou null ;
   *   reste : jours avant l'échéance (date), unités avant l'échéance (compteur), écart au seuil (seuil).
   */
  function etatGamme(gamme, aujourdhui) {
    return evaluerGamme(gamme, aujourdhui, contexteCalcul());
  }

  // ===========================================================================================
  // 4. Calendrier des prochaines semaines
  // ===========================================================================================

  /** Nombre de semaines demandé, sinon le paramètre horizon_calendrier_semaines, sinon 12. */
  function nombreDeSemaines(semaines) {
    const demande = semaines === undefined || semaines === null
      ? nombre(Donnees.parametre('horizon_calendrier_semaines', '')) : nombre(semaines);
    return demande !== null && demande >= 1 ? Math.floor(demande) : SEMAINES_PAR_DEFAUT;
  }

  /**
   * Éléments à placer : échéance de chaque gamme active sans OT ouvert (estimée pour un compteur),
   * et chaque OT préventif ouvert à sa date prévue. [{ gammeId, equipementId, date, estimee, otId }]
   */
  function elementsDuCalendrier(jour) {
    const contexte = contexteCalcul();
    const elements = [];
    Donnees.lignes('gammes').forEach((gamme) => {
      if (texte(gamme.actif) === '0') return;
      const etat = evaluerGamme(gamme, jour, contexte);
      if (etat.statut === 'ot_ouvert' || !etat.echeance) return;   // l'OT ouvert est placé ci-dessous
      elements.push({ gammeId: gamme.id, equipementId: gamme.equipement_id, date: etat.echeance,
        estimee: texte(gamme.declencheur) === 'compteur', otId: '' });
    });
    Donnees.lignes('ordres_travail').forEach((ot) => {
      const date = texte(ot.date_prevue).slice(0, 10);
      if (!estOuvert(ot) || !estOtPreventif(ot) || !estDateIso(date)) return;
      elements.push({ gammeId: texte(ot.gamme_id), equipementId: ot.equipement_id, date, estimee: false, otId: ot.id });
    });
    return elements;
  }

  function comparerElements(a, b) {
    if (a.date !== b.date) return a.date < b.date ? -1 : 1;
    return (a.otId + a.gammeId).localeCompare(b.otId + b.gammeId, 'fr', { numeric: true });
  }

  /**
   * Calendrier de `semaines` semaines (lundi → dimanche) à partir de la semaine d'aujourd'hui :
   * [{ lundi, dimanche, elements: [{ gammeId, equipementId, date, estimee, otId }] }].
   * Un élément en retard (date avant le premier lundi) est placé dans la première semaine avec
   * sa vraie date ; un élément après le dernier dimanche n'est pas placé.
   */
  function calendrier(aujourdhui, semaines) {
    const jour = dateDuJour(aujourdhui);
    const premierLundi = lundiDe(jour);
    const nombreSemaines = nombreDeSemaines(semaines);
    const liste = [];
    for (let numero = 0; numero < nombreSemaines; numero += 1) {
      const lundi = ajouterJours(premierLundi, 7 * numero);
      liste.push({ lundi, dimanche: ajouterJours(lundi, 6), elements: [] });
    }
    const dernierDimanche = liste[liste.length - 1].dimanche;
    elementsDuCalendrier(jour).forEach((element) => {
      if (element.date > dernierDimanche) return;
      const position = element.date < premierLundi ? 0 : Math.floor(joursEntre(premierLundi, element.date) / 7);
      liste[position].elements.push(element);
    });
    liste.forEach((semaine) => semaine.elements.sort(comparerElements));
    return liste;
  }

  return {
    DECLENCHEURS, STATUTS_GAMME,
    // règles pures (ARCHITECTURE.md §14.3)
    dernierReleve, etatGamme, calendrier,
    // Usage interne au module : outils prêtés aux fichiers preventif-*.js, qui y ajoutent les
    // leurs par Object.assign(Preventif.interne, …). Pas une API : son contenu peut changer.
    interne: {
      HORIZON_BIENTOT_JOURS,
      texte, nombre, arrondi, estDateIso, ajouterJours, joursEntre, lundiDe, dateDuJour,
      estOuvert, estOtPreventif, contexteCalcul, evaluerGamme, estUniteHeure, heuresParJour, echeanceEstimee,
      otsOuvertsParGamme, nombreDeSemaines,
    },
  };
})();
