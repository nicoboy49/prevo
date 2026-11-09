"""Accueil du responsable, 2.2, lot L6 (T485 ; CDC §3.4, CS173 de bout en bout ; D187 ; conception L4-L6 §4.1 ;
QUESTIONS-L2-L6 L4-L6 Q1, Q3, Q8 ; T463 : un contrat sans reconduction tacite n'est jamais « à décider »).

Tuile « Garanties et contrats » parmi les tuiles « à surveiller », sur le modèle de « Contrôles et habilitations » : trois
liens vers les listes filtrées de #/garanties (garanties qui se terminent dans le délai d'alerte ; contrats en alerte,
« à décider » ou « se termine bientôt » ; contrats aux dates à mettre à jour), le total dans la pastille, aucun montant ;
chiffres = Garanties.aEcheance, appelée par Accueil.calculerCompteurs (echeances).

Toujours la démo (index.html en file://, « Essayer avec les données de démo »), jamais de données réelles ; horloge du
navigateur FIGÉE (jamais la date réelle), fuseau Europe/Paris, mouvements réduits (chiffres finaux tout de suite).
Sauf la famille demo, les garanties et contrats de la démo sont d'abord retirés (Garanties.retirer…) et ceux du test
créés par l'application (Garanties.creerContrat, creerGarantie). Familles (le nom du test le dit) :
    cs173      contrat fini le 31/12/2026, préavis 3 mois, reconduction tacite : absent de l'accueil le 31/07/2026,
               compté le 01/08/2026 (« à résilier au plus tard le 30/09/2026 ») et jusqu'au 30/09, plus le 01/10
               (préavis dépassé) ; réglage alerte_echeances_jours à 30 : absent le 30/08, compté le 31/08 ; le lien
               mène à la liste filtrée, qui le montre ;
    tacite     sans reconduction tacite, jamais « à décider » : « se termine bientôt » 60 jours avant sa fin ; mêlé à
               un contrat à décider, le libellé dit les deux ;
    garanties  garanties qui se terminent sous le délai (première fin), contrat aux dates à mettre à jour ; liens vers
               les listes filtrées, mêmes nombres de lignes ;
    demo       date de référence de la démo : chiffres = Garanties.aEcheance et rôles de scénario ; « Contrôles et
               habilitations » intacte (trois liens, total) ; quatre tuiles « à surveiller », la nouvelle sur sa ligne ;
    profils    technicien : rien de nouveau (ni tuile ni lien vers Garanties et contrats) ;
    telephone  390 px : grille intacte (compteurs 2 × 2, tuiles l'une sous l'autre, liens empilés), aucun défilement
               horizontal ;
    langue     anglais : la tuile traduite.

Lancer depuis la racine du projet (au travers du verrou des navigateurs) :
    py -X utf8 -m unittest discover -s tests -p "test_accueil_v22.py" -v
"""
import json
import re
import unittest

from commun import CasNavigateur, attendre_pret, preregler_profil, scenarios_demo, url_fichier

REFERENCE = "2026-10-19"
LIEN_GARANTIES = "#/garanties?onglet=garanties&filtre=bientot"
LIEN_A_DECIDER = "#/garanties?onglet=contrats&filtre=a-decider"
LIEN_A_METTRE_A_JOUR = "#/garanties?onglet=contrats&filtre=a-mettre-a-jour"
LIENS_CONFORMITE = ["#/controles?filtre=30j", "#/equipe?filtre=a-renouveler", "#/controles?filtre=reserves-en-retard"]

# CS173 : fin de la période en cours 31/12/2026, préavis 3 mois, reconduction tacite (périodes de 12 mois)
CONTRAT_CS173 = {"objet": "Maintenance des compresseurs (CS173)", "date_debut": "2026-01-01", "date_fin": "2026-12-31",
                 "preavis_mois": "3", "reconduction_tacite": "1", "reconduction_mois": "12", "montant_annuel": "4800.50"}

