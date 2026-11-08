"""T329 (décisions de Nicolas du 07/11) — saisie gardée quand la session se perd, et brouillons gardés sur l'appareil.

Ce qui est vérifié, sur un serveur réel en mode comptes (copie de la démo, trois comptes, installation en français) :
    session perdue  : une fenêtre de saisie ouverte (Équipe › Ajouter une habilitation) ne bloque plus l'écran de
                      connexion ; le message dit quoi faire ; le même compte retrouve la fenêtre et sa saisie, puis
                      l'enregistre une seule fois ; un formulaire de la page (compte rendu d'un OT, au téléphone) reste
                      tel quel ; compte en anglais sur une installation française : aucun rechargement (avant T329, la
                      page se rechargeait dans la langue du poste, saisie perdue, sans message), l'écran de connexion
                      et son message en anglais ; un autre compte qui se connecte ne voit pas la saisie, et rien n'est
                      enregistré sous son nom ;
    brouillons      : déclaration de panne et compte rendu gardés sur l'appareil (localStorage) : repris après un
                      rechargement (onglet déchargé par le téléphone en veille), avec le bandeau « Brouillon repris » ;
                      aucune donnée nouvelle sur le serveur tant que rien n'est envoyé ; effacés à l'enregistrement ;
                      jamais montrés à un autre compte (gardés pour le leur) ; effacés au bout de 7 jours, tous auteurs ;
                      compte rendu enregistré ailleurs entre-temps : avertissement, et l'onglet Compte rendu s'ouvre.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_saisie_gardee.py" -v
"""
import csv
import io
import re
import unittest
from pathlib import Path

from atelier import motif_refus_du_demandeur
from commun import MOTS_DE_PASSE_DE_TEST, CasNavigateur, ServeurPrevo, attendre_pret
from test_acces_ecrans import requete
from test_langue_installation import poser_langue, texte_du_dictionnaire

ERREUR_401 = re.compile(r"status of 401")
INTITULE = "Habilitation T329 gardée"
TEXTE_CR = "Roulement changé, jeu contrôlé (T329)."
SYMPTOME = "Fuite d'huile T329"
PRECISIONS = "Depuis ce matin, sous le carter."
OT = "OT-2026-0212"                                     # En cours dans la démo : modifiable par un technicien
ONGLET_CR = ".ot-onglets [role=tab][data-onglet=compte-rendu]"
CHAMP_CR = "#form-compte-rendu textarea[name=compte_rendu]"
BROUILLONS_JS = """() => Object.fromEntries(Object.keys(localStorage).filter((cle) => cle.startsWith('prevo.brouillon|'))
  .map((cle) => [cle, JSON.parse(localStorage.getItem(cle))]))"""
CLE_DEMANDE_LEA = "prevo.brouillon|serveur|compte:lea.martin|demande"
CLE_CR_JULIEN = "prevo.brouillon|serveur|compte:julien.moreau|compte-rendu|" + OT
ATTENTE_ECRITURE_MS = 900                               # brouillon écrit 400 ms après la dernière frappe


def lignes_csv(dossier, nom):
    texte = (Path(dossier) / nom).read_bytes().decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte, newline=""), delimiter=";"))


class CasSaisieGardee(CasNavigateur):
    """Un serveur neuf par test (les sessions d'un compte y sont fermées) ; chargements de la page comptés."""

    def setUp(self):
        super().setUp()
        self.chargements = 0
        self.page.on("load", lambda _page: setattr(self, "chargements", self.chargements + 1))
        self.autoriser_erreur(ERREUR_401)
        self.autoriser_erreur(motif_refus_du_demandeur())                # tables refusées à Léa (demandeur)

    def serveur(self):
        lance = ServeurPrevo(comptes=True)
        lance.demarrer()
        self.addCleanup(lance.arreter)
        poser_langue(lance.dossier, "fr")
        return lance

    def telephone(self):
        self.page.set_viewport_size({"width": 375, "height": 740})

    def attendre_connexion(self):
        self.page.wait_for_function("document.documentElement.dataset.etat === 'connexion'")
        self.page.wait_for_selector("#connexion-identifiant", state="visible")

    def connecter(self, identifiant, navigation=False):
        self.page.fill("#connexion-identifiant", identifiant)
        self.page.fill("#connexion-mot-de-passe", MOTS_DE_PASSE_DE_TEST[identifiant])
        if navigation:
            with self.page.expect_navigation():
                self.page.click("#connexion-valider")
        else:
            self.page.click("#connexion-valider")

    def ouvrir(self, lance, route, identifiant, navigation=False):
        self.page.goto(lance.url + "/" + route)
        self.attendre_connexion()
        self.connecter(identifiant, navigation)
        attendre_pret(self.page)

    def fermer_les_sessions(self, lance, identifiant):
        """« Déconnecter partout » du responsable (comme une session expirée : la suivante requête reçoit 401)."""
        statut, _, octets = requete(lance.url, "POST", "/api/acces/deconnecter-partout", {"identifiant": identifiant},
                                    lance.session("responsable"))
        self.assertEqual(statut, 200, octets)

    def lecture_refusee(self):
        """Une lecture du serveur (comme le rafraîchissement des 20 secondes) : 401, la session est absente."""
        self.page.evaluate("App.adaptateur.listerVersions().catch(() => null)")

    def motif(self):
        return self.page.inner_text("#connexion-motif").strip()

    def brouillons(self):
        return self.page.evaluate(BROUILLONS_JS)

    def ouvrir_compte_rendu(self):
        self.page.click(ONGLET_CR)
        self.page.wait_for_selector(CHAMP_CR)

    def attendre_dans_le_fichier(self, lance, nom, colonne, valeur, nombre=1):
        for _ in range(100):
            if sum(1 for ligne in lignes_csv(lance.dossier, nom) if ligne.get(colonne) == valeur) >= nombre:
                break
            self.page.wait_for_timeout(100)
        self.assertEqual(sum(1 for ligne in lignes_csv(lance.dossier, nom) if ligne.get(colonne) == valeur), nombre)


