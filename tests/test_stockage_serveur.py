# -*- coding: utf-8 -*-
"""Tests de js/stockage-serveur.js (adaptateur « serveur », §6 et §7 de docs/ARCHITECTURE.md).

Le vrai serveur.py est lancé sur un dossier de données TEMPORAIRE (ServeurPrevo de
tests/commun.py) ; la page tests/fixtures/page-stockage-serveur.html est servie par ce même
serveur (même origine que l'API). Les tests pilotent l'adaptateur depuis le navigateur.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_stockage_serveur.py" -v
"""
import base64
import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from commun import CasNavigateur, ServeurPrevo, ServeurStatique, RACINE, COMPTES_DE_TEST  # noqa: E402

CHEMIN_PAGE = "/tests/fixtures/page-stockage-serveur.html"
BOM = b"\xef\xbb\xbf"
# Le serveur refuse un CSV dont l'en-tête ne commence pas par les colonnes du schéma (audit E2, §22.12) :
# les CSV de ces tests portent le vrai en-tête ; les lignes de données peuvent être plus courtes.
ENTETE_EQUIPEMENTS = (
    "id;repere;designation;localisation_id;parent_id;marque;modele;num_serie;date_mes;criticite;statut;"
    "heures_fonct_jour;habilitation_requise;consignation;document;actif;valeur_remplacement")
ENTETE_JOURNAL = "id;date_heure;poste;profil;table;id_ligne;action"
CSV_EQUIPEMENTS = BOM + (
    ENTETE_EQUIPEMENTS + "\r\n"
    "EQ-0001;;Pompe d'alimentation;LOC-0001\r\n"
    "EQ-0002;;Compresseur d'atelier;LOC-0002\r\n").encode("utf-8")
CSV_EQUIPEMENTS_V2 = BOM + (
    ENTETE_EQUIPEMENTS + "\r\n"
    "EQ-0001;;Pompe modifiée;LOC-0001\r\n").encode("utf-8")
# Image PNG de 1 pixel : sert à vérifier qu'un document s'affiche dans une <img>.
PNG_UN_PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")

# Chromium écrit en console chaque réponse ≥ 400 et chaque connexion refusée : c'est normal ici,
# les tests vérifient eux-mêmes les résultats.
ERREUR_RESEAU_ATTENDUE = "Failed to load resource"

MESSAGE_SERVEUR_INJOIGNABLE = (
    "Le serveur Prévo ne répond pas. Vérifiez que la fenêtre du serveur est ouverte sur le PC.")


def empreinte(octets):
    """Version d'un fichier : SHA-256, 16 premiers caractères hexadécimaux (décision D7)."""
    return hashlib.sha256(octets).hexdigest()[:16]


# Enveloppe JavaScript : exécute `corps` avec `stockage` (adaptateur neuf) et `argument`,
# et rend { ok: valeur } ou { erreur: { nom, message, versionActuelle, ... } }.
GABARIT_JS = """
async (argument) => {
  const stockage = StockageServeur.creer();
  const versOctets = (liste) => new Uint8Array(liste);
  const versListe = (octets) => (octets === null ? null : Array.from(octets));
  try {
    const valeur = await (async () => { %s })();
    return { ok: valeur === undefined ? null : valeur };
  } catch (erreur) {
    return { erreur: {
      nom: erreur.name,
      message: erreur.message,
      versionActuelle: erreur.versionActuelle === undefined ? 'absent' : erreur.versionActuelle,
      estConflit: erreur instanceof Donnees.ErreurConflit,
      estStockage: erreur instanceof Donnees.ErreurStockage,
    } };
  }
}
"""


class CasStockageServeur(CasNavigateur):
    """Base : ouvre la page de test sur un serveur et exécute du JavaScript avec l'adaptateur."""

    def setUp(self):
        super().setUp()
        self.autoriser_erreur(ERREUR_RESEAU_ATTENDUE)

    def ouvrir(self, serveur, page=None):
        page = page or self.page
        page.goto(serveur.url + CHEMIN_PAGE)
        page.wait_for_function("typeof StockageServeur === 'object'")
        return page

    def executer(self, corps, argument=None, page=None):
        page = page or self.page
        return page.evaluate(GABARIT_JS % corps, argument)

    def executer_ok(self, corps, argument=None, page=None):
        resultat = self.executer(corps, argument, page)
        self.assertNotIn("erreur", resultat, "erreur inattendue : %r" % resultat)
        return resultat["ok"]

    def executer_erreur(self, corps, argument=None, page=None):
        resultat = self.executer(corps, argument, page)
        self.assertIn("erreur", resultat, "une erreur était attendue, reçu : %r" % resultat)
        return resultat["erreur"]


