"""Écran « Ce poste » et thème clair (lot 4, ARCHITECTURE.md §17.7 ; brief §2 bis, §10, §11 ; tâche T67).

Toujours avec le faux fournisseur d'IA (tests/faux_fournisseur_ia.py), jamais un vrai modèle ; l'adresse
« en ligne » https://api.exemple.fr/v1 est interceptée par le test : rien ne quitte le poste.
    - écran #/poste ouvert aux trois profils, entrée « Ce poste » du menu (groupe « Administration ») ;
    - identité : nom du poste, profil, stockage, « Changer de profil ou de nom de poste… » ;
    - assistant IA, mode serveur (relais ; audit M1, M3, §22.12) : fournisseur, adresse et état de la clé du PC
      serveur (--ia-url, --ia-fournisseur, PREVO_IA_CLE) affichés sans champ de saisie (« réglé sur le PC
      serveur », « réglée sur le serveur » ou « aucune clé ») ; « Tester la connexion » remplit la liste des
      modèles, mention « reste sur le PC atelier » ; la clé du PC serveur est transmise au fournisseur mais
      jamais au poste (stockage, page, CSV, journal, console du serveur, console du navigateur) ;
    - assistant IA, démo (appel direct) : mention « reste sur ce PC » ; fournisseur en ligne refusé tant
      que le responsable ne l'autorise pas, puis avertissement explicite et mention « données envoyées à » ;
      clé gardée seulement pour la même adresse ;
    - assistant IA, mode dossier : carte inchangée (fournisseur, adresse, clé), avec la mention I5 ;
    - dictée : état détecté ; désactivée → aucun bouton micro sur le formulaire « Signaler » ;
    - thème clair appliqué tout de suite, gardé après rechargement et posé avant le premier écran ;
      contrastes AA du thème clair calculés dans la page ; impression inchangée (PDF, fond blanc) ;
    - téléphone 375 px : pas de défilement horizontal, zones de « Ce poste » d'au moins 48 px.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_poste.py" -v
"""
import csv
import json
import re
import unittest

import test_dictee   # reconnaissance vocale simulée et relevé des toasts (module seul : ses tests ne sont pas repris)
from commun import (RACINE, CasNavigateur, ServeurPrevo, ServeurStatique, attendre_pret, installer_dossier_simule,
                    preregler_profil, scenarios_demo, url_fichier)
from faux_fournisseur_ia import FauxFournisseur

CLE = "sk-test-cle-poste-prevo-8d41b2"
REFUS_DISTANT = "Le responsable n'a pas autorisé les fournisseurs en ligne"
# Audit I5 : sans serveur, la clé reste dans le navigateur ; « Ce poste » le dit.
MENTION_I5 = "En mode dossier, la clé reste dans ce navigateur ; le mode serveur la garde sur le PC serveur."
# Mode dossier servi par un petit serveur de fichiers : Prévo y cherche d'abord un serveur (404 attendus).
ERREURS_SERVEUR_STATIQUE = [re.compile(r"status of 404.*/api/ping"), re.compile(r"status of 404.*/api/csv/")]
HOTE_EN_LIGNE = "api.exemple.fr"
URL_EN_LIGNE = "https://api.exemple.fr/v1"
AVERTISSEMENT = ("Les textes envoyés — descriptions, comptes rendus, désignations — partent chez "
                 "api.exemple.fr ; ils peuvent contenir des noms.")
CARTES = ("#carte-identite", "#carte-ia", "#carte-dictee", "#carte-affichage")
CHAMP_DESCRIPTION = "#contenu textarea[name=description]"
BOUTON_DESCRIPTION = CHAMP_DESCRIPTION + " + .dictee-bouton"

# Thème relevé au chargement du document (avant le démarrage d'App) et au premier état « prêt ».
SUIVI_THEME_JS = """(() => {
  window.__suiviTheme = { auChargementDuDom: 'non relevé', aPret: 'non relevé' };
  const theme = () => document.documentElement.getAttribute('data-theme') || 'sombre';
  document.addEventListener('DOMContentLoaded', () => { window.__suiviTheme.auChargementDuDom = theme(); });
  new MutationObserver(() => {
    if (document.documentElement && document.documentElement.dataset.etat === 'pret'
        && window.__suiviTheme.aPret === 'non relevé') window.__suiviTheme.aPret = theme();
  }).observe(document, { subtree: true, attributes: true, attributeFilter: ['data-etat'] });
})();"""

