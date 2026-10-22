"""Écrans du responsable du wiki (lot 6 refondu, tâche T120 ; ARCHITECTURE.md §20.9 ; D104, D105, D107, D108 ; CS101,
CS106) : journal #/wiki-journal et ses vues, « Traiter la file », écriture à la main #/wiki-ecrire/…, contrôle du wiki.

Application ouverte en mode démo sur la base d'essai de test_wiki_ingestion (jeu de démo remplacé avant le chargement),
horloge fixée, réglages IA du poste vers le faux fournisseur. Ce qui est vérifié :
    journal     proposition : OT en lien, date d'intervention, « Intervention antérieure », modèle ; contradictions en
                tête ; phrases nouvelles surlignées, reprises avec l'ancienne forme barrée, identiques repliées, page
                créée en entier ; les autres entrées (refusée et ses raisons ligne par ligne, rejetée et son motif, à
                refaire, rien à ajouter, manuel, décision) listées avec leur statut ; une entrée seule (?entree=) ;
                rattrapage à l'affichage ;
    actions     valider (une, ou la sélection — pas de case pour une proposition avec contradiction), bilan (validées,
                « à refaire »), refus affiché avec son message ; rejeter (motif exigé dans la page) ; relancer ;
    file        « Traiter la file » avec le faux fournisseur : ordre, progression (en cours, au plus 5), « Arrêter »
                pendant le traitement (les envois partis finissent, la file garde le reste), bilan ; IA injoignable ;
                IA non activée et version web : pas de bouton, message du lot 4 ;
    hors        nombre affiché avant tout ajout, en tout et par équipement ; ajout par équipement puis du reste ;
    à la main   texte pré-rempli, aide ; refus avec ses raisons une par ligne et rien d'écrit ; succès et retour à la
                page ; nouvelle page (titre exigé, rattachement) ; archivage avec confirmation dans la page ;
    contrôle    Wiki.controleDuWiki et sa vue : un cas de chaque problème (et ce qui n'en est pas un) ;
    profils     routes refusées au technicien et au demandeur ;
    pièges      textes piégés venus des données : du texte, rien d'exécuté ;
    affichage   1440 et 375 px sans défilement horizontal, zones tactiles ≥ 48 px au téléphone, contrastes AA en thème
                clair ; aucune requête réseau hors du fournisseur d'IA.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_wiki_journal_ecrans.py" -v
"""
import json
import re
import unittest

import test_wiki_ingestion as ingestion
from commun import CasNavigateur, attendre_pret, port_libre, preregler_profil, url_fichier
from faux_fournisseur_ia import FauxFournisseur
from test_poste import AUDIT_TEXTES_JS

HEURE_FIXE = "2026-10-22T09:00:00"
NL = chr(10)
PROFILS = {"demandeur": ("Lucie Martin", ""), "technicien": ("", "TEC-0001"), "responsable": ("", "")}
PIEGE = '<img src=x onerror="window.__piege = 1"><script>window.__piege = 2</script><b>gras</b>'

# Base d'essai de test_wiki_ingestion, plus un OT clôturé administrativement que la file ne prend pas (hors du wiki).
BASE = dict(ingestion.BASE)
BASE["ordres_travail"] = ingestion.ORDRES + (
    "OT-2026-0009;EQ-0003;correctif différé;P3;Clôturé administrativement;CV-01 — Courroie usée;;;2026-07-01 08:00;"
    "2026-07-02 08:00;;;;S02;C02;R02;Courroie changée.;;2026-07-02 09:00;2026-07-03 09:00;\r\n")

TEXTE_PO01 = ingestion.TEXTE_PO01
APRES_PO01 = NL.join(["## Ce qui revient", "- Fuite de garniture au démarrage, fréquent ici [OT-2026-0007]",
                      "- Joint repris après la fuite, fréquent ici [OT-2026-0008]", "## À surveiller",
                      "- Voir [[Cavitation]] et le bruit de gravier [OT-2026-0007] [OT-2026-0008]"])
AVANT_KIT = "## Défaillances" + NL + "- Usure de la face [OT-2026-0007]"
APRES_KIT = AVANT_KIT + NL + "- Joint torique abîmé au montage [OT-2026-0001]"
APRES_CP01 = "## Ce qui revient" + NL + "- Filtre nettoyé, fréquent ici [OT-2026-0002]"
RAISONS = ["Page « CV-01 — Convoyeur » : phrase sans OT cité — « Bande tendue ».",
           "Page « CV-01 — Convoyeur » : nombre « 7 » absent des OT cités — « Tension à 7 bar »."]


def changement(page, cle, type_, titre, avant, apres, version_avant, creation=False):
    return {"page": page, "cle": cle, "type": type_, "titre": titre, "creation": creation, "version_avant": version_avant,
            "avant": avant, "apres": apres}


def entree(id_, ot, statut, ordre="", date="", changements=(), contradictions=(), **autres):
    ligne = {"id": id_, "nature": "ingestion", "ot_id": ot, "date_intervention": date, "statut": statut, "anterieure": "0",
             "ordre": ordre, "pages": "", "changements": json.dumps(list(changements), ensure_ascii=False),
             "contradictions": json.dumps(list(contradictions), ensure_ascii=False), "raisons": "", "modele": "faux",
             "essais": "1", "cree_le": "2026-10-20 08:00", "traite_le": "2026-10-20 08:05", "decide_par": "", "decide_le": "",
             "motif": ""}
    ligne.update(autres)
    return ligne


CONTRADICTION_KIT = {"page": "Kit garniture HC 50", "pageCle": "ART:ART-0001", "phrase": "Usure de la face",
                     "observation": "La face est intacte : le joint torique fuyait.", "ot": ["OT-2026-0001"], "statut": "ouverte"}
# Journal d'essai : trois propositions à valider (dont une avec une contradiction, d'un OT antérieur), et une entrée de
# chaque autre statut.
ENTREES = [
    entree("WJ-00002", "OT-2026-0008", "à valider", "2", "2026-06-01 08:00", pages="EQ:EQ-0001;ART:ART-0001;CAUSE:C01", changements=[
        changement("WP-0001", "EQ:EQ-0001", "équipement", "PO-01 — Pompe de process A", TEXTE_PO01, APRES_PO01, 1),
        changement("", "TITRE:joint qui suinte", "mode", "Joint qui suinte", "",
                   "## Symptômes" + NL + "- Goutte au joint après le démarrage [OT-2026-0008]", 0, creation=True)]),
    entree("WJ-00003", "OT-2026-0001", "à valider", "3", "2026-03-10 10:00", anterieure="1", pages="ART:ART-0001",
           changements=[changement("WP-0003", "ART:ART-0001", "composant", "Kit garniture HC 50", AVANT_KIT, APRES_KIT, 1)],
           contradictions=[CONTRADICTION_KIT]),
    entree("WJ-00004", "OT-2026-0002", "à valider", "4", "2026-03-10 10:00", pages="EQ:EQ-0002;ART:ART-0003;CAUSE:C02",
           changements=[changement("", "EQ:EQ-0002", "équipement", "CP-01 — Compresseur", "", APRES_CP01, 0)]),
    entree("WJ-00005", "OT-2026-0004", "refusée", date="2026-01-15 08:00", raisons=NL.join(RAISONS), modele="faux-invente"),
    entree("WJ-00006", "OT-2026-0006", "rejetée", "6", "2026-05-01 08:00", motif="Hors sujet", decide_par="Responsable",
           decide_le="2026-10-21 10:00", changements=[changement("", "EQ:EQ-0003", "équipement", "CV-01 — Convoyeur", "",
                                                                   "## Ce qui revient" + NL + "- Rouleaux [OT-2026-0006]", 0)]),
    entree("WJ-00007", "OT-2026-0003", "à refaire", date="2026-02-01 08:00", motif="à refaire : WJ-00006 rejetée"),
    entree("WJ-00008", "OT-2026-0005", "rien à ajouter", date="2026-03-01 08:00"),
    entree("WJ-00009", "", "appliquée", "9", nature="manuel", pages="WP:WP-0002", motif="Remise en ordre",
           decide_par="Responsable", decide_le="2026-05-02 10:00", changements=[changement(
               "WP-0002", "WP:WP-0002", "savoir-faire", "Changer la garniture de PO-01", "",
               "## Étapes" + NL + "- Repérer l'accouplement [OT-2026-0007]", 0)]),
    entree("WJ-00010", "OT-2026-0007", "appliquée", "10", nature="décision", motif="Les deux arrivent",
           decide_par="Responsable", decide_le="2026-05-03 10:00", contradictions=[{
               "entree": "WJ-00001", "rang": 0, "page": "Cavitation", "phrase": "Bruit de gravier", "observation": "Sifflement",
               "ot": ["OT-2026-0007"], "statut": "fermée", "decision": "les deux", "note": "Les deux arrivent"}]),
]
# L'entrée validée de la base (OT-2026-0007) porte une contradiction ouverte, ancienne, sur « Cavitation ».
CONTRADICTION_OUVERTE = {"page": "Cavitation", "pageCle": "WP:WP-0006", "phrase": "Bruit de gravier",
                         "observation": "Plutôt un sifflement à mi-débit.", "ot": ["OT-2026-0007"], "statut": "ouverte"}

