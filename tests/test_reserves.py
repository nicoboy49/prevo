"""Tests des réserves des contrôles à l'écran, 2.2 (T418, T419 ; CS170, CS176, D18, D156, D183, D187 ;
CONCEPTION-L2-L3 §3.4) : fenêtre « Enregistrer le contrôle réalisé » (réserves relevées, échéance commune, aperçu, rappel
des réserves encore ouvertes), carte « Réserves » de la fiche (controles-reserves-ecrans.js), carte « Dernier
contrôle », historique (journal des réserves du contrôle) ; T419 : boutons du responsable (« Lever », « Modifier »,
« Ajouter une réserve »), fenêtres « Lever la réserve », « Modifier la réserve », « Ajouter une réserve », rappel de
l'OT lié clôturé et levée pré-remplie.

    serveur  : serveur.py sur une copie du jeu de démo, CSV relus sur le disque ; aucun identifiant de contrôle écrit
               en dur (contrôle créé par le test, ou rôles de scenarios_demo()) ;
               - responsable : trois lignes saisies à la réalisation → trois réserves (CSV) affichées sous
                 « Contrôle du … — 3 réserves », échéance « 30 jours après le contrôle » ; observations plus écrites ;
                 une nouvelle réalisation ajoute sa réserve et laisse les trois autres à l'octet (deux groupes, le plus
                 récent d'abord) ; l'historique montre la saisie (une entrée pour les trois) ; gravité, OT lié, levée
                 (repliée sous « Voir les réserves levées (1) », commentaire), réserve en retard ;
               - technicien : carte lue (réserve levée avec son OT, réserve à échéance saisie, réserve en retard à
                 l'échéance par défaut), aucun bouton ni champ ;
               - responsable (T419) : lever une réserve sur trois (date, commentaire, OT) laisse les deux autres
                 ouvertes, statut « réserves à lever (2) » ; refus (date future, avant le contrôle, sans commentaire)
                 sans rien écrire ; la levée n'a plus de bouton ; modifier (texte, gravité, échéance ; échéance avant
                 le contrôle refusée) ; ajouter deux réserves oubliées au dernier contrôle ; historique ;
    demo     : index.html en file:// ;
               - responsable : rappel « 1 réserve des contrôles précédents reste à lever », aperçu en direct, toast,
                 badge « réserves à lever (4) » ; carte vide « Aucune réserve relevée. » ;
               - responsable (T419) : OT lié clôturé, rappel « L'OT … est clôturé : levez la réserve… » et levée
                 pré-remplie (date de fin de l'OT, « Levée par l'OT … », OT lié) ;
               - technicien en anglais : réserve reprise levée sans date (D183) « cleared, date unknown », commentaire
                 de la reprise traduit ; aucun bouton ;
               - technicien (T419) : réserve ouverte reliée à un OT clôturé : ni rappel ni bouton.
Dates calculées depuis la date du jour de l'application (Donnees.aujourdhui()).

Lancer depuis la racine du projet (au travers du verrou des navigateurs) :
    py -X utf8 -m unittest discover -s tests -p "test_reserves.py" -v
"""
import csv
import datetime
import io
import json
import unittest
from pathlib import Path

from commun import RACINE, CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, scenarios_demo

SCENARIOS = scenarios_demo()
RESERVES_DEMO = SCENARIOS["controle_reserves"]          # AE-01 : une réserve levée avec son OT, une ouverte
RESERVE_EN_RETARD = SCENARIOS["controle_observations"]  # RA-01 : une réserve en retard (échéance par défaut)
SANS_RESERVE = SCENARIOS["controle_a_jour"]
TECHNICIEN = SCENARIOS["technicien_br_valide"]
SAISIE_TROIS = "- Différentiel 30 mA à remplacer\n\n• Schéma unifilaire à mettre à jour\n1. Prise de terre à reprendre  "
TEXTES_TROIS = ["Différentiel 30 mA à remplacer", "Schéma unifilaire à mettre à jour", "Prise de terre à reprendre"]

APPEL_JS = """async ([fonction, arguments_]) => {
  try { return 'accepté:' + JSON.stringify(await Controles[fonction](...arguments_)); }
  catch (erreur) { return (erreur instanceof Donnees.ErreurValidation ? 'refus:' : 'erreur:') + erreur.message; }
}"""

# Réserves affichées par la carte, dans l'ordre (textContent : les levées repliées comprises).
RESERVES_DE_LA_CARTE_JS = """() => Array.from(document.querySelectorAll('.controles-fiche .controles-reserves .controles-reserve'))
  .map((li) => ({ id: li.dataset.reserve, statut: li.dataset.statut,
    texte: li.querySelector('.controles-reserve-texte').textContent,
    badge: li.querySelector('.controles-reserve-meta .badge').textContent.trim(),
    meta: li.querySelector('.controles-reserve-meta').textContent.replace(/\\s+/g, ' ').trim(),
    commentaire: (li.querySelector('.controles-reserve-commentaire') || { textContent: '' }).textContent.trim(),
    repliee: Boolean(li.closest('details')),
    groupe: li.closest('.controles-reserves-groupe').querySelector('h3').textContent.trim() }))"""

