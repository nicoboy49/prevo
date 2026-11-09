"""Tests de l'accueil, lot 3 (tâche T50, ARCHITECTURE.md §15.9).

Toujours serveur.py sur une copie du jeu de démo (ServeurPrevo). Familles (le nom du test le dit) :
    compteurs : « Contrôles sous 30 j » et « Habilitations à renouveler » = calcul Python
                indépendant sur les CSV du serveur (date du jour réelle) ; liens vers
                #/controles?filtre=30j et #/equipe?filtre=a-renouveler (les deux liens de la tuile
                « Contrôles et habilitations » de l'accueil « bento », T90) ; complément « dont n en
                retard » / « dont n échue(s) » ; 2.2 (T421, CS170) : « réserves en retard » = calcul Python
                (réserve ouverte d'un équipement suivi, échéance saisie ou date du contrôle + 30 jours, passée),
                lien vers #/controles?filtre=reserves-en-retard, détail selon l'échéance ;
    profils   : le technicien voit les trois indicateurs, le demandeur ne les voit pas ;
    telephone : 375 px, aucun défilement horizontal de la page avec huit indicateurs (lot 3 bis).

Aucun identifiant du jeu de démo écrit en dur. Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_accueil_lot3.py" -v
"""
import calendar
import csv
import datetime
import io
import re
import unittest
from pathlib import Path

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil

LIEN_CONTROLES = "#/controles?filtre=30j"
LIEN_HABILITATIONS = "#/equipe?filtre=a-renouveler"
LIEN_RESERVES = "#/controles?filtre=reserves-en-retard"
DELAI_LEVEE_PAR_DEFAUT_JOURS = 30          # D187 : sans échéance saisie, une réserve est à lever 30 jours après
DEBORDEMENT_JS = """(selecteur) => { const e = document.querySelector(selecteur);
    return e ? [e.scrollWidth, e.clientWidth] : null; }"""


def lire_csv(dossier, nom):
    texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte), delimiter=";"))


def brut(valeur):
    valeur = (valeur or "").strip()
    return valeur[1:] if valeur.startswith("'") else valeur


def jour(valeur):
    texte = brut(valeur)[:10]
    return datetime.date.fromisoformat(texte) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", texte) else None


def ajouter_mois(date, mois):
    total = date.year * 12 + date.month - 1 + mois
    annee, mois0 = divmod(total, 12)
    return datetime.date(annee, mois0 + 1, min(date.day, calendar.monthrange(annee, mois0 + 1)[1]))


def prochaine_date(controle):
    prochaine = jour(controle["prochaine_date"])
    if prochaine:
        return prochaine
    derniere = jour(controle["derniere_date"])
    try:
        periodicite = int(brut(controle["periodicite_mois"]))
    except ValueError:
        periodicite = 0
    return ajouter_mois(derniere, periodicite) if derniere and periodicite > 0 else None


def controles_sous_30_jours(dossier, aujourdhui):
    """(nombre, nombre en retard) — même définition que Controles.sous30Jours (§15.7)."""
    equipements = {e["id"]: e for e in lire_csv(dossier, "equipements.csv")}
    total = retard = 0
    for controle in lire_csv(dossier, "controles_reglementaires.csv"):
        equipement = equipements.get(controle["equipement_id"])
        if not equipement or brut(equipement["actif"]) == "0" or equipement["statut"] == "rebut":
            continue
        prochaine = prochaine_date(controle)
        if prochaine is None or prochaine <= aujourdhui + datetime.timedelta(days=30):
            total += 1
            if prochaine is not None and prochaine < aujourdhui:
                retard += 1
    return total, retard


def habilitations_a_renouveler(dossier, aujourdhui):
    """(nombre, nombre d'échues) — même définition que Equipe.aRenouveler (§15.8)."""
    actifs = {t["id"] for t in lire_csv(dossier, "techniciens.csv") if brut(t["actif"]) != "0"}
    comptent = {}
    for habilitation in lire_csv(dossier, "habilitations.csv"):
        if not brut(habilitation["intitule"]):
            continue
        cle = (habilitation["technicien_id"], re.sub(r"\s+", "", brut(habilitation["intitule"]).lower()))
        echeance = jour(habilitation["date_echeance"]) or datetime.date.max
        if cle not in comptent or echeance > comptent[cle]:
            comptent[cle] = echeance
    total = echues = 0
    for (technicien, _), echeance in comptent.items():
        if technicien not in actifs or echeance == datetime.date.max:
            continue
        restants = (echeance - aujourdhui).days
        if restants <= 60:
            total += 1
            echues += restants < 0
    return total, echues