# Contrastes WCAG calculés dans la page sur les couleurs réellement appliquées (variables de la charte).
CONTRASTES_JS = """() => {
  const sonde = document.createElement('div');
  document.body.appendChild(sonde);
  const lire = (variable) => {
    sonde.style.color = 'var(' + variable + ')';
    const m = getComputedStyle(sonde).color.match(/[0-9.]+/g).map(Number);
    return { r: m[0], g: m[1], b: m[2], a: m.length > 3 ? m[3] : 1 };
  };
  const sur = (dessus, dessous) => ({ r: dessus.r * dessus.a + dessous.r * (1 - dessus.a),
    g: dessus.g * dessus.a + dessous.g * (1 - dessus.a), b: dessus.b * dessus.a + dessous.b * (1 - dessus.a), a: 1 });
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const blanc = { r: 255, g: 255, b: 255, a: 1 };
  const mesurer = (avant, arriere) => {
    const fond = sur(lire(arriere), blanc);
    return Math.round(ratio(sur(lire(avant), fond), fond) * 100) / 100;
  };
  const fonds = ['--fond', '--carte', '--carte-2'];
  const textes = ['--texte', '--texte-2', '--muted'];
  // Traits et grands textes : couleurs d'accent de la charte (icônes, liserés, bordures d'état, focus).
  const traits = ['--bleu', '--cyan', '--vert', '--rouge', '--ambre', '--violet'];
  const resultat = { texte: [], trait: [], autres: [] };
  fonds.forEach((fond) => {
    textes.forEach((texte) => resultat.texte.push([texte + ' sur ' + fond, mesurer(texte, fond)]));
    traits.forEach((trait) => resultat.trait.push([trait + ' sur ' + fond, mesurer(trait, fond)]));
  });
  resultat.autres.push(['--placeholder sur --champ', mesurer('--placeholder', '--champ')]);
  resultat.autres.push(['--sur-couleur sur --bleu-bouton', mesurer('--sur-couleur', '--bleu-bouton')]);
  // Contour des champs (WCAG 1.4.11, 3:1) : un champ blanc sur une carte blanche n'est visible que par lui.
  resultat.contour = fonds.concat(['--champ']).map((fond) => ['--bord-champ sur ' + fond, mesurer('--bord-champ', fond)]);
  const champ = document.querySelector('#contenu input:not([type=checkbox]):not([type=radio]), #contenu select');
  resultat.bordReel = champ ? getComputedStyle(champ).borderTopColor : null;
  sonde.style.color = 'var(--bord-champ)';
  resultat.bordJeton = getComputedStyle(sonde).color;
  sonde.remove();
  return resultat;
}"""

# Textes réellement affichés (relecture du lot 4) : couleur du texte sur le fond composé de ses ancêtres
# (couleurs avec transparence comprises ; un fond en image ou dégradé compte pour sa couleur de fond),
# opacité des ancêtres comprise. Seuil 4,5:1, ou 3:1 pour un grand texte (24 px, ou 18,66 px gras).
# Non mesurés : éléments masqués, champs désactivés (WCAG les exempte), textes des graphiques (SVG).
AUDIT_TEXTES_JS = """(racine) => {
  const lire = (c) => { const m = (c || '').match(/[0-9.]+/g); if (!m) return null;
    const v = m.map(Number); return { r: v[0], g: v[1], b: v[2], a: v.length > 3 ? v[3] : 1 }; };
  const sur = (h, b) => ({ r: h.r * h.a + b.r * (1 - h.a), g: h.g * h.a + b.g * (1 - h.a), b: h.b * h.a + b.b * (1 - h.a), a: 1 });
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const fondDe = (el) => {
    const couches = [];
    for (let e = el; e; e = e.parentElement) {
      const c = lire(getComputedStyle(e).backgroundColor);
      if (c && c.a > 0) { couches.push(c); if (c.a >= 1) break; }
    }
    let fond = { r: 255, g: 255, b: 255, a: 1 };
    for (let i = couches.length - 1; i >= 0; i -= 1) fond = sur(couches[i], fond);
    return fond;
  };
  const opacite = (el) => { let o = 1; for (let e = el; e; e = e.parentElement) o *= Number(getComputedStyle(e).opacity); return o; };
  const echecs = [];
  for (const el of document.querySelectorAll(racine + ' *')) {
    if (el.closest('svg, [hidden], .visuellement-cache') || el.disabled || el.closest(':disabled')) continue;
    const texte = Array.from(el.childNodes).filter((n) => n.nodeType === 3).map((n) => n.textContent).join('').trim();
    if (!texte || !el.getClientRects().length) continue;
    const style = getComputedStyle(el);
    if (style.visibility === 'hidden') continue;
    const couleur = lire(style.color);
    const o = opacite(el);
    const fond = fondDe(el);
    const r = ratio(sur({ r: couleur.r, g: couleur.g, b: couleur.b, a: couleur.a * o }, fond), fond);
    const taille = parseFloat(style.fontSize);
    const grand = taille >= 24 || (taille >= 18.66 && Number(style.fontWeight) >= 700);
    if (r < (grand ? 3 : 4.5)) {
      echecs.push((el.className && typeof el.className === 'string' ? el.tagName.toLowerCase() + '.' + el.className.trim().split(/\\s+/).join('.') : el.tagName.toLowerCase())
        + ' « ' + texte.slice(0, 30) + ' » ' + Math.round(r * 100) / 100 + ':1');
    }
  }
  return Array.from(new Set(echecs));
}"""


def premier_technicien_actif(dossier):
    """Identifiant du premier technicien actif de techniciens.csv (lu sur le disque, rien d'écrit en dur)."""
    with open(dossier / "techniciens.csv", encoding="utf-8-sig", newline="") as fichier:
        for ligne in csv.DictReader(fichier, delimiter=";"):
            if ligne["actif"] != "0":
                return ligne["id"]
    raise AssertionError("aucun technicien actif dans techniciens.csv")


def texte_simple(texte):
    """Espaces (insécables comprises) et sauts de ligne ramenés à une espace simple."""
    return re.sub(r"\s+", " ", texte).strip()


