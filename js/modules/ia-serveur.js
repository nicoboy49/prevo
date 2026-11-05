'use strict';
// Ia (4/4) — mode serveur (audit M1, M2, M3 ; ARCHITECTURE.md §17.2 et §22.12) : le fournisseur d'IA, son
// adresse, sa clé et l'accord pour l'IA en ligne sont réglés sur le PC serveur (prevo.config.json, options
// --ia-url, --ia-fournisseur, --ia-en-ligne, variable PREVO_IA_CLE) ; le poste ne règle que l'activation, le
// modèle et son délai d'attente, et ne garde aucune clé. Complète l'objet Ia (après ia.js).
//
// API :
//   Ia.reglagesServeur() → { fournisseur, url, cleReglee, enLigne, portee } lus sur le serveur, ou null (pas
//     encore lus, illisibles, ou hors mode serveur) ; jamais la clé, que le serveur ne rend pas.
//   Ia.lireReglagesServeur() → Promise de Ia.reglagesServeur() : relit GET /api/ia/reglages (une lecture à la
//     fois) ; ne lève jamais. Fournisseur ou adresse changés : l'état de l'IA repart à « inconnu » (et le
//     fournisseur est retesté si l'IA est active) ; toujours un événement Ia 'changement' (raison 'serveur').
//     Lus à l'ouverture de Prévo quand l'IA est activée sur le poste (sans IA, aucun appel : CS76), à
//     l'ouverture de « Ce poste » et de Paramètres, et avant un test ou une demande s'ils ne sont pas connus.
//   Relais (Ia.interne.appelRelais, appelé par ia.js en mode serveur) : POST /api/ia avec { chemin, methode,
//     corps } seulement ; le serveur y met l'adresse, la clé et le délai (120 s). Un refus 403 (IA en ligne
//     non autorisée sur le PC serveur) fait relire les réglages : les boutons IA s'en vont d'eux-mêmes.
// À l'ouverture de Prévo en mode serveur, un ancien réglage du poste qui gardait un fournisseur, une adresse ou
// une clé (prevo.ia d'avant la version 2) est réécrit sans eux.

