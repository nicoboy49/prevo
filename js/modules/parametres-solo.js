'use strict';
// Parametres (3/4) — carte « Mode Solo » de l'écran Paramètres (ARCHITECTURE.md §22.11 ; CDC D132).
// Le mode Solo est le profil Responsable avec le réglage mode_solo = 1 de parametres.csv, pas un
// quatrième profil (App.modeSolo(), App.technicienSolo() dans js/app.js).
//   « Passer en mode Solo » : prénom, nom, métier (facultatif) → technicien « moi » créé par les
//   écritures du module Équipe (Equipe.creerTechnicien ; repris s'il existe déjà, actif, sous le même
//   nom), puis mode_solo = 1, solo_technicien_id et cloture_une_etape = 1 (clôture en une étape) dans parametres.csv.
//   « Quitter le mode Solo » : mode_solo = 0, rien n'est supprimé (le technicien reste dans l'équipe) ;
//   cloture_une_etape reste tel quel (réglage « Ordres de travail » du formulaire, désactivable).
// Les réglages (libellés, aides) sont déclarés dans la liste REGLAGES de parametres.js, qui affiche la
// carte par un relais (carteSolo, brancherSolo). Complète l'objet Parametres.

Object.assign(Parametres.interne, (() => {

  let reglages = [];                          // REGLAGES de parametres.js, reçus à l'affichage

  function reglage(cle) {
    return reglages.find((candidat) => candidat.cle === cle) || { libelle: cle, aide: '' };
  }

  // Écrit des clés de parametres.csv (ligne créée si elle manque) en une seule écriture.
  function ecrireParametres(valeurs, action) {
    return Donnees.modifier('parametres', (lignes) => {
      Object.keys(valeurs).forEach((cle) => {
        const ligne = lignes.find((l) => l.cle === cle);
        if (ligne) ligne.valeur = valeurs[cle]; else lignes.push({ cle: cle, valeur: valeurs[cle] });
      });
    }, { action: action });
  }

  function nomTechnicien(technicien) {
    return [technicien.prenom, technicien.nom].map((partie) => String(partie || '').trim()).filter(Boolean).join(' ');
  }

  /** Carte « Mode Solo » (fragment UI.html) ; `listeReglages` : REGLAGES de parametres.js. */
  function carteSolo(listeReglages) {
    reglages = listeReglages || [];
    const actif = App.modeSolo();
    const technicienId = App.technicienSolo();
    const technicien = technicienId ? Donnees.trouver('techniciens', technicienId) : null;
    return UI.html`<article class="carte" id="carte-solo">
      <div class="entete-carte"><h2>Mode Solo</h2>${actif ? UI.html`<span class="badge ok" id="solo-etat">Activé</span>` : ''}</div>
      <p>${reglage('mode_solo').aide}</p>
      ${actif ? UI.html`<dl class="valeurs">
          <dt>${reglage('solo_technicien_id').libelle}</dt>
          <dd id="solo-technicien">${technicien ? UI.html`<a href="#/equipe/${encodeURIComponent(technicien.id)}">${nomTechnicien(technicien) || technicien.id}</a> (${technicien.id})` : 'aucun'}</dd>
        </dl>
        <p class="note">${reglage('solo_technicien_id').aide} Les profils Demandeur et Technicien restent proposés sur les autres postes.</p>
        <div class="actions"><button type="button" class="btn btn-secondaire" id="btn-quitter-solo">${UI.icone('fermer')}Quitter le mode Solo</button></div>`
      : UI.html`<p class="note">Seul à la maintenance ? Prévo crée votre fiche de technicien et vous propose comme technicien de chaque nouvel OT.</p>
        <div class="actions"><button type="button" class="btn btn-primaire" id="btn-passer-solo">${UI.icone('utilisateur')}Passer en mode Solo</button></div>`}
    </article>`;
  }

  // Technicien actif de même prénom et nom (casse et accents ignorés) : repris plutôt que doublé.
  function technicienExistant(valeurs) {
    const cle = UI.normaliserRecherche(valeurs.nom + ' ' + valeurs.prenom);
    return Donnees.lignes('techniciens').find((t) => t.actif !== '0'
      && UI.normaliserRecherche(String(t.nom || '').trim() + ' ' + String(t.prenom || '').trim()) === cle) || null;
  }

  async function passerEnSolo() {
    const fait = await UI.fenetreAction({
      titre: 'Passer en mode Solo', libelleValider: 'Passer en mode Solo',
      introduction: UI.html`<p>Vous faites la maintenance vous-même : Prévo vous ajoute à l'équipe et vous propose comme technicien de chaque nouvel OT.</p>`,
      champs: [
        UI.champ({ nom: 'prenom', type: 'texte', libelle: 'Prénom' }, '', { obligatoire: true }),
        UI.champ({ nom: 'nom', type: 'texte', libelle: 'Nom' }, '', { obligatoire: true }),
        UI.champ({ nom: 'metier', type: 'texte', libelle: 'Métier (facultatif)' }, ''),
      ],
      verifier: () => [],
      action: async (valeurs) => {
        const existant = technicienExistant(valeurs);
        const technicienId = existant ? existant.id
          : await Equipe.creerTechnicien({ prenom: valeurs.prenom, nom: valeurs.nom, metier: valeurs.metier });
        await ecrireParametres({ mode_solo: '1', solo_technicien_id: technicienId, cloture_une_etape: '1' }, 'passage en mode Solo');
      },
    });
    if (!fait) return;
    App.marquerSaisie(false);
    UI.toast('Mode Solo activé.', 'succes');
    await App.reafficher();
  }

  async function quitterSolo() {
    await ecrireParametres({ mode_solo: '0' }, 'fin du mode Solo');
    App.marquerSaisie(false);
    UI.toast('Mode Solo quitté : rien n\'a été supprimé.', 'succes');
    await App.reafficher();
  }

  /** Branche les boutons de la carte ; `pendant(bouton, contexte, action)` : outil de parametres.js. */
  function brancherSolo(conteneur, pendant) {
    const passer = UI.$('#btn-passer-solo', conteneur);
    if (passer) passer.addEventListener('click', () => passerEnSolo());
    const quitter = UI.$('#btn-quitter-solo', conteneur);
    if (quitter) quitter.addEventListener('click', () => pendant(quitter, 'fin du mode Solo', quitterSolo));
  }

  return { carteSolo, brancherSolo };
})());
