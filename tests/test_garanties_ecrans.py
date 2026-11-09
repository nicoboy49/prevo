"""Tests de l'écran « Garanties et contrats », 2.2 (garanties-ecrans.js, T456 ; CDC §3.4, D182, D187, D190, CS173,
CS175 ; conception L4 §2.3 ; QUESTIONS-L2-L6, L4-L6 Q1, Q3, Q6, Q12).

Sans navigateur (TestTextes) : la phrase D182 est la valeur de garanties.principe.texte, la même que
controles.principe.texte dans les cinq langues ; aucune valeur de la section garanties ne dit « conforme » (fr) ni
« compliant » (en).
Serveur Prévo sur une copie du jeu de démo (ServeurPrevo), horloge du navigateur figée (jamais la date réelle) ;
garanties et contrats écrits dans les CSV de la copie (identifiants GAR-09xx, CTP-09xx), relus sur le disque après
chaque écriture. Familles (le nom du test le dit) :
    liste       : vides expliqués, menu du responsable, phrase D182 ; CS173 (fin 31/12/2026, préavis 3 mois) :
                  « à décider » le 01/08/2026, « en cours » le 31/07/2026 ; compteurs, onglet et filtres dans
                  l'adresse ; lignes retirées absentes ; total des montants avec les contrats sans montant à part ;
    fiche       : contrat à décider (bandeau, « Écrire au prestataire » en mailto:, équipement introuvable,
                  Reconduire, Noter la résiliation, Retirer, historique) ; garantie (fournisseur en tel: et
                  mailto:, document, création par le formulaire puis la fiche, Retirer, introuvable) ;
    profils     : technicien et demandeur : pas d'entrée de menu, adresses refusées ;
    telephone   : 375 px : cartes, aucun défilement horizontal, zones tactiles de 48 px.
Aucun écran ne dit « conforme ».

Lancer depuis la racine du projet (au travers du verrou des navigateurs) :
    py -X utf8 -m unittest discover -s tests -p "test_garanties_ecrans.py" -v
"""
import csv
import io
import re
import sys
import unittest
from pathlib import Path
from urllib.parse import unquote

from commun import RACINE, CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil

if str(RACINE / "outils") not in sys.path:
    sys.path.insert(0, str(RACINE / "outils"))
import textes_langues  # noqa: E402  (lecture des dictionnaires, celle de outils/controler_textes.py)
from jslex import decoder  # noqa: E402

PHRASE = "Prévo est une aide au suivi ; la responsabilité reste celle de l'employeur."
MOT_CONFORME = re.compile(r"(?<![\w-])conformes?(?![\w-])", re.IGNORECASE)
MOT_COMPLIANT = re.compile(r"(?<![\w-])compliant(?![\w-])", re.IGNORECASE)
LANGUES = ["fr", "en", "tr", "it", "pt-PT"]
PDF = b"%PDF-1.4\n% certificat de test (T456)\n%%EOF\n"
ESPACES = {0xA0: " ", 0x202F: " "}


def lire_csv(dossier, nom):
    texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte, newline=""), delimiter=";"))


def brut(valeur):
    valeur = (valeur or "").strip()
    return valeur[1:] if valeur.startswith("'") else valeur


def lignes(dossier, nom):
    return [{cle: brut(v) for cle, v in ligne.items()} for ligne in lire_csv(dossier, nom)]


def journal(dossier, table, identifiant):
    return [e["action"] for e in lire_csv(dossier, "journal.csv") if e["table"] == table and e["id_ligne"] == identifiant]


def ajouter_ligne_csv(chemin, valeurs):
    """Ajoute une ligne au CSV (en-tête du fichier, « ; », CRLF), comme l'écrit Prévo."""
    texte = chemin.read_text(encoding="utf-8-sig")
    entete = next(csv.reader(io.StringIO(texte), delimiter=";"))
    sortie = io.StringIO()
    csv.writer(sortie, delimiter=";", lineterminator="\r\n").writerow([valeurs.get(c, "") for c in entete])
    if not texte.endswith("\n"):
        texte += "\r\n"
    chemin.write_text(texte + sortie.getvalue(), encoding="utf-8-sig", newline="")


