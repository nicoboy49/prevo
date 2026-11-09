"""Chantier multilingue, Lot 3 — valeurs des listes affichées dans la langue de l'écran (T283 ; D155, D156, D146).

Les valeurs stockées des listes du schéma (statuts, types, priorités, criticités…) restent écrites en français dans les
données ; seul leur affichage passe par Schema.libelleValeur (valeurs.<table>.<champ>.<valeur>), par UI.badgeValeur pour
les badges (couleur choisie sur la valeur brute). Les marqueurs du journal relus par l'historique d'un contrôle sont
traduits à l'affichage ; une action inconnue s'affiche telle quelle.

Dans Chromium, application de démonstration en file:// (profil responsable), langue d'essai « xx » déclarée dans la page
(I18n.declarer, I18n.ajouter, I18n.choisir) puis écran réaffiché (App.reafficher) :
    - fiche d'un OT « En cours » : badge de statut au libellé de la langue d'essai, couleur gardée (ton de la valeur
      brute), type d'OT traduit ; la donnée reste « En cours » ;
    - liste des OT : colonne Statut (badges) et colonne Type au libellé de la langue d'essai, ligne par ligne ;
    - historique d'un contrôle : marqueurs du journal (« modification : … — contrôle réalisé le … ») traduits, action
      inconnue telle quelle ; statut calculé du contrôle traduit (« réserves à lever (1) », nombre compris) ;
    - retour au français : texte de chaque écran identique à celui d'avant le changement de langue.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_valeurs_affichees.py" -v
"""
import unittest

from commun import CasNavigateur, attendre_pret, scenarios_demo, url_fichier

SCENARIOS = scenarios_demo()
OT_EN_COURS = SCENARIOS["ot_statut_en_cours"]       # correctif « En cours », P2
CONTROLE = SCENARIOS["controle_observations"]       # RA-01 : une réserve à lever (badge « réserves à lever (1) »)
CLES_STATUT_CONTROLE = {"en retard": "en_retard", "réserves à lever": "reserves_a_lever",
                        "à planifier": "a_planifier", "à jour": "a_jour"}

STATUTS_OT = ["Créé", "Préparé", "Planifié", "En cours", "En attente", "Clôturé techniquement",
              "Clôturé administrativement", "Annulé"]
TYPES_OT = ["correctif immédiat", "correctif différé", "préventif systématique", "préventif conditionnel",
            "amélioration", "réglementaire"]


def libelle_essai(valeur):
    """Libellé de la langue d'essai : visible et différent de toute valeur française."""
    return "xx[" + valeur + "]"


TEXTES_ESSAI = dict(
    [("valeurs.ordres_travail.statut." + v, libelle_essai(v)) for v in STATUTS_OT]
    + [("valeurs.ordres_travail.type." + v, libelle_essai(v)) for v in TYPES_OT]
    + [("socle.badge_priorite.priorite_code", "xx priorité {code}"),
       ("controles.journal.modification", "xx-modif : {champs}"),
       ("controles.journal.action_complement", "{action} // {complement}"),
       ("controles.journal.realise_le_par", "xx-réalisé {date} / {organisme}"),
       ("controles.journal.realisation", "{realise} | {rapport} | {observations}"),
       ("controles.journal.sans_rapport", "xx-sans-rapport"),
       ("controles.journal.sans_observation", "xx-sans-observation")]
    + [("controles.statut_calcule." + cle, "xx-" + cle) for cle in CLES_STATUT_CONTROLE.values()]
    + [("controles.statut_calcule.reserves_a_lever_n", "xx-reserves_a_lever_n ({n})")])     # 2.2 : nombre de réserves

# Langue d'essai déclarée et choisie dans la page ; l'écran courant est réaffiché.
CHOISIR_ESSAI_JS = """async (textes) => {
  I18n.declarer({ code: 'xx', nom: 'Essai', locale: 'en-GB', statut: 'automatique' });
  I18n.ajouter('xx', textes);
  const choisie = I18n.choisir('xx');
  await App.reafficher();
  return choisie;
}"""
CHOISIR_FRANCAIS_JS = "async () => { I18n.choisir('fr'); await App.reafficher(); return I18n.langue; }"

