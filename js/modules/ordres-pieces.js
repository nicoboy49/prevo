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
    if (!estOuvert(ot)) return 'OT « ' + ot.statut + ' » : plus aucune sortie ni aucun retour ne peut lui être imputé.';
    return 'Les sorties et les retours sont saisis par le technicien ou le responsable.';
  }

  function tableauSortiesHtml(lignes, modifiable) {
    return UI.html`<div class="table-defile"><table class="table ot-table-empilee ot-table-sorties">
      <thead><tr><th scope="col">Article</th><th scope="col" class="num">Sorti</th><th scope="col" class="num">Retourné</th>
        <th scope="col" class="num">Net</th><th scope="col" class="num">Prix unitaire</th><th scope="col" class="num">Montant</th>
        ${modifiable ? UI.html`<th scope="col"><span class="visuellement-cache">Retour</span></th>` : ''}</tr></thead>
      <tbody>
        ${lignes.map((ligne) => UI.html`<tr data-article="${ligne.articleId}">
          <td data-libelle="Article">${ligne.libelle}</td>
          <td class="num" data-libelle="Sorti">${UI.nombreFr(ligne.sorti)}</td>
          <td class="num" data-libelle="Retourné">${UI.nombreFr(ligne.retourne)}</td>
          <td class="num" data-libelle="Net"><b>${UI.nombreFr(ligne.net)}</b></td>
          <td class="num" data-libelle="Prix unitaire">${UI.euro(ligne.prix)}</td>
          <td class="num" data-libelle="Montant">${UI.euro(ligne.montant)}</td>
          ${modifiable ? UI.html`<td class="ot-action-ligne">${ligne.net > 0
            ? UI.html`<button type="button" class="btn btn-secondaire ot-retourner" data-article="${ligne.articleId}">${UI.icone('retour')}Retourner</button>` : ''}</td>` : ''}
        </tr>`)}
        ${lignes.length ? '' : UI.html`<tr><td colspan="${modifiable ? 7 : 6}" class="vide-table">Aucune pièce sortie pour cet OT.</td></tr>`}
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
    return UI.html`<option value=""${articlesPrevus.length ? '' : UI.brut(' selected')}>— Choisir un article —</option>
      ${articlesPrevus.length ? UI.html`<optgroup label="Pièces prévues pour cet OT">${articlesPrevus.map((a, rang) => UI.html`
        <option value="${a.id}"${rang === 0 ? UI.brut(' selected') : ''}>${libelleArticle(a)} — prévu ${UI.nombreFr(prevues.get(a.id))} · stock ${stock(a)}</option>`)}</optgroup>` : ''}
      <optgroup label="Articles du magasin">${autres.map((a) => UI.html`<option value="${a.id}">${libelleArticle(a)} — stock ${stock(a)}</option>`)}</optgroup>`;
  }

  function formulaireSortieHtml(ot) {
    return UI.html`<h3 class="ot-sous-titre">Sortir une pièce</h3>
      <form class="form-ligne ot-sortie" id="form-sortie" novalidate>
        <div class="champ ot-champ-article"><label class="libelle" for="ot-sortie-article">Article</label>
          <select id="ot-sortie-article" name="article_id">${optionsSortie(ot)}</select></div>
        <div class="champ ot-champ-quantite"><label class="libelle" for="ot-sortie-quantite">Quantité</label>
          <input type="text" inputmode="decimal" id="ot-sortie-quantite" name="quantite" value="1"></div>
        <div class="champ ot-champ-commentaire"><label class="libelle" for="ot-sortie-commentaire">Commentaire</label>
          <input type="text" id="ot-sortie-commentaire" name="commentaire" maxlength="200" placeholder="Facultatif"></div>
        <button type="submit" class="btn btn-secondaire">${UI.icone('magasin')}Sortir du stock</button>
      </form>`;
  }

  /** Affiche le bloc « Pièces sorties » de l'OT dans `bloc` (carte de l'onglet Exécution). */
  function afficherPiecesSorties(bloc, ot) {
    const modifiable = peutSortir(ot);
    const lignes = lignesSorties(ot.id);
    const total = lignes.reduce((somme, ligne) => somme + ligne.montant, 0);
    UI.remplir(bloc, UI.html`
      ${enteteOnglet('Pièces sorties', 'Sorties du magasin imputées à l\'OT, retours déduits (RG6) ; comptées dans le coût.')}
      <div class="ot-sorties-message"></div>
      ${tableauSortiesHtml(lignes, modifiable)}
      ${lignes.length ? UI.html`<p class="ot-sorties-total">Montant des pièces (net) : <b id="ot-sorties-total">${UI.euro(total)}</b></p>` : ''}
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
    if (!valeurs.article_id) { messageBloc(bloc, 'Choisissez l\'article à sortir.'); return; }
    if (quantite === null || quantite <= 0) { messageBloc(bloc, 'Saisissez une quantité supérieure à 0 (ex. 1 ou 2,5).'); return; }
    const article = Donnees.trouver('articles', valeurs.article_id);
    const reussi = await ecrireMouvement(bloc, UI.$('button[type=submit]', formulaire),
      () => Magasin.sortir(ot.id, valeurs.article_id, quantite, valeurs.commentaire), 'sortie de stock');
    if (!reussi) return;
    await apresEnregistrement();
    UI.toast('Sortie enregistrée : ' + UI.nombreFr(quantite) + ' × ' + (libelleArticle(article) || valeurs.article_id) + ' pour ' + ot.id + '.', 'succes');
  }

  /**
   * « Retourner » : fenêtre (quantité, 1 par défaut ou le net s'il est plus petit ; commentaire),
   * puis Magasin.retourner, qui refuse plus que le net sorti pour cet OT.
   */
  async function demanderRetour(ot, ligne, bloc, bouton) {
    const idQuantite = UI.identifiantUnique('ot-retour-quantite');
    const idCommentaire = UI.identifiantUnique('ot-retour-commentaire');
    const contenu = UI.element(UI.html`<div class="form-colonne ot-fenetre-retour">
      <p>${ligne.libelle} : ${UI.nombreFr(ligne.net)} sorti(s) pour ${ot.id}, retours déduits.</p>
      <div class="champ"><label class="libelle" for="${idQuantite}">Quantité rendue au magasin</label>
        <input type="text" inputmode="decimal" id="${idQuantite}" name="quantite" value="${quantiteSaisie(Math.min(1, ligne.net))}">
        <p class="erreur-champ" hidden></p></div>
      <div class="champ"><label class="libelle" for="${idCommentaire}">Commentaire</label>
        <input type="text" id="${idCommentaire}" name="commentaire" maxlength="200" placeholder="Facultatif — ex. pièce non utilisée"></div>
    </div>`);
    const champQuantite = UI.$('[name="quantite"]', contenu);
    const choix = await UI.fenetre({
      titre: 'Retourner une pièce (' + ot.id + ')', contenu,
      boutons: [{ libelle: 'Annuler', valeur: null, classe: 'btn-fantome' },
        { libelle: 'Retourner au magasin', valeur: 'ok', classe: 'btn-primaire', defaut: true }],
      avantFermeture() {
        const quantite = UI.enNombre(champQuantite.value);
        const erreur = UI.$('.erreur-champ', contenu);
        erreur.textContent = quantite === null || quantite <= 0 ? 'Saisissez une quantité supérieure à 0.' : '';
        erreur.hidden = !erreur.textContent;
        return !erreur.textContent;
      },
    });
    if (choix !== 'ok') return;
    const quantite = UI.enNombre(champQuantite.value);
    const commentaire = UI.$('[name="commentaire"]', contenu).value.trim();
    const reussi = await ecrireMouvement(bloc, bouton,
      () => Magasin.retourner(ot.id, ligne.articleId, quantite, commentaire), 'retour en stock');
    if (!reussi) return;
    await apresEnregistrement();
    UI.toast('Retour enregistré : ' + UI.nombreFr(quantite) + ' × ' + ligne.libelle + ' rendu(s) au magasin.', 'succes');
  }

  // Bloc affiché par l'onglet Exécution (ordres-onglets.js) : usage interne au module.
  Object.assign(Ordres.interne, { afficherPiecesSorties });

  return {};
})());