AJOUTER_JS = """async ([entrees, contradiction]) => {
  await Donnees.modifier('wiki_journal', (lignes) => {
    entrees.forEach((e) => lignes.push(e));
    if (contradiction) lignes.find((e) => e.id === 'WJ-00001').contradictions = JSON.stringify([contradiction]);
  }, { journal: false });
}"""
ETAT_JS = """() => JSON.stringify({ pages: Donnees.lignes('wiki_pages'), journal: Donnees.lignes('wiki_journal') })"""
STATUT_JS = "(id) => (Donnees.trouver('wiki_journal', id) || {}).statut"
LIGNE_JS = "(id) => Donnees.trouver('wiki_pages', id)"
FILE_JS = "() => Wiki.file().map((e) => e.ot_id)"
TEXTE_JS = "(s) => { const e = document.querySelector(s); return e ? e.textContent.replace(/\\s+/g, ' ').trim() : null; }"
TEXTES_JS = "(s) => Array.from(document.querySelectorAll(s)).map((e) => e.textContent.replace(/\\s+/g, ' ').trim())"
LARGEUR_JS = "() => [document.documentElement.scrollWidth, window.innerWidth]"
# Le piège interprété laisserait une image, un script ou un <b>gras</b> dans l'écran.
INTERPRETE_JS = """() => document.querySelectorAll('#contenu img, #contenu script').length
  + Array.from(document.querySelectorAll('#contenu b')).filter((b) => b.textContent === 'gras').length"""
ZONES_JS = """(racine) => Array.from(document.querySelectorAll(['a', 'button', 'summary', 'label.case', 'select', 'textarea',
    'input:not([type=checkbox]):not([type=radio]):not([type=hidden]):not([type=file])'].map((s) => racine + ' ' + s).join(', ')))
  .filter((e) => e.getClientRects().length > 0 && !e.closest('[hidden], .visuellement-cache'))
  .map((e) => [e.id || e.className || e.tagName, (e.textContent || e.value || '').trim().slice(0, 30),
               Math.round(e.getBoundingClientRect().height * 10) / 10])"""


def plat(texte):
    return re.sub(r"\s+", " ", texte or "").strip()


class CasEcrans(CasNavigateur):
    """Ouvre l'application (mode démo sur la base d'essai) dans un contexte neuf ; aller à une route."""

    LENTEUR_S = 1

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.faux = FauxFournisseur(lenteur_s=cls.LENTEUR_S)
        cls.faux.demarrer()
        cls.addClassCleanup(cls.faux.arreter)

    def setUp(self):
        super().setUp()
        self.faux.requetes.clear()

    def ouvrir(self, profil="responsable", largeur=1280, hauteur=800, theme=None, telephone=False, ia=True, journal=False):
        self.contexte.close()
        options = {"locale": "fr-FR", "viewport": {"width": largeur, "height": hauteur}}
        if telephone:
            options.update(is_mobile=True, has_touch=True)
        self.contexte = self.navigateur.new_context(**options)
        self.largeur = largeur
        self.contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        self.contexte.clock.set_fixed_time(HEURE_FIXE)
        self.contexte.add_init_script("window.DEMO_DONNEES = %s;" % json.dumps({"tables": BASE, "dateReference": None}))
        if ia:
            ingestion.regler_ia(self.contexte, url=self.faux.url)
        if theme:
            self.contexte.add_init_script("try { localStorage.setItem('prevo.theme', %s); } catch (e) { /* vide */ }"
                                          % json.dumps(theme))
        nom, technicien = PROFILS[profil]
        preregler_profil(self.contexte, profil, nom, technicien)
        self.page = self.contexte.new_page()
        self.surveiller(self.page)
        self.requetes = []
        self.page.on("request", lambda requete: self.requetes.append(requete.url))
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        if journal:
            self.page.evaluate(AJOUTER_JS, [ENTREES, CONTRADICTION_OUVERTE])
        return self.page

    def aller(self, route, attendre):
        self.page.evaluate("(route) => { location.hash = route; }", route)
        self.page.wait_for_selector(attendre, state="attached")

    def journal(self, vue=""):
        self.aller("#/wiki-journal" + vue, '.wj[data-vue="%s"]' % (vue.split("=")[-1] if vue.startswith("?vue=") else "journal"))

    def texte(self, selecteur):
        return self.page.evaluate(TEXTE_JS, selecteur)

    def textes(self, selecteur):
        return self.page.evaluate(TEXTES_JS, selecteur)

    def agir(self, selecteur):
        """Clic sur un bouton d'action du journal, une fois l'action précédente et son repos (data-occupe) finis."""
        self.page.wait_for_selector(".wj:not([data-occupe])")
        self.page.click(selecteur)

    def annonce(self):
        self.page.wait_for_selector(".wj-annonce .alerte, .wj-annonce .alerte-texte", state="attached", timeout=30000)
        return self.texte(".wj-annonce")

    def statut(self, id_):
        return self.page.evaluate(STATUT_JS, id_)

    def etat(self):
        return self.page.evaluate(ETAT_JS)


def carte(id_):
    return '.wj-entree[data-entree="%s"]' % id_


# ---------------------------------------------------------------------------------------------------
# Journal : propositions, changements surlignés, autres entrées
# ---------------------------------------------------------------------------------------------------

