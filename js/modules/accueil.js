'use strict';
// Accueil : écran d'arrivée (#/accueil), adapté au profil (brief §9 E1, ARCHITECTURE.md §10).
//
//   Responsable : trois indicateurs (DI à traiter, OT en retard, P1 ouverts) qui mènent à la liste
//                 filtrée, une alerte si « Contrôle de la base » signale des erreurs, les 5 DI à
//                 traiter et les 5 OT en retard les plus anciens.
//   Technicien  : gros bouton « Signaler » et la liste de ses OT ouverts.
//   Demandeur   : gros bouton « Signaler un problème » et ses 5 dernières demandes (statut,
//                 motif de refus).
//   Tous, en mode serveur : carte « Connecter un téléphone » (QR code de l'adresse réseau du PC).
//
// Définitions des compteurs (ARCHITECTURE.md §10) :
//   DI à traiter  = demande au statut « Nouvelle » ;
//   OT en retard  = statut ni clôturé ni annulé ET date prévue avant aujourd'hui ;
//   P1 ouvert     = priorité P1 ET statut ni clôturé ni annulé.

const Accueil = (() => {

  const STATUTS_OT_FERMES = ['Clôturé techniquement', 'Clôturé administrativement', 'Annulé'];
  const NOMBRE_LIGNES = 5;             // lignes montrées dans les listes du responsable et du demandeur
  const NOMBRE_OT_TECHNICIEN = 15;     // un technicien voit tous ses OT ouverts, jusqu'à ce nombre
  const MILLISECONDES_PAR_JOUR = 24 * 60 * 60 * 1000;

  // Adresses du serveur lues une première fois puis gardées (évite un aller-retour à chaque affichage).
  let adressesEnMemoire = null;

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

  /** Les trois listes qui donnent les compteurs de l'accueil : { diATraiter, otEnRetard, p1Ouverts }. */
  function calculerCompteurs() {
    const aujourdhui = Donnees.aujourdhui();
    const ordres = Donnees.lignes('ordres_travail');
    return {
      diATraiter: Donnees.lignes('demandes').filter((di) => di.statut === 'Nouvelle'),
      otEnRetard: ordres.filter((ot) => otEnRetard(ot, aujourdhui)),
      p1Ouverts: ordres.filter(p1Ouvert),
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

  // Alerte du responsable : « Contrôle de la base » a trouvé des erreurs.
  function alerteControle() {
    const erreurs = Donnees.problemes().filter((p) => p.gravite === 'erreur').length;
    if (erreurs === 0) return '';
    // UI.bandeau rend un élément DOM : on le convertit en fragment sûr pour l'insérer dans un gabarit.
    return UI.brut(UI.bandeau('important', UI.html`<b>Contrôle de la base : ${pluriel(erreurs, 'erreur')} à corriger.</b>
      Des fichiers contiennent des références cassées, des identifiants manquants ou des valeurs illisibles.
      <a href="#/controle">Voir le contrôle de la base</a>`).outerHTML);
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
    } catch (erreur) {
      console.warn('Prévo : adresses réseau du serveur inconnues (' + (erreur && erreur.message) + ').', erreur);
    }
    return adresses;
  }

  function carteConnexion(adresses) {
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
          </ul>
        </div>
      </div>
    </article>`;
  }

  // ===========================================================================================
  // 4. Les trois accueils
  // ===========================================================================================

  function accueilResponsable() {
    const aujourdhui = Donnees.aujourdhui();
    const compteurs = calculerCompteurs();
    const nombreSecurite = compteurs.diATraiter.filter((di) => di.impact === 'sécurité').length;
    const nombreP1EnCours = compteurs.p1Ouverts.filter((ot) => ot.statut === 'En cours').length;

    // Demandes de sécurité d'abord, puis les plus anciennes.
    const demandes = compteurs.diATraiter.slice().sort((a, b) =>
      (b.impact === 'sécurité') - (a.impact === 'sécurité') || a.date_heure.localeCompare(b.date_heure));
    // Les OT les plus en retard d'abord.
    const retards = compteurs.otEnRetard.slice().sort((a, b) => a.date_prevue.localeCompare(b.date_prevue));

    return UI.html`
      <div class="entete-page"><div>
        <h1>Accueil</h1>
        <p>Vue d'ensemble de l'atelier au ${UI.dateFr(aujourdhui)}.</p>
      </div></div>
      ${alerteControle()}
      <div class="instruments accueil-instruments">
        ${indicateur('#/di?statut=Nouvelle', 'cyan', 'DI à traiter', compteurs.diATraiter.length,
          nombreSecurite ? 'dont ' + nombreSecurite + ' sécurité' : 'demandes nouvelles')}
        ${indicateur('#/ot?filtre=retard', 'ambre', 'OT en retard', compteurs.otEnRetard.length, 'date prévue dépassée')}
        ${indicateur('#/ot?filtre=p1', 'rouge', 'P1 ouverts', compteurs.p1Ouverts.length,
          nombreP1EnCours ? 'dont ' + nombreP1EnCours + ' en cours' : 'priorité la plus haute')}
      </div>
      <div class="grille">
        <div class="c6">${carteListe('Demandes à traiter', compteurs.diATraiter.length,
          demandes.slice(0, NOMBRE_LIGNES).map((di) => carteDemande(di, false)),
          '#/di?statut=Nouvelle', 'Voir toutes les demandes à traiter',
          'Aucune demande à traiter', 'Les nouvelles demandes d\'intervention apparaîtront ici.', 'demandes')}</div>
        <div class="c6">${carteListe('Ordres de travail en retard', compteurs.otEnRetard.length,
          retards.slice(0, NOMBRE_LIGNES).map((ot) => carteOrdre(ot, aujourdhui)),
          '#/ot?filtre=retard', 'Voir tous les OT en retard',
          'Aucun OT en retard', 'Tous les ordres de travail ouverts sont dans les temps.', 'ordres')}</div>
      </div>`;
  }

  function accueilTechnicien() {
    const aujourdhui = Donnees.aujourdhui();
    const identifiant = App.profil.technicienId;
    const rangPriorite = { P1: 1, P2: 2, P3: 3, P4: 4 };
    const mesOrdres = Donnees.lignes('ordres_travail')
      .filter((ot) => ot.technicien_id === identifiant && otOuvert(ot))
      .sort((a, b) => (rangPriorite[a.priorite] || 9) - (rangPriorite[b.priorite] || 9)
        || (a.date_prevue || '9999').localeCompare(b.date_prevue || '9999'));
    return UI.html`
      <div class="entete-page"><div>
        <h1>Accueil</h1>
        <p>Bonjour ${App.profil.nom}. Voici vos ordres de travail ouverts, les plus urgents en premier.</p>
      </div></div>
      <div class="pile-gros accueil-signaler">
        <a href="#/di/nouvelle" class="btn btn-primaire btn-gros">${UI.icone('ajouter')}<span>Signaler un problème<small>Créer une demande d'intervention</small></span></a>
      </div>
      ${carteListe('Mes ordres de travail ouverts', mesOrdres.length,
        mesOrdres.slice(0, NOMBRE_OT_TECHNICIEN).map((ot) => carteOrdre(ot, aujourdhui)),
        '#/ot', 'Voir tous les ordres de travail',
        'Aucun ordre de travail ouvert', 'Rien ne vous est affecté pour le moment.', 'ordres')}`;
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
    // En mode serveur, on lit l'adresse réseau AVANT d'écrire l'écran (un seul remplissage).
    const adresses = App.mode === 'serveur' ? await lireAdressesReseau() : null;
    // Si l'utilisateur est parti ailleurs pendant l'attente, on n'écrase pas son nouvel écran.
    if (!/^#\/accueil/.test(location.hash)) return;

    let contenu;
    if (App.estResponsable()) contenu = accueilResponsable();
    else if (App.estTechnicien()) contenu = accueilTechnicien();
    else contenu = accueilDemandeur();
    UI.remplir(conteneur, UI.html`${contenu}${adresses === null ? '' : carteConnexion(adresses)}`);
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

  return { afficher, calculerCompteurs, otEnRetard, p1Ouvert };
})();
