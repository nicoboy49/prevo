"""Tests de StockageDossier (js/stockage-dossier.js, ARCHITECTURE.md §6).

Le « dossier » est simulé : installer_dossier_simule() remplace showDirectoryPicker par un
sous-dossier de l'OPFS du navigateur, qui offre la même API que le vrai système de fichiers
(getFileHandle, createWritable, keepExistingData, seek, values, removeEntry). L'OPFS n'existe
qu'en http://127.0.0.1 : la page de test est donc servie par ServeurStatique.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_stockage_dossier.py" -v
"""
import hashlib
import re
import unittest

from commun import CasNavigateur, RACINE, ServeurStatique, installer_dossier_simule

PAGE = "/tests/fixtures/page-stockage-dossier.html"
NOM_DOSSIER_SIMULE = "donnees-test"
BOM = b"\xef\xbb\xbf"
# T232 (texte de Nicolas, le même que serveur.py) : fichier ouvert dans Excel, nommé ; repli si le nom n'est pas connu.
MESSAGE_FICHIER_OUVERT = "Le fichier « %s » est ouvert dans Excel ou un autre logiciel : fermez-le, puis réessayez."
MESSAGE_FICHIER_OUVERT_SANS_NOM = ("Un fichier du dossier de données est ouvert dans Excel ou un autre logiciel : "
                                   "fermez-le, puis réessayez.")

# Petits outils JavaScript ajoutés à la page de test (rien de tout cela n'est dans le code testé).
AIDE_JS = """
window.aide = (() => {
  const nomDossier = %s;

  async function dossier(chemin) {
    let courant = await (await navigator.storage.getDirectory()).getDirectoryHandle(nomDossier, { create: true });
    for (const morceau of chemin.split('/').filter(Boolean)) {
      courant = await courant.getDirectoryHandle(morceau);
    }
    return courant;
  }
  function separer(chemin) {
    const morceaux = chemin.split('/');
    return { dossier: morceaux.slice(0, -1).join('/'), fichier: morceaux[morceaux.length - 1] };
  }
  async function lireOpfs(chemin) {
    const { dossier: nomDossierParent, fichier } = separer(chemin);
    try {
      const poignee = await (await dossier(nomDossierParent)).getFileHandle(fichier);
      return Array.from(new Uint8Array(await (await poignee.getFile()).arrayBuffer()));
    } catch (erreur) {
      if (erreur.name === 'NotFoundError') { return null; }
      throw erreur;
    }
  }
  async function ecrireOpfs(chemin, octets) {
    const { dossier: nomDossierParent, fichier } = separer(chemin);
    const poignee = await (await dossier(nomDossierParent)).getFileHandle(fichier, { create: true });
    const flux = await poignee.createWritable();
    await flux.write(new Uint8Array(octets));
    await flux.close();
  }
  async function listerOpfs(chemin) {
    const noms = [];
    try {
      for await (const entree of (await dossier(chemin)).values()) { noms.push(entree.name); }
    } catch (erreur) {
      if (erreur.name === 'NotFoundError') { return null; }
      throw erreur;
    }
    return noms.sort();
  }
  function deux(n) { return (n < 10 ? '0' : '') + n; }
  function dateDuJour() {
    const d = new Date();
    return d.getFullYear() + '-' + deux(d.getMonth() + 1) + '-' + deux(d.getDate());
  }
  function dateHeure(decalageMs) {
    const d = new Date(Date.now() + (decalageMs || 0));
    return d.getFullYear() + '-' + deux(d.getMonth() + 1) + '-' + deux(d.getDate())
      + ' ' + deux(d.getHours()) + ':' + deux(d.getMinutes()) + ':' + deux(d.getSeconds());
  }

  // Arguments venus de Python : { __octets: [...] } -> Uint8Array ; { __blob: [...] } -> Blob.
  function revivre(valeur) {
    if (valeur && valeur.__octets) { return new Uint8Array(valeur.__octets); }
    if (valeur && valeur.__blob) { return new Blob([new Uint8Array(valeur.__blob)]); }
    return valeur;
  }
  // Résultats renvoyés à Python : Uint8Array et Blob deviennent { octets: [...] }.
  async function serialiser(valeur) {
    if (valeur instanceof Uint8Array) { return { octets: Array.from(valeur) }; }
    if (valeur instanceof Blob) { return { octets: Array.from(new Uint8Array(await valeur.arrayBuffer())) }; }
    if (Array.isArray(valeur)) { return Promise.all(valeur.map(serialiser)); }
    if (valeur && typeof valeur === 'object') {
      const copie = {};
      for (const cle of Object.keys(valeur)) { copie[cle] = await serialiser(valeur[cle]); }
      return copie;
    }
    return valeur;
  }
  async function appeler(methode, args) {
    try {
      const valeur = await window.dos[methode](...args.map(revivre));
      return { ok: true, valeur: await serialiser(valeur) };
    } catch (erreur) {
      return { ok: false, nom: erreur.name, message: erreur.message, versionActuelle: erreur.versionActuelle };
    }
  }
  return { lireOpfs, ecrireOpfs, listerOpfs, dateDuJour, dateHeure, appeler };
})();
""" % ('"%s"' % NOM_DOSSIER_SIMULE)