class TestSessionPerdue(CasSaisieGardee):

    def ouvrir_ajout_habilitation(self, lance):
        self.ouvrir(lance, "#/equipe/TEC-0002", "nicolas.briand")
        self.page.click("#equipe-ajouter-habilitation")
        self.page.fill("dialog[open] input[name=intitule]", INTITULE)

    def test_fenetre_de_saisie_gardee_pour_le_meme_compte_puis_enregistree_une_fois(self):
        lance = self.serveur()
        self.ouvrir_ajout_habilitation(lance)
        self.fermer_les_sessions(lance, "nicolas.briand")
        self.page.click("dialog[open] button:has-text('Ajouter')")                # refusé : 401
        self.attendre_connexion()
        # L'écran de connexion est utilisable : la fenêtre est mise de côté (gardée dans la page, fermée).
        self.assertEqual(self.page.locator("dialog[open]").count(), 0)
        self.assertEqual(self.page.locator("dialog").count(), 1)
        self.assertEqual(self.motif(), texte_du_dictionnaire("fr", "socle.session_perdue.reconnectez_vous_meme_compte"))
        self.assertFalse(INTITULE in "".join(l["intitule"] for l in lignes_csv(lance.dossier, "habilitations.csv")))
        self.connecter("nicolas.briand")
        self.page.wait_for_selector("dialog[open]")
        self.assertEqual(self.page.input_value("dialog[open] input[name=intitule]"), INTITULE)
        self.assertEqual(self.page.evaluate("document.documentElement.dataset.etat"), "pret")
        self.assertIn(texte_du_dictionnaire("fr", "socle.session_perdue.reconnecte_saisie_gardee"),
                      self.page.inner_text("#toast"))
        self.page.click("dialog[open] button:has-text('Ajouter')")
        self.page.wait_for_selector("dialog", state="detached")
        self.attendre_dans_le_fichier(lance, "habilitations.csv", "intitule", INTITULE)
        self.assertEqual(self.chargements, 1)

    def test_autre_compte_ne_voit_pas_la_saisie_et_rien_n_est_enregistre(self):
        lance = self.serveur()
        self.ouvrir_ajout_habilitation(lance)
        self.fermer_les_sessions(lance, "nicolas.briand")
        self.page.click("dialog[open] button:has-text('Ajouter')")
        self.attendre_connexion()
        self.connecter("julien.moreau")                                           # poste partagé : une autre personne
        attendre_pret(self.page)
        self.assertEqual(self.page.evaluate("App.session.identifiant"), "julien.moreau")
        self.assertEqual(self.page.locator("dialog").count(), 0)
        self.assertNotIn(INTITULE, self.page.content())
        self.page.wait_for_timeout(500)
        self.assertFalse(INTITULE in "".join(l["intitule"] for l in lignes_csv(lance.dossier, "habilitations.csv")))

    def test_compte_rendu_de_la_page_garde_au_telephone_pour_le_meme_compte(self):
        lance = self.serveur()
        self.telephone()
        self.ouvrir(lance, "#/ot/" + OT, "julien.moreau")
        self.ouvrir_compte_rendu()
        self.page.fill(CHAMP_CR, TEXTE_CR)
        self.fermer_les_sessions(lance, "julien.moreau")
        self.lecture_refusee()                                                   # le rafraîchissement suivant
        self.attendre_connexion()
        self.assertEqual(self.motif(), texte_du_dictionnaire("fr", "socle.session_perdue.reconnectez_vous_meme_compte"))
        self.connecter("julien.moreau")
        attendre_pret(self.page)
        self.assertEqual(self.page.input_value(CHAMP_CR), TEXTE_CR)
        self.page.click("#form-compte-rendu button[type=submit]")
        self.attendre_dans_le_fichier(lance, "ordres_travail.csv", "compte_rendu", TEXTE_CR)
        self.page.wait_for_timeout(ATTENTE_ECRITURE_MS)
        self.assertEqual(self.brouillons(), {})                                 # enregistré : plus de brouillon
        self.assertEqual(self.chargements, 1)

    def test_langue_du_compte_sans_rechargement_ecran_de_connexion_dans_sa_langue(self):
        lance = self.serveur()
        statut, _, octets = requete(lance.url, "POST", "/api/mot-de-passe", {"langue": "en"}, lance.session("technicien"))
        self.assertEqual(statut, 200, octets)
        self.telephone()
        self.ouvrir(lance, "#/ot/" + OT, "julien.moreau", navigation=True)      # rechargée dans la langue du compte
        self.assertEqual((self.page.evaluate("I18n.langue"), self.chargements), ("en", 2))
        self.ouvrir_compte_rendu()
        self.page.fill(CHAMP_CR, TEXTE_CR)
        self.fermer_les_sessions(lance, "julien.moreau")
        self.lecture_refusee()
        self.attendre_connexion()
        self.page.wait_for_timeout(1500)                                         # aucun rechargement ne vient
        self.assertEqual(self.chargements, 2)
        self.assertEqual(self.page.evaluate("document.documentElement.lang"), "en")
        self.assertEqual(self.motif(), texte_du_dictionnaire("en", "socle.session_perdue.reconnectez_vous_meme_compte"))
        self.connecter("julien.moreau")
        attendre_pret(self.page)
        self.assertEqual(self.page.input_value(CHAMP_CR), TEXTE_CR)
        self.assertEqual((self.page.evaluate("I18n.langue"), self.chargements), ("en", 2))