class TestDetection(CasStockageServeur):

    def test_detecter_vrai_sur_le_serveur_prevo(self):
        with ServeurPrevo(source=None) as serveur:
            self.ouvrir(serveur)
            self.assertTrue(self.page.evaluate("StockageServeur.detecter()"))

    def test_detecter_faux_sur_un_serveur_statique(self):
        # Un simple serveur de fichiers n'a pas /api/ping (404) : ce n'est pas Prévo.
        with ServeurStatique(RACINE) as statique:
            self.page.goto(statique.url + CHEMIN_PAGE)
            self.page.wait_for_function("typeof StockageServeur === 'object'")
            self.assertFalse(self.page.evaluate("StockageServeur.detecter()"))

    def test_detecter_faux_quand_le_serveur_est_arrete(self):
        with ServeurPrevo(source=None) as serveur:
            self.ouvrir(serveur)
            serveur.arreter()
            self.assertFalse(self.page.evaluate("StockageServeur.detecter()"))

    def test_adaptateur_mode_et_libelle(self):
        with ServeurPrevo(source=None) as serveur:
            self.ouvrir(serveur)
            resultat = self.executer_ok(
                "return { mode: stockage.mode, libelle: stockage.libelle, hote: location.host };")
            self.assertEqual(resultat["mode"], "serveur")
            self.assertEqual(resultat["libelle"], "Serveur " + resultat["hote"])
            self.assertIn(str(serveur.port), resultat["libelle"])