# Ajoute à la démo (en mémoire) une réserve reprise levée de la 2.1 (D183) : levée, sans date, commentaire de la reprise.
RESERVE_REPRISE_JS = """async ([controleId, date]) => Donnees.modifier('reserves_controle', (lignes, outils) => {
  const id = outils.nouvelId(lignes);
  lignes.push({ id, controle_id: controleId, date_controle: date, texte: 'Extincteur du local à recharger',
    gravite: '', echeance_levee: '', levee: '1', date_levee: '', commentaire_levee: Formats.COMMENTAIRE_LEVEE_REPRISE,
    ot_id: '' });
  return id;
})"""

# Un OT clôturé de la démo (en mémoire), d'un équipement suivi, à date de fin connue et passée : le plus récent.
OT_CLOTURE_JS = """() => {
  const suivis = new Set(Donnees.lignes('equipements').filter((e) => String(e.actif) !== '0' && e.statut !== 'rebut')
    .map((e) => e.id));
  const jour = Donnees.aujourdhui();
  const ot = Donnees.lignes('ordres_travail')
    .filter((o) => ['Clôturé techniquement', 'Clôturé administrativement'].includes(o.statut) && suivis.has(o.equipement_id)
      && /^\\d{4}-\\d{2}-\\d{2}/.test(o.date_fin || '') && o.date_fin.slice(0, 10) <= jour)
    .sort((a, b) => b.date_fin.localeCompare(a.date_fin))[0];
  return { ot: ot.id, equipement: ot.equipement_id, fin: ot.date_fin.slice(0, 10) };
}"""

# Ajoute à la démo (en mémoire) une réserve OUVERTE reliée à un OT : [controleId, date, otId] → identifiant.
RESERVE_OUVERTE_AVEC_OT_JS = """async ([controleId, date, otId]) => Donnees.modifier('reserves_controle', (lignes, outils) => {
  const id = outils.nouvelId(lignes);
  lignes.push({ id, controle_id: controleId, date_controle: date, texte: 'Soupape de sûreté à tarer',
    gravite: '', echeance_levee: '', levee: '0', date_levee: '', commentaire_levee: '', ot_id: otId });
  return id;
})"""

# Erreur affichée sous un champ de la fenêtre ouverte.
ERREUR_DU_CHAMP_JS = """([champ, message]) => {
  const zone = document.querySelector('dialog [data-champ="' + champ + '"] .erreur-champ');
  return Boolean(zone) && !zone.hidden && zone.textContent.trim() === message;
}"""


def lire_csv(dossier, nom):
    texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte), delimiter=";"))


def brut(valeur):
    valeur = (valeur or "").strip()
    return valeur[1:] if valeur.startswith("'") else valeur


def propre(ligne):
    return {cle: brut(valeur) for cle, valeur in ligne.items()}


def reserves_de(dossier, controle_id):
    return [propre(r) for r in lire_csv(dossier, "reserves_controle.csv") if brut(r["controle_id"]) == controle_id]


def controle_de(dossier, controle_id):
    return next(propre(c) for c in lire_csv(dossier, "controles_reglementaires.csv") if c["id"] == controle_id)


def fr(date):
    return date.strftime("%d/%m/%Y")


def jour(valeur):
    return datetime.date.fromisoformat(valeur[:10])


class CasReserves(CasNavigateur):

    def appeler(self, fonction, *arguments):
        resultat = self.page.evaluate(APPEL_JS, [fonction, list(arguments)])
        self.assertTrue(resultat.startswith("accepté:"), resultat)
        return json.loads(resultat[len("accepté:"):])

    def aujourdhui(self):
        return datetime.date.fromisoformat(self.page.evaluate("Donnees.aujourdhui()"))

    def aller(self, route):
        self.page.evaluate("(route) => { location.hash = route; }", route)

    def attendre_fiche(self, controle_id):
        self.page.wait_for_selector(".controles-fiche .controles-reserves[data-controle='%s']" % controle_id)

    def attendre_titre(self, titre):
        self.page.wait_for_function(
            "(t) => { const h = document.querySelector('.controles-fiche .controles-reserves > .entete-carte h2'); "
            "return h && h.textContent.trim() === t; }", arg=titre)

    def attendre_toast(self, texte):
        self.page.wait_for_function("(t) => document.getElementById('toast').textContent.includes(t)", arg=texte)

    def carte(self):
        return self.page.evaluate(RESERVES_DE_LA_CARTE_JS)

    def groupes(self):
        return self.page.eval_on_selector_all(".controles-fiche .controles-reserves-groupe h3",
                                              "hs => hs.map((h) => h.textContent.trim())")

    def dernier_controle_reserves(self):
        return self.page.inner_text(".controles-fiche .controles-dernier .controles-dernier-reserves").strip()

    def actions_historique(self):
        return self.page.eval_on_selector_all(".controles-historique .controles-action",
                                              "l => l.map((e) => e.textContent.trim())")

    def ouvrir_realisation(self):
        self.page.click("#controle-realise")
        self.page.wait_for_selector("dialog [name=reserves]")

    def apercu(self):
        return self.page.text_content("dialog .controles-apercu-reserves").strip()

    def sans_bouton(self):
        for selecteur in (".controles-reserves button", ".controles-reserves a.btn", ".controles-reserves [name]",
                          ".controles-reserves [data-action]", ".controles-reserve-rappel",
                          "#controle-realise", "#controle-creer-ot", ".controles-fiche [name]"):
            self.assertEqual(self.page.locator(selecteur).count(), 0, selecteur)

    # --- T419 : boutons et fenêtres des réserves ---------------------------------------------------

    def badges(self, controle):
        return self.page.eval_on_selector_all(".controles-fiche .controles-statuts[data-controle='%s'] .badge" % controle,
                                              "l => l.map((b) => b.textContent.trim())")

    def boutons(self, reserve):
        return self.page.eval_on_selector_all(".controles-reserve[data-reserve='%s'] button" % reserve,
                                              "l => l.map((b) => b.dataset.action + ':' + b.textContent.trim())")

    def ouvrir_fenetre(self, reserve, action, champ):
        """Clic sur « Lever » / « Modifier » d'une réserve (reserve None : « Ajouter une réserve » de la carte)."""
        if reserve is None:
            self.page.click(".controles-reserves .entete-carte [data-action=ajouter]")
        else:
            self.page.click(".controles-reserve[data-reserve='%s'] [data-action=%s]" % (reserve, action))
        self.page.wait_for_selector("dialog [name=%s]" % champ)

    def valider(self):
        self.page.click("dialog .fenetre-actions .btn-primaire")

    def attendre_erreur(self, champ, message):
        self.page.wait_for_function(ERREUR_DU_CHAMP_JS, arg=[champ, message])

    def valeur(self, nom):
        return self.page.input_value("dialog [name=%s]" % nom)


