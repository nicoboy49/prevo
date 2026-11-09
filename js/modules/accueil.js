'use strict';
// Accueil (1/2) : écran d'arrivée (#/accueil), adapté au profil (brief §9 E1, ARCHITECTURE.md §10 et §14.6).
// Ce fichier : calculs des compteurs, accueils du technicien et du demandeur, carte de connexion,
// affichage ; l'accueil du responsable (« bento », T90) est dans accueil-bento.js, qui complète Accueil.
//
//   Responsable : tuile de synthèse, « À traiter en premier », compteurs (DI à traiter, OT en retard,
//                 P1 ouverts, préventifs de la semaine), rapport du mois écoulé, 5 DI à traiter et 5 OT
//                 en retard, tuiles « à surveiller » (articles à commander ; contrôles sous 30 jours et
//                 habilitations à renouveler, lot 3 ; suggestions de préventif, lot 3 bis, §16.6 ; garanties
//                 et contrats, 2.2), une alerte si « Contrôle de la base » signale des erreurs (accueil-bento.js).
//   Technicien  : gros bouton « Signaler », les trois indicateurs des contrôles et de l'équipe (contrôles
//                 sous 30 jours, habilitations à renouveler, réserves en retard depuis la 2.2) et la liste
//                 de ses OT ouverts : d'abord ses préventifs de la semaine (ou la mention qu'il n'en a pas),
//                 puis ses autres OT.
//   Demandeur   : gros bouton « Signaler un problème » et ses 5 dernières demandes (statut,
//                 motif de refus).
//   Tous, en mode serveur et sauf sur téléphone (D31) : carte « Connecter un téléphone » (QR code
//   de l'adresse réseau du PC) — sur le téléphone, on est déjà connecté.
//
// Définitions des compteurs (ARCHITECTURE.md §10 et §14.6) :
//   DI à traiter             = demande au statut « Nouvelle » ;
//   OT en retard             = statut ni clôturé ni annulé ET date prévue avant aujourd'hui ;
//   P1 ouvert                = priorité P1 ET statut ni clôturé ni annulé ;
//   Préventif de la semaine  = OT d'origine « préventif », ni clôturé ni annulé, date prévue au
//                              plus tard le dimanche de la semaine en cours (retards compris) ;
//   Article à commander      = Magasin.aCommander() (article actif, stock ≤ point de commande) ;
//   Contrôle sous 30 jours   = Controles.sous30Jours() (équipement suivi, prochaine date inconnue
//                              ou dans les 30 jours, retards compris ; lot 3, §15.9) ;
//   Habilitation à renouveler = Equipe.aRenouveler() (technicien actif, habilitation qui compte
//                              échue ou à échéance dans les 60 jours ; lot 3, §15.9) ;
//   Réserve en retard        = Controles.reservesEnRetard() (réserve ouverte d'un contrôle d'équipement
//                              suivi, échéance de levée passée ; sans échéance saisie, 30 jours après le
//                              contrôle, D187 ; 2.2, CS170). Les observations reprises de la 2.1 n'ont pas
//                              d'échéance saisie : presque toutes le sont au premier lancement, d'où le détail
//                              « échéance par défaut passée (30 jours après le contrôle) ».
//   Échéances des garanties  = Garanties.aEcheance() (2.2, CS173 ; responsable seulement) : garanties qui se
//   et des contrats            terminent dans le délai d'alerte (réglage alerte_echeances_jours, 60 jours par
//                              défaut, D187), contrats en alerte (« à décider » avant la date limite de
//                              résiliation, reconduction tacite ; « se termine bientôt » avant la fin, sans
//                              reconduction tacite : jamais « à décider », T463) et contrats aux dates à mettre
//                              à jour. Module Garanties absent (pages de test) : null.

