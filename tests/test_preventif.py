"""Tests du module Préventif (js/modules/preventif-*.js) : RG5 et écran E8 (ARCHITECTURE.md §14.3).

Familles (le nom du test le dit) :
    unique      : génération à l'ouverture (responsable) : un seul OT pour la gamme mensuelle échue,
                  champs de l'OT, check-list copiée ; trois rechargements sans doublon ; deux postes
                  ouverts en même temps : un seul OT par gamme échue ; demandeur : rien n'est écrit ;
    cloture     : Preventif.apresCloture → dernière réalisation et échéance recalculées sur le disque
                  (gamme par date, gamme au compteur) ; second appel sans effet ;
    declencheur : relevé qui atteint la périodicité d'une gamme au compteur, relevé ≥ seuil, relevé
                  ≥ seuil mais antérieur à la dernière réalisation (aucun OT) ;
    ecrans      : liste et statuts, filtres, bouton « Générer les OT échus » ; création d'une gamme et
                  de sa check-list, modification, ordre, suppression journalisée ; calendrier de
                  12 semaines ; technicien en lecture seule ; demandeur sans accès ; téléphone 375 px ;
    demarrage   : base vide écrite au format courant (sans sauvegarde) ; base au format 1 →
                  sauvegarde puis format 2 (tous profils) ; sauvegarde impossible → aucun OT généré
                  à cette ouverture, application utilisable, nouvel essai à l'ouverture suivante ;
                  démo : génération et toast (chaque toast affiché est noté dès son apparition) ; marques.

Les identifiants viennent de tests/fixtures/demo-scenarios.json (commun.scenarios_demo()) ; aucun
numéro d'OT n'est écrit en dur. Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_preventif.py" -v
"""
import csv
import datetime
import io
import json
import re
import shutil
import unittest
from pathlib import Path

from commun import (RACINE, CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, scenarios_demo,
                    url_fichier)

SCENARIOS = scenarios_demo()
GAMME_ECHUE = SCENARIOS["gamme_mensuelle_echue"]        # date, 30 j, échue SANS OT ouvert (CV-01)
GAMME_COMPTEUR_ECHUE = SCENARIOS["gamme_compteur_echue"]  # compteur en heures, échue AVEC un OT ouvert (CH-01)
GAMME_COMPTEUR = SCENARIOS["gamme_compteur_sans_ot"]    # compteur, pas encore échue, sans OT (CP-01)
GAMME_SEUIL = SCENARIOS["gamme_seuil"]                  # seuil, dernier relevé sous le seuil
COMPTEUR_SEUIL = SCENARIOS["compteur_seuil"]
TECHNICIEN = SCENARIOS["technicien_br_valide"]

PARAMETRES_V1 = RACINE / "tests" / "fixtures" / "v1" / "parametres.csv"
STATUTS_FERMES = ("Clôturé techniquement", "Clôturé administrativement", "Annulé")
# Deux postes qui génèrent en même temps : le second voit sa première écriture refusée (409), relit
# la table et n'écrit plus rien. Ce conflit est voulu ; toute autre erreur fait échouer le test.
CONFLIT_GENERATION = re.compile(r"status of 409.*/api/csv/(ordres_travail|ot_operations)")
ERREUR_CSV_ABSENT = re.compile(r"status of 404.*/api/csv/")       # base vide : les 22 CSV manquent
TOAST_GENERATION = re.compile(r"^\d+ OT préventifs? générés?\.$")


# ---------------------------------------------------------------------------
# Lecture des CSV sur le disque (comme un autre poste ou Excel)
# ---------------------------------------------------------------------------

def lire_csv(dossier, nom):
    """Lignes (dictionnaires) d'un CSV de Prévo sur le disque (UTF-8 avec BOM, « ; »)."""
    texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte), delimiter=";"))


def brut(valeur):
    """Valeur sans l'apostrophe de protection (ARCHITECTURE.md §3.2)."""
    return valeur[1:] if valeur.startswith("'") else valeur


def nombre(valeur):
    return float(brut(valeur).replace(",", "."))


def par_id(dossier, nom):
    return {ligne["id"]: ligne for ligne in lire_csv(dossier, nom)}


def ots_ouverts_de(dossier, gamme_id):
    return [ot for ot in lire_csv(dossier, "ordres_travail.csv")
            if ot["gamme_id"] == gamme_id and ot["statut"] not in STATUTS_FERMES]


def operations_de_gamme(dossier, gamme_id):
    """(ordre, opération, valeur attendue) de la check-list d'une gamme, dans l'ordre."""
    lignes = [op for op in lire_csv(dossier, "gamme_operations.csv") if op["gamme_id"] == gamme_id]
    return sorted((int(brut(op["ordre"])), op["operation"], op["valeur_attendue"]) for op in lignes)


def operations_d_ot(dossier, ot_id):
    lignes = [op for op in lire_csv(dossier, "ot_operations.csv") if op["ot_id"] == ot_id]
    return sorted((int(brut(op["ordre"])), op["operation"], op["valeur_attendue"], op["fait"]) for op in lignes)


def plus_jours(date_iso, jours):
    return (datetime.date.fromisoformat(date_iso) + datetime.timedelta(days=jours)).isoformat()


