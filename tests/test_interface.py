"""Tests de js/interface.js (objet UI) et de css/style.css (charte Cockpit adaptée).

Tous les tests ouvrent la page tests/fixtures/guide-style.html en file:// : elle charge la feuille
de style, les bibliothèques de js/lib/ et js/interface.js, puis montre chaque composant.
Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_interface.py" -v
"""
import re
import unittest
import xml.etree.ElementTree as ET

from commun import RACINE, CasNavigateur, url_fichier

GUIDE = "tests/fixtures/guide-style.html"
ESPACES_INSECABLES = re.compile("[  ]")


def espaces_simples(texte):
    """Remplace les espaces insécables (fines ou non) produites par Intl par des espaces simples."""
    return ESPACES_INSECABLES.sub(" ", texte)


class CasGuide(CasNavigateur):
    """Ouvre le guide de style avant chaque test."""

    def setUp(self):
        super().setUp()
        self.ouvrir_guide()

    def ouvrir_guide(self, largeur=None, hauteur=800):
        if largeur is not None:
            self.page.set_viewport_size({"width": largeur, "height": hauteur})
        self.page.goto(url_fichier(GUIDE))
        self.page.wait_for_function("document.documentElement.dataset.etat === 'pret'")

    def evaluer(self, script, argument=None):
        return self.page.evaluate(script, argument)


# ---------------------------------------------------------------------------------------------
# Échappement, formats, badges
# ---------------------------------------------------------------------------------------------

