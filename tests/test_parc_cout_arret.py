"""Coût d'une heure d'arrêt d'un équipement, 2.2 L5 (T471 ; D188, CS174, D126 ; conception L4-L5-L6 §3.2 et §3.3 ;
QUESTIONS-L2-L6, L4-L6 Q5 et Q6).

Colonne equipements.cout_arret_h : décimal positif ou nul, deux décimales au plus, dans la devise réglée ; vide =
« non chiffré » (jamais de valeur par défaut, jamais estimé) ; 0 = arrêt sans coût, chiffré à 0.

Familles (le nom du test le dit) :
    regles     : Parc.verifierEquipement (démo en file://) : vide permis ; « 850 », « 1250.50 », « 1 250,50 », « 0 »
                 acceptés ; négatif, trois décimales, texte illisible, écriture scientifique refusés, avec le message de
                 la conception, sous le champ cout_arret_h ;
    formulaire : serveur sur une copie de la démo : champ juste après la valeur de remplacement, libellé dans la
                 devise réglée, aide de la conception, aucune valeur par défaut ; « -5 » et « 12,345 » refusés sous le
                 champ sans rien écrire ; « 1 250,50 » écrit 1250.50 et la fiche montre « 1 250,50 €/h » ; 0 écrit 0
                 (« 0,00 €/h ») ; champ vidé → colonne vide et « non chiffré » ;
    profils    : ligne « Coût d'une heure d'arrêt » de la fiche technique pour le responsable seul (montant dans la
                 devise réglée, CHF ; « non chiffré » si vide) ; technicien et demandeur : ni montant, ni ligne, ni
                 « non chiffré », au serveur comme en démo (où la valeur est pourtant dans les données du navigateur).

Jamais de données réelles : copie temporaire de donnees/demo (ServeurPrevo) ou démo en lecture seule ; équipements et
techniciens pris dans le jeu (aucun identifiant écrit en dur).

Lancer depuis la racine du projet (au travers du verrou des navigateurs) :
    py -X utf8 -m unittest discover -s tests -p "test_parc_cout_arret.py" -v
"""
import csv
import io
import re
import unittest
from pathlib import Path

from commun import CasNavigateur, RACINE, ServeurPrevo, attendre_pret, preregler_profil, url_fichier

DOSSIER_DEMO = RACINE / "donnees" / "demo"
ESPACES = re.compile("[%s%s]" % (chr(0xA0), chr(0x202F)))          # insécables (Intl)
CHAMP = "#parc-formulaire .champ[data-champ=cout_arret_h]"
LIGNE_FICHE = ".valeurs .parc-cout-arret"
MESSAGE = "Saisissez un montant positif ou nul, au centime (ex. 850 ou 1 250,50)."
AIDE = ("Production perdue, pénalités, heures supplémentaires… Laissez vide si vous ne savez pas : l'équipement sera "
        "« non chiffré » dans le rapport, jamais estimé.")
LIBELLE_FICHE = "Coût d'une heure d'arrêt"


def lire_csv(chemin):
    texte = Path(chemin).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte, newline=""), delimiter=";"))


def brut(valeur):
    valeur = (valeur or "").strip()
    return valeur[1:] if valeur.startswith("'") else valeur


def equipements(dossier):
    return [{cle: brut(v) for cle, v in ligne.items()} for ligne in lire_csv(Path(dossier) / "equipements.csv")]


def equipement_chiffre(dossier):
    """Premier équipement actif du jeu dont le coût d'une heure d'arrêt est renseigné (> 0)."""
    return next(e for e in equipements(dossier) if e.get("actif") != "0" and e.get("cout_arret_h")
                and float(e["cout_arret_h"]) > 0)


def equipement_non_chiffre(dossier):
    """Premier équipement actif du jeu sans coût d'une heure d'arrêt."""
    return next(e for e in equipements(dossier) if e.get("actif") != "0" and not e.get("cout_arret_h"))


def cout_sur_le_disque(dossier, identifiant):
    return next(e for e in equipements(dossier) if e["id"] == identifiant)["cout_arret_h"]


def premier_technicien(dossier):
    return next(t["id"] for t in lire_csv(Path(dossier) / "techniciens.csv") if brut(t.get("actif")) != "0")


