"""Lot 4 (multilingue) — identifiants et noms turcs dans le code des comptes (T301 ; D164 ; CS155 ; conception
validée par Nicolas le 07/11 : .chantier/i18n/L4/CONCEPTION-T301.md).

Règle de Nicolas : une même personne n'a jamais deux identifiants, deux personnes jamais le même ; un identifiant tapé
qui désigne plusieurs comptes est refusé, l'identifiant exact est demandé, Prévo ne choisit jamais un compte à la place
de la personne, et le compteur d'essais avant blocage s'applique quand même.

Ce qui est vérifié :
    pliage        un seul pliage (serveur.plier_nom) : İ, I, ı, i → i ; casse (casefold, ß → ss) ; accents retirés ;
                  identifiants de Yılmaz, IŞIK, Işık, İsmail, ISMAIL, Çağrı, Öztürk, Ayşe, Güneş ; noms français
                  inchangés (Élodie Le Gall → elodie.le-gall) ; même personne (forme_de_nom) quelle que soit la casse ;
    création      un deuxième compte au même prénom et au même nom (même désactivé, même écrit autrement : IŞIK et
                  Işık) est refusé avec l'identifiant existant (comptes.meme_personne), puis accepté avec
                  autre_personne (« .2 ») ; homonymes français de même ;
    désignation   l'identifiant exact tranche toujours ; sinon le texte ramené à des lettres simples, ou la règle
                  d'avant T301 (« Işık » → « is-k ») ; plusieurs comptes : aucun (trouver_compte), et la réinitialisation
                  dit lesquels (comptes.plusieurs) ;
    connexion     (serveur dans ce processus) casse et lettres turques : ÇAĞRI.ÖZTÜRK, Cagri.Ozturk, İSMAİL.GÜNEŞ…
                  ouvrent le même compte ; ancien compte « mehmet.y-lmaz » toujours ouvert (tel quel, ou tapé
                  « Mehmet.Yılmaz ») ; « Ayşe.Işık » désigne deux anciens comptes : 401 sessions.identifiant_ambigu,
                  aucun mot de passe vérifié, même avec le bon, puis chaque identifiant exact ouvre son compte ;
    compteur      dix essais ambigus : le dixième bloque (429) ; dix échecs tapés avec des casses différentes comptent
                  pour un seul compte ;
    route         POST /api/acces/comptes : 400 comptes.meme_personne (identifiant existant dans les valeurs),
                  autre_personne vrai → 200 « ayse.isik.2 », autre_personne qui n'est pas un booléen → 400.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_acces_noms_turcs.py" -v
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import test_acces_sessions as sessions

serveur = sessions.serveur

MOT_DE_PASSE_A = "ayse isik en majuscules"
MOT_DE_PASSE_B = "ayse isik en minuscules"
MOT_DE_PASSE_M = "mehmet ancien compte 2026"
MOT_DE_PASSE_C = "cagri ozturk mot de passe"
MOT_DE_PASSE_I = "ismail gunes mot de passe"
FAUX = "pas le bon mot de passe"
MESSAGE_AMBIGU = "Plusieurs comptes correspondent à cet identifiant : tapez-le exactement, tel qu'il vous a été donné."
COMPTES_JSON = b""


def setUpModule():
    """Comptes créés une fois (scrypt coûte), recopiés dans chaque dossier : le responsable des tests de sessions, deux
    anciens comptes nés de « Ayşe IŞIK » et « Ayşe Işık » avant T301 (ayse.isik, ayse.is-k), un ancien
    « mehmet.y-lmaz », et deux comptes créés par la règle de T301 (cagri.ozturk, ismail.gunes)."""
    global COMPTES_JSON
    dossier = Path(tempfile.mkdtemp(prefix="prevo-noms-turcs-modele-"))
    try:
        config = serveur.Configuration(str(dossier / "donnees"), [])
        config.horloge = lambda: sessions.CREATION_DES_COMPTES        # avant les sessions des tests (DEPART)
        serveur.creer_dossiers(config)
        serveur.creer_compte(config, "Nicolas", "Briand", "responsable", sessions.MOT_DE_PASSE_RESPONSABLE)
        # Identifiants d'avant T301, posés tels quels (autre_personne : la règle de T301 refuserait le second).
        serveur.creer_compte(config, "Ayşe", "IŞIK", "demandeur", MOT_DE_PASSE_A, identifiant="ayse.isik")
        serveur.creer_compte(config, "Ayşe", "Işık", "demandeur", MOT_DE_PASSE_B, identifiant="ayse.is-k",
                             autre_personne=True)
        serveur.creer_compte(config, "Mehmet", "Yılmaz", "demandeur", MOT_DE_PASSE_M, identifiant="mehmet.y-lmaz")
        serveur.creer_compte(config, "Çağrı", "Öztürk", "demandeur", MOT_DE_PASSE_C)
        serveur.creer_compte(config, "İsmail", "Güneş", "demandeur", MOT_DE_PASSE_I)
        COMPTES_JSON = (dossier / "donnees" / "acces" / "comptes.json").read_bytes()
        sessions.COMPTES_JSON = COMPTES_JSON          # recopié par CasDansLeProcessus dans chaque dossier de données
    finally:
        shutil.rmtree(dossier, ignore_errors=True)


def code_de(erreur):
    message = serveur.traduisible_de(erreur)
    return getattr(message, "code", None), dict(getattr(message, "valeurs", None) or {})


class TestPliage(unittest.TestCase):

    def test_identifiants_des_noms_turcs_et_francais(self):
        attendus = [
            (("Yılmaz", ""), "yilmaz"), (("YILMAZ", ""), "yilmaz"), (("YİLMAZ", ""), "yilmaz"),
            (("Ayşe", "Işık"), "ayse.isik"), (("Ayşe", "IŞIK"), "ayse.isik"), (("AYŞE", "ışık"), "ayse.isik"),
            (("İsmail", "Güneş"), "ismail.gunes"), (("ISMAIL", "GÜNEŞ"), "ismail.gunes"),
            (("Çağrı", "Öztürk"), "cagri.ozturk"), (("ÇAĞRI", "ÖZTÜRK"), "cagri.ozturk"),
            (("Élodie", "Le Gall"), "elodie.le-gall"), (("Jean-François", "Lefèvre"), "jean-francois.lefevre"),
            (("Zoé", "Durand"), "zoe.durand"), (("Jürgen", "Straße"), "jurgen.strasse"),
        ]
        for (prenom, nom), identifiant in attendus:
            with self.subTest(prenom=prenom, nom=nom):
                self.assertEqual(serveur.identifiant_depuis(prenom, nom, set()), identifiant)
        self.assertEqual(serveur.identifiant_depuis("Ayşe", "Işık", {"ayse.isik"}), "ayse.isik.2")

    def test_meme_personne_quelle_que_soit_l_ecriture(self):
        for ecriture in ("IŞIK", "Işık", "ışık", "isik", "  Isik  "):
            with self.subTest(ecriture=ecriture):
                self.assertEqual(serveur.forme_de_nom(ecriture), "isik")
        self.assertEqual(serveur.forme_de_nom("Le  Gall"), "le gall")
        comptes = [{"identifiant": "ayse.isik", "prenom": "Ayşe", "nom": "IŞIK"}]
        self.assertIs(serveur.meme_personne(comptes, "AYŞE", "Işık"), comptes[0])
        self.assertIsNone(serveur.meme_personne(comptes, "Ayşe", "Işıklı"))

    def test_designation_exacte_puis_pliee_puis_ancienne_regle(self):
        comptes = [{"identifiant": i} for i in ("ayse.isik", "ayse.is-k", "mehmet.y-lmaz", "cagri.ozturk")]
        attendus = {
            "ayse.isik": ["ayse.isik"], "ayse.is-k": ["ayse.is-k"], " ayse.isik ": ["ayse.isik"],
            "AYŞE.IŞIK": ["ayse.isik"], "Ayşe.Işık": ["ayse.isik", "ayse.is-k"],
            "Mehmet.Yılmaz": ["mehmet.y-lmaz"], "mehmet.y-lmaz": ["mehmet.y-lmaz"], "MEHMET.YILMAZ": [],
            "ÇAĞRI.ÖZTÜRK": ["cagri.ozturk"], "Cagri.Ozturk": ["cagri.ozturk"], "": [], "inconnu": [],
        }
        for tape, designes in attendus.items():
            with self.subTest(tape=tape):
                self.assertEqual([c["identifiant"] for c in serveur.comptes_designes(comptes, tape)], designes)
        self.assertIsNone(serveur.trouver_compte(comptes, "Ayşe.Işık"))          # plusieurs : jamais un choix
        self.assertEqual(serveur.trouver_compte(comptes, "Ayşe.Işık".replace("ı", "i").upper())["identifiant"],
                         "ayse.isik")


class TestCreation(unittest.TestCase):

    def setUp(self):
        dossier = Path(tempfile.mkdtemp(prefix="prevo-noms-turcs-"))
        self.addCleanup(shutil.rmtree, dossier, True)
        self.config = serveur.Configuration(str(dossier / "donnees"), [])
        serveur.creer_dossiers(self.config)
        (dossier / "donnees" / "acces").mkdir(parents=True, exist_ok=True)
        (dossier / "donnees" / "acces" / "comptes.json").write_bytes(COMPTES_JSON)

    def creer(self, prenom, nom, **options):
        return serveur.creer_compte(self.config, prenom, nom, "demandeur", "un mot de passe assez long", **options)

    def test_meme_personne_refusee_puis_acceptee_avec_autre_personne(self):
        for prenom, nom, existant in (("AYŞE", "ışık", "ayse.isik"), ("Mehmet", "YILMAZ", "mehmet.y-lmaz"),
                                      ("cagri", "OZTURK", "cagri.ozturk")):
            with self.subTest(nom=nom):
                with self.assertRaises(serveur.ErreurCompte) as refus:
                    self.creer(prenom, nom)
                self.assertEqual(code_de(refus.exception), ("comptes.meme_personne",
                                                            {"personne": prenom + " " + nom, "identifiant": existant}))
        avant = len(serveur.lire_comptes(self.config))
        self.assertEqual(self.creer("AYŞE", "ışık", autre_personne=True)["identifiant"], "ayse.isik.2")
        self.assertEqual(self.creer("Çağrı", "Öztürk", autre_personne=True)["identifiant"], "cagri.ozturk.2")
        self.assertEqual(len(serveur.lire_comptes(self.config)), avant + 2)
        # Homonymes français : même règle.
        self.assertEqual(self.creer("Jean", "Martin")["identifiant"], "jean.martin")
        with self.assertRaises(serveur.ErreurCompte):
            self.creer("JEAN", "MARTIN")
        self.assertEqual(self.creer("Jean", "Martin", autre_personne=True)["identifiant"], "jean.martin.2")

    def test_compte_desactive_compte_aussi(self):
        serveur.modifier_compte(self.config, "ismail.gunes", actif=False)
        with self.assertRaises(serveur.ErreurCompte) as refus:
            self.creer("ISMAIL", "GUNES")
        self.assertEqual(code_de(refus.exception)[1]["identifiant"], "ismail.gunes")

    def test_reinitialisation_d_un_identifiant_ambigu_donne_la_liste(self):
        with self.assertRaises(serveur.ErreurCompte) as refus:
            serveur.reinitialiser_compte(self.config, "Ayşe.Işık")
        self.assertEqual(code_de(refus.exception), ("comptes.plusieurs",
                                                    {"identifiant": "Ayşe.Işık", "identifiants": "ayse.isik, ayse.is-k"}))
        self.assertEqual(len(serveur.reinitialiser_compte(self.config, "İSMAİL.GÜNEŞ")), 16)
        compte = serveur.trouver_compte(serveur.lire_comptes(self.config), "ismail.gunes")
        self.assertTrue(compte["a_changer"])


class CasConnexion(sessions.CasDansLeProcessus):

    def refus(self, identifiant, mot_de_passe):
        reponse = self.client.connecter(identifiant, mot_de_passe)
        return reponse.statut, reponse.json().get("erreur_code")


class TestConnexion(CasConnexion):

    def test_casse_et_lettres_turques_ouvrent_le_meme_compte(self):
        for tape, mot_de_passe, identifiant in (
                ("cagri.ozturk", MOT_DE_PASSE_C, "cagri.ozturk"), ("ÇAĞRI.ÖZTÜRK", MOT_DE_PASSE_C, "cagri.ozturk"),
                ("Cagri.Ozturk", MOT_DE_PASSE_C, "cagri.ozturk"), (" çağrı.öztürk ", MOT_DE_PASSE_C, "cagri.ozturk"),
                ("İSMAİL.GÜNEŞ", MOT_DE_PASSE_I, "ismail.gunes"), ("ISMAIL.GUNES", MOT_DE_PASSE_I, "ismail.gunes"),
                ("ismail.gunes", MOT_DE_PASSE_I, "ismail.gunes"),
                ("mehmet.y-lmaz", MOT_DE_PASSE_M, "mehmet.y-lmaz"), ("Mehmet.Yılmaz", MOT_DE_PASSE_M, "mehmet.y-lmaz")):
            with self.subTest(tape=tape):
                cookie = self.connecter(tape, mot_de_passe)
                self.assertEqual(self.client.session(cookie)["identifiant"], identifiant)
        self.assertEqual(self.refus("MEHMET.YILMAZ", MOT_DE_PASSE_M), (401, "sessions.connexion_refusee"))

    def test_identifiant_qui_designe_plusieurs_comptes_refuse_sans_choisir(self):
        with mock.patch.object(serveur, "mot_de_passe_juste", wraps=serveur.mot_de_passe_juste) as verification:
            for mot_de_passe in (MOT_DE_PASSE_A, MOT_DE_PASSE_B, FAUX):
                reponse = self.client.connecter("Ayşe.Işık", mot_de_passe)
                self.assertEqual((reponse.statut, reponse.json()), (401, {"erreur": MESSAGE_AMBIGU,
                                                                          "erreur_code": "sessions.identifiant_ambigu"}))
                self.assertNotIn("set-cookie", reponse.entetes)
        self.assertEqual(verification.call_count, 0)                     # aucun mot de passe vérifié
        self.assertEqual(self.sessions(), {})
        journal = sessions.lignes_du_journal(self.donnees)
        self.assertEqual([(l["qui"], l["resultat"]) for l in journal], [(serveur.QUI_INCONNU, "echec")] * 3)
        # L'identifiant exact ouvre chacun des deux comptes.
        self.assertEqual(self.client.session(self.connecter("ayse.is-k", MOT_DE_PASSE_B))["identifiant"], "ayse.is-k")
        self.assertEqual(self.client.session(self.connecter("ayse.isik", MOT_DE_PASSE_A))["identifiant"], "ayse.isik")
        self.verifier_aucun_secret()

    def test_le_compteur_s_applique_aux_essais_ambigus(self):
        for numero in range(1, 10):
            self.assertEqual(self.refus("Ayşe.Işık", MOT_DE_PASSE_B), (401, "sessions.identifiant_ambigu"), numero)
        self.assertEqual(self.serveur.attentes, [1, 2, 4, 8, 8])               # du 5e au 9e échec, comme ailleurs
        dixieme = self.client.connecter("Ayşe.Işık", MOT_DE_PASSE_B)
        self.assertEqual((dixieme.statut, dixieme.entetes["retry-after"]), (429, "900"))
        self.assertEqual(self.client.connecter("Ayşe.Işık", MOT_DE_PASSE_B).statut, 429)
        # Les essais ont compté pour « ayse.isik » (le texte ramené) : ce compte attend aussi ; « ayse.is-k » non.
        self.assertEqual(self.client.connecter("ayse.isik", MOT_DE_PASSE_A).statut, 429)
        self.connecter("ayse.is-k", MOT_DE_PASSE_B)

    def test_les_essais_comptent_par_compte_quelle_que_soit_la_casse(self):
        ecritures = ("ÇAĞRI.ÖZTÜRK", "cagri.ozturk", "Çağrı.Öztürk")
        for numero in range(9):
            self.assertEqual(self.refus(ecritures[numero % 3], FAUX), (401, "sessions.connexion_refusee"), numero)
        self.assertEqual(self.client.connecter("CAGRI.OZTURK", FAUX).statut, 429)
        self.assertEqual(self.client.connecter("cagri.ozturk", MOT_DE_PASSE_C).statut, 429)
        qui = {l["qui"] for l in sessions.lignes_du_journal(self.donnees)}
        self.assertEqual(qui, {"cagri.ozturk"})


class TestRouteDeCreation(CasConnexion):

    def test_meme_personne_400_puis_autre_personne(self):
        cookie = self.connecter("nicolas.briand", sessions.MOT_DE_PASSE_RESPONSABLE)

        def creer(corps):
            return self.client.requete("POST", "/api/acces/comptes", corps, cookie=cookie)

        refus = creer({"prenom": "Ayşe", "nom": "ışık", "role": "demandeur"})
        self.assertEqual(refus.statut, 400, refus.octets)
        self.assertEqual(refus.json()["erreur_code"], "comptes.meme_personne")
        self.assertEqual(refus.json()["erreur_valeurs"], {"personne": "Ayşe ışık", "identifiant": "ayse.isik"})
        self.assertIn("C'est une autre personne", refus.json()["erreur"])
        mauvais = creer({"prenom": "Ayşe", "nom": "ışık", "role": "demandeur", "autre_personne": "oui"})
        self.assertEqual((mauvais.statut, mauvais.json()["erreur_code"]), (400, "comptes.autre_personne_booleen"))
        avant = json.loads((self.donnees / "acces" / "comptes.json").read_text(encoding="utf-8"))["comptes"]
        cree = creer({"prenom": "Ayşe", "nom": "ışık", "role": "demandeur", "autre_personne": True})
        self.assertEqual(cree.statut, 200, cree.octets)
        self.assertEqual(cree.json()["compte"]["identifiant"], "ayse.isik.2")
        apres = json.loads((self.donnees / "acces" / "comptes.json").read_text(encoding="utf-8"))["comptes"]
        self.assertEqual(len(apres), len(avant) + 1)
        self.assertNotIn("autre_personne", apres[-1])                          # rien de plus dans le fichier


if __name__ == "__main__":
    unittest.main()
