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
//   T214 : ZIP « données seules » (manifeste « documents »: « exclus », ZipDonnees) : tables remplacées comme
//      d'habitude, aucun document écrit, supprimé ni remplacé (le dossier des documents ne change pas) ; la
//      confirmation dit combien de documents déjà présents sont gardés et combien de documents cités manquent ici ;
//   2. confirmation #confirmation-import-zip : date et version du ZIP (manifeste), format (« mis au format N »), lignes
//      par table (actuel → importé), tables vidées (absentes du ZIP), nombre de documents, avertissement ;
//      Annuler → rien d'écrit ;
//   3. sauvegarde « avant-import-zip » d'abord (documents/ compris : T187, T188) ; échec → arrêt, rien d'écrit ;
//   4. documents du ZIP écrits un par un par l'adaptateur, chacun relu depuis le ZIP et revérifié juste avant
//      (ZipLecture.lireDocument, seconde passe : un seul document décompressé à la fois) ; nom demandé : celui du
//      ZIP sans le préfixe « AAAAMMJJ-HHMMSS- » ; le nom rendu est gardé ; un document existant n'est jamais supprimé ni remplacé (mode dossier : repris s'il est
//      identique à l'octet, sinon nom suivi de « -2 », « -3 »…) ; échec → arrêt, aucune table touchée ;
//   5. références réécrites avec les noms rendus (ZipDonnees.CHAMPS_DOCUMENTS et le paramètre rapports_mensuels) ;
//   T319 : les réglages de Paramètres que la base a et que le ZIP n'a pas (langue_defaut, devise…) gardent leur
//      valeur (reglagesGardes), dits à la confirmation (#reglages-gardes-import-zip) ;
//   6. chaque table du format courant remplacée : Donnees.csv.serialiser (protection des cellules, colonnes inconnues
//      du ZIP gardées), App.adaptateur.enregistrer avec la version fraîche (contrôle de version ; écritures refusées
//      en lecture seule) et { remplacerFichierAbime: true } (un fichier abîmé est remplacé : T200, l'import est l'une
//      des deux seules dérogations, avec la restauration) ; parametres.version_schema = format courant ; T213 : un CSV
//      que le ZIP marque abîmé (lu.abimes, accepté seulement à l'empreinte juste) est écrit avec les octets du ZIP,
//      tels quels, et sa date « abîmé depuis » (manifeste, sinon maintenant) va dans fichiers-abimes.json ; la
//      confirmation le dit (#abimes-import-zip) ;
//   T508 : avant la première table, le marqueur « import_zip_en_cours » (nom de la sauvegarde) est posé dans
//      parametres.csv, qui est remplacée en dernier, après la ligne de journal (voir poserMarqueur) ;
//   T508 : mode serveur avec comptes : la confirmation liste les comptes dont la fiche de technicien liée change de
//      personne ou disparaît avec l'import (#comptes-import-zip ; rien n'est écrit dans acces/, D172) ;
//   7. une ligne de journal ; 8. fenêtre #import-zip-termine, puis rechargement de l'application.
//   Erreur pendant 5 à 7 : tables remises depuis la sauvegarde « avant-import-zip » (App.adaptateur.restaurer), fenêtre
//   #import-zip-echec qui la nomme. acces/ (comptes, sessions, appareils) n'est jamais touché : rien ici n'y écrit.
// Dépendances : UI, App, Schema, Formats, Donnees, ZipLecture, ZipDonnees, Parametres.