class TestJournal(CasEcrans):

    def test_proposition_changements_surlignes_et_contradictions_en_tete(self):
        self.ouvrir(journal=True)
        self.journal()
        self.assertEqual(self.texte("#contenu h1"), "Journal du wiki")
        sections = self.page.evaluate("Array.from(document.querySelectorAll('.wj-corps > section')).map((s) => s.id)")
        self.assertEqual(sections, ["wj-a-valider", "wj-refusees", "wj-toutes"])
        # Les propositions dans l'ordre de leur rang.
        self.assertEqual(self.page.evaluate("Array.from(document.querySelectorAll('#wj-a-valider .wj-entree')).map((e) => e.dataset.entree)"),
                         ["WJ-00002", "WJ-00003", "WJ-00004"])
        c2 = carte("WJ-00002")
        self.assertEqual(self.page.get_attribute(c2 + " .wj-entree-titre a", "href"), "#/ot/OT-2026-0008")
        meta = self.texte(c2 + " .wj-meta")
        for attendu in ("à valider", "Intervention du 01/06/2026", "Modèle : faux", "Rang 2", "WJ-00002"):
            self.assertIn(attendu, meta)
        self.assertNotIn("antérieure", meta)
        page_po01 = c2 + ' .wj-changement[data-cle="EQ:EQ-0001"]'
        self.assertIn("Page modifiée", self.texte(page_po01 + " h4"))
        # Phrase nouvelle : surlignée (<mark>), étiquetée ; reprise : nouvelle forme et ancienne forme barrée.
        self.assertEqual(self.textes(page_po01 + " li.wj-nouvelle mark"), ["Joint repris après la fuite, fréquent ici [OT-2026-0008]"])
        self.assertEqual(self.textes(page_po01 + " li.wj-nouvelle .wj-etiquette"), ["Nouvelle"])
        self.assertEqual(self.textes(page_po01 + " li.wj-reprise ins"),
                         ["Voir Cavitation et le bruit de gravier [OT-2026-0007] [OT-2026-0008]"])
        self.assertEqual(self.textes(page_po01 + " li.wj-reprise del"), ["Voir Cavitation [OT-2026-0007]"])
        # Phrase identique : repliée dans un détail fermé, nulle part ailleurs.
        self.assertEqual(self.texte(page_po01 + " details.wj-identiques summary"), "1 phrase inchangée")
        self.assertFalse(self.page.evaluate("(s) => document.querySelector(s).open", page_po01 + " details.wj-identiques"))
        self.assertEqual(self.textes(page_po01 + " details.wj-identiques li"), ["Fuite de garniture au démarrage, fréquent ici [OT-2026-0007]"])
        hors_details = self.page.evaluate("""(s) => Array.from(document.querySelectorAll(s + ' li'))
          .filter((li) => !li.closest('details')).map((li) => li.textContent)""", page_po01)
        self.assertFalse(any("Fuite de garniture" in t for t in hors_details), hors_details)
        self.assertEqual(self.textes(page_po01 + " .wj-rubrique"), ["Ce qui revient", "À surveiller"])
        # Page créée : en entier.
        creee = c2 + ' .wj-changement[data-creation="oui"]'
        self.assertIn("Page créée", self.texte(creee + " h4"))
        self.assertIn("Joint qui suinte", self.texte(creee + " h4"))
        self.assertEqual(self.textes(creee + " li.wj-creee"), ["Goutte au joint après le démarrage [OT-2026-0008]"])
        # Page ancrée encore sans texte : toutes ses phrases sont nouvelles.
        self.assertEqual(self.textes(carte("WJ-00004") + " li.wj-nouvelle mark"), ["Filtre nettoyé, fréquent ici [OT-2026-0002]"])
        # Contradiction : en tête de sa carte, observation antérieure (OT antérieur), pas de case à cocher.
        c3 = carte("WJ-00003")
        enfants = self.page.evaluate("(s) => Array.from(document.querySelector(s).children).map((e) => e.className)", c3)
        self.assertIn("wj-entree-tete", enfants[0])
        self.assertIn("wj-contradictions", enfants[1])
        self.assertIn("wj-changement", enfants[2])
        contradiction = self.texte(c3 + " .wj-contradictions")
        for attendu in ("Page « Kit garniture HC 50 »", "Ce que dit la page : Usure de la face",
                        "Observation antérieure aux faits de la page : La face est intacte : le joint torique fuyait."):
            self.assertIn(attendu, contradiction)
        self.assertIn("Intervention antérieure", self.texte(c3 + " .wj-meta"))
        self.assertEqual(self.page.locator(c3 + " input.wj-choix").count(), 0)
        self.assertEqual(self.page.locator(carte("WJ-00002") + " input.wj-choix").count(), 1)
        self.assertEqual(self.page.locator(carte("WJ-00004") + " input.wj-choix").count(), 1)
        self.assertIn("WJ-00003, OT-2026-0001", self.texte(".wj-alerte-contradictions"))
        # Refusées : les raisons ligne par ligne et « Relancer ».
        self.assertEqual(self.textes("#wj-refusees " + carte("WJ-00005") + " .wj-raisons li"), RAISONS)
        self.assertEqual(self.page.locator("#wj-refusees .wj-relancer").count(), 1)
        # Toutes les entrées, avec leur statut.
        lignes = self.page.evaluate("""() => Object.fromEntries(Array.from(document.querySelectorAll('#wj-toutes .wj-ligne'))
          .map((li) => [li.dataset.entree, [li.dataset.statut, li.textContent.replace(/\\s+/g, ' ').trim()]]))""")
        self.assertEqual({k: v[0] for k, v in lignes.items()}, {
            "WJ-00001": "validée", "WJ-00002": "à valider", "WJ-00003": "à valider", "WJ-00004": "à valider",
            "WJ-00005": "refusée", "WJ-00006": "rejetée", "WJ-00007": "à refaire", "WJ-00008": "rien à ajouter",
            "WJ-00009": "appliquée", "WJ-00010": "appliquée"})
        self.assertIn("Motif : Hors sujet", lignes["WJ-00006"][1])
        self.assertIn(RAISONS[1], lignes["WJ-00005"][1])
        self.assertIn("Motif : à refaire : WJ-00006 rejetée", lignes["WJ-00007"][1])
        self.assertIn("Écriture à la main", lignes["WJ-00009"][1])
        self.assertIn("Changer la garniture de PO-01", lignes["WJ-00009"][1])
        self.assertIn("Page « Cavitation » : les deux sont vrais", lignes["WJ-00010"][1])
        # Une entrée seule.
        self.aller("#/wiki-journal?entree=WJ-00009", '.wj[data-vue="entree"]')
        self.assertIn("Écriture à la main — Changer la garniture de PO-01", self.texte(carte("WJ-00009") + " .wj-entree-titre"))
        self.assertEqual(self.textes(carte("WJ-00009") + " li.wj-nouvelle mark"), ["Repérer l'accouplement [OT-2026-0007]"])
        self.assertIn("Motif : Remise en ordre", self.texte(carte("WJ-00009")))
        self.aller("#/wiki-journal?entree=WJ-00099", '.wj[data-vue="entree"]')
        self.assertIn("Entrée introuvable", self.texte(".wj-corps"))

    def test_deux_clics_rapides_n_agissent_que_sur_la_proposition_choisie(self):
        """Relecture de T120 : deux clics au même endroit à 150 ms d'intervalle ; le second ne doit pas valider la
        carte arrivée sous le pointeur après le réaffichage."""
        self.ouvrir(journal=True)
        self.journal("?vue=a-valider")
        avant = self.page.evaluate("Donnees.lignes('wiki_journal').filter((e) => e.statut === 'à valider').map((e) => e.id)")
        bouton = self.page.locator(".wj-valider").first
        choisie = bouton.get_attribute("data-entree")
        bouton.scroll_into_view_if_needed()
        boite = bouton.bounding_box()
        x, y = boite["x"] + boite["width"] / 2, boite["y"] + boite["height"] / 2
        self.page.mouse.click(x, y)
        self.page.wait_for_timeout(150)
        self.page.mouse.click(x, y)
        self.page.wait_for_selector(".wj:not([data-occupe])")
        validees = [i for i in avant if self.statut(i) == "validée"]
        self.assertEqual(validees, [choisie])

    def test_valider_la_selection_puis_une_proposition_avec_contradiction(self):
        self.ouvrir(journal=True)
        self.journal("?vue=a-valider")
        bouton = ".wj-valider-selection"
        self.assertTrue(self.page.is_disabled(bouton))
        self.page.check(carte("WJ-00002") + " input.wj-choix")
        self.page.check(carte("WJ-00004") + " input.wj-choix")
        self.assertEqual(self.texte(bouton), "Valider les propositions sélectionnées (2)")
        self.agir(bouton)
        bilan = self.annonce()
        self.assertIn("2 propositions validées : WJ-00002, WJ-00004.", bilan)
        self.assertEqual((self.statut("WJ-00002"), self.statut("WJ-00004"), self.statut("WJ-00003")), ("validée", "validée", "à valider"))
        po01 = self.page.evaluate(LIGNE_JS, "WP-0001")
        self.assertEqual((po01["texte"], po01["version"]), (APRES_PO01, "2"))
        self.assertEqual(self.page.evaluate("Array.from(document.querySelectorAll('.wj-entree')).map((e) => e.dataset.entree)"), ["WJ-00003"])
        # Avec contradiction : validée seule, par son bouton.
        self.agir(carte("WJ-00003") + " .wj-valider")
        self.assertIn("Proposition validée : WJ-00003.", self.annonce())
        self.assertEqual(self.statut("WJ-00003"), "validée")
        self.assertEqual(self.page.evaluate(LIGNE_JS, "WP-0003")["texte"], APRES_KIT)
        # Sa contradiction est maintenant ouverte sur la page, avec le lien vers la page.
        self.journal("?vue=contradictions")
        ligne = '.wj-contradiction[data-entree="WJ-00003"]'
        self.assertEqual(self.page.get_attribute(ligne + " .wj-lien-page", "href"), "#/wiki/ART-0001")
        self.assertIn("Observation antérieure aux faits de la page : La face est intacte", self.texte(ligne))
        self.assertIn("Ce que dit la page : Bruit de gravier", self.texte('.wj-contradiction[data-entree="WJ-00001"]'))
        self.assertEqual(self.page.get_attribute('.wj-contradiction[data-entree="WJ-00001"] .wj-lien-page', "href"), "#/wiki/WP-0006")

    def test_refus_affiche_et_passage_a_refaire(self):
        self.ouvrir(journal=True)
        # Une proposition construite sur WJ-00004 (même page) ne passe pas avant elle.
        suite = entree("WJ-00011", "OT-2026-0009", "à valider", "11", "2026-07-02 08:00", pages="EQ:EQ-0003", changements=[
            changement("", "EQ:EQ-0002", "équipement", "CP-01 — Compresseur", APRES_CP01, APRES_CP01 + NL
                       + "- Courroie changée [OT-2026-0009]", 1)])
        self.page.evaluate(AJOUTER_JS, [[suite], None])
        self.journal("?vue=a-valider")
        avant = self.etat()
        self.agir(carte("WJ-00011") + " .wj-valider")
        self.assertIn("Refusé : Validez d'abord WJ-00004", self.annonce())
        self.assertEqual(self.etat(), avant)
        # Une page changée entre-temps (autre poste) : la proposition passe « à refaire », le bilan le dit.
        self.page.evaluate("""() => Donnees.modifier('wiki_pages', (lignes) => {
          const l = lignes.find((x) => x.id === 'WP-0001'); l.version = String(Number(l.version) + 1); })""")
        self.agir(carte("WJ-00002") + " .wj-valider")
        bilan = self.annonce()
        self.assertIn("Aucune proposition validée.", bilan)
        self.assertIn("Passées « à refaire »", bilan)
        self.assertIn("WJ-00002", bilan)
        self.assertEqual(self.statut("WJ-00002"), "à refaire")
        self.assertIn("OT-2026-0008", self.page.evaluate(FILE_JS))

    def test_rejeter_exige_un_motif_puis_relancer(self):
        self.ouvrir(journal=True)
        self.journal("?vue=a-valider")
        c4 = carte("WJ-00004")
        self.assertTrue(self.page.is_hidden(c4 + " .wj-rejet"))
        self.page.click(c4 + " .wj-rejeter")
        self.assertTrue(self.page.is_visible(c4 + " .wj-rejet"))
        self.assertTrue(self.page.is_hidden(c4 + " .wj-actions"))
        self.assertEqual(self.page.evaluate("document.activeElement.classList.contains('wj-motif')"), True)
        avant = self.etat()
        self.page.fill(c4 + " .wj-motif", "   ")
        self.agir(c4 + " .wj-confirmer-rejet")
        self.assertEqual(self.texte(c4 + " .wj-rejet .erreur-champ"), "Le motif du rejet est obligatoire.")
        self.assertEqual(self.page.get_attribute(c4 + " .wj-motif", "aria-invalid"), "true")
        self.assertEqual(self.etat(), avant)
        self.assertEqual(self.statut("WJ-00004"), "à valider")
        # « Annuler » referme le motif ; puis rejet avec un motif.
        self.page.click(c4 + " .wj-annuler-rejet")
        self.assertTrue(self.page.is_hidden(c4 + " .wj-rejet"))
        self.page.click(c4 + " .wj-rejeter")
        self.page.fill(c4 + " .wj-motif", "Phrase hors sujet")
        self.agir(c4 + " .wj-confirmer-rejet")
        self.assertIn("Proposition WJ-00004 rejetée (motif : Phrase hors sujet).", self.annonce())
        rejetee = self.page.evaluate("(id) => Donnees.trouver('wiki_journal', id)", "WJ-00004")
        self.assertEqual((rejetee["statut"], rejetee["motif"]), ("rejetée", "Phrase hors sujet"))
        # En échec : la refusée (raisons) et les rejetées, chacune relançable.
        self.journal("?vue=echecs")
        self.assertEqual(self.textes("#wj-echecs " + carte("WJ-00005") + " .wj-raisons li"), RAISONS)
        self.assertEqual(self.page.evaluate("Array.from(document.querySelectorAll('#wj-rejetees .wj-entree')).map((e) => e.dataset.entree)"),
                         ["WJ-00006", "WJ-00004"])
        self.agir("#wj-echecs " + carte("WJ-00005") + " .wj-relancer")
        self.assertIn("OT OT-2026-0004 remis dans la file", self.annonce())
        self.agir("#wj-rejetees " + carte("WJ-00004") + " .wj-relancer")
        self.assertIn("OT OT-2026-0002 remis dans la file", self.annonce())
        file = self.page.evaluate(FILE_JS)
        self.assertIn("OT-2026-0004", file)
        self.assertIn("OT-2026-0002", file)
        self.assertEqual(self.page.locator("#wj-echecs .wj-entree").count(), 0)
        self.assertEqual(self.page.evaluate("Array.from(document.querySelectorAll('#wj-rejetees .wj-entree')).map((e) => e.dataset.entree)"),
                         ["WJ-00006"])

    def test_rattrapage_a_l_affichage(self):
        self.ouvrir(journal=True)
        # La page de WJ-00003 a été écrite (dernière entrée), son statut n'a pas pu l'être.
        self.page.evaluate("""() => Donnees.modifier('wiki_pages', (lignes) => {
          Object.assign(lignes.find((l) => l.id === 'WP-0003'), { derniere_entree: 'WJ-00003', valide_par: 'Responsable' }); })""")
        self.assertEqual(self.statut("WJ-00003"), "à valider")
        self.journal()
        self.assertEqual(self.statut("WJ-00003"), "validée")
        self.assertEqual(self.page.locator("#wj-a-valider " + carte("WJ-00003")).count(), 0)


