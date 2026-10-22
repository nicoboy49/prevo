'use strict';
// Import (contrôles des formulaires, T92) — une ligne que le formulaire de Prévo refuserait est refusée à l'aperçu,
// avec la raison du formulaire, précédée du champ quand le message ne le nomme pas (lot 5 ; question du §6.14 du
// rapport T80, décision de Nicolas du 2026-10-22). Complète l'objet Import (fonctions pures : rien n'est écrit, seul
// Donnees est lu) ; appelé par Import.preparer (crochet) après la seconde passe et la cascade des parents, avant les
// identifiants et les écritures (terminer).
// Contrôles appelés tels quels, jamais recopiés : localisations → Parc.verifierLocalisation ; équipements →
// Parc.verifierEquipement ; articles et fournisseurs → Magasin.interne.verifierArticle / verifierFournisseur ;
// techniciens → Equipe.verifierTechnicien ; habilitations → Equipe.interne.verifierHabilitation ; codes →
// Parametres.verifierCode (modification : erreurs du libellé seules, comme l'écran) ; contrôles réglementaires →
// Controles.verifierControle (jour : « maintenant » de l'import) ; gammes → Preventif.verifierGamme. Rien pour les
// compteurs (aucun formulaire de création dans Prévo) ni pour l'historique (Import.preparerHistorique : un OT clôturé
// importé ne passe par aucun formulaire de création ; Ordres.verifierCloture est la règle de clôture RG4, que D92
// n'impose pas aux interventions reprises).
// Règles : une fiche créée est contrôlée telle qu'elle sera écrite (défauts du schéma compris) ; une mise à jour, sur
// la fiche existante complétée des changements (une cellule vide n'efface rien, D84) ; une ligne qui n'écrit pas la
// fiche (identique, opérations seules) ne l'est pas. Lignes dans l'ordre du fichier, comme des saisies successives :
// la base, les références créées par l'import et les fiches acceptées plus haut comptent pour l'unicité (un doublon du
// fichier, déjà refusé par l'import, ne l'est pas deux fois) ; une fiche que la ligne cite existe, même créée plus bas.
// Une fiche créée par l'import que le contrôle chercherait dans la base (fournisseur d'un article) n'est pas donnée :
// l'import en garantit l'existence. Ce qui dépend d'une ligne refusée l'est aussi (équipement enfant, localisation
// fille, opérations d'une gamme) ; terminer ne crée plus les références qu'elle seule utilisait.

