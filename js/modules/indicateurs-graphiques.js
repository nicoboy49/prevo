'use strict';
// Indicateurs (3/4) — graphiques ECharts de l'écran Indicateurs : thème de la charte, légende,
// « Voir les valeurs », exports CSV et PNG (ARCHITECTURE.md §15.4 ; brief §2 bis et §12).
//
//   Indicateurs.graphique(conteneur, { titre, option, colonnes, lignes, nomFichier,
//                                      id, classe, sousTitre, notes, vide })
// ajoute au conteneur une carte (titre, boutons « CSV » et « Image », légende, graphique, tableau
// « Voir les valeurs »), charge ECharts à la demande (App.chargerEcharts) puis dessine le graphique
// en SVG. Promesse : l'instance ECharts, ou null (pas de données, ECharts introuvable).
//   - option   : option ECharts « brute » (données, axes, séries) ; ce fichier l'habille du thème ;
//   - colonnes : [{ cle, libelle, type: 'nombre' | 'texte', decimales, raison, protege }] et
//     lignes : [{ cle: valeur }] → le tableau « Voir les valeurs » et le fichier CSV (mêmes valeurs) ;
//     colonne `raison` : nom du champ qui dit pourquoi la valeur manque (« non calculable : … ») ;
//   - vide     : texte affiché à la place du graphique quand il n'y a rien à dessiner.
// Les options des sept graphiques de l'écran sont construites ici aussi (Indicateurs.options).
//
// Règles de dessin (skill « dataviz », dans le cadre du contrat) :
//   - couleurs de séries imposées, dans l'ordre et jamais recyclées (COULEURS_SERIES), « autres »
//     à part, jamais une couleur de statut ; séries voisines vérifiées en deutéranopie et protanopie
//     (tests/test_indicateurs.py) ;
//   - un seul axe de valeurs ; légende (au-dessus du graphique) dès 2 séries ;
//   - barres fines (24 px au plus) au bout arrondi de 4 px, grille en trait fin et discret ;
//   - textes (axes, étiquettes, légende, infobulle) aux couleurs de texte de la charte, jamais à
//     la couleur d'une série ;
//   - l'infobulle n'est qu'un plus : chaque valeur est dans « Voir les valeurs ».

