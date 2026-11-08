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

  function libelleTable(nomTable) {
    const description = Schema.table(nomTable);
    return description ? description.libelle : nomTable;
  }

  // Verdict en tête de la fenêtre : lisible (total des lignes), vide, ou tables en erreur.
  function verdict(resultat, tables) {
    const enErreur = tables.filter((table) => table.erreur).length;
    if (resultat.ok) {
      const total = tables.reduce((somme, table) => somme + (Number(table.lignes) || 0), 0);
      return UI.bandeau('succes', UI.html`${I18n.html('sauvegardes.verdict.sauvegarde_lisible_tout', { tables: I18n.t('sauvegardes.verdict.tables_relues', { n: tables.length }), lignes: I18n.t('sauvegardes.verdict.lignes', { n: total }) })}`);
    }
    if (!tables.length) {
      return UI.bandeau('important', UI.html`${I18n.html('sauvegardes.verdict.sauvegarde_vide_contient_aucun')}`);
    }
    return UI.bandeau('important', UI.html`${I18n.html('sauvegardes.verdict.probleme_trouve_relisent_pas', { n: enErreur, nbTables: tables.length })}`);
  }

  function contenuResultat(sauvegarde, resultat) {
    const tables = Array.isArray(resultat.tables) ? resultat.tables : [];
    const decrite = Parametres.decrireSauvegarde(sauvegarde.nom);
    const contenu = UI.element(UI.html`<div class="form-colonne" id="resultat-test-sauvegarde" data-ok="${resultat.ok ? '1' : '0'}">
      <p>${I18n.html('sauvegardes.contenu_resultat.sauvegarde_prevo_relu_chaque', { date: decrite.date, typeEnMinuscule: decrite.type.toLowerCase() })}</p>
    </div>`);
    contenu.appendChild(verdict(resultat, tables));
    contenu.appendChild(UI.tableau({
      libelle: I18n.t('sauvegardes.contenu_resultat.tables_relues'),
      colonnes: [
        { cle: 'table', libelle: I18n.t('sauvegardes.contenu_resultat.table'), valeurTri: (l) => libelleTable(l.table),
          rendu: (l) => UI.html`${I18n.html('sauvegardes.contenu_resultat.libelle_table_table_csv', { libelleTable: libelleTable(l.table), table: l.table })}` },
        { cle: 'lignes', libelle: I18n.t('sauvegardes.contenu_resultat.lignes'), type: 'nombre', valeurTri: (l) => l.lignes,
          rendu: (l) => UI.html`<span data-lignes="${l.table}">${l.lignes === null || l.lignes === undefined ? '—' : String(l.lignes)}</span>` },
        { cle: 'erreur', libelle: I18n.t('sauvegardes.contenu_resultat.etat'), triable: false,
          rendu: (l) => (l.erreur
            ? UI.html`<span class="badge ko">${I18n.t('sauvegardes.contenu_resultat.probleme')}</span> <span class="test-sauvegarde-erreur" data-erreur="${l.table}">${l.erreur}</span>`
            : UI.html`<span class="badge ok">${I18n.t('sauvegardes.contenu_resultat.lisible')}</span>`) },
      ],
      lignes: tables,
      vide: I18n.t('sauvegardes.contenu_resultat.aucun_fichier_donnees_sauvegarde'),
    }));
    return contenu;
  }

  async function testerSauvegarde(sauvegarde) {
    const resultat = await App.adaptateur.testerSauvegarde(sauvegarde.nom);
    await UI.fenetre({ titre: I18n.t('sauvegardes.tester_sauvegarde.tester_sauvegarde'), contenu: contenuResultat(sauvegarde, resultat) });
  }

  /**
   * Cellule « actions » d'une ligne du tableau des sauvegardes : « Tester » puis « Restaurer… » en mode serveur,
   * « Restaurer… » seul ailleurs. `pendant(bouton, contexte, action)` : outil de parametres.js.
   */
  function actionsSauvegarde(sauvegarde, boutonRestaurer, pendant) {
    if (!serveurSaitTester()) return boutonRestaurer;
    const bouton = UI.element(UI.html`<button type="button" class="btn btn-secondaire" data-tester="${sauvegarde.nom}">${I18n.t('sauvegardes.actions_sauvegarde.tester')}</button>`);
    bouton.addEventListener('click', () => pendant(bouton, 'test d\'une sauvegarde', () => testerSauvegarde(sauvegarde)));
    const groupe = UI.element(UI.html`<span class="sauvegarde-actions"></span>`);
    groupe.append(bouton, boutonRestaurer);
    return groupe;
  }

  /** Note de la carte « Sauvegardes » propre au PC serveur (fragment UI.html ; '' hors du mode serveur). */
  function noteSauvegardes() {
    if (!serveurSaitTester()) return '';
    return UI.html`<p class="note sauvegardes-explication" id="note-sauvegardes-serveur">${I18n.t('sauvegardes.note_sauvegardes.tester_relit_sauvegarde_compte')}</p>`;
  }

  return { actionsSauvegarde, noteSauvegardes };
})());
