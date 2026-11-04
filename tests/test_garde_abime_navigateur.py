"""Garde « fichier abîmé » vue du navigateur, dans les deux modes (version corrective 1.2.1 ; même principe que T197 et
T200 de la 2.0).

Défaut de la 1.2.0 : un CSV abîmé (en-tête coupé, guillemet non fermé, valeur tapée à droite du tableau) était réécrit
par la première écriture venue — la génération des OT préventifs à l'ouverture, un formulaire, le passage au format —
et les valeurs que la lecture n'avait pas comprises étaient perdues sans avertissement. Correction : la garde est dans
la fonction d'écriture commune de chaque adaptateur (js/stockage-dossier.js, js/stockage-serveur.js, et serveur.py :
tests/test_garde_abime_serveur.py), Donnees refuse aussi plus tôt (ErreurFichierAbime), un bandeau « Fichier abîmé »
le dit dès l'ouverture, et le message ne fait rien perdre de la saisie.

    a. ParcoursGarde (mode serveur : ServeurPrevo ; mode dossier : OPFS simulé, servi par ServeurStatique) :
       - ouverture par le responsable sur le jeu entete-tronque : aucun fichier de données changé (ordres_travail.csv
         identique à l'octet, aucune sauvegarde), bandeau qui nomme le fichier et dit quoi faire ;
       - déclaration de panne par un demandeur (« Signaler un problème ») sur demandes.csv abîmé : message « prévenez
         le responsable », saisie restée dans le formulaire, fichiers identiques ;
       - journal.csv qui finit dans un guillemet ouvert : la modification d'un équipement réussit, le journal reste
         identique à l'octet ;
       - parametres.csv abîmé avec version_schema < 3 : le passage au format est refusé sans rien écrire (ni
         parametres.csv, ni sauvegarde « avant-format »), l'application s'ouvre avec le bandeau ; une seconde ouverture
         n'écrit rien non plus (aucune boucle) ;
    b. mode serveur seul : la fiche d'un OT (« Préparation ») sur ordres_travail.csv abîmé : message du responsable,
       texte resté dans le champ, fichier identique ;
    c. mode dossier seul : la modification d'un équipement sur equipements.csv abîmé (saisie gardée, fichier identique) ;
       restauration d'une sauvegarde par l'écran Paramètres par-dessus un fichier abîmé (permise : c'est le remède) ;
    d. TestTraductionServeur : réponses simulées (page.route) : le 409 « fichier_abime » du serveur devient
       Donnees.ErreurFichierAbime (jamais un conflit, qui serait réessayé) ; Donnees.ajouter ne se replie pas sur
       modifier ; une ligne de journal refusée ne fait pas échouer l'action (journaliser rend null) ;
    e. TestFonctions : Donnees.csv.finitDansUnGuillemetOuvert sur les 14 exemples partagés avec serveur.py, et même
       critère « abîmé » des deux côtés (Donnees.csv.analyser(...).abime et raisons_fichier_abime de serveur.py).

Règle numéro un : jamais de données réelles (copies de donnees/demo abîmées par programme, tests/jeux_abimes.py).

Lancer depuis la racine du projet, TOUJOURS à travers le verrou du navigateur :
    py -X utf8 -m unittest discover -s tests -p "test_garde_abime_navigateur.py" -v
"""
import base64
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from commun import (RACINE, CasNavigateur, ServeurPrevo, ServeurStatique, attendre_pret, charger_scripts,
                    installer_dossier_simule, preregler_profil, scenarios_demo)
from jeux_abimes import (avec_guillemet_ouvert, avec_note_en_trop, avec_version_schema, copier_demo, donnees_de,
                         entete_tronque, fichiers_de)
from test_garde_abime_serveur import EXEMPLES_GUILLEMET_OUVERT, SERVEUR

AIDE = "https://github.com/nicoboy49/prevo/issues"
CHEMIN_SAUVEGARDES = "Paramètres › Sauvegardes, bouton « Restaurer… »"
MESSAGE_AUTRE_PROFIL = ("Fichier abîmé : prévenez le responsable. Rien n'a été enregistré ; votre saisie est restée "
                        "dans le formulaire.")
MESSAGE_RESPONSABLE = ("Fichier abîmé (%s) : rien n'a été enregistré, pour ne rien perdre ; votre saisie est restée "
                       "dans le formulaire. Restaurez la sauvegarde du jour (" + CHEMIN_SAUVEGARDES + ") ou réparez le "
                       "fichier ; aide : " + AIDE)