# ---------------------------------------------------------------------------
# Serveur : CSV relus sur le disque
# ---------------------------------------------------------------------------

class TestServeur(CasReserves):

    def ouvrir(self, serveur, route, profil="responsable", technicien_id=""):
        preregler_profil(self.contexte, profil, technicien_id=technicien_id)
        self.page.goto(serveur.url + "/" + route)
        attendre_pret(self.page)
        self.page.wait_for_load_state("networkidle")

    def equipement_avec_ot(self, dossier):
        """(équipement suivi qui a au moins un OT, un de ses OT), lus dans le jeu copié."""
        equipements = {e["id"]: e for e in lire_csv(dossier, "equipements.csv")
                       if brut(e["actif"]) != "0" and e["statut"] != "rebut"}
        ot = next(propre(o) for o in lire_csv(dossier, "ordres_travail.csv") if brut(o["equipement_id"]) in equipements)
        return ot["equipement_id"], ot["id"]

    def test_trois_reserves_a_la_realisation_une_nouvelle_les_laisse_toutes_et_l_historique_montre_la_saisie(self):
        page = self.page
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            self.ouvrir(serveur, "#/controles")
            equipement, ot = self.equipement_avec_ot(dossier)
            controle = self.appeler("creerControle", {"equipement_id": equipement, "nature": "Installations électriques (T418)",
                                                      "periodicite_mois": "12"})
            aujourdhui = self.aujourdhui()
            d0, d1 = aujourdhui - datetime.timedelta(days=100), aujourdhui - datetime.timedelta(days=10)
            self.aller("#/controles/" + controle)
            self.attendre_fiche(controle)
            # Carte vide dite ; « Dernier contrôle » : aucune réserve
            self.assertEqual(page.inner_text(".controles-reserves > .entete-carte h2"), "Réserves")
            self.assertEqual(page.inner_text(".controles-reserves .controles-reserves-vide"), "Aucune réserve relevée.")
            self.assertEqual(self.dernier_controle_reserves(), "aucune")

            # Contrôle réalisé avec trois lignes, sans échéance : aperçu, pas de rappel (aucune réserve ouverte)
            self.ouvrir_realisation()
            self.assertEqual(page.locator("dialog .controles-reserves-precedentes").count(), 0)
            self.assertIn("Une ligne par réserve", page.inner_text("dialog [data-champ=reserves] .aide"))
            self.assertIn("Vide : 30 jours après le contrôle", page.inner_text("dialog [data-champ=echeance_levee] .aide"))
            page.fill("dialog [name=date]", d1.isoformat())
            page.fill("dialog [name=organisme]", "Organisme T418")
            page.fill("dialog [name=reserves]", SAISIE_TROIS)
            self.assertEqual(self.apercu(), "3 réserves seront enregistrées.")
            page.click("dialog .fenetre-actions .btn-primaire")
            self.attendre_toast("Contrôle réalisé enregistré, 3 réserves relevées.")
            self.attendre_titre("Réserves (3, dont 3 à lever)")
            reserves = reserves_de(dossier, controle)
            self.assertEqual([r["texte"] for r in reserves], TEXTES_TROIS)
            self.assertTrue(all((r["date_controle"], r["echeance_levee"], r["levee"]) == (d1.isoformat(), "", "0")
                                for r in reserves), reserves)
            ligne = controle_de(dossier, controle)
            self.assertEqual((ligne["derniere_date"], ligne["observations"], ligne["observations_levees"]),
                             (d1.isoformat(), "", "1"))                      # colonnes anciennes plus écrites
            # Trois réserves affichées sous « Contrôle du … — 3 réserves », échéance calculée dite
            echeance = fr(d1 + datetime.timedelta(days=30))
            self.assertEqual(self.groupes(), ["Contrôle du %s — 3 réserves" % fr(d1)])
            carte = self.carte()
            self.assertEqual([r["texte"] for r in carte], TEXTES_TROIS)
            self.assertEqual([r["id"] for r in carte], [r["id"] for r in reserves])
            for reserve in carte:
                self.assertEqual((reserve["statut"], reserve["badge"], reserve["repliee"]), ("à lever", "à lever", False))
                self.assertIn("échéance le %s (30 jours après le contrôle)" % echeance, reserve["meta"])
            self.assertEqual(self.dernier_controle_reserves(), "3")
            # L'historique montre la saisie : une entrée pour les trois réserves, et la réalisation
            actions = self.actions_historique()
            self.assertEqual(actions.count("Réserves relevées au contrôle du %s : 3" % fr(d1)), 1, actions)
            self.assertTrue(any(a.endswith("contrôle réalisé le %s par Organisme T418 ; sans rapport joint ; 3 réserves"
                                           % fr(d1)) for a in actions), actions)

            # Nouvelle réalisation : rappel des trois ouvertes ; une réserve ajoutée, à échéance saisie ; les trois
            # autres restent telles quelles (CS170)
            avant = reserves_de(dossier, controle)
            self.ouvrir_realisation()
            self.assertEqual(page.inner_text("dialog .controles-reserves-precedentes"),
                             "3 réserves des contrôles précédents restent à lever.")
            self.assertEqual(self.apercu(), "")
            page.fill("dialog [name=reserves]", "Éclairage de secours absent")
            self.assertEqual(self.apercu(), "1 réserve sera enregistrée.")
            echeance_saisie = aujourdhui + datetime.timedelta(days=15)
            page.fill("dialog [name=echeance_levee]", echeance_saisie.isoformat())
            page.click("dialog .fenetre-actions .btn-primaire")
            self.attendre_toast("Contrôle réalisé enregistré, 1 réserve relevée.")
            self.attendre_titre("Réserves (4, dont 4 à lever)")
            apres = reserves_de(dossier, controle)
            self.assertEqual(apres[:3], avant)
            self.assertEqual((apres[3]["texte"], apres[3]["date_controle"], apres[3]["echeance_levee"]),
                             ("Éclairage de secours absent", aujourdhui.isoformat(), echeance_saisie.isoformat()))
            self.assertEqual(self.groupes(), ["Contrôle du %s — 1 réserve" % fr(aujourdhui),
                                              "Contrôle du %s — 3 réserves" % fr(d1)])
            nouvelle = self.carte()[0]
            self.assertEqual(nouvelle["texte"], "Éclairage de secours absent")
            self.assertIn("échéance le %s" % fr(echeance_saisie), nouvelle["meta"])
            self.assertNotIn("jours après le contrôle", nouvelle["meta"])
            self.assertEqual(self.dernier_controle_reserves(), "1")

            # Gravité, OT lié, levée (repliée), réserve en retard (échéance par défaut passée)
            premiere, deuxieme = apres[0]["id"], apres[1]["id"]
            self.appeler("modifierReserve", premiere, {"gravite": "majeure"})
            self.appeler("lierOtAReserve", premiere, ot)
            levee_le = d1 + datetime.timedelta(days=5)
            self.appeler("leverReserve", deuxieme, {"date": levee_le.isoformat(), "commentaire": "Schéma mis à jour"})
            self.appeler("ajouterReserves", controle, {"date_controle": d0.isoformat(), "texte": "Garde-corps à refixer"})
            page.evaluate("App.reafficher()")                 # écritures de ce poste par l'API : l'écran est redessiné
            self.attendre_titre("Réserves (5, dont 4 à lever)")
            self.assertEqual(self.groupes(), ["Contrôle du %s — 1 réserve" % fr(aujourdhui),
                                              "Contrôle du %s — 3 réserves" % fr(d1),
                                              "Contrôle du %s — 1 réserve" % fr(d0)])
            carte = {r["id"]: r for r in self.carte()}
            self.assertIn("gravité : majeure", carte[premiere]["meta"])
            self.assertIn("OT lié : %s" % ot, carte[premiere]["meta"])
            self.assertEqual(page.locator(".controles-reserve[data-reserve='%s'] .controles-reserve-meta a[href='#/ot/%s']" % (premiere, ot)).count(), 1)
            self.assertEqual((carte[deuxieme]["statut"], carte[deuxieme]["badge"], carte[deuxieme]["repliee"]),
                             ("levée", "levée le %s" % fr(levee_le), True))
            self.assertEqual(carte[deuxieme]["commentaire"], "Ce qui a été fait : Schéma mis à jour")
            self.assertNotIn("échéance", carte[deuxieme]["meta"])
            self.assertEqual(page.inner_text(".controles-reserves-levees summary"), "Voir les réserves levées (1)")
            self.assertFalse(page.is_visible(".controles-reserve[data-reserve='%s']" % deuxieme))     # repliée
            en_retard = next(r for r in carte.values() if r["texte"] == "Garde-corps à refixer")
            self.assertEqual((en_retard["statut"], en_retard["badge"]), ("en retard", "en retard"))
            self.assertIn("échéance le %s (30 jours après le contrôle)" % fr(d0 + datetime.timedelta(days=30)), en_retard["meta"])
            actions = self.actions_historique()
            self.assertIn("Réserve levée le %s : Schéma mis à jour" % fr(levee_le), actions)
            self.assertIn("Reliée à %s" % ot, actions)
            self.assertIn("Correction de la réserve", actions)
            self.assertIn(TEXTES_TROIS[1], page.inner_text(".controles-historique"))   # la réserve concernée

    def test_technicien_lit_la_carte_sans_aucun_bouton(self):
        page = self.page
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            self.ouvrir(serveur, "#/controles/" + RESERVES_DEMO, profil="technicien", technicien_id=TECHNICIEN)
            self.attendre_fiche(RESERVES_DEMO)
            self.assertEqual(page.evaluate("App.profil.type"), "technicien")
            aujourdhui = self.aujourdhui()
            reserves = reserves_de(dossier, RESERVES_DEMO)
            levee = next(r for r in reserves if r["levee"] == "1")
            ouverte = next(r for r in reserves if r["levee"] != "1")
            self.assertTrue(levee["ot_id"] and ouverte["echeance_levee"], reserves)        # rôle de la démo (T417)
            self.assertEqual(page.inner_text(".controles-reserves > .entete-carte h2"), "Réserves (2, dont 1 à lever)")
            carte = {r["id"]: r for r in self.carte()}
            statut = "en retard" if jour(ouverte["echeance_levee"]) < aujourdhui else "à lever"
            self.assertEqual((carte[ouverte["id"]]["statut"], carte[ouverte["id"]]["repliee"]), (statut, False))
            self.assertIn("échéance le %s" % fr(jour(ouverte["echeance_levee"])), carte[ouverte["id"]]["meta"])
            self.assertNotIn("jours après le contrôle", carte[ouverte["id"]]["meta"])
            self.assertEqual((carte[levee["id"]]["badge"], carte[levee["id"]]["repliee"]),
                             ("levée le %s" % fr(jour(levee["date_levee"])), True))
            self.assertEqual(carte[levee["id"]]["commentaire"], "Ce qui a été fait : " + levee["commentaire_levee"])
            self.assertIn("OT lié : %s" % levee["ot_id"], carte[levee["id"]]["meta"])
            self.assertEqual(page.locator(".controles-reserves a[href='#/ot/%s']" % levee["ot_id"]).count(), 1)
            # La carte se lit : les levées se déplient, rien ne s'écrit
            page.click(".controles-reserves-levees summary")
            self.assertTrue(page.is_visible(".controles-reserve[data-reserve='%s']" % levee["id"]))
            self.sans_bouton()

            # RA-01 : réserve en retard à l'échéance par défaut (30 jours après le contrôle, D187)
            self.aller("#/controles/" + RESERVE_EN_RETARD)
            self.attendre_fiche(RESERVE_EN_RETARD)
            reserve = reserves_de(dossier, RESERVE_EN_RETARD)[0]
            carte = self.carte()
            self.assertEqual([(r["id"], r["statut"], r["badge"]) for r in carte], [(reserve["id"], "en retard", "en retard")])
            self.assertIn("échéance le %s (30 jours après le contrôle)" % fr(jour(reserve["date_controle"]) + datetime.timedelta(days=30)),
                          carte[0]["meta"])
            self.assertEqual(self.groupes(), ["Contrôle du %s — 1 réserve" % fr(jour(reserve["date_controle"]))])
            self.sans_bouton()

    def test_lever_une_reserve_sur_trois_refus_sans_ecriture_puis_modifier_et_ajouter(self):
        page = self.page
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            fichier = Path(dossier) / "reserves_controle.csv"
            self.ouvrir(serveur, "#/controles")
            equipement, ot = self.equipement_avec_ot(dossier)
            controle = self.appeler("creerControle", {"equipement_id": equipement, "nature": "Installations électriques (T419)",
                                                      "periodicite_mois": "12"})
            aujourdhui = self.aujourdhui()
            d1 = aujourdhui - datetime.timedelta(days=10)
            self.appeler("enregistrerRealisation", controle, {"date": d1.isoformat(), "organisme": "Organisme T419",
                                                              "reserves": SAISIE_TROIS})
            self.aller("#/controles/" + controle)
            self.attendre_fiche(controle)
            self.attendre_titre("Réserves (3, dont 3 à lever)")
            self.assertIn("réserves à lever (3)", self.badges(controle))
            reserves = reserves_de(dossier, controle)
            premiere, deuxieme, troisieme = [r["id"] for r in reserves]
            for reserve in (premiere, deuxieme, troisieme):
                self.assertEqual(self.boutons(reserve), ["lever:Lever", "modifier:Modifier"])
            self.assertEqual(page.inner_text(".controles-reserves .entete-carte [data-action=ajouter]"), "Ajouter une réserve")
            self.assertEqual(page.locator(".controles-reserve-rappel").count(), 0)          # aucun OT lié

            # « Lever la réserve » : rappel du texte et de la date du contrôle, levée le (défaut aujourd'hui), OT de
            # l'équipement proposés (aucun par défaut)
            self.ouvrir_fenetre(deuxieme, "lever", "commentaire")
            self.assertEqual(page.inner_text("dialog h2"), "Lever la réserve")
            rappel = page.inner_text("dialog .controles-rappel-reserve")
            self.assertIn("Relevée au contrôle du %s" % fr(d1), rappel)
            self.assertIn(TEXTES_TROIS[1], rappel)
            self.assertEqual((self.valeur("date"), self.valeur("commentaire"), self.valeur("ot_id")), (aujourdhui.isoformat(), "", ""))
            options = page.eval_on_selector_all("dialog [name=ot_id] option", "l => l.map((o) => o.value)")
            self.assertIn(ot, options)
            self.assertEqual(options[0], "")
            self.assertEqual(page.inner_text("dialog .fenetre-actions .btn-primaire"), "Lever la réserve")

            # Refus, sans rien écrire : date future, date avant le contrôle, sans commentaire
            avant = fichier.read_bytes()
            page.fill("dialog [name=date]", (aujourdhui + datetime.timedelta(days=1)).isoformat())
            page.fill("dialog [name=commentaire]", "Schéma mis à jour et affiché")
            self.valider()
            self.attendre_erreur("date", "La date de levée ne peut pas être dans le futur.")
            page.fill("dialog [name=date]", (d1 - datetime.timedelta(days=1)).isoformat())
            self.valider()
            self.attendre_erreur("date", "La réserve date du contrôle du %s : une levée antérieure est refusée." % fr(d1))
            levee_le = d1 + datetime.timedelta(days=2)
            page.fill("dialog [name=date]", levee_le.isoformat())
            page.fill("dialog [name=commentaire]", "")
            self.valider()
            self.attendre_erreur("commentaire", "Ce champ est obligatoire.")
            self.assertEqual(fichier.read_bytes(), avant)
            self.assertTrue(page.is_visible("dialog [name=commentaire]"))                  # la fenêtre reste ouverte

            # Levée acceptée (date, commentaire, OT) : les deux autres restent ouvertes, statut « réserves à lever (2) »
            page.fill("dialog [name=commentaire]", "Schéma mis à jour et affiché")
            page.select_option("dialog [name=ot_id]", ot)
            self.valider()
            self.attendre_toast("Réserve levée.")
            self.attendre_titre("Réserves (3, dont 2 à lever)")
            self.assertIn("réserves à lever (2)", self.badges(controle))
            apres = reserves_de(dossier, controle)
            self.assertEqual((apres[1]["levee"], apres[1]["date_levee"], apres[1]["commentaire_levee"], apres[1]["ot_id"]),
                             ("1", levee_le.isoformat(), "Schéma mis à jour et affiché", ot))
            self.assertEqual((apres[0], apres[2]), (reserves[0], reserves[2]))               # à l'octet près
            self.assertEqual([r["levee"] for r in apres], ["0", "1", "0"])
            carte = {r["id"]: r for r in self.carte()}
            self.assertEqual((carte[deuxieme]["statut"], carte[deuxieme]["repliee"]), ("levée", True))
            self.assertEqual(self.boutons(deuxieme), [])                                    # une levée est un fait
            self.assertEqual(self.boutons(premiere), ["lever:Lever", "modifier:Modifier"])

            # « Modifier la réserve » : texte, gravité, échéance ; échéance avant le contrôle refusée sans écrire
            self.ouvrir_fenetre(premiere, "modifier", "texte")
            self.assertEqual(page.inner_text("dialog h2"), "Modifier la réserve")
            self.assertEqual((self.valeur("texte"), self.valeur("gravite"), self.valeur("echeance_levee")), (TEXTES_TROIS[0], "", ""))
            self.assertIn("Vide : 30 jours après le contrôle.", page.inner_text("dialog [data-champ=echeance_levee] .aide"))
            avant = fichier.read_bytes()
            page.fill("dialog [name=texte]", "Différentiel 30 mA du TGBT à remplacer")
            page.select_option("dialog [name=gravite]", "majeure")
            page.fill("dialog [name=echeance_levee]", (d1 - datetime.timedelta(days=1)).isoformat())
            self.valider()
            self.attendre_erreur("echeance_levee", "L'échéance de levée ne peut pas précéder le contrôle du %s." % fr(d1))
            self.assertEqual(fichier.read_bytes(), avant)
            echeance = aujourdhui + datetime.timedelta(days=20)
            page.fill("dialog [name=echeance_levee]", echeance.isoformat())
            self.valider()
            self.attendre_toast("Réserve modifiée.")
            self.page.wait_for_function("(id) => document.querySelector(\".controles-reserve[data-reserve='\" + id + \"'] .controles-reserve-gravite\")",
                                        arg=premiere)
            modifiee = reserves_de(dossier, controle)[0]
            self.assertEqual((modifiee["texte"], modifiee["gravite"], modifiee["echeance_levee"], modifiee["levee"]),
                             ("Différentiel 30 mA du TGBT à remplacer", "majeure", echeance.isoformat(), "0"))
            carte = {r["id"]: r for r in self.carte()}
            self.assertIn("gravité : majeure", carte[premiere]["meta"])
            self.assertIn("échéance le %s" % fr(echeance), carte[premiere]["meta"])
            self.assertNotIn("jours après le contrôle", carte[premiere]["meta"])

            # « Ajouter une réserve » : date du dernier contrôle par défaut, une ligne par réserve
            self.ouvrir_fenetre(None, None, "texte")
            self.assertEqual(page.inner_text("dialog h2"), "Ajouter une réserve")
            self.assertEqual(self.valeur("date_controle"), d1.isoformat())
            page.fill("dialog [name=texte]", "Éclairage de secours absent\n- Porte coupe-feu à régler")
            self.valider()
            self.attendre_toast("2 réserves ajoutées.")
            self.attendre_titre("Réserves (5, dont 4 à lever)")
            toutes = reserves_de(dossier, controle)
            self.assertEqual([(r["texte"], r["date_controle"], r["levee"]) for r in toutes[3:]],
                             [("Éclairage de secours absent", d1.isoformat(), "0"), ("Porte coupe-feu à régler", d1.isoformat(), "0")])
            self.assertEqual(toutes[1:3], apres[1:3])                                        # les autres ne changent pas
            self.assertEqual(self.groupes(), ["Contrôle du %s — 5 réserves" % fr(d1)])
            self.assertIn("réserves à lever (4)", self.badges(controle))
            actions = self.actions_historique()
            self.assertIn("Réserve levée le %s : Schéma mis à jour et affiché" % fr(levee_le), actions)
            self.assertIn("Correction de la réserve", actions)
            self.assertIn("Réserves relevées au contrôle du %s : 2" % fr(d1), actions)


