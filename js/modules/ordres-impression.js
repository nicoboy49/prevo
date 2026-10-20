'use strict';
// Ordres (7/7) — bon de travail A4 (rempli dans #impression, puis window.print()) et
// enregistrement des écrans du module auprès d'App (ARCHITECTURE.md §8, §10 et §14.2). Dernier
// fichier du module : les fonctions d'affichage des fichiers précédents existent déjà.

Object.assign(Ordres, (() => {

  // Constantes, outils et écrans des fichiers précédents (ordres-regles.js à ordres-pieces.js).
  const { RAPPEL_CONSIGNATION, nomTechnicien } = Ordres;
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
          <div class="bt-entreprise">${entreprise ? entreprise + ' — ' : ''}Prévo</div>
          <h1>Bon de travail</h1>
          <div class="bt-numero">${ot.id} <span class="bt-priorite">${ot.priorite}</span></div>
          <div class="bt-meta"><span>Type : <b>${ot.type}</b></span><span>Statut : <b>${ot.statut}</b></span>
            <span>Prévu le : <b>${UI.dateFr(ot.date_prevue) || '—'}</b></span><span>Technicien : <b>${nomTechnicien(ot.technicien_id) || '—'}</b></span>
            <span>Temps prévu : <b>${ot.temps_prevu_h ? UI.heures(ot.temps_prevu_h) : '—'}</b></span></div>
        </div>
        <div class="bt-qr">${qrBon(equipementDe(ot))}</div>
      </header>
      <div class="bt-colonnes">
        <section class="bt-equipement"><h2>Équipement</h2>
          <dl class="valeurs"><dt>Repère</dt><dd>${equipement.repere || ot.equipement_id}</dd><dt>Désignation</dt><dd>${equipement.designation || ''}</dd>
            <dt>Localisation</dt><dd>${cheminLocalisation(equipement.localisation_id)}</dd><dt>Criticité</dt><dd>${equipement.criticite || ''}</dd>
            <dt>Habilitation</dt><dd>${equipement.habilitation_requise || 'aucune'}</dd></dl>
        </section>
        <section class="bt-travail"><h2>Travail à faire</h2>
          <p class="bt-texte">${ot.titre}</p>
          ${ot.travail_a_faire ? UI.html`<p class="bt-texte">${ot.travail_a_faire}</p>` : ''}
          ${ot.consignes ? UI.html`<p class="bt-texte"><b>Consignes :</b> ${ot.consignes}</p>` : ''}
          ${di ? UI.html`<p><b>Demande :</b> ${di.id} — ${texte(di.symptome).replace(/[.\s]+$/, '')}${di.impact ? ' (impact : ' + di.impact + ')' : ''}</p>` : ''}
        </section>
      </div>
      <section class="bt-consignation"><h2>Consignation</h2>
        <p class="bt-texte">${texte(equipement.consignation) || 'Aucune procédure renseignée : voir le responsable avant d\'intervenir.'}</p>
        <p class="bt-rappel">${RAPPEL_CONSIGNATION}</p>
        <div class="bt-case"><span class="bt-coche"></span>Consignation appliquée par : ______________________</div>
      </section>
      <section class="bt-operations"><h2>Opérations</h2>
        <table class="bt-table"><thead><tr><th class="bt-etroit">N°</th><th>Opération</th><th>Valeur attendue</th><th>Mesure</th><th class="bt-etroit">Fait</th></tr></thead>
          <tbody>${operations.length ? operations.map((op) => UI.html`<tr><td class="bt-etroit">${op.ordre}</td><td>${op.operation}</td><td>${op.valeur_attendue}</td><td class="bt-a-remplir"></td><td class="bt-etroit"><span class="bt-coche"></span></td></tr>`)
            : UI.brut(new Array(3).fill('<tr><td class="bt-etroit"></td><td class="bt-a-remplir"></td><td></td><td></td><td class="bt-etroit"><span class="bt-coche"></span></td></tr>').join(''))}</tbody></table>
      </section>
      <section class="bt-pieces"><h2>Pièces</h2>
        <table class="bt-table"><thead><tr><th>Référence</th><th>Désignation</th><th>Emplacement</th><th class="bt-etroit">Prévu</th><th class="bt-etroit">Utilisé</th></tr></thead>
          <tbody>${pieces.map((p) => {
            const article = Donnees.trouver('articles', p.article_id) || {};
            return UI.html`<tr><td>${article.reference || p.article_id}</td><td>${article.designation || ''}</td><td>${article.emplacement || ''}</td><td class="bt-etroit">${UI.nombreFr(p.quantite_prevue)}</td><td class="bt-a-remplir"></td></tr>`;
          })}${UI.brut('<tr><td class="bt-a-remplir"></td><td></td><td></td><td></td><td></td></tr>')}</tbody></table>
      </section>
      <section class="bt-temps"><h2>Temps passés</h2>
        <table class="bt-table"><thead><tr><th>Date</th><th>Technicien</th><th class="bt-etroit">Heures</th></tr></thead>
          <tbody>${UI.brut(new Array(3).fill('<tr><td class="bt-a-remplir"></td><td></td><td></td></tr>').join(''))}</tbody></table>
      </section>
      <section class="bt-compte-rendu"><h2>Compte rendu</h2>
        <p>Cause : ________ Remède : ________ Arrêt de production : ☐ oui ☐ non — durée : ______ h</p>
        <div class="bt-lignes">${lignesVides(4)}</div>
        <div class="bt-case"><span class="bt-coche"></span>Équipement remis en service en sécurité</div>
      </section>
      <section class="bt-signatures">
        <div class="bt-signature"><b>Technicien</b>Nom, date et signature</div>
        <div class="bt-signature"><b>Production (remise en service)</b>Nom, date et signature</div>
        <div class="bt-signature"><b>Responsable maintenance</b>Nom, date et signature</div>
      </section>
      <footer class="bt-pied"><span>Prévo — bon imprimé le ${UI.dateHeureFr(maintenant).replace(' ', ' à ')}</span><span>${ot.id}</span></footer>
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
      id: 'liste-ot', route: /^#\/ot$/, titre: 'Ordres de travail',
      menu: { libelle: 'Ordres de travail', court: 'Ordres', icone: 'ordres', ordre: 30 },
      profils: ['technicien', 'responsable'], tables: ['ordres_travail', 'equipements', 'techniciens'],
      afficher: afficherListe,
    });
    // « #/ot/nouveau » avant « #/ot/<id> » : la première route qui correspond gagne ; la route
    // fiche exclut en plus « nouveau » (ARCHITECTURE.md §14.2).
    App.ecran({
      id: 'nouvel-ot', route: /^#\/ot\/nouveau$/, titre: 'Nouvel OT', parent: 'liste-ot',
      profils: ['responsable'], tables: [],
      afficher: afficherNouveau,
    });
    App.ecran({
      id: 'fiche-ot', route: /^#\/ot\/(?!nouveau$)(?<id>[^/?]+)$/, titre: 'Ordre de travail', parent: 'liste-ot',
      profils: ['technicien', 'responsable'], tables: tablesFiche,
      afficher: afficherFiche,
    });
  });

  return {
    // affichage (ARCHITECTURE.md §10)
    bonDeTravailHtml, imprimerBon,
  };
})());
