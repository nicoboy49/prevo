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
//   Mode serveur : avertissement « Copie externe des sauvegardes » (D133, §22.11) quand la copie de la nuit a échoué
//   ou n'a pas été faite depuis plus d'un jour, avec le nombre de jours ; avertissement Tailscale (D128, §22.8) quand
//   Tailscale est déconnecté ou que sa clé expire sous 14 jours ; les deux lus sur /api/info après l'affichage.
//   Chaque tuile-lien mène à la liste filtrée de l'indicateur d'avant la refonte. Les chiffres défilent
//   de 0 à leur valeur (propriété CSS --compte) à l'ouverture de l'écran, pas à un réaffichage ;
//   prefers-reduced-motion coupe tout mouvement (accueil.css). Aucune couleur ici : des classes.

Object.assign(Accueil, (() => {

  const { otOuvert, joursEntre, libelleEquipement, badgeImpact, alerteControle, carteBaseVide,
    NOMBRE_LIGNES, ORIGINE_PREVENTIF } = Accueil.interne;
  const RANG_PRIORITE = { P1: 1, P2: 2, P3: 3, P4: 4 };
  const DATE_VIDE = '9999';                     // une date absente passe après toutes les autres
  const TONS_IMPACT = { 'sécurité': 'rouge', 'arrêt': 'ambre', 'dégradé': 'bleu' };
  const OPTIONS_DATE = { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' };
  const OPTIONS_DATE_COURTE = { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC' };

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
    if (nombre === 0) {
      // Une phrase complète par moment (jamais un mot choisi au milieu d'une phrase).
      if (moment === 'matin') return I18n.t('accueil.phrase_demandes.rien_urgent_matin');
      return moment === 'après-midi' ? I18n.t('accueil.phrase_demandes.rien_urgent_apres_midi') : I18n.t('accueil.phrase_demandes.rien_urgent_soir');
    }
    return I18n.t('accueil.phrase_demandes.a_traiter', { n: nombre });
  }

  /** « Ce matin dans l'atelier » (selon le moment), une phrase complète par moment. */
  function momentAtelier(moment) {
    if (moment === 'matin') return I18n.t('accueil.moment_atelier.matin_atelier');
    return moment === 'après-midi' ? I18n.t('accueil.moment_atelier.apres_midi_atelier') : I18n.t('accueil.moment_atelier.soir_atelier');
  }

  /** « 3 OT en retard · 1 P1 ouvert · 3 préventifs cette semaine » ; un segment à 0 est omis ('' si tous). */
  function ligneSecondaire(retards, p1, preventifs) {
    return [
      retards ? I18n.t('accueil.ligne_secondaire.ot_retard', { n: retards }) : '',
      p1 ? I18n.t('accueil.ligne_secondaire.p1_ouverts', { n: p1 }) : '',
      preventifs ? I18n.t('accueil.ligne_secondaire.preventifs_semaine', { n: preventifs }) : '',
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
    const texte = new Intl.DateTimeFormat(I18n.locale, avecAnnee ? OPTIONS_DATE : OPTIONS_DATE_COURTE).format(new Date(Date.UTC(annee, mois - 1, jour)));
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

  // Mode Solo (mode_solo = 1, D132, §22.11) : « Nouvel OT » en premier, « Signaler un problème » en second.
  function actionsSolo() {
    if (!App.modeSolo()) return '';
    const iconeAjouter = UI.icone('ajouter');
    const iconeAlerte = UI.icone('alerte');
    const nouvelOt = UI.html`<a class="btn btn-primaire" id="accueil-nouvel-ot" href="#/ot/nouveau">${iconeAjouter}${I18n.t('accueil.actions_solo.nouvel_ot')}</a>`;
    const signaler = UI.html`<a class="btn btn-secondaire" id="accueil-signaler" href="#/di/nouvelle">${iconeAlerte}${I18n.t('accueil.actions_solo.signaler_probleme')}</a>`;
    return UI.html`<div class="bento-solo" id="accueil-solo">
      ${nouvelOt}
      ${signaler}
    </div>`;
  }

  function entete(aujourdhui) {
    return UI.html`<div class="bento-entete">
      <div class="bento-salut"><h1>${I18n.t('accueil.entete.bonjour')}</h1><p class="bento-date">${dateEnLettres(aujourdhui, true)}</p></div>
      ${actionsSolo()}
      <div class="bento-entete-actions">
        ${App.mode === 'demo' ? UI.html`<span class="bento-demo" id="accueil-demo">${UI.icone('alerte')}${I18n.t('accueil.entete.demo_rien_enregistre')}</span>` : ''}
        <button type="button" class="btn btn-fantome bento-zip" id="btn-export-accueil">${UI.icone('export')}${I18n.t('accueil.entete.exporter_zip')}</button>
      </div>
    </div>`;
  }

  function tuileSynthese(compteurs, moment) {
    const nombre = compteurs.diATraiter.length;
    const securite = compteurs.diATraiter.filter((di) => di.impact === 'sécurité').length;
    const ligne = ligneSecondaire(compteurs.otEnRetard.length, compteurs.p1Ouverts.length, compteurs.preventifsSemaine.length);
    return UI.html`<section class="bento-tuile bento-synthese" id="bento-synthese" aria-labelledby="bento-phrase">
      <span class="bento-lueur" aria-hidden="true"><span class="bento-halo bento-halo-blanc"></span><span class="bento-halo bento-halo-cyan"></span></span>
      <p class="bento-moment">${momentAtelier(moment)}</p>
      <h2 class="bento-phrase" id="bento-phrase">${phraseDemandes(nombre, moment)}${nombre && securite
        ? UI.html`${I18n.html('accueil.tuile_synthese.dont_securite', { securite })}` : ''}</h2>
      ${ligne ? UI.html`<p class="bento-resume" id="bento-ligne">${ligne}</p>` : ''}
      <div class="bento-actions">
        ${I18n.html('accueil.tuile_synthese.voir_demandes_ouvrir_planning')}
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
          pastille: UI.html`<span class="badge ko">${I18n.t('accueil.reglages_premier.securite')}</span>`, action: I18n.t('accueil.reglages_premier.traiter_demande') };
      case 'p1':
        return { icone: 'alerte', ton: 'rouge', titre: element.titre, detail: equipement + ' · ' + Schema.libelleValeur('ordres_travail', 'statut', element.statut), lien: '#/ot/',
          pastille: UI.badgePriorite('P1'), action: I18n.t('accueil.reglages_premier.ouvrir_ordre_travail') };
      case 'retard':
        return { icone: 'horloge', ton: 'ambre', titre: element.titre, lien: '#/ot/',
          detail: I18n.t('accueil.reglages_premier.retard_prevu', { n: joursEntre(element.date_prevue, aujourdhui),
            datePrevue: UI.dateFr(element.date_prevue), equipement }),
          pastille: UI.html`<span class="badge attention">${I18n.t('accueil.reglages_premier.retard')}</span>`, action: I18n.t('accueil.reglages_premier.ouvrir_ordre_travail') };
      default:
        return { icone: 'preventif', ton: 'vert', titre: element.titre, lien: '#/ot/',
          detail: (element.date_prevue === aujourdhui ? I18n.t('accueil.reglages_premier.prevu_aujourd_hui') : I18n.t('accueil.reglages_premier.prevu_date_prevue', { date_prevue: UI.dateFr(element.date_prevue) })) + ' · ' + equipement,
          pastille: UI.html`<span class="badge info">${I18n.t('accueil.reglages_premier.preventif')}</span>`, action: I18n.t('accueil.reglages_premier.ouvrir_preventif') };
    }
  }

  function tuilePremier(choix, aujourdhui) {
    if (!choix) return '';
    const r = reglagesPremier(choix, aujourdhui);
    const id = choix.ligne.id;
    return UI.html`<section class="bento-tuile bento-premier" id="bento-premier" data-type="${choix.type}" data-id="${id}" aria-labelledby="bento-premier-titre">
      <div class="bento-premier-tete"><span class="bento-pastille-icone ${r.ton}">${UI.icone(r.icone)}</span><h2 id="bento-premier-titre">${I18n.t('accueil.tuile_premier.traiter_premier')}</h2></div>
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
      ${compteur('#/di?statut=Nouvelle', 'demandes', 'bleu', compteurs.diATraiter.length, I18n.t('accueil.compteurs4.di_traiter'),
        securite ? complement(I18n.t('accueil.compteurs4.dont_securite', { securite }), 'rouge') : complement(I18n.t('accueil.compteurs4.demandes_nouvelles')))}
      ${compteur('#/ot?filtre=retard', 'horloge', 'ambre', compteurs.otEnRetard.length, I18n.t('accueil.compteurs4.ot_retard'),
        plusVieux ? complement(I18n.t('accueil.compteurs4.jusqu_a_retard', { n: plusVieux }), 'ambre') : complement(I18n.t('accueil.compteurs4.tout_temps')))}
      ${compteur('#/ot?filtre=p1', 'alerte', 'rouge', p1, I18n.t('accueil.compteurs4.p1_ouverts', { n: p1 }),
        enCours ? complement(I18n.t('accueil.compteurs4.dont_cours', { enCours }), 'rouge') : complement(I18n.t('accueil.compteurs4.priorite_plus_haute')))}
      ${compteur('#/preventif?onglet=calendrier', 'preventif', 'vert', compteurs.preventifsSemaine.length, I18n.t('accueil.compteurs4.preventifs_semaine'),
        preventifsEnRetard ? complement(I18n.t('accueil.compteurs4.dont_retard', { preventifsEnRetard }), 'ambre') : complement(I18n.t('accueil.compteurs4.ici_dimanche')))}`;
  }

  function lienListe(lien, nombre) {
    return UI.html`<a class="bento-tout-voir" href="${lien}">${I18n.t('accueil.lien_liste.tout_voir', { nombre })}</a>`;
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
      <div class="bento-liste-tete"><h2 id="bento-demandes-titre">${I18n.t('accueil.liste_demandes.demandes_traiter')}</h2>${lienListe('#/di?statut=Nouvelle', demandes.length)}</div>
      ${lignes.length ? UI.html`<ul>${lignes}</ul>` : UI.html`<p class="bento-vide">${I18n.t('accueil.liste_demandes.aucune_demande_traiter')}</p>`}
    </section>`;
  }

  // OT en retard : les plus en retard d'abord ; pastille de priorité à gauche, retard en jours à droite.
  function listeRetards(compteurs, aujourdhui) {
    const retards = compteurs.otEnRetard.slice().sort((a, b) => a.date_prevue.localeCompare(b.date_prevue));
    const lignes = retards.slice(0, NOMBRE_LIGNES).map((ot) => {
      const jours = joursEntre(ot.date_prevue, aujourdhui);
      return UI.html`<li><a href="#/ot/${encodeURIComponent(ot.id)}">
        ${UI.badgePriorite(ot.priorite)}
        ${I18n.html('accueil.liste_retards.ot_titre_ot_id_repere_prevu', { otTitre: ot.titre, otId: ot.id, repere: repere(ot.equipement_id), date_prevue: UI.dateFr(ot.date_prevue), joursAbrege: I18n.t('accueil.liste_retards.jours_abrege', { n: jours }), retardJours: I18n.t('accueil.liste_retards.retard_jours', { n: jours }) })}</a></li>`;
    });
    return UI.html`<section class="bento-tuile bento-liste" id="bento-retards" aria-labelledby="bento-retards-titre">
      <div class="bento-liste-tete"><h2 id="bento-retards-titre">${I18n.t('accueil.compteurs4.ot_retard')}</h2>${lienListe('#/ot?filtre=retard', retards.length)}</div>
      ${lignes.length ? UI.html`<ul>${lignes}</ul>` : UI.html`<p class="bento-vide">${I18n.t('accueil.liste_retards.aucun_ot_retard_tout')}</p>`}
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
        <h2 class="lib">${I18n.t('accueil.tuile_conformite.controles_habilitations')}</h2>
        <a class="bento-sous-lien" href="#/controles?filtre=30j">${chiffre(controles)}<span class="bento-sous-texte"><span>${I18n.t('accueil.tuile_conformite.controles_sous_30', { n: controles })}</span>
          ${enRetard ? complement(I18n.t('accueil.tuile_conformite.dont_retard', { enRetard }), 'rouge') : complement(I18n.t('accueil.tuile_conformite.aucun_retard'))}</span>${UI.icone('chevron', 'bento-chevron')}</a>
        <a class="bento-sous-lien" href="#/equipe?filtre=a-renouveler">${chiffre(habilitations)}<span class="bento-sous-texte"><span>${I18n.t('accueil.tuile_conformite.habilitations_renouveler', { n: habilitations })}</span>
          ${echues ? complement(I18n.t('accueil.tuile_conformite.dont_echues', { n: echues }), 'ambre') : complement(I18n.t('accueil.tuile_conformite.aucune_echue'))}</span>${UI.icone('chevron', 'bento-chevron')}</a>
      </div>
    </div>`;
  }

  function tuilesSurveiller(compteurs, aujourdhui) {
    const critiques = compteurs.articlesACommander.filter((a) => a.article.critique === '1').length;
    // Suggestions est chargé après ce fichier : appelé au moment de l'affichage.
    const suggestions = Suggestions.ouvertes(aujourdhui);
    const surA = suggestions.filter((suggestion) => suggestion.criticite === 'A').length;
    return UI.html`
      ${surveiller('#/magasin?onglet=a-commander', 'ambre', compteurs.articlesACommander.length, I18n.t('accueil.tuiles_surveiller.articles_commander'),
        critiques ? complement(I18n.t('accueil.tuiles_surveiller.dont_critiques', { n: critiques }), 'rouge') : complement(I18n.t('accueil.tuiles_surveiller.stock_point_commande')))}
      ${tuileConformite(compteurs, aujourdhui)}
      ${surveiller('#/preventif?onglet=suggestions', 'vert', suggestions.length, I18n.t('accueil.tuiles_surveiller.suggestions_preventif'),
        surA ? complement(I18n.t('accueil.tuiles_surveiller.dont_criticite', { surA }), 'ambre') : complement(I18n.t('accueil.tuiles_surveiller.examiner')))}`;
  }

  // ===========================================================================================
  // 4. État du PC serveur : copie externe des sauvegardes (D133, §22.11) et Tailscale (D128, §22.8)
  // ===========================================================================================

  const JOURS_ALERTE_CLE_TAILSCALE = 14;        // même seuil que serveur.py (JOURS_ALERTE_CLE_TAILSCALE)

  /**
   * Texte de l'avertissement (fragment UI.html), ou '' quand tout va bien ou qu'aucun dossier de copie n'est réglé.
   * `copie` : copieExterne de App.adaptateur.info(), { derniereReussie, joursSansCopie, erreur } ou null. Avertit quand
   * la dernière copie a échoué ou qu'aucune copie n'a été faite depuis plus d'un jour.
   */
  function avertissementCopieExterne(copie) {
    if (!copie) return '';
    const jours = typeof copie.joursSansCopie === 'number' ? copie.joursSansCopie : null;
    if (!copie.erreur && !(jours !== null && jours > 1)) return '';
    let constat = I18n.t('accueil.avertissement_copie_externe.derniere_copie_echoue');
    if (jours === null) constat = I18n.t('accueil.avertissement_copie_externe.aucune_copie_reussie_instant');
    else if (jours >= 1) constat = I18n.t('accueil.avertissement_copie_externe.aucune_copie_depuis', { n: jours });
    return UI.html`${I18n.html('accueil.avertissement_copie_externe.copie_externe_sauvegardes_copie', { constat, erreur: copie.erreur || '' })}`;
  }

  /**
   * Texte de l'avertissement Tailscale (fragment UI.html), ou '' quand Tailscale va bien, manque ou n'est pas attendu.
   * `tailscale` : tailscale de App.adaptateur.info(), { present, connecte, nom, joursAvantExpiration } ou null. Avertit
   * quand Tailscale est déconnecté (les téléphones hors de l'atelier ne joignent plus Prévo), sinon quand la clé expire
   * sous 14 jours, aujourd'hui, ou a expiré.
   */
  function avertissementTailscale(tailscale) {
    if (!tailscale || !tailscale.present) return '';
    if (!tailscale.connecte) {
      return UI.html`${I18n.html('accueil.avertissement_tailscale.tailscale_deconnecte_telephones_hors')}`;
    }
    const jours = tailscale.joursAvantExpiration;
    if (jours === null || jours > JOURS_ALERTE_CLE_TAILSCALE) return '';
    let echeance = I18n.t('accueil.avertissement_tailscale.expire_dans', { n: jours });
    if (jours === 0) echeance = I18n.t('accueil.avertissement_tailscale.expire_aujourd_hui');
    else if (jours < 0) echeance = I18n.t('accueil.avertissement_tailscale.expire');
    return UI.html`${I18n.html('accueil.avertissement_tailscale.cle_tailscale_desactivez_expiration', { echeance, nom: tailscale.nom || I18n.t('accueil.avertissement_tailscale.pc') })}`;
  }

  // Pose l'avertissement (ou rien) dans sa zone ; data-lu marque la lecture faite, avertissement ou non (point
  // d'accroche des tests).
  function poserAvertissement(zone, id, texte) {
    if (texte) {
      const bloc = UI.bandeau('attention', texte);
      bloc.id = id;
      zone.className = 'alertes';
      zone.replaceChildren(bloc);
    }
    zone.dataset.lu = '1';
  }

  // État du PC serveur lu à chaque affichage (une seule lecture de GET /api/info) puis posé dans #copie-externe-zone et
  // #tailscale-zone : l'écran ne l'attend pas.
  async function afficherEtatServeur(conteneur) {
    const zoneCopie = conteneur.querySelector('#copie-externe-zone');
    const zoneTailscale = conteneur.querySelector('#tailscale-zone');
    if (!zoneCopie || !zoneTailscale) return;
    let info = null;
    if (App.mode === 'serveur' && typeof App.adaptateur.info === 'function') {
      try {
        info = await App.adaptateur.info();
      } catch (erreur) {
        console.warn('Prévo : état du PC serveur inconnu (' + (erreur && erreur.message) + ').', erreur);
      }
    }
    poserAvertissement(zoneCopie, 'alerte-copie-externe', avertissementCopieExterne(info ? info.copieExterne : null));
    poserAvertissement(zoneTailscale, 'alerte-tailscale', avertissementTailscale(info ? info.tailscale : null));
  }

  // ===========================================================================================
  // 5. Écran
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
    UI.remplir(conteneur, UI.html`${entete(aujourdhui)}<div id="maj-zone"></div>${alerteControle()}
      <div id="copie-externe-zone"></div><div id="tailscale-zone"></div>${carteBaseVide()}
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
    afficherEtatServeur(conteneur);
    App.definirTitreMobile(I18n.t('accueil.entete.bonjour'), dateEnLettres(aujourdhui, false));
  }

  return { afficherResponsable, choisirEnPremier, momentDeLaJournee, phraseDemandes, ligneSecondaire,
    avertissementCopieExterne, avertissementTailscale };
})());
