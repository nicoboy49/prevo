"""Balisage d'une page et contrôles d'une proposition du wiki (lot 6 refondu, tâche T113 ; refonte 2, tâche T133 ;
ARCHITECTURE.md §20.4, §20.6, §20.12 ; D96 et D100 révisées 2, D97, D106, D111).

    vocabulaire : chaque entrée de Wiki.VOCABULAIRE_SECURITE est trouvée (début de mot ou mot entier), avec accents
                  et apostrophes réels ; les faux amis (« épisodique », « Vatican », « soupape de sécurité »…) passent ;
    modèle      : Wiki.RUBRIQUES (équipement « En bref », « Astuces » ; composant « À quoi il sert » ; savoir-faire ;
                  plus de mode) et Wiki.LIMITES (par type et par rubrique), gelées ; Wiki.mesurerRubriques ;
    balisage    : lireTexte / ecrireTexte (aller-retour, rubriques dans l'ordre du type, citations en fin de phrase,
                  lignes hors de la forme) ; comparerTextes (identiques, nouvelles, reprises, retirées) ;
    contrôles   : une proposition conforme passe ; UN DÉFAUT INJECTÉ PAR MOTIF du §20.6 est refusé avec sa raison, qui
                  nomme la page (forme, citations, non-retrait, nombres, comptage, dates, nouveauté pour un OT antérieur,
                  sécurité, longueurs, liens, titres, contradictions) ; écriture à la main : retrait permis, le reste
                  contrôlé, message de sécurité propre ;
    refonte 2   : chaque rubrique à sa limite (5/6 phrases et 120/121 mots pour « En bref », 10/11 phrases pour
                  « Astuces », 3/4 phrases et 80/81 mots pour « À quoi il sert », 30/31 phrases et 600/601 mots pour un
                  savoir-faire) ; seul un savoir-faire se crée (équipement, composant libre, mode refusés ; type mode
                  inconnu, même modifié) ; sous-pages pour les savoir-faire seulement.

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
SAVOIR = "Réglage d'accouplement"           # un savoir-faire du catalogue (non envoyé)
SOURCE = ("PO-02 — Fuite à la garniture mécanique · Fuite · Garniture usée · Remplacement de pièce · Kit garniture "
          "mécanique PO-02 × 1 · Garniture usée remplacée ; accouplement désaligné de 0,4 mm, réaligné. Astuce : "
          "contrôler l'alignement au comparateur avant de remonter la garniture.")
AVANT = ("## En bref\n"
         "- Fuite à la garniture mécanique, fréquent ici [OT-2026-0010] [OT-2026-0020]\n"
         "- Remplacement de la garniture par un kit neuf [OT-2026-0010]")
APRES = ("## En bref\n"
         "- Fuite à la garniture mécanique, fréquent ici [OT-2026-0010] [OT-2026-0020] [OT-2026-0042]\n"
         "- Remplacement de la garniture par un kit neuf [OT-2026-0010]\n"
         "- Accouplement désaligné de 0,4 mm, voir [[Réglage d'accouplement]] [OT-2026-0042]\n"
         "## Astuces\n"
         "- Contrôler l'alignement au comparateur avant de remonter la garniture [OT-2026-0042]")
CONTEXTE = {
    "otIngere": {"id": OT, "dateIntervention": "2026-06-08 10:00", "sourceTexte": SOURCE},
    "anterieure": False,
    "pagesEnvoyees": [
        {"titre": EQUIPEMENT, "type": "équipement", "texte": AVANT,
         "otDates": [{"id": "OT-2026-0010", "date": "2026-02-10 09:00"}, {"id": "OT-2026-0020", "date": "2026-04-10 09:00"}]},
        {"titre": KIT, "type": "composant", "texte": "", "otDates": []},
    ],
    "catalogue": [{"titre": EQUIPEMENT, "type": "équipement"}, {"titre": KIT, "type": "composant"},
                  {"titre": SAVOIR, "type": "savoir-faire"}],
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
# Rubriques et limites de la refonte 2 (D96 et D100 révisées 2, §20.12).
RUBRIQUES = {
    "équipement": ["En bref", "Astuces"],
    "composant": ["À quoi il sert"],
    "savoir-faire": ["Quand le faire", "Étapes", "Pièces et outillage", "Pièges"],
}
LIMITES = {
    "équipement": {"page": None, "rubriques": {"En bref": {"phrases": 5, "mots": 120}, "Astuces": {"phrases": 10, "mots": None}}},
    "composant": {"page": None, "rubriques": {"À quoi il sert": {"phrases": 3, "mots": 80}}},
    "savoir-faire": {"page": {"phrases": 30, "mots": 600}, "rubriques": {}},
}


# Découpage d'un savoir-faire en sous-pages (§20.4, §20.6 ; révision de Nicolas du 2026-10-23 ; seules sous-pages,
# §20.12) : la mère garde une phrase de renvoi qui cite les OT des phrases déplacées dans la sous-page (rien n'est retiré).
MERE = "Changer la garniture de PO-02"
SOUS_PAGE = MERE + " — dépose"
AVANT_MERE = ("## Étapes\n"
              "- Déposer l'accouplement et repérer sa position [OT-2026-0010] [OT-2026-0020]\n"
              "- Mesurer un jeu axial de 0,2 mm à la garniture [OT-2026-0020]\n"
              "## Pièges\n"
              "- Ne pas réutiliser l'ancien kit [OT-2026-0010]")
APRES_MERE = ("## Étapes\n"
              "- Dépose et contrôles : voir [[Changer la garniture de PO-02 — dépose]] [OT-2026-0010] [OT-2026-0020] "
              "[OT-2026-0042]\n"
              "## Pièges\n"
              "- Ne pas réutiliser l'ancien kit [OT-2026-0010]")
# Une phrase déplacée telle quelle, une regroupée (son nombre vient du texte de la mère), une nouvelle (de l'OT ingéré).
TEXTE_SOUS_PAGE = ("## Étapes\n"
                   "- Déposer l'accouplement et repérer sa position [OT-2026-0010] [OT-2026-0020]\n"
                   "- Jeu axial de 0,2 mm relevé à la garniture [OT-2026-0020]\n"
                   "## Pièges\n"
                   "- Accouplement désaligné de 0,4 mm [OT-2026-0042]")
CONTEXTE_DECOUPE = copy.deepcopy(CONTEXTE)
CONTEXTE_DECOUPE["pagesEnvoyees"][0]["mere"] = ""
CONTEXTE_DECOUPE["pagesEnvoyees"].append({"titre": MERE, "type": "savoir-faire", "mere": "", "texte": AVANT_MERE,
                                          "otDates": [{"id": "OT-2026-0010", "date": "2026-02-10 09:00"},
                                                      {"id": "OT-2026-0020", "date": "2026-04-10 09:00"}]})
CONTEXTE_DECOUPE["catalogue"].append({"titre": MERE, "type": "savoir-faire"})
DECOUPE = {"rien": False, "contradictions": [], "pages": [
    {"action": "creer", "titre": SOUS_PAGE, "type": "savoir-faire", "rattacheA": MERE, "texte": TEXTE_SOUS_PAGE},
    {"action": "modifier", "titre": MERE, "texte": APRES_MERE},
]}
# Textes rédigés aux limites (§20.12) : le texte d'une autre machine, envoyé vide.
TOUR = "CN-01 — Tour à commande numérique"
CONTEXTE_TEXTES = copy.deepcopy(CONTEXTE)
CONTEXTE_TEXTES["pagesEnvoyees"].append({"titre": TOUR, "type": "équipement", "texte": "", "otDates": []})
CONTEXTE_TEXTES["catalogue"].append({"titre": TOUR, "type": "équipement"})


def decoupe(titre=SOUS_PAGE):
    """Le découpage conforme, sous-page titrée `titre` (la mère renvoie à ce titre)."""
    proposition = copy.deepcopy(DECOUPE)
    proposition["pages"][0]["titre"] = titre
    proposition["pages"][1]["texte"] = APRES_MERE.replace("[[" + SOUS_PAGE + "]]", "[[" + titre + "]]")
    return proposition


def ajouter_phrase(proposition, phrase, rubrique="Astuces"):
    """Copie de la proposition conforme, avec une phrase de plus dans la page de l'équipement."""
    resultat = copy.deepcopy(proposition)
    page = resultat["pages"][0]
    page["texte"] = page["texte"].replace("## " + rubrique + "\n", "## " + rubrique + "\n- " + phrase + "\n", 1)
    return resultat