class TestCsv(CasStockageServeur):

    def test_lecture_d_un_csv_octets_et_version(self):
        with ServeurPrevo(source=None) as serveur:
            (serveur.dossier / "equipements.csv").write_bytes(CSV_EQUIPEMENTS)
            self.ouvrir(serveur)
            resultat = self.executer_ok(
                "const r = await stockage.charger('equipements');"
                "return { octets: versListe(r.octets), version: r.version,"
                "         typeOctets: r.octets.constructor.name };")
            self.assertEqual(resultat["typeOctets"], "Uint8Array")
            self.assertEqual(bytes(resultat["octets"]), CSV_EQUIPEMENTS)
            self.assertEqual(resultat["version"], empreinte(CSV_EQUIPEMENTS))

    def test_table_absente_donne_null(self):
        with ServeurPrevo(source=None) as serveur:
            self.ouvrir(serveur)
            resultat = self.executer_ok("return await stockage.charger('equipements');")
            self.assertEqual(resultat, {"octets": None, "version": None})

    def test_creation_puis_conflit_si_le_fichier_existe_deja(self):
        with ServeurPrevo(source=None) as serveur:
            self.ouvrir(serveur)
            script = "return await stockage.enregistrer('equipements', versOctets(argument), null);"
            octets = list(CSV_EQUIPEMENTS)
            resultat = self.executer_ok(script, octets)
            self.assertEqual(resultat["version"], empreinte(CSV_EQUIPEMENTS))
            self.assertEqual((serveur.dossier / "equipements.csv").read_bytes(), CSV_EQUIPEMENTS)
            # Deuxième création : le fichier existe, c'est un conflit qui porte la version actuelle.
            erreur = self.executer_erreur(script, list(CSV_EQUIPEMENTS_V2))
            self.assertTrue(erreur["estConflit"], erreur)
            self.assertEqual(erreur["nom"], "ErreurConflit")
            self.assertEqual(erreur["versionActuelle"], empreinte(CSV_EQUIPEMENTS))
            self.assertEqual((serveur.dossier / "equipements.csv").read_bytes(), CSV_EQUIPEMENTS)

    def test_mise_a_jour_avec_la_bonne_version(self):
        with ServeurPrevo(source=None) as serveur:
            (serveur.dossier / "equipements.csv").write_bytes(CSV_EQUIPEMENTS)
            self.ouvrir(serveur)
            resultat = self.executer_ok(
                "const lu = await stockage.charger('equipements');"
                "return await stockage.enregistrer('equipements', versOctets(argument), lu.version);",
                list(CSV_EQUIPEMENTS_V2))
            self.assertEqual(resultat["version"], empreinte(CSV_EQUIPEMENTS_V2))
            self.assertEqual((serveur.dossier / "equipements.csv").read_bytes(), CSV_EQUIPEMENTS_V2)

    def test_version_perimee_donne_un_conflit_avec_la_version_actuelle(self):
        with ServeurPrevo(source=None) as serveur:
            (serveur.dossier / "equipements.csv").write_bytes(CSV_EQUIPEMENTS)
            self.ouvrir(serveur)
            erreur = self.executer_erreur(
                "return await stockage.enregistrer('equipements', versOctets(argument), '0123456789abcdef');",
                list(CSV_EQUIPEMENTS_V2))
            self.assertTrue(erreur["estConflit"], erreur)
            self.assertEqual(erreur["versionActuelle"], empreinte(CSV_EQUIPEMENTS))
            self.assertEqual((serveur.dossier / "equipements.csv").read_bytes(), CSV_EQUIPEMENTS)

    def test_version_attendue_sur_un_fichier_absent_donne_un_conflit_sans_version(self):
        with ServeurPrevo(source=None) as serveur:
            self.ouvrir(serveur)
            erreur = self.executer_erreur(
                "return await stockage.enregistrer('equipements', versOctets(argument), '0123456789abcdef');",
                list(CSV_EQUIPEMENTS))
            self.assertTrue(erreur["estConflit"], erreur)
            self.assertIsNone(erreur["versionActuelle"])

    def test_deux_pages_meme_version_une_seule_passe(self):
        with ServeurPrevo(source=None) as serveur:
            (serveur.dossier / "equipements.csv").write_bytes(CSV_EQUIPEMENTS)
            page_a = self.ouvrir(serveur)
            page_b = self.contexte.new_page()
            self.surveiller(page_b)
            self.ouvrir(serveur, page_b)
            lecture = "const lu = await stockage.charger('equipements'); return lu.version;"
            version_a = self.executer_ok(lecture, page=page_a)
            version_b = self.executer_ok(lecture, page=page_b)
            self.assertEqual(version_a, version_b)

            script = ("return await stockage.enregistrer('equipements', versOctets(argument.octets),"
                      " argument.version);")
            reussite = self.executer_ok(
                script, {"octets": list(CSV_EQUIPEMENTS_V2), "version": version_a}, page=page_a)
            self.assertEqual(reussite["version"], empreinte(CSV_EQUIPEMENTS_V2))
            autre = bytes(CSV_EQUIPEMENTS_V2) + b"EQ-0009;Autre;LOC-0001\r\n"
            erreur = self.executer_erreur(
                script, {"octets": list(autre), "version": version_b}, page=page_b)
            self.assertTrue(erreur["estConflit"], erreur)
            self.assertEqual(erreur["versionActuelle"], empreinte(CSV_EQUIPEMENTS_V2))
            self.assertEqual((serveur.dossier / "equipements.csv").read_bytes(), CSV_EQUIPEMENTS_V2)

    def test_deux_ecritures_simultanees_une_seule_passe(self):
        with ServeurPrevo(source=None) as serveur:
            (serveur.dossier / "equipements.csv").write_bytes(CSV_EQUIPEMENTS)
            self.ouvrir(serveur)
            resultat = self.executer_ok(
                "const lu = await stockage.charger('equipements');"
                "const essais = [1, 2].map((n) => stockage.enregistrer("
                "  'equipements', new TextEncoder().encode('" + ENTETE_EQUIPEMENTS + "\\r\\nEQ-000' + n + ';;n\\r\\n'),"
                "  lu.version));"
                "const issues = await Promise.allSettled(essais);"
                "return issues.map((i) => i.status === 'fulfilled' ? 'ok'"
                "  : (i.reason instanceof Donnees.ErreurConflit ? 'conflit' : 'autre:' + i.reason));")
            self.assertEqual(sorted(resultat), ["conflit", "ok"])

    def test_ajouter_cree_puis_complete_le_fichier(self):
        with ServeurPrevo(source=None) as serveur:
            self.ouvrir(serveur)
            script = "return await stockage.ajouter('journal', new TextEncoder().encode(argument));"
            entete = ENTETE_JOURNAL + "\r\n"
            premiere = self.executer_ok(script, entete + "JRN-1;2026-10-19 08:00;;;equipements;;création\r\n")
            contenu = (serveur.dossier / "journal.csv").read_bytes()
            self.assertEqual(premiere["version"], empreinte(contenu))
            self.assertTrue(contenu.startswith(BOM))
            seconde = self.executer_ok(script, entete + "JRN-2;2026-10-19 08:05;;;equipements;;modification\r\n")
            contenu = (serveur.dossier / "journal.csv").read_bytes()
            self.assertEqual(seconde["version"], empreinte(contenu))
            self.assertEqual(
                contenu.decode("utf-8-sig"),
                entete + "JRN-1;2026-10-19 08:00;;;equipements;;création\r\n"
                + "JRN-2;2026-10-19 08:05;;;equipements;;modification\r\n")

    def test_ajouter_avec_un_autre_en_tete_donne_un_conflit(self):
        with ServeurPrevo(source=None) as serveur:
            # Fichier existant : en-tête du schéma plus une colonne ajoutée dans Excel ;
            # corps : en-tête du schéma seul.
            (serveur.dossier / "journal.csv").write_bytes(BOM + (ENTETE_JOURNAL + ";colonne_excel\r\n").encode("utf-8"))
            self.ouvrir(serveur)
            erreur = self.executer_erreur(
                "return await stockage.ajouter('journal', new TextEncoder().encode('"
                + ENTETE_JOURNAL + "\\r\\n1;2\\r\\n'));")
            self.assertTrue(erreur["estConflit"], erreur)

    def test_lister_versions_donne_les_22_tables(self):
        with ServeurPrevo(source=None) as serveur:
            (serveur.dossier / "equipements.csv").write_bytes(CSV_EQUIPEMENTS)
            self.ouvrir(serveur)
            versions = self.executer_ok("return await stockage.listerVersions();")
            self.assertEqual(len(versions), 24)
            noms_schema = self.page.evaluate("Schema.nomsTables()")
            self.assertEqual(sorted(versions), sorted(noms_schema))
            self.assertEqual(versions["equipements"], empreinte(CSV_EQUIPEMENTS))
            self.assertIsNone(versions["journal"])
            self.assertEqual(sum(1 for v in versions.values() if v is not None), 1)

    def test_les_erreurs_serveur_deviennent_des_erreurs_de_stockage(self):
        with ServeurPrevo(source=None) as serveur:
            self.ouvrir(serveur)
            # Table inconnue : le serveur répond 404 avec un message, qui devient une ErreurStockage.
            erreur = self.executer_erreur(
                "return await stockage.enregistrer('table_inconnue', versOctets(argument), null);",
                list(CSV_EQUIPEMENTS))
            self.assertTrue(erreur["estStockage"], erreur)
            self.assertIn("Table inconnue", erreur["message"])


