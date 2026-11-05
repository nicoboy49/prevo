'use strict';
// Indicateurs (2/4) — séries des graphiques de l'écran Indicateurs et du rapport mensuel : Pareto
// des pannes et des arrêts, heures par mois, MTBF et MTTR des équipements A, causes des pannes,
// charge et capacité des techniciens (ARCHITECTURE.md §15.3). Règles PURES, comme
// indicateurs-regles.js, dont ce fichier reprend les outils (Indicateurs.interne).

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
    return lignes.filter((ligne) => ligne.code).sort((a, b) => b.nombre - a.nombre || a.libelle.localeCompare(b.libelle, 'fr'))
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
      .sort((a, b) => (texte(a.nom) + ' ' + texte(a.prenom)).localeCompare(texte(b.nom) + ' ' + texte(b.prenom), 'fr'))
      .map((technicien) => ({
        technicien,
        semaines: semaines.map((debut) => ({ lundi: debut, charge: Planning.chargeSemaine(technicien.id, debut), capacite: nombre(technicien.capacite_h_semaine) })),
      }));
  }

  return { paretoPannes, paretoArrets, heuresParMois, mtbfMttrCriticiteA, causes, chargeCapacite };
})());
