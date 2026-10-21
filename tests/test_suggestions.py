"""Écrans des suggestions de préventif (tâche T59, ARCHITECTURE.md §16.6 ; CDC D57, D58, D60 ; CS54).

Familles (le nom du test le dit) :
    liste      : cartes de l'onglet « Suggestions » = Suggestions.calculer(...).ouvertes (clés et ordre, par
                 l'attribut data-cle), égales au calcul Python indépendant ; badge de type en texte, textes,
                 liens vers l'équipement, les OT (5 au plus, puis « et n autres ») et les DI ; actions ;
                 encadré « Comprendre » (seuils en vigueur) ; onglet « Décisions » ; aucun « NaN »,
                 « Infinity », « undefined », « null » ;
    creer      : « Créer la gamme » (S1) : formulaire pré-rempli, gammes.csv identique à l'octet tant que
                 « Créer la gamme » n'est pas cliqué, puis gamme créée et suggestion traitée au journal ;
    ouvrir     : « Ouvrir la gamme » (S2) : rappel en tête de fiche ; enregistrer sans changement ne marque
                 rien ; un changement de périodicité marque la suggestion traitée ; check-list (S3) : un
                 seul marquage par visite ;
    ignorer    : motif vide refusé (fenêtre ouverte, journal inchangé), puis décision au journal, carte
                 retirée, ligne dans « Décisions » ; suggestion ignorée puis revenue : décision précédente
                 sur la carte, badge « revenue » ;
    cs54       : gammes.csv identique à l'octet après l'ouverture (OT échus générés), les onglets, la fiche
                 gamme et la fiche équipement avec encart, par les trois profils ; profils : technicien sans
                 onglets ni encarts (?onglet=suggestions → accueil et message), demandeur renvoyé ;
    telephone  : 375 px sans défilement horizontal, zones tactiles des cartes ≥ 48 px ;
    demo       : mode démo (dates décalées à aujourd'hui) : liste = calcul, puis liste vide (UI.vide).

Date : en mode serveur, ServeurPrevo copie la démo brute (datée de sa date de référence, lue dans
js/demo-donnees.js) ; l'horloge du navigateur est fixée à cette date, 10 h (Playwright
clock.set_fixed_time : les minuteurs continuent de tourner). Les rôles du lot 3 bis
(tests/fixtures/demo-scenarios.json), vérifiés par le générateur à cette date, valent donc à toute
heure et tout jour d'exécution. Le mode démo, lui, tourne à la date réelle.

Aucun identifiant du jeu de démo écrit en dur. Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_suggestions.py" -v
"""
import csv
import io
import re
import time
import unittest

from commun import RACINE, CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, scenarios_demo, url_fichier
from test_regles_suggestions import calcul_python, date_reference

SCENARIOS = scenarios_demo()
REFERENCE = date_reference()
HEURE_FIXE = REFERENCE + "T10:00:00"
MOTS_INTERDITS = re.compile(r"NaN|Infinity|undefined|\bnull\b")
PANNEAU = ".panneau-onglet[data-onglet='suggestions']"
CARTE = PANNEAU + " .sg-carte[data-cle='%s']"
LIGNE_DECISION = ".sg-decisions-tableau tbody tr:has(.sg-cle[data-cle='%s'])"
CALCUL_JS = "() => Suggestions.calculer(Donnees.aujourdhui())"
TROUVER_JS = "cle => Suggestions.trouver(cle, Donnees.aujourdhui())"

# Chaque toast affiché est noté à son apparition (un toast disparaît au bout de 4 s : le lire après
# coup échouerait au hasard ; même principe que tests/test_preventif.py).
NOTER_TOASTS_JS = """(() => {
  window.__toasts = [];
  let dernier = '';
  new MutationObserver(() => {
    const zone = document.getElementById('toast');
    const texte = zone && zone.classList.contains('visible') ? zone.textContent.trim() : '';
    if (texte && texte !== dernier) window.__toasts.push(texte);
    dernier = texte;
  }).observe(document, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['class'] });
})();"""

# Zones cliquables visibles de moins de 48 px dans les blocs désignés (même contrôle que
# PETITES_ZONES_JS de tests/test_ordres_lot2.py, limité aux blocs des suggestions).
PETITES_ZONES_JS = """(selecteur) => {
  const petites = [];
  for (const bloc of document.querySelectorAll(selecteur)) {
    for (const el of bloc.querySelectorAll('a, button, input, select, textarea, summary')) {
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height || el.closest('[hidden]') || el.type === 'hidden') continue;
      if (r.height < 47.5) petites.push(el.tagName + ' « ' + (el.textContent || el.value || '').trim().slice(0, 30) + ' » ' + Math.round(r.height) + ' px');
    }
  }
  return petites;
}"""


