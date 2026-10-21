"""Dictée vocale (lot 4, ARCHITECTURE.md §17.6 ; brief §11 ; CS72).

La reconnaissance vocale du navigateur est SIMULÉE (classe FausseReconnaissance posée avant le
chargement de la page) : aucun micro, aucun service en ligne. Familles :
    - bouton micro sur les champs data-dictee (formulaire « Signaler », fenêtre avec motif), absent si
      le navigateur ne propose pas la reconnaissance ;
    - première utilisation : avertissement du brief (« … Google ou Microsoft … »), une seule fois ;
      variante « sur ce PC » quand la reconnaissance sur l'appareil est disponible en français ;
    - texte dicté ajouté à la fin du champ, sans rien effacer ; second clic : arrêt ; erreurs ;
    - « Désactiver la dictée » : plus aucun bouton, réglage gardé sur le poste ;
    - téléphone sur une page non sécurisée (adresse réseau en http) : pas de bouton, aide « micro du
      clavier ».

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_dictee.py" -v
"""
import json
import unittest
import urllib.request

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil

RECONNAISSANCE_SIMULEE_JS = """(() => {
  window.__dictee = { instances: [], local: false };
  class FausseReconnaissance {
    constructor() {
      this.lang = ''; this.interimResults = false; this.continuous = false; this.processLocally = false;
      this.demarree = false; this.arretee = false;
      window.__dictee.instances.push(this);
    }
    start() { this.demarree = true; }
    stop() { this.arretee = true; setTimeout(() => { if (this.onend) this.onend(); }, 0); }
    static available(options) {
      return Promise.resolve(window.__dictee.local && options && options.processLocally ? 'available' : 'unavailable');
    }
  }
  window.SpeechRecognition = FausseReconnaissance;
  window.webkitSpeechRecognition = FausseReconnaissance;
  window.__dictee.dire = (texte, final) => {
    const r = window.__dictee.instances[window.__dictee.instances.length - 1];
    const resultat = [{ transcript: texte }];
    resultat.isFinal = final !== false;
    r.onresult({ resultIndex: 0, results: [resultat] });
  };
  window.__dictee.erreur = (code) => {
    const r = window.__dictee.instances[window.__dictee.instances.length - 1];
    r.onerror({ error: code });
  };
})();"""

SANS_RECONNAISSANCE_JS = """(() => { delete window.SpeechRecognition; delete window.webkitSpeechRecognition;
  Object.defineProperty(window, 'SpeechRecognition', { value: undefined });
  Object.defineProperty(window, 'webkitSpeechRecognition', { value: undefined }); })();"""

NOTER_TOASTS_JS = """(() => {
  window.__toasts = [];
  let dernier = '';
  new MutationObserver(() => {
    const zone = document.getElementById('toast');
    const texte = zone && zone.classList.contains('visible') ? zone.textContent.trim() : '';
    if (texte && texte !== dernier) window.__toasts.push(texte);
    dernier = texte;
  }).observe(document, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['class'] });
})();"""

CHAMP_DESCRIPTION = "#contenu textarea[name=description]"
BOUTON_DESCRIPTION = CHAMP_DESCRIPTION + " + .dictee-bouton"


