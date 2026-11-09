"""Tests du rapport mensuel figé (tâche T51, ARCHITECTURE.md §15.10 ; CDC du lot 3, D43 à D45).

Mode serveur : un serveur.py neuf par test (copie du jeu de démo, dates non décalées), responsable ;
vérifications sur le disque (donnees/documents/, parametres.csv, journal.csv). Familles :
    figer       la tuile du rapport de l'accueil (#bandeau-rapport, grille « bento » depuis T90) propose
                le mois écoulé ; « Figer » écrit rapport-mensuel-AAAA-MM.html dans les documents,
                l'ajoute à rapports_mensuels et au journal ; rien n'est écrit sans clic ; « Plus tard »
                retire la tuile ;
    autonome    le fichier n'a ni <script> ni ressource externe (seul lien : mailto:), s'ouvre seul en
                file:// sans erreur ni requête réseau, et tient sur UNE page A4 imprimée (PDF) ;
    chiffres    tuiles = Indicateurs.global du mois, et la 4ᵉ (2.2, T472) = Indicateurs.coutArret du mois au
                centime ; comparaison à N-1 « non comparable » quand l'historique ne couvre pas ce mois ; décision
                « à examiner » au-delà du seuil (paramètre abaissé), jamais « à remplacer » (coût de l'arrêt en
                détail : test_rapport_cout_arret.py) ;
    revisions   « Recalculer » écrit -r2 sans toucher au premier ; un fichier du même nom déjà présent
                sur le disque n'est jamais écrasé (révision suivante) ;
    courriel    lien mailto: sans pièce jointe, objet et corps du résumé ;
    reserves    2.2 (T421, CS170) : fait marquant « n réserves de contrôle en retard au … (échéance de levée passée…) » et
                décision « Lever les n réserves en retard : texte court (repère) » (calcul Python ; la démo : RA-01) ;
                trois faits au plus, les réserves passent avant la répétition des pannes, rien ne change sans
                réserve en retard ; langue choisie pour le rapport (D156) ;
    onglet      Rapport.afficherOnglet liste les rapports et recalcule ;
    demo        mode démo : rapport en mémoire (documentsEnMemoire, donc dans l'export ZIP).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_rapport.py" -v
"""
import csv
import datetime
import html
import io
import re
import shutil
import tempfile
import time
import unittest
import urllib.parse
from pathlib import Path

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, url_fichier
from test_accueil_lot3 import brut, reserves_en_retard

NOMS_MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
             "novembre", "décembre"]