OT_PREPARE = scenarios_demo()["ot_statut_prepare"]
NOM_DOSSIER = "donnees-garde-abime"
SAUVEGARDE_ANCIENNE = "2026-10-30"
REFUS_HTTP = re.compile(r"status of 409")          # Chromium note en console.error toute réponse HTTP >= 400
PING_SANS_SERVEUR = re.compile(r"status of 404.*/api/ping")   # mode dossier : aucun serveur Prévo ne répond

ECRIRE_OPFS_JS = """async ([nom, fichiers]) => {
  const racine = await (await navigator.storage.getDirectory()).getDirectoryHandle(nom, { create: true });
  for (const [chemin, enBase64] of Object.entries(fichiers)) {
    const morceaux = chemin.split('/');
    let dossier = racine;
    for (const sous of morceaux.slice(0, -1)) { dossier = await dossier.getDirectoryHandle(sous, { create: true }); }
    const binaire = atob(enBase64);
    const octets = new Uint8Array(binaire.length);
    for (let i = 0; i < binaire.length; i += 1) { octets[i] = binaire.charCodeAt(i); }
    const flux = await (await dossier.getFileHandle(morceaux[morceaux.length - 1], { create: true })).createWritable();
    await flux.write(octets);
    await flux.close();
  }
}"""

LIRE_OPFS_JS = """async (nom) => {
  const resultat = {};
  async function parcourir(dossier, prefixe) {
    for await (const entree of dossier.values()) {
      if (entree.kind === 'directory') { await parcourir(entree, prefixe + entree.name + '/'); continue; }
      const octets = new Uint8Array(await (await entree.getFile()).arrayBuffer());
      let binaire = '';
      for (let i = 0; i < octets.length; i += 0x8000) { binaire += String.fromCharCode.apply(null, octets.subarray(i, i + 0x8000)); }
      resultat[prefixe + entree.name] = btoa(binaire);
    }
  }
  await parcourir(await (await navigator.storage.getDirectory()).getDirectoryHandle(nom), '');
  return resultat;
}"""

BANDEAUX_JS = """() => Array.from(document.querySelectorAll('#alertes-app > *'))
  .map((e) => e.textContent.replace(/\\s+/g, ' ').trim())"""
TOAST_JS = "(t) => { const z = document.getElementById('toast'); return Boolean(z) && z.textContent.includes(t); }"


def en_base64(octets):
    return base64.b64encode(octets).decode("ascii")


def sauvegardes_de(fichiers):
    """Noms des dossiers de sauvegarde présents dans un {chemin : octets}."""
    return sorted({chemin.split("/")[1] for chemin in fichiers if chemin.startswith("sauvegardes/")
                   and chemin.count("/") >= 2})


class CasGarde(CasNavigateur):
    """Jeu de démo copié et abîmé par programme ; ouverture dans un mode (classe fille : ModeServeur, ModeDossier)."""

    def setUp(self):
        super().setUp()
        self.temporaire = Path(tempfile.mkdtemp(prefix="prevo-garde-nav-"))
        self.addCleanup(shutil.rmtree, str(self.temporaire), True)

    def jeu(self, abimes):
        """{fichier: fonction(octets) -> octets} appliquées à une copie de donnees/demo ; rend {chemin : octets}."""
        dossier = copier_demo(self.temporaire / "jeu")
        for nom, abimer in abimes.items():
            (dossier / nom).write_bytes(abimer((dossier / nom).read_bytes()))
        fichiers = fichiers_de(dossier)
        shutil.rmtree(str(dossier))
        return fichiers

    def aller(self, route, selecteur):
        self.page.evaluate("(route) => { location.hash = route; }", route)
        self.page.wait_for_selector(selecteur)

    def bandeaux(self):
        return self.page.evaluate(BANDEAUX_JS)

    def bandeau_abime(self, fichier):
        trouves = [texte for texte in self.bandeaux() if "Fichier abîmé : %s." % fichier in texte]
        self.assertEqual(len(trouves), 1, self.bandeaux())
        return trouves[0]

    def attendre_toast(self, texte):
        self.page.wait_for_function(TOAST_JS, arg=texte, timeout=10000)
        return self.page.evaluate("document.getElementById('toast').textContent").strip()

    def verifier_bandeau_responsable(self, fichier):
        texte = self.bandeau_abime(fichier)
        self.assertIn("pour ne rien perdre", texte)
        self.assertIn("Restaurez la sauvegarde du jour (" + CHEMIN_SAUVEGARDES + ")", texte)
        self.assertIn("réparez le fichier", texte)
        self.assertIn(AIDE, texte)
        self.assertEqual(self.page.locator("#alertes-app a[href='%s']" % AIDE).count(), 1)


