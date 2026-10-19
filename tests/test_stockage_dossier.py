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
        self.assertEqual(self.lister_opfs("sauvegardes/%s" % jour), ["equipements.csv"])

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
        self.assertEqual(len(noms), 22)
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
        vieux = self.page.evaluate("aide.dateHeure(-10 * 60 * 1000)")
        self.ecrire_opfs("verrou.txt", ("Poste X;%s;autre-session" % vieux).encode("utf-8"))
        self.assertEqual(self.reussir("verifierVerrou"), {"autreSession": None})

        recent = self.page.evaluate("aide.dateHeure(-60 * 1000)")
        self.ecrire_opfs("verrou.txt", ("Poste X;%s;autre-session" % recent).encode("utf-8"))
        self.assertEqual(self.reussir("verifierVerrou")["autreSession"]["poste"], "Poste X")

        self.ecrire_opfs("verrou.txt", b"n'importe quoi")
        self.assertEqual(self.reussir("verifierVerrou"), {"autreSession": None})

    def test_poste_sans_point_virgule_dans_le_verrou(self):
        self.choisir_dossier(poste="Atelier;nord\nbis")
        self.reussir("demarrerVerrou")
        self.assertRegex(self.lire_opfs("verrou.txt").decode("utf-8"),
                         r"^Atelier nord bis;\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2};[a-z0-9]+$")
        self.reussir("arreterVerrou")


if __name__ == "__main__":
    unittest.main()
