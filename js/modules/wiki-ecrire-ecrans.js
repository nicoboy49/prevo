'use strict';
// Wiki (9/9) — écriture à la main et contrôle du wiki (lot 6 refondu, ARCHITECTURE.md §20.7, §20.9 ; D97, D108) :
// écran #/wiki-ecrire/<id> (EQ-…, ART-…, WP-…) et #/wiki-ecrire/nouvelle?type=<type>&rattache=<id canonique>
// (responsable seulement), et Wiki.controleDuWiki(), calculé sans IA et sans rien écrire (la vue « Contrôle du wiki »
// du journal, wiki-journal-ecrans.js, et l'index #/wiki l'affichent). Dernier fichier du module.
//
// Précisions au contrat (§20.9) :
//  - écriture : zone de texte du balisage pré-remplie avec le texte validé, aide (balisage, rubriques du type,
//    aucune consigne de sécurité), motif facultatif ; « Enregistrer » → Wiki.ecrire(cible, texte, { version (celle
//    affichée), motif }) ; un refus affiche ses raisons (erreur.raisons) une par ligne, rien n'est écrit ; succès :
//    retour à #/wiki/<pageId> ; « Archiver » (page qui a une ligne) demande une confirmation dans la page, puis
//    Wiki.ecrire(cible, null, { archiver: true, version }) et retour à #/wiki ; nouvelle page : composant (libre),
//    mode (code cause facultatif) ou savoir-faire (rattaché à un équipement ou à un composant) ;
//  - Wiki.controleDuWiki() → [{ type, page (id canonique), titre, message }], types dans cet ordre : lien-casse
//    ([[titre]] inconnu du texte ; identifiant du champ liens inexistant ou page archivée), orpheline (page libre —
//    mode sans code cause, composant sans article, savoir-faire sans équipement, article ni rattachement — vers
//    laquelle aucune autre page active ne fait de lien, par son identifiant ou son titre), sans-ot (aucune citation
//    dans le texte, page vide comprise), titre-proche (même Wiki.formeDuTitre entre pages actives, une ligne par
//    page), trop-longue (plus de phrasesMax phrases ou de motsMax mots, rubriques comprises, comme §20.6),
//    contradiction-ancienne (ouverte sur une entrée validée depuis plus de contradictionAncienneJours, comptés depuis
//    decide_le, sinon traite_le), ancrage-disparu (equipement_id ou article_id absent ou inactif) ; pages actives.