def lire_csv(dossier, nom):
    """Lignes d'un CSV de Prévo sur le disque, valeurs sans l'apostrophe de protection (§3.2)."""
    texte = (dossier / nom).read_text(encoding="utf-8-sig")
    return [{k: (v or "").strip().lstrip("'") for k, v in ligne.items()}
            for ligne in csv.DictReader(io.StringIO(texte), delimiter=";")]


def decisions_au_journal(dossier, cle):
    return [l for l in lire_csv(dossier, "journal.csv") if l["action"].startswith("suggestion %s " % cle)]


def espaces(texte):
    """Espaces simples (les espaces insécables des nombres et dates comptent comme des espaces)."""
    return re.sub(r"\s+", " ", texte or "").strip()


def date_fr(moment):
    return "%s/%s/%s" % (moment[8:10], moment[5:7], moment[:4])


def minuscule_initiale(texte):
    return texte[:1].lower() + texte[1:]


def attendre(condition, delai_s=15):
    fin = time.time() + delai_s
    while time.time() < fin:
        if condition():
            return True
        time.sleep(0.2)
    return condition()


class CasEcrans(CasNavigateur):

    def setUp(self):
        super().setUp()
        self.contexte.add_init_script(NOTER_TOASTS_JS)

    def serveur(self):
        serveur = ServeurPrevo()
        serveur.demarrer()
        self.addCleanup(serveur.arreter)
        return serveur

    def nouveau_contexte(self, largeur=1280, telephone=False):
        """Autre contexte (autre profil, téléphone) : même surveillance des erreurs et des toasts."""
        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": largeur, "height": 812 if telephone else 800},
                                               is_mobile=telephone, has_touch=telephone)
        self.addCleanup(contexte.close)
        contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        contexte.add_init_script(NOTER_TOASTS_JS)
        page = contexte.new_page()
        self.surveiller(page)
        return contexte, page

    def ouvrir(self, serveur, route="#/accueil", profil="responsable", nom="Responsable", technicien_id="",
               contexte=None, page=None):
        """Ouvre Prévo (mode serveur) à la date de référence de la démo ; attend la fin des écritures
        de l'ouverture (OT échus générés) avant de rendre la page."""
        contexte = contexte or self.contexte
        page = page or self.page
        contexte.clock.set_fixed_time(HEURE_FIXE)
        preregler_profil(contexte, profil, nom, technicien_id)
        page.goto(serveur.url + "/" + route)
        attendre_pret(page)
        page.wait_for_load_state("networkidle")
        self.assertEqual(page.evaluate("Donnees.aujourdhui()"), REFERENCE)
        return page

    def aller(self, page, route):
        page.evaluate("route => { location.hash = route; }", route)

    def attendre_toast_note(self, page, motif):
        return page.wait_for_function(
            "motif => (window.__toasts || []).find((texte) => new RegExp(motif).test(texte)) || null",
            arg=motif).json_value()

    def hrefs(self, racine, selecteur):
        return racine.locator(selecteur).evaluate_all("liens => liens.map((a) => a.getAttribute('href'))")

    def sans_defilement_horizontal(self, page):
        return page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")

    def onglet_suggestions(self, page):
        self.aller(page, "#/preventif?onglet=suggestions")
        page.wait_for_selector(PANNEAU + " .sg-carte")

    def onglet_decisions(self, page):
        page.click(".onglet[data-onglet='decisions']")
        page.wait_for_function("location.hash === '#/preventif?onglet=decisions'")
        page.wait_for_selector(".sg-decisions-tableau tbody tr", state="attached")    # tableau masqué sur téléphone


# ---------------------------------------------------------------------------
# liste : cartes, textes, liens, encadré « Comprendre », onglet « Décisions »
# ---------------------------------------------------------------------------

