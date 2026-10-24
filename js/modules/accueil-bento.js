'use strict';
// Accueil (2/2) — accueil du responsable en « bento » (T90 ; BRIEF_design_accueil.md, ARCHITECTURE.md §19).
// Complète l'objet Accueil créé par accueil.js, dont il reprend les calculs (Accueil.calculerCompteurs).
//
//   En-tête : « Bonjour » et la date en toutes lettres ; à droite, la mention démo et « Exporter en ZIP »
//   (le bandeau démo de la coque est masqué sur cet écran seulement : css/modules/accueil.css).
//   Grille #bento (12 colonnes internes, soit les 6 du brief ; 2 au téléphone), dans l'ordre :
//     1. synthèse : « Ce matin / Cet après-midi / Ce soir dans l'atelier », phrase et ligne secondaire
//        construites d'après les données, deux boutons, décor « lueur » (aria-hidden) ;
//     2. « À traiter en premier » (choisirEnPremier) ; rien → tuile absente, la synthèse s'étend ;
//     3. quatre compteurs : DI à traiter, OT en retard, P1 ouverts, préventifs de la semaine ;
//     4. rapport du mois écoulé (Rapport.tuileAccueil ; absent → les compteurs s'étendent) ;
//     5. « Demandes à traiter » (pas au téléphone) et « OT en retard » : 5 lignes au plus ;
//     6. « à surveiller » : articles à commander, contrôles et habilitations, suggestions de préventif.
//   Puis la carte « Connecter un téléphone » (mode serveur, pas au téléphone : accueil.js).
//   Chaque tuile-lien mène à la liste filtrée de l'indicateur d'avant la refonte. Les chiffres défilent
//   de 0 à leur valeur (propriété CSS --compte) à l'ouverture de l'écran, pas à un réaffichage ;
//   prefers-reduced-motion coupe tout mouvement (accueil.css). Aucune couleur ici : des classes.