class ModeServeur:

    def ouvrir(self, fichiers, profil, nom="", technicien_id=""):
        source = self.temporaire / "source" / "donnees"
        for chemin, octets in fichiers.items():
            (source / chemin).parent.mkdir(parents=True, exist_ok=True)
            (source / chemin).write_bytes(octets)
        self.serveur = ServeurPrevo(source=source)
        self.serveur.demarrer()
        self.addCleanup(self.serveur.arreter)
        self.autoriser_erreur(REFUS_HTTP)
        preregler_profil(self.contexte, profil, nom=nom, technicien_id=technicien_id)
        self.page.goto(self.serveur.url + "/#/accueil")
        attendre_pret(self.page, 30000)

    def rouvrir(self):
        self.page.reload()
        attendre_pret(self.page, 30000)

    def apres(self):
        self.page.wait_for_load_state("networkidle")
        return fichiers_de(self.serveur.dossier)


class ModeDossier:

    def ouvrir(self, fichiers, profil, nom="", technicien_id=""):
        self.statique = ServeurStatique(RACINE)
        self.statique.demarrer()
        self.addCleanup(self.statique.arreter)
        self.autoriser_erreur(PING_SANS_SERVEUR)
        installer_dossier_simule(self.contexte, NOM_DOSSIER)
        preregler_profil(self.contexte, profil, nom=nom, technicien_id=technicien_id)
        self.page.goto(self.statique.url + "/index.html")
        self.page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        self.page.evaluate(ECRIRE_OPFS_JS, [NOM_DOSSIER, {c: en_base64(o) for c, o in fichiers.items()}])
        self.page.click("#btn-dossier")
        attendre_pret(self.page, 30000)

    def rouvrir(self):
        self.page.reload()
        self.page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        self.page.click("#btn-dossier")
        attendre_pret(self.page, 30000)

    def apres(self):
        brut = self.page.evaluate(LIRE_OPFS_JS, NOM_DOSSIER)
        return {chemin: base64.b64decode(valeur) for chemin, valeur in brut.items()}


# ---------------------------------------------------------------------------
# a. Parcours communs aux deux modes
# ---------------------------------------------------------------------------

