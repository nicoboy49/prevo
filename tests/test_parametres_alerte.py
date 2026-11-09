"""Tests du délai d'alerte des garanties et des contrats de prestataires dans Paramètres (T454 ; D187, CS173).

    découpage : le tableau des réglages vit dans js/modules/parametres-reglages.js (ParametresReglages.REGLAGES,
                gelé), chargé juste avant parametres.js ; Parametres.reglagesConnus() en rend une copie, que l'import
                ZIP lit pour garder les réglages absents du ZIP (T319) ;
    réglage   : alerte_echeances_jours, section « Garanties et contrats », libellé « Alerte avant l'échéance
                (jours) », aide de la conception L4 §2.3, 60 quand la clé manque ; hors de 1 à 365, vide ou non
                entier : refusé sous le champ, fichier inchangé ;
    effet     : à 30, écrit dans parametres.csv et relu après rechargement ; Garanties.delaiAlerte() rend 30 et le
                contrat de CS173 (fin 31/12/2026, préavis 3 mois, reconduction tacite) devient « à décider » le
                31/08/2026 (« en cours » le 30/08) ; à 60, il l'était dès le 01/08/2026.

Données : copie temporaire du jeu de démo servie par serveur.py (ServeurPrevo) ; le contrat de CS173 est écrit dans ce
fichier et passé aux règles pures (aucune donnée réelle).

Lancer depuis la racine du projet (navigateur : au travers du verrou) :
    py -X utf8 -m unittest discover -s tests -p "test_parametres_alerte.py" -v
"""
import csv
import unittest

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil

FORMULAIRE = "#form-parametres "
CHAMP = FORMULAIRE + "[name=alerte_echeances_jours]"
BLOC = FORMULAIRE + ".champ[data-champ='alerte_echeances_jours']"
AIDE = ("Garanties : avant la date de fin. Contrats : avant la date limite de résiliation (fin − préavis). "
        "Sert à l'accueil et à l'écran « Garanties et contrats ».")

# CS173 : contrat fini le 31/12/2026, préavis 3 mois, reconduit tacitement (date limite de résiliation le 30/09/2026).
CONTRAT_CS173 = {"id": "CTP-0001", "fournisseur_id": "FOU-0001", "objet": "Maintenance des compresseurs",
                 "date_debut": "2026-01-01", "date_fin": "2026-12-31", "preavis_mois": "3", "reconduction_tacite": "1",
                 "reconduction_mois": "12", "montant_annuel": "4800", "actif": "1"}
ETAT_CONTRAT_JS = "([contrat, jour]) => { const e = Garanties.etatContrat(contrat, jour); return [e.statut, e.dateLimite]; }"


def valeurs_parametres(chemin):
    """{ clé : valeur } de parametres.csv, sans l'apostrophe de protection d'Excel."""
    with open(chemin, encoding="utf-8-sig", newline="") as fichier:
        lignes = list(csv.DictReader(fichier, delimiter=";"))
    return {ligne["cle"]: ligne["valeur"][1:] if ligne["valeur"].startswith("'") else ligne["valeur"]
            for ligne in lignes}


class CasAlerte(CasNavigateur):

    def ouvrir_parametres(self, serveur):
        preregler_profil(self.contexte, "responsable")
        self.page.goto(serveur.url + "/#/parametres")
        attendre_pret(self.page)
        self.page.wait_for_selector(CHAMP)
        return self.page

    def etat_contrat(self, jour):
        return self.page.evaluate(ETAT_CONTRAT_JS, [CONTRAT_CS173, jour])


class TestReglagesSortis(CasAlerte):

    def test_reglages_dans_leur_fichier_et_connus_de_l_import_zip(self):
        with ServeurPrevo() as serveur:
            page = self.ouvrir_parametres(serveur)
            lu = page.evaluate("""() => {
              const reglage = ParametresReglages.REGLAGES.find((r) => r.cle === 'alerte_echeances_jours');
              const connus = Parametres.reglagesConnus();
              connus.pop();
              return {
                gele: Object.isFrozen(ParametresReglages.REGLAGES),
                memes: Parametres.reglagesConnus().map((r) => r.cle).join() === ParametresReglages.REGLAGES.map((r) => r.cle).join(),
                copie: Parametres.reglagesConnus().length === ParametresReglages.REGLAGES.length && connus.length === ParametresReglages.REGLAGES.length - 1,
                connu: Parametres.reglagesConnus().some((r) => r.cle === 'alerte_echeances_jours'),
                reglage: { type: reglage.type, defaut: reglage.defaut, min: reglage.min, max: reglage.max, libelle: reglage.libelle,
                           section: reglage.section, aide: reglage.aide, horsFormulaire: Boolean(reglage.horsFormulaire) },
              };
            }""")
            self.assertTrue(lu["gele"])
            self.assertTrue(lu["memes"])
            self.assertTrue(lu["copie"])                     # une copie : la retoucher ne change pas les réglages
            self.assertTrue(lu["connu"])                     # import ZIP (T319) : gardé de la base s'il manque au ZIP
            self.assertEqual(lu["reglage"], {"type": "entier", "defaut": "60", "min": 1, "max": 365,
                                             "libelle": "Alerte avant l'échéance (jours)",
                                             "section": "Garanties et contrats", "aide": AIDE, "horsFormulaire": False})