class TestListe(CasEcrans):

    def test_liste_egale_au_calcul_textes_liens_comprendre_et_decisions(self):
        serveur = self.serveur()
        page = self.ouvrir(serveur, "#/preventif?onglet=suggestions")
        page.wait_for_selector(PANNEAU + " .sg-carte")
        calcul = page.evaluate(CALCUL_JS)
        ouvertes = calcul["ouvertes"]
        self.assertEqual(sorted(s["cle"] for s in ouvertes), sorted(calcul_python(REFERENCE, dossier=serveur.dossier)))
        self.assertGreater(len(ouvertes), 5)
        affichees = page.eval_on_selector_all(PANNEAU + " .sg-carte", "cartes => cartes.map((c) => c.dataset.cle)")
        self.assertEqual(affichees, [s["cle"] for s in ouvertes])
        self.assertEqual(page.inner_text(".onglet[data-onglet='suggestions'] .badge").strip(), str(len(ouvertes)))
        self.assertIn(str(len(ouvertes)), page.inner_text(PANNEAU + " .sg-compteur"))
        self.assertEqual(page.locator(".pv-onglets .onglet").evaluate_all("o => o.map((e) => e.dataset.onglet)"),
                         ["gammes", "calendrier", "suggestions", "decisions"])

        for s in ouvertes:
            with self.subTest(cle=s["cle"]):
                carte = page.locator(CARTE % s["cle"])
                texte = espaces(carte.inner_text())
                self.assertEqual(espaces(carte.locator(".sg-type").inner_text()), s["regle"] + " · " + s["titre"])
                self.assertIn(espaces(s["texte"]), texte)
                self.assertIn(espaces(s["question"]), texte)
                if s["criticite"]:
                    self.assertIn("Criticité " + s["criticite"], texte)
                self.assertEqual(self.hrefs(carte, ".sg-titre a"), ["#/equipement/" + s["equipementId"]])
                self.assertEqual(self.hrefs(carte, ".sg-ots a"), ["#/ot/" + i for i in s["ots"][:5]])
                if len(s["ots"]) > 5:
                    reste = len(s["ots"]) - 5
                    self.assertIn("et %d autre%s" % (reste, "s" if reste > 1 else ""), espaces(carte.locator(".sg-ots").inner_text()))
                else:
                    self.assertNotIn("autre", carte.locator(".sg-ots").inner_text())
                self.assertEqual(self.hrefs(carte, ".sg-dis a"), ["#/di/" + i for i in s["dis"]])
                # CS53 (relecture finale) : les dates des faits, en période et à côté de chaque OT lié
                premier, dernier = s["dates"][0], s["dates"][-1]
                self.assertEqual(espaces(carte.locator(".sg-dates").inner_text()),
                                 "Dates : le %s" % date_fr(premier) if premier == dernier
                                 else "Dates : du %s au %s" % (date_fr(premier), date_fr(dernier)))
                self.assertEqual([t.strip("()") for t in carte.locator(".sg-ots .sg-date").all_inner_texts()],
                                 [date_fr(d) for d in list(reversed(s["dates"]))[:5]])
                if s["regle"] == "S1":
                    self.assertEqual(self.hrefs(carte, ".sg-actions a"),
                                     ["#/preventif/gamme/nouvelle?equipement=%s&suggestion=%s" % (s["equipementId"], s["cle"])])
                    self.assertEqual(espaces(carte.locator(".sg-actions a").inner_text()), "Créer la gamme")
                else:
                    self.assertEqual(self.hrefs(carte, ".sg-actions a"),
                                     ["#/preventif/gamme/%s?suggestion=%s" % (g, s["cle"]) for g in s["gammeIds"]])
                    self.assertEqual([espaces(t) for t in carte.locator(".sg-actions a").all_inner_texts()],
                                     ["Ouvrir la gamme " + g for g in s["gammeIds"]])
                self.assertEqual(espaces(carte.locator(".sg-actions button").inner_text()), "Ignorer…")
                self.assertEqual(carte.locator(".sg-actions button").get_attribute("aria-label"), "Ignorer la suggestion " + s["cle"])
                self.assertEqual(carte.locator(".sg-precedente").count(), 1 if s["decisionPrecedente"] else 0)
        # Au moins une carte a plus de 5 OT liés (« et n autres ») et une carte S3 a une DI liée.
        self.assertTrue(any(len(s["ots"]) > 5 for s in ouvertes))
        self.assertTrue(any(s["dis"] for s in ouvertes))

        # Encadré « Comprendre » : replié, définitions, règles avec les seuils en vigueur.
        comprendre = page.locator(PANNEAU + " details.sg-comprendre")
        self.assertIsNone(comprendre.get_attribute("open"))
        comprendre.locator("summary").click()
        texte = espaces(comprendre.inner_text())
        reglages = calcul["reglages"]
        self.assertIn("Prévo ne modifie jamais une gamme tout seul", texte)
        for regle in ("S1", "S2", "S3", "S4"):
            self.assertIn(regle + " · ", texte)
        self.assertIn("au moins %d pannes" % reglages["seuilPannes"], texte)
        self.assertIn("au moins %d visites" % reglages["visitesSansConstat"], texte)
        self.assertIn("%d derniers mois" % reglages["fenetreMois"], texte)
        self.assertIn(date_fr(reglages["debutFenetre"]), texte)
        self.assertIn("2 des 4 dernières visites", texte)
        self.assertNotRegex(page.inner_text("#contenu"), MOTS_INTERDITS)

        # Onglet « Décisions » : les décisions du journal, de la plus récente à la plus ancienne.
        self.onglet_decisions(page)
        decisions = calcul["decisions"]
        self.assertGreater(len(decisions), 0)
        cles = page.eval_on_selector_all(".sg-decisions-tableau tbody tr .sg-cle", "e => e.map((x) => x.dataset.cle)")
        self.assertEqual(cles, [d["cle"] for d in decisions])
        lignes = [espaces(t) for t in page.locator(".sg-decisions-tableau tbody tr").all_inner_texts()]
        for d, ligne in zip(decisions, lignes):
            self.assertIn(d["decision"], ligne)
            self.assertIn(espaces(d["texte"]), ligne)
            self.assertIn(date_fr(d["dateHeure"]), ligne)
        self.assertNotRegex(page.inner_text("#contenu"), MOTS_INTERDITS)


