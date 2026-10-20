"""Tests du Parc, lot 2 (tâche T30) : valeur de remplacement, relevés de compteur, gammes préventives
de l'équipement (ARCHITECTURE.md §14.6, js/modules/parc-*.js).

Toujours serveur.py sur une copie du jeu de démo (ServeurPrevo) : les CSV sont relus sur le disque.
Familles (le nom du test le dit) :
    valeur  : valeur de remplacement de la démo affichée (« 32 400,00 € HT ») ; modification par le
              formulaire → colonne valeur_remplacement de equipements.csv ; montant négatif refusé ;
    releve  : relevé saisi sur le compteur horaire (technicien) → ligne dans releves.csv ; valeur plus
              basse que le dernier relevé → avertissement, « Annuler » n'écrit rien, puis confirmation
              explicite → écrit ; relevé au-dessus du seuil de la gamme seuil → OT « préventif
              conditionnel » sur le disque, toast, OT visible dans la carte Préventif ;
    gammes  : la carte Préventif liste les gammes de CP-01 avec leur statut (Preventif.etatGamme) ;
              demandeur : ni bouton « Saisir un relevé » ni lien vers les gammes et les OT ;
              téléphone 375 px : aucun défilement horizontal, zones tactiles d'au moins 48 px.

Les identifiants viennent de tests/fixtures/demo-scenarios.json (commun.scenarios_demo()) ; aucun
numéro d'OT n'est écrit en dur. Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_parc_lot2.py" -v
"""
import csv
import io
import re
import unittest
from pathlib import Path

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, scenarios_demo

SCENARIOS = scenarios_demo()
COMPTEUR_HORAIRE = SCENARIOS["compteur_horaire"]        # compteur en heures (CP-01)
COMPTEUR_SEUIL = SCENARIOS["compteur_seuil"]            # perte de charge en bar (CP-01)
GAMME_SEUIL = SCENARIOS["gamme_seuil"]                  # seuil 0,8 bar, dernier relevé sous le seuil
TECHNICIEN = SCENARIOS["technicien_br_valide"]
STATUTS_FERMES = ("Clôturé techniquement", "Clôturé administrativement", "Annulé")
ESPACES = re.compile(r"[\s  ]+")

# Même contrôle que tests/test_recette_lot1.py (PETITES_ZONES_JS) : toute zone cliquable de #contenu
# mesure au moins 48 px de haut sur téléphone. Recopié ici : importer ce fichier de test ferait
# aussi lancer ses tests.
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

# Chaque toast affiché est noté au moment où il apparaît (il disparaît au bout de 4 s : le lire
# après coup échouerait au hasard sur un poste chargé). Même outil que tests/test_preventif.py.
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


# ---------------------------------------------------------------------------
# Lecture des CSV sur le disque (comme un autre poste ou Excel)
# ---------------------------------------------------------------------------

def lire_csv(dossier, nom):
    """Lignes (dictionnaires) d'un CSV de Prévo sur le disque (UTF-8 avec BOM, « ; »)."""
    texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte), delimiter=";"))


def par_id(dossier, nom):
    return {ligne["id"]: ligne for ligne in lire_csv(dossier, nom)}


def brut(valeur):
    """Valeur sans l'apostrophe de protection (ARCHITECTURE.md §3.2)."""
    return valeur[1:] if valeur.startswith("'") else valeur


def nombre(valeur):
    return float(brut(valeur).replace(",", "."))


def espaces_simples(texte):
    return ESPACES.sub(" ", texte).strip()


def euro_fr(montant):
    """32400 → « 32 400,00 € » (espaces ordinaires : comparer après espaces_simples)."""
    return "{:,.2f}".format(montant).replace(",", " ").replace(".", ",") + " €"


def releves_du_compteur(dossier, compteur_id):
    """Relevés d'un compteur, du plus ancien au plus récent (date, puis identifiant)."""
    lignes = [r for r in lire_csv(dossier, "releves.csv") if r["compteur_id"] == compteur_id]
    return sorted(lignes, key=lambda r: (r["date"], r["id"]))


