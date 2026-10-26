"""Fonctions IA de la demande et de l'ordre de travail (lot 4, ARCHITECTURE.md §17.5 points 1 à 3 ;
brief §10 ; tâche T69).

Toujours avec le faux fournisseur (tests/faux_fournisseur_ia.py), jamais un vrai modèle. Familles :
    - sans IA (inactive, ou active mais fournisseur injoignable) : aucun bouton IA dans « Signaler »
      ni dans le compte rendu, aucune requête vers le faux fournisseur (CS65) — démo et serveur ;
    - « Signaler » (#/di/nouvelle) : « Proposer avec l'IA » → encadré « Proposition de l'IA — … » ;
      Utiliser remplit le symptôme et coche l'impact, Modifier remplit et place le curseur, Ignorer
      ne touche à rien, un impact « sécurité » déjà choisi n'est jamais baissé ; rien n'est écrit
      avant « Envoyer » ; après l'envoi, la DI porte la proposition et le journal la trace ;
    - compte rendu de l'OT : « Rédiger le compte rendu » (Utiliser remplace le champ, « Annuler la
      proposition » rend les notes), « Proposer les codes » (les trois listes ; scénario du brief :
      le code inventé par « faux-invente » n'est pas mis dans la liste, il est annoncé), réponse
      illisible, délai dépassé, « Annuler » pendant la progression ; rien d'enregistré ni de statut
      changé sans « Enregistrer le compte rendu » ; après l'enregistrement, le journal trace chaque
      champ venu de l'IA (une seule fois) ; aucun bouton sur un OT verrouillé ni pour le demandeur ;
    - mode serveur : mêmes fonctions par le relais /api/ia (CSV comparés à l'octet), et téléphone
      375 px : boutons et encadré sans défilement horizontal, zones ≥ 48 px, proposition par le relais ;
      le fournisseur est réglé sur le PC serveur (--ia-url, audit M1, §22.12), le poste ne règle que
      l'activation, le modèle et le délai.
Données envoyées au faux fournisseur : jamais un nom de technicien ni de demandeur du jeu de démo.
Aucun identifiant du jeu de démo écrit en dur : rôles de scenarios_demo() et fichiers de la démo.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_ia_fonctions.py" -v
"""
import csv
import json
import re
import time
import unittest

from commun import (DOSSIER_DEMO, CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil,
                    scenarios_demo, url_fichier)
from faux_fournisseur_ia import REPONSES, FauxFournisseur
from test_dictee import NOTER_TOASTS_JS
from test_ia_regles import FICHIERS_JS, contenu_envoye, noms_de_la_demo, regler_ia, taire_coupures

SCENARIOS = scenarios_demo()
CODE_INVENTE = "C42"           # cause inventée par le modèle « faux-invente » (faux_fournisseur_ia.py)
REFUS_CONNEXION = "net::ERR_CONNECTION_REFUSED"
ERREUR_502 = re.compile(r"Failed to load resource: the server responded with a status of 502")
TABLES_SURVEILLEES = ("demandes", "ordres_travail", "journal")
LIBELLE_DI = "Proposer avec l'IA"
LIBELLE_CR = "Rédiger le compte rendu"
LIBELLE_CODES = "Proposer les codes"
CHAMP_CR = "#form-compte-rendu [name=compte_rendu]"
MENTION = "Proposition de l'IA — Ollama, faux"
NOTES = "soudure ratée, résistance changée, essai bon sur dix colis"

# Valeurs du formulaire « Signaler » et du compte rendu, et nom du champ qui a le focus.
VALEURS_DI_JS = """() => { const f = document.querySelector('.di-formulaire');
  const coche = f.querySelector('input[name=impact]:checked');
  return { symptome: f.querySelector('input[name=symptome]').value, impact: coche ? coche.value : '',
           description: f.querySelector('textarea[name=description]').value,
           focus: (document.activeElement && document.activeElement.name) || '' }; }"""
VALEURS_CR_JS = """() => { const f = document.querySelector('#form-compte-rendu');
  const v = (nom) => f.querySelector('[name=' + nom + ']').value;
  return { compte_rendu: v('compte_rendu'), symptome_code: v('symptome_code'), cause_code: v('cause_code'),
           remede_code: v('remede_code'), focus: (document.activeElement && document.activeElement.name) || '' }; }"""


def lire_csv(dossier, nom):
    with open(dossier / (nom + ".csv"), encoding="utf-8-sig", newline="") as fichier:
        return list(csv.DictReader(fichier, delimiter=";"))


def ligne_demo(nom, identifiant):
    """Ligne d'un fichier du jeu de démo (donnees/demo), par son identifiant."""
    return next(ligne for ligne in lire_csv(DOSSIER_DEMO, nom) if ligne["id"] == identifiant)


def premiers_codes():
    """Codes que choisit le faux fournisseur : le premier de chaque liste fermée du schéma, donc le
    premier de chaque famille dans codes_defaillance (ordre du fichier)."""
    premiers = {}
    for ligne in lire_csv(DOSSIER_DEMO, "codes_defaillance"):
        premiers.setdefault(ligne["famille"], ligne["code"])
    return {"symptome_code": premiers["symptôme"], "cause_code": premiers["cause"], "remede_code": premiers["remède"]}


