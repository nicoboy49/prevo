"""Relais POST /api/ia de serveur.py (lot 4, ARCHITECTURE.md §17.2 ; CDC D66 ; CS69).

Toujours avec le faux fournisseur (tests/faux_fournisseur_ia.py), jamais un vrai modèle :
    - Ollama (api/tags, api/chat) et API compatible OpenAI (models, chat/completions) relayés ;
    - la clé est transmise au fournisseur en « Authorization: Bearer », et n'apparaît jamais dans une
      réponse du serveur, sa console, ni un fichier de données ;
    - liste fermée des chemins, adresse contrôlée (http ou https, sans identifiant, requête ni
      fragment), en-tête X-Prevo obligatoire, méthode POST seule ;
    - fournisseur injoignable → 502 ; délai dépassé → 504 ; réponse de plus de 2 Mo → 502 ;
      redirection non suivie.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_serveur_ia.py" -v
"""
import json
import socket
import unittest
import urllib.error
import urllib.request

from commun import ServeurPrevo
from faux_fournisseur_ia import FauxFournisseur

CLE = "sk-test-cle-secrete-123456"


def port_ferme():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestRelaisIa(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.serveur = ServeurPrevo()
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)
        cls.faux = FauxFournisseur(lenteur_s=4, cle_attendue=CLE)
        cls.faux.demarrer()
        cls.addClassCleanup(cls.faux.arreter)

    def relayer(self, demande, entete_prevo=True, methode="POST", delai=30):
        octets = json.dumps(demande).encode("utf-8")
        requete = urllib.request.Request(self.serveur.url + "/api/ia", data=octets if methode == "POST" else None,
                                         method=methode, headers={"Content-Type": "application/json"})
        if entete_prevo:
            requete.add_header("X-Prevo", "1")
        try:
            with urllib.request.urlopen(requete, timeout=delai) as reponse:
                return reponse.status, json.loads(reponse.read().decode("utf-8"))
        except urllib.error.HTTPError as erreur:
            texte = erreur.read().decode("utf-8")
            return erreur.code, json.loads(texte) if texte else {}

    def chat_ollama(self, modele="faux", **autres):
        demande = {"url": self.faux.url, "chemin": "api/chat", "methode": "POST",
                   "corps": {"model": modele, "stream": False,
                             "messages": [{"role": "system", "content": "Fonction : compteRendu"},
                                          {"role": "user", "content": "notes : garniture changée"}]}}
        demande.update(autres)
        return self.relayer(demande)

    def test_ollama_liste_des_modeles_et_chat_relayes(self):
        statut, reponse = self.relayer({"url": self.faux.url, "chemin": "api/tags", "methode": "GET"})
        self.assertEqual((statut, reponse["statut"]), (200, 200))
        self.assertIn("faux", [m["name"] for m in reponse["corps"]["models"]])
        statut, reponse = self.chat_ollama()
        self.assertEqual((statut, reponse["statut"]), (200, 200))
        self.assertIn("Constat", json.loads(reponse["corps"]["message"]["content"])["texte"])
        self.assertEqual(self.faux.requetes_vers("/api/chat")[-1]["corps"]["messages"][1]["content"], "notes : garniture changée")

    def test_openai_cle_transmise_et_jamais_rendue(self):
        demande = {"url": self.faux.url + "/v1", "chemin": "chat/completions", "methode": "POST", "cle": CLE,
                   "corps": {"model": "faux", "messages": [{"role": "system", "content": "Fonction : resumeHistorique"}]}}
        statut, reponse = self.relayer(demande)
        self.assertEqual((statut, reponse["statut"]), (200, 200))
        self.assertIn("garniture", reponse["corps"]["choices"][0]["message"]["content"])
        self.assertEqual(self.faux.requetes_vers("/v1/chat/completions")[-1]["entetes"]["authorization"], "Bearer " + CLE)
        self.assertNotIn(CLE, json.dumps(reponse))
        # Sans clé : le fournisseur refuse (401), le relais rend ce statut sans rien inventer
        demande.pop("cle")
        statut, reponse = self.relayer(demande)
        self.assertEqual((statut, reponse["statut"]), (200, 401))
        # Liste des modèles
        statut, reponse = self.relayer({"url": self.faux.url + "/v1", "chemin": "models", "methode": "GET", "cle": CLE})
        self.assertIn("faux", [m["id"] for m in reponse["corps"]["data"]])

    def test_cle_absente_de_la_console_et_des_donnees(self):
        self.relayer({"url": self.faux.url + "/v1", "chemin": "chat/completions", "methode": "POST", "cle": CLE,
                      "corps": {"model": "faux", "messages": [{"role": "system", "content": "Fonction : codes"}]}})
        self.relayer({"url": "ftp://exemple/", "chemin": "models", "methode": "GET", "cle": CLE})   # refus : la clé n'est pas citée
        self.assertNotIn(CLE, self.serveur.sortie_console())
        self.assertIn("POST /api/ia", self.serveur.sortie_console())
        for fichier in self.serveur.dossier.rglob("*"):
            if fichier.is_file():
                self.assertNotIn(CLE.encode("utf-8"), fichier.read_bytes(), fichier.name)

    def test_refus_chemin_adresse_entete_methode(self):
        for chemin in ("api/pull", "api/chat/../delete", "../serveur.py", "v1/chat/completions", "", "API/CHAT"):
            with self.subTest(chemin=chemin):
                statut, reponse = self.relayer({"url": self.faux.url, "chemin": chemin, "methode": "GET"})
                self.assertEqual(statut, 400)
                self.assertIn("erreur", reponse)
        for url in ("ftp://127.0.0.1:1/", "file:///C:/Windows", "http://moi:secret@127.0.0.1:1",
                    self.faux.url + "?x=1", self.faux.url + "#a", "pas une adresse", ""):
            with self.subTest(url=url):
                statut, reponse = self.relayer({"url": url, "chemin": "api/tags", "methode": "GET"})
                self.assertEqual(statut, 400)
                self.assertNotIn("secret", json.dumps(reponse))
        statut, _ = self.relayer({"url": self.faux.url, "chemin": "api/tags", "methode": "DELETE"})
        self.assertEqual(statut, 400)
        statut, _ = self.relayer({"url": self.faux.url, "chemin": "api/tags", "methode": "GET"}, entete_prevo=False)
        self.assertEqual(statut, 403)
        statut, _ = self.relayer({}, methode="GET")
        self.assertEqual(statut, 405)
        statut, _ = self.relayer(["pas", "un", "objet"])
        self.assertEqual(statut, 400)

    def test_fournisseur_injoignable_delai_et_reponse_trop_grande(self):
        statut, reponse = self.relayer({"url": "http://127.0.0.1:%d" % port_ferme(), "chemin": "api/tags", "methode": "GET"})
        self.assertEqual(statut, 502)
        self.assertIn("injoignable", reponse["erreur"])
        statut, reponse = self.chat_ollama("faux-lent", delai=1)
        self.assertEqual(statut, 504)
        statut, reponse = self.chat_ollama("faux-enorme")
        self.assertEqual(statut, 502)
        self.assertIn("trop grande", reponse["erreur"])

    def test_redirection_non_suivie(self):
        avant = len(self.faux.requetes_vers("/redirection-cible"))
        statut, reponse = self.chat_ollama("faux-redirige")
        self.assertEqual((statut, reponse["statut"]), (200, 302))
        self.assertEqual(len(self.faux.requetes_vers("/redirection-cible")), avant)


if __name__ == "__main__":
    unittest.main()
