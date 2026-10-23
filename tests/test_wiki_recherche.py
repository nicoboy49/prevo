"""Recherche sans IA du wiki de maintenance (lot 6, tâches T98 et T116, ARCHITECTURE.md §20.8 ; décision D99 a).

Les données sont un CORPUS D'ESSAI écrit à la main (tests/fixtures/wiki/corpus.json : équipements dont deux
de même marque et modèle, OT clôturés et non clôturés, DI d'origine et DI regroupée, codes, astuces d'OT, un
article et des pages du wiki — actives, archivée, sans texte) chargé dans StockageDemo, page file:// avec les
seuls scripts utiles.

Couvert :
    - chaque requête du corpus : ses OT ou pages attendus parmi les 3 premiers de leur portée, les
      « jamais » absents de toutes les portées, « aucun » sans aucun résultat (lexique, pluriels, accents,
      majuscules, mots vides, expressions, OT non clôturés, DI d'origine ; T116 : mot présent seulement dans une
      astuce, astuce d'un OT en cours jamais trouvée, mot présent seulement dans une page active, page archivée
      et page sans texte jamais trouvées, citations [OT-…] et rubriques « ## » non indexées) ;
    - résultat d'une page : type « page », pageId, lien canonique (EQ-…, ART-… ou WP-…, égal à Wiki.page(pageId).id),
      titre de Wiki.page, équipement, repère, date (valide_le, sinon modifie_le), extrait sans balisage ;
      portées d'une page (équipement, jumeau, parc) ;
    - mots comparables (Wiki.motsRecherche), Wiki.LEXIQUE (groupes du contrat, figé), Wiki.MOTS_VIDES ;
    - classement : scores BM25 égaux à un CALCUL PYTHON INDÉPENDANT (k1 = 1,2, b = 0,75, poids 0,7 d'un
      équivalent du lexique), sur des OT, puis sur des OT avec astuce et des pages (balisage retiré par Python),
      égalité de score départagée par la date ;
    - portées : ordre équipement → même marque et modèle → parc, un résultat dans une seule portée,
      jumeaux comparés sans casse ni espaces, même marque mais autre modèle = parc, sans marque = portée
      « modèle » vide, sans équipement = parc seul, limite par portée ;
    - index : construit à la première recherche (un document par OT clôturé et par page active avec texte),
      refait après une écriture dans chacune des quatre tables indexées (Donnees.modifier ; wiki_pages : texte
      ajouté, page archivée, nombre de constructions) et après une relecture sans événement, pas refait pour
      une autre table ;
    - extrait (160 caractères au plus, autour du premier mot trouvé) et Wiki.surligner (<mark>, tout le
      reste échappé : le <script> d'un compte rendu reste du texte) ;
    - aucune requête réseau pendant les recherches ;
    - mesure indicative sur 5 000 OT fabriqués (la vraie mesure, D101, est celle de test_performance.py) ;
    - entités par leur nom (refonte 2, §20.12, T136 : Wiki.chercherEntites, recherche de l'accueil) sur le corpus et deux
      techniciens : chaque requête égale à un CALCUL PYTHON INDÉPENDANT pour les trois profils (préfixe de mot, accents,
      pluriels, mots vides, codes et références ; ni technicien ni intervention pour le demandeur, profil par défaut le
      plus restreint), réponses écrites à la main, ligne de détail = champs de l'élément de Wiki.listeEntites, entrées
      refaites quand une table change (écriture ou relecture), aucune requête réseau ;
    - entités, relecture de T136 (D101) : sur la démo, le corpus et la base d'essai de test_wiki_entites.py, pour les trois
      profils, résultats INCHANGÉS (égaux à Wiki.listeEntites filtrée par la règle des mots, ordre et détail compris) ; les
      entrées ne lisent que les tables des noms (une écriture dans ot_temps, habilitations ou mouvements_stock ne les
      refait pas ; chaque autre table ne refait que les types qui la lisent) ; ligne de détail calculée à sa première
      lecture seulement ; sur le jeu de charge (500 équipements, 5 000 OT, outils/generer_demo.py), une recherche après
      une écriture dans ot_temps en moins de 300 ms (D101), première recherche mesurée et affichée.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_wiki_recherche.py" -v
"""
import csv
import io
import json
import math
import random
import re
import statistics
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path

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
    "js/modules/wiki-calculs.js",          # Wiki.page : lien canonique et titre d'une page (comparés aux résultats)
    "js/modules/wiki-entites.js",
    "js/modules/wiki-recherche.js",
]
FICHIER_CORPUS = RACINE / "tests" / "fixtures" / "wiki" / "corpus.json"
CORPUS = json.loads(FICHIER_CORPUS.read_text(encoding="utf-8"))

# Contrat §20.8 (copie indépendante du code) : groupes du lexique, poids d'un équivalent, BM25.
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
    """Identifiant d'un résultat : l'OT-… d'un OT, le WP-… d'une page."""
    return resultat["otId"] if resultat["type"] == "ot" else resultat["pageId"]


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


