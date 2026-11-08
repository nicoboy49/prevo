"""Chantier multilingue, Lot 4 — langue de chaque compte (T298 ; D148 ; ARCHITECTURE.md §22.3, §24.11).

Ce qui est vérifié :
    route        (serveur dans ce processus) POST /api/mot-de-passe {"langue": code} seul : la langue du compte de la
                 session change, et elle seule (ni mot de passe, ni sel, ni empreinte, ni modifie_le ; aucune session
                 fermée ; la session rend la langue) ; "" la retire (langue de l'installation) ; même valeur : rien
                 d'écrit ; valeur hors des langues déclarées (« de », « EN », « en  », balisage, null, nombre, liste,
                 objet) : 400 comptes.langue_inconnue, rien d'écrit ; « langue » mêlée à « actuel »/« nouveau » ou à
                 tout autre champ : 400 sessions.langue_seule, rien de changé, le mot de passe garde ses règles (actuel
                 toujours exigé : 400 sans lui, 403 faux, aucun essai compté par la demande mêlée) ; mot de passe
                 provisoire et appareil enrôlé : 403 ; /api/session porte la langue (hors liste dans comptes.json : '') ;
    responsable  création avec langue, modification (Équipe › Accès : /api/acces/comptes…), valeur hors liste 400 et
                 rien d'écrit ; un technicien est refusé (403) sur le compte d'un autre comme à la création ; aucune
                 empreinte, aucun sel ne part ;
    journal      « langue:installation>en », « langue:en>fr », « langue:fr>installation » (qui = le compte), après
                 « modification » pour le responsable ;
    bêta 2       (serveur réel) base f3-v2.0.0 de la 2.0.0 bêta 2 (acces/comptes.json sans champ langue), plus un
                 technicien et un demandeur écrits au format de la bêta 2 : ouverte sans perte (CSV et comptes.json à
                 l'octet près), connexion de chaque rôle, langue absente = langue de l'installation ; après un
                 changement de langue, tous les autres champs de tous les comptes identiques ;
    écrans       (Chromium, serveur réel, installation française) : connexion → la langue du compte (anglais), un
                 rechargement ; déconnexion → la langue du poste ; « Ce poste » : « pour mon compte » enregistrée sur
                 le serveur et suivie dans un autre contexte de navigateur, « pour ce poste » comme avant (et retire la
                 langue du compte) ; clé « prevo.langue.compte » abîmée ignorée, clé laissée par un autre compte
                 effacée (un rechargement) ; clé refusée par le navigateur : un seul rechargement, pas de boucle ;
                 Équipe › Accès : liste « Langue » (langue de l'installation puis chaque langue dans sa langue),
                 création et modification, ligne « Langue changée (installation → en) » au journal.

Lancer depuis la racine du projet (à travers le verrou du navigateur) :
    py -X utf8 -m unittest discover -s tests -p "test_langue_compte.py" -v
"""
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from commun import COMPTES_DE_TEST, CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil
from jeux_formats import copier_jeu
from test_acces_sessions import CREATION_DES_COMPTES, Client, ServeurDansLeProcessus, lignes_du_journal, serveur
from test_langue_installation import poser_langue, texte_du_dictionnaire

MOT_DE_PASSE_RESPONSABLE = "phrase du responsable 2026"
MOT_DE_PASSE_TECHNICIEN = "cle a molette et graisse"
MOT_DE_PASSE_DEMANDEUR = "une demande de lea 2026"
MOT_DE_PASSE_PROVISOIRE = "provisoire-a-changer-7"
NOUVEAU_MOT_DE_PASSE = "nouvelle phrase choisie ici"
COMPTES_JSON = b""
VALEURS_REFUSEES = ("de", "EN", "en ", " en", "fr-FR", "xx\"><img src=x onerror=alert(1)>", None, 3, True,
                    ["en"], {"code": "en"})
CHAMPS_PUBLICS_DE_SESSION = {"identifiant", "role", "prenom", "nom", "technicien_id", "a_changer", "appareil", "langue"}
# Base de la 2.0.0 bêta 2 (tests/fixtures/formats/LISEZMOI.md) : compte responsable fictif claire.essai.
JEU_BETA2 = "f3-v2.0.0"
MOT_DE_PASSE_BETA2 = "essai-formats-prevo"
CHAMPS_BETA2 = ["identifiant", "prenom", "nom", "role", "technicien_id", "actif", "algo", "sel", "empreinte",
                "a_changer", "cree_le", "modifie_le", "mot_de_passe_le"]


