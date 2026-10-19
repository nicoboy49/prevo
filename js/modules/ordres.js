'use strict';
// Ordres : module « Ordres de travail » (OT) de Prévo — écrans E4 (liste) et E5 (fiche),
// création manuelle ou d'urgence, règles RG3 (statuts), RG4 (clôture), RG7 (coût), RG8
// (habilitations) et impression du bon de travail A4 (ARCHITECTURE.md §10, brief §7 et §9).
//
// Plan du fichier (une section = un sujet ; chaque fonction fait une seule chose) :
//   1. Constantes et petits outils (textes, dates, libellés)
//   2. Règles métier PURES, exposées pour les tests (aucune écriture)
//   3. Écritures : toujours par Donnees.modifier (identifiants et statut contrôlés DANS la fonction)
//   4. Liste des OT (#/ot) : filtres, tableau triable, cartes sur téléphone, export CSV
//   5. Nouvel OT (#/ot/nouveau, ?equipement=…, ?urgence=1)
//   6. Fiche OT (#/ot/<id>) : en-tête, étapes, consignation, barre d'actions, messages
//   7. Onglet Préparation      8. Onglet Exécution      9. Onglet Compte rendu (+ coût)
//  10. Onglet Historique équipement      11. Bon de travail (impression)      12. Écrans
//
// Règles du projet : JavaScript classique (pas de modules), compatible file:// et contexte non
// sécurisé ; textes des données toujours échappés (UI.html) ; jamais d'alert/confirm/prompt ;
// une erreur gérée passe par App.signalerErreur (toast + console.warn).

