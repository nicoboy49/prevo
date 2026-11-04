"""Personne ne perd sa saisie devant un fichier abîmé (chantier i18n-socle, tâche T201 ; suite de T197 et T200).

Depuis T200, un fichier abîmé n'est jamais réécrit (ErreurFichierAbime dans le navigateur, 409 « fichier_abime » du
serveur) ; avec les comptes, seul le responsable peut forcer son remplacement (import ZIP). Condition de Nicolas : un
technicien ou un opérateur bloqué par une table abîmée ne perd jamais ce qu'il a saisi, en particulier une déclaration
de panne faite par QR code :
    1. le message de refus dit quoi faire, sans jargon, selon le rôle (App.signalerErreur, App.messageErreur ;
       App.raisonErreur en court dans une phrase) : « Fichier abîmé : prévenez le responsable. … » pour qui n'est pas
       responsable ; pour le responsable, le fichier, la sauvegarde du jour à restaurer ou le ZIP à importer, et
       Paramètres › Contrôle de la base ; même règle pour le bandeau de l'ouverture ;
    2. la saisie reste dans le formulaire (champs, photo choisie), le bouton redevient utilisable, rien n'est vidé ni
       quitté ; rien n'est écrit (ni la table, ni la photo) ;
    3. le responsable voit le bandeau « Fichier abîmé » dès sa connexion suivante.

    a. TestQrServeurComptes : serveur avec comptes, copie de f3-v1.2.0, demandes.csv abîmé (une valeur au-delà de
       l'en-tête sur sa dernière ligne). Le demandeur ouvre sur un téléphone l'adresse de l'étiquette QR de EQ-0005,
       se connecte, « Signaler un problème », symptôme, impact, précisions, photo, « Envoyer » : message sans jargon,
       saisie identique, demandes.csv identique à l'octet, aucune demande ni photo écrite. Puis le responsable se
       connecte (autre navigateur) : bandeau « Fichier abîmé » qui cite demandes.csv, dès l'accueil.
    b. TestDeclarationDossier : mode dossier (OPFS simulé), profil demandeur, même jeu, même déclaration.
    c. TestTechnicienDossier : mode dossier, technicien TEC-0001, ordres_travail.csv abîmé (OT-2025-0006 remis
       « En cours » à son nom dans la copie) : compte rendu enregistré puis clôture technique depuis la fiche de l'OT.
    d. TestResponsableDossier : mode dossier, responsable, equipements.csv abîmé : « Modifier l'équipement » → message
       du responsable (fichier, sauvegarde du jour, ZIP, Contrôle de la base), saisie gardée, fichier identique.

Règle numéro un : jamais de données réelles (copies des jeux de tests/fixtures/formats/ dans des dossiers temporaires,
ou dans l'OPFS du navigateur de test).

Lancer depuis la racine du projet (à travers le verrou du navigateur) :
    py -X utf8 -m unittest discover -s tests -p "test_garde_abime_saisie.py" -v
"""
import csv
import io
import re
import unittest

from commun import ServeurPrevo
from test_demandes import fichier_png
from test_recette_socle import (DESIGNATION, EQUIPEMENT, ERREUR_SANS_SESSION, NOTER_TOASTS_JS, SERVEUR, BOM,
                                CasRecetteSocle, fichiers_de, fichiers_du_jeu, lignes_en_dictionnaires)

# Textes attendus (consigne de T201).
MESSAGE_NON_RESPONSABLE = ("Fichier abîmé : prévenez le responsable. Rien n'a été enregistré ; votre saisie est restée "
                           "dans le formulaire.")
BANDEAU_NON_RESPONSABLE = ("Fichier abîmé : prévenez le responsable. Tant qu'il n'est pas réparé, Prévo refuse les "
                           "enregistrements qui le touchent, sans rien perdre.")


def message_du_responsable(fichier):
    return ("Fichier abîmé (%s) : rien n'a été enregistré, pour ne rien perdre ; votre saisie est restée dans le "
            "formulaire. Restaurez la sauvegarde du jour (Paramètres › Sauvegardes) ou importez un ZIP ; le détail est "
            "dans Paramètres › Contrôle de la base." % fichier)


JARGON = ("en-tête", "guillemet")
VALEUR_EN_TROP = b";valeur en trop"
OT_DU_TECHNICIEN = "OT-2025-0006"
TECHNICIEN = "TEC-0001"
COMPTE_RENDU = "Contacteur grillé remplacé, essai de 15 min sans défaut."
SYMPTOME = "Fuite d'huile sous la pompe"
PRECISIONS = "Depuis ce matin, une flaque sous le carter. Déclaré par QR code."

