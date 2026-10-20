"""Tests de l'accueil et de la coque, lot 2 (tâche T32, ARCHITECTURE.md §14.6, D31, D32).

Toujours serveur.py sur une copie du jeu de démo (ServeurPrevo), profil responsable sauf mention.
Familles (le nom du test le dit) :
    compteurs  : « Préventifs de la semaine » et « Articles à commander » = calcul Python sur les CSV
                 du serveur APRÈS le chargement (la génération du préventif a eu lieu ; semaine
                 calculée depuis la date du jour réelle) ; liens vers le calendrier du préventif et
                 l'onglet « À commander » du magasin ; technicien : ses préventifs de la semaine dans
                 sa liste d'OT, ou la mention qu'il n'en a pas ;
    telephone  : contexte 375 × 812 « is_mobile » → pas de carte « Connecter un téléphone » (D31),
                 aucun défilement horizontal, zones tactiles d'au moins 48 px ; 1440 px → carte présente ;
    menu       : entreprise_nom long (≈ 60 caractères) écrit dans parametres.csv → à 1440 px le nom
                 tient sur deux lignes (ni une seule coupée, ni plus de deux), infobulle = nom complet ;
                 menu replié : rien ne déborde ; 375 px : aucun défilement horizontal (D32).

Aucun numéro d'OT, de DI, de mouvement ou d'achat écrit en dur. Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_accueil_lot2.py" -v
"""
import csv
import datetime
import io
import unittest
from pathlib import Path

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil

STATUTS_FERMES = ("Clôturé techniquement", "Clôturé administrativement", "Annulé")
LIEN_PREVENTIFS = "#/preventif?onglet=calendrier"
LIEN_ARTICLES = "#/magasin?onglet=a-commander"
# 62 caractères : bien plus que la largeur du menu latéral sur une ligne.
NOM_LONG = "Société Industrielle de Maintenance des Trois Vallées et Annexes"

# Même contrôle que tests/test_recette_lot1.py (PETITES_ZONES_JS) ; recopié ici : importer ce
# fichier de test ferait aussi lancer ses tests.
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

DEBORDEMENT_JS = """(selecteur) => { const e = document.querySelector(selecteur);
    return e ? [e.scrollWidth, e.clientWidth] : null; }"""


# ---------------------------------------------------------------------------
# Lecture et écriture des CSV sur le disque (comme un autre poste ou Excel)
# ---------------------------------------------------------------------------

def lire_csv(dossier, nom):
    """Lignes (dictionnaires) d'un CSV de Prévo sur le disque (UTF-8 avec BOM, « ; »)."""
    texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte), delimiter=";"))


def brut(valeur):
    """Valeur sans l'apostrophe de protection (ARCHITECTURE.md §3.2)."""
    return valeur[1:] if valeur.startswith("'") else valeur


def nombre_ou_none(valeur):
    texte = brut(valeur or "").strip().replace(",", ".")
    try:
        return float(texte) if texte else None
    except ValueError:
        return None


def ecrire_parametre(dossier, cle, valeur):
    """Remplace (ou ajoute) une clé de parametres.csv, au format de Prévo (BOM, « ; », CRLF)."""
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


def dimanche_de(jour):
    """Dimanche de la semaine (du lundi au dimanche) de la date donnée."""
    return jour + datetime.timedelta(days=6 - jour.weekday())


def preventifs_de_la_semaine(dossier, jour):
    """OT d'origine « préventif », ni clôturés ni annulés, date prévue ≤ dimanche (retards compris)."""
    dimanche = dimanche_de(jour).isoformat()
    return [ot for ot in lire_csv(dossier, "ordres_travail.csv")
            if ot["origine"] == "préventif" and ot["statut"] not in STATUTS_FERMES
            and ot["date_prevue"] and ot["date_prevue"][:10] <= dimanche]


def stock_python(mouvements, article_id):
    """Stock recalculé (date puis identifiant) : un inventaire fixe la valeur, entrée et retour
    ajoutent, une sortie retire (comme Donnees.stockArticle)."""
    stock = 0.0
    for mouvement in sorted((m for m in mouvements if m["article_id"] == article_id), key=lambda m: (m["date"], m["id"])):
        quantite = nombre_ou_none(mouvement["quantite"]) or 0.0
        if mouvement["type"] == "inventaire":
            stock = quantite
        elif mouvement["type"] in ("entrée", "retour"):
            stock += quantite
        elif mouvement["type"] == "sortie":
            stock -= quantite
    return round(stock, 6)


