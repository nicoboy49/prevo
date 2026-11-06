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
  // Libellé (badge), filtre (bouton) et résumé (« 3 à créer ») : lus à l'affichage, jamais figés au chargement.
  const ACTIONS = {
    creer: { get libelle() { return I18n.t('import.action.creer'); }, get filtre() { return I18n.t('import.filtre.creer'); }, ton: 'ok', resume: (n) => I18n.t('import.resume.creer', { n }) },
    mettre_a_jour: { get libelle() { return I18n.t('import.action.mettre_a_jour'); }, get filtre() { return I18n.t('import.filtre.mettre_a_jour'); }, ton: 'info', resume: (n) => I18n.t('import.resume.mettre_a_jour', { n }) },
    identique: { get libelle() { return I18n.t('import.action.identique'); }, get filtre() { return I18n.t('import.filtre.identique'); }, ton: 'neutre', resume: (n) => I18n.t('import.resume.identique', { n }) },
    refusee: { get libelle() { return I18n.t('import.action.refusee'); }, get filtre() { return I18n.t('import.filtre.refusee'); }, ton: 'ko', resume: (n) => I18n.t('import.resume.refusee', { n }) },
    doublon_sur: { get libelle() { return I18n.t('import.action.doublon_sur'); }, get filtre() { return I18n.t('import.filtre.doublon_sur'); }, ton: 'violet', resume: (n) => I18n.t('import.resume.doublon_sur', { n }) },
    doublon_suppose: { get libelle() { return I18n.t('import.action.doublon_suppose'); }, get filtre() { return I18n.t('import.filtre.doublon_suppose'); }, ton: 'attention', resume: (n) => I18n.t('import.resume.doublon_suppose', { n }) },
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
  // Nature d'une référence créée par l'import (lue à l'affichage).
  const REFERENCES = { get localisations() { return I18n.t('import.reference.localisation'); }, get fournisseurs() { return I18n.t('import.reference.fournisseur'); } };
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
    console.warn('Prévo (import) : ' + (contexte === 'apercu' ? 'aperçu' : contexte) + ' impossible (' + (erreur && erreur.message) + ').', erreur);
    const raison = App.raisonErreur(erreur);
    return contexte === 'apercu' ? I18n.t('import.erreur.apercu_impossible', { raison }) : I18n.t('import.erreur.import_impossible', { raison });
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
      return { ok: false, message: messageErreur(erreur, 'apercu') };
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
    const element = A.section(4, I18n.t('import.etape_apercu.apercu_prevo_va_faire'), I18n.t('import.etape_apercu.rien_encore_ecrit_verifiez'));
    element.appendChild(UI.element(UI.html`<div class="alertes" id="import-message-apercu"></div>`));
    if (historique) {
      element.appendChild(UI.element(UI.html`<p class="note import-option">${I18n.t('import.etape_apercu.chaque_intervention_acceptee_devient')}</p>`));
    } else {
      element.appendChild(UI.element(UI.html`<div class="import-option">
        <label class="case"><input type="checkbox" id="import-mettre-a-jour"${etat.mettreAJour ? UI.brut(' checked') : ''}>
          <span>${I18n.t('import.etape_apercu.completer_mettre_jour_fiches')}</span></label>
        <p class="aide">${I18n.t('import.etape_apercu.seules_colonnes_importees_remplies')}</p>
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
    const morceaux = actions.filter((action) => totaux[action]).map((action) => ACTIONS[action].resume(totaux[action]));
    const lues = I18n.t('import.resume.lignes_lues', { n: totaux.lignes });
    return morceaux.length ? I18n.t('import.resume.lues_detail', { lues, detail: morceaux.join(', ') }) : I18n.t('import.resume.lues', { lues });
  }

  function references(apercu) {
    const liste = apercu.referencesCreees || [];
    if (!liste.length) return '';
    return UI.html`<div class="encadre info" id="import-references">
      <b>${I18n.t('import.references.creees_aussi', { n: liste.length })}</b>
      <ul>${liste.map((reference) => UI.html`<li>${I18n.html('import.references.reference', { nature: REFERENCES[reference.table] || libelleTable(reference.table),
        libelle: reference.libelle, id: reference.id })}</li>`)}</ul>
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
    const filtres = [{ cle: 'tout', libelle: I18n.t('import.filtre.tout'), total: apercu.totaux.lignes, attribut: 'lignes' }]
      .concat(actions.map((action) => ({ cle: action, libelle: ACTIONS[action].filtre, total: apercu.totaux[action] || 0, attribut: action })));
    const refusees = apercu.totaux.refusee || 0;
    const filtrees = lignesFiltrees();
    const affichees = filtrees.slice(0, etat.limite);
    UI.remplir(zone, UI.html`
      <p class="import-resume" id="import-resume">${resume(apercu, actions)}</p>
      ${references(apercu)}
      <div class="import-barre">
        <div class="import-filtres" role="group" aria-label="${I18n.t('import.rendre_resultats.afficher_lignes')}">
          ${filtres.map((filtre) => UI.html`<button type="button" class="btn btn-secondaire import-filtre" data-filtre="${filtre.cle}"
            aria-pressed="${etat.filtre === filtre.cle ? 'true' : 'false'}"><span>${filtre.libelle} (<span data-total="${filtre.attribut}">${filtre.total}</span>)</span></button>`)}
        </div>
        ${refusees ? UI.html`<button type="button" class="btn btn-secondaire" id="import-refus">${UI.icone('export')}${I18n.t('import.rendre_resultats.telecharger_lignes_refusees', { refusees })}</button>` : ''}
      </div>
      <div class="import-cadre" tabindex="0" role="region" aria-label="${I18n.t('import.rendre_resultats.lignes_fichier')}">
        <table class="table import-lignes">
          <caption class="visuellement-cache">${I18n.t('import.rendre_resultats.prevo_fera_chaque_ligne')}</caption>
          <thead><tr><th scope="col" class="num">${I18n.t('import.rendre_resultats.ligne')}</th><th scope="col">${I18n.t('import.rendre_resultats.action')}</th><th scope="col">${I18n.t('import.rendre_resultats.fiche')}</th><th scope="col">${I18n.t('import.rendre_resultats.detail')}</th></tr></thead>
          <tbody>${affichees.length ? affichees.map(ligneApercu)
            : UI.html`<tr><td colspan="4" class="vide-table">${I18n.t('import.rendre_resultats.aucune_ligne_filtre')}</td></tr>`}</tbody>
        </table>
      </div>
      ${filtrees.length > affichees.length ? UI.html`<div class="actions"><button type="button" class="btn btn-secondaire" id="import-plus">
        ${I18n.t('import.rendre_resultats.afficher_lignes_plus', { n: Math.min(PAS_AFFICHAGE, filtrees.length - affichees.length), reste: filtrees.length - affichees.length })}</button></div>` : ''}`);
    if (aFocaliser) {
      const cible = UI.$(aFocaliser, zone);
      if (cible) cible.focus();
    }
  }

  function fiche(ligne) {
    const etat = A.etat();
    // Famille d'un code : valeur stockée de la liste, affichée par son libellé (D155).
    const valeurs = (FICHE[etat.type] || []).map((cle) => (etat.type === 'codes' && cle === 'famille'
      ? Schema.libelleValeur('codes_defaillance', 'famille', texte(ligne.valeurs && ligne.valeurs.famille)) : texte(ligne.valeurs && ligne.valeurs[cle]))).filter(Boolean)
      .map((valeur) => (valeur.length > 60 ? I18n.t('import.texte_coupe', { debut: valeur.slice(0, 59) }) : valeur));
    const cible = ligne.cible && !ligne.doublon && ligne.action !== 'refusee' ? ligne.cible : '';
    return UI.html`${valeurs.length ? UI.html`<b>${valeurs[0]}</b>${valeurs.slice(1).map((v) => UI.html`<span class="import-fiche-suite">${v}</span>`)}` : '—'}
      ${cible ? UI.html`<small class="import-cible">${cible}</small>` : ''}`;
  }

  function detail(ligne) {
    const etat = A.etat();
    const morceaux = [];
    if (ligne.changements && ligne.changements.length) {
      morceaux.push(UI.html`<ul class="import-changements">${ligne.changements.map((c) => UI.html`<li><span class="import-champ-nom">${c.libelle || c.champ}</span> :
        <span class="import-avant">${texte(c.avant) || I18n.t('import.detail.vide')}</span> → <b class="import-apres">${texte(c.apres) || I18n.t('import.detail.vide')}</b></li>`)}</ul>`);
    }
    if (ligne.doublon) {
      morceaux.push(UI.html`<p class="import-doublon">${ligne.doublon.ligne
        ? (ligne.doublon.ot ? I18n.t('import.detail.meme_intervention_ligne_ot', { ligne: ligne.doublon.ligne, ot: ligne.doublon.ot })
          : I18n.t('import.detail.meme_intervention_ligne_fichier', { ligne: ligne.doublon.ligne }))
        : UI.html`${I18n.t('import.detail.meme_intervention_ot_deja', { ot: ligne.doublon.ot })}`}</p>`);
    }
    if (ligne.raisons && ligne.raisons.length) {
      morceaux.push(UI.html`<ul class="import-raisons${ligne.action === 'refusee' ? ' import-refus' : ''}">${ligne.raisons.map((r) => UI.html`<li>${r}</li>`)}</ul>`);
    }
    if (!morceaux.length) morceaux.push(UI.html`<span class="import-rien">${ligne.action === 'identique' ? I18n.t('import.detail.aucun_changement') : '—'}</span>`);
    if (ligne.action === 'doublon_suppose' || (ligne.doublon && etat.quandMeme.has(ligne.numero))) {
      morceaux.push(UI.html`<label class="case import-case-quand-meme"><input type="checkbox" class="import-quand-meme" data-numero="${ligne.numero}"${etat.quandMeme.has(ligne.numero) ? UI.brut(' checked') : ''}>
        <span>${I18n.t('import.detail.importer_quand_meme')}</span></label>`);
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
    const element = A.section(5, I18n.t('import.etape_importer.importer'), tables.length ? I18n.t('import.etape_importer.derniere_etape_seulement_ici') : '');
    element.appendChild(UI.element(UI.html`<div class="import-bilan" id="import-bilan">${bilan(etat.apercu, tables)}</div>`));
    element.appendChild(UI.element(UI.html`<div class="import-progression" id="import-progression" hidden></div>`));
    element.appendChild(UI.element(UI.html`<div class="import-resultat" id="import-resultat" aria-live="polite"></div>`));
    const bouton = UI.element(UI.html`<button type="button" class="btn btn-primaire" id="import-importer">${UI.icone('valider')}${I18n.t('import.etape_importer.importer')}</button>`);
    bouton.disabled = !tables.length;
    bouton.addEventListener('click', () => importer(bouton));
    element.appendChild(A.navigation({ retour: 4, boutons: [bouton] }));
    zone.appendChild(element);
    if (etat.resultat) afficherResultat();
  }

  function bilan(apercu, tables) {
    if (!tables.length) {
      return UI.bandeau('attention', UI.html`${I18n.html('import.bilan.rien_importer_aucune_ligne')}`);
    }
    const modeDemo = App.mode === 'demo';
    return UI.html`<p>${I18n.t('import.bilan.cliquant_importer_prevo_ecrit')}</p>
      <ul class="import-tables">${tables.map((nomTable) => {
        const ecritures = apercu.ecritures[nomTable];
        const morceaux = [];
        if (ecritures.creer.length) morceaux.push(I18n.t('import.bilan.creations', { n: ecritures.creer.length }));
        if (ecritures.modifier.length) morceaux.push(I18n.t('import.bilan.mises_a_jour', { n: ecritures.modifier.length }));
        return UI.html`<li><b>${libelleTable(nomTable)}</b> : ${morceaux.join(', ')}</li>`;
      })}</ul>
      <p class="note">${modeDemo
        ? I18n.t('import.bilan.demo_rien_ecrit_disque')
        : I18n.t('import.bilan.juste_avant_prevo_fait')}
        ${I18n.t('import.bilan.chaque_fiche_ecrite_notee')}</p>`;
  }

  // Progression : une table de plus à chaque écriture locale (Donnees signale chaque table écrite).
  function suivreProgression(tables) {
    const zone = zoneDe('#import-progression');
    const ecrites = new Set();
    zone.hidden = false;
    UI.remplir(zone, UI.html`<p class="import-etat-progression" role="status">${App.mode === 'demo' ? I18n.t('import.suivre_progression.preparation') : I18n.t('import.suivre_progression.sauvegarde_avant_import')}</p>
      <progress max="${tables.length}" value="0" aria-label="${I18n.t('import.suivre_progression.tables_ecrites')}"></progress>`);
    const etatProgression = UI.$('.import-etat-progression', zone);
    const barre = UI.$('progress', zone);
    const ecouter = (evenement) => {
      const detail = evenement.detail || {};
      if (detail.origine !== 'local') return;
      (detail.tables || []).forEach((nomTable) => {
        if (!tables.includes(nomTable) || ecrites.has(nomTable)) return;
        ecrites.add(nomTable);
        barre.value = ecrites.size;
        etatProgression.textContent = I18n.t('import.suivre_progression.ecriture_libelle_table_ecrites_size_nb_tables', { libelleTable: libelleTable(nomTable), ecritesSize: ecrites.size, nbTables: tables.length });
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
      progression.finir({ complet: true, texte: I18n.t('import.importer.import_termine_tables', { n: resultat.tablesTouchees.length }) });
      await tracerIa(resultat);
      afficherResultat();
      UI.toast(I18n.t('import.importer.import_termine'), 'succes');
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
        progression.finir({ complet: false, texte: I18n.t('import.importer.import_arrete_cours_route') });
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
    if (message) zone.appendChild(UI.bandeau('important', UI.html`${I18n.html('import.erreur_import.rien_ete_importe', { message })}`));
  }

  function tableauResultat(resultat) {
    return UI.html`<div class="table-defile"><table class="table import-tableau-resultat">
      <caption class="visuellement-cache">${I18n.t('import.tableau_resultat.fiches_ecrites_table')}</caption>
      <thead><tr><th scope="col">${I18n.t('import.tableau_resultat.table')}</th><th scope="col" class="num">${I18n.t('import.tableau_resultat.creees')}</th><th scope="col" class="num">${I18n.t('import.tableau_resultat.mises_jour')}</th></tr></thead>
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
    const recommencer = UI.html`<button type="button" class="btn btn-secondaire" id="import-recommencer">${UI.icone('ajouter')}${I18n.t('import.resultat.importer_autres_donnees')}</button>`;
    if (etat.annule) {
      UI.remplir(zone, UI.html`${UI.brut(UI.bandeau('succes', I18n.html('import.resultat.import_annule', { n: resultat.tablesTouchees.length, tables })).outerHTML)}
        <div class="actions">${recommencer}</div>`);
    } else {
      const crees = resultat.tablesTouchees.reduce((somme, t) => somme + ((resultat.tables[t] || {}).crees || 0), 0);
      const misAJour = resultat.tablesTouchees.reduce((somme, t) => somme + ((resultat.tables[t] || {}).misAJour || 0), 0);
      const entete = etat.partiel
        ? UI.bandeau('important', I18n.html('import.resultat.import_arrete', { message: etat.partiel,
          tables: Object.keys(resultat.tables).map(libelleTable).join(', ') }))
        : UI.bandeau('succes', I18n.html('import.resultat.import_termine', { creees: I18n.t('import.resultat.fiches_creees', { n: crees }),
          misesAJour: I18n.t('import.resultat.fiches_mises_a_jour', { n: misAJour }) }));
      UI.remplir(zone, UI.html`${UI.brut(entete.outerHTML)}
        ${tableauResultat(resultat)}
        ${resultat.sauvegarde
          ? UI.html`<p class="note">${I18n.html('import.resultat.sauvegarde_faite_juste_avant', { sauvegarde: resultat.sauvegarde })}</p>`
          : UI.html`<p class="note">${I18n.t('import.resultat.demo_etat_avant_import')}</p>`}
        <div class="actions">
          <button type="button" class="btn btn-danger" id="import-annuler">${UI.icone('retour')}${I18n.t('import.resultat.annuler_import')}</button>
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
    const accord = await UI.confirmer(I18n.t('import.annuler.annuler_import_tables_touchees', { tables }),
    { titre: I18n.t('import.resultat.annuler_import'), oui: I18n.t('import.annuler.annuler_import'), non: I18n.t('import.annuler.garder_import'), danger: true });
    if (!accord) return;
    etat.enCours = true;
    bouton.disabled = true;
    bouton.setAttribute('aria-busy', 'true');
    try {
      await Import.annuler(resultat);
      etat.annule = true;
      etat.partiel = '';
      afficherResultat();
      UI.toast(I18n.t('import.annuler.import_annule'), 'succes');
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