def ots_ouverts_de(dossier, gamme_id):
    return [ot for ot in lire_csv(dossier, "ordres_travail.csv")
            if ot["gamme_id"] == gamme_id and ot["statut"] not in STATUTS_FERMES]


def equipement_du_compteur(dossier, compteur_id):
    return par_id(dossier, "compteurs.csv")[compteur_id]["equipement_id"]


# ---------------------------------------------------------------------------
# Outils communs des tests
# ---------------------------------------------------------------------------

class CasParcLot2(CasNavigateur):
    """Ouvrir la fiche d'un équipement avec un profil, saisir un relevé, lire l'écran."""

    def ouvrir(self, serveur, equipement_id, profil="responsable", technicien_id="", nom="", largeur=1280, hauteur=900):
        page = self.page
        page.set_viewport_size({"width": largeur, "height": hauteur})
        preregler_profil(self.contexte, profil, nom=nom, technicien_id=technicien_id)
        page.goto(serveur.url + "/#/equipement/" + equipement_id)
        attendre_pret(page)
        page.wait_for_load_state("networkidle")      # écritures du démarrage (format, préventif) finies
        self.attendre_fiche()
        return page

    def attendre_fiche(self):
        self.page.wait_for_selector("#contenu .parc-carte-compteurs")
        self.page.wait_for_selector("#contenu .parc-preventif")

    def noter_les_toasts(self):
        """À appeler AVANT d'ouvrir la page : chaque toast affiché est noté dans window.__toasts."""
        self.contexte.add_init_script(NOTER_TOASTS_JS)

    def attendre_toast_note(self, motif):
        return self.page.wait_for_function(
            "motif => (window.__toasts || []).find((texte) => new RegExp(motif).test(texte)) || null",
            arg=motif).json_value()

    def texte(self, selecteur):
        return espaces_simples(self.page.inner_text(selecteur))

    def sans_defilement_horizontal(self, contexte):
        largeurs = self.page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        self.assertLessEqual(largeurs[0], largeurs[1], "défilement horizontal (%s) : %r" % (contexte, largeurs))

    def ouvrir_fenetre_releve(self, compteur_id):
        self.page.click(".parc-saisir-releve[data-compteur='%s']" % compteur_id)
        self.page.wait_for_selector("dialog.dialogue .parc-formulaire-releve")

    def enregistrer_releve(self):
        self.page.click("dialog.dialogue button:has-text('Enregistrer le relevé')")

    def attendre_fenetre_fermee(self):
        self.page.wait_for_selector("dialog.dialogue", state="detached")


# ---------------------------------------------------------------------------
# valeur : valeur de remplacement
# ---------------------------------------------------------------------------

class TestValeur(CasParcLot2):

    def test_valeur_de_remplacement_affichee_modifiee_et_ecrite_sur_le_disque(self):
        with ServeurPrevo() as serveur:
            equipement = equipement_du_compteur(serveur.dossier, COMPTEUR_HORAIRE)
            montant = nombre(par_id(serveur.dossier, "equipements.csv")[equipement]["valeur_remplacement"])
            page = self.ouvrir(serveur, equipement)
            self.assertEqual(self.texte(".parc-valeur-remplacement"), euro_fr(montant) + " HT")
            libelle = page.evaluate("""() => document.querySelector('.parc-valeur-remplacement')
                .previousElementSibling.textContent.trim()""")
            self.assertEqual(libelle, "Valeur de remplacement")

            page.evaluate("id => { location.hash = '#/equipement/' + id + '/modifier'; }", equipement)
            page.wait_for_selector("#parc-formulaire [name=valeur_remplacement]")
            self.assertEqual(nombre(page.input_value("#parc-formulaire [name=valeur_remplacement]")), montant)

            # Un montant négatif est refusé, sous le champ ; on reste sur le formulaire.
            page.fill("#parc-formulaire [name=valeur_remplacement]", "-5")
            page.click("#parc-formulaire button[type=submit]")
            erreur = page.locator("#parc-formulaire .champ[data-champ='valeur_remplacement'] .erreur-champ")
            erreur.wait_for(state="visible")
            self.assertIn("montant", erreur.inner_text())
            self.assertTrue(page.evaluate("location.hash").endswith("/modifier"))

            page.fill("#parc-formulaire [name=valeur_remplacement]", "12 500,5")
            page.click("#parc-formulaire button[type=submit]")
            page.wait_for_function("id => location.hash === '#/equipement/' + id", arg=equipement)
            self.attendre_fiche()
            page.wait_for_function("""() => (document.querySelector('.parc-valeur-remplacement') || {}).textContent
                && document.querySelector('.parc-valeur-remplacement').textContent.replace(/[\\s\\u00a0\\u202f]+/g, ' ')
                   === '12 500,50 € HT'""")
            ligne = par_id(serveur.dossier, "equipements.csv")[equipement]
            self.assertEqual(brut(ligne["valeur_remplacement"]), "12500.5")


