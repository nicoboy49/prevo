"""Avertissement avant un gros export ZIP complet (T222, décision de Nicolas du 05/11), seuil et texte revus par la
recette du ZIP par morceaux (T215, docs/FORMAT.md §13) : la mémoire de l'export reste proportionnelle à la taille du ZIP,
jusqu'à une fois et demie (contre 5 à 6 fois avec JSZip, T212) ; seuil relevé de 150 à 500 Mo.

Code visé : js/modules/zip-donnees.js (AVERTISSEMENT, avertissement, exporter et sa fenêtre #export-zip-avertissement),
par les boutons #btn-export-zip et #btn-export-donnees-seules de Paramètres (App.exporterZip).

    calcul   page sans application : ZipDonnees.avertissement sur des résultats fabriqués ({ fichiers: [{ taille }],
             refus, sansDocuments } : depuis T228, les tailles de contenu()) : 500 Mo pile (en un ou deux
             fichiers) → null ; un octet de plus → le message exact (« plus de 500 Mo » : l'arrondi égalerait
             le seuil) ; 503,5 Mo et 1,5 Go écrits comme tels ;
             données seules ou refus → null quelle que soit la taille ; AVERTISSEMENT.contenu = 524 288 000, gelé ;
    serveur  ServeurPrevo sur une copie (dossier temporaire) de la démo dont les données citent 53 documents fictifs
             incompressibles de 9,5 Mo (20 notices, 27 photos, 6 rapports de contrôle ; 10 Mo au plus par document à
             l'import), plus de 500 Mo en tout ; le responsable, dans Paramètres :
               a. « Exporter en ZIP » : fenêtre « Export ZIP volumineux », texte exact (taille tirée des entrées du ZIP
                  complet de l'étape c), trois boutons dans l'ordre ; « Annuler » : aucun ZIP construit ni téléchargé,
                  aucune autre fenêtre (pas de refus), aucun message ; la croix (App.exporterZip) : résultat `annule`,
                  `fichiers` vide, pas de refus ;
               b. « Exporter les données seules » : prevo-export-AAAA-MM-JJ-sans-documents.zip, NB_TABLES CSV et
                  manifeste.json, aucune entrée documents/, « documents »: « exclus », message des données seules ;
               c. « Continuer l'export complet » : prevo-export-AAAA-MM-JJ.zip, NB_TABLES CSV, les 53 documents (noms, tailles
                  et SHA-256 de la source), manifeste.json sans « documents » ni « manquants », message des 53
                  documents ;
               d. « Exporter les données seules (sans les documents) » : aucune fenêtre, ZIP sans les documents.
             Sous le seuil, aucune fenêtre : couvert par les tests d'export existants (petites bases :
             test_zip_export.py, test_zip_donnees_seules.py, test_zip_limites.py).

Règle numéro un : jamais de données réelles (démo et documents fictifs, dossiers temporaires).

Lancer depuis la racine du projet (à travers le verrou du navigateur) :
    py -X utf8 -m unittest discover -s tests -p "test_zip_avertissement.py" -v
"""
import hashlib
import json
import math
import re
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from commun import NB_TABLES, CasNavigateur, ServeurPrevo, attendre_pret, charger_scripts, preregler_profil
from test_zip_export import NOTER_TOASTS_JS
from test_zip_import import TABLES, fichiers_demo
from test_zip_limites import ESPION_ZIP_JS, LIMITES, ecrire_dossier, octets_fictifs, poser_documents

MIO = 1024 * 1024
SEUIL = 500 * MIO                                               # AVERTISSEMENT.contenu (T222, revu par T215)
TAILLE_DOCUMENT = 19 * MIO // 2                                 # 9,5 Mo : sous la limite d'un document (10 Mo)
LONG_MS = 300000                                                # gros volumes : 5 minutes au plus par étape
TITRE = "Export ZIP volumineux"
BOUTONS = ["Annuler", "Continuer l'export complet", "Exporter les données seules"]
MOTIF_ZIP_COMPLET = re.compile(r"^prevo-export-\d{4}-\d{2}-\d{2}\.zip$")
MOTIF_ZIP_SANS_DOCUMENTS = re.compile(r"^prevo-export-\d{4}-\d{2}-\d{2}-sans-documents\.zip$")
MESSAGE_DONNEES_SEULES = "Export téléchargé : %d fichiers CSV, sans les documents (données seules)." % NB_TABLES
MESSAGE_COMPLET = "Export téléchargé : %d fichiers CSV et 53 document(s)." % NB_TABLES
CSV = sorted(table + ".csv" for table in TABLES)

