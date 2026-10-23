"""Balisage d'une page et contrôles d'une proposition du wiki (lot 6 refondu, tâche T113 ; ARCHITECTURE.md §20.4,
§20.6 ; D97, D106, D111).

    vocabulaire : chaque entrée de Wiki.VOCABULAIRE_SECURITE est trouvée (début de mot ou mot entier), avec accents
                  et apostrophes réels ; les faux amis (« épisodique », « Vatican », « soupape de sécurité »…) passent ;
    balisage    : lireTexte / ecrireTexte (aller-retour, rubriques dans l'ordre du type, citations en fin de phrase,
                  lignes hors de la forme) ; comparerTextes (identiques, nouvelles, reprises, retirées) ;
    contrôles   : une proposition conforme passe ; UN DÉFAUT INJECTÉ PAR MOTIF du §20.6 est refusé avec sa raison, qui
                  nomme la page (forme, citations, non-retrait, nombres, comptage, dates, nouveauté pour un OT antérieur,
                  sécurité, longueurs, liens, titres, contradictions) ; écriture à la main : retrait permis, le reste
                  contrôlé, message de sécurité propre.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_wiki_controles.py" -v
"""
import copy
import unittest

from commun import CasNavigateur, charger_scripts

SCRIPTS = [
    "js/lib/papaparse.min.js", "js/schema.js", "js/donnees.js",
    "js/modules/causes-frequentes.js", "js/modules/indicateurs-regles.js",
    "js/modules/wiki-regles.js", "js/modules/wiki-calculs.js", "js/modules/wiki-texte.js", "js/modules/wiki-recherche.js",
]

OT = "OT-2026-0042"
EQUIPEMENT = "PO-02 — Pompe centrifuge"
KIT = "Kit garniture mécanique PO-02"
MODE = "Désalignement d'accouplement"
SOURCE = ("PO-02 — Fuite à la garniture mécanique · Fuite · Garniture usée · Remplacement de pièce · Kit garniture "
          "mécanique PO-02 × 1 · Garniture usée remplacée ; accouplement désaligné de 0,4 mm, réaligné. Astuce : "
          "contrôler l'alignement au comparateur avant de remonter la garniture.")
AVANT = ("## Ce qui revient\n"
         "- Fuite à la garniture mécanique, fréquent ici [OT-2026-0010] [OT-2026-0020]\n"
         "## Ce qui a réglé le problème\n"
         "- Remplacement de la garniture par un kit neuf [OT-2026-0010]")
APRES = ("## Ce qui revient\n"
         "- Fuite à la garniture mécanique, fréquent ici [OT-2026-0010] [OT-2026-0020] [OT-2026-0042]\n"
         "## Ce qui a réglé le problème\n"
         "- Remplacement de la garniture par un kit neuf [OT-2026-0010]\n"
         "## À surveiller\n"
         "- Accouplement désaligné de 0,4 mm, voir [[Désalignement d'accouplement]] [OT-2026-0042]")
CONTEXTE = {
    "otIngere": {"id": OT, "dateIntervention": "2026-06-08 10:00", "sourceTexte": SOURCE},
    "anterieure": False,
    "pagesEnvoyees": [
        {"titre": EQUIPEMENT, "type": "équipement", "texte": AVANT,
         "otDates": [{"id": "OT-2026-0010", "date": "2026-02-10 09:00"}, {"id": "OT-2026-0020", "date": "2026-04-10 09:00"}]},
        {"titre": KIT, "type": "composant", "texte": "", "otDates": []},
    ],
    "catalogue": [{"titre": EQUIPEMENT, "type": "équipement"}, {"titre": KIT, "type": "composant"},
                  {"titre": MODE, "type": "mode"}],
}
VALABLE = {
    "rien": False,
    "pages": [
        {"action": "modifier", "titre": EQUIPEMENT, "texte": APRES},
        {"action": "creer", "titre": "Contrôler l'alignement de PO-02", "type": "savoir-faire", "rattacheA": EQUIPEMENT,
         "texte": "## Étapes\n- Contrôler l'alignement au comparateur avant de remonter la garniture [OT-2026-0042]"},
    ],
    "contradictions": [{"page": EQUIPEMENT, "phrase": "Fuite à la garniture mécanique, fréquent ici",
                        "observation": "La cause trouvée est le désalignement de l'accouplement, pas l'usure.", "ot": [OT]}],
}


# Découpage en sous-pages (§20.4, §20.6 ; révision de Nicolas du 2026-10-23) : la page de l'équipement garde une phrase
# de renvoi qui cite les OT des phrases déplacées dans la sous-page « PO-02 — garniture » (rien n'est retiré).
SOUS_PAGE = "PO-02 — garniture"
AVANT_MERE = ("## Ce qui revient\n"
              "- Fuite à la garniture mécanique, fréquent ici [OT-2026-0010] [OT-2026-0020]\n"
              "- Jeu axial de 0,2 mm à la garniture [OT-2026-0020]\n"
              "## Ce qui a réglé le problème\n"
              "- Remplacement de la garniture par un kit neuf [OT-2026-0010]")
