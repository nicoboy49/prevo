'use strict';
// Preventif (4/4) — onglet « Calendrier 12 semaines » de l'écran #/preventif (ARCHITECTURE.md §14.3,
// brief §9 E8) : une ligne par semaine (lundi → dimanche), lisible sur téléphone ; dans chaque
// semaine, les échéances des gammes (« estimée » pour une gamme au compteur) et les OT préventifs
// ouverts, avec leurs liens. Les calculs sont ceux de Preventif.calendrier (preventif-regles.js).
//   15. Outils (numéro de semaine, libellés)
//   16. Dessin du calendrier (Preventif.interne.afficherCalendrier, appelé par preventif-ecrans.js)
// Complète l'objet Preventif.

Object.assign(Preventif, (() => {

  const { texte, joursEntre } = Preventif.interne;

  // ===========================================================================================
  // 15. Outils
  // ===========================================================================================

  /** Numéro de semaine ISO 8601 d'une date 'AAAA-MM-JJ' (la semaine 1 contient le premier jeudi de l'année). */
  function numeroSemaine(dateIso) {
    const [annee, mois, jour] = dateIso.split('-').map(Number);
    const date = new Date(Date.UTC(annee, mois - 1, jour));
    const jourSemaine = date.getUTCDay() || 7;                      // 1 = lundi … 7 = dimanche
    date.setUTCDate(date.getUTCDate() + 4 - jourSemaine);           // jeudi de cette semaine
    const premierJanvier = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
    return Math.ceil(((date - premierJanvier) / 86400000 + 1) / 7);
  }

  /** '2026-10-19' → '19/10'. */
  function jourMois(dateIso) {
    return UI.dateFr(dateIso).slice(0, 5);
  }

  function repere(equipementId) {
    const equipement = Donnees.trouver('equipements', equipementId);
    return equipement ? (equipement.repere || equipement.id) : texte(equipementId);
  }

  // ===========================================================================================
  // 16. Dessin du calendrier
  // ===========================================================================================

  /** Une échéance de gamme ou un OT préventif ouvert, dans sa semaine. */
  function elementHtml(element, jour) {
    const gamme = element.gammeId ? Donnees.trouver('gammes', element.gammeId) : null;
    const ot = element.otId ? Donnees.trouver('ordres_travail', element.otId) : null;
    const enRetard = element.date < jour;
    const titre = gamme ? UI.html`<a href="#/preventif/gamme/${encodeURIComponent(gamme.id)}">${texte(gamme.libelle) || gamme.id}</a>`
      : texte(ot && ot.titre);
    return UI.html`<li class="pv-element${ot ? ' pv-element-ot' : ''}${enRetard ? ' pv-en-retard' : ''}"
        data-gamme="${element.gammeId}" data-ot="${element.otId}">
      <span class="pv-date sans-coupure">${UI.dateFr(element.date)}</span>
      <span class="pv-quoi"><b>${repere(element.equipementId)}</b> ${titre}</span>
      <span class="pv-marques">
        ${ot ? UI.html`<a class="pv-lien-ot" href="#/ot/${encodeURIComponent(ot.id)}">${ot.id}</a>${UI.badgeStatut(ot.statut)}`
          : UI.html`<span class="badge info">échéance</span>`}
        ${element.estimee ? UI.html`<span class="badge neutre" title="Date estimée d'après les heures de fonctionnement par jour">estimée</span>` : ''}
        ${enRetard ? UI.html`<span class="badge ko">en retard</span>` : ''}
      </span>
    </li>`;
  }

  function semaineHtml(semaine, rang, jour) {
    const courante = rang === 0;
    const elements = semaine.elements;
    return UI.html`<li class="pv-semaine${courante ? ' pv-semaine-courante' : ''}" data-lundi="${semaine.lundi}">
      <div class="pv-semaine-tete">
        <b>Semaine ${numeroSemaine(semaine.lundi)}</b>
        <span class="pv-semaine-dates">du ${jourMois(semaine.lundi)} au ${UI.dateFr(semaine.dimanche)}</span>
        ${courante ? UI.html`<span class="badge info">cette semaine</span>` : ''}
        <span class="badge ${elements.length ? 'cyan' : 'neutre'}" title="Éléments prévus">${elements.length}</span>
      </div>
      ${elements.length ? UI.html`<ul class="pv-elements">${elements.map((element) => elementHtml(element, jour))}</ul>`
        : UI.html`<p class="pv-rien">Rien de prévu.</p>`}
    </li>`;
  }

  /** Remplit le panneau de l'onglet « Calendrier » : semaines du lundi au dimanche, à partir de celle d'aujourd'hui. */
  function afficherCalendrier(panneau) {
    const jour = Donnees.aujourdhui();
    const semaines = Preventif.calendrier(jour);
    const enRetard = semaines.length ? semaines[0].elements.filter((e) => joursEntre(e.date, semaines[0].lundi) > 0).length : 0;
    UI.remplir(panneau, UI.html`
      <p class="note pv-legende">Échéances des gammes et OT préventifs ouverts, semaine par semaine. Une gamme au compteur
        a une date <b>estimée</b> (heures de fonctionnement par jour). Ce qui est en retard est rangé dans la semaine en cours.</p>
      ${enRetard ? UI.html`<p class="note">${enRetard} élément(s) en retard d'une semaine précédente.</p>` : ''}
      <ol class="pv-calendrier" aria-label="Calendrier du préventif sur ${semaines.length} semaines">
        ${semaines.map((semaine, rang) => semaineHtml(semaine, rang, jour))}
      </ol>`);
  }

  // Outil prêté à preventif-ecrans.js (usage interne au module).
  Object.assign(Preventif.interne, { afficherCalendrier });

  return {};
})());
