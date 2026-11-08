"""Chantier multilingue, Lot 4 — devise réglable, clé `devise` de parametres.csv (T304 ; D152, CS159, D146).

Dans Chromium, mode serveur (serveur.py sur une copie du jeu de démo, profil responsable) :
    - défaut EUR (aucune clé dans la démo) : affichage français identique (« 1 234,50 € », fiche d'un équipement
      « 32 400,00 € HT », libellé « Taux horaire (€ HT / h) ») ;
    - réglage « Devise » (Paramètres, section Entreprise) : EUR, CHF, GBP, USD, TRY (code — nom) et « Autre code
      ISO 4217 » ; CHF enregistré → `devise` = CHF dans parametres.csv, montants et libellés en CHF sur la fiche
      d'un équipement et le formulaire d'un technicien, valeurs des CSV inchangées (D146) ;
    - autre code : « sek » (minuscules) enregistré SEK ; code inconnu (« ZZZ »), trop court ou avec un chiffre refusé
      avec un message sous le champ, rien d'écrit ;
    - anglais + GBP : « £1,234.50 » et « Hourly rate (£ excl. VAT / h) » ;
    - valeur illisible ou inconnue sur le disque : repli sur EUR, sans erreur ;

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_devise.py" -v
"""
import csv
import io
import unittest
from pathlib import Path

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil

BOM = "﻿"
NBSP = " "
FORMULAIRE = "#form-parametres "
CHAMP_DEVISE = FORMULAIRE + "[name=devise]"
CHAMP_AUTRE = FORMULAIRE + "[name=devise_autre]"
VALEUR_REMPLACEMENT = ".parc-valeur-remplacement"
LIBELLE_TAUX = ".champ[data-champ='taux_horaire'] label"


def lire_csv(chemin):
    with open(chemin, encoding="utf-8-sig", newline="") as fichier:
        lecteur = csv.reader(fichier, delimiter=";")
        entete = next(lecteur)
        return entete, [dict(zip(entete, cellules)) for cellules in lecteur if any(cellules)]


def poser(dossier, cle, valeur):
    """cle = valeur dans parametres.csv (ligne remplacée ou ajoutée), écrit comme Prévo l'écrit."""
    chemin = Path(dossier) / "parametres.csv"
    entete, lignes = lire_csv(chemin)
    lignes = [ligne for ligne in lignes if ligne["cle"] != cle] + [{"cle": cle, "valeur": valeur}]
    tampon = io.StringIO(newline="")
    ecrivain = csv.writer(tampon, delimiter=";", lineterminator="\r\n")
    ecrivain.writerow(entete)
    for ligne in lignes:
        ecrivain.writerow([ligne.get(nom, "") for nom in entete])
    chemin.write_bytes((BOM + tampon.getvalue()).encode("utf-8"))


def sur_le_disque(dossier, cle):
    _, lignes = lire_csv(Path(dossier) / "parametres.csv")
    valeurs = [ligne["valeur"] for ligne in lignes if ligne["cle"] == cle]
    return valeurs[-1] if valeurs else None


def valeur_remplacement_du_disque(dossier, identifiant):
    _, lignes = lire_csv(Path(dossier) / "equipements.csv")
    return [ligne["valeur_remplacement"] for ligne in lignes if ligne["id"] == identifiant][0]