class CasPreventif(CasNavigateur):
    """Outils communs : ouvrir l'application avec un profil, écrire dans la page, lire l'écran."""

    def ouvrir(self, serveur, route="#/accueil", profil="responsable", technicien_id="", nom="", largeur=1280):
        self.page.set_viewport_size({"width": largeur, "height": 900})
        preregler_profil(self.contexte, profil, nom=nom, technicien_id=technicien_id)
        self.page.goto(serveur.url + "/" + route)
        attendre_pret(self.page)
        return self.page

    def aujourdhui(self):
        return self.page.evaluate("Donnees.aujourdhui()")

    def etat(self, gamme_id):
        return self.page.evaluate("id => Preventif.etatGamme(id)", gamme_id)

    def generer(self):
        return self.page.evaluate("Preventif.genererOTEchus()")

    def ajouter_releve(self, compteur_id, date, valeur):
        self.page.evaluate("""([compteur, date, valeur]) => Donnees.modifier('releves', (lignes, outils) => {
            lignes.push({ id: outils.nouvelId(lignes), compteur_id: compteur, date, valeur: String(valeur), utilisateur: 'Test' });
        })""", [compteur_id, date, valeur])

    def modifier_ligne(self, table, identifiant, changements):
        """Modifie une ligne par Donnees.modifier dans la page (comme un autre écran de Prévo)."""
        self.page.evaluate("""([table, id, changements]) => Donnees.modifier(table, (lignes) => {
            Object.assign(lignes.find((l) => l.id === id), changements);
        })""", [table, identifiant, changements])

    def attendre_toast(self, motif):
        """Attend que le texte du toast corresponde à `motif` et renvoie le texte lu à ce moment-là
        (le relire ensuite par inner_text rendrait '' si le toast a été masqué entre-temps)."""
        return self.page.wait_for_function(
            """motif => { const texte = document.getElementById('toast').textContent.trim();
                return new RegExp(motif).test(texte) ? texte : null; }""", arg=motif).json_value()

    # Un toast reste affiché 4 s, puis il est masqué (visibility: hidden : inner_text rend alors '')
    # ou remplacé par le suivant. Sur un poste chargé, le lire APRÈS coup échoue au hasard. Ce script,
    # installé avant tout chargement de page, note le texte de chaque toast au moment où il s'affiche.
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

    def noter_les_toasts(self):
        """À appeler AVANT d'ouvrir la page : chaque toast affiché est noté dans window.__toasts."""
        self.contexte.add_init_script(self.NOTER_TOASTS_JS)

    def attendre_toast_note(self, motif):
        """Attend qu'un toast affiché depuis le chargement de la page corresponde à `motif` (expression
        régulière) et renvoie son texte (tel qu'affiché, même s'il a disparu depuis)."""
        return self.page.wait_for_function(
            "motif => (window.__toasts || []).find((texte) => new RegExp(motif).test(texte)) || null",
            arg=motif).json_value()

    def sans_defilement_horizontal(self):
        return self.page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")

    def assert_au_plus_un_ot_ouvert_par_gamme(self, dossier):
        compte = {}
        for ot in lire_csv(dossier, "ordres_travail.csv"):
            if ot["gamme_id"] and ot["statut"] not in STATUTS_FERMES:
                compte[ot["gamme_id"]] = compte.get(ot["gamme_id"], 0) + 1
        self.assertEqual({g: n for g, n in compte.items() if n > 1}, {})

    def assert_ot_operations_sans_doublon(self, dossier):
        cles = [(op["ot_id"], op["ordre"]) for op in lire_csv(dossier, "ot_operations.csv")]
        self.assertEqual(len(cles), len(set(cles)), "ot_operations.csv contient des doublons")


# ---------------------------------------------------------------------------
# unique : un seul OT par gamme échue, quoi qu'il arrive
# ---------------------------------------------------------------------------

