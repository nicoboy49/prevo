'use strict';
// Import (6/7) — écran « Importer des données » (#/import, responsable seulement ; lot 5, ARCHITECTURE.md
// §18.9) : l'assistant en cinq étapes, une à la fois, avec « Retour ». Ce fichier porte le cadre et les
// étapes 1 « Quoi » (type, aide, modèles .xlsx et .csv), 2 « D'où » (dépôt, « Choisir un fichier »,
// collage ; feuille, ligne d'en-tête) et 3 « Colonnes » (correspondance, statut en texte et en couleur,
// « Proposer avec l'IA ») ; import-apercu.js porte les étapes 4 « Aperçu » et 5 « Importer ».
// Rien n'est écrit dans la base avant le bouton « Importer » de l'étape 5 : la seule écriture des étapes
// 1 à 4 est la correspondance validée, retenue sur ce poste (Import.memoriserCorrespondance, localStorage).
//
// Outils partagés avec import-apercu.js (interne au module, pas une API) : Import.assistant = { etat(),
//   allerA(numero), recommencer(), section(numero, titre, intro), navigation(options), entetes(), donnees(),
//   numeroPremiereLigne(), correspondanceValidee(), colonnesIa(), etapes: { numero: rendu(zone) },
//   calculerApercu (posé par import-apercu.js) }.

