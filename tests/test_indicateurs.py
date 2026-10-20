"""Tests de l'écran Indicateurs (tâche T49, ARCHITECTURE.md §15.4 ; brief §12) :
js/modules/indicateurs-graphiques.js, js/modules/indicateurs-ecrans.js, css/modules/indicateurs.css.

Familles (le nom du test le dit) :
    echarts      : ECharts absent à l'état « prêt » et sur l'accueil, chargé à l'ouverture de
                   #/indicateurs ; sept graphiques rendus en SVG ; un échec de chargement laisse un
                   message clair dans chaque carte et les tableaux « Voir les valeurs » visibles ;
    instruments  : chaque valeur du bandeau = Indicateurs.global(période, filtres) arrondie (heures et
                   % à 1 décimale, euros à 2) ; une valeur null affiche sa raison ; effectifs visibles ;
                   « dont attente de pièces » sous le MTTR quand elle est calculable ; encadré
                   « Comprendre » ; aucun NaN, Infinity ni undefined dans la page ;
    periode      : changer la période (liste, puis ?periode=du-au&du=&au=) change les valeurs et
                   l'adresse ; filtres criticité et atelier (?criticite=, ?atelier=) ;
    equipements  : tableau par équipement : un équipement sans heures de fonctionnement est « non
                   calculable » avec sa raison ; tri par clic ; lien vers la fiche ;
    graphiques   : chaque « Voir les valeurs » = les séries des règles (Indicateurs.paretoPannes…) ;
                   jamais deux axes de valeurs (lecture de l'option ECharts) ; légende dès 2 séries ;
                   palette : écart de couleur simulé (deutéranopie, protanopie ; Machado 2009, OKLab)
                   suffisant entre séries voisines d'un même graphique, aucune couleur de statut ;
    exports      : CSV (BOM, « ; », CRLF, point décimal) et PNG (signature PNG, largeur ×2) ;
    profils      : technicien et demandeur renvoyés à l'accueil, sans entrée de menu ;
    largeurs     : 1440 px et 375 px (téléphone) sans défilement horizontal, zones tactiles ≥ 48 px ;
                   redimensionnement suivi (le dessin reprend la largeur de sa zone) ;
    echappement  : une cause, un repère et un atelier contenant du HTML restent du texte ;
    rapports     : onglet « Rapports mensuels » (Rapport.afficherOnglet s'il existe, sinon message) ;
    demo         : index.html en file:// (« Essayer avec les données de démo ») : mêmes contrôles
                   essentiels, exports compris.

Aucun identifiant du jeu de démo n'est écrit en dur : les attentes sont calculées au moment du test
par les règles Indicateurs.* (déjà testées par test_regles_indicateurs.py) ou lues dans les CSV.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_indicateurs.py" -v
"""
import csv
import io
import math
import re
import struct
import unittest
from pathlib import Path

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, url_fichier

GRAPHIQUES = ["pareto-pannes", "pareto-arrets", "heures-mois", "mtbf-a", "mttr-a", "causes", "charge"]
INSTRUMENTS = {
    # data-indicateur : (clé de Indicateurs.global, unité affichée)
    "disponibilite": ("disponibilite", "%"), "mtbf": ("mtbf", "h"), "mttr": ("mttr", "h"),
    "duree-arret": ("dureeArret", "h"), "part-preventif": ("partPreventif", "%"),
    "respect-preventif": ("respectPreventif", "%"), "ot-en-retard": ("otEnRetard", ""),
    "cout": ("cout", "€"), "valeur-stock": ("valeurStock", "€"),
}
# Couleurs de statut de la charte (css/style.css, thème sombre) : interdites aux séries.
COULEURS_STATUT = {"#3DD68C", "#FF6B70", "#F5B544", "#2BD4F0", "#9B7BFF"}
SEUIL_DALTONISME = 8.0       # OKLab ΔE×100, cible du skill dataviz (plancher 6 seulement avec double codage)
SEUIL_VISION_NORMALE = 15.0
SIGNATURE_PNG = b"\x89PNG\r\n\x1a\n"

PETITES_ZONES_JS = """() => {
  const petites = [];
  for (const el of document.querySelectorAll('#contenu a, #contenu button, #contenu input, #contenu select, #contenu textarea, #contenu summary')) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height || el.closest('[hidden]') || el.type === 'hidden') continue;
    const cible = (el.type === 'checkbox' || el.type === 'radio') ? (el.closest('label') || el) : el;
    const hauteur = cible.getBoundingClientRect().height;
    if (hauteur < 47.5) petites.push(el.tagName + ' « ' + (el.textContent || el.value || '').trim().slice(0, 30) + ' » ' + Math.round(hauteur) + ' px');
  }
  return petites;
}"""

ATTENDRE_GRAPHIQUES_JS = """(nombre) => {
  const cartes = document.querySelectorAll('#contenu .indicateurs-graphique');
  return cartes.length === nombre && Array.from(cartes).every((c) => ['pret', 'vide', 'erreur'].includes(c.dataset.etat));
}"""