def setUpModule():
    """Quatre comptes créés une fois (scrypt coûte) : nicolas.briand (responsable), julien.moreau (technicien,
    TEC-0001), lea.martin (demandeur), paul.durand (demandeur, mot de passe provisoire à changer)."""
    global COMPTES_JSON
    dossier = Path(tempfile.mkdtemp(prefix="prevo-langue-compte-"))
    try:
        config = serveur.Configuration(str(dossier / "donnees"), [])
        config.horloge = lambda: CREATION_DES_COMPTES
        serveur.creer_dossiers(config)
        serveur.creer_compte(config, "Nicolas", "Briand", "responsable", MOT_DE_PASSE_RESPONSABLE)
        serveur.creer_compte(config, "Julien", "Moreau", "technicien", MOT_DE_PASSE_TECHNICIEN, technicien_id="TEC-0001")
        serveur.creer_compte(config, "Léa", "Martin", "demandeur", MOT_DE_PASSE_DEMANDEUR)
        serveur.creer_compte(config, "Paul", "Durand", "demandeur", MOT_DE_PASSE_PROVISOIRE, a_changer=True)
        COMPTES_JSON = (dossier / "donnees" / "acces" / "comptes.json").read_bytes()
    finally:
        shutil.rmtree(dossier, ignore_errors=True)


def comptes_par_identifiant(octets):
    return {compte["identifiant"]: compte for compte in json.loads(octets.decode("utf-8"))["comptes"]}


def sans_langue(compte):
    return {cle: valeur for cle, valeur in compte.items() if cle != "langue"}


# ---------------------------------------------------------------------------
# 1. La route (serveur dans ce processus)
# ---------------------------------------------------------------------------

class CasRoute(unittest.TestCase):

    def setUp(self):
        dossier = Path(tempfile.mkdtemp(prefix="prevo-langue-route-"))
        self.addCleanup(shutil.rmtree, dossier, True)
        self.donnees = dossier / "donnees"
        (self.donnees / "acces").mkdir(parents=True)
        (self.donnees / "acces" / "comptes.json").write_bytes(COMPTES_JSON)
        espion = mock.patch.object(serveur, "afficher")
        espion.start()
        self.addCleanup(espion.stop)
        lance = ServeurDansLeProcessus(self.donnees)
        self.addCleanup(lance.arreter)
        self.client = lance.client

    def connecter(self, identifiant, mot_de_passe):
        reponse = self.client.connecter(identifiant, mot_de_passe)
        self.assertEqual(reponse.statut, 200, reponse.octets)
        return reponse.cookie

    def langue(self, cookie, corps):
        return self.client.requete("POST", "/api/mot-de-passe", corps, cookie=cookie)

    def octets_comptes(self):
        return (self.donnees / "acces" / "comptes.json").read_bytes()

    def comptes(self):
        return comptes_par_identifiant(self.octets_comptes())

    def resultats(self, identifiant):
        return [ligne["resultat"] for ligne in lignes_du_journal(self.donnees) if ligne["qui"] == identifiant]

    def sessions(self):
        return json.loads((self.donnees / "acces" / "sessions.json").read_text(encoding="utf-8"))