Object.assign(Accueil, (() => {

  const { otOuvert, joursEntre, pluriel, libelleEquipement, badgeImpact, alerteControle, carteBaseVide,
    NOMBRE_LIGNES, ORIGINE_PREVENTIF } = Accueil.interne;
  const RANG_PRIORITE = { P1: 1, P2: 2, P3: 3, P4: 4 };
  const DATE_VIDE = '9999';                     // une date absente passe après toutes les autres
  const MOMENTS = {
    matin: { pastille: 'Ce matin', phrase: 'ce matin' },
    'après-midi': { pastille: 'Cet après-midi', phrase: 'cet après-midi' },
    soir: { pastille: 'Ce soir', phrase: 'ce soir' },
  };
  const TONS_IMPACT = { 'sécurité': 'rouge', 'arrêt': 'ambre', 'dégradé': 'bleu' };
  const FORMAT_DATE = new Intl.DateTimeFormat('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
  const FORMAT_DATE_COURTE = new Intl.DateTimeFormat('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC' });

  // Les chiffres défilent à l'ouverture de l'écran (démarrage, changement d'adresse), pas quand il est
  // réaffiché parce que des données ont changé.
  let animerChiffres = true;
  window.addEventListener('hashchange', () => { animerChiffres = true; });

  // ===========================================================================================
  // 1. Règles (exposées pour les tests)
  // ===========================================================================================

  /** Moment de la journée d'après l'heure locale : 'matin' (avant 12 h), 'après-midi' (12 h à 18 h), 'soir'. */
  function momentDeLaJournee(heure) {
    if (heure < 12) return 'matin';
    return heure < 18 ? 'après-midi' : 'soir';
  }

  /** « 5 demandes à traiter », « 1 demande à traiter » ; aucune : « Rien d'urgent ce matin. » (selon le moment). */
  function phraseDemandes(nombre, moment) {
    if (nombre === 0) return 'Rien d\'urgent ' + MOMENTS[moment].phrase + '.';
    return pluriel(nombre, 'demande') + ' à traiter';
  }

  /** « 3 OT en retard · 1 P1 ouvert · 3 préventifs cette semaine » ; un segment à 0 est omis ('' si tous). */
  function ligneSecondaire(retards, p1, preventifs) {
    return [
      retards ? retards + ' OT en retard' : '',
      p1 ? pluriel(p1, 'P1 ouvert', 'P1 ouverts') : '',
      preventifs ? pluriel(preventifs, 'préventif') + ' cette semaine' : '',
    ].filter(Boolean).join(' · ');
  }

  // Le candidat à la plus petite clé (comparaison terme à terme).
  function plusPetit(candidats) {
    const comparer = (a, b) => {
      for (let i = 0; i < a.cle.length; i += 1) {
        if (a.cle[i] < b.cle[i]) return -1;
        if (a.cle[i] > b.cle[i]) return 1;
      }
      return 0;
    };
    return candidats.reduce((meilleur, candidat) => (comparer(candidat, meilleur) < 0 ? candidat : meilleur));
  }

  /**
   * « À traiter en premier » : { type, ligne } ou null.
   *   'securite' / 'p1' : la DI de sécurité à traiter ou l'OT P1 ouvert le plus ancien (DI : date de la
   *                       demande, OT : date de création ; à égalité la DI) ;
   *   'retard'          : sinon l'OT le plus en retard (à égalité, la priorité la plus haute) ;
   *   'preventif'       : sinon le prochain préventif (OT préventif ouvert à la date prévue la plus proche).
   */
  function choisirEnPremier(compteurs) {
    const urgents = compteurs.diATraiter.filter((di) => di.impact === 'sécurité')
      .map((di) => ({ type: 'securite', ligne: di, cle: [di.date_heure || DATE_VIDE, 0, di.id] }))
      .concat(compteurs.p1Ouverts.map((ot) => ({ type: 'p1', ligne: ot, cle: [ot.date_creation || DATE_VIDE, 1, ot.id] })));
    if (urgents.length) return plusPetit(urgents);
    if (compteurs.otEnRetard.length) {
      return plusPetit(compteurs.otEnRetard.map((ot) => ({
        type: 'retard', ligne: ot, cle: [ot.date_prevue, RANG_PRIORITE[ot.priorite] || 9, ot.id] })));
    }
    const preventifs = Donnees.lignes('ordres_travail')
      .filter((ot) => ot.origine === ORIGINE_PREVENTIF && otOuvert(ot) && ot.date_prevue);
    if (preventifs.length) return plusPetit(preventifs.map((ot) => ({ type: 'preventif', ligne: ot, cle: [ot.date_prevue, 0, ot.id] })));
    return null;
  }

  /** '2026-10-19' → « Lundi 19 octobre 2026 » (ou « Lundi 19 octobre » sans l'année). */
  function dateEnLettres(dateIso, avecAnnee) {
    const [annee, mois, jour] = dateIso.split('-').map(Number);
    const texte = (avecAnnee ? FORMAT_DATE : FORMAT_DATE_COURTE).format(new Date(Date.UTC(annee, mois - 1, jour)));
    return texte.charAt(0).toUpperCase() + texte.slice(1);
  }

  // ===========================================================================================
  // 2. Morceaux de tuiles
  // ===========================================================================================

  // Chiffre qui défile : la valeur est le texte (lu par les lecteurs d'écran et les tests) ; le dessin
  // vient de ::after, compteur CSS mené par --compte (accueil.css).
  function chiffre(valeur) {
    return UI.html`<b class="chiffre" style="--valeur: ${valeur}"><span class="visuellement-cache">${valeur}</span></b>`;
  }

  function repere(equipementId) {
    const equipement = Donnees.trouver('equipements', equipementId);
    return equipement ? equipement.repere : (equipementId || '—');
  }

  function complement(texte, ton) {
    return UI.html`<span class="comp${ton ? ' ' + ton : ''}">${texte}</span>`;
  }

  // ===========================================================================================
  // 3. Tuiles
  // ===========================================================================================

  function entete(aujourdhui) {
    return UI.html`<div class="bento-entete">
      <div class="bento-salut"><h1>Bonjour</h1><p class="bento-date">${dateEnLettres(aujourdhui, true)}</p></div>
      <div class="bento-entete-actions">
        ${App.mode === 'demo' ? UI.html`<span class="bento-demo" id="accueil-demo">${UI.icone('alerte')}Démo — rien n'est enregistré</span>` : ''}
        <button type="button" class="btn btn-fantome bento-zip" id="btn-export-accueil">${UI.icone('export')}Exporter en ZIP</button>
      </div>
    </div>`;
  }

  function tuileSynthese(compteurs, moment) {
    const nombre = compteurs.diATraiter.length;
    const securite = compteurs.diATraiter.filter((di) => di.impact === 'sécurité').length;
    const ligne = ligneSecondaire(compteurs.otEnRetard.length, compteurs.p1Ouverts.length, compteurs.preventifsSemaine.length);
    return UI.html`<section class="bento-tuile bento-synthese" id="bento-synthese" aria-labelledby="bento-phrase">
      <span class="bento-lueur" aria-hidden="true"><span class="bento-halo bento-halo-blanc"></span><span class="bento-halo bento-halo-cyan"></span></span>
      <p class="bento-moment">${MOMENTS[moment].pastille} dans l'atelier</p>
      <h2 class="bento-phrase" id="bento-phrase">${phraseDemandes(nombre, moment)}${nombre && securite
        ? UI.html`, dont <span class="bento-securite">${securite} sécurité</span>` : ''}</h2>
      ${ligne ? UI.html`<p class="bento-resume" id="bento-ligne">${ligne}</p>` : ''}
      <div class="bento-actions">
        <a class="btn bento-btn-blanc" href="#/di?statut=Nouvelle">Voir les demandes <span aria-hidden="true">→</span></a>
        <a class="btn bento-btn-verre" href="#/planning">Ouvrir le planning</a>
      </div>
    </section>`;
  }

  // Réglages de la tuile « À traiter en premier » selon le type de l'élément choisi.
  function reglagesPremier(choix, aujourdhui) {
    const element = choix.ligne;
    const equipement = libelleEquipement(element.equipement_id);
    switch (choix.type) {
      case 'securite':
        return { icone: 'alerte', ton: 'rouge', titre: equipement, detail: element.symptome, lien: '#/di/',
          pastille: UI.html`<span class="badge ko">Sécurité</span>`, action: 'Traiter la demande' };
      case 'p1':
        return { icone: 'alerte', ton: 'rouge', titre: element.titre, detail: equipement + ' · ' + element.statut, lien: '#/ot/',
          pastille: UI.badgePriorite('P1'), action: 'Ouvrir l\'ordre de travail' };
      case 'retard':
        return { icone: 'horloge', ton: 'ambre', titre: element.titre, lien: '#/ot/',
          detail: 'En retard de ' + pluriel(joursEntre(element.date_prevue, aujourdhui), 'jour') + ' (prévu le '
            + UI.dateFr(element.date_prevue) + ') · ' + equipement,
          pastille: UI.html`<span class="badge attention">En retard</span>`, action: 'Ouvrir l\'ordre de travail' };
      default:
        return { icone: 'preventif', ton: 'vert', titre: element.titre, lien: '#/ot/',
          detail: (element.date_prevue === aujourdhui ? 'Prévu aujourd\'hui' : 'Prévu le ' + UI.dateFr(element.date_prevue)) + ' · ' + equipement,
          pastille: UI.html`<span class="badge info">Préventif</span>`, action: 'Ouvrir le préventif' };
    }
  }

  function tuilePremier(choix, aujourdhui) {
    if (!choix) return '';
    const r = reglagesPremier(choix, aujourdhui);
    const id = choix.ligne.id;
    return UI.html`<section class="bento-tuile bento-premier" id="bento-premier" data-type="${choix.type}" data-id="${id}" aria-labelledby="bento-premier-titre">
      <div class="bento-premier-tete"><span class="bento-pastille-icone ${r.ton}">${UI.icone(r.icone)}</span><h2 id="bento-premier-titre">À traiter en premier</h2></div>
      <p class="bento-premier-element">${r.titre}</p>
      <p class="bento-premier-detail">${r.detail}</p>
      <p class="bento-pastilles">${r.pastille}<span class="badge neutre">${id}</span></p>
      <a class="btn btn-primaire bento-premier-action" href="${r.lien}${encodeURIComponent(id)}">${r.action}</a>
    </section>`;
  }

  function compteur(lien, icone, ton, valeur, libelle, comp) {
    return UI.html`<a class="bento-tuile bento-compteur" href="${lien}">
      <span class="bento-pastille-icone ${ton}">${UI.icone(icone)}</span>
      ${chiffre(valeur)}<span class="lib">${libelle}</span>${comp}
    </a>`;
  }

  function compteurs4(compteurs, aujourdhui) {
    const securite = compteurs.diATraiter.filter((di) => di.impact === 'sécurité').length;
    const plusVieux = compteurs.otEnRetard.reduce((pire, ot) => Math.max(pire, joursEntre(ot.date_prevue, aujourdhui)), 0);
    const enCours = compteurs.p1Ouverts.filter((ot) => ot.statut === 'En cours').length;
    const p1 = compteurs.p1Ouverts.length;
    const preventifsEnRetard = compteurs.preventifsSemaine.filter((ot) => Accueil.otEnRetard(ot, aujourdhui)).length;
    return UI.html`
      ${compteur('#/di?statut=Nouvelle', 'demandes', 'bleu', compteurs.diATraiter.length, 'DI à traiter',
        securite ? complement('dont ' + securite + ' sécurité', 'rouge') : complement('demandes nouvelles'))}
      ${compteur('#/ot?filtre=retard', 'horloge', 'ambre', compteurs.otEnRetard.length, 'OT en retard',
        plusVieux ? complement('jusqu\'à ' + pluriel(plusVieux, 'jour') + ' de retard', 'ambre') : complement('tout est dans les temps'))}
      ${compteur('#/ot?filtre=p1', 'alerte', 'rouge', p1, p1 > 1 ? 'P1 ouverts' : 'P1 ouvert',
        enCours ? complement('dont ' + enCours + ' en cours', 'rouge') : complement('priorité la plus haute'))}
      ${compteur('#/preventif?onglet=calendrier', 'preventif', 'vert', compteurs.preventifsSemaine.length, 'Préventifs de la semaine',
        preventifsEnRetard ? complement('dont ' + preventifsEnRetard + ' en retard', 'ambre') : complement('d\'ici dimanche'))}`;
  }

  function lienListe(lien, nombre) {
    return UI.html`<a class="bento-tout-voir" href="${lien}">Tout voir (${nombre})</a>`;
  }

  // Demandes à traiter : sécurité d'abord, puis les plus anciennes. Un point de couleur et le badge
  // d'impact (texte) : la couleur n'est jamais seule.
  function listeDemandes(compteurs) {
    const demandes = compteurs.diATraiter.slice().sort((a, b) =>
      (b.impact === 'sécurité') - (a.impact === 'sécurité') || a.date_heure.localeCompare(b.date_heure));
    const lignes = demandes.slice(0, NOMBRE_LIGNES).map((di) => UI.html`<li><a href="#/di/${encodeURIComponent(di.id)}">
      <span class="bento-point ${TONS_IMPACT[di.impact] || 'neutre'}" aria-hidden="true"></span>
      <span class="bento-ligne-texte"><span class="bento-ligne-titre">${di.symptome}</span>
        <span class="bento-ligne-meta"><span class="bento-id">${di.id}</span> · ${repere(di.equipement_id)} · ${UI.dateHeureFr(di.date_heure)}</span></span>
      ${badgeImpact(di.impact)}</a></li>`);
    return UI.html`<section class="bento-tuile bento-liste" id="bento-demandes" aria-labelledby="bento-demandes-titre">
      <div class="bento-liste-tete"><h2 id="bento-demandes-titre">Demandes à traiter</h2>${lienListe('#/di?statut=Nouvelle', demandes.length)}</div>
      ${lignes.length ? UI.html`<ul>${lignes}</ul>` : UI.html`<p class="bento-vide">Aucune demande à traiter.</p>`}
    </section>`;
  }

  // OT en retard : les plus en retard d'abord ; pastille de priorité à gauche, retard en jours à droite.
  function listeRetards(compteurs, aujourdhui) {
    const retards = compteurs.otEnRetard.slice().sort((a, b) => a.date_prevue.localeCompare(b.date_prevue));
    const lignes = retards.slice(0, NOMBRE_LIGNES).map((ot) => {
      const jours = joursEntre(ot.date_prevue, aujourdhui);
      return UI.html`<li><a href="#/ot/${encodeURIComponent(ot.id)}">
        ${UI.badgePriorite(ot.priorite)}
        <span class="bento-ligne-texte"><span class="bento-ligne-titre">${ot.titre}</span>
          <span class="bento-ligne-meta"><span class="bento-id">${ot.id}</span> · ${repere(ot.equipement_id)} · prévu le ${UI.dateFr(ot.date_prevue)}</span></span>
        <span class="bento-retard"><span aria-hidden="true">${jours} j</span><span class="visuellement-cache">en retard de ${pluriel(jours, 'jour')}</span></span></a></li>`;
    });
    return UI.html`<section class="bento-tuile bento-liste" id="bento-retards" aria-labelledby="bento-retards-titre">
      <div class="bento-liste-tete"><h2 id="bento-retards-titre">OT en retard</h2>${lienListe('#/ot?filtre=retard', retards.length)}</div>
      ${lignes.length ? UI.html`<ul>${lignes}</ul>` : UI.html`<p class="bento-vide">Aucun OT en retard : tout est dans les temps.</p>`}
    </section>`;
  }

  // Tuile « à surveiller » : grosse pastille carrée avec le chiffre, libellé, détail coloré, chevron ;
  // toute la tuile est un lien.
  function surveiller(lien, ton, valeur, libelle, comp) {
    return UI.html`<a class="bento-tuile bento-surveiller" href="${lien}">
      <span class="bento-carre ${ton}">${chiffre(valeur)}</span>
      <span class="bento-surveiller-corps"><span class="lib">${libelle}</span>${comp}</span>
      ${UI.icone('chevron', 'bento-chevron')}
    </a>`;
  }

  // « Contrôles et habilitations » (lot 3, §15.9) : une tuile, deux liens (les deux listes filtrées
  // d'avant), le total dans la pastille.
  function tuileConformite(compteurs, aujourdhui) {
    const controles = compteurs.controlesSous30j.length;
    const habilitations = compteurs.habilitationsARenouveler.length;
    const enRetard = compteurs.controlesSous30j.filter((c) => Controles.etat(c, aujourdhui).statut === 'en retard').length;
    const echues = compteurs.habilitationsARenouveler.filter((h) => h.etat.statut === 'échue').length;
    return UI.html`<div class="bento-tuile bento-surveiller bento-conformite">
      <span class="bento-carre violet">${chiffre(controles + habilitations)}</span>
      <div class="bento-surveiller-corps">
        <h2 class="lib">Contrôles et habilitations</h2>
        <a class="bento-sous-lien" href="#/controles?filtre=30j">${chiffre(controles)}<span class="bento-sous-texte"><span>${controles > 1 ? 'contrôles' : 'contrôle'} sous 30 j</span>
          ${enRetard ? complement('dont ' + enRetard + ' en retard', 'rouge') : complement('aucun en retard')}</span>${UI.icone('chevron', 'bento-chevron')}</a>
        <a class="bento-sous-lien" href="#/equipe?filtre=a-renouveler">${chiffre(habilitations)}<span class="bento-sous-texte"><span>${habilitations > 1 ? 'habilitations' : 'habilitation'} à renouveler</span>
          ${echues ? complement('dont ' + pluriel(echues, 'échue'), 'ambre') : complement('aucune échue')}</span>${UI.icone('chevron', 'bento-chevron')}</a>
      </div>
    </div>`;
  }

  function tuilesSurveiller(compteurs, aujourdhui) {
    const critiques = compteurs.articlesACommander.filter((a) => a.article.critique === '1').length;
    // Suggestions est chargé après ce fichier : appelé au moment de l'affichage.
    const suggestions = Suggestions.ouvertes(aujourdhui);
    const surA = suggestions.filter((suggestion) => suggestion.criticite === 'A').length;
    return UI.html`
      ${surveiller('#/magasin?onglet=a-commander', 'ambre', compteurs.articlesACommander.length, 'Articles à commander',
        critiques ? complement('dont ' + pluriel(critiques, 'critique'), 'rouge') : complement('stock au point de commande'))}
      ${tuileConformite(compteurs, aujourdhui)}
      ${surveiller('#/preventif?onglet=suggestions', 'vert', suggestions.length, 'Suggestions de préventif',
        surA ? complement('dont ' + surA + ' sur criticité A', 'ambre') : complement('à examiner'))}`;
  }

  // ===========================================================================================
  // 4. Écran
  // ===========================================================================================

  /** Remplit #contenu avec l'accueil du responsable ; `carteConnexion` : fragment ou '' (accueil.js). */
  function afficherResponsable(conteneur, carteConnexion) {
    const aujourdhui = Donnees.aujourdhui();
    const compteurs = Accueil.calculerCompteurs();
    const choix = choisirEnPremier(compteurs);
    const classes = ['bento', 'accueil-instruments'];        // accueil-instruments : point d'accroche des tests (accueil chargé)
    if (!choix) classes.push('sans-premier');
    if (animerChiffres) classes.push('bento-anime');
    animerChiffres = false;
    UI.remplir(conteneur, UI.html`${entete(aujourdhui)}<div id="maj-zone"></div>${alerteControle()}${carteBaseVide()}
      <div class="${classes.join(' ')}" id="bento">
        ${tuileSynthese(compteurs, momentDeLaJournee(new Date().getHours()))}${tuilePremier(choix, aujourdhui)}
        ${compteurs4(compteurs, aujourdhui)}
        ${listeDemandes(compteurs)}${listeRetards(compteurs, aujourdhui)}
        ${tuilesSurveiller(compteurs, aujourdhui)}
      </div>${carteConnexion}`);
    // Rapport du mois écoulé (lot 3, §15.10) après les compteurs ; Rapport est chargé après ce fichier.
    const tuileRapport = typeof Rapport !== 'undefined' && typeof Rapport.tuileAccueil === 'function' ? Rapport.tuileAccueil() : null;
    const derniersCompteurs = conteneur.querySelectorAll('#bento .bento-compteur');
    if (tuileRapport && derniersCompteurs.length) derniersCompteurs[derniersCompteurs.length - 1].after(tuileRapport);
    conteneur.querySelector('#btn-export-accueil').addEventListener('click', () => App.exporterZip());
    // Mise à jour signalée (D120) : bandeau si une version plus récente est connue sur ce poste.
    if (typeof MiseAJour !== 'undefined') MiseAJour.afficherSiPossible();
    App.definirTitreMobile('Bonjour', dateEnLettres(aujourdhui, false));
  }

  return { afficherResponsable, choisirEnPremier, momentDeLaJournee, phraseDemandes, ligneSecondaire };
})());
