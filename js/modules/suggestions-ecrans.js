'use strict';
// Suggestions (2/2) — écrans du préventif suggéré (ARCHITECTURE.md §16.6 ; CDC du lot 3 bis, D57,
// D58, D60) : onglets « Suggestions » et « Décisions » de #/preventif, cartes et leurs actions
// (« Créer la gamme », « Ouvrir la gamme », « Ignorer… »), encarts des fiches gamme et équipement.
// Réservé au responsable. Complète l'objet Suggestions (suggestions-regles.js).
//    7. Petits outils d'affichage (badges, liens, rappel d'une suggestion)
//    8. Carte d'une suggestion et action « Ignorer… » (fenêtre au motif obligatoire)
//    9. Onglets « Suggestions » et « Décisions » de #/preventif
//   10. Encarts des fiches équipement (parc-fiche.js) et gamme (preventif-ecrans.js)
//   11. Relais de preventif-ecrans.js : formulaire de création (S1) et fiche d'une gamme (S2 à S4) ;
//       la suggestion suivie est marquée « traitée » au journal après la création ou la modification
// Prévo ne modifie jamais une gamme tout seul : afficher une suggestion n'écrit rien. Seules les
// décisions du responsable écrivent, au journal (Suggestions.ignorer, Suggestions.marquerTraitee).

