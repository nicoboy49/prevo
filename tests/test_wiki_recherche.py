"""Recherche sans IA du wiki de maintenance (lot 6, tâche T98, ARCHITECTURE.md §20.6 ; décision D99 a).

Les données sont un CORPUS D'ESSAI écrit à la main (tests/fixtures/wiki/corpus.json : équipements dont deux
de même marque et modèle, OT clôturés et non clôturés, DI d'origine et DI regroupée, codes, synthèses
validée, « à valider » et « remplacée ») chargé dans StockageDemo, page file:// avec les seuls scripts utiles.

Couvert :
    - chaque requête du corpus : ses OT (ou synthèses) attendus parmi les 3 premiers de leur portée, les
      « jamais » absents de toutes les portées, « aucun » sans aucun résultat (lexique, pluriels, accents,
      majuscules, mots vides, expressions, OT non clôturés, synthèses non validées, DI d'origine) ;
    - mots comparables (Wiki.motsRecherche), Wiki.LEXIQUE (groupes du contrat, figé), Wiki.MOTS_VIDES ;
    - classement : scores BM25 égaux à un CALCUL PYTHON INDÉPENDANT (k1 = 1,2, b = 0,75, poids 0,7 d'un
      équivalent du lexique), égalité de score départagée par la date ;
    - portées : ordre équipement → même marque et modèle → parc, un résultat dans une seule portée,
      jumeaux comparés sans casse ni espaces, même marque mais autre modèle = parc, sans marque = portée
      « modèle » vide, sans équipement = parc seul, limite par portée ;
    - index : construit à la première recherche, refait après une écriture dans chacune des quatre tables
      indexées (Donnees.modifier) et après une relecture sans événement, pas refait pour une autre table ;
    - extrait (160 caractères au plus, autour du premier mot trouvé) et Wiki.surligner (<mark>, tout le
      reste échappé : le <script> d'un compte rendu reste du texte) ;
    - aucune requête réseau pendant les recherches ;
    - mesure indicative sur 5 000 OT fabriqués (la vraie mesure, D101, est celle de test_performance.py).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_wiki_recherche.py" -v
"""
import csv
import io
import json
import math
import random
import statistics
import sys
import unittest

from commun import RACINE, CasNavigateur, charger_scripts

SCRIPTS = [
    "js/lib/papaparse.min.js",
    "js/schema.js",
    "js/donnees.js",
    "js/stockage-demo.js",
    "js/interface.js",
    "js/modules/causes-frequentes.js",
    "js/modules/indicateurs-regles.js",
    "js/modules/wiki-regles.js",
    "js/modules/wiki-recherche.js",
]
FICHIER_CORPUS = RACINE / "tests" / "fixtures" / "wiki" / "corpus.json"
CORPUS = json.loads(FICHIER_CORPUS.read_text(encoding="utf-8"))

# Contrat §20.6 (copie indépendante du code) : groupes du lexique, poids d'un équivalent, BM25.
LEXIQUE_CONTRAT = [
    ["bruit", "grincement", "grince", "claquement", "claque", "cognement", "cogne", "sifflement", "siffle"],
    ["fuite", "fuit", "suintement", "suinte", "goutte"],
    ["chauffe", "surchauffe", "chaud", "temperature"],
    ["vibration", "vibre", "balourd"],
    ["bloque", "blocage", "coince", "grippe"],
    ["casse", "rupture", "fissure"],
    ["arret", "stoppe", "ne demarre pas"],
    ["pression", "manque de pression"],
    ["usure", "use"],
]
POIDS_EQUIVALENT = 0.7
K1, B = 1.2, 0.75
CLOS = "Clôturé techniquement"


# ---------------------------------------------------------------------------
# Données : tables du corpus → textes CSV pour StockageDemo
# ---------------------------------------------------------------------------

def valeur_texte(valeur):
    """Une valeur du corpus : une liste de lignes est jointe par des sauts de ligne."""
    return "\n".join(valeur) if isinstance(valeur, list) else valeur


def texte_csv(lignes):
    """Lignes (dictionnaires) → CSV « ; », CRLF, champs entre guillemets si besoin (§3.1)."""
    colonnes = []
    for ligne in lignes:
        colonnes.extend(cle for cle in ligne if cle not in colonnes)
    sortie = io.StringIO()
    ecrivain = csv.DictWriter(sortie, fieldnames=colonnes, delimiter=";", lineterminator="\r\n", restval="")
    ecrivain.writeheader()
    for ligne in lignes:
        ecrivain.writerow({cle: valeur_texte(valeur) for cle, valeur in ligne.items()})
    return sortie.getvalue()


def tables_csv(tables):
    return {nom: texte_csv(lignes) for nom, lignes in tables.items() if lignes}


