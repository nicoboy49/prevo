'use strict';
// Wiki (6/8) — journal du wiki (lot 6 refondu, ARCHITECTURE.md §20.7 ; D105, D106, D107) : validation enchaînée et
// d'un bloc, rattrapage, rejet et « à refaire », relance, écriture à la main, contradictions et décisions,
// visibilité, intégrité. Toutes les écritures par Donnees.modifier ; responsable seulement.
//
// Précisions au contrat (§20.7) :
//  - page d'un changement : `page` (WP-…) quand il est connu, sinon sa clé (« EQ:<équipement> », « ART:<article> »,
//    « WP:<page> », « TITRE:<titre comparable> ») ; une ligne est créée pour une page ancrée encore sans texte et pour
//    une page créée ; la validation inscrit `page` dans chaque changement ;
//  - sous-page créée (§20.4 ; d'un savoir-faire seulement, §20.12) : rattache_a = la ligne de sa mère (un savoir-faire
//    envoyé, donc déjà une ligne ou créé par une entrée plus ancienne, validée avant), jamais equipement_id ni
//    article_id ; seul un savoir-faire se crée (contrôles de wiki-texte.js), à la main aussi ; une ancienne page (mode,
//    sous-page d'équipement ou de composant, Wiki.typeRetire) ne s'écrit plus à la main : elle s'archive ;
//  - lien vers une panne ([[<libellé du symptôme>]], page calculée de Wiki.listeEntites('panne')) : gardé dans `liens`
//    sous son identifiant PANNE-<code>, accepté à la main comme un titre du catalogue ;
//  - `version_avant` (wiki-ingestion.js) compte les propositions plus anciennes en attente sur la page : validées dans
//    l'ordre de `ordre`, chacune trouve la page dans la version attendue ;
//  - dépendance (« touche une même page ») : B, plus récente, dépend de A si A CHANGE une page sur laquelle B a été
//    construite — ses pages concernées (champ `pages`, sauf CAUSE:), celles qu'elle change, et les pages vers
//    lesquelles ses textes font un lien ; clés ramenées à celle de la ligne (page créée puis validée : TITRE:… →
//    WP:…). Une entrée qui passe « à refaire » ajoute ses pages changées à la cascade (dans l'ordre de `ordre`) ; elle
//    perd ses changements, ses contradictions et son rang, et repart dans la file ;
//  - « Valider la sélection » (plusieurs entrées) refuse une entrée qui porte une contradiction ;
//  - une contradiction se tranche sur une entrée « validée » ; elle passe « fermée » avec decision, decide_par,
//    decide_le et la note ; l'entrée `décision` reprend la contradiction et la note (motif) ;
//  - écriture à la main : l'entrée `manuel` est écrite d'abord (« appliquée », avant et après ; les entrées à valider
//    qui touchent la page passent « à refaire »), puis la page (derniere_entree = cette entrée, version vérifiée) ;
//    si la page ne peut pas être écrite, l'entrée passe « refusée » avec la raison. OT permis : les OT clôturés
//    administrativement et ceux que la page cite déjà ; les nombres sont cherchés dans le texte de leurs OT ;
//  - une entrée APPLIQUÉE (son identifiant est le derniere_entree de toutes les pages de ses changements) est validée,
//    quoi que dise encore son statut : c'est ce qui départage deux postes entre deux écritures (validation contre
//    rejet : la validation l'emporte et le motif le dit ; deux validations : une seule s'applique) ;
//  - rattrapage (Wiki.rattraper) : une entrée « à valider » appliquée est marquée « validée » ; pages relues
//    ({ relire: true }) au début de Wiki.valider et de Wiki.ecrire et à l'ouverture du journal, jamais à l'affichage
//    d'une page (D101 : sur les tables chargées, aucun appel réseau tant qu'il n'y a rien à rattraper) ;
//  - visibilité : Wiki.contradictionsDe (contradictions ouvertes des entrées validées) pour tous les profils ;
//    Wiki.enAttenteDe (propositions à valider qui changent la page) au responsable seulement.

