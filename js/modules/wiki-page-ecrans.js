'use strict';
// Wiki (7 bis/8) — rendu d'une page du wiki #/wiki/<id> pour les quatre types (lot 6 refondu, ARCHITECTURE.md §20.9 ;
// tâche T119). La route et l'appel à Wiki.page sont dans wiki-ecrans.js, chargé juste avant ; ce fichier ne fait
// que poser la page (Wiki.rendrePage), de haut en bas : en-tête (type, titre, lien vers la fiche) ; pour un
// savoir-faire, l'en-tête posé par Prévo (consignation de l'équipement telle quelle et « Ce savoir-faire ne
// remplace pas la consignation de l'équipement ») ; la couche calculée, séparée du texte ; le texte par rubrique,
// précédé de son origine ; l'encadré « À trancher » ; « Pages qui renvoient ici » ; au responsable, « Modifier »
// et les propositions en attente sur la page.
//
// Aucune donnée n'est insérée comme HTML : UI.html échappe, la consignation est posée par textContent, et le
// texte d'une page est construit élément par élément (texte, liens vers les pages, OT cités). Le demandeur voit
// les numéros d'OT en texte, sans lien, et aucune référence du magasin en lien.
//
// Précisions au contrat (§20.9) :
//  - [[titre]] → identifiant : même règle que le champ `liens` à la validation (équipements, articles, puis pages
//    actives, en forme comparable), sur toutes les pages (Wiki.catalogue est plafonné à catalogueMax) ; un titre
//    inconnu reste du texte (« page introuvable ») ;
//  - « Ce que dit la page » : la phrase de la page de même identité (Wiki.identitePhrase), avec ses OT ; sinon la
//    phrase telle que la contradiction l'a notée ;
//  - « Le nouveau remplace » mène à #/wiki-ecrire/<page> (écriture à la main, wiki-journal-ecrans.js).

