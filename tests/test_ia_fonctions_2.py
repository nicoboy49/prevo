"""Fonctions IA de la gamme, de la fiche équipement et du rapport (lot 4, ARCHITECTURE.md §17.5,
points 4 à 6 ; CDC D65, D69, D71 ; CS66, CS68). Faux fournisseur seulement, mode serveur : le fournisseur est
réglé sur le PC serveur (--ia-url, audit M1, §22.12), le poste ne règle que l'activation et le modèle.

    - check-list (fiche gamme, responsable) : opérations cochables ; RIEN n'est écrit avant « Ajouter
      les opérations cochées », puis seules les cochées s'ajoutent (journal habituel + trace IA) ;
      Ignorer : rien ; technicien : pas de bouton ;
    - résumé de l'historique : retiré au lot 6 (le wiki le remplace) — aucune carte sur la fiche équipement, quel
      que soit le profil ; l'emplacement d'un bouton IA (posé à la fin du test d'ouverture, message d'erreur
      gardé quand le bouton s'en va) est éprouvé sur la check-list de la fiche gamme ;
    - commentaire du rapport (onglet Rapports, responsable) : un chiffre écrit en clair par l'IA fait
      refuser la proposition ; sinon les jetons sont remplacés par les chiffres du rapport ; rien n'est
      figé sans « Figer le rapport » ; le rapport figé porte le commentaire et la mention « rédigé avec
      l'aide de l'IA » ; un commentaire écrit à la main n'a pas la mention ;
    - sans IA : aucun de ces boutons.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_ia_fonctions_2.py" -v
"""
import csv
import html
import io
import json
import re
import time
import unittest

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, scenarios_demo
from faux_fournisseur_ia import FauxFournisseur
from test_ia_regles import noms_de_la_demo, regler_ia, taire_coupures

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


def lire_csv(dossier, nom):
    texte = (dossier / nom).read_text(encoding="utf-8-sig")
    return [{k: (v or "").strip().lstrip("'") for k, v in ligne.items()} for ligne in csv.DictReader(io.StringIO(texte), delimiter=";")]


def attendre(condition, delai_s=15):
    fin = time.time() + delai_s
    while time.time() < fin:
        if condition():
            return True
        time.sleep(0.2)
    return condition()


class CasFonctions(CasNavigateur):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.faux = FauxFournisseur(lenteur_s=4)
        cls.faux.demarrer()
        cls.addClassCleanup(cls.faux.arreter)
        taire_coupures(cls.faux)

    def setUp(self):
        super().setUp()
        self.faux.requetes.clear()
        self.serveur = ServeurPrevo(arguments=["--ia-url", self.faux.url])
        self.serveur.demarrer()
        self.addCleanup(self.serveur.arreter)
        self.contexte.add_init_script(NOTER_TOASTS_JS)

    def ouvrir(self, route, profil="responsable", nom="Responsable", technicien_id="", ia=True, modele="faux"):
        if ia:
            regler_ia(self.contexte, modele=modele)
        preregler_profil(self.contexte, profil, nom, technicien_id)
        self.page.goto(self.serveur.url + "/")
        attendre_pret(self.page)
        self.page.wait_for_load_state("networkidle")
        if ia:
            self.page.wait_for_function("Ia.etat() === 'ok'")
        self.page.evaluate("(route) => { location.hash = route; }", route)
        return self.page

    def octets(self, *noms):
        return {nom: (self.serveur.dossier / nom).read_bytes() for nom in noms}

    def attendre_toast(self, motif):
        return self.page.wait_for_function(
            "motif => (window.__toasts || []).find((t) => t.includes(motif)) || null", arg=motif).json_value()


