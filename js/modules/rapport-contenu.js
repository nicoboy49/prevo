'use strict';
// Rapport : rapport mensuel figé — une page A4 pour la direction : trois tuiles comparées au mois
// précédent et à l'année précédente, faits marquants, décisions proposées, deux graphiques, encadré
// « Comprendre » (ARCHITECTURE.md §15.10 ; CDC du lot 3, D43 à D45).
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

const Rapport = (() => {

  // ===========================================================================================
  // 1. Petits outils
  // ===========================================================================================

  const NOMS_MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];
  const COULEURS_SERIES = ['#2F5BD3', '#A86A12', '#6B7280'];     // impression sur blanc : bleu, ocre, gris
  const PREFIXE_FICHIER = 'rapport-mensuel-';

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  /** 'AAAA-MM' + n mois (n négatif possible). */
  function decalerMois(mois, n) {
    const total = Number(mois.slice(0, 4)) * 12 + Number(mois.slice(5, 7)) - 1 + n;
    const annee = Math.floor(total / 12);
    return annee + '-' + String(total - annee * 12 + 1).padStart(2, '0');
  }

  /** '2026-09' → « septembre 2026 ». */
  function libelleMois(mois) {
    return NOMS_MOIS[Number(mois.slice(5, 7)) - 1] + ' ' + mois.slice(0, 4);
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
    if (valeur === null || valeur === undefined) return 'non calculable';
    return cle === 'cout' ? UI.euro(valeur, 0) : pourcentage(valeur);
  }

  /**
   * Comparaison d'une valeur à une valeur de référence : { sens, texte } ; sens ∈ 'hausse',
   * 'baisse', 'stable', null (non comparable ou non calculable). Taux : écart en points ; coût :
   * écart relatif en %.
   */
  function comparer(cle, valeur, reference, comparable, libelleReference) {
    if (!comparable) return { sens: null, texte: 'non comparable avec ' + libelleReference + ' (historique trop court)' };
    if (valeur === null || reference === null) return { sens: null, texte: 'non calculable pour ' + libelleReference };
    if (cle === 'cout') {
      if (reference === 0) {
        return valeur === 0 ? { sens: 'stable', texte: 'stable par rapport à ' + libelleReference }
          : { sens: 'hausse', texte: 'en hausse (' + libelleReference + ' : 0 €)' };
      }
      const ecart = (valeur - reference) / reference * 100;
      if (Math.abs(ecart) < 0.5) return { sens: 'stable', texte: 'stable par rapport à ' + libelleReference };
      return { sens: ecart > 0 ? 'hausse' : 'baisse',
        texte: (ecart > 0 ? 'en hausse de ' : 'en baisse de ') + UI.nombreFr(Math.abs(ecart), 0) + ' % par rapport à ' + libelleReference };
    }
    const points = (valeur - reference) * 100;
    if (Math.abs(points) < 0.05) return { sens: 'stable', texte: 'stable par rapport à ' + libelleReference };
    return { sens: points > 0 ? 'hausse' : 'baisse',
      texte: (points > 0 ? 'en hausse de ' : 'en baisse de ') + UI.nombreFr(Math.abs(points), 1) + ' point(s) par rapport à ' + libelleReference };
  }

  // ===========================================================================================
  // 2. Données du rapport (pures)
  // ===========================================================================================

  const TUILES = [
    { cle: 'disponibilite', libelle: 'Disponibilité', hausseFavorable: true, lire: (g) => g.disponibilite },
    { cle: 'cout', libelle: 'Coût de maintenance du mois', hausseFavorable: false, lire: (g) => g.cout },
    { cle: 'partPreventif', libelle: 'Part du préventif (heures)', hausseFavorable: true, lire: (g) => g.partPreventif },
  ];

  function faitsMarquants(periode, global, aujourdhui) {
    const faits = [];
    const pannes = Indicateurs.pannes(periode).filter((panne) => panne.duree !== null);
    if (pannes.length) {
      const longue = pannes.reduce((a, b) => (b.duree > a.duree ? b : a));
      faits.push('Plus long arrêt : ' + repere(longue.ot.equipement_id) + ', ' + UI.heures(longue.duree) + ' (' + longue.ot.id + ').');
    }
    const plusSouvent = Indicateurs.paretoPannes(periode, 1)[0];
    if (plusSouvent && plusSouvent.valeur >= 2) {
      faits.push(repere(plusSouvent.equipementId) + ' : ' + plusSouvent.valeur + ' pannes dans le mois.');
    }
    const enRetard = Donnees.lignes('controles_reglementaires').filter((controle) => Controles.interne.equipementSuivi(controle) && Controles.etat(controle, aujourdhui).statut === 'en retard');
    if (enRetard.length) faits.push(enRetard.length + ' contrôle(s) réglementaire(s) en retard au ' + UI.dateFr(aujourdhui) + '.');
    else if (global.otEnRetard.valeur) faits.push(global.otEnRetard.valeur + ' OT en retard au ' + UI.dateFr(aujourdhui) + '.');
    if (!faits.length) faits.push('Aucune panne avec arrêt de production ce mois-ci.');
    return faits.slice(0, 3);
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
    return { decision: meilleur && (repere(meilleur.equipementId) + ' : ' + UI.euro(meilleur.cout, 0) + ' de maintenance sur 12 mois, soit '
      + UI.nombreFr(meilleur.ratio, 0) + ' % de sa valeur de remplacement (' + UI.euro(meilleur.valeur, 0) + ') — réparer ou remplacer ? À examiner.'),
    sansValeur, seuil };
  }

  function decisions(mois, aujourdhui, remplacement) {
    const liste = [];
    if (remplacement.decision) liste.push(remplacement.decision);
    const enRetard = Donnees.lignes('controles_reglementaires').filter((controle) => Controles.interne.equipementSuivi(controle) && Controles.etat(controle, aujourdhui).statut === 'en retard');
    if (enRetard.length) {
      liste.push('Planifier ' + (enRetard.length > 1 ? 'les ' + enRetard.length + ' contrôles réglementaires en retard' : 'le contrôle réglementaire en retard')
        + ' : ' + enRetard.slice(0, 3).map((controle) => texte(controle.nature) + ' (' + repere(controle.equipement_id) + ')').join(' ; ') + '.');
    }
    const aCommander = Magasin.aCommander();
    if (aCommander.length) {
      const critiques = aCommander.filter((element) => texte(element.article.critique) === '1').length;
      liste.push('Commander ' + aCommander.length + ' article(s) sous le point de commande' + (critiques ? ', dont ' + critiques + ' critique(s)' : '') + '.');
    }
    return liste.slice(0, 3);
  }

  /**
   * Données du rapport d'un mois 'AAAA-MM', calculées à la date `aujourdhui` (date de génération,
   * qui sert aux retards) : { mois, libelleMois, genereLe, entreprise, tuiles, faits, decisions,
   * pareto, heures12Mois, nonCalculables, comprendre, courriel }.
   */
  function donnees(mois, aujourdhui, maintenant) {
    const jour = /^\d{4}-\d{2}-\d{2}$/.test(texte(aujourdhui).slice(0, 10)) ? texte(aujourdhui).slice(0, 10) : Donnees.aujourdhui();
    const periode = Indicateurs.periodeDuMois(mois);
    const global = Indicateurs.global(periode, {}, jour);
    const precedent = decalerMois(mois, -1);
    const anneePrecedente = decalerMois(mois, -12);
    const globalPrecedent = estCouvert(precedent) ? Indicateurs.global(Indicateurs.periodeDuMois(precedent), {}, jour) : null;
    const globalAnnee = estCouvert(anneePrecedente) ? Indicateurs.global(Indicateurs.periodeDuMois(anneePrecedente), {}, jour) : null;
    const tuiles = TUILES.map((tuile) => {
      const resultat = tuile.lire(global);
      const valeurPrecedente = globalPrecedent ? tuile.lire(globalPrecedent).valeur : null;
      const valeurAnnee = globalAnnee ? tuile.lire(globalAnnee).valeur : null;
      return {
        cle: tuile.cle, libelle: tuile.libelle, hausseFavorable: tuile.hausseFavorable,
        valeur: resultat.valeur, raison: resultat.raison, texteValeur: formater(tuile.cle, resultat.valeur),
        precedent: valeurPrecedente, anneePrecedente: valeurAnnee,
        tendance: {
          precedent: comparer(tuile.cle, resultat.valeur, valeurPrecedente, Boolean(globalPrecedent), libelleMois(precedent)),
          annee: comparer(tuile.cle, resultat.valeur, valeurAnnee, Boolean(globalAnnee), libelleMois(anneePrecedente)),
        },
      };
    });
    const remplacement = reparerOuRemplacer(mois);
    const nonCalculables = tuiles.filter((tuile) => tuile.valeur === null).map((tuile) => ({ libelle: tuile.libelle, raison: tuile.raison }));
    if (global.tempsRequis.exclus.length) {
      nonCalculables.push({ libelle: 'Équipements hors disponibilité', raison: global.tempsRequis.exclus.length + ' équipement(s) sans heures de fonctionnement par jour : '
        + global.tempsRequis.exclus.slice(0, 6).map((element) => repere(element.id)).join(', ') + (global.tempsRequis.exclus.length > 6 ? '…' : '') });
    }
    if (remplacement.sansValeur.length) {
      nonCalculables.push({ libelle: 'Réparer ou remplacer', raison: 'valeur de remplacement non renseignée pour ' + remplacement.sansValeur.length + ' équipement(s) avec des coûts : '
        + remplacement.sansValeur.slice(0, 6).map(repere).join(', ') });
    }
    const resultat = {
      mois, libelleMois: libelleMois(mois), genereLe: texte(maintenant) || Donnees.maintenant(),
      entreprise: texte(Donnees.parametre('entreprise_nom', '')),
      tuiles, faits: faitsMarquants(periode, global, jour), decisions: decisions(mois, jour, remplacement),
      pareto: Indicateurs.paretoArrets(periode, 5).map((ligne) => ({ repere: repere(ligne.equipementId), heures: ligne.valeur })),
      heures12Mois: Indicateurs.heuresParMois(mois, 12),
      mttr: global.mttr, attentePieces: global.attentePieces, seuilRemplacement: remplacement.seuil,
      nonCalculables,
      comprendre: [
        ['Disponibilité', 'MTBF / (MTBF + MTTR) : la part du temps de fonctionnement prévu pendant laquelle les équipements ont réellement tourné.'],
        ['Panne', 'OT correctif avec arrêt de production, daté par la demande d\'intervention.'],
        ['MTTR', 'durée d\'arrêt moyenne d\'une panne (temps de rétablissement, attente de pièces comprise).'],
        ['Coût', 'heures × taux horaire + pièces sorties × prix actuel + sous-traitance, des OT clôturés dans le mois.'],
        ['Part du préventif', 'heures passées sur des OT préventifs / heures passées sur tous les OT.'],
        ['Réparer ou remplacer', 'coût de maintenance des 12 derniers mois rapporté à la valeur de remplacement ; signalé au-delà de ' + UI.nombreFr(remplacement.seuil, 0) + ' % (réglable dans Paramètres).'],
      ],
    };
    resultat.courriel = texteCourriel(resultat);
    return resultat;
  }

  /** Mois à proposer de figer : le mois précédent, s'il n'est pas déjà figé et que l'historique le couvre. */
  function moisAProposer(aujourdhui) {
    const jour = /^\d{4}-\d{2}-\d{2}$/.test(texte(aujourdhui).slice(0, 10)) ? texte(aujourdhui).slice(0, 10) : Donnees.aujourdhui();
    const mois = decalerMois(jour.slice(0, 7), -1);
    if (rapportsFiges().some((nom) => nom.startsWith(PREFIXE_FICHIER + mois))) return null;
    return estCouvert(mois) ? mois : null;
  }

  /** Noms des rapports figés (paramètre rapports_mensuels), du plus ancien au plus récent. */
  function rapportsFiges() {
    return texte(Donnees.parametre('rapports_mensuels', '')).split(',').map(texte).filter(Boolean);
  }

  /** Objet et corps d'un courriel de résumé (texte simple, moins de 1 800 caractères). */
  function texteCourriel(rapport) {
    const lignes = ['Rapport mensuel de maintenance — ' + rapport.libelleMois + (rapport.entreprise ? ' — ' + rapport.entreprise : ''), ''];
    rapport.tuiles.forEach((tuile) => lignes.push('• ' + tuile.libelle + ' : ' + tuile.texteValeur + ' (' + tuile.tendance.precedent.texte + ')'));
    lignes.push('', 'Faits marquants :');
    rapport.faits.forEach((fait) => lignes.push('• ' + fait));
    if (rapport.decisions.length) {
      lignes.push('', 'Décisions proposées :');
      rapport.decisions.forEach((decision) => lignes.push('• ' + decision));
    }
    lignes.push('', 'Le rapport complet (une page) est dans Prévo : Indicateurs, onglet « Rapports mensuels ».');
    let corps = lignes.join('\r\n');      // RFC 6068 : fins de ligne CRLF (%0D%0A)
    if (corps.length > 1800) corps = corps.slice(0, 1790) + '…';
    return { objet: 'Rapport de maintenance — ' + rapport.libelleMois, corps };
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
    graphique.setOption(Object.assign({ animation: false, textStyle: { fontFamily: 'Arial, Helvetica, sans-serif', fontSize: 11, color: '#222' } }, option));
    const dessin = graphique.renderToSVGString();
    graphique.dispose();
    return dessin;
  }

  function graphiques(lib, rapport) {
    const pareto = rapport.pareto.length ? svg(lib, 340, 200, {
      grid: { left: 70, right: 30, top: 10, bottom: 30 },
      xAxis: { type: 'value', name: 'h', axisLabel: { color: '#333', formatter: (valeur) => UI.nombreFr(valeur) } },
      yAxis: { type: 'category', inverse: true, data: rapport.pareto.map((ligne) => etiquette(ligne.repere)), axisLabel: { color: '#333' } },
      series: [{ type: 'bar', data: rapport.pareto.map((ligne) => Math.round(ligne.heures * 10) / 10), itemStyle: { color: COULEURS_SERIES[0] },
        label: { show: true, position: 'right', color: '#222', formatter: (point) => UI.nombreFr(point.value, 1) } }],
    }) : '';
    const heures = svg(lib, 340, 200, {
      grid: { left: 40, right: 10, top: 30, bottom: 30 },
      legend: { top: 0, textStyle: { color: '#222' } },
      xAxis: { type: 'category', data: rapport.heures12Mois.map((element) => element.mois.slice(5, 7) + '/' + element.mois.slice(2, 4)), axisLabel: { color: '#333' } },
      yAxis: { type: 'value', name: 'h', axisLabel: { color: '#333', formatter: (valeur) => UI.nombreFr(valeur) } },
      series: [
        // Mêmes couleurs que l'écran Indicateurs : correctif bleu, préventif ocre.
        { name: 'Correctif', type: 'bar', data: rapport.heures12Mois.map((element) => element.correctif), itemStyle: { color: COULEURS_SERIES[0] } },
        { name: 'Préventif', type: 'bar', data: rapport.heures12Mois.map((element) => element.preventif), itemStyle: { color: COULEURS_SERIES[1] } },
      ],
    });
    return { pareto, heures };
  }

  /** Feu d'une tendance : forme ET texte (jamais la couleur seule). */
  function feu(tuile, tendance) {
    if (!tendance.sens) return UI.html`<span class="feu neutre">○ ${tendance.texte}</span>`;
    if (tendance.sens === 'stable') return UI.html`<span class="feu neutre">■ ${tendance.texte}</span>`;
    const favorable = (tendance.sens === 'hausse') === tuile.hausseFavorable;
    return UI.html`<span class="feu ${favorable ? 'bon' : 'mauvais'}">${tendance.sens === 'hausse' ? '▲' : '▼'} ${tendance.texte}${favorable ? '' : ' (à surveiller)'}</span>`;
  }

  const STYLE = `@page { size: A4; margin: 11mm 12mm; }
* { box-sizing: border-box; }
body { margin: 0; color: #111; background: #fff; font: 9.5pt/1.35 "Segoe UI", Arial, Helvetica, sans-serif; }
.page { max-width: 186mm; margin: 0 auto; }
header { border-bottom: 2px solid #111; padding-bottom: 4px; margin-bottom: 8px; }
h1 { font-size: 15pt; margin: 0; } h2 { font-size: 10.5pt; margin: 0 0 4px; }
.sous { margin: 2px 0 0; color: #333; }
.tuiles { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-bottom: 8px; }
.tuile { border: 1px solid #888; border-radius: 6px; padding: 6px 8px; }
.tuile .lib { font-weight: 600; } .tuile .val { font-size: 17pt; font-weight: 700; margin: 2px 0; }
.tuile .raison { font-size: 8.5pt; color: #333; }
.feu { display: block; font-size: 8.5pt; } .feu.bon { color: #14532d; } .feu.mauvais { color: #7f1d1d; font-weight: 600; } .feu.neutre { color: #333; }
.colonnes { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 8px; }
ul, ol { margin: 0; padding-left: 16px; } li { margin: 0 0 2px; }
figure { margin: 0; } figcaption { font-weight: 600; margin-bottom: 2px; }
.graphiques { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 8px; }
.graphiques svg { width: 100%; height: auto; }
.comprendre { border: 1px solid #888; border-radius: 6px; padding: 6px 8px; margin-bottom: 6px; font-size: 8.5pt; }
.comprendre dt { font-weight: 600; display: inline; } .comprendre dd { display: inline; margin: 0; } .comprendre div { margin-bottom: 1px; }
.non-calculable { font-size: 8.5pt; color: #333; }
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
    const rapport = reglages.donnees || donnees(mois, reglages.aujourdhui, reglages.maintenant);
    // Lot 4 (§17.5) : commentaire du responsable, éventuellement proposé par l'IA (mention alors imprimée).
    const commentaire = reglages.commentaire && texte(reglages.commentaire.texte) ? reglages.commentaire : null;
    const lib = await App.chargerEcharts();
    const dessins = graphiques(lib, rapport);
    const titre = 'Rapport mensuel de maintenance — ' + rapport.libelleMois;
    const mttr = rapport.mttr.valeur === null ? '' : UI.html`<p class="pied">MTTR : ${UI.heures(Math.round(rapport.mttr.valeur * 10) / 10)}${rapport.attentePieces.valeur === null ? ''
      : UI.html`, dont attente de pièces : ${UI.heures(Math.round(rapport.attentePieces.valeur * 10) / 10)} (sur ${rapport.attentePieces.effectif} panne(s) à historique complet)`}.</p>`;
    const page = UI.html`<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>${titre}${rapport.entreprise ? ' — ' + rapport.entreprise : ''}</title>
<style>${UI.brut(STYLE)}</style></head>
<body><main class="page">
<header><h1>${titre}</h1>
<p class="sous">${rapport.entreprise ? rapport.entreprise + ' · ' : ''}Données au ${UI.dateHeureFr(rapport.genereLe)} · Rapport figé par Prévo (GMAO)</p></header>
<section class="tuiles">${rapport.tuiles.map((tuile) => UI.html`<div class="tuile" data-cle="${tuile.cle}">
  <div class="lib">${tuile.libelle}</div><div class="val">${tuile.texteValeur}</div>
  ${tuile.valeur === null ? UI.html`<div class="raison">${tuile.raison}</div>` : ''}
  ${feu(tuile, tuile.tendance.precedent)}${feu(tuile, tuile.tendance.annee)}</div>`)}</section>
<section class="colonnes"><div><h2>Faits marquants</h2><ul>${rapport.faits.map((fait) => UI.html`<li>${fait}</li>`)}</ul></div>
<div><h2>Décisions à prendre</h2>${rapport.decisions.length ? UI.html`<ol>${rapport.decisions.map((decision) => UI.html`<li>${decision}</li>`)}</ol>`
    : UI.html`<p>Aucune décision urgente ce mois-ci.</p>`}</div></section>
${commentaire ? UI.html`<section class="commentaire"><h2>Commentaire</h2><p>${texte(commentaire.texte)}</p>${commentaire.aideIa
    ? UI.html`<p class="mention-ia">Commentaire rédigé avec l'aide de l'IA, relu et validé par le responsable.</p>` : ''}</section>` : ''}
<section class="graphiques">
<figure><figcaption>Durée d'arrêt du mois par équipement (heures)</figcaption>${dessins.pareto ? UI.brut(dessins.pareto) : UI.html`<p>Aucun arrêt ce mois-ci.</p>`}</figure>
<figure><figcaption>Heures de correctif et de préventif sur 12 mois</figcaption>${UI.brut(dessins.heures)}</figure>
</section>
${mttr}
<section class="comprendre"><h2>Comprendre</h2><dl>${rapport.comprendre.map(([terme, definition]) => UI.html`<div><dt>${terme} :</dt> <dd>${definition}</dd></div>`)}</dl></section>
${rapport.nonCalculables.length ? UI.html`<section class="non-calculable"><h2>Non calculable</h2><ul>${rapport.nonCalculables.map((element) => UI.html`<li><b>${element.libelle}</b> : ${element.raison}</li>`)}</ul></section>` : ''}
<p class="pied sans-impression"><a href="${lienCourriel(rapport)}">Préparer un courriel</a> (votre messagerie s'ouvre avec ce résumé ; rien n'est envoyé par Prévo).</p>
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
    interne: { texte, decalerMois, libelleMois, lienCourriel, estCouvert, debutHistorique },
  };
})();