def articles_a_commander(dossier):
    """Articles actifs dont le point de commande est renseigné et le stock ≤ point de commande."""
    mouvements = lire_csv(dossier, "mouvements_stock.csv")
    resultat = []
    for article in lire_csv(dossier, "articles.csv"):
        point = nombre_ou_none(article["point_commande"])
        if brut(article["actif"]) == "0" or point is None:
            continue
        if stock_python(mouvements, article["id"]) <= point:
            resultat.append(article["id"])
    return resultat


# ---------------------------------------------------------------------------
# Outils communs des tests
# ---------------------------------------------------------------------------

class CasAccueil(CasNavigateur):

    def ouvrir(self, serveur, profil="responsable", largeur=1440, hauteur=900, page=None, contexte=None, **options):
        page = page or self.page
        page.set_viewport_size({"width": largeur, "height": hauteur})
        preregler_profil(contexte or self.contexte, profil, **options)
        page.goto(serveur.url + "/#/accueil")
        attendre_pret(page)
        page.wait_for_load_state("networkidle")      # écritures du démarrage (format, préventif) finies
        page.wait_for_selector("#contenu h1")
        return page

    def chiffre(self, lien):
        return int(self.page.inner_text('#contenu .instruments a[href="%s"] .chiffre' % lien))

    def sans_defilement_horizontal(self, page, contexte):
        largeurs = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        self.assertLessEqual(largeurs[0], largeurs[1], "défilement horizontal (%s) : %r" % (contexte, largeurs))


# ---------------------------------------------------------------------------
# compteurs
# ---------------------------------------------------------------------------