# ---------------------------------------------------------------------------------------------------
# « Traiter la file » avec le faux fournisseur
# ---------------------------------------------------------------------------------------------------

class TestTraiterLaFile(CasEcrans):

    LENTEUR_S = 2

    def preparer(self, modele):
        self.page.evaluate("(modele) => Ia.enregistrerReglages({ modele })", modele)
        self.page.evaluate("(ids) => Wiki.mettreEnFile(ids)", ingestion.EN_FILE)
        self.journal("?vue=file")

    def envois(self):
        return len(self.faux.requetes_vers("/api/chat"))

    def test_progression_et_arreter_pendant_le_traitement(self):
        self.ouvrir()
        self.preparer("faux-lent")
        self.assertEqual(self.page.evaluate("Array.from(document.querySelectorAll('.wj-file > li')).map((li) => li.dataset.ot)"),
                         ingestion.EN_FILE)
        self.assertTrue(self.page.is_hidden("#wj-progression"))
        self.page.click(".wj-traiter")
        self.page.wait_for_function("""() => Number((document.querySelector('#wj-progression [data-compteur="enCours"] .wj-nombre')
          || {}).textContent) > 0""")
        self.assertTrue(self.page.is_hidden(".wj-traiter"))
        en_cours = int(self.texte('#wj-progression [data-compteur="enCours"] .wj-nombre'))
        self.assertLessEqual(en_cours, self.page.evaluate("Wiki.SEUILS.agentsSimultanes"))
        self.assertIn("au plus 5", self.texte('#wj-progression [data-compteur="enCours"]'))
        self.assertEqual(int(self.texte('#wj-progression [data-compteur="restants"] .wj-nombre')), len(ingestion.EN_FILE) - en_cours)
        self.page.click(".wj-arreter")
        self.assertTrue(self.page.is_visible(".wj-arret"))
        self.assertTrue(self.page.is_disabled(".wj-arreter"))
        bilan = self.annonce()
        self.assertIn("Traitement arrêté à votre demande", bilan)
        # Les envois partis ont fini (propositions à valider), rien d'autre n'est parti, la file garde le reste.
        partis = self.envois()
        self.assertGreaterEqual(partis, 1)
        self.assertLess(partis, len(ingestion.EN_FILE))
        a_valider = self.page.evaluate("Donnees.lignes('wiki_journal').filter((e) => e.statut === 'à valider').length")
        self.assertEqual(a_valider, partis)
        self.assertIn("%d proposition" % partis, bilan)
        reste = self.page.evaluate(FILE_JS)
        self.assertEqual(len(reste), len(ingestion.EN_FILE) - partis)
        self.assertIn("%d OT reste" % len(reste), bilan)
        self.assertEqual(self.page.evaluate("Array.from(document.querySelectorAll('.wj-file > li')).map((li) => li.dataset.ot)"), reste)
        self.assertTrue(self.page.is_hidden("#wj-progression"))
        self.assertEqual(self.envois(), partis)

    def test_traitement_jusqu_au_bout_puis_propositions(self):
        self.ouvrir()
        self.preparer("faux")
        self.page.click(".wj-traiter")
        bilan = self.annonce()
        self.assertIn("Traitement de la file terminé : 6 propositions à valider, 0 sans rien à ajouter, 0 refusée", bilan)
        self.assertIn("0 OT reste dans la file", bilan)
        self.assertIn("La file est vide", self.texte(".wj-corps"))
        self.assertEqual(self.envois(), 6)
        self.journal("?vue=a-valider")
        self.assertEqual(self.page.locator("#wj-a-valider .wj-entree").count(), 6)

    def test_ia_injoignable_les_ot_restent_en_file(self):
        self.autoriser_erreur("ERR_CONNECTION_REFUSED")
        self.ouvrir()
        self.page.evaluate("(url) => Ia.enregistrerReglages({ url })", "http://127.0.0.1:%d" % port_libre())
        self.preparer("faux")
        self.page.click(".wj-traiter")
        bilan = self.annonce()
        self.assertIn("Traitement interrompu", bilan)
        self.assertIn("Les OT non traités restent dans la file.", bilan)
        self.assertEqual(self.page.evaluate(FILE_JS), ingestion.EN_FILE)

    def test_sans_ia_et_version_web_pas_de_bouton(self):
        self.ouvrir(ia=False)
        self.preparer("faux")
        self.assertEqual(self.page.locator(".wj-traiter").count(), 0)
        self.assertEqual(self.texte(".wj-sans-ia"), "L'assistant IA n'est pas activé sur ce poste (« Ce poste »).")
        self.ouvrir()
        self.page.evaluate("(ids) => Wiki.mettreEnFile(ids)", ingestion.EN_FILE)
        self.page.evaluate("() => { App.versionWeb = true; }")
        self.journal("?vue=file")
        self.assertEqual(self.page.locator(".wj-traiter").count(), 0)
        self.assertEqual(self.texte(".wj-sans-ia"), plat(self.page.evaluate("Ia.MESSAGE_VERSION_WEB")))
        self.assertEqual(self.envois(), 0)


