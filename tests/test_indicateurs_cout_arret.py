"""Coût de l'arrêt sur l'écran Indicateurs (Prévo 2.2, lot L5, T474 ; D188, CS174 ; conception L4-L5-L6 §3.2).

L'onglet « Tableau de bord » gagne un 3ᵉ Pareto, « Pareto du coût de l'arrêt » (data-graphique="pareto-cout" :
10 premiers ; « Voir les valeurs » : Équipement, Heures d'arrêt, Coût d'une heure, Coût de l'arrêt, Cumul) et, à côté,
la carte « Non chiffré » : équipements sans coût horaire avec leurs heures d'arrêt et le lien « Saisir le coût
horaire » (modification de la fiche), OT sans durée avec leur lien et leur raison, en entier (le rapport mensuel n'en
cite que 8 et renvoie ici). Rien n'est estimé : un équipement non chiffré n'est jamais dans le Pareto ; des pannes
sans aucun équipement chiffré donnent « non chiffré », jamais 0,00 €. Filtres criticité et atelier respectés. Le
coût n'est montré qu'au profil qui a les coûts (D126 : cout_arret_h caché au technicien et au demandeur, T473).

Familles :
    demo        jeu de démo (file://) : l'équipement du rôle equipement_non_chiffre (tests/fixtures/demo-scenarios.json)
                est listé avec ses heures d'arrêt et jamais dans le Pareto ; chaque ligne du Pareto et le total égalent
                un calcul Python `decimal` fait sur les lignes de la page (sans le code des Indicateurs) ; lien
                « Saisir le coût horaire » ; filtres criticité et atelier ; téléphone 375 px ;
    jeu         jeu d'essai de la conception (tests/test_cout_arret_regles.py) : mars 2026 (591,62 €, partiel, PO-03
                et OT-2026-0003 listés), avril (0 € chiffré, équipement introuvable sans lien), juin (aucune panne),
                une journée sans équipement chiffré (« non chiffré ») ; anglais ;
    profil      sans les coûts : ni Pareto du coût, ni carte, ni entrée « Comprendre ».

Lancer depuis la racine du projet (navigateur : au travers du verrou) :
    py -X utf8 -m unittest discover -s tests -p "test_indicateurs_cout_arret.py" -v
"""
import html
import re
import unittest
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from commun import CasNavigateur, attendre_pret, preregler_profil, scenarios_demo, url_fichier
from test_cout_arret_regles import DEMANDES, EQUIPEMENTS, LOCALISATIONS, ORDRES, centimes_decimal

NOMBRE_GRAPHIQUES = 8              # dont pareto-cout
TYPES_PANNE = ("correctif immédiat", "correctif différé")
STATUTS_CLOTURES = ("Clôturé techniquement", "Clôturé administrativement")

# Résultats affichés après la navigation (la zone d'avant porte data-ancienne) et graphiques prêts.
ATTENDRE_GRAPHIQUES_JS = """(nombre) => {
  if (!document.querySelector('#contenu .indicateurs-resultats:not([data-ancienne])')) return false;
  const cartes = document.querySelectorAll('#contenu .indicateurs-graphique');
  return cartes.length === nombre && Array.from(cartes).every((c) => ['pret', 'vide', 'erreur'].includes(c.dataset.etat));
}"""

# Le Pareto du coût : cellules de « Voir les valeurs », notes, état, catégories du graphique (ECharts).
LIRE_PARETO_JS = """() => {
  const carte = document.querySelector('#contenu .indicateurs-graphique[data-graphique="pareto-cout"]');
  if (!carte) return null;
  const zone = carte.querySelector('.graph, [class^="indicateurs-graph-"]');
  const instance = zone && typeof echarts !== 'undefined' ? echarts.getInstanceByDom(zone) : null;
  const option = instance ? instance.getOption() : null;
  return {
    titre: carte.querySelector('h2').textContent.trim(), etat: carte.dataset.etat,
    entetes: Array.from(carte.querySelectorAll('.vue-tableau thead th')).map((th) => th.textContent.trim()),
    lignes: Array.from(carte.querySelectorAll('.vue-tableau tbody tr')).filter((tr) => !tr.querySelector('.vide-table'))
      .map((tr) => Array.from(tr.cells).map((td) => td.textContent.trim())),
    notes: Array.from(carte.querySelectorAll('.indicateurs-note')).map((p) => p.textContent.trim()),
    vide: carte.dataset.etat === 'vide' ? zone.textContent.trim() : null,
    categories: option ? [].concat(...option.yAxis.map((axe) => axe.data || [])) : null,
  };
}"""