class TestLangueParLaPersonne(CasRoute):

    def test_langue_seule_changee_sans_rien_toucher_d_autre(self):
        cookie = self.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN)
        autre = self.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN)        # une autre session du même compte
        avant = self.comptes()
        sessions = self.sessions()
        self.assertEqual(self.client.session(cookie)["langue"], "")                # absente : langue de l'installation
        reponse = self.langue(cookie, {"langue": "en"})
        self.assertEqual(reponse.statut, 200, reponse.octets)
        self.assertNotIn("set-cookie", reponse.entetes)                             # aucune session neuve
        self.assertEqual(reponse.json()["session"]["langue"], "en")
        self.assertEqual(set(reponse.json()["session"]), CHAMPS_PUBLICS_DE_SESSION)
        apres = self.comptes()
        self.assertEqual(apres["julien.moreau"]["langue"], "en")
        self.assertEqual(sans_langue(apres["julien.moreau"]), avant["julien.moreau"])  # sel, empreinte, dates : identiques
        self.assertEqual({k: v for k, v in apres.items() if k != "julien.moreau"},
                         {k: v for k, v in avant.items() if k != "julien.moreau"})
        self.assertEqual(self.sessions().keys(), sessions.keys())                  # aucune session fermée
        self.assertEqual(self.client.session(autre)["langue"], "en")                # l'autre session la voit
        self.assertEqual(self.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN) is not None, True)   # même mot de passe
        # Autre langue, puis "" : le champ est retiré, le compte redevient celui d'avant.
        self.assertEqual(self.langue(cookie, {"langue": "fr"}).json()["session"]["langue"], "fr")
        self.assertEqual(self.langue(cookie, {"langue": ""}).json()["session"]["langue"], "")
        self.assertEqual(self.comptes()["julien.moreau"], avant["julien.moreau"])
        # Même valeur : rien d'écrit, aucune ligne au journal.
        octets, lignes = self.octets_comptes(), len(lignes_du_journal(self.donnees))
        self.assertEqual(self.langue(cookie, {"langue": ""}).statut, 200)
        self.assertEqual((self.octets_comptes(), len(lignes_du_journal(self.donnees))), (octets, lignes))
        self.assertEqual([r for r in self.resultats("julien.moreau") if r.startswith("langue")],
                         ["langue:installation>en", "langue:en>fr", "langue:fr>installation"])

    def test_valeur_hors_liste_refusee_rien_ecrit(self):
        cookie = self.connecter("lea.martin", MOT_DE_PASSE_DEMANDEUR)
        octets, lignes = self.octets_comptes(), len(lignes_du_journal(self.donnees))
        for valeur in VALEURS_REFUSEES:
            reponse = self.langue(cookie, {"langue": valeur})
            self.assertEqual((reponse.statut, reponse.json()["erreur_code"]), (400, "comptes.langue_inconnue"), valeur)
        self.assertEqual((self.octets_comptes(), len(lignes_du_journal(self.donnees))), (octets, lignes))
        self.assertEqual(self.client.session(cookie)["langue"], "")

    def test_langue_meme_a_un_mot_de_passe_refusee_et_mot_de_passe_toujours_exige(self):
        cookie = self.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN)
        octets, lignes = self.octets_comptes(), len(lignes_du_journal(self.donnees))
        for corps in ({"langue": "en", "actuel": MOT_DE_PASSE_TECHNICIEN, "nouveau": NOUVEAU_MOT_DE_PASSE},
                      {"langue": "en", "nouveau": NOUVEAU_MOT_DE_PASSE},
                      {"langue": "en", "actuel": "pas le bon mot de passe", "nouveau": NOUVEAU_MOT_DE_PASSE},
                      {"langue": "en", "identifiant": "nicolas.briand"}):
            reponse = self.langue(cookie, corps)
            self.assertEqual((reponse.statut, reponse.json()["erreur_code"]), (400, "sessions.langue_seule"), corps)
        self.assertEqual((self.octets_comptes(), len(lignes_du_journal(self.donnees))), (octets, lignes))  # aucun essai compté
        self.assertEqual(self.client.session(cookie)["langue"], "")                 # session gardée
        # Le mot de passe garde exactement ses règles : actuel exigé (400 sans lui, 403 faux), puis changé.
        self.assertEqual(self.langue(cookie, {"nouveau": NOUVEAU_MOT_DE_PASSE}).statut, 400)
        faux = self.langue(cookie, {"actuel": "pas le bon mot de passe", "nouveau": NOUVEAU_MOT_DE_PASSE})
        self.assertEqual(faux.statut, 403)
        change = self.langue(cookie, {"actuel": MOT_DE_PASSE_TECHNICIEN, "nouveau": NOUVEAU_MOT_DE_PASSE})
        self.assertEqual(change.statut, 200, change.octets)
        self.assertIsNotNone(change.cookie)                                          # session neuve
        self.assertIsNone(self.client.session(cookie))                              # l'ancienne fermée
        self.assertEqual(self.resultats("julien.moreau")[-2:], ["echec", "modification"])

    def test_mot_de_passe_provisoire_et_appareil_enrole_refuses(self):
        provisoire = self.connecter("paul.durand", MOT_DE_PASSE_PROVISOIRE)
        refus = self.langue(provisoire, {"langue": "en"})
        self.assertEqual((refus.statut, refus.json()["erreur_code"]), (403, "sessions.mot_de_passe_provisoire"))
        responsable = self.connecter("nicolas.briand", MOT_DE_PASSE_RESPONSABLE)
        invitation = self.client.requete("POST", "/api/acces/invitations", {"heures": 1}, cookie=responsable).json()
        enrole = self.client.requete("POST", "/api/enroler", {"invitation": invitation["jeton"], "nom": "Tablette"})
        self.assertEqual(enrole.statut, 200, enrole.octets)
        appareil = enrole.cookie
        self.assertTrue(appareil.startswith("appareil="))
        self.assertEqual(self.client.session(appareil)["langue"], "")
        refus = self.langue(appareil, {"langue": "en"})
        self.assertEqual((refus.statut, refus.json()["erreur_code"]), (403, "sessions.langue_appareil"))
        self.assertNotIn("langue", json.dumps(self.comptes()))

    def test_session_porte_une_langue_declaree_seulement(self):
        comptes = json.loads(COMPTES_JSON.decode("utf-8"))
        for compte in comptes["comptes"]:
            if compte["identifiant"] == "lea.martin":
                compte["langue"] = "<script>alert(1)</script>"                       # écrit à la main
            if compte["identifiant"] == "julien.moreau":
                compte["langue"] = "en"
        (self.donnees / "acces" / "comptes.json").write_text(json.dumps(comptes), encoding="utf-8")
        lea = self.client.session(self.connecter("lea.martin", MOT_DE_PASSE_DEMANDEUR))
        julien = self.client.session(self.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN))
        self.assertEqual((lea["langue"], julien["langue"]), ("", "en"))
        self.assertEqual(set(lea), CHAMPS_PUBLICS_DE_SESSION)