def valeurs_langue(code):
    entrees = textes_langues.Langue(code, RACINE, textes_langues.fichiers_de(code)).entrees
    return {cle: [decoder(b) for b in (v.values() if isinstance(v, dict) else [v])] for cle, (_, v, _) in entrees.items()}


def vider_garanties_et_contrats(dossier):
    """La copie de la démo porte ses garanties et ses contrats (T460) : le test part de ces deux tables vides (la
    ligne d'en-tête gardée à l'octet près)."""
    for nom in ("garanties.csv", "contrats_prestataires.csv"):
        chemin = Path(dossier) / nom
        octets = chemin.read_bytes()
        chemin.write_bytes(octets[:octets.index(b"\n") + 1])


def jeu(dossier):
    """Garanties et contrats du test (01/08/2026, délai 60 jours), seuls dans leurs tables ; renvoie (équipements,
    fournisseurs)."""
    vider_garanties_et_contrats(dossier)
    equipements = [e for e in lignes(dossier, "equipements.csv") if e.get("actif") != "0"][:3]
    fournisseurs = lignes(dossier, "fournisseurs.csv")[:2]
    eq = [e["id"] for e in equipements]
    f1, f2 = fournisseurs[0]["id"], fournisseurs[1]["id"]
    for valeurs in (
            {"id": "GAR-0901", "equipement_id": eq[0], "fournisseur_id": f1, "date_debut": "2025-04-01",
             "date_fin": "2027-03-31", "conditions": "Pièces et main-d'œuvre", "actif": "1"},
            {"id": "GAR-0902", "equipement_id": eq[1], "fournisseur_id": f2, "date_fin": "2026-09-15", "actif": "1"},
            {"id": "GAR-0903", "equipement_id": eq[2], "date_fin": "2026-05-31", "actif": "1"},
            {"id": "GAR-0904", "equipement_id": eq[2], "date_fin": "2027-12-31", "actif": "0"}):
        ajouter_ligne_csv(dossier / "garanties.csv", valeurs)
    for valeurs in (
            {"id": "CTP-0901", "fournisseur_id": f1, "objet": "Maintenance des compresseurs",
             "equipement_ids": eq[0] + ";EQ-9999", "date_debut": "2026-01-01", "date_fin": "2026-12-31",
             "preavis_mois": "3", "reconduction_tacite": "1", "reconduction_mois": "12", "montant_annuel": "1200",
             "actif": "1"},
            {"id": "CTP-0902", "fournisseur_id": f2, "objet": "Nettoyage des filtres", "date_fin": "2027-06-30",
             "reconduction_tacite": "0", "actif": "1"},
            {"id": "CTP-0903", "fournisseur_id": f2, "objet": "Vérification des extincteurs", "date_fin": "2026-03-31",
             "reconduction_tacite": "0", "montant_annuel": "500", "actif": "1"},
            {"id": "CTP-0904", "fournisseur_id": f1, "objet": "Entretien des portes", "date_fin": "2026-06-30",
             "reconduction_tacite": "1", "montant_annuel": "300", "actif": "1"},
            {"id": "CTP-0905", "fournisseur_id": f1, "objet": "Contrat retiré", "date_fin": "2027-12-31",
             "montant_annuel": "999", "actif": "0"}):
        ajouter_ligne_csv(dossier / "contrats_prestataires.csv", valeurs)
    return equipements, fournisseurs