# Attentes calculées DANS la page par les règles (période et filtres lus dans l'écran).
ATTENDUS_INSTRUMENTS_JS = """() => {
  const zone = document.querySelector('#contenu .indicateurs-resultats');
  const p = Indicateurs.periode(zone.dataset.periode, Donnees.aujourdhui(), zone.dataset.du, zone.dataset.au);
  const filtres = { criticite: zone.dataset.criticite || '', atelier: zone.dataset.atelier || '' };
  const g = Indicateurs.global(p, filtres, Donnees.aujourdhui());
  const arrondi = (v, d) => Math.round(v * Math.pow(10, d)) / Math.pow(10, d);
  const pct = (r) => (r.valeur === null ? null : arrondi(r.valeur * 100, 1));
  const h = (r) => (r.valeur === null ? null : arrondi(r.valeur, 1));
  const e = (r) => (r.valeur === null ? null : arrondi(r.valeur, 2));
  const n = (r) => r.valeur;
  const valeurs = {
    disponibilite: pct(g.disponibilite), mtbf: h(g.mtbf), mttr: h(g.mttr), 'duree-arret': h(g.dureeArret),
    'part-preventif': pct(g.partPreventif), 'respect-preventif': pct(g.respectPreventif),
    'ot-en-retard': n(g.otEnRetard), cout: e(g.cout), 'valeur-stock': e(g.valeurStock) };
  const raisons = {
    disponibilite: g.disponibilite.raison, mtbf: g.mtbf.raison, mttr: g.mttr.raison, 'duree-arret': g.dureeArret.raison,
    'part-preventif': g.partPreventif.raison, 'respect-preventif': g.respectPreventif.raison,
    'ot-en-retard': g.otEnRetard.raison, cout: g.cout.raison, 'valeur-stock': g.valeurStock.raison };
  return { periode: { debut: p.debut, fin: p.fin, code: p.code }, valeurs, raisons,
           attente: { valeur: g.attentePieces.valeur === null ? null : arrondi(g.attentePieces.valeur, 1),
                      effectif: g.attentePieces.effectif, raison: g.attentePieces.raison },
           pannes: g.pannes.valeur };
}"""

LIRE_INSTRUMENTS_JS = """() => {
  const resultat = {};
  document.querySelectorAll('#contenu .indicateurs-instruments [data-indicateur]').forEach((el) => {
    const attente = el.querySelector('.indicateurs-attente');
    resultat[el.dataset.indicateur] = { valeur: el.dataset.valeur, chiffre: el.querySelector('.chiffre').textContent,
      texte: el.textContent.replace(/\\s+/g, ' '), attente: attente ? attente.textContent.replace(/\\s+/g, ' ') : null };
  });
  return resultat;
}"""

# Séries attendues de chaque graphique (règles), au format des tableaux « Voir les valeurs » :
# lignes de cellules ; un nombre est arrondi comme à l'écran, un texte est comparé tel quel.
ATTENDUS_GRAPHIQUES_JS = """() => {
  const zone = document.querySelector('#contenu .indicateurs-resultats');
  const jour = Donnees.aujourdhui();
  const p = Indicateurs.periode(zone.dataset.periode, jour, zone.dataset.du, zone.dataset.au);
  const filtres = { criticite: zone.dataset.criticite || '', atelier: zone.dataset.atelier || '' };
  const a = (v, d) => (v === null || v === undefined ? null : Math.round(v * Math.pow(10, d)) / Math.pow(10, d));
  const repere = (id) => { const e = Donnees.trouver('equipements', id); return (e && e.repere) || id; };
  const ctx = Indicateurs.interne.contexte();
  const garderA = (id) => { const e = ctx.equipements.get(id); return !filtres.atelier || (e && Indicateurs.interne.passeFiltres(e, { atelier: filtres.atelier }, ctx)); };
  const lundi = Planning.lundiDe(jour);
  const dateFr = (iso) => iso.slice(8, 10) + '/' + iso.slice(5, 7) + '/' + iso.slice(0, 4);
  const nom = (t) => ((t.prenom || '') + ' ' + (t.nom || '')).trim() || t.id;
  const resultatA = (cle) => Indicateurs.mtbfMttrCriticiteA(p).filter((l) => garderA(l.equipementId))
    .map((l) => [repere(l.equipementId), l[cle].valeur === null ? l[cle].raison : a(l[cle].valeur, 1)]);
  return {
    'pareto-pannes': Indicateurs.paretoPannes(p, 10, filtres).map((l) => [repere(l.equipementId), l.valeur, a(l.cumulPct, 1)]),
    'pareto-arrets': Indicateurs.paretoArrets(p, 10, filtres).map((l) => [repere(l.equipementId), a(l.valeur, 1), a(l.cumulPct, 1)]),
    'heures-mois': Indicateurs.heuresParMois(p.fin.slice(0, 7), 12, filtres)
      .map((l) => [l.mois.slice(5, 7) + '/' + l.mois.slice(0, 4), a(l.correctif, 1), a(l.preventif, 1), a(l.autres, 1)]),
    'mtbf-a': resultatA('mtbf'),
    'mttr-a': resultatA('mttr'),
    'causes': Indicateurs.causes(p, filtres).map((l) => [l.code, l.libelle, l.nombre]),
    'charge': [].concat(...Indicateurs.chargeCapacite(lundi, 4).map((l) => l.semaines.map((s) =>
      [nom(l.technicien), dateFr(s.lundi), a(s.charge, 1), a(s.capacite, 1)]))),
  };
}"""