class TestUnique(CasPreventif):

    def test_unique_ouverture_responsable_un_ot_complet_puis_trois_rechargements_sans_doublon(self):
        with ServeurPrevo() as serveur:
            page = self.ouvrir(serveur)
            jour = self.aujourdhui()
            self.assertRegex(self.attendre_toast(TOAST_GENERATION.pattern), TOAST_GENERATION)
            gamme = par_id(serveur.dossier, "gammes.csv")[GAMME_ECHUE]

            ouverts = ots_ouverts_de(serveur.dossier, GAMME_ECHUE)
            self.assertEqual(len(ouverts), 1, ouverts)
            ot = ouverts[0]
            self.assertRegex(ot["id"], r"^OT-\d{4}-\d{4}$")
            attendu = {"origine": "préventif", "gamme_id": GAMME_ECHUE, "equipement_id": gamme["equipement_id"],
                       "type": "préventif systématique", "priorite": "P3", "statut": "Créé",
                       "titre": brut(gamme["libelle"]), "consignes": brut(gamme["consignes"]), "date_prevue": jour}
            self.assertEqual({cle: brut(ot[cle]) for cle in attendu}, attendu)
            self.assertEqual(nombre(ot["temps_prevu_h"]), nombre(gamme["temps_prevu_h"]))
            self.assertEqual(ot["date_creation"][:10], jour)
            self.assertIn(GAMME_ECHUE, ot["travail_a_faire"])

            check_liste = operations_de_gamme(serveur.dossier, GAMME_ECHUE)
            self.assertGreater(len(check_liste), 0)
            copie = operations_d_ot(serveur.dossier, ot["id"])
            self.assertEqual(copie, [operation + ("0",) for operation in check_liste])

            # Journal : la création de l'OT est tracée, avec la raison (génération RG5).
            creations = [j for j in lire_csv(serveur.dossier, "journal.csv")
                         if j["table"] == "ordres_travail" and j["id_ligne"] == ot["id"]]
            self.assertEqual(len(creations), 1, creations)
            self.assertIn("génération du préventif (RG5)", creations[0]["action"])

            # Plus aucune gamme échue sans OT ; au plus un OT ouvert par gamme.
            self.assertEqual(page.evaluate(
                "Donnees.lignes('gammes').filter((g) => Preventif.etatGamme(g).statut === 'echue').map((g) => g.id)"), [])
            self.assertEqual(self.etat(GAMME_ECHUE)["otOuvertId"], ot["id"])
            self.assert_au_plus_un_ot_ouvert_par_gamme(serveur.dossier)

            octets_ot = (serveur.dossier / "ordres_travail.csv").read_bytes()
            for _ in range(3):
                page.reload()
                attendre_pret(page)
                self.assertEqual([o["id"] for o in ots_ouverts_de(serveur.dossier, GAMME_ECHUE)], [ot["id"]])
            self.assertEqual((serveur.dossier / "ordres_travail.csv").read_bytes(), octets_ot)
            self.assertEqual(operations_d_ot(serveur.dossier, ot["id"]), copie)
            self.assert_ot_operations_sans_doublon(serveur.dossier)

    def test_unique_deux_postes_ouverts_en_meme_temps_un_seul_ot_par_gamme_echue(self):
        self.autoriser_erreur(CONFLIT_GENERATION)
        with ServeurPrevo() as serveur:
            echues_avant = [g["id"] for g in lire_csv(serveur.dossier, "gammes.csv")]
            pages = []
            for profil, technicien in (("technicien", TECHNICIEN), ("responsable", "")):
                contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
                self.addCleanup(contexte.close)
                contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
                preregler_profil(contexte, profil, technicien_id=technicien, poste="Poste " + profil)
                page = contexte.new_page()
                self.surveiller(page)
                pages.append(page)
            for page in pages:                         # navigations lancées ensemble
                page.goto(serveur.url + "/#/accueil", wait_until="commit")
            for page in pages:
                attendre_pret(page)

            self.assertEqual(len(ots_ouverts_de(serveur.dossier, GAMME_ECHUE)), 1)
            self.assert_au_plus_un_ot_ouvert_par_gamme(serveur.dossier)
            self.assert_ot_operations_sans_doublon(serveur.dossier)
            ot_id = ots_ouverts_de(serveur.dossier, GAMME_ECHUE)[0]["id"]
            self.assertEqual(len(operations_d_ot(serveur.dossier, ot_id)), len(operations_de_gamme(serveur.dossier, GAMME_ECHUE)))
            for page in pages:                         # les deux postes voient le même OT
                self.assertEqual(page.evaluate("id => Preventif.etatGamme(id).otOuvertId", GAMME_ECHUE), ot_id)
                self.assertEqual(page.evaluate(
                    "ids => ids.filter((id) => Preventif.etatGamme(id).statut === 'echue')", echues_avant), [])

    def test_unique_cache_perime_la_decision_est_prise_sur_les_lignes_fraiches(self):
        self.autoriser_erreur(CONFLIT_GENERATION)
        with ServeurPrevo() as serveur:
            # Poste A : chargé AVANT que le poste B ne génère ; sa copie des OT reste périmée.
            self.ouvrir(serveur, profil="demandeur", nom="Lucie Test")
            self.page.evaluate("Donnees.arreterSurveillance()")
            self.assertEqual(self.etat(GAMME_ECHUE)["statut"], "echue")
            contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
            self.addCleanup(contexte.close)
            preregler_profil(contexte, "responsable", poste="Poste B")
            page_b = contexte.new_page()
            self.surveiller(page_b)
            page_b.goto(serveur.url + "/#/accueil")
            attendre_pret(page_b)
            ot_b = ots_ouverts_de(serveur.dossier, GAMME_ECHUE)
            self.assertEqual(len(ot_b), 1)
            # A génère : son cache dit « échue sans OT », mais l'écriture est refusée (409), la table
            # est relue et la fonction rejouée sur les lignes fraîches : aucun second OT.
            conflits_avant = self.page.evaluate("Donnees.statistiques.conflits")
            self.assertEqual(self.generer(), [])
            self.assertGreater(self.page.evaluate("Donnees.statistiques.conflits"), conflits_avant)
            self.assertEqual(ots_ouverts_de(serveur.dossier, GAMME_ECHUE), ot_b)
            self.assertEqual(self.etat(GAMME_ECHUE)["otOuvertId"], ot_b[0]["id"])
            self.assert_ot_operations_sans_doublon(serveur.dossier)

    def test_unique_un_demandeur_qui_ouvre_l_application_ne_genere_rien(self):
        with ServeurPrevo() as serveur:
            fichiers = ("ordres_travail.csv", "ot_operations.csv", "journal.csv", "gammes.csv")
            avant = {nom: (serveur.dossier / nom).read_bytes() for nom in fichiers}
            self.ouvrir(serveur, profil="demandeur", nom="Lucie Test")
            for nom in fichiers:
                self.assertEqual((serveur.dossier / nom).read_bytes(), avant[nom], nom)
            self.assertEqual(self.etat(GAMME_ECHUE)["statut"], "echue")
            self.assertEqual(self.page.evaluate("performance.getEntriesByName('prevo:preventif').length"), 1)


# ---------------------------------------------------------------------------
# cloture : apresCloture
# ---------------------------------------------------------------------------

