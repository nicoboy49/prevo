'use strict';
// Parc : arborescence des localisations et des équipements, fiche équipement (consignation,
// historique, QR code), création et modification (brief §6 « equipements » et « localisations »,
// §9 E7, ARCHITECTURE.md §8 et §10).
//
// Écrans :
//   #/parc                       arborescence site › atelier › ligne, recherche, inactifs (tous les profils)
//   #/equipement/<id>            fiche complète (tous les profils)
//   #/equipement/nouveau         formulaire de création (responsable)
//   #/equipement/<id>/modifier   formulaire de modification (responsable)
//   Les localisations se créent et se modifient dans une fenêtre, depuis le parc (responsable).
//
// Fonctions offertes aux autres modules :
//   Parc.cheminLocalisation(id)   « Site des Trois Vallées › Atelier Utilités »
//   Parc.libelleEquipement(id)    « PO-02 — Pompe centrifuge eau de refroidissement »
//
// Règles de gestion : un équipement n'est jamais supprimé (champ `actif`), le repère est unique
// parmi les équipements actifs, un équipement ne peut pas être son propre ancêtre.

const Parc = (() => {

  const SEPARATEUR_CHEMIN = ' › ';
  const LIMITE_HISTORIQUE = 20;                       // lignes montrées avant « Voir les autres »
  const TAILLE_MAX_DOCUMENT = 9 * 1024 * 1024;        // le serveur refuse plus de 10 Mo
  const EXTENSIONS_DOCUMENT = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'pdf', 'txt', 'csv', 'doc', 'docx', 'xls', 'xlsx', 'odt', 'ods'];
  const STATUTS_OT_FERMES = ['Clôturé techniquement', 'Clôturé administrativement', 'Annulé'];
  const TYPE_ENFANT = { site: 'atelier', atelier: 'ligne', ligne: 'ligne' };

  // Recherche et case « inactifs » : gardées d'un affichage à l'autre (un changement distant
  // réaffiche l'écran sans faire perdre la recherche en cours).
  const etatListe = { terme: '', inactifs: false };

  // ===========================================================================================
  // 1. Petits outils (aussi offerts aux autres modules)
  // ===========================================================================================

  function estActif(ligne) {
    return ligne.actif !== '0';
  }

  function comparerTextes(a, b) {
    return String(a || '').localeCompare(String(b || ''), 'fr', { numeric: true, sensitivity: 'base' });
  }

  function parRepere(a, b) {
    return comparerTextes(a.repere, b.repere);
  }

  /** « Site › Atelier › Ligne » d'une localisation. Identifiant inconnu : l'identifiant lui-même. */
  function cheminLocalisation(id) {
    if (!id) return '';
    let courante = Donnees.trouver('localisations', id);
    if (!courante) return id;
    const libelles = [];
    const dejaVues = new Set();
    while (courante && !dejaVues.has(courante.id)) {      // dejaVues : protège d'une boucle dans les données
      dejaVues.add(courante.id);
      libelles.unshift(courante.libelle || courante.id);
      courante = courante.parent_id ? Donnees.trouver('localisations', courante.parent_id) : null;
    }
    return libelles.join(SEPARATEUR_CHEMIN);
  }

  /** « PO-02 — Pompe centrifuge eau de refroidissement ». Identifiant inconnu : l'identifiant lui-même. */
  function libelleEquipement(id) {
    if (!id) return '';
    const equipement = Donnees.trouver('equipements', id);
    if (!equipement) return id;
    const repere = equipement.repere || equipement.id;
    return equipement.designation ? repere + ' — ' + equipement.designation : repere;
  }

  /** Identifiants de tous les descendants d'une ligne (table à `parent_id`), elle-même exclue. */
  function identifiantsDescendants(nomTable, id) {
    const resultat = new Set();
    const lignes = Donnees.lignes(nomTable);
    const aTraiter = [id];
    while (aTraiter.length) {
      const courant = aTraiter.pop();
      lignes.forEach((ligne) => {
        if (ligne.parent_id === courant && ligne.id !== id && !resultat.has(ligne.id)) {
          resultat.add(ligne.id);
          aTraiter.push(ligne.id);
        }
      });
    }
    return resultat;
  }

  // Vrai si, en remontant les `parent_id` depuis `id`, on retombe sur `id` (boucle dans les données).
  function remonteSurSoi(id, lignesParId) {
    const dejaVus = new Set([id]);
    let courant = lignesParId.get(id);
    while (courant && courant.parent_id) {
      if (dejaVus.has(courant.parent_id)) return courant.parent_id === id;
      dejaVus.add(courant.parent_id);
      courant = lignesParId.get(courant.parent_id);
    }
    return false;
  }

  function abreger(texte, longueurMax) {
    const propre = String(texte || '').replace(/\s+/g, ' ').trim();
    return propre.length > longueurMax ? propre.slice(0, longueurMax - 1).trimEnd() + '…' : propre;
  }

  function badgeCriticite(criticite) {
    const tons = { A: 'ko', B: 'attention', C: 'neutre' };
    const libelles = { A: 'très critique', B: 'critique', C: 'peu critique' };
    if (!tons[criticite]) return UI.html`<span class="badge neutre" title="Criticité non renseignée">Crit. —</span>`;
    return UI.html`<span class="badge ${tons[criticite]}" title="Criticité ${criticite} (${libelles[criticite]})">Crit. ${criticite}</span>`;
  }

  // Badges d'une ligne de l'arbre : criticité, statut s'il n'est pas « en service », mention inactif.
  function badgesEquipement(equipement) {
    return UI.html`${badgeCriticite(equipement.criticite)}
      ${equipement.statut && equipement.statut !== 'en service' ? UI.badgeStatut(equipement.statut) : ''}
      ${estActif(equipement) ? '' : UI.html`<span class="badge neutre barre" title="Équipement désactivé">Inactif</span>`}`;
  }

  // Liste « tableau sur ordinateur, cartes sur téléphone » : le tableau déborderait de l'écran.
  // `carte(ligne)` rend le lien (<a>) d'une carte ; `lien(ligne)` donne la route d'une ligne cliquable.
  function listeAdaptative({ colonnes, lignes, vide, libelle, lien, carte }) {
    if (UI.estTelephone()) {
      if (!lignes.length) return UI.element(UI.html`<p class="muted">${vide}</p>`);
      return UI.element(UI.html`<ul class="liste-cartes">${lignes.map((ligne) => UI.html`<li>${carte(ligne)}</li>`)}</ul>`);
    }
    return UI.tableau({
      colonnes, lignes, vide, libelle,
      surClic: lien ? (ligne) => App.naviguer(lien(ligne)) : undefined,
    });
  }

  // ===========================================================================================
  // 2. Contrôles de saisie (purs : testés sans écran)
  // ===========================================================================================

  /**
   * Contrôle les valeurs d'un équipement. Renvoie [{ nom, message }] (vide si tout va bien).
   *   valeurs : champs du formulaire ; lignesEquipements / lignesLocalisations : données à jour ;
   *   idCourant : identifiant de l'équipement modifié ('' pour une création).
   */
  function verifierEquipement(valeurs, lignesEquipements, lignesLocalisations, idCourant) {
    const erreurs = [];
    const courant = lignesEquipements.find((e) => e.id === idCourant);
    const seraActif = !courant || estActif(courant);
    const repere = String(valeurs.repere || '').trim();

    if (!repere) {
      erreurs.push({ nom: 'repere', message: 'Le repère est obligatoire (ex. PO-02).' });
    } else if (seraActif) {
      const motif = UI.normaliserRecherche(repere);
      const double = lignesEquipements.find((e) => e.id !== idCourant && estActif(e) && UI.normaliserRecherche(e.repere) === motif);
      if (double) {
        erreurs.push({ nom: 'repere', message: 'Le repère « ' + repere + ' » est déjà utilisé par un équipement actif : '
          + libelleEquipement(double.id) + '. Choisissez-en un autre.' });
      }
    }

    if (!String(valeurs.designation || '').trim()) {
      erreurs.push({ nom: 'designation', message: 'La désignation est obligatoire (ex. Pompe centrifuge).' });
    }

    if (valeurs.localisation_id && !lignesLocalisations.some((l) => l.id === valeurs.localisation_id)) {
      erreurs.push({ nom: 'localisation_id', message: 'Cette localisation n\'existe pas.' });
    }

    if (valeurs.parent_id) {
      const parents = new Map(lignesEquipements.map((e) => [e.id, e]));
      if (idCourant && valeurs.parent_id === idCourant) {
        erreurs.push({ nom: 'parent_id', message: 'Un équipement ne peut pas être son propre parent.' });
      } else if (!parents.has(valeurs.parent_id)) {
        erreurs.push({ nom: 'parent_id', message: 'L\'équipement parent n\'existe pas.' });
      } else if (idCourant && remonteParentJusqua(valeurs.parent_id, idCourant, parents)) {
        erreurs.push({ nom: 'parent_id', message: 'Boucle interdite : « ' + libelleEquipement(valeurs.parent_id)
          + ' » est déjà un sous-équipement de celui-ci.' });
      }
    }

    const criticites = ['A', 'B', 'C'];
    if (valeurs.criticite && !criticites.includes(valeurs.criticite)) {
      erreurs.push({ nom: 'criticite', message: 'La criticité doit être A, B ou C.' });
    }
    if (valeurs.statut && !['en service', 'arrêt', 'rebut'].includes(valeurs.statut)) {
      erreurs.push({ nom: 'statut', message: 'Le statut doit être « en service », « arrêt » ou « rebut ».' });
    }
    if (valeurs.heures_fonct_jour) {
      const heures = UI.enNombre(valeurs.heures_fonct_jour);
      if (heures === null || heures < 0 || heures > 24) {
        erreurs.push({ nom: 'heures_fonct_jour', message: 'Saisissez un nombre d\'heures entre 0 et 24 (ex. 16).' });
      }
    }
    return erreurs;
  }

  // Vrai si `ancetre` figure parmi les parents (de parent en parent) de `depart`, lui compris.
  function remonteParentJusqua(depart, ancetre, lignesParId) {
    const dejaVus = new Set();
    let courant = lignesParId.get(depart);
    while (courant && !dejaVus.has(courant.id)) {
      if (courant.id === ancetre) return true;
      dejaVus.add(courant.id);
      courant = courant.parent_id ? lignesParId.get(courant.parent_id) : null;
    }
    return false;
  }

  /** Contrôle les valeurs d'une localisation. Renvoie [{ nom, message }]. */
  function verifierLocalisation(valeurs, lignesLocalisations, idCourant) {
    const erreurs = [];
    const libelle = String(valeurs.libelle || '').trim();
    if (!libelle) {
      erreurs.push({ nom: 'libelle', message: 'Le libellé est obligatoire (ex. Atelier Usinage).' });
    }
    if (!['site', 'atelier', 'ligne'].includes(valeurs.type)) {
      erreurs.push({ nom: 'type', message: 'Choisissez un type : site, atelier ou ligne.' });
    }
    if (valeurs.parent_id) {
      const parents = new Map(lignesLocalisations.map((l) => [l.id, l]));
      if (idCourant && valeurs.parent_id === idCourant) {
        erreurs.push({ nom: 'parent_id', message: 'Une localisation ne peut pas être sa propre parente.' });
      } else if (!parents.has(valeurs.parent_id)) {
        erreurs.push({ nom: 'parent_id', message: 'La localisation parente n\'existe pas.' });
      } else if (idCourant && remonteParentJusqua(valeurs.parent_id, idCourant, parents)) {
        erreurs.push({ nom: 'parent_id', message: 'Boucle interdite : la localisation parente est déjà située dans celle-ci.' });
      }
    }
    if (libelle) {
      const motif = UI.normaliserRecherche(libelle);
      const jumelle = lignesLocalisations.find((l) => l.id !== idCourant && (l.parent_id || '') === (valeurs.parent_id || '')
        && UI.normaliserRecherche(l.libelle) === motif);
      if (jumelle) {
        erreurs.push({ nom: 'libelle', message: 'Il existe déjà une localisation « ' + jumelle.libelle + ' » à cet endroit.' });
      }
    }
    return erreurs;
  }

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

  // ===========================================================================================
  // 4. Localisation : création et modification dans une fenêtre
  // ===========================================================================================

  // Valeurs des champs (name=…) d'un bloc : les fenêtres de UI vivent déjà dans un <form>.
  function lireChamps(bloc) {
    const valeurs = {};
    UI.$$('[name]', bloc).forEach((controle) => { valeurs[controle.name] = String(controle.value || '').trim(); });
    return valeurs;
  }

  function afficherErreurs(bloc, erreurs) {
    UI.$$('.champ', bloc).forEach((champ) => UI.erreurChamp(bloc, champ.dataset.champ, ''));
    erreurs.forEach((erreur) => UI.erreurChamp(bloc, erreur.nom, erreur.message));
    const premier = UI.$('[aria-invalid="true"]', bloc);
    if (premier) premier.focus();
  }

  async function ouvrirFenetreLocalisation(idExistant) {
    const existante = idExistant ? Donnees.trouver('localisations', idExistant) : null;
    if (idExistant && !existante) { UI.toast('Cette localisation n\'existe plus.', 'attention'); return; }
    const champsSchema = Schema.table('localisations').champs;
    const definition = (nom) => champsSchema.find((c) => c.nom === nom);
    const exclus = existante ? identifiantsDescendants('localisations', existante.id) : new Set();
    if (existante) exclus.add(existante.id);
    const parents = Donnees.lignes('localisations').filter((l) => !exclus.has(l.id))
      .map((l) => ({ valeur: l.id, libelle: cheminLocalisation(l.id) }))
      .sort((a, b) => comparerTextes(a.libelle, b.libelle));

    const contenu = UI.element(UI.html`<div class="form-colonne parc-formulaire-localisation"></div>`);
    contenu.appendChild(UI.champ(definition('libelle'), existante ? existante.libelle : '', { attributs: { maxlength: '80' } }));
    const blocParent = UI.champ(definition('parent_id'), existante ? existante.parent_id : '', {
      liste: parents, aide: 'Laissez vide pour un site. Un atelier se range dans un site, une ligne dans un atelier.',
    });
    contenu.appendChild(blocParent);
    const blocType = UI.champ(definition('type'), existante ? existante.type : 'atelier');
    contenu.appendChild(blocType);
    contenu.appendChild(UI.element(UI.html`<p class="mention-requis"><span class="requis" aria-hidden="true">*</span>champ obligatoire</p>`));

    // Le type suit le parent tant que l'utilisateur ne l'a pas choisi lui-même.
    let typeChoisi = Boolean(existante);
    UI.$('select', blocType).addEventListener('change', () => { typeChoisi = true; });
    UI.$('select', blocParent).addEventListener('change', (evenement) => {
      if (typeChoisi) return;
      const parent = Donnees.trouver('localisations', evenement.target.value);
      UI.$('select', blocType).value = parent ? (TYPE_ENFANT[parent.type] || 'atelier') : 'site';
    });

    let fermerFenetre = null;
    let enregistre = false;
    let enCours = false;

    async function enregistrer() {
      if (enCours) return;
      const erreursSaisie = UI.verifierFormulaire(contenu);
      const valeurs = lireChamps(contenu);
      const erreurs = erreursSaisie.concat(verifierLocalisation(valeurs, Donnees.lignes('localisations'), idExistant)
        .filter((e) => !erreursSaisie.some((s) => s.nom === e.nom)));
      afficherErreurs(contenu, erreurs);
      if (erreurs.length) return;
      enCours = true;
      try {
        await Donnees.modifier('localisations', (lignes, outils) => {
          const problemes = verifierLocalisation(valeurs, lignes, idExistant);
          if (problemes.length) throw new Donnees.ErreurValidation(problemes.map((p) => p.message).join(' '));
          if (existante) {
            const ligne = lignes.find((l) => l.id === idExistant);
            if (!ligne) throw new Donnees.ErreurValidation('Cette localisation n\'existe plus.');
            Object.assign(ligne, { libelle: valeurs.libelle, parent_id: valeurs.parent_id, type: valeurs.type });
            return ligne.id;
          }
          const id = outils.nouvelId(lignes);
          lignes.push({ id, libelle: valeurs.libelle, parent_id: valeurs.parent_id, type: valeurs.type });
          return id;
        }, { action: existante ? 'modification de la localisation' : 'création de la localisation' });
        enregistre = true;
        fermerFenetre('ok');
      } catch (erreur) {
        if (erreur instanceof Donnees.ErreurValidation) {
          afficherErreurs(contenu, verifierLocalisation(valeurs, Donnees.lignes('localisations'), idExistant));
        }
        App.signalerErreur(erreur, 'enregistrement de la localisation');
      } finally {
        enCours = false;
      }
    }

    const choix = await UI.fenetre({
      titre: existante ? 'Modifier la localisation' : 'Nouvelle localisation',
      contenu,
      boutons: [
        { libelle: 'Annuler', valeur: null, classe: 'btn-fantome' },
        { libelle: 'Enregistrer', valeur: 'ok', classe: 'btn-primaire', defaut: true },
      ],
      surOuverture(dialogue, fermer) { fermerFenetre = fermer; },
      avantFermeture(valeur) {
        if (valeur !== 'ok' || enregistre) return true;
        enregistrer();                                  // la fenêtre se ferme toute seule si tout va bien
        return false;
      },
    });
    if (choix === 'ok') {
      UI.toast(existante ? 'Localisation modifiée.' : 'Localisation créée.', 'succes');
      await App.reafficher();
    }
  }

  // ===========================================================================================
  // 5. Écran #/equipement/<id> : fiche
  // ===========================================================================================

  // Adresse d'un document (async : en mode serveur c'est /api/documents/<nom>). null si introuvable.
  async function adresseDocument(nom) {
    if (!nom || !App.adaptateur) return null;
    try {
      return await App.adaptateur.urlDocument(nom);
    } catch (erreur) {
      console.warn('Prévo : document « ' + nom + ' » illisible (' + (erreur && erreur.message) + ').', erreur);
      return null;
    }
  }

  function carteConsignation(equipement) {
    const procedure = String(equipement.consignation || '').trim();
    const habilitation = String(equipement.habilitation_requise || '').trim();
    return UI.html`
      <section class="carte parc-consignation" aria-labelledby="parc-titre-consignation">
        <div class="entete-carte">
          <h2 id="parc-titre-consignation">${UI.icone('alerte')} Consignation avant intervention</h2>
          ${habilitation ? UI.html`<span class="badge attention parc-habilitation">Habilitation requise : ${habilitation}</span>` : ''}
        </div>
        <p class="parc-rappel"><b>Cocher une case ne consigne rien : appliquez la procédure.</b></p>
        ${procedure
          ? UI.html`<div class="parc-procedure">${procedure}</div>`
          : UI.html`<div class="encadre manque"><b>Aucune procédure de consignation n'est renseignée pour cet équipement.</b>
              Avant d'intervenir, demandez-la au responsable.</div>`}
        ${habilitation ? '' : UI.html`<p class="note">Aucune habilitation particulière n'est demandée pour cet équipement.</p>`}
      </section>`;
  }

  function carteCaracteristiques(equipement, lienDocument) {
    const parent = equipement.parent_id ? Donnees.trouver('equipements', equipement.parent_id) : null;
    const heures = UI.enNombre(equipement.heures_fonct_jour);
    let documentHtml = '';
    if (equipement.document) {
      documentHtml = lienDocument
        ? UI.html`<a href="${lienDocument}" target="_blank" rel="noopener">${UI.icone('document')} ${equipement.document}</a>`
        : UI.html`${equipement.document} <span class="badge attention">fichier introuvable</span>`;
    }
    return UI.html`
      <article class="carte">
        <h2>Fiche technique</h2>
        <dl class="valeurs">
          <dt>Identifiant</dt><dd>${equipement.id}</dd>
          <dt>Repère</dt><dd>${equipement.repere}</dd>
          <dt>Désignation</dt><dd>${equipement.designation}</dd>
          <dt>Localisation</dt><dd>${equipement.localisation_id ? cheminLocalisation(equipement.localisation_id) : ''}</dd>
          <dt>Équipement parent</dt><dd>${parent ? UI.html`<a href="#/equipement/${encodeURIComponent(parent.id)}">${libelleEquipement(parent.id)}</a>` : ''}</dd>
          <dt>Marque</dt><dd>${equipement.marque}</dd>
          <dt>Modèle</dt><dd>${equipement.modele}</dd>
          <dt>Numéro de série</dt><dd>${equipement.num_serie}</dd>
          <dt>Mise en service</dt><dd>${UI.dateFr(equipement.date_mes)}</dd>
          <dt>Criticité</dt><dd>${equipement.criticite ? badgeCriticite(equipement.criticite) : ''}</dd>
          <dt>Statut</dt><dd>${equipement.statut ? UI.badgeStatut(equipement.statut) : ''}</dd>
          <dt>Heures par jour</dt><dd>${heures === null ? '' : UI.heures(heures)}</dd>
          <dt>Habilitation requise</dt><dd>${equipement.habilitation_requise}</dd>
          <dt>Document</dt><dd>${documentHtml}</dd>
          <dt>Actif</dt><dd>${estActif(equipement) ? 'Oui' : 'Non — équipement désactivé'}</dd>
        </dl>
      </article>`;
  }

  function carteQr(equipement) {
    const texte = App.urlFicheEquipement(equipement.id);
    let dessin;
    try {
      dessin = UI.qrSvg(texte, 200);
    } catch (erreur) {
      console.warn('Prévo : QR code impossible (' + (erreur && erreur.message) + ').', erreur);
      dessin = UI.html`<p class="muted">QR code indisponible.</p>`;
    }
    const consigne = App.mode === 'serveur'
      ? 'Scannez avec l\'appareil photo du téléphone : la fiche de cet équipement s\'ouvre.'
      : 'Code ' + texte + ', lisible par la caméra du poste.';
    return UI.html`
      <article class="carte parc-qr-carte">
        <h2>QR code de l'équipement</h2>
        <div class="qr">${dessin}<span class="repere">${equipement.repere || equipement.id}</span></div>
        <p class="note">${consigne}</p>
      </article>`;
  }

  function carteCompteurs(equipement) {
    const compteurs = Donnees.lignes('compteurs').filter((c) => c.equipement_id === equipement.id);
    const lignes = compteurs.map((compteur) => {
      const releves = Donnees.lignes('releves').filter((r) => r.compteur_id === compteur.id)
        .sort((a, b) => comparerTextes(b.date, a.date) || comparerTextes(b.id, a.id));
      const dernier = releves[0];
      return UI.html`<li>
        <b>${compteur.libelle || compteur.id}</b>
        ${dernier
          ? UI.html`<span>Dernier relevé : <b class="fort">${UI.nombreFr(dernier.valeur)}${compteur.unite ? ' ' + compteur.unite : ''}</b>
              le ${UI.dateFr(dernier.date)}${dernier.utilisateur ? ' (' + dernier.utilisateur + ')' : ''}</span>`
          : UI.html`<span class="muted">Aucun relevé.</span>`}
      </li>`;
    });
    return UI.html`
      <article class="carte">
        <h2>Compteurs</h2>
        ${lignes.length ? UI.html`<ul class="parc-compteurs">${lignes}</ul>` : UI.html`<p class="muted">Aucun compteur sur cet équipement.</p>`}
      </article>`;
  }

  function carteSousEquipements(equipement) {
    const enfants = Donnees.lignes('equipements').filter((e) => e.parent_id === equipement.id).sort(parRepere);
    if (!enfants.length) return '';
    return UI.html`
      <article class="carte">
        <h2>Sous-équipements <span class="badge">${enfants.length}</span></h2>
        <ul class="liste-cartes">${enfants.map((enfant) => UI.html`<li><a href="#/equipement/${encodeURIComponent(enfant.id)}">
          <div class="carte-tete"><b>${enfant.repere || enfant.id}</b>${badgesEquipement(enfant)}</div>
          <div class="carte-titre">${enfant.designation}</div></a></li>`)}</ul>
      </article>`;
  }

  function carteArticles(equipement) {
    const liens = Donnees.lignes('article_equipement').filter((l) => l.equipement_id === equipement.id);
    const lignes = liens.map((lien) => {
      const article = Donnees.trouver('articles', lien.article_id);
      return {
        id: lien.id,
        reference: article ? article.reference : lien.article_id,
        designation: article ? article.designation : '(article inconnu)',
        quantite: lien.quantite,
        unite: article ? article.unite : '',
        emplacement: article ? article.emplacement : '',
        stock: article ? Donnees.stockArticle(article.id) : null,
        stockSecurite: article ? UI.enNombre(article.stock_securite) : null,
      };
    }).sort((a, b) => comparerTextes(a.reference, b.reference));

    function etatStock(ligne) {
      if (ligne.stock === null) return '';
      if (ligne.stock <= 0) return UI.html` <span class="badge ko">Rupture</span>`;
      if (ligne.stockSecurite !== null && ligne.stock <= ligne.stockSecurite) return UI.html` <span class="badge attention">Stock bas</span>`;
      return '';
    }
    const texteStock = (ligne) => (ligne.stock === null ? '–' : UI.nombreFr(ligne.stock) + (ligne.unite ? ' ' + ligne.unite : ''));
    const liste = listeAdaptative({
      lignes,
      vide: 'Aucune pièce n\'est liée à cet équipement.',
      libelle: 'Articles liés à l\'équipement',
      colonnes: [
        { cle: 'reference', libelle: 'Référence' },
        { cle: 'designation', libelle: 'Désignation' },
        { cle: 'quantite', libelle: 'Quantité', type: 'nombre', rendu: (l) => UI.nombreFr(l.quantite) },
        { cle: 'stock', libelle: 'En stock', type: 'nombre', rendu: (l) => UI.html`${texteStock(l)}${etatStock(l)}` },
        { cle: 'emplacement', libelle: 'Emplacement' },
      ],
      carte: (l) => UI.html`<div class="carte-ligne">
        <div class="carte-tete"><b>${l.reference}</b>${etatStock(l)}</div>
        <div class="carte-titre">${l.designation}</div>
        <div class="carte-meta"><span>Quantité : ${UI.nombreFr(l.quantite)}</span><span>En stock : ${texteStock(l)}</span>
          ${l.emplacement ? UI.html`<span>Emplacement : ${l.emplacement}</span>` : ''}</div></div>`,
    });
    const carte = UI.element(UI.html`<article class="carte"><h2>Pièces liées <span class="badge">${lignes.length}</span></h2><div class="parc-liste"></div></article>`);
    UI.$('.parc-liste', carte).appendChild(liste);
    return carte;
  }

  // Carte « historique » : les plus récentes d'abord, « Voir les autres » au-delà de LIMITE_HISTORIQUE.
  function carteHistorique(titre, lignes, construire) {
    const carte = UI.element(UI.html`<article class="carte">
      <div class="entete-carte"><h2>${titre} <span class="badge">${lignes.length}</span></h2></div>
      <div class="parc-liste"></div>
      <div class="actions" hidden><button type="button" class="btn btn-secondaire parc-voir-tout"></button></div>
    </article>`);
    const zone = UI.$('.parc-liste', carte);
    const zoneBouton = UI.$('.actions', carte);
    const bouton = UI.$('.parc-voir-tout', carte);
    let toutVoir = false;
    function dessiner() {
      UI.remplir(zone, construire(toutVoir ? lignes : lignes.slice(0, LIMITE_HISTORIQUE)));
      zoneBouton.hidden = lignes.length <= LIMITE_HISTORIQUE;
      bouton.textContent = toutVoir ? 'Réduire la liste' : 'Voir les ' + (lignes.length - LIMITE_HISTORIQUE) + ' autres';
    }
    bouton.addEventListener('click', () => { toutVoir = !toutVoir; dessiner(); });
    dessiner();
    return carte;
  }

  function carteHistoriqueOt(equipement) {
    const ordres = Donnees.lignes('ordres_travail').filter((o) => o.equipement_id === equipement.id)
      .sort((a, b) => comparerTextes(b.date_creation, a.date_creation) || comparerTextes(b.id, a.id));
    return carteHistorique('Historique des ordres de travail', ordres, (lignes) => listeAdaptative({
      lignes,
      vide: 'Aucun ordre de travail sur cet équipement.',
      libelle: 'Ordres de travail de l\'équipement',
      lien: (o) => '#/ot/' + encodeURIComponent(o.id),
      colonnes: [
        { cle: 'id', libelle: 'N°', rendu: (o) => UI.html`<a href="#/ot/${encodeURIComponent(o.id)}">${o.id}</a>` },
        { cle: 'date_creation', libelle: 'Date', rendu: (o) => UI.dateFr(o.date_creation), classe: 'sans-coupure' },
        { cle: 'type', libelle: 'Type' },
        { cle: 'priorite', libelle: 'Priorité', rendu: (o) => UI.badgePriorite(o.priorite) },
        { cle: 'statut', libelle: 'Statut', rendu: (o) => UI.badgeStatut(o.statut) },
        { cle: 'titre', libelle: 'Titre' },
      ],
      carte: (o) => UI.html`<a href="#/ot/${encodeURIComponent(o.id)}">
        <div class="carte-tete"><b>${o.id}</b>${UI.badgePriorite(o.priorite)}${UI.badgeStatut(o.statut)}</div>
        <div class="carte-titre">${o.titre}</div>
        <div class="carte-meta"><span>${UI.dateFr(o.date_creation)}</span><span>${o.type}</span></div></a>`,
    }));
  }

  function carteHistoriqueDi(equipement) {
    const demandes = Donnees.lignes('demandes').filter((d) => d.equipement_id === equipement.id)
      .sort((a, b) => comparerTextes(b.date_heure, a.date_heure) || comparerTextes(b.id, a.id));
    return carteHistorique('Historique des demandes d\'intervention', demandes, (lignes) => listeAdaptative({
      lignes,
      vide: 'Aucune demande d\'intervention sur cet équipement.',
      libelle: 'Demandes d\'intervention de l\'équipement',
      lien: (d) => '#/di/' + encodeURIComponent(d.id),
      colonnes: [
        { cle: 'id', libelle: 'N°', rendu: (d) => UI.html`<a href="#/di/${encodeURIComponent(d.id)}">${d.id}</a>` },
        { cle: 'date_heure', libelle: 'Date', rendu: (d) => UI.dateFr(d.date_heure), classe: 'sans-coupure' },
        { cle: 'symptome', libelle: 'Symptôme', rendu: (d) => abreger(d.symptome, 110) },
        { cle: 'statut', libelle: 'Statut', rendu: (d) => UI.badgeStatut(d.statut) },
      ],
      carte: (d) => UI.html`<a href="#/di/${encodeURIComponent(d.id)}">
        <div class="carte-tete"><b>${d.id}</b>${UI.badgeStatut(d.statut)}</div>
        <div class="carte-titre">${abreger(d.symptome, 110)}</div>
        <div class="carte-meta"><span>${UI.dateFr(d.date_heure)}</span></div></a>`,
    }));
  }

  // Désactive ou réactive un équipement (jamais de suppression : l'historique est conservé).
  async function changerActivite(equipement, activer) {
    if (!activer) {
      const ouverts = Donnees.lignes('ordres_travail').filter((o) => o.equipement_id === equipement.id && !STATUTS_OT_FERMES.includes(o.statut)).length;
      const sousEquipements = Donnees.lignes('equipements').filter((e) => e.parent_id === equipement.id && estActif(e)).length;
      let message = 'Désactiver ' + libelleEquipement(equipement.id) + ' ? Il ne sera plus proposé pour une demande ou un ordre de travail '
        + 'et disparaîtra de la liste du parc (sauf si « Afficher les inactifs » est coché). Son historique est conservé.';
      if (ouverts) message += ' Attention : ' + ouverts + ' ordre' + (ouverts > 1 ? 's' : '') + ' de travail ouvert' + (ouverts > 1 ? 's' : '') + ' le concerne' + (ouverts > 1 ? 'nt' : '') + ' encore.';
      if (sousEquipements) message += ' Ses ' + sousEquipements + ' sous-équipement(s) actif(s) ne sont pas désactivés.';
      if (!await UI.confirmer(message, { titre: 'Désactiver l\'équipement', oui: 'Désactiver', danger: true })) return;
    } else if (!await UI.confirmer('Réactiver ' + libelleEquipement(equipement.id) + ' ? Il réapparaîtra dans le parc.', { titre: 'Réactiver l\'équipement', oui: 'Réactiver' })) {
      return;
    }
    try {
      await Donnees.modifier('equipements', (lignes) => {
        const ligne = lignes.find((l) => l.id === equipement.id);
        if (!ligne) throw new Donnees.ErreurValidation('Cet équipement n\'existe plus.');
        if (activer) {
          const double = lignes.find((l) => l.id !== ligne.id && estActif(l) && UI.normaliserRecherche(l.repere) === UI.normaliserRecherche(ligne.repere));
          if (double) {
            throw new Donnees.ErreurValidation('Réactivation impossible : le repère « ' + ligne.repere + ' » est maintenant utilisé par '
              + libelleEquipement(double.id) + '. Changez le repère de l\'un des deux.');
          }
        }
        ligne.actif = activer ? '1' : '0';
      }, { action: activer ? 'réactivation' : 'désactivation' });
      UI.toast(activer ? 'Équipement réactivé.' : 'Équipement désactivé.', 'succes');
      await App.reafficher();
    } catch (erreur) {
      App.signalerErreur(erreur, activer ? 'réactivation' : 'désactivation');
    }
  }

  async function afficherFiche(conteneur, parametres) {
    const equipement = Donnees.trouver('equipements', parametres.id);
    if (!equipement) {
      App.definirTitre('Équipement introuvable');
      UI.remplir(conteneur, UI.html`<div class="parc">
        <div class="entete-page"><div>
          <div class="fil"><a href="#/parc">Parc</a></div>
          <h1>Équipement introuvable</h1>
        </div></div>
        ${UI.vide('Aucun équipement ne porte l\'identifiant « ' + parametres.id + ' »',
          'Le QR code est peut-être celui d\'un autre atelier, ou l\'équipement a été saisi sur un autre poste.', 'recherche')}
        <p><a class="btn btn-secondaire" href="#/parc">Retour au parc</a></p></div>`);
      return;
    }
    App.definirTitre(equipement.repere || equipement.id);
    const responsable = App.estResponsable();
    const adresse = await adresseDocument(equipement.document);
    const idUrl = encodeURIComponent(equipement.id);
    const actif = estActif(equipement);
    const sousEquipements = carteSousEquipements(equipement);

    UI.remplir(conteneur, UI.html`
      <div class="parc">
        <div class="entete-page">
          <div>
            <div class="fil"><a href="#/parc">Parc</a>${equipement.localisation_id ? UI.html` <span aria-hidden="true">›</span> <span>${cheminLocalisation(equipement.localisation_id)}</span>` : ''}</div>
            <h1>${libelleEquipement(equipement.id)}</h1>
            <p class="parc-badges-fiche">${badgeCriticite(equipement.criticite)} ${equipement.statut ? UI.badgeStatut(equipement.statut) : ''}
              ${actif ? '' : UI.html`<span class="badge neutre barre">Inactif</span>`}</p>
          </div>
        </div>

        <div class="parc-actions">
          <a class="btn btn-primaire btn-gros parc-signaler" href="#/di/nouvelle?equipement=${idUrl}">${UI.icone('alerte')}
            <span>Signaler un problème<small>Une panne, une fuite, un bruit anormal : prévenez la maintenance</small></span></a>
          ${responsable ? UI.html`<div class="actions">
            <a class="btn btn-secondaire" href="#/ot/nouveau?equipement=${idUrl}">${UI.icone('ordres')}Créer un OT</a>
            <a class="btn btn-secondaire" href="#/equipement/${idUrl}/modifier">${UI.icone('cle')}Modifier</a>
            <button type="button" class="btn ${actif ? 'btn-danger' : 'btn-secondaire'}" id="parc-activite">${actif ? 'Désactiver' : 'Réactiver'}</button>
          </div>` : ''}
        </div>

        ${actif ? '' : UI.html`<div class="alertes"><div class="alerte attention" role="status">${UI.icone('alerte')}
          <div class="alerte-texte"><b>Cet équipement est désactivé.</b> Il n'est plus proposé pour les demandes et les ordres de travail ; son historique reste consultable.</div></div></div>`}

        ${carteConsignation(equipement)}

        <div class="grille">
          <div class="c8">${carteCaracteristiques(equipement, adresse)}</div>
          <div class="c4">${carteQr(equipement)}</div>
        </div>
        <div class="grille">
          <div class="${sousEquipements ? 'c6' : 'c12'}">${carteCompteurs(equipement)}</div>
          ${sousEquipements ? UI.html`<div class="c6">${sousEquipements}</div>` : ''}
        </div>
        <div class="parc-complements"></div>
      </div>`);

    const zone = UI.$('.parc-complements', conteneur);
    zone.appendChild(carteArticles(equipement));
    zone.appendChild(carteHistoriqueOt(equipement));
    zone.appendChild(carteHistoriqueDi(equipement));

    const boutonActivite = UI.$('#parc-activite', conteneur);
    if (boutonActivite) boutonActivite.addEventListener('click', () => changerActivite(equipement, !actif));
  }

  // ===========================================================================================
  // 6. Écrans #/equipement/nouveau et #/equipement/<id>/modifier : formulaire
  // ===========================================================================================

  function extensionDe(nomFichier) {
    const point = String(nomFichier || '').lastIndexOf('.');
    return point === -1 ? '' : nomFichier.slice(point + 1).toLowerCase();
  }

  async function afficherFormulaire(conteneur, parametres) {
    const idCourant = parametres.id || '';
    const existant = idCourant ? Donnees.trouver('equipements', idCourant) : null;
    if (idCourant && !existant) {
      UI.remplir(conteneur, UI.html`<div class="parc"><div class="entete-page"><div><div class="fil"><a href="#/parc">Parc</a></div><h1>Équipement introuvable</h1></div></div>
        ${UI.vide('Équipement introuvable', 'Aucun équipement ne porte l\'identifiant « ' + idCourant + ' ».', 'recherche')}</div>`);
      return;
    }
    App.definirTitre(existant ? 'Modifier ' + (existant.repere || existant.id) : 'Nouvel équipement');
    const champsSchema = Schema.table('equipements').champs;
    const definition = (nom) => champsSchema.find((c) => c.nom === nom);
    const valeur = (nom) => (existant ? existant[nom] : undefined);

    // Listes déroulantes : localisations (avec leur chemin) et équipements parents possibles.
    const listeLocalisations = Donnees.lignes('localisations')
      .map((l) => ({ valeur: l.id, libelle: cheminLocalisation(l.id) }))
      .sort((a, b) => comparerTextes(a.libelle, b.libelle));
    const interdits = existant ? identifiantsDescendants('equipements', existant.id) : new Set();
    if (existant) interdits.add(existant.id);
    const listeParents = Donnees.lignes('equipements').filter((e) => !interdits.has(e.id))
      .sort(parRepere).map((e) => ({ valeur: e.id, libelle: libelleEquipement(e.id) }));

    const retour = existant ? '#/equipement/' + encodeURIComponent(existant.id) : '#/parc';
    UI.remplir(conteneur, UI.html`
      <div class="parc">
        <div class="entete-page"><div>
          <div class="fil"><a href="#/parc">Parc</a> <span aria-hidden="true">›</span>
            ${existant ? UI.html`<a href="${retour}">${existant.repere || existant.id}</a>` : UI.html`<span>Nouvel équipement</span>`}</div>
          <h1>${existant ? 'Modifier ' + libelleEquipement(existant.id) : 'Nouvel équipement'}</h1>
        </div></div>
        <article class="carte"><form class="form-grille" id="parc-formulaire" novalidate></form></article>
      </div>`);
    const formulaire = UI.$('#parc-formulaire', conteneur);
    const ajouter = (bloc, large) => { if (large) bloc.classList.add('large'); formulaire.appendChild(bloc); return bloc; };

    ajouter(UI.champ(definition('repere'), valeur('repere'), {
      aide: 'Code court, unique parmi les équipements actifs (ex. PO-02).', attributs: { maxlength: '40' },
    }));
    ajouter(UI.champ(definition('designation'), valeur('designation'), { attributs: { maxlength: '120' } }));
    ajouter(UI.champ(definition('localisation_id'), valeur('localisation_id'), { liste: listeLocalisations }));
    ajouter(UI.champ(definition('parent_id'), valeur('parent_id'), {
      liste: listeParents, aide: 'À remplir pour un sous-ensemble (ex. le motoréducteur d\'un convoyeur).',
    }));
    ajouter(UI.champ(definition('marque'), valeur('marque')));
    ajouter(UI.champ(definition('modele'), valeur('modele')));
    ajouter(UI.champ(definition('num_serie'), valeur('num_serie')));
    ajouter(UI.champ(definition('date_mes'), valeur('date_mes')));
    ajouter(UI.champ(definition('criticite'), valeur('criticite'), {
      aide: 'A : l\'arrêt bloque la production ou la sécurité. B : gênant. C : sans conséquence immédiate.',
    }));
    ajouter(UI.champ(definition('statut'), valeur('statut')));
    ajouter(UI.champ(definition('heures_fonct_jour'), valeur('heures_fonct_jour'), { aide: 'Utilisé pour estimer l\'usage entre deux relevés (0 à 24).' }));
    ajouter(UI.champ(definition('habilitation_requise'), valeur('habilitation_requise'), {
      aide: 'Ex. BR. Plusieurs habilitations : séparées par une virgule.',
    }));
    ajouter(UI.champ(definition('consignation'), valeur('consignation'), {
      aide: 'Une étape par ligne. Ce texte s\'affiche sur la fiche et sur les ordres de travail.',
    }), true);

    const idFichier = UI.identifiantUnique('parc-document');
    const blocDocument = ajouter(UI.element(UI.html`<div class="champ" data-champ="document_fichier">
      <label class="libelle" for="${idFichier}">Document (fiche technique, notice…)</label>
      <input type="file" id="${idFichier}" accept=".${EXTENSIONS_DOCUMENT.join(',.')}" aria-describedby="${idFichier}-aide ${idFichier}-erreur">
      <p class="aide" id="${idFichier}-aide">${existant && existant.document
        ? 'Document actuel : ' + existant.document + '. Choisir un fichier le remplace.' : 'PDF, image ou tableur, 9 Mo au maximum.'}</p>
      <p class="erreur-champ" id="${idFichier}-erreur" role="alert" hidden></p>
    </div>`), true);
    formulaire.appendChild(UI.element(UI.html`<p class="mention-requis large"><span class="requis" aria-hidden="true">*</span>champ obligatoire</p>`)).classList.add('large');
    formulaire.appendChild(UI.element(UI.html`<div class="actions">
      <button type="submit" class="btn btn-primaire">${UI.icone('valider')}Enregistrer</button>
      <a class="btn btn-fantome" href="${retour}">Annuler</a>
    </div>`));

    let enCours = false;
    formulaire.addEventListener('submit', async (evenement) => {
      evenement.preventDefault();
      if (enCours) return;
      const valeurs = UI.lireFormulaire(formulaire);
      const erreursSaisie = UI.verifierFormulaire(formulaire);
      const erreurs = erreursSaisie.concat(verifierEquipement(valeurs, Donnees.lignes('equipements'), Donnees.lignes('localisations'), idCourant)
        .filter((e) => !erreursSaisie.some((s) => s.nom === e.nom)));

      const fichier = UI.$('input[type=file]', blocDocument).files[0];
      let messageFichier = '';
      if (fichier) {
        if (!EXTENSIONS_DOCUMENT.includes(extensionDe(fichier.name))) messageFichier = 'Ce type de fichier n\'est pas accepté (PDF, images, documents Office ou texte).';
        else if (fichier.size > TAILLE_MAX_DOCUMENT) messageFichier = 'Ce fichier est trop volumineux (9 Mo au maximum).';
      }
      if (messageFichier) erreurs.push({ nom: 'document_fichier', message: messageFichier });
      afficherErreurs(formulaire, erreurs);
      if (erreurs.length) return;

      const bouton = UI.$('button[type=submit]', formulaire);
      enCours = true;
      bouton.disabled = true;
      bouton.setAttribute('aria-busy', 'true');
      try {
        if (fichier) {
          const nom = UI.nomFichierUnique(valeurs.repere, extensionDe(fichier.name));
          valeurs.document = await App.adaptateur.ecrireDocument(nom, fichier);
        }
        const id = await Donnees.modifier('equipements', (lignes, outils) => {
          const problemes = verifierEquipement(valeurs, lignes, Donnees.lignes('localisations'), idCourant);
          if (problemes.length) throw new Donnees.ErreurValidation(problemes.map((p) => p.message).join(' '));
          if (existant) {
            const ligne = lignes.find((l) => l.id === idCourant);
            if (!ligne) throw new Donnees.ErreurValidation('Cet équipement n\'existe plus.');
            Object.assign(ligne, valeurs);
            return ligne.id;
          }
          const nouvelId = outils.nouvelId(lignes);
          lignes.push(Object.assign({ id: nouvelId, actif: '1' }, valeurs));
          return nouvelId;
        }, { action: existant ? 'modification de l\'équipement' : 'création de l\'équipement' });
        App.marquerSaisie(false);
        UI.toast(existant ? 'Équipement enregistré.' : 'Équipement créé.', 'succes');
        App.naviguer('#/equipement/' + encodeURIComponent(id));
      } catch (erreur) {
        if (erreur instanceof Donnees.ErreurValidation) {
          afficherErreurs(formulaire, verifierEquipement(valeurs, Donnees.lignes('equipements'), Donnees.lignes('localisations'), idCourant));
        }
        App.signalerErreur(erreur, 'enregistrement de l\'équipement');
      } finally {
        enCours = false;
        bouton.disabled = false;
        bouton.removeAttribute('aria-busy');
      }
    });
  }

  // ===========================================================================================
  // 7. Enregistrement des écrans (App est chargé après les modules : on attend la page)
  // ===========================================================================================

  document.addEventListener('DOMContentLoaded', () => {
    const tous = ['demandeur', 'technicien', 'responsable'];
    App.ecran({
      id: 'parc', route: /^#\/parc$/, titre: 'Parc',
      menu: { libelle: 'Parc', icone: 'parc', ordre: 40 },
      profils: tous,
      tables: ['equipements', 'localisations'],
      afficher: afficherListe,
    });
    // Les routes les plus précises d'abord : « nouveau » ne doit pas être pris pour un identifiant.
    App.ecran({
      id: 'equipement-nouveau', route: /^#\/equipement\/nouveau$/, titre: 'Nouvel équipement', parent: 'parc',
      profils: ['responsable'],
      tables: [],
      afficher: afficherFormulaire,
    });
    App.ecran({
      id: 'equipement-modifier', route: /^#\/equipement\/(?<id>[^/?]+)\/modifier$/, titre: 'Modifier l\'équipement', parent: 'parc',
      profils: ['responsable'],
      tables: [],
      afficher: afficherFormulaire,
    });
    App.ecran({
      id: 'equipement', route: /^#\/equipement\/(?<id>[^/?]+)$/, titre: 'Équipement', parent: 'parc',
      profils: tous,
      tables: ['equipements', 'localisations', 'ordres_travail', 'demandes', 'compteurs', 'releves',
        'articles', 'article_equipement', 'mouvements_stock'],
      afficher: afficherFiche,
    });
  });

  return {
    cheminLocalisation,
    libelleEquipement,
    verifierEquipement,
    verifierLocalisation,
    afficherListe,
    afficherFiche,
    afficherFormulaire,
  };
})();
