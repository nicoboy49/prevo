'use strict';
// Planning : planning de la semaine par technicien, avec la charge comparée à la capacité
// (écran E6 ; ARCHITECTURE.md §15.5 ; brief §9 E6, §7 RG3 et RG8).
//
// Le module est découpé en trois fichiers, chargés dans cet ordre par index.html (§15.1) :
//   planning-regles.js     CE FICHIER, qui crée l'objet Planning : règles PURES
//                            1. Constantes et petits outils (dates ISO de la semaine)
//                            2. OT de la semaine, charge d'un technicien, grille de la semaine
//   planning-ecritures.js  planifier (RG3, RG8, journal)
//   planning-ecrans.js     écran #/planning : grille, glisser-déposer, bouton « Planifier… »
//
// Les fichiers suivants complètent l'objet : Object.assign(Planning, (() => { … })()). Une
// fonction dont un autre fichier du module a besoin est rangée dans Planning.interne (pas une API).
//
// La semaine va du lundi au dimanche. Les dates sont des chaînes ISO 'AAAA-MM-JJ', calculées en
// UTC (une semaine qui traverse un changement d'heure garde ses sept jours).

const Planning = (() => {

  // ===========================================================================================
  // 1. Constantes et petits outils
  // ===========================================================================================

  const STATUTS_FERMES = ['Clôturé techniquement', 'Clôturé administrativement', 'Annulé'];
  const RANG_PRIORITE = { P1: 1, P2: 2, P3: 3, P4: 4 };
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

  function dateDepuisNumero(numero) {
    const date = new Date(numero * MILLISECONDES_PAR_JOUR);
    return date.getUTCFullYear() + '-' + String(date.getUTCMonth() + 1).padStart(2, '0')
      + '-' + String(date.getUTCDate()).padStart(2, '0');
  }

  /** Lundi de la semaine d'une date (par défaut aujourd'hui). */
  function lundiDe(dateIso) {
    const numero = numeroJour(dateIso) === null ? numeroJour(Donnees.aujourdhui()) : numeroJour(dateIso);
    const jourSemaine = new Date(numero * MILLISECONDES_PAR_JOUR).getUTCDay();   // 0 = dimanche
    return dateDepuisNumero(numero - ((jourSemaine + 6) % 7));
  }

  /** Les sept dates ISO de la semaine qui contient `lundi` (ramené au lundi s'il ne l'est pas). */
  function joursDeLaSemaine(lundi) {
    const premier = numeroJour(lundiDe(lundi));
    return [0, 1, 2, 3, 4, 5, 6].map((decalage) => dateDepuisNumero(premier + decalage));
  }

  function estOuvert(ot) {
    return !STATUTS_FERMES.includes(texte(ot.statut));
  }

  function heures(valeur) {
    const nombre = Donnees.nombre(valeur);
    return nombre === null || nombre < 0 ? 0 : nombre;
  }

  /** Ordre d'affichage des OT : priorité (P1 d'abord, sans priorité à la fin), date prévue
   *  (sans date à la fin), identifiant. */
  function comparerOt(a, b) {
    return ((RANG_PRIORITE[texte(a.priorite)] || 9) - (RANG_PRIORITE[texte(b.priorite)] || 9))
      || (texte(a.date_prevue) || '9999').localeCompare(texte(b.date_prevue) || '9999')
      || texte(a.id).localeCompare(texte(b.id), 'fr', { numeric: true });
  }

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
  // 2. OT de la semaine, charge d'un technicien, grille de la semaine
  // ===========================================================================================

  /**
   * OT de la grille d'une semaine : ni clôturés ni annulés, avec un technicien et une date prévue
   * entre le lundi et le dimanche. Triés par priorité, date prévue, identifiant.
   */
  function ordresDeLaSemaine(lundi) {
    // Les sept dates réelles de la semaine : une date impossible (« 2026-02-30 », gardée telle
    // quelle par la lecture tolérante) n'est jamais prise pour un jour de la semaine.
    const jours = new Set(joursDeLaSemaine(lundi));
    return Donnees.lignes('ordres_travail').filter((ot) => {
      const date = texte(ot.date_prevue).slice(0, 10);
      return estOuvert(ot) && texte(ot.technicien_id) !== '' && jours.has(date);
    }).sort(comparerOt);
  }

  /** Charge d'un technicien pour une semaine : Σ temps prévus (heures ; vide = 0) de ses OT de la grille. */
  function chargeSemaine(technicienId, lundi) {
    return ordresDeLaSemaine(lundi)
      .filter((ot) => texte(ot.technicien_id) === texte(technicienId))
      .reduce((total, ot) => total + heures(ot.temps_prevu_h), 0);
  }

  /** Ligne de la grille pour un technicien : OT rangés par jour, charge, capacité, surcharge. */
  function ligneDuTechnicien(technicien, ordres, jours, options) {
    const cases = {};
    jours.forEach((jour) => { cases[jour] = []; });
    const siens = ordres.filter((ot) => texte(ot.technicien_id) === texte(technicien.id));
    siens.forEach((ot) => { cases[texte(ot.date_prevue).slice(0, 10)].push(ot); });
    const charge = siens.reduce((total, ot) => total + heures(ot.temps_prevu_h), 0);
    const capacite = Donnees.nombre(technicien.capacite_h_semaine);
    return Object.assign({
      technicien, cases, charge, capacite,
      surcharge: capacite !== null && charge > capacite,
    }, options || {});
  }

  /**
   * Grille d'une semaine : { lundi, jours, lignes, aPlanifier }.
   *   lignes     : une par technicien actif (par nom), puis, s'il y en a, une par technicien
   *                inactif ou inconnu qui a encore des OT cette semaine (inactif: true) ;
   *   aPlanifier : OT « Préparé » absents de la grille de cette semaine (sans technicien, sans
   *                date, ou prévus une autre semaine), par priorité puis date prévue.
   */
  function semaine(lundi) {
    const jours = joursDeLaSemaine(lundi);
    const ordres = ordresDeLaSemaine(jours[0]);
    const techniciens = Donnees.lignes('techniciens');
    const actifs = techniciens.filter((technicien) => texte(technicien.actif) !== '0')
      .sort(ordreDesNoms);
    const idsActifs = new Set(actifs.map((technicien) => texte(technicien.id)));
    const lignes = actifs.map((technicien) => ligneDuTechnicien(technicien, ordres, jours));
    const autres = Array.from(new Set(ordres.map((ot) => texte(ot.technicien_id)).filter((id) => !idsActifs.has(id)))).sort();
    autres.forEach((id) => {
      const technicien = techniciens.find((ligne) => texte(ligne.id) === id) || { id, nom: id, prenom: '', capacite_h_semaine: '' };
      lignes.push(ligneDuTechnicien(technicien, ordres, jours, { inactif: true }));
    });
    const dansLaGrille = new Set(ordres.map((ot) => ot.id));
    const aPlanifier = Donnees.lignes('ordres_travail')
      .filter((ot) => texte(ot.statut) === 'Préparé' && !dansLaGrille.has(ot.id))
      .sort(comparerOt);
    return { lundi: jours[0], jours, lignes, aPlanifier };
  }

  return {
    // règles pures (ARCHITECTURE.md §15.5)
    lundiDe, joursDeLaSemaine, ordresDeLaSemaine, chargeSemaine, semaine,
    // Usage interne au module (pas une API).
    interne: { texte, estOuvert, heures, comparerOt, nomComplet, ordreDesNoms, numeroJour, dateDepuisNumero },
  };
})();
