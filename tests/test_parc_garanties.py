"""Garanties et contrats sur la fiche équipement, 2.2 L4 (T458 ; CS173 ; conception L4-L5-L6 §2.3 et §2.4).

Technicien et responsable voient, sur la fiche d'un équipement sous garantie de la démo (rôle garantie_en_cours), le badge
« Sous garantie jusqu'au … » à côté de la criticité et la carte « Garanties et contrats » sous la carte des contrôles ;
le demandeur ne reçoit rien (ni badge, ni carte, ni tables). Jamais de montant. Équipement sans garantie : pas de badge,
carte « vide ». Lien « Ajouter une garantie » pour le responsable seul. Tests en mode serveur sur une copie de la démo.

Lancer depuis la racine du projet (au travers du verrou des navigateurs) :
    py -X utf8 -m unittest discover -s tests -p "test_parc_garanties.py" -v
"""
import csv
import io
import unittest
from pathlib import Path

from commun import CasNavigateur, RACINE, ServeurPrevo, attendre_pret, preregler_profil, scenarios_demo

DOSSIER_DEMO = RACINE / "donnees" / "demo"
BADGE = "#contenu .parc-badges-fiche .garanties-badge-equipement"
CARTE = "#contenu .garanties-carte-equipement"


def lire(dossier, table):
    texte = (Path(dossier) / (table + ".csv")).read_bytes().decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte, newline=""), delimiter=";"))


class TestParcGaranties(CasNavigateur):

    def ouvrir(self, serveur, identifiant, profil, technicien_id=""):
        nom = "Demandeur test" if profil == "demandeur" else ""
        preregler_profil(self.contexte, profil, nom=nom, technicien_id=technicien_id)
        self.page.goto(serveur.url + "/#/equipement/" + identifiant)
        # preregler_profil n'écrase rien : on pose le profil voulu, puis on recharge pour le lire
        self.page.evaluate("([t, n, id]) => localStorage.setItem('prevo.profil', JSON.stringify({type: t, nom: n, "
                           "technicienId: id}))", [profil, nom, technicien_id])
        self.page.reload()
        attendre_pret(self.page)
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_function(
            "(id) => { const dd = document.querySelector('#contenu .parc .valeurs dd');"
            " return dd !== null && dd.textContent.trim() === id; }", arg=identifiant)

    def jeu(self, dossier):
        garantie = next(g for g in lire(dossier, "garanties") if g["id"] == scenarios_demo()["garantie_en_cours"])
        sans = next(e["id"] for e in lire(dossier, "equipements") if e["actif"] != "0"
                    and not any(g["equipement_id"] == e["id"] for g in lire(dossier, "garanties"))
                    and not any(e["id"] in c.get("equipement_ids", "") for c in lire(dossier, "contrats_prestataires")))
        technicien = next(t["id"] for t in lire(dossier, "techniciens") if t.get("actif") != "0")
        return garantie["equipement_id"], sans, technicien

    def test_technicien_et_responsable_voient_le_badge_et_la_carte(self):
        page = self.page
        with ServeurPrevo() as serveur:
            sous, sans, technicien = self.jeu(serveur.dossier)
            for profil, tech, responsable in (("responsable", "", True), ("technicien", technicien, False)):
                self.ouvrir(serveur, sous, profil, tech)
                self.assertEqual(page.locator(BADGE).count(), 1, profil)
                self.assertIn("Sous garantie jusqu'au", page.inner_text(BADGE), profil)
                self.assertEqual(page.locator(CARTE).count(), 1, profil)
                # La carte suit la carte des contrôles
                self.assertTrue(page.evaluate(
                    "() => document.querySelector('.parc-controles').nextElementSibling"
                    ".classList.contains('garanties-carte-equipement')"), profil)
                self.assertEqual(page.locator(CARTE + " #garanties-ajouter-garantie").count(), 1 if responsable else 0, profil)
                texte = page.inner_text(CARTE)
                self.assertNotIn("€", texte, profil)
                self.assertNotIn("CHF", texte, profil)
                self.ouvrir(serveur, sans, profil, tech)
                self.assertEqual(page.locator(BADGE).count(), 0, profil)
                self.assertEqual(page.locator(CARTE).count(), 1, profil)
                self.assertIn("Aucune garantie ni aucun contrat", page.inner_text(CARTE), profil)

    def test_le_demandeur_ne_voit_rien(self):
        page = self.page
        with ServeurPrevo() as serveur:
            sous, _, _ = self.jeu(serveur.dossier)
            self.ouvrir(serveur, sous, "demandeur")
            self.assertEqual(page.locator(BADGE).count(), 0)
            self.assertEqual(page.locator(CARTE).count(), 0)
            contenu = page.inner_text("#contenu")
            self.assertNotIn("garantie", contenu.lower())

    def test_aucune_ligne_nouvelle_ne_cite_le_wiki(self):
        source = (RACINE / "js" / "modules" / "parc-fiche.js").read_text(encoding="utf-8")
        garanties = [l for l in source.splitlines() if "Garanties" in l and "wiki" in l.lower()]
        self.assertEqual(garanties, [])
        self.assertIn("Garanties.carteEquipement", source)


if __name__ == "__main__":
    unittest.main()
