"""Import d'un fichier marqué « abîmé » par Prévo (T213, option B de Nicolas : « un fichier marqué abîmé par Prévo
n'est accepté à l'import que si son empreinte correspond à celle du manifeste. Sinon, refus ; la confirmation dit en
clair quel fichier est abîmé et que la base retrouvera le même état, bandeau compris ; la date "abîmé depuis le …" est
conservée telle quelle, pas remise à zéro par l'import ; l'import ne tente aucune réparation. »).

Code visé : js/modules/zip-donnees.js (« abime_depuis » au manifeste), js/modules/zip-tables.js (ZipTables : CSV abîmé
accepté seulement marqué, à l'empreinte vérifiée par ZipLecture), js/modules/parametres-zip.js (octets du ZIP écrits
tels quels, confirmation #abimes-import-zip), adaptateurs (options.abimeDepuis) et serveur.py (X-Prevo-Abime-Depuis).

Base A : jeu entete-tronque (ordres_travail.csv : en-tête coupé, valeurs au-delà) et fichiers-abimes.json qui date le
fichier abîmé de 20 jours. Le responsable exporte A par le vrai bouton : le manifeste marque ordres_travail.csv
« abime » avec « abime_depuis » = cette date. Puis, dans une base saine :
    - ZIP dont ordres_travail.csv a changé d'un octet (empreinte fausse) : refusé, aucun CSV changé ;
    - ZIP dont le manifeste ne marque plus le fichier : refusé (« illisible »), aucun CSV changé ;
    - (serveur) CSV sain marqué « abime » : lu normalement (ZipLecture.lire : seul ordres_travail.csv est rendu
      dans `abimes`) ;
    - ZIP de l'export : confirmation (phrase exacte, badge « abîmé, tel quel »), import ; ordres_travail.csv identique
      à l'octet au fichier de A, fichiers-abimes.json garde la date d'origine (pas celle de l'import) ; après
      rechargement, le responsable voit « Fichier abîmé : ordres_travail.csv, depuis le … (20 jours). ».
    serveur  ServeurPrevo : A (copie du jeu), puis une copie de la démo (base saine) ;
    dossier  OPFS : A, puis la même base rendue saine (ordres_travail.csv de la démo) et rouverte ;
    en-tête  serveur.py seul (sans navigateur) : X-Prevo-Abime-Depuis refusé (400, rien d'écrit) sans la dérogation
             X-Prevo-Remplacer-Abime, avec une date mal formée, ou pour un CSV que le serveur ne voit pas abîmé (son
             en-tête reste alors contrôlé) ; accepté pour le CSV abîmé (fichiers-abimes.json : la date donnée) ; un
             CSV sain écrit avec la dérogation est retiré de fichiers-abimes.json.

Règle numéro un : jamais de données réelles (copies dans des dossiers temporaires, OPFS du navigateur de test).

Lancer depuis la racine du projet (à travers le verrou du navigateur) :
    py -X utf8 -m unittest discover -s tests -p "test_zip_abime.py" -v
"""
import base64
import datetime
import io
import json
import re
import tempfile
import unittest
import zipfile
from pathlib import Path

from commun import RACINE, ServeurPrevo, ServeurStatique, attendre_pret, installer_dossier_simule, preregler_profil
from jeux_formats import copier_jeu
from test_garde_abime_serveur import requete, version_de
from test_zip_import import (BOUTON_REMPLACER, ECRIRE_OPFS_JS, ERREUR_PING_ABSENT, INSTANTANE_OPFS_JS, CasImport,
                             en_base64, fichiers_du_jeu)

FICHIER = "ordres_travail.csv"
FICHIERS_ABIMES = "fichiers-abimes.json"
JOURS = 20
VU_LE = datetime.date.today() - datetime.timedelta(days=JOURS)
DATE = VU_LE.isoformat() + "T08:00:00"
NOM_DOSSIER = "donnees-zip-abime"
PHRASE = ("ordres_travail.csv est abîmé dans ce ZIP (abîmé depuis le %s) : il sera importé tel quel, sans réparation ; "
          "la base retrouvera le même état, avec le bandeau « Fichier abîmé ». Réparez-le ensuite, ou restaurez une "
          "sauvegarde." % VU_LE.strftime("%d/%m/%Y"))
BANDEAU = "Fichier abîmé : ordres_travail.csv, depuis le %s (%d jours)." % (VU_LE.strftime("%d/%m/%Y"), JOURS)

BANDEAUX_JS = """() => Array.from(document.querySelectorAll('#alertes-app > *'))
  .map((e) => e.textContent.replace(/\\s+/g, ' ').trim()).filter((t) => t.includes('abîmé'))"""