def ot_clos(identifiant, equipement, titre, date_fin="2026-10-01 10:00", **champs):
    """Un OT correctif clôturé techniquement (champs utiles à la recherche seulement)."""
    ligne = {"id": identifiant, "origine": "manuel", "di_id": "", "equipement_id": equipement,
             "type": "correctif immédiat", "priorite": "P2", "statut": CLOS, "titre": titre,
             "travail_a_faire": "", "date_creation": date_fin[:10] + " 08:00", "date_fin": date_fin,
             "date_cloture_tech": date_fin, "symptome_code": "", "cause_code": "", "remede_code": "",
             "compte_rendu": ""}
    ligne.update(champs)
    return ligne


def identifiant(resultat):
    return resultat["otId"]


# ---------------------------------------------------------------------------
# Calcul Python indépendant du classement (corpus simple : mots sans accents, ni pluriels, ni mots vides)
# ---------------------------------------------------------------------------

def poids_de_la_requete(requete):
    mots = requete.lower().split()
    poids = {mot: 1.0 for mot in mots}
    for mot in mots:
        for groupe in LEXIQUE_CONTRAT:
            if mot in groupe:
                for equivalent in groupe:
                    poids.setdefault(equivalent, POIDS_EQUIVALENT)
    return poids


def bm25(documents, requete):
    """documents : {identifiant: texte} → {identifiant: score} des documents qui ont au moins un mot."""
    mots_par_document = {cle: texte.lower().split() for cle, texte in documents.items()}
    nombre = len(documents)
    longueur_moyenne = sum(len(mots) for mots in mots_par_document.values()) / nombre
    scores = {}
    for mot, poids in poids_de_la_requete(requete).items():
        avec_le_mot = [cle for cle, mots in mots_par_document.items() if mot in mots]
        if not avec_le_mot:
            continue
        idf = math.log(1 + (nombre - len(avec_le_mot) + 0.5) / (len(avec_le_mot) + 0.5))
        for cle in avec_le_mot:
            mots = mots_par_document[cle]
            frequence = mots.count(mot)
            normalisation = K1 * (1 - B + B * len(mots) / longueur_moyenne)
            scores[cle] = scores.get(cle, 0.0) + poids * idf * frequence * (K1 + 1) / (frequence + normalisation)
    return scores


# ---------------------------------------------------------------------------
# Base des tests
# ---------------------------------------------------------------------------

CHARGER_JS = """async (tables) => {
  Donnees.initialiser(StockageDemo.creer(tables), { poste: 'Poste test', profil: 'Responsable test' });
  await Donnees.chargerTout();
}"""

# Ajoute ou modifie des lignes d'une table : { table, lignes: [ligne complète ou { id, ...champs changés }] }.
ECRIRE_JS = """async ({ table, lignes }) => {
  await Donnees.modifier(table, (copie) => {
    lignes.forEach((ligne) => {
      const existante = copie.find((l) => l.id === ligne.id);
      if (existante) Object.assign(existante, ligne); else copie.push(ligne);
    });
    return true;
  }, { action: 'test de la recherche' });
}"""


class CasRecherche(CasNavigateur):

    def setUp(self):
        super().setUp()
        self.requetes_reseau = []
        self.page.on("request", lambda requete: self.requetes_reseau.append(requete.url))
        charger_scripts(self.page, SCRIPTS)
        self.charger(CORPUS["tables"])

    def charger(self, tables):
        self.page.evaluate(CHARGER_JS, tables_csv(tables))

    def ecrire(self, table, *lignes):
        self.page.evaluate(ECRIRE_JS, {"table": table, "lignes": list(lignes)})

    def chercher(self, texte, **options):
        return self.page.evaluate("([texte, options]) => Wiki.rechercher(texte, options)", [texte, options])

    def ids(self, reponse, portee=None):
        """Identifiants des résultats, dans l'ordre (d'une portée, ou de toutes à la suite)."""
        return [identifiant(r) for p in reponse["portees"] if portee in (None, p["portee"]) for r in p["resultats"]]

    def etat(self):
        return self.page.evaluate("Wiki.etatRecherche()")


# ---------------------------------------------------------------------------
# Requêtes du corpus
# ---------------------------------------------------------------------------

