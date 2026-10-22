'use strict';
// Wiki (4/5) — synthèse [IA] d'une page (lot 6, ARCHITECTURE.md §20.4, §20.7, §20.8) : données envoyées à
// la fonction syntheseWiki (liste blanche), requêtes de la démo ; la carte de la synthèse et l'encadré
// de l'IA (tâche T102) complètent ce fichier. Complète l'objet Wiki.

Object.assign(Wiki, (() => {

  const STATUTS_CLOTURES = ['Clôturé techniquement', 'Clôturé administrativement'];

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  function nombre(valeur) {
    const lu = Number(String(valeur === null || valeur === undefined ? '' : valeur).replace(',', '.'));
    return Number.isFinite(lu) ? lu : 0;
  }

  // Libellé d'un code de défaillance d'une famille (le code lui-même s'il est inconnu, vide sans code).
  function libelleCode(codes, famille, code) {
    if (!texte(code)) return '';
    const ligne = codes.find((c) => c.famille === famille && c.code === code);
    return ligne ? texte(ligne.libelle) : texte(code);
  }

  // Pièces consommées par OT : sorties moins retours, par article, quantité nette > 0 → Map otId → [{ designation, quantite }].
  function piecesParOt(otIds) {
    const voulus = new Set(otIds);
    const parOt = new Map();
    Donnees.lignes('mouvements_stock').forEach((mouvement) => {
      if (!voulus.has(mouvement.ot_id) || (mouvement.type !== 'sortie' && mouvement.type !== 'retour')) return;
      if (!parOt.has(mouvement.ot_id)) parOt.set(mouvement.ot_id, new Map());
      const articles = parOt.get(mouvement.ot_id);
      const signe = mouvement.type === 'sortie' ? 1 : -1;
      articles.set(mouvement.article_id, (articles.get(mouvement.article_id) || 0) + signe * nombre(mouvement.quantite));
    });
    const resultat = new Map();
    parOt.forEach((articles, otId) => {
      resultat.set(otId, Array.from(articles.entries()).filter(([, quantite]) => quantite > 0).map(([articleId, quantite]) => ({
        designation: texte((Donnees.trouver('articles', articleId) || {}).designation) || articleId,
        quantite: String(Math.round(quantite * 1000) / 1000),
      })));
    });
    return resultat;
  }

  /**
   * Données de la fonction syntheseWiki pour un équipement (§20.4), en liste blanche : repère, désignation,
   * marque, modèle ; ses OT clôturés (identifiant, date de fin, type, titre, libellés des codes, compte
   * rendu, pièces consommées, durée d'arrêt). Jamais de nom de technicien ou de demandeur, de coût, de
   * document ni de photo. La consigne garde les 40 plus récents.
   */
  function donneesSynthese(equipementId) {
    const equipement = Donnees.trouver('equipements', equipementId);
    if (!equipement) return null;
    const codes = Donnees.lignes('codes_defaillance');
    const clos = Donnees.lignes('ordres_travail')
      .filter((ot) => ot.equipement_id === equipementId && STATUTS_CLOTURES.includes(ot.statut));
    const pieces = piecesParOt(clos.map((ot) => ot.id));
    return {
      repere: texte(equipement.repere),
      designation: texte(equipement.designation),
      marque: texte(equipement.marque),
      modele: texte(equipement.modele),
      ot: clos.map((ot) => ({
        id: ot.id,
        date: (texte(ot.date_fin) || texte(ot.date_cloture_tech) || texte(ot.date_creation)).slice(0, 10),
        type: texte(ot.type),
        titre: texte(ot.titre),
        symptome: libelleCode(codes, 'symptôme', ot.symptome_code),
        cause: libelleCode(codes, 'cause', ot.cause_code),
        remede: libelleCode(codes, 'remède', ot.remede_code),
        compteRendu: texte(ot.compte_rendu),
        pieces: pieces.get(ot.id) || [],
        dureeArret: texte(ot.duree_arret_h),
      })),
    };
  }

  /**
   * Requêtes de la démo (§20.8, D98) : pour chaque équipement où une synthèse peut être proposée, la
   * requête réelle de syntheseWiki (Ia.requete : messages, schéma, température) et les données qui ont
   * servi à la construire (pour relire la réponse par Ia.lireReponse, même circuit que le produit).
   */
  function requetesDemo(options) {
    return Donnees.lignes('equipements')
      .filter((equipement) => Wiki.page(equipement.id, options || {}).peutProposer)
      .sort((a, b) => texte(a.repere).localeCompare(texte(b.repere), 'fr'))
      .map((equipement) => {
        const donnees = donneesSynthese(equipement.id);
        return { equipementId: equipement.id, repere: texte(equipement.repere), requete: Ia.requete('syntheseWiki', donnees), donnees };
      });
  }

  return { donneesSynthese, requetesDemo };
})());
