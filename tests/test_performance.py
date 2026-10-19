"""Performance du lot 1 sur un jeu de charge (tâche T18, brief CS20).

Jeu de charge : 500 équipements, 5 000 OT (outils/generer_demo.py --volume 500,5000 --sans-js),
servi par serveur.py (ServeurPrevo), profil responsable préréglé. Deux budgets, médiane de
trois mesures :
    chargement complet : performance.getEntriesByName('prevo:pret')[0].startTime, compté depuis
                         le début de la navigation (contexte neuf à chaque mesure : cache vide) ;
                         budget 2 000 ms ;
    création d'une DI  : du clic sur « Envoyer » à l'affichage de la confirmation, mesuré dans la
                         page (performance.now()) ; budget 1 000 ms.
Les mesures sont affichées.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_performance.py" -v
"""
import shutil
import statistics
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from commun import RACINE, CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil

BUDGET_CHARGEMENT_MS = 2000
BUDGET_CREATION_DI_MS = 1000
MESURES = 3

# Chronomètre posé dans la page : t0 au clic sur « Envoyer » (phase de capture, avant le
# gestionnaire du module), t1 quand la confirmation (.di-numero) apparaît dans #contenu.
CHRONO_DI_JS = """() => {
  window.__chrono = { t0: null, t1: null };
  document.addEventListener('click', (e) => {
    if (e.target.closest('.di-envoyer') && window.__chrono.t0 === null) window.__chrono.t0 = performance.now();
  }, true);
  const observateur = new MutationObserver(() => {
    if (window.__chrono.t0 !== null && window.__chrono.t1 === null && document.querySelector('#contenu .di-numero')) {
      window.__chrono.t1 = performance.now();
      observateur.disconnect();
    }
  });
  observateur.observe(document.getElementById('contenu'), { childList: true, subtree: true });
}"""


class TestPerformance(CasNavigateur):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dossier_charge = Path(tempfile.mkdtemp(prefix="prevo-charge-"))
        cls.addClassCleanup(shutil.rmtree, cls.dossier_charge, True)
        sortie = cls.dossier_charge / "donnees"
        resultat = subprocess.run(
            [sys.executable, str(RACINE / "outils" / "generer_demo.py"), "--volume", "500,5000",
             "--sortie", str(sortie), "--sans-js"],
            cwd=str(RACINE), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=600)
        if resultat.returncode != 0:
            raise RuntimeError("generer_demo.py a échoué :\n" + resultat.stdout.decode("utf-8", "replace"))
        cls.serveur = ServeurPrevo(source=sortie)
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)

    def nouvelle_page(self):
        """Contexte neuf (cache vide), profil responsable préréglé."""
        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
        self.addCleanup(contexte.close)
        contexte.set_default_timeout(30000)
        preregler_profil(contexte, "responsable")
        page = contexte.new_page()
        self.surveiller(page)
        return page

    def test_volume_du_jeu_de_charge(self):
        page = self.nouvelle_page()
        page.goto(self.serveur.url + "/")
        attendre_pret(page, 30000)
        volumes = page.evaluate("[Donnees.lignes('equipements').length, Donnees.lignes('ordres_travail').length]")
        self.assertGreaterEqual(volumes[0], 500)
        self.assertGreaterEqual(volumes[1], 5000)

    def test_chargement_complet_median_sous_2_secondes(self):
        mesures = []
        for _ in range(MESURES):
            page = self.nouvelle_page()
            page.goto(self.serveur.url + "/")
            attendre_pret(page, 30000)
            mesures.append(page.evaluate("performance.getEntriesByName('prevo:pret')[0].startTime"))
            page.context.close()
        mediane = statistics.median(mesures)
        print("\n  [performance] chargement complet (500 équipements, 5000 OT) : %s ms -> médiane %.0f ms (budget %d)"
              % (", ".join("%.0f" % m for m in mesures), mediane, BUDGET_CHARGEMENT_MS))
        self.assertLess(mediane, BUDGET_CHARGEMENT_MS)

    def test_creation_di_mediane_sous_1_seconde(self):
        page = self.nouvelle_page()
        page.goto(self.serveur.url + "/")
        attendre_pret(page, 30000)
        equipement = page.evaluate("Donnees.lignes('equipements').find((e) => e.actif !== '0').id")
        mesures = []
        for numero in range(MESURES):
            page.evaluate("(id) => { location.hash = '#/di/nouvelle?equipement=' + encodeURIComponent(id); }", equipement)
            page.wait_for_selector(".di-formulaire .selecteur-choisi")
            page.fill("input[name=symptome]", "Mesure de performance %d" % (numero + 1))
            page.click("label.tuile:has(input[value='gêne'])")
            page.evaluate(CHRONO_DI_JS)
            page.click(".di-envoyer")
            page.wait_for_function("window.__chrono.t1 !== null", timeout=30000)
            mesures.append(page.evaluate("window.__chrono.t1 - window.__chrono.t0"))
            page.evaluate("location.hash = '#/accueil'")
            page.wait_for_function("document.querySelector('#contenu .di-numero') === null")
        mediane = statistics.median(mesures)
        print("\n  [performance] création de DI (clic -> confirmation) : %s ms -> médiane %.0f ms (budget %d)"
              % (", ".join("%.0f" % m for m in mesures), mediane, BUDGET_CREATION_DI_MS))
        self.assertLess(mediane, BUDGET_CREATION_DI_MS)


if __name__ == "__main__":
    unittest.main()