# Chromium note en console.error toute réponse HTTP >= 400 : seules celles-ci sont attendues.
# Demandeur avec les comptes : les tables qui ne sont pas à lui répondent 403 (vues comme absentes).
ERREUR_TABLES_DU_DEMANDEUR = re.compile(r"status of 403 .*/api/csv/(?:%s):" % "|".join(
    sorted(set(SERVEUR.TABLES) - set(SERVEUR.TABLES_DU_DEMANDEUR))))

# Saisie du formulaire « Signaler un problème », telle qu'on la voit (champs, photo, bouton).
SAISIE_DEMANDE_JS = """() => {
  const f = document.querySelector('.di-formulaire');
  if (!f) return null;
  const coche = f.querySelector('input[name=impact]:checked');
  const apercu = f.querySelector('.di-apercu');
  const image = f.querySelector('.di-apercu-image');
  const bouton = f.querySelector('.di-envoyer');
  return { equipement: f.querySelector('input[name=equipement_id]').value,
    symptome: f.querySelector('input[name=symptome]').value, impact: coche ? coche.value : '',
    description: f.querySelector('textarea[name=description]').value,
    photo: Boolean(apercu && !apercu.hidden && image && image.getAttribute('src')),
    boutonActif: !bouton.disabled, texteBouton: bouton.textContent.replace(/\\s+/g, ' ').trim(),
    hash: location.hash };
}"""

# Saisie du compte rendu d'un OT et statut affiché.
SAISIE_COMPTE_RENDU_JS = """() => {
  const f = document.querySelector('#form-compte-rendu');
  if (!f) return null;
  const bouton = f.querySelector('button[type=submit]');
  return { compte_rendu: f.querySelector('[name=compte_rendu]').value,
    remise_service: f.querySelector('[name=remise_service]').checked,
    cause_code: f.querySelector('[name=cause_code]').value, boutonActif: !bouton.disabled,
    statut: Donnees.trouver('ordres_travail', '""" + OT_DU_TECHNICIEN + """').statut, hash: location.hash };
}"""

BANDEAUX_JS = """() => Array.from(document.querySelectorAll('#alertes-app > *'))
  .map((e) => e.textContent.replace(/\\s+/g, ' ').trim())"""

# Raison courte (App.raisonErreur) d'un refus sur gammes.csv abîmé, pour le profil ouvert.
RAISON_GAMMES_JS = "() => App.raisonErreur(new Donnees.ErreurFichierAbime('gammes', 'gammes.csv'))"


def avec_valeur_en_trop(octets):
    """CSV (fini par CRLF) dont la dernière ligne porte une valeur au-delà de l'en-tête : fichier abîmé (une
    réécriture la perdrait ; csv.analyser du navigateur et raisons_fichier_abime du serveur)."""
    if not octets.endswith(b"\r\n"):
        raise AssertionError("le CSV devrait finir par CRLF : %r" % octets[-20:])
    return octets[:-2] + VALEUR_EN_TROP + b"\r\n"


def ot_remis_en_cours(octets, ot_id, technicien_id):
    """ordres_travail.csv (copie) où l'OT ot_id est « En cours », au technicien donné, sans fin ni clôture ni compte
    rendu (tous les OT du jeu f3-v1.2.0 sont clôturés administrativement, donc verrouillés)."""
    texte = octets.decode("utf-8-sig")
    lignes = list(csv.reader(io.StringIO(texte, newline=""), delimiter=";"))
    entete = lignes[0]
    trouve = False
    for ligne in lignes[1:]:
        if ligne and ligne[entete.index("id")] == ot_id:
            trouve = True
            for colonne, valeur in (("statut", "En cours"), ("technicien_id", technicien_id), ("date_fin", ""),
                                    ("cause_code", ""), ("remede_code", ""), ("compte_rendu", ""),
                                    ("remise_service", "0"), ("date_cloture_tech", ""), ("date_cloture_admin", "")):
                ligne[entete.index(colonne)] = valeur
    if not trouve:
        raise AssertionError("%s absent du jeu" % ot_id)
    sortie = io.StringIO(newline="")
    csv.writer(sortie, delimiter=";", lineterminator="\r\n").writerows(lignes)
    return BOM + sortie.getvalue().encode("utf-8")