LIRE_CARTE_JS = """() => {
  const carte = document.querySelector('#contenu .indicateurs-non-chiffre');
  if (!carte) return null;
  const texte = (el) => (el ? el.textContent.replace(/\\s+/g, ' ').trim() : '');
  const lignes = (selecteur) => Array.from(carte.querySelectorAll(selecteur + ' tbody tr')).map((tr) => ({
    id: tr.dataset.equipement || tr.dataset.ot,
    cellules: Array.from(tr.cells).map((td) => texte(td.querySelector('a:not(.indicateurs-saisir-cout)') || td)),
    liens: Array.from(tr.querySelectorAll('a')).map((a) => a.getAttribute('href')),
    saisir: texte(tr.querySelector('a.indicateurs-saisir-cout')), raison: texte(tr.querySelector('.indicateurs-raison')),
    replie: Boolean(tr.closest('details')) }));
  return { complet: carte.dataset.complet, titre: texte(carte.querySelector('h2')), resume: texte(carte.querySelector('p.note')),
           suites: Array.from(carte.querySelectorAll('details.indicateurs-suite > summary')).map(texte),
           equipements: lignes('.indicateurs-non-chiffres'), ots: lignes('.indicateurs-sans-duree'),
           classes: carte.className, voisine: (carte.previousElementSibling || {}).dataset ? carte.previousElementSibling.dataset.graphique : null };
}"""

# Lignes brutes de la page (rien du code des Indicateurs) : le calcul Python de référence part d'elles.
LIGNES_JS = """() => {
  const garder = (table, champs) => Donnees.lignes(table).map((l) => Object.fromEntries(champs.map((c) => [c, String(l[c] === undefined || l[c] === null ? '' : l[c]).trim()])));
  const zone = document.querySelector('#contenu .indicateurs-resultats');
  return {
    ordres: garder('ordres_travail', ['id', 'di_id', 'equipement_id', 'type', 'statut', 'date_creation', 'arret_production', 'duree_arret_h']),
    demandes: garder('demandes', ['id', 'date_heure', 'statut', 'ot_id']),
    equipements: garder('equipements', ['id', 'repere', 'criticite', 'cout_arret_h']),
    debut: zone.dataset.debut, fin: zone.dataset.fin,
  };
}"""


def blancs(texte):
    """Espaces insécables (Intl : « 591,62 € », « 4 h ») ramenées à l'espace simple, entités HTML décodées."""
    return html.unescape(texte or "").replace("\u00a0", " ").replace("\u202f", " ")


def decimal_fr(texte):
    """Nombre affiché à la française (« 1 234,50 », « 6,5 h ») → Decimal."""
    propre = re.sub(r"[\s\u00a0\u202f]", "", texte or "")
    return Decimal(re.sub(r"(h|%|€)$", "", propre).replace(",", "."))


def pannes_python(donnees):
    """Pannes de la période, comme la conception §3.1 les définit : OT correctif immédiat ou différé, arrêt de
    production, non annulé, daté par sa DI d'origine (sinon sa création)."""
    demandes = {d["id"]: d for d in donnees["demandes"]}
    acceptees = {}
    for di in sorted(donnees["demandes"], key=lambda d: d["date_heure"]):
        if di["ot_id"] and di["statut"] == "Acceptée":
            acceptees.setdefault(di["ot_id"], di)
    resultat = []
    for ot in donnees["ordres"]:
        if ot["type"] not in TYPES_PANNE or ot["arret_production"] != "1" or ot["statut"] == "Annulé":
            continue
        di = demandes.get(ot["di_id"]) or acceptees.get(ot["id"])
        date = (di["date_heure"] if di and di["date_heure"] else ot["date_creation"])[:10]
        if donnees["debut"] <= date <= donnees["fin"]:
            resultat.append(dict(ot, date=date))
    return sorted(resultat, key=lambda ot: (ot["date"], ot["id"]))