# ---------------------------------------------------------------------------
# creer, ouvrir : les actions qui mènent aux écrans du préventif
# ---------------------------------------------------------------------------

class TestActions(CasEcrans):

    def test_creer_la_gamme_formulaire_pre_rempli_rien_ecrit_avant_le_clic_puis_traitee(self):
        serveur = self.serveur()
        cle = SCENARIOS["suggestion_creer"]
        page = self.ouvrir(serveur, "#/preventif?onglet=suggestions")
        avant = (serveur.dossier / "gammes.csv").read_bytes()
        s = page.evaluate(TROUVER_JS, cle)
        self.assertEqual(s["regle"], "S1")
        page.click(CARTE % cle + " .sg-actions a")
        page.wait_for_selector("#pv-formulaire-gamme")
        self.assertEqual(page.evaluate("location.hash"),
                         "#/preventif/gamme/nouvelle?equipement=%s&suggestion=%s" % (s["equipementId"], cle))
        formulaire = "#pv-formulaire-gamme "
        self.assertEqual(page.input_value(formulaire + "[name=equipement_id]"), s["equipementId"])
        self.assertEqual(page.input_value(formulaire + "[name=libelle]"), "Prévenir : " + minuscule_initiale(s["causeLibelle"]))
        self.assertEqual(page.input_value(formulaire + "[name=declencheur]"), "date")
        rappel = page.locator(".sg-rappel[data-cle='%s']" % cle)
        self.assertIn(espaces(s["texte"]), espaces(rappel.inner_text()))
        page.wait_for_load_state("networkidle")
        self.assertEqual((serveur.dossier / "gammes.csv").read_bytes(), avant)
        self.assertEqual(decisions_au_journal(serveur.dossier, cle), [])

        page.fill(formulaire + "[name=periodicite_jours]", "30")
        page.click(formulaire + "button[type=submit]")
        page.wait_for_function("/^#\\/preventif\\/gamme\\/GAM-\\d+/.test(location.hash)")
        gamme_id = re.search(r"GAM-\d+", page.evaluate("location.hash")).group(0)
        self.assertTrue(attendre(lambda: decisions_au_journal(serveur.dossier, cle)))
        lignes = decisions_au_journal(serveur.dossier, cle)
        self.assertEqual([(l["table"], l["id_ligne"], l["action"]) for l in lignes],
                         [("equipements", s["equipementId"], "suggestion %s traitée : gamme %s créée" % (cle, gamme_id))])
        gamme = next(g for g in lire_csv(serveur.dossier, "gammes.csv") if g["id"] == gamme_id)
        self.assertEqual((gamme["equipement_id"], gamme["libelle"], gamme["declencheur"]),
                         (s["equipementId"], "Prévenir : " + minuscule_initiale(s["causeLibelle"]), "date"))
        self.assertIn(gamme_id, self.attendre_toast_note(page, "^Gamme GAM-"))

        self.onglet_suggestions(page)
        self.assertEqual(page.locator(CARTE % cle).count(), 0)
        self.onglet_decisions(page)
        ligne = espaces(page.locator(LIGNE_DECISION % cle).first.inner_text())
        self.assertIn("traitée", ligne)
        self.assertIn("gamme %s créée" % gamme_id, ligne)

    def test_ouvrir_la_gamme_enregistrer_sans_changement_ne_marque_rien_puis_periodicite_traitee(self):
        serveur = self.serveur()
        cle = SCENARIOS["suggestion_revoir"]
        page = self.ouvrir(serveur, "#/preventif?onglet=suggestions")
        avant = (serveur.dossier / "gammes.csv").read_bytes()
        s = page.evaluate(TROUVER_JS, cle)
        self.assertEqual(s["regle"], "S2")
        gamme_id = s["gammeIds"][0]
        page.click(CARTE % cle + " .sg-actions a[href='#/preventif/gamme/%s?suggestion=%s']" % (gamme_id, cle))
        page.wait_for_selector("#pv-formulaire-gamme")
        rappel = page.locator(".sg-rappel[data-cle='%s']" % cle)
        self.assertIn("Enregistrez la gamme ou modifiez sa check-list : la suggestion sera marquée traitée.",
                      espaces(rappel.inner_text()))
        self.assertIn(espaces(s["texte"]), espaces(rappel.inner_text()))
        # L'encart de la fiche ne répète pas la suggestion rappelée en tête.
        self.assertEqual(page.locator(".sg-encart .sg-carte[data-cle='%s']" % cle).count(), 0)
        page.wait_for_load_state("networkidle")
        self.assertEqual((serveur.dossier / "gammes.csv").read_bytes(), avant)

        formulaire = "#pv-formulaire-gamme "
        page.click(formulaire + "button[type=submit]")
        self.attendre_toast_note(page, "^Aucune modification")
        page.wait_for_load_state("networkidle")
        self.assertEqual(decisions_au_journal(serveur.dossier, cle), [])
        self.assertEqual((serveur.dossier / "gammes.csv").read_bytes(), avant)

        periodicite = int(next(g for g in lire_csv(serveur.dossier, "gammes.csv") if g["id"] == gamme_id)["periodicite_jours"])
        page.fill(formulaire + "[name=periodicite_jours]", str(periodicite - 15))
        page.click(formulaire + "button[type=submit]")
        self.assertTrue(attendre(lambda: decisions_au_journal(serveur.dossier, cle)))
        lignes = decisions_au_journal(serveur.dossier, cle)
        self.assertEqual(len(lignes), 1)
        self.assertEqual((lignes[0]["table"], lignes[0]["id_ligne"]), ("equipements", s["equipementId"]))
        self.assertTrue(lignes[0]["action"].startswith("suggestion %s traitée : gamme modifiée : " % cle), lignes[0]["action"])
        self.assertIn("periodicite_jours", lignes[0]["action"])
        gamme = next(g for g in lire_csv(serveur.dossier, "gammes.csv") if g["id"] == gamme_id)
        self.assertEqual(int(gamme["periodicite_jours"]), periodicite - 15)
        page.wait_for_function("cle => (document.querySelector('.sg-rappel[data-cle=\"' + cle + '\"]') || {}).textContent"
                               " && document.querySelector('.sg-rappel[data-cle=\"' + cle + '\"]').textContent.includes('marquée traitée')", arg=cle)
        self.onglet_suggestions(page)
        self.assertEqual(page.locator(CARTE % cle).count(), 0)

    def test_check_liste_modifiee_une_seule_decision_par_visite(self):
        serveur = self.serveur()
        cle = SCENARIOS["suggestion_anomalies"]
        page = self.ouvrir(serveur, "#/preventif?onglet=suggestions")
        s = page.evaluate(TROUVER_JS, cle)
        self.assertEqual(s["regle"], "S3")
        page.click(CARTE % cle + " .sg-actions a")
        page.wait_for_selector("#pv-ajout-operation")
        operations = page.locator(".pv-operations .pv-operation").count()
        for rang, texte in enumerate(("Contrôler les fixations (test)", "Nettoyer les capteurs (test)"), start=1):
            page.fill("#pv-nouvelle-operation", texte)
            page.click("#pv-ajout-operation button[type=submit]")
            page.wait_for_function("n => document.querySelectorAll('.pv-operations .pv-operation').length === n", arg=operations + rang)
            self.assertTrue(attendre(lambda: decisions_au_journal(serveur.dossier, cle)))
        page.wait_for_load_state("networkidle")
        lignes = decisions_au_journal(serveur.dossier, cle)
        self.assertEqual([(l["table"], l["id_ligne"], l["action"]) for l in lignes],
                         [("gammes", s["gammeIds"][0], "suggestion %s traitée : check-list modifiée" % cle)])
        self.assertIn("marquée traitée", page.inner_text(".sg-rappel[data-cle='%s']" % cle))