class TestEchappementEtFormats(CasGuide):

    def test_html_echappe_balises_et_guillemets(self):
        resultat = self.evaluer("""() => String(UI.html`<p title="${'a"b'}">${'<script>alert(1)</script>'} & ${"l'atelier"}</p>`)""")
        self.assertEqual(resultat, '<p title="a&quot;b">&lt;script&gt;alert(1)&lt;/script&gt; & l&#39;atelier</p>')

    def test_html_joint_les_tableaux_et_garde_les_fragments_surs(self):
        resultat = self.evaluer("""() => String(UI.html`<ul>${['<b>', UI.html`<li>${'x&y'}</li>`, null, undefined, false, 0]}</ul>`)""")
        self.assertEqual(resultat, "<ul>&lt;b&gt;<li>x&amp;y</li>0</ul>")

    def test_brut_insere_sans_echapper(self):
        resultat = self.evaluer("""() => String(UI.html`<div>${UI.brut('<b>sûr</b>')}${'<i>non</i>'}</div>`)""")
        self.assertEqual(resultat, "<div><b>sûr</b>&lt;i&gt;non&lt;/i&gt;</div>")

    def test_aucune_balise_injectee_dans_le_dom(self):
        nombre = self.evaluer("""() => {
            const zone = document.createElement('div');
            zone.innerHTML = UI.html`<span>${'<img src=x onerror="window.pirate=1">'}</span>`;
            document.body.appendChild(zone);
            return zone.querySelectorAll('img').length + (window.pirate ? 10 : 0);
        }""")
        self.assertEqual(nombre, 0)

    def test_echapper(self):
        self.assertEqual(self.evaluer("() => UI.echapper(`<a href=\"x\">'&'</a>`)"),
                         "&lt;a href=&quot;x&quot;&gt;&#39;&amp;&#39;&lt;/a&gt;")
        self.assertEqual(self.evaluer("() => UI.echapper(null) + UI.echapper(undefined)"), "")

    def test_dates_francaises(self):
        self.assertEqual(self.evaluer("() => UI.dateFr('2026-03-15')"), "15/03/2026")
        self.assertEqual(self.evaluer("() => UI.dateFr('2026-03-15 08:05')"), "15/03/2026")
        self.assertEqual(self.evaluer("() => UI.dateFr('')"), "")
        self.assertEqual(self.evaluer("() => UI.dateHeureFr('2026-03-15 08:05')"), "15/03/2026 08:05")
        self.assertEqual(self.evaluer("() => UI.dateHeureFr('2026-03-15T08:05')"), "15/03/2026 08:05")
        self.assertEqual(self.evaluer("() => UI.dateHeureFr('2026-03-15')"), "15/03/2026")

    def test_milliers_espace_insecable_visible(self):
        # T40 (demande de Nicolas) : l'espace fine U+202F d'Intl est presque invisible avec la police
        # Sora (« 15855 h ») ; l'affichage utilise l'espace insécable U+00A0, bien visible.
        for appel, attendu in (("UI.nombreFr(15855)", "15\u00a0855"),
                               ("UI.euro(1234.5)", "1\u00a0234,50\u00a0€"),
                               ("UI.heures(1500)", "1\u00a0500")):
            with self.subTest(appel=appel):
                texte = self.evaluer("() => " + appel)
                self.assertNotIn("\u202f", texte)
                self.assertIn(attendu, texte)

    def test_nombres_euros_heures(self):
        self.assertEqual(espaces_simples(self.evaluer("() => UI.nombreFr('1234.5')")), "1 234,5")
        self.assertEqual(espaces_simples(self.evaluer("() => UI.nombreFr('12.5', 2)")), "12,50")
        self.assertEqual(espaces_simples(self.evaluer("() => UI.nombreFr(0.333333)")), "0,33")
        self.assertEqual(self.evaluer("() => UI.nombreFr('')"), "–")
        self.assertEqual(self.evaluer("() => UI.nombreFr('abc')"), "–")
        self.assertEqual(espaces_simples(self.evaluer("() => UI.euro('1234.5')")), "1 234,50 €")
        self.assertEqual(espaces_simples(self.evaluer("() => UI.euro('96', 0)")), "96 €")
        self.assertEqual(espaces_simples(self.evaluer("() => UI.heures('1.5')")), "1,5 h")

    def test_badge_priorite_texte_et_classe(self):
        for numero in range(1, 5):
            code = "P%d" % numero
            fragment = self.evaluer("(p) => String(UI.badgePriorite(p))", code)
            self.assertIn("prio-p%d" % numero, fragment)
            texte = self.evaluer("""(p) => { const e = UI.element(UI.badgePriorite(p)); return e.textContent; }""", code)
            self.assertEqual(texte, code)
        self.assertIn("&lt;x&gt;", self.evaluer("() => String(UI.badgePriorite('<x>'))"))

    def test_couleurs_des_priorites(self):
        couleurs = self.evaluer("""() => {
            const style = getComputedStyle(document.documentElement);
            const zone = document.createElement('div');
            zone.innerHTML = UI.html`${['P1','P2','P3','P4'].map((p) => UI.badgePriorite(p))}`;
            document.body.appendChild(zone);
            const temoin = document.createElement('span');
            document.body.appendChild(temoin);
            const couleur = (v) => { temoin.style.color = 'var(' + v + ')'; return getComputedStyle(temoin).color; };
            return {
              badges: Array.from(zone.children).map((b) => getComputedStyle(b).backgroundColor),
              attendues: ['--rouge', '--ambre', '--cyan', '--muted'].map(couleur),
            };
        }""")
        self.assertEqual(couleurs["badges"], couleurs["attendues"])

    def test_badge_statut(self):
        self.assertIn('class="badge statut ko"', self.evaluer("() => String(UI.badgeStatut('Refusée'))"))
        self.assertIn('class="badge statut ok"', self.evaluer("() => String(UI.badgeStatut('en service'))"))
        self.assertIn('class="badge statut neutre"', self.evaluer("() => String(UI.badgeStatut('Inconnu'))"))

    def test_icones_demandees(self):
        noms = ["accueil", "demandes", "ordres", "parc", "parametres", "apropos", "plus", "recherche", "qr",
                "photo", "retour", "imprimer", "sauvegarde", "alerte", "telephone", "controle", "menu", "fermer",
                "export", "utilisateur", "engrenage", "cle", "horloge"]
        for nom in noms:
            svg = self.evaluer("(n) => String(UI.icone(n))", nom)
            self.assertTrue(svg.startswith('<svg class="icone"'), nom)
        self.assertEqual(self.evaluer("() => String(UI.icone('inexistante'))"), "")

    def test_icones_lot2_magasin_et_preventif(self):
        """ARCHITECTURE.md §14.2 : icônes « magasin » (carton) et « preventif » (calendrier coché),
        SVG au trait 24 × 24 bien formé, couleur du texte (currentColor), comme les autres."""
        calendrier = self.evaluer("() => String(UI.icone('calendrier'))")
        for nom in ("magasin", "preventif"):
            with self.subTest(icone=nom):
                svg = self.evaluer("(n) => String(UI.icone(n))", nom)
                self.assertTrue(svg.startswith('<svg class="icone"'), svg)
                racine = ET.fromstring(svg)          # lève une erreur si le SVG est mal formé
                self.assertEqual(racine.tag, "svg")
                self.assertEqual(racine.get("viewBox"), "0 0 24 24")
                traces = list(racine)
                self.assertTrue(traces, "aucun tracé")
                for trace in traces:
                    self.assertIn(trace.tag, ("path", "circle", "rect"))
                    # Ni couleur ni remplissage codés en dur : le trait vient de .icone (currentColor)
                    self.assertIsNone(trace.get("fill"))
                    self.assertIsNone(trace.get("stroke"))
                self.assertNotEqual(svg, calendrier)
                style = self.evaluer("""(n) => {
                    const zone = document.createElement('span');
                    zone.style.color = 'rgb(1, 2, 3)';
                    zone.innerHTML = String(UI.icone(n));
                    document.body.appendChild(zone);
                    const calcule = getComputedStyle(zone.querySelector('svg'));
                    const resultat = { trait: calcule.stroke, fond: calcule.fill };
                    zone.remove();
                    return resultat;
                }""", nom)
                self.assertEqual(style, {"trait": "rgb(1, 2, 3)", "fond": "none"})