class TestReglageAlerte(CasAlerte):

    def test_section_libelle_aide_et_defaut_quand_la_cle_manque(self):
        with ServeurPrevo() as serveur:
            self.assertNotIn("alerte_echeances_jours", valeurs_parametres(serveur.dossier / "parametres.csv"))
            page = self.ouvrir_parametres(serveur)
            self.assertEqual(page.input_value(CHAMP), "60")
            self.assertEqual(page.inner_text(BLOC + " label.libelle").strip(), "Alerte avant l'échéance (jours)")
            self.assertEqual(page.inner_text(BLOC + " p.aide").strip(), AIDE)
            # L'intertitre de la section est juste au-dessus du champ, seul de sa section.
            voisins = page.evaluate("""(selecteur) => {
              const bloc = document.querySelector(selecteur);
              const avant = bloc.previousElementSibling, apres = bloc.nextElementSibling;
              return [avant.tagName, avant.textContent.trim(), apres.tagName, apres.textContent.trim()];
            }""", BLOC)
            self.assertEqual(voisins[:2], ["H3", "Garanties et contrats"])
            self.assertEqual(voisins[2:], ["H3", "Assistant IA"])
            self.assertEqual(page.evaluate("Garanties.delaiAlerte()"), 60)

    def test_hors_de_1_a_365_ou_non_entier_refuse_sous_le_champ(self):
        with ServeurPrevo() as serveur:
            chemin = serveur.dossier / "parametres.csv"
            page = self.ouvrir_parametres(serveur)
            avant = chemin.read_bytes()
            for valeur in ("0", "366", "6,5", "", "-5"):
                with self.subTest(valeur=valeur):
                    page.fill(CHAMP, valeur)
                    # la marque d'erreur du tour précédent est retirée : celle qu'on attend vient de ce clic
                    page.evaluate("(s) => document.querySelector(s).classList.remove('en-erreur')", BLOC)
                    page.click(FORMULAIRE + "button[type=submit]")
                    page.wait_for_selector(BLOC + ".en-erreur")
                    self.assertTrue(page.inner_text(BLOC + " .erreur-champ").strip())
                    self.assertEqual(chemin.read_bytes(), avant)
            for valeur in ("1", "365"):                      # les bornes sont permises
                with self.subTest(valeur=valeur):
                    page.fill(CHAMP, valeur)
                    page.click(FORMULAIRE + "button[type=submit]")
                    page.wait_for_function("(v) => Donnees.parametre('alerte_echeances_jours', '') === v", arg=valeur)
                    self.assertEqual(valeurs_parametres(chemin)["alerte_echeances_jours"], valeur)

    def test_reglage_a_30_deplace_l_alerte_du_contrat_cs173_au_31_08_2026(self):
        with ServeurPrevo() as serveur:
            chemin = serveur.dossier / "parametres.csv"
            page = self.ouvrir_parametres(serveur)
            # Délai par défaut (60) : « à décider » dès le 01/08/2026, 60 jours avant la date limite du 30/09/2026.
            self.assertEqual(self.etat_contrat("2026-07-31"), ["en_cours", "2026-09-30"])
            self.assertEqual(self.etat_contrat("2026-08-01"), ["a_decider", "2026-09-30"])
            page.fill(CHAMP, "30")
            page.click(FORMULAIRE + "button[type=submit]")
            page.wait_for_function("document.getElementById('toast').textContent.includes('Paramètres enregistrés')")
            valeurs = valeurs_parametres(chemin)
            self.assertEqual(valeurs["alerte_echeances_jours"], "30")
            self.assertEqual(valeurs["delai_p2_h"], "24")                         # le reste n'a pas bougé
            self.assertEqual(page.evaluate("Garanties.delaiAlerte()"), 30)
            self.assertEqual(self.etat_contrat("2026-08-01"), ["en_cours", "2026-09-30"])
            self.assertEqual(self.etat_contrat("2026-08-30"), ["en_cours", "2026-09-30"])
            self.assertEqual(self.etat_contrat("2026-08-31"), ["a_decider", "2026-09-30"])
            self.assertEqual(self.etat_contrat("2026-09-30"), ["a_decider", "2026-09-30"])
            self.assertEqual(self.etat_contrat("2026-10-01"), ["preavis_depasse", "2026-09-30"])
            # Relu après rechargement (depuis le fichier)
            page.reload()
            attendre_pret(page)
            page.wait_for_selector(CHAMP)
            self.assertEqual(page.input_value(CHAMP), "30")
            self.assertEqual(page.evaluate("Garanties.delaiAlerte()"), 30)
            self.assertEqual(self.etat_contrat("2026-08-31"), ["a_decider", "2026-09-30"])


if __name__ == "__main__":
    unittest.main()
