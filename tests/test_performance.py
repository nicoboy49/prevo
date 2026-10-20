"""Performance sur un jeu de charge (tâches T18 et T35, brief CS20).

Jeu de charge : 500 équipements, 5 000 OT (outils/generer_demo.py --volume 500,5000 --sans-js, avec
gammes, relevés, mouvements de stock et achats en proportion), servi par serveur.py (ServeurPrevo),
profil responsable préréglé. Le générateur crée l'OT de chaque gamme déjà échue à sa date de
référence : pour que l'ouverture ait du travail, VIEILLISSEMENT du jeu, comme après des congés :
les 20 gammes à date sans OT ouvert les plus proches de leur échéance sont rendues échues (échéance
passée à hier). Trois budgets, médiane de trois mesures, toutes affichées :
    chargement complet, génération du préventif comprise :
                         max(prevo:pret, prevo:preventif) (marques de performance comptées depuis
                         le début de la navigation ; contexte neuf à chaque mesure : cache vide) ;
                         le PREMIER chargement génère les OT des gammes échues, les suivants n'en
                         génèrent plus : il est mesuré et affiché à part ; budget 2 000 ms ;
    création d'une DI  : du clic sur « Envoyer » à l'affichage de la confirmation ; budget 1 000 ms ;
    sortie de pièce    : du clic sur « Sortir du stock » (bloc « Pièces sorties » de l'onglet
                         Exécution d'un OT) à l'affichage du bloc mis à jour (net de l'article + 1) ;
                         budget 1 000 ms.
    indicateurs (lot 3) : du changement d'adresse vers #/indicateurs (12 mois) à l'affichage du bandeau
                         et des 7 graphiques (aucune carte « en chargement ») ; la 1re mesure charge
                         ECharts (contexte neuf) ; budget 2 000 ms, chacune des mesures ;
    planning (lot 3)   : du changement d'adresse vers #/planning?semaine=… à l'affichage de la grille
                         (.pl-grille) ; budget 1 000 ms ;
    rapport figé (lot 3) : Rapport.figer(mois) — calcul des indicateurs du mois, de M-1 et de N-1,
                         page HTML avec ses graphiques SVG, écriture du document ; budget 5 000 ms.
Les chronomètres des actions sont posés dans la page (performance.now()).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_performance.py" -v
"""
import csv
import datetime
import io
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
BUDGET_SORTIE_MS = 1000
BUDGET_INDICATEURS_MS = 2000        # lot 3 (CS49) : écran Indicateurs sur 12 mois, ECharts compris
BUDGET_PLANNING_MS = 1000           # lot 3 (CS49) : planning de la semaine affiché
BUDGET_RAPPORT_MS = 5000            # lot 3 (CS49) : rapport figé (calcul, page HTML, écriture)
MESURES = 3
GAMMES_VIEILLIES = 20
STATUTS_FERMES = ("Clôturé techniquement", "Clôturé administrativement", "Annulé")
BOM = "﻿"

# Fin du chargement : la plus tardive des deux marques (prevo:preventif précède normalement
# prevo:pret, mais la mesure ne doit pas dépendre de cet ordre).
CHARGEMENT_JS = """() => Math.max(...['prevo:pret', 'prevo:preventif'].map((nom) => {
  const marques = performance.getEntriesByName(nom);
  return marques.length ? marques[0].startTime : Infinity;
}))"""

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

# Sortie de pièce : t0 au clic sur « Sortir du stock », t1 quand le bloc « Pièces sorties » montre le
# net attendu pour l'article (la fiche de l'OT est réaffichée après l'écriture).
CHRONO_SORTIE_JS = """([article, net]) => {
  window.__chrono = { t0: null, t1: null };
  const affiche = () => {
    const cellule = document.querySelector("#ot-bloc-sorties tr[data-article='" + article + "'] td[data-libelle='Net']");
    return cellule !== null && cellule.textContent.trim() === net;
  };
  document.addEventListener('click', (e) => {
    if (e.target.closest('#form-sortie button[type=submit]') && window.__chrono.t0 === null) window.__chrono.t0 = performance.now();
  }, { capture: true, once: true });
  const observateur = new MutationObserver(() => {
    if (window.__chrono.t0 !== null && window.__chrono.t1 === null && affiche()) {
      window.__chrono.t1 = performance.now();
      observateur.disconnect();
    }
  });
  observateur.observe(document.getElementById('contenu'), { childList: true, subtree: true, characterData: true });
}"""


