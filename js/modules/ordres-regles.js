'use strict';
// Ordres : module « Ordres de travail » (OT) de Prévo — écrans E4 (liste) et E5 (fiche),
// création manuelle ou d'urgence, règles RG3 (statuts), RG4 (clôture), RG7 (coût), RG8
// (habilitations) et impression du bon de travail A4 (ARCHITECTURE.md §10, brief §7 et §9).
//
// Le module est découpé en sept fichiers, chargés dans cet ordre par index.html (ARCHITECTURE.md
// §14.2, décision D28 : 700 lignes au plus par fichier). Une section = un sujet ; chaque fonction
// fait une seule chose :
//   ordres-regles.js      CE FICHIER, qui crée l'objet Ordres :
//                           1. Constantes et petits outils (textes, dates, libellés)
//                           2. Règles métier PURES, exposées pour les tests (aucune écriture)
//   ordres-ecritures.js    3. Écritures : toujours par Donnees.modifier (contrôles DANS la fonction)
//   ordres-liste.js        4. Liste des OT (#/ot) : filtres, tableau triable, cartes, export CSV
//   ordres-fiche.js        5. Nouvel OT (#/ot/nouveau, ?equipement=…, ?urgence=1)
//                          6. Fiche OT (#/ot/<id>) : en-tête, étapes, consignation, anomalie d'un
//                             OT préventif et demandes liées, actions, messages
//   ordres-onglets.js      7. Onglet Préparation   8. Onglet Exécution   9. Onglet Compte rendu
//                         10. Onglet Historique équipement ; encart des causes fréquentes (7 et 9)
//   ordres-pieces.js      13. Pièces sorties et retours de l'onglet Exécution (RG6, magasin)
//   ordres-impression.js  11. Bon de travail (impression)   12. Enregistrement des écrans
//
// Les fichiers suivants complètent l'objet : Object.assign(Ordres, (() => { … return { … }; })()).
// Une fonction ou une constante dont un autre fichier du module a besoin est rangée dans
// Ordres.interne (usage interne au module : ce n'est pas une API, ni les autres modules ni les
// tests ne s'en servent) ; l'état de la session (memoire) y est partagé.
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
  // Lu à l'affichage (jamais figé au chargement).
  function rappelConsignation() {
    return I18n.t('ordres.rappel_consignation.cocher_case_consigne_rien');
  }

  // Mémoire du module pendant la session : filtres de la liste, onglet ouvert de chaque fiche.
  // Partagée par les fichiers ordres-*.js (Ordres.interne.memoire).
  const memoire = { filtres: null, profilFiltres: '', ongletParOt: {} };

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
      .sort((a, b) => UI.comparerTextes(a.libelle, b.libelle));
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

  /** « RAS », « R.A.S. », « rien à signaler »… (seuls, sans autre information) ; leurs équivalents anglais aussi
   *  (« NTR », « nothing to report », « N/A », « none », « nil ») : la règle est la même quelle que soit la langue de
   *  l'écran (D146), le compte rendu étant une donnée (T287). */
  function estRienASignaler(compteRendu) {
    const compact = texteSimple(compteRendu).replace(/ /g, '');
    return compact !== '' && /^(ras|rienasignaler|ntr|nothingtoreport|na|none|nil)+$/.test(compact);
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

  /**
   * Quantité nette déjà sortie du magasin pour un OT (sorties − retours), par article :
   * Map article → quantité. Calculée sur les mouvements de stock lus (comme le coût RG7), sans
   * passer par le module Magasin, chargé après celui-ci.
   */
  function netSortiParArticle(otId) {
    const net = new Map();
    Donnees.lignes('mouvements_stock').forEach((mouvement) => {
      if (mouvement.ot_id !== otId) return;
      const signe = mouvement.type === 'sortie' ? 1 : (mouvement.type === 'retour' ? -1 : 0);
      if (signe) net.set(mouvement.article_id, (net.get(mouvement.article_id) || 0) + signe * nombre(mouvement.quantite));
    });
    return net;
  }

  /**
   * Pièces prévues qui MANQUENT (RG3) : [{ article_id, libelle, prevu, sorti, stock, reste }].
   * Besoin restant d'un article = quantité prévue cumulée − net déjà sorti pour CET OT (au moins
   * 0) : une pièce déjà sortie pour l'OT n'a plus à être en stock. Elle manque si le stock est
   * inférieur à ce besoin restant. `prevu` reste la quantité prévue cumulée, `sorti` le net déjà
   * sorti pour l'OT (0 si rien, ou si tout a été retourné).
   */
  function piecesManquantes(otId) {
    const manquantes = [];
    const dejaSorti = netSortiParArticle(otId);
    quantitesPrevues(otId).forEach((prevu, articleId) => {
      const sorti = Math.max(0, arrondi(dejaSorti.get(articleId) || 0, 6));
      const reste = Math.max(0, arrondi(prevu - sorti, 6));
      const stock = Donnees.stockArticle(articleId);
      if (stock < reste) {
        manquantes.push({ article_id: articleId, libelle: libelleArticle(Donnees.trouver('articles', articleId)) || articleId,
          prevu: arrondi(prevu, 3), sorti: arrondi(sorti, 3), stock, reste: arrondi(reste, 3) });
      }
    });
    return manquantes;
  }

  /**
   * Détail d'une pièce manquante pour les messages RG3 (refus de « Planifié », bandeau de l'onglet
   * Préparation, motif de mise en attente proposé) : « 3 prévu(s), 1 en stock » (texte du lot 1),
   * ou, si du stock a déjà été sorti pour l'OT, « 3 prévu(s), 1 déjà sorti(s) pour cet OT, 1 en stock ».
   */
  function detailManque(piece) {
    if (piece.sorti > 0) return I18n.t('ordres.detail_manque.prevu_deja_sorti_ot', { prevu: UI.nombreFr(piece.prevu), sorti: UI.nombreFr(piece.sorti), stock: UI.nombreFr(piece.stock) });
    return I18n.t('ordres.detail_manque.prevu_stock', { n: piece.prevu, prevu: UI.nombreFr(piece.prevu), stock: UI.nombreFr(piece.stock) });
  }

  /**
   * Vrai si la date de fin est dans le futur (demande de Nicolas avant le lot 3 : une date de fin
   * saisie un an trop tard faussait la gamme du préventif). Comparaison à la minute près avec
   * l'heure locale du poste ; « AAAA-MM-JJ HH:MM », « AAAA-MM-JJTHH:MM » ou une date seule.
   */
  function dateFinDansLeFutur(dateFin, maintenant) {
    const fin = texte(dateFin).replace('T', ' ');
    if (!fin) return false;
    const reference = (maintenant || Donnees.maintenant()).replace('T', ' ');
    if (fin.length <= 10) return fin > reference.slice(0, 10);
    return fin.slice(0, 16) > reference.slice(0, 16);
  }

  /**
   * Manques qui bloquent la clôture technique (RG4) : TOUS, dans un tableau de phrases.
   * options.temps : lignes ot_temps à utiliser (par défaut, celles de l'OT dans Donnees).
   */
  function verifierCloture(ot, options) {
    const manques = [];
    const temps = (options && options.temps) || lignesDeLOt('ot_temps', ot.id);
    const compteRendu = texte(ot.compte_rendu);
    if (!texte(ot.date_fin)) manques.push(I18n.t('ordres.verifier_cloture.date_fin_travaux'));
    else if (texte(ot.date_debut) && texte(ot.date_fin) < texte(ot.date_debut)) manques.push(I18n.t('ordres.verifier_cloture.date_fin_posterieure_date'));
    else if (dateFinDansLeFutur(ot.date_fin)) manques.push(I18n.t('ordres.verifier_cloture.date_fin_soit_pas'));
    if (!temps.some((ligne) => nombre(ligne.heures) > 0)) manques.push(I18n.t('ordres.verifier_cloture.moins_temps_passe_onglet'));
    if (!texte(ot.cause_code)) manques.push(I18n.t('ordres.verifier_cloture.code_cause'));
    if (!texte(ot.remede_code)) manques.push(I18n.t('ordres.verifier_cloture.code_remede'));
    if (estCorrectif(ot) && estRienASignaler(compteRendu)) {
      manques.push(I18n.t('ordres.verifier_cloture.vrai_compte_rendu_ras'));
    } else if (compteRendu.length < 10) {
      manques.push(I18n.t('ordres.verifier_cloture.compte_rendu_moins_10'));
    }
    if (ot.remise_service !== '1') manques.push(I18n.t('ordres.verifier_cloture.case_equipement_remis_service'));
    return manques;
  }

  // --- RG8 : habilitations exigées par l'OT (D186, D191 ; conception L2-L3 §7.1, §7.2, §7.5) ----
  // Codes (aucun texte : les écrans les traduisent ; le marqueur du journal les écrit en français, D156).
  // Raisons d'une habilitation exigée non valide à la date : aucune ligne pour cet intitulé (absente),
  // des lignes toutes échues ou à échéance illisible (echue), une ligne obtenue après la date (pas_encore_obtenue).
  const RAISONS_HABILITATION = Object.freeze(['absente', 'echue', 'pas_encore_obtenue']);
  // Origine d'une exigence : la colonne habilitation_requise de l'équipement, ou celle de l'OT.
  const ORIGINES_HABILITATION = Object.freeze(['equipement', 'ot']);
  // Marqueur fixe du journal (D156), relu ici et par les écrans :
  // « dérogation habilitation : TEC-0004 le 2026-11-20 sans BR (échue), H0V (absente) ; motif : <texte> ».
  const MOTIF_DEROGATION = /(?:^|\s)dérogation habilitation : (\S+) le (\d{4}-\d{2}-\d{2}) sans (.+?) ; motif : ([\s\S]+)$/;
  const MOTIF_MANQUANTE = /^(.+?)(?: \((?:(absente)|(échue)|(pas encore obtenue))\))?$/;

  // Intitulé comparable et date lue : les fonctions d'Equipe (cherchées à l'appel, equipe-regles.js est
  // chargé après) ; une seule règle pour RG8 et pour l'écran Équipe (QUESTIONS-L2-L6 Q11).
  function cleIntitule(intitule) { return Equipe.interne.cleIntitule(intitule); }
  function dateLue(valeur) { return Equipe.interne.dateIso(valeur); }

  function ligneOt(ot) {
    return typeof ot === 'string' ? Donnees.trouver('ordres_travail', ot) : ot;
  }

  /** Intitulés d'une colonne habilitation_requise (« BR, B2V » ou « BR / H0V ») : tableau. */
  function intitulesDe(valeur) {
    return texte(valeur).split(/[,/]/).map((h) => h.trim()).filter(Boolean);
  }

  /** Exigences de l'équipement puis de l'OT, lues chacune sur sa ligne (jamais fusionnées), doublons
   *  (casse et espaces ignorés) réunis : [{ intitule, origines }] (première écriture gardée). */
  function exigencesDe(equipement, ot) {
    const parCle = new Map();
    [[equipement, 'equipement'], [ot, 'ot']].forEach(([ligne, origine]) => {
      intitulesDe(ligne && ligne.habilitation_requise).forEach((intitule) => {
        const cle = cleIntitule(intitule);
        if (!cle) return;
        const exigence = parCle.get(cle) || { intitule, origines: [] };
        if (!exigence.origines.includes(origine)) exigence.origines.push(origine);
        parCle.set(cle, exigence);
      });
    });
    return Array.from(parCle.values());
  }

  /** État d'une ligne d'habilitation au jour (bornes comprises ; obtention ou échéance vide : pas de borne,
   *  Q10 ; échéance illisible : échue, comme Equipe.etatHabilitation) : 'valide', 'echue' ou 'pas_encore_obtenue'. */
  function etatAuJour(habilitation, jour) {
    const echeance = dateLue(habilitation.date_echeance);
    if (texte(habilitation.date_echeance) && !echeance) return 'echue';
    const obtention = dateLue(habilitation.date_obtention);
    if (obtention && obtention > jour) return 'pas_encore_obtenue';
    if (echeance && echeance < jour) return 'echue';
    return 'valide';
  }

  /** Exigence non valide au jour → { intitule, origines, raison, echeance, obtention }, sinon null.
   *  echeance : la plus lointaine des lignes échues (lisible) ; obtention : la plus proche des lignes à venir. */
  function manquanteAuJour(exigence, lignes, jour) {
    const cle = cleIntitule(exigence.intitule);
    const siennes = lignes.filter((h) => cleIntitule(h.intitule) === cle);
    const etats = siennes.map((h) => etatAuJour(h, jour));
    if (etats.includes('valide')) return null;
    const manquante = { intitule: exigence.intitule, origines: exigence.origines.slice(), raison: 'absente', echeance: '', obtention: '' };
    const aVenir = siennes.filter((h, i) => etats[i] === 'pas_encore_obtenue').map((h) => dateLue(h.date_obtention)).sort();
    if (aVenir.length) return Object.assign(manquante, { raison: 'pas_encore_obtenue', obtention: aVenir[0] });
    if (siennes.length) {
      const echues = siennes.map((h) => dateLue(h.date_echeance)).filter(Boolean).sort();
      return Object.assign(manquante, { raison: 'echue', echeance: echues.length ? echues[echues.length - 1] : '' });
    }
    return manquante;
  }

  /** Contrôle d'exigences au jour (ISO) pour un technicien. Sans technicien : rien à contrôler. */
  function controleAuJour(exigees, technicienId, jour) {
    const id = texte(technicienId);
    const lignes = id ? Donnees.lignes('habilitations').filter((h) => texte(h.technicien_id) === id) : [];
    const manquantes = id ? exigees.map((exigence) => manquanteAuJour(exigence, lignes, jour)).filter(Boolean) : [];
    return { exigees, manquantes, bloque: manquantes.length > 0, technicienId: id, date: jour };
  }

  /**
   * Habilitations exigées par un OT (ligne ou identifiant) : habilitation_requise de son équipement ∪
   * habilitation_requise de l'OT (séparateurs « , » et « / », casse et espaces ignorés) →
   * [{ intitule, origines: ['equipement' | 'ot', …] }]. Un OT sans exigence rend [] : il n'est jamais bloqué.
   */
  function habilitationsExigees(ot) {
    const ligne = ligneOt(ot);
    return ligne ? exigencesDe(equipementDe(ligne), ligne) : [];
  }

  /**
   * RG8 (D186, D191) : le technicien a-t-il, à la date (date donnée, sinon date prévue de l'OT, sinon
   * aujourd'hui), une ligne valide pour chaque habilitation exigée ? → { exigees, manquantes, bloque,
   * technicienId, date }. manquantes : [{ intitule, origines, raison ('absente' | 'echue' |
   * 'pas_encore_obtenue'), echeance, obtention }] ; bloque : au moins une manquante. Sans exigence ou sans
   * technicien : bloque faux.
   */
  function controleHabilitation(ot, technicienId, date) {
    const ligne = ligneOt(ot);
    const jour = dateLue(date) || dateLue(ligne && ligne.date_prevue) || aujourdhui();
    return controleAuJour(habilitationsExigees(ligne), technicienId, jour);
  }

  /** Habilitations exigées par un équipement qui manquent au technicien au jour (intitulés ; vide si tout va bien). */
  function habilitationsManquantes(equipement, technicienId, date) {
    const jour = dateLue(date) || aujourdhui();
    return controleAuJour(exigencesDe(equipement, null), technicienId, jour).manquantes.map((m) => m.intitule);
  }

  /**
   * RG8 sur l'exigence d'un équipement (ligne ou identifiant), écrite au-dessus du même contrôle que
   * controleHabilitation : message si une habilitation exigée n'est pas valide à la date (sinon
   * aujourd'hui), sinon null. Ex. « TEC-0004 sans BR valide au 2026-10-21 ». pourLesDonnees : texte écrit
   * au journal, dans la langue de l'installation (D156) ; sinon celle de l'écran.
   */
  function verifierHabilitation(equipement, technicienId, dateReference, pourLesDonnees) {
    const ligne = typeof equipement === 'string' ? Donnees.trouver('equipements', equipement) : equipement;
    if (!ligne || !texte(technicienId)) return null;
    const date = dateLue(dateReference) || aujourdhui();
    const manquantes = habilitationsManquantes(ligne, technicienId, date);
    if (!manquantes.length) return null;
    if (pourLesDonnees) return I18n.donnees('ordres.verifier_habilitation.sans_valide', { technicienId, join: manquantes.join(', '), date });
    return I18n.t('ordres.verifier_habilitation.sans_valide', { technicienId, join: manquantes.join(', '), date });
  }

  /**
   * Marqueur fixe de dérogation (D156), en fin de l'action du journal de l'écriture (§7.5) :
   * « dérogation habilitation : TEC-0004 le 2026-11-20 sans BR (échue), H0V (absente) ; motif : … ».
   * manquantes : celles de controleHabilitation (ou des intitulés). Motif obligatoire (QUESTIONS-L2-L6
   * Q7), espaces et retours à la ligne réduits à une espace. Rend '' sans technicien, date, manquante ou motif.
   */
  function marqueurDerogation(technicienId, date, manquantes, motif) {
    const id = texte(technicienId);
    const jour = dateLue(date);
    const liste = (manquantes || []).map((m) => (typeof m === 'string' ? { intitule: m } : m || {}))
      .filter((m) => texte(m.intitule));
    const propre = texte(motif).replace(/\s+/g, ' ');
    if (!id || !jour || !liste.length || !propre) return '';
    const action = 'dérogation habilitation : ' + id + ' le ' + jour + ' sans '
      + liste.map((m) => texte(m.intitule) + (m.raison === 'echue' ? ' (échue)' : m.raison === 'absente' ? ' (absente)'
        : m.raison === 'pas_encore_obtenue' ? ' (pas encore obtenue)' : '')).join(', ')
      + ' ; motif : ' + propre;
    return action;
  }

  /** Relit le marqueur d'une action du journal → { technicienId, date, manquantes: [{ intitule, raison }],
   *  motif }, ou null (pas de marqueur, ou marqueur sans motif). raison : code, '' si le marqueur n'en dit pas. */
  function lireDerogation(action) {
    const trouve = MOTIF_DEROGATION.exec(texte(action));
    if (!trouve || !texte(trouve[4])) return null;
    const manquantes = trouve[3].split(', ').map((morceau) => {
      const m = MOTIF_MANQUANTE.exec(morceau.trim());
      const raison = m[2] ? 'absente' : m[3] ? 'echue' : m[4] ? 'pas_encore_obtenue' : '';
      return { intitule: m[1].trim(), raison };
    }).filter((m) => m.intitule);
    return manquantes.length ? { technicienId: trouve[1], date: trouve[2], manquantes, motif: texte(trouve[4]) } : null;
  }

  /**
   * Dérogation déjà notée au journal pour le même OT, le même technicien, la même date et les mêmes
   * habilitations (ensemble des intitulés, casse et espaces ignorés ; raisons non comparées) → l'entrée du
   * journal la plus récente, sinon null (§7.4 : préparer puis « Planifier » ne redemande pas).
   */
  function derogationAccordee(otId, technicienId, date, manquantes) {
    const ot = texte(otId);
    const id = texte(technicienId);
    const jour = dateLue(date);
    const attendues = new Set((manquantes || []).map((m) => cleIntitule(typeof m === 'string' ? m : m && m.intitule)).filter(Boolean));
    if (!ot || !id || !jour || !attendues.size) return null;
    const memes = (derogation) => {
      const cles = new Set(derogation.manquantes.map((m) => cleIntitule(m.intitule)));
      return cles.size === attendues.size && Array.from(cles).every((cle) => attendues.has(cle));
    };
    const trouvees = Donnees.lignes('journal').filter((entree) => {
      if (texte(entree.table) !== 'ordres_travail' || texte(entree.id_ligne) !== ot) return false;
      const derogation = lireDerogation(entree.action);
      return Boolean(derogation && derogation.technicienId === id && derogation.date === jour && memes(derogation));
    }).sort((a, b) => texte(b.date_heure).localeCompare(texte(a.date_heure)) || texte(b.id).localeCompare(texte(a.id)));
    return trouvees[0] || null;
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
    if (!ot) return { ok: false, erreurs: [I18n.t('ordres.verifier_passage.ordre_travail_introuvable')], avertissements, piecesManquantes: manquantes };
    if (!transitionsPossibles(ot).includes(cible)) {
      erreurs.push(estVerrouille(ot)
        ? I18n.t('ordres.verifier_passage.ot_verrouille_reprise_fait', { otStatut: Schema.libelleValeur('ordres_travail', 'statut', ot.statut) })
        : I18n.t('ordres.verifier_passage.passage_impossible', { otStatut: Schema.libelleValeur('ordres_travail', 'statut', ot.statut), cible: Schema.libelleValeur('ordres_travail', 'statut', cible) }));
    } else if (cible === 'En attente' && !texte(ot.motif_attente)) {
      erreurs.push(I18n.t('ordres.verifier_passage.motif_mise_attente_obligatoire'));
    } else if (cible === 'Annulé' && !texte(ot.motif_annulation)) {
      erreurs.push(I18n.t('ordres.verifier_passage.motif_annulation_obligatoire'));
    } else if (cible === 'Planifié') {
      if (!texte(ot.technicien_id)) erreurs.push(I18n.t('ordres.verifier_passage.choisissez_technicien_onglet_preparation'));
      if (!texte(ot.date_prevue)) erreurs.push(I18n.t('ordres.verifier_passage.indiquez_date_prevue_onglet'));
      manquantes = piecesManquantes(ot.id);
      manquantes.forEach((piece) => erreurs.push(I18n.t('ordres.verifier_passage.stock_insuffisant', { pieceLibelle: piece.libelle, detailManque: detailManque(piece) })));
      const habilitation = verifierHabilitation(equipementDe(ot), ot.technicien_id, ot.date_prevue);
      if (habilitation) avertissements.push(I18n.t('ordres.verifier_passage.avertissement_habilitation', { habilitation }));
    } else if (cible === 'Clôturé techniquement') {
      const manques = verifierCloture(ot);
      if (manques.length) erreurs.push(I18n.t('ordres.verifier_passage.manque_join', { join: manques.join(' ; ') }));
    } else if (cible === 'Clôturé administrativement') {
      // RG4 revérifiée : la clôture technique doit être encore complète (aucune saisie ne l'a défaite).
      const manques = verifierCloture(ot);
      if (manques.length) erreurs.push(I18n.t('ordres.verifier_passage.cloture_technique_plus_complete', { join: manques.join(' ; ') }));
    }
    return { ok: erreurs.length === 0, erreurs, avertissements, piecesManquantes: manquantes };
  }

  /**
   * Coût d'un OT (RG7), dans la devise réglée : { heures, pieces, soustraitance, total, detail }.
   *   heures : Σ heures passées × taux horaire du technicien (main-d'œuvre, dans la devise réglée) ;
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

  return {
    STATUTS, TYPES, PRIORITES, rappelConsignation, RAISONS_HABILITATION, ORIGINES_HABILITATION,
    // règles pures (ARCHITECTURE.md §10)
    transitionsPossibles, verifierPassage, verifierCloture, cout, verifierHabilitation, estOuvert, enRetard,
    estVerrouille, estCorrectif, estRienASignaler, piecesManquantes, filtrer, datePrevueParDefaut,
    dateFinDansLeFutur,
    // RG8 (D186, D191) : exigences de l'OT, contrôle, dérogation du responsable (marqueur du journal)
    habilitationsExigees, controleHabilitation, marqueurDerogation, lireDerogation, derogationAccordee,
    // affichage (les écritures, l'export et le bon de travail sont ajoutés par les fichiers suivants)
    libelleEquipement, nomTechnicien,
    // Usage interne au module : outils prêtés aux fichiers ordres-*.js, qui y ajoutent les leurs
    // par Object.assign(Ordres.interne, …). Pas une API : son contenu peut changer à tout moment.
    interne: {
      ETAPES, STATUTS_CLOTURES, memoire,
      texte, nombre, arrondi, aujourdhui, estResponsable, estTechnicien, monTechnicienId,
      equipementDe, repereEquipement, cheminLocalisation, listeTechniciens, libelleArticle, listeCodes,
      lignesDeLOt, operationsDe, placerChamp, champOt, statutDeReprise, quantitesPrevues,
      habilitationsManquantes, detailManque,
    },
  };
})();
