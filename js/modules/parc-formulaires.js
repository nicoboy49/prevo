'use strict';
// Parc (3/4) — formulaires : fenêtre de création et de modification d'une localisation (ouverte
// depuis le parc), écrans #/equipement/nouveau et #/equipement/<id>/modifier (responsable),
// fenêtre « Saisir un relevé » d'un compteur (technicien et responsable, ouverte depuis la fiche)
// (ARCHITECTURE.md §8, §10, §14.2 et §14.6). Complète l'objet Parc.

Object.assign(Parc, (() => {

  // Règles et outils de parc-regles.js.
  const { cheminLocalisation, libelleEquipement, verifierEquipement, verifierLocalisation } = Parc;
  const { comparerTextes, parRepere, identifiantsDescendants, dernierReleveDe, verifierReleve,
    estEnBaisse } = Parc.interne;

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
    ajouter(UI.champ(definition('valeur_remplacement'), valeur('valeur_remplacement'), {
      aide: 'Prix d\'un équipement neuf équivalent, en euros hors taxes (ex. 12 500).',
    }));
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
  // 8. Relevé de compteur : fenêtre de saisie et écriture (technicien et responsable)
  // ===========================================================================================

  /** « 15 855 h », « 0,58 bar » : nombre à la française suivi de l'unité du compteur. */
  function valeurAvecUnite(valeur, unite) {
    return UI.nombreFr(valeur) + (unite ? ' ' + unite : '');
  }

  /** Nom inscrit dans le relevé : celui du technicien (ou du demandeur), sinon « Responsable ». */
  function utilisateurCourant() {
    const profil = App.profil;
    if (!profil) return '';
    if (profil.type === 'responsable') return 'Responsable';
    return String(profil.nom || profil.technicienId || '').trim();
  }

  /**
   * Écrit un relevé dans releves.csv et renvoie son identifiant.
   *   valeurs : { date: 'AAAA-MM-JJ', valeur: '1234.5' } (point décimal) ;
   *   baisseConfirmee : vrai si l'utilisateur a confirmé une valeur plus basse que le dernier
   *   relevé (compteur remplacé ou remis à zéro).
   * Les contrôles sont refaits sur les lignes fraîches : un relevé plus élevé saisi entre-temps
   * sur un autre poste est vu, et la baisse non confirmée est alors refusée.
   */
  async function enregistrerReleve(compteurId, valeurs, baisseConfirmee) {
    return Donnees.modifier('releves', (lignes, outils) => {
      const compteur = Donnees.trouver('compteurs', compteurId);
      if (!compteur) throw new Donnees.ErreurValidation('Ce compteur n\'existe plus.');
      const problemes = verifierReleve(valeurs, outils.aujourdhui());
      if (problemes.length) throw new Donnees.ErreurValidation(problemes.map((p) => p.message).join(' '));
      const dernier = dernierReleveDe(lignes, compteurId);
      if (!baisseConfirmee && estEnBaisse(valeurs.valeur, dernier)) {
        throw new Donnees.ErreurValidation('La valeur saisie est plus basse que le dernier relevé ('
          + valeurAvecUnite(dernier.valeur, compteur.unite) + ' le ' + UI.dateFr(dernier.date)
          + '). Confirmez que le compteur a été remplacé ou remis à zéro, ou corrigez la valeur.');
      }
      const id = outils.nouvelId(lignes);
      lignes.push({ id, compteur_id: compteurId, date: valeurs.date, valeur: String(Donnees.nombre(valeurs.valeur)),
        utilisateur: utilisateurCourant() });
      return id;
    }, { action: 'relevé de compteur' });
  }

  // Après un relevé, une gamme au compteur ou au seuil peut être devenue échue (RG5) : la
  // génération est idempotente et sûre à plusieurs postes. Le toast dit ce qui a été créé.
  async function genererApresReleve() {
    let crees;
    try {
      crees = await Preventif.genererOTEchus();
    } catch (erreur) {
      App.signalerErreur({ message: 'Relevé enregistré, mais les OT préventifs n\'ont pas pu être générés : '
        + ((erreur && erreur.message) || String(erreur)) }, 'génération du préventif après un relevé');
      return;
    }
    UI.toast(crees.length ? 'Relevé enregistré. ' + Preventif.texteGeneration(crees.length) + '.' : 'Relevé enregistré.', 'succes');
  }

  // Contenu de la fenêtre : rappel du dernier relevé, date, valeur, avertissement de baisse.
  function contenuFenetreReleve(compteur, dernier, jour) {
    const unite = String(compteur.unite || '').trim();
    const champsSchema = Schema.table('releves').champs;
    const definition = (nom) => champsSchema.find((c) => c.nom === nom);
    const contenu = UI.element(UI.html`<div class="form-colonne parc-formulaire-releve">
      <p class="parc-releve-precedent">${dernier
        ? UI.html`Dernier relevé : <b class="fort">${valeurAvecUnite(dernier.valeur, unite)}</b> le ${UI.dateFr(dernier.date)}.`
        : 'Aucun relevé pour ce compteur.'}</p>
    </div>`);
    contenu.appendChild(UI.champ(definition('date'), jour, { libelle: 'Date du relevé', obligatoire: true, attributs: { max: jour } }));
    contenu.appendChild(UI.champ(definition('valeur'), '', {
      libelle: 'Valeur lue' + (unite ? ' (' + unite + ')' : ''), obligatoire: true,
      aide: 'Le nombre affiché par le compteur, sans calcul (ex. 1 250 ou 0,85).',
    }));
    contenu.appendChild(UI.element(UI.html`<div class="alerte attention parc-releve-baisse" role="alert" hidden>
      ${UI.icone('alerte')}<div class="alerte-texte">
        <p><b>Valeur plus basse que le dernier relevé${dernier ? ' (' + valeurAvecUnite(dernier.valeur, unite) + ')' : ''}.</b>
          Compteur remplacé ou remis à zéro ? Sinon, corrigez la valeur.</p>
        <label class="case"><input type="checkbox" name="baisse_confirmee" value="1">
          <span>Oui, le compteur a été remplacé ou remis à zéro</span></label>
        <p class="erreur-champ parc-releve-erreur-baisse" hidden></p>
      </div></div>`));
    return contenu;
  }

  /**
   * Fenêtre « Saisir un relevé » d'un compteur : date (aujourd'hui par défaut) et valeur. Une valeur
   * plus basse que le dernier relevé affiche un avertissement et demande une confirmation explicite
   * (case à cocher) ; « Annuler » ne change rien. Après l'écriture : génération des OT préventifs
   * échus. Renvoie vrai si un relevé a été enregistré (la fiche se réaffiche alors).
   */
  async function ouvrirFenetreReleve(compteurId) {
    const compteur = Donnees.trouver('compteurs', compteurId);
    if (!compteur) { UI.toast('Ce compteur n\'existe plus.', 'attention'); return false; }
    const jour = Donnees.aujourdhui();
    const dernier = dernierReleveDe(Donnees.lignes('releves'), compteurId);
    const contenu = contenuFenetreReleve(compteur, dernier, jour);
    const champValeur = UI.$('[name=valeur]', contenu);
    const avertissement = UI.$('.parc-releve-baisse', contenu);
    const caseBaisse = UI.$('[name=baisse_confirmee]', contenu);
    const erreurBaisse = UI.$('.parc-releve-erreur-baisse', contenu);

    // Valeurs saisies au format du fichier (point décimal, sans espaces).
    const lireReleve = () => {
      const valeurs = lireChamps(contenu);
      return { date: valeurs.date, valeur: valeurs.valeur.replace(/[\s  ]/g, '').replace(',', '.') };
    };
    const enBaisse = () => estEnBaisse(lireReleve().valeur, dernier);
    const montrerBaisse = (visible) => {
      avertissement.hidden = !visible;
      if (!visible) erreurBaisse.hidden = true;
    };
    // L'avertissement apparaît au clic sur « Enregistrer » (pas pendant la frappe, ni à la sortie du
    // champ : la fenêtre grandirait sous le doigt et le bouton visé se déplacerait) ; il disparaît
    // dès que la valeur n'est plus en baisse.
    champValeur.addEventListener('input', () => { if (!enBaisse()) montrerBaisse(false); });
    caseBaisse.addEventListener('change', () => { if (caseBaisse.checked) erreurBaisse.hidden = true; });

    let fermerFenetre = null;
    let enregistre = false;
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
        montrerBaisse(true);
        erreurBaisse.textContent = 'Cochez la case pour confirmer cette valeur, ou corrigez-la.';
        erreurBaisse.hidden = false;
        caseBaisse.focus();
        return;
      }
      enCours = true;
      try {
        await enregistrerReleve(compteurId, valeurs, caseBaisse.checked);
        enregistre = true;
        fermerFenetre('ok');
      } catch (erreur) {
        App.signalerErreur(erreur, 'enregistrement du relevé');
      } finally {
        enCours = false;
      }
    }

    const choix = await UI.fenetre({
      titre: 'Saisir un relevé — ' + (compteur.libelle || compteur.id),
      contenu,
      boutons: [
        { libelle: 'Annuler', valeur: null, classe: 'btn-fantome' },
        { libelle: 'Enregistrer le relevé', valeur: 'ok', classe: 'btn-primaire', defaut: true },
      ],
      surOuverture(dialogue, fermer) { fermerFenetre = fermer; },
      avantFermeture(valeur) {
        if (valeur !== 'ok' || enregistre) return true;
        enregistrer();                                  // la fenêtre se ferme toute seule si tout va bien
        return false;
      },
    });
    if (choix !== 'ok') return false;
    await genererApresReleve();
    return true;
  }

  // Fenêtres ouvertes par l'arborescence (parc-arbre.js) et la fiche (parc-fiche.js) : usage
  // interne au module.
  Object.assign(Parc.interne, { ouvrirFenetreLocalisation, ouvrirFenetreReleve });

  return {
    afficherFormulaire,
  };
})());
