'use strict';
// Parametres (4/4) — sauvegardes du PC serveur dans l'écran Paramètres (ARCHITECTURE.md §22.11 ; CDC D133, CS133).
//   « Tester » : bouton de chaque ligne du tableau des sauvegardes, à côté de « Restaurer… », en mode serveur
//   seulement (App.adaptateur.testerSauvegarde, POST /api/sauvegarde/tester) : le serveur relit chaque fichier de
//   la sauvegarde sans rien écrire ; une fenêtre donne le nombre de lignes de chaque table, ou l'erreur trouvée.
//   Note de la carte : une sauvegarde manuelle par minute au plus (le serveur répond 429 au-delà, et son message
//   s'affiche comme toute erreur), les 60 dernières gardées.
// Modes dossier et démo : ni bouton ni note (rien de tout cela n'y existe). Le tableau des sauvegardes est construit
// par parametres.js, qui appelle ce fichier par un relais (actionsSauvegarde, noteSauvegardes). Complète l'objet
// Parametres.

Object.assign(Parametres.interne, (() => {

  function serveurSaitTester() {
    return App.mode === 'serveur' && typeof App.adaptateur.testerSauvegarde === 'function';
  }

  function pluriel(nombre, singulier, plurielTexte) {
    return nombre + ' ' + (nombre > 1 ? (plurielTexte || singulier + 's') : singulier);
  }

  function libelleTable(nomTable) {
    const description = Schema.table(nomTable);
    return description ? description.libelle : nomTable;
  }

  // Verdict en tête de la fenêtre : lisible (total des lignes), vide, ou tables en erreur.
  function verdict(resultat, tables) {
    const enErreur = tables.filter((table) => table.erreur).length;
    if (resultat.ok) {
      const total = tables.reduce((somme, table) => somme + (Number(table.lignes) || 0), 0);
      return UI.bandeau('succes', UI.html`<b>Sauvegarde lisible :</b> ${pluriel(tables.length, 'table relue', 'tables relues')},
        ${pluriel(total, 'ligne')} en tout.`);
    }
    if (!tables.length) {
      return UI.bandeau('important', UI.html`<b>Sauvegarde vide :</b> elle ne contient aucun fichier de données.`);
    }
    return UI.bandeau('important', UI.html`<b>Problème trouvé :</b> ${pluriel(enErreur, 'table', 'tables')} sur
      ${tables.length} ne se ${enErreur > 1 ? 'relisent' : 'relit'} pas correctement (détail ci-dessous). Avant de
      restaurer, préférez une autre sauvegarde pour ${enErreur > 1 ? 'ces tables' : 'cette table'}.`);
  }

  function contenuResultat(sauvegarde, resultat) {
    const tables = Array.isArray(resultat.tables) ? resultat.tables : [];
    const decrite = Parametres.decrireSauvegarde(sauvegarde.nom);
    const contenu = UI.element(UI.html`<div class="form-colonne" id="resultat-test-sauvegarde" data-ok="${resultat.ok ? '1' : '0'}">
      <p>Sauvegarde du <b>${decrite.date}</b> (${decrite.type.toLowerCase()}) : Prévo a relu chaque fichier sur le PC
        serveur, sans rien modifier.</p>
    </div>`);
    contenu.appendChild(verdict(resultat, tables));
    contenu.appendChild(UI.tableau({
      libelle: 'Tables relues',
      colonnes: [
        { cle: 'table', libelle: 'Table', valeurTri: (l) => libelleTable(l.table),
          rendu: (l) => UI.html`${libelleTable(l.table)} <span class="note">${l.table}.csv</span>` },
        { cle: 'lignes', libelle: 'Lignes', type: 'nombre', valeurTri: (l) => l.lignes,
          rendu: (l) => UI.html`<span data-lignes="${l.table}">${l.lignes === null || l.lignes === undefined ? '—' : String(l.lignes)}</span>` },
        { cle: 'erreur', libelle: 'État', triable: false,
          rendu: (l) => (l.erreur
            ? UI.html`<span class="badge ko">Problème</span> <span class="test-sauvegarde-erreur" data-erreur="${l.table}">${l.erreur}</span>`
            : UI.html`<span class="badge ok">Lisible</span>`) },
      ],
      lignes: tables,
      vide: 'Aucun fichier de données dans cette sauvegarde.',
    }));
    return contenu;
  }

  async function testerSauvegarde(sauvegarde) {
    const resultat = await App.adaptateur.testerSauvegarde(sauvegarde.nom);
    await UI.fenetre({ titre: 'Tester une sauvegarde', contenu: contenuResultat(sauvegarde, resultat) });
  }

  /**
   * Cellule « actions » d'une ligne du tableau des sauvegardes : « Tester » puis « Restaurer… » en mode serveur,
   * « Restaurer… » seul ailleurs. `pendant(bouton, contexte, action)` : outil de parametres.js.
   */
  function actionsSauvegarde(sauvegarde, boutonRestaurer, pendant) {
    if (!serveurSaitTester()) return boutonRestaurer;
    const bouton = UI.element(UI.html`<button type="button" class="btn btn-secondaire" data-tester="${sauvegarde.nom}">Tester</button>`);
    bouton.addEventListener('click', () => pendant(bouton, 'test d\'une sauvegarde', () => testerSauvegarde(sauvegarde)));
    const groupe = UI.element(UI.html`<span class="sauvegarde-actions"></span>`);
    groupe.append(bouton, boutonRestaurer);
    return groupe;
  }

  /** Note de la carte « Sauvegardes » propre au PC serveur (fragment UI.html ; '' hors du mode serveur). */
  function noteSauvegardes() {
    if (!serveurSaitTester()) return '';
    return UI.html`<p class="note sauvegardes-explication" id="note-sauvegardes-serveur">« Tester » relit une sauvegarde
      et compte les lignes de chaque table, sans rien modifier. Une sauvegarde manuelle par minute au plus ; Prévo garde
      les 60 dernières (les quotidiennes et les copies de sécurité ne sont pas comptées).</p>`;
  }

  return { actionsSauvegarde, noteSauvegardes };
})());