const ParametresZip = (() => {

  const MOTIF_SAUVEGARDE = 'avant-import-zip';
  const PREFIXE_HORODATAGE = /^[0-9]{8}-[0-9]{6}-/;    // préfixe que le serveur impose aux documents (audit F4)
  const LONGUEUR_NOM_MAX = 128;                         // nom demandé d'un document (MOTIF_NOM_DOCUMENT de serveur.py)
  const ESSAIS_DE_NOM = 20;
  // Textes lus à l'affichage (fonctions), jamais figés au chargement du module.
  const avertissement = () => I18n.t('zip.avertissement.toutes_donnees_actuelles_seront');
  const raisonReserve = () => I18n.t('zip.raison_reserve.import_zip_reserve_responsable');
  const raisonDemo = () => I18n.t('zip.raison_demo.import_zip_indisponible_demo');
  const PROBLEMES_MONTRES = 5;

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  function pluriel(nombre, singulier, plurielTexte) {
    return nombre + ' ' + (nombre > 1 ? (plurielTexte || singulier + 's') : singulier);
  }

  // Message d'une erreur sans point final (pour l'insérer au milieu d'une phrase).
  function sansPoint(erreur) {
    return String((erreur && erreur.message) || erreur || I18n.t('commun.message.erreur_inconnue')).replace(/[\s.]+$/, '');
  }

  // Nom du fichier choisi, pour les messages et le journal : sans caractère de contrôle, 120 caractères au plus.
  // pourLesDonnees : le nom écrit au journal, dans la langue de l'installation (D156).
  function nomAffiche(nom, pourLesDonnees) {
    const propre = texte(nom).replace(/[\u0000-\u001f\u007f-\u009f]+/g, ' ').replace(/\s+/g, ' ');
    if (pourLesDonnees) return (propre.length > 120 ? I18n.donnees('zip.afficher.nom_tronque', { texte: propre.slice(0, 119) }) : propre) || I18n.donnees('zip.nom_affiche.fichier_sans_nom');
    return (propre.length > 120 ? I18n.t('zip.afficher.nom_tronque', { texte: propre.slice(0, 119) }) : propre) || I18n.t('zip.nom_affiche.fichier_sans_nom');
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
    if (!ZipDonnees.exportPermis().permis) return { visible: false, permis: false, raison: raisonReserve() };
    if (App.mode === 'demo') return { visible: true, permis: false, raison: raisonDemo() };
    if (Donnees.lectureSeule()) {
      const format = Donnees.etatDuFormat().base;
      return { visible: true, permis: false,
        raison: I18n.t('zip.etat.import_zip_refuse', { motif: new Donnees.ErreurLectureSeule(format).message }) };
    }
    return { visible: true, permis: true, raison: '' };
  }

  /** Bloc de la carte « Sauvegardes » (fragment UI.html ; '' pour un rôle qui n'a pas l'import). */
  function bloc() {
    if (!etat().visible) return '';
    return UI.html`<div class="import-zip" id="zone-import-zip">
      <p class="note sauvegardes-explication">${I18n.t('zip.bloc.importer_zip_remplace_toutes')}</p>
      ${App.mode === 'demo' ? UI.html`<p class="note" id="note-import-zip">${raisonDemo()}</p>` : ''}
      <div class="actions">
        <button type="button" class="btn btn-secondaire" id="btn-import-zip">${UI.icone('document')}${I18n.t('zip.bloc.importer_zip')}</button>
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
      bouton.title = raisonDemo();
      return;
    }
    bouton.addEventListener('click', () => {
      const droit = etat();
      if (droit.permis) champ.click();
      else pendant(bouton, 'import ZIP', () => montrerMessage('import-zip-refus', I18n.t('zip.brancher.import_zip_refuse'), 'important', droit.raison));
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
      return I18n.t('zip.origine.zip_sans_manifeste_export');
    }
    const court = (valeur) => (typeof valeur === 'string' ? texte(valeur).slice(0, 40) : '');
    const date = court(manifeste.date);
    const jour = /^\d{4}-\d{2}-\d{2}/.test(date) ? UI.dateFr(date.slice(0, 10)) + (date.length >= 16 ? ' ' + I18n.t('zip.origine.a_heure', { heure: date.slice(11, 16) }) : '') : '';
    const version = court(manifeste.version_appli);
    const mode = court(manifeste.mode);
    const par = version || I18n.t('zip.origine.version_inconnue');
    if (jour) {
      return mode ? I18n.t('zip.origine.exporte_prevo_mode', { jour, par, mode }) : I18n.t('zip.origine.exporte_prevo', { jour, par });
    }
    return mode ? I18n.t('zip.origine.exporte_date_inconnue_prevo', { par, mode }) : I18n.t('zip.origine.exporte_date_inconnue_prevo_2', { par });
  }

  function texteFormat(lu) {
    return I18n.t('zip.texte_format.format_donnees', { formatOrigine: lu.formatOrigine }) + (lu.migre
      ? ' ' + I18n.t('zip.texte_format.elles_seront_mises_format', { format: lu.format })
      : ' ' + I18n.t('zip.texte_format.format_version'));
  }

  function tableauTables(lu) {
    const lignes = Schema.nomsTables().map((nomTable) => ({
      table: nomTable,
      actuel: Donnees.lignes(nomTable).length,
      importe: lu.tables[nomTable].lignes.length + (nomTable === 'parametres' ? (lu.reglagesGardes || []).length : 0),
      videe: lu.absentes.includes(nomTable),
      abime: lu.abimes.some((abime) => abime.table === nomTable),
    }));
    return UI.tableau({
      libelle: I18n.t('zip.tableau_tables.tables_remplacees'),
      colonnes: [
        { cle: 'table', libelle: I18n.t('zip.tableau_tables.table'), valeurTri: (l) => libelleTable(l.table),
          rendu: (l) => UI.html`${libelleTable(l.table)} <span class="note">${Schema.table(l.table).fichier}</span>` },
        { cle: 'actuel', libelle: I18n.t('zip.tableau_tables.lignes_actuelles'), type: 'nombre', valeurTri: (l) => l.actuel,
          rendu: (l) => UI.html`<span data-actuel="${l.table}">${String(l.actuel)}</span>` },
        { cle: 'importe', libelle: I18n.t('zip.tableau_tables.lignes_apres_import'), type: 'nombre', valeurTri: (l) => l.importe,
          rendu: (l) => UI.html`<span data-importe="${l.table}">${String(l.importe)}</span>${l.videe
            ? UI.html` <span class="badge attention" data-videe="${l.table}">${I18n.t('zip.tableau_tables.videe')}</span>` : ''}${l.abime
            ? UI.html` <span class="badge attention" data-tel-quel="${l.table}">${I18n.t('zip.tableau_tables.abime_tel_quel')}</span>` : ''}` },
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
    return UI.html`<div class="encadre" id="problemes-import-zip"><b>${I18n.t('zip.problemes_montres.points_releves_lecture_zip')}</b>
      <ul>${retenus.slice(0, PROBLEMES_MONTRES).map((probleme) => UI.html`<li>${probleme.message}</li>`)}</ul>
      ${autres ? UI.html`<p class="note">${I18n.t('zip.problemes_montres.autres', { n: autres })}</p>` : ''}</div>`;
  }

  // T213 : phrase d'un CSV que le ZIP marque abîmé (ZipLecture, `abimes`) : importé tel quel, bandeau gardé.
  function phraseAbime(abime) {
    const depuis = abime.depuis ? ' ' + I18n.t('zip.phrase_abime.abime_depuis', { date: UI.dateFr(abime.depuis.slice(0, 10)) }) : '';
    return I18n.t('zip.phrase_abime.abime_zip_sera_importe', { fichier: abime.fichier, depuis });
  }

  // T214 : vrai pour un ZIP « données seules » (export sans les documents).
  function sansDocuments(lu) {
    return Boolean(lu.manifeste) && lu.manifeste.documents === 'exclus';
  }

  async function estPresent(nom) {
    if (!ZipDonnees.nomDocumentValide(nom)) return false;
    try { return Boolean(await App.adaptateur.lireDocument(nom)); } catch (erreur) { return false; }
  }

  // T214 : documents d'un import « données seules », pour la confirmation : { presents, cites, absents } = documents
  // cités par les données actuelles qui sont là (gardés tels quels), documents cités par les données importées, et
  // ceux-ci qui n'existent pas ici. Chacun n'est lu que pour savoir s'il est là, une fois. Un document là mais cité
  // par aucune donnée est gardé aussi, sans être compté (aucun adaptateur ne liste le dossier des documents).
  async function documentsHorsZip(lu) {
    const actuels = ZipDonnees.nomsDocuments();
    const importes = ZipDonnees.nomsDocuments(lu.tables);
    const presence = new Map();
    for (const nom of new Set(actuels.concat(importes))) presence.set(nom, await estPresent(nom));
    return { presents: actuels.filter((nom) => presence.get(nom)).length, cites: importes.length,
      absents: importes.filter((nom) => !presence.get(nom)).length };
  }

  function phraseSansDocuments(etat) {
    let presents = I18n.t('zip.phrase_sans_documents.aucun_document_supprime');
    if (etat.presents > 0) presents = I18n.t('zip.phrase_sans_documents.documents_deja_presents_sont', { n: etat.presents });
    let absents = I18n.t('zip.phrase_sans_documents.donnees_importees_citent_aucun');
    if (etat.absents > 0) absents = I18n.t('zip.phrase_sans_documents.documents_cites_donnees_importees', { n: etat.absents });
    else if (etat.cites) absents = I18n.t('zip.phrase_sans_documents.tous_documents_cites_donnees');
    return I18n.t('zip.phrase_sans_documents.zip_contient_pas_documents', { presents, absents });
  }

  /**
   * Fenêtre de confirmation ; true si l'utilisateur confirme le remplacement. horsZip : documentsHorsZip pour un ZIP
   * « données seules » (T214), sinon null.
   */
  async function confirmer(lu, nomFichier, horsZip) {
    const videes = lu.absentes.map((nomTable) => libelleTable(nomTable) + ' (' + Schema.table(nomTable).fichier + ')');
    const contenu = UI.element(UI.html`<div class="form-colonne" id="confirmation-import-zip"
        data-format="${String(lu.formatOrigine)}" data-migre="${lu.migre ? '1' : '0'}" data-documents="${String(lu.documents.length)}"
        data-sans-documents="${horsZip ? '1' : '0'}">
      <p>${I18n.html('zip.confirmer.fichier_nom_fichier_origine', { nomFichier, origine: origine(lu.manifeste) })}</p>
      <p id="format-import-zip">${texteFormat(lu)}</p>
      <div id="zone-tables-import-zip"></div>
      ${videes.length ? UI.html`<div class="encadre attention" id="tables-videes-import-zip"><b>${I18n.t('zip.confirmer.tables_absentes_zip_seront', { n: videes.length })} :</b> ${videes.join(', ')}.</div>` : ''}
      <p id="documents-import-zip">${horsZip ? phraseSansDocuments(horsZip) : lu.documents.length
        ? I18n.t('zip.confirmer.documents_joints_photos_notices', { n: lu.documents.length })
        : I18n.t('zip.confirmer.aucun_document_joint_zip')}</p>
      ${lu.abimes.length ? UI.html`<div class="encadre attention" id="abimes-import-zip">${lu.abimes.map((abime) =>
        UI.html`<p data-abime="${abime.table}">${phraseAbime(abime)}</p>`)}</div>` : ''}
      ${problemesMontres(lu)}
      ${lu.moiADemander ? UI.html`<p id="solo-moi-import-zip">${I18n.t('zip.confirmer.solo_moi_a_demander')}</p>` : ''}
      ${(lu.comptesTouches || []).length ? UI.html`<div class="encadre attention" id="comptes-import-zip">
        <b>${I18n.t('zip.confirmer.comptes_fiche_change', { n: lu.comptesTouches.length })} :</b>
        <ul>${lu.comptesTouches.map((lien) => UI.html`<li data-compte="${lien.compte}">${phraseCompte(lien)}</li>`)}</ul>
        <p>${I18n.t('zip.confirmer.comptes_a_corriger')}</p></div>` : ''}
      ${(lu.reglagesGardes || []).length ? UI.html`<p id="reglages-gardes-import-zip">${I18n.t('zip.confirmer.reglages_absents_gardes',
        { n: lu.reglagesGardes.length, reglages: lu.reglagesGardes.map((garde) => garde.libelle).join(', ') })}</p>` : ''}
      <div class="encadre attention" id="avertissement-import-zip"><b>${avertissement()}</b></div>
    </div>`);
    UI.$('#zone-tables-import-zip', contenu).appendChild(tableauTables(lu));
    const reponse = await UI.fenetre({
      titre: I18n.t('zip.confirmer.importer_zip'),
      contenu: contenu,
      classe: 'large',
      boutons: [
        { libelle: I18n.t('commun.bouton.annuler'), valeur: null, classe: 'btn-fantome', defaut: true },
        { libelle: I18n.t('zip.confirmer.remplacer_toutes_donnees'), valeur: 'importer', classe: 'btn-danger' },
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

  // Refus « nom déjà pris » de l'adaptateur, reconnu dans la langue de l'écran, celle où il l'écrit (T507, comme
  // documentExisteDeja de controles-ecritures.js, T413) : il n'a pas de code d'erreur pour ce cas.
  function estNomPris(erreur, nom) {
    return erreur instanceof Donnees.ErreurStockage
      && [I18n.t('socle.creer.document_existe_deja', { nom }), I18n.t('socle.creer.document_porte_deja_nom')].includes(erreur.message);
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
        if (!estNomPris(erreur, candidat)) {
          throw new Donnees.ErreurStockage(I18n.t('zip.ecrire_un_document.document_zip_pas_pu', { jointNom: joint.nom, sansPoint: sansPoint(erreur) }), erreur);
        }
      }
    }
    throw new Donnees.ErreurStockage(I18n.t('zip.ecrire_un_document.aucun_nom_libre_document', { jointNom: joint.nom }));
  }

  // Un document relu depuis le ZIP puis écrit, dans sa propre trame : une fois finie, plus rien ne garde ses octets
  // (une variable de la boucle de ecrireDocuments les garderait pendant la relecture du suivant).
  // T507 : en mode serveur, une image dont le contenu n'est pas celui que son nom annonce (le mode dossier l'accepte,
  // le serveur la refuse : 400) n'est pas envoyée : sautée ({ saute }), dite à la fin de l'import, qui continue.
  async function ecrireDepuisLeZip(lu, nom, pris) {
    const octets = await ZipLecture.lireDocument(lu, nom);
    if (App.mode === 'serveur' && ZipDonnees.imageRefusee(nom, octets)) return { saute: true };
    return ecrireUnDocument({ nom: nom, octets: octets }, pris);
  }

  /**
   * Écrit les documents du ZIP lu, dans son ordre → { parNom: Map(nom dans le ZIP → nom rendu), repris, sautes }. Seconde passe
   * de la lecture (T205) : chaque document est décompressé à nouveau depuis le ZIP, son empreinte revérifiée
   * (ZipLecture.lireDocument ; refus → échec de l'import, avant les tables), écrit, puis oublié avant le suivant.
   */
  async function ecrireDocuments(lu) {
    const parNom = new Map();
    const pris = new Set();
    const sautes = [];
    let repris = 0;
    for (const decrit of lu.documents) {
      const resultat = await ecrireDepuisLeZip(lu, decrit.nom, pris);
      if (resultat.saute) { sautes.push(decrit.nom); continue; }
      parNom.set(decrit.nom, resultat.nom);
      if (resultat.repris) repris += 1;
    }
    return { parNom: parNom, repris: repris, sautes: sautes };
  }

  /**
   * Tables à écrire : copies des tables lues, références aux documents réécrites (noms rendus), version_schema au
   * format courant → { <table>: { lignes, colonnesInconnues } } pour chaque table du schéma.
   */
  function tablesImportees(tables, parNom, gardes) {
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
    // T508 : le marqueur « import en cours » qu'un ZIP porterait (base restée interrompue) n'est jamais importé.
    resultat.parametres.lignes = resultat.parametres.lignes.filter((ligne) => texte(ligne.cle) !== Donnees.CLE_IMPORT_ZIP_EN_COURS);
    const parametres = resultat.parametres.lignes;
    const rapports = parametres.find((ligne) => ligne.cle === 'rapports_mensuels');
    if (rapports) {
      const noms = texte(rapports.valeur).split(',').map(texte).filter(Boolean);
      if (noms.some((nom) => parNom.has(nom))) rapports.valeur = noms.map(renommer).join(',');
    }
    const version = parametres.find((ligne) => ligne.cle === 'version_schema');
    if (version) version.valeur = String(Formats.courant);
    else parametres.push({ cle: 'version_schema', valeur: String(Formats.courant) });
    (gardes || []).forEach((garde) => parametres.push({ cle: garde.cle, valeur: garde.valeur }));
    return resultat;
  }

  /**
   * T319 (Nicolas, 07/11) : les réglages de Paramètres (Parametres.reglagesConnus : formulaire et mode Solo) que la
   * base a et que le ZIP n'a pas (export 1.2, bêta 1 ou bêta 2, démo : langue_defaut, devise, réglages de la 2.0…)
   * gardent la valeur de la base → [{ cle, valeur, libelle }], dans l'ordre de la base. Le reste de parametres.csv
   * (rapports_mensuels, clés inconnues…) suit le ZIP : remplacement complet (D172).
   */
  /** Prénom et nom d'une fiche de technicien, ramenés pour une comparaison (UI.normaliserRecherche : casse,
   *  accents, İ/ı). */
  function formeDuTechnicien(technicien) {
    return UI.normaliserRecherche(String(technicien.prenom || '').trim() + ' ' + String(technicien.nom || '').trim())
      .replace(/\s+/g, ' ').trim();
  }

  /**
   * T323 (Nicolas, 07/11) : mode Solo gardé de la base (T319) : son technicien « moi » (solo_technicien_id) ne vaut
   * après l'import que s'il désigne clairement UNE fiche du ZIP au même prénom et au même nom que la fiche « moi » de
   * la base (sous le même identifiant, ou sous un autre : il suit alors la fiche). Sinon (aucune, plusieurs, fiche
   * « moi » introuvable dans la base), il est vidé et Prévo demandera une fois au responsable qui est « moi », au lieu
   * de deviner (Parametres.interne.demanderMoiSolo). Rend vrai quand il faudra demander.
   */
  function moiSoloApresImport(gardes, techniciensDuZip) {
    const garde = gardes.find((candidat) => candidat.cle === 'solo_technicien_id');
    if (!garde || !texte(garde.valeur)) return false;
    const moi = Donnees.trouver('techniciens', texte(garde.valeur));
    const forme = moi ? formeDuTechnicien(moi) : '';
    const memes = forme ? techniciensDuZip.filter((technicien) => formeDuTechnicien(technicien) === forme) : [];
    garde.valeur = memes.length === 1 ? texte(memes[0].id) : '';
    return memes.length !== 1;
  }

  /**
   * T508 (relecture R3 ; D172 : acces/ n'est jamais écrit par l'import, on prévient seulement) : mode serveur avec
   * comptes ; comptes dont la fiche de technicien liée (technicien_id) désignera, après l'import, une autre personne
   * (prénom et nom, règle de T323) ou plus personne → [{ compte, id, avant, apres }] (prénom et nom ; '' : pas de
   * fiche). Lus par la route de l'écran Équipe › Accès ; lecture impossible : [] (l'import n'en dépend pas).
   */
  async function comptesDontLaFicheChange(techniciensDuZip) {
    if (App.mode !== 'serveur' || !App.comptesExiges() || typeof EquipeAcces === 'undefined') return [];
    let comptes = [];
    try {
      comptes = (await EquipeAcces.api.comptes()).comptes;
    } catch (erreur) {
      console.warn('Prévo : comptes illisibles avant l\'import ZIP (' + sansPoint(erreur) + ').', erreur);
    }
    const nomDe = (fiche) => (fiche ? (texte(fiche.prenom) + ' ' + texte(fiche.nom)).trim() || texte(fiche.id) : '');
    return (Array.isArray(comptes) ? comptes : []).filter((compte) => texte(compte.technicien_id)).map((compte) => {
      const id = texte(compte.technicien_id);
      const avant = Donnees.trouver('techniciens', id);
      const apres = techniciensDuZip.find((technicien) => texte(technicien.id) === id);
      return { compte: texte(compte.identifiant), id: id, avant: nomDe(avant), apres: nomDe(apres),
        meme: Boolean(avant && apres) && formeDuTechnicien(avant) === formeDuTechnicien(apres) };
    }).filter((lien) => !lien.meme && Boolean(lien.avant || lien.apres));
  }

  function phraseCompte(lien) {
    if (!lien.apres) return I18n.t('zip.confirmer.compte_fiche_absente', lien);
    return I18n.t(lien.avant ? 'zip.confirmer.compte_autre_personne' : 'zip.confirmer.compte_fiche_nouvelle', lien);
  }

  function reglagesGardes(lignesDuZip) {
    const connus = typeof Parametres !== 'undefined' && Parametres.reglagesConnus ? Parametres.reglagesConnus() : [];
    const libelles = new Map(connus.map((reglage) => [reglage.cle, reglage]));
    const vues = new Set(lignesDuZip.map((ligne) => texte(ligne.cle)));
    const gardes = [];
    Donnees.lignes('parametres').forEach((ligne) => {
      const cle = texte(ligne.cle);
      if (!libelles.has(cle) || vues.has(cle)) return;
      vues.add(cle);                                     // une clé en double dans la base : la première seulement
      gardes.push({ cle: cle, valeur: ligne.valeur, libelle: libelles.get(cle).libelle || cle });
    });
    return gardes;
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
      message = I18n.t('zip.restaurer_apres_echec.echec_tables_remises', { sansPoint: sansPoint(erreur), sauvegarde, copieSecurite: resultat.copieSecurite });
    } catch (erreurRestauration) {
      console.warn('Prévo : restauration après l\'import ZIP impossible (' + sansPoint(erreurRestauration) + ').',
        erreurRestauration);
      message = I18n.t('zip.restaurer_apres_echec.echec_puis_remise_impossible', { erreur: sansPoint(erreur), erreurRestauration: sansPoint(erreurRestauration), sauvegarde });
    }
    try { await Donnees.chargerTout(); } catch (erreurLecture) { /* l'écran dira ce qu'il peut lire */ }
    annoncerRechargement();
    await montrerMessage('import-zip-echec', I18n.t('zip.restaurer_apres_echec.import_zip_interrompu'), 'important', message);
    return { ok: false, sauvegarde: sauvegarde, message: message };
  }

  function arretAvantLesTables(message) {
    return montrerMessage('import-zip-echec', I18n.t('zip.restaurer_apres_echec.import_zip_interrompu'), 'important', message)
      .then(() => ({ ok: false, sauvegarde: null, message: message }));
  }

  // T508 : marqueur « import en cours » (Donnees.CLE_IMPORT_ZIP_EN_COURS = nom de la sauvegarde d'avant l'import),
  // écrit dans parametres.csv avant la première table remplacée. Il n'y a pas de transaction (D172) : si l'onglet est
  // fermé ou le poste coupé pendant les écritures, il reste, et l'ouverture suivante le dit (App, bandeau « import
  // interrompu »). parametres est remplacée EN DERNIER, par les lignes du ZIP, sans lui : la dernière écriture d'un
  // import réussi le retire ; un retour en arrière réussi aussi (la sauvegarde d'avant l'import ne le porte pas).
  function poserMarqueur(sauvegarde) {
    const cle = Donnees.CLE_IMPORT_ZIP_EN_COURS;
    return Donnees.modifier('parametres', (lignes) => {
      const ligne = lignes.find((candidate) => candidate.cle === cle);
      if (ligne) ligne.valeur = sauvegarde;
      else lignes.push({ cle: cle, valeur: sauvegarde });
    }, { journal: false, remplacerFichierAbime: true });
  }

  // Étapes 3 à 7 (voir l'en-tête) → { ok, sauvegarde, message }. Aucune exception pour un échec prévu : il est dit.
  async function executer(lu, nomFichier) {
    let sauvegarde = null;
    try {
      sauvegarde = await App.adaptateur.sauvegarder(MOTIF_SAUVEGARDE);
      if (!sauvegarde) throw new Error(I18n.t('zip.executer.stockage_pas_confirme_sauvegarde'));
    } catch (erreur) {
      return arretAvantLesTables(I18n.t('zip.executer.sauvegarde_avant_import_impossible', { sansPoint: sansPoint(erreur) }));
    }
    let documents;
    try {
      documents = await ecrireDocuments(lu);
    } catch (erreur) {
      return arretAvantLesTables(I18n.t('zip.executer.import_arrete_avant_toucher', { sansPoint: sansPoint(erreur), sauvegarde }));
    }
    const nomsTables = Schema.nomsTables().filter((nomTable) => nomTable !== 'parametres');     // parametres : en dernier (T508)
    try {
      await poserMarqueur(sauvegarde);
    } catch (erreur) {
      return arretAvantLesTables(I18n.t('zip.executer.import_arrete_avant_toucher', { sansPoint: sansPoint(erreur), sauvegarde }));
    }
    try {
      const tables = tablesImportees(lu.tables, documents.parNom, lu.reglagesGardes);
      const abimes = new Map(lu.abimes.map((abime) => [abime.table, abime]));
      for (const nomTable of nomsTables) await remplacerTable(nomTable, tables[nomTable], abimes.get(nomTable));
      nomsTables.push('parametres');
      const action = 'import ZIP : ' + nomFichier + ', ' + pluriel(nomsTables.length, 'table') + ', '
        + pluriel(lu.documents.length - documents.sautes.length, 'document')
        + (documents.sautes.length ? ' ; non repris (contenu qui n\'est pas l\'image annoncée) : ' + documents.sautes.join(', ') : '') + (abimes.size ? ' ; importés tels quels, abîmés : '
          + lu.abimes.map((abime) => abime.fichier).join(', ') : '')
        + (sansDocuments(lu) ? ' ; données seules : documents gardés tels quels' : '')
        + ' ; sauvegarde ' + sauvegarde + ' faite juste avant';
      // Un journal abîmé importé tel quel ne reçoit pas cette ligne : il doit rester identique à l'octet (T213).
      if (!abimes.has('journal') && !(await Donnees.journaliser('parametres', '', action))) {
        throw new Donnees.ErreurStockage(I18n.t('zip.executer.ligne_journal_pas_pu'));
      }
      await remplacerTable('parametres', tables.parametres, abimes.get('parametres'));     // dernière écriture : marqueur retiré
    } catch (erreur) {
      return restaurerApresEchec(sauvegarde, erreur);
    }
    return { ok: true, sauvegarde: sauvegarde, tables: nomsTables.length, documents: lu.documents.length - documents.sautes.length,
      repris: documents.repris, sautes: documents.sautes, abimes: lu.abimes.map((abime) => abime.fichier), sansDocuments: sansDocuments(lu) };
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
      await montrerMessage('import-zip-refus', I18n.t('zip.brancher.import_zip_refuse'), 'important', droit.raison);
      return { ok: false, etape: 'refus', message: droit.raison };
    }
    const nomFichier = nomAffiche(fichier && fichier.name);
    const lu = await ZipLecture.lire(fichier);
    if (!lu.ok) {
      const message = I18n.t('zip.importer.rien_ete_ecrit', { refus: lu.refus });
      await montrerMessage('import-zip-refus', I18n.t('zip.brancher.import_zip_refuse'), 'important', message);
      return { ok: false, etape: 'refus', message: message };
    }
    try {
      await Donnees.rafraichir();                          // nombres de lignes actuels à jour
    } catch (erreur) {
      console.warn('Prévo : rafraîchissement avant l\'import ZIP impossible (' + sansPoint(erreur) + ').', erreur);
    }
    const horsZip = sansDocuments(lu) ? await documentsHorsZip(lu) : null;
    lu.reglagesGardes = reglagesGardes(lu.tables.parametres.lignes);     // T319 : dits à la confirmation, puis écrits
    lu.moiADemander = moiSoloApresImport(lu.reglagesGardes, lu.tables.techniciens.lignes);   // T323
    lu.comptesTouches = await comptesDontLaFicheChange(lu.tables.techniciens.lignes);       // T508
    if (!(await confirmer(lu, nomFichier, horsZip))) {
      UI.toast(I18n.t('zip.importer.import_zip_annule_rien'), 'info');
      return { ok: false, etape: 'annule' };
    }
    UI.toast(I18n.t('zip.importer.import_zip_cours_sauvegarde'), 'info');
    Donnees.arreterSurveillance();                         // aucune relecture au milieu des écritures
    let resultat;
    try {
      resultat = await executer(lu, nomAffiche(fichier && fichier.name, true));      // nom écrit au journal (D156)
    } finally {
      if (!resultat || !resultat.ok) Donnees.demarrerSurveillance();
    }
    if (!resultat.ok) {
      await App.reafficher();
      return Object.assign({ etape: 'ecriture' }, resultat);
    }
    // Trois morceaux, chacun une proposition complète par cas (tables, documents, sauvegarde).
    const nbAbimes = resultat.abimes.length;
    const tables = nbAbimes === 0 ? I18n.t('zip.importer.import_zip_termine_tables', { n: resultat.tables })
      : (nbAbimes === 1 ? I18n.t('zip.importer.import_zip_termine_tables_2', { n: resultat.tables, join: resultat.abimes.join(', ') })
        : I18n.t('zip.importer.import_zip_termine_tables_3', { n: resultat.tables, join: resultat.abimes.join(', ') }));
    let documentsDits = I18n.t('zip.importer.sans_documents_donnees_seules');
    if (!resultat.sansDocuments) {
      documentsDits = resultat.repris
        ? I18n.t('zip.importer.documents_deja_present_repris', { n: resultat.documents, repris: resultat.repris })
        : I18n.t('zip.importer.documents_aucun_document_existant', { n: resultat.documents });
    }
    const message = I18n.t('zip.importer.sauvegarde_faite_juste_avant', { tables, documentsDits, sauvegarde: resultat.sauvegarde })
      + (resultat.sautes.length ? ' ' + I18n.t('zip.importer.documents_non_repris', { n: resultat.sautes.length, noms: resultat.sautes.join(', ') }) : '');
    await montrerMessage('import-zip-termine', I18n.t('zip.importer.import_zip_termine'), 'succes', message,
      [{ libelle: I18n.t('zip.importer.recharger_prevo'), valeur: 'ok', classe: 'btn-primaire', defaut: true }]);
    location.reload();                                     // étape 8 : l'application repart des nouvelles données
    return Object.assign({ etape: 'fait', message: message }, resultat);
  }

  return { etat, bloc, brancher, importer, nomDemande, tablesImportees, get AVERTISSEMENT() { return avertissement(); } };
})();

// Relais de parametres.js (bloc de la carte « Sauvegardes », branchement du bouton).
Object.assign(Parametres.interne, { blocImportZip: ParametresZip.bloc, brancherImportZip: ParametresZip.brancher });