# Enveloppe d'un dossier OPFS pour simuler un « autre poste » qui écrit au pire moment.
# window.crochets (modifiable depuis les tests) :
#   avantCreateWritable(nom) : appelé avant chaque createWritable d'un fichier de la racine ;
#   ecritureEnEchec(nom)     : vrai → le flux rendu échoue à l'écriture (NoModificationAllowedError) ;
#   avantGetFileHandle(nom)  : appelé avant chaque getFileHandle de la racine ;
#   avantGetDirectoryHandle(nom, options) : appelé avant chaque getDirectoryHandle de la racine.
# aide.autrePoste(nom, texte, ajout) écrit directement dans le vrai dossier (ajout = en fin).
ENVELOPPE_JS = """
(() => {
  window.crochets = {};
  function enveloppeFichier(nom, vraie) {
    return {
      kind: 'file', name: vraie.name,
      getFile: () => vraie.getFile(),
      createWritable: async (options) => {
        if (crochets.avantCreateWritable) { await crochets.avantCreateWritable(nom); }
        const flux = await vraie.createWritable(options);
        if (crochets.ecritureEnEchec && crochets.ecritureEnEchec(nom)) {
          return {
            seek: (p) => flux.seek(p),
            write: async () => {
              const erreur = new Error('écriture refusée (simulée)');
              erreur.name = 'NoModificationAllowedError';
              throw erreur;
            },
            close: () => flux.close(),
            abort: () => flux.abort(),
          };
        }
        return flux;
      },
    };
  }
  aide.vraiDossier = async () => (await navigator.storage.getDirectory()).getDirectoryHandle(%s, { create: true });
  aide.envelopper = (vrai) => ({
    name: vrai.name, kind: 'directory',
    getFileHandle: async (nom, options) => {
      if (crochets.avantGetFileHandle) { await crochets.avantGetFileHandle(nom); }
      return enveloppeFichier(nom, await vrai.getFileHandle(nom, options));
    },
    getDirectoryHandle: async (nom, options) => {
      if (crochets.avantGetDirectoryHandle) { await crochets.avantGetDirectoryHandle(nom, options); }
      return vrai.getDirectoryHandle(nom, options);
    },
    removeEntry: (nom, options) => vrai.removeEntry(nom, options),
    values: () => vrai.values(),
  });
  aide.autrePoste = async (nom, texte, ajout) => {
    const poignee = await (await aide.vraiDossier()).getFileHandle(nom, { create: true });
    const taille = (await poignee.getFile()).size;
    const flux = await poignee.createWritable({ keepExistingData: Boolean(ajout) });
    if (ajout) { await flux.seek(taille); }
    await flux.write(new TextEncoder().encode(texte));
    await flux.close();
  };
})();
""" % ('"%s"' % NOM_DOSSIER_SIMULE)


def empreinte(octets):
    """Version attendue : SHA-256 du contenu, 16 premiers caractères hexadécimaux."""
    return hashlib.sha256(octets).hexdigest()[:16]


def csv(texte):
    """Contenu d'un CSV de Prévo : BOM UTF-8, CRLF."""
    return BOM + texte.replace("\n", "\r\n").encode("utf-8")


def octets_js(octets):
    return {"__octets": list(octets)}


def revenir_en_python(valeur):
    """{ octets: [...] } -> bytes, récursivement."""
    if isinstance(valeur, dict):
        if set(valeur.keys()) == {"octets"}:
            return bytes(valeur["octets"])
        return {cle: revenir_en_python(v) for cle, v in valeur.items()}
    if isinstance(valeur, list):
        return [revenir_en_python(v) for v in valeur]
    return valeur