def texte_de_page(titre, balisage):
    """Texte indexé d'une page, refait ici sans le code : le titre, puis chaque ligne du balisage qui n'est pas
    une rubrique (« ## … »), sans la marque « - », sans les citations [OT-…], les liens [[titre]] gardés comme texte."""
    lignes = [titre]
    for ligne in balisage.splitlines():
        if ligne.lstrip().startswith("##"):
            continue
        ligne = re.sub(r"^\s*-\s+", "", ligne)
        ligne = re.sub(r"\[OT-\d{4}-\d{4,}\]", " ", ligne)
        lignes.append(re.sub(r"\[\[([^\[\]]+)\]\]", r"\1", ligne))
    return " ".join(" ".join(lignes).split())


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

    SCRIPTS = SCRIPTS

    def setUp(self):
        super().setUp()
        self.requetes_reseau = []
        self.page.on("request", lambda requete: self.requetes_reseau.append(requete.url))
        charger_scripts(self.page, self.SCRIPTS)
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

    def test_contenu_d_un_resultat_de_page(self):
        page = self.chercher("manomètre")["portees"][0]["resultats"][0]
        self.assertEqual(list(page), ["type", "pageId", "lien", "titre", "equipementId", "repere", "date", "cause",
                                      "remede", "extrait", "mots", "score"])
        self.assertEqual((page["type"], page["pageId"], page["lien"]), ("page", "WP-0001", "EQ-0001"))
        self.assertEqual(page["titre"], "PR-01 — Presse hydraulique 250 t")
        self.assertEqual((page["equipementId"], page["repere"], page["date"]), ("EQ-0001", "PR-01", "2026-09-15"))
        self.assertEqual((page["cause"], page["remede"]), ("", ""))
        # Extrait tiré des phrases : ni marque « - », ni citation, ni rubrique.
        self.assertEqual(page["extrait"], "Lire le manomètre du circuit principal avant chaque relance")
        self.assertEqual(page["mots"], ["manometre"])
        self.assertGreater(page["score"], 0)
        # Lien [[titre]] gardé comme texte dans l'extrait.
        page = self.chercher("magasin")["portees"][0]["resultats"][0]
        self.assertEqual(page["extrait"], "Garder un Joint de tige 25 mm d'avance au magasin")

    def test_lien_canonique_et_titre_de_chaque_page_comme_wiki_page(self):
        # mot présent seulement dans la page → (pageId, lien, titre, equipementId, repère, date)
        attendus = {
            "manomètre": ("WP-0001", "EQ-0001", "PR-01 — Presse hydraulique 250 t", "EQ-0001", "PR-01", "2026-09-15"),
            "sertisseuse": ("WP-0002", "WP-0002", "Changer un flexible hydraulique", "EQ-0002", "PR-02", "2026-09-20"),
            "carbure": ("WP-0003", "WP-0003", "Usure de la garniture mécanique", "", "", "2026-08-01"),
            "polir": ("WP-0006", "ART-0001", "Joint de tige 25 mm", "", "", "2026-09-16"),
        }
        for mot, (page_id, lien, titre, equipement, repere, date) in attendus.items():
            with self.subTest(mot=mot):
                resultats = self.chercher(mot, limite=100)["portees"][0]["resultats"]
                self.assertEqual([identifiant(r) for r in resultats], [page_id])
                page = resultats[0]
                self.assertEqual((page["type"], page["lien"], page["titre"]), ("page", lien, titre))
                self.assertEqual((page["equipementId"], page["repere"], page["date"]), (equipement, repere, date))
                calculee = self.page.evaluate("(id) => { const p = Wiki.page(id); return [p.id, p.titre]; }", page_id)
                self.assertEqual(calculee, [lien, titre])                    # même règle que Wiki.page

    def test_portees_d_une_page(self):
        # Page de PR-01 : sur l'équipement depuis PR-01, « modèle » depuis sa jumelle PR-02, parc ailleurs.
        for equipement, portee in (("EQ-0001", "equipement"), ("EQ-0002", "modele"), ("EQ-0003", "parc")):
            with self.subTest(equipement=equipement):
                self.assertEqual(self.ids(self.chercher("manomètre", equipementId=equipement), portee), ["WP-0001"])
        # Savoir-faire rattaché à PR-02 : « modèle » vu de PR-01 ; page sans équipement : toujours le parc.
        self.assertEqual(self.ids(self.chercher("sertisseuse", equipementId="EQ-0001"), "modele"), ["WP-0002"])
        self.assertEqual(self.ids(self.chercher("sertisseuse", equipementId="EQ-0002"), "equipement"), ["WP-0002"])
        for equipement in ("EQ-0001", "EQ-0004"):
            reponse = self.chercher("carbure", equipementId=equipement)
            self.assertEqual([self.ids(reponse, p) for p in ("equipement", "modele", "parc")], [[], [], ["WP-0003"]])
        self.assertEqual(self.ids(self.chercher("polir", equipementId="EQ-0001"), "parc"), ["WP-0006"])

    def test_astuce_d_un_ot_cloture_indexee_et_dans_l_extrait(self):
        resultat = self.chercher("extracteur")["portees"][0]["resultats"][0]
        self.assertEqual((resultat["type"], resultat["otId"]), ("ot", "OT-2026-0005"))
        self.assertEqual(resultat["extrait"], "Prévoir l'extracteur de chemise : la garniture colle souvent à l'arbre.")
        # Un mot du compte rendu ET de l'astuce : l'extrait vient du compte rendu (premier texte du corps).
        resultat = self.chercher("glissières")["portees"][0]["resultats"][0]
        self.assertEqual(resultat["otId"], "OT-2026-0002")
        self.assertTrue(resultat["extrait"].startswith("Glissières sèches"), resultat["extrait"])


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


# OT clôturés (titre, astuce) et pages du wiki (statut, titre, balisage) : mots simples, comme MINI.
MINI_ASTUCES = {
    "OT-2026-0001": ("pompe joint", "vanne courroie"),
    "OT-2026-0002": ("moteur", "joint joint palier"),
    "OT-2026-0003": ("courroie tendeur", ""),
}
MINI_PAGES = {
    "WP-0001": ("active", "pompe moteur",
                "## Etapes\n- graisser palier [OT-2026-0001]\n- changer joint [[courroie tendeur]] [OT-2026-0002] [OT-2026-0003]"),
    "WP-0002": ("archivée", "vanne", "## Etapes\n- vanne vanne vanne [OT-2026-0001]"),
    "WP-0003": ("active", "palier", ""),
    "WP-0004": ("active", "claquement", "## Symptomes\n- claquement moteur [OT-2026-0002]\n\n- tendeur [OT-2026-0003]"),
}


