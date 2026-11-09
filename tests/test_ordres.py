"""Tests du module Ordres de travail (js/modules/ordres-*.js, objet Ordres) : écrans E4 et E5,
règles RG3, RG4, RG7 et RG8 (ARCHITECTURE.md §10), bon de travail.

Familles (le nom du test le dit) :
    regles      : fonctions pures Ordres.* évaluées dans la page (jeu de démo en mode serveur) ;
    parcours    : OT complet par l'interface, en mode serveur, avec vérification des CSV sur le disque ;
    habilitation: refus RG8 (T437) affiché, rien d'écrit dans les CSV ;
    liste       : filtres (dont les liens de l'accueil ?filtre=retard / ?filtre=p1), tri, export CSV ;
    impression  : bon de travail dans #impression (émulation « print ») ;
    technicien  : « mes OT » par défaut ; demo : parcours court en file:// ; telephone : 375 px.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_ordres.py" -v
"""
import csv
import datetime
import io
import re
import unittest
from pathlib import Path

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, scenarios_demo, url_fichier

BOM = b"\xef\xbb\xbf"
RAPPEL = "Cocher une case ne consigne rien : appliquez la procédure."
STATUTS_FERMES = ("Clôturé techniquement", "Clôturé administrativement", "Annulé")

# Identifiants des objets de scénario du jeu de démo (outils/generer_demo.py, ARCHITECTURE.md §14.8).
SCENARIOS = scenarios_demo()
OT_P1 = SCENARIOS["ot_p1_ouvert"]                   # En cours, P1, CP-01
OT_CREE = SCENARIOS["ot_statut_cree"]               # préventif « Créé » (gamme compteur échue)
OT_PREPARE = SCENARIOS["ot_statut_prepare"]         # correctif « Préparé », en retard
OT_EN_COURS = SCENARIOS["ot_statut_en_cours"]       # correctif « En cours », P2
OT_EN_ATTENTE = SCENARIOS["ot_statut_en_attente"]   # « En attente » d'une pièce, en retard
OT_FUITE_PO02 = SCENARIOS["ot_fuite_garniture_po02"]  # correctif clôturé de PO-02 : 1 kit garniture prévu

# window.print() ouvrirait une boîte de dialogue : en test, un espion note seulement l'appel.
ESPION_IMPRESSION_JS = "window.print = function () { window.__impressions = (window.__impressions || 0) + 1; };"


def lire_csv(dossier, nom):
    """Lignes (dictionnaires) d'un CSV de Prévo sur le disque (UTF-8 avec BOM, « ; »)."""
    texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte), delimiter=";"))


def nombre(valeur):
    try:
        return float(str(valeur).replace(",", "."))
    except ValueError:
        return 0.0


def ot_ouvert(ot):
    return ot["statut"] not in STATUTS_FERMES


def ot_en_retard(ot, aujourdhui):
    return ot_ouvert(ot) and ot["date_prevue"] != "" and ot["date_prevue"][:10] < aujourdhui


def cout_python(dossier, ot_id):
    """RG7 recalculé depuis les CSV : heures × taux + (sorties − retours) × prix + sous-traitance."""
    taux = {t["id"]: nombre(t["taux_horaire"]) for t in lire_csv(dossier, "techniciens.csv")}
    prix = {a["id"]: nombre(a["prix_unitaire"]) for a in lire_csv(dossier, "articles.csv")}
    heures = sum(nombre(t["heures"]) * taux.get(t["technicien_id"], 0)
                 for t in lire_csv(dossier, "ot_temps.csv") if t["ot_id"] == ot_id)
    pieces = 0.0
    for mouvement in lire_csv(dossier, "mouvements_stock.csv"):
        if mouvement["ot_id"] != ot_id:
            continue
        signe = {"sortie": 1, "retour": -1}.get(mouvement["type"], 0)
        pieces += signe * nombre(mouvement["quantite"]) * prix.get(mouvement["article_id"], 0)
    ot = next(o for o in lire_csv(dossier, "ordres_travail.csv") if o["id"] == ot_id)
    soustraitance = nombre(ot["cout_soustraitance"]) if ot["cout_soustraitance"] else 0.0
    return round(heures, 2), round(pieces, 2), round(soustraitance, 2), round(heures + pieces + soustraitance, 2)


class CasOrdres(CasNavigateur):
    """Outils communs : ouvrir une route avec un profil, lire l'écran, piloter la fiche OT."""

    def ouvrir(self, serveur, route, profil="responsable", technicien_id="", largeur=1280):
        self.page.set_viewport_size({"width": largeur, "height": 900})
        preregler_profil(self.contexte, profil, technicien_id=technicien_id)
        self.page.goto(serveur.url + "/" + route)
        attendre_pret(self.page)

    def aller(self, route):
        self.page.evaluate("location.hash = %r" % route)

    def attendre_fiche(self, ot_id):
        self.page.wait_for_function(
            "document.querySelector('.ot-fiche .ot-numero') && document.querySelector('.ot-fiche .ot-numero').textContent === %r" % ot_id)

    def statut_affiche(self):
        return self.page.inner_text(".ot-badges .badge.statut")

    def attendre_statut(self, statut):
        self.page.wait_for_function(
            "document.querySelector('.ot-badges .badge.statut') && document.querySelector('.ot-badges .badge.statut').textContent === %r" % statut)

    def onglet(self, identifiant):
        self.page.click(".onglet[data-onglet='%s']" % identifiant)

    def transition(self, cible, zone=".ot-actions"):
        self.page.click("%s button[data-action='transition'][data-cible='%s']" % (zone, cible))

    def ids_affiches(self):
        """N° des OT du tableau de la liste (grand écran)."""
        return self.page.eval_on_selector_all(
            ".ot-liste-tableau tbody tr td:first-child a", "liens => liens.map(a => a.textContent)")

    def attendre_js(self, expression, delai_ms=10000):
        self.page.wait_for_function(expression, timeout=delai_ms)

    def creer_ot_par_l_interface(self, equipement_id, titre, technicien_id="", priorite="P3"):
        """Formulaire « Nouvel OT » ; renvoie l'identifiant de l'OT créé (fiche affichée)."""
        page = self.page
        self.aller("#/ot/nouveau?equipement=" + equipement_id)
        page.wait_for_selector("#form-nouvel-ot")
        page.fill("#form-nouvel-ot [name=titre]", titre)
        page.select_option("#form-nouvel-ot [name=priorite]", priorite)
        if technicien_id:
            page.select_option("#form-nouvel-ot [name=technicien_id]", technicien_id)
        page.click("#form-nouvel-ot button[type=submit]")
        page.wait_for_selector(".ot-fiche .ot-numero")
        return page.inner_text(".ot-fiche .ot-numero")