class TestLangueParLeResponsable(CasRoute):

    def test_creation_et_modification_avec_langue(self):
        responsable = self.connecter("nicolas.briand", MOT_DE_PASSE_RESPONSABLE)
        cree = self.client.requete("POST", "/api/acces/comptes", {"prenom": "Ana", "nom": "Silva", "role": "demandeur",
                                                                  "langue": "en"}, cookie=responsable)
        self.assertEqual(cree.statut, 200, cree.octets)
        self.assertEqual(cree.json()["compte"]["langue"], "en")
        self.assertEqual(self.comptes()["ana.silva"]["langue"], "en")
        sans = self.client.requete("POST", "/api/acces/comptes", {"prenom": "Rui", "nom": "Costa", "role": "demandeur",
                                                                  "langue": ""}, cookie=responsable)
        self.assertEqual(sans.statut, 200, sans.octets)
        self.assertNotIn("langue", self.comptes()["rui.costa"])                     # vide : aucun champ
        octets = self.octets_comptes()
        for valeur in VALEURS_REFUSEES:
            refus = self.client.requete("POST", "/api/acces/comptes", {"prenom": "Zoé", "nom": "Refus",
                                                                       "role": "demandeur", "langue": valeur},
                                        cookie=responsable)
            self.assertEqual(refus.statut, 400, valeur)
        self.assertEqual(self.octets_comptes(), octets)
        # Modifier : la langue seule, puis avec le rôle ; hors liste : 400, rien d'écrit.
        adresse = "/api/acces/comptes/julien.moreau"
        avant = self.comptes()["julien.moreau"]
        modifie = self.client.requete("POST", adresse, {"action": "modifier", "langue": "en"}, cookie=responsable)
        self.assertEqual((modifie.statut, modifie.json()["compte"]["langue"]), (200, "en"))
        apres = self.comptes()["julien.moreau"]
        self.assertEqual({k: v for k, v in sans_langue(apres).items() if k != "modifie_le"},
                         {k: v for k, v in avant.items() if k != "modifie_le"})
        octets = self.octets_comptes()
        for valeur in VALEURS_REFUSEES:
            refus = self.client.requete("POST", adresse, {"action": "modifier", "langue": valeur}, cookie=responsable)
            code = "comptes.langue_inconnue" if isinstance(valeur, str) else "comptes.texte_attendu"
            self.assertEqual((refus.statut, refus.json()["erreur_code"]), (400, code), valeur)
        self.assertEqual(self.octets_comptes(), octets)
        self.assertEqual(self.client.requete("POST", adresse, {"action": "modifier", "langue": ""},
                                             cookie=responsable).statut, 200)
        self.assertNotIn("langue", self.comptes()["julien.moreau"])
        # Le technicien voit la langue choisie par le responsable dans sa session.
        self.client.requete("POST", adresse, {"action": "modifier", "langue": "en"}, cookie=responsable)
        julien = self.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN)
        self.assertEqual(self.client.session(julien)["langue"], "en")
        # Journal : « modification » puis la langue, comme les autres changements de compte.
        self.assertEqual(self.resultats("julien.moreau")[:6],
                         ["modification", "langue:installation>en", "modification", "langue:en>installation",
                          "modification", "langue:installation>en"])
        self.assertIn("creation", self.resultats("ana.silva"))
        # Aucun secret ne part avec la liste des comptes.
        liste = self.client.requete("GET", "/api/acces/comptes", cookie=responsable)
        for compte in liste.json()["comptes"]:
            self.assertFalse({"sel", "empreinte", "algo"} & set(compte), compte["identifiant"])
        self.assertEqual({c["identifiant"]: c.get("langue") for c in liste.json()["comptes"]}["julien.moreau"], "en")

    def test_technicien_refuse_sur_le_compte_d_un_autre(self):
        technicien = self.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN)
        octets = self.octets_comptes()
        for chemin, corps in (("/api/acces/comptes/nicolas.briand", {"action": "modifier", "langue": "en"}),
                              ("/api/acces/comptes/lea.martin", {"action": "modifier", "langue": "en"}),
                              ("/api/acces/comptes/julien.moreau", {"action": "modifier", "langue": "en"}),
                              ("/api/acces/comptes", {"prenom": "Ana", "role": "demandeur", "langue": "en"})):
            self.assertEqual(self.client.requete("POST", chemin, corps, cookie=technicien).statut, 403, chemin)
        self.assertEqual(self.client.requete("GET", "/api/acces/comptes", cookie=technicien).statut, 403)
        self.assertEqual(self.octets_comptes(), octets)
        # Sa propre langue, il la change par sa session, jamais celle d'un autre.
        self.assertEqual(self.langue(technicien, {"langue": "en"}).statut, 200)
        comptes = self.comptes()
        self.assertEqual([c for c in comptes if "langue" in comptes[c]], ["julien.moreau"])


# ---------------------------------------------------------------------------
# 2. Compatibilité avec la 2.0.0 bêta 2 (serveur réel)
# ---------------------------------------------------------------------------

def compte_au_format_beta2(identifiant, prenom, nom, role, mot_de_passe, technicien_id, numero):
    """Un compte tel que l'écrivait la 2.0.0 bêta 2 (creer_compte : mêmes champs, même ordre, sans langue)."""
    sel = bytes([numero] * 16)
    algo, sel64, empreinte = serveur.hacher_mot_de_passe(mot_de_passe, sel, serveur.ALGO_SCRYPT)
    instant = "2026-10-28T09:%02d:00" % numero
    return dict(zip(CHAMPS_BETA2, [identifiant, prenom, nom, role, technicien_id, True, algo, sel64, empreinte, False,
                                   instant, instant, instant]))


