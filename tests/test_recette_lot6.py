"""Recette du lot 6 : le wiki de maintenance de bout en bout, en mode serveur (tâche T124, ARCHITECTURE.md §20 ; D101,
D104 a, D105, D107, D110 ; CS96, CS107). Faux fournisseur seulement (tests/faux_fournisseur_ia.py, qui répond à
`ingestionWiki` grâce à tests/faux_wiki.py), joint par le relais /api/ia de serveur.py : jamais un vrai modèle.

Le parcours, sur une copie du jeu de démo (serveur.py, ServeurPrevo), avec le profil responsable, sur un poste où l'IA
est activée vers le faux fournisseur :
    1. clôture technique AVEC une astuce : temps passé, date de fin, codes, compte rendu, « Astuce pour la prochaine
       fois », « Clôturer techniquement » (onglets Exécution et Compte rendu de la fiche de l'OT EM-01 en cours) ;
    2. clôture administrative (confirmation dans la fenêtre) : l'OT entre dans la file du wiki (D104 a), le message le
       dit, l'écriture est sur le disque ;
    3. #/wiki-journal?vue=file : la file montre l'OT ; « Traiter la file » → bilan « 1 proposition à valider » ; le
       faux fournisseur a reçu UN message, par le relais du serveur, avec l'astuce et sans le nom du technicien (CS99) ;
    4. #/wiki-journal?vue=a-valider : la proposition (OT en lien, phrase nouvelle surlignée dans « En bref » de la
       machine, savoir-faire créé à partir de l'astuce, D110) ; « Valider » → validée, pages écrites sur le disque ;
    5. #/wiki/EQ-0026 : « En bref » montre la phrase nouvelle, qui cite l'OT ; la page du savoir-faire porte l'astuce ;
    6. #/wiki (accueil) : la recherche trouve le savoir-faire et l'OT sur un mot de l'astuce, et la page de la machine
       sur la phrase nouvelle (Wiki.rechercher et l'écran) ;
    7. contradiction (D107) : un second OT de la même machine, déjà clôturé techniquement (intervention antérieure aux
       faits de la page), est clôturé administrativement ; le poste choisit le modèle « faux-contradiction » (le faux
       modèle contredit la première phrase de la machine) ; « Traiter la file » → proposition avec contradiction (en tête
       de sa carte, pas de case à cocher, « Intervention antérieure ») → validée seule → la page montre « À trancher »
       et garde sa phrase → le responsable tranche « L'ancien reste » avec une note → plus rien à trancher, décision au
       journal (entrée « décision », contradiction fermée, vue Contradictions vide pour cette entrée).
Assertions sur l'écran ET sur les données (en mémoire et sur le disque) ; aucune erreur dans la console (CasNavigateur) ;
horloge du navigateur fixée à la date de référence de la démo (les rôles datés du jeu tiennent à toute heure).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_recette_lot6.py" -v
"""
import csv
import io
import json
import re
import unittest
from pathlib import Path

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, scenarios_demo
from faux_fournisseur_ia import FauxFournisseur
from test_controles import date_reference
from test_dictee import NOTER_TOASTS_JS
from test_wiki_ingestion import regler_ia

REFERENCE = date_reference()
HEURE_FIXE = REFERENCE.isoformat() + "T09:30:00"
NL = chr(10)