def cout_python(donnees, garder=None):
    """Calcul de référence (Python decimal, ROUND_HALF_UP) : { chiffres, nonChiffres, sansDuree, totalCentimes } ;
    `garder` (filtre) : équipement → bool ; avec un filtre, une panne d'un équipement introuvable est écartée."""
    equipements = {e["id"]: e for e in donnees["equipements"]}
    durees = defaultdict(list)
    vus = []
    sans_duree = []
    for ot in pannes_python(donnees):
        equipement = equipements.get(ot["equipement_id"])
        if garder is not None and (equipement is None or not garder(equipement)):
            continue
        if ot["equipement_id"] not in vus:
            vus.append(ot["equipement_id"])
        if ot["duree_arret_h"]:
            durees[ot["equipement_id"]].append(ot["duree_arret_h"])
        else:
            sans_duree.append((ot["id"], ot["equipement_id"], ot["statut"] in STATUTS_CLOTURES))
    chiffres, non_chiffres = [], []
    for equipement_id in vus:
        heures = sum((Decimal(d) for d in durees[equipement_id]), Decimal(0))
        cout = (equipements.get(equipement_id) or {}).get("cout_arret_h", "")
        if not cout:
            non_chiffres.append((equipement_id, heures))
        elif durees[equipement_id]:
            chiffres.append((equipement_id, heures, Decimal(cout), centimes_decimal(durees[equipement_id], cout)))
    chiffres.sort(key=lambda l: (-l[3], -l[1], l[0]))
    non_chiffres.sort(key=lambda l: (-l[1], l[0]))
    return {"chiffres": chiffres, "nonChiffres": non_chiffres, "sansDuree": sans_duree,
            "totalCentimes": sum(l[3] for l in chiffres)}


def manque_fr(calcul):
    morceaux = []
    n = len(calcul["nonChiffres"])
    if n:
        morceaux.append("1 équipement non chiffré" if n == 1 else "%d équipements non chiffrés" % n)
    if calcul["sansDuree"]:
        morceaux.append("%d OT sans durée" % len(calcul["sansDuree"]))
    return ", ".join(morceaux)


class CasCoutArret(CasNavigateur):

    def ouvrir_demo(self, requete="", page=None, contexte=None):
        page = page or self.page
        preregler_profil(contexte or self.contexte, "responsable", "Responsable")
        page.goto(url_fichier("index.html"))
        page.click("#btn-demo")
        attendre_pret(page)
        self.aller(requete, page)
        return page

    def ouvrir_jeu(self, requete):
        preregler_profil(self.contexte, "responsable", "Responsable")
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        self.page.evaluate("""async (tables) => {
          Donnees.initialiser(StockageDemo.creer(tables), { poste: 'Poste test', profil: 'Responsable test' });
          await Donnees.chargerTout();
        }""", {"localisations": LOCALISATIONS, "equipements": EQUIPEMENTS, "demandes": DEMANDES, "ordres_travail": ORDRES})
        self.aller(requete)

    def aller(self, requete, page=None, nombre=NOMBRE_GRAPHIQUES):
        page = page or self.page
        page.evaluate("""(h) => { document.querySelectorAll('#contenu .indicateurs-resultats').forEach((z) => { z.dataset.ancienne = '1'; });
                                  App.naviguer(h); }""", "#/indicateurs" + requete)
        page.wait_for_function(ATTENDRE_GRAPHIQUES_JS, arg=nombre, timeout=20000)

    def pareto(self, page=None):
        return (page or self.page).evaluate(LIRE_PARETO_JS)

    def carte(self, page=None):
        return (page or self.page).evaluate(LIRE_CARTE_JS)

    def regle(self, page=None):
        """Indicateurs.coutArret de la vue affichée (période et filtres lus dans l'écran)."""
        return (page or self.page).evaluate("""() => { const z = document.querySelector('#contenu .indicateurs-resultats');
            const p = Indicateurs.periode(z.dataset.periode, Donnees.aujourdhui(), z.dataset.du, z.dataset.au);
            return Indicateurs.coutArret(p, { criticite: z.dataset.criticite || '', atelier: z.dataset.atelier || '' }); }""")

    def euro(self, centimes):
        return blancs(self.page.evaluate("(c) => UI.euro(c / 100, 2)", centimes))

    def repere(self, equipement_id):
        return self.page.evaluate("(id) => { const e = Donnees.trouver('equipements', id); return (e && e.repere) || id; }", equipement_id)

    def verifier_pareto(self, lus, chiffres):
        """Lignes de « Voir les valeurs » = les 10 premiers chiffrés à plus de 0 € du calcul Python, au centime."""
        attendus = [ligne for ligne in chiffres if ligne[3] > 0][:10]
        total = sum(ligne[3] for ligne in chiffres)
        self.assertEqual([l[0] for l in lus], [self.repere(l[0]) for l in attendus])
        cumul = 0
        for lu, (equipement_id, heures, cout, centimes) in zip(lus, attendus):
            with self.subTest(equipement=equipement_id):
                cumul += centimes
                self.assertEqual(decimal_fr(lu[1]), heures.quantize(Decimal("0.01"), ROUND_HALF_UP), lu)
                self.assertEqual(decimal_fr(lu[2]), cout.quantize(Decimal("0.01"), ROUND_HALF_UP), lu)
                self.assertEqual(decimal_fr(lu[3]), Decimal(centimes) / 100, lu)                  # au centime
                self.assertLessEqual(abs(float(decimal_fr(lu[4])) - cumul * 100 / total), 0.05 + 1e-9, lu)