def documents(fichiers):
    return sorted(chemin for chemin in fichiers if chemin.startswith("documents/"))


# ---------------------------------------------------------------------------
# Gestes et vérifications communs
# ---------------------------------------------------------------------------

class CasSaisieGardee(CasRecetteSocle):

    def nouveau_contexte(self, telephone=False):
        """Autre navigateur (autre poste, ou téléphone) : toasts notés, erreurs de console surveillées."""
        options = ({"viewport": {"width": 375, "height": 812}, "is_mobile": True, "has_touch": True}
                   if telephone else {"viewport": {"width": 1280, "height": 800}})
        contexte = self.navigateur.new_context(locale="fr-FR", **options)
        self.addCleanup(contexte.close)
        contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        contexte.add_init_script(NOTER_TOASTS_JS)
        page = contexte.new_page()
        self.surveiller(page)
        return page

    def nombre_de_toasts(self, page):
        return page.evaluate("(window.__toasts || []).length")

    def toast_apres(self, page, debut, morceau):
        """Premier message (UI.toast) montré après les `debut` premiers, qui contient `morceau`."""
        page.wait_for_function("([d, m]) => (window.__toasts || []).slice(d).some((t) => t.includes(m))",
                               arg=[debut, morceau])
        return next(t for t in page.evaluate("window.__toasts")[debut:] if morceau in t)

    def verifier_message_non_responsable(self, toast):
        self.assertEqual(toast, MESSAGE_NON_RESPONSABLE)
        for mot in JARGON:
            self.assertNotIn(mot, toast.lower())

    def verifier_bandeau_non_responsable(self, page):
        bandeaux = [b for b in page.evaluate(BANDEAUX_JS) if "abîmé" in b]
        self.assertEqual(len(bandeaux), 1, bandeaux)
        self.assertIn(BANDEAU_NON_RESPONSABLE, bandeaux[0])
        for mot in JARGON:
            self.assertNotIn(mot, bandeaux[0].lower())

    # -- « Signaler un problème » depuis la fiche de l'équipement (adresse de l'étiquette QR) -----

    def declarer_la_panne(self, page):
        """Fiche de EQ-0005 → « Signaler un problème » → symptôme, impact, précisions, photo ; rend la saisie vue."""
        page.wait_for_function("(id) => location.hash === '#/equipement/' + id", arg=EQUIPEMENT)
        page.click("a.parc-signaler")
        page.wait_for_selector(".di-formulaire")
        page.fill("input[name=symptome]", SYMPTOME)
        page.click("label.tuile:has(input[value='arrêt'])")
        page.fill("textarea[name=description]", PRECISIONS)
        page.locator(".di-fichier-photo").set_input_files(fichier_png(320, 240))
        page.wait_for_selector(".di-apercu:not([hidden]) img")
        saisie = page.evaluate(SAISIE_DEMANDE_JS)
        self.assertEqual((saisie["equipement"], saisie["symptome"], saisie["impact"], saisie["description"],
                          saisie["photo"]), (EQUIPEMENT, SYMPTOME, "arrêt", PRECISIONS, True), saisie)
        return saisie

    def envoyer_et_verifier_la_saisie_gardee(self, page, saisie):
        """« Envoyer » : message sans jargon, puis la même saisie, bouton de nouveau utilisable, écran pas quitté."""
        debut = self.nombre_de_toasts(page)
        page.click(".di-envoyer")
        toast = self.toast_apres(page, debut, "abîmé")
        self.verifier_message_non_responsable(toast)
        page.wait_for_function("() => { const b = document.querySelector('.di-envoyer'); "
                               "return b && !b.disabled && b.textContent.includes('Envoyer la demande'); }")
        apres = page.evaluate(SAISIE_DEMANDE_JS)
        self.assertEqual(apres, saisie, "saisie de la déclaration perdue ou changée après le refus")
        self.assertTrue(apres["hash"].startswith("#/di/nouvelle"), apres["hash"])
        self.assertEqual(page.locator(".di-numero").count(), 0)


# ---------------------------------------------------------------------------
# a. Déclaration de panne par QR, serveur avec comptes ; puis connexion du responsable
# ---------------------------------------------------------------------------