class TestCompteurs(CasAccueil):

    def test_compteurs_preventifs_de_la_semaine_et_articles_a_commander_egaux_au_calcul_python(self):
        with ServeurPrevo() as serveur:
            page = self.ouvrir(serveur)
            # Lus APRÈS le chargement : les OT préventifs générés à l'ouverture comptent.
            jour = datetime.date.today()
            self.assertEqual(page.evaluate("Donnees.aujourdhui()"), jour.isoformat())
            preventifs = preventifs_de_la_semaine(serveur.dossier, jour)
            articles = articles_a_commander(serveur.dossier)
            # Le jeu de démo a de quoi remplir les deux indicateurs (sinon ce test ne prouverait rien).
            self.assertGreater(len(preventifs), 0)
            self.assertGreater(len(articles), 0)

            self.assertEqual(self.chiffre(LIEN_PREVENTIFS), len(preventifs))
            self.assertEqual(self.chiffre(LIEN_ARTICLES), len(articles))
            calcul = page.evaluate("""() => { const c = Accueil.calculerCompteurs();
                return { preventifs: c.preventifsSemaine.map((ot) => ot.id), articles: c.articlesACommander.map((a) => a.article.id) }; }""")
            self.assertEqual(sorted(calcul["preventifs"]), sorted(ot["id"] for ot in preventifs))
            self.assertEqual(sorted(calcul["articles"]), sorted(articles))
            self.assertEqual(page.evaluate("Accueil.dimancheDe(%r)" % jour.isoformat()), dimanche_de(jour).isoformat())
            # Les cinq indicateurs des lots 1 et 2 (les deux du lot 3 s'y ajoutent : test_accueil_lot3).
            for lien in ("#/di?statut=Nouvelle", "#/ot?filtre=retard", "#/ot?filtre=p1", LIEN_PREVENTIFS, LIEN_ARTICLES):
                self.assertEqual(page.locator('#contenu .instruments > a[href="%s"]' % lien).count(), 1, lien)
            self.assertEqual(page.locator("#contenu .instruments > a").count(), 7)
            self.assertIn("Préventifs de la semaine", page.inner_text('#contenu .instruments a[href="%s"]' % LIEN_PREVENTIFS))
            self.assertIn("Articles à commander", page.inner_text('#contenu .instruments a[href="%s"]' % LIEN_ARTICLES))

            # Les liens mènent aux bons écrans.
            page.click('#contenu .instruments a[href="%s"]' % LIEN_PREVENTIFS)
            page.wait_for_function("lien => location.hash === lien", arg=LIEN_PREVENTIFS)
            page.wait_for_selector(".pv-calendrier")
            page.evaluate("location.hash = '#/accueil'")
            page.wait_for_selector('#contenu .instruments a[href="%s"]' % LIEN_ARTICLES)
            page.click('#contenu .instruments a[href="%s"]' % LIEN_ARTICLES)
            page.wait_for_function("lien => location.hash === lien", arg=LIEN_ARTICLES)
            page.wait_for_selector(".magasin-a-commander")
            page.wait_for_load_state("networkidle")

    def test_compteurs_technicien_ses_preventifs_de_la_semaine_dans_sa_liste_puis_mention_si_vide(self):
        with ServeurPrevo() as serveur:
            # Un technicien actif qui n'a aucun préventif de la semaine (les OT générés à l'ouverture
            # ne sont affectés à personne : le choix fait avant l'ouverture reste juste après).
            jour = datetime.date.today()
            avec_preventif = {ot["technicien_id"] for ot in preventifs_de_la_semaine(serveur.dossier, jour)}
            technicien = next(t["id"] for t in lire_csv(serveur.dossier, "techniciens.csv")
                              if brut(t["actif"]) != "0" and t["id"] not in avec_preventif)
            page = self.ouvrir(serveur, profil="technicien", technicien_id=technicien)
            self.assertEqual(page.locator("#contenu .accueil-preventifs > li").count(), 0)
            self.assertIn("Aucun préventif", page.inner_text("#contenu .accueil-preventifs-vide"))
            # Chaque OT ouvert du technicien apparaît une seule fois dans la carte.
            ouverts = sorted(ot["id"] for ot in lire_csv(serveur.dossier, "ordres_travail.csv")
                             if ot["technicien_id"] == technicien and ot["statut"] not in STATUTS_FERMES)
            cartes = page.eval_on_selector_all("#contenu .accueil-mes-ordres .liste-cartes > li b:first-child",
                                               "els => els.map((e) => e.textContent.trim())")
            self.assertEqual(len(cartes), len(set(cartes)))
            self.assertTrue(set(cartes) <= set(ouverts), cartes)
            if len(ouverts) <= 15:
                self.assertEqual(sorted(cartes), ouverts)

            # On lui affecte un préventif de la semaine (comme le ferait le responsable sur un autre poste).
            candidat = next((ot for ot in preventifs_de_la_semaine(serveur.dossier, jour) if ot["technicien_id"] != technicien), None)
            self.assertIsNotNone(candidat, "aucun OT préventif de la semaine à affecter")
            page.evaluate("""([id, tech]) => Donnees.modifier('ordres_travail', (lignes) => {
                lignes.find((l) => l.id === id).technicien_id = tech; })""", [candidat["id"], technicien])
            page.evaluate("App.reafficher()")
            page.wait_for_function("id => [...document.querySelectorAll('#contenu .accueil-preventifs > li b')].some((b) => b.textContent.trim() === id)",
                                   arg=candidat["id"])
            self.assertEqual(page.locator("#contenu .accueil-preventifs-vide").count(), 0)
            # Il n'est pas répété dans « Autres ordres de travail ».
            self.assertEqual(page.locator("#contenu .accueil-mes-ordres .liste-cartes > li a[href='#/ot/%s']" % candidat["id"]).count(), 1)
            page.wait_for_load_state("networkidle")


# ---------------------------------------------------------------------------
# telephone : carte « Connecter un téléphone » (D31)
# ---------------------------------------------------------------------------

class TestTelephone(CasAccueil):

    def test_telephone_pas_de_carte_qr_sur_un_telephone_presente_a_1440_px(self):
        with ServeurPrevo() as serveur:
            contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 375, "height": 812},
                                                   is_mobile=True, has_touch=True, device_scale_factor=2)
            try:
                telephone = contexte.new_page()
                self.surveiller(telephone)
                self.ouvrir(serveur, largeur=375, hauteur=812, page=telephone, contexte=contexte)
                telephone.wait_for_selector("#contenu .instruments")
                self.assertTrue(telephone.evaluate("UI.estTelephone()"))
                self.assertEqual(telephone.locator("#carte-connexion").count(), 0)
                self.sans_defilement_horizontal(telephone, "accueil, téléphone 375 px")
                self.assertEqual(telephone.evaluate(PETITES_ZONES_JS), [])
            finally:
                contexte.close()

            page = self.ouvrir(serveur)
            page.wait_for_selector("#carte-connexion", state="visible")
            self.assertIn("Connecter un téléphone", page.inner_text("#carte-connexion"))