# Retire les garanties et contrats de la démo, crée ceux du test (fournisseur et équipement suivi de la démo), réaffiche.
PREPARER_JS = """async ([contrats, garanties]) => {
  for (const g of Donnees.lignes('garanties')) if (String(g.actif) !== '0') await Garanties.retirerGarantie(g.id);
  for (const c of Donnees.lignes('contrats_prestataires')) if (String(c.actif) !== '0') await Garanties.retirerContrat(c.id);
  const fournisseur = Donnees.lignes('fournisseurs')[0];
  const equipement = Donnees.lignes('equipements').find((e) => String(e.actif) !== '0' && e.statut !== 'rebut');
  const ids = { contrats: [], garanties: [] };
  for (const v of contrats) ids.contrats.push(await Garanties.creerContrat(Object.assign({ fournisseur_id: fournisseur.id }, v)));
  for (const v of garanties) ids.garanties.push(await Garanties.creerGarantie(
    Object.assign({ equipement_id: equipement.id, fournisseur_id: fournisseur.id }, v)));
  await App.reafficher();
  return ids;
}"""

# La tuile lue à l'écran : titre, total, puis chaque lien { href, chiffre, libelle, detail, ton } ; null si absente.
TUILE_JS = """() => {
  const tuile = document.getElementById('bento-echeances');
  if (!tuile) return null;
  const espaces = (t) => t.replace(/\\s+/g, ' ').trim();
  const lien = (id) => { const a = document.getElementById(id); const detail = a.querySelector('.comp');
    return { href: a.getAttribute('href'), chiffre: Number(a.querySelector('.chiffre').textContent.trim()),
      libelle: espaces(a.querySelector('.bento-sous-texte > span').textContent), detail: espaces(detail.textContent),
      ton: ['rouge', 'ambre'].find((ton) => detail.classList.contains(ton)) || '' }; };
  return { titre: espaces(tuile.querySelector('h2').textContent), total: Number(tuile.querySelector('.bento-carre .chiffre').textContent.trim()),
    texte: espaces(tuile.textContent), liens: Array.from(tuile.querySelectorAll('a')).map((a) => a.getAttribute('href')),
    garanties: lien('bento-garanties-bientot'), contrats: lien('bento-contrats-a-decider'),
    miseAJour: lien('bento-contrats-a-mettre-a-jour') };
}"""

ECHEANCES_JS = """() => { const e = Accueil.calculerCompteurs().echeances;
  return { garanties: e.garanties.map((l) => l.id), contrats: e.contrats.map((l) => l.id), aMettreAJour: e.aMettreAJour.map((l) => l.id) }; }"""

DELAI_JS = """async (jours) => { await Donnees.modifier('parametres', (lignes) => {
  const ligne = lignes.find((l) => l.cle === 'alerte_echeances_jours');
  if (ligne) ligne.valeur = jours; else lignes.push({ cle: 'alerte_echeances_jours', valeur: jours });
}, { action: 'délai d\\'alerte (test T485)' }); await App.reafficher(); }"""

# Identifiants des lignes de la liste affichée de l'écran Garanties et contrats (onglet donné)
LISTE_JS = """(onglet) => Array.from(document.querySelectorAll(".garanties-liste[data-onglet='" + onglet + "'] a.garanties-lien"))
  .map((a) => decodeURIComponent(a.getAttribute('href').split('/').pop()))"""

BOITE_JS = """(selecteur) => Array.from(document.querySelectorAll(selecteur)).map((e) => {
  const r = e.getBoundingClientRect(); return { haut: Math.round(r.top), bas: Math.round(r.bottom), gauche: Math.round(r.left),
  largeur: Math.round(r.width) }; })"""


def heure(jour):
    return jour + "T09:00:00"