def traces(journal, table, identifiant):
    """Champs tracés « proposition IA utilisée (faux) : <champ> » pour une ligne, dans l'ordre du journal."""
    motif = re.compile(r";%s;%s;proposition IA utilisée \(faux\) : (\w+)" % (re.escape(table), re.escape(identifiant)))
    return motif.findall(journal)


class CasIaFonctions(CasNavigateur):
    """Faux fournisseur partagé par la classe (requêtes vidées à chaque test). Ouverture en démo
    (index.html en file://) ou sur un serveur Prévo (copie neuve du jeu de démo par test)."""

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
        self.serveur = None
        self.preparer_page()

    def preparer_page(self):
        self.adresses = []
        self.page.on("request", lambda requete: self.adresses.append(requete.url))
        self.contexte.add_init_script(NOTER_TOASTS_JS)

    def passer_au_telephone(self):
        """Remplace le contexte du test par un téléphone (375 px, tactile) ; à appeler avant regler_ia."""
        self.contexte.close()
        self.contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 375, "height": 812},
                                                    is_mobile=True, has_touch=True)
        self.contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        self.page = self.contexte.new_page()
        self.surveiller(self.page)
        self.preparer_page()

    # -- ouverture et navigation --------------------------------------------------------------

    def ouvrir(self, route, selecteur, profil="responsable", nom="Responsable", technicien_id="",
               serveur=None, attendre_ia=True):
        """Ouvre Prévo avec un profil puis la route. Serveur : la route est ouverte directement, AVANT
        la fin du test du fournisseur (les boutons IA doivent venir d'eux-mêmes). Démo : la route est
        ouverte une fois l'état de l'IA connu."""
        self.serveur = serveur
        preregler_profil(self.contexte, profil, nom, technicien_id=technicien_id)
        page = self.page
        if serveur:
            page.goto(serveur.url + "/" + route)
            attendre_pret(page)
            page.wait_for_selector(selecteur)
            page.wait_for_load_state("networkidle")   # écritures du démarrage finies avant d'agir
        else:
            page.goto(url_fichier("index.html"))
            page.click("#btn-demo")
            attendre_pret(page)
        if attendre_ia:
            page.wait_for_function("Ia.etat() !== 'inconnu'")
        if not serveur:
            self.aller(route, selecteur)
        return page

    def aller(self, route, selecteur):
        self.page.evaluate("(route) => { location.hash = route; }", route)
        self.page.wait_for_selector(selecteur)

    def ouvrir_signaler(self, **options):
        equipement = SCENARIOS["causes_equipement"]
        return self.ouvrir("#/di/nouvelle?equipement=" + equipement, ".di-formulaire", **options)

    def ouvrir_compte_rendu(self, ot_id, **options):
        page = self.ouvrir("#/ot/" + ot_id, ".ot-fiche", **options)
        self.onglet_compte_rendu(ot_id)
        return page

    def onglet_compte_rendu(self, ot_id):
        self.page.wait_for_function(
            "(id) => { const n = document.querySelector('.ot-fiche .ot-numero'); return n && n.textContent === id; }", arg=ot_id)
        self.page.click(".onglet[data-onglet='compte-rendu']")
        self.page.wait_for_selector("#form-compte-rendu")

    # -- fichiers, encadré, données envoyées --------------------------------------------------

    def instantane(self):
        """Serveur : octets de demandes.csv, ordres_travail.csv et journal.csv. Démo : les 24 fichiers en mémoire."""
        if self.serveur:
            return {nom: (self.serveur.dossier / (nom + ".csv")).read_bytes() for nom in TABLES_SURVEILLEES}
        return self.page.evaluate(FICHIERS_JS)

    def journal(self):
        if self.serveur:
            return (self.serveur.dossier / "journal.csv").read_text(encoding="utf-8-sig")
        return self.page.evaluate(FICHIERS_JS)["journal"]

    def cliquer_ia(self, libelle):
        self.page.click('.ia-bouton:has-text("%s")' % libelle)

    def attendre_proposition(self):
        self.page.wait_for_selector(".ia-encadre .ia-proposition", state="visible")
        return self.page.inner_text(".ia-encadre")

    def choisir(self, choix):
        self.page.click(".ia-encadre .ia-actions button:has-text('%s')" % choix)
        self.page.wait_for_selector(".ia-encadre", state="detached")

    def proposer_et_choisir(self, libelle, choix):
        self.cliquer_ia(libelle)
        texte = self.attendre_proposition()
        self.assertIn(MENTION, texte)
        self.choisir(choix)
        return texte

    def attendre_toast(self, motif):
        return self.page.wait_for_function(
            "motif => (window.__toasts || []).find((t) => t.includes(motif)) || null", arg=motif).json_value()

    def demandes_recues(self, fonction):
        return [r for r in self.faux.requetes if r["corps"] and contenu_envoye(r["corps"]).startswith("Fonction : " + fonction)]

    def verifier_donnees_envoyees(self, fonction, attendus, rang=-1):
        """Demandes `fonction` reçues : aucune ne contient un nom de la démo ; celle de rang `rang`
        (la dernière par défaut) contient `attendus`."""
        recues = self.demandes_recues(fonction)
        self.assertTrue(recues, "aucune demande « %s » reçue par le faux fournisseur" % fonction)
        noms = noms_de_la_demo()
        for recue in recues:
            envoye = json.dumps(recue["corps"], ensure_ascii=False)
            for nom in noms:
                self.assertNotIn(nom, envoye)
        texte = contenu_envoye(recues[rang]["corps"])
        for attendu in attendus:
            self.assertIn(attendu, texte)

    def verifier_par_le_relais(self):
        """Mode serveur : tout passe par /api/ia, rien ne part du navigateur vers le fournisseur."""
        self.assertTrue([a for a in self.adresses if a == self.serveur.url + "/api/ia"])
        self.assertFalse([a for a in self.adresses if a.startswith(self.faux.url)])

    def aucun_bouton_ia(self):
        self.assertEqual(self.page.locator(".ia-bouton, .ia-encadre").count(), 0)