class TestTextes(unittest.TestCase):

    def test_phrase_d182_dans_les_cinq_langues_sans_conforme(self):
        for code in LANGUES:
            with self.subTest(langue=code):
                valeurs = valeurs_langue(code)
                self.assertEqual(valeurs["garanties.principe.texte"], valeurs["controles.principe.texte"])
        francais = valeurs_langue("fr")
        self.assertEqual(francais["garanties.principe.texte"], [PHRASE])
        section = {cle: v for cle, v in francais.items() if cle.startswith("garanties.")}
        self.assertGreater(len(section), 150)
        self.assertEqual([c for c, v in section.items() if any(MOT_CONFORME.search(t) for t in v)], [])
        anglais = {c: v for c, v in valeurs_langue("en").items() if c.startswith("garanties.")}
        self.assertEqual([c for c, v in anglais.items() if any(MOT_COMPLIANT.search(t) for t in v)], [])
        source = (RACINE / "js" / "modules" / "garanties-ecrans.js").read_text(encoding="utf-8")
        self.assertIn("App.ecran", source)
        self.assertIn("mailto:", source)


class CasEcrans(CasNavigateur):

    def ouvrir(self, serveur, route, profil="responsable", technicien_id="", jour="2026-08-01", largeur=1280):
        self.contexte.clock.set_fixed_time(jour + "T09:00:00")
        self.page.set_viewport_size({"width": largeur, "height": 900})
        preregler_profil(self.contexte, profil, nom="Demandeur test" if profil == "demandeur" else "",
                         technicien_id=technicien_id)
        self.page.goto(serveur.url + "/" + route)
        attendre_pret(self.page)
        self.page.wait_for_load_state("networkidle")

    def nouveau_contexte(self):
        self.page.close()
        self.contexte.close()
        self.contexte = self.navigateur.new_context(locale="fr-FR")
        self.contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        self.page = self.contexte.new_page()
        self.surveiller(self.page)

    def aller(self, route, selecteur):
        self.page.evaluate("(route) => { location.hash = route; }", route)
        self.page.wait_for_selector(selecteur)

    def texte(self, selecteur):
        return self.page.inner_text(selecteur).translate(ESPACES)

    def attendre_toast(self, morceau):
        self.page.wait_for_function(
            "(texte) => document.getElementById('toast').textContent.includes(texte)", arg=morceau)

    def attendre_ligne(self, dossier, nom, condition):
        for _ in range(100):
            trouvees = [ligne for ligne in lignes(dossier, nom) if condition(ligne)]
            if trouvees:
                return trouvees[-1]
            self.page.wait_for_timeout(100)
        self.fail("aucune ligne attendue dans " + nom)

    def statuts(self):
        """{ identifiant de la ligne : code du statut } des lignes affichées (liens vers les fiches)."""
        return self.page.evaluate("""() => Object.fromEntries(Array.from(document.querySelectorAll(
            '.garanties-liste tbody tr, .garanties-liste .liste-cartes li')).map((ligne) => [
            decodeURIComponent(ligne.querySelector('a.garanties-lien').getAttribute('href').split('/').pop()),
            ligne.querySelector('[data-statut]').dataset.statut]))""")

    def compteurs(self):
        return self.page.evaluate("""() => Object.fromEntries(Array.from(document.querySelectorAll(
            '.garanties-compteurs a')).map((a) => [a.dataset.compteur, Number(a.querySelector('.chiffre').textContent)]))""")

    def sans_conforme(self):
        self.assertIsNone(MOT_CONFORME.search(self.page.inner_text("#contenu")))

    def sans_defilement(self, contexte):
        largeurs = self.page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        self.assertLessEqual(largeurs[0], largeurs[1], "défilement horizontal (%s) : %r" % (contexte, largeurs))


# ---------------------------------------------------------------------------
# Liste #/garanties
# ---------------------------------------------------------------------------