def avec_texte(texte, rang=0):
    resultat = copy.deepcopy(VALABLE)
    resultat["pages"][rang]["texte"] = texte
    return resultat


def balisage(*rubriques):
    """[(rubrique, [phrases])] → « ## rubrique » puis « - phrase [OT-2026-0042] » pour chaque phrase."""
    return "\n".join("## %s\n%s" % (nom, "\n".join("- %s [%s]" % (phrase, OT) for phrase in phrases))
                     for nom, phrases in rubriques)


def phrases(nombre):
    return ["Bruit au démarrage du moteur"] * nombre             # 5 mots chacune


def mots(nombre):
    return [" ".join(["mot"] * nombre)]                          # une phrase de `nombre` mots


def modification(titre, texte):
    return {"rien": False, "contradictions": [], "pages": [{"action": "modifier", "titre": titre, "texte": texte}]}


def creation(titre, type_, texte, rattache=""):
    return {"rien": False, "contradictions": [], "pages": [{"action": "creer", "titre": titre, "type": type_,
                                                             "rattacheA": rattache, "texte": texte}]}


class CasControles(CasNavigateur):

    OK = {"ok": True, "raisons": []}

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

    def refus_seul(self, proposition, raison, contexte=None):
        """Refusée pour cette seule raison, mot pour mot."""
        self.assertEqual(self.controler(proposition, contexte), {"ok": False, "raisons": [raison]})


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

    def test_messages_rubriques_et_limites(self):
        self.assertEqual(self.page.evaluate("Wiki.MESSAGE_SECURITE_IA"),
                         "L'IA ne rédige jamais de consigne de sécurité : voir la consignation de l'équipement")
        self.assertTrue(self.page.evaluate("Wiki.MESSAGE_SECURITE_MAIN").startswith("Le wiki ne contient pas de consigne"))
        self.assertEqual(self.page.evaluate("Wiki.RUBRIQUES"), RUBRIQUES)                 # plus de type « mode »
        self.assertEqual(self.page.evaluate("Wiki.LIMITES"), LIMITES)
        self.assertTrue(self.page.evaluate("Object.isFrozen(Wiki.RUBRIQUES) && Object.isFrozen(Wiki.VOCABULAIRE_NOUVEAUTE)"))
        # LIMITES gelée à tous les niveaux ; une limite par rubrique rédigée d'un équipement ou d'un composant.
        self.assertTrue(self.page.evaluate("""() => { const gele = (o) => o === null || typeof o !== 'object'
          || (Object.isFrozen(o) && Object.values(o).every(gele)); return gele(Wiki.LIMITES); }"""))
        for type_ in ("équipement", "composant"):
            self.assertEqual(list(LIMITES[type_]["rubriques"]), RUBRIQUES[type_])
        # Les seuils de page d'un savoir-faire sont ceux de LIMITES, sans doublon contradictoire.
        self.assertEqual(self.page.evaluate("[Wiki.SEUILS.phrasesMax, Wiki.SEUILS.motsMax]"), [30, 600])

    def test_mesurer_les_rubriques(self):
        """Mots d'une rubrique : ceux de ses phrases, sans citations (un lien compte comme son titre) ni nom de rubrique ;
        une rubrique écrite deux fois compte en une. La taille d'une page compte en plus les noms des rubriques."""
        texte = ("## En bref\n- Fuite à la garniture, voir [[Kit garniture mécanique PO-02]] [OT-2026-0010] [OT-2026-0020]\n"
                 "- Bruit [OT-2026-0042]\n## Astuces\n- Marquer l'accouplement [OT-2026-0042]\n## En bref\n- Usure [OT-2026-0010]")
        self.assertEqual(self.page.evaluate("(t) => Wiki.mesurerRubriques(t)", texte),
                         {"En bref": {"phrases": 3, "mots": 11}, "Astuces": {"phrases": 1, "mots": 2}})
        self.assertEqual(self.page.evaluate("(t) => Wiki.mesurerTexte(t)", texte), {"phrases": 4, "mots": 18})
        self.assertEqual(self.page.evaluate("Wiki.mesurerRubriques('')"), {})