# ---------------------------------------------------------------------------------------------
# Tableau, fenêtres, toast, onglets
# ---------------------------------------------------------------------------------------------

class TestComposantsInteractifs(CasGuide):

    def identifiants_du_tableau(self):
        return self.page.locator("#demo-tableau tbody tr td:first-child").all_inner_texts()

    def test_tableau_trie_au_clic(self):
        # tri initial : date prévue croissante, cellules vides à la fin
        self.assertEqual(self.identifiants_du_tableau(),
                         ["OT-2026-0098", "OT-2026-0107", "OT-2026-0101", "OT-2026-0110"])
        self.page.click("#demo-tableau th button:has-text('Coût')")
        self.assertEqual(self.identifiants_du_tableau(),
                         ["OT-2026-0101", "OT-2026-0107", "OT-2026-0098", "OT-2026-0110"])
        self.assertEqual(self.page.get_attribute("#demo-tableau th:has-text('Coût')", "aria-sort"), "ascending")
        self.page.click("#demo-tableau th button:has-text('Coût')")
        self.assertEqual(self.identifiants_du_tableau(),
                         ["OT-2026-0098", "OT-2026-0107", "OT-2026-0101", "OT-2026-0110"])
        self.assertEqual(self.page.get_attribute("#demo-tableau th:has-text('Coût')", "aria-sort"), "descending")
        self.page.click("#demo-tableau th button:has-text('Équipement')")
        self.assertEqual(self.identifiants_du_tableau(),
                         ["OT-2026-0098", "OT-2026-0107", "OT-2026-0110", "OT-2026-0101"])

    def test_tableau_clic_sur_une_ligne_et_tableau_vide(self):
        self.page.click("#demo-tableau tbody tr:has-text('OT-2026-0101') td:nth-child(2)")
        self.assertEqual(self.evaluer("() => window.lignesCliquees"), ["OT-2026-0101"])
        texte = self.evaluer("""() => UI.tableau({ colonnes: [{ cle: 'a', libelle: 'A' }], lignes: [],
                                                   vide: 'Aucun ordre de travail.' }).textContent""")
        self.assertIn("Aucun ordre de travail.", texte)

    def test_tableau_echappe_les_cellules(self):
        nombre = self.evaluer("""() => UI.tableau({ colonnes: [{ cle: 'a', libelle: 'A' }],
                                                    lignes: [{ a: '<img src=x>' }] }).querySelectorAll('img').length""")
        self.assertEqual(nombre, 0)

    def test_fenetre_renvoie_la_valeur_du_bouton(self):
        self.evaluer("""() => { window.choix = 'rien'; UI.fenetre({ titre: 'Essai', contenu: 'Texte <b>brut</b>',
            boutons: [{ libelle: 'Non', valeur: 'non' }, { libelle: 'Oui', valeur: 'oui', classe: 'btn-primaire' }] })
            .then((v) => { window.choix = v; }); }""")
        dialogue = self.page.locator("dialog.dialogue")
        self.assertTrue(dialogue.is_visible())
        self.assertEqual(dialogue.locator("h2").inner_text(), "Essai")
        self.assertIn("Texte <b>brut</b>", dialogue.locator(".fenetre-corps").inner_text())
        dialogue.locator("button:has-text('Oui')").click()
        self.page.wait_for_function("window.choix === 'oui'")
        self.assertEqual(self.page.locator("dialog").count(), 0)

    def test_fenetre_echap_renvoie_null(self):
        self.page.click("#btn-fenetre")
        self.page.wait_for_selector("dialog.dialogue")
        self.page.keyboard.press("Escape")
        self.page.wait_for_function("document.querySelector('#resultat-fenetre').textContent === 'Fenêtre : null'")

    def test_confirmer(self):
        self.evaluer("() => { window.reponse = 'rien'; UI.confirmer('Supprimer ?').then((v) => { window.reponse = v; }); }")
        self.page.click("dialog .btn-primaire")
        self.page.wait_for_function("window.reponse === true")
        self.evaluer("() => { window.reponse = 'rien'; UI.confirmer('Supprimer ?', { non: 'Garder' }).then((v) => { window.reponse = v; }); }")
        self.page.click("dialog button:has-text('Garder')")
        self.page.wait_for_function("window.reponse === false")

    def test_demander_motif_refuse_un_motif_vide(self):
        self.evaluer("""() => { window.motif = 'rien';
            UI.demanderMotif('Refuser la demande', 'Motif du refus').then((v) => { window.motif = v; }); }""")
        dialogue = self.page.locator("dialog.dialogue")
        self.assertEqual(dialogue.locator("textarea").get_attribute("data-dictee"), "")
        dialogue.locator("button:has-text('Valider')").click()
        self.assertTrue(dialogue.is_visible())
        self.assertIn("obligatoire", dialogue.locator(".erreur-champ").inner_text())
        self.assertEqual(dialogue.locator("textarea").get_attribute("aria-invalid"), "true")
        dialogue.locator("textarea").fill("    ")
        dialogue.locator("button:has-text('Valider')").click()
        self.assertTrue(dialogue.is_visible())
        self.assertEqual(self.evaluer("() => window.motif"), "rien")
        dialogue.locator("textarea").fill("  Équipement remplacé la semaine prochaine  ")
        dialogue.locator("button:has-text('Valider')").click()
        self.page.wait_for_function("window.motif !== 'rien'")
        self.assertEqual(self.evaluer("() => window.motif"), "Équipement remplacé la semaine prochaine")

    def test_demander_motif_annule_renvoie_null(self):
        self.evaluer("() => { window.motif = 'rien'; UI.demanderMotif('Titre', 'Motif').then((v) => { window.motif = v; }); }")
        self.page.click("dialog button:has-text('Annuler')")
        self.page.wait_for_function("window.motif === null")

    def test_toast_role_status(self):
        self.evaluer("() => UI.toast('DI-2026-0042 créée.', 'succes')")
        # le toast est rempli au tour suivant : on attend qu'il soit visible avant de lire son texte.
        # La classe « visible » ne suffit pas : visibility passe de hidden à visible par une transition
        # (.2s) et, tant que la valeur calculée est encore « hidden », innerText vaut ''.
        self.page.wait_for_function(
            "document.querySelector('#toast') && document.querySelector('#toast').classList.contains('visible')"
            " && getComputedStyle(document.querySelector('#toast')).visibility === 'visible'")
        toast = self.page.locator("#toast")
        self.assertEqual(toast.get_attribute("role"), "status")
        self.assertEqual(toast.inner_text(), "DI-2026-0042 créée.")
        self.assertIn("succes", toast.get_attribute("class"))

    def test_toast_cree_vide_puis_rempli_au_tour_suivant(self):
        resultat = self.evaluer("""() => {
            const zone = UI.toast('Bonjour', 'info');
            return [zone.textContent, zone.getAttribute('role'), document.querySelectorAll('#toast').length];
        }""")
        self.assertEqual(resultat, ["", "status", 1])
        self.page.wait_for_function("document.querySelector('#toast').textContent === 'Bonjour'")

    def test_toast_reutilise_la_zone_existante(self):
        resultat = self.evaluer("""() => {
            const zone = document.createElement('div');
            zone.id = 'toast'; zone.className = 'toast'; zone.setAttribute('role', 'status');
            document.body.appendChild(zone);
            const rendu = UI.toast('Réutilisé', 'erreur');
            return [rendu === zone, zone.textContent, zone.className, document.querySelectorAll('#toast').length];
        }""")
        self.assertEqual(resultat, [True, "Réutilisé", "toast erreur visible", 1])

    def test_html_refuse_l_appel_sans_gabarit(self):
        for appel in ("UI.html('<img src=x onerror=alert(1)>')", "UI.html(42)", "UI.html()"):
            message = self.evaluer("""(appel) => {
                try { new Function('return ' + appel)(); return null; } catch (e) { return e.message; }
            }""", appel)
            self.assertIsNotNone(message, appel)
            self.assertIn("UI.html s'utilise comme gabarit", message)

    def test_onglets(self):
        onglet = self.page.locator("#demo-onglets [role=tab]:has-text('Exécution')")
        onglet.click()
        self.assertEqual(onglet.get_attribute("aria-selected"), "true")
        panneau = self.page.locator("#" + onglet.get_attribute("aria-controls"))
        self.assertTrue(panneau.is_visible())
        self.assertIn("Opérations à cocher", panneau.inner_text())
        self.page.keyboard.press("ArrowRight")
        self.assertEqual(self.page.locator("#demo-onglets [aria-selected=true]").inner_text(), "Compte rendu")

    def test_bandeau(self):
        resultat = self.evaluer("""() => { const b = UI.bandeau('securite', 'Impact <sécurité>');
            return [b.className, b.getAttribute('role'), b.textContent]; }""")
        self.assertEqual(resultat, ["bandeau-securite", "alert", "Impact <sécurité>"])
        self.assertEqual(self.evaluer("() => UI.bandeau('attention', 'x').className"), "alerte attention")


