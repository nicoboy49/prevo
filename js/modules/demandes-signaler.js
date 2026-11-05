'use strict';
// Demandes (3/5) — écran « Signaler un problème » (#/di/nouvelle, ?equipement=…, ?ot=…) : cinq
// questions pensées téléphone d'abord (équipement, symptôme, impact, précisions, photo), puis
// l'écran de confirmation avec le numéro de la demande (ARCHITECTURE.md §8, §14.2 et §14.6 ;
// brief §9 E2). Lot 2 : le symptôme choisi parmi les suggestions donne son code symptôme ; avec
// ?ot=OT-…, la demande est liée à l'OT préventif pendant lequel l'anomalie a été constatée.
// Lot 4 (§17.5) : « Proposer avec l'IA » reformule le symptôme et propose l'impact (objet Ia).
// Complète l'objet Demandes.

Object.assign(Demandes, (() => {

  // Constantes, outils, règles et écritures des fichiers précédents (demandes-regles.js, demandes-ecritures.js).
  const { prioriteCalculee, libelleEquipement, codeSymptome, creer } = Demandes;
  const { texte, nomDuProfil, prioriteDeLaDemande, nomPhoto, codesSymptome, estOtPreventif } = Demandes.interne;

  // ===========================================================================================
  // 5. Écran « Signaler un problème » (#/di/nouvelle)
  // ===========================================================================================

  /** Lien vers un OT (texte simple pour le demandeur, qui n'a pas accès aux écrans des OT). */
  function lienOt(otId) {
    return App.estDemandeur() ? UI.html`${otId}` : UI.html`<a href="#/ot/${encodeURIComponent(otId)}">${otId}</a>`;
  }

  function afficherNouvelle(conteneur, parametres) {
    const requete = parametres.requete || new URLSearchParams();
    // ?ot=OT-… : OT préventif d'origine (bouton « Signaler une anomalie » d'un OT préventif).
    const otDemande = texte(requete.get('ot'));
    const otOrigine = otDemande ? Donnees.trouver('ordres_travail', otDemande) : null;
    const origineValable = estOtPreventif(otOrigine);
    // Équipement : ?equipement=…, sinon celui de l'OT d'origine.
    const equipementDemande = texte(requete.get('equipement')) || (origineValable ? texte(otOrigine.equipement_id) : '');
    const libellesSymptomes = codesSymptome().map((entree) => entree.libelle);
    const idSymptome = UI.identifiantUnique('di-symptome');
    const idDescription = UI.identifiantUnique('di-description');
    const idListe = UI.identifiantUnique('di-suggestions');
    const idPhoto = UI.identifiantUnique('di-photo');

    UI.remplir(conteneur, UI.html`
      <div class="di-nouvelle">
        <div class="entete-page"><div>
          <h1>${I18n.t('demandes.nouvelle.signaler_probleme')}</h1>
          <p>${I18n.t('demandes.nouvelle.cinq_questions_minute_responsable')}</p>
        </div></div>
        <div class="di-origine"></div>
        <div class="di-alerte-equipement"></div>
        <form class="form-colonne di-formulaire" novalidate>
          <section class="carte di-etape">
            <div class="champ" data-champ="equipement_id">
              <span class="libelle">${I18n.t('demandes.nouvelle.1_quel_equipement')} <span class="requis" aria-hidden="true">*</span></span>
              <div class="di-selecteur"></div>
              <p class="erreur-champ" hidden></p>
            </div>
          </section>

          <section class="carte di-etape">
            <div class="champ" data-champ="symptome">
              <label class="libelle" for="${idSymptome}">${I18n.t('demandes.nouvelle.2_constatez')} <span class="requis" aria-hidden="true">*</span></label>
              <input type="text" id="${idSymptome}" name="symptome" list="${idListe}" maxlength="200" required
                aria-required="true" autocomplete="off" enterkeyhint="next"
                placeholder="${I18n.t('demandes.nouvelle.ex_fuite_huile_sous')}">
              <datalist id="${idListe}">${libellesSymptomes.map((libelle) => UI.html`<option value="${libelle}"></option>`)}</datalist>
              ${libellesSymptomes.length ? UI.html`<div class="di-suggestions" role="group" aria-label="${I18n.t('demandes.nouvelle.suggestions_symptomes')}">
                ${libellesSymptomes.map((libelle) => UI.html`<button type="button" class="di-puce" data-symptome="${libelle}" aria-pressed="false">${libelle}</button>`)}
              </div>` : ''}
              <p class="erreur-champ" hidden></p>
            </div>
          </section>

          <section class="carte di-etape">
            <div class="champ" data-champ="impact">
              <span class="libelle" id="${idSymptome}-impact">${I18n.t('demandes.nouvelle.3_quel_impact')} <span class="requis" aria-hidden="true">*</span></span>
              <fieldset class="tuiles di-impacts" aria-labelledby="${idSymptome}-impact">
                ${Demandes.impacts().map((entree) => UI.html`
                  <label class="tuile${entree.valeur === 'sécurité' ? ' ' + I18n.t('demandes.nouvelle.securite') : ''}">
                    <input type="radio" name="impact" value="${entree.valeur}">
                    <span>${entree.libelle}<small>${entree.explication}</small></span>
                  </label>`)}
              </fieldset>
              <div class="di-zone-securite"></div>
              <p class="erreur-champ" hidden></p>
              <p class="di-priorite" aria-live="polite"></p>
            </div>
          </section>

          <section class="carte di-etape">
            <div class="champ" data-champ="description">
              <label class="libelle" for="${idDescription}">${I18n.html('demandes.nouvelle.4_precisions_facultatif')}</label>
              <textarea id="${idDescription}" name="description" rows="4" data-dictee
                placeholder="${I18n.t('demandes.nouvelle.depuis_quand_bruit_odeur')}"></textarea>
            </div>
            <div class="actions di-ia sans-impression" hidden></div>
          </section>

          <section class="carte di-etape">
            <div class="champ" data-champ="photo">
              <span class="libelle">${I18n.html('demandes.nouvelle.5_photo_facultatif')}</span>
              <label class="btn btn-secondaire btn-gros di-bouton-photo" for="${idPhoto}">
                ${UI.icone('photo')}<span class="di-texte-photo">${I18n.html('demandes.nouvelle.prendre_photo_choisir_galerie')}</span>
              </label>
              <input type="file" id="${idPhoto}" class="di-fichier-photo" accept="image/*" capture="environment">
              <div class="di-apercu" hidden>
                <img class="di-apercu-image" alt="${I18n.t('demandes.nouvelle.photo_jointe_demande')}">
                <button type="button" class="btn btn-fantome di-retirer-photo">${UI.icone('fermer')}${I18n.t('demandes.nouvelle.retirer_photo')}</button>
              </div>
              <p class="aide di-etat-photo" aria-live="polite"></p>
            </div>
          </section>

          <p class="di-demandeur">${I18n.html('demandes.nouvelle.demande_envoyee_nom', { nomDuProfil: nomDuProfil() })}</p>
          <button type="submit" class="btn btn-primaire btn-gros di-envoyer">
            ${UI.icone('valider')}<span>${I18n.t('demandes.nouvelle.envoyer_demande')}</span>
          </button>
        </form>
      </div>`);

    const formulaire = UI.$('.di-formulaire', conteneur);
    const champSymptome = UI.$('input[name=symptome]', formulaire);
    const zoneSecurite = UI.$('.di-zone-securite', formulaire);
    const zonePriorite = UI.$('.di-priorite', formulaire);
    const champPhoto = UI.$('.di-fichier-photo', formulaire);
    const apercu = UI.$('.di-apercu', formulaire);
    const imageApercu = UI.$('.di-apercu-image', formulaire);
    const etatPhoto = UI.$('.di-etat-photo', formulaire);
    const boutonEnvoyer = UI.$('.di-envoyer', formulaire);

    // État de la photo : Blob réduit, préparation en cours, nom une fois envoyée (pas de double envoi).
    const photo = { blob: null, preparation: null, nomEnvoye: '', adresseApercu: '' };

    // --- 1. équipement --------------------------------------------------------------------
    const selecteur = UI.selecteurEquipement(UI.$('.di-selecteur', formulaire), {
      equipements: Donnees.lignes('equipements'),
      localisations: Donnees.lignes('localisations'),
      valeur: equipementDemande,
      nom: 'equipement_id',
      surChoix: () => {
        App.marquerSaisie(true);
        effacerErreur('equipement_id');
        mettreAJourPriorite();
        Wiki.poserRechercheDemande(champSymptome, selecteur.valeur());   // « Déjà vu sur cette machine ? » (§20.7)
      },
    });
    Wiki.poserRechercheDemande(champSymptome, selecteur.valeur());
    if (equipementDemande && !selecteur.valeur()) {
      UI.$('.di-alerte-equipement', conteneur).appendChild(UI.bandeau('attention',
        UI.html`${I18n.html('demandes.nouvelle.equipement_inconnu_plus_actif', { equipementDemande })}`));
    }

    // --- OT préventif d'origine (?ot=) : bandeau, ou avertissement si l'OT ne convient pas -----
    // Un OT verrouillé (Clôturé administrativement, Annulé : RG3) reste lié à la demande, mais il ne
    // sera pas marqué : le bandeau le dit avant l'envoi.
    if (otDemande) {
      const suite = origineValable && Ordres.estVerrouille(otOrigine)
        ? UI.html`${I18n.t('demandes.nouvelle.demande_sera_liee_ot', { otDemande, otOrigineStatut: otOrigine.statut })}`
        : UI.html`${I18n.t('demandes.nouvelle.demande_sera_liee_ot_2')}`;
      UI.$('.di-origine', conteneur).appendChild(origineValable
        ? UI.bandeau('info', UI.html`<b>${I18n.t('demandes.nouvelle.anomalie_constatee_pendant_ot')} ${lienOt(otDemande)}</b><br>${suite}`)
        : UI.bandeau('attention', UI.html`${I18n.html('demandes.nouvelle.ordre_travail_introuvable_pas', { otDemande })}`));
    }

    // --- 2. symptôme : les puces remplissent le champ ; le code suit le texte -----------------
    // Le code symptôme est celui dont le libellé est exactement le texte (casse et espaces
    // ignorés) : choisir une puce le donne, retoucher le texte l'efface s'il ne correspond plus.
    // La puce du code retenu est marquée (aria-pressed) : on voit qu'un code est enregistré.
    function marquerSuggestion() {
      const code = codeSymptome(champSymptome.value);
      UI.$$('.di-puce', formulaire).forEach((puce) => {
        puce.setAttribute('aria-pressed', String(code !== '' && codeSymptome(puce.dataset.symptome) === code));
      });
    }
    formulaire.addEventListener('click', (evenement) => {
      const puce = evenement.target.closest('.di-puce');
      if (!puce) return;
      champSymptome.value = puce.dataset.symptome;
      champSymptome.dispatchEvent(new Event('input', { bubbles: true }));
      effacerErreur('symptome');
    });
    champSymptome.addEventListener('input', () => {
      if (champSymptome.value.trim()) effacerErreur('symptome');
      marquerSuggestion();
    });

    // --- 3. impact : bandeau rouge si « sécurité », priorité calculée -------------------------
    function impactChoisi() {
      const coche = UI.$('input[name=impact]:checked', formulaire);
      return coche ? coche.value : '';
    }

    function mettreAJourPriorite() {
      const impact = impactChoisi();
      zoneSecurite.textContent = '';
      if (impact === 'sécurité') {
        zoneSecurite.appendChild(UI.bandeau('securite',
          UI.html`<b>${I18n.t('demandes.nouvelle.danger_mettez_zone_securite')}</b>`));
      }
      const equipement = Donnees.trouver('equipements', selecteur.valeur());
      if (!impact) {
        UI.remplir(zonePriorite, UI.html`<span class="aide">${I18n.t('demandes.nouvelle.priorite_affiche_quand_impact')}</span>`);
        return;
      }
      const priorite = prioriteCalculee(equipement ? equipement.criticite : '', impact);
      UI.remplir(zonePriorite, UI.html`${I18n.t('demandes.nouvelle.priorite_calculee')} ${UI.badgePriorite(priorite)}
        <span class="aide">${equipement ? I18n.t('demandes.nouvelle.criticite_impact', { criticite: (equipement.criticite || 'B'), impact })
          : I18n.t('demandes.nouvelle.choisissez_equipement_affiner')}</span>`);
    }
    UI.$$('input[name=impact]', formulaire).forEach((bouton) => bouton.addEventListener('change', () => {
      effacerErreur('impact');
      mettreAJourPriorite();
    }));
    mettreAJourPriorite();

    // --- 5. photo -------------------------------------------------------------------------
    function libererApercu() {
      if (photo.adresseApercu) URL.revokeObjectURL(photo.adresseApercu);
      photo.adresseApercu = '';
    }

    function retirerPhoto() {
      libererApercu();
      photo.blob = null;
      photo.preparation = null;
      photo.nomEnvoye = '';
      champPhoto.value = '';
      imageApercu.removeAttribute('src');
      apercu.hidden = true;
      etatPhoto.textContent = '';
      UI.remplir(UI.$('.di-texte-photo', formulaire), UI.html`${I18n.html('demandes.nouvelle.prendre_photo_choisir_galerie')}`);
    }

    champPhoto.addEventListener('change', () => {
      const fichier = champPhoto.files && champPhoto.files[0];
      if (!fichier) return;
      libererApercu();
      photo.blob = null;
      photo.nomEnvoye = '';
      etatPhoto.textContent = I18n.t('demandes.nouvelle.preparation_photo');
      const preparation = UI.redimensionnerPhoto(fichier, 1280).then((blob) => {
        if (photo.preparation !== preparation) return blob;    // une autre photo a été choisie entre-temps
        photo.blob = blob;
        photo.adresseApercu = URL.createObjectURL(blob);
        imageApercu.src = photo.adresseApercu;
        apercu.hidden = false;
        etatPhoto.textContent = I18n.t('demandes.nouvelle.photo_prete_ko_sera', { max: Math.max(1, Math.round(blob.size / 1024)) });
        UI.remplir(UI.$('.di-texte-photo', formulaire), UI.html`${I18n.html('demandes.nouvelle.changer_photo_photo_actuelle')}`);
        return blob;
      }).catch((erreur) => {
        if (photo.preparation === preparation) retirerPhoto();
        UI.toast(I18n.t('demandes.nouvelle.photo_peut_pas_etre'), 'attention');
        console.warn('Prévo (demandes) : photo illisible (' + (erreur && erreur.message) + ').', erreur);
        return null;
      });
      photo.preparation = preparation;
    });
    UI.$('.di-retirer-photo', formulaire).addEventListener('click', retirerPhoto);

    // --- assistant IA (lot 4) : « Proposer avec l'IA » près des précisions ---------------------
    const tracerIa = brancherIa(formulaire, selecteur);

    // --- erreurs de champ -----------------------------------------------------------------
    function blocChamp(nom) {
      return UI.$$('.champ', formulaire).find((bloc) => bloc.dataset.champ === nom);
    }

    function afficherErreur(nom, message) {
      const bloc = blocChamp(nom);
      const zone = UI.$(':scope > .erreur-champ', bloc);
      bloc.classList.add('en-erreur');
      zone.textContent = message;
      zone.hidden = false;
    }

    function effacerErreur(nom) {
      const bloc = blocChamp(nom);
      const zone = bloc && UI.$(':scope > .erreur-champ', bloc);
      if (!zone) return;
      bloc.classList.remove('en-erreur');
      zone.hidden = true;
      zone.textContent = '';
    }

    function verifier() {
      const manques = [];
      if (!selecteur.valeur()) manques.push(['equipement_id', I18n.t('demandes.nouvelle.choisissez_equipement_concerne')]);
      if (!champSymptome.value.trim()) manques.push(['symptome', I18n.t('demandes.nouvelle.decrivez_quelques_mots_constatez')]);
      if (!impactChoisi()) manques.push(['impact', I18n.t('demandes.nouvelle.choisissez_impact')]);
      manques.forEach(([nom, message]) => afficherErreur(nom, message));
      if (manques.length) {
        const premier = blocChamp(manques[0][0]);
        premier.scrollIntoView({ block: 'center' });
        const cible = UI.$('input:not([type=hidden]):not([type=radio]), input[type=radio]', premier);
        if (cible) cible.focus({ preventScroll: true });
      }
      return manques.length === 0;
    }

    // --- envoi : photo d'abord, puis la demande ---------------------------------------------
    formulaire.addEventListener('submit', async (evenement) => {
      evenement.preventDefault();
      if (boutonEnvoyer.disabled || !verifier()) return;
      boutonEnvoyer.disabled = true;
      boutonEnvoyer.setAttribute('aria-busy', 'true');
      const texteBouton = UI.$('span', boutonEnvoyer);
      texteBouton.textContent = I18n.t('demandes.nouvelle.envoi_cours');
      try {
        // demandes.csv abîmé (T201) : refus AVANT d'écrire la photo (la demande serait refusée juste après) : rien
        // n'est écrit ; la saisie et la photo choisie restent dans le formulaire.
        if (Donnees.tablesAbimees().includes('demandes')) {
          throw new Donnees.ErreurFichierAbime('demandes', 'demandes.csv');
        }
        if (photo.preparation) await photo.preparation;
        let nomDeLaPhoto = '';
        if (photo.blob) {
          if (!photo.nomEnvoye) photo.nomEnvoye = await App.adaptateur.ecrireDocument(nomPhoto(), photo.blob);
          nomDeLaPhoto = photo.nomEnvoye;
        }
        const impact = impactChoisi();
        const id = await creer({
          equipement_id: selecteur.valeur(),
          symptome: champSymptome.value,
          symptome_code: codeSymptome(champSymptome.value),
          impact,
          description: UI.$('textarea[name=description]', formulaire).value,
          photo: nomDeLaPhoto,
          ot_origine_id: origineValable ? otDemande : '',
        });
        await tracerIa(id, { impact });
        App.marquerSaisie(false);
        libererApercu();
        afficherConfirmation(conteneur, id);
      } catch (erreur) {
        App.signalerErreur(erreur, 'envoi de la demande');
        boutonEnvoyer.disabled = false;
        boutonEnvoyer.removeAttribute('aria-busy');
        texteBouton.textContent = I18n.t('demandes.nouvelle.envoyer_demande');
      }
    });
  }

  // ===========================================================================================
  // 5 bis. Assistant IA du formulaire (lot 4, ARCHITECTURE.md §17.5) : « Proposer avec l'IA »
  // ===========================================================================================

  const zonesIa = new Set();                // { zone, poser } des formulaires affichés
  let ecouteIa = false;

  /**
   * Pose les boutons IA de `zone` maintenant, puis à chaque changement de l'IA : le test du
   * fournisseur, fait à l'ouverture de Prévo, se termine souvent après l'affichage de l'écran, et un
   * fournisseur devenu injoignable retire les boutons. Un seul écouteur ; une zone qui n'est plus
   * affichée (écran quitté ou réaffiché) est oubliée.
   */
  function suivreIa(zone, poser) {
    zonesIa.forEach((entree) => { if (!entree.zone.isConnected) zonesIa.delete(entree); });
    zonesIa.add({ zone, poser });
    poser();
    if (ecouteIa) return;
    ecouteIa = true;
    Ia.evenements.addEventListener('changement', () => zonesIa.forEach((entree) => {
      if (entree.zone.isConnected) entree.poser(); else zonesIa.delete(entree);
    }));
  }

  /**
   * « Proposer avec l'IA » près des précisions : l'IA reformule le symptôme et propose l'impact dans
   * un encadré. L'IA propose, l'humain valide : « Utiliser » remplit le symptôme et coche l'impact
   * proposé (s'il est dans la liste), « Modifier » fait de même puis place le curseur dans le symptôme ;
   * tout reste modifiable et rien n'est écrit avant « Envoyer ». Un impact « sécurité » déjà coché
   * n'est jamais baissé par l'IA. Sans IA utilisable sur ce poste, aucun bouton.
   * Renvoie tracer(id, envoyees) : après l'envoi réussi, une ligne de journal « proposition IA
   * utilisée » par champ venu de l'IA (l'impact seulement s'il a été envoyé tel que proposé).
   */
  function brancherIa(formulaire, selecteur) {
    const utilisees = new Map();            // champ → { valeur (null : texte retouchable), modele }

    async function tracer(id, envoyees) {
      for (const [champ, proposition] of utilisees) {
        if (proposition.valeur !== null && proposition.valeur !== envoyees[champ]) continue;
        try {
          await Ia.tracerUtilisation('demandes', id, champ, proposition.modele);
        } catch (erreur) {
          console.warn('Prévo (demandes) : trace de la proposition IA non écrite (' + (erreur && erreur.message) + ').', erreur);
        }
      }
      utilisees.clear();
    }
    if (typeof Ia === 'undefined') return tracer;

    const zone = UI.$('.di-ia', formulaire);
    const champSymptome = UI.$('input[name=symptome]', formulaire);
    const champDescription = UI.$('textarea[name=description]', formulaire);
    const impactCoche = () => { const coche = UI.$('input[name=impact]:checked', formulaire); return coche ? coche.value : ''; };
    // L'impact proposé, sauf s'il baissait un impact « sécurité » déjà choisi.
    const impactRetenu = (propose) => (propose && impactCoche() !== 'sécurité' ? propose : '');

    // Données envoyées (liste blanche du §17.3) : jamais le nom du demandeur.
    function donnees() {
      const equipement = Donnees.trouver('equipements', selecteur.valeur()) || {};
      return { symptome: champSymptome.value, description: champDescription.value,
        repere: equipement.repere, designation: equipement.designation };
    }

    function rendu(resultat) {
      const garde = resultat.impact && resultat.impact !== 'sécurité' && !impactRetenu(resultat.impact);
      return UI.html`<ul class="ia-liste">
        <li>${I18n.html('demandes.brancher_ia.symptome_symptome', { symptome: resultat.symptome })}</li>
        <li>${I18n.t('demandes.brancher_ia.impact')} ${resultat.impact ? UI.html`<b>${resultat.impact}</b>` : I18n.t('demandes.brancher_ia.aucun_impact_liste_propose')}${garde ? ' ' + I18n.t('demandes.brancher_ia.securite_choisi_garde') : ''}</li>
      </ul>`;
    }

    // « Utiliser » et « Modifier » : remplissent le formulaire par les événements habituels (code
    // symptôme, priorité calculée, saisie en cours) ; rien n'est écrit.
    function reprendre(resultat, reponse) {
      const longueurMax = champSymptome.maxLength > 0 ? champSymptome.maxLength : undefined;
      champSymptome.value = resultat.symptome.slice(0, longueurMax);
      champSymptome.dispatchEvent(new Event('input', { bubbles: true }));
      utilisees.set('symptome', { valeur: null, modele: reponse.modele });
      const impact = impactRetenu(resultat.impact);
      const radio = UI.$$('input[name=impact]', formulaire).find((bouton) => impact && bouton.value === impact);
      if (!radio) return;
      radio.checked = true;
      radio.dispatchEvent(new Event('change', { bubbles: true }));
      utilisees.set('impact', { valeur: impact, modele: reponse.modele });
    }

    function proposer() {
      if (!champSymptome.value.trim() && !champDescription.value.trim()) {
        UI.toast(I18n.t('demandes.brancher_ia.ecrivez_abord_constatez_question'), 'attention');
        return;
      }
      Ia.ouvrirEncadre({ apres: zone, fonction: 'reformulerDI', donnees: donnees(), rendu,
        utiliser: (resultat, reponse) => {
          reprendre(resultat, reponse);
          UI.toast(I18n.t('demandes.brancher_ia.proposition_reprise_formulaire_relisez'), 'info');
        },
        modifier: (resultat, reponse) => { reprendre(resultat, reponse); champSymptome.focus(); } });
    }

    function poser() {
      zone.textContent = '';
      const bouton = Ia.bouton(I18n.t('demandes.brancher_ia.proposer_ia'), proposer);
      if (bouton) zone.appendChild(bouton);
      zone.hidden = !bouton;
    }
    // Un symptôme remplacé par une suggestion ne vient plus de l'IA.
    formulaire.addEventListener('click', (evenement) => {
      if (evenement.target.closest('.di-puce')) utilisees.delete('symptome');
    });
    suivreIa(zone, poser);
    return tracer;
  }

  // Écran de confirmation : le numéro en grand, et la suite possible.
  function afficherConfirmation(conteneur, id) {
    const demande = Donnees.trouver('demandes', id) || { id, impact: '', equipement_id: '' };
    const priorite = prioriteDeLaDemande(demande);
    // OT d'origine verrouillé (lu après l'écriture : la marque l'a relu s'il a changé ailleurs).
    const otOrigine = demande.ot_origine_id ? Donnees.trouver('ordres_travail', demande.ot_origine_id) : null;
    const origineVerrouillee = Ordres.estVerrouille(otOrigine)
      ? UI.html`<br>${I18n.t('demandes.confirmation.ot_verrouille_pas_ete', { ot_origine_id: demande.ot_origine_id, otOrigineStatut: otOrigine.statut })}` : '';
    App.definirTitre(I18n.t('demandes.confirmation.demande_envoyee'));
    UI.remplir(conteneur, UI.html`
      <div class="di-confirmation" role="status">
        <div class="carte di-confirmation-carte">
          <div class="di-confirmation-icone">${UI.icone('valider')}</div>
          <p class="di-confirmation-titre">${I18n.t('demandes.confirmation.demande_envoyee')}</p>
          <p class="di-numero" data-numero="${id}">${id}</p>
          <p class="di-confirmation-texte">${I18n.html('demandes.confirmation.notez_numero_permet_suivre', { libelleEquipement: libelleEquipement(demande.equipement_id) })} ${UI.badgePriorite(priorite)}</p>
          ${demande.ot_origine_id ? UI.html`<p class="di-confirmation-texte di-confirmation-origine">${I18n.t('demandes.confirmation.anomalie_signalee_pendant_ot')} ${lienOt(demande.ot_origine_id)}.${origineVerrouillee}</p>` : ''}
        </div>
        <div class="di-zone-securite"></div>
        <div class="pile-gros">
          <a class="btn btn-primaire btn-gros" href="#/di/${encodeURIComponent(id)}">${UI.icone('demandes')}<span>${I18n.t('demandes.confirmation.voir_ma_demande')}</span></a>
          <a class="btn btn-secondaire btn-gros" href="#/di">${UI.icone('ordres')}<span>${I18n.t('demandes.confirmation.mes_demandes')}</span></a>
          <button type="button" class="btn btn-secondaire btn-gros di-autre">${UI.icone('ajouter')}<span>${I18n.t('demandes.confirmation.signaler_autre_probleme')}</span></button>
        </div>
      </div>`);
    if (demande.impact === 'sécurité') {
      UI.$('.di-zone-securite', conteneur).appendChild(UI.bandeau('securite',
        UI.html`${I18n.html('demandes.confirmation.danger_mettez_zone_securite')}`));
    }
    UI.$('.di-autre', conteneur).addEventListener('click', () => App.naviguer('#/di/nouvelle'));
    window.scrollTo(0, 0);
  }

  // Écran enregistré par demandes-fiche.js (usage interne au module).
  Object.assign(Demandes.interne, { afficherNouvelle });

  return {};
})());