class TestCheckListe(CasFonctions):

    def gamme(self):
        return lire_csv(self.serveur.dossier, "gammes.csv")[0]["id"]

    def test_proposition_rien_d_ecrit_puis_seules_les_cochees_ajoutees(self):
        gamme = self.gamme()
        page = self.ouvrir("#/preventif/gamme/" + gamme)
        page.wait_for_selector(".pv-check-liste .ia-bouton")
        avant = self.octets("gamme_operations.csv", "journal.csv")
        nombre_avant = len([o for o in lire_csv(self.serveur.dossier, "gamme_operations.csv") if o["gamme_id"] == gamme])
        page.click(".pv-check-liste .ia-bouton")
        page.wait_for_selector(".ia-encadre .pv-ia-operations input[type=checkbox]")
        self.assertIn("Proposition de l'IA", page.inner_text(".ia-encadre"))
        self.assertEqual(page.locator(".ia-encadre .pv-ia-operations input:checked").count(), 3)
        page.wait_for_load_state("networkidle")
        self.assertEqual(self.octets("gamme_operations.csv", "journal.csv"), avant)
        page.uncheck(".ia-encadre .pv-ia-operations input[data-rang='1']")
        page.click(".ia-encadre button:has-text('Ajouter les opérations cochées')")
        self.attendre_toast("2 opération(s) ajoutée(s)")
        self.assertTrue(attendre(lambda: len([o for o in lire_csv(self.serveur.dossier, "gamme_operations.csv")
                                              if o["gamme_id"] == gamme]) == nombre_avant + 2))
        ajoutees = [o["operation"] for o in lire_csv(self.serveur.dossier, "gamme_operations.csv") if o["gamme_id"] == gamme][-2:]
        self.assertEqual(ajoutees, ["Contrôler l'absence de fuite à la garniture", "Contrôler le serrage de l'accouplement"])
        self.assertTrue(attendre(lambda: any(l["action"] == "proposition IA utilisée (faux) : check-list" and l["id_ligne"] == gamme
                                             for l in lire_csv(self.serveur.dossier, "journal.csv"))))
        # Données envoyées : désignation de l'équipement et gamme, jamais de nom de personne
        envoye = json.dumps(self.faux.requetes_vers("/api/chat")[-1]["corps"], ensure_ascii=False)
        self.assertIn("Fonction : checkList", envoye)
        for nom in noms_de_la_demo():
            self.assertNotIn(nom, envoye)

    def test_echec_partiel_puis_nouvel_essai_sans_doublon(self):
        """Relecture du lot 4 : le 2e ajout échoue ; un nouvel essai n'ajoute que ce qui manque."""
        gamme = self.gamme()
        page = self.ouvrir("#/preventif/gamme/" + gamme)
        page.wait_for_selector(".pv-check-liste .ia-bouton")
        nombre_avant = len([o for o in lire_csv(self.serveur.dossier, "gamme_operations.csv") if o["gamme_id"] == gamme])
        page.click(".pv-check-liste .ia-bouton")
        page.wait_for_selector(".ia-encadre .pv-ia-operations input[type=checkbox]")
        self.autoriser_erreur("échec simulé")
        page.evaluate("""() => { const vrai = Preventif.ajouterOperation; let appels = 0;
          Preventif.ajouterOperation = (...a) => { appels += 1; if (appels === 2) return Promise.reject(new Error('échec simulé')); return vrai(...a); }; }""")
        page.click(".ia-encadre button:has-text('Ajouter les opérations cochées')")
        page.wait_for_selector(".ia-encadre .ia-erreur-action:not([hidden])")
        self.assertTrue(attendre(lambda: len([o for o in lire_csv(self.serveur.dossier, "gamme_operations.csv")
                                              if o["gamme_id"] == gamme]) == nombre_avant + 1))
        self.assertEqual(page.locator(".ia-encadre .pv-ia-operations input:checked").count(), 2)
        page.click(".ia-encadre button:has-text('Ajouter les opérations cochées')")
        self.attendre_toast("opération(s) ajoutée(s)")
        self.assertTrue(attendre(lambda: len([o for o in lire_csv(self.serveur.dossier, "gamme_operations.csv")
                                              if o["gamme_id"] == gamme]) == nombre_avant + 3))
        ajoutees = [o["operation"] for o in lire_csv(self.serveur.dossier, "gamme_operations.csv") if o["gamme_id"] == gamme][-3:]
        self.assertEqual(len(set(ajoutees)), 3, ajoutees)

    def test_ignorer_n_ecrit_rien_et_technicien_sans_bouton(self):
        gamme = self.gamme()
        page = self.ouvrir("#/preventif/gamme/" + gamme)
        page.wait_for_selector(".pv-check-liste .ia-bouton")
        avant = self.octets("gamme_operations.csv", "journal.csv")
        page.click(".pv-check-liste .ia-bouton")
        page.wait_for_selector(".ia-encadre .pv-ia-operations")
        page.click(".ia-encadre button:has-text('Ignorer')")
        page.wait_for_selector(".ia-encadre", state="detached")
        page.wait_for_load_state("networkidle")
        self.assertEqual(self.octets("gamme_operations.csv", "journal.csv"), avant)
        technicien = next(t for t in lire_csv(self.serveur.dossier, "techniciens.csv") if t["actif"] != "0")
        contexte = self.navigateur.new_context(locale="fr-FR")
        self.addCleanup(contexte.close)
        regler_ia(contexte)
        preregler_profil(contexte, "technicien", technicien["prenom"] + " " + technicien["nom"], technicien["id"])
        autre = contexte.new_page()
        self.surveiller(autre)
        autre.goto(self.serveur.url + "/#/preventif/gamme/" + gamme)
        attendre_pret(autre)
        autre.wait_for_function("Ia.etat() === 'ok'")
        autre.evaluate("App.reafficher()")
        autre.wait_for_selector(".pv-check-liste h2")
        self.assertEqual(autre.locator(".ia-bouton").count(), 0)


