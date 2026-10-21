"""Tests du rapport mensuel figé (tâche T51, ARCHITECTURE.md §15.10 ; CDC du lot 3, D43 à D45).

Mode serveur : un serveur.py neuf par test (copie du jeu de démo, dates non décalées), responsable ;
vérifications sur le disque (donnees/documents/, parametres.csv, journal.csv). Familles :
    figer       la tuile du rapport de l'accueil (#bandeau-rapport, grille « bento » depuis T90) propose
                le mois écoulé ; « Figer » écrit rapport-mensuel-AAAA-MM.html dans les documents,
                l'ajoute à rapports_mensuels et au journal ; rien n'est écrit sans clic ; « Plus tard »
                retire la tuile ;
    autonome    le fichier n'a ni <script> ni ressource externe (seul lien : mailto:), s'ouvre seul en
                file:// sans erreur ni requête réseau, et tient sur UNE page A4 imprimée (PDF) ;
    chiffres    tuiles = Indicateurs.global du mois ; comparaison à N-1 « non comparable » quand
                l'historique ne couvre pas ce mois ; décision « à examiner » au-delà du seuil
                (paramètre abaissé), jamais « à remplacer » ;
    revisions   « Recalculer » écrit -r2 sans toucher au premier ; un fichier du même nom déjà présent
                sur le disque n'est jamais écrasé (révision suivante) ;
    courriel    lien mailto: sans pièce jointe, objet et corps du résumé ;
    onglet      Rapport.afficherOnglet liste les rapports et recalcule ;
    demo        mode démo : rapport en mémoire (documentsEnMemoire, donc dans l'export ZIP).

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_rapport.py" -v
"""
import csv
import datetime
import io
import re
import shutil
import tempfile
import time
import unittest
import urllib.parse
from pathlib import Path

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, url_fichier

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
    return list(csv.DictReader(io.StringIO((Path(dossier) / nom).read_text(encoding="utf-8-sig")), delimiter=";"))


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

    def figer_depuis_l_accueil(self):
        self.page.wait_for_selector("#bandeau-rapport")
        self.page.click('#bandeau-rapport [data-action="figer-rapport"]')
        self.assertTrue(self.attendre(lambda: (self.documents / NOM).is_file()), "rapport non écrit")
        self.assertTrue(self.attendre(lambda: NOM in (parametre(self.serveur.dossier, "rapports_mensuels") or "")))
        return (self.documents / NOM).read_text(encoding="utf-8")


class TestFiger(CasRapport):

    def test_figer_depuis_l_accueil_ecrit_le_document_la_liste_et_le_journal(self):
        self.ouvrir()
        self.assertIn(LIBELLE, self.page.inner_text("#bandeau-rapport"))
        self.assertEqual(self.page.locator("#bento > #bandeau-rapport").count(), 1)      # tuile de la grille (T90)
        # Rien n'est écrit sans clic
        self.assertFalse((self.documents / NOM).exists())
        self.assertFalse(parametre(self.serveur.dossier, "rapports_mensuels"))
        contenu = self.figer_depuis_l_accueil()
        self.assertIn("Rapport mensuel de maintenance — " + LIBELLE, contenu)
        self.assertTrue(self.attendre(lambda: any("rapport mensuel figé : " + NOM in entree["action"]
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
            return { disponibilite: pct(g.disponibilite.valeur), partPreventif: pct(g.partPreventif.valeur),
                     cout: g.cout.valeur === null ? 'non calculable' : UI.euro(g.cout.valeur, 0),
                     n1Couvert: Rapport.interne.estCouvert(Rapport.interne.decalerMois(mois, -12)),
                     m1Couvert: Rapport.interne.estCouvert(Rapport.interne.decalerMois(mois, -1)) }; }""", MOIS)
        for cle in ("disponibilite", "partPreventif", "cout"):
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
        contenu = self.figer_depuis_l_accueil()
        self.assertIn("À examiner", contenu)
        self.assertIn("de sa valeur de remplacement", contenu)
        self.assertNotIn("à remplacer", contenu.lower())

    def test_lien_courriel_sans_piece_jointe(self):
        self.ouvrir()
        contenu = self.figer_depuis_l_accueil()
        liens = re.findall(r'href="(mailto:[^"]*)"', contenu)
        self.assertEqual(len(liens), 1)
        lien = liens[0].replace("&amp;", "&")
        self.assertTrue(lien.startswith("mailto:?subject="))
        parametres = urllib.parse.parse_qs(lien[len("mailto:?"):])
        self.assertEqual(set(parametres), {"subject", "body"})
        self.assertIn(LIBELLE, parametres["subject"][0])
        self.assertIn("\r\n", parametres["body"][0])                       # RFC 6068 : CRLF
        self.assertNotIn("joint", parametres["body"][0])
        self.assertIn("Faits marquants", parametres["body"][0])
        self.assertLess(len(parametres["body"][0]), 1800)


class TestRevisions(CasRapport):

    def test_recalculer_cree_une_revision_sans_ecraser_et_onglet(self):
        self.ouvrir()
        premier = self.figer_depuis_l_accueil()
        # Onglet « Rapports mensuels » affiché dans la page (indépendamment de l'écran Indicateurs)
        self.page.evaluate("Rapport.afficherOnglet(document.querySelector('#contenu'))")
        self.assertEqual(self.page.locator('.rapports-liste tr[data-nom="%s"]' % NOM).count(), 1)
        self.page.click('.rapports-liste [data-action="recalculer"][data-mois="%s"]' % MOIS)
        revision = "rapport-mensuel-%s-r2.html" % MOIS
        self.assertTrue(self.attendre(lambda: (self.documents / revision).is_file()))
        self.assertEqual((self.documents / NOM).read_text(encoding="utf-8"), premier)
        self.page.wait_for_selector('.rapports-liste tr[data-nom="%s"]' % revision)
        self.assertIn("figé", self.page.inner_text("#rapports-message"))
        self.assertEqual(parametre(self.serveur.dossier, "rapports_mensuels"), NOM + "," + revision)
        # À 375 px, la liste des rapports défile dans son cadre, jamais la page (correction de relecture)
        self.page.set_viewport_size({"width": 375, "height": 812})
        self.page.evaluate("Rapport.afficherOnglet(document.querySelector('#contenu'))")
        largeur, visible = self.page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        self.assertLessEqual(largeur, visible + 1)

    def test_un_fichier_du_meme_nom_deja_sur_le_disque_n_est_jamais_ecrase(self):
        self.autoriser_erreur("409")
        self.documents.mkdir(exist_ok=True)
        (self.documents / NOM).write_text("ANCIEN RAPPORT", encoding="utf-8")
        self.ouvrir()
        self.page.click('#bandeau-rapport [data-action="figer-rapport"]')
        revision = "rapport-mensuel-%s-r2.html" % MOIS
        self.assertTrue(self.attendre(lambda: (self.documents / revision).is_file()))
        self.assertEqual((self.documents / NOM).read_text(encoding="utf-8"), "ANCIEN RAPPORT")
        self.assertTrue(self.attendre(lambda: parametre(self.serveur.dossier, "rapports_mensuels") == revision))


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