class TestCloture(CasPreventif):

    def cloturer(self, ot_id, jour):
        self.modifier_ligne("ordres_travail", ot_id, {
            "statut": "Clôturé techniquement", "date_debut": jour + " 08:00", "date_fin": jour + " 10:30",
            "date_cloture_tech": jour + " 10:35", "remise_service": "1"})

    def test_cloture_gamme_mensuelle_realisee_aujourd_hui_echeance_le_mois_suivant_second_appel_sans_effet(self):
        with ServeurPrevo() as serveur:
            page = self.ouvrir(serveur)
            jour = self.aujourdhui()
            ot_id = self.etat(GAMME_ECHUE)["otOuvertId"]
            self.assertTrue(ot_id)
            self.cloturer(ot_id, jour)
            self.assertTrue(page.evaluate("id => Preventif.apresCloture(id)", ot_id))

            gamme = par_id(serveur.dossier, "gammes.csv")[GAMME_ECHUE]
            periodicite = int(brut(gamme["periodicite_jours"]))
            self.assertTrue(28 <= periodicite <= 31, periodicite)      # gamme mensuelle : le mois suivant
            self.assertEqual(gamme["derniere_realisation"], jour)
            self.assertEqual(gamme["prochaine_echeance"], plus_jours(jour, periodicite))
            journal = [j["action"] for j in lire_csv(serveur.dossier, "journal.csv")
                       if j["table"] == "gammes" and j["id_ligne"] == GAMME_ECHUE]
            self.assertTrue(any("réalisation de la gamme par l'OT " + ot_id in action for action in journal), journal)

            octets = (serveur.dossier / "gammes.csv").read_bytes()
            self.assertFalse(page.evaluate("id => Preventif.apresCloture(id)", ot_id))
            self.assertEqual((serveur.dossier / "gammes.csv").read_bytes(), octets)

            # La gamme est à jour : la génération ne crée plus rien pour elle.
            self.assertEqual(self.etat(GAMME_ECHUE)["statut"], "a_jour")
            crees = self.generer()
            self.assertNotIn(GAMME_ECHUE, [o["gamme_id"] for o in lire_csv(serveur.dossier, "ordres_travail.csv")
                                            if o["id"] in crees])
            self.assertEqual(ots_ouverts_de(serveur.dossier, GAMME_ECHUE), [])

    def test_cloture_gamme_au_compteur_base_au_dernier_releve_et_echeance_estimee(self):
        with ServeurPrevo() as serveur:
            page = self.ouvrir(serveur)
            jour = self.aujourdhui()
            ot_id = self.etat(GAMME_COMPTEUR_ECHUE)["otOuvertId"]
            self.assertTrue(ot_id)
            self.cloturer(ot_id, jour)
            self.assertTrue(page.evaluate("id => Preventif.apresCloture(id)", ot_id))

            gamme = par_id(serveur.dossier, "gammes.csv")[GAMME_COMPTEUR_ECHUE]
            releves = [r for r in lire_csv(serveur.dossier, "releves.csv")
                       if r["compteur_id"] == gamme["compteur_id"] and r["date"] <= jour]
            dernier = max(releves, key=lambda r: (r["date"], r["id"]))
            self.assertEqual(gamme["derniere_realisation"], jour)
            self.assertEqual(nombre(gamme["releve_derniere_realisation"]), nombre(dernier["valeur"]))
            # Échéance estimée : date du relevé + périodicité / heures de fonctionnement par jour.
            equipement = par_id(serveur.dossier, "equipements.csv")[gamme["equipement_id"]]
            heures_par_jour = nombre(equipement["heures_fonct_jour"]) if equipement["heures_fonct_jour"] else 8.0
            jours = -(-nombre(gamme["periodicite_unites"]) // heures_par_jour)
            self.assertEqual(gamme["prochaine_echeance"], plus_jours(dernier["date"], int(jours)))
            self.assertIn(self.etat(GAMME_COMPTEUR_ECHUE)["statut"], ("a_jour", "bientot"))


# ---------------------------------------------------------------------------
# declencheur : compteur et seuil
# ---------------------------------------------------------------------------

class TestDeclencheur(CasPreventif):

    def test_declencheur_compteur_qui_atteint_la_periodicite_puis_seuil_atteint(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur)
            jour = self.aujourdhui()
            gammes = par_id(serveur.dossier, "gammes.csv")

            gamme = gammes[GAMME_COMPTEUR]
            self.assertNotIn(self.etat(GAMME_COMPTEUR)["statut"], ("echue", "ot_ouvert"))
            atteint = nombre(gamme["releve_derniere_realisation"]) + nombre(gamme["periodicite_unites"])
            self.ajouter_releve(gamme["compteur_id"], jour, atteint)
            crees = self.generer()
            self.assertEqual(len(crees), 1, crees)
            ot = par_id(serveur.dossier, "ordres_travail.csv")[crees[0]]
            self.assertEqual((ot["gamme_id"], ot["origine"], ot["type"], ot["statut"]),
                             (GAMME_COMPTEUR, "préventif", "préventif systématique", "Créé"))
            self.assertEqual(len(operations_d_ot(serveur.dossier, ot["id"])), len(operations_de_gamme(serveur.dossier, GAMME_COMPTEUR)))

            seuil = nombre(gammes[GAMME_SEUIL]["seuil"])
            self.assertEqual(gammes[GAMME_SEUIL]["compteur_id"], COMPTEUR_SEUIL)
            self.ajouter_releve(COMPTEUR_SEUIL, jour, round(seuil + 0.05, 2))
            crees = self.generer()
            self.assertEqual(len(crees), 1, crees)
            ot = par_id(serveur.dossier, "ordres_travail.csv")[crees[0]]
            self.assertEqual((ot["gamme_id"], ot["origine"], ot["type"], ot["statut"]),
                             (GAMME_SEUIL, "préventif", "préventif conditionnel", "Créé"))
            self.assertEqual(self.generer(), [])                       # idempotent
            self.assert_au_plus_un_ot_ouvert_par_gamme(serveur.dossier)

    def test_declencheur_seuil_atteint_mais_releve_anterieur_a_la_derniere_realisation_aucun_ot(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur)
            jour = self.aujourdhui()
            seuil = nombre(par_id(serveur.dossier, "gammes.csv")[GAMME_SEUIL]["seuil"])
            self.modifier_ligne("gammes", GAMME_SEUIL, {"derniere_realisation": jour})
            self.ajouter_releve(COMPTEUR_SEUIL, plus_jours(jour, -1), round(seuil + 0.1, 2))
            etat = self.etat(GAMME_SEUIL)
            self.assertEqual(etat["statut"], "a_jour", etat)
            self.assertIn("antérieur à la dernière réalisation", etat["raison"])
            self.assertEqual(self.generer(), [])
            self.assertEqual(ots_ouverts_de(serveur.dossier, GAMME_SEUIL), [])


# ---------------------------------------------------------------------------
# ecrans
# ---------------------------------------------------------------------------

class TestEcrans(CasPreventif):

    def ligne_gamme(self, gamme_id):
        return self.page.locator('.pv-liste-tableau tbody tr:has(a[href="#/preventif/gamme/%s"])' % gamme_id)

    def lignes_affichees(self):
        return self.page.eval_on_selector_all(
            ".pv-liste-tableau tbody tr a[href^='#/preventif/gamme/']", "liens => liens.map((a) => a.getAttribute('href').split('/').pop())")

    def test_ecrans_liste_statuts_filtres_et_bouton_generer(self):
        with ServeurPrevo() as serveur:
            page = self.ouvrir(serveur, "#/preventif")
            page.wait_for_selector(".pv-liste-tableau tbody tr")
            self.assertEqual(page.evaluate("location.hash"), "#/preventif?onglet=gammes")
            gammes = lire_csv(serveur.dossier, "gammes.csv")
            self.assertEqual(sorted(self.lignes_affichees()), sorted(g["id"] for g in gammes))

            # Chaque ligne : statut calculé (badge + raison) et lien vers l'OT ouvert.
            etats = page.evaluate("""() => Object.fromEntries(Donnees.lignes('gammes').map((g) => {
                const e = Preventif.etatGamme(g); return [g.id, [Preventif.STATUTS_GAMME[e.statut], e.raison, e.otOuvertId]]; }))""")
            for gamme_id, (libelle, raison, ot_ouvert) in etats.items():
                ligne = self.ligne_gamme(gamme_id)
                self.assertEqual(ligne.locator(".badge.statut").inner_text().strip(), libelle, gamme_id)
                self.assertEqual(ligne.locator(".pv-raison").inner_text().strip(), raison, gamme_id)
                if ot_ouvert:
                    self.assertEqual(ligne.locator('a[href="#/ot/%s"]' % ot_ouvert).count(), 1, gamme_id)
            self.assertEqual(etats[GAMME_ECHUE][0], "OT ouvert")
            self.assertEqual(etats[GAMME_SEUIL][0], "À jour")

            # Filtres : statut, puis équipement.
            page.select_option("#pv-filtre-statut", "bientot")
            attendus = sorted(g for g, e in etats.items() if e[0] == "Bientôt")
            self.assertEqual(sorted(self.lignes_affichees()), attendus)
            page.select_option("#pv-filtre-statut", "")
            equipement = par_id(serveur.dossier, "gammes.csv")[GAMME_SEUIL]["equipement_id"]
            page.select_option("#pv-filtre-equipement", equipement)
            self.assertEqual(sorted(self.lignes_affichees()), sorted(g["id"] for g in gammes if g["equipement_id"] == equipement))
            page.select_option("#pv-filtre-equipement", "")

            # « Générer les OT échus » : rien (déjà fait à l'ouverture), puis une gamme rendue échue.
            page.click("#pv-generer")
            self.assertEqual(self.attendre_toast("^Aucune gamme échue"), "Aucune gamme échue.")
            autre = next(g["id"] for g in gammes if g["declencheur"] == "date" and etats[g["id"]][0] in ("Bientôt", "À jour"))
            self.modifier_ligne("gammes", autre, {"prochaine_echeance": plus_jours(self.aujourdhui(), -1)})
            page.click("#pv-generer")
            self.assertEqual(self.attendre_toast("^1 OT préventif généré"), "1 OT préventif généré.")
            self.assertEqual(len(ots_ouverts_de(serveur.dossier, autre)), 1)
            page.wait_for_function("id => document.querySelector('.pv-liste-tableau tbody tr:has(a[href=\"#/preventif/gamme/' + id + '\"]) .badge.statut').textContent === 'OT ouvert'", arg=autre)

    def test_ecrans_creation_gamme_check_liste_modification_ordre_suppression_journalisee(self):
        with ServeurPrevo() as serveur:
            page = self.ouvrir(serveur, "#/preventif")
            equipement = par_id(serveur.dossier, "gammes.csv")[GAMME_ECHUE]["equipement_id"]
            page.click("#pv-nouvelle")
            page.wait_for_selector("#pv-formulaire-gamme")
            formulaire = "#pv-formulaire-gamme "
            self.assertTrue(page.is_visible(formulaire + "[data-champ=periodicite_jours]"))
            self.assertFalse(page.is_visible(formulaire + "[data-champ=compteur_id]"))
            page.select_option(formulaire + "[name=declencheur]", "compteur")      # champs selon le déclencheur
            self.assertTrue(page.is_visible(formulaire + "[data-champ=compteur_id]"))
            self.assertFalse(page.is_visible(formulaire + "[data-champ=periodicite_jours]"))
            page.select_option(formulaire + "[name=declencheur]", "date")
            page.click(formulaire + "button[type=submit]")                        # vide : erreurs, rien d'écrit
            self.assertTrue(page.is_visible(formulaire + "[data-champ=libelle] .erreur-champ"))
            page.select_option(formulaire + "[name=equipement_id]", equipement)
            page.fill(formulaire + "[name=libelle]", "Contrôle des carters (test)")
            page.fill(formulaire + "[name=periodicite_jours]", "45")
            page.fill(formulaire + "[name=avance_jours]", "2")
            page.fill(formulaire + "[name=temps_prevu_h]", "1,5")
            page.fill(formulaire + "[name=consignes]", "Consigner avant ouverture.")
            page.click(formulaire + "button[type=submit]")
            page.wait_for_function("/^#\\/preventif\\/gamme\\/GAM-\\d+$/.test(location.hash)")
            gamme_id = page.evaluate("location.hash.split('/').pop()")
            gamme = par_id(serveur.dossier, "gammes.csv")[gamme_id]
            self.assertEqual({c: brut(gamme[c]) for c in ("equipement_id", "libelle", "declencheur", "periodicite_jours",
                                                           "avance_jours", "temps_prevu_h", "actif")},
                             {"equipement_id": equipement, "libelle": "Contrôle des carters (test)", "declencheur": "date",
                              "periodicite_jours": "45", "avance_jours": "2", "temps_prevu_h": "1.5", "actif": "1"})

            # Check-list : trois opérations ajoutées dans l'ordre.
            operations = [("Contrôler la fixation des carters", "Serrage OK"), ("Vérifier les protections", ""),
                          ("Nettoyer la zone", "Propre")]
            for rang, (texte, attendue) in enumerate(operations, start=1):
                page.fill("#pv-nouvelle-operation", texte)
                page.fill("#pv-nouvelle-attendue", attendue)
                page.click("#pv-ajout-operation button[type=submit]")
                page.wait_for_function("n => document.querySelectorAll('.pv-operations .pv-operation').length === n", arg=rang)
            sur_disque = operations_de_gamme(serveur.dossier, gamme_id)
            self.assertEqual(sur_disque, [(rang, t, a) for rang, (t, a) in enumerate(operations, start=1)])
            ids = [op["id"] for op in sorted((op for op in lire_csv(serveur.dossier, "gamme_operations.csv")
                                              if op["gamme_id"] == gamme_id), key=lambda op: int(brut(op["ordre"])))]

            # Modification de la gamme.
            page.fill(formulaire + "[name=periodicite_jours]", "60")
            page.click(formulaire + "button[type=submit]")
            self.attendre_toast("^Gamme enregistrée")
            self.assertEqual(brut(par_id(serveur.dossier, "gammes.csv")[gamme_id]["periodicite_jours"]), "60")

            # Modification d'une opération (fenêtre).
            page.click('[data-operation="%s"] [data-action="modifier"]' % ids[1])
            page.fill("#pv-modif-operation", "Vérifier les protections et les arrêts d'urgence")
            page.click("dialog .fenetre-actions .btn-primaire")
            page.wait_for_function("t => document.querySelector('.pv-operations').textContent.includes(t)", arg="arrêts d'urgence")
            self.assertEqual(par_id(serveur.dossier, "gamme_operations.csv")[ids[1]]["operation"],
                             "Vérifier les protections et les arrêts d'urgence")

            # Réordonnancement : la première descend d'un cran.
            page.click('[data-operation="%s"] [data-action="descendre"]' % ids[0])
            page.wait_for_function("id => document.querySelector('.pv-operations .pv-operation').dataset.operation === id", arg=ids[1])
            lignes = par_id(serveur.dossier, "gamme_operations.csv")
            self.assertEqual([brut(lignes[i]["ordre"]) for i in ids], ["2", "1", "3"])

            # Suppression de la troisième : ligne absente du fichier, entrée dans le journal.
            page.click('[data-operation="%s"] [data-action="supprimer"]' % ids[2])
            page.click("dialog .fenetre-actions .btn-danger")
            page.wait_for_function("() => document.querySelectorAll('.pv-operations .pv-operation').length === 2")
            self.attendre_toast("^Opération supprimée")
            lignes = par_id(serveur.dossier, "gamme_operations.csv")
            self.assertNotIn(ids[2], lignes)
            self.assertEqual(sorted(brut(lignes[i]["ordre"]) for i in ids[:2]), ["1", "2"])
            suppressions = [j for j in lire_csv(serveur.dossier, "journal.csv") if j["table"] == "gamme_operations"
                            and j["id_ligne"] == ids[2] and j["action"].startswith("suppression")]
            self.assertEqual(len(suppressions), 1, suppressions)
            self.assertIn("« Nettoyer la zone »", suppressions[0]["action"])
            self.assertEqual(suppressions[0]["profil"], "Responsable")

    def test_ecrans_calendrier_de_12_semaines_avec_l_echeance_de_cv01(self):
        with ServeurPrevo() as serveur:
            page = self.ouvrir(serveur, "#/preventif?onglet=calendrier")
            page.wait_for_selector(".pv-calendrier .pv-semaine")
            self.assertEqual(page.get_attribute(".onglet[data-onglet='calendrier']", "aria-selected"), "true")
            lundis = page.eval_on_selector_all(".pv-calendrier .pv-semaine", "s => s.map((e) => e.dataset.lundi)")
            self.assertEqual(len(lundis), 12)
            jour = datetime.date.fromisoformat(self.aujourdhui())
            premier = jour - datetime.timedelta(days=jour.weekday())
            self.assertEqual(lundis, [(premier + datetime.timedelta(weeks=n)).isoformat() for n in range(12)])

            # L'échéance de CV-01 (gamme mensuelle échue) : son OT généré, dans la semaine en cours.
            gamme = par_id(serveur.dossier, "gammes.csv")[GAMME_ECHUE]
            repere = par_id(serveur.dossier, "equipements.csv")[gamme["equipement_id"]]["repere"]
            element = page.locator('.pv-semaine[data-lundi="%s"] .pv-element[data-gamme="%s"]' % (lundis[0], GAMME_ECHUE))
            self.assertEqual(element.count(), 1)
            self.assertIn(brut(repere), element.inner_text())
            ot_id = self.etat(GAMME_ECHUE)["otOuvertId"]
            self.assertEqual(element.locator('a[href="#/ot/%s"]' % ot_id).count(), 1)

            # Mêmes éléments que Preventif.calendrier ; « estimée » pour les gammes au compteur.
            attendu = page.evaluate("""() => Preventif.calendrier(Donnees.aujourdhui())
                .map((s) => [s.elements.length, s.elements.filter((e) => e.estimee).length])""")
            affiche = page.eval_on_selector_all(".pv-calendrier .pv-semaine", """s => s.map((e) => [
                e.querySelectorAll('.pv-element').length,
                Array.from(e.querySelectorAll('.pv-element')).filter((l) => l.textContent.includes('estimée')).length])""")
            self.assertEqual(affiche, attendu)

            page.click(".onglet[data-onglet='gammes']")
            page.wait_for_function("location.hash === '#/preventif?onglet=gammes'")

    def test_ecrans_technicien_en_lecture_seule(self):
        with ServeurPrevo() as serveur:
            page = self.ouvrir(serveur, "#/preventif", profil="technicien", technicien_id=TECHNICIEN)
            page.wait_for_selector(".pv-liste-tableau tbody tr")
            self.assertEqual(page.locator("#menu a[href='#/preventif']").count(), 1)
            self.assertEqual(page.locator("#pv-nouvelle, #pv-generer").count(), 0)

            page.evaluate("id => { location.hash = '#/preventif/gamme/' + id; }", GAMME_ECHUE)
            page.wait_for_selector(".pv-fiche .valeurs")
            self.assertEqual(page.locator("#pv-formulaire-gamme, #pv-ajout-operation, .pv-fiche button[data-action]").count(), 0)
            self.assertEqual(page.locator(".pv-operations .pv-operation").count(),
                             len(operations_de_gamme(serveur.dossier, GAMME_ECHUE)))
            ot_id = self.etat(GAMME_ECHUE)["otOuvertId"]
            self.assertGreater(page.locator('.pv-ots a[href="#/ot/%s"]' % ot_id).count(), 0)

            page.evaluate("location.hash = '#/preventif/gamme/nouvelle'")
            page.wait_for_function("location.hash === '#/accueil'")
            self.assertIn("n'est pas disponible", self.attendre_toast("pas disponible"))

    def test_ecrans_demandeur_sans_acces(self):
        with ServeurPrevo() as serveur:
            page = self.ouvrir(serveur, "#/preventif", profil="demandeur", nom="Lucie Test")
            page.wait_for_function("location.hash === '#/accueil'")
            self.assertEqual(page.locator("#menu a[href='#/preventif']").count(), 0)
            self.assertIn("n'est pas disponible", self.attendre_toast("pas disponible"))

    def test_ecrans_telephone_375_px_sans_defilement_horizontal(self):
        with ServeurPrevo() as serveur:
            page = self.ouvrir(serveur, "#/preventif", largeur=375)
            page.wait_for_selector(".pv-liste-cartes .carte-ligne")
            self.assertFalse(page.is_visible(".pv-liste-tableau"))
            self.assertTrue(self.sans_defilement_horizontal(), "liste des gammes")
            page.click(".onglet[data-onglet='calendrier']")
            page.wait_for_selector(".pv-calendrier .pv-semaine")
            self.assertTrue(self.sans_defilement_horizontal(), "calendrier")
            page.evaluate("id => { location.hash = '#/preventif/gamme/' + id; }", GAMME_ECHUE)
            page.wait_for_selector(".pv-operations [data-action='descendre']")
            self.assertTrue(self.sans_defilement_horizontal(), "fiche de la gamme")
            for selecteur in (".pv-operations [data-action='descendre']", ".pv-operations [data-action='supprimer']",
                              "#pv-ajout-operation button[type=submit]", "#pv-formulaire-gamme button[type=submit]"):
                hauteur = page.locator(selecteur).first.bounding_box()["height"]
                self.assertGreaterEqual(hauteur, 48, selecteur)


# ---------------------------------------------------------------------------
# demarrage : format des fichiers, base vide, démo, marques de performance
# ---------------------------------------------------------------------------

def version_schema(dossier):
    for ligne in lire_csv(dossier, "parametres.csv"):
        if ligne["cle"] == "version_schema":
            return brut(ligne["valeur"])
    return None


def sauvegardes_avant_format(dossier):
    racine = Path(dossier) / "sauvegardes"
    return sorted(p.name for p in racine.glob("*_avant-format-v2")) if racine.is_dir() else []


class TestDemarrage(CasPreventif):

    def test_demarrage_creer_une_base_vide_ecrit_le_format_courant_sans_sauvegarde(self):
        self.autoriser_erreur(ERREUR_CSV_ABSENT)
        preregler_profil(self.contexte, "responsable")
        with ServeurPrevo(source=None) as serveur:
            self.page.goto(serveur.url + "/")
            self.page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
            self.page.click("#btn-base-vide")
            attendre_pret(self.page)
            courante = str(self.page.evaluate("Schema.version"))
            self.assertEqual(version_schema(serveur.dossier), courante)
            self.assertEqual(self.page.evaluate("Donnees.parametre('version_schema')"), courante)
            self.assertEqual(sauvegardes_avant_format(serveur.dossier), [])
            self.assertEqual(lire_csv(serveur.dossier, "journal.csv"), [])     # rien d'autre n'a été écrit
            self.assertEqual(self.page.evaluate("performance.getEntriesByName('prevo:preventif').length"), 1)

    def test_demarrage_base_au_format_1_sauvegarde_puis_format_2_pour_tous_les_profils(self):
        with ServeurPrevo() as serveur:
            shutil.copyfile(str(PARAMETRES_V1), str(serveur.dossier / "parametres.csv"))
            self.ouvrir(serveur, profil="demandeur", nom="Lucie Test")
            sauvegardes = sauvegardes_avant_format(serveur.dossier)
            self.assertEqual(len(sauvegardes), 1, sauvegardes)
            copie = serveur.dossier / "sauvegardes" / sauvegardes[0] / "parametres.csv"
            self.assertEqual(copie.read_bytes(), PARAMETRES_V1.read_bytes())      # état d'avant
            self.assertEqual(version_schema(serveur.dossier), "2")
            self.assertEqual(self.page.evaluate("Donnees.parametre('version_schema')"), "2")
            self.page.reload()
            attendre_pret(self.page)
            self.assertEqual(sauvegardes_avant_format(serveur.dossier), sauvegardes)   # pas de seconde sauvegarde

    def test_demarrage_sauvegarde_impossible_aucun_ot_genere_application_utilisable_puis_nouvel_essai(self):
        """Pas de passage au format 2 sans sauvegarde confirmée (décision de Nicolas) : sauvegarde
        impossible → version inchangée, AUCUNE génération automatique à cette ouverture (elle
        écrirait ordres_travail et ot_operations au format 2), application utilisable ; l'ouverture
        suivante retente tout (sauvegarde, format, génération)."""
        self.autoriser_erreur(re.compile(r"status of 500.*/api/sauvegarde"))
        with ServeurPrevo() as serveur:
            shutil.copyfile(str(PARAMETRES_V1), str(serveur.dossier / "parametres.csv"))
            self.assertEqual(ots_ouverts_de(serveur.dossier, GAMME_ECHUE), [])     # gamme échue sans OT ouvert
            ordres_avant = (serveur.dossier / "ordres_travail.csv").read_bytes()
            operations_avant = (serveur.dossier / "ot_operations.csv").read_bytes()
            corps = json.dumps({"erreur": "Disque plein (simulé)."})
            self.page.route("**/api/sauvegarde", lambda route: route.fulfill(
                status=500, content_type="application/json; charset=utf-8", body=corps))
            self.ouvrir(serveur)
            self.page.wait_for_load_state("networkidle")
            self.assertEqual(version_schema(serveur.dossier), "1")
            self.assertEqual(sauvegardes_avant_format(serveur.dossier), [])
            # Aucun OT généré : les deux fichiers sont inchangés sur le disque
            self.assertEqual(ots_ouverts_de(serveur.dossier, GAMME_ECHUE), [])
            self.assertEqual((serveur.dossier / "ordres_travail.csv").read_bytes(), ordres_avant)
            self.assertEqual((serveur.dossier / "ot_operations.csv").read_bytes(), operations_avant)
            alertes = self.page.inner_text("#alertes-app")
            self.assertIn("Disque plein (simulé)", alertes)
            self.assertIn("les OT préventifs échus ne sont pas générés automatiquement", alertes)
            self.assertEqual(self.page.evaluate("performance.getEntriesByName('prevo:preventif').length"), 1)
            # Application utilisable : écran Préventif, bouton « Générer les OT échus » du responsable
            self.page.click("#menu a[href='#/preventif']")
            self.page.wait_for_selector(".pv-liste-tableau tbody tr")
            self.assertTrue(self.page.is_visible("#pv-generer"))

            self.page.unroute("**/api/sauvegarde")
            self.page.reload()
            attendre_pret(self.page)
            self.assertEqual(version_schema(serveur.dossier), "2")
            self.assertEqual(len(sauvegardes_avant_format(serveur.dossier)), 1)
            self.assertEqual(len(ots_ouverts_de(serveur.dossier, GAMME_ECHUE)), 1)     # génération à cette ouverture

    def test_demarrage_demo_generation_a_l_ouverture_toast_et_marques(self):
        self.noter_les_toasts()
        preregler_profil(self.contexte, "responsable")
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        # Le toast de génération a été affiché (noté à son apparition : il a pu disparaître depuis)
        self.assertRegex(self.attendre_toast_note(TOAST_GENERATION.pattern), TOAST_GENERATION)
        ot_id = self.etat(GAMME_ECHUE)["otOuvertId"]
        self.assertTrue(ot_id)
        ot = self.page.evaluate("id => Donnees.trouver('ordres_travail', id)", ot_id)
        self.assertEqual((ot["origine"], ot["gamme_id"], ot["statut"]), ("préventif", GAMME_ECHUE, "Créé"))
        self.assertGreater(self.page.evaluate("id => Donnees.lignes('ot_operations').filter((o) => o.ot_id === id).length", ot_id), 0)
        marques = self.page.evaluate("""() => ['prevo:preventif', 'prevo:pret'].map(
            (nom) => performance.getEntriesByName(nom).map((m) => m.startTime))""")
        self.assertEqual([len(m) for m in marques], [1, 1])
        self.assertLessEqual(marques[0][0], marques[1][0])


if __name__ == "__main__":
    unittest.main()
