"""Catalogue des contrôles et des habilitations chargé par l'application (2.2, T410 ; CONCEPTION-L2-L3 §1.2, §1.5).

js/catalogue/fr.js (T400, window.CatalogueFR) est chargé par index.html juste après js/formats.js, avec les cinq
modules nouveaux des lots L2 et L3 (vides en T410). Vérifié dans l'application elle-même, en démo (index.html en
file://, en français puis en anglais) et en mode serveur (serveur.py sur une COPIE du jeu de démo) :
  - window.CatalogueFR a 31 contrôles et 15 habilitations, les lignes de docs/catalogue/*.json telles quelles (plus
    la mention calculée), en français quelle que soit la langue de l'interface (CDC §3.2) ;
  - tout est gelé : aucun objet du catalogue ne peut être changé, ni une ligne ajoutée ;
  - le catalogue est chargé juste après js/formats.js, les cinq modules nouveaux sont chargés, l'application arrive
    à l'état « prêt » ; aucune erreur dans la console (CasNavigateur fait échouer le test sinon).

Bibliothèque standard + Playwright. Lancer depuis la racine du projet (au travers du verrou des navigateurs) :
    py -X utf8 -m unittest discover -s tests -p "test_catalogue_controles.py" -v
"""
import json
import unittest

from commun import RACINE, CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, url_fichier

EFFECTIFS = {"controles": 31, "habilitations": 15}
SCRIPT_CATALOGUE = "js/catalogue/fr.js"
MODULES_NOUVEAUX = ["controles-reserves.js", "controles-catalogue.js", "controles-reserves-ecrans.js",
                    "equipe-habilitations.js", "ordres-habilitations.js"]

# Relevé fait dans la page : le catalogue (copie JSON), son gel (chaque objet, à toute profondeur), des écritures
# essayées (refusées), les scripts de la page et les objets des modules complétés par les fichiers nouveaux.
RELEVE_JS = """() => {
  const catalogue = window.CatalogueFR;
  const tousGeles = (valeur) => {
    if (!valeur || typeof valeur !== 'object') return true;
    return Object.isFrozen(valeur) && Object.keys(valeur).every((cle) => tousGeles(valeur[cle]));
  };
  let ecrituresRefusees = false;
  let ajoutRefuse = false;
  if (catalogue && catalogue.controles.length && catalogue.habilitations.length) {
    const controle = catalogue.controles[0];
    const habilitation = catalogue.habilitations[0];
    ecrituresRefusees = !Reflect.set(catalogue, 'controles', [])
      && !Reflect.set(catalogue.controles, 'length', 0)
      && !Reflect.set(controle, 'nature', 'modifiée')
      && !Reflect.set(controle.liens[0], 'url', 'https://exemple.invalid/')
      && !Reflect.set(habilitation, 'duree_mois', 1)
      && !Reflect.deleteProperty(controle, 'reference')
      && controle.nature !== 'modifiée' && catalogue.controles.length > 0;
    try { catalogue.habilitations.push({ id: 'H99' }); } catch (erreur) { ajoutRefuse = erreur instanceof TypeError; }
  }
  return {
    present: !!catalogue && typeof catalogue === 'object',
    contenu: catalogue ? JSON.parse(JSON.stringify(catalogue)) : null,
    geles: !!catalogue && tousGeles(catalogue),
    ecrituresRefusees: ecrituresRefusees,
    ajoutRefuse: ajoutRefuse,
    langue: document.documentElement.lang,
    scripts: Array.from(document.scripts).map((script) => script.getAttribute('src')).filter(Boolean),
    objets: [typeof Controles, typeof Equipe, typeof Ordres],
  };
}"""


def lignes_du_depot(nom):
    """Lignes de docs/catalogue/<nom>-fr.json (source du fichier généré js/catalogue/fr.js)."""
    with open(RACINE / "docs" / "catalogue" / (nom + "-fr.json"), encoding="utf-8") as fichier:
        return json.load(fichier)["lignes"]


class CasCatalogue(CasNavigateur):

    def verifier_catalogue(self, langue="fr"):
        releve = self.page.evaluate(RELEVE_JS)
        self.assertTrue(releve["present"], "window.CatalogueFR absent de l'application")
        self.assertEqual(releve["langue"], langue)
        for nom, effectif in EFFECTIFS.items():
            with self.subTest(liste=nom):
                lignes = releve["contenu"][nom]
                self.assertEqual(len(lignes), effectif)
                # Les lignes du dépôt telles quelles (françaises dans toutes les langues), plus la mention calculée.
                for chargee, attendue in zip(lignes, lignes_du_depot(nom)):
                    self.assertEqual(sorted(chargee), sorted(list(attendue) + ["mention"]), attendue["id"])
                    self.assertEqual({cle: chargee[cle] for cle in attendue}, attendue)
        self.assertEqual(sorted(releve["contenu"]), sorted(EFFECTIFS))
        self.assertTrue(releve["geles"], "un objet du catalogue n'est pas gelé")
        self.assertTrue(releve["ecrituresRefusees"], "une écriture dans le catalogue a été acceptée")
        self.assertTrue(releve["ajoutRefuse"], "une ligne a pu être ajoutée au catalogue")
        # Chargé une fois, juste après le registre des formats ; les cinq modules nouveaux chargés.
        scripts = releve["scripts"]
        self.assertEqual(scripts.count(SCRIPT_CATALOGUE), 1)
        self.assertEqual(scripts[scripts.index(SCRIPT_CATALOGUE) - 1], "js/formats.js")
        for module in MODULES_NOUVEAUX:
            with self.subTest(module=module):
                self.assertIn("js/modules/" + module, scripts)
        self.assertEqual(releve["objets"], ["object", "object", "object"])

    def ouvrir_demo(self):
        page = self.page
        page.goto(url_fichier("index.html"))
        page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        page.click("#btn-demo")
        page.wait_for_function("document.documentElement.dataset.etat === 'profil'")
        page.click("#profil-responsable")
        attendre_pret(page)


class TestCatalogueDemo(CasCatalogue):
    """Démo : index.html en file:// (aucun serveur), les données de démo en mémoire."""

    def test_catalogue_charge_et_gele_en_demo(self):
        self.ouvrir_demo()
        self.verifier_catalogue()

    def test_catalogue_en_francais_quand_l_interface_est_en_anglais(self):
        self.contexte.add_init_script(
            "try { if (localStorage.getItem('prevo.langue') === null) localStorage.setItem('prevo.langue', 'en'); }"
            " catch (erreur) { /* page sans stockage */ }")
        self.ouvrir_demo()
        self.verifier_catalogue(langue="en")


class TestCatalogueServeur(CasCatalogue):
    """Mode serveur : serveur.py sur une copie du jeu de démo (jamais donnees/ réel)."""

    def test_catalogue_charge_et_gele_en_mode_serveur(self):
        with ServeurPrevo() as serveur:
            preregler_profil(self.contexte, "responsable", nom="Responsable")
            self.page.goto(serveur.url + "/")
            attendre_pret(self.page)
            # Les écritures du démarrage (OT préventifs échus) sont finies avant le relevé.
            self.page.wait_for_load_state("networkidle")
            self.verifier_catalogue()


if __name__ == "__main__":
    unittest.main()