# ---------------------------------------------------------------------------------------------------
# Hors du wiki
# ---------------------------------------------------------------------------------------------------

class TestHorsDuWiki(CasEcrans):

    def test_deux_clics_rapides_n_ajoutent_que_l_equipement_choisi(self):
        self.ouvrir()
        self.journal("?vue=hors")
        bouton = self.page.locator('.wj-hors-equipement[data-equipement="EQ-0001"] .wj-ajouter')
        bouton.scroll_into_view_if_needed()
        boite = bouton.bounding_box()
        x, y = boite["x"] + boite["width"] / 2, boite["y"] + boite["height"] / 2
        self.page.mouse.click(x, y)
        self.page.wait_for_timeout(150)
        self.page.mouse.click(x, y)
        self.page.wait_for_selector(".wj:not([data-occupe])")
        self.assertEqual(self.page.evaluate(FILE_JS), ["OT-2026-0003", "OT-2026-0001", "OT-2026-0008"])

    def test_nombre_affiche_avant_puis_ajout_par_equipement_et_du_reste(self):
        self.ouvrir()
        self.journal("?vue=hors")
        hors = self.page.evaluate("Wiki.horsDuWiki().map((o) => o.id)")
        self.assertEqual(len(hors), 7)
        self.assertEqual(self.page.evaluate(FILE_JS), [])                          # rien d'ajouté avant le clic
        self.assertEqual(self.page.get_attribute(".wj-hors-total", "data-nombre"), "7")
        self.assertIn("7 OT clôturés administrativement ne sont pas dans le wiki", self.texte(".wj-hors-total"))
        self.assertEqual(self.texte('.wj-vue[data-vue="hors"] .badge'), "7")
        par_equipement = self.page.evaluate("""() => Array.from(document.querySelectorAll('.wj-hors-equipement'))
          .map((li) => [li.dataset.equipement, Number(li.dataset.nombre), li.querySelector('button').textContent.trim()])""")
        self.assertEqual(par_equipement, [["EQ-0003", 3, "Ajouter ces 3 OT"], ["EQ-0001", 3, "Ajouter ces 3 OT"],
                                          ["EQ-0002", 1, "Ajouter cet OT"]])
        for equipement, nombre, _ in par_equipement:
            self.assertEqual(self.page.evaluate("(id) => Wiki.horsDuWiki({ equipementId: id }).length", equipement), nombre)
        self.assertIn("Ajouter les 7 OT à la file", self.texte(".wj-hors-total + .actions .wj-ajouter"))
        self.agir('.wj-hors-equipement[data-equipement="EQ-0001"] .wj-ajouter')
        self.assertIn("3 OT ajoutés à la file du wiki.", self.annonce())
        self.assertEqual(self.page.evaluate(FILE_JS), ["OT-2026-0003", "OT-2026-0001", "OT-2026-0008"])
        self.assertIn("4 OT clôturés administrativement", self.texte(".wj-hors-total"))
        self.agir(".wj-hors-total + .actions .wj-ajouter")
        self.assertIn("4 OT ajoutés à la file du wiki.", self.annonce())
        self.assertEqual(sorted(self.page.evaluate(FILE_JS)), sorted(hors))
        self.assertIn("Tous les OT clôturés administrativement sont dans le wiki", self.texte(".wj-corps"))


# ---------------------------------------------------------------------------------------------------
# Écriture à la main
# ---------------------------------------------------------------------------------------------------