Object.assign(Wiki, (() => {

  const TABLES = ['wiki_pages', 'wiki_journal', 'equipements', 'articles', 'codes_defaillance'];
  const TYPES_NOUVELLE = ['composant', 'mode', 'savoir-faire'];
  const LIBELLES = { 'équipement': 'équipement', composant: 'composant ou pièce', mode: 'mode de défaillance',
    'savoir-faire': 'savoir-faire' };
  const S = Wiki.SEUILS;

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  function estActive(ligne) {
    return texte(ligne.statut) !== 'archivée';
  }

  function titreEquipement(equipement) {
    return [texte(equipement.repere), texte(equipement.designation)].filter(Boolean).join(' — ');
  }

  function titreArticle(article) {
    return texte(article.designation) || texte(article.reference).replace(/^'/, '') || texte(article.id);
  }

  /** { id (canonique), titre } d'une ligne de wiki_pages : EQ-… ou ART-… quand son ancrage existe, sinon WP-…. */
  function repereDe(ligne) {
    const equipement = texte(ligne.type) === 'équipement' && Donnees.trouver('equipements', texte(ligne.equipement_id));
    if (equipement) return { id: texte(equipement.id), titre: titreEquipement(equipement) };
    const article = texte(ligne.type) === 'composant' && texte(ligne.article_id) && Donnees.trouver('articles', texte(ligne.article_id));
    if (article) return { id: texte(article.id), titre: titreArticle(article) };
    return { id: texte(ligne.id), titre: texte(ligne.titre) };
  }

  function jours(depuis) {
    const lu = /^(\d{4})-(\d{2})-(\d{2})/.exec(texte(depuis));
    const jour = /^(\d{4})-(\d{2})-(\d{2})/.exec(Donnees.aujourdhui());
    if (!lu || !jour) return 0;
    return Math.round((Date.UTC(+jour[1], jour[2] - 1, +jour[3]) - Date.UTC(+lu[1], lu[2] - 1, +lu[3])) / 86400000);
  }

  // ===========================================================================================
  // 1. Contrôle du wiki (D108) : calculé, rien n'est corrigé
  // ===========================================================================================

  function controleDuWiki() {
    const lignes = Donnees.lignes('wiki_pages');
    const actives = lignes.filter(estActive);
    const problemes = { 'lien-casse': [], orpheline: [], 'sans-ot': [], 'titre-proche': [], 'trop-longue': [],
      'contradiction-ancienne': [], 'ancrage-disparu': [] };
    const noter = (type, ligne, message) => { const r = repereDe(ligne); problemes[type].push({ type, page: r.id, titre: r.titre, message }); };
    const titres = new Set(actives.map((l) => Wiki.comparable(repereDe(l).titre)).concat(actives.map((l) => Wiki.comparable(l.titre))));
    Donnees.lignes('equipements').forEach((e) => titres.add(Wiki.comparable(titreEquipement(e))));
    Donnees.lignes('articles').forEach((a) => titres.add(Wiki.comparable(titreArticle(a))));
    const sources = new Map();                    // cible (identifiant ou TITRE:forme) → pages actives qui y renvoient
    const relier = (cible, source) => { if (!sources.has(cible)) sources.set(cible, new Set()); sources.get(cible).add(source); };
    actives.forEach((ligne) => {
      Wiki.liensDe(ligne.texte).forEach((titre) => {
        relier('TITRE:' + Wiki.comparable(titre), ligne.id);
        if (!titres.has(Wiki.comparable(titre))) noter('lien-casse', ligne, 'lien [[' + titre + ']] vers une page inconnue');
      });
      texte(ligne.liens).split(';').map(texte).filter(Boolean).forEach((id) => {
        relier(id, ligne.id);
        const table = id.startsWith('EQ-') ? 'equipements' : (id.startsWith('ART-') ? 'articles' : 'wiki_pages');
        const cible = Donnees.trouver(table, id);
        if (!cible) noter('lien-casse', ligne, 'lien vers ' + id + ', page inexistante');
        else if (table === 'wiki_pages' && !estActive(cible)) noter('lien-casse', ligne, 'lien vers « ' + texte(cible.titre) + ' » (' + id + '), page archivée');
      });
    });
    const libre = (l) => ({ mode: !texte(l.cause_code), composant: !texte(l.article_id),
      'savoir-faire': !texte(l.equipement_id) && !texte(l.article_id) && !texte(l.rattache_a) })[texte(l.type)] === true;
    const liee = (l) => [l.id, repereDe(l).id, 'TITRE:' + Wiki.comparable(l.titre)]
      .some((cible) => Array.from(sources.get(cible) || []).some((source) => source !== l.id));
    actives.filter((l) => libre(l) && !liee(l)).forEach((l) => noter('orpheline', l, 'aucune page ne renvoie ici et elle n\'est rattachée à rien'));
    actives.filter((l) => !Wiki.citationsDe(l.texte).length)
      .forEach((l) => noter('sans-ot', l, texte(l.texte) ? 'son texte ne cite aucun OT' : 'page vide : aucun OT cité'));
    const parForme = new Map();
    actives.forEach((l) => { const forme = Wiki.formeDuTitre(repereDe(l).titre); if (forme) parForme.set(forme, (parForme.get(forme) || []).concat([l])); });
    parForme.forEach((memes) => memes.length > 1 && memes.forEach((l) => noter('titre-proche', l, 'titre trop proche de '
      + memes.filter((m) => m !== l).map((m) => '« ' + repereDe(m).titre + ' »').join(', '))));
    actives.forEach((l) => {
      const rubriques = Wiki.lireTexte(l.texte).rubriques;
      const phrases = rubriques.reduce((n, r) => n + r.phrases.length, 0);
      const mots = rubriques.reduce((n, r) => n + Wiki.nombreDeMots(r.nom) + r.phrases.reduce((m, p) => m + Wiki.nombreDeMots(p.propre), 0), 0);
      if (phrases > S.phrasesMax || mots > S.motsMax) {
        noter('trop-longue', l, phrases + ' phrases et ' + mots + ' mots (au plus ' + S.phrasesMax + ' phrases et ' + S.motsMax + ' mots)');
      }
    });
    Donnees.lignes('wiki_journal').filter((e) => texte(e.statut) === 'validée').forEach((entree) => {
      const depuis = texte(entree.decide_le) || texte(entree.traite_le);
      if (jours(depuis) <= S.contradictionAncienneJours) return;
      let liste = [];
      try { liste = JSON.parse(entree.contradictions || '[]') || []; } catch (erreur) { liste = []; }
      liste.filter((c) => c && texte(c.statut) === 'ouverte').forEach((c) => {
        const cle = texte(c.pageCle);
        const ligne = cle.startsWith('WP:') ? lignes.find((l) => l.id === cle.slice(3))
          : actives.find((l) => Wiki.comparable(l.titre) === (cle.startsWith('TITRE:') ? cle.slice(6) : Wiki.comparable(c.page)));
        const id = ligne ? repereDe(ligne).id : cle.slice(cle.indexOf(':') + 1);
        problemes['contradiction-ancienne'].push({ type: 'contradiction-ancienne', page: id, titre: texte(c.page) || id,
          message: 'ouverte depuis le ' + UI.dateFr(depuis) + ' (' + [texte(entree.ot_id), entree.id].filter(Boolean).join(', ') + ')' });
      });
    });
    actives.forEach((l) => [['equipement_id', 'equipements', 'équipement'], ['article_id', 'articles', 'article']].forEach(([champ, table, nom]) => {
      const id = texte(l[champ]);
      const cible = id ? Donnees.trouver(table, id) : null;
      if (id && !cible) noter('ancrage-disparu', l, nom + ' ' + id + ' absent');
      else if (cible && texte(cible.actif) === '0') noter('ancrage-disparu', l, nom + ' ' + id + ' inactif');
    }));
    return Object.keys(problemes).flatMap((type) => problemes[type]);
  }

  // ===========================================================================================
  // 2. Écran #/wiki-ecrire/<id> et #/wiki-ecrire/nouvelle
  // ===========================================================================================

  function aideHtml(type) {
    return UI.html`<h2 id="wj-titre-aide">Comment écrire</h2>
      <ul class="wj-aide-liste">
        <li><code>## Rubrique</code> commence une rubrique. Pour une page ${LIBELLES[type] || type} :
          <span class="wj-rubriques">${(Wiki.RUBRIQUES[type] || []).map((r, n) => UI.html`${n ? ', ' : ''}<span class="wj-rubrique-nom">« ${r} »</span>`)}</span>, dans cet ordre.</li>
        <li><code>- phrase [OT-AAAA-NNNN]</code> : une phrase par ligne, qui cite au moins un OT clôturé administrativement.</li>
        <li><code>[[Titre d'une page]]</code> dans une phrase : lien vers une autre page du wiki.</li>
        <li>Aucun comptage ni aucune date : les nombres de cas viennent de Prévo ; un nombre écrit doit figurer dans un OT cité.</li>
        <li class="wj-aide-securite"><b>Aucune consigne de sécurité</b> : elle se saisit dans la consignation de l'équipement.</li>
      </ul>
      <p class="aide">Mêmes contrôles que pour l'IA, sauf que vous pouvez retirer une phrase ou un OT cité. Chaque écriture entre au journal du wiki.</p>`;
  }

  function optionsRattachement(choisi) {
    const option = (id, titre) => UI.html`<option value="${id}"${id === choisi ? UI.brut(' selected') : ''}>${titre}</option>`;
    const libres = Donnees.lignes('wiki_pages').filter((l) => estActive(l) && texte(l.type) === 'composant' && !texte(l.article_id));
    return UI.html`<option value="">Choisir…</option>
      <optgroup label="Équipements">${Donnees.lignes('equipements').map((e) => option(texte(e.id), titreEquipement(e) || e.id))}</optgroup>
      <optgroup label="Composants">${Donnees.lignes('articles').map((a) => option(texte(a.id), titreArticle(a)))
        .concat(libres.map((l) => option(texte(l.id), texte(l.titre))))}</optgroup>`;
  }

  function champsNouvelle(type, rattache) {
    const causes = Donnees.lignes('codes_defaillance').filter((c) => texte(c.famille) === 'cause');
    return UI.html`<div class="form-grille wj-nouvelle-champs">
      <div class="champ"><label class="libelle" for="wj-type">Type de page</label>
        <select id="wj-type" name="type">${TYPES_NOUVELLE.map((t) => UI.html`<option value="${t}"${t === type ? UI.brut(' selected') : ''}>${LIBELLES[t]}</option>`)}</select></div>
      <div class="champ"><label class="libelle" for="wj-titre">Titre <span class="requis" aria-hidden="true">*</span></label>
        <input id="wj-titre" name="titre" maxlength="120" aria-required="true" aria-describedby="wj-titre-erreur" autocomplete="off">
        <p class="erreur-champ" id="wj-titre-erreur" role="alert" hidden></p></div>
      <div class="champ large wj-champ-rattache"><label class="libelle" for="wj-rattache">Rattaché à</label>
        <select id="wj-rattache" name="rattache">${optionsRattachement(rattache)}</select>
        <p class="aide">Un savoir-faire se rattache à un équipement ou à un composant ; sa page reprend la consignation de l'équipement.</p></div>
      <div class="champ large wj-champ-cause"><label class="libelle" for="wj-cause">Code cause (facultatif)</label>
        <select id="wj-cause" name="cause"><option value="">Aucun</option>${causes.map((c) => UI.html`<option value="${texte(c.code)}">${c.code} — ${c.libelle}</option>`)}</select></div>
    </div>`;
  }

  function archiverHtml(titre) {
    return UI.html`<section class="carte wj-archiver" aria-labelledby="wj-titre-archiver">
      <h2 id="wj-titre-archiver">Archiver la page</h2>
      <p class="aide">La page sort du wiki ; son texte reste au journal. Rien n'est effacé.</p>
      <div class="actions"><button type="button" class="btn btn-danger wj-archiver-demande">Archiver</button></div>
      <div class="wj-confirmation" role="alert" hidden>
        <p><b>Archiver la page « ${titre} » ?</b> Elle n'apparaîtra plus dans le wiki ni dans la recherche.</p>
        <div class="actions"><button type="button" class="btn btn-danger wj-archiver-confirmer">Confirmer l'archivage</button>
          <button type="button" class="btn btn-fantome wj-archiver-annuler">Annuler</button></div>
      </div>
    </section>`;
  }

  /** Refus d'une écriture : les raisons une par ligne (contrôles), sinon le message ; rien n'a été écrit. */
  function montrerRefus(zone, erreur) {
    const raisons = erreur && Array.isArray(erreur.raisons) ? erreur.raisons : [];
    if (!(erreur instanceof Donnees.ErreurValidation)) App.signalerErreur(erreur, 'écriture dans le wiki');
    UI.remplir(zone, UI.bandeau('important', raisons.length
      ? UI.html`<p><b>Texte refusé, rien n'a été écrit :</b></p><ul class="wj-raisons">${raisons.map((r) => UI.html`<li>${r}</li>`)}</ul>`
      : UI.html`<p><b>Rien n'a été écrit :</b> ${(erreur && erreur.message) || String(erreur)}</p>`));
    zone.scrollIntoView({ block: 'nearest' });
  }

  function afficherIntrouvable(conteneur, id) {
    UI.remplir(conteneur, UI.html`<div class="wiki wj wj-ecrire">
      <div class="entete-page"><div><div class="fil"><a href="#/wiki">Wiki</a></div><h1>Page introuvable</h1></div></div>
      ${UI.vide('Aucune page active ne porte l\'identifiant « ' + id + ' »', 'Elle a peut-être été archivée sur un autre poste.', 'wiki')}
      <p><a class="btn btn-secondaire" href="#/wiki">Retour au wiki</a></p></div>`);
  }

  async function afficherEcriture(conteneur, parametres) {
    const id = texte(parametres && parametres.id);
    const requete = (parametres && parametres.requete) || new URLSearchParams();
    const nouvelle = id === 'nouvelle';
    const page = nouvelle ? null : Wiki.page(id);
    if (!nouvelle && !page) {
      App.definirTitre('Page introuvable');
      afficherIntrouvable(conteneur, id);
      return;
    }
    const ligne = page && page.pageId ? Donnees.trouver('wiki_pages', page.pageId) : null;
    const version = ligne ? Number(ligne.version) || 0 : 0;
    const type = nouvelle ? (TYPES_NOUVELLE.includes(requete.get('type')) ? requete.get('type') : 'mode') : page.type;
    const retour = nouvelle ? '#/wiki' : '#/wiki/' + encodeURIComponent(id);
    const attente = page ? new Set((page.enAttente || []).map((e) => e.entreeId)).size : 0;
    App.definirTitre(nouvelle ? 'Nouvelle page du wiki' : 'Modifier ' + page.titre);
    UI.remplir(conteneur, UI.html`<div class="wiki wj wj-ecrire" data-page="${nouvelle ? '' : id}" data-version="${version}">
      <div class="entete-page"><div>
        <div class="fil"><a href="#/wiki">Wiki</a>${page ? UI.html` <span aria-hidden="true">›</span> <a href="${retour}">${page.titre}</a>` : ''}</div>
        <h1>${nouvelle ? 'Nouvelle page du wiki' : 'Modifier la page'}</h1>
        <p>${page ? page.titre + ' · ' + (LIBELLES[type] || type) + ' · version ' + version
          : 'Une page de composant, de mode de défaillance ou de savoir-faire, écrite à la main.'}</p>
      </div></div>
      <div class="wj-annonce" aria-live="polite"></div>
      ${attente ? UI.html`<div class="alerte attention" role="status">${UI.icone('alerte')}<div class="alerte-texte"><p>${attente > 1
        ? attente + ' propositions à valider portent sur cette page : enregistrer les fera passer « à refaire » (leurs OT reviennent dans la file).'
        : 'Une proposition à valider porte sur cette page : enregistrer la fera passer « à refaire » (son OT revient dans la file).'}</p></div></div>` : ''}
      <div class="wj-ecrire-grille">
        <form class="carte wj-formulaire" novalidate>
          ${nouvelle ? champsNouvelle(type, texte(requete.get('rattache'))) : ''}
          <div class="champ"><label class="libelle" for="wj-texte">Texte de la page</label>
            <textarea id="wj-texte" name="texte" rows="16" spellcheck="true" placeholder="## Rubrique
- Phrase qui cite son OT [OT-2026-0042]"></textarea></div>
          <div class="champ"><label class="libelle" for="wj-motif-ecriture">Motif (facultatif)</label>
            <input id="wj-motif-ecriture" name="motif" maxlength="300" autocomplete="off" placeholder="Ex. remise en ordre après relecture"></div>
          <div class="actions"><button type="submit" class="btn btn-primaire wj-enregistrer">${UI.icone('sauvegarde')}Enregistrer</button>
            <a class="btn btn-fantome" href="${retour}">Annuler</a></div>
        </form>
        <aside class="carte wj-aide-balisage" aria-labelledby="wj-titre-aide">${aideHtml(type)}</aside>
      </div>
      ${ligne ? archiverHtml(page.titre) : ''}
    </div>`);
    const racine = UI.$('.wj-ecrire', conteneur);
    const zone = UI.$('.wj-annonce', racine);
    const formulaire = UI.$('.wj-formulaire', racine);
    UI.$('#wj-texte', racine).value = page ? page.texte || '' : '';
    if (nouvelle) brancherNouvelle(racine);
    let enCours = false;
    formulaire.addEventListener('submit', async (evenement) => {
      evenement.preventDefault();
      if (enCours) return;
      const cible = nouvelle ? lireNouvelle(racine) : { pageId: id };
      if (!cible) return;
      enCours = true;
      UI.$('.wj-enregistrer', racine).disabled = true;
      try {
        const resultat = await Wiki.ecrire(cible, UI.$('#wj-texte', racine).value,
          { version: nouvelle ? undefined : version, motif: UI.$('#wj-motif-ecriture', racine).value });
        App.marquerSaisie(false);
        UI.toast('Page du wiki enregistrée.', 'succes');
        App.naviguer('#/wiki/' + encodeURIComponent(resultat.pageId));
      } catch (erreur) {
        montrerRefus(zone, erreur);
      } finally {
        enCours = false;
        UI.$('.wj-enregistrer', racine).disabled = false;
      }
    });
    if (ligne) brancherArchivage(racine, zone, id, version);
  }

  function brancherNouvelle(racine) {
    const choix = UI.$('#wj-type', racine);
    const montrer = () => {
      UI.$('.wj-champ-rattache', racine).hidden = choix.value !== 'savoir-faire';
      UI.$('.wj-champ-cause', racine).hidden = choix.value !== 'mode';
      UI.remplir(UI.$('.wj-aide-balisage', racine), aideHtml(choix.value));
    };
    choix.addEventListener('change', montrer);
    montrer();
  }

  /** Cible d'une nouvelle page, ou null (titre manquant : message sous le champ). */
  function lireNouvelle(racine) {
    const champ = UI.$('#wj-titre', racine);
    const erreur = UI.$('#wj-titre-erreur', racine);
    const titre = texte(champ.value);
    erreur.hidden = Boolean(titre);
    if (!titre) {
      erreur.textContent = 'Le titre est obligatoire.';
      champ.setAttribute('aria-invalid', 'true');
      champ.focus();
      return null;
    }
    champ.removeAttribute('aria-invalid');
    const type = UI.$('#wj-type', racine).value;
    return { nouvelle: { type, titre, rattacheA: type === 'savoir-faire' ? UI.$('#wj-rattache', racine).value : '',
      causeCode: type === 'mode' ? UI.$('#wj-cause', racine).value : '' } };
  }

  function brancherArchivage(racine, zone, id, version) {
    const bloc = UI.$('.wj-archiver', racine);
    const demande = UI.$('.wj-archiver-demande', bloc);
    const confirmation = UI.$('.wj-confirmation', bloc);
    const basculer = (ouvrir) => {
      confirmation.hidden = !ouvrir;
      demande.closest('.actions').hidden = ouvrir;
      (ouvrir ? UI.$('.wj-archiver-confirmer', bloc) : demande).focus();
    };
    demande.addEventListener('click', () => basculer(true));
    UI.$('.wj-archiver-annuler', bloc).addEventListener('click', () => basculer(false));
    UI.$('.wj-archiver-confirmer', bloc).addEventListener('click', async (evenement) => {
      const bouton = evenement.currentTarget;
      bouton.disabled = true;
      try {
        await Wiki.ecrire({ pageId: id }, null, { archiver: true, version });
        App.marquerSaisie(false);
        UI.toast('Page archivée : elle sort du wiki, son texte reste au journal.', 'succes');
        App.naviguer('#/wiki');
      } catch (erreur) {
        bouton.disabled = false;
        montrerRefus(zone, erreur);
      }
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'wiki-ecrire',
      route: /^#\/wiki-ecrire\/(?<id>[^/?]+)$/,
      titre: 'Écrire dans le wiki',
      parent: 'wiki',
      profils: ['responsable'],
      tables: TABLES,
      afficher: afficherEcriture,
    });
  });

  return { controleDuWiki };
})());