Object.assign(Suggestions, (() => {

  const ONGLETS = ['suggestions', 'decisions'];
  const ROUTE_ACCUEIL = '#/accueil';
  const LIBELLES_PROFIL = { demandeur: 'Demandeur', technicien: 'Technicien', responsable: 'Responsable' };
  // Couleur du badge de chaque règle et de chaque criticité : le texte dit toujours le type.
  const TONS_REGLES = { S1: 'info', S2: 'attention', S3: 'violet', S4: 'ok' };
  const TONS_CRITICITE = { A: 'ko', B: 'attention', C: 'neutre' };
  const OT_MONTRES = 5;                                   // OT liés montrés sur une carte, puis « et n autres »
  const MOTIF_MAX = 300;
  const PLUS_OUVERTE = 'Cette suggestion n\'est plus ouverte (déjà décidée, ou les faits ont changé)';

  // Suggestions marquées traitées depuis l'ouverture de Prévo (clé → ce qui a été fait) : après un
  // réaffichage, le rappel le dit, et une même suggestion n'est jamais marquée deux fois.
  const traitees = new Map();
  // Suggestion suivie par l'écran affiché (formulaire de création ou fiche d'une gamme) ; remise à
  // zéro à chaque affichage de ces écrans. `signature` : état de la check-list à l'arrivée.
  let suivi = { cle: '', gammeId: '', equipementId: '', signature: '' };

  // ===========================================================================================
  // 7. Petits outils d'affichage
  // ===========================================================================================

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  function jour() {
    return Donnees.aujourdhui();
  }

  /** « S2 · Revoir le préventif » : le type en clair (la couleur aide seulement). */
  function badgeType(s) {
    return UI.html`<span class="badge ${TONS_REGLES[s.regle] || 'neutre'} sg-type">${s.regle} · ${s.titre}</span>`;
  }

  function badgeCriticite(criticite) {
    return criticite
      ? UI.html`<span class="badge ${TONS_CRITICITE[criticite] || 'neutre'} sg-criticite">Criticité ${criticite}</span>`
      : UI.html`<span class="badge neutre sg-criticite">Criticité non renseignée</span>`;
  }

  /** « PO-02 — Pompe de relevage » ; l'identifiant seul si l'équipement est introuvable. */
  function libelleEquipement(equipementId) {
    const equipement = Donnees.trouver('equipements', equipementId);
    if (!equipement) return texte(equipementId);
    return (texte(equipement.repere) || equipement.id) + (texte(equipement.designation) ? ' — ' + texte(equipement.designation) : '');
  }

  function lienEquipement(equipementId) {
    return UI.html`<a href="#/equipement/${encodeURIComponent(equipementId)}">${libelleEquipement(equipementId)}</a>`;
  }

  /**
   * « OT liés : OT-… (11/09/2026), OT-… et 9 autres » (dans l'ordre reçu ; `limite` liens au plus).
   * `dateDe(rang)` (facultatif) : date affichée après le lien de ce rang.
   */
  function liensHtml(classe, libelle, ids, prefixe, limite, dateDe) {
    if (!ids.length) return '';
    const montres = ids.slice(0, limite || ids.length);
    const reste = ids.length - montres.length;
    return UI.html`<p class="sg-liens ${classe}"><span class="sg-libelle">${libelle}</span>
      ${montres.map((id, rang) => UI.html`${rang ? ', ' : ''}<a href="${prefixe}${encodeURIComponent(id)}">${id}</a>${dateDe
        ? UI.html` <span class="sg-date">(${UI.dateFr(dateDe(rang))})</span>` : ''}`)}${reste
      ? UI.html` <span>et ${reste} ${reste > 1 ? 'autres' : 'autre'}</span>` : ''}</p>`;
  }

  /**
   * Dates des faits (CS53) : « Dates : du 03/11/2025 au 11/09/2026 » (« le … » pour un seul jour).
   * `s.dates` va du plus ancien au plus récent ; `s.ots` du plus récent au plus ancien : l'OT de
   * rang r a la date de rang (n − 1 − r).
   */
  function datesHtml(s) {
    if (!s.dates.length) return '';
    const premier = s.dates[0];
    const dernier = s.dates[s.dates.length - 1];
    return UI.html`<p class="sg-dates"><span class="sg-libelle">Dates :</span> ${premier === dernier
      ? UI.html`le ${UI.dateFr(premier)}` : UI.html`du ${UI.dateFr(premier)} au ${UI.dateFr(dernier)}`}</p>`;
  }

  function dateDeLOt(s) {
    return (rang) => s.dates[s.dates.length - 1 - rang];
  }

  /** « Ignorée le 23/03/2026 : <motif> ; revenue sur de nouveaux faits ». */
  function decisionPrecedenteHtml(s) {
    const decision = s.decisionPrecedente;
    if (!decision) return '';
    const motif = texte(decision.texte).replace(/[\s.;]+$/, '');        // « … gammes. ; » → « … gammes ; »
    return UI.html`<p class="sg-precedente">${decision.decision === 'ignorée' ? 'Ignorée' : 'Traitée'} le ${UI.dateFr(decision.dateHeure)} : ${motif} ; revenue sur de nouveaux faits</p>`;
  }

  function messageTraitee(cle) {
    return 'Suggestion marquée traitée (inscrite au journal) : ' + traitees.get(cle) + '.';
  }

  /** Rappel d'une suggestion en tête du formulaire ou de la fiche d'une gamme ; `s` null : clé seule. */
  function rappelElement(cle, s, message, ton) {
    return UI.element(UI.html`<section class="encadre ${ton || 'info'} sg-rappel" data-cle="${cle}" aria-label="Suggestion ${cle}">
      <p class="sg-rappel-tete">${s ? badgeType(s) : ''}<b>Suggestion ${cle}</b></p>
      ${s ? UI.html`<p class="sg-texte">${s.texte}</p>` : ''}
      <p class="sg-rappel-etat" role="status">${message}</p>
    </section>`);
  }

  // ===========================================================================================
  // 8. Carte d'une suggestion et action « Ignorer… »
  // ===========================================================================================

  function adresseCreation(s) {
    return '#/preventif/gamme/nouvelle?equipement=' + encodeURIComponent(s.equipementId) + '&suggestion=' + encodeURIComponent(s.cle);
  }

  function adresseGamme(gammeId, cle) {
    return '#/preventif/gamme/' + encodeURIComponent(gammeId) + '?suggestion=' + encodeURIComponent(cle);
  }

  /** S1 : « Créer la gamme » ; S2 à S4 : « Ouvrir la gamme <id> » par gamme citée ; toujours « Ignorer… ». */
  function actionsHtml(s) {
    const liens = s.regle === 'S1'
      ? UI.html`<a class="btn btn-primaire" href="${adresseCreation(s)}">${UI.icone('ajouter')}Créer la gamme</a>`
      : s.gammeIds.map((id) => UI.html`<a class="btn btn-secondaire" href="${adresseGamme(id, s.cle)}">${UI.icone('preventif')}Ouvrir la gamme ${id}</a>`);
    return UI.html`<div class="actions sg-actions">${liens}
      <button type="button" class="btn btn-fantome" data-action="ignorer" aria-label="Ignorer la suggestion ${s.cle}">Ignorer…</button></div>`;
  }

  function carteHtml(s) {
    return UI.html`<article class="sg-carte" data-cle="${s.cle}" data-regle="${s.regle}">
      <div class="sg-carte-tete">${badgeType(s)}${badgeCriticite(s.criticite)}</div>
      <h3 class="sg-titre">${lienEquipement(s.equipementId)}</h3>
      <p class="sg-texte">${s.texte}</p>
      <p class="sg-question">${s.question}</p>
      ${datesHtml(s)}
      ${liensHtml('sg-ots', 'OT liés :', s.ots, '#/ot/', OT_MONTRES, dateDeLOt(s))}
      ${liensHtml('sg-dis', 'DI liées :', s.dis, '#/di/')}
      ${decisionPrecedenteHtml(s)}
      ${actionsHtml(s)}
    </article>`;
  }

  /** Cartes d'une liste ; l'écouteur de « Ignorer… » est posé sur ce bloc (redessiné à chaque affichage). */
  function cartesElement(liste) {
    const bloc = UI.element(UI.html`<div class="sg-cartes">${liste.map((s) => carteHtml(s))}</div>`);
    bloc.addEventListener('click', (evenement) => {
      const bouton = evenement.target.closest('button[data-action="ignorer"]');
      if (bouton && bloc.contains(bouton)) ignorerDepuisCarte(bouton.closest('[data-cle]').dataset.cle);
    });
    return bloc;
  }

  function champMotif() {
    const id = UI.identifiantUnique('sg-motif');
    return UI.element(UI.html`<div class="champ" data-champ="motif">
      <label class="libelle" for="${id}">Motif <span class="requis" aria-hidden="true">*</span></label>
      <textarea id="${id}" name="motif" rows="3" maxlength="${MOTIF_MAX}" required aria-required="true" data-dictee
        aria-describedby="${id}-aide ${id}-erreur" placeholder="Ex. périodicité imposée par le constructeur"></textarea>
      <p class="aide" id="${id}-aide">Inscrit au journal. La suggestion reviendra si de nouveaux faits atteignent de nouveau le seuil.</p>
      <p class="erreur-champ" id="${id}-erreur" role="alert" hidden></p></div>`);
  }

  /**
   * « Ignorer… » : fenêtre au motif obligatoire. Un refus (motif vide, trop long, suggestion qui n'est
   * plus ouverte) s'affiche sous le champ et la fenêtre reste ouverte ; boutons désactivés pendant
   * l'écriture au journal. Puis message et réaffichage (la carte disparaît).
   */
  async function ignorerDepuisCarte(cle) {
    const s = Suggestions.trouver(cle, jour());
    const contenu = UI.element(UI.html`<div class="form-colonne sg-fenetre"><p>${s ? s.texte : cle}</p></div>`);
    const champ = contenu.appendChild(champMotif());
    const zone = UI.$('textarea', champ);
    const erreur = UI.$('.erreur-champ', champ);
    const montrerErreur = (message) => {
      erreur.textContent = message;
      erreur.hidden = !message;
      if (message) { zone.setAttribute('aria-invalid', 'true'); zone.focus(); } else zone.removeAttribute('aria-invalid');
    };
    zone.addEventListener('input', () => { if (zone.value.trim()) montrerErreur(''); });
    let fermer = null;
    let fait = false;
    let enCours = false;
    let ecriture = null;                 // écriture en cours : attendue même si la fenêtre est fermée (Échap)

    async function valider(dialogue) {
      if (enCours) return;
      if (!zone.value.trim()) { montrerErreur('Indiquez pourquoi vous ignorez cette suggestion : le motif est inscrit au journal.'); return; }
      enCours = true;
      const boutons = UI.$$('button', dialogue);
      boutons.forEach((bouton) => { bouton.disabled = true; });
      try {
        ecriture = Suggestions.ignorer(cle, zone.value);
        await ecriture;
        fait = true;
        fermer('ok');
      } catch (refus) {
        if (refus instanceof Donnees.ErreurValidation) montrerErreur(refus.message);
        else App.signalerErreur(refus, 'décision sur la suggestion');
      } finally {
        enCours = false;
        boutons.forEach((bouton) => { bouton.disabled = false; });
      }
    }

    const choix = await UI.fenetre({
      titre: 'Ignorer la suggestion ' + cle, contenu,
      boutons: [{ libelle: 'Annuler', valeur: null, classe: 'btn-fantome' },
        { libelle: 'Ignorer la suggestion', valeur: 'ok', classe: 'btn-primaire', defaut: true }],
      surOuverture(dialogue, fermerFenetre) { fermer = fermerFenetre; },
      avantFermeture(valeur, dialogue) {
        if (valeur !== 'ok' || fait) return true;
        valider(dialogue);                              // la fenêtre se ferme toute seule si c'est écrit
        return false;
      },
    });
    if (choix !== 'ok' && ecriture) await ecriture.catch(() => {});   // fermée pendant l'écriture : son issue décide
    if (!fait) return;
    UI.toast('Suggestion ignorée (inscrite au journal).', 'succes');
    await App.reafficher();
  }

  // ===========================================================================================
  // 9. Onglets « Suggestions » et « Décisions » de #/preventif (responsable)
  // ===========================================================================================

  /** Encadré « Comprendre » : définitions (§16.2), les quatre règles avec les seuils en vigueur. */
  function comprendreHtml(r) {
    const depuisFormat2 = r.passageFormat2 ? ' (comptées depuis le passage au format 2, le ' + UI.dateFr(r.passageFormat2) + ')' : '';
    return UI.html`<details class="encadre sg-comprendre">
      <summary>Comprendre les suggestions</summary>
      <p><b>Prévo ne modifie jamais une gamme tout seul.</b> Une suggestion n'écrit rien : vous décidez.
        « Créer la gamme » et « Ouvrir la gamme » mènent aux écrans du préventif ; la suggestion est marquée traitée quand
        vous créez ou modifiez la gamme. « Ignorer… » demande un motif. Chaque décision est inscrite au journal (onglet « Décisions »).</p>
      <p><b>Les quatre règles</b></p>
      <ul>
        <li><b>S1 · Créer une gamme</b> : équipement suivi sans aucune gamme active, au moins ${r.seuilPannes} pannes de même cause sur la période.</li>
        <li><b>S2 · Revoir le préventif</b> : équipement dont une gamme suivie a déjà eu une visite ; au moins ${r.seuilPannes} pannes
          de même cause sur la période, après la première visite. À examiner : la gamme ne dit pas quelles pannes elle prévient.</li>
        <li><b>S3 · Anomalies répétées</b> : gamme suivie avec une anomalie à au moins 2 des 4 dernières visites.</li>
        <li><b>S4 · Allonger une gamme</b> : gamme suivie d'un équipement de criticité B ou C (jamais A) ; au moins
          ${r.visitesSansConstat} visites de suite sans anomalie${depuisFormat2}, et aucune panne de l'équipement depuis la première
          de ces visites. Les contrôles réglementaires ne sont jamais suggérés.</li>
      </ul>
      <p><b>Définitions</b></p>
      <ul>
        <li><b>Période</b> : les ${r.fenetreMois} derniers mois, du ${UI.dateFr(r.debutFenetre)} à aujourd'hui.</li>
        <li><b>Panne de même cause</b> : OT correctif (immédiat ou différé) clôturé, avec le même code cause (toutes les causes, « Autre cause » comprise).</li>
        <li><b>Équipement suivi</b> : actif et pas au rebut. <b>Gamme suivie</b> : active, par date ou au compteur (jamais au seuil), d'un équipement suivi.</li>
        <li><b>Visite</b> : OT clôturé d'une gamme. <b>Anomalie</b> : case « anomalie constatée » cochée, ou demande d'intervention créée depuis la visite.</li>
        <li><b>Date d'un OT</b> : fin des travaux, sinon clôture technique, sinon création.</li>
        <li><b>Intervalle médian</b> : l'écart du milieu, en jours, entre deux pannes qui se suivent (la moitié des écarts sont plus courts).</li>
        <li><b>Après une décision</b> (ignorée ou traitée), seuls les faits postérieurs comptent : la suggestion revient s'ils atteignent de nouveau le seuil.</li>
      </ul>
      <p>Ordre des cartes : S2, S3, S1 puis S4 ; puis criticité A, B, C ; puis nombre de faits. Les seuils se règlent dans Paramètres
        (section « Suggestions de préventif »).</p>
    </details>`;
  }

  function afficherSuggestions(panneau, calcul) {
    const nombre = calcul.ouvertes.length;
    UI.remplir(panneau, UI.html`<div class="suggestions">
      <p class="note sg-intro">Pistes tirées de l'historique des pannes et des visites. Prévo ne modifie jamais une gamme tout seul : vous décidez.</p>
      ${comprendreHtml(calcul.reglages)}
      <h2 class="sg-compteur">${nombre ? nombre + (nombre > 1 ? ' suggestions ouvertes' : ' suggestion ouverte') : 'Aucune suggestion ouverte'}</h2>
    </div>`);
    UI.$('.suggestions', panneau).appendChild(nombre ? cartesElement(calcul.ouvertes)
      : UI.element(UI.vide('Rien à revoir pour le moment', 'Une suggestion apparaît ici quand les pannes, les anomalies ou les visites '
        + 'sans constat atteignent les seuils (voir « Comprendre »).', 'preventif')));
  }

  /** Équipement (S1, S2) ou gamme (S3, S4) qui porte la décision, en lien s'il existe encore. */
  function cibleHtml(d) {
    if (d.table === 'gammes' && Donnees.trouver('gammes', d.idLigne)) {
      const gamme = Donnees.trouver('gammes', d.idLigne);
      return UI.html`<a href="#/preventif/gamme/${encodeURIComponent(gamme.id)}">${gamme.id}</a><span class="sg-sous">${libelleEquipement(gamme.equipement_id)}</span>`;
    }
    if (d.table === 'equipements' && Donnees.trouver('equipements', d.idLigne)) return lienEquipement(d.idLigne);
    return d.idLigne;
  }

  function decisionHtml(d) {
    return UI.html`${UI.badgeStatut(d.decision, d.decision === 'traitée' ? 'ok' : 'neutre')}${d.revenue
      ? UI.html` <span class="badge attention sg-revenue" title="De nouveaux faits ont de nouveau atteint le seuil : la suggestion est rouverte.">revenue</span>` : ''}`;
  }

  function cleHtml(d) {
    return UI.html`<span class="sg-cle" data-cle="${d.cle}">${d.cle}</span><span class="sg-sous">${d.regle} · ${Suggestions.TITRES[d.regle] || ''}</span>`;
  }

  function afficherDecisions(panneau, decisions) {
    if (!decisions.length) {
      UI.remplir(panneau, UI.vide('Aucune décision', 'Les suggestions ignorées ou traitées apparaîtront ici, avec leur motif.', 'preventif'));
      return;
    }
    UI.remplir(panneau, UI.html`<div class="suggestions">
      <p class="note">Décisions inscrites au journal, de la plus récente à la plus ancienne.</p>
      <div class="carte sg-decisions-tableau"></div>
      <ul class="liste-cartes sg-decisions-cartes">${decisions.map((d) => UI.html`<li><div class="carte-ligne sg-decision">
        <div class="carte-tete">${cleHtml(d)}${decisionHtml(d)}</div>
        <div class="carte-titre">${cibleHtml(d)}</div>
        <div class="sg-decision-texte">${d.texte}</div>
        <div class="carte-meta"><span>${UI.dateHeureFr(d.dateHeure)}</span><span>${d.profil}</span></div></div></li>`)}</ul>
    </div>`);
    UI.$('.sg-decisions-tableau', panneau).appendChild(UI.tableau({
      colonnes: [
        { cle: 'dateHeure', libelle: 'Date', classe: 'sans-coupure', rendu: (d) => UI.dateHeureFr(d.dateHeure) },
        { cle: 'cle', libelle: 'Suggestion', rendu: cleHtml },
        { cle: 'idLigne', libelle: 'Équipement / gamme', rendu: cibleHtml },
        { cle: 'decision', libelle: 'Décision', rendu: decisionHtml },
        { cle: 'texte', libelle: 'Motif ou suite donnée', classe: 'sg-col-texte' },
        { cle: 'profil', libelle: 'Profil' },
      ],
      lignes: decisions, libelle: 'Décisions sur les suggestions de préventif',
    }));
  }

  /**
   * Relais de preventif-ecrans.js : définitions des onglets « Suggestions » (compteur = nombre
   * ouvert) et « Décisions » pour UI.onglets ; liste vide pour un autre profil que le responsable.
   */
  function ongletsPreventif() {
    if (!App.estResponsable()) return [];
    const calcul = Suggestions.calculer(jour());
    return [
      { id: 'suggestions', libelle: 'Suggestions', compteur: calcul.ouvertes.length, afficher: (panneau) => afficherSuggestions(panneau, calcul) },
      { id: 'decisions', libelle: 'Décisions', afficher: (panneau) => afficherDecisions(panneau, calcul.decisions) },
    ];
  }

  /**
   * Relais de preventif-ecrans.js : ?onglet=suggestions|decisions demandé par un autre profil que le
   * responsable → message des écrans interdits (même forme que js/app.js) et accueil. Vrai si refusé.
   */
  function ongletRefuse(requete) {
    if (App.estResponsable() || !ONGLETS.includes(requete.get('onglet'))) return false;
    const profil = App.profil;
    UI.toast('L\'écran « Suggestions de préventif » n\'est pas disponible pour le profil '
      + (LIBELLES_PROFIL[profil && profil.type] || '') + '.', 'attention');
    try { history.replaceState(history.state, '', ROUTE_ACCUEIL); } catch (erreur) { /* adresse gardée telle quelle */ }
    App.naviguer(ROUTE_ACCUEIL);
    return true;
  }

  // ===========================================================================================
  // 10. Encarts « Suggestions de préventif » des fiches (responsable, suggestions ouvertes seulement)
  // ===========================================================================================

  function encart(liste) {
    if (!liste.length) return null;
    const id = UI.identifiantUnique('sg-titre-encart');
    const section = UI.element(UI.html`<section class="carte sg-encart" aria-labelledby="${id}">
      <div class="entete-carte"><h2 id="${id}">Suggestions de préventif <span class="badge">${liste.length}</span></h2>
        <a class="sg-tout" href="#/preventif?onglet=suggestions">Toutes les suggestions</a></div>
      <p class="note">Pistes tirées de l'historique : Prévo ne modifie jamais une gamme tout seul, vous décidez.</p>
    </section>`);
    section.appendChild(cartesElement(liste));
    return section;
  }

  /** Fiche équipement : S1, S2 de l'équipement et S3, S4 de ses gammes ; élément DOM ou null. */
  function encartEquipement(equipementId) {
    return App.estResponsable() ? encart(Suggestions.pourEquipement(equipementId, jour())) : null;
  }

  /** Fiche gamme : S2 qui la citent, S3, S4 ; sans la suggestion déjà rappelée en tête de fiche. */
  function encartGamme(gammeId) {
    if (!App.estResponsable()) return null;
    const rappelee = suivi.gammeId === gammeId ? suivi.cle : '';
    return encart(Suggestions.pourGamme(gammeId, jour()).filter((s) => s.cle !== rappelee));
  }

  // ===========================================================================================
  // 11. Relais du formulaire de création et de la fiche d'une gamme (preventif-ecrans.js)
  // ===========================================================================================

  function minusculeInitiale(valeur) {
    const propre = texte(valeur);
    return propre.charAt(0).toLowerCase() + propre.slice(1);
  }

  function signatureCheckListe(gammeId) {
    return JSON.stringify(Preventif.interne.operationsDeGamme(gammeId)
      .map((op) => [op.id, op.ordre, op.operation, op.valeur_attendue]));
  }

  function rappelHorsSuivi(cle, complement) {
    return traitees.has(cle) ? rappelElement(cle, null, messageTraitee(cle), 'ok')
      : rappelElement(cle, null, PLUS_OUVERTE + complement, 'attention');
  }

  function actualiserRappel(cle) {
    UI.$$('.sg-rappel').filter((rappel) => rappel.dataset.cle === cle).forEach((rappel) => {
      rappel.classList.remove('info', 'attention');
      rappel.classList.add('ok');
      UI.$('.sg-rappel-etat', rappel).textContent = messageTraitee(cle);
    });
  }

  /**
   * Marque la suggestion suivie « traitée » au journal, une seule fois. Un échec est signalé par un
   * message « attention » et ne défait rien de ce qui a été enregistré ; vrai si c'est marqué.
   */
  async function marquer(ceQuiAEteFait, messageReussite) {
    const cle = suivi.cle;
    suivi.cle = '';
    try {
      await Suggestions.marquerTraitee(cle, ceQuiAEteFait);
    } catch (erreur) {
      suivi.cle = cle;                                    // nouvel essai à la prochaine modification
      console.warn('Prévo : suggestion ' + cle + ' non marquée traitée (' + (erreur && erreur.message) + ').', erreur);
      UI.toast('C\'est enregistré, mais la suggestion ' + cle + ' n\'a pas pu être marquée traitée : '
        + ((erreur && erreur.message) || 'erreur inconnue'), 'attention');
      return false;
    }
    traitees.set(cle, ceQuiAEteFait);
    actualiserRappel(cle);
    if (messageReussite) UI.toast(messageReussite, 'succes');
    return true;
  }

  /**
   * #/preventif/gamme/nouvelle?equipement=<id>&suggestion=<clé> : valeurs initiales du formulaire et
   * rappel de la suggestion (élément ou null). Une S1 ouverte de cet équipement pré-remplit le libellé
   * « Prévenir : <cause> » et le déclencheur « date » ; rien n'est écrit avant « Créer la gamme ».
   */
  function preparerCreation(requete) {
    suivi = { cle: '', gammeId: '', equipementId: '', signature: '' };
    const valeurs = { equipement_id: requete.get('equipement') || '', declencheur: 'date' };
    const cle = requete.get('suggestion') || '';
    if (!cle || !App.estResponsable()) return { valeurs, rappel: null };
    const s = Suggestions.trouver(cle, jour());
    if (!s || s.regle !== 'S1' || s.equipementId !== valeurs.equipement_id) {
      return { valeurs, rappel: rappelHorsSuivi(cle, ' ou ne concerne pas cet équipement : rien n\'est pré-rempli.') };
    }
    suivi = { cle, gammeId: '', equipementId: s.equipementId, signature: '' };
    valeurs.libelle = 'Prévenir : ' + minusculeInitiale(s.causeLibelle);
    return { valeurs, rappel: rappelElement(cle, s, 'Rien n\'est écrit tant que vous n\'avez pas cliqué « Créer la gamme » ; '
      + 'la suggestion sera alors marquée traitée (inscrite au journal).') };
  }

  /** Après « Créer la gamme » : la S1 suivie est marquée traitée si la gamme est bien sur son équipement. */
  async function apresCreationGamme(gammeId) {
    const gamme = Donnees.trouver('gammes', gammeId);
    if (!suivi.cle || !gamme || gamme.equipement_id !== suivi.equipementId) return;
    await marquer('gamme ' + gammeId + ' créée',
      'Gamme ' + gammeId + ' créée, suggestion marquée traitée (inscrite au journal) : ajoutez maintenant sa check-list.');
  }

  /**
   * #/preventif/gamme/<id>?suggestion=<clé> (responsable) : rappel en tête de fiche (élément ou null).
   * La suggestion est suivie si elle est ouverte et cite cette gamme. À appeler à chaque affichage
   * de la fiche (avant encartGamme), pour tous les profils.
   */
  function suiviFiche(gammeId, requete) {
    suivi = { cle: '', gammeId, equipementId: '', signature: signatureCheckListe(gammeId) };
    const cle = requete.get('suggestion') || '';
    if (!cle || !App.estResponsable()) return null;
    const s = traitees.has(cle) ? null : Suggestions.trouver(cle, jour());
    if (!s || !s.gammeIds.includes(gammeId)) return rappelHorsSuivi(cle, ' ou ne concerne pas cette gamme : rien ne sera marqué.');
    suivi.cle = cle;
    return rappelElement(cle, s, 'Enregistrez la gamme ou modifiez sa check-list : la suggestion sera marquée traitée.');
  }

  /** Après un enregistrement de la gamme : marquée traitée s'il y a au moins un champ changé. */
  async function apresModificationGamme(gammeId, changes) {
    if (!suivi.cle || suivi.gammeId !== gammeId || !changes || !changes.length) return;
    await marquer('gamme modifiée : ' + changes.join(', '), 'Gamme enregistrée, suggestion marquée traitée (inscrite au journal).');
  }

  /** Après une action sur la check-list : marquée traitée si la check-list a changé depuis l'arrivée. */
  async function apresCheckListe(gammeId) {
    if (!suivi.cle || suivi.gammeId !== gammeId || signatureCheckListe(gammeId) === suivi.signature) return;
    await marquer('check-list modifiée');
  }

  return {
    ONGLETS,
    ongletsPreventif, ongletRefuse, encartEquipement, encartGamme,
    preparerCreation, apresCreationGamme, suiviFiche, apresModificationGamme, apresCheckListe,
  };
})());