class TestClassementAvecAstucesEtPages(CasRecherche):
    """Les astuces et les pages entrent dans le calcul BM25 : scores égaux au calcul Python indépendant."""

    def setUp(self):
        super().setUp()
        ordres = [ot_clos(cle, "EQ-0001", titre, date_fin="2026-0%d-10 10:00" % (1 + rang), astuce=astuce)
                  for rang, (cle, (titre, astuce)) in enumerate(MINI_ASTUCES.items())]
        pages = [{"id": cle, "type": "savoir-faire", "titre": titre, "texte": balisage, "statut": statut,
                  "valide_le": "2026-09-01 10:00"} for cle, (statut, titre, balisage) in MINI_PAGES.items()]
        self.charger({"equipements": CORPUS["tables"]["equipements"], "ordres_travail": ordres, "wiki_pages": pages})
        # Documents attendus : chaque OT (titre + astuce) ; chaque page active avec texte (titre + phrases).
        self.documents = {cle: titre + " " + astuce for cle, (titre, astuce) in MINI_ASTUCES.items()}
        self.documents.update({cle: texte_de_page(titre, balisage) for cle, (statut, titre, balisage) in MINI_PAGES.items()
                               if statut != "archivée" and balisage.strip()})

    def test_documents_indexes(self):
        self.chercher("pompe")
        self.assertEqual(sorted(self.documents), ["OT-2026-0001", "OT-2026-0002", "OT-2026-0003", "WP-0001", "WP-0004"])
        self.assertEqual(self.etat()["documents"], 5)
        self.assertEqual(self.documents["WP-0001"], "pompe moteur graisser palier changer joint courroie tendeur")

    def test_scores_bm25_egaux_au_calcul_python(self):
        for requete in ("joint", "vanne", "palier", "courroie tendeur", "moteur pompe", "cognement", "bruit palier",
                        "graisser joint", "etapes", "symptomes", "2026", "claquement tendeur"):
            with self.subTest(requete=requete):
                attendus = bm25(self.documents, requete)
                resultats = self.chercher(requete, limite=50)["portees"][0]["resultats"]
                self.assertEqual(sorted(identifiant(r) for r in resultats), sorted(attendus))
                for resultat in resultats:
                    self.assertAlmostEqual(resultat["score"], attendus[identifiant(resultat)], places=9)
                scores = [r["score"] for r in resultats]
                self.assertEqual(scores, sorted(scores, reverse=True))


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
        pages = sum(1 for page in CORPUS["tables"]["wiki_pages"]
                    if page["statut"] != "archivée" and valeur_texte(page["texte"]).strip())
        self.assertEqual(pages, 4)                                              # WP-0004 archivée, WP-0005 sans texte
        # Un document par OT clôturé et par page active qui a un texte.
        self.assertEqual(self.etat(), {"construit": True, "documents": clos + pages, "constructions": 1})
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
        # ordres_travail : une astuce posée sur un OT clôturé
        self.ecrire("ordres_travail", {"id": "OT-2026-0009", "astuce": "Repérer les masses d'équilibrage au feutre."})
        self.assertEqual(self.ids(self.chercher("feutre")), ["OT-2026-0009"])
        self.assertEqual(self.etat()["constructions"], 4)

    def test_index_refait_quand_wiki_pages_change(self):
        self.assertEqual(self.ids(self.chercher("cames")), [])
        self.assertEqual(self.etat()["constructions"], 1)
        # La page active sans texte reçoit un texte validé : elle entre dans l'index.
        self.ecrire("wiki_pages", {"id": "WP-0005", "texte": "## Causes\n- Cames du convoyeur desserrées [OT-2026-0007]",
                                   "valide_le": "2026-10-01 09:00"})
        self.assertFalse(self.etat()["construit"])                             # oublié dès l'événement
        self.assertEqual(self.ids(self.chercher("cames")), ["WP-0005"])
        self.assertEqual(self.etat()["constructions"], 2)
        # Texte d'une page changé : l'ancien mot n'est plus trouvé, le nouveau l'est.
        self.ecrire("wiki_pages", {"id": "WP-0003", "texte": "## Causes\n- Garniture en céramique usée [OT-2026-0005]"})
        self.assertEqual(self.ids(self.chercher("carbure")), [])
        self.assertEqual(self.ids(self.chercher("céramique")), ["WP-0003"])
        self.assertEqual(self.etat()["constructions"], 3)
        # Page archivée : elle sort de l'index ; nouvelle page active : elle y entre.
        self.ecrire("wiki_pages", {"id": "WP-0005", "statut": "archivée"},
                    {"id": "WP-0007", "type": "mode", "titre": "Desserrage des cames", "statut": "active",
                     "texte": "## Remèdes\n- Freiner les vis au frein-filet [OT-2026-0007]", "modifie_le": "2026-10-02 08:00"})
        self.assertEqual(self.ids(self.chercher("cames")), ["WP-0007"])
        self.assertEqual(self.etat()["constructions"], 4)

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


# ---------------------------------------------------------------------------
# Entités par leur nom (refonte 2, §20.12, D113 et D114 ; tâche T136 : Wiki.chercherEntites, recherche de l'accueil)
# ---------------------------------------------------------------------------