class TestListe(CasEcrans):

    def test_liste_vides_expliques_menu_et_phrase(self):
        page = self.page
        with ServeurPrevo() as serveur:
            vider_garanties_et_contrats(serveur.dossier)
            self.ouvrir(serveur, "#/garanties")
            page.wait_for_selector(".garanties-ecran")
            self.assertEqual(page.inner_text("#menu a[data-ecran='garanties'] .libelle"), "Garanties et contrats")
            self.assertEqual(page.inner_text(".garanties-ecran h1"), "Garanties et contrats")
            self.assertEqual(page.inner_text(".garanties-ecran .entete-page .garanties-principe"), PHRASE)
            self.assertEqual(page.get_attribute("#garanties-nouvelle", "href"), "#/garanties/garantie/nouvelle")
            self.assertEqual(page.get_attribute("#garanties-nouveau-contrat", "href"), "#/garanties/contrat/nouveau")
            self.assertEqual(self.compteurs(), {"sous-garantie": 0, "bientot": 0, "a-decider": 0, "a-mettre-a-jour": 0})
            self.assertIn("Finissent sous 60 jours", page.inner_text(".garanties-compteurs"))
            panneau = ".panneau-onglet[data-onglet='garanties']"
            self.assertIn("Aucune garantie enregistrée.", page.inner_text(panneau + " .vide"))
            self.assertIn("Prévo vous préviendra avant sa fin.", page.inner_text(panneau + " .vide"))
            page.click(".garanties-onglets .onglet[data-onglet='contrats']")
            self.assertEqual(page.evaluate("location.hash"), "#/garanties?onglet=contrats")
            self.assertIn("Aucun contrat enregistré.", page.inner_text(".panneau-onglet[data-onglet='contrats'] .vide"))
            self.assertIn("la date limite pour le résilier", page.inner_text(".panneau-onglet[data-onglet='contrats'] .vide"))
            self.sans_conforme()

    def test_liste_cs173_a_decider_compteurs_filtres_total(self):
        page = self.page
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            _, fournisseurs = jeu(dossier)
            self.ouvrir(serveur, "#/garanties")
            page.wait_for_selector(".garanties-liste")
            # Lignes retirées absentes ; garanties : ce qui finit bientôt d'abord
            self.assertEqual(self.statuts(), {"GAR-0902": "bientot", "GAR-0901": "en_cours", "GAR-0903": "terminee"})
            self.assertEqual(self.compteurs(), {"sous-garantie": 2, "bientot": 1, "a-decider": 1, "a-mettre-a-jour": 1})
            self.assertEqual(page.inner_text(".panneau-onglet[data-onglet='garanties'] .garanties-nombre"), "3 garanties sur 3")
            premiere = self.texte(".garanties-liste tbody tr:first-child")
            self.assertIn("se termine bientôt", premiere)
            self.assertIn("se termine dans 45 jours, le 15/09/2026", premiere)

            # Compteur « Contrats à décider » : onglet et filtre dans l'adresse ; CS173 « à décider » le 01/08/2026
            page.click(".garanties-compteurs a[data-compteur='a-decider']")
            page.wait_for_function("location.hash === '#/garanties?onglet=contrats&filtre=a-decider'")
            page.wait_for_selector(".panneau-onglet[data-onglet='contrats']:not([hidden]) .garanties-liste tbody tr")
            self.assertEqual(self.statuts(), {"CTP-0901": "a_decider"})
            ligne = self.texte(".garanties-liste tbody tr")
            self.assertIn("à décider", ligne)
            self.assertIn("à résilier au plus tard le 30/09/2026 (dans 60 jours), sinon il est reconduit le 31/12/2026", ligne)
            self.assertIn("30/09/2026", ligne)
            self.assertIn("1 200,00 €", ligne)
            self.assertIn("Filtre appliqué", page.inner_text(".garanties-compteurs a[data-compteur='a-decider']"))
            # Total : contrats en cours seulement (pas le terminé, pas le retiré), sans montant comptés à part
            self.assertEqual(self.texte(".garanties-total"),
                             "Total des contrats en cours : 1 500,00 € par an — 1 contrat sans montant.")

            # Filtres : tous les statuts, puis un prestataire ; l'adresse les garde
            page.select_option(".panneau-onglet[data-onglet='contrats'] select[name=filtre]", "")
            self.assertEqual(self.statuts(), {"CTP-0901": "a_decider", "CTP-0904": "a_mettre_a_jour",
                                              "CTP-0902": "en_cours", "CTP-0903": "termine"})
            page.select_option(".panneau-onglet[data-onglet='contrats'] select[name=fournisseur]", fournisseurs[1]["id"])
            self.assertEqual(set(self.statuts()), {"CTP-0902", "CTP-0903"})
            self.assertEqual(page.evaluate("location.hash"),
                             "#/garanties?onglet=contrats&fournisseur=" + fournisseurs[1]["id"])
            page.fill(".panneau-onglet[data-onglet='contrats'] input[name=recherche]", "extincteurs")
            self.assertEqual(set(self.statuts()), {"CTP-0903"})
            self.assertIn("recherche=extincteurs", page.evaluate("location.hash"))
            # Actualiser garde l'onglet et les filtres
            page.reload()
            attendre_pret(page)
            page.wait_for_selector(".panneau-onglet[data-onglet='contrats']:not([hidden]) .garanties-liste")
            self.assertEqual(set(self.statuts()), {"CTP-0903"})
            self.assertEqual(page.input_value(".panneau-onglet[data-onglet='contrats'] input[name=recherche]"), "extincteurs")

            # Compteur « Dates à mettre à jour »
            self.aller("#/garanties", ".garanties-compteurs")
            page.click(".garanties-compteurs a[data-compteur='a-mettre-a-jour']")
            page.wait_for_function("location.hash === '#/garanties?onglet=contrats&filtre=a-mettre-a-jour'")
            page.wait_for_selector(".panneau-onglet[data-onglet='contrats']:not([hidden]) .garanties-liste tbody tr")
            self.assertEqual(self.statuts(), {"CTP-0904": "a_mettre_a_jour"})
            self.sans_conforme()

            # La veille du délai (31/07/2026), le même contrat est « en cours » (CS173)
            self.nouveau_contexte()
            self.ouvrir(serveur, "#/garanties?onglet=contrats", jour="2026-07-31")
            page = self.page
            page.wait_for_selector(".panneau-onglet[data-onglet='contrats']:not([hidden]) .garanties-liste tbody tr")
            self.assertEqual(self.statuts()["CTP-0901"], "en_cours")
            self.assertEqual(self.compteurs()["a-decider"], 0)


