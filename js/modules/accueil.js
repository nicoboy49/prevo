'use strict';
// Accueil (1/2) : écran d'arrivée (#/accueil), adapté au profil (brief §9 E1, ARCHITECTURE.md §10 et §14.6).
// Ce fichier : calculs des compteurs, accueils du technicien et du demandeur, carte de connexion,
// affichage ; l'accueil du responsable (« bento », T90) est dans accueil-bento.js, qui complète Accueil.
//
//   Responsable : tuile de synthèse, « À traiter en premier », compteurs (DI à traiter, OT en retard,
//                 P1 ouverts, préventifs de la semaine), rapport du mois écoulé, 5 DI à traiter et 5 OT
//                 en retard, tuiles « à surveiller » (articles à commander ; contrôles sous 30 jours et
//                 habilitations à renouveler, lot 3 ; suggestions de préventif, lot 3 bis, §16.6), une
//                 alerte si « Contrôle de la base » signale des erreurs (accueil-bento.js).
//   Technicien  : gros bouton « Signaler », les deux indicateurs du lot 3 (contrôles sous 30 jours,
//                 habilitations à renouveler) et la liste de ses OT ouverts : d'abord ses préventifs
//                 de la semaine (ou la mention qu'il n'en a pas), puis ses autres OT.
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
//                              échue ou à échéance dans les 60 jours ; lot 3, §15.9).