class ParcoursGarde:

    def test_ouverture_par_le_responsable_sur_entete_tronque_rien_d_ecrit_et_bandeau(self):
        fichiers = self.jeu({"ordres_travail.csv": entete_tronque})
        self.ouvrir(fichiers, "responsable")
        apres = self.apres()
        self.assertEqual(apres["ordres_travail.csv"], fichiers["ordres_travail.csv"],
                         "ordres_travail.csv abîmé réécrit à l'ouverture (génération des OT préventifs)")
        self.assertEqual(donnees_de(apres), donnees_de(fichiers))
        self.assertEqual(sauvegardes_de(apres), [])                    # rien d'écrit, sauvegarde du jour comprise
        self.verifier_bandeau_responsable("ordres_travail.csv")

    def test_declaration_de_panne_par_un_demandeur_sur_demandes_abime(self):
        fichiers = self.jeu({"demandes.csv": avec_note_en_trop})
        self.ouvrir(fichiers, "demandeur", nom="Léa Martin")
        description = "Goutte à goutte sous la garniture côté moteur."
        self.aller("#/di/nouvelle?equipement=EQ-0005", ".di-envoyer")
        self.page.click(".di-puce[data-symptome='Fuite']")
        self.page.click("label.tuile:has(input[value='dégradé'])")
        self.page.fill("textarea[name=description]", description)
        self.page.click(".di-envoyer")
        self.page.wait_for_function("(t) => document.querySelector('.di-numero') || (%s)(t)" % TOAST_JS,
                                    arg="Fichier abîmé", timeout=10000)
        self.assertEqual(donnees_de(self.apres())["demandes.csv"], fichiers["demandes.csv"],
                         "demandes.csv abîmé réécrit par l'envoi de la demande")
        self.assertEqual(donnees_de(self.apres()), donnees_de(fichiers))
        self.assertEqual(self.attendre_toast("Fichier abîmé"), MESSAGE_AUTRE_PROFIL)
        # La saisie est restée dans le formulaire, rien n'a été envoyé.
        self.assertEqual(self.page.locator(".di-numero").count(), 0)
        self.assertEqual(self.page.input_value("input[name=symptome]"), "Fuite")
        self.assertEqual(self.page.input_value("textarea[name=description]"), description)
        self.assertTrue(self.page.is_checked("input[name=impact][value='dégradé']"))
        self.assertTrue(self.page.is_enabled(".di-envoyer"))
        bandeau = self.bandeau_abime("demandes.csv")
        self.assertIn("prévenez le responsable", bandeau)
        self.assertNotIn("Restaurez", bandeau)

    def test_journal_qui_finit_dans_un_guillemet_ouvert_reste_identique_et_l_action_reussit(self):
        fichiers = self.jeu({"journal.csv": avec_guillemet_ouvert})
        self.ouvrir(fichiers, "responsable")
        self.assertEqual(self.apres()["journal.csv"], fichiers["journal.csv"],
                         "journal.csv complété à l'ouverture (génération des OT préventifs) malgré son guillemet ouvert")
        self.aller("#/equipement/EQ-0005/modifier", "#parc-formulaire")
        self.page.fill("#parc-formulaire [name=designation]", "Pompe centrifuge modifiée")
        self.page.click("#parc-formulaire button[type=submit]")
        self.page.wait_for_function("location.hash === '#/equipement/EQ-0005'")
        apres = self.apres()
        self.assertEqual(apres["journal.csv"], fichiers["journal.csv"],
                         "journal.csv complété malgré son guillemet ouvert : les lignes ajoutées seraient avalées")
        self.assertIn("Pompe centrifuge modifiée".encode("utf-8"), apres["equipements.csv"])
        self.verifier_bandeau_responsable("journal.csv")

    def test_parametres_abime_format_ancien_rien_d_ecrit_appli_ouverte_avec_le_bandeau(self):
        fichiers = self.jeu({"parametres.csv": lambda octets: avec_note_en_trop(avec_version_schema(octets, 2))})
        self.ouvrir(fichiers, "responsable")
        for ouverture in ("première", "seconde"):
            with self.subTest(ouverture=ouverture):
                if ouverture == "seconde":
                    self.rouvrir()
                apres = self.apres()
                self.assertEqual(apres["parametres.csv"], fichiers["parametres.csv"],
                                 "parametres.csv abîmé réécrit par le passage au format")
                self.assertEqual(donnees_de(apres), donnees_de(fichiers))
                self.assertEqual(sauvegardes_de(apres), [], "sauvegarde faite alors que rien n'est écrit")
                self.assertEqual(self.page.evaluate("Donnees.parametre('version_schema')"), "2")
                self.verifier_bandeau_responsable("parametres.csv")


class TestGardeServeur(ModeServeur, ParcoursGarde, CasGarde):

    # b. La fiche d'un OT (onglet Préparation) : message du responsable, saisie gardée.
    def test_fiche_d_un_ot_sur_ordres_travail_abime_saisie_gardee(self):
        fichiers = self.jeu({"ordres_travail.csv": avec_note_en_trop})
        self.ouvrir(fichiers, "responsable")
        self.aller("#/ot/" + OT_PREPARE, ".ot-fiche .ot-numero")
        self.page.click(".onglet[data-onglet='preparation']")
        texte = "Texte saisi pendant que le fichier est abîmé"
        self.page.fill("#form-preparation [name=travail_a_faire]", texte)
        self.page.click("#form-preparation button[type=submit]")
        self.page.wait_for_function("(t) => document.getElementById('toast') "
                                    "&& document.getElementById('toast').classList.contains('visible')",
                                    arg="", timeout=10000)
        self.assertEqual(donnees_de(self.apres())["ordres_travail.csv"], fichiers["ordres_travail.csv"],
                         "ordres_travail.csv abîmé réécrit par la fiche de l'OT")
        self.assertEqual(donnees_de(self.apres()), donnees_de(fichiers))
        self.assertEqual(self.attendre_toast("Fichier abîmé"), MESSAGE_RESPONSABLE % "ordres_travail.csv")
        self.assertEqual(self.page.input_value("#form-preparation [name=travail_a_faire]"), texte)
        self.verifier_bandeau_responsable("ordres_travail.csv")