# ---------------------------------------------------------------------------
# Fiches
# ---------------------------------------------------------------------------

class TestFiches(CasEcrans):

    def test_fiche_contrat_a_decider_mailto_reconduire_resiliation_retrait(self):
        page = self.page
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            equipements, fournisseurs = jeu(dossier)
            self.ouvrir(serveur, "#/garanties/contrat/CTP-0901")
            page.wait_for_selector(".garanties-fiche[data-contrat='CTP-0901']")
            self.assertEqual(page.inner_text(".garanties-fiche h1"), "Contrat — Maintenance des compresseurs")
            self.assertEqual(page.inner_text(".garanties-fiche .garanties-principe"), PHRASE)
            self.assertEqual(page.get_attribute(".garanties-fiche [data-statut]", "data-statut"), "a_decider")
            self.assertEqual(self.texte(".garanties-bandeau p"),
                             "Pour ne pas être reconduit le 31/12/2026, ce contrat doit être résilié au plus tard le "
                             "30/09/2026 (dans 60 jours). Prévo n'envoie rien : écrivez au prestataire.")
            courriel = page.get_attribute("#contrat-ecrire", "href")
            self.assertTrue(courriel.startswith("mailto:" + fournisseurs[0]["email"] + "?subject="), courriel)
            self.assertEqual(unquote(courriel.split("subject=")[1]), "Résiliation du contrat : Maintenance des compresseurs")
            fiche = self.texte(".garanties-fiche .carte")
            for morceau in ("3 mois", "30/09/2026, dans 60 jours", "Oui, par périodes de 12 mois", "1 200,00 €",
                            "équipement introuvable (EQ-9999)", fournisseurs[0]["nom"]):
                self.assertIn(morceau, fiche)
            self.assertEqual(page.get_attribute(".garanties-equipements-liste a", "href"), "#/equipement/" + equipements[0]["id"])
            self.assertEqual(page.get_attribute("#contrat-modifier", "href"), "#/garanties/contrat/CTP-0901/modifier")
            self.sans_conforme()

            # Reconduire : période proposée (fin + 12 mois), écrite, au journal, dans l'historique
            page.click("#contrat-reconduire")
            page.wait_for_selector("dialog [name=date_fin]")
            self.assertEqual(page.input_value("dialog [name=date_debut]"), "2027-01-01")
            self.assertEqual(page.input_value("dialog [name=date_fin]"), "2027-12-31")
            page.click("dialog .fenetre-actions .btn-primaire")
            self.attendre_toast("Contrat reconduit jusqu'au 31/12/2027.")
            self.attendre_ligne(dossier, "contrats_prestataires.csv", lambda l: l["id"] == "CTP-0901" and l["date_fin"] == "2027-12-31")
            self.assertEqual(journal(dossier, "contrats_prestataires", "CTP-0901")[-1],
                             "modification : date_debut, date_fin — reconduction : du 01/01/2026 au 31/12/2026 → "
                             "du 01/01/2027 au 31/12/2027")
            page.wait_for_selector(".garanties-journal li")
            self.assertIn("Modification : Début, Fin — reconduction : du 01/01/2026 au 31/12/2026 → du 01/01/2027 au 31/12/2027",
                          page.inner_text(".garanties-journal"))

            # Noter la résiliation : lettre du jour, commentaire ; la reconduction tacite passe à non
            page.click("#contrat-resiliation")
            page.wait_for_selector("dialog [name=commentaire]")
            self.assertEqual(page.input_value("dialog [name=date]"), "2026-08-01")
            page.fill("dialog [name=commentaire]", "Lettre recommandée")
            page.click("dialog .fenetre-actions .btn-primaire")
            self.attendre_toast("Résiliation notée : le contrat se termine le 31/12/2027.")
            self.attendre_ligne(dossier, "contrats_prestataires.csv", lambda l: l["id"] == "CTP-0901" and l["reconduction_tacite"] == "0")
            self.assertEqual(journal(dossier, "contrats_prestataires", "CTP-0901")[-1],
                             "modification : reconduction_tacite — résiliation notée : lettre du 01/08/2026 ; Lettre recommandée")
            page.wait_for_function("!document.querySelector('#contrat-resiliation')")
            self.assertEqual(page.locator("#contrat-reconduire").count(), 0)
            self.assertIn("résiliation notée : lettre du 01/08/2026 ; Lettre recommandée", page.inner_text(".garanties-journal"))

            # Retirer : confirmation, puis la liste ; la fiche reste lisible, sans bouton
            page.click("#contrat-retirer")
            page.wait_for_selector("dialog .btn-danger")
            self.assertIn("Retirer ce contrat ? Il ne sera plus affiché ni rappelé ; il reste au journal.",
                          page.inner_text("dialog"))
            page.click("dialog .btn-danger")
            self.attendre_toast("Contrat retiré.")
            page.wait_for_function("location.hash === '#/garanties?onglet=contrats'")
            self.attendre_ligne(dossier, "contrats_prestataires.csv", lambda l: l["id"] == "CTP-0901" and l["actif"] == "0")
            self.assertEqual(journal(dossier, "contrats_prestataires", "CTP-0901")[-1], "modification : actif — contrat retiré")
            page.wait_for_selector(".panneau-onglet[data-onglet='contrats']:not([hidden]) .garanties-liste")
            self.assertNotIn("CTP-0901", self.statuts())
            self.aller("#/garanties/contrat/CTP-0901", ".garanties-fiche .alerte")
            self.assertIn("Contrat retiré : il n'est plus affiché ni rappelé ; il reste au journal.",
                          page.inner_text(".garanties-fiche .alerte"))
            self.assertEqual(page.locator(".garanties-fiche .entete-page .actions").count(), 0)
            self.assertIn("contrat retiré", page.inner_text(".garanties-journal"))

    def test_fiche_garantie_creee_par_le_formulaire_document_retrait(self):
        page = self.page
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            equipements, fournisseurs = jeu(dossier)
            (dossier / "documents").mkdir(exist_ok=True)
            (dossier / "documents" / "garantie-GAR-0901-2025-04-01.pdf").write_bytes(PDF)
            texte = (dossier / "garanties.csv").read_text(encoding="utf-8-sig")
            (dossier / "garanties.csv").write_text(texte.replace("Pièces et main-d'œuvre;", "Pièces et main-d'œuvre;garantie-GAR-0901-2025-04-01.pdf"),
                                                   encoding="utf-8-sig", newline="")
            self.ouvrir(serveur, "#/garanties/garantie/GAR-0901")
            page.wait_for_selector(".garanties-fiche[data-garantie='GAR-0901']")
            eq = equipements[0]
            self.assertEqual(page.inner_text(".garanties-fiche h1"), "Garantie — %s %s" % (eq["repere"], eq["designation"]))
            self.assertEqual(page.get_attribute(".garanties-fiche [data-statut]", "data-statut"), "en_cours")
            self.assertIn("jusqu'au 31/03/2027", page.inner_text(".garanties-raison"))
            self.assertEqual(page.inner_text(".garanties-fiche .garanties-principe"), PHRASE)
            f = fournisseurs[0]
            self.assertEqual(page.get_attribute(".garanties-fournisseur a[href^='tel:']", "href"),
                             "tel:" + re.sub(r"[^0-9+]", "", f["telephone"]))
            self.assertEqual(page.get_attribute(".garanties-fournisseur a[href^='mailto:']", "href"), "mailto:" + f["email"])
            self.assertIn("Pièces et main-d'œuvre", page.inner_text(".garanties-texte-long"))
            lien = page.get_attribute("a.garanties-document", "href")
            self.assertTrue(lien, "lien du document")
            self.assertEqual(page.request.get(serveur.url + lien if lien.startswith("/") else lien).body(), PDF)
            self.sans_conforme()

            # Création par le formulaire : l'appli ouvre la fiche de la garantie créée
            self.aller("#/garanties/garantie/nouvelle?equipement=" + equipements[1]["id"],
                       "#form-garantie .selecteur-choisi:not([hidden])")
            page.fill("#form-garantie [name=date_fin]", "2027-02-28")
            page.click("#form-garantie button[type=submit]")
            self.attendre_toast("Garantie enregistrée.")
            nouvelle = self.attendre_ligne(dossier, "garanties.csv", lambda l: l["date_fin"] == "2027-02-28")
            page.wait_for_selector(".garanties-fiche[data-garantie='%s']" % nouvelle["id"])
            self.assertEqual(page.evaluate("location.hash"), "#/garanties/garantie/" + nouvelle["id"])
            self.assertIn("Création — garantie enregistrée", page.inner_text(".garanties-journal"))
            self.assertIn("Aucun document joint", page.inner_text(".garanties-fiche .carte"))
            self.assertIn("Non renseigné", page.inner_text(".garanties-fiche .carte"))

            # Retirer : confirmation, la liste sans elle, la fiche lisible sans bouton
            page.click("#garantie-retirer")
            page.wait_for_selector("dialog .btn-danger")
            self.assertIn("Retirer cette garantie ? Elle ne sera plus affichée ni rappelée ; elle reste au journal.",
                          page.inner_text("dialog"))
            page.click("dialog .btn-danger")
            self.attendre_toast("Garantie retirée.")
            page.wait_for_function("location.hash === '#/garanties?onglet=garanties'")
            self.attendre_ligne(dossier, "garanties.csv", lambda l: l["id"] == nouvelle["id"] and l["actif"] == "0")
            self.assertEqual(journal(dossier, "garanties", nouvelle["id"])[-1], "modification : actif — garantie retirée")
            page.wait_for_selector(".panneau-onglet[data-onglet='garanties']:not([hidden]) .garanties-liste")
            self.assertNotIn(nouvelle["id"], self.statuts())
            self.aller("#/garanties/garantie/" + nouvelle["id"], ".garanties-fiche .alerte")
            self.assertIn("Garantie retirée : elle n'est plus affichée ni rappelée ; elle reste au journal.",
                          page.inner_text(".garanties-fiche .alerte"))
            self.assertEqual(page.locator("#garantie-retirer, #garantie-modifier").count(), 0)
            self.assertIn("Modification : Actif — garantie retirée", page.inner_text(".garanties-journal"))

            # Introuvable : expliqué
            self.aller("#/garanties/garantie/GAR-9999", ".garanties-fiche .vide")
            self.assertIn("La garantie GAR-9999 est introuvable.", page.inner_text(".garanties-fiche .vide"))


