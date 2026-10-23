'use strict';
// Wiki (6/8) — journal du wiki (lot 6 refondu, ARCHITECTURE.md §20.7 ; D105, D106, D107) : validation enchaînée et
// d'un bloc, rattrapage, rejet et « à refaire », relance, écriture à la main, contradictions et décisions,
// visibilité, intégrité. Toutes les écritures par Donnees.modifier ; responsable seulement.
//
// Précisions au contrat (§20.7) :
//  - page d'un changement : `page` (WP-…) quand il est connu, sinon sa clé (« EQ:<équipement> », « ART:<article> »,
//    « WP:<page> », « TITRE:<titre comparable> ») ; une ligne est créée pour une page ancrée encore sans texte et pour
//    une page créée ; la validation inscrit `page` dans chaque changement ;
//  - sous-page créée (§20.4) : rattache_a = la ligne de sa mère (de même type, créée d'abord : pages modifiées avant pages
//    créées), jamais equipement_id ni article_id ; à la main, sous une page qui a déjà une ligne ;
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
//  - rattrapage (Wiki.rattraper, pages relues, appelé par les écrans, au début de Wiki.valider et de Wiki.ecrire) :
//    une entrée « à valider » appliquée est marquée « validée » ;
//  - visibilité : Wiki.contradictionsDe (contradictions ouvertes des entrées validées) pour tous les profils ;
//    Wiki.enAttenteDe (propositions à valider qui changent la page) au responsable seulement.

