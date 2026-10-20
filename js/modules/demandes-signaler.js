'use strict';
// Demandes (3/5) — écran « Signaler un problème » (#/di/nouvelle, ?equipement=…) : cinq questions
// pensées téléphone d'abord (équipement, symptôme, impact, précisions, photo), puis l'écran de
// confirmation avec le numéro de la demande (ARCHITECTURE.md §8 et §14.2 ; brief §9 E2).
// Complète l'objet Demandes.

Object.assign(Demandes, (() => {

  // Constantes, outils, règles et écritures des fichiers précédents (demandes-regles.js, demandes-ecritures.js).
  const { IMPACTS, prioriteCalculee, libelleEquipement, creer } = Demandes;
  const { texte, sansAccents, nomDuProfil, prioriteDeLaDemande, nomPhoto } = Demandes.interne;

  // ===========================================================================================
  // 5. Écran « Signaler un problème » (#/di/nouvelle)
  // ===========================================================================================

  function afficherNouvelle(conteneur, parametres) {
    const equipementDemande = parametres.requete ? texte(parametres.requete.get('equipement')) : '';
    const libellesSymptomes = Donnees.lignes('codes_defaillance')
      .filter((code) => sansAccents(code.famille) === 'symptome' && code.libelle)
      .map((code) => code.libelle);
    const idSymptome = UI.identifiantUnique('di-symptome');
    const idDescription = UI.identifiantUnique('di-description');
    const idListe = UI.identifiantUnique('di-suggestions');
    const idPhoto = UI.identifiantUnique('di-photo');

    UI.remplir(conteneur, UI.html`
      <div class="di-nouvelle">
        <div class="entete-page"><div>
          <h1>Signaler un problème</h1>
          <p>Cinq questions, une minute. Le responsable maintenance reçoit votre demande aussitôt.</p>
        </div></div>
        <div class="di-alerte-equipement"></div>
        <form class="form-colonne di-formulaire" novalidate>
          <section class="carte di-etape">
            <div class="champ" data-champ="equipement_id">
              <span class="libelle">1. Quel équipement ? <span class="requis" aria-hidden="true">*</span></span>
              <div class="di-selecteur"></div>
              <p class="erreur-champ" hidden></p>
            </div>
          </section>

          <section class="carte di-etape">
            <div class="champ" data-champ="symptome">
              <label class="libelle" for="${idSymptome}">2. Que constatez-vous ? <span class="requis" aria-hidden="true">*</span></label>
              <input type="text" id="${idSymptome}" name="symptome" list="${idListe}" maxlength="200" required
                aria-required="true" autocomplete="off" enterkeyhint="next"
                placeholder="Ex. fuite d'huile sous la pompe">
              <datalist id="${idListe}">${libellesSymptomes.map((libelle) => UI.html`<option value="${libelle}"></option>`)}</datalist>
              ${libellesSymptomes.length ? UI.html`<div class="di-suggestions" role="group" aria-label="Suggestions de symptômes">
                ${libellesSymptomes.map((libelle) => UI.html`<button type="button" class="di-puce" data-symptome="${libelle}">${libelle}</button>`)}
              </div>` : ''}
              <p class="erreur-champ" hidden></p>
            </div>
          </section>

          <section class="carte di-etape">
            <div class="champ" data-champ="impact">
              <span class="libelle" id="${idSymptome}-impact">3. Quel impact ? <span class="requis" aria-hidden="true">*</span></span>
              <fieldset class="tuiles di-impacts" aria-labelledby="${idSymptome}-impact">
                ${IMPACTS.map((entree) => UI.html`
                  <label class="tuile${entree.valeur === 'sécurité' ? ' securite' : ''}">
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
              <label class="libelle" for="${idDescription}">4. Précisions <span class="aide">(facultatif)</span></label>
              <textarea id="${idDescription}" name="description" rows="4" data-dictee
                placeholder="Depuis quand ? Bruit, odeur, voyant allumé… Le clavier du téléphone permet de dicter."></textarea>
            </div>
          </section>

          <section class="carte di-etape">
            <div class="champ" data-champ="photo">
              <span class="libelle">5. Une photo <span class="aide">(facultatif)</span></span>
              <label class="btn btn-secondaire btn-gros di-bouton-photo" for="${idPhoto}">
                ${UI.icone('photo')}<span class="di-texte-photo">Prendre une photo<small>ou en choisir une dans la galerie</small></span>
              </label>
              <input type="file" id="${idPhoto}" class="di-fichier-photo" accept="image/*" capture="environment">
              <div class="di-apercu" hidden>
                <img class="di-apercu-image" alt="Photo jointe à la demande">
                <button type="button" class="btn btn-fantome di-retirer-photo">${UI.icone('fermer')}Retirer la photo</button>
              </div>
              <p class="aide di-etat-photo" aria-live="polite"></p>
            </div>
          </section>

          <p class="di-demandeur">Demande envoyée au nom de <b>${nomDuProfil()}</b>.</p>
          <button type="submit" class="btn btn-primaire btn-gros di-envoyer">
            ${UI.icone('valider')}<span>Envoyer la demande</span>
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
      },
    });
    if (equipementDemande && !selecteur.valeur()) {
      UI.$('.di-alerte-equipement', conteneur).appendChild(UI.bandeau('attention',
        UI.html`L'équipement <b>${equipementDemande}</b> est inconnu ou n'est plus actif : choisissez-le dans la liste.`));
    }

    // --- 2. symptôme : les puces remplissent le champ ---------------------------------------
    formulaire.addEventListener('click', (evenement) => {
      const puce = evenement.target.closest('.di-puce');
      if (!puce) return;
      champSymptome.value = puce.dataset.symptome;
      champSymptome.dispatchEvent(new Event('input', { bubbles: true }));
      effacerErreur('symptome');
    });
    champSymptome.addEventListener('input', () => { if (champSymptome.value.trim()) effacerErreur('symptome'); });

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
          UI.html`<b>Danger : mettez la zone en sécurité et prévenez votre responsable.</b>`));
      }
      const equipement = Donnees.trouver('equipements', selecteur.valeur());
      if (!impact) {
        UI.remplir(zonePriorite, UI.html`<span class="aide">La priorité s'affiche quand l'impact est choisi.</span>`);
        return;
      }
      const priorite = prioriteCalculee(equipement ? equipement.criticite : '', impact);
      UI.remplir(zonePriorite, UI.html`Priorité calculée : ${UI.badgePriorite(priorite)}
        <span class="aide">${equipement ? 'criticité ' + (equipement.criticite || 'B') + ' × impact ' + impact
          : 'choisissez l\'équipement pour affiner'}</span>`);
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
      UI.remplir(UI.$('.di-texte-photo', formulaire), UI.html`Prendre une photo<small>ou en choisir une dans la galerie</small>`);
    }

    champPhoto.addEventListener('change', () => {
      const fichier = champPhoto.files && champPhoto.files[0];
      if (!fichier) return;
      libererApercu();
      photo.blob = null;
      photo.nomEnvoye = '';
      etatPhoto.textContent = 'Préparation de la photo…';
      const preparation = UI.redimensionnerPhoto(fichier, 1280).then((blob) => {
        if (photo.preparation !== preparation) return blob;    // une autre photo a été choisie entre-temps
        photo.blob = blob;
        photo.adresseApercu = URL.createObjectURL(blob);
        imageApercu.src = photo.adresseApercu;
        apercu.hidden = false;
        etatPhoto.textContent = 'Photo prête (' + Math.max(1, Math.round(blob.size / 1024)) + ' Ko). Elle sera envoyée avec la demande.';
        UI.remplir(UI.$('.di-texte-photo', formulaire), UI.html`Changer la photo<small>la photo actuelle sera remplacée</small>`);
        return blob;
      }).catch((erreur) => {
        if (photo.preparation === preparation) retirerPhoto();
        UI.toast('Cette photo ne peut pas être lue. Essayez une autre photo.', 'attention');
        console.warn('Prévo (demandes) : photo illisible (' + (erreur && erreur.message) + ').', erreur);
        return null;
      });
      photo.preparation = preparation;
    });
    UI.$('.di-retirer-photo', formulaire).addEventListener('click', retirerPhoto);

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
      if (!selecteur.valeur()) manques.push(['equipement_id', 'Choisissez l\'équipement concerné.']);
      if (!champSymptome.value.trim()) manques.push(['symptome', 'Décrivez en quelques mots ce que vous constatez.']);
      if (!impactChoisi()) manques.push(['impact', 'Choisissez l\'impact.']);
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
      texteBouton.textContent = 'Envoi en cours…';
      try {
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
          impact,
          description: UI.$('textarea[name=description]', formulaire).value,
          photo: nomDeLaPhoto,
        });
        App.marquerSaisie(false);
        libererApercu();
        afficherConfirmation(conteneur, id);
      } catch (erreur) {
        App.signalerErreur(erreur, 'envoi de la demande');
        boutonEnvoyer.disabled = false;
        boutonEnvoyer.removeAttribute('aria-busy');
        texteBouton.textContent = 'Envoyer la demande';
      }
    });
  }

  // Écran de confirmation : le numéro en grand, et la suite possible.
  function afficherConfirmation(conteneur, id) {
    const demande = Donnees.trouver('demandes', id) || { id, impact: '', equipement_id: '' };
    const priorite = prioriteDeLaDemande(demande);
    App.definirTitre('Demande envoyée');
    UI.remplir(conteneur, UI.html`
      <div class="di-confirmation" role="status">
        <div class="carte di-confirmation-carte">
          <div class="di-confirmation-icone">${UI.icone('valider')}</div>
          <p class="di-confirmation-titre">Demande envoyée</p>
          <p class="di-numero" data-numero="${id}">${id}</p>
          <p class="di-confirmation-texte">Notez ce numéro : il permet de suivre votre demande.<br>
            ${libelleEquipement(demande.equipement_id)} · priorité ${UI.badgePriorite(priorite)}</p>
        </div>
        <div class="di-zone-securite"></div>
        <div class="pile-gros">
          <a class="btn btn-primaire btn-gros" href="#/di/${encodeURIComponent(id)}">${UI.icone('demandes')}<span>Voir ma demande</span></a>
          <a class="btn btn-secondaire btn-gros" href="#/di">${UI.icone('ordres')}<span>Mes demandes</span></a>
          <button type="button" class="btn btn-secondaire btn-gros di-autre">${UI.icone('ajouter')}<span>Signaler un autre problème</span></button>
        </div>
      </div>`);
    if (demande.impact === 'sécurité') {
      UI.$('.di-zone-securite', conteneur).appendChild(UI.bandeau('securite',
        UI.html`<b>Danger : mettez la zone en sécurité et prévenez votre responsable.</b> N'attendez pas la réponse à cette demande.`));
    }
    UI.$('.di-autre', conteneur).addEventListener('click', () => App.naviguer('#/di/nouvelle'));
    window.scrollTo(0, 0);
  }

  // Écran enregistré par demandes-fiche.js (usage interne au module).
  Object.assign(Demandes.interne, { afficherNouvelle });

  return {};
})());
