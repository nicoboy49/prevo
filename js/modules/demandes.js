'use strict';
// Demandes : module M2 « Demandes d'intervention » (DI) — tâche T13.
// Trois écrans (ARCHITECTURE.md §8, §10 RG1 et RG2 ; brief §9 E2 et E3) :
//   #/di/nouvelle   « Signaler un problème » : tous profils, pensé téléphone d'abord
//                   (une colonne, gros boutons utilisables avec des gants) ;
//   #/di            liste des demandes (filtres, tableau triable, cartes sur téléphone) ;
//   #/di/<id>       fiche d'une demande et, pour le responsable, les décisions
//                   (accepter, regrouper, différer, refuser).
//
// Fonctions exposées (utilisées par les tests et les autres modules) :
//   Demandes.prioriteCalculee(criticite, impact)   règle RG2, fonction pure
//   Demandes.creer(valeurs)                        → identifiant de la DI créée
//   Demandes.accepter(diId, { priorite, motifPriorite, type })  → identifiant de l'OT
//   Demandes.regrouper(diId, otId), Demandes.differer(diId, motif), Demandes.refuser(diId, motif)
//
// Règles de ce fichier :
// - toute écriture passe par Donnees.modifier (identifiants calculés DANS la fonction) ;
// - une action sur deux tables (accepter) enchaîne deux modifier() idempotents (décision D18) ;
// - contexte non sécurisé (téléphone en http://192.168…) : pas de crypto, la photo passe par
//   <input type="file" accept="image/*" capture="environment"> ;
// - pas d'alert/confirm/prompt ; console.warn (via App.signalerErreur) pour une erreur gérée.

