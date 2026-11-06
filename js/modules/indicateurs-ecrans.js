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
      periode: Indicateurs.libellesPeriodes()[requete.get('periode')] ? requete.get('periode') : '12-mois',
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
      <div class="entete-page"><div><h1>${I18n.t('indicateurs.ecran.indicateurs')}</h1>
        <p>${I18n.t('indicateurs.ecran.fiabilite_equipements_preventif_delais')}</p></div></div>
      <div class="indicateurs-onglets"></div>
    </div>`);
    UI.onglets(UI.$('.indicateurs-onglets', conteneur), [
      { id: 'tableau', libelle: I18n.t('indicateurs.ecran.tableau_bord'), afficher: (panneau) => afficherTableauDeBord(panneau, reglages) },
      { id: 'rapports', libelle: I18n.t('indicateurs.ecran.rapports_mensuels'), afficher: afficherRapports },
    ], {
      actif: reglages.onglet, libelle: I18n.t('indicateurs.ecran.rubriques_indicateurs'),
      surChangement: (id) => { reglages.onglet = id; remplacerAdresse(reglages); },
    });
  }

  function afficherRapports(panneau) {
    if (typeof Rapport !== 'undefined' && typeof Rapport.afficherOnglet === 'function') {
      Rapport.afficherOnglet(panneau);
      return;
    }
    UI.remplir(panneau, UI.vide(I18n.t('indicateurs.ecran.rapports_mensuels'), I18n.t('indicateurs.rapports.rapports_mensuels_arrivent_tache'), 'document'));
  }

  // ===========================================================================================
  // 15. Onglet « Tableau de bord » : filtres, puis résultats (recalculés à chaque changement)
  // ===========================================================================================

  function options(liste, choisie) {
    return liste.map(([valeur, libelle]) => UI.html`<option value="${valeur}"${valeur === choisie ? UI.brut(' selected') : ''}>${libelle}</option>`);
  }

  function afficherTableauDeBord(panneau, reglages) {
    const libelles = Indicateurs.libellesPeriodes();
    const periodes = Object.keys(libelles).map((code) => [code, libelles[code]]);
    UI.remplir(panneau, UI.html`
      <form class="filtres indicateurs-filtres" data-hors-saisie aria-label="${I18n.t('indicateurs.tableau_de_bord.periode_filtres')}">
        <label class="champ"><span class="libelle">${I18n.t('indicateurs.tableau_de_bord.periode')}</span>
          <select id="indicateurs-periode" name="periode">${options(periodes, reglages.periode)}</select></label>
        <label class="champ indicateurs-date" hidden><span class="libelle">${I18n.t('indicateurs.tableau_de_bord.du')}</span>
          <input type="date" id="indicateurs-du" name="du" value="${reglages.du}"></label>
        <label class="champ indicateurs-date" hidden><span class="libelle">${I18n.t('indicateurs.tableau_de_bord.au')}</span>
          <input type="date" id="indicateurs-au" name="au" value="${reglages.au}"></label>
        <label class="champ"><span class="libelle">${I18n.t('commun.champ.criticite')}</span>
          <select id="indicateurs-criticite" name="criticite">${options([['', I18n.t('indicateurs.tableau_de_bord.toutes')]].concat(CRITICITES.map((c) => [c, I18n.t('indicateurs.tableau_de_bord.criticite_c', { c: Schema.libelleValeur('equipements', 'criticite', c) })])), reglages.criticite)}</select></label>
        <label class="champ"><span class="libelle">${I18n.t('indicateurs.tableau_de_bord.atelier')}</span>
          <select id="indicateurs-atelier" name="atelier">${options([['', I18n.t('indicateurs.tableau_de_bord.tous_ateliers')]].concat(ateliers().map((l) => [l.id, l.libelle || l.id])), reglages.atelier)}</select></label>
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
        <article class="carte c12 indicateurs-delais"><h2>${I18n.t('indicateurs.resultats.delais_prise_charge')}</h2>${delais(global.delais)}</article>
        <article class="carte c12 indicateurs-equipements-carte"><div class="entete-carte"><h2>${I18n.t('indicateurs.resultats.equipement')}</h2></div>
          <p class="note">${I18n.t('indicateurs.resultats.equipements_suivis_cliquez_tete', { resumeFiltres: resumeFiltres(filtres) })}</p>
          <div class="indicateurs-equipements"></div></article>
      </div>`);
    UI.$('.indicateurs-equipements', zone).appendChild(tableauEquipements(periode, filtres));
    dessinerGraphiques(UI.$('.indicateurs-graphiques', zone), periode, filtres, jour);
  }

  function resumeFiltres(filtres) {
    const morceaux = [];
    if (filtres.criticite) morceaux.push(I18n.t('indicateurs.resume_filtres.criticite_criticite', { criticite: Schema.libelleValeur('equipements', 'criticite', filtres.criticite) }));
    if (filtres.atelier) {
      const atelier = Donnees.trouver('localisations', filtres.atelier);
      morceaux.push((atelier && atelier.libelle) || filtres.atelier);
    }
    return morceaux.length ? ' — ' + morceaux.join(', ') : '';
  }

  // ===========================================================================================
  // 16. Bandeau d'instruments et encadré « Comprendre »
  // ===========================================================================================

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
    const resume = (ots.length ? I18n.t('indicateurs.sources.ot_sources', { n: ots.length }) : '')
      + (ots.length && exclus.length ? ' · ' : '') + (exclus.length ? I18n.t('indicateurs.sources.ot_exclus', { n: exclus.length }) : '');
    return UI.html`<details class="indicateurs-sources"><summary>${resume}</summary>
      ${ots.length ? UI.html`<p>${ots.slice(0, SOURCES_MAX).map((id, rang) => UI.html`${rang ? ', ' : ''}${lien(id)}`)}${ots.length > SOURCES_MAX
        ? ' ' + I18n.t('indicateurs.sources.v1_autres', { n: (ots.length - SOURCES_MAX) }) : ''}</p>` : ''}
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
    const perimetre = requis.valeur === null ? null : I18n.t('indicateurs.instruments.n_equipements', { n: requis.effectif }) + (sansHeures ? ' ' + I18n.t('indicateurs.instruments.autres_sans_heures_fonctionnement', { n: sansHeures }) : '');
    const mttr = global.mttr;
    const attente = global.attentePieces;
    const preventif = global.respectPreventif;
    return [
      instrument({ cle: 'disponibilite', libelle: I18n.t('indicateurs.instruments.disponibilite'), resultat: global.disponibilite, format: formats.pourcentage,
        valeurAffichee: enPourcentage,
        complements: [I18n.t('indicateurs.instruments.pannes_perimetre', { n: nbPannes, perimetre }), global.disponibilite.note ? phrase(global.disponibilite.note) : ''] }),
      instrument({ cle: 'mtbf', libelle: I18n.t('indicateurs.instruments.mtbf_temps_moyen_entre'), resultat: global.mtbf, format: formats.heures,
        valeurAffichee: enHeures, complements: [I18n.t('indicateurs.instruments.n_pannes_perimetre', { n: nbPannes, perimetre })] }),
      instrument({ cle: 'mttr', libelle: I18n.t('indicateurs.instruments.mttr_temps_moyen_retablissement'), resultat: mttr, format: formats.heures,
        valeurAffichee: enHeures,
        complements: [I18n.t('indicateurs.instruments.pannes_mesurables', { n: mttr.effectif }) + (mttr.exclus.length ? ' ' + I18n.t('indicateurs.instruments.autres_non_cloturee_sans', { n: mttr.exclus.length }) : ''),
        attente.valeur === null ? '' : UI.html`<div class="comp indicateurs-attente">${I18n.t('indicateurs.instruments.dont_attente_pieces_historique', { attenteValeur: formats.heures(attente.valeur), n: attente.effectif })}</div>`] }),
      instrument({ cle: 'duree-arret', libelle: I18n.t('indicateurs.instruments.duree_arret'), resultat: global.dureeArret, format: formats.heures,
        valeurAffichee: enHeures,
        complements: [I18n.t('indicateurs.instruments.pannes_duree', { n: global.dureeArret.effectif }) + (global.dureeArret.exclus.length ? ' ' + I18n.t('indicateurs.instruments.sans_duree_arret', { nbExclus: global.dureeArret.exclus.length }) : '')] }),
      instrument({ cle: 'part-preventif', libelle: I18n.t('indicateurs.instruments.part_preventif'), resultat: global.partPreventif, format: formats.pourcentage,
        valeurAffichee: enPourcentage,
        complements: [global.partPreventif.note ? I18n.t('indicateurs.instruments.note_periode', { note: global.partPreventif.note }) : ''] }),
      instrument({ cle: 'respect-preventif', libelle: I18n.t('indicateurs.instruments.respect_preventif'), resultat: preventif, format: formats.pourcentage,
        valeurAffichee: enPourcentage,
        complements: [preventif.note, preventif.exclus.length ? I18n.t('indicateurs.instruments.ot_exclus_date_prevue', { n: preventif.exclus.length }) : ''] }),
      instrument({ cle: 'ot-en-retard', libelle: I18n.t('indicateurs.instruments.ot_retard'), resultat: global.otEnRetard, format: String,
        valeurAffichee: (valeur) => valeur, lien: '#/ot?filtre=retard',
        complements: [I18n.t('indicateurs.instruments.date_prevue_depassee', { jour: UI.dateFr(jour) })] }),
      instrument({ cle: 'cout', libelle: I18n.t('indicateurs.instruments.cout_maintenance'), resultat: global.cout, format: formats.euros,
        valeurAffichee: enEuros, complements: [I18n.t('indicateurs.instruments.ot_clotures_pieces_prix', { n: global.cout.effectif })] }),
      instrument({ cle: 'valeur-stock', libelle: I18n.t('indicateurs.instruments.valeur_stock'), resultat: global.valeurStock, format: formats.euros,
        valeurAffichee: enEuros,
        complements: [I18n.t('indicateurs.instruments.articles_tout_magasin', { n: global.valeurStock.effectif }) + (global.valeurStock.exclus.length ? ' ' + I18n.t('indicateurs.instruments.sans_prix', { nbExclus: global.valeurStock.exclus.length }) : '')] }),
    ];
  }

  /** Ce qui n'a pas pu être calculé sur la sélection, avec la raison. */
  function nonCalculables(global) {
    const libelles = { disponibilite: I18n.t('indicateurs.instruments.disponibilite'), mtbf: 'MTBF', mttr: 'MTTR', dureeArret: I18n.t('indicateurs.instruments.duree_arret'),
      partPreventif: I18n.t('indicateurs.instruments.part_preventif'), respectPreventif: I18n.t('indicateurs.instruments.respect_preventif'), attentePieces: I18n.t('indicateurs.non_calculables.attente_pieces') };
    const lignes = Object.keys(libelles).filter((cle) => global[cle].valeur === null)
      .map((cle) => UI.html`<li><b>${libelles[cle]}</b> : ${global[cle].raison}.</li>`);
    const sansHeures = global.tempsRequis.exclus;
    if (sansHeures.length) {
      const reperes = sansHeures.map((element) => { const equipement = Donnees.trouver('equipements', element.id); return (equipement && equipement.repere) || element.id; });
      lignes.push(UI.html`<li>${I18n.html('indicateurs.non_calculables.sans_temps_requis_ils', { n: sansHeures.length, pluriel: I18n.t('indicateurs.instruments.n_equipements', { n: sansHeures.length }), join: reperes.join(', '), raison: sansHeures[0].raison })}</li>`);
    }
    return lignes;
  }

  function comprendre(global) {
    const tolerance = Donnees.parametre('tolerance_preventif_pct', '10');
    const manques = nonCalculables(global);
    return UI.html`<details class="encadre indicateurs-comprendre"><summary>${I18n.t('indicateurs.comprendre.comprendre_indicateurs')}</summary>
      <ul>
        <li>${I18n.html('indicateurs.comprendre.panne_ot_correctif_immediat')}</li>
        <li>${I18n.html('indicateurs.comprendre.temps_requis_heures_fonctionnement')}</li>
        <li>${I18n.html('indicateurs.comprendre.duree_arret_somme_durees')}</li>
        <li>${I18n.html('indicateurs.comprendre.mtbf_temps_moyen_entre')}</li>
        <li>${I18n.html('indicateurs.comprendre.mttr_temps_moyen_retablissement')}</li>
        <li>${I18n.html('indicateurs.comprendre.dont_attente_pieces_moyenne')}</li>
        <li>${I18n.html('indicateurs.comprendre.disponibilite_mtbf_mtbf_mttr')}</li>
        <li>${I18n.html('indicateurs.comprendre.part_preventif_heures_passees')}</li>
        <li>${I18n.html('indicateurs.comprendre.respect_preventif_part_ot', { tolerance })}</li>
        <li>${I18n.html('indicateurs.comprendre.ot_retard_ot_ouverts')}</li>
        <li>${I18n.html('indicateurs.comprendre.delai_prise_charge_temps')}</li>
        <li>${I18n.html('indicateurs.comprendre.cout_main_uvre_pieces')}</li>
        <li>${I18n.html('indicateurs.comprendre.valeur_stock_stock_prix')}</li>
      </ul>
      ${manques.length ? UI.html`<h3>${I18n.t('indicateurs.comprendre.non_calculable_selection')}</h3><ul class="indicateurs-manques">${manques}</ul>` : ''}
    </details>`;
  }

  /** Délais de prise en charge par priorité (médiane, part dans le délai cible, effectif). */
  function delais(parPriorite) {
    return UI.html`<div class="table-defile"><table class="table">
      <caption class="visuellement-cache">${I18n.t('indicateurs.delais.delais_prise_charge_priorite')}</caption>
      <thead><tr><th scope="col">${I18n.t('commun.champ.priorite')}</th><th scope="col" class="num">${I18n.t('indicateurs.delais.delai_cible')}</th><th scope="col" class="num">${I18n.t('indicateurs.delais.mediane')}</th>
        <th scope="col" class="num">${I18n.t('indicateurs.delais.delai')}</th><th scope="col" class="num">${I18n.t('indicateurs.delais.ot_comptes')}</th></tr></thead>
      <tbody>${PRIORITES.map((priorite) => {
        const ligne = parPriorite[priorite];
        return UI.html`<tr><td>${UI.badgePriorite(priorite)}</td>
          <td class="num">${ligne.cible === null ? I18n.t('indicateurs.delais.aucun') : formats.heures(ligne.cible)}</td>
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

  const COLONNE_EQUIPEMENT = { cle: 'equipement', get libelle() { return I18n.t('commun.champ.equipement'); }, protege: true };

  function grapheParetos(periode, filtres) {
    const pannes = Indicateurs.paretoPannes(periode, 10, filtres)
      .map((ligne) => ({ equipement: repere(ligne.equipementId), libelle: repere(ligne.equipementId), valeur: ligne.valeur, cumulPct: ligne.cumulPct }));
    const arrets = Indicateurs.paretoArrets(periode, 10, filtres)
      .map((ligne) => ({ equipement: repere(ligne.equipementId), libelle: repere(ligne.equipementId), valeur: ligne.valeur, cumulPct: ligne.cumulPct }));
    const cumul = { cle: 'cumulPct', libelle: I18n.t('indicateurs.graphe_paretos.cumul'), type: 'nombre', decimales: 1 };
    return [
      { id: 'pareto-pannes', titre: I18n.t('indicateurs.graphe_paretos.pareto_pannes'), sousTitre: I18n.t('indicateurs.graphe_paretos.nombre_pannes_10_equipements'),
        option: Indicateurs.options.pareto(pannes, I18n.t('indicateurs.graphe_paretos.pannes'), (valeur) => I18n.t('indicateurs.graphe_paretos.n_pannes', { n: valeur })),
        colonnes: [COLONNE_EQUIPEMENT, { cle: 'valeur', libelle: I18n.t('indicateurs.graphe_paretos.pannes'), type: 'nombre', decimales: 0 }, cumul],
        lignes: pannes, hauteur: Indicateurs.options.hauteurBarres(pannes.length), vide: pannes.length ? '' : I18n.t('indicateurs.graphe_paretos.aucune_panne_periode') },
      { id: 'pareto-arrets', titre: I18n.t('indicateurs.graphe_paretos.pareto_durees_arret'), sousTitre: I18n.t('indicateurs.graphe_paretos.heures_arret_10_equipements'),
        option: Indicateurs.options.pareto(arrets, I18n.t('indicateurs.instruments.duree_arret'), formats.heures),
        colonnes: [COLONNE_EQUIPEMENT, { cle: 'valeur', libelle: I18n.t('indicateurs.graphe_paretos.duree_arret_h'), type: 'nombre', decimales: 1 }, cumul],
        lignes: arrets, hauteur: Indicateurs.options.hauteurBarres(arrets.length), vide: arrets.length ? '' : I18n.t('indicateurs.graphe_paretos.aucune_duree_arret_saisie') },
    ];
  }

  function grapheHeures(periode, filtres) {
    const lignes = Indicateurs.heuresParMois(periode.fin.slice(0, 7), 12, filtres)
      .map((ligne) => Object.assign({ libelle: ligne.mois.slice(5, 7) + '/' + ligne.mois.slice(0, 4) }, ligne));
    const total = lignes.reduce((somme, ligne) => somme + ligne.correctif + ligne.preventif + ligne.autres, 0);
    const heures = (cle, libelle) => ({ cle, libelle, type: 'nombre', decimales: 1 });
    return {
      id: 'heures-mois', titre: I18n.t('indicateurs.graphe_heures.heures_correctif_preventif_autres'), classe: 'c12',
      sousTitre: I18n.t('indicateurs.graphe_heures.heures_passees_temps_saisis', { dernierMois: lignes[lignes.length - 1].libelle }),
      option: Indicateurs.options.heuresParMois(lignes),
      colonnes: [{ cle: 'libelle', libelle: I18n.t('indicateurs.graphe_heures.mois') }, heures('correctif', I18n.t('indicateurs.graphe_heures.correctif_h')), heures('preventif', I18n.t('indicateurs.graphe_heures.preventif_h')), heures('autres', I18n.t('indicateurs.graphe_heures.autres_h'))],
      lignes, vide: total > 0 ? '' : I18n.t('indicateurs.graphe_heures.aucune_heure_saisie_12'),
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
      id: cle + '-a', titre: I18n.t('indicateurs.graphe_criticite_a.titre_equipements', { titre }),
      sousTitre: filtres.atelier ? I18n.t('indicateurs.graphe_criticite_a.equipements_criticite_atelier_choisi') : I18n.t('indicateurs.graphe_criticite_a.equipements_criticite_heures'),
      option: Indicateurs.options.barresHorizontales({ nom: titre, categories: calcules.map((ligne) => ligne.libelle),
        valeurs: calcules.map((ligne) => ligne.valeur), formatValeur: formats.heures, etiquette: (rang) => formats.heures(calcules[rang].valeur), margeDroite: 80 }),
      notes: manquants ? [I18n.t('indicateurs.graphe_criticite_a.equipements_sans_valeur_raison', { n: manquants })] : [],
      colonnes: [COLONNE_EQUIPEMENT, { cle: 'valeur', libelle: titre + ' (h)', type: 'nombre', decimales: 1, raison: 'raison' }],
      lignes, hauteur: Indicateurs.options.hauteurBarres(calcules.length), vide: calcules.length ? '' : (lignes.length ? I18n.t('indicateurs.graphe_criticite_a.aucune_valeur_calculable_voir') : I18n.t('indicateurs.graphe_criticite_a.aucun_equipement_criticite')),
    };
  }

  function grapheCauses(periode, filtres) {
    const lignes = Indicateurs.causes(periode, filtres);
    return {
      id: 'causes', titre: I18n.t('indicateurs.graphe_causes.causes_pannes'), sousTitre: I18n.t('indicateurs.graphe_causes.nombre_pannes_periode_code'),
      option: Indicateurs.options.barresHorizontales({ nom: 'Pannes', categories: lignes.map((ligne) => ligne.libelle),
        valeurs: lignes.map((ligne) => ligne.nombre), formatValeur: (valeur) => I18n.t('indicateurs.graphe_paretos.n_pannes', { n: valeur }),
        etiquette: (rang) => String(lignes[rang].nombre), couleurs: lignes.map((ligne) => (ligne.code ? null : Indicateurs.COULEUR_AUTRES)),
        largeurLibelles: UI.estTelephone() ? 110 : 170 }),
      hauteur: Indicateurs.options.hauteurBarres(lignes.length),
      colonnes: [{ cle: 'code', libelle: I18n.t('indicateurs.graphe_causes.code') }, { cle: 'libelle', libelle: I18n.t('indicateurs.graphe_causes.cause') }, { cle: 'nombre', libelle: I18n.t('indicateurs.graphe_paretos.pannes'), type: 'nombre', decimales: 0 }],
      lignes, vide: lignes.length ? '' : I18n.t('indicateurs.graphe_paretos.aucune_panne_periode'),
    };
  }

  function grapheCharge(jour) {
    const lundi = typeof Planning !== 'undefined' && typeof Planning.lundiDe === 'function' ? Planning.lundiDe(jour) : jour;
    const techniciens = Indicateurs.chargeCapacite(lundi, 4);
    const lignes = [].concat(...techniciens.map((ligne) => ligne.semaines.map((semaine) => ({
      technicien: nomTechnicien(ligne.technicien), semaine: UI.dateFr(semaine.lundi), charge: semaine.charge, capacite: semaine.capacite }))));
    return {
      id: 'charge', titre: I18n.t('indicateurs.graphe_charge.charge_capacite_techniciens'),
      sousTitre: I18n.t('indicateurs.graphe_charge.heures_prevues_ot_planifies', { lundi: UI.dateFr(lundi) }),
      option: Indicateurs.options.chargeCapacite(techniciens.map((ligne) => ({ libelle: nomCourt(ligne.technicien), semaines: ligne.semaines }))),
      colonnes: [{ cle: 'technicien', libelle: I18n.t('commun.champ.technicien') }, { cle: 'semaine', libelle: I18n.t('indicateurs.graphe_charge.semaine') },
        { cle: 'charge', libelle: I18n.t('indicateurs.graphe_charge.charge_h'), type: 'nombre', decimales: 1 }, { cle: 'capacite', libelle: I18n.t('indicateurs.graphe_charge.capacite_h'), type: 'nombre', decimales: 1 }],
      lignes, vide: techniciens.length ? '' : I18n.t('indicateurs.graphe_charge.aucun_technicien_actif'),
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
      libelle: I18n.t('indicateurs.tableau_equipements.indicateurs_equipement'), vide: I18n.t('indicateurs.tableau_equipements.aucun_equipement_suivi_filtres'),
      triInitial: { cle: 'pannes', sens: 'desc' },
      colonnes: [
        { cle: 'repere', libelle: I18n.t('commun.champ.equipement'), valeurTri: (l) => texte(l.equipement.repere) || l.equipement.id,
          rendu: (l) => UI.html`<a href="#/equipement/${encodeURIComponent(l.equipement.id)}">${texte(l.equipement.repere) || l.equipement.id}</a>
            <small class="indicateurs-designation">${l.equipement.designation || ''}</small>` },
        { cle: 'criticite', libelle: I18n.t('commun.champ.criticite'), valeurTri: (l) => l.equipement.criticite, rendu: (l) => Schema.libelleValeur('equipements', 'criticite', l.equipement.criticite) },
        { cle: 'pannes', libelle: I18n.t('indicateurs.graphe_paretos.pannes'), type: 'nombre', valeurTri: (l) => l.pannes.valeur, rendu: (l) => String(l.pannes.valeur) },
        { cle: 'arret', libelle: I18n.t('indicateurs.tableau_equipements.arret_h'), type: 'nombre', valeurTri: (l) => valeurTri(l.dureeArret), rendu: (l) => cellule(l.dureeArret, heures) },
        { cle: 'mtbf', libelle: I18n.t('indicateurs.tableau_equipements.mtbf_h'), type: 'nombre', valeurTri: (l) => valeurTri(l.mtbf), rendu: (l) => cellule(l.mtbf, heures) },
        { cle: 'mttr', libelle: I18n.t('indicateurs.tableau_equipements.mttr_h'), type: 'nombre', valeurTri: (l) => valeurTri(l.mttr), rendu: (l) => cellule(l.mttr, heures) },
        { cle: 'disponibilite', libelle: I18n.t('indicateurs.instruments.disponibilite'), type: 'nombre', valeurTri: (l) => valeurTri(l.disponibilite),
          rendu: (l) => cellule(l.disponibilite, formats.pourcentage) },
        { cle: 'cout', libelle: I18n.t('indicateurs.tableau_equipements.cout'), type: 'nombre', valeurTri: (l) => valeurTri(l.cout), rendu: (l) => cellule(l.cout, formats.euros) },
      ],
      lignes,
    });
  }

  // ===========================================================================================
  // 19. Enregistrement de l'écran (App est chargé après les modules, §8)
  // ===========================================================================================

  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'indicateurs', route: /^#\/indicateurs$/, get titre() { return I18n.t('indicateurs.ecran.indicateurs'); },
      menu: { get libelle() { return I18n.t('indicateurs.ecran.indicateurs'); }, icone: 'indicateurs', ordre: 50 },
      profils: ['responsable'], tables: TABLES,
      afficher: afficherEcran,
    });
  });

  return {};
})());