def fichiers_compares(dossier):
    """Octets des CSV de la base et de acces/comptes.json (ce qu'une ouverture ne doit jamais changer)."""
    dossier = Path(dossier)
    fichiers = {chemin.name: chemin.read_bytes() for chemin in sorted(dossier.glob("*.csv"))}
    fichiers["acces/comptes.json"] = (dossier / "acces" / "comptes.json").read_bytes()
    return fichiers


class TestCompatibiliteBeta2(unittest.TestCase):

    def setUp(self):
        self.racine = Path(tempfile.mkdtemp(prefix="prevo-langue-beta2-"))
        self.addCleanup(shutil.rmtree, self.racine, True)
        self.configuration = self.racine / "prevo.config.json"
        self.configuration.write_text(json.dumps({"comptes": True}), encoding="utf-8")

    def base(self, avec_autres_roles):
        source = copier_jeu(JEU_BETA2, self.racine / "jeu" / "donnees")
        chemin = source / "acces" / "comptes.json"
        self.assertNotIn(b'"langue"', chemin.read_bytes())
        if avec_autres_roles:
            contenu = json.loads(chemin.read_bytes().decode("utf-8"))
            contenu["comptes"] += [
                compte_au_format_beta2("julien.moreau", "Julien", "Moreau", "technicien", MOT_DE_PASSE_TECHNICIEN,
                                       "TEC-0001", 1),
                compte_au_format_beta2("lea.martin", "Léa", "Martin", "demandeur", MOT_DE_PASSE_DEMANDEUR, "", 2)]
            # Écrit comme la bêta 2 l'écrivait (ecrire_comptes : indent=2, ensure_ascii=False, sans fin de ligne).
            chemin.write_bytes(json.dumps(contenu, ensure_ascii=False, indent=2).encode("utf-8"))
        return source

    def lancer(self, source):
        return ServeurPrevo(source=source, arguments=["--config", str(self.configuration)])

    def test_base_beta2_ouverte_sans_perte_compte_relu(self):
        source = self.base(avec_autres_roles=False)
        origine = fichiers_compares(source)
        with self.lancer(source) as lance:
            client = Client(lance.url)
            connexion = client.connecter("claire.essai", MOT_DE_PASSE_BETA2)
            self.assertEqual(connexion.statut, 200, connexion.octets)
            session = client.session(connexion.cookie)
            self.assertEqual((session["role"], session["langue"]), ("responsable", ""))
            self.assertEqual(client.requete("GET", "/api/acces/comptes", cookie=connexion.cookie).statut, 200)
            self.assertEqual(client.requete("GET", "/api/csv/equipements", cookie=connexion.cookie).statut, 200)
            self.assertEqual(fichiers_compares(lance.dossier), origine)                 # à l'octet près

    def test_chaque_role_relu_puis_langue_changee_sans_toucher_aux_autres_champs(self):
        source = self.base(avec_autres_roles=True)
        origine = fichiers_compares(source)
        comptes_origine = comptes_par_identifiant(origine["acces/comptes.json"])
        with self.lancer(source) as lance:
            client = Client(lance.url)
            cookies = {}
            for identifiant, mot_de_passe, role in (("claire.essai", MOT_DE_PASSE_BETA2, "responsable"),
                                                    ("julien.moreau", MOT_DE_PASSE_TECHNICIEN, "technicien"),
                                                    ("lea.martin", MOT_DE_PASSE_DEMANDEUR, "demandeur")):
                connexion = client.connecter(identifiant, mot_de_passe)
                self.assertEqual(connexion.statut, 200, (identifiant, connexion.octets))
                session = client.session(connexion.cookie)
                self.assertEqual((session["role"], session["langue"]), (role, ""))
                cookies[identifiant] = connexion.cookie
            self.assertEqual(fichiers_compares(lance.dossier), origine)                 # rien changé encore
            # Le technicien choisit l'anglais pour son compte ; le responsable met le français à la demandeuse.
            self.assertEqual(client.requete("POST", "/api/mot-de-passe", {"langue": "en"},
                                            cookie=cookies["julien.moreau"]).statut, 200)
            self.assertEqual(client.requete("POST", "/api/acces/comptes/lea.martin", {"action": "modifier",
                                            "langue": "fr"}, cookie=cookies["claire.essai"]).statut, 200)
            apres = fichiers_compares(lance.dossier)
            comptes = comptes_par_identifiant(apres["acces/comptes.json"])
            self.assertEqual(list(comptes), list(comptes_origine))
            self.assertEqual(comptes["julien.moreau"]["langue"], "en")
            self.assertEqual(sans_langue(comptes["julien.moreau"]), comptes_origine["julien.moreau"])
            self.assertEqual(comptes["claire.essai"], comptes_origine["claire.essai"])
            self.assertEqual(comptes["lea.martin"]["langue"], "fr")
            self.assertEqual({k: v for k, v in sans_langue(comptes["lea.martin"]).items() if k != "modifie_le"},
                             {k: v for k, v in comptes_origine["lea.martin"].items() if k != "modifie_le"})
            self.assertEqual({nom: octets for nom, octets in apres.items() if nom != "acces/comptes.json"},
                             {nom: octets for nom, octets in origine.items() if nom != "acces/comptes.json"})
            # Les sessions ouvertes restent ouvertes et voient la langue.
            self.assertEqual(client.session(cookies["julien.moreau"])["langue"], "en")
            self.assertEqual(client.session(cookies["lea.martin"])["langue"], "fr")
            # Le mot de passe de chacun est toujours le même (sel et empreinte de la bêta 2 relus).
            self.assertEqual(client.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN).statut, 200)