class TestDictee(CasNavigateur):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serveur = ServeurPrevo()
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)

    def ouvrir(self, route="#/di/nouvelle", script=RECONNAISSANCE_SIMULEE_JS, contexte=None, page=None, url=None):
        contexte = contexte or self.contexte
        page = page or self.page
        if script:
            contexte.add_init_script(script)
        contexte.add_init_script(NOTER_TOASTS_JS)
        preregler_profil(contexte, "responsable", "Responsable")
        page.goto((url or self.serveur.url) + "/" + route)
        attendre_pret(page)
        return page

    def attendre_toast(self, page, motif):
        return page.wait_for_function(
            "motif => (window.__toasts || []).find((t) => t.includes(motif)) || null", arg=motif).json_value()

    def test_bouton_micro_sur_les_champs_dictes_et_dans_une_fenetre(self):
        page = self.ouvrir()
        page.wait_for_selector(BOUTON_DESCRIPTION)
        self.assertEqual(page.get_attribute(BOUTON_DESCRIPTION, "aria-pressed"), "false")
        self.assertGreaterEqual(page.locator(BOUTON_DESCRIPTION).bounding_box()["height"], 40)
        # Une fenêtre avec un champ dicté reçoit aussi son micro
        page.evaluate("""() => { UI.fenetre({ titre: 'Essai', contenu: UI.element(UI.html`<div><textarea name="essai" data-dictee></textarea></div>`) }); }""")
        page.wait_for_selector("dialog[open] textarea[name=essai] + .dictee-bouton")
        page.keyboard.press("Escape")

    def test_absent_sans_reconnaissance_du_navigateur(self):
        page = self.ouvrir(script=SANS_RECONNAISSANCE_JS)
        page.wait_for_selector(CHAMP_DESCRIPTION)
        page.wait_for_timeout(300)
        self.assertEqual(page.locator(".dictee-bouton").count(), 0)
        self.assertFalse(page.evaluate("Dictee.prisEnCharge()"))

    def test_avertissement_une_seule_fois_puis_texte_ajoute_sans_ecraser(self):
        page = self.ouvrir()
        page.fill(CHAMP_DESCRIPTION, "Bruit au démarrage")
        page.click(BOUTON_DESCRIPTION)
        page.wait_for_selector("dialog[open] .dictee-avertissement")
        self.assertIn("Google ou Microsoft", page.inner_text("dialog[open]"))
        page.click("dialog[open] .fenetre-actions .btn-primaire")           # « Continuer »
        page.wait_for_function("window.__dictee.instances.length === 1 && window.__dictee.instances[0].demarree")
        instance = page.evaluate("({ lang: window.__dictee.instances[0].lang, local: window.__dictee.instances[0].processLocally })")
        self.assertEqual(instance, {"lang": "fr-FR", "local": False})
        self.assertEqual(page.get_attribute(BOUTON_DESCRIPTION, "aria-pressed"), "true")
        page.evaluate("window.__dictee.dire('du moteur', false)")         # provisoire
        self.assertEqual(page.input_value(CHAMP_DESCRIPTION), "Bruit au démarrage du moteur")
        page.evaluate("window.__dictee.dire('côté accouplement')")        # définitif
        self.assertEqual(page.input_value(CHAMP_DESCRIPTION), "Bruit au démarrage côté accouplement")
        page.click(BOUTON_DESCRIPTION)                                     # second clic : arrêt
        page.wait_for_function("(s) => document.querySelector(s).getAttribute('aria-pressed') === 'false'", arg=BOUTON_DESCRIPTION)
        self.assertEqual(page.input_value(CHAMP_DESCRIPTION), "Bruit au démarrage côté accouplement")
        self.assertTrue(page.evaluate("JSON.parse(localStorage.getItem('prevo.dictee')).avertie"))
        # Deuxième utilisation : pas d'avertissement
        page.click(BOUTON_DESCRIPTION)
        page.wait_for_function("window.__dictee.instances.length === 2 && window.__dictee.instances[1].demarree")
        self.assertEqual(page.locator("dialog[open]").count(), 0)

    def test_reconnaissance_sur_l_appareil_dit_reste_sur_ce_pc(self):
        page = self.ouvrir()
        page.evaluate("window.__dictee.local = true")
        page.click(BOUTON_DESCRIPTION)
        page.wait_for_selector("dialog[open] .dictee-avertissement")
        self.assertIn("transcrite sur ce PC", page.inner_text("dialog[open]"))
        self.assertNotIn("Google", page.inner_text("dialog[open]"))
        page.click("dialog[open] .fenetre-actions .btn-primaire")
        page.wait_for_function("window.__dictee.instances.length === 1")
        self.assertTrue(page.evaluate("window.__dictee.instances[0].processLocally"))
        self.assertEqual(page.evaluate("JSON.parse(localStorage.getItem('prevo.dictee')).avertie"), "local")
        # Le français local n'est plus proposé : la voix partirait chez Google ou Microsoft → nouvel
        # avertissement (relecture du lot 4 : l'accord « sur ce PC » ne vaut pas pour le nuage)
        page.click(BOUTON_DESCRIPTION)                                      # arrêt
        page.wait_for_function("(s) => document.querySelector(s).getAttribute('aria-pressed') === 'false'", arg=BOUTON_DESCRIPTION)
        page.evaluate("window.__dictee.local = false")
        page.click(BOUTON_DESCRIPTION)
        page.wait_for_selector("dialog[open] .dictee-avertissement")
        self.assertIn("Google ou Microsoft", page.inner_text("dialog[open]"))
        page.click("dialog[open] .fenetre-actions .btn-primaire")
        page.wait_for_function("window.__dictee.instances.length === 2 && !window.__dictee.instances[1].processLocally")
        self.assertEqual(page.evaluate("JSON.parse(localStorage.getItem('prevo.dictee')).avertie"), "nuage")

    def test_texte_tape_pendant_la_dictee_jamais_efface(self):
        """Relecture du lot 4 (D73, jamais d'écrasement) : ce qui est tapé au clavier (ou posé par
        « Utiliser » de l'IA) pendant que la dictée écoute reste dans le champ."""
        page = self.ouvrir()
        page.evaluate("localStorage.setItem('prevo.dictee', JSON.stringify({ active: true, avertie: 'nuage' }))")
        page.fill(CHAMP_DESCRIPTION, "Bruit au démarrage")
        page.click(BOUTON_DESCRIPTION)
        page.wait_for_function("window.__dictee.instances.length === 1 && window.__dictee.instances[0].demarree")
        page.evaluate("window.__dictee.dire('côté moteur')")
        self.assertEqual(page.input_value(CHAMP_DESCRIPTION), "Bruit au démarrage côté moteur")
        page.focus(CHAMP_DESCRIPTION)
        page.keyboard.press("End")
        page.keyboard.type(" puis odeur")
        page.evaluate("window.__dictee.dire('de brûlé', false)")          # provisoire
        self.assertEqual(page.input_value(CHAMP_DESCRIPTION), "Bruit au démarrage côté moteur puis odeur de brûlé")
        page.evaluate("window.__dictee.dire('de brûlé')")                  # définitif
        # Texte posé par un autre moyen (ex. « Utiliser » de l'IA) pendant l'écoute : gardé, puis complété
        page.evaluate("""(s) => { const c = document.querySelector(s); c.value = 'Texte proposé par l\\'IA.';
          c.dispatchEvent(new Event('input', { bubbles: true })); }""", CHAMP_DESCRIPTION)
        page.evaluate("window.__dictee.dire('et vibrations')")
        self.assertEqual(page.input_value(CHAMP_DESCRIPTION), "Texte proposé par l'IA. et vibrations")
        page.click(BOUTON_DESCRIPTION)                                      # arrêt : rien n'est retiré
        page.wait_for_function("(s) => document.querySelector(s).getAttribute('aria-pressed') === 'false'", arg=BOUTON_DESCRIPTION)
        self.assertEqual(page.input_value(CHAMP_DESCRIPTION), "Texte proposé par l'IA. et vibrations")

    def test_desactiver_la_dictee_retire_les_boutons(self):
        page = self.ouvrir()
        page.click(BOUTON_DESCRIPTION)
        page.wait_for_selector("dialog[open] .dictee-avertissement")
        page.click("dialog[open] .fenetre-actions .btn-fantome")           # « Désactiver la dictée »
        self.attendre_toast(page, "Dictée désactivée")
        self.assertEqual(page.locator(".dictee-bouton").count(), 0)
        self.assertEqual(page.evaluate("window.__dictee.instances.length"), 0)
        self.assertFalse(page.evaluate("JSON.parse(localStorage.getItem('prevo.dictee')).active"))
        page.reload()
        attendre_pret(page)
        page.wait_for_selector(CHAMP_DESCRIPTION)
        page.wait_for_timeout(300)
        self.assertEqual(page.locator(".dictee-bouton").count(), 0)

    def test_erreur_micro_refuse_annoncee(self):
        page = self.ouvrir()
        page.evaluate("localStorage.setItem('prevo.dictee', JSON.stringify({ active: true, avertie: true }))")
        page.click(BOUTON_DESCRIPTION)
        page.wait_for_function("window.__dictee.instances.length === 1")
        page.evaluate("window.__dictee.erreur('not-allowed')")
        self.assertIn("Micro refusé", self.attendre_toast(page, "Micro refusé"))

    def test_telephone_sur_page_non_securisee_aide_clavier(self):
        with urllib.request.urlopen(self.serveur.url + "/api/info", timeout=10) as reponse:
            adresses = json.loads(reponse.read().decode("utf-8"))["adresses_reseau"]
        if not adresses:
            self.skipTest("aucune adresse réseau sur ce PC : impossible d'ouvrir une page non sécurisée")
        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 375, "height": 812}, is_mobile=True, has_touch=True)
        self.addCleanup(contexte.close)
        page = contexte.new_page()
        self.surveiller(page)
        self.ouvrir(contexte=contexte, page=page, url=adresses[0].rstrip("/"))
        page.wait_for_selector(CHAMP_DESCRIPTION)
        self.assertFalse(page.evaluate("window.isSecureContext"))
        page.wait_for_selector(".dictee-aide")
        self.assertIn("micro du clavier", page.inner_text(".dictee-aide"))
        self.assertEqual(page.locator(".dictee-bouton").count(), 0)


if __name__ == "__main__":
    unittest.main()