class TestBalisage(CasControles):

    def test_lire_et_ecrire_aller_retour(self):
        lu = self.page.evaluate("(t) => Wiki.lireTexte(t)", APRES)
        self.assertEqual(lu["erreurs"], [])
        self.assertEqual([r["nom"] for r in lu["rubriques"]], ["En bref", "Astuces"])
        lien = lu["rubriques"][0]["phrases"][2]
        self.assertEqual(lien["ot"], [OT])
        self.assertEqual(lien["liens"], [SAVOIR])
        self.assertEqual(lien["propre"], "Accouplement désaligné de 0,4 mm, voir Réglage d'accouplement")
        rubriques = [{"rubrique": "Astuces", "phrases": [{"texte": "Usure du roulement", "ot": [OT]}]},
                     {"rubrique": "En bref", "phrases": [{"texte": "Fuite [OT-2026-0010] à l'arbre", "ot": [OT, "OT-2026-0010"]}]}]
        ecrit = self.page.evaluate("([r, t]) => Wiki.ecrireTexte(r, t)", [rubriques, "équipement"])
        self.assertEqual(ecrit, "## En bref\n- Fuite à l'arbre [OT-2026-0010] [OT-2026-0042]\n"
                                "## Astuces\n- Usure du roulement [OT-2026-0042]")
        relu = self.page.evaluate("(t) => Wiki.ecrireTexte(Wiki.lireTexte(t).rubriques.map((r) => ({ nom: r.nom, phrases: r.phrases })), 'équipement')", APRES)
        self.assertEqual(relu, APRES)

    def test_lignes_hors_de_la_forme(self):
        lu = self.page.evaluate("(t) => Wiki.lireTexte(t)", "- avant toute rubrique [OT-2026-0001]\n## En bref\ntexte libre\n\n- ok [OT-2026-0001]")
        self.assertEqual([e["ligne"] for e in lu["erreurs"]], [1, 3])

    def test_comparer_les_textes(self):
        avant = AVANT + "\n## Astuces\n- Roulement à suivre [OT-2026-0010]"
        apres = ("## Astuces\n- Remplacement de la garniture par un kit neuf [OT-2026-0010]\n"
                 "## En bref\n- Fuites répétées de la garniture [OT-2026-0010] [OT-2026-0020] [OT-2026-0042]\n"
                 "- Alignement à contrôler [OT-2026-0042]")
        c = self.page.evaluate("([a, b]) => Wiki.comparerTextes(a, b)", [avant, apres])
        self.assertEqual([p["propre"] for p in c["identiques"]], ["Remplacement de la garniture par un kit neuf"])
        self.assertEqual([p["propre"] for p in c["nouvelles"]], ["Alignement à contrôler"])
        self.assertEqual([(r["phrase"]["propre"], [a["propre"] for a in r["anciennes"]]) for r in c["reprises"]],
                         [("Fuites répétées de la garniture", ["Fuite à la garniture mécanique, fréquent ici", "Roulement à suivre"])])
        self.assertEqual(c["retirees"], [])