class TestDocuments(CasStockageServeur):

    def test_document_ecrit_puis_relu_a_l_identique(self):
        with ServeurPrevo(source=None) as serveur:
            self.ouvrir(serveur)
            nom = self.executer_ok(
                "const blob = new Blob([versOctets(argument)], { type: 'image/png' });"
                "return await stockage.ecrireDocument('photo-test.png', blob);",
                list(PNG_UN_PIXEL))
            # Audit F4 (T159) : l'adaptateur rend le nom imposé par le serveur, « AAAAMMJJ-HHMMSS-<nom demandé> »
            self.assertRegex(nom, r"^\d{8}-\d{6}-photo-test\.png$")
            self.assertEqual((serveur.dossier / "documents" / nom).read_bytes(), PNG_UN_PIXEL)
            self.assertFalse((serveur.dossier / "documents" / "photo-test.png").exists())
            relu = self.executer_ok(
                "const blob = await stockage.lireDocument(argument);"
                "return { type: blob.type, octets: Array.from(new Uint8Array(await blob.arrayBuffer())) };", nom)
            self.assertEqual(relu["type"], "image/png")
            self.assertEqual(bytes(relu["octets"]), PNG_UN_PIXEL)

    def test_jamais_d_ecrasement_du_meme_nom_demande(self):
        # Même nom demandé deux fois : dans la même seconde le serveur répond 409 (« porte déjà ce nom » ; prouvé sans
        # aléa dans test_audit_reseau), à la seconde suivante il impose un autre nom. Le premier reste intact.
        with ServeurPrevo(source=None) as serveur:
            self.ouvrir(serveur)
            script = ("const blob = new Blob([versOctets(argument)], { type: 'image/png' });"
                      "return await stockage.ecrireDocument('photo-test.png', blob);")
            premier = self.executer_ok(script, list(PNG_UN_PIXEL))
            resultat = self.executer(script, list(PNG_UN_PIXEL) + [0])
            if "erreur" in resultat:
                erreur = resultat["erreur"]
                self.assertTrue(erreur["estStockage"], erreur)
                self.assertFalse(erreur["estConflit"])
                self.assertIn("porte déjà ce nom", erreur["message"])
                self.assertEqual(sorted(p.name for p in (serveur.dossier / "documents").iterdir()), [premier])
            else:
                self.assertNotEqual(resultat["ok"], premier)
                self.assertEqual((serveur.dossier / "documents" / resultat["ok"]).read_bytes(), PNG_UN_PIXEL + b"\x00")
            self.assertEqual((serveur.dossier / "documents" / premier).read_bytes(), PNG_UN_PIXEL)

    def test_document_absent_donne_null(self):
        with ServeurPrevo(source=None) as serveur:
            self.ouvrir(serveur)
            self.assertIsNone(self.executer_ok("return await stockage.lireDocument('absent.png');"))

    def test_url_document_est_encodee_et_affichable_dans_une_image(self):
        with ServeurPrevo(source=None) as serveur:
            self.ouvrir(serveur)
            self.assertEqual(
                self.executer_ok("return await stockage.urlDocument('a b+c.png');"),
                "/api/documents/a%20b%2Bc.png")
            nom = self.executer_ok(
                "const blob = new Blob([versOctets(argument)], { type: 'image/png' });"
                "return await stockage.ecrireDocument('photo-test.png', blob);",
                list(PNG_UN_PIXEL))
            largeur = self.executer_ok(
                "const adresse = await stockage.urlDocument(argument);"       # nom imposé par le serveur (T159)
                "const image = new Image();"
                "await new Promise((fini, echec) => {"
                "  image.onload = fini; image.onerror = () => echec(new Error('image non chargée'));"
                "  image.src = adresse; });"
                "return image.naturalWidth;", nom)
            self.assertEqual(largeur, 1)