class TestSansResume(CasFonctions):
    """Lot 6 : le résumé de l'historique (lot 4) est retiré ; ce que ses tests prouvaient pour Ia.emplacement est
    éprouvé sur la check-list de la fiche gamme (responsable)."""

    def gamme(self):
        return lire_csv(self.serveur.dossier, "gammes.csv")[0]["id"]

    def test_fiche_equipement_sans_resume_ia_quel_que_soit_le_profil(self):
        equipement = scenarios_demo()["causes_equipement"]
        for profil, nom, technicien in (("responsable", "Responsable", ""), ("technicien", "", "TEC-0001"),
                                        ("demandeur", "Paul Martin", "")):
            with self.subTest(profil=profil):
                page = self.ouvrir("#/equipement/" + equipement, profil=profil, nom=nom, technicien_id=technicien)
                page.wait_for_selector(".parc-complements")
                page.wait_for_function("Ia.etat() === 'ok'")
                self.assertEqual(page.locator(".parc-resume-ia, .parc-complements .ia-bouton").count(), 0)
        self.assertFalse(self.page.evaluate("'resumeHistorique' in Ia.PROMPTS"))

    def test_bouton_pose_a_la_fin_du_test_d_ouverture_sans_reafficher(self):
        """Fiche ouverte AVANT la fin du test du fournisseur (relais retardé) : le bouton apparaît ensuite de
        lui-même, sans réafficher la fiche (ajout de l'orchestrateur au lot 4, reporté sur la check-list)."""
        gamme = self.gamme()
        regler_ia(self.contexte, modele="faux")
        preregler_profil(self.contexte, "responsable", "Responsable")
        # Le test d'ouverture (relais /api/ia) est RETENU jusqu'à ce que la fiche soit vérifiée, puis libéré.
        retenues = []
        self.contexte.route(self.serveur.url + "/api/ia", lambda route: retenues.append(route))
        page = self.page
        page.goto(self.serveur.url + "/#/preventif/gamme/" + gamme)
        page.wait_for_selector(".pv-check-liste h2")
        for _ in range(100):                                # laisse arriver la requête retenue (5 s au plus)
            if retenues:
                break
            page.wait_for_timeout(50)
        self.assertTrue(retenues, "le test d'ouverture du fournisseur n'est pas parti")
        self.assertEqual(page.evaluate("Ia.etat()"), "inconnu")
        self.assertEqual(page.locator(".pv-check-liste .ia-bouton:visible").count(), 0)
        page.evaluate("document.querySelector('.pv-check-liste').dataset.temoin = '1'")
        for route in retenues:
            route.continue_()
        page.wait_for_selector(".pv-check-liste .ia-bouton", state="visible")
        self.assertEqual(page.evaluate("document.querySelector('.pv-check-liste').dataset.temoin"), "1")

    def test_erreur_reseau_message_visible_quand_le_bouton_s_en_va(self):
        """Relecture du lot 4 : relais injoignable au clic → l'IA passe « injoignable », le bouton s'en va, mais le
        message d'erreur reste affiché (reporté sur la check-list de la fiche gamme)."""
        page = self.ouvrir("#/preventif/gamme/" + self.gamme())
        page.wait_for_selector(".pv-check-liste .ia-bouton")
        self.autoriser_erreur("net::ERR_FAILED")
        self.contexte.route(self.serveur.url + "/api/ia", lambda route: route.abort("failed"))
        page.click(".pv-check-liste .ia-bouton")
        page.wait_for_selector(".pv-check-liste .ia-encadre .ia-erreur", state="visible")
        self.assertEqual(page.evaluate("Ia.etat()"), "injoignable")
        self.assertEqual(page.locator(".pv-check-liste .ia-bouton").count(), 0)
        self.assertIn("ne répond pas", page.inner_text(".pv-check-liste .ia-encadre"))