class TestQrServeurComptes(CasSaisieGardee):

    def test_declaration_par_qr_sur_demandes_abime_saisie_gardee_puis_bandeau_du_responsable(self):
        self.autoriser_erreur(ERREUR_SANS_SESSION)                    # sonde avant la connexion (comptes exigés)
        self.autoriser_erreur(ERREUR_TABLES_DU_DEMANDEUR)
        source = self.jeu("f3-v1.2.0")
        (source / "demandes.csv").write_bytes(avec_valeur_en_trop((source / "demandes.csv").read_bytes()))
        with ServeurPrevo(source=source, comptes=True) as serveur:
            abime = (serveur.dossier / "demandes.csv").read_bytes()
            self.assertTrue(abime.endswith(VALEUR_EN_TROP + b"\r\n"), "demandes.csv réécrit au démarrage")
            avant = fichiers_de(serveur.dossier)

            # Téléphone du demandeur : adresse de l'étiquette QR, connexion demandée, puis la fiche.
            telephone = self.nouveau_contexte(telephone=True)
            telephone.goto(serveur.url + "/#/equipement/" + EQUIPEMENT)
            self.se_connecter(telephone, "demandeur")
            self.assertEqual(telephone.evaluate("App.profil.type"), "demandeur")
            self.verifier_bandeau_non_responsable(telephone)
            saisie = self.declarer_la_panne(telephone)
            self.envoyer_et_verifier_la_saisie_gardee(telephone, saisie)

            # Rien d'écrit : demandes.csv identique à l'octet, aucune demande, aucune photo (le refus est montré une
            # fois l'envoi terminé : rien n'est en cours).
            apres = fichiers_de(serveur.dossier)
            self.assertEqual(apres["demandes.csv"], abime)
            self.assertEqual(len(lignes_en_dictionnaires(apres["demandes.csv"])),
                             len(lignes_en_dictionnaires(avant["demandes.csv"])))
            self.assertEqual(documents(apres), documents(avant), "photo écrite alors que rien n'est enregistré")

            # Le responsable se connecte ensuite (autre poste) : bandeau « Fichier abîmé » qui cite demandes.csv.
            poste = self.nouveau_contexte()
            poste.goto(serveur.url + "/#/accueil")
            self.se_connecter(poste, "responsable")
            self.assertEqual(poste.evaluate("App.profil.type"), "responsable")
            self.assertEqual(poste.evaluate("location.hash"), "#/accueil")
            bandeaux = [b for b in poste.evaluate(BANDEAUX_JS) if "abîmé" in b]
            self.assertEqual(len(bandeaux), 1, bandeaux)
            self.assertIn("Fichier abîmé : demandes.csv, repéré aujourd'hui.", bandeaux[0])
            self.assertIn("Paramètres › Contrôle de la base", bandeaux[0])
            self.assertNotIn("prévenez le responsable", bandeaux[0])
            self.assertEqual((serveur.dossier / "demandes.csv").read_bytes(), abime)
            poste.goto("about:blank")
            telephone.goto("about:blank")


# ---------------------------------------------------------------------------
# b. Même déclaration en mode dossier, profil demandeur
# ---------------------------------------------------------------------------

class TestDeclarationDossier(CasSaisieGardee):

    def setUp(self):
        super().setUp()
        self.demarrer_statique()

    def test_declaration_sur_demandes_abime_saisie_gardee_fichier_identique(self):
        fichiers = fichiers_du_jeu("f3-v1.2.0")
        fichiers["demandes.csv"] = avec_valeur_en_trop(fichiers["demandes.csv"])
        self.ouvrir_dossier(fichiers, "demandeur")
        self.verifier_bandeau_non_responsable(self.page)
        avant = self.instantane()
        self.aller("#/equipement/" + EQUIPEMENT, "a.parc-signaler")
        saisie = self.declarer_la_panne(self.page)
        self.envoyer_et_verifier_la_saisie_gardee(self.page, saisie)
        apres = self.instantane()
        self.assertEqual(apres["demandes.csv"], fichiers["demandes.csv"])
        self.assertEqual(documents(apres), documents(avant), "photo écrite alors que rien n'est enregistré")


# ---------------------------------------------------------------------------
# c. Technicien : compte rendu puis clôture technique d'un OT, ordres_travail.csv abîmé (mode dossier)
# ---------------------------------------------------------------------------