class CasAccueilV22(CasNavigateur):
    """Ouvre la démo dans un contexte réglé (taille, horloge figée, profil, langue)."""

    def ouvrir(self, jour, largeur=1440, hauteur=900, telephone=False, profil="responsable", technicien_id="",
               langue=None):
        options = dict(locale="fr-FR", timezone_id="Europe/Paris", reduced_motion="reduce",
                       viewport={"width": largeur, "height": hauteur})
        if telephone:
            options.update(is_mobile=True, has_touch=True, device_scale_factor=2)
        contexte = self.navigateur.new_context(**options)
        self.addCleanup(contexte.close)
        contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        contexte.clock.set_fixed_time(heure(jour))
        if langue:
            contexte.add_init_script("try { localStorage.setItem('prevo.langue', %s); } catch (e) { /* sans stockage */ }"
                                     % json.dumps(langue))
        preregler_profil(contexte, profil, "", technicien_id, poste="Poste atelier")
        page = contexte.new_page()
        self.surveiller(page)
        page.goto(url_fichier("index.html"))
        page.click("#btn-demo")
        attendre_pret(page)
        self.assertEqual(page.evaluate("Donnees.aujourdhui()"), jour)
        page.wait_for_selector("#bento" if profil == "responsable" else "#contenu .accueil-mes-ordres")
        return page

    def preparer(self, page, contrats=(), garanties=()):
        ids = page.evaluate(PREPARER_JS, [list(contrats), list(garanties)])
        page.wait_for_selector("#bento-echeances")
        return ids

    def aller_au(self, page, jour):
        """Horloge figée au jour donné, accueil réaffiché."""
        page.clock.set_fixed_time(heure(jour))
        self.assertEqual(page.evaluate("Donnees.aujourdhui()"), jour)
        page.evaluate("() => App.reafficher()")
        page.wait_for_selector("#bento-echeances")

    def tuile(self, page):
        tuile = page.evaluate(TUILE_JS)
        self.assertIsNotNone(tuile, "tuile « Garanties et contrats » absente")
        return tuile

    def contrats(self, page):
        """(chiffre, libellé, détail, ton) du lien des contrats en alerte, avec les identifiants comptés."""
        tuile = self.tuile(page)
        lien = tuile["contrats"]
        return (lien["chiffre"], lien["libelle"], lien["detail"], lien["ton"]), page.evaluate(ECHEANCES_JS)["contrats"]

    def ouvrir_lien(self, page, lien):
        page.click("#bento-echeances a[href='%s']" % lien)
        page.wait_for_function("() => !document.getElementById('bento')")
        page.wait_for_selector(".garanties-liste")
        self.assertEqual(page.evaluate("location.hash"), lien)

    def revenir(self, page):
        page.evaluate("location.hash = '#/accueil'")
        page.wait_for_selector("#bento-echeances")


# ---------------------------------------------------------------------------
# cs173
# ---------------------------------------------------------------------------

class TestCs173(CasAccueilV22):

    def test_cs173_contrat_absent_le_31_07_compte_le_01_08_puis_reglage_30_jours_compte_le_31_08(self):
        page = self.ouvrir("2026-07-31")
        identifiant = self.preparer(page, contrats=[CONTRAT_CS173])["contrats"][0]
        rien = (0, "contrat à décider", "rien à décider", "")
        compte = (1, "contrat à décider", "à résilier au plus tard le 30/09/2026", "rouge")
        # 31/07/2026 : 61 jours avant la date limite de résiliation (30/09) : rien à l'accueil
        self.assertEqual(self.contrats(page), (rien, []))
        self.assertEqual(self.tuile(page)["total"], 0)
        # 01/08/2026 : 60 jours avant (délai par défaut) : compté, la date limite dite, aucun montant
        self.aller_au(page, "2026-08-01")
        self.assertEqual(self.contrats(page), (compte, [identifiant]))
        tuile = self.tuile(page)
        self.assertEqual(tuile["total"], 1)
        self.assertEqual(tuile["titre"], "Garanties et contrats")
        self.assertEqual(tuile["contrats"]["href"], LIEN_A_DECIDER)
        self.assertNotRegex(tuile["texte"], r"4\s?800|€")
        # Jusqu'au 30/09 inclus ; le 01/10, préavis dépassé : plus rien à décider
        self.aller_au(page, "2026-09-30")
        self.assertEqual(self.contrats(page), (compte, [identifiant]))
        self.aller_au(page, "2026-10-01")
        self.assertEqual(self.contrats(page), (rien, []))
        # Réglage à 30 jours (D187) : le 30/08 rien, le 31/08 compté ; le libellé des garanties suit le réglage
        page.evaluate(DELAI_JS, "30")
        self.aller_au(page, "2026-08-30")
        self.assertEqual(self.contrats(page), (rien, []))
        self.assertEqual(self.tuile(page)["garanties"]["libelle"], "garantie finit sous 30 jours")
        self.aller_au(page, "2026-08-31")
        self.assertEqual(self.contrats(page), (compte, [identifiant]))
        # Le lien mène à la liste filtrée « à décider », qui montre le contrat
        self.ouvrir_lien(page, LIEN_A_DECIDER)
        self.assertEqual(page.evaluate(LISTE_JS, "contrats"), [identifiant])


