'use strict';
// Ordres (5/7) — contenu des onglets de la fiche OT (ARCHITECTURE.md §14.2 et §14.6) : Préparation
// (causes fréquentes, travail, technicien et RG8, opérations, pièces prévues et stock RG3),
// Exécution (check-list, déroulement, temps passés, pièces sorties de ordres-pieces.js), Compte
// rendu (causes fréquentes, codes, compte rendu, astuce du lot 6, assistant IA du lot 4, clôture
// technique RG4, coût RG7) et Historique de l'équipement. Complète l'objet Ordres ; la fiche
// (ordres-fiche.js) appelle ces onglets par Ordres.interne.

Object.assign(Ordres, (() => {

  // Constantes, outils, règles et écritures des fichiers précédents (ordres-regles.js à ordres-fiche.js).
  const { estVerrouille, verifierHabilitation, piecesManquantes, cout, nomTechnicien } = Ordres;
  const { texte, nombre, arrondi, aujourdhui, estResponsable, estTechnicien, monTechnicienId, equipementDe,
    listeTechniciens, libelleArticle, listeCodes, lignesDeLOt, operationsDe, placerChamp, champOt,
    modifierOt, modifierLieeAOt, journaliserHabilitation, optionsHtml, boutonsTransitions,
    declarerFormulaire, apresEnregistrement, pendant, listeErreursHtml, bandeauHabilitation, enteteOnglet,
    lienOt, detailManque } = Ordres.interne;

  // Fonction du fichier chargé APRÈS celui-ci (ordres-pieces.js) : cherchée au moment de l'appel.
  const afficherPiecesSorties = (bloc, ot) => Ordres.interne.afficherPiecesSorties(bloc, ot);
  // Champ « Astuce pour la prochaine fois » (lot 6, §20.9) : aide mot pour mot ; longueur au plus = seuil astuceMax (§20.1).
  const aideAstuce = () => I18n.t('ordres.aide_astuce.aurait_fait_gagner_temps');
  const ASTUCE_MAX = 500;

  /**
   * Encart « Causes fréquentes ici » (D25, ARCHITECTURE.md §14.5) pour l'équipement et le code
   * symptôme enregistré de l'OT, placé dans `zone` ; la zone est retirée s'il n'y a rien à montrer.
   */
  function placerCausesFrequentes(zone, ot) {
    const encart = typeof CausesFrequentes === 'undefined' ? null : CausesFrequentes.encart(ot.equipement_id, ot.symptome_code);
    if (encart) zone.appendChild(encart);
    else zone.remove();
  }

  // ===========================================================================================
  // 7. Onglet Préparation (responsable) : travail, technicien (RG8), opérations, pièces (RG3)
  // ===========================================================================================

  function peutPreparer(ot) {
    return estResponsable() && !estVerrouille(ot) && ot.statut !== 'Clôturé techniquement';
  }

  function afficherPreparation(panneau, ot) {
    const modifiable = peutPreparer(ot);
    const boutonsPreparation = boutonsTransitions(ot, ['Préparé', 'Planifié']);
    UI.remplir(panneau, UI.html`
      <div class="ot-causes"></div>
      <form class="carte" id="form-preparation" novalidate>
        ${enteteOnglet(I18n.t('ordres.preparation.preparation'), modifiable ? '' : I18n.t('ordres.preparation.lecture_seule'))}
        <fieldset class="ot-fieldset form-grille"${modifiable ? '' : UI.brut(' disabled')}>
          <div class="large" data-place="travail_a_faire"></div>
          <div class="large" data-place="consignes"></div>
          <div data-place="technicien_id"></div><div data-place="date_prevue"></div>
          <div data-place="temps_prevu_h"></div>
          <div class="large ot-zone-habilitation"></div>
        </fieldset>
        ${modifiable ? UI.html`<div class="actions"><span class="espace"></span><button type="submit" class="btn btn-secondaire">${UI.icone('valider')}${I18n.t('ordres.preparation.enregistrer_preparation')}</button></div>` : ''}
      </form>
      <div class="carte" id="ot-bloc-operations"></div>
      <div class="carte" id="ot-bloc-pieces"></div>
      ${modifiable && boutonsPreparation.length ? UI.html`<div class="carte ot-actions-preparation sans-impression">
        <p class="aide">${I18n.t('ordres.preparation.saisies_non_enregistrees_onglet')}</p>
        <div class="actions">${boutonsPreparation}</div></div>` : ''}`);

    const formulaire = UI.$('#form-preparation', panneau);
    const placer = (nom, element) => placerChamp(formulaire, nom, element);
    placer('travail_a_faire', champOt('travail_a_faire', ot.travail_a_faire));
    placer('consignes', champOt('consignes', ot.consignes));
    placer('technicien_id', champOt('technicien_id', ot.technicien_id, { liste: listeTechniciens(ot.technicien_id) }));
    placer('date_prevue', champOt('date_prevue', ot.date_prevue));
    placer('temps_prevu_h', champOt('temps_prevu_h', ot.temps_prevu_h));
    const montrerHabilitation = () => {
      const valeurs = UI.lireFormulaire(formulaire);
      const zone = UI.$('.ot-zone-habilitation', formulaire);
      zone.textContent = '';
      if (verifierHabilitation(ot.equipement_id, valeurs.technicien_id, valeurs.date_prevue)) {
        zone.appendChild(bandeauHabilitation(ot.equipement_id, valeurs.technicien_id, valeurs.date_prevue));
      }
    };
    montrerHabilitation();
    formulaire.addEventListener('change', montrerHabilitation);
    if (modifiable) {
      const enregistrer = () => enregistrerPreparation(ot, formulaire);
      declarerFormulaire(formulaire, enregistrer);
      formulaire.addEventListener('submit', async (evenement) => {
        evenement.preventDefault();
        const resultat = await enregistrer();
        if (!resultat) return;
        formulaire.dataset.modifie = '0';
        await apresEnregistrement();
        if (typeof resultat === 'string') UI.toast(resultat, 'attention');   // avertissement d'habilitation
        else UI.toast(I18n.t('ordres.preparation.preparation_enregistree'), 'succes');
      });
    }
    placerCausesFrequentes(UI.$('.ot-causes', panneau), ot);
    UI.$('#form-preparation', panneau).before(Wiki.champRecherche({ equipementId: ot.equipement_id, texteInitial: ot.titre, titre: I18n.t('ordres.preparation.chercher_historique'), montres: 3 }));
    afficherOperationsPreparation(UI.$('#ot-bloc-operations', panneau), ot, modifiable);
    afficherPieces(UI.$('#ot-bloc-pieces', panneau), ot, modifiable);
  }

  /**
   * Enregistre la préparation ; RG8 : avertissement au journal si le technicien n'est pas habilité.
   * Renvoie false (échec), true (enregistré) ou le texte de l'avertissement d'habilitation (enregistré).
   */
  async function enregistrerPreparation(ot, formulaire) {
    if (UI.verifierFormulaire(formulaire).length) return false;
    const valeurs = UI.lireFormulaire(formulaire);
    const changements = {
      travail_a_faire: valeurs.travail_a_faire, consignes: valeurs.consignes, technicien_id: valeurs.technicien_id,
      date_prevue: valeurs.date_prevue, temps_prevu_h: valeurs.temps_prevu_h,
    };
    const changes = await pendant(UI.$('button[type=submit]', formulaire), () => modifierOt(ot.id, changements, I18n.t('ordres.enregistrer_preparation.preparation')), I18n.t('ordres.enregistrer_preparation.preparation'));
    if (changes === undefined) return false;
    const affectation = changes.includes('technicien_id') || changes.includes('date_prevue');
    const habilitation = verifierHabilitation(ot.equipement_id, valeurs.technicien_id, valeurs.date_prevue);
    if (affectation && habilitation) {
      await journaliserHabilitation(ot.id, habilitation);
      return I18n.t('ordres.enregistrer_preparation.preparation_enregistree_avertissement_habilitation', { habilitation });
    }
    return true;
  }

  // --- Opérations (ot_operations) : ajoutables et modifiables, jamais supprimées ---

  function afficherOperationsPreparation(bloc, ot, modifiable) {
    const operations = operationsDe(ot.id);
    UI.remplir(bloc, UI.html`
      ${enteteOnglet(I18n.t('ordres.operations_preparation.operations_nb_operations', { nbOperations: operations.length }), I18n.t('ordres.operations_preparation.operation_jamais_supprimee'))}
      <form id="form-operations" novalidate>
        <fieldset class="ot-fieldset"${modifiable ? '' : UI.brut(' disabled')}>
          <div class="table-defile"><table class="table ot-table-saisie">
            <thead><tr><th scope="col" class="num">${I18n.t('ordres.operations_preparation.n')}</th><th scope="col">${I18n.t('ordres.operations_preparation.operation')}</th><th scope="col">${I18n.t('ordres.operations_preparation.valeur_attendue')}</th></tr></thead>
            <tbody>
              ${operations.map((op) => UI.html`<tr data-operation="${op.id}">
                <td class="num" data-libelle="${I18n.t('ordres.operations_preparation.n')}">${op.ordre}</td>
                <td data-libelle="${I18n.t('ordres.operations_preparation.operation')}"><input type="text" class="ot-op-libelle" value="${op.operation}" aria-label="${I18n.t('ordres.operations_preparation.operation_ordre', { ordre: op.ordre })}"></td>
                <td data-libelle="${I18n.t('ordres.operations_preparation.valeur_attendue')}"><input type="text" class="ot-op-attendu" value="${op.valeur_attendue}" aria-label="${I18n.t('ordres.operations_preparation.valeur_attendue_ligne', { ordre: op.ordre })}"></td></tr>`)}
              ${modifiable ? UI.html`<tr class="ot-nouvelle-ligne"><td class="num" data-libelle="${I18n.t('ordres.operations_preparation.n')}">+</td>
                <td data-libelle="${I18n.t('ordres.operations_preparation.nouvelle_operation')}"><input type="text" name="nouvelle_operation" placeholder="${I18n.t('ordres.operations_preparation.nouvelle_operation')}" aria-label="${I18n.t('ordres.operations_preparation.nouvelle_operation')}"></td>
                <td data-libelle="${I18n.t('ordres.operations_preparation.valeur_attendue')}"><input type="text" name="nouvelle_valeur" placeholder="${I18n.t('ordres.operations_preparation.valeur_attendue_facultatif')}" aria-label="${I18n.t('ordres.operations_preparation.valeur_attendue_nouvelle_operation')}"></td></tr>` : ''}
              ${!modifiable && !operations.length ? UI.html`<tr><td colspan="3" class="vide-table">${I18n.t('ordres.operations_preparation.aucune_operation')}</td></tr>` : ''}
            </tbody></table></div>
        </fieldset>
        ${modifiable ? UI.html`<div class="actions"><span class="espace"></span><button type="submit" class="btn btn-secondaire">${UI.icone('valider')}${I18n.t('ordres.operations_preparation.enregistrer_operations')}</button></div>` : ''}
      </form>`);
    if (!modifiable) return;
    const formulaire = UI.$('#form-operations', bloc);
    const enregistrer = () => enregistrerOperations(ot, formulaire);
    declarerFormulaire(formulaire, enregistrer);
    formulaire.addEventListener('submit', async (evenement) => {
      evenement.preventDefault();
      if (await enregistrer()) { formulaire.dataset.modifie = '0'; await apresEnregistrement(); UI.toast(I18n.t('ordres.operations_preparation.operations_enregistrees'), 'succes'); }
    });
  }

  async function enregistrerOperations(ot, formulaire) {
    const modifiees = UI.$$('tr[data-operation]', formulaire).map((rangee) => ({
      id: rangee.dataset.operation,
      operation: UI.$('.ot-op-libelle', rangee).value.trim(),
      valeur_attendue: UI.$('.ot-op-attendu', rangee).value.trim(),
    }));
    if (modifiees.some((op) => !op.operation)) {
      UI.toast(I18n.t('ordres.enregistrer_operations.operation_peut_pas_etre'), 'attention');
      return false;
    }
    const nouvelle = { operation: (UI.$('[name="nouvelle_operation"]', formulaire) || {}).value || '', valeur_attendue: (UI.$('[name="nouvelle_valeur"]', formulaire) || {}).value || '' };
    const resultat = await pendant(UI.$('button[type=submit]', formulaire), () => modifierLieeAOt(ot.id, 'ot_operations', (lignes, outils) => {
      modifiees.forEach((op) => {
        const ligne = lignes.find((l) => l.id === op.id && l.ot_id === ot.id);
        if (ligne) { ligne.operation = op.operation; ligne.valeur_attendue = op.valeur_attendue; }
      });
      if (nouvelle.operation.trim()) {
        const ordreMax = lignes.filter((l) => l.ot_id === ot.id).reduce((max, l) => Math.max(max, nombre(l.ordre)), 0);
        lignes.push({ id: outils.nouvelId(lignes), ot_id: ot.id, ordre: String(ordreMax + 1), operation: nouvelle.operation.trim(),
          valeur_attendue: nouvelle.valeur_attendue.trim(), fait: '0', valeur_mesuree: '' });
      }
      return true;
    }, { action: I18n.t('ordres.enregistrer_operations.operations_ot_id', { otId: ot.id }) }), I18n.t('ordres.enregistrer_operations.operations'));
    return resultat === true;
  }

  // --- Pièces prévues (ot_pieces) : stock disponible, alerte si insuffisant ; quantité 0 = retirée ---

  function optionsArticles(ot) {
    const liees = new Set(Donnees.lignes('article_equipement').filter((l) => l.equipement_id === ot.equipement_id).map((l) => l.article_id));
    const actifs = Donnees.lignes('articles').filter((a) => a.actif !== '0')
      .sort((a, b) => libelleArticle(a).localeCompare(libelleArticle(b), 'fr'));
    const option = (a) => UI.html`<option value="${a.id}">${I18n.t('ordres.options_articles.libelle_article_stock_stock_article', { libelleArticle: libelleArticle(a), stockArticle: UI.nombreFr(Donnees.stockArticle(a.id)) })}</option>`;
    const pourEquipement = actifs.filter((a) => liees.has(a.id));
    return UI.html`<option value="">${I18n.t('ordres.options_articles.choisir_article')}</option>
      ${pourEquipement.length ? UI.html`<optgroup label="${I18n.t('ordres.options_articles.pieces_equipement')}">${pourEquipement.map(option)}</optgroup>` : ''}
      <optgroup label="${I18n.t('ordres.options_articles.tout_magasin')}">${actifs.filter((a) => !liees.has(a.id)).map(option)}</optgroup>`;
  }

  /** Quantité du fichier ('1.5') → texte de saisie ('1,5') ; vide → '0'. */
  function quantiteSaisie(valeur) {
    return texte(valeur) === '' ? '0' : texte(valeur).replace('.', ',');
  }

  function afficherPieces(bloc, ot, modifiable) {
    const pieces = lignesDeLOt('ot_pieces', ot.id);
    // Même règle que « Planifié » (RG3) : une pièce manque si le stock est inférieur à son besoin
    // restant (prévu − déjà sorti pour cet OT).
    const manquantes = piecesManquantes(ot.id);
    const enManque = new Set(manquantes.map((p) => p.article_id));
    UI.remplir(bloc, UI.html`
      ${enteteOnglet(I18n.t('ordres.pieces.pieces_prevues'), I18n.t('ordres.pieces.quantite_0_piece_retiree'))}
      <form id="form-pieces" novalidate>
        <fieldset class="ot-fieldset"${modifiable ? '' : UI.brut(' disabled')}>
          <div class="table-defile"><table class="table ot-table-saisie">
            <thead><tr><th scope="col">${I18n.t('commun.champ.article')}</th><th scope="col">${I18n.t('ordres.pieces.emplacement')}</th><th scope="col" class="num">${I18n.t('ordres.pieces.prevu')}</th><th scope="col" class="num">${I18n.t('ordres.pieces.stock')}</th><th scope="col">${I18n.t('ordres.pieces.etat')}</th></tr></thead>
            <tbody>
              ${pieces.map((piece) => {
                const article = Donnees.trouver('articles', piece.article_id);
                const stock = Donnees.stockArticle(piece.article_id);
                const retiree = nombre(piece.quantite_prevue) === 0;
                const insuffisant = !retiree && enManque.has(piece.article_id);
                return UI.html`<tr data-piece="${piece.id}"${retiree ? UI.brut(' class="attenue"') : ''}>
                  <td data-libelle="${I18n.t('commun.champ.article')}">${libelleArticle(article) || piece.article_id}</td><td data-libelle="${I18n.t('ordres.pieces.emplacement')}">${article ? article.emplacement : ''}</td>
                  <td class="num" data-libelle="${I18n.t('ordres.pieces.prevu')}"><input type="text" inputmode="decimal" class="ot-quantite" value="${quantiteSaisie(piece.quantite_prevue)}" aria-label="${I18n.t('ordres.pieces.quantite_prevue', { libelleArticle: libelleArticle(article) })}"></td>
                  <td class="num" data-libelle="${I18n.t('ordres.pieces.stock')}">${UI.nombreFr(stock)}</td>
                  <td data-libelle="${I18n.t('ordres.pieces.etat')}">${retiree ? UI.html`<span class="badge neutre">${I18n.t('ordres.pieces.retiree')}</span>` : insuffisant ? UI.html`<span class="badge ko">${I18n.t('ordres.pieces.stock_insuffisant')}</span>` : UI.html`<span class="badge ok">${I18n.t('ordres.pieces.disponible')}</span>`}</td></tr>`;
              })}
              ${!pieces.length && !modifiable ? UI.html`<tr><td colspan="5" class="vide-table">${I18n.t('ordres.pieces.aucune_piece_prevue')}</td></tr>` : ''}
            </tbody></table></div>
          ${modifiable ? UI.html`<div class="form-ligne ot-ajout-piece">
            <div class="champ"><label class="libelle" for="ot-nouvel-article">${I18n.t('ordres.pieces.ajouter_piece')}</label><select id="ot-nouvel-article" name="nouvel_article">${optionsArticles(ot)}</select></div>
            <div class="champ ot-champ-quantite"><label class="libelle" for="ot-nouvelle-quantite">${I18n.t('commun.champ.quantite')}</label><input type="text" inputmode="decimal" id="ot-nouvelle-quantite" name="nouvelle_quantite" value="1"></div>
          </div>` : ''}
        </fieldset>
        ${modifiable ? UI.html`<div class="actions"><span class="espace"></span><button type="submit" class="btn btn-secondaire">${UI.icone('valider')}${I18n.t('ordres.pieces.enregistrer_pieces')}</button></div>` : ''}
      </form>`);
    if (manquantes.length) {
      bloc.insertBefore(UI.bandeau('important', listeErreursHtml(I18n.t('ordres.pieces.stock_insuffisant_ot_pourra'),
        manquantes.map((p) => p.libelle + ' : ' + detailManque(p)))), UI.$('#form-pieces', bloc));
    }
    if (!modifiable) return;
    const formulaire = UI.$('#form-pieces', bloc);
    const enregistrer = () => enregistrerPieces(ot, formulaire);
    declarerFormulaire(formulaire, enregistrer);
    formulaire.addEventListener('submit', async (evenement) => {
      evenement.preventDefault();
      if (await enregistrer()) { formulaire.dataset.modifie = '0'; await apresEnregistrement(); UI.toast(I18n.t('ordres.pieces.pieces_prevues_enregistrees'), 'succes'); }
    });
  }

  async function enregistrerPieces(ot, formulaire) {
    const quantites = UI.$$('tr[data-piece]', formulaire).map((rangee) => ({ id: rangee.dataset.piece, quantite: UI.enNombre(UI.$('.ot-quantite', rangee).value) }));
    const article = UI.$('[name="nouvel_article"]', formulaire).value;
    const quantiteNouvelle = UI.enNombre(UI.$('[name="nouvelle_quantite"]', formulaire).value);
    if (quantites.some((q) => q.quantite === null || q.quantite < 0) || (article && (quantiteNouvelle === null || quantiteNouvelle <= 0))) {
      UI.toast(I18n.t('ordres.enregistrer_pieces.quantites_saisissez_nombres_positifs'), 'attention');
      return false;
    }
    const resultat = await pendant(UI.$('button[type=submit]', formulaire), () => modifierLieeAOt(ot.id, 'ot_pieces', (lignes, outils) => {
      quantites.forEach((q) => {
        const ligne = lignes.find((l) => l.id === q.id && l.ot_id === ot.id);
        if (ligne && nombre(ligne.quantite_prevue) !== q.quantite) ligne.quantite_prevue = String(q.quantite);
      });
      if (article) {
        const existante = lignes.find((l) => l.ot_id === ot.id && l.article_id === article);
        if (existante) existante.quantite_prevue = String(arrondi(nombre(existante.quantite_prevue) + quantiteNouvelle, 3));
        else lignes.push({ id: outils.nouvelId(lignes), ot_id: ot.id, article_id: article, quantite_prevue: String(quantiteNouvelle) });
      }
      return true;
    }, { action: I18n.t('ordres.enregistrer_pieces.pieces_prevues', { otId: ot.id }) }), I18n.t('ordres.enregistrer_pieces.pieces_prevues_nom'));
    return resultat === true;
  }

  // ===========================================================================================
  // 8. Onglet Exécution : démarrer, check-list, temps passés, arrêt, sous-traitance, date de fin
  // ===========================================================================================

  function peutExecuter(ot) {
    return (estTechnicien() || estResponsable()) && ['En cours', 'En attente'].includes(ot.statut);
  }

  function afficherExecution(panneau, ot) {
    const modifiable = peutExecuter(ot);
    const operations = operationsDe(ot.id);
    const demarrage = boutonsTransitions(ot, ['En cours']);
    UI.remplir(panneau, UI.html`
      ${demarrage.length && ot.statut !== 'Clôturé techniquement' ? UI.html`<div class="carte ot-demarrer sans-impression">
        <p>${ot.statut === 'En attente' ? I18n.t('ordres.execution.ot_attente_reprenez_quand') : I18n.t('ordres.execution.intervention_pas_commence_demarrer')}</p>
        <div class="actions">${demarrage}</div></div>` : ''}
      <form class="carte" id="form-execution" novalidate>
        ${enteteOnglet(I18n.t('ordres.execution.execution'), modifiable ? '' : (ot.statut === 'Créé' || ot.statut === 'Préparé' || ot.statut === 'Planifié' ? I18n.t('ordres.execution.disponible_fois_ot_demarre') : I18n.t('ordres.preparation.lecture_seule')))}
        <fieldset class="ot-fieldset"${modifiable ? '' : UI.brut(' disabled')}>
          <h3 class="ot-sous-titre">${I18n.t('ordres.execution.check_list')}</h3>
          ${operations.length ? UI.html`<ul class="check-liste">${operations.map((op) => UI.html`
            <li data-operation="${op.id}"${op.fait === '1' ? UI.brut(' class="fait"') : ''}>
              <label class="case"><input type="checkbox" class="ot-fait"${op.fait === '1' ? UI.brut(' checked') : ''}>
                <span><span class="operation">${op.ordre}. ${op.operation}</span>${op.valeur_attendue ? UI.html`<span class="attendu">${I18n.t('ordres.execution.attendu_valeur_attendue', { valeur_attendue: op.valeur_attendue })}</span>` : ''}</span></label>
              <input type="text" class="mesure ot-mesure" value="${op.valeur_mesuree}" placeholder="${I18n.t('ordres.execution.valeur_mesuree')}" aria-label="${I18n.t('ordres.execution.valeur_mesuree_operation', { ordre: op.ordre })}">
            </li>`)}</ul>` : UI.html`<p class="muted">${I18n.t('ordres.execution.aucune_operation_prevue_onglet')}</p>`}
          <h3 class="ot-sous-titre">${I18n.t('ordres.execution.deroulement')}</h3>
          <div class="form-grille">
            <div class="champ ot-champ-lu"><span class="libelle">${I18n.t('ordres.execution.debut')}</span><p class="ot-valeur">${UI.dateHeureFr(ot.date_debut) || '—'}</p></div>
            <div class="ot-date-fin" data-place="date_fin"></div>
            <div data-place="arret_production"></div><div data-place="duree_arret_h"></div>
            <div data-place="cout_soustraitance"></div>
          </div>
        </fieldset>
        ${modifiable ? UI.html`<div class="actions"><span class="espace"></span><button type="submit" class="btn btn-secondaire">${UI.icone('valider')}${I18n.t('ordres.execution.enregistrer_execution')}</button></div>` : ''}
      </form>
      <div class="carte" id="ot-bloc-temps"></div>
      <div class="carte" id="ot-bloc-sorties"></div>`);
    const formulaire = UI.$('#form-execution', panneau);
    const placer = (nom, element) => placerChamp(formulaire, nom, element);
    placer('date_fin', champOt('date_fin', ot.date_fin));
    placer('arret_production', champOt('arret_production', ot.arret_production, { libelle: I18n.t('ordres.execution.arret_production_pendant_intervention') }));
    placer('duree_arret_h', champOt('duree_arret_h', ot.duree_arret_h));
    placer('cout_soustraitance', champOt('cout_soustraitance', ot.cout_soustraitance, { libelle: I18n.t('ordres.execution.cout_sous_traitance') }));
    if (modifiable) {
      const blocDateFin = UI.$('[data-champ="date_fin"]', formulaire);
      const maintenant = UI.element(UI.html`<button type="button" class="lien-bouton ot-maintenant">${I18n.t('ordres.execution.maintenant')}</button>`);
      maintenant.addEventListener('click', () => {
        UI.$('[name="date_fin"]', blocDateFin).value = Donnees.maintenant().replace(' ', 'T');
        formulaire.dataset.modifie = '1';
        App.marquerSaisie(true);
      });
      UI.$('.libelle', blocDateFin).appendChild(maintenant);
      // Pas de date de fin dans le futur : le sélecteur l'empêche, l'enregistrement le contrôle aussi.
      UI.$('[name="date_fin"]', blocDateFin).max = Donnees.maintenant().replace(' ', 'T');
      const enregistrer = () => enregistrerExecution(ot, formulaire);
      declarerFormulaire(formulaire, enregistrer);
      formulaire.addEventListener('submit', async (evenement) => {
        evenement.preventDefault();
        if (await enregistrer()) { formulaire.dataset.modifie = '0'; await apresEnregistrement(); UI.toast(I18n.t('ordres.execution.execution_enregistree'), 'succes'); }
      });
    }
    afficherTemps(UI.$('#ot-bloc-temps', panneau), ot, modifiable);
    afficherPiecesSorties(UI.$('#ot-bloc-sorties', panneau), ot);
  }

  async function enregistrerExecution(ot, formulaire) {
    const champFin = UI.$('[name="date_fin"]', formulaire);
    if (champFin) champFin.max = Donnees.maintenant().replace(' ', 'T');     // l'heure a pu avancer
    if (UI.verifierFormulaire(formulaire).length) return false;
    const valeurs = UI.lireFormulaire(formulaire);
    if (Ordres.dateFinDansLeFutur(valeurs.date_fin)) {
      UI.toast(I18n.t('ordres.enregistrer_execution.date_fin_peut_pas'), 'erreur');
      return false;
    }
    const checkListe = UI.$$('li[data-operation]', formulaire).map((li) => ({
      id: li.dataset.operation, fait: UI.$('.ot-fait', li).checked ? '1' : '0', valeur_mesuree: UI.$('.ot-mesure', li).value.trim(),
    }));
    const bouton = UI.$('button[type=submit]', formulaire);
    const changes = await pendant(bouton, () => modifierOt(ot.id, {
      date_fin: valeurs.date_fin, arret_production: valeurs.arret_production,
      duree_arret_h: valeurs.duree_arret_h, cout_soustraitance: valeurs.cout_soustraitance,
    }, I18n.t('ordres.enregistrer_execution.execution')), I18n.t('ordres.enregistrer_execution.execution'));
    if (changes === undefined) return false;
    if (!checkListe.length) return true;
    const resultat = await pendant(bouton, () => modifierLieeAOt(ot.id, 'ot_operations', (lignes) => {
      checkListe.forEach((op) => {
        const ligne = lignes.find((l) => l.id === op.id && l.ot_id === ot.id);
        if (ligne) { ligne.fait = op.fait; ligne.valeur_mesuree = op.valeur_mesuree; }
      });
      return true;
    }, { action: 'check-list de ' + ot.id }), 'check-list');
    return resultat === true;
  }

  // --- Temps passés (ot_temps) : par technicien et par date ---

  function afficherTemps(bloc, ot, modifiable) {
    const temps = lignesDeLOt('ot_temps', ot.id).slice().sort((a, b) => texte(a.date).localeCompare(texte(b.date)) || a.id.localeCompare(b.id));
    const total = temps.reduce((somme, ligne) => somme + nombre(ligne.heures), 0);
    const technicienParDefaut = (estTechnicien() && monTechnicienId()) || ot.technicien_id || '';
    UI.remplir(bloc, UI.html`
      ${enteteOnglet(I18n.t('ordres.temps.temps_passes'), I18n.t('ordres.temps.total_total', { total: UI.heures(total) }))}
      <div class="table-defile"><table class="table">
        <thead><tr><th scope="col">${I18n.t('commun.champ.date')}</th><th scope="col">${I18n.t('commun.champ.technicien')}</th><th scope="col" class="num">${I18n.t('ordres.temps.heures')}</th></tr></thead>
        <tbody>${temps.length ? temps.map((ligne) => UI.html`<tr><td>${UI.dateFr(ligne.date)}</td><td>${nomTechnicien(ligne.technicien_id)}</td><td class="num">${UI.heures(ligne.heures)}</td></tr>`)
          : UI.html`<tr><td colspan="3" class="vide-table">${I18n.t('ordres.temps.aucun_temps_saisi')}</td></tr>`}</tbody>
      </table></div>
      ${modifiable ? UI.html`<form class="form-ligne ot-ajout-temps" id="form-temps" novalidate>
        <div class="champ"><label class="libelle" for="ot-temps-technicien">${I18n.t('commun.champ.technicien')}</label>
          <select id="ot-temps-technicien" name="technicien_id">${optionsHtml(listeTechniciens(technicienParDefaut), technicienParDefaut)}</select></div>
        <div class="champ"><label class="libelle" for="ot-temps-date">${I18n.t('commun.champ.date')}</label><input type="date" id="ot-temps-date" name="date" value="${aujourdhui()}"></div>
        <div class="champ ot-champ-quantite"><label class="libelle" for="ot-temps-heures">${I18n.t('ordres.temps.heures')}</label><input type="text" inputmode="decimal" id="ot-temps-heures" name="heures" placeholder="1,5"></div>
        <button type="submit" class="btn btn-secondaire">${UI.icone('ajouter')}${I18n.t('ordres.temps.ajouter_temps')}</button>
      </form>` : ''}`);
    if (!modifiable) return;
    const formulaire = UI.$('#form-temps', bloc);
    // Avant une transition, un temps saisi mais pas encore ajouté est ajouté ; un champ vide est ignoré.
    declarerFormulaire(formulaire, () => ajouterTemps(ot, formulaire, false));
    formulaire.addEventListener('submit', async (evenement) => {
      evenement.preventDefault();
      if (await ajouterTemps(ot, formulaire, true)) { formulaire.dataset.modifie = '0'; await apresEnregistrement(); UI.toast(I18n.t('ordres.temps.temps_ajoute'), 'succes'); }
    });
  }

  async function ajouterTemps(ot, formulaire, depuisLeBouton) {
    const valeurs = UI.lireFormulaire(formulaire);
    const heures = UI.enNombre(valeurs.heures);
    if (!valeurs.heures && !depuisLeBouton) return true;   // rien à ajouter
    if (heures === null || heures <= 0 || heures > 24 || !valeurs.date || !valeurs.technicien_id) {
      UI.toast(I18n.t('ordres.ajouter_temps.temps_passe_choisissez_technicien'), 'attention');
      return false;
    }
    const resultat = await pendant(UI.$('button[type=submit]', formulaire), () => modifierLieeAOt(ot.id, 'ot_temps', (lignes, outils) => {
      lignes.push({ id: outils.nouvelId(lignes), ot_id: ot.id, technicien_id: valeurs.technicien_id, date: valeurs.date, heures: String(heures) });
      return true;
    }, { action: I18n.t('ordres.ajouter_temps.temps_passe', { otId: ot.id }) }), I18n.t('ordres.ajouter_temps.temps_passe_nom'));
    return resultat === true;
  }

  // ===========================================================================================
  // 9. Onglet Compte rendu : codes, compte rendu, remise en service, clôture technique, coût RG7
  // ===========================================================================================

  function afficherCompteRendu(panneau, ot) {
    const modifiable = peutExecuter(ot);
    const equipement = equipementDe(ot);
    UI.remplir(panneau, UI.html`
      <div class="ot-causes"></div>
      <form class="carte" id="form-compte-rendu" novalidate>
        ${enteteOnglet(I18n.t('ordres.compte_rendu.compte_rendu'), modifiable ? '' : I18n.t('ordres.preparation.lecture_seule'))}
        <fieldset class="ot-fieldset form-grille"${modifiable ? '' : UI.brut(' disabled')}>
          <div data-place="symptome_code"></div><div data-place="cause_code"></div><div data-place="remede_code"></div><div></div>
          <div class="large" data-place="compte_rendu"></div>
          <div class="large" data-place="astuce"></div>
          <div class="large ot-remise" data-place="remise_service"></div>
        </fieldset>
        ${modifiable ? UI.html`<div class="actions"><button type="submit" class="btn btn-secondaire">${UI.icone('valider')}${I18n.t('ordres.compte_rendu.enregistrer_compte_rendu')}</button>
          <span class="espace"></span>${boutonsTransitions(ot, ['Clôturé techniquement'])}</div>` : ''}
      </form>
      <div class="carte ot-cout" id="ot-cout"></div>`);
    const formulaire = UI.$('#form-compte-rendu', panneau);
    const placer = (nom, element) => placerChamp(formulaire, nom, element);
    placer('symptome_code', champOt('symptome_code', ot.symptome_code, { liste: listeCodes('symptôme') }));
    placer('cause_code', champOt('cause_code', ot.cause_code, { liste: listeCodes('cause') }));
    placer('remede_code', champOt('remede_code', ot.remede_code, { liste: listeCodes('remède') }));
    placer('compte_rendu', champOt('compte_rendu', ot.compte_rendu, {
      aide: I18n.t('ordres.compte_rendu.ete_constate_cause_ete'),
    }));
    // Astuce (facultative, jamais exigée par RG4) : mêmes règles d'édition ; en lecture seule, montrée si elle existe.
    if (modifiable || texte(ot.astuce)) placer('astuce', champOt('astuce', ot.astuce, { aide: aideAstuce() }));
    else UI.$('[data-place="astuce"]', formulaire).remove();
    placer('remise_service', champOt('remise_service', ot.remise_service, {
      libelle: I18n.t('ordres.compte_rendu.equipement_remis_service_securite'),
    }));
    if (equipement && texte(equipement.habilitation_requise)) {
      UI.$('.ot-remise', formulaire).appendChild(UI.element(UI.html`<p class="aide">${Ordres.rappelConsignation()}</p>`));
    }
    if (modifiable) {
      const ia = typeof Ia === 'undefined' ? null : brancherIa(formulaire, ot);   // assistant IA (§9 bis)
      const enregistrer = () => enregistrerCompteRendu(ot, formulaire, ia);
      declarerFormulaire(formulaire, enregistrer);
      formulaire.addEventListener('submit', async (evenement) => {
        evenement.preventDefault();
        if (await enregistrer()) { formulaire.dataset.modifie = '0'; await apresEnregistrement(); UI.toast(I18n.t('ordres.compte_rendu.compte_rendu_enregistre'), 'succes'); }
      });
    }
    placerCausesFrequentes(UI.$('.ot-causes', panneau), ot);
    afficherCout(UI.$('#ot-cout', panneau), ot);
  }

  // `ia` : propositions de l'IA reprises dans ce formulaire (tracées au journal après l'écriture).
  async function enregistrerCompteRendu(ot, formulaire, ia) {
    const valeurs = UI.lireFormulaire(formulaire);
    const longueur = Array.from(valeurs.astuce || '').length;           // en caractères, pas en unités UTF-16
    const refus = longueur > ASTUCE_MAX ? I18n.t('ordres.enregistrer_compte_rendu.astuce_trop_longue_caracteres', { n: longueur, max: ASTUCE_MAX }) : '';
    UI.erreurChamp(formulaire, 'astuce', refus);
    if (refus) { UI.toast(refus, 'erreur'); return false; }
    const changes = await pendant(UI.$('button[type=submit]', formulaire), () => modifierOt(ot.id, {
      symptome_code: valeurs.symptome_code, cause_code: valeurs.cause_code, remede_code: valeurs.remede_code,
      compte_rendu: valeurs.compte_rendu, remise_service: valeurs.remise_service, astuce: valeurs.astuce,
    }, I18n.t('ordres.enregistrer_compte_rendu.compte_rendu')), I18n.t('ordres.enregistrer_compte_rendu.compte_rendu'));
    if (changes === undefined) return false;
    if (ia) await ia.apresEnregistrement(changes, valeurs);
    return true;
  }

  function afficherCout(bloc, ot) {
    const resultat = cout(ot);
    const detail = resultat.detail;
    UI.remplir(bloc, UI.html`
      ${enteteOnglet(I18n.t('ordres.cout.cout_intervention'), I18n.t('ordres.cout.rg_7_main_uvre'))}
      <div class="lignes ot-lignes-cout">
        ${I18n.html('ordres.cout.main_uvre_pieces_sorties', { nombreHeures: UI.heures(detail.nombreHeures), euroHeures: UI.euro(resultat.heures), euroPieces: UI.euro(resultat.pieces), euroSoustraitance: UI.euro(resultat.soustraitance), euroTotal: UI.euro(resultat.total) })}
      </div>
      <details class="vue-tableau ot-detail-cout"><summary>${I18n.t('ordres.cout.voir_detail')}</summary>
        <div class="table-defile"><table class="table">
          <thead><tr><th scope="col">${I18n.t('ordres.cout.poste')}</th><th scope="col">${I18n.t('ordres.cout.detail')}</th><th scope="col" class="num">${I18n.t('ordres.cout.montant')}</th></tr></thead>
          <tbody>
            ${detail.temps.map((t) => UI.html`<tr><td>${nomTechnicien(t.technicien_id)}</td><td>${I18n.t('ordres.cout.date_heures_euro_h', { date: UI.dateFr(t.date), heures: UI.heures(t.heures), euro: UI.euro(t.taux) })}</td><td class="num">${UI.euro(t.montant)}</td></tr>`)}
            ${detail.pieces.map((p) => UI.html`<tr><td>${p.libelle}</td><td>${I18n.t('ordres.cout.sorties_sortie', { n: p.sorties, sorties: UI.nombreFr(p.sorties) })}${p.retours ? UI.html` ${I18n.t('ordres.cout.retours_retour', { n: p.retours, retours: UI.nombreFr(p.retours) })}` : ''} × ${UI.euro(p.prix)}</td><td class="num">${UI.euro(p.montant)}</td></tr>`)}
            ${resultat.soustraitance ? UI.html`<tr><td>${I18n.t('ordres.cout.sous_traitance')}</td><td></td><td class="num">${UI.euro(resultat.soustraitance)}</td></tr>` : ''}
            ${!detail.temps.length && !detail.pieces.length && !resultat.soustraitance ? UI.html`<tr><td colspan="3" class="vide-table">${I18n.t('ordres.cout.aucun_cout_instant')}</td></tr>` : ''}
          </tbody></table></div>
        <p class="note">${I18n.t('ordres.cout.pieces_sorties_retournees_ot')}</p>
      </details>`);
  }

  // ===========================================================================================
  // 9 bis. Assistant IA du compte rendu (lot 4, ARCHITECTURE.md §17.5) : « Proposer les codes » et
  // « Rédiger le compte rendu » à partir des notes du champ. L'IA propose, l'humain valide :
  // « Utiliser » remplit le formulaire ; rien n'est écrit avant « Enregistrer le compte rendu » et
  // aucun statut ne change. Seulement sur un OT modifiable (ni verrouillé, ni pour le demandeur).
  // ===========================================================================================

  // Familles de codes : clé de la réponse de l'IA, champ de l'OT, libellé affiché.
  const CODES_IA = [['symptome', 'symptome_code'], ['cause', 'cause_code'], ['remede', 'remede_code']];
  const libelleFamilleIa = (cle) => (cle === 'symptome' ? I18n.t('commun.champ.symptome')
    : cle === 'cause' ? I18n.t('ordres.libelle_famille_ia.cause') : I18n.t('ordres.libelle_famille_ia.remede'));

  const zonesIa = new Set();                // { zone, remplir } de l'onglet affiché
  let ecouteIa = false;

  /**
   * Zone de boutons IA pleine largeur placée contre `voisin` (insertAdjacentElement) ; `poser(zone)`
   * la remplit maintenant, puis à chaque changement de l'IA : le test du fournisseur, fait à
   * l'ouverture de Prévo, finit souvent après l'affichage, et un fournisseur devenu injoignable
   * retire les boutons. Un seul écouteur ; une zone qui n'est plus affichée est oubliée.
   * Renvoie la fonction qui la remplit de nouveau.
   */
  function zoneIa(voisin, position, poser) {
    const zone = UI.element(UI.html`<div class="actions ot-ia sans-impression"></div>`);
    voisin.insertAdjacentElement(position, zone);
    const remplir = () => { zone.textContent = ''; poser(zone); zone.hidden = !zone.children.length; };
    zonesIa.forEach((entree) => { if (!entree.zone.isConnected) zonesIa.delete(entree); });
    zonesIa.add({ zone, remplir });
    remplir();
    if (!ecouteIa) {
      ecouteIa = true;
      Ia.evenements.addEventListener('changement', () => zonesIa.forEach((entree) => {
        if (entree.zone.isConnected) entree.remplir(); else zonesIa.delete(entree);
      }));
    }
    return remplir;
  }

  // Données envoyées à l'IA (liste blanche du §17.3) : jamais de nom de technicien, de taux ni de coût.
  function donneesCompteRendu(ot, notes) {
    const equipement = equipementDe(ot) || {};
    // Pièces sorties nettes pour l'OT (sorties − retours, RG7) : seules la désignation et la quantité partent.
    const pieces = cout(ot).detail.pieces.filter((piece) => piece.quantite > 0).map((piece) => ({
      designation: (Donnees.trouver('articles', piece.article_id) || {}).designation || piece.libelle,
      quantite: UI.nombreFr(piece.quantite),
    }));
    return { notes, titre: ot.titre, type: ot.type, repere: equipement.repere, designation: equipement.designation, pieces };
  }

  function donneesCodes(ot, compteRendu) {
    const demande = ot.di_id ? Donnees.trouver('demandes', ot.di_id) : null;
    return { compteRendu, titre: ot.titre, symptomeDI: demande ? demande.symptome : '' };
  }

  // Encadré des codes : code retenu et son libellé ; code inventé par l'IA annoncé et ignoré (D70).
  function renduCodes(resultat) {
    const rejetes = new Map(resultat.rejetes.map((rejet) => [rejet.champ, rejet.code]));
    return UI.html`<ul class="ia-liste">${CODES_IA.map(([cle]) => {
      const libelle = libelleFamilleIa(cle);
      const code = resultat[cle];
      const connu = code && listeCodes(Ia.FAMILLES_CODES[cle]).find((entree) => entree.valeur === code);
      if (code) return UI.html`<li>${libelle} : <b>${connu ? connu.libelle : code}</b></li>`;
      if (rejetes.has(cle)) return UI.html`<li class="ot-ia-rejet">${I18n.t('ordres.rendu_codes.code_inconnu_propose_ia', { libelle, code: rejetes.get(cle) })}</li>`;
      return UI.html`<li>${I18n.t('ordres.rendu_codes.aucun_code_propose', { libelle })}</li>`;
    })}</ul>`;
  }

  /**
   * Boutons IA de l'onglet Compte rendu (OT modifiable). Renvoie { apresEnregistrement(changes,
   * valeurs) }, appelé après l'écriture réussie : journal « proposition IA utilisée » pour chaque
   * champ venu de l'IA et écrit (un code seulement s'il est resté celui proposé), une seule fois.
   */
  function brancherIa(formulaire, ot) {
    const utilisees = new Map();            // champ → { valeur (null : texte retouchable), modele }
    let origine = null;                     // notes d'avant la proposition (« Annuler la proposition »)
    const blocTexte = UI.$('[data-champ="compte_rendu"]', formulaire);
    const champTexte = UI.$('textarea', blocTexte);
    const liste = (champ) => UI.$('[name="' + champ + '"]', formulaire);
    // Valeur posée comme une saisie : formulaire « modifié », saisie en cours (pas de réaffichage).
    const changer = (champ, valeur, type) => { champ.value = valeur; champ.dispatchEvent(new Event(type, { bubbles: true })); };

    function prendreTexte(resultat, reponse) {
      if (origine === null) origine = champTexte.value;
      changer(champTexte, resultat.texte, 'input');
      utilisees.set('compte_rendu', { valeur: null, modele: reponse.modele });
      poserTexte();
    }

    function annulerProposition() {
      changer(champTexte, origine, 'input');
      origine = null;
      utilisees.delete('compte_rendu');
      poserTexte();
      champTexte.focus();
    }

    function prendreCodes(resultat, reponse) {
      CODES_IA.forEach(([cle, champ]) => {
        if (!resultat[cle]) return;              // aucun code, ou code inventé : la liste ne change pas
        changer(liste(champ), resultat[cle], 'change');
        utilisees.set(champ, { valeur: resultat[cle], modele: reponse.modele });
      });
    }

    function rediger(zone) {
      if (!champTexte.value.trim()) {
        UI.toast(I18n.t('ordres.brancher_ia.ecrivez_abord_notes_compte'), 'attention');
        return;
      }
      Ia.ouvrirEncadre({ apres: zone, fonction: 'compteRendu', donnees: donneesCompteRendu(ot, champTexte.value),
        utiliser: prendreTexte, modifier: (resultat, reponse) => { prendreTexte(resultat, reponse); champTexte.focus(); } });
    }

    zoneIa(blocTexte, 'beforebegin', (zone) => {
      const bouton = Ia.bouton(I18n.t('ordres.brancher_ia.proposer_codes'), () => Ia.ouvrirEncadre({ apres: zone, fonction: 'codes',
        donnees: donneesCodes(ot, champTexte.value), rendu: renduCodes, utiliser: prendreCodes,
        modifier: (resultat, reponse) => { prendreCodes(resultat, reponse); liste('symptome_code').focus(); } }));
      if (bouton) zone.appendChild(bouton);
    });
    const poserTexte = zoneIa(blocTexte, 'afterend', (zone) => {
      const bouton = Ia.bouton(I18n.t('ordres.brancher_ia.rediger_compte_rendu'), () => rediger(zone));
      if (bouton) zone.appendChild(bouton);
      if (origine === null) return;
      const annuler = UI.element(UI.html`<button type="button" class="btn btn-fantome ot-ia-annuler">${I18n.t('ordres.brancher_ia.annuler_proposition')}</button>`);
      annuler.addEventListener('click', annulerProposition);
      zone.appendChild(annuler);
    });

    async function apresEnregistrement(changes, valeurs) {
      for (const [champ, proposition] of utilisees) {
        const gardee = proposition.valeur === null || valeurs[champ] === proposition.valeur;
        if (!gardee || !changes.includes(champ)) continue;
        try {
          await Ia.tracerUtilisation('ordres_travail', ot.id, champ, proposition.modele);
        } catch (erreur) {
          console.warn('Prévo (ordres) : trace de la proposition IA non écrite (' + (erreur && erreur.message) + ').', erreur);
        }
      }
      utilisees.clear();
      origine = null;                         // enregistré : la proposition n'est plus annulable
      poserTexte();
    }
    return { apresEnregistrement };
  }

  // ===========================================================================================
  // 10. Onglet Historique équipement : autres OT et DI du même équipement
  // ===========================================================================================

  /**
   * Sur téléphone, un tableau « empilé » montre une carte par ligne : chaque cellule reçoit le
   * libellé de sa colonne (data-libelle, affiché par css/modules/ordres.css).
   */
  function etiqueterCellules(table) {
    table.classList.add('ot-table-empilee');
    const libelles = UI.$$('thead th', table).map((th) => th.textContent.trim());
    UI.$$('tbody tr', table).forEach((rangee) => {
      Array.from(rangee.cells).forEach((cellule, rang) => {
        if (libelles[rang] && cellule.colSpan === 1) cellule.dataset.libelle = libelles[rang];
      });
    });
  }

  function afficherHistorique(panneau, ot) {
    const autres = Donnees.lignes('ordres_travail').filter((autre) => autre.equipement_id === ot.equipement_id && autre.id !== ot.id);
    const demandes = Donnees.lignes('demandes').filter((di) => di.equipement_id === ot.equipement_id);
    const blocOt = UI.element(UI.html`<section class="carte"><div class="entete-carte"><h2>${I18n.t('ordres.historique.autres_ordres_travail', { nbAutres: autres.length })}</h2></div></section>`);
    blocOt.appendChild(UI.tableau({
      colonnes: [
        { cle: 'id', libelle: I18n.t('ordres.historique.numero'), rendu: (l) => lienOt(l.id) },
        { cle: 'date_creation', libelle: I18n.t('ordres.historique.cree'), rendu: (l) => UI.dateFr(l.date_creation) },
        { cle: 'priorite', libelle: I18n.t('commun.champ.priorite'), rendu: (l) => UI.badgePriorite(l.priorite) },
        { cle: 'statut', libelle: I18n.t('commun.champ.statut'), rendu: (l) => UI.badgeStatut(l.statut) },
        { cle: 'type', libelle: I18n.t('ordres.historique.type') },
        { cle: 'titre', libelle: I18n.t('ordres.historique.titre') },
      ],
      lignes: autres, triInitial: { cle: 'date_creation', sens: 'desc' }, libelle: I18n.t('ordres.historique.autres_ot_equipement'),
      vide: I18n.t('ordres.historique.aucun_autre_ot_equipement'), surClic: (l) => App.naviguer('#/ot/' + encodeURIComponent(l.id)),
    }));
    const blocDi = UI.element(UI.html`<section class="carte"><div class="entete-carte"><h2>${I18n.t('ordres.historique.demandes_intervention', { nbDemandes: demandes.length })}</h2></div></section>`);
    blocDi.appendChild(UI.tableau({
      colonnes: [
        { cle: 'id', libelle: I18n.t('ordres.historique.numero'), rendu: (l) => UI.html`<a href="#/di/${encodeURIComponent(l.id)}">${l.id}</a>` },
        { cle: 'date_heure', libelle: I18n.t('commun.champ.date'), rendu: (l) => UI.dateFr(l.date_heure) },
        { cle: 'symptome', libelle: I18n.t('commun.champ.symptome') },
        { cle: 'impact', libelle: I18n.t('ordres.historique.impact') },
        { cle: 'statut', libelle: I18n.t('commun.champ.statut'), rendu: (l) => UI.badgeStatut(l.statut) },
        { cle: 'ot_id', libelle: I18n.t('ordres.historique.ot'), rendu: (l) => (l.ot_id ? lienOt(l.ot_id) : '') },
      ],
      lignes: demandes, triInitial: { cle: 'date_heure', sens: 'desc' }, libelle: I18n.t('ordres.historique.demandes_equipement'),
      vide: I18n.t('ordres.historique.aucune_demande_equipement'), surClic: (l) => App.naviguer('#/di/' + encodeURIComponent(l.id)),
    }));
    UI.remplir(panneau, [blocOt, blocDi]);
    UI.$$('.table', panneau).forEach(etiqueterCellules);
  }

  // Onglets affichés par la fiche (ordres-fiche.js) et aide de l'astuce (fenêtre « Clore ») : usage interne au module.
  Object.assign(Ordres.interne, { afficherPreparation, afficherExecution, afficherCompteRendu, afficherHistorique, aideAstuce });

  return {};
})());