def reserves_en_retard(dossier, aujourdhui):
    """[(id, échéance par défaut ?)] des réserves en retard — même définition que Controles.reservesEnRetard (2.2,
    CS170) : réserve ouverte (levee ≠ 1) d'un contrôle existant dont l'équipement est suivi ; échéance de levée
    saisie, sinon date du contrôle + 30 jours (D187), sinon aucune (jamais en retard) ; en retard si elle est passée.
    Triées comme l'accueil : échéance la plus ancienne d'abord, puis par identifiant."""
    equipements = {e["id"]: e for e in lire_csv(dossier, "equipements.csv")}
    controles = {c["id"]: c for c in lire_csv(dossier, "controles_reglementaires.csv")}
    retards = []
    for reserve in lire_csv(dossier, "reserves_controle.csv"):
        controle = controles.get(reserve["controle_id"])
        equipement = equipements.get(controle["equipement_id"]) if controle else None
        if brut(reserve["levee"]) == "1" or not equipement or brut(equipement["actif"]) == "0" \
                or equipement["statut"] == "rebut":
            continue
        saisie = jour(reserve["echeance_levee"])
        releve = jour(reserve["date_controle"])
        echeance = saisie or (releve + datetime.timedelta(days=DELAI_LEVEE_PAR_DEFAUT_JOURS) if releve else None)
        if echeance is not None and echeance < aujourdhui:
            retards.append((echeance, reserve["id"], saisie is None))
    return [(identifiant, par_defaut) for _, identifiant, par_defaut in sorted(retards)]