APRES_MERE = ("## Ce qui revient\n"
              "- Garniture : voir [[PO-02 — garniture]] [OT-2026-0010] [OT-2026-0020] [OT-2026-0042]\n"
              "## Ce qui a réglé le problème\n"
              "- Remplacement de la garniture par un kit neuf [OT-2026-0010]")
# Une phrase déplacée telle quelle, une regroupée (son nombre vient du texte de la mère), une nouvelle (de l'OT ingéré).
TEXTE_SOUS_PAGE = ("## Ce qui revient\n"
                   "- Fuite à la garniture mécanique, fréquent ici [OT-2026-0010] [OT-2026-0020]\n"
                   "- Jeu axial de 0,2 mm relevé à la garniture [OT-2026-0020]\n"
                   "## À surveiller\n"
                   "- Accouplement désaligné de 0,4 mm [OT-2026-0042]")
CONTEXTE_DECOUPE = copy.deepcopy(CONTEXTE)
CONTEXTE_DECOUPE["pagesEnvoyees"][0].update({"texte": AVANT_MERE, "mere": ""})
CONTEXTE_DECOUPE["pagesEnvoyees"].append({"titre": MODE, "type": "mode", "mere": "", "otDates": [],
                                          "texte": "## Causes\n- Accouplement mal aligné [OT-2026-0010]"})
DECOUPE = {"rien": False, "contradictions": [], "pages": [
    {"action": "creer", "titre": SOUS_PAGE, "type": "équipement", "rattacheA": EQUIPEMENT, "texte": TEXTE_SOUS_PAGE},
    {"action": "modifier", "titre": EQUIPEMENT, "texte": APRES_MERE},
]}


def decoupe(titre=SOUS_PAGE):
    """Le découpage conforme, sous-page titrée `titre` (la mère renvoie à ce titre)."""
    proposition = copy.deepcopy(DECOUPE)
    proposition["pages"][0]["titre"] = titre
    proposition["pages"][1]["texte"] = APRES_MERE.replace("[[" + SOUS_PAGE + "]]", "[[" + titre + "]]")
    return proposition


def ajouter_phrase(proposition, phrase, rubrique="À surveiller"):
    """Copie de la proposition conforme, avec une phrase de plus dans la page de l'équipement."""
    resultat = copy.deepcopy(proposition)
    page = resultat["pages"][0]
    page["texte"] = page["texte"].replace("## " + rubrique + "\n", "## " + rubrique + "\n- " + phrase + "\n", 1)
    return resultat


def avec_texte(texte, rang=0):
    resultat = copy.deepcopy(VALABLE)
    resultat["pages"][rang]["texte"] = texte
    return resultat


class CasControles(CasNavigateur):

    def setUp(self):
        super().setUp()
        self.requetes = []
        self.page.on("request", lambda requete: self.requetes.append(requete.url))
        charger_scripts(self.page, SCRIPTS)

    def controler(self, proposition, contexte=None):
        return self.page.evaluate("([p, c]) => Wiki.controlerProposition(p, c)", [proposition, contexte or CONTEXTE])

    def refus(self, proposition, attendu, contexte=None):
        resultat = self.controler(proposition, contexte)
        self.assertFalse(resultat["ok"], attendu)
        self.assertTrue(any(attendu in raison for raison in resultat["raisons"]), (attendu, resultat["raisons"]))
        return resultat["raisons"]