class TestGardeDossier(ModeDossier, ParcoursGarde, CasGarde):

    # c. La modification d'un équipement : message du responsable, saisie gardée.
    def test_modification_d_un_equipement_sur_equipements_abime_saisie_gardee(self):
        fichiers = self.jeu({"equipements.csv": avec_note_en_trop})
        self.ouvrir(fichiers, "responsable")
        self.aller("#/equipement/EQ-0005/modifier", "#parc-formulaire")
        self.page.fill("#parc-formulaire [name=designation]", "Pompe centrifuge modifiée")
        self.page.fill("#parc-formulaire [name=marque]", "Hydronel SA")
        self.page.click("#parc-formulaire button[type=submit]")
        self.page.wait_for_function("(t) => location.hash === '#/equipement/EQ-0005' || (%s)(t)" % TOAST_JS,
                                    arg="Fichier abîmé", timeout=10000)
        apres = donnees_de(self.apres())
        self.assertEqual(apres["equipements.csv"], fichiers["equipements.csv"],
                         "equipements.csv abîmé réécrit par le formulaire")
        # Seuls les fichiers de la génération des OT préventifs à l'ouverture (ordres_travail.csv sain) ont changé.
        changes = {chemin for chemin, octets in apres.items() if fichiers.get(chemin) != octets}
        self.assertLessEqual(changes, {"ordres_travail.csv", "ot_operations.csv", "journal.csv"})
        self.assertEqual(self.attendre_toast("Fichier abîmé"), MESSAGE_RESPONSABLE % "equipements.csv")
        self.assertEqual(self.page.evaluate("location.hash"), "#/equipement/EQ-0005/modifier")
        self.assertEqual(self.page.input_value("#parc-formulaire [name=designation]"), "Pompe centrifuge modifiée")
        self.assertEqual(self.page.input_value("#parc-formulaire [name=marque]"), "Hydronel SA")
        self.verifier_bandeau_responsable("equipements.csv")

    # c. Le remède : restaurer une sauvegarde par l'écran Paramètres, par-dessus le fichier abîmé.
    def test_restauration_d_une_sauvegarde_par_dessus_un_fichier_abime(self):
        sains = self.jeu({})
        fichiers = dict(self.jeu({"ordres_travail.csv": entete_tronque}))
        for chemin, octets in donnees_de(sains).items():
            fichiers["sauvegardes/%s/%s" % (SAUVEGARDE_ANCIENNE, chemin)] = octets
        self.ouvrir(fichiers, "responsable")
        self.aller("#/parametres", '#carte-sauvegardes button[data-restaurer="%s"]' % SAUVEGARDE_ANCIENNE)
        self.page.click('button[data-restaurer="%s"]' % SAUVEGARDE_ANCIENNE)
        self.page.wait_for_selector("#fenetre-restauration")
        self.page.check("#fenetre-restauration input[name=portee][value=une]")
        self.page.select_option("#fenetre-restauration select[name=table]", "ordres_travail")
        self.page.click("dialog .fenetre-actions .btn-danger")
        self.page.wait_for_selector("#nom-copie-securite")
        securite = self.page.inner_text("#nom-copie-securite").strip()
        apres = self.apres()
        self.assertEqual(apres["ordres_travail.csv"], sains["ordres_travail.csv"])
        # Le fichier abîmé reste dans la copie de sécurité faite juste avant (rien n'est perdu).
        self.assertEqual(apres["sauvegardes/%s/ordres_travail.csv" % securite], fichiers["ordres_travail.csv"])


# ---------------------------------------------------------------------------
# d. Traduction du 409 « fichier_abime » par js/stockage-serveur.js (réponses simulées)
# ---------------------------------------------------------------------------

REFUS_ABIME = {"erreur": "Fichier abîmé (journal.csv) : rien n'a été enregistré.", "code": "fichier_abime",
               "table": "journal"}
CONFLIT_GENERIQUE = {"erreur": "Le fichier equipements.csv a été modifié par un autre poste.",
                     "version_actuelle": "0123456789abcdef"}