# ---------------------------------------------------------------------------------------------
# Formulaires et sélecteur d'équipement
# ---------------------------------------------------------------------------------------------

class TestFormulaires(CasGuide):

    def test_champs_selon_le_type_du_schema(self):
        resultat = self.evaluer("""() => {
            const form = document.createElement('form');
            const ajout = (def, v, o) => form.appendChild(UI.champ(def, v, o));
            ajout({ nom: 'titre', type: 'texte', libelle: 'Titre', obligatoire: true }, 'Fuite');
            ajout({ nom: 'compte_rendu', type: 'texte_long', libelle: 'Compte rendu' }, 'ligne 1');
            ajout({ nom: 'quantite', type: 'entier', libelle: 'Quantité' }, '3');
            ajout({ nom: 'heures', type: 'decimal', libelle: 'Heures' }, '1.5');
            ajout({ nom: 'date_prevue', type: 'date', libelle: 'Date' }, '2026-10-21');
            ajout({ nom: 'date_debut', type: 'date_heure', libelle: 'Début' }, '2026-10-21 08:30');
            ajout({ nom: 'remise_service', type: 'booleen', libelle: 'Remis en service' }, '1');
            ajout({ nom: 'arret', type: 'booleen', libelle: 'Arrêt' }, '0');
            ajout({ nom: 'criticite', type: 'choix', libelle: 'Criticité', valeurs: ['A', 'B', 'C'], defaut: 'B' }, undefined);
            ajout({ nom: 'technicien_id', type: 'ref', table: 'techniciens', libelle: 'Technicien' }, 'TEC-0002',
                  { liste: [{ valeur: 'TEC-0001', libelle: 'Léa' }, { valeur: 'TEC-0002', libelle: 'Karim' }] });
            document.body.appendChild(form);
            const champ = (n) => form.querySelector('[name="' + n + '"]');
            form.querySelector('[name=heures]').value = '2,25';
            return {
              valeurs: UI.lireFormulaire(form),
              requis: champ('titre').required && champ('titre').getAttribute('aria-required') === 'true',
              marqueRequis: form.querySelector('[data-champ=titre] .requis') !== null,
              dictee: champ('compte_rendu').tagName + ':' + champ('compte_rendu').hasAttribute('data-dictee'),
              typesHtml: ['date_prevue', 'date_debut', 'remise_service'].map((n) => champ(n).type),
              optionsRef: Array.from(champ('technicien_id').options).map((o) => o.value + '=' + o.text),
              optionsChoix: Array.from(champ('criticite').options).map((o) => o.value),
              libelleRelie: form.querySelector('label[for="' + champ('titre').id + '"]') !== null,
            };
        }""")
        self.assertEqual(resultat["valeurs"], {
            "titre": "Fuite", "compte_rendu": "ligne 1", "quantite": "3", "heures": "2.25",
            "date_prevue": "2026-10-21", "date_debut": "2026-10-21 08:30", "remise_service": "1", "arret": "0",
            "criticite": "B", "technicien_id": "TEC-0002"})
        self.assertTrue(resultat["requis"])
        self.assertTrue(resultat["marqueRequis"])
        self.assertTrue(resultat["libelleRelie"])
        self.assertEqual(resultat["dictee"], "TEXTAREA:true")
        self.assertEqual(resultat["typesHtml"], ["date", "datetime-local", "checkbox"])
        self.assertEqual(resultat["optionsRef"], ["=—", "TEC-0001=Léa", "TEC-0002=Karim"])
        self.assertEqual(resultat["optionsChoix"], ["", "A", "B", "C"])

    def test_verifier_formulaire_signale_les_manques(self):
        self.page.click("#formulaire-demo button[type=submit]")
        erreurs = self.evaluer("() => UI.verifierFormulaire(document.querySelector('#formulaire-demo')).map((e) => e.nom)")
        self.assertEqual(erreurs, ["titre", "quantite", "compte_rendu", "remise_service"])
        self.assertEqual(self.page.get_attribute("#formulaire-demo [name=titre]", "aria-invalid"), "true")
        self.assertTrue(self.page.locator("#formulaire-demo [data-champ=titre] .erreur-champ").is_visible())

    def test_selecteur_equipement_recherche_et_choix(self):
        recherche = self.page.locator("#selecteur-demo input[type=search]")
        recherche.fill("pompe glycolee")
        options = self.page.locator("#selecteur-demo .selecteur-option")
        self.assertEqual(options.count(), 1)
        self.assertIn("POMPE-03", options.first.inner_text())
        options.first.click()
        self.assertEqual(self.evaluer("() => window.equipementChoisi"), "EQ-0003")
        self.assertEqual(self.page.input_value("#selecteur-demo input[name=equipement_id]"), "EQ-0003")
        self.assertEqual(self.evaluer("() => window.selecteurDemo.valeur()"), "EQ-0003")
        # un équipement inactif n'est pas proposé
        self.page.click("#selecteur-demo .selecteur-changer")
        recherche.fill("perceuse")
        self.assertEqual(options.count(), 0)
        self.assertIn("Aucun équipement", self.page.inner_text("#selecteur-demo .selecteur-aide"))

    def test_identifiant_depuis_qr(self):
        self.assertEqual(self.evaluer("() => UI.identifiantDepuisQR('http://192.168.1.10:8080/#/equipement/EQ-0007')"), "EQ-0007")
        self.assertEqual(self.evaluer("() => UI.identifiantDepuisQR('GMAO:EQ-0012')"), "EQ-0012")
        self.assertIsNone(self.evaluer("() => UI.identifiantDepuisQR('https://exemple.fr')"))

    def test_scan_non_propose_en_contexte_non_securise(self):
        resultat = self.evaluer("""() => {
            Object.defineProperty(window, 'isSecureContext', { value: false, configurable: true });
            const zone = document.createElement('div');
            document.body.appendChild(zone);
            UI.selecteurEquipement(zone, { equipements: window.equipementsDemo, localisations: [] });
            return [UI.cameraDisponible(), zone.querySelectorAll('.selecteur-scanner').length];
        }""")
        self.assertEqual(resultat, [False, 0])