# ---------------------------------------------------------------------------
# tacite
# ---------------------------------------------------------------------------

SANS_TACITE = {"objet": "Nettoyage des ateliers (sans reconduction)", "date_debut": "2026-01-01", "date_fin": "2026-12-31",
               "preavis_mois": "3", "reconduction_tacite": "0"}
TACITE_MARS = {"objet": "Vérification des extincteurs", "date_debut": "2026-04-01", "date_fin": "2027-03-31",
               "preavis_mois": "3", "reconduction_tacite": "1"}        # date limite de résiliation : 31/12/2026


class TestTacite(CasAccueilV22):

    def test_tacite_sans_reconduction_jamais_a_decider_se_termine_bientot_puis_meles(self):
        page = self.ouvrir("2026-08-01")
        ids = self.preparer(page, contrats=[SANS_TACITE, TACITE_MARS])["contrats"]
        sans, tacite = ids
        # 01/08/2026 : la date limite de résiliation du contrat sans reconduction (30/09) ne compte pas (T463)
        self.assertEqual(self.contrats(page), ((0, "contrat à décider", "rien à décider", ""), []))
        # 31/10 : 61 jours avant sa fin, 61 jours avant la date limite de l'autre : rien
        self.aller_au(page, "2026-10-31")
        self.assertEqual(self.contrats(page)[1], [])
        # 01/11 : 60 jours avant la fin du premier (se termine bientôt) et avant la date limite du second (à décider)
        self.aller_au(page, "2026-11-01")
        lien, comptes = self.contrats(page)
        self.assertEqual(sorted(comptes), sorted(ids))
        self.assertEqual(lien, (2, "contrats à décider ou qui se terminent bientôt",
                                "à résilier au plus tard le 31/12/2026", "rouge"))
        # Le contrat à reconduction tacite retiré : celui qui reste « se termine bientôt », jamais « à décider »
        page.evaluate("async (id) => { await Garanties.retirerContrat(id); await App.reafficher(); }", tacite)
        page.wait_for_selector("#bento-echeances")
        lien, comptes = self.contrats(page)
        self.assertEqual(comptes, [sans])
        self.assertEqual(lien, (1, "contrat se termine bientôt", "fin le 31/12/2026", "ambre"))
        self.assertNotIn("décider", self.tuile(page)["contrats"]["libelle"])
        self.ouvrir_lien(page, LIEN_A_DECIDER)
        self.assertEqual(page.evaluate(LISTE_JS, "contrats"), [sans])


# ---------------------------------------------------------------------------
# garanties
# ---------------------------------------------------------------------------

GARANTIES = [{"date_debut": "2025-08-20", "date_fin": "2026-09-15"},      # 45 jours après le 01/08 : comptée
             {"date_debut": "2024-08-20", "date_fin": "2026-08-20"},      # 19 jours : comptée, la première
             {"date_debut": "2025-01-01", "date_fin": "2026-12-31"}]      # 152 jours : en cours, pas comptée
A_METTRE_A_JOUR = {"objet": "Maintenance des portes sectionnelles", "date_debut": "2025-07-01", "date_fin": "2026-06-30",
                   "preavis_mois": "1", "reconduction_tacite": "1"}   # reconduit tacitement, durée inconnue