Object.assign(Indicateurs, (() => {

  const { arrondi } = Indicateurs.interne;

  // ===========================================================================================
  // 8. Couleurs, formats et thème
  // ===========================================================================================

  // Thème T de la charte « Cockpit » (reference-design) : séries puis « autres ».
  const COULEURS_SERIES = Object.freeze(['#4C7DFF', '#C4841F', '#1498B6', '#8E6CF0']);
  const COULEUR_AUTRES = '#3A4670';
  const POLICE = 'Sora, sans-serif';
  const BARRE_MAX_PX = 24;
  const RAYON_PX = 4;
  const FACTEUR_IMAGE = 2;          // l'image PNG fait deux fois la taille affichée
  const TITRE_IMAGE_PX = 40;        // bande du titre en haut de l'image
  const LEGENDE_IMAGE_PX = 26;      // une ligne de légende (dès 2 séries)
  const LARGEUR_ENTREE_LEGENDE_PX = 165;   // place d'une entrée de légende (« Semaine du 19/10 »)
  const ESPACE_INSECABLE = '\u00A0';
  // Une série dont l'id commence ainsi est une marque de référence (capacité) : couleur du texte.
  const PREFIXE_REFERENCE = 'reference';

  /** Formats d'affichage (arrondis du §15.3 : heures et % à 1 décimale, euros à 2). */
  const formats = {
    heures: (valeur) => UI.nombreFr(arrondi(valeur, 1), 1) + ESPACE_INSECABLE + 'h',
    pourcentage: (fraction) => UI.nombreFr(arrondi(fraction * 100, 1), 1) + ESPACE_INSECABLE + '%',
    euros: (valeur) => UI.euro(arrondi(valeur, 2), 2),
    nombre: (valeur, decimales) => UI.nombreFr(arrondi(valeur, decimales || 0), decimales || 0),
  };

  function lireVariable(style, nom, defaut) {
    return style.getPropertyValue(nom).trim() || defaut;
  }

  /**
   * Couleurs du thème lues dans les variables de la charte (css/style.css) :
   * 'ecran' = thème courant (sombre par défaut, clair possible) ; 'papier' = image PNG, noir sur blanc.
   */
  function jetons(support) {
    const style = getComputedStyle(document.documentElement);
    if (support === 'papier') {
      const trait = lireVariable(style, '--encre-trait', '#888888');
      return {
        texte: lireVariable(style, '--encre', '#000000'), texte2: lireVariable(style, '--encre-2', '#333333'),
        discret: lireVariable(style, '--encre-2', '#333333'), axe: trait, grille: trait, opaciteGrille: 0.35,
        fond: lireVariable(style, '--papier', '#FFFFFF'), bulle: lireVariable(style, '--papier', '#FFFFFF'), ombre: trait,
      };
    }
    return {
      texte: lireVariable(style, '--texte', '#E8EDFF'), texte2: lireVariable(style, '--texte-2', '#B7C1E6'),
      discret: lireVariable(style, '--muted', '#7D89B5'), axe: lireVariable(style, '--trait-2', 'rgba(255,255,255,.12)'),
      grille: lireVariable(style, '--trait', 'rgba(255,255,255,.07)'), opaciteGrille: 1,
      fond: lireVariable(style, '--carte', '#121B36'), bulle: lireVariable(style, '--carte-2', '#172245'),
      ombre: lireVariable(style, '--teinte-neutre', 'rgba(255,255,255,.07)'),
    };
  }

  function mouvementReduit() {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  function enListe(valeur) {
    if (valeur === undefined || valeur === null) return [];
    return Array.isArray(valeur) ? valeur : [valeur];
  }

  /** Couleur d'une série (celle de ses barres, ou du texte pour une marque de référence). */
  function couleurSerie(serie, couleurs) {
    if (String(serie.id || '').startsWith(PREFIXE_REFERENCE)) return couleurs.texte2;
    return (serie.itemStyle && serie.itemStyle.color) || COULEURS_SERIES[0];
  }

  function habillerAxe(axe, couleurs) {
    const valeurs = axe.type === 'value';
    return Object.assign({}, axe, {
      axisLine: { show: !valeurs, lineStyle: { color: couleurs.axe } },
      axisTick: { show: false },
      axisLabel: Object.assign({ color: couleurs.discret, fontFamily: POLICE, fontSize: 12, hideOverlap: true }, axe.axisLabel || {}),
      splitLine: { show: valeurs, lineStyle: { color: couleurs.grille, width: 1, type: 'solid', opacity: couleurs.opaciteGrille } },
      nameTextStyle: { color: couleurs.discret, fontFamily: POLICE },
    });
  }

  function habillerSerie(serie, couleurs) {
    const copie = Object.assign({}, serie, { itemStyle: Object.assign({}, serie.itemStyle, { color: couleurSerie(serie, couleurs) }) });
    // Segments empilés : un liseré de la couleur du fond les sépare (2 px entre deux segments).
    if (serie.stack) Object.assign(copie.itemStyle, { borderColor: couleurs.fond, borderWidth: 1 });
    if (serie.label) copie.label = Object.assign({ color: couleurs.texte2, fontFamily: POLICE, fontSize: 12 }, serie.label);
    return copie;
  }

  /**
   * Option complète : l'option brute habillée du thème. support 'ecran' (infobulle, animation
   * sauf mouvement réduit) ou 'papier' (titre et légende dessinés, fond blanc, rien d'animé ;
   * `largeur` de l'image : la légende peut y tenir sur plusieurs lignes).
   */
  function habiller(option, support, titre, largeur) {
    const couleurs = jetons(support);
    const papier = support === 'papier';
    const series = enListe(option.series).map((serie) => habillerSerie(serie, couleurs));
    const resultat = Object.assign({}, option, {
      backgroundColor: papier ? couleurs.fond : 'transparent',
      textStyle: { fontFamily: POLICE, color: couleurs.texte2, fontSize: 13 },
      animation: !papier && !mouvementReduit(),
      grid: Object.assign({ left: 8, right: 24, top: 14, bottom: 6, containLabel: true }, option.grid || {}),
      xAxis: enListe(option.xAxis).map((axe) => habillerAxe(axe, couleurs)),
      yAxis: enListe(option.yAxis).map((axe) => habillerAxe(axe, couleurs)),
      series,
      legend: { show: false },
      aria: { enabled: true, label: { description: I18n.t('indicateurs.habiller.graphique_valeurs_sont_tableau', { titre }) } },
    });
    if (!papier) {
      resultat.tooltip = Object.assign({
        trigger: 'axis', confine: true, axisPointer: { type: 'shadow', shadowStyle: { color: couleurs.ombre } },
        backgroundColor: couleurs.bulle, borderColor: couleurs.axe, borderWidth: 1, padding: [8, 12],
        textStyle: { color: couleurs.texte, fontFamily: POLICE, fontSize: 13 }, extraCssText: 'border-radius: 12px;',
      }, option.tooltip || {});
      return resultat;
    }
    resultat.tooltip = { show: false };
    resultat.title = { text: titre, left: 8, top: 8, textStyle: { color: couleurs.texte, fontFamily: POLICE, fontSize: 15, fontWeight: 600 } };
    resultat.legend = { show: series.length >= 2, top: TITRE_IMAGE_PX - 4, left: 8, right: 8, itemWidth: 12, itemHeight: 12,
      textStyle: { color: couleurs.texte2, fontFamily: POLICE, fontSize: 12 } };
    resultat.grid.top += TITRE_IMAGE_PX + lignesLegende(series.length, largeur) * LEGENDE_IMAGE_PX;
    return resultat;
  }

  /** Nombre de lignes de la légende de l'image (0 pour une seule série). */
  function lignesLegende(nombreSeries, largeur) {
    if (nombreSeries < 2) return 0;
    return Math.ceil(nombreSeries * LARGEUR_ENTREE_LEGENDE_PX / Math.max(LARGEUR_ENTREE_LEGENDE_PX, (largeur || 600) - 16));
  }

  // ===========================================================================================
  // 9. Options des graphiques de l'écran (données → option brute)
  // ===========================================================================================

  /** Valeur d'un point d'infobulle (barre : nombre ; marque de référence : [x, y]). */
  function valeurPoint(point) {
    return Array.isArray(point.value) ? point.value[1] : point.value;
  }

  /** Infobulle « catégorie, puis une ligne par série » ; textes des données échappés. */
  function infobulle(formatValeur) {
    return {
      formatter(points) {
        const liste = enListe(points).filter((point) => {
          const valeur = valeurPoint(point);
          return valeur !== null && valeur !== undefined && valeur !== '-';
        });
        if (!liste.length) return '';
        const entete = UI.echapper(liste[0].axisValueLabel || liste[0].name || '');
        return '<div style="margin-bottom:4px">' + entete + '</div>' + liste.map((point) => point.marker + UI.echapper(point.seriesName)
          + ' : <b>' + UI.echapper(formatValeur(valeurPoint(point))) + '</b>').join('<br>');
      },
    };
  }

  /**
   * Barres horizontales d'une série (catégories de haut en bas). etiquette(rang) → texte au bout
   * de la barre ; couleurs[rang] facultatif (ex. « sans code » en couleur « autres »).
   */
  function barresHorizontales({ nom, categories, valeurs, formatValeur, etiquette, couleurs, margeDroite, largeurLibelles }) {
    return {
      grid: { right: margeDroite || 64 },
      xAxis: { type: 'value', splitNumber: 4, axisLabel: { formatter: (valeur) => UI.nombreFr(valeur) } },
      yAxis: { type: 'category', data: categories, inverse: true, axisLabel: { width: largeurLibelles || 120, overflow: 'truncate' } },
      tooltip: infobulle(formatValeur),
      series: [{
        type: 'bar', name: nom, barMaxWidth: BARRE_MAX_PX,
        data: valeurs.map((valeur, rang) => (couleurs && couleurs[rang] ? { value: valeur, itemStyle: { color: couleurs[rang] } } : valeur)),
        itemStyle: { color: COULEURS_SERIES[0], borderRadius: [0, RAYON_PX, RAYON_PX, 0] },
        label: { show: true, position: 'right', formatter: (point) => etiquette(point.dataIndex) },
      }],
    };
  }

  /** Hauteur (px) d'un graphique en barres horizontales : une bande de 30 px par catégorie. */
  function hauteurBarres(nombre) {
    return Math.max(200, nombre * 30 + 56);
  }

  /** Pareto (top 10, déjà trié) : barres et cumul en % en étiquette. lignes : [{ libelle, valeur, cumulPct }]. */
  function pareto(lignes, nom, formatValeur) {
    return barresHorizontales({
      nom, categories: lignes.map((ligne) => ligne.libelle), valeurs: lignes.map((ligne) => ligne.valeur),
      formatValeur, margeDroite: 104,
      etiquette: (rang) => I18n.t('indicateurs.pareto.cumul_v1_espace_insecable', { cumul: UI.nombreFr(arrondi(lignes[rang].cumulPct, 1), 1), espace: ESPACE_INSECABLE }),
    });
  }

  /** « oct. 25 » pour '2025-10'. */
  function moisCourt(mois) {
    const date = new Date(Date.UTC(Number(mois.slice(0, 4)), Number(mois.slice(5, 7)) - 1, 1));
    return new Intl.DateTimeFormat('fr-FR', { month: 'short', year: '2-digit', timeZone: 'UTC' }).format(date);
  }

  /** Heures par mois, empilées : correctif, préventif, autres. lignes : Indicateurs.heuresParMois. */
  function heuresParMois(lignes) {
    const groupes = [['correctif', I18n.t('indicateurs.heures_par_mois.correctif'), COULEURS_SERIES[0]], ['preventif', I18n.t('indicateurs.heures_par_mois.preventif'), COULEURS_SERIES[1]],
      ['autres', I18n.t('indicateurs.heures_par_mois.autres'), COULEUR_AUTRES]];
    const hauts = lignes.map((ligne) => groupes.reduce((haut, [cle], rang) => (ligne[cle] > 0 ? rang : haut), -1));
    return {
      xAxis: { type: 'category', data: lignes.map((ligne) => moisCourt(ligne.mois)) },
      yAxis: { type: 'value', axisLabel: { formatter: (valeur) => UI.nombreFr(valeur) } },
      tooltip: infobulle(formats.heures),
      series: groupes.map(([cle, nom, couleur], rang) => ({
        type: 'bar', name: nom, stack: 'heures', barMaxWidth: BARRE_MAX_PX,
        // Le segment le plus haut de chaque mois (non nul) porte le bout arrondi.
        data: lignes.map((ligne, mois) => ({ value: ligne[cle],
          itemStyle: { borderRadius: rang === hauts[mois] ? [RAYON_PX, RAYON_PX, 0, 0] : 0 } })),
        itemStyle: { color: couleur },
      })),
    };
  }

  /** Trait horizontal de la capacité, large comme le groupe de barres d'un technicien. */
  function dessinerCapacite(parametres, api) {
    const centre = api.coord([api.value(0), api.value(1)]);
    const largeur = api.size([1, 0])[0] * 0.86;
    return {
      type: 'line', shape: { x1: centre[0] - largeur / 2, y1: centre[1], x2: centre[0] + largeur / 2, y2: centre[1] },
      style: { stroke: api.visual('color'), lineWidth: 2, lineCap: 'round' },
    };
  }

  /**
   * Charge et capacité : un groupe de barres par technicien (une barre par semaine, couleurs dans
   * l'ordre), la capacité en trait horizontal sur le même axe en heures.
   * techniciens : [{ libelle, semaines: [{ lundi, charge, capacite }] }].
   */
  function chargeCapacite(techniciens) {
    const semaines = techniciens.length ? techniciens[0].semaines.map((semaine) => semaine.lundi) : [];
    const barres = semaines.slice(0, COULEURS_SERIES.length).map((lundi, rang) => ({
      type: 'bar', name: I18n.t('indicateurs.charge_capacite.semaine_v1', { date: UI.dateFr(lundi).slice(0, 5) }), barMaxWidth: BARRE_MAX_PX, barGap: '12%',
      data: techniciens.map((technicien) => technicien.semaines[rang].charge),
      itemStyle: { color: COULEURS_SERIES[rang], borderRadius: [RAYON_PX, RAYON_PX, 0, 0] },
    }));
    const capacites = techniciens.map((technicien, rang) => [rang, technicien.semaines.length ? technicien.semaines[0].capacite : null])
      .filter((point) => point[1] !== null && point[1] !== undefined);
    const series = barres.concat(capacites.length ? [{
      type: 'custom', id: PREFIXE_REFERENCE + '-capacite', name: I18n.t('indicateurs.charge_capacite.capacite'), data: capacites, z: 5,
      encode: { x: 0, y: 1 }, renderItem: dessinerCapacite,
    }] : []);
    return {
      xAxis: { type: 'category', data: techniciens.map((technicien) => technicien.libelle),
        // chaque technicien nommé ; sur téléphone, « S. Lambert » sur deux lignes pour tenir
        axisLabel: { interval: 0, hideOverlap: false, width: 90, overflow: 'truncate',
          formatter: (libelle) => (UI.estTelephone() ? libelle.replace('. ', '.\n') : libelle) } },
      yAxis: { type: 'value', axisLabel: { formatter: (valeur) => UI.nombreFr(valeur) } },
      tooltip: infobulle(formats.heures),
      series,
    };
  }

  // ===========================================================================================
  // 10. Carte, légende, tableau « Voir les valeurs »
  // ===========================================================================================

  function legende(series) {
    if (series.length < 2) return '';
    const couleurs = jetons('ecran');
    const bloc = UI.element(UI.html`<div class="legende">${series.map((serie) => UI.html`<span><i class="${serie.type === 'bar' ? 'lg-carre' : 'lg-trait'}" aria-hidden="true"></i>${serie.name}</span>`)}</div>`);
    UI.$$('i', bloc).forEach((pastille, rang) => {
      const couleur = couleurSerie(series[rang], couleurs);
      if (series[rang].type === 'bar') pastille.style.background = couleur; else pastille.style.color = couleur;
    });
    return bloc;
  }

  function texteCellule(colonne, ligne) {
    const valeur = ligne[colonne.cle];
    if (colonne.type !== 'nombre') return valeur === null || valeur === undefined ? '' : String(valeur);
    if (typeof valeur === 'number' && Number.isFinite(valeur)) return formats.nombre(valeur, colonne.decimales);
    return (colonne.raison && ligne[colonne.raison]) || '–';
  }

  /** Tableau simple (non triable) des valeurs du graphique, dans un cadre qui défile. */
  function tableauValeurs(colonnes, lignes, titre) {
    return UI.element(UI.html`<div class="table-defile"><table class="table indicateurs-table-valeurs">
      <caption class="visuellement-cache">${I18n.t('indicateurs.tableau_valeurs.valeurs_titre', { titre })}</caption>
      <thead><tr>${colonnes.map((colonne) => UI.html`<th scope="col" class="${colonne.type === 'nombre' ? 'num' : ''}">${colonne.libelle}</th>`)}</tr></thead>
      <tbody>${lignes.length ? lignes.map((ligne) => UI.html`<tr>${colonnes.map((colonne) => {
        const sansValeur = colonne.type === 'nombre' && !(typeof ligne[colonne.cle] === 'number' && Number.isFinite(ligne[colonne.cle]));
        return UI.html`<td class="${colonne.type === 'nombre' ? 'num' : ''}${sansValeur ? ' indicateurs-raison' : ''}">${texteCellule(colonne, ligne)}</td>`;
      })}</tr>`) : UI.html`<tr><td class="vide-table" colspan="${colonnes.length}">${I18n.t('indicateurs.tableau_valeurs.aucune_valeur_periode')}</td></tr>`}</tbody>
    </table></div>`);
  }

  function creerCarte(reglages) {
    const series = enListe(reglages.option && reglages.option.series);
    const carte = UI.element(UI.html`<article class="carte indicateurs-graphique ${reglages.classe || ''}" data-graphique="${reglages.id || ''}" data-etat="chargement">
      <div class="entete-carte"><h2>${reglages.titre}</h2>
        <div class="indicateurs-exports">
          <button type="button" class="btn btn-fantome" data-export="csv" title="${I18n.t('indicateurs.creer_carte.telecharger_valeurs_csv')}" aria-label="${I18n.t('indicateurs.creer_carte.telecharger_valeurs_csv_2', { reglagesTitre: reglages.titre })}">${UI.icone('export')}${I18n.t('indicateurs.creer_carte.csv')}</button>
          <button type="button" class="btn btn-fantome" data-export="image" disabled title="${I18n.t('indicateurs.creer_carte.telecharger_image_png')}" aria-label="${I18n.t('indicateurs.creer_carte.telecharger_image_png_2', { reglagesTitre: reglages.titre })}">${UI.icone('export')}${I18n.t('indicateurs.creer_carte.image')}</button>
        </div></div>
      ${reglages.sousTitre ? UI.html`<p class="note indicateurs-sous-titre">${reglages.sousTitre}</p>` : ''}
      <div class="indicateurs-legende"></div>
      <div class="graph" role="img" aria-label="${reglages.titre}"></div>
      ${enListe(reglages.notes).map((note) => UI.html`<p class="note indicateurs-note">${note}</p>`)}
      <details class="vue-tableau"><summary>${I18n.t('indicateurs.creer_carte.voir_valeurs')}</summary><div class="indicateurs-valeurs"></div></details>
    </article>`);
    if (!reglages.vide) UI.remplir(UI.$('.indicateurs-legende', carte), legende(series));
    if (reglages.hauteur) UI.$('.graph', carte).style.height = reglages.hauteur + 'px';   // barres horizontales : selon le nombre
    UI.$('.indicateurs-valeurs', carte).appendChild(tableauValeurs(reglages.colonnes || [], reglages.lignes || [], reglages.titre));
    return carte;
  }

  /** Remplace la zone du graphique par un texte (pas de données, ou ECharts introuvable). */
  function remplacerZone(carte, etat, contenu) {
    const zone = UI.$('.graph', carte);
    zone.className = 'indicateurs-graph-' + etat;
    zone.removeAttribute('role');
    zone.removeAttribute('aria-label');
    UI.remplir(zone, contenu);
    carte.dataset.etat = etat;
  }

  function montrerEchec(carte, erreur) {
    remplacerZone(carte, 'erreur', UI.bandeau('attention', UI.html`${I18n.html('indicateurs.montrer_echec.graphique_pas_pu_afficher', { message: (erreur && erreur.message) || '' })}`));
    UI.$('.vue-tableau', carte).open = true;
  }

  // ===========================================================================================
  // 11. Exports : CSV (format §3.1) et image PNG (SVG du graphique dessiné sur un <canvas>)
  // ===========================================================================================

  function celluleCsv(texte) {
    return /[;"\r\n]|^[ \t]|[ \t]$/.test(texte) ? '"' + texte.replace(/"/g, '""') + '"' : texte;
  }

  /** Valeur d'une cellule CSV : nombre au point décimal (arrondi comme à l'écran) ; texte protégé
   *  par l'apostrophe si Excel risquait de l'abîmer (§3.2). */
  function valeurCsv(colonne, ligne) {
    const valeur = ligne[colonne.cle];
    if (colonne.type === 'nombre' && typeof valeur === 'number' && Number.isFinite(valeur)) {
      return String(arrondi(valeur, colonne.decimales || 0));
    }
    const texte = colonne.type === 'nombre' ? ((colonne.raison && ligne[colonne.raison]) || '') : valeur;
    return Donnees.csv.ecrireValeur({ type: 'texte', protege: colonne.protege === true }, texte === null || texte === undefined ? '' : String(texte));
  }

  /** Octets du CSV : BOM UTF-8, « ; », CRLF, en-tête = libellés des colonnes. */
  function octetsCsv(colonnes, lignes) {
    const texte = [colonnes.map((colonne) => celluleCsv(colonne.libelle)).join(';')]
      .concat(lignes.map((ligne) => colonnes.map((colonne) => celluleCsv(valeurCsv(colonne, ligne))).join(';')))
      .join('\r\n') + '\r\n';
    const corps = new TextEncoder().encode(texte);
    const octets = new Uint8Array(corps.length + 3);
    octets.set([0xEF, 0xBB, 0xBF], 0);
    octets.set(corps, 3);
    return octets;
  }

  function exporterCsv(reglages) {
    UI.telecharger(reglages.nomFichier + '.csv', new Blob([octetsCsv(reglages.colonnes || [], reglages.lignes || [])], { type: 'text/csv;charset=utf-8' }));
  }

  /** SVG du graphique au thème « papier » (titre, légende, fond blanc), rendu hors écran. */
  function svgPapier(bibliotheque, option, titre, largeur, hauteurGraphique) {
    const hauteur = hauteurGraphique + TITRE_IMAGE_PX + lignesLegende(enListe(option.series).length, largeur) * LEGENDE_IMAGE_PX;
    const horsEcran = bibliotheque.init(null, null, { renderer: 'svg', ssr: true, width: largeur, height: hauteur });
    try {
      horsEcran.setOption(habiller(option, 'papier', titre, largeur));
      return { svg: horsEcran.renderToSVGString(), largeur, hauteur };
    } finally {
      horsEcran.dispose();
    }
  }

  /** PNG (Blob) : le SVG dessiné ×2 sur un <canvas> au fond blanc. */
  function pngDepuisSvg({ svg, largeur, hauteur }) {
    return new Promise((resoudre, rejeter) => {
      const image = new Image();
      image.onload = () => {
        const toile = document.createElement('canvas');
        toile.width = largeur * FACTEUR_IMAGE;
        toile.height = hauteur * FACTEUR_IMAGE;
        const dessin = toile.getContext('2d');
        dessin.fillStyle = jetons('papier').fond;
        dessin.fillRect(0, 0, toile.width, toile.height);
        dessin.drawImage(image, 0, 0, toile.width, toile.height);
        toile.toBlob((blob) => (blob ? resoudre(blob) : rejeter(new Error(I18n.t('indicateurs.png_depuis_svg.image_png_pas_pu')))), 'image/png');
      };
      image.onerror = () => rejeter(new Error(I18n.t('indicateurs.png_depuis_svg.image_graphique_pas_pu')));
      image.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
    });
  }

  async function exporterImage(reglages, zone) {
    try {
      const bibliotheque = await App.chargerEcharts();
      const rendu = svgPapier(bibliotheque, reglages.option, reglages.titre, Math.round(zone.clientWidth), Math.round(zone.clientHeight));
      UI.telecharger(reglages.nomFichier + '.png', await pngDepuisSvg(rendu));
    } catch (erreur) {
      App.signalerErreur(erreur, 'image du graphique « ' + reglages.titre + ' »');
    }
  }

  // ===========================================================================================
  // 12. Indicateurs.graphique : la carte complète
  // ===========================================================================================

  /** Suit la taille de la zone (fenêtre, menu replié, onglet rouvert) ; libère le graphique
   *  quand la zone a quitté la page. */
  function suivreTaille(zone, instance) {
    const observateur = new ResizeObserver(() => {
      if (instance.isDisposed()) { observateur.disconnect(); return; }       // déjà libéré (libererGraphiques)
      if (!zone.isConnected) { observateur.disconnect(); instance.dispose(); return; }
      if (zone.clientWidth && zone.clientHeight) instance.resize();
    });
    observateur.observe(zone);
  }

  async function graphique(conteneur, reglages) {
    const carte = creerCarte(reglages);
    conteneur.appendChild(carte);
    UI.$('[data-export="csv"]', carte).addEventListener('click', () => exporterCsv(reglages));
    if (reglages.vide) {
      remplacerZone(carte, 'vide', UI.html`<p class="muted">${reglages.vide}</p>`);
      return null;
    }
    let bibliotheque;
    try {
      bibliotheque = await App.chargerEcharts();
    } catch (erreur) {
      montrerEchec(carte, erreur);
      return null;
    }
    const zone = UI.$('.graph', carte);
    if (!carte.isConnected) return null;              // écran déjà remplacé pendant le chargement
    let instance;
    try {
      instance = bibliotheque.init(zone, null, { renderer: 'svg' });
      instance.setOption(habiller(reglages.option, 'ecran', reglages.titre));
    } catch (erreur) {
      montrerEchec(carte, erreur);
      throw erreur;                                   // défaut du code : il doit se voir
    }
    suivreTaille(zone, instance);
    const boutonImage = UI.$('[data-export="image"]', carte);
    boutonImage.disabled = false;
    boutonImage.addEventListener('click', () => exporterImage(reglages, zone));
    carte.dataset.etat = 'pret';
    return instance;
  }

  /** Libère les graphiques dessinés sous `racine` (avant de la vider). */
  function libererGraphiques(racine) {
    if (typeof echarts === 'undefined') return;
    UI.$$('.indicateurs-graphique .graph', racine).forEach((zone) => {
      const instance = echarts.getInstanceByDom(zone);
      if (instance) instance.dispose();
    });
  }

  Object.assign(Indicateurs.interne, { formats });

  return {
    COULEURS_SERIES, COULEUR_AUTRES,
    graphique, libererGraphiques,
    // option habillée du thème (support 'ecran' ou 'papier'), réutilisable par le rapport mensuel
    habillerOption: habiller,
    options: { barresHorizontales, pareto, heuresParMois, chargeCapacite, hauteurBarres },
  };
})());