class TestSauvegardes(CasStockageServeur):

    def test_sauvegarde_manuelle_liste_et_restauration(self):
        with ServeurPrevo(source=None) as serveur:
            (serveur.dossier / "equipements.csv").write_bytes(CSV_EQUIPEMENTS)
            self.ouvrir(serveur)
            nom = self.executer_ok("return await stockage.sauvegarder();")
            self.assertRegex(nom, r"^\d{4}-\d{2}-\d{2}_\d{6}$")

            liste = self.executer_ok("return await stockage.listerSauvegardes();")
            self.assertEqual(liste[0]["nom"], nom)          # la plus récente d'abord
            self.assertIn("equipements", liste[0]["tables"])

            # On modifie la table, puis on restaure uniquement celle-là.
            lu = self.executer_ok("return await stockage.charger('equipements');")
            self.executer_ok(
                "return await stockage.enregistrer('equipements', versOctets(argument), '%s');" % lu["version"],
                list(CSV_EQUIPEMENTS_V2))
            self.assertEqual((serveur.dossier / "equipements.csv").read_bytes(), CSV_EQUIPEMENTS_V2)

            resultat = self.executer_ok(
                "return await stockage.restaurer(argument.nom, argument.tables);",
                {"nom": nom, "tables": ["equipements"]})
            self.assertEqual(resultat["restaurees"], ["equipements"])
            self.assertRegex(resultat["copieSecurite"], r"^\d{4}-\d{2}-\d{2}_\d{6}_avant-restauration$")
            self.assertEqual((serveur.dossier / "equipements.csv").read_bytes(), CSV_EQUIPEMENTS)
            self.assertTrue((serveur.dossier / "sauvegardes" / resultat["copieSecurite"]
                             / "equipements.csv").is_file())
            # La copie de sécurité garde l'état d'avant la restauration.
            self.assertEqual((serveur.dossier / "sauvegardes" / resultat["copieSecurite"]
                              / "equipements.csv").read_bytes(), CSV_EQUIPEMENTS_V2)

    def test_restauration_de_toutes_les_tables(self):
        with ServeurPrevo(source=None) as serveur:
            (serveur.dossier / "equipements.csv").write_bytes(CSV_EQUIPEMENTS)
            self.ouvrir(serveur)
            nom = self.executer_ok("return await stockage.sauvegarder();")
            (serveur.dossier / "equipements.csv").write_bytes(CSV_EQUIPEMENTS_V2)
            resultat = self.executer_ok("return await stockage.restaurer(argument);", nom)
            self.assertEqual(resultat["restaurees"], ["equipements"])
            self.assertEqual((serveur.dossier / "equipements.csv").read_bytes(), CSV_EQUIPEMENTS)

    def test_restaurer_une_sauvegarde_inconnue_donne_une_erreur_de_stockage(self):
        with ServeurPrevo(source=None) as serveur:
            self.ouvrir(serveur)
            erreur = self.executer_erreur("return await stockage.restaurer('2020-01-01_000000');")
            self.assertTrue(erreur["estStockage"], erreur)
            self.assertIn("Sauvegarde introuvable", erreur["message"])


class TestInfoEtServeurArrete(CasStockageServeur):

    def test_info_donne_un_tableau_d_adresses_reseau(self):
        with ServeurPrevo(source=None) as serveur:
            self.ouvrir(serveur)
            info = self.executer_ok("return await stockage.info();")
            self.assertIsInstance(info["adressesReseau"], list)
            self.assertEqual(info["port"], serveur.port)
            for adresse in info["adressesReseau"]:
                self.assertTrue(re.match(r"^http://[\d.]+:%d/$" % serveur.port, adresse), adresse)

    def test_serveur_arrete_donne_une_erreur_de_stockage_explicite(self):
        with ServeurPrevo(source=None) as serveur:
            self.ouvrir(serveur)
            serveur.arreter()
            operations = {
                "charger": "return await stockage.charger('equipements');",
                "enregistrer": "return await stockage.enregistrer('equipements', new Uint8Array([1]), null);",
                "ajouter": "return await stockage.ajouter('journal', new Uint8Array([1]));",
                "listerVersions": "return await stockage.listerVersions();",
                "sauvegarder": "return await stockage.sauvegarder();",
                "info": "return await stockage.info();",
            }
            for nom, corps in operations.items():
                with self.subTest(operation=nom):
                    erreur = self.executer_erreur(corps)
                    self.assertEqual(erreur["nom"], "ErreurStockage")
                    self.assertTrue(erreur["estStockage"])
                    self.assertEqual(erreur["message"], MESSAGE_SERVEUR_INJOIGNABLE)