class TestGaranties(CasAccueilV22):

    def test_garanties_qui_finissent_et_contrat_aux_dates_a_mettre_a_jour_liens_vers_les_listes(self):
        page = self.ouvrir("2026-08-01")
        ids = self.preparer(page, contrats=[A_METTRE_A_JOUR], garanties=GARANTIES)
        tuile = self.tuile(page)
        echeances = page.evaluate(ECHEANCES_JS)
        self.assertEqual(echeances, {"garanties": [ids["garanties"][1], ids["garanties"][0]], "contrats": [],
                                     "aMettreAJour": ids["contrats"]})
        self.assertEqual(tuile["garanties"], {"href": LIEN_GARANTIES, "chiffre": 2, "libelle": "garanties finissent sous 60 jours",
                                              "detail": "première fin le 20/08/2026", "ton": "ambre"})
        self.assertEqual(tuile["miseAJour"], {"href": LIEN_A_METTRE_A_JOUR, "chiffre": 1,
                                              "libelle": "contrat aux dates à mettre à jour",
                                              "detail": "reconduit tacitement : saisissez la nouvelle période", "ton": "ambre"})
        self.assertEqual(tuile["contrats"]["chiffre"], 0)
        self.assertEqual(tuile["total"], 3)
        self.assertEqual(tuile["liens"], [LIEN_GARANTIES, LIEN_A_DECIDER, LIEN_A_METTRE_A_JOUR])
        # Chaque lien mène à la liste filtrée, qui a le même nombre de lignes
        self.ouvrir_lien(page, LIEN_GARANTIES)
        self.assertEqual(sorted(page.evaluate(LISTE_JS, "garanties")), sorted(ids["garanties"][:2]))
        self.revenir(page)
        self.ouvrir_lien(page, LIEN_A_METTRE_A_JOUR)
        self.assertEqual(page.evaluate(LISTE_JS, "contrats"), ids["contrats"])
        # Rien à l'échéance : détails neutres, les liens restent
        self.revenir(page)
        page.evaluate("""async () => { for (const g of Donnees.lignes('garanties')) if (String(g.actif) !== '0') await Garanties.retirerGarantie(g.id);
            for (const c of Donnees.lignes('contrats_prestataires')) if (String(c.actif) !== '0') await Garanties.retirerContrat(c.id);
            await App.reafficher(); }""")
        page.wait_for_selector("#bento-echeances")
        tuile = self.tuile(page)
        self.assertEqual([(tuile[n]["chiffre"], tuile[n]["detail"], tuile[n]["ton"]) for n in ("garanties", "contrats", "miseAJour")],
                         [(0, "aucune fin proche", ""), (0, "rien à décider", ""), (0, "rien à mettre à jour", "")])
        self.assertEqual(tuile["total"], 0)
        self.assertEqual(len(tuile["liens"]), 3)


# ---------------------------------------------------------------------------
# demo
# ---------------------------------------------------------------------------

class TestDemo(CasAccueilV22):

    def test_demo_chiffres_egaux_aux_echeances_conformite_intacte_et_tuile_sur_sa_ligne(self):
        scenarios = scenarios_demo()
        page = self.ouvrir(REFERENCE)
        echeances = page.evaluate(ECHEANCES_JS)
        self.assertIn(scenarios["garantie_bientot_finie"], echeances["garanties"])
        self.assertIn(scenarios["contrat_a_decider"], echeances["contrats"])
        self.assertIn(scenarios["contrat_a_mettre_a_jour"], echeances["aMettreAJour"])
        self.assertNotIn(scenarios["garantie_en_cours"], echeances["garanties"])
        tuile = self.tuile(page)
        self.assertEqual([tuile[n]["chiffre"] for n in ("garanties", "contrats", "miseAJour")],
                         [len(echeances[n]) for n in ("garanties", "contrats", "aMettreAJour")])
        self.assertEqual(tuile["total"], sum(len(v) for v in echeances.values()))
        self.assertNotIn("€", tuile["texte"])
        # « Contrôles et habilitations » intacte : trois liens, total = contrôles + habilitations + réserves
        conformite = page.evaluate("""() => { const c = Accueil.calculerCompteurs(); const t = document.querySelector('#bento .bento-conformite');
            return { liens: Array.from(t.querySelectorAll('a')).map((a) => a.getAttribute('href')),
              total: Number(t.querySelector('.bento-carre .chiffre').textContent.trim()),
              attendu: c.controlesSous30j.length + c.habilitationsARenouveler.length + c.reservesEnRetard.length }; }""")
        self.assertEqual(conformite["liens"], LIENS_CONFORMITE)
        self.assertEqual(conformite["total"], conformite["attendu"])
        # Quatre tuiles « à surveiller » ; les trois d'avant sur une ligne, « Garanties et contrats » dessous, toute
        # la largeur de la grille
        tuiles = page.evaluate(BOITE_JS, "#bento > .bento-surveiller")
        self.assertEqual(len(tuiles), 4)
        self.assertEqual(len({t["haut"] for t in tuiles[:3]}), 1)
        grille = page.evaluate(BOITE_JS, "#bento")[0]
        self.assertGreater(tuiles[3]["haut"], max(t["bas"] for t in tuiles[:3]))
        self.assertEqual((tuiles[3]["gauche"], tuiles[3]["largeur"]), (grille["gauche"], grille["largeur"]))
        self.assertEqual(page.evaluate("document.querySelector('#bento > .bento-surveiller:last-child').id"), "bento-echeances")