def poser_parametre(dossier, cle, valeur):
    """cle = valeur dans parametres.csv (ligne remplacée ou ajoutée), écrit comme Prévo l'écrit (BOM, « ; », CRLF)."""
    chemin = Path(dossier) / "parametres.csv"
    texte = chemin.read_text(encoding="utf-8-sig")
    lecteur = csv.reader(io.StringIO(texte, newline=""), delimiter=";")
    entete = next(lecteur)
    lignes = [l for l in lecteur if l and l[0] != cle] + [[cle, valeur]]
    sortie = io.StringIO()
    ecrivain = csv.writer(sortie, delimiter=";", lineterminator="\r\n")
    ecrivain.writerow(entete)
    ecrivain.writerows(lignes)
    chemin.write_text(sortie.getvalue(), encoding="utf-8-sig", newline="")


def espaces_simples(texte):
    return ESPACES.sub(" ", texte).strip()


class CasCoutArret(CasNavigateur):

    def ouvrir_serveur(self, serveur, route, profil="responsable", technicien_id=""):
        nom = "Demandeur test" if profil == "demandeur" else ""
        preregler_profil(self.contexte, profil, nom=nom, technicien_id=technicien_id)
        self.page.goto(serveur.url + "/" + route)
        attendre_pret(self.page)
        # Les écritures du démarrage (OT préventifs échus) sont finies avant le test.
        self.page.wait_for_load_state("networkidle")

    def changer_profil(self, serveur, route, profil, technicien_id=""):
        nom = "Demandeur test" if profil == "demandeur" else ""
        self.page.evaluate("([t, n, id]) => localStorage.setItem('prevo.profil', JSON.stringify({type: t, nom: n, "
                           "technicienId: id}))", [profil, nom, technicien_id])
        self.page.goto(serveur.url + "/" + route)
        self.page.reload()                                  # même document : on recharge pour lire le profil
        attendre_pret(self.page)
        self.assertEqual(self.page.evaluate("App.profil.type"), profil)

    def ouvrir_demo(self, profil, technicien_id=""):
        page = self.page
        page.goto(url_fichier("index.html"))
        page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        page.click("#btn-demo")
        page.wait_for_function("document.documentElement.dataset.etat === 'profil'")
        page.click("#profil-" + profil)
        if profil == "technicien":
            page.click("#profil-techniciens [data-technicien='%s']" % technicien_id)
        elif profil == "demandeur":
            page.fill("#profil-nom", "Demandeur test")
            page.click("#profil-panneau-demandeur button[type=submit]")
        attendre_pret(page)
        self.assertEqual(page.evaluate("App.profil.type"), profil)

    def attendre_fiche(self, identifiant):
        """Attend la fiche de CET équipement (l'identifiant est la première valeur de la fiche technique)."""
        self.page.wait_for_function("""(id) => { const dd = document.querySelector('#contenu .parc .valeurs dd');
            return location.hash === '#/equipement/' + id && dd !== null && dd.textContent.trim() === id; }""",
                                    arg=identifiant)

    def fiche(self, identifiant):
        self.page.evaluate("(r) => { location.hash = r; }", "#/equipement/" + identifiant)
        self.attendre_fiche(identifiant)

    def texte_fiche(self):
        return espaces_simples(self.page.inner_text(LIGNE_FICHE))

    def sans_ligne_de_cout(self, contexte):
        page = self.page
        self.assertEqual(page.locator(LIGNE_FICHE).count(), 0, contexte)
        contenu = espaces_simples(page.inner_text("#contenu"))
        self.assertNotIn(LIBELLE_FICHE, contenu, contexte)
        self.assertNotIn("non chiffré", contenu, contexte)
        self.assertNotIn("/h", espaces_simples(page.inner_text("#contenu .valeurs")), contexte)


# ---------------------------------------------------------------------------
# Règles : Parc.verifierEquipement
# ---------------------------------------------------------------------------

