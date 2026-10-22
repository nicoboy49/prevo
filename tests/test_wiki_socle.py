"""Socle du lot 6 (tâche T95, ARCHITECTURE.md §20.1 et §20.2) : wiki de maintenance.

    routes   : #/wiki et #/wiki/<équipement> ouverts aux trois profils, entrée « Wiki » du menu avec son
               icône, entre Parc et Magasin ; le module Wiki et ses seuils (D100) existent ;
    format 3 : la démo porte version_schema = 3 et la table wiki_syntheses (12 synthèses livrées depuis le lot 6,
               §20.8) ; l'export ZIP la contient (en-tête exact, une ligne par synthèse) ;
    contrôle : Donnees.problemes() signale un OT cité inexistant ou d'un autre équipement, une synthèse
               validée sans validateur, deux synthèses en cours pour un équipement ; une synthèse
               correcte ne donne aucun problème ;
    API      : Indicateurs.datePanne est publique (date de la DI d'origine, sinon création de l'OT).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_wiki_socle.py" -v
"""
import unittest
import zipfile

from commun import CasNavigateur, attendre_pret, preregler_profil, url_fichier

BOM = b"\xef\xbb\xbf"
ENTETE_WIKI = b"id;equipement_id;texte;ot_cites;ot_sources;statut;modele;date_proposition;corrigee_par;" \
              b"date_modification;valide_par;date_validation\r\n"
# Profil : (type, nom, technicienId) ; un technicien choisit sa fiche, un demandeur donne son nom.
PROFILS = {"demandeur": ("Lucie Martin", ""), "technicien": ("", "TEC-0001"), "responsable": ("", "")}

# Écrit des synthèses dans la base de démo (en mémoire) et rend les problèmes de la table.
ECRIRE_ET_CONTROLER = """async (lignes) => {
  await Donnees.modifier('wiki_syntheses', (table) => { lignes.forEach((l) => table.push(l)); return true; },
    { action: 'test du socle' });
  return Donnees.problemes().filter((p) => p.table === 'wiki_syntheses')
    .map((p) => ({ gravite: p.gravite, id: p.id, champ: p.champ, valeur: p.valeur, message: p.message }));
}"""

# Deux OT clôturés de deux équipements différents, dans la démo ; le premier est d'un équipement qui n'a pas
# encore de synthèse (la démo en livre 12, §20.8).
DEUX_OT = """() => {
  const avecSynthese = new Set(Donnees.lignes('wiki_syntheses').map((s) => s.equipement_id));
  const clos = Donnees.lignes('ordres_travail').filter((ot) => /^Clôturé/.test(ot.statut));
  const premier = clos.find((ot) => !avecSynthese.has(ot.equipement_id));
  const autre = clos.find((ot) => ot.equipement_id !== premier.equipement_id);
  return { equipement: premier.equipement_id, ot: premier.id, autreOt: autre.id };
}"""


def synthese(identifiant, equipement, **champs):
    ligne = {"id": identifiant, "equipement_id": equipement, "texte": "", "ot_cites": "", "ot_sources": "",
             "statut": "à valider", "modele": "faux", "date_proposition": "2026-10-19 09:00",
             "corrigee_par": "", "date_modification": "", "valide_par": "", "date_validation": ""}
    ligne.update(champs)
    return ligne