LIRE_TABLEAUX_JS = """() => {
  const resultat = {};
  document.querySelectorAll('#contenu .indicateurs-graphique').forEach((carte) => {
    const lignes = Array.from(carte.querySelectorAll('.vue-tableau tbody tr')).filter((tr) => !tr.querySelector('.vide-table'));
    resultat[carte.dataset.graphique] = lignes.map((tr) => Array.from(tr.cells).map((td) => td.textContent.trim()));
  });
  return resultat;
}"""

LIRE_OPTIONS_JS = """() => {
  const resultat = {};
  document.querySelectorAll('#contenu .indicateurs-graphique').forEach((carte) => {
    const zone = carte.querySelector('.graph');
    const instance = zone && typeof echarts !== 'undefined' ? echarts.getInstanceByDom(zone) : null;
    if (!instance) { resultat[carte.dataset.graphique] = null; return; }
    const option = instance.getOption();
    const axes = [].concat(option.xAxis || [], option.yAxis || []);
    resultat[carte.dataset.graphique] = {
      axesValeurs: axes.filter((axe) => axe.type === 'value').length,
      series: option.series.map((s) => ({ type: s.type, nom: s.name, couleur: (s.itemStyle && s.itemStyle.color) || null })),
      legende: Array.from(carte.querySelectorAll('.legende > span')).map((s) => s.textContent.trim()),
      svg: Boolean(zone.querySelector('svg')), largeur: zone.clientWidth,
    };
  });
  return resultat;
}"""


def nombre_fr(texte):
    """Nombre lu dans un texte affiché à la française (« 1 234,5 h », « 95,3 % », « 12,00 € »), ou None."""
    propre = re.sub(r"[\s\u00A0\u202F]", "", texte or "")
    propre = re.sub(r"(h|%|€)$", "", propre).replace(",", ".")
    try:
        return float(propre)
    except ValueError:
        return None


# --- Daltonisme : simulation de Machado, Oliveira et Fernandes (2009), sévérité 1, écart OKLab ×100 ----

MACHADO = {
    "protanopie": [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
    "deutéranopie": [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]],
}


def _lineaire(hexa):
    hexa = hexa.lstrip("#")
    valeurs = [int(hexa[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in valeurs]


def _oklab(rgb):
    r, g, b = rgb
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = (math.copysign(abs(x) ** (1 / 3), x) for x in (l, m, s))
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def _simuler(hexa, vision):
    rgb = _lineaire(hexa)
    if vision is None:
        return rgb
    matrice = MACHADO[vision]
    return [max(0.0, min(1.0, sum(matrice[i][j] * rgb[j] for j in range(3)))) for i in range(3)]


def ecart_couleurs(a, b, vision=None):
    """Écart OKLab (×100) entre deux couleurs, vues par une vision simulée (None = vision normale)."""
    return 100 * math.dist(_oklab(_simuler(a, vision)), _oklab(_simuler(b, vision)))


def lire_csv(dossier, nom):
    texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte), delimiter=";"))


def largeur_png(octets):
    """Largeur (pixels) lue dans l'en-tête IHDR d'un PNG."""
    return struct.unpack(">I", octets[16:20])[0]