class TestRegles(CasCoutArret):

    def test_regles_vide_permis_positif_ou_nul_deux_decimales_au_plus(self):
        self.ouvrir_demo("responsable")
        localisation = lire_csv(DOSSIER_DEMO / "localisations.csv")[0]["id"]
        base = {"repere": "ZZ-71", "designation": "Machine de test", "localisation_id": localisation, "parent_id": ""}
        verifier = """([valeurs]) => Parc.verifierEquipement(valeurs, Donnees.lignes('equipements'),
            Donnees.lignes('localisations'), '')"""

        def erreurs(cout):
            valeurs = dict(base) if cout is None else dict(base, cout_arret_h=cout)
            return [(e["nom"], e["message"]) for e in self.page.evaluate(verifier, [valeurs])]

        # Vide (ou absent) : permis, l'équipement sera « non chiffré » (D188 : aucune valeur par défaut)
        for cout in (None, "", "   "):
            self.assertEqual(erreurs(cout), [], repr(cout))
        # Positif ou nul, deux décimales au plus ; virgule et espaces de milliers acceptés
        for cout in ("0", "850", "1250.50", "1250.5", "1 250,50", "0,01", "87.35", "850."):
            self.assertEqual(erreurs(cout), [], cout)
        # Refusés, sous le champ, avec le message de la conception
        for cout in ("-5", "-0,01", "12.345", "0.001", "abc", "1e3", "12,5,0", "850 €"):
            self.assertEqual(erreurs(cout), [("cout_arret_h", MESSAGE)], cout)
        # Les autres contrôles ne changent pas
        self.assertEqual([n for n, _ in erreurs("-5") + erreurs("")], ["cout_arret_h"])


# ---------------------------------------------------------------------------
# Formulaire de l'équipement (responsable)
# ---------------------------------------------------------------------------

class TestFormulaire(CasCoutArret):

    def enregistrer(self, identifiant, cout):
        page = self.page
        page.fill(CHAMP + " input", cout)
        page.click("#parc-formulaire button[type=submit]")
        self.attendre_fiche(identifiant)

    def modifier(self, identifiant):
        self.page.evaluate("(r) => { location.hash = r; }", "#/equipement/%s/modifier" % identifiant)
        self.page.wait_for_selector(CHAMP + " input")

    def test_formulaire_champ_refus_saisie_zero_et_vide(self):
        page = self.page
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            equipement = equipement_non_chiffre(dossier)
            identifiant = equipement["id"]
            self.ouvrir_serveur(serveur, "#/equipement/" + identifiant)
            self.attendre_fiche(identifiant)
            # Fiche : vide → « non chiffré » (responsable)
            self.assertEqual(self.texte_fiche(), "non chiffré")

            self.modifier(identifiant)
            champs = page.eval_on_selector_all("#parc-formulaire .champ[data-champ]", "els => els.map(e => e.dataset.champ)")
            self.assertEqual(champs[champs.index("valeur_remplacement") + 1], "cout_arret_h")
            self.assertEqual(espaces_simples(page.inner_text(CHAMP + " .libelle")), "Coût d'une heure d'arrêt (€/h)")
            self.assertEqual(espaces_simples(page.inner_text(CHAMP + " .aide")), AIDE)
            self.assertEqual(page.input_value(CHAMP + " input"), "")           # aucune valeur par défaut
            self.assertEqual(page.get_attribute(CHAMP + " input", "inputmode"), "decimal")

            # Refus sous le champ, rien d'écrit
            avant = (dossier / "equipements.csv").read_bytes()
            for cout in ("-5", "12,345"):
                page.fill(CHAMP + " input", cout)
                page.click("#parc-formulaire button[type=submit]")
                page.wait_for_selector(CHAMP + ".en-erreur")
                self.assertEqual(page.inner_text(CHAMP + " .erreur-champ").strip(), MESSAGE, cout)
                self.assertEqual(page.evaluate("location.hash"), "#/equipement/%s/modifier" % identifiant)
                self.assertEqual((dossier / "equipements.csv").read_bytes(), avant, cout)

            # « 1 250,50 » : écrit 1250.50 (point décimal), montré au centime avec la devise
            self.enregistrer(identifiant, "1 250,50")
            self.assertEqual(cout_sur_le_disque(dossier, identifiant), "1250.50")
            self.assertEqual(self.texte_fiche(), "1 250,50 €/h")
            # Les autres colonnes de la ligne n'ont pas bougé
            apres = next(e for e in equipements(dossier) if e["id"] == identifiant)
            self.assertEqual({k: v for k, v in apres.items() if k != "cout_arret_h"},
                             {k: v for k, v in equipement.items() if k != "cout_arret_h"})

            # Prérempli à la modification suivante ; 0 = arrêt sans coût (chiffré à 0, pas « non chiffré »)
            self.modifier(identifiant)
            self.assertEqual(page.input_value(CHAMP + " input"), "1250,50")
            self.enregistrer(identifiant, "0")
            self.assertEqual(cout_sur_le_disque(dossier, identifiant), "0")
            self.assertEqual(self.texte_fiche(), "0,00 €/h")

            # Vidé : colonne vide, « non chiffré »
            self.modifier(identifiant)
            self.enregistrer(identifiant, "")
            self.assertEqual(cout_sur_le_disque(dossier, identifiant), "")
            self.assertEqual(self.texte_fiche(), "non chiffré")