const Demandes = (() => {

  // ===========================================================================================
  // 1. Constantes et règles pures
  // ===========================================================================================

  const STATUTS = ['Nouvelle', 'Acceptée', 'Regroupée', 'Différée', 'Refusée'];
  const STATUTS_A_TRAITER = ['Nouvelle', 'Différée'];          // décision encore possible (RG1)
  const STATUTS_OT_FERMES = ['Clôturé techniquement', 'Clôturé administrativement', 'Annulé'];
  const PRIORITES = ['P1', 'P2', 'P3', 'P4'];
  const TYPE_IMMEDIAT = 'correctif immédiat';
  const TYPE_DIFFERE = 'correctif différé';
  const MESSAGE_DEJA_TRAITEE = 'Cette demande a déjà été traitée sur un autre poste';

  // Les 4 impacts, dans l'ordre d'affichage, avec l'explication montrée sur les gros boutons.
  const IMPACTS = [
    { valeur: 'sécurité', libelle: 'Sécurité', explication: 'Danger pour une personne' },
    { valeur: 'arrêt', libelle: 'Arrêt', explication: 'La machine ne tourne plus' },
    { valeur: 'dégradé', libelle: 'Dégradé', explication: 'Elle tourne, mais mal' },
    { valeur: 'gêne', libelle: 'Gêne', explication: 'Peut attendre' },
  ];

  // RG2 : priorité = criticité de l'équipement × impact (« sécurité » donne toujours P1).
  const MATRICE_PRIORITE = {
    A: { 'gêne': 'P2', 'dégradé': 'P1', 'arrêt': 'P1' },
    B: { 'gêne': 'P3', 'dégradé': 'P2', 'arrêt': 'P1' },
    C: { 'gêne': 'P4', 'dégradé': 'P3', 'arrêt': 'P2' },
  };

  // Texte comparable : minuscules, sans accents ni espaces de bord (« Sécurité » → « securite »).
  function sansAccents(texte) {
    return String(texte === null || texte === undefined ? '' : texte)
      .normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
  }

  /** Impact écrit de façon approximative (« Securite », « ARRET ») → valeur canonique, ou ''. */
  function normaliserImpact(impact) {
    const cherche = sansAccents(impact);
    const trouve = IMPACTS.find((entree) => sansAccents(entree.valeur) === cherche);
    return trouve ? trouve.valeur : '';
  }

  /**
   * Priorité calculée (RG2), fonction pure :
   *   prioriteCalculee('B', 'dégradé') → 'P2' ; prioriteCalculee('C', 'sécurité') → 'P1'.
   * Criticité absente ou inconnue → B. Impact absent ou inconnu → '' (pas de priorité).
   */
  function prioriteCalculee(criticite, impact) {
    const impactConnu = normaliserImpact(impact);
    if (!impactConnu) return '';
    if (impactConnu === 'sécurité') return 'P1';
    const lettre = String(criticite === null || criticite === undefined ? '' : criticite).trim().toUpperCase();
    const ligne = MATRICE_PRIORITE[lettre] || MATRICE_PRIORITE.B;
    return ligne[impactConnu];
  }

  /** Type d'OT proposé à l'acceptation : P1 → correctif immédiat, sinon correctif différé. */
  function typePropose(priorite) {
    return priorite === 'P1' ? TYPE_IMMEDIAT : TYPE_DIFFERE;
  }

  /** Priorité calculée d'une DI (criticité lue sur son équipement). */
  function prioriteDeLaDemande(demande) {
    const equipement = Donnees.trouver('equipements', demande.equipement_id);
    return prioriteCalculee(equipement ? equipement.criticite : '', demande.impact);
  }

  function estOuvert(ot) {
    return Boolean(ot) && !STATUTS_OT_FERMES.includes(ot.statut);
  }

  /** OT ouverts (ni clôturés ni annulés) d'un équipement, les plus récents d'abord. */
  function otOuvertsDeLEquipement(equipementId) {
    return Donnees.lignes('ordres_travail')
      .filter((ot) => ot.equipement_id === equipementId && estOuvert(ot))
      .sort((a, b) => String(b.id).localeCompare(String(a.id), 'fr', { numeric: true }));
  }

  // Date prévue d'un OT : aujourd'hui + délai de la priorité (parametres.csv : delai_pN_h).
  // P4 (« prochain arrêt ») : pas de date.
  function datePrevue(priorite, aujourdhuiIso) {
    if (priorite === 'P4' || !PRIORITES.includes(priorite)) return '';
    const parDefaut = { P1: 0, P2: 24, P3: 168 };
    const lu = Donnees.nombre(Donnees.parametre('delai_' + priorite.toLowerCase() + '_h', ''));
    const heures = lu === null || lu < 0 ? parDefaut[priorite] : lu;
    const morceaux = /^(\d{4})-(\d{2})-(\d{2})/.exec(aujourdhuiIso || Donnees.aujourdhui());
    const date = new Date(Number(morceaux[1]), Number(morceaux[2]) - 1, Number(morceaux[3]), 0, 0, 0);
    date.setHours(date.getHours() + heures);
    return date.getFullYear() + '-' + deuxChiffres(date.getMonth() + 1) + '-' + deuxChiffres(date.getDate());
  }

  function deuxChiffres(nombre) {
    return String(nombre).padStart(2, '0');
  }

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  // ===========================================================================================
  // 2. Libellés partagés
  // ===========================================================================================

  /** « PO-02 — Pompe centrifuge… » : Parc.libelleEquipement s'il existe, sinon calculé ici. */
  function libelleEquipement(equipementId) {
    if (typeof Parc !== 'undefined' && Parc && typeof Parc.libelleEquipement === 'function') {
      try {
        const libelle = Parc.libelleEquipement(equipementId);
        if (libelle) return String(libelle);
      } catch (erreur) {
        console.warn('Prévo (demandes) : Parc.libelleEquipement a échoué, libellé calculé ici.', erreur);
      }
    }
    const equipement = Donnees.trouver('equipements', equipementId);
    if (!equipement) return equipementId || '—';
    return (equipement.repere || equipement.id) + (equipement.designation ? ' — ' + equipement.designation : '');
  }

  /** Nom inscrit dans « demandeur » : nom du profil (le responsable n'a pas de nom : « Responsable »). */
  function nomDuProfil() {
    const profil = App.profil;
    if (profil && profil.nom) return profil.nom;
    return App.libelleProfil() || 'Responsable';
  }

  /** Badge d'impact (le texte est toujours affiché, la couleur aide seulement). */
  function badgeImpact(impact) {
    const tons = { 'sécurité': 'ko', 'arrêt': 'attention', 'dégradé': 'cyan', 'gêne': 'neutre' };
    return UI.html`<span class="badge ${tons[impact] || 'neutre'}">${impact || '—'}</span>`;
  }

  // ===========================================================================================
  // 3. Écritures (toutes par Donnees.modifier)
  // ===========================================================================================

  // Vérifie qu'une décision est encore possible sur la DI (statut Nouvelle ou Différée).
  function verifierATraiter(demande, diId) {
    if (!demande) throw new Donnees.ErreurValidation('La demande ' + diId + ' est introuvable.');
    if (!STATUTS_A_TRAITER.includes(demande.statut)) {
      throw new Donnees.ErreurValidation(MESSAGE_DEJA_TRAITEE + ' (statut actuel : ' + demande.statut + ').');
    }
  }

  // Relit demandes.csv avant une décision : un autre poste a peut-être déjà décidé.
  // (Le contrôle est refait DANS la fonction de mutation : c'est lui qui fait foi.)
  async function verifierEncoreATraiter(diId) {
    const lignes = await Donnees.rechargerTable('demandes');
    verifierATraiter(lignes.find((ligne) => ligne.id === diId), diId);
  }

  /**
   * Crée une demande. valeurs : { equipement_id, symptome, impact, description, photo, demandeur }.
   * Renvoie l'identifiant (DI-AAAA-NNNN, calculé dans la fonction de mutation).
   */
  async function creer(valeurs) {
    const v = valeurs || {};
    const equipementId = texte(v.equipement_id);
    const symptome = texte(v.symptome).replace(/[\r\n]+/g, ' ');
    const impact = normaliserImpact(v.impact);
    if (!equipementId) throw new Donnees.ErreurValidation('Choisissez l\'équipement concerné.');
    if (!Donnees.trouver('equipements', equipementId)) {
      throw new Donnees.ErreurValidation('L\'équipement ' + equipementId + ' est inconnu.');
    }
    if (!symptome) throw new Donnees.ErreurValidation('Décrivez en quelques mots ce que vous constatez.');
    if (!impact) throw new Donnees.ErreurValidation('Choisissez l\'impact : sécurité, arrêt, dégradé ou gêne.');
    const demandeur = texte(v.demandeur) || nomDuProfil();
    const description = texte(v.description);
    const photo = texte(v.photo);

    return Donnees.modifier('demandes', (lignes, outils) => {
      const maintenant = outils.maintenant();
      const id = outils.nouvelId(lignes, maintenant);       // DI-AAAA-NNNN, recalculé à chaque essai
      lignes.push({
        id, date_heure: maintenant, demandeur, equipement_id: equipementId, symptome, impact,
        description, photo, statut: 'Nouvelle', motif_decision: '', date_decision: '', ot_id: '',
      });
      return id;
    }, { action: 'demande signalée' });
  }

  /**
   * Accepte une DI (RG1) : crée l'OT (ou réutilise celui qui porte déjà ce di_id) puis passe la DI
   * « Acceptée ». options : { priorite (défaut : calculée), motifPriorite (obligatoire si la
   * priorité change), type (défaut : P1 → correctif immédiat, sinon correctif différé) }.
   * Renvoie l'identifiant de l'OT.
   */
  async function accepter(diId, options) {
    const reglages = options || {};
    await verifierEncoreATraiter(diId);
    const demande = Donnees.trouver('demandes', diId);
    const calculee = prioriteDeLaDemande(demande) || 'P3';
    const priorite = texte(reglages.priorite) || calculee;
    if (!PRIORITES.includes(priorite)) throw new Donnees.ErreurValidation('Priorité inconnue : ' + priorite + '.');
    const motifPriorite = texte(reglages.motifPriorite);
    if (priorite !== calculee && !motifPriorite) {
      throw new Donnees.ErreurValidation('Indiquez le motif du changement de priorité (' + calculee + ' → ' + priorite + ').');
    }
    const type = texte(reglages.type) || typePropose(priorite);
    if (![TYPE_IMMEDIAT, TYPE_DIFFERE].includes(type)) {
      throw new Donnees.ErreurValidation('Type d\'ordre de travail inconnu : ' + type + '.');
    }
    const changementPriorite = priorite !== calculee
      ? 'priorité ' + calculee + ' → ' + priorite + ' : ' + motifPriorite : '';

    // (1) L'OT : réutilisé s'il existe déjà pour cette DI (essai précédent interrompu, autre poste),
    //     sinon créé. Idempotent : rejoué sans risque sur conflit.
    const otId = await Donnees.modifier('ordres_travail', (lignes, outils) => {
      const existant = lignes.find((ot) => ot.di_id === diId);
      if (existant) return existant.id;
      const maintenant = outils.maintenant();
      const id = outils.nouvelId(lignes, maintenant);
      lignes.push({
        id, origine: 'DI', di_id: diId, equipement_id: demande.equipement_id, type, priorite,
        statut: 'Créé', titre: texte(demande.symptome).replace(/[\r\n]+/g, ' '),
        travail_a_faire: demande.description || '', date_creation: maintenant,
        date_prevue: datePrevue(priorite, outils.aujourdhui()),
      });
      return id;
    }, { action: 'acceptation de ' + diId + (changementPriorite ? ' ; ' + changementPriorite : '') });

    // (2) La DI : encore à traiter ? (sinon un autre poste a décidé entre-temps)
    let vue = null;          // la DI telle que lue (fraîche) par la fonction de mutation
    try {
      await Donnees.modifier('demandes', (lignes, outils) => {
        const ligne = lignes.find((l) => l.id === diId);
        vue = ligne ? { statut: ligne.statut, ot_id: ligne.ot_id } : null;
        verifierATraiter(ligne, diId);
        ligne.statut = 'Acceptée';
        ligne.ot_id = otId;
        ligne.date_decision = outils.maintenant();
        ligne.motif_decision = changementPriorite ? changementPriorite.charAt(0).toUpperCase() + changementPriorite.slice(1) : '';
      }, { action: 'acceptée → ' + otId + (changementPriorite ? ' ; ' + changementPriorite : '') });
    } catch (erreur) {
      // La DI a été refusée, différée ou regroupée ailleurs entre les deux étapes : l'OT créé à
      // l'étape 1 n'a plus de raison d'être. (Acceptée ailleurs avec CET OT : il est conservé.)
      if (erreur instanceof Donnees.ErreurValidation && !(vue && vue.ot_id === otId)) {
        await annulerOtOrphelin(diId, otId);
      }
      throw erreur;
    }
    return otId;
  }

  /** Annule l'OT créé pour une DI finalement traitée sur un autre poste (s'il est encore « Créé »). */
  async function annulerOtOrphelin(diId, otId) {
    const motif = 'DI traitée sur un autre poste';
    try {
      await Donnees.modifier('ordres_travail', (lignes) => {
        const ot = lignes.find((l) => l.id === otId);
        if (!ot || ot.di_id !== diId || ot.statut !== 'Créé') return;
        ot.statut = 'Annulé';
        ot.motif_annulation = motif;
      }, { action: 'statut Créé → Annulé : ' + motif });
    } catch (erreur) {
      App.signalerErreur(erreur, 'annulation de l\'OT ' + otId);
    }
  }

  /** Rattache la DI à un OT ouvert du même équipement (statut « Regroupée »). */
  async function regrouper(diId, otId) {
    await verifierEncoreATraiter(diId);
    const demande = Donnees.trouver('demandes', diId);
    const ordres = await Donnees.rechargerTable('ordres_travail');
    const ot = ordres.find((ligne) => ligne.id === otId);
    if (!ot) throw new Donnees.ErreurValidation('L\'ordre de travail ' + otId + ' est introuvable.');
    if (!estOuvert(ot)) throw new Donnees.ErreurValidation('L\'ordre de travail ' + otId + ' n\'est plus ouvert (' + ot.statut + ').');
    if (ot.equipement_id !== demande.equipement_id) {
      throw new Donnees.ErreurValidation('L\'ordre de travail ' + otId + ' concerne un autre équipement.');
    }
    await Donnees.modifier('demandes', (lignes, outils) => {
      const ligne = lignes.find((l) => l.id === diId);
      verifierATraiter(ligne, diId);
      ligne.statut = 'Regroupée';
      ligne.ot_id = otId;
      ligne.date_decision = outils.maintenant();
      ligne.motif_decision = 'Regroupée avec ' + otId + ', déjà ouvert pour cet équipement.';
    }, { action: 'regroupée avec ' + otId });
    return otId;
  }

  /** Diffère une DI nouvelle (motif facultatif, visible du demandeur). */
  async function differer(diId, motif) {
    await verifierEncoreATraiter(diId);
    await Donnees.modifier('demandes', (lignes, outils) => {
      const ligne = lignes.find((l) => l.id === diId);
      verifierATraiter(ligne, diId);
      if (ligne.statut === 'Différée') throw new Donnees.ErreurValidation('Cette demande est déjà différée.');
      ligne.statut = 'Différée';
      ligne.date_decision = outils.maintenant();
      ligne.motif_decision = texte(motif);
    }, { action: 'différée' });
  }

  /** Refuse une DI : motif obligatoire, visible du demandeur. */
  async function refuser(diId, motif) {
    const motifPropre = texte(motif);
    if (!motifPropre) throw new Donnees.ErreurValidation('Le motif du refus est obligatoire : il sera montré au demandeur.');
    await verifierEncoreATraiter(diId);
    await Donnees.modifier('demandes', (lignes, outils) => {
      const ligne = lignes.find((l) => l.id === diId);
      verifierATraiter(ligne, diId);
      ligne.statut = 'Refusée';
      ligne.date_decision = outils.maintenant();
      ligne.motif_decision = motifPropre;
    }, { action: 'refusée' });
  }

  // ===========================================================================================
  // 4. Photo : réduite à 1280 px (JPEG) dès le choix, envoyée à la validation
  // ===========================================================================================

  // photo-AAAAMMJJ-HHMMSS-XXXX.jpg (Math.random suffit : pas de crypto en contexte non sécurisé ;
  // le stockage refuse d'écraser un document existant).
  function nomPhoto() {
    const d = new Date();
    const caracteres = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    let hasard = '';
    for (let i = 0; i < 4; i += 1) hasard += caracteres[Math.floor(Math.random() * caracteres.length)];
    return 'photo-' + d.getFullYear() + deuxChiffres(d.getMonth() + 1) + deuxChiffres(d.getDate())
      + '-' + deuxChiffres(d.getHours()) + deuxChiffres(d.getMinutes()) + deuxChiffres(d.getSeconds())
      + '-' + hasard + '.jpg';
  }

  // ===========================================================================================
  // 5. Écran « Signaler un problème » (#/di/nouvelle)
  // ===========================================================================================

  function afficherNouvelle(conteneur, parametres) {
    const equipementDemande = parametres.requete ? texte(parametres.requete.get('equipement')) : '';
    const libellesSymptomes = Donnees.lignes('codes_defaillance')
      .filter((code) => sansAccents(code.famille) === 'symptome' && code.libelle)
      .map((code) => code.libelle);
    const idSymptome = UI.identifiantUnique('di-symptome');
    const idDescription = UI.identifiantUnique('di-description');
    const idListe = UI.identifiantUnique('di-suggestions');
    const idPhoto = UI.identifiantUnique('di-photo');

    UI.remplir(conteneur, UI.html`
      <div class="di-nouvelle">
        <div class="entete-page"><div>
          <h1>Signaler un problème</h1>
          <p>Cinq questions, une minute. Le responsable maintenance reçoit votre demande aussitôt.</p>
        </div></div>
        <div class="di-alerte-equipement"></div>
        <form class="form-colonne di-formulaire" novalidate>
          <section class="carte di-etape">
            <div class="champ" data-champ="equipement_id">
              <span class="libelle">1. Quel équipement ? <span class="requis" aria-hidden="true">*</span></span>
              <div class="di-selecteur"></div>
              <p class="erreur-champ" hidden></p>
            </div>
          </section>

          <section class="carte di-etape">
            <div class="champ" data-champ="symptome">
              <label class="libelle" for="${idSymptome}">2. Que constatez-vous ? <span class="requis" aria-hidden="true">*</span></label>
              <input type="text" id="${idSymptome}" name="symptome" list="${idListe}" maxlength="200" required
                aria-required="true" autocomplete="off" enterkeyhint="next"
                placeholder="Ex. fuite d'huile sous la pompe">
              <datalist id="${idListe}">${libellesSymptomes.map((libelle) => UI.html`<option value="${libelle}"></option>`)}</datalist>
              ${libellesSymptomes.length ? UI.html`<div class="di-suggestions" role="group" aria-label="Suggestions de symptômes">
                ${libellesSymptomes.map((libelle) => UI.html`<button type="button" class="di-puce" data-symptome="${libelle}">${libelle}</button>`)}
              </div>` : ''}
              <p class="erreur-champ" hidden></p>
            </div>
          </section>

          <section class="carte di-etape">
            <div class="champ" data-champ="impact">
              <span class="libelle" id="${idSymptome}-impact">3. Quel impact ? <span class="requis" aria-hidden="true">*</span></span>
              <fieldset class="tuiles di-impacts" aria-labelledby="${idSymptome}-impact">
                ${IMPACTS.map((entree) => UI.html`
                  <label class="tuile${entree.valeur === 'sécurité' ? ' securite' : ''}">
                    <input type="radio" name="impact" value="${entree.valeur}">
                    <span>${entree.libelle}<small>${entree.explication}</small></span>
                  </label>`)}
              </fieldset>
              <div class="di-zone-securite"></div>
              <p class="erreur-champ" hidden></p>
              <p class="di-priorite" aria-live="polite"></p>
            </div>
          </section>

          <section class="carte di-etape">
            <div class="champ" data-champ="description">
              <label class="libelle" for="${idDescription}">4. Précisions <span class="aide">(facultatif)</span></label>
              <textarea id="${idDescription}" name="description" rows="4" data-dictee
                placeholder="Depuis quand ? Bruit, odeur, voyant allumé… Le clavier du téléphone permet de dicter."></textarea>
            </div>
          </section>

          <section class="carte di-etape">
            <div class="champ" data-champ="photo">
              <span class="libelle">5. Une photo <span class="aide">(facultatif)</span></span>
              <label class="btn btn-secondaire btn-gros di-bouton-photo" for="${idPhoto}">
                ${UI.icone('photo')}<span class="di-texte-photo">Prendre une photo<small>ou en choisir une dans la galerie</small></span>
              </label>
              <input type="file" id="${idPhoto}" class="di-fichier-photo" accept="image/*" capture="environment">
              <div class="di-apercu" hidden>
                <img class="di-apercu-image" alt="Photo jointe à la demande">
                <button type="button" class="btn btn-fantome di-retirer-photo">${UI.icone('fermer')}Retirer la photo</button>
              </div>
              <p class="aide di-etat-photo" aria-live="polite"></p>
            </div>
          </section>

          <p class="di-demandeur">Demande envoyée au nom de <b>${nomDuProfil()}</b>.</p>
          <button type="submit" class="btn btn-primaire btn-gros di-envoyer">
            ${UI.icone('valider')}<span>Envoyer la demande</span>
          </button>
        </form>
      </div>`);

    const formulaire = UI.$('.di-formulaire', conteneur);
    const champSymptome = UI.$('input[name=symptome]', formulaire);
    const zoneSecurite = UI.$('.di-zone-securite', formulaire);
    const zonePriorite = UI.$('.di-priorite', formulaire);
    const champPhoto = UI.$('.di-fichier-photo', formulaire);
    const apercu = UI.$('.di-apercu', formulaire);
    const imageApercu = UI.$('.di-apercu-image', formulaire);
    const etatPhoto = UI.$('.di-etat-photo', formulaire);
    const boutonEnvoyer = UI.$('.di-envoyer', formulaire);

    // État de la photo : Blob réduit, préparation en cours, nom une fois envoyée (pas de double envoi).
    const photo = { blob: null, preparation: null, nomEnvoye: '', adresseApercu: '' };

    // --- 1. équipement --------------------------------------------------------------------
    const selecteur = UI.selecteurEquipement(UI.$('.di-selecteur', formulaire), {
      equipements: Donnees.lignes('equipements'),
      localisations: Donnees.lignes('localisations'),
      valeur: equipementDemande,
      nom: 'equipement_id',
      surChoix: () => {
        App.marquerSaisie(true);
        effacerErreur('equipement_id');
        mettreAJourPriorite();
      },
    });
    if (equipementDemande && !selecteur.valeur()) {
      UI.$('.di-alerte-equipement', conteneur).appendChild(UI.bandeau('attention',
        UI.html`L'équipement <b>${equipementDemande}</b> est inconnu ou n'est plus actif : choisissez-le dans la liste.`));
    }

    // --- 2. symptôme : les puces remplissent le champ ---------------------------------------
    formulaire.addEventListener('click', (evenement) => {
      const puce = evenement.target.closest('.di-puce');
      if (!puce) return;
      champSymptome.value = puce.dataset.symptome;
      champSymptome.dispatchEvent(new Event('input', { bubbles: true }));
      effacerErreur('symptome');
    });
    champSymptome.addEventListener('input', () => { if (champSymptome.value.trim()) effacerErreur('symptome'); });

    // --- 3. impact : bandeau rouge si « sécurité », priorité calculée -------------------------
    function impactChoisi() {
      const coche = UI.$('input[name=impact]:checked', formulaire);
      return coche ? coche.value : '';
    }

    function mettreAJourPriorite() {
      const impact = impactChoisi();
      zoneSecurite.textContent = '';
      if (impact === 'sécurité') {
        zoneSecurite.appendChild(UI.bandeau('securite',
          UI.html`<b>Danger : mettez la zone en sécurité et prévenez votre responsable.</b>`));
      }
      const equipement = Donnees.trouver('equipements', selecteur.valeur());
      if (!impact) {
        UI.remplir(zonePriorite, UI.html`<span class="aide">La priorité s'affiche quand l'impact est choisi.</span>`);
        return;
      }
      const priorite = prioriteCalculee(equipement ? equipement.criticite : '', impact);
      UI.remplir(zonePriorite, UI.html`Priorité calculée : ${UI.badgePriorite(priorite)}
        <span class="aide">${equipement ? 'criticité ' + (equipement.criticite || 'B') + ' × impact ' + impact
          : 'choisissez l\'équipement pour affiner'}</span>`);
    }
    UI.$$('input[name=impact]', formulaire).forEach((bouton) => bouton.addEventListener('change', () => {
      effacerErreur('impact');
      mettreAJourPriorite();
    }));
    mettreAJourPriorite();

    // --- 5. photo -------------------------------------------------------------------------
    function libererApercu() {
      if (photo.adresseApercu) URL.revokeObjectURL(photo.adresseApercu);
      photo.adresseApercu = '';
    }

    function retirerPhoto() {
      libererApercu();
      photo.blob = null;
      photo.preparation = null;
      photo.nomEnvoye = '';
      champPhoto.value = '';
      imageApercu.removeAttribute('src');
      apercu.hidden = true;
      etatPhoto.textContent = '';
      UI.remplir(UI.$('.di-texte-photo', formulaire), UI.html`Prendre une photo<small>ou en choisir une dans la galerie</small>`);
    }

    champPhoto.addEventListener('change', () => {
      const fichier = champPhoto.files && champPhoto.files[0];
      if (!fichier) return;
      libererApercu();
      photo.blob = null;
      photo.nomEnvoye = '';
      etatPhoto.textContent = 'Préparation de la photo…';
      const preparation = UI.redimensionnerPhoto(fichier, 1280).then((blob) => {
        if (photo.preparation !== preparation) return blob;    // une autre photo a été choisie entre-temps
        photo.blob = blob;
        photo.adresseApercu = URL.createObjectURL(blob);
        imageApercu.src = photo.adresseApercu;
        apercu.hidden = false;
        etatPhoto.textContent = 'Photo prête (' + Math.max(1, Math.round(blob.size / 1024)) + ' Ko). Elle sera envoyée avec la demande.';
        UI.remplir(UI.$('.di-texte-photo', formulaire), UI.html`Changer la photo<small>la photo actuelle sera remplacée</small>`);
        return blob;
      }).catch((erreur) => {
        if (photo.preparation === preparation) retirerPhoto();
        UI.toast('Cette photo ne peut pas être lue. Essayez une autre photo.', 'attention');
        console.warn('Prévo (demandes) : photo illisible (' + (erreur && erreur.message) + ').', erreur);
        return null;
      });
      photo.preparation = preparation;
    });
    UI.$('.di-retirer-photo', formulaire).addEventListener('click', retirerPhoto);

    // --- erreurs de champ -----------------------------------------------------------------
    function blocChamp(nom) {
      return UI.$$('.champ', formulaire).find((bloc) => bloc.dataset.champ === nom);
    }

    function afficherErreur(nom, message) {
      const bloc = blocChamp(nom);
      const zone = UI.$(':scope > .erreur-champ', bloc);
      bloc.classList.add('en-erreur');
      zone.textContent = message;
      zone.hidden = false;
    }

    function effacerErreur(nom) {
      const bloc = blocChamp(nom);
      const zone = bloc && UI.$(':scope > .erreur-champ', bloc);
      if (!zone) return;
      bloc.classList.remove('en-erreur');
      zone.hidden = true;
      zone.textContent = '';
    }

    function verifier() {
      const manques = [];
      if (!selecteur.valeur()) manques.push(['equipement_id', 'Choisissez l\'équipement concerné.']);
      if (!champSymptome.value.trim()) manques.push(['symptome', 'Décrivez en quelques mots ce que vous constatez.']);
      if (!impactChoisi()) manques.push(['impact', 'Choisissez l\'impact.']);
      manques.forEach(([nom, message]) => afficherErreur(nom, message));
      if (manques.length) {
        const premier = blocChamp(manques[0][0]);
        premier.scrollIntoView({ block: 'center' });
        const cible = UI.$('input:not([type=hidden]):not([type=radio]), input[type=radio]', premier);
        if (cible) cible.focus({ preventScroll: true });
      }
      return manques.length === 0;
    }

    // --- envoi : photo d'abord, puis la demande ---------------------------------------------
    formulaire.addEventListener('submit', async (evenement) => {
      evenement.preventDefault();
      if (boutonEnvoyer.disabled || !verifier()) return;
      boutonEnvoyer.disabled = true;
      boutonEnvoyer.setAttribute('aria-busy', 'true');
      const texteBouton = UI.$('span', boutonEnvoyer);
      texteBouton.textContent = 'Envoi en cours…';
      try {
        if (photo.preparation) await photo.preparation;
        let nomDeLaPhoto = '';
        if (photo.blob) {
          if (!photo.nomEnvoye) photo.nomEnvoye = await App.adaptateur.ecrireDocument(nomPhoto(), photo.blob);
          nomDeLaPhoto = photo.nomEnvoye;
        }
        const impact = impactChoisi();
        const id = await creer({
          equipement_id: selecteur.valeur(),
          symptome: champSymptome.value,
          impact,
          description: UI.$('textarea[name=description]', formulaire).value,
          photo: nomDeLaPhoto,
        });
        App.marquerSaisie(false);
        libererApercu();
        afficherConfirmation(conteneur, id);
      } catch (erreur) {
        App.signalerErreur(erreur, 'envoi de la demande');
        boutonEnvoyer.disabled = false;
        boutonEnvoyer.removeAttribute('aria-busy');
        texteBouton.textContent = 'Envoyer la demande';
      }
    });
  }

  // Écran de confirmation : le numéro en grand, et la suite possible.
  function afficherConfirmation(conteneur, id) {
    const demande = Donnees.trouver('demandes', id) || { id, impact: '', equipement_id: '' };
    const priorite = prioriteDeLaDemande(demande);
    App.definirTitre('Demande envoyée');
    UI.remplir(conteneur, UI.html`
      <div class="di-confirmation" role="status">
        <div class="carte di-confirmation-carte">
          <div class="di-confirmation-icone">${UI.icone('valider')}</div>
          <p class="di-confirmation-titre">Demande envoyée</p>
          <p class="di-numero" data-numero="${id}">${id}</p>
          <p class="di-confirmation-texte">Notez ce numéro : il permet de suivre votre demande.<br>
            ${libelleEquipement(demande.equipement_id)} · priorité ${UI.badgePriorite(priorite)}</p>
        </div>
        <div class="di-zone-securite"></div>
        <div class="pile-gros">
          <a class="btn btn-primaire btn-gros" href="#/di/${encodeURIComponent(id)}">${UI.icone('demandes')}<span>Voir ma demande</span></a>
          <a class="btn btn-secondaire btn-gros" href="#/di">${UI.icone('ordres')}<span>Mes demandes</span></a>
          <button type="button" class="btn btn-secondaire btn-gros di-autre">${UI.icone('ajouter')}<span>Signaler un autre problème</span></button>
        </div>
      </div>`);
    if (demande.impact === 'sécurité') {
      UI.$('.di-zone-securite', conteneur).appendChild(UI.bandeau('securite',
        UI.html`<b>Danger : mettez la zone en sécurité et prévenez votre responsable.</b> N'attendez pas la réponse à cette demande.`));
    }
    UI.$('.di-autre', conteneur).addEventListener('click', () => App.naviguer('#/di/nouvelle'));
    window.scrollTo(0, 0);
  }

  // ===========================================================================================
  // 6. Liste des demandes (#/di)
  // ===========================================================================================

  function afficherListe(conteneur, parametres) {
    const requete = parametres.requete || new URLSearchParams();
    const profil = App.profil || {};
    const aUnNom = Boolean(profil.nom);
    const filtre = {
      statut: requete.get('statut') || (App.estResponsable() ? 'Nouvelle' : 'tous'),
      portee: requete.get('portee') || (App.estDemandeur() ? 'mes' : 'toutes'),
      recherche: requete.get('q') || '',
      equipement: requete.get('equipement') || '',
    };
    if (filtre.statut !== 'tous' && !STATUTS.includes(filtre.statut)) filtre.statut = 'tous';
    if (!aUnNom) filtre.portee = 'toutes';

    const optionsStatut = [
      { valeur: 'Nouvelle', libelle: 'À traiter (nouvelles)' },
      { valeur: 'Différée', libelle: 'Différées' },
      { valeur: 'Acceptée', libelle: 'Acceptées' },
      { valeur: 'Regroupée', libelle: 'Regroupées' },
      { valeur: 'Refusée', libelle: 'Refusées' },
      { valeur: 'tous', libelle: 'Tous les statuts' },
    ];

    UI.remplir(conteneur, UI.html`
      <div class="entete-page">
        <div><h1>Demandes d'intervention</h1>
          <p>${App.estResponsable() ? 'Les demandes à traiter, et tout l\'historique.' : 'Suivez vos demandes et la décision du responsable maintenance.'}</p></div>
        <div class="actions"><a class="btn btn-primaire" href="#/di/nouvelle">${UI.icone('ajouter')}Signaler un problème</a></div>
      </div>
      <article class="carte di-liste">
        <div class="filtres" data-hors-saisie>
          <input type="search" name="recherche" aria-label="Rechercher une demande"
            placeholder="N°, équipement, symptôme, demandeur…" value="${filtre.recherche}">
          <select name="statut" aria-label="Statut">
            ${optionsStatut.map((o) => UI.html`<option value="${o.valeur}" ${o.valeur === filtre.statut ? UI.brut('selected') : ''}>${o.libelle}</option>`)}
          </select>
          ${aUnNom ? UI.html`<select name="portee" aria-label="Demandes affichées">
            <option value="mes" ${filtre.portee === 'mes' ? UI.brut('selected') : ''}>Mes demandes</option>
            <option value="toutes" ${filtre.portee === 'toutes' ? UI.brut('selected') : ''}>Toutes les demandes</option>
          </select>` : ''}
        </div>
        <div class="di-filtre-equipement"></div>
        <p class="di-compte" aria-live="polite"></p>
        <div class="di-zone-tableau"></div>
        <ul class="liste-cartes di-cartes"></ul>
      </article>`);

    const zoneFiltres = UI.$('.filtres', conteneur);
    const compte = UI.$('.di-compte', conteneur);
    const listeCartes = UI.$('.di-cartes', conteneur);

    if (filtre.equipement) {
      const puce = UI.element(UI.html`<p class="di-puce-filtre">Équipement : <b>${libelleEquipement(filtre.equipement)}</b>
        <button type="button" class="btn btn-fantome">${UI.icone('fermer')}Tous les équipements</button></p>`);
      UI.$('button', puce).addEventListener('click', () => {
        filtre.equipement = '';
        puce.remove();
        rafraichir();
      });
      UI.$('.di-filtre-equipement', conteneur).appendChild(puce);
    }

    function lignesFiltrees() {
      const mots = UI.normaliserRecherche(filtre.recherche).split(' ').filter(Boolean);
      return Donnees.lignes('demandes').filter((demande) => {
        if (filtre.statut !== 'tous' && demande.statut !== filtre.statut) return false;
        if (filtre.portee === 'mes' && demande.demandeur !== profil.nom) return false;
        if (filtre.equipement && demande.equipement_id !== filtre.equipement) return false;
        if (!mots.length) return true;
        const texteRecherche = UI.normaliserRecherche([demande.id, demande.demandeur, demande.symptome,
          demande.description, demande.impact, demande.statut, demande.motif_decision,
          libelleEquipement(demande.equipement_id)].join(' '));
        return mots.every((mot) => texteRecherche.includes(mot));
      });
    }

    const tableau = UI.tableau({
      libelle: 'Demandes d\'intervention',
      colonnes: [
        { cle: 'id', libelle: 'N°', rendu: (l) => UI.html`<a href="#/di/${encodeURIComponent(l.id)}">${l.id}</a>` },
        { cle: 'date_heure', libelle: 'Date', rendu: celluleDate },
        { cle: 'equipement_id', libelle: 'Équipement', valeurTri: (l) => libelleEquipement(l.equipement_id), rendu: celluleEquipement },
        { cle: 'symptome', libelle: 'Symptôme', classe: 'di-col-symptome', rendu: (l) => celluleTexte(l.symptome) },
        { cle: 'impact', libelle: 'Impact', rendu: (l) => badgeImpact(l.impact) },
        { cle: 'priorite', libelle: 'Priorité calculée', valeurTri: (l) => prioriteDeLaDemande(l), rendu: (l) => UI.badgePriorite(prioriteDeLaDemande(l)) },
        { cle: 'statut', libelle: 'Statut', rendu: (l) => UI.badgeStatut(l.statut) },
        { cle: 'motif_decision', libelle: 'Motif (refus, report)', classe: 'di-col-motif',
          rendu: (l) => (['Refusée', 'Différée'].includes(l.statut) ? celluleTexte(l.motif_decision) : '') },
      ],
      lignes: [],
      triInitial: { cle: 'date_heure', sens: 'desc' },
      surClic: (l) => App.naviguer('#/di/' + encodeURIComponent(l.id)),
      vide: 'Aucune demande ne correspond à ces filtres.',
    });
    UI.$('.di-zone-tableau', conteneur).appendChild(tableau);

    // Cellules compactes : le texte complet reste lisible au survol (title) et dans la fiche.
    function celluleDate(l) {
      const morceaux = /^(\S+)\s+(\S+)$/.exec(UI.dateHeureFr(l.date_heure));
      return morceaux ? UI.html`<span class="di-date">${morceaux[1]}<small>${morceaux[2]}</small></span>` : UI.dateHeureFr(l.date_heure);
    }
    function celluleEquipement(l) {
      const equipement = Donnees.trouver('equipements', l.equipement_id);
      if (!equipement) return l.equipement_id;
      return UI.html`<span class="di-eq" title="${libelleEquipement(l.equipement_id)}"><b>${equipement.repere || equipement.id}</b><small>${equipement.designation}</small></span>`;
    }
    function celluleTexte(valeur) {
      return UI.html`<span class="di-coupe" title="${valeur}">${valeur}</span>`;
    }

    function carte(demande) {
      const priorite = prioriteDeLaDemande(demande);
      const motifVisible = ['Refusée', 'Différée'].includes(demande.statut) && demande.motif_decision;
      return UI.html`<li><a href="#/di/${encodeURIComponent(demande.id)}" class="${priorite === 'P1' || priorite === 'P2' ? 'accent-' + priorite.toLowerCase() : ''}">
        <div class="carte-tete"><b>${demande.id}</b>${UI.badgePriorite(priorite)}${UI.badgeStatut(demande.statut)}</div>
        <div class="carte-titre">${demande.symptome}</div>
        <div class="carte-meta"><span>${libelleEquipement(demande.equipement_id)}</span><span>${UI.dateHeureFr(demande.date_heure)}</span><span>${demande.impact}</span></div>
        ${motifVisible ? UI.html`<div class="di-motif"><b>Motif :</b> ${demande.motif_decision}</div>` : ''}
      </a></li>`;
    }

    function rafraichir() {
      const lignes = lignesFiltrees();
      tableau.mettreAJour(lignes);
      const triees = lignes.slice().sort((a, b) => String(b.date_heure).localeCompare(String(a.date_heure)));
      UI.remplir(listeCartes, triees.length ? UI.html`${triees.map(carte)}`
        : UI.html`<li>${UI.vide('Aucune demande', 'Aucune demande ne correspond à ces filtres.', 'demandes')}</li>`);
      compte.textContent = lignes.length + (lignes.length > 1 ? ' demandes' : ' demande');
    }

    zoneFiltres.addEventListener('input', (evenement) => {
      const champ = evenement.target;
      if (champ.name === 'recherche') filtre.recherche = champ.value;
      else if (champ.name === 'statut') filtre.statut = champ.value;
      else if (champ.name === 'portee') filtre.portee = champ.value;
      rafraichir();
    });
    rafraichir();
  }

  // ===========================================================================================
  // 7. Fiche d'une demande (#/di/<id>) et décisions du responsable
  // ===========================================================================================

  function texteSuivi(demande) {
    switch (demande.statut) {
      case 'Nouvelle': return 'En attente de la décision du responsable maintenance.';
      case 'Acceptée': return 'Acceptée : un ordre de travail a été créé.';
      case 'Regroupée': return 'Regroupée avec un ordre de travail déjà ouvert pour cet équipement.';
      case 'Différée': return 'Différée : elle sera traitée plus tard (par exemple au prochain arrêt).';
      case 'Refusée': return 'Refusée par le responsable maintenance.';
      default: return '';
    }
  }

  function afficherFiche(conteneur, parametres) {
    const diId = parametres.id;
    const demande = Donnees.trouver('demandes', diId);
    App.definirTitre(demande ? demande.id : 'Demande');
    if (!demande) {
      UI.remplir(conteneur, UI.html`
        <div class="entete-page"><div><div class="fil"><a href="#/di">Demandes</a> › <span>${diId}</span></div>
          <h1>Demande ${diId}</h1></div></div>
        ${UI.vide('Demande introuvable', 'Aucune demande ne porte ce numéro.', 'demandes')}`);
      return;
    }
    const equipement = Donnees.trouver('equipements', demande.equipement_id);
    const priorite = prioriteDeLaDemande(demande);
    const ot = demande.ot_id ? Donnees.trouver('ordres_travail', demande.ot_id) : null;
    const decisionPossible = App.estResponsable() && STATUTS_A_TRAITER.includes(demande.statut);

    UI.remplir(conteneur, UI.html`
      <div class="entete-page di-entete-fiche">
        <div>
          <div class="fil"><a href="#/di">Demandes</a> › <span>${demande.id}</span></div>
          <h1>${demande.symptome || demande.id}</h1>
          <p class="di-entete-badges"><b>${demande.id}</b> ${UI.badgeStatut(demande.statut)} ${UI.badgePriorite(priorite)} ${badgeImpact(demande.impact)}</p>
        </div>
      </div>
      <div class="di-zone-securite"></div>
      <div class="grille di-fiche">
        <article class="carte c8 di-details">
          <h2>La demande</h2>
          <dl class="valeurs">
            <dt>Équipement</dt>
            <dd>${equipement ? UI.html`<a href="#/equipement/${encodeURIComponent(equipement.id)}">${libelleEquipement(equipement.id)}</a>` : demande.equipement_id}</dd>
            <dt>Symptôme</dt><dd>${demande.symptome}</dd>
            <dt>Impact</dt><dd>${badgeImpact(demande.impact)}</dd>
            <dt>Priorité calculée</dt><dd>${UI.badgePriorite(priorite)}
              <span class="aide">criticité ${(equipement && equipement.criticite) || 'B'} × impact ${demande.impact || '—'}</span></dd>
            <dt>Précisions</dt><dd class="di-texte-long">${demande.description}</dd>
            <dt>Demandeur</dt><dd>${demande.demandeur}</dd>
            <dt>Signalée le</dt><dd>${UI.dateHeureFr(demande.date_heure)}</dd>
          </dl>
          ${demande.photo ? UI.html`<div class="di-photo"><h3>Photo</h3>
            <a class="di-lien-photo" target="_blank" rel="noopener"><img class="di-photo-image" alt="Photo jointe à ${demande.id}"></a>
            <p class="aide di-photo-etat">Chargement de la photo…</p></div>` : ''}
        </article>
        <aside class="c4 di-cote">
          <article class="carte di-suivi">
            <h2>Suivi</h2>
            <p>${UI.badgeStatut(demande.statut)} ${texteSuivi(demande)}</p>
            <dl class="valeurs">
              ${demande.date_decision ? UI.html`<dt>Décision le</dt><dd>${UI.dateHeureFr(demande.date_decision)}</dd>` : ''}
              ${demande.motif_decision ? UI.html`<dt>Motif</dt><dd class="di-motif-fiche">${demande.motif_decision}</dd>` : ''}
              ${demande.ot_id ? UI.html`<dt>Ordre de travail</dt><dd><a href="#/ot/${encodeURIComponent(demande.ot_id)}">${demande.ot_id}</a>
                ${ot ? UI.html` ${UI.badgeStatut(ot.statut)}` : ''}</dd>` : ''}
            </dl>
          </article>
          <div class="di-decision"></div>
        </aside>
      </div>`);

    if (demande.impact === 'sécurité' && STATUTS_A_TRAITER.includes(demande.statut)) {
      UI.$('.di-zone-securite', conteneur).appendChild(UI.bandeau('securite',
        UI.html`<b>Danger signalé :</b> la zone doit être mise en sécurité. Priorité P1 : à traiter immédiatement.`));
    }
    if (demande.photo) chargerPhoto(conteneur, demande.photo);
    if (decisionPossible) afficherPanneauDecision(UI.$('.di-decision', conteneur), demande, priorite);
  }

  // La photo est lue de façon asynchrone (URL du serveur ou URL d'objet en dossier / démo).
  async function chargerPhoto(conteneur, nom) {
    const image = UI.$('.di-photo-image', conteneur);
    const lien = UI.$('.di-lien-photo', conteneur);
    const etat = UI.$('.di-photo-etat', conteneur);
    try {
      const adresse = await App.adaptateur.urlDocument(nom);
      if (!adresse) { etat.textContent = 'Photo introuvable : ' + nom + '.'; image.hidden = true; return; }
      image.addEventListener('load', () => { etat.textContent = ''; }, { once: true });
      image.addEventListener('error', () => { etat.textContent = 'Photo illisible : ' + nom + '.'; image.hidden = true; }, { once: true });
      image.src = adresse;
      lien.href = adresse;
    } catch (erreur) {
      etat.textContent = 'Photo indisponible : ' + nom + '.';
      image.hidden = true;
      console.warn('Prévo (demandes) : photo « ' + nom + ' » non affichée (' + (erreur && erreur.message) + ').', erreur);
    }
  }

  function afficherPanneauDecision(zone, demande, priorite) {
    const otOuverts = otOuvertsDeLEquipement(demande.equipement_id);
    UI.remplir(zone, UI.html`
      <article class="carte di-panneau-decision">
        <h2>Décision</h2>
        <p class="di-rappel-priorite">Priorité calculée ${UI.badgePriorite(priorite)}</p>
        <p class="aide">Le demandeur voit la décision et son motif.</p>
        <div class="pile-gros">
          <button type="button" class="btn btn-primaire btn-gros" data-decision="accepter">${UI.icone('valider')}<span>Accepter<small>crée un ordre de travail</small></span></button>
          <button type="button" class="btn btn-secondaire btn-gros" data-decision="regrouper" ${otOuverts.length ? '' : UI.brut('disabled')}>${UI.icone('ordres')}<span>Regrouper<small>${otOuverts.length
            ? otOuverts.length + ' OT ouvert' + (otOuverts.length > 1 ? 's' : '') + ' sur cet équipement'
            : 'aucun OT ouvert sur cet équipement'}</small></span></button>
          ${demande.statut === 'Nouvelle' ? UI.html`<button type="button" class="btn btn-secondaire btn-gros" data-decision="differer">${UI.icone('horloge')}<span>Différer<small>à traiter plus tard</small></span></button>` : ''}
          <button type="button" class="btn btn-danger btn-gros" data-decision="refuser">${UI.icone('fermer')}<span>Refuser<small>motif obligatoire</small></span></button>
        </div>
      </article>`);

    zone.addEventListener('click', async (evenement) => {
      const bouton = evenement.target.closest('[data-decision]');
      if (!bouton || bouton.disabled) return;
      const actions = { accepter: decisionAccepter, regrouper: decisionRegrouper, differer: decisionDifferer, refuser: decisionRefuser };
      const boutons = UI.$$('[data-decision]', zone);
      const etatsAvant = boutons.map((b) => b.disabled);
      boutons.forEach((b) => { b.disabled = true; });
      try {
        await actions[bouton.dataset.decision](demande, priorite, otOuverts);
      } catch (erreur) {
        App.signalerErreur(erreur, 'décision sur ' + demande.id);
        // Un autre poste a peut-être décidé : on montre l'état réel de la demande.
        if (erreur instanceof Donnees.ErreurValidation || erreur instanceof Donnees.ErreurConflit) {
          await App.reafficher();
          return;
        }
      }
      if (document.contains(zone)) boutons.forEach((b, rang) => { b.disabled = etatsAvant[rang]; });
    });
  }

  // --- Accepter : priorité (modifiable avec motif), type proposé, date prévue -----------------
  async function decisionAccepter(demande, priorite) {
    const idPriorite = UI.identifiantUnique('di-acc-priorite');
    const idMotif = UI.identifiantUnique('di-acc-motif');
    const idType = UI.identifiantUnique('di-acc-type');
    const contenu = UI.element(UI.html`
      <div class="form-colonne di-fenetre-accepter">
        <p>Un ordre de travail va être créé pour <b>${libelleEquipement(demande.equipement_id)}</b> :
          « ${demande.symptome} ».</p>
        <div class="champ">
          <label class="libelle" for="${idPriorite}">Priorité</label>
          <select id="${idPriorite}" name="priorite">
            ${PRIORITES.map((p) => UI.html`<option value="${p}" ${p === priorite ? UI.brut('selected') : ''}>${p}${p === priorite ? ' (calculée)' : ''}</option>`)}
          </select>
        </div>
        <div class="champ di-champ-motif" hidden>
          <label class="libelle" for="${idMotif}">Motif du changement de priorité <span class="requis" aria-hidden="true">*</span></label>
          <textarea id="${idMotif}" name="motif" rows="3" data-dictee aria-required="true"></textarea>
          <p class="erreur-champ" hidden></p>
        </div>
        <div class="champ">
          <label class="libelle" for="${idType}">Type d'ordre de travail</label>
          <select id="${idType}" name="type">
            <option value="${TYPE_IMMEDIAT}">${TYPE_IMMEDIAT}</option>
            <option value="${TYPE_DIFFERE}">${TYPE_DIFFERE}</option>
          </select>
        </div>
        <p class="note di-date-prevue"></p>
      </div>`);
    const choixPriorite = UI.$('select[name=priorite]', contenu);
    const choixType = UI.$('select[name=type]', contenu);
    const blocMotif = UI.$('.di-champ-motif', contenu);
    const champMotif = UI.$('textarea', contenu);
    const erreurMotif = UI.$('.erreur-champ', blocMotif);
    const zoneDate = UI.$('.di-date-prevue', contenu);
    let typeTouche = false;

    function mettreAJour() {
      const choisie = choixPriorite.value;
      blocMotif.hidden = choisie === priorite;
      if (!typeTouche) choixType.value = typePropose(choisie);
      const date = datePrevue(choisie);
      zoneDate.textContent = date ? 'Date prévue : ' + UI.dateFr(date) + ' (délai de la priorité ' + choisie + ').'
        : 'Date prévue : au prochain arrêt (priorité P4, pas de date).';
    }
    choixPriorite.addEventListener('change', mettreAJour);
    choixType.addEventListener('change', () => { typeTouche = true; });
    champMotif.addEventListener('input', () => { erreurMotif.hidden = true; champMotif.removeAttribute('aria-invalid'); });
    mettreAJour();

    const choix = await UI.fenetre({
      titre: 'Accepter ' + demande.id,
      contenu,
      boutons: [
        { libelle: 'Annuler', valeur: null, classe: 'btn-fantome' },
        { libelle: 'Créer l\'ordre de travail', valeur: 'accepter', classe: 'btn-primaire', defaut: true },
      ],
      avantFermeture() {
        if (choixPriorite.value === priorite || champMotif.value.trim()) return true;
        erreurMotif.textContent = 'Le motif est obligatoire quand la priorité change.';
        erreurMotif.hidden = false;
        champMotif.setAttribute('aria-invalid', 'true');
        champMotif.focus();
        return false;
      },
    });
    if (choix !== 'accepter') return;
    const otId = await accepter(demande.id, {
      priorite: choixPriorite.value, motifPriorite: champMotif.value, type: choixType.value,
    });
    UI.toast('Demande ' + demande.id + ' acceptée : ' + otId + ' créé.', 'succes');
    App.naviguer('#/ot/' + encodeURIComponent(otId));
  }

  // --- Regrouper : choix d'un OT ouvert du même équipement -----------------------------------
  async function decisionRegrouper(demande, priorite, otOuverts) {
    const nomGroupe = UI.identifiantUnique('di-regroupe');
    const contenu = UI.element(UI.html`
      <div class="form-colonne">
        <p>Rattacher ${demande.id} à un ordre de travail déjà ouvert sur <b>${libelleEquipement(demande.equipement_id)}</b> :</p>
        <fieldset class="di-choix-ot"><legend class="visuellement-cache">Ordre de travail</legend>
          ${otOuverts.map((ot, rang) => UI.html`
            <label class="case di-option-ot"><input type="radio" name="${nomGroupe}" value="${ot.id}" ${rang === 0 ? UI.brut('checked') : ''}>
              <span><b>${ot.id}</b> ${UI.badgePriorite(ot.priorite)} ${UI.badgeStatut(ot.statut)}<br><span class="aide">${ot.titre}</span></span></label>`)}
        </fieldset>
      </div>`);
    const choix = await UI.fenetre({
      titre: 'Regrouper ' + demande.id,
      contenu,
      boutons: [
        { libelle: 'Annuler', valeur: null, classe: 'btn-fantome' },
        { libelle: 'Regrouper', valeur: 'regrouper', classe: 'btn-primaire', defaut: true },
      ],
    });
    if (choix !== 'regrouper') return;
    const coche = UI.$('input:checked', contenu);
    if (!coche) return;
    await regrouper(demande.id, coche.value);
    UI.toast('Demande ' + demande.id + ' regroupée avec ' + coche.value + '.', 'succes');
    App.marquerSaisie(false);
    await App.reafficher();
  }

  // --- Différer : motif facultatif -----------------------------------------------------------
  async function decisionDifferer(demande) {
    const idMotif = UI.identifiantUnique('di-motif-report');
    const contenu = UI.element(UI.html`
      <div class="champ">
        <label class="libelle" for="${idMotif}">Motif du report <span class="aide">(facultatif, visible du demandeur)</span></label>
        <textarea id="${idMotif}" name="motif" rows="3" data-dictee placeholder="Ex. à traiter lors de l'arrêt programmé de fin de mois"></textarea>
      </div>`);
    const choix = await UI.fenetre({
      titre: 'Différer ' + demande.id,
      contenu,
      boutons: [
        { libelle: 'Annuler', valeur: null, classe: 'btn-fantome' },
        { libelle: 'Différer', valeur: 'differer', classe: 'btn-primaire', defaut: true },
      ],
    });
    if (choix !== 'differer') return;
    await differer(demande.id, UI.$('textarea', contenu).value);
    UI.toast('Demande ' + demande.id + ' différée.', 'succes');
    App.marquerSaisie(false);
    await App.reafficher();
  }

  // --- Refuser : motif obligatoire ----------------------------------------------------------
  async function decisionRefuser(demande) {
    const motif = await UI.demanderMotif('Refuser ' + demande.id, 'Motif du refus (visible du demandeur)', {
      libelleValider: 'Refuser la demande', exemple: 'Ex. hors périmètre de la maintenance, à adresser au service méthodes',
    });
    if (motif === null) return;
    await refuser(demande.id, motif);
    UI.toast('Demande ' + demande.id + ' refusée.', 'succes');
    App.marquerSaisie(false);
    await App.reafficher();
  }

  // ===========================================================================================
  // 8. Enregistrement des écrans
  // ===========================================================================================

  // App est chargé après les modules : les écrans sont enregistrés une fois la page lue.
  // Ordre d'enregistrement important : « #/di/nouvelle » avant « #/di/<id> ».
  document.addEventListener('DOMContentLoaded', () => {
    const tousProfils = ['demandeur', 'technicien', 'responsable'];
    App.ecran({
      id: 'nouvelle-di', route: /^#\/di\/nouvelle$/, titre: 'Signaler un problème',
      menu: { libelle: 'Signaler', icone: 'ajouter', ordre: 15 },
      profils: tousProfils, tables: [],
      afficher: afficherNouvelle,
    });
    App.ecran({
      id: 'liste-di', route: /^#\/di$/, titre: 'Demandes',
      menu: { libelle: 'Demandes', icone: 'demandes', ordre: 20 },
      profils: tousProfils, tables: ['demandes', 'equipements'],
      afficher: afficherListe,
    });
    App.ecran({
      id: 'fiche-di', route: /^#\/di\/(?<id>[^/?]+)$/, titre: 'Demande', parent: 'liste-di',
      profils: tousProfils, tables: ['demandes', 'ordres_travail', 'equipements'],
      afficher: afficherFiche,
    });
  });

  return {
    STATUTS, IMPACTS, MATRICE_PRIORITE,
    prioriteCalculee, normaliserImpact, typePropose, datePrevue, libelleEquipement,
    creer, accepter, regrouper, differer, refuser,
  };
})();
