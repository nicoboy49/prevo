'use strict';
// Parametres — import ZIP (chantier « socle de données », T191 ; décision D172 ; ARCHITECTURE.md §22.11, « Import
// ZIP » ; CS168 : la sécurité de ce déroulé y est écrite). Bouton « Importer un ZIP… » de la carte « Sauvegardes »
// de Paramètres, relié à Parametres.interne en fin de fichier (relais blocImportZip et brancherImportZip de
// parametres.js) ; chargé juste après parametres-sauvegardes.js. Remplacement complet seulement, jamais de fusion.
//
// Droits : la règle de l'export (ZipDonnees.exportPermis) : avec les comptes, le responsable seul (bouton absent pour
// les autres rôles, qui n'ouvrent d'ailleurs pas Paramètres) ; sans comptes (« ce PC », mode dossier), tout profil
// qui ouvre Paramètres. Démo : bouton inactif, « indisponible en démo ». Lecture seule (D169) : refusé, avec le
// message, avant toute lecture du ZIP.
//
// Déroulé (ParametresZip.importer(fichier)) :
//   1. ZipLecture.lire (contrôles stricts, migration en mémoire, rien d'écrit) ; refus → fenêtre #import-zip-refus ;
//   2. confirmation #confirmation-import-zip : date et version du ZIP (manifeste), format (« mis au format N »), lignes
//      par table (actuel → importé), tables vidées (absentes du ZIP), nombre de documents, avertissement ;
//      Annuler → rien d'écrit ;
//   3. sauvegarde « avant-import-zip » d'abord (documents/ compris : T187, T188) ; échec → arrêt, rien d'écrit ;
//   4. documents du ZIP écrits un par un par l'adaptateur, chacun relu depuis le ZIP et revérifié juste avant
//      (ZipLecture.lireDocument, seconde passe : un seul document décompressé à la fois) ; nom demandé : celui du
//      ZIP sans le préfixe « AAAAMMJJ-HHMMSS- » ; le nom rendu est gardé ; un document existant n'est jamais supprimé ni remplacé (mode dossier : repris s'il est
//      identique à l'octet, sinon nom suivi de « -2 », « -3 »…) ; échec → arrêt, aucune table touchée ;
//   5. références réécrites avec les noms rendus (ZipDonnees.CHAMPS_DOCUMENTS et le paramètre rapports_mensuels) ;
//   6. chaque table du format courant remplacée : Donnees.csv.serialiser (protection des cellules, colonnes inconnues
//      du ZIP gardées), App.adaptateur.enregistrer avec la version fraîche (contrôle de version ; écritures refusées
//      en lecture seule) et { remplacerFichierAbime: true } (un fichier abîmé est remplacé : T200, l'import est l'une
//      des deux seules dérogations, avec la restauration) ; parametres.version_schema = format courant ; T213 : un CSV
//      que le ZIP marque abîmé (lu.abimes, accepté seulement à l'empreinte juste) est écrit avec les octets du ZIP,
//      tels quels, et sa date « abîmé depuis » (manifeste, sinon maintenant) va dans fichiers-abimes.json ; la
//      confirmation le dit (#abimes-import-zip) ;
//   7. une ligne de journal ; 8. fenêtre #import-zip-termine, puis rechargement de l'application.
//   Erreur pendant 5 à 7 : tables remises depuis la sauvegarde « avant-import-zip » (App.adaptateur.restaurer), fenêtre
//   #import-zip-echec qui la nomme. acces/ (comptes, sessions, appareils) n'est jamais touché : rien ici n'y écrit.
// Dépendances : UI, App, Schema, Formats, Donnees, ZipLecture, ZipDonnees, Parametres.