TEXTE_MAIN = NL.join(["## Ce qui revient", "- Fuite de garniture au démarrage, fréquent ici [OT-2026-0007]",
                      "## Ce qui a réglé le problème", "- Garniture usée remplacée [OT-2026-0001]"])


class TestEcritureALaMain(CasEcrans):

    def test_refus_raisons_une_par_ligne_puis_succes_et_retour(self):
        self.ouvrir(journal=True)
        self.aller("#/wiki-ecrire/EQ-0001", ".wj-ecrire")
        self.assertEqual(self.page.input_value("#wj-texte"), TEXTE_PO01)
        self.assertEqual(self.page.get_attribute(".wj-ecrire", "data-version"), "1")
        aide = self.texte(".wj-aide-balisage")
        self.assertIn("« Ce qui revient », « Ce qui a réglé le problème », « À surveiller », « Astuces »", aide)
        self.assertIn("Aucune consigne de sécurité", aide)
        self.assertIn("[[Titre d'une page]]", aide)
        self.assertIn("Une proposition à valider porte sur cette page", self.texte(".wj-ecrire .alerte"))
        avant = self.etat()
        self.page.fill("#wj-texte", TEXTE_MAIN + NL + "- Porter des gants [OT-2026-0001]" + NL + "- Pression à 7 bar [OT-2026-0001]")
        self.page.click(".wj-enregistrer")
        self.page.wait_for_selector(".wj-annonce .wj-raisons li")
        raisons = self.textes(".wj-annonce .wj-raisons li")
        self.assertGreaterEqual(len(raisons), 2)
        self.assertTrue(any("consigne de sécurité" in r and "gants" in r for r in raisons), raisons)
        self.assertTrue(any("nombre « 7 » absent des OT cités" in r for r in raisons), raisons)
        self.assertIn("Texte refusé, rien n'a été écrit", self.texte(".wj-annonce"))
        self.assertEqual(self.etat(), avant)
        self.assertEqual(self.page.evaluate("location.hash"), "#/wiki-ecrire/EQ-0001")
        # Succès : la page est écrite (version vérifiée), l'entrée « manuel » porte le motif, retour à la page.
        self.page.fill("#wj-texte", TEXTE_MAIN)
        self.page.fill("#wj-motif-ecriture", "Remise en ordre")
        self.page.click(".wj-enregistrer")
        self.page.wait_for_function("location.hash === '#/wiki/EQ-0001'")
        po01 = self.page.evaluate(LIGNE_JS, "WP-0001")
        self.assertEqual((po01["texte"], po01["version"]), (TEXTE_MAIN, "2"))
        manuel = self.page.evaluate("Donnees.lignes('wiki_journal').filter((e) => e.nature === 'manuel').pop()")
        self.assertEqual((manuel["statut"], manuel["motif"], json.loads(manuel["changements"])[0]["apres"]),
                         ("appliquée", "Remise en ordre", TEXTE_MAIN))
        self.assertEqual(self.statut("WJ-00002"), "à refaire")

    def test_conflit_de_version_affiche(self):
        self.ouvrir()
        self.aller("#/wiki-ecrire/EQ-0001", ".wj-ecrire")
        self.page.evaluate("""() => Donnees.modifier('wiki_pages', (lignes) => {
          const l = lignes.find((x) => x.id === 'WP-0001'); l.version = '5'; })""")
        avant = self.etat()
        self.page.fill("#wj-texte", TEXTE_MAIN)
        self.page.click(".wj-enregistrer")
        self.page.wait_for_selector(".wj-annonce .alerte")
        self.assertIn("La page a été modifiée entre-temps", self.texte(".wj-annonce"))
        self.assertEqual(self.etat(), avant)

    def test_nouvelle_page_titre_exige_et_rattachement(self):
        self.ouvrir()
        self.aller("#/wiki-ecrire/nouvelle?type=savoir-faire&rattache=EQ-0001", ".wj-ecrire #wj-type")
        self.assertEqual(self.page.input_value("#wj-type"), "savoir-faire")
        self.assertEqual(self.page.input_value("#wj-rattache"), "EQ-0001")
        self.assertTrue(self.page.is_visible(".wj-champ-rattache"))
        self.assertTrue(self.page.is_hidden(".wj-champ-cause"))
        self.assertIn("« Quand le faire », « Étapes », « Pièces et outillage », « Pièges »", self.texte(".wj-aide-balisage"))
        self.assertEqual(self.page.locator(".wj-archiver").count(), 0)
        avant = self.etat()
        self.page.fill("#wj-texte", "## Étapes" + NL + "- Marquer la position de l'accouplement [OT-2026-0001]")
        self.page.click(".wj-enregistrer")
        self.assertEqual(self.texte("#wj-titre-erreur"), "Le titre est obligatoire.")
        self.assertEqual(self.etat(), avant)
        # Changer de type : l'aide et les champs suivent.
        self.page.select_option("#wj-type", "mode")
        self.assertTrue(self.page.is_hidden(".wj-champ-rattache"))
        self.assertTrue(self.page.is_visible(".wj-champ-cause"))
        self.assertIn("« Symptômes », « Causes », « Remèdes », « Équipements concernés »", self.texte(".wj-aide-balisage"))
        self.page.select_option("#wj-type", "savoir-faire")
        self.page.fill("#wj-titre", "Poser la garniture")
        self.page.click(".wj-enregistrer")
        self.page.wait_for_function("location.hash.startsWith('#/wiki/WP-')")
        ligne = self.page.evaluate("(id) => Donnees.trouver('wiki_pages', id)", self.page.evaluate("location.hash").split("/")[-1])
        self.assertEqual((ligne["type"], ligne["titre"], ligne["equipement_id"], ligne["origine"]),
                         ("savoir-faire", "Poser la garniture", "EQ-0001", "manuel"))

    def test_archiver_avec_confirmation_dans_la_page(self):
        self.ouvrir()
        self.page.evaluate("""() => { window.__dialogues = [];
          window.confirm = (m) => { window.__dialogues.push(m); return true; };
          window.alert = (m) => { window.__dialogues.push(m); }; }""")
        self.aller("#/wiki-ecrire/EQ-0002", ".wj-ecrire")
        self.assertEqual(self.page.locator(".wj-archiver").count(), 0)         # page sans texte : rien à archiver
        self.aller("#/wiki-ecrire/WP-0006", '.wj-ecrire[data-page="WP-0006"]')
        self.assertTrue(self.page.is_hidden(".wj-confirmation"))
        self.page.click(".wj-archiver-demande")
        self.assertTrue(self.page.is_visible(".wj-confirmation"))
        self.assertIn("Archiver la page « Cavitation » ?", self.texte(".wj-confirmation"))
        self.assertEqual(self.page.evaluate("document.querySelectorAll('dialog[open]').length"), 0)
        self.assertEqual(self.page.evaluate(LIGNE_JS, "WP-0006")["statut"], "active")
        self.page.click(".wj-archiver-annuler")
        self.assertTrue(self.page.is_hidden(".wj-confirmation"))
        self.assertEqual(self.page.evaluate(LIGNE_JS, "WP-0006")["statut"], "active")
        self.page.click(".wj-archiver-demande")
        self.page.click(".wj-archiver-confirmer")
        self.page.wait_for_function("location.hash === '#/wiki'")
        self.assertEqual(self.page.evaluate(LIGNE_JS, "WP-0006")["statut"], "archivée")
        self.assertEqual(self.page.evaluate("window.__dialogues"), [])
        archivage = self.page.evaluate("Donnees.lignes('wiki_journal').filter((e) => e.nature === 'manuel').pop()")
        self.assertTrue(json.loads(archivage["changements"])[0]["archivage"])
        self.aller("#/wiki-ecrire/WP-0006", ".wj-ecrire")
        self.assertEqual(self.texte(".wj-ecrire h1"), "Page introuvable")