class TestDemo(CasCoutArret):
    """Jeu de démo en file:// : profil responsable, 12 derniers mois."""

    def test_equipement_non_chiffre_liste_avec_ses_heures_et_jamais_dans_le_pareto(self):
        role = scenarios_demo()["equipement_non_chiffre"]
        self.ouvrir_demo()
        donnees = self.page.evaluate(LIGNES_JS)
        calcul = cout_python(donnees)
        equipement = next(e for e in donnees["equipements"] if e["id"] == role)
        self.assertEqual(equipement["cout_arret_h"], "")
        heures = dict(calcul["nonChiffres"])[role]
        self.assertGreater(heures, 0, "le rôle a une panne avec durée dans la période")
        carte = self.carte()
        self.assertEqual(carte["titre"], "Non chiffré")
        self.assertIn("carte c6", carte["classes"])
        self.assertEqual(carte["voisine"], "pareto-cout")                          # à côté du Pareto du coût
        self.assertEqual(carte["complet"], "0")
        self.assertTrue(carte["resume"].startswith("Rien n'est estimé"), carte["resume"])
        # Tous les non chiffrés, par heures décroissantes, chacun avec ses heures d'arrêt et son lien
        self.assertEqual([l["id"] for l in carte["equipements"]], [e for e, _ in calcul["nonChiffres"]])
        for ligne, (equipement_id, attendu) in zip(carte["equipements"], calcul["nonChiffres"]):
            self.assertEqual(ligne["cellules"][0], self.repere(equipement_id))
            self.assertEqual(decimal_fr(blancs(ligne["cellules"][1])), attendu.quantize(Decimal("0.01"), ROUND_HALF_UP), ligne)
            self.assertEqual(ligne["saisir"], "Saisir le coût horaire")
            self.assertIn("#/equipement/%s/modifier" % equipement_id, ligne["liens"])
        # Les OT sans durée, avec leur lien et leur raison
        self.assertEqual([l["id"] for l in carte["ots"]], [ot for ot, _, _ in calcul["sansDuree"]])
        for ligne, (ot_id, equipement_id, clos) in zip(carte["ots"], calcul["sansDuree"]):
            self.assertEqual(ligne["liens"][0], "#/ot/%s" % ot_id)
            self.assertEqual([ligne["cellules"][1], ligne["raison"]], [self.repere(equipement_id), "sans durée d'arrêt" if clos else "non clôturé"])
        # Tous listés à l'écran (D188 : la liste complète du rapport est ici) ; au-delà de 5, repliés sous « Voir les n autres »
        self.assertEqual([l["replie"] for l in carte["equipements"]], [rang >= 5 for rang in range(len(carte["equipements"]))])
        attendues = ["Voir les %d autres" % (len(liste) - 5) for liste in (carte["equipements"], carte["ots"]) if len(liste) > 6]
        attendues += ["Voir 1 autre" for liste in (carte["equipements"], carte["ots"]) if len(liste) == 6]
        self.assertEqual(sorted(carte["suites"]), sorted(attendues))
        self.assertGreater(len(carte["equipements"]), 5, "la démo a plus de 5 équipements non chiffrés : la suite repliée est vérifiée")
        # Jamais dans le Pareto par coût : ni le tableau, ni le graphique
        pareto = self.pareto()
        self.assertEqual(pareto["etat"], "pret")
        reperes = [ligne[0] for ligne in pareto["lignes"]]
        self.assertTrue(reperes, "la démo chiffre des équipements (T475)")
        self.assertNotIn(self.repere(role), reperes)
        self.assertNotIn(self.repere(role), pareto["categories"])
        self.assertEqual(sorted(pareto["categories"]), sorted(reperes))
        # Règle (T470) d'accord : non chiffré avec ses heures, absent des lignes chiffrées
        regle = self.regle()
        self.assertIn(role, [l["equipementId"] for l in regle["nonChiffres"]])
        self.assertNotIn(role, [l["equipementId"] for l in regle["parEquipement"]])

    def test_pareto_et_total_egaux_au_calcul_python_au_centime(self):
        self.ouvrir_demo()
        calcul = cout_python(self.page.evaluate(LIGNES_JS))
        pareto = self.pareto()
        self.assertEqual(pareto["titre"], "Pareto du coût de l'arrêt")
        self.assertEqual(pareto["entetes"], ["Équipement", "Heures d'arrêt", "Coût d'une heure (€)", "Coût de l'arrêt (€)", "Cumul (%)"])
        self.verifier_pareto(pareto["lignes"], calcul["chiffres"])
        self.assertLessEqual(len(pareto["lignes"]), 10)
        self.assertEqual(blancs(pareto["notes"][0]), "Coût de l'arrêt de la période : %s." % self.euro(calcul["totalCentimes"]))
        self.assertEqual(self.regle()["totalCentimes"], calcul["totalCentimes"])
        self.assertEqual(blancs(pareto["notes"][1]), "Partiel : %s (liste : carte « Non chiffré »)." % manque_fr(calcul))
        # Export CSV : mêmes valeurs, au point décimal, au centime
        carte = self.page.locator('#contenu .indicateurs-graphique[data-graphique="pareto-cout"]')
        with self.page.expect_download() as attente:
            carte.locator('button[data-export="csv"]').click()
        octets = Path(attente.value.path()).read_bytes()
        self.assertTrue(octets.startswith(b"\xef\xbb\xbf"))
        lignes = octets[3:].decode("utf-8").rstrip("\r\n").split("\r\n")
        self.assertEqual(lignes[0], "Équipement;Heures d'arrêt;Coût d'une heure (€);Coût de l'arrêt (€);Cumul (%)")
        attendus = [l for l in calcul["chiffres"] if l[3] > 0][:10]
        self.assertEqual([Decimal(l.split(";")[3]) for l in lignes[1:]], [Decimal(l[3]) / 100 for l in attendus])
        # Comprendre : la formule, rien d'estimé
        comprendre = self.page.locator("#contenu .indicateurs-comprendre")
        comprendre.locator("summary").click()
        texte = comprendre.inner_text()
        self.assertIn("Coût de l'arrêt : pour les pannes de la période", texte)
        self.assertIn("Rien n'est estimé", texte)
        self.assertNotRegex(self.page.inner_text("#contenu"), r"NaN|Infinity|undefined")

    def test_saisir_le_cout_horaire_ouvre_la_modification_de_la_fiche(self):
        role = scenarios_demo()["equipement_non_chiffre"]
        self.ouvrir_demo()
        lien = self.page.locator('#contenu .indicateurs-non-chiffre tr[data-equipement="%s"] a.indicateurs-saisir-cout' % role)
        self.assertEqual(lien.get_attribute("aria-label"), "Saisir le coût horaire de %s" % self.repere(role))
        lien.click()
        self.page.wait_for_function("(h) => location.hash === h", arg="#/equipement/%s/modifier" % role)
        self.page.locator("#parc-formulaire .champ[data-champ=cout_arret_h]").wait_for()

    def test_filtres_criticite_et_atelier_respectes(self):
        role = scenarios_demo()["equipement_non_chiffre"]
        self.ouvrir_demo("?periode=12-mois&criticite=A")
        donnees = self.page.evaluate(LIGNES_JS)
        criticites = {e["id"]: e["criticite"] for e in donnees["equipements"]}
        self.assertNotEqual(criticites[role], "A")
        calcul = cout_python(donnees, lambda e: e["criticite"] == "A")
        self.verifier_pareto(self.pareto()["lignes"], calcul["chiffres"])
        carte = self.carte()
        self.assertEqual([l["id"] for l in carte["equipements"]], [e for e, _ in calcul["nonChiffres"]])
        self.assertNotIn(role, [l["id"] for l in carte["equipements"]])
        self.assertTrue(all(criticites.get(l["id"]) == "A" for l in carte["equipements"]))
        # Atelier : celui du rôle le garde, un autre l'écarte ; l'écran suit la règle filtrée
        ateliers = self.page.evaluate("""(role) => { const ctx = Indicateurs.interne.contexte();
            const e = ctx.equipements.get(role);
            const liste = Donnees.lignes('localisations').filter((l) => l.type === 'atelier');
            return { avec: liste.filter((l) => Indicateurs.interne.passeFiltres(e, { atelier: l.id }, ctx)).map((l) => l.id),
                     sans: liste.filter((l) => !Indicateurs.interne.passeFiltres(e, { atelier: l.id }, ctx)).map((l) => l.id) }; }""", role)
        self.assertTrue(ateliers["avec"] and ateliers["sans"], ateliers)
        for atelier, present in ((ateliers["avec"][0], True), (ateliers["sans"][0], False)):
            with self.subTest(atelier=atelier):
                self.aller("?periode=12-mois&atelier=" + atelier)
                self.page.wait_for_function("(a) => document.querySelector('#contenu .indicateurs-resultats').dataset.atelier === a", arg=atelier)
                regle = self.regle()
                carte = self.carte()
                self.assertEqual([l["id"] for l in carte["equipements"]], [l["equipementId"] for l in regle["nonChiffres"]])
                self.assertEqual([l["id"] for l in carte["ots"]], [l["otId"] for l in regle["sansDuree"]])
                self.assertEqual(role in [l["id"] for l in carte["equipements"]], present)
                lus = [l[0] for l in self.pareto()["lignes"]]
                self.assertEqual(lus, [self.repere(l["equipementId"]) for l in regle["parEquipement"] if l["centimes"] > 0][:10])

    def test_telephone_375_px_sans_defilement_zones_tactiles(self):
        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 375, "height": 812},
                                               is_mobile=True, has_touch=True, device_scale_factor=2)
        try:
            telephone = contexte.new_page()
            self.surveiller(telephone)
            self.ouvrir_demo(page=telephone, contexte=contexte)
            self.assertTrue(telephone.evaluate("UI.estTelephone()"))
            carte = telephone.locator("#contenu .indicateurs-non-chiffre")
            carte.scroll_into_view_if_needed()
            self.assertTrue(carte.is_visible())
            telephone.locator('#contenu [data-graphique="pareto-cout"] .vue-tableau summary').click()
            largeurs = telephone.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
            self.assertLessEqual(largeurs[0], largeurs[1], "défilement horizontal à 375 px : %r" % largeurs)
            # La carte tient dans la largeur de l'écran ; ses tableaux défilent dans leur cadre s'il le faut
            boite = carte.bounding_box()
            self.assertLessEqual(boite["x"] + boite["width"], 375 + 0.5, boite)
            petites = telephone.evaluate("""() => Array.from(document.querySelectorAll(
                '#contenu .indicateurs-non-chiffre a, #contenu .indicateurs-non-chiffre summary, #contenu [data-graphique="pareto-cout"] button, #contenu [data-graphique="pareto-cout"] summary'))
              .filter((el) => el.getBoundingClientRect().width).filter((el) => el.getBoundingClientRect().height < 47.5)
              .map((el) => el.textContent.trim().slice(0, 30) + ' ' + Math.round(el.getBoundingClientRect().height) + ' px')""")
            self.assertEqual(petites, [])
            self.assertGreater(telephone.locator("#contenu .indicateurs-non-chiffre a.indicateurs-saisir-cout").count(), 0)
            self.assertNotRegex(telephone.inner_text("#contenu"), r"NaN|Infinity|undefined")
        finally:
            contexte.close()