const ParametresZip = (() => {

  const MOTIF_SAUVEGARDE = 'avant-import-zip';
  const PREFIXE_HORODATAGE = /^[0-9]{8}-[0-9]{6}-/;    // préfixe que le serveur impose aux documents (audit F4)
  const LONGUEUR_NOM_MAX = 128;                         // nom demandé d'un document (MOTIF_NOM_DOCUMENT de serveur.py)
  const ESSAIS_DE_NOM = 20;
  const AVERTISSEMENT = 'Toutes les données actuelles seront remplacées ; une sauvegarde complète, documents compris, '
    + 'est faite juste avant ; les comptes et l\'accès ne sont pas touchés.';
  const RAISON_RESERVE = 'L\'import ZIP est réservé au responsable : il remplace toutes les données.';
  const RAISON_DEMO = 'Import ZIP indisponible en démo : rien n\'y est enregistré.';
  const PROBLEMES_MONTRES = 5;

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  function pluriel(nombre, singulier, plurielTexte) {
    return nombre + ' ' + (nombre > 1 ? (plurielTexte || singulier + 's') : singulier);
  }

  // Message d'une erreur sans point final (pour l'insérer au milieu d'une phrase).
  function sansPoint(erreur) {
    return String((erreur && erreur.message) || erreur || 'erreur inconnue').replace(/[\s.]+$/, '');
  }

  // Nom du fichier choisi, pour les messages et le journal : sans caractère de contrôle, 120 caractères au plus.
  function nomAffiche(nom) {
    const propre = texte(nom).replace(/[\u0000-\u001f\u007f-\u009f]+/g, ' ').replace(/\s+/g, ' ');
    return (propre.length > 120 ? propre.slice(0, 119) + '…' : propre) || 'fichier sans nom';
  }

  function libelleTable(nomTable) {
    const description = Schema.table(nomTable);
    return description ? description.libelle : nomTable;
  }

  // Date et heure locales « AAAA-MM-JJTHH:MM:SS » (fichiers-abimes.json, comme les manifestes).
  function dateHeure(date) {
    const deux = (nombre) => String(nombre).padStart(2, '0');
    return date.getFullYear() + '-' + deux(date.getMonth() + 1) + '-' + deux(date.getDate()) + 'T'
      + deux(date.getHours()) + ':' + deux(date.getMinutes()) + ':' + deux(date.getSeconds());
  }

  // ===========================================================================================
  // 1. Droits et bouton
  // ===========================================================================================

  /** { visible, permis, raison } : le bouton est-il montré, l'import permis, sinon pourquoi (phrase à montrer). */
  function etat() {
    if (!ZipDonnees.exportPermis().permis) return { visible: false, permis: false, raison: RAISON_RESERVE };
    if (App.mode === 'demo') return { visible: true, permis: false, raison: RAISON_DEMO };
    if (Donnees.lectureSeule()) {
      const format = Donnees.etatDuFormat().base;
      return { visible: true, permis: false,
        raison: 'Import ZIP refusé. ' + new Donnees.ErreurLectureSeule(format).message };
    }
    return { visible: true, permis: true, raison: '' };
  }

  /** Bloc de la carte « Sauvegardes » (fragment UI.html ; '' pour un rôle qui n'a pas l'import). */
  function bloc() {
    if (!etat().visible) return '';
    return UI.html`<div class="import-zip" id="zone-import-zip">
      <p class="note sauvegardes-explication">« Importer un ZIP… » remplace toutes les données par celles d'un ZIP
        exporté par Prévo (« Exporter en ZIP »), après confirmation et une sauvegarde complète faite juste avant.
        Les comptes et l'accès ne sont pas touchés.</p>
      ${App.mode === 'demo' ? UI.html`<p class="note" id="note-import-zip">${RAISON_DEMO}</p>` : ''}
      <div class="actions">
        <button type="button" class="btn btn-secondaire" id="btn-import-zip">${UI.icone('document')}Importer un ZIP…</button>
        <input type="file" id="fichier-import-zip" accept=".zip,application/zip" hidden>
      </div>
    </div>`;
  }

  /** Branche le bouton (pendant : outil de parametres.js qui désactive le bouton et signale une erreur). */
  function brancher(conteneur, pendant) {
    const bouton = UI.$('#btn-import-zip', conteneur);
    const champ = UI.$('#fichier-import-zip', conteneur);
    if (!bouton || !champ) return;
    if (App.mode === 'demo') {
      bouton.disabled = true;
      bouton.title = RAISON_DEMO;
      return;
    }
    bouton.addEventListener('click', () => {
      const droit = etat();
      if (droit.permis) champ.click();
      else pendant(bouton, 'import ZIP', () => montrerMessage('import-zip-refus', 'Import ZIP refusé', 'important', droit.raison));
    });
    champ.addEventListener('change', () => {
      const fichier = champ.files && champ.files[0];
      champ.value = '';
      if (fichier) pendant(bouton, 'import ZIP', () => importer(fichier));
    });
  }

  // Fenêtre d'information (refus, échec, fin) : un bandeau dans un bloc #id, bouton « Fermer » ou ceux donnés.
  function montrerMessage(id, titre, type, message, boutons) {
    const contenu = UI.element(UI.html`<div class="form-colonne" id="${id}"></div>`);
    contenu.appendChild(UI.bandeau(type, message));
    return UI.fenetre({ titre: titre, contenu: contenu, boutons: boutons });
  }

  // ===========================================================================================
  // 2. Confirmation
  // ===========================================================================================

  // Origine du ZIP d'après son manifeste (contenu non garanti : seules des chaînes courtes sont montrées).
  function origine(manifeste) {
    if (!manifeste) {
      return 'ZIP sans manifeste (export d\'une version plus ancienne de Prévo) : date et version de l\'export inconnues.';
    }
    const court = (valeur) => (typeof valeur === 'string' ? texte(valeur).slice(0, 40) : '');
    const date = court(manifeste.date);
    const jour = /^\d{4}-\d{2}-\d{2}/.test(date) ? UI.dateFr(date.slice(0, 10)) + (date.length >= 16 ? ' à ' + date.slice(11, 16) : '') : '';
    const version = court(manifeste.version_appli);
    return 'Exporté ' + (jour ? 'le ' + jour : '(date inconnue)') + ' par Prévo ' + (version || '(version inconnue)')
      + (court(manifeste.mode) ? ' (mode ' + court(manifeste.mode) + ')' : '') + '.';
  }

  function texteFormat(lu) {
    return 'Format des données : ' + lu.formatOrigine + (lu.migre
      ? ' ; elles seront mises au format ' + lu.format + ' (format de cette version) à l\'import.'
      : ' (format de cette version).');
  }

  function tableauTables(lu) {
    const lignes = Schema.nomsTables().map((nomTable) => ({
      table: nomTable,
      actuel: Donnees.lignes(nomTable).length,
      importe: lu.tables[nomTable].lignes.length,
      videe: lu.absentes.includes(nomTable),
      abime: lu.abimes.some((abime) => abime.table === nomTable),
    }));
    return UI.tableau({
      libelle: 'Tables remplacées',
      colonnes: [
        { cle: 'table', libelle: 'Table', valeurTri: (l) => libelleTable(l.table),
          rendu: (l) => UI.html`${libelleTable(l.table)} <span class="note">${Schema.table(l.table).fichier}</span>` },
        { cle: 'actuel', libelle: 'Lignes actuelles', type: 'nombre', valeurTri: (l) => l.actuel,
          rendu: (l) => UI.html`<span data-actuel="${l.table}">${String(l.actuel)}</span>` },
        { cle: 'importe', libelle: 'Lignes après l\'import', type: 'nombre', valeurTri: (l) => l.importe,
          rendu: (l) => UI.html`<span data-importe="${l.table}">${String(l.importe)}</span>${l.videe
            ? UI.html` <span class="badge attention" data-videe="${l.table}">vidée</span>` : ''}${l.abime
            ? UI.html` <span class="badge attention" data-tel-quel="${l.table}">abîmé, tel quel</span>` : ''}` },
      ],
      lignes: lignes,
    });
  }

  // Points relevés à la lecture (documents manquants à l'export, valeurs illisibles…), sauf les tables absentes,
  // déjà dites ; les PROBLEMES_MONTRES premiers.
  function problemesMontres(lu) {
    const retenus = lu.problemes.filter((probleme) => probleme.type !== 'table' && probleme.gravite !== 'info');
    if (!retenus.length) return '';
    const autres = retenus.length > PROBLEMES_MONTRES ? retenus.length - PROBLEMES_MONTRES : 0;
    return UI.html`<div class="encadre" id="problemes-import-zip"><b>Points relevés à la lecture du ZIP :</b>
      <ul>${retenus.slice(0, PROBLEMES_MONTRES).map((probleme) => UI.html`<li>${probleme.message}</li>`)}</ul>
      ${autres ? UI.html`<p class="note">… et ${pluriel(autres, 'autre')}.</p>` : ''}</div>`;
  }

  // T213 : phrase d'un CSV que le ZIP marque abîmé (ZipLecture, `abimes`) : importé tel quel, bandeau gardé.
  function phraseAbime(abime) {
    const depuis = abime.depuis ? ' (abîmé depuis le ' + UI.dateFr(abime.depuis.slice(0, 10)) + ')' : '';
    return abime.fichier + ' est abîmé dans ce ZIP' + depuis + ' : il sera importé tel quel, sans réparation ; la '
      + 'base retrouvera le même état, avec le bandeau « Fichier abîmé ». Réparez-le ensuite, ou restaurez une '
      + 'sauvegarde.';
  }

  /** Fenêtre de confirmation ; true si l'utilisateur confirme le remplacement. */
  async function confirmer(lu, nomFichier) {
    const videes = lu.absentes.map((nomTable) => libelleTable(nomTable) + ' (' + Schema.table(nomTable).fichier + ')');
    const contenu = UI.element(UI.html`<div class="form-colonne" id="confirmation-import-zip"
        data-format="${String(lu.formatOrigine)}" data-migre="${lu.migre ? '1' : '0'}" data-documents="${String(lu.documents.length)}">
      <p>Fichier <b>${nomFichier}</b>. <span id="origine-import-zip">${origine(lu.manifeste)}</span></p>
      <p id="format-import-zip">${texteFormat(lu)}</p>
      <div id="zone-tables-import-zip"></div>
      ${videes.length ? UI.html`<div class="encadre attention" id="tables-videes-import-zip"><b>${pluriel(videes.length,
        'table absente du ZIP sera vidée', 'tables absentes du ZIP seront vidées')} :</b> ${videes.join(', ')}.</div>` : ''}
      <p id="documents-import-zip">${lu.documents.length
        ? pluriel(lu.documents.length, 'document joint', 'documents joints') + ' (photos, notices, rapports figés) '
          + (lu.documents.length > 1 ? 'seront ajoutés' : 'sera ajouté') + ' au dossier des documents ; les documents '
          + 'déjà présents sont gardés.'
        : 'Aucun document joint dans ce ZIP ; les documents déjà présents sont gardés.'}</p>
      ${lu.abimes.length ? UI.html`<div class="encadre attention" id="abimes-import-zip">${lu.abimes.map((abime) =>
        UI.html`<p data-abime="${abime.table}">${phraseAbime(abime)}</p>`)}</div>` : ''}
      ${problemesMontres(lu)}
      <div class="encadre attention" id="avertissement-import-zip"><b>${AVERTISSEMENT}</b></div>
    </div>`);
    UI.$('#zone-tables-import-zip', contenu).appendChild(tableauTables(lu));
    const reponse = await UI.fenetre({
      titre: 'Importer un ZIP',
      contenu: contenu,
      classe: 'large',
      boutons: [
        { libelle: 'Annuler', valeur: null, classe: 'btn-fantome', defaut: true },
        { libelle: 'Remplacer toutes les données', valeur: 'importer', classe: 'btn-danger' },
      ],
    });
    return reponse === 'importer';
  }

  // ===========================================================================================
  // 3. Documents et références
  // ===========================================================================================

  // Nom demandé à l'adaptateur : celui du ZIP sans le préfixe d'horodatage du serveur (s'il reste un nom admis).
  function nomDemande(nom) {
    const sansPrefixe = nom.replace(PREFIXE_HORODATAGE, '');
    return sansPrefixe !== nom && ZipLecture.nomDocumentAdmis(sansPrefixe) ? sansPrefixe : nom;
  }

  // « notice.pdf », 3 → « notice-3.pdf » (base raccourcie pour rester sous LONGUEUR_NOM_MAX).
  function avecRang(nom, rang) {
    const point = nom.lastIndexOf('.');
    const extension = point > 0 ? nom.slice(point) : '';
    const suffixe = '-' + rang;
    const base = (point > 0 ? nom.slice(0, point) : nom).slice(0, LONGUEUR_NOM_MAX - extension.length - suffixe.length);
    return base + suffixe + extension;
  }

  function estNomPris(erreur) {
    return erreur instanceof Donnees.ErreurStockage && /existe déjà|porte déjà ce nom/.test(erreur.message);
  }

  async function memesOctets(blob, octets) {
    if (!blob || blob.size !== octets.length) return false;
    const lus = new Uint8Array(await blob.arrayBuffer());
    for (let i = 0; i < lus.length; i += 1) { if (lus[i] !== octets[i]) return false; }
    return true;
  }

  // Document déjà présent sous ce nom : en mode serveur, jamais (le serveur impose un nom neuf, horodaté) ; ailleurs,
  // le nom est gardé tel quel et l'adaptateur refuserait d'écraser : on lit ce qui est là.
  async function documentPresent(nom) {
    if (App.mode === 'serveur') return null;
    return App.adaptateur.lireDocument(nom);
  }

  // Écrit un document du ZIP → { nom: nom rendu, repris: vrai si un document identique était déjà là }.
  async function ecrireUnDocument(joint, pris) {
    const demande = nomDemande(joint.nom);
    for (let rang = 1; rang <= ESSAIS_DE_NOM; rang += 1) {
      const candidat = rang === 1 ? demande : avecRang(demande, rang);
      if (pris.has(candidat.toLowerCase())) continue;
      const present = await documentPresent(candidat);
      if (present && await memesOctets(present, joint.octets)) {
        pris.add(candidat.toLowerCase());
        return { nom: candidat, repris: true };
      }
      if (present) continue;
      try {
        const nom = await App.adaptateur.ecrireDocument(candidat, new Blob([joint.octets]));
        pris.add(candidat.toLowerCase());
        return { nom: nom, repris: false };
      } catch (erreur) {
        if (!estNomPris(erreur)) {
          throw new Donnees.ErreurStockage('Le document « ' + joint.nom + ' » du ZIP n\'a pas pu être enregistré ('
            + sansPoint(erreur) + ')', erreur);
        }
      }
    }
    throw new Donnees.ErreurStockage('Aucun nom libre pour le document « ' + joint.nom + ' » du ZIP');
  }

  // Un document relu depuis le ZIP puis écrit, dans sa propre trame : une fois finie, plus rien ne garde ses octets
  // (une variable de la boucle de ecrireDocuments les garderait pendant la relecture du suivant).
  async function ecrireDepuisLeZip(lu, nom, pris) {
    return ecrireUnDocument({ nom: nom, octets: await ZipLecture.lireDocument(lu, nom) }, pris);
  }

  /**
   * Écrit les documents du ZIP lu, dans son ordre → { parNom: Map(nom dans le ZIP → nom rendu), repris }. Seconde passe
   * de la lecture (T205) : chaque document est décompressé à nouveau depuis le ZIP, son empreinte revérifiée
   * (ZipLecture.lireDocument ; refus → échec de l'import, avant les tables), écrit, puis oublié avant le suivant.
   */
  async function ecrireDocuments(lu) {
    const parNom = new Map();
    const pris = new Set();
    let repris = 0;
    for (const decrit of lu.documents) {
      const resultat = await ecrireDepuisLeZip(lu, decrit.nom, pris);
      parNom.set(decrit.nom, resultat.nom);
      if (resultat.repris) repris += 1;
    }
    return { parNom: parNom, repris: repris };
  }

  /**
   * Tables à écrire : copies des tables lues, références aux documents réécrites (noms rendus), version_schema au
   * format courant → { <table>: { lignes, colonnesInconnues } } pour chaque table du schéma.
   */
  function tablesImportees(tables, parNom) {
    const renommer = (valeur) => (parNom.has(texte(valeur)) ? parNom.get(texte(valeur)) : valeur);
    const resultat = {};
    Schema.nomsTables().forEach((nomTable) => {
      const table = tables[nomTable];
      resultat[nomTable] = { lignes: table.lignes.map((ligne) => Object.assign({}, ligne)),
        colonnesInconnues: (table.colonnesInconnues || []).slice() };
    });
    ZipDonnees.CHAMPS_DOCUMENTS.forEach(([nomTable, nomChamp]) => {
      resultat[nomTable].lignes.forEach((ligne) => { ligne[nomChamp] = renommer(ligne[nomChamp]); });
    });
    const parametres = resultat.parametres.lignes;
    const rapports = parametres.find((ligne) => ligne.cle === 'rapports_mensuels');
    if (rapports) {
      const noms = texte(rapports.valeur).split(',').map(texte).filter(Boolean);
      if (noms.some((nom) => parNom.has(nom))) rapports.valeur = noms.map(renommer).join(',');
    }
    const version = parametres.find((ligne) => ligne.cle === 'version_schema');
    if (version) version.valeur = String(Formats.courant);
    else parametres.push({ cle: 'version_schema', valeur: String(Formats.courant) });
    return resultat;
  }

  // ===========================================================================================
  // 4. Écriture et retour en arrière
  // ===========================================================================================

  // Remplace une table : octets du chemin habituel (Donnees.csv.serialiser : protection des cellules, en-tête du
  // format courant puis colonnes inconnues), écrits par l'adaptateur avec la version FRAÎCHE (rien n'est écrasé sans
  // contrôle de version ; lecture seule : refusé), puis relus (cache juste : le journal s'y ajoute ensuite). Un fichier
  // abîmé est remplacé (dérogation de l'import ZIP, T200 : remplacerFichierAbime ; sans elle, ErreurFichierAbime).
  // T213 : un CSV que le ZIP marque abîmé (`abime`, de lu.abimes) est écrit avec les octets du ZIP, tels quels (ni
  // re-sérialisation, ni migration, ni réparation) ; abimeDepuis : la date du manifeste, sinon maintenant (gardée dans
  // fichiers-abimes.json par l'adaptateur : le bandeau « Fichier abîmé » dit toujours depuis quand).
  async function remplacerTable(nomTable, table, abime) {
    const octets = abime ? abime.octets : Donnees.csv.serialiser(nomTable, table.lignes, table.colonnesInconnues);
    const options = { remplacerFichierAbime: true };
    if (abime) options.abimeDepuis = abime.depuis || dateHeure(new Date());
    await Donnees.rechargerTable(nomTable);
    await App.adaptateur.enregistrer(nomTable, octets, Donnees.version(nomTable), options);
    await Donnees.rechargerTable(nomTable);
  }

  function annoncerRechargement() {
    Donnees.evenements.dispatchEvent(new CustomEvent('changement', {
      detail: { tables: Schema.nomsTables(), origine: 'local' },
    }));
  }

  // Tables qu'une restauration ne remet pas (absentes de la sauvegarde : elles n'existaient pas avant l'import) :
  // vidées, pour revenir à « table absente = vide ».
  async function viderHorsSauvegarde(restaurees) {
    for (const nomTable of Schema.nomsTables()) {
      if (restaurees.includes(nomTable) || !Donnees.lignes(nomTable).length) continue;
      await remplacerTable(nomTable, { lignes: [], colonnesInconnues: [] });
    }
  }

  // Erreur pendant les étapes 5 à 7 : tables remises depuis la sauvegarde faite juste avant ; message qui la nomme.
  async function restaurerApresEchec(sauvegarde, erreur) {
    console.warn('Prévo : import ZIP interrompu (' + sansPoint(erreur) + ').', erreur);
    let message;
    try {
      const resultat = await App.adaptateur.restaurer(sauvegarde);
      await Donnees.chargerTout();
      await viderHorsSauvegarde(resultat.restaurees || []);
      message = 'L\'import ZIP a échoué (' + sansPoint(erreur) + '). Les tables ont été remises dans leur état '
        + 'd\'avant, depuis la sauvegarde « ' + sauvegarde + ' » faite juste avant l\'import ; l\'état interrompu est '
        + 'gardé dans la copie de sécurité « ' + resultat.copieSecurite + ' ». Les documents déjà copiés restent dans '
        + 'le dossier des documents.';
    } catch (erreurRestauration) {
      console.warn('Prévo : restauration après l\'import ZIP impossible (' + sansPoint(erreurRestauration) + ').',
        erreurRestauration);
      message = 'L\'import ZIP a échoué (' + sansPoint(erreur) + ') et la remise automatique des tables n\'a pas '
        + 'abouti (' + sansPoint(erreurRestauration) + '). Restaurez la sauvegarde « ' + sauvegarde + ' » : Paramètres '
        + '› Sauvegardes, « Restaurer… », toutes les tables.';
    }
    try { await Donnees.chargerTout(); } catch (erreurLecture) { /* l'écran dira ce qu'il peut lire */ }
    annoncerRechargement();
    await montrerMessage('import-zip-echec', 'Import ZIP interrompu', 'important', message);
    return { ok: false, sauvegarde: sauvegarde, message: message };
  }

  function arretAvantLesTables(message) {
    return montrerMessage('import-zip-echec', 'Import ZIP interrompu', 'important', message)
      .then(() => ({ ok: false, sauvegarde: null, message: message }));
  }

  // Étapes 3 à 7 (voir l'en-tête) → { ok, sauvegarde, message }. Aucune exception pour un échec prévu : il est dit.
  async function executer(lu, nomFichier) {
    let sauvegarde = null;
    try {
      sauvegarde = await App.adaptateur.sauvegarder(MOTIF_SAUVEGARDE);
      if (!sauvegarde) throw new Error('le stockage n\'a pas confirmé la sauvegarde');
    } catch (erreur) {
      return arretAvantLesTables('Sauvegarde avant l\'import impossible (' + sansPoint(erreur) + ') : rien n\'a été '
        + 'importé, aucune donnée n\'a changé.');
    }
    let documents;
    try {
      documents = await ecrireDocuments(lu);
    } catch (erreur) {
      return arretAvantLesTables(sansPoint(erreur) + '. Import arrêté avant de toucher aux tables : aucune donnée n\'a '
        + 'changé (sauvegarde « ' + sauvegarde + ' » faite juste avant). Les documents déjà copiés restent dans le '
        + 'dossier des documents.');
    }
    const nomsTables = Schema.nomsTables();
    try {
      const tables = tablesImportees(lu.tables, documents.parNom);
      const abimes = new Map(lu.abimes.map((abime) => [abime.table, abime]));
      for (const nomTable of nomsTables) await remplacerTable(nomTable, tables[nomTable], abimes.get(nomTable));
      const ligne = 'import ZIP : ' + nomFichier + ', ' + pluriel(nomsTables.length, 'table') + ', '
        + pluriel(lu.documents.length, 'document') + (abimes.size ? ' ; importés tels quels, abîmés : '
          + lu.abimes.map((abime) => abime.fichier).join(', ') : '') + ' ; sauvegarde ' + sauvegarde + ' faite juste avant';
      // Un journal abîmé importé tel quel ne reçoit pas cette ligne : il doit rester identique à l'octet (T213).
      if (!abimes.has('journal') && !(await Donnees.journaliser('parametres', '', ligne))) {
        throw new Donnees.ErreurStockage('la ligne du journal n\'a pas pu être écrite');
      }
    } catch (erreur) {
      return restaurerApresEchec(sauvegarde, erreur);
    }
    return { ok: true, sauvegarde: sauvegarde, tables: nomsTables.length, documents: lu.documents.length,
      repris: documents.repris, abimes: lu.abimes.map((abime) => abime.fichier) };
  }

  // ===========================================================================================
  // 5. Import complet
  // ===========================================================================================

  /**
   * Import d'un ZIP choisi (File ou Blob) : contrôle, confirmation, écriture (voir l'en-tête) → Promise de
   * { ok, etape: 'refus' | 'annule' | 'ecriture' | 'fait', sauvegarde?, message? }. Recharge l'application après un
   * import réussi.
   */
  async function importer(fichier) {
    const droit = etat();
    if (!droit.permis) {
      await montrerMessage('import-zip-refus', 'Import ZIP refusé', 'important', droit.raison);
      return { ok: false, etape: 'refus', message: droit.raison };
    }
    const nomFichier = nomAffiche(fichier && fichier.name);
    const lu = await ZipLecture.lire(fichier);
    if (!lu.ok) {
      const message = lu.refus + ' Rien n\'a été écrit.';
      await montrerMessage('import-zip-refus', 'Import ZIP refusé', 'important', message);
      return { ok: false, etape: 'refus', message: message };
    }
    try {
      await Donnees.rafraichir();                          // nombres de lignes actuels à jour
    } catch (erreur) {
      console.warn('Prévo : rafraîchissement avant l\'import ZIP impossible (' + sansPoint(erreur) + ').', erreur);
    }
    if (!(await confirmer(lu, nomFichier))) {
      UI.toast('Import ZIP annulé : rien n\'a été écrit.', 'info');
      return { ok: false, etape: 'annule' };
    }
    UI.toast('Import ZIP en cours : sauvegarde, documents, puis tables…', 'info');
    Donnees.arreterSurveillance();                         // aucune relecture au milieu des écritures
    let resultat;
    try {
      resultat = await executer(lu, nomFichier);
    } finally {
      if (!resultat || !resultat.ok) Donnees.demarrerSurveillance();
    }
    if (!resultat.ok) {
      await App.reafficher();
      return Object.assign({ etape: 'ecriture' }, resultat);
    }
    const message = 'Import ZIP terminé : ' + pluriel(resultat.tables, 'table remplacée', 'tables remplacées')
      + (resultat.abimes.length ? ' (dont ' + resultat.abimes.join(', ') + (resultat.abimes.length > 1
        ? ', abîmés, importés tels quels)' : ', abîmé, importé tel quel)') : '') + ', '
      + pluriel(resultat.documents, 'document') + ' (' + (resultat.repris ? resultat.repris + ' déjà présent(s), repris ; ' : '')
      + 'aucun document existant supprimé). Sauvegarde faite juste avant : « ' + resultat.sauvegarde + ' » (Paramètres '
      + '› Sauvegardes). Prévo va se recharger avec les nouvelles données.';
    await montrerMessage('import-zip-termine', 'Import ZIP terminé', 'succes', message,
      [{ libelle: 'Recharger Prévo', valeur: 'ok', classe: 'btn-primaire', defaut: true }]);
    location.reload();                                     // étape 8 : l'application repart des nouvelles données
    return Object.assign({ etape: 'fait', message: message }, resultat);
  }

  return { etat, bloc, brancher, importer, nomDemande, tablesImportees, AVERTISSEMENT };
})();

// Relais de parametres.js (bloc de la carte « Sauvegardes », branchement du bouton).
Object.assign(Parametres.interne, { blocImportZip: ParametresZip.bloc, brancherImportZip: ParametresZip.brancher });
