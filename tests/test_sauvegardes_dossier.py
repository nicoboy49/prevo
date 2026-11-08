"""Sauvegardes du mode dossier (chantier « socle de données », T188 ; décision D170 ; docs/FORMAT.md §8 et §9) :
js/stockage-dossier.js (rotation, manifeste.json, avant-import-zip, sauvegarderAvantMiseAJour), js/app.js (ordre au
démarrage) et js/modules/parametres.js (libellés).

Le dossier est simulé dans l'OPFS du navigateur (installer_dossier_simule de tests/commun.py, http://127.0.0.1) ; les
jeux de tests/fixtures/formats/ sont copiés dans un dossier temporaire puis écrits dans l'OPFS : jamais de données réelles.

    rotation           horloge Playwright (contexte.clock.install) au 2026-04-10, changement d'heure du 29 mars dans
                       l'intervalle : fausses quotidiennes de 1 à 5, 10, 29, 30, 31 et 45 jours, « …_avant-… » anciennes,
                       62 manuelles, noms hors motif et un fichier ; la première écriture du jour (nouvelle quotidienne)
                       supprime les quotidiennes de plus de 30 jours et les 2 manuelles les plus anciennes, rien d'autre ;
                       une nouvelle manuelle (61) supprime la plus ancienne ;
    manifeste          manifeste.json de chaque sorte de sauvegarde (manuelle, quotidienne, à motif, avant-restauration),
                       comparé octet pour octet à un manifeste calculé en Python (hashlib) : champs et leur ordre, fichiers
                       triés, tailles, SHA-256 ; aucun marqueur « .en-cours » laissé ; la restauration l'ignore ;
    avant-import-zip   documents/ copié aussi (à l'octet, sous-dossiers exclus) et compté dans le manifeste ; une
                       manuelle ne copie pas documents/ ;
    avant-mise-a-jour  application entière (index.html) : premier démarrage sur f2-v1.1.0 (octets d'ORIGINE dans la
                       sauvegarde, « de » null et « vers », derniere-version.json écrit, passage au format 3 ensuite) et
                       sur f3-v1.2.0 avec la version « 1.2.0 » notée ; seconde ouverture : rien ; même version notée :
                       rien ; jeu plus-recent (lecture seule) : aucun octet écrit ; échec : bandeau, l'application
                       continue, rien n'est noté, nouvel essai réussi à l'ouverture suivante ; base vide : version notée,
                       aucune sauvegarde « avant-mise-a-jour » ;
    libellés           Paramètres › Sauvegardes : « Avant un import ZIP », « Avant la mise à jour de Prévo ».

Lancer depuis la racine du projet (à travers le verrou du navigateur) :
    py -X utf8 -m unittest discover -s tests -p "test_sauvegardes_dossier.py" -v
"""
import base64
import datetime
import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

from commun import FORMAT_COURANT, RACINE, CasNavigateur, ServeurStatique, attendre_pret, installer_dossier_simule, preregler_profil
from jeux_formats import copier_jeu

NOM_DOSSIER = "donnees-sauvegardes"
PAGE_STOCKAGE = "/tests/fixtures/page-stockage-dossier.html"
ERREUR_PING_ABSENT = re.compile(r"status of 404.*/api/ping")      # serveur statique : pas de /api/ping
VERSION_APPLI = re.search(r"const VERSION = '([^']+)';", (RACINE / "js" / "app.js").read_text(encoding="utf-8")).group(1)
BOM = b"\xef\xbb\xbf"
VERROU = "verrou.txt"
DERNIERE_VERSION = "derniere-version.json"
MANIFESTE = "manifeste.json"
DATE_HEURE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
MOTIF_QUOTIDIENNE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MOTIF_MANUELLE = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}$")
MOTIF_AVANT_MISE_A_JOUR = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}_avant-mise-a-jour$")
MOTIF_AVANT_FORMAT = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}_avant-format-v3$")
HORLOGE = "2026-04-10T10:00:00"
AUJOURDHUI = datetime.date(2026, 4, 10)