class TestCommentaireRapport(CasFonctions):

    def ouvrir_rapports(self, modele="faux"):
        # Horloge du navigateur fixée à la date de référence de la démo (T194) : le serveur sert donnees/demo telle
        # quelle (dates du 2026-10-19 au plus tard) ; un autre jour, le mois proposé pourrait n'avoir aucune
        # disponibilité calculable, et le faux modèle, qui écrit toujours {disponibilite}, serait refusé (jeton inconnu).
        self.contexte.clock.set_fixed_time("2026-10-19T09:00:00")
        page = self.ouvrir("#/indicateurs?onglet=rapports", modele=modele)
        page.wait_for_selector("#rapports-commentaire")
        return page

    def test_chiffre_en_clair_refuse(self):
        page = self.ouvrir_rapports(modele="faux-chiffres")
        page.wait_for_selector(".rapports-figer .ia-bouton")
        page.click(".rapports-figer .ia-bouton")
        page.wait_for_selector(".rapports-figer .ia-encadre .ia-erreur")
        self.assertIn("chiffre", page.inner_text(".rapports-figer .ia-encadre").lower())
        self.assertEqual(page.input_value("#rapports-commentaire"), "")

    def test_jetons_remplaces_rien_de_fige_sans_clic_puis_mention_dans_le_rapport(self):
        page = self.ouvrir_rapports()
        mois = page.input_value("#rapports-mois")
        jetons = page.evaluate("(mois) => Rapport.jetonsCommentaire(Rapport.donnees(mois))", mois)
        avant = self.octets("parametres.csv", "journal.csv")
        documents_avant = sorted(p.name for p in (self.serveur.dossier / "documents").iterdir())
        page.click(".rapports-figer .ia-bouton")
        page.wait_for_selector(".rapports-figer .ia-encadre .ia-texte")
        propose = page.inner_text(".rapports-figer .ia-encadre .ia-texte")
        self.assertNotIn("{", propose)
        self.assertIn(jetons["disponibilite"].replace(" ", " ").replace(" ", " "), propose.replace(" ", " ").replace(" ", " "))
        page.click(".rapports-figer .ia-encadre button:has-text('Utiliser')")
        self.assertEqual(page.input_value("#rapports-commentaire"), propose)
        page.wait_for_load_state("networkidle")
        self.assertEqual(self.octets("parametres.csv", "journal.csv"), avant)
        self.assertEqual(sorted(p.name for p in (self.serveur.dossier / "documents").iterdir()), documents_avant)
        page.click(".rapports-figer button[type=submit]")
        self.attendre_toast("Rapport figé")
        nouveaux = [p for p in (self.serveur.dossier / "documents").iterdir() if p.name not in documents_avant]
        self.assertEqual(len(nouveaux), 1)
        document = nouveaux[0].read_text(encoding="utf-8")
        self.assertIn("<h2>Commentaire</h2>", document)
        self.assertIn("rédigé avec l'aide de l'IA", document)
        self.assertIn("La disponibilité du mois", document)
        # Les jetons valent les tuiles du document figé (référence indépendante de Rapport.jetonsCommentaire)
        tuiles = {cle: html.unescape(re.sub(r"\s|&nbsp;", " ", valeur)).strip() for cle, valeur in re.findall(
            r'<div class="tuile" data-cle="([^"]+)">\s*<div class="lib">[^<]*</div><div class="val">([^<]*)</div>', document)}
        commentaire = html.unescape(re.sub(r"\s|&nbsp;", " ", document))
        self.assertIn("s'établit à %s ;" % tuiles["disponibilite"], commentaire)
        self.assertIn("coût du mois est de %s." % tuiles["cout"], commentaire)
        self.assertTrue(attendre(lambda: any(l["action"].startswith("proposition IA utilisée (faux) : commentaire du rapport")
                                             for l in lire_csv(self.serveur.dossier, "journal.csv"))))

    def test_commentaire_fige_en_anglais_demande_en_anglais_ecran_francais(self):
        """T303 (D159, CS156) : la langue du rapport (liste « Langue du rapport ») est celle de la consigne, pas celle de l'écran."""
        page = self.ouvrir_rapports()
        page.select_option("#rapports-langue", "en")
        page.click(".rapports-figer .ia-bouton")
        page.wait_for_selector(".rapports-figer .ia-encadre .ia-texte")
        systeme = self.faux.requetes_vers("/api/chat")[-1]["corps"]["messages"][0]["content"]
        self.assertTrue(systeme.startswith("Fonction : commentaireRapport"))
        self.assertTrue(systeme.endswith("Réponds en anglais (en)."), systeme[-80:])

    def test_commentaire_ecrit_a_la_main_sans_mention(self):
        page = self.ouvrir("#/indicateurs?onglet=rapports", ia=False)
        page.wait_for_selector("#rapports-commentaire")
        self.assertEqual(page.locator(".ia-bouton").count(), 0)              # sans IA : pas de bouton
        documents_avant = sorted(p.name for p in (self.serveur.dossier / "documents").iterdir())
        page.fill("#rapports-commentaire", "Mois calme : rien à signaler.")
        page.click(".rapports-figer button[type=submit]")
        self.attendre_toast("Rapport figé")
        nouveau = next(p for p in (self.serveur.dossier / "documents").iterdir() if p.name not in documents_avant)
        document = nouveau.read_text(encoding="utf-8")
        self.assertIn("Mois calme : rien à signaler.", document)
        self.assertNotIn("aide de l'IA", document)

    def test_commentaire_propose_pour_un_autre_mois_refuse_au_moment_de_figer(self):
        """Relecture du lot 4 (D71) : proposé pour le mois A puis mois B choisi → avertissement, rien de figé."""
        page = self.ouvrir_rapports()
        options = page.eval_on_selector_all("#rapports-mois option", "o => o.map((e) => e.value)")
        self.assertGreaterEqual(len(options), 2)
        page.click(".rapports-figer .ia-bouton")
        page.wait_for_selector(".rapports-figer .ia-encadre .ia-texte")
        page.click(".rapports-figer .ia-encadre button:has-text('Utiliser')")
        documents_avant = sorted(p.name for p in (self.serveur.dossier / "documents").iterdir())
        page.select_option("#rapports-mois", options[1])
        page.wait_for_selector(".rapports-ecart-mois:not([hidden])")
        self.assertIn("ne valent pas pour", page.inner_text(".rapports-ecart-mois"))
        page.click(".rapports-figer button[type=submit]")
        page.wait_for_selector("#rapports-message .alerte.important")
        self.assertIn("Proposez-le de nouveau", page.inner_text("#rapports-message"))
        page.wait_for_load_state("networkidle")
        self.assertEqual(sorted(p.name for p in (self.serveur.dossier / "documents").iterdir()), documents_avant)
        # Retour au mois de la proposition : plus d'avertissement, le rapport se fige
        page.select_option("#rapports-mois", options[0])
        page.wait_for_selector(".rapports-ecart-mois", state="hidden")
        page.click(".rapports-figer button[type=submit]")
        self.attendre_toast("Rapport figé")

    def test_points_envoyes_a_l_ia_sans_chiffres(self):
        """Relecture du lot 4 : les points à examiner partent sans chiffre ni montant (l'IA n'en écrit aucun)."""
        page = self.ouvrir_rapports()
        page.click(".rapports-figer .ia-bouton")
        page.wait_for_selector(".rapports-figer .ia-encadre .ia-texte")
        message = self.faux.requetes_vers("/api/chat")[-1]["corps"]["messages"][-1]["content"]
        points = message.split("Points à examiner :", 1)[1]
        self.assertTrue(points.strip() and points.strip() != "(aucun)", "le mois de démo a des points à examiner")
        self.assertIsNone(re.search(r"\d", points), points)