Object.assign(Wiki, (() => {

  const MESSAGE_SANS_CONSIGNATION = 'Aucune consignation saisie pour cet équipement';
  const MESSAGE_SANS_TEXTE = 'Aucun texte validé pour l\'instant.';
  const PHRASE_SAVOIR_FAIRE = 'Ce savoir-faire ne remplace pas la consignation de l\'équipement';   // = Wiki.PHRASE_SAVOIR_FAIRE
  const TYPES = { 'équipement': 'Équipement', composant: 'Composant', mode: 'Mode de défaillance', 'savoir-faire': 'Savoir-faire' };
  const DECISIONS = [['ancien', 'L\'ancien reste'], ['nouveau', 'Le nouveau remplace'], ['les deux', 'Les deux sont vrais']];
  const SOURCES_MONTAGE = { liste: 'dans la liste des pièces', consommation: 'consommé en intervention',
    'les deux': 'dans la liste des pièces et consommé en intervention' };
  const MOTIF_JETON = /\[\[([^[\]]+)\]\]|\[(OT-\d{4}-\d{4,})\]/g;
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

  function lienOt(otId, liens) {
    return liens ? UI.html`<a class="wiki-lien-ot" href="#/ot/${encodeURIComponent(otId)}">${otId}</a>`
      : UI.html`<b class="wiki-numero-ot">${otId}</b>`;
  }

  function lienWiki(id, titre, classe) {
    return UI.html`<a class="${classe || 'wiki-lien-page'}" href="#/wiki/${encodeURIComponent(id)}">${titre || id}</a>`;
  }

  function repereDe(equipementId) {
    const equipement = Donnees.trouver('equipements', equipementId);
    return { repere: texte(equipement && equipement.repere) || equipementId, designation: texte(equipement && equipement.designation) };
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

  /** Fourchette de Wilson → « entre 35 % et 85 % des cas » (même forme que CausesFrequentes). */
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

  /** Titre d'une page ([[titre]]) → identifiant, sur toutes les pages de l'index (pages actives en dernier). */
  function resolveur(sections) {
    const index = new Map();
    sections.forEach((section) => section.pages.forEach((page) => index.set(Wiki.comparable(page.titre), page.id)));
    return (titre) => index.get(Wiki.comparable(titre)) || '';
  }

  // ===========================================================================================
  // 2. Texte d'une page : rubriques, phrases, liens, OT cités, origine
  // ===========================================================================================

  /** Une phrase → <li> construit élément par élément : texte, liens vers les pages, puis ses OT cités. */
  function phraseElement(source, contexte) {
    const morceaux = [];
    const cites = [];
    let position = 0;
    for (const jeton of String(source || '').matchAll(MOTIF_JETON)) {
      morceaux.push({ texte: source.slice(position, jeton.index) });
      position = jeton.index + jeton[0].length;
      if (jeton[2]) { if (!cites.includes(jeton[2])) cites.push(jeton[2]); } else morceaux.push({ lien: jeton[1].trim() });
    }
    morceaux.push({ texte: String(source || '').slice(position) });
    morceaux.forEach((morceau) => { if ('texte' in morceau) morceau.texte = morceau.texte.replace(/\s+/g, ' '); });
    while (morceaux.length && 'texte' in morceaux[0] && !morceaux[0].texte.trim()) morceaux.shift();
    while (morceaux.length && 'texte' in morceaux[morceaux.length - 1] && !morceaux[morceaux.length - 1].texte.trim()) morceaux.pop();
    if (morceaux.length && 'texte' in morceaux[0]) morceaux[0].texte = morceaux[0].texte.replace(/^ /, '');
    if (morceaux.length && 'texte' in morceaux[morceaux.length - 1]) morceaux[morceaux.length - 1].texte = morceaux[morceaux.length - 1].texte.replace(/ $/, '');
    const li = document.createElement('li');
    li.className = 'wiki-phrase';
    const corps = document.createElement('span');
    corps.className = 'wiki-phrase-texte';
    morceaux.forEach((morceau) => {
      if ('texte' in morceau) { corps.appendChild(document.createTextNode(morceau.texte)); return; }
      const id = contexte.resoudre(morceau.lien);
      corps.appendChild(id ? UI.element(lienWiki(id, morceau.lien))
        : UI.element(UI.html`<span class="wiki-lien-absent" title="Page introuvable dans le wiki">${morceau.lien}</span>`));
    });
    li.appendChild(corps);
    if (cites.length) {
      li.appendChild(document.createTextNode(' '));
      li.appendChild(UI.element(UI.html`<span class="wiki-citations" aria-label="OT cités">${cites.map((ot) => lienOt(ot, contexte.liens))}</span>`));
    }
    return li;
  }

  /** Bandeau d'origine (§20.9, CS103). */
  function texteOrigine(page) {
    const modele = texte(page.modele);
    const ia = 'Rédigé avec l\'IA' + (modele ? ' (' + modele + ')' : '') + ' à partir des OT cités';
    const date = UI.dateFr(texte(page.valideLe));
    const par = (texte(page.validePar) || 'le responsable') + (date ? ' le ' + date : '');
    if (page.origine === 'IA') return ia + ' — validé par ' + par;
    if (page.origine === 'manuel') return 'Écrit par ' + par;
    if (page.origine === 'IA et manuel') return ia + ', puis modifié à la main — validé par ' + par;
    return 'Origine non renseignée' + (texte(page.validePar) ? ' — validé par ' + par : '');
  }

  function blocTexte(page, contexte) {
    const section = UI.element(UI.html`<section class="carte wiki-texte" id="wiki-texte" aria-labelledby="wiki-titre-texte">
      <div class="entete-carte"><h2 id="wiki-titre-texte">Ce que l'atelier a appris</h2>
        ${contexte.responsable ? UI.html`<a class="btn btn-secondaire" id="wiki-modifier"
          href="#/wiki-ecrire/${encodeURIComponent(page.id)}">${UI.icone('cle')}Modifier</a>` : ''}</div>
    </section>`);
    if (!texte(page.texte)) {
      section.appendChild(UI.element(UI.html`<p class="wiki-sans-texte"><b>${MESSAGE_SANS_TEXTE}</b></p>`));
      section.appendChild(UI.element(UI.html`<p class="aide">Le texte se rédige à partir des OT clôturés administrativement,
        puis le responsable le valide.</p>`));
      return section;
    }
    section.appendChild(UI.element(UI.html`<p class="wiki-origine" data-origine="${page.origine}">${UI.icone('apropos')}<span>${texteOrigine(page)}</span></p>`));
    const lu = Wiki.lireTexte(page.texte);
    lu.rubriques.filter((rubrique) => rubrique.phrases.length).forEach((rubrique) => {
      const bloc = UI.element(UI.html`<div class="wiki-rubrique"><h3>${rubrique.nom}</h3><ul class="wiki-phrases"></ul></div>`);
      rubrique.phrases.forEach((phrase) => UI.$('.wiki-phrases', bloc).appendChild(phraseElement(phrase.texte, contexte)));
      section.appendChild(bloc);
    });
    if (lu.erreurs.length) {
      section.appendChild(UI.element(UI.html`<p class="note wiki-hors-forme">${pluriel(lu.erreurs.length, 'ligne', 'lignes')}
        du texte hors de la forme attendue, non ${lu.erreurs.length > 1 ? 'affichées' : 'affichée'}.</p>`));
    }
    return section;
  }

  // ===========================================================================================
  // 3. « À trancher » (D107), « Pages qui renvoient ici », propositions en attente
  // ===========================================================================================

  /** Phrase de la page contredite : celle du texte de même identité (avec ses OT), sinon telle que notée. */
  function phraseContredite(page, contradiction) {
    const identite = Wiki.identitePhrase(contradiction.phrase);
    const trouvee = Wiki.lireTexte(page.texte).rubriques.flatMap((rubrique) => rubrique.phrases)
      .find((phrase) => Wiki.identitePhrase(phrase.texte) === identite);
    return trouvee ? trouvee.texte : contradiction.phrase;
  }

  async function trancher(element, contradiction, bouton) {
    const boutons = UI.$$('button[data-decision]', element);
    boutons.forEach((autre) => { autre.disabled = true; });
    bouton.setAttribute('aria-busy', 'true');
    const decision = bouton.dataset.decision;
    try {
      const resultat = await Wiki.trancher(contradiction.entreeId, contradiction.rang, decision, UI.$('.wiki-note', element).value);
      App.marquerSaisie(false);
      UI.toast('Décision enregistrée au journal du wiki.', 'succes');
      if (decision === 'nouveau' && resultat && resultat.pageId) {
        App.naviguer('#/wiki-ecrire/' + encodeURIComponent(resultat.pageId));
        return;
      }
      await App.reafficher();
    } catch (erreur) {
      console.warn('Prévo (wiki) : décision non enregistrée (' + (erreur && erreur.message) + ').', erreur);
      UI.toast('Décision non enregistrée : ' + ((erreur && erreur.message) || String(erreur)), 'erreur');
      boutons.forEach((autre) => { autre.disabled = false; });
      bouton.removeAttribute('aria-busy');
    }
  }

  function contradictionElement(page, contradiction, contexte) {
    const anterieure = Boolean(contradiction.anterieure);
    const ots = (contradiction.ot && contradiction.ot.length ? contradiction.ot : [contradiction.otSource]).filter(Boolean);
    const idNote = UI.identifiantUnique('wiki-note');
    const element = UI.element(UI.html`<li class="wiki-contradiction" data-entree="${contradiction.entreeId}"
        data-rang="${contradiction.rang}" data-anterieure="${anterieure ? 'oui' : 'non'}">
      <div class="wiki-cotes">
        <div class="wiki-cote wiki-cote-page"><h3>Ce que dit la page</h3><ul class="wiki-phrases"></ul></div>
        <div class="wiki-cote wiki-cote-ot"><h3>${anterieure ? 'Observation antérieure aux faits de la page' : 'Ce que dit le nouvel OT'}</h3>
          <p class="wiki-observation">${contradiction.observation}</p>
          ${ots.length ? UI.html`<p class="wiki-citations" aria-label="OT cités">${ots.map((ot) => lienOt(ot, contexte.liens))}</p>` : ''}</div>
      </div>
      ${contradiction.depuis ? UI.html`<p class="aide wiki-depuis">Signalée le ${UI.dateFr(contradiction.depuis)}.</p>` : ''}
      ${contexte.responsable ? UI.html`<div class="wiki-trancher" role="group" aria-label="Trancher cette contradiction">
        <div class="champ"><label class="libelle" for="${idNote}">Note (facultative)</label>
          <textarea id="${idNote}" class="wiki-note" rows="2" maxlength="500"></textarea></div>
        <div class="actions">${DECISIONS.map(([decision, libelle]) => UI.html`<button type="button"
          class="btn ${decision === 'nouveau' ? 'btn-primaire' : 'btn-secondaire'}" data-decision="${decision}">${libelle}</button>`)}</div>
      </div>` : ''}
    </li>`);
    UI.$('.wiki-cote-page .wiki-phrases', element).appendChild(phraseElement(phraseContredite(page, contradiction), contexte));
    UI.$$('button[data-decision]', element).forEach((bouton) => bouton.addEventListener('click', () => trancher(element, contradiction, bouton)));
    return element;
  }

  function blocContradictions(page, contexte) {
    const section = UI.element(UI.html`<section class="carte wiki-a-trancher" id="wiki-a-trancher" aria-labelledby="wiki-titre-trancher">
      <h2 id="wiki-titre-trancher">${UI.icone('alerte')}À trancher <span class="badge attention">${page.contradictions.length}</span></h2>
      <p class="aide">Un OT dit autre chose que la page. La page reste telle quelle tant que le responsable n'a pas tranché.</p>
      <ul class="wiki-contradictions"></ul>
    </section>`);
    page.contradictions.forEach((contradiction) => UI.$('.wiki-contradictions', section)
      .appendChild(contradictionElement(page, contradiction, contexte)));
    return section;
  }

  function blocRetours(page) {
    return UI.html`<section class="carte wiki-section" id="wiki-retours" aria-labelledby="wiki-titre-retours">
      <h2 id="wiki-titre-retours">Pages qui renvoient ici <span class="badge">${page.retours.length}</span></h2>
      ${page.retours.length ? UI.html`<ul class="wiki-retours">${page.retours.map((retour) => UI.html`<li data-id="${retour.id}">
          ${lienWiki(retour.id, retour.titre, 'wiki-lien-retour')}<span class="badge neutre">${TYPES[retour.type] || retour.type}</span></li>`)}</ul>`
        : UI.html`<p class="muted wiki-sans-retour">Aucune page ne renvoie ici pour l'instant.</p>`}
    </section>`;
  }

  function blocEnAttente(page) {
    const propositions = page.enAttente;
    return UI.html`<section class="carte wiki-section" id="wiki-en-attente" aria-labelledby="wiki-titre-attente">
      <h2 id="wiki-titre-attente">Propositions en attente sur cette page <span class="badge">${propositions.length}</span></h2>
      <p class="aide">Propositions de l'IA pas encore validées : vous seul les voyez, la page montre l'état validé.</p>
      ${propositions.length ? UI.html`<ul class="wiki-lignes wiki-attente">${propositions.map((proposition) => UI.html`<li data-entree="${proposition.entreeId}">
          <div class="wiki-ligne-tete"><a class="wiki-lien-proposition" href="#/wiki-journal?entree=${encodeURIComponent(proposition.entreeId)}">Proposition ${proposition.entreeId}</a>
            ${proposition.ot ? lienOt(proposition.ot, true) : ''}</div></li>`)}</ul>`
        : UI.html`<p class="muted wiki-sans-attente">Aucune proposition en attente sur cette page.</p>`}
    </section>`;
  }

  // ===========================================================================================
  // 4. Consignation (page d'équipement, en-tête des savoir-faire)
  // ===========================================================================================

  /**
   * Consignation : texte de la fiche tel quel (textContent), document ; jamais de texte d'IA. `reglages` : { id,
   * titre, phrase (en-tête d'un savoir-faire), equipementId, responsable }.
   */
  function blocConsignation(consignation, reglages) {
    const valeur = consignation || { texte: '', document: '' };
    const nomDocument = texte(valeur.document);
    const section = UI.element(UI.html`
      <section class="carte wiki-consignation${reglages.phrase ? ' wiki-entete-sf' : ''}" id="${reglages.id}" aria-labelledby="${reglages.id}-titre">
        <h2 id="${reglages.id}-titre">${UI.icone('alerte')} ${reglages.titre}</h2>
        ${reglages.phrase ? UI.html`<p class="wiki-entete-phrase"><b>${reglages.phrase}</b></p>` : ''}
        ${texte(valeur.texte)
          ? UI.html`<p class="aide">Procédure de la fiche de l'équipement, telle qu'elle a été saisie.</p>
            <div class="wiki-consignation-texte"></div>`
          : UI.html`<p class="wiki-sans-consignation"><b>${MESSAGE_SANS_CONSIGNATION}</b></p>
            ${reglages.responsable && !reglages.phrase ? UI.html`<p><a class="btn btn-secondaire" id="wiki-modifier-consignation"
              href="#/equipement/${encodeURIComponent(reglages.equipementId)}/modifier">${UI.icone('cle')}Saisir la consignation dans la fiche</a></p>` : ''}`}
        ${nomDocument ? UI.html`<p class="wiki-consignation-document">Document : <span class="wiki-document">${nomDocument}</span></p>` : ''}
      </section>`);
    const zoneTexte = UI.$('.wiki-consignation-texte', section);
    if (zoneTexte) zoneTexte.textContent = valeur.texte;      // tel quel : jamais interprété
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

  /** Rattachement d'un savoir-faire (même règle que son en-tête, §20.3) → { equipementId } | { articleId } | { pageId } | {}. */
  function rattachementDe(page) {
    const ligne = Donnees.trouver('wiki_pages', page.pageId) || {};
    let cible = ligne;
    if (!texte(ligne.equipement_id) && !texte(ligne.article_id) && texte(ligne.rattache_a)) {
      cible = Donnees.trouver('wiki_pages', texte(ligne.rattache_a)) || {};
      if (!texte(cible.equipement_id) && !texte(cible.article_id)) return { pageId: texte(ligne.rattache_a) };
    }
    if (Donnees.trouver('equipements', texte(cible.equipement_id))) return { equipementId: texte(cible.equipement_id) };
    if (Donnees.trouver('articles', texte(cible.article_id))) return { articleId: texte(cible.article_id) };
    return {};
  }

  /** En-tête d'un savoir-faire, posé par Prévo (§20.3, CS98) : jamais de texte d'IA. */
  function enteteSavoirFaire(page, contexte) {
    const entete = page.entete || { consignation: null, equipements: [] };
    const rattachement = rattachementDe(page);
    if (rattachement.equipementId) {
      const repere = (entete.equipements[0] && entete.equipements[0].repere) || repereDe(rattachement.equipementId).repere;
      return blocConsignation(entete.consignation, { id: 'wiki-entete', titre: 'Consignation de ' + repere,
        phrase: PHRASE_SAVOIR_FAIRE, equipementId: rattachement.equipementId, responsable: contexte.responsable });
    }
    const section = UI.element(UI.html`<section class="carte wiki-consignation wiki-entete-sf" id="wiki-entete" aria-labelledby="wiki-entete-titre">
      <h2 id="wiki-entete-titre">${UI.icone('alerte')} Consignation des équipements</h2>
      <p class="wiki-entete-phrase"><b>${PHRASE_SAVOIR_FAIRE}</b></p>
      ${entete.equipements.length ? UI.html`<p>Ce composant est monté sur ces équipements ; la consignation de chacun est en tête de sa page :</p>
        <ul class="wiki-jumeaux wiki-entete-equipements">${entete.equipements.map((monte) => UI.html`<li>${lienWiki(monte.equipementId, monte.repere || monte.equipementId)}</li>`)}</ul>`
        : UI.html`<p class="aide">Aucun équipement connu pour ce savoir-faire : voir la consignation de l'équipement sur sa fiche.</p>`}
    </section>`);
    return section;
  }

  // ===========================================================================================
  // 5. Couches calculées : équipement (reprise de la première version), composant, mode
  // ===========================================================================================

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

  function blocPannes(calcul) {
    return UI.html`<section class="carte wiki-section" id="wiki-pannes" aria-labelledby="wiki-titre-pannes">
      <h2 id="wiki-titre-pannes">Pannes habituelles</h2>
      <p class="aide">Les symptômes les plus fréquents des interventions correctives clôturées ; causes et remèdes
        à partir de ${Wiki.SEUILS.otMinimum} cas.</p>
      ${pannesHtml(calcul.pannes, 'Aucune intervention corrective clôturée avec un symptôme sur cet équipement.')}
    </section>`;
  }

  function blocPieces(calcul, liens) {
    const lignes = calcul.pieces.map((piece) => {
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
  function blocDernieres(calcul, liens) {
    const reste = calcul.total - calcul.dernieres.length;
    let suite = '';
    if (reste > 0 && liens) {
      suite = UI.html`<div class="actions"><a class="btn btn-secondaire" id="wiki-voir-autres"
        href="#/ot?equipement=${encodeURIComponent(calcul.equipement.id)}&amp;etat=clotures">${reste > 1
          ? 'Voir les ' + reste + ' autres interventions' : 'Voir l\'autre intervention'}</a></div>`;
    } else if (reste > 0) {
      suite = UI.html`<p class="aide" id="wiki-autres">Et ${pluriel(reste, 'intervention plus ancienne', 'interventions plus anciennes')}.</p>`;
    }
    return UI.html`<section class="carte wiki-section" id="wiki-dernieres" aria-labelledby="wiki-titre-dernieres">
      <h2 id="wiki-titre-dernieres">Dernières interventions <span class="badge">${calcul.total}</span></h2>
      ${calcul.dernieres.length ? UI.html`<ul class="wiki-lignes wiki-interventions">${calcul.dernieres.map((ot) => interventionHtml(ot, liens))}</ul>`
        : UI.html`<p class="muted">Aucune intervention clôturée sur cet équipement.</p>`}
      ${suite}
    </section>`;
  }

  function blocMemeModele(calcul) {
    if (!calcul.memeModele) return '';
    const equipement = calcul.equipement;
    const jumeaux = calcul.memeModele.equipements;
    return UI.html`<section class="carte wiki-section" id="wiki-meme-modele" aria-labelledby="wiki-titre-meme-modele">
      <h2 id="wiki-titre-meme-modele">Même marque et modèle</h2>
      <p class="aide">${equipement.marque} ${equipement.modele} : les pannes de cet équipement et de
        ${jumeaux.length > 1 ? 'ses jumeaux' : 'son jumeau'}, comptées ensemble.</p>
      <ul class="wiki-jumeaux" aria-label="Équipements de même marque et modèle">${jumeaux.map((autre) => UI.html`<li>
        <a href="#/wiki/${encodeURIComponent(autre.id)}">${autre.repere || autre.id}</a></li>`)}</ul>
      ${pannesHtml(calcul.memeModele.pannes, 'Aucune intervention corrective clôturée avec un symptôme sur ces équipements.')}
    </section>`;
  }

  function coucheEquipement(page, contexte) {
    const calcul = page.calcul;
    const elements = [blocConsignation(calcul.consignation, { id: 'wiki-consignation', titre: 'Consignation',
      equipementId: calcul.equipement.id, responsable: contexte.responsable })];
    elements.push(Wiki.champRecherche({ equipementId: calcul.equipement.id, titre: 'Chercher dans l\'historique de cet équipement' }));
    [blocPannes(calcul), blocPieces(calcul, contexte.liens), blocDernieres(calcul, contexte.liens), blocMemeModele(calcul)]
      .filter((bloc) => bloc).forEach((bloc) => elements.push(UI.element(bloc)));
    return elements;
  }

  function uniteDe(articleId) {
    const article = Donnees.trouver('articles', articleId);
    return article && texte(article.unite) ? ' ' + texte(article.unite) : '';
  }

  function intervalleTexte(remplacement) {
    const jours = remplacement.intervalleMedianJours;
    if (jours === null || jours === undefined) return remplacement.nombre < 2 ? 'un seul : pas d\'intervalle' : 'intervalle inconnu';
    return 'intervalle médian : ' + UI.nombreFr(jours) + ' ' + (jours >= 2 ? 'jours' : 'jour');
  }

  function coucheComposant(page, contexte) {
    if (!page.calcul) {
      return [UI.element(UI.html`<section class="carte wiki-section" id="wiki-sans-article" aria-labelledby="wiki-titre-sans-article">
        <h2 id="wiki-titre-sans-article">Article du magasin</h2>
        <p class="wiki-pas-d-article"><b>Pas d'article au magasin</b></p>
        <p class="aide">Page libre : aucun article ne lui correspond, rien n'est calculé pour elle.</p></section>`)];
    }
    const { article, montage, consommations, remplacements } = page.calcul;
    const unite = uniteDe(article.id);
    const vide = (valeur) => texte(valeur) || '–';
    const montrees = consommations.slice(0, Wiki.SEUILS.dernieres);
    const reste = consommations.length - montrees.length;
    return [
      UI.html`<section class="carte wiki-section" id="wiki-article" aria-labelledby="wiki-titre-article">
        <h2 id="wiki-titre-article">Article du magasin</h2>
        <dl class="valeurs wiki-article">
          <dt>Référence</dt><dd>${contexte.liens ? UI.html`<a class="wiki-lien-article" href="#/magasin/article/${encodeURIComponent(article.id)}">${vide(article.reference)}</a>` : vide(article.reference)}</dd>
          <dt>Désignation</dt><dd>${vide(article.designation)}</dd>
          <dt>Fabricant</dt><dd>${vide(article.fabricant)}</dd>
          <dt>Référence fabricant</dt><dd>${vide(article.refFabricant)}</dd>
          <dt>Emplacement</dt><dd>${vide(article.emplacement)}</dd>
          <dt>Stock</dt><dd class="wiki-stock">${UI.nombreFr(article.stock)}${unite}</dd>
        </dl></section>`,
      UI.html`<section class="carte wiki-section" id="wiki-montage" aria-labelledby="wiki-titre-montage">
        <h2 id="wiki-titre-montage">Où il est monté <span class="badge">${montage.length}</span></h2>
        <p class="aide">Équipements de la liste des pièces et équipements où il a été consommé.</p>
        ${montage.length ? UI.html`<ul class="wiki-lignes wiki-montage">${montage.map((monte) => UI.html`<li data-equipement="${monte.equipementId}">
            <div class="wiki-ligne-tete">${lienWiki(monte.equipementId, monte.repere)}<span class="wiki-designation">${repereDe(monte.equipementId).designation}</span></div>
            <div class="carte-meta"><span>${SOURCES_MONTAGE[monte.source] || monte.source}</span>
              ${texte(monte.quantite) ? UI.html`<span>Quantité montée : ${UI.nombreFr(monte.quantite)}</span>` : ''}</div></li>`)}</ul>`
          : UI.html`<p class="muted">Monté sur aucun équipement connu.</p>`}</section>`,
      UI.html`<section class="carte wiki-section" id="wiki-remplacements" aria-labelledby="wiki-titre-remplacements">
        <h2 id="wiki-titre-remplacements">Remplacements par équipement</h2>
        ${remplacements.length ? UI.html`<ul class="wiki-lignes wiki-remplacements">${remplacements.map((remplacement) => UI.html`<li data-equipement="${remplacement.equipementId}">
            <div class="wiki-ligne-tete"><b>${remplacement.repere || remplacement.equipementId}</b></div>
            <div class="carte-meta"><span>${pluriel(remplacement.nombre, 'remplacement', 'remplacements')}</span><span>${intervalleTexte(remplacement)}</span></div></li>`)}</ul>`
          : UI.html`<p class="muted">Jamais remplacé dans les interventions clôturées.</p>`}</section>`,
      UI.html`<section class="carte wiki-section" id="wiki-consommations" aria-labelledby="wiki-titre-consommations">
        <h2 id="wiki-titre-consommations">Consommations <span class="badge">${consommations.length}</span></h2>
        <p class="aide">Interventions clôturées où l'article est sorti du magasin, retours déduits ; les plus récentes d'abord.</p>
        ${montrees.length ? UI.html`<ul class="wiki-lignes wiki-consommations">${montrees.map((consommation) => UI.html`<li data-ot="${consommation.otId}">
            <div class="wiki-ligne-tete">${lienOt(consommation.otId, contexte.liens)}<span class="wiki-date">${UI.dateFr(consommation.date)}</span>
              <span class="badge neutre">${repereDe(consommation.equipementId).repere}</span></div>
            <div class="carte-meta"><span>Quantité : ${UI.nombreFr(consommation.quantite)}${unite}</span></div></li>`)}</ul>`
          : UI.html`<p class="muted">Aucune consommation dans les interventions clôturées.</p>`}
        ${reste > 0 ? UI.html`<p class="aide" id="wiki-autres-consommations">Et ${pluriel(reste, 'consommation plus ancienne', 'consommations plus anciennes')}.</p>` : ''}
      </section>`,
    ].map((bloc) => UI.element(bloc));
  }

  function coucheMode(page) {
    if (!page.calcul) {
      return [UI.element(UI.html`<section class="carte wiki-section" id="wiki-sans-cause" aria-labelledby="wiki-titre-sans-cause">
        <h2 id="wiki-titre-sans-cause">Code cause</h2>
        <p class="wiki-pas-de-cause"><b>Pas de code cause associé</b></p>
        <p class="aide">Page libre : rien n'est calculé pour elle.</p></section>`)];
    }
    const { cause, cas, equipements, remedes } = page.calcul;
    return [UI.element(UI.html`<section class="carte wiki-section" id="wiki-cause" aria-labelledby="wiki-titre-cause">
      <h2 id="wiki-titre-cause">Code cause <span class="badge neutre">${cause.code}</span></h2>
      <p class="wiki-cause-libelle"><b>${cause.libelle}</b></p>
      <p class="wiki-cas-mode">${cas ? pluriel(cas, 'intervention corrective clôturée', 'interventions correctives clôturées') + ' de cette cause'
        : 'Aucune intervention corrective clôturée de cette cause'}</p>
      <h3>Équipements touchés</h3>
      ${equipements.length ? UI.html`<ul class="wiki-lignes wiki-equipements-touches">${equipements.map((touche) => UI.html`<li data-equipement="${touche.equipementId}">
          <div class="wiki-ligne-tete">${lienWiki(touche.equipementId, touche.repere)}<span class="wiki-designation">${pluriel(touche.cas, 'cas', 'cas')}</span></div></li>`)}</ul>`
        : UI.html`<p class="muted">Aucun équipement connu.</p>`}
      <h3>Remèdes appliqués</h3>
      ${remedes.length ? UI.html`<ul class="wiki-remedes-mode">${remedes.map((remede) => UI.html`<li data-code="${remede.code}">
          <span class="wiki-remede">${remede.libelle}</span> : ${remede.fois} fois</li>`)}</ul>`
        : UI.html`<p class="muted">Aucun remède renseigné sur ces cas.</p>`}
      <p class="note wiki-mention">${Wiki.MENTION_STATISTIQUE}</p>
    </section>`)];
  }

  // ===========================================================================================
  // 6. La page
  // ===========================================================================================

  /** Lien de l'en-tête vers la fiche de l'équipement ou de l'article (pas de magasin pour le demandeur). */
  function ficheDe(page, contexte) {
    const equipement = (id) => ({ href: '#/equipement/' + encodeURIComponent(id), libelle: 'Fiche de l\'équipement', icone: 'parc' });
    const article = (id) => (contexte.liens ? { href: '#/magasin/article/' + encodeURIComponent(id), libelle: 'Fiche de l\'article', icone: 'magasin' } : null);
    if (page.type === 'équipement') return equipement(page.id);
    if (page.type === 'composant') return page.calcul ? article(page.calcul.article.id) : null;
    if (page.type !== 'savoir-faire') return null;
    const rattachement = rattachementDe(page);
    if (rattachement.equipementId) return equipement(rattachement.equipementId);
    if (rattachement.articleId) return article(rattachement.articleId);
    if (rattachement.pageId) return { href: '#/wiki/' + encodeURIComponent(rattachement.pageId), libelle: 'Page du composant', icone: 'wiki' };
    return null;
  }

  function enteteHtml(page, contexte) {
    const fiche = ficheDe(page, contexte);
    const calcul = page.type === 'équipement' ? page.calcul : null;
    const marqueModele = calcul ? [calcul.equipement.marque, calcul.equipement.modele].filter(Boolean).join(' ') : '';
    return UI.html`<div class="entete-page">
      <div>
        <div class="fil"><a href="#/wiki">Wiki</a> <span aria-hidden="true">›</span> <span>${TYPES[page.type] || page.type}</span></div>
        <h1>${page.titre || page.id}</h1>
        <p class="wiki-sous-titre"><span class="badge info wiki-type">${TYPES[page.type] || page.type}</span>
          ${calcul ? (marqueModele ? marqueModele + ' · ' : '') + textePannes(calcul.pannes12Mois) : ''}</p>
      </div>
      ${fiche ? UI.html`<div class="actions"><a class="btn btn-secondaire" id="wiki-lien-fiche" href="${fiche.href}">${UI.icone(fiche.icone)}${fiche.libelle}</a></div>` : ''}
    </div>`;
  }

  /**
   * Pose la page `page` (Wiki.page) dans `conteneur`. contexte : { liens (OT et magasin en liens), responsable,
   * index (Wiki.indexDesPages(), pour les liens [[titre]]) }.
   */
  function rendrePage(conteneur, page, reglages) {
    const contexte = Object.assign({}, reglages, { resoudre: resolveur(reglages.index || Wiki.indexDesPages()) });
    const couches = { 'équipement': coucheEquipement, composant: coucheComposant, mode: coucheMode };
    const couche = couches[page.type] ? couches[page.type](page, contexte) : [];
    App.definirTitre('Wiki ' + (page.type === 'équipement' && page.calcul.equipement.repere ? page.calcul.equipement.repere : page.titre));
    UI.remplir(conteneur, UI.html`
      <div class="wiki wiki-page" data-page="${page.id}" data-type="${page.type}" data-equipement="${page.type === 'équipement' ? page.id : ''}">
        ${enteteHtml(page, contexte)}
        ${page.type === 'savoir-faire' ? UI.html`<div class="wiki-zone-entete"></div>` : ''}
        ${couche.length ? UI.html`<div class="wiki-couche" id="wiki-couche">
          <p class="wiki-couche-titre">${UI.icone('indicateurs')}<span>Calculé par Prévo à partir de l'historique, sans IA</span></p>
        </div>` : ''}
        <div class="wiki-zone-texte"></div>
        <div class="wiki-zone-trancher"></div>
        ${blocRetours(page)}
        ${contexte.responsable ? blocEnAttente(page) : ''}
      </div>`);
    if (page.type === 'savoir-faire') UI.$('.wiki-zone-entete', conteneur).replaceWith(enteteSavoirFaire(page, contexte));
    if (couche.length) couche.forEach((element) => UI.$('#wiki-couche', conteneur).appendChild(element));
    UI.$('.wiki-zone-texte', conteneur).replaceWith(blocTexte(page, contexte));
    const zone = UI.$('.wiki-zone-trancher', conteneur);
    if (page.contradictions.length) zone.replaceWith(blocContradictions(page, contexte));
    else zone.remove();
  }

  return { rendrePage };
})());
