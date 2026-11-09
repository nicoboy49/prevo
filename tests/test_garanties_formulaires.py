"""Tests des formulaires d'une garantie et d'un contrat de prestataire, 2.2 (garanties-formulaires.js, T455 ; CDC §3.4,
CS173, D190 ; conception L4 §2.3 ; QUESTIONS-L2-L6, L4-L6 Q2, Q3, Q9).

Serveur Prévo sur une copie du jeu de démo (ServeurPrevo), profil préréglé ; CSV, journal et documents relus sur le
disque. Aucun identifiant de garantie ni de contrat écrit en dur ; équipements et fournisseurs pris dans le jeu copié.

Familles (le nom du test le dit) :
    garantie     : erreurs sous les champs avant toute écriture (équipement, date de fin, fin avant début, document
                   refusé) ; équipement pré-rempli par ?equipement= (Annuler revient à l'équipement) ; création avec
                   le certificat joint ; modification (champs changés, « aucune modification ») ; garantie retirée ou
                   introuvable : pas de formulaire ;
    contrat      : montant libellé avec la devise réglée (CHF HT) ; erreurs (prestataire, objet, fin, préavis, montant)
                   sans rien écrire ; CS173 : fin 31/12/2026 et 3 mois de préavis → « Date limite de résiliation :
                   30/09/2026 » avant l'enregistrement ; sans préavis ; avertissement non bloquant ; durée d'une
                   reconduction montrée avec la reconduction tacite seulement ; équipements en puces (Ajouter,
                   retirer, sans doublon) ; création avec le contrat signé ; modification d'un contrat qui cite un
                   équipement introuvable ;
    fournisseur  : « Nouveau fournisseur… » ouvre la fenêtre du Magasin ; la saisie (puces et document compris) est
                   reprise et le fournisseur créé choisi ; Annuler la fenêtre ne change rien ;
    profils      : technicien et demandeur renvoyés à l'accueil ;
    telephone    : 375 px sans défilement horizontal, zones tactiles de 48 px.

Lancer depuis la racine du projet (au travers du verrou des navigateurs) :
    py -X utf8 -m unittest discover -s tests -p "test_garanties_formulaires.py" -v
"""
import csv
import io
import re
import unittest
from pathlib import Path

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil

PDF = {"name": "certificat.pdf", "mimeType": "application/pdf", "buffer": b"%PDF-1.4\n% document de test (T455)\n%%EOF\n"}
TEXTE = {"name": "notes.txt", "mimeType": "text/plain", "buffer": b"pas un document"}

# Espion de App.naviguer : les adresses ouvertes après l'enregistrement (la fiche est l'écran de T456).
ESPION_JS = """() => { window.__adresses = []; const naviguer = App.naviguer;
  App.naviguer = (adresse) => { window.__adresses.push(adresse); return naviguer(adresse); }; }"""


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


def equipements_actifs(dossier):
    """(id, repère) des équipements actifs du jeu copié, dans l'ordre du fichier."""
    return [(e["id"], e["repere"]) for e in lignes(dossier, "equipements.csv") if e.get("actif") != "0"]


def ajouter_ligne_csv(chemin, valeurs):
    """Ajoute une ligne au CSV (en-tête du fichier, « ; », CRLF), comme l'écrit Prévo."""
    texte = chemin.read_text(encoding="utf-8-sig")
    entete = next(csv.reader(io.StringIO(texte), delimiter=";"))
    sortie = io.StringIO()
    csv.writer(sortie, delimiter=";", lineterminator="\r\n").writerow([valeurs.get(c, "") for c in entete])
    if not texte.endswith("\n"):
        texte += "\r\n"
    chemin.write_text(texte + sortie.getvalue(), encoding="utf-8-sig", newline="")