def lire_lignes(chemin):
    """Cellules brutes d'un CSV de Prévo (apostrophes de protection comprises) : (en-tête, lignes)."""
    lignes = list(csv.reader(io.StringIO(Path(chemin).read_text(encoding="utf-8-sig"), newline=""), delimiter=";"))
    return lignes[0], lignes[1:]


def lire_dictionnaires(chemin):
    """Lignes d'un CSV de Prévo en dictionnaires (valeurs brutes)."""
    entete, lignes = lire_lignes(chemin)
    return [dict(zip(entete, ligne)) for ligne in lignes]


def gammes_ouvertes(dossier):
    """Gammes qui ont un OT ouvert (ni clôturé ni annulé)."""
    return {o["gamme_id"] for o in lire_dictionnaires(Path(dossier) / "ordres_travail.csv")
            if o["gamme_id"] and o["statut"] not in STATUTS_FERMES}


def ecrire_lignes(chemin, entete, lignes):
    """Réécrit un CSV au format de Prévo (BOM, « ; », CRLF, guillemets seulement si besoin)."""
    tampon = io.StringIO(newline="")
    ecrivain = csv.writer(tampon, delimiter=";", lineterminator="\r\n")
    ecrivain.writerow(entete)
    ecrivain.writerows(lignes)
    Path(chemin).write_bytes((BOM + tampon.getvalue()).encode("utf-8"))


def gammes_echues_sans_ot(dossier, aujourdhui):
    """Gammes à date actives, échues (échéance − avance ≤ aujourd'hui) et sans OT ouvert (RG5)."""
    ouvertes = gammes_ouvertes(dossier)
    echues = []
    for gamme in lire_dictionnaires(Path(dossier) / "gammes.csv"):
        if gamme["declencheur"] != "date" or gamme["actif"] == "0" or gamme["id"] in ouvertes or not gamme["prochaine_echeance"]:
            continue
        avance = int(gamme["avance_jours"].lstrip("'") or 0)
        if datetime.date.fromisoformat(gamme["prochaine_echeance"]) - datetime.timedelta(days=avance) <= aujourdhui:
            echues.append(gamme["id"])
    return echues


def vieillir(dossier, aujourdhui, nombre):
    """Rend `nombre` gammes à date sans OT ouvert échues (échéance la plus proche d'abord, passée à
    hier) ; renvoie leurs identifiants."""
    entete, gammes = lire_lignes(Path(dossier) / "gammes.csv")
    colonne = {nom: position for position, nom in enumerate(entete)}
    ouvertes = gammes_ouvertes(dossier)
    candidates = sorted((g for g in gammes if g[colonne["declencheur"]] == "date" and g[colonne["actif"]] != "0"
                         and g[colonne["prochaine_echeance"]] and g[colonne["id"]] not in ouvertes),
                        key=lambda g: (g[colonne["prochaine_echeance"]], g[colonne["id"]]))[:nombre]
    hier = (aujourdhui - datetime.timedelta(days=1)).isoformat()
    for gamme in candidates:
        gamme[colonne["prochaine_echeance"]] = hier
    ecrire_lignes(Path(dossier) / "gammes.csv", entete, gammes)
    return sorted(g[colonne["id"]] for g in candidates)