ECRIRE_OPFS_JS = """async ([nom, fichiers]) => {
  const racine = await (await navigator.storage.getDirectory()).getDirectoryHandle(nom, { create: true });
  for (const [chemin, enBase64] of Object.entries(fichiers)) {
    const morceaux = chemin.split('/');
    let dossier = racine;
    for (const sous of morceaux.slice(0, -1)) { dossier = await dossier.getDirectoryHandle(sous, { create: true }); }
    const binaire = atob(enBase64);
    const octets = new Uint8Array(binaire.length);
    for (let i = 0; i < binaire.length; i += 1) { octets[i] = binaire.charCodeAt(i); }
    const flux = await (await dossier.getFileHandle(morceaux[morceaux.length - 1], { create: true })).createWritable();
    await flux.write(octets);
    await flux.close();
  }
}"""

INSTANTANE_OPFS_JS = """async (nom) => {
  const resultat = {};
  async function parcourir(dossier, prefixe) {
    for await (const entree of dossier.values()) {
      if (entree.kind === 'directory') { await parcourir(entree, prefixe + entree.name + '/'); continue; }
      const octets = new Uint8Array(await (await entree.getFile()).arrayBuffer());
      let binaire = '';
      for (let i = 0; i < octets.length; i += 0x8000) {
        binaire += String.fromCharCode.apply(null, octets.subarray(i, i + 0x8000));
      }
      resultat[prefixe + entree.name] = btoa(binaire);
    }
  }
  await parcourir(await (await navigator.storage.getDirectory()).getDirectoryHandle(nom, { create: true }), '');
  return resultat;
}"""

# Adaptateur seul (page de test de StockageDossier) : window.dos, puis appels { ok, valeur } ou { ok: false, nom, message }.
CREER_ADAPTATEUR_JS = """async () => {
  window.dos = await StockageDossier.creer(await StockageDossier.choisir(), { poste: 'Poste test' });
}"""

APPELER_JS = """async ([methode, args]) => {
  const revivre = (v) => (v && typeof v === 'object' && typeof v.texte === 'string' ? new TextEncoder().encode(v.texte) : v);
  try {
    return { ok: true, valeur: await window.dos[methode](...args.map(revivre)) };
  } catch (erreur) {
    return { ok: false, nom: erreur.name, message: erreur.message };
  }
}"""


def csv_prevo(texte):
    """Contenu d'un CSV de Prévo : BOM UTF-8, CRLF."""
    return BOM + texte.replace("\n", "\r\n").encode("utf-8")


def empreinte(octets):
    """Version d'un fichier pour l'adaptateur : SHA-256, 16 premiers caractères hexadécimaux."""
    return hashlib.sha256(octets).hexdigest()[:16]


def description(nom, octets):
    return {"nom": nom, "octets": len(octets), "sha256": hashlib.sha256(octets).hexdigest()}


def fichiers_du_jeu(nom):
    """{chemin relatif (« / ») : octets} d'une copie du jeu, faite dans un dossier temporaire."""
    with tempfile.TemporaryDirectory(prefix="prevo-sauvegardes-") as temporaire:
        dossier = copier_jeu(nom, Path(temporaire) / "donnees")
        return {p.relative_to(dossier).as_posix(): p.read_bytes() for p in sorted(dossier.rglob("*")) if p.is_file()}


def csv_de_la_racine(fichiers):
    return {chemin: octets for chemin, octets in fichiers.items() if "/" not in chemin and chemin.endswith(".csv")}


def dossiers_de_sauvegarde(instantane):
    """Noms des dossiers de sauvegardes/ (qui contiennent au moins un fichier)."""
    return sorted({chemin.split("/")[1] for chemin in instantane if chemin.startswith("sauvegardes/") and chemin.count("/") >= 2})


def contenu_sauvegarde(instantane, nom):
    """{chemin dans la sauvegarde : octets}."""
    prefixe = "sauvegardes/%s/" % nom
    return {chemin[len(prefixe):]: octets for chemin, octets in instantane.items() if chemin.startswith(prefixe)}


def sans_verrou(instantane):
    return {chemin: octets for chemin, octets in instantane.items() if chemin != VERROU}