class CasFormulaires(CasNavigateur):

    def ouvrir(self, serveur, route, profil="responsable", technicien_id="", largeur=1280):
        self.page.set_viewport_size({"width": largeur, "height": 900})
        nom = "Demandeur test" if profil == "demandeur" else ""
        preregler_profil(self.contexte, profil, nom=nom, technicien_id=technicien_id)
        self.page.goto(serveur.url + "/" + route)
        attendre_pret(self.page)
        # Les écritures du démarrage (OT préventifs échus) sont finies avant le test.
        self.page.wait_for_load_state("networkidle")

    def aller(self, route, selecteur=None):
        self.page.evaluate("(route) => { location.hash = route; }", route)
        if selecteur:
            self.page.wait_for_selector(selecteur)

    def attendre_toast(self, morceau):
        self.page.wait_for_function(
            "(texte) => document.getElementById('toast').textContent.includes(texte)", arg=morceau)

    def erreurs(self, formulaire):
        """{ nom du champ : message } des erreurs affichées sous les champs."""
        return self.page.evaluate("""(formulaire) => Object.fromEntries(Array.from(
            document.querySelectorAll(formulaire + ' .champ.en-erreur')).map((bloc) =>
            [bloc.dataset.champ, bloc.querySelector('.erreur-champ').textContent.trim()]))""", formulaire)

    def envoyer(self, formulaire):
        self.page.click(formulaire + " button[type=submit]")

    def date_limite(self):
        return self.page.inner_text("#form-contrat .garanties-date-limite").strip()

    def choisir_equipement(self, racine, equipement_id, repere):
        self.page.fill(racine + " .garanties-selecteur input[type=search]", repere)
        self.page.click(racine + " .garanties-selecteur .selecteur-option[data-id='%s']" % equipement_id)

    def puces(self):
        return self.page.eval_on_selector_all("#form-contrat .garanties-puce", "puces => puces.map(p => p.dataset.equipement)")

    def attendre_ligne(self, dossier, nom, condition):
        """La ligne du CSV qui remplit `condition`, attendue (l'écriture finit après le clic)."""
        for _ in range(100):
            trouvees = [ligne for ligne in lignes(dossier, nom) if condition(ligne)]
            if trouvees:
                return trouvees[-1]
            self.page.wait_for_timeout(100)
        self.fail("aucune ligne attendue dans " + nom)

    def sans_defilement(self, contexte):
        largeurs = self.page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        self.assertLessEqual(largeurs[0], largeurs[1], "défilement horizontal (%s) : %r" % (contexte, largeurs))


def etat(dossier, *noms):
    documents = dossier / "documents"
    return [(dossier / n).read_bytes() for n in noms + ("journal.csv",)] + [
        sorted(p.name for p in documents.iterdir()) if documents.is_dir() else []]


# ---------------------------------------------------------------------------
# Garantie
# ---------------------------------------------------------------------------