# ---------------------------------------------------------------------------
# menu : nom de l'entreprise sur deux lignes au plus (D32)
# ---------------------------------------------------------------------------

class TestMenu(CasAccueil):

    MESURE_NOM_JS = """() => { const e = document.getElementById('nom-entreprise'); const s = getComputedStyle(e);
        return { hauteur: e.getBoundingClientRect().height, interligne: parseFloat(s.lineHeight),
                 texte: e.textContent, titre: e.title, visible: e.offsetParent !== null, blanc: s.whiteSpace }; }"""

    def test_menu_nom_long_sur_deux_lignes_avec_infobulle_menu_replie_et_telephone_sans_debordement(self):
        self.assertGreaterEqual(len(NOM_LONG), 60)
        with ServeurPrevo() as serveur:
            ecrire_parametre(serveur.dossier, "entreprise_nom", NOM_LONG)
            page = self.ouvrir(serveur)

            # « GMAO » puis le nom de l'entreprise, sur deux lignes : ni coupé après la première,
            # ni plus de deux ; le nom complet est en infobulle.
            self.assertEqual(page.inner_text(".menu-tete .titre small").strip().upper(), "GMAO")
            mesure = page.evaluate(self.MESURE_NOM_JS)
            self.assertTrue(mesure["visible"], mesure)
            self.assertEqual(mesure["texte"], NOM_LONG)
            self.assertEqual(mesure["titre"], NOM_LONG)
            self.assertNotEqual(mesure["blanc"], "nowrap")
            self.assertGreaterEqual(mesure["hauteur"], 2 * mesure["interligne"] - 1, mesure)
            self.assertLessEqual(mesure["hauteur"], 2 * mesure["interligne"] + 1, mesure)
            # Rien ne déborde du menu ; le nom reste à gauche du bouton « Replier ».
            largeurs = page.evaluate(DEBORDEMENT_JS, ".menu-lateral")
            self.assertLessEqual(largeurs[0], largeurs[1], "menu déplié : %r" % (largeurs,))
            droite_nom = page.evaluate("document.getElementById('nom-entreprise').getBoundingClientRect().right")
            gauche_bouton = page.evaluate("document.getElementById('btn-replier').getBoundingClientRect().left")
            self.assertLessEqual(droite_nom, gauche_bouton + 0.5)
            self.sans_defilement_horizontal(page, "1440 px, menu déplié")

            # Menu replié : le nom est masqué, rien ne déborde.
            page.click("#btn-replier")
            page.wait_for_function("document.getElementById('app').classList.contains('replie')")
            self.assertFalse(page.is_visible("#nom-entreprise"))
            largeurs = page.evaluate(DEBORDEMENT_JS, ".menu-lateral")
            self.assertLessEqual(largeurs[0], largeurs[1], "menu replié : %r" % (largeurs,))
            self.sans_defilement_horizontal(page, "1440 px, menu replié")
            page.click("#btn-replier")
            page.wait_for_function("!document.getElementById('app').classList.contains('replie')")

            # Téléphone : en-tête mobile, aucun défilement horizontal.
            page.set_viewport_size({"width": 375, "height": 812})
            page.wait_for_selector(".entete-mobile", state="visible")
            self.sans_defilement_horizontal(page, "375 px")
            largeurs = page.evaluate(DEBORDEMENT_JS, ".entete-mobile")
            self.assertLessEqual(largeurs[0], largeurs[1], "en-tête mobile : %r" % (largeurs,))

    def test_menu_sans_nom_d_entreprise_seulement_gmao(self):
        with ServeurPrevo() as serveur:
            ecrire_parametre(serveur.dossier, "entreprise_nom", "")
            page = self.ouvrir(serveur)
            self.assertEqual(page.inner_text(".menu-tete .titre small").strip().upper(), "GMAO")
            self.assertFalse(page.is_visible("#nom-entreprise"))
            self.assertEqual(page.evaluate("document.getElementById('nom-entreprise').textContent"), "")


if __name__ == "__main__":
    unittest.main()