# ---------------------------------------------------------------------------------------------------
# Contrôle du wiki (D108)
# ---------------------------------------------------------------------------------------------------

DOUZE = NL.join(["- Constat %s [OT-2026-0007]" % mot for mot in
                 ["un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix", "onze", "douze", "treize"]])
CONTROLE_JS = """async () => {
  const page = (id, type, titre, texte, autres) => Object.assign({ id, type, titre, texte, version: '1', statut: 'active',
    origine: 'manuel' }, autres || {});
  await Donnees.modifier('wiki_pages', (lignes) => {
    lignes.find((l) => l.id === 'WP-0002').texte += '\\n- Voir [[Page fantôme]] [OT-2026-0007]';
    lignes.find((l) => l.id === 'WP-0010').liens = 'WP-0099;WP-0009';
    lignes.push(page('WP-0011', 'mode', 'Grippage du palier', '## Causes\\n- Graisse sèche, voir [[Joint torique]] [OT-2026-0007]'));
    lignes.push(page('WP-0012', 'mode', 'Usures de garniture', '## Causes\\n- Garniture sèche [OT-2026-0007]', { cause_code: 'C01' }));
    lignes.push(page('WP-0013', 'composant', 'Joint torique', '## Défaillances\\n' + %s));
    lignes.push(page('WP-0014', 'savoir-faire', 'Serrer la bride', '## Étapes\\n- Serrer [OT-2026-0007]', { equipement_id: 'EQ-0099' }));
  });
  await Donnees.modifier('articles', (lignes) => { lignes.find((a) => a.id === 'ART-0001').actif = '0'; });
  await Donnees.modifier('wiki_journal', (lignes) => {
    lignes.push({ id: 'WJ-00050', nature: 'ingestion', ot_id: 'OT-2026-0001', statut: 'validée', ordre: '50',
      changements: '[]', decide_le: '2026-01-02 10:00', contradictions: JSON.stringify([
        { page: 'Cavitation', pageCle: 'WP:WP-0006', phrase: 'Bruit de gravier', observation: 'x', statut: 'ouverte' },
        { page: 'Cavitation', pageCle: 'WP:WP-0006', phrase: 'Bruit de gravier', observation: 'y', statut: 'fermée' }]) });
    lignes.push({ id: 'WJ-00051', nature: 'ingestion', ot_id: 'OT-2026-0002', statut: 'validée', ordre: '51', changements: '[]',
      decide_le: Donnees.maintenant(), contradictions: JSON.stringify([
        { page: 'Desserrage', pageCle: 'WP:WP-0007', phrase: 'z', observation: 'récente', statut: 'ouverte' }]) });
  }, { journal: false });
}""" % json.dumps(DOUZE)
ATTENDU_CONTROLE = {
    "lien-casse": ["WP-0002", "WP-0010", "WP-0010"],
    "orpheline": ["WP-0011"],
    "sans-ot": ["WP-0007", "WP-0008"],
    "titre-proche": ["WP-0005", "WP-0012"],
    "trop-longue": ["WP-0013"],
    "contradiction-ancienne": ["WP-0006"],
    "ancrage-disparu": ["ART-0001", "WP-0014"],
}


class TestControleDuWiki(CasEcrans):

    def test_un_cas_de_chaque_probleme_et_sa_vue(self):
        self.ouvrir()
        avant = self.etat()
        self.assertEqual(self.page.evaluate("Wiki.controleDuWiki().map((p) => [p.type, p.page])"),
                         [["sans-ot", "WP-0007"], ["sans-ot", "WP-0008"]])
        self.assertEqual(self.etat(), avant)                                   # calculé, rien d'écrit
        self.page.evaluate(CONTROLE_JS)
        problemes = self.page.evaluate("Wiki.controleDuWiki()")
        self.assertEqual({t: [p["page"] for p in problemes if p["type"] == t] for t in ATTENDU_CONTROLE}, ATTENDU_CONTROLE)
        self.assertEqual(len(problemes), sum(len(v) for v in ATTENDU_CONTROLE.values()))
        self.assertTrue(all(set(p) == {"type", "page", "titre", "message"} for p in problemes))
        messages = {(p["type"], p["page"], p["message"]) for p in problemes}
        for attendu in [("lien-casse", "WP-0002", "lien [[Page fantôme]] vers une page inconnue"),
                        ("lien-casse", "WP-0010", "lien vers WP-0099, page inexistante"),
                        ("lien-casse", "WP-0010", "lien vers « Ancien geste » (WP-0009), page archivée"),
                        ("ancrage-disparu", "ART-0001", "article ART-0001 inactif"),
                        ("ancrage-disparu", "WP-0014", "équipement EQ-0099 absent"),
                        ("contradiction-ancienne", "WP-0006", "ouverte depuis le 02/01/2026 (OT-2026-0001, WJ-00050)")]:
            self.assertIn(attendu, messages)
        self.assertIn("13 phrases", [p["message"] for p in problemes if p["type"] == "trop-longue"][0])
        self.assertIn("« Usures de garniture »", [p["message"] for p in problemes if p["page"] == "WP-0005"][0])
        # La vue : par type, chaque page avec son lien et « Modifier ».
        self.journal("?vue=controle")
        self.assertEqual(self.texte("#wj-titre-controle .badge"), str(len(problemes)))
        for type_, pages in ATTENDU_CONTROLE.items():
            bloc = '.wj-controle-type[data-type="%s"]' % type_
            with self.subTest(type=type_):
                self.assertEqual(self.page.evaluate("(s) => Array.from(document.querySelectorAll(s + ' li')).map((li) => li.dataset.page)",
                                                    bloc), pages)
                self.assertEqual(self.texte(bloc + " h3 .badge"), str(len(pages)))
                for page_id in pages:
                    self.assertEqual(self.page.get_attribute('%s li[data-page="%s"] .wj-lien-page' % (bloc, page_id), "href"),
                                     "#/wiki/" + page_id)
                    self.assertEqual(self.page.get_attribute('%s li[data-page="%s"] .wj-modifier' % (bloc, page_id), "href"),
                                     "#/wiki-ecrire/" + page_id)
        self.assertIn("Kit garniture HC 50", self.texte('.wj-controle-type[data-type="ancrage-disparu"]'))
        self.assertEqual(self.texte('.wj-vue[data-vue="controle"] .badge'), str(len(problemes)))

    def test_relecture_titre_proche_d_un_article_lien_archive_une_fois_et_rebut(self):
        """Relecture de T120 : une page libre de même forme qu'un article est trop proche ; un lien vers une page
        archivée n'est signalé qu'une fois ; un équipement au rebut est un ancrage disparu."""
        self.ouvrir()
        self.page.evaluate("""async () => {
          await Donnees.modifier('wiki_pages', (lignes) => {
            lignes.push({ id: 'WP-0030', type: 'mode', titre: 'Filtres à huile', texte: '## Causes\\n- Usure [OT-2026-0002]',
              version: '1', statut: 'active', liens: '', ot_cites: 'OT-2026-0002' });
            const lien = lignes.find((l) => l.id === 'WP-0002');
            lien.texte += '\\n- Voir [[Ancien geste]] [OT-2026-0007]';
          });
          await Donnees.modifier('equipements', (lignes) => { lignes.find((e) => e.id === 'EQ-0001').statut = 'rebut'; });
        }""")
        problemes = self.page.evaluate("Wiki.controleDuWiki()")
        proches = [p for p in problemes if p["type"] == "titre-proche" and p["page"] == "WP-0030"]
        self.assertEqual(len(proches), 1)
        self.assertIn("« Filtre à huile »", proches[0]["message"])
        # Une page ancrée n'est jamais trop proche de son propre équipement ou article.
        self.assertEqual([p for p in problemes if p["type"] == "titre-proche" and p["page"] in ("EQ-0001", "ART-0001")], [])
        self.assertEqual([p["message"] for p in problemes if p["type"] == "lien-casse" and p["page"] == "WP-0002"
                          and "Ancien geste" in p["message"]], [])
        self.assertTrue(any(p["type"] == "ancrage-disparu" and "EQ-0001 au rebut" in p["message"] for p in problemes), problemes)


