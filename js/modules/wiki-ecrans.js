'use strict';
// Wiki (7/8) — écrans de lecture du wiki de maintenance (lot 6 refondu, ARCHITECTURE.md §20.9), pour les
// trois profils. Socle (T110) : écrans de la première version sans la synthèse — #/wiki (recherche sur
// tout le parc, liste des pages d'équipement) et #/wiki/<équipement> (en-tête, consignation telle quelle,
// recherche limitée à l'équipement, pannes habituelles, pièces consommées, dernières interventions, même
// marque et modèle) ; réécrits pour les quatre types de pages en T119. Champ de recherche réutilisable (Wiki.champRecherche,
// posé dans l'onglet Préparation de l'OT ; Wiki.poserRechercheDemande, dans la saisie d'une DI) ;
// enregistrement des écrans auprès d'App (le dernier fichier du module est wiki-journal-ecrans.js).
//
// Lecture seule : rien n'est écrit, aucun appel réseau (Wiki.pageEquipement, Wiki.listePages, Wiki.rechercher).
// Toute donnée insérée passe par UI.html (échappement) ; la consignation est posée par textContent,
// donc jamais interprétée, retours à la ligne compris. Le demandeur n'a accès ni aux écrans des OT ni au
// magasin : il voit les numéros d'OT et les références d'articles en texte, sans lien.