class CasPoste(CasNavigateur):
    """Outils communs : ouvrir « Ce poste », remplir la carte « Assistant IA », lire la page."""

    def setUp(self):
        super().setUp()
        self.console = []
        self.page.on("console", lambda message: self.console.append(message.text))
        self.adresses = []
        self.page.on("request", lambda requete: self.adresses.append(requete.url))

    def attendre_ecran_poste(self, page=None):
        page = page or self.page
        page.wait_for_function("""() => location.hash === '#/poste' && document.querySelector('#contenu h1')
            && document.querySelector('#contenu h1').textContent.trim() === 'Ce poste'
            && document.querySelector('#carte-ia')""")
        return page

    def aller(self, route, page=None):
        page = page or self.page
        page.evaluate("hash => { location.hash = hash; }", route)
        page.wait_for_function("hash => location.hash === hash", arg=route)
        if route == "#/poste":
            self.attendre_ecran_poste(page)

    def attendre_toast(self, motif, page=None):
        page = page or self.page
        return page.wait_for_function(
            "motif => (window.__toasts || []).find((t) => t.includes(motif)) || null", arg=motif).json_value()

    def attendre_texte(self, selecteur, extrait, page=None):
        page = page or self.page
        page.wait_for_function("([s, t]) => document.querySelector(s) && document.querySelector(s).innerText.includes(t)",
                               arg=[selecteur, extrait])

    def remplir_ia(self, fournisseur=None, url=None, modele=None, cle=None):
        page = self.page
        if fournisseur:
            page.select_option("#poste-ia-fournisseur", fournisseur)
        if url is not None:
            page.fill("#poste-ia-url", url)
        if modele is not None:
            page.fill("#poste-ia-modele", modele)
        if cle is not None:
            page.wait_for_selector("#poste-ia-cle", state="visible")
            page.fill("#poste-ia-cle", cle)

    def choisir_apres_test_de_connexion(self, modele):
        """« Tester la connexion », puis le modèle choisi dans la liste des modèles trouvés."""
        page = self.page
        page.click("#btn-tester-ia")
        page.wait_for_selector("#poste-ia-liste-modeles option[value='%s']" % modele, state="attached")
        self.attendre_texte("#poste-ia-resultat", "Connexion réussie")
        page.select_option("#poste-ia-liste-modeles", modele)
        self.assertEqual(page.input_value("#poste-ia-modele"), modele)
        return page.eval_on_selector_all("#poste-ia-liste-modeles option", "options => options.map((o) => o.value)")


# ---------------------------------------------------------------------------
# Mode serveur (relais /api/ia)
# ---------------------------------------------------------------------------

class CasPosteServeur(CasPoste):
    """Mode serveur : le fournisseur d'IA est réglé sur le PC serveur (options_ia, audit M1, M3, §22.12), lancé ici
    sur le faux fournisseur ; le poste ne règle que l'activation, le modèle et le délai."""

    @classmethod
    def options_ia(cls, faux):
        """(arguments de serveur.py, variables d'environnement) qui règlent le fournisseur du PC serveur."""
        raise NotImplementedError

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.faux = FauxFournisseur(cle_attendue=CLE)
        cls.faux.demarrer()
        cls.addClassCleanup(cls.faux.arreter)
        arguments, environnement = cls.options_ia(cls.faux)
        cls.serveur = ServeurPrevo(arguments=arguments, environnement=environnement)
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)

    def setUp(self):
        super().setUp()
        self.faux.requetes.clear()

    def ouvrir(self, route="#/poste", profil="responsable", **options):
        preregler_profil(self.contexte, profil, **options)
        self.page.goto(self.serveur.url + "/" + route)
        attendre_pret(self.page)
        if route == "#/poste":
            self.attendre_ecran_poste()
        return self.page

    def attendre_reglages_du_serveur(self):
        """« Ce poste » relit les réglages du PC serveur à son ouverture : la zone sans champ est alors remplie."""
        self.page.wait_for_selector("#poste-ia-serveur-cle")
        self.assertIn("réglé sur le PC serveur", self.page.inner_text("#poste-ia-serveur"))
        self.assertEqual(self.page.locator("#poste-ia-url, #poste-ia-fournisseur, #poste-ia-cle, #poste-ia-zone-cle, "
                                           "#carte-ia input[type=password]").count(), 0, "aucun champ du PC serveur")
        return self.page