# ---------------------------------------------------------------------------
# ignorer : motif obligatoire, décision au journal ; suggestion ignorée puis revenue
# ---------------------------------------------------------------------------

class TestIgnorer(CasEcrans):

    def test_ignorer_motif_vide_refuse_puis_decision_au_journal_carte_retiree(self):
        serveur = self.serveur()
        cle = SCENARIOS["suggestion_allonger"]
        page = self.ouvrir(serveur, "#/preventif?onglet=suggestions")
        s = page.evaluate(TROUVER_JS, cle)
        self.assertEqual(s["regle"], "S4")
        gammes_avant = (serveur.dossier / "gammes.csv").read_bytes()
        journal_avant = (serveur.dossier / "journal.csv").read_bytes()
        page.click(CARTE % cle + " .sg-actions button")
        page.wait_for_selector("dialog[open] textarea[name=motif]")
        page.click("dialog[open] .fenetre-actions .btn-primaire")
        page.wait_for_selector("dialog[open] .erreur-champ:not([hidden])")
        self.assertIn("motif", page.inner_text("dialog[open] .erreur-champ"))
        self.assertEqual(page.locator("dialog[open]").count(), 1)
        page.wait_for_load_state("networkidle")
        self.assertEqual((serveur.dossier / "journal.csv").read_bytes(), journal_avant)

        motif = "Constructeur : visite mensuelle exigée par la garantie (test)"
        page.fill("dialog[open] textarea[name=motif]", motif)
        page.click("dialog[open] .fenetre-actions .btn-primaire")
        self.assertEqual(self.attendre_toast_note(page, "^Suggestion ignorée"), "Suggestion ignorée (inscrite au journal).")
        page.wait_for_selector("dialog[open]", state="detached")
        page.wait_for_function("sel => !document.querySelector(sel)", arg=CARTE % cle)
        self.assertTrue(attendre(lambda: decisions_au_journal(serveur.dossier, cle)))
        lignes = decisions_au_journal(serveur.dossier, cle)
        self.assertEqual([(l["table"], l["id_ligne"], l["action"], l["profil"]) for l in lignes],
                         [("gammes", s["gammeIds"][0], "suggestion %s ignorée : %s" % (cle, motif), "Responsable")])
        self.assertEqual((serveur.dossier / "gammes.csv").read_bytes(), gammes_avant)
        self.onglet_decisions(page)
        ligne = espaces(page.locator(LIGNE_DECISION % cle).first.inner_text())
        self.assertIn("ignorée", ligne)
        self.assertIn(motif, ligne)

    def test_ignorer_echap_pendant_l_ecriture_message_et_reaffichage_quand_meme(self):
        # Relecture finale : fenêtre fermée par Échap pendant l'écriture au journal → la décision écrite
        # doit quand même donner le message, retirer la carte et mettre le compteur à jour.
        serveur = self.serveur()
        cle = SCENARIOS["suggestion_allonger"]
        page = self.ouvrir(serveur, "#/preventif?onglet=suggestions")
        avant = page.evaluate(CALCUL_JS)["ouvertes"]
        page.evaluate("""() => { const original = Donnees.journaliser;
            Donnees.journaliser = (...args) => new Promise((fini) => setTimeout(() => fini(original(...args)), 1500)); }""")
        page.click(CARTE % cle + " .sg-actions button")
        page.wait_for_selector("dialog[open] textarea[name=motif]")
        page.fill("dialog[open] textarea[name=motif]", "Échap pendant l'écriture (test)")
        page.click("dialog[open] .fenetre-actions .btn-primaire")
        page.keyboard.press("Escape")
        page.wait_for_selector("dialog[open]", state="detached")
        self.assertEqual(self.attendre_toast_note(page, "^Suggestion ignorée"), "Suggestion ignorée (inscrite au journal).")
        page.wait_for_function("sel => !document.querySelector(sel)", arg=CARTE % cle)
        self.assertEqual(page.inner_text(".onglet[data-onglet='suggestions'] .badge").strip(), str(len(avant) - 1))
        self.assertTrue(attendre(lambda: decisions_au_journal(serveur.dossier, cle)))

    def test_suggestion_ignoree_puis_revenue_decision_precedente_et_badge(self):
        serveur = self.serveur()
        cle = SCENARIOS["suggestion_ignoree_revenue"]
        page = self.ouvrir(serveur, "#/preventif?onglet=suggestions")
        page.wait_for_selector(CARTE % cle)
        precedente = page.evaluate(TROUVER_JS, cle)["decisionPrecedente"]
        self.assertEqual(precedente["decision"], "ignorée")
        self.assertEqual(espaces(page.inner_text(CARTE % cle + " .sg-precedente")),
                         "Ignorée le %s : %s ; revenue sur de nouveaux faits" % (date_fr(precedente["dateHeure"]),
                                                                                  espaces(precedente["texte"]).rstrip(" .;")))
        self.assertNotIn(". ;", page.inner_text(CARTE % cle + " .sg-precedente"))     # motif fini par un point
        self.onglet_decisions(page)
        ligne = page.locator(LIGNE_DECISION % cle).first
        self.assertEqual(ligne.locator(".sg-revenue").inner_text().strip(), "revenue")
        self.assertEqual(page.locator(".sg-decisions-tableau .sg-revenue").count(),
                         sum(1 for d in page.evaluate(CALCUL_JS)["decisions"] if d["revenue"]))