# Titres de toutes les fenêtres ouvertes (<dialog> ajoutés), dans l'ordre : UI est gelé, on observe le DOM.
NOTER_FENETRES_JS = """(() => {
  window.__fenetres = [];
  new MutationObserver((changements) => changements.forEach((changement) => changement.addedNodes.forEach((noeud) => {
    if (noeud.nodeName !== 'DIALOG') return;
    window.__fenetres.push(((noeud.querySelector('h2') || {}).textContent || '').trim());
  }))).observe(document, { subtree: true, childList: true });
})();"""

LIRE_FENETRE_JS = """() => {
  const fenetre = document.getElementById('export-zip-avertissement').closest('dialog');
  return {
    titre: fenetre.querySelector('h2').textContent.trim(),
    texte: fenetre.querySelector('#export-zip-avertissement .alerte-texte').textContent,
    boutons: Array.from(fenetre.querySelectorAll('.fenetre-actions button'), (bouton) => bouton.textContent.trim()),
  };
}"""


def en_mo(octets):
    """ZipLecture.enMo : « 152,6 Mo », « 152 Mo », « 1,5 Go » (Math.round au dixième)."""
    unite, suffixe = (1024 * MIO, " Go") if octets >= 1024 * MIO else (MIO, " Mo")
    dixiemes = math.floor(octets / unite * 10 + 0.5)
    texte = str(dixiemes // 10) if dixiemes % 10 == 0 else "%d,%d" % (dixiemes // 10, dixiemes % 10)
    return texte + suffixe


def message_attendu(octets):
    """Texte de l'avertissement pour `octets` de fichiers (« plus de 500 Mo » quand l'arrondi égalerait le seuil)."""
    taille = en_mo(octets)
    if taille == en_mo(SEUIL):
        taille = "plus de " + taille
    return ("Ce ZIP contiendrait %s de données et de documents. Le construire demande au navigateur jusqu'à une fois "
            "et demie cette taille en mémoire : sur un PC de 4 Go, il peut ralentir fortement, voire s'arrêter. L'export "
            "des données seules (sans les documents) est bien plus léger et s'importe comme l'export complet : les "
            "documents déjà présents sont alors gardés tels quels." % taille)


def sha256(octets):
    return hashlib.sha256(octets).hexdigest()


# ---------------------------------------------------------------------------
# 1. Calcul (page sans application)
# ---------------------------------------------------------------------------

class TestCalcul(CasNavigateur):

    def avertissement(self, tailles, refus=None, sans_documents=False):
        return self.page.evaluate(
            "([t, r, s]) => ZipDonnees.avertissement({ fichiers: t.map((n) => ({ taille: n })), refus: r, "
            "sansDocuments: s })", [tailles, refus, sans_documents])

    def test_seuil_de_500_mo_message_exact_donnees_seules_et_refus_sans_avertissement(self):
        charger_scripts(self.page, ["js/modules/zip-flux.js", "js/modules/zip-lecture.js", "js/modules/zip-donnees.js"])
        # Seuil : 500 Mo (524 288 000 octets), gelé.
        self.assertEqual(self.page.evaluate(
            "[ZipDonnees.AVERTISSEMENT.contenu, Object.isFrozen(ZipDonnees.AVERTISSEMENT)]"), [SEUIL, True])
        self.assertEqual(SEUIL, 524288000)
        self.assertEqual(self.page.evaluate(
            "() => { try { ZipDonnees.AVERTISSEMENT.contenu = 1; } catch (erreur) { /* gelé */ } "
            "return ZipDonnees.AVERTISSEMENT.contenu; }"), SEUIL)
        # 500 Mo pile, en un ou en deux fichiers (la somme compte) : pas d'avertissement.
        self.assertIsNone(self.avertissement([SEUIL]))
        self.assertIsNone(self.avertissement([300 * MIO, 200 * MIO]))
        self.assertIsNone(self.avertissement([]))
        # Un octet de plus : le message exact, « plus de 500 Mo ».
        self.assertEqual(self.avertissement([SEUIL + 1]), message_attendu(SEUIL + 1))
        self.assertEqual(self.avertissement([300 * MIO, 200 * MIO + 1]), message_attendu(SEUIL + 1))
        self.assertEqual(self.avertissement([SEUIL + 1]),
                         "Ce ZIP contiendrait plus de 500 Mo de données et de documents. Le construire demande au "
                         "navigateur jusqu'à une fois et demie cette taille en mémoire : sur un PC de 4 Go, il peut "
                         "ralentir fortement, voire s'arrêter. L'export des données seules (sans les documents) est "
                         "bien plus léger et s'importe comme l'export complet : les documents déjà présents sont alors "
                         "gardés tels quels.")
        # Au-delà de l'arrondi : la taille elle-même ; sous le seuil (l'ancien de 150 Mo dépassé) : rien.
        self.assertEqual(self.avertissement([53 * TAILLE_DOCUMENT]), message_attendu(1007 * MIO // 2))
        self.assertIn("contiendrait 503,5 Mo de données", message_attendu(1007 * MIO // 2))
        self.assertIsNone(self.avertissement([16 * TAILLE_DOCUMENT]))
        self.assertIn("contiendrait 1,5 Go de données", self.avertissement([1536 * MIO]))
        self.assertEqual(self.avertissement([1536 * MIO]), message_attendu(1536 * MIO))
        # Données seules, ou export refusé : jamais d'avertissement, quelle que soit la taille.
        self.assertIsNone(self.avertissement([SEUIL + 1], sans_documents=True))
        self.assertIsNone(self.avertissement([400 * MIO], sans_documents=True))
        self.assertIsNone(self.avertissement([SEUIL + 1],
                                             refus="Export impossible : l'import de Prévo refuserait ce ZIP."))


# ---------------------------------------------------------------------------
# 2. Mode serveur : plus de 500 Mo de documents
# ---------------------------------------------------------------------------

def base_lourde(dossier):
    """Démo dont les données citent 53 documents fictifs incompressibles de 9,5 Mo, écrite dans `dossier` →
    {nom: (octets, sha256)} des documents (écrits un à un : jamais tous en mémoire)."""
    demo = fichiers_demo()
    notices = {"notice-lourde-%02d.pdf" % n: ("notice-%d" % n, b"%PDF-1.4\n") for n in range(20)}
    photos = {"photo-lourde-%02d.jpg" % n: ("photo-%d" % n, b"\xff\xd8\xff\xe0") for n in range(27)}
    rapports = {"rapport-lourd-%02d.pdf" % n: ("rapport-%d" % n, b"%PDF-1.4\n") for n in range(6)}
    demo["equipements.csv"] = poser_documents(demo["equipements.csv"], "document", sorted(notices))
    demo["demandes.csv"] = poser_documents(demo["demandes.csv"], "photo", sorted(photos))
    demo["controles_reglementaires.csv"] = poser_documents(demo["controles_reglementaires.csv"], "rapport",
                                                           sorted(rapports))
    ecrire_dossier(dossier, demo)
    decrits = {}
    for nom, (graine, signature) in dict(notices, **photos, **rapports).items():
        octets = octets_fictifs(TAILLE_DOCUMENT, graine, signature)
        ecrire_dossier(dossier, {"documents/" + nom: octets})
        decrits[nom] = (len(octets), sha256(octets))
    return decrits


def lire_zip(chemin):
    """Entrées d'un ZIP → {nom: (octets, sha256)} et le manifeste (lus une entrée à la fois)."""
    decrits = {}
    with zipfile.ZipFile(chemin) as archive:
        for nom in archive.namelist():
            octets = archive.read(nom)
            decrits[nom] = (len(octets), sha256(octets))
            if nom == "manifeste.json":
                manifeste = json.loads(octets.decode("utf-8"))
    return decrits, manifeste


class TestServeur(CasNavigateur):

    def setUp(self):
        super().setUp()
        self.contexte.set_default_timeout(LONG_MS)
        self.contexte.add_init_script(NOTER_TOASTS_JS)
        self.contexte.add_init_script(NOTER_FENETRES_JS)
        self.temporaire = Path(tempfile.mkdtemp(prefix="prevo-zip-avertissement-"))
        self.addCleanup(shutil.rmtree, self.temporaire, True)
        preregler_profil(self.contexte, "responsable")

    def remettre_a_zero(self, page):
        page.evaluate("() => { window.__toasts = []; window.__fenetres = []; }")

    def compteurs(self, page):
        """[ZIP écrits (ZipFlux, terminer), téléchargements proposés (UI.telecharger)]."""
        return page.evaluate("[window.__generations, window.__telechargements]")

    def attendre_fin_export(self, page, selecteur):
        page.wait_for_function("(s) => !document.querySelector(s).disabled", arg=selecteur)

    def ouvrir_avertissement(self, page):
        """Clic sur « Exporter en ZIP » → (titre, texte, boutons) de la fenêtre d'avertissement."""
        page.click("#btn-export-zip")
        page.wait_for_selector("#export-zip-avertissement")
        fenetre = page.evaluate(LIRE_FENETRE_JS)
        self.assertEqual(fenetre["titre"], TITRE)
        self.assertEqual(fenetre["boutons"], BOUTONS)
        return fenetre["texte"]

    def choisir(self, page, libelle):
        page.locator("dialog .fenetre-actions button").filter(has_text=libelle).click()
        page.wait_for_selector("#export-zip-avertissement", state="detached")

    def verifier_sans_documents(self, telechargement):
        self.assertRegex(telechargement.suggested_filename, MOTIF_ZIP_SANS_DOCUMENTS)
        chemin = self.temporaire / telechargement.suggested_filename
        telechargement.save_as(str(chemin))
        decrits, manifeste = lire_zip(chemin)
        chemin.unlink()
        self.assertEqual(sorted(decrits), sorted(CSV + ["manifeste.json"]))
        self.assertEqual([nom for nom in decrits if nom.startswith("documents")], [])
        self.assertEqual(manifeste["documents"], "exclus")
        self.assertNotIn("manquants", manifeste)
        self.assertEqual(sorted(f["nom"] for f in manifeste["fichiers"]), CSV)

    def test_plus_de_500_mo_fenetre_annuler_donnees_seules_ou_export_complet(self):
        documents = base_lourde(self.temporaire / "source")
        self.assertEqual(len(documents), 53)
        self.assertLessEqual(TAILLE_DOCUMENT, LIMITES["document"])
        self.assertGreater(sum(taille for taille, _ in documents.values()), SEUIL)
        telechargements = []
        with ServeurPrevo(source=self.temporaire / "source") as serveur:
            page = self.page
            page.on("download", lambda telechargement: telechargements.append(telechargement.suggested_filename))
            page.goto(serveur.url + "/#/parametres")
            attendre_pret(page)
            page.wait_for_selector("#btn-export-zip")
            page.wait_for_load_state("networkidle")
            page.evaluate(ESPION_ZIP_JS)
            self.remettre_a_zero(page)

            # a. « Exporter en ZIP » → fenêtre ; « Annuler » : rien n'est construit ni téléchargé, aucun refus.
            textes = [self.ouvrir_avertissement(page)]
            self.choisir(page, "Annuler")
            self.attendre_fin_export(page, "#btn-export-zip")
            self.assertEqual(self.compteurs(page), [0, 0])
            self.assertEqual(page.evaluate("window.__fenetres"), [TITRE])
            self.assertEqual(page.locator("#export-zip-refus").count(), 0)
            self.assertEqual(page.evaluate("window.__toasts"), [])
            #    La croix (Échap, de même) : App.exporterZip rend le résultat annulé, sans fichiers ni refus.
            page.evaluate("() => { window.__retour = App.exporterZip().then((r) => r && "
                          "{ annule: r.annule === true, fichiers: r.fichiers.length, refus: r.refus }); }")
            page.wait_for_selector("#export-zip-avertissement")
            textes.append(page.evaluate(LIRE_FENETRE_JS)["texte"])
            page.click("dialog .fenetre-fermer")
            page.wait_for_selector("#export-zip-avertissement", state="detached")
            self.assertEqual(page.evaluate("window.__retour"), {"annule": True, "fichiers": 0, "refus": None})
            self.assertEqual(self.compteurs(page), [0, 0])
            self.assertEqual(page.evaluate("window.__fenetres"), [TITRE, TITRE])
            self.assertEqual(page.evaluate("window.__toasts"), [])
            self.assertEqual(telechargements, [])

            # b. « Exporter les données seules » : le ZIP sans les documents, et son message.
            self.remettre_a_zero(page)
            textes.append(self.ouvrir_avertissement(page))
            with page.expect_download(timeout=LONG_MS) as attente:
                self.choisir(page, "Exporter les données seules")
            self.verifier_sans_documents(attente.value)
            page.wait_for_function("(m) => (window.__toasts || []).includes(m)", arg=MESSAGE_DONNEES_SEULES)
            self.attendre_fin_export(page, "#btn-export-zip")
            self.assertEqual(self.compteurs(page), [1, 1])
            self.assertEqual(page.evaluate("window.__fenetres"), [TITRE])

            # c. « Continuer l'export complet » : le ZIP complet, les 53 documents à l'octet.
            self.remettre_a_zero(page)
            textes.append(self.ouvrir_avertissement(page))
            with page.expect_download(timeout=LONG_MS) as attente:
                self.choisir(page, "Continuer l'export complet")
            self.assertRegex(attente.value.suggested_filename, MOTIF_ZIP_COMPLET)
            chemin = self.temporaire / attente.value.suggested_filename
            attente.value.save_as(str(chemin))
            decrits, manifeste = lire_zip(chemin)
            chemin.unlink()
            self.assertEqual(sorted(decrits),
                             sorted(CSV + ["documents/" + nom for nom in documents] + ["manifeste.json"]))
            for nom, (taille, empreinte) in documents.items():
                self.assertEqual(decrits["documents/" + nom], (taille, empreinte), nom)
            self.assertNotIn("documents", manifeste)
            self.assertNotIn("manquants", manifeste)
            self.assertEqual(len(manifeste["fichiers"]), len(CSV) + 53)
            page.wait_for_function("(m) => (window.__toasts || []).includes(m)", arg=MESSAGE_COMPLET)
            self.attendre_fin_export(page, "#btn-export-zip")
            self.assertEqual(self.compteurs(page), [2, 2])
            self.assertEqual(page.evaluate("window.__fenetres"), [TITRE])
            # Le texte de chaque fenêtre : la taille de tous les fichiers du ZIP complet (manifeste compris).
            total = sum(taille for taille, _ in decrits.values())
            self.assertGreater(total, SEUIL)
            self.assertEqual(textes, [message_attendu(total)] * 4)

            # d. « Exporter les données seules (sans les documents) » : jamais d'avertissement.
            self.remettre_a_zero(page)
            with page.expect_download(timeout=LONG_MS) as attente:
                page.click("#btn-export-donnees-seules")
            self.verifier_sans_documents(attente.value)
            page.wait_for_function("(m) => (window.__toasts || []).includes(m)", arg=MESSAGE_DONNEES_SEULES)
            self.attendre_fin_export(page, "#btn-export-donnees-seules")
            self.assertEqual(page.evaluate("window.__fenetres"), [])
            self.assertEqual(self.compteurs(page), [3, 3])
            self.assertEqual(len(telechargements), 3)
            page.goto("about:blank")            # plus aucune requête de fond vers le serveur arrêté


if __name__ == "__main__":
    unittest.main()