class TestCePosteServeur(CasPosteServeur):
    """PC serveur réglé sur Ollama (--ia-url), sans clé."""

    @classmethod
    def options_ia(cls, faux):
        return ["--ia-url", faux.url], None

    def test_ecran_et_entree_du_menu_pour_les_trois_profils(self):
        technicien = premier_technicien_actif(self.serveur.dossier)
        profils = [("demandeur", {"nom": "Lucie Essai"}, "Demandeur · Lucie Essai"),
                   ("technicien", {"technicien_id": technicien}, "Technicien · "),
                   ("responsable", {}, "Responsable")]
        for type_profil, options, libelle in profils:
            with self.subTest(profil=type_profil):
                contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
                try:
                    page = contexte.new_page()
                    self.surveiller(page)
                    preregler_profil(contexte, type_profil, **options)
                    page.goto(self.serveur.url + "/#/accueil")
                    attendre_pret(page)
                    lien = page.locator("#menu a[data-ecran='poste']")
                    self.assertEqual(lien.count(), 1)
                    self.assertEqual(lien.get_attribute("href"), "#/poste")
                    self.assertEqual(lien.inner_text().strip(), "Ce poste")
                    groupe = page.evaluate("""() => {
                      let e = document.querySelector("#menu a[data-ecran='poste']").previousElementSibling;
                      while (e && !e.classList.contains('menu-groupe')) e = e.previousElementSibling;
                      return e ? e.textContent.trim() : null; }""")
                    self.assertEqual(groupe, "Administration")
                    lien.click()
                    self.attendre_ecran_poste(page)
                    for carte in CARTES:
                        self.assertTrue(page.is_visible(carte), carte)
                    self.assertEqual(page.inner_text("#poste-nom").strip(), "Poste test")
                    self.assertIn(libelle, page.inner_text("#poste-profil"))
                    self.assertTrue(page.inner_text("#poste-stockage").strip())
                    self.assertEqual(page.evaluate("document.querySelector('#menu a.actif').dataset.ecran"), "poste")
                finally:
                    contexte.close()

    def test_identite_changer_de_profil_ou_de_nom_de_poste(self):
        page = self.ouvrir()
        self.assertEqual(page.inner_text("#poste-nom").strip(), "Poste test")
        self.assertEqual(page.inner_text("#poste-profil").strip(), "Responsable")
        page.click("#btn-changer-profil")
        page.wait_for_function("document.documentElement.dataset.etat === 'profil'")
        self.assertTrue(page.is_visible("#profil-annuler"))
        self.assertEqual(page.input_value("#profil-poste"), "Poste test")
        page.fill("#profil-poste", "Poste atelier 2")
        page.click("#profil-responsable")
        attendre_pret(page)
        self.attendre_ecran_poste()
        self.assertEqual(page.inner_text("#poste-nom").strip(), "Poste atelier 2")
        self.assertEqual(page.evaluate("localStorage.getItem('prevo.poste')"), "Poste atelier 2")

    def test_ia_ollama_par_le_relais_liste_des_modeles_et_reste_sur_le_pc_atelier(self):
        page = self.ouvrir()
        self.assertFalse(page.is_checked("#poste-ia-actif"))
        # Fournisseur et adresse du PC serveur (--ia-url), affichés sans champ ; aucune clé pour Ollama
        self.attendre_reglages_du_serveur()
        self.assertEqual(page.inner_text("#poste-ia-serveur-fournisseur").strip(), "Ollama")
        self.assertEqual(page.inner_text("#poste-ia-serveur-url").strip(), self.faux.url)
        self.assertEqual(page.inner_text("#poste-ia-serveur-cle").strip(), "aucune clé")
        self.assertIn("reste sur le PC atelier", page.inner_text("#poste-ia-mention"))
        self.assertEqual(self.faux.requetes, [], "aucun appel tant que l'IA n'est pas activée")

        modeles = self.choisir_apres_test_de_connexion("faux")
        self.assertIn("faux-lent", modeles)
        self.assertIsNone(page.evaluate("localStorage.getItem('prevo.ia')"), "tester n'enregistre rien")
        page.check("#poste-ia-actif")
        page.click("#btn-enregistrer-ia")
        page.wait_for_function("Ia.etat() === 'ok'")
        reglages = page.evaluate("Ia.reglages()")
        self.assertEqual((reglages["actif"], reglages["fournisseur"], reglages["url"], reglages["modele"]),
                         (True, "ollama", self.faux.url, "faux"))
        self.assertEqual(json.loads(page.evaluate("localStorage.getItem('prevo.ia')")),
                         {"actif": True, "modele": "faux", "delaiS": 120}, "ni fournisseur, ni adresse, ni clé sur le poste")
        page.wait_for_selector("#ia-mention", state="visible")
        self.assertEqual(page.inner_text("#ia-mention").strip(), "IA : reste sur le PC atelier")
        self.assertIn("reste sur le PC atelier", page.inner_text("#poste-ia-mention"))
        self.attendre_texte("#poste-ia-etat", "le fournisseur répond")
        # Mode serveur : tout passe par le relais du serveur, rien ne part du navigateur vers le fournisseur
        self.assertGreaterEqual(len(self.faux.requetes), 2)
        self.assertEqual({r["chemin"] for r in self.faux.requetes}, {"/api/tags"})
        self.assertFalse([a for a in self.adresses if a.startswith(self.faux.url + "/")])
        self.assertTrue([a for a in self.adresses if a == self.serveur.url + "/api/ia"])
        self.assertTrue([a for a in self.adresses if a == self.serveur.url + "/api/ia/reglages"],
                        "réglages relus à l'ouverture de « Ce poste »")

    def test_dictee_desactivee_aucun_micro_sur_le_formulaire_signaler(self):
        self.contexte.add_init_script(test_dictee.RECONNAISSANCE_SIMULEE_JS)
        self.contexte.add_init_script(test_dictee.NOTER_TOASTS_JS)
        page = self.ouvrir("#/di/nouvelle")
        page.wait_for_selector(BOUTON_DESCRIPTION)               # dictée active par défaut
        self.aller("#/poste")
        self.assertTrue(page.is_checked("#poste-dictee-active"))
        self.attendre_texte("#poste-dictee-etat", "proposée par ce navigateur")
        self.assertNotIn("non proposée", page.inner_text("#poste-dictee-etat"))
        page.uncheck("#poste-dictee-active")
        self.attendre_toast("Dictée désactivée")
        self.assertFalse(page.evaluate("Dictee.reglages().active"))
        self.aller("#/di/nouvelle")
        page.wait_for_selector(CHAMP_DESCRIPTION)
        page.wait_for_timeout(300)
        self.assertEqual(page.locator(".dictee-bouton").count(), 0)
        # Réglage gardé après rechargement
        page.reload()
        attendre_pret(page)
        page.wait_for_selector(CHAMP_DESCRIPTION)
        page.wait_for_timeout(300)
        self.assertEqual(page.locator(".dictee-bouton").count(), 0)
        # Réactivée : le micro revient
        self.aller("#/poste")
        self.assertFalse(page.is_checked("#poste-dictee-active"))
        page.check("#poste-dictee-active")
        self.attendre_toast("Dictée activée")
        self.aller("#/di/nouvelle")
        page.wait_for_selector(BOUTON_DESCRIPTION)

    def test_dictee_etat_detecte(self):
        # Reconnaissance française sur l'appareil : « transcription sur ce PC »
        self.contexte.add_init_script(test_dictee.RECONNAISSANCE_SIMULEE_JS)
        self.contexte.add_init_script("window.__dictee.local = true;")
        page = self.ouvrir()
        self.attendre_texte("#poste-dictee-etat", "proposée par ce navigateur")
        # Le lieu de la transcription n'est demandé (SpeechRecognition.available) que sur clic
        self.assertFalse(page.evaluate("window.__dictee.instances.length"))
        page.click("#btn-verifier-dictee")
        self.attendre_texte("#poste-dictee-etat", "transcription sur ce PC")
        self.assertIn("proposée par ce navigateur", page.inner_text("#poste-dictee-etat"))
        # Sans reconnaissance sur l'appareil : la voix part chez Google ou Microsoft
        page.evaluate("window.__dictee.local = false")
        page.click("#btn-verifier-dictee")
        self.attendre_texte("#poste-dictee-etat", "Google ou Microsoft")
        # Navigateur sans reconnaissance vocale : « non proposée : … »
        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
        self.addCleanup(contexte.close)
        autre = contexte.new_page()
        self.surveiller(autre)
        contexte.add_init_script(test_dictee.SANS_RECONNAISSANCE_JS)
        preregler_profil(contexte, "responsable")
        autre.goto(self.serveur.url + "/#/poste")
        attendre_pret(autre)
        self.attendre_ecran_poste(autre)
        self.attendre_texte("#poste-dictee-etat", "non proposée : ", page=autre)
        self.assertTrue(autre.is_hidden("#btn-verifier-dictee"))

    def test_theme_clair_tout_de_suite_garde_apres_rechargement_et_avant_le_premier_ecran(self):
        self.contexte.add_init_script(SUIVI_THEME_JS)
        page = self.ouvrir()
        self.assertIsNone(page.evaluate("document.documentElement.getAttribute('data-theme')"))
        self.assertTrue(page.is_checked("#poste-theme-sombre"))
        self.assertNotEqual(page.evaluate("getComputedStyle(document.querySelector('#carte-identite')).backgroundColor"),
                            "rgb(255, 255, 255)")
        page.check("#poste-theme-clair")
        page.wait_for_function("document.documentElement.getAttribute('data-theme') === 'clair'")
        self.assertEqual(page.evaluate("localStorage.getItem('prevo.theme')"), "clair")
        self.assertEqual(page.evaluate("getComputedStyle(document.querySelector('#carte-identite')).backgroundColor"),
                         "rgb(255, 255, 255)")
        page.reload()
        attendre_pret(page)
        self.attendre_ecran_poste()
        suivi = page.evaluate("window.__suiviTheme")
        self.assertEqual(suivi, {"auChargementDuDom": "clair", "aPret": "clair"},
                         "thème posé avant le démarrage d'App, donc avant le premier écran")
        self.assertEqual(page.evaluate("document.documentElement.dataset.theme"), "clair")
        self.assertTrue(page.is_checked("#poste-theme-clair"))
        # Retour au thème sombre (défaut) : l'attribut disparaît
        page.check("#poste-theme-sombre")
        page.wait_for_function("document.documentElement.getAttribute('data-theme') === null")
        self.assertEqual(page.evaluate("localStorage.getItem('prevo.theme')"), "sombre")

    def test_contrastes_aa_du_theme_clair(self):
        page = self.ouvrir()
        page.check("#poste-theme-clair")
        page.wait_for_function("document.documentElement.dataset.theme === 'clair'")
        mesures = page.evaluate(CONTRASTES_JS)
        self.assertEqual(len(mesures["texte"]), 9)
        self.assertEqual(len(mesures["trait"]), 18)
        for nom, ratio in mesures["texte"] + mesures["autres"]:
            with self.subTest(couple=nom):
                self.assertGreaterEqual(ratio, 4.5, "%s : %s:1" % (nom, ratio))
        for nom, ratio in mesures["trait"] + mesures["contour"]:
            with self.subTest(couple=nom):
                self.assertGreaterEqual(ratio, 3.0, "%s : %s:1" % (nom, ratio))
        # Les vrais champs de l'écran portent ce contour (ajout de l'orchestrateur).
        self.assertEqual(mesures["bordReel"], mesures["bordJeton"])

    def test_textes_affiches_aa_en_theme_clair_sur_les_ecrans_principaux(self):
        """Relecture du lot 4 (CS74) : en thème clair, chaque texte affiché atteint 4,5:1 (3:1 en grand)."""
        page = self.ouvrir()
        page.check("#poste-theme-clair")
        page.wait_for_function("document.documentElement.dataset.theme === 'clair'")
        scenarios = scenarios_demo()
        routes = ["#/accueil", "#/planning", "#/ot", "#/ot/" + scenarios["ot_statut_en_cours"],
                  "#/equipement/" + scenarios["causes_equipement"], "#/preventif?onglet=suggestions", "#/di",
                  "#/indicateurs", "#/magasin", "#/poste", "#/parametres", "#/di/nouvelle"]
        for route in routes:
            with self.subTest(route=route):
                page.evaluate("hash => { location.hash = hash; }", route)
                page.wait_for_function("hash => location.hash.startsWith(hash)", arg=route)
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(400)
                self.assertEqual(page.evaluate(AUDIT_TEXTES_JS, "#app"), [], route)

    def test_impression_inchangee_noir_sur_blanc_et_pdf(self):
        page = self.ouvrir()
        styles = {}
        for theme in ("sombre", "clair"):
            page.check("#poste-theme-" + theme)
            page.wait_for_function("t => (document.documentElement.getAttribute('data-theme') || 'sombre') === t", arg=theme)
            page.emulate_media(media="print")
            styles[theme] = page.evaluate("""() => {
              const s = (sel) => getComputedStyle(document.querySelector(sel));
              return { fond: s('body').backgroundColor, fondHtml: s('html').backgroundColor, texte: s('body').color,
                       titre: s('#contenu h1').color, carte: s('#carte-ia').backgroundColor,
                       boutons: s('#btn-enregistrer-ia').display, menu: s('.menu-lateral').display };
            }""")
            page.emulate_media(media="screen")
        self.assertEqual(styles["clair"], styles["sombre"], "l'impression ne dépend pas du thème")
        self.assertEqual(styles["clair"]["fond"], "rgb(255, 255, 255)")
        self.assertEqual(styles["clair"]["fondHtml"], "rgb(255, 255, 255)")
        self.assertEqual(styles["clair"]["texte"], "rgb(0, 0, 0)")
        self.assertEqual(styles["clair"]["titre"], "rgb(0, 0, 0)")
        self.assertEqual((styles["clair"]["boutons"], styles["clair"]["menu"]), ("none", "none"))
        # Une capture PDF (thème clair choisi à l'écran) se fait sans erreur
        pdf = page.pdf(format="A4")
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 1000)


