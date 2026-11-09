'use strict';
// Parc (3/5) — formulaires : fenêtre de création et de modification d'une localisation (ouverte
// depuis le parc), écrans #/equipement/nouveau et #/equipement/<id>/modifier (responsable),
// fenêtre « Saisir un relevé » d'un compteur (technicien et responsable, ouverte depuis la fiche)
// (ARCHITECTURE.md §8, §10, §14.2 et §14.6). Complète l'objet Parc.

Object.assign(Parc, (() => {

  // Règles et outils de parc-regles.js.
  const { cheminLocalisation, libelleEquipement, verifierEquipement, verifierLocalisation } = Parc;
  const { comparerLibelles, parRepere, identifiantsDescendants, dernierReleveDe, verifierReleve,
    estEnBaisse } = Parc.interne;

  const TAILLE_MAX_DOCUMENT = 9 * 1024 * 1024;        // le serveur refuse plus de 10 Mo
  // Les mêmes que TYPES_DOCUMENTS de serveur.py (audit F4 : « .doc » et « .xls » ne sont plus acceptés), sans « html ».
  const EXTENSIONS_DOCUMENT = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'pdf', 'txt', 'csv', 'docx', 'xlsx', 'odt', 'ods'];
  const TYPE_ENFANT = { site: 'atelier', atelier: 'ligne', ligne: 'ligne' };

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
    if (idExistant && !existante) { UI.toast(I18n.t('parc.ouvrir_fenetre_localisation.localisation_existe_plus'), 'attention'); return; }
    const champsSchema = Schema.table('localisations').champs;
    const definition = (nom) => champsSchema.find((c) => c.nom === nom);
    const exclus = existante ? identifiantsDescendants('localisations', existante.id) : new Set();
    if (existante) exclus.add(existante.id);
    const parents = Donnees.lignes('localisations').filter((l) => !exclus.has(l.id))
      .map((l) => ({ valeur: l.id, libelle: cheminLocalisation(l.id) }))
      .sort((a, b) => comparerLibelles(a.libelle, b.libelle));

    const contenu = UI.element(UI.html`<div class="form-colonne parc-formulaire-localisation"></div>`);
    contenu.appendChild(UI.champ(definition('libelle'), existante ? existante.libelle : '', { attributs: { maxlength: '80' } }));
    const blocParent = UI.champ(definition('parent_id'), existante ? existante.parent_id : '', {
      liste: parents, aide: I18n.t('parc.ouvrir_fenetre_localisation.laissez_vide_site_atelier'),
    });
    contenu.appendChild(blocParent);
    const blocType = UI.champ(definition('type'), existante ? existante.type : 'atelier');
    contenu.appendChild(blocType);
    contenu.appendChild(UI.element(UI.html`<p class="mention-requis"><span class="requis" aria-hidden="true">*</span>${I18n.t('commun.message.champ_obligatoire')}</p>`));

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
            if (!ligne) throw new Donnees.ErreurValidation(I18n.t('parc.ouvrir_fenetre_localisation.localisation_existe_plus'));
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
      titre: existante ? I18n.t('parc.ouvrir_fenetre_localisation.modifier_localisation') : I18n.t('parc.ouvrir_fenetre_localisation.nouvelle_localisation'),
      contenu,
      boutons: [
        { libelle: I18n.t('commun.bouton.annuler'), valeur: null, classe: 'btn-fantome' },
        { libelle: I18n.t('commun.bouton.enregistrer'), valeur: 'ok', classe: 'btn-primaire', defaut: true },
      ],
      surOuverture(dialogue, fermer) { fermerFenetre = fermer; },
      avantFermeture(valeur) {
        if (valeur !== 'ok' || enregistre) return true;
        enregistrer();                                  // la fenêtre se ferme toute seule si tout va bien
        return false;
      },
    });
    if (choix === 'ok') {
      UI.toast(existante ? I18n.t('parc.ouvrir_fenetre_localisation.localisation_modifiee') : I18n.t('parc.ouvrir_fenetre_localisation.localisation_creee'), 'succes');
      await App.reafficher();
    }
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
      UI.remplir(conteneur, UI.html`<div class="parc"><div class="entete-page"><div><div class="fil"><a href="#/parc">${I18n.t('parc.formulaire.parc')}</a></div><h1>${I18n.t('parc.formulaire.equipement_introuvable')}</h1></div></div>
        ${UI.vide(I18n.t('parc.formulaire.equipement_introuvable'), I18n.t('parc.formulaire.aucun_equipement_porte_identifiant', { idCourant }), 'recherche')}</div>`);
      return;
    }
    App.definirTitre(existant ? I18n.t('parc.formulaire.modifier_v1', { repere: (existant.repere || existant.id) }) : I18n.t('parc.formulaire.nouvel_equipement'));
    const champsSchema = Schema.table('equipements').champs;
    const definition = (nom) => champsSchema.find((c) => c.nom === nom);
    const valeur = (nom) => (existant ? existant[nom] : undefined);

    // Listes déroulantes : localisations (avec leur chemin) et équipements parents possibles.
    const listeLocalisations = Donnees.lignes('localisations')
      .map((l) => ({ valeur: l.id, libelle: cheminLocalisation(l.id) }))
      .sort((a, b) => comparerLibelles(a.libelle, b.libelle));
    const interdits = existant ? identifiantsDescendants('equipements', existant.id) : new Set();
    if (existant) interdits.add(existant.id);
    const listeParents = Donnees.lignes('equipements').filter((e) => !interdits.has(e.id))
      .sort(parRepere).map((e) => ({ valeur: e.id, libelle: libelleEquipement(e.id) }));

    const retour = existant ? '#/equipement/' + encodeURIComponent(existant.id) : '#/parc';
    UI.remplir(conteneur, UI.html`
      <div class="parc">
        <div class="entete-page"><div>
          <div class="fil"><a href="#/parc">${I18n.t('parc.formulaire.parc')}</a> <span aria-hidden="true">›</span>
            ${existant ? UI.html`<a href="${retour}">${existant.repere || existant.id}</a>` : UI.html`<span>${I18n.t('parc.formulaire.nouvel_equipement')}</span>`}</div>
          <h1>${existant ? I18n.t('parc.formulaire.modifier_libelle_equipement', { libelleEquipement: libelleEquipement(existant.id) }) : I18n.t('parc.formulaire.nouvel_equipement')}</h1>
        </div></div>
        <article class="carte"><form class="form-grille" id="parc-formulaire" novalidate></form></article>
      </div>`);
    const formulaire = UI.$('#parc-formulaire', conteneur);
    const ajouter = (bloc, large) => { if (large) bloc.classList.add('large'); formulaire.appendChild(bloc); return bloc; };

    ajouter(UI.champ(definition('repere'), valeur('repere'), {
      aide: I18n.t('parc.formulaire.code_court_unique_parmi'), attributs: { maxlength: '40' },
    }));
    ajouter(UI.champ(definition('designation'), valeur('designation'), { attributs: { maxlength: '120' } }));
    ajouter(UI.champ(definition('localisation_id'), valeur('localisation_id'), { liste: listeLocalisations }));
    ajouter(UI.champ(definition('parent_id'), valeur('parent_id'), {
      liste: listeParents, aide: I18n.t('parc.formulaire.remplir_sous_ensemble_ex'),
    }));
    ajouter(UI.champ(definition('marque'), valeur('marque')));
    ajouter(UI.champ(definition('modele'), valeur('modele')));
    ajouter(UI.champ(definition('num_serie'), valeur('num_serie')));
    ajouter(UI.champ(definition('date_mes'), valeur('date_mes')));
    ajouter(UI.champ(definition('criticite'), valeur('criticite'), {
      aide: I18n.t('parc.formulaire.arret_bloque_production_securite'),
    }));
    ajouter(UI.champ(definition('statut'), valeur('statut')));
    ajouter(UI.champ(definition('heures_fonct_jour'), valeur('heures_fonct_jour'), { aide: I18n.t('parc.formulaire.utilise_estimer_usage_entre') }));
    ajouter(UI.champ(definition('valeur_remplacement'), valeur('valeur_remplacement'), {
      aide: I18n.t('parc.formulaire.prix_equipement_neuf_equivalent'),
    }));
    // Coût d'une heure d'arrêt (D188, CS174), dans la devise réglée (libellé du schéma) ; jamais de valeur par défaut.
    ajouter(UI.champ(definition('cout_arret_h'), valeur('cout_arret_h'), {
      aide: I18n.t('parc.formulaire.production_perdue_penalites_heures'),
    }));
    ajouter(UI.champ(definition('habilitation_requise'), valeur('habilitation_requise'), {
      aide: I18n.t('parc.formulaire.ex_br_plusieurs_habilitations'),
    }));
    ajouter(UI.champ(definition('consignation'), valeur('consignation'), {
      aide: I18n.t('parc.formulaire.etape_ligne_texte_affiche'),
    }), true);

    const idFichier = UI.identifiantUnique('parc-document');
    const blocDocument = ajouter(UI.element(UI.html`<div class="champ" data-champ="document_fichier">
      <label class="libelle" for="${idFichier}">${I18n.t('parc.formulaire.document_fiche_technique_notice')}</label>
      <input type="file" id="${idFichier}" accept=".${EXTENSIONS_DOCUMENT.join(',.')}" aria-describedby="${idFichier}-aide ${idFichier}-erreur">
      <p class="aide" id="${idFichier}-aide">${existant && existant.document
        ? I18n.t('parc.formulaire.document_actuel_choisir_fichier', { document: existant.document }) : I18n.t('parc.formulaire.pdf_image_tableur_9')}</p>
      <p class="erreur-champ" id="${idFichier}-erreur" role="alert" hidden></p>
    </div>`), true);
    formulaire.appendChild(UI.element(UI.html`<p class="mention-requis large"><span class="requis" aria-hidden="true">*</span>${I18n.t('commun.message.champ_obligatoire')}</p>`)).classList.add('large');
    formulaire.appendChild(UI.element(UI.html`<div class="actions">
      <button type="submit" class="btn btn-primaire">${UI.icone('valider')}${I18n.t('commun.bouton.enregistrer')}</button>
      <a class="btn btn-fantome" href="${retour}">${I18n.t('commun.bouton.annuler')}</a>
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
        if (!EXTENSIONS_DOCUMENT.includes(extensionDe(fichier.name))) messageFichier = I18n.t('parc.formulaire.type_fichier_pas_accepte');
        else if (fichier.size > TAILLE_MAX_DOCUMENT) messageFichier = I18n.t('commun.message.fichier_trop_volumineux');
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
            if (!ligne) throw new Donnees.ErreurValidation(I18n.t('parc.formulaire.equipement_existe_plus'));
            Object.assign(ligne, valeurs);
            return ligne.id;
          }
          const nouvelId = outils.nouvelId(lignes);
          lignes.push(Object.assign({ id: nouvelId, actif: '1' }, valeurs));
          return nouvelId;
        }, { action: existant ? 'modification de l\'équipement' : 'création de l\'équipement' });
        App.marquerSaisie(false);
        UI.toast(existant ? I18n.t('parc.formulaire.equipement_enregistre') : I18n.t('parc.formulaire.equipement_cree'), 'succes');
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
  // 8. Relevé de compteur : fenêtre de saisie et écriture (technicien et responsable)
  // ===========================================================================================

  /** « 15 855 h », « 0,58 bar » : nombre à la française suivi de l'unité du compteur. */
  function valeurAvecUnite(valeur, unite) {
    return UI.nombreFr(valeur) + (unite ? ' ' + unite : '');
  }

  /** Nom inscrit dans le relevé : celui du technicien (ou du demandeur), sinon « Responsable » (langue de l'installation, D156). */
  function utilisateurCourant() {
    const profil = App.profil;
    if (!profil) return '';
    if (profil.type === 'responsable') return I18n.donnees('parc.utilisateur_courant.responsable');
    return String(profil.nom || profil.technicienId || '').trim();
  }

  /** Valeur d'un champ d'une ligne, en texte sans espaces de bord ('' si absente). */
  function champ(ligne, nom) {
    const valeur = ligne[nom];
    return valeur === undefined || valeur === null ? '' : String(valeur).trim();
  }

  /**
   * Écrit un relevé dans releves.csv. Renvoie { id, remiseAZero } : remiseAZero vaut
   * { precedent, valeur } (nombres : dernier relevé avant la baisse, valeur saisie) si le relevé
   * est une baisse confirmée qui devient le dernier relevé du compteur (compteur remplacé ou remis
   * à zéro), null sinon (relevé ordinaire, ou relevé plus bas antidaté).
   *   valeurs : { date: 'AAAA-MM-JJ', valeur: '1234.5' } (point décimal) ;
   *   baisseConfirmee : vrai si l'utilisateur a confirmé une valeur plus basse que le dernier
   *   relevé (compteur remplacé ou remis à zéro).
   * Les contrôles sont refaits sur les lignes fraîches : un relevé plus élevé saisi entre-temps
   * sur un autre poste est vu, et la baisse non confirmée est alors refusée.
   */
  async function enregistrerReleve(compteurId, valeurs, baisseConfirmee) {
    return Donnees.modifier('releves', (lignes, outils) => {
      const compteur = Donnees.trouver('compteurs', compteurId);
      if (!compteur) throw new Donnees.ErreurValidation(I18n.t('parc.enregistrer_releve.compteur_existe_plus'));
      const problemes = verifierReleve(valeurs, outils.aujourdhui());
      if (problemes.length) throw new Donnees.ErreurValidation(problemes.map((p) => p.message).join(' '));
      const dernier = dernierReleveDe(lignes, compteurId);
      const baisse = estEnBaisse(valeurs.valeur, dernier);
      if (!baisseConfirmee && baisse) {
        throw new Donnees.ErreurValidation(I18n.t('parc.enregistrer_releve.valeur_saisie_plus_basse', { valeurAvecUnite: valeurAvecUnite(dernier.valeur, compteur.unite), date: UI.dateFr(dernier.date) }));
      }
      const id = outils.nouvelId(lignes);
      const valeur = Donnees.nombre(valeurs.valeur);
      lignes.push({ id, compteur_id: compteurId, date: valeurs.date, valeur: String(valeur),
        utilisateur: utilisateurCourant() });
      // Même ordre que Preventif (date, puis identifiant) : le relevé saisi est-il devenu le dernier ?
      const devientDernier = (dernierReleveDe(lignes, compteurId) || {}).id === id;
      return { id, remiseAZero: baisse && devientDernier ? { precedent: Donnees.nombre(dernier.valeur), valeur } : null };
    }, { action: 'relevé de compteur' });
  }

  /**
   * Compteur remplacé ou remis à zéro (baisse confirmée) : chaque gamme active « compteur » de ce
   * compteur garde son avancement. Nouvelle base (releve_derniere_realisation) = nouvelle valeur −
   * (dernier relevé avant la baisse − ancienne base, une base vide valant 0). Les gammes « seuil »
   * ne changent pas : leur seuil porte sur la valeur absolue du compteur. Décidé sur les lignes
   * fraîches de gammes (fonction rejouée en cas de conflit) ; une entrée de journal par gamme
   * ajustée (« remise à zéro du compteur CPT-… : base de GAM-… ajustée de A à B »).
   * remiseAZero : { precedent, valeur } (voir enregistrerReleve). Renvoie les gammes ajustées.
   */
  async function ajusterGammesApresRemiseAZero(compteurId, remiseAZero) {
    const ajustees = [];
    await Donnees.modifier('gammes', (lignes) => {
      ajustees.length = 0;
      lignes.forEach((gamme) => {
        if (champ(gamme, 'compteur_id') !== compteurId || champ(gamme, 'declencheur') !== 'compteur'
          || champ(gamme, 'actif') === '0') return;
        const avant = champ(gamme, 'releve_derniere_realisation');
        const avancement = remiseAZero.precedent - (Donnees.nombre(avant) || 0);
        const apres = String(Math.round((remiseAZero.valeur - avancement) * 1e6) / 1e6);
        if (apres === avant) return;
        gamme.releve_derniere_realisation = apres;
        ajustees.push({ id: gamme.id, avant, apres });
      });
    }, { journal: false });                    // journalisé ci-dessous, avec l'ancienne et la nouvelle base
    for (const { id, avant, apres } of ajustees) {
      await Donnees.journaliser('gammes', id, 'modification : releve_derniere_realisation — remise à zéro du compteur '
        + compteurId + ' : base de ' + id + ' ajustée de ' + (avant || 'vide') + ' à ' + apres);
    }
    return ajustees.map((gamme) => gamme.id);
  }

  /**
   * Après un relevé de remise à zéro : ajuste les gammes au compteur. Le relevé est déjà
   * enregistré : un échec ne l'annule pas ; il est rendu sous forme d'avertissement (texte du
   * toast, '' si tout va bien) et tracé en console (console.warn).
   */
  async function apresRemiseAZero(compteurId, remiseAZero) {
    try {
      await ajusterGammesApresRemiseAZero(compteurId, remiseAZero);
      return '';
    } catch (erreur) {
      const message = I18n.t('parc.apres_remise_azero.releve_enregistre_mais_base', { compteurId, raisonErreur: App.raisonErreur(erreur) });
      console.warn('Prévo (parc) : ' + message, erreur);
      return message;
    }
  }

  // Après un relevé, une gamme au compteur ou au seuil peut être devenue échue (RG5) : la
  // génération est idempotente et sûre à plusieurs postes. Le toast dit ce qui a été créé ;
  // `avertissement` (ajustement des gammes impossible) remplace alors le message de succès.
  async function genererApresReleve(avertissement) {
    let crees;
    try {
      crees = await Preventif.genererOTEchus();
    } catch (erreur) {
      App.signalerErreur({ message: (avertissement ? I18n.t('parc.generer_apres_releve.avertissement_plus', { avertissement }) : I18n.t('parc.generer_apres_releve.releve_enregistre_mais')) + ' ' + I18n.t('parc.generer_apres_releve.ot_preventifs_ont_pas', { raisonErreur: App.raisonErreur(erreur) }) },
      'génération du préventif après un relevé');
      return;
    }
    const generation = crees.length ? ' ' + Preventif.texteGeneration(crees.length) + '.' : '';
    if (avertissement) UI.toast(avertissement + generation, 'attention');
    else UI.toast(I18n.t('parc.generer_apres_releve.releve_enregistre', { generation }), 'succes');
  }

  // Rappel du dernier relevé (ligne de releves, ou null) : en tête de la fenêtre et dans
  // l'avertissement de baisse.
  function afficherDernierReleve(contenu, dernier, unite) {
    UI.remplir(UI.$('.parc-releve-precedent', contenu), dernier
      ? UI.html`${I18n.html('parc.dernier_releve.dernier_releve', { valeurAvecUnite: valeurAvecUnite(dernier.valeur, unite), date: UI.dateFr(dernier.date) })}`
      : UI.html`${I18n.t('parc.dernier_releve.aucun_releve_compteur')}`);
    UI.remplir(UI.$('.parc-releve-baisse-valeur', contenu),
      dernier ? UI.html` (${valeurAvecUnite(dernier.valeur, unite)})` : '');
  }

  // Contenu de la fenêtre : rappel du dernier relevé, date, valeur, avertissement de baisse.
  function contenuFenetreReleve(compteur, dernier, jour) {
    const unite = String(compteur.unite || '').trim();
    const champsSchema = Schema.table('releves').champs;
    const definition = (nom) => champsSchema.find((c) => c.nom === nom);
    const contenu = UI.element(UI.html`<div class="form-colonne parc-formulaire-releve">
      <p class="parc-releve-precedent"></p>
    </div>`);
    contenu.appendChild(UI.champ(definition('date'), jour, { libelle: I18n.t('parc.contenu_fenetre_releve.date_releve'), obligatoire: true, attributs: { max: jour } }));
    contenu.appendChild(UI.champ(definition('valeur'), '', {
      libelle: unite ? I18n.t('parc.formulaire.valeur_lue_unite', { unite }) : I18n.t('parc.formulaire.valeur_lue'), obligatoire: true,
      aide: I18n.t('parc.contenu_fenetre_releve.nombre_affiche_compteur_sans'),
    }));
    contenu.appendChild(UI.element(UI.html`<div class="alerte attention parc-releve-baisse" role="alert" hidden>
      ${UI.icone('alerte')}<div class="alerte-texte">
        <p>${I18n.html('parc.contenu_fenetre_releve.valeur_plus_basse_dernier')}</p>
        <label class="case"><input type="checkbox" name="baisse_confirmee" value="1">
          <span>${I18n.t('parc.contenu_fenetre_releve.oui_compteur_ete_remplace')}</span></label>
        <p class="erreur-champ parc-releve-erreur-baisse" hidden></p>
      </div></div>`));
    afficherDernierReleve(contenu, dernier, unite);
    return contenu;
  }

  /**
   * Fenêtre « Saisir un relevé » d'un compteur : date (aujourd'hui par défaut) et valeur. Une valeur
   * plus basse que le dernier relevé affiche un avertissement et demande une confirmation explicite
   * (case à cocher) ; « Annuler » ne change rien. Un refus venu des lignes fraîches (relevé plus
   * élevé saisi sur un autre poste) relit le dernier relevé et affiche l'avertissement sans fermer
   * la fenêtre. Après l'écriture : ajustement des gammes au compteur si le compteur a été remis à
   * zéro, puis génération des OT préventifs échus. Renvoie vrai si un relevé a été enregistré (la
   * fiche se réaffiche alors).
   */
  async function ouvrirFenetreReleve(compteurId) {
    const compteur = Donnees.trouver('compteurs', compteurId);
    if (!compteur) { UI.toast(I18n.t('parc.enregistrer_releve.compteur_existe_plus'), 'attention'); return false; }
    const jour = Donnees.aujourdhui();
    const unite = String(compteur.unite || '').trim();
    let dernier = dernierReleveDe(Donnees.lignes('releves'), compteurId);
    const contenu = contenuFenetreReleve(compteur, dernier, jour);
    const champValeur = UI.$('[name=valeur]', contenu);
    const avertissement = UI.$('.parc-releve-baisse', contenu);
    const caseBaisse = UI.$('[name=baisse_confirmee]', contenu);
    const erreurBaisse = UI.$('.parc-releve-erreur-baisse', contenu);

    // Valeurs saisies au format du fichier (point décimal, sans espaces).
    const lireReleve = () => {
      const valeurs = lireChamps(contenu);
      return { date: valeurs.date, valeur: valeurs.valeur.replace(/[\s\u00a0\u202f]/g, '').replace(',', '.') };
    };
    const enBaisse = () => estEnBaisse(lireReleve().valeur, dernier);
    const montrerBaisse = (visible) => {
      avertissement.hidden = !visible;
      if (!visible) erreurBaisse.hidden = true;
    };
    const demanderConfirmation = () => {
      montrerBaisse(true);
      erreurBaisse.textContent = I18n.t('parc.ouvrir_fenetre_releve.cochez_case_confirmer_valeur');
      erreurBaisse.hidden = false;
      caseBaisse.focus();
    };
    // L'avertissement apparaît au clic sur « Enregistrer » (pas pendant la frappe, ni à la sortie du
    // champ : la fenêtre grandirait sous le doigt et le bouton visé se déplacerait) ; il disparaît
    // dès que la valeur n'est plus en baisse.
    champValeur.addEventListener('input', () => { if (!enBaisse()) montrerBaisse(false); });
    caseBaisse.addEventListener('change', () => { if (caseBaisse.checked) erreurBaisse.hidden = true; });

    // Refus sur les lignes fraîches : le dernier relevé est relu (un autre poste a pu en saisir un
    // plus élevé) ; si la valeur est maintenant en baisse, l'avertissement et la case s'affichent.
    async function relireDernierReleve() {
      try {
        await Donnees.rechargerTable('releves');
      } catch (erreur) {
        console.warn('Prévo (parc) : relevés non relus après un refus.', erreur);
        return;
      }
      dernier = dernierReleveDe(Donnees.lignes('releves'), compteurId);
      afficherDernierReleve(contenu, dernier, unite);
      if (enBaisse() && !caseBaisse.checked) demanderConfirmation();
    }

    let fermerFenetre = null;
    let releve = null;
    let enCours = false;

    async function enregistrer() {
      if (enCours) return;
      const valeurs = lireReleve();
      const erreursSaisie = UI.verifierFormulaire(contenu);
      const erreurs = erreursSaisie.concat(verifierReleve(valeurs, Donnees.aujourdhui())
        .filter((e) => !erreursSaisie.some((s) => s.nom === e.nom)));
      afficherErreurs(contenu, erreurs);
      if (erreurs.length) return;
      if (enBaisse() && !caseBaisse.checked) {
        demanderConfirmation();
        return;
      }
      enCours = true;
      try {
        releve = await enregistrerReleve(compteurId, valeurs, caseBaisse.checked);
        fermerFenetre('ok');
      } catch (erreur) {
        App.signalerErreur(erreur, 'enregistrement du relevé');
        if (erreur instanceof Donnees.ErreurValidation) await relireDernierReleve();
      } finally {
        enCours = false;
      }
    }

    const choix = await UI.fenetre({
      titre: I18n.t('parc.ouvrir_fenetre_releve.saisir_releve', { compteur: (compteur.libelle || compteur.id) }),
      contenu,
      boutons: [
        { libelle: I18n.t('commun.bouton.annuler'), valeur: null, classe: 'btn-fantome' },
        { libelle: I18n.t('parc.ouvrir_fenetre_releve.enregistrer_releve'), valeur: 'ok', classe: 'btn-primaire', defaut: true },
      ],
      surOuverture(dialogue, fermer) { fermerFenetre = fermer; },
      avantFermeture(valeur) {
        if (valeur !== 'ok' || releve) return true;
        enregistrer();                                  // la fenêtre se ferme toute seule si tout va bien
        return false;
      },
    });
    if (choix !== 'ok') return false;
    const avertissementGammes = releve && releve.remiseAZero ? await apresRemiseAZero(compteurId, releve.remiseAZero) : '';
    await genererApresReleve(avertissementGammes);
    return true;
  }

  // Fenêtres ouvertes par l'arborescence (parc-arbre.js) et la fiche (parc-fiche.js) : usage
  // interne au module.
  Object.assign(Parc.interne, { ouvrirFenetreLocalisation, ouvrirFenetreReleve });

  return {
    afficherFormulaire,
  };
})());
