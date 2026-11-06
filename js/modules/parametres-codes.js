'use strict';
// Parametres (2/4) — carte « Codes de défaillance » de l'écran Paramètres (ARCHITECTURE.md §15.11 ;
// brief §6 « codes_defaillance », §9 E12) : liste par famille (symptôme, cause, remède), ajout d'un
// code, modification d'un libellé. Ni désactivation ni suppression : la table n'a pas de champ
// « actif » et les OT anciens citent leurs codes (corriger un libellé suffit).
// Les listes de codes de la fiche OT et des demandes lisent la même table : un code ajouté y apparaît.
// La carte est affichée par parametres.js (fonction relais afficherCodes). Complète l'objet Parametres.

Object.assign(Parametres, (() => {

  // Familles, dans l'ordre d'affichage : lettre du code proposé (S01, C03, R02…) et titre.
  const FAMILLES = [
    { famille: 'symptôme', lettre: 'S', get titre() { return I18n.t('parametres.titre.symptomes'); } },
    { famille: 'cause', lettre: 'C', get titre() { return I18n.t('parametres.titre.causes'); } },
    { famille: 'remède', lettre: 'R', get titre() { return I18n.t('parametres.titre.remedes'); } },
  ];
  const NUMERO_AUTRE = 99;                    // S99, C99 : « Autre » par convention, jamais proposé
  const MOTIF_CODE = /^[A-Z0-9][A-Z0-9_-]{0,11}$/;
  let familleChoisie = 'cause';               // famille du formulaire d'ajout, gardée d'un affichage à l'autre

  // ===========================================================================================
  // 6. Règles : code proposé, contrôle d'un code
  // ===========================================================================================

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  /** Code au format du fichier : sans espaces de bord, en majuscules (« c15 » → « C15 »). */
  function codeNormalise(valeur) {
    return texte(valeur).toUpperCase();
  }

  function definitionFamille(famille) {
    return FAMILLES.find((definition) => definition.famille === famille) || null;
  }

  /**
   * Code proposé pour une famille : sa lettre + le numéro qui suit le plus grand déjà pris (hors
   * 99, « Autre »), sur 2 chiffres (C14 → C15) ; si on arrive à 99, le premier numéro libre.
   * `lignes` : lignes de codes_defaillance (par défaut celles en mémoire). '' si famille inconnue.
   */
  function codePropose(famille, lignes) {
    const definition = definitionFamille(famille);
    if (!definition) return '';
    const codes = lignes || Donnees.lignes('codes_defaillance');
    const pris = new Set(codes.map((ligne) => codeNormalise(ligne.code)));
    const numeros = codes.filter((ligne) => ligne.famille === famille)
      .map((ligne) => /^[A-Z]+(\d+)$/.exec(codeNormalise(ligne.code))).filter(Boolean)
      .map((lu) => Number(lu[1])).filter((numero) => numero < NUMERO_AUTRE);
    const code = (numero) => definition.lettre + String(numero).padStart(2, '0');
    const candidats = [];
    for (let numero = (numeros.length ? Math.max(...numeros) : 0) + 1; numero < NUMERO_AUTRE; numero += 1) candidats.push(numero);
    for (let numero = 1; numero < NUMERO_AUTRE; numero += 1) candidats.push(numero);
    const libre = candidats.find((numero) => !pris.has(code(numero)));
    if (libre !== undefined) return code(libre);
    let numero = NUMERO_AUTRE + 1;
    while (pris.has(code(numero))) numero += 1;
    return code(numero);
  }

  /**
   * Contrôle un code : [{ nom, message }]. Famille connue ; code en majuscules et chiffres, unique
   * dans toute la table ; libellé obligatoire et unique dans sa famille (casse et accents ignorés).
   * idCourant : '' pour un ajout (le code n'est alors pas modifiable ensuite).
   */
  function verifierCode(valeurs, lignes, idCourant) {
    const erreurs = [];
    const famille = definitionFamille(valeurs.famille);
    if (!famille) erreurs.push({ nom: 'famille', message: I18n.t('parametres.verifier_code.choisissez_famille_code_symptome') });
    const code = codeNormalise(valeurs.code);
    if (!MOTIF_CODE.test(code)) {
      erreurs.push({ nom: 'code', message: I18n.t('parametres.verifier_code.code_ecrit_lettres_chiffres') });
    } else {
      const double = lignes.find((ligne) => ligne.id !== idCourant && codeNormalise(ligne.code) === code);
      if (double) erreurs.push({ nom: 'code', message: I18n.t('parametres.verifier_code.code_existe_deja', { code, famille: Schema.libelleValeur('codes_defaillance', 'famille', double.famille), doubleLibelle: double.libelle }) });
    }
    const libelle = texte(valeurs.libelle);
    if (!libelle) erreurs.push({ nom: 'libelle', message: I18n.t('parametres.verifier_code.libelle_obligatoire_ex_joint') });
    else if (famille) {
      const double = lignes.find((ligne) => ligne.id !== idCourant && ligne.famille === famille.famille
        && UI.normaliserRecherche(ligne.libelle) === UI.normaliserRecherche(libelle));
      if (double) erreurs.push({ nom: 'libelle', message: I18n.t('parametres.verifier_code.libelle_existe_deja_famille', { famille: Schema.libelleValeur('codes_defaillance', 'famille', famille.famille), doubleCode: double.code }) });
    }
    return erreurs;
  }

  function refuserSiErreurs(erreurs) {
    if (erreurs.length) throw new Donnees.ErreurValidation(erreurs.map((erreur) => erreur.message).join(' '));
  }

  // ===========================================================================================
  // 7. Écritures (Donnees.modifier, contrôles sur les lignes fraîches)
  // ===========================================================================================

  /**
   * Ajoute un code { famille, libelle, code } ; code vide → code proposé (calculé sur les lignes
   * fraîches). Renvoie l'identifiant créé (CD-…).
   */
  async function ajouterCode(valeurs) {
    const saisie = { famille: texte(valeurs && valeurs.famille), libelle: texte(valeurs && valeurs.libelle), code: codeNormalise(valeurs && valeurs.code) };
    let action = 'ajout d\'un code de défaillance';
    return Donnees.modifier('codes_defaillance', (lignes, outils) => {
      const code = saisie.code || codePropose(saisie.famille, lignes);
      refuserSiErreurs(verifierCode(Object.assign({}, saisie, { code }), lignes, ''));
      const id = outils.nouvelId(lignes);
      lignes.push({ id, famille: saisie.famille, code, libelle: saisie.libelle });
      action = 'code ' + code + ' (' + saisie.famille + ') : ' + saisie.libelle;
      return id;
    }, { get action() { return action; } });          // lu par Donnees.modifier après la mutation
  }

  /** Modifie le libellé d'un code (le code et la famille ne changent pas). Renvoie vrai si changé. */
  async function modifierLibelleCode(id, libelle) {
    const nouveau = texte(libelle);
    return Donnees.modifier('codes_defaillance', (lignes) => {
      const ligne = lignes.find((l) => l.id === id);
      if (!ligne) throw new Donnees.ErreurValidation(I18n.t('parametres.modifier_libelle_code.code_introuvable', { id }));
      const erreurs = verifierCode(Object.assign({}, ligne, { libelle: nouveau }), lignes, id).filter((erreur) => erreur.nom === 'libelle');
      refuserSiErreurs(erreurs);
      if (texte(ligne.libelle) === nouveau) return false;
      ligne.libelle = nouveau;
      return true;
    }, { action: 'libellé du code modifié : ' + nouveau });
  }

  // ===========================================================================================
  // 8. Carte « Codes de défaillance »
  // ===========================================================================================

  function codesDeLaFamille(famille) {
    return Donnees.lignes('codes_defaillance').filter((ligne) => ligne.famille === famille)
      .sort((a, b) => texte(a.code).localeCompare(texte(b.code), 'fr', { numeric: true }));
  }

  function listeFamilles() {
    return FAMILLES.map((definition) => {
      const codes = codesDeLaFamille(definition.famille);
      return UI.html`<section class="c4 codes-famille" aria-label="${definition.titre}">
        <h3>${definition.titre} <span class="badge">${codes.length}</span></h3>
        ${codes.length ? UI.html`<ul class="codes-liste">${codes.map((ligne) => UI.html`<li data-code="${ligne.id}">
          <b class="codes-code">${ligne.code}</b><span class="codes-libelle">${ligne.libelle}</span>
          <button type="button" class="btn btn-fantome codes-modifier" data-code-modifier="${ligne.id}"
            aria-label="${I18n.t('parametres.liste_familles.modifier_libelle_code', { ligneCode: ligne.code })}">${I18n.t('commun.bouton.modifier')}</button></li>`)}</ul>`
          : UI.html`<p class="muted">${I18n.t('parametres.liste_familles.aucun_code_famille')}</p>`}
      </section>`;
    });
  }

  function formulaireAjout() {
    const formulaire = UI.element(UI.html`<form id="form-code" class="form-grille codes-ajout" novalidate></form>`);
    formulaire.appendChild(UI.champ(Schema.champ('codes_defaillance', 'famille'), familleChoisie));
    formulaire.appendChild(UI.champ(Schema.champ('codes_defaillance', 'code'), codePropose(familleChoisie),
      { aide: I18n.t('parametres.formulaire_ajout.propose_lettre_famille_numero'), attributs: { maxlength: '12', autocomplete: 'off' } }));
    const libelle = UI.champ(Schema.champ('codes_defaillance', 'libelle'), '', { placeholder: I18n.t('parametres.formulaire_ajout.ex_joint_couvercle_use'), attributs: { maxlength: '80' } });
    libelle.classList.add('large');
    formulaire.appendChild(libelle);
    formulaire.appendChild(UI.element(UI.html`<div class="actions"><span class="espace"></span>
      <button type="submit" class="btn btn-primaire">${UI.icone('ajouter')}${I18n.t('parametres.formulaire_ajout.ajouter_code')}</button></div>`));
    UI.$('[name=famille]', formulaire).addEventListener('change', (evenement) => {
      familleChoisie = evenement.target.value;
      UI.$('[name=code]', formulaire).value = codePropose(familleChoisie);
    });
    formulaire.addEventListener('submit', (evenement) => { evenement.preventDefault(); enregistrerAjout(formulaire); });
    return formulaire;
  }

  function afficherErreurs(formulaire, erreurs) {
    UI.$$('.champ', formulaire).forEach((champ) => UI.erreurChamp(formulaire, champ.dataset.champ, ''));
    erreurs.forEach((erreur) => UI.erreurChamp(formulaire, erreur.nom, erreur.message));
    const premier = UI.$('[aria-invalid="true"]', formulaire);
    if (premier) premier.focus();
  }

  async function enregistrerAjout(formulaire) {
    const bouton = UI.$('button[type=submit]', formulaire);
    if (bouton.disabled) return;
    const valeurs = UI.lireFormulaire(formulaire);
    const erreurs = UI.verifierFormulaire(formulaire);
    verifierCode(valeurs, Donnees.lignes('codes_defaillance'), '').filter((erreur) => !erreurs.some((e) => e.nom === erreur.nom))
      .forEach((erreur) => erreurs.push(erreur));
    afficherErreurs(formulaire, erreurs);
    if (erreurs.length) return;
    bouton.disabled = true;
    try {
      await ajouterCode(valeurs);
      App.marquerSaisie(false);
      UI.toast(I18n.t('parametres.enregistrer_ajout.code_ajoute', { codeNormalise: codeNormalise(valeurs.code), valeursLibelle: texte(valeurs.libelle) }), 'succes');
      remplirCarte(formulaire.closest('#zone-codes'));
    } catch (erreur) {
      App.signalerErreur(erreur, 'ajout d\'un code de défaillance');
    } finally {
      bouton.disabled = false;
    }
  }

  async function ouvrirModification(ligne, zone) {
    const champ = UI.champ(Schema.champ('codes_defaillance', 'libelle'), ligne.libelle, { attributs: { maxlength: '80' } });
    const contenu = UI.element(UI.html`<div class="form-colonne"><p>${I18n.html('parametres.ouvrir_modification.code_ot_citent_afficheront', { ligneCode: ligne.code, famille: Schema.libelleValeur('codes_defaillance', 'famille', ligne.famille) })}</p></div>`);
    contenu.appendChild(champ);
    let fait = false;
    let fermer = null;
    const valider = async () => {
      const libelle = texte(UI.$('[name=libelle]', contenu).value);
      const erreurs = UI.verifierFormulaire(contenu)
        .concat(verifierCode(Object.assign({}, ligne, { libelle }), Donnees.lignes('codes_defaillance'), ligne.id).filter((e) => e.nom === 'libelle'));
      afficherErreurs(contenu, erreurs);
      if (erreurs.length) return;
      try {
        await modifierLibelleCode(ligne.id, libelle);
        fait = true;
        fermer('ok');
      } catch (erreur) {
        if (erreur instanceof Donnees.ErreurValidation) afficherErreurs(contenu, [{ nom: 'libelle', message: erreur.message }]);
        else App.signalerErreur(erreur, 'modification du libellé');
      }
    };
    const choix = await UI.fenetre({
      titre: I18n.t('parametres.ouvrir_modification.modifier_libelle'), contenu,
      boutons: [{ libelle: I18n.t('commun.bouton.annuler'), valeur: null, classe: 'btn-fantome' }, { libelle: I18n.t('commun.bouton.enregistrer'), valeur: 'ok', classe: 'btn-primaire', defaut: true }],
      surOuverture(dialogue, fermerFenetre) { fermer = fermerFenetre; },
      avantFermeture(valeur) {
        if (valeur !== 'ok' || fait) return true;
        valider();                                     // la fenêtre se ferme toute seule si tout va bien
        return false;
      },
    });
    if (choix !== 'ok') return;
    UI.toast(I18n.t('parametres.ouvrir_modification.libelle_modifie'), 'succes');
    remplirCarte(zone);
  }

  /** Remplit (ou réaffiche) la carte dans sa zone de l'écran Paramètres. */
  function remplirCarte(zone) {
    if (!zone) return;
    UI.remplir(zone, UI.html`<article class="carte" id="carte-codes">
      <div class="entete-carte"><h2>${I18n.html('parametres.remplir_carte.codes_defaillance', { nombre: Donnees.lignes('codes_defaillance').length })}</h2></div>
      <p class="note codes-explication">${I18n.t('parametres.remplir_carte.listes_alimentent_demandes_compte')}</p>
      <div class="codes-zone-ajout"></div>
      <div class="grille codes-familles">${listeFamilles()}</div>
    </article>`);
    UI.$('.codes-zone-ajout', zone).appendChild(formulaireAjout());
    UI.$$('[data-code-modifier]', zone).forEach((bouton) => bouton.addEventListener('click', () => {
      const ligne = Donnees.trouver('codes_defaillance', bouton.dataset.codeModifier);
      if (ligne) ouvrirModification(ligne, zone);
    }));
  }

  // Relais appelé par l'écran Paramètres (parametres.js).
  Object.assign(Parametres.interne, { afficherCodes: remplirCarte });

  return {
    // codes de défaillance (ARCHITECTURE.md §15.11)
    FAMILLES_CODES: FAMILLES.map((definition) => definition.famille),
    codePropose, verifierCode, ajouterCode, modifierLibelleCode,
  };
})());
