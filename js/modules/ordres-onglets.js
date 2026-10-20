'use strict';
// Ordres (5/6) — contenu des onglets de la fiche OT (ARCHITECTURE.md §14.2) : Préparation (travail,
// technicien et RG8, opérations, pièces prévues et stock RG3), Exécution (check-list, déroulement,
// temps passés), Compte rendu (codes, compte rendu, clôture technique RG4, coût RG7) et Historique
// de l'équipement. Complète l'objet Ordres ; la fiche (ordres-fiche.js) appelle ces onglets par
// Ordres.interne.

Object.assign(Ordres, (() => {

  // Constantes, outils, règles et écritures des fichiers précédents (ordres-regles.js à ordres-fiche.js).
  const { RAPPEL_CONSIGNATION, estVerrouille, verifierHabilitation, piecesManquantes, cout, nomTechnicien } = Ordres;
  const { texte, nombre, arrondi, aujourdhui, estResponsable, estTechnicien, monTechnicienId, equipementDe,
    listeTechniciens, libelleArticle, listeCodes, lignesDeLOt, operationsDe, placerChamp, champOt,
    quantitesPrevues, modifierOt, modifierLieeAOt, journaliserHabilitation, optionsHtml, boutonsTransitions,
    declarerFormulaire, apresEnregistrement, pendant, listeErreursHtml, bandeauHabilitation, enteteOnglet,
    lienOt } = Ordres.interne;

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
      <form class="carte" id="form-preparation" novalidate>
        ${enteteOnglet('Préparation', modifiable ? '' : 'Lecture seule')}
        <fieldset class="ot-fieldset form-grille"${modifiable ? '' : UI.brut(' disabled')}>
          <div class="large" data-place="travail_a_faire"></div>
          <div class="large" data-place="consignes"></div>
          <div data-place="technicien_id"></div><div data-place="date_prevue"></div>
          <div data-place="temps_prevu_h"></div>
          <div class="large ot-zone-habilitation"></div>
        </fieldset>
        ${modifiable ? UI.html`<div class="actions"><span class="espace"></span><button type="submit" class="btn btn-secondaire">${UI.icone('valider')}Enregistrer la préparation</button></div>` : ''}
      </form>
      <div class="carte" id="ot-bloc-operations"></div>
      <div class="carte" id="ot-bloc-pieces"></div>
      ${modifiable && boutonsPreparation.length ? UI.html`<div class="carte ot-actions-preparation sans-impression">
        <p class="aide">Les saisies non enregistrées de cet onglet sont enregistrées avant le changement de statut.</p>
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
        else UI.toast('Préparation enregistrée.', 'succes');
      });
    }
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
    const changes = await pendant(UI.$('button[type=submit]', formulaire), () => modifierOt(ot.id, changements, 'préparation'), 'préparation');
    if (changes === undefined) return false;
    const affectation = changes.includes('technicien_id') || changes.includes('date_prevue');
    const habilitation = verifierHabilitation(ot.equipement_id, valeurs.technicien_id, valeurs.date_prevue);
    if (affectation && habilitation) {
      await journaliserHabilitation(ot.id, habilitation);
      return 'Préparation enregistrée. Avertissement habilitation : ' + habilitation + ' (tracé au journal).';
    }
    return true;
  }

  // --- Opérations (ot_operations) : ajoutables et modifiables, jamais supprimées ---

  function afficherOperationsPreparation(bloc, ot, modifiable) {
    const operations = operationsDe(ot.id);
    UI.remplir(bloc, UI.html`
      ${enteteOnglet('Opérations (' + operations.length + ')', 'Une opération n\'est jamais supprimée.')}
      <form id="form-operations" novalidate>
        <fieldset class="ot-fieldset"${modifiable ? '' : UI.brut(' disabled')}>
          <div class="table-defile"><table class="table ot-table-saisie">
            <thead><tr><th scope="col" class="num">N°</th><th scope="col">Opération</th><th scope="col">Valeur attendue</th></tr></thead>
            <tbody>
              ${operations.map((op) => UI.html`<tr data-operation="${op.id}">
                <td class="num" data-libelle="N°">${op.ordre}</td>
                <td data-libelle="Opération"><input type="text" class="ot-op-libelle" value="${op.operation}" aria-label="Opération ${op.ordre}"></td>
                <td data-libelle="Valeur attendue"><input type="text" class="ot-op-attendu" value="${op.valeur_attendue}" aria-label="Valeur attendue ${op.ordre}"></td></tr>`)}
              ${modifiable ? UI.html`<tr class="ot-nouvelle-ligne"><td class="num" data-libelle="N°">+</td>
                <td data-libelle="Nouvelle opération"><input type="text" name="nouvelle_operation" placeholder="Nouvelle opération" aria-label="Nouvelle opération"></td>
                <td data-libelle="Valeur attendue"><input type="text" name="nouvelle_valeur" placeholder="Valeur attendue (facultatif)" aria-label="Valeur attendue de la nouvelle opération"></td></tr>` : ''}
              ${!modifiable && !operations.length ? UI.html`<tr><td colspan="3" class="vide-table">Aucune opération.</td></tr>` : ''}
            </tbody></table></div>
        </fieldset>
        ${modifiable ? UI.html`<div class="actions"><span class="espace"></span><button type="submit" class="btn btn-secondaire">${UI.icone('valider')}Enregistrer les opérations</button></div>` : ''}
      </form>`);
    if (!modifiable) return;
    const formulaire = UI.$('#form-operations', bloc);
    const enregistrer = () => enregistrerOperations(ot, formulaire);
    declarerFormulaire(formulaire, enregistrer);
    formulaire.addEventListener('submit', async (evenement) => {
      evenement.preventDefault();
      if (await enregistrer()) { formulaire.dataset.modifie = '0'; await apresEnregistrement(); UI.toast('Opérations enregistrées.', 'succes'); }
    });
  }

  async function enregistrerOperations(ot, formulaire) {
    const modifiees = UI.$$('tr[data-operation]', formulaire).map((rangee) => ({
      id: rangee.dataset.operation,
      operation: UI.$('.ot-op-libelle', rangee).value.trim(),
      valeur_attendue: UI.$('.ot-op-attendu', rangee).value.trim(),
    }));
    if (modifiees.some((op) => !op.operation)) {
      UI.toast('Une opération ne peut pas être vidée (elle n\'est jamais supprimée) : corrigez son texte.', 'attention');
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
    }, { action: 'opérations de ' + ot.id }), 'opérations');
    return resultat === true;
  }

  // --- Pièces prévues (ot_pieces) : stock disponible, alerte si insuffisant ; quantité 0 = retirée ---

  function optionsArticles(ot) {
    const liees = new Set(Donnees.lignes('article_equipement').filter((l) => l.equipement_id === ot.equipement_id).map((l) => l.article_id));
    const actifs = Donnees.lignes('articles').filter((a) => a.actif !== '0')
      .sort((a, b) => libelleArticle(a).localeCompare(libelleArticle(b), 'fr'));
    const option = (a) => UI.html`<option value="${a.id}">${libelleArticle(a)} — stock ${UI.nombreFr(Donnees.stockArticle(a.id))}</option>`;
    const pourEquipement = actifs.filter((a) => liees.has(a.id));
    return UI.html`<option value="">— Choisir un article —</option>
      ${pourEquipement.length ? UI.html`<optgroup label="Pièces de cet équipement">${pourEquipement.map(option)}</optgroup>` : ''}
      <optgroup label="Tout le magasin">${actifs.filter((a) => !liees.has(a.id)).map(option)}</optgroup>`;
  }

  /** Quantité du fichier ('1.5') → texte de saisie ('1,5') ; vide → '0'. */
  function quantiteSaisie(valeur) {
    return texte(valeur) === '' ? '0' : texte(valeur).replace('.', ',');
  }

  function afficherPieces(bloc, ot, modifiable) {
    const pieces = lignesDeLOt('ot_pieces', ot.id);
    const cumul = quantitesPrevues(ot.id);
    const manquantes = piecesManquantes(ot.id);
    UI.remplir(bloc, UI.html`
      ${enteteOnglet('Pièces prévues', 'Quantité 0 = pièce retirée (jamais supprimée).')}
      <form id="form-pieces" novalidate>
        <fieldset class="ot-fieldset"${modifiable ? '' : UI.brut(' disabled')}>
          <div class="table-defile"><table class="table ot-table-saisie">
            <thead><tr><th scope="col">Article</th><th scope="col">Emplacement</th><th scope="col" class="num">Prévu</th><th scope="col" class="num">En stock</th><th scope="col">État</th></tr></thead>
            <tbody>
              ${pieces.map((piece) => {
                const article = Donnees.trouver('articles', piece.article_id);
                const stock = Donnees.stockArticle(piece.article_id);
                const retiree = nombre(piece.quantite_prevue) === 0;
                const insuffisant = !retiree && stock < (cumul.get(piece.article_id) || 0);
                return UI.html`<tr data-piece="${piece.id}"${retiree ? UI.brut(' class="attenue"') : ''}>
                  <td data-libelle="Article">${libelleArticle(article) || piece.article_id}</td><td data-libelle="Emplacement">${article ? article.emplacement : ''}</td>
                  <td class="num" data-libelle="Prévu"><input type="text" inputmode="decimal" class="ot-quantite" value="${quantiteSaisie(piece.quantite_prevue)}" aria-label="Quantité prévue de ${libelleArticle(article)}"></td>
                  <td class="num" data-libelle="En stock">${UI.nombreFr(stock)}</td>
                  <td data-libelle="État">${retiree ? UI.html`<span class="badge neutre">retirée</span>` : insuffisant ? UI.html`<span class="badge ko">stock insuffisant</span>` : UI.html`<span class="badge ok">disponible</span>`}</td></tr>`;
              })}
              ${!pieces.length && !modifiable ? UI.html`<tr><td colspan="5" class="vide-table">Aucune pièce prévue.</td></tr>` : ''}
            </tbody></table></div>
          ${modifiable ? UI.html`<div class="form-ligne ot-ajout-piece">
            <div class="champ"><label class="libelle" for="ot-nouvel-article">Ajouter une pièce</label><select id="ot-nouvel-article" name="nouvel_article">${optionsArticles(ot)}</select></div>
            <div class="champ ot-champ-quantite"><label class="libelle" for="ot-nouvelle-quantite">Quantité</label><input type="text" inputmode="decimal" id="ot-nouvelle-quantite" name="nouvelle_quantite" value="1"></div>
          </div>` : ''}
        </fieldset>
        ${modifiable ? UI.html`<div class="actions"><span class="espace"></span><button type="submit" class="btn btn-secondaire">${UI.icone('valider')}Enregistrer les pièces</button></div>` : ''}
      </form>`);
    if (manquantes.length) {
      bloc.insertBefore(UI.bandeau('important', listeErreursHtml('Stock insuffisant : l\'OT ne pourra pas être planifié.',
        manquantes.map((p) => p.libelle + ' : ' + UI.nombreFr(p.prevu) + ' prévu(s), ' + UI.nombreFr(p.stock) + ' en stock'))), UI.$('#form-pieces', bloc));
    }
    if (!modifiable) return;
    const formulaire = UI.$('#form-pieces', bloc);
    const enregistrer = () => enregistrerPieces(ot, formulaire);
    declarerFormulaire(formulaire, enregistrer);
    formulaire.addEventListener('submit', async (evenement) => {
      evenement.preventDefault();
      if (await enregistrer()) { formulaire.dataset.modifie = '0'; await apresEnregistrement(); UI.toast('Pièces prévues enregistrées.', 'succes'); }
    });
  }

  async function enregistrerPieces(ot, formulaire) {
    const quantites = UI.$$('tr[data-piece]', formulaire).map((rangee) => ({ id: rangee.dataset.piece, quantite: UI.enNombre(UI.$('.ot-quantite', rangee).value) }));
    const article = UI.$('[name="nouvel_article"]', formulaire).value;
    const quantiteNouvelle = UI.enNombre(UI.$('[name="nouvelle_quantite"]', formulaire).value);
    if (quantites.some((q) => q.quantite === null || q.quantite < 0) || (article && (quantiteNouvelle === null || quantiteNouvelle <= 0))) {
      UI.toast('Quantités : saisissez des nombres positifs (0 pour retirer une pièce).', 'attention');
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
    }, { action: 'pièces prévues de ' + ot.id }), 'pièces prévues');
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
        <p>${ot.statut === 'En attente' ? 'L\'OT est en attente : reprenez-le quand la cause est levée.' : 'L\'intervention n\'a pas commencé. « Démarrer » inscrit l\'heure de début.'}</p>
        <div class="actions">${demarrage}</div></div>` : ''}
      <form class="carte" id="form-execution" novalidate>
        ${enteteOnglet('Exécution', modifiable ? '' : (ot.statut === 'Créé' || ot.statut === 'Préparé' || ot.statut === 'Planifié' ? 'Disponible une fois l\'OT démarré' : 'Lecture seule'))}
        <fieldset class="ot-fieldset"${modifiable ? '' : UI.brut(' disabled')}>
          <h3 class="ot-sous-titre">Check-list</h3>
          ${operations.length ? UI.html`<ul class="check-liste">${operations.map((op) => UI.html`
            <li data-operation="${op.id}"${op.fait === '1' ? UI.brut(' class="fait"') : ''}>
              <label class="case"><input type="checkbox" class="ot-fait"${op.fait === '1' ? UI.brut(' checked') : ''}>
                <span><span class="operation">${op.ordre}. ${op.operation}</span>${op.valeur_attendue ? UI.html`<span class="attendu">Attendu : ${op.valeur_attendue}</span>` : ''}</span></label>
              <input type="text" class="mesure ot-mesure" value="${op.valeur_mesuree}" placeholder="Valeur mesurée" aria-label="Valeur mesurée pour l'opération ${op.ordre}">
            </li>`)}</ul>` : UI.html`<p class="muted">Aucune opération prévue (onglet Préparation).</p>`}
          <h3 class="ot-sous-titre">Déroulement</h3>
          <div class="form-grille">
            <div class="champ ot-champ-lu"><span class="libelle">Début</span><p class="ot-valeur">${UI.dateHeureFr(ot.date_debut) || '—'}</p></div>
            <div class="ot-date-fin" data-place="date_fin"></div>
            <div data-place="arret_production"></div><div data-place="duree_arret_h"></div>
            <div data-place="cout_soustraitance"></div>
          </div>
        </fieldset>
        ${modifiable ? UI.html`<div class="actions"><span class="espace"></span><button type="submit" class="btn btn-secondaire">${UI.icone('valider')}Enregistrer l'exécution</button></div>` : ''}
      </form>
      <div class="carte" id="ot-bloc-temps"></div>`);
    const formulaire = UI.$('#form-execution', panneau);
    const placer = (nom, element) => placerChamp(formulaire, nom, element);
    placer('date_fin', champOt('date_fin', ot.date_fin));
    placer('arret_production', champOt('arret_production', ot.arret_production, { libelle: 'Arrêt de production pendant l\'intervention' }));
    placer('duree_arret_h', champOt('duree_arret_h', ot.duree_arret_h));
    placer('cout_soustraitance', champOt('cout_soustraitance', ot.cout_soustraitance, { libelle: 'Coût de sous-traitance (€)' }));
    if (modifiable) {
      const blocDateFin = UI.$('[data-champ="date_fin"]', formulaire);
      const maintenant = UI.element(UI.html`<button type="button" class="lien-bouton ot-maintenant">Maintenant</button>`);
      maintenant.addEventListener('click', () => {
        UI.$('[name="date_fin"]', blocDateFin).value = Donnees.maintenant().replace(' ', 'T');
        formulaire.dataset.modifie = '1';
        App.marquerSaisie(true);
      });
      UI.$('.libelle', blocDateFin).appendChild(maintenant);
      const enregistrer = () => enregistrerExecution(ot, formulaire);
      declarerFormulaire(formulaire, enregistrer);
      formulaire.addEventListener('submit', async (evenement) => {
        evenement.preventDefault();
        if (await enregistrer()) { formulaire.dataset.modifie = '0'; await apresEnregistrement(); UI.toast('Exécution enregistrée.', 'succes'); }
      });
    }
    afficherTemps(UI.$('#ot-bloc-temps', panneau), ot, modifiable);
  }

  async function enregistrerExecution(ot, formulaire) {
    if (UI.verifierFormulaire(formulaire).length) return false;
    const valeurs = UI.lireFormulaire(formulaire);
    const checkListe = UI.$$('li[data-operation]', formulaire).map((li) => ({
      id: li.dataset.operation, fait: UI.$('.ot-fait', li).checked ? '1' : '0', valeur_mesuree: UI.$('.ot-mesure', li).value.trim(),
    }));
    const bouton = UI.$('button[type=submit]', formulaire);
    const changes = await pendant(bouton, () => modifierOt(ot.id, {
      date_fin: valeurs.date_fin, arret_production: valeurs.arret_production,
      duree_arret_h: valeurs.duree_arret_h, cout_soustraitance: valeurs.cout_soustraitance,
    }, 'exécution'), 'exécution');
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
      ${enteteOnglet('Temps passés', 'Total : ' + UI.heures(total))}
      <div class="table-defile"><table class="table">
        <thead><tr><th scope="col">Date</th><th scope="col">Technicien</th><th scope="col" class="num">Heures</th></tr></thead>
        <tbody>${temps.length ? temps.map((ligne) => UI.html`<tr><td>${UI.dateFr(ligne.date)}</td><td>${nomTechnicien(ligne.technicien_id)}</td><td class="num">${UI.heures(ligne.heures)}</td></tr>`)
          : UI.html`<tr><td colspan="3" class="vide-table">Aucun temps saisi.</td></tr>`}</tbody>
      </table></div>
      ${modifiable ? UI.html`<form class="form-ligne ot-ajout-temps" id="form-temps" novalidate>
        <div class="champ"><label class="libelle" for="ot-temps-technicien">Technicien</label>
          <select id="ot-temps-technicien" name="technicien_id">${optionsHtml(listeTechniciens(technicienParDefaut), technicienParDefaut)}</select></div>
        <div class="champ"><label class="libelle" for="ot-temps-date">Date</label><input type="date" id="ot-temps-date" name="date" value="${aujourdhui()}"></div>
        <div class="champ ot-champ-quantite"><label class="libelle" for="ot-temps-heures">Heures</label><input type="text" inputmode="decimal" id="ot-temps-heures" name="heures" placeholder="1,5"></div>
        <button type="submit" class="btn btn-secondaire">${UI.icone('ajouter')}Ajouter le temps</button>
      </form>` : ''}`);
    if (!modifiable) return;
    const formulaire = UI.$('#form-temps', bloc);
    // Avant une transition, un temps saisi mais pas encore ajouté est ajouté ; un champ vide est ignoré.
    declarerFormulaire(formulaire, () => ajouterTemps(ot, formulaire, false));
    formulaire.addEventListener('submit', async (evenement) => {
      evenement.preventDefault();
      if (await ajouterTemps(ot, formulaire, true)) { formulaire.dataset.modifie = '0'; await apresEnregistrement(); UI.toast('Temps ajouté.', 'succes'); }
    });
  }

  async function ajouterTemps(ot, formulaire, depuisLeBouton) {
    const valeurs = UI.lireFormulaire(formulaire);
    const heures = UI.enNombre(valeurs.heures);
    if (!valeurs.heures && !depuisLeBouton) return true;   // rien à ajouter
    if (heures === null || heures <= 0 || heures > 24 || !valeurs.date || !valeurs.technicien_id) {
      UI.toast('Temps passé : choisissez le technicien, la date et un nombre d\'heures entre 0 et 24 (ex. 1,5).', 'attention');
      return false;
    }
    const resultat = await pendant(UI.$('button[type=submit]', formulaire), () => modifierLieeAOt(ot.id, 'ot_temps', (lignes, outils) => {
      lignes.push({ id: outils.nouvelId(lignes), ot_id: ot.id, technicien_id: valeurs.technicien_id, date: valeurs.date, heures: String(heures) });
      return true;
    }, { action: 'temps passé sur ' + ot.id }), 'temps passé');
    return resultat === true;
  }

  // ===========================================================================================
  // 9. Onglet Compte rendu : codes, compte rendu, remise en service, clôture technique, coût RG7
  // ===========================================================================================

  function afficherCompteRendu(panneau, ot) {
    const modifiable = peutExecuter(ot);
    const equipement = equipementDe(ot);
    UI.remplir(panneau, UI.html`
      <form class="carte" id="form-compte-rendu" novalidate>
        ${enteteOnglet('Compte rendu', modifiable ? '' : 'Lecture seule')}
        <fieldset class="ot-fieldset form-grille"${modifiable ? '' : UI.brut(' disabled')}>
          <div data-place="symptome_code"></div><div data-place="cause_code"></div><div data-place="remede_code"></div><div></div>
          <div class="large" data-place="compte_rendu"></div>
          <div class="large ot-remise" data-place="remise_service"></div>
        </fieldset>
        ${modifiable ? UI.html`<div class="actions"><button type="submit" class="btn btn-secondaire">${UI.icone('valider')}Enregistrer le compte rendu</button>
          <span class="espace"></span>${boutonsTransitions(ot, ['Clôturé techniquement'])}</div>` : ''}
      </form>
      <div class="carte ot-cout" id="ot-cout"></div>`);
    const formulaire = UI.$('#form-compte-rendu', panneau);
    const placer = (nom, element) => placerChamp(formulaire, nom, element);
    placer('symptome_code', champOt('symptome_code', ot.symptome_code, { liste: listeCodes('symptôme') }));
    placer('cause_code', champOt('cause_code', ot.cause_code, { liste: listeCodes('cause') }));
    placer('remede_code', champOt('remede_code', ot.remede_code, { liste: listeCodes('remède') }));
    placer('compte_rendu', champOt('compte_rendu', ot.compte_rendu, {
      aide: 'Ce qui a été constaté, la cause, ce qui a été fait (10 caractères au moins ; « RAS » refusé sur un correctif).',
    }));
    placer('remise_service', champOt('remise_service', ot.remise_service, {
      libelle: 'Équipement remis en service en sécurité (protections remises, consignation levée, production prévenue)',
    }));
    if (equipement && texte(equipement.habilitation_requise)) {
      UI.$('.ot-remise', formulaire).appendChild(UI.element(UI.html`<p class="aide">${RAPPEL_CONSIGNATION}</p>`));
    }
    if (modifiable) {
      const enregistrer = () => enregistrerCompteRendu(ot, formulaire);
      declarerFormulaire(formulaire, enregistrer);
      formulaire.addEventListener('submit', async (evenement) => {
        evenement.preventDefault();
        if (await enregistrer()) { formulaire.dataset.modifie = '0'; await apresEnregistrement(); UI.toast('Compte rendu enregistré.', 'succes'); }
      });
    }
    afficherCout(UI.$('#ot-cout', panneau), ot);
  }

  async function enregistrerCompteRendu(ot, formulaire) {
    const valeurs = UI.lireFormulaire(formulaire);
    const changes = await pendant(UI.$('button[type=submit]', formulaire), () => modifierOt(ot.id, {
      symptome_code: valeurs.symptome_code, cause_code: valeurs.cause_code, remede_code: valeurs.remede_code,
      compte_rendu: valeurs.compte_rendu, remise_service: valeurs.remise_service,
    }, 'compte rendu'), 'compte rendu');
    return changes !== undefined;
  }

  function afficherCout(bloc, ot) {
    const resultat = cout(ot);
    const detail = resultat.detail;
    UI.remplir(bloc, UI.html`
      ${enteteOnglet('Coût de l\'intervention', 'RG7 : main-d\'œuvre + pièces sorties − retours + sous-traitance')}
      <div class="lignes ot-lignes-cout">
        <span>Main-d'œuvre (${UI.heures(detail.nombreHeures)})</span><b>${UI.euro(resultat.heures)}</b>
        <span>Pièces sorties pour l'OT</span><b>${UI.euro(resultat.pieces)}</b>
        <span>Sous-traitance</span><b>${UI.euro(resultat.soustraitance)}</b>
        <span class="total">Total</span><b class="total" id="ot-cout-total">${UI.euro(resultat.total)}</b>
      </div>
      <details class="vue-tableau ot-detail-cout"><summary>Voir le détail</summary>
        <div class="table-defile"><table class="table">
          <thead><tr><th scope="col">Poste</th><th scope="col">Détail</th><th scope="col" class="num">Montant</th></tr></thead>
          <tbody>
            ${detail.temps.map((t) => UI.html`<tr><td>${nomTechnicien(t.technicien_id)}</td><td>${UI.dateFr(t.date)} · ${UI.heures(t.heures)} × ${UI.euro(t.taux)}/h</td><td class="num">${UI.euro(t.montant)}</td></tr>`)}
            ${detail.pieces.map((p) => UI.html`<tr><td>${p.libelle}</td><td>${UI.nombreFr(p.sorties)} sortie(s)${p.retours ? UI.html` − ${UI.nombreFr(p.retours)} retour(s)` : ''} × ${UI.euro(p.prix)}</td><td class="num">${UI.euro(p.montant)}</td></tr>`)}
            ${resultat.soustraitance ? UI.html`<tr><td>Sous-traitance</td><td></td><td class="num">${UI.euro(resultat.soustraitance)}</td></tr>` : ''}
            ${!detail.temps.length && !detail.pieces.length && !resultat.soustraitance ? UI.html`<tr><td colspan="3" class="vide-table">Aucun coût pour l'instant.</td></tr>` : ''}
          </tbody></table></div>
        <p class="note">Les sorties de pièces imputées à l'OT se saisissent au magasin (lot 2) ; les quantités prévues ne sont pas comptées.</p>
      </details>`);
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
    const blocOt = UI.element(UI.html`<section class="carte"><div class="entete-carte"><h2>Autres ordres de travail (${autres.length})</h2></div></section>`);
    blocOt.appendChild(UI.tableau({
      colonnes: [
        { cle: 'id', libelle: 'N°', rendu: (l) => lienOt(l.id) },
        { cle: 'date_creation', libelle: 'Créé le', rendu: (l) => UI.dateFr(l.date_creation) },
        { cle: 'priorite', libelle: 'Priorité', rendu: (l) => UI.badgePriorite(l.priorite) },
        { cle: 'statut', libelle: 'Statut', rendu: (l) => UI.badgeStatut(l.statut) },
        { cle: 'type', libelle: 'Type' },
        { cle: 'titre', libelle: 'Titre' },
      ],
      lignes: autres, triInitial: { cle: 'date_creation', sens: 'desc' }, libelle: 'Autres OT de l\'équipement',
      vide: 'Aucun autre OT sur cet équipement.', surClic: (l) => App.naviguer('#/ot/' + encodeURIComponent(l.id)),
    }));
    const blocDi = UI.element(UI.html`<section class="carte"><div class="entete-carte"><h2>Demandes d'intervention (${demandes.length})</h2></div></section>`);
    blocDi.appendChild(UI.tableau({
      colonnes: [
        { cle: 'id', libelle: 'N°', rendu: (l) => UI.html`<a href="#/di/${encodeURIComponent(l.id)}">${l.id}</a>` },
        { cle: 'date_heure', libelle: 'Date', rendu: (l) => UI.dateFr(l.date_heure) },
        { cle: 'symptome', libelle: 'Symptôme' },
        { cle: 'impact', libelle: 'Impact' },
        { cle: 'statut', libelle: 'Statut', rendu: (l) => UI.badgeStatut(l.statut) },
        { cle: 'ot_id', libelle: 'OT', rendu: (l) => (l.ot_id ? lienOt(l.ot_id) : '') },
      ],
      lignes: demandes, triInitial: { cle: 'date_heure', sens: 'desc' }, libelle: 'Demandes de l\'équipement',
      vide: 'Aucune demande sur cet équipement.', surClic: (l) => App.naviguer('#/di/' + encodeURIComponent(l.id)),
    }));
    UI.remplir(panneau, [blocOt, blocDi]);
    UI.$$('.table', panneau).forEach(etiqueterCellules);
  }

  // Onglets affichés par la fiche (ordres-fiche.js) : usage interne au module.
  Object.assign(Ordres.interne, { afficherPreparation, afficherExecution, afficherCompteRendu, afficherHistorique });

  return {};
})());