# ---------------------------------------------------------------------------
# cs54 : rien n'est écrit par l'affichage ; profils
# ---------------------------------------------------------------------------

class TestCs54EtProfils(CasEcrans):

    def test_cs54_gammes_identique_a_l_octet_pour_les_trois_profils_et_profils(self):
        serveur = self.serveur()
        # Référence : le fichier de la démo d'origine (la copie du serveur avant toute ouverture) — l'ouverture
        # elle-même (génération des OT échus) est ainsi couverte (relecture finale).
        avant = (RACINE / "donnees" / "demo" / "gammes.csv").read_bytes()
        self.assertEqual((serveur.dossier / "gammes.csv").read_bytes(), avant)
        page = self.ouvrir(serveur, "#/accueil")
        self.assertEqual((serveur.dossier / "gammes.csv").read_bytes(), avant)
        cle_gamme, cle_equipement = SCENARIOS["suggestion_allonger"], SCENARIOS["suggestion_revoir"]
        gamme_id = page.evaluate(TROUVER_JS, cle_gamme)["gammeIds"][0]
        equipement_id = page.evaluate(TROUVER_JS, cle_equipement)["equipementId"]

        # Responsable : onglets, fiche gamme et fiche équipement avec leur encart.
        for route, attente in (("#/preventif?onglet=suggestions", PANNEAU + " .sg-carte"),
                               ("#/preventif?onglet=decisions", ".sg-decisions-tableau tbody tr"),
                               ("#/preventif/gamme/" + gamme_id, ".sg-encart .sg-carte[data-cle='%s']" % cle_gamme),
                               ("#/equipement/" + equipement_id, ".sg-encart .sg-carte[data-cle='%s']" % cle_equipement)):
            with self.subTest(profil="responsable", route=route):
                self.aller(page, route)
                page.wait_for_selector(attente)
                self.assertNotRegex(page.inner_text("#contenu"), MOTS_INTERDITS)
        attendues = sorted(s["cle"] for s in page.evaluate(CALCUL_JS)["ouvertes"] if s["equipementId"] == equipement_id)
        cartes = page.eval_on_selector_all(".sg-encart .sg-carte", "c => c.map((e) => e.dataset.cle)")
        self.assertEqual(sorted(cartes), attendues)
        page.wait_for_load_state("networkidle")
        self.assertEqual((serveur.dossier / "gammes.csv").read_bytes(), avant)

        # Technicien : ni onglets, ni encarts, ni rappel ; ?onglet=suggestions → accueil et message.
        technicien = next(t for t in lire_csv(serveur.dossier, "techniciens.csv") if t["actif"] != "0")
        contexte, page_t = self.nouveau_contexte()
        self.ouvrir(serveur, "#/preventif", "technicien", technicien["prenom"] + " " + technicien["nom"], technicien["id"],
                    contexte, page_t)
        page_t.wait_for_selector(".pv-onglets .onglet")
        self.assertEqual(page_t.locator(".pv-onglets .onglet").evaluate_all("o => o.map((e) => e.dataset.onglet)"),
                         ["gammes", "calendrier"])
        for onglet in ("suggestions", "decisions"):
            with self.subTest(profil="technicien", onglet=onglet):
                # Le message des deux essais est le même : la zone du toast est vidée entre les deux.
                page_t.evaluate("""() => { window.__toasts = []; const zone = document.getElementById('toast');
                    if (zone) { zone.classList.remove('visible'); zone.textContent = ''; } }""")
                self.aller(page_t, "#/preventif?onglet=" + onglet)
                page_t.wait_for_function("location.hash === '#/accueil'")
                self.assertEqual(self.attendre_toast_note(page_t, "Suggestions de préventif"),
                                 "L'écran « Suggestions de préventif » n'est pas disponible pour le profil Technicien.")
        for route, attente in (("#/preventif/gamme/%s?suggestion=%s" % (gamme_id, cle_gamme), ".pv-fiche .pv-check-liste h2"),
                               ("#/equipement/" + equipement_id, ".parc-preventif")):
            with self.subTest(profil="technicien", route=route):
                self.aller(page_t, route)
                page_t.wait_for_selector(attente)
                self.assertEqual(page_t.locator(".sg-encart, .sg-rappel, .sg-carte").count(), 0)
        page_t.wait_for_load_state("networkidle")
        self.assertEqual((serveur.dossier / "gammes.csv").read_bytes(), avant)

        # Demandeur : le Préventif lui est fermé ; fiche équipement sans encart.
        contexte, page_d = self.nouveau_contexte()
        self.ouvrir(serveur, "#/preventif?onglet=suggestions", "demandeur", "Paul Martin", "", contexte, page_d)
        page_d.wait_for_function("location.hash === '#/accueil'")
        self.assertIn("n'est pas disponible pour le profil Demandeur", self.attendre_toast_note(page_d, "pas disponible"))
        self.aller(page_d, "#/equipement/" + equipement_id)
        page_d.wait_for_selector(".parc-consignation")
        self.assertEqual(page_d.locator(".sg-encart, .sg-carte").count(), 0)
        page_d.wait_for_load_state("networkidle")
        self.assertEqual((serveur.dossier / "gammes.csv").read_bytes(), avant)