class TestReponsesPiegees(CasFonctions):
    """Relecture du lot 4 : check-list, résumé et commentaire piégés (faux-html) affichés en texte."""

    def verifier_affiche_en_texte(self, selecteur):
        page = self.page
        page.wait_for_selector(selecteur + " .ia-encadre .ia-proposition", state="visible")
        self.assertIn("<img", page.inner_text(selecteur + " .ia-encadre"))
        self.assertEqual(page.locator(selecteur + " .ia-encadre img").count(), 0)
        page.wait_for_timeout(300)
        self.assertIsNone(page.evaluate("window.__xss === undefined ? null : window.__xss"))

    def test_check_liste_et_commentaire_html_affiches_en_texte(self):
        gamme = lire_csv(self.serveur.dossier, "gammes.csv")[0]["id"]
        page = self.ouvrir("#/preventif/gamme/" + gamme, modele="faux-html")
        page.wait_for_selector(".pv-check-liste .ia-bouton")
        page.click(".pv-check-liste .ia-bouton")
        self.verifier_affiche_en_texte(".pv-check-liste")

        page.evaluate("(route) => { location.hash = route; }", "#/indicateurs?onglet=rapports")
        page.wait_for_selector(".rapports-figer .ia-bouton")
        page.click(".rapports-figer .ia-bouton")
        self.verifier_affiche_en_texte(".rapports-figer")
        page.click(".rapports-figer .ia-encadre button:has-text('Utiliser')")
        self.assertTrue(page.input_value("#rapports-commentaire").startswith("<img"))


if __name__ == "__main__":
    unittest.main()