ESSAI_JS = """
  const essai = async (action) => {
    try { return { ok: true, valeur: await action() }; } catch (erreur) {
      return { ok: false, nom: erreur.name, message: erreur.message,
        abime: typeof Donnees.ErreurFichierAbime === 'function' && erreur instanceof Donnees.ErreurFichierAbime,
        conflit: erreur instanceof Donnees.ErreurConflit, stockage: erreur instanceof Donnees.ErreurStockage,
        table: erreur.table === undefined ? null : erreur.table };
    }
  };
"""

TRADUCTION_JS = """async () => {""" + ESSAI_JS + """
  const stockage = StockageServeur.creer();
  const octets = new TextEncoder().encode('id;date_heure;poste;profil;table;id_ligne;action\\r\\n');
  return {
    ajout: await essai(() => stockage.ajouter('journal', octets)),
    enregistrement: await essai(() => stockage.enregistrer('journal', octets, 'v1')),
    conflit: await essai(() => stockage.enregistrer('equipements', octets, 'v1')),
  };
}"""

DONNEES_JS = """async () => {""" + ESSAI_JS + """
  Donnees.initialiser(StockageServeur.creer(), { poste: 'Poste test', profil: 'Technicien TEC-0001' });
  const ajout = await essai(() => Donnees.ajouter('journal', [{ id: 'J-20261104140000-AAAA', action: 'essai' }]));
  const journalise = await Donnees.journaliser('equipements', 'EQ-0005', 'essai');
  return { ajout: ajout, journalise: journalise };
}"""


class TestTraductionServeur(CasNavigateur):

    def setUp(self):
        super().setUp()
        self.autoriser_erreur("Failed to load resource")
        self.statique = ServeurStatique(RACINE)
        self.statique.demarrer()
        self.addCleanup(self.statique.arreter)
        self.requetes = []
        self.page.route("**/api/**", self.repondre)
        self.page.goto(self.statique.url + "/tests/fixtures/page-stockage-serveur.html")
        self.page.wait_for_function("typeof StockageServeur === 'object' && typeof Donnees === 'object'")

    def repondre(self, route):
        requete = route.request
        chemin = requete.url.split("/api/", 1)[1]
        self.requetes.append((requete.method, chemin))
        if requete.method == "GET":
            route.fulfill(status=404, content_type="application/json", body=json.dumps({"erreur": "absent"}))
        elif chemin.startswith("csv/journal"):
            route.fulfill(status=409, content_type="application/json; charset=utf-8",
                          body=json.dumps(REFUS_ABIME, ensure_ascii=False))
        else:
            route.fulfill(status=409, content_type="application/json; charset=utf-8",
                          body=json.dumps(CONFLIT_GENERIQUE, ensure_ascii=False))

    def test_409_fichier_abime_traduit_en_erreur_fichier_abime_jamais_en_conflit(self):
        resultats = self.page.evaluate(TRADUCTION_JS)
        for cle in ("ajout", "enregistrement"):
            with self.subTest(appel=cle):
                resultat = resultats[cle]
                self.assertEqual((resultat["ok"], resultat["nom"], resultat["abime"], resultat["conflit"],
                                  resultat["stockage"], resultat["table"]),
                                 (False, "ErreurFichierAbime", True, False, True, "journal"), resultat)
                self.assertEqual(resultat["message"], MESSAGE_AUTRE_PROFIL)       # profil inconnu : pas responsable
        conflit = resultats["conflit"]                                            # le 409 sans code reste un conflit
        self.assertEqual((conflit["nom"], conflit["conflit"], conflit["abime"]), ("ErreurConflit", True, False))

    def test_donnees_ajouter_sans_repli_et_ligne_de_journal_refusee_sans_echec(self):
        resultat = self.page.evaluate(DONNEES_JS)
        self.assertEqual((resultat["ajout"]["nom"], resultat["ajout"]["abime"]), ("ErreurFichierAbime", True),
                         resultat["ajout"])
        self.assertIsNone(resultat["journalise"])            # journaliser n'échoue jamais : null, l'action continue
        # Aucun repli sur modifier (ni relecture, ni réécriture du journal) : deux ajouts, rien d'autre.
        self.assertEqual(self.requetes, [("POST", "csv/journal/ajout")] * 2)


# ---------------------------------------------------------------------------
# e. Fonctions : automate du guillemet ouvert et critère « abîmé », les mêmes qu'au serveur
# ---------------------------------------------------------------------------

