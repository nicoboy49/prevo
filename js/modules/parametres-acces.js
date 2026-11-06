'use strict';
// Parametres (5/5) — carte « Accès et installation » de l'écran Paramètres (ARCHITECTURE.md §22.10 ; CDC D130, D131
// dernier point, CS129, CS130). Visible seulement en mode serveur, sur le PC serveur (App.pcServeur()) et pour le
// responsable : depuis un client du réseau, en mode dossier ou démo, ou pour un autre profil, rien du tout (le serveur
// répond déjà 404 hors loopback aux routes /api/installation/… : l'écran ne montre pas ce qui ne marcherait pas).
//   État du serveur (en tête, bouton « Actualiser ») : actif depuis (/api/info, actif_depuis), portée et adresses
//   (adresse locale, adresses réseau, adresse Tailscale), Tailscale (GET etat : détecté à chaque lecture), copie
//   externe des sauvegardes (/api/info, copie_externe), dernières lignes du journal du serveur (GET journal ;
//   « aucune erreur notée » sinon), installation terminée ou non ; lien « Voir la fiche d'accès » (#/installation/fiche).
//   Chaque réglage refaisable, une sous-section par étape de l'assistant, même mécanique que lui (le brouillon de
//   l'API) : POST reprendre (brouillon repris de la configuration en cours) au premier enregistrement, puis POST
//   portee | certificat | tailscale | demarrage | sauvegardes | reglages | ia. Les formulaires des étapes sont ceux
//   d'InstallationEtapes (jamais recopiés), les aides celles d'AccesTextes.options (une seule source).
//   Un brouillon en attente est annoncé (« Modifications en attente ») : « Appliquer et relancer » (POST terminer :
//   configuration écrite puis relance ; « Prévo redémarre : les postes connectés se reconnecteront ») ou « Annuler »
//   (POST annuler, rien ne change). Après « terminer », /api/info est relu toutes les 2 s jusqu'à ce que actif_depuis
//   change (le serveur relancé) ou que la session soit à rouvrir (401), puis la page se recharge ; message après 60 s.
//   Retrait du démarrage (CS129) : passer à « À la main » quand Prévo démarrait avec le PC envoie {"retirer": true}
//   (Retirer_demarrage.ps1 lancé avec l'élévation : tâche, règle du pare-feu et veille défaites).
// Dépendances : UI, App, AccesTextes, InstallationEtapes. Objet ParametresAcces { carteAcces, brancherAcces }, relié à
// Parametres.interne en fin de fichier (relais carteAcces et brancherAcces de parametres.js).