# ---------------------------------------------------------------------------
# Démo (file://)
# ---------------------------------------------------------------------------

class TestDemo(CasReserves):

    def ouvrir_demo(self, profil, technicien_id=""):
        preregler_profil(self.contexte, profil, technicien_id=technicien_id)
        self.page.goto((RACINE / "index.html").resolve().as_uri())
        self.page.click("#btn-demo")
        attendre_pret(self.page)

    def test_responsable_rappel_apercu_en_direct_et_carte_vide(self):
        page = self.page
        self.ouvrir_demo("responsable")
        aujourdhui = self.aujourdhui()
        self.aller("#/controles/" + RESERVE_EN_RETARD)
        self.attendre_fiche(RESERVE_EN_RETARD)
        self.assertEqual(page.inner_text(".controles-reserves > .entete-carte h2"), "Réserves (1, dont 1 à lever)")
        ancienne = self.carte()
        self.assertEqual([r["statut"] for r in ancienne], ["en retard"])
        self.assertEqual(self.dernier_controle_reserves(), "1")

        self.ouvrir_realisation()
        self.assertEqual(page.inner_text("dialog .controles-reserves-precedentes"),
                         "1 réserve des contrôles précédents reste à lever.")
        self.assertEqual(self.apercu(), "")
        page.fill("dialog [name=reserves]", "Soupape à tarer")
        self.assertEqual(self.apercu(), "1 réserve sera enregistrée.")
        page.fill("dialog [name=reserves]", SAISIE_TROIS)
        self.assertEqual(self.apercu(), "3 réserves seront enregistrées.")
        page.fill("dialog [name=reserves]", " - \n\n")
        self.assertEqual(self.apercu(), "")
        page.fill("dialog [name=reserves]", SAISIE_TROIS)
        page.click("dialog .fenetre-actions .btn-primaire")
        self.attendre_toast("Contrôle réalisé enregistré, 3 réserves relevées.")
        self.attendre_titre("Réserves (4, dont 4 à lever)")
        groupes = self.groupes()
        self.assertEqual(groupes[0], "Contrôle du %s — 3 réserves" % fr(aujourdhui))
        self.assertEqual(len(groupes), 2)
        carte = self.carte()
        self.assertEqual([r["texte"] for r in carte[:3]], TEXTES_TROIS)
        self.assertEqual((carte[3]["id"], carte[3]["statut"]), (ancienne[0]["id"], "en retard"))     # gardée telle quelle
        badges = page.eval_on_selector_all(".controles-fiche .controles-statuts[data-controle='%s'] .badge" % RESERVE_EN_RETARD,
                                           "l => l.map((b) => b.textContent.trim())")
        self.assertIn("réserves à lever (4)", badges)
        self.assertEqual(self.actions_historique().count("Réserves relevées au contrôle du %s : 3" % fr(aujourdhui)), 1)

        # Contrôle sans réserve : carte vide dite
        self.aller("#/controles/" + SANS_RESERVE)
        self.attendre_fiche(SANS_RESERVE)
        self.assertEqual(page.inner_text(".controles-reserves > .entete-carte h2"), "Réserves")
        self.assertEqual(page.inner_text(".controles-reserves .controles-reserves-vide"), "Aucune réserve relevée.")
        self.assertEqual(self.dernier_controle_reserves(), "aucune")

    def test_technicien_en_anglais_reserve_reprise_levee_sans_date(self):
        page = self.page
        self.contexte.add_init_script("try { localStorage.setItem('prevo.langue', 'en'); } catch (erreur) {}")
        self.ouvrir_demo("technicien", TECHNICIEN)
        self.assertEqual((page.evaluate("I18n.langue"), page.evaluate("App.profil.type")), ("en", "technicien"))
        date = page.evaluate("(id) => Donnees.trouver('controles_reglementaires', id).derniere_date", SANS_RESERVE)
        page.evaluate(RESERVE_REPRISE_JS, [SANS_RESERVE, date])
        self.aller("#/controles/" + SANS_RESERVE)
        self.attendre_fiche(SANS_RESERVE)
        self.attendre_titre("Findings (1, cleared)")
        self.assertEqual(self.groupes(), ["Inspection of %s — 1 finding" % fr(jour(date))])
        reserve = self.carte()[0]
        self.assertEqual((reserve["statut"], reserve["badge"], reserve["repliee"]), ("levée", "cleared, date unknown", True))
        self.assertEqual(reserve["commentaire"], "What was done: cleared before 2.2, date unknown")
        self.assertEqual(page.inner_text(".controles-reserves-levees summary"), "Show cleared findings (1)")
        self.assertEqual(page.inner_text(".controles-fiche .controles-dernier dt:nth-of-type(4)"), "Findings recorded")
        self.assertEqual(self.dernier_controle_reserves(), "1")
        # La donnée reste en français (D156)
        self.assertEqual(page.evaluate("Donnees.lignes('reserves_controle').filter((r) => r.controle_id === %r)[0].commentaire_levee"
                                       % SANS_RESERVE), "levée avant la 2.2, date inconnue")
        self.sans_bouton()

    def test_ot_lie_cloture_rappel_et_levee_pre_remplie(self):
        page = self.page
        self.ouvrir_demo("responsable")
        cloture = page.evaluate(OT_CLOTURE_JS)
        fin = jour(cloture["fin"])
        date_controle = fin - datetime.timedelta(days=5)
        controle = self.appeler("creerControle", {"equipement_id": cloture["equipement"], "nature": "Appareil à pression (T419)",
                                                  "periodicite_mois": "12"})
        self.appeler("enregistrerRealisation", controle, {"date": date_controle.isoformat(), "reserves": "Soupape à tarer"})
        reserve = page.evaluate("(id) => Controles.reservesOuvertes(id)[0].id", controle)
        self.appeler("lierOtAReserve", reserve, cloture["ot"])
        self.aller("#/controles/" + controle)
        self.attendre_fiche(controle)
        self.assertEqual(page.inner_text(".controles-reserve[data-reserve='%s'] .controles-reserve-rappel" % reserve).strip(),
                         "L'OT %s est clôturé : levez la réserve si le travail l'a corrigée." % cloture["ot"])

        # « Lever » pré-rempli : date de fin de l'OT, « Levée par l'OT … », OT lié
        self.ouvrir_fenetre(reserve, "lever", "commentaire")
        self.assertEqual((self.valeur("date"), self.valeur("commentaire"), self.valeur("ot_id")),
                         (fin.isoformat(), "Levée par l'OT %s" % cloture["ot"], cloture["ot"]))
        self.valider()
        self.attendre_toast("Réserve levée.")
        self.attendre_titre("Réserves (1, levée)")
        ligne = page.evaluate("(id) => Donnees.trouver('reserves_controle', id)", reserve)
        self.assertEqual((ligne["levee"], ligne["date_levee"], ligne["commentaire_levee"], ligne["ot_id"]),
                         ("1", fin.isoformat(), "Levée par l'OT %s" % cloture["ot"], cloture["ot"]))
        self.assertEqual(page.locator(".controles-reserve-rappel").count(), 0)
        self.assertEqual(self.boutons(reserve), [])

    def test_technicien_ni_rappel_ni_bouton_avec_un_ot_lie_cloture(self):
        page = self.page
        self.ouvrir_demo("technicien", TECHNICIEN)
        self.assertEqual(page.evaluate("App.profil.type"), "technicien")
        cloture = page.evaluate(OT_CLOTURE_JS)
        date = page.evaluate("(id) => Donnees.trouver('controles_reglementaires', id).derniere_date", SANS_RESERVE)
        reserve = page.evaluate(RESERVE_OUVERTE_AVEC_OT_JS, [SANS_RESERVE, date, cloture["ot"]])
        self.aller("#/controles/" + SANS_RESERVE)
        self.attendre_fiche(SANS_RESERVE)
        self.attendre_titre("Réserves (1, dont 1 à lever)")
        self.assertIn("OT lié : %s" % cloture["ot"], self.carte()[0]["meta"])
        self.assertEqual(self.carte()[0]["id"], reserve)
        self.sans_bouton()                                   # ni « Lever », ni « Modifier », ni « Ajouter », ni rappel
        self.assertEqual(page.evaluate("typeof Controles.interne.ouvrirLeveeReserve"), "function")


if __name__ == "__main__":
    unittest.main()
