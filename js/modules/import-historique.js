'use strict';
// Import (2/7) — historique des interventions (lot 5, ARCHITECTURE.md §18.6, CDC D92) : OT clôturés
// importés d'une autre GMAO, ancien numéro gardé dans le compte rendu, doublons sûrs et supposés.
// Complète l'objet Import (fonctions pures : rien n'est écrit, seul Donnees est lu).
// Chaque ligne acceptée devient un OT « Clôturé administrativement » (origine « manuel », ou « préventif »
// sans gamme) et, si un temps passé est donné, une ligne ot_temps. Ordre des contrôles d'une ligne :
// 1. doublon SÛR (même ancien numéro dans Prévo ou plus haut dans le fichier) → ignorée ;
// 2. refus (cellule illisible, équipement absent ou introuvable, ni date de création ni début, nombre
//    négatif, ni titre ni compte rendu) ; 3. l'OT, défauts signalés ; 4. doublon SUPPOSÉ (même équipement,
// même date de création à la minute, même titre comparable) → montré, importé seulement si coché.
// Un OT existant n'est jamais modifié. Identifiants OT-AAAA-NNNN de l'année de date_creation.

Object.assign(Import, (() => {
  // Types de l'autre logiciel lus comme types de Prévo (D86, affichés dans l'aperçu « lu comme ») :
  // texte comparable → type. Ajoutés aux équivalences partagées de import-regles.js (conversion du champ « type »).
  const TYPES_LUS = {
    'depannage': 'correctif immédiat', 'curatif': 'correctif immédiat', 'preventif': 'préventif systématique',
    'entretien preventif': 'préventif systématique', 'maintenance preventive': 'préventif systématique',
    'conditionnel': 'préventif conditionnel', 'amelioratif': 'amélioration',
  };
  Import.interne.EQUIVALENCES['ordres_travail.type'] = TYPES_LUS;

  const [TYPE_DEFAUT, PRIORITE_DEFAUT, STATUT, TITRE_MAX] = ['correctif différé', 'P3', 'Clôturé administrativement', 80];
  const FAMILLES = [['symptome_code', 'symptôme'], ['cause_code', 'cause'], ['remede_code', 'remède']];
  const NOMBRES = ['duree_arret_h', 'temps_passe_h', 'cout_soustraitance'];
  // Ligne « Ancien n° : <numéro> » d'un compte rendu (casse et espaces libres ; « n° », « nº » ou « no »).
  const MOTIF_ANCIEN = /^\s*ancien\s+n(?:°|º|o)\.?\s*:\s*(.*?)\s*$/i;

  /** Ligne écrite en tête du compte rendu d'un OT importé (ajustement 1 de D92). */
  const ligneAncienNumero = (numero) => 'Ancien n° : ' + numero;

  /** Anciens numéros cités par un compte rendu (une ligne « Ancien n° : … » chacun), en clés comparables. */
  function anciensNumeros(compteRendu, o) {
    return String(compteRendu || '').split(/\r?\n/).map((ligne) => MOTIF_ANCIEN.exec(ligne))
      .filter((m) => m && m[1]).map((m) => o.cleTexte(m[1]));
  }

  /** Titre tiré du compte rendu (titre absent) : 80 caractères au plus, coupé en fin de mot. */
  function titreDe(compteRendu, o) {
    const ligne = o.texte(compteRendu).replace(/\s+/g, ' ');
    if (ligne.length <= TITRE_MAX) return ligne;
    let coupe = ligne.slice(0, TITRE_MAX);
    if (ligne[TITRE_MAX] !== ' ' && coupe.includes(' ')) coupe = coupe.slice(0, coupe.lastIndexOf(' '));
    return coupe.replace(/[\s,;:]+$/, '');
  }

  // Clé du doublon supposé : équipement, date de création à la minute, titre comparable.
  const cleDoublon = (equipementId, date, titre, o) => o.texte(equipementId) + '|' + o.texte(date).slice(0, 16) + '|' + o.comparable(titre);

  /** Code de défaillance de la famille donnée, par son code puis par son libellé (comparables) → { code } ou { erreur }. */
  function trouverCode(famille, valeur, o) {
    const codes = Donnees.lignes('codes_defaillance').filter((c) => o.texte(c.famille) === famille);
    const cherche = o.comparable(valeur);
    const parCode = codes.find((c) => o.comparable(c.code) === cherche);
    if (parCode) return { code: o.texte(parCode.code) };
    const parLibelle = codes.filter((c) => o.comparable(c.libelle) === cherche);
    if (parLibelle.length === 1) return { code: o.texte(parLibelle[0].code) };
    return { erreur: parLibelle.length ? 'désigne plusieurs codes « ' + famille + ' »' : 'introuvable parmi les codes « ' + famille + ' »' };
  }

  // OT de la base : anciens numéros cités et clés de doublon supposé (le premier OT l'emporte).
  function indexBase(o) {
    const [numeros, cles] = [new Map(), new Map()];
    for (const ot of Donnees.lignes('ordres_travail')) {
      anciensNumeros(ot.compte_rendu, o).forEach((numero) => { if (!numeros.has(numero)) numeros.set(numero, { ot: ot.id }); });
      const cle = cleDoublon(ot.equipement_id, ot.date_creation, ot.titre, o);
      if (!cles.has(cle)) cles.set(cle, { ot: ot.id });
    }
    return { numeros, cles };
  }

  // Ce qu'une ligne double : un OT de la base, ou une ligne plus haut dans le fichier.
  const decrireDoublon = (deja) => (deja.ot ? deja.ot : 'la ligne ' + deja.ligne.numero);

  // Refus d'une ligne qu'on garde (contrôles du §18.6) : équipement, dates, nombres, titre → [raison].
  function controler(contexte, o, v) {
    const erreurs = [];
    const equipement = o.trouverEquipement(v.equipement, contexte);
    if (!equipement) erreurs.push('équipement « ' + v.equipement + ' » introuvable dans Prévo');
    if (!v.date_creation && !v.date_debut) erreurs.push('ni date de création ni date de début : ligne refusée (la date de fin seule ne suffit pas)');
    for (const cle of NOMBRES) {
      if (v[cle] !== undefined && Number(v[cle]) < 0) erreurs.push(o.champDe(contexte.description, cle).libelle + ' : « ' + v[cle] + ' » ne peut pas être négatif');
    }
    if (!v.titre && !v.compte_rendu) erreurs.push('Titre obligatoire : ni titre ni compte rendu dans la ligne');
    return { equipement, erreurs };
  }

  // L'OT clôturé d'une ligne acceptée (§18.6) ; les valeurs par défaut et les déductions sont signalées.
  function construireOt(contexte, o, ligne, equipement) {
    const [v, raisons] = [ligne.valeurs, ligne.raisons];
    const type = v.type || TYPE_DEFAUT;
    if (!v.type) raisons.push('Type absent : « ' + TYPE_DEFAUT + ' » par défaut');
    const priorite = v.priorite || PRIORITE_DEFAUT;
    if (!v.priorite) raisons.push('Priorité absente : « ' + PRIORITE_DEFAUT + ' » par défaut');
    const titre = v.titre || titreDe(v.compte_rendu, o);
    if (!v.titre) raisons.push('Titre absent : début du compte rendu repris');
    const dateCreation = v.date_creation || v.date_debut;
    if (!v.date_creation) raisons.push('Date de création absente : date de début reprise');
    const dateDebut = v.date_debut || '';
    const dateFin = v.date_fin || dateDebut || dateCreation;
    if (!v.date_fin) raisons.push('Date de fin absente : ' + (dateDebut ? 'date de début' : 'date de création') + ' reprise');
    // Durée d'arrêt : vide si absente, jamais 0 inventé (ajustement 3) ; arrêt : la colonne, sinon une durée > 0.
    const duree = v.duree_arret_h || '';
    const avecDuree = duree !== '' && Number(duree) > 0;
    let arret = v.arret_production;
    if (arret === undefined) {
      arret = avecDuree ? '1' : '0';
      if (avecDuree) raisons.push("Arrêt de production absent : « oui », car une durée d'arrêt est donnée");
    } else if (arret === '0' && avecDuree) raisons.push("Arrêt de production « non » malgré une durée d'arrêt : laissé à « non »");
    if (arret === '1' && duree === '') raisons.push("Arrêt de production sans durée d'arrêt : durée laissée vide (panne hors MTTR et disponibilité)");
    // Codes par code ou libellé, dans la famille de la colonne seulement ; jamais créés.
    const codes = {};
    for (const [cle, famille] of FAMILLES) {
      codes[cle] = '';
      if (v[cle] === undefined) continue;
      const trouve = trouverCode(famille, v[cle], o);
      if (trouve.code) codes[cle] = trouve.code;
      else raisons.push(o.champDe(contexte.description, cle).libelle + ' « ' + v[cle] + ' » ' + trouve.erreur + ' : laissé vide (aucun code créé)');
    }
    let technicienId = '';
    if (v.technicien !== undefined) {
      const technicien = o.trouverTechnicien(v.technicien);
      if (technicien.id) technicienId = technicien.id;
      else raisons.push(technicien.erreur + ' : laissé vide');
    }
    const avecTemps = v.temps_passe_h !== undefined && Number(v.temps_passe_h) > 0;
    if (avecTemps && !technicienId) raisons.push('Temps passé sans technicien : ligne de temps sans technicien');
    const numero = v.ancien_numero || '';
    const compteRendu = numero ? ligneAncienNumero(numero) + (v.compte_rendu ? '\n' + v.compte_rendu : '') : (v.compte_rendu || '');
    const ot = o.nouvelleLigne('ordres_travail', Object.assign({
      origine: type.startsWith('préventif') ? 'préventif' : 'manuel', equipement_id: equipement.id, type, priorite, statut: STATUT,
      titre, date_creation: dateCreation, technicien_id: technicienId, date_debut: dateDebut, date_fin: dateFin,
      arret_production: arret, duree_arret_h: duree, compte_rendu: compteRendu, remise_service: '1',
      cout_soustraitance: v.cout_soustraitance || '', date_cloture_tech: dateFin, date_cloture_admin: dateFin,
    }, codes));
    const temps = avecTemps ? { technicien_id: technicienId, date: dateFin.slice(0, 10), heures: v.temps_passe_h } : null;
    return { ot, temps, cle: cleDoublon(equipement.id, dateCreation, titre, o) };
  }

  // Une ligne du fichier : conversion (import-regles.js), doublon sûr, refus, OT, doublon supposé, prévision.
  function lireLigne(contexte, o, index, cellules, rang) {
    if (!(cellules || []).some((cellule) => o.texte(cellule) !== '')) return;            // ligne vide : ignorée
    const ligne = { numero: contexte.premierNumero + rang, rang, action: 'creer', raisons: [], valeurs: {}, changements: [], cible: '' };
    contexte.lignes.push(ligne);
    if (rang >= o.PLAFOND_LIGNES) return o.refuser(ligne, 'au-delà de ' + o.PLAFOND_LIGNES + ' lignes (plafond) : ligne non lue');
    const lu = o.lireCellules(contexte.description, contexte.colonnes, cellules);
    const v = ligne.valeurs = lu.valeurs;
    ligne.raisons.push(...lu.notes);
    const numero = v.ancien_numero || '';
    const cleNumero = numero ? o.cleTexte(numero) : '';
    // 1. Doublon sûr (ajustement 2) : l'ancien numéro est déjà dans Prévo, ou plus haut dans le fichier.
    const deja = cleNumero ? index.base.numeros.get(cleNumero) || index.fichier.numeros.get(cleNumero) : null;
    if (deja) {
      Object.assign(ligne, { action: 'doublon_sur', _doublon: deja });
      ligne.raisons.unshift('Doublon sûr : ancien n° « ' + numero + ' » déjà ' + (deja.ot ? 'dans Prévo (' + deja.ot + ')' : 'à la ligne ' + deja.ligne.numero + ' du fichier') + ' : ligne ignorée');
      return;
    }
    // 2. Refus
    if (lu.erreurs.length || lu.manquants.length) return o.refuser(ligne, lu.erreurs.concat(lu.manquants));
    const { equipement, erreurs } = controler(contexte, o, v);
    if (erreurs.length) return o.refuser(ligne, erreurs);
    // 3. L'OT et sa ligne de temps
    const { ot, temps, cle } = construireOt(contexte, o, ligne, equipement);
    if (cleNumero) index.fichier.numeros.set(cleNumero, { ligne });
    // 4. Doublon supposé : montré, jamais écarté en silence ; importé seulement si « Importer quand même » est coché.
    const suppose = index.base.cles.get(cle) || index.fichier.cles.get(cle);
    if (suppose) {
      ligne._doublon = suppose;
      if (!index.forcees.has(ligne.numero)) {
        ligne.action = 'doublon_suppose';
        ligne.raisons.unshift('Doublon supposé : même équipement, même date de création et même titre que ' + decrireDoublon(suppose)
          + ' ; cochez « Importer quand même » pour l\'importer');
        return;
      }
      ligne.raisons.unshift('Doublon supposé de ' + decrireDoublon(suppose) + ' : importée quand même (case « Importer quand même » cochée)');
    } else index.fichier.cles.set(cle, { ligne });
    ligne._objet = o.prevoir(contexte, 'ordres_travail', ot, ligne);
    if (temps) o.prevoir(contexte, 'ot_temps', o.nouvelleLigne('ot_temps', Object.assign({ ot_id: ot }, temps)), ligne);
  }

  /**
   * Aperçu à blanc de l'historique (§18.5, §18.6), appelé par Import.preparer('historique', …) avec
   * outils = Import.interne. options : numeroPremiereLigne (2), importerQuandMeme (tableau ou Set des numéros
   * de ligne des doublons supposés à importer ; absent = aucun). Rend le format de preparer : lignes (action
   * creer, refusee, doublon_sur ou doublon_suppose ; pour un doublon, `cible` = l'OT doublé et `doublon` =
   * { ot, ligne }), ecritures { ordres_travail, ot_temps } (créations seulement), referencesCreees [], totaux.
   */
  function preparerHistorique(lignes, correspondanceChoisie, options, outils) {
    const [o, reglages] = [outils || Import.interne, options || {}];
    const contexte = o.nouveauContexte('historique', reglages);
    contexte.colonnes = o.colonnesParChamp(contexte.description, correspondanceChoisie);
    const coches = reglages.importerQuandMeme && typeof reglages.importerQuandMeme === 'object' ? Array.from(reglages.importerQuandMeme) : [];
    const index = { base: indexBase(o), fichier: { numeros: new Map(), cles: new Map() }, forcees: new Set(coches.map(Number)) };
    (lignes || []).forEach((cellules, rang) => lireLigne(contexte, o, index, cellules, rang));
    const apercu = o.terminer(contexte);
    contexte.lignes.forEach((ligne, i) => {
      if (!ligne._doublon) return;
      const doublee = ligne._doublon.ligne;
      const ot = ligne._doublon.ot || (doublee && o.GARDEES.has(doublee.action) && doublee._objet ? doublee._objet.id : '');
      apercu.lignes[i].doublon = { ot, ligne: doublee ? doublee.numero : null };
      if (ligne.action !== 'creer') apercu.lignes[i].cible = ot;
    });
    ['doublon_sur', 'doublon_suppose'].forEach((action) => { apercu.totaux[action] = apercu.totaux[action] || 0; });
    return apercu;
  }

  return { preparerHistorique, ligneAncienNumero };
})());