# ---------------------------------------------------------------------------
# Règles pures (ARCHITECTURE.md §10)
# ---------------------------------------------------------------------------

class TestRegles(CasOrdres):

    def test_regles_transitions_rg3_et_urgence(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot")
            attendu = {
                ("Créé", "manuel", "correctif différé"): ["Préparé", "En attente", "Annulé"],
                ("Créé", "urgence", "correctif différé"): ["Préparé", "En cours", "En attente", "Annulé"],
                ("Créé", "DI", "correctif immédiat"): ["Préparé", "En cours", "En attente", "Annulé"],
                ("Préparé", "manuel", "amélioration"): ["Planifié", "En attente", "Annulé"],
                ("Planifié", "manuel", "amélioration"): ["En cours", "Préparé", "En attente", "Annulé"],
                ("En cours", "manuel", "amélioration"): ["Clôturé techniquement", "En attente"],
                ("Clôturé techniquement", "manuel", "amélioration"): ["Clôturé administrativement", "En cours"],
                ("Clôturé administrativement", "manuel", "amélioration"): [],
                ("Annulé", "manuel", "amélioration"): [],
            }
            for (statut, origine, type_ot), transitions in attendu.items():
                with self.subTest(statut=statut, origine=origine, type=type_ot):
                    obtenu = self.page.evaluate(
                        "([s, o, t]) => Ordres.transitionsPossibles({ id: 'X', statut: s, origine: o, type: t })",
                        [statut, origine, type_ot])
                    self.assertEqual(obtenu, transitions)
            # En attente : reprise En cours si l'OT a démarré, sinon Préparé
            self.assertEqual(self.page.evaluate(
                "Ordres.transitionsPossibles({ statut: 'En attente', date_debut: '2026-10-19 08:00' })"), ["En cours", "Annulé"])
            self.assertEqual(self.page.evaluate(
                "Ordres.transitionsPossibles({ statut: 'En attente', date_debut: '' })"), ["Préparé", "Annulé"])
            # Motifs obligatoires ; verrouillage ; Planifié sans technicien ni date
            passage = self.page.evaluate(
                "Ordres.verifierPassage({ id: 'X', statut: 'En cours', motif_attente: '' }, 'En attente')")
            self.assertFalse(passage["ok"])
            self.assertIn("motif", passage["erreurs"][0])
            passage = self.page.evaluate(
                "Ordres.verifierPassage({ id: 'X', statut: 'Préparé', motif_annulation: 'doublon' }, 'Annulé')")
            self.assertTrue(passage["ok"])
            passage = self.page.evaluate("Ordres.verifierPassage({ id: 'X', statut: 'Annulé' }, 'En cours')")
            self.assertFalse(passage["ok"])
            self.assertIn("verrouillé", passage["erreurs"][0])
            passage = self.page.evaluate("Ordres.verifierPassage({ id: 'X', statut: 'Préparé', technicien_id: '', date_prevue: '' }, 'Planifié')")
            self.assertEqual(len(passage["erreurs"]), 2)
            # Stock (RG3) : la dernière fuite de PO-02 prévoit 1 kit garniture (2 au moins en stock)
            # → planifiable côté stock
            passage = self.page.evaluate(
                "Ordres.verifierPassage(Object.assign({}, Donnees.trouver('ordres_travail', %r),"
                " { statut: 'Préparé', technicien_id: 'TEC-0002', date_prevue: '2026-10-30' }), 'Planifié')"
                % OT_FUITE_PO02)
            self.assertTrue(passage["ok"], passage)
            # Ouvert / en retard (§10)
            self.assertTrue(self.page.evaluate("Ordres.estOuvert({ statut: 'En attente' })"))
            self.assertFalse(self.page.evaluate("Ordres.estOuvert({ statut: 'Clôturé techniquement' })"))
            self.assertTrue(self.page.evaluate("Ordres.enRetard({ statut: 'Planifié', date_prevue: '2026-01-01' }, '2026-10-19')"))
            self.assertFalse(self.page.evaluate("Ordres.enRetard({ statut: 'Annulé', date_prevue: '2026-01-01' }, '2026-10-19')"))

    def test_regles_cloture_rg4_ras_refuse_sur_correctif_seulement(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot")
            complet = {"id": "X", "statut": "En cours", "type": "correctif différé", "date_debut": "2026-10-19 08:00",
                       "date_fin": "2026-10-19 10:00", "cause_code": "C01", "remede_code": "R01",
                       "compte_rendu": "Garniture usée remplacée, essai sans fuite.", "remise_service": "1"}
            temps = [{"heures": "1.5"}]
            verifier = "([ot, temps]) => Ordres.verifierCloture(ot, { temps })"
            self.assertEqual(self.page.evaluate(verifier, [complet, temps]), [])
            # Tous les manques à la fois
            vide = dict(complet, date_fin="", cause_code="", remede_code="", compte_rendu="court", remise_service="0")
            manques = self.page.evaluate(verifier, [vide, []])
            self.assertEqual(len(manques), 6, manques)
            texte = " | ".join(manques)
            for attendu in ("date de fin", "temps passé", "code cause", "code remède", "10 caractères", "remis en service"):
                self.assertIn(attendu, texte)
            # « RAS » refusé sur un correctif (même long), accepté sur un préventif
            for compte_rendu in ("RAS", "R.A.S.", "RAS, rien à signaler", "Rien à signaler.",
                                 "NTR", "N/A", "Nothing to report.", "None"):     # anglais aussi (T287)
                with self.subTest(compte_rendu=compte_rendu):
                    manques = self.page.evaluate(verifier, [dict(complet, compte_rendu=compte_rendu), temps])
                    self.assertEqual(len(manques), 1, manques)
                    self.assertIn("RAS", manques[0])
            preventif = dict(complet, type="préventif systématique", compte_rendu="RAS, rien à signaler")
            self.assertEqual(self.page.evaluate(verifier, [preventif, temps]), [])
            # Un préventif avec « RAS » seul reste trop court (10 caractères)
            manques = self.page.evaluate(verifier, [dict(preventif, compte_rendu="RAS"), temps])
            self.assertEqual(len(manques), 1)
            self.assertIn("10 caractères", manques[0])

    def test_regles_cout_rg7_des_ot_clotures_recalcule_depuis_les_csv(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot")
            clotures = [o["id"] for o in lire_csv(serveur.dossier, "ordres_travail.csv")
                        if o["statut"] == "Clôturé administrativement"]
            avec_pieces = {m["ot_id"] for m in lire_csv(serveur.dossier, "mouvements_stock.csv") if m["type"] == "sortie"}
            self.assertTrue(any(ot_id in avec_pieces for ot_id in clotures), "la démo doit avoir un OT clôturé avec pièces")
            for ot_id in clotures:
                heures, pieces, soustraitance, total = cout_python(serveur.dossier, ot_id)
                cout = self.page.evaluate("Ordres.cout(Donnees.trouver('ordres_travail', %r))" % ot_id)
                with self.subTest(ot=ot_id):
                    self.assertAlmostEqual(cout["heures"], heures, places=2)
                    self.assertAlmostEqual(cout["pieces"], pieces, places=2)
                    self.assertAlmostEqual(cout["soustraitance"], soustraitance, places=2)
                    self.assertAlmostEqual(cout["total"], total, places=2)
            # Affiché dans l'onglet Compte rendu d'un OT clôturé avec pièces
            exemple = next(ot_id for ot_id in clotures if ot_id in avec_pieces)
            total = cout_python(serveur.dossier, exemple)[3]
            self.aller("#/ot/" + exemple)
            self.attendre_fiche(exemple)
            self.onglet("compte-rendu")
            attendu = "{:,.2f}".format(total).replace(",", " ").replace(".", ",")
            self.assertIn(attendu, self.page.inner_text("#ot-cout-total").replace(" ", " ").replace("\xa0", " "))

    def test_regles_habilitation_rg8_ae03(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot")
            message = self.page.evaluate(
                "Ordres.verifierHabilitation(Donnees.trouver('equipements', 'EQ-0012'), 'TEC-0004', '2026-10-21')")
            self.assertEqual(message, "TEC-0004 sans BR valide au 2026-10-21")
            self.assertIsNone(self.page.evaluate(
                "Ordres.verifierHabilitation(Donnees.trouver('equipements', 'EQ-0012'), 'TEC-0001', '2026-10-21')"))
            # Avant l'échéance (2026-05-31), TEC-0004 était habilité ; un équipement sans exigence : null
            self.assertIsNone(self.page.evaluate("Ordres.verifierHabilitation('EQ-0012', 'TEC-0004', '2026-05-01')"))
            self.assertIsNone(self.page.evaluate("Ordres.verifierHabilitation('EQ-0005', 'TEC-0004', '2026-10-21')"))


# ---------------------------------------------------------------------------
# Parcours complet (mode serveur) et habilitation
# ---------------------------------------------------------------------------

class TestParcours(CasOrdres):

    def test_parcours_complet_serveur_du_kit_garniture_a_l_ot_lie(self):
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot")
            ot_id = self.creer_ot_par_l_interface("EQ-0005", "PO-02 — fuite à la garniture", "TEC-0002", "P2")
            self.assertEqual(self.statut_affiche(), "Créé")
            self.assertIn(RAPPEL, page.inner_text(".ot-consignation"))

            # Préparation : kit garniture (stock 3) en quantité trop grande
            self.onglet("preparation")
            page.select_option("#ot-nouvel-article", "ART-0016")
            page.fill("#ot-nouvelle-quantite", "5")
            page.click("#form-pieces button[type=submit]")
            self.attendre_js("Donnees.lignes('ot_pieces').some(p => p.ot_id === %r && p.quantite_prevue === '5')" % ot_id)
            page.wait_for_selector("#ot-bloc-pieces .badge.ko")
            self.transition("Préparé")
            self.attendre_statut("Préparé")

            # Planifier : refusé (RG3), proposition de mise en attente « pièce »
            self.transition("Planifié", ".ot-actions-preparation")
            page.wait_for_selector("#ot-message .alerte")
            message = page.inner_text("#ot-message")
            self.assertIn("Stock insuffisant", message)
            self.assertIn("Kit garniture mécanique PO-02", message)
            self.assertEqual(self.statut_affiche(), "Préparé")
            page.click("#ot-message button[data-action='attente-piece']")
            page.wait_for_selector("dialog textarea")
            self.assertTrue(page.input_value("dialog textarea").startswith("Pièce : "))
            page.click("dialog .fenetre-actions .btn-fantome")          # Annuler : on corrige plutôt
            self.assertEqual(self.statut_affiche(), "Préparé")

            # Correction de la quantité (non enregistrée : la transition l'enregistre d'abord) → Planifié
            page.fill("#ot-bloc-pieces tr[data-piece] .ot-quantite", "1")
            self.transition("Planifié", ".ot-actions-preparation")
            self.attendre_statut("Planifié")
            self.assertTrue(page.evaluate("Donnees.lignes('ot_pieces').some(p => p.ot_id === %r && p.quantite_prevue === '1')" % ot_id))

            # Démarrer, temps passé
            self.onglet("execution")
            self.transition("En cours", ".ot-demarrer")
            self.attendre_statut("En cours")
            self.onglet("execution")
            page.fill("#ot-temps-heures", "1,5")
            page.click("#form-temps button[type=submit]")
            self.attendre_js("Donnees.lignes('ot_temps').some(t => t.ot_id === %r && t.heures === '1.5')" % ot_id)

            # Clôture refusée : « RAS », sans cause, sans date de fin, sans remise en service
            self.onglet("compte-rendu")
            page.fill("#form-compte-rendu [name=compte_rendu]", "RAS")
            self.transition("Clôturé techniquement", "#form-compte-rendu")
            page.wait_for_selector("#ot-message .alerte")
            message = page.inner_text("#ot-message")
            for attendu in ("Clôture technique impossible", "code cause", "code remède", "RAS",
                            "date de fin", "remis en service"):
                self.assertIn(attendu, message)
            self.assertNotIn("temps passé", message)
            self.assertEqual(self.statut_affiche(), "En cours")
            ligne = next(o for o in lire_csv(serveur.dossier, "ordres_travail.csv") if o["id"] == ot_id)
            self.assertEqual(ligne["statut"], "En cours")
            self.assertEqual(ligne["compte_rendu"], "RAS")      # la saisie a été enregistrée

            # Compléter : date de fin, codes, compte rendu, remise en service → clôture technique
            self.onglet("execution")
            page.click("#form-execution .ot-maintenant")
            page.click("#form-execution button[type=submit]")
            self.attendre_js("Donnees.trouver('ordres_travail', %r).date_fin !== ''" % ot_id)
            self.onglet("compte-rendu")
            page.select_option("#form-compte-rendu [name=symptome_code]", "S01")
            page.select_option("#form-compte-rendu [name=cause_code]", "C01")
            page.select_option("#form-compte-rendu [name=remede_code]", "R01")
            page.fill("#form-compte-rendu [name=compte_rendu]",
                      "Fuite à la garniture : kit garniture remplacé, essai 15 min sans fuite.")
            page.check("#form-compte-rendu [name=remise_service]")
            self.transition("Clôturé techniquement", "#form-compte-rendu")
            self.attendre_statut("Clôturé techniquement")

            # Clôture administrative (confirmation) → lecture seule
            self.transition("Clôturé administrativement")
            page.click("dialog .fenetre-actions .btn-primaire")
            self.attendre_statut("Clôturé administrativement")
            self.assertEqual(page.locator(".ot-fiche button[data-action='transition']").count(), 0)
            self.assertIn("lecture seule", page.inner_text(".ot-bandeau-etat"))
            self.assertTrue(page.is_disabled("#form-compte-rendu [name=compte_rendu]"))
            self.onglet("preparation")
            self.assertTrue(page.is_disabled("#form-preparation [name=travail_a_faire]"))
            self.assertEqual(page.locator("#form-pieces button[type=submit]").count(), 0)

            # Sur le disque
            ligne = next(o for o in lire_csv(serveur.dossier, "ordres_travail.csv") if o["id"] == ot_id)
            self.assertEqual(ligne["statut"], "Clôturé administrativement")
            self.assertEqual((ligne["cause_code"], ligne["remede_code"], ligne["remise_service"]), ("C01", "R01", "1"))
            self.assertTrue(ligne["date_debut"] and ligne["date_fin"] and ligne["date_cloture_tech"] and ligne["date_cloture_admin"])
            pieces = [p for p in lire_csv(serveur.dossier, "ot_pieces.csv") if p["ot_id"] == ot_id]
            self.assertEqual([(p["article_id"], p["quantite_prevue"]) for p in pieces], [("ART-0016", "1")])
            temps = [t for t in lire_csv(serveur.dossier, "ot_temps.csv") if t["ot_id"] == ot_id]
            self.assertEqual([(t["technicien_id"], t["heures"]) for t in temps], [("TEC-0002", "1.5")])
            journal = " | ".join(j["action"] for j in lire_csv(serveur.dossier, "journal.csv") if j["id_ligne"] == ot_id)
            self.assertIn("statut Préparé → Planifié", journal)
            self.assertIn("statut En cours → Clôturé techniquement", journal)

            # OT lié (reprise d'un OT verrouillé)
            page.click("#ot-lie")
            page.wait_for_function("location.hash !== %r && document.querySelector('.ot-fiche .ot-numero')"
                                   " && document.querySelector('.ot-fiche .ot-numero').textContent !== %r" % ("#/ot/" + ot_id, ot_id))
            nouvel_id = page.inner_text(".ot-fiche .ot-numero")
            self.assertEqual(self.statut_affiche(), "Créé")
            self.assertIn("Reprend l'OT\n" + ot_id, page.inner_text(".ot-fiche .grille"))
            lie = next(o for o in lire_csv(serveur.dossier, "ordres_travail.csv") if o["id"] == nouvel_id)
            self.assertEqual((lie["ot_lie_id"], lie["equipement_id"], lie["statut"]), (ot_id, "EQ-0005", "Créé"))

    def test_parcours_ot_d_urgence_cree_puis_demarre_directement(self):
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot")
            page.click("#ot-urgence")
            page.wait_for_selector("#form-nouvel-ot")
            self.assertIn("Intervention d'urgence", page.inner_text("#contenu"))
            # Équipement choisi par la recherche
            page.fill("#ot-nouveau-equipement input[type=search]", "BA-01")
            page.click("#ot-nouveau-equipement .selecteur-option[data-id='EQ-0029']")
            self.assertEqual(page.input_value("#form-nouvel-ot [name=priorite]"), "P1")
            self.assertTrue(page.is_disabled("#form-nouvel-ot [name=type]"))
            page.fill("#form-nouvel-ot [name=titre]", "BA-01 — balance bloquée, ligne arrêtée")
            page.click("#form-nouvel-ot button[type=submit]")
            page.wait_for_selector(".ot-fiche .ot-numero")
            ot_id = page.inner_text(".ot-fiche .ot-numero")
            self.assertEqual(self.statut_affiche(), "Créé")
            self.assertIn("P1", page.inner_text(".ot-badges"))
            # Créé → En cours directement (RG3, urgence)
            self.transition("En cours")
            self.attendre_statut("En cours")
            ligne = next(o for o in lire_csv(serveur.dossier, "ordres_travail.csv") if o["id"] == ot_id)
            self.assertEqual((ligne["origine"], ligne["type"], ligne["priorite"], ligne["statut"]),
                             ("urgence", "correctif immédiat", "P1", "En cours"))
            self.assertRegex(ligne["date_debut"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")

    def test_habilitation_refus_affiche_rien_d_ecrit(self):
        # RG8 bloquante (T437, D186) : l'affectation sans BR valide est refusée par l'écriture ; la fenêtre « passer
        # outre » du responsable (T438, tests/test_rg8_ecrans.py) est annulée, le message d'erreur commun redit le
        # refus ; rien n'est écrit, ni l'OT ni le journal.
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot")
            ot_id = self.creer_ot_par_l_interface("EQ-0012", "AE-03 — contrôle du câblage")
            self.onglet("preparation")
            page.select_option("#form-preparation [name=technicien_id]", "TEC-0004")
            page.fill("#form-preparation [name=date_prevue]", "2026-10-21")
            page.dispatch_event("#form-preparation [name=date_prevue]", "change")
            page.wait_for_selector("#form-preparation .ot-zone-habilitation .alerte")
            avertissement = page.inner_text("#form-preparation .ot-zone-habilitation")
            self.assertIn("BR", avertissement)
            self.assertIn("TEC-0004", avertissement)
            page.click("#form-preparation button[type=submit]")
            page.click("dialog.ot-fenetre-derogation .fenetre-actions .btn-fantome")       # Annuler
            page.wait_for_function("document.getElementById('toast').textContent.includes('Affectation refusée')")
            toast = page.inner_text("#toast")
            self.assertIn("(TEC-0004) n'a pas d'habilitation valide au 21/10/2026 : BR (échue le 31/05/2026).", toast)
            self.assertIn("Seul le responsable peut passer outre.", toast)
            ligne = next(o for o in lire_csv(serveur.dossier, "ordres_travail.csv") if o["id"] == ot_id)
            self.assertEqual(ligne["technicien_id"], "")
            self.assertNotEqual(ligne["date_prevue"], "2026-10-21")
            self.assertEqual([j["action"] for j in lire_csv(serveur.dossier, "journal.csv")
                              if j["id_ligne"] == ot_id and "habilitation" in j["action"]], [])
            # Avec un électricien habilité : plus de bandeau, et la préparation s'enregistre
            page.select_option("#form-preparation [name=technicien_id]", "TEC-0001")
            page.wait_for_function("!document.querySelector('#form-preparation .ot-zone-habilitation .alerte')")
            page.click("#form-preparation button[type=submit]")
            self.attendre_js("Donnees.trouver('ordres_travail', %r).technicien_id === 'TEC-0001'" % ot_id)


# ---------------------------------------------------------------------------
# Deux postes sur le même OT ; saisies de la fiche conservées (relecture des vagues 4-5)
# ---------------------------------------------------------------------------

# Prépare l'OT P1 en cours (argument : son identifiant) pour qu'il soit clôturable : date de fin,
# codes, compte rendu, temps.
PREPARER_CLOTURE_P1_JS = """async (otId) => {
  await Donnees.modifier('ordres_travail', (l) => { Object.assign(l.find((x) => x.id === otId), {
    date_fin: Donnees.maintenant(), cause_code: 'C01', remede_code: 'R01',
    compte_rendu: 'Filtre à huile remplacé, radiateur nettoyé.', remise_service: '1' }); });
  await Donnees.modifier('ot_temps', (l, o) => { l.push({ id: o.nouvelId(l), ot_id: otId,
    technicien_id: 'TEC-0004', date: Donnees.aujourdhui(), heures: '2' }); });
}"""


class TestDeuxPostes(CasOrdres):

    def autre_poste(self, serveur, route, profil="responsable", technicien_id=""):
        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 900})
        self.addCleanup(contexte.close)
        contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        preregler_profil(contexte, profil, technicien_id=technicien_id, poste="Poste B")
        page = contexte.new_page()
        self.surveiller(page)
        page.goto(serveur.url + "/" + route)
        attendre_pret(page)
        return page

    def ligne(self, serveur, nom, ot_id):
        return next(o for o in lire_csv(serveur.dossier, nom) if o["id"] == ot_id)

    def test_rg4_cloture_administrative_reverifie_la_cloture_technique(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot")
            ot = {"id": "X", "statut": "Clôturé techniquement", "type": "correctif différé", "date_debut": "2026-10-19 08:00",
                  "date_fin": "2026-10-19 10:00", "cause_code": "", "remede_code": "R01", "compte_rendu": "RAS",
                  "remise_service": "1"}
            passage = self.page.evaluate("(ot) => Ordres.verifierPassage(ot, 'Clôturé administrativement')", ot)
            self.assertFalse(passage["ok"], passage)
            texte = " ".join(passage["erreurs"])
            self.assertIn("code cause", texte)
            self.assertIn("RAS", texte)

    def test_rg4_compte_rendu_d_un_poste_refuse_apres_la_cloture_technique_d_un_autre(self):
        # Le poste A écrit avec une version périmée d'ordres_travail.csv : 409, relecture, puis refus.
        self.autoriser_erreur(re.compile(r"status of 409.*/api/csv/ordres_travail"))
        page = self.page
        with ServeurPrevo() as serveur:
            poste_b = self.autre_poste(serveur, "#/ot/" + OT_P1)
            poste_b.evaluate(PREPARER_CLOTURE_P1_JS, OT_P1)
            # Poste A : compte rendu « RAS » sans code cause, pas encore enregistré
            self.ouvrir(serveur, "#/ot/" + OT_P1, profil="technicien", technicien_id="TEC-0004")
            self.attendre_fiche(OT_P1)
            self.onglet("compte-rendu")
            page.fill("#form-compte-rendu [name=compte_rendu]", "RAS")
            page.select_option("#form-compte-rendu [name=cause_code]", "")
            # Poste B clôture techniquement pendant ce temps
            self.assertEqual(poste_b.evaluate("Ordres.changerStatut(%r, 'En cours', 'Clôturé techniquement')" % OT_P1),
                             "Clôturé techniquement")
            page.click("#form-compte-rendu button[type=submit]")
            page.wait_for_function("document.getElementById('toast').textContent.includes('Clôturé techniquement')")
            ligne = self.ligne(serveur, "ordres_travail.csv", OT_P1)
            self.assertEqual((ligne["compte_rendu"], ligne["cause_code"]), ("Filtre à huile remplacé, radiateur nettoyé.", "C01"))
            # La clôture administrative reste possible (l'OT est intact) et le compte rendu est le bon
            poste_b.evaluate("Donnees.rafraichir()")
            self.assertEqual(poste_b.evaluate(
                "Ordres.changerStatut(%r, 'Clôturé techniquement', 'Clôturé administrativement')" % OT_P1),
                "Clôturé administrativement")
            ligne = self.ligne(serveur, "ordres_travail.csv", OT_P1)
            self.assertEqual((ligne["statut"], ligne["compte_rendu"], ligne["cause_code"]),
                             ("Clôturé administrativement", "Filtre à huile remplacé, radiateur nettoyé.", "C01"))

    def test_ot_verrouille_sur_un_autre_poste_temps_refuse(self):
        page = self.page
        with ServeurPrevo() as serveur:
            poste_b = self.autre_poste(serveur, "#/ot/" + OT_P1)
            poste_b.evaluate(PREPARER_CLOTURE_P1_JS, OT_P1)
            temps_avant = [t["heures"] for t in lire_csv(serveur.dossier, "ot_temps.csv") if t["ot_id"] == OT_P1]
            # Poste A : onglet Exécution ouvert, puis B clôture administrativement
            self.ouvrir(serveur, "#/ot/" + OT_P1, profil="technicien", technicien_id="TEC-0004")
            self.attendre_fiche(OT_P1)
            self.onglet("execution")
            self.assertEqual(poste_b.evaluate("""async (otId) => {
                await Ordres.changerStatut(otId, 'En cours', 'Clôturé techniquement');
                return Ordres.changerStatut(otId, 'Clôturé techniquement', 'Clôturé administrativement'); }""", OT_P1),
                "Clôturé administrativement")
            page.fill("#ot-temps-heures", "5")
            page.click("#form-temps button[type=submit]")
            page.wait_for_function("document.getElementById('toast').textContent.includes('ne peut plus être modifié')")
            temps_apres = [t["heures"] for t in lire_csv(serveur.dossier, "ot_temps.csv") if t["ot_id"] == OT_P1]
            self.assertEqual(temps_apres, temps_avant)

    def test_ot_annule_sur_un_autre_poste_pieces_refusees(self):
        with ServeurPrevo() as serveur:
            poste_b = self.autre_poste(serveur, "#/ot/" + OT_CREE)
            # Un responsable (poste C) prépare l'OT « Créé » pendant que B l'annule
            poste_c = self.autre_poste(serveur, "#/ot/" + OT_CREE)
            poste_c.wait_for_selector(".ot-fiche .ot-numero")
            poste_c.click(".onglet[data-onglet='preparation']")
            poste_c.wait_for_selector("#ot-nouvel-article")
            poste_b.evaluate("Donnees.rafraichir()")
            self.assertEqual(poste_b.evaluate(
                "Ordres.changerStatut(%r, 'Créé', 'Annulé', { motif_annulation: 'doublon' })" % OT_CREE), "Annulé")
            poste_c.select_option("#ot-nouvel-article", "ART-0016")
            poste_c.click("#form-pieces button[type=submit]")
            poste_c.wait_for_function("document.getElementById('toast').textContent.includes('ne peut plus être modifié')")
            self.assertEqual([p for p in lire_csv(serveur.dossier, "ot_pieces.csv") if p["ot_id"] == OT_CREE], [])

    def test_saisies_des_autres_blocs_conservees_apres_un_enregistrement(self):
        page = self.page
        with ServeurPrevo() as serveur:
            # Préparation : « Travail à faire » tapé, puis « Enregistrer les pièces »
            self.ouvrir(serveur, "#/ot/" + OT_PREPARE)
            self.attendre_fiche(OT_PREPARE)
            self.onglet("preparation")
            page.fill("#form-preparation [name=travail_a_faire]", "Texte saisi avant d'ajouter une pièce")
            page.select_option("#ot-nouvel-article", "ART-0016")
            page.click("#form-pieces button[type=submit]")
            self.attendre_js("Donnees.lignes('ot_pieces').some((p) => p.ot_id === %r && p.article_id === 'ART-0016')" % OT_PREPARE)
            page.wait_for_function("document.getElementById('toast').textContent.includes('Pièces prévues enregistrées')")
            self.assertEqual(page.input_value("#form-preparation [name=travail_a_faire]"), "Texte saisi avant d'ajouter une pièce")
            self.assertEqual(self.ligne(serveur, "ordres_travail.csv", OT_PREPARE)["travail_a_faire"],
                             "Texte saisi avant d'ajouter une pièce")

            # Exécution : « Maintenant » pour la date de fin, puis « Ajouter le temps »
            self.aller("#/ot/" + OT_EN_COURS)
            self.attendre_fiche(OT_EN_COURS)
            self.onglet("execution")
            page.click("#form-execution .ot-maintenant")
            date_fin = page.input_value("#form-execution [name=date_fin]")
            self.assertTrue(date_fin)
            page.fill("#ot-temps-heures", "1,5")
            page.click("#form-temps button[type=submit]")
            page.wait_for_function("document.getElementById('toast').textContent.includes('Temps ajouté')")
            self.assertEqual(page.input_value("#form-execution [name=date_fin]"), date_fin)
            self.assertEqual(self.ligne(serveur, "ordres_travail.csv", OT_EN_COURS)["date_fin"], date_fin.replace("T", " "))


# ---------------------------------------------------------------------------
# Liste : filtres, tri, export CSV ; impression ; technicien
# ---------------------------------------------------------------------------

class TestListe(CasOrdres):

    def test_liste_filtres_liens_accueil_tri_et_export_csv(self):
        page = self.page
        with ServeurPrevo() as serveur:
            aujourdhui = datetime.date.today().isoformat()
            self.ouvrir(serveur, "#/ot")
            # Lu APRÈS l'ouverture : celle d'un responsable génère d'abord les OT préventifs échus (RG5, T28).
            ordres = lire_csv(serveur.dossier, "ordres_travail.csv")
            # Par défaut : les OT ouverts
            ouverts = sorted(o["id"] for o in ordres if ot_ouvert(o))
            self.assertEqual(sorted(self.ids_affiches()), ouverts)
            self.assertIn("%d ordre(s)" % len(ouverts), page.inner_text("#ot-compteur"))
            # Priorités : couleur ET libellé
            badge = page.locator(".ot-liste-tableau .badge.prio-p1").first
            self.assertEqual(badge.inner_text(), "P1")
            # Filtres : tous, P2, type, recherche équipement
            page.select_option("#ot-filtre-etat", "tous")
            self.assertEqual(len(self.ids_affiches()), len(ordres))
            page.select_option("#ot-filtre-priorite", "P2")
            self.assertEqual(sorted(self.ids_affiches()), sorted(o["id"] for o in ordres if o["priorite"] == "P2"))
            page.select_option("#ot-filtre-priorite", "")
            page.select_option("#ot-filtre-type", "réglementaire")
            self.assertEqual(sorted(self.ids_affiches()), sorted(o["id"] for o in ordres if o["type"] == "réglementaire"))
            page.select_option("#ot-filtre-type", "")
            page.fill("#ot-filtre-recherche", "PO-02")
            self.assertEqual(sorted(self.ids_affiches()), sorted(o["id"] for o in ordres if o["equipement_id"] == "EQ-0005"))
            page.select_option("#ot-filtre-etat", "annules")
            page.fill("#ot-filtre-recherche", "")
            self.assertEqual(sorted(self.ids_affiches()), sorted(o["id"] for o in ordres if o["statut"] == "Annulé"))
            page.select_option("#ot-filtre-etat", "clotures")
            self.assertEqual(sorted(self.ids_affiches()),
                             sorted(o["id"] for o in ordres if o["statut"].startswith("Clôturé")))

            # Tri par clic sur l'en-tête « N° »
            page.select_option("#ot-filtre-etat", "tous")
            page.click(".ot-liste-tableau th .tri[data-cle='id']")
            ids = self.ids_affiches()
            self.assertEqual(ids, sorted(ids))
            page.click(".ot-liste-tableau th .tri[data-cle='id']")
            ids = self.ids_affiches()
            self.assertEqual(ids, sorted(ids, reverse=True))

            # Export CSV de la liste filtrée : BOM, « ; », en-tête, une ligne par OT affiché
            page.select_option("#ot-filtre-etat", "ouverts")
            with page.expect_download() as attente:
                page.click("#ot-export")
            telechargement = attente.value
            self.assertRegex(telechargement.suggested_filename, r"^ordres-de-travail-\d{4}-\d{2}-\d{2}\.csv$")
            octets = Path(telechargement.path()).read_bytes()
            self.assertTrue(octets.startswith(BOM))
            texte = octets[3:].decode("utf-8")
            self.assertTrue(texte.startswith("id;priorite;statut;equipement_id;equipement_repere;"))
            self.assertIn("\r\n", texte)
            lignes = list(csv.DictReader(io.StringIO(texte), delimiter=";"))
            self.assertEqual(sorted(l["id"] for l in lignes), ouverts)
            ligne = next(l for l in lignes if l["id"] == OT_P1)
            self.assertEqual(ligne["equipement_repere"], "'CP-01")      # repère protégé (apostrophe, §3.2)
            self.assertEqual(ligne["priorite"], "P1")

            # Liens de l'accueil : ?filtre=retard et ?filtre=p1
            self.aller("#/ot?filtre=retard")
            page.wait_for_function("document.getElementById('ot-filtre-etat') && document.getElementById('ot-filtre-etat').value === 'retard'")
            en_retard = sorted(o["id"] for o in ordres if ot_en_retard(o, aujourdhui))
            self.assertEqual(sorted(self.ids_affiches()), en_retard)
            self.assertTrue(set(SCENARIOS["ot_en_retard"]) <= set(en_retard))
            self.assertEqual(page.locator(".ot-liste-tableau .ot-retard").count(), len(en_retard))
            self.aller("#/ot?filtre=p1")
            page.wait_for_function("document.getElementById('ot-filtre-priorite') && document.getElementById('ot-filtre-priorite').value === 'P1'")
            self.assertEqual(self.ids_affiches(), [OT_P1])
            self.assertEqual(page.input_value("#ot-filtre-etat"), "ouverts")
            self.aller("#/ot?filtre=inconnu")
            page.wait_for_function("document.getElementById('ot-filtre-priorite') && document.getElementById('ot-filtre-priorite').value === ''")
            self.assertEqual(sorted(self.ids_affiches()), ouverts)

            # Un clic sur une ligne ouvre la fiche
            page.click(".ot-liste-tableau tbody tr:first-child td:nth-child(5)")
            page.wait_for_selector(".ot-fiche")

    def test_impression_bon_de_travail_seul_imprime(self):
        page = self.page
        page.add_init_script(ESPION_IMPRESSION_JS)
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot/" + OT_P1)
            self.attendre_fiche(OT_P1)
            page.click("#ot-imprimer")
            self.assertEqual(page.evaluate("window.__impressions"), 1)
            bon = page.inner_text("#impression")
            for attendu in ("Bon de travail", OT_P1, "P1", "CP-01", "Consignation", RAPPEL,
                            "Opérations", "Pièces", "Temps passés", "Compte rendu", "Responsable maintenance"):
                self.assertIn(attendu, bon)
            self.assertEqual(page.locator("#impression .bon-travail .bt-qr svg").count(), 1)
            page.emulate_media(media="print")
            self.assertTrue(page.is_visible("#impression .bon-travail"))
            self.assertTrue(page.is_hidden(".menu-lateral"))
            self.assertTrue(page.is_hidden("#contenu"))
            page.emulate_media(media="screen")
            self.assertTrue(page.is_hidden("#impression"))
            # Après l'impression, la zone est vidée
            page.evaluate("window.dispatchEvent(new Event('afterprint'))")
            self.assertEqual(page.evaluate("document.getElementById('impression').children.length"), 0)

    def test_technicien_mes_ot_par_defaut_et_actions_limitees(self):
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot", profil="technicien", technicien_id="TEC-0002")
            # Lu APRÈS l'ouverture : celle d'un technicien génère d'abord les OT préventifs échus (RG5, T28).
            ordres = lire_csv(serveur.dossier, "ordres_travail.csv")
            self.assertEqual(page.input_value("#ot-filtre-technicien"), "TEC-0002")
            self.assertIn("Mes OT", page.inner_text("#ot-filtre-technicien option[value='TEC-0002']"))
            attendus = sorted(o["id"] for o in ordres if ot_ouvert(o) and o["technicien_id"] == "TEC-0002")
            self.assertTrue(attendus)
            self.assertEqual(sorted(self.ids_affiches()), attendus)
            self.assertEqual(page.locator("#ot-nouveau, #ot-urgence").count(), 0)
            # Tous les techniciens d'un clic
            page.select_option("#ot-filtre-technicien", "")
            self.assertEqual(len(self.ids_affiches()), len([o for o in ordres if ot_ouvert(o)]))
            # Fiche d'un OT en cours : clôture technique et attente, pas d'annulation ni de préparation
            self.aller("#/ot/" + OT_P1)
            self.attendre_fiche(OT_P1)
            cibles = page.eval_on_selector_all(".ot-actions button[data-action='transition']", "b => b.map(x => x.dataset.cible)")
            self.assertEqual(sorted(cibles), ["Clôturé techniquement", "En attente"])
            self.assertEqual(page.locator("#ot-priorite").count(), 0)
            self.onglet("preparation")
            self.assertTrue(page.is_disabled("#form-preparation [name=technicien_id]"))
            self.onglet("execution")
            self.assertFalse(page.is_disabled("#form-execution [name=date_fin]"))
            # La création d'OT est réservée au responsable
            self.aller("#/ot/nouveau")
            page.wait_for_function("location.hash === '#/accueil'")


# ---------------------------------------------------------------------------
# Mode démo (file://) et téléphone
# ---------------------------------------------------------------------------

class TestDemoEtTelephone(CasOrdres):

    def test_demo_parcours_court_preparer_puis_annuler(self):
        page = self.page
        page.goto(url_fichier("index.html"))
        page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        page.click("#btn-demo")
        page.wait_for_function("document.documentElement.dataset.etat === 'profil'")
        page.click("#profil-responsable")
        attendre_pret(page)
        self.aller("#/ot")
        page.wait_for_selector(".ot-liste-tableau tbody tr")
        self.assertIn(OT_CREE, self.ids_affiches())
        self.aller("#/ot/" + OT_CREE)
        self.attendre_fiche(OT_CREE)
        self.transition("Préparé")
        self.attendre_statut("Préparé")
        self.assertEqual(page.evaluate("Donnees.trouver('ordres_travail', %r).statut" % OT_CREE), "Préparé")
        # Annulation : motif obligatoire
        self.transition("Annulé")
        page.wait_for_selector("dialog textarea")
        page.click("dialog .fenetre-actions .btn-primaire")
        self.assertTrue(page.is_visible("dialog .erreur-champ"))
        page.fill("dialog textarea", "Doublon de l'OT de la gamme")
        page.click("dialog .fenetre-actions .btn-primaire")
        self.attendre_statut("Annulé")
        self.assertEqual(page.evaluate("Donnees.trouver('ordres_travail', %r).motif_annulation" % OT_CREE),
                         "Doublon de l'OT de la gamme")
        self.assertEqual(page.locator(".ot-fiche button[data-action='transition']").count(), 0)

    def test_telephone_375px_sans_defilement_horizontal(self):
        page = self.page
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot", largeur=375)
            page.set_viewport_size({"width": 375, "height": 812})

            def sans_defilement(contexte):
                largeurs = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
                self.assertLessEqual(largeurs[0], largeurs[1], "défilement horizontal (%s) : %r" % (contexte, largeurs))

            page.wait_for_selector(".ot-liste-cartes .liste-cartes")
            self.assertTrue(page.is_visible(".ot-liste-cartes"))
            self.assertTrue(page.is_hidden(".ot-liste-tableau"))
            self.assertIn("P1", page.inner_text(".ot-liste-cartes .badge.prio-p1"))
            sans_defilement("liste")
            for ot_id in (OT_P1, OT_EN_ATTENTE):
                self.aller("#/ot/" + ot_id)
                self.attendre_fiche(ot_id)
                for onglet in ("preparation", "execution", "compte-rendu", "historique"):
                    self.onglet(onglet)
                    sans_defilement(ot_id + " " + onglet)
            self.aller("#/ot/nouveau?urgence=1")
            page.wait_for_selector("#form-nouvel-ot")
            self.assertIn("Intervention d'urgence", page.inner_text("#contenu"))
            sans_defilement("OT d'urgence")


if __name__ == "__main__":
    unittest.main()
