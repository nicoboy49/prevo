"""Tests de RG8 à l'écran de l'OT, passer outre (T438 ; D186, D191 ; CS178, CS180 ; conception L2-L3 §7.4 et §7.6).

Application ouverte en mode serveur (serveur.py sur une copie temporaire du jeu de démo, dates non décalées), CSV relus
sur le disque. Le responsable voit le refus en direct (bandeau du nouvel OT et de la préparation), puis la fenêtre
« Habilitation exigée non valide » à l'enregistrement (nouvel OT, préparation, bouton « Planifier ») : « Passer outre
et enregistrer » reste inactif sans la case et le motif (QUESTIONS-L2-L6 Q7) ; Annuler n'écrit rien et redit le refus ;
passer outre écrit l'affectation, et l'action du journal de l'écriture garde le profil, le poste, l'heure, l'OT et
l'habilitation ; la fiche dit ensuite « Affecté sans habilitation BR valide : dérogation du responsable le … ». Une
dérogation notée vaut pour l'acte suivant (préparer puis « Planifier » ne redemande pas). Le technicien voit les
bandeaux, jamais la case ni le bouton : aucune fenêtre ne lui est ouverte, même par l'API. Un OT sans exigence ne
montre ni bandeau ni fenêtre.

T440 (D191, CS180) : champ « Habilitation exigée par l'OT » (ordres_travail.habilitation_requise) au nouvel OT et à la
préparation, avec sa liste et son aide ; posée sur un OT dont l'équipement n'exige rien, elle bloque l'affectation d'un
technicien qui ne l'a pas (refus en direct, fenêtre « Cet OT l'exige (OT) ») ; retirée, elle ne bloque plus ; l'en-tête
de la fiche et le bon de travail disent « Habilitation exigée : BR (équipement), H0V (OT) ».

Aucun identifiant du jeu de démo écrit en dur (rôles de tests/fixtures/demo-scenarios.json) ; date fixe 20/11/2026 ;
un serveur pour la classe, chaque test sur ses propres OT.

Lancer depuis la racine du projet (au travers du verrou des navigateurs) :
    py -X utf8 -m unittest discover -s tests -p "test_rg8_ecrans.py" -v
"""
import csv
import io
import unittest
from pathlib import Path

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, scenarios_demo

SCENARIOS = scenarios_demo()
EQ_BR = SCENARIOS["equipement_br"]                     # exige la BR
TEC_ECHUE = SCENARIOS["technicien_br_echue"]           # BR échue
OT_A_PLANIFIER = SCENARIOS["ot_a_planifier"]           # « Préparé », équipement sans exigence

DATE = "2026-11-20"
MOTIF = "Électricien du site présent ; consignation faite par lui"
DEROGER = {"passerOutreHabilitation": True, "motifDerogation": MOTIF}

FENETRE = "dialog.ot-fenetre-derogation"
CASE = FENETRE + " [name=passer_outre]"
CHAMP_MOTIF = FENETRE + " [name=motif]"
PASSER_OUTRE = FENETRE + " .ot-passer-outre"
ANNULER = FENETRE + " .fenetre-actions .btn-fantome"
ZONE_NOUVEL_OT = "#form-nouvel-ot .ot-zone-habilitation"
ZONE_PREPARATION = "#form-preparation .ot-zone-habilitation"
BANDEAU_DEROGATION = ".ot-bandeau-etat .alerte.attention .alerte-texte"


def lire_csv(dossier, nom):
    texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte), delimiter=";"))


def brut(valeur):
    valeur = (valeur or "").strip()
    return valeur[1:] if valeur.startswith("'") else valeur


def marqueur(technicien, date, liste, motif=MOTIF):
    return "dérogation habilitation : %s le %s sans %s ; motif : %s" % (technicien, date, liste, motif)


def date_fr(iso):
    return "%s/%s/%s" % (iso[8:10], iso[5:7], iso[0:4])


