"""Lot 7 — corrections de l'audit F2, F4 et I2 (D134, CS134 ; ARCHITECTURE.md §7, §22.12 ; tâche T159).

Un test par constat : le scénario de l'annexe A de l'audit est rejoué, puis le refus attendu est vérifié.

    F2  sémaphore     32 connexions tenues ouvertes : la 33e attend (ni refusée ni perdue) et passe dès qu'une des 32
                      se termine, en un temps borné ; la limite est celle du processus (porte et application) ;
        quota         quota_documents_mo = 1 : un document de 600 Ko passe, le suivant de 600 Ko est refusé 413 au
                      message clair et rien n'est écrit ; un petit document passe encore ;
        corps         le corps n'est jamais lu avant le contrôle de session : prouvé par
                      test_acces_sessions.test_corps_jamais_lu_sans_session (cité, pas dupliqué) ;
        429           une sauvegarde manuelle par minute : prouvé par
                      test_sauvegardes_lot7.test_deuxieme_sauvegarde_manuelle_de_la_minute_429 (cité) ;
        délai IA      délai fixé par le serveur (120 s) : prouvé par test_audit_ia.test_adresse_cle_et_delai_du_serveur
                      (cité) ;
    F4  .xls / .doc   415 à l'écriture (rien d'écrit) comme à la lecture d'un nom en .xls ou .doc ;
        disposition   Content-Disposition: attachment sur un .docx, un .txt et un .csv, absent sur un .jpg, un .pdf et
                      le rapport figé en .html (ouvert dans un onglet par « Ouvrir », exécution interdite par
                      « sandbox ») ; « sandbox » et nosniff partout ;
        nom imposé    la réponse 201 rend « AAAAMMJJ-HHMMSS-<nom demandé> » (extension en minuscules), le fichier est
                      sur le disque sous ce nom, il se lit par ce nom et jamais par le nom demandé ; même nom demandé
                      dans la même seconde : 409, l'original intact (horloge simulée, sans aléa) ; une photo de
                      demande garde son préfixe devant MOTIF_PHOTO_DE_DEMANDE ;
        signature     un .jpg qui commence par « %PDF » ⇒ 400 et rien d'écrit ; un vrai JPEG minimal passe ; un faux
                      PNG ⇒ 400, un vrai passe ; un PDF n'est pas contrôlé ;
    I2  repr          un chemin qui porte un caractère de contrôle (ESC, 0x01) ou « %0A » est écrit en repr sur la
                      console : aucun retour à la ligne ni séquence d'échappement n'y est injecté.

Serveur réel sur une copie vide des données (ServeurPrevo de commun.py) ; le 409 et le motif des photos sont joués sur
serveur.py importé, avec une horloge simulée. Aucune commande d'administrateur, aucune sortie réseau (127.0.0.1).

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_audit_reseau.py" -v
"""
import http.client
import importlib
import json
import os
import re
import shutil
import socket
import sys
import tempfile
import time
import unittest
from pathlib import Path

from commun import RACINE, ServeurPrevo

sys.path.insert(0, str(RACINE))
import serveur  # noqa: E402  (serveur.py importé comme module : 409 et motif des photos, sans aléa d'horloge)

JPEG = bytes((0xFF, 0xD8, 0xFF, 0xE0, 0, 16)) + b"JFIF" + bytes(64) + bytes((0xFF, 0xD9))
PNG = bytes((0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A)) + b"IHDR" + bytes(32)
PDF = b"%PDF-1.4\n%essai\n"
DOCX = b"PK\x03\x04" + bytes(32)          # un .docx est une archive zip : son contenu n'est pas contrôlé
HTML = b"<!doctype html><title>Rapport</title><p>essai</p>"
MOTIF_NOM_IMPOSE = re.compile(r"^\d{8}-\d{6}-")
FIN_DE_LIGNE = b"\r\n"


class Reponse:
    def __init__(self, statut, entetes, octets):
        self.statut, self.entetes, self.octets = statut, entetes, octets

    def json(self):
        return json.loads(self.octets.decode("utf-8"))


