"""Rappel « sous garantie » à la création d'un OT correctif (T459, CDC §3.4, CS173).

Mode serveur (jeu de démo copié dans un dossier temporaire), profil responsable. Familles :
    formulaire : #/ot/nouveau, zone .ot-zone-garantie — correctif ou urgence sur un équipement sous garantie : bandeau
                 (revu au changement de type) ; préventif ou équipement sans garantie : rien ; la création n'est pas
                 bloquée et le journal ne dit rien de la garantie ;
    demande    : fenêtre « Accepter » d'une DI — la même ligne pour un équipement sous garantie, rien sinon.

Lancer depuis la racine du projet (navigateur : au travers du verrou) :
    py -X utf8 -m unittest discover -s tests -p "test_ordres_garantie.py" -v
"""
import unittest

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil

ZONE = "#form-nouvel-ot .ot-zone-garantie"


class CasGarantie(CasNavigateur):

    def ouvrir(self, serveur, route):
        preregler_profil(self.contexte, "responsable")
        self.page.goto(serveur.url + "/" + route)
        attendre_pret(self.page)

    def preparer(self):
        """Une garantie en cours sur un équipement ; renvoie [équipement garanti, équipement sans garantie]."""
        return self.page.evaluate("""async () => {
          const ids = Donnees.lignes('equipements').filter((e) => e.actif !== '0').map((e) => e.id);
          const jour = new Date().toISOString().slice(0, 10);
          const libre = ids.find((id) => !Garanties.sousGarantie(id, jour));
          const garanti = ids.find((id) => id !== libre);
          await Garanties.creerGarantie({ equipement_id: garanti, date_fin: '2099-12-31', conditions: 'Pièces couvertes' });
          return [garanti, libre];
        }""")

    def nb_bandeaux(self, zone=ZONE):
        return self.page.locator(zone + " .garanties-rappel").count()


class TestFormulaire(CasGarantie):

    def test_correctif_sous_garantie_bandeau_puis_preventif_rien(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/accueil")
            garanti, _ = self.preparer()
            self.page.evaluate("(id) => { location.hash = '#/ot/nouveau?equipement=' + id; }", garanti)
            self.page.wait_for_selector("#form-nouvel-ot")
            self.page.select_option("#form-nouvel-ot [name=type]", "correctif différé")
            self.assertEqual(self.nb_bandeaux(), 1)
            self.assertIn("Pièces couvertes", self.page.inner_text(ZONE))
            self.page.select_option("#form-nouvel-ot [name=type]", "préventif systématique")
            self.assertEqual(self.nb_bandeaux(), 0)
            self.page.select_option("#form-nouvel-ot [name=type]", "correctif immédiat")
            self.assertEqual(self.nb_bandeaux(), 1)

    def test_equipement_sans_garantie_rien(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/accueil")
            _, libre = self.preparer()
            self.page.evaluate("(id) => { location.hash = '#/ot/nouveau?equipement=' + id; }", libre)
            self.page.wait_for_selector("#form-nouvel-ot")
            self.page.select_option("#form-nouvel-ot [name=type]", "correctif immédiat")
            self.assertEqual(self.nb_bandeaux(), 0)

    def test_urgence_sous_garantie_bandeau_sans_bloquer_la_creation(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/accueil")
            garanti, _ = self.preparer()
            self.page.evaluate("(id) => { location.hash = '#/ot/nouveau?urgence=1&equipement=' + id; }", garanti)
            self.page.wait_for_selector("#form-nouvel-ot")
            self.assertEqual(self.nb_bandeaux(), 1)
            self.page.fill("#form-nouvel-ot [name=titre]", "Fuite d'huile")
            self.page.click("#form-nouvel-ot button[type=submit]")
            self.page.wait_for_selector(".ot-fiche .ot-numero")


class TestDemande(CasGarantie):

    def accepter(self, equipement):
        di = self.page.evaluate("""(id) => Demandes.creer({ equipement_id: id, symptome: 'Fuite', impact: 'dégradé',
            description: 'Flaque.', demandeur: 'Lucie Martin' })""", equipement)
        self.page.evaluate("(di) => { location.hash = '#/di/' + di; }", di)
        self.page.wait_for_selector("[data-decision=accepter]")
        self.page.click("[data-decision=accepter]")
        self.page.wait_for_selector("dialog .di-fenetre-accepter")

    def test_fenetre_accepter_ligne_de_garantie(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/accueil")
            garanti, _ = self.preparer()
            self.accepter(garanti)
            self.assertEqual(self.nb_bandeaux("dialog .di-zone-garantie"), 1)

    def test_fenetre_accepter_equipement_sans_garantie_rien(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/accueil")
            _, libre = self.preparer()
            self.accepter(libre)
            self.assertEqual(self.nb_bandeaux("dialog .di-zone-garantie"), 0)


if __name__ == "__main__":
    unittest.main()