Object.assign(Wiki, (() => {

  const DECISIONS = ['ancien', 'nouveau', 'les deux'];
  const MESSAGE_RESERVE = 'Réservé au responsable : le wiki se valide et s\'écrit depuis son profil.';
  const { cleDeLigne, idCanonique, titreEquipement, titreArticle } = Wiki;      // clés, titres : wiki-ingestion.js

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  function json(valeur, defaut) {
    try { return JSON.parse(valeur) || defaut; } catch (erreur) { return defaut; }
  }

  function rang(entree) {
    return Number(entree.ordre) || 0;
  }

  function parRang(a, b) {
    return rang(a) - rang(b) || (texte(a.id) < texte(b.id) ? -1 : 1);
  }

  function ErreurValidation(message) {
    return new Donnees.ErreurValidation(message);
  }

  function changementsDe(entree) {
    return json(entree.changements, []).filter((changement) => changement && typeof changement === 'object');
  }

  function contradictionsDe(entree) {
    return json(entree.contradictions, []).filter((contradiction) => contradiction && typeof contradiction === 'object');
  }

  // ===========================================================================================
  // 1. Profil, pages et clés
  // ===========================================================================================

  function estResponsable(options) {
    if (options && typeof options.responsable === 'boolean') return options.responsable;
    return typeof App !== 'undefined' && Boolean(App) && typeof App.estResponsable === 'function' && App.estResponsable();
  }

  function exigerResponsable() {
    if (!estResponsable()) throw ErreurValidation(MESSAGE_RESERVE);
  }

  function nomDuResponsable() {
    const profil = typeof App !== 'undefined' && App ? App.profil : null;
    if (profil && texte(profil.nom)) return texte(profil.nom);
    return (typeof App !== 'undefined' && App && typeof App.libelleProfil === 'function' && texte(App.libelleProfil()))
      || 'Responsable';
  }

  function estActive(ligne) {
    return texte(ligne.statut) !== 'archivée';
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

  /** Pages que change une entrée (ses changements), en clés normalisées. */
  function changeesDe(entree, lignesPages) {
    return new Set(changementsDe(entree).map((changement) => {
      const ligne = ligneDeCle(lignesPages, changement.cle, changement.page);
      return ligne ? cleDeLigne(ligne) : normaliser(changement.cle, lignesPages);
    }));
  }

  /**
   * Pages sur lesquelles une entrée a été construite : ses pages concernées (sans la cause), celles qu'elle change,
   * et les pages vers lesquelles ses textes font un lien (une page créée par une autre proposition).
   */
  function luesDe(entree, lignesPages) {
    const cles = texte(entree.pages).split(';').map(texte).filter((cle) => cle && !cle.startsWith('CAUSE:'));
    changementsDe(entree).forEach((changement) => Wiki.liensDe(changement.apres || '')
      .forEach((titre) => cles.push('TITRE:' + Wiki.comparable(titre))));
    const lues = new Set(cles.map((cle) => normaliser(cle, lignesPages)));
    changeesDe(entree, lignesPages).forEach((cle) => lues.add(cle));
    return lues;
  }

  /** B dépend de A (plus ancienne) si A change une page sur laquelle B a été construite. */
  function depend(b, changeesParA, lignesPages) {
    return Array.from(luesDe(b, lignesPages)).some((cle) => changeesParA.has(cle));
  }

  /** Titre comparable → identifiant canonique (équipements, articles, pages actives), pour le champ `liens`. */
  function indexDesLiens(lignesPages) {
    const index = new Map();
    Donnees.lignes('equipements').forEach((e) => index.set(Wiki.comparable(titreEquipement(e)), texte(e.id)));
    Donnees.lignes('articles').forEach((a) => index.set(Wiki.comparable(titreArticle(a)), texte(a.id)));
    lignesPages.filter(estActive).forEach((ligne) => index.set(Wiki.comparable(ligne.titre), idCanonique(ligne)));
    return index;
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
   * canonique, ou vide) : une page de même type en fait une sous-page (§20.4 : rattache_a = la ligne de sa mère, aucun
   * ancrage propre) ; sinon l'équipement ou l'article visé (equipement_id, article_id), ou la ligne visée (rattache_a).
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
    } else if (vise && typeVise === ligne.type) {
      if (!mere) throw ErreurValidation('La page mère de « ' + ligne.titre + ' » n\'a pas encore de texte : écrivez-la d\'abord.');
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
   * Fait passer « à refaire » les entrées à valider de rang supérieur à `apres` construites sur une page de `cles`
   * (pages dont le texte n'est plus celui qu'elles ont lu), en ajoutant à `cles` les pages qu'elles changeaient.
   * Renvoie leurs identifiants. Dans une fonction de Donnees.modifier.
   */
  function cascade(lignesJournal, cles, apres, motif, maintenant) {
    const lignesPages = Donnees.lignes('wiki_pages');
    const perdues = new Set(Array.from(cles).map((cle) => normaliser(cle, lignesPages)));
    const marquees = [];
    lignesJournal.filter((entree) => texte(entree.statut) === 'à valider' && rang(entree) > apres).sort(parRang)
      .forEach((entree) => {
        const deja = appliqueeDans(entree, lignesPages);        // validée sur un autre poste : rien à refaire
        if (deja) { marquerValidee(entree, deja, ''); return; }
        if (!depend(entree, perdues, lignesPages)) return;
        changeesDe(entree, lignesPages).forEach((cle) => perdues.add(cle));
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
   * marquée « validée » (pages relues d'abord). Aucun choix n'est fait : rien n'est réservé au responsable. → nombre.
   */
  async function rattraper() {
    await Donnees.rechargerTable('wiki_pages');
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
            const erreur = ErreurValidation('La page « ' + texte(changements[n].titre) + ' » a changé depuis la proposition.');
            erreur.pageChangee = true;
            throw erreur;
          }
        });
        // Lignes nouvelles : pages modifiées (page ancrée encore sans ligne) avant pages créées — la mère d'une sous-page
        // a sa ligne avant elle, quel que soit l'ordre des changements dans l'entrée.
        const pages = trouvees.slice();
        changements.map((c, n) => n).filter((n) => !pages[n])
          .sort((a, b) => Number(Boolean(changements[a].creation)) - Number(Boolean(changements[b].creation)) || a - b)
          .forEach((n) => {
            const rattacheA = texte(changements[n].rattacheA);
            const vise = rattacheA ? indexDesLiens(lignes).get(Wiki.comparable(rattacheA)) || '' : '';
            pages[n] = nouvelleLigne(lignes, outils, texte(changements[n].cle), changements[n], vise);
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
    await rattraper();
    const choisis = Array.from(new Set((ids || []).map(texte).filter(Boolean)));
    if (!choisis.length) throw ErreurValidation('Aucune proposition choisie.');
    const journal = Donnees.lignes('wiki_journal');
    const entrees = choisis.map((id) => {
      const entree = journal.find((e) => e.id === id);
      if (!entree || texte(entree.statut) !== 'à valider') {
        throw ErreurValidation('La proposition ' + id + ' n\'est pas « à valider »' + (entree ? ' (' + entree.statut + ')' : '') + '.');
      }
      return entree;
    }).sort(parRang);
    if (entrees.length > 1) {
      const avec = entrees.filter((e) => contradictionsDe(e).length).map((e) => e.id);
      if (avec.length) {
        throw ErreurValidation('Propositions avec une contradiction, à valider une à une : ' + avec.join(', ') + '.');
      }
    }
    const lignesPages = Donnees.lignes('wiki_pages');
    entrees.forEach((entree) => {
      const avant = journal.filter((e) => texte(e.statut) === 'à valider' && !choisis.includes(e.id) && rang(e) < rang(entree)
        && depend(entree, changeesDe(e, lignesPages), lignesPages));
      if (avant.length) {
        throw ErreurValidation('Validez d\'abord ' + avant.map((e) => e.id).join(', ') + ' : ' + entree.id + ' a été construite sur '
          + (avant.length > 1 ? 'leurs changements' : 'ses changements') + ' (propositions enchaînées).');
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
          const cles = changeesDe(ligne, lignesFraiches);
          const motif = 'à refaire : une page a changé depuis la proposition';
          Object.assign(ligne, { statut: 'à refaire', motif, changements: '', contradictions: '', ordre: '', traite_le: outils.maintenant() });
          return { aRefaire: [ligne.id].concat(cascade(lignes, cles, rang(entree), 'à refaire : suit ' + ligne.id, outils.maintenant())) };
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
        if (autre) ligne.motif = 'validée ici alors qu\'un autre poste l\'avait passée « ' + autre + ' » : son texte est publié';
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
    if (!texte(motif)) throw ErreurValidation('Le motif du rejet est obligatoire.');
    const par = nomDuResponsable();
    await Donnees.rechargerTable('wiki_pages');
    const lignesPages = Donnees.lignes('wiki_pages');
    const resultat = await Donnees.modifier('wiki_journal', (lignes, outils) => {
      const ligne = lignes.find((e) => e.id === texte(id));
      if (!ligne || texte(ligne.statut) !== 'à valider') {
        throw ErreurValidation('La proposition ' + texte(id) + ' n\'est pas « à valider ».');
      }
      const deja = appliqueeDans(ligne, lignesPages);
      if (deja) { marquerValidee(ligne, deja, ''); return { dejaValidee: true }; }
      const maintenant = outils.maintenant();
      const cles = changeesDe(ligne, lignesPages);
      Object.assign(ligne, { statut: 'rejetée', motif: texte(motif), decide_par: par, decide_le: maintenant });
      return { rejetee: ligne.id, aRefaire: cascade(lignes, cles, rang(ligne), 'à refaire : ' + ligne.id + ' rejetée', maintenant) };
    }, { journal: false });
    if (resultat.dejaValidee) {
      throw ErreurValidation('La proposition ' + texte(id) + ' vient d\'être validée (sans doute sur un autre poste) : son texte '
        + 'est publié, elle ne se rejette plus. Corrigez la page à la main si besoin.');
    }
    return resultat;
  }

  /** Relance l'OT d'une entrée « rejetée » ou « refusée » : une nouvelle entrée « en file ». → son identifiant. */
  async function remettreEnFile(id) {
    exigerResponsable();
    return Donnees.modifier('wiki_journal', (lignes, outils) => {
      const ligne = lignes.find((e) => e.id === texte(id));
      if (!ligne || texte(ligne.nature) !== 'ingestion' || !['rejetée', 'refusée'].includes(texte(ligne.statut))) {
        throw ErreurValidation('Seul l\'OT d\'une proposition rejetée ou refusée se remet en file.');
      }
      const autre = lignes.find((e) => e !== ligne && texte(e.ot_id) === texte(ligne.ot_id) && texte(e.nature) === 'ingestion'
        && !['rejetée', 'refusée'].includes(texte(e.statut)));
      if (autre) throw ErreurValidation('L\'OT ' + ligne.ot_id + ' a déjà une entrée « ' + autre.statut + ' » (' + autre.id + ').');
      const ot = Donnees.trouver('ordres_travail', texte(ligne.ot_id)) || {};
      const nouvelle = { id: outils.nouvelId(lignes), nature: 'ingestion', ot_id: ligne.ot_id,
        date_intervention: texte(ot.date_fin) || texte(ligne.date_intervention), statut: 'en file', anterieure: '0', essais: '0',
        motif: 'relancé après ' + ligne.id, cree_le: outils.maintenant() };
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
      if (!ligne) throw ErreurValidation('Page du wiki introuvable : ' + id + '.');
      if (!estActive(ligne)) throw ErreurValidation('La page « ' + texte(ligne.titre) + ' » est archivée.');
      return { ligne, cle: cleDeLigne(ligne), type: texte(ligne.type), titre: texte(ligne.titre) };
    }
    if (id.startsWith('EQ-') || id.startsWith('ART-')) {
      const equipement = id.startsWith('EQ-') && Donnees.trouver('equipements', id);
      const article = id.startsWith('ART-') && Donnees.trouver('articles', id);
      if (!equipement && !article) throw ErreurValidation('Équipement ou article introuvable : ' + id + '.');
      const cle = (equipement ? 'EQ:' : 'ART:') + id;
      return { ligne: ligneDeCle(lignesPages, cle, ''), cle, type: equipement ? 'équipement' : 'composant',
        titre: equipement ? titreEquipement(equipement) : titreArticle(article) };
    }
    const nouvelle = cible && cible.nouvelle;
    if (!nouvelle) throw ErreurValidation('Page à écrire non précisée.');
    if (texte(nouvelle.type) === 'équipement' && !texte(nouvelle.rattacheA)) {
      throw ErreurValidation('Une page d\'équipement ne se crée pas : elle existe déjà (seule une sous-page se crée, rattachée à sa mère).');
    }
    return { ligne: null, nouvelle: true, cle: 'TITRE:' + Wiki.comparable(nouvelle.titre), type: texte(nouvelle.type),
      titre: texte(nouvelle.titre), rattache: texte(nouvelle.rattacheA), causeCode: texte(nouvelle.causeCode) };
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
    const avant = page.ligne ? page.ligne.texte || '' : '';
    const rattachement = page.rattache ? pageEnvoyee(page.rattache) : null;
    const envoyees = page.nouvelle ? [rattachement].filter(Boolean) : [{ titre: page.titre, type: page.type, texte: avant }];
    const cites = Wiki.citationsDe(valeur);
    const permis = Donnees.lignes('ordres_travail').filter((ot) => texte(ot.statut) === 'Clôturé administrativement')
      .map((ot) => ot.id).concat(Wiki.citationsDe(avant));
    const sources = {};
    cites.forEach((id) => { sources[id] = Wiki.texteSourceOt(id); });
    const controle = Wiki.controlerProposition({ rien: false, contradictions: [], pages: [{
      action: page.nouvelle ? 'creer' : 'modifier', titre: page.titre, type: page.type,
      rattacheA: rattachement ? rattachement.titre : '', texte: valeur }] }, {
      manuel: true, pagesEnvoyees: envoyees, catalogue: Wiki.catalogue().map((p) => ({ titre: p.titre, type: p.type })),
      otPermis: permis, sources });
    if (!controle.ok) {
      const erreur = ErreurValidation('Texte refusé : ' + controle.raisons.join(' '));
      erreur.raisons = controle.raisons;
      throw erreur;
    }
  }

  /**
   * Écriture à la main (§20.7) : cible { pageId } (WP-…, EQ-…, ART-…) ou { nouvelle: { type, titre, rattacheA
   * (identifiant canonique), causeCode } } ; options { version (vue à l'écran : conflit si la page a changé),
   * archiver, motif }. Contrôles du §20.6 (sauf archivage). → { pageId (canonique), ligneId, entreeId }.
   */
  async function ecrire(cible, valeur, options) {
    exigerResponsable();
    const opts = options || {};
    await rattraper();                           // pages relues ; une validation interrompue est d'abord rattrapée
    const page = cibleDe(cible);
    const archiver = Boolean(opts.archiver);
    if (archiver && !page.ligne) throw ErreurValidation('Seule une page qui a un texte s\'archive.');
    const nouveau = archiver ? (page.ligne.texte || '') : String(valeur === null || valeur === undefined ? '' : valeur).trim();
    if (!archiver) controlerEcriture(page, nouveau);
    const version = page.ligne ? Number(page.ligne.version) || 0 : 0;
    const attendue = opts.version === undefined || opts.version === null ? version : Number(opts.version) || 0;
    if (attendue !== version) throw ErreurValidation('La page a été modifiée entre-temps : rechargez-la puis recommencez.');
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
      cascade(lignes, new Set([page.cle]), -Infinity, 'à refaire : page écrite à la main (' + id + ')', maintenant);
      return id;
    }, { journal: false });
    try {
      const ligneId = await Donnees.modifier('wiki_pages', (lignes, outils) => {
        let ligne = page.ligne ? lignes.find((l) => l.id === page.ligne.id) : ligneDeCle(lignes, page.cle, '');
        if ((ligne ? Number(ligne.version) || 0 : 0) !== version) {
          throw ErreurValidation('La page a été modifiée entre-temps (sans doute sur un autre poste) : rechargez-la puis recommencez.');
        }
        if (page.nouvelle && ligne) throw ErreurValidation('Une page de ce titre existe déjà.');
        if (!ligne) {
          ligne = nouvelleLigne(lignes, outils, page.cle, { type: page.type, titre: page.titre }, texte(page.rattache));
          // Une sous-page (rattachée à sa mère) n'a pas d'ancrage propre, pas même un code cause.
          if (page.causeCode && !texte(ligne.rattache_a)) ligne.cause_code = page.causeCode;
        }
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
    if (!DECISIONS.includes(decision)) throw ErreurValidation('Décision inconnue : ' + decision + ' (ancien, nouveau ou les deux).');
    const par = nomDuResponsable();
    const resultat = await Donnees.modifier('wiki_journal', (lignes, outils) => {
      const entree = lignes.find((e) => e.id === texte(entreeId));
      if (!entree || texte(entree.statut) !== 'validée') throw ErreurValidation('Contradiction introuvable sur une proposition validée.');
      const contradictions = contradictionsDe(entree);
      const contradiction = contradictions[Number(rangContradiction)];
      if (!contradiction || texte(contradiction.statut) !== 'ouverte') throw ErreurValidation('Cette contradiction n\'est pas ouverte.');
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
          libelle: anterieure ? 'Observation antérieure aux faits de la page' : 'Ce que dit le nouvel OT',
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
          ecarts.push({ page: nom, entree: entree.id, message: 'son « avant » n\'est pas le texte laissé par l\'entrée précédente' });
        }
        precedent = changement.apres || '';
        if (texte(entree.nature) !== 'ingestion' || texte(entree.anterieure) === '1') return;
        const date = texte(entree.date_intervention);
        if (plusRecente && date && date < plusRecente) {
          ecarts.push({ page: nom, entree: entree.id, message: 'OT ' + entree.ot_id + ' intégré après un OT plus récent' });
        }
        if (date > plusRecente) plusRecente = date;
      });
      if (!ligne) ecarts.push({ page: nom, entree: suite[suite.length - 1].entree.id, message: 'page absente de wiki_pages' });
      else if ((ligne.texte || '') !== precedent) {
        ecarts.push({ page: nom, entree: suite[suite.length - 1].entree.id, message: 'le texte de la page n\'est pas l\'« après » de sa dernière entrée' });
      }
    });
    lignesPages.filter((ligne) => texte(ligne.texte) && !parPage.has(ligne.id))
      .forEach((ligne) => ecarts.push({ page: texte(ligne.titre), entree: '', message: 'texte sans entrée au journal' }));
    const envois = (options && options.envois) || [];
    envois.forEach((a, n) => envois.slice(n + 1).forEach((b) => {
      const communes = (a.cles || []).filter((cle) => (b.cles || []).includes(cle));
      const ensemble = a.debut < (b.fin === null ? Infinity : b.fin) && b.debut < (a.fin === null ? Infinity : a.fin);
      if (communes.length && ensemble) {
        ecarts.push({ page: communes.join(', '), entree: '', message: 'envois simultanés de ' + a.ot + ' et ' + b.ot });
      }
    }));
    return { ok: ecarts.length === 0, ecarts };
  }

  return {
    valider, rattraper, rejeter, remettreEnFile, ecrire, trancher, verifierIntegrite,
    contradictionsDe: contradictionsDePage, enAttenteDe,
  };
})());