# ---------------------------------------------------------------------------
# 3. Écrans (Chromium, serveur réel, installation française)
# ---------------------------------------------------------------------------

ETAT_JS = """() => {
  const lire = (cle) => { try { return localStorage.getItem(cle); } catch (erreur) { return 'illisible'; } };
  return { langue: I18n.langue, lang: document.documentElement.lang, compte: lire('prevo.langue.compte'),
    poste: lire('prevo.langue'), etat: document.documentElement.dataset.etat };
}"""
CLE_UNE_FOIS_JS = """(() => {
  try {
    if (!sessionStorage.getItem('test.cle')) {
      sessionStorage.setItem('test.cle', '1');
      localStorage.setItem('prevo.langue.compte', %s);
    }
  } catch (erreur) { /* sans stockage : rien */ }
})();"""
REFUS_CLE_COMPTE_JS = """(() => {
  const avant = Storage.prototype.setItem;
  Storage.prototype.setItem = function (cle, ...reste) {
    if (cle === 'prevo.langue.compte') throw new DOMException('Stockage refusé (test)', 'SecurityError');
    return avant.call(this, cle, ...reste);
  };
})();"""
ATTENTE_SANS_RECHARGEMENT_MS = 1500
# Sans session, l'appli demande à une lecture protégée si un cookie d'appareil a été refusé (401 attendu).
ERREUR_401_SONDE = re.compile(r"status of 401.*/api/versions")
LISTE_LANGUE_JS = """() => [...document.querySelectorAll('dialog[open] select[name=langue] option')]
  .map((o) => [o.value, o.textContent, o.lang])"""