LIGNES_LISTE_OT_JS = """() => Array.from(document.querySelectorAll('.ot-liste-tableau tbody tr')).map((tr) => ({
  id: tr.querySelector('a').textContent, statut: tr.querySelector('.badge.statut').textContent,
  type: tr.cells[5].textContent.trim() }))"""

ACTION_REALISATION = ("modification : derniere_date, prochaine_date, observations_levees — contrôle réalisé le "
                      "12/03/2026 par Bureau Alpin ; sans rapport joint ; sans observation")
ACTION_INCONNUE = "action écrite par un autre outil"


class TestValeursAffichees(CasNavigateur):

    def setUp(self):
        super().setUp()
        page = self.page
        page.goto(url_fichier("index.html"))
        page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        page.click("#btn-demo")
        page.wait_for_function("document.documentElement.dataset.etat === 'profil'")
        page.click("#profil-responsable")
        attendre_pret(page)

    def aller(self, route, selecteur):
        self.page.evaluate("location.hash = %r" % route)
        self.page.wait_for_selector(selecteur)

    def choisir_essai(self):
        self.assertTrue(self.page.evaluate(CHOISIR_ESSAI_JS, TEXTES_ESSAI))
        self.assertEqual(self.page.evaluate("I18n.langue"), "xx")

    def revenir_au_francais(self):
        self.assertEqual(self.page.evaluate(CHOISIR_FRANCAIS_JS), "fr")

    def texte(self, selecteur):
        return self.page.inner_text(selecteur)

    def test_badge_de_statut_et_type_de_la_fiche_ot(self):
        self.aller("#/ot/" + OT_EN_COURS, ".ot-fiche .ot-badges .badge.statut")
        badge = ".ot-badges .badge.statut"
        type_ot = self.page.evaluate("Donnees.trouver('ordres_travail', %r).type" % OT_EN_COURS)
        self.assertEqual(self.texte(badge), "En cours")
        self.assertIn("cyan", self.page.get_attribute(badge, "class"))
        priorite = self.page.evaluate("Donnees.trouver('ordres_travail', %r).priorite" % OT_EN_COURS)
        entete_francais = self.texte(".ot-entete")
        self.assertIn(type_ot, entete_francais)

        self.choisir_essai()
        self.page.wait_for_function("document.querySelector(%r).textContent === %r" % (badge, libelle_essai("En cours")))
        self.assertIn("cyan", self.page.get_attribute(badge, "class"))          # ton choisi sur la valeur brute
        self.assertIn(libelle_essai(type_ot), self.texte(".ot-entete"))
        self.assertEqual(self.page.get_attribute(".ot-badges .badge[class*='prio-']", "title"), "xx priorité " + priorite)
        # Étapes de l'avancement : libellés de la langue d'essai.
        self.assertIn(libelle_essai("Planifié"), self.texte(".ot-etapes"))
        # La donnée ne change pas.
        self.assertEqual(self.page.evaluate("Donnees.trouver('ordres_travail', %r).statut" % OT_EN_COURS), "En cours")

        self.revenir_au_francais()
        self.page.wait_for_function("document.querySelector(%r).textContent === 'En cours'" % badge)
        self.assertEqual(self.texte(".ot-entete"), entete_francais)

    def test_colonnes_statut_et_type_de_la_liste_des_ot(self):
        self.aller("#/ot", ".ot-liste-tableau tbody tr .badge.statut")
        francais = self.page.evaluate(LIGNES_LISTE_OT_JS)
        self.assertGreater(len(francais), 3)
        donnees = {ligne["id"]: self.page.evaluate("(id) => { const ot = Donnees.trouver('ordres_travail', id); "
                                                   "return { statut: ot.statut, type: ot.type }; }", ligne["id"])
                   for ligne in francais}
        for ligne in francais:
            with self.subTest(ot=ligne["id"], langue="fr"):
                self.assertEqual((ligne["statut"], ligne["type"]), (donnees[ligne["id"]]["statut"], donnees[ligne["id"]]["type"]))
        tableau_francais = self.texte(".ot-liste-tableau")

        self.choisir_essai()
        self.page.wait_for_function("document.querySelector('.ot-liste-tableau tbody tr .badge.statut').textContent"
                                    ".startsWith('xx[')")
        essai = self.page.evaluate(LIGNES_LISTE_OT_JS)
        self.assertEqual([ligne["id"] for ligne in essai], [ligne["id"] for ligne in francais])
        for ligne in essai:
            with self.subTest(ot=ligne["id"], langue="xx"):
                attendu = donnees[ligne["id"]]
                self.assertEqual((ligne["statut"], ligne["type"]), (libelle_essai(attendu["statut"]), libelle_essai(attendu["type"])))
        # Le filtre des types propose les libellés ; les valeurs des options restent les valeurs stockées.
        options = self.page.evaluate("Array.from(document.querySelectorAll('#ot-filtre-type option')).slice(1)"
                                     ".map((o) => [o.value, o.textContent])")
        self.assertEqual(options, [[t, libelle_essai(t)] for t in TYPES_OT])

        self.revenir_au_francais()
        self.page.wait_for_function("!document.querySelector('.ot-liste-tableau tbody tr .badge.statut').textContent"
                                    ".startsWith('xx[')")
        self.assertEqual(self.texte(".ot-liste-tableau"), tableau_francais)

    def test_historique_d_un_controle_marqueurs_du_journal_traduits(self):
        for action in (ACTION_REALISATION, ACTION_INCONNUE):
            self.assertTrue(self.page.evaluate("(action) => Donnees.journaliser('controles_reglementaires', %r, action)"
                                               % CONTROLE, action))
        self.aller("#/controles/" + CONTROLE, ".controles-historique .controles-action")
        actions = ".controles-historique .controles-action"
        francais = self.page.eval_on_selector_all(actions, "(liste) => liste.map((e) => e.textContent)")
        self.assertEqual(sorted(francais), sorted([ACTION_REALISATION, ACTION_INCONNUE]))
        statut = ".controles-statuts .badge.statut"
        etat = self.page.evaluate("Controles.etat(Donnees.trouver('controles_reglementaires', %r))" % CONTROLE)
        self.assertEqual((etat["statut"], etat["reservesALever"]), ("réserves à lever", 1))     # rôle de la démo (T417)
        francais = "réserves à lever (1)"                     # libellé avec le nombre de réserves ouvertes (T412)
        self.assertEqual(self.texte(statut), francais)
        classe = self.page.get_attribute(statut, "class")
        page_francaise = self.texte(".controles-historique")

        self.choisir_essai()
        self.page.wait_for_function("document.querySelector(%r).textContent === %r"
                                    % (statut, "xx-reserves_a_lever_n (1)"))
        self.assertEqual(self.page.get_attribute(statut, "class"), classe)          # ton choisi sur le statut calculé
        essai = self.page.eval_on_selector_all(actions, "(liste) => liste.map((e) => e.textContent)")
        self.assertEqual(sorted(essai), sorted([
            "xx-modif : derniere_date, prochaine_date, observations_levees // xx-réalisé 12/03/2026 / Bureau Alpin"
            " | xx-sans-rapport | xx-sans-observation",
            ACTION_INCONNUE]))
        # Le journal garde le texte français écrit par Prévo (D156).
        self.assertIn(ACTION_REALISATION, self.page.evaluate("Donnees.lignes('journal').map((l) => l.action)"))

        self.revenir_au_francais()
        self.page.wait_for_function("document.querySelector(%r).textContent === %r" % (statut, francais))
        self.assertEqual(self.texte(".controles-historique"), page_francaise)


if __name__ == "__main__":
    unittest.main()