class TestCePosteServeurCle(CasPosteServeur):
    """PC serveur réglé sur l'API compatible OpenAI du faux fournisseur, avec sa clé (PREVO_IA_CLE) : la clé est sur
    le PC serveur, jamais sur le poste."""

    @classmethod
    def options_ia(cls, faux):
        return ["--ia-url", faux.url + "/v1", "--ia-fournisseur", "openai"], {"PREVO_IA_CLE": CLE}

    def test_cle_transmise_jamais_ecrite_ni_reaffichee(self):
        page = self.ouvrir()
        self.attendre_reglages_du_serveur()
        self.assertEqual(page.inner_text("#poste-ia-serveur-fournisseur").strip(), "API compatible OpenAI")
        self.assertEqual(page.inner_text("#poste-ia-serveur-url").strip(), self.faux.url + "/v1")
        self.assertEqual(page.inner_text("#poste-ia-serveur-cle").strip(), "réglée sur le serveur")
        self.choisir_apres_test_de_connexion("faux")
        page.check("#poste-ia-actif")
        page.click("#btn-enregistrer-ia")
        page.wait_for_function("Ia.etat() === 'ok'")
        self.assertEqual(page.evaluate("Ia.reglages().cle"), "", "aucune clé sur le poste")
        self.assertTrue(self.faux.requetes)
        for requete in self.faux.requetes:
            with self.subTest(chemin=requete["chemin"]):
                self.assertEqual(requete["entetes"]["authorization"], "Bearer " + CLE)
        # Jamais affichée : seulement « réglée sur le serveur », aucune trace dans la page
        dans_la_page = page.evaluate("""() => document.documentElement.outerHTML
            + [...document.querySelectorAll('input, textarea, select')].map((e) => e.value).join('|')""")
        self.assertNotIn(CLE, dans_la_page)
        # Une écriture du poste (journal) après l'enregistrement : la clé n'y est pas
        page.evaluate("Ia.tracerUtilisation('parametres', 'ia_distant_autorise', 'essai', 'faux')")
        page.reload()
        attendre_pret(page)
        self.attendre_ecran_poste()
        self.attendre_reglages_du_serveur()
        self.assertEqual(page.inner_text("#poste-ia-serveur-cle").strip(), "réglée sur le serveur")
        self.assertEqual(page.evaluate("Ia.reglages().cle"), "", "la clé reste sur le PC serveur")
        stockage = page.evaluate("""() => JSON.stringify(Object.entries(sessionStorage))
            + JSON.stringify(Object.entries(localStorage))""")
        self.assertNotIn(CLE, stockage)
        self.assertIn("proposition IA utilisée (faux) : essai",
                      (self.serveur.dossier / "journal.csv").read_text(encoding="utf-8-sig"))
        octets_cle = CLE.encode("utf-8")
        fichiers = [f for f in sorted(self.serveur.dossier.rglob("*")) if f.is_file()]
        self.assertTrue([f for f in fichiers if f.suffix == ".csv"])
        for fichier in fichiers:
            with self.subTest(fichier=fichier.name):
                self.assertNotIn(octets_cle, fichier.read_bytes())
        self.assertNotIn(CLE, self.serveur.sortie_console())
        self.assertFalse([m for m in self.console if CLE in m])

    def test_telephone_375px_sans_defilement_et_zones_de_48px(self):
        self.page.set_viewport_size({"width": 375, "height": 812})
        page = self.ouvrir()
        self.attendre_reglages_du_serveur()
        self.choisir_apres_test_de_connexion("faux")
        largeurs = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        self.assertLessEqual(largeurs[0], largeurs[1], "défilement horizontal : %r" % (largeurs,))
        hauteurs = page.evaluate("""() => [...document.querySelectorAll(
            '#contenu .btn, #contenu label.case, #contenu select, #contenu input:not([type=checkbox]):not([type=radio])')]
          .filter((e) => e.getClientRects().length > 0)
          .map((e) => [e.id || e.textContent.trim().slice(0, 30) || e.outerHTML.slice(0, 40), e.getBoundingClientRect().height])""")
        self.assertGreater(len(hauteurs), 10)
        self.assertEqual([h for h in hauteurs if h[1] < 47.5], [])