class TestRequetesDuCorpus(CasRecherche):

    def test_chaque_requete_du_corpus(self):
        for requete in CORPUS["requetes"]:
            with self.subTest(requete=requete["nom"]):
                options = {"equipementId": requete["equipementId"]} if requete.get("equipementId") else {}
                reponse = self.chercher(requete["texte"], **options)
                attendues = ["equipement", "modele", "parc"] if options else ["parc"]
                self.assertEqual([p["portee"] for p in reponse["portees"]], attendues)
                for portee, identifiants in requete.get("attendus", {}).items():
                    premiers = self.ids(reponse, portee)[:3]
                    for attendu in identifiants:
                        self.assertIn(attendu, premiers, "%s : %s absent des 3 premiers de « %s » (%s)"
                                      % (requete["texte"], attendu, portee, premiers))
                tous = self.ids(self.chercher(requete["texte"], limite=100, **options))
                for exclu in requete.get("jamais", []):
                    self.assertNotIn(exclu, tous)
                if requete.get("aucun"):
                    self.assertEqual(tous, [])

    def test_contenu_d_un_resultat_d_ot(self):
        ot = self.chercher("temperature")["portees"][0]["resultats"][0]
        self.assertEqual(ot["type"], "ot")
        self.assertEqual(ot["otId"], "OT-2026-0004")
        self.assertEqual((ot["equipementId"], ot["repere"], ot["date"]), ("EQ-0003", "CP-01", "2026-05-05"))
        self.assertEqual(ot["titre"], "CP-01 — Température de refoulement trop haute")
        self.assertEqual((ot["cause"], ot["remede"]), ("encrassement", "nettoyage"))
        self.assertEqual(ot["extrait"], "Radiateur encrassé : nettoyage à l'air comprimé, température revenue à 85 °C.")
        self.assertEqual(ot["mots"], ["temperature"])
        self.assertGreater(ot["score"], 0)


    def test_requete_et_mots_rendus(self):
        reponse = self.chercher("  Les FUITES du vérin  ")
        self.assertEqual(reponse["requete"], "Les FUITES du vérin")
        self.assertEqual(reponse["mots"], ["fuite", "verin"])
        self.assertEqual(reponse["equivalents"], ["fuit", "suintement", "suinte", "goutte"])
        reponse = self.chercher("ne démarre pas")
        self.assertEqual(reponse["mots"], ["demarre", "ne demarre pas"])
        self.assertEqual(reponse["equivalents"], ["arret", "stoppe"])


# ---------------------------------------------------------------------------
# Mots, lexique et mots vides
# ---------------------------------------------------------------------------

class TestMots(CasRecherche):

    def mots(self, texte):
        return self.page.evaluate("(texte) => Wiki.motsRecherche(texte)", texte)

    def test_mots_comparables(self):
        self.assertEqual(self.mots("Les Fuites d'HUILE à la Température élevée"), ["fuite", "huile", "temperature", "elevee"])
        # pluriel simple : « s » ou « x » final retiré au-delà de 3 lettres seulement
        self.assertEqual(self.mots("niveaux joints gaz bras cas vis"), ["niveau", "joint", "gaz", "bra", "cas", "vis"])
        # moins de 2 lettres et mots vides retirés ; chiffres gardés ; ligatures
        self.assertEqual(self.mots("a l' 7 bar 01 ; nœud ŒIL"), ["bar", "01", "noeud", "oeil"])
        self.assertEqual(self.mots("la presse fait ce bruit"), ["presse", "bruit"])
        # une expression du lexique compte en plus de ses mots
        self.assertEqual(self.mots("Il ne démarre pas, manque de pression"),
                         ["demarre", "manque", "pression", "ne demarre pas", "manque de pression"])
        self.assertEqual(self.mots(""), [])
        self.assertEqual(self.mots(None), [])

    def test_lexique_du_contrat_et_mots_vides(self):
        self.assertEqual(self.page.evaluate("Wiki.LEXIQUE"), LEXIQUE_CONTRAT)
        self.assertTrue(self.page.evaluate("Object.isFrozen(Wiki.LEXIQUE) && Wiki.LEXIQUE.every(Object.isFrozen)"))
        self.assertEqual(self.page.evaluate("Wiki.RECHERCHE"), {
            "k1": 1.2, "b": 0.75, "poidsEquivalent": 0.7, "limite": 10, "longueurExtrait": 160, "lettresMinimum": 2})
        vides = self.page.evaluate("Wiki.MOTS_VIDES")
        self.assertTrue(self.page.evaluate("Object.isFrozen(Wiki.MOTS_VIDES)"))
        for mot in ("la", "le", "les", "de", "ce", "fait", "ne", "pas", "et", "est"):
            self.assertIn(mot, vides)
        mots_du_lexique = {mot for groupe in LEXIQUE_CONTRAT for entree in groupe for mot in [entree] if " " not in entree}
        self.assertEqual(mots_du_lexique & set(vides), set())
        for mot in vides:  # écrits en forme comparable
            self.assertRegex(mot, r"^[a-z]{2,}$")

    def test_requete_sans_mot_utile_ne_construit_pas_l_index(self):
        for texte in ("", "   ", "la le de", "a b c", "!!!"):
            with self.subTest(texte=texte):
                reponse = self.chercher(texte, equipementId="EQ-0001")
                self.assertEqual(reponse["mots"], [])
                self.assertEqual(self.ids(reponse), [])
                self.assertEqual([p["portee"] for p in reponse["portees"]], ["equipement", "modele", "parc"])
        self.assertEqual(self.etat(), {"construit": False, "documents": 0, "constructions": 0})


# ---------------------------------------------------------------------------
# Classement BM25 (calcul Python indépendant)
# ---------------------------------------------------------------------------

