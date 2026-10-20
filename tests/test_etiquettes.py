"""Tests des étiquettes QR par lot (tâche T45, ARCHITECTURE.md §15.6) : js/modules/parc-etiquettes.js
(complète l'objet Parc), écran #/parc/etiquettes et css/modules/etiquettes.css.

Familles (le nom du test le dit) :
    regles   : Parc.FORMATS_ETIQUETTES, Parc.equipementsPourEtiquettes (localisation ET ses
               sous-localisations, actifs hors rebut, filtres, tri par repère) et
               Parc.planchesEtiquettes (une planche A4 par lot de 24 ou de 8) ;
    serveur  : serveur.py sur une copie du jeu de démo. /api/info est remplacé par DEUX adresses
               réseau connues (le poste de test peut en avoir zéro, une ou plusieurs) : chaque QR,
               décodé par jsQR, est l'URL réseau de la fiche ; le choix de l'adresse écrit adresse_qr
               dans parametres.csv, relu au rechargement ;
    demo     : index.html en file:// (« Essayer avec les données de démo ») : QR « GMAO:<id> » et
               mention « lisible par la caméra de ce poste », aucun choix d'adresse ;
    impression : aperçu d'impression (émulation « print ») : seul #impression est imprimé, noir sur
               blanc, menu masqué ; planches de 210 × 297 mm ; format 24 = 3 × 8 étiquettes de
               70 × 37 mm, format 8 = 2 × 4 de 105 × 74 mm ; décalage en mm appliqué et mémorisé
               (localStorage prevo.etiquettes) ; PDF d'autant de pages A4 que de planches ;
    profils  : technicien et demandeur renvoyés à l'accueil, sans bouton dans le Parc ;
    telephone : 375 px : aucun défilement horizontal, zones tactiles d'au moins 48 px.

Aucun identifiant du jeu de démo n'est écrit en dur : la localisation testée (une localisation qui a
des sous-localisations) et les équipements attendus sont calculés ici, en Python, depuis les CSV.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_etiquettes.py" -v
"""
import csv
import io
import json
import math
import re
import unittest
import urllib.parse
from pathlib import Path

from commun import CasNavigateur, RACINE, ServeurPrevo, attendre_pret, preregler_profil, url_fichier

DOSSIER_DEMO = RACINE / "donnees" / "demo"
PX_PAR_MM = 96 / 25.4
FORMATS = {"24": {"colonnes": 3, "lignes": 8, "largeurMm": 70, "hauteurMm": 37},
           "8": {"colonnes": 2, "lignes": 4, "largeurMm": 105, "hauteurMm": 74}}
AVERTISSEMENT = ("si l'adresse IP ou le port du PC change, les étiquettes ne mènent plus à la fiche : "
                 "demandez une adresse fixe pour ce PC (réservation dans la box)")
MENTION_DOSSIER = "lisible par la caméra de ce poste"

# window.print() ouvrirait une boîte de dialogue : en test, un espion note seulement l'appel.
ESPION_IMPRESSION_JS = "window.print = function () { window.__impressions = (window.__impressions || 0) + 1; };"

# Chaque QR d'une zone (aperçu ou #impression) rendu sur un <canvas> puis décodé par jsQR.
DECODER_QR_JS = """async (selecteur) => {
  const resultats = [];
  for (const etiquette of document.querySelectorAll(selecteur + ' .etiquette')) {
    const svg = etiquette.querySelector('svg.qr-svg');
    let texte = null;
    if (svg) {
      const image = new Image();
      image.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(new XMLSerializer().serializeToString(svg));
      await image.decode();
      const toile = document.createElement('canvas');
      toile.width = 300; toile.height = 300;
      const contexte = toile.getContext('2d');
      contexte.drawImage(image, 0, 0, 300, 300);
      const code = jsQR(contexte.getImageData(0, 0, 300, 300).data, 300, 300);
      texte = code ? code.data : null;
    }
    const repere = etiquette.querySelector('.etiquette-repere');
    resultats.push({ id: etiquette.dataset.equipement, qr: texte, repere: repere ? repere.textContent.trim() : null });
  }
  return resultats;
}"""