# ZipLecture.lire sur des octets donnés en base64 → { ok, refus, abimes: [[table, depuis]] }.
LIRE_ABIMES_JS = """async (enBase64) => {
  const r = await ZipLecture.lire(Uint8Array.from(atob(enBase64), (c) => c.charCodeAt(0)));
  return { ok: r.ok, refus: r.refus, abimes: r.ok ? r.abimes.map((a) => [a.table, a.depuis]) : null };
}"""


def octets_zip(entrees):
    """Octets d'un ZIP des entrées ({nom: octets}, dans l'ordre), comme l'export (deflate)."""
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as archive:
        for nom, octets in entrees.items():
            archive.writestr(zipfile.ZipInfo(nom, date_time=(2026, 11, 4, 9, 30, 0)), octets, zipfile.ZIP_DEFLATED)
    return tampon.getvalue()


def avec_manifeste(entrees, changer):
    """Copie des entrées dont le manifeste est passé à changer(manifeste) (réécrit comme par l'export)."""
    manifeste = json.loads(entrees["manifeste.json"].decode("utf-8"))
    changer(manifeste)
    return dict(entrees, **{"manifeste.json": (json.dumps(manifeste, ensure_ascii=False, indent=2) + "\n").encode()})


def entree(manifeste, nom):
    return next(fichier for fichier in manifeste["fichiers"] if fichier["nom"] == nom)


def sans_marque(manifeste):
    decrit = entree(manifeste, FICHIER)
    decrit.pop("abime")
    decrit.pop("abime_depuis", None)


def un_octet_change(entrees):
    """Copie des entrées où ordres_travail.csv a un octet de changé (même taille : seule l'empreinte diffère)."""
    octets = entrees[FICHIER]
    position = octets.index(b"OT-2025-0001") + len("OT-2025-000")
    return dict(entrees, **{FICHIER: octets[:position] + b"9" + octets[position + 1:]})


class CasAbime(CasImport):

    def exporter(self, page):
        """Export par le vrai bouton de Paramètres → {nom: octets} des entrées, dans l'ordre du ZIP."""
        page.wait_for_selector("#btn-export-zip")
        with page.expect_download() as attente:
            page.click("#btn-export-zip")
        with zipfile.ZipFile(attente.value.path()) as archive:
            return {nom: archive.read(nom) for nom in archive.namelist()}

    def verifier_marque(self, entrees, original):
        manifeste = json.loads(entrees["manifeste.json"].decode("utf-8"))
        self.assertEqual(entree(manifeste, FICHIER)["abime"], True)
        self.assertEqual(entree(manifeste, FICHIER)["abime_depuis"], DATE)
        self.assertEqual([f["nom"] for f in manifeste["fichiers"] if "abime_depuis" in f], [FICHIER])
        self.assertEqual(entrees[FICHIER], original)

    def ecrire_zip(self, nom, entrees):
        chemin = self.temporaire / nom
        chemin.write_bytes(octets_zip(entrees))
        return chemin

    def verifier_refus(self, page, entrees, morceau, csv_actuels):
        """Le ZIP est refusé (fenêtre #import-zip-refus avec ce morceau), aucun CSV n'a changé."""
        avant = csv_actuels()
        self.choisir_zip(page, self.ecrire_zip("refuse-%d.zip" % len(morceau), entrees))
        texte = self.texte_fenetre(page, "import-zip-refus")
        self.assertIn(morceau, texte)
        self.assertIn("Rien n'a été écrit.", texte)
        self.fermer_fenetre(page, "import-zip-refus")
        self.assertEqual(page.locator("#confirmation-import-zip").count(), 0)
        self.assertEqual(csv_actuels(), avant)

    def importer(self, page, entrees):
        """Import du ZIP de l'export : confirmation vérifiée, remplacement → texte de la fenêtre de fin."""
        self.choisir_zip(page, self.ecrire_zip("prevo-export-abime.zip", entrees))
        self.confirmation(page)
        self.assertEqual(re.sub(r"\s+", " ", page.inner_text("#abimes-import-zip")).strip(), PHRASE)
        self.assertEqual(page.locator("#confirmation-import-zip [data-tel-quel]").evaluate_all(
            "(liste) => liste.map((e) => [e.dataset.telQuel, e.textContent])"), [["ordres_travail", "abîmé, tel quel"]])
        page.click(BOUTON_REMPLACER)
        termine = self.texte_fenetre(page, "import-zip-termine")
        self.assertIn("(dont ordres_travail.csv, abîmé, importé tel quel)", termine)
        return termine

    def recharger_et_verifier_bandeau(self, page, reprendre):
        with page.expect_navigation():
            page.click("dialog button:has-text('Recharger Prévo')")
        if reprendre:
            page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
            page.click("#btn-reprendre")
        attendre_pret(page)
        self.assertEqual(page.evaluate("Donnees.tablesAbimees()"), ["ordres_travail"])
        page.wait_for_function("(morceau) => document.getElementById('alertes-app').textContent.includes(morceau)",
                               arg="ordres_travail.csv, depuis le")
        bandeaux = [texte for texte in page.evaluate(BANDEAUX_JS) if "Fichier abîmé : " in texte]
        self.assertEqual(len(bandeaux), 1, page.evaluate(BANDEAUX_JS))
        self.assertIn(BANDEAU, bandeaux[0])