# ---------------------------------------------------------------------------
# Sans IA : Prévo identique, aucun appel (CS65)
# ---------------------------------------------------------------------------

class TestSansIa(CasIaFonctions):

    def verifier_ecrans_sans_bouton(self):
        """« Signaler » (déjà affiché) puis le compte rendu d'un OT en cours : aucun bouton IA."""
        page = self.page
        page.wait_for_timeout(300)
        self.aucun_bouton_ia()
        self.assertEqual(page.locator(".di-ia:visible").count(), 0)
        ot_id = SCENARIOS["ot_statut_en_cours"]
        self.aller("#/ot/" + ot_id, ".ot-fiche")
        self.onglet_compte_rendu(ot_id)
        page.wait_for_timeout(300)
        self.aucun_bouton_ia()
        self.assertEqual(page.locator("#form-compte-rendu .ot-ia:visible").count(), 0)
        self.assertTrue(page.is_enabled(CHAMP_CR), "le compte rendu reste saisissable sans IA")

    def test_ia_inactive_demo_aucun_bouton_aucune_requete(self):
        regler_ia(self.contexte, actif=False, url=self.faux.url)
        page = self.ouvrir_signaler(attendre_ia=False)
        time.sleep(1)
        self.assertEqual(page.evaluate("[Ia.active(), Ia.etat()]"), [False, "inconnu"])
        self.verifier_ecrans_sans_bouton()
        self.assertEqual(self.faux.requetes, [])
        self.assertFalse([a for a in self.adresses if a.startswith(self.faux.url) or a.endswith("/api/ia")])

    def test_fournisseur_injoignable_demo_aucun_bouton(self):
        self.autoriser_erreur(REFUS_CONNEXION)       # le seul test d'ouverture échoue (attendu)
        with FauxFournisseur() as eteint:
            adresse = eteint.url
        regler_ia(self.contexte, url=adresse)
        page = self.ouvrir_signaler()
        self.assertEqual(page.evaluate("Ia.etat()"), "injoignable")
        self.verifier_ecrans_sans_bouton()
        self.assertEqual(self.faux.requetes, [])

    def test_serveur_ia_inactive_puis_fournisseur_injoignable(self):
        # Fournisseur réglé sur le PC serveur (--ia-url, audit M1) : ici un fournisseur éteint
        with FauxFournisseur() as eteint:
            adresse = eteint.url
        with ServeurPrevo(arguments=["--ia-url", adresse]) as serveur:
            regler_ia(self.contexte, actif=False)
            page = self.ouvrir_signaler(serveur=serveur, attendre_ia=False)
            time.sleep(1)
            self.verifier_ecrans_sans_bouton()
            self.assertEqual(self.faux.requetes, [])
            self.assertFalse([a for a in self.adresses if "/api/ia" in a], "ni relais, ni lecture des réglages du serveur")

            # IA activée sur le poste, fournisseur du PC serveur éteint : le relais répond 502 au test d'ouverture
            self.autoriser_erreur(ERREUR_502)
            page.evaluate("Ia.enregistrerReglages({ actif: true })")
            page.evaluate("(route) => { location.hash = route; }", "#/di/nouvelle?equipement=" + SCENARIOS["causes_equipement"])
            page.reload()                                   # nouvelle ouverture : un seul test du fournisseur
            attendre_pret(page)
            page.wait_for_selector(".di-formulaire")
            page.wait_for_function("Ia.etat() === 'injoignable'")
            self.verifier_ecrans_sans_bouton()
            self.assertEqual(self.faux.requetes, [])


# ---------------------------------------------------------------------------
# « Signaler » : reformuler le symptôme, proposer l'impact (démo)
# ---------------------------------------------------------------------------