class TestGarantie(CasFormulaires):

    def test_garantie_erreurs_avant_ecriture_puis_creation_avec_document(self):
        page = self.page
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            (eq, repere), _ = equipements_actifs(dossier)[:2]
            fournisseur = lignes(dossier, "fournisseurs.csv")[0]
            self.ouvrir(serveur, "#/garanties/garantie/nouvelle")
            page.wait_for_selector("#form-garantie")
            avant = etat(dossier, "garanties.csv")
            self.assertEqual(page.inner_text(".garanties-page-formulaire h1"), "Nouvelle garantie")
            self.assertIn("Garanties et contrats", page.inner_text(".garanties-page-formulaire .fil"))

            # Erreurs sous les champs, rien d'écrit
            self.envoyer("#form-garantie")
            self.assertEqual(self.erreurs("#form-garantie"), {
                "equipement_id": "Choisissez l'équipement couvert.",
                "date_fin": "Saisissez la date de fin de la garantie."})
            page.fill("#form-garantie [name=date_debut]", "2027-01-02")
            page.fill("#form-garantie [name=date_fin]", "2027-01-01")
            page.set_input_files("#form-garantie input[type=file]", TEXTE)
            self.envoyer("#form-garantie")
            erreurs = self.erreurs("#form-garantie")
            self.assertEqual(erreurs["date_fin"], "La date de fin ne peut pas précéder la date de début.")
            self.assertEqual(erreurs["document"], "Le document doit être un PDF, un JPEG ou un PNG.")
            self.assertEqual(etat(dossier, "garanties.csv"), avant)

            # Équipement pré-rempli par ?equipement= ; Annuler revient à l'équipement
            self.aller("#/garanties/garantie/nouvelle?equipement=" + eq, "#form-garantie .selecteur-choisi:not([hidden])")
            self.assertEqual(page.input_value("#form-garantie input[name=equipement_id]"), eq)
            self.assertIn(repere, page.inner_text("#form-garantie .selecteur-resume"))
            self.assertEqual(page.get_attribute("#form-garantie a.btn-fantome", "href"), "#/equipement/" + eq)
            self.assertEqual(page.input_value("#form-garantie [name=date_fin]"), "")

            # Création avec le certificat : écrite, puis la fiche de la garantie
            page.select_option("#form-garantie [name=fournisseur_id]", fournisseur["id"])
            page.fill("#form-garantie [name=date_debut]", "2026-06-01")
            page.fill("#form-garantie [name=date_fin]", "2027-05-31")
            page.fill("#form-garantie [name=conditions]", "Pièces et main-d'œuvre, hors pièces d'usure")
            page.set_input_files("#form-garantie input[type=file]", PDF)
            page.evaluate(ESPION_JS)
            self.envoyer("#form-garantie")
            self.attendre_toast("Garantie enregistrée.")
            ligne = self.attendre_ligne(dossier, "garanties.csv", lambda l: l["equipement_id"] == eq)
            gar = ligne["id"]
            self.assertEqual({c: ligne[c] for c in ("fournisseur_id", "date_debut", "date_fin", "conditions", "actif")},
                             {"fournisseur_id": fournisseur["id"], "date_debut": "2026-06-01", "date_fin": "2027-05-31",
                              "conditions": "Pièces et main-d'œuvre, hors pièces d'usure", "actif": "1"})
            self.assertRegex(ligne["document"], r"^\d{8}-\d{6}-garantie-%s-\d{4}-\d{2}-\d{2}\.pdf$" % gar)
            self.assertEqual((dossier / "documents" / ligne["document"]).read_bytes(), PDF["buffer"])
            self.assertEqual(journal(dossier, "garanties", gar), ["création — garantie enregistrée ; document : " + ligne["document"]])
            self.assertEqual(page.evaluate("window.__adresses"), ["#/garanties/garantie/" + gar])

    def test_garantie_modifiee_aucune_modification_retiree_introuvable(self):
        page = self.page
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            (eq, repere), _ = equipements_actifs(dossier)[:2]
            fournisseur = lignes(dossier, "fournisseurs.csv")[0]
            self.ouvrir(serveur, "#/accueil")
            gar = page.evaluate("""(valeurs) => Garanties.creerGarantie(valeurs)""",
                                {"equipement_id": eq, "fournisseur_id": fournisseur["id"], "date_fin": "2027-05-31",
                                 "conditions": "Main-d'œuvre comprise"})
            self.aller("#/garanties/garantie/%s/modifier" % gar, "#form-garantie")
            self.assertEqual(page.inner_text(".garanties-page-formulaire h1"), "Modifier la garantie")
            self.assertIn(gar, page.inner_text(".garanties-page-formulaire .entete-page p"))
            self.assertEqual(page.input_value("#form-garantie input[name=equipement_id]"), eq)
            self.assertEqual(page.input_value("#form-garantie [name=fournisseur_id]"), fournisseur["id"])
            self.assertEqual(page.input_value("#form-garantie [name=date_fin]"), "2027-05-31")
            self.assertEqual(page.input_value("#form-garantie [name=conditions]"), "Main-d'œuvre comprise")
            self.assertEqual(page.get_attribute("#form-garantie a.btn-fantome", "href"), "#/garanties/garantie/" + gar)

            # Champs changés seulement
            page.select_option("#form-garantie [name=fournisseur_id]", "")
            page.fill("#form-garantie [name=date_fin]", "2027-06-30")
            self.envoyer("#form-garantie")
            self.attendre_toast("Garantie enregistrée.")
            self.attendre_ligne(dossier, "garanties.csv", lambda l: l["id"] == gar and l["date_fin"] == "2027-06-30")
            self.assertEqual(journal(dossier, "garanties", gar)[-1],
                             "modification : fournisseur_id, date_fin — modification de la garantie")

            # Rien de changé : rien d'écrit
            octets = (dossier / "garanties.csv").read_bytes()
            self.aller("#/garanties/garantie/%s/modifier" % gar, "#form-garantie")
            self.envoyer("#form-garantie")
            self.attendre_toast("Aucune modification à enregistrer.")
            self.assertEqual((dossier / "garanties.csv").read_bytes(), octets)

            # Retirée : plus de formulaire ; introuvable : expliqué
            page.evaluate("(id) => Garanties.retirerGarantie(id)", gar)
            self.aller("#/garanties/garantie/%s/modifier" % gar, ".garanties-zone-formulaire .alerte")
            self.assertIn("La garantie %s est retirée : elle ne se modifie plus." % gar,
                          page.inner_text(".garanties-zone-formulaire"))
            self.assertEqual(page.locator("#form-garantie").count(), 0)
            self.aller("#/garanties/garantie/GAR-9999/modifier", ".garanties-zone-formulaire .vide")
            self.assertIn("Garantie introuvable", page.inner_text(".garanties-zone-formulaire"))
            self.assertIn("La garantie GAR-9999 est introuvable.", page.inner_text(".garanties-zone-formulaire"))


