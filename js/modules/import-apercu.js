'use strict';
// Import (7/7) — étapes 4 « Aperçu » et 5 « Importer » de l'assistant (lot 5, ARCHITECTURE.md §18.9) :
// totaux par action et filtres, tableau défilant dans son cadre (changements avant → après, raisons),
// références créées, doublons supposés avec « Importer quand même » (non cochée), case « Compléter et
// mettre à jour les fiches existantes » (cochée par défaut ; chaque case recalcule l'aperçu), « Télécharger
// les lignes refusées » ; puis l'import (bouton désactivé tant qu'il n'y a rien à faire, progression table par
// table, résultat, sauvegarde), « Annuler cet import » après confirmation, et la trace « proposition IA
// utilisée » au journal quand une colonne proposée par l'IA a été gardée. Complète l'objet Import
// (Import.assistant, posé par import-ecrans.js).
// L'aperçu (Import.preparer) ne fait que lire : seul le bouton « Importer » écrit (Import.importer, avec
// recalculer = le même calcul, mêmes options et même « maintenant »).

Object.assign(Import.assistant, (() => {

  const A = Import.assistant;
  const ACTIONS = {
    creer: { libelle: 'À créer', filtre: 'À créer', ton: 'ok', resume: ['à créer', 'à créer'] },
    mettre_a_jour: { libelle: 'À mettre à jour', filtre: 'À mettre à jour', ton: 'info', resume: ['à mettre à jour', 'à mettre à jour'] },
    identique: { libelle: 'Identique', filtre: 'Identiques', ton: 'neutre', resume: ['identique', 'identiques'] },
    refusee: { libelle: 'Refusée', filtre: 'Refusées', ton: 'ko', resume: ['refusée', 'refusées'] },
    doublon_sur: { libelle: 'Doublon sûr', filtre: 'Doublons sûrs', ton: 'violet', resume: ['doublon sûr (ignoré)', 'doublons sûrs (ignorés)'] },
    doublon_suppose: { libelle: 'Doublon supposé', filtre: 'Doublons supposés', ton: 'attention', resume: ['doublon supposé', 'doublons supposés'] },
  };
  const ACTIONS_REFERENTIELS = ['creer', 'mettre_a_jour', 'identique', 'refusee'];
  const ACTIONS_HISTORIQUE = ['creer', 'refusee', 'doublon_sur', 'doublon_suppose'];
  // Champs qui nomment la fiche d'une ligne dans l'aperçu (le premier en gras).
  const FICHE = {
    localisations: ['chemin'], equipements: ['repere', 'designation'], articles: ['reference', 'designation'],
    fournisseurs: ['nom'], techniciens: ['prenom', 'nom'], habilitations: ['technicien', 'intitule'],
    codes: ['code', 'famille', 'libelle'], compteurs: ['equipement', 'libelle'], controles: ['equipement', 'nature'],
    gammes: ['equipement', 'libelle', 'operations'], historique: ['ancien_numero', 'equipement', 'titre'],
  };
  const REFERENCES = { localisations: 'Localisation', fournisseurs: 'Fournisseur' };
  // Table où la trace « proposition IA utilisée » est écrite : celle de la fiche importée.
  const TABLE_PRINCIPALE = {
    localisations: 'localisations', equipements: 'equipements', articles: 'articles', fournisseurs: 'fournisseurs',
    techniciens: 'techniciens', habilitations: 'habilitations', codes: 'codes_defaillance', compteurs: 'compteurs',
    controles: 'controles_reglementaires', gammes: 'gammes', historique: 'ordres_travail',
  };
  const PAS_AFFICHAGE = 200;

  const texte = (valeur) => (valeur === null || valeur === undefined ? '' : String(valeur).trim());
  const libelleTable = (nomTable) => (Schema.table(nomTable) || { libelle: nomTable }).libelle;
  const zoneDe = (selecteur) => document.querySelector('#contenu ' + selecteur);

  function messageErreur(erreur, contexte) {
    if (erreur instanceof Import.ErreurImport) return erreur.message;
    console.warn('Prévo (import) : ' + contexte + ' impossible (' + (erreur && erreur.message) + ').', erreur);
    return contexte.charAt(0).toUpperCase() + contexte.slice(1) + ' impossible : ' + App.raisonErreur(erreur) + '.';
  }

  // ===========================================================================================
  // 1. Calcul de l'aperçu (à blanc : Import.preparer ne fait que lire)
  // ===========================================================================================

  /** Aperçu de la correspondance validée, avec les cases de l'étape 4 → { ok, message }. */
  function calculerApercu() {
    const etat = A.etat();
    if (!etat.maintenant) etat.maintenant = Donnees.maintenant();
    const calcul = {
      type: etat.type, lignes: A.donnees(), correspondance: A.correspondanceValidee(),
      options: { mettreAJour: etat.mettreAJour, numeroPremiereLigne: A.numeroPremiereLigne(), maintenant: etat.maintenant,
        importerQuandMeme: Array.from(etat.quandMeme) },
    };
    try {
      etat.apercu = Import.preparer(calcul.type, calcul.lignes, calcul.correspondance, calcul.options);
      etat.calcul = calcul;
      return { ok: true };
    } catch (erreur) {
      etat.apercu = null;
      etat.calcul = null;
      return { ok: false, message: messageErreur(erreur, 'aperçu') };
    }
  }

  function tablesAEcrire(apercu) {
    return Import.ORDRE_ECRITURE.filter((nomTable) => {
      const ecritures = apercu && apercu.ecritures ? apercu.ecritures[nomTable] : null;
      return ecritures && ((ecritures.creer || []).length || (ecritures.modifier || []).length);
    });
  }

  // ===========================================================================================
  // 2. Étape 4 — Aperçu
  // ===========================================================================================

  function etapeApercu(zone) {
    const etat = A.etat();
    const calcul = etat.apercu ? { ok: true } : calculerApercu();
    const historique = etat.type === 'historique';
    const element = A.section(4, 'Aperçu : ce que Prévo va faire', 'Rien n\'est encore écrit. Vérifiez ce que deviendra chaque '
      + 'ligne du fichier ; les lignes refusées ne seront pas importées.');
    element.appendChild(UI.element(UI.html`<div class="alertes" id="import-message-apercu"></div>`));
    if (historique) {
      element.appendChild(UI.element(UI.html`<p class="note import-option">Chaque intervention acceptée devient un OT clôturé ;
        un OT déjà dans Prévo n'est jamais modifié. Un doublon supposé n'est importé que si vous cochez « Importer quand même ».</p>`));
    } else {
      element.appendChild(UI.element(UI.html`<div class="import-option">
        <label class="case"><input type="checkbox" id="import-mettre-a-jour"${etat.mettreAJour ? UI.brut(' checked') : ''}>
          <span>Compléter et mettre à jour les fiches existantes</span></label>
        <p class="aide">Seules les colonnes importées et remplies qui changent sont écrites ; une cellule vide n'efface rien.
          Décochée : les fiches déjà dans Prévo ne sont pas touchées, seules les nouvelles sont créées.</p>
      </div>`));
    }
    element.appendChild(UI.element(UI.html`<div class="import-resultats-apercu"></div>`));
    element.appendChild(A.navigation({ retour: 3, continuer: { actif: calcul.ok, action: () => { etat.message = null; A.allerA(5); } } }));
    zone.appendChild(element);

    afficherMessage(calcul.ok ? etat.message : { type: 'important', texte: calcul.message });
    const caseMiseAJour = UI.$('#import-mettre-a-jour', element);
    if (caseMiseAJour) {
      caseMiseAJour.addEventListener('change', () => {
        etat.mettreAJour = caseMiseAJour.checked;
        recalculer();
      });
    }
    const resultats = UI.$('.import-resultats-apercu', element);
    resultats.addEventListener('click', (evenement) => {
      const filtre = evenement.target.closest('.import-filtre');
      if (filtre) {
        etat.filtre = filtre.dataset.filtre;
        etat.limite = PAS_AFFICHAGE;
        rendreResultats('.import-filtre[data-filtre="' + etat.filtre + '"]');
      } else if (evenement.target.closest('#import-plus')) {
        etat.limite += PAS_AFFICHAGE;
        rendreResultats('#import-plus');
      } else if (evenement.target.closest('#import-refus')) {
        telechargerRefus();
      }
    });
    resultats.addEventListener('change', (evenement) => {
      const quandMeme = evenement.target.closest('input.import-quand-meme');
      if (!quandMeme) return;
      const numero = Number(quandMeme.dataset.numero);
      if (quandMeme.checked) etat.quandMeme.add(numero); else etat.quandMeme.delete(numero);
      recalculer('input.import-quand-meme[data-numero="' + numero + '"]');
    });
    if (calcul.ok) rendreResultats();
  }

  function afficherMessage(message) {
    const zone = zoneDe('#import-message-apercu');
    if (!zone) return;
    zone.textContent = '';
    if (message) zone.appendChild(UI.bandeau(message.type, message.texte));
  }

  // Une case a changé : nouvel aperçu (mêmes lignes, même correspondance), puis nouvel affichage.
  function recalculer(aFocaliser) {
    const calcul = calculerApercu();
    const continuer = zoneDe('#import-continuer');
    if (continuer) continuer.disabled = !calcul.ok;
    afficherMessage(calcul.ok ? null : { type: 'important', texte: calcul.message });
    A.etat().message = null;
    if (calcul.ok) rendreResultats(aFocaliser);
  }

  function resume(apercu, actions) {
    const totaux = apercu.totaux;
    const morceaux = actions.filter((action) => totaux[action]).map((action) => {
      const [un, plusieurs] = ACTIONS[action].resume;
      return totaux[action] + ' ' + (totaux[action] > 1 ? plusieurs : un);
    });
    return A.pluriel(totaux.lignes, 'ligne lue', 'lignes lues') + (morceaux.length ? ' : ' + morceaux.join(', ') : '') + '.';
  }

  function references(apercu) {
    const liste = apercu.referencesCreees || [];
    if (!liste.length) return '';
    return UI.html`<div class="encadre info" id="import-references">
      <b>${liste.length > 1 ? 'Créées aussi, car citées par les lignes à importer' : 'Créée aussi, car citée par les lignes à importer'} :</b>
      <ul>${liste.map((reference) => UI.html`<li>${REFERENCES[reference.table] || libelleTable(reference.table)} « ${reference.libelle} »
        <small class="import-cible">${reference.id}</small></li>`)}</ul>
    </div>`;
  }

  function lignesFiltrees() {
    const etat = A.etat();
    const lignes = etat.apercu.lignes;
    if (etat.filtre === 'tout') return lignes;
    if (etat.filtre === 'doublon_suppose') {
      return lignes.filter((ligne) => ligne.action === 'doublon_suppose' || (ligne.doublon && etat.quandMeme.has(ligne.numero)));
    }
    return lignes.filter((ligne) => ligne.action === etat.filtre);
  }

  function rendreResultats(aFocaliser) {
    const zone = zoneDe('.import-resultats-apercu');
    const etat = A.etat();
    if (!zone || !etat.apercu) return;
    const apercu = etat.apercu;
    const actions = etat.type === 'historique' ? ACTIONS_HISTORIQUE : ACTIONS_REFERENTIELS;
    const filtres = [{ cle: 'tout', libelle: 'Toutes', total: apercu.totaux.lignes, attribut: 'lignes' }]
      .concat(actions.map((action) => ({ cle: action, libelle: ACTIONS[action].filtre, total: apercu.totaux[action] || 0, attribut: action })));
    const refusees = apercu.totaux.refusee || 0;
    const filtrees = lignesFiltrees();
    const affichees = filtrees.slice(0, etat.limite);
    UI.remplir(zone, UI.html`
      <p class="import-resume" id="import-resume">${resume(apercu, actions)}</p>
      ${references(apercu)}
      <div class="import-barre">
        <div class="import-filtres" role="group" aria-label="Afficher les lignes">
          ${filtres.map((filtre) => UI.html`<button type="button" class="btn btn-secondaire import-filtre" data-filtre="${filtre.cle}"
            aria-pressed="${etat.filtre === filtre.cle ? 'true' : 'false'}"><span>${filtre.libelle} (<span data-total="${filtre.attribut}">${filtre.total}</span>)</span></button>`)}
        </div>
        ${refusees ? UI.html`<button type="button" class="btn btn-secondaire" id="import-refus">${UI.icone('export')}Télécharger les lignes refusées (${refusees})</button>` : ''}
      </div>
      <div class="import-cadre" tabindex="0" role="region" aria-label="Lignes du fichier">
        <table class="table import-lignes">
          <caption class="visuellement-cache">Ce que Prévo fera de chaque ligne du fichier</caption>
          <thead><tr><th scope="col" class="num">Ligne</th><th scope="col">Action</th><th scope="col">Fiche</th><th scope="col">Détail</th></tr></thead>
          <tbody>${affichees.length ? affichees.map(ligneApercu)
            : UI.html`<tr><td colspan="4" class="vide-table">Aucune ligne pour ce filtre.</td></tr>`}</tbody>
        </table>
      </div>
      ${filtrees.length > affichees.length ? UI.html`<div class="actions"><button type="button" class="btn btn-secondaire" id="import-plus">
        Afficher ${Math.min(PAS_AFFICHAGE, filtrees.length - affichees.length)} lignes de plus (sur ${filtrees.length - affichees.length})</button></div>` : ''}`);
    if (aFocaliser) {
      const cible = UI.$(aFocaliser, zone);
      if (cible) cible.focus();
    }
  }

  function fiche(ligne) {
    const etat = A.etat();
    const valeurs = (FICHE[etat.type] || []).map((cle) => texte(ligne.valeurs && ligne.valeurs[cle])).filter(Boolean)
      .map((valeur) => (valeur.length > 60 ? valeur.slice(0, 59) + '…' : valeur));
    const cible = ligne.cible && !ligne.doublon && ligne.action !== 'refusee' ? ligne.cible : '';
    return UI.html`${valeurs.length ? UI.html`<b>${valeurs[0]}</b>${valeurs.slice(1).map((v) => UI.html`<span class="import-fiche-suite">${v}</span>`)}` : '—'}
      ${cible ? UI.html`<small class="import-cible">${cible}</small>` : ''}`;
  }

  function detail(ligne) {
    const etat = A.etat();
    const morceaux = [];
    if (ligne.changements && ligne.changements.length) {
      morceaux.push(UI.html`<ul class="import-changements">${ligne.changements.map((c) => UI.html`<li><span class="import-champ-nom">${c.libelle || c.champ}</span> :
        <span class="import-avant">${texte(c.avant) || '(vide)'}</span> → <b class="import-apres">${texte(c.apres) || '(vide)'}</b></li>`)}</ul>`);
    }
    if (ligne.doublon) {
      morceaux.push(UI.html`<p class="import-doublon">${ligne.doublon.ligne
        ? UI.html`Même intervention que la ligne ${ligne.doublon.ligne} du fichier${ligne.doublon.ot ? UI.html` (${ligne.doublon.ot})` : ''}.`
        : UI.html`Même intervention que l'OT ${ligne.doublon.ot} déjà dans Prévo.`}</p>`);
    }
    if (ligne.raisons && ligne.raisons.length) {
      morceaux.push(UI.html`<ul class="import-raisons${ligne.action === 'refusee' ? ' import-refus' : ''}">${ligne.raisons.map((r) => UI.html`<li>${r}</li>`)}</ul>`);
    }
    if (!morceaux.length) morceaux.push(UI.html`<span class="import-rien">${ligne.action === 'identique' ? 'Aucun changement.' : '—'}</span>`);
    if (ligne.action === 'doublon_suppose' || (ligne.doublon && etat.quandMeme.has(ligne.numero))) {
      morceaux.push(UI.html`<label class="case import-case-quand-meme"><input type="checkbox" class="import-quand-meme" data-numero="${ligne.numero}"${etat.quandMeme.has(ligne.numero) ? UI.brut(' checked') : ''}>
        <span>Importer quand même</span></label>`);
    }
    return morceaux;
  }

  function ligneApercu(ligne) {
    const action = ACTIONS[ligne.action] || { libelle: ligne.action, ton: 'neutre' };
    return UI.html`<tr data-numero="${ligne.numero}" data-action="${ligne.action}" class="import-${ligne.action}">
      <td class="num">${ligne.numero}</td>
      <td><span class="badge ${action.ton}">${action.libelle}</span></td>
      <td class="import-fiche">${fiche(ligne)}</td>
      <td class="import-detail">${detail(ligne)}</td>
    </tr>`;
  }

  /** Lignes refusées : CSV au format de Prévo (colonne « Raison » en tête), à corriger puis réimporter. */
  function telechargerRefus() {
    const etat = A.etat();
    if (!etat.apercu || !etat.calcul) return;
    const base = texte(etat.lecture && etat.lecture.nom).replace(/\.[^.]*$/, '').normalize('NFD').replace(/\p{M}+/gu, '')
      .replace(/[^A-Za-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '').toLowerCase() || 'import';
    UI.telecharger('lignes-refusees-' + base + '.csv', Import.rapportRefus(etat.apercu, etat.calcul.lignes, A.entetes()),
      'text/csv;charset=utf-8');
  }

  // ===========================================================================================
  // 3. Étape 5 — Importer, résultat, annulation
  // ===========================================================================================

  function etapeImporter(zone) {
    const etat = A.etat();
    const tables = tablesAEcrire(etat.apercu);
    const element = A.section(5, 'Importer', tables.length ? 'Dernière étape : c\'est seulement ici que Prévo écrit.' : '');
    element.appendChild(UI.element(UI.html`<div class="import-bilan" id="import-bilan">${bilan(etat.apercu, tables)}</div>`));
    element.appendChild(UI.element(UI.html`<div class="import-progression" id="import-progression" hidden></div>`));
    element.appendChild(UI.element(UI.html`<div class="import-resultat" id="import-resultat" aria-live="polite"></div>`));
    const bouton = UI.element(UI.html`<button type="button" class="btn btn-primaire" id="import-importer">${UI.icone('valider')}Importer</button>`);
    bouton.disabled = !tables.length;
    bouton.addEventListener('click', () => importer(bouton));
    element.appendChild(A.navigation({ retour: 4, boutons: [bouton] }));
    zone.appendChild(element);
    if (etat.resultat) afficherResultat();
  }

  function bilan(apercu, tables) {
    if (!tables.length) {
      return UI.bandeau('attention', UI.html`<b>Rien à importer :</b> aucune ligne à créer ni à mettre à jour. Revenez à l'aperçu
        (lignes refusées, case « Compléter et mettre à jour les fiches existantes ») ou à la correspondance des colonnes.`);
    }
    const modeDemo = App.mode === 'demo';
    return UI.html`<p>En cliquant sur « Importer », Prévo écrit :</p>
      <ul class="import-tables">${tables.map((nomTable) => {
        const ecritures = apercu.ecritures[nomTable];
        const morceaux = [];
        if (ecritures.creer.length) morceaux.push(A.pluriel(ecritures.creer.length, 'création'));
        if (ecritures.modifier.length) morceaux.push(A.pluriel(ecritures.modifier.length, 'mise à jour', 'mises à jour'));
        return UI.html`<li><b>${libelleTable(nomTable)}</b> : ${morceaux.join(', ')}</li>`;
      })}</ul>
      <p class="note">${modeDemo
        ? 'Démo : rien n\'est écrit sur un disque. L\'état d\'avant l\'import est gardé en mémoire : « Annuler cet import » le rétablit.'
        : 'Juste avant, Prévo fait une sauvegarde « Avant import » : « Annuler cet import » rend les tables touchées dans leur état d\'avant.'}
        Chaque fiche écrite est notée au journal.</p>`;
  }

  // Progression : une table de plus à chaque écriture locale (Donnees signale chaque table écrite).
  function suivreProgression(tables) {
    const zone = zoneDe('#import-progression');
    const ecrites = new Set();
    zone.hidden = false;
    UI.remplir(zone, UI.html`<p class="import-etat-progression" role="status">${App.mode === 'demo' ? 'Préparation…' : 'Sauvegarde avant l\'import…'}</p>
      <progress max="${tables.length}" value="0" aria-label="Tables écrites"></progress>`);
    const etatProgression = UI.$('.import-etat-progression', zone);
    const barre = UI.$('progress', zone);
    const ecouter = (evenement) => {
      const detail = evenement.detail || {};
      if (detail.origine !== 'local') return;
      (detail.tables || []).forEach((nomTable) => {
        if (!tables.includes(nomTable) || ecrites.has(nomTable)) return;
        ecrites.add(nomTable);
        barre.value = ecrites.size;
        etatProgression.textContent = 'Écriture : ' + libelleTable(nomTable) + ' (' + ecrites.size + ' sur ' + tables.length + ')…';
      });
    };
    Donnees.evenements.addEventListener('changement', ecouter);
    return {
      finir(message) {
        Donnees.evenements.removeEventListener('changement', ecouter);
        if (message) {
          barre.value = message.complet ? tables.length : ecrites.size;
          etatProgression.textContent = message.texte;
        }
      },
      cacher() { zone.hidden = true; },
    };
  }

  async function importer(bouton) {
    const etat = A.etat();
    if (etat.enCours || !etat.calcul || !etat.apercu) return;
    const tables = tablesAEcrire(etat.apercu);
    if (!tables.length) return;
    etat.enCours = true;
    const retour = zoneDe('#import-retour');
    bouton.disabled = true;
    bouton.setAttribute('aria-busy', 'true');
    if (retour) retour.disabled = true;
    afficherErreurImport('');
    const progression = suivreProgression(tables);
    const calcul = etat.calcul;
    try {
      const resultat = await Import.importer(etat.apercu, { nomFichier: texte(etat.lecture && etat.lecture.nom),
        recalculer: () => Import.preparer(calcul.type, calcul.lignes, calcul.correspondance, calcul.options) });
      etat.resultat = resultat;
      progression.finir({ complet: true, texte: 'Import terminé : ' + A.pluriel(resultat.tablesTouchees.length, 'table écrite', 'tables écrites') + '.' });
      await tracerIa(resultat);
      afficherResultat();
      UI.toast('Import terminé.', 'succes');
    } catch (erreur) {
      progression.finir(null);
      bouton.removeAttribute('aria-busy');
      if (erreur && erreur.perime && erreur.apercu) {
        // Un autre poste a écrit entre-temps : nouvel aperçu, à vérifier avant de relancer.
        progression.cacher();
        etat.apercu = erreur.apercu;
        etat.message = { type: 'attention', texte: erreur.message };
        etat.enCours = false;
        A.allerA(4);
        return;
      }
      // Une table qui échoue n'est pas écrite (Donnees.modifier) : « partiel » seulement si une table l'a été.
      if (erreur && erreur.resultatPartiel && Object.keys(erreur.resultatPartiel.tables || {}).length) {
        progression.finir({ complet: false, texte: 'Import arrêté en cours de route.' });
        etat.resultat = erreur.resultatPartiel;
        etat.partiel = messageErreur(erreur, 'import');
        afficherResultat();
      } else {
        progression.cacher();
        afficherErreurImport(messageErreur(erreur, 'import'));
        bouton.disabled = false;
        if (retour) retour.disabled = false;
      }
    } finally {
      etat.enCours = false;
    }
  }

  /** Trace « proposition IA utilisée » quand une colonne proposée par l'IA a servi (après l'import réussi). */
  async function tracerIa(resultat) {
    const etat = A.etat();
    const colonnes = A.colonnesIa();
    if (!colonnes.length) return;
    const description = Import.TYPES[etat.type];
    const libelle = (cle) => (description.champs.find((champ) => champ.cle === cle) || { libelle: cle }).libelle;
    const table = TABLE_PRINCIPALE[etat.type] || resultat.tablesTouchees[0];
    await Donnees.journaliser(table, '', 'proposition IA utilisée (' + (etat.modeleIa || 'IA') + ') : colonnes de l\'import '
      + resultat.nomFichier + ' (' + colonnes.map((c) => '« ' + c.entete + ' » → ' + libelle(c.champ)).join(', ') + ')');
  }

  function afficherErreurImport(message) {
    const zone = zoneDe('#import-resultat');
    if (!zone) return;
    zone.textContent = '';
    if (message) zone.appendChild(UI.bandeau('important', UI.html`<b>Rien n'a été importé.</b> ${message}`));
  }

  function tableauResultat(resultat) {
    return UI.html`<div class="table-defile"><table class="table import-tableau-resultat">
      <caption class="visuellement-cache">Fiches écrites par table</caption>
      <thead><tr><th scope="col">Table</th><th scope="col" class="num">Créées</th><th scope="col" class="num">Mises à jour</th></tr></thead>
      <tbody>${resultat.tablesTouchees.map((nomTable) => {
        const bilanTable = resultat.tables[nomTable] || { crees: 0, misAJour: 0 };
        return UI.html`<tr data-table="${nomTable}"><td>${libelleTable(nomTable)}</td><td class="num import-crees">${bilanTable.crees}</td>
          <td class="num import-mis-a-jour">${bilanTable.misAJour}</td></tr>`;
      })}</tbody>
    </table></div>`;
  }

  function afficherResultat() {
    const etat = A.etat();
    const zone = zoneDe('#import-resultat');
    const resultat = etat.resultat;
    if (!zone || !resultat) return;
    const importer = zoneDe('#import-importer');
    const retour = zoneDe('#import-retour');
    if (importer) importer.hidden = true;
    if (retour) retour.hidden = true;
    UI.$$('#contenu #import-bilan, #contenu #import-etape-5 .import-intro').forEach((element) => { element.hidden = true; });
    const tables = resultat.tablesTouchees.map(libelleTable).join(', ');
    const recommencer = UI.html`<button type="button" class="btn btn-secondaire" id="import-recommencer">${UI.icone('ajouter')}Importer d'autres données</button>`;
    if (etat.annule) {
      UI.remplir(zone, UI.html`${UI.brut(UI.bandeau('succes', UI.html`<b>Import annulé :</b> ${tables} ${resultat.tablesTouchees.length > 1 ? 'sont revenues' : 'est revenue'}
        à l'état d'avant l'import.`).outerHTML)}
        <div class="actions">${recommencer}</div>`);
    } else {
      const crees = resultat.tablesTouchees.reduce((somme, t) => somme + ((resultat.tables[t] || {}).crees || 0), 0);
      const misAJour = resultat.tablesTouchees.reduce((somme, t) => somme + ((resultat.tables[t] || {}).misAJour || 0), 0);
      const entete = etat.partiel
        ? UI.bandeau('important', UI.html`<b>L'import s'est arrêté en cours de route :</b> ${etat.partiel}
          Des fiches ont déjà été écrites (${Object.keys(resultat.tables).map(libelleTable).join(', ')}) : annulez cet import
          pour revenir à l'état d'avant, puis recommencez.`)
        : UI.bandeau('succes', UI.html`<b>Import terminé :</b> ${A.pluriel(crees, 'fiche créée', 'fiches créées')},
          ${A.pluriel(misAJour, 'fiche mise à jour', 'fiches mises à jour')}.`);
      UI.remplir(zone, UI.html`${UI.brut(entete.outerHTML)}
        ${tableauResultat(resultat)}
        ${resultat.sauvegarde
          ? UI.html`<p class="note">Sauvegarde faite juste avant l'import : <b id="import-sauvegarde">${resultat.sauvegarde}</b>
            (Paramètres, « Sauvegardes », type « Avant import »).</p>`
          : UI.html`<p class="note">Démo : l'état d'avant l'import est gardé en mémoire tant que cette page reste ouverte.</p>`}
        <div class="actions">
          <button type="button" class="btn btn-danger" id="import-annuler">${UI.icone('retour')}Annuler cet import</button>
          ${etat.partiel ? '' : recommencer}
        </div>`);
      UI.$('#import-annuler', zone).addEventListener('click', (evenement) => annuler(evenement.currentTarget));
    }
    const boutonRecommencer = UI.$('#import-recommencer', zone);
    if (boutonRecommencer) boutonRecommencer.addEventListener('click', () => A.recommencer());
  }

  async function annuler(bouton) {
    const etat = A.etat();
    const resultat = etat.resultat;
    if (!resultat || etat.enCours) return;
    const tables = resultat.tablesTouchees.map(libelleTable).join(', ');
    const accord = await UI.confirmer('Annuler cet import ? Les tables touchées (' + tables + ') reviennent à leur état d\'avant '
      + 'l\'import : les modifications faites depuis l\'import, sur ces tables, seront perdues.',
    { titre: 'Annuler cet import', oui: 'Annuler l\'import', non: 'Garder l\'import', danger: true });
    if (!accord) return;
    etat.enCours = true;
    bouton.disabled = true;
    bouton.setAttribute('aria-busy', 'true');
    try {
      await Import.annuler(resultat);
      etat.annule = true;
      etat.partiel = '';
      afficherResultat();
      UI.toast('Import annulé.', 'succes');
    } catch (erreur) {
      App.signalerErreur(erreur, 'annulation de l\'import');
      bouton.disabled = false;
      bouton.removeAttribute('aria-busy');
    } finally {
      etat.enCours = false;
    }
  }

  return { calculerApercu, etapes: Object.assign(A.etapes, { 4: etapeApercu, 5: etapeImporter }) };
})());