# Planches d'une zone : taille et position (relative à la planche) de chaque étiquette, en px CSS ;
# « contenu_dedans » : le QR et le repère tiennent dans l'étiquette.
MESURER_PLANCHES_JS = """(selecteur) => Array.from(document.querySelectorAll(selecteur + ' .planche-etiquettes')).map((planche) => {
  const p = planche.getBoundingClientRect();
  return { largeur: p.width, hauteur: p.height,
    etiquettes: Array.from(planche.querySelectorAll('.etiquette')).map((e) => {
      const r = e.getBoundingClientRect();
      const dedans = (el) => { if (!el) return false; const b = el.getBoundingClientRect();
        return b.width > 0 && b.left >= r.left - .5 && b.right <= r.right + .5 && b.top >= r.top - .5 && b.bottom <= r.bottom + .5; };
      return { x: r.left - p.left, y: r.top - p.top, largeur: r.width, hauteur: r.height,
               contenu_dedans: dedans(e.querySelector('svg.qr-svg')) && dedans(e.querySelector('.etiquette-repere')) };
    }) };
})"""

COULEURS_IMPRESSION_JS = """() => {
  const e = document.querySelector('#impression .etiquette');
  const repere = document.querySelector('#impression .etiquette-repere');
  const planche = document.querySelector('#impression .planche-etiquettes');
  return { texte: getComputedStyle(e).color, repere: getComputedStyle(repere).color,
           fond: getComputedStyle(planche).backgroundColor, corps: getComputedStyle(document.body).backgroundColor };
}"""

TRIE_PAR_REPERE_JS = """(reperes) => reperes.every((r, i) => i === 0
  || reperes[i - 1].localeCompare(r, 'fr', { numeric: true, sensitivity: 'base' }) <= 0)"""

# Même contrôle que tests/test_recette_lot1.py (PETITES_ZONES_JS) ; recopié ici : importer ce
# fichier de test ferait aussi lancer ses tests.
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


# ---------------------------------------------------------------------------
# Calculs indépendants sur les CSV (Python)
# ---------------------------------------------------------------------------

def lire_csv(dossier, nom):
    """Lignes (dictionnaires) d'un CSV de Prévo sur le disque (UTF-8 avec BOM, « ; »)."""
    texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte, newline=""), delimiter=";"))


def brut(valeur):
    """Valeur sans l'apostrophe de protection (ARCHITECTURE.md §3.2)."""
    return valeur[1:] if valeur.startswith("'") else valeur


def sous_arbre(localisations, racine):
    """Identifiants de la localisation `racine` et de toutes ses sous-localisations."""
    resultat = {racine}
    ajout = True
    while ajout:
        ajout = False
        for localisation in localisations:
            if localisation["parent_id"] in resultat and localisation["id"] not in resultat:
                resultat.add(localisation["id"])
                ajout = True
    return resultat


def equipements_attendus(dossier, localisation_id, criticite=""):
    """Équipements actifs hors rebut de la localisation et de ses sous-localisations : { id: repère }."""
    zone = sous_arbre(lire_csv(dossier, "localisations.csv"), localisation_id)
    return {e["id"]: brut(e["repere"]) or e["id"] for e in lire_csv(dossier, "equipements.csv")
            if e["actif"].strip() != "0" and e["statut"].strip() != "rebut"
            and e["localisation_id"] in zone and (not criticite or e["criticite"] == criticite)}