# ---------------------------------------------------------------------------------------------------
# Profils, textes piégés
# ---------------------------------------------------------------------------------------------------

class TestProfilsEtPieges(CasEcrans):

    def test_routes_refusees_au_technicien_et_au_demandeur(self):
        for profil in ("technicien", "demandeur"):
            for route in ("#/wiki-journal", "#/wiki-journal?vue=file", "#/wiki-ecrire/EQ-0001", "#/wiki-ecrire/nouvelle?type=mode"):
                with self.subTest(profil=profil, route=route):
                    self.ouvrir(profil)
                    avant = self.etat()
                    self.page.evaluate("(r) => { location.hash = r; }", route)
                    self.page.wait_for_function("location.hash === '#/accueil'")
                    self.assertEqual(self.page.locator(".wj").count(), 0)
                    self.assertEqual(self.etat(), avant)

    def test_textes_pieges_restent_du_texte(self):
        self.ouvrir(journal=True)
        self.page.evaluate("""(piege) => Promise.all([
          Donnees.modifier('ordres_travail', (lignes) => { lignes.find((o) => o.id === 'OT-2026-0008').titre = piege; }),
          Donnees.modifier('wiki_pages', (lignes) => { lignes.find((l) => l.id === 'WP-0007').titre = piege; }),
          Donnees.modifier('wiki_journal', (lignes) => {
            const e = (id) => lignes.find((x) => x.id === id);
            const changements = JSON.parse(e('WJ-00002').changements);
            changements[0].apres += '\\n- ' + piege + ' [OT-2026-0008]';
            changements[1].titre = piege;
            e('WJ-00002').changements = JSON.stringify(changements);
            e('WJ-00005').raisons = 'Page « ' + piege + ' » : phrase vide.';
            e('WJ-00006').motif = piege;
            const contradictions = JSON.parse(e('WJ-00003').contradictions);
            contradictions[0].observation = piege;
            e('WJ-00003').contradictions = JSON.stringify(contradictions);
          }, { journal: false })])""", PIEGE)
        for route, attendre in (("#/wiki-journal", '.wj[data-vue="journal"]'), ("#/wiki-journal?vue=echecs", '.wj[data-vue="echecs"]'),
                                ("#/wiki-journal?vue=controle", '.wj[data-vue="controle"]'),
                                ("#/wiki-journal?entree=WJ-00002", '.wj[data-vue="entree"]')):
            with self.subTest(route=route):
                self.aller(route, attendre)
                self.page.wait_for_timeout(100)
                self.assertIsNone(self.page.evaluate("window.__piege"))
                self.assertEqual(self.page.evaluate(INTERPRETE_JS), 0)
                self.assertIn(PIEGE, self.page.evaluate("document.querySelector('#contenu').textContent"))
        # Écriture à la main : une raison qui reprend un texte piégé (lien vers une page inconnue) reste du texte.
        lien = PIEGE.replace("gras", "ailleurs")
        self.aller("#/wiki-ecrire/EQ-0001", ".wj-ecrire")
        self.page.fill("#wj-texte", TEXTE_MAIN + NL + "- Voir [[" + lien + "]] [OT-2026-0001]")
        self.page.click(".wj-enregistrer")
        self.page.wait_for_selector(".wj-annonce .wj-raisons li")
        self.assertIn(lien, self.page.evaluate("document.querySelector('.wj-annonce').textContent"))
        self.assertIsNone(self.page.evaluate("window.__piege"))
        self.assertEqual(self.page.evaluate(INTERPRETE_JS), 0)


# ---------------------------------------------------------------------------------------------------
# Affichage : 1440 et 375 px, zones tactiles, contrastes, réseau
# ---------------------------------------------------------------------------------------------------

class TestAffichage(CasEcrans):

    def parcourir(self, verifier):
        """Toutes les vues du journal (motif de rejet ouvert, détails dépliés), le traitement en cours puis son bilan,
        l'écriture à la main (raisons d'un refus, confirmation d'archivage) et une nouvelle page."""
        page = self.page
        page.evaluate("Ia.enregistrerReglages({ modele: 'faux-lent' })")
        self.journal()
        verifier("journal")
        page.click(carte("WJ-00004") + " .wj-rejeter")
        page.evaluate("() => document.querySelectorAll('.wj details').forEach((d) => { d.open = true; })")
        verifier("journal, motif de rejet et détails ouverts")
        for vue in ("a-valider", "contradictions", "echecs", "hors", "controle"):
            self.journal("?vue=" + vue)
            verifier(vue)
        self.aller("#/wiki-journal?entree=WJ-00009", '.wj[data-vue="entree"]')
        verifier("entrée")
        self.journal("?vue=file")
        verifier("file")
        page.click(".wj-traiter")
        page.wait_for_selector("#wj-progression:not([hidden]) .wj-compteurs")
        verifier("file, traitement en cours")
        page.click(".wj-arreter")
        self.annonce()
        verifier("file, bilan")
        self.aller("#/wiki-ecrire/WP-0006", ".wj-ecrire")
        page.fill("#wj-texte", TEXTE_MAIN.replace("## Ce qui revient", "## Symptômes").replace("## Ce qui a réglé le problème", "## Causes")
                  + NL + "- Porter des gants [OT-2026-0001]")
        page.click(".wj-enregistrer")
        page.wait_for_selector(".wj-annonce .wj-raisons li")
        page.click(".wj-archiver-demande")
        verifier("écriture à la main")
        self.aller("#/wiki-ecrire/nouvelle?type=savoir-faire&rattache=EQ-0001", ".wj-ecrire #wj-type")
        verifier("nouvelle page")

    def verifier_largeur(self, ou):
        # Comparée à la largeur demandée : au téléphone (is_mobile), une page trop large agrandit aussi innerWidth.
        largeur, ecran = self.page.evaluate(LARGEUR_JS)
        self.assertLessEqual(max(largeur, ecran), self.largeur, "%s : page plus large que l'écran (%s, %s > %s)"
                             % (ou, largeur, ecran, self.largeur))

    def test_1440_px_sans_defilement_horizontal_et_sans_reseau(self):
        self.ouvrir(largeur=1440, hauteur=900, journal=True)
        self.parcourir(self.verifier_largeur)
        autres = [u for u in self.requetes if not u.startswith(("file:", "data:", "blob:", self.faux.url))]
        self.assertEqual(autres, [])

    def test_375_px_sans_defilement_horizontal_et_zones_de_48_px(self):
        self.ouvrir(largeur=375, hauteur=812, telephone=True, journal=True)

        def verifier(ou):
            self.verifier_largeur(ou)
            zones = self.page.evaluate(ZONES_JS, "#contenu")
            self.assertGreater(len(zones), 0, ou)
            self.assertEqual([z for z in zones if z[2] < 47.5], [], "%s : zones de moins de 48 px" % ou)
        self.parcourir(verifier)

    def test_theme_clair_contraste_aa_des_textes(self):
        for largeur, hauteur, telephone in ((1440, 900, False), (375, 812, True)):
            with self.subTest(largeur=largeur):
                page = self.ouvrir(largeur=largeur, hauteur=hauteur, telephone=telephone, theme="clair", journal=True)
                self.assertEqual(page.evaluate("document.documentElement.dataset.theme"), "clair")

                def verifier(ou):
                    page.wait_for_timeout(100)
                    self.assertEqual(page.evaluate(AUDIT_TEXTES_JS, "#contenu"), [], ou)
                self.parcourir(verifier)


if __name__ == "__main__":
    unittest.main()