def requete(port, methode, chemin, corps=None, entetes=None):
    """Une requête HTTP/1.1 sur 127.0.0.1:port ; X-Prevo posé sur PUT et POST. Rend Reponse (en-têtes en minuscules)."""
    envoyes = {"User-Agent": "tests-prevo/1.0"}
    if methode in ("PUT", "POST"):
        envoyes["X-Prevo"] = "1"
        envoyes["Content-Type"] = "application/octet-stream"
    envoyes.update(entetes or {})
    connexion = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    try:
        connexion.request(methode, chemin, body=corps, headers=envoyes)
        reponse = connexion.getresponse()
        return Reponse(reponse.status, {nom.lower(): valeur for nom, valeur in reponse.getheaders()}, reponse.read())
    finally:
        connexion.close()


def fichiers(dossier):
    """Noms des fichiers du dossier documents/ (sans fichier temporaire), triés ; [] s'il n'existe pas."""
    return sorted(p.name for p in Path(dossier).iterdir()) if Path(dossier).is_dir() else []


# ---------------------------------------------------------------------------
# F2 — sémaphore de 32 connexions
# ---------------------------------------------------------------------------

class TestSemaphore(unittest.TestCase):

    def test_la_33e_connexion_attend_puis_passe(self):
        self.assertEqual(serveur.CONNEXIONS_MAX, 32)
        with ServeurPrevo(source=None) as reel:
            debut = time.monotonic()
            tenues = []
            try:
                # 32 connexions dont la requête n'est jamais terminée (pas de ligne vide après les en-têtes) : chacune
                # occupe un fil de service, qui attend la suite jusqu'au délai du serveur (60 s).
                for _ in range(serveur.CONNEXIONS_MAX):
                    prise = socket.create_connection(("127.0.0.1", reel.port), timeout=30)
                    prise.sendall(b"GET /api/ping HTTP/1.1" + FIN_DE_LIGNE + b"Host: 127.0.0.1" + FIN_DE_LIGNE)
                    tenues.append(prise)
                time.sleep(0.5)             # le temps que les 32 fils de service aient pris le sémaphore
                # 33e : requête complète, qui n'obtient rien tant que les 32 tiennent.
                trente_troisieme = socket.create_connection(("127.0.0.1", reel.port), timeout=30)
                tenues.append(trente_troisieme)
                trente_troisieme.sendall(b"GET /api/ping HTTP/1.1" + FIN_DE_LIGNE + b"Host: 127.0.0.1" + FIN_DE_LIGNE
                                         + b"Connection: close" + FIN_DE_LIGNE + FIN_DE_LIGNE)
                trente_troisieme.settimeout(2)
                with self.assertRaises(socket.timeout, msg="la 33e connexion a été servie malgré les 32 tenues"):
                    trente_troisieme.recv(1)
                # Une des 32 se termine : la 33e passe (ni refusée ni perdue), en un temps borné.
                tenues.pop(0).close()
                trente_troisieme.settimeout(15)
                recu = b""
                while True:
                    morceau = trente_troisieme.recv(65536)
                    if not morceau:
                        break
                    recu += morceau
                self.assertTrue(recu.startswith(b"HTTP/1.1 200"), recu[:120])
                self.assertIn(b'"application"', recu)
            finally:
                for prise in tenues:
                    prise.close()
            self.assertLess(time.monotonic() - debut, 30)
            # Les 31 connexions restantes sont fermées : le serveur sert de nouveau tout le monde, sans attente.
            fin = time.monotonic() + 15
            while time.monotonic() < fin:
                try:
                    if requete(reel.port, "GET", "/api/ping").statut == 200:
                        break
                except OSError:
                    pass
                time.sleep(0.2)
            self.assertEqual(requete(reel.port, "GET", "/api/ping").statut, 200)
            self.assertNotIn("Traceback", reel.sortie_console())

    def test_le_semaphore_est_celui_du_processus_porte_et_application(self):
        # Une seule limite par serveur (§22.6) : le sémaphore est un objet du module, pas de l'écouteur.
        self.assertIsInstance(serveur.SEMAPHORE_CONNEXIONS, type(serveur.threading.BoundedSemaphore(1)))
        self.assertEqual(serveur.SEMAPHORE_CONNEXIONS._initial_value, serveur.CONNEXIONS_MAX)
        # Pris par requête (au premier octet), pas par connexion : une connexion keep-alive inactive ne tient
        # aucune place (défaut trouvé par la recette du lot 7, tests/test_recette_lot7.py TestConnexionsInactives).
        self.assertIn("SEMAPHORE_CONNEXIONS", serveur.GestionnaireRequetes.handle_one_request.__code__.co_names)
        self.assertNotIn("process_request_thread", vars(serveur.ServeurPrevo))