def choisir_localisations(dossier):
    """(localisation non racine qui a des sous-localisations, racine) : celles qui ont le plus
    d'équipements attendus, avec au moins un équipement rangé dans une sous-localisation."""
    localisations = lire_csv(dossier, "localisations.csv")
    equipements = lire_csv(dossier, "equipements.csv")
    parents = {l["parent_id"] for l in localisations if l["parent_id"]}

    def dans_une_sous_localisation(identifiant):
        zone = sous_arbre(localisations, identifiant) - {identifiant}
        return any(e["localisation_id"] in zone for e in equipements
                   if e["actif"].strip() != "0" and e["statut"].strip() != "rebut")

    candidates = [l["id"] for l in localisations if l["id"] in parents and dans_une_sous_localisation(l["id"])]
    assert candidates, "le jeu de démo n'a aucune localisation avec des sous-localisations équipées"
    nombre = lambda identifiant: len(equipements_attendus(dossier, identifiant))
    racines = [c for c in candidates if not next(l for l in localisations if l["id"] == c)["parent_id"]]
    internes = [c for c in candidates if c not in racines] or candidates
    return max(internes, key=nombre), max(racines or candidates, key=nombre)


def proche(valeur_px, attendue_mm, tolerance_px=0.75):
    return abs(valeur_px - attendue_mm * PX_PAR_MM) <= tolerance_px


# ---------------------------------------------------------------------------
# Base commune
# ---------------------------------------------------------------------------

class CasEtiquettes(CasNavigateur):

    def aller(self, route, page=None):
        page = page or self.page
        page.evaluate("(r) => { location.hash = r; }", route)
        if route.startswith("#/parc/etiquettes"):
            page.wait_for_selector("#etiquettes-apercu")
            page.wait_for_function("document.querySelector('#etiquettes-resume') !== null")
        else:
            page.wait_for_selector("#contenu .parc h1")

    def ids_apercu(self, page=None):
        page = page or self.page
        return page.eval_on_selector_all("#etiquettes-apercu .etiquette", "l => l.map(e => e.dataset.equipement)")

    def sans_defilement_horizontal(self, page, contexte):
        largeurs = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        self.assertLessEqual(largeurs[0], largeurs[1], "défilement horizontal (%s) : %r" % (contexte, largeurs))

    def verifier_etiquettes(self, page, selecteur, attendus, qr_attendu):
        """Une étiquette par équipement attendu, repère en clair, QR décodé = qr_attendu(id)."""
        lues = page.evaluate(DECODER_QR_JS, selecteur)
        ids = [l["id"] for l in lues]
        self.assertEqual(len(ids), len(set(ids)), "étiquette en double : %r" % ids)
        self.assertEqual(set(ids), set(attendus))
        for lue in lues:
            with self.subTest(equipement=lue["id"]):
                self.assertEqual(lue["repere"], attendus[lue["id"]])
                self.assertEqual(lue["qr"], qr_attendu(lue["id"]))
        self.assertTrue(page.evaluate(TRIE_PAR_REPERE_JS, [l["repere"] for l in lues]), [l["repere"] for l in lues])
        return lues

    def verifier_planches(self, page, selecteur, nombre, format_, haut_mm=0.0, gauche_mm=0.0):
        """Planches A4 en mm : nombre de planches, étiquettes par planche, tailles et positions."""
        gabarit = FORMATS[format_]
        par_planche = gabarit["colonnes"] * gabarit["lignes"]
        planches = page.evaluate(MESURER_PLANCHES_JS, selecteur)
        self.assertEqual(len(planches), math.ceil(nombre / par_planche))
        marge_haut = (297 - gabarit["lignes"] * gabarit["hauteurMm"]) / 2
        marge_gauche = (210 - gabarit["colonnes"] * gabarit["largeurMm"]) / 2
        for numero, planche in enumerate(planches):
            self.assertTrue(proche(planche["largeur"], 210, 1.0), planche["largeur"])
            self.assertTrue(proche(planche["hauteur"], 297, 1.5), planche["hauteur"])
            attendues = min(par_planche, nombre - numero * par_planche)
            self.assertEqual(len(planche["etiquettes"]), attendues)
            for rang, etiquette in enumerate(planche["etiquettes"]):
                colonne, ligne = rang % gabarit["colonnes"], rang // gabarit["colonnes"]
                with self.subTest(planche=numero, etiquette=rang):
                    self.assertTrue(proche(etiquette["largeur"], gabarit["largeurMm"]), etiquette)
                    self.assertTrue(proche(etiquette["hauteur"], gabarit["hauteurMm"]), etiquette)
                    self.assertTrue(proche(etiquette["x"], marge_gauche + gauche_mm + colonne * gabarit["largeurMm"]), etiquette)
                    self.assertTrue(proche(etiquette["y"], marge_haut + haut_mm + ligne * gabarit["hauteurMm"]), etiquette)
                    self.assertTrue(etiquette["contenu_dedans"], "QR ou repère hors de l'étiquette : %r" % etiquette)
        # Grille complète de la première planche quand elle est pleine : colonnes × lignes positions
        if nombre >= par_planche:
            premiere = planches[0]["etiquettes"]
            self.assertEqual(len({round(e["x"]) for e in premiere}), gabarit["colonnes"])
            self.assertEqual(len({round(e["y"]) for e in premiere}), gabarit["lignes"])
        return planches