class TestDevise(CasNavigateur):

    def setUp(self):
        super().setUp()
        preregler_profil(self.contexte, "responsable")

    # -- outils ---------------------------------------------------------------------------------

    def ouvrir(self, serveur, route):
        self.page.goto(serveur.url + "/" + route)
        attendre_pret(self.page)

    def aller(self, route):
        self.page.evaluate("(route) => { location.hash = route; }", route)

    def montant(self):
        return self.page.evaluate("UI.euro('1234.5')")

    def fiche_equipement(self):
        self.aller("#/equipement/EQ-0001")
        self.page.wait_for_selector(VALEUR_REMPLACEMENT)
        return self.page.inner_text(VALEUR_REMPLACEMENT).strip()

    def libelle_taux(self):
        self.aller("#/equipe/nouveau")
        self.page.wait_for_selector(LIBELLE_TAUX)
        return self.page.inner_text(LIBELLE_TAUX).strip()

    def enregistrer(self):
        self.page.click(FORMULAIRE + "button[type=submit]")
        self.page.wait_for_timeout(600)

    # -- tests ----------------------------------------------------------------------------------

    def test_defaut_eur_affichage_francais_identique(self):
        with ServeurPrevo() as serveur:
            self.assertIsNone(sur_le_disque(serveur.dossier, "devise"))                  # absente de la démo
            self.ouvrir(serveur, "#/accueil")
            self.assertEqual(self.page.evaluate("UI.devise()"), "EUR")
            self.assertEqual(self.montant(), "1" + NBSP + "234,50" + NBSP + "€")
            self.assertEqual(self.page.evaluate("UI.symboleDevise()"), "€")
            self.assertEqual(self.fiche_equipement(), "32" + NBSP + "400,00" + NBSP + "€ HT")
            self.assertEqual(self.libelle_taux(), "Taux horaire (€ HT / h)")

    def test_reglage_chf_enregistre_montants_affiches_donnees_inchangees(self):
        with ServeurPrevo() as serveur:
            avant = valeur_remplacement_du_disque(serveur.dossier, "EQ-0001")
            self.ouvrir(serveur, "#/parametres")
            self.page.wait_for_selector(CHAMP_DEVISE)
            champ = self.page.evaluate("""(selecteur) => {
              const liste = document.querySelector(selecteur);
              const bloc = liste.closest('.champ');
              return { options: [...liste.options].map((o) => [o.value, o.textContent]), valeur: liste.value,
                libelle: bloc.querySelector('label').textContent.trim(), aide: bloc.querySelector('.aide').textContent.trim(),
                suivant: bloc.nextElementSibling.dataset.champ,
                section: [...document.querySelectorAll('#form-parametres > *')].slice(0, 5).map((e) => e.tagName === 'H3'
                  ? 'h3' : e.dataset.champ) };
            }""", CHAMP_DEVISE)
            self.assertEqual([option[0] for option in champ["options"]], ["EUR", "CHF", "GBP", "USD", "TRY", "autre"])
            self.assertEqual(champ["options"][0], ["EUR", "EUR — euro"])
            self.assertEqual(champ["options"][1], ["CHF", "CHF — franc suisse"])
            self.assertEqual(champ["valeur"], "EUR")
            self.assertEqual(champ["libelle"], "Devise")
            self.assertEqual(champ["aide"], "Change seulement l'affichage : aucun montant n'est converti.")
            self.assertEqual(champ["section"], ["h3", "entreprise_nom", "langue_defaut", "devise", "devise_autre"])

            self.page.select_option(CHAMP_DEVISE, "CHF")
            self.enregistrer()
            self.assertEqual(sur_le_disque(serveur.dossier, "devise"), "CHF")
            self.assertEqual(self.page.evaluate("UI.devise()"), "CHF")
            self.assertEqual(self.montant(), "1" + NBSP + "234,50" + NBSP + "CHF")
            self.assertEqual(self.fiche_equipement(), "32" + NBSP + "400,00" + NBSP + "CHF HT")
            self.assertEqual(self.libelle_taux(), "Taux horaire (CHF HT / h)")
            # D146 : les données ne changent jamais (nombre sans symbole, aucune conversion).
            self.assertEqual(valeur_remplacement_du_disque(serveur.dossier, "EQ-0001"), avant)
            self.assertEqual(self.page.evaluate("Donnees.trouver('equipements', 'EQ-0001').valeur_remplacement"), avant)
            # Réglage relu.
            self.aller("#/parametres")
            self.page.wait_for_selector(CHAMP_DEVISE)
            self.assertEqual(self.page.input_value(CHAMP_DEVISE), "CHF")

    def test_autre_code_iso_accepte_ou_refuse(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/parametres")
            self.page.wait_for_selector(CHAMP_DEVISE)
            self.page.select_option(CHAMP_DEVISE, "autre")
            for saisie in ("ZZZ", "SE", "S3K"):
                self.page.fill(CHAMP_AUTRE, saisie)
                self.enregistrer()
                message = self.page.inner_text(".champ[data-champ='devise_autre'] .erreur-champ").strip()
                self.assertIn("Code de devise inconnu", message, saisie)
                self.assertIsNone(sur_le_disque(serveur.dossier, "devise"), saisie)
            self.page.fill(CHAMP_AUTRE, "sek")
            self.enregistrer()
            self.assertEqual(sur_le_disque(serveur.dossier, "devise"), "SEK")
            self.assertEqual(self.page.evaluate("UI.devise()"), "SEK")
            self.assertEqual(self.montant(), "1" + NBSP + "234,50" + NBSP + "SEK")
            # Relu : « autre » et le code dans son champ.
            self.aller("#/accueil")
            self.aller("#/parametres")
            self.page.wait_for_selector(CHAMP_DEVISE)
            self.assertEqual((self.page.input_value(CHAMP_DEVISE), self.page.input_value(CHAMP_AUTRE)), ("autre", "SEK"))

    def test_gbp_en_anglais(self):
        self.contexte.add_init_script("try { localStorage.setItem('prevo.langue', 'en'); } catch (erreur) { /* sans stockage */ }")
        with ServeurPrevo() as serveur:
            poser(serveur.dossier, "devise", "GBP")
            self.ouvrir(serveur, "#/accueil")
            self.assertEqual(self.page.evaluate("I18n.langue"), "en")
            self.assertEqual(self.montant(), "£1,234.50")
            self.assertEqual(self.libelle_taux(), "Hourly rate (£ excl. VAT / h)")

    def test_valeur_inconnue_sur_le_disque_repli_eur(self):
        with ServeurPrevo() as serveur:
            for valeur in ("XYZ", "euro", "chf"):
                poser(serveur.dossier, "devise", valeur)
                self.ouvrir(serveur, "#/accueil")
                self.page.reload()                  # même adresse : le seul changement de #… ne relit pas les données
                attendre_pret(self.page)
                self.assertEqual(self.page.evaluate("UI.devise()"), "CHF" if valeur == "chf" else "EUR", valeur)
                self.assertEqual(self.montant(), "1" + NBSP + "234,50" + NBSP + ("CHF" if valeur == "chf" else "€"), valeur)


if __name__ == "__main__":
    unittest.main()