# ---------------------------------------------------------------------------
# F2 — constats déjà prouvés ailleurs : cités, pas dupliqués
# ---------------------------------------------------------------------------

class TestConstatsCites(unittest.TestCase):

    CITATIONS = (
        ("test_acces_sessions", "TestSessions", "test_corps_jamais_lu_sans_session"),
        ("test_sauvegardes_lot7", None, "test_deuxieme_sauvegarde_manuelle_de_la_minute_429"),
        ("test_audit_ia", None, "test_adresse_cle_et_delai_du_serveur"),
    )

    def test_corps_apres_session_429_et_delai_ia_sont_prouves_par_leurs_tests(self):
        """Corps lu après le contrôle de session (test_acces_sessions), sauvegarde manuelle 429 (test_sauvegardes_lot7),
        délai IA fixé par le serveur (test_audit_ia) : ces tests existent, c'est eux qui prouvent le constat."""
        for module, _, fonction in self.CITATIONS:
            with self.subTest(module=module, test=fonction):
                source = (RACINE / "tests" / (module + ".py")).read_text(encoding="utf-8")
                self.assertIn("def %s(self)" % fonction, source, "test cité introuvable")
        self.assertEqual(serveur.DELAI_IA_S, 120)


# ---------------------------------------------------------------------------
# F2 — quota du dossier documents
# ---------------------------------------------------------------------------

class TestQuotaDocuments(unittest.TestCase):

    def setUp(self):
        self.temporaire = Path(tempfile.mkdtemp(prefix="prevo-quota-"))
        self.addCleanup(shutil.rmtree, self.temporaire, True)
        configuration = self.temporaire / "prevo.config.json"
        configuration.write_text(json.dumps({"quota_documents_mo": 1}), encoding="utf-8")
        # Le dernier --config l'emporte sur celui que ServeurPrevo donne (portée « ce PC », aucun compte).
        self.serveur = ServeurPrevo(source=None, arguments=["--config", str(configuration)])
        self.serveur.demarrer()
        self.addCleanup(self.serveur.arreter)
        self.documents = self.serveur.dossier / "documents"

    def test_600_ko_passe_puis_600_ko_de_plus_413_et_rien_ecrit(self):
        gros = PDF + bytes(600 * 1024 - len(PDF))
        premier = requete(self.serveur.port, "PUT", "/api/documents/premier.pdf", gros)
        self.assertEqual(premier.statut, 201, premier.octets)
        nom_premier = premier.json()["nom"]
        self.assertEqual(fichiers(self.documents), [nom_premier])
        second = requete(self.serveur.port, "PUT", "/api/documents/second.pdf", gros)
        self.assertEqual(second.statut, 413, second.octets)
        message = second.json()["erreur"]
        self.assertTrue(message.startswith("Dossier des documents plein ("), message)
        self.assertIn("sur 1 Mo", message)
        self.assertIn("faites de la place ou augmentez quota_documents_mo", message)
        self.assertEqual(fichiers(self.documents), [nom_premier], "rien ne doit être écrit, pas même un temporaire")
        # Un petit document tient encore dans le quota.
        petit = requete(self.serveur.port, "PUT", "/api/documents/petit.pdf", PDF + bytes(100 * 1024))
        self.assertEqual(petit.statut, 201, petit.octets)
        self.assertEqual(len(fichiers(self.documents)), 2)
        # Faire de la place suffit : le dossier est mesuré à chaque envoi, sans redémarrer.
        (self.documents / nom_premier).unlink()
        troisieme = requete(self.serveur.port, "PUT", "/api/documents/troisieme.pdf", gros)
        self.assertEqual(troisieme.statut, 201, troisieme.octets)