class TestJeuDEssai(CasCoutArret):
    """Jeu d'essai de la conception (tests/test_cout_arret_regles.py), périodes choisies par l'adresse."""

    MARS = "?periode=du-au&du=2026-03-01&au=2026-03-31"

    def test_mars_591_62_partiel_et_liste_complete(self):
        self.ouvrir_jeu(self.MARS)
        pareto = self.pareto()
        self.assertEqual(pareto["lignes"], [["PO-01", "3,75", "150,00", "562,50", "95,1"],
                                            ["PO-02", "0,33", "87,35", "29,11", "100,0"],
                                            ["PO-04", "0,05", "0,10", "0,01", "100,0"]])
        attendu = sum([centimes_decimal(["1.5", "2.25"], "150"), centimes_decimal(["0.3333"], "87.35"), centimes_decimal(["0.05"], "0.10")])
        self.assertEqual(attendu, 59162)
        self.assertEqual([blancs(n) for n in pareto["notes"]], ["Coût de l'arrêt de la période : 591,62 €.",
                                                              "Partiel : 1 équipement non chiffré, 1 OT sans durée (liste : carte « Non chiffré »)."])
        self.assertEqual(pareto["categories"], ["PO-01", "PO-02", "PO-04"])
        carte = self.carte()
        self.assertEqual(carte["complet"], "0")
        self.assertEqual([(l["id"], l["cellules"][0], blancs(l["cellules"][1])) for l in carte["equipements"]], [("EQ-0003", "PO-03", "4 h")])
        self.assertEqual(carte["equipements"][0]["liens"], ["#/equipement/EQ-0003", "#/equipement/EQ-0003/modifier"])
        self.assertEqual([(l["id"], l["cellules"], l["raison"], l["liens"]) for l in carte["ots"]],
                         [("OT-2026-0003", ["OT-2026-0003", "PO-01"], "non clôturé", ["#/ot/OT-2026-0003", "#/equipement/EQ-0001"])])
        self.assertEqual(carte["suites"], [])                                       # 5 lignes au plus : rien de replié
        # Le non chiffré n'est jamais estimé : PO-03 n'est ni dans le Pareto ni dans le total
        self.assertNotIn("PO-03", [l[0] for l in pareto["lignes"]])

    def test_avril_zero_euro_chiffre_et_equipement_introuvable_sans_lien(self):
        self.ouvrir_jeu("?periode=du-au&du=2026-04-01&au=2026-04-30")
        pareto = self.pareto()
        # PO-09 (2 h × 1 250,50 €, panne datée par sa DI du 30/04) puis PO-08 (0,8334 h × 2,01 €) ; PO-05 (0 €) n'y est pas
        self.assertEqual([(l[0], decimal_fr(l[3])) for l in pareto["lignes"]],
                         [("PO-09", Decimal(centimes_decimal(["2"], "1250.50")) / 100),
                          ("PO-08", Decimal(centimes_decimal(["0.5", "0.33335"], "2.01")) / 100)])
        carte = self.carte()
        ids = [l["id"] for l in carte["equipements"]]
        self.assertEqual(ids, ["EQ-0099", "EQ-0007", "EQ-0006", "EQ-0003"])        # par heures décroissantes
        self.assertNotIn("EQ-0005", ids)                                            # 0 saisi : chiffré, pas « non chiffré »
        introuvable = carte["equipements"][0]
        self.assertEqual((introuvable["cellules"][0], introuvable["liens"], introuvable["saisir"]), ("EQ-0099", [], ""))
        self.assertEqual([(l["id"], l["raison"]) for l in carte["ots"]],
                         [("OT-2026-0016", "sans durée d'arrêt"), ("OT-2026-0018", "sans durée d'arrêt")])

    def test_sans_panne_puis_pannes_sans_aucun_equipement_chiffre(self):
        self.ouvrir_jeu("?periode=du-au&du=2026-06-01&au=2026-06-30")
        pareto = self.pareto()
        self.assertEqual((pareto["etat"], pareto["vide"], pareto["lignes"]), ("vide", "Aucune panne sur la période.", []))
        self.assertEqual([blancs(n) for n in pareto["notes"]], ["Coût de l'arrêt de la période : 0,00 €."])
        carte = self.carte()
        self.assertEqual((carte["complet"], carte["resume"], carte["equipements"], carte["ots"]), ("1", "Aucune panne sur la période.", [], []))
        # Le 6 mars : une seule panne, sur PO-03 sans coût horaire → « non chiffré », jamais 0,00 €
        self.aller("?periode=du-au&du=2026-03-06&au=2026-03-06")
        self.page.wait_for_function("document.querySelector('#contenu .indicateurs-resultats').dataset.du === '2026-03-06'")
        pareto = self.pareto()
        self.assertEqual((pareto["etat"], pareto["vide"]), ("vide", "Aucun coût d'arrêt chiffré sur la période."))
        self.assertEqual([blancs(n) for n in pareto["notes"]], ["Coût de l'arrêt de la période : non chiffré.",
                                                              "Partiel : 1 équipement non chiffré (liste : carte « Non chiffré »)."])
        self.assertNotIn("0,00", " ".join(pareto["notes"]))
        self.assertEqual([l["id"] for l in self.carte()["equipements"]], ["EQ-0003"])

    def test_anglais(self):
        self.contexte.add_init_script("try { localStorage.setItem('prevo.langue', 'en'); } catch (e) { /* rien */ }")
        self.ouvrir_jeu(self.MARS)
        self.assertEqual(self.page.evaluate("I18n.langue"), "en")
        pareto = self.pareto()
        self.assertEqual(pareto["titre"], "Downtime cost Pareto")
        self.assertEqual(pareto["entetes"][1:4], ["Downtime hours", "Cost per hour (€)", "Downtime cost (€)"])
        self.assertEqual([blancs(n) for n in pareto["notes"]], ["Downtime cost for the period: €591.62.",
                                                              "Partial: 1 equipment not costed, 1 WO with no duration (list: “Not costed” card)."])
        carte = self.carte()
        self.assertEqual(carte["titre"], "Not costed")
        self.assertEqual(carte["equipements"][0]["saisir"], "Enter the hourly cost")
        self.assertEqual(carte["ots"][0]["raison"], "not closed")