# OT de scénario « En cours » du jeu de démo (EM-01, fardeleuse) ; l'autre OT de la même machine, déjà clôturé
# techniquement et plus ancien, sert à la contradiction (trouvé par les données, jamais écrit en dur).
OT_EN_COURS = scenarios_demo()["ot_statut_en_cours"]
CODE_CAUSE, CODE_REMEDE = "C11", "R02"
COMPTE_RENDU = "Température de soudure dérivée : réajustée après préchauffage de la barre, colis témoins conformes."
# Sans chiffre ni consigne de sécurité (les contrôles du §20.6 refuseraient la proposition) ; le faux modèle en tire
# un savoir-faire commun titré par son premier geste (D116).
ASTUCE = "Préchauffer la barre de soudure avant le premier colis de la série."
GESTE = "Préchauffer la barre de soudure avant le premier colis de la série"
MOT_ASTUCE = "préchauffer"                  # un mot que seule l'astuce apporte au wiki de la démo
NOTE_DECISION = "Réglage confirmé à l'atelier"
BILAN_UNE_PROPOSITION = "Traitement de la file terminé : 1 proposition à valider, 0 sans rien à ajouter, 0 refusée"
TOAST_FILE = "OT ajouté à la file du wiki."
TOAST_DECISION = "Décision enregistrée au journal du wiki."
OBSERVATION_FAUX = "Cet OT trouve une autre cause."          # tests/faux_wiki.py, modèle faux-contradiction

TEXTE_JS = "(s) => { const e = document.querySelector(s); return e ? e.textContent.replace(/\\s+/g, ' ').trim() : null; }"
TEXTES_JS = "(s) => Array.from(document.querySelectorAll(s)).map((e) => e.textContent.replace(/\\s+/g, ' ').trim())"
FILE_JS = "() => Wiki.file().map((e) => e.ot_id)"
ENTREE_JS = "(ot) => Donnees.lignes('wiki_journal').filter((e) => e.nature === 'ingestion' && e.ot_id === ot).pop() || null"
PAGE_MACHINE_JS = """(id) => Donnees.lignes('wiki_pages').find((l) => l.type === 'équipement' && l.equipement_id === id
  && l.statut !== 'archivée') || null"""
PAGE_TITRE_JS = "(titre) => Donnees.lignes('wiki_pages').find((l) => l.titre === titre && l.statut !== 'archivée') || null"
RECHERCHE_JS = """(texte) => Wiki.rechercher(texte, {}).portees.flatMap((p) => p.resultats
  .map((r) => [r.type, r.type === 'ot' ? r.otId : r.pageId]))"""
TROUVES_JS = "() => Array.from(document.querySelectorAll('#wiki-trouves .wiki-trouve')).map((li) => [li.dataset.type, li.dataset.id])"


def plat(texte):
    return re.sub(r"\s+", " ", texte or "").strip()


def premiere_phrase_de(texte_page):
    """Première phrase du texte d'une page (première ligne « - … » sous sa première rubrique), citations retirées."""
    ligne = next(l for l in texte_page.split(NL) if l.startswith("- "))
    return plat(re.sub(r"\[OT-\d{4}-\d{4,}\]", " ", ligne[2:]))


def lire_csv(dossier, table):
    """Lignes d'un CSV du dossier de données du serveur (valeurs brutes, apostrophe de protection comprise)."""
    texte = (Path(dossier) / (table + ".csv")).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte, newline=""), delimiter=";"))


def ligne_csv(dossier, table, identifiant):
    return next(l for l in lire_csv(dossier, table) if l["id"] == identifiant)