class CasIndicateurs(CasNavigateur):
    """Outils communs : ouvrir l'écran, attendre les graphiques, comparer aux règles."""

    def attendre_graphiques(self, page=None):
        page = page or self.page
        page.wait_for_function(ATTENDRE_GRAPHIQUES_JS, arg=len(GRAPHIQUES), timeout=20000)

    def verifier_instruments(self, page=None):
        page = page or self.page
        attendus = page.evaluate(ATTENDUS_INSTRUMENTS_JS)
        lus = page.evaluate(LIRE_INSTRUMENTS_JS)
        self.assertEqual(sorted(lus), sorted(INSTRUMENTS))
        for cle, (_, unite) in INSTRUMENTS.items():
            with self.subTest(instrument=cle):
                valeur = attendus["valeurs"][cle]
                if valeur is None:
                    self.assertEqual(lus[cle]["valeur"], "")
                    self.assertIn(attendus["raisons"][cle].lower(), lus[cle]["texte"].lower())
                else:
                    self.assertTrue(math.isclose(float(lus[cle]["valeur"]), valeur, abs_tol=1e-9),
                                    "%s : %r ≠ %r" % (cle, lus[cle]["valeur"], valeur))
                    self.assertTrue(math.isclose(nombre_fr(lus[cle]["chiffre"]), valeur, abs_tol=1e-9),
                                    "%s affiché %r" % (cle, lus[cle]["chiffre"]))
                    if unite:
                        self.assertTrue(lus[cle]["chiffre"].strip().endswith(unite), lus[cle]["chiffre"])
        # « dont attente de pièces » sous le MTTR, seulement quand elle est calculable (D36)
        attente = attendus["attente"]
        if attente["valeur"] is None:
            # Rien sous le MTTR ; la raison va dans l'encadré « Comprendre »
            self.assertIsNone(lus["mttr"]["attente"])
            self.assertIn(attente["raison"], page.locator("#contenu .indicateurs-comprendre").text_content())
        else:
            texte = lus["mttr"]["attente"]
            self.assertIsNotNone(texte, "« dont attente de pièces » absent sous le MTTR")
            self.assertIn("dont attente de pièces", texte)
            nombres = re.findall(r"\d[\d\u00A0\u202F ]*(?:,\d+)?", texte)
            self.assertTrue(math.isclose(nombre_fr(nombres[0]), attente["valeur"], abs_tol=1e-9), texte)
            self.assertIn("sur %d panne" % attente["effectif"], texte)
            self.assertIn("historique complet", texte)
        return attendus

    def sans_nan(self, page=None):
        page = page or self.page
        textes = page.evaluate("() => [document.querySelector('#contenu').innerText, document.querySelector('#contenu').textContent]")
        for texte in textes:
            for interdit in ("NaN", "Infinity", "undefined"):
                self.assertNotIn(interdit, texte)

    def sans_defilement_horizontal(self, page, contexte):
        largeurs = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        self.assertLessEqual(largeurs[0], largeurs[1], "défilement horizontal (%s) : %r" % (contexte, largeurs))

    def verifier_csv(self, page, graphique):
        carte = page.locator('#contenu .indicateurs-graphique[data-graphique="%s"]' % graphique)
        with page.expect_download() as attente:
            carte.locator('button[data-export="csv"]').click()
        telechargement = attente.value
        self.assertTrue(telechargement.suggested_filename.endswith(".csv"), telechargement.suggested_filename)
        octets = Path(telechargement.path()).read_bytes()
        self.assertTrue(octets.startswith(b"\xef\xbb\xbf"), octets[:10])
        texte = octets[3:].decode("utf-8")
        self.assertTrue(texte.endswith("\r\n"))
        self.assertNotIn("\n", texte.replace("\r\n", ""))
        lignes = texte[:-2].split("\r\n")
        nb_colonnes = len(lignes[0].split(";"))
        self.assertGreaterEqual(nb_colonnes, 2, lignes[0])
        for ligne in lignes:
            self.assertEqual(len(ligne.split(";")), nb_colonnes, ligne)
        return lignes

    def verifier_png(self, page, graphique):
        carte = page.locator('#contenu .indicateurs-graphique[data-graphique="%s"]' % graphique)
        largeur = carte.locator(".graph").evaluate("(el) => el.clientWidth")
        with page.expect_download() as attente:
            carte.locator('button[data-export="image"]').click()
        telechargement = attente.value
        self.assertTrue(telechargement.suggested_filename.endswith(".png"), telechargement.suggested_filename)
        octets = Path(telechargement.path()).read_bytes()
        self.assertTrue(octets.startswith(SIGNATURE_PNG), octets[:10])
        self.assertEqual(largeur_png(octets), 2 * largeur)