class TestVocabulaireDeSecurite(CasControles):

    def termes(self, texte):
        return self.page.evaluate("(t) => Wiki.termesDeSecurite(t)", texte)

    def test_vocabulaire_de_securite_chaque_entree_et_faux_amis(self):
        vocabulaire = self.page.evaluate("Wiki.VOCABULAIRE_SECURITE")
        self.assertTrue(self.page.evaluate("Object.isFrozen(Wiki.VOCABULAIRE_SECURITE)"))
        for entree in vocabulaire:
            mot = entree[:-1] + "ation" if entree.endswith("*") else entree
            with self.subTest(entree=entree):
                self.assertNotEqual(self.termes("Pendant l'intervention, %s du poste" % mot.upper()), [], entree)
        for phrase in ("Couper l'alimentation générale", "Vérifier l'absence de tension", "Porter des gants",
                       "Mise en sécurité de la machine", "Poser le cadenas", "Habilitation BR requise"):
            with self.subTest(phrase=phrase):
                self.assertNotEqual(self.termes(phrase), [])
        for phrase in ("Panne épisodique du capteur", "Retour du Vatican", "La soupape de sécurité fuit",
                       "Le pressostat de sécurité déclenche", "Graissage du portique (gantry)", "Épingle cassée"):
            with self.subTest(faux_ami=phrase):
                self.assertEqual(self.termes(phrase), [])

    def test_messages_et_rubriques(self):
        self.assertEqual(self.page.evaluate("Wiki.MESSAGE_SECURITE_IA"),
                         "L'IA ne rédige jamais de consigne de sécurité : voir la consignation de l'équipement")
        self.assertTrue(self.page.evaluate("Wiki.MESSAGE_SECURITE_MAIN").startswith("Le wiki ne contient pas de consigne"))
        self.assertEqual(self.page.evaluate("Wiki.RUBRIQUES"), {
            "équipement": ["Ce qui revient", "Ce qui a réglé le problème", "À surveiller", "Astuces"],
            "composant": ["Défaillances", "Signes d'usure", "Montage et remplacement", "Équivalences"],
            "mode": ["Symptômes", "Causes", "Remèdes", "Équipements concernés"],
            "savoir-faire": ["Quand le faire", "Étapes", "Pièces et outillage", "Pièges"]})
        self.assertTrue(self.page.evaluate("Object.isFrozen(Wiki.RUBRIQUES) && Object.isFrozen(Wiki.VOCABULAIRE_NOUVEAUTE)"))


class TestBalisage(CasControles):

    def test_lire_et_ecrire_aller_retour(self):
        lu = self.page.evaluate("(t) => Wiki.lireTexte(t)", APRES)
        self.assertEqual(lu["erreurs"], [])
        self.assertEqual([r["nom"] for r in lu["rubriques"]], ["Ce qui revient", "Ce qui a réglé le problème", "À surveiller"])
        derniere = lu["rubriques"][2]["phrases"][0]
        self.assertEqual(derniere["ot"], [OT])
        self.assertEqual(derniere["liens"], [MODE])
        self.assertEqual(derniere["propre"], "Accouplement désaligné de 0,4 mm, voir Désalignement d'accouplement")
        rubriques = [{"rubrique": "À surveiller", "phrases": [{"texte": "Usure du roulement", "ot": [OT]}]},
                     {"rubrique": "Ce qui revient", "phrases": [{"texte": "Fuite [OT-2026-0010] à l'arbre", "ot": [OT, "OT-2026-0010"]}]}]
        ecrit = self.page.evaluate("([r, t]) => Wiki.ecrireTexte(r, t)", [rubriques, "équipement"])
        self.assertEqual(ecrit, "## Ce qui revient\n- Fuite à l'arbre [OT-2026-0010] [OT-2026-0042]\n"
                                "## À surveiller\n- Usure du roulement [OT-2026-0042]")
        relu = self.page.evaluate("(t) => Wiki.ecrireTexte(Wiki.lireTexte(t).rubriques.map((r) => ({ nom: r.nom, phrases: r.phrases })), 'équipement')", APRES)
        self.assertEqual(relu, APRES)

    def test_lignes_hors_de_la_forme(self):
        lu = self.page.evaluate("(t) => Wiki.lireTexte(t)", "- avant toute rubrique [OT-2026-0001]\n## Causes\ntexte libre\n\n- ok [OT-2026-0001]")
        self.assertEqual([e["ligne"] for e in lu["erreurs"]], [1, 3])

    def test_comparer_les_textes(self):
        avant = AVANT + "\n## À surveiller\n- Roulement à suivre [OT-2026-0010]"
        apres = ("## Ce qui a réglé le problème\n- Remplacement de la garniture par un kit neuf [OT-2026-0010]\n"
                 "## Ce qui revient\n- Fuites répétées de la garniture [OT-2026-0010] [OT-2026-0020] [OT-2026-0042]\n"
                 "## À surveiller\n- Alignement à contrôler [OT-2026-0042]")
        c = self.page.evaluate("([a, b]) => Wiki.comparerTextes(a, b)", [avant, apres])
        self.assertEqual([p["propre"] for p in c["identiques"]], ["Remplacement de la garniture par un kit neuf"])
        self.assertEqual([p["propre"] for p in c["nouvelles"]], ["Alignement à contrôler"])
        self.assertEqual([(r["phrase"]["propre"], [a["propre"] for a in r["anciennes"]]) for r in c["reprises"]],
                         [("Fuites répétées de la garniture", ["Fuite à la garniture mécanique, fréquent ici", "Roulement à suivre"])])
        self.assertEqual(c["retirees"], [])