class TestProfilSansLesCouts(CasCoutArret):

    def test_aucun_cout_de_l_arret_pour_un_profil_sans_les_couts(self):
        # Le serveur ne donne pas cout_arret_h au technicien ni au demandeur (T473), qui n'ouvrent pas les Indicateurs
        # (test_indicateurs.py) ; l'écran ne montre de toute façon le coût de l'arrêt qu'au responsable.
        self.ouvrir_jeu(TestJeuDEssai.MARS)
        self.assertEqual(self.page.locator('#contenu [data-graphique="pareto-cout"]').count(), 1)
        self.page.evaluate("() => { App.estResponsable = () => false; }")
        self.aller("?periode=du-au&du=2026-03-01&au=2026-03-30", nombre=NOMBRE_GRAPHIQUES - 1)
        self.page.wait_for_function("document.querySelector('#contenu .indicateurs-resultats').dataset.au === '2026-03-30'")
        self.assertEqual(self.page.locator('#contenu [data-graphique="pareto-cout"]').count(), 0)
        self.assertEqual(self.page.locator("#contenu .indicateurs-non-chiffre").count(), 0)
        texte = self.page.text_content("#contenu")
        for interdit in ("Coût de l'arrêt", "non chiffré", "Non chiffré", "Saisir le coût horaire", "591,62"):
            self.assertNotIn(interdit, texte)


if __name__ == "__main__":
    unittest.main()