MINI = {
    "OT-2026-0001": "pompe joint vanne",
    "OT-2026-0002": "pompe pompe moteur",
    "OT-2026-0003": "vanne moteur courroie tendeur",
    "OT-2026-0004": "joint",
    "OT-2026-0005": "claquement palier",
    "OT-2026-0006": "grincement grincement palier moteur courroie",
}


class TestClassement(CasRecherche):

    def setUp(self):
        super().setUp()
        ordres = [ot_clos(cle, "EQ-0001", texte, date_fin="2026-0%d-10 10:00" % (1 + rang))
                  for rang, (cle, texte) in enumerate(MINI.items())]
        self.charger({"equipements": CORPUS["tables"]["equipements"], "ordres_travail": ordres})

    def test_scores_bm25_egaux_au_calcul_python(self):
        for requete in ("pompe vanne", "moteur", "joint courroie", "claquement", "cognement", "bruit palier",
                        "grincement moteur tendeur"):
            with self.subTest(requete=requete):
                attendus = bm25(MINI, requete)
                resultats = self.chercher(requete, limite=50)["portees"][0]["resultats"]
                self.assertEqual(sorted(identifiant(r) for r in resultats), sorted(attendus))
                for resultat in resultats:
                    self.assertAlmostEqual(resultat["score"], attendus[identifiant(resultat)], places=9)
                scores = [r["score"] for r in resultats]
                self.assertEqual(scores, sorted(scores, reverse=True))

    def test_un_equivalent_compte_pour_0_7(self):
        direct = self.chercher("claquement")["portees"][0]["resultats"]
        equivalent = self.chercher("cognement")["portees"][0]["resultats"]
        score_direct = next(r["score"] for r in direct if r["otId"] == "OT-2026-0005")
        score_equivalent = next(r["score"] for r in equivalent if r["otId"] == "OT-2026-0005")
        self.assertAlmostEqual(score_equivalent / score_direct, 0.7, places=12)

    def test_egalite_de_score_le_plus_recent_d_abord(self):
        jumeaux = [ot_clos("OT-2026-%04d" % numero, "EQ-0004", "Cognement du palier", date_fin=date)
                   for numero, date in ((101, "2026-03-01 10:00"), (102, "2026-09-01 10:00"), (103, "2026-06-01 10:00"))]
        self.ecrire("ordres_travail", *jumeaux)
        resultats = self.chercher("cognement")["portees"][0]["resultats"]
        egaux = [r for r in resultats if r["otId"] in ("OT-2026-0101", "OT-2026-0102", "OT-2026-0103")]
        self.assertEqual(len({r["score"] for r in egaux}), 1)
        self.assertEqual([r["otId"] for r in egaux], ["OT-2026-0102", "OT-2026-0103", "OT-2026-0101"])


# ---------------------------------------------------------------------------
# Portées
# ---------------------------------------------------------------------------