const Accueil = (() => {

  const STATUTS_OT_FERMES = ['Clôturé techniquement', 'Clôturé administrativement', 'Annulé'];
  const NOMBRE_LIGNES = 5;             // lignes montrées dans les listes du responsable et du demandeur
  const NOMBRE_OT_TECHNICIEN = 15;     // un technicien voit tous ses OT ouverts, jusqu'à ce nombre
  const MILLISECONDES_PAR_JOUR = 24 * 60 * 60 * 1000;
  const ORIGINE_PREVENTIF = 'préventif';
  const LIEN_RESERVES_EN_RETARD = '#/controles?filtre=reserves-en-retard';

  // Adresses du serveur lues une première fois puis gardées (évite un aller-retour à chaque affichage).
  let adressesEnMemoire = null;
  let porteOuverte = false;       // lot 7 : le serveur a sa porte d'entrée (deux écouteurs, hors de « ce PC »)
  let cePcSeulement = false;      // recette du lot 7 : portée « ce PC », aucun téléphone ne joint Prévo

  // ===========================================================================================
  // 1. Calculs (fonctions pures sur les lignes des tables, exposées pour les tests)
  // ===========================================================================================

  function otOuvert(ot) {
    return !STATUTS_OT_FERMES.includes(ot.statut);
  }

  function otEnRetard(ot, aujourdhui) {
    return otOuvert(ot) && ot.date_prevue !== '' && ot.date_prevue < aujourdhui;
  }

  function p1Ouvert(ot) {
    return ot.priorite === 'P1' && otOuvert(ot);
  }

  /** Dimanche de la semaine (du lundi au dimanche) d'une date ISO : '2026-10-20' (mardi) → '2026-10-25'. */
  function dimancheDe(dateIso) {
    const [annee, mois, jour] = dateIso.split('-').map(Number);
    const date = new Date(Date.UTC(annee, mois - 1, jour));        // en UTC : pas de piège d'heure d'été
    date.setUTCDate(date.getUTCDate() + (7 - date.getUTCDay()) % 7);  // getUTCDay() : 0 = dimanche
    return date.toISOString().slice(0, 10);
  }

  /** OT préventif ouvert à faire au plus tard le `dimanche` donné (retards compris). */
  function preventifDeLaSemaine(ot, dimanche) {
    const prevue = String(ot.date_prevue || '').slice(0, 10);
    return ot.origine === ORIGINE_PREVENTIF && otOuvert(ot) && prevue !== '' && prevue <= dimanche;
  }

  /**
   * Les listes qui donnent les compteurs de l'accueil :
   * { diATraiter, otEnRetard, p1Ouverts, preventifsSemaine } (lignes de demandes et d'OT),
   * articlesACommander (éléments de Magasin.aCommander() : { article, stock, pointCommande, … }),
   * controlesSous30j, habilitationsARenouveler et reservesEnRetard (éléments de
   * Controles.reservesEnRetard() : { reserve, controle, etat }, l'échéance la plus ancienne d'abord),
   * echeances (Garanties.aEcheance() : { garanties, contrats, aMettreAJour }, lignes ; null sans le module).
   */
  function calculerCompteurs() {
    const aujourdhui = Donnees.aujourdhui();
    const dimanche = dimancheDe(aujourdhui);
    const ordres = Donnees.lignes('ordres_travail');
    return {
      diATraiter: Donnees.lignes('demandes').filter((di) => di.statut === 'Nouvelle'),
      otEnRetard: ordres.filter((ot) => otEnRetard(ot, aujourdhui)),
      p1Ouverts: ordres.filter(p1Ouvert),
      preventifsSemaine: ordres.filter((ot) => preventifDeLaSemaine(ot, dimanche)),
      articlesACommander: Magasin.aCommander(),
      // Lot 3 (§15.9) : les règles des contrôles et de l'équipe, appelées au moment du calcul
      // (leurs fichiers sont chargés après celui-ci).
      controlesSous30j: Controles.sous30Jours(aujourdhui),
      habilitationsARenouveler: Equipe.aRenouveler(aujourdhui),
      // 2.2 (CS170) : réserves des contrôles dont l'échéance de levée est passée (controles-reserves.js).
      reservesEnRetard: Controles.reservesEnRetard(aujourdhui),
      // 2.2 (CS173) : garanties et contrats à échéance (garanties-regles.js, chargé après ce fichier ; absent des
      // pages de test qui ne chargent pas tous les modules).
      echeances: typeof Garanties !== 'undefined' ? Garanties.aEcheance(aujourdhui) : null,
    };
  }

  /**
   * Détail des réserves en retard (éléments de Controles.reservesEnRetard), sous leur nombre : aucune → « aucune
   * échéance de levée passée » ; toutes à l'échéance saisie → « échéance de levée passée » ; toutes à l'échéance
   * par défaut (réserves reprises de la 2.1 ou saisies sans échéance, D187) → « échéance par défaut passée
   * (30 jours après le contrôle) » ; sinon « dont n à l'échéance par défaut (30 jours après le contrôle) ».
   */
  function detailReservesEnRetard(reserves) {
    const parDefaut = reserves.filter((element) => element.etat.parDefaut).length;
    const jours = Controles.interne.DELAI_LEVEE_PAR_DEFAUT_JOURS;
    if (!reserves.length) return I18n.t('accueil.detail_reserves_en_retard.aucune_echeance_passee');
    if (!parDefaut) return I18n.t('accueil.detail_reserves_en_retard.echeance_passee');
    if (parDefaut === reserves.length) return I18n.t('accueil.detail_reserves_en_retard.echeance_par_defaut_passee', { jours });
    return I18n.t('accueil.detail_reserves_en_retard.dont_echeance_par_defaut', { n: parDefaut, jours });
  }

  /** Nombre de jours entre deux dates ISO (AAAA-MM-JJ) : combien de jours après `debut` tombe `fin`. */
  function joursEntre(debut, fin) {
    const [anneeD, moisD, jourD] = debut.split('-').map(Number);
    const [anneeF, moisF, jourF] = fin.split('-').map(Number);
    return Math.round((Date.UTC(anneeF, moisF - 1, jourF) - Date.UTC(anneeD, moisD - 1, jourD)) / MILLISECONDES_PAR_JOUR);
  }

  function pluriel(nombre, singulier, plurielTexte) {
    return nombre + ' ' + (nombre > 1 ? (plurielTexte || singulier + 's') : singulier);
  }

  // « EQ-0005 » → « PO-02 — Pompe d'alimentation » (repli : l'identifiant brut).
  function libelleEquipement(equipementId) {
    const equipement = Donnees.trouver('equipements', equipementId);
    if (!equipement) return equipementId || '—';
    return equipement.repere + (equipement.designation ? ' — ' + equipement.designation : '');
  }

  // ===========================================================================================
  // 2. Petits morceaux d'écran
  // ===========================================================================================

  // Impact d'une demande : couleur de la charte ET libellé.
  function badgeImpact(impact) {
    const tons = { 'sécurité': 'ko', 'arrêt': 'attention', 'dégradé': 'info', 'gêne': 'neutre' };
    return UI.html`<span class="badge ${tons[impact] || 'neutre'}">${Schema.libelleValeur('demandes', 'impact', impact) || '—'}</span>`;
  }

  function carteDemande(di, avecMotif) {
    const motif = avecMotif && di.motif_decision && (di.statut === 'Refusée' || di.statut === 'Différée')
      ? UI.html`<p class="accueil-motif"><b>${di.statut === 'Refusée' ? I18n.t('accueil.carte_demande.motif_refus') : I18n.t('accueil.carte_demande.motif_report')} :</b> ${di.motif_decision}</p>`
      : '';
    return UI.html`<li><a href="#/di/${encodeURIComponent(di.id)}" class="${di.impact === 'sécurité' ? 'accent-p1' : ''}">
      <div class="carte-tete"><b>${di.id}</b>${avecMotif ? UI.badgeValeur('demandes', 'statut', di.statut) : badgeImpact(di.impact)}</div>
      <div class="carte-titre">${di.symptome}</div>
      <div class="carte-meta"><span>${libelleEquipement(di.equipement_id)}</span>${avecMotif ? '' : UI.html`<span>${di.demandeur}</span>`}<span>${UI.dateHeureFr(di.date_heure)}</span></div>
      ${motif}
    </a></li>`;
  }

  function carteOrdre(ot, aujourdhui) {
    const enRetard = otEnRetard(ot, aujourdhui);
    const retard = enRetard ? UI.html`<span class="accueil-retard">${I18n.t('accueil.carte_ordre.retard_jours', { n: joursEntre(ot.date_prevue, aujourdhui) })}</span>` : '';
    const prevu = ot.date_prevue ? UI.html`<span>${I18n.t('accueil.carte_ordre.prevu_date_prevue', { date_prevue: UI.dateFr(ot.date_prevue) })}</span>` : UI.html`<span>${I18n.t('accueil.carte_ordre.pas_date_prevue')}</span>`;
    return UI.html`<li><a href="#/ot/${encodeURIComponent(ot.id)}" class="${ot.priorite === 'P1' ? 'accent-p1' : (ot.priorite === 'P2' ? 'accent-p2' : '')}">
      <div class="carte-tete"><b>${ot.id}</b>${UI.badgePriorite(ot.priorite)}${UI.badgeValeur('ordres_travail', 'statut', ot.statut)}</div>
      <div class="carte-titre">${ot.titre}</div>
      <div class="carte-meta"><span>${libelleEquipement(ot.equipement_id)}</span>${prevu}${retard}</div>
    </a></li>`;
  }

  // Une carte « titre + liste de cartes + lien vers la liste complète ».
  function carteListe(titre, nombreTotal, elements, lien, libelleLien, videTitre, videTexte, videIcone) {
    const reste = nombreTotal - elements.length;
    return UI.html`<article class="carte">
      <div class="entete-carte"><h2>${titre}</h2><span class="badge ${nombreTotal > 0 ? 'info' : 'neutre'}">${nombreTotal}</span></div>
      ${elements.length
        ? UI.html`<ul class="liste-cartes">${elements}</ul>`
        : UI.vide(videTitre, videTexte, videIcone)}
      ${lien ? UI.html`<p class="accueil-voir-tout"><a href="${lien}">${reste > 0 ? I18n.t('accueil.carte_liste.libelle_lien_reste_plus', { libelleLien, reste }) : libelleLien}</a></p>` : ''}
    </article>`;
  }

  function indicateur(lien, classe, libelle, chiffre, complement) {
    return UI.html`<a href="${lien}" class="${classe}">
      <div class="lib">${libelle}</div><div class="chiffre">${chiffre}</div><div class="comp">${complement}</div>
    </a>`;
  }

  // Lot 3 (§15.9) : contrôles réglementaires sous 30 jours et habilitations à renouveler ; 2.2 (CS170) :
  // réserves en retard. La couleur du trait suit l'état (rouge : un contrôle ou une réserve en retard ;
  // ambre : une habilitation échue), toujours avec le texte qui le dit.
  function indicateursConformite(compteurs, aujourdhui) {
    const reserves = compteurs.reservesEnRetard;
    const controlesEnRetard = compteurs.controlesSous30j
      .filter((controle) => Controles.etat(controle, aujourdhui).statut === 'en retard').length;
    const habilitationsEchues = compteurs.habilitationsARenouveler
      .filter((element) => element.etat.statut === 'échue').length;
    return UI.html`${indicateur('#/controles?filtre=30j', controlesEnRetard ? 'rouge' : '', I18n.t('accueil.indicateurs_conformite.controles_sous_30'),
      compteurs.controlesSous30j.length, controlesEnRetard ? I18n.t('accueil.indicateurs_conformite.dont_retard', { controlesEnRetard }) : I18n.t('accueil.indicateurs_conformite.controles_reglementaires'))}
      ${indicateur('#/equipe?filtre=a-renouveler', habilitationsEchues ? 'ambre' : '', I18n.t('accueil.indicateurs_conformite.habilitations_renouveler'),
      compteurs.habilitationsARenouveler.length,
      habilitationsEchues ? I18n.t('accueil.indicateurs_conformite.dont_echues', { n: habilitationsEchues }) : I18n.t('accueil.indicateurs_conformite.60_jours'))}
      ${indicateur(LIEN_RESERVES_EN_RETARD, reserves.length ? 'rouge' : '', I18n.t('accueil.indicateurs_conformite.reserves_en_retard'),
      reserves.length, detailReservesEnRetard(reserves))}`;
  }

  // Alerte du responsable : « Contrôle de la base » a trouvé des erreurs.
  function alerteControle() {
    const erreurs = Donnees.problemes().filter((p) => p.gravite === 'erreur').length;
    if (erreurs === 0) return '';
    // UI.bandeau rend un élément DOM : on le convertit en fragment sûr pour l'insérer dans un gabarit.
    return UI.brut(UI.bandeau('important', UI.html`${I18n.html('accueil.alerte_controle.erreurs_corriger', { n: erreurs })}`).outerHTML);
  }

  // Base sans équipement (responsable) : invitation à reprendre les listes existantes (lot 5, §18.9).
  function carteBaseVide() {
    if (Donnees.lignes('equipements').length) return '';
    return UI.html`<article class="carte" id="carte-import-accueil">
      <div class="entete-carte"><h2>${I18n.t('accueil.carte_base_vide.parc_vide')}</h2></div>
      <p>${I18n.t('accueil.carte_base_vide.reprenez_listes_existantes_equipements')}</p>
      <div class="actions"><a class="btn btn-primaire" id="lien-import-accueil" href="#/import">${UI.icone('document')}${I18n.t('accueil.carte_base_vide.importer_donnees')}</a></div>
    </article>`;
  }

  // ===========================================================================================
  // 3. Connexion d'un téléphone (mode serveur)
  // ===========================================================================================

  async function lireAdressesReseau() {
    if (adressesEnMemoire) return adressesEnMemoire;
    let adresses = [];
    try {
      const informations = await App.adaptateur.info();
      adresses = (informations && informations.adressesReseau) || [];
      adressesEnMemoire = adresses;
      // Lot 7 (§22.6) : hors de « ce PC », l'adresse est celle de la porte d'entrée, qui conduit le téléphone à
      // l'application en https après « Faites confiance au PC atelier » (une fois par téléphone).
      porteOuverte = Boolean(informations && informations.porte);
      cePcSeulement = Boolean(informations && informations.cePcSeulement);
    } catch (erreur) {
      console.warn('Prévo : adresses réseau du serveur inconnues (' + (erreur && erreur.message) + ').', erreur);
    }
    return adresses;
  }

  function carteConnexion(adresses) {
    // Recette du lot 7 : en portée « ce PC », Prévo n'écoute que sur ce PC : pas de QR qu'aucun téléphone n'ouvrirait.
    if (cePcSeulement) {
      return UI.html`<article class="carte" id="carte-connexion">
        <div class="entete-carte"><h2>${I18n.t('accueil.carte_connexion.connecter_telephone')}</h2></div>
        <div class="encadre info" id="connexion-ce-pc">
          ${I18n.html('accueil.carte_connexion.prevo_joignable_pc_instant')}
        </div>
      </article>`;
    }
    if (adresses.length === 0) {
      return UI.html`<article class="carte" id="carte-connexion">
        <div class="entete-carte"><h2>${I18n.t('accueil.carte_connexion.connecter_telephone')}</h2></div>
        <div class="encadre attention">
          ${I18n.html('accueil.carte_connexion.aucune_adresse_reseau_detectee')}
        </div>
        <p class="note">${I18n.t('accueil.carte_connexion.attendant_prevo_reste_utilisable')}</p>
      </article>`;
    }
    const autres = adresses.slice(1);
    return UI.html`<article class="carte" id="carte-connexion">
      <div class="entete-carte"><h2>${I18n.t('accueil.carte_connexion.connecter_telephone')}</h2></div>
      <div class="accueil-connexion">
        <div class="qr" id="qr-connexion">${UI.qrSvg(adresses[0], 176)}</div>
        <div class="accueil-connexion-texte">
          <p>${I18n.t('accueil.carte_connexion.scannez_qr_code_appareil')}</p>
          <p>${I18n.html('accueil.carte_connexion.saisissez_adresse', { adresse: adresses[0] })}</p>
          ${autres.length ? UI.html`<p class="note">${I18n.t('accueil.carte_connexion.autres_adresses_pc', { join: autres.join(' · ') })}</p>` : ''}
          <ul class="accueil-rappels">
            <li>${I18n.html('accueil.carte_connexion.telephone_doit_etre_meme')}</li>
            <li>${I18n.html('accueil.carte_connexion.premier_lancement_windows_demande')}</li>
            ${porteOuverte ? UI.html`<li>${I18n.html('accueil.carte_connexion.premiere_fois_telephone_affiche')}</li>` : ''}
          </ul>
        </div>
      </div>
    </article>`;
  }

  // ===========================================================================================
  // 4. Accueils du technicien et du demandeur (celui du responsable : accueil-bento.js)
  // ===========================================================================================

  // Carte du technicien : ses préventifs de la semaine d'abord (ou la mention qu'il n'en a pas),
  // puis ses autres OT ouverts. Un OT n'apparaît qu'une fois.
  function carteOrdresTechnicien(mesOrdres, idsPreventifs, aujourdhui) {
    const preventifs = mesOrdres.filter((ot) => idsPreventifs.has(ot.id));
    const autres = mesOrdres.filter((ot) => !idsPreventifs.has(ot.id));
    const montres = autres.slice(0, NOMBRE_OT_TECHNICIEN);
    const reste = autres.length - montres.length;
    return UI.html`<article class="carte accueil-mes-ordres">
      <div class="entete-carte"><h2>${I18n.t('accueil.carte_ordres_technicien.mes_ordres_travail_ouverts')}</h2><span class="badge ${mesOrdres.length > 0 ? 'info' : 'neutre'}">${mesOrdres.length}</span></div>
      <h3 class="accueil-sous-titre">${I18n.t('accueil.carte_ordres_technicien.mes_preventifs_semaine')} <span class="badge ${preventifs.length > 0 ? 'info' : 'neutre'}">${preventifs.length}</span></h3>
      ${preventifs.length
        ? UI.html`<ul class="liste-cartes accueil-preventifs">${preventifs.map((ot) => carteOrdre(ot, aujourdhui))}</ul>`
        : UI.html`<p class="muted accueil-preventifs-vide">${I18n.t('accueil.carte_ordres_technicien.aucun_preventif_faire_ici', { dimancheDe: UI.dateFr(dimancheDe(aujourdhui)) })}</p>`}
      <h3 class="accueil-sous-titre">${I18n.html('accueil.carte_ordres_technicien.autres_ordres_travail', { nbAutres: autres.length })}</h3>
      ${montres.length
        ? UI.html`<ul class="liste-cartes">${montres.map((ot) => carteOrdre(ot, aujourdhui))}</ul>`
        : UI.vide(I18n.t('accueil.carte_ordres_technicien.aucun_autre_ordre_travail'), I18n.t('accueil.carte_ordres_technicien.rien_autre_affecte_moment'), 'ordres')}
      <p class="accueil-voir-tout"><a href="#/ot">${reste > 0 ? I18n.t('accueil.carte_ordres_technicien.voir_tous_ordres_travail', { reste }) : I18n.t('accueil.carte_ordres_technicien.voir_tous_ordres_travail_2')}</a></p>
    </article>`;
  }

  function accueilTechnicien() {
    const aujourdhui = Donnees.aujourdhui();
    const identifiant = App.profil.technicienId;
    const rangPriorite = { P1: 1, P2: 2, P3: 3, P4: 4 };
    const mesOrdres = Donnees.lignes('ordres_travail')
      .filter((ot) => ot.technicien_id === identifiant && otOuvert(ot))
      .sort((a, b) => (rangPriorite[a.priorite] || 9) - (rangPriorite[b.priorite] || 9)
        || (a.date_prevue || '9999').localeCompare(b.date_prevue || '9999'));
    // Ses préventifs de la semaine : même définition que le compteur du responsable.
    const dimanche = dimancheDe(aujourdhui);
    const idsPreventifs = new Set(mesOrdres.filter((ot) => preventifDeLaSemaine(ot, dimanche)).map((ot) => ot.id));
    const compteurs = calculerCompteurs();
    return UI.html`
      <div class="entete-page"><div>
        <h1>${I18n.t('accueil.accueil_technicien.accueil')}</h1>
        <p>${I18n.t('accueil.accueil_technicien.bonjour_voici_ordres_travail', { profilNom: App.profil.nom })}</p>
      </div></div>
      <div class="pile-gros accueil-signaler">
        <a href="#/di/nouvelle" class="btn btn-primaire btn-gros">${UI.icone('ajouter')}<span>${I18n.html('accueil.accueil_technicien.signaler_probleme_creer_demande')}</span></a>
      </div>
      <div class="instruments accueil-instruments accueil-instruments-technicien">${indicateursConformite(compteurs, aujourdhui)}</div>
      ${carteOrdresTechnicien(mesOrdres, idsPreventifs, aujourdhui)}`;
  }

  function accueilDemandeur() {
    const nom = App.profil.nom.trim().toLowerCase();
    const mesDemandes = Donnees.lignes('demandes')
      .filter((di) => di.demandeur.trim().toLowerCase() === nom)
      .sort((a, b) => b.date_heure.localeCompare(a.date_heure));
    return UI.html`
      <div class="entete-page"><div>
        <h1>${I18n.t('accueil.accueil_technicien.accueil')}</h1>
        <p>${I18n.t('accueil.accueil_demandeur.bonjour_equipement_fonctionne_pas', { profilNom: App.profil.nom })}</p>
      </div></div>
      <div class="pile-gros accueil-signaler">
        <a href="#/di/nouvelle" class="btn btn-primaire btn-gros">${UI.icone('ajouter')}<span>${I18n.html('accueil.accueil_technicien.signaler_probleme_creer_demande')}</span></a>
      </div>
      ${carteListe(I18n.t('accueil.accueil_demandeur.mes_dernieres_demandes'), mesDemandes.length,
        mesDemandes.slice(0, NOMBRE_LIGNES).map((di) => carteDemande(di, true)),
        '#/di', I18n.t('accueil.accueil_demandeur.voir_toutes_mes_demandes'),
        I18n.t('accueil.accueil_demandeur.aucune_demande_moment'), I18n.t('accueil.accueil_demandeur.demandes_creez_apparaitront_ici'), 'demandes')}`;
  }

  // ===========================================================================================
  // 5. Écran
  // ===========================================================================================

  async function afficher(conteneur) {
    // Carte « Connecter un téléphone » : en mode serveur, sauf sur un téléphone (D31 : il est déjà
    // connecté, et le QR ne se scanne pas sur son propre écran). On lit l'adresse réseau AVANT
    // d'écrire l'écran (un seul remplissage).
    const avecConnexion = App.mode === 'serveur' && !UI.estTelephone();
    const adresses = avecConnexion ? await lireAdressesReseau() : null;
    // Si l'utilisateur est parti ailleurs pendant l'attente, on n'écrase pas son nouvel écran.
    if (!/^#\/accueil/.test(location.hash)) return;

    const connexion = adresses === null ? '' : carteConnexion(adresses);
    // Responsable : accueil « bento » (accueil-bento.js, chargé après ce fichier : appelé au moment de
    // l'affichage), avec la tuile du rapport du mois écoulé (lot 3, §15.9).
    if (App.estResponsable()) { Accueil.afficherResponsable(conteneur, connexion); return; }
    const contenu = App.estTechnicien() ? accueilTechnicien() : accueilDemandeur();
    UI.remplir(conteneur, UI.html`${contenu}${connexion}`);
  }

  // App est chargé après les modules : l'écran est enregistré une fois la page lue.
  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'accueil', route: /^#\/accueil$/, get titre() { return I18n.t('accueil.accueil_technicien.accueil'); },
      menu: { get libelle() { return I18n.t('accueil.accueil_technicien.accueil'); }, icone: 'accueil', ordre: 10 },
      profils: ['demandeur', 'technicien', 'responsable'],
      // Les compteurs viennent de demandes et ordres_travail ; l'alerte de contrôle peut venir de
      // n'importe quelle table (sauf le journal, qui change à chaque action).
      tables: Schema.nomsTables().filter((nomTable) => nomTable !== 'journal'),
      afficher,
    });
  });

  return {
    afficher, calculerCompteurs, otEnRetard, p1Ouvert, dimancheDe, preventifDeLaSemaine,
    // Pour accueil-bento.js seulement (pas une API : aucun autre module ni test ne s'en sert).
    interne: { otOuvert, joursEntre, pluriel, libelleEquipement, badgeImpact, alerteControle, carteBaseVide,
      detailReservesEnRetard, NOMBRE_LIGNES, ORIGINE_PREVENTIF, LIEN_RESERVES_EN_RETARD },
  };
})();