# ---------------------------------------------------------------------------
# Fiche technique : responsable seul (D126)
# ---------------------------------------------------------------------------

class TestProfils(CasCoutArret):

    def test_profils_serveur_responsable_seul_dans_la_devise_reglee(self):
        page = self.page
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            poser_parametre(dossier, "devise", "CHF")
            chiffre, non_chiffre = equipement_chiffre(dossier), equipement_non_chiffre(dossier)
            technicien = premier_technicien(dossier)
            self.ouvrir_serveur(serveur, "#/equipement/" + chiffre["id"])
            self.fiche(chiffre["id"])
            attendu = espaces_simples(page.evaluate("(v) => UI.euro(v)", chiffre["cout_arret_h"])) + "/h"
            self.assertIn("CHF", attendu)
            self.assertEqual(self.texte_fiche(), attendu)
            libelles = [espaces_simples(t) for t in page.locator(".valeurs dt").all_inner_texts()]
            self.assertEqual(libelles[libelles.index("Valeur de remplacement") + 1], LIBELLE_FICHE)
            self.fiche(non_chiffre["id"])
            self.assertEqual(self.texte_fiche(), "non chiffré")
            # Le libellé du formulaire suit la devise réglée
            page.evaluate("(r) => { location.hash = r; }", "#/equipement/%s/modifier" % chiffre["id"])
            page.wait_for_selector(CHAMP + " input")
            self.assertEqual(espaces_simples(page.inner_text(CHAMP + " .libelle")), "Coût d'une heure d'arrêt (CHF/h)")

            for profil, technicien_id in (("technicien", technicien), ("demandeur", "")):
                self.changer_profil(serveur, "#/equipement/" + chiffre["id"], profil, technicien_id)
                for equipement in (chiffre, non_chiffre):
                    self.fiche(equipement["id"])
                    self.sans_ligne_de_cout("%s, %s" % (profil, equipement["id"]))

    # En démo, rien ne cache la colonne : les données du navigateur la portent, l'écran seul la tait.
    def verifier_demo(self, profil, technicien_id=""):
        chiffre = equipement_chiffre(DOSSIER_DEMO)
        self.ouvrir_demo(profil, technicien_id)
        self.assertEqual(self.page.evaluate("(id) => Donnees.trouver('equipements', id).cout_arret_h", chiffre["id"]),
                         chiffre["cout_arret_h"])
        self.fiche(chiffre["id"])
        return chiffre

    def test_profils_demo_technicien_sans_la_ligne(self):
        self.verifier_demo("technicien", premier_technicien(DOSSIER_DEMO))
        self.sans_ligne_de_cout("technicien")

    def test_profils_demo_demandeur_sans_la_ligne(self):
        self.verifier_demo("demandeur")
        self.sans_ligne_de_cout("demandeur")

    def test_profils_demo_responsable_voit_le_montant(self):
        chiffre = self.verifier_demo("responsable")
        self.assertEqual(self.texte_fiche(),
                         espaces_simples(self.page.evaluate("(v) => UI.euro(v)", chiffre["cout_arret_h"])) + "/h")
        self.assertIn("€/h", self.texte_fiche())


if __name__ == "__main__":
    unittest.main()