Object.assign(Wiki, (() => {

  // Tables lues par les écrans : réaffichés si l'une change sur un autre poste.
  const TABLES = ['equipements', 'ordres_travail', 'demandes', 'codes_defaillance', 'mouvements_stock',
    'articles', 'wiki_pages', 'wiki_journal'];
  const PROFILS = ['demandeur', 'technicien', 'responsable'];

  const DELAI_RECHERCHE_MS = 300;                       // la recherche part après 300 ms sans frappe
  const RESULTATS_MONTRES = 5;                          // par portée, avant « Voir les n autres résultats »
  const RESULTATS_MONTRES_DEMANDE = 3;                  // saisie d'une DI (téléphone) : formulaire plus court
  const MESSAGE_SANS_CONSIGNATION = 'Aucune consignation saisie pour cet équipement';
  const TITRE_RECHERCHE_DEMANDE = 'Déjà vu sur cette machine ?';
  const ESPACE_INSECABLE = String.fromCharCode(160);   // « 35 % », comme l'encart des causes fréquentes

  // ===========================================================================================
  // 1. Petits outils
  // ===========================================================================================

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  function pluriel(nombre, singulier, formePlurielle) {
    return nombre + ' ' + (nombre > 1 ? formePlurielle : singulier);
  }

  /** Le demandeur n'a accès ni aux OT ni au magasin (profils de leurs routes) : pas de lien pour lui. */
  function avecLiens() {
    return App.estTechnicien() || App.estResponsable();
  }

  function lienOt(otId, liens) {
    return liens ? UI.html`<a class="wiki-lien-ot" href="#/ot/${encodeURIComponent(otId)}">${otId}</a>`
      : UI.html`<b class="wiki-numero-ot">${otId}</b>`;
  }

  /** « le 11/09/2026 » ou « du 30/09/2025 au 11/09/2026 » (jours de panne AAAA-MM-JJ). */
  function periode(debut, fin) {
    if (!debut && !fin) return '';
    if (!debut || !fin || debut === fin) return 'le ' + UI.dateFr(fin || debut);
    return 'du ' + UI.dateFr(debut) + ' au ' + UI.dateFr(fin);
  }

  function textePannes(nombre) {
    return nombre ? pluriel(nombre, 'panne', 'pannes') + ' sur 12 mois' : 'Aucune panne sur 12 mois';
  }

  /** Fourchette de Wilson de Wiki.page → « entre 35 % et 85 % des cas » (même forme que CausesFrequentes). */
  function texteFourchette(fourchette) {
    if (!fourchette) return '';
    const pourcent = (part) => Math.floor(part * 100 + 0.5) + ESPACE_INSECABLE + '%';
    return 'entre ' + pourcent(fourchette.bas) + ' et ' + pourcent(fourchette.haut) + ' des cas';
  }

  // Adresse d'un document (async : en mode serveur c'est /api/documents/<nom>) ; null si introuvable.
  async function adresseDocument(nom) {
    if (!nom || !App.adaptateur) return null;
    try {
      return await App.adaptateur.urlDocument(nom);
    } catch (erreur) {
      console.warn('Prévo (wiki) : document « ' + nom + ' » illisible (' + (erreur && erreur.message) + ').', erreur);
      return null;
    }
  }

  // ===========================================================================================
  // 2. Champ de recherche réutilisable (§20.6, §20.7)
  // ===========================================================================================

  const recherchesPosees = new WeakMap();      // élément du champ → { champ, chercherPlusTard, repris }
  const symptomesSuivis = new WeakSet();       // champs « symptôme » des DI déjà écoutés

  /**
   * Un résultat : OT (numéro en lien ou en texte selon le profil, puis son titre) ou page du wiki (son titre en
   * lien vers #/wiki/<lien>, pour tous les profils : le wiki est ouvert au demandeur).
   */
  function resultatHtml(resultat, portee, liens, cache) {
    const estOt = resultat.type === 'ot';
    const tete = estOt ? lienOt(resultat.otId, liens)
      : UI.html`<a class="wiki-lien-page" href="#/wiki/${encodeURIComponent(resultat.lien)}">${resultat.titre}</a><span class="badge info">Page du wiki</span>`;
    const repere = portee !== 'equipement' && resultat.repere ? UI.html`<span class="badge neutre">${resultat.repere}</span>` : '';
    const codes = [resultat.cause ? UI.html`<span>Cause : ${resultat.cause}</span>` : '',
      resultat.remede ? UI.html`<span>Remède : ${resultat.remede}</span>` : ''];
    return UI.html`<li class="wiki-trouve" data-type="${resultat.type}" data-id="${estOt ? resultat.otId : resultat.pageId}"${cache ? UI.brut(' hidden') : ''}>
      <div class="wiki-ligne-tete">${tete}${repere}${resultat.date ? UI.html`<span class="wiki-date">${UI.dateFr(resultat.date)}</span>` : ''}</div>
      ${estOt ? UI.html`<div class="carte-titre">${resultat.titre}</div>` : ''}
      ${resultat.cause || resultat.remede ? UI.html`<div class="carte-meta">${codes}</div>` : ''}
      ${resultat.extrait ? UI.html`<p class="wiki-extrait">${Wiki.surligner(resultat.extrait, resultat.mots)}</p>` : ''}
    </li>`;
  }

  /** Une portée (« Sur cet équipement »…) : ses `montres` premiers résultats, le reste derrière un bouton. */
  function blocPortee(portee, liens, montres) {
    const reste = portee.resultats.length - montres;
    const texteBouton = reste > 1 ? 'Voir les ' + reste + ' autres résultats' : 'Voir l\'autre résultat';
    const bloc = UI.element(UI.html`<div class="wiki-portee" data-portee="${portee.portee}">
      <h3>${portee.libelle} <span class="badge">${portee.resultats.length}</span></h3>
      <ul class="wiki-lignes">${portee.resultats.map((resultat, rang) => resultatHtml(resultat, portee.portee, liens, rang >= montres))}</ul>
      ${reste > 0 ? UI.html`<button type="button" class="btn btn-fantome wiki-voir-plus" aria-expanded="false">${texteBouton}</button>` : ''}
    </div>`);
    const bouton = UI.$('.wiki-voir-plus', bloc);
    if (bouton) {
      bouton.addEventListener('click', () => {
        const ouvrir = bouton.getAttribute('aria-expanded') !== 'true';
        UI.$$('.wiki-trouve', bloc).forEach((ligne, rang) => { ligne.hidden = !ouvrir && rang >= montres; });
        bouton.setAttribute('aria-expanded', String(ouvrir));
        bouton.textContent = ouvrir ? 'Montrer moins de résultats' : texteBouton;
      });
    }
    return bloc;
  }

  function afficherResultats(zone, resultat, montres) {
    if (!resultat.requete) {
      zone.textContent = '';
      return;
    }
    const portees = resultat.portees.filter((portee) => portee.resultats.length);
    if (!portees.length) {
      UI.remplir(zone, UI.html`<p class="wiki-rien"><b>Rien trouvé pour « ${resultat.requete} ».</b></p>
        <p class="aide">Essayez un autre mot : fuite, bruit, chauffe, ne démarre pas…</p>`);
      return;
    }
    const liens = avecLiens();
    UI.remplir(zone, portees.map((portee) => blocPortee(portee, liens, montres)));
  }

  /** Construit le champ et sa zone de résultats → { element, champ, chercherPlusTard }. */
  /**
   * Texte de départ d'une recherche limitée à un équipement : son repère (souvent en tête d'un titre d'OT,
   * « PO-02 — Fuite… ») est retiré, avec les tirets et deux-points qui le suivent ; sinon « po » et « 02 »
   * seraient cherchés partout.
   */
  function sansRepere(valeur, equipementId) {
    const equipement = equipementId ? Donnees.trouver('equipements', equipementId) : null;
    const repere = texte(equipement && equipement.repere);
    if (!repere) return texte(valeur);
    return texte(valeur).split(repere).join(' ').replace(/^[\s—–:-]+/, '').replace(/\s+/g, ' ').trim();
  }

  function creerChamp(options) {
    const reglages = options || {};
    const equipementId = texte(reglages.equipementId);
    const titre = texte(reglages.titre) || 'Chercher dans l\'historique';
    const montres = Number.isInteger(reglages.montres) && reglages.montres > 0 ? reglages.montres : RESULTATS_MONTRES;
    const id = UI.identifiantUnique('wiki-recherche');
    const aide = equipementId
      ? 'Dans les interventions clôturées : cet équipement d\'abord, puis ceux de même marque et modèle, puis le reste du parc.'
      : 'Dans les interventions clôturées de tout le parc.';
    const element = UI.element(UI.html`
      <section class="carte wiki-recherche" data-hors-saisie role="search" aria-label="${titre}" data-equipement="${equipementId}">
        <label class="wiki-recherche-titre" for="${id}">${UI.icone('recherche')}<span>${titre}</span></label>
        <input type="search" id="${id}" class="wiki-recherche-champ" data-hors-saisie maxlength="200" autocomplete="off"
          enterkeyhint="search" placeholder="Ex. fuite, bruit, ne démarre pas" value="${sansRepere(reglages.texteInitial, equipementId)}">
        <p class="aide wiki-recherche-aide">${aide}</p>
        <div class="wiki-resultats" aria-live="polite"></div>
      </section>`);
    const champ = UI.$('.wiki-recherche-champ', element);
    const zone = UI.$('.wiki-resultats', element);
    let minuterie = null;

    function chercher() {
      clearTimeout(minuterie);
      minuterie = null;
      try {
        afficherResultats(zone, Wiki.rechercher(champ.value, { equipementId }), montres);
      } catch (erreur) {
        UI.remplir(zone, UI.html`<p class="erreur">Recherche impossible : ${(erreur && erreur.message) || ''}</p>`);
        console.warn('Prévo (wiki) : recherche impossible (' + (erreur && erreur.message) + ').', erreur);
      }
    }
    // Après DELAI_RECHERCHE_MS sans frappe ; rien si le champ n'est plus affiché (écran quitté).
    function chercherPlusTard() {
      clearTimeout(minuterie);
      minuterie = setTimeout(() => { if (element.isConnected) chercher(); }, DELAI_RECHERCHE_MS);
    }
    champ.addEventListener('input', chercherPlusTard);
    champ.addEventListener('keydown', (evenement) => {
      if (evenement.key !== 'Enter') return;
      evenement.preventDefault();            // jamais l'envoi du formulaire qui contient le champ (DI)
      chercher();
    });
    if (champ.value) chercherPlusTard();      // pré-rempli (titre de l'OT, symptôme) : résultats tout de suite
    return { element, champ, chercherPlusTard };
  }

  /**
   * Champ de recherche réutilisable : Wiki.champRecherche({ equipementId, texteInitial, titre, montres }) →
   * élément <section> (carte) à poser dans l'écran. Sans équipement : tout le parc ; avec : portées équipement,
   * même marque et modèle, parc. Champ type="search" [data-hors-saisie] (ce n'est pas une saisie en cours) ;
   * `montres` : résultats montrés par portée avant « Voir les n autres résultats » (5 par défaut).
   */
  function champRecherche(options) {
    return creerChamp(options).element;
  }

  // Le champ « Déjà vu sur cette machine ? » reprend le symptôme tant qu'on n'y a pas tapé autre chose.
  function suivreSymptome(champSymptome) {
    const etape = champSymptome.closest('section');
    const bloc = etape ? UI.$('.wiki-recherche-demande', etape) : null;
    const recherche = bloc ? recherchesPosees.get(bloc) : null;
    if (!recherche || recherche.champ.value !== recherche.repris) return;
    recherche.repris = texte(champSymptome.value);
    recherche.champ.value = recherche.repris;
    recherche.chercherPlusTard();
  }

  /**
   * Saisie d'une DI (§20.7) : une fois l'équipement choisi, le champ « Déjà vu sur cette machine ? »,
   * pré-rempli avec le symptôme saisi, sous le symptôme (dans sa <section>). À rappeler à chaque choix
   * d'équipement : sans équipement, le champ est retiré ; avec un autre, il est refait.
   */
  function poserRechercheDemande(champSymptome, equipementId) {
    const etape = champSymptome ? champSymptome.closest('section') : null;
    if (!etape) return null;
    const id = texte(equipementId);
    const actuel = UI.$('.wiki-recherche-demande', etape);
    if (actuel && actuel.dataset.equipement === id) return actuel;
    if (actuel) actuel.remove();
    if (!id) return null;
    const recherche = creerChamp({ equipementId: id, texteInitial: champSymptome.value, titre: TITRE_RECHERCHE_DEMANDE,
      montres: RESULTATS_MONTRES_DEMANDE });
    recherche.element.classList.replace('carte', 'wiki-recherche-demande');
    recherche.repris = recherche.champ.value;
    recherchesPosees.set(recherche.element, recherche);
    etape.appendChild(recherche.element);
    if (!symptomesSuivis.has(champSymptome)) {
      symptomesSuivis.add(champSymptome);
      champSymptome.addEventListener('input', () => suivreSymptome(champSymptome));
    }
    return recherche.element;
  }

  // ===========================================================================================
  // 3. Écran #/wiki : liste des pages
  // ===========================================================================================

  function pageHtml(entree) {
    return UI.html`<li data-equipement="${entree.equipementId}" data-pannes="${entree.pannes12Mois}">
      <a href="#/wiki/${encodeURIComponent(entree.equipementId)}">
        <div class="carte-tete"><b>${entree.repere || entree.equipementId}</b></div>
        <div class="carte-titre">${entree.designation}</div>
        <div class="carte-meta"><span class="wiki-pannes">${textePannes(entree.pannes12Mois)}</span></div>
      </a></li>`;
  }

  function afficherListe(conteneur) {
    // Wiki.listePages trie par pannes des 12 derniers mois (décroissant), puis par repère.
    const pages = Wiki.listePages();
    App.definirTitre('Wiki');
    UI.remplir(conteneur, UI.html`
      <div class="wiki wiki-liste">
        <div class="entete-page"><div>
          <h1>Wiki de maintenance</h1>
          <p>Ce que l'atelier sait de chaque équipement : pannes habituelles, ce qui les a réglées, pièces changées.</p>
        </div></div>
        <div class="wiki-zone-recherche"></div>
        <section class="wiki-pages-zone" aria-labelledby="wiki-titre-pages">
          <div class="entete-carte">
            <h2 id="wiki-titre-pages">Pages des équipements <span class="badge" id="wiki-nombre-pages">${pages.length}</span></h2>
          </div>
          <p class="aide">Un équipement a sa page dès qu'une intervention y est clôturée ; les plus en panne
            sur les 12 derniers mois d'abord.</p>
          <ul class="liste-cartes wiki-pages"></ul>
        </section>
      </div>`);
    UI.$('.wiki-zone-recherche', conteneur).replaceWith(champRecherche({ titre: 'Chercher dans l\'historique du parc' }));
    const liste = UI.$('.wiki-pages', conteneur);
    if (pages.length) {
      UI.remplir(liste, pages.map(pageHtml));
      return;
    }
    UI.remplir(liste, UI.html`<li class="wiki-liste-vide">${UI.vide('Aucune page pour l\'instant',
      'Un équipement a sa page dès qu\'une intervention y est clôturée.', 'wiki')}</li>`);
  }

  // ===========================================================================================
  // 4. Écran #/wiki/<équipement> : page d'un équipement
  // ===========================================================================================

  /** Consignation (#wiki-consignation) : texte humain de la fiche tel quel, document ; jamais de texte d'IA. */
  function blocConsignation(page, responsable) {
    const consignation = page.consignation || { texte: '', document: '' };
    const nomDocument = texte(consignation.document);
    const section = UI.element(UI.html`
      <section class="carte wiki-consignation" id="wiki-consignation" aria-labelledby="wiki-titre-consignation">
        <h2 id="wiki-titre-consignation">${UI.icone('alerte')} Consignation</h2>
        ${texte(consignation.texte)
          ? UI.html`<p class="aide">Procédure de la fiche de l'équipement, telle qu'elle a été saisie.</p>
            <div class="wiki-consignation-texte"></div>`
          : UI.html`<p class="wiki-sans-consignation"><b>${MESSAGE_SANS_CONSIGNATION}</b></p>
            ${responsable ? UI.html`<p><a class="btn btn-secondaire" id="wiki-modifier-consignation"
              href="#/equipement/${encodeURIComponent(page.equipement.id)}/modifier">${UI.icone('cle')}Saisir la consignation dans la fiche</a></p>` : ''}`}
        ${nomDocument ? UI.html`<p class="wiki-consignation-document">Document : <span class="wiki-document">${nomDocument}</span></p>` : ''}
      </section>`);
    const zoneTexte = UI.$('.wiki-consignation-texte', section);
    if (zoneTexte) zoneTexte.textContent = consignation.texte;      // tel quel : jamais interprété
    const zoneDocument = UI.$('.wiki-document', section);
    if (zoneDocument) {
      adresseDocument(nomDocument).then((adresse) => {
        UI.remplir(zoneDocument, adresse
          ? UI.html`<a class="wiki-lien-document" href="${adresse}" target="_blank" rel="noopener">${UI.icone('document')} ${nomDocument}</a>`
          : UI.html`${nomDocument} <span class="badge attention">fichier introuvable</span>`);
      });
    }
    return section;
  }

  function remedeHtml(remede) {
    const recidives = remede.recidives ? pluriel(remede.recidives, 'récidive', 'récidives') : 'aucune récidive';
    return UI.html`<li data-code="${remede.code}"><span class="wiki-remede">${remede.libelle}</span> : ${remede.fois} fois,
      ${recidives} dans les ${Wiki.SEUILS.recidiveJours} jours</li>`;
  }

  /** Symptôme suffisant : mention « peu de cas », causes et remèdes, fourchettes dans un détail repliable. */
  function causesHtml(symptome) {
    if (!symptome.causes.length) return UI.html`<p class="aide wiki-sans-cause">Aucune cause n'est renseignée sur ces cas.</p>`;
    return UI.html`${symptome.peuDeCas ? UI.html`<p class="causes-piste wiki-piste"><b>${Wiki.MENTION_PISTE}</b></p>` : ''}
      <ul class="wiki-causes">${symptome.causes.map((cause) => UI.html`<li data-code="${cause.code}">
        <span class="wiki-cause"><b>${cause.libelle}</b> — ${cause.nombre} cas sur ${symptome.casAvecCause}${cause.dernierCas
          ? ' · dernier cas le ' + UI.dateFr(cause.dernierCas) : ''}</span>
        ${cause.remedes.length ? UI.html`<ul class="wiki-remedes" aria-label="Remèdes employés">${cause.remedes.map(remedeHtml)}</ul>`
          : UI.html`<p class="aide">Aucun remède renseigné.</p>`}
      </li>`)}</ul>
      <details class="causes-precision wiki-precision"><summary>Précision de ces chiffres</summary>
        <dl class="causes-fourchettes">${symptome.causes.map((cause) => UI.html`<div><dt>${cause.libelle} :</dt>
          <dd>${texteFourchette(cause.fourchette)}</dd></div>`)}</dl>
        <p class="causes-explication">Calculée ainsi (méthode de Wilson), une fourchette contient la vraie part de la cause
          95 fois sur 100 ; elle se resserre quand les cas s'accumulent.</p>
      </details>`;
  }

  function symptomeHtml(symptome) {
    return UI.html`<li class="wiki-symptome" data-code="${symptome.code}" data-suffisant="${symptome.suffisant ? 'oui' : 'non'}">
      <div class="wiki-symptome-tete"><h3>${symptome.libelle}</h3><span class="badge info wiki-cas">${symptome.cas} cas</span>
        <span class="wiki-periode">${periode(symptome.debut, symptome.fin)}</span></div>
      ${symptome.suffisant ? causesHtml(symptome)
        : UI.html`<p class="wiki-insuffisant">Pas encore assez de cas pour ce symptôme (${symptome.cas} sur ${Wiki.SEUILS.otMinimum})</p>`}
    </li>`;
  }

  function pannesHtml(pannes, messageVide) {
    if (!pannes.length) return UI.html`<p class="muted wiki-sans-panne">${messageVide}</p>`;
    return UI.html`<ul class="wiki-symptomes">${pannes.map(symptomeHtml)}</ul>
      <p class="note wiki-mention">${Wiki.MENTION_STATISTIQUE}</p>`;
  }

  function blocPannes(page) {
    return UI.html`<section class="carte wiki-section" id="wiki-pannes" aria-labelledby="wiki-titre-pannes">
      <h2 id="wiki-titre-pannes">Pannes habituelles</h2>
      <p class="aide">Les symptômes les plus fréquents des interventions correctives clôturées ; causes et remèdes
        à partir de ${Wiki.SEUILS.otMinimum} cas.</p>
      ${pannesHtml(page.pannes, 'Aucune intervention corrective clôturée avec un symptôme sur cet équipement.')}
    </section>`;
  }

  function blocPieces(page, liens) {
    const lignes = page.pieces.map((piece) => {
      const article = Donnees.trouver('articles', piece.articleId);
      const unite = article ? texte(article.unite) : '';
      const reference = liens && article
        ? UI.html`<a class="wiki-lien-article" href="#/magasin/article/${encodeURIComponent(piece.articleId)}">${piece.reference}</a>`
        : UI.html`<b>${piece.reference}</b>`;
      return UI.html`<li data-article="${piece.articleId}">
        <div class="wiki-ligne-tete">${reference}<span class="wiki-designation">${piece.designation}</span></div>
        <div class="carte-meta"><span class="wiki-quantite">Quantité : ${UI.nombreFr(piece.quantite)}${unite ? ' ' + unite : ''}</span>
          <span>${pluriel(piece.nombreOt, 'intervention', 'interventions')}</span>
          ${piece.derniereDate ? UI.html`<span>dernière sortie le ${UI.dateFr(piece.derniereDate)}</span>` : ''}</div>
      </li>`;
    });
    return UI.html`<section class="carte wiki-section" id="wiki-pieces" aria-labelledby="wiki-titre-pieces">
      <h2 id="wiki-titre-pieces">Pièces consommées <span class="badge">${lignes.length}</span></h2>
      <p class="aide">Sorties du magasin pour les interventions de l'équipement, retours déduits.</p>
      ${lignes.length ? UI.html`<ul class="wiki-lignes wiki-pieces">${lignes}</ul>`
        : UI.html`<p class="muted">Aucune pièce sortie du magasin pour cet équipement.</p>`}
    </section>`;
  }

  function interventionHtml(ot, liens) {
    const codes = [['Symptôme', ot.codes.symptome], ['Cause', ot.codes.cause], ['Remède', ot.codes.remede]]
      .filter(([, libelle]) => libelle);
    const arret = ot.dureeArret === null || ot.dureeArret === undefined ? '' : UI.html`<span>Arrêt : ${UI.heures(ot.dureeArret)}</span>`;
    return UI.html`<li data-ot="${ot.id}">
      <div class="wiki-ligne-tete">${lienOt(ot.id, liens)}${ot.date ? UI.html`<span class="wiki-date">${UI.dateFr(ot.date)}</span>` : ''}
        ${ot.type ? UI.html`<span class="badge neutre">${ot.type}</span>` : ''}</div>
      <div class="carte-titre">${ot.titre}</div>
      ${codes.length || arret ? UI.html`<div class="carte-meta">${codes.map(([nom, libelle]) => UI.html`<span>${nom} : ${libelle}</span>`)}${arret}</div>` : ''}
      ${ot.extrait ? UI.html`<p class="wiki-extrait">${ot.extrait}</p>` : ''}
    </li>`;
  }

  /** Dernières interventions ; au-delà, « Voir les autres » vers les OT clôturés de l'équipement (texte pour le demandeur). */
  function blocDernieres(page, liens) {
    const reste = page.total - page.dernieres.length;
    let suite = '';
    if (reste > 0 && liens) {
      suite = UI.html`<div class="actions"><a class="btn btn-secondaire" id="wiki-voir-autres"
        href="#/ot?equipement=${encodeURIComponent(page.equipement.id)}&amp;etat=clotures">${reste > 1
          ? 'Voir les ' + reste + ' autres interventions' : 'Voir l\'autre intervention'}</a></div>`;
    } else if (reste > 0) {
      suite = UI.html`<p class="aide" id="wiki-autres">Et ${pluriel(reste, 'intervention plus ancienne', 'interventions plus anciennes')}.</p>`;
    }
    return UI.html`<section class="carte wiki-section" id="wiki-dernieres" aria-labelledby="wiki-titre-dernieres">
      <h2 id="wiki-titre-dernieres">Dernières interventions <span class="badge">${page.total}</span></h2>
      ${page.dernieres.length ? UI.html`<ul class="wiki-lignes wiki-interventions">${page.dernieres.map((ot) => interventionHtml(ot, liens))}</ul>`
        : UI.html`<p class="muted">Aucune intervention clôturée sur cet équipement.</p>`}
      ${suite}
    </section>`;
  }

  function blocMemeModele(page) {
    if (!page.memeModele) return '';
    const equipement = page.equipement;
    const jumeaux = page.memeModele.equipements;
    return UI.html`<section class="carte wiki-section" id="wiki-meme-modele" aria-labelledby="wiki-titre-meme-modele">
      <h2 id="wiki-titre-meme-modele">Même marque et modèle</h2>
      <p class="aide">${equipement.marque} ${equipement.modele} : les pannes de cet équipement et de
        ${jumeaux.length > 1 ? 'ses jumeaux' : 'son jumeau'}, comptées ensemble.</p>
      <ul class="wiki-jumeaux" aria-label="Équipements de même marque et modèle">${jumeaux.map((autre) => UI.html`<li>
        <a href="#/wiki/${encodeURIComponent(autre.id)}">${autre.repere || autre.id}</a></li>`)}</ul>
      ${pannesHtml(page.memeModele.pannes, 'Aucune intervention corrective clôturée avec un symptôme sur ces équipements.')}
    </section>`;
  }

  function afficherIntrouvable(conteneur, id) {
    App.definirTitre('Équipement introuvable');
    UI.remplir(conteneur, UI.html`<div class="wiki wiki-page wiki-introuvable">
      <div class="entete-page"><div>
        <div class="fil"><a href="#/wiki">Wiki</a></div>
        <h1>Équipement introuvable</h1>
      </div></div>
      ${UI.vide('Aucun équipement ne porte l\'identifiant « ' + id + ' »',
        'Il a peut-être été saisi sur un autre poste. La liste du wiki montre les équipements connus.', 'wiki')}
      <p><a class="btn btn-secondaire" href="#/wiki">Retour au wiki</a></p>
    </div>`);
  }

  async function afficherPage(conteneur, parametres) {
    const id = texte(parametres.id);
    const page = Wiki.pageEquipement(id);
    if (!page) {
      afficherIntrouvable(conteneur, id);
      return;
    }
    const liens = avecLiens();
    const equipement = page.equipement;
    const repere = equipement.repere || equipement.id;
    const marqueModele = [equipement.marque, equipement.modele].filter(Boolean).join(' ');
    App.definirTitre('Wiki ' + repere);
    UI.remplir(conteneur, UI.html`
      <div class="wiki wiki-page" data-equipement="${equipement.id}">
        <div class="entete-page">
          <div>
            <div class="fil"><a href="#/wiki">Wiki</a> <span aria-hidden="true">›</span> <span>${repere}</span></div>
            <h1>${repere}${equipement.designation ? ' — ' + equipement.designation : ''}</h1>
            <p class="wiki-sous-titre">${marqueModele ? marqueModele + ' · ' : ''}${textePannes(page.pannes12Mois)}</p>
          </div>
          <div class="actions"><a class="btn btn-secondaire" id="wiki-lien-fiche"
            href="#/equipement/${encodeURIComponent(equipement.id)}">${UI.icone('parc')}Fiche de l'équipement</a></div>
        </div>
        <div class="wiki-zone-consignation"></div>
        <div class="wiki-zone-recherche"></div>
        ${blocPannes(page)}
        ${blocPieces(page, liens)}
        ${blocDernieres(page, liens)}
        ${blocMemeModele(page)}
      </div>`);
    UI.$('.wiki-zone-consignation', conteneur).replaceWith(blocConsignation(page, App.estResponsable()));
    UI.$('.wiki-zone-recherche', conteneur).replaceWith(champRecherche({
      equipementId: equipement.id, titre: 'Chercher dans l\'historique de cet équipement' }));
  }

  // ===========================================================================================
  // 5. Enregistrement des écrans (App est chargé après les modules : on attend la page)
  // ===========================================================================================

  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'wiki',
      route: /^#\/wiki$/,
      titre: 'Wiki',
      menu: { libelle: 'Wiki', icone: 'wiki', ordre: 42 },
      profils: PROFILS,
      tables: TABLES,
      afficher: afficherListe,
    });
    App.ecran({
      id: 'wiki-equipement',
      route: /^#\/wiki\/(?<id>[^/?]+)$/,
      titre: 'Wiki de l\'équipement',
      parent: 'wiki',
      profils: PROFILS,
      tables: TABLES,
      afficher: afficherPage,
    });
  });

  return { champRecherche, poserRechercheDemande };
})());