class TestTechnicienDossier(CasSaisieGardee):

    def setUp(self):
        super().setUp()
        self.demarrer_statique()

    def test_compte_rendu_et_cloture_sur_ordres_abime_saisie_gardee_fichier_identique(self):
        fichiers = fichiers_du_jeu("f3-v1.2.0")
        fichiers["ordres_travail.csv"] = avec_valeur_en_trop(
            ot_remis_en_cours(fichiers["ordres_travail.csv"], OT_DU_TECHNICIEN, TECHNICIEN))
        self.ouvrir_dossier(fichiers, "technicien", technicien_id=TECHNICIEN)
        # À l'ouverture, la génération des OT préventifs est refusée : le bandeau le dit, sans message « saisie ».
        self.verifier_bandeau_non_responsable(self.page)
        self.assertEqual([t for t in self.page.evaluate("window.__toasts") if "abîmé" in t], [])
        self.assertEqual(self.instantane()["ordres_travail.csv"], fichiers["ordres_travail.csv"])
        # Raison glissée dans une phrase (« …, mais la gamme n'a pas été mise à jour (…) ») : même règle, en court.
        self.assertEqual(self.page.evaluate(RAISON_GAMMES_JS), "fichier abîmé : prévenez le responsable")

        self.aller("#/ot/" + OT_DU_TECHNICIEN, ".ot-fiche .ot-numero")
        self.page.click(".onglet[data-onglet='compte-rendu']")
        self.page.wait_for_selector("#form-compte-rendu [name=compte_rendu]")
        self.page.fill("#form-compte-rendu [name=compte_rendu]", COMPTE_RENDU)
        self.page.select_option("#form-compte-rendu [name=cause_code]", "C01")
        self.page.check("#form-compte-rendu [name=remise_service]")
        saisie = self.page.evaluate(SAISIE_COMPTE_RENDU_JS)
        self.assertEqual((saisie["compte_rendu"], saisie["cause_code"], saisie["remise_service"], saisie["statut"]),
                         (COMPTE_RENDU, "C01", True, "En cours"), saisie)

        for bouton in ("#form-compte-rendu button[type=submit]",
                       "#form-compte-rendu button[data-action='transition'][data-cible='Clôturé techniquement']"):
            with self.subTest(bouton=bouton):
                debut = self.nombre_de_toasts(self.page)
                self.page.click(bouton)
                self.verifier_message_non_responsable(self.toast_apres(self.page, debut, "abîmé"))
                self.page.wait_for_function("() => !document.querySelector('#form-compte-rendu button[type=submit]')"
                                            ".disabled")
                self.assertEqual(self.page.evaluate(SAISIE_COMPTE_RENDU_JS), saisie,
                                 "saisie du compte rendu perdue ou changée après le refus")
                self.page.wait_for_load_state("networkidle")
                self.assertEqual(self.instantane()["ordres_travail.csv"], fichiers["ordres_travail.csv"])


# ---------------------------------------------------------------------------
# d. Responsable : « Modifier l'équipement », equipements.csv abîmé (mode dossier)
# ---------------------------------------------------------------------------

class TestResponsableDossier(CasSaisieGardee):

    def setUp(self):
        super().setUp()
        self.demarrer_statique()

    def test_modification_d_equipement_sur_fichier_abime_message_du_responsable_saisie_gardee(self):
        fichiers = fichiers_du_jeu("f3-v1.2.0")
        fichiers["equipements.csv"] = avec_valeur_en_trop(fichiers["equipements.csv"])
        self.ouvrir_dossier(fichiers, "responsable")
        bandeaux = [b for b in self.page.evaluate(BANDEAUX_JS) if "abîmé" in b]
        self.assertEqual(len(bandeaux), 1, bandeaux)
        self.assertIn("Fichier abîmé : equipements.csv, repéré aujourd'hui.", bandeaux[0])
        debut = self.nombre_de_toasts(self.page)
        self.remplir_equipement(DESIGNATION)
        toast = self.toast_apres(self.page, debut, "abîmé")
        self.assertEqual(toast, message_du_responsable("equipements.csv"))
        self.page.wait_for_function("() => !document.querySelector('#parc-formulaire button[type=submit]').disabled")
        self.assertEqual(self.page.input_value("#parc-formulaire [name=designation]"), DESIGNATION)
        self.assertEqual(self.page.evaluate("location.hash"), "#/equipement/%s/modifier" % EQUIPEMENT)
        self.page.wait_for_load_state("networkidle")
        self.assertEqual(self.instantane()["equipements.csv"], fichiers["equipements.csv"])
        raison = self.page.evaluate(RAISON_GAMMES_JS)
        self.assertTrue(raison.startswith("fichier abîmé (gammes.csv), rien n'y a été enregistré"), raison)
        self.assertIn("sauvegarde du jour", raison)
        self.assertNotIn("prévenez", raison)


if __name__ == "__main__":
    unittest.main()