class TestAccueilLot3(CasNavigateur):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serveur = ServeurPrevo()
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)

    def ouvrir(self, profil="responsable", nom="Responsable", technicien_id=""):
        preregler_profil(self.contexte, profil, nom, technicien_id)
        self.page.goto(self.serveur.url + "/#/accueil")
        attendre_pret(self.page)

    def indicateur(self, lien):
        lien_html = self.page.locator("#contenu a[href='%s']" % lien)
        return lien_html.count(), (lien_html.locator(".chiffre").inner_text() if lien_html.count() else None), \
            (lien_html.locator(".comp").inner_text() if lien_html.count() else None)

    def test_compteurs_egaux_au_calcul_python_et_liens(self):
        self.ouvrir()
        aujourdhui = datetime.date.fromisoformat(self.page.evaluate("Donnees.aujourdhui()"))
        controles, retards = controles_sous_30_jours(self.serveur.dossier, aujourdhui)
        habilitations, echues = habilitations_a_renouveler(self.serveur.dossier, aujourdhui)
        self.assertGreater(controles, 0, "la démo doit avoir des contrôles sous 30 jours")
        self.assertGreater(habilitations, 0, "la démo doit avoir des habilitations à renouveler")

        nombre, chiffre, complement = self.indicateur(LIEN_CONTROLES)
        self.assertEqual(nombre, 1)
        self.assertEqual(int(chiffre), controles)
        if retards:
            self.assertIn("dont %d en retard" % retards, complement)

        nombre, chiffre, complement = self.indicateur(LIEN_HABILITATIONS)
        self.assertEqual(nombre, 1)
        self.assertEqual(int(chiffre), habilitations)
        if echues:
            self.assertIn("dont %d échue" % echues, complement)

        # Réserves en retard (2.2, T421) : la démo en a (la réserve du réservoir, sans échéance saisie)
        reserves = reserves_en_retard(self.serveur.dossier, aujourdhui)
        self.assertTrue(reserves, "la démo doit avoir une réserve en retard")
        nombre, chiffre, complement = self.indicateur(LIEN_RESERVES)
        self.assertEqual(nombre, 1)
        self.assertEqual(int(chiffre), len(reserves))
        par_defaut = sum(1 for _, defaut in reserves if defaut)
        if par_defaut == len(reserves):
            self.assertEqual(complement, "échéance par défaut passée (30 jours après le contrôle)")
        elif par_defaut:
            self.assertEqual(complement, "dont %d à l'échéance par défaut (30 jours après le contrôle)" % par_defaut)
        else:
            self.assertEqual(complement, "échéance de levée passée")

        # Mêmes valeurs que les règles (calculerCompteurs est le point d'extension)
        self.assertEqual(self.page.evaluate("Accueil.calculerCompteurs().controlesSous30j.length"), controles)
        self.assertEqual(self.page.evaluate("Accueil.calculerCompteurs().habilitationsARenouveler.length"), habilitations)
        self.assertEqual(self.page.evaluate("Accueil.calculerCompteurs().reservesEnRetard.map((e) => e.reserve.id)"),
                         [identifiant for identifiant, _ in reserves])
        # Les cinq indicateurs du lot 2 sont toujours là (plus celui du lot 3 bis, §16.6) ; accueil
        # « bento » (T90) : 4 compteurs, 2 tuiles « à surveiller » et les 3 liens de « Contrôles et habilitations »
        # (réserves en retard depuis la 2.2), plus les 3 liens de « Garanties et contrats » (2.2, T485)
        self.assertEqual(self.page.locator(
            "#contenu #bento :is(a.bento-compteur, a.bento-surveiller, a.bento-sous-lien)").count(), 12)
        # Contrôles, habilitations et réserves réunis dans une tuile
        self.assertEqual(self.page.locator("#contenu .bento-conformite a[href='%s']" % LIEN_CONTROLES).count(), 1)
        self.assertEqual(self.page.locator("#contenu .bento-conformite a[href='%s']" % LIEN_HABILITATIONS).count(), 1)
        self.assertEqual(self.page.locator("#contenu .bento-conformite a[href='%s']" % LIEN_RESERVES).count(), 1)

    def test_profils_technicien_voit_les_trois_indicateurs_demandeur_aucun(self):
        technicien = next(t for t in lire_csv(self.serveur.dossier, "techniciens.csv") if brut(t["actif"]) != "0")
        self.ouvrir("technicien", technicien["prenom"] + " " + technicien["nom"], technicien["id"])
        self.assertEqual(self.indicateur(LIEN_CONTROLES)[0], 1)
        self.assertEqual(self.indicateur(LIEN_HABILITATIONS)[0], 1)
        aujourdhui = datetime.date.fromisoformat(self.page.evaluate("Donnees.aujourdhui()"))
        nombre, chiffre, _ = self.indicateur(LIEN_RESERVES)
        self.assertEqual((nombre, int(chiffre)), (1, len(reserves_en_retard(self.serveur.dossier, aujourdhui))))
        self.assertEqual(self.page.locator("#contenu .accueil-mes-ordres").count(), 1)

        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
        try:
            page = contexte.new_page()
            self.surveiller(page)
            preregler_profil(contexte, "demandeur", "Paul Martin")
            page.goto(self.serveur.url + "/#/accueil")
            attendre_pret(page)
            self.assertEqual(page.locator("#contenu a[href='%s']" % LIEN_CONTROLES).count(), 0)
            self.assertEqual(page.locator("#contenu a[href='%s']" % LIEN_HABILITATIONS).count(), 0)
            self.assertEqual(page.locator("#contenu a[href='%s']" % LIEN_RESERVES).count(), 0)
        finally:
            contexte.close()

    def test_telephone_375_px_sans_defilement_horizontal(self):
        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 375, "height": 812},
                                               is_mobile=True, has_touch=True)
        try:
            page = contexte.new_page()
            self.surveiller(page)
            preregler_profil(contexte, "responsable", "Responsable")
            page.goto(self.serveur.url + "/#/accueil")
            attendre_pret(page)
            largeur, visible = page.evaluate(DEBORDEMENT_JS, "html")
            self.assertLessEqual(largeur, visible + 1)
            self.assertEqual(page.locator("#contenu a[href='%s']" % LIEN_CONTROLES).count(), 1)
        finally:
            contexte.close()


if __name__ == "__main__":
    unittest.main()