Object.assign(Import, (() => {
  const { texte, comparable, refuser, GARDEES } = Import.interne;
  const gardee = (ligne) => Boolean(ligne) && GARDEES.has(ligne.action);

  // Contrôle de chaque type : (valeurs, lignes(table), idCourant, jour, estProvisoire) → [{ nom, message }].
  const CONTROLES = {
    localisations: (v, lignes, id) => Parc.verifierLocalisation(v, lignes('localisations'), id),
    equipements: (v, lignes, id) => Parc.verifierEquipement(v, lignes('equipements'), lignes('localisations'), id),
    articles: (v, lignes, id, jour, estProvisoire) => Magasin.interne.verifierArticle(
      estProvisoire(v.fournisseur_id) ? Object.assign({}, v, { fournisseur_id: '' }) : v, lignes('articles'), id),
    fournisseurs: (v, lignes, id) => Magasin.interne.verifierFournisseur(v, lignes('fournisseurs'), id),
    techniciens: (v, lignes, id) => Equipe.verifierTechnicien(v, lignes('techniciens'), id),
    habilitations: (v) => Equipe.interne.verifierHabilitation(v),
    codes: (v, lignes, id) => Parametres.verifierCode(v, lignes('codes_defaillance'), id).filter((e) => !id || e.nom === 'libelle'),
    controles: (v, lignes, id, jour) => Controles.verifierControle(v, jour),
    gammes: (v) => Preventif.verifierGamme(v),
  };
  // Valeurs comparées par les contrôles d'unicité, en texte comparable (plus large que celui des formulaires : toutes
  // les fiches candidates sont données, le formulaire tranche).
  const CLES = {
    localisations: [(l) => l.libelle], equipements: [(l) => l.repere], articles: [(l) => l.reference], fournisseurs: [(l) => l.nom],
    techniciens: [(l) => texte(l.nom) + ' ' + texte(l.prenom)], codes_defaillance: [(l) => texte(l.code).toUpperCase(), (l) => l.libelle],
  };
  // Raison d'une ligne qui cite une fiche qu'une ligne refusée devait créer (même texte que la cascade de T80).
  const DEPENDANCES = { equipements: 'équipement parent refusé', localisations: 'localisation parente refusée', gammes: 'gamme refusée' };

  // ===== État vu par les formulaires ==========================================================
  const nouvelEtat = (contexte) => ({ contexte, provisoires: new Map(), pris: new Set(), tables: new Map(), prevues: new Map() });
  // Identifiant provisoire d'une fiche créée par l'import (le vrai est donné par terminer) : lisible dans un message.
  function provisoire(etat, objet) {
    if (!etat.provisoires.has(objet)) {
      const entree = etat.contexte.entrees.get(objet);
      const base = entree && entree.ligne ? 'ligne ' + entree.ligne.numero + ' du fichier' : "créée par l'import, n° " + (etat.provisoires.size + 1);
      let id = base;
      for (let n = 2; etat.pris.has(id); n += 1) id = base + ' (' + n + ')';
      etat.pris.add(id);
      etat.provisoires.set(objet, id);
    }
    return etat.provisoires.get(objet);
  }
  const valeurDe = (etat, valeur) => (valeur && typeof valeur === 'object'
    ? (etat.contexte.entrees.has(valeur) ? provisoire(etat, valeur) : valeur.id) : valeur);
  // Fiche prévue → ligne de table : références en identifiants (provisoires pour les fiches créées par l'import).
  function enLigne(etat, table, objet) {
    const ligne = {};
    Object.keys(objet).forEach((nom) => { ligne[nom] = valeurDe(etat, objet[nom]); });
    ligne.id = provisoire(etat, objet);
    if (table === 'localisations' && etat.contexte.arbre) ligne.parent_id = valeurDe(etat, etat.contexte.arbre.parents.get(objet)) || '';
    return ligne;
  }
  const clesDe = (table, ligne) => (CLES[table] || []).map((cle, i) => i + '|' + comparable(cle(ligne)));
  function indexer(index, table, ligne) {
    index.parId.set(ligne.id, ligne);
    clesDe(table, ligne).forEach((cle) => index.parCle.set(cle, (index.parCle.get(cle) || new Set()).add(ligne.id)));
  }
  function retirer(index, table, id) {
    const ancienne = index.parId.get(id);
    if (ancienne) clesDe(table, ancienne).forEach((cle) => index.parCle.get(cle).delete(id));
    index.parId.delete(id);
  }
  // Une table : la base, les références créées par l'import, puis les fiches acceptées (créées ou complétées).
  function indexDe(etat, table) {
    if (!etat.tables.has(table)) {
      const index = { parId: new Map(), parCle: new Map() };
      Donnees.lignes(table).forEach((ligne) => indexer(index, table, ligne));
      etat.contexte.crees.filter((e) => e.table === table && !e.ligne).forEach((e) => indexer(index, table, enLigne(etat, table, e.objet)));
      etat.tables.set(table, index);
    }
    return etat.tables.get(table);
  }
  // Fiches que les lignes gardées créeront : elles existent pour une ligne qui les cite (parent plus bas dans le fichier).
  function prevuesDe(etat, table) {
    if (!etat.prevues.has(table)) {
      etat.prevues.set(table, new Map(etat.contexte.crees.filter((e) => e.table === table && gardee(e.ligne))
        .map((e) => [provisoire(etat, e.objet), enLigne(etat, table, e.objet)])));
    }
    return etat.prevues.get(table);
  }
  // Lignes d'une table utiles au contrôle d'une fiche : la fiche existante, celles qui lui ressemblent (unicité) et
  // celles qu'elle cite, avec leurs parents (existence, boucles). Le formulaire n'en regarde pas d'autres : même verdict
  // que sur toute la table, sans la parcourir à chaque ligne (5 000 lignes, CS93).
  function lignesUtiles(etat, table, fiche, principale) {
    const [index, prevues, utiles] = [indexDe(etat, table), prevuesDe(etat, table), new Map()];
    const trouver = (id) => index.parId.get(id) || prevues.get(id);
    const ajouter = (id) => { if (id !== fiche.propre && trouver(id)) utiles.set(id, trouver(id)); };
    if (principale && fiche.idCourant) ajouter(fiche.idCourant);
    if (principale) clesDe(table, fiche.valeurs).forEach((cle) => (index.parCle.get(cle) || []).forEach(ajouter));
    Object.values(fiche.valeurs).forEach((valeur) => {
      for (let id = valeur, pas = 0; typeof id === 'string' && id && trouver(id) && !utiles.has(id) && pas < 1000; pas += 1) {
        ajouter(id);
        id = trouver(id).parent_id;
      }
    });
    return Array.from(utiles.values());
  }
  // Fiche que la ligne écrit dans la table du type : { valeurs, idCourant, propre } ou null (rien d'écrit dans cette table).
  function ficheEcrite(etat, ligne) {
    const { table, entrees } = etat.contexte;
    if (ligne._objet && (entrees.get(ligne._objet) || {}).table === table) {
      const valeurs = enLigne(etat, table, ligne._objet);
      const propre = valeurs.id;
      delete valeurs.id;
      return { valeurs, idCourant: '', propre };
    }
    const existante = ligne._existante;
    const changement = existante && (ligne._modifier || []).find((m) => m.table === table && m.id === existante.id);
    if (!changement) return null;
    const valeurs = Object.assign({}, existante);
    Object.keys(changement.changes).forEach((nom) => { valeurs[nom] = valeurDe(etat, changement.changes[nom]); });
    return { valeurs, idCourant: existante.id, propre: '' };
  }
  function accepter(etat, fiche) {
    const [table, index] = [etat.contexte.table, indexDe(etat, etat.contexte.table)];
    if (fiche.idCourant) retirer(index, table, fiche.idCourant);
    indexer(index, table, Object.assign({}, fiche.valeurs, { id: fiche.idCourant || fiche.propre }));
  }

  // ===== Refus et dépendances ===================================================================
  // Raison du formulaire, précédée du libellé du champ (colonne de l'import, sinon schéma) quand le message ne le nomme pas.
  function raison(contexte, erreur) {
    const champ = contexte.description.champs.find((c) => (c.champ === erreur.nom && c.table === contexte.table) || c.ecrit === erreur.nom)
      || Schema.champ(contexte.table, erreur.nom);
    const libelle = champ ? texte(champ.libelle) : '';
    return !libelle || comparable(erreur.message).includes(comparable(libelle)) ? erreur.message : libelle + ' : ' + erreur.message;
  }
  // Ligne gardée qui cite, directement ou par une référence créée, une fiche qu'une ligne refusée devait créer : refusée
  // à son tour, jusqu'à stabilité (même mécanisme que la cascade des parents de T80).
  function refuserDependantes(contexte) {
    const parLigne = new Map();
    contexte.crees.forEach((e) => { if (e.ligne) parLigne.set(e.ligne, (parLigne.get(e.ligne) || []).concat([e.objet])); });
    const cites = (objet) => Object.values(objet).concat(contexte.arbre && (contexte.entrees.get(objet) || {}).table === 'localisations'
      ? [contexte.arbre.parents.get(objet)] : []);
    function source(ligne, valeur, vus) {
      const entree = valeur && typeof valeur === 'object' ? contexte.entrees.get(valeur) : null;
      if (!entree || entree.ligne === ligne || vus.has(valeur)) return null;
      vus.add(valeur);
      if (entree.ligne) return gardee(entree.ligne) ? null : entree;
      return cites(valeur).map((v) => source(ligne, v, vus)).find(Boolean) || null;     // référence créée : ce qu'elle cite
    }
    for (let change = true; change;) {
      change = false;
      for (const ligne of contexte.lignes.filter(gardee)) {
        const vus = new Set();
        const valeurs = [].concat(...(parLigne.get(ligne) || []).map(cites), ...(ligne._modifier || []).map((m) => Object.values(m.changes)));
        const refusee = valeurs.map((valeur) => source(ligne, valeur, vus)).find(Boolean);
        if (!refusee) continue;
        // Note de la seconde passe que le refus contredit (opération d'une gamme refusée).
        if (ligne._tete) ligne.raisons = ligne.raisons.filter((r) => r !== 'opération ajoutée à la gamme de la ligne ' + ligne._tete.numero);
        refuser(ligne, (DEPENDANCES[refusee.table] || 'fiche liée refusée') + ' (ligne ' + refusee.ligne.numero + ')');
        change = true;
      }
    }
  }

  /** Crochet de Import.preparer : refuse les lignes que le formulaire du type refuserait, puis ce qui en dépend. */
  function controlerFormulaires(contexte) {
    const controle = CONTROLES[contexte.type];
    if (!controle) return;
    const [etat, jour] = [nouvelEtat(contexte), texte(contexte.maintenant).slice(0, 10)];
    const estProvisoire = (id) => typeof id === 'string' && etat.pris.has(id);
    let refus = 0;
    contexte.lignes.filter(gardee).forEach((ligne) => {
      const fiche = ficheEcrite(etat, ligne);
      if (!fiche) return;
      const erreurs = controle(fiche.valeurs, (table) => lignesUtiles(etat, table, fiche, table === contexte.table), fiche.idCourant, jour, estProvisoire);
      if (!erreurs.length) return accepter(etat, fiche);
      refuser(ligne, erreurs.map((erreur) => raison(contexte, erreur)));
      refus += 1;
    });
    if (refus) refuserDependantes(contexte);
  }

  return { controlerFormulaires };
})());