class TestPortees(CasRecherche):

    def test_ordre_et_exclusivite_des_portees(self):
        reponse = self.chercher("fuite pression bruit", equipementId="EQ-0001", limite=100)
        self.assertEqual([p["portee"] for p in reponse["portees"]], ["equipement", "modele", "parc"])
        self.assertEqual([p["libelle"] for p in reponse["portees"]],
                         ["Sur cet équipement", "Même marque et modèle (Schuler HP 250)", "Ailleurs dans le parc"])
        equipements = {p["portee"]: {r["equipementId"] for r in p["resultats"]} for p in reponse["portees"]}
        self.assertEqual(equipements["equipement"], {"EQ-0001"})
        self.assertEqual(equipements["modele"], {"EQ-0002"})                 # « SCHULER » / « HP250 »
        self.assertTrue(equipements["parc"])
        self.assertEqual(equipements["parc"] & {"EQ-0001", "EQ-0002"}, set())
        self.assertIn("EQ-0006", equipements["parc"])                        # même marque, autre modèle
        tous = self.ids(reponse)
        self.assertEqual(len(tous), len(set(tous)))                           # aucun doublon
        # Mêmes documents que la recherche sur tout le parc, répartis sans perte.
        self.assertEqual(sorted(tous), sorted(self.ids(self.chercher("fuite pression bruit", limite=100))))

    def test_sans_equipement_le_parc_seul(self):
        reponse = self.chercher("fuite")
        self.assertEqual([(p["portee"], p["libelle"]) for p in reponse["portees"]], [("parc", "Dans tout le parc")])
        self.assertIn("OT-2026-0001", self.ids(reponse))

    def test_jumelle_vue_depuis_l_autre_presse(self):
        reponse = self.chercher("grincement", equipementId="EQ-0002", limite=100)
        self.assertEqual(self.ids(reponse, "equipement"), ["OT-2026-0003"])   # claquement ; l'OT annulé, jamais
        self.assertEqual(self.ids(reponse, "modele"), ["OT-2026-0002"])
        self.assertEqual(reponse["portees"][1]["libelle"], "Même marque et modèle (SCHULER HP250)")

    def test_sans_marque_ni_modele_la_portee_modele_est_vide(self):
        reponse = self.chercher("contacteur remplacé", equipementId="EQ-0005", limite=100)
        self.assertEqual(reponse["portees"][1], {"portee": "modele", "libelle": "Même marque et modèle", "resultats": []})
        self.assertEqual(self.ids(reponse, "equipement")[0], "OT-2026-0007")
        self.assertTrue(self.ids(reponse, "parc"))

    def test_sans_jumeau_la_portee_modele_est_vide(self):
        reponse = self.chercher("vibrations", equipementId="EQ-0003", limite=100)
        self.assertEqual(reponse["portees"][1], {"portee": "modele", "libelle": "Même marque et modèle", "resultats": []})
        self.assertEqual(self.ids(reponse, "equipement"), ["OT-2026-0009"])

    def test_equipement_inconnu(self):
        reponse = self.chercher("fuite", equipementId="EQ-9999", limite=100)
        self.assertEqual([len(p["resultats"]) for p in reponse["portees"][:2]], [0, 0])
        self.assertEqual(sorted(self.ids(reponse, "parc")), sorted(self.ids(self.chercher("fuite", limite=100))))

    def test_limite_par_portee(self):
        nouveaux = [ot_clos("OT-2026-%04d" % (200 + n), "EQ-0004", "PO-01 — Cognement n° %d" % n,
                            date_fin="2026-09-%02d 10:00" % (1 + n)) for n in range(12)]
        nouveaux += [ot_clos("OT-2026-%04d" % (300 + n), "EQ-0003", "CP-01 — Cognement n° %d" % n) for n in range(4)]
        self.ecrire("ordres_travail", *nouveaux)
        self.assertEqual(len(self.ids(self.chercher("cognement"))), 10)
        self.assertEqual(len(self.ids(self.chercher("cognement", limite=3))), 3)
        for limite in (0, -2, "abc", 1.5, None):
            with self.subTest(limite=limite):
                self.assertEqual(len(self.ids(self.chercher("cognement", limite=limite))), 10)
        reponse = self.chercher("cognement", equipementId="EQ-0003", limite=2)
        self.assertEqual([len(p["resultats"]) for p in reponse["portees"]], [2, 0, 2])


# ---------------------------------------------------------------------------
# Index : construction paresseuse et invalidation
# ---------------------------------------------------------------------------

class TestIndex(CasRecherche):

    def test_construit_a_la_premiere_recherche(self):
        self.assertEqual(self.etat(), {"construit": False, "documents": 0, "constructions": 0})
        self.chercher("fuite")
        clos = sum(1 for ot in CORPUS["tables"]["ordres_travail"] if ot["statut"].startswith("Clôturé"))
        self.assertEqual(self.etat(), {"construit": True, "documents": clos, "constructions": 1})   # un document par OT clôturé
        self.chercher("bruit", equipementId="EQ-0001")
        self.assertEqual(self.etat()["constructions"], 1)                      # réutilisé

    def test_index_refait_apres_un_nouvel_ot_cloture(self):
        self.assertEqual(self.ids(self.chercher("turbine")), [])
        self.ecrire("ordres_travail", ot_clos("OT-2026-0100", "EQ-0003", "CP-01 — Turbine encrassée",
                                              compte_rendu="Turbine nettoyée, essai concluant."))
        self.assertFalse(self.etat()["construit"])                             # oublié dès l'événement
        self.assertEqual(self.ids(self.chercher("turbine")), ["OT-2026-0100"])
        self.assertEqual(self.etat()["constructions"], 2)
        # Un OT en cours qui est clôturé devient trouvable.
        self.assertNotIn("OT-2026-0008", self.ids(self.chercher("alignement")))
        self.ecrire("ordres_travail", {"id": "OT-2026-0008", "statut": CLOS, "date_fin": "2026-10-21 10:00",
                                       "compte_rendu": "Alignement refait au comparateur."})
        self.assertEqual(self.ids(self.chercher("alignement")), ["OT-2026-0008"])

    def test_index_refait_pour_chaque_table_indexee(self):
        self.chercher("fuite")
        # demandes : nouvelle description de la DI d'origine
        self.ecrire("demandes", {"id": "DI-2026-0001", "description": "Tache d'huile sur le capot."})
        self.assertEqual(self.ids(self.chercher("capot")), ["OT-2026-0001"])
        # codes_defaillance : libellé changé
        self.ecrire("codes_defaillance", {"id": "CD-0010", "libelle": "contacteur grillé"})
        self.assertEqual(self.ids(self.chercher("grillé")), ["OT-2026-0007"])
        self.assertEqual(self.etat()["constructions"], 3)

    def test_une_autre_table_ne_refait_pas_l_index(self):
        self.chercher("fuite")
        self.ecrire("localisations", {"id": "LOC-0001", "libelle": "Atelier presses", "type": "atelier"})
        self.ecrire("equipements", {"id": "EQ-0004", "designation": "Pompe centrifuge (fuite)"})
        self.assertTrue(self.etat()["construit"])
        self.chercher("fuite")
        self.assertEqual(self.etat()["constructions"], 1)

    def test_index_refait_apres_une_relecture_sans_evenement(self):
        self.assertIn("OT-2026-0001", self.ids(self.chercher("fuite")))
        # Donnees.initialiser + chargerTout n'émettent aucun événement : l'index le voit quand même.
        self.charger({"equipements": CORPUS["tables"]["equipements"],
                      "ordres_travail": [ot_clos("OT-2026-0500", "EQ-0004", "PO-01 — Fuite au presse-étoupe")]})
        self.assertEqual(self.ids(self.chercher("fuite")), ["OT-2026-0500"])
        self.assertEqual(self.etat()["constructions"], 2)