class TestStockageDossier(CasNavigateur):

    def setUp(self):
        super().setUp()
        self.statique = ServeurStatique(RACINE)
        self.statique.demarrer()
        self.addCleanup(self.statique.arreter)
        installer_dossier_simule(self.contexte, NOM_DOSSIER_SIMULE)
        self.ouvrir(self.page)

    # -- aides ----------------------------------------------------------------------------

    def ouvrir(self, page, recharger=False):
        """Charge la page de test et y ajoute les outils JavaScript."""
        if recharger:
            page.reload()
        else:
            page.goto(self.statique.url + PAGE)
        page.add_script_tag(content=AIDE_JS)
        page.add_script_tag(content=ENVELOPPE_JS)

    def choisir_dossier_enveloppe(self, page=None, poste="Poste A"):
        """Comme choisir_dossier, mais l'adaptateur travaille sur le dossier enveloppé (crochets)."""
        (page or self.page).evaluate("""async (poste) => {
            await StockageDossier.choisir();
            window.dos = await StockageDossier.creer(aide.envelopper(await aide.vraiDossier()), { poste: poste });
        }""", poste)

    def choisir_dossier(self, page=None, poste="Poste A"):
        """Choisit le dossier simulé et crée l'adaptateur (window.dos). Renvoie le libellé."""
        page = page or self.page
        return page.evaluate("""async (poste) => {
            const poignee = await StockageDossier.choisir();
            window.dos = await StockageDossier.creer(poignee, { poste: poste });
            return [window.dos.mode, window.dos.libelle];
        }""", poste)

    def appeler(self, methode, *arguments, page=None):
        resultat = (page or self.page).evaluate(
            "([methode, args]) => aide.appeler(methode, args)", [methode, list(arguments)])
        return revenir_en_python(resultat)

    def reussir(self, methode, *arguments, page=None):
        resultat = self.appeler(methode, *arguments, page=page)
        self.assertTrue(resultat["ok"], "%s a échoué : %s" % (methode, resultat))
        return resultat["valeur"]

    def echouer(self, methode, *arguments, page=None):
        resultat = self.appeler(methode, *arguments, page=page)
        self.assertFalse(resultat["ok"], "%s aurait dû échouer : %s" % (methode, resultat))
        return resultat

    def lire_opfs(self, chemin, page=None):
        valeur = (page or self.page).evaluate("(c) => aide.lireOpfs(c)", chemin)
        return None if valeur is None else bytes(valeur)

    def ecrire_opfs(self, chemin, octets, page=None):
        (page or self.page).evaluate("([c, o]) => aide.ecrireOpfs(c, o)", [chemin, list(octets)])

    def lister_opfs(self, chemin="", page=None):
        return (page or self.page).evaluate("(c) => aide.listerOpfs(c)", chemin)

    def date_du_jour(self):
        return self.page.evaluate("aide.dateDuJour()")

    def enregistrer(self, table, octets, version=None):
        return self.reussir("enregistrer", table, octets_js(octets), version)["version"]

    # -- choix du dossier, lecture ---------------------------------------------------------

    def test_choisir_dossier_vide_charger_donne_null(self):
        self.assertTrue(self.page.evaluate("StockageDossier.disponible()"))
        self.assertIsNone(self.page.evaluate("StockageDossier.poigneeMemorisee()"))
        mode, libelle = self.choisir_dossier()
        self.assertEqual(mode, "dossier")
        self.assertEqual(libelle, "Dossier « donnees-test »")
        self.assertEqual(self.reussir("charger", "equipements"), {"octets": None, "version": None})
        self.assertEqual(self.reussir("info"), {})

    def test_table_inconnue_refusee(self):
        self.choisir_dossier()
        erreur = self.echouer("charger", "table_inventee")
        self.assertEqual(erreur["nom"], "ErreurStockage")

    def test_ecrire_puis_relire_octets_et_version(self):
        self.choisir_dossier()
        contenu = csv("id;nom\nEQ-0001;Pompe é à\n")
        version = self.enregistrer("equipements", contenu, None)
        self.assertEqual(version, empreinte(contenu))
        self.assertEqual(self.lire_opfs("equipements.csv"), contenu)
        relu = self.reussir("charger", "equipements")
        self.assertEqual(relu["octets"], contenu)
        self.assertEqual(relu["version"], empreinte(contenu))
        # Remplacement avec la bonne version : le fichier est bien réécrit en entier.
        plus_court = csv("id;nom\n")
        version2 = self.enregistrer("equipements", plus_court, version)
        self.assertEqual(self.lire_opfs("equipements.csv"), plus_court)
        self.assertEqual(version2, empreinte(plus_court))

    def test_conflit_si_version_perimee(self):
        self.choisir_dossier()
        v1 = self.enregistrer("equipements", csv("id;nom\n1;a\n"), None)
        v2 = self.enregistrer("equipements", csv("id;nom\n1;b\n"), v1)

        perimee = self.echouer("enregistrer", "equipements", octets_js(csv("id;nom\n1;c\n")), v1)
        self.assertEqual(perimee["nom"], "ErreurConflit")
        self.assertEqual(perimee["versionActuelle"], v2)

        existe_deja = self.echouer("enregistrer", "equipements", octets_js(csv("id;nom\n")), None)
        self.assertEqual(existe_deja["nom"], "ErreurConflit")
        self.assertEqual(existe_deja["versionActuelle"], v2)

        disparu = self.echouer("enregistrer", "journal", octets_js(csv("id;nom\n")), "0123456789abcdef")
        self.assertEqual(disparu["nom"], "ErreurConflit")
        self.assertIsNone(disparu["versionActuelle"])

        # Rien n'a été écrasé par les tentatives refusées.
        self.assertEqual(self.lire_opfs("equipements.csv"), csv("id;nom\n1;b\n"))
        self.assertIsNone(self.lire_opfs("journal.csv"))

    # -- ajout (journal) -------------------------------------------------------------------

    def test_ajouter_creation_puis_ajout_en_fin(self):
        self.choisir_dossier()
        premier = b"id;texte\r\n1;premiere\r\n"
        version1 = self.reussir("ajouter", "journal", octets_js(premier))["version"]
        attendu1 = BOM + premier
        self.assertEqual(self.lire_opfs("journal.csv"), attendu1)
        self.assertEqual(version1, empreinte(attendu1))

        second = "id;texte\r\n2;seconde\r\n3;troisieme é\r\n".encode("utf-8")
        version2 = self.reussir("ajouter", "journal", octets_js(second))["version"]
        attendu2 = attendu1 + "2;seconde\r\n3;troisieme é\r\n".encode("utf-8")
        self.assertEqual(self.lire_opfs("journal.csv"), attendu2)
        self.assertEqual(version2, empreinte(attendu2))
        self.assertEqual(self.reussir("charger", "journal")["version"], version2)

        # Un corps sans ligne de données ne change rien.
        version3 = self.reussir("ajouter", "journal", octets_js(b"id;texte\r\n"))["version"]
        self.assertEqual(version3, version2)
        self.assertEqual(self.lire_opfs("journal.csv"), attendu2)

    def test_ajouter_a_un_fichier_sans_fin_de_ligne(self):
        self.choisir_dossier()
        self.enregistrer("journal", BOM + b"id;texte\r\n1;a", None)       # pas de CRLF final
        self.reussir("ajouter", "journal", octets_js(b"id;texte\r\n2;b\r\n"))
        self.assertEqual(self.lire_opfs("journal.csv"), BOM + b"id;texte\r\n1;a\r\n2;b\r\n")

    def test_ajouter_entete_different_est_un_conflit(self):
        self.choisir_dossier()
        contenu = csv("id;texte\n1;a\n")
        self.enregistrer("journal", contenu, None)
        erreur = self.echouer("ajouter", "journal", octets_js(b"id;autre\r\n2;b\r\n"))
        self.assertEqual(erreur["nom"], "ErreurConflit")
        self.assertEqual(erreur["versionActuelle"], empreinte(contenu))
        self.assertEqual(self.lire_opfs("journal.csv"), contenu)

    def test_ajouter_fichier_non_utf8_est_un_conflit(self):
        self.choisir_dossier()
        reenregistre_par_excel = b"id;texte\r\n1;caf\xe9\r\n"           # Windows-1252, pas UTF-8
        self.enregistrer("journal", reenregistre_par_excel, None)
        erreur = self.echouer("ajouter", "journal", octets_js(b"id;texte\r\n2;b\r\n"))
        self.assertEqual(erreur["nom"], "ErreurConflit")
        self.assertEqual(self.lire_opfs("journal.csv"), reenregistre_par_excel)

    def test_ajouter_a_un_fichier_vide_le_recree_avec_bom(self):
        self.choisir_dossier()
        self.ecrire_opfs("journal.csv", b"")
        self.reussir("ajouter", "journal", octets_js(b"id;texte\r\n1;a\r\n"))
        self.assertEqual(self.lire_opfs("journal.csv"), BOM + b"id;texte\r\n1;a\r\n")

    # -- documents -------------------------------------------------------------------------

    def test_documents_ecriture_lecture_et_refus_d_ecraser(self):
        self.choisir_dossier()
        png = b"\x89PNG\r\n\x1a\n" + bytes(range(50))
        self.assertEqual(self.reussir("ecrireDocument", "photo-1.png", {"__blob": list(png)}), "photo-1.png")
        self.assertEqual(self.lire_opfs("documents/photo-1.png"), png)
        self.assertEqual(self.reussir("lireDocument", "photo-1.png"), png)
        url = self.reussir("urlDocument", "photo-1.png")
        self.assertTrue(url.startswith("blob:"), url)

        erreur = self.echouer("ecrireDocument", "photo-1.png", {"__blob": [1, 2, 3]})
        self.assertEqual(erreur["nom"], "ErreurStockage")
        self.assertIn("existe déjà", erreur["message"])
        self.assertEqual(self.lire_opfs("documents/photo-1.png"), png)       # intact

        self.assertIsNone(self.reussir("lireDocument", "absent.png"))
        self.assertIsNone(self.reussir("urlDocument", "absent.png"))

    def test_documents_noms_invalides_refuses(self):
        self.choisir_dossier()
        for nom in ["../secret.png", "a/b.png", "a\\b.png", "a b.png", ".cache.png", "a..b.png",
                    "virus.exe", "sans-extension", "con.txt", "COM1.pdf", "é.png", "x" * 130 + ".png", ""]:
            with self.subTest(nom=nom):
                erreur = self.echouer("ecrireDocument", nom, {"__blob": [1]})
                self.assertEqual(erreur["nom"], "ErreurStockage")
        self.assertIsNone(self.lister_opfs("documents"))                    # rien n'a été créé

    def test_documents_html_acceptes_lot3(self):
        # Lot 3 (ARCHITECTURE.md §15.1) : le rapport mensuel figé est un document « .html » ;
        # « .htm » reste refusé, et un rapport n'est jamais écrasé.
        self.choisir_dossier()
        page_html = "<!doctype html><title>Rapport</title>".encode("utf-8")
        self.assertEqual(self.reussir("ecrireDocument", "rapport-mensuel-2026-09.html", {"__blob": list(page_html)}),
                         "rapport-mensuel-2026-09.html")
        self.assertEqual(self.lire_opfs("documents/rapport-mensuel-2026-09.html"), page_html)
        erreur = self.echouer("ecrireDocument", "rapport-mensuel-2026-09.html", {"__blob": [1]})
        self.assertIn("existe déjà", erreur["message"])
        self.assertEqual(self.echouer("ecrireDocument", "page.htm", {"__blob": [1]})["nom"], "ErreurStockage")

    def test_documents_html_ouverts_sans_executer_leurs_scripts(self):
        # Correction de relecture (lot 3) : l'URL d'un document .html est une page enveloppe qui
        # l'affiche dans un cadre isolé SANS scripts ; les autres documents restent tels quels.
        self.autoriser_erreur("Blocked script execution")      # le navigateur dit qu'il a bloqué le script
        self.choisir_dossier()
        piege = b'<p>Rapport</p><script>window.top.__piege = 1;</script>'
        self.reussir("ecrireDocument", "rapport-piege.html", {"__blob": list(piege)})
        url = self.reussir("urlDocument", "rapport-piege.html")
        resultat = self.page.evaluate("""async (adresse) => {
            const page = new DOMParser().parseFromString(await (await fetch(adresse)).text(), 'text/html');
            const cadre = document.createElement('iframe');
            cadre.src = adresse;
            await new Promise((resoudre) => { cadre.onload = resoudre; document.body.appendChild(cadre); });
            await new Promise((resoudre) => setTimeout(resoudre, 300));
            return { scripts: page.scripts.length, sandbox: page.querySelector('iframe').getAttribute('sandbox'),
                     piege: window.__piege === undefined ? null : window.__piege }; }""", url)
        self.assertEqual(resultat, {"scripts": 0, "sandbox": "allow-modals", "piege": None})
        self.assertTrue(any("Blocked script execution" in erreur for erreur in self.erreurs_console), self.erreurs_console)
        png = b"\x89PNG\r\n\x1a\n" + bytes(range(20))
        self.reussir("ecrireDocument", "photo-x.png", {"__blob": list(png)})
        url_png = self.reussir("urlDocument", "photo-x.png")
        self.assertEqual(self.page.evaluate("async (a) => Array.from(new Uint8Array(await (await fetch(a)).arrayBuffer()))", url_png), list(png))

    # -- sauvegardes -----------------------------------------------------------------------

    def test_sauvegarde_quotidienne_a_la_premiere_ecriture_du_jour(self):
        self.choisir_dossier()
        jour = self.date_du_jour()
        etat1 = csv("id;nom\n1;avant\n")
        etat2 = csv("id;nom\n1;apres\n")
        etat3 = csv("id;nom\n1;encore apres\n")

        # Première écriture ever : aucun CSV à sauvegarder, donc pas de sauvegarde.
        v1 = self.enregistrer("equipements", etat1, None)
        self.assertNotIn("sauvegardes", self.lister_opfs())

        # Première écriture suivante : la sauvegarde du jour contient l'état d'AVANT.
        v2 = self.enregistrer("equipements", etat2, v1)
        self.assertEqual(self.lister_opfs("sauvegardes"), [jour])
        self.assertEqual(self.lire_opfs("sauvegardes/%s/equipements.csv" % jour), etat1)

        # Les écritures suivantes du même jour ne la touchent plus.
        self.enregistrer("equipements", etat3, v2)
        self.assertEqual(self.lister_opfs("sauvegardes"), [jour])
        self.assertEqual(self.lire_opfs("sauvegardes/%s/equipements.csv" % jour), etat1)

    def test_sauvegarde_quotidienne_aussi_avant_un_ajout(self):
        self.choisir_dossier()
        jour = self.date_du_jour()
        etat = csv("id;nom\n1;a\n")
        self.enregistrer("equipements", etat, None)
        self.reussir("ajouter", "journal", octets_js(b"id;texte\r\n1;x\r\n"))
        self.assertEqual(self.lire_opfs("sauvegardes/%s/equipements.csv" % jour), etat)
        self.assertEqual(self.lister_opfs("sauvegardes/%s" % jour), ["equipements.csv", "manifeste.json"])   # T188

    def test_ecritures_simultanees_une_seule_sauvegarde_du_jour_complete(self):
        self.choisir_dossier()
        jour = self.date_du_jour()
        etat_equipements = csv("id;nom\n1;eq\n")
        etat_journal = csv("id;texte\n1;j\n")
        # Les deux fichiers existent déjà (posés directement dans le dossier) avant les écritures.
        self.ecrire_opfs("equipements.csv", etat_equipements)
        self.ecrire_opfs("journal.csv", etat_journal)
        self.page.evaluate("""async () => {
            const e = (t) => new TextEncoder().encode(t);
            const v = await window.dos.listerVersions();
            await Promise.all([
              window.dos.enregistrer('equipements', e('id;nom\\r\\n1;nouveau\\r\\n'), v.equipements),
              window.dos.enregistrer('journal', e('id;texte\\r\\n1;nouveau\\r\\n'), v.journal),
            ]);
        }""")
        self.assertEqual(self.lister_opfs("sauvegardes"), [jour])
        self.assertEqual(self.lire_opfs("sauvegardes/%s/equipements.csv" % jour), etat_equipements)
        self.assertEqual(self.lire_opfs("sauvegardes/%s/journal.csv" % jour), etat_journal)

    def test_sauvegarde_manuelle_liste_et_restauration(self):
        self.choisir_dossier()
        jour = self.date_du_jour()
        equipements_v1 = csv("id;nom\n1;un\n")
        journal_v1 = csv("id;texte\n1;j\n")
        ve = self.enregistrer("equipements", equipements_v1, None)
        self.enregistrer("journal", journal_v1, None)

        nom = self.reussir("sauvegarder")
        self.assertRegex(nom, r"^\d{4}-\d{2}-\d{2}_\d{6}$")
        self.assertTrue(nom.startswith(jour))
        self.assertEqual(self.lire_opfs("sauvegardes/%s/equipements.csv" % nom), equipements_v1)
        self.assertEqual(self.lire_opfs("sauvegardes/%s/journal.csv" % nom), journal_v1)

        # On modifie les deux tables, puis on restaure seulement « equipements ».
        equipements_v2 = csv("id;nom\n1;deux\n")
        journal_v2 = csv("id;texte\n1;j\n2;k\n")
        self.enregistrer("equipements", equipements_v2, ve)
        self.enregistrer("journal", journal_v2, empreinte(journal_v1))

        liste = self.reussir("listerSauvegardes")
        noms = [s["nom"] for s in liste]
        self.assertIn(nom, noms)
        self.assertIn(jour, noms)                                            # sauvegarde quotidienne
        self.assertEqual(noms, sorted(noms, reverse=True))                   # la plus récente d'abord
        self.assertEqual([s for s in liste if s["nom"] == nom][0]["tables"], ["equipements", "journal"])

        resultat = self.reussir("restaurer", nom, ["equipements"])
        self.assertEqual(resultat["restaurees"], ["equipements"])
        self.assertRegex(resultat["copieSecurite"], r"^\d{4}-\d{2}-\d{2}_\d{6}_avant-restauration$")
        self.assertEqual(self.lire_opfs("equipements.csv"), equipements_v1)           # restauré
        self.assertEqual(self.lire_opfs("journal.csv"), journal_v2)                   # intact
        copie = resultat["copieSecurite"]                                             # état d'avant
        self.assertEqual(self.lire_opfs("sauvegardes/%s/equipements.csv" % copie), equipements_v2)
        self.assertEqual(self.lire_opfs("sauvegardes/%s/journal.csv" % copie), journal_v2)
        self.assertEqual(self.reussir("charger", "equipements")["version"], empreinte(equipements_v1))

        # Restauration complète (sans liste de tables).
        resultat2 = self.reussir("restaurer", nom)
        self.assertEqual(resultat2["restaurees"], ["equipements", "journal"])
        self.assertEqual(self.lire_opfs("journal.csv"), journal_v1)
        self.assertNotEqual(resultat2["copieSecurite"], copie)
        self.assertEqual(self.lire_opfs("sauvegardes/%s/journal.csv" % resultat2["copieSecurite"]), journal_v2)

    def test_restauration_refus(self):
        self.choisir_dossier()
        self.enregistrer("equipements", csv("id;nom\n1;a\n"), None)
        nom = self.reussir("sauvegarder")
        for argument in [("../etc",), ("2000-01-01",), ("2000-01-01_000000",), (nom, ["table_inventee"]),
                         (nom, ["journal"]), (nom, "equipements")]:
            with self.subTest(argument=argument):
                erreur = self.echouer("restaurer", *argument)
                self.assertEqual(erreur["nom"], "ErreurStockage")
        # Aucune copie de sécurité n'a été faite pour les refus.
        self.assertEqual([n for n in self.lister_opfs("sauvegardes") if "avant-restauration" in n], [])

    def test_liste_des_sauvegardes_vide_sans_dossier(self):
        self.choisir_dossier()
        self.assertEqual(self.reussir("listerSauvegardes"), [])

    # -- versions --------------------------------------------------------------------------

    def test_lister_versions(self):
        self.choisir_dossier()
        avant = self.reussir("listerVersions")
        noms = self.page.evaluate("Schema.nomsTables()")
        self.assertEqual(len(noms), 24)
        self.assertEqual(sorted(avant.keys()), sorted(noms))
        self.assertTrue(all(v is None for v in avant.values()))

        contenu = csv("id;nom\n1;a\n")
        self.enregistrer("equipements", contenu, None)
        apres = self.reussir("listerVersions")
        self.assertEqual(apres["equipements"], empreinte(contenu))
        self.assertEqual([t for t, v in apres.items() if v is not None], ["equipements"])

    # -- reprise du dossier après rechargement ----------------------------------------------

    def test_reprendre_le_dossier_apres_rechargement(self):
        self.choisir_dossier()
        contenu = csv("id;nom\nEQ-0001;Pompe\n")
        self.enregistrer("equipements", contenu, None)

        self.ouvrir(self.page, recharger=True)
        self.assertEqual(self.page.evaluate("StockageDossier.poigneeMemorisee()"), {"nom": NOM_DOSSIER_SIMULE})
        libelle = self.page.evaluate("""async () => {
            const poignee = await StockageDossier.reprendre();
            if (!poignee) { return null; }
            window.dos = await StockageDossier.creer(poignee, { poste: 'Poste A' });
            return window.dos.libelle;
        }""")
        self.assertEqual(libelle, "Dossier « donnees-test »")
        relu = self.reussir("charger", "equipements")
        self.assertEqual(relu["octets"], contenu)
        self.assertEqual(relu["version"], empreinte(contenu))

    def test_reprendre_renvoie_null_si_permission_refusee(self):
        self.choisir_dossier()
        self.ouvrir(self.page, recharger=True)
        resultat = self.page.evaluate("""async () => {
            FileSystemHandle.prototype.queryPermission = async () => 'prompt';
            FileSystemHandle.prototype.requestPermission = async () => 'denied';
            return StockageDossier.reprendre();
        }""")
        self.assertIsNone(resultat)

    def test_reprendre_sans_dossier_memorise(self):
        self.assertIsNone(self.page.evaluate("StockageDossier.reprendre()"))

    # -- verrou ----------------------------------------------------------------------------

    def test_verrou_vu_par_une_seconde_session(self):
        self.choisir_dossier(poste="Poste A")
        self.assertEqual(self.reussir("verifierVerrou"), {"autreSession": None})   # pas de verrou
        self.reussir("demarrerVerrou")
        contenu = self.lire_opfs("verrou.txt").decode("utf-8")
        self.assertRegex(contenu, r"^Poste A;\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2};[a-z0-9]+$")
        self.assertEqual(self.reussir("verifierVerrou"), {"autreSession": None})   # son propre verrou

        seconde = self.contexte.new_page()
        self.surveiller(seconde)
        self.ouvrir(seconde)
        self.choisir_dossier(page=seconde, poste="Poste B")
        verrou = self.reussir("verifierVerrou", page=seconde)["autreSession"]
        self.assertEqual(verrou["poste"], "Poste A")
        self.assertRegex(verrou["heure"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
        self.reussir("arreterVerrou", page=seconde)
        self.reussir("arreterVerrou")
        seconde.close()

    def test_verrou_ancien_ou_illisible_ignore(self):
        self.choisir_dossier(poste="Poste A")
        recent = self.page.evaluate("aide.dateHeure(-60 * 1000)")
        self.ecrire_opfs("verrou.txt", ("Poste X;%s;autre-session" % recent).encode("utf-8"))
        self.assertEqual(self.reussir("verifierVerrou")["autreSession"]["poste"], "Poste X")

        # Le même verrou, 10 minutes plus tard (horloge de la page avancée) : abandonné.
        self.page.evaluate("""() => {
            const vraiNow = Date.now.bind(Date);
            Date.now = () => vraiNow() + 10 * 60 * 1000;
        }""")
        self.assertEqual(self.reussir("verifierVerrou"), {"autreSession": None})

        self.ecrire_opfs("verrou.txt", b"n'importe quoi")
        self.assertEqual(self.reussir("verifierVerrou"), {"autreSession": None})

    def test_verrou_d_un_pc_dont_l_horloge_retarde(self):
        """L'autre PC écrit une heure en retard de 10 min, mais son verrou vient d'être écrit :
        c'est la date de modification du fichier qui compte, pas le texte."""
        self.choisir_dossier(poste="Poste A")
        en_retard = self.page.evaluate("aide.dateHeure(-10 * 60 * 1000)")
        self.ecrire_opfs("verrou.txt", ("Poste X;%s;autre-session" % en_retard).encode("utf-8"))
        verrou = self.reussir("verifierVerrou")["autreSession"]
        self.assertIsNotNone(verrou, "verrou récent ignoré à cause de l'horloge de l'autre PC")
        self.assertEqual(verrou["poste"], "Poste X")
        self.assertEqual(verrou["heure"], en_retard)

    def test_poste_sans_point_virgule_dans_le_verrou(self):
        self.choisir_dossier(poste="Atelier;nord\nbis")
        self.reussir("demarrerVerrou")
        self.assertRegex(self.lire_opfs("verrou.txt").decode("utf-8"),
                         r"^Atelier nord bis;\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2};[a-z0-9]+$")
        self.reussir("arreterVerrou")

    # -- concurrence avec un autre poste (relecture vague 3) -------------------------------

    ENTETE_JOURNAL = "id;date_heure;poste;profil;table;id_ligne;action"
    LIGNE_AUTRE = "J-AUTRE-POSTE-LIGNE-LONGUE;2026-10-19 10:00;autre;autre;t;x;action de l autre poste\r\n"

    def ligne_journal(self, identifiant):
        return "%s;2026-10-19 10:00;p;p;t;x;a\r\n" % identifiant

    def corps_journal(self, identifiant):
        return octets_js((self.ENTETE_JOURNAL + "\r\n" + self.ligne_journal(identifiant)).encode("utf-8"))

    def test_ajout_en_fin_n_ecrase_pas_la_ligne_d_un_autre_poste(self):
        """CRITIQUE 1 : un autre poste ajoute une ligne entre notre lecture et notre écriture."""
        self.choisir_dossier_enveloppe()
        self.reussir("ajouter", "journal", self.corps_journal("J-1"))
        self.reussir("ajouter", "journal", self.corps_journal("J-2"))      # sauvegarde du jour faite
        self.page.evaluate("""(ligne) => {
            let fait = false;
            crochets.avantCreateWritable = async (nom) => {
                if (nom === 'journal.csv' && !fait) { fait = true; await aide.autrePoste('journal.csv', ligne, true); }
            };
        }""", self.LIGNE_AUTRE)
        resultat = self.appeler("ajouter", "journal", self.corps_journal("J-MOI"))
        self.page.evaluate("() => { crochets.avantCreateWritable = null; }")

        avant = BOM + (self.ENTETE_JOURNAL + "\r\n" + self.ligne_journal("J-1") + self.ligne_journal("J-2")
                       + self.LIGNE_AUTRE).encode("utf-8")
        fichier = self.lire_opfs("journal.csv")
        if resultat["ok"]:
            self.assertEqual(fichier, avant + self.ligne_journal("J-MOI").encode("utf-8"))
        else:
            self.assertEqual(resultat["nom"], "ErreurConflit", resultat)
            self.assertEqual(fichier, avant, "la ligne de l'autre poste a été abîmée")

    def test_ajout_concurrent_via_donnees_le_repli_garde_les_deux_lignes(self):
        """CRITIQUE 1, de bout en bout : Donnees.journaliser se replie sur modifier et rien n'est perdu."""
        self.choisir_dossier_enveloppe()
        self.reussir("ajouter", "journal", self.corps_journal("J-1"))
        self.reussir("ajouter", "journal", self.corps_journal("J-2"))
        resultat = self.page.evaluate("""async (ligne) => {
            Donnees.initialiser(window.dos, { poste: 'A', profil: 'P' });
            await Donnees.chargerTout();
            let fait = false;
            crochets.avantCreateWritable = async (nom) => {
                if (nom === 'journal.csv' && !fait) { fait = true; await aide.autrePoste('journal.csv', ligne, true); }
            };
            const id = await Donnees.journaliser('equipements', 'EQ-0001', 'essai');
            crochets.avantCreateWritable = null;
            const lu = Donnees.csv.analyser('journal', (await window.dos.charger('journal')).octets);
            return { id: id, ids: lu.lignes.map((l) => l.id), problemes: lu.problemes.length };
        }""", self.LIGNE_AUTRE)
        self.assertIsNotNone(resultat["id"])
        self.assertEqual(resultat["ids"], ["J-1", "J-2", "J-AUTRE-POSTE-LIGNE-LONGUE", resultat["id"]])
        self.assertEqual(resultat["problemes"], 0)

    def test_ecriture_d_un_autre_poste_pendant_la_sauvegarde_du_jour_donne_un_conflit(self):
        """CRITIQUE 2 : un autre poste écrit pendant la sauvegarde quotidienne."""
        self.choisir_dossier_enveloppe()
        v1 = self.enregistrer("equipements", csv("id;nom\nEQ-0001;a\n"), None)   # pas de sauvegarde (1re fois)
        self.assertIsNone(self.lister_opfs("sauvegardes"))
        autre = csv("id;nom\nEQ-0001;a\nEQ-0002;ajout autre poste\n")
        self.page.evaluate("""(texte) => {
            let fait = false;
            crochets.avantGetDirectoryHandle = async (nom, options) => {
                if (nom === 'sauvegardes' && options && options.create && !fait) {
                    fait = true;
                    await aide.autrePoste('equipements.csv', texte, false);
                }
            };
        }""", autre.decode("utf-8"))
        resultat = self.appeler("enregistrer", "equipements", octets_js(csv("id;nom\nEQ-0001;modifié\n")), v1)
        self.assertFalse(resultat["ok"], "écriture de l'autre poste écrasée sans conflit : %s" % resultat)
        self.assertEqual(resultat["nom"], "ErreurConflit")
        self.assertEqual(resultat["versionActuelle"], empreinte(autre))
        self.assertEqual(self.lire_opfs("equipements.csv"), autre)

    def test_ecriture_d_un_autre_poste_juste_avant_la_notre_donne_un_conflit(self):
        """CRITIQUE 2 (fenêtre finale) : l'autre poste écrit après notre contrôle de version."""
        self.choisir_dossier_enveloppe()
        v1 = self.enregistrer("equipements", csv("id;nom\nEQ-0001;a\n"), None)
        v2 = self.enregistrer("equipements", csv("id;nom\nEQ-0001;b\n"), v1)       # sauvegarde du jour faite
        autre = csv("id;nom\nEQ-0001;b\nEQ-0002;autre poste\n")
        self.page.evaluate("""(texte) => {
            let fait = false;
            crochets.avantCreateWritable = async (nom) => {
                if (nom === 'equipements.csv' && !fait) { fait = true; await aide.autrePoste(nom, texte, false); }
            };
        }""", autre.decode("utf-8"))
        resultat = self.appeler("enregistrer", "equipements", octets_js(csv("id;nom\nEQ-0001;c\n")), v2)
        self.assertFalse(resultat["ok"], "écriture de l'autre poste écrasée sans conflit : %s" % resultat)
        self.assertEqual(resultat["nom"], "ErreurConflit")
        self.assertEqual(self.lire_opfs("equipements.csv"), autre)

    def test_creation_concurrente_d_un_fichier_absent(self):
        """Fichier absent au contrôle, créé par un autre poste avant notre écriture : conflit."""
        self.choisir_dossier_enveloppe()
        autre = csv("id;nom\nEQ-0009;autre poste\n")
        self.page.evaluate("""(texte) => {
            let fait = false;
            crochets.avantCreateWritable = async (nom) => {
                if (nom === 'equipements.csv' && !fait) { fait = true; await aide.autrePoste(nom, texte, false); }
            };
        }""", autre.decode("utf-8"))
        resultat = self.appeler("enregistrer", "equipements", octets_js(csv("id;nom\nEQ-0001;moi\n")), None)
        self.assertFalse(resultat["ok"], resultat)
        self.assertEqual(resultat["nom"], "ErreurConflit")
        self.assertEqual(self.lire_opfs("equipements.csv"), autre)

    def test_echec_d_ecriture_ne_supprime_pas_le_fichier_d_un_autre_poste(self):
        """Notre écriture échoue ; entre-temps un autre poste a créé le fichier : il doit rester."""
        self.choisir_dossier_enveloppe()
        autre = csv("id;nom\nEQ-0009;autre poste\n")
        self.page.evaluate("""(texte) => {
            crochets.avantCreateWritable = async (nom) => {
                if (nom === 'equipements.csv') { await aide.autrePoste(nom, texte, false); }
            };
            crochets.ecritureEnEchec = (nom) => nom === 'equipements.csv';
        }""", autre.decode("utf-8"))
        resultat = self.appeler("enregistrer", "equipements", octets_js(csv("id;nom\nEQ-0001;moi\n")), None)
        self.assertFalse(resultat["ok"], resultat)
        self.assertEqual(self.lire_opfs("equipements.csv"), autre, "le fichier de l'autre poste a été supprimé")

    def test_echec_d_ecriture_d_un_nouveau_fichier_ne_laisse_pas_de_fichier_vide(self):
        self.choisir_dossier_enveloppe()
        self.page.evaluate("() => { crochets.ecritureEnEchec = (nom) => nom === 'equipements.csv'; }")
        resultat = self.appeler("enregistrer", "equipements", octets_js(csv("id;nom\nEQ-0001;moi\n")), None)
        self.assertFalse(resultat["ok"], resultat)
        self.assertEqual(resultat["nom"], "ErreurStockage")
        self.assertEqual(resultat["message"], MESSAGE_FICHIER_OUVERT % "equipements.csv")      # T232
        self.assertIsNone(self.lire_opfs("equipements.csv"))

    def test_fichier_ouvert_dans_excel_le_message_nomme_le_fichier(self):
        """T232 : refus « fichier ouvert » (NoModificationAllowedError) à l'écriture d'une table, puis du journal : le
        message nomme le fichier refusé (texte de Nicolas, le même que serveur.py) ; repli quand le nom n'est pas
        connu (ici, un refus hors des écritures, à la lecture)."""
        self.choisir_dossier_enveloppe()
        avant = csv("id;nom\nEQ-0001;a\n")
        self.enregistrer("equipements", avant, None)
        self.page.evaluate("() => { crochets.ecritureEnEchec = (nom) => nom === 'equipements.csv' "
                           "|| nom === 'journal.csv'; }")
        for methode, arguments, fichier in [
                ("enregistrer", ("equipements", octets_js(csv("id;nom\nEQ-0001;b\n")), empreinte(avant)),
                 "equipements.csv"),
                ("ajouter", ("journal", self.corps_journal("J-1")), "journal.csv")]:
            with self.subTest(methode=methode):
                erreur = self.echouer(methode, *arguments)
                self.assertEqual((erreur["nom"], erreur["message"]),
                                 ("ErreurStockage", MESSAGE_FICHIER_OUVERT % fichier))
        self.assertEqual(self.lire_opfs("equipements.csv"), avant)
        self.assertIsNone(self.lire_opfs("journal.csv"))
        self.page.evaluate("""() => {
            crochets.ecritureEnEchec = null;
            crochets.avantGetFileHandle = (nom) => {
                if (nom !== 'equipements.csv') { return; }
                const erreur = new Error('refus simulé');
                erreur.name = 'NoModificationAllowedError';
                throw erreur;
            };
        }""")
        erreur = self.echouer("charger", "equipements")
        self.assertEqual((erreur["nom"], erreur["message"]), ("ErreurStockage", MESSAGE_FICHIER_OUVERT_SANS_NOM))

    def test_dossier_de_donnees_disparu_donne_une_erreur(self):
        """Dossier supprimé ou clé USB débranchée : erreur, et non « fichier absent » (base vide)."""
        self.choisir_dossier()
        self.enregistrer("equipements", csv("id;nom\nEQ-0001;a\n"), None)
        self.page.evaluate("""async () => {
            await (await navigator.storage.getDirectory()).removeEntry(%s, { recursive: true });
        }""" % ('"%s"' % NOM_DOSSIER_SIMULE))
        for methode, arguments in [("charger", ("equipements",)), ("charger", ("journal",)),
                                   ("listerVersions", ())]:
            with self.subTest(methode=methode, arguments=arguments):
                erreur = self.echouer(methode, *arguments)
                self.assertEqual(erreur["nom"], "ErreurStockage")
                self.assertIn("introuvable ou inaccessible", erreur["message"])

    def test_sauvegarde_du_jour_interrompue_est_refaite(self):
        """Onglet fermé pendant la copie de la sauvegarde du jour : elle est refaite plus tard
        par un autre onglet, et n'apparaît pas dans la liste tant qu'elle est incomplète."""
        jour = self.date_du_jour()
        equipements = csv("id;nom\nEQ-0001;a\n")
        journal = csv(self.ENTETE_JOURNAL + "\n" + self.ligne_journal("J-1"))
        self.ecrire_opfs("equipements.csv", equipements)
        self.ecrire_opfs("journal.csv", journal)

        # Onglet 1 : la copie reste bloquée sur journal.csv, puis l'onglet est fermé.
        self.choisir_dossier_enveloppe()
        self.page.evaluate("""() => {
            crochets.avantGetFileHandle = (nom) => (nom === 'journal.csv' ? new Promise(() => {}) : null);
            window.dos.enregistrer('parametres', new TextEncoder().encode('cle;valeur\\r\\n'), null);
        }""")
        self.page.wait_for_function("""async () => {
            const noms = await aide.listerOpfs('sauvegardes/' + aide.dateDuJour());
            return Boolean(noms) && noms.includes('equipements.csv');
        }""", polling=50, timeout=5000)
        self.page.close()

        # Onglet 2, un peu plus tard (horloge avancée de 10 minutes).
        seconde = self.contexte.new_page()
        self.surveiller(seconde)
        self.ouvrir(seconde)
        self.choisir_dossier(page=seconde, poste="Poste B")
        seconde.evaluate("""() => {
            const vraiNow = Date.now.bind(Date);
            Date.now = () => vraiNow() + 10 * 60 * 1000;
        }""")
        liste = self.reussir("listerSauvegardes", page=seconde)
        self.assertNotIn(jour, [s["nom"] for s in liste], "sauvegarde incomplète listée : %s" % liste)
        erreur = self.echouer("restaurer", jour, page=seconde)
        self.assertEqual(erreur["nom"], "ErreurStockage")
        self.assertIn("incomplète", erreur["message"])

        version = empreinte(equipements)
        self.reussir("enregistrer", "equipements", octets_js(csv("id;nom\nEQ-0001;b\n")), version, page=seconde)
        self.assertEqual(self.lire_opfs("sauvegardes/%s/equipements.csv" % jour, page=seconde), equipements)
        self.assertEqual(self.lire_opfs("sauvegardes/%s/journal.csv" % jour, page=seconde), journal)
        liste = self.reussir("listerSauvegardes", page=seconde)
        du_jour = [s for s in liste if s["nom"] == jour]
        self.assertEqual(len(du_jour), 1, liste)
        self.assertEqual(du_jour[0]["tables"], ["equipements", "journal"])
        self.assertEqual([n for n in self.lister_opfs("sauvegardes/%s" % jour, page=seconde)
                          if not n.startswith(".")], ["equipements.csv", "journal.csv", "manifeste.json"])
        seconde.close()

    def test_sauvegarde_en_cours_sur_un_autre_poste_n_est_pas_effacee(self):
        """Marqueur « en cours » récent : un autre poste copie en ce moment ; on ne la refait pas."""
        jour = self.date_du_jour()
        self.ecrire_opfs("equipements.csv", csv("id;nom\nEQ-0001;a\n"))
        self.page.evaluate("""async (jour) => {
            const racine = await aide.vraiDossier();
            const s = await (await racine.getDirectoryHandle('sauvegardes', { create: true }))
                .getDirectoryHandle(jour, { create: true });
            const f = await (await s.getFileHandle('.en-cours', { create: true })).createWritable();
            await f.write('autre poste'); await f.close();
        }""", jour)
        self.choisir_dossier()
        self.reussir("enregistrer", "equipements", octets_js(csv("id;nom\nEQ-0001;b\n")),
                     empreinte(csv("id;nom\nEQ-0001;a\n")))
        self.assertEqual(self.lister_opfs("sauvegardes/%s" % jour), [".en-cours"])


if __name__ == "__main__":
    unittest.main()