# ---------------------------------------------------------------------------
# Mode serveur (adresses réseau remplacées par deux adresses connues)
# ---------------------------------------------------------------------------

class TestEtiquettesServeur(CasEtiquettes):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serveur = ServeurPrevo()
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)

    def adresses(self, serveur):
        return ["http://192.168.50.10:%d/" % serveur.port, "http://10.20.30.40:%d/" % serveur.port]

    def ouvrir(self, serveur=None, profil="responsable", route=None, page=None, contexte=None, **profil_extra):
        """Ouvre l'application ; /api/info répond avec les deux adresses de self.adresses()."""
        serveur = serveur or self.serveur
        page = page or self.page
        contexte = contexte or self.contexte
        corps = json.dumps({"port": serveur.port, "adresse_locale": "http://localhost:%d/" % serveur.port,
                            "adresses_reseau": self.adresses(serveur)})
        page.route(re.compile(r".*/api/info$"),
                   lambda route_: route_.fulfill(status=200, content_type="application/json; charset=utf-8", body=corps))
        preregler_profil(contexte, profil, **profil_extra)
        page.goto(serveur.url + "/")
        attendre_pret(page)
        if route:
            self.aller(route, page)
        return page

    def imprimer_en_pdf(self, page):
        """PDF de Chromium ; window.__etiquettesImprimees = étiquettes présentes à « beforeprint »."""
        page.evaluate("""() => { window.__etiquettesImprimees = null;
            window.addEventListener('beforeprint', () => {
              window.__etiquettesImprimees = document.querySelectorAll('#impression .etiquette').length; }, { once: true }); }""")
        return page.pdf(prefer_css_page_size=True, print_background=True)

    def url_attendue(self, base, identifiant):
        return base.rstrip("/") + "/#/equipement/" + urllib.parse.quote(identifiant, safe="")

    # -- regles ---------------------------------------------------------------------------------

    def test_regles_formats_selection_par_localisation_et_sous_localisations_tri_et_planches(self):
        dossier = self.serveur.dossier
        localisation, racine = choisir_localisations(dossier)
        page = self.ouvrir()
        self.assertEqual(page.evaluate("Parc.FORMATS_ETIQUETTES"), FORMATS)

        attendus = equipements_attendus(dossier, localisation)
        lus = page.evaluate("(l) => Parc.equipementsPourEtiquettes({ localisationId: l }).map(e => e.id)", localisation)
        self.assertEqual(sorted(lus), sorted(attendus))
        reperes = page.evaluate("(l) => Parc.equipementsPourEtiquettes({ localisationId: l }).map(e => e.repere || e.id)", localisation)
        self.assertTrue(page.evaluate(TRIE_PAR_REPERE_JS, reperes), reperes)

        # Criticité : sous-ensemble ; ids : intersection, sans les inactifs ni le rebut
        for criticite in ("A", "B", "C"):
            with self.subTest(criticite=criticite):
                lus = page.evaluate("([l, c]) => Parc.equipementsPourEtiquettes({ localisationId: l, criticite: c }).map(e => e.id)",
                                    [localisation, criticite])
                self.assertEqual(sorted(lus), sorted(equipements_attendus(dossier, localisation, criticite)))
        tous = lire_csv(dossier, "equipements.csv")
        exclus = [e["id"] for e in tous if e["actif"].strip() == "0" or e["statut"].strip() == "rebut"]
        choisis = sorted(attendus)[:2] + exclus
        lus = page.evaluate("(ids) => Parc.equipementsPourEtiquettes({ ids }).map(e => e.id)", choisis)
        self.assertEqual(sorted(lus), sorted(attendus)[:2])
        tout_le_parc = page.evaluate("() => Parc.equipementsPourEtiquettes({}).length")
        self.assertEqual(tout_le_parc, len([e for e in tous if e["actif"].strip() != "0" and e["statut"].strip() != "rebut"]))

        # Planches : une section par lot de 24 ou de 8, une étiquette par équipement
        nombre = len(equipements_attendus(dossier, racine))
        for format_, par_planche in (("24", 24), ("8", 8)):
            with self.subTest(format=format_):
                compte = page.evaluate("""([l, f]) => { const zone = document.createElement('div');
                    zone.innerHTML = String(Parc.planchesEtiquettes(Parc.equipementsPourEtiquettes({ localisationId: l }), f, { haut: 0, gauche: 0 }));
                    return [zone.querySelectorAll('.planche-etiquettes').length, zone.querySelectorAll('.etiquette').length,
                            zone.querySelectorAll('.etiquette svg.qr-svg').length]; }""", [racine, format_])
                self.assertEqual(compte, [math.ceil(nombre / par_planche), nombre, nombre])

    # -- serveur : écran, QR, adresse ----------------------------------------------------------------

    def test_serveur_bouton_du_parc_ecran_qr_reseau_et_adresse_choisie_puis_relue(self):
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            localisation, _ = choisir_localisations(dossier)
            attendus = equipements_attendus(dossier, localisation)
            premiere, seconde = self.adresses(serveur)
            page = self.ouvrir(serveur, route="#/parc")

            # Bouton « Imprimer des étiquettes » dans le Parc (responsable)
            bouton = page.locator("#contenu a[href='#/parc/etiquettes']")
            self.assertEqual(bouton.count(), 1)
            self.assertIn("Imprimer des étiquettes", bouton.inner_text())
            bouton.click()
            page.wait_for_selector("#etiquettes-apercu")
            self.assertEqual(page.evaluate("location.hash"), "#/parc/etiquettes")

            self.aller("#/parc/etiquettes?localisation=" + localisation)
            self.assertEqual(page.input_value("#etiquettes-localisation"), localisation)
            self.assertIn(str(len(attendus)), page.inner_text("#etiquettes-resume"))

            # Mode serveur : adresse encodée affichée, avertissement, choix entre les deux adresses
            self.assertIn(premiere, page.inner_text("#etiquettes-adresse-encodee"))
            texte = re.sub(r"\s+", " ", page.inner_text("#contenu"))
            self.assertIn(AVERTISSEMENT, texte.replace("Si l'adresse", "si l'adresse"))
            self.assertNotIn(MENTION_DOSSIER, texte)
            options = page.eval_on_selector_all("#etiquettes-adresse option", "o => o.map(x => x.value)")
            self.assertEqual(options, [premiere, seconde])
            self.assertEqual(page.input_value("#etiquettes-adresse"), premiere)

            # Chaque QR = App.urlFicheEquipement(id) = URL réseau de la fiche
            self.verifier_etiquettes(page, "#etiquettes-apercu", attendus, lambda i: self.url_attendue(premiere, i))
            un_id = sorted(attendus)[0]
            self.assertEqual(page.evaluate("(i) => App.urlFicheEquipement(i)", un_id), self.url_attendue(premiere, un_id))

            # Une case décochée retire l'étiquette ; « Tout décocher » désactive l'impression
            case = page.locator("#etiquettes-liste input[type=checkbox]").first
            retire = case.get_attribute("value")
            case.uncheck()
            self.assertNotIn(retire, self.ids_apercu())
            self.assertEqual(len(self.ids_apercu()), len(attendus) - 1)
            page.click("#etiquettes-tout-decocher")
            self.assertEqual(self.ids_apercu(), [])
            self.assertTrue(page.is_disabled("#etiquettes-imprimer"))
            page.click("#etiquettes-tout-cocher")
            self.assertEqual(sorted(self.ids_apercu()), sorted(attendus))

            # Choix de la seconde adresse → adresse_qr écrite dans parametres.csv
            page.select_option("#etiquettes-adresse", seconde)
            page.click("#etiquettes-adresse-enregistrer")
            page.wait_for_function("(a) => document.querySelector('#etiquettes-adresse-encodee')"
                                   " && document.querySelector('#etiquettes-adresse-encodee').textContent.includes(a)", arg=seconde)
            parametres = {l["cle"]: l["valeur"] for l in lire_csv(dossier, "parametres.csv")}
            self.assertEqual(parametres.get("adresse_qr"), seconde)
            self.verifier_etiquettes(page, "#etiquettes-apercu", attendus, lambda i: self.url_attendue(seconde, i))

            # Relue au rechargement : l'adresse choisie reste celle des QR
            page.reload()
            attendre_pret(page)
            self.aller("#/parc/etiquettes?localisation=" + localisation)
            self.assertEqual(page.input_value("#etiquettes-adresse"), seconde)
            self.assertIn(seconde, page.inner_text("#etiquettes-adresse-encodee"))
            self.assertEqual(page.evaluate("(i) => App.urlFicheEquipement(i)", un_id), self.url_attendue(seconde, un_id))
            self.verifier_etiquettes(page, "#etiquettes-apercu", attendus, lambda i: self.url_attendue(seconde, i))

    def test_serveur_filtres_de_l_adresse_criticite_et_identifiants(self):
        dossier = self.serveur.dossier
        localisation, _ = choisir_localisations(dossier)
        page = self.ouvrir()
        attendus_a = equipements_attendus(dossier, localisation, "A")
        self.aller("#/parc/etiquettes?localisation=%s&criticite=A" % localisation)
        self.assertEqual(page.input_value("#etiquettes-criticite"), "A")
        self.assertEqual(sorted(self.ids_apercu()), sorted(attendus_a))
        choisis = sorted(equipements_attendus(dossier, localisation))[:3]
        self.aller("#/parc/etiquettes?ids=" + ",".join(choisis))
        self.assertEqual(sorted(self.ids_apercu()), choisis)

    # -- impression ---------------------------------------------------------------------------------

    def test_impression_format_24_puis_8_avec_decalage_memorise_noir_sur_blanc_et_pdf_a4(self):
        dossier = self.serveur.dossier
        _, racine = choisir_localisations(dossier)
        attendus = equipements_attendus(dossier, racine)
        nombre = len(attendus)
        self.assertGreaterEqual(nombre, 24, "il faut une planche de 24 pleine pour vérifier la grille 3 × 8")
        page = self.page
        page.add_init_script(ESPION_IMPRESSION_JS)
        self.ouvrir(route="#/parc/etiquettes?localisation=" + racine)
        premiere = self.adresses(self.serveur)[0]

        # Format 24 par défaut, sans décalage
        self.assertEqual(page.input_value("#etiquettes-format"), "24")
        # L'aperçu à l'écran est réduit (zoom) : ses mesures en mm se vérifient sur #impression.
        self.assertEqual(page.locator("#etiquettes-apercu .planche-etiquettes").count(), math.ceil(nombre / 24))
        page.click("#etiquettes-imprimer")
        self.assertEqual(page.evaluate("window.__impressions"), 1)
        self.assertEqual(page.locator("#impression .etiquette").count(), nombre)

        page.emulate_media(media="print")
        self.assertTrue(page.is_visible("#impression .planche-etiquettes"))
        self.assertTrue(page.is_hidden(".menu-lateral"))
        self.assertTrue(page.is_hidden("#contenu"))
        couleurs = page.evaluate(COULEURS_IMPRESSION_JS)
        self.assertEqual(couleurs["texte"], "rgb(0, 0, 0)")
        self.assertEqual(couleurs["repere"], "rgb(0, 0, 0)")
        self.assertIn(couleurs["fond"], ("rgb(255, 255, 255)", "rgba(0, 0, 0, 0)"))
        self.assertEqual(couleurs["corps"], "rgb(255, 255, 255)")
        self.verifier_planches(page, "#impression", nombre, "24")
        self.verifier_etiquettes(page, "#impression", attendus, lambda i: self.url_attendue(premiere, i))

        # PDF (impression réelle de Chromium) : autant de pages A4 que de planches (marges nulles :
        # avec les 12 mm du bon de travail, chaque planche de 297 mm déborderait sur une 2e page).
        # page.pdf() émet beforeprint puis afterprint (qui vide #impression) : on note ce qui est imprimé.
        pdf = self.imprimer_en_pdf(page)
        self.assertEqual(page.evaluate("window.__etiquettesImprimees"), nombre)
        pages = len(re.findall(rb"/Type\s*/Page(?![A-Za-z])", pdf))
        self.assertEqual(pages, math.ceil(nombre / 24))
        largeur, hauteur = (float(v) for v in re.search(
            rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]", pdf).groups())
        self.assertAlmostEqual(largeur, 595.3, delta=2)
        self.assertAlmostEqual(hauteur, 841.9, delta=2)
        page.emulate_media(media="screen")
        self.assertTrue(page.is_hidden("#impression"))
        page.evaluate("window.dispatchEvent(new Event('afterprint'))")
        self.assertEqual(page.evaluate("document.getElementById('impression').children.length"), 0)

        # Format 8 et décalage (haut 2 mm, gauche 1,5 mm), mémorisés sur le poste
        page.select_option("#etiquettes-format", "8")
        page.fill("#etiquettes-decalage-haut", "2")
        page.fill("#etiquettes-decalage-gauche", "1.5")
        page.locator("#etiquettes-decalage-gauche").dispatch_event("change")
        page.click("#etiquettes-imprimer")
        self.assertEqual(page.evaluate("window.__impressions"), 2)
        page.emulate_media(media="print")
        self.verifier_planches(page, "#impression", nombre, "8", haut_mm=2, gauche_mm=1.5)
        pdf = self.imprimer_en_pdf(page)
        self.assertEqual(page.evaluate("window.__etiquettesImprimees"), nombre)
        self.assertEqual(len(re.findall(rb"/Type\s*/Page(?![A-Za-z])", pdf)), math.ceil(nombre / 8))
        page.emulate_media(media="screen")
        page.evaluate("window.dispatchEvent(new Event('afterprint'))")

        memoire = json.loads(page.evaluate("localStorage.getItem('prevo.etiquettes')"))
        self.assertEqual(memoire.get("format"), "8")
        self.assertEqual(float(memoire.get("haut")), 2.0)
        self.assertEqual(float(memoire.get("gauche")), 1.5)
        page.reload()
        attendre_pret(page)
        self.aller("#/parc/etiquettes?localisation=" + racine)
        self.assertEqual(page.input_value("#etiquettes-format"), "8")
        self.assertEqual(float(page.input_value("#etiquettes-decalage-haut")), 2.0)
        self.assertEqual(float(page.input_value("#etiquettes-decalage-gauche")), 1.5)
        self.assertEqual(page.locator("#etiquettes-apercu .planche-etiquettes").count(), math.ceil(nombre / 8))

    # -- profils ------------------------------------------------------------------------------------

    def test_profils_technicien_et_demandeur_renvoyes_a_l_accueil_sans_bouton(self):
        techniciens = [t for t in lire_csv(self.serveur.dossier, "techniciens.csv") if t["actif"].strip() != "0"]
        self.assertTrue(techniciens)
        for profil, extra in (("technicien", {"technicien_id": techniciens[0]["id"]}), ("demandeur", {"nom": "Opérateur test"})):
            with self.subTest(profil=profil):
                contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
                try:
                    page = contexte.new_page()
                    self.surveiller(page)
                    self.ouvrir(profil=profil, page=page, contexte=contexte, route="#/parc", **extra)
                    self.assertEqual(page.locator("#contenu a[href='#/parc/etiquettes']").count(), 0)
                    page.evaluate("location.hash = '#/parc/etiquettes'")
                    page.wait_for_function("location.hash === '#/accueil'")
                    self.assertEqual(page.locator("#etiquettes-apercu").count(), 0)
                    self.assertIn("pas disponible", page.inner_text("#toast"))
                finally:
                    contexte.close()

    # -- telephone ----------------------------------------------------------------------------------

    def test_telephone_375_px_sans_defilement_horizontal_et_zones_de_48_px(self):
        localisation, _ = choisir_localisations(self.serveur.dossier)
        page = self.page
        page.set_viewport_size({"width": 375, "height": 812})
        self.ouvrir(route="#/parc")
        self.assertTrue(page.evaluate("UI.estTelephone()"))
        self.sans_defilement_horizontal(page, "parc, 375 px")
        self.aller("#/parc/etiquettes?localisation=" + localisation)
        self.sans_defilement_horizontal(page, "étiquettes, 375 px")
        self.assertEqual(page.evaluate(PETITES_ZONES_JS), [])
        page.select_option("#etiquettes-format", "8")
        self.sans_defilement_horizontal(page, "étiquettes format 8, 375 px")
        page.set_viewport_size({"width": 360, "height": 740})
        self.sans_defilement_horizontal(page, "étiquettes, 360 px")


# ---------------------------------------------------------------------------
# Mode démo (file://) : QR « GMAO:<id> »
# ---------------------------------------------------------------------------

class TestEtiquettesDemo(CasEtiquettes):

    def test_demo_qr_gmao_et_mention_camera_du_poste_sans_choix_d_adresse(self):
        localisation, _ = choisir_localisations(DOSSIER_DEMO)
        attendus = equipements_attendus(DOSSIER_DEMO, localisation)
        page = self.page
        preregler_profil(self.contexte, "responsable", "Responsable")
        page.goto(url_fichier("index.html"))
        page.click("#btn-demo")
        attendre_pret(page)
        self.assertEqual(page.evaluate("App.mode"), "demo")
        self.aller("#/parc")
        page.click("#contenu a[href='#/parc/etiquettes']")
        page.wait_for_selector("#etiquettes-apercu")
        self.aller("#/parc/etiquettes?localisation=" + localisation)
        texte = re.sub(r"\s+", " ", page.inner_text("#contenu"))
        self.assertIn("GMAO:", texte)
        self.assertIn(MENTION_DOSSIER, texte)
        self.assertNotIn("réservation dans la box", texte)
        self.assertEqual(page.locator("#etiquettes-adresse").count(), 0)
        self.verifier_etiquettes(page, "#etiquettes-apercu", attendus, lambda i: "GMAO:" + i)
        self.assertEqual(page.locator("#etiquettes-apercu .planche-etiquettes").count(), math.ceil(len(attendus) / 24))


if __name__ == "__main__":
    unittest.main()