# ---------------------------------------------------------------------------
# Extrait et surlignage
# ---------------------------------------------------------------------------

SURLIGNER_JS = """([extrait, mots]) => {
  const fragment = Wiki.surligner(extrait, mots);
  const hote = document.createElement('div');
  hote.innerHTML = String(fragment);
  document.body.appendChild(hote);
  const rendu = {
    html: String(fragment), sur: UI.estSur(fragment), texte: hote.textContent,
    marques: Array.from(hote.querySelectorAll('mark')).map((m) => m.textContent),
    elements: Array.from(hote.querySelectorAll('*')).map((e) => e.tagName.toLowerCase()),
    piege: window.piege === undefined ? null : window.piege,
  };
  hote.remove();
  return rendu;
}"""


class TestExtraitEtSurlignage(CasRecherche):

    def surligner(self, extrait, mots):
        return self.page.evaluate(SURLIGNER_JS, [extrait, mots])

    def test_surligner_echappe_le_script_d_un_compte_rendu(self):
        resultat = self.chercher("graisseur")["portees"][0]["resultats"][0]
        self.assertEqual(resultat["otId"], "OT-2026-0006")
        self.assertIn("<script>alert('prevo')</script>", resultat["extrait"])   # texte brut
        rendu = self.surligner(resultat["extrait"], resultat["mots"])
        self.assertTrue(rendu["sur"])
        self.assertNotIn("<script", rendu["html"])
        self.assertIn("&lt;script&gt;alert(&#39;prevo&#39;)&lt;/script&gt;", rendu["html"])
        self.assertEqual(rendu["elements"], ["mark"])
        self.assertEqual(rendu["marques"], ["Graisseur"])
        self.assertEqual(rendu["texte"], resultat["extrait"])

    def test_surligner_n_insere_jamais_de_html_venu_des_donnees(self):
        piege = '<img src="x" onerror="window.piege=1"><b>fuite</b> & "guillemets"'
        rendu = self.surligner(piege, ["fuite"])
        self.assertEqual(rendu["elements"], ["mark"])
        self.assertEqual(rendu["marques"], ["fuite"])
        self.assertEqual(rendu["texte"], piege)
        self.assertIsNone(rendu["piege"])
        # Un « mot » piégé ne sort pas non plus de son <mark>.
        rendu = self.surligner("a <mark>b</mark> fuite", ["<mark>"])
        self.assertEqual(rendu["elements"], ["mark", "mark"])
        self.assertEqual(rendu["marques"], ["mark", "mark"])
        self.assertEqual(rendu["texte"], "a <mark>b</mark> fuite")

    def test_surligner_accents_pluriels_expressions_et_mots_vides(self):
        self.assertEqual(self.surligner("Température trop haute, températures relevées", ["temperature"])["marques"],
                         ["Température", "températures"])
        self.assertEqual(self.surligner("Fuites et fuite, FUITE", ["Fuites"])["marques"], ["Fuites", "fuite", "FUITE"])
        self.assertEqual(self.surligner("Le convoyeur ne démarre pas du tout", ["ne demarre pas"])["marques"],
                         ["ne démarre pas"])
        self.assertEqual(self.surligner("Il ne démarre plus", ["ne demarre pas"])["marques"], [])
        self.assertEqual(self.surligner("la presse et la pompe", ["la", "et"])["marques"], [])
        self.assertEqual(self.surligner("", ["fuite"])["html"], "")
        self.assertEqual(self.surligner(None, ["fuite"])["html"], "")

    def test_extrait_autour_du_premier_mot_trouve(self):
        debut = "Démontage complet du groupe, contrôle des fixations, du serrage des bornes et de l'état des câbles. " * 3
        compte_rendu = debut + "Roulement côté accouplement grippé, remplacé. " + "Essai en marche concluant sur deux heures. " * 4
        self.ecrire("ordres_travail", ot_clos("OT-2026-0400", "EQ-0004", "PO-01 — Dépannage", compte_rendu=compte_rendu))
        resultat = self.chercher("roulement")["portees"][0]["resultats"][0]
        self.assertEqual(resultat["otId"], "OT-2026-0400")
        extrait = resultat["extrait"]
        self.assertLessEqual(len(extrait), 160)
        self.assertTrue(extrait.startswith("…") and extrait.endswith("…"), extrait)
        self.assertIn("Roulement côté accouplement grippé", extrait)
        self.assertLess(extrait.index("Roulement"), 60)                      # le mot vient tôt dans l'extrait
        self.assertIn(extrait.strip("…"), " ".join(compte_rendu.split()))    # un morceau du texte, coupé aux espaces
        self.assertEqual(self.surligner(extrait, resultat["mots"])["marques"], ["Roulement"])

    def test_extrait_sans_mot_dans_le_corps_et_extrait_de_la_di(self):
        # Mot trouvé seulement dans le titre : début du compte rendu.
        resultat = self.chercher("refoulement")["portees"][0]["resultats"][0]
        self.assertEqual(resultat["extrait"], "Radiateur encrassé : nettoyage à l'air comprimé, température revenue à 85 °C.")
        # Mot trouvé seulement dans la DI d'origine : l'extrait vient de la DI.
        resultat = self.chercher("bouton")["portees"][0]["resultats"][0]
        self.assertEqual(resultat["extrait"], "Bouton marche sans effet depuis ce matin.")
        # Expression trouvée : extrait autour d'elle.
        resultat = self.chercher("arrêt")["portees"][0]["resultats"][0]
        self.assertEqual(resultat["otId"], "OT-2026-0007")
        self.assertEqual(self.surligner(resultat["extrait"], resultat["mots"])["marques"], ["ne démarre pas"])

    def test_extraits_du_corpus_au_plus_160_caracteres(self):
        for requete in CORPUS["requetes"]:
            for portee in self.chercher(requete["texte"], limite=100)["portees"]:
                for resultat in portee["resultats"]:
                    with self.subTest(requete=requete["texte"], resultat=identifiant(resultat)):
                        self.assertLessEqual(len(resultat["extrait"]), 160)
                        self.assertTrue(resultat["mots"])