# ---------------------------------------------------------------------------
# F4 — documents : types, Content-Disposition, nom imposé, signature des images
# ---------------------------------------------------------------------------

class TestDocuments(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.serveur = ServeurPrevo(source=None)
        cls.serveur.demarrer()
        cls.documents = cls.serveur.dossier / "documents"

    @classmethod
    def tearDownClass(cls):
        cls.serveur.arreter()

    def envoyer(self, nom, octets):
        return requete(self.serveur.port, "PUT", "/api/documents/" + nom, octets)

    def lire(self, nom):
        return requete(self.serveur.port, "GET", "/api/documents/" + nom)

    def test_xls_et_doc_refuses_415_a_l_ecriture_et_a_la_lecture(self):
        avant = fichiers(self.documents)
        for nom, octets in (("classeur.xls", b"\xd0\xcf\x11\xe0" + bytes(16)), ("lettre.doc", b"\xd0\xcf\x11\xe0" + bytes(16)),
                            ("sans-extension", b"x"), ("page.htm", b"<p>x</p>")):
            with self.subTest(nom=nom):
                reponse = self.envoyer(nom, octets)
                self.assertEqual(reponse.statut, 415, reponse.octets)
                self.assertEqual(reponse.json()["erreur"],
                                 "Type de document refusé. Types acceptés : %s." % ", ".join(sorted(serveur.TYPES_DOCUMENTS)))
                lecture = self.lire(nom)
                self.assertEqual(lecture.statut, 415, lecture.octets)
                lecture = self.lire("20261028-101500-" + nom)
                self.assertEqual(lecture.statut, 415, lecture.octets)
        self.assertEqual(fichiers(self.documents), avant)
        self.assertNotIn("doc", serveur.TYPES_DOCUMENTS)
        self.assertNotIn("xls", serveur.TYPES_DOCUMENTS)
        for present in ("docx", "xlsx", "odt", "ods"):
            self.assertIn(present, serveur.TYPES_DOCUMENTS)

    def test_content_disposition_hors_images_et_pdf(self):
        for nom, octets, type_mime, en_telechargement in (
                ("compte-rendu.docx", DOCX, serveur.TYPES_DOCUMENTS["docx"], True),
                ("notes.txt", b"notes", "text/plain; charset=utf-8", True),
                ("releve.csv", b"a;b\r\n1;2\r\n", "text/csv; charset=utf-8", True),
                ("rapport-mensuel-2026-09.html", HTML, "text/html; charset=utf-8", False),   # « Ouvrir » un rapport figé
                ("photo.jpg", JPEG, "image/jpeg", False),
                ("notice.pdf", PDF, "application/pdf", False)):
            with self.subTest(nom=nom):
                envoi = self.envoyer(nom, octets)
                self.assertEqual(envoi.statut, 201, envoi.octets)
                enregistre = envoi.json()["nom"]
                lecture = self.lire(enregistre)
                self.assertEqual(lecture.statut, 200)
                self.assertEqual(lecture.octets, octets)
                self.assertEqual(lecture.entetes["content-type"], type_mime)
                self.assertEqual(lecture.entetes["content-security-policy"], "sandbox")
                self.assertEqual(lecture.entetes["x-content-type-options"], "nosniff")
                if en_telechargement:
                    self.assertEqual(lecture.entetes.get("content-disposition"), 'attachment; filename="%s"' % enregistre)
                else:
                    self.assertNotIn("content-disposition", lecture.entetes)

    def test_nom_impose_par_le_serveur(self):
        envoi = self.envoyer("Compte-Rendu_VGP.PDF", PDF)
        self.assertEqual(envoi.statut, 201, envoi.octets)
        enregistre = envoi.json()["nom"]
        self.assertNotEqual(enregistre, "Compte-Rendu_VGP.PDF")
        self.assertRegex(enregistre, r"^\d{8}-\d{6}-Compte-Rendu_VGP\.pdf$")          # horodatage, extension en minuscules
        horodatage = time.strftime("%Y%m%d")
        self.assertTrue(enregistre.startswith(horodatage), (enregistre, horodatage))
        self.assertIn(enregistre, fichiers(self.documents))
        self.assertNotIn("Compte-Rendu_VGP.PDF", fichiers(self.documents))
        self.assertNotIn("Compte-Rendu_VGP.pdf", fichiers(self.documents))
        self.assertEqual((self.documents / enregistre).read_bytes(), PDF)
        self.assertEqual(self.lire(enregistre).statut, 200)
        self.assertEqual(self.lire("Compte-Rendu_VGP.PDF").statut, 404)
        self.assertEqual(self.lire("Compte-Rendu_VGP.pdf").statut, 404)
        # Les documents d'avant le lot 7 gardent leur nom : un fichier sans préfixe se lit tel quel.
        (self.documents / "ancienne-notice.pdf").write_bytes(PDF)
        self.assertEqual(self.lire("ancienne-notice.pdf").statut, 200)
        # Le nom demandé reste contrôlé : nom refusé 400, rien d'écrit.
        avant = fichiers(self.documents)
        for nom in ("-tiret.pdf", "a..b.pdf", "CON.pdf", "x" * 130 + ".pdf"):
            with self.subTest(nom=nom):
                self.assertEqual(self.envoyer(nom, PDF).statut, 400)
        self.assertEqual(fichiers(self.documents), avant)

    def test_meme_nom_demande_dans_la_meme_seconde_409_sans_ecrasement(self):
        """serveur.py importé, horloge simulée : deux demandes du même nom à la même seconde donnent le même nom imposé,
        la seconde est refusée 409 et l'original reste intact. À la seconde suivante, le nom diffère."""
        dossier = tempfile.mkdtemp(prefix="prevo-409-")
        self.addCleanup(shutil.rmtree, dossier, True)
        config = serveur.Configuration(dossier, [])
        serveur.creer_dossiers(config)
        instant = [1_790_000_000.0]
        config.horloge = lambda: instant[0]
        premier = serveur.enregistrer_document(config, "notice.pdf", b"v1")
        self.assertRegex(premier, r"^\d{8}-\d{6}-notice\.pdf$")
        with self.assertRaises(serveur.ErreurHttp) as refus:
            serveur.enregistrer_document(config, "notice.pdf", b"v2")
        self.assertEqual(refus.exception.statut, 409)
        self.assertEqual(Path(config.dossier_documents, premier).read_bytes(), b"v1")
        self.assertEqual(fichiers(config.dossier_documents), [premier])
        instant[0] += 1
        second = serveur.enregistrer_document(config, "notice.pdf", b"v2")
        self.assertNotEqual(second, premier)
        self.assertEqual(sorted(fichiers(config.dossier_documents)), sorted([premier, second]))

    def test_photo_de_demande_reconnue_avec_le_prefixe_du_serveur(self):
        """Le demandeur envoie « photo-… » (nom demandé, sans préfixe) et relit le nom enregistré (avec préfixe) : les deux
        formes passent MOTIF_PHOTO_DE_DEMANDE ; un autre document, préfixé ou non, non."""
        demande = "photo-20261026-101530-WXYZ.jpg"
        self.assertIsNotNone(serveur.MOTIF_PHOTO_DE_DEMANDE.fullmatch(demande))
        self.assertIsNotNone(serveur.MOTIF_PHOTO_DE_DEMANDE.fullmatch("20261026-101531-" + demande))
        self.assertIsNone(serveur.MOTIF_PHOTO_DE_DEMANDE.fullmatch("20261026-101531-rapport.pdf"))
        self.assertIsNone(serveur.MOTIF_PHOTO_DE_DEMANDE.fullmatch("2026-101531-" + demande))
        self.assertIsNone(serveur.MOTIF_PHOTO_DE_DEMANDE.fullmatch("x-" + demande))

    def test_faux_jpeg_et_faux_png_refuses_400_rien_ecrit(self):
        avant = fichiers(self.documents)
        for nom, octets, attendu in (("faux.jpg", b"%PDF-1.4 pas une image", "jpg"), ("faux.jpeg", HTML, "jpeg"),
                                     ("faux.png", b"png", "png"), ("faux.gif", JPEG, "gif"),
                                     ("faux.webp", b"RIFF\x00\x00\x00\x00WAVE", "webp"), ("vide.jpg", b"", "jpg")):
            with self.subTest(nom=nom):
                reponse = self.envoyer(nom, octets)
                self.assertEqual(reponse.statut, 400, reponse.octets)
                self.assertEqual(reponse.json(), {"erreur": "Le contenu n'est pas une image %s." % attendu})
        self.assertEqual(fichiers(self.documents), avant)
        # Les vraies images passent ; un PDF ou un texte n'est pas contrôlé.
        for nom, octets in (("vrai.jpg", JPEG), ("vrai.jpeg", JPEG), ("vrai.png", PNG), ("vrai.gif", b"GIF89a" + bytes(8)),
                            ("vrai.webp", b"RIFF\x00\x00\x00\x00WEBPVP8 "), ("texte.pdf", b"pas un pdf"), ("note.txt", b"")):
            with self.subTest(nom=nom):
                reponse = self.envoyer(nom, octets)
                self.assertEqual(reponse.statut, 201, reponse.octets)
                self.assertEqual((self.documents / reponse.json()["nom"]).read_bytes(), octets)
        self.assertIn("verifier_signature_image", serveur.GestionnaireRequetes.api_document_ecrire.__code__.co_names)


# ---------------------------------------------------------------------------
# I2 — repr du chemin sur la console
# ---------------------------------------------------------------------------

class TestReprDuChemin(unittest.TestCase):

    def envoyer_brut(self, port, ligne_de_requete):
        """Envoie une requête PUT brute (chemin tel quel, caractères de contrôle compris) et rend la réponse."""
        with socket.create_connection(("127.0.0.1", port), timeout=10) as prise:
            prise.sendall(ligne_de_requete + FIN_DE_LIGNE + b"Host: 127.0.0.1:%d" % port + FIN_DE_LIGNE + b"X-Prevo: 1"
                          + FIN_DE_LIGNE + b"Content-Length: 3" + FIN_DE_LIGNE + b"Connection: close" + FIN_DE_LIGNE
                          + FIN_DE_LIGNE + b"abc")
            recu = b""
            while True:
                morceau = prise.recv(65536)
                if not morceau:
                    break
                recu += morceau
        return recu

    def test_caractere_de_controle_et_retour_a_la_ligne_ecrits_en_repr(self):
        with ServeurPrevo(source=None) as reel:
            cas = (b"PUT /api/documents/x\x1b[2Ky.jpg HTTP/1.1",         # ESC [2K : efface la ligne d'un terminal
                   b"PUT /api/documents/x\x01y.jpg HTTP/1.1",
                   b"PUT /api/documents/x%0Ay.jpg HTTP/1.1",
                   b"PUT /api/documents/x%0D%0A14:00:00%20%2010.0.0.9%20%20PUT%20/api/csv/demandes%20%20200.jpg HTTP/1.1")
            for ligne in cas:
                with self.subTest(ligne=ligne):
                    recu = self.envoyer_brut(reel.port, ligne)
                    self.assertTrue(recu.startswith(b"HTTP/1.1 400"), recu[:80])
            self.assertEqual(fichiers(reel.dossier / "documents"), [])
            console = reel.sortie_console()
            lignes_put = [ligne for ligne in console.splitlines() if "PUT" in ligne]
            self.assertEqual(len(lignes_put), len(cas), console)
            for ligne in lignes_put:
                self.assertRegex(ligne, r"^\d{2}:\d{2}:\d{2}  127\.0\.0\.1  PUT '/api/documents/.*'  400$", ligne)
            self.assertIn("'/api/documents/x\\x1b[2Ky.jpg'", console)
            self.assertIn("'/api/documents/x\\x01y.jpg'", console)
            self.assertIn("'/api/documents/x%0Ay.jpg'", console)
            self.assertNotIn("\x1b", console)
            self.assertNotIn("\x01", console)
            # Aucune ligne injectée : rien qui ressemble à une écriture venue d'ailleurs.
            self.assertFalse([ligne for ligne in console.splitlines() if ligne.startswith("y.jpg")], console)
            self.assertNotIn("\n14:00:00  10.0.0.9", console)


if __name__ == "__main__":
    unittest.main()
