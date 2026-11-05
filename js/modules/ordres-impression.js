'use strict';
// Ordres (7/7) — bon de travail A4 (rempli dans #impression, puis window.print()) et
// enregistrement des écrans du module auprès d'App (ARCHITECTURE.md §8, §10 et §14.2). Dernier
// fichier du module : les fonctions d'affichage des fichiers précédents existent déjà.

Object.assign(Ordres, (() => {

  // Constantes, outils et écrans des fichiers précédents (ordres-regles.js à ordres-pieces.js).
  const { nomTechnicien } = Ordres;
  const { texte, nombre, equipementDe, cheminLocalisation, lignesDeLOt, operationsDe,
    afficherListe, afficherNouveau, afficherFiche } = Ordres.interne;

  // ===========================================================================================
  // 11. Bon de travail (impression A4 dans #impression, puis window.print())
  // ===========================================================================================

  function lignesVides(nombreLignes) {
    return UI.brut(new Array(nombreLignes).fill('<span></span>').join(''));
  }

  function qrBon(equipement) {
    if (!equipement) return '';
    try {
      return UI.html`${UI.qrSvg(App.urlFicheEquipement(equipement.id), 100)}<span>${equipement.repere || equipement.id}</span>`;
    } catch (erreur) {
      console.warn('Prévo : QR du bon de travail impossible (' + (erreur && erreur.message) + ').', erreur);
      return UI.html`<span>${equipement.repere || equipement.id}</span>`;
    }
  }

  /** HTML du bon de travail d'un OT (structure .bon-travail de css/style.css §14). */
  function bonDeTravailHtml(ot) {
    const equipement = equipementDe(ot) || {};
    const operations = operationsDe(ot.id);
    const pieces = lignesDeLOt('ot_pieces', ot.id).filter((p) => nombre(p.quantite_prevue) > 0);
    const di = ot.di_id ? Donnees.trouver('demandes', ot.di_id) : null;
    const entreprise = Donnees.parametre('entreprise_nom', '');
    const maintenant = Donnees.maintenant();
    return UI.html`<article class="bon-travail">
      <header class="bt-entete">
        <div>
          <div class="bt-entreprise">${entreprise ? I18n.t('ordres.bon_de_travail.entreprise_prevo', { entreprise }) : I18n.t('ordres.bon_de_travail.prevo')}</div>
          <h1>${I18n.t('ordres.bon_de_travail.bon_travail')}</h1>
          <div class="bt-numero">${ot.id} <span class="bt-priorite">${ot.priorite}</span></div>
          <div class="bt-meta">${I18n.html('ordres.bon_de_travail.type_statut_prevu_technicien', { otType: ot.type, otStatut: ot.statut, datePrevue: UI.dateFr(ot.date_prevue) || '—', technicien: nomTechnicien(ot.technicien_id) || '—', tempsPrevu: ot.temps_prevu_h ? UI.heures(ot.temps_prevu_h) : '—' })}</div>
        </div>
        <div class="bt-qr">${qrBon(equipementDe(ot))}</div>
      </header>
      <div class="bt-colonnes">
        <section class="bt-equipement"><h2>${I18n.t('commun.champ.equipement')}</h2>
          <dl class="valeurs"><dt>${I18n.t('commun.champ.repere')}</dt><dd>${equipement.repere || ot.equipement_id}</dd><dt>${I18n.t('commun.champ.designation')}</dt><dd>${equipement.designation || ''}</dd>
            <dt>${I18n.t('ordres.bon_de_travail.localisation')}</dt><dd>${cheminLocalisation(equipement.localisation_id)}</dd><dt>${I18n.t('commun.champ.criticite')}</dt><dd>${equipement.criticite || ''}</dd>
            <dt>${I18n.t('ordres.bon_de_travail.habilitation')}</dt><dd>${equipement.habilitation_requise || 'aucune'}</dd></dl>
        </section>
        <section class="bt-travail"><h2>${I18n.t('ordres.bon_de_travail.travail_faire')}</h2>
          <p class="bt-texte">${ot.titre}</p>
          ${ot.travail_a_faire ? UI.html`<p class="bt-texte">${ot.travail_a_faire}</p>` : ''}
          ${ot.consignes ? UI.html`<p class="bt-texte">${I18n.html('ordres.bon_de_travail.consignes_consignes', { consignes: ot.consignes })}</p>` : ''}
          ${di ? UI.html`<p>${I18n.html('ordres.bon_de_travail.demande_di_id', { diId: di.id, symptome: texte(di.symptome).replace(/[.\s]+$/, '') })}${di.impact ? ' ' + I18n.t('ordres.bon_de_travail.impact', { impact: di.impact }) : ''}</p>` : ''}
        </section>
      </div>
      <section class="bt-consignation"><h2>${I18n.t('ordres.bon_de_travail.consignation')}</h2>
        <p class="bt-texte">${texte(equipement.consignation) || I18n.t('ordres.bon_de_travail.aucune_procedure_renseignee_voir')}</p>
        <p class="bt-rappel">${Ordres.rappelConsignation()}</p>
        <div class="bt-case"><span class="bt-coche"></span>${I18n.t('ordres.bon_de_travail.consignation_appliquee')}</div>
      </section>
      <section class="bt-operations"><h2>${I18n.t('ordres.bon_de_travail.operations')}</h2>
        <table class="bt-table"><thead><tr><th class="bt-etroit">${I18n.t('ordres.bon_de_travail.n')}</th><th>${I18n.t('ordres.bon_de_travail.operation')}</th><th>${I18n.t('ordres.bon_de_travail.valeur_attendue')}</th><th>${I18n.t('ordres.bon_de_travail.mesure')}</th><th class="bt-etroit">${I18n.t('ordres.bon_de_travail.fait')}</th></tr></thead>
          <tbody>${operations.length ? operations.map((op) => UI.html`<tr><td class="bt-etroit">${op.ordre}</td><td>${op.operation}</td><td>${op.valeur_attendue}</td><td class="bt-a-remplir"></td><td class="bt-etroit"><span class="bt-coche"></span></td></tr>`)
            : UI.brut(new Array(3).fill('<tr><td class="bt-etroit"></td><td class="bt-a-remplir"></td><td></td><td></td><td class="bt-etroit"><span class="bt-coche"></span></td></tr>').join(''))}</tbody></table>
      </section>
      <section class="bt-pieces"><h2>${I18n.t('ordres.bon_de_travail.pieces')}</h2>
        <table class="bt-table"><thead><tr><th>${I18n.t('commun.champ.reference')}</th><th>${I18n.t('commun.champ.designation')}</th><th>${I18n.t('ordres.bon_de_travail.emplacement')}</th><th class="bt-etroit">${I18n.t('ordres.bon_de_travail.prevu')}</th><th class="bt-etroit">${I18n.t('ordres.bon_de_travail.utilise')}</th></tr></thead>
          <tbody>${pieces.map((p) => {
            const article = Donnees.trouver('articles', p.article_id) || {};
            return UI.html`<tr><td>${article.reference || p.article_id}</td><td>${article.designation || ''}</td><td>${article.emplacement || ''}</td><td class="bt-etroit">${UI.nombreFr(p.quantite_prevue)}</td><td class="bt-a-remplir"></td></tr>`;
          })}${UI.brut('<tr><td class="bt-a-remplir"></td><td></td><td></td><td></td><td></td></tr>')}</tbody></table>
      </section>
      <section class="bt-temps"><h2>${I18n.t('ordres.bon_de_travail.temps_passes')}</h2>
        <table class="bt-table"><thead><tr><th>${I18n.t('commun.champ.date')}</th><th>${I18n.t('commun.champ.technicien')}</th><th class="bt-etroit">${I18n.t('ordres.bon_de_travail.heures')}</th></tr></thead>
          <tbody>${UI.brut(new Array(3).fill('<tr><td class="bt-a-remplir"></td><td></td><td></td></tr>').join(''))}</tbody></table>
      </section>
      <section class="bt-compte-rendu"><h2>${I18n.t('ordres.bon_de_travail.compte_rendu')}</h2>
        <p>${I18n.t('ordres.bon_de_travail.cause_remede_arret_production')}</p>
        <div class="bt-lignes">${lignesVides(4)}</div>
        <div class="bt-case"><span class="bt-coche"></span>${I18n.t('ordres.bon_de_travail.equipement_remis_service_securite')}</div>
      </section>
      <section class="bt-signatures">
        <div class="bt-signature">${I18n.html('ordres.bon_de_travail.technicien_nom_date_signature')}</div>
        <div class="bt-signature">${I18n.html('ordres.bon_de_travail.production_remise_service_nom')}</div>
        <div class="bt-signature">${I18n.html('ordres.bon_de_travail.responsable_maintenance_nom_date')}</div>
      </section>
      <footer class="bt-pied">${I18n.html('ordres.bon_de_travail.bon_imprime', { date: UI.dateHeureFr(maintenant).replace(' ', ' ' + I18n.t('ordres.bon_de_travail.a') + ' '), otId: ot.id })}</footer>
    </article>`;
  }

  /** Remplit #impression avec le bon de travail puis lance l'impression ; vidé après impression. */
  function imprimerBon(otId) {
    const ot = Donnees.trouver('ordres_travail', otId);
    const zone = document.getElementById('impression');
    if (!ot || !zone) return;
    UI.remplir(zone, bonDeTravailHtml(ot));
    window.addEventListener('afterprint', () => { zone.textContent = ''; }, { once: true });
    window.print();
  }

  // ===========================================================================================
  // 12. Enregistrement des écrans (App est chargé après les modules)
  // ===========================================================================================

  document.addEventListener('DOMContentLoaded', () => {
    const tablesFiche = ['ordres_travail', 'ot_operations', 'ot_pieces', 'ot_temps', 'equipements', 'techniciens',
      'habilitations', 'articles', 'mouvements_stock', 'demandes', 'codes_defaillance'];
    App.ecran({
      id: 'liste-ot', route: /^#\/ot$/,
      get titre() { return I18n.t('ordres.ecran.liste_titre'); },
      menu: { get libelle() { return I18n.t('ordres.menu.libelle'); }, get court() { return I18n.t('ordres.menu.court'); }, icone: 'ordres', ordre: 30 },
      profils: ['technicien', 'responsable'], tables: ['ordres_travail', 'equipements', 'techniciens'],
      afficher: afficherListe,
    });
    // « #/ot/nouveau » avant « #/ot/<id> » : la première route qui correspond gagne ; la route
    // fiche exclut en plus « nouveau » (ARCHITECTURE.md §14.2).
    App.ecran({
      id: 'nouvel-ot', route: /^#\/ot\/nouveau$/, parent: 'liste-ot',
      get titre() { return I18n.t('ordres.ecran.nouveau_titre'); },
      profils: ['responsable'], tables: [],
      afficher: afficherNouveau,
    });
    App.ecran({
      id: 'fiche-ot', route: /^#\/ot\/(?!nouveau$)(?<id>[^/?]+)$/, parent: 'liste-ot',
      get titre() { return I18n.t('ordres.ecran.fiche_titre'); },
      profils: ['technicien', 'responsable'], tables: tablesFiche,
      afficher: afficherFiche,
    });
  });

  return {
    // affichage (ARCHITECTURE.md §10)
    bonDeTravailHtml, imprimerBon,
  };
})());