class TestComptes(CasStockageServeur):
    """Lot 7 (T154) : ServeurPrevo(comptes=True) et l'adaptateur face à 401 et 403 (§22.4, §22.5)."""

    ECOUTEUR_JS = ("window.__sessionsAbsentes = []; document.addEventListener(StockageServeur.EVENEMENT_SESSION_ABSENTE, "
                   "(e) => window.__sessionsAbsentes.push(e.detail));")

    def test_usage_par_defaut_inchange_sans_comptes(self):
        with ServeurPrevo(source=None) as serveur:
            self.ouvrir(serveur)
            session = self.executer_ok("return await stockage.session();")
            self.assertEqual(session, {"comptes": False, "session": None})
            self.assertFalse((serveur.dossier / "acces").exists())
            with self.assertRaises(ValueError):
                serveur.session("responsable")

    def test_sans_session_401_evenement_puis_avec_session_lecture_et_403_du_role(self):
        with ServeurPrevo(comptes=True) as serveur:
            self.assertEqual(set(json.loads((serveur.dossier / "acces" / "comptes.json").read_text("utf-8"))
                                 ["comptes"][0].keys()) >= {"identifiant", "role", "empreinte"}, True)
            self.ouvrir(serveur)
            self.page.evaluate(self.ECOUTEUR_JS)
            # Sans cookie : /api/session reste publique ; une table rend 401, ErreurStockage + événement.
            self.assertEqual(self.executer_ok("return await stockage.session();"), {"comptes": True, "session": None})
            erreur = self.executer_erreur("return await stockage.charger('equipements');")
            self.assertTrue(erreur["estStockage"], erreur)
            self.assertIn("Connexion nécessaire", erreur["message"])
            self.assertEqual(self.page.evaluate("window.__sessionsAbsentes.length"), 1)
            self.assertEqual(self.page.evaluate("window.__sessionsAbsentes[0].appareilRefuse"), False)
            self.assertIn("Connexion nécessaire", self.page.evaluate("window.__sessionsAbsentes[0].message"))
            self.executer_erreur("return await stockage.charger('equipements');")      # un seul événement par seconde
            self.assertEqual(self.page.evaluate("window.__sessionsAbsentes.length"), 1)
            # Session du technicien posée dans le contexte : lecture permise, écriture de parametres refusée (403).
            cookie = serveur.poser_session(self.contexte, "technicien", profil=False)
            self.assertRegex(cookie, r"^id=[A-Za-z0-9_-]{43}$")
            self.ouvrir(serveur)
            self.page.evaluate(self.ECOUTEUR_JS)
            session = self.executer_ok("return await stockage.session();")
            self.assertEqual((session["comptes"], session["session"]["identifiant"], session["session"]["role"],
                              session["session"]["technicienId"], session["session"]["aChanger"],
                              session["session"]["appareil"]),
                             (True, COMPTES_DE_TEST["technicien"][0], "technicien", "TEC-0001", False, False))
            lu = self.executer_ok("const r = await stockage.charger('equipements'); return r.octets !== null;")
            self.assertTrue(lu)
            refus = self.executer_erreur(
                "return await stockage.enregistrer('parametres', versOctets(argument), null);",
                list(BOM + b"cle;valeur\r\nessai;1\r\n"))
            self.assertTrue(refus["estStockage"], refus)
            self.assertTrue(refus["message"].startswith("Accès refusé"), refus)
            self.assertEqual(self.page.evaluate("window.__sessionsAbsentes.length"), 0)     # 403 : pas un 401
            # Réglage en plus par « reglages » : session courte, cookie d'un autre rôle.
            self.assertEqual(serveur.session("responsable")[:3], "id=")
        with ServeurPrevo(comptes=True, reglages={"invitation_heures": 2}) as serveur:
            configuration = json.loads((serveur._racine_temporaire / "prevo.config.json").read_text("utf-8"))
            self.assertEqual(configuration, {"invitation_heures": 2, "comptes": True})