class CasRecetteLot6(CasNavigateur):
    """Gestes communs : fiche OT, journal du wiki, lecture de l'écran et des données."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.faux = FauxFournisseur(lenteur_s=1)
        cls.faux.demarrer()
        cls.addClassCleanup(cls.faux.arreter)

    def setUp(self):
        super().setUp()
        self.faux.requetes.clear()
        self.requetes = []
        self.contexte.clock.set_fixed_time(HEURE_FIXE)
        self.contexte.add_init_script(NOTER_TOASTS_JS)
        preregler_profil(self.contexte, "responsable")
        regler_ia(self.contexte, url=self.faux.url)
        self.page.on("request", lambda requete: self.requetes.append(requete.url))

    # -- écran --------------------------------------------------------------------------------------

    def texte(self, selecteur):
        return self.page.evaluate(TEXTE_JS, selecteur)

    def textes(self, selecteur):
        return self.page.evaluate(TEXTES_JS, selecteur)

    def aller(self, route, attendre):
        self.page.evaluate("(route) => { location.hash = route; }", route)
        self.page.wait_for_selector(attendre, state="attached")

    def toasts(self):
        return self.page.evaluate("window.__toasts || []")

    def attendre_toast(self, extrait):
        self.page.wait_for_function("(t) => (window.__toasts || []).some((x) => x.includes(t))", arg=extrait)

    # -- fiche OT ----------------------------------------------------------------------------------

    def ouvrir_ot(self, ot_id):
        self.aller("#/ot/" + ot_id, ".ot-fiche")
        self.page.wait_for_function(
            "(id) => { const n = document.querySelector('.ot-fiche .ot-numero'); return n && n.textContent === id; }", arg=ot_id)

    def onglet(self, identifiant):
        self.page.click(".onglet[data-onglet='%s']" % identifiant)

    def attendre_statut(self, statut):
        self.page.wait_for_function(
            "(s) => { const b = document.querySelector('.ot-badges .badge.statut'); return b && b.textContent === s; }", arg=statut)

    def cloturer_administrativement(self, ot_id):
        """« Clôturer administrativement » (fiche de l'OT), confirmation dans la fenêtre, statut puis message de la file."""
        self.page.click(".ot-actions button:has-text('Clôturer administrativement')")
        self.page.wait_for_selector("dialog[open] .fenetre-actions .btn-primaire")
        self.page.click("dialog[open] .fenetre-actions .btn-primaire")
        self.attendre_statut("Clôturé administrativement")
        self.attendre_toast(TOAST_FILE)
        self.assertEqual(self.page.locator(".ot-fiche button[data-action='transition']").count(), 0, "OT verrouillé")

    # -- journal du wiki ---------------------------------------------------------------------------

    def journal(self, vue):
        self.aller("#/wiki-journal?vue=" + vue, '.wj[data-vue="%s"]' % vue)

    def agir(self, selecteur):
        self.page.wait_for_selector(".wj:not([data-occupe])")
        self.page.click(selecteur)

    def annonce(self):
        self.page.wait_for_selector(".wj-annonce .alerte, .wj-annonce .alerte-texte", state="attached", timeout=60000)
        return self.texte(".wj-annonce")

    def traiter_la_file(self, ots_attendus):
        """#/wiki-journal?vue=file : la file dans l'ordre attendu, « Traiter la file », le bilan."""
        self.journal("file")
        self.assertEqual(self.page.evaluate("Array.from(document.querySelectorAll('.wj-file > li')).map((li) => li.dataset.ot)"),
                         ots_attendus)
        self.assertEqual(self.page.locator(".wj-sans-ia").count(), 0, "l'IA du poste est utilisable")
        self.page.click(".wj-traiter")
        bilan = self.annonce()
        self.assertIn("0 OT reste dans la file", bilan)
        self.assertEqual(self.page.evaluate(FILE_JS), [])
        return bilan

    def entree(self, ot_id):
        entree = self.page.evaluate(ENTREE_JS, ot_id)
        self.assertIsNotNone(entree, "entrée du journal du wiki pour " + ot_id)
        return entree

    def valider(self, entree_id):
        """« Valider » sur la carte de la proposition (vue À valider) ; rend le bilan."""
        self.journal("a-valider")
        carte = '.wj-entree[data-entree="%s"]' % entree_id
        self.page.wait_for_selector("#wj-a-valider " + carte)
        self.agir(carte + " .wj-valider")
        bilan = self.annonce()
        self.assertIn("Proposition validée : %s." % entree_id, bilan)
        self.assertEqual(self.page.evaluate("(id) => Donnees.trouver('wiki_journal', id).statut", entree_id), "validée")
        return bilan


class TestRecetteWiki(CasRecetteLot6):

    def test_cloture_file_traitement_validation_page_recherche_puis_contradiction_tranchee(self):
        with ServeurPrevo() as serveur:
            page = self.page
            page.goto(serveur.url + "/")
            attendre_pret(page)
            self.assertEqual(page.evaluate("App.mode"), "serveur")
            self.assertEqual(page.evaluate("Donnees.aujourdhui()"), REFERENCE.isoformat())
            ot = page.evaluate("(id) => Donnees.trouver('ordres_travail', id)", OT_EN_COURS)
            self.assertEqual(ot["statut"], "En cours")
            equipement_id = ot["equipement_id"]
            equipement = page.evaluate("(id) => Donnees.trouver('equipements', id)", equipement_id)
            technicien = page.evaluate("(id) => Donnees.trouver('techniciens', id)", ot["technicien_id"])
            nom_technicien = technicien["prenom"] + " " + technicien["nom"]
            phrase = ot["titre"].split(" — ", 1)[-1]           # la phrase du faux modèle : le titre de l'OT sans le repère
            # Le second OT : même machine, clôturé techniquement, plus ancien (intervention antérieure aux faits).
            ot_anterieur = page.evaluate("""(id) => Donnees.lignes('ordres_travail').filter((o) => o.equipement_id === id
              && o.statut === 'Clôturé techniquement').sort((a, b) => a.date_fin.localeCompare(b.date_fin))[0] || null""", equipement_id)
            self.assertIsNotNone(ot_anterieur, "un OT clôturé techniquement sur " + equipement["repere"])
            # État de départ : file vide, aucune page ne cite l'OT, pas de savoir-faire du geste.
            self.assertEqual(page.evaluate(FILE_JS), [])
            page_machine = page.evaluate(PAGE_MACHINE_JS, equipement_id)
            self.assertIsNotNone(page_machine, "page wiki de la machine dans la démo")
            self.assertNotIn(OT_EN_COURS, page_machine["texte"])
            self.assertIsNone(page.evaluate(PAGE_TITRE_JS, GESTE))
            self.assertEqual([t for t in page.evaluate(RECHERCHE_JS, MOT_ASTUCE) if t[0] == "page"], [],
                             "aucune page ne parle encore du geste")
            print("\n  [recette] OT %s (%s), page %s « %s » ; OT antérieur %s (%s)"
                  % (OT_EN_COURS, equipement["repere"], page_machine["id"], page_machine["titre"], ot_anterieur["id"],
                     ot_anterieur["date_fin"]))

            # 1. Clôture technique avec une astuce (onglets Exécution et Compte rendu)
            self.ouvrir_ot(OT_EN_COURS)
            self.attendre_statut("En cours")
            self.onglet("execution")
            page.wait_for_selector("#form-temps")
            page.select_option("#ot-temps-technicien", ot["technicien_id"])
            page.fill("#ot-temps-heures", "1,5")
            page.click("#form-temps button[type=submit]")
            self.attendre_toast("Temps ajouté")
            self.onglet("execution")
            page.click("#form-execution .ot-maintenant")
            page.click("#form-execution button[type=submit]")
            self.attendre_toast("Exécution enregistrée")
            self.onglet("compte-rendu")
            page.wait_for_selector("#form-compte-rendu [name=astuce]")
            page.select_option("#form-compte-rendu [name=cause_code]", CODE_CAUSE)
            page.select_option("#form-compte-rendu [name=remede_code]", CODE_REMEDE)
            page.fill("#form-compte-rendu [name=compte_rendu]", COMPTE_RENDU)
            page.fill("#form-compte-rendu [name=astuce]", ASTUCE)
            page.check("#form-compte-rendu [name=remise_service]")
            page.click("#form-compte-rendu button:has-text('Clôturer techniquement')")
            self.attendre_statut("Clôturé techniquement")
            sur_disque = ligne_csv(serveur.dossier, "ordres_travail", OT_EN_COURS)
            self.assertEqual((sur_disque["statut"], sur_disque["astuce"], sur_disque["cause_code"], sur_disque["remede_code"]),
                             ("Clôturé techniquement", ASTUCE, CODE_CAUSE, CODE_REMEDE))
            self.assertEqual(sur_disque["date_fin"], REFERENCE.isoformat() + " 09:30")
            self.assertEqual(page.evaluate(FILE_JS), [], "rien dans la file avant la clôture administrative")

            # 2. Clôture administrative : l'OT entre dans la file (D104 a)
            self.cloturer_administrativement(OT_EN_COURS)
            self.assertEqual(page.evaluate(FILE_JS), [OT_EN_COURS])
            en_file = self.entree(OT_EN_COURS)
            self.assertEqual((en_file["statut"], en_file["date_intervention"], en_file["essais"]),
                             ("en file", sur_disque["date_fin"], "0"))
            self.assertEqual(ligne_csv(serveur.dossier, "ordres_travail", OT_EN_COURS)["statut"], "Clôturé administrativement")
            self.assertEqual(ligne_csv(serveur.dossier, "wiki_journal", en_file["id"])["statut"], "en file")
            self.assertEqual(self.faux.requetes_vers("/api/chat"), [], "rien n'est envoyé à la clôture (D104 a)")

            # 3. « Traiter la file » : un message au faux fournisseur, par le relais ; une proposition
            bilan = self.traiter_la_file([OT_EN_COURS])
            self.assertIn(BILAN_UNE_PROPOSITION, bilan)
            envois = self.faux.requetes_vers("/api/chat")
            self.assertEqual(len(envois), 1)
            message = next(m["content"] for m in envois[0]["corps"]["messages"] if m["role"] == "user")
            self.assertTrue(message.startswith("OT à intégrer : " + OT_EN_COURS), message[:80])
            self.assertIn("Astuce pour la prochaine fois : " + ASTUCE, message)
            self.assertIn("=== Page « " + page_machine["titre"] + " » (équipement", message)
            self.assertNotIn(nom_technicien, json.dumps(envois[0]["corps"], ensure_ascii=False))          # CS99
            self.assertEqual(envois[0]["corps"]["model"], "faux")
            self.assertTrue(any("/api/ia" in u for u in self.requetes), "l'appel passe par le relais du serveur")
            self.assertEqual([u for u in self.requetes if u.startswith(self.faux.url)], [], "jamais le fournisseur en direct")
            proposition = self.entree(OT_EN_COURS)
            self.assertEqual((proposition["id"], proposition["statut"], proposition["modele"]), (en_file["id"], "à valider", "faux"))
            changements = json.loads(proposition["changements"])
            self.assertEqual([c["cle"] for c in changements if not c["creation"]], ["EQ:" + equipement_id])
            self.assertIn("- %s [%s]" % (phrase, OT_EN_COURS), changements[0]["apres"])
            crees = [c for c in changements if c["creation"]]
            self.assertEqual([(c["titre"], c["type"], c["rattacheA"]) for c in crees], [(GESTE, "savoir-faire", page_machine["titre"])])
            self.assertIn("- %s [%s]" % (ASTUCE, OT_EN_COURS), crees[0]["apres"])

            # 4. Le journal montre la proposition ; le responsable la valide
            self.journal("a-valider")
            carte = '#wj-a-valider .wj-entree[data-entree="%s"]' % proposition["id"]
            page.wait_for_selector(carte)
            self.assertEqual(page.get_attribute(carte + " .wj-entree-titre a", "href"), "#/ot/" + OT_EN_COURS)
            meta = self.texte(carte + " .wj-meta")
            self.assertIn("à valider", meta)
            self.assertIn("Modèle : faux", meta)
            self.assertNotIn("antérieure", meta)
            nouvelles = self.textes(carte + ' .wj-changement[data-cle="EQ:%s"] li.wj-nouvelle mark' % equipement_id)
            self.assertIn("%s [%s]" % (phrase, OT_EN_COURS), nouvelles)
            self.assertEqual(self.textes(carte + ' .wj-changement[data-cle="EQ:%s"] .wj-rubrique' % equipement_id)[:1], ["En bref"])
            creee = carte + ' .wj-changement[data-creation="oui"]'
            self.assertIn("Page créée", self.texte(creee + " h4"))
            self.assertIn(GESTE, self.texte(creee + " h4"))
            self.assertIn("%s [%s]" % (ASTUCE, OT_EN_COURS), self.textes(creee + " li.wj-creee"))
            self.assertEqual(page.locator(carte + " input.wj-choix").count(), 1)
            version_avant = int(page_machine["version"])
            self.valider(proposition["id"])
            self.assertEqual(page.locator('#wj-a-valider .wj-entree[data-entree="%s"]' % proposition["id"]).count(), 0)
            page_machine = page.evaluate(PAGE_MACHINE_JS, equipement_id)
            self.assertIn("- %s [%s]" % (phrase, OT_EN_COURS), page_machine["texte"])
            self.assertEqual((int(page_machine["version"]), page_machine["derniere_entree"]), (version_avant + 1, proposition["id"]))
            savoir_faire = page.evaluate(PAGE_TITRE_JS, GESTE)
            self.assertIsNotNone(savoir_faire)
            self.assertEqual((savoir_faire["type"], savoir_faire["equipement_id"], savoir_faire["origine"]), ("savoir-faire", equipement_id, "IA"))
            self.assertIn("- %s [%s]" % (ASTUCE, OT_EN_COURS), savoir_faire["texte"])
            # Sur le disque : les pages et le journal.
            self.assertIn("- %s [%s]" % (phrase, OT_EN_COURS), ligne_csv(serveur.dossier, "wiki_pages", page_machine["id"])["texte"].replace("\r\n", NL))
            self.assertEqual(ligne_csv(serveur.dossier, "wiki_pages", savoir_faire["id"])["titre"], GESTE)
            self.assertEqual(ligne_csv(serveur.dossier, "wiki_journal", proposition["id"])["statut"], "validée")

            # 5. La page de la machine montre la phrase nouvelle ; celle du savoir-faire porte l'astuce
            self.aller("#/wiki/" + equipement_id, '.wiki-page[data-page="%s"] .wiki-page-grille' % equipement_id)
            en_bref = '.wiki-texte[data-rubrique="En bref"]'
            page.wait_for_selector(en_bref)
            phrases = self.textes(en_bref + " .wiki-phrase")
            self.assertTrue(any(p.startswith(phrase) for p in phrases), phrases)
            self.assertGreaterEqual(page.locator(en_bref + ' sup.wiki-ref[data-ot="%s"]' % OT_EN_COURS).count(), 1)
            self.assertIn("IA", self.texte(en_bref + " .wiki-origine"))
            self.assertEqual(page.locator("#wiki-a-trancher").count(), 0)
            self.assertEqual(page.locator('#wiki-references li[data-ot="%s"]' % OT_EN_COURS).count(), 1)
            self.aller("#/wiki/" + savoir_faire["id"], '.wiki-page[data-page="%s"] .wiki-page-grille' % savoir_faire["id"])
            self.assertIn(GESTE, self.texte(".wiki-page h1"))
            etapes = self.textes('.wiki-texte[data-rubrique="Étapes"] .wiki-phrase')
            self.assertTrue(any(p.startswith(ASTUCE.rstrip(".")) for p in etapes), etapes)

            # 6. La recherche du wiki trouve la page nouvelle (le savoir-faire) et l'OT sur un mot de l'astuce
            trouves = page.evaluate(RECHERCHE_JS, MOT_ASTUCE)
            self.assertIn(["page", savoir_faire["id"]], trouves)
            self.assertIn(["ot", OT_EN_COURS], trouves)
            self.assertIn(["page", page_machine["id"]], page.evaluate(RECHERCHE_JS, phrase))
            self.aller("#/wiki", "#wiki-accueil")
            page.fill("#wiki-champ-accueil", MOT_ASTUCE)
            page.wait_for_selector("#wiki-trouves:not([hidden]) .wiki-trouves-titre")
            a_l_ecran = page.evaluate(TROUVES_JS)
            self.assertIn(["page", savoir_faire["id"]], a_l_ecran)
            self.assertIn(["ot", OT_EN_COURS], a_l_ecran)
            self.assertGreaterEqual(page.locator('#wiki-trouves a[href="#/wiki/%s"]' % savoir_faire["id"]).count(), 1)
            print("  [recette] proposition %s validée : « %s » sur %s, savoir-faire %s créé ; recherche « %s » : %d résultats"
                  % (proposition["id"], phrase, page_machine["id"], savoir_faire["id"], MOT_ASTUCE, len(trouves)))

            # 7. Contradiction : le second OT, clôturé administrativement, traité par « faux-contradiction »
            page.evaluate("() => Ia.enregistrerReglages({ modele: 'faux-contradiction' })")
            premiere_phrase = premiere_phrase_de(page_machine["texte"])      # celle que le faux modèle contredit
            self.ouvrir_ot(ot_anterieur["id"])
            self.attendre_statut("Clôturé techniquement")
            self.cloturer_administrativement(ot_anterieur["id"])
            self.assertEqual(page.evaluate(FILE_JS), [ot_anterieur["id"]])
            bilan = self.traiter_la_file([ot_anterieur["id"]])
            self.assertIn(BILAN_UNE_PROPOSITION, bilan)
            self.assertEqual(len(self.faux.requetes_vers("/api/chat")), 2)
            self.assertEqual(self.faux.requetes_vers("/api/chat")[1]["corps"]["model"], "faux-contradiction")
            contradictoire = self.entree(ot_anterieur["id"])
            self.assertEqual((contradictoire["statut"], contradictoire["anterieure"]), ("à valider", "1"))
            contradictions = json.loads(contradictoire["contradictions"])
            self.assertEqual([(c["page"], c["pageCle"], c["phrase"], c["observation"], c["statut"]) for c in contradictions],
                             [(page_machine["titre"], "EQ:" + equipement_id, premiere_phrase, OBSERVATION_FAUX, "ouverte")])
            self.journal("a-valider")
            carte = '#wj-a-valider .wj-entree[data-entree="%s"]' % contradictoire["id"]
            page.wait_for_selector(carte)
            self.assertIn("Intervention antérieure", self.texte(carte + " .wj-meta"))
            enfants = page.evaluate("(s) => Array.from(document.querySelector(s).children).map((e) => e.className)", carte)
            self.assertIn("wj-contradictions", enfants[1])
            texte_contradiction = self.texte(carte + " .wj-contradictions")
            self.assertIn("Page « %s »" % page_machine["titre"], texte_contradiction)
            self.assertIn("Ce que dit la page : " + premiere_phrase, texte_contradiction)
            self.assertIn("Observation antérieure aux faits de la page : " + OBSERVATION_FAUX, texte_contradiction)
            self.assertEqual(page.locator(carte + " input.wj-choix").count(), 0, "une proposition avec contradiction se valide seule")
            self.assertIn("%s, %s" % (contradictoire["id"], ot_anterieur["id"]), self.texte(".wj-alerte-contradictions"))
            self.valider(contradictoire["id"])
            # La phrase contredite n'a pas été écrasée (D107) ; la contradiction est ouverte sur la page.
            page_machine = page.evaluate(PAGE_MACHINE_JS, equipement_id)
            self.assertIn(premiere_phrase, page_machine["texte"])
            self.assertEqual([(c["entreeId"], c["rang"], c["anterieure"]) for c in page.evaluate("(id) => Wiki.page(id).contradictions", equipement_id)],
                             [(contradictoire["id"], 0, True)])
            self.journal("contradictions")
            ligne = '.wj-contradiction[data-entree="%s"]' % contradictoire["id"]
            page.wait_for_selector(ligne)
            self.assertEqual(page.get_attribute(ligne + " .wj-lien-page", "href"), "#/wiki/" + equipement_id)

            # Sur la page : « À trancher » en tête, la phrase toujours là ; le responsable tranche « L'ancien reste »
            self.aller("#/wiki/" + equipement_id, '.wiki-page[data-page="%s"] #wiki-a-trancher' % equipement_id)
            bloc = '#wiki-a-trancher .wiki-contradiction[data-entree="%s"]' % contradictoire["id"]
            self.assertEqual(page.locator("#wiki-a-trancher .wiki-contradiction").count(), 1)
            self.assertEqual(page.get_attribute(bloc, "data-anterieure"), "oui")
            self.assertEqual(self.texte(bloc + " .wiki-cote-ot h3"), "Observation antérieure aux faits de la page")
            self.assertIn(premiere_phrase, self.texte(bloc + " .wiki-cote-page .wiki-phrase"))
            self.assertIn(OBSERVATION_FAUX, self.texte(bloc + " .wiki-observation"))
            self.assertTrue(any(p.startswith(premiere_phrase) for p in self.textes(en_bref + " .wiki-phrase")))
            self.assertEqual(page.evaluate("(s) => Array.from(document.querySelectorAll(s + ' button[data-decision]')).map((b) => [b.dataset.decision, b.textContent.trim()])", bloc),
                             [["ancien", "L'ancien reste"], ["nouveau", "Le nouveau remplace"], ["les deux", "Les deux sont vrais"]])
            page.fill(bloc + " .wiki-note", NOTE_DECISION)
            page.click(bloc + ' button[data-decision="ancien"]')
            self.attendre_toast(TOAST_DECISION)
            page.wait_for_selector("#wiki-a-trancher", state="detached")
            page.wait_for_selector('.wiki-page[data-page="%s"] .wiki-page-grille' % equipement_id)
            self.assertTrue(any(p.startswith(premiere_phrase) for p in self.textes(en_bref + " .wiki-phrase")), "l'ancien reste")
            # Les données : contradiction fermée, décision au journal (en mémoire et sur le disque), plus rien à trancher.
            fermee = json.loads(page.evaluate("(id) => Donnees.trouver('wiki_journal', id).contradictions", contradictoire["id"]))[0]
            self.assertEqual((fermee["statut"], fermee["decision"], fermee["note"]), ("fermée", "ancien", NOTE_DECISION))
            decision = page.evaluate("(ot) => Donnees.lignes('wiki_journal').filter((e) => e.nature === 'décision' && e.ot_id === ot).pop()",
                                     ot_anterieur["id"])
            self.assertIsNotNone(decision)
            self.assertEqual((decision["statut"], decision["motif"], decision["pages"]), ("appliquée", NOTE_DECISION, "EQ:" + equipement_id))
            self.assertEqual(json.loads(decision["contradictions"])[0]["entree"], contradictoire["id"])
            self.assertEqual(page.evaluate("(id) => Wiki.page(id).contradictions", equipement_id), [])
            sur_disque = ligne_csv(serveur.dossier, "wiki_journal", decision["id"])
            self.assertEqual((sur_disque["nature"], sur_disque["motif"]), ("décision", NOTE_DECISION))
            self.journal("contradictions")
            self.assertEqual(page.locator(ligne).count(), 0)
            self.journal("journal")
            ligne_decision = '#wj-toutes .wj-ligne[data-entree="%s"]' % decision["id"]
            page.wait_for_selector(ligne_decision)
            self.assertIn("Page « %s » : l'ancien reste" % page_machine["titre"], self.texte(ligne_decision))
            self.assertEqual(page.evaluate("(id) => document.querySelector('#wj-toutes .wj-ligne[data-entree=\"' + id + '\"]').dataset.statut",
                                           contradictoire["id"]), "validée")
            print("  [recette] contradiction de %s (%s) tranchée « l'ancien reste » : décision %s ; %d envois au faux fournisseur"
                  % (contradictoire["id"], ot_anterieur["id"], decision["id"], len(self.faux.requetes_vers("/api/chat"))))


if __name__ == "__main__":
    unittest.main()