class TestSignalerDemo(CasIaFonctions):

    def setUp(self):
        super().setUp()
        # Vrai nom d'un demandeur de la démo pour le profil : il ne doit jamais partir vers l'IA.
        self.demandeur = ligne_demo("demandes", SCENARIOS["di_statut_nouvelle"])["demandeur"]
        self.equipement = ligne_demo("equipements", SCENARIOS["causes_equipement"])
        regler_ia(self.contexte, url=self.faux.url)

    def test_utiliser_rien_ecrit_avant_envoyer_puis_trace(self):
        page = self.ouvrir_signaler(profil="demandeur", nom=self.demandeur)
        page.wait_for_selector('.di-ia .ia-bouton:has-text("%s")' % LIBELLE_DI)
        page.fill("input[name=symptome]", "ça fuit")
        page.fill("textarea[name=description]", "flaque sous la machine depuis ce matin")
        avant = self.instantane()

        texte = self.proposer_et_choisir(LIBELLE_DI, "Utiliser")
        self.assertIn(REPONSES["reformulerDI"]["symptome"], texte)
        self.assertIn("dégradé", texte)
        self.verifier_donnees_envoyees("reformulerDI", ["ça fuit", "flaque sous la machine depuis ce matin",
                                                        self.equipement["designation"]])
        valeurs = page.evaluate(VALEURS_DI_JS)
        self.assertEqual(valeurs["symptome"], REPONSES["reformulerDI"]["symptome"])
        self.assertEqual(valeurs["impact"], REPONSES["reformulerDI"]["impact"])
        self.assertEqual(valeurs["description"], "flaque sous la machine depuis ce matin")
        self.assertIn("Priorité calculée", page.inner_text(".di-priorite"))
        self.assertEqual(self.instantane(), avant, "rien n'est écrit avant « Envoyer »")

        # « Envoyer » (le bouton habituel) : la DI porte la proposition, le journal la trace
        page.click(".di-envoyer")
        page.wait_for_selector(".di-numero")
        di_id = page.get_attribute(".di-numero", "data-numero")
        di = page.evaluate("(id) => Donnees.trouver('demandes', id)", di_id)
        self.assertEqual((di["symptome"], di["impact"], di["demandeur"]),
                         (REPONSES["reformulerDI"]["symptome"], "dégradé", self.demandeur))
        self.assertEqual(traces(self.journal(), "demandes", di_id), ["symptome", "impact"])

    def test_modifier_ignorer_et_impact_securite_jamais_baisse(self):
        page = self.ouvrir_signaler(profil="demandeur", nom=self.demandeur)
        page.wait_for_selector(".di-ia .ia-bouton")
        # Le bouton suit l'IA sans réafficher l'écran : coupée sur le poste, puis remise
        page.evaluate("Ia.enregistrerReglages({ actif: false })")
        self.aucun_bouton_ia()
        self.assertTrue(page.is_hidden(".di-ia"))
        page.evaluate("Ia.enregistrerReglages({ actif: true })")
        self.assertEqual(page.locator(".di-ia .ia-bouton").count(), 1)
        # Rien d'écrit : rien n'est demandé, la personne est invitée à décrire d'abord
        self.cliquer_ia(LIBELLE_DI)
        self.attendre_toast("Écrivez d'abord ce que vous constatez")
        self.assertEqual((page.locator(".ia-encadre").count(), self.demandes_recues("reformulerDI")), (0, []))
        page.fill("input[name=symptome]", "bruit bizarre")
        avant = self.instantane()

        # Ignorer : rien ne change
        self.proposer_et_choisir(LIBELLE_DI, "Ignorer")
        self.assertEqual(page.evaluate(VALEURS_DI_JS)["symptome"], "bruit bizarre")
        self.assertEqual(page.evaluate(VALEURS_DI_JS)["impact"], "")

        # Modifier : symptôme et impact remplis, curseur dans le symptôme pour le retoucher
        self.proposer_et_choisir(LIBELLE_DI, "Modifier")
        valeurs = page.evaluate(VALEURS_DI_JS)
        self.assertEqual((valeurs["symptome"], valeurs["impact"], valeurs["focus"]),
                         (REPONSES["reformulerDI"]["symptome"], "dégradé", "symptome"))
        page.keyboard.press("End")
        page.keyboard.type(", côté opérateur")
        self.assertEqual(page.input_value("input[name=symptome]"), REPONSES["reformulerDI"]["symptome"] + ", côté opérateur")

        # « Sécurité » choisi par la personne : l'IA ne le baisse jamais
        page.click("label.tuile.securite")
        self.assertEqual(page.evaluate(VALEURS_DI_JS)["impact"], "sécurité")
        texte = self.proposer_et_choisir(LIBELLE_DI, "Utiliser")
        self.assertIn("« Sécurité » choisi : gardé", texte)
        self.assertEqual(page.evaluate(VALEURS_DI_JS)["impact"], "sécurité")
        self.assertTrue(page.is_visible(".di-zone-securite .bandeau-securite"))
        self.assertEqual(self.instantane(), avant, "rien n'est écrit avant « Envoyer »")


# ---------------------------------------------------------------------------
# Compte rendu de l'OT : rédiger, codes, erreurs, enregistrement habituel (démo)
# ---------------------------------------------------------------------------