class TestReponsesAnormales(CasStockageServeur):
    """fetch simulé (page servie par un simple serveur statique) : délais, réponses inattendues."""

    # window.reponses : file de réponses { statut, corps } ou 'jamais' (aucune réponse ; la
    # promesse n'est rejetée que si la requête est abandonnée par son signal).
    # setTimeout est accéléré : un délai de 15 s devient 50 ms.
    FETCH_SIMULE = """() => {
      window.reponses = [];
      window.fetch = (url, options) => {
        const r = window.reponses.shift();
        if (r === 'jamais') {
          return new Promise((_, rejeter) => {
            const signal = options && options.signal;
            if (signal) {
              signal.addEventListener('abort', () => rejeter(new DOMException('abandon', 'AbortError')));
            }
          });
        }
        return Promise.resolve(new Response(r.corps, { status: r.statut, headers: r.entetes || {} }));
      };
      const vraiSetTimeout = window.setTimeout.bind(window);
      window.setTimeout = (f, delai, ...reste) => vraiSetTimeout(f, delai >= 15000 ? 50 : delai, ...reste);
    }"""

    def setUp(self):
        super().setUp()
        self.statique = ServeurStatique(RACINE)
        self.statique.demarrer()
        self.addCleanup(self.statique.arreter)
        self.page.goto(self.statique.url + CHEMIN_PAGE)
        self.page.wait_for_function("typeof StockageServeur === 'object'")
        self.page.evaluate(self.FETCH_SIMULE)

    def reponses(self, *reponses):
        self.page.evaluate("(liste) => { window.reponses.push(...liste); }", list(reponses))

    def test_serveur_qui_ne_repond_jamais_donne_une_erreur_de_delai(self):
        self.reponses("jamais")
        resultat = self.page.evaluate("""async () => {
          const stockage = StockageServeur.creer();
          const essai = stockage.enregistrer('equipements', new Uint8Array([1]), 'abc')
            .then(() => 'réussi', (e) => e.name + ' | ' + e.message);
          return Promise.race([essai, new Promise((r) => window.setTimeout(() => r('TOUJOURS EN ATTENTE'), 3000))]);
        }""")
        self.assertTrue(resultat.startswith("ErreurStockage | Le serveur Prévo met trop de temps à répondre"),
                        resultat)

    def test_reponse_200_qui_n_est_pas_du_json(self):
        self.reponses({"statut": 200, "corps": "<html>portail captif</html>"})
        erreur = self.executer_erreur("return await stockage.enregistrer('equipements', new Uint8Array([1]), 'abc');")
        self.assertTrue(erreur["estStockage"], erreur)
        self.assertNotEqual(erreur["message"], MESSAGE_SERVEUR_INJOIGNABLE)
        self.assertIn("Réponse inattendue du serveur", erreur["message"])
        self.assertIn("rechargez la page", erreur["message"])

    def test_404_d_une_table_hors_schema_n_est_pas_un_fichier_absent(self):
        self.reponses({"statut": 404, "corps": '{"erreur":"Table inconnue : zz."}'})
        erreur = self.executer_erreur("return await stockage.charger('zz');")
        self.assertTrue(erreur["estStockage"], erreur)
        self.assertIn("Table inconnue", erreur["message"])
        # Une table du schéma en 404 reste un fichier absent.
        self.reponses({"statut": 404, "corps": '{"erreur":"Fichier absent."}'})
        self.assertEqual(self.executer_ok("return await stockage.charger('equipements');"),
                         {"octets": None, "version": None})

    def test_versions_sans_cle_tables(self):
        self.reponses({"statut": 200, "corps": "{}"})
        erreur = self.executer_erreur("return await stockage.listerVersions();")
        self.assertEqual(erreur["nom"], "ErreurStockage", erreur)
        self.assertTrue(erreur["estStockage"], erreur)


