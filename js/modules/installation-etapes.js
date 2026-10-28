'use strict';
// InstallationEtapes : les formulaires des huit étapes de l'assistant d'installation (installation-ecrans.js,
// ARCHITECTURE.md §22.10 ; D131, D132 ; CS130) — champs, « Régler autrement » (réglages fins avec l'aide
// d'AccesTextes.options), lecture des valeurs et messages. Chaque formulaire reçoit le contexte « c » de l'écran :
// c.etat (GET etat), c.brouillon(), c.situation(), c.etatEtape(cle), c.blocTextes(choix), c.aideOption(cle).
// Les réglages que l'API n'écrit pas (durées de session, IA, quota) sont montrés avec leur aide et renvoyés à
// Paramètres › Accès et installation. Migration depuis 1.2 (T171) : les CSV présents sont annoncés dès l'étape 1 et
// gardés ; sans CSV au départ (brouillon.base_presente faux), l'étape 8 demande par quoi commencer (vide ou démo) ;
// dossier conseillé C:\Prevo proposé à l'étape 8 tant que le brouillon n'a pas deplacement_refuse (« Rester ici »).
// Dépendances : UI, AccesTextes. Chargé avant installation-ecrans.js.

const InstallationEtapes = (() => {

  const LONGUEUR_MIN_MOT_DE_PASSE = 12;        // règles du serveur (§22.3)
  const LONGUEUR_MAX_MOT_DE_PASSE = 256;
  const LONGUEUR_SOLIDE = 20;
  const LIEN_TAILSCALE = 'https://tailscale.com/download';
  const LIBELLES_PORTEE = { 'ce-pc': 'Seulement sur ce PC', atelier: 'Sur le Wi-Fi de l\'atelier', dehors: 'Aussi hors de l\'atelier' };
  const LIBELLES_DEMARRAGE = { systeme: 'Avec le PC, sans fenêtre', session: 'À l\'ouverture de session', aucun: 'À la main, par le raccourci' };

  // ===========================================================================================
  // 1. Petits blocs : champ d'un réglage, réglage lu, bouton radio
  // ===========================================================================================

  function champReglage(c, cle, libelle, type, valeur, attributs) {
    return UI.html`<div class="champ">
      <label class="libelle" for="inst-${cle}">${libelle}</label>
      <input type="${type}" id="inst-${cle}" name="${cle}" value="${valeur === null || valeur === undefined ? '' : valeur}" ${UI.brut(attributs || '')}>
      <p class="aide">${c.aideOption(cle)}</p>
    </div>`;
  }

  // Réglage que l'assistant ne peut pas écrire (l'API n'a pas d'étape pour lui) : montré avec son aide et sa valeur.
  function reglageLu(c, cle) {
    const valeur = c.brouillon()[cle];
    const texte = Array.isArray(valeur) ? valeur.join(', ') : (valeur === true ? 'oui' : valeur === false ? 'non' : String(valeur === undefined ? '' : valeur));
    return UI.html`<div class="installation-reglage-lu"><b>${cle}</b> : ${texte || '—'}<p class="aide">${c.aideOption(cle)}</p></div>`;
  }

  const NOTE_PLUS_TARD = 'Ces réglages se changent après l\'installation dans Paramètres › Accès et installation, ou dans prevo.config.json.';

  function choixRadio(nom, valeur, coche, titre, detail) {
    return UI.html`<label class="installation-choix">
      <input type="radio" name="${nom}" value="${valeur}" ${UI.brut(coche ? 'checked' : '')}>
      <span><b>${titre}</b>${detail ? UI.html`<small>${detail}</small>` : ''}</span>
    </label>`;
  }

  // ===========================================================================================
  // 2. Formulaires des étapes : { champs, autrement, lire(section) → corps ou { probleme }, message (rien coché),
  //    passer (l'étape est faite : « Continuer » avance sans appel), propresBoutons (Tailscale), reussite(donnees) →
  //    toast, echec(donnees) → message qui garde l'étape ouverte, apres(section) (mots de passe vidés) }
  // ===========================================================================================

  function formulaireSituation(c) {
    const details = {
      seul: 'Un PC, un téléphone : le mode Solo (technicien « moi », clôture en une étape).',
      equipe: 'Plusieurs personnes, des téléphones : comptes, https, appareils enrôlés par QR.',
      informaticien: 'Toutes les options sur une page ; rien d\'automatique sans votre accord.',
    };
    const choisie = c.situation();
    const nombre = Number(c.etat.nombre_csv) || 0;
    // Migration depuis 1.2 (D131, T171) : des CSV sont là → dit dès la première étape ; ils ne sont jamais touchés.
    const migration = c.etat.csv_presents ? UI.html`<div class="alerte" id="inst-migration"><div class="alerte-texte">
        <b>Vos données de Prévo 1.2 sont là</b> : ${nombre} fichier${nombre > 1 ? 's' : ''}${c.etat.derniere_modification
          ? ', dernière modification le ' + UI.dateHeureFr(c.etat.derniere_modification) : ''} ; elles sont gardées. L'assistant règle
        l'accès (comptes, https, téléphones) sans rien changer à vos fichiers.</div></div>` : '';
    return {
      champs: UI.html`${migration}<div class="installation-choix-liste">${Object.keys(AccesTextes.situations).map((cle) =>
        choixRadio('situation', cle, cle === choisie, AccesTextes.situations[cle], details[cle]))}</div>`,
      autrement: UI.html`<p class="note">Tout ce que l'assistant règle s'écrit dans <b>prevo.config.json</b>, à côté de serveur.py, à la fin
        (« Terminer ») ; rien avant. Un informaticien peut aussi tout faire en ligne de commande : <b>serveur.py --aide</b>.</p>`,
      lire(section) {
        const coche = UI.$('input[name="situation"]:checked', section);
        return coche ? { situation: coche.value } : null;
      },
      message: 'Choisissez qui va utiliser Prévo.',
    };
  }

  function formulairePortee(c) {
    const b = c.brouillon();
    const details = { 'ce-pc': 'Ni compte ni https : personne d\'autre ne peut le joindre.',
      atelier: 'Postes et téléphones de l\'entreprise ; compte du responsable et https.',
      dehors: 'Téléphone en déplacement, maison : par un réseau privé (Tailscale).' };
    return {
      champs: UI.html`<p class="aide">${c.aideOption('portee')}</p>
        <div class="installation-choix-liste">${Object.keys(LIBELLES_PORTEE).map((cle) =>
          choixRadio('portee', cle, cle === b.portee, LIBELLES_PORTEE[cle], details[cle]))}</div>`,
      autrement: UI.html`<div class="form-colonne">
        ${champReglage(c, 'port_http', 'Port http (l\'application sur ce PC, la porte d\'entrée sur le réseau)', 'number', b.port_http, 'min="1" max="65535"')}
        ${champReglage(c, 'port_https', 'Port https (l\'application sur le réseau)', 'number', b.port_https, 'min="1" max="65535"')}
        ${champReglage(c, 'noms', 'Noms acceptés (séparés par des virgules)', 'text', (b.noms || []).join(', '), 'autocomplete="off" spellcheck="false"')}
      </div>`,
      lire(section) {
        const coche = UI.$('input[name="portee"]:checked', section);
        if (!coche) return null;
        return { portee: coche.value, port_http: Number(UI.$('#inst-port_http', section).value),
          port_https: Number(UI.$('#inst-port_https', section).value), noms: nomsSaisis(section) };
      },
      message: 'Choisissez d\'où Prévo doit pouvoir être ouvert.',
    };
  }

  // Noms acceptés saisis dans une section (virgules, points-virgules ou espaces) ; le serveur les met en minuscules.
  function nomsSaisis(section) {
    const champ = UI.$('#inst-noms', section);
    return champ ? champ.value.split(/[\s,;]+/).map((n) => n.trim()).filter(Boolean) : [];
  }

  function indicationForce(valeur) {
    const longueur = valeur.length;
    if (!longueur) return '';
    if (longueur < LONGUEUR_MIN_MOT_DE_PASSE) return longueur + ' caractère' + (longueur > 1 ? 's' : '') + ' : trop court (' + LONGUEUR_MIN_MOT_DE_PASSE + ' au moins).';
    if (longueur < LONGUEUR_SOLIDE) return longueur + ' caractères : correct. Plus long, c\'est plus solide.';
    return longueur + ' caractères : solide.';
  }

  function formulaireCompte(c) {
    const b = c.brouillon();
    const sansMotDePasse = b.portee === 'ce-pc';            // Solo sur ce PC : le technicien « moi », sans compte
    const existant = Boolean(c.etat.responsable_existe) || c.etatEtape('compte') === 'fait';
    return {
      champs: UI.html`
        ${existant ? UI.html`<div class="alerte"><div class="alerte-texte"><b>Un compte responsable existe déjà.</b> Cette étape est faite : continuez. Pour un mot de
          passe perdu, le script Reinitialiser_mot_de_passe.bat sur ce PC le remplace.</div></div>` : ''}
        ${sansMotDePasse ? UI.html`<p class="note">Sur ce PC seulement : votre nom crée votre fiche de technicien, sans mot de passe.</p>` : ''}
        <div class="form-colonne">
          <div class="champ"><label class="libelle" for="inst-prenom">Prénom <span class="requis" aria-hidden="true">*</span></label>
            <input type="text" id="inst-prenom" name="prenom" autocomplete="given-name" maxlength="80"></div>
          <div class="champ"><label class="libelle" for="inst-nom">Nom</label>
            <input type="text" id="inst-nom" name="nom" autocomplete="family-name" maxlength="80"></div>
          ${sansMotDePasse ? '' : UI.html`
          <p class="note">12 caractères au moins, 256 au plus, aucune règle de composition : une phrase de passe de plusieurs mots est conseillée.
            Un mot de passe perdu se réinitialise sur ce PC (Reinitialiser_mot_de_passe.bat), jamais par courriel.</p>
          <div class="champ"><label class="libelle" for="inst-mot-de-passe">Mot de passe</label>
            <input type="password" id="inst-mot-de-passe" name="mot_de_passe" autocomplete="new-password" minlength="12" maxlength="256" aria-describedby="inst-force">
            <p class="aide" id="inst-force" aria-live="polite"></p></div>
          <div class="champ"><label class="libelle" for="inst-confirmation">Confirmation</label>
            <input type="password" id="inst-confirmation" name="confirmation" autocomplete="new-password" maxlength="256"></div>`}
        </div>`,
      autrement: UI.html`<p class="note">${NOTE_PLUS_TARD}</p>${['session_heures', 'session_longue_jours', 'invitation_heures', 'demandeurs_avec_compte'].map((cle) => reglageLu(c, cle))}`,
      passer: existant,
      lire(section) {
        const prenom = UI.$('#inst-prenom', section).value.trim();
        if (!prenom) return { probleme: 'Le prénom est obligatoire.' };
        const corps = { prenom: prenom, nom: UI.$('#inst-nom', section).value.trim() };
        if (sansMotDePasse) return corps;
        const motDePasse = UI.$('#inst-mot-de-passe', section).value;
        if (motDePasse.length < LONGUEUR_MIN_MOT_DE_PASSE) return { probleme: 'Le mot de passe doit faire ' + LONGUEUR_MIN_MOT_DE_PASSE + ' caractères au moins (il en a ' + motDePasse.length + ').' };
        if (motDePasse.length > LONGUEUR_MAX_MOT_DE_PASSE) return { probleme: 'Le mot de passe doit faire ' + LONGUEUR_MAX_MOT_DE_PASSE + ' caractères au plus.' };
        if (motDePasse !== UI.$('#inst-confirmation', section).value) return { probleme: 'La confirmation ne correspond pas au mot de passe.' };
        return Object.assign(corps, { mot_de_passe: motDePasse });
      },
      // Les mots de passe ne restent jamais dans la page : vidés à chaque réponse.
      apres(section) {
        UI.$$('input[type="password"]', section).forEach((champ) => { champ.value = ''; });
        const force = UI.$('#inst-force', section);
        if (force) force.textContent = '';
      },
    };
  }

  function formulaireCertificat(c) {
    const b = c.brouillon();
    const informaticien = c.situation() === 'informaticien';
    const dehors = b.portee === 'dehors';
    const tailscale = c.etat.tailscale || {};
    let choisi = b.certificat_auto ? 'automatique' : b.certificat ? 'fichiers' : b.mandataire ? (dehors ? 'reseau_prive' : 'mandataire') : '';
    if (!choisi) choisi = informaticien ? 'mandataire' : (c.situation() === 'seul' && dehors && tailscale.present ? 'reseau_prive' : 'automatique');
    const principal = [
      choixRadio('mode', 'automatique', choisi === 'automatique', 'Automatique (recommandé)',
        c.etat.mkcert_present ? 'Prévo fabrique un certificat pour l\'atelier ; chaque téléphone lui fait confiance une fois (QR).'
          : 'mkcert est introuvable dans outils-tiers/ : remettez-le (il est dans le zip de Prévo), ou choisissez une autre voie.'),
      dehors ? choixRadio('mode', 'reseau_prive', choisi === 'reseau_prive', 'Par le réseau privé (Tailscale)',
        tailscale.present ? 'Certificat reconnu partout, rien à installer sur les téléphones ; Prévo n\'est joignable que par l\'adresse Tailscale.'
          : 'Tailscale n\'est pas détecté sur ce PC : il sera guidé à l\'étape suivante.') : '',
    ];
    const avances = [
      choixRadio('mode', 'fichiers', choisi === 'fichiers', 'J\'ai mon certificat (deux fichiers PEM)', 'Fourni par la PKI de l\'entreprise.'),
      choixRadio('mode', 'mandataire', choisi === 'mandataire', 'Derrière mon mandataire inverse', 'IIS, nginx, Caddy ou tailscale serve portent le https ; Prévo écoute sur 127.0.0.1.'),
    ];
    const fichiers = UI.html`<div class="form-colonne">
      ${champReglage(c, 'certificat', 'Certificat (fichier PEM)', 'text', b.certificat, 'autocomplete="off" spellcheck="false"')}
      ${champReglage(c, 'cle', 'Clé privée (fichier PEM)', 'text', b.cle, 'autocomplete="off" spellcheck="false"')}
      ${champReglage(c, 'noms', 'Noms acceptés (mandataire : le nom par lequel il appelle Prévo)', 'text', (b.noms || []).join(', '), 'autocomplete="off" spellcheck="false"')}
    </div>`;
    return {
      champs: UI.html`<div class="installation-choix-liste">${principal}${informaticien ? avances : ''}</div>${informaticien ? fichiers : ''}`,
      autrement: informaticien ? UI.html`<p class="note">${c.aideOption('certificat_auto')} ${c.aideOption('mandataire')}</p>`
        : UI.html`<div class="installation-choix-liste">${avances}</div>${fichiers}`,
      lire(section) {
        const coche = UI.$('input[name="mode"]:checked', section);
        if (!coche) return null;
        const corps = { mode: coche.value };
        const noms = nomsSaisis(section);
        if (corps.mode === 'fichiers') Object.assign(corps, { certificat: UI.$('#inst-certificat', section).value.trim(), cle: UI.$('#inst-cle', section).value.trim() });
        if (corps.mode === 'mandataire' && noms.length) corps.noms = noms;
        return corps;
      },
      message: 'Choisissez comment Prévo obtient son certificat.',
      reussite(donnees) {
        if (donnees.mode === 'automatique') return 'Certificat prêt pour : ' + (donnees.noms_certificat || []).join(', ') + '. Les étiquettes QR déjà imprimées en http sont à réimprimer.';
        return '';
      },
    };
  }

  function formulaireTailscale(c) {
    const t = c.etat.tailscale || {};
    const b = c.brouillon();
    const ligne = !t.present ? 'Tailscale n\'est pas détecté sur ce PC' + (t.raison ? ' (' + t.raison + ')' : '') + '.'
      : t.connecte ? 'Tailscale est installé et connecté : ce PC s\'appelle ' + (t.nom || '(nom inconnu)') + '.'
        : 'Tailscale est installé mais pas connecté : ouvrez Tailscale et connectez-vous.';
    return {
      champs: UI.html`
        <p class="installation-tailscale-etat" id="inst-tailscale-etat">${ligne}</p>
        <p class="note">Tailscale demande un compte (Google, Microsoft, Apple ou GitHub : celui de votre téléphone) et son application
          sur chaque téléphone qui sort. Prévo ne crée jamais de compte à votre place, n'ouvre aucun port et n'installe rien sans clic.</p>
        ${t.present ? '' : UI.html`<p><a class="btn btn-secondaire" id="inst-tailscale-telecharger" href="${LIEN_TAILSCALE}" target="_blank" rel="noopener">Télécharger Tailscale (site officiel)</a></p>`}
        <div class="actions installation-actions-etape">
          <button type="button" class="btn btn-primaire" id="inst-tailscale-appliquer">J'ai installé Tailscale et je suis connecté</button>
          <button type="button" class="btn btn-fantome" id="inst-tailscale-plus-tard">Plus tard</button>
        </div>
        <div id="inst-tailscale-resultat" class="installation-resultat" hidden></div>`,
      autrement: UI.html`<p class="note">Ce que Prévo lancera, une fois Tailscale connecté : <code>tailscale serve --bg --https=443 http://127.0.0.1:${b.port_http || 8080}</code>
        (le nom Tailscale de ce PC est ajouté aux noms acceptés, et Prévo écoute derrière ce mandataire). Le VPN de l'entreprise : « Plus tard », puis le nom
        DNS interne dans les noms acceptés (étape « Depuis où », Régler autrement).</p>${reglageLu(c, 'noms')}`,
      propresBoutons: true,                                   // « J'ai installé… » et « Plus tard » font les appels
      passer: c.etatEtape('tailscale') === 'fait',              // déjà appliqué : « Continuer » avance sans appel
    };
  }

  function formulaireDemarrage(c) {
    const b = c.brouillon();
    const windows = c.etat.systeme === 'windows';
    const details = { systeme: 'Tâche planifiée au démarrage' + (windows ? ' et règle du pare-feu « réseau privé », créées dans la même invite d\'administrateur.' : '.'),
      session: 'Démarre quand vous ouvrez votre session, avec une fenêtre.', aucun: 'Vous lancez Prévo par le raccourci, et la fenêtre reste ouverte.' };
    return {
      champs: UI.html`<div class="installation-choix-liste">${Object.keys(LIBELLES_DEMARRAGE).map((cle) =>
          choixRadio('demarrage', cle, cle === (b.demarrage || 'aucun'), LIBELLES_DEMARRAGE[cle], details[cle]))}</div>
        <label class="case installation-case"><input type="checkbox" id="inst-veille" ${UI.brut(b.veille_desactivee ? 'checked' : '')}>
          <span>Empêcher la veille du PC quand il est sur secteur</span></label>
        <p class="aide">${c.aideOption('veille_desactivee')}</p>
        ${windows ? UI.html`<p class="note" id="inst-demarrage-uac"><b>Une seule invite d'administrateur de Windows va s'ouvrir</b> pour « Avec le PC » : acceptez-la.
          Rien n'est lancé pour « À la main ».</p>` : ''}
        <div id="inst-demarrage-resultat" class="installation-resultat" hidden></div>`,
      autrement: UI.html`<p class="note">${c.aideOption('demarrage')} Les scripts sont écrits dans le dossier de Prévo (Installer_demarrage.ps1, Retirer_demarrage.ps1 ;
        prevo.service sous Linux) : un informaticien peut les relire avant de les lancer, ou préférer l'outil de service de l'entreprise.</p>`,
      lire(section) {
        const coche = UI.$('input[name="demarrage"]:checked', section);
        return coche ? { demarrage: coche.value, veille_desactivee: UI.$('#inst-veille', section).checked } : null;
      },
      message: 'Choisissez comment Prévo démarre.',
      reussite(donnees) {
        if (donnees.commandes && donnees.commandes.length) return 'À lancer à la main sur ce serveur : ' + donnees.commandes.join(' ; ');
        if (donnees.lance && !donnees.lance.ok) return null;
        return '';
      },
      echec(donnees) {
        if (donnees.lance && !donnees.lance.ok) return 'L\'invite d\'administrateur a été refusée ou a échoué (' + (donnees.lance.message || 'code ' + donnees.lance.code) + ') : réessayez, ou choisissez « À la main ».';
        return '';
      },
    };
  }

  function formulaireSauvegardes(c) {
    const b = c.brouillon();
    return {
      champs: UI.html`<p class="note">La sauvegarde du jour est déjà faite dans donnees/sauvegardes/ ; deux copies sur le même disque ne protègent pas d'une panne du disque.</p>
        <div class="form-colonne">${champReglage(c, 'copie_sauvegardes', 'Dossier de copie (clé USB, NAS, dossier OneDrive ou Drive)', 'text', b.copie_sauvegardes, 'autocomplete="off" spellcheck="false" placeholder="D:\\Sauvegardes Prevo"')}</div>
        <div class="actions installation-actions-etape"><button type="button" class="btn btn-fantome" id="inst-sauvegardes-plus-tard">Plus tard</button></div>`,
      autrement: UI.html`<p class="note">${NOTE_PLUS_TARD}</p>${reglageLu(c, 'quota_documents_mo')}`,
      lire(section) {
        const dossier = UI.$('#inst-copie_sauvegardes', section).value.trim();
        return dossier ? { dossier: dossier } : { probleme: 'Indiquez un dossier, ou choisissez « Plus tard ».' };
      },
    };
  }

  function formulaireRecapitulatif(c) {
    const b = c.brouillon();
    const lignes = [
      ['Qui utilise', AccesTextes.situations[c.situation()] || c.situation()],
      ['Depuis où', LIBELLES_PORTEE[b.portee] || b.portee],
      ['Comptes', b.comptes ? 'Connexion obligatoire (compte du responsable créé)' : 'Aucun : Prévo n\'est joignable que sur ce PC'],
      ['Certificat', b.portee === 'ce-pc' ? 'Sans objet (http sur ce PC)' : b.certificat_auto ? 'Automatique (mkcert)' : b.certificat ? 'Vos fichiers PEM' : b.mandataire ? 'Derrière un mandataire (Tailscale ou celui de l\'entreprise)' : 'À régler'],
      ['Démarrage', LIBELLES_DEMARRAGE[b.demarrage] || b.demarrage],
      ['Veille', b.veille_desactivee ? 'Empêchée sur secteur' : 'Inchangée'],
      ['Copie des sauvegardes', b.copie_sauvegardes || 'Plus tard'],
    ];
    const deplacer = c.etatEtape('deplacer') === 'a_faire' && !b.deplacement_refuse;
    // Sans CSV au départ de l'assistant (T171) : par quoi commencer ; avec (migration 1.2) : rien à demander, tout est gardé.
    const choixBase = b.base_presente === false;
    return {
      champs: UI.html`
        <dl class="installation-recap">${lignes.map(([titre, valeur]) => UI.html`<div><dt>${titre}</dt><dd>${valeur}</dd></div>`)}</dl>
        ${choixBase ? UI.html`<div class="carte installation-dossier" id="inst-base">
          <h3>Par quoi commencer ?</h3>
          <div class="installation-choix-liste">
            ${choixRadio('base', 'vide', true, 'Commencer vide', 'Vos équipements, vos demandes, vos OT : rien d\'autre.')}
            ${choixRadio('base', 'demo', false, 'Commencer avec les données de démonstration', 'Un atelier fictif (équipements, OT, gammes, magasin, wiki) pour essayer ; ses dates sont ramenées à aujourd\'hui.')}
          </div>
        </div>` : ''}
        ${deplacer ? UI.html`<div class="carte installation-dossier" id="inst-dossier">
          <h3>Dossier de Prévo</h3>
          <p>Prévo tourne dans <b>${c.etat.dossier}</b>. Le dossier conseillé est <b>${c.etat.dossier_conseille}</b> : hors des téléchargements et du bureau, un chemin
            court et stable pour la tâche planifiée et les sauvegardes.</p>
          <p>Déplacer : Prévo est copié dans ${c.etat.dossier_conseille}, chaque fichier est vérifié, puis Prévo se relance depuis là et l'assistant
            reprend ici. L'ancien dossier n'est pas supprimé : à effacer à la main ensuite.</p>
          <div class="actions">
            <button type="button" class="btn btn-secondaire" id="inst-deplacer">Déplacer Prévo dans ${c.etat.dossier_conseille} (recommandé)</button>
            <button type="button" class="btn btn-fantome" id="inst-dossier-garder">Rester ici</button>
          </div>
          <p class="erreur-champ" id="inst-deplacer-erreur" role="alert" hidden></p>
        </div>` : ''}
        <div id="inst-fiche"><p class="chargement" role="status">Lecture de la fiche d'accès…</p></div>`,
      autrement: UI.html`${c.blocTextes('ia')}<p class="note">${NOTE_PLUS_TARD}</p>${['ia_fournisseur', 'ia_url', 'ia_en_ligne'].map((cle) => reglageLu(c, cle))}`,
      // Corps de « terminer » : la base de départ quand elle a été demandée, rien sinon.
      lire(section) {
        const coche = UI.$('input[name="base"]:checked', section);
        return coche ? { base: coche.value } : {};
      },
    };
  }

  const FORMULAIRES = { situation: formulaireSituation, portee: formulairePortee, compte: formulaireCompte, certificat: formulaireCertificat,
    tailscale: formulaireTailscale, demarrage: formulaireDemarrage, sauvegardes: formulaireSauvegardes, recapitulatif: formulaireRecapitulatif };

  /** Formulaire d'une étape : { champs, autrement, lire(section), message, passer, propresBoutons, reussite, echec, apres }. */
  function formulaire(cle, contexte) {
    return FORMULAIRES[cle](contexte);
  }

  return { formulaire, indicationForce, LIBELLES_PORTEE, LIBELLES_DEMARRAGE };
})();
