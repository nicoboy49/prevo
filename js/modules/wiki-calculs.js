'use strict';
// Wiki (2/8) — couches calculées du composant et du mode, pages virtuelles et catalogue (lot 6 refondu,
// ARCHITECTURE.md §20.3). Socle (T110) : Wiki.page(id) ne connaît encore que la page d'un équipement ;
// les articles, les modes, les pages du wiki et le catalogue arrivent avec T112. Lecture seule.

Object.assign(Wiki, (() => {

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  /** Page d'un identifiant (§20.3) : { id, type, titre, calcul } ou null. Socle : équipement seulement. */
  function page(id, options) {
    const calcul = Wiki.pageEquipement(texte(id), options);
    if (!calcul) return null;
    const titre = [calcul.equipement.repere, calcul.equipement.designation].filter(Boolean).join(' — ');
    return { id: calcul.equipement.id, type: 'équipement', titre, calcul };
  }

  return { page };
})());