def cas_du_critere():
    """{nom : (table, octets)} : les 24 fichiers de la démo (sains) et des fichiers abîmés ou limites."""
    demo = RACINE / "donnees" / "demo"
    cas = {chemin.name: (chemin.stem, chemin.read_bytes()) for chemin in sorted(demo.glob("*.csv"))}
    ordres = (demo / "ordres_travail.csv").read_bytes()
    journal = (demo / "journal.csv").read_bytes()
    bom = b"\xef\xbb\xbf"
    cas.update({
        "en-tête coupé": ("ordres_travail", entete_tronque(ordres)),
        "valeur tapée à droite du tableau": ("ordres_travail", avec_note_en_trop(ordres)),
        "guillemet non fermé": ("ordres_travail", ordres + 'OT-9999;"jamais fermé\r\n'.encode()),
        "texte collé à un guillemet fermant": ("ordres_travail", ordres + b'OT-9998;"ferm\xc3\xa9"colle;x\r\n'),
        "journal qui finit dans un guillemet ouvert": ("journal", avec_guillemet_ouvert(journal)),
        "Windows-1252, valeur en trop": ("ordres_travail",
                                         avec_note_en_trop(ordres).decode("utf-8").encode("cp1252", "replace")),
        "séparateur virgule, valeur en trop": ("equipements", bom + b"id,designation\r\nEQ-1,Tour,en trop\r\n"),
        "lignes courtes": ("equipements", bom + b"id;designation;repere\r\nEQ-1\r\nEQ-2;Tour\r\n"),
        "cellule blanche en trop": ("equipements", bom + b"id;designation\r\nEQ-1;Tour; \r\n"),
        "vide": ("equipements", b""),
        "BOM seul": ("equipements", bom),
        "blancs": ("equipements", bom + b"  \r\n\r\n"),
    })
    return cas


CRITERE_JS = """(cas) => {
  const resultat = {};
  for (const [nom, [table, enBase64]] of Object.entries(cas)) {
    const binaire = atob(enBase64);
    const octets = new Uint8Array(binaire.length);
    for (let i = 0; i < binaire.length; i += 1) { octets[i] = binaire.charCodeAt(i); }
    resultat[nom] = Donnees.csv.analyser(table, octets).abime;
  }
  return resultat;
}"""


class TestFonctions(CasNavigateur):

    def setUp(self):
        super().setUp()
        charger_scripts(self.page, ["js/lib/papaparse.min.js", "js/schema.js", "js/donnees.js"])

    def test_fin_dans_un_guillemet_ouvert_les_14_exemples_partages_avec_le_serveur(self):
        exemples = [list(octets) for octets, _ in EXEMPLES_GUILLEMET_OUVERT]
        obtenus = self.page.evaluate("""(exemples) => exemples.map((liste) => {
          const octets = Uint8Array.from(liste);
          return [Donnees.csv.finitDansUnGuillemetOuvert(octets), Donnees.csv.finitDansUnGuillemetOuvert(octets.buffer)];
        })""", exemples)
        self.assertEqual(len(obtenus), 14)
        for (octets, attendu), (sur_vue, sur_tampon) in zip(EXEMPLES_GUILLEMET_OUVERT, obtenus):
            with self.subTest(octets=octets):
                self.assertIs(sur_vue, attendu)
                self.assertIs(sur_tampon, attendu)
                self.assertIs(SERVEUR.finit_dans_un_guillemet_ouvert(octets), attendu)

    def test_meme_critere_abime_dans_le_navigateur_et_au_serveur(self):
        cas = cas_du_critere()
        navigateur = self.page.evaluate(CRITERE_JS, {nom: [table, en_base64(octets)] for nom, (table, octets) in cas.items()})
        for nom, (table, octets) in cas.items():
            with self.subTest(cas=nom):
                serveur = bool(SERVEUR.raisons_fichier_abime(octets))
                self.assertIs(navigateur[nom], serveur, "navigateur %r, serveur %r" % (navigateur[nom], serveur))
        attendus_abimes = {"en-tête coupé", "valeur tapée à droite du tableau", "guillemet non fermé",
                           "texte collé à un guillemet fermant", "journal qui finit dans un guillemet ouvert",
                           "Windows-1252, valeur en trop", "séparateur virgule, valeur en trop"}
        self.assertEqual({nom for nom, abime in navigateur.items() if abime}, attendus_abimes)


if __name__ == "__main__":
    unittest.main()
