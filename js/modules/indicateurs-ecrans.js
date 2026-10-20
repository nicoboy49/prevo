'use strict';
// Indicateurs (4/4) — écran E11 #/indicateurs (ARCHITECTURE.md §15.4 ; brief §12), réservé au
// responsable (§15.2) :
//   - onglet « Tableau de bord » : période (?periode=mois|mois-precedent|3-mois|12-mois|du-au,
//     ?du=, ?au=), filtres criticité et atelier (?criticite=, ?atelier=) ; bandeau d'instruments
//     (chaque valeur non calculable dit pourquoi ; effectifs visibles ; « dont attente de pièces »
//     sous le MTTR quand elle est calculable) ; encadré « Comprendre » ; sept graphiques
//     (Indicateurs.graphique) ; délais de prise en charge ; tableau par équipement trié par clic ;
//   - onglet « Rapports mensuels » (?onglet=rapports) : Rapport.afficherOnglet (rapport-*.js) s'il
//     existe.
// Les réglages restent dans l'adresse (history.replaceState) : un lien ou un rechargement rouvre la
// même vue. Les chiffres viennent tous des règles (indicateurs-regles.js, indicateurs-series.js).

Object.assign(Indicateurs, (() => {

  const { arrondi, estSuivi, passeFiltres, contexte, texte, formats } = Indicateurs.interne;

  const CRITICITES = ['A', 'B', 'C'];
  const PRIORITES = ['P1', 'P2', 'P3', 'P4'];
  const ONGLETS = ['tableau', 'rapports'];
  // Tables dont un changement sur un autre poste réaffiche l'écran (le journal, écrit à chaque
  // modification, n'en fait pas partie : « Actualiser » relit l'attente de pièces).
  const TABLES = ['ordres_travail', 'demandes', 'equipements', 'ot_temps', 'mouvements_stock', 'articles',
    'techniciens', 'gammes', 'compteurs', 'localisations', 'codes_defaillance', 'parametres'];

  // ===========================================================================================
  // 13. Réglages de la vue (adresse ↔ écran)
  // ===========================================================================================

  function ateliers() {
    return Donnees.lignes('localisations').filter((localisation) => texte(localisation.type) === 'atelier')
      .sort((a, b) => texte(a.libelle).localeCompare(texte(b.libelle), 'fr'));
  }

  /** Réglages lus dans l'adresse ; une valeur inconnue est ignorée. */
  function reglagesDepuisAdresse(requete) {
    const criticite = String(requete.get('criticite') || '').toUpperCase();
    const atelier = requete.get('atelier') || '';
    return {
      periode: Indicateurs.PERIODES[requete.get('periode')] ? requete.get('periode') : '12-mois',
      du: requete.get('du') || '', au: requete.get('au') || '',
      criticite: CRITICITES.includes(criticite) ? criticite : '',
      atelier: ateliers().some((localisation) => localisation.id === atelier) ? atelier : '',
      onglet: ONGLETS.includes(requete.get('onglet')) ? requete.get('onglet') : 'tableau',
    };
  }

  function adresse(reglages) {
    const requete = new URLSearchParams();
    requete.set('periode', reglages.periode);
    if (reglages.periode === 'du-au') { requete.set('du', reglages.du); requete.set('au', reglages.au); }
    if (reglages.criticite) requete.set('criticite', reglages.criticite);
    if (reglages.atelier) requete.set('atelier', reglages.atelier);
    requete.set('onglet', reglages.onglet);
    return '#/indicateurs?' + requete.toString();
  }

  function remplacerAdresse(reglages) {
    try { history.replaceState(history.state, '', adresse(reglages)); } catch (erreur) { /* adresse gardée */ }
  }

  // ===========================================================================================
  // 14. Écran : en-tête et onglets
  // ===========================================================================================

  function afficherEcran(conteneur, parametres) {
    const reglages = reglagesDepuisAdresse((parametres && parametres.requete) || new URLSearchParams());
    UI.remplir(conteneur, UI.html`<div class="indicateurs">
      <div class="entete-page"><div><h1>Indicateurs</h1>
        <p>Fiabilité des équipements, préventif, délais, coûts et stock. Chaque chiffre dit sur quoi il est
        calculé ; ce qui ne peut pas l'être est signalé, jamais estimé.</p></div></div>
      <div class="indicateurs-onglets"></div>
    </div>`);
    UI.onglets(UI.$('.indicateurs-onglets', conteneur), [
      { id: 'tableau', libelle: 'Tableau de bord', afficher: (panneau) => afficherTableauDeBord(panneau, reglages) },
      { id: 'rapports', libelle: 'Rapports mensuels', afficher: afficherRapports },
    ], {
      actif: reglages.onglet, libelle: 'Rubriques des indicateurs',
      surChangement: (id) => { reglages.onglet = id; remplacerAdresse(reglages); },
    });
  }

  function afficherRapports(panneau) {
    if (typeof Rapport !== 'undefined' && typeof Rapport.afficherOnglet === 'function') {
      Rapport.afficherOnglet(panneau);
      return;
    }
    UI.remplir(panneau, UI.vide('Rapports mensuels', 'Les rapports mensuels arrivent avec la tâche suivante.', 'document'));
  }

  // ===========================================================================================
  // 15. Onglet « Tableau de bord » : filtres, puis résultats (recalculés à chaque changement)
  // ===========================================================================================

  function options(liste, choisie) {
    return liste.map(([valeur, libelle]) => UI.html`<option value="${valeur}"${valeur === choisie ? UI.brut(' selected') : ''}>${libelle}</option>`);
  }

  function afficherTableauDeBord(panneau, reglages) {
    const periodes = Object.keys(Indicateurs.PERIODES).map((code) => [code, Indicateurs.PERIODES[code]]);
    UI.remplir(panneau, UI.html`
      <form class="filtres indicateurs-filtres" data-hors-saisie aria-label="Période et filtres">
        <label class="champ"><span class="libelle">Période</span>
          <select id="indicateurs-periode" name="periode">${options(periodes, reglages.periode)}</select></label>
        <label class="champ indicateurs-date" hidden><span class="libelle">Du</span>
          <input type="date" id="indicateurs-du" name="du" value="${reglages.du}"></label>
        <label class="champ indicateurs-date" hidden><span class="libelle">Au</span>
          <input type="date" id="indicateurs-au" name="au" value="${reglages.au}"></label>
        <label class="champ"><span class="libelle">Criticité</span>
          <select id="indicateurs-criticite" name="criticite">${options([['', 'Toutes']].concat(CRITICITES.map((c) => [c, 'Criticité ' + c])), reglages.criticite)}</select></label>
        <label class="champ"><span class="libelle">Atelier</span>
          <select id="indicateurs-atelier" name="atelier">${options([['', 'Tous les ateliers']].concat(ateliers().map((l) => [l.id, l.libelle || l.id])), reglages.atelier)}</select></label>
      </form>
      <div class="indicateurs-resultats"></div>`);
    const formulaire = UI.$('.indicateurs-filtres', panneau);
    const resultats = UI.$('.indicateurs-resultats', panneau);
    formulaire.addEventListener('submit', (evenement) => evenement.preventDefault());
    formulaire.addEventListener('change', (evenement) => {
      lireFiltres(formulaire, reglages, evenement.target);
      afficherResultats(resultats, reglages, formulaire);
      remplacerAdresse(reglages);                    // après : la période a pu être corrigée
    });
    afficherResultats(resultats, reglages, formulaire);
  }

  /** Lit le formulaire ; « Période choisie » part des dates de la période affichée. */
  function lireFiltres(formulaire, reglages, champChange) {
    reglages.periode = UI.$('#indicateurs-periode', formulaire).value;
    reglages.criticite = UI.$('#indicateurs-criticite', formulaire).value;
    reglages.atelier = UI.$('#indicateurs-atelier', formulaire).value;
    const du = UI.$('#indicateurs-du', formulaire);
    const au = UI.$('#indicateurs-au', formulaire);
    if (champChange && champChange.id === 'indicateurs-periode' && reglages.periode === 'du-au' && (!du.value || !au.value)) {
      const zone = formulaire.nextElementSibling;
      du.value = du.value || zone.dataset.debut || '';
      au.value = au.value || zone.dataset.fin || '';
    }
    reglages.du = du.value;
    reglages.au = au.value;
  }

  function afficherResultats(zone, reglages, formulaire) {
    Indicateurs.libererGraphiques(zone);
    const jour = Donnees.aujourdhui();
    const periode = Indicateurs.periode(reglages.periode, jour, reglages.du, reglages.au);
    reglages.periode = periode.code;                 // « du-au » sans dates valables → 12 mois
    const filtres = { criticite: reglages.criticite, atelier: reglages.atelier };
    const global = Indicateurs.global(periode, filtres, jour);
    UI.$('#indicateurs-periode', formulaire).value = periode.code;
    UI.$$('.indicateurs-date', formulaire).forEach((bloc) => { bloc.hidden = periode.code !== 'du-au'; });
    Object.assign(zone.dataset, {
      periode: periode.code, du: periode.code === 'du-au' ? reglages.du : '', au: periode.code === 'du-au' ? reglages.au : '',
      debut: periode.debut, fin: periode.fin, criticite: filtres.criticite, atelier: filtres.atelier,
    });
    UI.remplir(zone, UI.html`
      <p class="indicateurs-resume" aria-live="polite">${periode.libelle}${resumeFiltres(filtres)}</p>
      <div class="instruments indicateurs-instruments">${instruments(global, jour)}</div>
      ${comprendre(global)}
      <div class="grille indicateurs-graphiques"></div>
      <div class="grille">
        <article class="carte c12 indicateurs-delais"><h2>Délais de prise en charge</h2>${delais(global.delais)}</article>
        <article class="carte c12 indicateurs-equipements-carte"><div class="entete-carte"><h2>Par équipement</h2></div>
          <p class="note">Équipements suivis${resumeFiltres(filtres)} ; cliquez un en-tête pour trier, un repère pour ouvrir la fiche.</p>
          <div class="indicateurs-equipements"></div></article>
      </div>`);
    UI.$('.indicateurs-equipements', zone).appendChild(tableauEquipements(periode, filtres));
    dessinerGraphiques(UI.$('.indicateurs-graphiques', zone), periode, filtres, jour);
  }

  function resumeFiltres(filtres) {
    const morceaux = [];
    if (filtres.criticite) morceaux.push('criticité ' + filtres.criticite);
    if (filtres.atelier) {
      const atelier = Donnees.trouver('localisations', filtres.atelier);
      morceaux.push((atelier && atelier.libelle) || filtres.atelier);
    }
    return morceaux.length ? ' — ' + morceaux.join(', ') : '';
  }

  // ===========================================================================================
  // 16. Bandeau d'instruments et encadré « Comprendre »
  // ===========================================================================================

  function pluriel(nombre, mot, motPluriel) {
    return nombre + ' ' + (nombre > 1 ? (motPluriel || mot + 's') : mot);
  }

  /** Texte d'une raison, avec une majuscule (« Non calculable : … »). */
  function phrase(raison) {
    const contenu = texte(raison);
    return contenu ? contenu.charAt(0).toUpperCase() + contenu.slice(1) : '';
  }

  const SOURCES_MAX = 40;

  /**
   * OT sources d'un résultat (D35 : chaque chiffre avec ses OT) : liste repliée « n OT sources », un
   * lien par OT (40 au plus, puis « et n autres »), et les OT exclus avec leur raison.
   */
  function sources(resultat) {
    const ots = resultat.ots || [];
    const exclus = (resultat.exclus || []).filter((element) => /^OT-/.test(texte(element.id)));
    if (!ots.length && !exclus.length) return '';
    const lien = (id) => UI.html`<a href="#/ot/${encodeURIComponent(id)}">${id}</a>`;
    const resume = (ots.length ? pluriel(ots.length, 'OT source', 'OT sources') : '')
      + (ots.length && exclus.length ? ' · ' : '') + (exclus.length ? pluriel(exclus.length, 'OT exclu', 'OT exclus') : '');
    return UI.html`<details class="indicateurs-sources"><summary>${resume}</summary>
      ${ots.length ? UI.html`<p>${ots.slice(0, SOURCES_MAX).map((id, rang) => UI.html`${rang ? ', ' : ''}${lien(id)}`)}${ots.length > SOURCES_MAX
        ? ' et ' + (ots.length - SOURCES_MAX) + ' autres' : ''}</p>` : ''}
      ${exclus.length ? UI.html`<ul>${exclus.slice(0, SOURCES_MAX).map((element) => UI.html`<li>${lien(element.id)} : ${element.raison}</li>`)}</ul>` : ''}
    </details>`;
  }

  /** Un instrument : libellé, chiffre (ou tiret et raison), compléments (effectifs). */
  function instrument({ cle, libelle, resultat, format, valeurAffichee, complements, lien }) {
    const calcule = resultat.valeur !== null;
    // Les OT sources (D35) sous chaque chiffre, sauf dans un instrument qui est lui-même un lien.
    const lignes = (calcule ? complements.filter(Boolean) : [phrase(resultat.raison)]).concat(lien ? [] : [sources(resultat)]).filter(Boolean);
    const contenu = UI.html`<div class="lib">${libelle}</div>
      <div class="chiffre">${calcule ? format(resultat.valeur) : '–'}</div>
      ${lignes.map((ligne) => (UI.estSur(ligne) ? ligne : UI.html`<div class="comp">${ligne}</div>`))}`;
    const valeur = calcule ? String(valeurAffichee(resultat.valeur)) : '';
    return lien
      ? UI.html`<a href="${lien}" data-indicateur="${cle}" data-valeur="${valeur}">${contenu}</a>`
      : UI.html`<div data-indicateur="${cle}" data-valeur="${valeur}">${contenu}</div>`;
  }

  const enPourcentage = (fraction) => arrondi(fraction * 100, 1);
  const enHeures = (valeur) => arrondi(valeur, 1);
  const enEuros = (valeur) => arrondi(valeur, 2);

  function instruments(global, jour) {
    const requis = global.tempsRequis;
    const nbPannes = global.pannes.valeur;
    const sansHeures = requis.exclus.length;
    const perimetre = requis.valeur === null ? null : pluriel(requis.effectif, 'équipement')
      + (sansHeures ? ' (' + pluriel(sansHeures, 'autre') + ' sans heures de fonctionnement, non compté' + (sansHeures > 1 ? 's' : '') + ')' : '');
    const mttr = global.mttr;
    const attente = global.attentePieces;
    const preventif = global.respectPreventif;
    return [
      instrument({ cle: 'disponibilite', libelle: 'Disponibilité', resultat: global.disponibilite, format: formats.pourcentage,
        valeurAffichee: enPourcentage,
        complements: [pluriel(nbPannes, 'panne') + ' · ' + perimetre, global.disponibilite.note ? phrase(global.disponibilite.note) : ''] }),
      instrument({ cle: 'mtbf', libelle: 'MTBF (temps moyen entre pannes)', resultat: global.mtbf, format: formats.heures,
        valeurAffichee: enHeures, complements: ['sur ' + pluriel(nbPannes, 'panne') + ' · ' + perimetre] }),
      instrument({ cle: 'mttr', libelle: 'MTTR (temps moyen de rétablissement)', resultat: mttr, format: formats.heures,
        valeurAffichee: enHeures,
        complements: ['sur ' + pluriel(mttr.effectif, 'panne mesurable', 'pannes mesurables')
          + (mttr.exclus.length ? ' · ' + pluriel(mttr.exclus.length, 'autre') + ' non clôturée(s) ou sans durée' : ''),
        attente.valeur === null ? '' : UI.html`<div class="comp indicateurs-attente">dont attente de pièces : ${formats.heures(attente.valeur)}
          (sur ${pluriel(attente.effectif, 'panne')} à historique complet)</div>`] }),
      instrument({ cle: 'duree-arret', libelle: 'Durée d\'arrêt', resultat: global.dureeArret, format: formats.heures,
        valeurAffichee: enHeures,
        complements: [pluriel(global.dureeArret.effectif, 'panne') + ' avec une durée'
          + (global.dureeArret.exclus.length ? ' · ' + global.dureeArret.exclus.length + ' sans durée d\'arrêt' : '')] }),
      instrument({ cle: 'part-preventif', libelle: 'Part du préventif', resultat: global.partPreventif, format: formats.pourcentage,
        valeurAffichee: enPourcentage,
        complements: [global.partPreventif.note ? global.partPreventif.note + ' sur la période' : ''] }),
      instrument({ cle: 'respect-preventif', libelle: 'Respect du préventif', resultat: preventif, format: formats.pourcentage,
        valeurAffichee: enPourcentage,
        complements: [preventif.note, preventif.exclus.length ? pluriel(preventif.exclus.length, 'OT exclu', 'OT exclus') + ' (date prévue ou périodicité inconnue)' : ''] }),
      instrument({ cle: 'ot-en-retard', libelle: 'OT en retard', resultat: global.otEnRetard, format: String,
        valeurAffichee: (valeur) => valeur, lien: '#/ot?filtre=retard',
        complements: ['date prévue dépassée au ' + UI.dateFr(jour)] }),
      instrument({ cle: 'cout', libelle: 'Coût de maintenance', resultat: global.cout, format: formats.euros,
        valeurAffichee: enEuros, complements: [pluriel(global.cout.effectif, 'OT clôturé', 'OT clôturés') + ' · pièces au prix actuel'] }),
      instrument({ cle: 'valeur-stock', libelle: 'Valeur du stock', resultat: global.valeurStock, format: formats.euros,
        valeurAffichee: enEuros,
        complements: [pluriel(global.valeurStock.effectif, 'article') + ' · tout le magasin'
          + (global.valeurStock.exclus.length ? ' · ' + global.valeurStock.exclus.length + ' sans prix' : '')] }),
    ];
  }

  /** Ce qui n'a pas pu être calculé sur la sélection, avec la raison. */
  function nonCalculables(global) {
    const libelles = { disponibilite: 'Disponibilité', mtbf: 'MTBF', mttr: 'MTTR', dureeArret: 'Durée d\'arrêt',
      partPreventif: 'Part du préventif', respectPreventif: 'Respect du préventif', attentePieces: 'Attente de pièces' };
    const lignes = Object.keys(libelles).filter((cle) => global[cle].valeur === null)
      .map((cle) => UI.html`<li><b>${libelles[cle]}</b> : ${global[cle].raison}.</li>`);
    const sansHeures = global.tempsRequis.exclus;
    if (sansHeures.length) {
      const reperes = sansHeures.map((element) => { const equipement = Donnees.trouver('equipements', element.id); return (equipement && equipement.repere) || element.id; });
      lignes.push(UI.html`<li><b>${pluriel(sansHeures.length, 'équipement')}</b> sans temps requis (${reperes.join(', ')}) :
        ${sansHeures[0].raison} ; ${sansHeures.length > 1 ? 'ils ne comptent' : 'il ne compte'} ni dans le MTBF ni dans la disponibilité.</li>`);
    }
    return lignes;
  }

  function comprendre(global) {
    const tolerance = Donnees.parametre('tolerance_preventif_pct', '10');
    const manques = nonCalculables(global);
    return UI.html`<details class="encadre indicateurs-comprendre"><summary>Comprendre ces indicateurs</summary>
      <ul>
        <li><b>Panne</b> : un OT correctif (immédiat ou différé) qui a arrêté la production, non annulé, compté à la date de la demande d'intervention (sinon à la création de l'OT).</li>
        <li><b>Temps requis</b> : heures de fonctionnement par jour de l'équipement × jours de la période (depuis sa mise en service). Sans heures par jour renseignées, l'équipement est « non calculable » : il n'entre ni dans le MTBF ni dans la disponibilité (jamais d'estimation).</li>
        <li><b>Durée d'arrêt</b> : somme des durées d'arrêt saisies sur les pannes.</li>
        <li><b>MTBF</b> (temps moyen entre pannes) = (temps requis − durée d'arrêt) ÷ nombre de pannes.</li>
        <li><b>MTTR</b> (temps moyen de rétablissement) = durée d'arrêt ÷ nombre de pannes mesurables (clôturées, avec une durée d'arrêt) ; les attentes (pièces, production) sont comprises.</li>
        <li><b>dont attente de pièces</b> : moyenne des heures passées « En attente » d'une pièce, lues dans le journal, sur les pannes mesurables dont tout l'historique des statuts est au journal.</li>
        <li><b>Disponibilité</b> = MTBF ÷ (MTBF + MTTR) ; 100 % s'il n'y a eu aucune panne.</li>
        <li><b>Part du préventif</b> : heures passées sur des OT préventifs ÷ heures passées sur tous les OT (temps saisis dans la période).</li>
        <li><b>Respect du préventif</b> : part des OT préventifs systématiques à échéance dans la période (date prévue + ${tolerance} % de la périodicité de la gamme) clôturés au plus tard à l'échéance.</li>
        <li><b>OT en retard</b> : OT ouverts dont la date prévue est dépassée, aujourd'hui.</li>
        <li><b>Délai de prise en charge</b> : temps entre la demande (ou la création de l'OT) et le début de l'intervention ; médiane par priorité et part des OT pris en charge dans le délai cible.</li>
        <li><b>Coût</b> : main-d'œuvre + pièces (au prix actuel) + sous-traitance des OT clôturés dans la période.</li>
        <li><b>Valeur du stock</b> : stock × prix unitaire des articles actifs (tout le magasin, sans filtre).</li>
      </ul>
      ${manques.length ? UI.html`<h3>Non calculable sur cette sélection</h3><ul class="indicateurs-manques">${manques}</ul>` : ''}
    </details>`;
  }

  /** Délais de prise en charge par priorité (médiane, part dans le délai cible, effectif). */
  function delais(parPriorite) {
    return UI.html`<div class="table-defile"><table class="table">
      <caption class="visuellement-cache">Délais de prise en charge par priorité</caption>
      <thead><tr><th scope="col">Priorité</th><th scope="col" class="num">Délai cible</th><th scope="col" class="num">Médiane</th>
        <th scope="col" class="num">Dans le délai</th><th scope="col" class="num">OT comptés</th></tr></thead>
      <tbody>${PRIORITES.map((priorite) => {
        const ligne = parPriorite[priorite];
        return UI.html`<tr><td>${UI.badgePriorite(priorite)}</td>
          <td class="num">${ligne.cible === null ? 'aucun' : formats.heures(ligne.cible)}</td>
          <td class="num">${ligne.mediane === null ? '–' : formats.heures(ligne.mediane)}</td>
          <td class="num">${ligne.partDansLeDelai === null ? '–' : formats.pourcentage(ligne.partDansLeDelai)}</td>
          <td class="num">${ligne.effectif}</td></tr>`;
      })}</tbody></table></div>`;
  }

  // ===========================================================================================
  // 17. Les sept graphiques (séries des règles → Indicateurs.graphique)
  // ===========================================================================================

  function repere(equipementId) {
    const equipement = Donnees.trouver('equipements', equipementId);
    return (equipement && texte(equipement.repere)) || equipementId;
  }

  function nomTechnicien(technicien) {
    return (texte(technicien.prenom) + ' ' + texte(technicien.nom)).trim() || technicien.id;
  }

  /** « J. Moreau » : nom court pour l'axe (le tableau garde le nom complet). */
  function nomCourt(technicien) {
    const prenom = texte(technicien.prenom);
    return ((prenom ? prenom.charAt(0) + '. ' : '') + texte(technicien.nom)).trim() || technicien.id;
  }

  const COLONNE_EQUIPEMENT = { cle: 'equipement', libelle: 'Équipement', protege: true };

  function grapheParetos(periode, filtres) {
    const pannes = Indicateurs.paretoPannes(periode, 10, filtres)
      .map((ligne) => ({ equipement: repere(ligne.equipementId), libelle: repere(ligne.equipementId), valeur: ligne.valeur, cumulPct: ligne.cumulPct }));
    const arrets = Indicateurs.paretoArrets(periode, 10, filtres)
      .map((ligne) => ({ equipement: repere(ligne.equipementId), libelle: repere(ligne.equipementId), valeur: ligne.valeur, cumulPct: ligne.cumulPct }));
    const cumul = { cle: 'cumulPct', libelle: 'Cumul (%)', type: 'nombre', decimales: 1 };
    return [
      { id: 'pareto-pannes', titre: 'Pareto des pannes', sousTitre: 'Nombre de pannes des 10 équipements les plus touchés ; étiquette : part cumulée du total.',
        option: Indicateurs.options.pareto(pannes, 'Pannes', (valeur) => pluriel(valeur, 'panne')),
        colonnes: [COLONNE_EQUIPEMENT, { cle: 'valeur', libelle: 'Pannes', type: 'nombre', decimales: 0 }, cumul],
        lignes: pannes, hauteur: Indicateurs.options.hauteurBarres(pannes.length), vide: pannes.length ? '' : 'Aucune panne sur la période.' },
      { id: 'pareto-arrets', titre: 'Pareto des durées d\'arrêt', sousTitre: 'Heures d\'arrêt des 10 équipements les plus arrêtés ; étiquette : part cumulée du total.',
        option: Indicateurs.options.pareto(arrets, 'Durée d\'arrêt', formats.heures),
        colonnes: [COLONNE_EQUIPEMENT, { cle: 'valeur', libelle: 'Durée d\'arrêt (h)', type: 'nombre', decimales: 1 }, cumul],
        lignes: arrets, hauteur: Indicateurs.options.hauteurBarres(arrets.length), vide: arrets.length ? '' : 'Aucune durée d\'arrêt saisie sur la période.' },
    ];
  }

  function grapheHeures(periode, filtres) {
    const lignes = Indicateurs.heuresParMois(periode.fin.slice(0, 7), 12, filtres)
      .map((ligne) => Object.assign({ libelle: ligne.mois.slice(5, 7) + '/' + ligne.mois.slice(0, 4) }, ligne));
    const total = lignes.reduce((somme, ligne) => somme + ligne.correctif + ligne.preventif + ligne.autres, 0);
    const heures = (cle, libelle) => ({ cle, libelle, type: 'nombre', decimales: 1 });
    return {
      id: 'heures-mois', titre: 'Heures correctif, préventif et autres', classe: 'c12',
      sousTitre: 'Heures passées (temps saisis sur les OT) par mois, sur les 12 mois finissant en ' + lignes[lignes.length - 1].libelle
        + ' ; « autres » : amélioration et réglementaire.',
      option: Indicateurs.options.heuresParMois(lignes),
      colonnes: [{ cle: 'libelle', libelle: 'Mois' }, heures('correctif', 'Correctif (h)'), heures('preventif', 'Préventif (h)'), heures('autres', 'Autres (h)')],
      lignes, vide: total > 0 ? '' : 'Aucune heure saisie sur ces 12 mois.',
    };
  }

  /** Équipements A (filtre atelier appliqué) avec leurs MTBF et MTTR, calculés une fois pour les deux graphiques. */
  function equipementsA(periode, filtres) {
    const ctx = contexte();
    return Indicateurs.mtbfMttrCriticiteA(periode)
      .filter((ligne) => !filtres.atelier || passeFiltres(ctx.equipements.get(ligne.equipementId), { atelier: filtres.atelier }, ctx));
  }

  function grapheCriticiteA(listeA, filtres, cle, titre) {
    const lignes = listeA.map((ligne) => ({ equipement: repere(ligne.equipementId), libelle: repere(ligne.equipementId), valeur: ligne[cle].valeur, raison: ligne[cle].raison }));
    const calcules = lignes.filter((ligne) => ligne.valeur !== null);
    const manquants = lignes.length - calcules.length;
    return {
      id: cle + '-a', titre: titre + ' des équipements A',
      sousTitre: 'Équipements de criticité A' + (filtres.atelier ? ' de l\'atelier choisi' : '') + ', en heures.',
      option: Indicateurs.options.barresHorizontales({ nom: titre, categories: calcules.map((ligne) => ligne.libelle),
        valeurs: calcules.map((ligne) => ligne.valeur), formatValeur: formats.heures, etiquette: (rang) => formats.heures(calcules[rang].valeur), margeDroite: 80 }),
      notes: manquants ? [pluriel(manquants, 'équipement') + ' sans valeur (raison dans « Voir les valeurs »).'] : [],
      colonnes: [COLONNE_EQUIPEMENT, { cle: 'valeur', libelle: titre + ' (h)', type: 'nombre', decimales: 1, raison: 'raison' }],
      lignes, hauteur: Indicateurs.options.hauteurBarres(calcules.length), vide: calcules.length ? '' : (lignes.length ? 'Aucune valeur calculable : voir « Voir les valeurs ».' : 'Aucun équipement de criticité A.'),
    };
  }

  function grapheCauses(periode, filtres) {
    const lignes = Indicateurs.causes(periode, filtres);
    return {
      id: 'causes', titre: 'Causes des pannes', sousTitre: 'Nombre de pannes de la période par code de cause.',
      option: Indicateurs.options.barresHorizontales({ nom: 'Pannes', categories: lignes.map((ligne) => ligne.libelle),
        valeurs: lignes.map((ligne) => ligne.nombre), formatValeur: (valeur) => pluriel(valeur, 'panne'),
        etiquette: (rang) => String(lignes[rang].nombre), couleurs: lignes.map((ligne) => (ligne.code ? null : Indicateurs.COULEUR_AUTRES)),
        largeurLibelles: UI.estTelephone() ? 110 : 170 }),
      hauteur: Indicateurs.options.hauteurBarres(lignes.length),
      colonnes: [{ cle: 'code', libelle: 'Code' }, { cle: 'libelle', libelle: 'Cause' }, { cle: 'nombre', libelle: 'Pannes', type: 'nombre', decimales: 0 }],
      lignes, vide: lignes.length ? '' : 'Aucune panne sur la période.',
    };
  }

  function grapheCharge(jour) {
    const lundi = typeof Planning !== 'undefined' && typeof Planning.lundiDe === 'function' ? Planning.lundiDe(jour) : jour;
    const techniciens = Indicateurs.chargeCapacite(lundi, 4);
    const lignes = [].concat(...techniciens.map((ligne) => ligne.semaines.map((semaine) => ({
      technicien: nomTechnicien(ligne.technicien), semaine: UI.dateFr(semaine.lundi), charge: semaine.charge, capacite: semaine.capacite }))));
    return {
      id: 'charge', titre: 'Charge et capacité des techniciens',
      sousTitre: 'Heures prévues des OT planifiés, semaine par semaine (4 semaines à partir du ' + UI.dateFr(lundi) + ') ; trait : capacité hebdomadaire.',
      option: Indicateurs.options.chargeCapacite(techniciens.map((ligne) => ({ libelle: nomCourt(ligne.technicien), semaines: ligne.semaines }))),
      colonnes: [{ cle: 'technicien', libelle: 'Technicien' }, { cle: 'semaine', libelle: 'Semaine du' },
        { cle: 'charge', libelle: 'Charge (h)', type: 'nombre', decimales: 1 }, { cle: 'capacite', libelle: 'Capacité (h)', type: 'nombre', decimales: 1 }],
      lignes, vide: techniciens.length ? '' : 'Aucun technicien actif.',
    };
  }

  /** Les sept graphiques, lancés ensemble (ECharts est chargé une seule fois pour tous). */
  function dessinerGraphiques(conteneur, periode, filtres, jour) {
    const suffixe = '-' + periode.debut + '-au-' + periode.fin;
    const listeA = equipementsA(periode, filtres);
    [].concat(grapheParetos(periode, filtres), [grapheHeures(periode, filtres),
      grapheCriticiteA(listeA, filtres, 'mtbf', 'MTBF'), grapheCriticiteA(listeA, filtres, 'mttr', 'MTTR'),
      grapheCauses(periode, filtres), grapheCharge(jour)])
      .forEach((definition) => {
        Indicateurs.graphique(conteneur, Object.assign({ classe: 'c6', nomFichier: 'indicateurs-' + definition.id + suffixe }, definition));
      });
  }

  // ===========================================================================================
  // 18. Tableau par équipement
  // ===========================================================================================

  /** Cellule d'un résultat : valeur arrondie, ou sa raison (« non calculable : … »). */
  function cellule(resultat, format) {
    return resultat.valeur === null ? UI.html`<span class="indicateurs-raison">${resultat.raison}</span>` : format(resultat.valeur);
  }

  function valeurTri(resultat) {
    return resultat.valeur === null ? null : resultat.valeur;
  }

  function tableauEquipements(periode, filtres) {
    const ctx = contexte();
    const lignes = Array.from(ctx.equipements.values()).filter((equipement) => estSuivi(equipement) && passeFiltres(equipement, filtres, ctx))
      .map((equipement) => Object.assign({ equipement }, Indicateurs.parEquipement(equipement.id, periode, ctx)));
    const heures = (valeur) => formats.nombre(valeur, 1);
    return UI.tableau({
      libelle: 'Indicateurs par équipement', vide: 'Aucun équipement suivi pour ces filtres.',
      triInitial: { cle: 'pannes', sens: 'desc' },
      colonnes: [
        { cle: 'repere', libelle: 'Équipement', valeurTri: (l) => texte(l.equipement.repere) || l.equipement.id,
          rendu: (l) => UI.html`<a href="#/equipement/${encodeURIComponent(l.equipement.id)}">${texte(l.equipement.repere) || l.equipement.id}</a>
            <small class="indicateurs-designation">${l.equipement.designation || ''}</small>` },
        { cle: 'criticite', libelle: 'Criticité', valeurTri: (l) => l.equipement.criticite, rendu: (l) => l.equipement.criticite || '' },
        { cle: 'pannes', libelle: 'Pannes', type: 'nombre', valeurTri: (l) => l.pannes.valeur, rendu: (l) => String(l.pannes.valeur) },
        { cle: 'arret', libelle: 'Arrêt (h)', type: 'nombre', valeurTri: (l) => valeurTri(l.dureeArret), rendu: (l) => cellule(l.dureeArret, heures) },
        { cle: 'mtbf', libelle: 'MTBF (h)', type: 'nombre', valeurTri: (l) => valeurTri(l.mtbf), rendu: (l) => cellule(l.mtbf, heures) },
        { cle: 'mttr', libelle: 'MTTR (h)', type: 'nombre', valeurTri: (l) => valeurTri(l.mttr), rendu: (l) => cellule(l.mttr, heures) },
        { cle: 'disponibilite', libelle: 'Disponibilité', type: 'nombre', valeurTri: (l) => valeurTri(l.disponibilite),
          rendu: (l) => cellule(l.disponibilite, formats.pourcentage) },
        { cle: 'cout', libelle: 'Coût', type: 'nombre', valeurTri: (l) => valeurTri(l.cout), rendu: (l) => cellule(l.cout, formats.euros) },
      ],
      lignes,
    });
  }

  // ===========================================================================================
  // 19. Enregistrement de l'écran (App est chargé après les modules, §8)
  // ===========================================================================================

  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'indicateurs', route: /^#\/indicateurs$/, titre: 'Indicateurs',
      menu: { libelle: 'Indicateurs', icone: 'indicateurs', ordre: 50 },
      profils: ['responsable'], tables: TABLES,
      afficher: afficherEcran,
    });
  });

  return {};
})());
