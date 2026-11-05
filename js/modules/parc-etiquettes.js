'use strict';
// Parc (4/5) — étiquettes QR par lot : sélection d'équipements, planches A4 de 24 ou 8 étiquettes,
// adresse encodée dans les QR (ARCHITECTURE.md §15.6 ; brief §9 E7).
// Complète l'objet Parc. L'écran #/parc/etiquettes est enregistré par parc-fiche.js (dernier
// fichier du module, seul à écouter DOMContentLoaded).
//
// Offert :
//   Parc.FORMATS_ETIQUETTES                      les deux formats de planche (24 ou 8 étiquettes)
//   Parc.equipementsPourEtiquettes({ localisationId, criticite, ids })   équipements à étiqueter
//   Parc.planchesEtiquettes(equipements, format, { haut, gauche })        HTML des planches A4
//   Parc.afficherEtiquettes(conteneur, parametres)                        écran #/parc/etiquettes
//
// Impression : chaque planche est une page A4 dessinée en millimètres (positions absolues). La
// feuille css/modules/etiquettes.css lui donne une page nommée « etiquettes » sans marge
// (@page etiquettes { size: A4; margin: 0 }) : le bon de travail garde ses marges de 12 mm.

Object.assign(Parc, (() => {

  // Outils de parc-regles.js.
  const { estActif, comparerTextes, parRepere, identifiantsDescendants, badgeCriticite } = Parc.interne;
  const { cheminLocalisation } = Parc;

  /** Les deux formats de planche A4 (dimensions d'une étiquette en mm). */
  const FORMATS_ETIQUETTES = {
    '24': { colonnes: 3, lignes: 8, largeurMm: 70, hauteurMm: 37 },
    '8': { colonnes: 2, lignes: 4, largeurMm: 105, hauteurMm: 74 },
  };
  const FORMAT_DEFAUT = '24';
  const A4 = { largeurMm: 210, hauteurMm: 297 };
  const DECALAGE_MAX_MM = 10;                         // décalage d'impression accepté : -10 à +10 mm
  const CLE_MEMOIRE = 'prevo.etiquettes';            // localStorage : { format, haut, gauche }
  const CLE_ADRESSE_QR = 'adresse_qr';                // parametres.csv (§15.1)
  const TAILLE_QR_PX = 160;                           // taille du dessin ; l'impression la fixe en mm (CSS)

  // ===========================================================================================
  // 9. Étiquettes QR par lot : sélection et planches (règles)
  // ===========================================================================================

  /** Vrai si l'équipement mérite une étiquette : actif et pas au rebut. */
  function estEtiquetable(equipement) {
    return estActif(equipement) && equipement.statut !== 'rebut';
  }

  /**
   * Équipements à étiqueter, triés par repère : actifs hors rebut, de la localisation ET de ses
   * sous-localisations (si `localisationId`), de la criticité demandée (si `criticite`), parmi les
   * identifiants donnés (si `ids` est une liste non vide).
   */
  function equipementsPourEtiquettes(criteres) {
    const { localisationId = '', criticite = '', ids = [] } = criteres || {};
    let zone = null;
    if (localisationId) {
      zone = identifiantsDescendants('localisations', localisationId);
      zone.add(localisationId);
    }
    const choisis = Array.isArray(ids) && ids.length ? new Set(ids) : null;
    return Donnees.lignes('equipements')
      .filter((e) => estEtiquetable(e)
        && (!zone || zone.has(e.localisation_id))
        && (!criticite || e.criticite === criticite)
        && (!choisis || choisis.has(e.id)))
      .sort((a, b) => parRepere(a, b) || comparerTextes(a.id, b.id));
  }

  // Millimètres écrits pour le CSS : point décimal, deux décimales au plus (« 12.5 »).
  function mm(valeur) {
    return String(Math.round(valeur * 100) / 100);
  }

  // Décalage lu sans surprise : un nombre entre -10 et +10 mm, 0 sinon.
  function decalageMm(valeur) {
    const nombre = Donnees.nombre(valeur);
    if (nombre === null) return 0;
    return Math.min(DECALAGE_MAX_MM, Math.max(-DECALAGE_MAX_MM, nombre));
  }

  // QR d'une étiquette : l'adresse de la fiche (App.urlFicheEquipement). Repère seul si impossible.
  function qrEtiquette(equipement) {
    try {
      return UI.qrSvg(App.urlFicheEquipement(equipement.id), TAILLE_QR_PX);
    } catch (erreur) {
      console.warn('Prévo : QR de l\'étiquette ' + equipement.id + ' impossible (' + (erreur && erreur.message) + ').', erreur);
      return UI.html`<span class="etiquette-sans-qr">${I18n.t('parc.qr_etiquette.qr_indisponible')}</span>`;
    }
  }

  // Une étiquette, placée en mm dans sa planche : QR, repère en gros, désignation, entreprise.
  function etiquetteHtml(equipement, position, gabarit, entreprise) {
    const boite = { left: mm(position.gaucheMm), top: mm(position.hautMm), width: mm(gabarit.largeurMm), height: mm(gabarit.hauteurMm) };
    const style = Object.keys(boite).map((propriete) => propriete + ': ' + boite[propriete] + 'mm').join('; ');
    return UI.html`<div class="etiquette" data-equipement="${equipement.id}" style="${style}">
      <div class="etiquette-qr">${qrEtiquette(equipement)}</div>
      <div class="etiquette-texte">
        <b class="etiquette-repere">${equipement.repere || equipement.id}</b>
        <span class="etiquette-designation">${equipement.designation}</span>
        ${entreprise ? UI.html`<span class="etiquette-entreprise">${entreprise}</span>` : ''}
      </div>
    </div>`;
  }

  /**
   * HTML des planches A4 (une <section class="planche-etiquettes"> par page) : étiquettes rangées
   * de gauche à droite puis de haut en bas, la grille centrée sur la feuille, puis décalée de
   * `decalage.haut` et `decalage.gauche` mm (réglage de l'imprimante). Format : '24' ou '8'.
   */
  function planchesEtiquettes(equipements, format, decalage) {
    const cle = String(format || FORMAT_DEFAUT);
    const gabarit = FORMATS_ETIQUETTES[cle];
    if (!gabarit) throw new Error(I18n.t('parc.planches_etiquettes.format_etiquettes_inconnu_24', { format }));
    const haut = decalageMm(decalage && decalage.haut);
    const gauche = decalageMm(decalage && decalage.gauche);
    const parPlanche = gabarit.colonnes * gabarit.lignes;
    const margeHaut = (A4.hauteurMm - gabarit.lignes * gabarit.hauteurMm) / 2;
    const margeGauche = (A4.largeurMm - gabarit.colonnes * gabarit.largeurMm) / 2;
    const entreprise = Donnees.parametre('entreprise_nom', '');
    const liste = equipements || [];
    const total = Math.ceil(liste.length / parPlanche);
    const planches = [];
    for (let numero = 0; numero < total; numero += 1) {
      const etiquettes = liste.slice(numero * parPlanche, (numero + 1) * parPlanche).map((equipement, rang) => {
        const position = {
          gaucheMm: margeGauche + gauche + (rang % gabarit.colonnes) * gabarit.largeurMm,
          hautMm: margeHaut + haut + Math.floor(rang / gabarit.colonnes) * gabarit.hauteurMm,
        };
        return etiquetteHtml(equipement, position, gabarit, entreprise);
      });
      planches.push(UI.html`<section class="planche-etiquettes format-${cle}" aria-label="${I18n.t('parc.planches_etiquettes.planche_v1_total', { numero: numero + 1, total })}">${etiquettes}</section>`);
    }
    return UI.html`${planches}`;
  }

  // ===========================================================================================
  // 10. Écran #/parc/etiquettes : sélection, adresse, format, décalage, aperçu, impression
  // ===========================================================================================

  // Réglages du poste (localStorage) : format et décalage. Valeur illisible → réglages par défaut.
  function lireReglages() {
    let lus = {};
    try {
      lus = JSON.parse(localStorage.getItem(CLE_MEMOIRE) || '{}') || {};
    } catch (erreur) {
      lus = {};
    }
    return {
      format: FORMATS_ETIQUETTES[lus.format] ? String(lus.format) : FORMAT_DEFAUT,
      haut: decalageMm(lus.haut),
      gauche: decalageMm(lus.gauche),
    };
  }

  function memoriserReglages(reglages) {
    try {
      localStorage.setItem(CLE_MEMOIRE, JSON.stringify({ format: reglages.format, haut: reglages.haut, gauche: reglages.gauche }));
    } catch (erreur) {
      console.warn('Prévo : réglages des étiquettes non mémorisés (' + (erreur && erreur.message) + ').', erreur);
    }
  }

  // Sélection de l'écran, gardée d'un affichage à l'autre tant que l'adresse ne change pas (un
  // changement sur un autre poste réaffiche l'écran sans perdre les cases décochées).
  let selection = null;

  function selectionPour(requete) {
    const texte = requete.toString();
    if (!selection || selection.requete !== texte) {
      selection = {
        requete: texte,
        localisationId: requete.get('localisation') || '',
        criticite: requete.get('criticite') || '',
        ids: (requete.get('ids') || '').split(',').map((id) => id.trim()).filter(Boolean),
        decoches: new Set(),
      };
    }
    return selection;
  }

  // Début de l'adresse mise dans les QR (« http://192.168.1.10:8080/ ») : App.urlFicheEquipement
  // la calcule (adresse_qr, sinon première adresse détectée) ; on retire la fin propre à la fiche.
  function adresseDeBase() {
    const exemple = App.urlFicheEquipement('X');
    const fin = '#/equipement/X';
    return exemple.endsWith(fin) ? exemple.slice(0, -fin.length) : exemple;
  }

  function memeAdresse(a, b) {
    return String(a || '').replace(/\/+$/, '') === String(b || '').replace(/\/+$/, '');
  }

  // Adresses proposées : celles du PC, plus l'adresse choisie avant si elle n'y est plus.
  function adressesProposees() {
    const adresses = App.adressesReseau();
    const choisie = String(Donnees.parametre(CLE_ADRESSE_QR, '') || '').trim();
    if (/^https?:\/\/\S+$/i.test(choisie) && !adresses.some((a) => memeAdresse(a, choisie))) adresses.push(choisie);
    return adresses;
  }

  async function enregistrerAdresse(adresse) {
    await Donnees.modifier('parametres', (lignes) => {
      if (!/^https?:\/\/\S+$/i.test(adresse)) {
        throw new Donnees.ErreurValidation(I18n.t('parc.enregistrer_adresse.adresse_invalide_doit_commencer', { adresse }));
      }
      const ligne = lignes.find((l) => l.cle === CLE_ADRESSE_QR);
      if (ligne) ligne.valeur = adresse; else lignes.push({ cle: CLE_ADRESSE_QR, valeur: adresse });
    }, { action: 'adresse des QR des étiquettes : ' + adresse });
  }

  // Carte « Adresse des QR » : en mode serveur, l'adresse encodée, l'avertissement et le choix ;
  // en dossier et en démo, ce que contient le QR.
  function carteAdresse() {
    if (App.mode !== 'serveur') {
      return UI.html`<section class="carte etiquettes-adresse" aria-labelledby="etiquettes-titre-adresse">
        <h2 id="etiquettes-titre-adresse">${UI.icone('qr')} ${I18n.t('parc.carte_adresse.contenu_qr')}</h2>
        <p>${I18n.html('parc.carte_adresse.qr_contient_gmao_id')}</p>
      </section>`;
    }
    const base = adresseDeBase();
    const adresses = adressesProposees();
    const choix = adresses.length > 1 ? UI.html`<div class="form-ligne etiquettes-choix-adresse">
        <label for="etiquettes-adresse">${I18n.t('parc.carte_adresse.adresse_pc_mettre_qr')}
          <select id="etiquettes-adresse">${adresses.map((adresse) => UI.html`<option value="${adresse}" ${memeAdresse(adresse, base) ? UI.brut('selected') : ''}>${adresse}</option>`)}</select>
        </label>
        <button type="button" class="btn btn-secondaire" id="etiquettes-adresse-enregistrer">${UI.icone('valider')}${I18n.t('parc.carte_adresse.utiliser_adresse')}</button>
      </div>` : '';
    return UI.html`<section class="carte etiquettes-adresse" aria-labelledby="etiquettes-titre-adresse">
      <h2 id="etiquettes-titre-adresse">${UI.icone('qr')} ${I18n.t('parc.carte_adresse.adresse_encodee_qr')}</h2>
      <p>${I18n.html('parc.carte_adresse.chaque_qr_ouvre_fiche', { base })}</p>
      <div class="encadre attention etiquettes-avertissement">${UI.icone('alerte')}
        ${I18n.t('parc.carte_adresse.si_adresse_ip_port')}</div>
      ${adresses.length ? '' : UI.html`<p class="note">${I18n.t('parc.carte_adresse.aucune_adresse_reseau_ete')}</p>`}
      ${App.cePcSeulement && App.cePcSeulement() ? UI.html`<div class="encadre info" id="etiquettes-ce-pc">${UI.icone('alerte')}
        ${I18n.t('parc.carte_adresse.prevo_joignable_pc_instant')}</div>` : ''}
      ${choix}
    </section>`;
  }

  // Options « Tout le parc », puis chaque localisation par son chemin (« Site › Atelier › Ligne »).
  function optionsLocalisations(valeur) {
    const localisations = Donnees.lignes('localisations')
      .map((l) => ({ id: l.id, chemin: cheminLocalisation(l.id) }))
      .sort((a, b) => comparerTextes(a.chemin, b.chemin));
    return UI.html`<option value="">${I18n.t('parc.options_localisations.tout_parc')}</option>${localisations.map((l) => UI.html`<option value="${l.id}" ${l.id === valeur ? UI.brut('selected') : ''}>${l.chemin}</option>`)}`;
  }

  function optionsCriticite(valeur) {
    const choix = [['', I18n.t('parc.options_criticite.toutes')], ['A', I18n.t('parc.options_criticite.tres_critique')], ['B', I18n.t('parc.options_criticite.b_critique')], ['C', I18n.t('parc.options_criticite.peu_critique')]];
    return UI.html`${choix.map(([code, libelle]) => UI.html`<option value="${code}" ${code === valeur ? UI.brut('selected') : ''}>${libelle}</option>`)}`;
  }

  function optionsFormat(valeur) {
    return UI.html`${Object.keys(FORMATS_ETIQUETTES).sort((a, b) => Number(b) - Number(a)).map((cle) => {
      const g = FORMATS_ETIQUETTES[cle];
      return UI.html`<option value="${cle}" ${cle === valeur ? UI.brut('selected') : ''}>${I18n.t('parc.options_format.planche_mm', { cle, colonnes: g.colonnes, lignes: g.lignes, largeurMm: g.largeurMm, hauteurMm: g.hauteurMm })}</option>`;
    })}`;
  }

  // Liste à cocher des équipements retenus par les filtres.
  function listeEquipementsHtml(equipements, decoches) {
    if (!equipements.length) {
      return UI.html`<p class="muted etiquettes-vide">${I18n.t('parc.liste_equipements.aucun_equipement_actif_correspond')}</p>`;
    }
    return UI.html`${equipements.map((e) => UI.html`<label class="case etiquettes-case">
      <input type="checkbox" value="${e.id}" ${decoches.has(e.id) ? '' : UI.brut('checked')}>
      <span class="etiquettes-case-texte"><b>${e.repere || e.id}</b> <span>${e.designation}</span>
        <small>${e.localisation_id ? cheminLocalisation(e.localisation_id) : I18n.t('parc.liste_equipements.sans_localisation')}</small></span>
      ${badgeCriticite(e.criticite)}
    </label>`)}`;
  }

  function afficherEtiquettes(conteneur, parametres) {
    const etat = selectionPour(parametres.requete);
    const reglages = lireReglages();
    // data-hors-saisie : ces réglages ne sont pas une saisie à protéger (l'état est gardé ici).
    UI.remplir(conteneur, UI.html`
      <div class="parc etiquettes" data-hors-saisie>
        <div class="entete-page">
          <div>
            <div class="fil"><a href="#/parc">${I18n.t('parc.etiquettes.parc')}</a></div>
            <h1>${I18n.t('parc.etiquettes.etiquettes_qr')}</h1>
            <p>${I18n.t('parc.etiquettes.choisissez_equipements_format_planche')}</p>
          </div>
        </div>
        ${carteAdresse()}
        <div class="grille etiquettes-grille">
          <section class="carte c5 etiquettes-selection" aria-labelledby="etiquettes-titre-selection">
            <h2 id="etiquettes-titre-selection">${I18n.t('parc.etiquettes.equipements')}</h2>
            <div class="form-ligne">
              <label for="etiquettes-localisation">${I18n.t('parc.etiquettes.localisation_sous_localisations')}
                <select id="etiquettes-localisation">${optionsLocalisations(etat.localisationId)}</select></label>
              <label for="etiquettes-criticite">${I18n.t('commun.champ.criticite')}
                <select id="etiquettes-criticite">${optionsCriticite(etat.criticite)}</select></label>
            </div>
            ${etat.ids.length ? UI.html`<p class="note">${I18n.html('parc.etiquettes.selection_limitee_lien', { n: etat.ids.length })}</p>` : ''}
            <div class="actions">
              <button type="button" class="btn btn-fantome" id="etiquettes-tout-cocher">${I18n.t('parc.etiquettes.tout_cocher')}</button>
              <button type="button" class="btn btn-fantome" id="etiquettes-tout-decocher">${I18n.t('parc.etiquettes.tout_decocher')}</button>
            </div>
            <fieldset class="etiquettes-liste" id="etiquettes-liste">
              <legend class="visuellement-cache">${I18n.t('parc.etiquettes.equipements_etiqueter')}</legend>
            </fieldset>
          </section>
          <div class="c7 etiquettes-droite">
            <section class="carte etiquettes-reglages" aria-labelledby="etiquettes-titre-format">
              <h2 id="etiquettes-titre-format">${I18n.t('parc.etiquettes.format_impression')}</h2>
              <div class="form-ligne">
                <label for="etiquettes-format">${I18n.t('parc.etiquettes.planche_4')}
                  <select id="etiquettes-format">${optionsFormat(reglages.format)}</select></label>
              </div>
              <div class="form-ligne etiquettes-decalages">
                <label for="etiquettes-decalage-haut">${I18n.t('parc.etiquettes.decalage_vers_bas_mm')}
                  <input type="number" id="etiquettes-decalage-haut" min="-${DECALAGE_MAX_MM}" max="${DECALAGE_MAX_MM}" step="0.5" inputmode="decimal" value="${reglages.haut}"></label>
                <label for="etiquettes-decalage-gauche">${I18n.t('parc.etiquettes.decalage_vers_droite_mm')}
                  <input type="number" id="etiquettes-decalage-gauche" min="-${DECALAGE_MAX_MM}" max="${DECALAGE_MAX_MM}" step="0.5" inputmode="decimal" value="${reglages.gauche}"></label>
              </div>
              <p class="aide">${I18n.t('parc.etiquettes.si_impression_tombe_cote')}</p>
              <p class="etiquettes-resume" id="etiquettes-resume" role="status" aria-live="polite"></p>
              <div class="actions">
                <button type="button" class="btn btn-primaire" id="etiquettes-imprimer">${UI.icone('imprimer')}${I18n.t('commun.bouton.imprimer')}</button>
              </div>
            </section>
            <section class="carte etiquettes-apercu-carte" aria-labelledby="etiquettes-titre-apercu">
              <h2 id="etiquettes-titre-apercu">${I18n.t('parc.etiquettes.apercu')}</h2>
              <div class="etiquettes-apercu" id="etiquettes-apercu"></div>
            </section>
          </div>
        </div>
      </div>`);
    brancherEcran(conteneur, etat, reglages);
  }

  // Événements de l'écran : filtres, cases, format, décalage, adresse, impression.
  function brancherEcran(conteneur, etat, reglages) {
    const zoneListe = UI.$('#etiquettes-liste', conteneur);
    const zoneApercu = UI.$('#etiquettes-apercu', conteneur);
    const resume = UI.$('#etiquettes-resume', conteneur);
    const boutonImprimer = UI.$('#etiquettes-imprimer', conteneur);
    let retenus = [];                                  // équipements des filtres (cochés ou non)

    const equipementsCoches = () => retenus.filter((e) => !etat.decoches.has(e.id));

    function dessinerApercu() {
      const choisis = equipementsCoches();
      const gabarit = FORMATS_ETIQUETTES[reglages.format];
      const planches = Math.ceil(choisis.length / (gabarit.colonnes * gabarit.lignes));
      resume.textContent = choisis.length
        ? I18n.t('parc.etiquettes.resume_apercu', { etiquettes: I18n.t('parc.etiquettes.n_etiquettes', { n: choisis.length }),
          planches: I18n.t('parc.etiquettes.n_planches', { n: planches }), format: reglages.format })
        : I18n.t('parc.brancher_ecran.aucune_etiquette_cochez_moins');
      boutonImprimer.disabled = choisis.length === 0;
      UI.remplir(zoneApercu, choisis.length
        ? planchesEtiquettes(choisis, reglages.format, reglages)
        : UI.vide(I18n.t('parc.brancher_ecran.rien_imprimer'), I18n.t('parc.brancher_ecran.cochez_equipements_voir_etiquettes'), 'qr'));
    }

    function dessinerListe() {
      retenus = equipementsPourEtiquettes({ localisationId: etat.localisationId, criticite: etat.criticite, ids: etat.ids });
      UI.remplir(zoneListe, UI.html`<legend class="visuellement-cache">${I18n.t('parc.etiquettes.equipements_etiqueter')}</legend>${listeEquipementsHtml(retenus, etat.decoches)}`);
      dessinerApercu();
    }

    UI.$('#etiquettes-localisation', conteneur).addEventListener('change', (evenement) => {
      etat.localisationId = evenement.target.value;
      dessinerListe();
    });
    UI.$('#etiquettes-criticite', conteneur).addEventListener('change', (evenement) => {
      etat.criticite = evenement.target.value;
      dessinerListe();
    });
    zoneListe.addEventListener('change', (evenement) => {
      const caseACocher = evenement.target;
      if (caseACocher.type !== 'checkbox') return;
      if (caseACocher.checked) etat.decoches.delete(caseACocher.value); else etat.decoches.add(caseACocher.value);
      dessinerApercu();
    });
    UI.$('#etiquettes-tout-cocher', conteneur).addEventListener('click', () => {
      retenus.forEach((e) => etat.decoches.delete(e.id));
      dessinerListe();
    });
    UI.$('#etiquettes-tout-decocher', conteneur).addEventListener('click', () => {
      retenus.forEach((e) => etat.decoches.add(e.id));
      dessinerListe();
    });

    UI.$('#etiquettes-format', conteneur).addEventListener('change', (evenement) => {
      reglages.format = FORMATS_ETIQUETTES[evenement.target.value] ? evenement.target.value : FORMAT_DEFAUT;
      memoriserReglages(reglages);
      dessinerApercu();
    });
    [['#etiquettes-decalage-haut', 'haut'], ['#etiquettes-decalage-gauche', 'gauche']].forEach(([selecteur, cle]) => {
      const champ = UI.$(selecteur, conteneur);
      // Pendant la frappe : pris en compte dès que c'est un nombre ; en sortie du champ : valeur
      // ramenée entre -10 et +10 mm et réécrite.
      champ.addEventListener('input', () => {
        if (Donnees.nombre(champ.value) === null && champ.value !== '') return;
        reglages[cle] = decalageMm(champ.value);
        memoriserReglages(reglages);
        dessinerApercu();
      });
      champ.addEventListener('change', () => {
        reglages[cle] = decalageMm(champ.value);
        champ.value = String(reglages[cle]);
        memoriserReglages(reglages);
        dessinerApercu();
      });
    });

    const boutonAdresse = UI.$('#etiquettes-adresse-enregistrer', conteneur);
    if (boutonAdresse) {
      boutonAdresse.addEventListener('click', async () => {
        const adresse = UI.$('#etiquettes-adresse', conteneur).value;
        boutonAdresse.disabled = true;
        try {
          await enregistrerAdresse(adresse);
          UI.toast(I18n.t('parc.brancher_ecran.qr_contiendront_desormais', { adresse }), 'succes');
          await App.reafficher();
        } catch (erreur) {
          App.signalerErreur(erreur, 'adresse des QR');
          boutonAdresse.disabled = false;
        }
      });
    }

    boutonImprimer.addEventListener('click', () => imprimer(equipementsCoches(), reglages));
    dessinerListe();
  }

  /** Remplit #impression avec les planches puis lance l'impression ; vidé après impression. */
  function imprimer(equipements, reglages) {
    const zone = document.getElementById('impression');
    if (!zone || !equipements.length) return;
    UI.remplir(zone, planchesEtiquettes(equipements, reglages.format, reglages));
    window.addEventListener('afterprint', () => { zone.textContent = ''; }, { once: true });
    window.print();
  }

  return {
    FORMATS_ETIQUETTES,
    equipementsPourEtiquettes,
    planchesEtiquettes,
    afficherEtiquettes,
  };
})());