# ---------------------------------------------------------------------------
# telephone : 375 px
# ---------------------------------------------------------------------------

class TestTelephone(CasEcrans):

    def test_telephone_375_px_sans_defilement_horizontal_zones_de_48_px(self):
        serveur = self.serveur()
        contexte, page = self.nouveau_contexte(largeur=375, telephone=True)
        self.ouvrir(serveur, "#/preventif?onglet=suggestions", contexte=contexte, page=page)
        page.wait_for_selector(PANNEAU + " .sg-carte")
        # Relecture finale : l'onglet actif est dans la partie visible de la barre d'onglets (qui défile)
        page.wait_for_function("""() => { const b = document.querySelector(".onglet[data-onglet='suggestions']");
            const r = b.closest('.barre-onglets').getBoundingClientRect(); const p = b.getBoundingClientRect();
            return p.left >= r.left - 1 && p.right <= r.right + 1; }""")
        self.assertTrue(self.sans_defilement_horizontal(page), "onglet ramené sans faire défiler la page")
        page.click(PANNEAU + " details.sg-comprendre summary")
        self.assertTrue(self.sans_defilement_horizontal(page), "onglet Suggestions")
        self.assertEqual(page.evaluate(PETITES_ZONES_JS, PANNEAU + " .sg-carte, " + PANNEAU + " .sg-comprendre"), [])

        self.onglet_decisions(page)
        self.assertFalse(page.is_visible(".sg-decisions-tableau"))
        page.wait_for_selector(".sg-decisions-cartes .sg-decision")
        self.assertTrue(self.sans_defilement_horizontal(page), "onglet Décisions")
        self.assertEqual(page.evaluate(PETITES_ZONES_JS, ".sg-decisions-cartes"), [])

        cle = SCENARIOS["suggestion_revoir"]
        s = page.evaluate(TROUVER_JS, cle)
        self.aller(page, "#/equipement/" + s["equipementId"])
        page.wait_for_selector(".sg-encart .sg-carte[data-cle='%s']" % cle)
        self.assertTrue(self.sans_defilement_horizontal(page), "fiche équipement avec encart")
        self.assertEqual(page.evaluate(PETITES_ZONES_JS, ".sg-encart"), [])

        self.aller(page, "#/preventif/gamme/%s?suggestion=%s" % (s["gammeIds"][0], cle))
        page.wait_for_selector(".sg-rappel[data-cle='%s']" % cle)
        self.assertTrue(self.sans_defilement_horizontal(page), "fiche gamme avec rappel")
        self.assertEqual(page.evaluate(PETITES_ZONES_JS, ".sg-rappel, .sg-encart"), [])

        self.aller(page, "#/preventif?onglet=suggestions")
        page.wait_for_selector(CARTE % cle)
        page.click(CARTE % cle + " .sg-actions button")
        page.wait_for_selector("dialog[open] textarea[name=motif]")
        self.assertTrue(self.sans_defilement_horizontal(page), "fenêtre « Ignorer »")
        self.assertEqual(page.evaluate(PETITES_ZONES_JS, "dialog[open]"), [])
        page.keyboard.press("Escape")
        page.wait_for_selector("dialog[open]", state="detached")