class TestIndicateursServeur(CasIndicateurs):
    """Mode serveur : serveur.py sur une copie du jeu de démo, profil responsable."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serveur = ServeurPrevo()
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)

    def ouvrir(self, requete="", page=None, contexte=None, profil="responsable", **options):
        page = page or self.page
        preregler_profil(contexte or self.contexte, profil, options.pop("nom", "Responsable"), **options)
        page.goto(self.serveur.url + "/#/indicateurs" + requete)
        attendre_pret(page)
        page.wait_for_load_state("networkidle")       # écritures du démarrage (préventif) finies
        return page

    # -- echarts -------------------------------------------------------------------------------

    def test_echarts_absent_avant_l_ecran_puis_charge_sept_graphiques_en_svg(self):
        preregler_profil(self.contexte, "responsable", "Responsable")
        self.page.goto(self.serveur.url + "/#/accueil")
        attendre_pret(self.page)
        self.assertEqual(self.page.evaluate("typeof echarts"), "undefined")
        # Entrée de menu « Indicateurs » (responsable)
        self.assertEqual(self.page.locator('#menu a[href="#/indicateurs"]').count(), 1)
        self.page.click('#menu a[href="#/indicateurs"]')
        self.page.wait_for_selector("#contenu .indicateurs")
        self.attendre_graphiques()
        self.assertEqual(self.page.evaluate("typeof echarts"), "object")
        self.assertEqual(self.page.locator("script[src*='echarts']").count(), 1)
        options = self.page.evaluate(LIRE_OPTIONS_JS)
        self.assertEqual(sorted(options), sorted(GRAPHIQUES))
        rendus = [cle for cle, option in options.items() if option and option["svg"]]
        self.assertGreaterEqual(len(rendus), 5, options)      # le jeu de démo remplit au moins 5 graphiques
        self.assertEqual(self.page.locator("#contenu .indicateurs-graphique .vue-tableau summary").all_inner_texts(),
                         ["Voir les valeurs"] * len(GRAPHIQUES))

    def test_echarts_echec_message_dans_chaque_carte_et_tableaux_visibles(self):
        self.autoriser_erreur("Failed to load resource")
        self.autoriser_erreur("ERR_FAILED")
        self.page.route(re.compile(r".*/js/lib/echarts\.min\.js$"), lambda route: route.abort())
        self.ouvrir()
        self.attendre_graphiques()
        etats = self.page.eval_on_selector_all("#contenu .indicateurs-graphique", "(cs) => cs.map((c) => c.dataset.etat)")
        self.assertIn("erreur", etats)
        for carte in self.page.locator('#contenu .indicateurs-graphique[data-etat="erreur"]').all():
            self.assertIn("pas pu être chargée", carte.inner_text())
            self.assertTrue(carte.locator(".vue-tableau").evaluate("(d) => d.open"))
            self.assertTrue(carte.locator(".vue-tableau table").is_visible())
        # Le bandeau d'instruments et le tableau par équipement ne dépendent pas d'ECharts
        self.verifier_instruments()

    # -- instruments ---------------------------------------------------------------------------

    def test_instruments_egaux_aux_regles_arrondies_raisons_effectifs_et_comprendre(self):
        self.ouvrir()
        self.attendre_graphiques()
        attendus = self.verifier_instruments()
        self.assertEqual(attendus["periode"]["code"], "12-mois")
        # Effectifs visibles : le nombre de pannes comptées figure dans le bandeau
        self.assertIn("%d panne" % attendus["pannes"], self.page.inner_text("#contenu .indicateurs-instruments"))
        comprendre = self.page.locator("#contenu .indicateurs-comprendre")
        self.assertEqual(comprendre.count(), 1)
        comprendre.locator("summary").click()
        texte = comprendre.inner_text()
        for mot in ("MTBF", "MTTR", "Disponibilité", "attente de pièces", "non calculable"):
            self.assertIn(mot, texte)
        self.sans_nan()

    # -- periode -------------------------------------------------------------------------------

    def test_periode_changer_la_periode_change_les_valeurs_et_l_adresse(self):
        self.ouvrir()
        self.attendre_graphiques()
        douze = self.page.evaluate(LIRE_INSTRUMENTS_JS)
        self.page.select_option("#indicateurs-periode", "3-mois")
        self.page.wait_for_function("document.querySelector('#contenu .indicateurs-resultats').dataset.periode === '3-mois'")
        self.attendre_graphiques()
        self.assertIn("periode=3-mois", self.page.evaluate("location.hash"))
        attendus = self.verifier_instruments()
        self.assertEqual(attendus["periode"]["code"], "3-mois")
        trois = self.page.evaluate(LIRE_INSTRUMENTS_JS)
        self.assertNotEqual({c: v["valeur"] for c, v in douze.items()}, {c: v["valeur"] for c, v in trois.items()})
        self.sans_nan()

        # Période choisie par l'adresse : du … au …
        aujourdhui = self.page.evaluate("Donnees.aujourdhui()")
        du = "%d-01-01" % int(aujourdhui[:4])
        self.page.goto(self.serveur.url + "/#/indicateurs?periode=du-au&du=%s&au=%s" % (du, aujourdhui))
        self.page.wait_for_function("document.querySelector('#contenu .indicateurs-resultats') "
                                    "&& document.querySelector('#contenu .indicateurs-resultats').dataset.periode === 'du-au'")
        self.attendre_graphiques()
        attendus = self.verifier_instruments()
        self.assertEqual((attendus["periode"]["debut"], attendus["periode"]["fin"]), (du, aujourdhui))
        self.assertTrue(self.page.is_visible("#indicateurs-du"))
        self.assertEqual(self.page.input_value("#indicateurs-du"), du)

    def test_periode_filtres_criticite_et_atelier(self):
        self.ouvrir()
        atelier = self.page.evaluate("""() => { const ateliers = Donnees.lignes('localisations').filter((l) => l.type === 'atelier');
            const ctx = Indicateurs.interne.contexte();
            const avecA = ateliers.find((l) => Donnees.lignes('equipements').some((e) => e.criticite === 'A'
              && Indicateurs.interne.passeFiltres(e, { atelier: l.id }, ctx)));
            return (avecA || ateliers[0]).id; }""")
        self.page.goto(self.serveur.url + "/#/indicateurs?criticite=A&atelier=" + atelier)
        self.page.wait_for_function("document.querySelector('#contenu .indicateurs-resultats') "
                                    "&& document.querySelector('#contenu .indicateurs-resultats').dataset.atelier !== ''")
        self.attendre_graphiques()
        self.assertEqual(self.page.input_value("#indicateurs-criticite"), "A")
        self.assertEqual(self.page.input_value("#indicateurs-atelier"), atelier)
        self.verifier_instruments()
        # Le tableau par équipement ne garde que les équipements filtrés
        attendus = self.page.evaluate("""(atelier) => { const ctx = Indicateurs.interne.contexte();
            return Donnees.lignes('equipements').filter((e) => Indicateurs.interne.estSuivi(e)
              && Indicateurs.interne.passeFiltres(e, { criticite: 'A', atelier }, ctx)).map((e) => e.id).sort(); }""", atelier)
        lus = self.page.eval_on_selector_all("#contenu .indicateurs-equipements tbody a[href^='#/equipement/']",
                                             "(liens) => liens.map((a) => decodeURIComponent(a.getAttribute('href').split('/').pop())).sort()")
        self.assertEqual(lus, attendus)
        self.page.select_option("#indicateurs-criticite", "")
        self.page.wait_for_function("document.querySelector('#contenu .indicateurs-resultats').dataset.criticite === ''")
        self.assertNotIn("criticite=A", self.page.evaluate("location.hash"))
        self.verifier_instruments()

    # -- equipements ---------------------------------------------------------------------------

    def test_equipements_non_calculable_avec_raison_tri_par_clic_et_lien_vers_la_fiche(self):
        self.ouvrir()
        tableau = self.page.locator("#contenu .indicateurs-equipements")
        tableau.wait_for()
        suivis = self.page.evaluate("""() => Donnees.lignes('equipements').filter((e) => Indicateurs.interne.estSuivi(e)).map((e) => e.id)""")
        self.assertEqual(tableau.locator("tbody tr").count(), len(suivis))
        sans_heures = self.page.evaluate("""() => Donnees.lignes('equipements').filter((e) => Indicateurs.interne.estSuivi(e)
            && !(Donnees.nombre(e.heures_fonct_jour) > 0)).map((e) => e.id)""")
        self.assertGreater(len(sans_heures), 0, "le jeu de démo doit avoir un équipement sans heures de fonctionnement")
        for equipement_id in sans_heures:
            ligne = tableau.locator("tbody tr", has=self.page.locator('a[href="#/equipement/%s"]' % equipement_id))
            texte = ligne.inner_text()
            self.assertIn("non calculable", texte)
            self.assertIn("heures de fonctionnement par jour non renseignées", texte)

        # Tri par clic sur « Pannes » : les deux sens, chacun vérifié sur la colonne affichée
        entetes = [t.strip() for t in tableau.locator("thead th").all_inner_texts()]
        colonne = next(rang for rang, texte in enumerate(entetes) if texte.startswith("Pannes"))
        sens_vus = set()
        for _ in range(2):
            tableau.locator("thead th button.tri", has_text="Pannes").click()
            sens = tableau.locator("thead th").nth(colonne).get_attribute("aria-sort")
            valeurs = [nombre_fr(t) for t in tableau.locator("tbody tr").evaluate_all(
                "(lignes, c) => lignes.map((l) => l.cells[c].textContent)", colonne)]
            self.assertEqual(valeurs, sorted(valeurs, reverse=(sens == "descending")), sens)
            sens_vus.add(sens)
        self.assertEqual(sens_vus, {"ascending", "descending"})

        # Lien vers la fiche de l'équipement
        lien = tableau.locator("tbody a[href^='#/equipement/']").first
        cible = lien.get_attribute("href")
        lien.click()
        self.page.wait_for_function("(h) => location.hash === h", arg=cible)

    # -- graphiques ----------------------------------------------------------------------------

    def test_graphiques_voir_les_valeurs_egaux_aux_series_des_regles(self):
        self.ouvrir()
        self.attendre_graphiques()
        attendus = self.page.evaluate(ATTENDUS_GRAPHIQUES_JS)
        lus = self.page.evaluate(LIRE_TABLEAUX_JS)
        self.assertEqual(sorted(lus), sorted(GRAPHIQUES))
        for graphique in GRAPHIQUES:
            with self.subTest(graphique=graphique):
                self.assertEqual(len(lus[graphique]), len(attendus[graphique]), lus[graphique])
                for ligne_lue, ligne_attendue in zip(lus[graphique], attendus[graphique]):
                    self.assertEqual(len(ligne_lue), len(ligne_attendue), ligne_lue)
                    for lu, attendu in zip(ligne_lue, ligne_attendue):
                        if attendu is None:
                            self.assertIn(lu, ("", "–"))
                        elif isinstance(attendu, (int, float)):
                            self.assertTrue(math.isclose(nombre_fr(lu), attendu, abs_tol=1e-9), "%r ≠ %r" % (lu, attendu))
                        else:
                            self.assertEqual(lu, attendu)
        # Le jeu de démo remplit ces graphiques (sinon le test ne prouverait rien)
        for graphique in ("pareto-pannes", "pareto-arrets", "heures-mois", "mtbf-a", "causes", "charge"):
            self.assertGreater(len(attendus[graphique]), 0, graphique)

    def test_graphiques_un_seul_axe_de_valeurs_legende_des_deux_series_et_palette_daltonisme(self):
        self.ouvrir()
        self.attendre_graphiques()
        options = self.page.evaluate(LIRE_OPTIONS_JS)
        self.assertGreater(len([o for o in options.values() if o]), 0)
        plusieurs_series = 0
        for graphique, option in options.items():
            if option is None:
                continue
            with self.subTest(graphique=graphique):
                self.assertTrue(option["svg"], "rendu SVG attendu")
                self.assertLessEqual(option["axesValeurs"], 1, "deux axes de valeurs")
                series = option["series"]
                if len(series) >= 2:
                    plusieurs_series += 1
                    self.assertEqual(option["legende"], [s["nom"] for s in series])
                else:
                    self.assertEqual(option["legende"], [])
                couleurs = [s["couleur"].upper() for s in series if s["type"] == "bar"]
                for couleur in couleurs:
                    self.assertNotIn(couleur, COULEURS_STATUT)
                # Séries voisines (barres côte à côte ou empilées) : distinctes en vision normale et
                # sous deutéranopie et protanopie simulées.
                for a, b in zip(couleurs, couleurs[1:]):
                    self.assertGreaterEqual(ecart_couleurs(a, b), SEUIL_VISION_NORMALE, (a, b))
                    for vision in MACHADO:
                        self.assertGreaterEqual(ecart_couleurs(a, b, vision), SEUIL_DALTONISME, (a, b, vision))
                # Une marque de référence (capacité) se distingue de chaque barre
                for marque in (s["couleur"] for s in series if s["type"] != "bar"):
                    for couleur in couleurs:
                        for vision in (None, *MACHADO):
                            self.assertGreaterEqual(ecart_couleurs(marque, couleur, vision), SEUIL_DALTONISME,
                                                    (marque, couleur, vision))
        self.assertGreaterEqual(plusieurs_series, 2, "heures par mois et charge ont plusieurs séries")

    # -- exports -------------------------------------------------------------------------------

    def test_exports_csv_bom_point_virgule_crlf_point_decimal_et_png_double_largeur(self):
        self.ouvrir()
        self.attendre_graphiques()
        lignes = self.verifier_csv(self.page, "heures-mois")
        attendus = self.page.evaluate(ATTENDUS_GRAPHIQUES_JS)["heures-mois"]
        self.assertEqual(len(lignes), 1 + len(attendus))
        decimaux = 0
        for ligne, attendu in zip(lignes[1:], attendus):
            cellules = ligne.split(";")
            for cellule, valeur in zip(cellules[1:], attendu[1:]):
                self.assertNotIn(",", cellule)
                self.assertTrue(math.isclose(float(cellule), valeur, abs_tol=1e-9), (cellule, valeur))
                decimaux += "." in cellule
        self.assertGreater(decimaux, 0, "au moins une valeur décimale, écrite avec un point")
        self.verifier_png(self.page, "heures-mois")
        self.verifier_png(self.page, "charge")

    # -- profils -------------------------------------------------------------------------------

    def test_profils_technicien_et_demandeur_renvoyes_a_l_accueil(self):
        technicien = next(t for t in lire_csv(self.serveur.dossier, "techniciens.csv") if t["actif"] != "0")
        for profil, options in (("technicien", {"nom": technicien["nom"], "technicien_id": technicien["id"]}),
                                ("demandeur", {"nom": "Paul Martin"})):
            with self.subTest(profil=profil):
                contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
                try:
                    page = contexte.new_page()
                    self.surveiller(page)
                    self.ouvrir(page=page, contexte=contexte, profil=profil, **options)
                    page.wait_for_function("location.hash === '#/accueil'")
                    self.assertEqual(page.locator("#contenu .indicateurs").count(), 0)
                    self.assertEqual(page.locator('#menu a[href="#/indicateurs"]').count(), 0)
                    self.assertEqual(page.evaluate("typeof echarts"), "undefined")
                finally:
                    contexte.close()

    # -- largeurs ------------------------------------------------------------------------------

    def test_largeurs_1440_et_375_sans_defilement_horizontal_zones_tactiles(self):
        self.page.set_viewport_size({"width": 1440, "height": 900})
        self.ouvrir()
        self.attendre_graphiques()
        self.sans_defilement_horizontal(self.page, "1440 px")
        # Redimensionnement suivi : chaque dessin SVG reprend la largeur de sa zone
        largeurs_svg = """() => Array.from(document.querySelectorAll('#contenu .indicateurs-graphique .graph'))
            .filter((z) => z.querySelector('svg')).map((z) => [z.clientWidth, Math.round(z.querySelector('svg').getBoundingClientRect().width)])"""
        avant = self.page.evaluate(largeurs_svg)
        self.page.set_viewport_size({"width": 1000, "height": 900})
        self.page.wait_for_function("(js) => eval(js)().every(([zone, svg]) => Math.abs(zone - svg) <= 1)", arg=largeurs_svg)
        apres = self.page.evaluate(largeurs_svg)
        self.assertNotEqual([z for z, _ in avant], [z for z, _ in apres])
        self.sans_defilement_horizontal(self.page, "1000 px")
        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 375, "height": 812},
                                               is_mobile=True, has_touch=True, device_scale_factor=2)
        try:
            telephone = contexte.new_page()
            self.surveiller(telephone)
            self.ouvrir(page=telephone, contexte=contexte)
            self.attendre_graphiques(telephone)
            self.assertTrue(telephone.evaluate("UI.estTelephone()"))
            self.sans_defilement_horizontal(telephone, "375 px")
            telephone.locator("#contenu .indicateurs-comprendre summary").click()
            for details in telephone.locator("#contenu .vue-tableau summary").all():
                details.click()
            self.sans_defilement_horizontal(telephone, "375 px, tableaux ouverts")
            self.assertEqual(telephone.evaluate(PETITES_ZONES_JS), [])
            self.sans_nan(telephone)
        finally:
            contexte.close()

    # -- echappement ---------------------------------------------------------------------------

    def test_echappement_textes_des_donnees_jamais_interpretes(self):
        # Une cause, un repère et un atelier contenant du HTML s'affichent tels quels (axes, tableaux,
        # résumé) : aucun élément n'est créé. Modification EN MÉMOIRE seulement (rien n'est écrit).
        self.ouvrir()
        self.attendre_graphiques()
        piege = '<b id="piege">piège</b>'
        atelier = self.page.evaluate("""(piege) => {
            const p = Indicateurs.periode('12-mois', Donnees.aujourdhui());
            const code = Indicateurs.causes(p, {}).find((c) => c.code).code;
            Donnees.lignes('codes_defaillance').find((c) => c.famille === 'cause' && c.code === code).libelle = piege;
            Donnees.trouver('equipements', Indicateurs.paretoPannes(p, 10, {})[0].equipementId).repere = piege;
            const atelier = Donnees.lignes('localisations').find((l) => l.type === 'atelier');
            atelier.libelle = piege;
            return atelier.id; }""", piege)
        self.page.evaluate("(atelier) => App.naviguer('#/indicateurs?atelier=' + atelier)", atelier)
        self.page.wait_for_function("document.querySelector('#contenu .indicateurs-resultats') "
                                    "&& document.querySelector('#contenu .indicateurs-resultats').dataset.atelier !== ''")
        self.attendre_graphiques()
        self.assertEqual(self.page.locator("#piege").count(), 0)
        self.assertIn(piege, self.page.inner_text("#contenu .indicateurs-resume"))
        # Sans filtre (même page, données gardées en mémoire) : le repère et la cause piégés
        # sont dans les axes, les tableaux et les infobulles possibles
        self.page.evaluate("App.naviguer('#/indicateurs?periode=12-mois')")
        self.page.wait_for_function("document.querySelector('#contenu .indicateurs-resultats') "
                                    "&& document.querySelector('#contenu .indicateurs-resultats').dataset.atelier === ''")
        self.attendre_graphiques()
        self.assertEqual(self.page.locator("#piege").count(), 0)
        textes = self.page.locator("#contenu .indicateurs-equipements").text_content()
        self.assertIn(piege, textes)
        tableaux = self.page.evaluate(LIRE_TABLEAUX_JS)
        for graphique in ("causes", "pareto-pannes"):
            self.assertTrue(any(piege in cellule for ligne in tableaux[graphique] for cellule in ligne), graphique)
        # Le texte des axes (SVG) est du texte, pas du balisage
        self.assertTrue(self.page.evaluate("""() => Array.from(document.querySelectorAll('#contenu .graph svg text'))
            .some((t) => t.textContent.includes('<b id='))"""))

    # -- rapports ------------------------------------------------------------------------------

    def test_rapports_onglet_rapports_mensuels(self):
        self.ouvrir("?onglet=rapports")
        panneau = self.page.locator('#contenu .panneau-onglet[data-onglet="rapports"]')
        panneau.wait_for()
        self.assertTrue(panneau.is_visible())
        if not self.page.evaluate("typeof Rapport.afficherOnglet === 'function'"):
            self.assertIn("Les rapports mensuels arrivent avec la tâche suivante", panneau.inner_text())
        # Retour au tableau de bord : l'adresse suit l'onglet, les graphiques se dessinent
        self.page.click('#contenu .onglet[data-onglet="tableau"]')
        self.assertIn("onglet=tableau", self.page.evaluate("location.hash"))
        self.attendre_graphiques()
        self.assertEqual(self.page.evaluate("typeof echarts"), "object")


class TestIndicateursDemo(CasIndicateurs):
    """Mode démo en file:// : ECharts à la demande, valeurs, exports."""

    def test_demo_echarts_a_la_demande_instruments_graphiques_et_exports(self):
        preregler_profil(self.contexte, "responsable", "Responsable")
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        self.assertEqual(self.page.evaluate("typeof echarts"), "undefined")
        self.page.evaluate("location.hash = '#/indicateurs'")
        self.page.wait_for_selector("#contenu .indicateurs")
        self.attendre_graphiques()
        self.assertEqual(self.page.evaluate("typeof echarts"), "object")
        self.verifier_instruments()
        attendus = self.page.evaluate(ATTENDUS_GRAPHIQUES_JS)
        lus = self.page.evaluate(LIRE_TABLEAUX_JS)
        for graphique in GRAPHIQUES:
            with self.subTest(graphique=graphique):
                self.assertEqual(len(lus[graphique]), len(attendus[graphique]))
        self.sans_nan()
        lignes = self.verifier_csv(self.page, "pareto-arrets")
        self.assertEqual(len(lignes), 1 + len(attendus["pareto-arrets"]))
        self.verifier_png(self.page, "pareto-pannes")


