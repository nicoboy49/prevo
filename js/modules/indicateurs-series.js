'use strict';
// Indicateurs (2/4) — séries des graphiques de l'écran Indicateurs et du rapport mensuel : Pareto
// des pannes et des arrêts, heures par mois, MTBF et MTTR des équipements A, causes des pannes,
// charge et capacité des techniciens (ARCHITECTURE.md §15.3) ; coût de l'arrêt (2.2, D188, CS174 :
// §8 ci-dessous). Règles PURES, comme indicateurs-regles.js, dont ce fichier reprend les outils
// (Indicateurs.interne).

Object.assign(Indicateurs, (() => {

  const {
    TYPES_CORRECTIFS, TYPES_PREVENTIFS, texte, nombre, nombreOuZero, arrondi, jourDe, ajouterJours, ajouterMois,
    contexte, grouper, ordresFiltres, estSuivi, passeFiltres,
  } = Indicateurs.interne;
  const { pannes, parEquipement } = Indicateurs;

  /** Un filtre criticité ou atelier est-il actif ? (une panne d'équipement introuvable est alors écartée) */
  function aDesFiltres(filtres) {
    return Boolean(filtres && (filtres.criticite || filtres.atelier));
  }

  // ===========================================================================================
  // 7. Séries des graphiques
  // ===========================================================================================

  /** Pareto : les n premiers équipements selon `mesure(pannes)`, avec le cumul en % du total. */
  function pareto(periodeChoisie, n, mesure, filtres) {
    const ctx = contexte();
    const parEquipementId = grouper(pannes(periodeChoisie, {}, ctx).map((panne) => Object.assign({ equipement_id: panne.ot.equipement_id }, panne)), 'equipement_id');
    const lignes = [];
    parEquipementId.forEach((liste, equipementId) => {
      const equipement = ctx.equipements.get(equipementId);
      if (equipement ? !passeFiltres(equipement, filtres, ctx) : aDesFiltres(filtres)) return;
      lignes.push({ equipementId, valeur: mesure(liste), ots: liste.map((panne) => panne.ot.id) });
    });
    const triees = lignes.filter((ligne) => ligne.valeur > 0).sort((a, b) => b.valeur - a.valeur || a.equipementId.localeCompare(b.equipementId));
    const total = triees.reduce((somme, ligne) => somme + ligne.valeur, 0);
    let cumul = 0;
    return triees.slice(0, n || 10).map((ligne) => {
      cumul += ligne.valeur;
      return Object.assign(ligne, { cumulPct: total ? cumul / total * 100 : 0 });
    });
  }

  function paretoPannes(periodeChoisie, n, filtres) {
    return pareto(periodeChoisie, n, (liste) => liste.length, filtres);
  }

  function paretoArrets(periodeChoisie, n, filtres) {
    return pareto(periodeChoisie, n, (liste) => liste.reduce((somme, panne) => somme + (panne.duree || 0), 0), filtres);
  }

  /** Heures passées par mois (12 mois finissant par dernierMois 'AAAA-MM') : correctif,
   *  préventif, autres (amélioration, réglementaire). */
  function heuresParMois(dernierMois, nbMois, filtres) {
    const ctx = contexte();
    const nombreMois = nbMois || 12;
    const premier = ajouterMois(dernierMois + '-01', -(nombreMois - 1));
    const mois = [];
    for (let rang = 0; rang < nombreMois; rang += 1) mois.push(ajouterMois(premier, rang).slice(0, 7));
    const series = new Map(mois.map((cle) => [cle, { mois: cle, correctif: 0, preventif: 0, autres: 0 }]));
    ordresFiltres(filtres, ctx).filter((ot) => texte(ot.statut) !== 'Annulé').forEach((ot) => {
      const groupe = TYPES_CORRECTIFS.includes(texte(ot.type)) ? 'correctif' : (TYPES_PREVENTIFS.includes(texte(ot.type)) ? 'preventif' : 'autres');
      (ctx.tempsParOt.get(ot.id) || []).forEach((ligne) => {
        const element = series.get(jourDe(ligne.date).slice(0, 7));
        if (element) element[groupe] += nombreOuZero(ligne.heures);
      });
    });
    return mois.map((cle) => {
      const element = series.get(cle);
      return { mois: cle, correctif: arrondi(element.correctif), preventif: arrondi(element.preventif), autres: arrondi(element.autres) };
    });
  }

  /** MTBF et MTTR des équipements suivis de criticité A : [{ equipementId, mtbf, mttr }]. */
  function mtbfMttrCriticiteA(periodeChoisie) {
    const ctx = contexte();
    return Array.from(ctx.equipements.values())
      .filter((equipement) => estSuivi(equipement) && texte(equipement.criticite) === 'A')
      .sort((a, b) => texte(a.repere).localeCompare(texte(b.repere), 'fr', { numeric: true }))
      .map((equipement) => {
        const indicateurs = parEquipement(equipement.id, periodeChoisie, ctx);
        return { equipementId: equipement.id, mtbf: indicateurs.mtbf, mttr: indicateurs.mttr };
      });
  }

  /** Causes des pannes de la période : [{ code, libelle, nombre }], décroissant ; « sans code » à la fin. */
  function causes(periodeChoisie, filtres) {
    const ctx = contexte();
    const libelles = new Map(Donnees.lignes('codes_defaillance').filter((code) => texte(code.famille) === 'cause')
      .map((code) => [texte(code.code), texte(code.libelle)]));
    const compte = new Map();
    pannes(periodeChoisie, {}, ctx).forEach((panne) => {
      const equipement = ctx.equipements.get(texte(panne.ot.equipement_id));
      if (equipement ? !passeFiltres(equipement, filtres, ctx) : aDesFiltres(filtres)) return;
      const code = texte(panne.ot.cause_code);
      compte.set(code, (compte.get(code) || 0) + 1);
    });
    const lignes = Array.from(compte, ([code, total]) => ({ code, libelle: code ? (libelles.get(code) || code) : I18n.t('indicateurs.causes.sans_code'), nombre: total }));
    return lignes.filter((ligne) => ligne.code).sort((a, b) => b.nombre - a.nombre || UI.comparerTextes(a.libelle, b.libelle))
      .concat(lignes.filter((ligne) => !ligne.code));
  }

  /** Charge et capacité de chaque technicien actif sur `n` semaines à partir de `lundi`
   *  (délègue à Planning.chargeSemaine ; [] si le planning n'est pas disponible). */
  function chargeCapacite(lundi, n) {
    if (typeof Planning === 'undefined' || typeof Planning.chargeSemaine !== 'function') return [];
    const premier = Planning.lundiDe(lundi);
    const semaines = [];
    for (let rang = 0; rang < (n || 4); rang += 1) semaines.push(ajouterJours(premier, 7 * rang));
    return Donnees.lignes('techniciens').filter((technicien) => texte(technicien.actif) !== '0')
      .sort((a, b) => UI.comparerTextes(texte(a.nom) + ' ' + texte(a.prenom), texte(b.nom) + ' ' + texte(b.prenom)))
      .map((technicien) => ({
        technicien,
        semaines: semaines.map((debut) => ({ lundi: debut, charge: Planning.chargeSemaine(technicien.id, debut), capacite: nombre(technicien.capacite_h_semaine) })),
      }));
  }

  // ===========================================================================================
  // 8. Coût de l'arrêt (D188, CS174) : Σ durées d'arrêt des pannes × coût d'une heure d'arrêt
  //    (equipements.cout_arret_h, valeur actuelle de la fiche), au centime, SANS FLOTTANT.
  //    Aucun coût horaire par défaut : un équipement sans coût est « non chiffré », une panne
  //    sans durée n'est pas comptée ; tous deux sont listés, jamais estimés. 0 saisi = chiffré à 0.
  // ===========================================================================================

  const STATUTS_CLOTURES = ['Clôturé techniquement', 'Clôturé administrativement'];
  const DIX_MILLIEMES_PAR_HEURE = 10000;

  /**
   * Décimal du fichier → entier à l'échelle 10^decimales, lu dans la forme normalisée de Donnees
   * (« 1 234,5 » → « 1234.5 ») chiffre à chiffre : jamais de flottant. Au-delà de `decimales`
   * décimales : arrondi moitié vers le haut. null si vide, illisible ou négatif.
   */
  function entierALEchelle(valeur, decimales) {
    const lu = Donnees.normaliser.decimal(typeof valeur === 'number' ? String(valeur) : valeur);
    const morceaux = lu.ok ? /^(-?)(\d+)(?:\.(\d*))?$/.exec(lu.valeur) : null;
    if (!morceaux) return null;
    const fraction = morceaux[3] || '';
    if (morceaux[1] === '-' && /[1-9]/.test(morceaux[2] + fraction)) return null;
    let entier = Number(morceaux[2] + (fraction + '0'.repeat(decimales)).slice(0, decimales));
    if (fraction.charAt(decimales) >= '5') entier += 1;
    return Number.isSafeInteger(entier) ? entier : null;
  }

  /** Coût d'une heure d'arrêt en centimes (« 87,35 » → 8735), ou null : non chiffré. */
  function centimesDuCoutHoraire(valeur) {
    return entierALEchelle(valeur, 2);
  }

  /** Durée d'arrêt en dix-millièmes d'heure (« 0,3333 » → 3333), ou null : sans durée. */
  function dixMilliemesDHeure(valeur) {
    return entierALEchelle(valeur, 4);
  }

  /** Centimes de (dixMilliemes / 10 000) h × centimesParHeure, arrondis une fois au centime, moitié
   *  vers le haut. Heures entières et reste séparés, division entière exacte (aucun flottant). */
  function centimesDeLArret(dixMilliemes, centimesParHeure) {
    const reste = dixMilliemes % DIX_MILLIEMES_PAR_HEURE;
    const heuresEntieres = (dixMilliemes - reste) / DIX_MILLIEMES_PAR_HEURE;
    const produit = reste * centimesParHeure + DIX_MILLIEMES_PAR_HEURE / 2;
    return heuresEntieres * centimesParHeure + (produit - produit % DIX_MILLIEMES_PAR_HEURE) / DIX_MILLIEMES_PAR_HEURE;
  }

  /**
   * Coût de l'arrêt des pannes de la période (Indicateurs.pannes : mêmes OT que le Pareto des
   * arrêts ; équipements au rebut ou désactivés compris) →
   * { totalCentimes, total, parEquipement, nonChiffres, sansDuree, complet }.
   * parEquipement : [{ equipementId, heures, coutHoraireCentimes, centimes, ots }], équipements
   * chiffrés ayant au moins une panne avec durée, par coût décroissant ; nonChiffres :
   * [{ equipementId, heures, ots }], équipements avec une panne et sans coût horaire lisible
   * (introuvable compris), par heures décroissantes ; ots = pannes dont les heures sont comptées ;
   * sansDuree : [{ otId, equipementId, raison }], par date de panne. total = totalCentimes / 100 ;
   * totalCentimes = somme des lignes ; complet = rien de non chiffré ni de sans durée.
   */
  function coutArret(periodeChoisie, filtres) {
    const ctx = contexte();
    const parEquipementId = new Map();
    const sansDuree = [];
    pannes(periodeChoisie, {}, ctx).forEach((panne) => {
      const equipementId = texte(panne.ot.equipement_id);
      const equipement = ctx.equipements.get(equipementId);
      if (equipement ? !passeFiltres(equipement, filtres, ctx) : aDesFiltres(filtres)) return;
      if (!parEquipementId.has(equipementId)) parEquipementId.set(equipementId, { equipementId, equipement, dixMilliemes: 0, ots: [] });
      const element = parEquipementId.get(equipementId);
      const duree = dixMilliemesDHeure(panne.ot.duree_arret_h);
      if (duree === null) {
        const raison = STATUTS_CLOTURES.includes(texte(panne.ot.statut))
          ? I18n.t('indicateurs.cout_arret.sans_duree_arret') : I18n.t('indicateurs.cout_arret.non_cloture');
        sansDuree.push({ otId: panne.ot.id, equipementId, raison });
        return;
      }
      element.dixMilliemes += duree;
      element.ots.push(panne.ot.id);
    });
    const chiffres = [];
    const nonChiffres = [];
    parEquipementId.forEach((element) => {
      const heures = element.dixMilliemes / DIX_MILLIEMES_PAR_HEURE;
      const coutHoraire = element.equipement ? centimesDuCoutHoraire(element.equipement.cout_arret_h) : null;
      if (coutHoraire === null) nonChiffres.push({ equipementId: element.equipementId, heures, ots: element.ots });
      else if (element.ots.length) {
        chiffres.push({ equipementId: element.equipementId, heures, coutHoraireCentimes: coutHoraire,
          centimes: centimesDeLArret(element.dixMilliemes, coutHoraire), ots: element.ots });
      }
    });
    chiffres.sort((a, b) => b.centimes - a.centimes || b.heures - a.heures || a.equipementId.localeCompare(b.equipementId));
    nonChiffres.sort((a, b) => b.heures - a.heures || a.equipementId.localeCompare(b.equipementId));
    const totalCentimes = chiffres.reduce((somme, ligne) => somme + ligne.centimes, 0);
    return { totalCentimes, total: totalCentimes / 100, parEquipement: chiffres, nonChiffres, sansDuree,
      complet: nonChiffres.length === 0 && sansDuree.length === 0 };
  }

  /** Pareto du coût de l'arrêt : les n premiers (10 par défaut) équipements chiffrés à plus de 0 €,
   *  [{ equipementId, valeur (€), centimes, heures, cumulPct, ots }], cumul en % du total. */
  function paretoCoutArret(periodeChoisie, n, filtres) {
    const calcul = coutArret(periodeChoisie, filtres);
    let cumul = 0;
    return calcul.parEquipement.filter((ligne) => ligne.centimes > 0).slice(0, n || 10).map((ligne) => {
      cumul += ligne.centimes;
      return { equipementId: ligne.equipementId, valeur: ligne.centimes / 100, centimes: ligne.centimes, heures: ligne.heures,
        cumulPct: calcul.totalCentimes ? cumul / calcul.totalCentimes * 100 : 0, ots: ligne.ots };
    });
  }

  Object.assign(Indicateurs.interne, { centimesDuCoutHoraire, dixMilliemesDHeure });

  return { paretoPannes, paretoArrets, heuresParMois, mtbfMttrCriticiteA, causes, chargeCapacite, coutArret, paretoCoutArret };
})());