# Deux techniciens ajoutés au corpus : l'un porte un nom qui commence comme une machine (« Pompidou », « pomp… »).
TECHNICIENS_CORPUS = [
    {"id": "TEC-0001", "nom": "Pompidou", "prenom": "Julie", "metier": "Mécanicienne", "taux_horaire": "38",
     "capacite_h_semaine": "35", "actif": "1"},
    {"id": "TEC-0002", "nom": "Lefèvre", "prenom": "Marc", "metier": "Électricien", "taux_horaire": "40",
     "capacite_h_semaine": "35", "actif": "0"},
]
REQUETES_ENTITES = ["presse", "PR-01", "pr 02", "pompe", "pomp", "Pompes", "fuite", "FUITES", "joint", "JT-25", "jt",
                    "flexible", "hydrau", "ÉCHAUFFEMENT", "vibrations", "OT-2026-0012", "2026 0012", "julie", "lefevre",
                    "changer un flexible", "convoyeur à bande", "accumulateur", "zzz", "de la"]
CHERCHER_ENTITES_JS = """([texte, profil]) => Wiki.chercherEntites(texte, profil ? { profil } : {}).groupes.map((g) => ({
  type: g.type, liens: g.entites.map((e) => e.lien), titres: g.entites.map((e) => e.titre) }))"""