const ParametresAcces = (() => {

  const INTERVALLE_RELANCE_MS = 2000;
  const DELAI_RELANCE_MS = 60000;
  // Textes lus à l'affichage (fonctions), jamais figés au chargement du module.
  const messageServeurInjoignable = () => I18n.t('parametres.message_serveur_injoignable.serveur_prevo_repond_pas');
  const avertissementRelance = () => I18n.t('parametres.avertissement_relance.prevo_redemarre_postes_connectes');
  const libelles = () => ({
    demandeurs_avec_compte: I18n.t('parametres.libelles.chaque_demandeur_mot_passe'),
    session_heures: I18n.t('parametres.libelles.duree_session_sans_activite'),
    session_longue_jours: I18n.t('parametres.libelles.duree_rester_connecte_appareil'),
    invitation_heures: I18n.t('parametres.libelles.duree_validite_invitation_appareils'),
    quota_documents_mo: I18n.t('parametres.libelles.place_maximale_documents_joints'),
    ia_fournisseur: I18n.t('parametres.libelles.type_service_ia'),
    ia_url: I18n.t('parametres.libelles.adresse_service_ia'),
    ia_en_ligne: I18n.t('parametres.libelles.autoriser_service_ia_ligne'),
  });
  const libellesFournisseur = () => ({ ollama: I18n.t('parametres.libelles_fournisseur.ollama_local'), openai: I18n.t('parametres.libelles_fournisseur.api_compatible_open_ai_lm') });

  // --- État -------------------------------------------------------------------------------
  let etat = null;                 // GET etat (configuration en cours, brouillon, étapes, Tailscale, mkcert…)
  let info = null;                 // GET /api/info (actif depuis, adresses, porte, copie externe)
  let journal = null;              // GET journal ({ fichier, lignes })
  let ouvertes = new Set();        // sections dépliées, gardées d'un rendu à l'autre
  let pendant = null;              // pendant(bouton, contexte, action) de parametres.js

  // ===========================================================================================
  // 1. Visibilité et appels au serveur
  // ===========================================================================================

  function visible() {
    return App.mode === 'serveur' && typeof App.pcServeur === 'function' && App.pcServeur() && App.estResponsable()
      && typeof InstallationEtapes !== 'undefined' && typeof AccesTextes !== 'undefined';
  }

  /** GET (sans corps) ou POST JSON vers « chemin » → { statut, donnees, message } ; ne lève jamais. */
  async function appeler(chemin, corps) {
    const options = { cache: 'no-store', credentials: 'same-origin', headers: {} };
    if (corps !== undefined) {
      options.method = 'POST';
      options.headers = { 'X-Prevo': '1', 'Content-Type': 'application/json; charset=utf-8' };
      options.body = JSON.stringify(corps);
    }
    let reponse;
    try {
      reponse = await fetch(chemin, options);
    } catch (erreur) {
      return { statut: 0, donnees: null, message: messageServeurInjoignable() };
    }
    const donnees = await reponse.json().catch(() => null);
    const message = donnees && typeof donnees.erreur === 'string' && donnees.erreur
      ? StockageServeur.texte(donnees, 'erreur') : I18n.t('commun.message.serveur_a_repondu', { status: reponse.status });
    return { statut: reponse.status, donnees: donnees, message: reponse.ok ? '' : message };
  }

  const etape = (nom, corps) => appeler('/api/installation/' + nom, corps);

  async function lireTout() {
    const [e, j, i] = await Promise.all([etape('etat'), etape('journal'), appeler('/api/info')]);
    const refus = [e, j, i].find((r) => !r.statut || r.statut >= 400);
    if (refus) return refus.message;
    etat = e.donnees;
    journal = j.donnees;
    info = i.donnees;
    return '';
  }

  // Valeurs montrées : le brouillon s'il existe, sinon la configuration en cours (jamais ia_cle).
  function valeurs() {
    return (etat && (etat.brouillon || etat.configuration)) || {};
  }

  function situation() {
    return (etat && (etat.situation || (etat.brouillon && etat.brouillon.situation))) || '';
  }

  function etatEtape(cle) {
    return (etat && etat.etapes && etat.etapes[cle]) || 'a_faire';
  }

  function aideOption(cle) {
    const option = AccesTextes.options && AccesTextes.options[cle];
    return option && option.aide ? option.aide : '';
  }

  function formulaireDe(cle) {
    return InstallationEtapes.formulaire(cle, { etat, brouillon: valeurs, situation, etatEtape, blocTextes: () => '', aideOption });
  }

  // Réponse d'une étape qui écrit le brouillon : {brouillon, etapes} repris dans l'état.
  function reprendre(donnees) {
    if (!donnees) return;
    if ('brouillon' in donnees) etat.brouillon = donnees.brouillon;
    if (donnees.etapes) etat.etapes = donnees.etapes;
    if (etat.brouillon && etat.brouillon.situation) etat.situation = etat.brouillon.situation;
  }

  // Le brouillon est repris de la configuration en cours au premier enregistrement (POST reprendre) : 'present' s'il
  // existait, 'cree' s'il vient d'être repris, false si le serveur refuse (message montré).
  async function assurerBrouillon(cle) {
    if (etat.brouillon) return 'present';
    const reponse = await etape('reprendre', {});
    if (!reponse.statut || reponse.statut >= 400) { montrerErreur(cle, reponse.message); return false; }
    reprendre(reponse.donnees);
    return 'cree';
  }

  // Un brouillon repris pour un enregistrement que le serveur refuse est jeté : rien n'est « en attente ».
  async function jeterSiNeuf(brouillon) {
    if (brouillon !== 'cree') return;
    const reponse = await etape('annuler', {});
    if (reponse.statut === 200) reprendre(reponse.donnees);
  }

  // ===========================================================================================
  // 2. État du serveur
  // ===========================================================================================

  function texteTailscale(t) {
    if (!t || !t.present) return t && t.raison ? I18n.t('parametres.texte_tailscale.non_detecte_pc', { raison: StockageServeur.texte(t, 'raison') }) : I18n.t('parametres.texte_tailscale.non_detecte_pc_2');
    if (!t.connecte) return I18n.t('parametres.texte_tailscale.installe_mais_pas_connecte');
    const jours = t.jours_avant_expiration;
    const nom = t.nom || I18n.t('parametres.texte_tailscale.nom_inconnu');
    if (jours === null || jours === undefined) return I18n.t('parametres.texte_tailscale.connecte_nom', { nom });
    if (jours > 14) return I18n.t('parametres.texte_tailscale.connecte_cle_valable_jours', { nom, jours });
    if (jours <= 0) return I18n.t('parametres.texte_tailscale.connecte_cle_expire_aujourd', { nom });
    return I18n.t('parametres.texte_tailscale.connecte_cle_expire_jours', { n: jours, nom });
  }

  function texteCopie(copie, dossier) {
    if (!dossier) return I18n.t('parametres.texte_copie.aucune_copie_reglee_sauvegarde');
    const derniere = copie && copie.derniere_reussie ? I18n.t('parametres.texte_copie.derniere_copie_reussie', { derniere_reussie: UI.dateFr(copie.derniere_reussie) }) : I18n.t('parametres.texte_copie.aucune_copie_reussie_instant');
    const erreur = copie && copie.erreur ? ' ' + I18n.t('parametres.texte_copie.dernier_echec', { erreur: StockageServeur.texte(copie, 'erreur') }) : '';
    return UI.html`${dossier} — ${derniere}${erreur}`;
  }

  function adressesDuServeur() {
    const v = valeurs();
    const t = etat.tailscale || {};
    const adresses = [info.adresse_locale].concat(info.adresses_reseau || []).filter(Boolean);
    if (t.present && t.nom && v.mandataire) adresses.push('https://' + t.nom + '/');
    return adresses;
  }

  function etatServeur() {
    const v = valeurs();
    const lignes = (journal && journal.lignes) || [];
    return UI.html`<dl class="valeurs acces-etat" id="acces-etat">
      <dt>${I18n.t('parametres.etat_serveur.actif_depuis')}</dt><dd id="acces-actif-depuis">${info.actif_depuis ? UI.dateHeureFr(info.actif_depuis) : 'inconnu'}</dd>
      <dt>${I18n.t('parametres.etat_serveur.installation')}</dt><dd id="acces-installation">${etat.configuration_presente ? I18n.t('parametres.etat_serveur.terminee_prevo_config_json')
        : UI.html`${I18n.html('parametres.etat_serveur.pas_terminee_ouvrir_assistant')}`}</dd>
      <dt>${I18n.t('parametres.etat_serveur.portee')}</dt><dd id="acces-portee">${InstallationEtapes.LIBELLES_PORTEE[etat.portee] || etat.portee || '—'}${info.porte ? ' ' + I18n.t('parametres.etat_serveur.porte_entree_ouverte_reseau') : ''}</dd>
      <dt>${I18n.t('parametres.etat_serveur.adresses')}</dt><dd id="acces-adresses">${adressesDuServeur().map((adresse) => UI.html`<span class="acces-adresse">${adresse}</span>`)}</dd>
      <dt>${I18n.t('parametres.etat_serveur.tailscale')}</dt><dd id="acces-tailscale">${texteTailscale(etat.tailscale)}</dd>
      <dt>${I18n.t('parametres.etat_serveur.copie_sauvegardes')}</dt><dd id="acces-copie">${texteCopie(info.copie_externe, v.copie_sauvegardes)}</dd>
      <dt>${I18n.t('parametres.etat_serveur.journal_serveur')}</dt><dd id="acces-journal">${lignes.length
        ? UI.html`<pre class="acces-journal">${lignes.join('\n')}</pre><span class="note">${I18n.t('parametres.etat_serveur.dernieres_lignes', { fichier: journal.fichier })}</span>`
        : I18n.t('parametres.etat_serveur.aucune_erreur_notee')}</dd>
    </dl>`;
  }

  // ===========================================================================================
  // 3. Sous-sections : une par étape de l'assistant, plus les réglages simples et l'IA
  // ===========================================================================================

  // Formulaire DOM (UI.champ pose les valeurs par propriété : un gabarit n'en garderait rien) ; `champs` :
  // [clé, type, valeur, options d'UI.champ].
  function formulaireDom(cle, champs) {
    const formulaire = UI.element(UI.html`<form class="form-colonne" id="acces-form-${cle}" novalidate></form>`);
    champs.forEach(([nom, type, valeur, options]) => {
      formulaire.appendChild(UI.champ({ nom: nom, type: type, libelle: libelles()[nom] }, valeur, Object.assign({ aide: aideOption(nom) }, options || {})));
    });
    return formulaire;
  }

  function resumePortee(v) {
    const portee = InstallationEtapes.LIBELLES_PORTEE[v.portee] || v.portee;
    if ((v.noms || []).length) return I18n.t('parametres.resume_portee.http_https_noms', { portee, port_http: v.port_http, port_https: v.port_https, join: v.noms.join(', ') });
    return I18n.t('parametres.resume_portee.http_https', { portee, port_http: v.port_http, port_https: v.port_https });
  }

  function resumeCertificat(v) {
    if (v.portee === 'ce-pc') return I18n.t('parametres.resume_certificat.sans_objet_prevo_reste');
    return v.certificat_auto ? I18n.t('parametres.resume_certificat.automatique_mkcert') : v.certificat ? I18n.t('parametres.resume_certificat.fichiers_pem') : v.mandataire ? I18n.t('parametres.resume_certificat.derriere_mandataire_tailscale_celui') : I18n.t('parametres.resume_certificat.regler');
  }

  function resumeDemarrage(v) {
    const demarrage = InstallationEtapes.LIBELLES_DEMARRAGE[v.demarrage] || v.demarrage;
    return v.veille_desactivee ? I18n.t('parametres.resume_demarrage.veille_empechee_secteur', { demarrage }) : I18n.t('parametres.resume_demarrage.veille_inchangee', { demarrage });
  }

  function resumeReglages(v) {
    if (v.demandeurs_avec_compte) {
      return I18n.t('parametres.resume_reglages.demandeurs_mot_passe_session', { session_heures: v.session_heures, session_longue_jours: v.session_longue_jours, invitation_heures: v.invitation_heures, quota_documents_mo: v.quota_documents_mo });
    }
    return I18n.t('parametres.resume_reglages.demandeurs_appareil_enrole_session', { session_heures: v.session_heures, session_longue_jours: v.session_longue_jours, invitation_heures: v.invitation_heures, quota_documents_mo: v.quota_documents_mo });
  }

  function resumeIa(v) {
    const fournisseur = libellesFournisseur()[v.ia_fournisseur] || v.ia_fournisseur;
    return v.ia_en_ligne ? I18n.t('parametres.resume_ia.ligne_autorise', { fournisseur, ia_url: v.ia_url }) : I18n.t('parametres.resume_ia.ligne_non', { fournisseur, ia_url: v.ia_url });
  }

  function formulaireReglages() {
    const v = valeurs();
    return formulaireDom('reglages', [
      ['demandeurs_avec_compte', 'booleen', v.demandeurs_avec_compte ? '1' : '0'],
      ['session_heures', 'entier', v.session_heures], ['session_longue_jours', 'entier', v.session_longue_jours],
      ['invitation_heures', 'entier', v.invitation_heures], ['quota_documents_mo', 'entier', v.quota_documents_mo],
    ]);
  }

  function lireReglages(zone) {
    const valeursLues = UI.lireFormulaire(UI.$('form', zone));
    const corps = { demandeurs_avec_compte: valeursLues.demandeurs_avec_compte === '1' };
    for (const cle of ['session_heures', 'session_longue_jours', 'invitation_heures', 'quota_documents_mo']) {
      const nombre = Donnees.nombre(valeursLues[cle]);
      if (nombre === null || !Number.isInteger(nombre)) return { probleme: I18n.t('parametres.lire_reglages.saisissez_nombre_entier', { libelle: libelles()[cle] }) };
      corps[cle] = nombre;
    }
    return corps;
  }

  function formulaireIa() {
    const v = valeurs();
    const fournisseurs = Object.entries(libellesFournisseur()).map(([cle, libelle]) => ({ valeur: cle, libelle }));
    return formulaireDom('ia', [
      ['ia_fournisseur', 'ref', v.ia_fournisseur, { liste: fournisseurs, obligatoire: true }],
      ['ia_url', 'texte', v.ia_url], ['ia_en_ligne', 'booleen', v.ia_en_ligne ? '1' : '0'],
    ]);
  }

  function noteCleIa() {
    const serveur = typeof Ia !== 'undefined' && Ia.reglagesServeur ? Ia.reglagesServeur() : null;
    if (serveur && serveur.cleReglee) {
      return UI.html`<p class="note" id="acces-ia-cle">${I18n.t('parametres.note_cle_ia.cle_service_reglee_pc', { aideOption: aideOption('ia_cle') })}</p>`;
    }
    return UI.html`<p class="note" id="acces-ia-cle">${I18n.t('parametres.note_cle_ia.cle_service_aucune_regle', { aideOption: aideOption('ia_cle') })}</p>`;
  }

  function lireIa(zone) {
    const valeursLues = UI.lireFormulaire(UI.$('form', zone));
    const url = String(valeursLues.ia_url || '').trim();
    if (!url) return { probleme: I18n.t('parametres.lire_ia.donnez_adresse_service_ia') };
    return { fournisseur: valeursLues.ia_fournisseur, url: url, en_ligne: valeursLues.ia_en_ligne === '1' };
  }

  function sansObjet(cle, v) {
    if (cle === 'certificat' && v.portee === 'ce-pc') return I18n.t('parametres.sans_objet.prevo_reste_pc_http');
    if (cle === 'tailscale' && v.portee !== 'dehors') return I18n.t('parametres.sans_objet.prevo_pas_joignable_hors');
    return '';
  }

  function autrement(contenu) {
    return contenu ? UI.html`<details class="installation-autrement"><summary>${I18n.t('parametres.autrement.regler_autrement')}</summary>
      <div class="installation-autrement-corps">${contenu}</div></details>` : '';
  }

  // Les sept sous-sections : clé, titre, étape de l'API, résumé des valeurs en cours, corps (champs + boutons) et lecture.
  function sections() {
    const v = valeurs();
    const windows = etat.systeme === 'windows';
    const enForce = etat.configuration || {};
    const liste = [
      { cle: 'portee', etape: 'portee', titre: I18n.t('parametres.sections.portee_ports_noms_acceptes'), resume: resumePortee(v) },
      { cle: 'certificat', etape: 'certificat', titre: I18n.t('parametres.sections.certificat_https'), resume: resumeCertificat(v) },
      { cle: 'tailscale', etape: 'tailscale', titre: I18n.t('parametres.sections.hors_atelier_tailscale'), resume: texteTailscale(etat.tailscale), propresBoutons: true },
      { cle: 'demarrage', etape: 'demarrage', titre: I18n.t('parametres.sections.demarrage_pc_veille'), resume: resumeDemarrage(v) },
      { cle: 'sauvegardes', etape: 'sauvegardes', titre: I18n.t('parametres.etat_serveur.copie_sauvegardes'), resume: v.copie_sauvegardes || I18n.t('parametres.sections.aucune_copie') },
      // Formulaires DOM, posés dans leur zone au rendu (rendreContenu) : construire() les crée.
      { cle: 'reglages', etape: 'reglages', titre: I18n.t('parametres.sections.comptes_demandeurs_durees_session'), resume: resumeReglages(v),
        corps: UI.html`<div class="acces-formulaire" data-formulaire="reglages"></div>`, construire: formulaireReglages, lire: lireReglages },
      { cle: 'ia', etape: 'ia', titre: I18n.t('parametres.sections.assistant_ia'), resume: resumeIa(v),
        corps: UI.html`<div class="acces-formulaire" data-formulaire="ia"></div>${noteCleIa()}`, construire: formulaireIa, lire: lireIa },
    ];
    liste.forEach((section) => {
      if (section.construire) return;
      const formulaire = formulaireDe(section.cle);
      section.formulaire = formulaire;
      section.corps = UI.html`${formulaire.champs}${autrement(formulaire.autrement)}`;
      section.lire = formulaire.lire;
      section.message = formulaire.message;
      if (section.cle === 'demarrage') {
        // Retrait (CS129) : « À la main » alors que la configuration en force démarre Prévo avec le PC.
        const retrait = (enForce.demarrage || 'aucun') !== 'aucun';
        section.lire = (zone) => {
          const corps = formulaire.lire(zone);
          return corps && retrait && corps.demarrage === 'aucun' ? Object.assign(corps, { retirer: true }) : corps;
        };
        section.corps = UI.html`${section.corps}${retrait && windows ? UI.html`<p class="note" id="acces-retrait-note">${I18n.t('parametres.sections.passer_main_retire_tache')}</p>` : ''}`;
      }
      if (section.cle === 'sauvegardes') {
        section.lire = (zone) => ({ dossier: UI.$('#inst-copie_sauvegardes', zone).value.trim() });
      }
    });
    return liste;
  }

  function rendreSection(section) {
    const v = valeurs();
    const raison = sansObjet(section.cle, v);
    const ouverte = ouvertes.has(section.cle);
    const corps = raison
      ? UI.html`<p class="installation-sautee">${I18n.t('parametres.rendre_section.sans_objet', { raison })}</p>`
      : UI.html`${section.corps}
        <p class="erreur-champ installation-erreur" id="acces-erreur-${section.cle}" role="alert" hidden></p>
        ${section.propresBoutons ? '' : UI.html`<div class="actions"><span class="espace"></span>
          <button type="button" class="btn btn-secondaire" data-enregistrer="${section.cle}">${UI.icone('valider')}${I18n.t('parametres.rendre_section.enregistrer_reglage')}</button></div>`}`;
    return UI.html`<details class="acces-section${raison ? ' sans-objet' : ''}" data-section="${section.cle}" ${UI.brut(ouverte ? 'open' : '')}>
      <summary><span class="acces-titre">${section.titre}</span><span class="acces-resume">${raison ? I18n.t('parametres.rendre_section.sans_objet_2') : section.resume}</span></summary>
      <div class="acces-corps">${corps}</div>
    </details>`;
  }

  // ===========================================================================================
  // 4. Modifications en attente : appliquer et relancer, annuler
  // ===========================================================================================

  function bandeauAttente() {
    if (!etat.brouillon) return '';
    return UI.html`<div class="alerte attention acces-attente" id="acces-attente"><div class="alerte-texte">
      <p>${I18n.html('parametres.bandeau_attente.modifications_attente_elles_prennent', { avertissementRelance: avertissementRelance() })}</p>
      <div class="actions">
        <button type="button" class="btn btn-primaire" id="acces-appliquer">${UI.icone('valider')}${I18n.t('parametres.bandeau_attente.appliquer_relancer')}</button>
        <button type="button" class="btn btn-fantome" id="acces-annuler">${I18n.t('commun.bouton.annuler')}</button>
      </div>
      <div class="installation-attente" id="acces-relance" hidden></div>
    </div></div>`;
  }

  async function appliquer(carte) {
    const reponse = await etape('terminer', {});
    if (!reponse.statut || reponse.statut >= 400) { montrerErreur('attente', reponse.message); return; }
    await attendreRelance(carte, reponse.donnees.relance, info.actif_depuis);
  }

  async function annuler(carte) {
    const reponse = await etape('annuler', {});
    if (!reponse.statut || reponse.statut >= 400) { montrerErreur('attente', reponse.message); return; }
    reprendre(reponse.donnees);
    UI.toast(I18n.t('parametres.annuler.modifications_annulees_rien_change'), 'info');
    await rafraichir(carte);
  }

  // Le serveur relancé répond à /api/info avec un autre « actif_depuis » (ou 401 : session à rouvrir) ; interrogé
  // toutes les 2 s, puis la page se recharge sur Paramètres ; message au bout de 60 s.
  async function serveurRelance(avant) {
    const reponse = await appeler('/api/info');
    if (reponse.statut === 401) return true;
    return reponse.statut === 200 && Boolean(reponse.donnees) && reponse.donnees.actif_depuis !== avant;
  }

  async function attendreRelance(carte, relance, avant) {
    const zone = UI.$('#acces-relance', carte);
    UI.$$('.btn', carte).forEach((bouton) => { bouton.disabled = true; });
    zone.hidden = false;
    UI.remplir(zone, UI.html`<p class="chargement" role="status">${I18n.t('parametres.attendre_relance.configuration_ecrite')} ${relance ? I18n.t('parametres.attendre_relance.prevo_relance_patientez')
      : I18n.t('parametres.attendre_relance.relancez_prevo_main_lancer')}</p>`);
    const debut = Date.now();
    while (Date.now() - debut < DELAI_RELANCE_MS) {
      await new Promise((suite) => { setTimeout(suite, INTERVALLE_RELANCE_MS); });
      try {
        if (await serveurRelance(avant)) { location.reload(); return; }
      } catch (erreur) { /* le serveur redémarre : on réessaie */ }
    }
    UI.remplir(zone, UI.html`<p class="erreur-champ" role="alert">${I18n.t('parametres.attendre_relance.serveur_revient_pas_relancez')}</p>`);
    UI.$$('.btn', carte).forEach((bouton) => { bouton.disabled = false; });
  }

  // ===========================================================================================
  // 5. Enregistrement d'une sous-section, Tailscale
  // ===========================================================================================

  function montrerErreur(cle, message) {
    const zone = UI.$('#acces-erreur-' + cle);
    if (!zone) { if (message) UI.toast(message, 'erreur'); return; }
    zone.textContent = message || '';
    zone.hidden = !message;
  }

  async function enregistrer(section, zone, carte) {
    montrerErreur(section.cle, '');
    const corps = section.lire ? section.lire(zone) : {};
    if (!corps) { montrerErreur(section.cle, section.message || I18n.t('parametres.enregistrer.completez_reglage')); return; }
    if (corps.probleme) { montrerErreur(section.cle, corps.probleme); return; }
    const brouillon = await assurerBrouillon(section.cle);
    if (!brouillon) return;
    const reponse = await etape(section.etape, corps);
    if (!reponse.statut || reponse.statut >= 400) { montrerErreur(section.cle, reponse.message); await jeterSiNeuf(brouillon); return; }
    reprendre(reponse.donnees);
    const donnees = reponse.donnees || {};
    if (corps.retirer && donnees.lance && !donnees.lance.ok) {
      montrerErreur(section.cle, donnees.lance.message
        ? I18n.t('parametres.enregistrer.retrait_ete_refuse_echoue', { lanceMessage: StockageServeur.texte(donnees.lance, 'message') })
        : I18n.t('parametres.enregistrer.retrait_ete_refuse_echoue_2', { lanceCode: donnees.lance.code }));
      return;
    }
    const echec = section.formulaire && section.formulaire.echec ? section.formulaire.echec(donnees) : '';
    if (echec) { montrerErreur(section.cle, echec); return; }
    const texte = section.formulaire && section.formulaire.reussite ? section.formulaire.reussite(donnees) : '';
    UI.toast(texte || I18n.t('parametres.enregistrer.reglage_enregistre_appliquer_relancer'), 'succes');
    rendreContenu(carte);
  }

  // « J'ai installé Tailscale et je suis connecté » : détecter puis appliquer (tailscale serve lancée par le serveur,
  // nom ajouté aux noms acceptés dans le brouillon), rappels, « unattended » sur clic.
  async function appliquerTailscale(zone, carte) {
    montrerErreur('tailscale', '');
    const brouillon = await assurerBrouillon('tailscale');
    if (!brouillon) return;
    const detection = await etape('tailscale', { action: 'detecter' });
    if (!detection.statut || detection.statut >= 400) { montrerErreur('tailscale', detection.message); await jeterSiNeuf(brouillon); return; }
    const d = detection.donnees.detection || {};
    const proposition = detection.donnees.proposition || {};
    if (!d.present || !d.connecte) {
      montrerErreur('tailscale', !d.present ? (d.raison ? I18n.t('parametres.appliquer_tailscale.tailscale_toujours_pas_detecte', { raison: StockageServeur.texte(d, 'raison') })
          : I18n.t('parametres.appliquer_tailscale.tailscale_toujours_pas_detecte_2'))
        : I18n.t('parametres.appliquer_tailscale.tailscale_installe_mais_pas'));
      await jeterSiNeuf(brouillon);
      return;
    }
    const application = await etape('tailscale', { action: 'appliquer' });
    if (!application.statut || application.statut >= 400) { montrerErreur('tailscale', application.message); await jeterSiNeuf(brouillon); return; }
    reprendre(application.donnees);
    etat.tailscale = Object.assign({}, etat.tailscale, d);
    rendreContenu(carte);
    const resultat = UI.$('#inst-tailscale-resultat', carte);
    if (!resultat) return;
    UI.remplir(resultat, UI.html`<p>${I18n.html('parametres.appliquer_tailscale.resultat_adresse', { message: StockageServeur.texte(application.donnees, 'message') || I18n.t('parametres.appliquer_tailscale.tailscale_publie_prevo'), adresse: application.donnees.adresse || '' })}</p>
      <ul>${(proposition.rappels || []).map((rappel) => UI.html`<li>${rappel}</li>`)}</ul>
      ${proposition.unattended ? UI.html`<div class="actions"><button type="button" class="btn btn-secondaire" id="inst-tailscale-unattended">${I18n.t('parametres.appliquer_tailscale.rester_connecte_meme_sans')}</button></div>` : ''}`);
    resultat.hidden = false;
    const unattended = UI.$('#inst-tailscale-unattended', resultat);
    if (unattended) {
      unattended.addEventListener('click', () => pendant(unattended, 'Tailscale sans session', async () => {
        const reponse = await etape('tailscale', { action: 'unattended' });
        if (!reponse.statut || reponse.statut >= 400) { montrerErreur('tailscale', reponse.message); return; }
        UI.toast(StockageServeur.texte(reponse.donnees, 'message') || I18n.t('parametres.appliquer_tailscale.fait'), 'succes');
        unattended.hidden = true;
      }));
    }
  }

  // ===========================================================================================
  // 6. Rendu de la carte et branchement
  // ===========================================================================================

  function rendreContenu(carte) {
    const contenu = UI.$('#acces-contenu', carte);
    if (!contenu) return;
    const liste = etat.configuration_presente ? sections() : [];
    UI.remplir(contenu, UI.html`${bandeauAttente()}${etatServeur()}
      ${liste.length ? UI.html`<h3 class="acces-intertitre">${I18n.t('parametres.rendre_contenu.reglages_acces')}</h3>
        <p class="note">${I18n.t('parametres.rendre_contenu.chaque_reglage_assistant_refait')}</p>
        <div class="acces-sections">${liste.map(rendreSection)}</div>`
        : UI.html`<p class="note" id="acces-sans-configuration">${I18n.html('parametres.rendre_contenu.tant_installation_pas_terminee')}</p>`}`);
    contenu.dataset.lu = '1';
    UI.$$('details.acces-section', contenu).forEach((details) => {
      details.addEventListener('toggle', () => { if (details.open) ouvertes.add(details.dataset.section); else ouvertes.delete(details.dataset.section); });
    });
    liste.forEach((section) => {
      const zone = UI.$('details[data-section="' + section.cle + '"]', contenu);
      if (!zone) return;
      zone.addEventListener('input', () => montrerErreur(section.cle, ''));
      const bouton = UI.$('[data-enregistrer]', zone);
      if (bouton) bouton.addEventListener('click', () => pendant(bouton, 'réglage de l\'accès', () => enregistrer(section, zone, carte)));
      const zoneFormulaire = UI.$('[data-formulaire]', zone);
      if (zoneFormulaire && section.construire) {
        const formulaire = section.construire();
        formulaire.addEventListener('submit', (evenement) => { evenement.preventDefault(); if (bouton) bouton.click(); });
        zoneFormulaire.appendChild(formulaire);
      }
      const plusTardSauvegardes = UI.$('#inst-sauvegardes-plus-tard', zone);
      if (plusTardSauvegardes) {
        plusTardSauvegardes.textContent = I18n.t('parametres.rendre_contenu.plus_copier');
        plusTardSauvegardes.addEventListener('click', () => pendant(plusTardSauvegardes, 'copie des sauvegardes', async () => {
          UI.$('#inst-copie_sauvegardes', zone).value = '';
          await enregistrer(section, zone, carte);
        }));
      }
      const plusTardTailscale = UI.$('#inst-tailscale-plus-tard', zone);
      if (plusTardTailscale) plusTardTailscale.hidden = true;
      const appliquerBouton = UI.$('#inst-tailscale-appliquer', zone);
      if (appliquerBouton) appliquerBouton.addEventListener('click', () => pendant(appliquerBouton, 'Tailscale', () => appliquerTailscale(zone, carte)));
    });
    const boutonAppliquer = UI.$('#acces-appliquer', contenu);
    if (boutonAppliquer) boutonAppliquer.addEventListener('click', () => pendant(boutonAppliquer, 'application des réglages', () => appliquer(carte)));
    const boutonAnnuler = UI.$('#acces-annuler', contenu);
    if (boutonAnnuler) boutonAnnuler.addEventListener('click', () => pendant(boutonAnnuler, 'annulation des réglages', () => annuler(carte)));
  }

  async function rafraichir(carte) {
    const contenu = UI.$('#acces-contenu', carte);
    const message = await lireTout();
    if (!/^#\/parametres/.test(location.hash) || !contenu || !contenu.isConnected) return;
    if (message) { UI.remplir(contenu, UI.html`<p class="erreur-champ" role="alert">${message}</p>`); contenu.dataset.lu = '1'; return; }
    rendreContenu(carte);
  }

  /** Carte « Accès et installation » (fragment UI.html) ; '' hors du PC serveur, du mode serveur ou du responsable. */
  function carteAcces() {
    if (!visible()) return '';
    return UI.html`<article class="carte" id="carte-acces">
      <div class="entete-carte"><h2>${I18n.t('parametres.carte_acces.acces_installation')}</h2>
        <button type="button" class="btn btn-secondaire" id="acces-actualiser">${UI.icone('actualiser')}${I18n.t('commun.bouton.actualiser')}</button></div>
      <p class="note">${I18n.html('parametres.carte_acces.assistant_installation_regle_refait')}</p>
      <div id="acces-contenu"><p class="chargement" role="status">${I18n.t('parametres.carte_acces.lecture_etat_serveur')}</p></div>
    </article>`;
  }

  /** Branche la carte (lecture de l'état puis rendu) ; `pendantAction(bouton, contexte, action)` : outil de parametres.js. */
  function brancherAcces(conteneur, pendantAction) {
    const carte = UI.$('#carte-acces', conteneur);
    if (!carte) return;
    pendant = pendantAction;
    ouvertes = new Set();
    const actualiser = UI.$('#acces-actualiser', carte);
    actualiser.addEventListener('click', () => pendant(actualiser, 'état du serveur', () => rafraichir(carte)));
    rafraichir(carte);
  }

  return { carteAcces, brancherAcces };
})();

// Relais de parametres.js (comme parametres-solo.js et parametres-sauvegardes.js) : la carte et son branchement.
Object.assign(Parametres.interne, { carteAcces: ParametresAcces.carteAcces, brancherAcces: ParametresAcces.brancherAcces });
