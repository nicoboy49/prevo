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
                         ECharts (contexte neuf) ; budget 2 000 ms pour la première et pour la médiane ;
    planning (lot 3)   : du changement d'adresse vers #/planning?semaine=… à l'affichage de la grille
                         (.pl-grille) ; budget 1 000 ms ;
    rapport figé (lot 3) : Rapport.figer(mois) — calcul des indicateurs du mois, de M-1 et de N-1,
                         page HTML avec ses graphiques SVG, écriture du document ; budget 5 000 ms.
    suggestions (lot 3 bis) : du changement d'adresse vers #/preventif?onglet=suggestions à l'affichage
                         des cartes (calcul des quatre règles sur tout l'historique compris) ;
                         budget 1 000 ms (médiane).
    ouverture sans IA (lot 4) : aucun appel réseau hors du serveur Prévo (ni /api/ia), aucun en démo.
    chargement sans SheetJS (lot 5, D89, CS93) : js/lib/xlsx.full.min.js n'est jamais demandé à l'ouverture
                         (serveur et démo), il ne l'est qu'à la demande (App.chargerSheetJS) ;
    import (lot 5, D89, CS93) : 5 000 lignes d'articles puis 5 000 OT d'historique fabriqués ici, importés dans
                         une copie du jeu de charge : lecture et aperçu (Import.lire, Import.correspondance,
                         Import.preparer) < 3 000 ms ; écriture (Import.importer : aperçu recalculé sur les
                         données fraîches, sauvegarde « avant-import », tables et journal) < 5 000 ms.
    wiki (lot 6, D101) : page wiki de l'équipement qui a le plus d'OT affichée < 500 ms (première et médiane) ; une
                         recherche sur tout le parc < 300 ms, la première (qui construit l'index) comprise ; une requête
                         d'ingestion (Wiki.donneesIngestion puis Ia.requete('ingestionWiki', …)) construite < 1 000 ms
                         pour l'OT clôturé administrativement qui concerne le plus de pages ; aucun appel réseau.
Les chronomètres des actions sont posés dans la page (performance.now()).

Horloge : le navigateur vit à la date de référence du jeu de charge (DATE_REFERENCE de outils/generer_demo.py,
la même que la démo), 9 h 30 au début de chaque page, et le vieillissement part de cette date. Avec la vraie
date, les gammes que le temps rend échues s'ajoutaient aux 20 vieillies (5 le 2026-10-22, 21 le 2026-10-29 : le
test du chargement aurait échoué sur son nombre d'OT). La date est décalée, pas figée (Date.now avance) et
performance.now n'est pas touché : clock.set_fixed_time de Playwright remplace aussi l'objet performance, dont
getEntriesByName rend alors une liste vide (plus de marques de chargement).

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

from commun import RACINE, CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, url_fichier
from test_controles import date_reference

BUDGET_CHARGEMENT_MS = 2000
BUDGET_CREATION_DI_MS = 1000
BUDGET_SORTIE_MS = 1000
BUDGET_INDICATEURS_MS = 2000        # lot 3 (CS49) : écran Indicateurs sur 12 mois, ECharts compris
BUDGET_PLANNING_MS = 1000           # lot 3 (CS49) : planning de la semaine affiché
BUDGET_RAPPORT_MS = 5000            # lot 3 (CS49) : rapport figé (calcul, page HTML, écriture)
BUDGET_SUGGESTIONS_MS = 1000        # lot 3 bis (CS62) : onglet Suggestions du Préventif affiché
BUDGET_APERCU_IMPORT_MS = 3000      # lot 5 (D89) : lecture et aperçu d'un fichier de 5 000 lignes
BUDGET_ECRITURE_IMPORT_MS = 5000    # lot 5 (D89) : écriture de l'import (sauvegarde et journal compris)
BUDGET_PAGE_WIKI_MS = 500           # lot 6 (D101) : page wiki d'un équipement affichée
BUDGET_RECHERCHE_WIKI_MS = 300      # lot 6 (D101) : une recherche (la première construit l'index)
BUDGET_REQUETE_INGESTION_MS = 1000  # lot 6 (D101) : une requête d'ingestion construite (données et message au modèle)
LIGNES_IMPORT = 5000
SHEETJS = "js/lib/xlsx.full.min.js"
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

# Date du navigateur décalée vers `debut` (millisecondes) au chargement de chaque page : Date.now avance,
# performance n'est pas touché (voir l'en-tête). new Date(…) avec arguments reste la vraie.
HORLOGE_JS = """(() => {
  const Natif = Date;
  const decalage = %d - Natif.now();
  function DateDecalee(...valeurs) {
    if (!new.target) return new Natif(Natif.now() + decalage).toString();
    return valeurs.length ? new Natif(...valeurs) : new Natif(Natif.now() + decalage);
  }
  DateDecalee.prototype = Natif.prototype;
  DateDecalee.now = () => Natif.now() + decalage;
  DateDecalee.parse = Natif.parse;
  DateDecalee.UTC = Natif.UTC;
  window.Date = DateDecalee;
})();"""

# Import de 5 000 lignes (lot 5) : lecture d'un fichier CSV, correspondance automatique et aperçu, puis écriture.
IMPORT_JS = """async ([type, nom, texte]) => {
  const t0 = performance.now();
  const lu = await Import.lire(new File([texte], nom, { type: 'text/csv' }));
  const lignes = lu.feuilles[0].lignes;
  const rang = Import.ligneEntete(lignes, type);
  const donnees = lignes.slice(rang + 1);
  const correspondance = Import.correspondance(type, Import.entetes(lignes, rang, false), donnees, 'auto');
  const t1 = performance.now();
  const reglages = { mettreAJour: true, numeroPremiereLigne: rang + 2, maintenant: Donnees.maintenant() };
  const apercu = Import.preparer(type, donnees, correspondance, reglages);
  const t2 = performance.now();
  const resultat = await Import.importer(apercu, { nomFichier: nom,
    recalculer: () => Import.preparer(type, donnees, correspondance, reglages) });
  const t3 = performance.now();
  return { lecture: t1 - t0, apercu: t2 - t1, ecriture: t3 - t2, totaux: apercu.totaux, tables: resultat.tables,
           sauvegarde: resultat.sauvegarde, pasSures: correspondance.filter((c) => c.statut !== 'sure').map((c) => c.entete) };
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


def texte_csv(lignes, separateur):
    tampon = io.StringIO(newline="")
    csv.writer(tampon, delimiter=separateur, lineterminator="\r\n").writerows(lignes)
    return tampon.getvalue()


def fichier_articles(dossier):
    """Export d'une autre GMAO : 5 000 articles nouveaux (« ; », décimales à virgule), fournisseurs du jeu de
    charge et trois nouveaux (créés une fois, D88)."""
    fournisseurs = [f["nom"] for f in lire_dictionnaires(Path(dossier) / "fournisseurs.csv")]
    fournisseurs += ["Fournisseur importé %d" % n for n in (1, 2, 3)]
    lignes = [["Code article", "Libellé", "Fournisseur", "Qté stock", "Prix achat", "Stock mini", "Délai livraison"]]
    for n in range(1, LIGNES_IMPORT + 1):
        lignes.append(["IMP-%05d" % n, "Article importé n° %d" % n, fournisseurs[n % len(fournisseurs)],
                       str(n % 40), "%d,%02d" % (1 + n % 300, n % 100), "2", str(3 + n % 10)])
    return texte_csv(lignes, ";")


def fichier_historique(dossier):
    """Historique d'une autre GMAO : 5 000 OT clôturés (« , », dates JJ/MM/AAAA HH:MM) sur les équipements du jeu
    de charge, types libres, codes par code, intervenants par « Prénom Nom », temps passé."""
    dossier = Path(dossier)
    reperes = [e["repere"].lstrip("'") for e in lire_dictionnaires(dossier / "equipements.csv") if e["actif"] != "0"]
    techniciens = ["%s %s" % (t["prenom"], t["nom"]) for t in lire_dictionnaires(dossier / "techniciens.csv")]
    codes = {}
    for code in lire_dictionnaires(dossier / "codes_defaillance.csv"):
        codes.setdefault(code["famille"], []).append(code["code"])
    types = ["Dépannage", "Préventif", "Curatif", "Correctif différé", "Amélioration"]
    depart = datetime.datetime(2023, 1, 2, 7, 0)
    lignes = [["N° OT", "Machine", "Date demande", "Début", "Fin", "Type", "Libellé", "Compte rendu", "Durée arrêt (h)",
               "Arrêt", "Symptôme", "Cause", "Remède", "Intervenant", "Temps (h)"]]
    for n in range(LIGNES_IMPORT):
        demande = depart + datetime.timedelta(minutes=101 * n)
        type_ = types[n % len(types)]
        panne = type_ in ("Dépannage", "Curatif")
        lignes.append([
            "H%05d" % n, reperes[n % len(reperes)], demande.strftime("%d/%m/%Y %H:%M"),
            (demande + datetime.timedelta(minutes=20)).strftime("%d/%m/%Y %H:%M"),
            (demande + datetime.timedelta(minutes=140)).strftime("%d/%m/%Y %H:%M"), type_,
            "Intervention importée n° %d" % n, "Compte rendu de l'intervention %d : remis en état, essais concluants." % n,
            "1.5" if panne else "", "oui" if panne else "non",
            codes["symptôme"][n % len(codes["symptôme"])] if panne else "",
            codes["cause"][n % len(codes["cause"])] if panne else "",
            codes["remède"][n % len(codes["remède"])] if panne else "",
            techniciens[n % len(techniciens)], "1,25"])
    return texte_csv(lignes, ",")


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
        # Date de référence du jeu (voir l'en-tête), et non la date du jour.
        cls.aujourdhui = date_reference()
        cls.debut_horloge_ms = int(datetime.datetime.combine(cls.aujourdhui, datetime.time(9, 30)).timestamp() * 1000)
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
        contexte.add_init_script(HORLOGE_JS % self.debut_horloge_ms)
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
            mesures, crees, octets, demandes = [], [], None, []
            for numero in range(MESURES):
                page = self.nouvelle_page()
                page.on("request", lambda requete: demandes.append(requete.url))
                page.goto(serveur.url + "/")
                attendre_pret(page, 30000)
                mesures.append(page.evaluate(CHARGEMENT_JS))
                self.assertEqual(page.evaluate("[Donnees.aujourdhui(), typeof XLSX]"), [self.aujourdhui.isoformat(), "undefined"])
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
        # T86 : ce premier chargement dépassait parfois 2 s. Mesuré (profil du processeur) : la génération
        # cherchait l'identifiant suivant en relisant toute la table pour chaque OT et chaque opération de
        # check-list créés (plusGrandNumero, première fonction du profil) ; corrigé dans preventif-ecritures.js.
        # Le reste de l'écart avec les chargements suivants est la réécriture de ordres_travail et ot_operations.
        self.assertLess(mesures[0], BUDGET_CHARGEMENT_MS, "premier chargement (avec génération du préventif)")
        self.assertLess(mediane, BUDGET_CHARGEMENT_MS)
        # CS93 (lot 5) : ce chargement ne demande pas SheetJS
        self.assertEqual([a for a in demandes if SHEETJS in a], [])

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

    # -- Lot 3 bis (CS62) --------------------------------------------------------------------------

    def test_onglet_suggestions_mediane_sous_1_seconde(self):
        page = self.ouvrir()
        mesures = []
        for _ in range(MESURES):
            page.evaluate("location.hash = '#/accueil'")
            page.wait_for_selector("#contenu .accueil-instruments")
            duree = page.evaluate("""() => new Promise((resoudre) => {
                const t0 = performance.now();
                const observateur = new MutationObserver(() => {
                  const panneau = document.querySelector("#contenu .panneau-onglet[data-onglet='suggestions']");
                  if (panneau && panneau.querySelector('.sg-cartes, .vide')) {
                    // l'image suivante comprise (mise en page et affichage, relecture finale)
                    observateur.disconnect(); requestAnimationFrame(() => resoudre(performance.now() - t0)); }
                });
                observateur.observe(document.getElementById('contenu'), { childList: true, subtree: true });
                location.hash = '#/preventif?onglet=suggestions';
            })""")
            mesures.append(duree)
        cartes = page.evaluate("document.querySelectorAll('#contenu .sg-carte').length")
        mediane = statistics.median(mesures)
        print("\n  [performance] onglet Suggestions (%d cartes) : %s ms -> médiane %.0f ms (budget %d)"
              % (cartes, ", ".join("%.0f" % m for m in mesures), mediane, BUDGET_SUGGESTIONS_MS))
        self.assertGreater(cartes, 0, "le jeu de charge doit produire des suggestions")
        self.assertEqual(cartes, page.evaluate("Suggestions.ouvertes(Donnees.aujourdhui()).length"))
        self.assertLess(mediane, BUDGET_SUGGESTIONS_MS)

    def test_ouverture_sans_ia_aucun_appel_reseau_hors_du_serveur(self):
        """Lot 4 (CS76) : tant que l'IA n'est pas activée, l'ouverture ne fait aucun appel hors du serveur
        Prévo (ni /api/ia, ni fournisseur) ; même chose en démo (file://) : aucune requête hors du disque."""
        page = self.nouvelle_page()
        adresses = []
        page.on("request", lambda requete: adresses.append(requete.url))
        page.goto(self.serveur.url + "/")
        attendre_pret(page, 30000)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(500)
        self.assertEqual(page.evaluate("[Ia.active(), Ia.etat()]"), [False, "inconnu"])
        self.assertTrue(adresses)
        self.assertEqual([a for a in adresses if not a.startswith(self.serveur.url + "/")], [])
        self.assertEqual([a for a in adresses if "/api/ia" in a], [])

        demo = self.nouvelle_page()
        adresses_demo = []
        demo.on("request", lambda requete: adresses_demo.append(requete.url))
        demo.goto(url_fichier("index.html"))
        demo.click("#btn-demo")
        attendre_pret(demo, 30000)
        demo.wait_for_load_state("networkidle")
        demo.wait_for_timeout(500)
        self.assertEqual(demo.evaluate("[Ia.active(), Ia.etat()]"), [False, "inconnu"])
        self.assertEqual([a for a in adresses_demo if not a.startswith(("file:", "data:", "blob:"))], [])

    # -- Lot 5 (D89, CS93) -------------------------------------------------------------------------

    def test_chargement_sans_sheetjs_serveur_et_demo_sous_2_secondes(self):
        """Ouverture (serveur, puis démo) : SheetJS n'est jamais demandé ; il ne l'est qu'à la demande
        (App.chargerSheetJS, à l'ouverture d'un classeur) — ce qui prouve aussi que la surveillance le verrait."""
        for nom, ouvrir in (("serveur", lambda p: p.goto(self.serveur.url + "/")),
                            ("démo", lambda p: (p.goto(url_fichier("index.html")), p.click("#btn-demo")))):
            with self.subTest(mode=nom):
                page = self.nouvelle_page()
                adresses = []
                page.on("request", lambda requete: adresses.append(requete.url))
                ouvrir(page)
                attendre_pret(page, 30000)
                page.wait_for_load_state("networkidle")
                duree = page.evaluate(CHARGEMENT_JS)
                print("\n  [performance] chargement (%s) sans SheetJS : %.0f ms (budget %d), %d fichiers demandés"
                      % (nom, duree, BUDGET_CHARGEMENT_MS, len(adresses)))
                self.assertEqual([a for a in adresses if SHEETJS in a], [])
                self.assertEqual(page.evaluate("typeof XLSX"), "undefined")
                self.assertLess(duree, BUDGET_CHARGEMENT_MS)
                page.evaluate("App.chargerSheetJS().then(() => true)")
                self.assertEqual(len([a for a in adresses if SHEETJS in a]), 1, "à la demande : demandé une fois")
                self.assertEqual(page.evaluate("typeof XLSX.read"), "function")

    def test_import_5000_articles_et_5000_ot_apercu_sous_3_s_ecriture_sous_5_s(self):
        """D89 : sur une copie du jeu de charge, 5 000 lignes d'articles puis 5 000 OT d'historique : lecture et
        aperçu (Import.preparer) < 3 s, écriture (Import.importer) < 5 s, chacun mesuré dans la page."""
        with ServeurPrevo(source=self.source) as serveur:
            page = self.nouvelle_page()
            page.goto(serveur.url + "/")
            attendre_pret(page, 30000)
            page.wait_for_load_state("networkidle")
            avant = page.evaluate("['articles', 'mouvements_stock', 'ordres_travail', 'ot_temps'].map((t) => Donnees.lignes(t).length)")
            for type_, nom, texte, tables in (
                    ("articles", "articles-5000.csv", fichier_articles(self.source), ("articles", "mouvements_stock")),
                    ("historique", "historique-5000.csv", fichier_historique(self.source), ("ordres_travail", "ot_temps"))):
                with self.subTest(type=type_):
                    mesure = page.evaluate(IMPORT_JS, [type_, nom, texte])
                    print("\n  [performance] import de %d lignes (%s) : lecture %.0f ms + aperçu %.0f ms = %.0f ms (budget %d) ;"
                          " écriture %.0f ms (budget %d)" % (LIGNES_IMPORT, type_, mesure["lecture"], mesure["apercu"],
                                                             mesure["lecture"] + mesure["apercu"], BUDGET_APERCU_IMPORT_MS,
                                                             mesure["ecriture"], BUDGET_ECRITURE_IMPORT_MS))
                    # Le jeu fabriqué est entièrement valable : on mesure 5 000 créations, pas des refus.
                    self.assertEqual(mesure["pasSures"], [])
                    self.assertEqual((mesure["totaux"]["creer"], mesure["totaux"]["refusee"]), (LIGNES_IMPORT, 0), mesure["totaux"])
                    for table in tables:
                        self.assertEqual(mesure["tables"][table]["crees"], LIGNES_IMPORT, table)
                    self.assertRegex(mesure["sauvegarde"], r"_avant-import$")
                    self.assertLess(mesure["lecture"] + mesure["apercu"], BUDGET_APERCU_IMPORT_MS, "lecture et aperçu")
                    self.assertLess(mesure["ecriture"], BUDGET_ECRITURE_IMPORT_MS, "écriture")
            apres = page.evaluate("['articles', 'mouvements_stock', 'ordres_travail', 'ot_temps'].map((t) => Donnees.lignes(t).length)")
            self.assertEqual([b - a for a, b in zip(avant, apres)], [LIGNES_IMPORT] * 4)

    def test_wiki_page_sous_500_ms_et_recherche_sous_300_ms_sans_appel_reseau(self):
        """Lot 6 (D101) : la page wiki de l'équipement qui a le plus d'OT s'affiche en moins de 500 ms (médiane et
        première fois) ; une recherche sur tout le parc prend moins de 300 ms, la première (qui construit l'index)
        comprise ; ni l'une ni l'autre ne fait d'appel réseau."""
        page = self.ouvrir()
        requetes = []
        page.on("request", lambda requete: requetes.append(requete.url))
        equipement = page.evaluate("""() => { const compte = new Map();
            Donnees.lignes('ordres_travail').forEach((o) => compte.set(o.equipement_id, (compte.get(o.equipement_id) || 0) + 1));
            return Array.from(compte.entries()).sort((a, b) => b[1] - a[1])[0][0]; }""")
        mesures_page = []
        for _ in range(MESURES):
            page.evaluate("location.hash = '#/accueil'")
            page.wait_for_selector("#contenu .accueil-instruments")
            mesures_page.append(page.evaluate("""(id) => new Promise((resoudre) => {
                const t0 = performance.now();
                const observateur = new MutationObserver(() => {
                  if (document.querySelector('#contenu #wiki-consignation')) {
                    observateur.disconnect(); requestAnimationFrame(() => resoudre(performance.now() - t0)); }
                });
                observateur.observe(document.getElementById('contenu'), { childList: true, subtree: true });
                location.hash = '#/wiki/' + id;
            })""", equipement))
        mesures_recherche = page.evaluate("""() => ['bruit au palier', 'fuite garniture', 'arret intempestif capteur',
            'surchauffe moteur', 'courroie qui claque'].map((texte) => {
              const t0 = performance.now();
              const resultat = Wiki.rechercher(texte, {});
              return { duree: performance.now() - t0, trouves: resultat.portees.reduce((n, p) => n + p.resultats.length, 0) };
            })""")
        durees = [m["duree"] for m in mesures_recherche]
        print("\n  [performance] page wiki (%s) : %s ms -> médiane %.0f ms (budget %d) ; recherches : %s ms (budget %d)"
              % (equipement, ", ".join("%.0f" % m for m in mesures_page), statistics.median(mesures_page),
                 BUDGET_PAGE_WIKI_MS, ", ".join("%.0f" % d for d in durees), BUDGET_RECHERCHE_WIKI_MS))
        self.assertLess(mesures_page[0], BUDGET_PAGE_WIKI_MS, "première page wiki")
        self.assertLess(statistics.median(mesures_page), BUDGET_PAGE_WIKI_MS)
        self.assertLess(max(durees), BUDGET_RECHERCHE_WIKI_MS, "recherche (index compris)")
        self.assertTrue(all(m["trouves"] > 0 for m in mesures_recherche), mesures_recherche)
        # /api/info : c'est l'accueil du responsable, affiché entre deux mesures, qui lit l'état de la copie externe des
        # sauvegardes (lot 7, T175) ; la page wiki et la recherche, elles, ne font aucun appel.
        self.assertEqual([u for u in requetes if "/api/" in u and "/api/ping" not in u and "/api/versions" not in u
                          and "/api/info" not in u], [])

    def test_wiki_requete_d_ingestion_construite_sous_1_seconde_sans_appel_reseau(self):
        """Lot 6 (D101) : une requête d'ingestion — Wiki.donneesIngestion(otId) (état proposé recalculé, pages
        concernées, textes, catalogue) puis le message au modèle (Ia.requete('ingestionWiki', …)) — se construit en moins
        de 1 s sur le jeu de charge, pour l'OT clôturé administrativement qui concerne le plus de pages ; première mesure et
        médiane de trois ; aucun appel réseau."""
        page = self.ouvrir()
        requetes = []
        page.on("request", lambda requete: requetes.append(requete.url))
        choix = page.evaluate("""() => { const etat = Wiki.etatPropose();
            const clotures = Donnees.lignes('ordres_travail').filter((o) => o.statut === 'Clôturé administrativement');
            let meilleur = null;
            clotures.forEach((o) => { const n = Wiki.pagesConcernees(o.id, etat).cles.length;
              if (!meilleur || n > meilleur.pages) meilleur = { ot: o.id, pages: n }; });
            return Object.assign(meilleur, { clotures: clotures.length, pagesWiki: Donnees.lignes('wiki_pages').length }); }""")
        self.assertGreater(choix["clotures"], 1000, "le jeu de charge doit avoir des OT clôturés administrativement")
        mesures = page.evaluate("""([ot, n]) => { const mesures = [];
            for (let i = 0; i < n; i += 1) {
              const t0 = performance.now();
              const donnees = Wiki.donneesIngestion(ot);              // comme un envoi : l'état proposé est recalculé
              const requete = Ia.requete('ingestionWiki', donnees);
              mesures.push({ duree: performance.now() - t0, pages: donnees.pages.length, catalogue: donnees.catalogue.length,
                caracteres: requete.messages.reduce((total, m) => total + m.content.length, 0),
                entete: requete.messages[1].content.slice(0, 40) });
            }
            return mesures; }""", [choix["ot"], MESURES])
        durees = [m["duree"] for m in mesures]
        print("\n  [performance] requête d'ingestion de %s (%d pages concernées sur %d OT clôturés et %d pages du wiki ; "
              "%d pages envoyées, catalogue de %d, %d caractères) : %s ms -> médiane %.0f ms (budget %d)"
              % (choix["ot"], choix["pages"], choix["clotures"], choix["pagesWiki"], mesures[0]["pages"], mesures[0]["catalogue"],
                 mesures[0]["caracteres"], ", ".join("%.0f" % d for d in durees), statistics.median(durees),
                 BUDGET_REQUETE_INGESTION_MS))
        self.assertTrue(all(m["entete"].startswith("OT à intégrer : " + choix["ot"]) for m in mesures), mesures[0]["entete"])
        self.assertEqual(mesures[0]["pages"], choix["pages"] if choix["pages"] <= page.evaluate("Wiki.SEUILS.pagesEnvoyeesMax")
                         else page.evaluate("Wiki.SEUILS.pagesEnvoyeesMax"))
        self.assertLess(durees[0], BUDGET_REQUETE_INGESTION_MS, "première requête d'ingestion")
        self.assertLess(statistics.median(durees), BUDGET_REQUETE_INGESTION_MS)
        self.assertEqual([u for u in requetes if "/api/" in u and "/api/ping" not in u and "/api/versions" not in u], [])


if __name__ == "__main__":
    unittest.main()