class TestServeur(CasAbime):

    def test_serveur_fichier_abime_exporte_puis_importe_tel_quel_date_gardee(self):
        source = copier_jeu("entete-tronque", self.temporaire / "a")
        (source / FICHIERS_ABIMES).write_text(json.dumps({"depuis": {"ordres_travail": DATE}}), encoding="utf-8")
        preregler_profil(self.contexte, "responsable", nom="Claire Abîmé")
        page = self.page
        with ServeurPrevo(source=source) as base_a:
            page.goto(base_a.url + "/#/parametres")
            attendre_pret(page)
            original = (base_a.dossier / FICHIER).read_bytes()
            entrees = self.exporter(page)
            self.verifier_marque(entrees, original)
            page.goto("about:blank")
        with ServeurPrevo() as base_b:                       # copie de la démo : base saine
            dossier = base_b.dossier
            self.assertFalse((dossier / FICHIERS_ABIMES).exists())
            page.goto(base_b.url + "/#/parametres")
            attendre_pret(page)
            page.wait_for_load_state("networkidle")

            def csv_actuels():
                return {p.name: p.read_bytes() for p in sorted(dossier.glob("*.csv"))}

            # Refus : empreinte fausse, marque retirée ; un CSV sain marqué est lu comme les autres.
            self.verifier_refus(page, un_octet_change(entrees), "« ordres_travail.csv » ne correspond pas à son "
                                "empreinte dans le manifeste", csv_actuels)
            self.verifier_refus(page, avec_manifeste(entrees, sans_marque), "« ordres_travail.csv » est illisible",
                                csv_actuels)
            sain_marque = avec_manifeste(entrees, lambda m: entree(m, "equipements.csv").update(abime=True))
            lu = page.evaluate(LIRE_ABIMES_JS, base64.b64encode(octets_zip(sain_marque)).decode("ascii"))
            self.assertEqual((lu["ok"], lu["abimes"]), (True, [["ordres_travail", DATE]]), lu["refus"])
            # Import : fichier à l'octet, date d'origine gardée, bandeau après rechargement.
            self.importer(page, entrees)
            self.assertEqual((dossier / FICHIER).read_bytes(), original)
            self.assertEqual(json.loads((dossier / FICHIERS_ABIMES).read_text(encoding="utf-8")),
                             {"depuis": {"ordres_travail": DATE}})
            self.recharger_et_verifier_bandeau(page, reprendre=False)
            self.assertEqual((dossier / FICHIER).read_bytes(), original)