def decaler_mois(mois, n):
    total = int(mois[:4]) * 12 + int(mois[5:7]) - 1 + n
    return "%04d-%02d" % (total // 12, total % 12 + 1)


def libelle_mois(mois):
    return NOMS_MOIS[int(mois[5:7]) - 1] + " " + mois[:4]


# Mois écoulé à la date du jour réelle (l'application lit la vraie date) : jamais écrit en dur.
MOIS = decaler_mois(datetime.date.today().isoformat()[:7], -1)
LIBELLE = libelle_mois(MOIS)
NOM = "rapport-mensuel-%s.html" % MOIS


def lire_csv(dossier, nom):
    # Windows refuse un instant l'ouverture d'un fichier que le serveur remplace (écriture atomique, os.replace) :
    # quelques essais rapprochés au lieu d'une erreur (T199 : PermissionError vu dans la suite complète du 2026-11-04).
    for essai in range(20):
        try:
            texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
            break
        except PermissionError:
            if essai == 19:
                raise
            time.sleep(0.05)
    return list(csv.DictReader(io.StringIO(texte), delimiter=";"))


def ecrire_parametre(dossier, cle, valeur):
    chemin = Path(dossier) / "parametres.csv"
    lignes = lire_csv(dossier, "parametres.csv")
    for ligne in lignes:
        if ligne["cle"] == cle:
            ligne["valeur"] = valeur
            break
    else:
        lignes.append({"cle": cle, "valeur": valeur})
    tampon = io.StringIO(newline="")
    ecrivain = csv.writer(tampon, delimiter=";", lineterminator="\r\n")
    ecrivain.writerow(["cle", "valeur"])
    for ligne in lignes:
        ecrivain.writerow([ligne["cle"], ligne["valeur"]])
    chemin.write_bytes(b"\xef\xbb\xbf" + tampon.getvalue().encode("utf-8"))


def parametre(dossier, cle):
    return next((ligne["valeur"] for ligne in lire_csv(dossier, "parametres.csv") if ligne["cle"] == cle), None)


LONGUEUR_TEXTE_RESERVE = 60     # rapport-contenu.js : texte d'une réserve citée par une décision


def texte_court(texte):
    """Texte d'une réserve citée par la décision « Lever les réserves en retard » (même règle que rapport-contenu.js) :
    sur une ligne, coupé à 60 caractères au dernier blanc de la seconde moitié, puis « … »."""
    ligne = re.sub(r"\s+", " ", texte.strip())
    if len(ligne) <= LONGUEUR_TEXTE_RESERVE:
        return ligne
    coupe = ligne[:LONGUEUR_TEXTE_RESERVE]
    if coupe.rfind(" ") >= LONGUEUR_TEXTE_RESERVE / 2:
        coupe = coupe[:coupe.rfind(" ")]
    return re.sub(r"[\s,;:.]+$", "", coupe) + "…"


def fait_reserves_attendu(nombre, par_defaut, date):
    """Fait marquant des réserves en retard (français), d'après leur nombre et celles à l'échéance par défaut."""
    debut = "%d réserve%s de contrôle en retard au %s (échéance de levée passée" % (nombre, "s" if nombre > 1 else "", date)
    if not par_defaut:
        return debut + ")."
    if par_defaut == nombre:
        return debut + " ; échéance par défaut : 30 jours après le contrôle)."
    return debut + " ; dont %d à l'échéance par défaut : 30 jours après le contrôle)." % par_defaut


class CasRapport(CasNavigateur):

    def setUp(self):
        super().setUp()
        self.serveur = ServeurPrevo()
        self.serveur.demarrer()
        self.addCleanup(self.serveur.arreter)
        self.documents = Path(self.serveur.dossier) / "documents"

    def ouvrir(self, route="#/accueil"):
        preregler_profil(self.contexte, "responsable", "Responsable")
        self.page.goto(self.serveur.url + "/" + route)
        attendre_pret(self.page)

    def attendre(self, condition, delai_s=15):
        fin = time.time() + delai_s
        while time.time() < fin:
            if condition():
                return True
            time.sleep(0.2)
        return condition()

    def rapport(self, nom_demande):
        """Fichier du rapport figé demandé sous ce nom : le serveur l'enregistre sous « AAAAMMJJ-HHMMSS-<nom demandé> »
        (audit F4, T159) ; None tant qu'il n'est pas écrit."""
        if not self.documents.is_dir():
            return None
        return next((p for p in self.documents.iterdir() if re.fullmatch(r"\d{8}-\d{6}-" + re.escape(nom_demande), p.name)),
                    None)

    @staticmethod
    def nom_demande(nom):
        """Nom demandé d'un rapport enregistré (préfixe du serveur retiré)."""
        return re.sub(r"^\d{8}-\d{6}-", "", nom)

    def figer_depuis_l_accueil(self):
        self.page.wait_for_selector("#bandeau-rapport")
        self.page.click('#bandeau-rapport [data-action="figer-rapport"]')
        self.assertTrue(self.attendre(lambda: self.rapport(NOM) is not None), "rapport non écrit")
        self.assertTrue(self.attendre(lambda: self.rapport(NOM).name in (parametre(self.serveur.dossier, "rapports_mensuels") or "")))
        return self.rapport(NOM).read_text(encoding="utf-8")


class TestFiger(CasRapport):

    def test_figer_depuis_l_accueil_ecrit_le_document_la_liste_et_le_journal(self):
        self.ouvrir()
        self.assertIn(LIBELLE, self.page.inner_text("#bandeau-rapport"))
        self.assertEqual(self.page.locator("#bento > #bandeau-rapport").count(), 1)      # tuile de la grille (T90)
        # Rien n'est écrit sans clic
        self.assertIsNone(self.rapport(NOM))
        self.assertFalse(parametre(self.serveur.dossier, "rapports_mensuels"))
        contenu = self.figer_depuis_l_accueil()
        self.assertIn("Rapport mensuel de maintenance — " + LIBELLE, contenu)
        self.assertTrue(self.attendre(lambda: any("rapport mensuel figé : " + self.rapport(NOM).name in entree["action"]
                                                  for entree in lire_csv(self.serveur.dossier, "journal.csv"))))
        # La tuile ne revient pas : le mois est figé
        self.page.wait_for_function("!document.querySelector('#bandeau-rapport')")
        self.assertIsNone(self.page.evaluate("Rapport.moisAProposer(Donnees.aujourdhui())"))

    def test_plus_tard_masque_le_bandeau_sans_rien_ecrire(self):
        self.ouvrir()
        self.page.click('#bandeau-rapport [data-action="rapport-plus-tard"]')
        self.assertEqual(self.page.locator("#bandeau-rapport").count(), 0)
        self.page.evaluate("App.reafficher()")
        self.page.wait_for_selector("#contenu .accueil-instruments")
        self.assertEqual(self.page.locator("#bandeau-rapport").count(), 0)
        self.assertFalse(self.documents.exists() and any(self.documents.iterdir()))
        self.assertFalse(parametre(self.serveur.dossier, "rapports_mensuels"))


class TestContenu(CasRapport):

    def test_autonome_sans_script_ni_ressource_externe_une_page_a4_sans_erreur(self):
        self.ouvrir()
        contenu = self.figer_depuis_l_accueil()
        self.assertNotIn("<script", contenu.lower())
        self.assertNotRegex(contenu, r"\ssrc\s*=")
        self.assertEqual([lien for lien in re.findall(r'href="([^"]*)"', contenu) if not lien.startswith("mailto:")], [])
        self.assertNotIn("url(", contenu)
        self.assertNotIn("@import", contenu)
        self.assertIn("<svg", contenu)
        # Ouvert seul en file://, dans un dossier quelconque : aucune erreur, aucune requête réseau
        dossier = Path(tempfile.mkdtemp(prefix="rapport-prevo-"))
        self.addCleanup(shutil.rmtree, dossier, True)
        copie = dossier / NOM
        copie.write_text(contenu, encoding="utf-8")
        page = self.contexte.new_page()
        self.surveiller(page)
        requetes = []
        page.on("request", lambda requete: requetes.append(requete.url))
        page.goto(copie.resolve().as_uri())
        self.assertEqual([url for url in requetes if not url.startswith("file:")], [])
        self.assertEqual(len(requetes), 1, requetes)
        self.assertIn("Comprendre", page.inner_text("body"))
        pdf = page.pdf(prefer_css_page_size=True)
        self.assertEqual(len(re.findall(rb"/Type\s*/Page[^s]", pdf)), 1, "le rapport doit tenir sur une page A4")

    def test_tuiles_egales_aux_indicateurs_et_comparaisons(self):
        self.ouvrir()
        contenu = self.figer_depuis_l_accueil()
        attendu = self.page.evaluate("""(mois) => {
            const g = Indicateurs.global(Indicateurs.periodeDuMois(mois), {}, Donnees.aujourdhui());
            const pct = (v) => v === null ? 'non calculable' : UI.nombreFr(v * 100, 1) + ' %';
            const arret = Indicateurs.coutArret(Indicateurs.periodeDuMois(mois));
            return { disponibilite: pct(g.disponibilite.valeur), partPreventif: pct(g.partPreventif.valeur),
                     cout: g.cout.valeur === null ? 'non calculable' : UI.euro(g.cout.valeur, 0),
                     coutArret: arret.parEquipement.length || arret.complet ? UI.euro(arret.totalCentimes / 100, 2) : 'non chiffré',
                     n1Couvert: Rapport.interne.estCouvert(Rapport.interne.decalerMois(mois, -12)),
                     m1Couvert: Rapport.interne.estCouvert(Rapport.interne.decalerMois(mois, -1)) }; }""", MOIS)
        self.assertEqual(re.findall(r'<div class="tuile" data-cle="([^"]+)">', contenu),
                         ["disponibilite", "cout", "partPreventif", "coutArret"])
        for cle in ("disponibilite", "partPreventif", "cout", "coutArret"):
            with self.subTest(tuile=cle):
                bloc = re.search(r'<div class="tuile" data-cle="%s">(.*?)</div>\s*(?:<div class="tuile"|</section>)' % cle, contenu, re.S)
                self.assertIsNotNone(bloc, cle)
                self.assertIn(attendu[cle], bloc.group(1).replace("&nbsp;", "\u00A0"))
        self.assertTrue(attendu["m1Couvert"])
        if not attendu["n1Couvert"]:
            self.assertIn("non comparable avec " + libelle_mois(decaler_mois(MOIS, -12)), contenu)
        else:
            self.assertIn("par rapport à " + libelle_mois(decaler_mois(MOIS, -12)), contenu)
        for interdit in ("NaN", "Infinity", "undefined"):
            self.assertNotIn(interdit, contenu)

    def test_seuil_reparer_ou_remplacer_a_examiner_jamais_a_remplacer(self):
        ecrire_parametre(self.serveur.dossier, "seuil_remplacement_pct", "1")
        self.ouvrir()
        contenu = html.unescape(self.figer_depuis_l_accueil())
        self.assertIn("À examiner", contenu)
        self.assertIn("de sa valeur de remplacement", contenu)
        # Le texte des réserves citées (2.2, T421) est une donnée saisie (« … à remplacer avant la prochaine
        # inspection ») : la règle D44 porte sur les mots de Prévo, on le retire avant de chercher
        for reserve in lire_csv(self.serveur.dossier, "reserves_controle.csv"):
            contenu = contenu.replace(texte_court(brut(reserve["texte"])), "").replace(brut(reserve["texte"]), "")
        self.assertNotIn("à remplacer", contenu.lower())

    def test_reserves_en_retard_fait_marquant_et_decision(self):
        # 2.2 (T421, CS170) : les réserves en retard (calcul Python sur les CSV du serveur ; la démo : celle de RA-01,
        # sans échéance saisie) sont citées par un fait marquant et une décision, dans le document figé
        self.ouvrir()
        aujourdhui = datetime.date.fromisoformat(self.page.evaluate("Donnees.aujourdhui()"))
        reserves = reserves_en_retard(self.serveur.dossier, aujourdhui)
        self.assertTrue(reserves, "la démo doit avoir une réserve en retard")
        contenu = html.unescape(self.figer_depuis_l_accueil())
        par_defaut = sum(1 for _, defaut in reserves if defaut)
        self.assertIn("<li>%s</li>" % fait_reserves_attendu(len(reserves), par_defaut, aujourdhui.strftime("%d/%m/%Y")), contenu)
        lignes = {ligne["id"]: ligne for ligne in lire_csv(self.serveur.dossier, "reserves_controle.csv")}
        controles = {ligne["id"]: ligne for ligne in lire_csv(self.serveur.dossier, "controles_reglementaires.csv")}
        reperes = {ligne["id"]: ligne["repere"] for ligne in lire_csv(self.serveur.dossier, "equipements.csv")}
        citees = " ; ".join("%s (%s)" % (texte_court(brut(lignes[identifiant]["texte"])),
                                         brut(reperes[controles[lignes[identifiant]["controle_id"]]["equipement_id"]]))
                            for identifiant, _ in reserves[:3])
        debut = "Lever la réserve en retard : " if len(reserves) == 1 else "Lever les %d réserves en retard : " % len(reserves)
        self.assertIn("<li>%s%s.</li>" % (debut, citees), contenu)
        self.assertIn("(RA-01)", citees)
        # Trois faits et trois décisions au plus, comme avant la 2.2
        self.assertLessEqual(len(re.findall(r"<li>", contenu.split("Faits marquants")[1].split("</ul>")[0])), 3)
        self.assertLessEqual(len(re.findall(r"<li>", contenu.split("Décisions à prendre")[1].split("</ol>")[0])), 3)

    def test_lien_courriel_sans_piece_jointe(self):
        self.ouvrir()
        contenu = self.figer_depuis_l_accueil()
        liens = re.findall(r'href="(mailto:[^"]*)"', contenu)
        self.assertEqual(len(liens), 1)
        # Attribut HTML décodé : encodeURIComponent laisse l'apostrophe (« Coût de l'arrêt », 2.2), échappée en &#39;
        lien = html.unescape(liens[0])
        self.assertTrue(lien.startswith("mailto:?subject="))
        parametres = urllib.parse.parse_qs(lien[len("mailto:?"):])
        self.assertEqual(set(parametres), {"subject", "body"})
        self.assertIn(LIBELLE, parametres["subject"][0])
        self.assertIn("\r\n", parametres["body"][0])                       # RFC 6068 : CRLF
        self.assertNotIn("joint", parametres["body"][0])
        self.assertIn("Faits marquants", parametres["body"][0])
        self.assertIn("• Coût de l'arrêt : ", parametres["body"][0])                # 4ᵉ tuile (2.2, T472)
        self.assertLess(len(parametres["body"][0]), 1800)


class TestRevisions(CasRapport):

    def test_recalculer_cree_une_revision_sans_ecraser_et_onglet(self):
        self.ouvrir()
        premier = self.figer_depuis_l_accueil()
        nom = self.rapport(NOM).name
        # Après « figer », l'accueil est réaffiché (App.reafficher) et la tuile disparaît : l'attendre avant d'injecter
        # l'onglet, sinon ce réaffichage peut le remplacer sous la charge (T259 ; même attente que TestFiger).
        self.page.wait_for_function("!document.querySelector('#bandeau-rapport')")
        # Onglet « Rapports mensuels » affiché dans la page (indépendamment de l'écran Indicateurs)
        self.page.evaluate("Rapport.afficherOnglet(document.querySelector('#contenu'))")
        self.assertEqual(self.page.locator('.rapports-liste tr[data-nom="%s"]' % nom).count(), 1)
        self.page.click('.rapports-liste [data-action="recalculer"][data-mois="%s"]' % MOIS)
        # Révision « -r2 » malgré le préfixe du serveur (rapport-ecrans.js le retire pour compter les révisions)
        revision = "rapport-mensuel-%s-r2.html" % MOIS
        self.assertTrue(self.attendre(lambda: self.rapport(revision) is not None))
        self.assertEqual(self.rapport(NOM).read_text(encoding="utf-8"), premier)
        self.page.wait_for_selector('.rapports-liste tr[data-nom="%s"]' % self.rapport(revision).name)
        self.assertIn("figé", self.page.inner_text("#rapports-message"))
        self.assertEqual(parametre(self.serveur.dossier, "rapports_mensuels"), nom + "," + self.rapport(revision).name)
        # À 375 px, la liste des rapports défile dans son cadre, jamais la page (correction de relecture)
        self.page.set_viewport_size({"width": 375, "height": 812})
        self.page.evaluate("Rapport.afficherOnglet(document.querySelector('#contenu'))")
        largeur, visible = self.page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        self.assertLessEqual(largeur, visible + 1)

    def test_un_fichier_du_meme_nom_deja_sur_le_disque_n_est_jamais_ecrase(self):
        # Un rapport d'avant le lot 7 (sans préfixe) porte déjà le nom demandé : le serveur écrit le nouveau sous son
        # nom imposé (audit F4, T159), l'ancien reste intact et seul le nouveau entre dans rapports_mensuels.
        self.documents.mkdir(exist_ok=True)
        (self.documents / NOM).write_text("ANCIEN RAPPORT", encoding="utf-8")
        self.ouvrir()
        self.page.click('#bandeau-rapport [data-action="figer-rapport"]')
        self.assertTrue(self.attendre(lambda: self.rapport(NOM) is not None))
        self.assertEqual((self.documents / NOM).read_text(encoding="utf-8"), "ANCIEN RAPPORT")
        self.assertIn("Rapport mensuel de maintenance", self.rapport(NOM).read_text(encoding="utf-8"))
        self.assertTrue(self.attendre(lambda: parametre(self.serveur.dossier, "rapports_mensuels") == self.rapport(NOM).name))


class TestRapportReservesDemo(CasNavigateur):
    """Mode démo, horloge à la date de référence (2026-10-19 : dates non décalées), rapport de septembre 2026."""

    FAITS_JS = "() => Rapport.donnees('2026-09', Donnees.aujourdhui()).faits"
    DECISIONS_JS = "() => Rapport.donnees('2026-09', Donnees.aujourdhui()).decisions"

    def test_trois_faits_au_plus_les_reserves_passent_avant_la_repetition_des_pannes(self):
        self.contexte.clock.set_fixed_time("2026-10-19T09:00:00")
        preregler_profil(self.contexte, "responsable", "Responsable")
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        self.assertEqual(self.page.evaluate("Donnees.aujourdhui()"), "2026-10-19")
        avec = self.page.evaluate(self.FAITS_JS)
        decisions_avec = self.page.evaluate(self.DECISIONS_JS)
        # Le fait des réserves, en français (langue de l'installation), et dans la langue choisie pour le rapport (D156)
        reserve = fait_reserves_attendu(1, 1, "19/10/2026")
        self.assertEqual(avec[-1], reserve)
        anglais = self.page.evaluate("""async () => { await I18n.chargerLangue('en');
            return Rapport.donnees('2026-09', Donnees.aujourdhui(), '', 'en').faits; }""")
        self.assertEqual(anglais[-1], "1 inspection finding overdue on 19/10/2026 (clearing due date passed; "
                                      "default due date: 30 days after the inspection).")
        # La réserve levée : le rapport est celui d'avant la 2.2 (ici arrêt, pannes, contrôles en retard)
        self.page.evaluate("""async () => { for (const e of Controles.reservesEnRetard(Donnees.aujourdhui())) {
            await Controles.leverReserve(e.reserve.id, { date: Donnees.aujourdhui(), commentaire: 'Purgeur remplacé (test).' }); } }""")
        sans = self.page.evaluate(self.FAITS_JS)
        decisions_sans = self.page.evaluate(self.DECISIONS_JS)
        self.assertEqual(len(sans), 3)
        self.assertTrue(sans[0].startswith("Plus long arrêt"), sans)
        self.assertIn("pannes dans le mois", sans[1])
        self.assertIn("en retard au 19/10/2026", sans[2])
        self.assertNotIn(reserve, sans)
        # Avec la réserve : trois faits au plus ; la répétition des pannes sort, l'ordre des autres reste
        self.assertEqual(avec, [sans[0], sans[2], reserve])
        # Décisions : « Lever la réserve en retard » après les contrôles à planifier, trois au plus
        lever = "Lever la réserve en retard : Purgeur automatique du réservoir défectueux : à remplacer… (RA-01)."
        self.assertNotIn(lever, decisions_sans)
        self.assertEqual(len(decisions_avec), min(3, len(decisions_sans) + 1))
        self.assertEqual(decisions_avec.index(lever), 1 if decisions_sans[0].startswith("Planifier") else 0)
        self.assertEqual([d for d in decisions_avec if d != lever], decisions_sans[:len(decisions_avec) - 1])


class TestRapportDemo(CasNavigateur):

    def test_mode_demo_rapport_en_memoire_donc_dans_l_export(self):
        preregler_profil(self.contexte, "responsable", "Responsable")
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        mois = self.page.evaluate("Rapport.moisAProposer(Donnees.aujourdhui())")
        self.assertTrue(mois)
        self.page.click('#bandeau-rapport [data-action="figer-rapport"]')
        nom = "rapport-mensuel-%s.html" % mois
        self.page.wait_for_function("(nom) => App.adaptateur.documentsEnMemoire().some((d) => d.nom === nom)", arg=nom)
        texte = self.page.evaluate("""async (nom) => (await App.adaptateur.lireDocument(nom)).text()""", nom)
        self.assertIn("Rapport mensuel de maintenance", texte)
        self.assertNotIn("<script", texte.lower())


if __name__ == "__main__":
    unittest.main()
