'use strict';
// Parc (3/4) — formulaires : fenêtre de création et de modification d'une localisation (ouverte
// depuis le parc), écrans #/equipement/nouveau et #/equipement/<id>/modifier (responsable)
// (ARCHITECTURE.md §8, §10 et §14.2). Complète l'objet Parc.

Object.assign(Parc, (() => {

  // Règles et outils de parc-regles.js.
  const { cheminLocalisation, libelleEquipement, verifierEquipement, verifierLocalisation } = Parc;
  const { comparerTextes, parRepere, identifiantsDescendants } = Parc.interne;

  const TAILLE_MAX_DOCUMENT = 9 * 1024 * 1024;        // le serveur refuse plus de 10 Mo
  const EXTENSIONS_DOCUMENT = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'pdf', 'txt', 'csv', 'doc', 'docx', 'xls', 'xlsx', 'odt', 'ods'];
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

  // Fenêtre ouverte par l'arborescence (parc-arbre.js) : usage interne au module.
  Object.assign(Parc.interne, { ouvrirFenetreLocalisation });

  return {
    afficherFormulaire,
  };
})());