class TestSourcesDesIndicateurs(CasNavigateur):
    """Correction de relecture (D35) : chaque chiffre avec ses OT ; part du préventif en heures."""

    def test_liens_vers_les_ot_sources_et_heures_du_preventif(self):
        with ServeurPrevo() as serveur:
            preregler_profil(self.contexte, "responsable", "Responsable")
            self.page.goto(serveur.url + "/#/indicateurs?periode=12-mois")
            attendre_pret(self.page)
            self.page.wait_for_selector("[data-indicateur='mttr'] details.indicateurs-sources")
            attendu = self.page.evaluate("""() => { const g = Indicateurs.global(Indicateurs.periode('12-mois', Donnees.aujourdhui()), {}, Donnees.aujourdhui());
                return { mttr: g.mttr.ots.length, exclus: g.mttr.exclus.filter((e) => /^OT-/.test(e.id)).length, note: g.partPreventif.note }; }""")
            liens = self.page.evaluate("Array.from(document.querySelectorAll(\"[data-indicateur='mttr'] details.indicateurs-sources a[href^='#/ot/']\")).length")
            self.assertEqual(liens, min(attendu["mttr"], 40) + min(attendu["exclus"], 40))
            self.assertIn(attendu["note"], self.page.inner_text("[data-indicateur='part-preventif']"))
            self.assertIn(" h de préventif sur ", attendu["note"])


if __name__ == "__main__":
    unittest.main()