# ---------------------------------------------------------------------------
# Aucun appel réseau
# ---------------------------------------------------------------------------

class TestReseau(CasRecherche):

    def test_aucune_requete_reseau_pendant_les_recherches(self):
        self.page.evaluate("""() => {
          window.appelsReseau = [];
          const interdit = (nom) => function () { window.appelsReseau.push(nom); throw new Error('réseau interdit : ' + nom); };
          window.fetch = interdit('fetch');
          XMLHttpRequest.prototype.open = interdit('XMLHttpRequest');
          navigator.sendBeacon = interdit('sendBeacon');
          window.WebSocket = interdit('WebSocket');
          window.EventSource = interdit('EventSource');
        }""")
        requetes_avant = len(self.requetes_reseau)
        ressources_avant = self.page.evaluate("performance.getEntriesByType('resource').length")
        nombre = self.page.evaluate("""(requetes) => {
          let rendus = 0;
          requetes.forEach((requete) => {
            [null, 'EQ-0001', 'EQ-0004', 'EQ-0005'].forEach((equipementId) => {
              Wiki.rechercher(requete, { equipementId }).portees.forEach((portee) => portee.resultats.forEach((r) => {
                const hote = document.createElement('div');
                hote.innerHTML = String(Wiki.surligner(r.extrait, r.mots));
                document.body.appendChild(hote);
                rendus += 1;
              }));
            });
          });
          return rendus;
        }""", [r["texte"] for r in CORPUS["requetes"]])
        self.assertGreater(nombre, 50)
        self.assertEqual(self.requetes_reseau[requetes_avant:], [])
        self.assertEqual(self.page.evaluate("window.appelsReseau"), [])
        self.assertEqual(self.page.evaluate("performance.getEntriesByType('resource').length"), ressources_avant)


# ---------------------------------------------------------------------------
# Mesure indicative (la vraie mesure D101 est faite par test_performance.py sur le jeu de charge)
# ---------------------------------------------------------------------------

COMPOSANTS = ["roulement", "joint", "courroie", "moteur", "vérin", "flexible", "contacteur", "capteur", "électrovanne",
              "palier", "garniture", "filtre", "réducteur", "pignon", "chaîne", "accouplement", "ventilateur",
              "carte électronique", "fusible", "disjoncteur", "purgeur", "radiateur", "amortisseur", "glissière"]
SYMPTOMES = ["Fuite d'huile", "Bruit anormal", "Grincement", "Vibrations", "Température élevée", "Ne démarre pas",
             "Arrêt intempestif", "Manque de pression", "Claquement", "Surchauffe", "Blocage", "Défaut de cote"]