# ---------------------------------------------------------------------------
# demo : mode démo, date réelle
# ---------------------------------------------------------------------------

class TestDemo(CasEcrans):

    def test_demo_liste_egale_au_calcul_puis_liste_vide(self):
        preregler_profil(self.contexte, "responsable", "Responsable")
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        page = self.page
        self.onglet_suggestions(page)
        attendues = page.evaluate("() => Suggestions.calculer(Donnees.aujourdhui()).ouvertes.map((s) => s.cle)")
        self.assertGreater(len(attendues), 0)
        self.assertEqual(page.eval_on_selector_all(PANNEAU + " .sg-carte", "c => c.map((e) => e.dataset.cle)"), attendues)
        self.assertNotRegex(page.inner_text("#contenu"), MOTS_INTERDITS)

        # Toutes ignorées (en mémoire) : liste vide expliquée, compteur à 0.
        page.evaluate("""async () => { for (const s of Suggestions.ouvertes(Donnees.aujourdhui())) {
            await Suggestions.ignorer(s.cle, 'essai de la liste vide'); } }""")
        page.evaluate("App.reafficher()")
        page.wait_for_selector(PANNEAU + " .vide")
        self.assertEqual(page.locator(PANNEAU + " .sg-carte").count(), 0)
        self.assertEqual(page.inner_text(".onglet[data-onglet='suggestions'] .badge").strip(), "0")
        self.onglet_decisions(page)
        self.assertGreaterEqual(page.locator(".sg-decisions-tableau tbody tr .sg-cle").count(), len(attendues))
        self.assertNotRegex(page.inner_text("#contenu"), MOTS_INTERDITS)


if __name__ == "__main__":
    unittest.main()