const Ordres = (() => {

  // ===========================================================================================
  // 1. Constantes et petits outils
  // ===========================================================================================

  const STATUTS = ['Créé', 'Préparé', 'Planifié', 'En cours', 'En attente',
    'Clôturé techniquement', 'Clôturé administrativement', 'Annulé'];
  // Étapes « normales » affichées en haut de la fiche (En attente et Annulé sont « hors » étapes).
  const ETAPES = ['Créé', 'Préparé', 'Planifié', 'En cours', 'Clôturé techniquement', 'Clôturé administrativement'];
  const STATUTS_VERROUILLES = ['Clôturé administrativement', 'Annulé'];
  const STATUTS_CLOTURES = ['Clôturé techniquement', 'Clôturé administrativement'];
  const TYPES = ['correctif immédiat', 'correctif différé', 'préventif systématique',
    'préventif conditionnel', 'amélioration', 'réglementaire'];
  const PRIORITES = ['P1', 'P2', 'P3', 'P4'];
  const RAPPEL_CONSIGNATION = 'Cocher une case ne consigne rien : appliquez la procédure.';

  // Choix du filtre « état » de la liste (valeur → libellé).
  const ETATS_LISTE = [
    { valeur: 'ouverts', libelle: 'Ouverts' },
    { valeur: 'retard', libelle: 'En retard' },
    { valeur: 'clotures', libelle: 'Clôturés' },
    { valeur: 'annules', libelle: 'Annulés' },
    { valeur: 'tous', libelle: 'Tous' },
  ];

  // Mémoire du module pendant la session : filtres de la liste, onglet ouvert de chaque fiche.
  const memoire = { filtres: null, profilFiltres: '', ongletParOt: {} };
  // Formulaires de la fiche affichée : { formulaire, enregistrer } (vidé à chaque affichage).
  let formulairesFiche = [];

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  function nombre(valeur) {
    const resultat = Donnees.nombre(valeur);
    return resultat === null || Number.isNaN(resultat) ? 0 : resultat;
  }

  function arrondi(valeur, decimales) {
    const facteur = Math.pow(10, decimales === undefined ? 2 : decimales);
    return Math.round(valeur * facteur) / facteur;
  }

  /** Texte sans accents, en minuscules, ponctuation remplacée par des espaces. */
  function texteSimple(valeur) {
    return UI.normaliserRecherche(valeur).replace(/[^a-z0-9]+/g, ' ').trim();
  }

  function aujourdhui() {
    return Donnees.aujourdhui();
  }

  function deuxChiffres(nombreEntier) {
    return String(nombreEntier).padStart(2, '0');
  }

  function dateIso(date) {
    return date.getFullYear() + '-' + deuxChiffres(date.getMonth() + 1) + '-' + deuxChiffres(date.getDate());
  }

  /** Date prévue par défaut d'une priorité : maintenant + delai_pN_h (vide pour P4 « prochain arrêt »). */
  function datePrevueParDefaut(priorite) {
    if (priorite === 'P4') return '';
    const heures = Donnees.nombre(Donnees.parametre('delai_' + String(priorite).toLowerCase() + '_h', ''));
    if (heures === null || Number.isNaN(heures)) return aujourdhui();
    return dateIso(new Date(Date.now() + heures * 3600 * 1000));
  }

  function estResponsable() { return App.estResponsable(); }
  function estTechnicien() { return App.estTechnicien(); }
  function monTechnicienId() { return (App.profil && App.profil.technicienId) || ''; }

  // --- Libellés (équipements, techniciens, articles, codes) ---------------------------------

  function equipementDe(ot) {
    return Donnees.trouver('equipements', ot.equipement_id);
  }

  function repereEquipement(id) {
    const equipement = Donnees.trouver('equipements', id);
    return equipement ? (equipement.repere || equipement.id) : (id || '');
  }

  /** « CP-01 — Compresseur à vis 30 kW » (repli si le module Parc n'expose rien). */
  function libelleEquipement(id) {
    if (typeof Parc !== 'undefined' && Parc && typeof Parc.libelleEquipement === 'function') {
      try {
        const libelle = Parc.libelleEquipement(id);
        if (libelle) return libelle;
      } catch (erreur) { /* module Parc en cours d'écriture : repli ci-dessous */ }
    }
    const equipement = Donnees.trouver('equipements', id);
    if (!equipement) return id || '';
    return (equipement.repere || equipement.id) + (equipement.designation ? ' — ' + equipement.designation : '');
  }

  /** « Site › Atelier › Ligne » d'une localisation (parents remontés, 10 niveaux au plus). */
  function cheminLocalisation(localisationId) {
    const morceaux = [];
    let courant = Donnees.trouver('localisations', localisationId);
    for (let niveau = 0; courant && niveau < 10; niveau += 1) {
      morceaux.unshift(courant.libelle || courant.id);
      courant = courant.parent_id ? Donnees.trouver('localisations', courant.parent_id) : null;
    }
    return morceaux.join(' › ');
  }

  function nomTechnicien(id) {
    if (!id) return '';
    const technicien = Donnees.trouver('techniciens', id);
    if (!technicien) return id;
    return ((technicien.prenom || '') + ' ' + (technicien.nom || '')).trim() || id;
  }

  /** Techniciens proposés dans une liste : les actifs, plus celui déjà affecté s'il est inactif. */
  function listeTechniciens(idActuel) {
    return Donnees.lignes('techniciens')
      .filter((t) => t.actif !== '0' || t.id === idActuel)
      .map((t) => ({ valeur: t.id, libelle: nomTechnicien(t.id) + (t.metier ? ' — ' + t.metier : '') }))
      .sort((a, b) => a.libelle.localeCompare(b.libelle, 'fr'));
  }

  function libelleArticle(article) {
    if (!article) return '';
    return (article.reference ? article.reference + ' — ' : '') + (article.designation || article.id);
  }

  /** Codes de défaillance d'une famille (« symptôme », « cause », « remède ») pour une liste. */
  function listeCodes(famille) {
    return Donnees.lignes('codes_defaillance')
      .filter((c) => c.famille === famille && c.code)
      .map((c) => ({ valeur: c.code, libelle: c.code + ' — ' + (c.libelle || '') }))
      .sort((a, b) => a.valeur.localeCompare(b.valeur, 'fr', { numeric: true }));
  }

  function libelleCode(code) {
    if (!code) return '';
    const trouve = Donnees.lignes('codes_defaillance').find((c) => c.code === code);
    return trouve ? code + ' — ' + trouve.libelle : code;
  }

  function lignesDeLOt(table, otId) {
    return Donnees.lignes(table).filter((ligne) => ligne.ot_id === otId);
  }

  function operationsDe(otId) {
    return lignesDeLOt('ot_operations', otId)
      .slice().sort((a, b) => nombre(a.ordre) - nombre(b.ordre) || a.id.localeCompare(b.id));
  }

  /** Remplace la place <div data-place="nom" class="large"> par le champ, en gardant ses classes. */
  function placerChamp(formulaire, nom, element) {
    const place = UI.$('[data-place="' + nom + '"]', formulaire);
    place.classList.forEach((classe) => element.classList.add(classe));
    place.replaceWith(element);
  }

  /** Champ du schéma des OT rendu par UI.champ (libellé, contrôle, aide, erreur). */
  function champOt(nom, valeur, options) {
    return UI.champ(Schema.champ('ordres_travail', nom), valeur, options);
  }

  // ===========================================================================================
  // 2. Règles métier PURES (ARCHITECTURE.md §10) — aucune écriture, exposées pour les tests
  // ===========================================================================================

  /** Vrai si l'OT n'est ni clôturé (techniquement ou administrativement) ni annulé. */
  function estOuvert(ot) {
    return Boolean(ot) && !STATUTS_CLOTURES.includes(ot.statut) && ot.statut !== 'Annulé';
  }

  /** « OT en retard » : ouvert et date prévue dépassée (dateReference : aujourd'hui par défaut). */
  function enRetard(ot, dateReference) {
    const reference = dateReference || aujourdhui();
    return estOuvert(ot) && Boolean(ot.date_prevue) && ot.date_prevue.slice(0, 10) < reference;
  }

  function estVerrouille(ot) {
    return Boolean(ot) && STATUTS_VERROUILLES.includes(ot.statut);
  }

  function estCorrectif(ot) {
    return /^correctif/.test(texte(ot && ot.type));
  }

  function estUrgence(ot) {
    return ot.origine === 'urgence' || ot.type === 'correctif immédiat';
  }

  /** Statut de reprise d'un OT en attente : En cours s'il a déjà démarré, sinon Préparé. */
  function statutDeReprise(ot) {
    return texte(ot.date_debut) ? 'En cours' : 'Préparé';
  }

  /** Statuts atteignables depuis le statut actuel (tableau RG3, sans tenir compte du profil). */
  function transitionsPossibles(ot) {
    if (!ot) return [];
    switch (ot.statut) {
      case 'Créé':
        return estUrgence(ot) ? ['Préparé', 'En cours', 'En attente', 'Annulé'] : ['Préparé', 'En attente', 'Annulé'];
      case 'Préparé': return ['Planifié', 'En attente', 'Annulé'];
      case 'Planifié': return ['En cours', 'Préparé', 'En attente', 'Annulé'];
      case 'En cours': return ['Clôturé techniquement', 'En attente'];
      case 'En attente': return [statutDeReprise(ot), 'Annulé'];
      case 'Clôturé techniquement': return ['Clôturé administrativement', 'En cours'];
      default: return []; // Clôturé administrativement, Annulé : verrouillés
    }
  }

  /** « RAS », « R.A.S. », « rien à signaler »… (seuls, sans autre information). */
  function estRienASignaler(compteRendu) {
    const compact = texteSimple(compteRendu).replace(/ /g, '');
    return compact !== '' && /^(ras|rienasignaler)+$/.test(compact);
  }

  /** Pièces prévues d'un OT cumulées par article (quantité > 0 seulement) : Map article → quantité. */
  function quantitesPrevues(otId) {
    const cumul = new Map();
    lignesDeLOt('ot_pieces', otId).forEach((piece) => {
      const quantite = nombre(piece.quantite_prevue);
      if (quantite > 0 && piece.article_id) cumul.set(piece.article_id, (cumul.get(piece.article_id) || 0) + quantite);
    });
    return cumul;
  }

  /** Pièces prévues dont le stock est insuffisant : [{ article_id, libelle, prevu, stock }]. */
  function piecesManquantes(otId) {
    const manquantes = [];
    quantitesPrevues(otId).forEach((prevu, articleId) => {
      const stock = Donnees.stockArticle(articleId);
      if (stock < prevu) {
        manquantes.push({ article_id: articleId, libelle: libelleArticle(Donnees.trouver('articles', articleId)) || articleId, prevu: arrondi(prevu, 3), stock });
      }
    });
    return manquantes;
  }

  /**
   * Manques qui bloquent la clôture technique (RG4) : TOUS, dans un tableau de phrases.
   * options.temps : lignes ot_temps à utiliser (par défaut, celles de l'OT dans Donnees).
   */
  function verifierCloture(ot, options) {
    const manques = [];
    const temps = (options && options.temps) || lignesDeLOt('ot_temps', ot.id);
    const compteRendu = texte(ot.compte_rendu);
    if (!texte(ot.date_fin)) manques.push('la date de fin des travaux');
    else if (texte(ot.date_debut) && texte(ot.date_fin) < texte(ot.date_debut)) manques.push('une date de fin postérieure à la date de début');
    if (!temps.some((ligne) => nombre(ligne.heures) > 0)) manques.push('au moins un temps passé (onglet Exécution)');
    if (!texte(ot.cause_code)) manques.push('le code cause');
    if (!texte(ot.remede_code)) manques.push('le code remède');
    if (estCorrectif(ot) && estRienASignaler(compteRendu)) {
      manques.push('un vrai compte rendu : « RAS » ou « rien à signaler » est refusé sur un correctif (décrivez ce qui a été constaté et fait)');
    } else if (compteRendu.length < 10) {
      manques.push('un compte rendu d\'au moins 10 caractères');
    }
    if (ot.remise_service !== '1') manques.push('la case « Équipement remis en service en sécurité »');
    return manques;
  }

  /** Habilitations requises par un équipement (« BR, B2V » ou « BR / H0V ») : tableau. */
  function habilitationsRequises(equipement) {
    return texte(equipement && equipement.habilitation_requise).split(/[,/]/).map((h) => h.trim()).filter(Boolean);
  }

  /** Habilitations requises qui manquent au technicien à la date donnée (tableau, vide si tout va bien). */
  function habilitationsManquantes(equipement, technicienId, date) {
    const habilitations = Donnees.lignes('habilitations').filter((h) => h.technicien_id === technicienId);
    return habilitationsRequises(equipement).filter((requise) => !habilitations.some((h) =>
      texte(h.intitule).toLowerCase() === requise.toLowerCase()
      && (!texte(h.date_obtention) || h.date_obtention.slice(0, 10) <= date)
      && (!texte(h.date_echeance) || date <= h.date_echeance.slice(0, 10))));
  }

  /**
   * RG8 : message d'avertissement si le technicien n'a pas une habilitation requise valide à la
   * date (date prévue, sinon aujourd'hui), sinon null. equipement : ligne ou identifiant.
   * Ex. « TEC-0004 sans BR valide au 2026-10-21 ».
   */
  function verifierHabilitation(equipement, technicienId, dateReference) {
    const ligne = typeof equipement === 'string' ? Donnees.trouver('equipements', equipement) : equipement;
    if (!ligne || !technicienId) return null;
    const date = texte(dateReference).slice(0, 10) || aujourdhui();
    const manquantes = habilitationsManquantes(ligne, technicienId, date);
    if (!manquantes.length) return null;
    return technicienId + ' sans ' + manquantes.join(', ') + ' valide au ' + date;
  }

  /**
   * Peut-on passer l'OT au statut `cible` ? → { ok, erreurs, avertissements, piecesManquantes }.
   * `ot` porte les valeurs à jour (ex. motif_attente saisi). Contrôles : tableau RG3, motifs
   * obligatoires, Planifié (technicien, date prévue, stock des pièces prévues), clôture RG4.
   */
  function verifierPassage(ot, cible) {
    const erreurs = [];
    const avertissements = [];
    let manquantes = [];
    if (!ot) return { ok: false, erreurs: ['Ordre de travail introuvable.'], avertissements, piecesManquantes: manquantes };
    if (!transitionsPossibles(ot).includes(cible)) {
      erreurs.push(estVerrouille(ot)
        ? 'Cet OT est « ' + ot.statut + ' » : il est verrouillé. Une reprise se fait par un nouvel OT lié.'
        : 'Passage de « ' + ot.statut + ' » à « ' + cible + ' » impossible.');
    } else if (cible === 'En attente' && !texte(ot.motif_attente)) {
      erreurs.push('Le motif de mise en attente est obligatoire.');
    } else if (cible === 'Annulé' && !texte(ot.motif_annulation)) {
      erreurs.push('Le motif d\'annulation est obligatoire.');
    } else if (cible === 'Planifié') {
      if (!texte(ot.technicien_id)) erreurs.push('Choisissez le technicien (onglet Préparation).');
      if (!texte(ot.date_prevue)) erreurs.push('Indiquez la date prévue (onglet Préparation).');
      manquantes = piecesManquantes(ot.id);
      manquantes.forEach((piece) => erreurs.push('Stock insuffisant pour « ' + piece.libelle + ' » : '
        + UI.nombreFr(piece.prevu) + ' prévu(s), ' + UI.nombreFr(piece.stock) + ' en stock.'));
      const habilitation = verifierHabilitation(equipementDe(ot), ot.technicien_id, ot.date_prevue);
      if (habilitation) avertissements.push('Avertissement habilitation : ' + habilitation + '.');
    } else if (cible === 'Clôturé techniquement') {
      const manques = verifierCloture(ot);
      if (manques.length) erreurs.push('Il manque : ' + manques.join(' ; ') + '.');
    }
    return { ok: erreurs.length === 0, erreurs, avertissements, piecesManquantes: manquantes };
  }

  /**
   * Coût d'un OT (RG7) en euros : { heures, pieces, soustraitance, total, detail }.
   *   heures : Σ heures passées × taux horaire du technicien (main-d'œuvre, en €) ;
   *   pieces : Σ (sorties − retours de stock imputées à l'OT) × prix unitaire de l'article ;
   *   soustraitance : cout_soustraitance ; total : la somme.
   *   detail : { nombreHeures, temps: [{ technicien_id, date, heures, taux, montant }],
   *              pieces: [{ article_id, libelle, sorties, retours, quantite, prix, montant }] }.
   */
  function cout(ot) {
    const temps = lignesDeLOt('ot_temps', ot.id).map((ligne) => {
      const technicien = Donnees.trouver('techniciens', ligne.technicien_id);
      const taux = nombre(technicien && technicien.taux_horaire);
      const heures = nombre(ligne.heures);
      return { technicien_id: ligne.technicien_id, date: ligne.date, heures, taux, montant: heures * taux };
    });
    const parArticle = new Map();
    Donnees.lignes('mouvements_stock').forEach((mouvement) => {
      if (mouvement.ot_id !== ot.id || (mouvement.type !== 'sortie' && mouvement.type !== 'retour')) return;
      const entree = parArticle.get(mouvement.article_id) || { sorties: 0, retours: 0 };
      if (mouvement.type === 'sortie') entree.sorties += nombre(mouvement.quantite);
      else entree.retours += nombre(mouvement.quantite);
      parArticle.set(mouvement.article_id, entree);
    });
    const pieces = [];
    parArticle.forEach((entree, articleId) => {
      const article = Donnees.trouver('articles', articleId);
      const prix = nombre(article && article.prix_unitaire);
      const quantite = entree.sorties - entree.retours;
      pieces.push({ article_id: articleId, libelle: libelleArticle(article) || articleId, sorties: entree.sorties,
        retours: entree.retours, quantite, prix, montant: quantite * prix });
    });
    const montantHeures = temps.reduce((somme, ligne) => somme + ligne.montant, 0);
    const montantPieces = pieces.reduce((somme, ligne) => somme + ligne.montant, 0);
    const soustraitance = nombre(ot.cout_soustraitance);
    return {
      heures: arrondi(montantHeures),
      pieces: arrondi(montantPieces),
      soustraitance: arrondi(soustraitance),
      total: arrondi(montantHeures + montantPieces + soustraitance),
      detail: { nombreHeures: arrondi(temps.reduce((s, l) => s + l.heures, 0)), temps, pieces },
    };
  }

  /** Filtre des OT de la liste. filtres : { etat, priorite, technicien, type, recherche }. */
  function filtrer(ordres, filtres) {
    const reglages = filtres || {};
    const mots = UI.normaliserRecherche(reglages.recherche).split(' ').filter(Boolean);
    const date = aujourdhui();
    return ordres.filter((ot) => {
      if (reglages.etat === 'ouverts' && !estOuvert(ot)) return false;
      if (reglages.etat === 'retard' && !enRetard(ot, date)) return false;
      if (reglages.etat === 'clotures' && !STATUTS_CLOTURES.includes(ot.statut)) return false;
      if (reglages.etat === 'annules' && ot.statut !== 'Annulé') return false;
      if (reglages.priorite && ot.priorite !== reglages.priorite) return false;
      if (reglages.technicien === '__aucun' && ot.technicien_id) return false;
      if (reglages.technicien && reglages.technicien !== '__aucun' && ot.technicien_id !== reglages.technicien) return false;
      if (reglages.type && ot.type !== reglages.type) return false;
      if (mots.length) {
        const equipement = Donnees.trouver('equipements', ot.equipement_id) || {};
        const cible = UI.normaliserRecherche([ot.id, ot.titre, equipement.repere, equipement.designation, ot.equipement_id].join(' '));
        if (!mots.every((mot) => cible.includes(mot))) return false;
      }
      return true;
    });
  }

  // ===========================================================================================
  // 3. Écritures (Donnees.modifier) — chaque fonction relit la ligne fraîche et la contrôle
  // ===========================================================================================

  function ErreurValidation(message) {
    return new Donnees.ErreurValidation(message);
  }

  // Ligne d'OT dans une copie de table, ou erreur si absente ; `modifiable` refuse un OT verrouillé.
  function ligneOt(lignes, otId, modifiable) {
    const ligne = lignes.find((l) => l.id === otId);
    if (!ligne) throw ErreurValidation('L\'ordre de travail ' + otId + ' est introuvable.');
    if (modifiable && estVerrouille(ligne)) {
      throw ErreurValidation('L\'OT ' + otId + ' est « ' + ligne.statut + ' » : il ne peut plus être modifié.');
    }
    return ligne;
  }

  /**
   * Crée un OT et renvoie son identifiant (OT-AAAA-NNNN calculé dans la fonction de mutation).
   * valeurs : equipement_id, titre, type, priorite, origine (manuel, urgence…), et facultatifs.
   */
  async function creer(valeurs) {
    return Donnees.modifier('ordres_travail', (lignes, outils) => {
      const date = outils.aujourdhui();
      const id = outils.nouvelId(lignes, date);
      lignes.push(Object.assign({
        origine: 'manuel', statut: 'Créé', arret_production: '0', remise_service: '0',
      }, valeurs, { id, statut: 'Créé', date_creation: outils.maintenant() }));
      return id;
    }, { action: 'création de l\'OT (' + (valeurs.origine || 'manuel') + ')' });
  }

  /** Modifie des champs d'un OT non verrouillé ; renvoie la liste des champs réellement changés. */
  async function modifierOt(otId, changements, action) {
    return Donnees.modifier('ordres_travail', (lignes) => {
      const ligne = ligneOt(lignes, otId, true);
      const changes = Object.keys(changements).filter((nom) => texte(ligne[nom]) !== texte(changements[nom]));
      changes.forEach((nom) => { ligne[nom] = changements[nom]; });
      return changes;
    }, { action });
  }

  /**
   * Change le statut d'un OT (RG3). Dans la fonction de mutation : le statut lu doit être encore
   * `statutAttendu` (sinon l'OT a bougé sur un autre poste) et le passage est revérifié.
   * complement : { motif_attente } ou { motif_annulation }.
   */
  async function changerStatut(otId, statutAttendu, cible, complement) {
    const ajout = complement || {};
    const motif = ajout.motif_attente || ajout.motif_annulation || '';
    return Donnees.modifier('ordres_travail', (lignes, outils) => {
      const ligne = ligneOt(lignes, otId, false);
      if (ligne.statut !== statutAttendu) {
        throw ErreurValidation('L\'OT ' + otId + ' est passé « ' + ligne.statut + ' » sur un autre poste. Actualisez puis recommencez.');
      }
      const verification = verifierPassage(Object.assign({}, ligne, ajout), cible);
      if (!verification.ok) throw ErreurValidation(verification.erreurs.join(' '));
      const maintenant = outils.maintenant();
      if (cible === 'En attente') ligne.motif_attente = ajout.motif_attente;
      if (cible === 'Annulé') ligne.motif_annulation = ajout.motif_annulation;
      if (cible === 'En cours' && !texte(ligne.date_debut)) ligne.date_debut = maintenant;
      if (cible === 'En cours' && statutAttendu === 'Clôturé techniquement') ligne.date_cloture_tech = '';
      if (cible === 'Clôturé techniquement') ligne.date_cloture_tech = maintenant;
      if (cible === 'Clôturé administrativement') ligne.date_cloture_admin = maintenant;
      ligne.statut = cible;
      return cible;
    }, { action: 'statut ' + statutAttendu + ' → ' + cible + (motif ? ' : ' + motif : '') });
  }

  /** Priorité modifiée par le responsable, motif obligatoire (journal : « priorité P2 → P1 : motif »). */
  async function changerPriorite(otId, nouvelle, motif) {
    const ancienne = texte((Donnees.trouver('ordres_travail', otId) || {}).priorite);
    return Donnees.modifier('ordres_travail', (lignes) => {
      const ligne = ligneOt(lignes, otId, true);
      if (!PRIORITES.includes(nouvelle)) throw ErreurValidation('Priorité inconnue : ' + nouvelle + '.');
      if (!texte(motif)) throw ErreurValidation('Le motif du changement de priorité est obligatoire.');
      ligne.priorite = nouvelle;
    }, { action: 'priorité ' + ancienne + ' → ' + nouvelle + ' : ' + motif });
  }

  /** Crée un OT lié (reprise d'un OT verrouillé) : ot_lie_id = OT d'origine. Renvoie son identifiant. */
  async function creerOtLie(otId) {
    const origine = Donnees.trouver('ordres_travail', otId);
    if (!origine) throw ErreurValidation('L\'ordre de travail ' + otId + ' est introuvable.');
    return creer({
      origine: 'manuel', equipement_id: origine.equipement_id, type: origine.type, priorite: origine.priorite,
      titre: 'Reprise de ' + origine.id + ' — ' + texte(origine.titre).slice(0, 120),
      travail_a_faire: origine.travail_a_faire, consignes: origine.consignes,
      date_prevue: datePrevueParDefaut(origine.priorite), ot_lie_id: origine.id,
    });
  }

  /** Enregistre l'avertissement RG8 au journal (« avertissement habilitation : … »). */
  async function journaliserHabilitation(otId, message) {
    return Donnees.journaliser('ordres_travail', otId, 'avertissement habilitation : ' + message);
  }

  // ===========================================================================================
  // 4. Liste des OT (#/ot)
  // ===========================================================================================

  function filtresParDefaut() {
    return { etat: 'ouverts', priorite: '', technicien: estTechnicien() ? monTechnicienId() : '', type: '', recherche: '' };
  }

  const CLES_ADRESSE = ['filtre', 'etat', 'statut', 'priorite', 'technicien', 'type', 'recherche', 'equipement'];

  // Paramètres de l'adresse (liens de l'accueil) : ?filtre=retard (OT en retard), ?filtre=p1 (P1
  // ouverts), ?etat=ouverts|retard|clotures|annules|tous, ?priorite=P1, ?technicien=TEC-0002, ?type=…,
  // ?recherche=… (ou ?equipement=EQ-0005). Valeur inconnue ignorée. Avec des paramètres, on repart
  // des filtres par défaut ; sans paramètre, on reprend les filtres mémorisés pendant la session.
  function filtresDepuisAdresse(requete) {
    const profil = App.profil ? App.profil.type + ':' + App.profil.technicienId : '';
    if (memoire.profilFiltres !== profil) { memoire.filtres = null; memoire.profilFiltres = profil; }
    const avecParametres = Boolean(requete) && CLES_ADRESSE.some((cle) => requete.has(cle));
    const filtres = Object.assign(filtresParDefaut(), avecParametres ? {} : (memoire.filtres || {}));
    if (!avecParametres) return filtres;
    const etat = (requete.get('etat') || requete.get('filtre') || requete.get('statut') || '').toLowerCase()
      .replace('en-retard', 'retard').replace('en_retard', 'retard');
    if (ETATS_LISTE.some((e) => e.valeur === etat)) filtres.etat = etat;
    if (etat === 'p1') { filtres.etat = 'ouverts'; filtres.priorite = 'P1'; }   // « P1 ouverts » de l'accueil
    if (PRIORITES.includes((requete.get('priorite') || '').toUpperCase())) filtres.priorite = requete.get('priorite').toUpperCase();
    if (requete.has('technicien')) filtres.technicien = requete.get('technicien');
    if (TYPES.includes(requete.get('type'))) filtres.type = requete.get('type');
    const recherche = requete.get('recherche') || (requete.get('equipement') ? repereEquipement(requete.get('equipement')) : '');
    if (recherche) filtres.recherche = recherche;
    return filtres;
  }

  function optionsHtml(options, valeurChoisie) {
    return UI.html`${options.map((o) => UI.html`<option value="${o.valeur}"${o.valeur === valeurChoisie ? UI.brut(' selected') : ''}>${o.libelle}</option>`)}`;
  }

  function optionsTechnicienFiltre() {
    const options = [{ valeur: '', libelle: 'Tous les techniciens' }, { valeur: '__aucun', libelle: 'Non affectés' }];
    listeTechniciens('').forEach((t) => {
      options.push({ valeur: t.valeur, libelle: t.valeur === monTechnicienId() ? 'Mes OT (' + nomTechnicien(t.valeur) + ')' : nomTechnicien(t.valeur) });
    });
    return options;
  }

  function barreFiltresHtml(filtres) {
    return UI.html`
      <form class="filtres ot-filtres" id="ot-filtres" data-hors-saisie role="search" aria-label="Filtrer les ordres de travail">
        <label class="visuellement-cache" for="ot-filtre-recherche">Rechercher (n°, titre, équipement)</label>
        <input type="search" id="ot-filtre-recherche" name="recherche" value="${filtres.recherche}" placeholder="N°, titre ou équipement" autocomplete="off">
        <label class="visuellement-cache" for="ot-filtre-etat">État</label>
        <select id="ot-filtre-etat" name="etat">${optionsHtml(ETATS_LISTE, filtres.etat)}</select>
        <label class="visuellement-cache" for="ot-filtre-priorite">Priorité</label>
        <select id="ot-filtre-priorite" name="priorite">${optionsHtml([{ valeur: '', libelle: 'Toutes priorités' }].concat(PRIORITES.map((p) => ({ valeur: p, libelle: 'Priorité ' + p }))), filtres.priorite)}</select>
        <label class="visuellement-cache" for="ot-filtre-technicien">Technicien</label>
        <select id="ot-filtre-technicien" name="technicien">${optionsHtml(optionsTechnicienFiltre(), filtres.technicien)}</select>
        <label class="visuellement-cache" for="ot-filtre-type">Type</label>
        <select id="ot-filtre-type" name="type">${optionsHtml([{ valeur: '', libelle: 'Tous types' }].concat(TYPES.map((t) => ({ valeur: t, libelle: t }))), filtres.type)}</select>
      </form>`;
  }

  function badgeRetard(ot) {
    return enRetard(ot) ? UI.html` <span class="badge ko ot-retard">en retard</span>` : '';
  }

  function origineHtml(ot) {
    if (ot.origine === 'DI' && ot.di_id) return UI.html`DI <a href="#/di/${encodeURIComponent(ot.di_id)}">${ot.di_id}</a>`;
    return ot.origine || '';
  }

  // Origine dans la liste : le n° de DI (lien) ou le mot (préventif, urgence, manuel).
  function origineCourte(ot) {
    if (ot.origine === 'DI' && ot.di_id) return UI.html`<a href="#/di/${encodeURIComponent(ot.di_id)}" title="Demande d'intervention">${ot.di_id}</a>`;
    return ot.origine || '';
  }

  function colonnesListe() {
    return [
      { cle: 'id', libelle: 'N°', rendu: (ot) => UI.html`<a href="#/ot/${encodeURIComponent(ot.id)}">${ot.id}</a>` },
      { cle: 'priorite', libelle: 'Priorité', rendu: (ot) => UI.badgePriorite(ot.priorite) },
      { cle: 'statut', libelle: 'Statut', valeurTri: (ot) => String(STATUTS.indexOf(ot.statut)), rendu: (ot) => UI.badgeStatut(ot.statut) },
      { cle: 'equipement', libelle: 'Équipement', valeurTri: (ot) => repereEquipement(ot.equipement_id),
        rendu: (ot) => UI.html`<b class="sans-coupure">${repereEquipement(ot.equipement_id)}</b>` },
      { cle: 'titre', libelle: 'Titre', classe: 'ot-col-titre' },
      { cle: 'type', libelle: 'Type' },
      { cle: 'technicien', libelle: 'Technicien', valeurTri: (ot) => nomTechnicien(ot.technicien_id), rendu: (ot) => nomTechnicien(ot.technicien_id) },
      { cle: 'date_prevue', libelle: 'Prévu le', classe: 'ot-col-date', rendu: (ot) => UI.html`<span class="sans-coupure">${UI.dateFr(ot.date_prevue)}</span>${badgeRetard(ot)}` },
      { cle: 'origine', libelle: 'Origine', classe: 'ot-col-origine', rendu: origineCourte },
    ];
  }

  function cartesHtml(ordres) {
    if (!ordres.length) return UI.vide('Aucun ordre de travail', 'Aucun OT ne correspond à ces filtres.', 'ordres');
    return UI.html`<ul class="liste-cartes">${ordres.map((ot) => UI.html`
      <li><a href="#/ot/${encodeURIComponent(ot.id)}" class="${ot.priorite === 'P1' || ot.priorite === 'P2' ? 'accent-' + ot.priorite.toLowerCase() : ''}">
        <div class="carte-tete"><b>${ot.id}</b>${UI.badgePriorite(ot.priorite)}${UI.badgeStatut(ot.statut)}${badgeRetard(ot)}</div>
        <div class="carte-titre">${ot.titre}</div>
        <div class="carte-meta"><span>${repereEquipement(ot.equipement_id)}</span>
          ${ot.date_prevue ? UI.html`<span>Prévu le ${UI.dateFr(ot.date_prevue)}</span>` : ''}
          <span>${nomTechnicien(ot.technicien_id) || 'Non affecté'}</span><span>${ot.type}</span></div>
      </a></li>`)}</ul>`;
  }

  // Ordre par défaut (cartes du téléphone, et à égalité dans le tableau) : priorité, date prévue, n°.
  function trierParDefaut(ordres) {
    return ordres.slice().sort((a, b) => texte(a.priorite || 'P9').localeCompare(texte(b.priorite || 'P9'))
      || texte(a.date_prevue || '9999').localeCompare(texte(b.date_prevue || '9999')) || a.id.localeCompare(b.id));
  }

  function afficherListe(conteneur, parametres) {
    const filtres = filtresDepuisAdresse(parametres && parametres.requete);
    memoire.filtres = filtres;
    // Les filtres pris dans l'adresse sont mémorisés : l'adresse redevient « #/ot » (un réaffichage
    // ne remettra pas ces filtres par-dessus ceux que l'utilisateur aura changés).
    if (parametres && parametres.requete && String(parametres.requete)) {
      try { history.replaceState(history.state, '', '#/ot'); } catch (erreur) { /* adresse gardée telle quelle */ }
    }
    const tous = Donnees.lignes('ordres_travail');
    UI.remplir(conteneur, UI.html`
      <div class="entete-page">
        <div><h1>Ordres de travail</h1><p>Préparer, planifier, exécuter et clôturer les interventions.</p></div>
        <div class="actions">
          ${estResponsable() ? UI.html`
            <a class="btn btn-danger" id="ot-urgence" href="#/ot/nouveau?urgence=1">${UI.icone('alerte')}OT d'urgence</a>
            <a class="btn btn-primaire" id="ot-nouveau" href="#/ot/nouveau">${UI.icone('ajouter')}Nouvel OT</a>` : ''}
        </div>
      </div>
      ${barreFiltresHtml(filtres)}
      <div class="ot-liste-tete">
        <p class="note" id="ot-compteur" role="status"></p>
        <button type="button" class="btn btn-secondaire" id="ot-export">${UI.icone('export')}Exporter en CSV</button>
      </div>
      <div class="carte ot-liste-tableau"></div>
      <div class="ot-liste-cartes"></div>`);

    let affiches = [];
    const tableau = UI.tableau({
      colonnes: colonnesListe(), lignes: [], libelle: 'Ordres de travail',
      triInitial: { cle: 'priorite', sens: 'asc' }, vide: 'Aucun ordre de travail ne correspond à ces filtres.',
      surClic: (ot) => App.naviguer('#/ot/' + encodeURIComponent(ot.id)),
    });
    UI.$('.ot-liste-tableau', conteneur).appendChild(tableau);

    function rafraichir() {
      affiches = trierParDefaut(filtrer(tous, memoire.filtres));
      tableau.mettreAJour(affiches);
      UI.remplir(UI.$('.ot-liste-cartes', conteneur), cartesHtml(affiches));
      UI.$('#ot-compteur', conteneur).textContent = affiches.length + ' ordre(s) de travail sur ' + tous.length;
    }

    const formulaire = UI.$('#ot-filtres', conteneur);
    const lireFiltres = () => { memoire.filtres = Object.assign({}, memoire.filtres, UI.lireFormulaire(formulaire)); rafraichir(); };
    formulaire.addEventListener('input', lireFiltres);
    formulaire.addEventListener('change', lireFiltres);
    formulaire.addEventListener('submit', (evenement) => evenement.preventDefault());
    UI.$('#ot-export', conteneur).addEventListener('click', () => exporterCsv(affiches));
    rafraichir();
  }

  // --- Export CSV de la liste filtrée (ARCHITECTURE.md §3 : BOM, « ; », CRLF, guillemets, apostrophe) ---

  const COLONNES_EXPORT = [
    { nom: 'id', type: 'id', valeur: (ot) => ot.id },
    { nom: 'priorite', type: 'choix', valeur: (ot) => ot.priorite },
    { nom: 'statut', type: 'choix', valeur: (ot) => ot.statut },
    { nom: 'equipement_id', type: 'ref', valeur: (ot) => ot.equipement_id },
    { nom: 'equipement_repere', type: 'texte', protege: true, valeur: (ot) => repereEquipement(ot.equipement_id) },
    { nom: 'equipement_designation', type: 'texte', valeur: (ot) => (equipementDe(ot) || {}).designation || '' },
    { nom: 'titre', type: 'texte', valeur: (ot) => ot.titre },
    { nom: 'type', type: 'choix', valeur: (ot) => ot.type },
    { nom: 'technicien_id', type: 'ref', valeur: (ot) => ot.technicien_id },
    { nom: 'technicien', type: 'texte', valeur: (ot) => nomTechnicien(ot.technicien_id) },
    { nom: 'date_creation', type: 'date_heure', valeur: (ot) => ot.date_creation },
    { nom: 'date_prevue', type: 'date', valeur: (ot) => ot.date_prevue },
    { nom: 'en_retard', type: 'booleen', valeur: (ot) => (enRetard(ot) ? '1' : '0') },
    { nom: 'origine', type: 'choix', valeur: (ot) => ot.origine },
    { nom: 'di_id', type: 'ref', valeur: (ot) => ot.di_id },
  ];

  function celluleCsv(valeur) {
    return /[;"\r\n]|^[ \t]|[ \t]$/.test(valeur) ? '"' + valeur.replace(/"/g, '""') + '"' : valeur;
  }

  /** Texte CSV (sans BOM) d'une liste d'OT : en-tête puis une ligne par OT, fins de ligne CRLF. */
  function csvListe(ordres) {
    const lignes = [COLONNES_EXPORT.map((c) => c.nom).join(';')];
    ordres.forEach((ot) => {
      lignes.push(COLONNES_EXPORT.map((colonne) => celluleCsv(Donnees.csv.ecrireValeur(colonne, texte(colonne.valeur(ot))))).join(';'));
    });
    return lignes.join('\r\n') + '\r\n';
  }

  function exporterCsv(ordres) {
    const octets = new TextEncoder().encode(csvListe(ordres));
    const contenu = new Uint8Array(octets.length + 3);
    contenu.set([0xEF, 0xBB, 0xBF], 0);
    contenu.set(octets, 3);
    UI.telecharger('ordres-de-travail-' + aujourdhui() + '.csv', new Blob([contenu], { type: 'text/csv;charset=utf-8' }));
    UI.toast(ordres.length + ' ordre(s) de travail exporté(s).', 'succes');
  }

  // ===========================================================================================
  // 5. Nouvel OT (#/ot/nouveau, ?equipement=EQ-0005, ?urgence=1)
  // ===========================================================================================

  function afficherNouveau(conteneur, parametres) {
    const requete = parametres.requete || new URLSearchParams('');
    const urgence = requete.get('urgence') === '1';
    const priorite = urgence ? 'P1' : 'P3';
    App.definirTitre(urgence ? 'OT d\'urgence' : 'Nouvel OT');
    UI.remplir(conteneur, UI.html`
      <div class="entete-page"><div>
        <div class="fil"><a href="#/ot">Ordres de travail</a> › <span>${urgence ? 'OT d\'urgence' : 'Nouvel OT'}</span></div>
        <h1>${urgence ? 'OT d\'urgence' : 'Nouvel ordre de travail'}</h1>
        <p>${urgence ? 'Correctif immédiat, priorité P1 : l\'OT pourra être démarré tout de suite.' : 'OT créé à la main (origine « manuel »). Il pourra ensuite être préparé, planifié et exécuté.'}</p>
      </div></div>
      <form class="carte form-grille" id="form-nouvel-ot" novalidate>
        <div class="champ large"><span class="libelle">Équipement <span class="requis" aria-hidden="true">*</span></span>
          <div id="ot-nouveau-equipement"></div><p class="erreur-champ" id="ot-nouveau-equipement-erreur" hidden></p></div>
        <div class="large" data-place="titre"></div>
        <div data-place="type"></div><div data-place="priorite"></div>
        <div class="large" data-place="travail_a_faire"></div>
        <div data-place="technicien_id"></div><div data-place="date_prevue"></div>
        <div class="large ot-zone-habilitation"></div>
        <div class="actions">
          <a class="btn btn-fantome" href="#/ot">Annuler</a><span class="espace"></span>
          <button type="submit" class="btn ${urgence ? 'btn-danger' : 'btn-primaire'}">${UI.icone('valider')}${urgence ? 'Créer l\'OT d\'urgence' : 'Créer l\'OT'}</button>
        </div>
      </form>`);
    if (urgence) {
      conteneur.insertBefore(UI.bandeau('securite', UI.html`<b>Intervention d'urgence.</b> Mettez la zone en sécurité et appliquez la procédure de consignation de l'équipement avant d'intervenir.`), UI.$('#form-nouvel-ot', conteneur));
    }
    const formulaire = UI.$('#form-nouvel-ot', conteneur);
    const placer = (nom, element) => placerChamp(formulaire, nom, element);
    placer('titre', champOt('titre', '', { placeholder: 'Ex. PO-02 — fuite à la garniture' }));
    placer('type', champOt('type', urgence ? 'correctif immédiat' : 'correctif différé', { lectureSeule: urgence }));
    placer('priorite', champOt('priorite', priorite, { lectureSeule: urgence }));
    placer('travail_a_faire', champOt('travail_a_faire', ''));
    placer('technicien_id', champOt('technicien_id', '', { liste: listeTechniciens('') }));
    placer('date_prevue', champOt('date_prevue', datePrevueParDefaut(priorite), { aide: 'Par défaut : création + délai de la priorité (Paramètres).' }));

    const selecteur = UI.selecteurEquipement(UI.$('#ot-nouveau-equipement', formulaire), {
      equipements: Donnees.lignes('equipements'), localisations: Donnees.lignes('localisations'),
      valeur: requete.get('equipement') || '', surChoix: () => montrerHabilitationNouvelOt(formulaire, selecteur),
    });
    montrerHabilitationNouvelOt(formulaire, selecteur);
    formulaire.addEventListener('change', (evenement) => {
      if (evenement.target.name === 'priorite') {
        const champDate = UI.$('[name="date_prevue"]', formulaire);
        champDate.value = datePrevueParDefaut(evenement.target.value);
      }
      montrerHabilitationNouvelOt(formulaire, selecteur);
    });
    formulaire.addEventListener('submit', (evenement) => {
      evenement.preventDefault();
      validerNouvelOt(formulaire, selecteur, urgence);
    });
  }

  function montrerHabilitationNouvelOt(formulaire, selecteur) {
    const valeurs = UI.lireFormulaire(formulaire);
    const zone = UI.$('.ot-zone-habilitation', formulaire);
    zone.textContent = '';
    const message = verifierHabilitation(selecteur.valeur(), valeurs.technicien_id, valeurs.date_prevue);
    if (message) zone.appendChild(bandeauHabilitation(selecteur.valeur(), valeurs.technicien_id, valeurs.date_prevue));
  }

  async function validerNouvelOt(formulaire, selecteur, urgence) {
    const erreurs = UI.verifierFormulaire(formulaire);
    const erreurEquipement = UI.$('#ot-nouveau-equipement-erreur', formulaire);
    erreurEquipement.hidden = Boolean(selecteur.valeur());
    erreurEquipement.textContent = selecteur.valeur() ? '' : 'Choisissez l\'équipement concerné.';
    if (erreurs.length || !selecteur.valeur()) return;
    const valeurs = UI.lireFormulaire(formulaire);
    const bouton = UI.$('button[type=submit]', formulaire);
    bouton.disabled = true;
    try {
      const id = await creer({
        origine: urgence ? 'urgence' : 'manuel', equipement_id: selecteur.valeur(), titre: valeurs.titre,
        type: urgence ? 'correctif immédiat' : valeurs.type, priorite: urgence ? 'P1' : valeurs.priorite,
        travail_a_faire: valeurs.travail_a_faire, technicien_id: valeurs.technicien_id, date_prevue: valeurs.date_prevue,
      });
      const habilitation = verifierHabilitation(selecteur.valeur(), valeurs.technicien_id, valeurs.date_prevue);
      if (habilitation) await journaliserHabilitation(id, habilitation);
      App.marquerSaisie(false);
      UI.toast('Ordre de travail ' + id + ' créé.', 'succes');
      App.naviguer('#/ot/' + encodeURIComponent(id));
    } catch (erreur) {
      App.signalerErreur(erreur, 'création d\'un OT');
      bouton.disabled = false;
    }
  }

  // ===========================================================================================
  // 6. Fiche OT (#/ot/<id>) : en-tête, étapes, consignation, actions, messages
  // ===========================================================================================

  const LIBELLES_ACTION = {
    'Préparé': (ot) => (ot.statut === 'Planifié' ? 'Déplanifier' : ot.statut === 'En attente' ? 'Reprendre (Préparé)' : 'Marquer préparé'),
    'Planifié': () => 'Planifier',
    'En cours': (ot) => (ot.statut === 'Clôturé techniquement' ? 'Rouvrir' : ot.statut === 'En attente' ? 'Reprendre (En cours)' : 'Démarrer'),
    'En attente': () => 'Mettre en attente',
    'Annulé': () => 'Annuler l\'OT',
    'Clôturé techniquement': () => 'Clôturer techniquement',
    'Clôturé administrativement': () => 'Clôturer administrativement',
  };

  /** Le profil courant peut-il demander ce passage ? (technicien : démarrer, attente, clôture technique) */
  function actionAutorisee(ot, cible) {
    if (estResponsable()) return true;
    if (!estTechnicien()) return false;
    if (cible === 'En cours') return ot.statut !== 'Clôturé techniquement';   // rouvrir : responsable
    return cible === 'En attente' || cible === 'Clôturé techniquement';
  }

  function classeAction(cible) {
    if (cible === 'Annulé') return 'btn-danger';
    if (cible === 'En attente' || cible === 'Préparé') return 'btn-secondaire';
    return 'btn-primaire';
  }

  function boutonTransition(ot, cible) {
    return UI.html`<button type="button" class="btn ${classeAction(cible)}" data-action="transition" data-cible="${cible}">${LIBELLES_ACTION[cible](ot)}</button>`;
  }

  function boutonsTransitions(ot, cibles) {
    return cibles.filter((cible) => transitionsPossibles(ot).includes(cible) && actionAutorisee(ot, cible))
      .map((cible) => boutonTransition(ot, cible));
  }

  function etapesHtml(ot) {
    const reference = ot.statut === 'En attente' ? statutDeReprise(ot) : ot.statut;
    let rangCourant = ETAPES.indexOf(reference);
    if (ot.statut === 'Annulé') rangCourant = -1;
    const horsEtape = ot.statut === 'En attente' || ot.statut === 'Annulé';
    return UI.html`<ol class="etapes ot-etapes" aria-label="Avancement de l'OT">
      ${ETAPES.map((etape, rang) => {
        let classe = '';
        if (rang < rangCourant || (rang === rangCourant && horsEtape)) classe = 'fait';
        if (rang === rangCourant && !horsEtape) classe = 'courant';
        return UI.html`<li class="${classe}"${classe === 'courant' ? UI.brut(' aria-current="step"') : ''}>${etape}</li>`;
      })}
      ${horsEtape ? UI.html`<li class="hors" aria-current="step">${ot.statut}</li>` : ''}
    </ol>`;
  }

  function enteteFicheHtml(ot) {
    const equipement = equipementDe(ot);
    return UI.html`
      <div class="entete-page ot-entete">
        <div>
          <div class="fil"><a href="#/ot">Ordres de travail</a> › <span>${ot.id}</span></div>
          <h1><span class="ot-numero">${ot.id}</span> ${ot.titre}</h1>
          <div class="ot-badges">${UI.badgePriorite(ot.priorite)} ${UI.badgeStatut(ot.statut)}${badgeRetard(ot)}
            <span class="badge neutre">${ot.type}</span>
            ${equipement ? UI.html`<a class="ot-lien-equipement" href="#/equipement/${encodeURIComponent(equipement.id)}">${libelleEquipement(equipement.id)}</a>` : ''}
          </div>
        </div>
        <div class="actions">
          ${estResponsable() && !estVerrouille(ot) ? UI.html`<button type="button" class="btn btn-fantome" id="ot-priorite">${UI.icone('alerte')}Priorité</button>` : ''}
          <button type="button" class="btn btn-secondaire" id="ot-imprimer">${UI.icone('imprimer')}Imprimer le bon de travail</button>
        </div>
      </div>`;
  }

  function lienOt(id) {
    return UI.html`<a href="#/ot/${encodeURIComponent(id)}">${id}</a>`;
  }

  function reperesHtml(ot) {
    const lies = Donnees.lignes('ordres_travail').filter((autre) => autre.ot_lie_id === ot.id);
    return UI.html`<dl class="valeurs">
      <dt>Origine</dt><dd>${origineHtml(ot)}${ot.gamme_id ? UI.html` (gamme ${ot.gamme_id})` : ''}</dd>
      <dt>Technicien</dt><dd>${nomTechnicien(ot.technicien_id)}</dd>
      <dt>Créé le</dt><dd>${UI.dateHeureFr(ot.date_creation)}</dd>
      <dt>Prévu le</dt><dd>${UI.dateFr(ot.date_prevue)}${badgeRetard(ot)}</dd>
      <dt>Temps prévu</dt><dd>${ot.temps_prevu_h ? UI.heures(ot.temps_prevu_h) : ''}</dd>
      <dt>Début · fin</dt><dd>${UI.dateHeureFr(ot.date_debut)}${ot.date_fin ? ' → ' + UI.dateHeureFr(ot.date_fin) : ''}</dd>
      ${ot.date_cloture_tech ? UI.html`<dt>Clôture technique</dt><dd>${UI.dateHeureFr(ot.date_cloture_tech)}</dd>` : ''}
      ${ot.date_cloture_admin ? UI.html`<dt>Clôture administrative</dt><dd>${UI.dateHeureFr(ot.date_cloture_admin)}</dd>` : ''}
      ${ot.ot_lie_id ? UI.html`<dt>Reprend l'OT</dt><dd>${lienOt(ot.ot_lie_id)}</dd>` : ''}
      ${lies.length ? UI.html`<dt>Repris par</dt><dd>${lies.map((l, rang) => UI.html`${rang ? ', ' : ''}${lienOt(l.id)}`)}</dd>` : ''}
    </dl>`;
  }

  function equipementHtml(equipement) {
    if (!equipement) return UI.html`<p class="muted">Équipement introuvable.</p>`;
    return UI.html`<dl class="valeurs">
      <dt>Repère</dt><dd><a href="#/equipement/${encodeURIComponent(equipement.id)}">${equipement.repere || equipement.id}</a></dd>
      <dt>Désignation</dt><dd>${equipement.designation}</dd>
      <dt>Localisation</dt><dd>${cheminLocalisation(equipement.localisation_id)}</dd>
      <dt>Criticité</dt><dd>${equipement.criticite}</dd>
      <dt>État</dt><dd>${equipement.statut ? UI.badgeStatut(equipement.statut) : ''}</dd>
      <dt>Habilitation requise</dt><dd>${equipement.habilitation_requise || 'aucune'}</dd>
    </dl>`;
  }

  /** Bloc consignation (RG4) : procédure de l'équipement + rappel « Cocher une case ne consigne rien ». */
  function consignationHtml(equipement) {
    const procedure = texte(equipement && equipement.consignation);
    return UI.html`<section class="carte ot-consignation" aria-labelledby="ot-titre-consignation">
      <div class="entete-carte"><h2 id="ot-titre-consignation">${UI.icone('cle')} Consignation de l'équipement</h2></div>
      ${procedure ? UI.html`<div class="ot-procedure">${procedure}</div>`
        : UI.html`<p class="muted">Aucune procédure de consignation n'est renseignée pour cet équipement : voyez votre responsable avant d'intervenir.</p>`}
      <p class="ot-rappel"><b>${RAPPEL_CONSIGNATION}</b></p>
    </section>`;
  }

  function bandeauEtat(ot) {
    if (ot.statut === 'En attente') return UI.bandeau('attention', UI.html`<b>En attente</b> — ${ot.motif_attente || 'motif non renseigné'}`);
    if (ot.statut === 'Annulé') return UI.bandeau('important', UI.html`<b>OT annulé</b> — ${ot.motif_annulation || 'motif non renseigné'}. Il reste consultable mais n'est plus modifiable.`);
    if (ot.statut === 'Clôturé administrativement') {
      return UI.bandeau('info', UI.html`<b>OT verrouillé</b> (clôturé administrativement le ${UI.dateHeureFr(ot.date_cloture_admin)}) : lecture seule. Une reprise se fait par un nouvel OT lié.`);
    }
    return null;
  }

  function actionsHtml(ot) {
    const boutons = boutonsTransitions(ot, ['Préparé', 'Planifié', 'En cours', 'Clôturé techniquement', 'Clôturé administrativement', 'En attente', 'Annulé']);
    const lie = estVerrouille(ot) && estResponsable()
      ? UI.html`<button type="button" class="btn btn-primaire" id="ot-lie">${UI.icone('ajouter')}Créer un OT lié</button>` : '';
    if (!boutons.length && !lie) return '';
    return UI.html`<div class="carte ot-actions sans-impression"><div class="entete-carte"><h2>Actions</h2></div>
      <div class="actions">${boutons}${lie}</div></div>`;
  }

  /** Affiche un message (refus, manques…) au-dessus des onglets et le fait voir. */
  function afficherMessage(type, contenu) {
    const zone = UI.$('#ot-message');
    if (!zone) { UI.toast(String(contenu), type === 'important' ? 'erreur' : 'attention'); return null; }
    zone.textContent = '';
    const bandeau = UI.bandeau(type, contenu);
    zone.appendChild(bandeau);
    if (typeof zone.scrollIntoView === 'function') zone.scrollIntoView({ block: 'nearest' });
    return bandeau;
  }

  function viderMessage() {
    const zone = UI.$('#ot-message');
    if (zone) zone.textContent = '';
  }

  function ongletParDefaut(ot) {
    if (['En cours', 'En attente'].includes(ot.statut)) return 'execution';
    if (STATUTS_CLOTURES.includes(ot.statut) || ot.statut === 'Annulé') return 'compte-rendu';
    return 'preparation';
  }

  function afficherFiche(conteneur, parametres) {
    formulairesFiche = [];
    const ot = Donnees.trouver('ordres_travail', parametres.id);
    if (!ot) {
      UI.remplir(conteneur, UI.html`<div class="entete-page"><div><div class="fil"><a href="#/ot">Ordres de travail</a> › <span>${parametres.id}</span></div><h1>Ordre de travail ${parametres.id}</h1></div></div>
        ${UI.vide('Ordre de travail introuvable', 'Aucun OT ne porte cet identifiant.', 'ordres')}`);
      return;
    }
    App.definirTitre(ot.id);
    const equipement = equipementDe(ot);
    // Racine neuve à chaque affichage : #contenu est réutilisé, ses écouteurs s'accumuleraient.
    const racine = document.createElement('div');
    racine.className = 'ot-fiche';
    UI.remplir(conteneur, racine);
    UI.remplir(racine, UI.html`
      ${enteteFicheHtml(ot)}
      ${etapesHtml(ot)}
      <div class="ot-bandeau-etat"></div>
      <div class="grille">
        <section class="carte c6"><h2>Équipement</h2>${equipementHtml(equipement)}</section>
        <section class="carte c6"><h2>Repères</h2>${reperesHtml(ot)}</section>
      </div>
      ${consignationHtml(equipement)}
      ${actionsHtml(ot)}
      <div id="ot-message" class="ot-message" aria-live="polite"></div>
      <div class="ot-onglets"></div>`);
    const etat = bandeauEtat(ot);
    if (etat) UI.$('.ot-bandeau-etat', racine).appendChild(etat);

    UI.onglets(UI.$('.ot-onglets', racine), [
      { id: 'preparation', libelle: 'Préparation', afficher: (panneau) => afficherPreparation(panneau, ot) },
      { id: 'execution', libelle: 'Exécution', afficher: (panneau) => afficherExecution(panneau, ot) },
      { id: 'compte-rendu', libelle: 'Compte rendu', afficher: (panneau) => afficherCompteRendu(panneau, ot) },
      { id: 'historique', libelle: 'Historique équipement', afficher: (panneau) => afficherHistorique(panneau, ot) },
    ], { actif: memoire.ongletParOt[ot.id] || ongletParDefaut(ot), libelle: 'Parties de l\'ordre de travail',
      surChangement: (id) => { memoire.ongletParOt[ot.id] = id; } });

    brancherActionsFiche(racine, ot);
  }

  function brancherActionsFiche(racine, ot) {
    racine.addEventListener('click', (evenement) => {
      const bouton = evenement.target.closest('button[data-action="transition"]');
      if (bouton) { demanderTransition(ot, bouton.dataset.cible, bouton); return; }
      if (evenement.target.closest('#ot-imprimer')) imprimerBon(ot.id);
      if (evenement.target.closest('#ot-priorite')) demanderPriorite(ot);
      if (evenement.target.closest('#ot-lie')) lancerOtLie(ot);
      const attentePiece = evenement.target.closest('button[data-action="attente-piece"]');
      if (attentePiece) mettreEnAttentePiece(ot);
    });
  }

  // --- Formulaires de la fiche : enregistrés avant une transition s'ils ont été modifiés ------

  /** Déclare un formulaire de la fiche : `enregistrer()` renvoie true si l'enregistrement a réussi. */
  function declarerFormulaire(formulaire, enregistrer) {
    const marquer = () => { formulaire.dataset.modifie = '1'; };
    formulaire.addEventListener('input', marquer);
    formulaire.addEventListener('change', marquer);
    formulairesFiche.push({ formulaire, enregistrer });
  }

  /** Enregistre les formulaires modifiés (sans réafficher). Renvoie { ok, enregistres }. */
  async function enregistrerFormulairesModifies() {
    let enregistres = 0;
    for (const entree of formulairesFiche) {
      if (entree.formulaire.dataset.modifie !== '1' || !document.contains(entree.formulaire)) continue;
      const reussi = await entree.enregistrer();
      if (!reussi) return { ok: false, enregistres };
      entree.formulaire.dataset.modifie = '0';
      enregistres += 1;
    }
    return { ok: true, enregistres };
  }

  /** Réaffiche la fiche après un enregistrement (saisie terminée, défilement conservé). */
  async function apresEnregistrement() {
    App.marquerSaisie(false);
    await App.reafficher();
  }

  // Exécute une écriture : bouton désactivé pendant l'action, erreur affichée proprement.
  async function pendant(bouton, action, contexte) {
    if (bouton) bouton.disabled = true;
    try {
      return await action();
    } catch (erreur) {
      App.signalerErreur(erreur, contexte);
      return undefined;
    } finally {
      if (bouton && document.contains(bouton)) bouton.disabled = false;
    }
  }

  function listeErreursHtml(titre, erreurs) {
    return UI.html`<b>${titre}</b><ul class="ot-manques">${erreurs.map((e) => UI.html`<li>${e}</li>`)}</ul>`;
  }

  /** Clic sur un bouton de transition : motifs, enregistrement des saisies, contrôles, écriture. */
  async function demanderTransition(ot, cible, bouton) {
    viderMessage();
    const sauvegarde = await enregistrerFormulairesModifies();
    if (!sauvegarde.ok) return;
    const actuel = Donnees.trouver('ordres_travail', ot.id) || ot;
    const complement = await demanderComplement(actuel, cible);
    if (complement === null) { if (sauvegarde.enregistres) await apresEnregistrement(); return; }
    const verification = verifierPassage(Object.assign({}, actuel, complement), cible);
    if (!verification.ok) {
      if (sauvegarde.enregistres) await apresEnregistrement();
      afficherRefus(actuel, cible, verification);
      return;
    }
    if (cible === 'Clôturé administrativement' && !(await UI.confirmer(
      'L\'OT ' + actuel.id + ' sera verrouillé : plus aucune modification possible. Une reprise se fera par un nouvel OT lié.',
      { titre: 'Clôturer administrativement', oui: 'Clôturer et verrouiller' }))) return;
    const reussi = await pendant(bouton, () => changerStatut(actuel.id, actuel.statut, cible, complement), 'changement de statut');
    if (reussi === undefined) return;
    await apresEnregistrement();
    UI.toast(actuel.id + ' : ' + cible + '.', 'succes');
    if (verification.avertissements.length) afficherMessage('attention', verification.avertissements.join(' '));
  }

  // Motif demandé pour En attente et Annulé : { motif_… } ; null si l'utilisateur renonce.
  async function demanderComplement(ot, cible) {
    if (cible === 'En attente') {
      const motif = await UI.demanderMotif('Mettre en attente ' + ot.id, 'Motif de mise en attente', { exemple: 'Ex. pièce en commande, attente de l\'arrêt de la ligne…' });
      return motif === null ? null : { motif_attente: motif };
    }
    if (cible === 'Annulé') {
      const motif = await UI.demanderMotif('Annuler ' + ot.id, 'Motif d\'annulation', { libelleValider: 'Annuler l\'OT' });
      return motif === null ? null : { motif_annulation: motif };
    }
    return {};
  }

  function afficherRefus(ot, cible, verification) {
    const titre = cible === 'Clôturé techniquement'
      ? 'Clôture technique impossible : le statut reste « ' + ot.statut + ' ».'
      : 'Passage à « ' + cible + ' » refusé : le statut reste « ' + ot.statut + ' ».';
    const bandeau = afficherMessage('important', listeErreursHtml(titre, verification.erreurs));
    if (bandeau && verification.piecesManquantes.length && transitionsPossibles(ot).includes('En attente') && actionAutorisee(ot, 'En attente')) {
      bandeau.querySelector('.alerte-texte').appendChild(UI.element(UI.html`<div class="actions">
        <button type="button" class="btn btn-secondaire" data-action="attente-piece">Mettre en attente (motif : pièce)</button></div>`));
    }
  }

  /** RG3 : stock insuffisant → mise en attente avec un motif « Pièce : … » prérempli (modifiable). */
  async function mettreEnAttentePiece(ot) {
    const actuel = Donnees.trouver('ordres_travail', ot.id) || ot;
    const manquantes = piecesManquantes(actuel.id);
    const proposition = 'Pièce : ' + (manquantes.length
      ? manquantes.map((p) => p.libelle + ' (' + UI.nombreFr(p.prevu) + ' prévu(s), ' + UI.nombreFr(p.stock) + ' en stock)').join(' ; ')
      : 'stock insuffisant') + '.';
    const motif = await UI.demanderMotif('Mettre en attente ' + actuel.id, 'Motif de mise en attente', { valeur: proposition });
    if (motif === null) return;
    const reussi = await pendant(null, () => changerStatut(actuel.id, actuel.statut, 'En attente', { motif_attente: motif }), 'mise en attente');
    if (reussi === undefined) return;
    await apresEnregistrement();
    UI.toast(actuel.id + ' : En attente.', 'succes');
  }

  async function demanderPriorite(ot) {
    const contenu = UI.element(UI.html`<div class="form-colonne">
      <p>Priorité actuelle : ${UI.badgePriorite(ot.priorite)}. Le changement est tracé au journal avec son motif.</p>
      <div class="champ"><label class="libelle" for="ot-nouvelle-priorite">Nouvelle priorité</label>
        <select id="ot-nouvelle-priorite">${optionsHtml(PRIORITES.map((p) => ({ valeur: p, libelle: p })), ot.priorite)}</select></div>
      <div class="champ"><label class="libelle" for="ot-motif-priorite">Motif <span class="requis" aria-hidden="true">*</span></label>
        <textarea id="ot-motif-priorite" rows="3" data-dictee required aria-required="true"></textarea>
        <p class="erreur-champ" hidden></p></div></div>`);
    const choix = await UI.fenetre({
      titre: 'Modifier la priorité de ' + ot.id, contenu,
      boutons: [{ libelle: 'Annuler', valeur: null, classe: 'btn-fantome' }, { libelle: 'Enregistrer', valeur: 'ok', classe: 'btn-primaire', defaut: true }],
      avantFermeture() {
        const erreur = UI.$('.erreur-champ', contenu);
        let message = '';
        if (UI.$('#ot-nouvelle-priorite', contenu).value === ot.priorite) message = 'Choisissez une priorité différente de l\'actuelle.';
        else if (!UI.$('#ot-motif-priorite', contenu).value.trim()) message = 'Le motif est obligatoire.';
        erreur.textContent = message;
        erreur.hidden = !message;
        return !message;
      },
    });
    if (choix !== 'ok') return;
    const nouvelle = UI.$('#ot-nouvelle-priorite', contenu).value;
    const motif = UI.$('#ot-motif-priorite', contenu).value.trim();
    const reussi = await pendant(null, () => changerPriorite(ot.id, nouvelle, motif), 'changement de priorité');
    if (reussi === undefined) return;
    await apresEnregistrement();
    UI.toast('Priorité ' + ot.priorite + ' → ' + nouvelle + ' enregistrée.', 'succes');
  }

  async function lancerOtLie(ot) {
    const id = await pendant(UI.$('#ot-lie'), () => creerOtLie(ot.id), 'création d\'un OT lié');
    if (!id) return;
    UI.toast('OT lié ' + id + ' créé (reprise de ' + ot.id + ').', 'succes');
    App.naviguer('#/ot/' + encodeURIComponent(id));
  }

  /** Avertissement RG8 affichable (texte complet, avec le nom du technicien et l'équipement). */
  function bandeauHabilitation(equipementId, technicienId, date) {
    const equipement = Donnees.trouver('equipements', equipementId);
    const jour = texte(date).slice(0, 10) || aujourdhui();
    const manquantes = habilitationsManquantes(equipement, technicienId, jour);
    return UI.bandeau('attention', UI.html`<b>Avertissement habilitation :</b> ${nomTechnicien(technicienId)} (${technicienId})
      n'a pas d'habilitation ${manquantes.join(', ')} valide au ${UI.dateFr(jour)}, exigée pour ${repereEquipement(equipementId)}.
      L'affectation reste possible ; l'avertissement est tracé au journal.`);
  }

  // Panneau d'onglet : zone de titre + contenu en lecture seule ou modifiable.
  function enteteOnglet(titre, explication) {
    return UI.html`<div class="entete-carte"><h2>${titre}</h2>${explication ? UI.html`<span class="aide">${explication}</span>` : ''}</div>`;
  }

  // ===========================================================================================
  // 7. Onglet Préparation (responsable) : travail, technicien (RG8), opérations, pièces (RG3)
  // ===========================================================================================

  function peutPreparer(ot) {
    return estResponsable() && !estVerrouille(ot) && ot.statut !== 'Clôturé techniquement';
  }

  function afficherPreparation(panneau, ot) {
    const modifiable = peutPreparer(ot);
    const boutonsPreparation = boutonsTransitions(ot, ['Préparé', 'Planifié']);
    UI.remplir(panneau, UI.html`
      <form class="carte" id="form-preparation" novalidate>
        ${enteteOnglet('Préparation', modifiable ? '' : 'Lecture seule')}
        <fieldset class="ot-fieldset form-grille"${modifiable ? '' : UI.brut(' disabled')}>
          <div class="large" data-place="travail_a_faire"></div>
          <div class="large" data-place="consignes"></div>
          <div data-place="technicien_id"></div><div data-place="date_prevue"></div>
          <div data-place="temps_prevu_h"></div>
          <div class="large ot-zone-habilitation"></div>
        </fieldset>
        ${modifiable ? UI.html`<div class="actions"><span class="espace"></span><button type="submit" class="btn btn-secondaire">${UI.icone('valider')}Enregistrer la préparation</button></div>` : ''}
      </form>
      <div class="carte" id="ot-bloc-operations"></div>
      <div class="carte" id="ot-bloc-pieces"></div>
      ${modifiable && boutonsPreparation.length ? UI.html`<div class="carte ot-actions-preparation sans-impression">
        <p class="aide">Les saisies non enregistrées de cet onglet sont enregistrées avant le changement de statut.</p>
        <div class="actions">${boutonsPreparation}</div></div>` : ''}`);

    const formulaire = UI.$('#form-preparation', panneau);
    const placer = (nom, element) => placerChamp(formulaire, nom, element);
    placer('travail_a_faire', champOt('travail_a_faire', ot.travail_a_faire));
    placer('consignes', champOt('consignes', ot.consignes));
    placer('technicien_id', champOt('technicien_id', ot.technicien_id, { liste: listeTechniciens(ot.technicien_id) }));
    placer('date_prevue', champOt('date_prevue', ot.date_prevue));
    placer('temps_prevu_h', champOt('temps_prevu_h', ot.temps_prevu_h));
    const montrerHabilitation = () => {
      const valeurs = UI.lireFormulaire(formulaire);
      const zone = UI.$('.ot-zone-habilitation', formulaire);
      zone.textContent = '';
      if (verifierHabilitation(ot.equipement_id, valeurs.technicien_id, valeurs.date_prevue)) {
        zone.appendChild(bandeauHabilitation(ot.equipement_id, valeurs.technicien_id, valeurs.date_prevue));
      }
    };
    montrerHabilitation();
    formulaire.addEventListener('change', montrerHabilitation);
    if (modifiable) {
      const enregistrer = () => enregistrerPreparation(ot, formulaire);
      declarerFormulaire(formulaire, enregistrer);
      formulaire.addEventListener('submit', async (evenement) => {
        evenement.preventDefault();
        const resultat = await enregistrer();
        if (!resultat) return;
        formulaire.dataset.modifie = '0';
        await apresEnregistrement();
        if (typeof resultat === 'string') UI.toast(resultat, 'attention');   // avertissement d'habilitation
        else UI.toast('Préparation enregistrée.', 'succes');
      });
    }
    afficherOperationsPreparation(UI.$('#ot-bloc-operations', panneau), ot, modifiable);
    afficherPieces(UI.$('#ot-bloc-pieces', panneau), ot, modifiable);
  }

  /**
   * Enregistre la préparation ; RG8 : avertissement au journal si le technicien n'est pas habilité.
   * Renvoie false (échec), true (enregistré) ou le texte de l'avertissement d'habilitation (enregistré).
   */
  async function enregistrerPreparation(ot, formulaire) {
    if (UI.verifierFormulaire(formulaire).length) return false;
    const valeurs = UI.lireFormulaire(formulaire);
    const changements = {
      travail_a_faire: valeurs.travail_a_faire, consignes: valeurs.consignes, technicien_id: valeurs.technicien_id,
      date_prevue: valeurs.date_prevue, temps_prevu_h: valeurs.temps_prevu_h,
    };
    const changes = await pendant(UI.$('button[type=submit]', formulaire), () => modifierOt(ot.id, changements, 'préparation'), 'préparation');
    if (changes === undefined) return false;
    const affectation = changes.includes('technicien_id') || changes.includes('date_prevue');
    const habilitation = verifierHabilitation(ot.equipement_id, valeurs.technicien_id, valeurs.date_prevue);
    if (affectation && habilitation) {
      await journaliserHabilitation(ot.id, habilitation);
      return 'Préparation enregistrée. Avertissement habilitation : ' + habilitation + ' (tracé au journal).';
    }
    return true;
  }

  // --- Opérations (ot_operations) : ajoutables et modifiables, jamais supprimées ---

  function afficherOperationsPreparation(bloc, ot, modifiable) {
    const operations = operationsDe(ot.id);
    UI.remplir(bloc, UI.html`
      ${enteteOnglet('Opérations (' + operations.length + ')', 'Une opération n\'est jamais supprimée.')}
      <form id="form-operations" novalidate>
        <fieldset class="ot-fieldset"${modifiable ? '' : UI.brut(' disabled')}>
          <div class="table-defile"><table class="table ot-table-saisie">
            <thead><tr><th scope="col" class="num">N°</th><th scope="col">Opération</th><th scope="col">Valeur attendue</th></tr></thead>
            <tbody>
              ${operations.map((op) => UI.html`<tr data-operation="${op.id}">
                <td class="num" data-libelle="N°">${op.ordre}</td>
                <td data-libelle="Opération"><input type="text" class="ot-op-libelle" value="${op.operation}" aria-label="Opération ${op.ordre}"></td>
                <td data-libelle="Valeur attendue"><input type="text" class="ot-op-attendu" value="${op.valeur_attendue}" aria-label="Valeur attendue ${op.ordre}"></td></tr>`)}
              ${modifiable ? UI.html`<tr class="ot-nouvelle-ligne"><td class="num" data-libelle="N°">+</td>
                <td data-libelle="Nouvelle opération"><input type="text" name="nouvelle_operation" placeholder="Nouvelle opération" aria-label="Nouvelle opération"></td>
                <td data-libelle="Valeur attendue"><input type="text" name="nouvelle_valeur" placeholder="Valeur attendue (facultatif)" aria-label="Valeur attendue de la nouvelle opération"></td></tr>` : ''}
              ${!modifiable && !operations.length ? UI.html`<tr><td colspan="3" class="vide-table">Aucune opération.</td></tr>` : ''}
            </tbody></table></div>
        </fieldset>
        ${modifiable ? UI.html`<div class="actions"><span class="espace"></span><button type="submit" class="btn btn-secondaire">${UI.icone('valider')}Enregistrer les opérations</button></div>` : ''}
      </form>`);
    if (!modifiable) return;
    const formulaire = UI.$('#form-operations', bloc);
    const enregistrer = () => enregistrerOperations(ot, formulaire);
    declarerFormulaire(formulaire, enregistrer);
    formulaire.addEventListener('submit', async (evenement) => {
      evenement.preventDefault();
      if (await enregistrer()) { formulaire.dataset.modifie = '0'; await apresEnregistrement(); UI.toast('Opérations enregistrées.', 'succes'); }
    });
  }

  async function enregistrerOperations(ot, formulaire) {
    const modifiees = UI.$$('tr[data-operation]', formulaire).map((rangee) => ({
      id: rangee.dataset.operation,
      operation: UI.$('.ot-op-libelle', rangee).value.trim(),
      valeur_attendue: UI.$('.ot-op-attendu', rangee).value.trim(),
    }));
    if (modifiees.some((op) => !op.operation)) {
      UI.toast('Une opération ne peut pas être vidée (elle n\'est jamais supprimée) : corrigez son texte.', 'attention');
      return false;
    }
    const nouvelle = { operation: (UI.$('[name="nouvelle_operation"]', formulaire) || {}).value || '', valeur_attendue: (UI.$('[name="nouvelle_valeur"]', formulaire) || {}).value || '' };
    const resultat = await pendant(UI.$('button[type=submit]', formulaire), () => Donnees.modifier('ot_operations', (lignes, outils) => {
      verifierOtModifiable(ot.id);
      modifiees.forEach((op) => {
        const ligne = lignes.find((l) => l.id === op.id && l.ot_id === ot.id);
        if (ligne) { ligne.operation = op.operation; ligne.valeur_attendue = op.valeur_attendue; }
      });
      if (nouvelle.operation.trim()) {
        const ordreMax = lignes.filter((l) => l.ot_id === ot.id).reduce((max, l) => Math.max(max, nombre(l.ordre)), 0);
        lignes.push({ id: outils.nouvelId(lignes), ot_id: ot.id, ordre: String(ordreMax + 1), operation: nouvelle.operation.trim(),
          valeur_attendue: nouvelle.valeur_attendue.trim(), fait: '0', valeur_mesuree: '' });
      }
      return true;
    }, { action: 'opérations de ' + ot.id }), 'opérations');
    return resultat === true;
  }

  // Refus d'écrire dans une table liée si l'OT est verrouillé (relu dans le cache à jour).
  function verifierOtModifiable(otId) {
    const ot = Donnees.trouver('ordres_travail', otId);
    if (!ot) throw ErreurValidation('L\'ordre de travail ' + otId + ' est introuvable.');
    if (estVerrouille(ot)) throw ErreurValidation('L\'OT ' + otId + ' est « ' + ot.statut + ' » : il ne peut plus être modifié.');
  }

  // --- Pièces prévues (ot_pieces) : stock disponible, alerte si insuffisant ; quantité 0 = retirée ---

  function optionsArticles(ot) {
    const liees = new Set(Donnees.lignes('article_equipement').filter((l) => l.equipement_id === ot.equipement_id).map((l) => l.article_id));
    const actifs = Donnees.lignes('articles').filter((a) => a.actif !== '0')
      .sort((a, b) => libelleArticle(a).localeCompare(libelleArticle(b), 'fr'));
    const option = (a) => UI.html`<option value="${a.id}">${libelleArticle(a)} — stock ${UI.nombreFr(Donnees.stockArticle(a.id))}</option>`;
    const pourEquipement = actifs.filter((a) => liees.has(a.id));
    return UI.html`<option value="">— Choisir un article —</option>
      ${pourEquipement.length ? UI.html`<optgroup label="Pièces de cet équipement">${pourEquipement.map(option)}</optgroup>` : ''}
      <optgroup label="Tout le magasin">${actifs.filter((a) => !liees.has(a.id)).map(option)}</optgroup>`;
  }

  /** Quantité du fichier ('1.5') → texte de saisie ('1,5') ; vide → '0'. */
  function quantiteSaisie(valeur) {
    return texte(valeur) === '' ? '0' : texte(valeur).replace('.', ',');
  }

  function afficherPieces(bloc, ot, modifiable) {
    const pieces = lignesDeLOt('ot_pieces', ot.id);
    const cumul = quantitesPrevues(ot.id);
    const manquantes = piecesManquantes(ot.id);
    UI.remplir(bloc, UI.html`
      ${enteteOnglet('Pièces prévues', 'Quantité 0 = pièce retirée (jamais supprimée).')}
      <form id="form-pieces" novalidate>
        <fieldset class="ot-fieldset"${modifiable ? '' : UI.brut(' disabled')}>
          <div class="table-defile"><table class="table ot-table-saisie">
            <thead><tr><th scope="col">Article</th><th scope="col">Emplacement</th><th scope="col" class="num">Prévu</th><th scope="col" class="num">En stock</th><th scope="col">État</th></tr></thead>
            <tbody>
              ${pieces.map((piece) => {
                const article = Donnees.trouver('articles', piece.article_id);
                const stock = Donnees.stockArticle(piece.article_id);
                const retiree = nombre(piece.quantite_prevue) === 0;
                const insuffisant = !retiree && stock < (cumul.get(piece.article_id) || 0);
                return UI.html`<tr data-piece="${piece.id}"${retiree ? UI.brut(' class="attenue"') : ''}>
                  <td data-libelle="Article">${libelleArticle(article) || piece.article_id}</td><td data-libelle="Emplacement">${article ? article.emplacement : ''}</td>
                  <td class="num" data-libelle="Prévu"><input type="text" inputmode="decimal" class="ot-quantite" value="${quantiteSaisie(piece.quantite_prevue)}" aria-label="Quantité prévue de ${libelleArticle(article)}"></td>
                  <td class="num" data-libelle="En stock">${UI.nombreFr(stock)}</td>
                  <td data-libelle="État">${retiree ? UI.html`<span class="badge neutre">retirée</span>` : insuffisant ? UI.html`<span class="badge ko">stock insuffisant</span>` : UI.html`<span class="badge ok">disponible</span>`}</td></tr>`;
              })}
              ${!pieces.length && !modifiable ? UI.html`<tr><td colspan="5" class="vide-table">Aucune pièce prévue.</td></tr>` : ''}
            </tbody></table></div>
          ${modifiable ? UI.html`<div class="form-ligne ot-ajout-piece">
            <div class="champ"><label class="libelle" for="ot-nouvel-article">Ajouter une pièce</label><select id="ot-nouvel-article" name="nouvel_article">${optionsArticles(ot)}</select></div>
            <div class="champ ot-champ-quantite"><label class="libelle" for="ot-nouvelle-quantite">Quantité</label><input type="text" inputmode="decimal" id="ot-nouvelle-quantite" name="nouvelle_quantite" value="1"></div>
          </div>` : ''}
        </fieldset>
        ${modifiable ? UI.html`<div class="actions"><span class="espace"></span><button type="submit" class="btn btn-secondaire">${UI.icone('valider')}Enregistrer les pièces</button></div>` : ''}
      </form>`);
    if (manquantes.length) {
      bloc.insertBefore(UI.bandeau('important', listeErreursHtml('Stock insuffisant : l\'OT ne pourra pas être planifié.',
        manquantes.map((p) => p.libelle + ' : ' + UI.nombreFr(p.prevu) + ' prévu(s), ' + UI.nombreFr(p.stock) + ' en stock'))), UI.$('#form-pieces', bloc));
    }
    if (!modifiable) return;
    const formulaire = UI.$('#form-pieces', bloc);
    const enregistrer = () => enregistrerPieces(ot, formulaire);
    declarerFormulaire(formulaire, enregistrer);
    formulaire.addEventListener('submit', async (evenement) => {
      evenement.preventDefault();
      if (await enregistrer()) { formulaire.dataset.modifie = '0'; await apresEnregistrement(); UI.toast('Pièces prévues enregistrées.', 'succes'); }
    });
  }

  async function enregistrerPieces(ot, formulaire) {
    const quantites = UI.$$('tr[data-piece]', formulaire).map((rangee) => ({ id: rangee.dataset.piece, quantite: UI.enNombre(UI.$('.ot-quantite', rangee).value) }));
    const article = UI.$('[name="nouvel_article"]', formulaire).value;
    const quantiteNouvelle = UI.enNombre(UI.$('[name="nouvelle_quantite"]', formulaire).value);
    if (quantites.some((q) => q.quantite === null || q.quantite < 0) || (article && (quantiteNouvelle === null || quantiteNouvelle <= 0))) {
      UI.toast('Quantités : saisissez des nombres positifs (0 pour retirer une pièce).', 'attention');
      return false;
    }
    const resultat = await pendant(UI.$('button[type=submit]', formulaire), () => Donnees.modifier('ot_pieces', (lignes, outils) => {
      verifierOtModifiable(ot.id);
      quantites.forEach((q) => {
        const ligne = lignes.find((l) => l.id === q.id && l.ot_id === ot.id);
        if (ligne && nombre(ligne.quantite_prevue) !== q.quantite) ligne.quantite_prevue = String(q.quantite);
      });
      if (article) {
        const existante = lignes.find((l) => l.ot_id === ot.id && l.article_id === article);
        if (existante) existante.quantite_prevue = String(arrondi(nombre(existante.quantite_prevue) + quantiteNouvelle, 3));
        else lignes.push({ id: outils.nouvelId(lignes), ot_id: ot.id, article_id: article, quantite_prevue: String(quantiteNouvelle) });
      }
      return true;
    }, { action: 'pièces prévues de ' + ot.id }), 'pièces prévues');
    return resultat === true;
  }

  // ===========================================================================================
  // 8. Onglet Exécution : démarrer, check-list, temps passés, arrêt, sous-traitance, date de fin
  // ===========================================================================================

  function peutExecuter(ot) {
    return (estTechnicien() || estResponsable()) && ['En cours', 'En attente'].includes(ot.statut);
  }

  function afficherExecution(panneau, ot) {
    const modifiable = peutExecuter(ot);
    const operations = operationsDe(ot.id);
    const demarrage = boutonsTransitions(ot, ['En cours']);
    UI.remplir(panneau, UI.html`
      ${demarrage.length && ot.statut !== 'Clôturé techniquement' ? UI.html`<div class="carte ot-demarrer sans-impression">
        <p>${ot.statut === 'En attente' ? 'L\'OT est en attente : reprenez-le quand la cause est levée.' : 'L\'intervention n\'a pas commencé. « Démarrer » inscrit l\'heure de début.'}</p>
        <div class="actions">${demarrage}</div></div>` : ''}
      <form class="carte" id="form-execution" novalidate>
        ${enteteOnglet('Exécution', modifiable ? '' : (ot.statut === 'Créé' || ot.statut === 'Préparé' || ot.statut === 'Planifié' ? 'Disponible une fois l\'OT démarré' : 'Lecture seule'))}
        <fieldset class="ot-fieldset"${modifiable ? '' : UI.brut(' disabled')}>
          <h3 class="ot-sous-titre">Check-list</h3>
          ${operations.length ? UI.html`<ul class="check-liste">${operations.map((op) => UI.html`
            <li data-operation="${op.id}"${op.fait === '1' ? UI.brut(' class="fait"') : ''}>
              <label class="case"><input type="checkbox" class="ot-fait"${op.fait === '1' ? UI.brut(' checked') : ''}>
                <span><span class="operation">${op.ordre}. ${op.operation}</span>${op.valeur_attendue ? UI.html`<span class="attendu">Attendu : ${op.valeur_attendue}</span>` : ''}</span></label>
              <input type="text" class="mesure ot-mesure" value="${op.valeur_mesuree}" placeholder="Valeur mesurée" aria-label="Valeur mesurée pour l'opération ${op.ordre}">
            </li>`)}</ul>` : UI.html`<p class="muted">Aucune opération prévue (onglet Préparation).</p>`}
          <h3 class="ot-sous-titre">Déroulement</h3>
          <div class="form-grille">
            <div class="champ ot-champ-lu"><span class="libelle">Début</span><p class="ot-valeur">${UI.dateHeureFr(ot.date_debut) || '—'}</p></div>
            <div class="ot-date-fin" data-place="date_fin"></div>
            <div data-place="arret_production"></div><div data-place="duree_arret_h"></div>
            <div data-place="cout_soustraitance"></div>
          </div>
        </fieldset>
        ${modifiable ? UI.html`<div class="actions"><span class="espace"></span><button type="submit" class="btn btn-secondaire">${UI.icone('valider')}Enregistrer l'exécution</button></div>` : ''}
      </form>
      <div class="carte" id="ot-bloc-temps"></div>`);
    const formulaire = UI.$('#form-execution', panneau);
    const placer = (nom, element) => placerChamp(formulaire, nom, element);
    placer('date_fin', champOt('date_fin', ot.date_fin));
    placer('arret_production', champOt('arret_production', ot.arret_production, { libelle: 'Arrêt de production pendant l\'intervention' }));
    placer('duree_arret_h', champOt('duree_arret_h', ot.duree_arret_h));
    placer('cout_soustraitance', champOt('cout_soustraitance', ot.cout_soustraitance, { libelle: 'Coût de sous-traitance (€)' }));
    if (modifiable) {
      const blocDateFin = UI.$('[data-champ="date_fin"]', formulaire);
      const maintenant = UI.element(UI.html`<button type="button" class="lien-bouton ot-maintenant">Maintenant</button>`);
      maintenant.addEventListener('click', () => {
        UI.$('[name="date_fin"]', blocDateFin).value = Donnees.maintenant().replace(' ', 'T');
        formulaire.dataset.modifie = '1';
        App.marquerSaisie(true);
      });
      UI.$('.libelle', blocDateFin).appendChild(maintenant);
      const enregistrer = () => enregistrerExecution(ot, formulaire);
      declarerFormulaire(formulaire, enregistrer);
      formulaire.addEventListener('submit', async (evenement) => {
        evenement.preventDefault();
        if (await enregistrer()) { formulaire.dataset.modifie = '0'; await apresEnregistrement(); UI.toast('Exécution enregistrée.', 'succes'); }
      });
    }
    afficherTemps(UI.$('#ot-bloc-temps', panneau), ot, modifiable);
  }

  async function enregistrerExecution(ot, formulaire) {
    if (UI.verifierFormulaire(formulaire).length) return false;
    const valeurs = UI.lireFormulaire(formulaire);
    const checkListe = UI.$$('li[data-operation]', formulaire).map((li) => ({
      id: li.dataset.operation, fait: UI.$('.ot-fait', li).checked ? '1' : '0', valeur_mesuree: UI.$('.ot-mesure', li).value.trim(),
    }));
    const bouton = UI.$('button[type=submit]', formulaire);
    const changes = await pendant(bouton, () => modifierOt(ot.id, {
      date_fin: valeurs.date_fin, arret_production: valeurs.arret_production,
      duree_arret_h: valeurs.duree_arret_h, cout_soustraitance: valeurs.cout_soustraitance,
    }, 'exécution'), 'exécution');
    if (changes === undefined) return false;
    if (!checkListe.length) return true;
    const resultat = await pendant(bouton, () => Donnees.modifier('ot_operations', (lignes) => {
      verifierOtModifiable(ot.id);
      checkListe.forEach((op) => {
        const ligne = lignes.find((l) => l.id === op.id && l.ot_id === ot.id);
        if (ligne) { ligne.fait = op.fait; ligne.valeur_mesuree = op.valeur_mesuree; }
      });
      return true;
    }, { action: 'check-list de ' + ot.id }), 'check-list');
    return resultat === true;
  }

  // --- Temps passés (ot_temps) : par technicien et par date ---

  function afficherTemps(bloc, ot, modifiable) {
    const temps = lignesDeLOt('ot_temps', ot.id).slice().sort((a, b) => texte(a.date).localeCompare(texte(b.date)) || a.id.localeCompare(b.id));
    const total = temps.reduce((somme, ligne) => somme + nombre(ligne.heures), 0);
    const technicienParDefaut = (estTechnicien() && monTechnicienId()) || ot.technicien_id || '';
    UI.remplir(bloc, UI.html`
      ${enteteOnglet('Temps passés', 'Total : ' + UI.heures(total))}
      <div class="table-defile"><table class="table">
        <thead><tr><th scope="col">Date</th><th scope="col">Technicien</th><th scope="col" class="num">Heures</th></tr></thead>
        <tbody>${temps.length ? temps.map((ligne) => UI.html`<tr><td>${UI.dateFr(ligne.date)}</td><td>${nomTechnicien(ligne.technicien_id)}</td><td class="num">${UI.heures(ligne.heures)}</td></tr>`)
          : UI.html`<tr><td colspan="3" class="vide-table">Aucun temps saisi.</td></tr>`}</tbody>
      </table></div>
      ${modifiable ? UI.html`<form class="form-ligne ot-ajout-temps" id="form-temps" novalidate>
        <div class="champ"><label class="libelle" for="ot-temps-technicien">Technicien</label>
          <select id="ot-temps-technicien" name="technicien_id">${optionsHtml(listeTechniciens(technicienParDefaut), technicienParDefaut)}</select></div>
        <div class="champ"><label class="libelle" for="ot-temps-date">Date</label><input type="date" id="ot-temps-date" name="date" value="${aujourdhui()}"></div>
        <div class="champ ot-champ-quantite"><label class="libelle" for="ot-temps-heures">Heures</label><input type="text" inputmode="decimal" id="ot-temps-heures" name="heures" placeholder="1,5"></div>
        <button type="submit" class="btn btn-secondaire">${UI.icone('ajouter')}Ajouter le temps</button>
      </form>` : ''}`);
    if (!modifiable) return;
    const formulaire = UI.$('#form-temps', bloc);
    // Avant une transition, un temps saisi mais pas encore ajouté est ajouté ; un champ vide est ignoré.
    declarerFormulaire(formulaire, () => ajouterTemps(ot, formulaire, false));
    formulaire.addEventListener('submit', async (evenement) => {
      evenement.preventDefault();
      if (await ajouterTemps(ot, formulaire, true)) { formulaire.dataset.modifie = '0'; await apresEnregistrement(); UI.toast('Temps ajouté.', 'succes'); }
    });
  }

  async function ajouterTemps(ot, formulaire, depuisLeBouton) {
    const valeurs = UI.lireFormulaire(formulaire);
    const heures = UI.enNombre(valeurs.heures);
    if (!valeurs.heures && !depuisLeBouton) return true;   // rien à ajouter
    if (heures === null || heures <= 0 || heures > 24 || !valeurs.date || !valeurs.technicien_id) {
      UI.toast('Temps passé : choisissez le technicien, la date et un nombre d\'heures entre 0 et 24 (ex. 1,5).', 'attention');
      return false;
    }
    const resultat = await pendant(UI.$('button[type=submit]', formulaire), () => Donnees.modifier('ot_temps', (lignes, outils) => {
      verifierOtModifiable(ot.id);
      lignes.push({ id: outils.nouvelId(lignes), ot_id: ot.id, technicien_id: valeurs.technicien_id, date: valeurs.date, heures: String(heures) });
      return true;
    }, { action: 'temps passé sur ' + ot.id }), 'temps passé');
    return resultat === true;
  }

  // ===========================================================================================
  // 9. Onglet Compte rendu : codes, compte rendu, remise en service, clôture technique, coût RG7
  // ===========================================================================================

  function afficherCompteRendu(panneau, ot) {
    const modifiable = peutExecuter(ot);
    const equipement = equipementDe(ot);
    UI.remplir(panneau, UI.html`
      <form class="carte" id="form-compte-rendu" novalidate>
        ${enteteOnglet('Compte rendu', modifiable ? '' : 'Lecture seule')}
        <fieldset class="ot-fieldset form-grille"${modifiable ? '' : UI.brut(' disabled')}>
          <div data-place="symptome_code"></div><div data-place="cause_code"></div><div data-place="remede_code"></div><div></div>
          <div class="large" data-place="compte_rendu"></div>
          <div class="large ot-remise" data-place="remise_service"></div>
        </fieldset>
        ${modifiable ? UI.html`<div class="actions"><button type="submit" class="btn btn-secondaire">${UI.icone('valider')}Enregistrer le compte rendu</button>
          <span class="espace"></span>${boutonsTransitions(ot, ['Clôturé techniquement'])}</div>` : ''}
      </form>
      <div class="carte ot-cout" id="ot-cout"></div>`);
    const formulaire = UI.$('#form-compte-rendu', panneau);
    const placer = (nom, element) => placerChamp(formulaire, nom, element);
    placer('symptome_code', champOt('symptome_code', ot.symptome_code, { liste: listeCodes('symptôme') }));
    placer('cause_code', champOt('cause_code', ot.cause_code, { liste: listeCodes('cause') }));
    placer('remede_code', champOt('remede_code', ot.remede_code, { liste: listeCodes('remède') }));
    placer('compte_rendu', champOt('compte_rendu', ot.compte_rendu, {
      aide: 'Ce qui a été constaté, la cause, ce qui a été fait (10 caractères au moins ; « RAS » refusé sur un correctif).',
    }));
    placer('remise_service', champOt('remise_service', ot.remise_service, {
      libelle: 'Équipement remis en service en sécurité (protections remises, consignation levée, production prévenue)',
    }));
    if (equipement && texte(equipement.habilitation_requise)) {
      UI.$('.ot-remise', formulaire).appendChild(UI.element(UI.html`<p class="aide">${RAPPEL_CONSIGNATION}</p>`));
    }
    if (modifiable) {
      const enregistrer = () => enregistrerCompteRendu(ot, formulaire);
      declarerFormulaire(formulaire, enregistrer);
      formulaire.addEventListener('submit', async (evenement) => {
        evenement.preventDefault();
        if (await enregistrer()) { formulaire.dataset.modifie = '0'; await apresEnregistrement(); UI.toast('Compte rendu enregistré.', 'succes'); }
      });
    }
    afficherCout(UI.$('#ot-cout', panneau), ot);
  }

  async function enregistrerCompteRendu(ot, formulaire) {
    const valeurs = UI.lireFormulaire(formulaire);
    const changes = await pendant(UI.$('button[type=submit]', formulaire), () => modifierOt(ot.id, {
      symptome_code: valeurs.symptome_code, cause_code: valeurs.cause_code, remede_code: valeurs.remede_code,
      compte_rendu: valeurs.compte_rendu, remise_service: valeurs.remise_service,
    }, 'compte rendu'), 'compte rendu');
    return changes !== undefined;
  }

  function afficherCout(bloc, ot) {
    const resultat = cout(ot);
    const detail = resultat.detail;
    UI.remplir(bloc, UI.html`
      ${enteteOnglet('Coût de l\'intervention', 'RG7 : main-d\'œuvre + pièces sorties − retours + sous-traitance')}
      <div class="lignes ot-lignes-cout">
        <span>Main-d'œuvre (${UI.heures(detail.nombreHeures)})</span><b>${UI.euro(resultat.heures)}</b>
        <span>Pièces sorties pour l'OT</span><b>${UI.euro(resultat.pieces)}</b>
        <span>Sous-traitance</span><b>${UI.euro(resultat.soustraitance)}</b>
        <span class="total">Total</span><b class="total" id="ot-cout-total">${UI.euro(resultat.total)}</b>
      </div>
      <details class="vue-tableau ot-detail-cout"><summary>Voir le détail</summary>
        <div class="table-defile"><table class="table">
          <thead><tr><th scope="col">Poste</th><th scope="col">Détail</th><th scope="col" class="num">Montant</th></tr></thead>
          <tbody>
            ${detail.temps.map((t) => UI.html`<tr><td>${nomTechnicien(t.technicien_id)}</td><td>${UI.dateFr(t.date)} · ${UI.heures(t.heures)} × ${UI.euro(t.taux)}/h</td><td class="num">${UI.euro(t.montant)}</td></tr>`)}
            ${detail.pieces.map((p) => UI.html`<tr><td>${p.libelle}</td><td>${UI.nombreFr(p.sorties)} sortie(s)${p.retours ? UI.html` − ${UI.nombreFr(p.retours)} retour(s)` : ''} × ${UI.euro(p.prix)}</td><td class="num">${UI.euro(p.montant)}</td></tr>`)}
            ${resultat.soustraitance ? UI.html`<tr><td>Sous-traitance</td><td></td><td class="num">${UI.euro(resultat.soustraitance)}</td></tr>` : ''}
            ${!detail.temps.length && !detail.pieces.length && !resultat.soustraitance ? UI.html`<tr><td colspan="3" class="vide-table">Aucun coût pour l'instant.</td></tr>` : ''}
          </tbody></table></div>
        <p class="note">Les sorties de pièces imputées à l'OT se saisissent au magasin (lot 2) ; les quantités prévues ne sont pas comptées.</p>
      </details>`);
  }

  // ===========================================================================================
  // 10. Onglet Historique équipement : autres OT et DI du même équipement
  // ===========================================================================================

  /**
   * Sur téléphone, un tableau « empilé » montre une carte par ligne : chaque cellule reçoit le
   * libellé de sa colonne (data-libelle, affiché par css/modules/ordres.css).
   */
  function etiqueterCellules(table) {
    table.classList.add('ot-table-empilee');
    const libelles = UI.$$('thead th', table).map((th) => th.textContent.trim());
    UI.$$('tbody tr', table).forEach((rangee) => {
      Array.from(rangee.cells).forEach((cellule, rang) => {
        if (libelles[rang] && cellule.colSpan === 1) cellule.dataset.libelle = libelles[rang];
      });
    });
  }

  function afficherHistorique(panneau, ot) {
    const autres = Donnees.lignes('ordres_travail').filter((autre) => autre.equipement_id === ot.equipement_id && autre.id !== ot.id);
    const demandes = Donnees.lignes('demandes').filter((di) => di.equipement_id === ot.equipement_id);
    const blocOt = UI.element(UI.html`<section class="carte"><div class="entete-carte"><h2>Autres ordres de travail (${autres.length})</h2></div></section>`);
    blocOt.appendChild(UI.tableau({
      colonnes: [
        { cle: 'id', libelle: 'N°', rendu: (l) => lienOt(l.id) },
        { cle: 'date_creation', libelle: 'Créé le', rendu: (l) => UI.dateFr(l.date_creation) },
        { cle: 'priorite', libelle: 'Priorité', rendu: (l) => UI.badgePriorite(l.priorite) },
        { cle: 'statut', libelle: 'Statut', rendu: (l) => UI.badgeStatut(l.statut) },
        { cle: 'type', libelle: 'Type' },
        { cle: 'titre', libelle: 'Titre' },
      ],
      lignes: autres, triInitial: { cle: 'date_creation', sens: 'desc' }, libelle: 'Autres OT de l\'équipement',
      vide: 'Aucun autre OT sur cet équipement.', surClic: (l) => App.naviguer('#/ot/' + encodeURIComponent(l.id)),
    }));
    const blocDi = UI.element(UI.html`<section class="carte"><div class="entete-carte"><h2>Demandes d'intervention (${demandes.length})</h2></div></section>`);
    blocDi.appendChild(UI.tableau({
      colonnes: [
        { cle: 'id', libelle: 'N°', rendu: (l) => UI.html`<a href="#/di/${encodeURIComponent(l.id)}">${l.id}</a>` },
        { cle: 'date_heure', libelle: 'Date', rendu: (l) => UI.dateFr(l.date_heure) },
        { cle: 'symptome', libelle: 'Symptôme' },
        { cle: 'impact', libelle: 'Impact' },
        { cle: 'statut', libelle: 'Statut', rendu: (l) => UI.badgeStatut(l.statut) },
        { cle: 'ot_id', libelle: 'OT', rendu: (l) => (l.ot_id ? lienOt(l.ot_id) : '') },
      ],
      lignes: demandes, triInitial: { cle: 'date_heure', sens: 'desc' }, libelle: 'Demandes de l\'équipement',
      vide: 'Aucune demande sur cet équipement.', surClic: (l) => App.naviguer('#/di/' + encodeURIComponent(l.id)),
    }));
    UI.remplir(panneau, [blocOt, blocDi]);
    UI.$$('.table', panneau).forEach(etiqueterCellules);
  }

  // ===========================================================================================
  // 11. Bon de travail (impression A4 dans #impression, puis window.print())
  // ===========================================================================================

  function lignesVides(nombreLignes) {
    return UI.brut(new Array(nombreLignes).fill('<span></span>').join(''));
  }

  function qrBon(equipement) {
    if (!equipement) return '';
    try {
      return UI.html`${UI.qrSvg(App.urlFicheEquipement(equipement.id), 100)}<span>${equipement.repere || equipement.id}</span>`;
    } catch (erreur) {
      console.warn('Prévo : QR du bon de travail impossible (' + (erreur && erreur.message) + ').', erreur);
      return UI.html`<span>${equipement.repere || equipement.id}</span>`;
    }
  }

  /** HTML du bon de travail d'un OT (structure .bon-travail de css/style.css §14). */
  function bonDeTravailHtml(ot) {
    const equipement = equipementDe(ot) || {};
    const operations = operationsDe(ot.id);
    const pieces = lignesDeLOt('ot_pieces', ot.id).filter((p) => nombre(p.quantite_prevue) > 0);
    const di = ot.di_id ? Donnees.trouver('demandes', ot.di_id) : null;
    const entreprise = Donnees.parametre('entreprise_nom', '');
    const maintenant = Donnees.maintenant();
    return UI.html`<article class="bon-travail">
      <header class="bt-entete">
        <div>
          <div class="bt-entreprise">${entreprise ? entreprise + ' — ' : ''}Prévo</div>
          <h1>Bon de travail</h1>
          <div class="bt-numero">${ot.id} <span class="bt-priorite">${ot.priorite}</span></div>
          <div class="bt-meta"><span>Type : <b>${ot.type}</b></span><span>Statut : <b>${ot.statut}</b></span>
            <span>Prévu le : <b>${UI.dateFr(ot.date_prevue) || '—'}</b></span><span>Technicien : <b>${nomTechnicien(ot.technicien_id) || '—'}</b></span>
            <span>Temps prévu : <b>${ot.temps_prevu_h ? UI.heures(ot.temps_prevu_h) : '—'}</b></span></div>
        </div>
        <div class="bt-qr">${qrBon(equipementDe(ot))}</div>
      </header>
      <div class="bt-colonnes">
        <section class="bt-equipement"><h2>Équipement</h2>
          <dl class="valeurs"><dt>Repère</dt><dd>${equipement.repere || ot.equipement_id}</dd><dt>Désignation</dt><dd>${equipement.designation || ''}</dd>
            <dt>Localisation</dt><dd>${cheminLocalisation(equipement.localisation_id)}</dd><dt>Criticité</dt><dd>${equipement.criticite || ''}</dd>
            <dt>Habilitation</dt><dd>${equipement.habilitation_requise || 'aucune'}</dd></dl>
        </section>
        <section class="bt-travail"><h2>Travail à faire</h2>
          <p class="bt-texte">${ot.titre}</p>
          ${ot.travail_a_faire ? UI.html`<p class="bt-texte">${ot.travail_a_faire}</p>` : ''}
          ${ot.consignes ? UI.html`<p class="bt-texte"><b>Consignes :</b> ${ot.consignes}</p>` : ''}
          ${di ? UI.html`<p><b>Demande :</b> ${di.id} — ${texte(di.symptome).replace(/[.\s]+$/, '')}${di.impact ? ' (impact : ' + di.impact + ')' : ''}</p>` : ''}
        </section>
      </div>
      <section class="bt-consignation"><h2>Consignation</h2>
        <p class="bt-texte">${texte(equipement.consignation) || 'Aucune procédure renseignée : voir le responsable avant d\'intervenir.'}</p>
        <p class="bt-rappel">${RAPPEL_CONSIGNATION}</p>
        <div class="bt-case"><span class="bt-coche"></span>Consignation appliquée par : ______________________</div>
      </section>
      <section class="bt-operations"><h2>Opérations</h2>
        <table class="bt-table"><thead><tr><th class="bt-etroit">N°</th><th>Opération</th><th>Valeur attendue</th><th>Mesure</th><th class="bt-etroit">Fait</th></tr></thead>
          <tbody>${operations.length ? operations.map((op) => UI.html`<tr><td class="bt-etroit">${op.ordre}</td><td>${op.operation}</td><td>${op.valeur_attendue}</td><td class="bt-a-remplir"></td><td class="bt-etroit"><span class="bt-coche"></span></td></tr>`)
            : UI.brut(new Array(3).fill('<tr><td class="bt-etroit"></td><td class="bt-a-remplir"></td><td></td><td></td><td class="bt-etroit"><span class="bt-coche"></span></td></tr>').join(''))}</tbody></table>
      </section>
      <section class="bt-pieces"><h2>Pièces</h2>
        <table class="bt-table"><thead><tr><th>Référence</th><th>Désignation</th><th>Emplacement</th><th class="bt-etroit">Prévu</th><th class="bt-etroit">Utilisé</th></tr></thead>
          <tbody>${pieces.map((p) => {
            const article = Donnees.trouver('articles', p.article_id) || {};
            return UI.html`<tr><td>${article.reference || p.article_id}</td><td>${article.designation || ''}</td><td>${article.emplacement || ''}</td><td class="bt-etroit">${UI.nombreFr(p.quantite_prevue)}</td><td class="bt-a-remplir"></td></tr>`;
          })}${UI.brut('<tr><td class="bt-a-remplir"></td><td></td><td></td><td></td><td></td></tr>')}</tbody></table>
      </section>
      <section class="bt-temps"><h2>Temps passés</h2>
        <table class="bt-table"><thead><tr><th>Date</th><th>Technicien</th><th class="bt-etroit">Heures</th></tr></thead>
          <tbody>${UI.brut(new Array(3).fill('<tr><td class="bt-a-remplir"></td><td></td><td></td></tr>').join(''))}</tbody></table>
      </section>
      <section class="bt-compte-rendu"><h2>Compte rendu</h2>
        <p>Cause : ________ Remède : ________ Arrêt de production : ☐ oui ☐ non — durée : ______ h</p>
        <div class="bt-lignes">${lignesVides(4)}</div>
        <div class="bt-case"><span class="bt-coche"></span>Équipement remis en service en sécurité</div>
      </section>
      <section class="bt-signatures">
        <div class="bt-signature"><b>Technicien</b>Nom, date et signature</div>
        <div class="bt-signature"><b>Production (remise en service)</b>Nom, date et signature</div>
        <div class="bt-signature"><b>Responsable maintenance</b>Nom, date et signature</div>
      </section>
      <footer class="bt-pied"><span>Prévo — bon imprimé le ${UI.dateHeureFr(maintenant).replace(' ', ' à ')}</span><span>${ot.id}</span></footer>
    </article>`;
  }

  /** Remplit #impression avec le bon de travail puis lance l'impression ; vidé après impression. */
  function imprimerBon(otId) {
    const ot = Donnees.trouver('ordres_travail', otId);
    const zone = document.getElementById('impression');
    if (!ot || !zone) return;
    UI.remplir(zone, bonDeTravailHtml(ot));
    window.addEventListener('afterprint', () => { zone.textContent = ''; }, { once: true });
    window.print();
  }

  // ===========================================================================================
  // 12. Enregistrement des écrans (App est chargé après les modules)
  // ===========================================================================================

  document.addEventListener('DOMContentLoaded', () => {
    const tablesFiche = ['ordres_travail', 'ot_operations', 'ot_pieces', 'ot_temps', 'equipements', 'techniciens',
      'habilitations', 'articles', 'mouvements_stock', 'demandes', 'codes_defaillance'];
    App.ecran({
      id: 'liste-ot', route: /^#\/ot$/, titre: 'Ordres de travail',
      menu: { libelle: 'Ordres de travail', court: 'Ordres', icone: 'ordres', ordre: 30 },
      profils: ['technicien', 'responsable'], tables: ['ordres_travail', 'equipements', 'techniciens'],
      afficher: afficherListe,
    });
    // « #/ot/nouveau » avant « #/ot/<id> » : la première route qui correspond gagne.
    App.ecran({
      id: 'nouvel-ot', route: /^#\/ot\/nouveau$/, titre: 'Nouvel OT', parent: 'liste-ot',
      profils: ['responsable'], tables: [],
      afficher: afficherNouveau,
    });
    App.ecran({
      id: 'fiche-ot', route: /^#\/ot\/(?<id>[^/?]+)$/, titre: 'Ordre de travail', parent: 'liste-ot',
      profils: ['technicien', 'responsable'], tables: tablesFiche,
      afficher: afficherFiche,
    });
  });

  return {
    STATUTS, TYPES, PRIORITES, RAPPEL_CONSIGNATION,
    // règles pures (ARCHITECTURE.md §10)
    transitionsPossibles, verifierPassage, verifierCloture, cout, verifierHabilitation, estOuvert, enRetard,
    estVerrouille, estCorrectif, estRienASignaler, piecesManquantes, filtrer, datePrevueParDefaut,
    // écritures
    creer, changerStatut, changerPriorite, creerOtLie,
    // affichage et export
    libelleEquipement, nomTechnicien, csvListe, bonDeTravailHtml, imprimerBon,
  };
})();