class TestControles(CasControles):

    def test_une_proposition_conforme_passe(self):
        self.assertEqual(self.controler(VALABLE), self.OK)
        self.assertEqual(self.controler({"rien": True, "pages": [], "contradictions": []}), self.OK)
        self.assertEqual([u for u in self.requetes if not u.startswith(("file:", "data:"))], [])

    def test_forme(self):
        self.refus(avec_texte(APRES + "\n## Historique\n- Ancienne fuite [OT-2026-0042]"),
            "Page « PO-02 — Pompe centrifuge » : rubrique « Historique » inconnue pour une page équipement")
        # Les rubriques retirées par la refonte 2 sont inconnues.
        for rubrique in ("Ce qui revient", "Ce qui a réglé le problème", "À surveiller"):
            with self.subTest(rubrique=rubrique):
                self.refus(avec_texte(APRES + "\n## %s\n- Fuite [OT-2026-0042]" % rubrique),
                           "rubrique « %s » inconnue pour une page équipement" % rubrique)
        self.refus(modification(KIT, "## Défaillances\n- Usure [OT-2026-0042]"),
                   "Page « Kit garniture mécanique PO-02 » : rubrique « Défaillances » inconnue pour une page composant")
        autre = copy.deepcopy(VALABLE)
        autre["pages"][0]["titre"] = "CP-01 — Compresseur"
        self.refus(autre, "Page « CP-01 — Compresseur » : cette page n'a pas été envoyée")
        sans_rattachement = copy.deepcopy(VALABLE)
        sans_rattachement["pages"][1]["rattacheA"] = ""
        self.refus(sans_rattachement, "un savoir-faire se rattache à une page envoyée")
        self.refus(avec_texte(APRES + "\ntexte libre"), "hors de la forme")
        # Le rattachement : une page envoyée d'équipement ou de composant, jamais une ancienne page de mode.
        avec_mode = copy.deepcopy(CONTEXTE)
        avec_mode["pagesEnvoyees"].append({"titre": "Désalignement d'accouplement", "type": "mode", "texte": "", "otDates": []})
        sur_un_mode = copy.deepcopy(VALABLE)
        sur_un_mode["pages"][1]["rattacheA"] = "Désalignement d'accouplement"
        self.refus(sur_un_mode, "un savoir-faire se rattache à une page envoyée (équipement ou composant)", avec_mode)
        sur_un_composant = copy.deepcopy(VALABLE)
        sur_un_composant["pages"][1]["rattacheA"] = KIT
        self.assertEqual(self.controler(sur_un_composant), self.OK)

    def test_seul_un_savoir_faire_se_cree(self):
        """Refonte 2 (§20.12) : le texte d'une machine ou d'un article existe toujours, sur sa page ; une page de mode
        n'existe plus (type inconnu) ; seul un savoir-faire se crée. Chaque refus est la seule raison."""
        texte_equipement = "## En bref\n- Bruit au démarrage [OT-2026-0042]"
        for rattache in ("", KIT):
            with self.subTest(equipement=rattache):
                self.refus_seul(creation("CV-09 — Convoyeur", "équipement", texte_equipement, rattache),
                                "Page « CV-09 — Convoyeur » : une page d'équipement ne se crée pas : le texte d'une machine "
                                "s'écrit sur sa page, qui existe toujours (seul un savoir-faire se crée).")
        # Un composant libre (sans article), ou rattaché à un équipement, ou au titre d'un article existant.
        for titre, rattache in (("Joint de bride", ""), ("Joint de bride", EQUIPEMENT), (KIT, "")):
            with self.subTest(composant=titre, rattache=rattache):
                self.refus_seul(creation(titre, "composant", "## À quoi il sert\n- Étanchéité de la bride [OT-2026-0042]",
                                         rattache),
                                "Page « %s » : une page de composant ne se crée pas : le texte d'un article s'écrit sur sa "
                                "page, qui existe toujours (seul un savoir-faire se crée)." % titre)
        self.refus_seul(creation("Usure commune", "mode", "## Causes\n- Usure normale des pièces [OT-2026-0042]"),
                        "Page « Usure commune » : type « mode » inconnu (équipement, composant, savoir-faire).")
        # Une ancienne page de mode envoyée ne se modifie pas non plus.
        avec_mode = copy.deepcopy(CONTEXTE)
        avec_mode["pagesEnvoyees"].append({"titre": "Usure commune", "type": "mode", "texte": "", "otDates": []})
        self.refus_seul(modification("Usure commune", "## Causes\n- Usure normale des pièces [OT-2026-0042]"),
                        "Page « Usure commune » : type « mode » inconnu (équipement, composant, savoir-faire).", avec_mode)
        # Le texte d'une machine ou d'un article se modifie ; un savoir-faire se crée.
        self.assertEqual(self.controler(modification(KIT, "## À quoi il sert\n- Étanchéité de l'arbre [OT-2026-0042]")), self.OK)
        self.assertEqual(self.controler(VALABLE), self.OK)

    def test_citations(self):
        self.refus(ajouter_phrase(VALABLE, "Bruit au démarrage"), "phrase sans OT cité — « Bruit au démarrage »")
        self.refus(ajouter_phrase(VALABLE, "Bruit au démarrage [OT-1999-9999]"), "OT cité hors des OT permis : OT-1999-9999")
        self.refus(ajouter_phrase(VALABLE, "[OT-2026-0042]"), "phrase vide (réduite à ses citations)")

    def test_non_retrait(self):
        sans_ot = avec_texte(APRES.replace(" [OT-2026-0020]", ""))
        raisons = self.refus(sans_ot, "OT cité retiré de la page : OT-2026-0020")
        self.assertFalse(any("phrase retirée" in r for r in raisons), raisons)       # la phrase est restée
        sans_phrase = avec_texte(APRES.replace("- Remplacement de la garniture par un kit neuf [OT-2026-0010]\n", ""))
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

    def test_longueur_d_un_savoir_faire_et_pages_creees(self):
        self.assertEqual(self.page.evaluate("[Wiki.SEUILS.phrasesMax, Wiki.SEUILS.motsMax]"), [30, 600])
        # Aux bornes : 30 phrases et 600 mots passent ; 31 phrases, 601 mots non.
        juste = copy.deepcopy(VALABLE)
        juste["pages"][1]["texte"] = "## Étapes\n" + "\n".join("- Étape à suivre au comparateur [OT-2026-0042]" for _ in range(30))
        self.assertEqual(self.controler(juste), self.OK)
        trop = copy.deepcopy(VALABLE)
        trop["pages"][1]["texte"] = "## Étapes\n" + "\n".join("- Étape à suivre au comparateur [OT-2026-0042]" for _ in range(31))
        raisons = self.refus(trop, "31 phrases, 30 au plus (au-delà, la page se découpe en sous-pages)")
        self.assertEqual(len(raisons), 1, raisons)
        assez = copy.deepcopy(VALABLE)
        assez["pages"][1]["texte"] = "## Étapes\n- " + " ".join(["mot"] * 599) + " [OT-2026-0042]"
        self.assertEqual(self.controler(assez), self.OK)          # 599 mots + « Étapes »
        bavard = copy.deepcopy(VALABLE)
        bavard["pages"][1]["texte"] = "## Étapes\n- " + " ".join(["mot"] * 600) + " [OT-2026-0042]"
        self.refus(bavard, "601 mots, 600 au plus")         # 600 mots + « Étapes » (rubrique comprise)
        nombreuses = copy.deepcopy(VALABLE)
        for titre in ("Graisser le palier de PO-02", "Purger la pompe PO-02", "Serrer les brides de PO-02"):
            nombreuses["pages"].append({"action": "creer", "type": "savoir-faire", "titre": titre, "rattacheA": EQUIPEMENT,
                                        "texte": "## Étapes\n- Usure [OT-2026-0042]"})
        self.refus(nombreuses, "Proposition : 4 pages créées, 3 au plus par OT")

    def test_liens_et_titres(self):
        self.refus(ajouter_phrase(VALABLE, "Voir [[Page inexistante]] [OT-2026-0042]"), "lien vers une page inconnue « Page inexistante »")
        meme = copy.deepcopy(VALABLE)
        meme["pages"][1].update({"titre": SAVOIR})
        self.refus(meme, "une page de ce titre existe déjà")
        # Le titre de la page d'un article est pris.
        article = copy.deepcopy(VALABLE)
        article["pages"][1].update({"titre": KIT})
        self.refus(article, "Page « Kit garniture mécanique PO-02 » : une page de ce titre existe déjà")
        proche = copy.deepcopy(VALABLE)
        proche["pages"][1].update({"titre": "Réglages de l'accouplement"})
        self.refus(proche, "titre trop proche de « Réglage d'accouplement »")
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
        retrait = modification(EQUIPEMENT, "## En bref\n- Fuite à l'arbre due au désalignement de 0,4 mm [OT-2026-0042]")
        self.assertEqual(self.controler(retrait, contexte), self.OK)
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
        # Les limites et la création valent aussi à la main.
        self.refus(modification(EQUIPEMENT, balisage(("En bref", phrases(6)))),
                   "Page « PO-02 — Pompe centrifuge » : « En bref » : 6 phrases, 5 au plus.", contexte)
        self.refus_seul(creation("Corrosion des brides", "mode", "## Causes\n- Eau [OT-2026-0042]"),
                        "Page « Corrosion des brides » : type « mode » inconnu (équipement, composant, savoir-faire).", contexte)
        self.refus(creation("Joint de bride", "composant", "## À quoi il sert\n- Étanchéité [OT-2026-0042]"),
                   "Page « Joint de bride » : une page de composant ne se crée pas", contexte)