# ---------------------------------------------------------------------------
# Profils et téléphone
# ---------------------------------------------------------------------------

class TestProfilsEtTelephone(CasEcrans):

    def test_profils_technicien_et_demandeur_ni_menu_ni_adresse(self):
        with ServeurPrevo() as serveur:
            jeu(serveur.dossier)
            technicien = lignes(serveur.dossier, "techniciens.csv")[0]["id"]
            for profil, route in (("technicien", "#/garanties?onglet=contrats"), ("technicien", "#/garanties/contrat/CTP-0901"),
                                  ("demandeur", "#/garanties"), ("demandeur", "#/garanties/garantie/GAR-0901")):
                with self.subTest(profil=profil, route=route):
                    self.nouveau_contexte()
                    self.ouvrir(serveur, route, profil=profil, technicien_id=technicien if profil == "technicien" else "")
                    self.page.wait_for_function("location.hash === '#/accueil'")
                    self.assertEqual(self.page.locator("#menu a[data-ecran='garanties']").count(), 0)
                    self.assertEqual(self.page.locator(".garanties-ecran, .garanties-fiche").count(), 0)
                    self.assertNotIn("1 200,00", self.page.inner_text("#contenu").translate(ESPACES))

    def test_telephone_375px_cartes_sans_defilement(self):
        page = self.page
        with ServeurPrevo() as serveur:
            jeu(serveur.dossier)
            self.ouvrir(serveur, "#/garanties", largeur=375)
            page.set_viewport_size({"width": 375, "height": 812})
            self.aller("#/garanties?onglet=garanties", ".garanties-liste .liste-cartes")
            self.assertEqual(self.statuts(), {"GAR-0902": "bientot", "GAR-0901": "en_cours", "GAR-0903": "terminee"})
            self.sans_defilement("liste des garanties")
            self.aller("#/garanties?onglet=contrats", ".panneau-onglet[data-onglet='contrats']:not([hidden]) .liste-cartes")
            self.assertEqual(self.statuts()["CTP-0901"], "a_decider")
            self.sans_defilement("liste des contrats")
            for selecteur in ("#garanties-nouvelle", "#garanties-nouveau-contrat", ".garanties-liste .liste-cartes a"):
                self.assertGreaterEqual(page.eval_on_selector(selecteur, "e => e.getBoundingClientRect().height"), 48, selecteur)
            self.aller("#/garanties/contrat/CTP-0901", ".garanties-fiche .garanties-bandeau")
            self.sans_defilement("fiche du contrat")
            for selecteur in ("#contrat-modifier", "#contrat-resiliation", "#contrat-reconduire", "#contrat-retirer", "#contrat-ecrire"):
                self.assertGreaterEqual(page.eval_on_selector(selecteur, "e => e.getBoundingClientRect().height"), 48, selecteur)
            self.aller("#/garanties/garantie/GAR-0901", ".garanties-fiche[data-garantie='GAR-0901']")
            self.sans_defilement("fiche de la garantie")
            self.assertGreaterEqual(page.eval_on_selector(".garanties-fournisseur a[href^='tel:']",
                                                          "e => e.getBoundingClientRect().height"), 48)


if __name__ == "__main__":
    unittest.main()