class CasSauvegardesDossier(CasNavigateur):

    def setUp(self):
        super().setUp()
        self.autoriser_erreur(ERREUR_PING_ABSENT)
        self.statique = ServeurStatique(RACINE)
        self.statique.demarrer()
        self.addCleanup(self.statique.arreter)
        installer_dossier_simule(self.contexte, NOM_DOSSIER)

    # -- dossier simulé ----------------------------------------------------------------------

    def instantane(self):
        brut = self.page.evaluate(INSTANTANE_OPFS_JS, NOM_DOSSIER)
        return {chemin: base64.b64decode(valeur) for chemin, valeur in brut.items()}

    def ecrire(self, fichiers):
        envoyes = {chemin: base64.b64encode(octets).decode("ascii") for chemin, octets in fichiers.items()}
        self.page.evaluate(ECRIRE_OPFS_JS, [NOM_DOSSIER, envoyes])

    # -- adaptateur seul ---------------------------------------------------------------------

    def ouvrir_stockage(self, fichiers):
        self.page.goto(self.statique.url + PAGE_STOCKAGE)
        self.ecrire(fichiers)
        self.page.evaluate(CREER_ADAPTATEUR_JS)

    def reussir(self, methode, *arguments):
        resultat = self.page.evaluate(APPELER_JS, [methode, list(arguments)])
        self.assertTrue(resultat["ok"], "%s a échoué : %s" % (methode, resultat))
        return resultat["valeur"]

    # -- application entière -----------------------------------------------------------------

    def ouvrir_app(self, fichiers, profil="demandeur"):
        """Application ouverte (état « prêt ») sur le dossier simulé qui contient `fichiers`."""
        preregler_profil(self.contexte, profil, nom="Lucie Essai")
        self.page.goto(self.statique.url + "/index.html")
        self.page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        self.ecrire(fichiers)
        self.assertEqual(self.instantane(), fichiers)
        self.page.click("#btn-dossier")
        attendre_pret(self.page)
        self.assertEqual(self.page.evaluate("App.mode"), "dossier")
        self.assertEqual(self.page.evaluate("App.version"), VERSION_APPLI)

    def rouvrir_app(self):
        self.page.reload()
        self.page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        self.page.click("#btn-reprendre")
        attendre_pret(self.page)

    # -- vérifications -----------------------------------------------------------------------

    def verifier_manifeste(self, brut, fichiers, motif, format, version=VERSION_APPLI, complements=()):
        """manifeste.json égal, octet pour octet, à celui calculé ici (hashlib) : application, version_appli (si
        connue), format, date, motif, mode, compléments (de, vers), fichiers triés par nom. Rend le manifeste lu."""
        manifeste = json.loads(brut.decode("utf-8"))
        attendu = {"application": "Prévo"}
        if version is not None:
            attendu["version_appli"] = version
        attendu.update({"format": format, "date": manifeste.get("date"), "motif": motif, "mode": "dossier"})
        attendu.update(complements)
        attendu["fichiers"] = [description(nom, octets) for nom, octets in sorted(fichiers.items())]
        self.assertEqual(manifeste, attendu)
        self.assertEqual(list(manifeste), list(attendu))                              # ordre des champs
        self.assertRegex(manifeste["date"], DATE_HEURE)
        self.assertEqual(brut, (json.dumps(attendu, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
        return manifeste

    def verifier_note(self, instantane, version=VERSION_APPLI):
        note = json.loads(instantane[DERNIERE_VERSION].decode("utf-8"))
        self.assertEqual(list(note), ["version", "depuis"])
        self.assertEqual(note["version"], version)
        self.assertRegex(note["depuis"], DATE_HEURE)


# ---------------------------------------------------------------------------
# Rotation, manifeste, avant-import-zip (adaptateur seul)
# ---------------------------------------------------------------------------

class TestRotationEtManifeste(CasSauvegardesDossier):

    def test_rotation_quotidiennes_de_plus_de_30_jours_et_manuelles_au_dela_de_60(self):
        self.contexte.clock.install(time=HORLOGE)
        equipements = csv_prevo("id;nom\nEQ-0001;Presse\n")
        # T206 : 1 à 5 jours en plus, pour que 7 quotidiennes saines soient plus récentes que celles de 31 et 45 jours
        # (les 7 quotidiennes saines les plus récentes sont toujours gardées, quel que soit leur âge).
        quotidiennes = {age: (AUJOURDHUI - datetime.timedelta(days=age)).isoformat()
                        for age in (1, 2, 3, 4, 5, 10, 29, 30, 31, 45)}
        avant = ["2025-01-01_120000_avant-format-v3", "2025-01-01_120000_avant-mise-a-jour",
                 "2025-01-02_120000_avant-import-zip", "2025-01-03_120000_avant-import",
                 "2025-01-04_120000_avant-restauration", "2025-01-05_120000_avant-format-v2"]
        debut = datetime.datetime(2026, 1, 1, 8, 0, 0)
        manuelles = [(debut + datetime.timedelta(hours=heures)).strftime("%Y-%m-%d_%H%M%S") for heures in range(62)]
        etrangers = ["2025-02-30", "2025-13-01", "2025-1-01", "vieux-dossier", "2025-01-01-copie", "2025-01-01_1200",
                     "2025-01-01_120000_autre"]
        un_fichier = "sauvegardes/2025-01-06"                          # nom de quotidienne, mais un fichier
        fichiers = {"equipements.csv": equipements, un_fichier: b"un fichier, pas un dossier\r\n"}
        for nom in list(quotidiennes.values()) + avant + manuelles + etrangers:
            fichiers["sauvegardes/%s/equipements.csv" % nom] = equipements
        self.ouvrir_stockage(fichiers)
        self.assertEqual(self.page.evaluate("new Date().getFullYear() + '-' + (new Date().getMonth() + 1)"), "2026-4")

        # Première écriture du jour : nouvelle quotidienne (l'état d'avant l'écriture), puis rotation.
        self.reussir("enregistrer", "equipements", {"texte": "id;nom\r\nEQ-0001;Presse 2\r\n"}, empreinte(equipements))
        apres = self.instantane()
        du_jour = AUJOURDHUI.isoformat()
        gardees = ({quotidiennes[age] for age in (1, 2, 3, 4, 5, 10, 29, 30)} | set(avant) | set(manuelles[2:])
                   | set(etrangers))
        self.assertEqual(set(dossiers_de_sauvegarde(apres)), gardees | {du_jour})
        self.assertEqual(apres[un_fichier], fichiers[un_fichier])
        for nom in gardees:
            self.assertEqual(contenu_sauvegarde(apres, nom), {"equipements.csv": equipements}, nom)
        nouvelle = contenu_sauvegarde(apres, du_jour)
        self.assertEqual(set(nouvelle), {"equipements.csv", MANIFESTE})
        self.verifier_manifeste(nouvelle[MANIFESTE], {"equipements.csv": equipements}, "quotidienne", 1, version=None)

        # Nouvelle manuelle : 61 → la plus ancienne supprimée ; les autres sauvegardes ne bougent pas.
        manuelle = self.reussir("sauvegarder")
        self.assertRegex(manuelle, MOTIF_MANUELLE)
        self.assertTrue(manuelle.startswith(du_jour + "_"), manuelle)
        dossiers = set(dossiers_de_sauvegarde(self.instantane()))
        self.assertEqual(dossiers, (gardees - {manuelles[2]}) | {du_jour, manuelle})
        self.assertEqual(len([nom for nom in dossiers if MOTIF_MANUELLE.match(nom)]), 60)

    def test_manifeste_exact_dans_chaque_sauvegarde_et_ignore_par_la_restauration(self):
        parametres = csv_prevo("cle;valeur\nversion_schema;'%d\nnom_site;Atelier Été\n" % FORMAT_COURANT)
        equipements = csv_prevo("id;nom\nEQ-0001;Presse à injecter\nEQ-0002;Tour numérique\n")
        journal = csv_prevo("id;texte\nJ-1;première ligne\n")
        racine = {"parametres.csv": parametres, "equipements.csv": equipements, "journal.csv": journal}
        self.ouvrir_stockage(racine)
        self.page.evaluate("() => { window.App = { version: '9.8.7' }; }")      # version de l'appli (App absent ici)

        manuelle = self.reussir("sauvegarder")
        self.assertRegex(manuelle, MOTIF_MANUELLE)
        contenu = contenu_sauvegarde(self.instantane(), manuelle)
        self.assertEqual(set(contenu), set(racine) | {MANIFESTE})                  # aucun « .en-cours » laissé
        self.verifier_manifeste(contenu[MANIFESTE], racine, "manuelle", FORMAT_COURANT, version="9.8.7")

        # Quotidienne (première écriture du jour) : l'état d'avant l'écriture.
        nouveaux_equipements = csv_prevo("id;nom\nEQ-0001;Presse modifiée\n")
        self.reussir("enregistrer", "equipements", {"texte": nouveaux_equipements[3:].decode("utf-8")},
                     empreinte(equipements))
        apres = self.instantane()
        jour = [nom for nom in dossiers_de_sauvegarde(apres) if MOTIF_QUOTIDIENNE.match(nom)]
        self.assertEqual(len(jour), 1)
        self.verifier_manifeste(contenu_sauvegarde(apres, jour[0])[MANIFESTE], racine, "quotidienne", FORMAT_COURANT, version="9.8.7")

        # À motif : le motif est écrit tel quel.
        actuel = dict(racine, **{"equipements.csv": apres["equipements.csv"]})
        a_motif = self.reussir("sauvegarder", "avant-format-v3")
        self.verifier_manifeste(contenu_sauvegarde(self.instantane(), a_motif)[MANIFESTE], actuel, "avant-format-v3", FORMAT_COURANT,
                                version="9.8.7")

        # Restauration : manifeste.json n'est jamais copié dans les données ; la copie de sécurité a le sien.
        resultat = self.reussir("restaurer", manuelle)
        self.assertEqual(sorted(resultat["restaurees"]), ["equipements", "journal", "parametres"])
        restaure = self.instantane()
        self.assertNotIn(MANIFESTE, restaure)
        self.assertEqual(csv_de_la_racine(restaure), racine)
        securite = contenu_sauvegarde(restaure, resultat["copieSecurite"])
        self.verifier_manifeste(securite[MANIFESTE], actuel, "avant-restauration", FORMAT_COURANT, version="9.8.7")
        liste = {s["nom"]: s["tables"] for s in self.reussir("listerSauvegardes")}
        self.assertEqual(sorted(liste[manuelle]), ["equipements", "journal", "parametres"])

    def test_avant_import_zip_copie_aussi_les_documents(self):
        parametres = csv_prevo("cle;valeur\nversion_schema;'%d\n" % FORMAT_COURANT)
        equipements = csv_prevo("id;nom;document\nEQ-0001;Presse;notice.pdf\n")
        racine = {"parametres.csv": parametres, "equipements.csv": equipements}
        documents = {"documents/photo-presse.png": bytes(range(256)) * 3,
                     "documents/notice.pdf": b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\n"}
        sous_dossier = {"documents/archives/ancien.txt": b"dans un sous-dossier : pas un document\r\n"}
        self.ouvrir_stockage(dict(racine, **documents, **sous_dossier))

        nom = self.reussir("sauvegarder", "avant-import-zip")
        self.assertRegex(nom, r"^\d{4}-\d{2}-\d{2}_\d{6}_avant-import-zip$")
        contenu = contenu_sauvegarde(self.instantane(), nom)
        self.assertEqual(set(contenu), set(racine) | set(documents) | {MANIFESTE})
        for chemin, octets in dict(racine, **documents).items():
            self.assertEqual(contenu[chemin], octets, chemin)                      # à l'octet
        self.verifier_manifeste(contenu[MANIFESTE], dict(racine, **documents), "avant-import-zip", FORMAT_COURANT, version=None)
        self.assertIn(nom, [s["nom"] for s in self.reussir("listerSauvegardes")])

        # Une sauvegarde manuelle ne copie pas documents/ (les documents ne sont que dans « avant-import-zip »).
        manuelle = self.reussir("sauvegarder")
        self.assertEqual(set(contenu_sauvegarde(self.instantane(), manuelle)), set(racine) | {MANIFESTE})


# ---------------------------------------------------------------------------
# avant-mise-a-jour (application entière)
# ---------------------------------------------------------------------------

class TestAvantMiseAJour(CasSauvegardesDossier):

    def test_premier_demarrage_f2_v1_1_0_sauvegarde_d_origine_note_puis_passage_au_format_3(self):
        origine = fichiers_du_jeu("f2-v1.1.0")
        self.assertNotIn(DERNIERE_VERSION, origine)
        csv_origine = csv_de_la_racine(origine)
        self.ouvrir_app(origine)
        apres = self.instantane()
        dossiers = dossiers_de_sauvegarde(apres)

        # Une sauvegarde « avant-mise-a-jour » avec les octets d'ORIGINE (format 2), « de » inconnu.
        maj = [nom for nom in dossiers if MOTIF_AVANT_MISE_A_JOUR.match(nom)]
        self.assertEqual(len(maj), 1, dossiers)
        contenu = contenu_sauvegarde(apres, maj[0])
        brut = contenu.pop(MANIFESTE)
        self.assertEqual(contenu, csv_origine)
        self.verifier_manifeste(brut, csv_origine, "avant-mise-a-jour", 2,
                                complements=[("de", None), ("vers", VERSION_APPLI)])
        self.verifier_note(apres)

        # Puis le passage au format 3 (T186) : sa sauvegarde « avant-format-v3 » vient après, avec les mêmes octets.
        self.assertIn(b"version_schema;'%d" % FORMAT_COURANT, apres["parametres.csv"])
        avant_format = [nom for nom in dossiers if MOTIF_AVANT_FORMAT.match(nom)]
        self.assertEqual(len(avant_format), 1, dossiers)
        self.assertLessEqual(maj[0][:17], avant_format[0][:17])
        for nom in dossiers:
            self.assertTrue(nom in maj + avant_format or MOTIF_QUOTIDIENNE.match(nom), dossiers)
            copie = contenu_sauvegarde(apres, nom)
            self.assertEqual({c: o for c, o in copie.items() if c != MANIFESTE}, csv_origine, nom)
        nouveaux = {chemin for chemin in set(apres) - set(origine) if not chemin.startswith("sauvegardes/")}
        self.assertEqual(nouveaux, {VERROU, DERNIERE_VERSION})

        # Seconde ouverture : rien n'est écrit (verrou.txt mis à part).
        self.rouvrir_app()
        self.assertEqual(sans_verrou(self.instantane()), sans_verrou(apres))

    def test_premier_demarrage_f3_v1_2_0_version_notee_differente(self):
        origine = fichiers_du_jeu("f3-v1.2.0")
        origine[DERNIERE_VERSION] = b'{"version": "1.2.0", "depuis": "2026-01-05T08:00:00"}\r\n'
        csv_origine = csv_de_la_racine(origine)
        self.ouvrir_app(origine)
        apres = self.instantane()

        # Seule la sauvegarde « avant-mise-a-jour » (rien à passer au format 3, aucune écriture de CSV).
        dossiers = dossiers_de_sauvegarde(apres)
        self.assertEqual(len(dossiers), 1, dossiers)
        self.assertRegex(dossiers[0], MOTIF_AVANT_MISE_A_JOUR)
        contenu = contenu_sauvegarde(apres, dossiers[0])
        brut = contenu.pop(MANIFESTE)
        self.assertEqual(contenu, csv_origine)
        self.verifier_manifeste(brut, csv_origine, "avant-mise-a-jour", FORMAT_COURANT,
                                complements=[("de", "1.2.0"), ("vers", VERSION_APPLI)])
        self.verifier_note(apres)
        self.assertEqual(csv_de_la_racine(apres), csv_origine)

        self.rouvrir_app()
        self.assertEqual(sans_verrou(self.instantane()), sans_verrou(apres))

    def test_meme_version_notee_rien_n_est_ecrit(self):
        origine = fichiers_du_jeu("f3-v1.2.0")
        origine[DERNIERE_VERSION] = json.dumps({"version": VERSION_APPLI, "depuis": "2026-10-28T09:00:00"}).encode("utf-8")
        self.ouvrir_app(origine)
        self.assertEqual(sans_verrou(self.instantane()), origine)

    def test_donnees_plus_recentes_lecture_seule_aucun_octet_ecrit(self):
        origine = fichiers_du_jeu("plus-recent")
        self.ouvrir_app(origine)
        self.page.wait_for_load_state("networkidle")
        self.assertTrue(self.page.evaluate("Donnees.lectureSeule()"))
        self.assertEqual(self.instantane(), origine)                  # ni sauvegarde, ni derniere-version.json

    def test_echec_bandeau_l_application_continue_puis_nouvel_essai(self):
        origine = fichiers_du_jeu("f3-v1.2.0")
        # Un FICHIER « sauvegardes » empêche de créer le dossier des sauvegardes.
        origine["sauvegardes"] = b"un fichier a la place du dossier des sauvegardes\r\n"
        self.ouvrir_app(origine)
        alertes = self.page.inner_text("#alertes-app")
        self.assertIn("avant la mise à jour de Prévo", alertes)
        self.assertIn("n'a pas pu être faite", alertes)
        self.assertIn("prochaine ouverture", alertes)
        self.assertGreater(self.page.evaluate("Donnees.lignes('equipements').length"), 0)
        self.assertEqual(sans_verrou(self.instantane()), origine)     # derniere-version.json pas écrit

        # Le fichier retiré, l'ouverture suivante fait la sauvegarde puis note la version.
        self.page.evaluate("""async (nom) => {
            await (await (await navigator.storage.getDirectory()).getDirectoryHandle(nom)).removeEntry('sauvegardes');
        }""", NOM_DOSSIER)
        self.rouvrir_app()
        apres = self.instantane()
        self.assertEqual(len([nom for nom in dossiers_de_sauvegarde(apres) if MOTIF_AVANT_MISE_A_JOUR.match(nom)]), 1)
        self.verifier_note(apres)
        self.assertEqual(self.page.inner_text("#alertes-app").count("avant la mise à jour"), 0)

    def test_base_vide_version_notee_sans_sauvegarde_avant_mise_a_jour(self):
        preregler_profil(self.contexte, "demandeur", nom="Lucie Essai")
        self.page.goto(self.statique.url + "/index.html")
        self.page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        self.page.click("#btn-dossier")
        self.page.wait_for_selector("#ecran-base-vide", state="visible")
        self.page.click("#btn-base-vide")
        attendre_pret(self.page)
        apres = self.instantane()
        self.verifier_note(apres)
        self.assertEqual([nom for nom in dossiers_de_sauvegarde(apres) if "avant-" in nom], [])
        self.rouvrir_app()
        self.assertEqual([nom for nom in dossiers_de_sauvegarde(self.instantane()) if "avant-" in nom], [])


# ---------------------------------------------------------------------------
# Libellés (Paramètres › Sauvegardes)
# ---------------------------------------------------------------------------

class TestLibelles(CasSauvegardesDossier):

    def test_libelles_des_sauvegardes_avant_import_zip_et_avant_mise_a_jour(self):
        self.ouvrir_app(fichiers_du_jeu("f3-v1.2.0"), profil="responsable")
        types = self.page.evaluate("(noms) => noms.map((nom) => Parametres.decrireSauvegarde(nom).type)", [
            "2026-11-04_101500_avant-import-zip", "2026-11-04_101500_avant-mise-a-jour", "2026-11-04_101500_avant-import",
            "2026-11-04_101500_avant-format-v3", "2026-11-04_101500_avant-restauration", "2026-11-04_101500",
            "2026-11-04"])
        self.assertEqual(types, ["Avant un import ZIP", "Avant la mise à jour de Prévo", "Avant import", "Avant format 3",
                                 "Copie de sécurité", "Manuelle", "Quotidienne"])
        self.assertRegex(self.page.evaluate("App.adaptateur.sauvegarder('avant-import-zip')"), r"_avant-import-zip$")
        self.page.evaluate("location.hash = '#/parametres'")
        self.page.wait_for_function("""() => {
            const carte = document.getElementById('carte-sauvegardes');
            return Boolean(carte) && carte.innerText.includes('Avant un import ZIP');
        }""")
        carte = self.page.inner_text("#carte-sauvegardes")
        self.assertIn("Avant la mise à jour de Prévo", carte)


if __name__ == "__main__":
    unittest.main()