class TestLimitesDesTextes(CasControles):
    """Longueurs des textes rédigés (D100 révisée 2, §20.12) : chaque rubrique à sa borne, refusée au-delà avec une
    raison qui nomme la page et la rubrique ; les mots d'une rubrique sans son nom ; pas de limite de mots pour
    « Astuces » ; une rubrique écrite deux fois compte en une."""

    def test_en_bref_5_phrases_et_120_mots(self):
        self.assertEqual(self.controler(modification(TOUR, balisage(("En bref", phrases(5)))), CONTEXTE_TEXTES), self.OK)
        self.refus_seul(modification(TOUR, balisage(("En bref", phrases(6)))),
                        "Page « CN-01 — Tour à commande numérique » : « En bref » : 6 phrases, 5 au plus.", CONTEXTE_TEXTES)
        # 120 mots : le nom de la rubrique (« En bref ») et les citations ne comptent pas.
        self.assertEqual(self.controler(modification(TOUR, balisage(("En bref", mots(120)))), CONTEXTE_TEXTES), self.OK)
        self.refus_seul(modification(TOUR, balisage(("En bref", mots(121)))),
                        "Page « CN-01 — Tour à commande numérique » : « En bref » : 121 mots, 120 au plus (citations non "
                        "comptées).", CONTEXTE_TEXTES)
        # Réparti sur deux phrases, de même.
        self.refus(modification(TOUR, balisage(("En bref", mots(60) + mots(61)))), "« En bref » : 121 mots, 120 au plus",
                   CONTEXTE_TEXTES)

    def test_astuces_10_phrases_sans_limite_de_mots(self):
        self.assertEqual(self.controler(modification(TOUR, balisage(("Astuces", phrases(10)))), CONTEXTE_TEXTES), self.OK)
        self.refus_seul(modification(TOUR, balisage(("Astuces", phrases(11)))),
                        "Page « CN-01 — Tour à commande numérique » : « Astuces » : 11 phrases, 10 au plus.", CONTEXTE_TEXTES)
        self.assertEqual(self.controler(modification(TOUR, balisage(("Astuces", mots(700)))), CONTEXTE_TEXTES), self.OK)

    def test_a_quoi_il_sert_3_phrases_et_80_mots(self):
        self.assertEqual(self.controler(modification(KIT, balisage(("À quoi il sert", phrases(3))))), self.OK)
        self.refus_seul(modification(KIT, balisage(("À quoi il sert", phrases(4)))),
                        "Page « Kit garniture mécanique PO-02 » : « À quoi il sert » : 4 phrases, 3 au plus.")
        self.assertEqual(self.controler(modification(KIT, balisage(("À quoi il sert", mots(80))))), self.OK)
        self.refus_seul(modification(KIT, balisage(("À quoi il sert", mots(81)))),
                        "Page « Kit garniture mécanique PO-02 » : « À quoi il sert » : 81 mots, 80 au plus (citations non "
                        "comptées).")

    def test_chaque_rubrique_a_sa_limite(self):
        # 5 + 10 phrases : chaque rubrique à sa borne, la page passe (pas de limite de page pour un équipement).
        self.assertEqual(self.controler(modification(TOUR, balisage(("En bref", phrases(5)), ("Astuces", phrases(10)))),
                                        CONTEXTE_TEXTES), self.OK)
        # Les deux rubriques au-delà : deux raisons, une par rubrique.
        resultat = self.controler(modification(TOUR, balisage(("En bref", phrases(6)), ("Astuces", phrases(11)))), CONTEXTE_TEXTES)
        self.assertEqual(resultat["raisons"], [
            "Page « CN-01 — Tour à commande numérique » : « En bref » : 6 phrases, 5 au plus.",
            "Page « CN-01 — Tour à commande numérique » : « Astuces » : 11 phrases, 10 au plus."])
        # Une rubrique écrite deux fois compte en une.
        self.refus_seul(modification(TOUR, balisage(("En bref", phrases(3)), ("Astuces", phrases(1)), ("En bref", phrases(3)))),
                        "Page « CN-01 — Tour à commande numérique » : « En bref » : 6 phrases, 5 au plus.", CONTEXTE_TEXTES)

    def test_un_savoir_faire_30_phrases_et_600_mots(self):
        cree = lambda texte: creation("Graisser le palier de PO-02", "savoir-faire", texte, EQUIPEMENT)  # noqa: E731
        self.assertEqual(self.controler(cree(balisage(("Étapes", phrases(30))))), self.OK)
        self.refus_seul(cree(balisage(("Étapes", phrases(31)))),
                        "Page « Graisser le palier de PO-02 » : 31 phrases, 30 au plus (au-delà, la page se découpe en "
                        "sous-pages).")
        self.assertEqual(self.controler(cree(balisage(("Étapes", mots(599))))), self.OK)        # 599 mots + « Étapes »
        self.refus_seul(cree(balisage(("Étapes", mots(600)))),
                        "Page « Graisser le palier de PO-02 » : 601 mots, 600 au plus (rubriques comprises, citations non "
                        "comptées ; au-delà, la page se découpe en sous-pages).")