# ---------------------------------------------------------------------------
# Démo (index.html en file://, appel direct du fournisseur)
# ---------------------------------------------------------------------------

class TestCePosteDemo(CasPoste):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.faux = FauxFournisseur()
        cls.faux.demarrer()
        cls.addClassCleanup(cls.faux.arreter)

    def setUp(self):
        super().setUp()
        self.faux.requetes.clear()
        self.contexte.add_init_script(test_dictee.NOTER_TOASTS_JS)

    def ouvrir_demo(self, profil="responsable", **options):
        preregler_profil(self.contexte, profil, **options)
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        self.aller("#/poste")
        return self.page

    def test_demo_ollama_appel_direct_reste_sur_ce_pc(self):
        page = self.ouvrir_demo()
        self.assertIn("reste sur ce PC", page.inner_text("#poste-ia-mention"))
        self.remplir_ia(url=self.faux.url)
        self.assertIn("reste sur ce PC", page.inner_text("#poste-ia-mention"))
        self.choisir_apres_test_de_connexion("faux")
        page.check("#poste-ia-actif")
        page.click("#btn-enregistrer-ia")
        page.wait_for_function("Ia.etat() === 'ok'")
        self.attendre_toast("enregistré")
        page.wait_for_selector("#ia-mention", state="visible")
        self.assertEqual(page.inner_text("#ia-mention").strip(), "IA : reste sur ce PC")
        self.assertIn("reste sur ce PC", page.inner_text("#poste-ia-mention"))
        self.assertTrue(page.is_checked("#poste-ia-actif"))
        # Appel direct : le navigateur joint le fournisseur, aucune requête vers /api/ia
        self.assertTrue(self.faux.requetes)
        self.assertEqual({r["chemin"] for r in self.faux.requetes}, {"/api/tags"})
        self.assertFalse([a for a in self.adresses if "/api/ia" in a])
        # Désactivée sur le poste : plus de mention dans la coque
        page.uncheck("#poste-ia-actif")
        page.click("#btn-enregistrer-ia")
        page.wait_for_function("!Ia.reglages().actif")
        page.wait_for_selector("#ia-mention", state="hidden")

    def test_demo_fournisseur_en_ligne_refuse_puis_avertissement_quand_le_responsable_l_autorise(self):
        appels = []

        def repondre(route):
            requete = route.request
            entetes = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                       "Access-Control-Allow-Headers": "authorization, content-type"}
            if requete.method == "OPTIONS":
                route.fulfill(status=204, headers=entetes)
                return
            appels.append({"methode": requete.method, "url": requete.url, "entetes": requete.headers})
            route.fulfill(status=200, headers=dict(entetes, **{"Content-Type": "application/json"}),
                          body=json.dumps({"data": [{"id": "modele-en-ligne"}]}))

        # Aucune requête ne quitte le poste : l'adresse en ligne est interceptée par le test.
        self.contexte.route("https://%s/**" % HOTE_EN_LIGNE, repondre)
        page = self.ouvrir_demo()
        self.remplir_ia(fournisseur="openai", url=URL_EN_LIGNE, modele="modele-en-ligne", cle="cle-en-ligne")
        self.assertIn("données envoyées à " + HOTE_EN_LIGNE, page.inner_text("#poste-ia-mention"))
        self.assertIn(REFUS_DISTANT, page.inner_text("#poste-ia-portee"))
        # « Tester la connexion » : refusé sans appel
        page.click("#btn-tester-ia")
        self.attendre_texte("#poste-ia-resultat", REFUS_DISTANT)
        # Activation refusée avec le message de IaRefusee : rien n'est écrit, aucun avertissement
        page.check("#poste-ia-actif")
        page.click("#btn-enregistrer-ia")
        self.attendre_toast(REFUS_DISTANT)
        self.assertIsNone(page.evaluate("localStorage.getItem('prevo.ia')"))
        self.assertFalse(page.evaluate("Ia.active()"))
        self.assertEqual(page.locator("dialog[open]").count(), 0)
        self.assertEqual(appels, [])

        # Le responsable autorise les fournisseurs en ligne (parametres.csv, réglage partagé)
        page.evaluate("""() => Donnees.modifier('parametres', (lignes) => {
          const ligne = lignes.find((l) => l.cle === 'ia_distant_autorise');
          if (ligne) ligne.valeur = '1'; else lignes.push({ cle: 'ia_distant_autorise', valeur: '1' });
        })""")
        self.attendre_texte("#poste-ia-portee", "autorisé par le responsable")
        # Avertissement explicite ; « Annuler » : rien n'est écrit
        page.click("#btn-enregistrer-ia")
        page.wait_for_selector("dialog[open] .poste-avertissement-distant")
        self.assertIn(AVERTISSEMENT, texte_simple(page.inner_text("dialog[open]")))
        page.click("dialog[open] .fenetre-actions .btn-fantome")
        page.wait_for_selector("dialog[open]", state="detached")
        self.assertIsNone(page.evaluate("localStorage.getItem('prevo.ia')"))
        self.assertEqual(appels, [])
        # Confirmé : activé, mention « données envoyées à api.exemple.fr » (coque et carte)
        page.click("#btn-enregistrer-ia")
        page.wait_for_selector("dialog[open] .poste-avertissement-distant")
        page.click("dialog[open] .fenetre-actions .btn-primaire")
        page.wait_for_function("Ia.active() && Ia.etat() === 'ok'")
        page.wait_for_selector("#ia-mention.distant", state="visible")
        self.assertEqual(page.inner_text("#ia-mention").strip(), "IA : données envoyées à " + HOTE_EN_LIGNE)
        self.assertIn("données envoyées à " + HOTE_EN_LIGNE, page.inner_text("#poste-ia-mention"))
        self.assertEqual([(a["methode"], a["url"]) for a in appels], [("GET", URL_EN_LIGNE + "/models")])
        self.assertEqual(appels[0]["entetes"]["authorization"], "Bearer cle-en-ligne")
        # Déjà actif chez le même fournisseur : enregistrer de nouveau ne redemande pas l'avertissement
        page.fill("#poste-ia-delai", "60")
        page.click("#btn-enregistrer-ia")
        page.wait_for_function("Ia.reglages().delaiS === 60")
        self.assertEqual(page.locator("dialog[open]").count(), 0)

    def test_cle_jamais_gardee_pour_une_autre_adresse(self):
        """Ajout de l'orchestrateur (défaut injecté) ; joué en démo depuis T158 (appel direct : seul cas où le poste
        garde une clé, le mode serveur n'en garde plus) : la clé enregistrée n'est gardée que pour la même adresse ;
        changer d'adresse sans saisir de clé l'abandonne (jamais envoyée à un autre service)."""
        page = self.ouvrir_demo()
        self.remplir_ia(fournisseur="openai", url=self.faux.url + "/v1", modele="faux", cle=CLE)
        self.assertIn(MENTION_I5, page.inner_text("#poste-ia-zone-cle"))
        self.choisir_apres_test_de_connexion("faux")
        page.check("#poste-ia-actif")
        page.click("#btn-enregistrer-ia")
        page.wait_for_function("Ia.etat() === 'ok'")
        self.assertEqual(page.evaluate("Ia.reglages().cle"), CLE)
        autre = self.faux.url.replace("127.0.0.1", "localhost") + "/v1"
        self.assertNotEqual(autre, self.faux.url + "/v1")
        self.remplir_ia(url=autre)
        page.click("#btn-enregistrer-ia")
        page.wait_for_function("(url) => Ia.reglages().url === url", arg=autre)
        self.assertEqual(page.evaluate("Ia.reglages().cle"), "")