class TestBrouillons(CasSaisieGardee):

    def remplir_declaration(self):
        self.page.fill("input[name=symptome]", SYMPTOME)
        self.page.click("label.tuile:has(input[name=impact][value='arrêt'])")
        self.page.fill("textarea[name=description]", PRECISIONS)
        self.page.wait_for_timeout(ATTENTE_ECRITURE_MS)

    def declaration_a_l_ecran(self):
        return self.page.evaluate("""() => ({ symptome: document.querySelector('input[name=symptome]').value,
          impact: (document.querySelector('input[name=impact]:checked') || {}).value || '',
          description: document.querySelector('textarea[name=description]').value,
          equipement: document.querySelector('input[name=equipement_id]').value,
          repris: Boolean(document.querySelector('.di-brouillon .brouillon-repris')) })""")

    def test_declaration_de_panne_gardee_sur_l_appareil_puis_effacee_a_l_envoi(self):
        lance = self.serveur()
        self.telephone()
        self.ouvrir(lance, "#/di/nouvelle?equipement=EQ-0005", "lea.martin")
        ecritures = []
        self.page.on("request", lambda r: ecritures.append(r.method + " " + r.url) if r.method != "GET" else None)
        self.remplir_declaration()
        brouillons = self.brouillons()
        self.assertEqual(list(brouillons), [CLE_DEMANDE_LEA])
        self.assertEqual(brouillons[CLE_DEMANDE_LEA]["valeurs"], {"equipement_id": "EQ-0005", "symptome": SYMPTOME,
                                                                  "impact": "arrêt", "description": PRECISIONS})
        self.assertEqual(ecritures, [])                                       # rien n'est parti au serveur
        # Onglet déchargé par le téléphone en veille : au retour, la page se recharge.
        self.page.reload()
        attendre_pret(self.page)
        self.assertEqual(self.declaration_a_l_ecran(), {"symptome": SYMPTOME, "impact": "arrêt",
                                                        "description": PRECISIONS, "equipement": "EQ-0005",
                                                        "repris": True})
        fichiers = [p for p in Path(lance.dossier).rglob("*") if p.is_file()]
        self.assertFalse([p.name for p in fichiers if SYMPTOME.encode("utf-8") in p.read_bytes()])
        self.page.click(".di-envoyer")
        self.page.wait_for_selector(".di-confirmation")
        self.attendre_dans_le_fichier(lance, "demandes.csv", "symptome", SYMPTOME)
        self.page.wait_for_timeout(ATTENTE_ECRITURE_MS)
        self.assertEqual(self.brouillons(), {})                                 # envoyée : plus de brouillon

    def test_brouillon_jamais_montre_a_un_autre_compte_et_garde_pour_le_sien(self):
        lance = self.serveur()
        self.telephone()
        self.ouvrir(lance, "#/di/nouvelle?equipement=EQ-0005", "lea.martin")
        self.remplir_declaration()
        self.page.evaluate("() => { App.deconnecter(); }")
        self.attendre_connexion()
        self.connecter("julien.moreau")
        attendre_pret(self.page)
        self.assertEqual(self.page.evaluate("location.hash"), "#/di/nouvelle?equipement=EQ-0005")
        a_l_ecran = self.declaration_a_l_ecran()
        self.assertEqual((a_l_ecran["symptome"], a_l_ecran["description"], a_l_ecran["repris"]), ("", "", False))
        self.assertNotIn(SYMPTOME, self.page.content())
        self.assertIn(CLE_DEMANDE_LEA, self.brouillons())                     # gardé pour Léa
        self.page.evaluate("() => { App.deconnecter(); }")
        self.attendre_connexion()
        self.connecter("lea.martin")
        attendre_pret(self.page)
        self.assertEqual(self.declaration_a_l_ecran()["symptome"], SYMPTOME)

    def test_brouillons_de_plus_de_7_jours_effaces_tous_auteurs(self):
        lance = self.serveur()
        self.ouvrir(lance, "#/di/nouvelle?equipement=EQ-0005", "lea.martin")
        self.page.evaluate("""([lea, julien]) => {
          const jour = 24 * 3600 * 1000;
          const poser = (cle, age, symptome) => localStorage.setItem(cle, JSON.stringify({ le: Date.now() - age,
            valeurs: { equipement_id: 'EQ-0005', symptome, impact: '', description: '', compte_rendu: symptome },
            depart: {}, ot: '' }));
          poser(lea, 8 * jour, 'Vieux brouillon');
          poser(julien, 8 * jour, 'Vieux compte rendu');
          poser(julien + '-recent', 6 * jour, 'Récent');
        }""", [CLE_DEMANDE_LEA, CLE_CR_JULIEN])
        self.page.reload()
        attendre_pret(self.page)
        self.assertEqual(self.declaration_a_l_ecran()["symptome"], "")
        self.page.wait_for_timeout(300)
        self.assertEqual(list(self.brouillons()), [CLE_CR_JULIEN + "-recent"])

    def test_compte_rendu_repris_avec_avertissement_puis_efface_a_l_enregistrement(self):
        lance = self.serveur()
        self.telephone()
        self.ouvrir(lance, "#/ot/" + OT, "julien.moreau")
        self.ouvrir_compte_rendu()
        self.page.fill(CHAMP_CR, TEXTE_CR)
        self.page.wait_for_timeout(ATTENTE_ECRITURE_MS)
        self.assertEqual(list(self.brouillons()), [CLE_CR_JULIEN])
        # Un autre poste enregistre un compte rendu entre-temps.
        self.page.evaluate("""async (id) => { await Donnees.modifier('ordres_travail', (lignes) => {
          lignes.find((l) => l.id === id).compte_rendu = 'Texte enregistré ailleurs'; return true; }); }""", OT)
        self.page.reload()
        attendre_pret(self.page)
        self.page.wait_for_selector(CHAMP_CR)
        self.assertEqual(self.page.get_attribute(ONGLET_CR, "aria-selected"), "true")   # ouvert d'emblée
        self.assertEqual(self.page.input_value(CHAMP_CR), TEXTE_CR)
        bandeau = self.page.inner_text(".brouillon-repris")
        self.assertIn(texte_du_dictionnaire("fr", "ordres.brouillon.modifie_ailleurs"), bandeau)
        self.page.click("#form-compte-rendu button[type=submit]")
        self.attendre_dans_le_fichier(lance, "ordres_travail.csv", "compte_rendu", TEXTE_CR)
        self.page.wait_for_timeout(ATTENTE_ECRITURE_MS)
        self.assertEqual(self.brouillons(), {})

    def test_abandonner_le_brouillon_remet_la_saisie_enregistree(self):
        lance = self.serveur()
        self.ouvrir(lance, "#/ot/" + OT, "julien.moreau")
        self.ouvrir_compte_rendu()
        self.page.fill(CHAMP_CR, TEXTE_CR)
        self.page.wait_for_timeout(ATTENTE_ECRITURE_MS)
        self.page.reload()
        attendre_pret(self.page)
        self.page.wait_for_selector(".brouillon-repris")
        self.page.click(".brouillon-repris .brouillon-abandonner")
        self.assertEqual(self.page.input_value(CHAMP_CR), "")
        self.page.wait_for_timeout(ATTENTE_ECRITURE_MS)
        self.assertEqual(self.brouillons(), {})
        self.assertEqual(self.page.locator(".brouillon-repris").count(), 0)


if __name__ == "__main__":
    unittest.main()