class TestSousPages(CasControles):
    """Découpage d'un savoir-faire en sous-pages (§20.4, §20.6, CS113 ; seules sous-pages, §20.12) : un découpage conforme
    passe, d'un bloc ; chaque sous-page mal formée est refusée avec sa raison, qui la nomme ; une sous-page d'équipement ou
    de composant est refusée."""

    def test_un_decoupage_conforme_passe(self):
        self.assertEqual(self.controler(DECOUPE, CONTEXTE_DECOUPE), self.OK)
        # L'ordre des pages dans la proposition ne compte pas (la mère d'abord, ici).
        inverse = copy.deepcopy(DECOUPE)
        inverse["pages"].reverse()
        self.assertEqual(self.controler(inverse, CONTEXTE_DECOUPE), self.OK)
        # Les phrases nouvelles d'une sous-page restent contrôlées (nombre absent de l'OT et de la mère).
        nombre = copy.deepcopy(DECOUPE)
        nombre["pages"][0]["texte"] += "\n- Jeu de 0,7 mm à revoir [OT-2026-0042]"
        self.refus(nombre, "Page « %s » : nombre « 0.7 » absent des OT cités" % SOUS_PAGE, CONTEXTE_DECOUPE)

    def test_sous_page_d_equipement_ou_de_composant_refusee(self):
        """Une page d'équipement ou de composant ne se découpe plus : sa sous-page est refusée, pour cette seule raison,
        même avec la mère modifiée qui renvoie à elle."""
        for mere, type_, rubrique in ((EQUIPEMENT, "équipement", "En bref"), (KIT, "composant", "À quoi il sert")):
            with self.subTest(type=type_):
                titre = mere.split(" — ")[0] + " — faces"
                proposition = creation(titre, type_, "## %s\n- Faces usées par le désalignement [OT-2026-0042]" % rubrique, mere)
                self.refus_seul(proposition, "Page « %s » : une sous-page n'existe que pour un savoir-faire (seul un "
                                             "savoir-faire se crée)." % titre, CONTEXTE_DECOUPE)
                avec_mere = copy.deepcopy(proposition)
                avec_mere["pages"].append({"action": "modifier", "titre": mere, "texte": "## %s\n- Faces : voir [[%s]] "
                                           "[OT-2026-0042]" % (rubrique, titre)})
                self.refus(avec_mere, "Page « %s » : une sous-page n'existe que pour un savoir-faire" % titre, CONTEXTE_DECOUPE)

    def test_mere_non_modifiee_ou_sans_renvoi(self):
        seule = copy.deepcopy(DECOUPE)
        seule["pages"] = seule["pages"][:1]
        raisons = self.refus(seule, "Page « %s » : sa page mère « %s » n'est pas modifiée par la proposition"
                             % (SOUS_PAGE, MERE), CONTEXTE_DECOUPE)
        self.assertEqual(len(raisons), 1, raisons)
        sans_renvoi = copy.deepcopy(DECOUPE)
        sans_renvoi["pages"][1]["texte"] = APRES_MERE.replace("voir [[%s]]" % SOUS_PAGE, "voir la page de la dépose")
        raisons = self.refus(sans_renvoi, "Page « %s » : sa page mère « %s » ne renvoie pas à elle" % (SOUS_PAGE, MERE),
                             CONTEXTE_DECOUPE)
        self.assertEqual(len(raisons), 1, raisons)

    def test_savoir_faire_rattache_a_une_ancienne_sous_page(self):
        """Un savoir-faire se rattache à la page mère, jamais à une sous-page (ancienne sous-page d'équipement, d'avant la
        refonte 2) : il y perdrait l'ancrage de l'équipement (envoyé avec ses OT, consignation en tête)."""
        contexte = copy.deepcopy(CONTEXTE_DECOUPE)
        contexte["pagesEnvoyees"].append({"titre": "PO-02 — joints", "type": "équipement", "mere": EQUIPEMENT, "otDates": [],
                                          "texte": "## En bref\n- Joint torique sec [OT-2026-0020]"})
        savoir = creation("Changer un joint torique", "savoir-faire", "## Étapes\n- Graisser le joint neuf avant la pose "
                          "[OT-2026-0042]", "PO-02 — joints")
        raisons = self.refus(savoir, "Page « Changer un joint torique » : un savoir-faire se rattache à la page mère « %s », "
                                     "jamais à une sous-page" % EQUIPEMENT, contexte)
        self.assertEqual(len(raisons), 1, raisons)
        savoir["pages"][0]["rattacheA"] = EQUIPEMENT                 # rattaché à la mère : accepté
        self.assertEqual(self.controler(savoir, contexte), self.OK)

    def test_titre_d_une_sous_page(self):
        attendu = "le titre d'une sous-page commence par « %s — » suivi de son sujet" % MERE
        for titre in ("Dépose de la garniture de PO-02", MERE + " - dépose", MERE + " dépose"):
            with self.subTest(titre=titre):
                raisons = self.refus(decoupe(titre), "Page « %s » : %s" % (titre, attendu), CONTEXTE_DECOUPE)
                self.assertEqual(len(raisons), 1, raisons)
        # Sans sujet : refusé (et c'est le titre de la mère).
        self.refus(decoupe(MERE + " —"), attendu, CONTEXTE_DECOUPE)
        # Une autre machine dans le préfixe : refusé (et son nombre n'est pas dans l'OT).
        self.refus(decoupe("Changer la garniture de PO-03 — dépose"), "commence par « %s — »" % MERE, CONTEXTE_DECOUPE)
        # Comparé en forme comparable : casse et accents indifférents.
        self.assertEqual(self.controler(decoupe("changer la Garniture de po-02 — Dépose du kit"), CONTEXTE_DECOUPE), self.OK)

    def test_mere_elle_meme_sous_page_ou_non_envoyee(self):
        contexte = copy.deepcopy(CONTEXTE_DECOUPE)
        contexte["pagesEnvoyees"].append({"titre": MERE + " — joints", "type": "savoir-faire", "mere": MERE, "otDates": [],
                                          "texte": "## Étapes\n- Changer le joint torique [OT-2026-0020]"})
        petite = {"rien": False, "contradictions": [], "pages": [
            {"action": "modifier", "titre": MERE + " — joints",
             "texte": "## Étapes\n- Joints : voir [[%s — joints — toriques]] [OT-2026-0020]" % MERE},
            {"action": "creer", "titre": MERE + " — joints — toriques", "type": "savoir-faire", "rattacheA": MERE + " — joints",
             "texte": "## Étapes\n- Changer le joint torique [OT-2026-0020]"}]}
        raisons = self.refus(petite, "Page « %s — joints — toriques » : sa page mère « %s — joints » est elle-même une "
                                     "sous-page (de « %s »)" % (MERE, MERE, MERE), contexte)
        self.assertEqual(len(raisons), 1, raisons)
        # Rattachée à un savoir-faire du catalogue, qui n'a pas été envoyé.
        non_envoyee = creation(SAVOIR + " — contrôle", "savoir-faire", "## Étapes\n- Contrôler au comparateur [OT-2026-0042]",
                               SAVOIR)
        self.refus(non_envoyee, "sa page mère « Réglage d'accouplement » n'a pas été envoyée", CONTEXTE)

    def test_longueurs_et_pages_creees_sous_pages_comprises(self):
        longue = copy.deepcopy(DECOUPE)
        longue["pages"][0]["texte"] += "\n" + "\n".join("- Accouplement à revoir [OT-2026-0042]" for _ in range(28))
        raisons = self.refus(longue, "Page « %s » : 31 phrases, 30 au plus." % SOUS_PAGE, CONTEXTE_DECOUPE)
        self.assertFalse(any("découpe" in raison for raison in raisons), raisons)   # une sous-page ne se découpe pas
        nombreuses = copy.deepcopy(DECOUPE)
        for titre in ("Graisser le palier de PO-02", "Purger la pompe PO-02", "Serrer les brides de PO-02"):
            nombreuses["pages"].append({"action": "creer", "type": "savoir-faire", "titre": titre, "rattacheA": EQUIPEMENT,
                                        "texte": "## Étapes\n- Usure [OT-2026-0042]"})
        self.refus(nombreuses, "Proposition : 4 pages créées, 3 au plus par OT", CONTEXTE_DECOUPE)

    def test_sous_page_ecrite_a_la_main(self):
        # À la main, une page s'écrit à la fois : la mère n'a pas à être modifiée en même temps ; le titre reste contrôlé.
        contexte = {"manuel": True, "pagesEnvoyees": [CONTEXTE_DECOUPE["pagesEnvoyees"][2]], "catalogue": CONTEXTE_DECOUPE["catalogue"],
                    "otPermis": ["OT-2026-0010", "OT-2026-0020", "OT-2026-0042"],
                    "sources": {"OT-2026-0042": SOURCE, "OT-2026-0010": "Garniture remplacée.", "OT-2026-0020": "Fuite."}}
        seule = {"rien": False, "contradictions": [], "pages": [DECOUPE["pages"][0]]}
        self.assertEqual(self.controler(seule, contexte), self.OK)
        self.refus({"rien": False, "contradictions": [], "pages": [decoupe("Dépose de la garniture de PO-02")["pages"][0]]},
                   "le titre d'une sous-page commence par « %s — »" % MERE, contexte)
        # Sous une page d'équipement, refusée à la main aussi.
        contexte["pagesEnvoyees"] = [CONTEXTE["pagesEnvoyees"][0]]
        self.refus_seul(creation("PO-02 — garniture", "équipement", "## En bref\n- Garniture sèche [OT-2026-0042]", EQUIPEMENT),
                        "Page « PO-02 — garniture » : une sous-page n'existe que pour un savoir-faire (seul un savoir-faire "
                        "se crée).", contexte)


if __name__ == "__main__":
    unittest.main()