Object.assign(Ia, (() => {

  const ADRESSE_RELAIS = '/api/ia';
  const ADRESSE_REGLAGES = '/api/ia/reglages';
  const PORTEES = ['pc-atelier', 'atelier', 'distant'];
  const CHAMPS_DU_SERVEUR = ['fournisseur', 'url', 'cle'];     // jamais mémorisés sur le poste en mode serveur
  let connus = null;                  // { fournisseur, url, cleReglee, enLigne, portee }
  let lecture = null;                 // promesse de la lecture en cours

  function modeServeur() {
    return typeof App !== 'undefined' && Boolean(App) && App.mode === 'serveur' && !Ia.versionWeb();
  }

  /** L'IA est réservée aux techniciens et au responsable (lot 7, §22.5, arbitrage de Nicolas du 2026-10-28) : faux
   *  pour un demandeur en mode serveur avec les comptes exigés (le serveur lui répond 403) ; vrai partout ailleurs. */
  function permiseAuProfil() {
    if (!modeServeur() || typeof App.comptesExiges !== 'function' || !App.comptesExiges()) return true;
    return !(typeof App.estDemandeur === 'function' && App.estDemandeur());
  }

  /** Réglages de l'IA lus sur le PC serveur (copie), ou null. */
  function reglagesServeur() {
    return connus ? Object.assign({}, connus) : null;
  }

  // Réponse du serveur → réglages propres (fournisseur inconnu : ollama ; portée inconnue : distant).
  function normaliser(lus) {
    const texte = (valeur) => (typeof valeur === 'string' ? valeur.trim() : '');
    return {
      fournisseur: Object.prototype.hasOwnProperty.call(Ia.FOURNISSEURS, lus.fournisseur) ? lus.fournisseur : 'ollama',
      url: texte(lus.url), cleReglee: lus.cle_reglee === true, enLigne: lus.en_ligne === true,
      portee: PORTEES.includes(lus.portee) ? lus.portee : 'distant',
    };
  }

  // Fin d'une lecture : réglages retenus s'ils sont lisibles ; dans tous les cas, événement 'serveur'.
  function retenir(lus) {
    const avant = connus;
    const lisibles = Boolean(lus) && typeof lus === 'object';
    if (lisibles) connus = normaliser(lus);
    const change = lisibles && (!avant || avant.fournisseur !== connus.fournisseur || avant.url !== connus.url);
    if (change) Ia.interne.oublierEtat();               // un test d'avant ne vaut pas pour un autre fournisseur
    Ia.interne.signaler('serveur');
    if (change && avant && Ia.active()) Ia.tester();
  }

  /** Relit GET /api/ia/reglages ; promesse de reglagesServeur() (null hors mode serveur). Ne lève jamais. */
  function lireReglagesServeur() {
    if (!modeServeur() || !permiseAuProfil()) return Promise.resolve(null);   // un demandeur n'a pas l'IA (403)
    if (!lecture) {
      lecture = fetch(ADRESSE_REGLAGES, { cache: 'no-store', headers: { Accept: 'application/json' } })
        .then((reponse) => (reponse.ok ? reponse.json() : null))
        .catch((erreur) => {
          console.warn('Prévo : réglages de l\'assistant IA du serveur illisibles (' + (erreur && erreur.message) + ').');
          return null;
        })
        .then((lus) => {
          lecture = null;
          try { retenir(lus); } catch (erreur) { console.warn('Prévo : réglages de l\'assistant IA non appliqués.', erreur); }
          return reglagesServeur();
        });
    }
    return lecture;
  }

  // Ancien réglage du poste (fournisseur, adresse ou clé gardés dans prevo.ia) : réécrit sans eux (M3).
  function oublierAncienReglage() {
    let lus = null;
    try { lus = JSON.parse(window.localStorage.getItem(Ia.interne.CLE_REGLAGES) || 'null'); } catch (erreur) { return; }
    if (lus && typeof lus === 'object' && CHAMPS_DU_SERVEUR.some((nom) => nom in lus)) Ia.interne.memoriser();
  }

  // Relais du serveur (§17.2, §22.12) : la demande ne porte que chemin, methode et corps.
  async function appelRelais(r, chemin, methode, corps, signal) {
    const interne = Ia.interne;
    const demande = { chemin, methode };
    if (methode === 'POST') demande.corps = corps;
    let reponse;
    try {
      reponse = await fetch(ADRESSE_RELAIS, {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Prevo': '1' },
        body: JSON.stringify(demande), signal, cache: 'no-store',
      });
    } catch (erreur) {
      if (signal.aborted) throw erreur;
      throw interne.erreurReseau(I18n.t('ia.appel_relais.serveur_prevo_repond_pas'), erreur);
    }
    const donnees = await interne.lireCorps(reponse, signal);
    if (reponse.status === 504) throw interne.messageDelai(Math.min(r.delaiS, interne.DELAI_RELAIS_S));
    if (reponse.status === 502) {
      const hote = interne.hoteAffiche(r.url) || I18n.t('ia.appel_relais.adresse_inconnue');
      throw interne.erreurReseau(I18n.t('ia.appel_relais.pc_atelier_joint_pas', { hote }));
    }
    if (reponse.status === 403) lireReglagesServeur();
    if (reponse.status !== 200 || !donnees || typeof donnees !== 'object') {
      const erreur = donnees && typeof donnees === 'object' && donnees.erreur;
      if (erreur) throw new Ia.IaIndisponible(I18n.t('ia.appel_relais.serveur_refuse_erreur', { erreur }));
      throw new Ia.IaIndisponible(I18n.t('ia.appel_relais.serveur_refuse_code', { status: reponse.status }));
    }
    return { statut: Number(donnees.statut) || 0, corps: donnees.corps };
  }

  // Ouverture de Prévo (Ia.verifierAuDemarrage signale 'ouverture' avant tout) : ancien réglage du poste
  // réécrit, puis réglages du PC serveur lus si l'IA est activée sur le poste.
  Ia.evenements.addEventListener('changement', (evenement) => {
    if (!evenement.detail || evenement.detail.raison !== 'ouverture' || !modeServeur()) return;
    oublierAncienReglage();
    if (Ia.reglages().actif) lireReglagesServeur();     // lireReglagesServeur ne fait rien pour un demandeur
  });

  Ia.interne.appelRelais = appelRelais;

  return { reglagesServeur, lireReglagesServeur, permiseAuProfil };
})());