# ---------------------------------------------------------------------------
# Mode dossier (page servie en http://127.0.0.1, dossier simulé) : carte inchangée, mention I5
# ---------------------------------------------------------------------------

class TestCePosteDossier(CasPoste):

    def test_mode_dossier_carte_inchangee_avec_la_mention_i5(self):
        for motif in ERREURS_SERVEUR_STATIQUE:
            self.autoriser_erreur(motif)
        installer_dossier_simule(self.contexte, "donnees-poste-i5")
        preregler_profil(self.contexte, "responsable")
        with ServeurStatique(RACINE) as statique:
            page = self.page
            page.goto(statique.url + "/index.html")
            page.click("#btn-dossier")
            page.wait_for_selector("#btn-base-demo", state="visible")
            page.click("#btn-base-demo")
            attendre_pret(page, 30000)
            self.assertEqual(page.evaluate("App.mode"), "dossier")
            self.aller("#/poste")
            for champ in ("#poste-ia-fournisseur", "#poste-ia-url", "#poste-ia-modele", "#poste-ia-delai"):
                self.assertTrue(page.is_visible(champ), champ)
            self.assertEqual(page.locator("#poste-ia-serveur").count(), 0)
            self.assertNotIn(MENTION_I5, page.inner_text("#carte-ia"), "pas de clé pour Ollama : pas de mention")
            page.select_option("#poste-ia-fournisseur", "openai")
            page.wait_for_selector("#poste-ia-cle", state="visible")
            self.assertEqual(page.get_attribute("#poste-ia-cle", "type"), "password")
            self.assertIn(MENTION_I5, page.inner_text("#poste-ia-zone-cle"))
            self.assertFalse([a for a in self.adresses if "/api/ia" in a])


if __name__ == "__main__":
    unittest.main()