class TestCompteRenduDemo(CasIaFonctions):

    def setUp(self):
        super().setUp()
        self.ot_id = SCENARIOS["ot_statut_en_cours"]
        self.ot = ligne_demo("ordres_travail", self.ot_id)
        self.di = ligne_demo("demandes", self.ot["di_id"])
        self.equipement = ligne_demo("equipements", self.ot["equipement_id"])

    def ouvrir_technicien(self, **reglages):
        """Fiche de l'OT en cours, onglet Compte rendu, avec le profil de son technicien."""
        regler_ia(self.contexte, url=self.faux.url, **reglages)
        technicien = ligne_demo("techniciens", self.ot["technicien_id"])
        page = self.ouvrir_compte_rendu(self.ot_id, profil="technicien", nom=technicien["prenom"] + " " + technicien["nom"],
                                        technicien_id=self.ot["technicien_id"])
        page.wait_for_selector('.ia-bouton:has-text("%s")' % LIBELLE_CR)
        return page

    def statut_affiche(self):
        return self.page.inner_text(".ot-badges .badge.statut")

    def test_rediger_utiliser_annuler_la_proposition_modifier_ignorer(self):
        page = self.ouvrir_technicien()
        self.assertEqual(page.input_value(CHAMP_CR), "")
        avant = self.instantane()
        statut = self.statut_affiche()

        # Notes vides : rien n'est demandé, la personne est invitée à écrire (ou dicter) ses notes
        self.cliquer_ia(LIBELLE_CR)
        self.attendre_toast("Écrivez d'abord vos notes")
        self.assertEqual(page.locator(".ia-encadre").count(), 0)
        self.assertEqual(self.demandes_recues("compteRendu"), [])

        page.fill(CHAMP_CR, NOTES)
        texte = self.proposer_et_choisir(LIBELLE_CR, "Utiliser")
        self.assertIn("Constat : fuite à la garniture mécanique.", texte)
        self.verifier_donnees_envoyees("compteRendu", [NOTES, self.ot["titre"], self.equipement["designation"]])
        self.assertEqual(page.input_value(CHAMP_CR), REPONSES["compteRendu"]["texte"])

        # « Annuler la proposition » rend les notes tant que rien n'est enregistré
        page.click("#form-compte-rendu button:has-text('Annuler la proposition')")
        self.assertEqual(page.input_value(CHAMP_CR), NOTES)
        self.assertEqual(page.locator("button:has-text('Annuler la proposition')").count(), 0)

        # Modifier : le champ est rempli et le curseur y est placé pour retoucher
        self.proposer_et_choisir(LIBELLE_CR, "Modifier")
        valeurs = page.evaluate(VALEURS_CR_JS)
        self.assertEqual((valeurs["compte_rendu"], valeurs["focus"]), (REPONSES["compteRendu"]["texte"], "compte_rendu"))
        page.click("#form-compte-rendu button:has-text('Annuler la proposition')")
        self.assertEqual(page.input_value(CHAMP_CR), NOTES)

        # Ignorer : rien ne change
        self.proposer_et_choisir(LIBELLE_CR, "Ignorer")
        self.assertEqual(page.input_value(CHAMP_CR), NOTES)

        # Rien n'est enregistré sans le bouton habituel, le statut ne bouge pas
        self.assertEqual(self.instantane(), avant)
        self.assertEqual(self.statut_affiche(), statut)

    def test_codes_utiliser_puis_code_invente_rejete_et_annonce(self):
        page = self.ouvrir_technicien()
        attendus = premiers_codes()
        page.fill(CHAMP_CR, NOTES)
        avant = self.instantane()

        texte = self.proposer_et_choisir(LIBELLE_CODES, "Utiliser")
        for code in attendus.values():
            self.assertIn(code, texte)
        self.verifier_donnees_envoyees("codes", [NOTES, self.ot["titre"], self.di["symptome"]])
        valeurs = page.evaluate(VALEURS_CR_JS)
        self.assertEqual({champ: valeurs[champ] for champ in attendus}, attendus)

        # Scénario du brief : un code inventé par l'IA n'est pas mis dans la liste, il est annoncé
        page.evaluate("Ia.enregistrerReglages({ modele: 'faux-invente' })")
        page.select_option("#form-compte-rendu [name=cause_code]", "")
        self.cliquer_ia(LIBELLE_CODES)
        texte = self.attendre_proposition()
        self.assertIn("code inconnu proposé par l'IA, ignoré : " + CODE_INVENTE, texte)
        self.choisir("Utiliser")
        valeurs = page.evaluate(VALEURS_CR_JS)
        self.assertEqual(valeurs["cause_code"], "")
        self.assertEqual((valeurs["symptome_code"], valeurs["remede_code"]), (attendus["symptome_code"], attendus["remede_code"]))
        options = page.eval_on_selector_all("#form-compte-rendu [name=cause_code] option", "o => o.map((e) => e.value)")
        self.assertNotIn(CODE_INVENTE, options)
        self.assertEqual(self.instantane(), avant)

    def test_reponse_illisible_delai_depasse_et_annuler(self):
        page = self.ouvrir_technicien(modele="faux-illisible")
        page.fill(CHAMP_CR, NOTES)
        avant = self.instantane()

        # Réponse illisible : message dans l'encadré, aucune proposition
        self.cliquer_ia(LIBELLE_CR)
        page.wait_for_selector(".ia-encadre .ia-erreur", state="visible")
        self.assertIn("illisible", page.inner_text(".ia-encadre .ia-erreur"))
        self.assertEqual(page.locator(".ia-encadre .ia-proposition, .ia-encadre button:has-text('Utiliser')").count(), 0)
        page.click(".ia-encadre button:has-text('Fermer')")
        self.assertEqual(page.input_value(CHAMP_CR), NOTES)

        # Fournisseur lent, délai court : progression, puis message de délai
        page.evaluate("Ia.enregistrerReglages({ modele: 'faux-lent', delaiS: 1 })")
        self.cliquer_ia(LIBELLE_CR)
        page.wait_for_selector(".ia-encadre .ia-progression", state="visible")
        self.assertIn("L'IA rédige", page.inner_text(".ia-encadre"))
        page.wait_for_selector(".ia-encadre .ia-erreur", state="visible")
        self.assertIn("délai", page.inner_text(".ia-encadre .ia-erreur"))
        page.click(".ia-encadre button:has-text('Fermer')")

        # « Annuler » pendant la progression ferme l'encadré, rien ne change
        page.evaluate("Ia.enregistrerReglages({ delaiS: 30 })")
        self.cliquer_ia(LIBELLE_CODES)
        page.wait_for_selector(".ia-encadre .ia-progression", state="visible")
        page.click(".ia-encadre button:has-text('Annuler')")
        page.wait_for_selector(".ia-encadre", state="detached")
        valeurs = page.evaluate(VALEURS_CR_JS)
        self.assertEqual((valeurs["compte_rendu"], valeurs["cause_code"]), (NOTES, self.ot["cause_code"]))
        self.assertEqual(page.evaluate("Ia.etat()"), "ok", "un fournisseur lent ou bavard reste joignable")
        self.assertEqual(page.locator(".ia-bouton").count(), 2)
        self.assertEqual(self.instantane(), avant)

    def test_enregistrement_habituel_valeurs_et_trace_statut_inchange(self):
        page = self.ouvrir_technicien()
        attendus = premiers_codes()
        page.fill(CHAMP_CR, NOTES)
        self.proposer_et_choisir(LIBELLE_CODES, "Utiliser")
        self.proposer_et_choisir(LIBELLE_CR, "Utiliser")

        page.click("#form-compte-rendu button[type=submit]")
        self.attendre_toast("Compte rendu enregistré.")
        ot = page.evaluate("(id) => Donnees.trouver('ordres_travail', id)", self.ot_id)
        self.assertEqual(ot["compte_rendu"].replace("\r\n", "\n"), REPONSES["compteRendu"]["texte"])
        self.assertEqual({champ: ot[champ] for champ in attendus}, attendus)
        self.assertEqual(ot["statut"], self.ot["statut"])
        self.assertEqual(self.statut_affiche(), self.ot["statut"])
        self.assertEqual(sorted(traces(self.journal(), "ordres_travail", self.ot_id)),
                         ["cause_code", "compte_rendu", "remede_code", "symptome_code"])

        # Un second enregistrement, retouché à la main, n'ajoute aucune trace
        page.evaluate("document.querySelector('#form-compte-rendu').dataset.ancien = '1'")
        page.fill(CHAMP_CR, "Compte rendu retouché à la main après la proposition.")
        page.click("#form-compte-rendu button[type=submit]")
        page.wait_for_selector("#form-compte-rendu:not([data-ancien])")      # fiche réaffichée après l'écriture
        self.assertEqual(len(traces(self.journal(), "ordres_travail", self.ot_id)), 4)

    def test_code_change_a_la_main_avant_l_enregistrement_non_trace(self):
        """Un code proposé puis changé à la main avant « Enregistrer » ne vient plus de l'IA : aucune trace
        pour lui ; les codes gardés tels quels sont tracés (ajout de l'orchestrateur, défaut injecté)."""
        page = self.ouvrir_technicien()
        attendus = premiers_codes()
        page.fill(CHAMP_CR, NOTES)
        self.proposer_et_choisir(LIBELLE_CODES, "Utiliser")
        autre = page.evaluate("""(actuel) => Array.from(document.querySelectorAll('#form-compte-rendu [name=cause_code] option'))
          .map((option) => option.value).find((valeur) => valeur && valeur !== actuel)""", attendus["cause_code"])
        page.select_option("#form-compte-rendu [name=cause_code]", autre)
        page.click("#form-compte-rendu button[type=submit]")
        self.attendre_toast("Compte rendu enregistré.")
        ot = page.evaluate("(id) => Donnees.trouver('ordres_travail', id)", self.ot_id)
        self.assertEqual((ot["cause_code"], ot["compte_rendu"].replace("\r\n", "\n")), (autre, NOTES))
        self.assertEqual(sorted(traces(self.journal(), "ordres_travail", self.ot_id)), ["remede_code", "symptome_code"])

    def test_boutons_seulement_sur_un_ot_modifiable(self):
        regler_ia(self.contexte, url=self.faux.url)
        en_attente = SCENARIOS["ot_statut_en_attente"]
        page = self.ouvrir_compte_rendu(en_attente)
        page.wait_for_selector('.ia-bouton:has-text("%s")' % LIBELLE_CODES)
        self.assertEqual(page.locator('.ia-bouton:has-text("%s")' % LIBELLE_CR).count(), 1)
        # Les boutons suivent l'IA sans réafficher l'écran : coupée sur le poste, puis remise
        page.evaluate("Ia.enregistrerReglages({ actif: false })")
        self.aucun_bouton_ia()
        page.evaluate("Ia.enregistrerReglages({ actif: true })")
        self.assertEqual(page.locator(".ia-bouton").count(), 2)
        for role in ("ot_statut_cloture_administratif", "ot_statut_annule", "ot_statut_cloture_technique"):
            with self.subTest(role=role):
                ot_id = SCENARIOS[role]
                self.aller("#/ot/" + ot_id, ".ot-fiche")
                self.onglet_compte_rendu(ot_id)
                self.assertTrue(page.is_disabled(CHAMP_CR))
                self.aucun_bouton_ia()
        self.assertEqual(self.faux.requetes_vers("/api/chat"), [])

    def test_demandeur_aucun_bouton_d_ot(self):
        regler_ia(self.contexte, url=self.faux.url)
        page = self.ouvrir_signaler(profil="demandeur", nom="Demandeur essai")
        page.wait_for_selector(".di-ia .ia-bouton")         # « Signaler » : oui
        self.page.evaluate("(route) => { location.hash = route; }", "#/ot/" + self.ot_id)
        self.attendre_toast("n'est pas disponible pour le profil")
        self.assertEqual(page.locator("#form-compte-rendu").count(), 0)
        self.aucun_bouton_ia()


