'use strict';
// Wiki (3/5) — écritures des synthèses (lot 6, ARCHITECTURE.md §20.5) : enregistrer, valider, modifier
// (une synthèse validée puis modifiée repasse « à valider »), remplacer ; responsable seulement, par
// Donnees.modifier (contrôle de version, journal « <champs> — <action> »). Chaque texte passe d'abord par
// Wiki.controlerSynthese (§20.4) : rien n'est écrit s'il est refusé. Complète l'objet Wiki.
// Un refus lève Donnees.ErreurValidation (message pour l'utilisateur) ; jamais de suppression : une
// synthèse remplacée reste dans la table, statut « remplacée » (historique de la page).

Object.assign(Wiki, (() => {

  const TABLE = 'wiki_syntheses';
  const STATUTS_CLOTURES = ['Clôturé techniquement', 'Clôturé administrativement'];
  const MESSAGE_RESERVE = 'Seul le responsable peut enregistrer, corriger ou valider une synthèse du wiki.';

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  function ErreurValidation(message) {
    return new Donnees.ErreurValidation(message);
  }

  // Profil courant (App), ou null hors de l'application (pages de test sans App).
  function profilCourant() {
    return typeof App !== 'undefined' && App.profil ? App.profil : null;
  }

  function verifierResponsable() {
    const profil = profilCourant();
    if (!profil || profil.type !== 'responsable') throw ErreurValidation(MESSAGE_RESERVE);
    return profil;
  }

  // Nom inscrit comme validateur ou correcteur : celui du profil, sinon « Responsable » (jamais vide).
  function nomDe(profil) {
    return texte(profil && profil.nom) || 'Responsable';
  }

  // Texte comparé « identique » : fins de ligne et espaces de bord ignorés.
  function texteNormalise(valeur) {
    return String(valeur || '').replace(/\r\n?/g, '\n').split('\n').map((ligne) => ligne.trim()).filter(Boolean).join('\n');
  }

  function identifiants(valeur) {
    return String(valeur || '').split(';').map(texte).filter(Boolean);
  }

  /** Identifiants des OT clôturés d'un équipement. */
  function otClotures(equipementId) {
    return Donnees.lignes('ordres_travail')
      .filter((ot) => ot.equipement_id === equipementId && STATUTS_CLOTURES.includes(ot.statut)).map((ot) => ot.id);
  }

  /** Contrôle d'un texte : refus = ErreurValidation avec toutes les raisons. → résultat de controlerSynthese. */
  function controler(valeur, otPermis, origine) {
    const controle = Wiki.controlerSynthese(valeur, otPermis, { origine });
    if (!controle.ok) throw ErreurValidation('Synthèse refusée : ' + controle.raisons.join(' '));
    return controle;
  }

  /** Synthèse courante (non « remplacée ») d'un équipement parmi des lignes, ou null. */
  function courante(lignes, equipementId) {
    return lignes.find((ligne) => ligne.equipement_id === equipementId && ligne.statut !== 'remplacée') || null;
  }

  /**
   * Enregistre une nouvelle synthèse pour un équipement : { texte, otSources: [id], modele } ; options
   * { valider, corrige } — `valider` : statut « validée » (nom et date du responsable) au lieu de « à
   * valider » ; `corrige` : le texte a été changé à la main avant l'enregistrement (« corrigée par », et
   * contrôle « à la main » : OT envoyés ou OT clôturés de l'équipement). La synthèse courante, s'il y en
   * a une, passe « remplacée » (l'écran a demandé confirmation). → identifiant de la nouvelle ligne.
   */
  async function enregistrer(equipementId, proposition, options) {
    const profil = verifierResponsable();
    const reglages = options || {};
    if (!Donnees.trouver('equipements', equipementId)) throw ErreurValidation('Équipement « ' + equipementId + ' » introuvable.');
    const sources = (proposition && proposition.otSources || []).map(texte).filter(Boolean);
    const permis = reglages.corrige ? sources.concat(otClotures(equipementId)) : sources;
    const controle = controler(proposition && proposition.texte, permis, reglages.corrige ? 'main' : 'ia');
    const modele = texte(proposition && proposition.modele) || 'modèle inconnu';
    const action = reglages.valider ? 'synthèse proposée (' + modele + ') et validée' : 'synthèse proposée (' + modele + ')';
    const id = await Donnees.modifier(TABLE, (lignes, outils) => {
      const actuelle = courante(lignes, equipementId);
      if (actuelle) actuelle.statut = 'remplacée';
      const maintenant = outils.maintenant();
      const ligne = {
        id: outils.nouvelId(lignes),
        equipement_id: equipementId,
        texte: texteNormalise(proposition.texte),
        ot_cites: controle.otCites.join(';'),
        ot_sources: sources.join(';'),
        statut: reglages.valider ? 'validée' : 'à valider',
        modele,
        date_proposition: maintenant,
        corrigee_par: reglages.corrige ? nomDe(profil) : '',
        date_modification: reglages.corrige ? maintenant : '',
        valide_par: reglages.valider ? nomDe(profil) : '',
        date_validation: reglages.valider ? maintenant : '',
      };
      lignes.push(ligne);
      return ligne.id;
    }, { action });
    if (typeof Ia !== 'undefined' && Ia.tracerUtilisation) {
      try {
        await Ia.tracerUtilisation(TABLE, id, 'synthèse', modele);
      } catch (erreur) {
        console.warn('Prévo : trace de l\'IA non écrite (' + (erreur && erreur.message) + ').', erreur);
      }
    }
    return id;
  }

  /** « à valider » → « validée » (nom et date du responsable). → vrai si la ligne a changé. */
  async function valider(id) {
    const profil = verifierResponsable();
    return Donnees.modifier(TABLE, (lignes, outils) => {
      const ligne = lignes.find((l) => l.id === id);
      if (!ligne) throw ErreurValidation('Synthèse « ' + id + ' » introuvable.');
      if (ligne.statut === 'remplacée') throw ErreurValidation('Cette synthèse a été remplacée : elle ne peut plus être validée.');
      if (ligne.statut === 'validée') return false;
      ligne.statut = 'validée';
      ligne.valide_par = nomDe(profil);
      ligne.date_validation = outils.maintenant();
      return true;
    }, { action: 'synthèse validée' });
  }

  /**
   * Corrige le texte d'une synthèse : contrôles « à la main » (OT envoyés ou OT clôturés de l'équipement) ;
   * texte changé → « à valider », « corrigée par », validateur effacé ; texte identique → rien.
   * → vrai si la ligne a changé.
   */
  async function modifier(id, nouveauTexte) {
    const profil = verifierResponsable();
    const existante = Donnees.trouver(TABLE, id);
    if (!existante) throw ErreurValidation('Synthèse « ' + id + ' » introuvable.');
    if (existante.statut === 'remplacée') throw ErreurValidation('Cette synthèse a été remplacée : elle ne peut plus être corrigée.');
    if (texteNormalise(nouveauTexte) === texteNormalise(existante.texte)) return false;
    const controle = controler(nouveauTexte, identifiants(existante.ot_sources).concat(otClotures(existante.equipement_id)), 'main');
    return Donnees.modifier(TABLE, (lignes, outils) => {
      const ligne = lignes.find((l) => l.id === id);
      if (!ligne) throw ErreurValidation('Synthèse « ' + id + ' » introuvable.');
      if (ligne.statut === 'remplacée') throw ErreurValidation('Cette synthèse a été remplacée : elle ne peut plus être corrigée.');
      if (texteNormalise(nouveauTexte) === texteNormalise(ligne.texte)) return false;
      ligne.texte = texteNormalise(nouveauTexte);
      ligne.ot_cites = controle.otCites.join(';');
      ligne.statut = 'à valider';
      ligne.corrigee_par = nomDe(profil);
      ligne.date_modification = outils.maintenant();
      ligne.valide_par = '';
      ligne.date_validation = '';
      return true;
    }, { action: 'synthèse corrigée — à valider' });
  }

  /**
   * Une synthèse est-elle montrée à ce profil ? « validée » : à tous ; « à valider » et « remplacée »
   * (historique) : au responsable seulement (§20.5).
   */
  function syntheseVisible(synthese, profil) {
    if (!synthese) return false;
    if (synthese.statut === 'validée') return true;
    return !!profil && profil.type === 'responsable';
  }

  /** Synthèses remplacées d'un équipement, la plus récente d'abord (historique de la page, responsable). */
  function remplacees(equipementId) {
    return Donnees.lignes(TABLE).filter((ligne) => ligne.equipement_id === equipementId && ligne.statut === 'remplacée')
      .sort((a, b) => texte(b.date_proposition).localeCompare(texte(a.date_proposition)) || texte(b.id).localeCompare(texte(a.id)));
  }

  return { MESSAGE_RESERVE, enregistrer, valider, modifier, syntheseVisible, remplacees };
})());
