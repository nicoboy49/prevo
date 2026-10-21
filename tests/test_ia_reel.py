"""Essai réel facultatif de l'assistant IA (lot 4, CDC D72, CS78) : vrai Ollama et qwen2.5:7b sur ce PC.

Sauté sauf PREVO_TEST_IA=1 (comme le vrai Excel avec PREVO_TEST_EXCEL=1) : la suite complète n'utilise
que le faux fournisseur (tests/faux_fournisseur_ia.py), jamais un vrai modèle.

Jeu d'essai en français tiré du jeu de démo, en mode serveur (relais /api/ia, comme un poste de l'atelier) :
    codes         : OT correctifs clôturés de la démo, avec compte rendu, symptôme de la DI et trois codes
                    (une cause différente par OT tant que possible) ; justesse = code proposé égal au code
                    de la démo, par famille (symptôme, cause, remède) ;
    reformulation : DI de la démo (symptôme, description, repère, désignation) ;
    compte rendu  : notes brèves tirées des comptes rendus de la démo.
Ce qui fait échouer l'essai : une réponse hors délai, illisible ou refusée par les validations de Prévo
(code hors de la liste fermée, texte vide). La justesse et la qualité des textes sont MESURÉES et
affichées (pas de seuil : D72 demande une mesure, consignée dans le pilotage et le guide).

Variables : PREVO_TEST_IA=1 ; PREVO_IA_URL (défaut http://localhost:11434) ; PREVO_IA_MODELE (défaut
qwen2.5:7b) ; PREVO_IA_NOMBRE (OT du jeu des codes, défaut 12).
Lancer depuis la racine du projet (PowerShell) :
    $env:PREVO_TEST_IA = "1"; py -m unittest discover -s tests -p "test_ia_reel.py" -v
"""
import csv
import json
import os
import statistics
import unittest
import urllib.request

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil
from test_ia_regles import DEMANDER_JS, regler_ia

URL = os.environ.get("PREVO_IA_URL", "http://localhost:11434").rstrip("/")
MODELE = os.environ.get("PREVO_IA_MODELE", "qwen2.5:7b")
NOMBRE = int(os.environ.get("PREVO_IA_NOMBRE", "12"))
DELAI_S = 300


def essai_demande():
    return os.environ.get("PREVO_TEST_IA") == "1"


def lire_csv(dossier, nom):
    with open(dossier / nom, encoding="utf-8-sig", newline="") as fichier:
        return [{k: (v or "").strip().lstrip("'") for k, v in ligne.items()}
                for ligne in csv.DictReader(fichier, delimiter=";")]


def modeles_installes():
    """Noms des modèles d'Ollama (GET /api/tags) ; AssertionError claire si Ollama ne répond pas."""
    try:
        with urllib.request.urlopen(URL + "/api/tags", timeout=5) as reponse:
            return [m.get("name", "") for m in json.loads(reponse.read().decode("utf-8")).get("models", [])]
    except OSError as erreur:
        raise AssertionError("Ollama ne répond pas à %s (%s) : lancez Ollama ou réglez PREVO_IA_URL." % (URL, erreur))


def jeu_des_codes(dossier, nombre):
    """OT correctifs clôturés avec compte rendu, symptôme de DI et trois codes : une cause différente par
    OT d'abord (ordre des identifiants), puis les suivants, jusqu'à `nombre`."""
    demandes = {d["id"]: d for d in lire_csv(dossier, "demandes.csv")}
    candidats = [o for o in lire_csv(dossier, "ordres_travail.csv")
                 if o["statut"].startswith("Clôturé") and o["compte_rendu"] and o["di_id"] in demandes
                 and demandes[o["di_id"]]["symptome"] and o["symptome_code"] and o["cause_code"] and o["remede_code"]]
    candidats.sort(key=lambda o: o["id"])
    choisis, causes = [], set()
    for ot in candidats:
        if ot["cause_code"] not in causes:
            choisis.append(ot)
            causes.add(ot["cause_code"])
    choisis += [o for o in candidats if o not in choisis]
    return [dict(ot=o, symptome_di=demandes[o["di_id"]]["symptome"]) for o in choisis[:nombre]]


def mesures(durees_ms):
    secondes = [d / 1000 for d in durees_ms]
    return "médiane %.1f s, pire %.1f s, total %.0f s" % (statistics.median(secondes), max(secondes), sum(secondes))