class TestControles(CasControles):

    def test_une_proposition_conforme_passe(self):
        self.assertEqual(self.controler(VALABLE), {"ok": True, "raisons": []})
        self.assertEqual(self.controler({"rien": True, "pages": [], "contradictions": []}), {"ok": True, "raisons": []})
        self.assertEqual([u for u in self.requetes if not u.startswith(("file:", "data:"))], [])

    def test_forme(self):
        self.refus(avec_texte(APRES + "\n## Historique\n- Ancienne fuite [OT-2026-0042]"),
            "Page « PO-02 — Pompe centrifuge » : rubrique « Historique » inconnue pour une page équipement")
        autre = copy.deepcopy(VALABLE)
        autre["pages"][0]["titre"] = "CP-01 — Compresseur"
        self.refus(autre, "Page « CP-01 — Compresseur » : cette page n'a pas été envoyée")
        # Une page d'équipement ne se crée que comme sous-page : sans rattachement, ou rattachée à une page d'un autre type.
        for rattachement in ("", KIT):
            with self.subTest(rattachement=rattachement):
                equipement = copy.deepcopy(VALABLE)
                equipement["pages"][1].update({"type": "équipement", "titre": "CV-09 — Convoyeur", "rattacheA": rattachement,
                                               "texte": "## Ce qui revient\n- Bruit [OT-2026-0042]"})
                self.refus(equipement, "Page « CV-09 — Convoyeur » : une page d'équipement ne se crée pas")
        sans_rattachement = copy.deepcopy(VALABLE)
        sans_rattachement["pages"][1]["rattacheA"] = ""
        self.refus(sans_rattachement, "un savoir-faire se rattache à une page envoyée")
        self.refus(avec_texte(APRES + "\ntexte libre"), "hors de la forme")
        # Le rattachement : une page envoyée d'équipement ou de composant, jamais un mode.
        avec_mode = copy.deepcopy(CONTEXTE)
        avec_mode["pagesEnvoyees"].append({"titre": MODE, "type": "mode", "texte": "", "otDates": []})
        sur_un_mode = copy.deepcopy(VALABLE)
        sur_un_mode["pages"][1]["rattacheA"] = MODE
        self.refus(sur_un_mode, "un savoir-faire se rattache à une page envoyée (équipement ou composant)", avec_mode)
        sur_un_composant = copy.deepcopy(VALABLE)
        sur_un_composant["pages"][1]["rattacheA"] = KIT
        self.assertEqual(self.controler(sur_un_composant), {"ok": True, "raisons": []})

    def test_citations(self):
        self.refus(ajouter_phrase(VALABLE, "Bruit au démarrage"), "phrase sans OT cité — « Bruit au démarrage »")
        self.refus(ajouter_phrase(VALABLE, "Bruit au démarrage [OT-1999-9999]"), "OT cité hors des OT permis : OT-1999-9999")
        self.refus(ajouter_phrase(VALABLE, "[OT-2026-0042]"), "phrase vide (réduite à ses citations)")

    def test_non_retrait(self):
        sans_ot = avec_texte(APRES.replace(" [OT-2026-0020]", ""))
        raisons = self.refus(sans_ot, "OT cité retiré de la page : OT-2026-0020")
        self.assertFalse(any("phrase retirée" in r for r in raisons), raisons)       # la phrase est restée
        sans_phrase = avec_texte(APRES.replace("## Ce qui a réglé le problème\n- Remplacement de la garniture par un kit neuf [OT-2026-0010]\n", ""))
        self.refus(sans_phrase, "phrase retirée — « Remplacement de la garniture par un kit neuf »")
        oubli = avec_texte(APRES.replace("Fuite à la garniture mécanique, fréquent ici [OT-2026-0010] [OT-2026-0020] [OT-2026-0042]",
                                         "Fuites répétées de la garniture [OT-2026-0010] [OT-2026-0042]"))
        self.refus(oubli, "phrase retirée — « Fuite à la garniture mécanique, fréquent ici »")
        # Une reprise qui cite tous les OT de l'ancienne phrase est permise (reformulation).
        reprise = avec_texte(APRES.replace("Fuite à la garniture mécanique, fréquent ici", "Fuites répétées de la garniture, fréquentes ici"))
        self.assertTrue(self.controler(reprise)["ok"], self.controler(reprise)["raisons"])
        # Une phrase vidée de son texte ne reprend rien : l'ancienne est retirée.
        videe = avec_texte(APRES.replace("Remplacement de la garniture par un kit neuf [OT-2026-0010]", "[OT-2026-0010]"))
        raisons = self.refus(videe, "phrase vide (réduite à ses citations)")
        self.assertTrue(any("phrase retirée — « Remplacement de la garniture par un kit neuf »" in r for r in raisons), raisons)
        # Une phrase gardée telle quelle garde tous ses OT, même si l'OT reste cité ailleurs sur la page.
        perdu = avec_texte(APRES.replace("fréquent ici [OT-2026-0010] [OT-2026-0020]", "fréquent ici [OT-2026-0020]"))
        raisons = self.refus(perdu, "OT retiré de la phrase « Fuite à la garniture mécanique, fréquent ici » : OT-2026-0010")
        self.assertFalse(any("OT cité retiré de la page" in r for r in raisons), raisons)

    def test_nombres_comptage_et_dates(self):
        self.refus(ajouter_phrase(VALABLE, "Pression relevée à 7 bar [OT-2026-0042]"), "nombre « 7 » absent des OT cités")
        self.refus(ajouter_phrase(VALABLE, "Garniture changée 3 fois [OT-2026-0042]"), "comptage interdit")
        raisons = self.refus(ajouter_phrase(VALABLE, "Garniture changée trois fois [OT-2026-0042]"), "comptage interdit")
        self.assertFalse(any("nombre «" in r for r in raisons), raisons)
        self.refus(ajouter_phrase(VALABLE, "Fuite apparue en 2026 [OT-2026-0042]"), "aucune date dans le wiki")
        self.refus(ajouter_phrase(VALABLE, "Fuite constatée en juin [OT-2026-0042]"), "aucune date dans le wiki")
        self.refus(ajouter_phrase(VALABLE, "Garniture changée le 12/03 [OT-2026-0042]"), "aucune date dans le wiki")
        self.refus(ajouter_phrase(VALABLE, "Garniture changée le 2026-06-08 [OT-2026-0042]"), "aucune date dans le wiki")
        self.refus(ajouter_phrase(VALABLE, "Fuite jamais vue avant 2026 [OT-2026-0042]"), "aucune date dans le wiki")
        self.refus(ajouter_phrase(VALABLE, "Le kit posé avant 2025 a tenu [OT-2026-0042]"), "aucune date dans le wiki")
        self.refus(ajouter_phrase(VALABLE, "Garniture changée trente fois [OT-2026-0042]"), "comptage interdit")
        # Un numéro d'OT n'est pas un nombre connu : « 2026 » ne vient que des citations.
        raisons = self.refus(ajouter_phrase(VALABLE, "Compteur à 2026 heures [OT-2026-0042]"), "nombre « 2026 » absent des OT cités")
        self.assertFalse(any("aucune date" in r for r in raisons), raisons)
        # Un numéro d'OT écrit dans la phrase n'est pas un nombre de la phrase.
        rappel = ajouter_phrase(VALABLE, "Même cause que OT-2026-0010 [OT-2026-0042]")
        self.assertTrue(self.controler(rappel)["ok"], self.controler(rappel)["raisons"])
        # « l'entretien des 2000 heures » n'est pas une date (le nombre figure dans l'OT).
        heures = copy.deepcopy(CONTEXTE)
        heures["otIngere"]["sourceTexte"] = SOURCE + " Entretien des 2000 heures fait."
        entretien = ajouter_phrase(VALABLE, "À revoir à l'entretien des 2000 heures [OT-2026-0042]")
        self.assertTrue(self.controler(entretien, heures)["ok"], self.controler(entretien, heures)["raisons"])
        # Le titre d'une page dans un lien n'est pas une affirmation : ses nombres ne sont pas contrôlés.
        roulement = copy.deepcopy(CONTEXTE)
        roulement["catalogue"].append({"titre": "Roulement 6204", "type": "composant"})
        lien = ajouter_phrase(VALABLE, "Voir aussi [[Roulement 6204]] [OT-2026-0042]")
        self.assertTrue(self.controler(lien, roulement)["ok"], self.controler(lien, roulement)["raisons"])
        self.refus(ajouter_phrase(VALABLE, "Roulement 6204 à surveiller [OT-2026-0042]"), "nombre « 6204 » absent des OT cités", roulement)
        # Permis : un nombre de l'OT (« 0,4 » écrit « 0.4 »), « une fois », le titre d'une page dans un lien.
        permis = ajouter_phrase(VALABLE, "Une fois réaligné à 0.4 mm près, voir [[Kit garniture mécanique PO-02]] [OT-2026-0042]")
        self.assertTrue(self.controler(permis)["ok"], self.controler(permis)["raisons"])
        titre = copy.deepcopy(VALABLE)
        titre["pages"][1]["titre"] = "Contrôler l'alignement de PO-07"
        self.refus(titre, "nombre « 07 » du titre absent des OT")

    def test_nouveaute_pour_un_ot_anterieur(self):
        phrase = "Désormais l'accouplement est réaligné [OT-2026-0042]"
        anterieur = copy.deepcopy(CONTEXTE)
        anterieur.update({"anterieure": True})
        anterieur["otIngere"]["dateIntervention"] = "2026-03-01 10:00"
        self.refus(ajouter_phrase(VALABLE, phrase), "intervention antérieure à des faits déjà intégrés", anterieur)
        # La même phrase pour un OT non antérieur : permise.
        self.assertTrue(self.controler(ajouter_phrase(VALABLE, phrase))["ok"])
        # Une phrase qui cite aussi un OT plus récent n'est pas fondée sur le seul OT antérieur : permise.
        appuyee = ajouter_phrase(VALABLE, "Désormais l'accouplement est réaligné [OT-2026-0042] [OT-2026-0020]")
        self.assertTrue(self.controler(appuyee, anterieur)["ok"], self.controler(appuyee, anterieur)["raisons"])

    def test_securite(self):
        raisons = self.refus(ajouter_phrase(VALABLE, "Couper l'alimentation avant de démonter [OT-2026-0042]"),
                             "L'IA ne rédige jamais de consigne de sécurité")
        self.assertTrue(any("couper l alimentation" in r for r in raisons), raisons)
        contradiction = copy.deepcopy(VALABLE)
        contradiction["contradictions"][0]["observation"] = "Il fallait consigner la pompe."
        self.refus(contradiction, "L'IA ne rédige jamais de consigne de sécurité")

    def test_longueurs(self):
        self.assertEqual(self.page.evaluate("[Wiki.SEUILS.phrasesMax, Wiki.SEUILS.motsMax]"), [30, 600])
        # Aux bornes : 30 phrases et 600 mots passent ; 31 phrases, 601 mots non.
        juste = copy.deepcopy(VALABLE)
        juste["pages"][1]["texte"] = "## Étapes\n" + "\n".join("- Étape à suivre au comparateur [OT-2026-0042]" for _ in range(30))
        self.assertEqual(self.controler(juste), {"ok": True, "raisons": []})
        trop = copy.deepcopy(VALABLE)
        trop["pages"][1]["texte"] = "## Étapes\n" + "\n".join("- Étape à suivre au comparateur [OT-2026-0042]" for _ in range(31))
        raisons = self.refus(trop, "31 phrases, 30 au plus (au-delà, la page se découpe en sous-pages)")
        self.assertEqual(len(raisons), 1, raisons)
        assez = copy.deepcopy(VALABLE)
        assez["pages"][1]["texte"] = "## Étapes\n- " + " ".join(["mot"] * 599) + " [OT-2026-0042]"
        self.assertEqual(self.controler(assez), {"ok": True, "raisons": []})          # 599 mots + « Étapes »
        bavard = copy.deepcopy(VALABLE)
        bavard["pages"][1]["texte"] = "## Étapes\n- " + " ".join(["mot"] * 600) + " [OT-2026-0042]"
        self.refus(bavard, "601 mots, 600 au plus")         # 600 mots + « Étapes » (rubrique comprise)
        nombreuses = copy.deepcopy(VALABLE)
        for numero in range(3):
            nombreuses["pages"].append({"action": "creer", "type": "mode", "titre": "Mode de défaillance %s" % "abc"[numero],
                                        "texte": "## Causes\n- Usure [OT-2026-0042]"})
        self.refus(nombreuses, "Proposition : 4 pages créées, 3 au plus par OT")

    def test_liens_et_titres(self):
        self.refus(ajouter_phrase(VALABLE, "Voir [[Page inexistante]] [OT-2026-0042]"), "lien vers une page inconnue « Page inexistante »")
        meme = copy.deepcopy(VALABLE)
        meme["pages"][1].update({"type": "mode", "titre": MODE, "texte": "## Causes\n- Usure [OT-2026-0042]"})
        self.refus(meme, "une page de ce titre existe déjà")
        composant = copy.deepcopy(VALABLE)
        composant["pages"][1].update({"type": "composant", "titre": KIT, "rattacheA": "",
                                      "texte": "## Défaillances\n- Usure [OT-2026-0042]"})
        self.refus(composant, "Page « Kit garniture mécanique PO-02 » : une page de ce titre existe déjà")
        proche = copy.deepcopy(VALABLE)
        proche["pages"][1].update({"type": "mode", "titre": "Désalignements de l'accouplement", "texte": "## Causes\n- Usure [OT-2026-0042]"})
        self.refus(proche, "titre trop proche de « Désalignement d'accouplement »")
        # Un lien vers une page créée par la même proposition est permis.
        cree = ajouter_phrase(VALABLE, "Voir [[Contrôler l'alignement de PO-02]] [OT-2026-0042]")
        self.assertTrue(self.controler(cree)["ok"], self.controler(cree)["raisons"])

    def test_contradictions(self):
        inexistante = copy.deepcopy(VALABLE)
        inexistante["contradictions"][0]["phrase"] = "Bruit au démarrage"
        self.refus(inexistante, "la phrase contredite n'existe pas sur la page")
        autre_ot = copy.deepcopy(VALABLE)
        autre_ot["contradictions"][0]["ot"] = ["OT-2026-0010"]
        self.refus(autre_ot, "elle doit citer l'OT ingéré (OT-2026-0042), et lui seul")
        non_envoyee = copy.deepcopy(VALABLE)
        non_envoyee["contradictions"][0]["page"] = "CP-01 — Compresseur"
        self.refus(non_envoyee, "Contradiction sur la page « CP-01 — Compresseur » : cette page n'a pas été envoyée")
        rien = copy.deepcopy(VALABLE)
        rien["rien"] = True
        self.refus(rien, "« Rien à ajouter » avec des pages ou des contradictions")

    def test_ecriture_a_la_main(self):
        contexte = {"manuel": True, "pagesEnvoyees": [CONTEXTE["pagesEnvoyees"][0]], "catalogue": CONTEXTE["catalogue"],
                    "otPermis": ["OT-2026-0010", "OT-2026-0020", "OT-2026-0042"],
                    "sources": {"OT-2026-0042": SOURCE, "OT-2026-0010": "Garniture remplacée.", "OT-2026-0020": "Fuite."}}
        retrait = {"rien": False, "contradictions": [], "pages": [{"action": "modifier", "titre": EQUIPEMENT,
                   "texte": "## Ce qui revient\n- Fuite à l'arbre due au désalignement de 0,4 mm [OT-2026-0042]"}]}
        self.assertEqual(self.controler(retrait, contexte), {"ok": True, "raisons": []})
        securite = copy.deepcopy(retrait)
        securite["pages"][0]["texte"] += "\n- Porter des gants pour la dépose [OT-2026-0042]"
        raisons = self.refus(securite, "Le wiki ne contient pas de consigne de sécurité", contexte)
        self.assertFalse(any("L'IA ne rédige" in r for r in raisons), raisons)
        hors = copy.deepcopy(retrait)
        hors["pages"][0]["texte"] += "\n- Bruit [OT-2026-0099]"
        self.refus(hors, "OT cité hors des OT permis : OT-2026-0099", contexte)
        nombre = copy.deepcopy(retrait)
        nombre["pages"][0]["texte"] += "\n- Pression à 7 bar [OT-2026-0010]"
        self.refus(nombre, "nombre « 7 » absent des OT cités", contexte)