# ---------------------------------------------------------------------------
# releve : saisie d'un relevé de compteur
# ---------------------------------------------------------------------------

class TestReleve(CasParcLot2):

    def test_releve_saisi_par_un_technicien_sur_le_compteur_horaire_ligne_dans_releves_csv(self):
        with ServeurPrevo() as serveur:
            equipement = equipement_du_compteur(serveur.dossier, COMPTEUR_HORAIRE)
            dernier = releves_du_compteur(serveur.dossier, COMPTEUR_HORAIRE)[-1]
            technicien = par_id(serveur.dossier, "techniciens.csv")[TECHNICIEN]
            ids_avant = set(par_id(serveur.dossier, "releves.csv"))
            self.noter_les_toasts()
            page = self.ouvrir(serveur, equipement, profil="technicien", technicien_id=TECHNICIEN)
            jour = page.evaluate("Donnees.aujourdhui()")
            nouvelle = int(nombre(dernier["valeur"])) + 25

            self.ouvrir_fenetre_releve(COMPTEUR_HORAIRE)
            self.assertEqual(page.input_value("dialog.dialogue [name=date]"), jour)    # aujourd'hui par défaut
            self.assertIn("Dernier relevé", self.texte("dialog.dialogue .parc-releve-precedent"))
            page.fill("dialog.dialogue [name=valeur]", str(nouvelle))
            self.enregistrer_releve()
            self.attendre_fenetre_fermee()
            self.assertEqual(self.attendre_toast_note(r"^Relevé enregistré\.$"), "Relevé enregistré.")

            nouveaux = [r for r in lire_csv(serveur.dossier, "releves.csv") if r["id"] not in ids_avant]
            self.assertEqual(len(nouveaux), 1, nouveaux)
            releve = nouveaux[0]
            self.assertEqual((releve["compteur_id"], releve["date"]), (COMPTEUR_HORAIRE, jour))
            self.assertEqual(nombre(releve["valeur"]), nouvelle)
            self.assertEqual(releve["utilisateur"], technicien["prenom"] + " " + technicien["nom"])

            # La fiche se réaffiche avec le nouveau dernier relevé.
            attendu = "{:,}".format(nouvelle).replace(",", " ")
            page.wait_for_function("""([id, attendu]) => {
                const zone = document.querySelector(".parc-compteurs li[data-compteur='" + id + "'] .parc-dernier-releve");
                return zone && zone.textContent.replace(/[\\s\\u00a0\\u202f]+/g, ' ').includes(attendu);
            }""", arg=[COMPTEUR_HORAIRE, attendu])

    def test_releve_plus_bas_avertissement_annulation_puis_confirmation_explicite(self):
        with ServeurPrevo() as serveur:
            equipement = equipement_du_compteur(serveur.dossier, COMPTEUR_HORAIRE)
            dernier = releves_du_compteur(serveur.dossier, COMPTEUR_HORAIRE)[-1]
            plus_bas = int(nombre(dernier["valeur"])) - 100
            nombre_avant = len(lire_csv(serveur.dossier, "releves.csv"))
            page = self.ouvrir(serveur, equipement)

            # Valeur plus basse : avertissement, la fenêtre reste ouverte ; « Annuler » n'écrit rien.
            self.ouvrir_fenetre_releve(COMPTEUR_HORAIRE)
            page.fill("dialog.dialogue [name=valeur]", str(plus_bas))
            self.enregistrer_releve()
            page.wait_for_selector("dialog.dialogue .parc-releve-baisse", state="visible")
            self.assertIn("remplacé ou remis à zéro", self.texte("dialog.dialogue .parc-releve-baisse"))
            self.assertTrue(page.is_visible("dialog.dialogue .parc-releve-erreur-baisse"))
            page.click("dialog.dialogue button:has-text('Annuler')")
            self.attendre_fenetre_fermee()
            page.wait_for_load_state("networkidle")
            self.assertEqual(len(lire_csv(serveur.dossier, "releves.csv")), nombre_avant)

            # Une valeur corrigée (plus haute) fait disparaître l'avertissement.
            self.ouvrir_fenetre_releve(COMPTEUR_HORAIRE)
            champ = page.locator("dialog.dialogue [name=valeur]")
            champ.fill(str(plus_bas))
            self.assertFalse(page.is_visible("dialog.dialogue .parc-releve-baisse"))   # rien pendant la frappe
            self.enregistrer_releve()
            page.wait_for_selector("dialog.dialogue .parc-releve-baisse", state="visible")
            champ.fill(str(plus_bas + 500))
            page.wait_for_selector("dialog.dialogue .parc-releve-baisse", state="hidden")

            # Confirmation explicite (compteur remplacé) : le relevé plus bas est écrit.
            champ.fill(str(plus_bas))
            self.enregistrer_releve()
            page.wait_for_selector("dialog.dialogue .parc-releve-baisse", state="visible")
            self.assertEqual(len(lire_csv(serveur.dossier, "releves.csv")), nombre_avant)
            page.check("dialog.dialogue [name=baisse_confirmee]")
            self.assertFalse(page.is_visible("dialog.dialogue .parc-releve-erreur-baisse"))
            self.enregistrer_releve()
            self.attendre_fenetre_fermee()
            releves = lire_csv(serveur.dossier, "releves.csv")
            self.assertEqual(len(releves), nombre_avant + 1)
            self.assertEqual(nombre(releves_du_compteur(serveur.dossier, COMPTEUR_HORAIRE)[-1]["valeur"]), plus_bas)
            self.attendre_fiche()
            page.wait_for_load_state("networkidle")

    def test_releve_controle_sur_les_lignes_fraiches_baisse_refusee_si_un_autre_poste_a_releve_plus_haut(self):
        with ServeurPrevo() as serveur:
            equipement = equipement_du_compteur(serveur.dossier, COMPTEUR_HORAIRE)
            dernier = int(nombre(releves_du_compteur(serveur.dossier, COMPTEUR_HORAIRE)[-1]["valeur"]))
            page = self.ouvrir(serveur, equipement)
            jour = page.evaluate("Donnees.aujourdhui()")
            self.ouvrir_fenetre_releve(COMPTEUR_HORAIRE)
            # Pendant la saisie, un autre poste enregistre un relevé bien plus élevé (fichier sur le disque).
            chemin = Path(serveur.dossier) / "releves.csv"
            chemin.write_bytes(chemin.read_bytes() + ("REL-999999;%s;%s;%d;Autre poste\r\n"
                                                      % (COMPTEUR_HORAIRE, jour, dernier + 1000)).encode("utf-8"))
            # Le premier essai d'écriture est refusé (409, version périmée) : la table est relue.
            self.autoriser_erreur(re.compile(r"status of 409.*/api/csv/releves"))
            page.fill("dialog.dialogue [name=valeur]", str(dernier + 10))    # plus haut que le relevé vu
            self.enregistrer_releve()
            page.wait_for_function("() => /plus basse que le dernier relevé/.test(document.getElementById('toast').textContent)")
            self.assertTrue(page.is_visible("dialog.dialogue"))                  # rien d'enregistré
            valeurs = [nombre(r["valeur"]) for r in releves_du_compteur(serveur.dossier, COMPTEUR_HORAIRE)]
            self.assertNotIn(dernier + 10, valeurs)
            page.click("dialog.dialogue button:has-text('Annuler')")
            self.attendre_fenetre_fermee()
            page.wait_for_load_state("networkidle")

    def test_releve_au_dessus_du_seuil_cree_un_ot_conditionnel_visible_dans_la_carte_preventif(self):
        with ServeurPrevo() as serveur:
            gamme = par_id(serveur.dossier, "gammes.csv")[GAMME_SEUIL]
            self.assertEqual(gamme["compteur_id"], COMPTEUR_SEUIL)
            seuil = nombre(gamme["seuil"])
            self.noter_les_toasts()
            page = self.ouvrir(serveur, gamme["equipement_id"])
            self.assertEqual(ots_ouverts_de(serveur.dossier, GAMME_SEUIL), [])
            ligne_gamme = ".parc-preventif li[data-gamme='%s']" % GAMME_SEUIL
            self.assertEqual(page.get_attribute(ligne_gamme, "data-statut"), "a_jour")

            valeur = round(seuil + 0.05, 2)
            self.ouvrir_fenetre_releve(COMPTEUR_SEUIL)
            page.fill("dialog.dialogue [name=valeur]", ("%.2f" % valeur).replace(".", ","))
            self.enregistrer_releve()
            self.attendre_fenetre_fermee()
            self.attendre_toast_note(r"^Relevé enregistré\. 1 OT préventif généré\.$")

            self.assertEqual(nombre(releves_du_compteur(serveur.dossier, COMPTEUR_SEUIL)[-1]["valeur"]), valeur)
            ouverts = ots_ouverts_de(serveur.dossier, GAMME_SEUIL)
            self.assertEqual(len(ouverts), 1, ouverts)
            ot = ouverts[0]
            self.assertEqual((ot["origine"], ot["type"], ot["statut"], ot["equipement_id"]),
                             ("préventif", "préventif conditionnel", "Créé", gamme["equipement_id"]))

            # La carte Préventif montre l'OT ouvert, avec un lien vers lui.
            lien = page.wait_for_selector("%s[data-statut='ot_ouvert'] a.parc-lien-ot[href='#/ot/%s']" % (ligne_gamme, ot["id"]))
            self.assertEqual(lien.inner_text().strip(), ot["id"])
            self.assertEqual(self.texte(ligne_gamme + " .badge"), "OT ouvert")
            page.wait_for_load_state("networkidle")


