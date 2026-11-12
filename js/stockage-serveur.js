'use strict';
// StockageServeur : adaptateur de stockage « serveur » (le PC qui fait tourner serveur.py).
// Contrat : docs/ARCHITECTURE.md §6 (adaptateurs) et §7 (API du serveur).
// Tout passe par fetch vers /api/… (même origine que la page). Ce fichier n'utilise ni crypto,
// ni presse-papiers : il doit marcher en http://192.168.x.x:8080 depuis un téléphone
// (contexte non sécurisé). Les versions (SHA-256) et les sauvegardes sont calculées par le serveur.
// Dépendances : Donnees (js/donnees.js) pour les erreurs ErreurConflit et ErreurStockage, Schema
// (js/schema.js) pour la liste des tables ; lues au moment des appels, pas au chargement.

const StockageServeur = (() => {

  const DELAI_DETECTION_MS = 2000;
  const NOM_APPLICATION = 'Prévo';
  // Délai maximal d'une requête (réponse et lecture du corps comprises).
  const DELAI_REPONSE_MS = 15000;
  const CODE_FORMAT_PLUS_RECENT = 'format_plus_recent';      // 409 du serveur en lecture seule (T185, D169)
  const CODE_FICHIER_ABIME = 'fichier_abime';                // 409 du serveur : fichier abîmé, jamais réécrit (T200)
  const ENTETE_REMPLACER_ABIME = 'X-Prevo-Remplacer-Abime';  // dérogation demandée (import ZIP, T200)
  const ENTETE_ABIME_DEPUIS = 'X-Prevo-Abime-Depuis';        // CSV abîmé importé tel quel, et sa date (T213)
  const MOTIF_DATE_HEURE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/;   // dates de fichiers-abimes.json (T206)

  // ===========================================================================
  // Détection
  // ===========================================================================

  // Vrai si un serveur Prévo répond sur cette adresse (« » = le site qui a servi la page).
  // Abandonne au bout de 2 secondes : l'application bascule alors vers l'écran de démarrage.
  async function detecter(base = '') {
    const controleur = new AbortController();
    const minuteur = setTimeout(function () { controleur.abort(); }, DELAI_DETECTION_MS);
    try {
      const reponse = await fetch(base + '/api/ping', { signal: controleur.signal, cache: 'no-store' });
      if (!reponse.ok) { return false; }
      const donnees = await reponse.json();
      return Boolean(donnees) && donnees.application === NOM_APPLICATION;
    } catch (erreur) {
      return false;     // réseau coupé, délai dépassé, réponse qui n'est pas du JSON : pas de serveur
    } finally {
      clearTimeout(minuteur);
    }
  }

  // ===========================================================================
  // Requêtes et correspondance des erreurs
  // ===========================================================================

  // Lit le JSON d'une réponse ; null si le corps n'est pas du JSON.
  async function lireJsonOuNull(reponse) {
    try {
      return await reponse.json();
    } catch (erreur) {
      return null;
    }
  }

  // Messages de ce module (lus au moment de l'erreur, jamais figés au chargement du module).
  function messageServeurInjoignable() {
    return I18n.t('socle.message_serveur_injoignable.serveur_prevo_repond_pas');
  }

  function messageDelaiDepasse() {
    return I18n.t('socle.message_delai_depasse.serveur_prevo_met_trop');
  }

  // Réponse « réussie » mais illisible (ex. page d'un portail Wi-Fi, proxy) : l'écriture a pu se faire.
  function messageReponseInattendue() {
    return I18n.t('socle.message_reponse_inattendue.reponse_inattendue_serveur_operation');
  }

  // ===========================================================================
  // Messages du serveur (D157, T246)
  // ===========================================================================

  // Un message du serveur arrive avec son code et ses valeurs, à côté du texte français :
  // { erreur: '<français>', erreur_code: 'csv.table_inconnue', erreur_valeurs: { table: 'x' } } (même suffixe pour
  // « message », « raison »… ; « _sans_point » : point final retiré). Une valeur peut être elle-même un message
  // ({ code, valeurs, texte }) ou une liste (jointe par « , »). Le texte affiché est la clé serveur.<code> de la langue
  // active (js/i18n/fr.js) ; le français reçu quand le navigateur ne connaît pas le code (serveur plus récent).
  function messageTraduit(code, valeurs, repli, sansPoint) {
    if (typeof code !== 'string' || !code) return repli;
    const lues = {};
    if (valeurs && typeof valeurs === 'object' && !Array.isArray(valeurs)) {
      Object.keys(valeurs).forEach((nom) => { lues[nom] = valeurDuMessage(valeurs[nom]); });
    }
    const traduit = I18n.t('serveur.' + code, lues);
    if (traduit === 'serveur.' + code) return repli;    // code inconnu de ce navigateur
    return sansPoint ? traduit.replace(/\.+$/, '') : traduit;
  }

  function valeurDuMessage(valeur) {
    if (Array.isArray(valeur)) return valeur.map(valeurDuMessage).join(', ');
    if (valeur && typeof valeur === 'object') {
      return messageTraduit(valeur.code, valeur.valeurs, String(valeur.texte || ''), valeur.sans_point === true);
    }
    return valeur;
  }

  // Texte du champ `champ` d'une réponse du serveur (« erreur », « message », « raison »…), dans la langue active.
  function texteDuServeur(donnees, champ) {
    if (!donnees || typeof donnees !== 'object' || typeof donnees[champ] !== 'string') {
      return donnees && typeof donnees === 'object' ? donnees[champ] : undefined;
    }
    return messageTraduit(donnees[champ + '_code'], donnees[champ + '_valeurs'], donnees[champ],
      donnees[champ + '_sans_point'] === true);
  }

  // Transforme une réponse en erreur (409 → ErreurConflit, autre code ≥ 400 → ErreurStockage, avec le code HTTP
  // dans `codeHttp`). Lot 7 (§22.4, §22.5) : 401 = session absente ou expirée, appareil refusé → l'événement
  // EVENEMENT_SESSION_ABSENTE est émis sur document (l'écran de connexion, T155, l'écoute et s'affiche ; sans
  // écouteur, le message du serveur s'affiche comme toute erreur) ; 403 = rôle ou règle refusés → le message du
  // serveur (« Accès refusé : … ») tel quel.
  // T185 (D169) : 409 au code « format_plus_recent » = le serveur a trouvé à son démarrage des données d'une version
  // plus récente de Prévo et refuse toute écriture → Donnees.ErreurLectureSeule (jamais un conflit à réessayer).
  // T200 : 409 au code « fichier_abime » (corps { erreur, code, table }) = le fichier de la table est abîmé et le serveur
  // refuse de le réécrire ou de le compléter → Donnees.ErreurFichierAbime, AVANT le 409 générique (un conflit serait
  // réessayé par Donnees.modifier, avec un faux message).
  async function erreurDepuisReponse(reponse) {
    const donnees = await lireJsonOuNull(reponse);
    const message = (donnees && donnees.erreur && texteDuServeur(donnees, 'erreur'))      // D157 : traduit par son code
      || I18n.t('socle.erreur_depuis_reponse.serveur_refuse_demande_code', { status: reponse.status });
    if (reponse.status === 409 && donnees && donnees.code === CODE_FORMAT_PLUS_RECENT
      && typeof Donnees.ErreurLectureSeule === 'function') {
      return new Donnees.ErreurLectureSeule(donnees.format);
    }
    if (reponse.status === 409 && donnees && donnees.code === CODE_FICHIER_ABIME
      && typeof Donnees.ErreurFichierAbime === 'function') {
      const table = typeof donnees.table === 'string' ? donnees.table : '';
      return new Donnees.ErreurFichierAbime(table, table ? table + '.csv' : I18n.t('socle.erreur_depuis_reponse.table'));
    }
    if (reponse.status === 409) {
      const versionActuelle = donnees && donnees.version_actuelle !== undefined
        ? donnees.version_actuelle : null;
      return new Donnees.ErreurConflit(message, versionActuelle);
    }
    // 423 (fichier ouvert dans Excel) et tous les autres codes : le message du serveur est lisible tel quel.
    const erreur = new Donnees.ErreurStockage(message);
    erreur.codeHttp = reponse.status;
    if (reponse.status === 401) {
      erreur.sessionAbsente = true;
      erreur.appareilRefuse = Boolean(donnees && donnees.appareil_refuse);
      signalerSessionAbsente(erreur);
    }
    return erreur;
  }

  // Événement d'une session absente (401) : { message, appareilRefuse }. Jamais plus d'un par seconde (un
  // chargement lance plusieurs requêtes à la fois : un seul passage à l'écran de connexion).
  const EVENEMENT_SESSION_ABSENTE = 'prevo:session-absente';
  const SILENCE_SESSION_ABSENTE_MS = 1000;
  let derniereSessionAbsente = 0;
  function signalerSessionAbsente(erreur) {
    const maintenant = Date.now();
    if (maintenant - derniereSessionAbsente < SILENCE_SESSION_ABSENTE_MS) { return; }
    derniereSessionAbsente = maintenant;
    try {
      document.dispatchEvent(new CustomEvent(EVENEMENT_SESSION_ABSENTE,
        { detail: { message: erreur.message, appareilRefuse: Boolean(erreur.appareilRefuse) } }));
    } catch (erreurEvenement) {
      console.warn('Prévo : événement de session absente non émis (' + erreurEvenement.message + ').');
    }
  }

  // Erreur pendant l'envoi ou la lecture : délai dépassé (requête abandonnée) ou serveur injoignable.
  function erreurReseau(erreur) {
    if (erreur && erreur.name === 'AbortError') {
      return new Donnees.ErreurStockage(messageDelaiDepasse(), erreur);
    }
    return new Donnees.ErreurStockage(messageServeurInjoignable(), erreur);
  }

  // Envoie la requête et rend la réponse, quel que soit son code (l'appelant décide).
  // Échec réseau (serveur arrêté, câble débranché) → ErreurStockage au message prévu.
  // Pas de réponse en 15 s → requête abandonnée, ErreurStockage « met trop de temps à répondre ».
  // Le minuteur n'est pas arrêté à la réception des en-têtes : il couvre aussi la lecture du
  // corps (abandonner une requête déjà entièrement lue n'a aucun effet).
  // Toute requête qui écrit (PUT, POST) envoie un corps, même vide, et l'en-tête X-Prevo: 1.
  async function appeler(url, options) {
    const controleur = new AbortController();
    setTimeout(function () { controleur.abort(); }, DELAI_REPONSE_MS);
    try {
      return await fetch(url, Object.assign({ cache: 'no-store' }, options, { signal: controleur.signal }));
    } catch (erreur) {
      throw erreurReseau(erreur);
    }
  }

  // Comme appeler, mais lève l'erreur correspondante pour tout code ≥ 400.
  async function appelerOuErreur(url, options) {
    const reponse = await appeler(url, options);
    if (reponse.status >= 400) { throw await erreurDepuisReponse(reponse); }
    return reponse;
  }

  // Lit l'objet JSON d'une réponse réussie. Échec de lecture en route = délai ou serveur
  // injoignable ; corps lu mais qui n'est pas un objet JSON = réponse inattendue.
  async function lireJson(reponse) {
    let texte;
    try {
      texte = await reponse.text();
    } catch (erreur) {
      throw erreurReseau(erreur);
    }
    let donnees;
    try {
      donnees = JSON.parse(texte);
    } catch (erreur) {
      throw new Donnees.ErreurStockage(messageReponseInattendue(), erreur);
    }
    if (donnees === null || typeof donnees !== 'object') {
      throw new Donnees.ErreurStockage(messageReponseInattendue());
    }
    return donnees;
  }

  // Lit et jette le corps d'une réponse dont seul le code compte (404 « fichier absent ») : un corps jamais lu laisse la
  // requête inachevée pour le navigateur (réseau jamais au repos : T402, tables du format 4 absentes en mode serveur).
  async function jeterCorps(reponse) {
    try {
      await reponse.arrayBuffer();
    } catch (erreur) {
      /* corps illisible ou requête abandonnée : rien à garder */
    }
  }

  async function lireOctets(reponse) {
    try {
      return new Uint8Array(await reponse.arrayBuffer());
    } catch (erreur) {
      throw erreurReseau(erreur);
    }
  }

  // « copie_externe » de /api/info (lot 7, D133, §22.11) → { derniereReussie, joursSansCopie, erreur }, ou null quand
  // le PC serveur n'a aucun dossier de copie externe.
  function copieExterneLue(copie) {
    if (!copie || typeof copie !== 'object') return null;
    return {
      derniereReussie: typeof copie.derniere_reussie === 'string' ? copie.derniere_reussie : null,
      joursSansCopie: typeof copie.jours_sans_copie === 'number' ? copie.jours_sans_copie : null,
      erreur: typeof copie.erreur === 'string' && copie.erreur ? texteDuServeur(copie, 'erreur') : null,
    };
  }

  // « tailscale » de /api/info (lot 7, D128, §22.8) → { present, connecte, nom, joursAvantExpiration }, ou null quand
  // le PC serveur n'attend pas Tailscale (portée « ce PC » sans mandataire ni nom en .ts.net : rien n'est détecté).
  function tailscaleLu(tailscale) {
    if (!tailscale || typeof tailscale !== 'object') return null;
    return {
      present: tailscale.present === true,
      connecte: tailscale.connecte === true,
      nom: typeof tailscale.nom === 'string' && tailscale.nom ? tailscale.nom : null,
      joursAvantExpiration: typeof tailscale.jours_avant_expiration === 'number' ? tailscale.jours_avant_expiration : null,
    };
  }

  // « format » de /api/info (T185, D168, D169) → { base, courant, plusRecent, migration, tablesAbimees, tablesVides,
  // tableBloquee }, ou null quand le serveur n'a pas regardé le format des données. C'est le serveur qui passe les
  // fichiers au format courant, à son démarrage ; migration dit ce qu'il a fait : 'faite', 'rien' (rien à faire, ou
  // données plus récentes : plusRecent), 'impossible' (sauvegarde « avant-format-vN » impossible : rien d'écrit) ou
  // 'incomplete' (un fichier tenu par un autre programme, tableBloquee : fermez Excel et relancez Prévo).
  // tablesAbimees : fichiers jamais réécrits (en-tête illisible, ou fichier qu'une réécriture abîmerait).
  // abimesDepuis (T206, « abimes_depuis ») : { table: 'AAAA-MM-JJTHH:MM:SS' }, date à laquelle le serveur a vu chaque
  // table abîmée la première fois (fichiers-abimes.json) ; {} si le serveur ne la donne pas.
  function formatLu(format) {
    if (!format || typeof format !== 'object') return null;
    const tables = (liste) => (Array.isArray(liste) ? liste.filter((table) => typeof table === 'string') : []);
    const dates = (objet) => {
      const resultat = {};
      if (!objet || typeof objet !== 'object' || Array.isArray(objet)) return resultat;
      Object.keys(objet).forEach((table) => {
        if (typeof objet[table] === 'string' && MOTIF_DATE_HEURE.test(objet[table])) resultat[table] = objet[table];
      });
      return resultat;
    };
    return {
      base: typeof format.base === 'number' ? format.base : null,
      courant: typeof format.courant === 'number' ? format.courant : null,
      plusRecent: format.plus_recent === true,
      migration: typeof format.migration === 'string' ? format.migration : null,
      tablesAbimees: tables(format.tables_abimees),
      tablesVides: tables(format.tables_vides),
      tableBloquee: typeof format.table_bloquee === 'string' && format.table_bloquee ? format.table_bloquee : null,
      abimesDepuis: dates(format.abimes_depuis),
    };
  }

  // ===========================================================================
  // Fabrique de l'adaptateur
  // ===========================================================================

  // base : préfixe des adresses (« » = même origine que la page, cas normal).
  function creer(base = '') {
    const entetesEcriture = { 'X-Prevo': '1' };

    function urlTable(table) {
      return base + '/api/csv/' + encodeURIComponent(table);
    }

    function urlDocument(nom) {
      return base + '/api/documents/' + encodeURIComponent(nom);
    }

    async function charger(table) {
      const reponse = await appeler(urlTable(table), { method: 'GET' });
      // 404 = fichier absent, mais seulement pour une table du schéma (sinon : table inconnue). 403 (lot 7, D126,
      // ARCHITECTURE.md §22.5) : table que le rôle de la session ne lit pas (demandeur) : vue comme absente, sans
      // erreur, pour que le chargement des tables (Donnees.chargerTout) aboutisse ; /api/versions ne la liste pas.
      if ((reponse.status === 404 || reponse.status === 403) && Schema.nomsTables().indexOf(table) !== -1) {
        await jeterCorps(reponse);
        return { octets: null, version: null };
      }
      if (reponse.status >= 400) { throw await erreurDepuisReponse(reponse); }
      return { octets: await lireOctets(reponse), version: reponse.headers.get('X-Version') };
    }

    // versionAttendue : version lue au chargement, ou null si le fichier ne doit pas exister.
    // options.remplacerFichierAbime === true (import ZIP, T200) : en-tête X-Prevo-Remplacer-Abime: 1, le serveur
    // remplace alors un fichier abîmé ; sans lui, il refuse (409 « fichier_abime » → ErreurFichierAbime).
    // T213 : options.abimeDepuis ('AAAA-MM-JJTHH:MM:SS', avec remplacerFichierAbime) : l'import ZIP écrit un CSV marqué
    // abîmé, tel quel ; en-tête X-Prevo-Abime-Depuis : le serveur l'accepte malgré son en-tête s'il le voit abîmé lui
    // aussi, et garde cette date dans fichiers-abimes.json.
    async function enregistrer(table, octets, versionAttendue, options) {
      const derogation = Boolean(options) && options.remplacerFichierAbime === true
        ? { [ENTETE_REMPLACER_ABIME]: '1' } : {};
      if (derogation[ENTETE_REMPLACER_ABIME] && typeof options.abimeDepuis === 'string') {
        derogation[ENTETE_ABIME_DEPUIS] = options.abimeDepuis;
      }
      const reponse = await appelerOuErreur(urlTable(table), {
        method: 'PUT',
        headers: Object.assign({
          'Content-Type': 'text/csv; charset=utf-8',
          'X-Version-Attendue': versionAttendue === null || versionAttendue === undefined
            ? 'aucune' : versionAttendue,
        }, derogation, entetesEcriture),
        body: octets,
      });
      const donnees = await lireJson(reponse);
      return { version: donnees.version };
    }

    async function ajouter(table, octets) {
      const adresse = urlTable(table) + '/ajout';
      const reponse = await appelerOuErreur(adresse, {
        method: 'POST',
        headers: Object.assign({ 'Content-Type': 'text/csv; charset=utf-8' }, entetesEcriture),
        body: octets,
      });
      const donnees = await lireJson(reponse);
      return { version: donnees.version };
    }

    // → { nomTable: version | null, … }
    async function listerVersions() {
      const reponse = await appelerOuErreur(base + '/api/versions', { method: 'GET' });
      const donnees = await lireJson(reponse);
      if (!donnees.tables || typeof donnees.tables !== 'object' || Array.isArray(donnees.tables)) {
        throw new Donnees.ErreurStockage(messageReponseInattendue());
      }
      const versions = {};
      Object.keys(donnees.tables).forEach(function (table) {
        const detail = donnees.tables[table];
        versions[table] = detail ? detail.version : null;
      });
      return versions;
    }

    // Refuse d'écraser un document : le serveur répond 409 s'il existe déjà.
    async function ecrireDocument(nom, blob) {
      const reponse = await appeler(urlDocument(nom), {
        method: 'PUT',
        headers: Object.assign({ 'Content-Type': blob.type || 'application/octet-stream' }, entetesEcriture),
        body: blob,
      });
      if (reponse.status >= 400) {
        const erreur = await erreurDepuisReponse(reponse);
        // 409 : document du même nom (conflit), sauf en lecture seule (T185 : ErreurLectureSeule telle quelle).
        if (erreur instanceof Donnees.ErreurConflit) {
          throw new Donnees.ErreurStockage(I18n.t('socle.creer.document_porte_deja_nom'));
        }
        throw erreur;
      }
      const donnees = await lireJson(reponse);
      return donnees.nom;
    }

    async function lireDocument(nom) {
      const reponse = await appeler(urlDocument(nom), { method: 'GET' });
      if (reponse.status === 404) { await jeterCorps(reponse); return null; }
      if (reponse.status >= 400) { throw await erreurDepuisReponse(reponse); }
      try {
        return await reponse.blob();
      } catch (erreur) {
        throw erreurReseau(erreur);
      }
    }

    // Le serveur sert le document : l'adresse suffit pour un <img src> ou un lien.
    async function adresseDocument(nom) {
      return urlDocument(nom);
    }

    // motif (facultatif) : mot de la liste fermée du serveur (ex. 'avant-format-v2'), ajouté à la fin
    // du nom (« AAAA-MM-JJ_HHMMSS_avant-format-v2 ») ; motif refusé → ErreurStockage (400).
    // Sans motif : corps vide, sauvegarde manuelle « AAAA-MM-JJ_HHMMSS » comme avant.
    async function sauvegarder(motif) {
      const avecMotif = motif !== undefined && motif !== null && motif !== '';
      const reponse = await appelerOuErreur(base + '/api/sauvegarde', {
        method: 'POST',
        headers: avecMotif
          ? Object.assign({ 'Content-Type': 'application/json; charset=utf-8' }, entetesEcriture)
          : entetesEcriture,
        body: avecMotif ? JSON.stringify({ motif: motif }) : '',
      });
      const donnees = await lireJson(reponse);
      return donnees.sauvegarde;
    }

    // → [{ nom, tables: [...] }], plus récente d'abord (ordre donné par le serveur)
    async function listerSauvegardes() {
      const reponse = await appelerOuErreur(base + '/api/sauvegardes', { method: 'GET' });
      const donnees = await lireJson(reponse);
      return donnees.sauvegardes;
    }

    // tables : liste facultative ; sans elle, toutes les tables de la sauvegarde sont restaurées.
    async function restaurer(nom, tables) {
      const demande = { sauvegarde: nom };
      if (tables) { demande.tables = tables; }
      const reponse = await appelerOuErreur(base + '/api/restauration', {
        method: 'POST',
        headers: Object.assign({ 'Content-Type': 'application/json; charset=utf-8' }, entetesEcriture),
        body: JSON.stringify(demande),
      });
      const donnees = await lireJson(reponse);
      return { restaurees: donnees.restaurees, videes: donnees.videes || [], copieSecurite: donnees.copie_securite };
    }

    // « Tester une sauvegarde » (lot 7, D133) : le serveur relit chaque CSV de la sauvegarde et compte ses lignes,
    // sans rien écrire → { nom, ok, tables: [{ table, lignes, erreur }] } (erreur dans la langue active, D157) ; nom
    // refusé ou sauvegarde absente → ErreurStockage. Propre au mode serveur (les autres adaptateurs n'ont pas cette
    // méthode).
    async function testerSauvegarde(nom) {
      const reponse = await appelerOuErreur(base + '/api/sauvegarde/tester', {
        method: 'POST',
        headers: Object.assign({ 'Content-Type': 'application/json; charset=utf-8' }, entetesEcriture),
        body: JSON.stringify({ nom: nom }),
      });
      const donnees = await lireJson(reponse);
      if (Array.isArray(donnees.tables)) {
        donnees.tables = donnees.tables.map((table) => (table && typeof table.erreur === 'string'
          ? Object.assign({}, table, { erreur: texteDuServeur(table, 'erreur') }) : table));
      }
      return donnees;
    }

    // Lot 7 (§22.4) : GET /api/session → { comptes: bool, session: null | { identifiant, role, prenom, nom,
    // technicienId, aChanger, appareil, langue (T298 : celle du compte, '' pour la langue de l'installation) } } ;
    // route publique (jamais 401), même sans comptes ({ comptes: false }).
    async function session() {
      const reponse = await appelerOuErreur(base + '/api/session', { method: 'GET' });
      const donnees = await lireJson(reponse);
      const identite = donnees.session && typeof donnees.session === 'object' ? donnees.session : null;
      return Object.assign({
        comptes: Boolean(donnees.comptes),
        session: identite === null ? null : {
          identifiant: String(identite.identifiant || ''), role: String(identite.role || ''),
          prenom: String(identite.prenom || ''), nom: String(identite.nom || ''),
          technicienId: String(identite.technicien_id || ''), aChanger: Boolean(identite.a_changer),
          appareil: Boolean(identite.appareil), langue: String(identite.langue || ''),
        },
      }, donnees.installation_inachevee ? { installationInachevee: true } : {});   // §22.10 : aucun responsable
    }

    async function info() {
      const reponse = await appelerOuErreur(base + '/api/info', { method: 'GET' });
      const donnees = await lireJson(reponse);
      // Lot 7 (§22.6) : hors de « ce PC », les adresses sont celles de la porte d'entrée et « porte » est vrai.
      // Lot 7 (§22.10) : installation_a_faire est vrai tant que prevo.config.json n'existe pas (assistant proposé, jamais imposé).
      // Recette du lot 7 : ce_pc_seulement vrai en portée « ce PC » (aucun téléphone ne joint Prévo).
      return { adressesReseau: donnees.adresses_reseau || [], port: donnees.port, porte: donnees.porte === true,
        cePcSeulement: donnees.ce_pc_seulement === true,
        copieExterne: copieExterneLue(donnees.copie_externe), tailscale: tailscaleLu(donnees.tailscale),
        installationAFaire: donnees.installation_a_faire === true,
        format: formatLu(donnees.format) };        // T185 : passage au format courant fait par le serveur
    }

    // T206 (contrat, point 4) : depuis quand chaque table est abîmée, { table: 'AAAA-MM-JJTHH:MM:SS' } (format de
    // /api/info, « abimes_depuis » ; {} si le serveur ne le donne pas).
    async function abimesDepuis() {
      const format = (await info()).format;
      return format ? format.abimesDepuis : {};
    }

    return {
      mode: 'serveur',
      // Lu à chaque affichage (jamais figé à la création de l'adaptateur).
      get libelle() { return I18n.t('socle.creer.serveur_host', { host: location.host }); },
      charger: charger,
      enregistrer: enregistrer,
      ajouter: ajouter,
      listerVersions: listerVersions,
      ecrireDocument: ecrireDocument,
      lireDocument: lireDocument,
      urlDocument: adresseDocument,
      sauvegarder: sauvegarder,
      listerSauvegardes: listerSauvegardes,
      restaurer: restaurer,
      testerSauvegarde: testerSauvegarde,
      info: info,
      abimesDepuis: abimesDepuis,
      session: session,
    };
  }

  return {
    detecter: detecter,
    creer: creer,
    texte: texteDuServeur,     // D157 : message d'une réponse du serveur dans la langue active (modules à fetch propre)
    EVENEMENT_SESSION_ABSENTE: EVENEMENT_SESSION_ABSENTE,
  };
})();