# ---------------------------------------------------------------------------
# profils
# ---------------------------------------------------------------------------

class TestProfils(CasAccueilV22):

    def test_profils_technicien_rien_de_nouveau(self):
        page = self.ouvrir(REFERENCE, profil="technicien", technicien_id="TEC-0002")
        self.assertEqual(page.locator("#bento-echeances").count(), 0)
        self.assertEqual(page.locator("#contenu a[href^='#/garanties']").count(), 0)
        self.assertEqual(page.locator("#contenu .accueil-instruments-technicien > a").evaluate_all(
            "l => l.map((a) => a.getAttribute('href'))"), LIENS_CONFORMITE)
        self.assertNotIn("Garanties", page.inner_text("#contenu"))


# ---------------------------------------------------------------------------
# telephone
# ---------------------------------------------------------------------------

class TestTelephone(CasAccueilV22):

    def test_telephone_grille_intacte_liens_empiles_sans_defilement_horizontal(self):
        page = self.ouvrir(REFERENCE, 390, 844, telephone=True)
        largeurs = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        self.assertLessEqual(largeurs[0], largeurs[1])
        # Compteurs en 2 × 2 (inchangés)
        compteurs = page.evaluate(BOITE_JS, "#bento .bento-compteur")
        self.assertEqual((len({c["haut"] for c in compteurs}), len({c["gauche"] for c in compteurs})), (2, 2))
        # Tuiles « à surveiller » l'une sous l'autre, même largeur, « Garanties et contrats » la dernière
        tuiles = page.evaluate(BOITE_JS, "#bento > .bento-surveiller")
        self.assertEqual(len(tuiles), 4)
        self.assertEqual([t["haut"] for t in tuiles], sorted(t["haut"] for t in tuiles))
        self.assertEqual(len({(t["gauche"], t["largeur"]) for t in tuiles}), 1)
        # Ses trois liens empilés, 48 px au moins (D31 : zones du téléphone)
        liens = page.evaluate(BOITE_JS, "#bento-echeances a.bento-sous-lien")
        self.assertEqual(len(liens), 3)
        self.assertEqual(len({l["gauche"] for l in liens}), 1)
        self.assertEqual([l["haut"] for l in liens], sorted(l["haut"] for l in liens))
        hauteurs = page.locator("#bento-echeances a.bento-sous-lien").evaluate_all(
            "l => l.map((a) => a.getBoundingClientRect().height)")
        self.assertTrue(all(h >= 47.5 for h in hauteurs), hauteurs)
        # Rien ne dépasse de la tuile
        debord = page.evaluate("() => { const t = document.getElementById('bento-echeances'); return [t.scrollWidth, t.clientWidth]; }")
        self.assertLessEqual(debord[0], debord[1])


# ---------------------------------------------------------------------------
# langue
# ---------------------------------------------------------------------------

class TestLangue(CasAccueilV22):

    def test_langue_anglais_tuile_traduite(self):
        page = self.ouvrir("2026-08-01", langue="en")
        self.assertEqual(page.evaluate("I18n.langue"), "en")
        self.preparer(page, contrats=[CONTRAT_CS173])
        tuile = self.tuile(page)
        self.assertEqual(tuile["titre"], "Warranties and contracts")
        self.assertEqual(tuile["contrats"]["libelle"], "contract with a decision due")
        # La date suit le format de la langue : on ne vérifie que la phrase qui l'entoure
        self.assertRegex(tuile["contrats"]["detail"], r"^terminate by \S*2026\S* at the latest$")
        self.assertEqual(tuile["garanties"]["libelle"], "warranties ending within 60 days")      # 0 : pluriel anglais
        self.assertNotRegex(tuile["texte"], re.compile("[àéè]|décider|garantie"))


if __name__ == "__main__":
    unittest.main()
