'use strict';
// Ordres (6/7) — bloc « Pièces sorties » de l'onglet Exécution (ARCHITECTURE.md §14.4 et §14.6,
// RG6) : pièces sorties du magasin pour l'OT (sorti, retourné, net, prix, montant), « Sortir une
// pièce » (les pièces prévues de l'OT en tête, puis les articles actifs avec leur stock) et
// « Retourner » (pas plus que le net sorti).
// Les écritures sont celles du magasin : Magasin.sortir et Magasin.retourner contrôlent le stock
// sur les lignes fraîches et refusent par Donnees.ErreurValidation (« Stock insuffisant : 3 en
// stock, 5 demandé ») ; ce refus est affiché tel quel dans le bloc. Le coût RG7 de l'onglet Compte
// rendu (Ordres.cout) compte ces mouvements : il est à jour au réaffichage de la fiche.
// Complète l'objet Ordres ; l'onglet Exécution (ordres-onglets.js) appelle ce bloc par Ordres.interne.

Object.assign(Ordres, (() => {

  // Règles et outils des fichiers précédents (ordres-regles.js à ordres-onglets.js).
  const { estOuvert } = Ordres;
  const { texte, nombre, estResponsable, estTechnicien, libelleArticle, quantitesPrevues, enteteOnglet,
    apresEnregistrement } = Ordres.interne;

  // ===========================================================================================
  // 13. Pièces sorties (onglet Exécution) : sorties et retours imputés à l'OT (RG6)
  // ===========================================================================================

  /** Sortir et retourner : technicien ou responsable, OT ni clôturé ni annulé (ni donc verrouillé). */
  function peutSortir(ot) {
    return (estTechnicien() || estResponsable()) && estOuvert(ot);
  }

  /** Quantité affichée dans un champ de saisie : 1.5 → '1,5'. */
  function quantiteSaisie(valeur) {
    return String(valeur).replace('.', ',');
  }

  /**
   * Lignes du bloc : Magasin.sortiesDeLOt ({ articleId, sorti, retourne, net }) complété de
   * l'article, de son libellé, de son prix unitaire et du montant (net × prix, comme RG7).
   */
  function lignesSorties(otId) {
    return Magasin.sortiesDeLOt(otId).map((ligne) => {
      const article = Donnees.trouver('articles', ligne.articleId);
      const prix = nombre(article && article.prix_unitaire);
      return Object.assign({ libelle: libelleArticle(article) || ligne.articleId, prix, montant: ligne.net * prix }, ligne);
    });
  }

  // Pourquoi le bloc est en lecture seule (aucun bouton).
  function raisonLectureSeule(ot) {
    if (!estOuvert(ot)) return I18n.t('ordres.raison_lecture_seule.ot_plus_aucune_sortie', { otStatut: Schema.libelleValeur('ordres_travail', 'statut', ot.statut) });
    return I18n.t('ordres.raison_lecture_seule.sorties_retours_sont_saisis');
  }

  function tableauSortiesHtml(lignes, modifiable) {
    return UI.html`<div class="table-defile"><table class="table ot-table-empilee ot-table-sorties">
      <thead><tr><th scope="col">${I18n.t('commun.champ.article')}</th><th scope="col" class="num">${I18n.t('ordres.tableau_sorties.sorti')}</th><th scope="col" class="num">${I18n.t('ordres.tableau_sorties.retourne')}</th>
        <th scope="col" class="num">${I18n.t('ordres.tableau_sorties.net')}</th><th scope="col" class="num">${I18n.t('commun.champ.prix_unitaire')}</th><th scope="col" class="num">${I18n.t('ordres.tableau_sorties.montant')}</th>
        ${modifiable ? UI.html`<th scope="col"><span class="visuellement-cache">${I18n.t('ordres.tableau_sorties.retour')}</span></th>` : ''}</tr></thead>
      <tbody>
        ${lignes.map((ligne) => UI.html`<tr data-article="${ligne.articleId}">
          <td data-libelle="${I18n.t('commun.champ.article')}">${ligne.libelle}</td>
          <td class="num" data-libelle="${I18n.t('ordres.tableau_sorties.sorti')}">${UI.nombreFr(ligne.sorti)}</td>
          <td class="num" data-libelle="${I18n.t('ordres.tableau_sorties.retourne')}">${UI.nombreFr(ligne.retourne)}</td>
          <td class="num" data-libelle="${I18n.t('ordres.tableau_sorties.net')}"><b>${UI.nombreFr(ligne.net)}</b></td>
          <td class="num" data-libelle="${I18n.t('commun.champ.prix_unitaire')}">${UI.euro(ligne.prix)}</td>
          <td class="num" data-libelle="${I18n.t('ordres.tableau_sorties.montant')}">${UI.euro(ligne.montant)}</td>
          ${modifiable ? UI.html`<td class="ot-action-ligne">${ligne.net > 0
            ? UI.html`<button type="button" class="btn btn-secondaire ot-retourner" data-article="${ligne.articleId}">${UI.icone('retour')}${I18n.t('ordres.tableau_sorties.retourner')}</button>` : ''}</td>` : ''}
        </tr>`)}
        ${lignes.length ? '' : UI.html`<tr><td colspan="${modifiable ? 7 : 6}" class="vide-table">${I18n.t('ordres.tableau_sorties.aucune_piece_sortie_ot')}</td></tr>`}
      </tbody></table></div>`;
  }

  /**
   * Articles proposés à la sortie : les pièces prévues de l'OT d'abord (la première est choisie),
   * puis les autres articles actifs du magasin, chacun avec son stock.
   */
  function optionsSortie(ot) {
    const prevues = quantitesPrevues(ot.id);                   // Map article → quantité prévue (> 0)
    const stock = (article) => UI.nombreFr(Donnees.stockArticle(article.id));
    const articlesPrevus = Array.from(prevues.keys()).map((id) => Donnees.trouver('articles', id)).filter(Boolean);
    const autres = Donnees.lignes('articles').filter((a) => texte(a.actif) !== '0' && !prevues.has(a.id))
      .sort((a, b) => libelleArticle(a).localeCompare(libelleArticle(b), 'fr'));
    return UI.html`<option value=""${articlesPrevus.length ? '' : UI.brut(' selected')}>${I18n.t('ordres.options_sortie.choisir_article')}</option>
      ${articlesPrevus.length ? UI.html`<optgroup label="${I18n.t('ordres.options_sortie.pieces_prevues_ot')}">${articlesPrevus.map((a, rang) => UI.html`
        <option value="${a.id}"${rang === 0 ? UI.brut(' selected') : ''}>${I18n.t('ordres.options_sortie.prevu_stock', { libelleArticle: libelleArticle(a), prevu: UI.nombreFr(prevues.get(a.id)), stock: stock(a) })}</option>`)}</optgroup>` : ''}
      <optgroup label="${I18n.t('ordres.options_sortie.articles_magasin')}">${autres.map((a) => UI.html`<option value="${a.id}">${I18n.t('ordres.options_sortie.libelle_article_stock_stock', { libelleArticle: libelleArticle(a), stock: stock(a) })}</option>`)}</optgroup>`;
  }

  function formulaireSortieHtml(ot) {
    return UI.html`<h3 class="ot-sous-titre">${I18n.t('ordres.formulaire_sortie.sortir_piece')}</h3>
      <form class="form-ligne ot-sortie" id="form-sortie" novalidate>
        <div class="champ ot-champ-article"><label class="libelle" for="ot-sortie-article">${I18n.t('commun.champ.article')}</label>
          <select id="ot-sortie-article" name="article_id">${optionsSortie(ot)}</select></div>
        <div class="champ ot-champ-quantite"><label class="libelle" for="ot-sortie-quantite">${I18n.t('commun.champ.quantite')}</label>
          <input type="text" inputmode="decimal" id="ot-sortie-quantite" name="quantite" value="1"></div>
        <div class="champ ot-champ-commentaire"><label class="libelle" for="ot-sortie-commentaire">${I18n.t('commun.champ.commentaire')}</label>
          <input type="text" id="ot-sortie-commentaire" name="commentaire" maxlength="200" placeholder="${I18n.t('ordres.formulaire_sortie.facultatif')}"></div>
        <button type="submit" class="btn btn-secondaire">${UI.icone('magasin')}${I18n.t('ordres.formulaire_sortie.sortir_stock')}</button>
      </form>`;
  }

  /** Affiche le bloc « Pièces sorties » de l'OT dans `bloc` (carte de l'onglet Exécution). */
  function afficherPiecesSorties(bloc, ot) {
    const modifiable = peutSortir(ot);
    const lignes = lignesSorties(ot.id);
    const total = lignes.reduce((somme, ligne) => somme + ligne.montant, 0);
    UI.remplir(bloc, UI.html`
      ${enteteOnglet(I18n.t('ordres.pieces_sorties.pieces_sorties'), I18n.t('ordres.pieces_sorties.sorties_magasin_imputees_ot'))}
      <div class="ot-sorties-message"></div>
      ${tableauSortiesHtml(lignes, modifiable)}
      ${lignes.length ? UI.html`<p class="ot-sorties-total">${I18n.html('ordres.pieces_sorties.montant_pieces_net', { euro: UI.euro(total) })}</p>` : ''}
      ${modifiable ? formulaireSortieHtml(ot) : UI.html`<p class="note ot-sorties-lecture">${raisonLectureSeule(ot)}</p>`}`);
    if (!modifiable) return;
    const formulaire = UI.$('#form-sortie', bloc);
    formulaire.addEventListener('submit', (evenement) => {
      evenement.preventDefault();
      sortirPiece(ot, formulaire, bloc);
    });
    bloc.addEventListener('click', (evenement) => {
      const bouton = evenement.target.closest('button.ot-retourner');
      const ligne = bouton && lignes.find((l) => l.articleId === bouton.dataset.article);
      if (ligne) demanderRetour(ot, ligne, bloc, bouton);
    });
  }

  // --- Messages et écritures ------------------------------------------------------------------

  /** Message du bloc (refus RG6 affiché tel quel) ; texte vide = message effacé. */
  function messageBloc(bloc, message) {
    const zone = UI.$('.ot-sorties-message', bloc);
    zone.textContent = '';
    if (message) zone.appendChild(UI.bandeau('important', message));
  }

  /**
   * Exécute une écriture du magasin, bouton désactivé pendant l'action. Un refus
   * (ErreurValidation : stock insuffisant, retour au-delà du net, OT clôturé ailleurs…) s'affiche
   * dans le bloc ; une autre erreur (conflit, stockage) passe par App.signalerErreur.
   * Renvoie true si l'écriture a réussi.
   */
  async function ecrireMouvement(bloc, bouton, action, contexte) {
    messageBloc(bloc, '');
    if (bouton) bouton.disabled = true;
    try {
      await action();
      return true;
    } catch (erreur) {
      if (erreur instanceof Donnees.ErreurValidation) {
        messageBloc(bloc, erreur.message);
        console.warn('Prévo (' + contexte + ') : ' + erreur.message);
      } else {
        App.signalerErreur(erreur, contexte);
      }
      return false;
    } finally {
      if (bouton && document.contains(bouton)) bouton.disabled = false;
    }
  }

  /** « Sortir du stock » : Magasin.sortir(ot, article, quantité, commentaire), puis fiche réaffichée. */
  async function sortirPiece(ot, formulaire, bloc) {
    const valeurs = UI.lireFormulaire(formulaire);
    const quantite = UI.enNombre(valeurs.quantite);
    if (!valeurs.article_id) { messageBloc(bloc, I18n.t('ordres.sortir_piece.choisissez_article_sortir')); return; }
    if (quantite === null || quantite <= 0) { messageBloc(bloc, I18n.t('ordres.sortir_piece.saisissez_quantite_superieure_0')); return; }
    const article = Donnees.trouver('articles', valeurs.article_id);
    const reussi = await ecrireMouvement(bloc, UI.$('button[type=submit]', formulaire),
      () => Magasin.sortir(ot.id, valeurs.article_id, quantite, valeurs.commentaire), I18n.t('ordres.sortir_piece.sortie_stock'));
    if (!reussi) return;
    await apresEnregistrement();
    UI.toast(I18n.t('ordres.sortir_piece.sortie_enregistree', { quantite: UI.nombreFr(quantite), libelle: (libelleArticle(article) || valeurs.article_id), otId: ot.id }), 'succes');
  }

  /**
   * « Retourner » : fenêtre (quantité, 1 par défaut ou le net s'il est plus petit ; commentaire),
   * puis Magasin.retourner, qui refuse plus que le net sorti pour cet OT.
   */
  async function demanderRetour(ot, ligne, bloc, bouton) {
    const idQuantite = UI.identifiantUnique('ot-retour-quantite');
    const idCommentaire = UI.identifiantUnique('ot-retour-commentaire');
    const contenu = UI.element(UI.html`<div class="form-colonne ot-fenetre-retour">
      <p>${I18n.t('ordres.demander_retour.sorti_retours_deduits', { n: ligne.net, ligneLibelle: ligne.libelle, net: UI.nombreFr(ligne.net), otId: ot.id })}</p>
      <div class="champ"><label class="libelle" for="${idQuantite}">${I18n.t('ordres.demander_retour.quantite_rendue_magasin')}</label>
        <input type="text" inputmode="decimal" id="${idQuantite}" name="quantite" value="${quantiteSaisie(Math.min(1, ligne.net))}">
        <p class="erreur-champ" hidden></p></div>
      <div class="champ"><label class="libelle" for="${idCommentaire}">${I18n.t('commun.champ.commentaire')}</label>
        <input type="text" id="${idCommentaire}" name="commentaire" maxlength="200" placeholder="${I18n.t('ordres.demander_retour.facultatif_ex_piece_non')}"></div>
    </div>`);
    const champQuantite = UI.$('[name="quantite"]', contenu);
    const choix = await UI.fenetre({
      titre: I18n.t('ordres.demander_retour.retourner_piece', { otId: ot.id }), contenu,
      boutons: [{ libelle: I18n.t('commun.bouton.annuler'), valeur: null, classe: 'btn-fantome' },
        { libelle: I18n.t('ordres.demander_retour.retourner_magasin'), valeur: 'ok', classe: 'btn-primaire', defaut: true }],
      avantFermeture() {
        const quantite = UI.enNombre(champQuantite.value);
        const erreur = UI.$('.erreur-champ', contenu);
        erreur.textContent = quantite === null || quantite <= 0 ? I18n.t('ordres.demander_retour.saisissez_quantite_superieure_0') : '';
        erreur.hidden = !erreur.textContent;
        return !erreur.textContent;
      },
    });
    if (choix !== 'ok') return;
    const quantite = UI.enNombre(champQuantite.value);
    const commentaire = UI.$('[name="commentaire"]', contenu).value.trim();
    const reussi = await ecrireMouvement(bloc, bouton,
      () => Magasin.retourner(ot.id, ligne.articleId, quantite, commentaire), I18n.t('ordres.demander_retour.retour_stock'));
    if (!reussi) return;
    await apresEnregistrement();
    UI.toast(I18n.t('ordres.demander_retour.retour_enregistre_rendu_magasin', { n: quantite, libelle: ligne.libelle, quantite: UI.nombreFr(quantite) }), 'succes');
  }

  // Bloc affiché par l'onglet Exécution (ordres-onglets.js) : usage interne au module.
  Object.assign(Ordres.interne, { afficherPiecesSorties });

  return {};
})());