class TestWikiSocle(CasNavigateur):

    def ouvrir_demo(self, profil="responsable"):
        nom, technicien = PROFILS[profil]
        preregler_profil(self.contexte, profil, nom, technicien)
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)

    def verifier_routes_et_menu(self, profil):
        self.ouvrir_demo(profil)
        page = self.page
        lien = page.locator('#menu a[data-ecran="wiki"]')
        self.assertEqual(lien.count(), 1)
        self.assertEqual(lien.get_attribute("href"), "#/wiki")
        self.assertEqual(lien.locator("svg.icone").count(), 1)
        page.evaluate("location.hash = '#/wiki'")
        page.wait_for_selector(".wiki-liste", state="attached")
        self.assertEqual(page.inner_text("#contenu h1").strip(), "Wiki de maintenance")
        page.evaluate("location.hash = '#/wiki/EQ-0001'")
        page.wait_for_selector(".wiki-page", state="attached")
        self.assertEqual(lien.get_attribute("aria-current"), "page")

    def test_routes_et_menu_demandeur(self):
        self.verifier_routes_et_menu("demandeur")

    def test_routes_et_menu_technicien(self):
        self.verifier_routes_et_menu("technicien")

    def test_routes_et_menu_responsable(self):
        self.verifier_routes_et_menu("responsable")

    def test_entree_du_menu_entre_parc_et_magasin(self):
        self.ouvrir_demo("responsable")
        ordre = self.page.evaluate("Array.from(document.querySelectorAll('#menu a')).map((a) => a.dataset.ecran)")
        self.assertLess(ordre.index("parc"), ordre.index("wiki"))
        self.assertLess(ordre.index("wiki"), ordre.index("magasin"))

    def test_module_et_seuils(self):
        self.ouvrir_demo("technicien")
        self.assertEqual(self.page.evaluate("Wiki.SEUILS"), {
            "otMinimum": 5, "otEnvoyesMax": 40, "pucesMax": 6, "motsMax": 150, "recidiveJours": 30,
            "dernieres": 10, "symptomesMax": 5})
        self.assertTrue(self.page.evaluate("Object.isFrozen(Wiki.SEUILS)"))

    def test_demo_au_format_3_syntheses_livrees_et_export_zip(self):
        self.ouvrir_demo("responsable")
        self.assertEqual(self.page.evaluate("Donnees.parametre('version_schema')"), "3")
        self.assertEqual(self.page.evaluate("Schema.version"), 3)
        self.assertEqual(self.page.evaluate("Donnees.lignes('wiki_syntheses').length"), 12)
        self.assertEqual(self.page.evaluate("Donnees.problemes().filter((p) => p.table === 'wiki_syntheses').length"), 0)
        with self.page.expect_download() as attente:
            self.page.click("#btn-export-accueil")
        with zipfile.ZipFile(attente.value.path()) as archive:
            noms = [n for n in archive.namelist() if n.endswith(".csv")]
            self.assertEqual(len(noms), 23)
            contenu = archive.read("wiki_syntheses.csv")
            self.assertTrue(contenu.startswith(BOM + ENTETE_WIKI))
            self.assertEqual(contenu.count(b"\r\nWIKI-"), 12)

    def test_problemes_de_la_table_des_syntheses(self):
        self.ouvrir_demo("responsable")
        cas = self.page.evaluate(DEUX_OT)
        equipement, ot, autre_ot = cas["equipement"], cas["ot"], cas["autreOt"]

        # Une synthèse correcte (validée, avec son validateur, OT de l'équipement) : aucun problème.
        correcte = synthese("WIKI-9001", equipement, ot_cites=ot, ot_sources=ot, statut="validée",
                            valide_par="Responsable", date_validation="2026-10-19 10:00")
        self.assertEqual(self.page.evaluate(ECRIRE_ET_CONTROLER, [correcte]), [])

        # Puis trois défauts : OT inventé, OT d'un autre équipement, validée sans validateur, et une
        # seconde synthèse en cours pour le même équipement.
        fautive = synthese("WIKI-9002", equipement, ot_cites="OT-1999-9999", ot_sources=autre_ot,
                           statut="validée")
        problemes = self.page.evaluate(ECRIRE_ET_CONTROLER, [fautive])
        self.assertTrue(all(p["gravite"] == "attention" for p in problemes), problemes)
        self.assertEqual(sorted((p["id"], p["champ"], p["valeur"]) for p in problemes), sorted([
            ("WIKI-9002", "ot_cites", "OT-1999-9999"),
            ("WIKI-9002", "ot_sources", autre_ot),
            ("WIKI-9002", "valide_par", ""),
            ("WIKI-9002", "statut", "validée"),
        ]))
        messages = " ".join(p["message"] for p in problemes)
        self.assertIn("n'existe pas", messages)
        self.assertIn("est celui d'un autre équipement", messages)
        self.assertIn("déjà une synthèse en cours (WIKI-9001)", messages)

        # Une synthèse remplacée ne compte pas comme « en cours ».
        remplacee = synthese("WIKI-9003", equipement, ot_cites=ot, ot_sources=ot, statut="remplacée")
        problemes = self.page.evaluate(ECRIRE_ET_CONTROLER, [remplacee])
        self.assertFalse([p for p in problemes if p["id"] == "WIKI-9003"], problemes)

    def test_date_panne_publique(self):
        self.ouvrir_demo("responsable")
        resultat = self.page.evaluate("""() => {
          const ordres = Donnees.lignes('ordres_travail');
          const demandes = Donnees.lignes('demandes');
          const avecDi = ordres.find((ot) => ot.di_id && demandes.some((di) => di.id === ot.di_id));
          const sansDi = ordres.find((ot) => !ot.di_id && !demandes.some((di) => di.ot_id === ot.id));
          const ctx = Indicateurs.contexte();
          return {
            avecDi: Indicateurs.datePanne(avecDi), diDate: demandes.find((di) => di.id === avecDi.di_id).date_heure,
            sansDi: Indicateurs.datePanne(sansDi), creation: sansDi.date_creation,
            avecContexte: Indicateurs.datePanne(avecDi, ctx),
          };
        }""")
        self.assertEqual(resultat["avecDi"], resultat["diDate"])
        self.assertEqual(resultat["avecContexte"], resultat["diDate"])
        self.assertEqual(resultat["sansDi"], resultat["creation"])


if __name__ == "__main__":
    unittest.main()