class TestLangueDuCompteEcrans(CasNavigateur):

    def setUp(self):
        super().setUp()
        self.chargements = {}
        self.avertissements = []
        self.suivre(self.page)

    def suivre(self, page):
        self.chargements[page] = 0
        page.on("load", lambda _page: self.chargements.__setitem__(page, self.chargements[page] + 1))
        page.on("console", lambda message: self.avertissements.append(message.text)
                if message.type == "warning" else None)

    # -- outils ---------------------------------------------------------------------------------

    def serveur_francais(self):
        """Serveur réel, copie de la démo, trois comptes (COMPTES_DE_TEST) ; installation en français."""
        lance = ServeurPrevo(comptes=True)
        lance.demarrer()
        self.addCleanup(lance.arreter)
        poser_langue(lance.dossier, "fr")
        return lance

    def langue_par_l_api(self, lance, role, valeur):
        reponse = Client(lance.url).requete("POST", "/api/mot-de-passe", {"langue": valeur}, cookie=lance.session(role))
        self.assertEqual(reponse.statut, 200, reponse.octets)

    def comptes(self, lance):
        return comptes_par_identifiant((lance.dossier / "acces" / "comptes.json").read_bytes())

    def attendre(self, nombre, etat="pret", page=None):
        """Le `nombre`-ième chargement de la page, l'application dans `etat`, puis aucun chargement de plus."""
        page = page or self.page
        for _ in range(150):
            if self.chargements[page] >= nombre:
                break
            page.wait_for_timeout(100)
        if etat == "pret":
            attendre_pret(page)
        else:
            page.wait_for_function("document.documentElement.dataset.etat === %r" % etat)
        page.wait_for_timeout(ATTENTE_SANS_RECHARGEMENT_MS)
        self.assertEqual(self.chargements[page], nombre, "nombre de chargements de la page")
        return page.evaluate(ETAT_JS)

    def ouvrir_poste(self, lance, page=None, chargements=1):
        page = page or self.page
        page.goto(lance.url + "/#/poste")
        etat = self.attendre(chargements, page=page)
        page.wait_for_selector("#poste-langue-liste")
        return etat

    def choisir(self, code, chargements):
        with self.page.expect_navigation():
            self.page.select_option("#poste-langue-liste", code)
        return self.attendre(chargements)

    def portees(self, page=None):
        return (page or self.page).evaluate("""() => [...document.querySelectorAll('input[name=poste-langue-portee]')]
          .map((b) => [b.value, b.checked])""")

    # -- tests ----------------------------------------------------------------------------------

    def test_connexion_dans_la_langue_du_compte_puis_deconnexion_dans_celle_du_poste(self):
        lance = self.serveur_francais()
        self.langue_par_l_api(lance, "technicien", "en")
        identifiant, _, _, mot_de_passe, _ = COMPTES_DE_TEST["technicien"]
        self.autoriser_erreur(ERREUR_401_SONDE)
        self.page.goto(lance.url + "/")
        etat = self.attendre(1, "connexion")
        self.assertEqual((etat["langue"], etat["compte"]), ("fr", None))            # l'écran de connexion : le poste
        self.page.fill("#connexion-identifiant", identifiant)
        self.page.fill("#connexion-mot-de-passe", mot_de_passe)
        with self.page.expect_navigation():
            self.page.click("#connexion-valider")
        etat = self.attendre(2)
        self.assertEqual((etat["langue"], etat["lang"], etat["compte"], etat["poste"]), ("en", "en", "en", None))
        self.assertEqual(self.page.evaluate("I18n.t('poste.menu.libelle')"),
                         texte_du_dictionnaire("en", "poste.menu.libelle"))
        self.assertEqual(self.page.evaluate("App.session.langue"), "en")
        # Déconnexion : la clé est effacée, l'écran de connexion revient dans la langue du poste (français).
        with self.page.expect_navigation():
            self.page.evaluate("() => { App.deconnecter(); }")
        etat = self.attendre(3, "connexion")
        self.assertEqual((etat["langue"], etat["compte"]), ("fr", None))
        self.assertEqual(self.page.inner_text("#connexion-valider").strip(),
                         texte_du_dictionnaire("fr", "socle.connexion_valider.connecter"))

    def test_pour_mon_compte_enregistree_et_suivie_sur_un_autre_navigateur(self):
        lance = self.serveur_francais()
        lance.poser_session(self.contexte, "technicien")
        self.ouvrir_poste(lance)
        self.assertEqual(self.portees(), [["compte", False], ["poste", True]])          # le compte n'a pas de langue
        # « Pour mon compte » : la langue affichée (français) part au compte, sans rechargement.
        self.page.check("#poste-langue-compte")
        self.page.wait_for_function("App.session.langue === 'fr'")
        self.assertEqual(self.comptes(lance)["julien.moreau"]["langue"], "fr")
        # Puis English : enregistré dans le compte, page rechargée en anglais ; le choix du poste n'a pas bougé.
        etat = self.choisir("en", 2)
        self.assertEqual((etat["langue"], etat["compte"], etat["poste"]), ("en", "en", None))
        self.assertEqual(self.comptes(lance)["julien.moreau"]["langue"], "en")
        self.page.wait_for_selector("#poste-langue-compte")
        self.assertEqual(self.portees(), [["compte", True], ["poste", False]])
        # Un autre navigateur (autre contexte, rien dans son stockage) : connecté, il passe à l'anglais, une fois.
        autre = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
        self.addCleanup(autre.close)
        lance.poser_session(autre, "technicien")
        page = autre.new_page()
        self.surveiller(page)
        self.suivre(page)
        etat = self.ouvrir_poste(lance, page=page, chargements=2)
        self.assertEqual((etat["langue"], etat["compte"], etat["poste"]), ("en", "en", None))
        self.assertEqual(self.portees(page), [["compte", True], ["poste", False]])
        resultats = [ligne["resultat"] for ligne in lignes_du_journal(lance.dossier) if ligne["qui"] == "julien.moreau"]
        self.assertEqual([r for r in resultats if r.startswith("langue")], ["langue:installation>fr", "langue:fr>en"])

    def test_pour_ce_poste_comme_avant(self):
        lance = self.serveur_francais()
        lance.poser_session(self.contexte, "responsable")
        self.ouvrir_poste(lance)
        etat = self.choisir("en", 2)                                                   # « pour ce poste » coché
        self.assertEqual((etat["langue"], etat["compte"], etat["poste"]), ("en", None, "en"))
        self.assertNotIn("langue", self.comptes(lance)["nicolas.briand"])
        # Le compte prend la langue, puis « pour ce poste » la lui retire : le poste la garde, rien ne se recharge.
        self.page.wait_for_selector("#poste-langue-compte")
        self.page.check("#poste-langue-compte")
        self.page.wait_for_function("App.session.langue === 'en'")
        self.assertEqual(self.comptes(lance)["nicolas.briand"]["langue"], "en")
        self.page.check("#poste-langue-poste")
        self.page.wait_for_function("App.session.langue === ''")
        etat = self.attendre(2)
        self.assertEqual((etat["langue"], etat["compte"], etat["poste"]), ("en", None, "en"))
        self.assertNotIn("langue", self.comptes(lance)["nicolas.briand"])

    def test_sans_comptes_rien_ne_change_sur_ce_poste(self):
        preregler_profil(self.contexte, "responsable")
        with ServeurPrevo() as lance:
            self.page.goto(lance.url + "/#/poste")
            self.attendre(1)
            self.page.wait_for_selector("#poste-langue-liste")
            self.assertEqual(self.portees(), [])
            self.assertEqual(self.page.locator("#poste-langue .aide").count(), 1)

    def test_cle_abimee_ignoree(self):
        self.contexte.add_init_script(CLE_UNE_FOIS_JS % json.dumps("xx\"><img src=x onerror=alert(1)>"))
        requetes = []
        self.page.on("request", lambda requete: requetes.append(requete.url))
        lance = self.serveur_francais()
        lance.poser_session(self.contexte, "technicien")
        self.page.goto(lance.url + "/#/accueil")
        etat = self.attendre(1)
        self.assertEqual((etat["langue"], etat["compte"]), ("fr", None))              # ignorée, puis effacée
        autres = [url for url in requetes if "/js/i18n/" in url and not re.search(r"/js/i18n/(langues|fr|aide/fr)\.js$", url)]
        self.assertEqual(autres, [])

    def test_cle_laissee_par_un_autre_compte_effacee_un_rechargement(self):
        """Poste partagé : la clé d'une session précédente (anglais) ; le compte connecté n'a pas de langue."""
        self.contexte.add_init_script(CLE_UNE_FOIS_JS % json.dumps("en"))
        lance = self.serveur_francais()
        lance.poser_session(self.contexte, "responsable")
        self.page.goto(lance.url + "/#/accueil")
        etat = self.attendre(2)
        self.assertEqual((etat["langue"], etat["compte"]), ("fr", None))

    def test_un_seul_rechargement_quand_la_cle_est_refusee(self):
        self.contexte.add_init_script(REFUS_CLE_COMPTE_JS)
        lance = self.serveur_francais()
        self.langue_par_l_api(lance, "technicien", "en")
        lance.poser_session(self.contexte, "technicien")
        self.page.goto(lance.url + "/#/accueil")
        etat = self.attendre(2)                                                        # un rechargement, puis plus aucun
        self.assertEqual((etat["langue"], etat["compte"]), ("fr", None))
        self.assertEqual(len([t for t in self.avertissements if "déjà rechargée pour la langue" in t]), 1)

    def test_equipe_acces_creation_modification_et_journal(self):
        lance = self.serveur_francais()
        lance.poser_session(self.contexte, "responsable")
        self.page.goto(lance.url + "/#/equipe/acces")
        self.attendre(1)
        self.page.wait_for_selector("#acces-comptes tbody tr")
        dialogue = self.page.locator("dialog[open]").last
        # Créer : liste « Langue », la langue de l'installation d'abord, puis chaque langue sous son nom.
        self.page.click("#acces-creer-compte")
        self.assertEqual(self.page.evaluate(LISTE_LANGUE_JS),
                         [["", texte_du_dictionnaire("fr", "equipe.champs_compte.langue_installation"), ""],
                          ["fr", "Français", "fr"], ["en", "English", "en"]])
        self.assertEqual(dialogue.locator("select[name=langue]").input_value(), "")
        dialogue.locator("input[name=prenom]").fill("Ana")
        dialogue.locator("input[name=nom]").fill("Silva")
        dialogue.locator("select[name=role]").select_option("demandeur")
        dialogue.locator("select[name=langue]").select_option("en")
        dialogue.locator("button:has-text('Créer le compte')").click()
        self.page.wait_for_selector("#acces-mot-de-passe-provisoire")
        self.page.locator("dialog[open] .fenetre-actions button").last.click()
        self.page.wait_for_selector("dialog[open]", state="detached")
        self.assertEqual(self.comptes(lance)["ana.silva"]["langue"], "en")
        # Modifier : la langue de julien.moreau, relue à la réouverture.
        ligne = self.page.locator("#acces-comptes tbody tr:has(td b:text-is('julien.moreau'))")
        ligne.locator("button[data-action=modifier]").click()
        self.assertEqual(dialogue.locator("select[name=langue]").input_value(), "")
        dialogue.locator("select[name=langue]").select_option("en")
        dialogue.locator("button:has-text('Enregistrer')").click()
        self.page.wait_for_selector("dialog[open]", state="detached")
        self.assertEqual(self.comptes(lance)["julien.moreau"]["langue"], "en")
        self.page.wait_for_selector("#acces-comptes tbody tr:has(td b:text-is('julien.moreau'))")
        ligne.locator("button[data-action=modifier]").click()
        self.assertEqual(dialogue.locator("select[name=langue]").input_value(), "en")
        self.page.locator("dialog[open] .fenetre-actions button").first.click()
        self.page.wait_for_selector("dialog[open]", state="detached")
        # Journal : « Langue changée (installation → en) », après « Compte modifié ».
        self.page.goto(lance.url + "/#/equipe/acces?onglet=journal")
        self.page.wait_for_selector("#acces-journal tbody tr")
        attendu = texte_du_dictionnaire("fr", "equipe.libelle_resultat.langue_changee").format(
            avant=texte_du_dictionnaire("fr", "equipe.libelle_resultat.langue_installation"), apres="en")
        lignes = self.page.locator("#acces-journal tbody tr:has-text('julien.moreau')").all_inner_texts()
        self.assertTrue(any(attendu in texte for texte in lignes), lignes)


if __name__ == "__main__":
    unittest.main()