# ---------------------------------------------------------------------------
# gammes : carte Préventif, profils, téléphone
# ---------------------------------------------------------------------------

class TestGammes(CasParcLot2):

    def test_gammes_la_carte_liste_les_gammes_de_cp01_avec_leur_statut(self):
        with ServeurPrevo() as serveur:
            equipement = par_id(serveur.dossier, "gammes.csv")[GAMME_SEUIL]["equipement_id"]
            attendues = sorted(g["id"] for g in lire_csv(serveur.dossier, "gammes.csv") if g["equipement_id"] == equipement)
            self.assertGreaterEqual(len(attendues), 2)
            page = self.ouvrir(serveur, equipement)
            affichees = page.eval_on_selector_all(".parc-preventif li[data-gamme]", """els => els.map((e) => {
                const href = (selecteur) => { const a = e.querySelector(selecteur); return a ? a.getAttribute('href') : null; };
                return { id: e.dataset.gamme, statut: e.dataset.statut, badge: e.querySelector('.badge').textContent.trim(),
                         lien: href('a.parc-lien-gamme'), ot: href('a.parc-lien-ot') };
            })""")
            self.assertEqual(sorted(a["id"] for a in affichees), attendues)
            self.assertIn(str(len(attendues)), self.texte(".parc-preventif h2"))

            rangs = page.evaluate("Object.keys(Preventif.STATUTS_GAMME)")
            for gamme in affichees:
                with self.subTest(gamme=gamme["id"]):
                    etat = page.evaluate("id => Preventif.etatGamme(id)", gamme["id"])
                    self.assertEqual(gamme["statut"], etat["statut"])
                    self.assertEqual(gamme["badge"], page.evaluate("s => Preventif.STATUTS_GAMME[s]", etat["statut"]))
                    self.assertEqual(gamme["lien"], "#/preventif/gamme/" + gamme["id"])
                    self.assertEqual(gamme["ot"], "#/ot/" + etat["otOuvertId"] if etat["otOuvertId"] else None)
                    self.assertIn(espaces_simples(etat["raison"]), self.texte(".parc-preventif li[data-gamme='%s']" % gamme["id"]))
            # De la plus urgente à la moins urgente ; la gamme seuil (relevé sous le seuil) est à jour.
            positions = [rangs.index(g["statut"]) for g in affichees]
            self.assertEqual(positions, sorted(positions))
            self.assertEqual(next(g for g in affichees if g["id"] == GAMME_SEUIL)["badge"], "À jour")

            page.click(".parc-preventif a.parc-lien-gamme[href='#/preventif/gamme/%s']" % GAMME_SEUIL)
            page.wait_for_function("id => location.hash === '#/preventif/gamme/' + id", arg=GAMME_SEUIL)
            page.wait_for_selector("#pv-formulaire-gamme")
            page.wait_for_load_state("networkidle")

    def test_gammes_demandeur_sans_saisie_de_releve_ni_lien_vers_gammes_et_ot(self):
        with ServeurPrevo() as serveur:
            equipement = equipement_du_compteur(serveur.dossier, COMPTEUR_HORAIRE)
            nombre_gammes = sum(1 for g in lire_csv(serveur.dossier, "gammes.csv") if g["equipement_id"] == equipement)
            page = self.ouvrir(serveur, equipement, profil="demandeur", nom="Lucie Martin")
            self.assertEqual(page.locator(".parc-saisir-releve").count(), 0)
            self.assertEqual(page.get_by_role("button", name="Saisir un relevé").count(), 0)
            self.assertIn("Dernier relevé", self.texte(".parc-carte-compteurs"))
            self.assertEqual(page.locator(".parc-preventif li[data-gamme]").count(), nombre_gammes)
            self.assertEqual(page.locator(".parc-preventif a").count(), 0)

    def test_gammes_technicien_voit_le_bouton_saisir_un_releve_pour_chaque_compteur(self):
        with ServeurPrevo() as serveur:
            equipement = equipement_du_compteur(serveur.dossier, COMPTEUR_HORAIRE)
            compteurs = sorted(c["id"] for c in lire_csv(serveur.dossier, "compteurs.csv") if c["equipement_id"] == equipement)
            page = self.ouvrir(serveur, equipement, profil="technicien", technicien_id=TECHNICIEN)
            boutons = page.eval_on_selector_all(".parc-saisir-releve", "els => els.map((e) => e.dataset.compteur)")
            self.assertEqual(sorted(boutons), compteurs)
            self.assertGreater(page.locator(".parc-preventif a.parc-lien-gamme").count(), 0)

    def test_gammes_telephone_375_px_sans_defilement_horizontal_et_zones_de_48_px(self):
        with ServeurPrevo() as serveur:
            equipement = equipement_du_compteur(serveur.dossier, COMPTEUR_HORAIRE)
            page = self.ouvrir(serveur, equipement, largeur=375, hauteur=812)
            self.assertTrue(page.evaluate("UI.estTelephone()"))
            self.sans_defilement_horizontal("fiche")
            self.assertEqual(page.evaluate(PETITES_ZONES_JS), [])
            self.assertGreater(page.locator(".parc-preventif a.parc-lien-gamme").count(), 0)

            self.ouvrir_fenetre_releve(COMPTEUR_HORAIRE)
            self.sans_defilement_horizontal("fenêtre de relevé")
            largeur_fenetre = page.evaluate("document.querySelector('dialog.dialogue').getBoundingClientRect().width")
            self.assertLessEqual(largeur_fenetre, 375)
            for bouton in page.locator("dialog.dialogue .fenetre-actions button").all():
                self.assertGreaterEqual(bouton.bounding_box()["height"], 47.5)
            page.click("dialog.dialogue button:has-text('Annuler')")
            self.attendre_fenetre_fermee()


if __name__ == "__main__":
    unittest.main()