class TestPerformance(CasNavigateur):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dossier_charge = Path(tempfile.mkdtemp(prefix="prevo-charge-"))
        cls.addClassCleanup(shutil.rmtree, cls.dossier_charge, True)
        cls.source = cls.dossier_charge / "donnees"
        resultat = subprocess.run(
            [sys.executable, str(RACINE / "outils" / "generer_demo.py"), "--volume", "500,5000",
             "--sortie", str(cls.source), "--sans-js"],
            cwd=str(RACINE), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=600)
        if resultat.returncode != 0:
            raise RuntimeError("generer_demo.py a échoué :\n" + resultat.stdout.decode("utf-8", "replace"))
        cls.aujourdhui = datetime.date.today()
        cls.gammes_vieillies = vieillir(cls.source, cls.aujourdhui, GAMMES_VIEILLIES)
        # Serveur partagé par les mesures d'actions (DI, sortie) ; le chargement a le sien (premier chargement).
        cls.serveur = ServeurPrevo(source=cls.source)
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)

    def nouvelle_page(self, serveur=None):
        """Contexte neuf (cache vide), profil responsable préréglé."""
        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
        self.addCleanup(contexte.close)
        contexte.set_default_timeout(30000)
        preregler_profil(contexte, "responsable")
        page = contexte.new_page()
        self.surveiller(page)
        return page

    def ouvrir(self, serveur=None):
        page = self.nouvelle_page()
        page.goto((serveur or self.serveur).url + "/")
        attendre_pret(page, 30000)
        page.wait_for_load_state("networkidle")
        return page

    def test_volume_du_jeu_de_charge(self):
        lignes = {table: len(lire_lignes(self.source / (table + ".csv"))[1])
                  for table in ("equipements", "ordres_travail", "gammes", "releves", "mouvements_stock", "achats")}
        print("\n  [performance] jeu de charge : %s" % ", ".join("%s %d" % (t, n) for t, n in lignes.items()))
        self.assertGreaterEqual(lignes["equipements"], 500)
        self.assertGreaterEqual(lignes["ordres_travail"], 5000)
        for table in ("gammes", "releves", "mouvements_stock", "achats"):          # en proportion
            self.assertGreaterEqual(lignes[table], 100, table)
        page = self.ouvrir()
        volumes = page.evaluate("['equipements', 'ordres_travail', 'gammes', 'mouvements_stock'].map((t) => Donnees.lignes(t).length)")
        self.assertGreaterEqual(volumes[0], 500)
        self.assertGreaterEqual(volumes[1], 5000)

    def test_chargement_complet_generation_du_preventif_comprise_median_sous_2_secondes(self):
        # Les gammes vieillies sont échues et sans OT : le premier chargement aura à les générer.
        echues = gammes_echues_sans_ot(self.source, self.aujourdhui)
        self.assertEqual(sorted(echues), self.gammes_vieillies)
        self.assertEqual(len(echues), GAMMES_VIEILLIES)
        with ServeurPrevo(source=self.source) as serveur:
            ordres = serveur.dossier / "ordres_travail.csv"
            nombre = len(lire_lignes(ordres)[1])
            mesures, crees, octets = [], [], None
            for numero in range(MESURES):
                page = self.nouvelle_page()
                page.goto(serveur.url + "/")
                attendre_pret(page, 30000)
                mesures.append(page.evaluate(CHARGEMENT_JS))
                crees.append(len(lire_lignes(ordres)[1]) - nombre)            # OT générés par ce chargement
                nombre = len(lire_lignes(ordres)[1])
                if numero == 0:
                    octets = (ordres.read_bytes(), (serveur.dossier / "ot_operations.csv").read_bytes())
                page.context.close()
            # Le premier chargement a généré un OT par gamme échue ; les suivants n'ont rien écrit.
            self.assertEqual(crees, [GAMMES_VIEILLIES, 0, 0])
            self.assertEqual(gammes_echues_sans_ot(serveur.dossier, self.aujourdhui), [])
            self.assertEqual((ordres.read_bytes(), (serveur.dossier / "ot_operations.csv").read_bytes()), octets)
        mediane = statistics.median(mesures)
        print("\n  [performance] chargement complet, préventif compris (500 équipements, 5000 OT) :"
              " premier (génère %d OT) %.0f ms ; suivants %s ms -> médiane des 3 %.0f ms (budget %d)"
              % (crees[0], mesures[0], ", ".join("%.0f" % m for m in mesures[1:]), mediane, BUDGET_CHARGEMENT_MS))
        # CS34 : « chargement complet < 2 s génération du préventif comprise ». Seul le premier
        # chargement génère des OT : la médiane seule ne le garderait pas (relecture de la vague 5).
        self.assertLess(mesures[0], BUDGET_CHARGEMENT_MS, "premier chargement (avec génération du préventif)")
        self.assertLess(mediane, BUDGET_CHARGEMENT_MS)

    def test_creation_di_mediane_sous_1_seconde(self):
        page = self.ouvrir()
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

    def test_sortie_de_piece_depuis_l_ot_mediane_sous_1_seconde(self):
        page = self.ouvrir()
        # Un OT « En cours » et un article actif qui a au moins MESURES unités en stock
        ot_id, article = page.evaluate("""(n) => [
            Donnees.lignes('ordres_travail').find((o) => o.statut === 'En cours').id,
            Donnees.lignes('articles').filter((a) => a.actif !== '0').map((a) => a.id).find((id) => Donnees.stockArticle(id) >= n)]""", MESURES)
        self.assertTrue(ot_id and article, (ot_id, article))
        stock_avant = page.evaluate("(a) => Donnees.stockArticle(a)", article)
        net_avant = page.evaluate("([ot, a]) => (Magasin.sortiesDeLOt(ot).find((l) => l.articleId === a) || { net: 0 }).net", [ot_id, article])
        page.evaluate("(id) => { location.hash = '#/ot/' + id; }", ot_id)
        page.wait_for_function("(id) => { const n = document.querySelector('.ot-fiche .ot-numero'); return n && n.textContent === id; }", arg=ot_id)
        page.click(".onglet[data-onglet='execution']")
        mesures = []
        for numero in range(1, MESURES + 1):
            page.wait_for_selector("#ot-bloc-sorties #form-sortie button[type=submit]:not([disabled])")
            page.select_option("#ot-sortie-article", article)
            page.fill("#ot-sortie-quantite", "1")
            page.evaluate(CHRONO_SORTIE_JS, [article, str(int(net_avant) + numero)])
            page.click("#form-sortie button[type=submit]")
            page.wait_for_function("window.__chrono.t1 !== null", timeout=30000)
            mesures.append(page.evaluate("window.__chrono.t1 - window.__chrono.t0"))
        self.assertEqual(page.evaluate("(a) => Donnees.stockArticle(a)", article), stock_avant - MESURES)
        sorties = [m for m in lire_dictionnaires(self.serveur.dossier / "mouvements_stock.csv")
                   if m["type"] == "sortie" and m["ot_id"] == ot_id and m["article_id"] == article]
        self.assertGreaterEqual(len(sorties), MESURES)
        mediane = statistics.median(mesures)
        print("\n  [performance] sortie de pièce depuis l'OT (clic -> bloc « Pièces sorties » à jour) : %s ms"
              " -> médiane %.0f ms (budget %d)" % (", ".join("%.0f" % m for m in mesures), mediane, BUDGET_SORTIE_MS))
        self.assertLess(mediane, BUDGET_SORTIE_MS)

    # -- Lot 3 (CS49) ------------------------------------------------------------------------------

    def test_planning_de_la_semaine_mediane_sous_1_seconde(self):
        page = self.ouvrir()
        lundi = page.evaluate("Planning.lundiDe(Donnees.aujourdhui())")
        mesures = []
        for numero in range(MESURES):
            semaine = (datetime.date.fromisoformat(lundi) + datetime.timedelta(days=7 * (numero % 2))).isoformat()
            page.evaluate("location.hash = '#/accueil'")
            page.wait_for_selector("#contenu .accueil-instruments")
            duree = page.evaluate("""(semaine) => new Promise((resoudre) => {
                const t0 = performance.now();
                const observateur = new MutationObserver(() => {
                  const grille = document.querySelector('#contenu .pl-ecran[data-lundi="' + semaine + '"] .pl-grille');
                  if (grille) { observateur.disconnect(); resoudre(performance.now() - t0); }
                });
                observateur.observe(document.getElementById('contenu'), { childList: true, subtree: true });
                location.hash = '#/planning?semaine=' + semaine;
            })""", semaine)
            mesures.append(duree)
        lignes = page.evaluate("document.querySelectorAll('#contenu .pl-grille tbody tr').length")
        cartes = page.evaluate("document.querySelectorAll('#contenu .pl-ot').length")
        mediane = statistics.median(mesures)
        print("\n  [performance] planning de la semaine (%d lignes, %d cartes) : %s ms -> médiane %.0f ms (budget %d)"
              % (lignes, cartes, ", ".join("%.0f" % m for m in mesures), mediane, BUDGET_PLANNING_MS))
        self.assertGreater(lignes, 0)
        self.assertLess(mediane, BUDGET_PLANNING_MS)

    def test_ecran_indicateurs_douze_mois_echarts_compris_sous_2_secondes(self):
        # Contexte neuf : ECharts n'est pas encore chargé, la première mesure le charge (cache vide).
        page = self.ouvrir()
        self.assertEqual(page.evaluate("typeof echarts"), "undefined")
        mesures = []
        for _ in range(MESURES):
            page.evaluate("location.hash = '#/accueil'")
            page.wait_for_selector("#contenu .accueil-instruments")
            duree = page.evaluate("""() => new Promise((resoudre) => {
                const t0 = performance.now();
                const fini = () => {
                  const cartes = document.querySelectorAll('#contenu .indicateurs-graphique[data-etat]');
                  return document.querySelector('#contenu .instruments') && cartes.length >= 7
                    && Array.from(cartes).every((carte) => carte.dataset.etat !== 'chargement');
                };
                const observateur = new MutationObserver(() => {
                  if (fini()) { observateur.disconnect(); resoudre(performance.now() - t0); }
                });
                observateur.observe(document.getElementById('contenu'), { childList: true, subtree: true, attributes: true });
                location.hash = '#/indicateurs?periode=12-mois';
            })""")
            mesures.append(duree)
        etats = page.evaluate("Array.from(document.querySelectorAll('#contenu .indicateurs-graphique')).map((c) => c.dataset.etat)")
        print("\n  [performance] écran Indicateurs, 12 mois (%d graphiques : %s) : %s ms (1re : chargement d'ECharts) -> pire %.0f ms (budget %d)"
              % (len(etats), ", ".join(sorted(set(etats))), ", ".join("%.0f" % m for m in mesures), max(mesures), BUDGET_INDICATEURS_MS))
        self.assertNotIn("erreur", etats)
        self.assertLess(mesures[0], BUDGET_INDICATEURS_MS, "premier affichage, chargement d'ECharts compris")
        self.assertLess(statistics.median(mesures), BUDGET_INDICATEURS_MS)

    def test_rapport_fige_sous_5_secondes(self):
        page = self.ouvrir()
        mois = page.evaluate("Rapport.interne.decalerMois(Donnees.aujourdhui().slice(0, 7), -1)")
        duree, nom = page.evaluate("""async (mois) => { const t0 = performance.now();
            const resultat = await Rapport.figer(mois); return [performance.now() - t0, resultat.nom]; }""", mois)
        print("\n  [performance] rapport figé de %s (%s) : %.0f ms (budget %d)" % (mois, nom, duree, BUDGET_RAPPORT_MS))
        self.assertTrue((Path(self.serveur.dossier) / "documents" / nom).is_file())
        self.assertLess(duree, BUDGET_RAPPORT_MS)


if __name__ == "__main__":
    unittest.main()