class TestMessagesTraduits(CasStockageServeur):
    """T246 (D157) : un message du serveur arrive avec son code et ses valeurs ; le navigateur affiche la clé
    serveur.<code> de la langue active, le français reçu quand il ne connaît pas le code. Une « autre langue » est
    simulée en remplaçant la valeur française d'une clé (I18n.ajouter)."""

    def setUp(self):
        super().setUp()
        self.statique = ServeurStatique(RACINE)
        self.statique.demarrer()
        self.addCleanup(self.statique.arreter)
        self.page.goto(self.statique.url + CHEMIN_PAGE)
        self.page.wait_for_function("typeof StockageServeur === 'object'")
        self.page.evaluate(TestReponsesAnormales.FETCH_SIMULE)

    def reponses(self, *reponses):
        self.page.evaluate("(liste) => { window.reponses.push(...liste); }", list(reponses))

    def autre_langue(self, cles):
        self.page.evaluate("(cles) => I18n.ajouter('fr', cles)", cles)

    def test_en_francais_le_message_du_dictionnaire_est_celui_du_serveur(self):
        corps = {"erreur": "Table inconnue : zz.", "erreur_code": "csv.table_inconnue",
                 "erreur_valeurs": {"table": "zz"}}
        self.assertEqual(self.page.evaluate("(d) => StockageServeur.texte(d, 'erreur')", corps),
                         "Table inconnue : zz.")

    def test_erreur_traduite_par_son_code_sinon_le_francais_recu(self):
        self.autre_langue({"serveur.csv.table_inconnue": "Unknown table: {table}."})
        self.reponses({"statut": 404, "corps": json.dumps({"erreur": "Table inconnue : zz.",
                                                          "erreur_code": "csv.table_inconnue",
                                                          "erreur_valeurs": {"table": "zz"}})})
        self.assertEqual(self.executer_erreur("return await stockage.charger('zz');")["message"],
                         "Unknown table: zz.")
        # Code que ce navigateur ne connaît pas (serveur plus récent) : le français reçu, tel quel.
        self.reponses({"statut": 400, "corps": json.dumps({"erreur": "Message d'un serveur plus récent.",
                                                          "erreur_code": "essai.code_inconnu"})})
        self.assertEqual(self.executer_erreur("return await stockage.charger('zz');")["message"],
                         "Message d'un serveur plus récent.")

    def test_valeurs_message_imbrique_liste_pluriel_et_point_final(self):
        self.autre_langue({"serveur.acces.ajout_seulement": "Refused: {raison}",
                           "serveur.demandes.numero_pris": "number {numero} is taken.",
                           "serveur.demandes.non_supprimable": "a request cannot be deleted ({demandes}).",
                           "serveur.demandes.sans_numero": "no number",
                           "serveur.sauvegardes.plafond_manuelles": {"one": "wait {n} second.",
                                                                     "other": "wait {n} seconds."},
                           "serveur.tailscale.lancement_impossible": "tailscale could not start ({erreur})."})
        texte = "(d) => StockageServeur.texte(d, Object.keys(d)[0])"
        imbrique = {"erreur": "fr", "erreur_code": "acces.ajout_seulement",
                    "erreur_valeurs": {"raison": {"code": "demandes.numero_pris", "texte": "fr",
                                                  "valeurs": {"numero": "DI-7"}}}}
        self.assertEqual(self.page.evaluate(texte, imbrique), "Refused: number DI-7 is taken.")
        liste = {"erreur": "fr", "erreur_code": "demandes.non_supprimable",
                 "erreur_valeurs": {"demandes": ["DI-1", {"code": "demandes.sans_numero", "texte": "sans numéro"}]}}
        self.assertEqual(self.page.evaluate(texte, liste), "a request cannot be deleted (DI-1, no number).")
        for n, attendu in ((1, "wait 1 second."), (50, "wait 50 seconds.")):
            pluriel = {"erreur": "fr", "erreur_code": "sauvegardes.plafond_manuelles", "erreur_valeurs": {"n": n}}
            self.assertEqual(self.page.evaluate(texte, pluriel), attendu)
        sans_point = {"raison": "fr", "raison_code": "tailscale.lancement_impossible",
                      "raison_valeurs": {"erreur": "x"}, "raison_sans_point": True}
        self.assertEqual(self.page.evaluate(texte, sans_point), "tailscale could not start (x)")
        self.assertEqual(self.page.evaluate(texte, {"message": "sans code"}), "sans code")

    def test_copie_externe_et_test_d_une_sauvegarde_traduits(self):
        self.autre_langue({"serveur.copie.dossier_introuvable": "Copy folder « {nom} » not found.",
                           "serveur.sauvegardes.test_vide": "Empty file."})
        self.reponses({"statut": 200, "corps": json.dumps({"adresses_reseau": [], "port": 8080, "copie_externe": {
            "derniere_reussie": None, "jours_sans_copie": None, "erreur": "Dossier de copie « Cle » introuvable.",
            "erreur_code": "copie.dossier_introuvable", "erreur_valeurs": {"nom": "Cle"}}})})
        self.assertEqual(self.executer_ok("return (await stockage.info()).copieExterne.erreur;"),
                         "Copy folder « Cle » not found.")
        self.reponses({"statut": 200, "corps": json.dumps({"nom": "s", "ok": False, "tables": [
            {"table": "fournisseurs", "lignes": None, "erreur": "Fichier vide : la ligne d'en-tête manque.",
             "erreur_code": "sauvegardes.test_vide"},
            {"table": "demandes", "lignes": 2, "erreur": None}]})})
        tables = self.executer_ok("return (await stockage.testerSauvegarde('s')).tables;")
        self.assertEqual([table["erreur"] for table in tables], ["Empty file.", None])


if __name__ == "__main__":
    unittest.main()