# ---------------------------------------------------------------------------
# Contrat
# ---------------------------------------------------------------------------

class TestContrat(CasFormulaires):

    def test_contrat_erreurs_date_limite_avant_enregistrement_puis_creation(self):
        page = self.page
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            ajouter_ligne_csv(dossier / "parametres.csv", {"cle": "devise", "valeur": "CHF"})
            (eq1, repere1), (eq2, repere2) = equipements_actifs(dossier)[:2]
            fournisseur = lignes(dossier, "fournisseurs.csv")[0]
            self.ouvrir(serveur, "#/garanties/contrat/nouveau")
            page.wait_for_selector("#form-contrat")
            avant = etat(dossier, "contrats_prestataires.csv")
            self.assertEqual(page.inner_text(".garanties-page-formulaire h1"), "Nouveau contrat")
            # Montant dans la devise réglée, hors taxes (D190, Q9)
            self.assertEqual(page.inner_text("#form-contrat .champ[data-champ=montant_annuel] .libelle").strip(),
                             "Montant annuel (CHF HT)")
            self.assertEqual(self.date_limite(), "Date limite de résiliation : saisissez la fin de la période en cours.")
            self.assertTrue(page.is_hidden("#form-contrat .champ[data-champ=reconduction_mois]"))

            # Erreurs sous les champs, rien d'écrit
            self.envoyer("#form-contrat")
            self.assertEqual(self.erreurs("#form-contrat"), {
                "fournisseur_id": "Choisissez le prestataire.", "objet": "Saisissez l'objet du contrat.",
                "date_fin": "Saisissez la date de fin de la période en cours."})
            page.fill("#form-contrat [name=preavis_mois]", "1,5")
            page.fill("#form-contrat [name=montant_annuel]", "-5")
            self.envoyer("#form-contrat")
            erreurs = self.erreurs("#form-contrat")
            self.assertEqual(erreurs["preavis_mois"], "Préavis : un nombre entier de mois, 0 ou plus.")
            self.assertEqual(erreurs["montant_annuel"], "Montant : un nombre positif, ou rien.")

            # CS173 : la date limite de résiliation se voit à la saisie, avant tout enregistrement
            page.fill("#form-contrat [name=date_fin]", "2026-12-31")
            page.fill("#form-contrat [name=preavis_mois]", "3")
            self.assertEqual(self.date_limite(), "Date limite de résiliation : 30/09/2026")
            page.fill("#form-contrat [name=preavis_mois]", "")
            self.assertEqual(self.date_limite(), "Date limite de résiliation : 31/12/2026 (sans préavis, la fin de la période)")
            page.fill("#form-contrat [name=preavis_mois]", "3")
            # Avertissement non bloquant : le préavis dépasse la durée du contrat
            page.fill("#form-contrat [name=date_debut]", "2026-11-01")
            self.assertIn("Le préavis dépasse la durée du contrat", page.inner_text("#form-contrat .garanties-avertissement"))
            page.fill("#form-contrat [name=date_debut]", "2026-01-01")
            self.assertEqual(page.inner_text("#form-contrat .garanties-avertissement").strip(), "")
            self.assertEqual(etat(dossier, "contrats_prestataires.csv"), avant)

            # Reconduction tacite : la durée d'une reconduction apparaît
            page.check("#form-contrat [name=reconduction_tacite]")
            self.assertTrue(page.is_visible("#form-contrat .champ[data-champ=reconduction_mois]"))
            page.fill("#form-contrat [name=reconduction_mois]", "12")

            # Équipements concernés : puces, sans doublon, retirables
            self.assertTrue(page.is_disabled("#form-contrat .garanties-ajouter-equipement"))
            for equipement_id, repere in ((eq1, repere1), (eq2, repere2), (eq1, repere1)):
                self.choisir_equipement("#form-contrat", equipement_id, repere)
                page.click("#form-contrat .garanties-ajouter-equipement")
            self.assertEqual(self.puces(), [eq1, eq2])
            self.assertIn(repere2, page.inner_text("#form-contrat .garanties-puce[data-equipement='%s']" % eq2))
            page.click("#form-contrat .garanties-puce[data-equipement='%s'] button" % eq1)
            self.assertEqual(self.puces(), [eq2])
            self.choisir_equipement("#form-contrat", eq1, repere1)
            page.click("#form-contrat .garanties-ajouter-equipement")
            self.assertEqual(page.input_value("#form-contrat input[name=equipement_ids]"), eq2 + ";" + eq1)

            # Création avec le contrat signé
            page.select_option("#form-contrat [name=fournisseur_id]", fournisseur["id"])
            page.fill("#form-contrat [name=objet]", "Maintenance préventive des compresseurs")
            page.fill("#form-contrat [name=montant_annuel]", "4 800,50")
            page.set_input_files("#form-contrat input[type=file]", dict(PDF, name="contrat signé.pdf"))
            page.evaluate(ESPION_JS)
            self.envoyer("#form-contrat")
            self.attendre_toast("Contrat enregistré.")
            ligne = self.attendre_ligne(dossier, "contrats_prestataires.csv",
                                        lambda l: l["objet"] == "Maintenance préventive des compresseurs")
            ctp = ligne["id"]
            self.assertEqual({c: ligne[c] for c in ("fournisseur_id", "equipement_ids", "date_debut", "date_fin",
                                                    "preavis_mois", "reconduction_tacite", "reconduction_mois",
                                                    "montant_annuel", "actif")},
                             {"fournisseur_id": fournisseur["id"], "equipement_ids": eq2 + ";" + eq1,
                              "date_debut": "2026-01-01", "date_fin": "2026-12-31", "preavis_mois": "3",
                              "reconduction_tacite": "1", "reconduction_mois": "12", "montant_annuel": "4800.50",
                              "actif": "1"})
            self.assertRegex(ligne["document"], r"^\d{8}-\d{6}-contrat-%s-\d{4}-\d{2}-\d{2}\.pdf$" % ctp)
            self.assertEqual(journal(dossier, "contrats_prestataires", ctp),
                             ["création — contrat enregistré ; document : " + ligne["document"]])
            self.assertEqual(page.evaluate("window.__adresses"), ["#/garanties/contrat/" + ctp])

    def test_contrat_modifie_equipement_introuvable_et_reconduction_gardee(self):
        page = self.page
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            (eq1, repere1), _ = equipements_actifs(dossier)[:2]
            fournisseur = lignes(dossier, "fournisseurs.csv")[0]
            # Contrat écrit dans le fichier (un identifiant d'équipement qui n'existe plus ne s'écrit pas par l'écran)
            ajouter_ligne_csv(dossier / "contrats_prestataires.csv", {
                "id": "CTP-0901", "fournisseur_id": fournisseur["id"], "objet": "Vérification des compresseurs",
                "equipement_ids": eq1 + ";EQ-9999", "date_debut": "2026-01-01", "date_fin": "2026-12-31",
                "preavis_mois": "3", "reconduction_tacite": "1", "reconduction_mois": "12", "montant_annuel": "1200",
                "actif": "1"})
            self.ouvrir(serveur, "#/garanties/contrat/CTP-0901/modifier")
            page.wait_for_selector("#form-contrat")
            self.assertEqual(page.inner_text(".garanties-page-formulaire h1"), "Modifier le contrat")
            self.assertEqual(self.puces(), [eq1, "EQ-9999"])
            self.assertIn("équipement introuvable (EQ-9999)", page.inner_text("#form-contrat .garanties-puces"))
            self.assertEqual(self.date_limite(), "Date limite de résiliation : 30/09/2026")
            self.assertEqual(page.input_value("#form-contrat [name=montant_annuel]"), "1200")
            self.assertTrue(page.is_checked("#form-contrat [name=reconduction_tacite]"))
            self.assertEqual(page.input_value("#form-contrat [name=reconduction_mois]"), "12")
            self.assertEqual(page.get_attribute("#form-contrat a.btn-fantome", "href"), "#/garanties/contrat/CTP-0901")

            # L'équipement introuvable est refusé sous le champ, rien d'écrit
            avant = etat(dossier, "contrats_prestataires.csv")
            self.envoyer("#form-contrat")
            self.assertEqual(self.erreurs("#form-contrat"), {"equipement_ids": "L'équipement EQ-9999 est introuvable."})
            self.assertEqual(etat(dossier, "contrats_prestataires.csv"), avant)

            # Retiré de la liste ; sans reconduction tacite, la durée d'une reconduction (cachée) n'est ni contrôlée ni
            # changée
            page.click("#form-contrat .garanties-puce[data-equipement='EQ-9999'] button")
            page.fill("#form-contrat [name=reconduction_mois]", "abc")
            page.uncheck("#form-contrat [name=reconduction_tacite]")
            self.assertTrue(page.is_hidden("#form-contrat .champ[data-champ=reconduction_mois]"))
            self.envoyer("#form-contrat")
            self.attendre_toast("Contrat enregistré.")
            ligne = self.attendre_ligne(dossier, "contrats_prestataires.csv",
                                        lambda l: l["id"] == "CTP-0901" and l["reconduction_tacite"] == "0")
            self.assertEqual((ligne["equipement_ids"], ligne["reconduction_mois"], ligne["montant_annuel"]),
                             (eq1, "12", "1200"))
            self.assertEqual(journal(dossier, "contrats_prestataires", "CTP-0901")[-1],
                             "modification : equipement_ids, reconduction_tacite — modification du contrat")