Object.assign(Import, (() => {

  // Titres et libellés lus à l'affichage (accesseurs : jamais figés au chargement du module).
  const ETAPES = [
    { numero: 1, get titre() { return I18n.t('import.etapes.quoi'); } }, { numero: 2, get titre() { return I18n.t('import.etapes.ou'); } },
    { numero: 3, get titre() { return I18n.t('import.etapes.colonnes'); } }, { numero: 4, get titre() { return I18n.t('import.etapes.apercu'); } },
    { numero: 5, get titre() { return I18n.t('import.etapes.importer'); } },
  ];
  const EXTENSIONS = '.xlsx,.xlsm,.xls,.ods,.csv,.tsv,.txt';
  const STATUTS = {
    sure: { get libelle() { return I18n.t('import.statut_colonne.sure'); }, ton: 'ok' },
    a_confirmer: { get libelle() { return I18n.t('import.statut_colonne.a_confirmer'); }, ton: 'attention' },
    non_utilisee: { get libelle() { return I18n.t('import.statut_colonne.non_utilisee'); }, ton: 'neutre' },
  };
  const EXTRAIT_LIGNES = 8;
  const EXTRAIT_COLONNES = 30;
  const TITRES_IA_MAX = 60;

  let etat = null;                 // état de l'assistant : neuf à chaque affichage de l'écran
  let racine = null;               // <main id="contenu"> de l'écran affiché
  let lectures = 0;                // numéro de la dernière lecture lancée (une lecture dépassée est ignorée)

  function nouvelEtat() {
    return {
      etape: 1, type: '',
      lecture: null, feuille: 0, rangEntete: 0, rangPropose: 0, deuxLignes: false,
      correspondance: null, modeleIa: '',
      // Étapes 4 et 5 (import-apercu.js)
      apercu: null, calcul: null, maintenant: '', mettreAJour: true, quandMeme: new Set(), filtre: 'tout', limite: 200,
      message: null, resultat: null, annule: false, enCours: false,
    };
  }

  // ===========================================================================================
  // 1. Petits outils
  // ===========================================================================================

  const texte = (valeur) => (valeur === null || valeur === undefined ? '' : String(valeur).trim());
  const ligneRemplie = (ligne) => (ligne || []).some((cellule) => texte(cellule) !== '');
  // Même règle que la lecture (import-lecture.js) : nombres, dates ISO ou JJ/MM/AAAA.
  const estNombreOuDate = (valeur) => /^[-+]?[\d\s.,]+$/.test(valeur) || /^\d{4}-\d{2}-\d{2}/.test(valeur)
    || /^\d{1,2}\/\d{1,2}\/\d{2,4}/.test(valeur);

  /** Lettre de colonne d'un tableur : 0 → A, 26 → AA. */
  function lettreColonne(rang) {
    let lettres = '';
    for (let n = rang + 1; n > 0; n = Math.floor((n - 1) / 26)) lettres = String.fromCharCode(65 + ((n - 1) % 26)) + lettres;
    return lettres;
  }

  function couper(valeur, longueur) {
    const brut = texte(valeur).replace(/\s+/g, ' ');
    return brut.length > longueur ? I18n.t('import.texte_coupe', { debut: brut.slice(0, longueur - 1) }) : brut;
  }

  const description = () => Import.TYPES[etat.type];
  // Un champ obligatoire, ou une clé naturelle (une clé vide refuse la ligne) ; l'ancien numéro d'OT de
  // l'historique est une clé de doublon, pas une obligation.
  const obligatoire = (champ) => champ.obligatoire || (champ.cleNaturelle && etat.type !== 'historique');
  const libelleChamp = (champ) => (obligatoire(champ) ? I18n.t('import.colonnes.champ_obligatoire', { champ: champ.libelle }) : champ.libelle);
  const nomColonne = (entree) => entree.entete || I18n.t('import.nom_colonne.colonne_lettre_colonne', { lettreColonne: lettreColonne(entree.colonne) });

  // --- Lignes de la feuille choisie : en-têtes, données (sous l'en-tête), numéro de leur 1re ligne ----------

  function lignesFeuille() {
    const feuille = etat.lecture ? etat.lecture.feuilles[etat.feuille] : null;
    return feuille ? feuille.lignes : [];
  }
  const entetes = () => Import.entetes(lignesFeuille(), etat.rangEntete, etat.deuxLignes);
  const donnees = () => lignesFeuille().slice(etat.rangEntete + (etat.deuxLignes ? 2 : 1));
  const numeroPremiereLigne = () => etat.rangEntete + (etat.deuxLignes ? 3 : 2);     // comme un tableur la numérote
  const correspondanceValidee = () => (etat.correspondance || [])
    .map((e) => ({ colonne: e.colonne, entete: e.entete, champ: e.champ, statut: e.statut }));
  /** Colonnes gardées telles que l'IA les a proposées (trace « proposition IA utilisée » après l'import). */
  const colonnesIa = () => (etat.correspondance || []).filter((e) => e.origine === 'ia' && e.champ && e.statut !== 'non_utilisee');

  // La correspondance et l'aperçu dépendent du type, du fichier, de la feuille et de l'en-tête.
  function oublierCorrespondance() {
    etat.correspondance = null;
    etat.modeleIa = '';
    oublierApercu();
  }

  function oublierApercu() {
    Object.assign(etat, { apercu: null, calcul: null, maintenant: '', message: null, filtre: 'tout', limite: 200 });
    etat.quandMeme.clear();
  }

  // ===========================================================================================
  // 2. Cadre : fil des étapes, section, navigation
  // ===========================================================================================

  function afficher(conteneur) {
    etat = nouvelEtat();
    racine = conteneur;
    UI.remplir(conteneur, UI.html`
      <div class="entete-page"><div>
        <div class="fil">${I18n.html('import.ecran.parametres_importer_donnees')}</div>
        <h1>${I18n.t('import.ecran.importer_donnees')}</h1>
        <p>${I18n.t('import.ecran.reprenez_listes_existantes_excel')}</p>
      </div></div>
      <ol class="etapes import-fil" aria-label="${I18n.t('import.ecran.etapes_import')}">
        ${ETAPES.map((e) => UI.html`<li data-etape="${e.numero}">${e.numero}. ${e.titre}</li>`)}
      </ol>
      <p class="import-etape-courte"></p>
      <div class="import-etapes"></div>`);
    rendre(false);
  }

  function allerA(numero) {
    etat.etape = numero;
    rendre(true);
  }

  /** « Importer d'autres données » : l'assistant repart de l'étape 1, sans rien garder. */
  function recommencer() {
    etat = nouvelEtat();
    rendre(true);
  }

  function rendre(focaliser) {
    // #contenu sert à tous les écrans : si l'utilisateur est parti ailleurs (fin d'une action lente), rien.
    const zone = racine ? UI.$('.import-etapes', racine) : null;
    if (!zone) return;
    UI.$$('.import-fil li', racine).forEach((li) => {
      const numero = Number(li.dataset.etape);
      li.classList.toggle('fait', numero < etat.etape);
      li.classList.toggle('courant', numero === etat.etape);
      if (numero === etat.etape) li.setAttribute('aria-current', 'step'); else li.removeAttribute('aria-current');
    });
    const courante = ETAPES.find((e) => e.numero === etat.etape);
    UI.$('.import-etape-courte', racine).textContent = I18n.t('import.rendre.etape_courante', { numero: etat.etape, total: ETAPES.length, titre: courante.titre });
    zone.textContent = '';
    assistant.etapes[etat.etape](zone);
    if (focaliser) {
      window.scrollTo(0, 0);
      const titre = UI.$('.import-etape > h2', zone);
      if (titre) titre.focus({ preventScroll: true });
    }
  }

  /** Section d'une étape : carte, titre (focalisable), introduction. */
  function section(numero, titre, intro) {
    return UI.element(UI.html`<section class="carte import-etape" data-etape="${numero}" id="import-etape-${numero}"
        aria-labelledby="import-titre-${numero}">
      <h2 id="import-titre-${numero}" tabindex="-1">${numero}. ${titre}</h2>
      ${intro ? UI.html`<p class="import-intro">${intro}</p>` : ''}
    </section>`);
  }

  /**
   * Barre « Retour » / « Continuer » d'une étape. options : { retour: numéro | null, continuer: { libelle,
   * actif, action } | null, boutons: [éléments ajoutés à droite] }.
   */
  function navigation(options) {
    const barre = UI.element(UI.html`<div class="actions import-navigation">
      ${options.retour ? UI.html`<button type="button" class="btn btn-fantome" id="import-retour">${UI.icone('retour')}${I18n.t('import.navigation.retour')}</button>` : ''}
      <span class="espace"></span>
    </div>`);
    if (options.retour) UI.$('#import-retour', barre).addEventListener('click', () => allerA(options.retour));
    (options.boutons || []).forEach((bouton) => barre.appendChild(bouton));
    if (options.continuer) {
      const bouton = UI.element(UI.html`<button type="button" class="btn btn-primaire" id="import-continuer">${options.continuer.libelle || I18n.t('commun.bouton.continuer')}${UI.icone('chevron')}</button>`);
      bouton.disabled = options.continuer.actif === false;
      bouton.addEventListener('click', () => options.continuer.action(bouton));
      barre.appendChild(bouton);
    }
    return barre;
  }

  function boutonContinuer() {
    return racine ? UI.$('#import-continuer', racine) : null;
  }

  // ===========================================================================================
  // 3. Étape 1 — Quoi : type de données, aide, modèles à remplir
  // ===========================================================================================

  function etapeQuoi(zone) {
    const element = section(1, I18n.t('import.etape_quoi.voulez_importer'), I18n.t('import.etape_quoi.import_type_donnees_reprendre'));
    const types = Object.values(Import.TYPES);
    element.appendChild(UI.element(UI.html`<fieldset class="import-types">
      <legend class="visuellement-cache">${I18n.t('import.etape_quoi.type_donnees')}</legend>
      ${types.map((type) => UI.html`<label class="import-type">
        <input type="radio" name="import-type" value="${type.cle}"${type.cle === etat.type ? UI.brut(' checked') : ''}>
        <span><b>${type.libelle}</b><small class="import-type-aide">${type.aide}</small></span>
      </label>`)}
    </fieldset>`));
    const modeles = UI.element(UI.html`<div class="import-modeles">
      <p class="note">${I18n.t('import.etape_quoi.pas_encore_fichier_telechargez')}</p>
      <div class="actions">
        <button type="button" class="btn btn-secondaire" id="import-modele-xlsx">${UI.icone('export')}${I18n.t('import.etape_quoi.modele_xlsx')}</button>
        <button type="button" class="btn btn-secondaire" id="import-modele-csv">${UI.icone('export')}${I18n.t('import.etape_quoi.modele_csv')}</button>
      </div>
    </div>`);
    element.appendChild(modeles);
    element.appendChild(navigation({ retour: null, continuer: { actif: Boolean(etat.type), action: () => allerA(2) } }));
    zone.appendChild(element);

    const majBoutons = () => {
      UI.$$('#import-modele-xlsx, #import-modele-csv', element).forEach((bouton) => { bouton.disabled = !etat.type; });
      UI.$('#import-continuer', element).disabled = !etat.type;
    };
    UI.$('.import-types', element).addEventListener('change', (evenement) => {
      if (evenement.target.name === 'import-type') choisirType(evenement.target.value);
      majBoutons();
    });
    UI.$('#import-modele-xlsx', element).addEventListener('click', (evenement) => telechargerModele('xlsx', evenement.currentTarget));
    UI.$('#import-modele-csv', element).addEventListener('click', (evenement) => telechargerModele('csv', evenement.currentTarget));
    majBoutons();
  }

  function choisirType(type) {
    if (type === etat.type) return;
    etat.type = type;
    oublierCorrespondance();
    if (etat.lecture) {                                  // la ligne d'en-tête probable dépend du type
      etat.rangPropose = Import.ligneEntete(lignesFeuille(), type);
      etat.rangEntete = etat.rangPropose;
    }
  }

  async function telechargerModele(format, bouton) {
    if (!etat.type) return;
    bouton.disabled = true;
    bouton.setAttribute('aria-busy', 'true');
    try {
      const blob = await Import.modele(etat.type, format);
      UI.telecharger(Import.nomModele(etat.type, format), blob);
    } catch (erreur) {
      App.signalerErreur(erreur, 'modèle à remplir');
    } finally {
      bouton.disabled = !etat.type;
      bouton.removeAttribute('aria-busy');
    }
  }

  // ===========================================================================================
  // 4. Étape 2 — D'où : fichier déposé ou choisi, collage ; feuille, ligne d'en-tête
  // ===========================================================================================

  function etapeOu(zone) {
    const element = section(2, I18n.t('import.etape_ou.ou_viennent_donnees'), I18n.html('import.etape_ou.type_choisi', { type: description().libelle }));
    element.appendChild(UI.element(UI.html`<div class="import-sources">
      <label class="depot import-depot" id="import-depot">
        ${UI.icone('document')}
        <b>${I18n.t('import.etape_ou.deposez_fichier')}</b>
        <span class="btn btn-secondaire import-choisir">${I18n.t('import.etape_ou.choisir_fichier')}</span>
        <small>${I18n.t('import.etape_ou.formats_lus')}</small>
        <input type="file" id="import-fichier" class="visuellement-cache" accept="${EXTENSIONS}">
      </label>
      <div class="champ import-collage">
        <label class="libelle" for="import-collage">${I18n.t('import.etape_ou.collez_cellules_copiees_tableur')}</label>
        <textarea id="import-collage" rows="6" spellcheck="false" placeholder="${I18n.t('import.etape_ou.titres_colonnes_compris')}"></textarea>
        <p class="aide">${I18n.t('import.etape_ou.selectionnez_cellules_excel_libre_office')}</p>
        <div class="actions"><button type="button" class="btn btn-secondaire" id="import-lire-collage">${I18n.t('import.etape_ou.lire_collage')}</button></div>
      </div>
    </div>`));
    element.appendChild(UI.element(UI.html`<div class="alertes import-erreur" id="import-erreur" hidden></div>`));
    element.appendChild(UI.element(UI.html`<div class="import-lu" id="import-lu" hidden></div>`));
    element.appendChild(navigation({ retour: 1, continuer: { actif: false, action: () => allerA(3) } }));
    zone.appendChild(element);

    const depot = UI.$('#import-depot', element);
    const fichier = UI.$('#import-fichier', element);
    fichier.addEventListener('change', () => {
      const choisi = fichier.files && fichier.files[0];
      fichier.value = '';                                 // le même fichier pourra être choisi de nouveau
      if (choisi) lire(choisi);
    });
    depot.addEventListener('dragover', (evenement) => { evenement.preventDefault(); depot.classList.add('survol'); });
    depot.addEventListener('dragleave', () => depot.classList.remove('survol'));
    depot.addEventListener('drop', (evenement) => {
      evenement.preventDefault();
      depot.classList.remove('survol');
      const depose = evenement.dataTransfer && evenement.dataTransfer.files ? evenement.dataTransfer.files[0] : null;
      if (depose) lire(depose);
    });
    UI.$('#import-lire-collage', element).addEventListener('click', () => {
      const colle = UI.$('#import-collage', element).value;
      if (!colle.trim()) { afficherErreur(I18n.t('import.etape_ou.collage_vide_copiez_cellules')); return; }
      lire({ texte: colle, nom: I18n.t('import.lecture.collage') });
    });
    afficherLecture();
  }

  function afficherErreur(message) {
    const zone = racine ? UI.$('#import-erreur', racine) : null;
    if (!zone) return;
    zone.textContent = '';
    zone.hidden = !message;
    if (message) zone.appendChild(UI.bandeau('important', message));
  }

  async function lire(source) {
    lectures += 1;
    const numero = lectures;
    const zoneLu = UI.$('#import-lu', racine);
    afficherErreur('');
    zoneLu.hidden = false;
    UI.remplir(zoneLu, UI.chargement(I18n.t('import.lire.lecture', { nom: source.name || source.nom || I18n.t('import.lire.fichier') })));
    const bouton = boutonContinuer();
    if (bouton) bouton.disabled = true;
    try {
      const lecture = await Import.lire(source);
      if (numero !== lectures || !zoneLu.isConnected) return;
      Object.assign(etat, { lecture, feuille: 0, deuxLignes: false });
      etat.rangPropose = Import.ligneEntete(lecture.feuilles[0].lignes, etat.type);
      etat.rangEntete = etat.rangPropose;
      oublierCorrespondance();
      afficherLecture();
    } catch (erreur) {
      if (numero !== lectures || !zoneLu.isConnected) return;
      etat.lecture = null;
      oublierCorrespondance();
      afficherLecture();
      if (!(erreur instanceof Import.ErreurImport)) console.warn('Prévo (import) : lecture impossible (' + (erreur && erreur.message) + ').', erreur);
      afficherErreur(erreur instanceof Import.ErreurImport ? erreur.message
        : I18n.t('import.lire.fichier_illisible', { raison: (erreur && erreur.message) || I18n.t('commun.message.erreur_inconnue') }));
    }
  }

  /** Problème de la ligne d'en-tête choisie (message clair), ou ''. */
  function problemeEntete() {
    const ligne = lignesFeuille()[etat.rangEntete] || [];
    const textes = ligne.map(texte).filter((cellule) => cellule && !estNombreOuDate(cellule));
    if (!textes.length) {
      return I18n.t('import.probleme_entete.aucune_ligne_entete', { numero: etat.rangEntete + 1 });
    }
    if (!donnees().some(ligneRemplie)) return I18n.t('import.probleme_entete.aucune_ligne_donnees', { numero: etat.rangEntete + 1 });
    return '';
  }

  function decrireSource(lecture) {
    if (lecture.format === 'collage') return I18n.t('import.source.collage');
    const feuilles = lecture.feuilles.length;
    const nature = ['xlsx', 'xlsm', 'xls', 'ods', 'tableur'].includes(lecture.format) ? I18n.t('import.source.classeur') : I18n.t('import.source.fichier_texte');
    const source = lecture.encodage ? I18n.t('import.source.encodage', { nature, encodage: lecture.encodage }) : nature;
    return feuilles > 1 ? I18n.t('import.source.feuilles', { source, n: feuilles }) : source;
  }

  function afficherLecture() {
    const zoneLu = racine ? UI.$('#import-lu', racine) : null;
    if (!zoneLu) return;
    if (!etat.lecture) {
      zoneLu.hidden = true;
      zoneLu.textContent = '';
      majContinuerOu();
      return;
    }
    const lecture = etat.lecture;
    const lignes = lignesFeuille();
    const maximum = Math.max(1, Math.min(lignes.length, 20));
    zoneLu.hidden = false;
    UI.remplir(zoneLu, UI.html`
      <h3>${UI.icone('document')}<span>${lecture.nom}</span> <small>(${decrireSource(lecture)})</small></h3>
      <div class="form-ligne import-reglages">
        ${lecture.feuilles.length > 1 ? UI.html`<div class="champ">
          <label class="libelle" for="import-feuille">${I18n.t('import.lecture.feuille')}</label>
          <select id="import-feuille">${lecture.feuilles.map((feuille, rang) => UI.html`<option value="${rang}"${rang === etat.feuille ? UI.brut(' selected') : ''}>${feuille.nom}</option>`)}</select>
        </div>` : ''}
        <div class="champ">
          <label class="libelle" for="import-ligne-entete">${I18n.t('import.lecture.ligne_tete_titres_colonnes')}</label>
          <input type="number" id="import-ligne-entete" min="1" max="${maximum}" step="1" inputmode="numeric" value="${etat.rangEntete + 1}">
          <p class="aide">${I18n.t('import.lecture.ligne_proposee', { numero: etat.rangPropose + 1 })}</p>
        </div>
        <label class="case import-deux-lignes"><input type="checkbox" id="import-deux-lignes"${etat.deuxLignes ? UI.brut(' checked') : ''}>
          <span>${I18n.t('import.lecture.tete_deux_lignes_titres')}</span></label>
      </div>
      <div class="import-resume-lecture"></div>`);
    const feuille = UI.$('#import-feuille', zoneLu);
    if (feuille) {
      feuille.addEventListener('change', () => {
        etat.feuille = Number(feuille.value) || 0;
        etat.rangPropose = Import.ligneEntete(lignesFeuille(), etat.type);
        etat.rangEntete = etat.rangPropose;
        etat.deuxLignes = false;
        oublierCorrespondance();
        afficherLecture();
        UI.$('#import-feuille', racine).focus();
      });
    }
    const ligne = UI.$('#import-ligne-entete', zoneLu);
    const changerLigne = () => {
      const numero = Number(ligne.value);
      const valable = Number.isInteger(numero) && numero >= 1 && numero <= lignes.length;
      ligne.setAttribute('aria-invalid', valable ? 'false' : 'true');
      if (!valable || numero - 1 === etat.rangEntete) return;
      etat.rangEntete = numero - 1;
      oublierCorrespondance();
      afficherResumeLecture();
    };
    ligne.addEventListener('input', changerLigne);
    ligne.addEventListener('change', changerLigne);
    UI.$('#import-deux-lignes', zoneLu).addEventListener('change', (evenement) => {
      etat.deuxLignes = evenement.target.checked;
      oublierCorrespondance();
      afficherResumeLecture();
    });
    afficherResumeLecture();
  }

  // Titres lus, nombre de lignes de données, extrait du haut de la feuille (ligne d'en-tête en évidence).
  function afficherResumeLecture() {
    const zone = racine ? UI.$('.import-resume-lecture', racine) : null;
    if (!zone) return;
    const probleme = problemeEntete();
    afficherErreur(probleme);
    const lignes = lignesFeuille();
    const titres = entetes();
    const remplies = donnees().filter(ligneRemplie).length;
    const premiere = numeroPremiereLigne();
    const finEntete = etat.rangEntete + (etat.deuxLignes ? 1 : 0);
    const extrait = lignes.slice(0, Math.max(EXTRAIT_LIGNES, finEntete + 4));
    const largeur = Math.min(EXTRAIT_COLONNES, Math.max(1, ...extrait.map((l) => l.length)));
    UI.remplir(zone, UI.html`
      <p class="import-titres" id="import-titres"><b>${I18n.t('import.resume_lecture.colonnes', { n: titres.length })}</b>
        ${titres.map((titre, rang) => UI.html`${rang ? ', ' : ''}<span>${I18n.t('import.resume_lecture.titre', { titre: titre || I18n.t('import.resume_lecture.sans_titre') })}</span>`)}</p>
      ${probleme ? '' : UI.html`<p class="note">${I18n.t('import.resume_lecture.lignes_donnees', { n: remplies, premiere })}</p>`}
      <div class="table-defile import-extrait" tabindex="0" role="region" aria-label="${I18n.t('import.resume_lecture.debut_fichier')}">
        <table class="table">
          <caption class="visuellement-cache">${I18n.t('import.resume_lecture.debut_fichier_ligne_tete')}</caption>
          <thead><tr><th scope="col" class="num">${I18n.t('import.resume_lecture.ligne')}</th>${Array.from({ length: largeur }, (_, rang) => UI.html`<th scope="col">${lettreColonne(rang)}</th>`)}</tr></thead>
          <tbody>${extrait.map((cellules, rang) => {
            const classe = rang >= etat.rangEntete && rang <= finEntete ? 'import-ligne-entete' : (rang < etat.rangEntete ? 'import-ligne-ignoree' : '');
            return UI.html`<tr class="${classe}"><td class="num">${rang + 1}</td>${Array.from({ length: largeur }, (_, colonne) => UI.html`<td>${couper(cellules[colonne], 40)}</td>`)}</tr>`;
          })}</tbody>
        </table>
      </div>`);
    majContinuerOu();
  }

  function majContinuerOu() {
    const bouton = boutonContinuer();
    if (bouton && etat.etape === 2) bouton.disabled = !etat.lecture || Boolean(problemeEntete());
  }

  // ===========================================================================================
  // 5. Étape 3 — Colonnes : champ par colonne, statut, IA
  // ===========================================================================================

  function preparerCorrespondance() {
    etat.correspondance = Import.correspondance(etat.type, entetes(), donnees(), 'auto')
      .map((entree) => Object.assign({ origine: '' }, entree));
  }

  function etapeColonnes(zone) {
    if (!etat.correspondance) preparerCorrespondance();
    const element = section(3, I18n.t('import.etape_colonnes.quelles_colonnes_importer'), I18n.t('import.etape_colonnes.prevo_rapproche_chaque_colonne'));
    element.appendChild(UI.element(UI.html`<div class="alertes" id="import-alertes-colonnes"></div>`));
    const zoneIa = UI.element(UI.html`<div class="import-zone-ia" id="import-zone-ia"></div>`);
    if (typeof Ia !== 'undefined' && typeof Ia.emplacement === 'function') {
      zoneIa.appendChild(Ia.emplacement(I18n.t('import.etape_colonnes.proposer_ia'), () => demanderIa(zoneIa)));
    }
    element.appendChild(zoneIa);
    element.appendChild(UI.element(UI.html`<div class="import-cadre-colonnes">
      <table class="table import-colonnes">
        <caption class="visuellement-cache">${I18n.t('import.etape_colonnes.correspondance_colonnes_fichier_champs')}</caption>
        <thead><tr><th scope="col">${I18n.t('import.etape_colonnes.colonne_fichier')}</th><th scope="col">${I18n.t('import.etape_colonnes.exemples')}</th><th scope="col">${I18n.t('import.etape_colonnes.champ_prevo')}</th><th scope="col">${I18n.t('commun.champ.statut')}</th></tr></thead>
        <tbody></tbody>
      </table>
    </div>`));
    element.appendChild(navigation({ retour: 2, continuer: { action: validerColonnes } }));
    zone.appendChild(element);
    UI.$('.import-colonnes tbody', element).addEventListener('change', (evenement) => {
      const choix = evenement.target.closest('select.import-champ');
      if (choix) choisirChamp(Number(choix.dataset.colonne), choix.value);
    });
    rendreColonnes();
  }

  function exemples(colonne) {
    const trouves = [];
    for (const cellules of donnees()) {
      const valeur = texte((cellules || [])[colonne]);
      if (valeur) trouves.push(couper(valeur, 60));
      if (trouves.length === 3) break;
    }
    return trouves;
  }

  function ligneColonne(entree) {
    const statut = STATUTS[entree.statut] || STATUTS.non_utilisee;
    const titre = nomColonne(entree);
    const valeurs = exemples(entree.colonne);
    return UI.html`<tr data-colonne="${entree.colonne}" class="import-${entree.statut}">
      <td data-titre="${I18n.t('import.etape_colonnes.colonne_fichier')}">${I18n.html('import.ligne_colonne.entete_lettre', { entete: entree.entete || I18n.t('import.resume_lecture.sans_titre'),
        lettre: lettreColonne(entree.colonne) })}</td>
      <td data-titre="${I18n.t('import.etape_colonnes.exemples')}">${valeurs.length ? UI.html`<ul class="import-exemples">${valeurs.map((v) => UI.html`<li>${v}</li>`)}</ul>`
        : UI.html`<span class="import-sans-exemple">${I18n.t('import.ligne_colonne.colonne_vide')}</span>`}</td>
      <td data-titre="${I18n.t('import.etape_colonnes.champ_prevo')}"><select class="import-champ" data-colonne="${entree.colonne}" aria-label="${I18n.t('import.ligne_colonne.champ_prevo', { titre })}">
        <option value="">${I18n.t('import.ligne_colonne.pas_importer')}</option>
        ${description().champs.map((champ) => UI.html`<option value="${champ.cle}"${champ.cle === entree.champ ? UI.brut(' selected') : ''}>${libelleChamp(champ)}</option>`)}
      </select></td>
      <td data-titre="${I18n.t('commun.champ.statut')}"><span class="badge ${statut.ton} import-statut">${statut.libelle}</span>
        ${entree.raison ? UI.html`<small class="import-raison">${entree.raison}</small>` : ''}</td>
    </tr>`;
  }

  function rendreColonnes(colonneAFocaliser) {
    const corps = racine ? UI.$('.import-colonnes tbody', racine) : null;
    if (!corps) return;
    UI.remplir(corps, UI.html`${etat.correspondance.map(ligneColonne)}`);
    afficherAlertesColonnes(false);
    if (colonneAFocaliser !== undefined) {
      const choix = UI.$('select.import-champ[data-colonne="' + colonneAFocaliser + '"]', corps);
      if (choix) choix.focus();
    }
  }

  function afficherAlertesColonnes(insister) {
    const zone = racine ? UI.$('#import-alertes-colonnes', racine) : null;
    if (!zone) return;
    zone.textContent = '';
    const utilisees = etat.correspondance.filter((e) => e.champ && e.statut !== 'non_utilisee');
    if (!utilisees.length) {
      zone.appendChild(UI.bandeau(insister ? 'important' : 'attention', I18n.t('import.alertes_colonnes.aucune_colonne_importee_choisissez')));
      return;
    }
    const pris = new Set(utilisees.map((e) => e.champ));
    const manquants = description().champs.filter((champ) => obligatoire(champ) && !pris.has(champ.cle));
    if (manquants.length) {
      zone.appendChild(UI.bandeau('attention', I18n.html('import.alertes_colonnes.sans_colonne', { n: manquants.length, champs: manquants.map((c) => c.libelle).join(', ') })));
    }
    const aConfirmer = etat.correspondance.filter((e) => e.statut === 'a_confirmer' && e.champ).length;
    if (aConfirmer) {
      zone.appendChild(UI.bandeau('info', I18n.html('import.alertes_colonnes.a_confirmer', { n: aConfirmer })));
    }
  }

  /** Champ choisi à la main : un champ ne sert qu'à une colonne (l'autre colonne le rend). */
  function choisirChamp(colonne, champ) {
    const entree = etat.correspondance.find((e) => e.colonne === colonne);
    if (!entree) return;
    if (champ) {
      etat.correspondance.forEach((autre) => {
        if (autre !== entree && autre.champ === champ) {
          Object.assign(autre, { champ: '', statut: 'non_utilisee', raison: I18n.t('import.choisir_champ.champ_repris_colonne', { nomColonne: nomColonne(entree) }), origine: '' });
        }
      });
    }
    Object.assign(entree, champ ? { champ, statut: 'sure', raison: I18n.t('import.choisir_champ.choisi_main'), origine: '' }
      : { champ: '', statut: 'non_utilisee', raison: I18n.t('import.choisir_champ.ecartee_main'), origine: '' });
    oublierApercu();
    rendreColonnes(colonne);
  }

  function validerColonnes() {
    const utilisees = etat.correspondance.filter((e) => e.champ && e.statut !== 'non_utilisee');
    if (!utilisees.length) {
      afficherAlertesColonnes(true);
      return;
    }
    Import.memoriserCorrespondance(etat.type, entetes(), etat.correspondance);
    if (!etat.apercu) {
      const calcul = assistant.calculerApercu();
      if (!calcul.ok) {
        const zone = UI.$('#import-alertes-colonnes', racine);
        zone.textContent = '';
        zone.appendChild(UI.bandeau('important', calcul.message));
        return;
      }
    }
    allerA(4);
  }

  // --- IA (D87 a) : titres des colonnes non reconnues seulement, jamais une cellule ------------------

  function demanderIa(apres) {
    const candidates = etat.correspondance.filter((e) => e.statut !== 'sure' && e.entete);
    if (!candidates.length) {
      UI.toast(I18n.t('import.demander_ia.toutes_colonnes_sont_reconnues'), 'info');
      return;
    }
    const titres = Array.from(new Set(candidates.map((e) => e.entete))).slice(0, TITRES_IA_MAX);
    // Champs encore libres : ceux des colonnes « sûres » ne sont pas proposés.
    const pris = new Set(etat.correspondance.filter((e) => e.statut === 'sure' && e.champ).map((e) => e.champ));
    const champs = description().champs.filter((champ) => !pris.has(champ.cle)).map((champ) => ({ cle: champ.cle, libelle: champ.libelle }));
    Ia.ouvrirEncadre({
      apres, fonction: 'colonnesImport', donnees: { type: description().libelle, champs, colonnes: titres },
      rendu: (resultat) => renduIa(resultat),
      boutons: [{ libelle: I18n.t('import.demander_ia.appliquer_confirmer'), valeur: 'appliquer', classe: 'btn-primaire',
        action: (resultat, reponse) => appliquerIa(resultat, reponse.modele) }],
    });
  }

  function renduIa(resultat) {
    const libelle = (cle) => (Import.interne.champDe(description(), cle) || { libelle: cle }).libelle;
    return UI.html`<p class="note">${I18n.t('import.rendu_ia.seuls_titres_colonnes_non')}</p>
      ${resultat.colonnes.length
        ? UI.html`<ul class="ia-liste">${resultat.colonnes.map((c) => UI.html`<li>${I18n.html('import.rendu_ia.entete_libelle', { entete: c.entete, libelle: libelle(c.champ) })}</li>`)}</ul>`
        : UI.html`<p>${I18n.t('import.rendu_ia.ia_rapproche_aucune_colonnes')}</p>`}
      ${resultat.rejetes.length ? UI.html`<p class="note">${I18n.t('import.rendu_ia.propositions_ecartees', { n: resultat.rejetes.length })}</p>` : ''}`;
  }

  function appliquerIa(resultat, modele) {
    const vues = new Set();
    let appliquees = 0;
    resultat.colonnes.forEach(({ entete, champ }) => {
      const entree = etat.correspondance.find((e) => e.statut !== 'sure' && e.entete === entete && !vues.has(e));
      if (!entree) return;
      vues.add(entree);
      if (etat.correspondance.some((e) => e !== entree && e.statut === 'sure' && e.champ === champ)) return;
      etat.correspondance.forEach((autre) => {
        if (autre !== entree && autre.champ === champ) {
          Object.assign(autre, { champ: '', statut: 'non_utilisee', raison: I18n.t('import.appliquer_ia.champ_propose_ia', { entete }), origine: '' });
        }
      });
      Object.assign(entree, { champ, statut: 'a_confirmer', raison: I18n.t('import.appliquer_ia.proposee_ia_confirmer', { modele }), origine: 'ia' });
      appliquees += 1;
    });
    if (appliquees) {
      etat.modeleIa = modele;
      oublierApercu();
    }
    rendreColonnes();
    UI.toast(appliquees ? I18n.t('import.appliquer_ia.colonnes_proposees', { n: appliquees })
      : I18n.t('import.appliquer_ia.aucune_proposition_ia_appliquer'), appliquees ? 'succes' : 'info');
    return true;
  }

  // ===========================================================================================
  // 6. Enregistrement de l'écran
  // ===========================================================================================

  const assistant = {
    etat: () => etat, allerA, recommencer, section, navigation, entetes, donnees, numeroPremiereLigne, correspondanceValidee,
    colonnesIa, etapes: { 1: etapeQuoi, 2: etapeOu, 3: etapeColonnes }, calculerApercu: null,
  };

  // App est chargé après les modules : l'écran est enregistré une fois la page lue.
  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'import',
      route: /^#\/import$/,
      get titre() { return I18n.t('import.ecran.titre'); },
      parent: 'parametres',
      profils: ['responsable'],
      tables: [],
      afficher,
    });
  });

  return { assistant };
})());