# ---------------------------------------------------------------------------
# Mode serveur : par le relais /api/ia, CSV comparés à l'octet ; téléphone
# ---------------------------------------------------------------------------

class TestParLeRelais(CasIaFonctions):

    def test_signaler_par_le_relais_csv_identiques_puis_envoi(self):
        demandeur = ligne_demo("demandes", SCENARIOS["di_statut_nouvelle"])["demandeur"]
        with ServeurPrevo(arguments=["--ia-url", self.faux.url]) as serveur:
            regler_ia(self.contexte)
            page = self.ouvrir_signaler(serveur=serveur, profil="demandeur", nom=demandeur, attendre_ia=False)
            page.wait_for_selector('.di-ia .ia-bouton:has-text("%s")' % LIBELLE_DI)   # posé dès le test réussi
            page.fill("input[name=symptome]", "ça fuit")
            page.fill("textarea[name=description]", "flaque sous la machine")
            avant = self.instantane()
            for choix in ("Ignorer", "Modifier", "Utiliser"):
                with self.subTest(choix=choix):
                    self.proposer_et_choisir(LIBELLE_DI, choix)
                    self.assertEqual(self.instantane(), avant, "CSV identiques à l'octet avant « Envoyer »")
            # première demande : la saisie d'origine (les suivantes partent de la proposition reprise)
            self.verifier_donnees_envoyees("reformulerDI", ["ça fuit", "flaque sous la machine"], rang=0)

            page.click(".di-envoyer")
            page.wait_for_selector(".di-numero")
            di_id = page.get_attribute(".di-numero", "data-numero")
            ligne = next(l for l in lire_csv(serveur.dossier, "demandes") if l["id"] == di_id)
            self.assertEqual((ligne["symptome"], ligne["impact"]), (REPONSES["reformulerDI"]["symptome"], "dégradé"))
            self.assertEqual(traces(self.journal(), "demandes", di_id), ["symptome", "impact"])
            self.verifier_par_le_relais()

    def test_compte_rendu_et_codes_par_le_relais_puis_enregistrement(self):
        ot_id = SCENARIOS["ot_statut_en_cours"]
        ot_demo = ligne_demo("ordres_travail", ot_id)
        technicien = ligne_demo("techniciens", ot_demo["technicien_id"])
        attendus = premiers_codes()
        with ServeurPrevo(arguments=["--ia-url", self.faux.url]) as serveur:
            regler_ia(self.contexte)
            page = self.ouvrir_compte_rendu(ot_id, serveur=serveur, profil="technicien",
                                            nom=technicien["prenom"] + " " + technicien["nom"],
                                            technicien_id=ot_demo["technicien_id"])
            page.wait_for_selector('.ia-bouton:has-text("%s")' % LIBELLE_CODES)
            page.fill(CHAMP_CR, NOTES)
            avant = self.instantane()
            self.proposer_et_choisir(LIBELLE_CODES, "Utiliser")
            self.proposer_et_choisir(LIBELLE_CR, "Utiliser")
            self.assertEqual(self.instantane(), avant, "CSV identiques à l'octet avant l'enregistrement")
            self.verifier_donnees_envoyees("compteRendu", [NOTES, ot_demo["titre"]])
            self.verifier_donnees_envoyees("codes", [ot_demo["titre"]])

            page.click("#form-compte-rendu button[type=submit]")
            self.attendre_toast("Compte rendu enregistré.")
            ligne = next(l for l in lire_csv(serveur.dossier, "ordres_travail") if l["id"] == ot_id)
            self.assertEqual(ligne["compte_rendu"].replace("\r\n", "\n"), REPONSES["compteRendu"]["texte"])
            self.assertEqual({champ: ligne[champ] for champ in attendus}, attendus)
            self.assertEqual(ligne["statut"], ot_demo["statut"])
            self.assertEqual(sorted(traces(self.journal(), "ordres_travail", ot_id)),
                             ["cause_code", "compte_rendu", "remede_code", "symptome_code"])
            self.verifier_par_le_relais()

    def test_telephone_375px_par_le_relais(self):
        ot_id = SCENARIOS["ot_statut_en_cours"]
        technicien_id = ligne_demo("ordres_travail", ot_id)["technicien_id"]
        self.passer_au_telephone()
        with ServeurPrevo(arguments=["--ia-url", self.faux.url]) as serveur:
            regler_ia(self.contexte)
            page = self.ouvrir_signaler(serveur=serveur, profil="technicien", nom="Technicien essai",
                                        technicien_id=technicien_id)
            page.wait_for_selector(".di-ia .ia-bouton")
            page.fill("input[name=symptome]", "ça fuit")
            self.verifier_ecran_telephone(LIBELLE_DI)

            self.aller("#/ot/" + ot_id, ".ot-fiche")
            self.onglet_compte_rendu(ot_id)
            page.fill(CHAMP_CR, NOTES)
            self.verifier_ecran_telephone(LIBELLE_CODES)
            self.verifier_ecran_telephone(LIBELLE_CR, "Utiliser")
            # après « Utiliser » : « Annuler la proposition », lui aussi facile à toucher
            self.assertGreaterEqual(page.locator(".ot-ia-annuler").bounding_box()["height"], 48)
            self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 375)
            self.verifier_par_le_relais()

    def verifier_ecran_telephone(self, libelle, choix="Ignorer"):
        """Proposition ouverte : zones ≥ 48 px, aucun défilement horizontal ; puis `choix`."""
        page = self.page
        self.cliquer_ia(libelle)
        self.assertIn(MENTION, self.attendre_proposition())
        hauteurs = page.evaluate("""() => [...document.querySelectorAll('.ia-bouton, .ia-encadre button')]
          .filter((e) => e.offsetParent !== null).map((e) => Math.round(e.getBoundingClientRect().height))""")
        self.assertTrue(hauteurs)
        self.assertGreaterEqual(min(hauteurs), 48)
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 375)
        self.choisir(choix)


