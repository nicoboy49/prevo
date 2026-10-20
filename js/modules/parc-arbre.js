'use strict';
// Parc (2/4) — écran #/parc : arborescence site › atelier › ligne › équipement, recherche, case
// « inactifs », boutons de localisation pour le responsable (ARCHITECTURE.md §8 et §14.2).
// Complète l'objet Parc.

Object.assign(Parc, (() => {

  // Outils de parc-regles.js.
  const { estActif, comparerTextes, parRepere, remonteSurSoi, badgesEquipement } = Parc.interne;

  // Fenêtre de localisation : dans parc-formulaires.js, chargé APRÈS ce fichier ; elle est
  // cherchée au moment de l'appel, pas au chargement.
  const ouvrirFenetreLocalisation = (idExistant) => Parc.interne.ouvrirFenetreLocalisation(idExistant);

  // Recherche et case « inactifs » : gardées d'un affichage à l'autre (un changement distant
  // réaffiche l'écran sans faire perdre la recherche en cours).
  const etatListe = { terme: '', inactifs: false };

  // ===========================================================================================
  // 3. Écran #/parc : arborescence
  // ===========================================================================================

  // Prépare l'arborescence à afficher selon la recherche et la case « inactifs ».
  // Renvoie { html, nbEquipements, nbCorrespondances }.
  function construireArbre() {
    const mots = UI.normaliserRecherche(etatListe.terme).split(' ').filter(Boolean);
    const responsable = App.estResponsable();
    const equipements = Donnees.lignes('equipements').filter((e) => etatListe.inactifs || estActif(e));
    const equipementsParId = new Map(equipements.map((e) => [e.id, e]));

    // 1. Équipements retenus : ceux qui correspondent à la recherche, plus leurs parents (pour le contexte).
    const retenus = new Set();
    let nbCorrespondances = 0;
    equipements.forEach((equipement) => {
      const texte = UI.normaliserRecherche([equipement.repere, equipement.designation, equipement.marque, equipement.modele].join(' '));
      if (!mots.every((mot) => texte.includes(mot))) return;
      nbCorrespondances += 1;
      let courant = equipement;
      while (courant && !retenus.has(courant.id)) {
        retenus.add(courant.id);
        const parent = equipementsParId.get(courant.parent_id);
        courant = parent && parent.localisation_id === courant.localisation_id ? parent : null;
      }
    });

    // 2. Rangement : un sous-équipement se range sous son parent (même localisation), les autres sous leur localisation.
    const enfantsParParent = new Map();
    const racinesParLocalisation = new Map();
    const localisationsConnues = new Set(Donnees.lignes('localisations').map((l) => l.id));
    equipements.filter((e) => retenus.has(e.id)).sort(parRepere).forEach((equipement) => {
      const parent = equipementsParId.get(equipement.parent_id);
      const rangeSousParent = parent && retenus.has(parent.id) && parent.localisation_id === equipement.localisation_id
        && !remonteSurSoi(equipement.id, equipementsParId);
      if (rangeSousParent) {
        if (!enfantsParParent.has(parent.id)) enfantsParParent.set(parent.id, []);
        enfantsParParent.get(parent.id).push(equipement);
      } else {
        const cle = localisationsConnues.has(equipement.localisation_id) ? equipement.localisation_id : '';
        if (!racinesParLocalisation.has(cle)) racinesParLocalisation.set(cle, []);
        racinesParLocalisation.get(cle).push(equipement);
      }
    });

    function nombreAvecEnfants(equipement) {
      return 1 + (enfantsParParent.get(equipement.id) || []).reduce((somme, enfant) => somme + nombreAvecEnfants(enfant), 0);
    }

    function ligneEquipement(equipement) {
      const enfants = enfantsParParent.get(equipement.id) || [];
      return UI.html`<li>
        <a class="feuille ${estActif(equipement) ? '' : 'attenue'}" href="#/equipement/${encodeURIComponent(equipement.id)}">
          <b>${equipement.repere || equipement.id}</b>
          <span class="parc-designation">${equipement.designation}${equipement.marque ? UI.html` <small>(${equipement.marque})</small>` : ''}</span>
          <span class="type parc-badges">${badgesEquipement(equipement)}</span>
        </a>
        ${enfants.length ? UI.html`<ul>${enfants.map(ligneEquipement)}</ul>` : ''}
      </li>`;
    }

    // 3. Localisations (récursif). Une localisation sans équipement disparaît pendant une recherche.
    const localisations = Donnees.lignes('localisations');
    const localisationsParId = new Map(localisations.map((l) => [l.id, l]));
    const sousLocalisations = new Map();
    const racinesLocalisations = [];
    localisations.slice().sort((a, b) => comparerTextes(a.libelle, b.libelle)).forEach((localisation) => {
      const parent = localisationsParId.get(localisation.parent_id);
      if (parent && !remonteSurSoi(localisation.id, localisationsParId)) {
        if (!sousLocalisations.has(parent.id)) sousLocalisations.set(parent.id, []);
        sousLocalisations.get(parent.id).push(localisation);
      } else {
        racinesLocalisations.push(localisation);
      }
    });

    function noeudLocalisation(localisation) {
      const sous = (sousLocalisations.get(localisation.id) || []).map(noeudLocalisation).filter(Boolean);
      const racines = racinesParLocalisation.get(localisation.id) || [];
      const nombre = sous.reduce((somme, noeud) => somme + noeud.nombre, 0)
        + racines.reduce((somme, equipement) => somme + nombreAvecEnfants(equipement), 0);
      if (mots.length && nombre === 0) return null;
      return {
        nombre,
        html: UI.html`<li>
          <details open>
            <summary>
              <b>${localisation.libelle || localisation.id}</b>
              <span class="type" title="${nombre} équipement${nombre > 1 ? 's' : ''}"><span class="parc-type-loc">${localisation.type || ''} · </span><span class="parc-nombre">${nombre}</span><span class="parc-mot-equip"> équipement${nombre > 1 ? 's' : ''}</span></span>
              ${responsable ? UI.html`<button type="button" class="btn btn-fantome parc-modifier-localisation" data-localisation="${localisation.id}"
                aria-label="Modifier la localisation ${localisation.libelle}">${UI.icone('cle')}<span class="parc-libelle-bouton">Modifier</span></button>` : ''}
            </summary>
            ${sous.length || racines.length ? UI.html`<ul>${sous.map((noeud) => noeud.html)}${racines.map(ligneEquipement)}</ul>` : UI.html`<p class="note parc-vide-loc">Aucun équipement ici.</p>`}
          </details>
        </li>`,
      };
    }

    const noeuds = racinesLocalisations.map(noeudLocalisation).filter(Boolean);
    const sansLocalisation = racinesParLocalisation.get('') || [];
    let nombreTotal = noeuds.reduce((somme, noeud) => somme + noeud.nombre, 0);
    let blocSansLocalisation = '';
    if (sansLocalisation.length) {
      const nombre = sansLocalisation.reduce((somme, equipement) => somme + nombreAvecEnfants(equipement), 0);
      nombreTotal += nombre;
      blocSansLocalisation = UI.html`<li><details open>
        <summary><b>Sans localisation</b><span class="type">${nombre} équipement${nombre > 1 ? 's' : ''}</span></summary>
        <ul>${sansLocalisation.map(ligneEquipement)}</ul></details></li>`;
    }
    return {
      html: UI.html`<ul class="arbre">${noeuds.map((noeud) => noeud.html)}${blocSansLocalisation}</ul>`,
      nbEquipements: nombreTotal,
      nbCorrespondances,
    };
  }

  function afficherListe(conteneur) {
    const responsable = App.estResponsable();
    const actifs = Donnees.lignes('equipements').filter(estActif).length;
    const inactifs = Donnees.lignes('equipements').length - actifs;
    UI.remplir(conteneur, UI.html`
      <div class="parc">
        <div class="entete-page">
          <div>
            <h1>Parc</h1>
            <p>${actifs} équipement${actifs > 1 ? 's' : ''} actif${actifs > 1 ? 's' : ''} dans ${Donnees.lignes('localisations').length} localisations.
              Touchez un équipement pour ouvrir sa fiche.</p>
          </div>
          ${responsable ? UI.html`<div class="actions">
            <a class="btn btn-primaire" href="#/equipement/nouveau">${UI.icone('ajouter')}Nouvel équipement</a>
            <button type="button" class="btn btn-secondaire" id="parc-nouvelle-localisation">${UI.icone('ajouter')}Nouvelle localisation</button>
          </div>` : ''}
        </div>
        <div class="filtres parc-filtres" data-hors-saisie>
          <label class="visuellement-cache" for="parc-recherche">Rechercher un équipement</label>
          <input type="search" id="parc-recherche" autocomplete="off" enterkeyhint="search"
            placeholder="Repère, désignation ou marque">
          <label class="case" for="parc-inactifs"><input type="checkbox" id="parc-inactifs">Afficher les inactifs${inactifs ? ' (' + inactifs + ')' : ''}</label>
          <button type="button" class="btn btn-fantome" id="parc-replier" data-etat="ouvert">Tout replier</button>
        </div>
        <p class="note parc-resultat" role="status" aria-live="polite"></p>
        <article class="carte parc-arbre" id="parc-arbre"></article>
      </div>`);

    const champRecherche = UI.$('#parc-recherche', conteneur);
    const caseInactifs = UI.$('#parc-inactifs', conteneur);
    const boutonReplier = UI.$('#parc-replier', conteneur);
    const zoneArbre = UI.$('#parc-arbre', conteneur);
    const zoneResultat = UI.$('.parc-resultat', conteneur);
    champRecherche.value = etatListe.terme;
    caseInactifs.checked = etatListe.inactifs;

    function dessinerArbre() {
      const arbre = construireArbre();
      boutonReplier.dataset.etat = 'ouvert';
      boutonReplier.textContent = 'Tout replier';
      if (arbre.nbEquipements === 0) {
        UI.remplir(zoneArbre, etatListe.terme.trim()
          ? UI.vide('Aucun équipement trouvé', 'Aucun équipement ne correspond à « ' + etatListe.terme.trim() + ' ». Essayez un autre mot, ou cochez « Afficher les inactifs ».', 'recherche')
          : UI.vide('Le parc est vide', responsable ? 'Commencez par créer vos localisations, puis vos équipements.' : 'Le responsable n\'a pas encore saisi d\'équipement.', 'parc'));
        zoneResultat.textContent = '';
        return;
      }
      UI.remplir(zoneArbre, arbre.html);
      zoneResultat.textContent = etatListe.terme.trim()
        ? arbre.nbCorrespondances + ' équipement' + (arbre.nbCorrespondances > 1 ? 's' : '') + ' trouvé' + (arbre.nbCorrespondances > 1 ? 's' : '')
          + ' pour « ' + etatListe.terme.trim() + ' ».'
        : '';
    }

    champRecherche.addEventListener('input', () => { etatListe.terme = champRecherche.value; dessinerArbre(); });
    caseInactifs.addEventListener('change', () => { etatListe.inactifs = caseInactifs.checked; dessinerArbre(); });
    boutonReplier.addEventListener('click', () => {
      const ouvrir = boutonReplier.dataset.etat !== 'ouvert';
      UI.$$('details', zoneArbre).forEach((detail) => { detail.open = ouvrir; });
      boutonReplier.dataset.etat = ouvrir ? 'ouvert' : 'ferme';
      boutonReplier.textContent = ouvrir ? 'Tout replier' : 'Tout déplier';
    });
    zoneArbre.addEventListener('click', (evenement) => {
      const bouton = evenement.target.closest('.parc-modifier-localisation');
      if (!bouton) return;
      evenement.preventDefault();                      // le bouton est dans un <summary> : pas de repli
      ouvrirFenetreLocalisation(bouton.dataset.localisation);
    });
    const boutonLocalisation = UI.$('#parc-nouvelle-localisation', conteneur);
    if (boutonLocalisation) boutonLocalisation.addEventListener('click', () => ouvrirFenetreLocalisation(''));
    dessinerArbre();
  }

  return {
    afficherListe,
  };
})());