class TestDossier(CasAbime):

    def setUp(self):
        super().setUp()
        self.autoriser_erreur(ERREUR_PING_ABSENT)

    def opfs(self, page):
        return {chemin: base64.b64decode(valeur)
                for chemin, valeur in page.evaluate(INSTANTANE_OPFS_JS, NOM_DOSSIER).items()}

    def ouvrir(self, page, reprendre):
        if reprendre:
            page.click("#btn-reprendre")
        else:
            page.click("#btn-dossier")
        attendre_pret(page)
        self.assertEqual(page.evaluate("App.mode"), "dossier")
        page.evaluate("location.hash = '#/parametres'")
        page.wait_for_selector("#btn-import-zip")
        page.wait_for_load_state("networkidle")

    def test_dossier_fichier_abime_exporte_puis_importe_tel_quel_date_gardee(self):
        base = fichiers_du_jeu("entete-tronque")
        base[FICHIERS_ABIMES] = json.dumps({"depuis": {"ordres_travail": DATE}}).encode("utf-8")
        installer_dossier_simule(self.contexte, NOM_DOSSIER)
        preregler_profil(self.contexte, "responsable", nom="Claire Abîmé")
        page = self.page
        with ServeurStatique(RACINE) as statique:
            page.goto(statique.url + "/index.html")
            page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
            page.evaluate(ECRIRE_OPFS_JS, [NOM_DOSSIER, {chemin: en_base64(o) for chemin, o in base.items()}])
            self.ouvrir(page, reprendre=False)
            original = self.opfs(page)[FICHIER]
            self.assertEqual(original, base[FICHIER])                    # jamais réécrit à l'ouverture
            entrees = self.exporter(page)
            self.verifier_marque(entrees, original)
            # La base redevient saine (ordres_travail.csv de la démo), puis est rouverte.
            demo = (RACINE / "donnees" / "demo" / FICHIER).read_bytes()
            page.evaluate(ECRIRE_OPFS_JS, [NOM_DOSSIER, {FICHIER: en_base64(demo)}])
            page.reload()
            page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
            self.ouvrir(page, reprendre=True)
            self.assertEqual(page.evaluate("Donnees.tablesAbimees()"), [])
            self.assertNotIn("ordres_travail", json.loads(self.opfs(page)[FICHIERS_ABIMES])["depuis"])

            def csv_actuels():
                return {c: o for c, o in self.opfs(page).items() if "/" not in c and c.endswith(".csv")}

            self.verifier_refus(page, un_octet_change(entrees), "« ordres_travail.csv » ne correspond pas à son "
                                "empreinte dans le manifeste", csv_actuels)
            self.verifier_refus(page, avec_manifeste(entrees, sans_marque), "« ordres_travail.csv » est illisible",
                                csv_actuels)
            self.importer(page, entrees)
            apres = self.opfs(page)
            self.assertEqual(apres[FICHIER], original)
            self.assertEqual(json.loads(apres[FICHIERS_ABIMES]), {"depuis": {"ordres_travail": DATE}})
            self.recharger_et_verifier_bandeau(page, reprendre=True)
            apres = self.opfs(page)
            self.assertEqual(apres[FICHIER], original)
            self.assertEqual(json.loads(apres[FICHIERS_ABIMES]), {"depuis": {"ordres_travail": DATE}})


class TestEnTeteServeur(unittest.TestCase):

    def test_en_tete_abime_depuis_seulement_pour_un_csv_abime_avec_la_derogation(self):
        with tempfile.TemporaryDirectory(prefix="prevo-zip-abime-") as temporaire:
            abime = (copier_jeu("entete-tronque", Path(temporaire) / "jeu") / FICHIER).read_bytes()
        coupe = abime.split(b"\r\n", 1)[0] + b"\r\n"          # en-tête coupé, aucune valeur au-delà : pas abîmé
        with ServeurPrevo() as serveur:                         # copie de la démo
            chemin = serveur.dossier / FICHIER
            avant = chemin.read_bytes()
            derogation = {"X-Version-Attendue": version_de(avant), "X-Prevo-Remplacer-Abime": "1"}
            for entetes, corps in (({"X-Version-Attendue": version_de(avant), "X-Prevo-Abime-Depuis": DATE}, abime),
                                   (dict(derogation, **{"X-Prevo-Abime-Depuis": "hier"}), abime),
                                   (dict(derogation, **{"X-Prevo-Abime-Depuis": DATE}), coupe)):
                with self.subTest(entetes=entetes, corps=len(corps)):
                    statut, reponse = requete(serveur, "PUT", "/api/csv/ordres_travail", corps, entetes)
                    self.assertEqual(statut, 400, reponse)
                    self.assertEqual(chemin.read_bytes(), avant)
                    self.assertFalse((serveur.dossier / FICHIERS_ABIMES).exists())
            statut, reponse = requete(serveur, "PUT", "/api/csv/ordres_travail", abime,
                                      dict(derogation, **{"X-Prevo-Abime-Depuis": DATE}))
            self.assertEqual(statut, 200, reponse)
            self.assertEqual(chemin.read_bytes(), abime)
            self.assertEqual(json.loads((serveur.dossier / FICHIERS_ABIMES).read_text(encoding="utf-8")),
                             {"depuis": {"ordres_travail": DATE}})
            statut, reponse = requete(serveur, "PUT", "/api/csv/ordres_travail", avant,
                                      {"X-Version-Attendue": version_de(abime), "X-Prevo-Remplacer-Abime": "1"})
            self.assertEqual(statut, 200, reponse)
            self.assertEqual(chemin.read_bytes(), avant)
            self.assertFalse((serveur.dossier / FICHIERS_ABIMES).exists())


if __name__ == "__main__":
    unittest.main()