# ---------------------------------------------------------------------------
# « Nouveau fournisseur… » : fenêtre du Magasin, saisie reprise
# ---------------------------------------------------------------------------

class TestFournisseur(CasFormulaires):

    def test_fournisseur_cree_depuis_le_contrat_saisie_reprise(self):
        page = self.page
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            (eq1, repere1), _ = equipements_actifs(dossier)[:2]
            fournisseurs_avant = [f["id"] for f in lignes(dossier, "fournisseurs.csv")]
            self.ouvrir(serveur, "#/garanties/contrat/nouveau")
            page.wait_for_selector("#form-contrat")
            page.fill("#form-contrat [name=objet]", "Nettoyage des filtres")
            page.fill("#form-contrat [name=date_fin]", "2026-12-31")
            page.fill("#form-contrat [name=preavis_mois]", "2")
            self.choisir_equipement("#form-contrat", eq1, repere1)
            page.click("#form-contrat .garanties-ajouter-equipement")
            page.set_input_files("#form-contrat input[type=file]", PDF)

            # Annuler la fenêtre : rien ne change
            page.click("#form-contrat .garanties-nouveau-fournisseur")
            page.wait_for_selector("dialog [name=nom]")
            page.click("dialog .fenetre-actions .btn-fantome")
            page.wait_for_selector("dialog [name=nom]", state="detached")
            self.assertEqual(page.input_value("#form-contrat [name=objet]"), "Nettoyage des filtres")

            # Fournisseur créé : l'écran est réaffiché avec la saisie, le nouveau fournisseur choisi
            page.click("#form-contrat .garanties-nouveau-fournisseur")
            page.wait_for_selector("dialog [name=nom]")
            page.fill("dialog [name=nom]", "Filtres Express")
            page.click("dialog .fenetre-actions .btn-primaire")
            self.attendre_toast("créé")
            nouveau = self.attendre_ligne(dossier, "fournisseurs.csv", lambda f: f["id"] not in fournisseurs_avant)
            self.assertEqual(nouveau["nom"], "Filtres Express")
            page.wait_for_function("(id) => { const l = document.querySelector('#form-contrat [name=fournisseur_id]');"
                                   " return l && l.value === id; }", arg=nouveau["id"])
            self.assertEqual(page.input_value("#form-contrat [name=objet]"), "Nettoyage des filtres")
            self.assertEqual(page.input_value("#form-contrat [name=date_fin]"), "2026-12-31")
            self.assertEqual(self.puces(), [eq1])
            self.assertEqual(self.date_limite(), "Date limite de résiliation : 31/10/2026")
            self.assertEqual(page.eval_on_selector("#form-contrat input[type=file]", "c => c.files.length"), 1)

            self.envoyer("#form-contrat")
            self.attendre_toast("Contrat enregistré.")
            ligne = self.attendre_ligne(dossier, "contrats_prestataires.csv", lambda l: l["objet"] == "Nettoyage des filtres")
            self.assertEqual((ligne["fournisseur_id"], ligne["equipement_ids"], ligne["preavis_mois"]),
                             (nouveau["id"], eq1, "2"))
            self.assertEqual((dossier / "documents" / ligne["document"]).read_bytes(), PDF["buffer"])