Object.assign(Wiki, (() => {

  const DECISIONS = ['ancien', 'nouveau', 'les deux'];
  const { cleDeLigne, idCanonique, titreEquipement, titreArticle } = Wiki;      // clés, titres : wiki-ingestion.js

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  function json(valeur, defaut) {
    try { return JSON.parse(valeur) || defaut; } catch (erreur) { return defaut; }
  }

  const rang = (entree) => Number(entree.ordre) || 0;
  const parRang = (a, b) => rang(a) - rang(b) || (texte(a.id) < texte(b.id) ? -1 : 1);
  const ErreurValidation = (message) => new Donnees.ErreurValidation(message);
  const changementsDe = (entree) => json(entree.changements, []).filter((changement) => changement && typeof changement === 'object');
  const contradictionsDe = (entree) => json(entree.contradictions, []).filter((c) => c && typeof c === 'object');
  const estActive = (ligne) => texte(ligne.statut) !== 'archivée';

  // ===========================================================================================
  // 1. Profil, pages et clés
  // ===========================================================================================

  function estResponsable(options) {
    if (options && typeof options.responsable === 'boolean') return options.responsable;
    return typeof App !== 'undefined' && Boolean(App) && typeof App.estResponsable === 'function' && App.estResponsable();
  }

  const exigerResponsable = () => {
    if (!estResponsable()) throw ErreurValidation(I18n.t('wiki.exiger_responsable.reserve_responsable_wiki_valide'));
  };

  function nomDuResponsable() {
    const profil = typeof App !== 'undefined' && App ? App.profil : null;
    if (profil && texte(profil.nom)) return texte(profil.nom);
    return (typeof App !== 'undefined' && App && typeof App.libelleProfil === 'function' && texte(App.libelleProfil()))
      || I18n.t('wiki.nom_du_responsable.responsable');
  }

  /** Ligne de wiki_pages d'un changement ou d'une clé (null si la page n'a pas encore de ligne). */
  function ligneDeCle(lignes, cle, pageId, archivees) {
    if (texte(pageId)) return lignes.find((ligne) => ligne.id === texte(pageId)) || null;
    // archivees : pages archivées comprises, après les actives (intégrité, entrée appliquée à une page archivée depuis).
    const actives = archivees ? lignes.filter(estActive).concat(lignes.filter((l) => !estActive(l))) : lignes.filter(estActive);
    const valeur = texte(cle);
    if (valeur.startsWith('EQ:')) {
      return actives.find((l) => texte(l.type) === 'équipement' && texte(l.equipement_id) === valeur.slice(3)) || null;
    }
    if (valeur.startsWith('ART:')) {
      return actives.find((l) => texte(l.type) === 'composant' && texte(l.article_id) === valeur.slice(4)) || null;
    }
    if (valeur.startsWith('WP:')) return lignes.find((l) => l.id === valeur.slice(3)) || null;
    if (valeur.startsWith('TITRE:')) return actives.find((l) => Wiki.comparable(l.titre) === valeur.slice(6)) || null;
    return null;
  }

  /** Clé d'une page ramenée à celle de sa ligne quand elle en a une (TITRE:… d'une page validée depuis → WP:…). */
  function normaliser(cle, lignesPages) {
    const ligne = ligneDeCle(lignesPages, cle, '');
    return ligne ? cleDeLigne(ligne) : texte(cle);
  }

  /** Pages que change une entrée et, parmi elles, celles qu'elle crée → { changees, creees }, en clés normalisées. */
  function pagesDe(entree, lignesPages) {
    const pages = { changees: new Set(), creees: new Set() };
    changementsDe(entree).forEach((changement) => {
      const ligne = ligneDeCle(lignesPages, changement.cle, changement.page);
      const cle = ligne ? cleDeLigne(ligne) : normaliser(changement.cle, lignesPages);
      pages.changees.add(cle);
      if (changement.creation) pages.creees.add(cle);
    });
    return pages;
  }

  /**
   * B dépend de A (plus ancienne) si A change une page sur laquelle B a été construite (ses pages concernées, sans la
   * cause, et celles qu'elle change), ou crée une page vers laquelle B fait un lien (A rejetée, elle disparaîtrait). Un
   * lien vers une page que A ne fait que modifier n'en dépend pas (démo, 2026-10-23 : un lien vers un équipement liait
   * toute proposition à la dernière qui changeait cet équipement).
   */
  function depend(b, pagesA, lignesPages) {
    const lues = texte(b.pages).split(';').map(texte).filter((cle) => cle && !cle.startsWith('CAUSE:'))
      .map((cle) => normaliser(cle, lignesPages)).concat(Array.from(pagesDe(b, lignesPages).changees));
    const liens = changementsDe(b).flatMap((changement) => Wiki.liensDe(changement.apres || ''))
      .map((titre) => normaliser('TITRE:' + Wiki.comparable(titre), lignesPages));
    return lues.some((cle) => pagesA.changees.has(cle)) || liens.some((cle) => pagesA.creees.has(cle));
  }

  /** Pannes (pages calculées, wiki-entites.js : codes symptôme qui ont un cas) → [{ id (PANNE-…), titre }]. */
  const pannes = () => (typeof Wiki.listeEntites === 'function' && Wiki.listeEntites('panne', { profil: 'responsable' })) || [];

  /** Titre comparable → identifiant canonique (pannes, équipements, articles, pages actives), pour le champ `liens`. */
  function indexDesLiens(lignesPages) {
    const index = new Map(pannes().map((panne) => [Wiki.comparable(panne.titre), panne.id]));
    Donnees.lignes('equipements').forEach((e) => index.set(Wiki.comparable(titreEquipement(e)), texte(e.id)));
    Donnees.lignes('articles').forEach((a) => index.set(Wiki.comparable(titreArticle(a)), texte(a.id)));
    lignesPages.filter(estActive).forEach((ligne) => index.set(Wiki.comparable(ligne.titre), idCanonique(ligne)));
    return index;
  }

  /** Ancienne page d'avant la refonte 2 (§20.12) → ce qu'elle est (« mode », « sous-page d'équipement »…), sinon ''. */
  function typeRetire(ligne) {
    const type = texte(ligne && ligne.type);
    if (!Wiki.RUBRIQUES[type]) return type || I18n.t('wiki.type_retire.sans_type');
    const mere = type !== 'savoir-faire' && texte(ligne.rattache_a) ? Donnees.trouver('wiki_pages', texte(ligne.rattache_a)) : null;
    if (!(mere && texte(mere.type) === type)) return '';
    return type === 'équipement' ? I18n.t('wiki.type_retire.sous_page_equipement') : I18n.t('wiki.type_retire.sous_page_composant');
  }

  function liensDuTexte(valeur, index) {
    return Array.from(new Set(Wiki.liensDe(valeur).map((titre) => index.get(Wiki.comparable(titre))).filter(Boolean))).join(';');
  }

  /**
   * Pose le texte et ce qui en découle sur une ligne : ot_cites, liens, version + 1, origine, dernière entrée,
   * validation. `parIa` : la proposition vient de l'IA (origine « IA » ou « IA et manuel »).
   */
  function poserTexte(ligne, valeur, contexte) {
    const avant = texte(ligne.origine);
    ligne.texte = valeur;
    ligne.ot_cites = Wiki.citationsDe(valeur).join(';');
    ligne.liens = liensDuTexte(valeur, contexte.index);
    ligne.version = String((Number(ligne.version) || 0) + 1);
    if (contexte.parIa) {
      ligne.origine = avant === 'manuel' || avant === 'IA et manuel' ? 'IA et manuel' : 'IA';
      ligne.modele = contexte.modele;
    } else {
      ligne.origine = avant === 'IA' || avant === 'IA et manuel' ? 'IA et manuel' : 'manuel';
    }
    Object.assign(ligne, { cle: Wiki.comparable(ligne.titre), derniere_entree: contexte.entreeId, valide_par: contexte.par,
      valide_le: contexte.maintenant, modifie_le: contexte.maintenant });
  }

  /**
   * Nouvelle ligne pour une clé (page ancrée sans ligne, ou page créée), rattachée à la page `vise` (identifiant
   * canonique, ou vide) : un savoir-faire en fait une sous-page (§20.4 : rattache_a = la ligne de sa mère, aucun
   * ancrage propre ; refusé pour un autre type, §20.12) ; sinon l'équipement ou l'article visé (equipement_id,
   * article_id), ou la ligne visée (rattache_a).
   */
  function nouvelleLigne(lignes, outils, cle, changement, vise) {
    const ligne = { id: outils.nouvelId(lignes), type: texte(changement.type), titre: texte(changement.titre), version: '0',
      statut: 'active', cree_le: outils.maintenant() };
    const prefixe = vise.startsWith('EQ-') ? 'EQ:' : (vise.startsWith('ART-') ? 'ART:' : 'WP:');
    const mere = vise ? ligneDeCle(lignes, prefixe + vise, '') : null;
    const typeVise = { 'EQ:': 'équipement', 'ART:': 'composant' }[prefixe] || texte(mere && mere.type);
    if (cle.startsWith('EQ:')) {
      const equipement = Donnees.trouver('equipements', cle.slice(3)) || { id: cle.slice(3) };
      Object.assign(ligne, { type: 'équipement', equipement_id: cle.slice(3), titre: titreEquipement(equipement) });
    } else if (cle.startsWith('ART:')) {
      const article = Donnees.trouver('articles', cle.slice(4)) || { id: cle.slice(4) };
      Object.assign(ligne, { type: 'composant', article_id: cle.slice(4), titre: titreArticle(article) });
    } else if (ligne.type !== 'savoir-faire') {     // proposition d'avant la refonte 2 (§20.12 : mode, composant libre, sous-page)
      throw ErreurValidation(I18n.t('wiki.nouvelle_ligne.seule_page_savoir_faire', { ligneTitre: ligne.titre }));
    } else if (vise && typeVise === ligne.type) {
      if (!mere) throw ErreurValidation(I18n.t('wiki.nouvelle_ligne.page_mere_pas_encore', { ligneTitre: ligne.titre }));
      ligne.rattache_a = mere.id;
    } else if (vise.startsWith('EQ-')) ligne.equipement_id = vise;
    else if (vise.startsWith('ART-')) ligne.article_id = vise;
    else if (vise) ligne.rattache_a = vise;
    lignes.push(ligne);
    return ligne;
  }

  // ===========================================================================================
  // 2. Cascade « à refaire » (D105)
  // ===========================================================================================

  /**
   * Fait passer « à refaire » les entrées à valider de rang supérieur à `apres` qui dépendent des pages `cles` (texte
   * perdu) ou `creees` (jamais créées), en y ajoutant les pages qu'elles changeaient et créaient. Renvoie leurs
   * identifiants. Dans une fonction de Donnees.modifier.
   */
  function cascade(lignesJournal, cles, apres, motif, maintenant, creees) {
    const lignesPages = Donnees.lignes('wiki_pages');
    const normalisees = (liste) => new Set(Array.from(liste || []).map((cle) => normaliser(cle, lignesPages)));
    const perdues = { changees: normalisees(cles), creees: normalisees(creees) };
    const marquees = [];
    lignesJournal.filter((entree) => texte(entree.statut) === 'à valider' && rang(entree) > apres).sort(parRang)
      .forEach((entree) => {
        const deja = appliqueeDans(entree, lignesPages);        // validée sur un autre poste : rien à refaire
        if (deja) { marquerValidee(entree, deja, ''); return; }
        if (!depend(entree, perdues, lignesPages)) return;
        const siennes = pagesDe(entree, lignesPages);
        ['changees', 'creees'].forEach((nom) => siennes[nom].forEach((cle) => perdues[nom].add(cle)));
        Object.assign(entree, { statut: 'à refaire', motif, changements: '', contradictions: '', ordre: '', traite_le: maintenant });
        marquees.push(entree.id);
      });
    return marquees;
  }

  // ===========================================================================================
  // 3. Validation, rattrapage, rejet, relance
  // ===========================================================================================

  /**
   * Lignes de wiki_pages d'une entrée si elle y est APPLIQUÉE (son identifiant est le derniere_entree de toutes les
   * pages de ses changements), sinon null. Une entrée appliquée est validée, quoi que dise encore son statut : c'est
   * la règle qui départage deux postes (validation contre rejet, deux validations) entre deux écritures.
   */
  function appliqueeDans(entree, lignesPages) {
    const changements = changementsDe(entree);
    if (!changements.length) return null;
    const lignes = changements.map((c) => ligneDeCle(lignesPages, c.cle, c.page, true));
    return lignes.every((ligne) => ligne && texte(ligne.derniere_entree) === entree.id) ? lignes : null;
  }

  /** Marque « validée » une entrée appliquée (dans une fonction de Donnees.modifier sur wiki_journal). */
  function marquerValidee(entree, pages, motif) {
    Object.assign(entree, { statut: 'validée', decide_par: texte(pages[0].valide_par), decide_le: texte(pages[0].valide_le),
      changements: JSON.stringify(changementsDe(entree).map((c, n) => Object.assign({}, c, { page: pages[n].id }))) });
    if (motif) entree.motif = motif;
  }

  /**
   * Rattrapage (§20.7) : une entrée « à valider » appliquée aux pages sans que son statut ait pu être écrit est
   * marquée « validée ». options.relire : pages relues d'abord (validation, écriture, ouverture du journal) ; sinon sur
   * les tables chargées (affichage d'une page, D101). Aucun choix n'est fait : rien n'est réservé au responsable. → nombre.
   */
  async function rattraper(options) {
    if (options && options.relire) await Donnees.rechargerTable('wiki_pages');
    const lignesPages = Donnees.lignes('wiki_pages');
    const aMarquer = Donnees.lignes('wiki_journal').filter((e) => texte(e.statut) === 'à valider' && appliqueeDans(e, lignesPages));
    if (!aMarquer.length) return 0;
    return Donnees.modifier('wiki_journal', (lignes) => {
      let nombre = 0;
      lignes.filter((e) => texte(e.statut) === 'à valider').forEach((entree) => {
        const pages = appliqueeDans(entree, lignesPages);
        if (!pages) return;
        marquerValidee(entree, pages, '');
        nombre += 1;
      });
      return nombre;
    }, { journal: false });
  }

  /** Applique une entrée à valider (une écriture de wiki_pages) → ids des lignes, ou null si une version a changé. */
  async function appliquer(entree, par) {
    const changements = changementsDe(entree);
    if (!changements.length) return [];
    try {
      return await Donnees.modifier('wiki_pages', (lignes, outils) => {
        const trouvees = changements.map((c) => ligneDeCle(lignes, c.cle, c.page));
        trouvees.forEach((ligne, n) => {
          if ((ligne ? Number(ligne.version) || 0 : 0) !== (Number(changements[n].version_avant) || 0)) {
            const erreur = ErreurValidation(I18n.t('wiki.appliquer.page_change_depuis_proposition', { titre: texte(changements[n].titre) }));
            erreur.pageChangee = true;
            throw erreur;
          }
        });
        // Lignes nouvelles, dans l'ordre des changements : une page ancrée encore sans texte (machine, article) ou une page
        // créée ; la mère d'une sous-page a toujours déjà sa ligne (un savoir-faire envoyé, §20.6), aucun ordre à imposer.
        const pages = trouvees.slice();
        changements.forEach((c, n) => {
          const vise = !pages[n] && texte(c.rattacheA) ? indexDesLiens(lignes).get(Wiki.comparable(c.rattacheA)) || '' : '';
          if (!pages[n]) pages[n] = nouvelleLigne(lignes, outils, texte(c.cle), c, vise);
        });
        const index = indexDesLiens(lignes);
        const contexte = { index, parIa: true, modele: texte(entree.modele), entreeId: entree.id, par, maintenant: outils.maintenant() };
        pages.forEach((ligne, n) => poserTexte(ligne, changements[n].apres || '', contexte));
        return pages.map((ligne) => ligne.id);
      }, { action: 'proposition ' + entree.id + ' validée' + (texte(entree.ot_id) ? ' (' + entree.ot_id + ')' : '') });
    } catch (erreur) {
      if (erreur && erreur.pageChangee) return null;
      throw erreur;
    }
  }

  /**
   * Valide des propositions (§20.7), dans l'ordre de `ordre`, chacune d'un bloc. Refus (rien n'est fait) : profil
   * autre que responsable, entrée inconnue ou pas « à valider », entrée plus ancienne à valider (hors sélection) qui
   * touche une même page, contradiction dans une sélection de plusieurs. Une page qui a changé fait passer l'entrée
   * (et ses suivantes) « à refaire ». → { validees: [ids], aRefaire: [ids] }.
   */
  async function valider(ids) {
    exigerResponsable();
    await rattraper({ relire: true });
    const choisis = Array.from(new Set((ids || []).map(texte).filter(Boolean)));
    if (!choisis.length) throw ErreurValidation(I18n.t('wiki.valider.aucune_proposition_choisie'));
    const journal = Donnees.lignes('wiki_journal');
    const entrees = choisis.map((id) => {
      const entree = journal.find((e) => e.id === id);
      if (!entree || texte(entree.statut) !== 'à valider') {
        throw ErreurValidation(entree ? I18n.t('wiki.valider.proposition_pas_valider', { id, entreeStatut: entree.statut })
          : I18n.t('wiki.valider.proposition_pas_valider_sans_statut', { id }));
      }
      return entree;
    }).sort(parRang);
    if (entrees.length > 1) {
      const avec = entrees.filter((e) => contradictionsDe(e).length).map((e) => e.id);
      if (avec.length) {
        throw ErreurValidation(I18n.t('wiki.valider.propositions_contradiction_valider', { propositions: avec.join(', ') }));
      }
    }
    const lignesPages = Donnees.lignes('wiki_pages');
    entrees.forEach((entree) => {
      const avant = journal.filter((e) => texte(e.statut) === 'à valider' && !choisis.includes(e.id) && rang(e) < rang(entree)
        && depend(entree, pagesDe(e, lignesPages), lignesPages));
      if (avant.length) {
        throw ErreurValidation(I18n.t('wiki.valider.validez_abord_ete_construite', { n: avant.length, precedentes: avant.map((e) => e.id).join(', '), entreeId: entree.id }));
      }
    });
    const par = nomDuResponsable();
    const bilan = { validees: [], aRefaire: [] };
    for (const entree of entrees) {
      const fraiche = Donnees.trouver('wiki_journal', entree.id);
      if (!fraiche || texte(fraiche.statut) !== 'à valider') continue;      // passée « à refaire » par une précédente
      const pages = await appliquer(fraiche, par);
      if (pages === null) {
        await Donnees.rechargerTable('wiki_pages');
        const lignesFraiches = Donnees.lignes('wiki_pages');
        const issue = await Donnees.modifier('wiki_journal', (lignes, outils) => {
          const ligne = lignes.find((e) => e.id === entree.id);
          if (!ligne || texte(ligne.statut) !== 'à valider') return { aRefaire: [] };
          const deja = appliqueeDans(ligne, lignesFraiches);          // validée entre-temps sur un autre poste
          if (deja) { marquerValidee(ligne, deja, ''); return { validee: true, aRefaire: [] }; }
          const { changees, creees } = pagesDe(ligne, lignesFraiches);
          const motif = I18n.t('wiki.valider.refaire_page_change_depuis');
          Object.assign(ligne, { statut: 'à refaire', motif, changements: '', contradictions: '', ordre: '', traite_le: outils.maintenant() });
          return { aRefaire: [ligne.id].concat(cascade(lignes, changees, rang(entree), I18n.t('wiki.valider.refaire_suit', { ligneId: ligne.id }), outils.maintenant(), creees)) };
        }, { journal: false });
        if (issue.validee) bilan.validees.push(entree.id);
        bilan.aRefaire.push(...issue.aRefaire);
        continue;
      }
      // Les pages portent cette entrée : elle est validée, même si un autre poste l'a rejetée ou fait passer « à refaire »
      // entre-temps (ses changements et son rang sont alors rétablis, et le motif le dit).
      await Donnees.modifier('wiki_journal', (lignes, outils) => {
        const ligne = lignes.find((e) => e.id === entree.id);
        if (!ligne || texte(ligne.statut) === 'validée') return;
        const autre = texte(ligne.statut) !== 'à valider' ? texte(ligne.statut) : '';
        Object.assign(ligne, { statut: 'validée', decide_par: par, decide_le: outils.maintenant(), ordre: fraiche.ordre,
          contradictions: fraiche.contradictions,
          changements: JSON.stringify(changementsDe(fraiche).map((c, n) => Object.assign({}, c, { page: pages[n] }))) });
        if (autre) ligne.motif = I18n.t('wiki.valider.validee_ici_alors_autre', { autre });
      }, { journal: false });
      bilan.validees.push(entree.id);
    }
    return bilan;
  }

  /**
   * Rejette une proposition avec un motif (obligatoire) : « rejetée » ; les entrées à valider suivantes qui touchent
   * une même page passent « à refaire » (cascade). → { rejetee, aRefaire: [ids] }.
   */
  async function rejeter(id, motif) {
    exigerResponsable();
    if (!texte(motif)) throw ErreurValidation(I18n.t('wiki.rejeter.motif_rejet_obligatoire'));
    const par = nomDuResponsable();
    await Donnees.rechargerTable('wiki_pages');
    const lignesPages = Donnees.lignes('wiki_pages');
    const resultat = await Donnees.modifier('wiki_journal', (lignes, outils) => {
      const ligne = lignes.find((e) => e.id === texte(id));
      if (!ligne || texte(ligne.statut) !== 'à valider') {
        throw ErreurValidation(I18n.t('wiki.valider.proposition_pas_valider_sans_statut', { id: texte(id) }));
      }
      const deja = appliqueeDans(ligne, lignesPages);
      if (deja) { marquerValidee(ligne, deja, ''); return { dejaValidee: true }; }
      const maintenant = outils.maintenant();
      const { changees, creees } = pagesDe(ligne, lignesPages);
      Object.assign(ligne, { statut: 'rejetée', motif: texte(motif), decide_par: par, decide_le: maintenant });
      return { rejetee: ligne.id, aRefaire: cascade(lignes, changees, rang(ligne), I18n.t('wiki.rejeter.refaire_rejetee', { ligneId: ligne.id }), maintenant, creees) };
    }, { journal: false });
    if (resultat.dejaValidee) {
      throw ErreurValidation(I18n.t('wiki.rejeter.proposition_vient_etre_validee', { id: texte(id) }));
    }
    return resultat;
  }

  /** Relance l'OT d'une entrée « rejetée » ou « refusée » : une nouvelle entrée « en file ». → son identifiant. */
  async function remettreEnFile(id) {
    exigerResponsable();
    return Donnees.modifier('wiki_journal', (lignes, outils) => {
      const ligne = lignes.find((e) => e.id === texte(id));
      if (!ligne || texte(ligne.nature) !== 'ingestion' || !['rejetée', 'refusée'].includes(texte(ligne.statut))) {
        throw ErreurValidation(I18n.t('wiki.remettre_en_file.seul_ot_proposition_rejetee'));
      }
      const autre = lignes.find((e) => e !== ligne && texte(e.ot_id) === texte(ligne.ot_id) && texte(e.nature) === 'ingestion'
        && !['rejetée', 'refusée'].includes(texte(e.statut)));
      if (autre) throw ErreurValidation(I18n.t('wiki.remettre_en_file.ot_deja_entree', { ot_id: ligne.ot_id, autreStatut: autre.statut, autreId: autre.id }));
      const ot = Donnees.trouver('ordres_travail', texte(ligne.ot_id)) || {};
      const nouvelle = { id: outils.nouvelId(lignes), nature: 'ingestion', ot_id: ligne.ot_id,
        date_intervention: texte(ot.date_fin) || texte(ligne.date_intervention), statut: 'en file', anterieure: '0', essais: '0',
        motif: I18n.t('wiki.remettre_en_file.relance_apres', { ligneId: ligne.id }), cree_le: outils.maintenant() };
      lignes.push(nouvelle);
      return nouvelle.id;
    }, { journal: false });
  }

  // ===========================================================================================
  // 4. Écriture à la main (§20.7) et contradictions (D107)
  // ===========================================================================================

  /** Page visée par une écriture à la main : { ligne, cle, type, titre, rattache } (ligne null : page encore sans ligne). */
  function cibleDe(cible) {
    const lignesPages = Donnees.lignes('wiki_pages');
    const id = texte(cible && cible.pageId);
    if (id.startsWith('WP-')) {
      const ligne = lignesPages.find((l) => l.id === id);
      if (!ligne) throw ErreurValidation(I18n.t('wiki.cible_de.page_wiki_introuvable', { id }));
      if (!estActive(ligne)) throw ErreurValidation(I18n.t('wiki.cible_de.page_archivee', { ligneTitre: texte(ligne.titre) }));
      return { ligne, cle: cleDeLigne(ligne), type: texte(ligne.type), titre: texte(ligne.titre) };
    }
    if (id.startsWith('EQ-') || id.startsWith('ART-')) {
      const equipement = id.startsWith('EQ-') && Donnees.trouver('equipements', id);
      const article = id.startsWith('ART-') && Donnees.trouver('articles', id);
      if (!equipement && !article) throw ErreurValidation(I18n.t('wiki.cible_de.equipement_article_introuvable', { id }));
      const cle = (equipement ? 'EQ:' : 'ART:') + id;
      return { ligne: ligneDeCle(lignesPages, cle, ''), cle, type: equipement ? 'équipement' : 'composant',
        titre: equipement ? titreEquipement(equipement) : titreArticle(article) };
    }
    const nouvelle = cible && cible.nouvelle;
    if (!nouvelle) throw ErreurValidation(I18n.t('wiki.cible_de.page_ecrire_non_precisee'));
    // Seul un savoir-faire se crée (§20.12) : les contrôles refusent un autre type, avec la raison.
    return { ligne: null, nouvelle: true, cle: 'TITRE:' + Wiki.comparable(nouvelle.titre), type: texte(nouvelle.type),
      titre: texte(nouvelle.titre), rattache: texte(nouvelle.rattacheA) };
  }

  /** Page d'un identifiant canonique, pour le contrôle du rattachement (savoir-faire, sous-page : `mere` si c'en est une). */
  function pageEnvoyee(id) {
    const page = id ? Wiki.page(id) : null;
    const ligne = page ? Donnees.trouver('wiki_pages', page.pageId || page.id) : null;
    const mere = ligne && texte(ligne.rattache_a) ? Donnees.trouver('wiki_pages', texte(ligne.rattache_a)) : null;
    return page ? { titre: page.titre, type: page.type, texte: page.texte || '',
      mere: mere && texte(mere.type) === page.type ? texte(mere.titre) : '' } : null;
  }

  function controlerEcriture(page, valeur) {
    const retire = page.ligne ? typeRetire(page.ligne) : '';
    if (retire) throw ErreurValidation(I18n.t('wiki.controler_ecriture.page_type_page_retire', { pageTitre: page.titre, retire }));
    const avant = page.ligne ? page.ligne.texte || '' : '';
    const rattachement = page.rattache ? pageEnvoyee(page.rattache) : null;
    // Une sous-page modifiée porte sa mère : ses refus de longueur ne conseillent pas de la découper (un seul niveau).
    const envoyees = page.nouvelle ? [rattachement].filter(Boolean) : [{ titre: page.titre, type: page.type, texte: avant,
      mere: page.ligne ? (pageEnvoyee(page.ligne.id) || {}).mere || '' : '' }];
    const cites = Wiki.citationsDe(valeur);
    const permis = Donnees.lignes('ordres_travail').filter((ot) => texte(ot.statut) === 'Clôturé administrativement')
      .map((ot) => ot.id).concat(Wiki.citationsDe(avant));
    const sources = {};
    cites.forEach((id) => { sources[id] = Wiki.texteSourceOt(id); });
    const controle = Wiki.controlerProposition({ rien: false, contradictions: [], pages: [{
      action: page.nouvelle ? 'creer' : 'modifier', titre: page.titre, type: page.type,
      rattacheA: rattachement ? rattachement.titre : '', texte: valeur }] }, {
      manuel: true, pagesEnvoyees: envoyees,
      catalogue: Wiki.catalogue().concat(pannes()).map((p) => ({ titre: p.titre, type: p.type || 'panne' })),
      otPermis: permis, sources });
    if (!controle.ok) {
      const erreur = ErreurValidation(I18n.t('wiki.controler_ecriture.texte_refuse', { raisons: controle.raisons.join(' ') }));
      erreur.raisons = controle.raisons;
      throw erreur;
    }
  }

  /**
   * Écriture à la main (§20.7) : cible { pageId } (WP-…, EQ-…, ART-…) ou { nouvelle: { type (savoir-faire), titre,
   * rattacheA (identifiant canonique) } } ; options { version (vue à l'écran : conflit si la page a changé),
   * archiver, motif }. Contrôles du §20.6 (sauf archivage). → { pageId (canonique), ligneId, entreeId }.
   */
  async function ecrire(cible, valeur, options) {
    exigerResponsable();
    const opts = options || {};
    await rattraper({ relire: true });           // pages relues ; une validation interrompue est d'abord rattrapée
    const page = cibleDe(cible);
    const archiver = Boolean(opts.archiver);
    if (archiver && !page.ligne) throw ErreurValidation(I18n.t('wiki.ecrire.seule_page_texte_archive'));
    const nouveau = archiver ? (page.ligne.texte || '') : String(valeur === null || valeur === undefined ? '' : valeur).trim();
    if (!archiver) controlerEcriture(page, nouveau);
    const version = page.ligne ? Number(page.ligne.version) || 0 : 0;
    const attendue = opts.version === undefined || opts.version === null ? version : Number(opts.version) || 0;
    if (attendue !== version) throw ErreurValidation(I18n.t('wiki.ecrire.page_ete_modifiee_entre'));
    const par = nomDuResponsable();
    const avant = page.ligne ? page.ligne.texte || '' : '';
    const entreeId = await Donnees.modifier('wiki_journal', (lignes, outils) => {
      const maintenant = outils.maintenant();
      const id = outils.nouvelId(lignes);
      lignes.push({ id, nature: 'manuel', statut: 'appliquée', anterieure: '0', essais: '0', pages: page.cle,
        ordre: String(lignes.reduce((max, e) => Math.max(max, rang(e)), 0) + 1),
        changements: JSON.stringify([{ page: page.ligne ? page.ligne.id : '', cle: page.cle, type: page.type, titre: page.titre,
          creation: !page.ligne, archivage: archiver, version_avant: version, avant, apres: nouveau }]),
        contradictions: '[]', cree_le: maintenant, traite_le: maintenant, decide_par: par, decide_le: maintenant, motif: texte(opts.motif) });
      cascade(lignes, new Set([page.cle]), -Infinity, I18n.t('wiki.ecrire.refaire_page_ecrite_main', { id }), maintenant);
      return id;
    }, { journal: false });
    try {
      const ligneId = await Donnees.modifier('wiki_pages', (lignes, outils) => {
        let ligne = page.ligne ? lignes.find((l) => l.id === page.ligne.id) : ligneDeCle(lignes, page.cle, '');
        if ((ligne ? Number(ligne.version) || 0 : 0) !== version) {
          throw ErreurValidation(I18n.t('wiki.ecrire.page_ete_modifiee_autre_poste'));
        }
        if (page.nouvelle && ligne) throw ErreurValidation(I18n.t('wiki.ecrire.page_titre_existe_deja'));
        if (!ligne) ligne = nouvelleLigne(lignes, outils, page.cle, { type: page.type, titre: page.titre }, texte(page.rattache));
        const contexte = { index: indexDesLiens(lignes), parIa: false, entreeId, par, maintenant: outils.maintenant() };
        poserTexte(ligne, nouveau, contexte);
        if (archiver) ligne.statut = 'archivée';
        return ligne.id;
      }, { action: archiver ? 'page du wiki archivée (' + entreeId + ')' : 'page du wiki écrite à la main (' + entreeId + ')' });
      const ligne = Donnees.trouver('wiki_pages', ligneId);
      if (!page.ligne) {                         // page créée : son WP-… noté dans l'entrée (intégrité, même archivée)
        await Donnees.modifier('wiki_journal', (lignes) => {
          const entree = lignes.find((e) => e.id === entreeId);
          if (entree) entree.changements = JSON.stringify(changementsDe(entree).map((c) => Object.assign({}, c, { page: ligneId })));
        }, { journal: false }).catch(() => {});
      }
      return { pageId: ligne ? idCanonique(ligne) : ligneId, ligneId, entreeId };
    } catch (erreur) {
      await Donnees.modifier('wiki_journal', (lignes) => {
        const ligne = lignes.find((e) => e.id === entreeId);
        if (ligne) Object.assign(ligne, { statut: 'refusée', raisons: (erreur && erreur.message) || String(erreur) });
      }, { journal: false }).catch(() => {});
      throw erreur;
    }
  }

  /**
   * Tranche une contradiction (D107) : decision ∈ ancien, nouveau, les deux ; la contradiction (rang dans l'entrée
   * « validée ») passe « fermée » et une entrée `décision` « appliquée » la trace. → { decisionId, pageId } (`nouveau` :
   * l'écran ouvre ensuite l'écriture à la main de pageId).
   */
  async function trancher(entreeId, rangContradiction, decision, note) {
    exigerResponsable();
    if (!DECISIONS.includes(decision)) throw ErreurValidation(I18n.t('wiki.trancher.decision_inconnue_ancien_nouveau', { decision }));
    const par = nomDuResponsable();
    const resultat = await Donnees.modifier('wiki_journal', (lignes, outils) => {
      const entree = lignes.find((e) => e.id === texte(entreeId));
      if (!entree || texte(entree.statut) !== 'validée') throw ErreurValidation(I18n.t('wiki.trancher.contradiction_introuvable_proposition_validee'));
      const contradictions = contradictionsDe(entree);
      const contradiction = contradictions[Number(rangContradiction)];
      if (!contradiction || texte(contradiction.statut) !== 'ouverte') throw ErreurValidation(I18n.t('wiki.trancher.contradiction_pas_ouverte'));
      const maintenant = outils.maintenant();
      Object.assign(contradiction, { statut: 'fermée', decision, decide_par: par, decide_le: maintenant, note: texte(note) });
      entree.contradictions = JSON.stringify(contradictions);
      const id = outils.nouvelId(lignes);
      lignes.push({ id, nature: 'décision', ot_id: entree.ot_id, statut: 'appliquée', anterieure: entree.anterieure || '0',
        essais: '0', pages: texte(contradiction.pageCle), changements: '[]',
        contradictions: JSON.stringify([Object.assign({ entree: entree.id, rang: Number(rangContradiction) }, contradiction)]),
        cree_le: maintenant, traite_le: maintenant, decide_par: par, decide_le: maintenant, motif: texte(note) });
      return { decisionId: id, cle: texte(contradiction.pageCle), titre: texte(contradiction.page) };
    }, { journal: false });
    const ligne = ligneDeCle(Donnees.lignes('wiki_pages'), resultat.cle, '')
      || Donnees.lignes('wiki_pages').find((l) => estActive(l) && Wiki.comparable(l.titre) === Wiki.comparable(resultat.titre));
    const cle = resultat.cle;
    const pageId = ligne ? idCanonique(ligne) : (cle.startsWith('EQ:') || cle.startsWith('ART:') ? cle.slice(cle.indexOf(':') + 1) : '');
    return { decisionId: resultat.decisionId, pageId };
  }

  // ===========================================================================================
  // 5. Visibilité : crochets de Wiki.page (wiki-calculs.js)
  // ===========================================================================================

  /** Clés d'une page de Wiki.page : { id (canonique), pageId (WP-… de sa ligne), titre }. */
  function clesDePage(page) {
    const id = texte(page && page.id);
    const cles = new Set();
    if (id.startsWith('EQ-')) cles.add('EQ:' + id);
    else if (id.startsWith('ART-')) cles.add('ART:' + id);
    else if (id) cles.add('WP:' + id);
    if (texte(page && page.pageId)) cles.add('WP:' + texte(page.pageId));
    if (texte(page && page.titre)) cles.add('TITRE:' + Wiki.comparable(page.titre));
    const lignesPages = Donnees.lignes('wiki_pages');
    return new Set(Array.from(cles).map((cle) => normaliser(cle, lignesPages)).concat(Array.from(cles)));
  }

  /**
   * Contradictions ouvertes des propositions validées qui portent sur la page (tous les profils) →
   * [{ entreeId, rang, ot, otSource, phrase, observation, anterieure, libelle, depuis }].
   */
  function contradictionsDePage(page) {
    const cles = clesDePage(page);
    const lignesPages = Donnees.lignes('wiki_pages');
    return Donnees.lignes('wiki_journal').filter((e) => texte(e.statut) === 'validée').sort(parRang)
      .flatMap((entree) => contradictionsDe(entree).map((contradiction, n) => ({ entree, contradiction, n })))
      .filter(({ contradiction }) => texte(contradiction.statut) === 'ouverte'
        && (cles.has(normaliser(contradiction.pageCle, lignesPages)) || cles.has('TITRE:' + Wiki.comparable(contradiction.page))))
      .map(({ entree, contradiction, n }) => {
        const anterieure = texte(entree.anterieure) === '1';
        return { entreeId: entree.id, rang: n, ot: (contradiction.ot || []).slice(), otSource: texte(entree.ot_id),
          phrase: texte(contradiction.phrase), observation: texte(contradiction.observation), anterieure,
          libelle: anterieure ? I18n.t('wiki.contradictions_de_page.observation_anterieure_faits_page') : I18n.t('wiki.contradictions_de_page.dit_nouvel_ot'),
          depuis: texte(entree.decide_le) || texte(entree.traite_le) };
      });
  }

  /** Propositions « à valider » qui changent la page, au responsable seulement → [{ entreeId, ot, creation, rang }]. */
  function enAttenteDe(page, options) {
    if (!estResponsable(options)) return [];
    const cles = clesDePage(page);
    const lignesPages = Donnees.lignes('wiki_pages');
    return Donnees.lignes('wiki_journal').filter((e) => texte(e.statut) === 'à valider').sort(parRang)
      .flatMap((entree) => changementsDe(entree)
        .filter((c) => cles.has(normaliser(c.cle, lignesPages)) || (texte(c.page) && cles.has('WP:' + texte(c.page))))
        .map((c) => ({ entreeId: entree.id, ot: texte(entree.ot_id), creation: Boolean(c.creation), rang: rang(entree) })));
  }

  // ===========================================================================================
  // 6. Intégrité (§20.7, CS111)
  // ===========================================================================================

  /**
   * Intégrité du wiki → { ok, ecarts: [{ page, entree, message }] } : pour chaque page, les entrées appliquées
   * (ingestion « validée », manuel « appliquée ») dans l'ordre de `ordre` forment une chaîne (avant de la première vide,
   * avant de chacune = après de la précédente, texte de la page = après de la dernière) ; les OT intégrés le sont
   * par date d'intervention croissante, sauf les entrées `anterieure` ; une page qui a un texte a une entrée ;
   * options.envois (bilan de Wiki.traiterFile) : jamais deux envois en même temps sur une même clé.
   */
  function verifierIntegrite(options) {
    const ecarts = [];
    const lignesPages = Donnees.lignes('wiki_pages');
    const parPage = new Map();
    Donnees.lignes('wiki_journal').filter((e) => (texte(e.nature) === 'ingestion' && texte(e.statut) === 'validée')
      || (texte(e.nature) === 'manuel' && texte(e.statut) === 'appliquée')).sort(parRang).forEach((entree) => {
      changementsDe(entree).forEach((changement) => {
        const ligne = ligneDeCle(lignesPages, changement.cle, changement.page, true);
        const cle = ligne ? ligne.id : texte(changement.cle);
        if (!parPage.has(cle)) parPage.set(cle, []);
        parPage.get(cle).push({ entree, changement });
      });
    });
    parPage.forEach((suite, cle) => {
      const ligne = lignesPages.find((l) => l.id === cle);
      const nom = ligne ? texte(ligne.titre) : cle;
      let precedent = '';
      let plusRecente = '';
      suite.forEach(({ entree, changement }) => {
        if ((changement.avant || '') !== precedent) {
          ecarts.push({ page: nom, entree: entree.id, message: I18n.t('wiki.verifier_integrite.avant_pas_texte_laisse') });
        }
        precedent = changement.apres || '';
        if (texte(entree.nature) !== 'ingestion' || texte(entree.anterieure) === '1') return;
        const date = texte(entree.date_intervention);
        if (plusRecente && date && date < plusRecente) {
          ecarts.push({ page: nom, entree: entree.id, message: I18n.t('wiki.verifier_integrite.ot_integre_apres_ot', { ot_id: entree.ot_id }) });
        }
        if (date > plusRecente) plusRecente = date;
      });
      if (!ligne) ecarts.push({ page: nom, entree: suite[suite.length - 1].entree.id, message: I18n.t('wiki.verifier_integrite.page_absente_wiki_pages') });
      else if ((ligne.texte || '') !== precedent) {
        ecarts.push({ page: nom, entree: suite[suite.length - 1].entree.id, message: I18n.t('wiki.verifier_integrite.texte_page_pas_apres') });
      }
    });
    lignesPages.filter((ligne) => texte(ligne.texte) && !parPage.has(ligne.id))
      .forEach((ligne) => ecarts.push({ page: texte(ligne.titre), entree: '', message: I18n.t('wiki.verifier_integrite.texte_sans_entree_journal') }));
    const envois = (options && options.envois) || [];
    envois.forEach((a, n) => envois.slice(n + 1).forEach((b) => {
      const communes = (a.cles || []).filter((cle) => (b.cles || []).includes(cle));
      const ensemble = a.debut < (b.fin === null ? Infinity : b.fin) && b.debut < (a.fin === null ? Infinity : a.fin);
      if (communes.length && ensemble) {
        ecarts.push({ page: communes.join(', '), entree: '', message: I18n.t('wiki.verifier_integrite.envois_simultanes', { premier: a.ot, second: b.ot }) });
      }
    }));
    return { ok: ecarts.length === 0, ecarts };
  }

  return {
    valider, rattraper, rejeter, remettreEnFile, ecrire, trancher, verifierIntegrite,
    contradictionsDe: contradictionsDePage, enAttenteDe, typeRetire, pannesDuWiki: pannes,
  };
})());