class TestRg8Ecrans(CasNavigateur):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serveur = ServeurPrevo()
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)
        cls.dossier = cls.serveur.dossier
        technicien = next(t for t in lire_csv(cls.dossier, "techniciens.csv") if t["id"] == TEC_ECHUE)
        cls.nom_echue = "%s %s" % (brut(technicien["prenom"]), brut(technicien["nom"]))
        cls.echeance_br = max(brut(h["date_echeance"]) for h in lire_csv(cls.dossier, "habilitations.csv")
                              if h["technicien_id"] == TEC_ECHUE and brut(h["intitule"]).upper() == "BR")
        cls.repere_br = brut(next(e for e in lire_csv(cls.dossier, "equipements.csv") if e["id"] == EQ_BR)["repere"])

    # -- outils ----------------------------------------------------------------------------------

    def ouvrir(self, route="#/ot", profil="responsable", technicien_id=""):
        preregler_profil(self.contexte, profil, technicien_id=technicien_id)
        self.page.goto(self.serveur.url + "/" + route)
        attendre_pret(self.page)
        self.page.wait_for_load_state("networkidle")

    def aller(self, route):
        self.page.evaluate("location.hash = %r" % route)

    def appeler(self, expression, *arguments):
        return self.page.evaluate(expression, list(arguments))

    def nouvel_ot_par_api(self, titre, **valeurs):
        """OT « Créé » sur l'équipement à BR (sans technicien sauf valeurs), par l'écriture elle-même."""
        options = valeurs.pop("options", None)
        return self.appeler("([valeurs, options]) => Ordres.creer(valeurs, options)",
                            dict({"equipement_id": EQ_BR, "titre": titre, "type": "correctif différé", "priorite": "P3"},
                                 **valeurs), options)

    def preparer_par_api(self, ot_id):
        self.assertEqual(self.appeler("([id]) => Ordres.changerStatut(id, 'Créé', 'Préparé')", ot_id), "Préparé")

    def affecter_sans_controle(self, ot_id, technicien, date):
        """Affectation d'avant la 2.2 (RG8 non rétroactive) : écrite sans contrôle ni journal."""
        self.appeler("""([id, technicien, date]) => Donnees.modifier('ordres_travail', (lignes) => {
            Object.assign(lignes.find((o) => o.id === id), { technicien_id: technicien, date_prevue: date }); },
            { journal: false })""", ot_id, technicien, date)

    def ot(self, ot_id):
        return next(o for o in lire_csv(self.dossier, "ordres_travail.csv") if o["id"] == ot_id)

    def nombre_ot(self):
        return len(lire_csv(self.dossier, "ordres_travail.csv"))

    def journal(self):
        return lire_csv(self.dossier, "journal.csv")

    def entrees(self, ot_id):
        return [j for j in self.journal() if j["table"] == "ordres_travail" and j["id_ligne"] == ot_id]

    def br_echue(self):
        return "BR (échue le %s)" % date_fr(self.echeance_br)

    def constat(self):
        return "%s (%s) n'a pas d'habilitation valide au %s pour : %s." % (
            self.nom_echue, TEC_ECHUE, date_fr(DATE), self.br_echue())

    def attendre_fiche(self, ot_id):
        self.page.wait_for_function(
            "(id) => { const n = document.querySelector('.ot-fiche .ot-numero'); return n && n.textContent === id; }",
            arg=ot_id)

    def attendre_statut(self, statut):
        self.page.wait_for_function(
            "(s) => { const b = document.querySelector('.ot-badges .badge.statut'); return b && b.textContent === s; }",
            arg=statut)

    def ouvrir_fiche(self, ot_id, onglet=None):
        self.aller("#/ot/" + ot_id)
        self.attendre_fiche(ot_id)
        if onglet:
            self.page.click(".onglet[data-onglet='%s']" % onglet)

    def attendre_toast(self, texte):
        # text_content, pas inner_text : le toast entre par une transition de visibility (css/style.css §10), et
        # inner_text d'un élément encore « hidden » au premier instant rend '' (échec au hasard des délais).
        self.page.wait_for_function("(t) => document.getElementById('toast').textContent.includes(t)", arg=texte)
        return self.page.text_content("#toast")

    def attendre_fenetre(self):
        """La fenêtre du responsable : titre, constat, exigence ; « Passer outre » inactif à l'ouverture."""
        fenetre = self.page.wait_for_selector(FENETRE)
        self.assertEqual(fenetre.query_selector("h2").inner_text(), "Habilitation exigée non valide")
        texte = fenetre.inner_text()
        self.assertIn(self.constat(), texte)
        self.assertIn("Je passe outre, sous ma responsabilité. Le journal notera qui, quand, cet OT et ces habilitations.",
                      texte)
        self.assertIn("Motif de la dérogation", texte)
        self.assertEqual(self.page.inner_text(PASSER_OUTRE).strip(), "Passer outre et enregistrer")
        self.assertIn("btn-danger", self.page.get_attribute(PASSER_OUTRE, "class"))
        self.assertTrue(self.page.is_disabled(PASSER_OUTRE))
        self.assertFalse(self.page.is_checked(CASE))
        return texte

    def passer_outre(self, motif=MOTIF):
        """Case cochée et motif écrit, dans les deux ordres : le bouton ne s'active qu'avec les deux (Q7)."""
        self.page.fill(CHAMP_MOTIF, motif)
        self.assertTrue(self.page.is_disabled(PASSER_OUTRE))          # motif sans la case
        self.page.check(CASE)
        self.assertTrue(self.page.is_enabled(PASSER_OUTRE))
        self.page.fill(CHAMP_MOTIF, "   ")
        self.assertTrue(self.page.is_disabled(PASSER_OUTRE))          # case sans motif (blanc)
        self.page.fill(CHAMP_MOTIF, motif)
        self.assertTrue(self.page.is_enabled(PASSER_OUTRE))
        self.page.click(PASSER_OUTRE)
        self.page.wait_for_selector(FENETRE, state="detached")

    def annuler(self):
        self.page.click(ANNULER)
        self.page.wait_for_selector(FENETRE, state="detached")

    def verifier_entree_derogation(self, entree, ot_id):
        """Qui (profil, poste), quand (date_heure), quel OT (id_ligne), quelle habilitation (le marqueur)."""
        self.assertEqual((entree["table"], entree["id_ligne"], entree["profil"], entree["poste"]),
                         ("ordres_travail", ot_id, "Responsable", "Poste test"))
        self.assertRegex(entree["date_heure"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}")
        self.assertTrue(entree["action"].endswith(" ; " + marqueur(TEC_ECHUE, DATE, "BR (échue)")), entree["action"])

    def bandeau_derogation_attendu(self, entree):
        return "Affecté sans habilitation BR valide : dérogation du responsable le %s à %s. Motif : %s" % (
            date_fr(entree["date_heure"]), entree["date_heure"][11:16], MOTIF)

    def choisir_affectation(self, formulaire, technicien, date):
        self.page.select_option(formulaire + " [name=technicien_id]", technicien)
        self.page.fill(formulaire + " [name=date_prevue]", date)
        self.page.dispatch_event(formulaire + " [name=date_prevue]", "change")

    # -- nouvel OT ---------------------------------------------------------------------------------

    def test_nouvel_ot_refus_en_direct_annuler_puis_passer_outre_et_journal(self):
        self.ouvrir("#/ot/nouveau?equipement=" + EQ_BR)
        page = self.page
        page.wait_for_selector("#form-nouvel-ot")
        page.fill("#form-nouvel-ot [name=titre]", "T438 — nouvel OT")
        self.assertEqual(page.locator(ZONE_NOUVEL_OT + " .alerte").count(), 0)     # pas encore de technicien
        self.choisir_affectation("#form-nouvel-ot", TEC_ECHUE, DATE)
        bandeau = page.wait_for_selector(ZONE_NOUVEL_OT + " .alerte.important").inner_text()
        self.assertIn("Habilitation exigée non valide : " + self.constat(), bandeau)
        self.assertIn("L'affectation est refusée ; en enregistrant, vous pourrez passer outre, sous votre "
                      "responsabilité, avec un motif.", bandeau)

        # Annuler : rien n'est écrit, le refus est redit, le formulaire reste.
        avant_ot, avant_journal = self.nombre_ot(), len(self.journal())
        page.click("#form-nouvel-ot button[type=submit]")
        texte = self.attendre_fenetre()
        self.assertIn("Cet OT l'exige (équipement %s). L'affectation est refusée." % self.repere_br, texte)
        self.annuler()
        toast = self.attendre_toast("Affectation refusée")
        self.assertIn("Seul le responsable peut passer outre.", toast)
        self.assertEqual(page.evaluate("location.hash.split('?')[0]"), "#/ot/nouveau")
        self.assertEqual((self.nombre_ot(), len(self.journal())), (avant_ot, avant_journal))
        self.assertTrue(page.is_enabled("#form-nouvel-ot button[type=submit]"))

        # Passer outre : l'OT est créé avec l'affectation, la dérogation est dans l'action du journal de la création.
        page.click("#form-nouvel-ot button[type=submit]")
        self.attendre_fenetre()
        self.passer_outre()
        page.wait_for_selector(".ot-fiche .ot-numero")
        ot_id = page.inner_text(".ot-fiche .ot-numero")
        ligne = self.ot(ot_id)
        self.assertEqual((ligne["technicien_id"], ligne["date_prevue"], ligne["statut"]), (TEC_ECHUE, DATE, "Créé"))
        self.assertEqual(self.nombre_ot(), avant_ot + 1)
        entrees = self.entrees(ot_id)
        self.assertEqual([j["action"] for j in entrees],
                         ["création — création de l'OT (manuel) ; " + marqueur(TEC_ECHUE, DATE, "BR (échue)")])
        self.verifier_entree_derogation(entrees[0], ot_id)
        # La fiche le dit (tous profils) ; la préparation ne redit pas le refus : la dérogation vaut.
        self.assertEqual(page.inner_text(BANDEAU_DEROGATION), self.bandeau_derogation_attendu(entrees[0]))
        page.click(".onglet[data-onglet='preparation']")
        page.wait_for_selector("#form-preparation")
        self.assertEqual(page.locator(ZONE_PREPARATION + " .alerte").count(), 0)

    # -- préparation, puis « Planifier » sans redemander ----------------------------------------

    def test_preparation_passer_outre_puis_planifier_ne_redemande_pas(self):
        self.ouvrir()
        ot_id = self.nouvel_ot_par_api("T438 — préparation")
        self.preparer_par_api(ot_id)
        self.ouvrir_fiche(ot_id, "preparation")
        page = self.page
        page.wait_for_selector("#form-preparation")
        self.choisir_affectation("#form-preparation", TEC_ECHUE, DATE)
        self.assertIn(self.constat(), page.wait_for_selector(ZONE_PREPARATION + " .alerte.important").inner_text())
        page.click("#form-preparation button[type=submit]")
        self.attendre_fenetre()
        self.passer_outre()
        self.attendre_toast("Préparation enregistrée.")
        self.assertEqual((self.ot(ot_id)["technicien_id"], self.ot(ot_id)["date_prevue"]), (TEC_ECHUE, DATE))
        derniere = self.entrees(ot_id)[-1]
        self.assertTrue(derniere["action"].startswith("modification : "), derniere["action"])
        self.assertIn(" — préparation ; ", derniere["action"])
        self.verifier_entree_derogation(derniere, ot_id)
        page.wait_for_selector(BANDEAU_DEROGATION)
        self.assertEqual(page.inner_text(BANDEAU_DEROGATION), self.bandeau_derogation_attendu(derniere))

        # « Planifier » : même OT, technicien, date et habilitations → aucune fenêtre, rien de plus au journal.
        page.click(".ot-actions button[data-action='transition'][data-cible='Planifié']")
        self.attendre_statut("Planifié")
        self.assertEqual(page.locator("dialog").count(), 0)
        self.assertEqual(self.entrees(ot_id)[-1]["action"], "modification : statut — statut Préparé → Planifié")
        self.assertEqual(sum("dérogation habilitation" in j["action"] for j in self.entrees(ot_id)), 1)

    # -- bouton « Planifier » d'une affectation d'avant la 2.2 ---------------------------------

    def test_bouton_planifier_refuse_annuler_puis_passer_outre(self):
        self.ouvrir()
        ot_id = self.nouvel_ot_par_api("T438 — planifier")
        self.preparer_par_api(ot_id)
        self.affecter_sans_controle(ot_id, TEC_ECHUE, DATE)
        self.ouvrir_fiche(ot_id, "preparation")
        page = self.page
        self.assertIn(self.constat(), page.wait_for_selector(ZONE_PREPARATION + " .alerte.important").inner_text())
        self.assertEqual(page.locator(BANDEAU_DEROGATION).count(), 0)               # aucune dérogation notée

        planifier = ".ot-actions button[data-action='transition'][data-cible='Planifié']"
        avant = len(self.entrees(ot_id))
        page.click(planifier)
        self.attendre_fenetre()
        self.annuler()
        self.attendre_toast("Affectation refusée")
        self.assertEqual(self.statut_affiche(), "Préparé")
        self.assertEqual((self.ot(ot_id)["statut"], len(self.entrees(ot_id))), ("Préparé", avant))

        page.click(planifier)
        self.attendre_fenetre()
        self.passer_outre()
        self.attendre_statut("Planifié")
        self.assertEqual(self.ot(ot_id)["statut"], "Planifié")
        derniere = self.entrees(ot_id)[-1]
        self.assertEqual(derniere["action"], "modification : statut — statut Préparé → Planifié ; "
                         + marqueur(TEC_ECHUE, DATE, "BR (échue)"))
        self.verifier_entree_derogation(derniere, ot_id)
        page.wait_for_selector(BANDEAU_DEROGATION)
        self.assertEqual(page.inner_text(BANDEAU_DEROGATION), self.bandeau_derogation_attendu(derniere))

    def statut_affiche(self):
        return self.page.inner_text(".ot-badges .badge.statut")

    # -- technicien : bandeaux vus, aucun moyen de passer outre (CS178) ----------------------------

    def test_technicien_voit_les_bandeaux_sans_case_ni_bouton(self):
        self.ouvrir()
        avec_derogation = self.nouvel_ot_par_api("T438 — technicien, dérogation", technicien_id=TEC_ECHUE,
                                                 date_prevue=DATE, options=DEROGER)
        sans_derogation = self.nouvel_ot_par_api("T438 — technicien, sans dérogation")
        self.preparer_par_api(sans_derogation)
        self.affecter_sans_controle(sans_derogation, TEC_ECHUE, DATE)
        entree = self.entrees(avec_derogation)[-1]

        # Une page neuve sous le profil du technicien concerné.
        self.contexte.close()
        self.contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
        self.contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        self.page = self.contexte.new_page()
        self.surveiller(self.page)
        self.ouvrir("#/ot/" + avec_derogation, profil="technicien", technicien_id=TEC_ECHUE)
        page = self.page
        self.assertFalse(page.evaluate("App.estResponsable()"))
        self.attendre_fiche(avec_derogation)
        self.assertEqual(page.inner_text(BANDEAU_DEROGATION), self.bandeau_derogation_attendu(entree))

        self.ouvrir_fiche(sans_derogation, "preparation")
        bandeau = page.wait_for_selector(ZONE_PREPARATION + " .alerte.important .alerte-texte").inner_text()
        self.assertEqual(bandeau, "Habilitation exigée non valide : " + self.constat()
                         + " Seul le responsable peut passer outre.")
        self.assertNotIn("vous pourrez passer outre", bandeau)
        self.assertEqual(page.locator("#form-preparation button[type=submit]").count(), 0)
        self.assertEqual(page.locator("button[data-cible='Planifié']").count(), 0)

        # Même par l'API : aucune fenêtre ; l'écriture avec dérogation est refusée, rien n'est écrit.
        avant_ot, avant_journal = self.nombre_ot(), len(self.journal())
        infos = {"otId": sans_derogation, "technicienId": TEC_ECHUE, "date": DATE,
                 "manquantes": [{"intitule": "BR", "raison": "echue", "echeance": self.echeance_br,
                                 "obtention": "", "origines": ["equipement"]}]}
        self.assertIsNone(self.appeler("([infos]) => Ordres.demanderDerogation(infos)", infos))
        resultat = self.appeler("""async ([valeurs]) => {
            try { await Ordres.avecDerogation((options) => Ordres.creer(valeurs, options)); return { accepte: true }; }
            catch (erreur) { return { refus: erreur.message, habilitation: Boolean(erreur.habilitation) }; } }""",
                                {"equipement_id": EQ_BR, "titre": "T438 — technicien", "type": "correctif différé",
                                 "priorite": "P3", "technicien_id": TEC_ECHUE, "date_prevue": DATE})
        self.assertEqual(resultat.get("habilitation"), True, resultat)
        self.assertTrue(resultat["refus"].startswith("Affectation refusée : "), resultat)
        self.assertEqual(page.locator("dialog").count(), 0)
        self.assertEqual(page.locator("[name=passer_outre], .ot-passer-outre").count(), 0)
        self.assertEqual((self.nombre_ot(), len(self.journal())), (avant_ot, avant_journal))

    # -- OT sans exigence (CS180) : ni bandeau ni fenêtre -------------------------------------------

    def test_ot_sans_exigence_ni_bandeau_ni_fenetre(self):
        self.ouvrir()
        page = self.page
        equipement = self.ot(OT_A_PLANIFIER)["equipement_id"]
        self.assertEqual(page.evaluate("(id) => Ordres.habilitationsExigees(id)", OT_A_PLANIFIER), [])
        nouveau = self.appeler("([v]) => Equipe.creerTechnicien(v)", {"nom": "Sans habilitation", "prenom": "Écran"})

        self.aller("#/ot/nouveau?equipement=" + equipement)
        page.wait_for_selector("#form-nouvel-ot")
        page.fill("#form-nouvel-ot [name=titre]", "T438 — sans exigence")
        self.choisir_affectation("#form-nouvel-ot", nouveau, DATE)
        self.assertEqual(page.locator(ZONE_NOUVEL_OT + " .alerte").count(), 0)
        page.click("#form-nouvel-ot button[type=submit]")
        page.wait_for_selector(".ot-fiche .ot-numero")
        ot_id = page.inner_text(".ot-fiche .ot-numero")
        self.assertEqual(page.locator("dialog").count(), 0)
        self.assertEqual([j["action"] for j in self.entrees(ot_id)], ["création — création de l'OT (manuel)"])
        self.assertEqual(page.locator(BANDEAU_DEROGATION).count(), 0)

        # Préparation puis « Planifier » de l'OT à planifier, sur ce technicien sans habilitation.
        self.ouvrir_fiche(OT_A_PLANIFIER, "preparation")
        page.wait_for_selector("#form-preparation")
        self.choisir_affectation("#form-preparation", nouveau, DATE)
        self.assertEqual(page.locator(ZONE_PREPARATION + " .alerte").count(), 0)
        page.click(".ot-actions button[data-action='transition'][data-cible='Planifié']")
        self.attendre_statut("Planifié")
        self.assertEqual(page.locator("dialog").count(), 0)
        ligne = self.ot(OT_A_PLANIFIER)
        self.assertEqual((ligne["statut"], ligne["technicien_id"], ligne["date_prevue"]), ("Planifié", nouveau, DATE))
        self.assertFalse(any("dérogation" in j["action"] or "habilitation" in j["action"]
                             for j in self.entrees(OT_A_PLANIFIER)))

    # -- habilitation exigée par l'OT (T440 ; D191, CS180) -------------------------------------------

    def equipement_sans_exigence(self):
        equipement = self.ot(OT_A_PLANIFIER)["equipement_id"]
        ligne = next(e for e in lire_csv(self.dossier, "equipements.csv") if e["id"] == equipement)
        self.assertEqual(brut(ligne["habilitation_requise"]), "")
        return equipement

    def technicien_sans_habilitation(self, prenom):
        return self.appeler("([v]) => Equipe.creerTechnicien(v)", {"nom": "Sans habilitation", "prenom": prenom})

    def saisir_exigence(self, formulaire, valeur):
        self.page.fill(formulaire + " [name=habilitation_requise]", valeur)
        self.page.dispatch_event(formulaire + " [name=habilitation_requise]", "change")

    def aide_exigence(self, formulaire):
        return self.page.inner_text(formulaire + " [data-champ=habilitation_requise] .aide")

    def attendre_sans_refus(self, zone):
        self.page.wait_for_function("(z) => !document.querySelector(z + ' .alerte')", arg=zone)

    def habilitation_du_bon(self, ot_id):
        """La ligne « Habilitation exigée » du bon de travail (bonDeTravailHtml, sans lancer l'impression)."""
        return self.appeler("""([id]) => {
            const bon = UI.element(Ordres.bonDeTravailHtml(Donnees.trouver('ordres_travail', id)));
            const dt = Array.from(bon.querySelectorAll('.bt-equipement dt')).find((d) => d.textContent === 'Habilitation exigée');
            return dt ? dt.nextElementSibling.textContent : null; }""", ot_id)

    def test_nouvel_ot_exigence_de_l_ot_bloque_sans_exigence_de_l_equipement_retiree_ne_bloque_plus(self):
        equipement = self.equipement_sans_exigence()
        self.ouvrir()
        technicien = self.technicien_sans_habilitation("Nouvel OT")
        self.aller("#/ot/nouveau?equipement=" + equipement)
        page = self.page
        formulaire = "#form-nouvel-ot"
        page.wait_for_selector(formulaire + " [name=habilitation_requise]")
        page.fill(formulaire + " [name=titre]", "T440 — nouvel OT, exigence de l'OT")
        self.assertEqual(page.inner_text(formulaire + " [data-champ=habilitation_requise] .libelle"),
                         "Habilitation exigée par l'OT")
        self.assertEqual(self.aide_exigence(formulaire),
                         "L'équipement n'en exige aucune. Plusieurs : séparez par des virgules.")
        propositions = page.eval_on_selector_all(formulaire + " datalist option", "(os) => os.map((o) => o.value)")
        self.assertIn("BR", propositions)                                   # intitulé connu (équipements, habilitations)
        page.fill(formulaire + " [name=habilitation_requise]", "BR, ")
        self.assertIn("BR, H0V", page.eval_on_selector_all(formulaire + " datalist option", "(os) => os.map((o) => o.value)"))
        self.saisir_exigence(formulaire, "")
        self.choisir_affectation(formulaire, technicien, DATE)
        self.assertEqual(page.locator(ZONE_NOUVEL_OT + " .alerte").count(), 0)   # l'équipement n'exige rien

        # Exigence posée sur l'OT : refus en direct, puis la fenêtre (l'OT l'exige) ; Annuler n'écrit rien.
        self.saisir_exigence(formulaire, "H0V")
        bandeau = page.wait_for_selector(ZONE_NOUVEL_OT + " .alerte.important").inner_text()
        self.assertIn("(%s) n'a pas d'habilitation valide au %s pour : H0V (absente)." % (technicien, date_fr(DATE)), bandeau)
        avant_ot, avant_journal = self.nombre_ot(), len(self.journal())
        page.click(formulaire + " button[type=submit]")
        self.assertIn("Cet OT l'exige (OT). L'affectation est refusée.", page.wait_for_selector(FENETRE).inner_text())
        self.annuler()
        self.attendre_toast("Affectation refusée")
        self.assertEqual((self.nombre_ot(), len(self.journal())), (avant_ot, avant_journal))

        # Exigence retirée : plus de refus, l'OT est créé sans fenêtre ni dérogation.
        self.saisir_exigence(formulaire, "")
        self.attendre_sans_refus(ZONE_NOUVEL_OT)
        page.click(formulaire + " button[type=submit]")
        page.wait_for_selector(".ot-fiche .ot-numero")
        ot_id = page.inner_text(".ot-fiche .ot-numero")
        self.assertEqual(page.locator("dialog").count(), 0)
        ligne = self.ot(ot_id)
        self.assertEqual((ligne["technicien_id"], ligne["date_prevue"], brut(ligne["habilitation_requise"])),
                         (technicien, DATE, ""))
        self.assertEqual([j["action"] for j in self.entrees(ot_id)], ["création — création de l'OT (manuel)"])
        self.assertEqual(page.locator(".ot-entete .ot-habilitation-exigee").count(), 0)
        self.assertEqual(self.habilitation_du_bon(ot_id), "aucune")

    def test_preparation_exigence_de_l_ot_bloque_passer_outre_puis_retiree_ne_bloque_plus(self):
        equipement = self.equipement_sans_exigence()
        self.ouvrir()
        technicien = self.technicien_sans_habilitation("Préparation")
        ot_id = self.nouvel_ot_par_api("T440 — préparation, exigence de l'OT", equipement_id=equipement)
        self.preparer_par_api(ot_id)
        self.ouvrir_fiche(ot_id, "preparation")
        page = self.page
        formulaire = "#form-preparation"
        page.wait_for_selector(formulaire + " [name=habilitation_requise]")
        self.assertEqual(page.input_value(formulaire + " [name=habilitation_requise]"), "")
        self.choisir_affectation(formulaire, technicien, DATE)
        self.assertEqual(page.locator(ZONE_PREPARATION + " .alerte").count(), 0)

        # Exigence posée : refus en direct, fenêtre, le responsable passe outre ; l'exigence et la dérogation sont écrites.
        self.saisir_exigence(formulaire, "H0V")
        bandeau = page.wait_for_selector(ZONE_PREPARATION + " .alerte.important").inner_text()
        self.assertIn("pour : H0V (absente).", bandeau)
        page.click(formulaire + " button[type=submit]")
        texte = page.wait_for_selector(FENETRE).inner_text()
        self.assertIn("(%s) n'a pas d'habilitation valide au %s pour : H0V (absente)." % (technicien, date_fr(DATE)), texte)
        self.assertIn("Cet OT l'exige (OT). L'affectation est refusée.", texte)
        self.passer_outre()
        self.attendre_toast("Préparation enregistrée.")
        ligne = self.ot(ot_id)
        self.assertEqual((ligne["technicien_id"], ligne["date_prevue"], brut(ligne["habilitation_requise"])),
                         (technicien, DATE, "H0V"))
        derniere = self.entrees(ot_id)[-1]
        self.assertTrue(derniere["action"].endswith(" ; " + marqueur(technicien, DATE, "H0V (absente)")), derniere["action"])
        page.wait_for_selector(".ot-entete .ot-habilitation-exigee")
        self.assertEqual(page.inner_text(".ot-entete .ot-habilitation-exigee"), "Habilitation exigée : H0V (OT)")
        self.assertEqual(self.habilitation_du_bon(ot_id), "H0V (OT)")

        # Exigence retirée : plus de refus ni de fenêtre ; vide dans le fichier, plus rien dans l'en-tête.
        page.wait_for_selector(formulaire + " [name=habilitation_requise]")
        self.assertEqual(page.input_value(formulaire + " [name=habilitation_requise]"), "H0V")
        self.saisir_exigence(formulaire, "")
        self.attendre_sans_refus(ZONE_PREPARATION)
        page.click(formulaire + " button[type=submit]")
        page.wait_for_function("(id) => Donnees.trouver('ordres_travail', id).habilitation_requise === ''", arg=ot_id)
        page.wait_for_function("() => !document.querySelector('.ot-entete .ot-habilitation-exigee')")
        self.assertEqual(page.locator("dialog").count(), 0)
        self.assertEqual((brut(self.ot(ot_id)["habilitation_requise"]), self.ot(ot_id)["technicien_id"]), ("", technicien))
        self.assertNotIn("dérogation", self.entrees(ot_id)[-1]["action"])
        self.assertEqual(page.locator(BANDEAU_DEROGATION).count(), 0)

    def test_en_tete_et_bon_de_travail_disent_l_exigence_et_son_origine(self):
        self.ouvrir()
        ot_id = self.nouvel_ot_par_api("T440 — en-tête et bon", habilitation_requise="H0V")
        self.ouvrir_fiche(ot_id, "preparation")
        page = self.page
        self.assertEqual(page.inner_text(".ot-entete .ot-habilitation-exigee"), "Habilitation exigée : BR (équipement), H0V (OT)")
        self.assertEqual(self.habilitation_du_bon(ot_id), "BR (équipement), H0V (OT)")
        page.wait_for_selector("#form-preparation [name=habilitation_requise]")
        self.assertEqual(page.input_value("#form-preparation [name=habilitation_requise]"), "H0V")
        self.assertEqual(self.aide_exigence("#form-preparation"),
                         "En plus de celle de l'équipement (BR). Plusieurs : séparez par des virgules.")
        # Doublon (casse ignorée) réuni sous la première écriture, avec ses deux origines ; « / » sépare aussi.
        self.assertEqual(self.appeler("([ot]) => Ordres.interne.libelleExigences(ot)",
                                      {"equipement_id": EQ_BR, "habilitation_requise": "H0V / br"}),
                         "BR (équipement, OT), H0V (OT)")
        # OT sans exigence : ni badge ni exigence au bon (« aucune »).
        self.ouvrir_fiche(OT_A_PLANIFIER)
        self.assertEqual(page.locator(".ot-entete .ot-habilitation-exigee").count(), 0)
        self.assertEqual(self.habilitation_du_bon(OT_A_PLANIFIER), "aucune")


if __name__ == "__main__":
    unittest.main()