# ---------------------------------------------------------------------------
# Profils et téléphone
# ---------------------------------------------------------------------------

class TestProfilsEtTelephone(CasFormulaires):

    def test_profils_technicien_et_demandeur_renvoyes_a_l_accueil(self):
        with ServeurPrevo() as serveur:
            technicien = lignes(serveur.dossier, "techniciens.csv")[0]["id"]
            for profil, route in (("technicien", "#/garanties/garantie/nouvelle"),
                                  ("demandeur", "#/garanties/contrat/nouveau")):
                with self.subTest(profil=profil):
                    self.page.close()
                    self.contexte.close()
                    self.contexte = self.navigateur.new_context(locale="fr-FR")
                    self.page = self.contexte.new_page()
                    self.surveiller(self.page)
                    self.ouvrir(serveur, route, profil=profil, technicien_id=technicien if profil == "technicien" else "")
                    self.page.wait_for_function("location.hash === '#/accueil'")
                    self.assertEqual(self.page.locator("#form-garantie, #form-contrat").count(), 0)

    def test_telephone_375px_sans_defilement_horizontal(self):
        page = self.page
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            (eq1, repere1), (eq2, repere2) = equipements_actifs(dossier)[:2]
            self.ouvrir(serveur, "#/garanties/contrat/nouveau", largeur=375)
            page.set_viewport_size({"width": 375, "height": 812})
            page.wait_for_selector("#form-contrat")
            for equipement_id, repere in ((eq1, repere1), (eq2, repere2)):
                self.choisir_equipement("#form-contrat", equipement_id, repere)
                page.click("#form-contrat .garanties-ajouter-equipement")
            page.fill("#form-contrat [name=date_debut]", "2026-11-01")
            page.fill("#form-contrat [name=date_fin]", "2026-12-31")
            page.fill("#form-contrat [name=preavis_mois]", "3")
            page.check("#form-contrat [name=reconduction_tacite]")
            page.wait_for_selector("#form-contrat .garanties-avertissement .alerte")
            self.sans_defilement("contrat")
            for selecteur in ("#form-contrat button[type=submit]", "#form-contrat a.btn-fantome",
                              "#form-contrat .garanties-nouveau-fournisseur", "#form-contrat .garanties-ajouter-equipement",
                              "#form-contrat .garanties-puce button"):
                hauteur = page.eval_on_selector(selecteur, "e => e.getBoundingClientRect().height")
                self.assertGreaterEqual(hauteur, 48, selecteur)
            self.aller("#/garanties/garantie/nouvelle?equipement=" + eq1, "#form-garantie .selecteur-choisi:not([hidden])")
            self.sans_defilement("garantie")
            self.assertGreaterEqual(page.eval_on_selector("#form-garantie button[type=submit]",
                                                          "e => e.getBoundingClientRect().height"), 48)


if __name__ == "__main__":
    unittest.main()