def mots_d_un_nom(texte):
    """Mots d'un nom, refaits ici : minuscules, sans accents, tout ce qui n'est ni lettre ni chiffre sépare."""
    sans = "".join(c for c in unicodedata.normalize("NFD", texte) if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", sans.replace("œ", "oe").replace("æ", "ae")).split()


def mots_de_la_requete(requete, mots_vides):
    """Mots d'une requête : ceux d'un nom, sans les mots vides ni ceux d'une lettre, pluriel simple retiré (§20.8)."""
    resultat = []
    for mot in mots_d_un_nom(requete):
        if len(mot) < 2 or mot in mots_vides:
            continue
        if len(mot) > 3 and mot[-1] in "sx":
            mot = mot[:-1]
        if mot not in resultat:
            resultat.append(mot)
    return resultat


# Ligne de détail d'une entité trouvée (relecture de T136, copie du contrat en tête de wiki-recherche.js) : les champs de
# l'élément de Wiki.listeEntites que l'accueil montre ; nom cherché de chaque type et titre montré.
CHAMPS_DETAIL = {
    "machine": ["equipementId", "titre", "lien", "lieu", "marqueModele"], "panne": ["id", "code", "titre", "cas", "machines", "lien"],
    "article": ["articleId", "titre", "lien", "reference", "emplacement"], "technicien": ["technicienId", "nom", "lien", "metier", "actif"],
    "savoir-faire": ["id", "titre", "rattachement", "mere", "lien"], "intervention": ["id", "titre", "statut", "date", "lien"],
}
NOMS_CHERCHES = {
    "machine": lambda e: [e["titre"]], "panne": lambda e: [e["titre"], e["code"]], "article": lambda e: [e["titre"], e["reference"]],
    "technicien": lambda e: [e["nom"]], "savoir-faire": lambda e: [e["titre"]], "intervention": lambda e: [e["id"], e["titre"]],
}
TYPES_ENTITES = ["machine", "panne", "article", "technicien", "savoir-faire", "intervention"]


def detail_attendu(type_, element):
    """Ligne de détail attendue : les champs du contrat, pris dans l'élément de Wiki.listeEntites."""
    return {champ: element[champ] for champ in CHAMPS_DETAIL[type_]}


def entites_attendues(tables, requete, profil, mots_vides):
    """Groupes attendus, calculés ici sur les tables du corpus : [(type, [lien])] ; interventions : ensemble des liens."""
    mots = mots_de_la_requete(requete, mots_vides)
    if not mots:
        return []

    def correspond(*noms):
        du_nom = mots_d_un_nom(" ".join(noms))
        return all(any(m.startswith(mot) for m in du_nom) for mot in mots)
    clos = ("Clôturé techniquement", "Clôturé administrativement")
    cas = {}
    for ot in tables["ordres_travail"]:
        if ot["type"].startswith("correctif") and ot["statut"] in clos and ot["symptome_code"]:
            cas[ot["symptome_code"]] = cas.get(ot["symptome_code"], 0) + 1
    libelles = {c["code"]: c["libelle"] for c in reversed(tables["codes_defaillance"]) if c["famille"] == "symptôme"}
    titre_machine = lambda e: " — ".join(x for x in (e["repere"], e["designation"]) if x)  # noqa: E731
    titre_article = lambda a: a.get("designation") or a.get("reference") or a["id"]       # noqa: E731
    nom = lambda t: (t["prenom"] + " " + t["nom"]).strip() or t["id"]                      # noqa: E731
    groupes = [
        ("machine", [e["id"] for e in sorted(tables["equipements"], key=lambda e: (titre_machine(e), e["id"]))
                     if correspond(titre_machine(e))]),
        ("panne", ["PANNE-" + code for code, _ in sorted(cas.items(), key=lambda e: (-e[1], e[0]))
                   if correspond(libelles.get(code, code), code)]),
        ("article", [a["id"] for a in sorted(tables["articles"], key=lambda a: (titre_article(a), a["id"]))
                     if correspond(titre_article(a), a.get("reference", ""))]),
        ("technicien", [t["id"] for t in sorted(tables.get("techniciens", []), key=lambda t: (nom(t), t["id"]))
                        if profil != "demandeur" and correspond(nom(t))]),
        ("savoir-faire", [p["id"] for p in sorted(tables["wiki_pages"], key=lambda p: (p["titre"], p["id"]))
                          if p["type"] == "savoir-faire" and p["statut"] != "archivée" and correspond(p["titre"])]),
        ("intervention", sorted(o["id"] for o in tables["ordres_travail"] if profil != "demandeur" and correspond(o["id"], o["titre"]))),
    ]
    return [(type_, liens) for type_, liens in groupes if liens]


class TestEntites(CasRecherche):

    SCRIPTS = SCRIPTS + ["js/modules/equipe-regles.js"]       # habilitations d'un technicien (Wiki.listeEntites)

    def setUp(self):
        super().setUp()
        self.tables = dict(CORPUS["tables"], techniciens=TECHNICIENS_CORPUS)
        self.charger(self.tables)

    def chercher_entites(self, texte, profil=None):
        return self.page.evaluate(CHERCHER_ENTITES_JS, [texte, profil])

    def test_chaque_requete_egale_au_calcul_python_pour_les_trois_profils(self):
        mots_vides = set(self.page.evaluate("Wiki.MOTS_VIDES"))
        trouves = 0
        for profil in ("demandeur", "technicien", "responsable"):
            for requete in REQUETES_ENTITES:
                with self.subTest(profil=profil, requete=requete):
                    lus = self.chercher_entites(requete, profil)
                    attendus = entites_attendues(self.tables, requete, profil, mots_vides)
                    obtenus = [(g["type"], sorted(g["liens"]) if g["type"] == "intervention" else g["liens"]) for g in lus]
                    self.assertEqual(obtenus, attendus)
                    # Interventions : dans l'ordre des listes (ouvertes en tête, puis de la plus récente)
                    for groupe in lus:
                        if groupe["type"] == "intervention":
                            self.assertEqual(groupe["liens"], self.page.evaluate("(ids) => Wiki.ordreInterventions(ids)", groupe["liens"]))
                    trouves += sum(len(g["liens"]) for g in lus)
        self.assertGreater(trouves, 60)

    def test_cas_attendus(self):
        """Quelques réponses écrites à la main (le calcul Python pourrait se tromper comme le code)."""
        groupes = lambda texte, profil="responsable": {g["type"]: g["liens"] for g in self.chercher_entites(texte, profil)}  # noqa: E731
        self.assertEqual(groupes("presse"), {"machine": ["EQ-0001", "EQ-0002", "EQ-0006"]})
        self.assertEqual(groupes("PR-01")["machine"], ["EQ-0001"])                     # ni PR-02, ni OT-2026-0010
        self.assertNotIn("OT-2026-0010", groupes("PR-01").get("intervention", []))
        # « pompes » : pluriel retiré ; l'OT en cours (OT-2026-0008) avant le clôturé (ordre des interventions)
        self.assertEqual(groupes("Pompes"), {"machine": ["EQ-0004"], "intervention": ["OT-2026-0008", "OT-2026-0006"]})
        self.assertEqual(groupes("pomp"), {"machine": ["EQ-0004"], "technicien": ["TEC-0001"],
                                           "intervention": ["OT-2026-0008", "OT-2026-0006"]})
        self.assertEqual(groupes("pomp", "demandeur"), {"machine": ["EQ-0004"]})        # ni technicien ni intervention
        self.assertEqual(groupes("FUITES")["panne"], ["PANNE-FUI"])                    # libellé du code symptôme
        self.assertEqual(groupes("FUI")["panne"], ["PANNE-FUI"])                       # son code
        self.assertEqual(groupes("ÉCHAUFFEMENT"), {"panne": ["PANNE-ECH"]})
        self.assertEqual(groupes("JT-25"), {"article": ["ART-0001"]})
        self.assertEqual(groupes("changer un flexible"), {"savoir-faire": ["WP-0002"]})
        self.assertEqual(groupes("accumulateur", "technicien"), {"intervention": ["OT-2026-0013"]})   # archivée : WP-0004 absente
        self.assertEqual(groupes("lefevre")["technicien"], ["TEC-0002"])               # inactif : toujours une page
        titres = {g["type"]: g["titres"] for g in self.chercher_entites("julie", "technicien")}
        self.assertEqual(titres, {"technicien": ["Julie Pompidou"]})

    def test_profil_par_defaut_le_plus_restreint(self):
        """Sans profil donné ni App : le demandeur (même règle que Wiki.entite)."""
        self.assertIsNone(self.page.evaluate("typeof App === 'undefined' ? null : App"))
        self.assertEqual([g["type"] for g in self.chercher_entites("pomp")], ["machine"])
        self.assertEqual([g["type"] for g in self.chercher_entites("pomp", "responsable")], ["machine", "technicien", "intervention"])

    def test_rien_sans_mot_utile(self):
        for texte in ("", "   ", "de la", "a", "- / !", None):
            with self.subTest(texte=texte):
                reponse = self.page.evaluate("(t) => Wiki.chercherEntites(t, { profil: 'responsable' })", texte)
                self.assertEqual((reponse["mots"], reponse["groupes"]), ([], []))

    def test_element_de_la_liste_et_lien_de_la_page(self):
        reponse = self.page.evaluate("Wiki.chercherEntites('fuite presse joint', { profil: 'responsable' })")
        self.assertEqual(reponse["groupes"], [])                     # chaque mot doit commencer un mot du nom
        machine = self.page.evaluate("""() => { const g = Wiki.chercherEntites('PR-03', { profil: 'technicien' }).groupes[0];
          const liste = Wiki.listeEntites('machine', { profil: 'technicien' }).flatMap((l) => l.machines);
          return [g.entites[0], liste.find((m) => m.equipementId === 'EQ-0006')]; }""")
        # Ligne de détail : les champs de l'élément de la liste que l'accueil montre, mêmes valeurs (relecture de T136)
        self.assertEqual(machine[0]["element"], detail_attendu("machine", machine[1]))
        self.assertEqual(machine[0]["element"]["marqueModele"], "Schuler HP 400")
        self.assertEqual((machine[0]["type"], machine[0]["lien"], machine[0]["titre"]), ("machine", "EQ-0006", "PR-03 — Presse plieuse"))
        article = self.page.evaluate("Wiki.chercherEntites('joint de tige', { profil: 'demandeur' }).groupes[0].entites[0]")
        self.assertEqual((article["type"], article["lien"], article["element"]["reference"]), ("article", "ART-0001", "JT-25"))

    def test_entrees_refaites_quand_une_table_change(self):
        self.assertEqual(self.chercher_entites("rouleaux", "technicien"), [])
        self.ecrire("equipements", {"id": "EQ-0007", "repere": "CV-02", "designation": "Convoyeur à rouleaux", "actif": "1"})
        self.assertEqual([(g["type"], g["liens"]) for g in self.chercher_entites("rouleaux", "technicien")], [("machine", ["EQ-0007"])])
        # Une panne sans cas clôturé disparaît (OT-2026-0004 rouvert : son seul cas) ; un savoir-faire archivé aussi
        self.assertEqual(self.chercher_entites("ÉCHAUFFEMENT", "technicien"), [{"type": "panne", "liens": ["PANNE-ECH"], "titres": ["échauffement"]}])
        self.ecrire("ordres_travail", {"id": "OT-2026-0004", "statut": "En cours"})
        self.assertEqual(self.chercher_entites("ÉCHAUFFEMENT", "technicien"), [])
        self.ecrire("wiki_pages", {"id": "WP-0002", "statut": "archivée"})
        self.assertNotIn("savoir-faire", [g["type"] for g in self.chercher_entites("flexible", "technicien")])
        # Même résultat si Donnees relit les tables sans événement (nouveaux tableaux)
        self.charger(dict(self.tables, techniciens=TECHNICIENS_CORPUS[:1]))
        self.assertEqual([g["liens"] for g in self.chercher_entites("lefevre", "technicien")], [])

    def test_aucune_requete_reseau(self):
        self.page.evaluate("""() => { window.appelsReseau = [];
          const interdit = (nom) => function () { window.appelsReseau.push(nom); throw new Error('réseau interdit : ' + nom); };
          window.fetch = interdit('fetch'); XMLHttpRequest.prototype.open = interdit('XMLHttpRequest'); }""")
        avant = len(self.requetes_reseau)
        for profil in ("demandeur", "technicien", "responsable"):
            for requete in REQUETES_ENTITES:
                self.chercher_entites(requete, profil)
        self.assertEqual(self.requetes_reseau[avant:], [])
        self.assertEqual(self.page.evaluate("window.appelsReseau"), [])


# ---------------------------------------------------------------------------
# Entités, relecture de T136 (D101) : résultats inchangés, tables des noms seulement, détail à la lecture, jeu de charge
# ---------------------------------------------------------------------------

DOSSIER_DEMO = RACINE / "donnees" / "demo"
PROFILS = ("demandeur", "technicien", "responsable")

# Listes de Wiki.listeEntites d'un profil (machines à plat, sous-ensembles compris) : la référence des résultats d'avant.
LISTES_JS = """(profil) => {
  const aPlat = (machines) => machines.flatMap((m) => [m].concat(aPlat(m.sousEnsembles || [])));
  return Object.fromEntries(TYPES.map((type) => {
    const liste = Wiki.listeEntites(type, { profil });
    return [type, liste && (type === 'machine' ? aPlat(liste.flatMap((g) => g.machines)) : liste)];
  }));
}""".replace("TYPES", json.dumps(TYPES_ENTITES))
CHERCHER_TOUT_JS = """([requetes, profil]) => requetes.map((requete) => Wiki.chercherEntites(requete, { profil }).groupes.map((g) => ({
  type: g.type, liens: g.entites.map((e) => e.lien), titres: g.entites.map((e) => e.titre), elements: g.entites.map((e) => e.element) })))"""
# Modifie un champ de la première ligne d'une table ; rend vrai si la table a bien été réécrite.
MODIFIER_PREMIERE_JS = """async ([table, champ, valeur]) => {
  const avant = Donnees.lignes(table);
  await Donnees.modifier(table, (lignes) => { lignes[0] = Object.assign({}, lignes[0], { [champ]: valeur }); return true; },
    { action: 'test de la recherche des entités' });
  return Donnees.lignes(table) !== avant;
}"""


def groupes_par_les_listes(listes, requete, mots_vides):
    """Groupes que rendait la recherche d'avant (listes de Wiki.listeEntites filtrées par la règle des mots, ici en Python)."""
    mots = mots_de_la_requete(requete, mots_vides)
    if not mots:
        return []
    groupes = []
    for type_ in TYPES_ENTITES:
        elements = listes[type_]
        if elements is None:                                     # type que le profil ne voit pas
            continue
        if type_ == "machine":
            elements = sorted(elements, key=lambda e: (e["titre"], e["equipementId"]))
        trouves = [e for e in elements
                   if all(any(m.startswith(mot) for m in mots_d_un_nom(" ".join(NOMS_CHERCHES[type_](e)))) for mot in mots)]
        if trouves:
            groupes.append({"type": type_, "liens": [e["lien"] for e in trouves],
                            "titres": [e["nom"] if type_ == "technicien" else e["titre"] for e in trouves],
                            "elements": [detail_attendu(type_, e) for e in trouves]})
    return groupes


def requetes_des_noms(listes, nombre=220, graine=136):
    """Requêtes tirées des noms : chaque mot, son début (3 lettres), les deux premiers mots d'un nom ; plus quelques cas fixes."""
    requetes = set()
    for type_ in TYPES_ENTITES:
        for element in listes[type_] or []:
            mots = mots_d_un_nom(" ".join(NOMS_CHERCHES[type_](element)))
            requetes.update(mots)
            requetes.update(mot[:3] for mot in mots)
            if len(mots) > 1:
                requetes.add(" ".join(mots[:2]))
    choisies = random.Random(graine).sample(sorted(requetes), min(nombre, len(requetes)))
    return choisies + ["pompe", "2025", "2026", "ot", "de la", "zzz", "PR-01", "Fuites"]


class TestEntitesInchangees(CasRecherche):
    """Résultats de Wiki.chercherEntites égaux à ceux d'avant (listes de Wiki.listeEntites), ordre et détail compris."""

    SCRIPTS = SCRIPTS + ["js/modules/equipe-regles.js"]

    def verifier(self, types_couverts):
        mots_vides = set(self.page.evaluate("Wiki.MOTS_VIDES"))
        listes = {profil: self.page.evaluate(LISTES_JS, profil) for profil in PROFILS}
        requetes = requetes_des_noms(listes["responsable"])
        couverts, trouves = set(), 0
        for profil in PROFILS:
            obtenus = self.page.evaluate(CHERCHER_TOUT_JS, [requetes, profil])
            for requete, groupes in zip(requetes, obtenus):
                with self.subTest(profil=profil, requete=requete):
                    self.assertEqual(groupes, groupes_par_les_listes(listes[profil], requete, mots_vides))
                couverts.update(g["type"] for g in groupes)
                trouves += sum(len(g["liens"]) for g in groupes)
                if profil == "demandeur":
                    self.assertFalse({"technicien", "intervention"} & {g["type"] for g in groupes}, requete)
        self.assertEqual(couverts, set(types_couverts))
        self.assertGreater(trouves, 300)

    def test_demo(self):
        self.page.evaluate(CHARGER_JS, {f.stem: f.read_bytes().decode("utf-8-sig") for f in DOSSIER_DEMO.glob("*.csv")})
        self.verifier([t for t in TYPES_ENTITES if t != "savoir-faire"])          # le wiki de la démo est vide au socle

    def test_corpus(self):
        self.charger(dict(CORPUS["tables"], techniciens=TECHNICIENS_CORPUS))
        self.verifier(TYPES_ENTITES)

    def test_base_d_essai_des_entites(self):
        """Base d'essai de test_wiki_entites.py : sous-ensembles, cycle, parent inconnu, savoir-faire rattachés, sous-page, archivé."""
        from test_wiki_entites import BASE
        self.page.evaluate(CHARGER_JS, BASE)
        self.verifier(TYPES_ENTITES)


class TestEntitesTablesLues(CasRecherche):
    """Les entrées ne lisent que les tables des noms ; la ligne de détail n'est calculée qu'à sa lecture."""

    SCRIPTS = SCRIPTS + ["js/modules/equipe-regles.js"]

    def setUp(self):
        super().setUp()
        from test_wiki_entites import BASE
        self.page.evaluate(CHARGER_JS, BASE)

    def etat(self):
        return self.page.evaluate("Wiki.etatEntites()")

    def modifier(self, table, champ, valeur):
        self.assertTrue(self.page.evaluate(MODIFIER_PREMIERE_JS, [table, champ, valeur]), table)

    def test_seules_les_tables_des_noms_refont_les_entrees(self):
        self.page.evaluate("Wiki.chercherEntites('pompe', { profil: 'responsable' })")
        self.assertEqual(self.etat()["types"], TYPES_ENTITES)
        # Stock, heures pointées, habilitations, lieux, achats : aucune entrée refaite (D101, relecture de T136)
        for table, champ, valeur in [("ot_temps", "heures", "9.75"), ("habilitations", "date_echeance", "2031-01-01"),
                                     ("mouvements_stock", "quantite", "7"), ("localisations", "libelle", "Usine du bas"),
                                     ("achats", "quantite", "9")]:
            with self.subTest(table=table):
                avant = self.etat()["constructions"]
                self.modifier(table, champ, valeur)
                self.assertEqual(self.etat()["types"], TYPES_ENTITES)
                self.page.evaluate("Wiki.chercherEntites('pompe', { profil: 'responsable' })")
                self.assertEqual(self.etat()["constructions"], avant)
        # Chaque table des noms ne refait que les types qui la lisent
        for table, champ, valeur, refaits in [
                ("equipements", "designation", "Pompe B", ["machine", "savoir-faire"]),
                ("ordres_travail", "titre", "Fuite reprise", ["panne", "intervention"]),
                ("codes_defaillance", "libelle", "Fuite franche", ["panne"]),
                ("articles", "designation", "Roulement 6206", ["article", "savoir-faire"]),
                ("techniciens", "metier", "Chef d'équipe", ["technicien"]),
                ("wiki_pages", "titre", "PO-01 — Pompe B", ["savoir-faire"])]:
            with self.subTest(table=table):
                avant = self.etat()["constructions"]
                self.modifier(table, champ, valeur)
                self.assertEqual(self.etat()["types"], [t for t in TYPES_ENTITES if t not in refaits])
                self.page.evaluate("Wiki.chercherEntites('pompe', { profil: 'responsable' })")
                self.assertEqual(self.etat()["constructions"], avant + len(refaits))

    def test_detail_lu_frais_et_calcule_a_la_lecture(self):
        resultat = self.page.evaluate("""() => {
          const depart = Wiki.etatEntites().details;
          const reponse = Wiki.chercherEntites('2026', { profil: 'responsable' });
          const apresRecherche = Wiki.etatEntites().details;
          const interventions = reponse.groupes.find((g) => g.type === 'intervention').entites;
          interventions.slice(0, 6).forEach((e) => e.element);
          const apresSix = Wiki.etatEntites().details;
          interventions.slice(0, 6).forEach((e) => e.element);
          return { trouvees: interventions.length, recherche: apresRecherche - depart, six: apresSix - apresRecherche,
                   relues: Wiki.etatEntites().details - apresSix };
        }""")
        self.assertEqual(resultat, {"trouvees": 15, "recherche": 0, "six": 6, "relues": 0})
        # Le lieu d'une machine est lu à l'appel : une localisation renommée se voit sans refaire les entrées
        self.page.evaluate("Wiki.chercherEntites('PO-01', { profil: 'responsable' })")
        avant = self.etat()["constructions"]
        self.modifier("localisations", "libelle", "Usine du bas")
        element = self.page.evaluate("Wiki.chercherEntites('PO-01', { profil: 'responsable' }).groupes[0].entites[0].element")
        self.assertEqual((element["equipementId"], element["lieu"]), ("EQ-0001", "Usine du bas › Atelier A › Ligne 1"))
        self.assertEqual(self.etat()["constructions"], avant)


class TestEntitesJeuDeCharge(CasRecherche):
    """D101 sur le jeu de charge (500 équipements, 5 000 OT, outils/generer_demo.py comme test_wiki_entites.py)."""

    SCRIPTS = SCRIPTS + ["js/modules/equipe-regles.js"]

    def test_recherche_apres_une_ecriture_dans_ot_temps_sous_300_ms(self):
        with tempfile.TemporaryDirectory() as dossier:
            resultat = subprocess.run([sys.executable, str(RACINE / "outils" / "generer_demo.py"), "--volume", "500,5000",
                                       "--sortie", dossier, "--sans-js"], capture_output=True, cwd=RACINE)
            self.assertEqual(resultat.returncode, 0, resultat.stdout.decode("utf-8", "replace"))
            tables = {f.stem: f.read_bytes().decode("utf-8-sig") for f in Path(dossier).glob("*.csv")}
        self.page.evaluate(CHARGER_JS, tables)
        mesure = self.page.evaluate("""async () => {
          // Une recherche de l'accueil : les entités (chaque ligne de détail lue, comme l'écran), puis le plein texte.
          const chercher = (requete, profil) => {
            const t0 = performance.now();
            const entites = Wiki.chercherEntites(requete, { profil });
            entites.groupes.forEach((g) => g.entites.forEach((e) => e.element));
            const t1 = performance.now();
            Wiki.rechercher(requete, {});
            const t2 = performance.now();
            return { entites: t1 - t0, pleinTexte: t2 - t1, total: t2 - t0,
                     trouvees: entites.groupes.reduce((n, g) => n + g.entites.length, 0) };
          };
          const sortie = { volume: ['equipements', 'ordres_travail', 'ot_temps', 'habilitations', 'mouvements_stock']
            .map((t) => Donnees.lignes(t).length), premiere: chercher('pompe', 'responsable'), apres: {} };
          const champs = { ot_temps: ['heures', (v) => String((Number(v) || 1) + 0.25)],
            habilitations: ['date_echeance', () => '2031-01-01'], mouvements_stock: ['quantite', (v) => String((Number(v) || 1) + 1)] };
          for (const table of Object.keys(champs)) {
            const [champ, valeur] = champs[table];
            const avant = Wiki.etatEntites().constructions;
            const lignes = Donnees.lignes(table);
            await Donnees.modifier(table, (copie) => { copie[0] = Object.assign({}, copie[0], { [champ]: valeur(copie[0][champ]) }); return true; },
              { action: 'test de la recherche des entités' });
            sortie.apres[table] = Object.assign(chercher('roulement', 'responsable'), { ecrite: Donnees.lignes(table) !== lignes,
              refaites: Wiki.etatEntites().constructions - avant });
          }
          sortie.demandeur = chercher('courroie', 'demandeur');
          return sortie;
        }""")
        self.assertEqual(mesure["volume"][:2], [500, 5000])
        premiere = mesure["premiere"]
        sys.stderr.write("\n  [D101, jeu de charge] première recherche « pompe » : entités %.0f ms (%d trouvées), plein texte "
                         "(index construit) %.0f ms, total %.0f ms\n" % (premiere["entites"], premiere["trouvees"],
                                                                        premiere["pleinTexte"], premiere["total"]))
        self.assertGreater(premiere["trouvees"], 0)
        self.assertLess(premiere["entites"], 300)
        for table, apres in mesure["apres"].items():
            sys.stderr.write("  après une écriture dans %s : entités %.0f ms, plein texte %.0f ms, total %.0f ms\n"
                             % (table, apres["entites"], apres["pleinTexte"], apres["total"]))
            with self.subTest(table=table):
                self.assertEqual((apres["ecrite"], apres["refaites"]), (True, 0))
                self.assertGreater(apres["trouvees"], 0)
                self.assertLess(apres["total"], 300)
        demandeur = mesure["demandeur"]
        sys.stderr.write("  demandeur, « courroie » : entités %.0f ms, plein texte %.0f ms, total %.0f ms\n"
                         % (demandeur["entites"], demandeur["pleinTexte"], demandeur["total"]))
        self.assertLess(demandeur["total"], 300)


if __name__ == "__main__":
    unittest.main()