@unittest.skipUnless(essai_demande(), "essai réel non demandé : définir PREVO_TEST_IA=1 (vrai Ollama, %s)" % MODELE)
class TestIaReelle(CasNavigateur):

    DELAI_PAR_DEFAUT_MS = (DELAI_S + 30) * 1000

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        installes = modeles_installes()
        if MODELE not in installes:
            raise AssertionError("Modèle %s absent d'Ollama (installés : %s). Rien n'est téléchargé par l'essai."
                                 % (MODELE, ", ".join(installes) or "aucun"))

    def setUp(self):
        super().setUp()
        self.serveur = ServeurPrevo()
        self.serveur.demarrer()
        self.addCleanup(self.serveur.arreter)
        regler_ia(self.contexte, url=URL, modele=MODELE, delaiS=DELAI_S)
        preregler_profil(self.contexte, "responsable", "Responsable")
        self.page.goto(self.serveur.url + "/")
        attendre_pret(self.page)
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_function("Ia.etat() !== 'inconnu'", timeout=60000)
        self.assertEqual(self.page.evaluate("Ia.etat()"), "ok", "Prévo ne joint pas %s par le relais" % URL)

    def demander(self, fonction, donnees):
        reponse = self.page.evaluate(DEMANDER_JS, [fonction, donnees, {}])
        self.assertTrue(reponse["ok"], "%s : %s — %s" % (fonction, reponse.get("nom"), reponse.get("message")))
        self.assertEqual(reponse["modele"], MODELE)
        return reponse

    def test_codes_de_defaillance_justesse_par_famille(self):
        jeu = jeu_des_codes(self.serveur.dossier, NOMBRE)
        self.assertGreaterEqual(len(jeu), min(NOMBRE, 6), "jeu d'essai trop petit dans la démo")
        connus = {c["code"] for c in lire_csv(self.serveur.dossier, "codes_defaillance.csv")}
        justes = {"symptome": 0, "cause": 0, "remede": 0}
        durees = []
        print("\n=== Codes de défaillance (%s, %d OT) ===" % (MODELE, len(jeu)))
        for essai in jeu:
            ot = essai["ot"]
            reponse = self.demander("codes", {"compteRendu": ot["compte_rendu"], "titre": ot["titre"],
                                              "symptomeDI": essai["symptome_di"]})
            durees.append(reponse["duree"])
            resultat = reponse["resultat"]
            attendus = {"symptome": ot["symptome_code"], "cause": ot["cause_code"], "remede": ot["remede_code"]}
            for famille, attendu in attendus.items():
                propose = resultat.get(famille) or ""
                self.assertTrue(propose == "" or propose in connus, "%s : code inventé %r" % (ot["id"], propose))
                justes[famille] += propose == attendu
            print("%s  démo %s/%s/%s  proposé %s/%s/%s  rejetés %s  %.1f s" % (
                ot["id"], attendus["symptome"], attendus["cause"], attendus["remede"],
                resultat.get("symptome") or "—", resultat.get("cause") or "—", resultat.get("remede") or "—",
                resultat.get("rejetes") or [], reponse["duree"] / 1000))
        total = sum(justes.values())
        print("Justesse : symptôme %d/%d, cause %d/%d, remède %d/%d — ensemble %d/%d (%.0f %%)" % (
            justes["symptome"], len(jeu), justes["cause"], len(jeu), justes["remede"], len(jeu),
            total, 3 * len(jeu), 100 * total / (3 * len(jeu))))
        print("Temps : " + mesures(durees))

    def test_reformulation_des_di_et_compte_rendu(self):
        demandes = [d for d in lire_csv(self.serveur.dossier, "demandes.csv") if d["description"] and d["symptome"]][:4]
        equipements = {e["id"]: e for e in lire_csv(self.serveur.dossier, "equipements.csv")}
        durees = []
        print("\n=== Reformulation des DI (%s) ===" % MODELE)
        for di in demandes:
            eq = equipements.get(di["equipement_id"], {})
            reponse = self.demander("reformulerDI", {"symptome": di["symptome"], "description": di["description"],
                                                     "repere": eq.get("repere", ""), "designation": eq.get("designation", "")})
            durees.append(reponse["duree"])
            texte = json.dumps(reponse["resultat"], ensure_ascii=False)
            self.assertGreater(len(texte), 10)
            print("%s  « %s »\n    -> %s  (%.1f s)" % (di["id"], di["description"][:160], texte[:400], reponse["duree"] / 1000))
        print("Temps : " + mesures(durees))

        ordres = [o for o in lire_csv(self.serveur.dossier, "ordres_travail.csv")
                  if o["type"].startswith("correctif") and len(o["compte_rendu"]) > 40][:4]
        durees = []
        print("\n=== Compte rendu à partir de notes brèves (%s) ===" % MODELE)
        for ot in ordres:
            eq = equipements.get(ot["equipement_id"], {})
            notes = " ".join(ot["compte_rendu"].split()[:12])
            reponse = self.demander("compteRendu", {"notes": notes, "titre": ot["titre"], "type": ot["type"],
                                                    "repere": eq.get("repere", ""), "designation": eq.get("designation", ""),
                                                    "pieces": []})
            durees.append(reponse["duree"])
            texte = json.dumps(reponse["resultat"], ensure_ascii=False)
            self.assertGreater(len(texte), 10)
            print("%s  notes « %s »\n    -> %s  (%.1f s)" % (ot["id"], notes, texte[:500], reponse["duree"] / 1000))
        print("Temps : " + mesures(durees))


if __name__ == "__main__":
    unittest.main()