# ---------------------------------------------------------------------------------------------
# QR code et photos
# ---------------------------------------------------------------------------------------------

class TestQrEtPhotos(CasGuide):

    def test_qr_svg_relu_par_jsqr(self):
        adresse = "http://192.168.1.10:8080/#/equipement/EQ-0007"
        relu = self.evaluer("""async (texte) => {
            const svg = String(UI.qrSvg(texte, 300));
            const image = new Image();
            image.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
            await image.decode();
            const toile = document.createElement('canvas');
            toile.width = 300; toile.height = 300;
            const contexte = toile.getContext('2d');
            contexte.drawImage(image, 0, 0, 300, 300);
            const pixels = contexte.getImageData(0, 0, 300, 300);
            const code = jsQR(pixels.data, 300, 300);
            return code ? code.data : null;
        }""", adresse)
        self.assertEqual(relu, adresse)

    def test_qr_svg_avec_accents(self):
        texte = "GMAO:EQ-0001 Pompe à eau glycolée"
        relu = self.evaluer("""async (texte) => {
            const image = new Image();
            image.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(String(UI.qrSvg(texte, 300)));
            await image.decode();
            const toile = document.createElement('canvas');
            toile.width = 300; toile.height = 300;
            const contexte = toile.getContext('2d');
            contexte.drawImage(image, 0, 0, 300, 300);
            const code = jsQR(contexte.getImageData(0, 0, 300, 300).data, 300, 300);
            return code ? code.data : null;
        }""", texte)
        self.assertEqual(relu, texte)

    def redimensionner(self, largeur, hauteur):
        return self.evaluer("""async ([largeur, hauteur]) => {
            const toile = document.createElement('canvas');
            toile.width = largeur; toile.height = hauteur;
            const contexte = toile.getContext('2d');
            contexte.fillStyle = 'rgb(40, 120, 200)';
            contexte.fillRect(0, 0, largeur, hauteur);
            contexte.fillStyle = 'rgb(250, 200, 40)';
            contexte.fillRect(0, 0, largeur / 2, hauteur / 2);
            const source = await new Promise((ok) => toile.toBlob(ok, 'image/png'));
            const fichier = new File([source], 'photo.png', { type: 'image/png' });
            const resultat = await UI.redimensionnerPhoto(fichier, 1280);
            const octets = new Uint8Array(await resultat.slice(0, 3).arrayBuffer());
            const image = await createImageBitmap(resultat);
            return { type: resultat.type, largeur: image.width, hauteur: image.height,
                     entete: Array.from(octets), taille: resultat.size };
        }""", [largeur, hauteur])

    def test_redimensionner_photo_paysage(self):
        resultat = self.redimensionner(3000, 2000)
        self.assertEqual(resultat["type"], "image/jpeg")
        self.assertEqual(resultat["entete"], [0xFF, 0xD8, 0xFF])  # signature JPEG
        self.assertEqual(resultat["largeur"], 1280)
        self.assertEqual(resultat["hauteur"], 853)  # 2000 × 1280 / 3000, proportions gardées
        self.assertGreater(resultat["taille"], 0)

    def test_redimensionner_photo_portrait_et_petite(self):
        portrait = self.redimensionner(1000, 3000)
        self.assertEqual((portrait["largeur"], portrait["hauteur"]), (427, 1280))
        petite = self.redimensionner(800, 600)
        self.assertEqual((petite["type"], petite["largeur"], petite["hauteur"]), ("image/jpeg", 800, 600))

    def test_nom_fichier_unique_accepte_par_le_serveur(self):
        noms = self.evaluer("() => [UI.nomFichierUnique('DI-2026-0042', 'jpg'), UI.nomFichierUnique('Équipe é/../x', 'JPG')]")
        for nom in noms:
            self.assertRegex(nom, r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
            self.assertNotIn("..", nom)
            self.assertTrue(nom.endswith(".jpg"))


# ---------------------------------------------------------------------------------------------
# Feuille de style : tailles, téléphone, impression
# ---------------------------------------------------------------------------------------------

class TestFeuilleDeStyle(CasGuide):

    def test_corps_en_16_px_et_champs_au_moins_16_px(self):
        self.assertEqual(self.evaluer("() => getComputedStyle(document.body).fontSize"), "16px")
        tailles = self.evaluer("""() => UI.$$('input:not([type=checkbox]):not([type=radio]):not([type=file]), select, textarea, .btn, .table td')
            .map((e) => parseFloat(getComputedStyle(e).fontSize))""")
        self.assertGreater(len(tailles), 10)
        self.assertGreaterEqual(min(tailles), 16)
        badges = self.evaluer("() => UI.$$('.badge, .table th').map((e) => parseFloat(getComputedStyle(e).fontSize))")
        self.assertTrue(all(13 <= t <= 14 for t in badges), badges)

    def test_police_sora_chargee(self):
        self.evaluer("() => document.fonts.ready")
        self.assertTrue(self.evaluer("() => document.fonts.check('16px Sora')"))
        self.assertIn("Sora", self.evaluer("() => getComputedStyle(document.body).fontFamily"))

    def test_telephone_boutons_et_zones_tactiles_48_px(self):
        self.ouvrir_guide(375, 812)
        hauteurs = self.evaluer("""() => UI.$$('.btn, .barre-bas a, .barre-bas button, .onglet, input:not([type=checkbox]):not([type=radio]):not([type=file]), select')
            .filter((e) => e.getClientRects().length > 0)
            .map((e) => [e.textContent.trim().slice(0, 30) || e.outerHTML.slice(0, 50), e.getBoundingClientRect().height])""")
        self.assertGreater(len(hauteurs), 20)
        trop_petits = [h for h in hauteurs if h[1] < 47.5]
        self.assertEqual(trop_petits, [])

    def test_telephone_en_tetes_de_tri_et_liens_boutons_48_px(self):
        self.ouvrir_guide(375, 812)
        hauteurs = self.evaluer("""() => UI.$$('.table th .tri, .lien-bouton')
            .filter((e) => e.getClientRects().length > 0)
            .map((e) => [e.className, e.getBoundingClientRect().height])""")
        self.assertGreaterEqual(len(hauteurs), 2)
        self.assertEqual([h for h in hauteurs if h[1] < 47.5], [])

    def test_contrastes_wcag_texte_normal(self):
        """Ratio >= 4,5:1 (luminances relatives WCAG) sur les couleurs réellement calculées."""
        script = """(theme) => {
            const calme = document.createElement('style');   // pas de transition en cours pendant la mesure
            calme.textContent = '*, *::before, *::after { transition: none !important; }';
            document.head.appendChild(calme);
            const racine = document.documentElement;
            if (theme === 'clair') racine.dataset.theme = 'clair'; else delete racine.dataset.theme;
            const lire = (c) => { const m = c.match(/[0-9.]+/g).map(Number); return { r: m[0], g: m[1], b: m[2], a: m.length > 3 ? m[3] : 1 }; };
            const sur = (dessus, dessous) => ({ r: dessus.r * dessus.a + dessous.r * (1 - dessus.a),
                g: dessus.g * dessus.a + dessous.g * (1 - dessus.a), b: dessus.b * dessus.a + dessous.b * (1 - dessus.a), a: 1 });
            const fondDe = (el) => {
                const pile = [];
                for (let e = el; e; e = e.parentElement) pile.push(lire(getComputedStyle(e).backgroundColor));
                let fond = { r: 255, g: 255, b: 255, a: 1 };
                for (let i = pile.length - 1; i >= 0; i -= 1) fond = sur(pile[i], fond);
                return fond;
            };
            const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
                return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
            const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
            const mesures = [];
            const mesurer = (nom, el, pseudo) => {
                if (!el) { mesures.push([nom, 0]); return; }
                const fond = fondDe(el);
                const texte = sur(lire(getComputedStyle(el, pseudo || null).color), fond);
                mesures.push([nom, Math.round(ratio(texte, fond) * 100) / 100]);
            };
            mesurer('btn-primaire', UI.$('.btn-primaire'));
            mesurer('badge violet', UI.$('.badge.violet'));
            mesurer('badge cyan', UI.$('.badge.cyan'));
            mesurer('placeholder', UI.$('input[placeholder]:not(.mesure)'), '::placeholder');
            mesurer('lien-bouton (cyan)', UI.$('.lien-bouton'));
            mesurer('lien (cyan)', UI.$('main a'));
            return mesures;
        }"""
        for theme in ("sombre", "clair"):
            for nom, ratio in self.evaluer(script, theme):
                with self.subTest(theme=theme, element=nom):
                    self.assertGreaterEqual(ratio, 4.5, "%s (%s) : %s:1" % (nom, theme, ratio))

    def test_navigation_selon_la_largeur(self):
        def etat():
            return self.evaluer("""() => ({
                menu: getComputedStyle(document.querySelector('.menu-lateral')).display,
                barre: getComputedStyle(document.querySelector('.barre-bas')).display,
                largeurLibelle: document.querySelector('.menu a .libelle').getBoundingClientRect().width,
                entreesBarre: document.querySelectorAll('.barre-bas > a, .barre-bas > button').length,
            })""")
        grand = etat()
        self.assertEqual((grand["menu"], grand["barre"]), ("flex", "none"))
        self.assertGreater(grand["largeurLibelle"], 30)
        self.page.click("#btn-replier")
        self.assertLessEqual(etat()["largeurLibelle"], 1)
        self.ouvrir_guide(900)
        tablette = etat()
        self.assertEqual(tablette["menu"], "flex")
        self.assertLessEqual(tablette["largeurLibelle"], 1)  # icônes seules
        self.ouvrir_guide(375)
        telephone = etat()
        self.assertEqual((telephone["menu"], telephone["barre"], telephone["entreesBarre"]), ("none", "grid", 5))

    def test_360_px_sans_defilement_horizontal(self):
        self.ouvrir_guide(360, 740)
        largeurs = self.evaluer("() => [document.documentElement.scrollWidth, document.documentElement.clientWidth, document.body.scrollWidth]")
        self.assertLessEqual(largeurs[0], largeurs[1], largeurs)
        self.assertLessEqual(largeurs[2], largeurs[1], largeurs)

    def test_impression_noir_sur_blanc_sans_menu(self):
        self.page.emulate_media(media="print")
        styles = self.evaluer("""() => {
            const s = (sel) => getComputedStyle(document.querySelector(sel));
            return {
              fond: s('body').backgroundColor, texte: s('body').color, fondHtml: s('html').backgroundColor,
              menu: s('.menu-lateral').display, barre: s('.barre-bas').display, demo: s('.bandeau-demo').display,
              bouton: s('#btn-theme').display, sansImpression: s('.sans-impression').display,
              carte: s('.carte').backgroundColor, titre: s('h1').color,
            };
        }""")
        self.assertEqual(styles["fond"], "rgb(255, 255, 255)")
        self.assertEqual(styles["fondHtml"], "rgb(255, 255, 255)")
        self.assertEqual(styles["texte"], "rgb(0, 0, 0)")
        self.assertEqual(styles["titre"], "rgb(0, 0, 0)")
        for cle in ("menu", "barre", "demo", "bouton", "sansImpression"):
            self.assertEqual(styles[cle], "none", cle)

    def test_impression_du_bon_de_travail_seul(self):
        self.evaluer("() => document.querySelector('#impression').appendChild(document.querySelector('#bon-demo').cloneNode(true))")
        self.page.emulate_media(media="print")
        resultat = self.evaluer("""() => ({
            coque: getComputedStyle(document.querySelector('.coque')).display,
            impression: getComputedStyle(document.querySelector('#impression')).display,
            sections: ['bt-entete', 'bt-equipement', 'bt-consignation', 'bt-travail', 'bt-operations', 'bt-pieces',
                       'bt-temps', 'bt-compte-rendu', 'bt-signatures']
              .filter((c) => document.querySelector('#impression .' + c)).length,
        })""")
        self.assertEqual(resultat, {"coque": "none", "impression": "block", "sections": 9})
        self.page.emulate_media(media="screen")
        self.assertEqual(self.evaluer("() => getComputedStyle(document.querySelector('#impression')).display"), "none")


# ---------------------------------------------------------------------------------------------
# Règles du code (ARCHITECTURE.md §2)
# ---------------------------------------------------------------------------------------------

class TestReglesDuCode(unittest.TestCase):

    def setUp(self):
        self.source = (RACINE / "js" / "interface.js").read_text(encoding="utf-8")
        self.css = (RACINE / "css" / "style.css").read_text(encoding="utf-8")

    def test_script_classique_un_seul_global(self):
        self.assertTrue(self.source.startswith("'use strict';"))
        self.assertIsNone(re.search(r"^\s*(import|export)\s", self.source, re.M))
        globaux = re.findall(r"^(?:const|let|var|function|class)\s+([A-Za-z_$][\w$]*)", self.source, re.M)
        self.assertEqual(globaux, ["UI"])

    def test_pas_de_fonctions_interdites(self):
        sans_commentaires = re.sub(r"//.*", "", re.sub(r"/\*.*?\*/", "", self.source, flags=re.S))
        for motif in (r"\balert\s*\(", r"\bconfirm\s*\(", r"\bprompt\s*\(", r"\bcrypto\b", r"\bclipboard\b",
                      r"\bfetch\s*\(", r"\bimport\s*\("):
            self.assertIsNone(re.search(motif, sans_commentaires), motif)
        # la caméra n'est demandée qu'après la vérification du contexte sécurisé
        self.assertIn("window.isSecureContext && navigator.mediaDevices", self.source)

    def test_couleurs_uniquement_dans_les_variables(self):
        lignes_fautives = []
        for numero, ligne in enumerate(self.css.splitlines(), 1):
            sans_variables = re.sub(r"--[\w-]+\s*:[^;]*;", "", ligne)
            if re.search(r"#[0-9A-Fa-f]{3,8}\b|rgba?\(|hsla?\(", sans_variables):
                lignes_fautives.append("%d: %s" % (numero, ligne.strip()))
        self.assertEqual(lignes_fautives, [])

    def test_police_et_mouvement_reduit(self):
        self.assertIn("url(polices/sora-latin-wght-normal.woff2)", self.css)
        self.assertIn("prefers-reduced-motion", self.css)
        self.assertTrue((RACINE / "css" / "polices" / "sora-latin-wght-normal.woff2").is_file())


if __name__ == "__main__":
    unittest.main()