class TestSousPages(CasControles):
    """Découpage d'une page en sous-pages (§20.4, §20.6, CS113) : un découpage conforme passe, d'un bloc ; chaque
    sous-page mal formée est refusée avec sa raison, qui la nomme."""

    OK = {"ok": True, "raisons": []}

    def test_un_decoupage_conforme_passe(self):
        self.assertEqual(self.controler(DECOUPE, CONTEXTE_DECOUPE), self.OK)
        # L'ordre des pages dans la proposition ne compte pas (la mère d'abord, ici).
        inverse = copy.deepcopy(DECOUPE)
        inverse["pages"].reverse()
        self.assertEqual(self.controler(inverse, CONTEXTE_DECOUPE), self.OK)
        # Une sous-page de composant ou de mode : mêmes règles, le préfixe est le titre entier de la mère.
        for mere, type_, rubrique in ((KIT, "composant", "Défaillances"), (MODE, "mode", "Causes")):
            with self.subTest(type=type_):
                titre = mere + " — faces"
                proposition = {"rien": False, "contradictions": [], "pages": [
                    {"action": "modifier", "titre": mere, "texte": "## %s\n- Usure des faces, voir [[%s]] [OT-2026-0042]%s"
                     % (rubrique, titre, "\n- Accouplement mal aligné [OT-2026-0010]" if type_ == "mode" else "")},
                    {"action": "creer", "titre": titre, "type": type_, "rattacheA": mere,
                     "texte": "## %s\n- Faces usées par le désalignement [OT-2026-0042]" % rubrique}]}
                self.assertEqual(self.controler(proposition, CONTEXTE_DECOUPE), self.OK)
        # Les phrases nouvelles d'une sous-page restent contrôlées (nombre absent de l'OT et de la mère).
        nombre = copy.deepcopy(DECOUPE)
        nombre["pages"][0]["texte"] += "\n- Jeu de 0,7 mm à revoir [OT-2026-0042]"
        self.refus(nombre, "Page « PO-02 — garniture » : nombre « 0.7 » absent des OT cités", CONTEXTE_DECOUPE)

    def test_mere_non_modifiee_ou_sans_renvoi(self):
        seule = copy.deepcopy(DECOUPE)
        seule["pages"] = seule["pages"][:1]
        raisons = self.refus(seule, "Page « PO-02 — garniture » : sa page mère « PO-02 — Pompe centrifuge » n'est pas modifiée "
                                    "par la proposition", CONTEXTE_DECOUPE)
        self.assertEqual(len(raisons), 1, raisons)
        sans_renvoi = copy.deepcopy(DECOUPE)
        sans_renvoi["pages"][1]["texte"] = APRES_MERE.replace("voir [[PO-02 — garniture]]", "voir la page garniture")
        raisons = self.refus(sans_renvoi, "Page « PO-02 — garniture » : sa page mère « PO-02 — Pompe centrifuge » ne renvoie pas "
                                          "à elle", CONTEXTE_DECOUPE)
        self.assertEqual(len(raisons), 1, raisons)

    def test_titre_d_une_sous_page(self):
        for titre in ("Garniture de PO-02", "PO-02 - garniture", "PO-02 —", "PO-02 garniture"):
            with self.subTest(titre=titre):
                raisons = self.refus(decoupe(titre), "Page « %s » : le titre d'une sous-page commence par « PO-02 — » suivi de "
                                                     "son sujet" % titre, CONTEXTE_DECOUPE)
                self.assertEqual(len(raisons), 1, raisons)
        # Un autre repère : refusé (et son nombre n'est pas dans l'OT).
        self.refus(decoupe("PO-03 — garniture"), "commence par « PO-02 — »", CONTEXTE_DECOUPE)
        # Comparé en forme comparable : casse et accents indifférents.
        self.assertEqual(self.controler(decoupe("po-02 — Garniture usée"), CONTEXTE_DECOUPE), self.OK)

    def test_mere_elle_meme_sous_page_ou_non_envoyee(self):
        contexte = copy.deepcopy(CONTEXTE_DECOUPE)
        contexte["pagesEnvoyees"].append({"titre": "PO-02 — joints", "type": "équipement", "mere": EQUIPEMENT, "otDates": [],
                                          "texte": "## Ce qui revient\n- Joint torique sec [OT-2026-0020]"})
        petite = {"rien": False, "contradictions": [], "pages": [
            {"action": "modifier", "titre": "PO-02 — joints",
             "texte": "## Ce qui revient\n- Joints : voir [[PO-02 — joints — toriques]] [OT-2026-0020]"},
            {"action": "creer", "titre": "PO-02 — joints — toriques", "type": "équipement", "rattacheA": "PO-02 — joints",
             "texte": "## Ce qui revient\n- Joint torique sec [OT-2026-0020]"}]}
        raisons = self.refus(petite, "Page « PO-02 — joints — toriques » : sa page mère « PO-02 — joints » est elle-même une "
                                     "sous-page (de « PO-02 — Pompe centrifuge »)", contexte)
        self.assertEqual(len(raisons), 1, raisons)
        # Rattachée à une page de même type du catalogue, qui n'a pas été envoyée.
        non_envoyee = {"rien": False, "contradictions": [], "pages": [
            {"action": "creer", "titre": MODE + " — contrôle", "type": "mode", "rattacheA": MODE,
             "texte": "## Causes\n- Accouplement mal aligné [OT-2026-0042]"}]}
        self.refus(non_envoyee, "sa page mère « Désalignement d'accouplement » n'a pas été envoyée", CONTEXTE)

    def test_longueurs_et_pages_creees_sous_pages_comprises(self):
        longue = copy.deepcopy(DECOUPE)
        longue["pages"][0]["texte"] += "\n" + "\n".join("- Accouplement à revoir [OT-2026-0042]" for _ in range(28))
        raisons = self.refus(longue, "Page « PO-02 — garniture » : 31 phrases, 30 au plus.", CONTEXTE_DECOUPE)
        self.assertFalse(any("découpe" in raison for raison in raisons), raisons)   # une sous-page ne se découpe pas
        nombreuses = copy.deepcopy(DECOUPE)
        for lettre in "abc":
            nombreuses["pages"].append({"action": "creer", "type": "mode", "titre": "Mode de défaillance " + lettre,
                                        "texte": "## Causes\n- Usure [OT-2026-0042]"})
        self.refus(nombreuses, "Proposition : 4 pages créées, 3 au plus par OT", CONTEXTE_DECOUPE)

    def test_sous_page_ecrite_a_la_main(self):
        # À la main, une page s'écrit à la fois : la mère n'a pas à être modifiée en même temps ; le titre reste contrôlé.
        contexte = {"manuel": True, "pagesEnvoyees": [CONTEXTE_DECOUPE["pagesEnvoyees"][0]], "catalogue": CONTEXTE["catalogue"],
                    "otPermis": ["OT-2026-0010", "OT-2026-0020", "OT-2026-0042"],
                    "sources": {"OT-2026-0042": SOURCE, "OT-2026-0010": "Garniture remplacée.", "OT-2026-0020": "Fuite."}}
        seule = {"rien": False, "contradictions": [], "pages": [DECOUPE["pages"][0]]}
        self.assertEqual(self.controler(seule, contexte), self.OK)
        self.refus({"rien": False, "contradictions": [], "pages": [decoupe("Garniture de PO-02")["pages"][0]]},
                   "le titre d'une sous-page commence par « PO-02 — »", contexte)


if __name__ == "__main__":
    unittest.main()