const Accueil = (() => {

  const STATUTS_OT_FERMES = ['Clôturé techniquement', 'Clôturé administrativement', 'Annulé'];
  const NOMBRE_LIGNES = 5;             // lignes montrées dans les listes du responsable et du demandeur
  const NOMBRE_OT_TECHNICIEN = 15;     // un technicien voit tous ses OT ouverts, jusqu'à ce nombre
  const MILLISECONDES_PAR_JOUR = 24 * 60 * 60 * 1000;
  const ORIGINE_PREVENTIF = 'préventif';

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
   * { diATraiter, otEnRetard, p1Ouverts, preventifsSemaine } (lignes de demandes et d'OT) et
   * articlesACommander (éléments de Magasin.aCommander() : { article, stock, pointCommande, … }).
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
    };
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
    return UI.html`<span class="badge ${tons[impact] || 'neutre'}">${impact || '—'}</span>`;
  }

  function carteDemande(di, avecMotif) {
    const motif = avecMotif && di.motif_decision && (di.statut === 'Refusée' || di.statut === 'Différée')
      ? UI.html`<p class="accueil-motif"><b>${di.statut === 'Refusée' ? 'Motif du refus' : 'Motif du report'} :</b> ${di.motif_decision}</p>`
      : '';
    return UI.html`<li><a href="#/di/${encodeURIComponent(di.id)}" class="${di.impact === 'sécurité' ? 'accent-p1' : ''}">
      <div class="carte-tete"><b>${di.id}</b>${avecMotif ? UI.badgeStatut(di.statut) : badgeImpact(di.impact)}</div>
      <div class="carte-titre">${di.symptome}</div>
      <div class="carte-meta"><span>${libelleEquipement(di.equipement_id)}</span>${avecMotif ? '' : UI.html`<span>${di.demandeur}</span>`}<span>${UI.dateHeureFr(di.date_heure)}</span></div>
      ${motif}
    </a></li>`;
  }

  function carteOrdre(ot, aujourdhui) {
    const enRetard = otEnRetard(ot, aujourdhui);
    const retard = enRetard ? UI.html`<span class="accueil-retard">en retard de ${pluriel(joursEntre(ot.date_prevue, aujourdhui), 'jour')}</span>` : '';
    const prevu = ot.date_prevue ? UI.html`<span>prévu le ${UI.dateFr(ot.date_prevue)}</span>` : UI.html`<span>pas de date prévue</span>`;
    return UI.html`<li><a href="#/ot/${encodeURIComponent(ot.id)}" class="${ot.priorite === 'P1' ? 'accent-p1' : (ot.priorite === 'P2' ? 'accent-p2' : '')}">
      <div class="carte-tete"><b>${ot.id}</b>${UI.badgePriorite(ot.priorite)}${UI.badgeStatut(ot.statut)}</div>
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
      ${lien ? UI.html`<p class="accueil-voir-tout"><a href="${lien}">${reste > 0 ? libelleLien + ' (' + reste + ' de plus)' : libelleLien}</a></p>` : ''}
    </article>`;
  }

  function indicateur(lien, classe, libelle, chiffre, complement) {
    return UI.html`<a href="${lien}" class="${classe}">
      <div class="lib">${libelle}</div><div class="chiffre">${chiffre}</div><div class="comp">${complement}</div>
    </a>`;
  }

  // Lot 3 (§15.9) : contrôles réglementaires sous 30 jours et habilitations à renouveler. La couleur
  // du trait suit l'état (rouge : un contrôle en retard ; ambre : une habilitation échue), toujours
  // avec le texte qui le dit.
  function indicateursConformite(compteurs, aujourdhui) {
    const controlesEnRetard = compteurs.controlesSous30j
      .filter((controle) => Controles.etat(controle, aujourdhui).statut === 'en retard').length;
    const habilitationsEchues = compteurs.habilitationsARenouveler
      .filter((element) => element.etat.statut === 'échue').length;
    return UI.html`${indicateur('#/controles?filtre=30j', controlesEnRetard ? 'rouge' : '', 'Contrôles sous 30 j',
      compteurs.controlesSous30j.length, controlesEnRetard ? 'dont ' + controlesEnRetard + ' en retard' : 'contrôles réglementaires')}
      ${indicateur('#/equipe?filtre=a-renouveler', habilitationsEchues ? 'ambre' : '', 'Habilitations à renouveler',
      compteurs.habilitationsARenouveler.length,
      habilitationsEchues ? 'dont ' + pluriel(habilitationsEchues, 'échue') : 'dans les 60 jours')}`;
  }

  // Alerte du responsable : « Contrôle de la base » a trouvé des erreurs.
  function alerteControle() {
    const erreurs = Donnees.problemes().filter((p) => p.gravite === 'erreur').length;
    if (erreurs === 0) return '';
    // UI.bandeau rend un élément DOM : on le convertit en fragment sûr pour l'insérer dans un gabarit.
    return UI.brut(UI.bandeau('important', UI.html`<b>Contrôle de la base : ${pluriel(erreurs, 'erreur')} à corriger.</b>
      Des fichiers contiennent des références cassées, des identifiants manquants ou des valeurs illisibles.
      <a href="#/controle">Voir le contrôle de la base</a>`).outerHTML);
  }

  // Base sans équipement (responsable) : invitation à reprendre les listes existantes (lot 5, §18.9).
  function carteBaseVide() {
    if (Donnees.lignes('equipements').length) return '';
    return UI.html`<article class="carte" id="carte-import-accueil">
      <div class="entete-carte"><h2>Votre parc est vide</h2></div>
      <p>Reprenez vos listes existantes (équipements, articles, fournisseurs, techniciens, historique des
        interventions) depuis Excel, OpenDocument ou CSV : Prévo montre tout avant d'écrire, et l'import peut
        être annulé.</p>
      <div class="actions"><a class="btn btn-primaire" id="lien-import-accueil" href="#/import">${UI.icone('document')}Importer des données</a></div>
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
        <div class="entete-carte"><h2>Connecter un téléphone</h2></div>
        <div class="encadre info" id="connexion-ce-pc">
          <b>Prévo n'est joignable que sur ce PC pour l'instant</b> (portée « ce PC »)&nbsp;: un téléphone ne peut pas
          l'ouvrir. Pour les téléphones de l'atelier, ouvrez Prévo au Wi-Fi&nbsp;: Paramètres › Accès et installation
          (responsable, sur ce PC).
        </div>
      </article>`;
    }
    if (adresses.length === 0) {
      return UI.html`<article class="carte" id="carte-connexion">
        <div class="entete-carte"><h2>Connecter un téléphone</h2></div>
        <div class="encadre attention">
          <b>Aucune adresse réseau détectée.</b> Ce PC ne semble pas relié à un réseau local (Wi-Fi ou câble),
          donc un téléphone ne peut pas s'y connecter pour l'instant. Branchez le PC au réseau de l'atelier,
          puis fermez et relancez <code>Lancer_GMAO</code> : le QR code apparaîtra ici.
        </div>
        <p class="note">En attendant, Prévo reste utilisable sur ce PC.</p>
      </article>`;
    }
    const autres = adresses.slice(1);
    return UI.html`<article class="carte" id="carte-connexion">
      <div class="entete-carte"><h2>Connecter un téléphone</h2></div>
      <div class="accueil-connexion">
        <div class="qr" id="qr-connexion">${UI.qrSvg(adresses[0], 176)}</div>
        <div class="accueil-connexion-texte">
          <p>Scannez ce QR code avec l'appareil photo du téléphone : Prévo s'ouvre dans son navigateur.</p>
          <p>Ou saisissez cette adresse : <b class="accueil-adresse" id="adresse-reseau">${adresses[0]}</b></p>
          ${autres.length ? UI.html`<p class="note">Autres adresses de ce PC : ${autres.join(' · ')}</p>` : ''}
          <ul class="accueil-rappels">
            <li>Le téléphone doit être sur le <b>même réseau Wi-Fi</b> que ce PC.</li>
            <li>Au premier lancement, Windows demande d'autoriser Python : choisissez <b>réseau privé</b>.</li>
            ${porteOuverte ? UI.html`<li>La première fois, le téléphone affiche <b>« Faites confiance au PC atelier »</b> :
              suivez ses étapes une seule fois, puis Prévo s'ouvre de lui-même.</li>` : ''}
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
      <div class="entete-carte"><h2>Mes ordres de travail ouverts</h2><span class="badge ${mesOrdres.length > 0 ? 'info' : 'neutre'}">${mesOrdres.length}</span></div>
      <h3 class="accueil-sous-titre">Mes préventifs de la semaine <span class="badge ${preventifs.length > 0 ? 'info' : 'neutre'}">${preventifs.length}</span></h3>
      ${preventifs.length
        ? UI.html`<ul class="liste-cartes accueil-preventifs">${preventifs.map((ot) => carteOrdre(ot, aujourdhui))}</ul>`
        : UI.html`<p class="muted accueil-preventifs-vide">Aucun préventif à faire d'ici dimanche ${UI.dateFr(dimancheDe(aujourdhui))}.</p>`}
      <h3 class="accueil-sous-titre">Autres ordres de travail <span class="badge neutre">${autres.length}</span></h3>
      ${montres.length
        ? UI.html`<ul class="liste-cartes">${montres.map((ot) => carteOrdre(ot, aujourdhui))}</ul>`
        : UI.vide('Aucun autre ordre de travail ouvert', 'Rien d\'autre ne vous est affecté pour le moment.', 'ordres')}
      <p class="accueil-voir-tout"><a href="#/ot">${reste > 0 ? 'Voir tous les ordres de travail (' + reste + ' de plus)' : 'Voir tous les ordres de travail'}</a></p>
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
        <h1>Accueil</h1>
        <p>Bonjour ${App.profil.nom}. Voici vos ordres de travail ouverts, les plus urgents en premier.</p>
      </div></div>
      <div class="pile-gros accueil-signaler">
        <a href="#/di/nouvelle" class="btn btn-primaire btn-gros">${UI.icone('ajouter')}<span>Signaler un problème<small>Créer une demande d'intervention</small></span></a>
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
        <h1>Accueil</h1>
        <p>Bonjour ${App.profil.nom}. Un équipement ne fonctionne pas bien ? Signalez-le en quelques secondes.</p>
      </div></div>
      <div class="pile-gros accueil-signaler">
        <a href="#/di/nouvelle" class="btn btn-primaire btn-gros">${UI.icone('ajouter')}<span>Signaler un problème<small>Créer une demande d'intervention</small></span></a>
      </div>
      ${carteListe('Mes dernières demandes', mesDemandes.length,
        mesDemandes.slice(0, NOMBRE_LIGNES).map((di) => carteDemande(di, true)),
        '#/di', 'Voir toutes mes demandes',
        'Aucune demande pour le moment', 'Les demandes que vous créez apparaîtront ici avec leur avancement.', 'demandes')}`;
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
      id: 'accueil', route: /^#\/accueil$/, titre: 'Accueil',
      menu: { libelle: 'Accueil', icone: 'accueil', ordre: 10 },
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
      NOMBRE_LIGNES, ORIGINE_PREVENTIF },
  };
})();
