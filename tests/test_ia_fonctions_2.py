"""Fonctions IA de la gamme, de la fiche équipement et du rapport (lot 4, ARCHITECTURE.md §17.5,
points 4 à 6 ; CDC D65, D69, D71 ; CS66, CS68). Faux fournisseur seulement, mode serveur.

    - check-list (fiche gamme, responsable) : opérations cochables ; RIEN n'est écrit avant « Ajouter
      les opérations cochées », puis seules les cochées s'ajoutent (journal habituel + trace IA) ;
      Ignorer : rien ; technicien : pas de bouton ;
    - résumé de l'historique (fiche équipement, technicien et responsable) : texte proposé, aucun
      fichier modifié, 20 OT au plus envoyés, aucun nom de technicien ni de demandeur ; demandeur :
      pas de carte ;
    - commentaire du rapport (onglet Rapports, responsable) : un chiffre écrit en clair par l'IA fait
      refuser la proposition ; sinon les jetons sont remplacés par les chiffres du rapport ; rien n'est
      figé sans « Figer le rapport » ; le rapport figé porte le commentaire et la mention « rédigé avec
      l'aide de l'IA » ; un commentaire écrit à la main n'a pas la mention ;
    - sans IA : aucun de ces boutons.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_ia_fonctions_2.py" -v
"""
import csv
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
        self.serveur = ServeurPrevo()
        self.serveur.demarrer()
        self.addCleanup(self.serveur.arreter)
        self.contexte.add_init_script(NOTER_TOASTS_JS)

    def ouvrir(self, route, profil="responsable", nom="Responsable", technicien_id="", ia=True, modele="faux"):
        if ia:
            regler_ia(self.contexte, url=self.faux.url, modele=modele)
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
        regler_ia(contexte, url=self.faux.url)
        preregler_profil(contexte, "technicien", technicien["prenom"] + " " + technicien["nom"], technicien["id"])
        autre = contexte.new_page()
        self.surveiller(autre)
        autre.goto(self.serveur.url + "/#/preventif/gamme/" + gamme)
        attendre_pret(autre)
        autre.wait_for_function("Ia.etat() === 'ok'")
        autre.evaluate("App.reafficher()")
        autre.wait_for_selector(".pv-check-liste h2")
        self.assertEqual(autre.locator(".ia-bouton").count(), 0)


class TestResume(CasFonctions):

    def test_resume_de_l_historique_sans_ecriture(self):
        equipement = scenarios_demo()["causes_equipement"]
        page = self.ouvrir("#/equipement/" + equipement)
        page.wait_for_selector(".parc-resume-ia .ia-bouton")
        avant = self.octets("ordres_travail.csv", "journal.csv", "equipements.csv")
        page.click(".parc-resume-ia .ia-bouton")
        page.wait_for_selector(".parc-resume-ia .ia-encadre .ia-texte")
        self.assertIn("garniture", page.inner_text(".parc-resume-ia .ia-encadre"))
        self.assertIn("Proposition de l'IA", page.inner_text(".parc-resume-ia .ia-encadre"))
        page.wait_for_load_state("networkidle")
        self.assertEqual(self.octets("ordres_travail.csv", "journal.csv", "equipements.csv"), avant)
        message = self.faux.requetes_vers("/api/chat")[-1]["corps"]["messages"][-1]["content"]
        self.assertLessEqual(message.count("\n- "), 20)
        for nom in noms_de_la_demo():
            self.assertNotIn(nom, message)

    def test_demandeur_sans_carte_et_sans_ia_sans_carte(self):
        equipement = scenarios_demo()["causes_equipement"]
        page = self.ouvrir("#/equipement/" + equipement, profil="demandeur", nom="Paul Martin")
        page.wait_for_selector(".parc-complements")
        self.assertEqual(page.locator(".parc-resume-ia").count(), 0)
        contexte = self.navigateur.new_context(locale="fr-FR")
        self.addCleanup(contexte.close)
        preregler_profil(contexte, "responsable", "Responsable")
        autre = contexte.new_page()
        self.surveiller(autre)
        autre.goto(self.serveur.url + "/#/equipement/" + equipement)
        attendre_pret(autre)
        autre.wait_for_selector(".parc-complements")
        self.assertEqual(autre.locator(".parc-resume-ia, .ia-bouton").count(), 0)


class TestCommentaireRapport(CasFonctions):

    def ouvrir_rapports(self, modele="faux"):
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
        self.assertTrue(attendre(lambda: any(l["action"].startswith("proposition IA utilisée (faux) : commentaire du rapport")
                                             for l in lire_csv(self.serveur.dossier, "journal.csv"))))

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


if __name__ == "__main__":
    unittest.main()