ETATS = ["usé", "détérioré", "desserré", "encrassé", "grippé", "cassé", "hors service", "fissuré", "colmaté"]
ACTIONS = ["remplacé", "resserré", "nettoyé", "graissé", "réglé", "réparé", "changé"]
PHRASES = ["Contrôle des fixations et du serrage des bornes.", "Relevé d'intensité dans la plage nominale.",
           "Remise en service après un essai de 30 minutes.", "Essai en marche concluant.",
           "Pièce commandée en urgence, montée le lendemain.", "Nettoyage de la zone et contrôle visuel des abords.",
           "Mesure des jeux conforme à la notice du constructeur.", "Production prévenue, redémarrage sans défaut."]
MARQUES = ["Schuler", "Atlas Copco", "Grundfos", "SEW", "Siemens", "Festo", "KSB", "Bosch Rexroth", "Trumpf", "Fanuc"]


def jeu_de_charge(equipements=500, ordres=5000, graine=98):
    """Équipements et OT fabriqués (textes de dépannage réalistes), 85 % clôturés, une DI sur trois."""
    hasard = random.Random(graine)
    lignes_eq = [{"id": "EQ-%04d" % n, "repere": "M-%03d" % n, "designation": "Machine %d" % n,
                  "marque": hasard.choice(MARQUES), "modele": "T%d" % hasard.randint(1, 6), "actif": "1"}
                 for n in range(1, equipements + 1)]
    lignes_ot, lignes_di = [], []
    for n in range(1, ordres + 1):
        symptome, composant = hasard.choice(SYMPTOMES), hasard.choice(COMPOSANTS)
        numero_equipement = hasard.randint(1, equipements)
        equipement = "EQ-%04d" % numero_equipement
        jour = "2026-%02d-%02d" % (hasard.randint(1, 9), hasard.randint(1, 28))
        identifiant_ot = "OT-2026-%05d" % n
        compte_rendu = "%s %s : %s. %s %s" % (composant.capitalize(), hasard.choice(ETATS), hasard.choice(ACTIONS),
                                              " ".join(hasard.sample(PHRASES, 3)), hasard.choice(PHRASES))
        ligne = ot_clos(identifiant_ot, equipement, "%s — %s du %s" % (lignes_eq[numero_equipement - 1]["repere"], symptome, composant),
                        date_fin=jour + " 10:00", compte_rendu=compte_rendu,
                        travail_a_faire="Rechercher l'origine : %s. Contrôler le %s." % (symptome.lower(), composant))
        if hasard.random() < 0.15:
            ligne.update(statut="En cours", date_fin="", compte_rendu="")
        if n % 3 == 0:
            identifiant_di = "DI-2026-%05d" % n
            ligne["di_id"] = identifiant_di
            lignes_di.append({"id": identifiant_di, "date_heure": jour + " 07:30", "equipement_id": equipement,
                              "symptome": "%s sur la machine" % symptome, "impact": "dégradé",
                              "description": "Constaté au démarrage du poste, %s probablement en cause." % composant,
                              "statut": "Acceptée", "ot_id": identifiant_ot})
        lignes_ot.append(ligne)
    return {"equipements": lignes_eq, "ordres_travail": lignes_ot, "demandes": lignes_di,
            "codes_defaillance": CORPUS["tables"]["codes_defaillance"]}


MESURER_JS = """(requetes) => {
  const debut = performance.now();
  const premiere = Wiki.rechercher(requetes[0], { equipementId: 'EQ-0001' });
  const dureePremiere = performance.now() - debut;
  const durees = requetes.slice(1).map((requete) => {
    const depart = performance.now();
    Wiki.rechercher(requete, { equipementId: 'EQ-0001' });
    return performance.now() - depart;
  });
  return { dureePremiere, durees, etat: Wiki.etatRecherche(),
           resultats: premiere.portees.reduce((total, p) => total + p.resultats.length, 0) };
}"""


class TestMesureIndicative(CasRecherche):

    def test_5000_ot_mesure_indicative(self):
        tables = jeu_de_charge()
        self.charger(tables)
        requetes = ["fuite d'huile au vérin", "la presse fait ce bruit", "température moteur", "ne démarre pas",
                    "vibrations palier", "courroie cassée", "manque de pression", "grincement glissière",
                    "contacteur hors service", "roulement grippé remplacé", "filtre colmaté"]
        mesure = self.page.evaluate(MESURER_JS, requetes)
        clos = sum(1 for ot in tables["ordres_travail"] if ot["statut"] == CLOS)
        self.assertEqual(mesure["etat"], {"construit": True, "documents": clos, "constructions": 1})
        self.assertGreater(mesure["resultats"], 0)
        mediane = statistics.median(mesure["durees"])
        sys.stderr.write("\n  [mesure indicative] %d OT clôturés : première recherche (index compris) %.0f ms ; "
                         "suivantes : médiane %.1f ms, maximum %.1f ms\n"
                         % (clos, mesure["dureePremiere"], mediane, max(mesure["durees"])))
        # Indicatif : budget D101 de 300 ms par recherche ; large marge pour la première (index construit).
        self.assertLess(mediane, 300)
        self.assertLess(mesure["dureePremiere"], 3000)


if __name__ == "__main__":
    unittest.main()