# ---------------------------------------------------------------------------
# Réponses piégées : tout texte de l'IA est affiché comme du texte (relecture du lot 4)
# ---------------------------------------------------------------------------

class TestReponsesPiegees(CasIaFonctions):

    def verifier_affiche_en_texte(self):
        page = self.page
        self.assertIn("<img", page.inner_text(".ia-encadre"))
        self.assertEqual(page.locator(".ia-encadre img").count(), 0)          # <b> de l'écran permis, pas d'<img> venue de l'IA
        self.assertNotIn("<b>C01</b>", page.inner_html(".ia-encadre"))     # code piégé : échappé
        page.wait_for_timeout(300)
        self.assertIsNone(page.evaluate("window.__xss === undefined ? null : window.__xss"))

    def test_signaler_et_compte_rendu_proposition_html_affichee_en_texte(self):
        regler_ia(self.contexte, url=self.faux.url, modele="faux-html")
        ot_id = SCENARIOS["ot_statut_en_cours"]
        technicien_id = ligne_demo("ordres_travail", ot_id)["technicien_id"]
        page = self.ouvrir_signaler(profil="technicien", nom="Technicien essai", technicien_id=technicien_id)
        page.wait_for_selector('.di-ia .ia-bouton')
        page.fill("input[name=symptome]", "ça fuit")
        self.cliquer_ia(LIBELLE_DI)
        self.attendre_proposition()
        self.verifier_affiche_en_texte()
        self.choisir("Utiliser")
        self.assertTrue(page.input_value("input[name=symptome]").startswith("<img"))   # texte brut dans le champ
        self.assertIsNone(page.evaluate("window.__xss === undefined ? null : window.__xss"))

        self.aller("#/ot/" + ot_id, ".ot-fiche")
        self.onglet_compte_rendu(ot_id)
        page.wait_for_selector('.ia-bouton:has-text("%s")' % LIBELLE_CODES)
        page.fill(CHAMP_CR, NOTES)
        for libelle in (LIBELLE_CODES, LIBELLE_CR):
            with self.subTest(fonction=libelle):
                self.cliquer_ia(libelle)
                self.attendre_proposition()
                self.verifier_affiche_en_texte()
                self.choisir("Ignorer")


if __name__ == "__main__":
    unittest.main()
